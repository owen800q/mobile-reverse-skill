---
title: '[原创]入门OLLVM(上): 从LLVM到OLLVM-编译,使用,移植和源码分析'
url: https://bbs.kanxue.com/thread-288976.htm
tid: 288976
author: 东方玻璃
date: '2025-11-03'
tags: [Android安全, 原创, 基础理论, 逆向分析, 混淆加固, 源码框架, 其他]
crawled_at: '2026-07-31T14:02:15+08:00'
replies: 22
---

目录- 前言
- 编译LLVM
- Windows 编译 LLVM
- Mac 编译 LLVM
- Linux 编译 LLVM
- Clang 编译 C代码
- CLion 调试 Clang
- llvm-gtest报错
- 安装zlib库
- 安装zstd库
- debug配置
- z.dll缺失
- LLVM Pass
- LLVM基础
- LLVM IR
- IR的概念
- IR示例
- 使用LLVM Tools
- LLVM opt
- CLion调试opt
- LLVM Pass
- Pass的实现
- 实现Module Pass
- 实现Function / Basic Block Pass
- 编译Pass
- 测试Pass
- 脱离LLVM源码编译Pass
- project/CMakeLists.txt
- project/MyFunctionPass
- project/MyModulePass
- debug配置
- 问题: optnone导致function pass不执行
- CLion调试自定义Pass
- 实现函数名加密Pass
- Clang使用自定义Pass
- 移植和使用 OLLVM
- 移植OLLVM到LLVM19
- 获取Obfuscation
- 移植Obfuscation
- 编译OLLVM
- 测试OLLVM
- Instructions Substitution
- Bogus Control Flow
- Control Flow Flattening
- 集成 OLLVM 到 NDK
- 创建Native测试工程
- 添加混淆配置
- Obfuscation Pass
- 调试Pass
- 打印函数
- 通过opt调试pass
- Instructions Substitution
- Instructions Substitution 关键流程
- SubstitutionPass::run
- SubstitutionPass::substitute
- SubstitutionPass
- SubstitutionPass::addNeg
- Substitution 效果分析
- 测试代码
- main IR
- SplitBasicBlocks
- Split BasicBlocks 关键流程
- SplitBasicBlockPass::run
- SplitBasicBlockPass::split
- SplitBasicBlockPass::shuffle
- BasicBlock::splitBasicBlock
- PHI Node
- BasicBlock::replaceSuccessorsPhiUsesWith
- BasicBlock::replacePhiUsesWith
- Instructions::replaceIncomingBlockWith
- SplitBasicBlocks 效果分析
- 测试代码
- main IR
- Control Flow Flattening
- Control Flow Flattening 关键流程
- Flattening::flatten
- FlatteningPass::run
- FlatteningPass::flatten
- Utils::fixStack
- Control Flow Flattening 效果分析
- 测试代码
- IDA分析
- main IR
- Bogus Control Flow
- Bogus Control Flow 关键流程
- BogusControlFlowPass::run
- BogusControlFlowPass::bogus
- BogusControlFlowPass::addBogusFlow
- BogusControlFlowPass::createAlteredBasicBlock
- BogusControlFlowPass::doF
- Bogus Control Flow 效果分析
- 测试代码
- IDA分析
- main IR
- Indirect Branch
- Indirect Branch 关键流程
- IndirectBranchPass::run
- IndirectBranchPass::NumberBasicBlock
- IndirectBranchPass::getIndirectTargets
- llvm::SplitAllCriticalEdges
- Indirect Branch 效果分析
- 测试代码
- IDA分析
- main IR
- entry IR
- if.else IR
- Indirect Call
- Indirect Call 关键流程
- IndirectCallPass::doIndirctCall
- IndirectCallPass::NumberCallees
- IndirectCallPass::getIndirectCallees
- Indirect Call 效果分析
- 测试代码
- IDA分析
- main IR
- 结语
- References
# 前言

首次遇到OLLVM时是校队转正比赛的压轴题, 当初不懂这是什么骚操作, 侥幸因为题目使用RC4加密, 通过侧信道方式爆破出了flag

后来了解到D810等去混淆脚本, 针对OLLVM中较为基础的指令替换, 虚假控制流和平坦化没有问题, 久而久之顶着混淆硬看也不是不行

再后来遇到了BR混淆即间接跳转(Indirect Branch)混淆, 学了一阵子大佬思路和脚本云里雾里, 始终不明白其原理, 到底有哪些特例

直到决心沉住气阅读源码, 调试几遍, 似乎也没有当初想的那么难

闲话少说, 希望本文能抛砖引玉, 对入门OLLVM的师傅有所帮助

本文按顺序阅读即可, 实践体会从LLVM到OLLVM的流程并解决问题非常重要, 一定要多动手和调试

环境:

- Windows 10
- IDA Pro 9.2
- CMake
- Ninja
- CLion
- Visual Studio 2022 / MSVC
- Android Studio

本文主要包括以下部分:

1. 编译 LLVM 项目
2. LLVM 相关工具的使用和调试
3. LLVM Pass 的实现和调试
4. OLLVM 的移植和使用
5. OLLVM 移植到 Android NDK
6. OLLVM Pass 的源码分析和混淆效果分析
7. 参考资料及相关 OLLVM 项目

其中1-5为基础部分, 6为重点部分

文章附件 [ollvm-study-attachments.zip](https://pan.baidu.com/s/1YVSOccGhlLc8X8ZQ5u4SWg?pwd=k7f2) :

- hello-llvm 使用llvm相关工具时的测试文件
- MD5FunctionNamePass MD5函数名加密Pass的CLion项目
- MyPass 自定义函数和模块Pass的CLion项目
- OLLVM-Pases-19.x 适用于LLVM-19.x系列的Obfuscation, 包括修复后的CallSite-Fixed.h头文件
- OllvmTest 阅读源码和调试Obfuscation Pass时的相关测试文件

注意:

1. 本文最初基于llvm-18.1.8, 使用fla混淆时遇到无法修复的bug, 遂改用llvm19

如遇文中涉及llvm18的文字或图片请默认替换为llvm19
2. 不同机器和平台上可能遇到不同问题, 本文以Windows 10平台为主
3. 使用LLVM和OLLVM仅需要Release模式编译clang即可(占用空间小)

调试时需要Debug模式编译llvm,clang,lld(占用空间大,约100G)

# 编译LLVM

LLVM 官网下载 https://releases.llvm.org github链接 https://github.com/llvm/llvm-project.git

NDK 28.2.13676358 对应 clang 19.0.1

![image](https://bbs.kanxue.com/upload/attach/202511/968342_58WJS27H4WTBZ39.png)

NDK 27.3.13750724 对应 clang 18.0.4 (本文后续涉及到该版本NDK请替换为上述版本)

![image](https://bbs.kanxue.com/upload/attach/202511/968342_JPASH4AWK3UGFBZ.png)

可以到 https://github.com/llvm/llvm-project/releases 查看是否有一致的版本,如果没有可以拉取最近的版本

拉取距离最近的19.1.7版本 (--depth 1 指定浅克隆, 不保存历史更改记录)

```
git clone --depth 1 --branch llvmorg-19.1.7 https://github.com/llvm/llvm-project.git
```

编译LLVM参考 https://llvm.org/docs/GettingStarted.html

主要分为2步:

- cmake初始化ninja构建配置
- ninja构建项目

## Windows 编译 LLVM

windows平台编译clang有2种方案: 使用msvc或mingw 不同方案编译得到的clang行为会略有不同

本文以msvc为例, 安装Visual Studio 2022后, 搜索MSVC命令行工具并打开

![image](https://bbs.kanxue.com/upload/attach/202511/968342_MHQNKB8DAWU7QAU.png)

进入llvm/build目录, 注意cd命令需添加/d参数进行跨分区跳转

参考[windows下命令行模式中cd命令无效的原因](https://www.cnblogs.com/huchong/p/7474087.html)

![5-MSVC-cmake](https://bbs.kanxue.com/upload/attach/202511/968342_QJWA5XAT8EGND5D.png)

之后使用cmake初始化ninja构建配置

```
cmake -G "Ninja" -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_FLAGS="/utf-8" -DLLVM_ENABLE_RTTI=ON -DLLVM_ENABLE_EH=ON -DLLVM_ENABLE_PROJECTS="llvm;clang;lld" ../llvm
```

参数的具体作用如下：

1. -G "Ninja" 指定构建系统Build工具
2. -DCMAKE_BUILD_TYPE=Debug

指定构建类型为 Debug 模式，包含调试信息，不启用优化，便于开发和调试
3. -DCMAKE_CXX_FLAGS="/utf-8"
向 C++ 编译器传递 "/utf-8" 选项（这是 MSVC 编译器的选项），指定源文件和执行字符集为 UTF-8
4. -DLLVM_ENABLE_RTTI=ON
启用运行时类型信息（RTTI），LLVM 默认禁用 RTTI 以提高性能，启用后可使用 dynamic_cast`等依赖 RTTI 的功能
5. -DLLVM_ENABLE_EH=ON
启用 C++ 异常处理（EH），LLVM 默认禁用异常，启用后允许代码中使用 try/catch 等异常机制。
6. -DLLVM_ENABLE_PROJECTS="llvm;clang;lld"
指定要构建的 LLVM 子项目，这里包括核心的 LLVM 库、Clang 编译器和 LLD 链接器。
7. ../llvm
指定 LLVM 源代码的根目录路径，cmake 会从该目录读取 CMakeLists.txt 进行配置。

执行这条命令后，会在当前目录(build)生成 Ninja 构建文件，之后可以使用ninja命令进行编译构建

| 1 | `ninja -j16` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202511/968342_R5AGE3P6GJDPK5Q.png)

Debug模式编译完成后有100G+,需预留足够空间

![7-llvm-build-size](https://bbs.kanxue.com/upload/attach/202511/968342_7QE9RP6Z5AZ27JM.png)

编译完成后进入bin目录验证是否正常运行

![image](https://bbs.kanxue.com/upload/attach/202511/968342_ZJWXVMDMCCM5EPW.png)

## Mac 编译 LLVM

安装cmake和ninja用于构建llvm项目

| 1 | `brew` `install` `cmake ninja` |
|-|-|

拉取llvm源码项目

| 1 | `git clone --depth 1 --branch llvmorg-19.1.7 https:``//github``.com``/llvm/llvm-project``.git` |
|-|-|

cmake配置构建设置 (release版)

| 1234 | `cd` `llvm-project-19.1.7``mkdir` `build``cd` `build``cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_RTTI=ON -DLLVM_ENABLE_EH=ON -DLLVM_ENABLE_PROJECTS=``"clang"` `..``/llvm` |
|-|-|

如果配置debug版

| 1 | `cmake -G Ninja -DCMAKE_BUILD_TYPE=Debug -DLLVM_ENABLE_RTTI=ON -DLLVM_ENABLE_EH=ON -DLLVM_ENABLE_PROJECTS=``"llvm;clang;lld"` `..``/llvm` |
|-|-|

构建项目

| 1 | `ninja -j16` |
|-|-|

将clang所在bin目录临时添加到PATH

| 1 | `export` `PATH=``"/Users/orientalglass/Study/OLLVMStudy/attachents/llvm-project/build/bin:$PATH"` |
|-|-|

注意: 使用clang时需要指定系统sdk路径, 否则clang会报 "can't find "<stdio.h>" 等错误, 例如

| 1 | `clang -isysroot` `/Applications/Xcode``.app``/Contents/Developer/Platforms/MacOSX``.platform``/Developer/SDKs/MacOSX``.sdk` `/Users/orientalglass/Study/OLLVMStudy/attachents/Test/test``.c -o` `/Users/orientalglass/Study/OLLVMStudy/attachents/Test/test` |
|-|-|

## Linux 编译 LLVM

大部分文章基于linux编译llvm, 先安装依赖后拉取llvm源码编译即可, 此处不多赘述

可参考 [从llvm到ollvm学习笔记](https://whitebird0.github.io/post/%E4%BB%8Ellvm%E5%88%B0ollvm%E5%AD%A6%E4%B9%A0%E7%AC%94%E8%AE%B0.html) 和 [[原创]llvm学习笔记——llvm基础](https://bbs.kanxue.com/thread-279624.htm)

## Clang 编译 C代码

使用前可将编译好的clang所在bin目录添加到环境变量

hello.c代码如下

| 12345 | `#include <stdio.h>``int` `main() {``printf``(``"Hello, World!\n"``);``return` `0;``}` |
|-|-|

编译

| 1 | `clang hello.c` `-``o hello.exe` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202511/968342_VGMHU8K78VN4Z52.png)

## CLion 调试 Clang

使用CLion打开clang/CMakeLists.txt, 并选择作为项目打开

### llvm-gtest报错

此时发现报错如下,这个错误表明 CMake 在配置 LLVM 项目时找不到 llvm-gtest，因此无法继续

![image](https://bbs.kanxue.com/upload/attach/202511/968342_DPKYPEF3R8XAUQX.png)

由于不需要运行测试，可通过添加CMake配置参数 "-DLLVM_INCLUDE_TESTS=OFF" 跳过测试模块

另外在Windows平台建议将默认的编译工具链Toolchain由MinGW替换为Visual Studio, 保证兼容性防止出现bug

![image](https://bbs.kanxue.com/upload/attach/202511/968342_RTGFQ4D8BMPRQJP.png)

### 安装zlib库

之后遇到第2个报错,原因是缺少zlib库

![image](https://bbs.kanxue.com/upload/attach/202511/968342_GPMRDAZMFF5X8FG.png)

参考文章[Windows中zlib的安装与配置](https://blog.csdn.net/m0_64206188/article/details/129903489)

首先拉取zlib源码

```
git clone https://github.com/madler/zlib.git
```

再打开CMake-gui

![image](https://bbs.kanxue.com/upload/attach/202511/968342_FBT3RGCR92YGXZE.png)

分别输入zlib的源码路径和build路径, 之后依次点击左下方Configure,Generate

中间文本框可能出现红色,此时再次点击Configure和Generate消除红色即可

最后点击Open Project,使用VS打开项目

![image](https://bbs.kanxue.com/upload/attach/202511/968342_T74EURXXFQM4KGS.png)

首先右键INSTALL项目并设为启动项目

![image](https://bbs.kanxue.com/upload/attach/202511/968342_GGZ5F6Q9HVBCFDJ.png)

再选择Release模式Build INSTALL项目,成功后显示如下:

![image](https://bbs.kanxue.com/upload/attach/202511/968342_B7UU6HYWZMD3SQS.png)

注意: 此处由于需要将编译后的zlib库写入系统核心区,可能会报错如下

| 1234567891011 | `错误  MSB3073 命令“setlocal``"C:\Program Files\CMake\bin\cmake.exe"` `-``DBUILD_TYPE``=``Release` `-``P cmake_install.cmake``if` `%``errorlevel``%` `neq` `0` `goto :cmEnd``:cmEnd``endlocal & call :cmErrorLevel` `%``errorlevel``%` `& goto :cmDone``:cmErrorLevel``exit` `/``b` `%``1``:cmDone``if` `%``errorlevel``%` `neq` `0` `goto :VCEnd``:VCEnd”已退出，代码为` `1``。` `INSTALL C:\Program Files\Microsoft Visual Studio\``2022``\Community\MSBuild\Microsoft\VC\v170\Microsoft.CppCommon.targets` `166` |
|-|-|

这个问题是由于权限不足,只需要手动用管理员权限打开VS并重新Build即可解决

### 安装zstd库

解决zlib后紧接着又出现了zstd库的问题

![image](https://bbs.kanxue.com/upload/attach/202511/968342_49S2DQ694F944AE.png)

参考[windows环境下zstd编译](https://blog.csdn.net/jamin_liu_90/article/details/142964462), 编译流程类似zlib

zstd源码项目解压后,在build/cmake中有CMakeLists.txt

![image](https://bbs.kanxue.com/upload/attach/202511/968342_2CPVEXV3CCYBHHF.png)

编译完成后以管理员权限运行VisualStudio, 打开~zstd\build\cmake\build\zstd.sln

同安装zlib时类似,先生成再设置INSTALL项目为启动项目进行安装便可以解决问题

![image](https://bbs.kanxue.com/upload/attach/202511/968342_P6XGNRF6DSV956D.png)

std库安装成功后输出如下

![image](https://bbs.kanxue.com/upload/attach/202511/968342_CS4EPQCZYXJDGZT.png)

然而此时仍会报错,CMake没有找到zstd,需要手动添加find_package指明zstd

![image](https://bbs.kanxue.com/upload/attach/202511/968342_PQC6VXQGU2BKXD6.png)

大功告成之后,可以看到LLVM的项目

![image](https://bbs.kanxue.com/upload/attach/202511/968342_3BHF6K7SBG7T6QC.png)

### debug配置

debug前先设置clang的debug配置,添加启动参数,实际上就是保证启动时执行以下编译命令(参数输入clang后面的部分即可,CLion调试时自动拼接):

| 1 | `clang` `"E:\KnowledgeRepository\Study\OLLVMStudy\attachments\hello.c"` `-``o` `"E:\KnowledgeRepository\Study\OLLVMStudy\attachments\hello.exe"` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202511/968342_E9Y7REK4HX2PCYH.png)

之后找到clang_main并下断点调试 (clang/tools/driver/driver.cpp)

**注意: 调试时CLion会重新编译一次clang,需要花费一定时间和空间**

### z.dll缺失

然而运行后找不到z.dll,明明前面安装zlib时已经安装了z.dll,为什么这里找不到呢?

仔细一看VS的输出,发现z.dll是安装到了C:\Program Files (x86)\zlib\bin目录内,并非是直接安装为系统dll

![image](https://bbs.kanxue.com/upload/attach/202511/968342_9W87DYCTXWT86FN.png)

于是复制一份z.dll到CLion的debug输出目录下,成功解决问题

![image](https://bbs.kanxue.com/upload/attach/202511/968342_UNTUQ4WHADWMDWN.png)

后记: 似乎重新编译后能识别到系统的z.dll, 无需手动复制, 可能由于先前编译时没有安装zlib

# LLVM Pass

## LLVM基础

官方手册 https://llvm.org/docs/LangRef.html 和 https://llvm.gnu.ac.cn/docs/LangRef.html

[[原创]llvm学习笔记——llvm基础](https://bbs.kanxue.com/thread-279624.htm)

## LLVM IR

### IR的概念

LLVM IR（Intermediate Representation，中间表示）是 LLVM 编译框架的核心。它是一种 **介于高级语言（如 C/C++）与底层机器码之间的中间语言** ，既能表达高级语言的语义，又足够接近机器指令，便于优化和生成目标代码。

LLVM IR 的两种存储形式：

- 文本格式（.ll）：人类可读，方便分析和调试。
- 二进制格式（.bc）：Bitcode 文件，适合存储和传输。

LLVM IR 与具体 CPU 架构解耦，可以跨平台复用优化逻辑。LLVM IR 参考手册https://llvm.org/docs/LangRef.html

### IR示例

例如一段C代码

| 123 | `int` `add(``int` `a,` `int` `b) {``return` `a + b;``}` |
|-|-|

对应的LLVM IR (.II)如下

| 12345 | `define i32 @add(i32` `%``a, i32` `%``b) {``entry:``%``0` `=` `add i32` `%``a,` `%``b``ret i32` `%``0``}` |
|-|-|

在这个例子中：

- define i32 @add 定义了一个返回 i32 的函数 add；
- %a 和 %b 是函数参数；
- add i32 %a, %b 表示整数相加；
- ret i32 %0 返回结果。

通过 LLVM IR，编译器就能在架构无关的层面做优化，然后再交由 LLVM 后端翻译成目标平台的机器码。

### 使用LLVM Tools

1. 将C文件转换为LLVM IR (.ll)

| 1 | `clang` `-``emit``-``llvm` `-``S hello.c` `-``o hello.ll` |
|-|-|
2. 生成二进制LLVM IR (.bc)

| 1 | `clang` `-``emit``-``llvm` `-``c hello.c` `-``o hello.bc` |
|-|-|
3. 使用llvm-dis将.bc转换为.ll形式

| 1 | `llvm``-``dis hello.bc` `-``o hello_bc2ll.ll` |
|-|-|
4. 使用llvm-as将.ll转换为.bc

| 1 | `llvm``-``as hello.ll` `-``o hello_ll2bc.bc` |
|-|-|
5. 将LLVM bitcode转换为汇编

| 1 | `llc hello.bc` `-``o hello.s` |
|-|-|
6. 将汇编转换成可执行程序

| 1 | `clang hello.s` `-``o hello.exe` |
|-|-|

结果如下

![image](https://bbs.kanxue.com/upload/attach/202511/968342_U6S24TMPTBXYS2V.png)

其中.ll的文件内容如下(省略部分)

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273 | `; ModuleID` `=` `'hello.c'``source_filename` `=` `"hello.c"``target datalayout` `=` `"e-m:w-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"``target triple` `=` `"x86_64-pc-windows-msvc19.41.34123"` `$sprintf` `=` `comdat` `any` `$vsprintf` `=` `comdat` `any` `$_snprintf` `=` `comdat` `any` `$_vsnprintf` `=` `comdat` `any` `$printf` `=` `comdat` `any` `$_vsprintf_l` `=` `comdat` `any` `$_vsnprintf_l` `=` `comdat` `any` `$__local_stdio_printf_options` `=` `comdat` `any` `$_vfprintf_l` `=` `comdat` `any` `$``"??_C@_0P@MHJMLPNF@Hello?0?5World?$CB?6?$AA@"` `=` `comdat` `any` `@``"??_C@_0P@MHJMLPNF@Hello?0?5World?$CB?6?$AA@"` `=` `linkonce_odr dso_local unnamed_addr constant [``15` `x i8] c``"Hello, World!\0A\00"``, comdat, align` `1``@__local_stdio_printf_options``._OptionsStorage` `=` `internal` `global` `i64` `0``, align` `8` `......` `; Function Attrs: noinline nounwind optnone uwtable``define dso_local i32 @main()` `#0 {``entry:``%``retval` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retval, align` `4``%``call` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_0P@MHJMLPNF@Hello?0?5World?$CB?6?$AA@"``)``ret i32` `0``}` `......` `entry:``%``_ArgList.addr` `=` `alloca ptr, align` `8``%``_Locale.addr` `=` `alloca ptr, align` `8``%``_Format.addr` `=` `alloca ptr, align` `8``%``_Stream.addr` `=` `alloca ptr, align` `8``store ptr` `%``_ArgList, ptr` `%``_ArgList.addr, align` `8``store ptr` `%``_Locale, ptr` `%``_Locale.addr, align` `8``store ptr` `%``_Format, ptr` `%``_Format.addr, align` `8``store ptr` `%``_Stream, ptr` `%``_Stream.addr, align` `8``%``0` `=` `load ptr, ptr` `%``_ArgList.addr, align` `8``%``1` `=` `load ptr, ptr` `%``_Locale.addr, align` `8``%``2` `=` `load ptr, ptr` `%``_Format.addr, align` `8``%``3` `=` `load ptr, ptr` `%``_Stream.addr, align` `8``%``call` `=` `call ptr @__local_stdio_printf_options()``%``4` `=` `load i64, ptr` `%``call, align` `8``%``call1` `=` `call i32 @__stdio_common_vfprintf(i64 noundef` `%``4``, ptr noundef` `%``3``, ptr noundef` `%``2``, ptr noundef` `%``1``, ptr noundef` `%``0``)``ret i32` `%``call1``}` `declare dso_local ptr @__acrt_iob_func(i32 noundef)` `#2` `declare dso_local i32 @__stdio_common_vfprintf(i64 noundef, ptr noundef, ptr noundef, ptr noundef, ptr noundef)` `#2`  `!llvm.module.flags` `=` `!{!``0``, !``1``, !``2``, !``3``}``!llvm.ident` `=` `!{!``4``}` `!``0` `=` `!{i32` `1``, !``"wchar_size"``, i32` `2``}``!``1` `=` `!{i32` `8``, !``"PIC Level"``, i32` `2``}``!``2` `=` `!{i32` `7``, !``"uwtable"``, i32` `2``}``!``3` `=` `!{i32` `1``, !``"MaxTLSAlign"``, i32` `65536``}``!``4` `=` `!{!``"clang version 18.1.8 (https://github.com/llvm/llvm-project.git 3b5b5c1ec4a3095ab096dd780e84d7ab81f3d7ff)"``}` |
|-|-|

.s汇编文件的main函数如下,可以发现默认使用AT&T汇编语法

```
main:                                   # @main
.seh_proc main
# %bb.0:                                # %entry
    subq	$40, %rsp
    .seh_stackalloc 40
    .seh_endprologue
    movl	$0, 36(%rsp)
    leaq	"??_C@_0P@MHJMLPNF@Hello?0?5World?$CB?6?$AA@"(%rip), %rcx
    callq	printf
    xorl	%eax, %eax
    addq	$40, %rsp
    retq
    .seh_endproc
                                        # -- End function
    .def	printf;
    .scl	2;
    .type	32;
    .endef
    .section	.text,"xr",discard,printf
    .globl	printf                          # -- Begin function printf
    .p2align	4, 0x90
```

反汇编hello.exe结果如下

![image](https://bbs.kanxue.com/upload/attach/202511/968342_Z6EMN75RPG82PCJ.png)

两种语法的主要不同:

1. 操作数顺序

AT&T的源操作数在前,目的操作数在后,与Intel语法相反

例如：movl %eax, %ebx（ebx=eax）
2. 操作数大小指定方式

AT&T通过指令后缀显式指定操作数位数

b8位, w16位, l32位, q64位

例如：movb %al, %bl（8 位移动）、movq %rax, %rbx（64 位移动）

而Intel语法由寄存器隐含操作数大小,如al,ax,eax,rax
3. 寄存器和立即数前缀

AT&T的寄存器加前缀'%', 立即数加前缀'$', Intel则无需前缀
4. 内存寻址方式

	- AT&T 语法：格式为 section:disp(base, index, scale)
	例如：movl 0x10(%rbp, %rdi, 4), %eax
	表示地址 = 0x10（位移） + rbp（基址） + rdi×4（索引 × 比例）
	- Intel 语法：格式为 [base + index*scale + disp]
	例如：mov eax, [rbp + rdi*4 + 0x10]
5. jmp和call的目标表示

	- **AT&T 语法**：符号前加'$'表示绝对地址，无符号表示相对地址
	例如：jmp $label（绝对跳转）、jmp label（相对跳转）
	- **Intel 语法**：直接写符号，由汇编器自动处理地址类型
	例如：jmp label（无需特殊前缀）

## LLVM opt

opt 是 LLVM 提供的一个命令行工具，主要用于 **对 LLVM IR 进行分析和优化** 。

它不会直接生成目标机器码，而是专注于 **IR 层面的处理** ，通常在编译流程中作为“优化器”环节出现。

opt 工具通过应用各种优化 Pass，可以实现 **“优化/分析” ** 的目的。

| 1234567891011 | `LLVM IR (.ll` `/` `.bc)``↓``opt 工具``↓  （加载并执行多个 Pass）``┌───────────────┐``│ Pass A (分析) │``│ Pass B (优化) │``│ Pass C (混淆) │``└───────────────┘``↓``优化``/``变换后的 LLVM IR` |
|-|-|

opt O3优化.ll文件生成.bc文件

| 1 | `opt` `-``O3 hello.ll` `-``o hello_optll.bc` |
|-|-|

opt O3优化.bc文件生成.ll文件, -S表示输出可读的文本格式

| 1 | `opt` `-``O3 hello.bc` `-``S` `-``o hello_optbc.ll` |
|-|-|

应用单个pass优化, 参数说明：

- -passes：应用特定的优化 pass
- mem2reg：把内存变量提升为寄存器变量（SSA 形式）
- -S：输出可读的 .ll 文件

| 1 | `opt` `-``passes``=``mem2reg hello.ll` `-``S` `-``o hello_opt_mem2reg.ll` |
|-|-|

函数内联优化,将函数调用替换为函数体减少调用开销

| 1 | `opt` `-``passes``=``inline hello.ll` `-``S` `-``o hello_opt_inline.ll` |
|-|-|

应用多个pass

| 1 | `opt` `-``passes``=``"mem2reg,inline,constprop"` `hello.ll` `-``S` `-``o hello_opt_passes.ll` |
|-|-|

生成函数的控制流图（Control Flow Graph）, 输出.dot文件

| 1 | `opt` `-``passes``=``dot``-``cfg hello.ll` |
|-|-|

## CLion调试opt

CLion 打开 llvm-project\llvm\CMakeLists.txt 并作为项目打开

打开CMake设置, 设置默认工具链Toolchain为Visual Studio

遇到第一种报错,提示路径字符过长,直接在LLVM项目的CMakeLists.txt中设置最大值, set(CMAKE_OBJECT_PATH_MAX 512) , 不需要每个子项目单独设置

![image](https://bbs.kanxue.com/upload/attach/202511/968342_NH39SPA2GMD6G4X.png)

之后出现第二个警告,选择直接忽略

![image](https://bbs.kanxue.com/upload/attach/202511/968342_NJSD4QZ6R9XBFGK.png)

设置参数

| 1 | `-``O3` `"E:\KnowledgeRepository\Study\OLLVMStudy\attachments\hello.ll"` `-``o` `"E:\KnowledgeRepository\Study\OLLVMStudy\attachments\hello_opt.bc"` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202511/968342_EDREM4ZBT5QV4RE.png)

在llvm/tools/opt/opt.cpp中给main函数下断点调试, 同调试clang类似,需要手动添加z.dll保证正常运行

![image](https://bbs.kanxue.com/upload/attach/202511/968342_JQJ4FG5T2HSM5PT.png)

## LLVM Pass

LLVM Pass 是 LLVM 的扩展机制，**Pass** 是一种对程序中间表示（IR）进行分析或转换的模块，由 Pass Manager 统一调度。

通过编写自定义 Pass，开发者可以插入自己的逻辑来优化代码、分析性能或插入调试信息等。

Pass的分类

| Pass | 作用范围 | 适用场合 |
|-|-|-|
| Module Pass | 作用于整个llvm::Module | 适用于需要全局视角的操作，例如链接优化或全局变量分析 |
| Function Pass | 针对每个函数 llvm::Function | 适用于优化单个函数内的代码，例如循环优化、死代码删除等 |
| Basic Block Pass | 针对函数内的每个基本块（Basic Block） | 通常用于优化基本块内部，例如指令合并、无用指令消除等 |

## Pass的实现

老版本 https://llvm.org/docs/WritingAnLLVMPass.html

新版本 https://llvm.org/docs/WritingAnLLVMNewPMPass.html

### 实现Module Pass

创建 MyModulePass.cpp，定义一个模块级别的 Pass，run 函数实现了对模块的遍历，并输出每个函数的名称

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152 | `#include "llvm/IR/PassManager.h"  // 包含 LLVM 新 Pass Manager 的头文件``#include "llvm/Passes/PassBuilder.h"  // 提供 PassBuilder，用于注册和管理 Pass``#include "llvm/Passes/PassPlugin.h"  // 用于实现动态插件的接口``#include "llvm/IR/Module.h"  // 定义了 Module 类，用于表示 LLVM IR 的顶层结构``#include "llvm/Support/raw_ostream.h"  // 提供 LLVM 的输出支持，如 errs() 输出到标准错误流` `using` `namespace` `llvm;` `// 使用 LLVM 命名空间简化代码` `// 定义一个 Module Pass``struct` `MyModulePass : PassInfoMixin<MyModulePass> {``// run 函数：Pass 的主入口，用于实现实际的操作逻辑``// 参数说明``// Module &M: 表示当前处理的模块``// ModuleAnalysisManager &MAM: 提供对模块级分析的访问``PreservedAnalyses run(Module &M, ModuleAnalysisManager &MAM) {``// 输出当前模块的名称``errs() <<` `"Processing Module: "` `<< M.getName() <<` `"\n"``;` `// 遍历模块中的每个函数``for` `(``auto` `&F: M) {``// 输出每个函数的名称``errs() <<` `"Function: "` `<< F.getName() <<` `"\n"``;``}` `// 返回 PreservedAnalyses::all()，表示此 Pass 不修改 IR``return` `PreservedAnalyses::all();``}``};` `// 动态插件入口函数，LLVM 在加载插件时会调用此函数``// 函数名固定为 llvmGetPassPluginInfo，返回插件的描述信息``extern` `"C"` `PassPluginLibraryInfo llvmGetPassPluginInfo() {``// 返回插件的信息``return` `{``LLVM_PLUGIN_API_VERSION,` `// LLVM 插件 API 的版本号``"MyPass"``,` `// 插件的名称``LLVM_VERSION_STRING,` `// 当前 LLVM 的版本号``[](PassBuilder &PB) {` `// PassBuilder 的回调函数，用于注册 Pass``// 注册解析 Pipeline 的回调函数``PB.registerPipelineParsingCallback(``[](StringRef Name, ModulePassManager &MPM,``ArrayRef<PassBuilder::PipelineElement>) {``// 检查 Pipeline 中的 Pass 名称是否为 "my-module-pass"``if` `(Name ==` `"my-module-pass"``) {``// 将 MyModulePass 注册到模块 Pass 管理器中``MPM.addPass(MyModulePass());``return` `true``;` `// 表示 Pass 已成功注册``}``return` `false``;` `// 名称不匹配，忽略``});``}};``}` |
|-|-|

### 实现Function / Basic Block Pass

创建 MyFunctionPass.cpp，定义一个函数级别的 Pass，run 遍历函数中的基本块以及基本块中的每条指令，并将其输出

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960 | `#include "llvm/IR/PassManager.h"  // 包含 LLVM 新 Pass 管理器的头文件``#include "llvm/Passes/PassBuilder.h"  // 提供 PassBuilder，用于构建和注册 Pass``#include "llvm/Passes/PassPlugin.h"  // 提供 Pass 插件接口的支持``#include "llvm/IR/Module.h"  // 定义 LLVM IR 的模块类``#include "llvm/Support/raw_ostream.h"  // 提供 LLVM 的输出支持，比如 errs()` `using` `namespace` `llvm;` `// 使用 LLVM 的命名空间，简化后续代码编写` `// 定义一个函数级别的 Pass``struct` `MyFunctionPass :` `public` `PassInfoMixin<MyFunctionPass> {``// 函数级别的运行入口``// 参数``//   - Function &F: 当前正在处理的函数``//   - FunctionAnalysisManager &FAM: 函数级别的分析管理器``PreservedAnalyses run(Function &F, FunctionAnalysisManager &FAM) {``// 输出当前函数的名称``errs() <<` `"Processing Function: "` `<< F.getName() <<` `"\n"``;` `// 遍历函数中的每个基本块（Basic Block）``for` `(``auto` `&BB : F) {``errs() <<` `"Basic Block:\n"``;``// 遍历基本块中的每条指令``for` `(``auto` `&I : BB) {``// 输出当前指令``errs() << I <<` `"\n"``;``}``}` `// 返回 PreservedAnalyses::all()，表明该 Pass 不修改 IR``return` `PreservedAnalyses::all();``}``};` `// 定义插件的入口函数，注册 Pass 到 Pass 管理器``llvm::PassPluginLibraryInfo getPassPluginInfo() {``// 返回插件的元信息``return` `{``LLVM_PLUGIN_API_VERSION,` `// LLVM 插件的 API 版本``"MyPass"``,` `// 插件名称``LLVM_VERSION_STRING,` `// 当前 LLVM 的版本号``[](PassBuilder &PB) {` `// 一个回调，用于将 Pass 注册到 PassBuilder 中``// 注册管道解析回调函数，用于支持命令行参数调用``PB.registerPipelineParsingCallback(``[](StringRef Name, FunctionPassManager &FPM,``ArrayRef<PassBuilder::PipelineElement>) {``// 检查命令行中的 Pass 名称是否匹配 "my-function-pass"``if` `(Name ==` `"my-function-pass"``) {``// 如果匹配，将自定义 Pass 添加到函数 Pass 管理器中``FPM.addPass(MyFunctionPass());``return` `true``;` `// 表明注册成功``}``return` `false``;` `// 未匹配，跳过此 Pass``});``}};``}` `// 必须导出符号 `llvmGetPassPluginInfo`，这是 LLVM 插件的入口点``extern` `"C"` `LLVM_ATTRIBUTE_WEAK ::llvm::PassPluginLibraryInfo llvmGetPassPluginInfo() {``return` `getPassPluginInfo();` `// 调用自定义的插件入口函数``}` |
|-|-|

### 编译Pass

创建 CMake 项目配置文件 CMakeLists.txt

```
cmake_minimum_required(VERSION 3.5.1)
# 设置 LLVM 安装目录的路径，LLVM_DIR 指向 LLVM 的 cmake 配置目录
#set(LLVM_DIR "E:/KnowledgeRepository/Study/OLLVMStudy/attachments/llvm-project/build/lib/cmake/llvm")
# 项目名称
project(pass)

# 查找已安装的 LLVM，要求是通过 CONFIG 模式查找
find_package(LLVM REQUIRED CONFIG)
# 将 LLVM 的 CMake 模块路径添加到 CMake 模块路径中
list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")
# 包含 LLVM 的 CMake 配置文件，用于导入其编译选项和头文件路径
include(LLVMConfig)

# 设置 C++ 标准为 C++17，并强制启用标准特性
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED YES)
set(CMAKE_CXX_EXTENSIONS NO)

# /MD   使用多线程的动态运行时库（Release 模式常用）。
# /MDd  使用多线程的动态运行时库（带调试符号，Debug 模式）。
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /MD")

# 设置 LLVM 编译标志
separate_arguments(LLVM_DEFINITIONS_LIST NATIVE_COMMAND ${LLVM_DEFINITIONS})
add_definitions(${LLVM_DEFINITIONS_LIST})

# 包含 LLVM 头文件路径
include_directories(${LLVM_INCLUDE_DIRS})

# 链接 LLVM 的库目录，确保链接阶段可以找到需要的库
link_directories(${LLVM_LIBRARY_DIRS})

# 添加自定义 Pass
add_library(MyPass SHARED
        MyFunctionPass.cpp
        #        MyModulePass.cpp
)

# 自动映射并链接需要的 LLVM 组件库（如 core、support 等）
llvm_map_components_to_libnames(LLVM_LIBS core support)

# 将生成的共享库与必要的 LLVM 库链接起来
target_link_libraries(MyPass ${LLVM_LIBS})

# 在 Windows 平台上，显式指定要导出的符号（如 llvmGetPassPluginInfo）
if (WIN32)
    # 使用 export.def 文件来控制导出符号
    set_target_properties(MyPass PROPERTIES LINK_FLAGS "/DEF:${CMAKE_CURRENT_SOURCE_DIR}/export.def")
endif ()
```

在 Windows 上，动态链接库（DLL）的符号导出通常需要显式指定。否则，运行时的链接器（linker）无法正确找到并加载这些符号。

创建一个 export.def 文件，用于显式导出 llvmGetPassPluginInfo

参数说明：

- LIBRARY: DLL 的名称（不需要扩展名），这里是 MyPass
- EXPORTS: 列出需要导出的函数名

| 123 | `LIBRARY MyPass``EXPORTS``llvmGetPassPluginInfo` |
|-|-|

执行命令编译pass

| 12345678 | `# 创建 build 目录``mkdir build && cd build` `# 运行 CMake 命令生成构建文件``cmake` `-``G` `"Ninja"` `-``DCMAKE_BUILD_TYPE``=``Release ..` `# 编译项目``cmake` `-``-``build .` |
|-|-|

编译成功

![image](https://bbs.kanxue.com/upload/attach/202511/968342_6DVE3HWM54TAKSG.png)

### 测试Pass

编译后可通过 opt 命令运行 Pass

其中：

- -load-pass-plugin 加载插件。
- -passes 指定运行的 Pass 名称。

创建test.ll文件

| 123 | `define i32 @main() {``ret i32` `0``}` |
|-|-|

使用 opt 工具加载 MyPass.dll 插件，运行自定义的 my-function-pass ，对 test.ll 进行优化处理，并将结果输出到 test_opt.ll

| 1234 | `opt` `-``-``load``-``pass``-``plugin``=``MyPass.dll` `-``-``passes``=``my``-``function``-``pass` `-``S test.ll` `-``o test_opt.ll``Processing Function: main``Basic Block:``ret i32` `0` |
|-|-|

同上类似,需要将zstd.dll和MyPass.dll放到同一路径,否则会报错

![image](https://bbs.kanxue.com/upload/attach/202511/968342_K57DFK87ZVFTA9C.png)

为根绝该问题,选择创建环境变量EnvsPath, 保存zstd和zlib的bin目录路径

之后将"%EnvsPath%"添加到环境变量Path中即可让所有程序都能找到对应dll

![image](https://bbs.kanxue.com/upload/attach/202511/968342_4JDDDV9SKVQZAYS.png)

## 脱离LLVM源码编译Pass

新版脱离源码开发Pass [Developing LLVM passes out of source](https://llvm.org/docs/CMake.html#id20)

新版Pass编写教程 [WritingAnLLVMNewPMPass](https://llvm.org/docs/WritingAnLLVMNewPMPass.html)

旧版脱离源码开发Pass [8.0.1 developing-llvm-passes-out-of-source](https://releases.llvm.org/8.0.1/docs/CMake.html#developing-llvm-passes-out-of-source)

旧版Pass编写教程 [8.0.1 WritingAnLLVMPass.html](https://releases.llvm.org/8.0.1/docs/WritingAnLLVMPass.html)

主要步骤:

1. 创建项目project,在其中创建CMakeLists.txt, MyFunctionPass和MyModulePass目录
2. 在MyFunctionPass和MyModulePass目录内分别创建CMakeLists.txt和对应的cpp文件
3. 配置所有CMakeLists.txt, 编写Pass

### project/CMakeLists.txt

```
cmake_minimum_required(VERSION 3.22.0)  # 指定需求的cmake最低版本
project(MyPasses)   # 整个项目的名称, 与编译出的pass无关

# 指定LLVM的cmake配置目录
set(LLVM_DIR "E:\\KnowledgeRepository\\Study\\OLLVMStudy\\attachments\\OLLVM-19.1.7\\llvm-project\\build\\lib\\cmake\\llvm")

# 通过config模式查找已安装的LLVM包
find_package(LLVM REQUIRED CONFIG)
list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")
include(LLVMConfig)

# 设置C++标准为C++17，并强制启用标准特性
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED YES)
set(CMAKE_CXX_EXTENSIONS NO)

# 设置LLVM编译标志
separate_arguments(LLVM_DEFINITIONS_LIST NATIVE_COMMAND ${LLVM_DEFINITIONS})
add_definitions(${LLVM_DEFINITIONS_LIST})

# 包含LLVM头文件
include_directories(${LLVM_INCLUDE_DIRS})
# 链接LLVM库目录，确保链接阶段可以找到需要的库
link_directories(${LLVM_LIBRARY_DIRS})

# 添加pass子目录,pass代码以及如何编译pass均在子目录实现,主项目会自动进入子项目寻找CMakeLists进行构建
add_subdirectory(MyModulePass)
add_subdirectory(MyFunctionPass)

# 自动映射并链接需要的LLVM组件库（如 core、support 等）
llvm_map_components_to_libnames(LLVM_LIBS core support)

# 链接生成的pass与必要的LLVM库
target_link_libraries(MyModulePass ${LLVM_LIBS})
target_link_libraries(MyFunctionPass ${LLVM_LIBS})

# Windows上，dll需要显式指定导出的符号（llvmGetPassPluginInfo指定pass插件入口）, 此处使用 export.def 文件控制导出符号
if (WIN32)
    set_target_properties(MyModulePass PROPERTIES LINK_FLAGS "/DEF:${CMAKE_CURRENT_SOURCE_DIR}/export.def")
    set_target_properties(MyFunctionPass PROPERTIES LINK_FLAGS "/DEF:${CMAKE_CURRENT_SOURCE_DIR}/export.def")
endif ()
```

### project/MyFunctionPass

CMakeLists.txt

```
add_library(MyFunctionPass MODULE
        MyFunctionPass.cpp
  )
```

MyFunctionPass.cpp

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657 | `#include "llvm/IR/Function.h"``#include "llvm/IR/PassManager.h"  // 包含 LLVM 新 Pass 管理器的头文件``#include "llvm/Passes/PassBuilder.h"  // 提供 PassBuilder，用于构建和注册 Pass``#include "llvm/Passes/PassPlugin.h"  // 提供 Pass 插件接口的支持``#include "llvm/IR/Module.h"  // 定义 LLVM IR 的模块类``#include "llvm/Support/raw_ostream.h"  // 提供 LLVM 的输出支持，比如 errs()` `using` `namespace` `llvm;` `class` `MyFunctionPass :` `public` `PassInfoMixin<MyFunctionPass> {``public``:``PreservedAnalyses run(Function &F, FunctionAnalysisManager &FAM) {``// 输出当前函数的名称``// 处理所有函数，包括声明` `errs() <<` `"Function: "` `<< F.getName() <<` `" (isDeclaration: "` `<< F.isDeclaration() <<` `")\n"``;` `if``(F.getName().compare(``"main"``) !=0 ) {``// 遍历函数中的每个基本块（Basic Block）``for` `(``auto` `&BB : F) {``errs() <<` `"Basic Block:\n"``;``// 遍历基本块中的每条指令``for` `(``auto` `&I : BB) {``// 输出当前指令``errs() << I <<` `"\n"``;``}``}``}` `// 该 Pass 不修改 IR``return` `PreservedAnalyses::all();``}``};``PassPluginLibraryInfo getPassPluginInfo() {``// 返回插件的元信息``return` `{``LLVM_PLUGIN_API_VERSION,` `// LLVM 插件的 API 版本``"MyFunctionPass"``,` `// 插件名称``LLVM_VERSION_STRING,` `// 当前 LLVM 的版本号``[](PassBuilder &PB) {` `// 一个回调，用于将 Pass 注册到 PassBuilder 中``// 注册管道解析回调函数，用于支持命令行参数调用``PB.registerPipelineParsingCallback(``[](StringRef Name, FunctionPassManager &FPM,``ArrayRef<PassBuilder::PipelineElement>) {``// 检查命令行中的 Pass 名称是否匹配 "my-function-pass"``if` `(Name ==` `"my-function-pass"``) {``// 如果匹配，将自定义 Pass 添加到函数 Pass 管理器中``FPM.addPass(MyFunctionPass());``return` `true``;` `// 表明注册成功``}``return` `false``;` `// 未匹配，跳过此 Pass``});``}};``}``extern` `"C"` `LLVM_ATTRIBUTE_WEAK ::llvm::PassPluginLibraryInfo llvmGetPassPluginInfo() {``return` `getPassPluginInfo();` `// 调用自定义的插件入口函数``}` |
|-|-|

### project/MyModulePass

CMakeLists.txt

```
add_library(MyModulePass MODULE
        MyModulePass.cpp
  )
```

MyModulePass.cpp

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354 | `#include "llvm/IR/Function.h"``#include "llvm/IR/PassManager.h"  // 包含 LLVM 新 Pass 管理器的头文件``#include "llvm/Passes/PassBuilder.h"  // 提供 PassBuilder，用于构建和注册 Pass``#include "llvm/Passes/PassPlugin.h"  // 提供 Pass 插件接口的支持``#include "llvm/IR/Module.h"  // 定义 LLVM IR 的模块类``#include "llvm/Support/raw_ostream.h"  // 提供 LLVM 的输出支持，比如 errs()` `using` `namespace` `llvm;` `class` `MyModulePass :` `public` `PassInfoMixin<MyModulePass> {``public``:``PreservedAnalyses run(Module &M, ModuleAnalysisManager &MAM) {``// 输出当前模块的名称``errs() <<` `"Processing Module: "` `<< M.getName() <<` `"\n"``;` `// 遍历模块中的每个函数``for` `(``auto` `&F: M) {``// 输出每个函数的名称``errs() <<` `"Function: "` `<< F.getName() <<` `"\n"``;``for``(``auto` `&BB: F) {``errs() <<` `"Basic Block: "` `<< BB.getName() <<` `"\n"``;``for``(``auto` `&I: BB) {``errs() << I <<` `"\n"``;``}``}``}` `// 返回 PreservedAnalyses::all()，表示此 Pass 不修改 IR``return` `PreservedAnalyses::all();``}``};``PassPluginLibraryInfo getPassPluginInfo() {``return` `{``LLVM_PLUGIN_API_VERSION,` `// LLVM 插件 API 的版本号``"MyModulePass"``,` `// 插件的名称``LLVM_VERSION_STRING,` `// 当前 LLVM 的版本号``[](PassBuilder &PB) {` `// PassBuilder 的回调函数，用于注册 Pass``// 注册解析 Pipeline 的回调函数``PB.registerPipelineParsingCallback(``[](StringRef Name, ModulePassManager &MPM,``ArrayRef<PassBuilder::PipelineElement>) {``// 检查 Pipeline 中的 Pass 名称是否为 "my-module-pass"``if` `(Name ==` `"my-module-pass"``) {``// 将 MyModulePass 注册到模块 Pass 管理器中``MPM.addPass(MyModulePass());``return` `true``;` `// 表示 Pass 已成功注册``}``return` `false``;` `// 名称不匹配，忽略``});``}};``}``extern` `"C"` `LLVM_ATTRIBUTE_WEAK ::llvm::PassPluginLibraryInfo llvmGetPassPluginInfo() {``return` `getPassPluginInfo();` `// 调用自定义的插件入口函数``}` |
|-|-|

### debug配置

以MyFunctionPass为例, 编译出MyFunctionPass.dll后, 指定opt加载pass并执行

![image](https://bbs.kanxue.com/upload/attach/202511/968342_N66N6PPPRT6JCJD.png)

效果如下, 由于脱离llvm源码树,所以修改和编译起来更快,不需要每次debug重新编译clang和opt

![image](https://bbs.kanxue.com/upload/attach/202511/968342_MQ35XS9B9ECNH42.png)

### 问题: optnone导致function pass不执行

clang默认情况或O0优化下会为函数生成optnone属性, 并且添加到attributes属性集

由于该属性禁止opt对函数进行任何优化, function pass受此影响失效, 但module pass作用于整个模块, 因此不会失效

| 1234 | `attributes` `#0 = { noinline nounwind optnone uwtable "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }` `; Function Attrs: noinline nounwind optnone uwtable``define dso_local i32 @main()` `#0 {......}` |
|-|-|

解决办法:

1. clang编译时通过-Xclang指定-disable-O0-optnone (推荐)

| 1 | `clang.exe` `-``Xclang` `-``disable``-``O0``-``optnone` `-``emit``-``llvm` `-``S main.c` `-``o main.ll` |
|-|-|
2. 手动去除ir中的optnone属性

## CLion调试自定义Pass

首先设置MyPass的debug设置, 启动程序选择之前编译好的opt,参数输入如下

| 1 | `-``-``load``-``pass``-``plugin``=``"E:\KnowledgeRepository\Study\OLLVMStudy\attachments\MyPass\MyPass.dll"` `-``-``passes``=``my``-``function``-``pass` `-``S` `"E:\KnowledgeRepository\Study\OLLVMStudy\attachments\MyPass\test.ll"` `-``o` `"E:\KnowledgeRepository\Study\OLLVMStudy\attachments\MyPass\test_opt.ll"` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202511/968342_TDVTX7V9P5Z7QPW.png)

在MyFunctionPass.cpp的run方法下断点即可调试

![34-CLion-Debug-Pass](https://bbs.kanxue.com/upload/attach/202511/968342_CVMU94D9RVVWTKC.png)

## 实现函数名加密Pass

新建hello_test.c

| 12345678910111213141516171819 | `#include <stdio.h>` `const` `char` `*getHello() {``return` `"Hello,"``;``}` `const` `char` `*getWorld() {``return` `"World!"``;``}` `// 主函数``int` `main() {``// 调用两个函数并打印结果``const` `char` `*hello = getHello();``const` `char` `*world = getWorld();` `printf``(``"%s %s\n"``, hello, world);``return` `0;``}` |
|-|-|

生成LLVM IR(.ll)

| 1 | `clang` `-``emit``-``llvm` `-``S hello_test.c` `-``o hello_test.ll` |
|-|-|

opt使用md5-function-name-pass 优化 并导出优化后的ll文件

| 1234567891011121314151617 | `opt` `-``-``load``-``pass``-``plugin``=``.``/``cmake``-``build``-``debug``-``visual``-``studio``/``MD5FunctionNamePass.dll` `-``-``passes``=``md5``-``function``-``name``-``pass` `-``S hello_test.ll` `-``o hello_test_opt.ll` `MD5FunctionNamePass Plugin Loaded Successfully.``Skipping standard library function: sprintf``Skipping standard library function: vsprintf``Skipping comdat function: _snprintf``Skipping comdat function: _vsnprintf``Original Function Name: getHello``MD5` `Hash``:` `9d55bba9469f8ffcfe1202d85490c913``Original Function Name: getWorld``MD5` `Hash``: f612c236a8d854b3f6fa57efab4376d2``Skipping encryption` `for` `function: main``Skipping standard library function: printf``Skipping comdat function: _vsprintf_l``Skipping comdat function: _vsnprintf_l``Skipping comdat function: __local_stdio_printf_options``Skipping comdat function: _vfprintf_l` |
|-|-|

打开hello_test_opt.ll,发现函数名均被替换为md5值

![image](https://bbs.kanxue.com/upload/attach/202511/968342_A53ZV8VHCP9P8DQ.png)

## Clang使用自定义Pass

运行以下命令直接加载插件并应用于编译流程

这是老版本的传统方式,通过load加载任意llvm插件(包括pass,分析器等)

| 1 | `clang` `-``Xclang` `-``load` `-``Xclang MD5FunctionNamePass.dll hello.c` `-``o hello.exe` |
|-|-|

或者使用新版方式, 专门用于加载函数优化阶段的pass插件(FunctionPass)

| 1 | `clang` `-``Xclang` `-``fpass``-``plugin``=``MD5FunctionNamePass.dll hello.c` `-``o hello.exe` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202511/968342_H6PHDDWFMYU4CTX.png)

# 移植和使用 OLLVM

OLLVM（Obfuscator-LLVM）是基于 **LLVM 编译器框架** 的一个开源扩展项目，主要用于程序代码混淆与保护。

OLLVM 基于 LLVM 的 **Pass 插件机制** ，在优化环节增加 **代码混淆功能** ，从而增加二进制程序的逆向难度。

常见的混淆手段包括：

- 控制流平坦化（Control Flow Flattening）：打乱程序的控制流结构，使其执行路径不再直观。
- 指令替换（Instruction Substitution）：将简单指令替换为等价的复杂指令序列。
- 伪控制流（Bogus Control Flow）：引入大量无用的分支或跳转，干扰逆向分析。
- 字符串加密：防止敏感字符串在二进制中被直接提取。

OLLVM 项目地址：https://github.com/obfuscator-llvm/obfuscator

目前最新版本的是分支名为 llvm-4.0，基于 LLVM 团队发布的版本 4.0.1

## 移植OLLVM到LLVM19

### 获取Obfuscation

OLLVM 的核心代码在：**lib/Transforms/Obfuscation** 或 **lib/Passes/Obfuscation** 内

Initial LLVM and Clang 4.0 之外的都是基于 LLVM 4.0 改动过的代码

由于 obfuscator 中的代码已经 7 年多没有维护更新了，移植到 llvm19 变动太大, 故采用以下项目中的Obfuscation

参考 [移植到19.1.0所需要的diff文件](https://github.com/DreamSoule/ollvm17/issues/38) 末尾提供的Passes.zip, 其中包含了Obfuscation Pass文件

如果仅为使用OLLVM可参考以下项目:

- https://github.com/Haedus-Industries/ollvm-19 工具链和库文件更全面
- https://github.com/JiaPai12138/OLLVM-19 只有二进制文件

### 移植Obfuscation

首先复制Obfuscation文件夹到 LLVM 工程 llvm/lib/Passes/Obfuscation

![image](https://bbs.kanxue.com/upload/attach/202511/968342_4XHGB5AH2RVVPWH.png)

再修改llvm/lib/Passes/CMakeLists.txt, 添加Obfuscation相关的源文件

![image](https://bbs.kanxue.com/upload/attach/202511/968342_G5UUX4HZFW3FHWP.png)

之后编辑 llvm/lib/Passes/PassBuilder.cpp

先添加Obfuscation相关头文件和命令行支持

![image](https://bbs.kanxue.com/upload/attach/202511/968342_HCVAJQ25ECRH6Y2.png)

| 12345678910111213141516171819202122 | `// 导入 Obfuscation 相关头文件``#include "Obfuscation/BogusControlFlow.h" // 虚假控制流``#include "Obfuscation/Flattening.h"  // 控制流平坦化``#include "Obfuscation/SplitBasicBlock.h" // 基本块分割``#include "Obfuscation/Substitution.h" // 指令替换``#include "Obfuscation/StringEncryption.h" // 字符串加密``#include "Obfuscation/IndirectGlobalVariable.h" // 间接全局变量``#include "Obfuscation/IndirectBranch.h" // 间接跳转``#include "Obfuscation/IndirectCall.h" // 间接调用``#include "Obfuscation/Utils.h" // 为了控制函数名混淆开关 (bool obf_function_name_cmd;)`  `// 添加命令行支持``static` `cl::opt<``bool``> s_obf_split(``"split"``, cl::init(``false``), cl::desc(``"SplitBasicBlock: split_num=3(init)"``));``static` `cl::opt<``bool``> s_obf_sobf(``"sobf"``, cl::init(``false``), cl::desc(``"String Obfuscation"``));``static` `cl::opt<``bool``> s_obf_fla(``"fla"``, cl::init(``false``), cl::desc(``"Flattening"``));``static` `cl::opt<``bool``> s_obf_sub(``"sub"``, cl::init(``false``), cl::desc(``"Substitution: sub_loop"``));``static` `cl::opt<``bool``> s_obf_bcf(``"bcf"``, cl::init(``false``), cl::desc(``"BogusControlFlow: application number -bcf_loop=x must be x > 0"``));``static` `cl::opt<``bool``> s_obf_ibr(``"ibr"``, cl::init(``false``), cl::desc(``"Indirect Branch"``));``static` `cl::opt<``bool``> s_obf_igv(``"igv"``, cl::init(``false``), cl::desc(``"Indirect Global Variable"``));``static` `cl::opt<``bool``> s_obf_icall(``"icall"``, cl::init(``false``), cl::desc(``"Indirect Call"``));``static` `cl::opt<``bool``> s_obf_fn_name_cmd(``"fncmd"``, cl::init(``false``), cl::desc(``"use function name control obfuscation(_ + command + _ \| example: function_fla_bcf_)"``));` |
|-|-|

再注册obfuscation相关pass

![39-register-obfuscation-passes](https://bbs.kanxue.com/upload/attach/202511/968342_YP2B4DTP9C32E56.png)

| 12345678910111213141516171819202122232425 | `PassBuilder::PassBuilder( ... ) : ... {``...``// 注册 Obfuscation 相关 Pass``this``->registerPipelineStartEPCallback(``[](llvm::ModulePassManager &MPM,``llvm::OptimizationLevel Level) {``outs() <<` `"[OLLVM] run.PipelineStartEPCallback\n"``;``obf_function_name_cmd = s_obf_fn_name_cmd;``if` `(obf_function_name_cmd) {``outs() <<` `"[OLLVM] enable function name control obfuscation(_ + command + _ \| example: function_fla_)\n"``;``}``MPM.addPass(StringEncryptionPass(s_obf_sobf));` `// 先进行字符串加密 出现字符串加密基本块以后再进行基本块分割和其他混淆 加大解密难度``llvm::FunctionPassManager FPM;``FPM.addPass(IndirectCallPass(s_obf_icall));` `// 间接调用``FPM.addPass(SplitBasicBlockPass(s_obf_split));` `// 优先进行基本块分割``FPM.addPass(FlatteningPass(s_obf_fla));` `// 对于控制流平坦化``FPM.addPass(SubstitutionPass(s_obf_sub));` `// 指令替换``FPM.addPass(BogusControlFlowPass(s_obf_bcf));` `// 虚假控制流``MPM.addPass(createModuleToFunctionPassAdaptor(std::move(FPM)));``MPM.addPass(IndirectBranchPass(s_obf_ibr));` `// 间接指令 理论上间接指令应该放在最后``MPM.addPass(IndirectGlobalVariablePass(s_obf_igv));` `// 间接全局变量``MPM.addPass(RewriteSymbolPass());` `// 根据yaml信息 重命名特定symbols``}``);``}` |
|-|-|

### 编译OLLVM

进入build目录,重新配置cmake,主要是将构建类型设置为Release以节省空间

注: 使用OLLVM只需要Release模式编译即可, 移植OLLVM到NDK时也使用Release版clang

但后续调试obfuscation pass时仍需使用Debug模式编译

```
cmake -G "Ninja" -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="/utf-8" -DLLVM_ENABLE_RTTI=ON -DLLVM_ENABLE_EH=ON -DLLVM_ENABLE_PROJECTS="clang" ../llvm
```

ninja构建项目

| 1 | `ninja -j16` |
|-|-|

注意Debug模式编译可能遇到如下报错

| 12345 | `/``Users``/``orientalglass``/``Study``/``OLLVMStudy``/``attachents``/``llvm``-``project``/``llvm``/``lib``/``Passes``/``Obfuscation``/``compat``/``CallSite.h:``137``:``18``: error: no member named` `'isOpaqueOrPointeeTypeMatches'` `in` `'llvm::PointerType'``136` `\|` `assert``(cast<PointerType>(V``-``>getType())``\|            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~``137` `\|` `-``>isOpaqueOrPointeeTypeMatches(``\|` |
|-|-|

参考 [OLLVM19搭建](https://en.flyco.com/2025/04/25/OLLVM19%E6%9E%84%E5%BB%BA)

原因: API不兼容, 从 LLVM17 开始，引入了 强制启用不透明指针（opaque pointer）模型，并彻底移除了 PointerType 中对 pointee type 的直接访问接口，包括：getElementType()（17 中废弃） isOpaqueOrPointeeTypeMatches()（已移除）

手动修改源码，位置：~/llvm/lib/Passes/Obfuscation/compat/CallSite.h:137:18

| 1234567891011 | `#if LLVM_VERSION_MAJOR >= 15``assert``(cast<PointerType>(V->getType())``->isOpaqueOrPointeeTypeMatches(``cast<CallBase>(getInstruction())->getFunctionType()) &&``"New callee type does not match FunctionType on call"``);``#else``assert``(cast<PointerType>(V->getType())->getElementType() ==``cast<CallBase>(getInstruction())->getFunctionType() &&``"New callee type does not match FunctionType on call"``);``#endif``*getCallee() = V;` |
|-|-|

替换成如下代码即可解决：

| 12345678 | `// LLVM 17+ 使用 opaque pointer，不需要类型检查``#if LLVM_VERSION_MAJOR < 17``auto` `*PtrTy = cast<PointerType>(V->getType());``auto` `*FuncTy = cast<CallBase>(getInstruction())->getFunctionType();``assert``(PtrTy->getElementType() == FuncTy &&``"New callee type does not match FunctionType on call"``);``#endif``*getCallee() = V;` |
|-|-|

### 测试OLLVM

编写一个add.c的测试程序

| 123456789101112131415 | `#include <stdio.h>` `int` `main() {``int` `a = 1;``int` `b = 1;``int` `sum;` `// 执行加法运算``sum = a + b;` `// 输出运算结果``printf``(``"结果是: %d + %d = %d\n"``, a, b, sum);` `return` `0;``}` |
|-|-|

不使用ollvm编译的结果,结构较为简单清晰

| 1 | `clang add.c` `-``o add.exe` |
|-|-|

![42-ollvm-test-add](https://bbs.kanxue.com/upload/attach/202511/968342_7TTT7FN4HE3ZTVN.png)

使用ollvm 的sub即指令替换,并且loop=3

| 1 | `clang` `-``mllvm` `-``sub` `-``mllvm` `-``sub_loop``=``3` `add.c` `-``o add_sub_loop3.exe` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202511/968342_VMTBCGXKJDAAZKX.png)

可以发现汇编的运算指令膨胀了很多,不过ida的伪C代码仍然给出了优化后的结果

## Instructions Substitution

Instruction Substitution 是将一些常用的简单指令替换为具有等效逻辑但更加复杂的指令序列，从而提高代码逆向分析的难度。

使用 clang 编译时通过添加 -sub 参数启用指令替换功能, 通过-sub_loop参数指定替换次数

| 12 | `-``mllvm` `-``sub` `-``mllvm` `-``sub` `-``mllvm` `-``sub_loop``=``3` `启用指令替换功能，并对每个指令应用``3``次替换操作（默认为``1``次）` |
|-|-|

实现原理：

- 在 LLVM 的 Pass 管道中实现一个 Transformation Pass
- 遍历 IR 指令，将目标指令替换为复杂的等效指令序列

目前已实现加、减、与、或、异或指令的替换。比如加法运算 a + b：

替换为：a - (-b)

等价 LLVM IR 为：

| 1234 | `%``0` `=` `load i32``*` `%``a, align` `4`       `; 从指针` `%``a 加载一个` `32` `位整数到` `%``0``，``%``a 是一个` `4` `字节对齐的内存地址``%``1` `=` `load i32``*` `%``b, align` `4`       `; 从指针` `%``b 加载一个` `32` `位整数到` `%``1``，``%``b 是一个` `4` `字节对齐的内存地址``%``2` `=` `sub i32` `0``,` `%``1`               `; 计算` `0` `-` `%``1``，结果存储到` `%``2``，相当于取` `%``1` `的相反数（``-``b）``%``3` `=` `sub nsw i32` `%``0``,` `%``2`          `; 计算` `%``0` `-` `%``2``，结果存储到` `%``3``，其中 nsw（No Signed Wrap）指示结果不会发生有符号溢出` |
|-|-|

参考：[Instructions Substitution](https://github.com/obfuscator-llvm/obfuscator/wiki/Instructions-Substitution)

## Bogus Control Flow

Bogus Control Flow（BCF） 是 OLLVM（Obfuscation LLVM）的一种控制流混淆技术。

BCF 的核心思想是通过增加**虚假的分支语句**，构造看似复杂的控制流图（CFG），让逆向分析者难以理解程序的真实逻辑。这些分支通常通过难以猜测的条件判断来决定执行路径，但无论选择哪条路径，最终的逻辑都保持正确。

比如，未混淆的代码示例：

| 123 | `int` `add(``int` `a,` `int` `b) {``return` `a + b;``}` |
|-|-|

经过BCF混淆后可能有如下结构

| 1234567891011121314 | `int` `add(``int` `a,` `int` `b) {``int` `bogus_condition = (a ^ b) & 0x1;` `// 伪条件``if` `(bogus_condition) {``// 虚假路径``for` `(``int` `i = 0; i < 10; i++) {``a += i;` `// 无意义的计算``}``}` `else` `{``// 真正的逻辑``return` `a + b;``}``// 伪条件的控制下，总是返回正确的值``return` `a + b;``}` |
|-|-|

启用虚假控制流,并对一个函数应用 3 次虚假控制流转换,默认为1

| 1 | `clang` `-``mllvm` `-``bcf` `-``mllvm` `-``bcf_loop``=``3` |
|-|-|

启用虚假控制流，并以 40% 的概率对基本块进行混淆。默认值为 30%

| 1 | `clang` `-``mllvm` `-``bcf` `-``mllvm` `-``bcf_prob``=``40` |
|-|-|

控制流程图膨胀很多

![image](https://bbs.kanxue.com/upload/attach/202511/968342_X3KGZTGFTFXDH78.png)

## Control Flow Flattening

Control Flow Flattening（控制流平坦化）通过引入一个调度变量和统一的调度循环，将程序的所有基本块按编号管理，使用条件跳转动态调度执行顺序，从而隐藏原始控制流结构。

例如，原始代码如下

| 1234567 | `int` `calculate(``int` `x) {``if` `(x > 0) {``return` `x * 2;``}` `else` `{``return` `-x;``}``}` |
|-|-|

平坦化后的代码

| 1234567891011121314151617181920212223242526272829303132 | `int` `calculate(``int` `x) {``int` `dispatcher = 0;``int` `result = 0;` `while` `(1) {``switch` `(dispatcher) {``case` `0:` `// 起始块``if` `(x > 0) {``dispatcher = 1;` `// 跳转到正数处理``}` `else` `{``dispatcher = 2;` `// 跳转到负数处理``}``break``;` `case` `1:` `// 正数处理块``result = x * 2;``dispatcher = 3;` `// 跳转到结束块``break``;` `case` `2:` `// 负数处理块``result = -x;``dispatcher = 3;` `// 跳转到结束块``break``;` `case` `3:` `// 结束块``return` `result;` `default``:``return` `-1;` `// 错误路径``}``}``}` |
|-|-|

命令如下

| 123 | `clang` `-``mllvm` `-``fla` `# 启用控制流平坦化``clang` `-``mllvm` `-``fla` `-``mllvm` `-``split` `# 启用基本块拆分``clang` `-``mllvm` `-``fla` `-``mllvm` `-``split` `-``mllvm` `-``split_num``=``3` `# 指定对每个基本块拆分的次数,默认为1` |
|-|-|

分别只使用fla和split_num=3配合fla,结果如下

可以发现左边只使用fla的变化不大,因为没有分支语句,而右边使用split配合的流程图显然更复杂

所以一般使用split配合fla加强混淆效果

![image](https://bbs.kanxue.com/upload/attach/202511/968342_VR8YWCG7PUMCDUT.png)

# 集成 OLLVM 到 NDK

在 Android 应用安全中，**Native 层 so 库往往是最容易被逆向分析的目标** 。无论是游戏的核心逻辑，还是 App 的关键算法，一旦 so 被反编译，核心代码就可能暴露无遗。

传统的 Java 层混淆工具（如 ProGuard、R8）对 C/C++ 代码无能为力，因此 **NDK 层代码的保护** 成了安全加固中的难点。解决思路：**在编译阶段对 so 进行混淆处理** ，让逆向难度大幅提升。

在 Android 平台上，自 **NDK r18** 开始，Google 就全面弃用了 GCC，转而采用 **LLVM/Clang** 作为官方工具链。也就是说，所有的 C/C++ 代码编译、优化、生成 so 库的过程，底层都是由 LLVM 驱动完成的。

集成OLLVM到NDK后最终实现编译流程大概如下：

| 1234567891011121314151617181920212223242526 | `┌──────────────────┐``│   C` `/` `C``+``+` `源码    │``└────────┬─────────┘``│``▼``┌──────────────────┐``│   LLVM (Clang)   │  ← Android NDK 内置的官方编译器工具链``│   前端：生成 IR   │``└────────┬─────────┘``│ LLVM IR``▼``┌──────────────────┐``│    OLLVM Pass    │  ← 基于 LLVM 的扩展：混淆（控制流平坦化、指令替换等）``│   （插入在中间） │``└────────┬─────────┘``│ 混淆后的 IR``▼``┌──────────────────┐``│   LLVM 后端优化   │``│` `+` `代码生成      │``└────────┬─────────┘``│ 汇编``▼``┌──────────────────┐``│   链接生成 so     │ ← 最终供 Android 应用调用的 native 库``└──────────────────┘` |
|-|-|

对比 Android NDK 目录 toolchains\llvm\prebuilt\windows-x86_64 和 OLLVM的目录

其中主要几个文件夹：

- bin：包含可执行文件，例如编译器（clang、clang++）、链接器（ld）等，主要用于 NDK 工具链的操作。
- include：包含头文件，提供编译时所需的接口定义。例如，标准 C/C++ 库的头文件以及与 Android 平台相关的头文件。
- lib：包含静态库和动态库，提供编译和链接时使用的库文件。例如，支持标准 C/C++ 函数的实现库。

1. 粗略移植(不推荐)

只需要将OLLVM的bin, include, lib目录复制并替换NDK的对应目录即可移植

![image](https://bbs.kanxue.com/upload/attach/202511/968342_B67Z7P4UJEFYMRG.png)
2. 精细移植(推荐)

参考[Android逆向-ollvm-使用](https://juejin.cn/post/7349931303787216907)

将以下文件: clang, clang++, clang-format 移植到NDK的 "~\toolchains\llvm\prebuilt\windows-x86_64\bin" 目录内即可

如果编译时Android Studio提示找不到头文件,则从 "~\lib\clang\

## 创建Native测试工程

创建一个Android Native工程 OllvmNativeTest

编辑 local.properties 添加 ndk.dir 配置为 移植了ollvm的ndk 路径

![image](https://bbs.kanxue.com/upload/attach/202511/968342_AP8SM67ZH5XJUXT.png)

MainActivity.java

| 12345678910111213141516171819202122232425262728293031323334 | `package` `com.example.ollvm;` `import` `androidx.appcompat.app.AppCompatActivity;` `import` `android.os.Bundle;``import` `android.widget.TextView;` `import` `com.example.ollvm.databinding.ActivityMainBinding;` `public` `class` `MainActivity` `extends` `AppCompatActivity {` `// Used to load the 'ollvm' library on application startup.``static` `{``System.loadLibrary(``"ollvm"``);``}` `private` `ActivityMainBinding binding;` `public` `native` `int` `sub(``int` `a,``int` `b);``public` `native` `String bcf(String str);``public` `native` `String fla(``int` `x,``int` `y);``@Override``protected` `void` `onCreate(Bundle savedInstanceState) {``super``.onCreate(savedInstanceState);` `binding = ActivityMainBinding.inflate(getLayoutInflater());``setContentView(binding.getRoot());` `// Example of a call to a native method``TextView tv = binding.sampleText;``String result=sub(``9``,``3``)+bcf(``"Hello, OLLVM!"``)+fla(``1``,``2``);``tv.setText(result);``}``}` |
|-|-|

ollvm-lib.cpp

| 12345678910111213141516171819202122232425262728293031323334353637383940 | `#include <jni.h>``#include <string>``#include <sstream>` `// 测试sub, 整数相减``extern` `"C"``JNIEXPORT jint JNICALL``Java_com_example_ollvm_MainActivity_sub(JNIEnv *env, jobject thiz, jint a, jint b) {``return` `a-b;``}` `// 测试bcf, 接收字符串并返回拼接字符串``extern` `"C"``JNIEXPORT jstring JNICALL``Java_com_example_ollvm_MainActivity_bcf(JNIEnv *env, jobject thiz, jstring str) {``const` `char``* input=env->GetStringUTFChars(str, nullptr);``std::string result=std::string(``"BCF: "``)+input;``return` `env->NewStringUTF(result.c_str());``}` `// 测试fla, int相加判断大小``extern` `"C"``JNIEXPORT jstring JNICALL``Java_com_example_ollvm_MainActivity_fla(JNIEnv *env, jobject thiz, jint x, jint y) {``int` `sum = x + y;` `// 使用字符串流拼接结果``std::ostringstream result;` `if` `(sum < 5) {``result <<` `"x = "` `<< x <<` `", y = "` `<< y <<` `", x + y "` `<<` `"< 5"``;``}` `else` `if``(sum == 5){``result <<` `"x = "` `<< x <<` `", y = "` `<< y <<` `", x + y "` `<<` `"= 5"``;``}` `else``{``result <<` `"x = "` `<< x <<` `", y = "` `<< y <<` `", x + y "` `<<` `"> 5"``;``}` `// 返回拼接好的字符串``return` `env->NewStringUTF(result.str().c_str());``}` |
|-|-|

## 添加混淆配置

1. 全局混淆

编辑 CMakeLists.txt，添加如下配置启用 OLLVM 混淆

```
add_definitions("-mllvm -sub") # 全局启用指令替换
add_definitions("-mllvm -bcf") # 全局启用基本块控制流混淆
add_definitions("-mllvm -fla") # 全局启用控制流平坦化
```
2. 针对单个动态库混淆(无效)

```
target_compile_options(
    ollvm-lib
    PRIVATE
    -mllvm -bcf  # 启用 Bogus Control Flow 混淆
    -mllvm -sub  # 启用 Substitution 混淆
    -mllvm -fla  # 启用 Flattening 混淆
)
```

可以发现多个-mllvm被合并成一个

![image](https://bbs.kanxue.com/upload/attach/202511/968342_BQD4B68FKBV3FJ3.png)
3. 在CMakeLists.txt中, 通过CMAKE_FLAGS设置参数

```
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -mllvm -sub -mllvm -sub_loop=3 -mllvm -bcf -mllvm -bcf_loop=3 -mllvm -fla -mllvm -split -mllvm -split_num=3")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -mllvm -sub -mllvm -sub_loop=3 -mllvm -bcf -mllvm -bcf_loop=3 -mllvm -fla -mllvm -split -mllvm -split_num=3")
```
4. 在build.gradle中

严格按照android\defaultConfig\externalNativeBuild\cmake的层级目录

设置cppFlags传递ollvm参数

```
android {
    ......
    defaultConfig {
        ......
        externalNativeBuild {
            cmake {
                cppFlags '-mllvm -sub -mllvm -bcf'
            }
        }
    }
```

测试参数为混淆全开 (不包括indirect branch/call)

| 1 | `-mllvm -sub -mllvm -sub_loop=3 -mllvm -bcf -mllvm -bcf_loop=3 -mllvm -fla -mllvm -``split` `-mllvm -split_num=3` |
|-|-|

效果如下,简单的减法函数膨胀成900行伪代码以及复杂的流程图

![image](https://bbs.kanxue.com/upload/attach/202511/968342_ZNWVNMW4WUEMKG2.png)

# Obfuscation Pass

经过以上基础学习, 我们了解了LLVM和Pass相关概念, LLVM工具的使用, 移植编译OLLVM 以及集成到 NDK

接下来阅读各混淆Pass的源码深入理解其原理, 同时分析测试代码混淆前后的IR变化加强理解

注意:

- 以下分析和调试均使用Debug版的OLLVM, 注意使用CLion配置时可能需要重新编译
- 有前文未提到的Indirect Branch/Call 混淆, 对应混淆参数分别为-ibr和-icall

## 调试Pass

编译clang后,实际上opt用于调用pass处理IR,所以obfuscation pass被集成在opt中

通过opt --help可以查询支持哪些obfuscation pass参数

![image](https://bbs.kanxue.com/upload/attach/202511/968342_ZCSWVU5ZEQVYK77.png)

调试方法:

1. 先修改obfuscation, 为pass添加打印语句
2. 再调试opt并通过参数调用指定pass

### 打印函数

PrintUtils.h

| 1234567891011121314 | `#ifndef PRINT_UTILS_H``#define PRINT_UTILS_H` `#include "llvm/IR/Function.h"``#include "llvm/IR/BasicBlock.h"``#include "llvm/IR/Instruction.h"``#include "llvm/Support/raw_ostream.h"` `using` `namespace` `llvm;` `void` `printInstruction(Instruction& inst);``void` `printBasicBlock(BasicBlock& BB);``void` `printFunction(Function& func);``#endif` |
|-|-|

PrintUtils.cpp

| 12345678910111213141516 | `#include "PrintUtils.h"``// 打印指令内容``void` `printInstruction(Instruction& inst) {``inst.print(outs());``outs()<<``"\n"``;``}``// 打印基本块内容``void` `printBasicBlock(BasicBlock& BB) {``BB.print(outs());``outs()<<``"\n"``;``}``// 打印函数内容``void` `printFunction(Function& func) {``func.print(outs());``outs()<<``"\n"``;``}` |
|-|-|

修改llvm/lib/Passes/CMakeLists.txt, 添加PrintUtils.cpp到项目中

![image](https://bbs.kanxue.com/upload/attach/202511/968342_8MRQ89NS8VF86QR.png)

之后在需要调试的pass中添加代码即可, 以Substitution.cpp为例:

- 通过函数名匹配main函数并打印
- 执行混淆时打印被混淆的指令及其所属基本块(混淆前后各打印一次)

![image](https://bbs.kanxue.com/upload/attach/202511/968342_W6JC94VGBU2ACTD.png)

### 通过opt调试pass

由于pass不能单独执行, 且pass被集成到opt中, 所以需要使用CLion调试opt从而调试pass

注意: opt优化的是IR文件, 所以要先生成IR文件才能调试, 参考前文脱离LLVM源码编译Pass中提到的optnone问题

使用以下命令编译源文件得到的IR文件才能正常用于opt优化调试

| 1 | `clang -Xclang -disable-O0-optnone -emit-llvm -S main.c -o main.ll` |
|-|-|

之后在obfuscation对应pass源码中断点, 设置参数优化IR文件以调试opt

注意参数中一定要传递"-On" 其中n=0~3, 优化力度依次增加, 如果不传递该参数则不会调用pass优化

例如使用以下参数进行优化

| 1 | `opt -O0 --sub add.ll -S -o add_opt_test.ll` |
|-|-|

实际调试时修改opt参数参考如下:

例如调试bcf时指定bcf_loop=1时的调试参数

| 1234567 | `-O0``-S``--bcf``--bcf_loop=1``E:\KnowledgeRepository\Study\OLLVMStudy\attachments\OllvmTest\bogus_control_flow_test\bogus_control_flow_test.ll``-o``E:\KnowledgeRepository\Study\OLLVMStudy\attachments\OllvmTest\bogus_control_flow_test\bogus_control_flow_test_result.ll` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202511/968342_KVEY992AUNJSFKZ.png)

## Instructions Substitution

功能: 将单个二进制运算指令(加减乘除,位运算等)替换为等价指令序列

### Instructions Substitution 关键流程

1. SubstitutionPass::run

pass的入口函数,检查剩余混淆次数以及是否需要进行混淆

调用SubstitutionPass::substitute执行具体混淆操作
2. SubstitutionPass::substitute

对传入的函数循环进行ObfTimes次混淆操作

第一层for循环遍历Funciton的每个BasicBlock

第二层for循环遍历BasicBlock的每个Instruction

当指令为BinaryOperator时, switch判断指令具体类型并调用随机混淆函数
3. 混淆函数 如SubstitutionPass::addNeg

生成等价指令序列并替换原始指令

![image](https://bbs.kanxue.com/upload/attach/202511/968342_FFARSNV5NSNB3KK.png)

### SubstitutionPass::run

pass的入口函数, 检查剩余混淆次数后调用substitute函数执行sub混淆

| 12345678910111213141516 | `PreservedAnalyses SubstitutionPass::run(Function &F, FunctionAnalysisManager &AM) {``// 检查混淆次数``if` `(ObfTimes <= 0) {``errs() <<` `"Substitution application number -sub_loop=x must be x > 0"``;``return` `PreservedAnalyses::all();``}` `Function *tmp = &F;``// 执行sub混淆``if` `(toObfuscate(flag, tmp,` `"sub"``)) {``substitute(tmp);``return` `PreservedAnalyses::none();``}` `return` `PreservedAnalyses::all();``}` |
|-|-|

### SubstitutionPass::substitute

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546 | `bool` `SubstitutionPass::substitute(Function *f) {``Function *tmp = f;` `// 设置sub混淆循环次数,和sub_loop对应``int` `times = ObfTimes;``do` `{``// 遍历Function的每个BasicBlock``for` `(Function::iterator bb = tmp->begin(); bb != tmp->end(); ++bb) {``// 遍历每个BasicBlock的每条Instruction``for` `(BasicBlock::iterator inst = bb->begin(); inst != bb->end(); ++inst) {``// 如果是二进制操作指令(加减乘除,位运算等)则执行混淆``if` `(inst->isBinaryOp()) {``//打印混淆前的IR``//errs()<<"Current opcode: ";inst->print(errs());errs()<<"\n";``//errs()<<"Before optimiser:\n";``//printBasicBlockInfo(bb);` `//判断操作码类型并进行对应的混淆处理``switch` `(inst->getOpcode()) {``case` `BinaryOperator::Add:``// 匹配到Add指令, 从funcAdd函数指针数组中,随机选择一个混淆函数执行sub``// 参数为BinaryOperator 即``(``this``->*funcAdd[llvm::cryptoutils->get_range(NUMBER_ADD_SUBST)])(``cast<BinaryOperator>(inst));``++Add;``break``;``case` `BinaryOperator::Sub:``// case BinaryOperator::FSub:``// Substitute with random sub operation``(``this``->*funcSub[llvm::cryptoutils->get_range(NUMBER_SUB_SUBST)])(``cast<BinaryOperator>(inst));``++Sub;``break``;``// other cases ......``default``:``break``;``}` `// End switch``//打印混淆后的IR``//errs()<<"After optimiser:\n";``//printBasicBlockInfo(bb);``}` `// End isBinaryOp``}` `// End for basickblock``}` `// End for Function``}` `while` `(--times > 0);` `// for times``return` `false``;``}` |
|-|-|

### SubstitutionPass

该类定义在Substitution.h中, 可以发现Add指令有7种混淆函数

| 1234567891011121314151617181920212223242526272829303132 | `#define NUMBER_ADD_SUBST 7``#define NUMBER_SUB_SUBST 6``#define NUMBER_AND_SUBST 6``#define NUMBER_OR_SUBST 6``#define NUMBER_XOR_SUBST 6``#define NUMBER_MUL_SUBST 2` `namespace` `llvm {``class` `SubstitutionPass :` `public` `PassInfoMixin<SubstitutionPass> {``public``:``bool` `flag;``void` `(SubstitutionPass::*funcAdd[NUMBER_ADD_SUBST])(BinaryOperator *bo);``void` `(SubstitutionPass::*funcSub[NUMBER_SUB_SUBST])(BinaryOperator *bo);``void` `(SubstitutionPass::*funcAnd[NUMBER_AND_SUBST])(BinaryOperator *bo);``void` `(SubstitutionPass::*funcOr[NUMBER_OR_SUBST])(BinaryOperator *bo);``void` `(SubstitutionPass::*funcXor[NUMBER_XOR_SUBST])(BinaryOperator *bo);``void` `(SubstitutionPass::*funcMul[NUMBER_MUL_SUBST])(BinaryOperator *bo);` `//added for hikari` `SubstitutionPass(``bool` `flag) {``this``->flag = flag;``funcAdd[0] = &SubstitutionPass::addNeg;``funcAdd[1] = &SubstitutionPass::addDoubleNeg;``funcAdd[2] = &SubstitutionPass::addRand;``funcAdd[3] = &SubstitutionPass::addRand2;``funcAdd[4] = &SubstitutionPass::addSubstitution;``funcAdd[5] = &SubstitutionPass::addSubstitution2;``funcAdd[6] = &SubstitutionPass::addSubstitution3;` `// ...... other substitution passes` `}``// ......``}` |
|-|-|

### SubstitutionPass::addNeg

以addNeg为例, 其将 a=b+c 替换为 a = b - (-c)

| 123456789101112131415161718192021222324252627 | `// Implementation of a = b - (-c)``void` `SubstitutionPass::addNeg(BinaryOperator *bo) {``// 创建临时BinaryOperator, 用于后续创建混淆指令``BinaryOperator *op = NULL;` `// 判断指令类型是否为Add``if` `(bo->getOpcode() == Instruction::Add) {``// 创建bo指令中操作数1的相反数, b为操作数0, c为操作数1, 即创建 -c``op = BinaryOperator::CreateNeg(bo->getOperand(1),` `""``, bo);``// 创建Sub指令, 操作数0指定为bo指令的操作数0, 操作数1指定为刚创建的-c``// 即创建了Sub b, -c``op = BinaryOperator::Create(Instruction::Sub, bo->getOperand(0), op,` `""``, bo);` `// Check signed wrap``//op->setHasNoSignedWrap(bo->hasNoSignedWrap());``//op->setHasNoUnsignedWrap(bo->hasNoUnsignedWrap());` `// 用创建的op指令替换原来的bo指令 即将Add b, c 替换为 Sub b, -c``bo->replaceAllUsesWith(op);``}``// 若不为Add则跳过,不执行混淆``/* else {``op = BinaryOperator::CreateFNeg(bo->getOperand(1), "", bo);``op = BinaryOperator::Create(Instruction::FSub, bo->getOperand(0), op, "",``bo);``}*/``}` |
|-|-|

### Substitution 效果分析

#### 测试代码

测试代码add.c

| 123456789101112131415 | `#include <stdio.h>` `int` `main() {``int` `a = 1;``int` `b = 1;``int` `sum;` `// 执行加法运算``sum = a + b;` `// 输出运算结果``printf``(``"结果是: %d + %d = %d\n"``, a, b, sum);` `return` `0;``}` |
|-|-|

#### main IR

对应add.ll main (未调用sub)

不难看出 %0=a, %1=b, %sum=%add=%0+%1

| 1234567891011121314151617181920 | `; Function Attrs:` `noinline` `nounwind optnone uwtable``define dso_local i32 @main() #0 {``entry:``%retval = alloca i32, align 4``%a = alloca i32, align 4``%b = alloca i32, align 4``%sum = alloca i32, align 4``store i32 0, ptr %retval, align 4``store i32 1, ptr %a, align 4``store i32 1, ptr %b, align 4``%0 = load i32, ptr %a, align 4``%1 = load i32, ptr %b, align 4``%add = add nsw i32 %0, %1``store i32 %add, ptr %sum, align 4``%2 = load i32, ptr %sum, align 4``%3 = load i32, ptr %b, align 4``%4 = load i32, ptr %a, align 4``%call = call i32 (ptr, ...) @``printf``(ptr noundef @``"??_C@_0BJ@JAMMOFDE@?g?$LL?$JD?f?$JO?$JM?f?$JI?$KP?3?5?$CFd?5?$CL?5?$CFd?5?$DN?5?$CFd?6?$AA@"``, i32 noundef %4, i32 noundef %3, i32 noundef %2)``ret i32 0``}` |
|-|-|

混淆后add_opt_sub.ll

%0=a, %1=b,

%2=%0+730782619

%3=%2+%1

%4=%3-730782619

%sum=%4

即%sum=%4=%3-730782619=%2+%1-730782619=%0+730782619+%1-730782619=%0+%1=a+b

其中指令 %add = add nsw i32 %0, %1 不影响后续结果, 故没有作用从而成为了死代码

| 1234567891011121314151617181920212223 | `; Function Attrs:` `noinline` `nounwind optnone uwtable``define dso_local i32 @main() #0 {``entry:``%retval = alloca i32, align 4``%a = alloca i32, align 4``%b = alloca i32, align 4``%sum = alloca i32, align 4``store i32 0, ptr %retval, align 4``store i32 1, ptr %a, align 4``store i32 1, ptr %b, align 4``%0 = load i32, ptr %a, align 4``%1 = load i32, ptr %b, align 4``%2 = add i32 %0, 730782619``%3 = add i32 %2, %1``%4 = sub i32 %3, 730782619``%add = add nsw i32 %0, %1``store i32 %4, ptr %sum, align 4``%5 = load i32, ptr %sum, align 4``%6 = load i32, ptr %b, align 4``%7 = load i32, ptr %a, align 4``%call = call i32 (ptr, ...) @``printf``(ptr noundef @``"??_C@_0BJ@JAMMOFDE@?g?$LL?$JD?f?$JO?$JM?f?$JI?$KP?3?5?$CFd?5?$CL?5?$CFd?5?$DN?5?$CFd?6?$AA@"``, i32 noundef %7, i32 noundef %6, i32 noundef %5)``ret i32 0``}` |
|-|-|

显然插入了以下3条指令

| 123 | `%``2` `=` `add i32` `%``0``,` `730782619``%``3` `=` `add i32` `%``2``,` `%``1``%``4` `=` `sub i32` `%``3``,` `730782619` |
|-|-|

## SplitBasicBlocks

功能: 随机选取分割点,将函数的每个基本块分割为多个小基本块, 小基本块间用分支指令br连接

### Split BasicBlocks 关键流程

Split Basic Blocks 的流程比较简单,实际上只需要重点关注SplitBasicBlockPass::split即可

分割基本块最终通过调用API函数BasicBlock::splitBasicBlock实现

![SplitBasicBlock](https://bbs.kanxue.com/upload/attach/202511/968342_V8DSSWCTAWP39GU.png)

### SplitBasicBlockPass::run

| 12345678910 | `PreservedAnalyses SplitBasicBlockPass::run(Function& F, FunctionAnalysisManager& AM) {``Function *tmp = &F;` `// 传入的Function``if` `(toObfuscate(flag, tmp,` `"split"``)){` `// 判断什么函数需要开启混淆``errs() <<` `"run split on function "``<<F.getName() <<``"\n"``;``split(tmp);` `// 分割流程``++Split;` `// 计次``return` `PreservedAnalyses::none();``}``return` `PreservedAnalyses::all();``}` |
|-|-|

### SplitBasicBlockPass::split

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455 | `void` `SplitBasicBlockPass::split(Function *f){``std::vector<BasicBlock *> origBB;``// 1. 保存所有基本块``for` `(Function::iterator I = f->begin(), IE = f->end(); I != IE; ++I){``origBB.push_back(&*I);``}``// 2. 遍历origBB保存的函数的全部基本块``for` `(std::vector<BasicBlock *>::iterator I = origBB.begin(), IE = origBB.end();I != IE; ++I){``BasicBlock *curr = *I;` `// 当前基本块的某条指令``int` `splitN = SplitNum;` `// 对应split_num参数, 指定对于每个基本块分割的节点数``// 不分割只有一条指令的基本块且不可分割含有PHI指令的基本块``if` `(curr->size() < 2 \|\| containsPHI(curr)){``//outs() << "\033[0;33mThis BasicBlock is lower then two or had PIH Instruction!\033[0m\n";``continue``;``}``// 检查splitN和基本块大小``// 如果传入的分割块数大于等于基本块自身大小 则修改分割数为基本块大小减一``if` `((``size_t``)splitN >= curr->size()){``splitN = curr->size() - 1;``}` `// 3. 创建分割点数组 分割点对应每2条指令间的空隙``// 例如指令0和指令1之间,可以在指令0之后,指令1之前进行分割, 所以1便是分割点``std::vector<``int``> test;``for` `(unsigned i = 1; i < curr->size(); ++i){``test.push_back(i);` `// 分割点的范围[1,基本块大小-1]``}` `// 4. 打乱分割点并通过排序选取分割点``if` `(test.size() != 1){``shuffle(test);` `// 打乱分割点``// 对前splitN个分割点排序(从小到大), 用于按顺序分割, 防止乱序导致出错(前驱指令可能影响后继指令)``// 排序后选取前splitN个分割点``std::sort(test.begin(), test.begin() + splitN);` `}``// 4. 分割当前基本块``BasicBlock::iterator it = curr->begin();` `//当前指令``BasicBlock *toSplit = curr;` `//当前基本块``int` `last = 0;` `//记录上一条分割点位置``// 对当前基本块分割split_num次``for` `(``int` `i = 0; i < splitN; ++i){``// 如果当前基本块只有1条指令则不分割``if` `(toSplit->size() < 2){``continue``;``}``// 通过分割点数组保存的偏移, 定位到分割点位 test[i] - last 即两条分割点之间的偏移值``for` `(``int` `j = 0; j < test[i] - last; ++j){``++it;``}``last = test[i];` `// 上一条分割点``// 在分割点指令处分割基本块 获取基本块名称添加.split后缀作为分割后的新块名``toSplit = toSplit->splitBasicBlock(it, toSplit->getName() +` `".split"``);``}``++Split;``}``}` |
|-|-|

### SplitBasicBlockPass::shuffle

通过随机数作为索引,交换元素顺序打乱数组

| 123456 | `void` `SplitBasicBlockPass::shuffle(std::vector<``int``> &vec){``int` `n = vec.size();``for` `(``int` `i = n - 1; i > 0; --i){``std::swap(vec[i], vec[cryptoutils->get_uint32_t() % (i + 1)]);``}``}` |
|-|-|

### BasicBlock::splitBasicBlock

| 1234567891011121314151617181920212223242526272829303132 | `BasicBlock *BasicBlock::splitBasicBlock(iterator I,` `const` `Twine &BBName,``bool` `Before) {``if` `(Before)``return` `splitBasicBlockBefore(I, BBName);` `assert``(getTerminator() &&` `"Can't use splitBasicBlock on degenerate BB!"``);``assert``(I != InstList.end() &&``"Trying to get me to create degenerate basic block!"``);` `// 1.创建新的基本块 并插入下一基本块的前方 (即当前基本块后方, 插入2块基本块之间)``// this指针指向了当前指令所属的基本块``BasicBlock *New = BasicBlock::Create(getContext(), BBName, getParent(),``this``->getNextNode());` `// 保存分割点处的调试信息``DebugLoc Loc = I->getStableDebugLoc();``// 2. 将当前基本块的指令从I到end, 移动到新基本块中``New->splice(New->end(),` `this``, I, end());` `// 3. 在当前基本块的末尾添加branch分支指令, 跳转到新基本块中``BranchInst *BI = BranchInst::Create(New,` `this``);``BI->setDebugLoc(Loc);` `// 此处有疑问: 当前基本块的I-end指令是否需要删除?` `// Now we must loop through all of the successors of the New block (which``// _were_ the successors of the 'this' block), and update any PHI nodes in``// successors.  If there were PHI nodes in the successors, then they need to``// know that incoming branches will be from New, not from Old (this).``// 4. 处理后继块PHI节点``New->replaceSuccessorsPhiUsesWith(``this``, New);``return` `New;``}` |
|-|-|

### PHI Node

上述代码中调用了SplitBasicBlockPass::containsPHI判断基本块中是否包含PHI指令

| 12345678 | `bool` `SplitBasicBlockPass::containsPHI(BasicBlock *BB){``for` `(Instruction &I : *BB){``if` `(isa<PHINode>(&I)){``return` `true``;``}``}``return` `false``;``}` |
|-|-|

参考 [SSA Form and PHI Nodes](https://www.llvmpy.org/llvmpy-doc/dev/doc/llvm_concepts.html)

所有 LLVM 指令以静态单一赋值形式（SSA）表示 。本质上，这意味着任何变量只能被赋值一次。

单次赋值的结果就是 PHI (Φ) 节点。当变量可以根据控制流路径被赋值时，这些节点则是必需的。

例如有下列代码:

| 1234 | `a = 1;``if` `(v < 10)``a = 2;``b = a;` |
|-|-|

假设v<10, a会被再次赋值为2, 由于SSA性质, a已经被赋值一次, 所以不能继续赋值

LLVM中通过PHI Node解决该问题, 用于**基本块之间的分支和合并**, 当一个基本块有多个前驱基本块时, PHI Node可用于表示从不同前驱基本块中接收的值

以上代码会被转换为如下形式:

| 1234 | `a1 = 1;``if` `(v < 10)``a2 = 2;``b = PHI(a1, a2);` |
|-|-|

PHI 节点根据控制流到达 PHI 节点的位置选择 a1 或 a2 。

PHI 节点的参数 a1 与块 “a1 = 1;” 相关联，而 a2 与块 “a2 = 2;” 相关联。

PHI 节点必须在 LLVM IR 中显式创建, 因此, LLVM 指令集有一条名为 phi 的指令

关于如何处理后继基本块,感兴趣的师傅可以深入了解

总的操作是将后继基本块中PHI Nodes的前驱基本块由当前基本块转换为新基本块, 调用链如下:

### BasicBlock::replaceSuccessorsPhiUsesWith

| 12345678910 | `void` `BasicBlock::replaceSuccessorsPhiUsesWith(BasicBlock *Old,``BasicBlock *New) {``Instruction *TI = getTerminator();``if` `(!TI)``// Cope with being called on a BasicBlock that doesn't have a terminator``// yet. Clang's CodeGenFunction::EmitReturnBlock() likes to do this.``return``;``for` `(BasicBlock *Succ : successors(TI))``Succ->replacePhiUsesWith(Old, New);``}` |
|-|-|

### BasicBlock::replacePhiUsesWith

| 12345678910 | `void` `BasicBlock::replacePhiUsesWith(BasicBlock *Old, BasicBlock *New) {``// N.B. This might not be a complete BasicBlock, so don't assume``// that it ends with a non-phi instruction.``for` `(Instruction &I : *``this``) {``PHINode *PN = dyn_cast<PHINode>(&I);``if` `(!PN)``break``;``PN->replaceIncomingBlockWith(Old, New);``}``}` |
|-|-|

### Instructions::replaceIncomingBlockWith

| 1234567891011 | `/// Replace every incoming basic block \p Old to basic block \p New.``void` `replaceIncomingBlockWith(``const` `BasicBlock *Old, BasicBlock *New) {``assert``(New && Old &&` `"PHI node got a null basic block!"``);``for` `(unsigned Op = 0, NumOps = getNumOperands(); Op != NumOps; ++Op)``if` `(getIncomingBlock(Op) == Old)``setIncomingBlock(Op, New);``}` `void` `setIncomingBlock(unsigned i, BasicBlock *BB) {``const_cast``<block_iterator>(block_begin())[i] = BB;``}` |
|-|-|

### SplitBasicBlocks 效果分析

#### 测试代码

| 12345 | `#include<stdio.h>``int` `main(){``printf``(``"Hello, Split Basic Block!\n"``);``return` `0;``}` |
|-|-|

#### main IR

混淆前

| 12345678 | `; Function Attrs: noinline nounwind uwtable``define dso_local i32 @main()` `#0 {``entry:``%``retval` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retval, align` `4``%``call` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_0BL@MDKBAEJA@Hello?0?5Split?5Basic?5Block?$CB?6?$AA@"``)``ret i32` `0``}` |
|-|-|

混淆后

| 1234567891011121314151617 | `; Function Attrs: noinline nounwind uwtable``define dso_local i32 @main()` `#0 {``entry:``%``retval` `=` `alloca i32, align` `4``br label` `%``entry.split` `entry.split:                                      ; preds` `=` `%``entry``store i32` `0``, ptr` `%``retval, align` `4``br label` `%``entry.split.split` `entry.split.split:                                ; preds` `=` `%``entry.split``%``call` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_0BL@MDKBAEJA@Hello?0?5Split?5Basic?5Block?$CB?6?$AA@"``)``br label` `%``entry.split.split.split` `entry.split.split.split:                          ; preds` `=` `%``entry.split.split``ret i32` `0``}` |
|-|-|

经过SplitBasicBlocks后, 原来1个基本块被分割为4个基本块

基本块名称依次添加.split后缀, 它们之间通过br指令连接, 指令流原始执行顺序并未改变

## Control Flow Flattening

功能: 重整基本块关系, 将控制流由垂直转为平坦化

### Control Flow Flattening 关键流程

![ControlFlowFlattening](https://bbs.kanxue.com/upload/attach/202511/968342_32PB3Q2G5VK4R3S.png)

### Flattening::flatten

先学习简单的旧版flatten函数

参考[[原创] OLLVM 攻略笔记](https://bbs.kanxue.com/thread-286256.htm) 中https://github.com/amimo/goron的flatten

关键步骤:

1. 将函数中的switch结构转换为if-else结构简化控制流,保证平坦化后只有一个主switch结构
2. 存储所有基本块到oriBB, 若遇到异常处理调用指令invoke则终止平坦化
3. 从oriBB中删除entry块, 并单独处理entry块

如果entry块以条件分支结束且有多个后继块则进行分割

无论如何都去除entry块的终止指令
4. 创建并初始化switchVar变量, 该变量用于存储switch的条件值
5. 创建控制流平坦化的循环结构
6. 创建主switch指令
7. 将所有原始基本块整合到主switch中
8. 修复栈结构,优化switch结构

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105 | `bool` `Flattening::flatten(Function *f) {``vector<BasicBlock *> origBB;` `// 存储原始基本块``BasicBlock *loopEntry;` `// 进入循环的基本块``BasicBlock *loopEnd;` `// 退出循环的基本块``LoadInst *load;` `// switch 变量的加载指令``SwitchInst *switchI;` `// switch 指令``AllocaInst *switchVar;` `// switch 变量的存储位置` `// 生成16字节随机加扰密钥``char` `scrambling_key[16];``llvm::cryptoutils->get_bytes(scrambling_key, 16);` `// 适配不同 LLVM 版本选取API` `#if LLVM_VERSION_MAJOR * 10 + LLVM_VERSION_MINOR >= 90``FunctionPass *lower = createLegacyLowerSwitchPass();``#else``FunctionPass *lower = createLowerSwitchPass();``#endif``// 1. 将函数中的switch结构转换为if-else结构,简化控制流,保证平坦化后只有一个主switch结构``lower->runOnFunction(*f);`  `// 2. 遍历所有基本块并存储到 origBB``for` `(Function::iterator i = f->begin(); i != f->end(); ++i) {``BasicBlock *tmp = &*i;` `// 当前基本块指针``origBB.push_back(tmp);``if` `(isa<InvokeInst>(tmp->getTerminator())) {``return` `false``;` `// 遇到涉及异常处理的 invoke 指令,直接终止平坦化混淆``}``}` `// 基本块数量小于等于1则无需平坦化``if` `(origBB.size() <= 1) {``return` `false``;``}` `LLVMContext &Ctx = f->getContext();` `// 获取 LLVM 上下文` `// IPO(过程间混淆) 相关处理, 获取密钥值``const` `IPObfuscationContext::IPOInfo *SecretInfo = nullptr;``if` `(IPO) {``SecretInfo = IPO->getIPOInfo(f);` `// 获取 IPO 相关信息``}``// 若启用了IPO则使用IPO提供的秘钥,否则默认为0``Value *MySecret = SecretInfo ? SecretInfo->SecretLI : ConstantInt::get(Type::getInt32Ty(Ctx), 0);` `// 移除第一个基本块 (通常为函数入口块entry)``// 入口块entry需要特殊处理不能放到switch中``origBB.erase(origBB.begin());` `// 3. 处理第一个基本块，确保其可以被 switch 控制``Function::iterator tmp = f->begin();``BasicBlock *insert = &*tmp;``// 如果entry块以条件分支结束且有多个后继块(>1)则进行分割``if` `(isa<BranchInst>(insert->getTerminator()) && insert->getTerminator()->getNumSuccessors() > 1) {``BasicBlock::iterator i = insert->end();` `// 获取终止指令迭代器``--i;` `// 移动到终止指令的前一条指令``// 如果entry块包含多条指令则继续前移``if` `(insert->size() > 1) {``--i;``}``// 在指定位置分割entry块, 创建新的基本块first``BasicBlock *tmpBB = insert->splitBasicBlock(i,` `"first"``);``// 将新分割的块添加到原始基本块列表开头``// 即填补原entry块的位置,entry块本身不可加入switch,但分割后的first块可以``origBB.insert(origBB.begin(), tmpBB);``}``insert->getTerminator()->eraseFromParent();` `// 移除entry块的终止指令,为后续构建新控制流准备` `// 4. 创建并初始化switchVar变量 注意不是switch指令,是switch的条件值变量``// 创建 switchVar 控制变量 用于决定执行哪个基本块 entry作为dispatcher?``switchVar =` `new` `AllocaInst(Type::getInt32Ty(f->getContext()), 0,` `"switchVar"``, insert);``// 初始化switchVar变量为加密后的0值,使用scramble32对0进行加密``new` `StoreInst(ConstantInt::get(Type::getInt32Ty(f->getContext()), llvm::cryptoutils->scramble32(0, scrambling_key)), switchVar, insert);` `// 5. 创建控制流平坦化的循环结构``loopEntry = BasicBlock::Create(f->getContext(),` `"loopEntry"``, f, insert);` `// 循环入口,包含switch指令``loopEnd = BasicBlock::Create(f->getContext(),` `"loopEnd"``, f, insert);` `// 循环出口,跳转回入口``load =` `new` `LoadInst(switchVar,` `"switchVar"``, loopEntry);` `// 在循环入口加载switch变量值``insert->moveBefore(loopEntry);` `// 调整基本块顺序,将entry块移动到循环入口前``BranchInst::Create(loopEntry, insert);` `// 创建分支指令,entry块跳转到循环入口``BranchInst::Create(loopEntry, loopEnd);` `// 创建分支指令,循环结束跳转回循环入口` `// 6. 创建主switch指令``// 创建switch的default块, 无匹配case时执行``BasicBlock *swDefault = BasicBlock::Create(f->getContext(),` `"switchDefault"``, f, loopEnd);``BranchInst::Create(loopEnd, swDefault);` `// 创建分支指令,default块跳转到循环结束``// 创建switch指令 参数: 条件值, 默认块, 预估case数, 插入位置``// 即在loopEntry后插入switch, 条件为循环入口加载的switchVar``switchI = SwitchInst::Create(load, swDefault, 0, loopEntry);` `// 7. 将原始基本块整合到主switch结构中``for` `(BasicBlock *bb : origBB) {``bb->moveBefore(loopEnd);` `// 将基本块移动到循环结束块前方``// 为当前基本块生成加密的case值,使用scramble32对case编号加密``ConstantInt *numCase = ConstantInt::get(switchI->getCondition()->getType(), llvm::cryptoutils->scramble32(switchI->getNumCases(), scrambling_key));``switchI->addCase(numCase, bb);` `// 将基本块添加到switch的case列表中``}` `// 8. 修复和优化``fixStack(f);` `// 修复栈结构,保证栈平衡``lower->runOnFunction(*f);` `// 再次运行createLowerSwitchPass, 优化switch结构``delete` `lower;` `return` `true``;``}` |
|-|-|

### FlatteningPass::run

| 1234567891011121314 | `PreservedAnalyses FlatteningPass::run(Function& F, FunctionAnalysisManager& AM) {``Function *tmp = &F;` `// 传入的Function``// 判断是否需要开启控制流平坦化``if` `(toObfuscate(flag, tmp,` `"fla"``)) {``INIT_CONTEXT(F);``// outs()<<"[Soule] debug. "<< F.getName()<<" \n";``if` `(flatten(tmp)) {``++Flattened;``}``return` `PreservedAnalyses::none();``}``return` `PreservedAnalyses::all();` `}` |
|-|-|

### FlatteningPass::flatten

新版flatten函数和旧版在整体结构上基本一致, 细节略有区别, 代码量加倍

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220 | `bool` `FlatteningPass::flatten(Function *f) {` `SmallVector<BasicBlock *, 8> origBB;` `// 原始基本块列表``BasicBlock *loopEntry, *loopEnd;` `// 循环入口和结束块``LoadInst *load;` `// switch变量的加载指令``SwitchInst *switchI;` `// switch指令``AllocaInst *switchVar, *switchVarAddr;``// switch变量和switch变量地址``const` `DataLayout &DL = f->getParent()->getDataLayout();` `// 获取DataLayout用于平台无关的内存布局计算` `// 加扰秘钥 SCRAMBLER``std::unordered_map<uint32_t, uint32_t> scrambling_key;` `// END OF SCRAMBLER` `// 使用新版PassManager``// 创建Pass构建器, 函数分析管理器, 函数pass管理器并注册``PassBuilder PB;``FunctionAnalysisManager FAM;``FunctionPassManager FPM;``PB.registerFunctionAnalyses(FAM);``FPM.addPass(LowerSwitchPass());``FPM.run(*f, FAM);` `// 1. 遍历函数中所有基本块,进行合法性检查后存储到origBB``for` `(BasicBlock &BB : *f) {``// 是否为检查异常处理块或Landing Pad, 若是则终止平坦化混淆``if` `(BB.isEHPad() \|\| BB.isLandingPad()) {``errs() << f->getName()``<<` `" Contains Exception Handing Instructions and is unsupported "``"for flattening in the open-source version of Hikari.\n"``;``return` `false``;``}``// 检查终止指令 所有基本块的终止指令必须为Branch或Return才能进行平坦化混淆``if` `(!isa<BranchInst>(BB.getTerminator()) &&``!isa<ReturnInst>(BB.getTerminator()))``return` `false``;``// 追加到origBB,emplace_back同push_back功能类似,但不创建临时对象``origBB.emplace_back(&BB);` `}` `// 基本块个数<=1,不进行平坦化``if` `(origBB.size() <= 1)``return` `false``;` `// 删除第一个基本块(entry块)``origBB.erase(origBB.begin());` `Function::iterator tmp = f->begin();` `// 获取entry块的迭代器``BasicBlock *insert = &*tmp;` `// 获取entry块的指针` `// 2. 单独检查并处理entry块``BranchInst *br = nullptr;``// 如果终止指令是branch指令则获取该指令``if` `(isa<BranchInst>(insert->getTerminator()))``br = cast<BranchInst>(insert->getTerminator());` `// 如果分支指令是条件分支指令或有多个后继块``if` `((br && br->isConditional()) \|\|``insert->getTerminator()->getNumSuccessors() > 1) {``BasicBlock::iterator i = insert->end();` `// 终止指令迭代器``--i;` `// 前移一个指令` `// 如果有多条指令则额外前移一个单位``if` `(insert->size() > 1) {``--i;``}` `// 分割entry块,新块名为first``BasicBlock *tmpBB = insert->splitBasicBlock(i,` `"first"``);``// 将first块添加到origBB头部``origBB.insert(origBB.begin(), tmpBB);``}` `// 3. 创建并初始化switchVar和switchVarAddr``// 获取entry块的原始终止指令``Instruction *oldTerm = insert->getTerminator();` `// 创建switchVar变量, 利用DataLayout确保平台兼容性``switchVar =` `new` `AllocaInst(Type::getInt32Ty(f->getContext()),``DL.getAllocaAddrSpace(),` `"switchVar"``, oldTerm);``// 创建switchVarAddr地址变量``switchVarAddr =``new` `AllocaInst(Type::getInt32Ty(f->getContext())->getPointerTo(),``DL.getAllocaAddrSpace(),` `""``, oldTerm);` `// 移除entry的原始终止指令``oldTerm->eraseFromParent();` `// 分别初始化switchVar和switchVarAddr``new` `StoreInst(ConstantInt::get(Type::getInt32Ty(f->getContext()),``cryptoutils->scramble32(0, scrambling_key)),``switchVar, insert);``new` `StoreInst(switchVar, switchVarAddr, insert);` `// 4. 创建控制流平坦化的循环结构``// 创建主循环的入口和出口基本块``loopEntry = BasicBlock::Create(f->getContext(),` `"loopEntry"``, f, insert);``loopEnd = BasicBlock::Create(f->getContext(),` `"loopEnd"``, f, insert);` `// 在循环入口loopEntry加载switchVar变量``load =` `new` `LoadInst(switchVar->getAllocatedType(), switchVar,` `"switchVar"``,``loopEntry);` `// 调整基本块顺序,构建初始控制流``insert->moveBefore(loopEntry);` `// 将entry块移动到loopEntry块前``BranchInst::Create(loopEntry, insert);` `// 创建分支指令,entry -> loopEntry``BranchInst::Create(loopEntry, loopEnd);` `// 创建分支指令,loopEnd -> loopEntry` `// 5. 创建主switch指令``// 创建switch的default块``BasicBlock *swDefault =``BasicBlock::Create(f->getContext(),` `"switchDefault"``, f, loopEnd);``BranchInst::Create(loopEnd, swDefault);` `// switchDefault -> loopEnd` `// 创建switch指令并设置条件为load (LoadInst加载的switchVar)``switchI = SwitchInst::Create(&*f->begin(), swDefault, 0, loopEntry);``switchI->setCondition(load);` `// 移除entry块的终止指令 ??? 为什么要移除第二次``f->begin()->getTerminator()->eraseFromParent();``BranchInst::Create(loopEntry, &*f->begin());` `// 创建分支指令 entry->loopEntry ???也有第二次` `// 6. 将原始基本块整合到主switch结构中``for` `(BasicBlock *i : origBB) {``ConstantInt *numCase = nullptr;` `// 移动基本块到loopEnd块前``i->moveBefore(loopEnd);` `// 为基本块生成加密的case值``numCase = cast<ConstantInt>(ConstantInt::get(``switchI->getCondition()->getType(),``cryptoutils->scramble32(switchI->getNumCases(), scrambling_key)));` `// 将基本块添加到switch的case中``switchI->addCase(numCase, i);``}` `// 7. 计算和修复控制流 分别处理单后继的无条件分支和双后继的条件分支指令``// 针对每个基本块, 删除原终结指令, 查找后继块的case值(若无后继则为default块)``// 之后更新switchVar为后继块case值, 并创建branch分支跳转到loopEnd块``// 由于loopEnd块会跳转回loopEntry, 所以会继续循环执行下一个基本块的代码, 直到跳出循环``for` `(BasicBlock *i : origBB) {``ConstantInt *numCase = nullptr;` `// 处理单后继的无条件跳转``if` `(i->getTerminator()->getNumSuccessors() == 1) {``BasicBlock *succ = i->getTerminator()->getSuccessor(0);` `// 获取后继块``i->getTerminator()->eraseFromParent();` `//删除终止指令` `// 查找后继块对应的case值``numCase = switchI->findCaseDest(succ);` `// 如果找不到对应case则使用default值``if` `(!numCase) {``numCase = cast<ConstantInt>(``ConstantInt::get(switchI->getCondition()->getType(),``cryptoutils->scramble32(switchI->getNumCases() - 1,``scrambling_key)));``}` `// 使用switchVarAddr访问并更新switchVar``new` `StoreInst(``numCase,``new` `LoadInst(switchVarAddr->getAllocatedType(), switchVarAddr,` `""``, i),``i);` `// 创建branch指令, 当前基本块跳转到loopEnd``BranchInst::Create(loopEnd, i);``continue``;``}` `// 处理双后继的条件分支块``if` `(i->getTerminator()->getNumSuccessors() == 2) {``// 获取两个分支目标后继块的case值``ConstantInt *numCaseTrue =``switchI->findCaseDest(i->getTerminator()->getSuccessor(0));``ConstantInt *numCaseFalse =``switchI->findCaseDest(i->getTerminator()->getSuccessor(1));` `// 检查case值,若找不到则使用默认值``if` `(!numCaseTrue) {``numCaseTrue = cast<ConstantInt>(``ConstantInt::get(switchI->getCondition()->getType(),``cryptoutils->scramble32(switchI->getNumCases() - 1,``scrambling_key)));``}` `// 检查case值,若找不到则使用默认值``if` `(!numCaseFalse) {``numCaseFalse = cast<ConstantInt>(``ConstantInt::get(switchI->getCondition()->getType(),``cryptoutils->scramble32(switchI->getNumCases() - 1,``scrambling_key)));``}` `BranchInst *br = cast<BranchInst>(i->getTerminator());``// 创建select指令, 选择目标case``SelectInst *sel =``SelectInst::Create(br->getCondition(), numCaseTrue, numCaseFalse,` `""``,``i->getTerminator());` `// 移除原基本块的终止指令``i->getTerminator()->eraseFromParent();``// 利用switchVarAddr访问并更新switchVar``new` `StoreInst(``sel,``new` `LoadInst(switchVarAddr->getAllocatedType(), switchVarAddr,` `""``, i),``i);``// 创建branch指令,当前基本块分支跳转到loopEnd``BranchInst::Create(loopEnd, i);``continue``;``}``}``// 8. 修复栈结构``errs() <<` `"Fixing Stack\n"``;``fixStack(*f);``errs() <<` `"Fixed Stack\n"``;``return` `true``;` `}` |
|-|-|

### Utils::fixStack

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556 | `/** LLVM\llvm\lib\Transforms\Scalar\Reg2Mem.cpp``* @brief 修复PHI指令和逃逸变量``*``* @param F``*/``void` `fixStack(Function &F) {``// Insert all new allocas into entry block.``BasicBlock *BBEntry = &F.getEntryBlock();` `// 获取entry块``// 1. 断言确保entry没有前驱块 entry块是函数执行的起点,不应该有前驱块``assert``(pred_empty(BBEntry) &&``"Entry block to function must not have predecessors!"``);` `// Find first non-alloca instruction and create insertion point. This is``// safe if block is well-formed: it always have terminator, otherwise``// we'll get and assertion.``// 2. 获取入口块中第一条非alloca指令``BasicBlock::iterator I = BBEntry->begin();``while` `(isa<AllocaInst>(I))``++I;` `// 3. 创建位转换指令作为插入点(无实际功能,仅做标记点)``// 将0常量转换为i32类型后存储到变量fix_stack_point中``CastInst *AllocaInsertionPoint =` `new` `BitCastInst(``Constant::getNullValue(Type::getInt32Ty(F.getContext())),``Type::getInt32Ty(F.getContext()),` `"fix_stack_point"``, &*I);` `// Find the escaped instructions. But don't create stack slots for``// allocas in entry block.``// 4. 查找并保存所有需要处理的逃逸指令 逃逸指令: 在定义的基本块之外被使用的指令``// 创建工作列表, 存储需要处理的逃逸指令``std::list<Instruction *> WorkList;``// 第一次遍历, 查找所有逃逸指令``for` `(Instruction &I : instructions(F))``// 排除entry块的alloca指令(已在栈上) 通过valueEscapes检查是否为逃逸指令``if` `(!(isa<AllocaInst>(I) && I.getParent() == BBEntry) && valueEscapes(I))``WorkList.push_front(&I);` `// 将逃逸指令添加到list最前端` `// Demote escaped instructions``// NumRegsDemoted += WorkList.size(); // 注释掉的统计代码``// 5. 将逃逸指令降级到栈上``for` `(Instruction *I : WorkList)``// LLVM内置函数, 将寄存器形式的指令降级到栈上分配``// 参数: *I需要降级的指令, false不强制降级, 指定指令插入点(LLVM19适配)` `DemoteRegToStack(*I,` `false``, AllocaInsertionPoint->getIterator());` `//fix for llvm 19` `WorkList.clear();` `// 6. 查找所有PHI Nodes``for` `(BasicBlock &BB : F)``for` `(``auto` `&Phi : BB.phis())``WorkList.push_front(&Phi);` `// 7. 降级所有PHI Nodes到栈上``for` `(Instruction *I : WorkList)``DemotePHIToStack(cast<PHINode>(I), AllocaInsertionPoint->getIterator());` `//fix for llvm19``}` |
|-|-|

其中有一个非常关键的概念: 降级到栈上

首先了解一下LLVM中数据的存储方式:

| 存储方式 | 特点 | 示例 |
|-|-|-|
| SSA 寄存器形式 | 使用虚拟寄存器 | %result = add i32 %a, %b |
| 内存形式 | 使用栈内存分配和访问 | %mem = alloca i32 store i32 %result, ptr %mem %val = load i32, ptr %mem |

需要注意:

- 降级到栈上 ≠ 简单的将寄存器值保存到栈

而是将原本使用 SSA 寄存器形式的值，转换为通过栈内存分配和访问的形式
- SSA虚拟寄存器 ≠ 物理寄存器

SSA寄存器是LLVM中的中间表示, 是否使用物理寄存器需通过映射算法确定

对于普通指令的降级 (DemoteRegToStack):

降级前: 原始代码使用SSA寄存器存储add结果

| 12345 | `define i32 @add(i32` `%``a, i32` `%``b) {``entry:``%``sum` `=` `add i32` `%``a,` `%``b     ; 结果存储在虚拟寄存器``%``sum``中``ret i32` `%``sum`              `; 直接使用``}` |
|-|-|

降级后:

| 12345678 | `define i32 @add(i32` `%``a, i32` `%``b) {``entry:``%``stack_slot` `=` `alloca i32              ;` `1.` `分配栈空间``%``sum` `=` `add i32` `%``a,` `%``b                 ;` `2.` `计算（结果存储到虚拟寄存器``%``sum``）``store i32` `%``sum``, ptr` `%``stack_slot       ;` `3.` `从``%``sum``存储到栈``%``result` `=` `load i32, ptr` `%``stack_slot   ;` `4.` `从栈中重新加载到虚拟寄存器``%``result``ret i32` `%``result                       ;` `5.` `返回栈中加载的值``}` |
|-|-|

对于 PHI 节点的降级 (DemotePHIToStack):

降级前: 使用SSA虚拟寄存器向PHI Node传递值

| 1234567891011121314 | `define i32 @phi_example(i1` `%``cond, i32` `%``a, i32` `%``b) {``entry:``br i1` `%``cond, label` `%``true, label` `%``false` `true:``br label` `%``merge` `false:``br label` `%``merge` `merge:``%``result` `=` `phi i32 [` `%``a,` `%``true ], [` `%``b,` `%``false ]  ; PHI节点``ret i32` `%``result``}` |
|-|-|

降级后: 分支将具体值存入栈中供PHI Node选取使用

| 1234567891011121314151617 | `define i32 @phi_example(i1` `%``cond, i32` `%``a, i32` `%``b) {``entry:``%``stack_slot` `=` `alloca i32              ; 分配栈空间用于分支存储值``br i1` `%``cond, label` `%``true, label` `%``false` `true:``store i32` `%``a, ptr` `%``stack_slot         ; 在true分支存储``%``a到栈上``br label` `%``merge` `false:``store i32` `%``b, ptr` `%``stack_slot         ; 在false分支存储` `br label` `%``merge` `merge:``%``result` `=` `load i32, ptr` `%``stack_slot   ; 从栈中加载最终值并返回``ret i32` `%``result``}` |
|-|-|

### Control Flow Flattening 效果分析

#### 测试代码

| 1234567891011 | `#include <stdio.h>``int` `main(){``int` `x=3,y=6;``if``(x>y){``printf``(``"%d > %d"``,x,y);``}``else``{``printf``(``"%d <= %d"``,x,y);``}``return` `0;``}` |
|-|-|

#### IDA分析

![control_flow_flattening_decompile](https://bbs.kanxue.com/upload/attach/202511/968342_8PNRE4TBPC43VZ7.png)

#### main IR

混淆前: 包含entry, if.then, if.else, if.end 共4个基本块

| 1234567891011121314151617181920212223242526272829 | `; Function Attrs: noinline nounwind uwtable``define dso_local i32 @main()` `#0 {``entry:``%``retval` `=` `alloca i32, align` `4``%``x` `=` `alloca i32, align` `4``%``y` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retval, align` `4``store i32` `3``, ptr` `%``x, align` `4``store i32` `6``, ptr` `%``y, align` `4``%``0` `=` `load i32, ptr` `%``x, align` `4``%``1` `=` `load i32, ptr` `%``y, align` `4``%``cmp` `=` `icmp sgt i32` `%``0``,` `%``1``br i1` `%``cmp``, label` `%``if``.then, label` `%``if``.``else` `if``.then:                                          ; preds` `=` `%``entry``%``2` `=` `load i32, ptr` `%``y, align` `4``%``3` `=` `load i32, ptr` `%``x, align` `4``%``call` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_07NCCKKCBF@?$CFd?5?$DO?5?$CFd?$AA@"``, i32 noundef` `%``3``, i32 noundef` `%``2``)``br label` `%``if``.end` `if``.``else``:                                          ; preds` `=` `%``entry``%``4` `=` `load i32, ptr` `%``y, align` `4``%``5` `=` `load i32, ptr` `%``x, align` `4``%``call1` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_08PPKAIFBH@?$CFd?5?$DM?$DN?5?$CFd?$AA@"``, i32 noundef` `%``5``, i32 noundef` `%``4``)``br label` `%``if``.end` `if``.end:                                           ; preds` `=` `%``if``.``else``,` `%``if``.then``ret i32` `0``}` |
|-|-|

混淆后: 包含entry, if.then, if.else, if.end, first, loopEntry, loopEnd, switchDefault 共8个基本块

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566 | `Main func after control flow flattening:``; Function Attrs: noinline nounwind uwtable``define dso_local i32 @main()` `#0 {``entry:``%``retval` `=` `alloca i32, align` `4``%``x` `=` `alloca i32, align` `4``%``y` `=` `alloca i32, align` `4``%``.reg2mem` `=` `alloca i32, align` `4``%``.reg2mem2` `=` `alloca i32, align` `4``%``fix_stack_point` `=` `bitcast i32` `0` `to i32``store i32` `0``, ptr` `%``retval, align` `4``store i32` `3``, ptr` `%``x, align` `4``store i32` `6``, ptr` `%``y, align` `4``%``0` `=` `load i32, ptr` `%``x, align` `4``store i32` `%``0``, ptr` `%``.reg2mem2, align` `4``%``1` `=` `load i32, ptr` `%``y, align` `4``store i32` `%``1``, ptr` `%``.reg2mem, align` `4``%``switchVar` `=` `alloca i32, align` `4``%``2` `=` `alloca ptr, align` `8``store i32` `-``1117939497``, ptr` `%``switchVar, align` `4``store ptr` `%``switchVar, ptr` `%``2``, align` `8``br label` `%``loopEntry` `loopEntry:                                        ; preds` `=` `%``entry,` `%``loopEnd``%``switchVar1` `=` `load i32, ptr` `%``switchVar, align` `4``switch i32` `%``switchVar1, label` `%``switchDefault [``i32` `-``1117939497``, label` `%``first``i32` `1096699745``, label` `%``if``.then``i32` `-``2042035316``, label` `%``if``.``else``i32` `937045764``, label` `%``if``.end``]` `switchDefault:                                    ; preds` `=` `%``loopEntry``br label` `%``loopEnd` `first:                                            ; preds` `=` `%``loopEntry``%``.``reload` `=` `load i32, ptr` `%``.reg2mem, align` `4``%``.reload3` `=` `load i32, ptr` `%``.reg2mem2, align` `4``%``cmp` `=` `icmp sgt i32` `%``.reload3,` `%``.``reload``%``3` `=` `select i1` `%``cmp``, i32` `1096699745``, i32` `-``2042035316``%``4` `=` `load ptr, ptr` `%``2``, align` `8``store i32` `%``3``, ptr` `%``4``, align` `4``br label` `%``loopEnd` `if``.then:                                          ; preds` `=` `%``loopEntry``%``5` `=` `load i32, ptr` `%``y, align` `4``%``6` `=` `load i32, ptr` `%``x, align` `4``%``call` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_07NCCKKCBF@?$CFd?5?$DO?5?$CFd?$AA@"``, i32 noundef` `%``6``, i32 noundef` `%``5``)``%``7` `=` `load ptr, ptr` `%``2``, align` `8``store i32` `937045764``, ptr` `%``7``, align` `4``br label` `%``loopEnd` `if``.``else``:                                          ; preds` `=` `%``loopEntry``%``8` `=` `load i32, ptr` `%``y, align` `4``%``9` `=` `load i32, ptr` `%``x, align` `4``%``call1` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_08PPKAIFBH@?$CFd?5?$DM?$DN?5?$CFd?$AA@"``, i32 noundef` `%``9``, i32 noundef` `%``8``)``%``10` `=` `load ptr, ptr` `%``2``, align` `8``store i32` `937045764``, ptr` `%``10``, align` `4``br label` `%``loopEnd` `if``.end:                                           ; preds` `=` `%``loopEntry``ret i32` `0` `loopEnd:                                          ; preds` `=` `%``if``.``else``,` `%``if``.then,` `%``first,` `%``switchDefault``br label` `%``loopEntry``}` |
|-|-|

逐步解析相关变化, 首先从entry块切入

| 12345678910111213141516171819202122232425262728293031 | `entry:``%``retval` `=` `alloca i32, align` `4``%``x` `=` `alloca i32, align` `4``%``y` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retval, align` `4``store i32` `3``, ptr` `%``x, align` `4``store i32` `6``, ptr` `%``y, align` `4``%``0` `=` `load i32, ptr` `%``x, align` `4``%``1` `=` `load i32, ptr` `%``y, align` `4``%``cmp` `=` `icmp sgt i32` `%``0``,` `%``1``br i1` `%``cmp``, label` `%``if``.then, label` `%``if``.``else` `entry:``%``retval` `=` `alloca i32, align` `4``%``x` `=` `alloca i32, align` `4``%``y` `=` `alloca i32, align` `4``%``.reg2mem` `=` `alloca i32, align` `4``%``.reg2mem2` `=` `alloca i32, align` `4``%``fix_stack_point` `=` `bitcast i32` `0` `to i32``store i32` `0``, ptr` `%``retval, align` `4``store i32` `3``, ptr` `%``x, align` `4``store i32` `6``, ptr` `%``y, align` `4``%``0` `=` `load i32, ptr` `%``x, align` `4``store i32` `%``0``, ptr` `%``.reg2mem2, align` `4``%``1` `=` `load i32, ptr` `%``y, align` `4``store i32` `%``1``, ptr` `%``.reg2mem, align` `4``%``switchVar` `=` `alloca i32, align` `4``%``2` `=` `alloca ptr, align` `8``store i32` `-``1117939497``, ptr` `%``switchVar, align` `4``store ptr` `%``switchVar, ptr` `%``2``, align` `8``br label` `%``loopEntry` |
|-|-|

有3处改动

1. %x和%y声明后插入降级声明代码

| 123 | `%``.reg2mem` `=` `alloca i32, align` `4``%``.reg2mem2` `=` `alloca i32, align` `4``%``fix_stack_point` `=` `bitcast i32` `0` `to i32` |
|-|-|
2. %x和%y赋值后reg2mem降级操作

| 1234 | `%``0` `=` `load i32, ptr` `%``x, align` `4``store i32` `%``0``, ptr` `%``.reg2mem2, align` `4``%``1` `=` `load i32, ptr` `%``y, align` `4``store i32` `%``1``, ptr` `%``.reg2mem, align` `4` |
|-|-|
3. 替换icmp和br指令

| 12345 | `%``switchVar` `=` `alloca i32, align` `4``%``2` `=` `alloca ptr, align` `8``store i32` `-``1117939497``, ptr` `%``switchVar, align` `4``store ptr` `%``switchVar, ptr` `%``2``, align` `8``br label` `%``loopEntry` |
|-|-|

entry块设置 %switchVar = -1117939497 后跳转到loopEntry块, 不难发现实际是跳转到first块

| 12345678 | `loopEntry:                                        ; preds` `=` `%``entry,` `%``loopEnd``%``switchVar1` `=` `load i32, ptr` `%``switchVar, align` `4``switch i32` `%``switchVar1, label` `%``switchDefault [``i32` `-``1117939497``, label` `%``first``i32` `1096699745``, label` `%``if``.then``i32` `-``2042035316``, label` `%``if``.``else``i32` `937045764``, label` `%``if``.end``]` |
|-|-|

回顾flatten中第2步处理entry块:

1. 如果entry的终止指令是branch则获取
2. 如果该branch指令是条件分支指令或者有多个后继块则分割entry
3. entry块指令数=1时迭代器从end前移1单位,否则前移2单位
4. 利用迭代器分割entry后,新块命名为first并添加到origBB头部

所以icmp和br指令实际上被分配给了first块:

1. 首先从栈中加载entry块中保存的reg2mem (x和y) 到 reload
2. 通过icmp指令比较reload, 结果存储到%cmp
3. 通过select指令根据比较结果选择不同case值存储到%3
4. %4 = %2= ptr %switchVar 即获取switchVar的指针
5. 将case值存储到switchVar中, br跳转到loopEnd

| 12345678 | `first:                                            ; preds` `=` `%``loopEntry``%``.``reload` `=` `load i32, ptr` `%``.reg2mem, align` `4``%``.reload3` `=` `load i32, ptr` `%``.reg2mem2, align` `4``%``cmp` `=` `icmp sgt i32` `%``.reload3,` `%``.``reload``%``3` `=` `select i1` `%``cmp``, i32` `1096699745``, i32` `-``2042035316``%``4` `=` `load ptr, ptr` `%``2``, align` `8``store i32` `%``3``, ptr` `%``4``, align` `4``br label` `%``loopEnd` |
|-|-|

loopEnd块只会跳转回loopEntry

| 12 | `loopEnd:                                          ; preds` `=` `%``if``.``else``,` `%``if``.then,` `%``first,` `%``switchDefault``br label` `%``loopEntry` |
|-|-|

而first块中的case值分别对应if-else结构的两个分支块

| 12 | `i32` `1096699745``, label` `%``if``.then``i32` `-``2042035316``, label` `%``if``.``else` |
|-|-|

if.then和if.else代码类似

先加载x和y值后调用printf函数打印, 之后获取switchVar指针并设置case值, 跳转到loopEnd

| 123456789101112131415 | `if``.then:                                          ; preds` `=` `%``loopEntry``%``5` `=` `load i32, ptr` `%``y, align` `4``%``6` `=` `load i32, ptr` `%``x, align` `4``%``call` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_07NCCKKCBF@?$CFd?5?$DO?5?$CFd?$AA@"``, i32 noundef` `%``6``, i32 noundef` `%``5``)``%``7` `=` `load ptr, ptr` `%``2``, align` `8``store i32` `937045764``, ptr` `%``7``, align` `4``br label` `%``loopEnd` `if``.``else``:                                          ; preds` `=` `%``loopEntry``%``8` `=` `load i32, ptr` `%``y, align` `4``%``9` `=` `load i32, ptr` `%``x, align` `4``%``call1` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_08PPKAIFBH@?$CFd?5?$DM?$DN?5?$CFd?$AA@"``, i32 noundef` `%``9``, i32 noundef` `%``8``)``%``10` `=` `load ptr, ptr` `%``2``, align` `8``store i32` `937045764``, ptr` `%``10``, align` `4``br label` `%``loopEnd` |
|-|-|

此处case值固定为937045764, 对应if.end块

| 12 | `if``.end:                                           ; preds` `=` `%``loopEntry``ret i32` `0` |
|-|-|

执行到if.end块后运行ret指令退出main函数, 至此通过entry切入, 混淆后的main函数分析完毕

## Bogus Control Flow

功能: 创建虚假分支块从而混淆原程序控制流

### Bogus Control Flow 关键流程

BogusControlFlow的关键流程如下,先调用bogus后调用doF

![BogusControlFlow](https://bbs.kanxue.com/upload/attach/202511/968342_EFF2K55XT5CTZVX.png)

由于代码比较绕, 为了清晰展示流程额外绘制几张混淆过程中的基本块变化图

假设需要混淆的基本块名为basicBlock

![image](https://bbs.kanxue.com/upload/attach/202511/968342_R23A4X8XVKYYX48.png)

![BogusControlFlow-Process2](https://bbs.kanxue.com/upload/attach/202511/968342_XYB2FEG52HXJ298.png)

![BogusControlFlow-Process3](https://bbs.kanxue.com/upload/attach/202511/968342_23QQEU9XQMPJSP6.png)

![BogusControlFlow-Process4](https://bbs.kanxue.com/upload/attach/202511/968342_97XMMXPYCFR8M7W.png)

可以发现,原本basicBlock->successor的控制流经过一次bogus混淆后额外添加了3个干扰基本块

### BogusControlFlowPass::run

bcf中主要执行bogus和doF

- bogus添加虚假控制流
- doF创建并替换bogus中创建的永真条件跳转指令为一般条件跳转指令

| 1234567891011121314151617181920 | `PreservedAnalyses BogusControlFlowPass::run(Function& F, FunctionAnalysisManager& AM) {``// Check if the percentage is correct``if` `(ObfTimes <= 0){``errs() <<` `"BogusControlFlow application number -bcf_loop=x must be x > 0"``;``return` `PreservedAnalyses::all();``}``// Check if the number of applications is correct``if` `(!((ObfProbRate > 0) && (ObfProbRate <= 100))) {``errs() <<` `"BogusControlFlow application basic blocks percentage "``"-bcf_prob=x must be 0 < x <= 100"``;``return` `PreservedAnalyses::all();``}``// If fla annotations``if` `(toObfuscate(flag, &F,` `"bcf"``)){``bogus(F);``doF(*F.getParent(), F);``return` `PreservedAnalyses::none();``}``return` `PreservedAnalyses::all();``}` |
|-|-|

### BogusControlFlowPass::bogus

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152 | `void` `BogusControlFlowPass::bogus(Function &F) {``// 统计和调试相关``++NumFunction;` `// 记录函数个数``int` `NumBasicBlocks = 0;` `// 记录基本块个数``bool` `firstTime =` `true``;` `// First time we do the loop in this function``bool` `hasBeenModified =` `false``;` `if` `(ObfProbRate < 0 \|\| ObfProbRate > 100) {``ObfProbRate = defaultObfRate;` `// 每个基本块混淆的概率,同bcf_prob参数对应, 如果概率不在正常范围则使用默认概率``}``if` `(ObfTimes <= 0) {``ObfTimes = defaultObfTime;``}``NumTimesOnFunctions = ObfTimes;` `// 同bcf_num参数对应``int` `NumObfTimes = ObfTimes;` `// 循环bcf_loop次``do` `{``// 1. 存储所有基本块``std::list<BasicBlock *> basicBlocks;``for` `(Function::iterator i = F.begin(); i != F.end(); ++i) {``basicBlocks.push_back(&*i);``}` `// 遍历所有基本块``while` `(!basicBlocks.empty()) {``NumBasicBlocks++;``// 通过概率控制选择基本块, 和bcf_prob参数对应, 暂时不懂range(100)是什么意思?``if` `((``int``)llvm::cryptoutils->get_range(100) <= ObfProbRate) {` `hasBeenModified =` `true``;` `++NumModifiedBasicBlocks;` `// 被修改的基本块计数``NumAddedBasicBlocks += 3;` `// 每次bogus flow额外添加3个基本块``FinalNumBasicBlocks += 3;``// Add bogus flow to the given Basic Block (see description)``// 2. 从列表取基本块并添加虚假控制流``BasicBlock *basicBlock = basicBlocks.front();` `// 取列表第一个基本块``addBogusFlow(basicBlock, F);` `// 向指定基本块添加伪控制流``}` `// 从列表中移除第一个基本块``basicBlocks.pop_front();` `// 如果是第一次迭代该函数 // first time we iterate on this function``if` `(firstTime) {` `++InitNumBasicBlocks;``++FinalNumBasicBlocks;``}``}` `// end of while(!basicBlocks.empty())``firstTime =` `false``;``}` `while` `(--NumObfTimes > 0);``}` |
|-|-|

### BogusControlFlowPass::addBogusFlow

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475 | `void` `BogusControlFlowPass::addBogusFlow(BasicBlock *basicBlock, Function &F) {``// Split the block: first part with only the phi nodes and debug info and``// terminator``//                  created by splitBasicBlock. (-> No instruction)``//                  Second part with every instructions from the original``//                  block``// We do this way, so we don't have to adjust all the phi nodes, metadatas``// and so on for the first block. We have to let the phi nodes in the first``// part, because they actually are updated in the second part according to``// them.` `// 获取基本块中第一个合法指令 非PHI, 非Dbg, 非Lifetime的指令 (即一般指令?)``BasicBlock::iterator i1 = basicBlock->begin();``if` `(basicBlock->getFirstNonPHIOrDbgOrLifetime())``i1 = (BasicBlock::iterator)basicBlock->getFirstNonPHIOrDbgOrLifetime();``// 如果存在异常处理块则跳过,不进行混淆``if` `(basicBlock->getFirstNonPHI()->isEHPad())``return``;` `// Fix Verifier.cpp: "CatchPadInst not the first non-PHI instruction in the``// block.", "The unwind destination does not have an exception handling``// instruction!"` `// 1. 分割基本块, 在当前basicBlock和其后继基本块之间, 插入新建的originalBB基本块``// 即 basicBlock -> originalBB -> successor basicBlock``Twine *var;``var =` `new` `Twine(``"originalBB"``);``BasicBlock *originalBB = basicBlock->splitBasicBlocki1, *var);` `// 2. 创建alteredBB基本块,并fork和填充垃圾指令``// 创建alteredBB基本块,` `Twine *var3 =` `new` `Twine(``"alteredBB"``);``// 根据传入的基本块fork新的基本块, 进行修正和垃圾指令填充``BasicBlock *alteredBB = createAlteredBasicBlock(originalBB, *var3, &F);` `// 3. 删除alteredBB, basicBlock的终结指令``alteredBB->getTerminator()->eraseFromParent();``basicBlock->getTerminator()->eraseFromParent();` `// 4. 先后创建永真FCmp和条件branch指令并插入basicBlock末尾``// 创建2个值(默认为浮点1) 作为FCmp指令的条件, 在doF函数中会将这两个值复杂化``Value *LHS = ConstantFP::get(Type::getFloatTy(F.getContext()), 1.0);``Value *RHS = ConstantFP::get(Type::getFloatTy(F.getContext()), 1.0);``// 创建永真的FCmp指令, 插入到basicBlock的末尾``// cmp LHS, RHS``Twine *var4 =` `new` `Twine(``"condition"``);``FCmpInst *condition =` `new` `FCmpInst(InsertPosition(basicBlock),``FCmpInst::FCMP_TRUE, LHS, RHS, *var4);` `//fix for llvm 19``// 创建条件跳转指令, 插入basicBlock末尾``// true块为originalBB, false块为alteredBB, 条件为condition``BranchInst::Create(originalBB, alteredBB, (Value *)condition, basicBlock);` `// 5. 创建从alteredBB跳转到originalBB的分支指令``// 经过以上处理后, basicBlock有2条分支, 条件永真跳转到originalBB, 假分支alteredBB最终也会跳转到originalBB``BranchInst::Create(originalBB, alteredBB);` `// 6. 以originalBB末尾的转移指令进行分割,新基本块名为originalBBpart2``BasicBlock::iterator i = originalBB->end();``Twine *var5 =` `new` `Twine(``"originalBBpart2"``);``BasicBlock *originalBBpart2 = originalBB->splitBasicBlock(--i, *var5);` `// 7. 删除originalBB末尾的转移指令``originalBB->getTerminator()->eraseFromParent();` `// 8. 同上类似, 创建永真条件跳转指令, 插入到originalBB的末尾``// true分支为originalBBpart2, false分支为alteredBB``Twine *var6 =` `new` `Twine(``"condition2"``);``FCmpInst *condition2 =` `new` `FCmpInst(InsertPosition (originalBB),``CmpInst::FCMP_TRUE, LHS, RHS, *var6);` `//fix for llvm 19``// 在originalBB末尾创建条件branch指令, 从alteredBB跳转到originalBBPart2``BranchInst::Create(originalBBpart2, alteredBB, (Value *)condition2,``originalBB);``// 经过以上操作后, true块originalBB也进行了一次控制流混淆``// originalBBpart2似乎没有实际内容,主要用于连接后继块``}` `// end of addBogusFlow()` |
|-|-|

### BogusControlFlowPass::createAlteredBasicBlock

该函数用于fork虚假块, 并填充垃圾指令

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207 | `BasicBlock *createAlteredBasicBlock(BasicBlock *basicBlock,` `const` `Twine &Name,``Function *F) {``// Useful to remap the informations concerning instructions.``ValueToValueMapTy VMap;``// 通过CloneBasicBlock复制basicBlock为alteredBB``// 注意此basicBlock为上述代码中通过splitBasicBlock分割basicBlock得到的originalBB``// 即createAlteredBasicBlock(originalBB, *var3, &F);``BasicBlock *alteredBB = llvm::CloneBasicBlock(basicBlock, VMap, Name, F);` `// 1. 重映射指令以修复alteredBB 主要处理指令操作数和PHINode的前驱基本块``BasicBlock::iterator ji = basicBlock->begin();` `// 基本块的首条指令``for` `(BasicBlock::iterator i = alteredBB->begin(), e = alteredBB->end();` `// 遍历基本块的指令``i != e; ++i) {``// 遍历指令的的操作数``for` `(User::op_iterator opi = i->op_begin(), ope = i->op_end(); opi != ope;``++opi) {``// 通过VMap映射表得到操作数值, 若值不为0则需要重映射 (映射基本块后默认指令的操作数全0?)``Value *v = MapValue(*opi, VMap, RF_None, 0);``if` `(v != 0) {``*opi = v;``}``}``// 恢复PHI Node的前驱基本块``if` `(PHINode *pn = dyn_cast<PHINode>(i)) {``for` `(unsigned j = 0, e = pn->getNumIncomingValues(); j != e; ++j) {``Value *v = MapValue(pn->getIncomingBlock(j), VMap, RF_None, 0);``if` `(v != 0) {``pn->setIncomingBlock(j, cast<BasicBlock>(v));``}``}``}` `// 恢复当前指令的metadata和DebugLoc``SmallVector<std::pair<unsigned, MDNode *>, 4> MDs;``i->getAllMetadata(MDs);``i->setDebugLoc(ji->getDebugLoc());``ji++;` `}` `// The instructions' informations are now all correct` `// 2. 删除alteredBB中的调试指令``for` `(``auto` `I = alteredBB->begin(), E = alteredBB->end(); I != E;) {``Instruction *Instr = &*I++;``if` `(isa<DbgInfoIntrinsic>(Instr))``Instr->eraseFromParent();``}``// Fix Verifier.cpp: "mismatched subprogram between llvm.dbg.value label and``// !dbg attachment"` `// 3. 遍历alteredBB, 添加垃圾指令``for` `(BasicBlock::iterator i = alteredBB->begin(), e = alteredBB->end();``i != e; ++i) {``// 如果是二进制运算指令,则添加垃圾指令, 即加减乘除和位运算``if` `(i->isBinaryOp()) {` `// binary instructions``unsigned opcode = i->getOpcode();` `// 获取操作码``Instruction *op, *op1 = NULL;``Twine *var =` `new` `Twine(``"_"``);``// treat differently float or int``// 整型二进制运算指令``if` `(opcode == Instruction::Add \|\| opcode == Instruction::Sub \|\|``opcode == Instruction::Mul \|\| opcode == Instruction::UDiv \|\|``opcode == Instruction::SDiv \|\| opcode == Instruction::URem \|\|``opcode == Instruction::SRem \|\| opcode == Instruction::Shl \|\|``opcode == Instruction::LShr \|\| opcode == Instruction::AShr \|\|``opcode == Instruction::And \|\| opcode == Instruction::Or \|\|``opcode == Instruction::Xor) {``// 随机10次, 选择创建某种垃圾指令添加到当前指令前,或者不作操作``for` `(``int` `random = (``int``)llvm::cryptoutils->get_range(10); random < 10;``++random) {``switch` `(llvm::cryptoutils->get_range(4)) {` `// to improve``case` `0:` `// do nothing``break``;``case` `1:``op = BinaryOperator::CreateNeg(i->getOperand(0), *var, &*i);``op1 = BinaryOperator::Create(Instruction::Add, op, i->getOperand(1),``"gen"``, &*i);``break``;``case` `2:``op1 = BinaryOperator::Create(Instruction::Sub, i->getOperand(0),``i->getOperand(1), *var, &*i);``op = BinaryOperator::Create(Instruction::Mul, op1, i->getOperand(1),``"gen"``, &*i);``break``;``case` `3:``op = BinaryOperator::Create(Instruction::Shl, i->getOperand(0),``i->getOperand(1), *var, &*i);``break``;``}``}``}``// 浮点型二进制运算指令``if` `(opcode == Instruction::FAdd \|\| opcode == Instruction::FSub \|\|``opcode == Instruction::FMul \|\| opcode == Instruction::FDiv \|\|``opcode == Instruction::FRem) {``for` `(``int` `random = (``int``)llvm::cryptoutils->get_range(10); random < 10;``++random) {``switch` `(llvm::cryptoutils->get_range(3)) {` `// can be improved``case` `0:` `// do nothing``break``;``case` `1:``op = UnaryOperator::CreateFNeg(i->getOperand(0), *var, &*i);``op1 = BinaryOperator::Create(Instruction::FAdd, op,``i->getOperand(1),` `"gen"``, &*i);``break``;``case` `2:``op = BinaryOperator::Create(Instruction::FSub, i->getOperand(0),``i->getOperand(1), *var, &*i);``op1 = BinaryOperator::Create(Instruction::FMul, op,``i->getOperand(1),` `"gen"``, &*i);``break``;``}``}``}``// 整数比较指令ICmp``if` `(opcode == Instruction::ICmp) {` `// Condition (with int)``ICmpInst *currentI = (ICmpInst *)(&i);``switch` `(llvm::cryptoutils->get_range(3)) {` `// must be improved``case` `0:` `// do nothing``break``;``case` `1:``currentI->swapOperands();` `// 交换操作数 (感觉没什么用)``break``;``case` `2:` `// randomly change the predicate``switch` `(llvm::cryptoutils->get_range(10)) {``case` `0:``currentI->setPredicate(ICmpInst::ICMP_EQ);` `// 修改指令条件码``break``;` `// equal``case` `1:``currentI->setPredicate(ICmpInst::ICMP_NE);``break``;` `// not equal``case` `2:``currentI->setPredicate(ICmpInst::ICMP_UGT);``break``;` `// unsigned greater than``case` `3:``currentI->setPredicate(ICmpInst::ICMP_UGE);``break``;` `// unsigned greater or equal``case` `4:``currentI->setPredicate(ICmpInst::ICMP_ULT);``break``;` `// unsigned less than``case` `5:``currentI->setPredicate(ICmpInst::ICMP_ULE);``break``;` `// unsigned less or equal``case` `6:``currentI->setPredicate(ICmpInst::ICMP_SGT);``break``;` `// signed greater than``case` `7:``currentI->setPredicate(ICmpInst::ICMP_SGE);``break``;` `// signed greater or equal``case` `8:``currentI->setPredicate(ICmpInst::ICMP_SLT);``break``;` `// signed less than``case` `9:``currentI->setPredicate(ICmpInst::ICMP_SLE);``break``;` `// signed less or equal``}``break``;``}``}``// 浮点型比较指令FCmp``if` `(opcode == Instruction::FCmp) {` `// Conditions (with float)``FCmpInst *currentI = (FCmpInst *)(&i);``switch` `(llvm::cryptoutils->get_range(3)) {` `// must be improved``case` `0:` `// do nothing``break``;``case` `1:``currentI->swapOperands();``break``;``case` `2:` `// randomly change the predicate``switch` `(llvm::cryptoutils->get_range(10)) {``case` `0:``currentI->setPredicate(FCmpInst::FCMP_OEQ);``break``;` `// ordered and equal``case` `1:``currentI->setPredicate(FCmpInst::FCMP_ONE);``break``;` `// ordered and operands are unequal``case` `2:``currentI->setPredicate(FCmpInst::FCMP_UGT);``break``;` `// unordered or greater than``case` `3:``currentI->setPredicate(FCmpInst::FCMP_UGE);``break``;` `// unordered, or greater than, or equal``case` `4:``currentI->setPredicate(FCmpInst::FCMP_ULT);``break``;` `// unordered or less than``case` `5:``currentI->setPredicate(FCmpInst::FCMP_ULE);``break``;` `// unordered, or less than, or equal``case` `6:``currentI->setPredicate(FCmpInst::FCMP_OGT);``break``;` `// ordered and greater than``case` `7:``currentI->setPredicate(FCmpInst::FCMP_OGE);``break``;` `// ordered and greater than or equal``case` `8:``currentI->setPredicate(FCmpInst::FCMP_OLT);``break``;` `// ordered and less than``case` `9:``currentI->setPredicate(FCmpInst::FCMP_OLE);``break``;` `// ordered or less than, or equal``}``break``;``}``}``}``}``return` `alteredBB;``}` `// end of createAlteredBasicBlock()` |
|-|-|

### BogusControlFlowPass::doF

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899 | `bool` `BogusControlFlowPass::doF(Module &M, Function &F) {``// In this part we extract all always-true predicate and replace them with``// opaque predicate: For this, we declare two global values: x and y, and``// replace the FCMP_TRUE predicate with (y < 10 \|\| x * (x + 1) % 2 == 0) A``// better way to obfuscate the predicates would be welcome. In the meantime``// we will erase the name of the basic blocks, the instructions and the``// functions.``DEBUG_WITH_TYPE(``"gen"``, errs() <<` `"bcf: Starting doFinalization...\n"``);` `Twine *varX =` `new` `Twine(``"x"``);``Twine *varY =` `new` `Twine(``"y"``);``// 创建零常量x1和y1用于后续初始化x和y``Value *x1 = ConstantInt::get(Type::getInt32Ty(M.getContext()), 0,` `false``);``Value *y1 = ConstantInt::get(Type::getInt32Ty(M.getContext()), 0,` `false``);` `// 创建全局变量x和y并初始化为0``GlobalVariable *x =``new` `GlobalVariable(M, Type::getInt32Ty(M.getContext()),` `false``,``GlobalValue::CommonLinkage, (Constant *)x1, *varX);``GlobalVariable *y =``new` `GlobalVariable(M, Type::getInt32Ty(M.getContext()),` `false``,``GlobalValue::CommonLinkage, (Constant *)y1, *varY);` `std::vector<Instruction *> toEdit, toDelete;` `// 待修改和待删除的指令``BinaryOperator *op, *op1 = NULL;``LoadInst *opX, *opY;``ICmpInst *condition, *condition2;``// Looking for the conditions and branches to transform` `// 1. 遍历函数的基本块 保存永真FCmp指令及其条件``for` `(Function::iterator fi = F.begin(), fe = F.end(); fi != fe; ++fi) {``// fi->setName("");``Instruction *tbb = fi->getTerminator();` `// 获取基本块终止符``// 如果是branch分支指令``if` `(tbb->getOpcode() == Instruction::Br) {``BranchInst *br = (BranchInst *)(tbb);``// 如果是条件分支指令``if` `(br->isConditional()) {``FCmpInst *cond = (FCmpInst *)br->getCondition();` `// 获取分支条件,转换为FCmp指令``unsigned opcode = cond->getOpcode();` `// 获取FCmp的操作符``if` `(opcode == Instruction::FCmp) {` `// 如果是FCmp指令``// 如果条件为永真 (bogus中创建的永真FCmp)``if` `(cond->getPredicate() == FCmpInst::FCMP_TRUE) {``// 永真FCmp添加到toDelete, 原条件跳转指令添加到toEdit``toDelete.push_back(cond);` `// The condition``toEdit.push_back(tbb);` `// The branch using the condition``}``}``}``}``}` `// 2. 遍历toEdit中存放的永真FCmp指令 用条件branch替换永真FCmp``for` `(std::vector<Instruction *>::iterator i = toEdit.begin();``i != toEdit.end(); ++i) {` `// 创建条件 if y < 10 \|\| x*(x+1) % 2 == 0 , 并根据该条件创建条件跳转指令``opX =` `new` `LoadInst(Type::getInt32Ty(M.getContext()), (Value *)x,` `""``, (*i));``opY =` `new` `LoadInst(Type::getInt32Ty(M.getContext()), (Value *)y,` `""``, (*i));` `// Sub x, 1``op = BinaryOperator::Create(``Instruction::Sub, (Value *)opX,``ConstantInt::get(Type::getInt32Ty(M.getContext()), 1,` `false``),` `""``, (*i));``// Mul x, op = Mul x, x-1``op1 = BinaryOperator::Create(Instruction::Mul, (Value *)opX, op,` `""``, (*i));``// URem op1, 2 = URem x*(x-1), 2 = x*(x-1)%2``op = BinaryOperator::Create(``Instruction::URem, op1,``ConstantInt::get(Type::getInt32Ty(M.getContext()), 2,` `false``),` `""``, (*i));``// 创建条件码 x*(x-1) % 2 == 0``// ICMP_EQ op, 0 -> x*(x-1)%2 == 0``condition =` `new` `ICmpInst(``(*i), ICmpInst::ICMP_EQ, op,``ConstantInt::get(Type::getInt32Ty(M.getContext()), 0,` `false``));``// 创建条件码 y<10``// ICMP_SLT y, 10``condition2 =` `new` `ICmpInst(``(*i), ICmpInst::ICMP_SLT, opY,``ConstantInt::get(Type::getInt32Ty(M.getContext()), 10,` `false``));``// op1 = Or condition, condition2 -> x*(x-1)%2 == 0 \|\| y < 10``op1 = BinaryOperator::Create(Instruction::Or, (Value *)condition,``(Value *)condition2,` `""``, (*i));` `// 创建新的条件分支branch指令, true进入后继块0, false进入后继块1, 条件码为op1``BranchInst::Create(((BranchInst *)*i)->getSuccessor(0),``((BranchInst *)*i)->getSuccessor(1), (Value *)op1,``((BranchInst *)*i)->getParent());` `// 删除原始的branch指令``(*i)->eraseFromParent();` `// erase the branch``}``// 3. 删除toDelete中存放的永真比较指令``for` `(std::vector<Instruction *>::iterator i = toDelete.begin();``i != toDelete.end(); ++i) {``(*i)->eraseFromParent();``}``return` `true``;``}` |
|-|-|

### Bogus Control Flow 效果分析

#### 测试代码

| 12345 | `#include<stdio.h>``int` `main(){``printf``(``"Hello, Bogus Control Flow!\n"``);``return` `0;``}` |
|-|-|

#### IDA分析

![image](https://bbs.kanxue.com/upload/attach/202511/968342_TK8V4VA3URME4VE.png)

#### main IR

注意: pass默认的bcf_loop=2, 调试时通过--bcf_loop=1参数限制只做一次bogus保证易于分析

混淆前

| 12345678 | `; Function Attrs: noinline nounwind uwtable``define dso_local i32 @main()` `#0 {``entry:``%``retval` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retval, align` `4``%``call` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_0BM@FJMCKOIH@Hello?0?5Bogus?5Control?5Flow?$CB?6?$AA@"``)``ret i32` `0``}` |
|-|-|

混淆后

| 123456789101112131415161718192021222324252627282930313233343536 | `; Function Attrs: noinline nounwind uwtable``define dso_local i32 @main()` `#0 {``entry:``%``0` `=` `load i32, ptr @x.``7``, align` `4``%``1` `=` `load i32, ptr @y.``8``, align` `4``%``2` `=` `sub i32` `%``0``,` `1``%``3` `=` `mul i32` `%``0``,` `%``2``%``4` `=` `urem i32` `%``3``,` `2``%``5` `=` `icmp eq i32` `%``4``,` `0``%``6` `=` `icmp slt i32` `%``1``,` `10``%``7` `=` `or` `i1` `%``5``,` `%``6``br i1` `%``7``, label` `%``originalBB, label` `%``originalBBalteredBB` `originalBB:                                       ; preds` `=` `%``entry,` `%``originalBBalteredBB``%``retval` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retval, align` `4``%``call` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_0BM@FJMCKOIH@Hello?0?5Bogus?5Control?5Flow?$CB?6?$AA@"``)``%``8` `=` `load i32, ptr @x.``7``, align` `4``%``9` `=` `load i32, ptr @y.``8``, align` `4``%``10` `=` `sub i32` `%``8``,` `1``%``11` `=` `mul i32` `%``8``,` `%``10``%``12` `=` `urem i32` `%``11``,` `2``%``13` `=` `icmp eq i32` `%``12``,` `0``%``14` `=` `icmp slt i32` `%``9``,` `10``%``15` `=` `or` `i1` `%``13``,` `%``14``br i1` `%``15``, label` `%``originalBBpart2, label` `%``originalBBalteredBB` `originalBBpart2:                                  ; preds` `=` `%``originalBB``ret i32` `0` `originalBBalteredBB:                              ; preds` `=` `%``originalBB,` `%``entry``%``retvalalteredBB` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retvalalteredBB, align` `4``%``callalteredBB` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_0BM@FJMCKOIH@Hello?0?5Bogus?5Control?5Flow?$CB?6?$AA@"``)``br label` `%``originalBB``}` |
|-|-|

混淆后的结果和开头流程分析时给定的流程类似,此处不过多赘述

## Indirect Branch

功能:将基本块间的条件跳转替换为间接条件跳转

例如if和if-else结构, 无论哪种情况都存在条件真分支和条件假分支

### Indirect Branch 关键流程

![image](https://bbs.kanxue.com/upload/attach/202511/968342_XQS5ATWFF3TKSWQ.png)

### IndirectBranchPass::run

没有封装到函数中,直接于run方法内实现混淆逻辑

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107 | `PreservedAnalyses IndirectBranchPass::run(Module &M, ModuleAnalysisManager &AM) {``if` `(``this``->flag) {``outs() <<` `"[Soule] force.run.IndirectBranchPass\n"``;``}``// 遍历模块中的所有函数``for` `(Function &Fn : M) {``// 判断是否需要混淆``if` `(toObfuscate(flag, &Fn,` `"ibr"``)) {` `// 如果混淆选项指定跳过该函数,则返回``if` `(Options && Options->skipFunction(Fn.getName())) {``continue``;``}` `// 跳过以下情况: 函数为空/具有链接一次的类型/属于启动代码段``if` `(Fn.empty() \|\| Fn.hasLinkOnceLinkage() \|\| Fn.getSection() ==` `".text.startup"``) {``continue``;``}` `// 获取LLVM上下文``LLVMContext &Ctx = Fn.getContext();` `// 初始化成员变量``BBNumbering.clear();``BBTargets.clear();` `// 分裂所有临界边,避免间接分支指令无法处理的情况``// llvm cannot split critical edge from IndirectBrInst``SplitAllCriticalEdges(Fn, CriticalEdgeSplittingOptions(nullptr, nullptr));``// 1. 收集所有条件分支指令的目标地址并为基本块编号``NumberBasicBlock(Fn);` `// 没有可处理的基本块,返回``if` `(BBNumbering.empty()) {``continue``;``}` `// 2. 生成随机秘钥用于加解密``// 获取随机数,用于生成秘钥``uint64_t V = RandomEngine.get_uint64_t();``IntegerType *intType = Type::getInt32Ty(Ctx);``unsigned pointerSize =``Fn.getEntryBlock().getModule()->getDataLayout().getTypeAllocSize(``PointerType::getUnqual(Fn.getContext()));` `// Soule``if` `(pointerSize == 8) {``intType = Type::getInt64Ty(Ctx);``}``// 生成随机加解密秘钥``ConstantInt *EncKey = ConstantInt::get(intType, V,` `false``);``ConstantInt *EncKey1 = ConstantInt::get(intType, -V,` `false``);` `// 获取自定义混淆值 (似乎没作用,此处默认为0)``Value *MySecret = ConstantInt::get(intType, 0,` `true``);` `// 获取零常量``ConstantInt *Zero = ConstantInt::get(intType, 0);``// 3. 创建间接分支目标数组的全局变量``GlobalVariable *DestBBs = getIndirectTargets(Fn, EncKey1);` `// 遍历函数的所有基本块``for` `(``auto` `&BB : Fn) {``// 获取分支指令``auto` `*BI = dyn_cast<BranchInst>(BB.getTerminator());``// 如果是条件分支指令则进行替换 其他分支指令跳过``if` `(BI && BI->isConditional()) {``// 创建IR构建器``IRBuilder<> IRB(BI);` `Value *Cond = BI->getCondition();` `// 获取分支条件``Value *Idx;` `// 间接分支的索引``Value *TIdx, *FIdx;` `// 条件真分支和假分支的索引` `// 4. 获取分支指令后继块编号并根据条件选择索引``// 获取条件真假分支对应的后继基本块编号``TIdx = ConstantInt::get(intType, BBNumbering[BI->getSuccessor(0)]);``FIdx = ConstantInt::get(intType, BBNumbering[BI->getSuccessor(1)]);``// 根据条件选择索引``Idx = IRB.CreateSelect(Cond, TIdx, FIdx);` `// 5. 从全局目标基本块地址表获取目标地址 (加密状态)``// 获取对应偏移处的指针 等价于&DestBBs[0][Idx]``// 参数为: 元素类型,首地址,偏移列表, 其中偏移列表可用于指定多级数组索引``Value *GEP = IRB.CreateGEP(DestBBs->getValueType(), DestBBs, {Zero, Idx});``// 加载目标基本块地址 (加密状态) 参数为: 类型,地址,名称``Value *EncDestAddr = IRB.CreateLoad(GEP->getType(), GEP,` `"EncDestAddr"``);` `// 6. 计算解密密钥并解密目标地址``// 计算解密秘钥``// DecKey = EncKey + MySecret``Value *DecKey = IRB.CreateAdd(EncKey, MySecret);``// 解密目标地址``Value *DestAddr = IRB.CreateGEP(Type::getInt8Ty(Ctx), EncDestAddr, DecKey);` `// 7. 创建间接分支指令并替换原指令``// 创建间接分支指令 指定只存在2个合法分支目标``IndirectBrInst *IBI = IndirectBrInst::Create(DestAddr, 2);``// 添加间接分支的合法目标``IBI->addDestination(BI->getSuccessor(0));``IBI->addDestination(BI->getSuccessor(1));``// 替换原来的分支指令, b变为br指令``ReplaceInstWithInst(BI, IBI);``}``}``}``}``return` `PreservedAnalyses::none();``}` |
|-|-|

### IndirectBranchPass::NumberBasicBlock

功能: 收集函数中所有条件分支指令的目标基本块并分配随机索引

| 12345678910111213141516171819202122232425262728293031 | `void` `IndirectBranchPass::NumberBasicBlock(Function &F) {``// 1. 保存函数中所有条件分支指令的后继基本块(目标基本块)并初始化对应索引为0``// 遍历函数的所有基本块``for` `(``auto` `&BB : F) {``// 检查基本块终结指令是否为分支指令``if` `(``auto` `*BI = dyn_cast<BranchInst>(BB.getTerminator())) {``// 只处理条件分支指令``if` `(BI->isConditional()) {``unsigned N = BI->getNumSuccessors();` `// 获取后继块数量``for` `(unsigned I = 0; I < N; I++) {` `// 遍历所有后继块``BasicBlock *Succ = BI->getSuccessor(I);` `// 获取后继块``if` `(BBNumbering.count(Succ) == 0) {` `// 检查后继块是否处理过``BBTargets.push_back(Succ);` `// 将后继块添加到目标集合``BBNumbering[Succ] = 0;` `// 初始化索引为0, 后续分配``}``}``}``}``}` `// 2. 打乱目标基本块顺序``long` `seed = RandomEngine.get_uint32_t();` `// 生成随机种子``std::default_random_engine e(seed);` `// 创建随机引擎``std::shuffle(BBTargets.begin(), BBTargets.end(), e);` `// 随机打乱目标基本块顺序` `// 3. 为目标基本块分配索引 (递增连续)``unsigned N = 0;``for` `(``auto` `BB : BBTargets) {``BBNumbering[BB] = N++;``}``}` |
|-|-|

### IndirectBranchPass::getIndirectTargets

功能: 创建全局间接分支目标基本块地址数组,加密并保存间接分支目标基本块地址

| 1234567891011121314151617181920212223242526272829303132333435 | `GlobalVariable *IndirectBranchPass::getIndirectTargets(Function &F, ConstantInt *EncKey) {``// 1. 生成全局变量名并检查是否已存在``// 生成全局变量名称：函数名 + "_IndirectBrTargets"``std::string GVName(F.getName().str() +` `"_IndirectBrTargets"``);``// 检查是否已存在同名全局变量``GlobalVariable *GV = F.getParent()->getNamedGlobal(GVName);``if` `(GV)``return` `GV;` `// 2. 遍历所有分支目标基本块地址并加密,存储到数组中``// 创建加密地址数组``std::vector<Constant *> Elements;` `// 遍历所有目标基本块``for` `(``const` `auto` `BB : BBTargets) {``// 获取基本块地址并转换为int8*类型``Constant *CE = ConstantExpr::getBitCast(BlockAddress::get(BB),``llvm::PointerType::get(Type::getInt8Ty(F.getContext()),0));``// 对地址进行加密：CE + EncKey``CE = ConstantExpr::getGetElementPtr(Type::getInt8Ty(F.getContext()), CE, EncKey);``Elements.push_back(CE);``}` `// 3. 创建全局变量数组,复制第2步中的动态数组``// 创建数组类型：元素类型为i8*，大小为元素数量``ArrayType *ATy =``ArrayType::get(llvm::PointerType::get(Type::getInt8Ty(F.getContext()),0), Elements.size());``// 创建数组常量``Constant *CA = ConstantArray::get(ATy, ArrayRef<Constant *>(Elements));``// 创建全局变量``GV =` `new` `GlobalVariable(*F.getParent(), ATy,` `false``,``GlobalValue::LinkageTypes::PrivateLinkage, CA, GVName);``// 添加到compiler.used防止被优化器删除``appendToCompilerUsed(*F.getParent(), {GV});``return` `GV;``}` |
|-|-|

### llvm::SplitAllCriticalEdges

这是llvm的一个工具类方法, 定义于: ~\llvm\lib\Transforms\Utils\BasicBlockUtils.cpp

| 12345678910111213 | `unsigned``llvm::SplitAllCriticalEdges(Function &F,``const` `CriticalEdgeSplittingOptions &Options) {``unsigned NumBroken = 0;``for` `(BasicBlock &BB : F) {``Instruction *TI = BB.getTerminator();` `// 获取基本块终止指令``if` `(TI->getNumSuccessors() > 1 && !isa<IndirectBrInst>(TI))` `// 如果有多个后继且不是间接分支指令``for` `(unsigned i = 0, e = TI->getNumSuccessors(); i != e; ++i)` `// 遍历所有后继块``if` `(SplitCriticalEdge(TI, i, Options))` `// 尝试拆分第i个后继的边``++NumBroken;` `// 拆分成功,计数+1``}``return` `NumBroken;``}` |
|-|-|

该函数用于分离临界边,那么什么是临界边,为什么要分离临界边?

临界边: 从一个具有多个后继的块(即分支块), 到一个具有多个前驱的块(即汇聚块)的边

一条边 BB → Succ 是临界边，当且仅当:

- BB 有 多个后继 (BB->getNumSuccessors() > 1)
- Succ 有 多个前驱 (Succ->getNumberOfPredecessors() > 1)

临界边在进行某些变换时（比如插入新块、拆分控制流、混淆等）会带来困难

拆分临界边的操作及其作用:

- 拆分实际上是在临界边中插入新的基本块
- 后续操作基于新基本块,以保证不对其他边造成影响

例如C有多个后继,D有多个前驱, 所以C->D是临界边

- 假设修改C块末尾的br指令为indirectbr, 很显然会影响C->E, 破坏原有语义
- 假设修改D的入口指令, 显然会影响B->D, 破坏原有语义

所以解决方法是拆分临界边,在C->D之间插入新块D', 即C->D'->D

之后的操作可基于D'进行, 无论修改D'的入口还是出口代码均不会影响其他边

![CriticalEdges](https://bbs.kanxue.com/upload/attach/202511/968342_8DX2SPKQGCX8ZHV.png)

参考[llvm进阶（1）SplitAllCriticalEdges（关键边切割的艺术）](https://mp.weixin.qq.com/s?__biz=MjM5NDMzMzAwNQ==&amp;mid=2247485973&amp;idx=1&amp;sn=b6a48af4b7c214227eb487f951aba772&amp;poc_token=HJvjAmmjnhLPbLamlPtvW0VeZ5mY6NIlkT6XAxDX)

### Indirect Branch 效果分析

#### 测试代码

| 123456789101112 | `#include <stdio.h>``int` `main(){``int` `a=33,b=66;``if``(a==b){``printf``(``"%d == %d"``,a,b);``}``else` `if``(a>b){``printf``(``"%d > %d"``,a,b);``}``else``{``printf``(``"%d < %d"``,a,b);``}``return` `0;``}` |
|-|-|

#### IDA分析

![image](https://bbs.kanxue.com/upload/attach/202511/968342_4ADQDMAXHVY7RVD.png)

#### main IR

混淆前的main函数

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344 | `; Function Attrs: noinline nounwind uwtable``define dso_local i32 @main()` `#0 {``entry:``%``retval` `=` `alloca i32, align` `4``%``a` `=` `alloca i32, align` `4``%``b` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retval, align` `4``store i32` `33``, ptr` `%``a, align` `4``store i32` `66``, ptr` `%``b, align` `4``%``0` `=` `load i32, ptr` `%``a, align` `4``%``1` `=` `load i32, ptr` `%``b, align` `4``%``cmp` `=` `icmp eq i32` `%``0``,` `%``1``br i1` `%``cmp``, label` `%``if``.then, label` `%``if``.``else` `if``.then:                                          ; preds` `=` `%``entry``%``2` `=` `load i32, ptr` `%``b, align` `4``%``3` `=` `load i32, ptr` `%``a, align` `4``%``call` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_08DEPMFGLC@?$CFd?5?$DN?$DN?5?$CFd?$AA@"``, i32 noundef` `%``3``, i32 noundef` `%``2``)``br label` `%``if``.end6` `if``.``else``:                                          ; preds` `=` `%``entry``%``4` `=` `load i32, ptr` `%``a, align` `4``%``5` `=` `load i32, ptr` `%``b, align` `4``%``cmp1` `=` `icmp sgt i32` `%``4``,` `%``5``br i1` `%``cmp1, label` `%``if``.then2, label` `%``if``.else4` `if``.then2:                                         ; preds` `=` `%``if``.``else``%``6` `=` `load i32, ptr` `%``b, align` `4``%``7` `=` `load i32, ptr` `%``a, align` `4``%``call3` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_07NCCKKCBF@?$CFd?5?$DO?5?$CFd?$AA@"``, i32 noundef` `%``7``, i32 noundef` `%``6``)``br label` `%``if``.end` `if``.else4:                                         ; preds` `=` `%``if``.``else``%``8` `=` `load i32, ptr` `%``b, align` `4``%``9` `=` `load i32, ptr` `%``a, align` `4``%``call5` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_07KIOKPBHF@?$CFd?5?$DM?5?$CFd?$AA@"``, i32 noundef` `%``9``, i32 noundef` `%``8``)``br label` `%``if``.end` `if``.end:                                           ; preds` `=` `%``if``.else4,` `%``if``.then2``br label` `%``if``.end6` `if``.end6:                                          ; preds` `=` `%``if``.end,` `%``if``.then``ret i32` `0``}` |
|-|-|

混淆后的main函数

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152 | `; Function Attrs: noinline nounwind uwtable``define dso_local i32 @main()` `#0 {``entry:``%``retval` `=` `alloca i32, align` `4``%``a` `=` `alloca i32, align` `4``%``b` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retval, align` `4``store i32` `33``, ptr` `%``a, align` `4``store i32` `66``, ptr` `%``b, align` `4``%``0` `=` `load i32, ptr` `%``a, align` `4``%``1` `=` `load i32, ptr` `%``b, align` `4``%``cmp` `=` `icmp eq i32` `%``0``,` `%``1``%``2` `=` `select i1` `%``cmp``, i64` `0``, i64` `1``%``3` `=` `getelementptr [``4` `x ptr], ptr @main_IndirectBrTargets, i64` `0``, i64` `%``2``%``EncDestAddr` `=` `load ptr, ptr` `%``3``, align` `8``%``4` `=` `getelementptr i8, ptr` `%``EncDestAddr, i64` `-``8909362643113078243``indirectbr ptr` `%``4``, [label` `%``if``.then, label` `%``if``.``else``]` `if``.then:                                          ; preds` `=` `%``entry``%``5` `=` `load i32, ptr` `%``b, align` `4``%``6` `=` `load i32, ptr` `%``a, align` `4``%``call` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_08DEPMFGLC@?$CFd?5?$DN?$DN?5?$CFd?$AA@"``, i32 noundef` `%``6``, i32 noundef` `%``5``)``br label` `%``if``.end6` `if``.``else``:                                          ; preds` `=` `%``entry``%``7` `=` `load i32, ptr` `%``a, align` `4``%``8` `=` `load i32, ptr` `%``b, align` `4``%``cmp1` `=` `icmp sgt i32` `%``7``,` `%``8``%``9` `=` `select i1` `%``cmp1, i64` `3``, i64` `2``%``10` `=` `getelementptr [``4` `x ptr], ptr @main_IndirectBrTargets, i64` `0``, i64` `%``9``%``EncDestAddr1` `=` `load ptr, ptr` `%``10``, align` `8``%``11` `=` `getelementptr i8, ptr` `%``EncDestAddr1, i64` `-``8909362643113078243``indirectbr ptr` `%``11``, [label` `%``if``.then2, label` `%``if``.else4]` `if``.then2:                                         ; preds` `=` `%``if``.``else``%``12` `=` `load i32, ptr` `%``b, align` `4``%``13` `=` `load i32, ptr` `%``a, align` `4``%``call3` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_07NCCKKCBF@?$CFd?5?$DO?5?$CFd?$AA@"``, i32 noundef` `%``13``, i32 noundef` `%``12``)``br label` `%``if``.end` `if``.else4:                                         ; preds` `=` `%``if``.``else``%``14` `=` `load i32, ptr` `%``b, align` `4``%``15` `=` `load i32, ptr` `%``a, align` `4``%``call5` `=` `call i32 (ptr, ...) @printf(ptr noundef @``"??_C@_07KIOKPBHF@?$CFd?5?$DM?5?$CFd?$AA@"``, i32 noundef` `%``15``, i32 noundef` `%``14``)``br label` `%``if``.end` `if``.end:                                           ; preds` `=` `%``if``.else4,` `%``if``.then2``br label` `%``if``.end6` `if``.end6:                                          ; preds` `=` `%``if``.end,` `%``if``.then``ret i32` `0``}` |
|-|-|

#### entry IR

关于entry块

| 123456789101112131415161718192021222324252627282930 | `Current instruction:   br i1` `%``cmp``, label` `%``if``.then, label` `%``if``.``else``Basic Block Before optimization:``entry:``%``retval` `=` `alloca i32, align` `4``%``a` `=` `alloca i32, align` `4``%``b` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retval, align` `4``store i32` `33``, ptr` `%``a, align` `4``store i32` `66``, ptr` `%``b, align` `4``%``0` `=` `load i32, ptr` `%``a, align` `4``%``1` `=` `load i32, ptr` `%``b, align` `4``%``cmp` `=` `icmp eq i32` `%``0``,` `%``1``br i1` `%``cmp``, label` `%``if``.then, label` `%``if``.``else` `Basic Block After optimization:``entry:``%``retval` `=` `alloca i32, align` `4``%``a` `=` `alloca i32, align` `4``%``b` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retval, align` `4``store i32` `33``, ptr` `%``a, align` `4``store i32` `66``, ptr` `%``b, align` `4``%``0` `=` `load i32, ptr` `%``a, align` `4``%``1` `=` `load i32, ptr` `%``b, align` `4``%``cmp` `=` `icmp eq i32` `%``0``,` `%``1``%``2` `=` `select i1` `%``cmp``, i64` `0``, i64` `1``%``3` `=` `getelementptr [``4` `x ptr], ptr @main_IndirectBrTargets, i64` `0``, i64` `%``2``%``EncDestAddr` `=` `load ptr, ptr` `%``3``, align` `8``%``4` `=` `getelementptr i8, ptr` `%``EncDestAddr, i64` `-``8909362643113078243``indirectbr ptr` `%``4``, [label` `%``if``.then, label` `%``if``.``else``]` |
|-|-|

不难发现关键点为 entry块末尾的br条件分支指令

| 12 | `%``cmp` `=` `icmp eq i32` `%``0``,` `%``1``br i1` `%``cmp``, label` `%``if``.then, label` `%``if``.``else` |
|-|-|

被替换成

| 123456 | `%``cmp` `=` `icmp eq i32` `%``0``,` `%``1``%``2` `=` `select i1` `%``cmp``, i64` `0``, i64` `1``%``3` `=` `getelementptr [``4` `x ptr], ptr @main_IndirectBrTargets, i64` `0``, i64` `%``2``%``EncDestAddr` `=` `load ptr, ptr` `%``3``, align` `8``%``4` `=` `getelementptr i8, ptr` `%``EncDestAddr, i64` `-``8909362643113078243``indirectbr ptr` `%``4``, [label` `%``if``.then, label` `%``if``.``else``]` |
|-|-|

逐步解析以上代码:

1. " %cmp = icmp eq i32 %0, %1 "

对应测试代码中的 if(a==b){...}
2. " %2 = select i1 %cmp, i64 0, i64 1 "

对应Pass中如下代码

先从原始的br指令中获取后继的条件真和条件假对应的基本块地址

再根据地址从BBNumbering中获取对应基本块索引

最后根据原始br指令的跳转条件, 创建select指令, 根据结果选择不同索引赋给Idx

| 12345678910 | `// 获取原br指令条件,声明相关变量``Value *Cond = BI->getCondition();``Value *Idx;``Value *TIdx, *FIdx;` `// 获取原br指令后继基本块索引``TIdx = ConstantInt::get(intType, BBNumbering[BI->getSuccessor(0)]);``FIdx = ConstantInt::get(intType, BBNumbering[BI->getSuccessor(1)]);``// 根据条件选择索引``Idx = IRB.CreateSelect(Cond, TIdx, FIdx);` |
|-|-|
3. " %3 = getelementptr [4 x ptr], ptr @main_IndirectBrTargets, i64 0, i64 %2 "
 " %EncDestAddr = load ptr, ptr %3, align 8 "

对应Pass中如下代码

先使用IRB.CreateGEP从目标基本块地址表DestBBs中获取Idx对应的元素地址

再通过IRB.CreateLoad从GEP指针中加载得到目标基本块地址 (加密状态)

等价于访问数组和解引用指针

| 1234 | `// GEP = &DestBBs[0][Idx]``Value *GEP = IRB.CreateGEP(DestBBs->getValueType(), DestBBs, {Zero, Idx});``// EncDestAddr = *GEP``Value *EncDestAddr = IRB.CreateLoad(GEP->getType(), GEP,` `"EncDestAddr"``);` |
|-|-|
4. " %4 = getelementptr i8, ptr %EncDestAddr, i64 -8909362643113078243 "

对应Pass的如下代码

先计算解密密钥, 后解密目标地址

| 1234 | `// DecKey = EncKey + MySecret = EncKey``Value *DecKey = IRB.CreateAdd(EncKey, MySecret);``// DestAddr = EncDestAddr + DecKey = EncDestAddr + EncKey``Value *DestAddr = IRB.CreateGEP(Type::getInt8Ty(Ctx), EncDestAddr, DecKey);` |
|-|-|

注意此处的EncKey实际上是解密密钥

Pass中使用EncKey的相反数EncKey1作为加密秘钥生成间接分支目标地址全局表

| 123456789 | `uint64_t V = RandomEngine.get_uint64_t();``// ...... 根据cpu架构计算intType指针大小``ConstantInt *EncKey = ConstantInt::get(intType, V,` `false``);``ConstantInt *EncKey1 = ConstantInt::get(intType, -V,` `false``);` `Value *MySecret = ConstantInt::get(intType, 0,` `true``);``ConstantInt *Zero = ConstantInt::get(intType, 0);` `GlobalVariable *DestBBs = getIndirectTargets(Fn, EncKey1);` |
|-|-|
5. " indirectbr ptr %4, [label %if.then, label %if.else] "

对应Pass代码如下

| 1234567 | `// 创建IndirectBr指令, indirectbr DestAddr, 指定存在2个合法跳转目标``IndirectBrInst *IBI = IndirectBrInst::Create(DestAddr, 2);``// 添加合法跳转目标 实际上是原br分支指令的后继基本块地址``IBI->addDestination(BI->getSuccessor(0));``IBI->addDestination(BI->getSuccessor(1));``// 替换原指令``ReplaceInstWithInst(BI, IBI);` |
|-|-|

注意点:

1. IRB.CreateGEP

该函数用于计算元素指针, 本质是根据首地址+偏移计算目标地址

函数原形:

| 1234 | `// 参数1: 数据类型指针, 参数2: 数据首地址指针, 参数3: 索引列表` `Value *CreateGEP(Type *Ty, Value *Ptr, ArrayRef<Value *> IdxList,``const` `Twine &Name =` `""``,``GEPNoWrapFlags NW = GEPNoWrapFlags::none())` |
|-|-|

值得一提的是通过参数1数据类型和参数3索引列表, 可实现多级数组或结构体访问

例如第一次调用时传入"DestBBs->getValueType()" 和 "{Zero, Idx}" 对应 "&DestBBs[0][Idx]"

而第二次调用时传入"Type::getInt8Ty(Ctx)" 和 "DecKey" 对应 "EncDestAddr+DecKey"
2. IndirectBrInst

indirectbr指令可以有多个合法目标地址, 但具体时刻的真实目标地址只有一个

#### if.else IR

if.else块,同上类似

| 123456789101112131415161718 | `Current instruction:   br i1` `%``cmp1, label` `%``if``.then2, label` `%``if``.else4``Basic Block Before optimization:``if``.``else``:                                          ; preds` `=` `%``entry``%``7` `=` `load i32, ptr` `%``a, align` `4``%``8` `=` `load i32, ptr` `%``b, align` `4``%``cmp1` `=` `icmp sgt i32` `%``7``,` `%``8``br i1` `%``cmp1, label` `%``if``.then2, label` `%``if``.else4` `Basic Block After optimization:``if``.``else``:                                          ; preds` `=` `%``entry``%``7` `=` `load i32, ptr` `%``a, align` `4``%``8` `=` `load i32, ptr` `%``b, align` `4``%``cmp1` `=` `icmp sgt i32` `%``7``,` `%``8``%``9` `=` `select i1` `%``cmp1, i64` `3``, i64` `2``%``10` `=` `getelementptr [``4` `x ptr], ptr @main_IndirectBrTargets, i64` `0``, i64` `%``9``%``EncDestAddr1` `=` `load ptr, ptr` `%``10``, align` `8``%``11` `=` `getelementptr i8, ptr` `%``EncDestAddr1, i64` `-``8909362643113078243``indirectbr ptr` `%``11``, [label` `%``if``.then2, label` `%``if``.else4]` |
|-|-|

## Indirect Call

功能: 加密函数调用地址, 将bl指令替换为blr指令

### Indirect Call 关键流程

和Indirect Branch基本结构类似, 更加简单

![IndirectCall](https://bbs.kanxue.com/upload/attach/202511/968342_UZG2N5PR3TET2BF.png)

### IndirectCallPass::doIndirctCall

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100 | `bool` `IndirectCallPass::doIndirctCall(Function &Fn){``if` `(Options && Options->skipFunction(Fn.getName())) {``return` `false``;``}` `LLVMContext &Ctx = Fn.getContext();` `CalleeNumbering.clear();` `// 清空被调函数编号``Callees.clear();` `// 清空被调函数集合``CallSites.clear();` `// 清空调用指令集合` `// 1. 收集函数中的直接调用点并存储到数组,为所有被调函数地址编号``NumberCallees(Fn);`  `// 如果没有被调函数则返回``if` `(Callees.empty()) {``return` `false``;``}` `// 2. 根据目标平台类型, 生成加解密秘钥``// 获取随机数,用于生成秘钥``uint64_t V = RandomEngine.get_uint64_t();``IntegerType *intType = Type::getInt32Ty(Ctx);` `// 根据目标平台指针大小选择整数的类型``unsigned pointerSize = Fn.getEntryBlock().getModule()->getDataLayout().getTypeAllocSize(PointerType::getUnqual(Fn.getContext()));` `// Soule``if` `(pointerSize == 8) {``intType = Type::getInt64Ty(Ctx);``}``// 生成加密和解密秘钥 互为相反数``ConstantInt *EncKey = ConstantInt::get(intType, V,` `false``);``ConstantInt *EncKey1 = ConstantInt::get(intType, -V,` `false``);` `Value *MySecret = ConstantInt::get(intType, 0,` `true``);` `// 获取自定义混淆值``ConstantInt *Zero = ConstantInt::get(intType, 0);` `// 创建零常量`  `// 3. 创建加密函数地址数组全局变量``GlobalVariable *Targets = getIndirectCallees(Fn, EncKey1);`  `// 遍历调用指令集合``for` `(``auto` `CI : CallSites) {``SmallVector<Value *, 8> Args;` `// 参数集合``SmallVector<AttributeSet, 8> ArgAttrVec;` `// 参数属性集合` `CallBase *CB = CI;` `// 当前调用指令的高级表示` `// 获取被调函数及其类型``Function *Callee = CB->getCalledFunction();``FunctionType *FTy = CB->getFunctionType();` `IRBuilder<> IRB(CB);` `// 创建IR构建器, 定位在当前指令前` `// 清空参数和参数属性集合``Args.clear();``ArgAttrVec.clear();` `// 4. 获取目标函数地址(加密状态)``// 获取被调函数在全局被调函数目标地址表中的索引``Value *Idx = ConstantInt::get(intType, CalleeNumbering[CB->getCalledFunction()]);``// 通过全局被调函数目标地址表获取目标函数地址项指针 &Targets[0][Idx]``Value *GEP = IRB.CreateGEP(Targets->getValueType(), Targets, {Zero, Idx});``// 加载目标函数地址(加密状态) *GEP = *&Targets[0][Idx] = Targets[0][Idx]``LoadInst *EncDestAddr = IRB.CreateLoad(GEP->getType(), GEP, CI->getName());` `// 5. 保存函数参数 (似乎没作用,函数参数列表和函数地址没关系)` `// 获取原始的调用属性列表``const` `AttributeList &CallPAL = CB->getAttributes();``auto` `I = CB->arg_begin();` `// 设置参数迭代器``unsigned i = 0;` `// 遍历并处理固定参数 (函数声明中明确指定的参数)``for` `(unsigned e = FTy->getNumParams(); i != e; ++I, ++i) {``Args.push_back(*I);` `// 将参数添加到参数集合``AttributeSet Attrs = CallPAL.getParamAttrs(i);` `// 获取参数属性``ArgAttrVec.push_back(Attrs);` `// 将参数属性添加到集合``}` `// 遍历并处理剩余参数, 针对可变参数函数 (如printf)``for` `(``auto` `E = CB->arg_end(); I != E; ++I, ++i) {``Args.push_back(*I);` `// 功能同上``ArgAttrVec.push_back(CallPAL.getParamAttrs(i));``}` `// 6. 解密目标函数地址``// 计算解密秘钥 Secret = EncKey + MySecret = EncKey = V``Value *Secret = IRB.CreateAdd(EncKey, MySecret);``// 解密函数地址 DestAddr = EncDestAddr + Secret = EncDestAddr + V``Value *DestAddr = IRB.CreateGEP(Type::getInt8Ty(Ctx), EncDestAddr, Secret);` `// 7. 创建函数指针并替换原始call指令操作数``// 创建函数指针 将int8*指针转换为具体的函数指针``Value *FnPtr = IRB.CreateBitCast(DestAddr, FTy->getPointerTo());``// 设置新的函数名称``FnPtr->setName(``"Call_"` `+ Callee->getName());``// 替换call指令, 将直接调用替换为间接调用``CB->setCalledOperand(FnPtr);``}` `return` `true``;``}` |
|-|-|

### IndirectCallPass::NumberCallees

功能: 收集函数中的直接调用点, 并为被调函数编号

| 1234567891011121314151617181920212223242526272829 | `void` `IndirectCallPass::NumberCallees(Function &F){``// 遍历函数所有基本块``for` `(``auto` `&BB : F){``// 遍历基本块中所有指令``for` `(``auto` `&I : BB){``// 1. 检查是否为call指令``if` `(dyn_cast<CallInst>(&I)){``CallSite CS(&I);` `// 创建CallSite便于处理调用指令``Function *Callee = CS.getCalledFunction();` `// 获取被调函数指针``if` `(Callee == nullptr){``continue``;``}``// 跳过llvm内建函数``if` `(Callee->isIntrinsic()){``continue``;``}``// 2. 保存call指令``CallSites.push_back((CallInst *)&I);``// 3. 为保存被调函数地址并分配唯一编号``if` `(CalleeNumbering.count(Callee) == 0){``// 利用被调函数数组大小对被调函数编号, 每次自增1``CalleeNumbering[Callee] = Callees.size();``// 保存被调函数地址``Callees.push_back(Callee);``}``}``}``}``}` |
|-|-|

### IndirectCallPass::getIndirectCallees

功能: 创建/获取用于存储加密函数地址的全局变量指针

1. 生成并检查被调函数地址数组对应全局变量名
2. 遍历被调函数地址数组, 对每个被调函数地址进行混淆
3. 创建被调函数地址数组全局变量, 添加到compiler.used防止被优化
4. 返回创建的全局变量

| 1234567891011121314151617181920212223242526272829303132 | `GlobalVariable *IndirectCallPass::getIndirectCallees(Function &F, ConstantInt *EncKey){``// 1. 生成全局变量名并检查是否已存在``// 全局变量名称=函数名+后缀``std::string GVName(F.getName().str() +` `"_IndirectCallees"``);``// 检查是否存在同名全局变量,若存在则直接返回``GlobalVariable *GV = F.getParent()->getNamedGlobal(GVName);``if` `(GV){``return` `GV;``}` `// 2. 遍历所有被调函数地址并加密, 存储到动态数组中``std::vector<Constant *> Elements;``for` `(``auto` `Callee : Callees){``// 将函数指针转换为int8*类型(即byte*)``Constant *CE = ConstantExpr::getBitCast(Callee, llvm::PointerType::get(Type::getInt8Ty(F.getContext()),0));``// 执行函数地址加密, CE=CE+EncKey, 加密地址=原地址+偏移秘钥``CE = ConstantExpr::getGetElementPtr(Type::getInt8Ty(F.getContext()), CE, EncKey);``Elements.push_back(CE);``}` `//3. 创建全局变量数组, 复制第2步中的动态数组``// 创建数组类型, 元素为int8*, 大小为被调函数数量``ArrayType *ATy = ArrayType::get(llvm::PointerType::get(Type::getInt8Ty(F.getContext()),0), Elements.size());``// 创建被钓函数地址数组常量 vector转换为ArrayRef``Constant *CA = ConstantArray::get(ATy, ArrayRef<Constant *>(Elements));``// 创建全局变量``// 参数: 所属模块, 变量类型, 是否为常量, 私有链接, 初始值, 变量名``GV =` `new` `GlobalVariable(*F.getParent(), ATy,` `false``, GlobalValue::LinkageTypes::PrivateLinkage, CA, GVName);``// 添加到compiler.used防止被优化器opt删除``appendToCompilerUsed(*F.getParent(), {GV});``return` `GV;``}` |
|-|-|

### Indirect Call 效果分析

#### 测试代码

| 12345678910111213141516 | `#include<stdio.h>``void` `func1(){``printf``(``"func1 is called!"``);``}``void` `func2(){``printf``(``"func2 is called!"``);``}``void` `func3(){``printf``(``"func3 is called!"``);``}``int` `main(){``func1();``func2();``func3();``return` `0;``}` |
|-|-|

#### IDA分析

![image](https://bbs.kanxue.com/upload/attach/202511/968342_35RTPZH4VKFYQVH.png)

#### main IR

混淆前

| 12345678910 | `; Function Attrs: noinline nounwind uwtable``define dso_local i32 @main()` `#0 {``entry:``%``retval` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retval, align` `4``call void @func1()``call void @func2()``call void @func3()``ret i32` `0``}` |
|-|-|

混淆后

| 12345678910111213141516 | `; Function Attrs: noinline nounwind uwtable``define dso_local i32 @main()` `#0 {``entry:``%``retval` `=` `alloca i32, align` `4``store i32` `0``, ptr` `%``retval, align` `4``%``0` `=` `load ptr, ptr @main_IndirectCallees, align` `8``%``Call_func1` `=` `getelementptr i8, ptr` `%``0``, i64` `-``7628271351554987263``call void` `%``Call_func1()``%``1` `=` `load ptr, ptr getelementptr ([``3` `x ptr], ptr @main_IndirectCallees, i64` `0``, i64` `1``), align` `8``%``Call_func2` `=` `getelementptr i8, ptr` `%``1``, i64` `-``7628271351554987263``call void` `%``Call_func2()``%``2` `=` `load ptr, ptr getelementptr ([``3` `x ptr], ptr @main_IndirectCallees, i64` `0``, i64` `2``), align` `8``%``Call_func3` `=` `getelementptr i8, ptr` `%``2``, i64` `-``7628271351554987263``call void` `%``Call_func3()``ret i32` `0``}` |
|-|-|

不难看出结构基本类似, 以func1为例:

| 1 | `call void @func1()` |
|-|-|

被替换为

| 123 | `%``0` `=` `load ptr, ptr @main_IndirectCallees, align` `8``%``Call_func1` `=` `getelementptr i8, ptr` `%``0``, i64` `-``7628271351554987263``call void` `%``Call_func1()` |
|-|-|

以上代码逻辑非常简单:

1. 获取main的被调函数间接跳转地址表main_IndirectCallees指针
2. 计算被调函数真实跳转地址 Call_func=main_IndirectCallees+DecryptKey
3. 调用被调函数

# 结语

从LLVM再到OLLVM, 混淆的核心基于LLVM的Pass机制, 想深入OLLVM则需要学习LLVM, 从而实现自定义的混淆pass

在此推荐 [Getting Started with LLVM Core Libraries（中文版）](https://getting-started-with-llvm-core-libraries-zh-cn.readthedocs.io/zh-cn/latest/)和《LLVM编译器原理与实践》作者: 吴建明 吴一昊

本文的不足之处:

- LLVM基础部分没有系统性深入讲解, 仅介绍了基本的编译和使用
- 以Windows平台为主, 相较其他平台更容易踩坑
- 未实现脱离LLVM源码编译Obfuscation Pass

大部分文章基于老版本Pass管理器脱离llvm项目源码, 暂时没看到涉及新版Pass管理器的脱离案例

每次调试都会重新编译项目, 虽然调试时改动不大, 但总觉得不够优雅

使用时如果添加其他Pass也会影响整个项目, 有待改进

由于本文知识水平有限, 如有其他不足或补充之处望师傅们及时指出

下篇文章将基于本文, 总结OLLVM去混淆的各种方案并实战具体样本 (立个新坑flag)

# References

相关资料:

[[原创]llvm学习笔记——llvm基础](https://bbs.kanxue.com/thread-279624.htm)

[OLLVM混淆源码解读](https://bbs.kanxue.com/thread-282175.htm)

[[原创] OLLVM 攻略笔记](https://bbs.kanxue.com/thread-286256.htm)

[LLVM 全面解析：NDK 为什么离不开它？如何亲手编译调试 clang](https://cyrus-studio.github.io/blog/posts/llvm-%E5%85%A8%E9%9D%A2%E8%A7%A3%E6%9E%90ndk-%E4%B8%BA%E4%BB%80%E4%B9%88%E7%A6%BB%E4%B8%8D%E5%BC%80%E5%AE%83%E5%A6%82%E4%BD%95%E4%BA%B2%E6%89%8B%E7%BC%96%E8%AF%91%E8%B0%83%E8%AF%95-clang/)

[LLVM 不止能编译！自定义 Pass + 定制 clang 实现函数名加密](https://cyrus-studio.github.io/blog/posts/llvm-%E4%B8%8D%E6%AD%A2%E8%83%BD%E7%BC%96%E8%AF%91%E8%87%AA%E5%AE%9A%E4%B9%89-pass-+-%E5%AE%9A%E5%88%B6-clang-%E5%AE%9E%E7%8E%B0%E5%87%BD%E6%95%B0%E5%90%8D%E5%8A%A0%E5%AF%86/)

[OLLVM 移植 LLVM 18 实战，轻松实现 C&C++ 代码混淆](https://cyrus-studio.github.io/blog/posts/ollvm-%E7%A7%BB%E6%A4%8D-llvm-18-%E5%AE%9E%E6%88%98%E8%BD%BB%E6%9D%BE%E5%AE%9E%E7%8E%B0-cc++-%E4%BB%A3%E7%A0%81%E6%B7%B7%E6%B7%86/)

[别让 so 裸奔！移植 OLLVM 到 NDK 并集成到 Android Studio](https://cyrus-studio.github.io/blog/posts/%E5%88%AB%E8%AE%A9-so-%E8%A3%B8%E5%A5%94%E7%A7%BB%E6%A4%8D-ollvm-%E5%88%B0-ndk-%E5%B9%B6%E9%9B%86%E6%88%90%E5%88%B0-android-studio/)

OLLVM相关项目:

注: 旧版Pass管理器的Pass文件位于 "llvm/lib/Transforms"; 新版Pass管理器的Pass位于 "llvm/lib/Passes"

| 项目名 | 描述 | Obfuscation位置 |
|-|-|-|
| [obfuscator](https://github.com/obfuscator-llvm/obfuscator) | 梦开始的地方 | Transforms |
| [goron](https://github.com/amimo/goron) | 经典项目,似乎最早实现IndirectBranch/Call | Transforms |
| [ollvm17](https://github.com/DreamSoule/ollvm17) | 经典项目,很多项目基于此项目移植 | Passes |
| [Hikari (Arkari)](https://github.com/KomiMoe/Hikari) | 支持多种混淆方式,包括间接跳转 | Transforms |
| [Polaris-Obfuscator](https://github.com/za233/Polaris-Obfuscator) | 支持多种强混淆方式,除IR外还支持MIR干扰反汇编器 | Transforms |
| [SsagePass](https://github.com/SsageParuders/SsagePass) | 实现了基于虚拟机的控制流平坦化 | - |
| [xVMP](https://github.com/GANGE666/xVMP) | 基于LLVM IR的VMP | Transforms |

---

# 回复

## 回复 by 逆天而行 (#2)

*2025-11-3 13:51*

整理的太全面啦！！！

## 回复 by 东方玻璃 (#3)

*2025-11-3 14:31*

>
> [逆天而行](https://bbs.kanxue.com/user-957038.htm)
>
>  整理的太全面啦！！！
>
>

站在巨人的肩膀上![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by 孤独的街 (#4)

*2025-11-3 15:14*

全面的知识点，感谢分享

## 回复 by ngiokweng (#5)

*2025-11-3 18:07*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  站在巨人的肩膀上[em_065]
>
>

站在巨人的JB上![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by 东方玻璃 (#6)

*2025-11-3 18:16*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  站在巨人的JB上[em_065]
>
>

让我站站![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by kkte (#7)

*2025-11-4 11:36*

太强了，cv开始

## 回复 by Whoami默 (#8)

*2025-11-4 15:52*

32G内存都编译不了llvm吗？我已经失败好几次了

## 回复 by 东方玻璃 (#9)

*2025-11-4 17:11*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Whoami默](https://bbs.kanxue.com/user-788084.htm)
>
>  32G内存都编译不了llvm吗？我已经失败好几次了
>
>
>

内存要求不高,我mac 16g都可以,存储最好预留150G+

## 回复 by koflfy (#10)

*2025-11-5 19:11*

mark

## 回复 by MsScotch (#11)

*2025-11-5 22:29*

用上了，用上了，感谢大佬

## 回复 by Whoami默 (#12)

*2025-11-8 16:00*

期待出下一篇反混淆文章

## 回复 by Whoami默 (#13)

*2025-11-8 17:24*

-icall也可以看看，应该是太简单，所以没讲![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by Whoami默 (#14)

*2025-11-8 17:26*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Whoami默](https://bbs.kanxue.com/user-788084.htm)
>
>  -icall也可以看看，应该是太简单，所以没讲[em_004]
>
>

擦，看错了，讲了，太不细心了

## 回复 by 东方玻璃 (#15)

*2025-11-8 17:48*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Whoami默](https://bbs.kanxue.com/user-788084.htm)
>
>  擦，看错了，讲了，太不细心了
>
>

下次可以整理讲下其他版本的pass,花样还挺多![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by Whoami默 (#16)

*2025-11-9 09:55*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  下次可以整理讲下其他版本的pass,花样还挺多[em_065]
>
>

可以![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by Whoami默 (#17)

*2025-11-12 16:34*

不知道为什么md5那个按照ll编译成可执行文件，拖到ida中函数名并没有md5

## 回复 by 东方玻璃 (#18)

*2025-11-12 16:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Whoami默](https://bbs.kanxue.com/user-788084.htm)
>
>  不知道为什么md5那个按照ll编译成可执行文件，拖到ida中函数名并没有md5
>
>

盲猜optnone属性没关

## 回复 by Whoami默 (#19)

*2025-11-12 17:36*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  盲猜optnone属性没关
>
>

关了，也可能是我用的ollvm的clang把

## 回复 by mb_dnnvtvvz (#20)

*2025-12-24 08:37*

我在编译LLVM的时候，link阶段真的等了很久很久，一度以为卡死了

## 回复 by 东方玻璃 (#21)

*2025-12-24 10:31*

>
> [mb_dnnvtvvz](https://bbs.kanxue.com/user-1001641.htm)
>
>  我在编译LLVM的时候，link阶段真的等了很久很久，一度以为卡死了
>
>

windows编译可以enter下cmd窗口,会卡住不更新![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by iBa0 (#22)

*2026-4-6 17:56*

牛逼，没下了铁铁

## 回复 by 东方玻璃 (#23)

*2026-4-6 18:01*

>
> [iBa0](https://bbs.kanxue.com/user-971547.htm)
>  牛逼，没下了铁铁
>
>

下篇实战,不过最近没有实战需求所以先鸽一会![image](https://bbs.kanxue.com/view/img/face/065.gif)
