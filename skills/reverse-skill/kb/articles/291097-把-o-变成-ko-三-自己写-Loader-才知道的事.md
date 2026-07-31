---
title: '[原创]把 .o 变成 .ko（三）：自己写 Loader 才知道的事'
url: https://bbs.kanxue.com/thread-291097.htm
tid: 291097
author: 孤木落
date: '2026-05-04'
tags: [Android安全, 原创, 基础理论, 程序开发, 系统相关, 源码框架]
crawled_at: '2026-07-31T15:07:42+08:00'
replies: 15
---

# 把 `.o` 变成 `.ko`（三）：自己写 Loader 才知道的事

>
> 本文是系列第三篇，也是收官之作。
>
>
> 前两篇讲述了如何通过 ELF 格式转换，将用户空间编译产物变成 `.ko`，并踩平了 Android GKI 设备上的安全特性陷阱，包括 SELinux、vermagic、BTI、PAC、CFI 和厂商驱动对 ELF section 布局的敏感问题。
>
>
> 当基础格式和安全机制都打通后，我们面临一个更根本的问题：
>
>
> **是否必须依赖内核原生的模块加载器？**
>
>
> 如果希望在目标设备运行时动态接收、解析、重定位并执行受控二进制，就必须自己实现一个运行在内核空间的迷你加载器。
>
>
> 本篇记录自研内核模块加载器 **KPM Loader** 从设计到落地过程中遇到的关键问题。原始调试过程中一共记录了第 21 到第 39 个坑，经过复盘后，将其中被后续方案完全覆盖的临时坑合并，最终整理为第 21 到第 34 个核心坑。
>
>
>

---

## 背景：为什么需要自己的 Loader

KPatcher 的离线转换方案解决了“生成合法 `.ko`”的问题，但它有一个根本局限：

>
> 所有 ELF 转换、section 修补、符号处理和重定位修复都必须在开发机上完成。
>
>
>

如果希望目标设备在运行时直接接收二进制、完成解析、重定位和执行，就需要一个运行在内核空间的加载器。

KPM Loader 应运而生。

它是一个独立内核模块，通过 `/proc` 接口接收一种自定义格式的二进制，称为 KPM，并在内核空间完成：

- ELF 解析
- section 布局
- 符号解析
- 重定位处理
- 内存权限切换
- 指令缓存刷新
- KPM 入口函数调用
- KPM 卸载与资源释放

本质上，这就是一个迷你的内核模块加载器。

内核原生加载器走过的每一步：

- ELF 校验
- section 分类
- 符号解析
- relocation 应用
- module memory 分配
- text 权限切换
- init / exit 生命周期管理

我们都要自己实现一遍。

而那些在内核加载器里被成熟代码处理好的细节，自己动手时全都变成了坑。

---

# 第一部分：运行时基础环境

## 坑 21：`kallsyms_lookup_name` 地址的 KASLR 时效性

### 现象

每次都按流程获取 `kallsyms_lookup_name` 地址：

```bash
insmod loader.ko kaddr=0x...
```

模块可以加载成功。

但有时前一秒还能正常工作的模块，下一秒就崩溃。

崩溃类型是：

```
IABT
```

也就是 Instruction Abort。

崩溃点恰好发生在调用 `kallsyms_lookup_name()` 的位置。

### 根因

Android GKI 内核启用了 KASLR：

```
Kernel Address Space Layout Randomization
```

每次设备重启后，内核符号的虚拟地址都会重新随机化。

典型错误流程如下：

```bash
# 终端 1：获取地址
adb shell grep kallsyms_lookup_name /proc/kallsyms

# 输出：
# ffffffeedaaa69b8 T kallsyms_lookup_name

# 设备中途崩溃重启，KASLR 重新随机化

# 终端 2：继续使用旧地址
adb shell insmod loader.ko kaddr=0xffffffeedaaa69b8

# 旧地址已经失效，跳转到随机位置，触发 IABT
```

两个 adb 会话之间设备恰好发生了重启，符号地址已经变化，但 loader 仍在使用旧地址。

### 解决

始终在同一次启动周期内重新获取地址，并立即加载模块。

示例：

```bash
ADDR=$(adb shell "su -c 'grep kallsyms_lookup_name /proc/kallsyms | head -1'" \
    | awk '{print "0x"$1}')

adb shell "su -c 'insmod /data/local/tmp/loader.ko kaddr=$ADDR'"
```

### 教训

KASLR 地址只在单次启动周期内有效。

任何崩溃、重启、软重启之后，都必须重新获取所有 kallsyms 地址。

这是动态分析内核环境的基础纪律。

---

## 坑 22：`hex_to_ulong` 的 `0x` 前缀陷阱

### 现象

通过 `/proc/kpm_loader` 写入了正确的 `kallsyms_lookup_name` 地址：

```bash
echo kaddr 0xffffffeedaaa69b8 > /proc/kpm_loader
```

但 `dmesg` 显示：

```
kallsyms_lookup_name set to 0
```

后续所有符号解析全部失败。

### 根因

自写的 `hex_to_ulong()` 函数没有处理 `0x` 前缀。

有 bug 的解析逻辑类似这样：

```c
static int hex_to_ulong(const char *s, int max_len, unsigned long *out)
{
    unsigned long v = 0;
    int i;

    for (i = 0; i < max_len && s[i]; i++) {
        /*
         * 遇到非十六进制字符就停止。
         *
         * 输入是 0xffffffeedaaa69b8：
         *   s[0] = '0'
         *   s[1] = 'x'
         *
         * 'x' 不是十六进制字符，于是循环在 i = 1 处退出。
         */
    }

    /*
     * 函数错误地认为 i > 0 就是解析成功，
     * 最终 out 被设置成 0。
     */
}
```

也就是说：

```
0xffffffeedaaa69b8
```

被错误解析成：

```
0
```

而且函数还返回“成功”。

### 解决

在解析前显式跳过 `0x` 或 `0X` 前缀：

```c
if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X'))
    s += 2;
```

### 教训

十六进制解析函数必须显式处理 `0x` 前缀。

内核日志、`/proc/kallsyms` 输出、用户空间脚本提取出来的地址，几乎都会保留这个前缀。

如果解析器不处理它，就会解析出 0，而且很可能没有任何错误提示。

---

# 第二部分：内存管理与权限切换

## 坑 23：ARM64 上 `module_alloc()` 返回的是不可执行内存

### 现象

KPM 加载完成后调用入口函数：

```
kpm_init()
```

结果触发：

```
IABT
```

也就是 Instruction Abort。

崩溃地址正好落在 KPM 的 `.text` 段中。

这说明代码所在内存不可执行。

### 根因

在 ARM64 GKI 上，`module_alloc()` 返回的内存属性通常是：

```
PAGE_KERNEL
```

也就是：

- 可读
- 可写
- 不可执行

在 ARM64 上，不可执行由 PXN 控制：

```
PXN = Privileged Execute Never
```

因此，`module_alloc()` 得到的内存默认不是可执行内存。

这和很多 x86_64 环境不同。x86 上开发 loader 时，这类问题经常不会暴露；但在 ARM64 Android GKI 上，PXN 是硬件强制的。

### 解决

不能一分配完就直接执行。

正确流程应该是：

```
阶段 1：分配内存
  module_alloc()
  得到 RW / NX 内存

阶段 2：写入内容
  复制 section
  解析符号
  生成 PLT / GOT
  应用 relocation

阶段 3：切换权限
  set_memory_x()
  设置 text 可执行

阶段 4：刷新指令缓存
  flush_icache

阶段 5：调用入口函数
  kpm_init()
```

示例流程：

```c
void *base = module_alloc(total_size);

/* 阶段 1：清零 */
memset(base, 0, total_size);

/* 阶段 2：所有写入都在 RW 阶段完成 */
kpm_move_sections(mod, info, base);
kpm_simplify_symbols(mod, info);
kpm_build_got(mod, info);
kpm_apply_relocations(mod, info);

/* 阶段 3：之后才切换为可执行 */
kpm_make_exec(base, total_size);

/* 阶段 4：刷新 icache */
kpm_flush_icache(base, total_size);

/* 阶段 5：调用 KPM */
call_kpm_init(mod->init, args, event, reserved);
```

### 教训

ARM64 的 PXN 是硬件级约束。

不能假设 `module_alloc()` 返回的内存默认可执行。

所有代码写入完成后，必须显式切换为可执行。

---

## 坑 24：WXN 硬件上的写入时序问题

### 现象

重定位计算完全正确，但写入指令后读回仍是旧值。

表现像是写操作失败，但没有明确报错。

### 根因

部分 ARM64 硬件实现支持 WXN：

```
Write XOR Execute
```

也就是页面不能同时拥有写权限和执行权限。

错误流程如下：

```
kpm_alloc_exec(size)
  → 分配内存
  → 立即 set_memory_x()

kpm_move_sections()
  → 复制 .text 内容

kpm_apply_relocations()
  → patch 指令
```

问题在于：

>
> 在 relocation patching 之前，页面已经被设置成可执行。
>
>
>

此时如果硬件或内核策略不允许可执行页继续写入，那么后续对 `.text` 的写操作可能失败或行为异常。

### 正确流程

必须严格遵循：

```
RW 阶段：
  复制 section
  应用 relocation
  写 PLT / GOT / thunk
  完成所有 patching

RX 阶段：
  切换为可执行
  刷新 icache
  不再写 .text
```

也就是：

```c
/* RW 阶段 */
base = module_alloc(size);
memset(base, 0, size);

kpm_move_sections(...);
kpm_apply_relocations(...);
kpm_generate_trampolines(...);

/* RX 阶段 */
set_memory_x(...);
flush_icache_range(...);

/* 执行阶段 */
call_kpm_init(...);
```

### 教训

ARM64 上写权限和执行权限必须分阶段管理。

只要 `.text` 进入可执行阶段，就不应该再继续 patch 它。

---

## 坑 25：GKI 符号可见性限制

### 现象

编译阶段一切正常，但运行时：

```c
kallsyms_lookup("module_alloc")
```

返回：

```
NULL
```

类似的问题还出现在：

- `set_memory_x`
- `set_memory_rw`
- `__flush_icache_range`
- `aarch64_insn_patch_text_nosync`

### 根因

Android GKI 严格限制导出符号列表。

某个符号即使存在于 `/proc/kallsyms` 中，也不代表普通模块可以直接引用。

常见情况是：

| 符号 | 是否通常可直接模块引用 |
|-|-|
| `printk` | 可以 |
| `kmalloc` / `kfree` | 可以 |
| `vmalloc` / `vfree` | 可以 |
| `filp_open` / `filp_close` | 视配置而定 |
| `module_alloc` | 通常不可直接引用 |
| `set_memory_x` | 通常不可直接引用 |
| `set_memory_rw` | 通常不可直接引用 |
| `__flush_icache_range` | 通常不可直接引用 |
| `aarch64_insn_patch_text_nosync` | 通常不可直接引用 |

KPM Loader 又恰好需要这些不导出的核心函数。

### 解决

在 loader 初始化阶段，通过传入的 `kallsyms_lookup_name` 地址统一解析，并缓存所需符号。

示例结构：

```c
static unsigned long cached_module_alloc;
static unsigned long cached_set_memory_x;
static unsigned long cached_set_memory_rw;
static unsigned long cached_flush_icache;
static unsigned long cached_insn_patch;

static const char *needed_syms[] = {
    "module_alloc",
    "set_memory_x",
    "set_memory_rw",
    "__flush_icache_range",
    "aarch64_insn_patch_text_nosync",
    NULL
};
```

初始化时统一解析：

```c
for (int i = 0; needed_syms[i]; i++) {
    unsigned long addr = kallsyms_lookup(needed_syms[i]);

    if (!addr) {
        pr_warn("kpm_loader: symbol %s not found\n", needed_syms[i]);
        continue;
    }

    /*
     * 根据符号名缓存到对应变量。
     */
}
```

### 教训

不要假设某个内核符号在 GKI 上一定导出。

写内核 loader 需要的关键函数，往往恰好不在 GKI 对外导出列表中。

---

# 第三部分：重定位引擎

## 坑 26：AArch64 重定位类型常量整体偏移一位

### 现象

KPM 中的：

```c
printk("kpm_test: init called\n");
```

输出了乱码，而不是正常字符串。

进一步调试发现，ADRP 指令编码异常：

```
正确值：0xB0000000
实际值：0x9001FF00
```

对比：

```
正确：
  0xB0000000 = adrp x0, #0x1000
  指向 rodata 页面

实际：
  0x9001FF00 = adrp x0, #0x7FC000
  指向约 8MB 外的随机页面
```

但重定位数学本身是对的：

```
val   = mod->start + 0x1000
place = mod->start + 0x8
sval  = 0x1000
imm   = 1
```

理论上 ADRP 应该被编码成：

```
0xB0000000
```

但实际却变成了：

```
0x9001FF00
```

### 根因

loader 中定义的 AArch64 relocation type 常量，从 `MOVW_PREL_G0` 开始整体偏移了一位。

错误表大致如下：

| 常量 | 错误值 | 正确值 |
|-|-|-|
| `R_AARCH64_MOVW_PREL_G0` | `0x112` | `0x111` |
| `R_AARCH64_MOVW_PREL_G0_NC` | `0x113` | `0x112` |
| `R_AARCH64_ADR_PREL_PG_HI21` | `0x114` | `0x113` |
| `R_AARCH64_ADR_PREL_PG_HI21_NC` | `0x115` | `0x114` |
| `R_AARCH64_ADD_ABS_LO12_NC` | `0x116` | `0x115` |
| `R_AARCH64_LDST8_ABS_LO12_NC` | `0x117` | `0x116` |
| `R_AARCH64_TSTBR14` | `0x118` | `0x117` |
| `R_AARCH64_CONDBR19` | `0x119` | `0x118` |

这导致真实的 ADRP relocation 被错误匹配到了 MOVW relocation 分支。

最终出现这样的污染路径：

```
真实 relocation：
  type = 275
  含义 = R_AARCH64_ADR_PREL_PG_HI21

错误匹配：
  type 275 被当成 MOVW_PREL_G0_NC

结果：
  用 MOVW 编码逻辑 patch ADRP 指令
```

于是：

```
原始 ADRP 指令 = 0x90000000
错误 imm       = 0xFF8
错误编码结果   = 0x9001FF00
```

### 解决

严格按照 ARM ELF 规范修正 relocation 常量：

```c
#define R_AARCH64_MOVW_PREL_G0          0x111
#define R_AARCH64_MOVW_PREL_G0_NC       0x112
#define R_AARCH64_ADR_PREL_PG_HI21      0x113
#define R_AARCH64_ADR_PREL_PG_HI21_NC   0x114
#define R_AARCH64_ADD_ABS_LO12_NC       0x115
#define R_AARCH64_LDST8_ABS_LO12_NC     0x116
#define R_AARCH64_TSTBR14               0x117
#define R_AARCH64_CONDBR19              0x118
```

修复后：

```
ADRP: new_insn=b0000000
kpm_test: init called
```

### 教训

ELF relocation type 常量不能凭记忆手写。

必须和权威来源交叉验证，例如：

- ARM ELF ABI
- binutils `include/elf/aarch64.h`
- LLVM AArch64 relocation 定义

一个常量错位，会导致后续多个 relocation 类型互相顶替，症状非常隐蔽。

---

## 坑 27：ET_REL 非 `SHF_ALLOC` 段的 `sh_addr` 必须手动设置

### 现象

重定位引擎处理 `.rela.text` 等 relocation section 时，需要访问：

```c
sechdrs[].sh_addr
```

但对于：

- `.symtab`
- `.strtab`
- `.rela.text`
- `.rela.data`

这些非 `SHF_ALLOC` 段，`sh_addr` 仍然是 0。

结果访问空地址，触发内核 Oops。

### 根因

对于 ET_REL 文件，section header 中的 `sh_addr` 通常是 0。

因为它还没有被最终链接，也没有运行时地址。

内核原生 module loader 会在加载过程中设置 section 的运行时地址。

但自己写 loader 时，这一步需要手动完成。

尤其要注意：

>
> 重定位处理不仅需要访问 `SHF_ALLOC` 段，也需要访问非 `SHF_ALLOC` 的符号表、字符串表和 relocation 表。
>
>
>

例如：

```c
Elf_Sym  *symtab = (Elf_Sym *)sechdrs[symindex].sh_addr;
char     *strtab = (char *)sechdrs[strindex].sh_addr;
Elf_Rela *rela   = (Elf_Rela *)sechdrs[relsec].sh_addr;
```

如果这些 `sh_addr` 没有设置，就会访问 NULL。

### 解决

在 loader setup 阶段，对所有非 `SHF_ALLOC` 段设置 `sh_addr`，让它们指向文件缓冲区中的原始位置：

```c
for (unsigned int i = 0; i < shnum; i++) {
    if (!(info->sechdrs[i].sh_flags & SHF_ALLOC)) {
        info->sechdrs[i].sh_addr =
            (unsigned long)info->hdr + info->sechdrs[i].sh_offset;
    }
}
```

### 教训

ET_REL 文件中的 `sh_addr` 不能直接相信。

自己写 loader 时，非 ALLOC 段也必须拥有一个可访问的内存地址。

否则符号表、字符串表、relocation 表都会在运行时访问失败。

---

## 坑 28：字符串指针转换的 section 偏移陷阱

### 现象

KPM 加载成功，但 `dmesg` 显示：

```
loading module '' version ''
```

模块名和版本号都是空字符串。

但检查 KPM 文件中的 `.kpm.info` 段，字符串明明存在。

### 根因

在 ELF 文件解析阶段，KPM 的元数据指针：

- `name`
- `version`
- `license`

都指向文件缓冲区中的 `.kpm.info` 段。

当 KPM 被搬迁到运行时内存后，需要把这些指针从“文件地址”转换成“运行时地址”。

错误写法是：

```c
mod->info.name = info->name - (const char *)info->hdr + mod->info.base;
```

这个公式的问题是：

>
> 它以整个 ELF 文件头作为基准，而不是以 `.kpm.info` 段起始地址作为基准。
>
>
>

实际数据流类似：

```
info->name      = hdr + section_offset + string_offset
info->hdr       = hdr
mod->info.base  = runtime 中 .kpm.info 段地址
```

错误公式会把 `section_offset` 也加进运行时地址里，导致最终指针偏移过头。

### 解决

必须以 `.kpm.info` 段在文件中的起始地址为基准：

```c
unsigned long info_sec_offset = info->sechdrs[info->info_idx].sh_offset;

const char *info_file_base =
    (const char *)info->hdr + info_sec_offset;

mod->info.name =
    info->name - info_file_base + mod->info.base;

mod->info.version =
    info->version - info_file_base + mod->info.base;

mod->info.license =
    info->license - info_file_base + mod->info.base;
```

### 教训

文件地址转换成运行时地址时，减法基准必须正确。

如果指针指向 section 内部，就必须减去：

```
hdr + section_offset
```

而不是只减去：

```
hdr
```

---

# 第四部分：CFI、BTI 与异构代码边界

## 坑 29：CFI 保护代码调用非 CFI KPM 的边界问题

### 现象

KPM 加载流程全部完成，section 搬迁和 relocation 都正确。

但在调用：

```c
kpm_init()
```

时设备静默重启。

最后一条日志停在：

```
icache flushed, about to call KPM init
```

之后没有更多 dmesg。

### 根因

KPM Loader 自身是用 CFI_ICALL + LTO 编译的。

这意味着 loader 中通过函数指针发起的间接调用，会被编译器插入 CFI 检查。

而 KPM 二进制没有使用相同的 CFI 体系编译。

于是当 loader 调用：

```c
fn(args, event, reserved);
```

时，编译器会插入类型检查：

```
检查目标函数是否拥有匹配的 CFI 类型信息
```

但 KPM 的入口函数没有对应的 CFI 信息，于是触发 CFI failure。

更复杂的是，CFI 问题并不只存在于：

```
loader → KPM
```

这一条路径。

还会存在于：

```
KPM → KPM 内部函数指针
内核 → KPM 注册的回调
KPM thunk / trampoline → 非标准代码页
```

因此，单独处理某一个调用点是不够的。

### 解决

最终方案需要同时覆盖两层：

#### 1. 明确的桥接函数禁用 CFI

对 loader 主动调用 KPM 的入口函数，使用桥接函数，并在桥接函数上关闭 CFI 检查：

```c
__attribute__((no_sanitize("cfi")))
static long call_kpm_init(kpm_initcall_t fn,
                          const char *args,
                          const char *event,
                          void *reserved)
{
    return fn(args, event, reserved);
}

__attribute__((no_sanitize("cfi")))
static long call_kpm_exit(kpm_exitcall_t fn, void *reserved)
{
    return fn(reserved);
}
```

这解决的是：

```
loader → KPM
```

这一条直接调用路径。

#### 2. 对 KPM 可执行区域进行统一登记

对于 KPM 代码区、hook 区、thunk 区、trampoline 区等额外分配的可执行代码页，需要建立统一的区域追踪机制。

抽象逻辑如下：

```c
static bool is_kpm_exec_area(unsigned long addr)
{
    return is_kpm_area(addr)
        || is_hook_area(addr)
        || is_thunk_area(addr)
        || is_trampoline_area(addr);
}
```

最终判断原则是：

>
> 所有非内核原生构建体系生成的可执行代码页，都必须被 loader 明确登记和识别。
>
>
>

这样才能避免某些间接调用路径仍然落回内核 CFI 的默认失败路径。

### 教训

CFI 不是只在“调用入口函数”时才会触发。

只要存在函数指针、回调、trampoline、thunk，就可能进入 CFI 检查路径。

因此 CFI 适配必须从“单点修复”升级为“可执行区域治理”。

---

## 坑 30：KPM 入口函数必须有 BTI 着陆指令

### 现象

CFI 边界处理后，崩溃转移到：

```
kpm_init
```

函数入口。

`pstore` 日志显示：

```
Target Branch Exception
```

### 根因

ARM64 BTI 要求间接跳转目标地址的第一条指令必须是合法的 BTI landing pad。

KPM Loader 通过函数指针调用：

```c
mod->init()
```

这是一个间接调用。

因此 CPU 会检查 `kpm_init` 第一条指令是否为合法 BTI 指令。

如果 KPM 是用普通汇编或未启用 BTI 的编译器选项生成的，那么函数入口没有：

```asm
bti c
```

就会触发 Target Branch Exception。

### 解决

如果 KPM 用汇编写，入口函数需要显式添加 BTI landing pad：

```asm
kpm_init:
    hint #34        // bti c
    stp x29, x30, [sp, #-16]!
    ...

kpm_exit:
    hint #34        // bti c
    stp x29, x30, [sp, #-16]!
    ...
```

如果 KPM 用 C 编写，则使用：

```bash
-mbranch-protection=standard
```

### 教训

只要函数是通过函数指针、回调或 thunk 间接进入的，它就必须满足 BTI 要求。

KPM 是否是“模块内部代码”并不重要。

从 CPU 视角看，它只是一个间接跳转目标。

---

# 第五部分：KPM 运行期资源管理

## 坑 31：`vfree()` 需要原始分配地址

### 现象

释放 thunk 时调用：

```c
vfree(kp_thunk_addrs[idx]);
```

触发内核警告：

```
Trying to vfree() bad address
```

### 根因

thunk 分配时，实际流程类似：

```
mem = vmalloc(PAGE_SIZE)
thunk = mem + 8
kp_thunk_addrs[idx] = thunk
```

这里把 thunk 放在 `mem + 8` 处，是为了避开函数入口前读取 CFI hash 时可能踩到 guard page 的问题。

但 `vfree()` 要求传入的是：

```
vmalloc 返回的原始地址
```

也就是：

```
mem
```

而不是：

```
mem + 8
```

因此直接释放 `thunk` 会被内核认为是非法地址。

### 解决

释放前恢复页起始地址：

```c
void *page =
    (void *)((unsigned long)kp_thunk_addrs[idx] & ~(PAGE_SIZE - 1));

vfree(page);
```

### 教训

`vfree()` 必须接收 vmalloc 返回的原始指针。

任何偏移后的地址都不能直接传给 `vfree()`。

---

## 坑 32：只读内核数据区不能依赖 `set_memory_rw()`

### 现象

对某些内核只读数据区执行写入时，触发：

```
Unable to handle kernel write to read-only memory
```

即使提前调用了：

```c
set_memory_rw()
```

仍然无效。

### 根因

Android GKI 中，一些关键内核数据在初始化后会被标记为：

```
__ro_after_init
```

这类区域通常位于内核自身的 `.data` / `.rodata` 相关映射中。

`set_memory_rw()` 对 vmalloc/module_alloc 这类动态映射区域更有效，但对内核线性映射或初始化后只读区域不一定能生效。

错误流程是：

```
set_memory_rw(target)
  → 实际失败或不适用

直接写 target
  → 触发只读内存写入异常
```

### 解决

对于这类地址，必须使用架构允许的内核 patching 机制，而不是直接写。

在 ARM64 上，常见思路是通过内核提供的指令/文本 patch 接口完成临时可写映射、写入和恢复。

核心原则是：

```
不要假设 set_memory_rw 可以修改所有内核地址。
```

### 教训

`set_memory_rw()` 不是万能写权限开关。

对于 `__ro_after_init` 或内核自身只读映射，直接写入很容易触发 Oops。

---

## 坑 33：页边界函数入口读取 CFI hash 会踩 guard page

### 现象

KPM 中某个函数地址恰好页对齐：

```
0x...000
```

在读取：

```c
*(func - 4)
```

获取 CFI hash 时，触发：

```
do_translation_fault
```

### 根因

vmalloc/module_alloc 区域前后可能存在 guard page。

当函数入口正好位于页起始位置时：

```
func = page_start
func - 4 = previous_page + PAGE_SIZE - 4
```

而前一个页面可能是未映射的 guard page。

于是读取 `func - 4` 会触发页错误。

### 解决

读取函数入口前 4 字节之前，必须检查页内偏移：

```c
if ((func_addr & (PAGE_SIZE - 1)) >= 4) {
    u32 cfi_hash = *(u32 *)(func_addr - 4);
    /*
     * 使用 cfi_hash
     */
}
```

如果函数入口位于页起始位置，就不能直接读取 `func - 4`。

### 教训

读取函数入口前的元数据时，必须考虑页边界。

尤其是 vmalloc/module_alloc 产生的区域，前后 guard page 会让 `addr - 4` 这种访问变得危险。

---

# 第六部分：GOT、外部符号与地址层级

## 坑 34：GOT 双重解引用与函数指针变量的地址层级

### 现象

加载复杂 KPM 时，loader 报错：

```
unsupported RELA type 312
```

后续补上 GOT relocation 支持后，又出现新的崩溃：

```
跳转到 0x7fd503233f
触发 do_translation_fault
```

进一步反汇编发现，KPM 调用外部函数时生成了类似模式：

```asm
adrp x8, :got:symbol
ldr  x8, [x8, #:lo12]
ldr  x8, [x8]
blr  x8
```

也就是说，它不是直接调用 GOT 槽中的地址，而是做了两次解引用。

### 根因一：复杂 KPM 会产生 GOT 重定位

`type 312` 对应 GOT 相关 relocation，例如：

```
R_AARCH64_LD64_GOT_LO12_NC
```

如果 KPM 使用：

```bash
-fPIC
-mcmodel=large
```

编译，就很容易产生 GOT 访问。

因此 loader 必须支持 GOT relocation。

### 根因二：外部符号访问可能是“双重解引用”

对于某些编译模型，KPM 对外部符号的访问不是：

```
GOT 槽 = 函数地址
直接 blr 函数地址
```

而是：

```
GOT 槽 = 某个指针变量的地址
第一次 ldr：取出指针变量地址
第二次 ldr：读取指针变量的值
blr：调用最终函数
```

如果 loader 直接把函数地址填进 GOT 槽，那么第二次 `ldr` 就会把函数开头的机器码当成指针读取。

例如函数开头如果是 PAC 指令：

```
0xd503233f
```

那么读取出来的“地址”就可能变成类似：

```
0x7fd503233f
```

最终跳转到垃圾地址。

### 根因三：符号声明类型决定访问模式

KernelPatch 中有些外部符号被声明为函数指针变量：

```c
extern void (*printk)(const char *fmt, ...);
extern unsigned long (*kallsyms_lookup_name)(const char *name);
```

这和普通函数声明完全不同：

```c
extern void printk(const char *fmt, ...);
```

两者语义区别如下：

| 声明形式 | 编译器理解 | KPM 需要的地址 |
|-|-|-|
| `extern void printk(...)` | `printk` 是函数 | 函数地址 |
| `extern void (*printk)(...)` | `printk` 是函数指针变量 | 函数指针变量自身的地址 |

如果声明是：

```c
extern void (*printk)(const char *fmt, ...);
```

那么 KPM 会生成：

```
先找到 printk 变量地址
再读取变量中的函数地址
最后调用
```

因此 loader 不能把 `printk` 解析成函数地址，而应该提供一个“指针变量”：

```c
static void (*kp_printk_ptr)(const char *fmt, ...);

kp_printk_ptr = printk;

/*
 * 注意：这里传的是变量地址，而不是函数地址。
 */
local_syms[PRINTK_IDX].addr = (unsigned long)&kp_printk_ptr;
```

同理：

```c
static unsigned long (*kp_kallsyms_lookup_name_ptr)(const char *name);

kp_kallsyms_lookup_name_ptr = kp_kallsyms_lookup_name;

local_syms[KALLSYMS_IDX].addr =
    (unsigned long)&kp_kallsyms_lookup_name_ptr;
```

### 解决

loader 需要区分三种地址层级：

| 情况 | 应填入的地址 |
|-|-|
| 普通函数符号 | 函数地址 |
| 函数指针变量符号 | 指针变量自身地址 |
| GOT 双重解引用符号 | 包装槽地址 |

对于需要包装的外部函数，可以分配一层 wrapper slot：

```c
u64 *slot = &wrap_pool[wrap_count++];

*slot = real_func_addr;

/*
 * GOT 槽中放 slot 地址，而不是 real_func_addr。
 */
got_entry = (u64)slot;
```

这样 KPM 的双重解引用链条就成立：

```
GOT entry
  → wrapper slot 地址
    → wrapper slot 中保存真实函数地址
      → BLR 真实函数
```

### 教训

外部符号解析不能只问“这个符号的地址是多少”。

还必须问：

>
> KPM 编译器认为这个符号是什么？
>
>
>

它可能是：

- 一个普通函数
- 一个函数指针变量
- 一个数据对象
- 一个需要 GOT 包装的外部引用

声明类型不同，编译器生成的访问模式完全不同。

loader 必须提供匹配的地址层级。

---

# 第七部分：符号表维护问题

## 坑 35：`local_syms` 表与初始化代码错位

### 现象

KPM 入口函数中第一个：

```c
printk("init args=%s\n", args);
```

就触发崩溃。

反汇编发现：

```asm
ldr x8, [x24]
blr x8
```

但 `x24` 并不是 `printk` 指针变量地址，而是另一个 local symbol 的地址，甚至可能是某个完全无关的 helper 函数。

### 根因

`local_syms[]` 表声明和 `local_syms_init()` 初始化函数是两份平行维护的列表。

表声明类似：

```
index 21 = printk
index 22 = hook_unwrap_remove
index 23 = sp_el0_is_current
...
```

但初始化代码中却写成了：

```c
local_syms[21].addr = (unsigned long)&kp_sp_el0_is_current;
local_syms[22].addr = (unsigned long)&kp_thread_info_in_task;
local_syms[23].addr = (unsigned long)&kp_sp_el0_is_thread_info;
```

从某个索引开始，表项和初始化代码整体错位。

结果就是：

```
KPM 想解析 printk
实际拿到 sp_el0_is_current
```

后续再叠加“函数指针变量地址层级”的问题，就会表现成非常混乱的跳转崩溃。

### 解决

至少要保证表声明和初始化顺序完全一致：

```c
local_syms[21].addr = (unsigned long)&kp_printk_ptr;
local_syms[22].addr = (unsigned long)&kp_hook_unwrap_remove;
local_syms[23].addr = (unsigned long)&kp_sp_el0_is_current;
local_syms[24].addr = (unsigned long)&kp_thread_info_in_task;
local_syms[25].addr = (unsigned long)&kp_sp_el0_is_thread_info;
local_syms[26].addr = (unsigned long)&kp_thread_size;
local_syms[27].addr = (unsigned long)&kp_task_in_thread_info_offset;
```

更好的方式是使用 X-Macro 或集中式表定义，避免声明和初始化分离。

例如：

```c
#define LOCAL_SYM_TABLE(X)                 \
    X(printk,                &kp_printk_ptr) \
    X(hook_unwrap_remove,    kp_hook_unwrap_remove) \
    X(sp_el0_is_current,     kp_sp_el0_is_current) \
    X(thread_info_in_task,   kp_thread_info_in_task)
```

然后用同一张表同时生成：

- 符号名数组
- 地址初始化代码
- 调试输出
- 索引枚举

### 教训

平行维护的列表是 bug 温床。

只要中间插入或删除一次元素，就可能造成后续所有索引整体错位。

符号表这种核心数据结构，必须尽量做到：

```
单一事实来源
```

---

# 本篇总结

经过整理后，KPM Loader 的核心坑从原始记录中的第 21 到第 39 坑，收敛为第 21 到第 35 坑。

这些问题可以归纳为六类。

---

## 1. 运行时基础环境

### 坑 21：KASLR 地址时效性

KASLR 地址只在单次启动周期内有效。

设备一旦重启，所有 kallsyms 地址都必须重新获取。

### 坑 22：十六进制解析的 `0x` 前缀

内核地址字符串通常带 `0x` 前缀。

自写 parser 必须显式处理，否则很容易把地址解析成 0。

---

## 2. 内存管理与权限切换

### 坑 23：`module_alloc()` 默认不可执行

ARM64 上 `module_alloc()` 通常返回 RW / NX 内存。

不能直接执行，必须后续切换权限。

### 坑 24：WXN 写入时序

所有 patching 必须在 RW 阶段完成。

切换到 RX 后，不应继续修改 `.text`。

### 坑 25：GKI 符号可见性

GKI 不保证导出 loader 所需的核心符号。

`module_alloc`、`set_memory_x`、`flush_icache` 等往往需要通过 kallsyms 间接解析。

---

## 3. 重定位引擎

### 坑 26：AArch64 relocation 常量错位

一个 relocation type 数字写错，会导致多个 relocation 分支互相顶替。

症状可能表现为字符串乱码、ADRP 错跳、远距离随机访问。

### 坑 27：非 ALLOC 段 `sh_addr`

`.symtab`、`.strtab`、`.rela.*` 这些非 ALLOC 段也必须有有效 `sh_addr`。

否则 relocation 阶段会访问 NULL。

### 坑 28：字符串指针转换基准

section 内部指针转运行时地址时，必须以 section 起始地址为基准，而不是 ELF 文件头。

---

## 4. CFI / BTI 边界

### 坑 29：CFI 异构调用边界

CFI 编译的 loader 调用非同体系 KPM 时，需要桥接函数和统一的可执行区域治理。

单点 `no_sanitize("cfi")` 不够，必须覆盖 KPM、hook、thunk、trampoline 等所有额外代码页。

### 坑 30：BTI landing pad

所有被间接调用的 KPM 函数入口都必须有 `bti c`。

汇编写 KPM 时要手动加；C 写 KPM 时应启用对应编译选项。

---

## 5. 运行期资源管理

### 坑 31：`vfree()` 原始地址

`vfree()` 必须传入 `vmalloc()` 返回的原始地址。

偏移后的 thunk 指针不能直接释放。

### 坑 32：只读内核数据区写入

`set_memory_rw()` 不是万能写权限开关。

对于初始化后只读区域，必须使用架构支持的 patching 机制，而不是直接写。

### 坑 33：页边界 CFI hash 读取

读取 `func - 4` 前必须检查页内偏移。

函数入口如果正好页对齐，`func - 4` 可能落入 guard page。

---

## 6. GOT、外部符号与 local symbol 表

### 坑 34：GOT 双重解引用与地址层级

复杂 KPM 会产生 GOT relocation。

外部符号可能需要函数地址、函数指针变量地址或 wrapper slot 地址。

loader 必须根据符号声明类型提供正确层级的地址。

### 坑 35：`local_syms` 表错位

符号表声明和初始化代码不能平行维护。

应使用集中式定义，避免索引错位导致符号解析错乱。

---

# 全系列总结

从第一篇到第三篇，我们走完了“把 `.so` 变成 `.ko`”的完整旅程。

---

## 第一篇：ELF 格式转换

第一篇覆盖坑 1 到坑 13。

核心内容是：

- 用户空间 ELF 与内核模块 ELF 的差异
- section 白名单与黑名单
- `.modinfo` 构造
- `struct module` 处理
- symbol table 修复
- relocation 映射
- x86 Kali 环境下离线转换链路打通

这一阶段解决的是：

>
> 如何把一个用户空间编译产物，在格式上伪装成内核能识别的 `.ko`。
>
>
>

---

## 第二篇：Android GKI 安全特性

第二篇覆盖坑 14 到坑 20。

核心内容是：

- SELinux 对 `insmod` 的拦截
- vermagic 后缀匹配
- ARM64 BTI
- ARM64 PAC
- SCS
- CFI_ICALL 与 kCFI 差异
- mrdump 对非标准 `.text.*` section 的敏感

这一阶段解决的是：

>
> 如何让格式正确的 `.ko` 真正在 ARM64 Android GKI 设备上加载成功。
>
>
>

最终结论是：

- 编译选项必须匹配目标内核安全特性
- CFI 要以参考模块的二进制特征为准
- CFI_ICALL 生成的 `.text.*` 子段需要通过 linker script 合并
- 不能只满足内核 loader，还要兼容厂商驱动对 ELF section 名的假设

---

## 第三篇：自研 KPM Loader

第三篇，也就是本文，覆盖整理后的坑 21 到坑 35。

核心内容是：

- KASLR 与 kallsyms 地址时效性
- 运行时符号解析
- ARM64 module memory 权限
- RW / RX 分阶段切换
- AArch64 relocation 引擎
- GOT 与外部符号包装
- CFI / BTI 异构边界
- thunk / trampoline 资源管理
- local symbol 表维护

这一阶段解决的是：

>
> 如何在内核空间实现一个迷你模块加载器，让目标设备能够在运行时加载、重定位并执行受控 KPM 二进制。
>
>
>

---

# 结语

这三篇文章看似是在讲“把 `.so` 变成 `.ko`”，但真正贯穿其中的主题其实是：

>
> 当你试图绕开成熟的内核构建与加载体系时，原本被工具链、内核 loader、链接器和架构代码替你处理掉的细节，会一个不漏地回到你面前。
>
>
>

ELF 格式只是第一层。

真正困难的是：

- 架构安全特性
- 内核符号可见性
- relocation 语义
- 内存权限模型
- CFI / BTI / PAC 边界
- 厂商驱动假设
- 编译器生成代码模式
- loader 自身的数据结构一致性

内核开发的残酷在于，它很少给你清晰的错误提示。

很多时候，一个 relocation 常量写错、一个地址多解引用一次、一个函数入口少了 `bti c`，最终表现出来的都只是：

```
静默重启
Instruction Abort
Translation Fault
Kernel panic
```

但也正因如此，每一次踩坑都格外有价值。

希望这个系列能帮助同样在 ARM64 Android GKI 设备上做内核开发、调试和研究的人，少走一些弯路。

**全系列完。**

---

# 回复

## 回复 by 孤木落 (#2)

*2026-5-4 15:05*

这三篇文章写完之后，实现的成果主要有两个:
1. 一套只使用ndk的跨版本兼容内核模块开发框架
2. 一个可跨版本兼容的kpm加载器(作为kernel su元模块使用)，不需要patch内核，可在越狱模式的设备上使用

## 回复 by 孤木落 (#3)

*2026-5-4 15:07*

本篇中加载器设计主要参考安卓内核自己的模块加载器和kernel patch的kpm加载器
坑点全部出现在仿制加载器的过程之中

## 回复 by iBa0 (#4)

*2026-5-6 14:51*

1

## 回复 by xingbing (#5)

*2026-5-6 16:50*

谢谢分享

## 回复 by Imxz (#6)

*2026-5-8 10:56*

tql

## 回复 by mb_nkjfyhkg (#7)

*2026-5-9 16:23*

mark

## 回复 by mb_fdskejlh (#8)

*2026-5-22 20:29*

牛啊牛啊

## 回复 by tjytjy (#9)

*2026-6-1 15:31*

666

## 回复 by dob_C (#10)

*2026-6-1 17:19*

谢谢分享

## 回复 by 橙_ (#11)

*2026-6-4 16:20*

666

## 回复 by mb_nkgrclmk (#12)

*2026-6-25 18:23*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by ulong9527 (#13)

*2026-6-26 09:48*

感谢分享，学习一下

## 回复 by wx_kx92911 (#14)

*2026-7-15 09:48*

感谢分析

## 回复 by mb_degalzhb (#15)

*2026-7-15 14:41*

666

## 回复 by B.M.K (#16)

*2026-7-15 17:44*

1
