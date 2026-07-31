---
title: '[原创]Android从ELF-Loader到自定义Linker的实现及原理'
url: https://bbs.kanxue.com/thread-290643.htm
tid: 290643
author: 东方玻璃
date: '2026-04-04'
tags: [Android安全, 原创, 基础理论, NDK分析, 混淆加固, 系统相关, 源码框架]
crawled_at: '2026-07-31T15:11:59+08:00'
replies: 110
---

# 0x0 前言

本文为完善旧坑所作, 学习ELF文件结构后, 实现了解析器和加载器, 当初便想实现自定义Linker, 无奈碰到抽象bug暂时弃坑, 断断续续尝试几次终于解决bug成功跑通 之后让AI重构屎山代码, 更加清晰易懂, 遂填坑

Push AI一把嗦固然非常爽, 但我个人的体验往往是脑中空空, 学得快忘得快, 印象不深, 长此以往容易让人浮躁, 知识消化吸收不良

最后, 希望给学习相关知识点的师傅一些帮助, 同师傅们静下心学习底层原理

阅读本文的正确姿势:

1. 自定义Linker概述, 大概了解本文的目的, 要做什么
2. ELF文件结构, 学习ELF文件理论基础
3. ELF Loader, 学习ELF可执行程序加载器的原理及实现
4. Custom Linker, 学习自定义Linker的原理及实现
5. Android Linker 源码阅读, 深入了解安卓系统Linker的工作流程

本文分为以下部分:

1. **ELF文件结构**

ELF文件相关理论基础快速入门
2. **Linker概述**

系统Linker的工作流程简介 + 自定义Linker的概述
3. **ELF Loader**

一个简单的ELF可执行程序加载器, 用于辅助理解自定义Linker核心流程
4. **Custom Linker**

将ELF Loader迁移到Android平台, 手搓自定义Linker
5. **Custom Linker Test**

自定义Linker效果测试, 匿名内存模块扫描脚本, 抹去ELF关键信息增加逆向难度
6. **Linker源码阅读分析**

从Android 4.4和Android 10源码深入Android系统linker内部流程
7. **参考及推荐资料**

学习自定义Linker期间参考的资料, 以及部分推荐资料

附件:

- ELF-Loader

ELF Loader源码
- SelfDefineLoader

自定义Linker源码项目
- scan_hidden_modules.js

匿名内存模块frida扫描脚本
- DumpedSO

测试自定义Linker时dump出的SO
- SoFixer

小风编译的修复版[SoFixer](https://github.com/LunFengChen/SoFixer)

环境:

- Windows 10
- Pixel AOSP10
- IDA Pro 9.3
- 010 editor 15.0.1
- frida 16.1.4
- Android Studio 2025.3.2
- Kali Linux 2023.4 amd64

声明:

- 本文部分内容使用AI辅助, 文章整体经人工打磨过, 如有错漏还请见谅
- 本文实现的自定义Linker仅供学习相关原理使用, 存在诸多bug并不完备

# 0x1 ELF 文件结构

在学习自定义linker前, 先过一遍ELF文件结构相关知识点

Linux 的一个 .so 或可执行文件本质上是 ELF(Executable and Linkable Format) 文件

ELF文件结构解析和加载器实现可以参考本人之前的一篇文章: [ELF文件结构浅析-解析器和加载器实现](https://bbs.kanxue.com/thread-284556-1.htm)

## ELF 基本框架

可以将ELF文件分为5大核心块:

1. ELF Header

描述ELF文件核心结构的基本信息, 例如文件类型, 架构, 入口点地址等

并且指定了Program Headers和Section Headers的起始地址以及对应表项数目
2. Program Headers

每个表项描述段(Segment)的基本信息, 包括段的起始地址, 大小, 权限等

供Linker判断segment是否需要加载, 如何加载到内存中
3. Sections / Segments

节 Section 是文件视图, 每个节都有其功能, 划分各个节有助于静态分析工具和用户了解ELF文件的细节

段 Segment 是内存视图, Linker加载ELF文件到内存中只需要关注段如何加载, 不需要了解各个节的细节

一个段可以包含多个节, 如果节的权限相同且地址连续便可以视为同一个段方便
4. Dynamic段

Section Headers 中, 为 **.dynamic** 节, Program Headers中, 为 PT_DYNAMIC 段

称之为 dynamic段 更加合适, 因为Linker在加载和链接时非常依赖它的信息

其指向了符号表(导入/导出符号), 重定位表, Hash表(导出表), 依赖库, PLT, GOT, .init, .init_array等结构
5. Section Headers

每个表项描述节(Section)的基本信息, 包括节名, 起始地址, 大小等

通常位于ELF文件末尾, Linker加载ELF文件时通常不会加载它, 因为运行时并不需要该结构, 但静态分析工具非常需要

ELF文件按照顺序的布局大致如下 (以'.'开头的均为节区, 它们的顺序并非固定, 和编译器生成规则有关):

![image](https://bbs.kanxue.com/upload/attach/202604/968342_YZUP4QX5Q668RJ7.png)

Section和Segment两者的关系:

- 一个Segment可以包含多个Section, 一个Section只属于一个Segment
- 加载器只关心Segment(Program Header), 不需要Section Header
- strip掉Section Header的SO仍然可以正常加载运行, 但会让IDA等逆向工具难以分析

Section和Segment在不同视角下的映射图:

![image](https://bbs.kanxue.com/upload/attach/202604/968342_DW4V9XHSWFMRAWB.png)

IDA显示的segments, 可以发现相同权限的section通常是连续的

即多个相同权限的section可以视为同一个segment

![image](https://bbs.kanxue.com/upload/attach/202604/968342_E72H48KCT3M56PX.png)

## ELF Header

ELF Header位于文件最开头, 64位下固定64字节, 是整个文件的"身份证", 包含:

ELF文件类型, 目标CPU架构, 入口点地址

ELF Header大小, Program / Section Headers的起始地址, 表项大小, 表项数等关键信息

```cpp
typedef struct {
    unsigned char e_ident[16];    // Magic: 0x7f 'E' 'L' 'F' + 类别/字节序/版本
    uint16_t 	e_type;           // 文件类型: ET_EXEC(可执行) / ET_DYN(共享库/PIE)
    uint16_t 	e_machine;        // 目标架构: EM_386 / EM_X86_64 / EM_AARCH64
    uint32_t 	e_version;        // ELF版本
    Elf_Addr 	e_entry;          // 程序入口点虚拟地址 (可执行文件的_start,so通常为0)
    Elf_Off  	e_phoff;          // Program Header 表的文件偏移
    Elf_Off  	e_shoff;          // Section Header 表的文件偏移
    Elf64_Word	e_flags;		  // Processor-specific flags // 无用
      Elf64_Half	e_ehsize;		  // ELF Header 大小
      Elf64_Half	e_phentsize;	  // Program header 表项大小
    uint16_t 	e_phnum;          // Program Header 表项条目数
    Elf64_Half	e_shentsize;	  // Section header 表项大小
    uint16_t 	e_shnum;          // Section Header 表项条目数
    Elf64_Half	e_shstrndx;		  // 节名表在Section Headers中的索引
} Elf64_Ehdr;
```

Linker会首先读取该结构, 校验Magic Number (\x7fELF) 和 CPU架构, 然后从 e_phoff 定位段表

## Section Header

每个Section Header描述一个节的名称、类型、在文件中的位置和大小:

```cpp
typedef struct
{
  Elf64_Word    sh_name;        /* 节区名称（在字符串表中的索引） */
  Elf64_Word    sh_type;        /* 节区类型（如 SHT_PROGBITS, SHT_SYMTAB 等） */
  Elf64_Xword   sh_flags;       /* 节区标志位（如可写 W、分配 A、执行 X） */
  Elf64_Addr    sh_addr;        /* 节区在执行时的虚拟内存地址 */
  Elf64_Off     sh_offset;      /* 节区在文件中的偏移量 */
  Elf64_Xword   sh_size;        /* 节区的字节大小 */
  Elf64_Word    sh_link;        /* 链接到另一个相关节区的索引 */
  Elf64_Word    sh_info;        /* 节区的附加信息（取决于节区类型） */
  Elf64_Xword   sh_addralign;   /* 节区的内存对齐要求（必须是 2 的幂） */
  Elf64_Xword   sh_entsize;     /* 如果节区包含固定大小的表项，则为每项的大小 */
} Elf64_Shdr;
```

一些常见的节区列表汇总如下, 文章后续会讲解这些节区:

| Section | **核心功能与作用** | **备注说明** | sh_type |
|-|-|-|-|
| **动态链接核心** |  |  |  |
| `.dynamic` | **动态链接信息表**。相当于动态链接器的"配置文件"。 | 包含对 `.dynsym`、`.got` 等关键节的索引和依赖的 `.so` 库列表。 | SHT_DYNAMIC |
| **符号相关** |  |  |  |
| `.strtab` | 静态字符串表。存储 `.symtab` 中的字符串。 | 用于链接和调试。 | SHT_STRTAB |
| `.symtab` | **静态符号表**。包含程序所有的符号（包括局部变量）。 | 用于链接和调试，运行时不加载，可被剥离。 | SHT_SYMTAB |
| `.dynstr` | 动态字符串表。存储 `.dynsym` 中符号的名字（字符串）。 | 运行时不可或缺。 | SHT_STRTAB |
| `.dynsym` | **动态符号表**。包含运行时需要动态链接的符号（导入/导出函数和变量）。 | 运行时不可或缺。 | SHT_DYNSYM |
| `.gnu.hash` | 动态符号表的哈希表（GNU 风格）。 | 用于在运行时加速动态链接器查找符号的速度。 | SHT_GNU_HASH |
| **重定位相关** |  |  |  |
| `.rela.dyn` | **数据段的重定位表**。指示动态链接器在加载时如何修改 `.got` 或数据段中的绝对地址。 | 用于全局变量或非延迟绑定的指针。 | SHT_RELA |
| `.rela.plt` | **函数调用的重定位表**。指示如何修改 `.got.plt` 中的地址。 | 专门服务于函数的延迟绑定（Lazy Binding）。 | SHT_RELA |
| **初始化/终止相关** |  |  |  |
| `.init` | 程序的初始化代码。在 `main()` 函数之前执行。 | 通常存放 C++ 的全局对象构造函数等。 | SHT_PROGBITS |
| `.init_array` | 包含指向初始化函数的指针数组。现代编译器多用它替代 `.init` 节。 | `__attribute__((constructor))` 修饰的函数会放在这里。 | SHT_INIT_ARRAY |
| `.fini` | 程序的终止代码。在 `main()` 结束后或调用 `exit()` 时执行。 | 通常存放 C++ 的全局对象析构函数。 | SHT_PROGBITS |
| `.fini_array` | 包含指向终止函数的指针数组。替代 `.fini`。 | `__attribute__((destructor))` 修饰的函数会放在这里。 | SHT_FINI_ARRAY |
| **PLT/GOT相关** |  |  |  |
| `.got` | **全局偏移表**。存放全局变量或强解析函数的绝对地址。 | 下文详述 | SHT_PROGBITS |
| `.plt` | **过程链接表**, 存放可执行代码, 用于**延迟绑定**调用外部函数。 | 下文详述, 例如 printf() 函数调用实际上是call printf@plt | SHT_PROGBITS |
| `.got.plt` | **专门用于 PLT 的全局偏移表**。存放外部函数的绝对地址。 | 下文详述, 例如call printf@plt 后,函数的代码为 jmp *got@plt[printf] | SHT_PROGBITS |
| `.plt.got` | **非延迟绑定的过程链接表**, 存放可执行代码 | 下文详述, 同plt类似, 但已经填充完毕, 不需要延迟绑定 | SHT_PROGBITS |
| **代码/数据相关** |  |  |  |
| `.text` | **代码段**。存放程序主要的机器指令。 | 只读、可执行。 | SHT_PROGBITS |
| `.rodata` | **只读数据段**。存放程序中的常量（如字符串字面量、`const` 变量）。 | 内存属性为只读，修改会导致段错误。 | SHT_PROGBITS |
| `.data` | **已初始化的数据段**。存放赋了初始值的全局变量和静态变量。 | 可读、可写。 | SHT_PROGBITS |
| `.bss` | **未初始化的数据段**。存放未赋初值或初始化为 0 的全局/静态变量。 | 在磁盘文件中不占空间，加载到内存时由系统清零。 | SHT_NOBITS |
| **其他** |  |  |  |
| `.shstrtab` | 节区头部字符串表（Section Header String Table）。 | 存储所有节区名称的字符串（如 ".text", ".data"）。 | SHT_STRTAB |

以上并非所有节区, 一般还会有支持异常处理, 调试器辅助信息等功能的节区

010editor查看Section Headers效果如下

![image](https://bbs.kanxue.com/upload/attach/202604/968342_5DU644RTKYPAMK4.png)

## Program Header

Program Header描述了文件中哪些部分需要映射到内存, 以及映射的属性:

```cpp
typedef struct {
    uint32_t p_type;    // 段类型
    uint32_t p_flags;   // 权限: PF_R(读) | PF_W(写) | PF_X(执行)
    Elf_Off  p_offset;  // 段在文件中的偏移
    Elf_Addr p_vaddr;   // 段在内存中的虚拟地址
    Elf_Addr p_paddr;   // 物理地址(通常忽略)
    uint64_t p_filesz;  // 段在文件中的大小
    uint64_t p_memsz;   // 段在内存中的大小 (≥ p_filesz, 差值部分为BSS)
    uint64_t p_align;   // 对齐要求
} Elf64_Phdr;
```

常见的段类型:

| **宏定义 (Macro)** | **值 (Value)** | **含义说明 (中文注释)** |
|-|-|-|
| `PT_NULL` | `0` | 程序头表项未使用 |
| `PT_LOAD` | `1` | 需要加载到内存的段, 如代码段(R-X)和数据段(RW-) |
| `PT_DYNAMIC` | `2` | 指向dynamic段 |
| `PT_INTERP` | `3` | 指向动态链接器路径(如`/lib/ld-linux.so.2`) |
| `PT_PHDR` | `6` | 指向Program Header Table自身 |

010editor查看Program Headers效果如下, 带有很多辅助信息:

![image](https://bbs.kanxue.com/upload/attach/202604/968342_9FZN6SKKPJYF7NU.png)

Linker加载ELF文件时, 会遍历所有`PT_LOAD`段, 计算映像大小并分配内存, 将段填充至指定的虚拟地址, 之后设置段权限完成加载

## String Table

ELF文件中有很多字符串,例如段名,变量名等, 由于字符串长度往往不固定,所以使用固定结构描述比较困难

常见做法是将字符串集中起来存放到一张字符串表,然后通过索引查表来引用字符串

字符串表的内部结构极其简单：一块**连续的字节数组**

设计规则：

1. 每个字符串都以空字符 `\0` (NULL) 结尾
2. 表的第 0 个字节永远是 `\0`
3. 一个字符串可以包含另一个字符串

例如，如果有 `"printf\0"`，恰好有个符号叫 `rintf`，那么偏移量向后移动 1 位，就可以复用这段内存

ELF文件中有3种字符串表, 其中 `.dynstr` 最重要:

1. `.shstrtab` 节头字符串表

存储“节区”自身的名字, 例如 `".text"`, `".data"`, `".bss"` 等字符串

非运行时必须, 主要供链接器和静态分析工具（如 `readelf`）解析文件结构时使用
2. `.strtab` 静态字符串表

存储“静态符号”的名字, 包含了代码中所有的函数名, 全局变量名，用于调试的局部变量名和源文件名称

非运行时必须, 用于静态链接和调试。为了减小文件体积，发布前常使用 `strip` 命令将其剥离
3. `.dynstr` 动态字符串表

存储“动态链接”所需的名字: 1. 动态符号名(导入/导出函数和变量) 2. 依赖的外部共享库名称如 "libc.so.6"

**运行时必须**, 它是linker在运行时寻找外部函数、加载依赖库的符号名称来源,不可剥离。

010editor查看`.dynstr`效果如下:![image](https://bbs.kanxue.com/upload/attach/202604/968342_F6YGXDDKETA4YQ4.png)

## Symbol Table

符号表记录了ELF导出和导入的所有符号(函数/全局变量等):

```cpp
typedef struct {
    uint32_t st_name;   // 符号名在字符串表(.dynstr)中的偏移
    uint8_t  st_info;   // 符号类型(函数/数据) + 绑定属性(全局/局部/弱)
    uint8_t  st_other;  // 可见性
    uint16_t st_shndx;  // 所在Section的索引 (SHN_UNDEF=外部符号)
    Elf_Addr st_value;  // 符号的地址(或偏移)
    uint64_t st_size;   // 符号的大小
} Elf64_Sym;
```

通过符号表和对应的字符串表可以得到符号名,符号大小,符号地址等信息

1. `.symtab` 静态符号表

存储文件中的所有符号，包括局部函数、静态变量、调试信息等

非运行时必须，主要用于静态链接和调试(如 `gdb` 解析函数名),与 `.strtab` 一样，发布前常被 `strip` 剥离
2. `.dynsym` 动态符号表

仅存储动态链接所需的符号：导入/导出的外部函数/变量

**运行时必须**，它是Linker解析外部依赖的符号来源，不可剥离

值得一提的是符号表中`st_name`存的不是字符串本身, 而是一个偏移量, 实际的函数名/变量名存在**字符串表(`.dynstr`)**中

查找符号名时: symbolName = dynstr[sym.st_name]

例如该样本中, strTableAddr = 0xA28, sym.st_name = 0x2F

所以 sym_name_off = 0xA28+0x2F = 0xA57 , 即 strTable[0xA57] = "memcpy\0"

![image](https://bbs.kanxue.com/upload/attach/202604/968342_FA73AE6GYYRACZZ.png)

## Dynamic Table

Dynamic Table 是动态链接的核心"索引目录", 它是一个`Elf_Dyn`数组, 每个元素是一个`(tag, value)`键值对:

```cpp
typedef struct {
    Elf_Sxword d_tag;    // 标签类型
    union {
        Elf_Xword d_val; // 整数值(如大小)
        Elf_Addr  d_ptr; // 地址值(如表的虚拟地址)
    } d_un;
} Elf64_Dyn;
```

Linker遍历Program Headers, 通过`PT_DYNAMIC`段属性找到dynamic table, 然后遍历提取所有需要的信息

常见d_tag标志含义及对应d_un作用如下:

| d_tag | 含义 | d_un |
|-|-|-|
| **依赖库相关** |  |  |
| `DT_NEEDED` | 依赖的共享库名 | `.dynstr`中的偏移 |
| `DT_SONAME` | 本共享库的名称 | `.dynstr`中的偏移 |
| `DT_RPATH` / `DT_RUNPATH` | 运行时库搜索路径 | `.dynstr`中的偏移 |
| **导入/导出符号相关** |  |  |
| `DT_STRTAB` | 动态字符串表地址 | `.dynstr` |
| `DT_STRSZ` | 动态字符串表大小 | 字节数 |
| `DT_SYMTAB` | 动态符号表地址 | `.dynsym` |
| `DT_HASH` / `DT_GNU_HASH` | SysV / GNU Hash表地址 | `.hash` / `.gnu.hash` |
| **重定位相关** |  |  |
| `DT_PLTREL` | PLT重定位表项类型，值为DT_RELA或DT_REL | 枚举值 |
| `DT_RELA` / `DT_REL` | 重定位表地址 | `.rela.dyn` / `.rel.dyn` |
| `DT_RELASZ` / `DT_RELSZ` | 重定位表大小 | 字节数 |
| `DT_JMPREL` | PLT重定位表地址 | `.rela.plt` / `.rel.plt` |
| `DT_PLTRELSZ` | PLT重定位表大小 | 字节数 |
| **初始化/终止相关** |  |  |
| `DT_INIT` | 全局初始化函数地址 | `.init` |
| `DT_INIT_ARRAY` | 构造函数数组地址 | `.init_array` |
| `DT_INIT_ARRAYSZ` | 构造函数数组大小 | 字节数 |
| `DT_FINI` | 全局终止函数地址 | `.fini` |
| `DT_FINI_ARRAY` | 析构函数数组地址 | `.fini_array` |
| `DT_FINI_ARRAYSZ` | 析构函数数组大小 | 字节数 |

后续ELF Loader和自定义Linker会使用到其中大部分tag, 有一部分并不需要使用

010editor查看Dynamic Segment效果如下

![image](https://bbs.kanxue.com/upload/attach/202604/968342_PH24YX3UYXFRMVX.png)

## Relocation Table

重定位表告诉Linker 哪些位置需要重定位, 如何重定位修复, 有2种常见格式:

**Rel** (32位常用, 无显式addend):

```cpp
typedef struct {
    Elf32_Addr r_offset;  // 需要修正的位置
    uint32_t   r_info;    // 高位=符号索引, 低位=重定位类型
} Elf32_Rel;
// addend隐含在r_offset指向的原始值中
```

**Rela** (64位常用, 带显式addend):

```cpp
typedef struct {
    Elf64_Addr  r_offset;  // 需要修正的位置
    uint64_t    r_info;    // 高32位=符号索引, 低32位=重定位类型
    int64_t     r_addend;  // 附加值
} Elf64_Rela;
```

有2张重定位表需要处理:

- **`.rela.dyn`** (DT_RELA / DT_REL) 数据段中的地址引用(全局变量指针等)
- **`.rela.plt`** (DT_JMPREL) PLT跳转表中的函数地址

常见的重定位类型 (不同CPU架构对应枚举不同, 以AArch64为例):

| 类型 | 含义 | 公式 |
|-|-|-|
| `R_AARCH64_RELATIVE` | 基址重定位 | `*target = base + addend` |
| `R_AARCH64_ABS64` | 绝对地址引用 | `*target = sym_addr + addend` |
| `R_AARCH64_GLOB_DAT` | GOT数据项修复 | `*target = sym_addr + addend` |
| `R_AARCH64_JUMP_SLOT` | PLT跳转槽修复 | `*target = sym_addr + addend` |

其中`R_RELATIVE`不涉及外部符号, 不需要查符号表, 其余3种需要先通过符号表解析出符号地址

## Hash Table

Hash表用于快速**按名查找符号**, 避免遍历整个符号表, 实际上承担了 **导出符号表** 的功能

有两种格式:

**SysV Hash**(传统格式, 结构简单):

查找: `hash(name) % nbucket` -> 得到起始索引 -> 沿chain逐个strcmp

```c
typedef struct{
    uint32_t  nbucket;  //bucket的数目
    uint32_t  nchain;  	//chain的数目,和动态符号表的符号数相同
    uint32_t  buckets[];  //nbucket个项的数组
    uint32_t  chains[];   //nchain个项的数组
}SysVHash;
```

**GNU Hash** (现代格式, NDK r23+默认):

查找: Bloom Filter预筛 -> Bucket定位 -> Chain比较

```cpp
typedef struct{
    uint32_t nbucket;
    uint32_t symndx;  		//支持查找index>=symndx的符号, index&lt;symndx的不能直接通过GNU Hash表查找
    uint32_t bloomSize;  	// 布隆过滤器需要的3个数据,用于快速判断某个符号是否查不到
    uint32_t bloomShift;  	//
    ElfW(Addr) blooms[];	// bloomSize个项的数组 32/64位下, 元素大小分别为uint32_t/uint64_t
    uint32_t  buckets[];  	// nbucket个项的数组
    uint32_t  chains[];     // 和符号表索引一一对应, chain的大小等于导出函数个数
}GnuHash;
```

NDK r23+(2021年起) 默认`--hash-style=gnu`, 生成的SO只有`.gnu.hash`没有`.hash`

所以Linker优先使用GNU Hash, 而SysV Hash作为兼容备选

关于Hash Table详细机制比较复杂此处不展开, 先前的文章有详细介绍 [Hash Table (Export Table)](https://bbs.kanxue.com/thread-284556-1.htm#msg_header_h1_10), 兴趣的师傅可以自行学习

## PLT&GOT 相关机制

汇总相关机制如下

| 类型 | 代码跳板 | 地址表 | 填入真实地址时机 | 运行时权限与安全 |
|-|-|-|-|-|
| .plt + .got | .plt | .got | 程序启动时 | 可读可写 |
| .plt + .got.plt | .plt | .got.plt | 第一次被调用时 | 可写 (容易被劫持) |
| .plt.got + .got | .plt.got | .got | 程序启动时 | 只读 (更加安全) |

### .plt & .got

PLT(Procedure Linkage Table) 和 GOT(Global Offset Table) 是实现 **外部函数调用** 的核心机制:

- **GOT** 位于数据段 (RW-)

一个地址数组, 每个外部符号一个槽位, 加载时由linker进行重定位, 填入真实地址

每个元素可以是变量地址, 也可以是函数地址, 即 addr = *GOT[offset]
- **PLT **位于代码段 (R-X)

每个外部函数对应一个PLT跳转存根, 间接通过GOT存储的地址跳转到目标

例如一个ELF程序调用 printf() 函数, 实际流程如下:

```python
     printf()
        │
        ↓
   call printf@PLT          ← PLT: 一小段跳转代码
        │
        ↓
   jmp *GOT[printf]         ← GOT: 存储printf的真实地址
        │
        ↓
   printf() 实际代码         ← libc.so 中的实现
```

核心：`.plt` (跳板代码) + `.got` (可读可写地址表) + Linker 重定位填充地址

很显然, PLT是固定指向GOT的, 但GOT表项可以修改, 方便程序运行时动态加载依赖库的外部函数/变量

前文提到了: .got, .plt, .got.plt, .plt.got 这四张表, 前两张好理解, 后两张是干嘛的呢?

实际上它们都是为了外部函数调用服务的, 只不过使用场景不同:

### .got.plt & 延迟绑定

.got.plt 是专为 **延迟绑定** 服务的全局地址表

为什么要延迟绑定? 当 linker 进行链接时, 会进行重定位并默认填充所有GOT表项

但当程序依赖的外部库函数过多 (如上千个外部函数), 运行却只调用某几个时

显然提前链接这些函数会严重拖慢程序启动运行速度, 所以需要延迟绑定

延迟绑定机制, 外部函数调用流程如下:

第一次调用：触发 Linker 解析函数地址

```python
      printf()
         │
         ↓
    call printf@PLT          ← .plt: 执行跳转代码
         │
         ↓
  jmp *GOT.PLT[printf]       ← .got.plt: 初始状态，回指 .plt 内部
         │
         ↓
 _dl_runtime_resolve()       ← Linker: 查找真实地址，并更新覆写进 .got.plt
         │
         ↓
   printf() 实际代码          ← libc.so
```

第二次及之后的调用：和前文 PLT -> GOT 原理一致

```python
      printf()
         │
         ↓
    call printf@PLT          ← .plt: 执行跳转代码
         │
         ↓
  jmp *GOT.PLT[printf]       ← .got.plt: 此时已存有 printf 的真实地址
         │
         ↓
   printf() 实际代码          ← libc.so
```

核心：`.plt` (跳板代码) + `.got.plt` (可写地址表) + Linker 解析函数真实地址

值得一提的是, Linux ELF程序**默认使用延迟绑定**机制以加快程序运行速度

但不难看出, 为了实现延迟绑定机制, .got.plt 的权限为RW-, 可写则意味着存在被劫持的可能

### .plt.got & 立即绑定

为了封堵 .got.plt 可写的安全漏洞，现代程序支持开启 **完全重定位只读 (Full RELRO)** , 代价是牺牲启动速度，放弃延迟绑定

程序启动时, Linker 把所有外部函数的真实地址全部找出来，填入 `.got` 表中

之后将整个 **`.got`** 表所在的内存页设置为只读, 保证再也无法篡改函数指针

```python
      printf()
         │
         ↓
    call printf@PLT.GOT      ← .plt.got: 执行跳转代码
         │
         ↓
    jmp *GOT[printf]         ← .got: 绝对安全的只读表，直接读取真实地址
         │
         ↓
   printf() 实际代码          ← libc.so
```

核心：`.plt.got` (跳板代码) + `.got` (只读地址表) + Linker 重定位填充地址

# 0x2 自定义Linker概述

## 自定义Linker的作用

系统的`dlopen`是一个黑盒: 调用它之后, 帮你完成加载、链接、重定位、初始化, 然后返回一个handle。整个过程无法干预, 也无法定制。

自定义Linker的核心价值在于 **对SO加载过程的完全控制**:

- 被加载的SO对系统不可见

自定义Linker加载的SO可以不在系统的soinfo链表中, 从而实现在`/proc/pid/maps`中没有文件路径的效果
- 可插入自定义逻辑

加载前可以解密SO, 加载后可以抹除头部, 中间可以插入反调试检查

## 自定义Linker的实现方式

自定义Linker的实现方式目前了解到两种:

1. 使用soinfo辅助, 加载完毕后手动断开soinfo链, soinfo可以使用官方的也可以魔改
2. 不依赖soinfo, 申请匿名内存, 直接加载

网上了解到的大部分文章基于Android官方或魔改版的soinfo实现方式1的自定义linker

本文基于之前实现的ELF Loader, 使用方式2实现

值得一提的是, 随着功能增加, 用于描述so的class向soinfo靠拢, 所以本质上方式1和方式2的核心原理是一致的

## 自定义Linker的主要工作

自定义Linker实际上是**把系统linker做的事情做一遍**。

linker加载ELF的核心工作并不复杂:

1. 将ELF加载/映射到内存中成为file buffer并校验ELF的合法性
2. 分配image buffer内存并加载所有 `PT_LOAD` 类型的段
3. 解析 `dynamic` 段, 获取链接和重定位必要信息
4. 链接依赖库, 重定位修复指令/变量/函数地址
5. 调用初始化函数(so)或跳转到入口点(可执行程序)

系统linker通过 `ElfReader` 读取文件, `soinfo_link_image` 链接重定位, `CallConstructors` 初始化

自定义linker做同样的事, 只是不走系统的代码路径:

| 系统Linker | 自定义Linker | 作用 |
|-|-|-|
| `open_library` | Step 1: `mapFile` | 打开并映射文件 |
| `ElfReader::VerifyElfHeader` | Step 2: `checkElfHeader` | 校验ELF Magic和架构 |
| `ElfReader::ReserveAddressSpace` | Step 3: `allocImage` | 计算大小, 申请匿名内存 |
| `ElfReader::LoadSegments` | Step 4: `loadSegments` | 加载PT_LOAD段 + 清零BSS |
| `soinfo::prelink_image` | Step 5: `parseDynamic` | 解析动态段 |
| `find_library (DT_NEEDED)` | Step 6: `loadDeps` | dlopen依赖库 |
| `soinfo::relocate` | Step 7: `relocate` | 重定位 |
| `phdr_table_protect_segments` | Step 8: `setProtection` | 设置内存权限 |
| `soinfo::call_constructors` | Step 9: `callInit` | 调用.init / .init_array / JNI_OnLoad |

# 0x3 ELF Loader

在实现自定义Linker之前, 先用一个 ELF 可执行程序加载器来理解核心流程

这个 ELF Loader 只有200多行代码, 但覆盖了加载器的全部核心步骤, 后面的自定义 Linker 只是在同样的骨架上做适配和扩展

## 基本步骤

ELF-Loader.h 根据32/64位定义不同结构体, 并定义 ElfLoader 类如下, 封装了部分关键结构方便函数调用

```cpp
#ifdef __x86_64__
#define Elf_Ehdr Elf64_Ehdr
#define Elf_Phdr Elf64_Phdr
#define Elf_Addr Elf64_Addr
#define Elf_Dyn  Elf64_Dyn
#define Elf_Rel  Elf64_Rela
#define Elf_Sym  Elf64_Sym
#define ELF_R_TYPE  ELF64_R_TYPE
#define ELF_R_SYM   ELF64_R_SYM
#define R_RELATIVE  R_X86_64_RELATIVE
#define R_GLOB_DAT  R_X86_64_GLOB_DAT
#define R_JMP_SLOT  R_X86_64_JUMP_SLOT
#define DT_REL_TAG  DT_RELA
#define DT_RELSZ_TAG DT_RELASZ
#else
#define Elf_Ehdr Elf32_Ehdr
#define Elf_Phdr Elf32_Phdr
#define Elf_Addr Elf32_Addr
#define Elf_Dyn  Elf32_Dyn
#define Elf_Rel  Elf32_Rel
#define Elf_Sym  Elf32_Sym
#define ELF_R_TYPE  ELF32_R_TYPE
#define ELF_R_SYM   ELF32_R_SYM
#define R_RELATIVE  R_386_RELATIVE
#define R_GLOB_DAT  R_386_GLOB_DAT
#define R_JMP_SLOT  R_386_JMP_SLOT
#define DT_REL_TAG  DT_REL
#define DT_RELSZ_TAG DT_RELSZ
#endif

class ElfLoader {
    // File Buffer
    uint8_t* fileMap;  size_t fileSize;
    // ELF Headers
    Elf_Ehdr* ehdr;  Elf_Phdr* phdr;  size_t phdrNum;
    // Image Buffer
    uint8_t* image;  size_t imageSize;
    // 动态段指向的链接/重定位相关结构
    Elf_Rel* relTable;     size_t relCount;
    Elf_Rel* jmpRelTable;  size_t jmpRelCount;
    Elf_Sym* symTab;
    char*    strTab;
    std::vector&lt;void*&gt; depHandles;

    // 关键函数
    bool mapFile();          // Step 1
    bool checkElfHeader();   // Step 2
    void allocImage();       // Step 3
    void loadSegments();     // Step 4
    void parseDynamic();     // Step 5
    void loadDeps();         // Step 6
    void relocate();         // Step 7
    void setProtection();    // Step 8
    // Step 9: jump to entry (in load())
public:
    bool load();
};
```

外部程序可通过ElfLoader::load()函数加载so

```cpp
bool ElfLoader::load() {
    if (!mapFile())        return false;  // 1. 映射文件
    if (!checkElfHeader()) return false;  // 2. 校验ELF头
    allocImage();                         // 3. 分配映像
    loadSegments();                       // 4. 加载段
    parseDynamic();                       // 5. 解析动态段
    loadDeps();                           // 6. 加载依赖
    relocate();                           // 7. 重定位
    setProtection();                      // 8. 设置权限

    // 9. 跳转入口点
    auto entry = (void(*)())(image + ehdr->e_entry);
    printf("Load ELF! Entry: %p\n", (void*)entry);
    entry();
    return true;
}
```

## Step 1: mapFile

映射ELF文件为file buffer, 方便读取信息, 使用mmap比直接读取到内存中更方便快速

open -> fstat 获取大小 -> mmap 只读映射文件到内存, 不需要额外的read/malloc

```cpp
bool ElfLoader::mapFile() {
    int fd = open(filePath, O_RDONLY);
    struct stat st;
    fstat(fd, &st);
    fileSize = st.st_size;
    fileMap = (uint8_t*)mmap(nullptr, fileSize, PROT_READ, MAP_PRIVATE, fd, 0);
    close(fd);
    return true;
}
```

## Step 2: checkElfHeader

校验 Magic Number ("\x7fELF") + 文件类型 (ET_EXEC/ET_DYN)

然后从 e_phoff 定位段表方便后续操作

```cpp
bool ElfLoader::checkElfHeader() {
    ehdr = (Elf_Ehdr*)fileMap;
    // 校验 Magic: 0x7f 'E' 'L' 'F'
    if (memcmp(ehdr->e_ident, ELFMAG, SELFMAG) != 0)
        return false;
    // 校验类型: 必须是可执行文件或共享库
    if (ehdr->e_type != ET_EXEC && ehdr->e_type != ET_DYN)
        return false;
    // 定位 Program Header 表
    phdr = (Elf_Phdr*)(fileMap + ehdr->e_phoff);
    phdrNum = ehdr->e_phnum;
    return true;
}
```

## Step 3: allocImage

遍历段表找到最后一个`PT_LOAD`段的结束地址, 页对齐后就是映像总大小

(一般情况下, 各个段连续, 所以最后一个段的结束地址对应了映像大小, 但并不严谨)

用`MAP_ANONYMOUS`分配一块**RW匿名内存**, 初始可写是因为后续Step 4要memcpy、Step 7要修改重定位目标

```cpp
void ElfLoader::allocImage() {
    // 注意: 此处假定 PT_LOAD 段按 p_vaddr 递增排列 (绝大多数情况成立)
    // 严格实现应遍历所有段取 max, 参见 Loader.cpp 的 allocImage
    size_t maxAddr = 0;
    for (int i = phdrNum - 1; i >= 0; i--) {
        if (phdr[i].p_type == PT_LOAD) {
            maxAddr = phdr[i].p_vaddr + phdr[i].p_memsz;
            break;
        }
    }
    imageSize = alignUp(maxAddr, 0x1000);
    // 匿名映射, 初始RW (重定位需要写入, 完成后再设正式权限)
    image = (uint8_t*)mmap(nullptr, imageSize, PROT_READ | PROT_WRITE,
                            MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (image == MAP_FAILED) {
        printf("Image alloc failed: %zu bytes\n", imageSize);
        image = nullptr;
    }
}
```

## Step 4: loadSegments

遍历所有`PT_LOAD`段, 从文件映射(`fileMap + p_offset`)复制到映像内存(`image + p_vaddr`)

`p_filesz`是文件中的实际数据大小, `p_memsz`是内存中应占的大小, 差值部分是BSS段 (未初始化全局变量), ELF规范要求填零

```cpp
void ElfLoader::loadSegments() {
    // 遍历PT_LOAD段
    for (size_t i = 0; i < phdrNum; i++) {
        if (phdr[i].p_type != PT_LOAD) continue;
        uint8_t* dest = image + phdr[i].p_vaddr;
        // 从file buffer复制到 image buffer
        memcpy(dest, fileMap + phdr[i].p_offset, phdr[i].p_filesz);
        // 清零BSS: p_memsz > p_filesz 的部分
        if (phdr[i].p_memsz > phdr[i].p_filesz)
            memset(dest + phdr[i].p_filesz, 0, phdr[i].p_memsz - phdr[i].p_filesz);
    }
}
```

## Step 5: parseDynamic

Dynamic段本质是一个`(tag, value)`键值对数组, 是linker的"索引目录", 这一步从中提取链接和重定位所需信息:

| tag | 对应的表 | 用途 |
|-|-|-|
| `DT_REL/DT_RELA` + `DT_RELSZ/DT_RELASZ` | `.rel.dyn` / `.rela.dyn` | 数据引用的重定位表 + 大小 |
| `DT_JMPREL` + `DT_PLTRELSZ` | `.rel.plt` / `.rela.plt` | 函数调用的重定位表 + 大小 |
| `DT_SYMTAB` | `.dynsym` | 动态符号表 |
| `DT_STRTAB` | `.dynstr` | 动态符号字符串表 |

注意:

- `d_val`存的是虚拟地址, 需要加上`image`基址
- 重定位表大小指整个表的大小, 除以单个重定位表项大小以获取表项个数

```cpp
void ElfLoader::parseDynamic() {
    // 在Phdr中找到 PT_DYNAMIC 段 (结果保存到成员变量, loadDeps中复用)
    for (size_t i = 0; i < phdrNum; i++) {
        if (phdr[i].p_type == PT_DYNAMIC) {
            dynTable = (Elf_Dyn*)(image + phdr[i].p_vaddr);
            dynCount = phdr[i].p_filesz / sizeof(Elf_Dyn);
            break;
        }
    }
    if (!dynTable) return;
    // 遍历(tag, value)键值对, 提取各表地址
    for (size_t i = 0; i < dynCount; i++) {
        switch (dynTable[i].d_tag) {
            case DT_REL_TAG:   relTable    = (Elf_Rel*)(image + dynTable[i].d_un.d_val); break;
            case DT_RELSZ_TAG: relCount    = dynTable[i].d_un.d_val / sizeof(Elf_Rel);  break;
            case DT_JMPREL:    jmpRelTable = (Elf_Rel*)(image + dynTable[i].d_un.d_val); break;
            case DT_PLTRELSZ:  jmpRelCount = dynTable[i].d_un.d_val / sizeof(Elf_Rel);  break;
            case DT_SYMTAB:    symTab      = (Elf_Sym*)(image + dynTable[i].d_un.d_val); break;
            case DT_STRTAB:    strTab      = (char*)(image + dynTable[i].d_un.d_val);    break;
        }
    }
}
```

## Step 6: loadDeps

`DT_NEEDED`的`d_val`是字符串表中的偏移, 指向依赖库名 (如`libc.so`、`libm.so`)

此处为了便于理解, 没有实现依赖库的加载和符号解析功能, 直接使用 `dlopen`拿到handle, 后续用`dlsym`从中解析符号

```cpp
void ElfLoader::loadDeps() {
    if (!dynTable) return;
    for (size_t i = 0; i < dynCount; i++) {
        if (dynTable[i].d_tag == DT_NEEDED) {
            const char* libName = strTab + dynTable[i].d_un.d_val;
            void* h = dlopen(libName, RTLD_NOW);
            if (h) depHandles.push_back(h);
        }
    }
}
```

## Step 7: relocate

ELF编译时不知道自己会被加载到哪个地址, 所有**绝对地址**引用都需要在加载时修正

有两张重定位表需要处理:

- **.rel/.rela.dyn** — 数据段中的地址引用(全局变量指针等)
- **.rel/.rela.plt** — PLT跳转表中的函数地址

```cpp
void ElfLoader::relocate() {
    Elf_Addr base = (Elf_Addr)image;
    // 用数组统一处理两张表
    Elf_Rel* tables[] = { relTable, jmpRelTable };
    size_t   counts[] = { relCount, jmpRelCount };
    for (int t = 0; t < 2; t++) {
        if (!tables[t]) continue;
        for (size_t i = 0; i < counts[t]; i++) {
            Elf_Addr* target = (Elf_Addr*)(image + tables[t][i].r_offset);
            switch (ELF_R_TYPE(tables[t][i].r_info)) {
                case R_RELATIVE:
                    // 基址重定位: 加载基地址
                    *target += base;
                    break;
                case R_GLOB_DAT:
                case R_JMP_SLOT: {
                    // 符号重定位: 从依赖库查找符号地址
                    const char* name = &strTab[symTab[ELF_R_SYM(tables[t][i].r_info)].st_name];
                    *target = resolveSymbol(name);
                    break;
                }
            }
        }
    }
}
```

重定位类型分两大类:

- 相对偏移地址重定位 (R_RELATIVE)

最常见, `r_offset` 指示修正位置, 直接加上基址即可修复
- 符号重定位 (GLOB_DAT/JMP_SLOT)

需要获取外部符号地址, 从`r_info`提取符号索引, 查符号表获取名称, `resolveSymbol`遍历依赖库逐个`dlsym`查找符号地址

其中`resolveSymbol`实现如下:

```cpp
Elf_Addr ElfLoader::resolveSymbol(const char* name) {
    for (auto h : depHandles) {
        void* addr = dlsym(h, name);
        if (addr) return (Elf_Addr)addr;
    }
    return 0;
}
```

注意: 重定位表 32位架构通常使用Elf32_Rel , 64位使用 Elf64_Rela, 此处没有考虑RELA的append所以并不严谨, 只是恰好样本append=0, 后续实现自定义Linker注意

## Step 8: setProtection

之前分配映像时统一设为RW (方便写入和重定位), 现在一切就位, 按Program Header中`p_flags`指定的权限恢复

- 代码段 (.text): R-X
- 数据段 (.data): RW-
- 只读数据 (.rodata): R--

```cpp
void ElfLoader::setProtection() {
    for (size_t i = 0; i < phdrNum; i++) {
        if (phdr[i].p_type != PT_LOAD) continue;
        int prot = 0;
        if (phdr[i].p_flags & PF_R) prot |= PROT_READ;
        if (phdr[i].p_flags & PF_W) prot |= PROT_WRITE;
        if (phdr[i].p_flags & PF_X) prot |= PROT_EXEC;
        mprotect(image + phdr[i].p_vaddr, alignUp(phdr[i].p_memsz, 0x1000), prot);
    }
}
```

## Step 9: Jump to Entry Point

前8步完成后, ELF的代码和数据已填充, 完成链接和重定位, 并设置段权限, 此时程序映像可以执行

最后从 ELF Header 的 e_entry 获取入口先地址并跳转即可

```cpp
bool ElfLoader::load() {
    if (!mapFile())        return false;  // 1. 映射文件
    if (!checkElfHeader()) return false;  // 2. 校验ELF头
    allocImage();                         // 3. 分配映像
    loadSegments();                       // 4. 加载段
    parseDynamic();                       // 5. 解析动态段
    loadDeps();                           // 6. 加载依赖
    relocate();                           // 7. 重定位
    setProtection();                      // 8. 设置权限

    // 9. 跳转入口点
    auto entry = (void(*)())(image + ehdr->e_entry);
    entry();
    return true;
}
```

## ELF Loader Test

hello.cpp

```cpp
#include&lt;cstdio&gt;
int main(){
    printf("Hello, World!\n");
    return 0;
}
```

main.cpp

```cpp
#include "ELF-Loader.h"
int main(int argc, char* argv[]) {
    if (argc != 2) {
        printf("Usage: %s <elf_file>\n", argv[0]);
        return 1;
    }
    ElfLoader loader(argv[1]);
    loader.load();
    return 0;
}
```

分别编译

```sh
g++ hello.cpp -o hello64
g++ main.cpp ELF-Loader.h ELF-Loader.cpp -o loader64
```

效果如下:

32位ELF程序

![image](https://bbs.kanxue.com/upload/attach/202604/968342_4MDHNSWTBDDF66F.png)

64位ELF程序

![ELF-Loader64-run-result](https://bbs.kanxue.com/upload/attach/202604/968342_3XFP9A9GX8MMEEU.png)

理解了ELF Loader的9条步骤后, 接下来将其迁移到Android平台——实现自定义Linker用于加载SO

# 0x4 Custom Linker

ELF Loader 加载的是可执行程序 (有`e_entry`入口点), 而 Android 的 SO 文件没有入口点

需要依次调用 `.init` -> `.init_array` -> `JNI_OnLoad` 进行初始化

本节将 ELF Loader 迁移到 Android AArch64 平台, 实现自定义Linker加载SO

tip: 为了章节的完整性, 部分重复内容并没有去除, 但对标题进行了标注, 师傅们可以按需跳过

## ELF Loader To Custom Linker

二者共享相同的9条核心步骤, 但部分步骤有差异:

| Step | ELF Loader | Custom Linker |
|-|-|-|
| 1 mapFile | 完全相同 | 完全相同 |
| 2 checkElfHeader | 校验 ET_EXEC/ET_DYN | 校验 EM_AARCH64 |
| 3 allocImage | alignUp(,0x1000) | PAGE_START/PAGE_END宏 |
| 4 loadSegments | 完全相同 | 完全相同 |
| 5 parseDynamic | 6个tag | 额外提取 GNU/SysV Hash |
| 6 loadDeps | 完全相同 | 完全相同 |
| 7 relocate | Rel(无addend) | Rela(带addend) + ABS64 |
| 8 setProtection | 相同 | 额外`__builtin___clear_cache` |
| 9 entry point | jump to `e_entry` | callInit .init -> .init_array -> JNI_OnLoad |

同样的, 外部程序可通过 Loader::load() 函数加载SO

注意:

- load结束后必须要关闭 file buffer 的映射, 否则目标SO文件仍然能通过maps获取到
- wipeElfHeaders 的作用是抹去ELF部分信息以增加逆向难度, 默认注释即可, 后续测试时使用

```cpp
bool Loader::load() {
    LOGD("=== Start Loading: %s ===", soPath.c_str());

    if (!mapFile())       { LOGE("Step 1 Failed: mapFile");       return false; }
    if (!checkElfHeader()){ LOGE("Step 2 Failed: checkElfHeader");return false; }
    if (!allocImage())    { LOGE("Step 3 Failed: allocImage");    return false; }
    if (!loadSegments())  { LOGE("Step 4 Failed: loadSegments");  return false; }
    if (!parseDynamic())  { LOGE("Step 5 Failed: parseDynamic");  return false; }
    if (!loadDeps())      { LOGE("Step 6 Failed: loadDeps");      return false; }
    if (!relocate())      { LOGE("Step 7 Failed: relocate");      return false; }
    if (!setProtection()) { LOGE("Step 8 Failed: setProtection"); return false; }
    if (!callInit())      { LOGE("Step 9 Failed: callInit");      return false; }

    // 关闭file buffer映射, 防止通过maps获取目标SO映射信息
    if (pFileMap && fileSize > 0) munmap(pFileMap, fileSize);

    // 反逆向: 抹除头部信息
    // wipeElfHeaders(); LOGD("Wipe ELF headers");
    LOGD("=== Load Complete ===");
    return true;
}
```

## Step 1: mapFile (完全相同)

open -> fstat 获取大小 -> mmap 只读映射文件到内存, 与ELF Loader的`mapFile`完全相同

```cpp
bool Loader::mapFile() {
    fd = open(soPath.c_str(), O_RDONLY);
    struct stat st;
    fstat(fd, &st);
    fileSize = st.st_size;
    pFileMap = (uint8_t*)mmap(nullptr, fileSize, PROT_READ, MAP_PRIVATE, fd, 0);
    return true;
}
```

## Step 2: checkElfHeader (基本一致)

校验Magic Number(`\x7fELF`), 文件类型, 目标CPU架构(`EM_AARCH64=183`), 任一不匹配则拒绝加载

```cpp
bool Loader::checkElfHeader() {
    pElfHeader = (Elf64_Ehdr*)pFileMap;
    // 校验 Magic: 0x7f 'E' 'L' 'F'
    if (memcmp(pElfHeader->e_ident, ELFMAG, SELFMAG) != 0) {
        LOGE("Invalid ELF magic");
        return false;
    }
    // 校验文件类型和CPU架构: 必须是 AArch64 的SO
    if (pElfHeader->e_type != ET_DYN || pElfHeader->e_machine != EM_AARCH64) {
        LOGE("Not an AArch64 ELF");
        return false;
    }
    // 定位 Program Header 表
    pProgramHeader = (Elf64_Phdr*)(pFileMap + pElfHeader->e_phoff);
    programHeaderNum = pElfHeader->e_phnum;
    return true;
}
```

## Step 3: allocImage (基本一致)

遍历所有`PT_LOAD`段, 算出虚拟地址范围, 页对齐后用`MAP_ANONYMOUS`分配一块连续的**匿名内存**

初始设为RW-, 因为后面要往里写数据(加载段)和改数据(重定位)

使用 PAGE_START 和 PAGE_END 宏计算对齐值

由于申请的是匿名内存, 也没有使用soinfo并注册到soinfo list, 所以加载的目标so信息对maps和soinfo list是不可见的

```cpp
#define PAGE_START(x) ((uintptr_t)(x) & ~(g_PageSize - 1))         // 向下对齐到页首
#define PAGE_END(x)   PAGE_START((uintptr_t)(x) + (g_PageSize - 1)) // 向上对齐到下一页首
bool Loader::allocImage() {
    Elf64_Addr minVaddr = (Elf64_Addr)-1, maxVaddr = 0;
    // 遍历所有PT_LOAD段, 找出虚拟地址范围
    for (size_t i = 0; i < programHeaderNum; i++) {
        if (pProgramHeader[i].p_type != PT_LOAD) continue;
        if (pProgramHeader[i].p_vaddr < minVaddr) minVaddr = pProgramHeader[i].p_vaddr;
        Elf64_Addr segEnd = pProgramHeader[i].p_vaddr + pProgramHeader[i].p_memsz;
        if (segEnd > maxVaddr) maxVaddr = segEnd;
    }
    imageSize = PAGE_END(maxVaddr) - PAGE_START(minVaddr);
    // 匿名映射: 不关联文件, 初始权限RW(后续重定位需要写入)
    pImageBase = (uint8_t*)mmap(nullptr, imageSize, PROT_READ | PROT_WRITE,
                                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
}
```

## Step 4: loadSegments (完全相同)

遍历所有`PT_LOAD`段, 从文件映射(`fileMap + p_offset`)复制到映像内存(`image + p_vaddr`)

`p_filesz`是文件中的实际数据大小, `p_memsz`是内存中应占的大小, 差值部分是BSS段 (未初始化全局变量), ELF规范要求填零

```cpp
bool Loader::loadSegments() {
    for (size_t i = 0; i < programHeaderNum; i++) {
        if (pProgramHeader[i].p_type != PT_LOAD) continue;
        uint8_t* dest = pImageBase + pProgramHeader[i].p_vaddr;
        memcpy(dest, pFileMap + pProgramHeader[i].p_offset, pProgramHeader[i].p_filesz);
        // 清零BSS: p_memsz > p_filesz 的部分
        if (pProgramHeader[i].p_memsz > pProgramHeader[i].p_filesz)
            memset(dest + pProgramHeader[i].p_filesz, 0,
                   pProgramHeader[i].p_memsz - pProgramHeader[i].p_filesz);
    }
}
```

## Step 5: parseDynamic

与ELF Loader相比, 多提取了GNU Hash和SysV Hash表

并将GNU Hash的内部结构(布隆过滤器、桶数组、链数组)全部解析到成员变量中

| d_tag | 对应的表 | 用途 |
|-|-|-|
| `DT_RELA` / `DT_RELASZ` | `.rela.dyn` | 数据引用的重定位 |
| `DT_JMPREL` / `DT_PLTRELSZ` | `.rela.plt` | 函数调用的重定位 |
| `DT_SYMTAB` | `.dynsym` | 动态符号表 |
| `DT_STRTAB` | `.dynstr` | 符号名字符串表 |
| `DT_GNU_HASH` | `.gnu.hash` | GNU Hash表(主要) |
| `DT_HASH` | `.hash` | SysV Hash表(兼容旧版) |

```cpp
bool Loader::parseDynamic() {
    // 在Phdr中找到 PT_DYNAMIC 段
    for (size_t i = 0; i < programHeaderNum; i++) {
        if (pProgramHeader[i].p_type == PT_DYNAMIC) {
            pDynamicTable = (Elf64_Dyn*)(pImageBase + pProgramHeader[i].p_vaddr);
            dynamicItemNum = pProgramHeader[i].p_memsz / sizeof(Elf64_Dyn);
            break;
        }
    }
    // 遍历提取各表地址
    for (size_t i = 0; i < dynamicItemNum; i++) {
        Elf64_Xword val = pDynamicTable[i].d_un.d_val;
        switch (pDynamicTable[i].d_tag) {
            case DT_RELA:     pRelaDyn = (Elf64_Rela*)(pImageBase + val); break;
            case DT_RELASZ:   relaDynNum = val / sizeof(Elf64_Rela);     break;
            case DT_JMPREL:   pRelaPlt = (Elf64_Rela*)(pImageBase + val); break;
            case DT_PLTRELSZ: relaPltNum = val / sizeof(Elf64_Rela);     break;
            case DT_SYMTAB:   pDynSym  = (Elf64_Sym*)(pImageBase + val); break;
            case DT_STRTAB:   pDynStr  = (char*)(pImageBase + val);      break;
            // GNU Hash 表 (NDK r23+ 默认只生成这个)
            case DT_GNU_HASH:
                pGnuHash = (uint32_t*)(pImageBase + val);
                gnuBucketNum   = pGnuHash[0];
                gnuSymOffset   = pGnuHash[1];  // Hash覆盖的符号起始索引
                gnuMaskWords   = pGnuHash[2];
                gnuShift2      = pGnuHash[3];
                gnuBloomFilter = (Elf64_Xword*)(pGnuHash + 4);
                gnuBuckets     = (uint32_t*)(gnuBloomFilter + gnuMaskWords);
                gnuChains      = gnuBuckets + gnuBucketNum;
                break;
            // SysV Hash 表 (兼容旧版 SO)
            case DT_HASH:
                pSysvHash     = (uint32_t*)(pImageBase + val);
                sysvBucketNum = pSysvHash[0];
                sysvChainNum  = pSysvHash[1];
                break;
        }
    }
    return true;
}
```

## Step 6: loadDeps (完全相同)

```cpp
bool Loader::loadDeps() {
    for (size_t i = 0; i < dynamicItemNum; i++) {
        if (pDynamicTable[i].d_tag != DT_NEEDED) continue;
        const char* libName = pDynStr + pDynamicTable[i].d_un.d_val;
        void* handle = dlopen(libName, RTLD_NOW | RTLD_GLOBAL);
        depHandles.push_back(handle);
    }
}
```

## Step 7: relocate

AArch64使用RELA格式(带addend), 依然有2张重定位表 **.rela.dyn** 和 **.rela.plt** 需要处理

```cpp
void Loader::processRelocs(Elf64_Rela* table, size_t count) {
    for (size_t i = 0; i < count; i++) {
        uint32_t type = ELF64_R_TYPE(table[i].r_info);
        uint32_t symIdx = ELF64_R_SYM(table[i].r_info);
        Elf64_Addr* target = (Elf64_Addr*)(pImageBase + table[i].r_offset);

        switch (type) {
            case R_AARCH64_RELATIVE:
                // 基址重定位: 直接加基地址
                *target = (Elf64_Addr)pImageBase + table[i].r_addend;
                break;
            case R_AARCH64_ABS64:
            case R_AARCH64_GLOB_DAT:
            case R_AARCH64_JUMP_SLOT:
                // 符号重定位: 从依赖库解析符号地址
                const char* symName = pDynStr + pDynSym[symIdx].st_name;
                Elf64_Addr symAddr = resolveSymbol(symName);
                *target = symAddr + table[i].r_addend;
                break;
        }
    }
}
```

4种重定位类型分2大类:

- 基址重定位(R_AARCH64_RELATIVE)

 最常见, 处理方式: `*target = pImageBase + r_addend`
- 符号重定位(ABS64/GLOB_DAT/JUMP_SLOT)

需要在依赖库中查找外部符号地址, 通过`resolveSymbol`遍历所有依赖库的`dlsym`实现

与ELF Loader的区别:

- 使用`Elf64_Rela`(带`r_addend`), ELF Loader中x86使用`Elf32_Rel`(无addend)
- 多了`R_AARCH64_ABS64`类型

resolveSymbol()

```cpp
Elf64_Addr Loader::resolveSymbol(const char* name) {
    for (void* h : depHandles) {
        void* addr = dlsym(h, name);
        if (addr) return (Elf64_Addr)addr;
    }
    return 0;
}
```

## Step 8: setProtection (基本一致)

把Step 4中统一设成RW的映像, 按每个段的实际属性重新设置权限

注意: `__builtin___clear_cache`是AArch64上必须的: D-Cache和I-Cache分离, 前面通过memcpy写入的代码在D-Cache中, CPU执行走的是I-Cache, 不刷新会SIGILL崩溃。这是ELF Loader中不需要的步骤

```cpp
bool Loader::setProtection() {
    for (size_t i = 0; i < programHeaderNum; i++) {
        if (pProgramHeader[i].p_type != PT_LOAD) continue;
        int prot = 0;
        if (pProgramHeader[i].p_flags & PF_R) prot |= PROT_READ;
        if (pProgramHeader[i].p_flags & PF_W) prot |= PROT_WRITE;
        if (pProgramHeader[i].p_flags & PF_X) prot |= PROT_EXEC;
        uint8_t* start = pImageBase + PAGE_START(pProgramHeader[i].p_vaddr);
        uint8_t* end   = pImageBase + PAGE_END(pProgramHeader[i].p_vaddr + pProgramHeader[i].p_memsz);
        mprotect(start, end - start, prot);
    }
    __builtin___clear_cache((char*)pImageBase, (char*)pImageBase + imageSize);
}
```

## Step 9: callInit

这是ELF Loader与自定义Linker最大的区别: 可执行程序跳转`e_entry`, 而SO没有入口点, 需要主动调用初始化函数链

SO的初始化分三层, 调用顺序严格遵循系统linker:

1. **`.init`** — 链接器级别全局初始化函数
2. **`.init_array`** — C++全局对象构造函数、`__attribute__((constructor))`标记的函数
3. **`JNI_OnLoad`** — Android特有的JNI方法注册入口, 通过`getSymbol`在自身符号表查找后调用

到这步执行后, 被加载的SO便可以被正常调用——代码就位, 全局变量初始化, 外部符号链接完毕, 构造函数执行完毕

```cpp
bool Loader::callInit() {
    Elf64_Addr initFunc = 0;
    Elf64_Addr* initArray = nullptr;
    size_t initArraySize = 0;

    // 从动态表提取初始化相关条目
    for (size_t i = 0; i < dynamicItemNum; i++) {
        switch (pDynamicTable[i].d_tag) {
            case DT_INIT:         initFunc = pDynamicTable[i].d_un.d_val; break;
            case DT_INIT_ARRAY:   initArray = (Elf64_Addr*)(pImageBase + pDynamicTable[i].d_un.d_val); break;
            case DT_INIT_ARRAYSZ: initArraySize = pDynamicTable[i].d_un.d_val / sizeof(Elf64_Addr); break;
        }
    }

    // 1. 调用 .init
    if (initFunc)
        ((void(*)())(pImageBase + initFunc))();

    // 2. 调用 .init_array
    if (initArray)
        for (size_t i = 0; i < initArraySize; i++)
            ((void(*)())(initArray[i]))();

    // 3. 查找并调用 JNI_OnLoad
    Elf64_Addr jniOnLoad = getSymbol("JNI_OnLoad");
    if (jniOnLoad) {
        typedef jint (*JNI_OnLoadFn)(JavaVM*, void*);
        ((JNI_OnLoadFn)jniOnLoad)(jvm, nullptr);
    }
    return true;
}
```

getSymbol 和 findSymbol 实现如下, 用于查找SO自身符号, 底层通过GNU/Sysv Hash Table查找实现

```cpp
Elf64_Addr Loader::getSymbol(const char* name) {
    Elf64_Sym* sym = findSymbol(name);
    if (sym) return (Elf64_Addr)(pImageBase + sym->st_value);
    return 0;
}
Elf64_Sym* Loader::findSymbol(const char* name) {
    Elf64_Sym* sym = findSymbolGnu(name);
    if (sym) return sym;
    return findSymbolSysv(name);
}
```

# 0x5 Custom Linker Test

## 相关测试文件

### Loader.cpp

自定义Linker相关文件分别为Loader.h和Loader.cpp, 大部分代码前文已经提到此处不做展开

值得一提的是Loader.cpp的JNI_OnLoad用于主动加载目标so

```cpp
extern "C" JNIEXPORT jint JNICALL
JNI_OnLoad(JavaVM* vm, void* reserved) {
    LOGI("Host JNI_OnLoad called");

    // 注意: 必须用 new 堆分配, 不能用栈变量!
    // 被加载 SO 的代码和数据位于 Loader 管理的 mmap 映像中,
    // 如果 Loader 析构 (munmap), 后续调用已注册的 JNI 方法会 SIGSEGV。
    auto* loader = new Loader(vm, "/data/local/tmp/libtestdemo.so");
    loader->load();

    return JNI_VERSION_1_6;
}
```

### MainActivity.java

加载libselfdefineloader.so, 之后测试init_array和JNI函数是否能正确执行

```java
//......
public class MainActivity extends AppCompatActivity {

    private ActivityMainBinding binding;

    static {
        System.loadLibrary("selfdefineloader");
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        binding = ActivityMainBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());

        TextView tv = binding.sampleText;

        // 验证 init_array 执行情况
        int initFlag = getInitFlag();
        int initArrayCount = getInitArrayCount();
        Log.d("MainActivity", "initFlag=" + initFlag + ", initArrayCount=" + initArrayCount);

        // 验证 JNI 函数
        String result = "add(333,666)=" + add(333, 666)
                + "\nsub(666,333)=" + sub(666, 333)
                + "\ninitFlag=" + initFlag + " (expect 1)"
                + "\ninitArrayCount=" + initArrayCount + " (expect 101)";
        tv.setText(result);
    }

    public native int add(int x, int y);
    public native int sub(int x, int y);
    public native int getInitFlag();
    public native int getInitArrayCount();
}
```

### testdemo.cpp

创建全局变量, 实现init_array函数, JNI_OnLoad动态注册JNI函数

```cpp
#include &lt;jni.h&gt;
#include &lt;string&gt;
#include &lt;android/log.h&gt;

#define TAG "glass"
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, TAG, __VA_ARGS__)

static const char *ClassName = "com/example/selfdefineloader/MainActivity";

// ==================== 全局变量测试 ====================
static int g_initFlag = 0;         // 记录初始化是否执行
static int g_initArrayCount = 0;   // 记录 init_array 执行次数

// ==================== .init 函数 ====================
// __attribute__((constructor)) 不带优先级时进入 .init_array
// 要进入 .init 段需要用链接器脚本或 naked constructor, 但实际上 Android NDK
// 编译的 SO 不生成 .init 段, 只生成 .init_array
// 所以这里统一用 constructor attribute, 通过优先级区分执行顺序

// 最先执行: 优先级 101 (用户可用的最小优先级)
__attribute__((constructor(101)))
void myInit1() {
    g_initFlag = 1;
    LOGD("[init_array priority=101] myInit1 executed, g_initFlag = %d", g_initFlag);
}

// 其次执行: 优先级 102
__attribute__((constructor(102)))
void myInit2() {
    g_initArrayCount = 100;
    LOGD("[init_array priority=102] myInit2 executed, g_initArrayCount = %d", g_initArrayCount);
}

// 无优先级: 在有优先级的之后执行
__attribute__((constructor))
void myInit3() {
    g_initArrayCount += 1;
    LOGD("[init_array no priority] myInit3 executed, g_initArrayCount = %d", g_initArrayCount);
}

// ==================== .fini_array 函数 ====================
__attribute__((destructor))
void myFini() {
    LOGD("[fini_array] myFini executed, cleanup");
}

// ==================== JNI 函数 ====================
jint add(JNIEnv* env, jobject obj, jint x, jint y) {
    return x + y;
}

jint sub(JNIEnv* env, jobject obj, jint x, jint y) {
    return x - y;
}

// 验证 init_array 是否在 JNI_OnLoad 之前执行
jint getInitFlag(JNIEnv* env, jobject obj) {
    return g_initFlag;
}

// 验证多个 init_array 函数的执行顺序和次数
jint getInitArrayCount(JNIEnv* env, jobject obj) {
    return g_initArrayCount;
}

// ==================== JNI 注册 ====================
static JNINativeMethod methods[] = {
        {"add",               "(II)I", (void*)add},
        {"sub",               "(II)I", (void*)sub},
        {"getInitFlag",       "()I",   (void*)getInitFlag},
        {"getInitArrayCount", "()I",   (void*)getInitArrayCount}
};

jint JNI_OnLoad(JavaVM* vm, void* reserved) {
    LOGD("[JNI_OnLoad] entered, g_initFlag = %d, g_initArrayCount = %d", g_initFlag, g_initArrayCount);

    JNIEnv* env = nullptr;
    if (vm->GetEnv((void**)&env, JNI_VERSION_1_6) != JNI_OK)
        return -1;

    jclass clazz = env->FindClass(ClassName);
    if (clazz) {
        env->RegisterNatives(clazz, methods, sizeof(methods) / sizeof(methods[0]));
        return JNI_VERSION_1_6;
    }
    return -1;
}
```

### CMakeLists.txt

生成libtestdemo.so到build/outputs/lib/arm64-v8a/目录下, 且不打包进apk, 方便测试

```cmake
# Sets the minimum CMake version required for this project.
cmake_minimum_required(VERSION 3.22.1)

project("selfdefineloader")

# 关闭优化 (-O0)，便于调试和单步跟踪加载流程
# 隐藏所有符号 (-fvisibility=hidden)，只导出显式标记的函数
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O0 -fvisibility=hidden")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O0 -fvisibility=hidden")

add_library(${CMAKE_PROJECT_NAME} SHARED
        # List C/C++ source files with relative paths to this CMakeLists.txt.
        Loader.cpp
        Loader.h
)
# testdemo: 编译但不打包到 APK 中
# EXCLUDE_FROM_ALL 使 Gradle 不会自动将其包含到 APK
add_library(testdemo SHARED EXCLUDE_FROM_ALL
        testdemo.cpp
)
target_link_libraries(testdemo log)

# 编译完成后自动复制到 outputs 目录
set(TESTDEMO_OUTPUT_DIR "${CMAKE_SOURCE_DIR}/../../../build/outputs/lib/${ANDROID_ABI}")
add_custom_command(TARGET testdemo POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E make_directory "${TESTDEMO_OUTPUT_DIR}"
        COMMAND ${CMAKE_COMMAND} -E copy "$<TARGET_FILE:testdemo>" "${TESTDEMO_OUTPUT_DIR}/"
        COMMENT "Copying libtestdemo.so to ${TESTDEMO_OUTPUT_DIR}"
)

# 让主库构建时顺带编译 testdemo
add_dependencies(${CMAKE_PROJECT_NAME} testdemo)

# Specifies libraries CMake should link to your target library. You
# can link libraries from various origins, such as libraries defined in this
# build script, prebuilt third-party libraries, or Android system libraries.
target_link_libraries(${CMAKE_PROJECT_NAME}
        # List libraries link to the target library
        android
        log)
```

## 运行效果

编译后推送libtestdemo.so至"/data/local/tmp"目录下

```sj
adb push libtestdemo.so /data/local/tmp
```

注意: 由于selinux权限限制, 如果不能读取该目录, 则需要root权限的shell使用`setenforce 0`关闭selinux

启动app, 运行效果如下:

- 成功加载libtestdemo.so并进行链接和重定位
- 调用init_array的初始化函数
- 调用JNI_OnLoad注册JNI函数
- Java层成功调用目标SO的Native方法

![image](https://bbs.kanxue.com/upload/attach/202604/968342_RYPWGAJ88AHHGJV.png)

自定义Linker可以保证在"/proc/tid/maps"中无法发现目标so, 因为so所在内存属于匿名内存

![image](https://bbs.kanxue.com/upload/attach/202604/968342_2YQB2CPR6CQ2CZ7.png)

## 逆向: 扫描内存匿名模块

不难发现so加载到内存后, 保留了ELF Header, 这是一个关键特征, 另外一个特征是部分段具有R-X权限

一个具有可执行权限的匿名内存段会干什么呢? 好难猜啊

基于这些特征, 可以编写frida脚本, 扫描匿名内存模块:

1. 获取所有已知模块的基址, 设置白名单
2. 枚举进程内存范围

对于单个SO, 通常情况下内存范围是连续的

匹配到R-X的内存段时, 判断其基地址首部4字节是否为ELF Magic Number
3. 匹配到可疑内存段后, 判断是否属于已知模块, 若不属于则为匿名模块, 进行dump

```js
function saveToFile(path, data) {
    const file = new File(path, "wb");
    file.write(data);
    file.flush();
    file.close();
}
function getElfFullSize(base) {
    try {
        const is64Bit = base.add(4).readU8() === 2;
        const e_phoff = is64Bit ? base.add(32).readS64() : base.add(28).readS32();
        const e_phnum = is64Bit ? base.add(56).readU16() : base.add(44).readU16();
        const p_size = is64Bit ? 56 : 32;

        let maxAddr = 0;
        for (let i = 0; i < e_phnum; i++) {
            const phdrAddr = base.add(e_phoff).add(i * p_size);
            const p_type = phdrAddr.readU32();

            if (p_type === 1) { // PT_LOAD
                const p_vaddr = is64Bit ? phdrAddr.add(16).readS64() : phdrAddr.add(8).readS32();
                const p_memsz = is64Bit ? phdrAddr.add(40).readS64() : phdrAddr.add(20).readS32();
                const end = p_vaddr + p_memsz;
                if (end > maxAddr) maxAddr = end;
            }
        }
        // 向上对齐到页 (4096)
        return (maxAddr + 0xFFF) & ~0xFFF;
    } catch (e) {
        console.log("    [!] 无法解析 Phdr 计算大小，跳过。");
        return 0;
    }
}
function dump_module(base, soName, saveDir) {
    console.log(`[+] Dump 模块: ${soName} at ${base}, save to ${saveDir}`);
    // 2. 计算整个 SO 的内存大小 (解析 PT_LOAD)
    const fullSize = getElfFullSize(base);
    if (fullSize === 0) return;

    // 3. 执行 Dump
    const fileName = `${soName}_${base}_${fullSize}.so`;
    const filePath = saveDir + fileName;

    const dumpData = base.readByteArray(fullSize);
    saveToFile(filePath, dumpData);

    console.log(`[+] Dump 成功: ${filePath}`);
    console.log(`    Size: ${(fullSize / 1024 / 1024).toFixed(2)} MB (${fullSize} Bytes)`);
}

function scanHiddenModules(soName, pkgName) {
    const saveDir = `/data/data/${pkgName}/`;
    console.log(`[*] 开始扫描内存，Dump 文件将保存至: ${saveDir}`);

    // 0.获取所有已知模块基地址, 设置白名单
    const knownModules = Process.enumerateModules().map(m => m.base.toString());

    // 遍历app进程内存范围
    Process.enumerateRanges({
        protection: 'r-x',
        coalesce: true
    }).forEach(function (range) {
        try {
            // 1. 验证 ELF 魔数
            const buf = range.base.readByteArray(4);
            if (!buf) return;
            const bytes = new Uint8Array(buf);
            if (bytes[0] === 0x7f && bytes[1] === 0x45 && bytes[2] === 0x4c && bytes[3] === 0x46) {
                // 2. 获取内存范围所属基地址, 验证是否为已知模块
                const base = range.base;
                if (knownModules.indexOf(base.toString()) !== -1) return;
                console.log(`[!] 发现隐藏模块: ${base}`);
                 // 3. 发现匿名模块, dump
                dump_module(base, soName, saveDir);

            }
        } catch (e) { }
    });
}

function main() {
    var soName = "libtestdemo.so";
    var package_name = "com.example.selfdefineloader";
    scanHiddenModules(soName, package_name);
}
setImmediate(main);
```

attach模式注入脚本, 扫描并dump

![image](https://bbs.kanxue.com/upload/attach/202604/968342_ZSWQ43S54QJG5RK.png)

拉取到PC并使用[SoFixer](https://github.com/F8LEFT/SoFixer)修复

![image](https://bbs.kanxue.com/upload/attach/202604/968342_E7XR5SVF3AC66P4.png)

最后, IDA分析对比修复前后的SO, 左边未修复无法看到符号, 右边可以看到JNI_OnLoad

![image](https://bbs.kanxue.com/upload/attach/202604/968342_NH3X43BC3GUECY4.png)

值得一提的是, 该脚本是笔者逆向分析 zgcbank-4.5.1(某bang加固) 时 拷打AI得到的, 所以针对市面上部分自定义Linker加固壳有效

## 反逆向: wipeElfHeaders

加载完成后, ELF Header, Program Header, Dynamic Segment, 这三块数据已完成使命 (所有需要的信息已提取到成员变量中), 可以直接抹去, 增大逆向分析的难度:

- 攻击者通过`/proc/pid/mem` 或 `/proc/pid/maps` dump出来的内存, IDA和readelf无法识别为有效ELF
- 无法还原动态段, 重定位表, 符号表等结构, 所以无法直接使用SoFixer修复
- 抹去这部分信息后, 便无法通过前文提到的脚本扫描并dump

注意: 抹除前需要`mprotect`修改内存页权限, 抹除后需要恢复原权限

```cpp
void Loader::wipeElfHeaders() {
    if (!pImageBase) return;

    void* headerPage = (void*)PAGE_START(pImageBase);

    // 1. 抹除 ELF Header (前 64 字节)
    mprotect(headerPage, g_PageSize, PROT_READ | PROT_WRITE);
    memset(pImageBase, 0, sizeof(Elf64_Ehdr));

    // 2. 抹除 Program Headers
    uint8_t* phdrStart = (uint8_t*)pProgramHeader;
    if (phdrStart >= pImageBase && phdrStart < pImageBase + imageSize) {
        uintptr_t phdrPageStart = PAGE_START(phdrStart);
        uintptr_t phdrPageEnd = PAGE_END(phdrStart + programHeaderNum * sizeof(Elf64_Phdr));
        size_t phdrLen = phdrPageEnd - phdrPageStart;

        mprotect((void*)phdrPageStart, phdrLen, PROT_READ | PROT_WRITE);
        memset(phdrStart, 0, programHeaderNum * sizeof(Elf64_Phdr));
        mprotect((void*)phdrPageStart, phdrLen, PROT_READ);
    }

    // 3. 抹除 Dynamic Section
    if (pDynamicTable) {
        uint8_t* dynStart = (uint8_t*)pDynamicTable;
        if (dynStart >= pImageBase && dynStart < pImageBase + imageSize) {
            size_t dynSize = dynamicItemNum * sizeof(Elf64_Dyn);
            uintptr_t dynPageStart = PAGE_START(dynStart);
            uintptr_t dynPageEnd = PAGE_END(dynStart + dynSize);
            size_t dynLen = dynPageEnd - dynPageStart;

            mprotect((void*)dynPageStart, dynLen, PROT_READ | PROT_WRITE);
            memset(dynStart, 0, dynSize);
            mprotect((void*)dynPageStart, dynLen, PROT_READ);
        }
    }

    // 恢复首页为 R-X (代码段通常从首页开始)
    mprotect(headerPage, g_PageSize, PROT_READ | PROT_EXEC);

    LOGD("ELF headers wiped — anti-dump active");
}
```

# 0x6 Linker概述

以下内容偏理论, 主要从 Android 4.4.4_r1 和 Android 10.0.0_r47 源码入手, 分别分析32位和64位的linker加载和链接so的工作流程

其中32位的linker较为简单, 64位的linker添加了更多操作, 但只要逐步跟进可以发现并不复杂

## Linker Load So32 概述

32位linker: 简单直接, 加载和链接在`find_library_internal`中串行完成, 不涉及命名空间隔离

Android 4.4.4_r1 Linker加载和链接so的核心调用链:

```python
Java: System.loadLibrary("native-lib")
  └─→ Runtime.loadLibrary
      └─→ doLoad
          └─→ nativeLoad (JNI边界)
              └─→ Runtime_nativeLoad
                  └─→ JavaVMExt::LoadNativeLibrary
                      ├─→ dlopen ──→ do_dlopen
                      │               ├─→ find_library
                      │               │     └─→ find_library_internal
                      │               │           ├─→ find_loaded_library    [已加载? 直接返回]
                      │               │           ├─→ load_library           [未加载: 开始加载]
                      │               │           │     ├─→ open_library     (打开SO文件)
                      │               │           │     └─→ ElfReader::Load
                      │               │           │           ├─ ReadElfHeader
                      │               │           │           ├─ VerifyElfHeader
                      │               │           │           ├─ ReadProgramHeader
                      │               │           │           ├─ ReserveAddressSpace
                      │               │           │           ├─ LoadSegments
                      │               │           │           └─ FindPhdr
                      │               │           └─→ soinfo_link_image     [链接+重定位]
                      │               │                 ├─ 遍历Dynamic段 (提取符号表/重定位表等)
                      │               │                 ├─ find_library (递归加载DT_NEEDED依赖)
                      │               │                 └─ soinfo_relocate (执行重定位)
                      │               └─→ CallConstructors
                      │                     ├─ 依赖库 CallConstructors (递归)
                      │                     ├─ CallFunction (DT_INIT)
                      │                     └─ CallArray (DT_INIT_ARRAY)
                      ├─→ dlsym("JNI_OnLoad")
                      └─→ JNI_OnLoad()
```

流程图:

![image](https://bbs.kanxue.com/upload/attach/202604/968342_GR6PQ94JF79DBA4.png)

## Linker Load So64 概述

64位linker: 引入了命名空间隔离(`android_dlopen_ext`), `find_libraries`加载和链接SO, 支持随机序加载防攻击

Android 10.0.0_r47 Linker 核心调用链:

```python
Java: System.loadLibrary("native-lib")
  └─→ Runtime.loadLibrary0
      └─→ nativeLoad (JNI边界)
          └─→ Runtime_nativeLoad
              └─→ JVM_NativeLoad
                  └─→ JavaVMExt::LoadNativeLibrary
                      ├─→ android::OpenNativeLibrary
                      │     ├─→ android_dlopen_ext  [主要路径, 带命名空间]
                      │     └─→ dlopen              [兼容路径]
                      │           └─→ dlopen_ext
                      │               └─→ do_dlopen
                      │                   ├─→ find_library
                      │                   │     └─→ find_libraries (批量加载)
                      │                   │           ├─ Step 0: prepare (创建LoadTask队列)
                      │                   │           ├─ Step 1: find_library_internal
                      │                   │           │    ├─ find_loaded_library_by_soname [已加载?]
                      │                   │           │    └─ load_library [未加载: 加载]
                      │                   │           │         ├─ open_library (搜索并打开SO)
                      │                   │           │         ├─ ElfReader::Read
                      │                   │           │         │    ├─ ReadElfHeader
                      │                   │           │         │    ├─ VerifyElfHeader
                      │                   │           │         │    ├─ ReadProgramHeaders
                      │                   │           │         │    ├─ ReadSectionHeaders
                      │                   │           │         │    └─ ReadDynamicSection
                      │                   │           │         └─ 添加DT_NEEDED到load_tasks
                      │                   │           ├─ Step 2: LoadTask::load (随机序加载)
                      │                   │           │    └─ ElfReader::Load
                      │                   │           │         ├─ ReserveAddressSpace
                      │                   │           │         ├─ LoadSegments
                      │                   │           │         └─ FindPhdr
                      │                   │           ├─ Step 3: prelink_image (解析Dynamic段)
                      │                   │           ├─ Step 4-5: 地址空间+GNU RELRO保护
                      │                   │           ├─ Step 6: link_image (重定位)
                      │                   │           └─ Step 7: 标记linked + 引用计数
                      │                   └─→ call_constructors
                      │                         ├─ 依赖库 call_constructors (递归)
                      │                         ├─ call_function (DT_INIT)
                      │                         └─ call_array (DT_INIT_ARRAY)
                      ├─→ FindSymbol("JNI_OnLoad")
                      └─→ JNI_OnLoad()
```

加载和链接so的流程图:

![image](https://bbs.kanxue.com/upload/attach/202604/968342_VN7K367ADZB9KFW.png)

# 0x7 Linker Load So32 详解

前文内容是我们自己从零实现Linker, 本节换个角度——阅读 Android 官方 linker 的源码, 看看系统是如何实现的

这一节不是实现参考, 而是帮助读者理解系统 linker 的完整工作流程

本节基于 Android 4.4.4_r1 源码, 32位 linker 结构简单直接, 适合入门理解整体流程

## Java Level

java层通常使用以下代码加载一个so

```java
static{
    System.loadLibrary("native-lib");
}
```

### System.loadLibrary

Android 4.4定义如下

https://cs.android.com/android/platform/superproject/+/android-4.4.4_r1:/libcore/luni/src/main/java/java/lang/System.java#525

```java
public static void loadLibrary(String libName) {
    Runtime.getRuntime().loadLibrary(libName, VMStack.getCallingClassLoader());
}
```

### Runtime.loadLibrary

Android 4.4

https://cs.android.com/android/platform/superproject/+/android-4.4.4_r1:libcore/luni/src/main/java/java/lang/Runtime.java;bpv=0

```java
    /*
     * Searches for a library, then loads and links it without security checks.
     */
    void loadLibrary(String libraryName, ClassLoader loader) {
        if (loader != null) {
            // 1. 调用findLibrary通过名称"native-lib"寻找真实库名
            String filename = loader.findLibrary(libraryName);
            if (filename == null) {
                throw new UnsatisfiedLinkError("Couldn't load " + libraryName +
                                               " from loader " + loader +
                                               ": findLibrary returned null");
            }
            // 2. 调用doLoad加载so
            String error = doLoad(filename, loader);
            if (error != null) {
                throw new UnsatisfiedLinkError(error);
            }
            return;
        }

        String filename = System.mapLibraryName(libraryName);
        List&lt;String&gt; candidates = new ArrayList&lt;String&gt;();
        String lastError = null;
        for (String directory : mLibPaths) {
            String candidate = directory + filename;
            candidates.add(candidate);
            // 3. 通过其他路径搜索库文件,依然调用doLoad
            if (IoUtils.canOpenReadOnly(candidate)) {
                String error = doLoad(candidate, loader);
                if (error == null) {
                    return; // We successfully loaded the library. Job done.
                }
                lastError = error;
            }
        }

        if (lastError != null) {
            throw new UnsatisfiedLinkError(lastError);
        }
        throw new UnsatisfiedLinkError("Library " + libraryName + " not found; tried " + candidates);
    }
```

### doLoad

获取ClassLoader的native library搜索路径, 传递给`nativeLoad`。加锁保证同一时间只有一个`LD_LIBRARY_PATH`在使用

```java
    private static native void nativeExit(int code);

    private String doLoad(String name, ClassLoader loader) {
        String ldLibraryPath = null;
        if (loader != null && loader instanceof BaseDexClassLoader) {
            // 1. 如果是BaseDexClassLoader,则获取系统so的路径
            ldLibraryPath = ((BaseDexClassLoader) loader).getLdLibraryPath();
        }

        synchronized (this) {
            // 2. 调用nativeLoad,同时加上同步锁
            return nativeLoad(name, loader, ldLibraryPath);
        }
    }
```

## JNI Level

Java层的`nativeLoad`进入Native层, 最终调用ART虚拟机的`LoadNativeLibrary`完成SO加载

### nativeLoad

native函数声明, 对应的JNI实现为`Runtime_nativeLoad`

```java
    // TODO: should be synchronized, but dalvik doesn't support synchronized internal natives.
    private static native String nativeLoad(String filename, ClassLoader loader, String ldLibraryPath);
```

### Runtime_nativeLoad

`nativeLoad`的JNI实现。更新`LD_LIBRARY_PATH`后, 调用`JavaVMExt::LoadNativeLibrary`执行真正的加载

https://cs.android.com/android/platform/superproject/+/android-4.4.4_r1:art/runtime/native/java_lang_Runtime.cc

```cpp
static jstring Runtime_nativeLoad(JNIEnv* env, jclass, jstring javaFilename,
                                  jobject javaLoader, jstring javaLdLibraryPath)
{
  //1. 各种检查操作
  ScopedObjectAccess soa(env);
  ScopedUtfChars filename(env, javaFilename);
  if (filename.c_str() == NULL) {
    return NULL;
  }

  if (javaLdLibraryPath != NULL) {
    ScopedUtfChars ldLibraryPath(env, javaLdLibraryPath);
    if (ldLibraryPath.c_str() == NULL) {
      return NULL;
    }
    void* sym = dlsym(RTLD_DEFAULT, "android_update_LD_LIBRARY_PATH");
    if (sym != NULL) {
      typedef void (*Fn)(const char*);
      Fn android_update_LD_LIBRARY_PATH = reinterpret_cast&lt;Fn&gt;(sym);
      (*android_update_LD_LIBRARY_PATH)(ldLibraryPath.c_str());
    } else {
      LOG(ERROR) << "android_update_LD_LIBRARY_PATH not found; .so dependencies will not work!";
    }
  }

  mirror::ClassLoader* classLoader = soa.Decode&lt;mirror::ClassLoader*&gt;(javaLoader);
  std::string detail;
  JavaVMExt* vm = Runtime::Current()->GetJavaVM();
  //2. 调用vm的LoadNativeLibrary
  bool success = vm->LoadNativeLibrary(filename.c_str(), classLoader, detail);
  if (success) {
    return NULL;
  }

  // Don't let a pending exception from JNI_OnLoad cause a CheckJNI issue with NewStringUTF.
  // 不要让 JNI_OnLoad 中的未决异常导致 NewStringUTF 的 CheckJNI 问题。
  env->ExceptionClear();
  return env->NewStringUTF(detail.c_str());
}
```

### JavaVMExt::LoadNativeLibrary

https://cs.android.com/android/platform/superproject/+/android-4.4.4_r1:art/runtime/jni_internal.cc

- 调用dlopen加载so
- 查找so的JNI_OnLOad函数并执行

```cpp
bool JavaVMExt::LoadNativeLibrary(const std::string& path, ClassLoader* class_loader,
                                  std::string& detail) {
  detail.clear();
    //......
  self->TransitionFromRunnableToSuspended(kWaitingForJniOnLoad);
    // 1. 调用dlopen加载so并返回handle
  void* handle = dlopen(path.empty() ? NULL : path.c_str(), RTLD_LAZY);
  self->TransitionFromSuspendedToRunnable();

  VLOG(jni) << "[Call to dlopen(\"" << path << "\", RTLD_LAZY) returned " << handle << "]";

  if (handle == NULL) {
    detail = dlerror();
    LOG(ERROR) << "dlopen(\"" << path << "\", RTLD_LAZY) failed: " << detail;
    return false;
  }

  // Create a new entry.
  // TODO: move the locking (and more of this logic) into Libraries.
  bool created_library = false;
  {
    MutexLock mu(self, libraries_lock);
    library = libraries->Get(path);
    if (library == NULL) {  // We won race to get libraries_lock
      library = new SharedLibrary(path, handle, class_loader);
      libraries->Put(path, library);
      created_library = true;
    }
  }
  if (!created_library) {
    LOG(INFO) << "WOW: we lost a race to add shared library: "
        << "\"" << path << "\" ClassLoader=" << class_loader;
    return library->CheckOnLoadResult();
  }

  VLOG(jni) << "[Added shared library \"" << path << "\" for ClassLoader " << class_loader << "]";

  bool was_successful = false;
    //2. 如果so成功加载,则调用dlsym查找JNI_OnLoad符号并执行
  void* sym = dlsym(handle, "JNI_OnLoad");
  if (sym == NULL) {
    VLOG(jni) << "[No JNI_OnLoad found in \"" << path << "\"]";
    was_successful = true;
  } else {
    // Call JNI_OnLoad.  We have to override the current class
    // loader, which will always be "null" since the stuff at the
    // top of the stack is around Runtime.loadLibrary().  (See
    // the comments in the JNI FindClass function.)
    typedef int (*JNI_OnLoadFn)(JavaVM*, void*);
    JNI_OnLoadFn jni_on_load = reinterpret_cast<JNI_OnLoadFn>(sym);
    ClassLoader* old_class_loader = self->GetClassLoaderOverride();
    self->SetClassLoaderOverride(class_loader);

    int version = 0;
    {
      ScopedThreadStateChange tsc(self, kNative);
      VLOG(jni) << "[Calling JNI_OnLoad in \"" << path << "\"]";
      //3. 执行JNI_OnLoad
      version = (*jni_on_load)(this, NULL);
    }

    self->SetClassLoaderOverride(old_class_loader);

    if (version == JNI_ERR) {
      StringAppendF(&detail, "JNI_ERR returned from JNI_OnLoad in \"%s\"", path.c_str());
    } else if (IsBadJniVersion(version)) {
      StringAppendF(&detail, "Bad JNI version returned from JNI_OnLoad in \"%s\": %d",
                    path.c_str(), version);
      // It's unwise to call dlclose() here, but we can mark it
      // as bad and ensure that future load attempts will fail.
      // We don't know how far JNI_OnLoad got, so there could
      // be some partially-initialized stuff accessible through
      // newly-registered native method calls.  We could try to
      // unregister them, but that doesn't seem worthwhile.
    } else {
      was_successful = true;
    }
    VLOG(jni) << "[Returned " << (was_successful ? "successfully" : "failure")
              << " from JNI_OnLoad in \"" << path << "\"]";
  }

  library->SetResult(was_successful);
  return was_successful;
}
```

## Linker Init

Linker为了加载so的部分前置操作

### dlopen

https://cs.android.com/android/platform/superproject/+/android-4.4.4_r1:bionic/linker/dlfcn.cpp

调用了do_dlopen,并返回soinfo指针

```cpp
void* dlopen(const char* filename, int flags) {
  ScopedPthreadMutexLocker locker(&gDlMutex);
  soinfo* result = do_dlopen(filename, flags);
  if (result == NULL) {
    __bionic_format_dlerror("dlopen failed", linker_get_error_buffer());
    return NULL;
  }
  return result;
}
```

### do_dlopen

https://cs.android.com/android/platform/superproject/+/android-4.4.4_r1:bionic/linker/linker.cpp

- 调用find_library,返回soinfo
- 调用soinfo.CallConstructors(), 执行init, init_array等初始化操作

```cpp
soinfo* do_dlopen(const char* name, int flags) {
  if ((flags & ~(RTLD_NOW|RTLD_LAZY|RTLD_LOCAL|RTLD_GLOBAL)) != 0) {
    DL_ERR("invalid flags to dlopen: %x", flags);
    return NULL;
  }
  set_soinfo_pool_protection(PROT_READ | PROT_WRITE);
  soinfo* si = find_library(name);
  if (si != NULL) {
    si->CallConstructors();
  }
  set_soinfo_pool_protection(PROT_READ);
  return si;
}
```

### find_library

- 调用find_library_internal
- so的引用计数+1

```cpp
static soinfo* find_library(const char* name) {
  soinfo* si = find_library_internal(name);
  if (si != NULL) {
    si->ref_count++;
  }
  return si;
}
```

### find_library_internal

 https://cs.android.com/android/platform/superproject/+/android-4.4.4_r1:bionic/linker/linker.cpp#751

- 判断so是否加载过
- 如果未加载则调用load_library加载so
- 加载后调用soinfo_link_image进行链接

```cpp
static soinfo* find_library_internal(const char* name) {
  if (name == NULL) {
    return somain;
  }
    //1. 查询该so是否加载过,加载过的so位于已加载列表,无需二次加载
  soinfo* si = find_loaded_library(name);
  if (si != NULL) {
    if (si->flags & FLAG_LINKED) {
      return si;
    }
    DL_ERR("OOPS: recursive link to \"%s\"", si->name);
    return NULL;
  }

  TRACE("[ '%s' has not been loaded yet.  Locating...]", name);
    //2. 调用load_library加载so
  si = load_library(name);
  if (si == NULL) {
    return NULL;
  }

  // At this point we know that whatever is loaded @ base is a valid ELF
  // shared library whose segments are properly mapped in.
  TRACE("[ init_library base=0x%08x sz=0x%08x name='%s' ]",
        si->base, si->size, si->name);

    //3. 链接so
  if (!soinfo_link_image(si)) {
    munmap(reinterpret_cast&lt;void*&gt;(si->base), si->size);
    soinfo_free(si);
    return NULL;
  }

  return si;
}
```

#### find_loaded_library

 遍历solist,从已加载so中获取soinfo

 https://cs.android.com/android/platform/superproject/+/android-4.4.4_r1:bionic/linker/linker.cpp#732

```cpp
static soinfo *find_loaded_library(const char *name)
{
    soinfo *si;
    const char *bname;

    // TODO: don't use basename only for determining libraries
    // http://code.google.com/p/android/issues/detail?id=6670

    bname = strrchr(name, '/');
    bname = bname ? bname + 1 : name;

    for (si = solist; si != NULL; si = si->next) {
        if (!strcmp(bname, si->name)) {
            return si;
        }
    }
    return NULL;
}
```

## Linker Load

加载SO文件到内存的核心流程, 通过ElfReader完成ELF解析、地址空间分配和段加载

### load_library

加载SO的入口: 打开文件 → 创建`ElfReader`执行加载 → 分配`soinfo`并填充加载结果(基址、大小、load_bias等)

```cpp
static soinfo* load_library(const char* name) {
    // 1.打开so文件,获取文件描述符fd
    int fd = open_library(name);
    if (fd == -1) {
        DL_ERR("library \"%s\" not found", name);
        return NULL;
    }

    // 2.创建ElfReader对象,并调用load方法
    ElfReader elf_reader(name, fd);
    if (!elf_reader.Load()) {
        return NULL;
    }

    // 3.生成soinfo,并根据elf_reader结果赋值
    const char* bname = strrchr(name, '/');
    soinfo* si = soinfo_alloc(bname ? bname + 1 : name);
    if (si == NULL) {
        return NULL;
    }
    si->base = elf_reader.load_start();
    si->size = elf_reader.load_size();
    si->load_bias = elf_reader.load_bias();
    si->flags = 0;
    si->entry = 0;
    si->dynamic = NULL;
    si->phnum = elf_reader.phdr_count();
    si->phdr = elf_reader.loaded_phdr();
    return si;
}
```

### elf_reader.Load

ElfReader的主流程, 串联6个步骤: 读取ELF头 → 验证ELF头 → 读取程序头表 → 分配地址空间 → 加载段 → 定位Phdr。任一步骤失败则整体失败

https://cs.android.com/android/platform/superproject/+/android-4.4.4_r1:bionic/linker/linker_phdr.cpp

```cpp
bool ElfReader::Load() {
  return ReadElfHeader() &&			// 读取ElfHeader
         VerifyElfHeader() &&		// 验证ElfHeader
         ReadProgramHeader() &&		// 读取程序头表(段表)
         ReserveAddressSpace() &&	// 准备地址空间
         LoadSegments() &&			// 加载段
         FindPhdr();				// 寻找Phdr段
}
```

#### ElfReader::ReadElfHeader

从文件描述符读取`sizeof(Elf32_Ehdr)`字节到`header_`结构体, 后续所有解析基于这个结构

```cpp
bool ElfReader::ReadElfHeader() {
    //读取header长度的内容复制到header_
  ssize_t rc = TEMP_FAILURE_RETRY(read(fd_, &header_, sizeof(header_)));
  if (rc < 0) {
    DL_ERR("can't read file \"%s\": %s", name_, strerror(errno));
    return false;
  }
  if (rc != sizeof(header_)) {
    DL_ERR("\"%s\" is too small to be an ELF executable", name_);
    return false;
  }
  return true;
}
```

#### ElfReader::VerifyElfHeader

校验ELF头的合法性: Magic Number(`\x7fELF`) → 32位(`ELFCLASS32`) → 小端序(`ELFDATA2LSB`) → 共享库(`ET_DYN`) → 版本号 → 目标架构(ARM/x86/MIPS)

```cpp
bool ElfReader::VerifyElfHeader() {
    // 校验Magic
  if (header_.e_ident[EI_MAG0] != ELFMAG0 ||
      header_.e_ident[EI_MAG1] != ELFMAG1 ||
      header_.e_ident[EI_MAG2] != ELFMAG2 ||
      header_.e_ident[EI_MAG3] != ELFMAG3) {
    DL_ERR("\"%s\" has bad ELF magic", name_);
    return false;
  }

    // Android 4.4只有32位模式
  if (header_.e_ident[EI_CLASS] != ELFCLASS32) {
    DL_ERR("\"%s\" not 32-bit: %d", name_, header_.e_ident[EI_CLASS]);
    return false;
  }
    // 必须小端序
  if (header_.e_ident[EI_DATA] != ELFDATA2LSB) {
    DL_ERR("\"%s\" not little-endian: %d", name_, header_.e_ident[EI_DATA]);
    return false;
  }

    // 必须是Shared Object文件
  if (header_.e_type != ET_DYN) {
    DL_ERR("\"%s\" has unexpected e_type: %d", name_, header_.e_type);
    return false;
  }

    // 当前版本
  if (header_.e_version != EV_CURRENT) {
    DL_ERR("\"%s\" has unexpected e_version: %d", name_, header_.e_version);
    return false;
  }

    // 校验e_machine
  if (header_.e_machine !=
#ifdef ANDROID_ARM_LINKER
      EM_ARM
#elif defined(ANDROID_MIPS_LINKER)
      EM_MIPS
#elif defined(ANDROID_X86_LINKER)
      EM_386
#endif
  ) {
    DL_ERR("\"%s\" has unexpected e_machine: %d", name_, header_.e_machine);
    return false;
  }

  return true;
}
```

### ElfReader::ReadProgramHeader

根据`e_phoff`和`e_phnum`定位程序头表(段表), 用`mmap`将其映射到内存。段表描述了SO中每个Segment的类型、偏移、地址和权限

```cpp
bool ElfReader::ReadProgramHeader() {
    // 段表的个数
  phdr_num_ = header_.e_phnum;

  // Like the kernel, we only accept program header tables that
  // are smaller than 64KiB.
  if (phdr_num_ < 1 || phdr_num_ > 65536/sizeof(Elf32_Phdr)) {
    DL_ERR("\"%s\" has invalid e_phnum: %d", name_, phdr_num_);
    return false;
  }

    // 段表的起始地址,结束地址,偏移
  Elf32_Addr page_min = PAGE_START(header_.e_phoff);
  Elf32_Addr page_max = PAGE_END(header_.e_phoff + (phdr_num_ * sizeof(Elf32_Phdr)));
  Elf32_Addr page_offset = PAGE_OFFSET(header_.e_phoff);

  phdr_size_ = page_max - page_min;

    // 映射段表至内存中
  void* mmap_result = mmap(NULL, phdr_size_, PROT_READ, MAP_PRIVATE, fd_, page_min);
  if (mmap_result == MAP_FAILED) {
    DL_ERR("\"%s\" phdr mmap failed: %s", name_, strerror(errno));
    return false;
  }

    // phdr_table_指向了段表在内存的起始地址
  phdr_mmap_ = mmap_result;
  phdr_table_ = reinterpret_cast<Elf32_Phdr*>(reinterpret_cast&lt;char*&gt;(mmap_result) + page_offset);
  return true;
}
```

### ElfReader::ReserveAddressSpace

计算SO映像需要的内存大小(通过`phdr_table_get_load_size`遍历所有`PT_LOAD`段), 然后用`mmap`匿名映射一块足够大的连续内存。`load_bias_`记录实际加载地址与默认虚拟地址的偏差, 后续重定位依赖这个值

```cpp
bool ElfReader::ReserveAddressSpace() {
  //此时段表已经加载至内存,接下来准备内存用于加载段
  Elf32_Addr min_vaddr;
  // 获取so加载至内存中的大小
  load_size_ = phdr_table_get_load_size(phdr_table_, phdr_num_, &min_vaddr);
  if (load_size_ == 0) {
    DL_ERR("\"%s\" has no loadable segments", name_);
    return false;
  }

  uint8_t* addr = reinterpret_cast<uint8_t*>(min_vaddr);
  int mmap_flags = MAP_PRIVATE | MAP_ANONYMOUS;
  // 匿名映射一块足够装下so的内存
  void* start = mmap(addr, load_size_, PROT_NONE, mmap_flags, -1, 0);
  if (start == MAP_FAILED) {
    DL_ERR("couldn't reserve %d bytes of address space for \"%s\"", load_size_, name_);
    return false;
  }

  load_start_ = start;
  load_bias_ = reinterpret_cast<uint8_t*>(start) - addr;
  return true;
}
```

#### phdr_table_get_load_size

遍历所有`PT_LOAD`段, 找出最小和最大虚拟地址, 页对齐后差值即为SO映射到内存需要的总大小

```cpp
size_t phdr_table_get_load_size(const Elf32_Phdr* phdr_table,
                                size_t phdr_count,
                                Elf32_Addr* out_min_vaddr,
                                Elf32_Addr* out_max_vaddr)
{
    Elf32_Addr min_vaddr = 0xFFFFFFFFU;
    Elf32_Addr max_vaddr = 0x00000000U;

    bool found_pt_load = false;
    // 遍历段表
    for (size_t i = 0; i < phdr_count; ++i) {
        const Elf32_Phdr* phdr = &phdr_table[i];
        // 只加载PT_LOAD段
        if (phdr->p_type != PT_LOAD) {
            continue;
        }
        found_pt_load = true;

        // 遍历所有的PT_LOAD段,寻找其中最小的一个起始虚拟地址
        if (phdr->p_vaddr < min_vaddr) {
            min_vaddr = phdr->p_vaddr;
        }

        // 遍历所有的PT_LOAD段,寻找其中最大的一个起始虚拟地址
        if (phdr->p_vaddr + phdr->p_memsz > max_vaddr) {
            max_vaddr = phdr->p_vaddr + phdr->p_memsz;
        }
    }
    if (!found_pt_load) {
        min_vaddr = 0x00000000U;
    }

    // 页对齐
    min_vaddr = PAGE_START(min_vaddr);
    max_vaddr = PAGE_END(max_vaddr);

    if (out_min_vaddr != NULL) {
        *out_min_vaddr = min_vaddr;
    }
    if (out_max_vaddr != NULL) {
        *out_max_vaddr = max_vaddr;
    }
    // 最大地址-最小地址=so映射至内存的大小
    return max_vaddr - min_vaddr;
}
```

### ElfReader::LoadSegments

ReserveAddressSpace只是申请内存,这里才是实际加载段的地方

```cpp
bool ElfReader::LoadSegments() {
  // 遍历段表,加载PT_LOAD段
  for (size_t i = 0; i < phdr_num_; ++i) {
    const Elf32_Phdr* phdr = &phdr_table_[i];

    if (phdr->p_type != PT_LOAD) {
      continue;
    }

    // Segment addresses in memory.
    Elf32_Addr seg_start = phdr->p_vaddr + load_bias_;
    Elf32_Addr seg_end   = seg_start + phdr->p_memsz;
    // 段的起始地址和节数地址(页对齐)
    Elf32_Addr seg_page_start = PAGE_START(seg_start);
    Elf32_Addr seg_page_end   = PAGE_END(seg_end);

    Elf32_Addr seg_file_end   = seg_start + phdr->p_filesz;

    // File offsets.
    Elf32_Addr file_start = phdr->p_offset;
    Elf32_Addr file_end   = file_start + phdr->p_filesz;

    Elf32_Addr file_page_start = PAGE_START(file_start);
    Elf32_Addr file_length = file_end - file_page_start;

    if (file_length != 0) {
      // 以内存对齐的方式映射段至内存中
      void* seg_addr = mmap((void*)seg_page_start,
                            file_length,
                            PFLAGS_TO_PROT(phdr->p_flags),
                            MAP_FIXED|MAP_PRIVATE,
                            fd_,
                            file_page_start);
      if (seg_addr == MAP_FAILED) {
        DL_ERR("couldn't map \"%s\" segment %d: %s", name_, i, strerror(errno));
        return false;
      }
    }

    // 如果该段可写,并且文件大小并不按照页对齐,则将页内没有和文件对应的部分置零
    // 疑惑:(为什么不直接初始化所有内存区域为0,为了节省时间吗?)
    // if the segment is writable, and does not end on a page boundary,
    // zero-fill it until the page limit.
    if ((phdr->p_flags & PF_W) != 0 && PAGE_OFFSET(seg_file_end) > 0) {
      memset((void*)seg_file_end, 0, PAGE_SIZE - PAGE_OFFSET(seg_file_end));
    }

    seg_file_end = PAGE_END(seg_file_end);

    // 如果段指定的内存大小超出了文件映射的页面,则对多出的页进行匿名映射,防止出现Bus error
    // 此处应是用于.bss等段的特殊处理,这种段文件大小=0,但内存大小可能占据好几个页
    // seg_file_end is now the first page address after the file
    // content. If seg_end is larger, we need to zero anything
    // between them. This is done by using a private anonymous
    // map for all extra pages.
    if (seg_page_end > seg_file_end) {
      void* zeromap = mmap((void*)seg_file_end,
                           seg_page_end - seg_file_end,
                           PFLAGS_TO_PROT(phdr->p_flags),
                           MAP_FIXED|MAP_ANONYMOUS|MAP_PRIVATE,
                           -1,
                           0);
      if (zeromap == MAP_FAILED) {
        DL_ERR("couldn't zero fill \"%s\" gap: %s", name_, strerror(errno));
        return false;
      }
    }
  }
  return true;
}
```

上述流程将一个SO的PT_LOAD段加载到内存中,而这之后还需要进行链接和重定位操作才能使用so

## Linker Link So

### load_library

在Linker Load SO过程中,起点是load_library函数,调用了elf_reader.Load()

```cpp
static soinfo* load_library(const char* name) {
    // 1.打开so文件,获取文件描述符fd
    int fd = open_library(name);
    if (fd == -1) {
        DL_ERR("library \"%s\" not found", name);
        return NULL;
    }

    // 2.创建ElfReader对象,并调用load方法
    ElfReader elf_reader(name, fd);
    if (!elf_reader.Load()) {
        return NULL;
    }

    // 3.生成soinfo,并根据elf_reader结果赋值
    const char* bname = strrchr(name, '/');
    soinfo* si = soinfo_alloc(bname ? bname + 1 : name);
    if (si == NULL) {
        return NULL;
    }
    si->base = elf_reader.load_start();
    si->size = elf_reader.load_size();
    si->load_bias = elf_reader.load_bias();
    si->flags = 0;
    si->entry = 0;
    si->dynamic = NULL;
    si->phnum = elf_reader.phdr_count();
    si->phdr = elf_reader.loaded_phdr();
    return si;
}
```

### find_library_internal

load_library的上层是find_library_internal

该函数在调用load_library加载so后调用了soinfo_link_image进行链接操作,接下来学习链接相关代码

```cpp
static soinfo* find_library_internal(const char* name) {
  if (name == NULL) {
    return somain;
  }
    //1. 查询该so是否加载过,加载过的so位于已加载列表,无需二次加载
  soinfo* si = find_loaded_library(name);
  if (si != NULL) {
    if (si->flags & FLAG_LINKED) {
      return si;
    }
    DL_ERR("OOPS: recursive link to \"%s\"", si->name);
    return NULL;
  }

  TRACE("[ '%s' has not been loaded yet.  Locating...]", name);
    //2. 调用load_library加载so
  si = load_library(name);
  if (si == NULL) {
    return NULL;
  }

  // At this point we know that whatever is loaded @ base is a valid ELF
  // shared library whose segments are properly mapped in.
  TRACE("[ init_library base=0x%08x sz=0x%08x name='%s' ]",
        si->base, si->size, si->name);

    //3. 链接so
  if (!soinfo_link_image(si)) {
    munmap(reinterpret_cast&lt;void*&gt;(si->base), si->size);
    soinfo_free(si);
    return NULL;
  }

  return si;
}
```

### soinfo_link_image

https://cs.android.com/android/platform/superproject/+/android-4.4.4_r1:bionic/linker/linker.cpp#1303

- 遍历段表,寻找Dynamic段
- 遍历dynamic段,获取相关信息
- 遍历dynamic段,进行链接,处理so的依赖
- 进行重定位

```cpp
static bool soinfo_link_image(soinfo* si) {
    /* "base" might wrap around UINT32_MAX. */
    // 获取基址,段表指针,段表数目
    Elf32_Addr base = si->load_bias;
    const Elf32_Phdr *phdr = si->phdr;
    int phnum = si->phnum;
    bool relocating_linker = (si->flags & FLAG_LINKER) != 0;

    /* We can't debug anything until the linker is relocated */
    if (!relocating_linker) {
        INFO("[ linking %s ]", si->name);
        DEBUG("si->base = 0x%08x si->flags = 0x%08x", si->base, si->flags);
    }

    /* Extract dynamic section */
    size_t dynamic_count;
    Elf32_Word dynamic_flags;
    // 遍历段表,寻找PT_DYNAMIC段
    phdr_table_get_dynamic_section(phdr, phnum, base, &si->dynamic,
                                   &dynamic_count, &dynamic_flags);
    if (si->dynamic == NULL) {
        if (!relocating_linker) {
            DL_ERR("missing PT_DYNAMIC in \"%s\"", si->name);
        }
        return false;
    } else {
        if (!relocating_linker) {
            DEBUG("dynamic = %p", si->dynamic);
        }
    }

#ifdef ANDROID_ARM_LINKER
    // 异常处理相关
    (void) phdr_table_get_arm_exidx(phdr, phnum, base,
                                    &si->ARM_exidx, &si->ARM_exidx_count);
#endif

    // Extract useful information from dynamic section.
    // 遍历Dynamic段
    uint32_t needed_count = 0;
    for (Elf32_Dyn* d = si->dynamic; d->d_tag != DT_NULL; ++d) {
        DEBUG("d = %p, d[0](tag) = 0x%08x d[1](val) = 0x%08x", d, d->d_tag, d->d_un.d_val);
        switch(d->d_tag){
        // 哈希表,记录导出函数
        case DT_HASH:
            si->nbucket = ((unsigned *) (base + d->d_un.d_ptr))[0];
            si->nchain = ((unsigned *) (base + d->d_un.d_ptr))[1];
            si->bucket = (unsigned *) (base + d->d_un.d_ptr + 8);
            si->chain = (unsigned *) (base + d->d_un.d_ptr + 8 + si->nbucket * 4);
            break;
        // 字符串表
        case DT_STRTAB:
            si->strtab = (const char *) (base + d->d_un.d_ptr);
            break;
        // 符号表
        case DT_SYMTAB:
            si->symtab = (Elf32_Sym *) (base + d->d_un.d_ptr);
            break;
        // PLTREL类型的重定位表,未做处理
        case DT_PLTREL:
            if (d->d_un.d_val != DT_REL) {
                DL_ERR("unsupported DT_RELA in \"%s\"", si->name);
                return false;
            }
            break;
        // JMPREL类型的重定位表
        case DT_JMPREL:
            si->plt_rel = (Elf32_Rel*) (base + d->d_un.d_ptr);
            break;
           // plt重定位表大小
        case DT_PLTRELSZ:
            si->plt_rel_count = d->d_un.d_val / sizeof(Elf32_Rel);
            break;
        // rel重定位表
        case DT_REL:
            si->rel = (Elf32_Rel*) (base + d->d_un.d_ptr);
            break;
        // rel重定位表大小
        case DT_RELSZ:
            si->rel_count = d->d_un.d_val / sizeof(Elf32_Rel);
            break;
        // GOT全局偏移量表,和PLT延迟绑定有关
        case DT_PLTGOT:
            /* Save this in case we decide to do lazy binding. We don't yet. */
            si->plt_got = (unsigned *)(base + d->d_un.d_ptr);
            break;
        // 调试相关
        case DT_DEBUG:
            // Set the DT_DEBUG entry to the address of _r_debug for GDB
            // if the dynamic table is writable
            if ((dynamic_flags & PF_W) != 0) {
                d->d_un.d_val = (int) &_r_debug;
            }
            break;
         // RELA类型重定位表
         case DT_RELA:
            DL_ERR("unsupported DT_RELA in \"%s\"", si->name);
            return false;
        // init初始化函数
        case DT_INIT:
            si->init_func = reinterpret_cast<linker_function_t>(base + d->d_un.d_ptr);
            DEBUG("%s constructors (DT_INIT) found at %p", si->name, si->init_func);
            break;
        // finit析构函数
        case DT_FINI:
            si->fini_func = reinterpret_cast<linker_function_t>(base + d->d_un.d_ptr);
            DEBUG("%s destructors (DT_FINI) found at %p", si->name, si->fini_func);
            break;
        // init_array 初始化函数列表
        case DT_INIT_ARRAY:
            si->init_array = reinterpret_cast<linker_function_t*>(base + d->d_un.d_ptr);
            DEBUG("%s constructors (DT_INIT_ARRAY) found at %p", si->name, si->init_array);
            break;
        // init_array大小
        case DT_INIT_ARRAYSZ:
            si->init_array_count = ((unsigned)d->d_un.d_val) / sizeof(Elf32_Addr);
            break;
        // fini_array 析构函数列表
        case DT_FINI_ARRAY:
            si->fini_array = reinterpret_cast<linker_function_t*>(base + d->d_un.d_ptr);
            DEBUG("%s destructors (DT_FINI_ARRAY) found at %p", si->name, si->fini_array);
            break;
        // 析构函数列表大小
        case DT_FINI_ARRAYSZ:
            si->fini_array_count = ((unsigned)d->d_un.d_val) / sizeof(Elf32_Addr);
            break;
        // preinit_array 也是初始化函数列表,和init_array不同,大多只出现在可执行文件中,so一般没有
        case DT_PREINIT_ARRAY:
            si->preinit_array = reinterpret_cast<linker_function_t*>(base + d->d_un.d_ptr);
            DEBUG("%s constructors (DT_PREINIT_ARRAY) found at %p", si->name, si->preinit_array);
            break;
        // preinit_array大小
        case DT_PREINIT_ARRAYSZ:
            si->preinit_array_count = ((unsigned)d->d_un.d_val) / sizeof(Elf32_Addr);
            break;
        case DT_TEXTREL:
            si->has_text_relocations = true;
            break;
        case DT_SYMBOLIC:
            si->has_DT_SYMBOLIC = true;
            break;
        // so的依赖
        case DT_NEEDED:
            ++needed_count;
            break;
#if defined DT_FLAGS
        // TODO: why is DT_FLAGS not defined?
        case DT_FLAGS:
            if (d->d_un.d_val & DF_TEXTREL) {
                si->has_text_relocations = true;
            }
            if (d->d_un.d_val & DF_SYMBOLIC) {
                si->has_DT_SYMBOLIC = true;
            }
            break;
#endif
#if defined(ANDROID_MIPS_LINKER)
    ......
#endif
        }
    }
    ......
    // 开始进行so的依赖处理,即链接
    // 开辟soinfo空间,用于处理so的依赖
    soinfo** needed = (soinfo**) alloca((1 + needed_count) * sizeof(soinfo*));
    soinfo** pneeded = needed;
    // 再次遍历dynamic段,查找DT_NEEDED表项
    for (Elf32_Dyn* d = si->dynamic; d->d_tag != DT_NULL; ++d) {
        if (d->d_tag == DT_NEEDED) {
            const char* library_name = si->strtab + d->d_un.d_val;
            DEBUG("%s needs %s", si->name, library_name);
            // 查找并处理依赖,已经加载直接返回,未加载则加载
            soinfo* lsi = find_library(library_name);
            if (lsi == NULL) {
                strlcpy(tmp_err_buf, linker_get_error_buffer(), sizeof(tmp_err_buf));
                DL_ERR("could not load library \"%s\" needed by \"%s\"; caused by %s",
                       library_name, si->name, tmp_err_buf);
                return false;
            }
            *pneeded++ = lsi;
        }
    }
    *pneeded = NULL;

    // so的依赖处理完毕,开始进行重定位

    if (si->has_text_relocations) {
        ......
    }

    // 进行重定位,通过soinfo_relocate
    if (si->plt_rel != NULL) {
        DEBUG("[ relocating %s plt ]", si->name );
        if (soinfo_relocate(si, si->plt_rel, si->plt_rel_count, needed)) {
            return false;
        }
    }
    // 进行重定位
    if (si->rel != NULL) {
        DEBUG("[ relocating %s ]", si->name );
        if (soinfo_relocate(si, si->rel, si->rel_count, needed)) {
            return false;
        }
    }

#ifdef ANDROID_MIPS_LINKER
    if (!mips_relocate_got(si, needed)) {
        return false;
    }
#endif

    // 设置linked标识,表示已经进行链接
    si->flags |= FLAG_LINKED;
    DEBUG("[ finished linking %s ]", si->name);

    if (si->has_text_relocations) {
        /* All relocations are done, we can protect our segments back to
         * read-only. */
        if (phdr_table_protect_segments(si->phdr, si->phnum, si->load_bias) < 0) {
            DL_ERR("can't protect segments for \"%s\": %s",
                   si->name, strerror(errno));
            return false;
        }
    }

    /* We can also turn on GNU RELRO protection */
    if (phdr_table_protect_gnu_relro(si->phdr, si->phnum, si->load_bias) < 0) {
        DL_ERR("can't enable GNU RELRO protection for \"%s\": %s",
               si->name, strerror(errno));
        return false;
    }

    notify_gdb_of_load(si);
    return true;
}
```

## Linker Relocate So

链接完成后进入重定位阶段, 修正SO代码和数据中的所有地址引用

### soinfo_relocate

核心重定位函数, 在`soinfo_link_image`中被调用两次: 一次处理`.plt.rel`(函数调用), 一次处理`.rel`(数据引用)。对每个重定位条目: 提取类型和符号索引 → 如果需要符号则通过`soinfo_do_lookup`从依赖库查找 → 根据类型(JUMP_SLOT/GLOB_DAT/ABS32/RELATIVE等)计算目标地址并回填

```cpp
/* TODO: don't use unsigned for addrs below. It works, but is not
 * ideal. They should probably be either uint32_t, Elf32_Addr, or unsigned
 * long.
 */
static int soinfo_relocate(soinfo* si, Elf32_Rel* rel, unsigned count,
                           soinfo* needed[])
{
    // 获取符号表和字符串表,定义相关变量
    Elf32_Sym* symtab = si->symtab;
    const char* strtab = si->strtab;
    Elf32_Sym* s;
    Elf32_Rel* start = rel;
    soinfo* lsi;

    // 遍历重定位表
    for (size_t idx = 0; idx < count; ++idx, ++rel) {
        // 获取重定位类型
        unsigned type = ELF32_R_TYPE(rel->r_info);
        // 获取重定位符号
        unsigned sym = ELF32_R_SYM(rel->r_info);
        // 计算重定位地址 reloc = (real_base-default_base)+offset = load_bias+offset
        Elf32_Addr reloc = static_cast<Elf32_Addr>(rel->r_offset + si->load_bias);
        Elf32_Addr sym_addr = 0;
        char* sym_name = NULL;

        DEBUG("Processing '%s' relocation at index %d", si->name, idx);
        if (type == 0) { // R_*_NONE
            continue;
        }
        if (sym != 0) {
            // 若sym为0则无需使用符号重定位;若sym不为0,说明需要用符号进行重定位,先获取符号名
            sym_name = (char *)(strtab + symtab[sym].st_name);
            // 根据符号名从所有依赖的so中查找需要的符号
            // soinfo_do_lookup: 通过符号,根据哈希表查询对应符号地址
            s = soinfo_do_lookup(si, sym_name, &lsi, needed);
            if (s == NULL) {
                /* We only allow an undefined symbol if this is a weak
                   reference..   */
                // 没有从依赖中找到so,则从自身符号表查找符号
                s = &symtab[sym];
                if (ELF32_ST_BIND(s->st_info) != STB_WEAK) {
                    DL_ERR("cannot locate symbol \"%s\" referenced by \"%s\"...", sym_name, si->name);
                    return -1;
                }

                /* IHI0044C AAELF 4.5.1.1:

                   Libraries are not searched to resolve weak references.
                   It is not an error for a weak reference to remain
                   unsatisfied.

                   During linking, the value of an undefined weak reference is:
                   - Zero if the relocation type is absolute
                   - The address of the place if the relocation is pc-relative
                   - The address of nominal base address if the relocation
                     type is base-relative.
                  */

                // 如果符号不是外部符号而是内部符号,只能是以下几种重定位类型
                switch (type) {
#if defined(ANDROID_ARM_LINKER)
                case R_ARM_JUMP_SLOT:
                case R_ARM_GLOB_DAT:
                case R_ARM_ABS32:
                case R_ARM_RELATIVE:    /* Don't care. */
#elif defined(ANDROID_X86_LINKER)
                case R_386_JMP_SLOT:
                case R_386_GLOB_DAT:
                case R_386_32:
                case R_386_RELATIVE:    /* Dont' care. */
#endif /* ANDROID_*_LINKER */
                    /* sym_addr was initialized to be zero above or relocation
                       code below does not care about value of sym_addr.
                       No need to do anything.  */
                    break;

#if defined(ANDROID_X86_LINKER)
                case R_386_PC32:
                    sym_addr = reloc;
                    break;
#endif /* ANDROID_X86_LINKER */

#if defined(ANDROID_ARM_LINKER)
                case R_ARM_COPY:
                    /* Fall through.  Can't really copy if weak symbol is
                       not found in run-time.  */
#endif /* ANDROID_ARM_LINKER */
                default:
                    DL_ERR("unknown weak reloc type %d @ %p (%d)",
                                 type, rel, (int) (rel - start));
                    return -1;
                }
            } else {
                /* We got a definition.  */
#if 0
                if ((base == 0) && (si->base != 0)) {
                        /* linking from libraries to main image is bad */
                    DL_ERR("cannot locate \"%s\"...",
                           strtab + symtab[sym].st_name);
                    return -1;
                }
#endif
                // 通过依赖so成功查找到符号,获取外部符号地址
                sym_addr = static_cast<Elf32_Addr>(s->st_value + lsi->load_bias);
            }
            count_relocation(kRelocSymbol);
        } else {
            // sym为0,当前重定位无需使用符号
            s = NULL;
        }

/* TODO: This is ugly. Split up the relocations by arch into
 * different files.
 */
        // 根据重定位类型进行不同处理
        switch(type){
#if defined(ANDROID_ARM_LINKER)
        case R_ARM_JUMP_SLOT:
            count_relocation(kRelocAbsolute);
            MARK(rel->r_offset);
            TRACE_TYPE(RELO, "RELO JMP_SLOT %08x <- %08x %s", reloc, sym_addr, sym_name);
            // 直接将待重定位处填充符号地址
            *reinterpret_cast<Elf32_Addr*>(reloc) = sym_addr;
            break;
        case R_ARM_GLOB_DAT:
            count_relocation(kRelocAbsolute);
            MARK(rel->r_offset);
            TRACE_TYPE(RELO, "RELO GLOB_DAT %08x <- %08x %s", reloc, sym_addr, sym_name);
            // 直接将待重定位处填充符号地址,同上
            *reinterpret_cast<Elf32_Addr*>(reloc) = sym_addr;
            break;
        case R_ARM_ABS32:
            count_relocation(kRelocAbsolute);
            MARK(rel->r_offset);
            TRACE_TYPE(RELO, "RELO ABS %08x <- %08x %s", reloc, sym_addr, sym_name);
            // 读出待重定位处的数据,和符号地址相加后回填
            *reinterpret_cast<Elf32_Addr*>(reloc) += sym_addr;
            break;
        case R_ARM_REL32:
            count_relocation(kRelocRelative);
            MARK(rel->r_offset);
            TRACE_TYPE(RELO, "RELO REL32 %08x <- %08x - %08x %s",
                       reloc, sym_addr, rel->r_offset, sym_name);
            // 读出待重定位处的数据,和符号地址相加,减去重定位地址,最后回填
            *reinterpret_cast<Elf32_Addr*>(reloc) += sym_addr - rel->r_offset;
            break;
// x86架构下linker的重定位,同arm类似
#elif defined(ANDROID_X86_LINKER)
        case R_386_JMP_SLOT:
            count_relocation(kRelocAbsolute);
            MARK(rel->r_offset);
            TRACE_TYPE(RELO, "RELO JMP_SLOT %08x <- %08x %s", reloc, sym_addr, sym_name);
            *reinterpret_cast<Elf32_Addr*>(reloc) = sym_addr;
            break;
        case R_386_GLOB_DAT:
            count_relocation(kRelocAbsolute);
            MARK(rel->r_offset);
            TRACE_TYPE(RELO, "RELO GLOB_DAT %08x <- %08x %s", reloc, sym_addr, sym_name);
            *reinterpret_cast<Elf32_Addr*>(reloc) = sym_addr;
            break;
#elif defined(ANDROID_MIPS_LINKER)
    case R_MIPS_REL32:
            count_relocation(kRelocAbsolute);
            MARK(rel->r_offset);
            TRACE_TYPE(RELO, "RELO REL32 %08x <- %08x %s",
                       reloc, sym_addr, (sym_name) ? sym_name : "*SECTIONHDR*");
            if (s) {
                *reinterpret_cast<Elf32_Addr*>(reloc) += sym_addr;
            } else {
                *reinterpret_cast<Elf32_Addr*>(reloc) += si->base;
            }
            break;
#endif /* ANDROID_*_LINKER */

#if defined(ANDROID_ARM_LINKER)
        case R_ARM_RELATIVE:
#elif defined(ANDROID_X86_LINKER)
        case R_386_RELATIVE:
#endif /* ANDROID_*_LINKER */
            count_relocation(kRelocRelative);
            MARK(rel->r_offset);
            if (sym) {
                DL_ERR("odd RELATIVE form...");
                return -1;
            }
            TRACE_TYPE(RELO, "RELO RELATIVE %08x <- +%08x", reloc, si->base);
            // 相对重定位,读出待重定位处数据,和so的基址相加并回填
            *reinterpret_cast<Elf32_Addr*>(reloc) += si->base;
            break;

#if defined(ANDROID_X86_LINKER)
        case R_386_32:
            count_relocation(kRelocRelative);
            MARK(rel->r_offset);

            TRACE_TYPE(RELO, "RELO R_386_32 %08x <- +%08x %s", reloc, sym_addr, sym_name);
            *reinterpret_cast<Elf32_Addr*>(reloc) += sym_addr;
            break;

        case R_386_PC32:
            count_relocation(kRelocRelative);
            MARK(rel->r_offset);
            TRACE_TYPE(RELO, "RELO R_386_PC32 %08x <- +%08x (%08x - %08x) %s",
                       reloc, (sym_addr - reloc), sym_addr, reloc, sym_name);
            *reinterpret_cast<Elf32_Addr*>(reloc) += (sym_addr - reloc);
            break;
#endif /* ANDROID_X86_LINKER */

#ifdef ANDROID_ARM_LINKER
        case R_ARM_COPY:
              ...... // 进行部分错误处理
            break;
#endif /* ANDROID_ARM_LINKER */

        default:
            DL_ERR("unknown reloc type %d @ %p (%d)",
                   type, rel, (int) (rel - start));
            return -1;
        }
    }
    return 0;
}
```

### soinfo_do_lookup

符号查找的总调度函数。查找顺序: 主可执行文件 → 自身(如果有`DT_SYMBOLIC`) → 预加载库(`LD_PRELOAD`) → 依赖库(`DT_NEEDED`列表)。内部通过`soinfo_elf_lookup`使用SysV Hash表在各个soinfo中查找符号

其中`soinfo_elf_lookup`通过`elfhash`计算符号名的hash值, `bucket[hash % nbucket]`定位桶, 沿`chain`链逐个`strcmp`比较

```cpp
static Elf32_Sym* soinfo_elf_lookup(soinfo* si, unsigned hash, const char* name) {
    Elf32_Sym* symtab = si->symtab;
    const char* strtab = si->strtab;

    TRACE_TYPE(LOOKUP, "SEARCH %s in %s@0x%08x %08x %d",
               name, si->name, si->base, hash, hash % si->nbucket);

    for (unsigned n = si->bucket[hash % si->nbucket]; n != 0; n = si->chain[n]) {
        Elf32_Sym* s = symtab + n;
        if (strcmp(strtab + s->st_name, name)) continue;

            /* only concern ourselves with global and weak symbol definitions */
        switch(ELF32_ST_BIND(s->st_info)){
        case STB_GLOBAL:
        case STB_WEAK:
            if (s->st_shndx == SHN_UNDEF) {
                continue;
            }

            TRACE_TYPE(LOOKUP, "FOUND %s in %s (%08x) %d",
                       name, si->name, s->st_value, s->st_size);
            return s;
        }
    }

    return NULL;
}

static unsigned elfhash(const char* _name) {
    const unsigned char* name = (const unsigned char*) _name;
    unsigned h = 0, g;

    while(*name) {
        h = (h << 4) + *name++;
        g = h & 0xf0000000;
        h ^= g;
        h ^= g >> 24;
    }
    return h;
}

static Elf32_Sym* soinfo_do_lookup(soinfo* si, const char* name, soinfo** lsi, soinfo* needed[]) {
    unsigned elf_hash = elfhash(name);
    Elf32_Sym* s = NULL;

    if (si != NULL && somain != NULL) {

        /*
         * Local scope is executable scope. Just start looking into it right away
         * for the shortcut.
         */

        if (si == somain) {
            s = soinfo_elf_lookup(si, elf_hash, name);
            if (s != NULL) {
                *lsi = si;
                goto done;
            }
        } else {
            /* Order of symbol lookup is controlled by DT_SYMBOLIC flag */

            /*
             * If this object was built with symbolic relocations disabled, the
             * first place to look to resolve external references is the main
             * executable.
             */

            if (!si->has_DT_SYMBOLIC) {
                DEBUG("%s: looking up %s in executable %s",
                      si->name, name, somain->name);
                s = soinfo_elf_lookup(somain, elf_hash, name);
                if (s != NULL) {
                    *lsi = somain;
                    goto done;
                }
            }

            /* Look for symbols in the local scope (the object who is
             * searching). This happens with C++ templates on i386 for some
             * reason.
             *
             * Notes on weak symbols:
             * The ELF specs are ambiguous about treatment of weak definitions in
             * dynamic linking.  Some systems return the first definition found
             * and some the first non-weak definition.   This is system dependent.
             * Here we return the first definition found for simplicity.  */

            s = soinfo_elf_lookup(si, elf_hash, name);
            if (s != NULL) {
                *lsi = si;
                goto done;
            }

            /*
             * If this object was built with -Bsymbolic and symbol is not found
             * in the local scope, try to find the symbol in the main executable.
             */

            if (si->has_DT_SYMBOLIC) {
                DEBUG("%s: looking up %s in executable %s after local scope",
                      si->name, name, somain->name);
                s = soinfo_elf_lookup(somain, elf_hash, name);
                if (s != NULL) {
                    *lsi = somain;
                    goto done;
                }
            }
        }
    }

    /* Next, look for it in the preloads list */
    for (int i = 0; gLdPreloads[i] != NULL; i++) {
        s = soinfo_elf_lookup(gLdPreloads[i], elf_hash, name);
        if (s != NULL) {
            *lsi = gLdPreloads[i];
            goto done;
        }
    }

    for (int i = 0; needed[i] != NULL; i++) {
        DEBUG("%s: looking up %s in %s",
              si->name, name, needed[i]->name);
        s = soinfo_elf_lookup(needed[i], elf_hash, name);
        if (s != NULL) {
            *lsi = needed[i];
            goto done;
        }
    }

done:
    if (s != NULL) {
        TRACE_TYPE(LOOKUP, "si %s sym %s s->st_value = 0x%08x, "
                   "found in %s, base = 0x%08x, load bias = 0x%08x",
                   si->name, name, s->st_value,
                   (*lsi)->name, (*lsi)->base, (*lsi)->load_bias);
        return s;
    }

    return NULL;
}
```

### do_dlopen

回到do_dlopen,在调用find_library以及后续的加载,链接,重定位操作后

调用了soinfo的CallConstructors()函数

```cpp
soinfo* do_dlopen(const char* name, int flags) {
  if ((flags & ~(RTLD_NOW|RTLD_LAZY|RTLD_LOCAL|RTLD_GLOBAL)) != 0) {
    DL_ERR("invalid flags to dlopen: %x", flags);
    return NULL;
  }
  set_soinfo_pool_protection(PROT_READ | PROT_WRITE);
  soinfo* si = find_library(name);
  if (si != NULL) {
    si->CallConstructors();
  }
  set_soinfo_pool_protection(PROT_READ);
  return si;
}
```

### soinfo::CallConstructors

该函数的作用如下

- 判断是否调用过该so的构造函数,调用过则无需重复调用
- 遍历该so的dynamic段,调用该so依赖的so的构造函数
- 调用该so的init和init_array

https://cs.android.com/android/platform/superproject/+/android-4.4.4_r1:bionic/linker/linker.cpp#1192

```cpp
void soinfo::CallConstructors() {
    //1. 已调用过构造函数则无需调用
  if (constructors_called) {
    return;
  }

  // We set constructors_called before actually calling the constructors, otherwise it doesn't
  // protect against recursive constructor calls. One simple example of constructor recursion
  // is the libc debug malloc, which is implemented in libc_malloc_debug_leak.so:
  // 1. The program depends on libc, so libc's constructor is called here.
  // 2. The libc constructor calls dlopen() to load libc_malloc_debug_leak.so.
  // 3. dlopen() calls the constructors on the newly created
  //    soinfo for libc_malloc_debug_leak.so.
  // 4. The debug .so depends on libc, so CallConstructors is
  //    called again with the libc soinfo. If it doesn't trigger the early-
  //    out above, the libc constructor will be called again (recursively!).
  constructors_called = true;

  if ((flags & FLAG_EXE) == 0 && preinit_array != NULL) {
    // The GNU dynamic linker silently ignores these, but we warn the developer.
    PRINT("\"%s\": ignoring %d-entry DT_PREINIT_ARRAY in shared library!",
          name, preinit_array_count);
  }
    //2. 遍历dynamic段,获取该so依赖的so名称
  if (dynamic != NULL) {
    for (Elf32_Dyn* d = dynamic; d->d_tag != DT_NULL; ++d) {
      if (d->d_tag == DT_NEEDED) {
        const char* library_name = strtab + d->d_un.d_val;
        TRACE("\"%s\": calling constructors in DT_NEEDED \"%s\"", name, library_name);
        // 由于之前已经加载过so依赖的so,此处通过find_loaded_library直接获取他们的soinfo并调用构造函数
        find_loaded_library(library_name)->CallConstructors();
      }
    }
  }

  TRACE("\"%s\": calling constructors", name);
  //3. 调用init和init_array
  // DT_INIT should be called before DT_INIT_ARRAY if both are present.
  // init在init_array之前被调用
  CallFunction("DT_INIT", init_func);
  CallArray("DT_INIT_ARRAY", init_array, init_array_count, false);
}
```

### soinfo::CallFunction

调用单个初始化/析构函数。跳过NULL和-1(无效地址), 调用完成后重新设置`soinfo_pool`为可写(因为被调用的函数可能调用了`dlopen`/`dlclose`修改了数据结构)

```cpp
void soinfo::CallFunction(const char* function_name UNUSED, linker_function_t function) {
  if (function == NULL || reinterpret_cast<uintptr_t>(function) == static_cast<uintptr_t>(-1)) {
    return;
  }

  TRACE("[ Calling %s @ %p for '%s' ]", function_name, function, name);
  function();
  TRACE("[ Done calling %s @ %p for '%s' ]", function_name, function, name);

  // The function may have called dlopen(3) or dlclose(3), so we need to ensure our data structures
  // are still writable. This happens with our debug malloc (see http://b/7941716).
  set_soinfo_pool_protection(PROT_READ | PROT_WRITE);
}
```

### soinfo::CallArray

遍历函数指针数组(如`init_array`), 逐个调用`CallFunction`。支持正序/逆序遍历(init正序, fini逆序)

```cpp
void soinfo::CallArray(const char* array_name UNUSED, linker_function_t* functions, size_t count, bool reverse) {
  if (functions == NULL) {
    return;
  }

  TRACE("[ Calling %s (size %d) @ %p for '%s' ]", array_name, count, functions, name);

  int begin = reverse ? (count - 1) : 0;
  int end = reverse ? -1 : count;
  int step = reverse ? -1 : 1;

  for (int i = begin; i != end; i += step) {
    TRACE("[ %s[%d] == %p ]", array_name, i, functions[i]);
    CallFunction("function", functions[i]);
  }

  TRACE("[ Done calling %s for '%s' ]", array_name, name);
}
```

# 0x8 Linker Load So64 详解

64位 linker (Android 10.0.0_r47) 在 32 位的基础上新增了命名空间隔离、批量加载、随机序等特性

## Java Level

与32位流程类似, 但调用链略有差异: `loadLibrary` → `loadLibrary0` → `nativeLoad`

### System.loadLibrary

Android 10的入口与4.4基本一致, 调用`loadLibrary0`替代了旧版的`loadLibrary`

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:libcore/ojluni/src/main/java/java/lang/System.java

```java
   @CallerSensitive
    public static void loadLibrary(String libname) {
        Runtime.getRuntime().loadLibrary0(Reflection.getCallerClass(), libname);
    }
```

### Rumtime. loadLibrary0

与32位的`loadLibrary`功能相同: 通过ClassLoader查找SO真实路径, 然后调用`nativeLoad`进入Native层。新增了`BootClassLoader`的特殊处理

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:libcore/ojluni/src/main/java/java/lang/Runtime.java

```java
    void loadLibrary0(Class<?> fromClass, String libname) {
        ClassLoader classLoader = ClassLoader.getClassLoader(fromClass);
        loadLibrary0(classLoader, fromClass, libname);
    }
    private synchronized void loadLibrary0(ClassLoader loader, Class<?> callerClass, String libname) {
        if (libname.indexOf((int)File.separatorChar) != -1) {
            throw new UnsatisfiedLinkError(
    "Directory separator should not appear in library name: " + libname);
        }
        String libraryName = libname;
        // Android-note: BootClassLoader doesn't implement findLibrary(). http://b/111850480
        // Android's class.getClassLoader() can return BootClassLoader where the RI would
        // have returned null; therefore we treat BootClassLoader the same as null here.
        if (loader != null && !(loader instanceof BootClassLoader)) {
            // 1. 调用findLibrary搜索so真实库名
            String filename = loader.findLibrary(libraryName);
            if (filename == null) {
                // It's not necessarily true that the ClassLoader used
                // System.mapLibraryName, but the default setup does, and it's
                // misleading to say we didn't find "libMyLibrary.so" when we
                // actually searched for "liblibMyLibrary.so.so".
                throw new UnsatisfiedLinkError(loader + " couldn't find \"" +
                                               System.mapLibraryName(libraryName) + "\"");
            }
            //2. 调用nativeLoad加载so
            String error = nativeLoad(filename, loader);
            if (error != null) {
                throw new UnsatisfiedLinkError(error);
            }
            return;
        }

        // We know some apps use mLibPaths directly, potentially assuming it's not null.
        // Initialize it here to make sure apps see a non-null value.
        getLibPaths();
        String filename = System.mapLibraryName(libraryName);
        //3. 通过其他路径搜索并加载so
        String error = nativeLoad(filename, loader, callerClass);
        if (error != null) {
            throw new UnsatisfiedLinkError(error);
        }
    }
```

## JNI Level

Java层进入Native层的边界。与32位不同, Android 10多了一层`JVM_NativeLoad`跳转

### nativeLoad

native函数声明, 内部转发到三参数版本

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:libcore/ojluni/src/main/java/java/lang/Runtime.java#1114

```java
private static String nativeLoad(String filename, ClassLoader loader) {
    return nativeLoad(filename, loader, null);
}
private static native String nativeLoad(String filename, ClassLoader loader, Class<?> caller);
```

### Runtime_nativeLoad

`nativeLoad`的JNI实现。直接转发给`JVM_NativeLoad`, 这是Android 10新增的一层跳转

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:libcore/ojluni/src/main/native/Runtime.c

```cpp
JNIEXPORT jstring JNICALL
Runtime_nativeLoad(JNIEnv* env, jclass ignored, jstring javaFilename,
                   jobject javaLoader, jclass caller)
{
    return JVM_NativeLoad(env, javaFilename, javaLoader, caller);
}
```

### JVM_NativeLoad

Android 10新增的跳转层。获取`JavaVMExt`实例后调用`LoadNativeLibrary`, 功能与32位的`Runtime_nativeLoad`对等

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:art/openjdkjvm/OpenjdkJvm.cc

```cpp
JNIEXPORT jstring JVM_NativeLoad(JNIEnv* env,
                                 jstring javaFilename,
                                 jobject javaLoader,
                                 jclass caller) {
  ScopedUtfChars filename(env, javaFilename);
  if (filename.c_str() == nullptr) {
    return nullptr;
  }

  std::string error_msg;
  {
    art::JavaVMExt* vm = art::Runtime::Current()->GetJavaVM();
    // 调用art::JavaVMExt::LoadNativeLibrary方法加载so
    bool success = vm->LoadNativeLibrary(env,
                                         filename.c_str(),
                                         javaLoader,
                                         caller,
                                         &error_msg);
    if (success) {
      return nullptr;
    }
  }

  // Don't let a pending exception from JNI_OnLoad cause a CheckJNI issue with NewStringUTF.
  env->ExceptionClear();
  return env->NewStringUTF(error_msg.c_str());
}
```

### JavaVMExt::LoadNativeLibrary

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:art/runtime/jni/java_vm_ext.cc?fi=LoadNativeLibrary#LoadNativeLibrary

```cpp
bool JavaVMExt::LoadNativeLibrary(JNIEnv* env,
                                  const std::string& path,
                                  jobject class_loader,
                                  jclass caller_class,
                                  std::string* error_msg) {
  error_msg->clear();

  // See if we've already loaded this library.  If we have, and the class loader
  // matches, return successfully without doing anything.
  // TODO: for better results we should canonicalize the pathname (or even compare
  // inodes). This implementation is fine if everybody is using System.loadLibrary.
  SharedLibrary* library;
  //1. 判断so是否加载过
  Thread* self = Thread::Current();
  {
    // TODO: move the locking (and more of this logic) into Libraries.
    MutexLock mu(self, *Locks::jni_libraries_lock_);
    library = libraries_->Get(path);
  }
  void* class_loader_allocator = nullptr;
  std::string caller_location;
  {
    ScopedObjectAccess soa(env);
    // As the incoming class loader is reachable/alive during the call of this function,
    // it's okay to decode it without worrying about unexpectedly marking it alive.
    ObjPtr&lt;mirror::ClassLoader&gt; loader = soa.Decode&lt;mirror::ClassLoader&gt;(class_loader);

    ClassLinker* class_linker = Runtime::Current()->GetClassLinker();
    if (class_linker->IsBootClassLoader(soa, loader.Ptr())) {
      loader = nullptr;
      class_loader = nullptr;
      if (caller_class != nullptr) {
        ObjPtr&lt;mirror::Class&gt; caller = soa.Decode&lt;mirror::Class&gt;(caller_class);
        ObjPtr&lt;mirror::DexCache&gt; dex_cache = caller->GetDexCache();
        if (dex_cache != nullptr) {
          caller_location = dex_cache->GetLocation()->ToModifiedUtf8();
        }
      }
    }

    class_loader_allocator = class_linker->GetAllocatorForClassLoader(loader.Ptr());
    CHECK(class_loader_allocator != nullptr);
  }
  if (library != nullptr) {
    // Use the allocator pointers for class loader equality to avoid unnecessary weak root decode.
    if (library->GetClassLoaderAllocator() != class_loader_allocator) {
      // The library will be associated with class_loader. The JNI
      // spec says we can't load the same library into more than one
      // class loader.
      //
      // This isn't very common. So spend some time to get a readable message.
      auto call_to_string = [&](jobject obj) -> std::string {
        if (obj == nullptr) {
          return "null";
        }
        // Handle jweaks. Ignore double local-ref.
        ScopedLocalRef&lt;jobject&gt; local_ref(env, env->NewLocalRef(obj));
        if (local_ref != nullptr) {
          ScopedLocalRef&lt;jclass&gt; local_class(env, env->GetObjectClass(local_ref.get()));
          jmethodID to_string = env->GetMethodID(local_class.get(),
                                                 "toString",
                                                 "()Ljava/lang/String;");
          DCHECK(to_string != nullptr);
          ScopedLocalRef&lt;jobject&gt; local_string(env,
                                               env->CallObjectMethod(local_ref.get(), to_string));
          if (local_string != nullptr) {
            ScopedUtfChars utf(env, reinterpret_cast&lt;jstring&gt;(local_string.get()));
            if (utf.c_str() != nullptr) {
              return utf.c_str();
            }
          }
          if (env->ExceptionCheck()) {
            // We can't do much better logging, really. So leave it with a Describe.
            env->ExceptionDescribe();
            env->ExceptionClear();
          }
          return "(Error calling toString)";
        }
        return "null";
      };
      std::string old_class_loader = call_to_string(library->GetClassLoader());
      std::string new_class_loader = call_to_string(class_loader);
      StringAppendF(error_msg, "Shared library \"%s\" already opened by "
          "ClassLoader %p(%s); can't open in ClassLoader %p(%s)",
          path.c_str(),
          library->GetClassLoader(),
          old_class_loader.c_str(),
          class_loader,
          new_class_loader.c_str());
      LOG(WARNING) << *error_msg;
      return false;
    }
    VLOG(jni) << "[Shared library \"" << path << "\" already loaded in "
              << " ClassLoader " << class_loader << "]";
    if (!library->CheckOnLoadResult()) {
      StringAppendF(error_msg, "JNI_OnLoad failed on a previous attempt "
          "to load \"%s\"", path.c_str());
      return false;
    }
    return true;
  }

  // Open the shared library.  Because we're using a full path, the system
  // doesn't have to search through LD_LIBRARY_PATH.  (It may do so to
  // resolve this library's dependencies though.)

  // Failures here are expected when java.library.path has several entries
  // and we have to hunt for the lib.

  // Below we dlopen but there is no paired dlclose, this would be necessary if we supported
  // class unloading. Libraries will only be unloaded when the reference count (incremented by
  // dlopen) becomes zero from dlclose.

  // Retrieve the library path from the classloader, if necessary.
  ScopedLocalRef&lt;jstring&gt; library_path(env, GetLibrarySearchPath(env, class_loader));

  Locks::mutator_lock_->AssertNotHeld(self);
  const char* path_str = path.empty() ? nullptr : path.c_str();
  bool needs_native_bridge = false;
  char* nativeloader_error_msg = nullptr;
  //2. 调用android::OpenNativeLibrary加载so,获取handle
  void* handle = android::OpenNativeLibrary(
      env,
      runtime_->GetTargetSdkVersion(),
      path_str,
      class_loader,
      (caller_location.empty() ? nullptr : caller_location.c_str()),
      library_path.get(),
      &needs_native_bridge,
      &nativeloader_error_msg);
  VLOG(jni) << "[Call to dlopen(\"" << path << "\", RTLD_NOW) returned " << handle << "]";

  if (handle == nullptr) {
    *error_msg = nativeloader_error_msg;
    android::NativeLoaderFreeErrorMessage(nativeloader_error_msg);
    VLOG(jni) << "dlopen(\"" << path << "\", RTLD_NOW) failed: " << *error_msg;
    return false;
  }

  if (env->ExceptionCheck() == JNI_TRUE) {
    LOG(ERROR) << "Unexpected exception:";
    env->ExceptionDescribe();
    env->ExceptionClear();
  }
  // Create a new entry.
  // TODO: move the locking (and more of this logic) into Libraries.
  //3. 创建新的SharedLibrary 结构体放到 libraries 中
  bool created_library = false;
  {
    // Create SharedLibrary ahead of taking the libraries lock to maintain lock ordering.
    std::unique_ptr&lt;SharedLibrary&gt; new_library(
        new SharedLibrary(env,
                          self,
                          path,
                          handle,
                          needs_native_bridge,
                          class_loader,
                          class_loader_allocator));

    MutexLock mu(self, *Locks::jni_libraries_lock_);
    library = libraries_->Get(path);
    if (library == nullptr) {  // We won race to get libraries_lock.
      library = new_library.release();
      libraries_->Put(path, library);
      created_library = true;
    }
  }
  if (!created_library) {
    LOG(INFO) << "WOW: we lost a race to add shared library: "
        << "\"" << path << "\" ClassLoader=" << class_loader;
    return library->CheckOnLoadResult();
  }
  VLOG(jni) << "[Added shared library \"" << path << "\" for ClassLoader " << class_loader << "]";

  bool was_successful = false;
  //4. 获取JNI_OnLoad符号(函数指针)
  void* sym = library->FindSymbol("JNI_OnLoad", nullptr);
  if (sym == nullptr) {
    VLOG(jni) << "[No JNI_OnLoad found in \"" << path << "\"]";
    was_successful = true;
  } else {
    // Call JNI_OnLoad.  We have to override the current class
    // loader, which will always be "null" since the stuff at the
    // top of the stack is around Runtime.loadLibrary().  (See
    // the comments in the JNI FindClass function.)
    //5. 如果覆写了JNI_OnLoad方法,则需要重写ClassLoader
    ScopedLocalRef&lt;jobject&gt; old_class_loader(env, env->NewLocalRef(self->GetClassLoaderOverride()));
    self->SetClassLoaderOverride(class_loader);

    VLOG(jni) << "[Calling JNI_OnLoad in \"" << path << "\"]";
    using JNI_OnLoadFn = int(*)(JavaVM*, void*);
    JNI_OnLoadFn jni_on_load = reinterpret_cast<JNI_OnLoadFn>(sym);
    //6. 调用JNI_OnLoad
    int version = (*jni_on_load)(this, nullptr);

    if (IsSdkVersionSetAndAtMost(runtime_->GetTargetSdkVersion(), SdkVersion::kL)) {
      // Make sure that sigchain owns SIGSEGV.
      EnsureFrontOfChain(SIGSEGV);
    }

    self->SetClassLoaderOverride(old_class_loader.get());

    if (version == JNI_ERR) {
      StringAppendF(error_msg, "JNI_ERR returned from JNI_OnLoad in \"%s\"", path.c_str());
    } else if (JavaVMExt::IsBadJniVersion(version)) {
      StringAppendF(error_msg, "Bad JNI version returned from JNI_OnLoad in \"%s\": %d",
                    path.c_str(), version);
      // It's unwise to call dlclose() here, but we can mark it
      // as bad and ensure that future load attempts will fail.
      // We don't know how far JNI_OnLoad got, so there could
      // be some partially-initialized stuff accessible through
      // newly-registered native method calls.  We could try to
      // unregister them, but that doesn't seem worthwhile.
    } else {
      was_successful = true;
    }
    VLOG(jni) << "[Returned " << (was_successful ? "successfully" : "failure")
              << " from JNI_OnLoad in \"" << path << "\"]";
  }

  library->SetResult(was_successful);
  return was_successful;
}
```

### android::OpenNativeLibrary

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:system/core/libnativeloader/native_loader.cpp

该函数内部有android_dlopen_ext和dlopen两种打开so的方式

android_dlopen_ext 是 Android 特有的扩展版本的动态库加载函数，它提供了比标准 dlopen更丰富的功能，主要用于：

- **命名空间支持**：通过 android_dlextinfo 结构体中的 library_namespace 字段，可以指定要使用的命名空间（namespace）。命名空间是 Android 7.0 (N) 引入的特性，用于隔离不同模块的共享库，防止符号冲突。
- **更精细的加载控制**：可以设置各种标志（如 ANDROID_DLEXT_USE_NAMESPACE）来控制加载行为，例如指定库的搜索路径、是否允许从其他命名空间查找符号等。

当 caller_location 不为空且能找到对应的 boot_namespace 时，函数会优先使用 android_dlopen_ext 并指定 boot_namespace，这样可以确保 SO 文件在特定的命名空间上下文中加载，避免符号冲突。

当无法找到 boot_namespace 时（例如 caller_location 为空），函数会回退到使用标准的dlopen。这种情况下，SO 文件会在默认的全局命名空间中加载，这可能会导致符号冲突，但在某些兼容性场景下是必要的。

总而言之,大部分情况下走android_dlopen_ext分支,其他情况为了兼容性走dlopen分支

```cpp
void* OpenNativeLibrary(JNIEnv* env, int32_t target_sdk_version, const char* path,
                        jobject class_loader, const char* caller_location, jstring library_path,
                        bool* needs_native_bridge, char** error_msg) {
#if defined(__ANDROID__)
  UNUSED(target_sdk_version);
  if (class_loader == nullptr) {
    *needs_native_bridge = false;
    if (caller_location != nullptr) {
      android_namespace_t* boot_namespace = FindExportedNamespace(caller_location);
      if (boot_namespace != nullptr) {
        const android_dlextinfo dlextinfo = {
            .flags = ANDROID_DLEXT_USE_NAMESPACE,
            .library_namespace = boot_namespace,
        };
        //1. 调用android_dlopen_ext打开so并返回handle
        //RTLD_NOW表示立即解析所有符号并在加载时报告解析错误
        void* handle = android_dlopen_ext(path, RTLD_NOW, &dlextinfo);
        if (handle == nullptr) {
          *error_msg = strdup(dlerror());
        }
        return handle;
      }
    }
    //2. 调用dlopen打开so并返回handle
    void* handle = dlopen(path, RTLD_NOW);
    if (handle == nullptr) {
      *error_msg = strdup(dlerror());
    }
    return handle;
  }

  std::lock_guard&lt;std::mutex&gt; guard(g_namespaces_mutex);
  NativeLoaderNamespace* ns;

  if ((ns = g_namespaces->FindNamespaceByClassLoader(env, class_loader)) == nullptr) {
    // This is the case where the classloader was not created by ApplicationLoaders
    // In this case we create an isolated not-shared namespace for it.
    std::string create_error_msg;
    if ((ns = g_namespaces->Create(env, target_sdk_version, class_loader, false /* is_shared */,
                                   nullptr, library_path, nullptr, &create_error_msg)) == nullptr) {
      *error_msg = strdup(create_error_msg.c_str());
      return nullptr;
    }
  }

  return OpenNativeLibraryInNamespace(ns, path, needs_native_bridge, error_msg);
#else
  UNUSED(env, target_sdk_version, class_loader, caller_location);

  // Do some best effort to emulate library-path support. It will not
  // work for dependencies.
  //
  // Note: null has a special meaning and must be preserved.
  std::string c_library_path;  // Empty string by default.
  if (library_path != nullptr && path != nullptr && path[0] != '/') {
    ScopedUtfChars library_path_utf_chars(env, library_path);
    c_library_path = library_path_utf_chars.c_str();
  }

  std::vector&lt;std::string&gt; library_paths = base::Split(c_library_path, ":");

  for (const std::string& lib_path : library_paths) {
    *needs_native_bridge = false;
    const char* path_arg;
    std::string complete_path;
    if (path == nullptr) {
      // Preserve null.
      path_arg = nullptr;
    } else {
      complete_path = lib_path;
      if (!complete_path.empty()) {
        complete_path.append("/");
      }
      complete_path.append(path);
      path_arg = complete_path.c_str();
    }
    void* handle = dlopen(path_arg, RTLD_NOW);
    if (handle != nullptr) {
      return handle;
    }
    if (NativeBridgeIsSupported(path_arg)) {
      *needs_native_bridge = true;
      handle = NativeBridgeLoadLibrary(path_arg, RTLD_NOW);
      if (handle != nullptr) {
        return handle;
      }
      *error_msg = strdup(NativeBridgeGetError());
    } else {
      *error_msg = strdup(dlerror());
    }
  }
  return nullptr;
#endif
}
```

## Linker Load So

进入linker核心代码, 从`android_dlopen_ext`出发经过多层调用最终到达`do_dlopen`, 这是整个SO加载的真正入口

### android_dlopen_ext

调用了__loader_android_dlopen_ext

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/libdl/libdl.cpp

```cpp
__attribute__((__weak__))
void* android_dlopen_ext(const char* filename, int flag, const android_dlextinfo* extinfo) {
  const void* caller_addr = __builtin_return_address(0);
  return __loader_android_dlopen_ext(filename, flag, extinfo, caller_addr);
}
```

android_dlopen_ext 函数的常见 flag 含义:

- RTLD_NOW 立即解析所有符号，并在加载时报告任何解析错误
- RTLD_LAZY 只在符号首次使用时解析
- RTLD_GLOBAL 将库及其符号添加到全局命名空间中，以便其他库可以使用这些符号

内建函数 __builtin_return_address(LEVEL) 用于返回当前函数或调用者的返回地址

函数的参数LEVEL表示函数调用链中的不同层次的函数，各个值代表的意义如下:

- 0 返回当前函数的返回地址
- 1 返回当前函数调用者的返回地址
- 2 返回当前函数调用者的调用者的返回地址

### __loader_android_dlopen_ext

linker内部的转发函数, 直接调用`dlopen_ext`

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/dlfcn.cpp#146

```cpp
void* __loader_android_dlopen_ext(const char* filename,
                           int flags,
                           const android_dlextinfo* extinfo,
                           const void* caller_addr) {
  return dlopen_ext(filename, flags, extinfo, caller_addr);
}
```

### dlopen_ext

加锁后调用`do_dlopen`, 失败时格式化错误信息到`dlerror`缓冲区

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/dlfcn.cpp#132

```cpp
static void* dlopen_ext(const char* filename,
                        int flags,
                        const android_dlextinfo* extinfo,
                        const void* caller_addr) {
  ScopedPthreadMutexLocker locker(&g_dl_mutex);
  g_linker_logger.ResetState();
  void* result = do_dlopen(filename, flags, extinfo, caller_addr);
  if (result == nullptr) {
    __bionic_format_dlerror("dlopen failed", linker_get_error_buffer());
    return nullptr;
  }
  return result;
}
```

### do_dlopen

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#2718

进入该函数后便正式进入linker的核心流程, 而该函数执行完毕后so便成功加载并且可以执行

该函数主要有2个核心功能:

1. 调用find_library加载so并返回soinfo
2. 调用soinfo.call_constructors()

其内部递归调用依赖库的constructors, 再调用自身init和init_array进行初始化

```cpp
void* do_dlopen(const char* name, int flags,
                const android_dlextinfo* extinfo,
                const void* caller_addr) {
  std::string trace_prefix = std::string("dlopen: ") + (name == nullptr ? "(nullptr)" : name);
  ScopedTrace trace(trace_prefix.c_str());
  ScopedTrace loading_trace((trace_prefix + " - loading and linking").c_str());
  soinfo* const caller = find_containing_library(caller_addr);
  android_namespace_t* ns = get_caller_namespace(caller);

  LD_LOG(kLogDlopen,
         "dlopen(name=\"%s\", flags=0x%x, extinfo=%s, caller=\"%s\", caller_ns=%s@%p, targetSdkVersion=%i) ...",
         name,
         flags,
         android_dlextinfo_to_string(extinfo).c_str(),
         caller == nullptr ? "(null)" : caller->get_realpath(),
         ns == nullptr ? "(null)" : ns->get_name(),
         ns,
         get_application_target_sdk_version());

  auto purge_guard = android::base::make_scope_guard([&]() { purge_unused_memory(); });

  auto failure_guard = android::base::make_scope_guard(
      [&]() { LD_LOG(kLogDlopen, "... dlopen failed: %s", linker_get_error_buffer()); });

  // 检测flags合法性
  if ((flags & ~(RTLD_NOW|RTLD_LAZY|RTLD_LOCAL|RTLD_GLOBAL|RTLD_NODELETE|RTLD_NOLOAD)) != 0) {
    DL_ERR("invalid flags to dlopen: %x", flags);
    return nullptr;
  }

  // 检测extinfo合法性
  if (extinfo != nullptr) {
    if ((extinfo->flags & ~(ANDROID_DLEXT_VALID_FLAG_BITS)) != 0) {
      DL_ERR("invalid extended flags to android_dlopen_ext: 0x%" PRIx64, extinfo->flags);
      return nullptr;
    }

    if ((extinfo->flags & ANDROID_DLEXT_USE_LIBRARY_FD) == 0 &&
        (extinfo->flags & ANDROID_DLEXT_USE_LIBRARY_FD_OFFSET) != 0) {
      DL_ERR("invalid extended flag combination (ANDROID_DLEXT_USE_LIBRARY_FD_OFFSET without "
          "ANDROID_DLEXT_USE_LIBRARY_FD): 0x%" PRIx64, extinfo->flags);
      return nullptr;
    }

    if ((extinfo->flags & ANDROID_DLEXT_USE_NAMESPACE) != 0) {
      if (extinfo->library_namespace == nullptr) {
        DL_ERR("ANDROID_DLEXT_USE_NAMESPACE is set but extinfo->library_namespace is null");
        return nullptr;
      }
      ns = extinfo->library_namespace;
    }
  }

  // Workaround for dlopen(/system/lib/&lt;soname&gt;) when .so is in /apex. http://b/121248172
  // The workaround works only when targetSdkVersion < Q.
  std::string name_to_apex;
  if (translateSystemPathToApexPath(name, &name_to_apex)) {
    const char* new_name = name_to_apex.c_str();
    LD_LOG(kLogDlopen, "dlopen considering translation from %s to APEX path %s",
           name,
           new_name);
    // Some APEXs could be optionally disabled. Only translate the path
    // when the old file is absent and the new file exists.
    // TODO(b/124218500): Re-enable it once app compat issue is resolved
    /*
    if (file_exists(name)) {
      LD_LOG(kLogDlopen, "dlopen %s exists, not translating", name);
    } else
    */
    if (!file_exists(new_name)) {
      LD_LOG(kLogDlopen, "dlopen %s does not exist, not translating",
             new_name);
    } else {
      LD_LOG(kLogDlopen, "dlopen translation accepted: using %s", new_name);
      name = new_name;
    }
  }
  // End Workaround for dlopen(/system/lib/&lt;soname&gt;) when .so is in /apex.

  std::string asan_name_holder;

  const char* translated_name = name;
  if (g_is_asan && translated_name != nullptr && translated_name[0] == '/') {
    char original_path[PATH_MAX];
    if (realpath(name, original_path) != nullptr) {
      asan_name_holder = std::string(kAsanLibDirPrefix) + original_path;
      if (file_exists(asan_name_holder.c_str())) {
        soinfo* si = nullptr;
        if (find_loaded_library_by_realpath(ns, original_path, true, &si)) {
          PRINT("linker_asan dlopen NOT translating \"%s\" -> \"%s\": library already loaded", name,
                asan_name_holder.c_str());
        } else {
          PRINT("linker_asan dlopen translating \"%s\" -> \"%s\"", name, translated_name);
          translated_name = asan_name_holder.c_str();
        }
      }
    }
  }

  ProtectedDataGuard guard;
  //1. 调用find_library,获取soinfo
  soinfo* si = find_library(ns, translated_name, flags, extinfo, caller);
  loading_trace.End();

  if (si != nullptr) {
    void* handle = si->to_handle();
    LD_LOG(kLogDlopen,
           "... dlopen calling constructors: realpath=\"%s\", soname=\"%s\", handle=%p",
           si->get_realpath(), si->get_soname(), handle);
    //2. 调用so的构造函数
    si->call_constructors();
    failure_guard.Disable();
    LD_LOG(kLogDlopen,
           "... dlopen successful: realpath=\"%s\", soname=\"%s\", handle=%p",
           si->get_realpath(), si->get_soname(), handle);
    return handle;
  }

  return nullptr;
}
```

#### soinfo::call_constructors

call_function和call_array函数与前文类似

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker_soinfo.cpp#399

```cpp
void soinfo::call_constructors() {
  if (constructors_called) {
    return;
  }

  // We set constructors_called before actually calling the constructors, otherwise it doesn't
  // protect against recursive constructor calls. One simple example of constructor recursion
  // is the libc debug malloc, which is implemented in libc_malloc_debug_leak.so:
  // 1. The program depends on libc, so libc's constructor is called here.
  // 2. The libc constructor calls dlopen() to load libc_malloc_debug_leak.so.
  // 3. dlopen() calls the constructors on the newly created
  //    soinfo for libc_malloc_debug_leak.so.
  // 4. The debug .so depends on libc, so CallConstructors is
  //    called again with the libc soinfo. If it doesn't trigger the early-
  //    out above, the libc constructor will be called again (recursively!).
  constructors_called = true;

  if (!is_main_executable() && preinit_array_ != nullptr) {
    // The GNU dynamic linker silently ignores these, but we warn the developer.
    PRINT("\"%s\": ignoring DT_PREINIT_ARRAY in shared library!", get_realpath());
  }

  get_children().for_each([] (soinfo* si) {
    si->call_constructors();
  });

  if (!is_linker()) {
    bionic_trace_begin((std::string("calling constructors: ") + get_realpath()).c_str());
  }

  // DT_INIT should be called before DT_INIT_ARRAY if both are present.
  call_function("DT_INIT", init_func_, get_realpath());
  call_array("DT_INIT_ARRAY", init_array_, init_array_count_, false, get_realpath());

  if (!is_linker()) {
    bionic_trace_end();
  }
}
```

### find_library

`do_dlopen`的核心调用。封装了`find_libraries`的单库加载接口, 加载成功后增加引用计数

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#1919

```cpp
static soinfo* find_library(android_namespace_t* ns,
                            const char* name, int rtld_flags,
                            const android_dlextinfo* extinfo,
                            soinfo* needed_by) {
  soinfo* si = nullptr;

  if (name == nullptr) {
    si = solist_get_somain();
  } else if (!find_libraries(ns,
                             needed_by,
                             &name,
                             1,
                             &si,
                             nullptr,
                             0,
                             rtld_flags,
                             extinfo,
                             false /* add_as_children */,
                             true /* search_linked_namespaces */)) {
    if (si != nullptr) {
      soinfo_unload(si);
    }
    return nullptr;
  }

  si->increment_ref_count();

  return si;
}
```

### find_libraries

**64位linker的核心加载函数**。与32位的串行流程不同, 这里拆分为7个step流水线执行: prepare → 加载依赖 → 随机序加载 → prelink → 构建全局组 → 链接重定位 → 标记完成

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#1634

函数声明如下

```cpp
bool find_libraries(android_namespace_t* ns,			//调用者的命名空间
                    soinfo* start_with,					//调用者的soinfo
                    const char* const library_names[],	//所有加载库名称
                    size_t library_names_count,			//加载库数量
                    soinfo* soinfos[],					//加载完成的 soinfo
                    std::vector&lt;soinfo*&gt;* ld_preloads,	//保存预加载库，没有可以为 null
                    size_t ld_preloads_count,			//预加载库数量
                    int rtld_flags,
                    const android_dlextinfo* extinfo,	//Android 调用附带
                    bool add_as_children,
                    bool search_linked_namespaces,		//查询链接命名空间
                    std::vector<android_namespace_t*>* namespaces	//链接命名空间
                   )
```

该函数内部执行了加载so的具体操作,分为7个部分:

1. step0: prepare

#### find_libraries step0: prepare

- 创建该so对应的LoadTask任务并添加到load_tasks队列中
- 为soinfo分配空间

```cpp
  // Step 0: prepare.
  std::unordered_map&lt;const soinfo*, ElfReader&gt; readers_map;
  LoadTaskList load_tasks;

  //支持同时加载多个so,但find_libraary传入的library_names_count==1,只加载一个so
  for (size_t i = 0; i < library_names_count; ++i) {
    const char* name = library_names[i];
    // 将so添加到load_tasks任务中
    load_tasks.push_back(LoadTask::create(name, start_with, ns, &readers_map));
  }

  // If soinfos array is null allocate one on stack.
  // The array is needed in case of failure; for example
  // when library_names[] = {libone.so, libtwo.so} and libone.so
  // is loaded correctly but libtwo.so failed for some reason.
  // In this case libone.so should be unloaded on return.
  // See also implementation of failure_guard below.

  // 为soinfo分配空间
  if (soinfos == nullptr) {
    size_t soinfos_size = sizeof(soinfo*)*library_names_count;
    soinfos = reinterpret_cast&lt;soinfo**&gt;(alloca(soinfos_size));
    memset(soinfos, 0, soinfos_size);
  }

  // list of libraries to link - see step 2.
  size_t soinfos_count = 0;

  auto scope_guard = android::base::make_scope_guard([&]() {
    for (LoadTask* t : load_tasks) {
      LoadTask::deleter(t);
    }
  });

  ZipArchiveCache zip_archive_cache;
```

#### find_libraries step1: add needed libraries to load_tasks

- 遍历load_tasks,并调用find_library_internal加载so
- 将该so的soinfo添加至soinfos列表中

```cpp
  // Step 1: expand the list of load_tasks to include
  // all DT_NEEDED libraries (do not load them just yet)
  // 遍历load_tasks,如果是find_library传递而来的显然初始时只有一个task,后续依次添加so的依赖库
  for (size_t i = 0; i<load_tasks.size(); ++i) {
    LoadTask* task = load_tasks[i];				//该so对应的LoadTask
    soinfo* needed_by = task->get_needed_by();	//获取依赖库的soinfo

    bool is_dt_needed = needed_by != nullptr && (needed_by != start_with || add_as_children);
    task->set_extinfo(is_dt_needed ? nullptr : extinfo);
    task->set_dt_needed(is_dt_needed);

    LD_LOG(kLogDlopen, "find_libraries(ns=%s): task=%s, is_dt_needed=%d", ns->get_name(),
           task->get_name(), is_dt_needed);

    // Note: start from the namespace that is stored in the LoadTask. This namespace
    // is different from the current namespace when the LoadTask is for a transitive
    // dependency and the lib that created the LoadTask is not found in the
    // current namespace but in one of the linked namespace.
    // 加载so,传入load_tasks指针用于添加该so的依赖至任务队列中
    if (!find_library_internal(const_cast<android_namespace_t*>(task->get_start_from()),
                               task,
                               &zip_archive_cache,
                               &load_tasks,
                               rtld_flags,
                               search_linked_namespaces || is_dt_needed)) {
      return false;
    }

    soinfo* si = task->get_soinfo();

    if (is_dt_needed) {
      needed_by->add_child(si);
    }

    // When ld_preloads is not null, the first
    // ld_preloads_count libs are in fact ld_preloads.
    if (ld_preloads != nullptr && soinfos_count < ld_preloads_count) {
      ld_preloads->push_back(si);
    }

    // 将当前soinfo添加至已加载的soinfo列表中
    if (soinfos_count < library_names_count) {
      soinfos[soinfos_count++] = si;
    }
  }
```

### find_library_internal

查找并加载单个SO。查找顺序: 已加载列表 → `load_library`加载 → 灰名单兼容 → 链接命名空间搜索。加载成功后将SO的依赖库添加到`load_tasks`队列

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#1539

```cpp
static bool find_library_internal(android_namespace_t* ns,
                                  LoadTask* task,
                                  ZipArchiveCache* zip_archive_cache,
                                  LoadTaskList* load_tasks,
                                  int rtld_flags,
                                  bool search_linked_namespaces) {
  soinfo* candidate;
  //1. 该so已经加载过,给task设置soinfo后直接返回
  if (find_loaded_library_by_soname(ns, task->get_name(), search_linked_namespaces, &candidate)) {
    LD_LOG(kLogDlopen,
           "find_library_internal(ns=%s, task=%s): Already loaded (by soname): %s",
           ns->get_name(), task->get_name(), candidate->get_realpath());
    task->set_soinfo(candidate);
    return true;
  }

  // Library might still be loaded, the accurate detection
  // of this fact is done by load_library.
  TRACE("[ \"%s\" find_loaded_library_by_soname failed (*candidate=%s@%p). Trying harder... ]",
        task->get_name(), candidate == nullptr ? "n/a" : candidate->get_realpath(), candidate);
  //2. 没有加载该so,执行load_library加载
  if (load_library(ns, task, zip_archive_cache, load_tasks, rtld_flags, search_linked_namespaces)) {
    return true;
  }

  // TODO(dimitry): workaround for http://b/26394120 (the grey-list)
  //3. 如果是预置系统库则使用默认命名空间获取soinfo
  if (ns->is_greylist_enabled() && is_greylisted(ns, task->get_name(), task->get_needed_by())) {
    // For the libs in the greylist, switch to the default namespace and then
    // try the load again from there. The library could be loaded from the
    // default namespace or from another namespace (e.g. runtime) that is linked
    // from the default namespace.
    LD_LOG(kLogDlopen,
           "find_library_internal(ns=%s, task=%s): Greylisted library - trying namespace %s",
           ns->get_name(), task->get_name(), g_default_namespace.get_name());
    ns = &g_default_namespace;
    if (load_library(ns, task, zip_archive_cache, load_tasks, rtld_flags,
                     search_linked_namespaces)) {
      return true;
    }
  }
  // END OF WORKAROUND

  //4. 默认命名空间没有发现,从共享命名空间寻找
  if (search_linked_namespaces) {
    // if a library was not found - look into linked namespaces
    // preserve current dlerror in the case it fails.
    DlErrorRestorer dlerror_restorer;
    LD_LOG(kLogDlopen, "find_library_internal(ns=%s, task=%s): Trying %zu linked namespaces",
           ns->get_name(), task->get_name(), ns->linked_namespaces().size());
    for (auto& linked_namespace : ns->linked_namespaces()) {
      if (find_library_in_linked_namespace(linked_namespace, task)) {
        if (task->get_soinfo() == nullptr) {
          // try to load the library - once namespace boundary is crossed
          // we need to load a library within separate load_group
          // to avoid using symbols from foreign namespace while.
          //
          // However, actual linking is deferred until when the global group
          // is fully identified and is applied to all namespaces.
          // Otherwise, the libs in the linked namespace won't get symbols from
          // the global group.
          if (load_library(linked_namespace.linked_namespace(), task, zip_archive_cache, load_tasks, rtld_flags, false)) {
            LD_LOG(
                kLogDlopen, "find_library_internal(ns=%s, task=%s): Found in linked namespace %s",
                ns->get_name(), task->get_name(), linked_namespace.linked_namespace()->get_name());
            return true;
          }
        } else {
          // lib is already loaded
          return true;
        }
      }
    }
  }

  return false;
}
```

### load_library(ZipArchiveCache)

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#1408

![image](https://bbs.kanxue.com/upload/attach/202604/968342_D4QPQSFGWR9Y257.png)

```cpp
static bool load_library(android_namespace_t* ns,
                         LoadTask* task,
                         ZipArchiveCache* zip_archive_cache,
                         LoadTaskList* load_tasks,
                         int rtld_flags,
                         bool search_linked_namespaces) {
  const char* name = task->get_name();
  soinfo* needed_by = task->get_needed_by();
  const android_dlextinfo* extinfo = task->get_extinfo();

  off64_t file_offset;
  std::string realpath;
  //1. 检查extinfo.flags是否为ANDROID_DLEXT_USE_LIBRARY_FD,若是则通过fd文件描述符打开so
  if (extinfo != nullptr && (extinfo->flags & ANDROID_DLEXT_USE_LIBRARY_FD) != 0) {
    file_offset = 0;
    if ((extinfo->flags & ANDROID_DLEXT_USE_LIBRARY_FD_OFFSET) != 0) {
      file_offset = extinfo->library_fd_offset;
    }

    if (!realpath_fd(extinfo->library_fd, &realpath)) {
      if (!is_first_stage_init()) {
        PRINT(
            "warning: unable to get realpath for the library \"%s\" by extinfo->library_fd. "
            "Will use given name.",
            name);
      }
      realpath = name;
    }

    task->set_fd(extinfo->library_fd, false);
    task->set_file_offset(file_offset);
    //2. 调用另一个load_library重载加载so
    return load_library(ns, task, load_tasks, rtld_flags, realpath, search_linked_namespaces);
  }

  // Open the file.
  //3. 调用open_library打开so并加载
  int fd = open_library(ns, zip_archive_cache, name, needed_by, &file_offset, &realpath);
  if (fd == -1) {
    DL_ERR("library \"%s\" not found", name);
    return false;
  }

  task->set_fd(fd, true);
  task->set_file_offset(file_offset);

  return load_library(ns, task, load_tasks, rtld_flags, realpath, search_linked_namespaces);
}
```

### open_library

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#1123

```cpp
static int open_library(android_namespace_t* ns,
                        ZipArchiveCache* zip_archive_cache,
                        const char* name, soinfo *needed_by,
                        off64_t* file_offset, std::string* realpath) {
  TRACE("[ opening %s from namespace %s ]", name, ns->get_name());

  // If the name contains a slash, we should attempt to open it directly and not search the paths.
  //1. 通过so绝对路径寻找so,例如System.load()
  if (strchr(name, '/') != nullptr) {
    int fd = -1;

    if (strstr(name, kZipFileSeparator) != nullptr) {
      fd = open_library_in_zipfile(zip_archive_cache, name, file_offset, realpath);
    }

    if (fd == -1) {
      fd = TEMP_FAILURE_RETRY(open(name, O_RDONLY | O_CLOEXEC));
      if (fd != -1) {
        *file_offset = 0;
        if (!realpath_fd(fd, realpath)) {
          if (!is_first_stage_init()) {
            PRINT("warning: unable to get realpath for the library \"%s\". Will use given path.",
                  name);
          }
          *realpath = name;
        }
      }
    }

    return fd;
  }

  // Otherwise we try LD_LIBRARY_PATH first, and fall back to the default library path
  int fd = open_library_on_paths(zip_archive_cache, name, file_offset, ns->get_ld_library_paths(), realpath);
  if (fd == -1 && needed_by != nullptr) {
    fd = open_library_on_paths(zip_archive_cache, name, file_offset, needed_by->get_dt_runpath(), realpath);
    // Check if the library is accessible
    if (fd != -1 && !ns->is_accessible(*realpath)) {
      close(fd);
      fd = -1;
    }
  }

  if (fd == -1) {
    fd = open_library_on_paths(zip_archive_cache, name, file_offset, ns->get_default_library_paths(), realpath);
  }

  return fd;
}
```

#### open_library_in_zipfile

该函数用于寻找so的真实路径并返回fd

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#998

```cpp
static int open_library_in_zipfile(ZipArchiveCache* zip_archive_cache,
                                   const char* const input_path,
                                   off64_t* file_offset, std::string* realpath) {
  std::string normalized_path;
  if (!normalize_path(input_path, &normalized_path)) {
    return -1;
  }

  const char* const path = normalized_path.c_str();
  TRACE("Trying zip file open from path \"%s\" -> normalized \"%s\"", input_path, path);

  // Treat an '!/' separator inside a path as the separator between the name
  // of the zip file on disk and the subdirectory to search within it.
  // For example, if path is "foo.zip!/bar/bas/x.so", then we search for
  // "bar/bas/x.so" within "foo.zip".
  const char* const separator = strstr(path, kZipFileSeparator);
  if (separator == nullptr) {
    return -1;
  }

  char buf[512];
  if (strlcpy(buf, path, sizeof(buf)) >= sizeof(buf)) {
    PRINT("Warning: ignoring very long library path: %s", path);
    return -1;
  }

  buf[separator - path] = '\0';

  const char* zip_path = buf;
  const char* file_path = &buf[separator - path + 2];
  int fd = TEMP_FAILURE_RETRY(open(zip_path, O_RDONLY | O_CLOEXEC));
  if (fd == -1) {
    return -1;
  }

  ZipArchiveHandle handle;
  if (!zip_archive_cache->get_or_open(zip_path, &handle)) {
    // invalid zip-file (?)
    close(fd);
    return -1;
  }

  ZipEntry entry;

  if (FindEntry(handle, ZipString(file_path), &entry) != 0) {
    // Entry was not found.
    close(fd);
    return -1;
  }

  // Check if it is properly stored
  if (entry.method != kCompressStored || (entry.offset % PAGE_SIZE) != 0) {
    close(fd);
    return -1;
  }

  *file_offset = entry.offset;

  // 寻找到so真实路径
  if (realpath_fd(fd, realpath)) {
    *realpath += separator;
  } else {
    if (!is_first_stage_init()) {
      PRINT("warning: unable to get realpath for the library \"%s\". Will use given path.",
            normalized_path.c_str());
    }
    *realpath = normalized_path;
  }

  return fd;
}
```

#### open_library_on_paths

调用了open_library_at_path

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#1104

```cpp
static int open_library_on_paths(ZipArchiveCache* zip_archive_cache,
                                 const char* name, off64_t* file_offset,
                                 const std::vector&lt;std::string&gt;& paths,
                                 std::string* realpath) {
  for (const auto& path : paths) {
    char buf[512];
    if (!format_path(buf, sizeof(buf), path.c_str(), name)) {
      continue;
    }

    int fd = open_library_at_path(zip_archive_cache, buf, file_offset, realpath);
    if (fd != -1) {
      return fd;
    }
  }

  return -1;
}
```

#### open_library_at_path

内部调用了open_library_in_zipfile和open,其中open传入的2个标志含义如下:

- `O_RDONLY` 表示以只读方式打开文件。
- `O_CLOEXEC` 表示在 exec 族函数 (execl, execlp, execle, execv, execvp, execvpe) 调用后，将自动关闭文件描述符

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#1079

```cpp
static int open_library_at_path(ZipArchiveCache* zip_archive_cache,
                                const char* path, off64_t* file_offset,
                                std::string* realpath) {
  int fd = -1;
  //1. 如果路径包含"/"则通过zipfile打开so
  if (strstr(path, kZipFileSeparator) != nullptr) {
    fd = open_library_in_zipfile(zip_archive_cache, path, file_offset, realpath);
  }

  //2. 通过open打开so
  if (fd == -1) {
    fd = TEMP_FAILURE_RETRY(open(path, O_RDONLY | O_CLOEXEC));
    if (fd != -1) {
      *file_offset = 0;
      if (!realpath_fd(fd, realpath)) {
        if (!is_first_stage_init()) {
          PRINT("warning: unable to get realpath for the library \"%s\". Will use given path.",
                path);
        }
        *realpath = path;
      }
    }
  }

  return fd;
}
```

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#1258

```cpp
static bool load_library(android_namespace_t* ns,
                         LoadTask* task,
                         LoadTaskList* load_tasks,
                         int rtld_flags,
                         const std::string& realpath,
                         bool search_linked_namespaces) {
  off64_t file_offset = task->get_file_offset();
  const char* name = task->get_name();
  const android_dlextinfo* extinfo = task->get_extinfo();

  LD_LOG(kLogDlopen, "load_library(ns=%s, task=%s, flags=0x%x, realpath=%s)", ns->get_name(), name,
         rtld_flags, realpath.c_str());

  if ((file_offset % PAGE_SIZE) != 0) {
    DL_ERR("file offset for the library \"%s\" is not page-aligned: %" PRId64, name, file_offset);
    return false;
  }
  if (file_offset < 0) {
    DL_ERR("file offset for the library \"%s\" is negative: %" PRId64, name, file_offset);
    return false;
  }

  struct stat file_stat;
  if (TEMP_FAILURE_RETRY(fstat(task->get_fd(), &file_stat)) != 0) {
    DL_ERR("unable to stat file for the library \"%s\": %s", name, strerror(errno));
    return false;
  }
  if (file_offset >= file_stat.st_size) {
    DL_ERR("file offset for the library \"%s\" >= file size: %" PRId64 " >= %" PRId64,
        name, file_offset, file_stat.st_size);
    return false;
  }

  // Check for symlink and other situations where
  // file can have different names, unless ANDROID_DLEXT_FORCE_LOAD is set
  if (extinfo == nullptr || (extinfo->flags & ANDROID_DLEXT_FORCE_LOAD) == 0) {
    soinfo* si = nullptr;
    if (find_loaded_library_by_inode(ns, file_stat, file_offset, search_linked_namespaces, &si)) {
      LD_LOG(kLogDlopen,
             "load_library(ns=%s, task=%s): Already loaded under different name/path \"%s\" - "
             "will return existing soinfo",
             ns->get_name(), name, si->get_realpath());
      task->set_soinfo(si);
      return true;
    }
  }

  if ((rtld_flags & RTLD_NOLOAD) != 0) {
    DL_ERR("library \"%s\" wasn't loaded and RTLD_NOLOAD prevented it", name);
    return false;
  }

  struct statfs fs_stat;
  if (TEMP_FAILURE_RETRY(fstatfs(task->get_fd(), &fs_stat)) != 0) {
    DL_ERR("unable to fstatfs file for the library \"%s\": %s", name, strerror(errno));
    return false;
  }

  // do not check accessibility using realpath if fd is located on tmpfs
  // this enables use of memfd_create() for apps
  if ((fs_stat.f_type != TMPFS_MAGIC) && (!ns->is_accessible(realpath))) {
    // TODO(dimitry): workaround for http://b/26394120 - the grey-list

    // TODO(dimitry) before O release: add a namespace attribute to have this enabled
    // only for classloader-namespaces
    const soinfo* needed_by = task->is_dt_needed() ? task->get_needed_by() : nullptr;
    if (is_greylisted(ns, name, needed_by)) {
      // print warning only if needed by non-system library
      if (needed_by == nullptr || !is_system_library(needed_by->get_realpath())) {
        const soinfo* needed_or_dlopened_by = task->get_needed_by();
        const char* sopath = needed_or_dlopened_by == nullptr ? "(unknown)" :
                                                      needed_or_dlopened_by->get_realpath();
        DL_WARN_documented_change(__ANDROID_API_N__,
                                  "private-api-enforced-for-api-level-24",
                                  "library \"%s\" (\"%s\") needed or dlopened by \"%s\" "
                                  "is not accessible by namespace \"%s\"",
                                  name, realpath.c_str(), sopath, ns->get_name());
        add_dlwarning(sopath, "unauthorized access to",  name);
      }
    } else {
      // do not load libraries if they are not accessible for the specified namespace.
      const char* needed_or_dlopened_by = task->get_needed_by() == nullptr ?
                                          "(unknown)" :
                                          task->get_needed_by()->get_realpath();

      DL_ERR("library \"%s\" needed or dlopened by \"%s\" is not accessible for the namespace \"%s\"",
             name, needed_or_dlopened_by, ns->get_name());

      // do not print this if a library is in the list of shared libraries for linked namespaces
      if (!maybe_accessible_via_namespace_links(ns, name)) {
        PRINT("library \"%s\" (\"%s\") needed or dlopened by \"%s\" is not accessible for the"
              " namespace: [name=\"%s\", ld_library_paths=\"%s\", default_library_paths=\"%s\","
              " permitted_paths=\"%s\"]",
              name, realpath.c_str(),
              needed_or_dlopened_by,
              ns->get_name(),
              android::base::Join(ns->get_ld_library_paths(), ':').c_str(),
              android::base::Join(ns->get_default_library_paths(), ':').c_str(),
              android::base::Join(ns->get_permitted_paths(), ':').c_str());
      }
      return false;
    }
  }

  soinfo* si = soinfo_alloc(ns, realpath.c_str(), &file_stat, file_offset, rtld_flags);
  if (si == nullptr) {
    return false;
  }

  task->set_soinfo(si);

  // Read the ELF header and some of the segments.
  if (!task->read(realpath.c_str(), file_stat.st_size)) {
    soinfo_free(si);
    task->set_soinfo(nullptr);
    return false;
  }

  // find and set DT_RUNPATH and dt_soname
  // Note that these field values are temporary and are
  // going to be overwritten on soinfo::prelink_image
  // with values from PT_LOAD segments.
  const ElfReader& elf_reader = task->get_elf_reader();
  for (const ElfW(Dyn)* d = elf_reader.dynamic(); d->d_tag != DT_NULL; ++d) {
    if (d->d_tag == DT_RUNPATH) {
      si->set_dt_runpath(elf_reader.get_string(d->d_un.d_val));
    }
    if (d->d_tag == DT_SONAME) {
      si->set_soname(elf_reader.get_string(d->d_un.d_val));
    }
  }

#if !defined(__ANDROID__)
  // Bionic on the host currently uses some Android prebuilts, which don't set
  // DT_RUNPATH with any relative paths, so they can't find their dependencies.
  // b/118058804
  if (si->get_dt_runpath().empty()) {
    si->set_dt_runpath("$ORIGIN/../lib64:$ORIGIN/lib64");
  }
#endif

  for_each_dt_needed(task->get_elf_reader(), [&](const char* name) {
    LD_LOG(kLogDlopen, "load_library(ns=%s, task=%s): Adding DT_NEEDED task: %s",
           ns->get_name(), task->get_name(), name);
    load_tasks->push_back(LoadTask::create(name, si, ns, task->get_readers_map()));
  });

  return true;
}
```

### load_library(realpath)

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#1261

```cpp
static bool load_library(android_namespace_t* ns,
                         LoadTask* task,
                         LoadTaskList* load_tasks,
                         int rtld_flags,
                         const std::string& realpath,
                         bool search_linked_namespaces) {
  off64_t file_offset = task->get_file_offset();
  const char* name = task->get_name();
  const android_dlextinfo* extinfo = task->get_extinfo();

  //1. 各种合法性检查,约100行
  ......

  //2. 申请soinfo空间
  soinfo* si = soinfo_alloc(ns, realpath.c_str(), &file_stat, file_offset, rtld_flags);
  if (si == nullptr) {
    return false;
  }

  task->set_soinfo(si);

  // Read the ELF header and some of the segments.
  //3. 读取ELF头
  if (!task->read(realpath.c_str(), file_stat.st_size)) {
    soinfo_free(si);
    task->set_soinfo(nullptr);
    return false;
  }

  // find and set DT_RUNPATH and dt_soname
  // Note that these field values are temporary and are
  // going to be overwritten on soinfo::prelink_image
  // with values from PT_LOAD segments.
  const ElfReader& elf_reader = task->get_elf_reader();
  //4. 遍历dynamic段,解析表项的符号
  for (const ElfW(Dyn)* d = elf_reader.dynamic(); d->d_tag != DT_NULL; ++d) {
    if (d->d_tag == DT_RUNPATH) {
      si->set_dt_runpath(elf_reader.get_string(d->d_un.d_val));
    }
    if (d->d_tag == DT_SONAME) {
      si->set_soname(elf_reader.get_string(d->d_un.d_val));
    }
  }

#if !defined(__ANDROID__)
  // Bionic on the host currently uses some Android prebuilts, which don't set
  // DT_RUNPATH with any relative paths, so they can't find their dependencies.
  // b/118058804
  if (si->get_dt_runpath().empty()) {
    si->set_dt_runpath("$ORIGIN/../lib64:$ORIGIN/lib64");
  }
#endif

  //5. 模版函数for_each_dt_needed,遍历dynamic段,将so的依赖库添加至load_tasks队列中
  for_each_dt_needed(task->get_elf_reader(), [&](const char* name) {
    LD_LOG(kLogDlopen, "load_library(ns=%s, task=%s): Adding DT_NEEDED task: %s",
           ns->get_name(), task->get_name(), name);
    load_tasks->push_back(LoadTask::create(name, si, ns, task->get_readers_map()));
  });

  return true;
}
```

for_each_dt_needed

```cpp
//android-platform\bionic\linker\linker_soinfo.h
template&lt;typename F&gt;
void for_each_dt_needed(const soinfo* si, F action) {
  for (const ElfW(Dyn)* d = si->dynamic; d->d_tag != DT_NULL; ++d) {
    if (d->d_tag == DT_NEEDED) {
      action(fix_dt_needed(si->get_string(d->d_un.d_val), si->get_realpath()));
    }
  }
}
```

### LoadTask::read

读取阶段的入口, 封装了`ElfReader::Read`。与32位不同, 64位将读取(Read)和加载(Load)拆分为两个独立步骤

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#694

```cpp
  bool read(const char* realpath, off64_t file_size) {
    ElfReader& elf_reader = get_elf_reader();
    return elf_reader.Read(realpath, fd_, file_offset_, file_size);
  }
```

### ElfReader::Read

64位的ELF读取流程, 与32位相比新增了`ReadSectionHeaders`和`ReadDynamicSection`。读取完成后设置`did_read_`标记避免重复读取

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker_phdr.cpp#149

```cpp
bool ElfReader::Read(const char* name, int fd, off64_t file_offset, off64_t file_size) {
  if (did_read_) {
    return true;
  }
  name_ = name;
  fd_ = fd;
  file_offset_ = file_offset;
  file_size_ = file_size;

  if (ReadElfHeader() &&
      VerifyElfHeader() &&
      ReadProgramHeaders() &&
      ReadSectionHeaders() &&
      ReadDynamicSection()) {
    did_read_ = true;
  }

  return did_read_;
}
```

##### ElfReader::ReadElfHeader

```cpp
bool ElfReader::ReadElfHeader() {
  ssize_t rc = TEMP_FAILURE_RETRY(pread64(fd_, &header_, sizeof(header_), file_offset_));
  if (rc < 0) {
    DL_ERR("can't read file \"%s\": %s", name_.c_str(), strerror(errno));
    return false;
  }

  if (rc != sizeof(header_)) {
    DL_ERR("\"%s\" is too small to be an ELF executable: only found %zd bytes", name_.c_str(),
           static_cast<size_t>(rc));
    return false;
  }
  return true;
}
```

##### ElfReader::VerifyElfHeader

```cpp
bool ElfReader::VerifyElfHeader() {
  if (memcmp(header_.e_ident, ELFMAG, SELFMAG) != 0) {
    DL_ERR("\"%s\" has bad ELF magic: %02x%02x%02x%02x", name_.c_str(),
           header_.e_ident[0], header_.e_ident[1], header_.e_ident[2], header_.e_ident[3]);
    return false;
  }

  // Try to give a clear diagnostic for ELF class mismatches, since they're
  // an easy mistake to make during the 32-bit/64-bit transition period.
  int elf_class = header_.e_ident[EI_CLASS];
#if defined(__LP64__)
  if (elf_class != ELFCLASS64) {
    if (elf_class == ELFCLASS32) {
      DL_ERR("\"%s\" is 32-bit instead of 64-bit", name_.c_str());
    } else {
      DL_ERR("\"%s\" has unknown ELF class: %d", name_.c_str(), elf_class);
    }
    return false;
  }
#else
  if (elf_class != ELFCLASS32) {
    if (elf_class == ELFCLASS64) {
      DL_ERR("\"%s\" is 64-bit instead of 32-bit", name_.c_str());
    } else {
      DL_ERR("\"%s\" has unknown ELF class: %d", name_.c_str(), elf_class);
    }
    return false;
  }
#endif

  if (header_.e_ident[EI_DATA] != ELFDATA2LSB) {
    DL_ERR("\"%s\" not little-endian: %d", name_.c_str(), header_.e_ident[EI_DATA]);
    return false;
  }

  if (header_.e_type != ET_DYN) {
    DL_ERR("\"%s\" has unexpected e_type: %d", name_.c_str(), header_.e_type);
    return false;
  }

  if (header_.e_version != EV_CURRENT) {
    DL_ERR("\"%s\" has unexpected e_version: %d", name_.c_str(), header_.e_version);
    return false;
  }

  if (header_.e_machine != GetTargetElfMachine()) {
    DL_ERR("\"%s\" is for %s (%d) instead of %s (%d)",
           name_.c_str(),
           EM_to_string(header_.e_machine), header_.e_machine,
           EM_to_string(GetTargetElfMachine()), GetTargetElfMachine());
    return false;
  }

  if (header_.e_shentsize != sizeof(ElfW(Shdr))) {
    // Fail if app is targeting Android O or above
    if (get_application_target_sdk_version() >= __ANDROID_API_O__) {
      DL_ERR_AND_LOG("\"%s\" has unsupported e_shentsize: 0x%x (expected 0x%zx)",
                     name_.c_str(), header_.e_shentsize, sizeof(ElfW(Shdr)));
      return false;
    }
    DL_WARN_documented_change(__ANDROID_API_O__,
                              "invalid-elf-header_section-headers-enforced-for-api-level-26",
                              "\"%s\" has unsupported e_shentsize 0x%x (expected 0x%zx)",
                              name_.c_str(), header_.e_shentsize, sizeof(ElfW(Shdr)));
    add_dlwarning(name_.c_str(), "has invalid ELF header");
  }

  if (header_.e_shstrndx == 0) {
    // Fail if app is targeting Android O or above
    if (get_application_target_sdk_version() >= __ANDROID_API_O__) {
      DL_ERR_AND_LOG("\"%s\" has invalid e_shstrndx", name_.c_str());
      return false;
    }

    DL_WARN_documented_change(__ANDROID_API_O__,
                              "invalid-elf-header_section-headers-enforced-for-api-level-26",
                              "\"%s\" has invalid e_shstrndx", name_.c_str());
    add_dlwarning(name_.c_str(), "has invalid ELF header");
  }

  return true;
}
```

##### ElfReader::ReadProgramHeaders

```cpp
bool ElfReader::ReadProgramHeaders() {
  phdr_num_ = header_.e_phnum;

  // Like the kernel, we only accept program header tables that
  // are smaller than 64KiB.
  if (phdr_num_ < 1 || phdr_num_ > 65536/sizeof(ElfW(Phdr))) {
    DL_ERR("\"%s\" has invalid e_phnum: %zd", name_.c_str(), phdr_num_);
    return false;
  }

  // Boundary checks
  size_t size = phdr_num_ * sizeof(ElfW(Phdr));
  if (!CheckFileRange(header_.e_phoff, size, alignof(ElfW(Phdr)))) {
    DL_ERR_AND_LOG("\"%s\" has invalid phdr offset/size: %zu/%zu",
                   name_.c_str(),
                   static_cast<size_t>(header_.e_phoff),
                   size);
    return false;
  }

  if (!phdr_fragment_.Map(fd_, file_offset_, header_.e_phoff, size)) {
    DL_ERR("\"%s\" phdr mmap failed: %s", name_.c_str(), strerror(errno));
    return false;
  }

  phdr_table_ = static_cast&lt;ElfW(Phdr)*&gt;(phdr_fragment_.data());
  return true;
}
```

##### ElfReader::ReadSectionHeaders

```cpp
bool ElfReader::ReadSectionHeaders() {
  shdr_num_ = header_.e_shnum;

  if (shdr_num_ == 0) {
    DL_ERR_AND_LOG("\"%s\" has no section headers", name_.c_str());
    return false;
  }

  size_t size = shdr_num_ * sizeof(ElfW(Shdr));
  if (!CheckFileRange(header_.e_shoff, size, alignof(const ElfW(Shdr)))) {
    DL_ERR_AND_LOG("\"%s\" has invalid shdr offset/size: %zu/%zu",
                   name_.c_str(),
                   static_cast<size_t>(header_.e_shoff),
                   size);
    return false;
  }

  if (!shdr_fragment_.Map(fd_, file_offset_, header_.e_shoff, size)) {
    DL_ERR("\"%s\" shdr mmap failed: %s", name_.c_str(), strerror(errno));
    return false;
  }

  shdr_table_ = static_cast&lt;const ElfW(Shdr)*&gt;(shdr_fragment_.data());
  return true;
}
```

##### ElfReader::ReadDynamicSection

```cpp
bool ElfReader::ReadDynamicSection() {
  // 1. Find .dynamic section (in section headers)
  const ElfW(Shdr)* dynamic_shdr = nullptr;
  for (size_t i = 0; i < shdr_num_; ++i) {
    if (shdr_table_[i].sh_type == SHT_DYNAMIC) {
      dynamic_shdr = &shdr_table_ [i];
      break;
    }
  }

  if (dynamic_shdr == nullptr) {
    DL_ERR_AND_LOG("\"%s\" .dynamic section header was not found", name_.c_str());
    return false;
  }

  // Make sure dynamic_shdr offset and size matches PT_DYNAMIC phdr
  size_t pt_dynamic_offset = 0;
  size_t pt_dynamic_filesz = 0;
  for (size_t i = 0; i < phdr_num_; ++i) {
    const ElfW(Phdr)* phdr = &phdr_table_[i];
    if (phdr->p_type == PT_DYNAMIC) {
      pt_dynamic_offset = phdr->p_offset;
      pt_dynamic_filesz = phdr->p_filesz;
    }
  }

  if (pt_dynamic_offset != dynamic_shdr->sh_offset) {
    if (get_application_target_sdk_version() >= __ANDROID_API_O__) {
      DL_ERR_AND_LOG("\"%s\" .dynamic section has invalid offset: 0x%zx, "
                     "expected to match PT_DYNAMIC offset: 0x%zx",
                     name_.c_str(),
                     static_cast<size_t>(dynamic_shdr->sh_offset),
                     pt_dynamic_offset);
      return false;
    }
    DL_WARN_documented_change(__ANDROID_API_O__,
                              "invalid-elf-header_section-headers-enforced-for-api-level-26",
                              "\"%s\" .dynamic section has invalid offset: 0x%zx "
                              "(expected to match PT_DYNAMIC offset 0x%zx)",
                              name_.c_str(),
                              static_cast<size_t>(dynamic_shdr->sh_offset),
                              pt_dynamic_offset);
    add_dlwarning(name_.c_str(), "invalid .dynamic section");
  }

  if (pt_dynamic_filesz != dynamic_shdr->sh_size) {
    if (get_application_target_sdk_version() >= __ANDROID_API_O__) {
      DL_ERR_AND_LOG("\"%s\" .dynamic section has invalid size: 0x%zx, "
                     "expected to match PT_DYNAMIC filesz: 0x%zx",
                     name_.c_str(),
                     static_cast<size_t>(dynamic_shdr->sh_size),
                     pt_dynamic_filesz);
      return false;
    }
    DL_WARN_documented_change(__ANDROID_API_O__,
                              "invalid-elf-header_section-headers-enforced-for-api-level-26",
                              "\"%s\" .dynamic section has invalid size: 0x%zx "
                              "(expected to match PT_DYNAMIC filesz 0x%zx)",
                              name_.c_str(),
                              static_cast<size_t>(dynamic_shdr->sh_size),
                              pt_dynamic_filesz);
    add_dlwarning(name_.c_str(), "invalid .dynamic section");
  }

  if (dynamic_shdr->sh_link >= shdr_num_) {
    DL_ERR_AND_LOG("\"%s\" .dynamic section has invalid sh_link: %d",
                   name_.c_str(),
                   dynamic_shdr->sh_link);
    return false;
  }

  const ElfW(Shdr)* strtab_shdr = &shdr_table_[dynamic_shdr->sh_link];

  if (strtab_shdr->sh_type != SHT_STRTAB) {
    DL_ERR_AND_LOG("\"%s\" .dynamic section has invalid link(%d) sh_type: %d (expected SHT_STRTAB)",
                   name_.c_str(), dynamic_shdr->sh_link, strtab_shdr->sh_type);
    return false;
  }

  if (!CheckFileRange(dynamic_shdr->sh_offset, dynamic_shdr->sh_size, alignof(const ElfW(Dyn)))) {
    DL_ERR_AND_LOG("\"%s\" has invalid offset/size of .dynamic section", name_.c_str());
    return false;
  }

  if (!dynamic_fragment_.Map(fd_, file_offset_, dynamic_shdr->sh_offset, dynamic_shdr->sh_size)) {
    DL_ERR("\"%s\" dynamic section mmap failed: %s", name_.c_str(), strerror(errno));
    return false;
  }

  dynamic_ = static_cast&lt;const ElfW(Dyn)*&gt;(dynamic_fragment_.data());

  if (!CheckFileRange(strtab_shdr->sh_offset, strtab_shdr->sh_size, alignof(const char))) {
    DL_ERR_AND_LOG("\"%s\" has invalid offset/size of the .strtab section linked from .dynamic section",
                   name_.c_str());
    return false;
  }

  if (!strtab_fragment_.Map(fd_, file_offset_, strtab_shdr->sh_offset, strtab_shdr->sh_size)) {
    DL_ERR("\"%s\" strtab section mmap failed: %s", name_.c_str(), strerror(errno));
    return false;
  }

  strtab_ = static_cast&lt;const char*&gt;(strtab_fragment_.data());
  strtab_size_ = strtab_fragment_.size();
  return true;
}
```

### find_libraries step2: load libraries (random order)

乱序加载的原因是为了抵御攻击

```cpp
 // Step 2: Load libraries in random order (see b/24047022)
  LoadTaskList load_list;
  for (auto&& task : load_tasks) {
    soinfo* si = task->get_soinfo();
    auto pred = [&](const LoadTask* t) {
      return t->get_soinfo() == si;
    };

    if (!si->is_linked() &&
        std::find_if(load_list.begin(), load_list.end(), pred) == load_list.end() ) {
      load_list.push_back(task);
    }
  }
  bool reserved_address_recursive = false;
  if (extinfo) {
    reserved_address_recursive = extinfo->flags & ANDROID_DLEXT_RESERVED_ADDRESS_RECURSIVE;
  }
  if (!reserved_address_recursive) {
    // Shuffle the load order in the normal case, but not if we are loading all
    // the libraries to a reserved address range.
    shuffle(&load_list);
  }

  // Set up address space parameters.
  address_space_params extinfo_params, default_params;
  size_t relro_fd_offset = 0;
  if (extinfo) {
    if (extinfo->flags & ANDROID_DLEXT_RESERVED_ADDRESS) {
      extinfo_params.start_addr = extinfo->reserved_addr;
      extinfo_params.reserved_size = extinfo->reserved_size;
      extinfo_params.must_use_address = true;
    } else if (extinfo->flags & ANDROID_DLEXT_RESERVED_ADDRESS_HINT) {
      extinfo_params.start_addr = extinfo->reserved_addr;
      extinfo_params.reserved_size = extinfo->reserved_size;
    }
  }

  for (auto&& task : load_list) {
    address_space_params* address_space =
        (reserved_address_recursive || !task->is_dt_needed()) ? &extinfo_params : &default_params;
    //
    if (!task->load(address_space)) {
      return false;
    }
  }
```

#### LoadTask::load

 将ELF的相关结构的值赋值给soinfo

```cpp
bool load(address_space_params* address_space) {
    ElfReader& elf_reader = get_elf_reader();
    if (!elf_reader.Load(address_space)) {
      return false;
    }

    si_->base = elf_reader.load_start();
    si_->size = elf_reader.load_size();
    si_->set_mapped_by_caller(elf_reader.is_mapped_by_caller());
    si_->load_bias = elf_reader.load_bias();
    si_->phnum = elf_reader.phdr_count();
    si_->phdr = elf_reader.loaded_phdr();

    return true;
  }
```

## Linker Link&Relocate So

SO加载到内存后进入链接和重定位阶段, 对应`find_libraries`的Step 3-7

### step3: pre-link needed libraries

广度优先遍历所有已加载的SO, 调用`prelink_image`解析各自的Dynamic段, 提取符号表、重定位表、Hash表、初始化函数等信息

```cpp
  // Step 3: pre-link all DT_NEEDED libraries in breadth first order.
  for (auto&& task : load_tasks) {
    soinfo* si = task->get_soinfo();
    if (!si->is_linked() && !si->prelink_image()) {
      return false;
    }
    register_soinfo_tls(si);
  }
```

调用prelink_image来预链接依赖库，遍历 dynamic段提取必要的信息

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#3374

```cpp
bool soinfo::prelink_image() {
  /* Extract dynamic section */
  ElfW(Word) dynamic_flags = 0;
  phdr_table_get_dynamic_section(phdr, phnum, load_bias, &dynamic, &dynamic_flags);

  /* We can't log anything until the linker is relocated */
  bool relocating_linker = (flags_ & FLAG_LINKER) != 0;
  if (!relocating_linker) {
    INFO("[ Linking \"%s\" ]", get_realpath());
    DEBUG("si->base = %p si->flags = 0x%08x", reinterpret_cast&lt;void*&gt;(base), flags_);
  }

  if (dynamic == nullptr) {
    if (!relocating_linker) {
      DL_ERR("missing PT_DYNAMIC in \"%s\"", get_realpath());
    }
    return false;
  } else {
    if (!relocating_linker) {
      DEBUG("dynamic = %p", dynamic);
    }
  }

#if defined(__arm__)
  (void) phdr_table_get_arm_exidx(phdr, phnum, load_bias,
                                  &ARM_exidx, &ARM_exidx_count);
#endif

  TlsSegment tls_segment;
  if (__bionic_get_tls_segment(phdr, phnum, load_bias, &tls_segment)) {
    if (!__bionic_check_tls_alignment(&tls_segment.alignment)) {
      if (!relocating_linker) {
        DL_ERR("TLS segment alignment in \"%s\" is not a power of 2: %zu",
               get_realpath(), tls_segment.alignment);
      }
      return false;
    }
    tls_ = std::make_unique<soinfo_tls>();
    tls_->segment = tls_segment;
  }

  // Extract useful information from dynamic section.
  // Note that: "Except for the DT_NULL element at the end of the array,
  // and the relative order of DT_NEEDED elements, entries may appear in any order."
  //
  // source: http://www.sco.com/developers/gabi/1998-04-29/ch5.dynamic.html
  uint32_t needed_count = 0;
  for (ElfW(Dyn)* d = dynamic; d->d_tag != DT_NULL; ++d) {
    DEBUG("d = %p, d[0](tag) = %p d[1](val) = %p",
          d, reinterpret_cast&lt;void*&gt;(d->d_tag), reinterpret_cast&lt;void*&gt;(d->d_un.d_val));
    switch (d->d_tag) {
      case DT_SONAME:
        // this is parsed after we have strtab initialized (see below).
        break;

      case DT_HASH:
        nbucket_ = reinterpret_cast<uint32_t*>(load_bias + d->d_un.d_ptr)[0];
        nchain_ = reinterpret_cast<uint32_t*>(load_bias + d->d_un.d_ptr)[1];
        bucket_ = reinterpret_cast<uint32_t*>(load_bias + d->d_un.d_ptr + 8);
        chain_ = reinterpret_cast<uint32_t*>(load_bias + d->d_un.d_ptr + 8 + nbucket_ * 4);
        break;

      case DT_GNU_HASH:
        gnu_nbucket_ = reinterpret_cast<uint32_t*>(load_bias + d->d_un.d_ptr)[0];
        // skip symndx
        gnu_maskwords_ = reinterpret_cast<uint32_t*>(load_bias + d->d_un.d_ptr)[2];
        gnu_shift2_ = reinterpret_cast<uint32_t*>(load_bias + d->d_un.d_ptr)[3];

        gnu_bloom_filter_ = reinterpret_cast&lt;ElfW(Addr)*&gt;(load_bias + d->d_un.d_ptr + 16);
        gnu_bucket_ = reinterpret_cast<uint32_t*>(gnu_bloom_filter_ + gnu_maskwords_);
        // amend chain for symndx = header[1]
        gnu_chain_ = gnu_bucket_ + gnu_nbucket_ -
            reinterpret_cast<uint32_t*>(load_bias + d->d_un.d_ptr)[1];

        if (!powerof2(gnu_maskwords_)) {
          DL_ERR("invalid maskwords for gnu_hash = 0x%x, in \"%s\" expecting power to two",
              gnu_maskwords_, get_realpath());
          return false;
        }
        --gnu_maskwords_;

        flags_ |= FLAG_GNU_HASH;
        break;

      case DT_STRTAB:
        strtab_ = reinterpret_cast&lt;const char*&gt;(load_bias + d->d_un.d_ptr);
        break;

      case DT_STRSZ:
        strtab_size_ = d->d_un.d_val;
        break;

      case DT_SYMTAB:
        symtab_ = reinterpret_cast&lt;ElfW(Sym)*&gt;(load_bias + d->d_un.d_ptr);
        break;

      case DT_SYMENT:
        if (d->d_un.d_val != sizeof(ElfW(Sym))) {
          DL_ERR("invalid DT_SYMENT: %zd in \"%s\"",
              static_cast<size_t>(d->d_un.d_val), get_realpath());
          return false;
        }
        break;

      case DT_PLTREL:
#if defined(USE_RELA)
        if (d->d_un.d_val != DT_RELA) {
          DL_ERR("unsupported DT_PLTREL in \"%s\"; expected DT_RELA", get_realpath());
          return false;
        }
#else
        if (d->d_un.d_val != DT_REL) {
          DL_ERR("unsupported DT_PLTREL in \"%s\"; expected DT_REL", get_realpath());
          return false;
        }
#endif
        break;

      case DT_JMPREL:
#if defined(USE_RELA)
        plt_rela_ = reinterpret_cast&lt;ElfW(Rela)*&gt;(load_bias + d->d_un.d_ptr);
#else
        plt_rel_ = reinterpret_cast&lt;ElfW(Rel)*&gt;(load_bias + d->d_un.d_ptr);
#endif
        break;

      case DT_PLTRELSZ:
#if defined(USE_RELA)
        plt_rela_count_ = d->d_un.d_val / sizeof(ElfW(Rela));
#else
        plt_rel_count_ = d->d_un.d_val / sizeof(ElfW(Rel));
#endif
        break;

      case DT_PLTGOT:
#if defined(__mips__)
        // Used by mips and mips64.
        plt_got_ = reinterpret_cast&lt;ElfW(Addr)**&gt;(load_bias + d->d_un.d_ptr);
#endif
        // Ignore for other platforms... (because RTLD_LAZY is not supported)
        break;

      case DT_DEBUG:
        // Set the DT_DEBUG entry to the address of _r_debug for GDB
        // if the dynamic table is writable
// FIXME: not working currently for N64
// The flags for the LOAD and DYNAMIC program headers do not agree.
// The LOAD section containing the dynamic table has been mapped as
// read-only, but the DYNAMIC header claims it is writable.
#if !(defined(__mips__) && defined(__LP64__))
        if ((dynamic_flags & PF_W) != 0) {
          d->d_un.d_val = reinterpret_cast<uintptr_t>(&_r_debug);
        }
#endif
        break;
#if defined(USE_RELA)
      case DT_RELA:
        rela_ = reinterpret_cast&lt;ElfW(Rela)*&gt;(load_bias + d->d_un.d_ptr);
        break;

      case DT_RELASZ:
        rela_count_ = d->d_un.d_val / sizeof(ElfW(Rela));
        break;

      case DT_ANDROID_RELA:
        android_relocs_ = reinterpret_cast<uint8_t*>(load_bias + d->d_un.d_ptr);
        break;

      case DT_ANDROID_RELASZ:
        android_relocs_size_ = d->d_un.d_val;
        break;

      case DT_ANDROID_REL:
        DL_ERR("unsupported DT_ANDROID_REL in \"%s\"", get_realpath());
        return false;

      case DT_ANDROID_RELSZ:
        DL_ERR("unsupported DT_ANDROID_RELSZ in \"%s\"", get_realpath());
        return false;

      case DT_RELAENT:
        if (d->d_un.d_val != sizeof(ElfW(Rela))) {
          DL_ERR("invalid DT_RELAENT: %zd", static_cast<size_t>(d->d_un.d_val));
          return false;
        }
        break;

      // Ignored (see DT_RELCOUNT comments for details).
      case DT_RELACOUNT:
        break;

      case DT_REL:
        DL_ERR("unsupported DT_REL in \"%s\"", get_realpath());
        return false;

      case DT_RELSZ:
        DL_ERR("unsupported DT_RELSZ in \"%s\"", get_realpath());
        return false;

#else
      case DT_REL:
        rel_ = reinterpret_cast&lt;ElfW(Rel)*&gt;(load_bias + d->d_un.d_ptr);
        break;

      case DT_RELSZ:
        rel_count_ = d->d_un.d_val / sizeof(ElfW(Rel));
        break;

      case DT_RELENT:
        if (d->d_un.d_val != sizeof(ElfW(Rel))) {
          DL_ERR("invalid DT_RELENT: %zd", static_cast<size_t>(d->d_un.d_val));
          return false;
        }
        break;

      case DT_ANDROID_REL:
        android_relocs_ = reinterpret_cast<uint8_t*>(load_bias + d->d_un.d_ptr);
        break;

      case DT_ANDROID_RELSZ:
        android_relocs_size_ = d->d_un.d_val;
        break;

      case DT_ANDROID_RELA:
        DL_ERR("unsupported DT_ANDROID_RELA in \"%s\"", get_realpath());
        return false;

      case DT_ANDROID_RELASZ:
        DL_ERR("unsupported DT_ANDROID_RELASZ in \"%s\"", get_realpath());
        return false;

      // "Indicates that all RELATIVE relocations have been concatenated together,
      // and specifies the RELATIVE relocation count."
      //
      // TODO: Spec also mentions that this can be used to optimize relocation process;
      // Not currently used by bionic linker - ignored.
      case DT_RELCOUNT:
        break;

      case DT_RELA:
        DL_ERR("unsupported DT_RELA in \"%s\"", get_realpath());
        return false;

      case DT_RELASZ:
        DL_ERR("unsupported DT_RELASZ in \"%s\"", get_realpath());
        return false;

#endif
      case DT_RELR:
        relr_ = reinterpret_cast&lt;ElfW(Relr)*&gt;(load_bias + d->d_un.d_ptr);
        break;

      case DT_RELRSZ:
        relr_count_ = d->d_un.d_val / sizeof(ElfW(Relr));
        break;

      case DT_RELRENT:
        if (d->d_un.d_val != sizeof(ElfW(Relr))) {
          DL_ERR("invalid DT_RELRENT: %zd", static_cast<size_t>(d->d_un.d_val));
          return false;
        }
        break;

      // Ignored (see DT_RELCOUNT comments for details).
      case DT_RELRCOUNT:
        break;

      case DT_INIT:
        init_func_ = reinterpret_cast<linker_ctor_function_t>(load_bias + d->d_un.d_ptr);
        DEBUG("%s constructors (DT_INIT) found at %p", get_realpath(), init_func_);
        break;

      case DT_FINI:
        fini_func_ = reinterpret_cast<linker_dtor_function_t>(load_bias + d->d_un.d_ptr);
        DEBUG("%s destructors (DT_FINI) found at %p", get_realpath(), fini_func_);
        break;

      case DT_INIT_ARRAY:
        init_array_ = reinterpret_cast<linker_ctor_function_t*>(load_bias + d->d_un.d_ptr);
        DEBUG("%s constructors (DT_INIT_ARRAY) found at %p", get_realpath(), init_array_);
        break;

      case DT_INIT_ARRAYSZ:
        init_array_count_ = static_cast<uint32_t>(d->d_un.d_val) / sizeof(ElfW(Addr));
        break;

      case DT_FINI_ARRAY:
        fini_array_ = reinterpret_cast<linker_dtor_function_t*>(load_bias + d->d_un.d_ptr);
        DEBUG("%s destructors (DT_FINI_ARRAY) found at %p", get_realpath(), fini_array_);
        break;

      case DT_FINI_ARRAYSZ:
        fini_array_count_ = static_cast<uint32_t>(d->d_un.d_val) / sizeof(ElfW(Addr));
        break;

      case DT_PREINIT_ARRAY:
        preinit_array_ = reinterpret_cast<linker_ctor_function_t*>(load_bias + d->d_un.d_ptr);
        DEBUG("%s constructors (DT_PREINIT_ARRAY) found at %p", get_realpath(), preinit_array_);
        break;

      case DT_PREINIT_ARRAYSZ:
        preinit_array_count_ = static_cast<uint32_t>(d->d_un.d_val) / sizeof(ElfW(Addr));
        break;

      case DT_TEXTREL:
#if defined(__LP64__)
        DL_ERR("\"%s\" has text relocations", get_realpath());
        return false;
#else
        has_text_relocations = true;
        break;
#endif

      case DT_SYMBOLIC:
        has_DT_SYMBOLIC = true;
        break;

      case DT_NEEDED:
        ++needed_count;
        break;

      case DT_FLAGS:
        if (d->d_un.d_val & DF_TEXTREL) {
#if defined(__LP64__)
          DL_ERR("\"%s\" has text relocations", get_realpath());
          return false;
#else
          has_text_relocations = true;
#endif
        }
        if (d->d_un.d_val & DF_SYMBOLIC) {
          has_DT_SYMBOLIC = true;
        }
        break;

      case DT_FLAGS_1:
        set_dt_flags_1(d->d_un.d_val);

        if ((d->d_un.d_val & ~SUPPORTED_DT_FLAGS_1) != 0) {
          DL_WARN("Warning: \"%s\" has unsupported flags DT_FLAGS_1=%p "
                  "(ignoring unsupported flags)",
                  get_realpath(), reinterpret_cast&lt;void*&gt;(d->d_un.d_val));
        }
        break;
#if defined(__mips__)
      case DT_MIPS_RLD_MAP:
        // Set the DT_MIPS_RLD_MAP entry to the address of _r_debug for GDB.
        {
          r_debug** dp = reinterpret_cast<r_debug**>(load_bias + d->d_un.d_ptr);
          *dp = &_r_debug;
        }
        break;
      case DT_MIPS_RLD_MAP_REL:
        // Set the DT_MIPS_RLD_MAP_REL entry to the address of _r_debug for GDB.
        {
          r_debug** dp = reinterpret_cast<r_debug**>(
              reinterpret_cast&lt;ElfW(Addr)&gt;(d) + d->d_un.d_val);
          *dp = &_r_debug;
        }
        break;

      case DT_MIPS_RLD_VERSION:
      case DT_MIPS_FLAGS:
      case DT_MIPS_BASE_ADDRESS:
      case DT_MIPS_UNREFEXTNO:
        break;

      case DT_MIPS_SYMTABNO:
        mips_symtabno_ = d->d_un.d_val;
        break;

      case DT_MIPS_LOCAL_GOTNO:
        mips_local_gotno_ = d->d_un.d_val;
        break;

      case DT_MIPS_GOTSYM:
        mips_gotsym_ = d->d_un.d_val;
        break;
#endif
      // Ignored: "Its use has been superseded by the DF_BIND_NOW flag"
      case DT_BIND_NOW:
        break;

      case DT_VERSYM:
        versym_ = reinterpret_cast&lt;ElfW(Versym)*&gt;(load_bias + d->d_un.d_ptr);
        break;

      case DT_VERDEF:
        verdef_ptr_ = load_bias + d->d_un.d_ptr;
        break;
      case DT_VERDEFNUM:
        verdef_cnt_ = d->d_un.d_val;
        break;

      case DT_VERNEED:
        verneed_ptr_ = load_bias + d->d_un.d_ptr;
        break;

      case DT_VERNEEDNUM:
        verneed_cnt_ = d->d_un.d_val;
        break;

      case DT_RUNPATH:
        // this is parsed after we have strtab initialized (see below).
        break;

      case DT_TLSDESC_GOT:
      case DT_TLSDESC_PLT:
        // These DT entries are used for lazy TLSDESC relocations. Bionic
        // resolves everything eagerly, so these can be ignored.
        break;

      default:
        if (!relocating_linker) {
          const char* tag_name;
          if (d->d_tag == DT_RPATH) {
            tag_name = "DT_RPATH";
          } else if (d->d_tag == DT_ENCODING) {
            tag_name = "DT_ENCODING";
          } else if (d->d_tag >= DT_LOOS && d->d_tag <= DT_HIOS) {
            tag_name = "unknown OS-specific";
          } else if (d->d_tag >= DT_LOPROC && d->d_tag <= DT_HIPROC) {
            tag_name = "unknown processor-specific";
          } else {
            tag_name = "unknown";
          }
          DL_WARN("Warning: \"%s\" unused DT entry: %s (type %p arg %p) (ignoring)",
                  get_realpath(),
                  tag_name,
                  reinterpret_cast&lt;void*&gt;(d->d_tag),
                  reinterpret_cast&lt;void*&gt;(d->d_un.d_val));
        }
        break;
    }
  }

#if defined(__mips__) && !defined(__LP64__)
  if (!mips_check_and_adjust_fp_modes()) {
    return false;
  }
#endif

  DEBUG("si->base = %p, si->strtab = %p, si->symtab = %p",
        reinterpret_cast&lt;void*&gt;(base), strtab_, symtab_);

  // Sanity checks.
  if (relocating_linker && needed_count != 0) {
    DL_ERR("linker cannot have DT_NEEDED dependencies on other libraries");
    return false;
  }
  if (nbucket_ == 0 && gnu_nbucket_ == 0) {
    DL_ERR("empty/missing DT_HASH/DT_GNU_HASH in \"%s\" "
        "(new hash type from the future?)", get_realpath());
    return false;
  }
  if (strtab_ == nullptr) {
    DL_ERR("empty/missing DT_STRTAB in \"%s\"", get_realpath());
    return false;
  }
  if (symtab_ == nullptr) {
    DL_ERR("empty/missing DT_SYMTAB in \"%s\"", get_realpath());
    return false;
  }

  // second pass - parse entries relying on strtab
  for (ElfW(Dyn)* d = dynamic; d->d_tag != DT_NULL; ++d) {
    switch (d->d_tag) {
      case DT_SONAME:
        set_soname(get_string(d->d_un.d_val));
        break;
      case DT_RUNPATH:
        set_dt_runpath(get_string(d->d_un.d_val));
        break;
    }
  }

  // Before M release linker was using basename in place of soname.
  // In the case when dt_soname is absent some apps stop working
  // because they can't find dt_needed library by soname.
  // This workaround should keep them working. (Applies only
  // for apps targeting sdk version < M.) Make an exception for
  // the main executable and linker; they do not need to have dt_soname.
  // TODO: >= O the linker doesn't need this workaround.
  if (soname_ == nullptr &&
      this != solist_get_somain() &&
      (flags_ & FLAG_LINKER) == 0 &&
      get_application_target_sdk_version() < __ANDROID_API_M__) {
    soname_ = basename(realpath_.c_str());
    DL_WARN_documented_change(__ANDROID_API_M__,
                              "missing-soname-enforced-for-api-level-23",
                              "\"%s\" has no DT_SONAME (will use %s instead)",
                              get_realpath(), soname_);

    // Don't call add_dlwarning because a missing DT_SONAME isn't important enough to show in the UI
  }
  return true;
}
```

### step:4 construct the global group

构建global_group: 为预链接的依赖库设置`DF_1_GLOBAL`全局标志, 将`LD_PRELOAD`库和显式标记的库收集到全局组中, 后续重定位时用于全局符号查找

```cpp
  // Step 4: Construct the global group. Note: DF_1_GLOBAL bit of a library is
  // determined at step 3.

  // Step 4-1: DF_1_GLOBAL bit is force set for LD_PRELOADed libs because they
  // must be added to the global group
  if (ld_preloads != nullptr) {
    for (auto&& si : *ld_preloads) {
      si->set_dt_flags_1(si->get_dt_flags_1() | DF_1_GLOBAL);
    }
  }

  // Step 4-2: Gather all DF_1_GLOBAL libs which were newly loaded during this
  // run. These will be the new member of the global group
  soinfo_list_t new_global_group_members;
  for (auto&& task : load_tasks) {
    soinfo* si = task->get_soinfo();
    if (!si->is_linked() && (si->get_dt_flags_1() & DF_1_GLOBAL) != 0) {
      new_global_group_members.push_back(si);
    }
  }

  // Step 4-3: Add the new global group members to all the linked namespaces
  if (namespaces != nullptr) {
    for (auto linked_ns : *namespaces) {
      for (auto si : new_global_group_members) {
        if (si->get_primary_namespace() != linked_ns) {
          linked_ns->add_soinfo(si);
          si->add_secondary_namespace(linked_ns);
        }
      }
    }
  }
```

### step5: collect roots of local_groups

收集本地组的根节点。每个未链接的soinfo如果自身就是`local_group_root`, 则作为一个独立的链接单元

```cpp
  // Step 5: Collect roots of local_groups.
  // Whenever needed_by->si link crosses a namespace boundary it forms its own local_group.
  // Here we collect new roots to link them separately later on. Note that we need to avoid
  // collecting duplicates. Also the order is important. They need to be linked in the same
  // BFS order we link individual libraries.
  std::vector&lt;soinfo*&gt; local_group_roots;
  if (start_with != nullptr && add_as_children) {
    local_group_roots.push_back(start_with);
  } else {
    CHECK(soinfos_count == 1);
    local_group_roots.push_back(soinfos[0]);
  }

  for (auto&& task : load_tasks) {
    soinfo* si = task->get_soinfo();
    soinfo* needed_by = task->get_needed_by();
    bool is_dt_needed = needed_by != nullptr && (needed_by != start_with || add_as_children);
    android_namespace_t* needed_by_ns =
        is_dt_needed ? needed_by->get_primary_namespace() : ns;

    if (!si->is_linked() && si->get_primary_namespace() != needed_by_ns) {
      auto it = std::find(local_group_roots.begin(), local_group_roots.end(), si);
      LD_LOG(kLogDlopen,
             "Crossing namespace boundary (si=%s@%p, si_ns=%s@%p, needed_by=%s@%p, ns=%s@%p, needed_by_ns=%s@%p) adding to local_group_roots: %s",
             si->get_realpath(),
             si,
             si->get_primary_namespace()->get_name(),
             si->get_primary_namespace(),
             needed_by == nullptr ? "(nullptr)" : needed_by->get_realpath(),
             needed_by,
             ns->get_name(),
             ns,
             needed_by_ns->get_name(),
             needed_by_ns,
             it == local_group_roots.end() ? "yes" : "no");

      if (it == local_group_roots.end()) {
        local_group_roots.push_back(si);
      }
    }
  }
```

### step6: link all local groups

遍历每个本地组根节点, 通过`walk_dependencies_tree`收集可访问的依赖, 然后调用`soinfo::link_image`执行真正的链接和重定位

```cpp
  // Step 6: Link all local groups
  for (auto root : local_group_roots) {
    soinfo_list_t local_group;
    android_namespace_t* local_group_ns = root->get_primary_namespace();

    walk_dependencies_tree(root,
      [&] (soinfo* si) {
        if (local_group_ns->is_accessible(si)) {
          local_group.push_back(si);
          return kWalkContinue;
        } else {
          return kWalkSkip;
        }
      });

    soinfo_list_t global_group = local_group_ns->get_global_group();
    bool linked = local_group.visit([&](soinfo* si) {
      // Even though local group may contain accessible soinfos from other namespaces
      // we should avoid linking them (because if they are not linked -> they
      // are in the local_group_roots and will be linked later).
      if (!si->is_linked() && si->get_primary_namespace() == local_group_ns) {
        const android_dlextinfo* link_extinfo = nullptr;
        if (si == soinfos[0] || reserved_address_recursive) {
          // Only forward extinfo for the first library unless the recursive
          // flag is set.
          link_extinfo = extinfo;
        }
        // 调用soinfo.link_image进行链接
        if (!si->link_image(global_group, local_group, link_extinfo, &relro_fd_offset) ||
            !get_cfi_shadow()->AfterLoad(si, solist_get_head())) {
          return false;
        }
      }

      return true;
    });

    if (!linked) {
      return false;
    }
  }
```

#### soinfo::link_image

链接的核心函数。主要工作: 调用`relocate`执行重定位(.rela.dyn + .rela.plt + android压缩重定位) → 应用GNU RELRO保护 → 标记已链接

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#3872

```cpp
bool soinfo::link_image(const soinfo_list_t& global_group, const soinfo_list_t& local_group,
                        const android_dlextinfo* extinfo, size_t* relro_fd_offset) {
  if (is_image_linked()) {
    // already linked.
    return true;
  }

  local_group_root_ = local_group.front();
  if (local_group_root_ == nullptr) {
    local_group_root_ = this;
  }

  if ((flags_ & FLAG_LINKER) == 0 && local_group_root_ == this) {
    target_sdk_version_ = get_application_target_sdk_version();
  }

  VersionTracker version_tracker;

  if (!version_tracker.init(this)) {
    return false;
  }

#if !defined(__LP64__)
    //......
#endif

  if (android_relocs_ != nullptr) {
    // check signature
    if (android_relocs_size_ > 3 &&
        android_relocs_[0] == 'A' &&
        android_relocs_[1] == 'P' &&
        android_relocs_[2] == 'S' &&
        android_relocs_[3] == '2') {
      DEBUG("[ android relocating %s ]", get_realpath());

      bool relocated = false;
      const uint8_t* packed_relocs = android_relocs_ + 4;
      const size_t packed_relocs_size = android_relocs_size_ - 4;

      // 调用relocate进行重定位
      relocated = relocate(
          version_tracker,
          packed_reloc_iterator<sleb128_decoder>(
            sleb128_decoder(packed_relocs, packed_relocs_size)),
          global_group, local_group);

      if (!relocated) {
        return false;
      }
    } else {
      DL_ERR("bad android relocation header.");
      return false;
    }
  }

  if (relr_ != nullptr) {
    DEBUG("[ relocating %s relr ]", get_realpath());
    if (!relocate_relr()) {
      return false;
    }
  }

#if defined(USE_RELA)
  if (rela_ != nullptr) {
    DEBUG("[ relocating %s rela ]", get_realpath());
    if (!relocate(version_tracker,
            plain_reloc_iterator(rela_, rela_count_), global_group, local_group)) {
      return false;
    }
  }
  if (plt_rela_ != nullptr) {
    DEBUG("[ relocating %s plt rela ]", get_realpath());
    if (!relocate(version_tracker,
            plain_reloc_iterator(plt_rela_, plt_rela_count_), global_group, local_group)) {
      return false;
    }
  }
#else
  if (rel_ != nullptr) {
    DEBUG("[ relocating %s rel ]", get_realpath());
    if (!relocate(version_tracker,
            plain_reloc_iterator(rel_, rel_count_), global_group, local_group)) {
      return false;
    }
  }
  if (plt_rel_ != nullptr) {
    DEBUG("[ relocating %s plt rel ]", get_realpath());
    if (!relocate(version_tracker,
            plain_reloc_iterator(plt_rel_, plt_rel_count_), global_group, local_group)) {
      return false;
    }
  }
#endif

#if defined(__mips__)
  if (!mips_relocate_got(version_tracker, global_group, local_group)) {
    return false;
  }
#endif

  DEBUG("[ finished linking %s ]", get_realpath());

#if !defined(__LP64__)
  if (has_text_relocations) {
    // All relocations are done, we can protect our segments back to read-only.
    if (phdr_table_protect_segments(phdr, phnum, load_bias) < 0) {
      DL_ERR("can't protect segments for \"%s\": %s",
             get_realpath(), strerror(errno));
      return false;
    }
  }
#endif

  // We can also turn on GNU RELRO protection if we're not linking the dynamic linker
  // itself --- it can't make system calls yet, and will have to call protect_relro later.
  if (!is_linker() && !protect_relro()) {
    return false;
  }

  /* Handle serializing/sharing the RELRO segment */
  if (extinfo && (extinfo->flags & ANDROID_DLEXT_WRITE_RELRO)) {
    if (phdr_table_serialize_gnu_relro(phdr, phnum, load_bias,
                                       extinfo->relro_fd, relro_fd_offset) < 0) {
      DL_ERR("failed serializing GNU RELRO section for \"%s\": %s",
             get_realpath(), strerror(errno));
      return false;
    }
  } else if (extinfo && (extinfo->flags & ANDROID_DLEXT_USE_RELRO)) {
    if (phdr_table_map_gnu_relro(phdr, phnum, load_bias,
                                 extinfo->relro_fd, relro_fd_offset) < 0) {
      DL_ERR("failed mapping GNU RELRO section for \"%s\": %s",
             get_realpath(), strerror(errno));
      return false;
    }
  }

  notify_gdb_of_load(this);
  set_image_linked();
  return true;
}

bool soinfo::protect_relro() {
  if (phdr_table_protect_gnu_relro(phdr, phnum, load_bias) < 0) {
    DL_ERR("can't enable GNU RELRO protection for \"%s\": %s",
           get_realpath(), strerror(errno));
    return false;
  }
  return true;
}
```

#### soinfo::relocate

64位的核心重定位函数。使用模板迭代器遍历RELA表, 对每个条目: 提取类型和符号 → 通过`soinfo_do_lookup`查找符号 → 根据重定位类型(RELATIVE/ABS64/GLOB_DAT/JUMP_SLOT/TLS等)计算目标地址并回填。与32位的主要区别: 使用`Elf64_Rela`(带addend)而非`Elf32_Rel`, 支持TLS重定位类型

https://cs.android.com/android/platform/superproject/+/android-10.0.0_r47:bionic/linker/linker.cpp#2862

```cpp
template&lt;typename ElfRelIteratorT&gt;
bool soinfo::relocate(const VersionTracker& version_tracker, ElfRelIteratorT&& rel_iterator,
                      const soinfo_list_t& global_group, const soinfo_list_t& local_group) {
  const size_t tls_tp_base = __libc_shared_globals()->static_tls_layout.offset_thread_pointer();
  std::vector&lt;std::pair&lt;TlsDescriptor*, size_t&gt;> deferred_tlsdesc_relocs;

  for (size_t idx = 0; rel_iterator.has_next(); ++idx) {
    const auto rel = rel_iterator.next();
    if (rel == nullptr) {
      return false;
    }

    ElfW(Word) type = ELFW(R_TYPE)(rel->r_info);
    ElfW(Word) sym = ELFW(R_SYM)(rel->r_info);

    ElfW(Addr) reloc = static_cast&lt;ElfW(Addr)&gt;(rel->r_offset + load_bias);
    ElfW(Addr) sym_addr = 0;
    const char* sym_name = nullptr;
    ElfW(Addr) addend = get_addend(rel, reloc);

    DEBUG("Processing \"%s\" relocation at index %zd", get_realpath(), idx);
    if (type == R_GENERIC_NONE) {
      continue;
    }

    const ElfW(Sym)* s = nullptr;
    soinfo* lsi = nullptr;

    if (sym == 0) {
      // By convention in ld.bfd and lld, an omitted symbol on a TLS relocation
      // is a reference to the current module.
      if (is_tls_reloc(type)) {
        lsi = this;
      }
    } else if (ELF_ST_BIND(symtab_[sym].st_info) == STB_LOCAL && is_tls_reloc(type)) {
      // In certain situations, the Gold linker accesses a TLS symbol using a
      // relocation to an STB_LOCAL symbol in .dynsym of either STT_SECTION or
      // STT_TLS type. Bionic doesn't support these relocations, so issue an
      // error. References:
      //  - https://groups.google.com/d/topic/generic-abi/dJ4_Y78aQ2M/discussion
      //  - https://sourceware.org/bugzilla/show_bug.cgi?id=17699
      s = &symtab_[sym];
      sym_name = get_string(s->st_name);
      DL_ERR("unexpected TLS reference to local symbol \"%s\": "
             "sym type %d, rel type %u (idx %zu of \"%s\")",
             sym_name, ELF_ST_TYPE(s->st_info), type, idx, get_realpath());
      return false;
    } else {
      sym_name = get_string(symtab_[sym].st_name);
      const version_info* vi = nullptr;

      if (!lookup_version_info(version_tracker, sym, sym_name, &vi)) {
        return false;
      }
      // 查找符号
      if (!soinfo_do_lookup(this, sym_name, vi, &lsi, global_group, local_group, &s)) {
        return false;
      }

      if (s == nullptr) {
        // We only allow an undefined symbol if this is a weak reference...
        s = &symtab_[sym];
        if (ELF_ST_BIND(s->st_info) != STB_WEAK) {
          DL_ERR("cannot locate symbol \"%s\" referenced by \"%s\"...", sym_name, get_realpath());
          return false;
        }

        /* IHI0044C AAELF 4.5.1.1:

           Libraries are not searched to resolve weak references.
           It is not an error for a weak reference to remain unsatisfied.

           During linking, the value of an undefined weak reference is:
           - Zero if the relocation type is absolute
           - The address of the place if the relocation is pc-relative
           - The address of nominal base address if the relocation
             type is base-relative.
         */
        // 解析重定位项类型
        switch (type) {
          case R_GENERIC_JUMP_SLOT:
          case R_GENERIC_GLOB_DAT:
          case R_GENERIC_RELATIVE:
          case R_GENERIC_IRELATIVE:
          case R_GENERIC_TLS_DTPMOD:
          case R_GENERIC_TLS_DTPREL:
          case R_GENERIC_TLS_TPREL:
          case R_GENERIC_TLSDESC:
#if defined(__aarch64__)
          case R_AARCH64_ABS64:
          case R_AARCH64_ABS32:
          case R_AARCH64_ABS16:
#elif defined(__x86_64__)
          case R_X86_64_32:
          case R_X86_64_64:
#elif defined(__arm__)
          case R_ARM_ABS32:
#elif defined(__i386__)
          case R_386_32:
#endif
            /*
             * The sym_addr was initialized to be zero above, or the relocation
             * code below does not care about value of sym_addr.
             * No need to do anything.
             */
            break;
#if defined(__x86_64__)
          case R_X86_64_PC32:
            sym_addr = reloc;
            break;
#elif defined(__i386__)
          case R_386_PC32:
            sym_addr = reloc;
            break;
#endif
          default:
            DL_ERR("unknown weak reloc type %d @ %p (%zu)", type, rel, idx);
            return false;
        }
      } else { // We got a definition.
#if !defined(__LP64__)
        // When relocating dso with text_relocation .text segment is
        // not executable. We need to restore elf flags before resolving
        // STT_GNU_IFUNC symbol.
        bool protect_segments = has_text_relocations &&
                                lsi == this &&
                                ELF_ST_TYPE(s->st_info) == STT_GNU_IFUNC;
        if (protect_segments) {
          if (phdr_table_protect_segments(phdr, phnum, load_bias) < 0) {
            DL_ERR("can't protect segments for \"%s\": %s",
                   get_realpath(), strerror(errno));
            return false;
          }
        }
#endif
        if (is_tls_reloc(type)) {
          if (ELF_ST_TYPE(s->st_info) != STT_TLS) {
            DL_ERR("reference to non-TLS symbol \"%s\" from TLS relocation in \"%s\"",
                   sym_name, get_realpath());
            return false;
          }
          if (lsi->get_tls() == nullptr) {
            DL_ERR("TLS relocation refers to symbol \"%s\" in solib \"%s\" with no TLS segment",
                   sym_name, lsi->get_realpath());
            return false;
          }
          sym_addr = s->st_value;
        } else {
          if (ELF_ST_TYPE(s->st_info) == STT_TLS) {
            DL_ERR("reference to TLS symbol \"%s\" from non-TLS relocation in \"%s\"",
                   sym_name, get_realpath());
            return false;
          }
          sym_addr = lsi->resolve_symbol_address(s);
        }
#if !defined(__LP64__)
        if (protect_segments) {
          if (phdr_table_unprotect_segments(phdr, phnum, load_bias) < 0) {
            DL_ERR("can't unprotect loadable segments for \"%s\": %s",
                   get_realpath(), strerror(errno));
            return false;
          }
        }
#endif
      }
      count_relocation(kRelocSymbol);
    }

    // 进行重定位操作
    switch (type) {
      case R_GENERIC_JUMP_SLOT:
        count_relocation(kRelocAbsolute);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO JMP_SLOT %16p <- %16p %s\n",
                   reinterpret_cast&lt;void*&gt;(reloc),
                   reinterpret_cast&lt;void*&gt;(sym_addr + addend), sym_name);

        *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = (sym_addr + addend);
        break;
      case R_GENERIC_GLOB_DAT:
        count_relocation(kRelocAbsolute);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO GLOB_DAT %16p <- %16p %s\n",
                   reinterpret_cast&lt;void*&gt;(reloc),
                   reinterpret_cast&lt;void*&gt;(sym_addr + addend), sym_name);
        *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = (sym_addr + addend);
        break;
      case R_GENERIC_RELATIVE:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO RELATIVE %16p <- %16p\n",
                   reinterpret_cast&lt;void*&gt;(reloc),
                   reinterpret_cast&lt;void*&gt;(load_bias + addend));
        *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = (load_bias + addend);
        break;
      case R_GENERIC_IRELATIVE:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO IRELATIVE %16p <- %16p\n",
                    reinterpret_cast&lt;void*&gt;(reloc),
                    reinterpret_cast&lt;void*&gt;(load_bias + addend));
        {
#if !defined(__LP64__)
          // When relocating dso with text_relocation .text segment is
          // not executable. We need to restore elf flags for this
          // particular call.
          if (has_text_relocations) {
            if (phdr_table_protect_segments(phdr, phnum, load_bias) < 0) {
              DL_ERR("can't protect segments for \"%s\": %s",
                     get_realpath(), strerror(errno));
              return false;
            }
          }
#endif
          ElfW(Addr) ifunc_addr = call_ifunc_resolver(load_bias + addend);
#if !defined(__LP64__)
          // Unprotect it afterwards...
          if (has_text_relocations) {
            if (phdr_table_unprotect_segments(phdr, phnum, load_bias) < 0) {
              DL_ERR("can't unprotect loadable segments for \"%s\": %s",
                     get_realpath(), strerror(errno));
              return false;
            }
          }
#endif
          *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = ifunc_addr;
        }
        break;
      case R_GENERIC_TLS_TPREL:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        {
          ElfW(Addr) tpoff = 0;
          if (lsi == nullptr) {
            // Unresolved weak relocation. Leave tpoff at 0 to resolve
            // &weak_tls_symbol to __get_tls().
          } else {
            CHECK(lsi->get_tls() != nullptr); // We rejected a missing TLS segment above.
            const TlsModule& mod = get_tls_module(lsi->get_tls()->module_id);
            if (mod.static_offset != SIZE_MAX) {
              tpoff += mod.static_offset - tls_tp_base;
            } else {
              DL_ERR("TLS symbol \"%s\" in dlopened \"%s\" referenced from \"%s\" using IE access model",
                     sym_name, lsi->get_realpath(), get_realpath());
              return false;
            }
          }
          tpoff += sym_addr + addend;
          TRACE_TYPE(RELO, "RELO TLS_TPREL %16p <- %16p %s\n",
                     reinterpret_cast&lt;void*&gt;(reloc),
                     reinterpret_cast&lt;void*&gt;(tpoff), sym_name);
          *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = tpoff;
        }
        break;

#if !defined(__aarch64__)
      // Omit support for DTPMOD/DTPREL on arm64, at least until
      // http://b/123385182 is fixed. arm64 uses TLSDESC instead.
      case R_GENERIC_TLS_DTPMOD:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        {
          size_t module_id = 0;
          if (lsi == nullptr) {
            // Unresolved weak relocation. Evaluate the module ID to 0.
          } else {
            CHECK(lsi->get_tls() != nullptr); // We rejected a missing TLS segment above.
            module_id = lsi->get_tls()->module_id;
          }
          TRACE_TYPE(RELO, "RELO TLS_DTPMOD %16p <- %zu %s\n",
                     reinterpret_cast&lt;void*&gt;(reloc), module_id, sym_name);
          *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = module_id;
        }
        break;
      case R_GENERIC_TLS_DTPREL:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO TLS_DTPREL %16p <- %16p %s\n",
                   reinterpret_cast&lt;void*&gt;(reloc),
                   reinterpret_cast&lt;void*&gt;(sym_addr + addend), sym_name);
        *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = sym_addr + addend;
        break;
#endif  // !defined(__aarch64__)

#if defined(__aarch64__)
      // Bionic currently only implements TLSDESC for arm64. This implementation should work with
      // other architectures, as long as the resolver functions are implemented.
      case R_GENERIC_TLSDESC:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        {
          TlsDescriptor* desc = reinterpret_cast&lt;TlsDescriptor*&gt;(reloc);
          if (lsi == nullptr) {
            // Unresolved weak relocation.
            desc->func = tlsdesc_resolver_unresolved_weak;
            desc->arg = addend;
            TRACE_TYPE(RELO, "RELO TLSDESC %16p <- unresolved weak 0x%zx %s\n",
                       reinterpret_cast&lt;void*&gt;(reloc), static_cast<size_t>(addend), sym_name);
          } else {
            CHECK(lsi->get_tls() != nullptr); // We rejected a missing TLS segment above.
            size_t module_id = lsi->get_tls()->module_id;
            const TlsModule& mod = get_tls_module(module_id);
            if (mod.static_offset != SIZE_MAX) {
              desc->func = tlsdesc_resolver_static;
              desc->arg = mod.static_offset - tls_tp_base + sym_addr + addend;
              TRACE_TYPE(RELO, "RELO TLSDESC %16p <- static (0x%zx - 0x%zx + 0x%zx + 0x%zx) %s\n",
                         reinterpret_cast&lt;void*&gt;(reloc), mod.static_offset, tls_tp_base,
                         static_cast<size_t>(sym_addr), static_cast<size_t>(addend), sym_name);
            } else {
              tlsdesc_args_.push_back({
                .generation = mod.first_generation,
                .index.module_id = module_id,
                .index.offset = sym_addr + addend,
              });
              // Defer the TLSDESC relocation until the address of the TlsDynamicResolverArg object
              // is finalized.
              deferred_tlsdesc_relocs.push_back({ desc, tlsdesc_args_.size() - 1 });
              const TlsDynamicResolverArg& desc_arg = tlsdesc_args_.back();
              TRACE_TYPE(RELO, "RELO TLSDESC %16p <- dynamic (gen %zu, mod %zu, off %zu) %s",
                         reinterpret_cast&lt;void*&gt;(reloc), desc_arg.generation,
                         desc_arg.index.module_id, desc_arg.index.offset, sym_name);
            }
          }
        }
        break;
#endif  // defined(__aarch64__)

#if defined(__aarch64__)
      case R_AARCH64_ABS64:
        count_relocation(kRelocAbsolute);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO ABS64 %16llx <- %16llx %s\n",
                   reloc, sym_addr + addend, sym_name);
        *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = sym_addr + addend;
        break;
      case R_AARCH64_ABS32:
        count_relocation(kRelocAbsolute);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO ABS32 %16llx <- %16llx %s\n",
                   reloc, sym_addr + addend, sym_name);
        {
          const ElfW(Addr) min_value = static_cast&lt;ElfW(Addr)&gt;(INT32_MIN);
          const ElfW(Addr) max_value = static_cast&lt;ElfW(Addr)&gt;(UINT32_MAX);
          if ((min_value <= (sym_addr + addend)) &&
              ((sym_addr + addend) <= max_value)) {
            *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = sym_addr + addend;
          } else {
            DL_ERR("0x%016llx out of range 0x%016llx to 0x%016llx",
                   sym_addr + addend, min_value, max_value);
            return false;
          }
        }
        break;
      case R_AARCH64_ABS16:
        count_relocation(kRelocAbsolute);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO ABS16 %16llx <- %16llx %s\n",
                   reloc, sym_addr + addend, sym_name);
        {
          const ElfW(Addr) min_value = static_cast&lt;ElfW(Addr)&gt;(INT16_MIN);
          const ElfW(Addr) max_value = static_cast&lt;ElfW(Addr)&gt;(UINT16_MAX);
          if ((min_value <= (sym_addr + addend)) &&
              ((sym_addr + addend) <= max_value)) {
            *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = (sym_addr + addend);
          } else {
            DL_ERR("0x%016llx out of range 0x%016llx to 0x%016llx",
                   sym_addr + addend, min_value, max_value);
            return false;
          }
        }
        break;
      case R_AARCH64_PREL64:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO REL64 %16llx <- %16llx - %16llx %s\n",
                   reloc, sym_addr + addend, rel->r_offset, sym_name);
        *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = sym_addr + addend - rel->r_offset;
        break;
      case R_AARCH64_PREL32:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO REL32 %16llx <- %16llx - %16llx %s\n",
                   reloc, sym_addr + addend, rel->r_offset, sym_name);
        {
          const ElfW(Addr) min_value = static_cast&lt;ElfW(Addr)&gt;(INT32_MIN);
          const ElfW(Addr) max_value = static_cast&lt;ElfW(Addr)&gt;(UINT32_MAX);
          if ((min_value <= (sym_addr + addend - rel->r_offset)) &&
              ((sym_addr + addend - rel->r_offset) <= max_value)) {
            *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = sym_addr + addend - rel->r_offset;
          } else {
            DL_ERR("0x%016llx out of range 0x%016llx to 0x%016llx",
                   sym_addr + addend - rel->r_offset, min_value, max_value);
            return false;
          }
        }
        break;
      case R_AARCH64_PREL16:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO REL16 %16llx <- %16llx - %16llx %s\n",
                   reloc, sym_addr + addend, rel->r_offset, sym_name);
        {
          const ElfW(Addr) min_value = static_cast&lt;ElfW(Addr)&gt;(INT16_MIN);
          const ElfW(Addr) max_value = static_cast&lt;ElfW(Addr)&gt;(UINT16_MAX);
          if ((min_value <= (sym_addr + addend - rel->r_offset)) &&
              ((sym_addr + addend - rel->r_offset) <= max_value)) {
            *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) = sym_addr + addend - rel->r_offset;
          } else {
            DL_ERR("0x%016llx out of range 0x%016llx to 0x%016llx",
                   sym_addr + addend - rel->r_offset, min_value, max_value);
            return false;
          }
        }
        break;

      case R_AARCH64_COPY:
        /*
         * ET_EXEC is not supported so this should not happen.
         *
         * http://infocenter.arm.com/help/topic/com.arm.doc.ihi0056b/IHI0056B_aaelf64.pdf
         *
         * Section 4.6.11 "Dynamic relocations"
         * R_AARCH64_COPY may only appear in executable objects where e_type is
         * set to ET_EXEC.
         */
        DL_ERR("%s R_AARCH64_COPY relocations are not supported", get_realpath());
        return false;
#elif defined(__x86_64__)
      case R_X86_64_32:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO R_X86_64_32 %08zx <- +%08zx %s", static_cast<size_t>(reloc),
                   static_cast<size_t>(sym_addr), sym_name);
        *reinterpret_cast<Elf32_Addr*>(reloc) = sym_addr + addend;
        break;
      case R_X86_64_64:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO R_X86_64_64 %08zx <- +%08zx %s", static_cast<size_t>(reloc),
                   static_cast<size_t>(sym_addr), sym_name);
        *reinterpret_cast<Elf64_Addr*>(reloc) = sym_addr + addend;
        break;
      case R_X86_64_PC32:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO R_X86_64_PC32 %08zx <- +%08zx (%08zx - %08zx) %s",
                   static_cast<size_t>(reloc), static_cast<size_t>(sym_addr - reloc),
                   static_cast<size_t>(sym_addr), static_cast<size_t>(reloc), sym_name);
        *reinterpret_cast<Elf32_Addr*>(reloc) = sym_addr + addend - reloc;
        break;
#elif defined(__arm__)
      case R_ARM_ABS32:
        count_relocation(kRelocAbsolute);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO ABS %08x <- %08x %s", reloc, sym_addr, sym_name);
        *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) += sym_addr;
        break;
      case R_ARM_REL32:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO REL32 %08x <- %08x - %08x %s",
                   reloc, sym_addr, rel->r_offset, sym_name);
        *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) += sym_addr - rel->r_offset;
        break;
      case R_ARM_COPY:
        /*
         * ET_EXEC is not supported so this should not happen.
         *
         * http://infocenter.arm.com/help/topic/com.arm.doc.ihi0044d/IHI0044D_aaelf.pdf
         *
         * Section 4.6.1.10 "Dynamic relocations"
         * R_ARM_COPY may only appear in executable objects where e_type is
         * set to ET_EXEC.
         */
        DL_ERR("%s R_ARM_COPY relocations are not supported", get_realpath());
        return false;
#elif defined(__i386__)
      case R_386_32:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO R_386_32 %08x <- +%08x %s", reloc, sym_addr, sym_name);
        *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) += sym_addr;
        break;
      case R_386_PC32:
        count_relocation(kRelocRelative);
        MARK(rel->r_offset);
        TRACE_TYPE(RELO, "RELO R_386_PC32 %08x <- +%08x (%08x - %08x) %s",
                   reloc, (sym_addr - reloc), sym_addr, reloc, sym_name);
        *reinterpret_cast&lt;ElfW(Addr)*&gt;(reloc) += (sym_addr - reloc);
        break;
#endif
      default:
        DL_ERR("unknown reloc type %d @ %p (%zu)", type, rel, idx);
        return false;
    }
  }

#if defined(__aarch64__)
  // Bionic currently only implements TLSDESC for arm64.
  for (const std::pair&lt;TlsDescriptor*, size_t&gt;& pair : deferred_tlsdesc_relocs) {
    TlsDescriptor* desc = pair.first;
    desc->func = tlsdesc_resolver_dynamic;
    desc->arg = reinterpret_cast<size_t>(&tlsdesc_args_[pair.second]);
  }
#endif

  return true;
}
```

#### soinfo_do_lookup

64位的符号查找函数。与32位逻辑类似, 查找顺序: 自身(DT_SYMBOLIC) → global_group → local_group。主要区别: 支持GNU Hash + SysV Hash双模式查找, 支持版本符号(version_info)匹配

```cpp
bool soinfo_do_lookup(soinfo* si_from, const char* name, const version_info* vi,
                      soinfo** si_found_in, const soinfo_list_t& global_group,
                      const soinfo_list_t& local_group, const ElfW(Sym)** symbol) {
  SymbolName symbol_name(name);
  const ElfW(Sym)* s = nullptr;

  /* "This element's presence in a shared object library alters the dynamic linker's
   * symbol resolution algorithm for references within the library. Instead of starting
   * a symbol search with the executable file, the dynamic linker starts from the shared
   * object itself. If the shared object fails to supply the referenced symbol, the
   * dynamic linker then searches the executable file and other shared objects as usual."
   *
   * http://www.sco.com/developers/gabi/2012-12-31/ch5.dynamic.html
   *
   * Note that this is unlikely since static linker avoids generating
   * relocations for -Bsymbolic linked dynamic executables.
   */
  if (si_from->has_DT_SYMBOLIC) {
    DEBUG("%s: looking up %s in local scope (DT_SYMBOLIC)", si_from->get_realpath(), name);
    if (!si_from->find_symbol_by_name(symbol_name, vi, &s)) {
      return false;
    }

    if (s != nullptr) {
      *si_found_in = si_from;
    }
  }

  // 1. Look for it in global_group
  if (s == nullptr) {
    bool error = false;
    global_group.visit([&](soinfo* global_si) {
      DEBUG("%s: looking up %s in %s (from global group)",
          si_from->get_realpath(), name, global_si->get_realpath());
      if (!global_si->find_symbol_by_name(symbol_name, vi, &s)) {
        error = true;
        return false;
      }

      if (s != nullptr) {
        *si_found_in = global_si;
        return false;
      }

      return true;
    });

    if (error) {
      return false;
    }
  }

  // 2. Look for it in the local group
  if (s == nullptr) {
    bool error = false;
    local_group.visit([&](soinfo* local_si) {
      if (local_si == si_from && si_from->has_DT_SYMBOLIC) {
        // we already did this - skip
        return true;
      }

      DEBUG("%s: looking up %s in %s (from local group)",
          si_from->get_realpath(), name, local_si->get_realpath());
      if (!local_si->find_symbol_by_name(symbol_name, vi, &s)) {
        error = true;
        return false;
      }

      if (s != nullptr) {
        *si_found_in = local_si;
        return false;
      }

      return true;
    });

    if (error) {
      return false;
    }
  }

  if (s != nullptr) {
    TRACE_TYPE(LOOKUP, "si %s sym %s s->st_value = %p, "
               "found in %s, base = %p, load bias = %p",
               si_from->get_realpath(), name, reinterpret_cast&lt;void*&gt;(s->st_value),
               (*si_found_in)->get_realpath(), reinterpret_cast&lt;void*&gt;((*si_found_in)->base),
               reinterpret_cast&lt;void*&gt;((*si_found_in)->load_bias));
  }

  *symbol = s;
  return true;
}
```

### step7: Mark all load_tasks

最后一步: 将所有已完成链接的soinfo标记为`linked`, 并为跨load_group的依赖引用增加引用计数, 防止过早卸载

```cpp
  // Step 7: Mark all load_tasks as linked and increment refcounts
  // for references between load_groups (at this point it does not matter if
  // referenced load_groups were loaded by previous dlopen or as part of this
  // one on step 6)
  if (start_with != nullptr && add_as_children) {
    start_with->set_linked();
  }

  for (auto&& task : load_tasks) {
    soinfo* si = task->get_soinfo();
    // 设置已链接标志
    si->set_linked();
  }

  for (auto&& task : load_tasks) {
    soinfo* si = task->get_soinfo();
    soinfo* needed_by = task->get_needed_by();
    if (needed_by != nullptr &&
        needed_by != start_with &&
        needed_by->get_local_group_root() != si->get_local_group_root()) {
      // 增加依赖库的引用计数
      si->increment_ref_count();
    }
  }
  return true;
```

# 0x9 结语

自定义Linker作为Android Native层加固常用的保护方案之一, 其原理并不复杂, 结合Java层的Dex代码抽取加固能更加有效保护App

新坑flag: 结合之前实现的抽取加固 [[原创]Android从整体加固到抽取加固的实现及原理](https://bbs.kanxue.com/thread-286929.htm) , 添加自定义linker功能, 实现Java+Native双层加固

本文不足之处:

1. Loader/Linker功能有限

没有实现完备的SO加载和符号解析等功能, 有待完善
2. 自定义Linker只能处理动态注册的JNI函数

因为可以在Custom Linker的JNI_OnLoad中获取JavaVM指针并传递给目标SO, 所以使用动态注册的JNI函数比较好处理, 当Java层调用Native方法时, ART会自动在VM中查找注册的JNI函数.

而静态注册的JNI函数查找方法依赖函数的符号名称, 查找逻辑不同, 暂时没有处理对应情况.
3. 部分细节没有深入探讨, 有待读者自行学习 (例如Hash Table查找算法)

# 0xA References

参考的Linker基础部分:

[Android Linker详解](https://bbs.kanxue.com/thread-269801.htm)

[[原创]Android Linker详解(二)](https://bbs.kanxue.com/thread-269891.htm)

[安卓so加载流程源码分析](https://oacia.dev/android-load-so/)

[[原创]从Java到Native，so中的函数是如何一步步被加载的？](https://bbs.kanxue.com/thread-285950.htm)

参考的自定义Linker部分:

[《基于linker实现so加壳技术基础》上篇](https://bbs.kanxue.com/thread-269484.htm)

[《基于linker实现so加壳技术基础》下篇](https://bbs.kanxue.com/thread-269485.htm)

[基于linker实现so加壳补充-------从dex中加载so](https://bbs.kanxue.com/thread-269757.htm)

拓展推荐部分:

ngiokweng 师傅的[[原创]自實現Linker加載so](https://bbs.kanxue.com/thread-282316.htm)

Yangser 师傅的 [[原创] 自定义Linker与SO加固技术](https://bbs.kanxue.com/thread-287254.htm)  项目地址 [soLoader](https://github.com/SoyBeanMilkx/soLoader)

[fake-linker](https://github.com/sanfengAndroid/fake-linker) hook 工具

上传的附件：
- CustomLinker-attachments.zip

（1.57MB，149次下载）

---

# 回复

## 回复 by x1a0f3n9 (#2)

*2026-4-4 02:35*

严肃学习

## 回复 by 东方玻璃 (#3)

*2026-4-4 02:37*

>
> [x1a0f3n9](https://bbs.kanxue.com/user-1036990.htm)
>  严肃学习
>

风佬带带![image](https://bbs.kanxue.com/view/img/face/056.gif)

## 回复 by Cure. (#4)

*2026-4-4 09:29*

666

## 回复 by huangjw (#5)

*2026-4-4 09:37*

可真有你的， 正好复习下

## 回复 by GhHei (#6)

*2026-4-4 09:46*

同感，AI是提高了效率，但也觉得自己浮躁很多，感谢示范～

## 回复 by iBa0 (#7)

*2026-4-4 10:12*

123

## 回复 by lackone (#8)

*2026-4-4 10:45*

6666

## 回复 by 29o (#9)

*2026-4-4 11:09*

666

## 回复 by 墨穹呢 (#10)

*2026-4-4 12:05*

火钳刘明

## 回复 by Imxz (#11)

*2026-4-4 12:12*

rbq

## 回复 by 下雨天sana (#12)

*2026-4-4 13:42*

严肃学习

## 回复 by mb_ldbucrik (#13)

*2026-4-4 15:03*

感谢分享

## 回复 by 心有万象 (#14)

*2026-4-4 15:06*

逐字分析

## 回复 by reserve_zhou (#15)

*2026-4-4 15:19*

学习

## 回复 by 晴空万里丶 (#16)

*2026-4-4 18:53*

666，学习下

## 回复 by it爱好者_625041 (#17)

*2026-4-4 19:23*

666

## 回复 by fengvmu (#18)

*2026-4-4 19:47*

6

## 回复 by kingking888 (#19)

*2026-4-4 22:13*

666

## 回复 by tonykros (#20)

*2026-4-4 23:23*

666

## 回复 by 土豆爱学习 (#21)

*2026-4-5 10:56*

666认真学习，大佬辛苦了

## 回复 by 苦瓜tim (#22)

*2026-4-5 11:07*

666感谢大佬分享

## 回复 by mb_qimctavn (#23)

*2026-4-5 11:24*

6

## 回复 by veluboii (#24)

*2026-4-6 11:21*

666

## 回复 by 呆萌的小白 (#25)

*2026-4-6 11:34*

技术又更新了么,又白学了么

## 回复 by MaYil (#26)

*2026-4-6 12:43*

感谢分享

## 回复 by mb_euhyowpw (#27)

*2026-4-6 16:32*

666

## 回复 by jyotidwi (#28)

*2026-4-6 16:40*

⁶66

## 回复 by Zepp7289 (#29)

*2026-4-6 17:33*

tql

## 回复 by HSQ (#30)

*2026-4-6 18:22*

感谢分享

## 回复 by 小迷糊ddd (#31)

*2026-4-6 22:48*

感谢分享，受教了。

## 回复 by 卡坦精 (#32)

*2026-4-7 09:46*

666

## 回复 by XCicada (#33)

*2026-4-7 10:12*

学习

## 回复 by mb_pesxllvn (#34)

*2026-4-7 10:31*

666

## 回复 by Snark (#35)

*2026-4-7 11:10*

11

## 回复 by mb_rrvlrvbk (#36)

*2026-4-7 11:21*

大佬牛哇

## 回复 by mb_vkqcleyo (#37)

*2026-4-7 13:58*

6666

## 回复 by 独一无二_370133 (#38)

*2026-4-7 14:14*

666

## 回复 by GEKEZYX (#39)

*2026-4-7 17:42*

666

## 回复 by SomeMx (#40)

*2026-4-7 18:50*

学习一下

## 回复 by ZACSN12 (#41)

*2026-4-7 21:46*

学习

## 回复 by wx_宇克鴻 (#42)

*2026-4-8 11:35*

666

## 回复 by 星雨心愿 (#43)

*2026-4-8 15:55*

666

## 回复 by mb_vxjviech (#44)

*2026-4-8 16:33*

666

## 回复 by 需要渗透高手 (#45)

*2026-4-8 17:15*

太强了

## 回复 by xianyuuuan (#46)

*2026-4-8 17:35*

强强，最近也在学习和总结相关内容的文章，大佬总结的更为详细哇![image](https://bbs.kanxue.com/view/img/face/086.gif)

## 回复 by 东方玻璃 (#47)

*2026-4-8 17:38*

>
> [xianyuuuan](https://bbs.kanxue.com/user-1002959.htm)
>  强强，最近也在学习和总结相关内容的文章，大佬总结的更为详细哇[em_086]
>

期待师傅的文章, 我只是站在其他大佬的jb上![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by koflfy (#48)

*2026-4-8 19:18*

mark

## 回复 by Thehepta (#49)

*2026-4-9 16:40*

1

## 回复 by mb_uvyukvot (#50)

*2026-4-9 16:54*

666

## 回复 by 毛毛毛毛虫 (#51)

*2026-4-9 19:54*

学习看看

## 回复 by Mr.He (#52)

*2026-4-9 19:57*

666

## 回复 by guijingwen (#53)

*2026-4-9 20:09*

66

## 回复 by APlus (#54)

*2026-4-10 14:17*

6

## 回复 by 需要渗透高手 (#55)

*2026-4-10 23:16*

努力学习中

## 回复 by mb_mlyojneh (#56)

*2026-4-11 19:12*

学习

## 回复 by 还没想好名字 (#57)

*2026-4-13 17:22*

看一看

## 回复 by mb_mihutdve (#58)

*2026-4-14 14:06*

666

## 回复 by uni7corn (#59)

*2026-4-14 14:34*

感谢分享，学习了

## 回复 by 菜鸟9527 (#60)

*2026-4-15 13:14*

太强了佬，学习学习

## 回复 by mb_uzmffdbw (#61)

*2026-4-16 15:34*

666

## 回复 by AK1988DA (#62)

*2026-4-16 20:51*

3

## 回复 by 冷瞳 (#63)

*2026-4-18 18:52*

666

## 回复 by mb_dcjxxhsk (#64)

*2026-4-21 10:36*

666

## 回复 by mb_yjiuccxa (#65)

*2026-4-21 15:00*

学习

## 回复 by git_49999huanptd2011 (#66)

*2026-4-21 16:07*

666

## 回复 by mb_pjqwrjje (#67)

*2026-4-22 10:43*

666

## 回复 by ldehua (#68)

*2026-4-22 15:14*

666

## 回复 by mb_zcfhleoj (#69)

*2026-4-22 16:31*

感谢分享

## 回复 by wx_coddvccwyh (#70)

*2026-4-23 22:15*

666

## 回复 by fyrlove (#71)

*2026-4-23 22:46*

内容写的真不错，消化需要时间，跟着您学习了。

## 回复 by 东方玻璃 (#72)

*2026-4-23 23:33*

>
> [fyrlove](https://bbs.kanxue.com/user-703941.htm)
>  内容写的真不错，消化需要时间，跟着您学习了。
>

大佬过誉了,共同进步互相学习![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by mb_ileraodd (#73)

*2026-4-25 17:00*

66666

## 回复 by Iceshara (#74)

*2026-4-28 18:53*

666

## 回复 by Iceshara (#75)

*2026-4-28 18:54*

666

## 回复 by Iceshara (#76)

*2026-4-28 18:54*

666 厉害

## 回复 by Iceshara (#77)

*2026-4-28 18:54*

666 厉害

## 回复 by qqqiu (#78)

*2026-5-3 09:15*

66

## 回复 by mb_dmryhnwz (#79)

*2026-5-3 09:46*

666

## 回复 by dsr000 (#80)

*2026-5-3 11:16*

666

## 回复 by niama (#81)

*2026-5-4 07:45*

666

## 回复 by mb_xbgppumd (#82)

*2026-5-5 01:30*

666

## 回复 by mb_ayrcgfjj (#83)

*2026-5-9 06:54*

66666666666666

## 回复 by 五彩斑斓的黑 (#84)

*2026-5-9 08:34*

666

## 回复 by 黑洞23 (#85)

*2026-5-9 11:45*

可以，学爽了

## 回复 by zzhone (#86)

*2026-5-10 19:04*

好看

## 回复 by mb_wiezfmox (#87)

*2026-5-12 03:26*

666

## 回复 by mb_fdskejlh (#88)

*2026-5-16 20:57*

牛啊

## 回复 by mb_vdqbqpou (#89)

*2026-5-17 04:00*

好的

## 回复 by genliese (#90)

*2026-5-22 10:11*

支持一下

## 回复 by 简单的简单 (#91)

*2026-5-29 13:37*

666

## 回复 by Tanuyoki0 (#92)

*2026-6-3 21:43*

学习学习

## 回复 by 叶晓枫A (#93)

*2026-6-4 10:54*

技术又更新了么,又白学了么

## 回复 by gfxvggbwic (#94)

*2026-6-5 09:05*

666

## 回复 by nuomida (#95)

*2026-6-5 13:30*

学习一下

## 回复 by 章康 (#96)

*2026-6-8 11:56*

666

## 回复 by huangbof (#97)

*2026-6-8 18:06*

superproject

## 回复 by mb_sqetvntx (#98)

*2026-6-11 20:53*

学习

## 回复 by dob_C (#99)

*2026-6-24 16:46*

感谢分享

## 回复 by mb_dlljjfcf (#100)

*2026-6-28 22:16*

6666

## 回复 by Bonquer (#101)

*2026-6-28 22:36*

啊

## 回复 by mb_qqihqaoo (#102)

*2026-7-5 15:04*

6666666666

## 回复 by 破执. (#103)

*2026-7-9 02:04*

看看

## 回复 by mb_fafswnif (#104)

*2026-7-15 19:45*

666

## 回复 by RikkaRin (#105)

*2026-7-16 20:16*

6666

## 回复 by mb_degalzhb (#106)

*2026-7-20 10:55*

感谢分享《[原创]Android从ELF-Loader到自定义Linker的实现及原理》。文中的分析过程和关键思路很有参考价值，我会结合实际环境进一步验证和学习。

## 回复 by AYHMO (#107)

*2026-7-22 15:26*

66666

## 回复 by mb_isbmbfet (#108)

*2026-7-22 15:54*

666

## 回复 by GeQ1an (#109)

6666666

## 回复 by mxystery (#110)

6666

## 回复 by TnT柠檬茶 (#111)

666
