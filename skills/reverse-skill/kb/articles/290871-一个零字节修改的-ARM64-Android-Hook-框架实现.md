---
title: '[原创]一个零字节修改的 ARM64 Android Hook 框架实现'
url: https://bbs.kanxue.com/thread-290871.htm
tid: 290871
author: REerr
date: '2026-04-19'
tags: [Android安全, 原创, 逆向分析, HOOK注入, 源码框架, 工具脚本]
crawled_at: '2026-08-08T10:10:51+00:00'
replies: 123
---

# 一个零字节修改的 ARM64 Android Hook 框架（完整实现与踩坑记）

>
> **代码仓库**：<https://github.com/xiaokanghub/ptehooker>（GPL-2.0）
>
>
> 环境基线：Xiaomi M2102K1AC / Android 13 (API 33) / Kernel 5.4.233 / APatch v0.12.2 (KernelPatch 框架)
>
>
> 代码共 ~1800 行 KPM + ~3000 行 Python host。文中代码片段可直接复用。
>
>
>

---

## 〇、前言

起点是看雪 [thread-290718](https://bbs.kanxue.com/thread-290718.htm) 第 7.2 节提出的"方案 C"骨架：

>
> *查名片，找老巢：读取目标 Java 方法 ArtMethod 结构体中的 entry_point_from_quick_compiled_code_ 指针。*
>
>
> *布设隐形陷阱：不对这个指针做任何修改。直接拿着真实的指令地址，呼叫内核 KPM 在这里拉起 UXN 高压电网。*
>
>
>

这句话给出了方向但没落地。本文记录把它做成**生产级**框架（能在 aweme 这种 7000+ VMA、高密度的商用 APP 上稳定跑）的全过程，重点是**可复现的工程细节**：

- 每个机制的完整 C / ARM64 代码
- 实际遇到的两个内核级深坑（DBI X17 clobber、Ghost UAF）的排查日志和修复补丁
- 真实调试过程中的 ghost 字节 dump、offset_map 对比
- 完整的构建 / 部署 / 调试命令链

读完应该能复现整个框架或独立实现同样的机制。

目标效果的一组数据：

| 指标 | 数值 |
|-|-|
| aweme Pass 3 fault 处理 | **267,735 次 / 30 秒 / 0 崩溃** |
| KPM 代码规模 | ~1800 行 .c |
| 目标进程 `/proc/maps` 里的痕迹 | 0 个新 VMA |
| 目标进程 `TracerPid` | 0 |
| ArtMethod 字节修改 | 0（默认模式） |
| 单元测试 | 29 个全过 |

---

## 一、项目定位和威胁模型

### 它不是什么

- 不是 Frida 替代品（没有 QuickJS、Stalker、eBPF trace）
- 不是即插即用工具（需要 Root + APatch / KernelPatch）
- 不能对抗 kernel-level PTE 级反作弊

### 它是什么

以 **stealth** 为唯一设计目标的 ARM64 Android hook 框架，三条硬红线：

1. **不往目标进程注入任何 `.so`**
2. **不 ptrace、不改 TracerPid**
3. **不改 ArtMethod / 代码段任何一个字节**（默认 7.2 trap 模式）

### 威胁模型矩阵

| 检测手段 | 我们能否过 |
|-|-|
| 扫 `/proc/pid/maps` | ✅ 看不到 |
| 扫 TracerPid / ptrace_scope | ✅ |
| `dl_iterate_phdr` 遍历 `.so` | ✅ |
| CRC / MD5 of `.text` pages | ✅ 字节未改 |
| 扫 `ArtMethod.entry_point` 是否落在合法 oat 段 | ✅ 字段未改 |
| 扫 `ArtMethod.access_flags` ACC_NATIVE bit 变化 | ✅ |
| `/proc/self/pagemap` PFN 对比（用户态） | ✅ 只翻 PTE 里 1 个 bit，PFN 不变 |
| Kernel 驱动扫 PTE.UXN | ❌ 能看到（但反作弊一般没这权限） |
| 时序检测（fault 后 μs 级延迟） | ⚠️ 首次取指有延迟，稳态影响小 |

---

## 二、ARM64 PTE 和 UXN 位（背景知识）

ARM64 的页表项（PTE）是 64 位，相关的几个位：

```python
bit  63: NSE (非安全扩展)
bit  62-61: 保留 / IGNORED
bit  60-59: Contiguous / DBM
bit  58-55: 软件位（内核可用）
bit  54: UXN (Unprivileged eXecute Never) ← ★我们的陷阱开关
bit  53: PXN (Privileged eXecute Never)
bit  52: Contiguous
bit  51-50: 保留
bit  50: GP (Guarded Page, ARMv8.5 BTI)
bit  49-12: 物理页帧号 PFN
bit  11-10: NG, AF
bit   9-8: SH (Shareability)
bit   7-6: AP (Access Permission)
         bit 7 = AP[2]: 0 = RW, 1 = RO
         bit 6 = AP[1]: 0 = kernel only, 1 = user+kernel
bit   5: NS
bit   4-2: Attr Index
bit   1-0: Block / Page type
\```

**UXN = 1** 时，EL0（用户态）从该页取指令 → Instruction Abort → 进入内核 `do_mem_abort`。**数据读写不受影响**。

关键：**只翻这 1 个 bit，物理页帧、其他权限、属性都不变**。对反作弊读页内容完全透明 —— 他读的还是原字节。

这是 7.2 方案的物理基础。

---

## 三、KernelPatch / KPM 框架入口

APatch 把 Linus 的 kernel 补过一个 patch 后，提供**自定义内核模块 (KPM)** 运行环境：

- 通过 `supercall` 系统调用（编号 45）+ 预设的 superkey 鉴权
- KPM 能注册 `KPM_INIT / KPM_CTL0 / KPM_EXIT`
- 能调 `kallsyms_lookup_name` 拿内核符号

我们的 KPM 主入口如下：

```c
// ptehook_planc_v2.c

#include &lt;compat.h&gt;
#include &lt;kallsyms.h&gt;
#include &lt;hook.h&gt;
#include "dbi_kern.h"
#include "ghost_mm.h"

/* 通过 kallsyms 拿到的内核符号 */
typedef int  (*access_process_vm_t)(struct task_struct *, unsigned long,
                                     void *, int, unsigned int);
typedef void *(*get_task_mm_t)(struct task_struct *);
typedef void  (*mmput_t)(struct mm_struct *);
typedef int  (*apply_to_page_range_t)(struct mm_struct *mm, unsigned long addr,
                                       unsigned long size, pte_fn_t fn, void *data);
typedef unsigned long (*get_free_pages_t)(unsigned int, unsigned int);
typedef void (*free_pages_t)(unsigned long, unsigned int);
typedef void *(*find_vma_t)(struct mm_struct *, unsigned long);
typedef void (*on_each_cpu_t)(void (*fn)(void *), void *arg, int wait);

static access_process_vm_t   fn_access_process_vm;
static get_task_mm_t         fn_get_task_mm;
static mmput_t               fn_mmput;
static apply_to_page_range_t fn_apply_to_page_range;
static get_free_pages_t      fn_get_free_pages;
static free_pages_t          fn_free_pages;
static find_vma_t            fn_find_vma;
static const int64_t        *ptr_physvirt_offset;
static on_each_cpu_t         fn_on_each_cpu;
static void                 *addr_do_mem_abort;

static long planc2_init(const char *args, const char *event, void *__user r)
{
    fn_access_process_vm   = (access_process_vm_t)kallsyms_lookup_name("access_process_vm");
    fn_get_task_mm         = (get_task_mm_t)kallsyms_lookup_name("get_task_mm");
    fn_mmput               = (mmput_t)kallsyms_lookup_name("mmput");
    fn_apply_to_page_range = (apply_to_page_range_t)kallsyms_lookup_name("apply_to_page_range");
    fn_get_free_pages      = (get_free_pages_t)kallsyms_lookup_name("__get_free_pages");
    fn_free_pages          = (free_pages_t)kallsyms_lookup_name("free_pages");
    fn_find_vma            = (find_vma_t)kallsyms_lookup_name("find_vma");
    ptr_physvirt_offset    = (const int64_t *)kallsyms_lookup_name("physvirt_offset");
    fn_on_each_cpu         = (on_each_cpu_t)kallsyms_lookup_name("on_each_cpu");
    addr_do_mem_abort      = (void *)kallsyms_lookup_name("do_mem_abort");

    /* 把这些指针塞进 ghost_mm 模块 */
    struct ghost_mm_syms gsyms = {
        .get_free_pages      = fn_get_free_pages,
        .free_pages          = fn_free_pages,
        .find_vma            = fn_find_vma,
        .apply_to_page_range = fn_apply_to_page_range,
        .physvirt_offset_p   = ptr_physvirt_offset,
        .on_each_cpu         = fn_on_each_cpu,
    };
    ghost_mm_init(&gsyms);

    return 0;
}

static long planc2_ctl0(const char *args, char *__user out_msg, int outlen)
{
    static char buf[4096];
    int off = 0;
    const char *p = args;

    if (str_starts_with(p, "uxn-hook")) {
        /* parse: uxn-hook &lt;pid&gt; <target_va> <replace_va> */
        int pid = parse_num(&p);
        unsigned long target  = parse_num(&p);
        unsigned long replace = parse_num(&p);
        off = cmd_uxn_hook(pid, target, replace, buf, sizeof(buf));
    }
    else if (str_starts_with(p, "uxn-unhook")) {
        /* ... */
    }
    else if (str_starts_with(p, "ghost-alloc-at")) {
        /* ... */
    }
    else if (str_starts_with(p, "proc-read")) {
        /* ... */
    }
    /* 省略其他 10 多条命令 */

    compat_copy_to_user(out_msg, buf, off < outlen ? off + 1 : outlen);
    return 0;
}

KPM_INIT(planc2_init);
KPM_CTL0(planc2_ctl0);
KPM_EXIT(planc2_exit);
\```

用户态工具 `ptehook_ctl` 负责：

1. 读取 `/data/adb/ptehook/superkey`
2. 调 `syscall(45, superkey, ...)` 进入 KernelPatch 代码
3. KernelPatch 转发到我们注册的 `planc2_ctl0`
4. 命令参数是 ASCII 字符串（好解析、好加新命令）

---

## 四、Ghost 内存：无 VMA 的物理页映射

### 4.1 为什么要 VMA-less

Shellcode 和 DBI 重编译代码需要放在目标进程**可执行**的内存里。普通 mmap 出来的内存：

- 会在 `/proc/pid/maps` 出现
- 会在 `/proc/pid/smaps` 计数 RSS
- 会被 `dl_iterate_phdr` 和 VMA walker 发现

要规避这些，必须**绕过 VMA 子系统，直接在进程页表里插 PTE**。

### 4.2 核心代码

```c
// ghost_mm.c

struct ghost_page {
    struct task_struct *task;
    struct mm_struct   *mm;
    unsigned long       vaddr;         // 目标进程用户态 VA
    unsigned long       kaddr;         // 内核 linear-map VA（我们写 shellcode 用）
    unsigned long       pfn;            // 物理页帧号
    uint64_t            installed_pte;  // 已装的 PTE 值
    int                 order;          // 2^order 页
    unsigned long       alloc_size;
    int                 installed;
};

struct install_ctx {
    uint64_t pte_val;
    int      written;
};

static int install_pte_cb(void *pte_ptr, unsigned long addr, void *data)
{
    struct install_ctx *c = (struct install_ctx *)data;
    uint64_t *p = (uint64_t *)pte_ptr;
    if (*p != 0 && (*p & PTE_VALID)) return -EEXIST;
    *p = c->pte_val;
    c->written = 1;
    return 0;
}

int ghost_alloc(struct task_struct *task, struct mm_struct *mm,
                unsigned long near, unsigned long range,
                uint64_t pte_template, int num_pages,
                struct ghost_page *out)
{
    unsigned long kva;
    unsigned long vaddr;
    uint64_t pa_base, new_pte;
    int order = pages_to_order(num_pages);
    int i, ret;

    // 1. 分配 2^order 个物理页
    kva = g_syms.get_free_pages(GFP_KERNEL | GFP_ZERO, order);
    if (!kva) return -ENOMEM;
    pa_base = (uint64_t)((int64_t)kva + *g_syms.physvirt_offset_p);

    // 2. 在目标 mm 找空洞 VA
    vaddr = find_hole_near(mm, near, range, 1 << order);
    if (!vaddr) { g_syms.free_pages(kva, order); return -ENOSPC; }

    // 3. 逐页安装 PTE
    for (i = 0; i < (1 << order); i++) {
        uint64_t page_pa = pa_base + (uint64_t)i * 0x1000;
        struct install_ctx ictx;

        new_pte  = (pte_template & ~ARM64_PFN_MASK) | (page_pa & ARM64_PFN_MASK);
        new_pte |= PTE_VALID | PTE_TYPE_PAGE | PTE_AF;
        new_pte &= ~PTE_UXN;               // 允许执行
        new_pte &= ~(1UL << 50);           // 清 GP (BTI 强制位)
        new_pte &= ~(1UL << 7);            // 清 AP[2] (允许写入 shellcode)

        ictx.pte_val = new_pte;
        ictx.written = 0;
        ret = g_syms.apply_to_page_range(mm, vaddr + i * 0x1000, 0x1000,
                                           install_pte_cb, &ictx);
        if (ret || !ictx.written) {
            // 回滚已装的 PTE
            int j;
            for (j = 0; j < i; j++) {
                struct clear_ctx cctx = { .cleared = 0 };
                g_syms.apply_to_page_range(mm, vaddr + j * 0x1000, 0x1000,
                                            clear_pte_cb, &cctx);
            }
            g_syms.free_pages(kva, order);
            return -EFAULT;
        }
    }

    // 4. TLB 刷新
    asm volatile(
        "dsb ishst\n\t"
        "tlbi vmalle1is\n\t"
        "dsb ish\n\t"
        "isb\n\t"
        ::: "memory"
    );

    out->task = task;
    out->mm = mm;
    out->vaddr = vaddr;
    out->kaddr = kva;
    out->pfn = pa_base >> 12;
    out->installed_pte = new_pte;
    out->order = order;
    out->alloc_size = (1UL << order) * 0x1000;
    out->installed = 1;
    return 0;
}
\```

### 4.3 PTE 模板的诡异性

`pte_template` 参数很关键 —— 是**从邻居 VMA 抓来的** PTE 作为模板：

```c
/* 调用前：先读附近一个正常 libart r-xp 页的 PTE 作为模板 */
pop.mode = 0;                // read mode
pop.out_val = &tpte;
fn_apply_to_page_range(mm, libart_page, 0x1000, pte_op_cb, &pop);
/* 然后调 ghost_alloc(..., pte_template=tpte, ...) */
\```

为什么这样做？因为 PTE 里的很多属性（MAIR index、NS、SH 等）来自 CPU 内存模型，直接瞎填会得到 uncached 或错误 shareability 的页。**从邻居继承**保证我们的 ghost 页和 libart r-xp 在 cache/coherence 行为上一致。

### 4.4 find_hole_near 的坑

早期版本有个实际上机才发现的 bug：

```c
/* 原版 */
if (gap_end - gap_start >= 0x1000) {   // 只要求 1 页空洞
    /* pick this gap */
}
\```

在 aweme 这种密集进程里，`num_pages=8`（DBI 最坏展开）时，单页空洞不够。安装第 2 页 PTE 时撞到相邻 VMA → `-EEXIST` → 回滚 → `-ENOSPC`。

修复：

```c
static unsigned long find_hole_near(struct mm_struct *mm, unsigned long near,
                                     unsigned long range, int num_pages)
{
    unsigned long need = (unsigned long)num_pages * 0x1000;
    /* ... iterate VMAs ... */
    if (gap_end - gap_start >= need) {   // 要求连续 num_pages 页
        /* pick */
    }
}
\```

---

## 五、Fault handler：UXN hook 的心脏

`do_mem_abort` 是 ARM64 内核处理用户态 fault 的入口。我们用 KernelPatch 的 `hook_wrap3` 把它 wrap 住：

```c
// ptehook_planc_v2.c

struct uxn_hook_slot {
    int used;
    int pid;
    unsigned long target_addr;        // 精确 hook 点
    unsigned long target_page;         // target_addr & ~0xFFF
    unsigned long replace_addr;        // 用户 shellcode VA
    uint64_t saved_pte;                // 原 PTE (unhook 恢复用)
    struct dbi_page_ctx dbi;           // DBI 状态
    struct ghost_page gp;              // DBI 重编译 ghost
    unsigned long fault_hits;
    unsigned long pass3_hits;
    unsigned long last_pass3_far;
    unsigned long last_pass3_new_pc;
};

#define UXN_HOOK_MAX 16
static struct uxn_hook_slot uxn_hooks[UXN_HOOK_MAX];

static void before_do_mem_abort(hook_fargs3_t *fargs, void *udata)
{
    unsigned long  far  = fargs->arg0;
    unsigned long  esr  = fargs->arg1;
    void          *regs_vp = (void *)fargs->arg2;
    unsigned int   ec, ifsc;
    unsigned long *pc_ptr;
    uint64_t       new_pc;
    int            i, cur_pid;

    /* 1. ESR 过滤：只处理 EL0 instruction abort + permission fault */
    ec = (esr >> 26) & 0x3F;
    if (ec != 0x20) return;              /* 不是 EL0 instruction abort */
    ifsc = esr & 0x3F;
    if (ifsc < 0x0C || ifsc > 0x0F) return;   /* 不是 permission fault */

    /* 2. pt_regs 里的 PC 在 +0x100 (A13 kernel 5.4 offset) */
    pc_ptr = (unsigned long *)((char *)regs_vp + 0x100);

    /* 3. 过滤本次 fault 的进程 */
    cur_pid = fn_task_pid_nr_ns ? fn_task_pid_nr_ns(current, 0, 0) : 0;

    /* Pass 2: 精确 target 匹配 → 我们的 shellcode */
    for (i = 0; i < UXN_HOOK_MAX; i++) {
        struct uxn_hook_slot *s = &uxn_hooks[i];
        if (!s->used) continue;
        if (cur_pid && s->pid != cur_pid) continue;
        if ((far & ~3UL) == (s->target_addr & ~3UL)) {
            *pc_ptr = s->replace_addr;     /* ← 改 PC */
            fargs->skip_origin = 1;        /* 告诉 KernelPatch: 别走原 handler */
            s->fault_hits++;
            return;
        }
    }

    /* Pass 3: 同页其他 FAR → DBI 重编译版本 */
    for (i = 0; i < UXN_HOOK_MAX; i++) {
        struct uxn_hook_slot *s = &uxn_hooks[i];
        if (!s->used) continue;
        if (cur_pid && s->pid != cur_pid) continue;
        if (s->target_page != (far & ~0xFFFUL)) continue;

        new_pc = dbi_target_to_ghost_pc(&s->dbi, far);
        if (new_pc) {
            *pc_ptr = new_pc;
            fargs->skip_origin = 1;
            s->fault_hits++;
            s->pass3_hits++;
            s->last_pass3_far    = far;
            s->last_pass3_new_pc = new_pc;
            return;
        }
    }

    /* 不匹配：放行给原 do_mem_abort（会 SIGSEGV user process） */
}

/* 首次 uxn_hook 安装时挂 hook_wrap3 */
if (!g_hook_installed) {
    hook_wrap3(addr_do_mem_abort, before_do_mem_abort, after_do_mem_abort, 0);
    g_hook_installed = 1;
}
\```

### 5.1 关键设计点

1. **Pass 2 > Pass 3 优先级**：exact target 先匹配，避免同 target_addr 既是 hook 入口又被当成 fallthrough
2. **per-PID 过滤**：防止旧 hook slot（上一个 APP 实例已死）污染新进程
3. **ESR 过滤**：只处理相关 fault 类型，其他 fault（比如真 data abort）放行
4. **`fargs->skip_origin = 1`**：KernelPatch 的 wrap3 机制约定，设 1 就不走原 `do_mem_abort`（否则会 double handle）

### 5.2 cmd_uxn_hook 完整流程

```c
static int cmd_uxn_hook(int pid, unsigned long target, unsigned long replace,
                         char *buf, int bsize)
{
    struct task_struct *task;
    struct mm_struct *mm;
    struct uxn_hook_slot *s;
    unsigned long target_page = target & ~0xFFFUL;
    struct pte_op pop;
    uint64_t tpte;
    int slot, ghost_pages, r;

    /* 0. 老 slot 清理 + slot 查找 */
    reap_dead_uxn_slots();
    if (find_uxn_slot_by_target(pid, target) >= 0) return fail("already hooked");

    slot = find_uxn_slot();
    s = &uxn_hooks[slot];
    task = find_task(pid);
    mm = fn_get_task_mm(task);

    /* 1. 读目标页 4KB 原字节 → s->orig_buf */
    r = fn_access_process_vm(task, target_page, s->orig_buf,
                              DBI_TARGET_SIZE, FOLL_FORCE);

    /* 2. 读 target PTE (unhook 恢复用) */
    pop.mode = 0;
    pop.out_val = &tpte;
    fn_apply_to_page_range(mm, target_page, 0x1000, pte_op_cb, &pop);

    /* 3. pre-DBI 算 ghost 需要多少页 */
    s->dbi.target_page = target_page;
    s->dbi.ghost_page  = 0;              /* 第一趟用 dummy 算 size */
    s->dbi.orig        = s->orig_buf;
    s->dbi.ghost       = s->ghost_buf;
    s->dbi.ghost_capacity = DBI_GHOST_MAX_INSNS;
    dbi_recompile_page(&s->dbi);
    ghost_pages = (s->dbi.ghost_count * 4 + 0xFFF) >> 12;

    /* 4. 分配 DBI ghost（先试 ±512MB 近 libart，失败则 ±8GB） */
    r = ghost_alloc(task, mm, target_page, 512UL << 20, tpte,
                     ghost_pages, &s->gp);
    if (r == -ENOSPC) {
        r = ghost_alloc(task, mm, target_page, 8UL << 30, tpte,
                         ghost_pages, &s->gp);
    }

    /* 5. 二次 DBI，用真 ghost_page */
    s->dbi.ghost_page = s->gp.vaddr;
    dbi_recompile_page(&s->dbi);

    /* 6. 把重编译字节写入 ghost */
    ghost_write(&s->gp, 0, s->ghost_buf, s->dbi.ghost_count * 4);
    ghost_sync_icache(&s->gp);

    /* 7. 保存 slot 状态 */
    s->used = 1;
    s->pid = pid;
    s->target_addr  = target;
    s->target_page  = target_page;
    s->replace_addr = replace;
    s->saved_pte    = tpte;
    s->fault_hits = s->pass3_hits = 0;
    asm volatile("dmb ish" ::: "memory");

    /* 8. 首次装 hook 时挂 do_mem_abort */
    if (!g_hook_installed) {
        hook_wrap3(addr_do_mem_abort, before_do_mem_abort, after_do_mem_abort, 0);
        g_hook_installed = 1;
    }

    /* 9. 在 target PTE 设 UXN=1 + TLB flush */
    pop.mode = 1;   /* set UXN */
    fn_apply_to_page_range(mm, target_page, 0x1000, pte_op_cb, &pop);
    asm volatile(
        "dsb ishst\n\t"
        "tlbi vmalle1is\n\t"
        "dsb ish\n\t"
        "isb\n\t"
        ::: "memory"
    );

    fn_mmput(mm);
    return ok("slot=%d ghost=0x%lx backup=0x%lx", slot, s->gp.vaddr,
               dbi_target_to_ghost_pc(&s->dbi, target));
}
\```

---

## 六、DBI 引擎：整页代码重编译

### 6.1 为什么要 DBI

UXN 是**按页**生效的。目标方法 entry_point 在某个 4KB 页上，但**整页的所有函数**调用都会触发 fault。比如 `art_quick_to_interpreter_bridge` 和 `art_quick_imt_conflict_trampoline` 可能在同一页。不 hook 这些 helper 的时候，他们的调用也会被我们的 UXN 挡住，必须能正确 fallthrough 到原逻辑。

DBI 的任务：**把整页代码重编译一份到 ghost，所有 PC-relative 指令修复成能从 ghost 执行**。

### 6.2 数据结构

```c
// dbi_kern.h

#define DBI_TARGET_SIZE      4096
#define DBI_TARGET_INSNS     1024
#define DBI_GHOST_MAX_INSNS  8192       // 最坏展开 8x

struct dbi_page_ctx {
    uint64_t target_page;
    uint64_t ghost_page;
    const uint32_t *orig;
    uint32_t *ghost;
    int ghost_capacity;
    int ghost_count;

    /* 核心：target word idx → ghost word idx */
    uint16_t offset_map[DBI_TARGET_INSNS];

    /* 前向 intra-page 条件跳转的回填队列 */
    struct dbi_pending_branch pending[512];
    int n_pending;

    int fixed, expanded, passthrough, failed, intra_page_fixed;
};

struct dbi_pending_branch {
    int       ghost_idx;         // ghost 中的字节位置（需回填）
    uint32_t  enc_template;      // 不带 imm 的模板
    uint16_t  target_tidx;       // target page 内的 word idx
    uint8_t   kind;              // 0=B.cond 1=CBZ 2=TBZ 3=B
};
\```

### 6.3 ARM64 指令分类和处理

```c
// dbi_kern.c

static int recomp_b(struct dbi_page_ctx *ctx, uint32_t insn, uint64_t orig_pc);
static int recomp_bl(struct dbi_page_ctx *ctx, uint32_t insn, uint64_t orig_pc);
static int recomp_bcond(struct dbi_page_ctx *ctx, uint32_t insn, uint64_t orig_pc);
static int recomp_cbz(struct dbi_page_ctx *ctx, uint32_t insn, uint64_t orig_pc);
static int recomp_tbz(struct dbi_page_ctx *ctx, uint32_t insn, uint64_t orig_pc);
static int recomp_adrp(struct dbi_page_ctx *ctx, uint32_t insn, uint64_t orig_pc);
static int recomp_adr(struct dbi_page_ctx *ctx, uint32_t insn, uint64_t orig_pc);
static int recomp_ldr_lit(struct dbi_page_ctx *ctx, uint32_t insn, uint64_t orig_pc,
                            int variant);
static int recomp_ldr_vec_lit(struct dbi_page_ctx *ctx, uint32_t insn, uint64_t orig_pc);

int dbi_recompile_page(struct dbi_page_ctx *ctx)
{
    int i;
    ctx->ghost_count = 0;
    ctx->fixed = ctx->expanded = ctx->passthrough = ctx->failed = 0;
    ctx->intra_page_fixed = 0;
    ctx->n_pending = 0;

    for (i = 0; i < DBI_TARGET_INSNS; i++) {
        uint32_t insn = ctx->orig[i];
        uint64_t orig_pc = ctx->target_page + (uint64_t)(i * 4);
        int prev_ghost_idx = ctx->ghost_count;
        int rc = 0;

        ctx->offset_map[i] = (uint16_t)prev_ghost_idx;

        /* NOP */
        if (insn == 0xD503201F) { ctx->passthrough++; rc = emit(ctx, insn); }
        /* B imm26 */
        else if ((insn & 0xFC000000) == 0x14000000) rc = recomp_b(ctx, insn, orig_pc);
        /* BL imm26 */
        else if ((insn & 0xFC000000) == 0x94000000) rc = recomp_bl(ctx, insn, orig_pc);
        /* B.cond */
        else if ((insn & 0xFF000010) == 0x54000000) rc = recomp_bcond(ctx, insn, orig_pc);
        /* CBZ/CBNZ */
        else if ((insn & 0x7E000000) == 0x34000000) rc = recomp_cbz(ctx, insn, orig_pc);
        /* TBZ/TBNZ */
        else if ((insn & 0x7E000000) == 0x36000000) rc = recomp_tbz(ctx, insn, orig_pc);
        /* ADRP */
        else if ((insn & 0x9F000000) == 0x90000000) rc = recomp_adrp(ctx, insn, orig_pc);
        /* ADR */
        else if ((insn & 0x9F000000) == 0x10000000) rc = recomp_adr(ctx, insn, orig_pc);
        /* LDR (literal) 32-bit W reg */
        else if ((insn & 0xFF000000) == 0x18000000) rc = recomp_ldr_lit(ctx, insn, orig_pc, 0);
        /* LDR (literal) 64-bit X reg */
        else if ((insn & 0xFF000000) == 0x58000000) rc = recomp_ldr_lit(ctx, insn, orig_pc, 1);
        /* LDRSW (literal) 32-bit sign-extended to X */
        else if ((insn & 0xFF000000) == 0x98000000) rc = recomp_ldr_lit(ctx, insn, orig_pc, 2);
        /* PRFM (literal) → drop to NOP */
        else if ((insn & 0xFF000000) == 0xD8000000) { ctx->expanded++; rc = emit(ctx, 0xD503201F); }
        /* SIMD LDR (literal) S/D/Q reg */
        else if ((insn & 0x3F000000) == 0x1C000000) rc = recomp_ldr_vec_lit(ctx, insn, orig_pc);
        /* 其他：透传 */
        else { ctx->passthrough++; rc = emit(ctx, insn); }

        if (rc < 0) {
            ctx->failed++;
            ctx->ghost_count = prev_ghost_idx;
            emit(ctx, 0xD503201F);       /* NOP 填位 */
        }
    }

    /* 回填前向 intra-page 条件跳转 */
    for (int p = 0; p < ctx->n_pending; p++) {
        struct dbi_pending_branch *b = &ctx->pending[p];
        uint64_t target_ghost = ctx->ghost_page + (uint64_t)ctx->offset_map[b->target_tidx] * 4;
        uint64_t patch_pc = ctx->ghost_page + (uint64_t)b->ghost_idx * 4;
        int64_t delta = (int64_t)(target_ghost - patch_pc);
        uint32_t enc;

        if (b->kind == 0 || b->kind == 1) {        /* B.cond, CBZ: imm19 */
            int64_t imm19 = delta / 4;
            enc = b->enc_template | (((uint32_t)imm19 & 0x7FFFFU) << 5);
        } else if (b->kind == 2) {                  /* TBZ: imm14 */
            int64_t imm14 = delta / 4;
            enc = b->enc_template | (((uint32_t)imm14 & 0x3FFFU) << 5);
        } else {                                     /* B: imm26 */
            int64_t imm26 = delta / 4;
            enc = b->enc_template | ((uint32_t)imm26 & 0x03FFFFFFU);
        }
        ctx->ghost[b->ghost_idx] = enc;
    }
    return 0;
}

uint64_t dbi_target_to_ghost_pc(const struct dbi_page_ctx *ctx,
                                 uint64_t target_pc)
{
    if (target_pc < ctx->target_page) return 0;
    uint64_t off = target_pc - ctx->target_page;
    if (off >= DBI_TARGET_SIZE) return 0;
    unsigned idx = (unsigned)(off >> 2);
    return ctx->ghost_page + (uint64_t)ctx->offset_map[idx] * 4;
}
\```

### 6.4 一个典型 recomp：ADRP

ADRP 是 PC-relative 的，在 ghost 位置执行时计算结果会错。解法是换成绝对地址加载：

```c
static int recomp_adrp(struct dbi_page_ctx *ctx, uint32_t insn, uint64_t orig_pc)
{
    uint32_t rd    = insn & 0x1FU;
    uint64_t immlo = (insn >> 29) & 0x3U;
    uint64_t immhi = (insn >> 5) & 0x7FFFFU;
    int64_t imm21 = sign_extend64((immhi << 2) | immlo, 21);
    uint64_t target = (orig_pc & ~0xFFFULL) + ((uint64_t)imm21 << 12);
    ctx->expanded++;
    return emit_load_addr(ctx, rd, target);      /* MOVZ/MOVK 4 条展成绝对加载 */
}

/* emit_load_addr：4 条 MOV 加载 64-bit 立即数到 rd */
static int emit_load_addr(struct dbi_page_ctx *ctx, uint32_t rd, uint64_t addr)
{
    uint32_t movs[4];
    int n = emit_mov_imm64(rd, addr, movs, 4);
    if (n < 0) return -1;
    for (int i = 0; i < n; i++) {
        if (emit(ctx, movs[i]) < 0) return -1;
    }
    return 0;
}

static int emit_mov_imm64(uint32_t rd, uint64_t imm, uint32_t *out, int max_insns)
{
    int n = 0, first = 1;
    for (int shift = 0; shift < 64; shift += 16) {
        uint16_t chunk = (uint16_t)((imm >> shift) & 0xFFFFU);
        uint32_t hw = (uint32_t)(shift / 16);

        if (chunk == 0) {
            if (!first) continue;                /* 非首条 + 零块 → 跳过 */
            if (imm != 0) continue;              /* 首条但 imm 非零 → 继续找首个非零 */
        }
        if (n >= max_insns) return -1;

        if (first) {
            /* MOVZ Xd, #chunk, LSL #(hw*16) : opc=00, bit[30:29] */
            out[n++] = 0xD2800000U | (hw << 21) | ((uint32_t)chunk << 5) | (rd & 0x1FU);
            first = 0;
        } else {
            /* MOVK Xd, #chunk, LSL #(hw*16) : opc=11 */
            out[n++] = 0xF2800000U | (hw << 21) | ((uint32_t)chunk << 5) | (rd & 0x1FU);
        }
    }
    if (first) {
        /* imm == 0 的边界 */
        out[n++] = 0xD2800000U | (rd & 0x1FU);
    }
    return n;
}
\```

### 6.5 更有意思的 recomp：条件分支 + 回填

B.cond 的 imm19 只够 ±1MB 范围。ADRP 修复过的代码在 ghost 里比原地址偏移大，原 B.cond 可能超范围。同时**如果目标在同一 hooked 页**，最好跳到 ghost 里对应位置（而不是原 VA → UXN 反弹）—— 这就是我们最重要的 bugfix（见第 7 节）：

```c
static int recomp_bcond(struct dbi_page_ctx *ctx, uint32_t insn, uint64_t orig_pc)
{
    int64_t imm19 = sign_extend64((insn >> 5) & 0x7FFFFU, 19);
    uint64_t target = orig_pc + (imm19 << 2);
    uint32_t cond = insn & 0xFU;
    uint32_t enc;

    /* intra-page：不 clobber 寄存器 */
    if (is_intra_page(ctx, target)) {
        uint32_t tidx = (uint32_t)((target - ctx->target_page) >> 2);
        uint32_t this_tidx = (uint32_t)((orig_pc - ctx->target_page) >> 2);

        if (tidx < this_tidx) {
            /* 后向：offset_map 已填，直接 emit */
            uint64_t gtarget = ctx->ghost_page + (uint64_t)ctx->offset_map[tidx] * 4;
            int64_t delta = (int64_t)(gtarget - ghost_cur_pc(ctx));
            if (enc_b_cond(cond, delta, &enc) == 0) {
                ctx->intra_page_fixed++;
                return emit(ctx, enc);
            }
        } else {
            /* 前向：emit placeholder，主循环后回填 */
            int ghost_idx = ctx->ghost_count;
            uint32_t tpl = 0x54000000U | (cond & 0xFU);   /* imm19=0 */
            if (emit(ctx, tpl) < 0) return -1;
            queue_pending_branch(ctx, ghost_idx, tpl, (uint16_t)tidx, 0);
            ctx->intra_page_fixed++;
            return 0;
        }
    }

    /* inter-page：老路径 */
    {
        uint64_t new_pc = ghost_cur_pc(ctx);
        int64_t delta = (int64_t)(target - new_pc);
        if (enc_b_cond(cond, delta, &enc) == 0) {
            ctx->fixed++;
            return emit(ctx, enc);
        }
    }

    /* 超范围：反转条件 + 远跳 */
    ctx->expanded++;
    {
        int bcond_idx = ctx->ghost_count;
        int after_idx;
        int64_t skip_delta;
        if (emit(ctx, 0) < 0) return -1;
        if (emit_far_jump(ctx, target) < 0) return -1;     /* MOVZ X17 + BR */
        after_idx = ctx->ghost_count;
        skip_delta = (int64_t)((after_idx - bcond_idx) * 4);
        if (enc_b_cond(cond ^ 1U, skip_delta, &enc) < 0) return -1;
        ctx->ghost[bcond_idx] = enc;
        return 0;
    }
}
\```

---

## 七、踩坑记一：DBI X17 Clobber 根因（最深的坑）

整个项目最深的一个坑。第一次崩的时候是 hook aweme 的 `MSManager.frameSign`，app 跑 5-20s 必崩：

```python
Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0xaa110420
pc  000000787bd33464  /apex/com.android.art/lib64/libart.so (artInvokeInterfaceTrampoline+248)
lr  000000784c8f3100  &lt;unknown&gt;
x0  000000787b81a078  x1  00000000199cf9e8
x17 000000787bd3336c
x20 000000787b81a078      ← 关键：这看起来像 libart VA 而不是 ART 对象
x24 00000000aa1103e0      ← ldr w8,[x24,#64] = 0xaa110420 → 未映射
\```

### 7.1 排查过程

**第一步：反汇编崩点**

libart.so 里 `artInvokeInterfaceTrampoline+0xF8` 反汇编：

```python
733464: ldr w8, [x24, #64]     ← 崩在这
\```

X24 本应是个 `mirror::Object*`，但拿到了 `0xaa1103e0` —— **完全不像 ART heap 指针**（ART 用 TBI tag 0xb4 或 low-ram 0x70 开头）。

**第二步：向上追 X24**

```python
7333bc: mov x20, x0                   ; X20 = X0
...
733430: ldr w24, [x20]                ; X24 = [X20] 低 32 位
733450: mov x0, x24
733454: bl ReadBarrier::Mark
733458: mov x24, x0                   ; X24 = ReadBarrier 结果
733464: ldr w8, [x24, #64]             ; 崩
\```

X24 从 `[X20]` 读出来，X20 源自 X0。

**看崩点 X20 = 0x787b81a058**。这是 libart.so 里 `cmp x0, x17` 这条指令所在的 VA（offset 0x58）。也就是说 **X0 入 BL 时是 libart 代码段 VA**，根本不是对象。

**第三步：看调用点**

`bl artInvokeInterfaceTrampoline` 在 `art_quick_imt_conflict_trampoline` 里：

```python
21a050: ldr x16, [x0, #16]          ; IMT 表遍历
21a054: ldr x0, [x16]
21a058: cmp x0, x17                  ; X17 = 调用者传入的 IMT key
21a05c: b.eq #16 (21a06c)
21a060: cbz x0, #24 (21a078)         ; 表末尾 → 跳 21a078
21a064: ldr x0, [x16, #16]!
21a068: b #-16 (21a058)               ; 循环回跳
21a078: mov x0, x17                   ; ★ 找不到 → X0 = IMT key
...
21a0d4: bl artInvokeInterfaceTrampoline
\```

按 ART 约定，X17 **在整个 trampoline 函数体内都是 IMT key**。走到 `mov x0, x17` 时把 key 放 X0，BL 交给 artInvokeInterfaceTrampoline。

**第四步：X17 什么时候不对的？**

崩溃时 X17 = `0x787bd3336c` = `artInvokeInterfaceTrampoline` 函数入口。这是 BL 展开成 `MOVZ/MOVK X17 + BLR X17` 之后的值，**已经是 BL 本身污染的**。X0 的值在 BL 之前就确定了。

真正要找的是 **`mov x0, x17` 执行那一瞬间 X17 是什么**。

X0 at crash = 0x787b81a058 = libart `cmp x0, x17` 指令地址。**这不是巧合**。X17 在 `mov x0, x17` 执行时就已经是 `0x787b81a058` 了。

**第五步：dump ghost 字节**

重现崩溃，保留 KPM 里的 ghost 物理页，通过 `ghost-read` 命令读出 8KB：

```python
$ /data/local/tmp/ptehook_ctl $SK raw ghost-read 8919 0x784c8f3000 1024
\```

对照 `offset_map` 定位 `b #-16` 这条循环回跳指令在 ghost 里变成了什么：

```python
target word idx 26 (原指令 0x17fffffc, b #-16 到 idx 22) → ghost word 29-32:
  g[29]  0xd2940b11    MOVZ X17, #0xa058
  g[30]  0xf2bcec31    MOVK X17, #0xe761, LSL #16
  g[31]  0xf2c00e71    MOVK X17, #0x73, LSL #32
  g[32]  0xd61f0220    BR X17
\```

装上：**X17 = 0x73e761a058**（= target page + offset 0x58 = libart 里 `cmp x0, x17` 的 VA）。

**就是这里**！`b #-16` 回跳到 `0x21a058`。target VA 和 ghost VA 距离 218MB > B 的 ±128MB 范围，DBI 展开成 `MOVZ X17 + BR X17`。**展开过程把 X17 写成了跳转目标的绝对 VA**。

BR 后 CPU 跳到原 VA 0x21a058，触发 UXN 反弹 → Pass 3 → ghost 对应位置继续跑。**但 X17 已经被污染**。后续 `cmp x0, x17` / `cbz x0` / `mov x0, x17` 全部用脏值，X0 拿到 0x787b81a058，传给 artInvokeInterfaceTrampoline，崩在 +248。

### 7.2 问题本质

ARM AAPCS64 规定 X16/X17 是 **IPR scratch**，函数调用过程中可以被 linker 存根污染。但 **ART trampolines 不遵守 AAPCS**：它们用 X17 传 IMT key 贯穿整个函数体。DBI 只看指令语义不看 ART 调用约定，就用 X17 做了远跳 scratch。

### 7.3 修复

彻底方案：**intra-page 分支的目标翻译到 ghost VA，绝不用 far-jump 展开**。

- Ghost 总大小 <32KB，永远在 CBZ ±1MB、B ±128MB 范围内
- 1 条原指令就能表达，**不用任何 scratch 寄存器**

实现要点在 6.5 节的 `recomp_bcond` 里看得见：前向分支因为 offset_map 还没填，先 emit placeholder，加到 pending 队列，主循环结束后回填。

完整修复涉及 4 个 recomp 函数（B, B.cond, CBZ, TBZ）。`recomp_b` 的片段：

```c
static int recomp_b(struct dbi_page_ctx *ctx, uint32_t insn, uint64_t orig_pc)
{
    int64_t imm26 = sign_extend64(insn & 0x03FFFFFFU, 26);
    uint64_t target = orig_pc + (imm26 << 2);
    uint32_t enc;

    if (is_intra_page(ctx, target)) {
        uint32_t tidx      = (target   - ctx->target_page) >> 2;
        uint32_t this_tidx = (orig_pc  - ctx->target_page) >> 2;

        if (tidx < this_tidx) {
            /* 后向：offset_map[tidx] 已填 */
            uint64_t gtarget = ctx->ghost_page + (uint64_t)ctx->offset_map[tidx] * 4;
            int64_t delta = (int64_t)(gtarget - ghost_cur_pc(ctx));
            if (enc_b(delta, &enc) == 0) {
                ctx->intra_page_fixed++;
                return emit(ctx, enc);
            }
        } else {
            /* 前向：queue pending，主循环后回填 */
            int ghost_idx = ctx->ghost_count;
            uint32_t tpl = 0x14000000U;     /* B opcode, imm26=0 */
            if (emit(ctx, tpl) < 0) return -1;
            queue_pending_branch(ctx, ghost_idx, tpl, (uint16_t)tidx, 3);
            ctx->intra_page_fixed++;
            return 0;
        }
    }

    /* inter-page：原流程（超范围展成 MOVZ/MOVK X17 + BR X17，此时 X17 clobber
       无所谓，因为跨页跳转后对方不依赖 X17） */
    {
        uint64_t new_pc = ghost_cur_pc(ctx);
        int64_t delta = (int64_t)(target - new_pc);
        if (enc_b(delta, &enc) == 0) { ctx->fixed++; return emit(ctx, enc); }
    }
    ctx->expanded++;
    return emit_far_jump(ctx, target);
}
\```

### 7.4 验证

修复前：aweme 5-20s 必崩。

修复后：

```python
[+] uxn-hook @ 0x73e761a430 → ghost 0x748f063000
[ 1s] hits=31869  pass3=31869  last_far=0x73e761a050
[ 5s] hits=121832 pass3=121832
[10s] hits=230782 pass3=230780
[12s] hits=267735 pass3=267732
[30s] hits=267735 pass3=267732     ← aweme idle, 无新流量
\```

**267,735 次 Pass 3 命中，aweme 零崩溃**。平均 22k 命中/秒吞吐。

---

## 八、踩坑记二：Ghost 物理页 UAF

DBI 修好后，又发现一个新问题：**`jit_watch` 动态切换 hook 会导致内核 panic / 设备 reboot**。

### 8.1 场景

`jit_watch` 是后台 Python 线程，轮询 `ArtMethod.entry_point`。ART 会在运行中把方法从 Nterp 升级到 JIT，entry_point 随之变化 —— 我们的 hook 钉在旧 ep 就失效。watcher 检测到变化会：

```python
def _rehook_if_drifted(self, h):
    current_ep = K.proc_read_u64(self.pid, am + _ep_offset())
    if current_ep != h.meta['orig_ep']:
        K.uxn_unhook(self.pid, h.meta['orig_ep'])     # 卸旧 hook
        backup = K.uxn_hook(self.pid, current_ep, ghost)   # 装新 hook
        /* 重写 shellcode */
\```

**aweme 高 Pass 3 流量下**（22k/s），这个切换导致内核 panic。

### 8.2 根因

`uxn_unhook` 做这些事：

```c
s->used = 0;                           // 1. slot 不可用
asm volatile("dmb ish");
...
pop.mode = 2;                          // 2. 恢复原 PTE (UXN=0)
fn_apply_to_page_range(mm, target_page, 0x1000, pte_op_cb, &pop);
asm volatile("tlbi vmalle1is; dsb ish; isb");
ghost_free(&s->gp);                    // 3. 释放物理页
\```

`tlbi vmalle1is` 只保证**未来**的取指走 PTE（此时 PTE 已恢复原 libart 页）。但**CPU 当前正在执行的指令序列是从 I-cache 里来的**：

- 一条已 fetch 的指令会跑完
- I-cache 缓存的 code line 也继续可执行（ARM64 是 VIPT I-cache，不需要 TLB 就能 hit）
- 直到遇到 I-cache miss 才会重新 fetch

**此时 `ghost_free` 把物理页还给 buddy allocator**。Allocator 转手给下一个申请者，写入新数据。**I-cache miss 时再从物理页取 → 拿到垃圾指令 → 用户态 UDF 或内核 panic**。

### 8.3 修复：IPI + I-cache 广播

```c
// ghost_mm.c

/* 每个 CPU 执行的 IPI handler，强制过异常入口 + I-cache 失效 */
static void ghost_free_drain_ipi(void *arg)
{
    asm volatile(
        "ic ialluis\n\t"      /* invalidate I-cache inner-shareable */
        "dsb ish\n\t"
        "isb\n\t"
        ::: "memory"
    );
}

int ghost_free(struct ghost_page *gp)
{
    int i, page_count = 1 << gp->order;

    /* 1. 清 PTE */
    for (i = 0; i < page_count; i++) {
        struct clear_ctx cctx = { .cleared = 0 };
        g_syms.apply_to_page_range(gp->mm, gp->vaddr + i * 0x1000,
                                     0x1000, clear_pte_cb, &cctx);
    }

    /* 2. TLB + I-cache 广播失效 */
    asm volatile(
        "dsb ishst\n\t"
        "tlbi vmalle1is\n\t"
        "dsb ish\n\t"
        "ic ialluis\n\t"              /* ★ 关键 */
        "dsb ish\n\t"
        "isb\n\t"
        ::: "memory"
    );

    /* 3. IPI 所有 CPU 同步等待。异常返回 serialises 取指。*/
    if (g_syms.on_each_cpu) {
        g_syms.on_each_cpu(ghost_free_drain_ipi, NULL, 1);
    }

    /* 4. 现在安全：没有任何 CPU 能从 ghost 物理页执行 */
    g_syms.free_pages(gp->kaddr, gp->order);

    gp->installed = 0;
    return 0;
}
\```

**原理**：

- ARM64 异常入口（包括 IPI）是 context-synchronization event，架构保证 serialises instruction fetch
- 每个 CPU 收到 IPI → 进 exception entry → 执行 `ic ialluis` → `dsb ish` → `isb` → 返回
- 所有核都走过这个流程后，**再没有 CPU 能从 ghost 物理页的指令上继续**

`on_each_cpu` 通过 `kallsyms_lookup_name("on_each_cpu")` 在 KPM 初始化时拿到：

```c
fn_on_each_cpu = (on_each_cpu_t)kallsyms_lookup_name("on_each_cpu");
/* ... */
gsyms.on_each_cpu = fn_on_each_cpu;
ghost_mm_init(&gsyms);
\```

### 8.4 验证

10 轮快速 rehook 压测（每 0.6s 改 `ArtMethod+0x18`，watcher 每次都检测到并重装）：

```python
cycle  1: drift→0x73a5c1a2c0 → watcher 0x73a5c1a2c0 ✓
cycle  2: drift→0x73a5c1a430 → watcher 0x73a5c1a430 ✓
...
cycle 10: drift→0x73a5c1a078 → watcher 0x73a5c1a078 ✓
after close, live slots: 0

$ adb shell "uptime"
 00:45:33 up 10 min, 0 users, load average: 5.38, 3.30, 1.74
\```

设备 uptime 10+ 分钟无重启，aweme 存活。修复前同样负载必崩。

---

## 九、上层 Python API 设计

### 9.1 `Session` 类骨架

```python
# pte_hookctl/ptehook/session.py

class Session:
    def __init__(self, pid, package=None):
        self.pid = pid
        self.package = package
        self.hooks = []
        self._watcher_thread = None
        self._watcher_stop = threading.Event()

    def java_hook(self, class_desc, method, sig, *,
                   replace=None, on_call=None, action=None,
                   artmethod=None,
                   wait_jit=False, warmup_timeout=30.0,
                   unsafe_bridge=False,
                   force_acc_native=False,
                   legacy_entry_patch=False,
                   jit_watch=False, jit_watch_interval=0.5):
        """
        class_desc: DEX descriptor e.g. "Lcom/foo/Bar;"
        method, sig: 方法名和签名
        replace/on_call/action: 用哪种 Action
        wait_jit: entry_point 在 libart bridge 时，等 ART JIT 编译完成
        unsafe_bridge: 强制允许在 bridge 页装（DBI 修好后可用）
        jit_watch: 后台监测 entry_point 变化自动重装
        """
        if action is None:
            action = actions.ReturnConst(replace) if replace is not None \
                     else actions.LogArgs(on_call=on_call) if on_call \
                     else actions.Noop()

        info = DP.find_method_in_apk(self.apk, class_desc, method, sig)
        target = self._resolve_artmethod(info, artmethod)

        if wait_jit:
            self._wait_for_jit(target, warmup_timeout)
        elif not unsafe_bridge and not legacy_entry_patch:
            ep = K.untag(K.proc_read_u64(self.pid, target + _ep_offset()))
            maps = K.read_maps(self.pid)
            in_libart = any(s <= ep < e and "libart.so" in p
                             for s, e, _, _, p in maps)
            if in_libart:
                raise RuntimeError("entry_point 在 libart 桥; 需 wait_jit=True 或 unsafe_bridge=True")

        meta = self._install_java(target, action)
        if jit_watch:
            meta["watch"] = True
            self._start_jit_watcher(jit_watch_interval)
        ih = InstalledHook("java", action, meta)
        self.hooks.append(ih)
        return ih

    def _install_java(self, target_addr, action):
        """7.2 trap 安装：不改 ArtMethod，只在 entry_point 页拉 UXN"""
        orig_ep = K.untag(K.proc_read_u64(self.pid, target_addr + _ep_offset()))
        ghost = self._alloc_ghost(0x1000)
        log_buf = ghost + 0x800 if action.needs_log else 0

        # uxn_hook 先装，拿到 DBI backup 地址
        backup = K.uxn_hook(self.pid, orig_ep, ghost)
        if getattr(action, "BACKUP_REQUIRED", False):
            action.set_backup(backup)
        action_code = action.build(log_buf)

        # shellcode = X0 过滤器 + action bytes
        full = SC.java_uxn_filter(target_addr, action_code, backup)
        K.ghost_write(self.pid, ghost, 0, full)

        return dict(target=target_addr, ghost=ghost, log_buf=log_buf,
                    orig_ep=orig_ep, backup=backup)
\```

### 9.2 Action：shellcode 行为封装

```python
# pte_hookctl/ptehook/actions.py

class ReturnConst(Action):
    def __init__(self, value):
        self.value = value
    def build(self, log_buf_addr=0):
        return SC.const_return(self.value)

class LogArgs(Action):
    needs_log = True
    MARKER = 0xC0DE1A57
    def __init__(self, on_call=None):
        self.on_call = on_call
        self.last_counter = 0
    def build(self, log_buf_addr=0):
        return SC.log_trampoline_clean(log_buf_addr, self.MARKER)
    def parse_event(self, data):
        regs = [int.from_bytes(data[i*8:(i+1)*8], "little") for i in range(8)]
        marker = int.from_bytes(data[64:72], "little")
        counter = int.from_bytes(data[72:80], "little")
        new_calls = counter - self.last_counter
        self.last_counter = counter
        return dict(regs=regs, counter=counter, new_calls=new_calls,
                    valid=(marker == self.MARKER))
\```

### 9.3 shellcode.py：ARM64 指令生成

```python
# pte_hookctl/shellcode.py
import struct

def _insn(value):
    return struct.pack("&lt;I", value)

def mov_wide(rd, imm, shift=0):
    """MOVZ Xd, #imm, LSL #(shift*16)"""
    return 0xD2800000 | (shift &lt;&lt; 21) | ((imm & 0xFFFF) &lt;&lt; 5) | rd

def mov_k(rd, imm, shift=0):
    """MOVK Xd, #imm, LSL #(shift*16)"""
    return 0xF2800000 | (shift &lt;&lt; 21) | ((imm & 0xFFFF) &lt;&lt; 5) | rd

def load_imm64_fixed(rd, value):
    """固定 4 条指令（包括零块）加载 64-bit 立即数"""
    parts = [(value &gt;> (16*i)) & 0xFFFF for i in range(4)]
    b = _insn(mov_wide(rd, parts[0], 0))
    for i in range(1, 4):
        b += _insn(mov_k(rd, parts[i], i))
    return b

def const_return(value):
    """BTI jc; MOV X0, #value; RET"""
    b = _insn(0xD50324DF)             # BTI jc
    if 0 <= value < 0x10000:
        b += _insn(mov_wide(0, value))
    else:
        b += load_imm64_fixed(0, value)
    b += _insn(0xD65F03C0)            # RET
    return b

def java_uxn_filter(expected_method_ptr, action_shellcode, backup_addr):
    """7.2 trap 的 X0 过滤器 wrapper

    原始 BLR entry_point 时 X0=ArtMethod*。只有 X0 匹配我们 hook 的那个
    ArtMethod 时才执行 action，否则跳到 backup（DBI 重编译的原函数）。"""
    MASK = 0x00FFFFFFFFFFFFFF
    b  = _insn(0xD50324DF)                        # BTI jc
    b += load_imm64_fixed(17, MASK)              # X17 = mask
    b += _insn(0x8A110010)                        # AND X16, X0, X17
    b += load_imm64_fixed(17, expected_method_ptr & MASK)  # X17 = expected (untagged)
    b += _insn(0xEB11021F)                        # CMP X16, X17
    b += _insn(0x54000000 | (6 << 5) | 0x0)       # B.EQ +24 → 跳到 match
    b += load_imm64_fixed(16, backup_addr)       # X16 = backup
    b += _insn(0xD61F0200)                        # BR X16
    b += action_shellcode                         # match:
    return b
\```

### 9.4 kpm_client.py：ctl 命令封装

```python
# pte_hookctl/kpm_client.py

import subprocess, re, os

ADB_SERIAL = os.environ.get("ADB_SERIAL", "")
PTEHOOK_CTL = "/data/local/tmp/ptehook_ctl"
SUPERKEY_PATH = "/data/adb/ptehook/superkey"

def _run(cmd):
    wrapped = f"SK=$(cat {SUPERKEY_PATH}); {cmd}"
    full = ["adb", "-s", ADB_SERIAL, "shell", f"su -c '{wrapped}'"]
    p = subprocess.run(full, capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        raise RuntimeError(f"adb cmd failed: {p.stderr}")
    return p.stdout

def ctl_raw(args):
    return _run(f"{PTEHOOK_CTL} $SK raw {args}")

def uxn_hook(pid, target, replace, force=True):
    """UXN hook。force=True 遇到 already-hooked 自动 unhook 重试。"""
    def _once():
        return ctl_raw(f"uxn-hook {pid} 0x{target:x} 0x{replace:x}")
    out = _once()
    if force and "[FAIL] already hooked" in out:
        ctl_raw(f"uxn-unhook {pid} 0x{target:x}")
        out = _once()
    m = re.search(r"backup=0x([0-9a-fA-F]+)", out)
    if not m:
        raise RuntimeError(f"uxn-hook failed: {out}")
    return int(m.group(1), 16)

def proc_read(pid, addr, length):
    out = ctl_raw(f"proc-read {pid} 0x{addr:x} {length}")
    m = re.search(r"\[OK\]\s*\d+\s*bytes:\s*([0-9a-fA-F]+)", out)
    if not m:
        raise RuntimeError(f"proc-read failed: {out}")
    return bytes.fromhex(m.group(1)[:length * 2])

def ghost_read(pid, vaddr, length):
    """单次上限 1536 字节，自动 chunk。"""
    CHUNK = 1024
    out = bytearray()
    remaining = length
    cur = vaddr
    while remaining > 0:
        n = min(remaining, CHUNK)
        resp = ctl_raw(f"ghost-read {pid} 0x{cur:x} {n}")
        m = re.search(r"\[OK\][^:]+:\s*([0-9a-fA-F]+)", resp)
        if not m:
            raise RuntimeError(f"ghost-read failed: {resp}")
        chunk = bytes.fromhex(m.group(1))
        out += chunk
        cur += len(chunk)
        remaining -= len(chunk)
        if len(chunk) < n: break     # KPM 截断（到 ghost 区域末尾）
    return bytes(out)
\```

---

## 十、Scanner：从 APK 定位 ArtMethod

### 10.1 思路

DEX 文件里方法用 `method_idx` 索引。ART 加载 DEX 后，每个方法对应一个 `ArtMethod` 结构体，在 `[anon:dalvik-LinearAlloc]` VMA 里。设备侧 C 程序用 `process_vm_readv` 扫 LinearAlloc，按 pattern 过滤：

```c
// device_scanner.c (设备侧 binary)

static int cfg_artmethod_size       = 0x20;   // A13/A14
static int cfg_off_declaring_class  = 0x00;
static int cfg_off_access_flags     = 0x04;
static int cfg_off_dex_method_index = 0x08;

static void scan_range(pid_t pid, uint64_t start, uint64_t end, uint32_t target_idx)
{
    const size_t CHUNK = 64 * 1024;
    uint8_t *buf = malloc(CHUNK);
    for (uint64_t off = start; off < end; off += CHUNK) {
        size_t len = MIN(end - off, CHUNK);
        ssize_t got = vm_read(pid, off, buf, len);
        if (got <= 0) continue;

        for (ssize_t i = 0; i + cfg_artmethod_size <= got; i += 4) {
            uint32_t decl   = *(uint32_t *)(buf + i + cfg_off_declaring_class);
            uint32_t midx   = *(uint32_t *)(buf + i + cfg_off_dex_method_index);
            uint32_t access = *(uint32_t *)(buf + i + cfg_off_access_flags);
            if (midx != target_idx) continue;
            if (decl == 0 || access == 0 || access == 0xFFFFFFFF) continue;
            if (decl < 0x10000 || decl > 0x40000000) continue;   /* 过滤非 app class */

            uint64_t cand = off + i;
            /* adjacent check: ±ARTMETHOD_SIZE 邻居应该是同类其他方法 */
            if (n_adjacent > 0 && !has_adjacent(pid, cand)) continue;

            printf("  0x%lx  access=0x%x  decl=0x%x\n", cand, access, decl);
        }
    }
    free(buf);
}
\```

aweme 的 LinearAlloc ~100MB，扫描 0.17s。

### 10.2 Python 侧消歧

scanner 多候选时需要消歧。比如 `method_idx=33853` 在 aweme 里返回 5 个候选 —— 因为有多个 class 碰巧都有第 33853 个方法。消歧两层过滤：

```python
def _resolve_artmethod_once(self, info):
    idx = info["method_idx"]
    dex_af = info.get("access_flags")
    adj_csv = ",".join(str(x) for x in info["adjacent_idxs"])

    out = _adb_root(f"/data/local/tmp/pte_scan {self.pid} {idx} {adj_csv}")
    cands = [int(line.split()[0], 16) for line in out.splitlines()
             if line.strip().startswith("0x")]

    # Filter 1: access_flags 低 16 bit 匹配 DEX
    if dex_af is not None and len(cands) > 1:
        filt = []
        for c in cands:
            art_af = K.proc_read_u32(self.pid, c + _af_offset())
            if (art_af & 0xFFFF) == (dex_af & 0xFFFF):
                filt.append(c)
        if filt: cands = filt

    if len(cands) == 1: return cands[0]

    # Filter 2: cluster size (同类方法在 LinearAlloc 连续排列)
    expected = len(info["adjacent_idxs"]) + 1
    cluster_matches = []
    for c in cands:
        cand_decl = K.proc_read_u32(self.pid, c)
        n_same = 1
        for k in range(1, 20):
            try:
                if K.proc_read_u32(self.pid, c + k * 0x20) == cand_decl:
                    n_same += 1
                else: break
            except: break
        for k in range(1, 20):
            try:
                if K.proc_read_u32(self.pid, c - k * 0x20) == cand_decl:
                    n_same += 1
                else: break
            except: break
        if n_same == expected or n_same == expected - 2:
            cluster_matches.append((c, n_same))

    if len(cluster_matches) == 1:
        return cluster_matches[0][0]
    raise RuntimeError(f"无法消歧: {len(cands)} 候选；传 artmethod='0x...' 指定")
\```

---

## 十一、跨 Android / kernel 版本兼容

### 11.1 ArtMethod 布局

```python
# art_offsets.py

# Android 13 / 14 (API 33/34) — 相同布局
_A13 = dict(
    ARTMETHOD_SIZE             = 0x20,
    ARTMETHOD_DECLARING_CLASS  = 0x00,
    ARTMETHOD_ACCESS_FLAGS     = 0x04,
    ARTMETHOD_DEX_METHOD_INDEX = 0x08,
    ARTMETHOD_METHOD_INDEX     = 0x0C,
    ARTMETHOD_DATA             = 0x10,
    ARTMETHOD_ENTRY_QUICK      = 0x18,
)

# Android 11 / 12 — 多了 dex_code_item_offset 字段
_A12 = dict(
    ARTMETHOD_SIZE             = 0x28,
    ARTMETHOD_DECLARING_CLASS  = 0x00,
    ARTMETHOD_ACCESS_FLAGS     = 0x04,
    ARTMETHOD_DEX_CODE_ITEM_OFFSET = 0x08,
    ARTMETHOD_DEX_METHOD_INDEX = 0x0C,
    ARTMETHOD_METHOD_INDEX     = 0x10,
    ARTMETHOD_DATA             = 0x18,
    ARTMETHOD_ENTRY_QUICK      = 0x20,
)

_OFFSETS_BY_API = { 30: _A12, 31: _A12, 32: _A12,
                     33: _A13, 34: _A13, 35: _A13 }

def detect_api_level(serial=None):
    cmd = ["adb"] + (["-s", serial] if serial else []) + \
          ["shell", "getprop", "ro.build.version.sdk"]
    return int(subprocess.check_output(cmd, text=True).strip())

def get_offsets(api=None):
    if api is None: api = detect_api_level()
    if api in _OFFSETS_BY_API:
        return _OFFSETS_BY_API[api]
    below = [k for k in _OFFSETS_BY_API if k <= api]
    closest = max(below) if below else min(_OFFSETS_BY_API)
    return _OFFSETS_BY_API[closest]
\```

Python 侧用 `_ep_offset()` / `_af_offset()` 取代所有硬编码：

```python
def _ep_offset():
    return AO.get_offsets().get("ARTMETHOD_ENTRY_QUICK", 0x18)

def _af_offset():
    return AO.get_offsets().get("ARTMETHOD_ACCESS_FLAGS", 0x04)
\```

`device_scanner.c` 也加了 CLI flag：

```python
./pte_scan &lt;pid&gt; <method_idx> [adj] [--size=N] [--off-decl=N] [--off-af=N] [--off-midx=N]
\```

Python 侧根据 `get_offsets()` 构造这些 flag：

```python
def _scanner_flags():
    o = AO.get_offsets()
    parts = []
    if o["ARTMETHOD_SIZE"] != 0x20:           parts.append(f"--size={o['ARTMETHOD_SIZE']}")
    if o["ARTMETHOD_ACCESS_FLAGS"] != 0x04:   parts.append(f"--off-af={o['ARTMETHOD_ACCESS_FLAGS']}")
    if o["ARTMETHOD_DEX_METHOD_INDEX"] != 0x08: parts.append(f"--off-midx={o['ARTMETHOD_DEX_METHOD_INDEX']}")
    return " ".join(parts)
\```

### 11.2 Kernel 版本探测

```c
// ptehook_planc_v2.c

static struct {
    int off_vma_start, off_vma_end;
    int off_vma_next,  off_vma_prev, off_vma_rb;
    int off_mm_mmap,   off_mm_mm_rb;
    int has_linked_list_vma;
} g_kl = {
    /* 5.4 ARM64 默认 */
    .off_vma_start = 0x00,
    .off_vma_end   = 0x08,
    .off_vma_next  = 0x10,
    .off_vma_prev  = 0x18,
    .off_vma_rb    = 0x20,
    .off_mm_mmap   = 0x00,
    .off_mm_mm_rb  = 0x08,
    .has_linked_list_vma = 1,
};

static void probe_kern_layout(void)
{
    /* mt_erase 只在 kernel 6.1+ (maple tree) 存在 */
    if (kallsyms_lookup_name("mt_erase") != 0) {
        g_kl.has_linked_list_vma = 0;
        pr_info("ptehook: kernel >= 6.1 (maple tree) 检测到\n");
    } else {
        g_kl.has_linked_list_vma = 1;
        pr_info("ptehook: kernel < 6.1 (linked-list VMAs)\n");
    }
}
\```

`hide-vma` 之类依赖 linked-list VMA 的命令在 maple tree 内核下直接拒绝：

```c
if (!g_kl.has_linked_list_vma)
    return fail("kernel >= 6.1 (maple tree); hide-vma 未实现");
\```

---

## 十二、完整构建 / 部署 / 加载

### 12.1 构建 KPM

```bash
cd ptehook/test_kmod
make -f Makefile.planc
# 产出: ptehook_planc_v2.kpm  (~90KB)
\```

`Makefile.planc` 关键行：

```makefile
NDK_CLANG = $(NDK_PATH)/bin/aarch64-linux-android29-clang
CFLAGS = -target aarch64-linux-android -O2 -Wall \
          -fno-stack-protector -fno-common -fno-builtin -fno-pic \
          -nostdlib -nostdinc -ffreestanding -mgeneral-regs-only -mcmodel=large \
          -I. -I$(KP_KERNEL)/include -I$(KP_KERNEL)/patch/include \
          -I$(KP_KERNEL)/linux/include -I$(KP_KERNEL)/linux/arch/arm64/include

OBJS = ptehook_planc_v2.o dbi_kern.o ghost_mm.o

all: ptehook_planc_v2.kpm

%.o: %.c
    $(NDK_CLANG) $(CFLAGS) -c $< -o $@

ptehook_planc_v2.kpm: $(OBJS)
    $(NDK_PATH)/bin/aarch64-linux-android-ld -r -o $@ $^
\```

### 12.2 构建设备侧 binary

```bash
# Scanner
$NDK/aarch64-linux-android29-clang -O2 -static \
    -o pte_scan device_scanner.c

# ctl client (from KernelPatch examples)
$NDK/aarch64-linux-android29-clang -O2 -static \
    -o ptehook_ctl ptehook_ctl.c
\```

### 12.3 推送 + 加载

```bash
# 准备 superkey（一次性，APatch 设置时给出）
adb shell "su -c 'mkdir -p /data/adb/ptehook && \
    echo YOUR_APATCH_SUPERKEY > /data/adb/ptehook/superkey && \
    chmod 600 /data/adb/ptehook/superkey'"

# 推送 + 加载
adb push ptehook_planc_v2.kpm pte_scan ptehook_ctl /data/local/tmp/
adb shell "su -c 'chmod 755 /data/local/tmp/pte_scan /data/local/tmp/ptehook_ctl'"

SK=$(adb shell "su -c 'cat /data/adb/ptehook/superkey'")
adb shell "su -c '/data/adb/kpatch $SK kpm load /data/local/tmp/ptehook_planc_v2.kpm'"

# 验证
adb shell "su -c '/data/adb/kpatch $SK kpm list'"
# → ptehook-planc-v2

adb shell "su -c '/data/local/tmp/ptehook_ctl $SK raw stat'"
# === STATUS ===
# hook_installed: 0
# armed         : 0
# ghost.installed: 0
# kern.linked_list_vma: 1
# kern.vma_off: start=0x0 end=0x8 next=0x10 rb=0x20
\```

### 12.4 重装（改代码后）

```bash
adb shell "su -c '/data/adb/kpatch $SK kpm unload ptehook-planc-v2 && \
    /data/adb/kpatch $SK kpm load /data/local/tmp/ptehook_planc_v2.kpm'"
\```

KPM unload 时会触发 `cleanup_all_state`，自动清所有目标进程的 ghost PTE + 物理页：

```c
static void cleanup_all_state(void)
{
    char buf[512];
    int i;
    for (i = 0; i < UXN_HOOK_MAX; i++) {
        struct uxn_hook_slot *s = &uxn_hooks[i];
        if (s->used) cmd_uxn_unhook(s->pid, s->target_addr, buf, sizeof(buf));
    }
    for (i = 0; i < JAVA_HOOK_MAX; i++) {
        struct java_hook_entry *j = &g_h.java_hooks[i];
        if (j->used) cmd_java_unhook(j->pid, j->art_method, j->entry_offset,
                                      buf, sizeof(buf));
    }
    for (i = 0; i < GHOST_POOL_MAX; i++) {
        struct ghost_pool_entry *g = &g_h.ghost_pool[i];
        if (g->used) cmd_ghost_free(g->pid, g->gp.vaddr, buf, sizeof(buf));
    }
}

static long planc2_exit(void *__user r)
{
    cleanup_all_state();      // 必须在 do_mem_abort hook 移除前做
    /* ... 其他清理 ... */
    return 0;
}
\```

---

## 十三、实战：aweme MSManager.frameSign hook

### 13.1 完整脚本

```python
# hook_aweme_frameSign.py
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ptehook, kpm_client as K

sess = ptehook.attach("com.ss.android.ugc.aweme")

def on_enter(regs):
    # frameSign 虚方法: X0=ArtMethod, X1=this, X2=String 引用, X3=int
    print(f"  frameSign: this=0x{regs[1]:x} int={regs[3] & 0xFFFFFFFF}")

installed = sess.java_hook_all(
    "Lcom/bytedance/mobsec/metasec/ml/MSManager;",
    "frameSign",
    "(Ljava/lang/String;I)Ljava/util/Map;",
    on_call=on_enter,
    unsafe_bridge=True,     # DBI 修好可安全开
    jit_watch=True,          # UAF 修好可安全开，应对 ART tier 升级
)
print(f"装了 {len(installed)} 个 hook")

try:
    sess.run(poll_hz=10)
except KeyboardInterrupt:
    pass
finally:
    sess.close()
\```

### 13.2 运行过程跟踪

启动后输出：

```python
scanned 259 LinearAlloc VMAs, 62592 KB
[+] attached to pid 13117 (com.ss.android.ugc.aweme)
[+] DEX: classes43.dex method_idx=33853
[+] java_hook_all: 2 candidates
[+] entry_point (untagged) = 0x73e761a430
[!] entry_point 位于 libart.so (r-xp) —— 方法未编译，指向 art_quick_*_bridge 或 trampoline
[+] uxn-hook @ 0x73e761a430 → ghost 0x748f063000 backup 0x73e9eb7530
  [0] 0x77a5a0f0a8 OK
[+] JIT drift watcher started (interval=0.5s)
[+] 1/1 hooks installed
装了 1 个 hook
\```

### 13.3 监测 Pass 3 命中率

另一个终端：

```bash
SK=$(adb shell "su -c 'cat /data/adb/ptehook/superkey'")
watch -n 1 "adb shell \"su -c '/data/local/tmp/ptehook_ctl $SK raw uxn-list'\""
\```

```python
=== UXN-LIST ===
slot=0 pid=13117 target=0x73e761a430 page=0x73e761a000 replace=0x9fd6d000
       ghost=0x748f063000 hits=267735 pass3=267732
       last_far=0x73e761a050 last_new_pc=0x748f06305c
[OK] 1/16 slots used
\```

`last_far=0x73e761a050` 指向 `art_quick_imt_conflict_trampoline` 入口 —— 说明 aweme 的 IMT 分发密集命中这一页，DBI fallthrough 正常。

### 13.4 确定方法实际被调用情况

aweme 的坑：**`MSManager.frameSign` 只是 wrapper**，实际签名由 `ms.bd.c.f2.frameSign` 执行。`java_hook_all` 装在 MSManager 上大概率 on_call 不触发。

解法 1：`ms.bd.c.g2$a` 接口有多个实现类，DEX parse 时找出所有实现类，都 hook：

```python
# 扫 DEX 找出接口的所有实现类
impls = DP.find_interface_implementations(
    "/tmp/aweme.apk",
    "Lms/bd/c/g2$a;"   # interface FQN
)
for cls in impls:
    sess.java_hook_all(cls, "frameSign", "(Ljava/lang/String;I)Ljava/util/Map;",
                        on_call=on_enter, unsafe_bridge=True)
\```

解法 2：native hook `libmetasec_ml.so` 的 JNI_OnLoad 里 `RegisterNatives` 表：

```python
sess.native_hook("libmetasec_ml.so",
                  symbol="_ZN..._dynamic_frame_sign...",  # 动态分析找到的 C 函数
                  action=ptehook.CallBackup(on_call=..., on_return=...))
\```

---

## 十四、调试 & 诊断工具

### 14.1 `uxn-list`：slot 状态

```bash
$ /data/local/tmp/ptehook_ctl $SK raw uxn-list
=== UXN-LIST ===
slot=0 pid=13117 target=0x73e761a430 ... hits=267735 pass3=267732
       last_far=0x73e761a050 last_new_pc=0x748f06305c
[OK] 1/16 slots used
\```

Python 封装返回结构化数据：

```python
for r in K.uxn_list():
    print(f"slot={r['slot']} pid={r['pid']} target=0x{r['target']:x} "
          f"hits={r['hits']} pass3={r['pass3']} last_far=0x{r['last_far']:x}")
\```

### 14.2 `ghost-read`：读 DBI ghost 字节（debug）

```bash
# 读 1024 字节，内部最大 1536 字节/次
$ /data/local/tmp/ptehook_ctl $SK raw ghost-read 13117 0x748f063000 1024
[OK] 1024 bytes (uxn slot=0 +0x0): ffc302d1e827016dea2f026d...
\```

Python 自动 chunk：

```python
ghost_bytes = K.ghost_read(pid, ghost_vaddr, 8192)     # 任意长度
# 分析 DBI 生成的 ARM64 指令
import struct
for i in range(0, len(ghost_bytes), 4):
    w = struct.unpack_from('&lt;I', ghost_bytes, i)[0]
    print(f"  g[{i//4:3d}] 0x{i:03x}: 0x{w:08x}")
\```

### 14.3 `stat`：全局状态

```python
=== STATUS ===
hook_installed: 1
armed         : 0
ghost.installed: 0
kern.linked_list_vma: 1
kern.vma_off: start=0x0 end=0x8 next=0x10 rb=0x20
\```

### 14.4 Python 单元测试

```bash
cd pte_hookctl
python3 tests/test_shellcode.py
# ----------------------------------------------------------------------
# Ran 29 tests in 0.006s
# OK
\```

29 个测试覆盖：

- shellcode 生成器 (mov_wide, const_return, java_uxn_filter 等)
- DBI ARM64 指令编码 (LDR literal, LDRSW, SIMD LDR)
- ArtMethod 偏移表（多 API 版本）
- ghost_read chunking 逻辑（用 mock）

---

## 十五、和其他框架的对比

| 维度 | Frida | LSPlant | wxshadow+rustFrida | **ptehook** |
|-|-|-|-|-|
| 注入 `.so` 到目标 | ✅ libfrida-agent | ✅ Zygisk | ✅ libagent | **❌** |
| ptrace 目标 | ✅ | ❌ | ✅ spawn | **❌** |
| 改 `.text` 字节 | ✅ inline | ✅ inline | ✅ (藏 shadow 页) | **❌** |
| 改 ArtMethod 字节 | — | ✅ entry_point | — | **❌ (默认)** |
| `/proc/maps` 可见 | ✅ | ✅ | ✅ | **❌** |
| JS 脚本热更 | ✅ QuickJS | ❌ | ✅ QuickJS | ❌ |
| Java onEnter+onLeave | ✅ | ✅ | ✅ | ⚠️ Native 支持 |
| 改 Java 入参 | ✅ | ✅ | ✅ | ❌ |
| Nterp-tier 方法 | ✅ | ✅ | ✅ | ⚠️ 需 wait_jit |
| Spawn 注入 | ✅ | ✅ | ✅ | ❌ 只能 attach |
| pagemap PFN 一致 | ❌ | ❌ | ❌ | **✅** |

---

## 十六、已知限制

### 16.1 Nterp-only 方法

ART 13 Nterp 对"未 JIT 的纯 Java 方法"有极深的 fast path，Java-to-Java 调用**不读 entry_point**。尝试过：

- 清 `ACC_COMPILE_DONT_BOTHER (0x10000000)` → ART 不理
- 拉满 `hotness_count_` = 0xFFFF → ART 不理
- 打 `ACC_NATIVE (0x100)` → Nterp 仍走 fast path

只能 `wait_jit=True` 等 ART 自然 JIT（通常 10 次调用左右）。对 trivial 方法（比如 `return 0`）ART 拒绝 JIT，这种方法目前抓不到。

### 16.2 Kernel 6.1+ maple tree

`hide-vma` / `hide-range` 依赖 linked-list VMA，kernel 6.1+ 改成 maple tree 后这两个命令会拒绝执行。**核心 hook 路径（UXN / DBI / ghost）不受影响**，因为 `vm_area_struct` 的 `vm_start/vm_end` 偏移一直稳定。

### 16.3 Java `CallBackupJava` (onEnter+onLeave)

7.2 trap 模式下不支持。需要 LSPlant 风格的 ArtMethod 克隆（在 ART heap 里 alloc 新 ArtMethod、注册到 class_table、WriteBarrier），跨进程实现 ≈ 9 天工作量，ROI 不够。

---

## 十七、路线图

按优先级：

1. **Shadow page hook**（解 Nterp 问题，但需配套 pagemap/smaps hook 补 stealth）
2. **Host-side JS 脚本引擎**（热更 hook 逻辑，不碰目标进程，零 stealth 代价）
3. **Spawn-time 注入**（zygote fork 内核 hook，覆盖 app 启动阶段）
4. **Field hook / Throw / NewObject** JNI ops（shellcode 里调 `JNIEnv` vtable）
5. **maple tree kernel 下的 hide-vma 实现**

不做的：

- QBDI 级指令 trace（时序暴露严重）
- QuickJS 注入到目标进程（扩大检测面）

---

## 十八、收尾

这个项目走下来最大的感受是 —— **"方案 C"骨架简单，工程细节全在坑里**。

几个坑的代价：

| 坑 | 发现代价 | 修法 |
|-|-|-|
| DBI X17 clobber | 3 次尝试 + dump ghost 字节 | intra-page ghost VA + pending backpatch |
| Ghost UAF | 1 次 kernel reboot + 思考 | `on_each_cpu` + `ic ialluis` 广播 |
| KPM 卸载不清 PTE | 多轮孤儿 PTE 占 gap | `cleanup_all_state` 兜底 |
| Scanner 早期 cluster 误匹配 | 多次上机尝试 | retry + access_flags 双层过滤 |
| ART Nterp 短路 | ART 源码翻查 | 确认无解，走 wait_jit |

**每一个坑都是 ART / Linux kernel / ARM64 语义交互的细节**。特别想强调 DBI 的 X17 clobber —— 写 DBI 是有 textbook 的（怎么重编译 PC-relative），但**没人告诉你 ART trampoline 的寄存器约定不遵守 AAPCS**。X17 在 AAPCS 里可以随便 clobber，但在 ART 的 imt_conflict_trampoline 里它是神圣的 IMT key 载体。这种隐含约定只能靠实战踩出来。

**ptehook 不是 Frida 替代品**，它解决的是 Frida 解决不了的一个特定问题 —— **stealth**。如果要做的反作弊对抗需要零 `.so` 注入 / 零字节修改 / 零 ptrace 痕迹，这个框架的机制就是为你设计的。如果需要 JS 热更 / 完整 Java onEnter+onLeave / spawn 注入，**老老实实用 Frida**。

感谢 7.2 节那篇启蒙文章。没有"查名片、布陷阱"这个框架性思路，我不会往这个方向做。

---

## 附录 A：完整 KPM 命令列表

```python
install &lt;pid&gt; &lt;addr&gt;                  # legacy 单 hook 安装
remove                                # 卸载 legacy hook
stat                                  # 全局状态 + kernel layout

ghost-alloc &lt;pid&gt; &lt;near&gt; &lt;size&gt;       # 近 libart 分配 ghost
ghost-alloc-at &lt;pid&gt; &lt;exact&gt; &lt;size&gt;   # 指定 VA 分配
ghost-free &lt;pid&gt; &lt;vaddr&gt;
ghost-write &lt;pid&gt; &lt;vaddr&gt; &lt;off&gt; &lt;hex&gt;
ghost-read &lt;pid&gt; &lt;vaddr&gt; &lt;len&gt;        # ≤1536/次

java-hook &lt;pid&gt; <art_method> <ep_off> <new_ep>   # 改 ArtMethod.entry_point (legacy)
java-unhook &lt;pid&gt; <art_method> <ep_off>

proc-patch &lt;pid&gt; &lt;addr&gt; &lt;hex&gt;         # 跨进程写
proc-read &lt;pid&gt; &lt;addr&gt; &lt;len&gt;

uxn-hook &lt;pid&gt; &lt;target&gt; &lt;replace&gt;     # 7.2 trap 安装
uxn-unhook &lt;pid&gt; &lt;target&gt;
uxn-list                              # 所有 UXN slot
uxn-add-redirect &lt;pid&gt; &lt;target&gt; &lt;replace&gt;
uxn-del-redirect &lt;pid&gt; &lt;target&gt;

hide-vma &lt;pid&gt; &lt;vaddr&gt;                # kernel <6.1 only
hide-range &lt;pid&gt; &lt;start&gt; &lt;end&gt;
watch &lt;pid&gt; <so_name> &lt;offset&gt;        # so 加载后自动 hook
\```

## 附录 B：关键源码文件速查

| 想了解 | 读这个 |
|-|-|
| UXN 陷阱怎么工作 | `test_kmod/ptehook_planc_v2.c::before_do_mem_abort` |
| Ghost 如何分配 | `test_kmod/ghost_mm.c::ghost_alloc / find_hole_near` |
| DBI 重编译每类指令 | `test_kmod/dbi_kern.c::recomp_*` |
| DBI intra-page 回填 | `test_kmod/dbi_kern.c::dbi_recompile_page` (末尾循环) |
| Ghost UAF 修复 | `test_kmod/ghost_mm.c::ghost_free_drain_ipi` |
| shellcode 生成 | `pte_hookctl/shellcode.py::java_uxn_filter` |
| Java hook 安装流程 | `pte_hookctl/ptehook/session.py::_install_java` |
| ArtMethod 扫描消歧 | `pte_hookctl/ptehook/session.py::_resolve_artmethod` |
| JIT 漂移监测 | `pte_hookctl/ptehook/session.py::_jit_watch_loop` |
| KPM 卸载清理 | `test_kmod/ptehook_planc_v2.c::cleanup_all_state` |
| 跨 Android 版本偏移 | `pte_hookctl/art_offsets.py::_OFFSETS_BY_API` |
| 跨 kernel 版本探测 | `test_kmod/ptehook_planc_v2.c::probe_kern_layout` |

## 附录 C：本文涉及的 ARM64 指令编码快速参考

| 指令 | mask | opcode pattern |
|-|-|-|
| NOP | 0xFFFFFFFF | 0xD503201F |
| B imm26 | 0xFC000000 | 0x14000000 |
| BL imm26 | 0xFC000000 | 0x94000000 |
| B.cond imm19 | 0xFF000010 | 0x54000000 |
| CBZ/CBNZ imm19 | 0x7E000000 | 0x34000000 |
| TBZ/TBNZ imm14 | 0x7E000000 | 0x36000000 |
| ADRP imm21 | 0x9F000000 | 0x90000000 |
| ADR imm21 | 0x9F000000 | 0x10000000 |
| LDR (lit) Wt | 0xFF000000 | 0x18000000 |
| LDR (lit) Xt | 0xFF000000 | 0x58000000 |
| LDRSW (lit) | 0xFF000000 | 0x98000000 |
| PRFM (lit) | 0xFF000000 | 0xD8000000 |
| LDR (lit) S/D/Q | 0x3F000000 | 0x1C000000 |
| BR Xn | 0xFFFFFC1F | 0xD61F0000 \| (Rn<<5) |
| BLR Xn | 0xFFFFFC1F | 0xD63F0000 \| (Rn<<5) |
| RET | 0xFFFFFFFF | 0xD65F03C0 |
| BTI jc | 0xFFFFFFFF | 0xD50324DF |
| MOVZ Xd, imm16, LSL (hw*16) |  | 0xD2800000 \| (hw<<21) \| (imm<<5) \| Rd |
| MOVK Xd, imm16, LSL (hw*16) |  | 0xF2800000 \| (hw<<21) \| (imm<<5) \| Rd |

---

*代码仓库：<https://github.com/xiaokanghub/ptehooker>（GPL-2.0）。欢迎回帖交流，也欢迎 issue / PR 修 bug。*

---

# 回复

## 回复 by wx_插曲 (#2)

*2026-4-19 10:41*

66

## 回复 by Zepp7289 (#3)

*2026-4-19 11:59*

tql

## 回复 by Imxz (#4)

*2026-4-19 12:06*

tql

## 回复 by mJqalJqN (#5)

*2026-4-19 12:32*

1

## 回复 by mb_ldbucrik (#6)

*2026-4-19 13:25*

向大佬学习

## 回复 by mb_paopxhtx (#7)

*2026-4-19 14:18*

向大佬学习

## 回复 by xianhuimin (#8)

*2026-4-19 14:29*

学习学习

## 回复 by mb_zatexoyx (#9)

*2026-4-19 15:40*

666

## 回复 by kingking888 (#10)

*2026-4-19 15:40*

666

## 回复 by 夜惜风雨 (#11)

*2026-4-19 17:03*

6666666666

## 回复 by mb_xqptnehm (#12)

*2026-4-19 17:04*

666666666666

## 回复 by 方子敬xiao (#13)

*2026-4-19 17:53*

6666666666

## 回复 by ulong9527 (#14)

*2026-4-19 18:08*

6

## 回复 by 熊猫吃鱼 (#15)

*2026-4-19 18:09*

666666

## 回复 by lvchalove (#16)

*2026-4-19 19:06*

66666

## 回复 by xingbing (#17)

*2026-4-19 19:52*

向大佬学习

## 回复 by 一栋奥特曼 (#18)

*2026-4-19 19:55*

666

## 回复 by 零_721409 (#19)

*2026-4-19 20:33*

6666

## 回复 by 菱志漪 (#20)

*2026-4-19 21:35*

666666

## 回复 by 特洛伊Troye (#21)

*2026-4-19 22:01*

太强了

## 回复 by mb_iesvmzqc (#22)

*2026-4-19 22:37*

tql

## 回复 by dob_C (#23)

*2026-4-20 09:32*

感谢分享

## 回复 by GEKEZYX (#24)

*2026-4-20 09:42*

666

## 回复 by iBa0 (#25)

*2026-4-20 09:45*

666

## 回复 by git_14248bibinocode (#26)

*2026-4-20 10:59*

tql

## 回复 by XCicada (#27)

*2026-4-20 11:07*

一句话总结，总的来说，这一版确实够硬。

## 回复 by mb_zknjgprg (#28)

*2026-4-20 11:38*

666

## 回复 by 龙飞雪 (#29)

*2026-4-20 11:47*

学习了。

## 回复 by bullyxy (#30)

*2026-4-20 12:59*

666

## 回复 by 孤梦拾遗 (#31)

*2026-4-20 14:09*

666

## 回复 by Gryffindoss (#32)

*2026-4-20 14:48*

66666

## 回复 by dreameriii (#33)

*2026-4-20 16:26*

66666

## 回复 by 黑屏 (#34)

*2026-4-20 16:33*

66

## 回复 by Viseris (#35)

*2026-4-20 17:09*

6666

## 回复 by 啊你好哇123 (#36)

*2026-4-20 17:59*

学习学习

## 回复 by amwpecel (#37)

*2026-4-20 18:11*

555

## 回复 by wx_D_755717 (#38)

*2026-4-20 20:24*

666

## 回复 by huangjw (#39)

*2026-4-21 09:22*

火钳刘明

## 回复 by Xx_gg (#40)

*2026-4-21 09:23*

66666

## 回复 by pan_634488 (#41)

*2026-4-21 09:28*

666

## 回复 by wx_Kerberos (#42)

*2026-4-21 09:35*

![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by buluo533 (#43)

*2026-4-21 09:37*

6666

## 回复 by Ankeys (#44)

*2026-4-21 10:48*

牛13![image](https://bbs.kanxue.com/view/img/face/069.gif)

## 回复 by 小尘0000 (#45)

*2026-4-21 17:47*

666

## 回复 by FMNS (#46)

*2026-4-21 18:26*

6666

## 回复 by 温泉划水鱼 (#47)

*2026-4-21 23:23*

仙人指路

## 回复 by Elenia (#48)

*2026-4-23 09:54*

感谢分享

## 回复 by k4y0z (#49)

*2026-4-23 09:58*

666

## 回复 by guijingwen (#50)

*2026-4-23 10:13*

66

## 回复 by Crack999 (#51)

*2026-4-23 11:16*

666666

## 回复 by 西瓜帅 (#52)

*2026-4-23 13:46*

我来看看

## 回复 by 4Chan (#53)

*2026-4-23 14:30*

666

## 回复 by 珍惜Any (#54)

*2026-4-23 14:51*

高频调用+多个地址都在一个内存页，我自己测我自己的发现非常不稳

## 回复 by virjar (#55)

*2026-4-23 16:49*

学习学习

## 回复 by TeamAR (#56)

*2026-4-23 16:59*

666

## 回复 by wx_范迪塞尔 (#57)

*2026-4-23 17:00*

6666

## 回复 by zz胡 (#58)

*2026-4-23 20:19*

66666666666

## 回复 by mb_dcjxxhsk (#59)

*2026-4-23 23:19*

666

## 回复 by jyotidwi (#60)

*2026-4-24 00:00*

tql

## 回复 by 温泉划水鱼 (#61)

*2026-4-24 20:16*

太强了，大佬求个v交流

## 回复 by mb_ileraodd (#62)

*2026-4-25 16:51*

6666

## 回复 by PPTV (#63)

*2026-4-27 08:08*

666

## 回复 by uni7corn (#64)

*2026-4-27 10:58*

感谢分享，学习了

## 回复 by mb_benfvkcd (#65)

*2026-4-27 11:35*

666

## 回复 by Freax (#66)

*2026-4-27 13:50*

学习

## 回复 by Ahzn (#67)

*2026-4-27 14:16*

呵呵 6倒6匹带个码

## 回复 by mb_nkjfyhkg (#68)

*2026-4-28 01:52*

mark

## 回复 by mb_svmkwhkk (#69)

*2026-4-29 14:34*

6666

## 回复 by mb_svmkwhkk (#70)

*2026-4-29 14:34*

6666牛逼

## 回复 by mb_svmkwhkk (#71)

*2026-4-29 14:34*

6666牛逼![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by ClPrada (#72)

*2026-5-1 18:11*

66666666

## 回复 by mb_jwevvolh (#73)

*2026-5-2 12:28*

666

## 回复 by wx_小白_266 (#74)

*2026-5-3 16:07*

666

## 回复 by mb_lvesdvhu (#75)

*2026-5-3 16:35*

6666

## 回复 by ILA1992 (#76)

*2026-5-6 15:01*

很好111

## 回复 by mb_tblxoyne (#77)

*2026-5-6 19:51*

666

## 回复 by 末日大哥 (#78)

*2026-5-6 20:05*

666

## 回复 by dreameriii (#79)

*2026-5-7 09:42*

大佬，github 项目缺少了一个 ptehook_ctl.c 的代码，能麻烦补充下吗？![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by alds (#80)

*2026-5-9 16:26*

666

## 回复 by ILA1992 (#81)

*2026-5-14 01:40*

ACE 检测到 PC 在 ghost 页执行，CRC 不匹配，这个应该解决不了吧？还不算是根本无痕，现有的手段已经能检测。

## 回复 by REerr (#82)

*2026-5-17 06:21*

>
> [dreameriii](https://bbs.kanxue.com/user-719252.htm)
>  大佬，github 项目缺少了一个 ptehook_ctl.c 的代码，能麻烦补充下吗？[em_014]
>

https://github.com/xiaokanghub/ptehooker/blob/main/pte_hookctl/pte_hookctl.py 用这个

## 回复 by REerr (#83)

*2026-5-17 06:22*

>
> [ILA1992](https://bbs.kanxue.com/user-967083.htm)
>  ACE 检测到 PC 在 ghost 页执行，CRC 不匹配，这个应该解决不了吧？还不算是根本无痕，现有的手段已经能检测。
>

ACE那就是另外的故事

## 回复 by uboluo (#84)

*2026-5-19 10:31*

666

## 回复 by dreameriii (#85)

*2026-5-20 09:57*

>
> [REerr](https://bbs.kanxue.com/user-951706.htm)
>  https://github.com/xiaokanghub/ptehooker/blob/main/pte_hookctl/pte_hookctl.py 用这个
>

貌似不太行吧， pte_hookctl.py 依赖 kpm_client.py 执行， kpm_client.py 调用 ctl_raw 函数，就是在执行 /data/local/tmp/ptehook_ctl 程序……还是说我哪里理解错了。。？![image](https://bbs.kanxue.com/view/img/face/048.gif)

## 回复 by lucifer11 (#86)

*2026-5-25 11:48*

66666666666

## 回复 by wx_Oh.漏 (#87)

*2026-5-25 11:50*

11111

## 回复 by mb_vdqbqpou (#88)

*2026-5-27 10:09*

牛逼

## 回复 by mb_homnvxow (#89)

*2026-5-27 11:43*

666

## 回复 by mb_tthxtwsc (#90)

*2026-6-1 14:40*

感谢分享，虽然还是不会![image](https://bbs.kanxue.com/view/img/face/020.gif)

## 回复 by Bonquer (#91)

*2026-6-1 14:42*

666

## 回复 by mb_enbuhisq (#92)

*2026-6-2 10:37*

666666666

## 回复 by wx_qsrl (#93)

*2026-6-2 20:11*

1111

## 回复 by wx_故事与酒 (#94)

*2026-6-2 21:43*

66666666666666666666666

## 回复 by mb_pmefooyx (#95)

*2026-6-2 22:41*

666666

## 回复 by mb_cfjwplfo (#96)

*2026-6-5 23:46*

libart是不是有问题，我用这个框架hook Art函数一直崩溃报错，其他so就没问题

## 回复 by Mr.ChenX (#97)

*2026-6-6 10:58*

666

## 回复 by uboluo (#98)

*2026-6-12 16:41*

666

## 回复 by mb_axzjntyl (#99)

*2026-6-12 16:57*

666

## 回复 by feng504x (#100)

*2026-6-13 20:47*

>
> [dreameriii](https://bbs.kanxue.com/user-719252.htm)
>  貌似不太行吧， pte_hookctl.py 依赖 kpm_client.py 执行， kpm_client.py 调用 ctl_raw 函数，就是在执行 /data/local/tmp/ptehoo ...
>

确实少了这个跑不动，我只能让ai + apatch 代码自己写了一个， 就是kpm调用的ctl0

## 回复 by mb_eumnbkwy (#101)

*2026-6-15 07:34*

看看

## 回复 by YoungBai (#102)

*2026-6-15 09:38*

666

## 回复 by dreameriii (#103)

*2026-6-24 17:17*

>
> [feng504x](https://bbs.kanxue.com/user-851059.htm)
>  确实少了这个跑不动，我只能让ai + apatch 代码自己写了一个， 就是kpm调用的ctl0
>

能否分享下你的实现呢？ 我让AI写了，一直没发用 ……

## 回复 by didiid (#104)

*2026-6-25 11:44*

666

## 回复 by byhk (#105)

*2026-6-25 12:24*

谢谢分享

## 回复 by mb_zuzhlnnf (#106)

*2026-7-9 11:52*

6666

## 回复 by mb_bdctiije (#107)

*2026-7-14 12:50*

学习

## 回复 by mb_vymbqugn (#108)

*2026-7-14 13:02*

1

## 回复 by puppet_w (#109)

*2026-7-14 14:02*

6666

## 回复 by 珍惜Any (#110)

*2026-7-14 14:52*

其实我落地了![image](https://bbs.kanxue.com/view/img/face/057.gif) 正常lsplant是入口替换。我这个是直接类似frida inlinehook入口 。![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by mb_pelomxiq (#111)

*2026-7-17 18:12*

666

## 回复 by _雨化田 (#112)

*2026-7-19 08:48*

感谢分享

## 回复 by Yuuuual (#113)

*2026-7-23 13:38*

学习记录，感谢分享

## 回复 by xtyuns (#114)

*2026-7-24 13:48*

学习一下

## 回复 by mb_pesxllvn (#115)

*2026-7-24 14:29*

666

## 回复 by git_30584zhutou9527 (#116)

*2026-7-24 22:04*

666

## 回复 by wx_coddvccwyh (#117)

*2026-7-25 03:28*

66666

## 回复 by guardia (#118)

*2026-7-25 04:10*

see

## 回复 by mb_mrcxjlrd (#119)

*2026-7-26 22:53*

666

## 回复 by RhaySF (#120)

*2026-7-27 01:21*

666

## 回复 by mb_xiycqmtm (#121)

666

## 回复 by mb_rtxtnuec (#122)

感谢分享

## 回复 by mb_irhdtnzm (#123)

1

## 回复 by mb_rbixrkdo (#124)

学习一下了
