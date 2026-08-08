---
title: '[原创]UPX arm64-linux 源码分析 修复Unidbg以支持模拟未脱壳的UPX安卓so'
url: https://bbs.kanxue.com/thread-290169.htm
tid: 290169
author: _0xA1pha
date: '2026-03-04'
tags: [Android安全, 原创, 系统相关, 基础理论]
crawled_at: '2026-08-08T10:20:58+00:00'
replies: 28
---

## 概述

通过阅读UPX源码、Unidbg源码，找到了直接模拟未脱壳的UPX安卓so崩溃原因。目前此贡献已被合并至[上游](https://github.com/zhkl0228/unidbg/commit/44fd8c22685e2aeec5b1a41381abd8e36cd5ba33)。

## UPX源码阅读

git版本提交SHA：`611d67542ae0ae9f8128ff121ae2a21ea007261d`

### 压缩阶段

 ![压缩流程](https://bbs.kanxue.com/upload/attach/202603/1059242_U9K7KUT4MEUJC7J.webp)

1. **格式识别与分发** ([src/packmast.cpp](https://github.com/upx/upx/blob/devel/src/packmast.cpp))

	- [PackMaster](https://github.com/upx/upx/blob/devel/src/packmast.cpp#64-76) 类通过 [visitAllPackers](https://github.com/upx/upx/blob/devel/src/packmast.cpp#136-154) 遍历所有支持的格式。

 ![image](https://bbs.kanxue.com/upload/attach/202603/1059242_494NDYASSHZY4U6.webp)

- 每个格式（如 [PackLinuxElf64amd](https://github.com/upx/upx/blob/devel/src/p_lx_elf.h#518-534) 或 **[PackLinuxElf64arm](https://github.com/upx/upx/blob/devel/src/p_lx_elf.h#539-540)**）通过 [canPack()](https://github.com/upx/upx/blob/devel/src/p_unix.cpp#73-95) 检查输入文件是否可以被压缩。
- 对于 ARM64，它会识别 `EM_AARCH64` 机器码。

1. **准备工作** ([src/p_lx_elf.cpp](https://github.com/upx/upx/blob/devel/src/p_lx_elf.cpp), [src/packer.cpp](https://github.com/upx/upx/blob/devel/src/packer.cpp))

	- 对于 ARM64，会使用 `ElfLinkerArm64LE`。
	- [pack1()](https://github.com/upx/upx/blob/devel/src/p_lx_elf.cpp#4627-4634)：生成新的可执行文件头。对于安卓so，会特别处理 `android_shlib` ，处理符号表和重定位。
2. **数据压缩** ([src/p_unix.cpp](https://github.com/upx/upx/blob/devel/src/p_unix.cpp) 中的 [pack2](https://github.com/upx/upx/blob/devel/src/p_lx_elf.cpp#5682-5802))

	- UPX 将原文件内容按块（Block）读取。
	- 调用 [compressWithFilters()](https://github.com/upx/upx/blob/devel/src/packer.cpp#1010-1214) 进行压缩。现在版本一般是NRV算法，也见过LZMA的。
3. **注入解压 Stub** ([src/p_lx_elf.cpp](https://github.com/upx/upx/blob/devel/src/p_lx_elf.cpp) 中的 [pack3](https://github.com/upx/upx/blob/devel/src/p_lx_elf.cpp#578-781))

	- 从 `src/stub` 提取 ARM64 专用的汇编代码（如 `arm64-linux.elf-entry.S`）和 C 逻辑。
	- 所谓的`stub`是UPX的一段可执行代码，stub本身也是运行时自解压的，是运行时自脱壳的核心。
4. **收尾工作** (`src/p_unix.cpp` 中的 `pack4`)

	- 写入 `PackHeader` 信息到文件末尾。
	- 记录 `overlay_offset`，这是加壳后原始压缩数据在文件中的偏移量，供解压 stub 使用。这些地方很容易被魔改，随便改一点基本上就不能`upx -d`脱壳了。## 运行阶段

 ![解压流程](https://bbs.kanxue.com/upload/attach/202603/1059242_YWGCWCGYC6XB487.webp)

1. **入口启动 (Entry)**

	- 运行从 `_start` 开始，首先一次性压所有栈，保护现场。
	- 通过 `memfd_create` 系统调用或降级在 `/dev/shm` 下创建临时文件，用于存放即将解压的第二阶段 Stub 逻辑。
2. **Stub 自解压**

	- 初始 Stub 将其自身“折叠（Folded）”部分的 C 逻辑代码解压到上述临时文件中。
	- 通过 `mmap` 将该临时文件映射为可执行内存，并跳转过去。
3. **分析与内存规划** (`do_xmap` 函数)

	- 读取压缩时的元数据，使用 `xfind_pages` 预定原始程序的总内存范围。
	- 获取 `AT_PAGESZ` 以确保内存页对齐一致。
4. **循环解压块** (`unpackExtent` 函数)

	- 循环解压数据块到原始内存位置。
	- 对 ARM64 指令进行 "unfilter" 处理（还原跳转偏移）。
5. **权限恢复与清理**

	- 调用 `mprotect` 恢复内存段权限。
	- 使用 ARM64 专用的 `make_hatch_arm64` 创建一段“逃生舱”代码，负责执行 `munmap` 后跳转回原始 OEP。**这就是Unidbg无法直接带壳模拟的原因。**

	>
	> 为什么要用“逃生舱”，因为 `munmap` 不能操作自己所在的内存，所以需要申请一块新的，在新内存上操作。
	>
	>
	>
6. **恢复现场**

	- 恢复所有寄存器状态并跳转。这是传统的手动脱壳方法的常用点。依稀记得用od调win就是在popad上打个断点然后单步几下找大跳。

>
> 所有的系统调用均通过`SVC 0`执行，这块东西是直接汇编手搓的
>
>
>

## 分析解决Unidbg报错

根据运行时报错可以定位到如下位置，修改如下。

| 123456789101112131415161718 | `ddiff --git a/unidbg-api/src/main/java/com/github/unidbg/spi/AbstractLoader.java b/unidbg-api/src/main/java/com/github/unidbg/spi/AbstractLoader.java``index 756bca92e..a61afef46 100644``--- a/unidbg-api/src/main/java/com/github/unidbg/spi/AbstractLoader.java``+++ b/unidbg-api/src/main/java/com/github/unidbg/spi/AbstractLoader.java``@@ -195,8 +195,13 @@ public final int munmap(long start, int length) {``long size = aligned - removed.size;``while (size != 0) {``MemoryMap remove = memoryMap.remove(address);``+                    if (remove == null) {``+                        log.warn("munmap failed to find adjacent region at address=0x{}", Long.toHexString(address));``+                        break;``+                    }``if (removed.prot != remove.prot) {``-                        throw new IllegalStateException();``+                        log.warn("munmap prot mismatch: removed.prot={}, remove.prot={}, address=0x{}", removed.prot, remove.prot, Long.toHexString(address));``}``address += remove.size;``size -= remove.size;` |
|-|-|

根据UPX源码得知：运行时mmap会**一次申请所有段的内存**（防止临近的段被分到别的程序去了），此时这些段的权限必然是各不相同的（参考正常的程序）。因此，在munmap时，就会产生跨不同权限段操作的情况，原来代码中`removed.prot != remove.prot`**必然成立**。这样就会`throw`错误中断。我们仅需把`throw`改为无害的`log warn`即可完美解决此问题。

>
>  经过测试，原先不能直接模拟的lib，经过这样修改代码可以直接模拟。这完美避免了分析魔改UPX和修复头等工作。
>
>
>

---

# 回复

## 回复 by Imxz (#2)

*2026-3-4 17:39*

tql

## 回复 by Thehepta (#3)

*2026-3-4 17:40*

1

## 回复 by mb_asiwnxyv (#4)

*2026-3-4 19:27*

感谢分享

## 回复 by myios (#5)

*2026-3-4 19:47*

666

## 回复 by mb_ldbucrik (#6)

*2026-3-4 21:04*

向大佬学习

## 回复 by 铭天星 (#7)

*2026-3-4 22:39*

666

## 回复 by mb_dmryhnwz (#8)

*2026-3-4 23:58*

4

## 回复 by SomeMx (#9)

*2026-3-5 01:54*

过来瞧瞧

## 回复 by wx_插曲 (#10)

*2026-3-5 08:45*

66

## 回复 by mb_ysegxpmv (#11)

*2026-3-5 09:36*

学习一下upx的原理

## 回复 by win柠初 (#12)

*2026-3-6 11:29*

学习一下upx的原理

## 回复 by 阿C想回老家 (#13)

*2026-3-7 14:40*

点赞

## 回复 by SInnon (#14)

*2026-3-7 14:45*

66666666666666

## 回复 by mb_tcheuwvg (#15)

*2026-3-9 16:44*

66666666

## 回复 by mb_ykavguun (#16)

*2026-3-9 17:40*

11

## 回复 by xeiyu (#17)

*2026-3-12 02:15*

666

## 回复 by mb_rqlksylg (#18)

*2026-3-12 03:27*

good

## 回复 by cobe (#19)

*2026-3-12 10:40*

666

## 回复 by GEKEZYX (#20)

*2026-3-13 09:55*

666

## 回复 by 年lm (#21)

*2026-3-13 23:14*

666

## 回复 by asuralove (#22)

*2026-3-21 16:45*

666

## 回复 by iBa0 (#23)

*2026-3-22 20:39*

123

## 回复 by k4y0z (#24)

*2026-3-23 10:16*

666

## 回复 by 小迷糊ddd (#25)

*2026-4-5 21:17*

感谢分享，记录学习。

## 回复 by uni7corn (#26)

*2026-4-27 12:22*

感谢分享，学习了

## 回复 by wx_小白_266 (#27)

*2026-5-8 21:40*

tql

## 回复 by mb_oxqwhbqt (#28)

*2026-7-17 16:00*

这项技术贡献非常出色，通过深入分析UPX和Unidbg源码，成功解决了未脱壳的UPX安卓SO崩溃问题，并将代码合并到上游，展现了强大的技术实力。这种代码级别的优化和问题定位能力，无疑为后续的开发和维

## 回复 by mb_xultgqpf (#29)

这位开发者真是厉害！通过深入分析UPX和Unidbg的源码，找到了模拟未脱壳安卓SO崩溃的根本原因，并成功将问题解决。这种对技术细节的深入理解和代码的巧妙修改，不仅展示了扎实的技术功底。
