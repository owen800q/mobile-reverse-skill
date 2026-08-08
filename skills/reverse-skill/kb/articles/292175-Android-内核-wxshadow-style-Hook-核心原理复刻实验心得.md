---
title: '[原创] Android 内核 wxshadow-style Hook 核心原理复刻实验心得'
url: https://bbs.kanxue.com/thread-292175.htm
tid: 292175
author: Ivory0
date: '2026-07-26'
tags: [Android安全, 原创, HOOK注入, 基础理论]
crawled_at: '2026-08-08T10:01:51+00:00'
replies: 25
---

# Android 内核 wxshadow-style Hook 核心原理复刻实验心得

>
> 本文记录一次基于 Pixel 7 / Android 14 / FolkPatch KPM 的 wxshadow-style Hook 复刻实验。文章重点是设计思路、验证路径和问题定位复盘，范围限定为 测试 APP 页级目标、PTE 事务和异常分流。
>
>
>

GitHub: [wxshadow hook 原理 POC](https://github.com/tiwe0/wxshadow-hook-poc)

## 0. 写在前面

最初目标很朴素：拜读了 [linux/android 利用shadow内存无痕hook方法](https://bbs.kanxue.com/thread-290304.htm)、 [Android 内核无痕 Hook 框架设计思路和避坑指北](https://bbs.kanxue.com/thread-292066.htm)、 [Android内核无痕Hook理解和感悟](https://bbs.kanxue.com/thread-290718.htm) 几篇文章后，萌生了针对手头的机器，复刻 wxshadow 思路的 KPM 的实验的想法。做着做着发现，原理并不难，都是些计算机组成原理和操作系统的基础知识，真正困难的部分反而集中在 PTE 修改之后的一系列状态管理问题：

- 哪个进程、哪个 `mm`、哪一页、哪个 generation 才是本次 Hook 的合法对象；
- 异常入口进来时，如何判断这是自己的 fault，并让其他 fault 沿原路径处理；
- PTE 修改以后，TLB、icache、dcache、恢复路径、owner 退出路径如何完成一致性恢复；
- KPM 卸载时，回调、worker、in-flight handler、page record 是否已经全部收干净；
- 设备重启以后，如何区分“功能异常”“观测扰动”“卸载路径触发重启”。

这次实验的最终产物为一个 **概念验证级别的 wxshadow 思路的复现代码**：目标页由测试 App 主动选定，也就是测试 App 主动调用启动 hook（通常 hook 都是外部侵入性的，但这里不影响我们的验证），KPM 只接受固定 UID、owner TGID、owner `mm`、token、slot、generation 都匹配的请求。这个边界让实验可以被稳定复现，也让每一次失败都有比较清楚的异常归因；若要扩展到更通用的目标描述符或内核注入框架边界，还需要补齐目标准入、生命周期和检测面验证。

最终成果已经开源到 GitHub，各位有兴趣的佬可以直接在此基础上继续开发，或者根据手头的机器更改更好的实现路线：

\```
tag: wxshadow-f5d2-route-identity-vma-20260725
base tag: wxshadow-final-lab-page-table-20260725
device: Pixel 7 panther / Android 14
kernel: 5.10.198-android13-4-00050-g12f3388846c3-ab11920634
runtime: FolkPatch 50ac6,d01
\```

## 0.5 原理速览

开始之前我们先快速过一遍原理，几个大佬的文章我拜读了好几遍，细节分支思路上有些不同，但总体的思路是一致的。通过页 fault 和 页 切换这些用户空间无法直接感知的手段实现 hook。

我们先快速复习一下计算机组成原理和操作系统中非常重要的模块：虚拟内存。

虚拟内存很好的解决了权限管理和内存时空利用率的问题。原理很简单，用一个数据结构记录虚拟内存到物理内存的映射关系。程序只能看到虚拟地址，读/写内存时，物理内存页存在就直接用，不存在就出 页缺失 fault，然后内核出面分配物理页并维护映射关系。重要的是，这一过程是在内核中发生的，用户空间的程序不用特别的手段（比如一些侧信道手段），是没办法直接感知到的。

好了，原理很简单，但实现起来坑就很多了。二分搜索的原理也很简单，但现在让在座的各位立刻手写一个正确的二分搜索算法，估计有不少佬都开始汗流浃背了。

本文把 wxshadow-style Hook 拆成三个问题。

第一部分是 **如何触发 hook 安装**。常见路线有硬件断点和 UXN fault。硬件断点命中精确，但资源和上下文管理成本高；UXN fault 通过把目标页临时设为不可执行，在目标代码第一次执行时进入 IABT，再由 KPM 校验 `mm + VA + generation` 后完成切换。本文选择 UXN 作为安装触发入口。

第二部分是 **如何实现执行视图切换**。可选路线包括 visible clone、raw two-PFN 和 BRK/step descriptor。本文先用 visible clone 验证最小闭环，再升级到 raw two-PFN：同一 VA 的 PTE 在 original PFN 和 shadow PFN 之间切换，执行时进入 shadow 页。

第三部分是 **如何实现读取视图隐藏**。核心目标是执行看 shadow，读取尽量看 original。本文采用 translation-DABT read-cycle，并进一步验证 Pixel 7 上的 wxshadow-style raw-XOM permission-DABT original-read。

## 1. 总体架构

整个实验拆成两层。

第一层是 Lab App。它是我们的测试 App，负责创建受控目标页、触发读写执行、通过 KernelPatch SuperCall 发送命令、记录用户态观测结果。目标地址来源限定为 Lab App 自己分配或映射的页。

第二层是 KPM。KPM 负责：

- 维护 session：`Lab UID + owner TGID + owner mm + token`；
- 维护 raw page table：固定两个 Lab slot；
- 保存每页的 source VA、source PFN、shadow PFN、original PTE、generation；
- 在 IABT / DABT / GUP / fork / exit / prctl 等路径里按 `mm + page + generation` 路由；
- 在 clear、owner exit、exec、异常回滚、module unload 时恢复 PTE、释放 shadow backing、解除 hook、等待 worker 退出。

最后代码里绕不开的结构有这些：

\```
session
  lab_uid
  owner_tgid
  owner_mm
  token

raw_page_slot[N]
  slot_id
  generation
  owner_mm
  source_va
  source_pfn
  shadow_pfn
  original_pte
  state
  patch_records[1024]
  route_counters
\```

这就是本文里的 shadow page（这个词是从另一位佬 kkkbbb 那里借用过来的，有兴趣的可以去看看 rustfrida 那个项目）：执行时切到 shadow PFN，必要时恢复 original view。

### 1.1 数据结构：从单页对象改成 page-owned descriptor

这部分将原本简单的页对象升级成能承载更多管理信息的描述符结构。

```c
#define R0LAB_RAW_PAGE_SLOT_CAPACITY 2U                 // Lab 版固定两页，用 slot0/slot1 验证多页隔离。
#define R0LAB_PATCH_RECORD_CAPACITY 1024U               // 每页 patch record 上限，后续 rebuild 只扫描本页记录。
#define R0LAB_PATCH_DIRTY_BITMAP_SIZE (R0LAB_RAW_PAGE_SIZE / 8U) // 页内 dirty 位图，用于描述 4 KiB 页内哪些范围需要重建。

enum r0lab_raw_state {                                  // raw page 的状态机，PTE 切换必须和这里同步。
    R0LAB_RAW_EMPTY = 0,                                // slot 还没有捕获目标页。
    R0LAB_RAW_CAPTURED,                                 // 已记录 source PFN 和 original PTE。
    R0LAB_RAW_SOURCE_UXN,                               // source 页被设置 UXN，用来触发下一次 IABT。
    R0LAB_RAW_SHADOW_RX,                                // 同一 VA 已切到 shadow PFN，可执行 patch 后代码。
    R0LAB_RAW_ORIGINAL_STEP,                            // 单步窗口使用 original 视图。
    R0LAB_RAW_RESTORED,                                 // 已恢复 original PTE。
    R0LAB_RAW_POISONED,                                 // 事务异常后标记为不可继续复用。
    R0LAB_RAW_ORIGINAL_READ,                            // 一次性 original-read window 正在打开。
    R0LAB_RAW_SHADOW_XOM,                               // 执行走 shadow，普通读侧触发 permission-DABT。
};                                                       // 状态枚举结束。

struct r0lab_raw_page {                                 // 保存同一 VA 的原始页、shadow 页和 live PTE 状态。
    void *mm;                                           // owner 进程的 mm，用来限制 fault/hook 归属。
    unsigned long address;                              // source VA，所有 PTE 操作都围绕这一页。
    void *shadow_kaddr;                                 // shadow backing 的内核映射地址。
    unsigned long source_pfn;                           // 原始物理页 PFN。
    unsigned long shadow_pfn;                           // shadow backing PFN。
    unsigned long original_pte;                         // 捕获时保存的 original PTE。
    unsigned long source_uxn_pte;                       // source PFN + UXN，用来触发执行异常。
    unsigned long shadow_rx_pte;                        // shadow PFN + RX，用来执行 patch 后代码。
    unsigned long shadow_xom_pte;                       // shadow PFN + 执行侧保留、用户读侧关闭。
    unsigned long active_pte;                           // page record 认为当前 live PTE 应该是什么。
    unsigned long read_cycle_saved_pte;                 // original-read window 打开前保存的 PTE。
    unsigned long read_cycle_active;                    // 当前是否处在 read-cycle。
    unsigned long gup_hide_active;                      // 当前是否处在 GUP original 视图窗口。
    unsigned long fork_hide_active;                     // 当前是否处在 fork original 视图窗口。
    unsigned long state;                                // 当前 raw page 状态，对应 r0lab_raw_state。
};                                                       // raw page 低层状态结束。

struct r0lab_page_record {                              // Lab 层保存的页身份信息。
    unsigned long source_address;                       // Lab App 声明的页地址。
    unsigned long source_pfn;                           // 捕获到的 source PFN。
    unsigned long shadow_pfn;                           // 分配到的 shadow PFN。
    uint64_t generation;                                // 每次 arm/clear 后递增，过滤旧命令。
    uint8_t backend;                                    // 当前页使用的 backend 类型。
    uint8_t state;                                      // Lab 层状态摘要，便于 status/manifest 输出。
};                                                       // 页身份 record 结束。

struct r0lab_patch_record {                             // 一个页内 patch 片段。
    uint16_t offset;                                    // patch 在 4 KiB 页内的起始偏移。
    uint16_t length;                                    // patch 长度。
    uint8_t active;                                     // 是否参与 shadow rebuild。
    uint64_t version;                                   // 版本号，用来决定多个 patch 的覆盖顺序。
    void *data;                                         // patch 字节内容。
};                                                       // patch record 结束。

enum r0lab_raw_hook_kind {                              // 记录 token 来自哪一种 hook 入口。
    R0LAB_RAW_HOOK_NONE = 0,                            // 未命中任何 hook。
    R0LAB_RAW_HOOK_ABORT,                               // do_mem_abort/IABT/DABT 路由。
    R0LAB_RAW_HOOK_FAULT,                               // handle_mm_fault 观测路由。
    R0LAB_RAW_HOOK_GUP,                                 // GUP 读者路由。
    R0LAB_RAW_HOOK_FORK,                                // dup_mmap/fork 路由。
    R0LAB_RAW_HOOK_SYSCALL,                             // syscall 控制入口。
    R0LAB_RAW_HOOK_PRCTL,                               // prctl 控制入口。
    R0LAB_RAW_HOOK_EXIT,                                // owner exit 清理入口。
};                                                       // hook kind 结束。

struct r0lab_raw_hook_page_token {                      // hook 命中后传给具体处理函数的页令牌。
    uint16_t slot_id;                                   // 命中的 slot。
    uint64_t generation;                                // 命中时的 generation。
    struct r0lab_raw_shadow_page *page;                 // 命中的页对象。
    enum r0lab_raw_hook_kind kind;                      // 命中的 hook 类型。
};                                                       // hook token 结束。

struct r0lab_raw_shadow_page {                          // 单个 Lab slot 的完整页对象。
    struct r0lab_page_record record;                    // 对外可观测的页身份摘要。
    struct r0lab_raw_page raw;                          // PTE/PFN/read-cycle 等低层状态。
    uint64_t generation;                                // slot 当前 generation。
    uint16_t slot_id;                                   // slot 编号。
    bool reserving;                                     // 正在分配或捕获资源。
    bool armed;                                         // 当前页已 arm，可参与 hook 路由。
    bool clearing;                                      // 正在 clear/restore。
    bool transitioning;                                 // 正在进行 PTE 事务，禁止重入。
    bool mm_count_owned;                                // KPM 持有 mm_count 引用。
    bool mm_users_owned;                                // KPM 持有 mm_users 引用。
    bool hook_installed;                                // abort/main hook 是否已安装。
    bool gup_hook_installed;                            // GUP hook 是否已安装。
    bool fork_hook_installed;                           // fork hook 是否已安装。
    bool fault_hook_installed;                          // fault hook 是否已安装。
    bool exit_hook_installed;                           // exit hook 是否已安装。
    bool syscall_hook_installed;                        // syscall hook 是否已安装。
    bool prctl_hook_installed;                          // prctl hook 是否已安装。
    struct r0lab_patch_record patch_records[R0LAB_PATCH_RECORD_CAPACITY]; // 本页所有 patch records。
    uint16_t patch_rebuild_order[R0LAB_PATCH_RECORD_CAPACITY]; // rebuild 时按 version 排序后的索引表。
    uint8_t patch_dirty[R0LAB_PATCH_DIRTY_BITMAP_SIZE]; // 页内 dirty bitmap。
    uint64_t patch_version;                             // 本页 patch 版本计数器。
    uint16_t patch_record_slots;                        // 已使用过的 record slot 数。
    uint16_t patch_active_count;                        // active record 数。
    struct r0lab_raw_hook_route_stats hook_route_stats; // 本页 hook 命中/拒绝计数。
};                                                       // 单页 shadow object 结束。

struct r0lab_raw_page_table {                           // Lab 的两页 page table。
    struct r0lab_raw_shadow_page slots[R0LAB_RAW_PAGE_SLOT_CAPACITY]; // 固定 slot 数组。
    uint16_t selected_slot;                             // 当前命令默认操作的 slot。
    struct r0lab_raw_hook_route_stats hook_route_miss_stats; // 没有命中任何 slot 的路由计数。
};                                                       // page table 结束。
\```

读这段结构体时，可以按三条线拆开：

- 身份线：`mm`、`address`、`slot_id`、`generation` 决定一个 callback 是否命中本页；
- PTE 线：`original_pte`、`source_uxn_pte`、`shadow_rx_pte`、`shadow_xom_pte`、`active_pte` 描述同一 VA 当前应该指向哪一个 PFN，以及是否处在“执行走 shadow、读取触发 permission-DABT”的 raw-XOM 状态；
- 生命周期线：`reserving`、`armed`、`clearing`、`transitioning` 和各类 hook flag 决定是否允许进入下一次状态转换。

这组结构体对应了几个改造点：

- `r0lab_raw_page` 只管 raw PTE 层：当前 `mm`、目标 VA、原始 PTE、source PFN、shadow PFN、active PTE 和临时 read/GUP/fork window；
- `r0lab_page_record` 是跨 callback 的公共页身份，IABT、DABT、GUP、fork、exit、syscall、prctl 都围绕它做命中判断；
- `r0lab_raw_shadow_page` 把一个 Lab slot 需要的 hook flag、生命周期状态、patch records 和 route stats 都收在页对象里；
- `r0lab_raw_page_table` 把实验边界固定成两个 slot，slot 之间靠 `slot_id` 和 `generation` 隔离，旧 ABI 仍然落到 slot0。

有了这层 page-owned descriptor，后面的改造才有承载点。比如 patch record 从全局数组改成 `page->patch_records[]`，GUP/fork/exit 也从 “当前 raw page” 改成 “先找到命中的 slot，再处理这个 slot 的状态”。

### 1.2 完整 Hook 状态机

先放全图。后面的章节基本都在拆这条执行路径：页准入、PTE 事务、异常路由、original-read window、生命周期清理。

 ![完整 Hook 状态机](https://bbs.kanxue.com/upload/attach/202607/939147_9FSAZDAQXWSSGSE.webp)

这张图里有三个控制点。

第一，所有入口都先落到 page descriptor。IABT、DABT、GUP、fork、exit、prctl 这些路径都要重新确认 owner `mm`、page VA 和 generation，命中后才进入对应 handler，其他情况进入 reject path。

第二，PTE 切换只在 page record 状态允许时发生。`SOURCE_UXN`、`SHADOW_RX`、`ORIGINAL_READ`、`RESTORED` 这些状态和 live PTE 必须对得上，状态提交放在 PTE 事务成功之后。

第三，清理路径和功能路径同等重要。显式 clear、owner exit、owner exec、module unload 都要走 exact-original restore、record release、worker drain 和 module list 检查，最终以 `modules=empty`、`warn_count` 保持原值作为收口证据。

## 2. 为什么先做 visible-clone，再做 raw two-PFN

最早的稳定路线选择 visible-clone，raw PTE 放到后面推进。也就是先验证执行视图切换，再验证读视图隐藏。

实验的 M4 阶段里，源页是一个固定的 `MOV W0,#42; RET`，也就是返回数字 42，clone 页是 `MOV W0,#99; RET`，也就是返回 99。KPM 先把 source PTE 改成 UXN，让第一次执行触发 instruction abort，再在异常处理里把 PC 重定向到 clone 页。

clone 是普通可见映射，隐蔽性很弱。它在早期仍然有用：

- 先验证异常路由、owner 绑定、一次性触发、恢复 ABI；
- 避开 raw PFN、cache、TLB、teardown 一起上机的风险。

后续 raw two-PFN 才开始做同 VA 的 PFN 切换：

\```
normal execute -> source PFN -> returns 42
arm raw      -> source PTE becomes SOURCE_UXN
IABT         -> switch same VA to shadow PFN
shadow exec  -> returns 99
clear        -> restore original PTE
normal exec  -> returns 42
\```

这一步证明的是“同一 VA 的执行视图可切换”。证明范围限定在 execution shadow：raw two-PFN 激活后，普通读也会看到 shadow PFN；完整 original-read 隐藏需要额外的读 fault 分流能力。

### 2.1 raw PTE 修改要当成事务

一开始我也容易把 raw PTE 理解成“找到 PTE，然后写一个新值”。上机测试以后，这个抽象很快不够用。于是后面收敛成一个小事务：

\```
admit page -> snapshot original PTE/PFN -> prepare shadow backing
walk target mm -> take leaf PTE lock -> check live PTE == expected
clear old PTE -> target-mm TLB invalidate
sync executable shadow aliases when needed -> install replacement PTE
commit page state
\```

这里有几条硬约束：

- 接受范围限定为 4 KiB leaf PTE；huge PMD、special、contiguous、devmap、tagged 等页表形态进入 unsupported 分类；
- 每次转换都要求 live PTE 等于 page record 里预期的 `original/source_uxn/shadow_rx` 之一，匹配成功后才写入，未命中返回 `EAGAIN`；
- PTE 修改在目标 `mm` 的 `mmap_read_lock` 和 leaf PTE lock 下完成；
- 替换采用 break-before-make 思路：先 clear 旧 PTE，再做 target-mm page TLB invalidation，最后安装 replacement；
- shadow backing 写入可执行内容后要做 icache alias 同步；CPU 执行新字节需要同时满足 PTE 和 icache 状态；
- page record 的状态在 PTE 事务成功以后提交，让内存状态跟随页表写入结果。

这一段的验证同时覆盖返回值和 live-PTE snapshot。held 状态里要能看到 `mmap_lock=read`、`pte_lock=held`、`live_match=1`、`live_state=source_uxn`、 `record_state=source_uxn`。行为层再用 `42 -> 99 -> 42`、read-cycle `99 -> original-read -> 99`、最终 `modules=empty warn_count` 保持原值作为最终的证据。

### 2.2 代码层面的 PTE 事务

raw PTE 相关代码被放进 `kpm/r0lab_raw_compat.c`，主 KPM 文件只通过 `r0lab_raw.h` 里的小 ABI 调用它。这样做的原因是，目标内核头、`mm_struct` 布局、PTE bit 和 KernelPatch KPM 的紧凑头文件混在一起会很难维护。

页表 walk 的入口先把 VMA 和 leaf PTE 形态收紧：

```c
static int r0lab_raw_walk_locked(struct mm_struct *mm, unsigned long address, // 在目标 mm 中定位一页 leaf PTE。
                                 struct vm_area_struct **vma_out,           // 返回命中的 VMA。
                                 pte_t **ptep_out, spinlock_t **ptl_out)    // 返回 leaf PTE 指针和对应锁。
{
    struct vm_area_struct *vma;                                              // 保存 find_vma 的结果。
    pgd_t *pgd;                                                              // 一级页表项。
    p4d_t *p4d;                                                              // 二级页表项，兼容 4/5 级页表布局。
    pud_t *pud;                                                              // 三级页表项。
    pmd_t *pmd;                                                              // 四级页表项，后面检查是否为 section。
    pte_t *ptep;                                                             // 最终 leaf PTE 指针。
    spinlock_t *ptl;                                                         // leaf PTE lock。

    if (!mm || !address || (address & (PAGE_SIZE - 1)) ||                    // mm/address 为空或地址未按页对齐时拒绝。
        !vma_out || !ptep_out || !ptl_out)                                    // 输出指针也必须存在，避免成功路径写空指针。
        return R0LAB_RAW_EINVAL;                                             // 参数形态错误。

    vma = find_vma(mm, address);                                             // 找覆盖 address 的 VMA。
    if (!vma || address < vma->vm_start ||                                   // 要求 VMA 存在且 address 落在 VMA 内。
        address + PAGE_SIZE > vma->vm_end || vma->vm_mm != mm)               // 要求完整覆盖 4 KiB 页且属于目标 mm。
        return R0LAB_RAW_ENOENT;                                             // VMA 形态不满足 Lab 页准入。

    pgd = pgd_offset(mm, address);                                           // 从 mm 根页表取 pgd。
    if (pgd_none(*pgd) || pgd_bad(*pgd))                                     // pgd 为空或坏项时停止 walk。
        return R0LAB_RAW_ENOENT;                                             // 页表形态不满足准入。
    p4d = p4d_offset(pgd, address);                                          // 向下走到 p4d。
    if (p4d_none(*p4d) || p4d_bad(*p4d))                                     // p4d 为空或坏项时停止 walk。
        return R0LAB_RAW_ENOENT;                                             // 页表形态不满足准入。
    pud = pud_offset(p4d, address);                                          // 向下走到 pud。
    if (pud_none(*pud) || pud_bad(*pud) || pud_sect(*pud))                   // pud 为空、坏项或 section mapping 都不处理。
        return R0LAB_RAW_ENOENT;                                             // 只接受继续向下的普通页表。
    pmd = pmd_offset(pud, address);                                          // 向下走到 pmd。
    if (pmd_none(*pmd) || pmd_bad(*pmd) || pmd_sect(*pmd))                   // pmd 为空、坏项或 section mapping 都不处理。
        return R0LAB_RAW_ENOENT;                                             // 只接受普通 4 KiB leaf PTE。

    ptep = pte_offset_kernel(pmd, address);                                  // 取 leaf PTE 地址。
    ptl = r0lab_raw_pte_lockptr(pmd);                                        // 通过兼容 helper 取这个 PTE 页对应的锁。
    spin_lock(ptl);                                                          // 调用者在锁内检查 live PTE 并替换。

    *vma_out = vma;                                                          // 把 VMA 交给调用者用于 flush_tlb_page。
    *ptep_out = ptep;                                                        // 把 leaf PTE 指针交给调用者。
    *ptl_out = ptl;                                                          // 把已持有的 PTE lock 交给调用者释放。
    return 0;                                                                // walk 成功，后续进入 PTE 事务。
}
\```

这段 walk 代码说明了准入边界。地址必须 4 KiB 对齐，VMA 必须完整覆盖这一页，`vma->vm_mm` 必须等于目标 `mm`。各级页表项需要通过 `none/bad` 检查，`pud_sect()` 和 `pmd_sect()` 会挡掉 section mapping，后续只处理 leaf PTE。函数返回时已经拿到 leaf PTE lock，调用者在这个锁内完成 live PTE 检查和替换。

真正替换 PTE 时，顺序固定成 clear、flush、sync、install：

```c
static int r0lab_raw_replace_locked(struct r0lab_raw_page *page,             // 在已持有 PTE lock 的前提下替换一页 PTE。
                                    struct mm_struct *mm,                   // 目标 mm。
                                    struct vm_area_struct *vma,             // 目标 VMA，用于 TLB flush。
                                    unsigned long address, pte_t *ptep,      // 目标 VA 和 leaf PTE 指针。
                                    pte_t replacement)                      // 准备安装的新 PTE。
{
    pte_t old;                                                              // 保存被清掉的旧 PTE。

    old = ptep_get_and_clear(mm, address, ptep);                            // break-before-make：先清掉旧 PTE。
    flush_tlb_page(vma, address);                                           // 清掉目标页相关 TLB。
    if (page && page->shadow_kaddr && page->shadow_pfn &&                   // 只有切向 shadow backing 时才需要同步 icache alias。
        pte_present(replacement) &&                                         // replacement 必须是 present PTE。
        pte_pfn(replacement) == page->shadow_pfn) {                         // replacement 指向 shadow PFN。
        r0lab_runtime_sync_icache_aliases(                                  // 同步 shadow backing 的指令缓存别名。
            (unsigned long)page->shadow_kaddr,                              // 起始地址是 shadow backing。
            (unsigned long)page->shadow_kaddr + PAGE_SIZE);                 // 同步范围是一整页。
    }
    set_pte_at(mm, address, ptep, replacement);                             // 安装新 PTE。
    return r0lab_raw_pte_value(old) ? 0 : R0LAB_RAW_EAGAIN;                 // 旧 PTE 有效则提交成功，否则按并发变化处理。
}
\```

这段替换代码把 break-before-make 落成三个动作：先 `ptep_get_and_clear()` 清掉旧 PTE，再对目标 VMA 做 `flush_tlb_page()`，最后 `set_pte_at()` 安装新 PTE。replacement 指向 shadow PFN 时额外同步 icache alias，让 shadow backing 写入后的 CPU 指令缓存状态与新字节保持一致。返回 `EAGAIN` 表示 clear 出来的旧 PTE 为空，调用方会把它当作并发变化处理。

状态切换函数只在 live PTE 命中预期以后提交内存状态。以 IABT 后切到 shadow 为例：

```c
int r0lab_raw_activate_shadow(struct r0lab_raw_page *page)                  // IABT 后把同一 VA 切到 shadow PFN。
{
    struct mm_struct *mm;                                                   // owner mm。
    struct vm_area_struct *vma;                                             // 目标 VMA。
    pte_t *ptep;                                                            // 目标 leaf PTE。
    spinlock_t *ptl;                                                        // leaf PTE lock。
    pte_t current_pte;                                                      // live PTE 快照。
    pte_t shadow_rx;                                                        // 将要安装的 shadow RX PTE。
    int result;                                                             // 保存 walk/replace 结果。

    if (!page || !page->mm || !page->address ||                             // page、mm、address 必须存在。
        page->state != R0LAB_RAW_SOURCE_UXN || !page->shadow_rx_pte)        // 只允许 SOURCE_UXN 状态切到 SHADOW_RX。
        return R0LAB_RAW_EINVAL;                                            // 状态不满足时拒绝切换。

    mm = (struct mm_struct *)page->mm;                                      // 从 page record 取 owner mm。
    mmap_read_lock(mm);                                                     // 锁住 VMA 结构，防止 walk 期间 VMA 变化。
    result = r0lab_raw_walk_locked(mm, page->address, &vma, &ptep, &ptl);    // 定位 leaf PTE 并持有 PTE lock。
    if (result)                                                             // walk 失败时只释放 mmap lock。
        goto out_unlock_mmap;                                               // 跳到 mmap unlock。

    current_pte = READ_ONCE(*ptep);                                         // 在 PTE lock 内读取 live PTE。
    if (r0lab_raw_pte_value(current_pte) != page->source_uxn_pte) {         // 要求 live PTE 仍是预期的 source UXN PTE。
        result = R0LAB_RAW_EAGAIN;                                          // live PTE 已变更，按重试/并发变化处理。
        goto out_unlock_pte;                                                // 先释放 PTE lock。
    }

    shadow_rx = r0lab_raw_pte_from_value(page->shadow_rx_pte);              // 把保存的 PTE 数值还原成 pte_t。
    result = r0lab_raw_replace_locked(page, mm, vma, page->address, ptep,   // 执行 clear/flush/sync/install。
                                      shadow_rx);                           // replacement 是 shadow RX PTE。
    if (!result) {                                                          // 只有 PTE 事务成功后才提交内存状态。
        page->active_pte = page->shadow_rx_pte;                             // 记录当前 live PTE 应为 shadow RX。
        page->state = R0LAB_RAW_SHADOW_RX;                                  // page 状态进入 SHADOW_RX。
    }

out_unlock_pte:                                                             // PTE 事务出口。
    spin_unlock(ptl);                                                       // 释放 leaf PTE lock。
out_unlock_mmap:                                                            // VMA walk 出口。
    mmap_read_unlock(mm);                                                   // 释放 mmap read lock。
    return result;                                                          // 返回事务结果。
}
\```

这段状态切换代码对应 IABT resume。入口要求 `page->state` 已经是 `R0LAB_RAW_SOURCE_UXN`，说明 source 页被主动设置为不可执行。随后在 PTE lock 内读取 live PTE，只接受 `source_uxn_pte`。替换成功后才更新 `active_pte/state`，测试脚本才能用 live-PTE snapshot 反查“记录状态”和“页表
现场”是否一致。

## 3. Page-list-first：用 page record 承载目标页语义

早期实现里，很多路径都围绕一个全局 raw page 对象发展。单页 smoke 测试往往丝滑通过，但一旦加入 fork、GUP、prctl、exit、patch record，所有状态都会挤在一个对象里：

- 当前页是否 armed；
- 当前 hook 是否属于这一页；
- 当前异常是否来自这一页；
- clear 是显式 clear、owner exit clear，还是 unload clear；
- patch record 属于哪一个版本；
- owner 退出时该释放哪个 `mm` 引用。

这种结构能跑通 demo，但后续排查问题时定位非常头大。

于是后面改成 page-list-first，也就是固定两页 Lab slot，每个 slot 自己持有 generation、PFN、patch records、route counters 和 cleanup state。所有 callback 统一通过 `target mm + page VA + generation` 做路由。

改成 page-list-first 后，几件事变得清楚：

- slot0 兼容旧 ABI；
- slot1 用来验证多页独立性；
- patch/release 记录保持 slot 隔离；
- fork/GUP/fault/abort/prctl 逐步迁移到 page-record 路由；
- 出问题时从 slot、generation 和 counter 定位。

路由函数也按这个思路做。每个 hook callback 进来以后，先拿一个 `r0lab_raw_hook_page_token`，命中后进入本页处理，其他情况记录 reject counter 并沿用原路径：

```c
static int r0lab_raw_page_find_for_hook_locked(                              // 在 page table 中为一个 hook 入口查找命中页。
    enum r0lab_raw_hook_kind kind, void *mm, unsigned long address,          // kind 标识入口类型，mm/address 标识 fault 或 hook 目标。
    uint64_t generation, unsigned int route_flags,                           // generation 过滤旧命令，route_flags 描述本次入口权限。
    struct r0lab_raw_hook_page_token *token)                                 // 命中后返回 page token。
{
    struct r0lab_raw_shadow_page *page;                                      // 候选 slot。
    bool wrong_state;                                                        // 当前状态是否允许进入本 hook。
    bool busy;                                                               // 是否已有读/GUP/fork/PTE 事务窗口。

    if (token) {                                                             // token 允许为空，部分路径只需要 route 结果。
        token->slot_id = R0LAB_RAW_PRIMARY_SLOT;                             // 先初始化为默认 slot，避免调用者读到旧值。
        token->generation = 0;                                               // 清空 generation。
        token->page = NULL;                                                  // 清空 page 指针。
        token->kind = R0LAB_RAW_HOOK_NONE;                                   // 标记为未命中。
    }

    page = r0lab_raw_page_find_by_mm_addr_locked(mm, address);               // 通过 owner mm + VA 查找 slot。
    if (!page) {                                                             // 没有 slot 覆盖这个地址。
        r0lab_raw_hook_route_reject_locked(NULL, true, false, false,         // 记录一次 page miss reject。
                                           false, false);
        return R0LAB_ENOENT;                                                 // 交回原路径处理。
    }
    if (!mm || page->raw.mm != mm) {                                         // 命中的页必须仍属于当前 mm。
        r0lab_raw_hook_route_reject_locked(page, false, true, false,         // 记录一次 mm mismatch reject。
                                           false, false);
        return R0LAB_EPERM;                                                  // mm 身份不一致。
    }
    if (generation && page->generation != generation) {                      // generation 非 0 时必须精确匹配。
        r0lab_raw_hook_route_reject_locked(page, false, false, true,         // 记录一次 generation mismatch reject。
                                           false, false);
        return R0LAB_EAGAIN;                                                 // 旧命令或旧 fault。
    }

    busy = page->transitioning ||                                            // 正在 PTE 事务中。
           ((route_flags & R0LAB_RAW_HOOK_ROUTE_MUTATING) &&                 // mutating 路径还要检查一次性窗口。
            (page->raw.gup_hide_active || page->raw.fork_hide_active ||      // GUP/fork window 会临时切 original。
             page->raw.read_cycle_active));                                  // read-cycle window 也会临时切 original。
    if (busy) {                                                              // 重入风险存在。
        r0lab_raw_hook_route_reject_locked(page, false, false, false,        // 记录一次 busy reject。
                                           true, false);
        return R0LAB_EBUSY;                                                  // 让调用方稍后重试或沿用原路径。
    }

    wrong_state = !page->armed || page->reserving || page->clearing ||       // 未 arm、正在 reserve、正在 clear 都不进入 hook。
                  !page->generation ||                                       // generation 为 0 表示 slot 未进入有效期。
                  !r0lab_raw_hook_route_state_allowed(page, route_flags);    // 当前 raw state 必须符合入口要求。
    if (wrong_state) {                                                       // 状态窗口不匹配。
        r0lab_raw_hook_route_reject_locked(page, false, false, false,        // 记录一次 state reject。
                                           false, true);
        return R0LAB_EAGAIN;                                                 // 作为未就绪处理。
    }
    if (!r0lab_raw_saved_identity_matches(&page->raw)) {                     // 保存态 PFN/PTE 身份必须仍然匹配。
        r0lab_raw_hook_route_identity_reject_locked(page);                   // 记录一次 PTE/PFN 身份漂移 reject。
        return R0LAB_EAGAIN;                                                 // 身份漂移时停止进入本 hook。
    }

    ++page->hook_route_stats.route_hits;                                     // 记录一次有效命中。
    if (route_flags & R0LAB_RAW_HOOK_ROUTE_MUTATING)                         // mutating 路径会改 PTE 或 page state。
        page->transitioning = true;                                          // 设置 transitioning 防止重入。

    if (token) {                                                             // 调用者需要 token 时才写回。
        token->slot_id = page->slot_id;                                      // 返回命中 slot。
        token->generation = page->generation;                                // 返回命中 generation。
        token->page = page;                                                  // 返回 page 对象。
        token->kind = kind;                                                  // 返回 hook 类型。
    }
    return 0;                                                                // 路由成功。
}
\```

这段 route 代码定了 callback 的统一准入规则。`mm + address` 先定位 slot；`generation` 用来过滤旧命令；`transitioning` 和 read/GUP/fork active flag 用来过滤嵌套 PTE 修改；`armed/reserving/clearing/state` 用来过滤生命周期窗口。`r0lab_raw_saved_identity_matches()` 再确认保存下来的 original/source-UXN/shadow PTE 都还指向声明时的 source PFN 或 shadow PFN。只有通过这些检查，callback 才会拿到 token 并进入后续 PTE 操作。route status 里的 `route_identity_mismatch` 用来记录这类身份不一致事件。

这个 token 让 callback 的安全边界变得具体：命中的是哪个 slot、哪个 generation、是否允许修改 PTE、是否正在 read/GUP/fork window 中，都在进入具体 hook 逻辑前完成检查。后面新增 prctl、syscall、GUP、fork、exit 路由时，都复用这套入口，减少了“某个 callback 自己判断一遍”的分叉。

patch record 也从全局状态移动到页对象里。一次 patch 只允许命中当前 owner `mm`、当前 slot、当前 generation，并且要求页处在 `SHADOW_RX`：

```c
static int r0lab_raw_slot_patch_admit_locked(                                // patch 写入前的统一准入检查。
    uint64_t token, uint16_t slot_id, uint64_t generation,                   // token/slot/generation 来自 Lab App 命令。
    unsigned int offset, unsigned int length, struct mm_struct *current_mm,   // offset/length 描述页内 patch 范围。
    struct r0lab_raw_shadow_page **out_page)                                 // 成功后返回可修改的 page。
{
    struct r0lab_raw_shadow_page *page;                                      // 候选 slot。

    if (slot_id >= R0LAB_RAW_PAGE_SLOT_CAPACITY || !length ||                // slot 越界或空 patch 直接拒绝。
        offset >= R0LAB_RAW_PAGE_SIZE ||                                     // 起点必须落在 4 KiB 页内。
        length > R0LAB_RAW_PAGE_SIZE - offset)                               // offset+length 不能越过页尾。
        return R0LAB_EINVAL;                                                 // patch 范围非法。

    page = r0lab_raw_page_slot_locked(slot_id);                              // 在已持有全局锁的前提下取 slot。
    if (!g_session.active || g_session.token != token ||                     // session 必须 active，token 必须匹配。
        g_session.owner_tgid != r0lab_current_tgid() || !current_mm ||        // 调用线程必须属于 owner 进程。
        page->raw.mm != current_mm)                                          // 当前 mm 必须等于 page owner mm。
        return R0LAB_EPERM;                                                  // 身份校验失败。

    if (!page->armed || page->reserving || page->clearing ||                 // page 必须处于 armed 且无 reserve/clear。
        page->transitioning || page->generation != generation ||             // 禁止重入，并要求 generation 精确匹配。
        page->raw.state != R0LAB_RAW_SHADOW_RX || !page->raw.shadow_kaddr || // patch 只允许在 SHADOW_RX + shadow backing 存在时进行。
        page->raw.gup_hide_active || page->raw.fork_hide_active ||           // GUP/fork 窗口中禁止 patch。
        page->raw.read_cycle_active)                                         // original-read window 中禁止 patch。
        return R0LAB_EAGAIN;                                                 // 状态未就绪。

    page->transitioning = true;                                              // 进入 patch/rebuild 原子阶段。
    *out_page = page;                                                        // 返回通过准入的 page。
    return 0;                                                                // 准入成功。
}
\```

这段 admit 代码定死了 patch 入口的约束。调用者必须来自 owner 进程，`token`、 `slot_id`、`generation`、当前 `mm` 都要匹配。页必须处在 `SHADOW_RX`，并且 clear、transition、read-cycle、GUP、fork window 相关标志均为 inactive。满足条件后设置 `transitioning`，后面的 record upsert 和 shadow rebuild 才能作为一个原子阶段推进。

重建 shadow 字节时，先从原始页重新拷贝 range，再按 `version` 顺序应用活跃 record，最后同步 icache：

```c
static int r0lab_raw_rebuild_patch_range(struct r0lab_raw_shadow_page *page,  // 重建 shadow 页内一个范围。
                                         unsigned int offset,                // 本次重建范围起点。
                                         unsigned int length)                // 本次重建范围长度。
{
    uint16_t *order;                                                         // 临时排序数组，保存 record index。
    void *source_kaddr;                                                      // original 页的内核可访问地址。
    unsigned int order_count = 0;                                            // 本次参与 rebuild 的 record 数。
    unsigned int range_end;                                                  // 本次 rebuild 范围的结束偏移。
    unsigned int index;                                                      // 通用循环变量。

    if (!page || !length || offset >= R0LAB_RAW_PAGE_SIZE ||                 // page 为空、长度为 0、offset 越界都拒绝。
        length > R0LAB_RAW_PAGE_SIZE - offset)                               // offset+length 不能越过 4 KiB 页尾。
        return R0LAB_EINVAL;                                                 // rebuild 参数非法。
    if (!page->raw.shadow_kaddr || !g_sync_icache_aliases)                   // shadow backing 或 icache 同步函数必须存在。
        return R0LAB_ENOSYS;                                                 // 当前环境缺少必要能力。
    source_kaddr = r0lab_raw_source_kernel_address(&page->raw);              // 获取 original 页的内核访问地址。
    if (!source_kaddr)                                                       // original 页无法访问时停止 rebuild。
        return R0LAB_EFAULT;                                                 // source 映射不可用。

    order = page->patch_rebuild_order;                                       // 取本页 rebuild 排序缓冲区。
    range_end = offset + length;                                             // 预先算出 rebuild 范围终点。
    for (index = 0; index < page->patch_record_slots; ++index) {             // 扫描本页已使用的 patch record slot。
        unsigned int insert_at;                                              // 当前 record 在排序数组中的插入位置。

        if (!r0lab_patch_overlaps(&page->patch_records[index], offset,       // 只关心 active/data/length 有效且和本次范围重叠的 record。
                                  length))
            continue;                                                        // 无效或无重叠则跳过。
        insert_at = order_count;                                             // 默认插到末尾。
        while (insert_at &&                                                  // 用插入排序按 version 从小到大排列。
               page->patch_records[order[insert_at - 1U]].version >          // 前一个 record 版本更大时后移。
               page->patch_records[index].version) {                         // 当前 record 应该排到更前。
            order[insert_at] = order[insert_at - 1U];                         // 后移已有索引。
            --insert_at;                                                     // 继续向前找插入点。
        }
        order[insert_at] = (uint16_t)index;                                  // 写入当前 record index。
        ++order_count;                                                       // 参与 rebuild 的 record 数加一。
    }

    memcpy((char *)page->raw.shadow_kaddr + offset,                          // 先把 shadow 目标范围恢复为 original 字节。
           (char *)source_kaddr + offset, length);                           // 拷贝同一页内相同 offset/length。
    r0lab_raw_apply_seed_range(page, offset, length);                        // 再应用 seed patch，作为活跃 record 的底层。

    for (index = 0; index < order_count; ++index) {                          // 按 version 顺序叠加 active records。
        const struct r0lab_patch_record *record =                            // 取排序后的 patch record。
            &page->patch_records[order[index]];
        unsigned int record_end = (unsigned int)record->offset +             // record 结束位置。
                                  record->length;
        unsigned int copy_start = offset > record->offset ?                  // 交集起点取两者较大值。
                                  offset : record->offset;
        unsigned int copy_end = range_end < record_end ?                     // 交集终点取两者较小值。
                                range_end : record_end;

        if (copy_end <= copy_start)                                          // 防御性检查交集是否为空。
            continue;                                                        // 空交集不拷贝。
        memcpy((char *)page->raw.shadow_kaddr + copy_start,                  // 把 patch 数据写入 shadow 页交集范围。
               (char *)record->data + copy_start - record->offset,           // patch 数据源偏移要扣掉 record 起点。
               copy_end - copy_start);                                       // 只拷贝交集长度。
    }

    g_sync_icache_aliases((unsigned long)page->raw.shadow_kaddr + offset,    // shadow 字节变化后同步 icache alias。
                          (unsigned long)page->raw.shadow_kaddr + range_end);// 结束地址是本次 rebuild 范围末尾。
    return 0;                                                                // rebuild 成功。
}
\```

这段 rebuild 代码定死了 patch records 的合成规则。它先找出和本次 range 重叠的活跃 record，并按 `version` 从旧到新排序；然后用 original 页重新铺底，再叠加 seed 和 active records。拷贝时只写交集区间，通过范围约束防止一个窄范围 rebuild 覆盖相邻 patch。最后同步 icache alias，保证 shadow 页执行视图和 patch metadata 一致。

F3 阶段验证了两个 slot 的 patch record 独立性：slot0 和 slot1 可以分别 patch 到不同返回值，释放 slot0 时 slot1 保持原状态，slot0 填满 1024 条记录后第 1025 条返回 `ENOSPC`，slot1 的 metadata 保持原值。

## 4. 受控 hidden-read：从 translation-DABT 到 raw-XOM read-fault

wxshadow 最麻烦的地方之一，是执行时使用 shadow 页，读取时却只能看到 original 页。

早期主线选择 translation-DABT read-cycle，因为它最容易把故障来源控制在 Lab 边界内：

\```
1. 正常执行已经在 shadow PFN 上。
2. Lab 显式 arm 一次 data-abort read-cycle。
3. 用户态把同一 raw VA 临时变成 PROT_NONE 后读取。
4. do_mem_abort 里识别 owner mm + raw VA + 非写 translation DABT。
5. KPM 把 PTE 切回 original+UXN，skip origin，让用户态 read 重试成功。
6. 下一次执行触发 IABT，再切回 shadow PFN。
\```

这个版本能证明“original-read window”这个状态机，但需要 Lab 主动制造 `PROT_NONE`。

后面我继续把触发源换成更贴近原版 wxshadow 的 raw-XOM read-fault。这里普通用户态 XOM probe 结果为 absent：Pixel 7 的 `PROT_EXEC` probe 记录为 `user_xom_read_fault=absent`。真正成立的是 Lab-owned raw PTE 路线：在已经激活的 shadow 页上清掉用户读侧，保留执行侧，让同一 VA 进入 `shadow_xom` 状态。

\```
正常建立 shadow page
-> 同一 VA 的 PTE 写成 shadow_xom PFN
-> 执行走 shadow
-> 读触发 permission DABT
-> fault handler 临时把 PTE 切回 original+UXN
-> 读重试拿到 original
-> 下一次执行触发 IABT
-> handler 再把 PTE 切回 shadow_xom PFN
\```

执行时读到的是 shadow 代码返回值 `99`；普通读取同一地址先打到 permission fault，KPM 打开一次 original window，所以读到原始指令字 `52800540`；下一次执行触发 IABT 后恢复 shadow，返回值又回到 `99`。

## 5. BRK/step descriptor：把断点限定为受控 step

实验 S4 阶段做的是 BRK / single-step 方向。

最早的单点验证只证明固定地址、固定 X1 的写入。后来把它改成 page-owned descriptor：

\```
s4_descriptor
  slot_id
  generation
  owner_mm
  page
  brk_offset
  step_offset
  register_policy
\```

BRK callback 和 single-step callback 从全局地址判断改为扫描当前 page table 里已 armed 的 descriptor。这样可以验证两页：

\```
page0 normal -> 42
page1 normal -> 42
page1 hook   -> 99
page0 hook   -> 99
restore both -> 42 / 42
\```

这里为了把断点能力限定在 page-owned descriptor 描述的范围内。加了负向测试：

- bad BRK offset；
- bad step offset；
- stale generation；
- wrong slot；
- arbitrary register index/value；
- cross-slot PC；
- wrong step owner TID。

负向 descriptor probe 通过后，才刷新 S4 ABI、BRK-only、step-only、raw-step、raw-reg、descriptor routing 和 full runner。

## 6. 生命周期治理比 PTE 写入更难

这次实验里，首次 PTE 修改没有成为主要风险点，反复触发设备重启的环节集中在生命周期。

反复出现的风险主要有三类：

### 6.1 `.kpm.exit` 作为阻塞卸载点的适用范围

FolkPatch manager 侧对 KPM `.exit` 返回 busy 采用有限处理策略。等 `.exit` 里才发现 worker 仍在运行、hook 仍在链上、in-flight handler 仍有计数，卸载窗口已经进入高风险状态。

后面改成这套策略：

- 命令层显式 `workers shutdown`；
- KPM `.exit` 只检查 terminal state；
- 每个测试 phase 后都要求 module list 为空；
- 清理状态不明确时保留现场，跳过二次 unload。

### 6.2 owner-exit 比 explicit clear 更危险

显式 clear 是我们主动发命令，时机和线程都可控。owner exit 是目标进程正在 `exit_mmap`，此时 VMA、页表、`mm` 引用、hook callback 都处在敏感路径。

实验曾经在两页 owner-exit 路径上遇到 panic。pstore 里能看到 stopped CPU 落在：

\```
unmap_page_range -> unmap_vmas -> exit_mmap -> KPM wrapper -> __mmput
\```

这说明问题指向全局 `exit_mmap` hook 暴露面和 raw page teardown 的危险组合，需要从生命周期状态机处理。于是后面拆成了很多小片：

- no-abort hold；
- passthrough abort wrapper；
- mmget/mmput exposure；
- empty lock exposure；
- inflight accounting exposure；
- IABT transition ABI；
- reference lifetime parity；
- final lifecycle stress。

每一步只改一个变量，出现异常先分类，再进入下一步修改。

### 6.3 观测本身也可能扰动系统

调试过程中，`status`、logcat、boot-id reader、maps reader 都可能成为扰动源。所以后面很多脚本会分成：

- setup；
- held state；
- online polls；
- preserve-only；
- physical reboot closeout；
- post-reboot module list check。

这些步骤数量较多，内核态调试里，“我想看一下状态” 本身就可能改变现场。

## 7. 验证体系：每个阶段都要能明确归因

写这种代码堪比数学证明，既需要逻辑上完备，又需要有完整的测试约束、原因记录等。常规的先跑通再完善在这里并不太适用。

验证拆成三层，完整通过需要同时具备静态契约、单项 smoke 和最终压力门证据。

第一层是静态契约：

```sh
scripts/verify_wxshadow_reference_source.sh
scripts/verify_wxshadow_reference_inventory.sh
scripts/test_wxshadow_reference_inventory_host.sh
scripts/verify_v1_contract.sh
\```

它验证前期机制梳理数量、文档锚点、脚本语法和禁用路径。

第二层是单项 device smoke，例如：

\```
M0 environment / lifecycle
M1 isolation
M2 HWBP
M3 UXN
M4 visible clone
S4 BRK/step/raw-step/raw-reg
raw two-PFN
raw page table
raw patch records
raw GUP/fork/fault/abort/write/exit
\```

第三层是最终 F7 lifecycle stress runner：

\```
build/evidence/f7-lifecycle-stress-20260725T044119Z/manifest.log
\```

这里放几个测试过程中的证据链例子：

\```
serial=32250DLH2000Z3
repeat_count=1
m0_loops=100
warn_before=3
phase=m5_faults_1 ... status=pass
phase=m5_lifecycle_1 ... status=pass
phase=v1_device ... status=pass
phase=final modules=empty warn_count=3
warn_after=3 result=pass
\```

嵌套 full runner：

\```
build/evidence/v1-device-20260725T044309Z/manifest.log
29 status=pass evidence= phase rows
phase=final modules=empty warn_count=3
warn_after=3 result=pass
\```

manifest 的价值在于留下每个 phase 的证据索引，用可追溯日志替代终端回忆。后面写文章、复盘、回退，都可以从 manifest 追到具体子测试日志。

## 8. 关于 arbitrary process/address：本文的边界选择

读者通常会期待最后来一个任意 PID、任意地址、任意 patch 的实现。但本次实验把实验停在了概念验证。

概念验证级别的输入是：

\```
owner UID
owner TGID
owner mm
token
slot id
generation
page VA
expected bytes
permitted backend
\```

任意 PID/VA 的输入是：

\```
pid
address
patch bytes
mode
\```

后者看起来简单，上机前要先回答这些问题：

- 如何安全拿目标 `mm`，拿多久，谁释放；
- 地址是否属于用户态、是否 page aligned、是否 executable；
- VMA 中途拆分、unmap、mprotect 怎么处理；
- 跨页指令、PAC/BTI、PC-relative load 怎么 relocation；
- fork/exec/exit 过程中记录如何迁移或撤销；
- `/proc`、ptrace、GUP、VMA walk 的观测语义是否要统一隐藏；
- 异常恢复时如何锁定目标进程页表。

这些已经超出原理验证的实现，而更接近通用内核注入框架。为了让文章和产物都能被稳定复现，本文选择 typed target descriptor，范围限定在受控 process/address。（人话：做起来太复杂，而且也过不了审）

因此，本实验的边界是：

\```
1. target-declared address：目标进程必须由受控 Lab App 主动声明
2. KPM 只接受经过 UID/TGID/mm/token/slot/generation 校验的页描述符
3. 通用 arbitrary process/address 属于后续研究方向
\```

## 9. 其他可能探索路线

硬件特性、内核配置或触发源一变，wxshadow-style 设计会出现新的入口。当前 Pixel 7 实验外推到其他设备前需要重新验证。

### 9.1 如果设备支持 EPAN / Linux XOM

EPAN 是 Enhanced Privileged Access Never。Linux arm64 的 `CONFIG_ARM64_EPAN` 说明里把它描述为：让 PAN 可以和 execute-only 映射一起使用。历史上 arm64 曾经支持过用户态 execute-only PTE，但后来在缺少合适硬件保护时，内核 EL1 对这种用户映射的误读不一定会被 PAN 拦住，所以本实验主线曾回退到 `PROT_EXEC` 隐含 `PROT_READ` 的保守行为。

如果某台设备同时满足下面条件：

\```
1. CPU advertises EPAN
2. kernel enables CONFIG_ARM64_EPAN
3. userspace PROT_EXEC/XOM probe proves read fault
4. EL0 read fault can be decoded as stable non-write data abort
\```

满足这些条件后，hidden-read 设计可以更接近“正常执行 shadow，普通读触发 fault 后切回 original”的形态。它的好处是：不必像本文一样让 Lab App 主动 `PROT_NONE` 制造 translation-DABT，普通读本身就可能成为 original-read window 的入口。

不过验证门槛会同步抬高：

- EPAN 特性可以通过 `/proc/cpuinfo` 里的 `epan` 字段预筛，最终仍要用用户态 XOM probe 证明读会 fault；
- 成功判据需要区分 permission DABT 和 translation DABT，SIGSEGV 只是现象；
- fault handler 仍然必须绑定 owner `mm + VA + generation`；
- GUP、`/proc/pid/mem`、ptrace 这些内核读路径是否也能统一回 original，需要单独证明，EPAN 只提供读 fault 前提。

EPAN 提供的是更好的硬件前提，page ownership、PTE 事务和 lifecycle cleanup 仍然逃不掉。

### 9.2 raw-XOM / `PTE_USER` clearing

另一条更贴近 wxshadow 的路线，是直接构造 raw XOM descriptor：例如清掉 `PTE_USER`、保留执行权限，让同一页保持“EL0 可执行但不可直接读”的状态。

这种设计如果成立，普通读取 shadow 页时会进入 permission-fault 分支，KPM 可以在 data abort 里短暂恢复 original，再在下一次 IABT 或状态机里回到 shadow。

Pixel 7 上这条路线已经被收进 Lab 成品，但边界很窄：

\```
raw xom read fault arm <token>
  source=raw_shadow_xom
  action=begin_xom_read_cycle
  observe_only=0
  pte_switch=1
  read_cycle=uxn_original_exec_resume
  capability=raw_xom_read_fault
\```

核心代码可以压缩成三段看。

第一段构造 `shadow_xom_pte`。它沿用 original PTE 的内存属性，PFN 换成 shadow PFN，然后清掉用户读侧并保留 EL0 执行侧：

```c
static inline pte_t r0lab_raw_make_shadow_xom(pte_t original,                // 基于 original PTE 构造 shadow-XOM PTE。
                                              unsigned long shadow_pfn)      // replacement 指向 shadow PFN。
{
    pte_t pte = pfn_pte(shadow_pfn, r0lab_raw_pte_pgprot(original));         // 复用 original 的页属性，只替换 PFN。

    pte = clear_pte_bit(pte, __pgprot(PTE_USER));                           // 清掉用户读侧权限，制造 permission-DABT 入口。
    return clear_pte_bit(pte, __pgprot(PTE_UXN));                           // 保留 EL0 执行侧，让执行仍可进入 shadow。
}

int r0lab_raw_activate_shadow_xom(struct r0lab_raw_page *page)               // 把 SHADOW_RX 进一步切到 SHADOW_XOM。
{
    pte_t current_pte = READ_ONCE(*ptep);                                    // 在 PTE lock 下读取 live PTE。

    if (r0lab_raw_pte_value(current_pte) != page->shadow_rx_pte ||           // live PTE 必须仍是已记录的 SHADOW_RX。
        pte_pfn(current_pte) != page->shadow_pfn)                            // live PFN 必须仍指向 shadow backing。
        return R0LAB_RAW_EAGAIN;                                             // 身份不一致时停止升级。

    shadow_xom = r0lab_raw_make_shadow_xom(original, page->shadow_pfn);      // 构造 shadow-XOM replacement。
    result = r0lab_raw_replace_locked(page, mm, vma, page->address, ptep,    // 通过统一 PTE 事务替换 live PTE。
                                      shadow_xom);
    if (!result) {                                                           // replacement 成功后提交 page 状态。
        page->shadow_xom_pte = r0lab_raw_pte_value(shadow_xom);             // 保存 shadow-XOM PTE 数值。
        page->active_pte = page->shadow_xom_pte;                             // active_pte 同步为 shadow-XOM。
        page->state = R0LAB_RAW_SHADOW_XOM;                                  // 状态进入 SHADOW_XOM。
    }
    return result;                                                           // 返回 PTE 事务结果。
}
\```

第二段打开 original-read window。这里要求当前 live PTE 确实还是 `shadow_xom_pte`，保证异常处理时状态仍由当前 page record 持有：

```c
int r0lab_raw_begin_xom_read_cycle(struct r0lab_raw_page *page)              // permission-DABT 后打开一次 original-read window。
{
    if (page->state != R0LAB_RAW_SHADOW_XOM ||                               // 只有 SHADOW_XOM 状态允许进入读窗口。
        page->read_cycle_active ||                                           // 已有 read-cycle 时拒绝重入。
        page->gup_hide_active ||                                             // GUP window 中拒绝重入。
        page->fork_hide_active)                                              // fork window 中拒绝重入。
        return R0LAB_RAW_EINVAL;                                             // 状态窗口非法。

    current_pte = READ_ONCE(*ptep);                                          // 读取当前 live PTE。
    if (r0lab_raw_pte_value(current_pte) != page->shadow_xom_pte ||          // live PTE 必须仍是 shadow-XOM。
        pte_pfn(current_pte) != page->shadow_pfn)                            // live PFN 必须仍指向 shadow backing。
        return R0LAB_RAW_EAGAIN;                                             // 身份变化时放弃本次读窗口。

    result = r0lab_raw_replace_locked(page, mm, vma, page->address, ptep,    // 把 PTE 临时切回 source_uxn。
                                      source_uxn);                           // source_uxn 让读看到 original，执行仍触发 IABT。
    if (!result) {                                                           // PTE 事务成功后提交 read-cycle 状态。
        page->read_cycle_saved_pte = page->shadow_xom_pte;                  // 保存恢复时要回到的 shadow-XOM PTE。
        page->read_cycle_active = 1;                                         // 标记一次性读窗口已打开。
        page->active_pte = page->source_uxn_pte;                             // active_pte 同步为 source UXN。
        page->state = R0LAB_RAW_ORIGINAL_READ;                               // 状态进入 ORIGINAL_READ。
        ++page->read_cycle_begin_events;                                     // 记录 read-cycle 打开次数。
    }
    return result;                                                           // 返回 PTE 事务结果。
}
\```

第三段是异常路由。`SHADOW_XOM` 只通过显式 flag 放给 permission-DABT 读分支，GUP、fork、普通 patch、syscall、prctl 等旧路径保持原有状态处理：

```c
enum r0lab_raw_hook_route_flags {                                            // hook 路由的状态要求位。
    R0LAB_RAW_HOOK_ROUTE_REQUIRE_SHADOW_RX = 1U << 1,                        // 默认要求页面处于 SHADOW_RX。
    R0LAB_RAW_HOOK_ROUTE_ALLOW_SHADOW_XOM  = 1U << 4,                        // 允许 permission-DABT 读分支命中 SHADOW_XOM。
};                                                                           // route flag 定义结束。

if ((route_flags & R0LAB_RAW_HOOK_ROUTE_ALLOW_SHADOW_XOM) &&                 // 调用者明确允许 SHADOW_XOM。
    page->raw.state == R0LAB_RAW_SHADOW_XOM)                                 // 当前页确实处于 SHADOW_XOM。
    return true;                                                             // 这个状态对当前 route 合法。

permission_read = is_permission_fault(esr) && !(esr & R0LAB_M3_ESR_WNR);     // ESR 同时满足 permission fault 和读访问。
route_result = acquire_page_token(current_mm, far,                           // 用当前 mm 和 FAR 地址获取 page token。
    R0LAB_RAW_HOOK_ROUTE_REQUIRE_SHADOW_RX |                                 // 保留旧的 SHADOW_RX 路由要求。
    R0LAB_RAW_HOOK_ROUTE_ALLOW_SHADOW_XOM,                                   // 额外允许 SHADOW_XOM read-fault。
    &route_token);                                                           // 返回 route token。

shadow_rx_state = page->raw.state == R0LAB_RAW_SHADOW_RX;                   // 记录当前是否为旧 read-cycle 路径。
shadow_xom_state = page->raw.state == R0LAB_RAW_SHADOW_XOM;                 // 记录当前是否为 raw-XOM 路径。

if (!route_result &&                                                         // page token 命中成功。
    permission_read &&                                                       // fault 是读侧 permission-DABT。
    page->abort_probe_source == R0LAB_ABORT_PROBE_SOURCE_READ_PERMISSION &&  // probe 来源也确认是读权限异常。
    shadow_xom_state &&                                                      // 当前页处于 SHADOW_XOM。
    !page->raw.read_cycle_active) {                                          // 当前没有已打开的 read-cycle。
    branch = R0LAB_RAW_ABORT_BRANCH_XOM_READ;                                // 选择 raw-XOM original-read 分支。
}
\```

这条路径只接受当前 Lab App 已声明、已经 raw two-PFN 激活的页。KPM 继续用 owner `mm + VA + generation` 来筛 fault；ESR/FAR 需要同时满足 `WnR=0`、permission fault、命中当前 page record，并且当前页处在 `SHADOW_XOM`。translation-DABT read-cycle 和 write-release 分支只接受 `SHADOW_RX`。通过后，handler 把 PTE 临时切回 original+UXN 并 skip origin，让读指令原地重试。下一次执行触发 IABT，再恢复 `shadow_xom`。

### 9.3 permission-DABT 替代 translation-DABT

permission-DABT 路线解决的是触发源问题。早期版本从：

\```
explicit arm -> PROT_NONE -> translation DABT -> original-read -> IABT resume
\```

升级到：

\```
ordinary read -> permission DABT -> original-read -> IABT resume
\```

Pixel 7 的 raw-XOM gate 已经证明了这个升级路径。它的价值是减少用户态显式 `mprotect(PROT_NONE)` 参与，让普通读本身成为 data abort 入口。进入更大主线前还要继续证明：

- ESR/FAR 解码稳定，`WnR=0`、fault page 命中当前 page record；
- handler 仅处理自己的 read fault，写 fault、其他地址、其他 `mm` 必须放行；
- 原始读重试成功后，shadow resume 的 IABT 保持状态连续；
- 连续读、跨线程读、owner exit 中读、clear 中读都能给出清晰归因。

它只改变 read-cycle 的入口，生命周期难度还在。

### 9.4 iTLB/dTLB split-view 升级路线

如果后续换到支持读侧 fault 的设备，成品形态可以进一步收敛到 iTLB/dTLB split-view：

\```
execute path -> I-side translation -> shadow PFN
read path    -> D-side fault/window -> original PFN
same VA      -> two views, page-record scoped
\```

这个写法更接近 wxshadow 的目标态：同一个 VA 执行时走 shadow，普通读触发 data abort 后短暂回到 original，再由下一次执行异常恢复 shadow。它依赖硬件、 内核配置和异常分类同时过关，需要通过独立 read-fault gate 证明。

### 9.5 `handle_mm_fault` 正向路由

我们做过 `handle_mm_fault` 相关探索，但当前主线只把它放在 observe-only 和
blocked diagnostic 位置。原因是：raw VA 的 `PROT_NONE` 读在 Pixel 7 上会更早
被 `do_mem_abort`/badaccess 路径处理，正向进入 `handle_mm_fault` 的 raw-page
read route 保持 blocked 分类。

如果某个内核/VMA 组合能稳定让目标读进入 `handle_mm_fault`，可以把 original-read window 放到更接近 Linux fault core 的位置。好处是 VMA、fault flags、page-table walk 语义更集中；风险是锁顺序、递归 fault、GUP/fault 重入、VMA 生命周期都会变复杂。可接受的验证顺序应该是：

\```
observe-only hit -> page-record routing -> pte_switch=0 smoke
one-shot read-cycle -> two-slot isolation -> lifecycle stress
\```

在这组验证完成之前，`handle_mm_fault` 保持 hidden-read 探索项状态。

### 9.6 GUP、`/proc`、ptrace、VMA walk 隐蔽面

wxshadow 类实现通常会关注外部读：GUP、`/proc/pid/mem`、ptrace、VMA walk 等路径看到的是 original 还是 shadow。本文只验证了 Lab 边界里的 GUP hook 窗口，实现范围限定在 Lab-bounded GUP smoke。

继续做之前，先把“读”分类，再选择对应 hook：

\```
same-process normal load
external process_vm_readv / GUP
/proc/pid/mem style reader
ptrace peek
VMA/maps walker
kernel-side copy/read helpers
\```

每一类读的锁、上下文、是否允许睡眠、是否可以 safely retry 都不同。统一隐藏已经超出小补丁范围，会发展成新的检测面工程。

### 9.7 PAC / BTI / MTE 等架构特性

PAC、BTI、MTE 不直接提供 shadow page，但会改变 Hook 的可用设计空间。

PAC/BTI 对 arbitrary patch 和 trampoline 影响最大。如果要把固定 `MOV W0,#42; RET` 扩展成任意函数 patch，需要处理 BTI landing pad、PAC 保护的返回/间接分支、PC-relative load、literal pool、跨页指令和 异常返回 ABI。PAC/BTI 主要约束 patch engine，使它更像一个受约束的
AArch64 relocator。

MTE 更适合当调试和防错工具：可以帮助暴露 shadow backing、metadata、teardown 里的野指针或 use-after-free 风险。PTE ownership 和读路径隐藏仍然需要独立证明。

### 9.8 EL2 / stage-2 shadow

如果控制面下移到 hypervisor/EL2，可以在 stage-2 页表里做另一层 shadow：guest 内核看到的是一套页表，stage-2 决定真实物理页。这种设计对 `/proc` 或 guest page-table walk 的隐藏性可能更强。

但它已经超出 FolkPatch KPM 复刻项目，进入 hypervisor 级内存虚拟化项目范围。验证对象会变成 VMID、stage-2 TLB、guest/host cache coherency、EL2 trap latency、Android 启动链和 SELinux/AVB 兼容性。本文把它作为后续方向，KPM 成品路线仍然聚焦 FolkPatch 环境。

### 9.9 更完整的 DBI / trampoline 引擎

还有一条偏工程化的路线：暂时放弃 page-level hidden-read，转向把 raw page table 和 BRK/step descriptor 扩展成小型 DBI/trampoline 引擎。它能覆盖更多函数形态， 但问题会从“PTE 状态机”转成“指令重写正确性”：

- AArch64 指令长度固定，但 PC-relative 访问很常见；
- branch range、literal pool、ADR/ADRP、LDR literal 都要 relocation；
- PAC/BTI 会约束入口和返回；
- 单步和异常恢复必须保持完整寄存器/flags/栈 ABI；
- 跨页 patch 要和 page table 生命周期绑定。

DBI/trampoline 更适合做功能型 Hook 框架，不适合拿来证明 wxshadow 的 shadow page 隐藏性。

## 10. 最终成果

| 能力 | 状态 | 说明 |
|-|-|-|
| 固定 Lab 页 IABT 激活 | 支持 | source UXN 后通过 `do_mem_abort` 进入 shadow |
| raw two-PFN 同 VA 执行切换 | 支持 | execution view 可切到 shadow PFN |
| original-read window | 支持，受控 | 通过一次性 translation-DABT read-cycle |
| raw-XOM / `PTE_USER` clearing | 支持，Pixel 7 Lab 边界 | 同一 VA 执行走 `shadow_xom`，普通读触发 permission-DABT 后读 original，下一次 IABT 恢复 shadow |
| page identity / VMA 观测 | 支持，守卫态 | route 发 token 前校验保存态 PFN/PTE 身份，`raw slot live pte` 输出 `vma_match`、`vma_flags`、`pte_match`、`pfn_match` 和 `identity_match` |
| 两页 page table | 支持 | slot0/slot1 独立 generation/PFN/state |
| page-local patch records | 支持 | 每页 1024 条记录，版本化 rebuild |
| GUP/fork/fault/abort/write/exit 路由 | 支持，Lab 边界 | 通过 target-mm + page-record 路由 |
| S4 BRK/step descriptor | 支持，Lab 边界 | 包含两页 routing 和负向 descriptor controls |
| owner exit / exec / ENOMEM / interrupted arm | 支持 | F7 lifecycle stress 验证 |
| arbitrary PID/VA | 未纳入 | 本文成品目标限定在 Lab-declared page |
| 通用 iTLB/dTLB split-view | 未纳入 | 当前证明范围是 Pixel 7 Lab-owned raw-XOM 页，通用设备和外部读者需要另设 gate |
| `/proc` / ptrace / VMA 隐蔽 | 未纳入 | 属于广义检测面治理 |

## 11. 总结

这次复刻最大的收获是：内核 Hook 的难点集中在状态转换治理。每个状态转换都要能讲清楚、测出来，并在异常时可回退。

最后稳定下来的原则：

- 先做 visible clone，再做 raw PFN；
- 先做单页，再做两页 page table；
- 先做 page-local patch records，再迁移 GUP/fork/fault/abort/prctl/exit；
- 先分类 panic，再改代码；
- 卸载路径采用显式 worker shutdown 和 terminal state 检查；
- raw-XOM、`PTE_USER` clearing 只在 Pixel 7 Lab-owned read-fault gate 内写成能力；
- arbitrary PID/VA、`/proc`、ptrace、VMA 隐蔽保留为后续研究方向；
- 每次通过的测试都用 manifest、commit 和 tag 固化。

最终产物定位为一个能在固定 Pixel 7/FolkPatch/Lab App 环境里复现 wxshadow 核心状态机的研究样品。通用隐蔽框架属于后续研究方向，并不在本文讨论范围内。这个实验已经证明，page ownership、raw PTE transaction、shadow execution、translation-DABT original-read、raw-XOM permission-DABT original-read、descriptor routing 和 lifecycle cleanup 可以拆成可验证阶段。

## 12. 参考资料

- [linux/android 利用shadow内存无痕hook方法](https://bbs.kanxue.com/thread-290304.htm)
- [Android 内核无痕 Hook 框架设计思路和避坑指北](https://bbs.kanxue.com/thread-292066.htm)
- [Android内核无痕Hook理解和感悟](https://bbs.kanxue.com/thread-290718.htm)
- [Linux arm64 CONFIG_ARM64_EPAN](https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/refs/heads/master/arch/arm64/Kconfig)
- [arm64: Introduce execute-only page access permissions](https://patches.linaro.org/patch/73807/)
- [arm64: Revert support for execute-only user mappings](https://kernel.googlesource.com/pub/scm/linux/kernel/git/jbarnes/linux/+/24cecc37746393432d994c0dbc251fb9ac7c5d72)

---

# 回复

## 回复 by Midsw (#2)

*2026-7-26 17:57*

tql. mark

## 回复 by mb_iiulbilc (#3)

*2026-7-26 19:43*

感谢楼主，一篇对自己边界相当城实的文章，没有夸大自己，非常棒

## 回复 by mb_ldbucrik (#4)

*2026-7-26 21:00*

感谢分享

## 回复 by Sigil (#5)

*2026-7-26 23:39*

1

## 回复 by guardia (#6)

*2026-7-27 00:09*

1

## 回复 by wx_Huber Barrientos (#7)

*2026-7-27 00:47*

666

## 回复 by iBa0 (#8)

*2026-7-27 09:31*

112312

## 回复 by mb_pesxllvn (#9)

*2026-7-27 10:53*

6666

## 回复 by wx_三生三世 (#10)

*2026-7-27 14:57*

学习

## 回复 by 珍惜Any (#11)

*2026-7-27 17:26*

点赞

## 回复 by Gryffindoss (#12)

*2026-7-28 10:16*

666

## 回复 by yushusu (#13)

*2026-7-28 14:22*

6

## 回复 by 黑屏 (#14)

*2026-7-28 14:23*

666

## 回复 by wgetlaidu (#15)

*2026-7-28 15:37*

666

## 回复 by wx_范迪塞尔 (#16)

*2026-7-28 16:19*

6666

## 回复 by git_71735namngsec-netizen (#17)

*2026-7-28 22:03*

666

## 回复 by mb_irhdtnzm (#18)

*2026-7-30 06:57*

1

## 回复 by mb_euhyowpw (#19)

*2026-7-30 21:29*

666

## 回复 by 小黄鸭爱学习 (#20)

*2026-7-31 13:39*

最近少有的非AI好文

## 回复 by xianhuimin (#21)

看看

## 回复 by 学计算机睡觉 (#22)

666

## 回复 by Imxz (#23)

tql

## 回复 by roysue (#24)

666

## 回复 by mb_kbkqyusp (#25)

666

## 回复 by 4ak5ra (#26)

学习
