---
title: '[原创]从0到1构建一个Hook工具之PLT Hook篇（四）'
url: https://bbs.kanxue.com/thread-290921.htm
tid: 290921
author: n_1ng
date: '2026-04-21'
tags: [Android安全, 原创, HOOK注入]
crawled_at: '2026-07-31T15:10:08+08:00'
replies: 31
---

## 前言

在前面的几篇文章里，我们已经把注入器和 Java Hook 这两部分大致梳理了一遍。继续往下走，一个比较自然的问题就是：如果目标不再是 Java 方法，而是 so 里的 native 函数，那 Hook 又该怎么做？

Native Hook 这件事如果再往下拆，其实又可以分成几条路。最常见的两类，一类是直接改机器码的 Inline Hook，另一类是利用动态链接过程留下来的导入表/重定位信息做 PLT Hook。相较之下，PLT Hook 更适合作为一个 Native Hook 框架的第一步：它不用上来就硬改目标函数入口，而是优先利用 ELF 和动态链接器已经准备好的信息。

## 目标

这篇文章我们先把目标定在实现一个可用的plt hook demo。项目地址：https://github.com/x1aon1ng/Nook

读完之后，我希望至少能把下面这些问题讲明白：

1. PLT Hook 到底 Hook 的是什么？
2. 一个导入函数在运行时是如何通过 GOT/PLT 被调用的
3. `PLT Hook` 为什么本质上是“改重定位结果”
4. 为什么改一个槽位里的函数指针，就能劫持 native 调用？
5. 一次 `hook_symbol()` 调用在内部究竟经历了哪些步骤？

## 知道这些基础后会更好理解下文

### 1. ELF 与 so

在 Android/Linux 里，native 动态库本质上就是 ELF 文件。`libxxx.so` 被加载进进程后，并不是简单把文件原样搬到内存里，而是由动态链接器按照 ELF 中的 program header、dynamic segment、relocation 信息等内容完成装载和重定位。

如果只从 Hook 的角度去看，ELF 里最重要的几类信息是：

1. 动态符号表 `.dynsym`
2. 动态字符串表 `.dynstr`
3. 重定位表，如 `.rel.plt`、`.rela.plt`、`.rel.dyn`、`.rela.dyn`
4. `PT_LOAD`、`PT_DYNAMIC` 这些 program header
5. SHT：ELF 里除了 Program Header Table，还有一套 Section Header Table，通常简称 SHT，对应着elf的两种描述视角，这里暂时不展开讲，简单理解上面讲的.dynsym、.dynstr都是section，每个section header都描述了一个section的类型、偏移、大小等信息

后面 的 PLT Hook，本质上就是围绕这些信息展开。

### 2.导入函数

导入函数，简单说就是：

当前模块里“要调用，但实现不在自己这个模块里”的函数。 比如 libnative-lib.so 里写了：

```python
  strcmp(a, b);
  malloc(16);
```

如果 strcmp 和 malloc 的实现都不在 libnative-lib.so 自己内部，而是在别的 so 里，比如 libc.so，那对 libnative-lib.so 来说，strcmp、malloc 就是导入函数。

对应的另一边就是导出函数，我理解的概念大概是：如果一个函数定义在某个 so 里，并且它的符号对外可见、能被别的模块链接和调用，那它就是这个 so 的导出函数。

了解这个概念后，我们就可以回答上面的问题：PLT Hook就是在Hook导入函数。

### 3. 动态链接、PLT 和 GOT

当一个 so 调用另一个 so 里的导入函数时，编译器通常不会把调用点直接写成最终的真实地址。原因很简单：编译时还不知道这个函数在目标进程里最终会被映射到哪里。

于是就有了两层非常重要的中间结构：

1. `PLT`，Procedure Linkage Table，可以理解成导入函数调用的跳板
2. `GOT`，Global Offset Table，可以理解成运行时保存目标地址的槽位表

一个很粗略但够用的理解是：

```
调用点
  ->
PLT stub
  ->
GOT 槽位
  ->
真实函数地址
```

一旦动态链接器完成重定位，GOT 里的某个槽位就会被写成对应导入函数的真实地址。此后，调用链就会顺着这个槽位跳到真正的目标函数里。

所以，所谓 `PLT Hook`，从运行时视角看，本质上并不是去改 PLT 机器码，而是去改“PLT/GOT 这条调用链最终依赖的那个槽位里的函数指针”。

所以PLT Hook的本质就是在修改重定位的结果。

### 4. 重定位条目是什么

如果说 GOT 槽位是最终要改的目标，那么 relocation entry 就是“告诉你该改哪里”的索引。

一个重定位条目里，最关键的通常是三个字段：

1. 符号索引，说明这条 relocation 对应哪个导入符号
2. relocation type，说明这条 relocation 属于哪一类修正
3. relocation offset，说明最终要修正的目标位置在哪里

对 `PLT Hook` 来说，最核心的问题其实就是：

1. 先找到目标符号对应的 relocation
2. 再拿到它的 offset
3. 然后把这个 offset 换算成进程里的真实地址
4. 最后在那个地址上把原函数地址替换掉

当地址被替换掉后，自然的就走到了我们的Hook逻辑的，这就是PLT Hook的核心。

### 5. 文件里的 offset 不等于内存里的地址

`ELFIO` 解析的是磁盘上的 ELF 文件，而真正的 Hook 动作发生在已经加载到进程内存中的 so 映像上。文件里的 relocation offset 只是“相对于 ELF 映像布局”的偏移，不是可以直接拿来写内存的真实地址。

所以中间必须经过一步 runtime bias 换算。最常见的一种写法是：

```
slot_address = runtime_bias + relocation_offset
```

而 `runtime_bias` 的求法，通常要结合 `PT_LOAD` 段和运行时模块基址一起算出来：

```c
runtime_bias = runtime_module_base + p_offset - p_vaddr
```

### 6. 为什么要临时 mprotect

GOT/PLT 对应的内存页在运行时往往不是天然可写的，很多时候只有读权限，甚至还会带执行权限。想要在上面改指针，就得先把对应页临时改成可写：

1. 先查当前页权限
2. `mprotect` 成可写
3. 写入 replacement
4. 恢复原来的页权限

### 7. PLT Hook 和 Inline Hook 的区别

这两类 Hook 最大的区别不在“Hook 的函数都是 native 函数”，而在“改的是哪一层”。

`PLT Hook` 改的是导入调用链路上的目标槽位，特点是：

1. 不直接改目标函数机器码
2. 更依赖 ELF 和重定位信息
3. 只能影响经过导入槽位发起的调用

`Inline Hook` 改的是函数入口处的机器码，特点是：

1. 直接劫持目标函数执行流
2. 不依赖导入表
3. 能覆盖的场景更广
4. 但实现难度和风险也更高

## 从一个最小例子理解 PLT Hook

假设有一个目标模块 `libnative-lib.so`，它内部调用了 `strcmp`。编译和链接完成后，运行时这个调用大致会依赖某个 relocation 对应的 GOT 槽位。

一开始，槽位里装的是原始的 `strcmp` 地址：

```
libnative-lib.so
  ->
strcmp 对应的 GOT 槽位
  ->
libc.so:strcmp
```

如果我们把这个槽位改成自己的 `hooked_strcmp`：

```
libnative-lib.so
  ->
strcmp 对应的 GOT 槽位
  ->
hooked_strcmp
```

那么后续只要 `libnative-lib.so` 仍然通过这条导入链路调用 `strcmp`，执行流就会先进到 `hooked_strcmp`。

而如果在改写前，我们先把槽位里原本保存的函数地址读出来存到 `original`，后续在 `hooked_strcmp` 里就还可以继续调用原始 `strcmp`。

## 当前项目中 PLT Hook 的整体结构

先看一下当前项目里和 PLT Hook 相关的目录划分：

```
include/nook/
  NookPltHook.h
  NookNativeHook.h

src/framework/
  NookPltHook.cpp
  NookNativeHook.cpp

src/native_hook/core/
  module_info.cpp
  module_match.cpp
  native_hook_dispatcher.cpp
  runtime_patch.cpp

src/native_hook/plt_hook/
  plt_hook_impl.cpp
  elfio_image_parser.cpp
  elf_reader.cpp
  elf_hash.cpp
```

这几层各自负责的事情大概是：

1. `include/nook/NookPltHook.h`对外暴露 PLT Hook API
2. `src/framework/NookPltHook.cpp`负责参数校验、初始化、策略装配
3. `src/framework/NookNativeHook.cpp`当前只是把 Native Hook 门面转到 Plt Hook
4. `src/native_hook/core`放模块定位、路径匹配、通用调度、内存 patch
5. `src/native_hook/plt_hook`放 ELF 元数据解析

## 一次 PLT Hook 调用链

先把整条调用链串起来，再分别讲细节。一次 `hook_symbol()` 大致会经历下面这些步骤，这只是针对当前项目，一个简单的PLT Hook实际并不需要这么复杂：

1. 用户调用 `NookNativeHookHookSymbol()`
2. 它直接转发到 `NookPltHookSymbol()`
3. `NookPltHookSymbol()` 组装依赖并进入统一调度器
4. 调度器通过 `/proc/self/maps` 找到目标模块的运行时基址和磁盘路径
5. 尝试 `ELFIO` 解析主路径
6. 最终定位到某个 relocation 对应的 slot 地址
7. 通过统一的 runtime patch 逻辑改写该地址里的函数指针
8. 同时把原始函数地址保存到 `original`

也就是说，对外看起来只是一个：

```cpp
api.hook_symbol("libnative-lib.so",
                "strcmp",
                reinterpret_cast&lt;void*&gt;(hooked_strcmp),
                &original);
```

但内部实际上完成了“模块定位 -> 文件解析 -> 重定位筛选 -> 地址换算 -> 内存页修改 -> 指针改写”这一整套动作，即：

```
  NookPltHookSymbol
    -> HookSymbolWithFallback
      -> get_module_info
      -> TryPltHookWithElfio
        -> LoadFromFile
        -> ComputeRuntimeBias
        -> CollectRelocationsForSymbol
        -> PatchPointerAtAddress
      -> 失败时 TryPltHookWithElfReader
```

## 对外接口层：NookPltHook 做了什么

先看公开头文件：

```cpp
NookStatus NookPltHookInitialize(void);
NookStatus NookPltHookIsAvailable(int* available);
NookStatus NookPltHookSymbol(const char* module_name,
                             const char* symbol_name,
                             void* replacement,
                             void** original);
```

对外 API 非常薄，真正的核心在 `NookPltHookSymbol()` 里。

它做的事情主要有三类：

1. 参数校验
2. 懒初始化
3. 组装 primary/fallback 依赖

对应代码：

```cpp
NookStatus NookPltHookSymbol(const char* module_name,
                             const char* symbol_name,
                             void* replacement,
                             void** original) {
    if (module_name == nullptr || module_name[0] == '\0' ||
        symbol_name == nullptr || symbol_name[0] == '\0' ||
        replacement == nullptr || original == nullptr) {
        return NOOK_STATUS_INVALID_ARGUMENT;
    }

    *original = nullptr;
    if (!g_plt_hook_initialized) {
        const NookStatus status = NookPltHookInitialize();
        if (status != NOOK_STATUS_OK) {
            return status;
        }
    }

#if defined(__ANDROID__) || defined(__linux__)
    const NookNativeInternal::FallbackHookDependencies dependencies = {
            &ResolveModuleInfo,
            &NookNativeInternal::TryPltHookWithElfio,
            &NookNativeInternal::TryPltHookWithElfReader,
            nullptr};

    return NookNativeInternal::HookSymbolWithFallback(
            module_name, symbol_name, replacement, original, dependencies);
#else
    return NOOK_STATUS_NOT_IMPLEMENTED;
#endif
}
```

可以看到，这一层本身完全不碰 ELF 头、不碰 relocation，也不碰 `mprotect`。它只负责把这次 Hook 需要的策略拼起来，然后把执行权交给内部调度器。

## 模块定位：如何从 /proc/self/maps 找到目标 so

在真正解析 ELF 之前，首先得回答一个问题：目标模块当前在进程里到底被加载到了哪里？这个问题其实在之前的文章中也多次提到，这里再简单讲一下。

当前的做法很传统，也很直接，就是扫描 `/proc/self/maps`。

`get_module_info()` 的核心逻辑可以概括成：

1. 打开 `/proc/self/maps`
2. 逐行读取映射记录
3. 从每一行里解析出起始地址、权限、路径
4. 用 `module_path_matches()` 判断这行是不是目标模块
5. 命中后返回 `map_start` 作为运行时模块基址，同时把路径保存下来

代码逻辑大致如下：

```cpp
while (std::fgets(buffer, sizeof(buffer), maps_file)) {
    if (std::sscanf(buffer,
                    "%lx-%lx %4s %*x %*x:%*x %*d %127s",
                    &map_start,
                    &map_end,
                    perms,
                    so_name) != 4) {
        continue;
    }

    if (!module_path_matches(so_name, module)) {
        continue;
    }

    *module_base = reinterpret_cast&lt;void*&gt;(map_start);
    *module_path = so_name;
    return true;
}
```

## 主路径一：ELFIO 负责解决什么问题

到了这一步，我们已经拿到了两份非常关键的信息：

1. 运行时视角下的 `module_base`
2. 文件视角下的 `module_path`

接下来 `ELFIO` 路径要解决的问题就比较纯粹了：只从磁盘上的 ELF 文件里，把“这个符号对应哪些 relocation”找出来。

`ElfioImageParser` 负责的事情大致可以拆成三件：

1. 从 `.dynsym` 找到目标符号的动态符号索引
2. 遍历所有 `SHT_REL/SHT_RELA` section，找出引用该符号的 relocation
3. 从首个 `PT_LOAD` 段计算 runtime bias

### 1. 查找动态符号索引

它会先拿到 `.dynsym`，然后逐项遍历：

```cpp
ELFIO::section* dynsym = elf_file_.sections[".dynsym"];
ELFIO::symbol_section_accessor symbols(elf_file_, dynsym);

for (ELFIO::Elf_Xword index = 0; index < symbols.get_symbols_num(); ++index) {
    if (!symbols.get_symbol(index,
                            current_name,
                            value,
                            size,
                            bind,
                            type,
                            section_index,
                            other)) {
        continue;
    }
    if (current_name == symbol_name) {
        *symbol_index = static_cast<uint32_t>(index);
        return true;
    }
}
```

一旦拿到 `symbol_index`，后面的 relocation 过滤就有了抓手。

### 2. 收集该符号对应的 relocation

`CollectRelocationsForSymbol()` 不会只盯 `.plt` 相关段，而是会遍历所有 `SHT_REL/SHT_RELA` section：

```cpp
for (const auto& section : elf_file_.sections) {
    const ELFIO::section* current_section = section.get();
    const ELFIO::Elf_Word section_type = current_section->get_type();
    if (section_type != ELFIO::SHT_REL && section_type != ELFIO::SHT_RELA) {
        continue;
    }

    ELFIO::relocation_section_accessor reloc_accessor(elf_file_,
                                                      const_cast&lt;ELFIO::section*&gt;(current_section));
    ...
}
```

然后只保留 `relocation_symbol == symbol_index` 的那些条目，并把 offset、type、section_name 等信息记录下来。

这一点很重要：虽然我们习惯把这类方案叫 `PLT Hook`，但 `Nook` 当前的主路径实现并不只看 `.plt`，而是把引用该符号的 relocation 全部纳入候选。这使它既能覆盖典型 `JUMP_SLOT` 场景，也能覆盖部分 `.dyn` 里的全局数据/函数槽位场景。

### 3. 计算 runtime bias

有了 relocation offset 还不够，因为这依然只是文件视角下的偏移。`ComputeRuntimeBias()` 会遍历 program header，找到首个 `PT_LOAD` 段：

```cpp
for (const auto& segment : elf_file_.segments) {
    if (!segment || segment->get_type() != ELFIO::PT_LOAD) {
        continue;
    }

    *runtime_bias = runtime_module_base +
                    static_cast<uintptr_t>(segment->get_offset()) -
                    static_cast<uintptr_t>(segment->get_virtual_address());
    return true;
}
```

这个式子的含义其实就是：把“文件内偏移体系”平移到“当前进程的运行时映像体系”里去。

## 主路径二：如何把 relocation offset 变成真实可 patch 地址

当 `ElfioImageParser` 把数据都准备好之后，`TryPltHookWithElfio()` 就只剩下最后几步：

1. 加载 ELF 文件
2. 计算 runtime bias
3. 收集目标符号的 relocation 列表
4. 依次尝试 patch 每一个候选 relocation 对应的 slot 地址

核心逻辑：

```cpp
std::vector&lt;ElfHooker::ParsedRelocation&gt; relocations;
if (!parser.CollectRelocationsForSymbol(target.symbol_name, &relocations)) {
    return false;
}

for (const auto& relocation : relocations) {
    void* slot_address = reinterpret_cast&lt;void*&gt;(runtime_bias + relocation.offset);
    if (ElfHooker::PatchPointerAtAddress(slot_address, target.replacement, target.original)) {
        return true;
    }
}
```

可以看到，这里并没有再去关心这个 relocation 来自 `.rel.plt` 还是 `.rela.dyn`，也没有继续纠缠 ELF 头结构。它只做了一件事：把“文件中的 relocation offset”换算成“进程中的 slot 地址”，然后交给统一 patch 层去改。

从分层上看，这一点是 当前实现里最清晰也最舒服的地方：

1. `ELFIO` 只负责元数据提取
2. runtime patch 只负责内存改写
3. 两者之间通过 `relocation.offset` 和 `runtime_bias` 对接

## 运行时 patch：真正改写 GOT/PLT 槽位时发生了什么

如果说前面几节解决的是“该改哪里”，那么这一节解决的就是“怎么安全地改”。

`runtime_patch.cpp` 里主要有三块逻辑：

1. relocation 匹配辅助
2. 跨页 patch 范围计算
3. 真正的指针改写

### 1. 先保存原指针，再写新指针

这一步最核心的逻辑其实就两句：

```cpp
*original = *slot;
*slot = replacement;
```

但这两句的语义很关键。`original` 保存的不是“从符号表重新解析出来的函数地址”，而是“这个 GOT/PLT 槽位在被改写之前，原本指向的那个真实目标地址”。这正是后续 Hook 函数继续调用原函数时最需要的值。

### 2. 为什么要计算跨页范围

如果 patch 地址恰好落在页尾，`sizeof(void*)` 的写入完全可能跨越两页。为了避免只改了一半或 `mprotect` 范围不够，`ComputePatchPageRange()` 会先算好完整范围：

```cpp
const uintptr_t start = target_address & page_mask;
const uintptr_t end = (target_address + write_size - 1u) & page_mask;

range.start = start;
range.length = (end - start) + page_size;
```

### 3. 真正的 PatchPointerAtAddress

`PatchPointerAtAddress()` 的完整思路是：

1. 查询 slot 当前所在页的原始权限
2. 生成一个“去掉执行、补上写权限”的临时权限
3. `mprotect` 使该范围可写
4. 先保存原指针，再写入 replacement
5. 清理 cache
6. 恢复原始页权限

对应代码大致如下：

```cpp
int original_protection = 0;
if (!get_address_protection(slot_address, &original_protection)) {
    return false;
}

int writable_protection = original_protection & ~PROT_EXEC;
writable_protection |= PROT_WRITE;

if (mprotect(page_start, patch_range.length, writable_protection) != 0) {
    return false;
}

const bool wrote_pointer =
        CaptureAndWritePointer(reinterpret_cast&lt;void**&gt;(slot_address), replacement, original);
clear_cache(page_start, patch_range.length);
const int restore_result = mprotect(page_start, patch_range.length, original_protection);
return wrote_pointer && restore_result == 0;
```

这部分逻辑其实就是整套 PLT Hook 的生效的关键：把对应的地址里的指针改掉，跳到我们自己的逻辑。

## ElfReader 是怎么工作的

前面讲的都是当前 `Nook` 里优先走的 `ELFIO` 主路径， 当前的做法是保留一条手写 ElfReader路径作为 fallback，这样一来：

1. 主路径失败时还有兜底
2. 新老实现可以在同一个公开 API 下共存
3. 重构过程中可以降低一次性切换的风险

这条 fallback 路径和 `ELFIO` 最大的区别在于：它不是“先抽取元数据，再交给外层 patch”，而是自己把解析、查找和改写串成了一整条链。

其实实现是类似的，两条路径不同在于：

1. `ELFIO` 路径更像“文件解析层 + 公共 runtime patch 层”
2. `ElfReader` 路径更像“项目内置的一体化兼容实现”

代码参考了：https://github.com/MelonWXD/ELFHooker

### 1. 它解析的不是磁盘文件，而是内存中的已加载映像

`ELFIO` 主路径拿到的是 `module_path`，然后去读磁盘上的 ELF 文件；而 `ElfReader` 构造时直接拿到的是模块运行时基址：

```cpp
ElfReader reader(target.module_name, target.module_base);
if (reader.parse() != 0) {
    return false;
}
return reader.hook(target.symbol_name, target.replacement, target.original) == 0;
```

这意味着它面对的是“当前进程里已经映射好的 ELF 映像”，所以很多字段都不再是文件偏移意义上的概念，而是直接围绕运行时内存布局来做解释。

### 2. 先校验 ELF 头，再找 program header 和 dynamic segment

`parse()` 的入口逻辑大致是：

1. 把 `start` 当作 ELF header 起点
2. 校验 magic、位数、endianness、`e_machine`
3. 解析 program header
4. 找到首个 `PT_LOAD` 段算出 `bias`
5. 再进入 `parseDynamicSegment()`

这里的 `bias` 和前面 `ELFIO` 路径里的 `runtime_bias` 本质上解决的是同一类问题，只不过做法更贴近“当前这块内存如何解释成一个已装载 ELF”。

对应代码主干大致如下：

```cpp
this->ehdr = reinterpret_cast&lt;ElfW(Ehdr) *&gt;(this->start);
if (0 != verifyElfHeader()) {
    return -1;
}

this->phdrNum = ehdr->e_phnum;
this->phdr = reinterpret_cast&lt;ElfW(Phdr) *&gt;(this->start + ehdr->e_phoff);
this->bias = getSegmentBaseAddress();
if (0 == this->bias) {
    return -1;
}
if (0 != parseDynamicSegment()) {
    return -1;
}
```

### 3. 它自己解析 dynamic segment 里的关键表

`parseDynamicSegment()` 做的事情，其实就是把后续 Hook 需要的一批关键数据结构先准备出来，包括：

1. `DT_STRTAB` 对应的字符串表
2. `DT_SYMTAB` 对应的符号表
3. `DT_REL/DT_RELA`
4. `DT_JMPREL`
5. `DT_HASH`
6. `DT_GNU_HASH`

也就是说，在 `ElfReader` 这条路径里，符号查找、relocation 扫描这些动作并不依赖外部库，而是完全靠自己把 dynamic segment 中的元数据拆出来。

### 4. 符号查找：自己实现了 ELF hash 和 GNU hash

这一点是 `ElfReader` 和 `ELFIO` 路径差异很大的地方。

在 `ELFIO` 路径里，当前项目的做法是直接遍历 `.dynsym` 去找目标符号；但在 `ElfReader` 里，项目自己实现了两套更传统的符号查找方式：

1. SysV ELF hash
2. GNU hash

如果模块有 `DT_GNU_HASH`，就优先走 GNU hash；否则就回退到 ELF hash。这也是为什么 `plt_hook` 目录下还保留着 `elf_hash.cpp` 和对应头文件。

### 5. relocation 扫描：先扫 pltRel，再扫 rel

`ElfReader::hook()` 的主逻辑：

1. 先通过符号查找拿到目标符号索引 `symidx`
2. 先扫描 `pltRel`
3. 如果没命中，再扫描普通 `rel`
4. 一旦命中，就用 `bias + matched_offset` 算出最终 slot 地址
5. 然后执行 patch

对应代码结构大致是：

```cpp
if (0 == findSymbolByName(func_name, &sym, &symidx)) {
    rel = this->pltRel;
    for (uint32_t i = 0; i < this->pltRelCount; i++) {
        ...
        if (ElfHooker::FindFirstMatchingRelocationOffset(...)) {
            addr = reinterpret_cast&lt;void *&gt;(this->bias + matched_offset);
            if (0 == hookInternally(addr, new_func, old_func)) {
                return 0;
            }
            break;
        }
    }

    rel = this->rel;
    for (uint32_t i = 0; i < this->relCount; i++) {
        ...
    }
}
```

这里也能看出它和 `ELFIO` 路径的风格差异：

1. `ELFIO` 路径是先把 relocation 全部收集出来，再统一尝试 patch
2. `ElfReader` 路径是边扫描、边判断、边计算地址，命中后直接进入改写

### 6. hookInternally：自己的 patch 逻辑

`ElfReader` 不只是负责解析和查找，它内部还有一套自己的 patch 流程，也就是 `hookInternally()`。

它的整体思路和前面公共的 `runtime patch` 很像：

1. 先判断目标地址所在 segment
2. 根据 segment flag 推导原始内存权限
3. 计算跨页范围
4. `mprotect` 使目标页可写
5. 保存原指针并写入 replacement
6. 清理 cache
7. 恢复原始权限

从这里也能看出为什么前面说它是“一体化兼容实现”：在这条路径里，解析 ELF、筛选 relocation、计算地址、改写内存，并没有被拆成多个相对独立的内部层，而是更多集中在 `ElfReader` 这一个类附近完成。

### 7. 为什么现在还要保留它

写到这里，其实就很容易回答一个问题：既然已经有了 `ELFIO` 主路径，为什么不把 `ElfReader` 删掉？

我觉得至少有下面几个原因：

1. 它仍然是一个稳定可用的 fallback
2. 它可以作为新路径行为的参照
3. 某些解析失败场景下，它可能仍然能工作
4. 重构阶段保留旧路径，比一次性切干净更稳妥

所以从当前 `Nook` 的实现定位看，`ElfReader` 更像是一条兼容和兜底路径，而不是未来主要继续扩展复杂度的方向。

## 一个完整示例：以 strcmp Hook 为例

项目里已经有一个比较直接的例子：`examples/native_hook/nook_native_strcmp_test/payload.cpp`。

这份 payload 的逻辑不复杂，但很适合把前面的原理串起来：

1. 先通过运行时 loader 解析出 `NookNativeApi`
2. 调 `initialize()`
3. 重试调用 `hook_symbol("libnative-lib.so", "strcmp", hooked_strcmp, &original)`
4. 成功后把返回的原始函数地址保存到全局变量里

核心代码大致是：

```cpp
const NookStatus hook_status = api.hook_symbol(kTargetModule,
                                               kTargetSymbol,
                                               reinterpret_cast&lt;void*&gt;(hooked_strcmp),
                                               &original);
if (hook_status == NOOK_STATUS_OK) {
    g_original_strcmp = reinterpret_cast&lt;int (*)(const char*, const char*)&gt;(original);
    g_hook_installed.store(true);
}
```

而真正的 Hook 函数只是：

```cpp
int hooked_strcmp(const char* a, const char* b) {
    __android_log_print(ANDROID_LOG_INFO,
                        kTag,
                        "hooked strcmp: a=%s b=%s",
                        a ? a : "&lt;null&gt;",
                        b ? b : "&lt;null&gt;");
    return NookTestAlwaysEqualStrcmp(a, b);
}
```

表面上看，这只是一次普通的函数替换；但放回 `Nook` 内部实现链路中，它实际已经隐含触发了：

1. `libnative-lib.so` 运行时定位
2. `strcmp` 动态符号索引查找
3. relocation 枚举和筛选
4. runtime bias 计算
5. GOT/PLT 槽位改写
6. 原函数地址保存

这也是为什么我觉得 PLT Hook 很适合作为 Native Hook 框架的第一步：对外接口很简洁，但内部已经把一条完整的 Hook 基础设施链路跑通了。

## 这套实现的边界与局限

虽然当前 `Nook` 里的 PLT Hook 已经够用，但它也有非常明确的边界。

### 1. 它只能 Hook 经过导入表的调用

如果目标调用根本没有经过导入槽位，而是：

1. 模块内部直接调用
2. 静态函数
3. 编译器直接内联
4. 调用点已经被其他优化改写

那么 PLT Hook 是无能为力的。因为它的切入点从来都不是“目标函数入口”，而是“导入链路上的重定位结果”。

### 2. 模块名匹配比较宽松

当前 `module_path_matches()` 支持子串匹配，这使使用体验更宽容，但也意味着如果进程里存在名字很像的 so，理论上会有误命中风险。

### 3. 文件视角和运行时视角必须严格对齐

`ELFIO` 路径读的是磁盘文件，patch 的是进程内存。如果 runtime bias 算错，最后 patch 的就不是目标槽位，而是一个错误地址。这也是整个实现里最不允许出错的换算步骤之一。

## 小结

到这里，其实可以把 `Nook` 当前的 PLT Hook 核心思路压缩成一句话：

`Nook` 的 PLT Hook，本质上就是“先利用 ELF 元数据定位目标符号对应的重定位槽位，再把该槽位在运行时映像中的真实地址安全改写成 replacement，同时保留原始目标地址供后续继续调用”。

如果再拆细一点，这套实现可以被理解成四层：

1. 公开 API 层负责暴露 `hook_symbol()` 能力
2. 调度与模块定位层负责找到目标模块的运行时基址和磁盘路径
3. ELF 元数据解析层负责找到目标符号对应的 relocation
4. 运行时 patch 层负责真正改写 GOT/PLT 槽位

我觉得 `Nook` 当前这部分实现最值得记录的，并不是“PLT Hook 这个概念本身有多新”，而是它把原本容易耦合在一起的几件事尽量拆开了：

1. 文件解析归文件解析
2. 运行时写内存归运行时写内存
3. 对外 API 归对外 API
4. 新实现和旧实现可以在一个稳定入口下并存

这让整套 Native Hook 基础设施在演进时更容易控制风险，也更容易继续往 `Inline Hook` 那一侧扩展。

下一篇继续写 Native Hook，我会尝试顺着这个方向把 `Inline Hook` 接上：同样是 Hook native 函数，为什么到了 Inline Hook 这里，问题会从“找 relocation 和改槽位”变成“改机器码、搬运指令和构造 trampoline”。

---

# 回复

## 回复 by xingbing (#2)

*2026-4-22 15:51*

学习。

## 回复 by 温泉划水鱼 (#3)

*2026-4-24 11:54*

感谢分享！

## 回复 by 拍拖 (#4)

*2026-4-26 11:49*

感谢分享

## 回复 by wx_插曲 (#5)

*2026-4-26 12:34*

66

## 回复 by iBa0 (#6)

*2026-4-27 11:10*

1

## 回复 by Zzzr (#7)

*2026-4-28 14:26*

学习。

## 回复 by Zzzr (#8)

*2026-4-28 14:26*

学习。

## 回复 by GEKEZYX (#9)

*2026-4-30 01:27*

666

## 回复 by GEKEZYX (#10)

*2026-4-30 01:27*

666

## 回复 by GEKEZYX (#11)

*2026-4-30 01:27*

666

## 回复 by GEKEZYX (#12)

*2026-4-30 01:28*

6666

## 回复 by mb_xbsbbedj (#13)

*2026-4-30 02:30*

66666666666

## 回复 by wx_coddvccwyh (#14)

*2026-4-30 23:45*

6666

## 回复 by mb_ckanaznr (#15)

*2026-5-1 03:44*

6666

## 回复 by uni7corn (#16)

*2026-5-2 15:33*

6666

## 回复 by Xx_gg (#17)

*2026-5-6 09:08*

6666

## 回复 by SomeMx (#18)

*2026-5-6 09:12*

学习

## 回复 by wx_北极星_493 (#19)

*2026-5-7 16:06*

看看

## 回复 by 周凡_693405 (#20)

*2026-5-12 17:08*

6666

## 回复 by 末日大哥 (#21)

*2026-5-12 17:09*

666学习一下

## 回复 by wx_Huber Barrientos (#22)

*2026-5-17 00:06*

感谢分享

## 回复 by merryfish (#23)

*2026-5-19 02:34*

nice

## 回复 by git_94327axixa518 (#24)

*2026-5-28 19:14*

666

## 回复 by mb_kgneopde (#25)

*2026-6-12 17:21*

6666

## 回复 by wx_从现在开始 (#26)

*2026-6-12 17:30*

感觉有点AI啊。。。![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by n_1ng (#27)

*2026-6-12 17:57*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  wx_从现在开始](https://bbs.kanxue.com/user-790427.htm)
>  感觉有点AI啊。。。[em_004]
>

哈哈，这个项目很大一部分就是vibe coding的产物

## 回复 by ulong9527 (#28)

*2026-6-26 09:52*

感谢分享，学习一下

## 回复 by 5234c (#29)

*2026-6-29 14:35*

观赏

## 回复 by ~时光荏苒 (#30)

*2026-7-1 21:38*

66

## 回复 by wx_kx92911 (#31)

*2026-7-15 10:08*

感谢分析

## 回复 by mb_degalzhb (#32)

*2026-7-15 14:48*

666
