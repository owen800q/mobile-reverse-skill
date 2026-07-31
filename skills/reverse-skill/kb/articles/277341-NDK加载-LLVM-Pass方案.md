---
title: '[原创] NDK加载 LLVM Pass方案'
url: https://bbs.kanxue.com/thread-277341.htm
tid: 277341
author: Ylarod
date: '2023-05-23'
tags: [Android安全, 原创, NDK分析, 混淆加固]
crawled_at: '2026-07-31T14:48:06+08:00'
replies: 11
---

# NDK加载 LLVM Pass方案

本文基于 ndk r25c （25.2.9519653）
仅测试 **Linux** 和 **macOS**

# 获取ndk r25c

## 直接下载

点只因下载：<https://dl.google.com/android/repository/android-ndk-r25c-linux.zip>

## 使用sdkmanager安装

| 1 | `$ANDROID_HOME``/``tools``/``bin``/``sdkmanager` `-``-``install` `"ndk;25.2.9519653"` |
|-|-|

>
> 坑：archlinux 需要 `sudo archlinux-java set java-8-openjdk`
>
>
>

# 查看clang信息

| 1 | `cat $ANDROID_HOME``/``ndk``/``25.2``.``9519653``/``toolchains``/``llvm``/``prebuilt``/``linux``-``x86_64``/``AndroidVersion.txt` |
|-|-|

内容：

| 123 | `14.0``.``7``based on r450784d1``for` `additional information on LLVM revision` `and` `cherry``-``picks, see clang_source_info.md` |
|-|-|

# 下载未精简的clang

![Untitled](https://bbs.kanxue.com/upload/attach/202305/892096_8YUEVRCX7B76TFW.png)

 然后去Google的 prebuilt clang仓库找到 r450784d1 相关的分支并打开：

 <https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+log/refs/heads/master/clang-r450784d>

 ![Untitled](https://bbs.kanxue.com/upload/attach/202305/892096_MKR4Q38W6JRS25S.png)

 点开最新的一个commit，进入

 <https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+/4d52068718fb7940b103cc49506f77e5d22f25df/clang-r450784d1/>

 然后点击tgz下载这一份clang

 ![Untitled](https://bbs.kanxue.com/upload/attach/202305/892096_AAQQTTW8PWZASA6.png)

 然后基于这一份clang直接编译llvm动态库插件就可以直接用ndk加载了

 解压

| 12 | `mkdir clang``tar xzvf clang``-``r450784d1.tar.gz` `-``C clang` |
|-|-|

# 编译使用pass实例

1. 下载代码

| 1 | `git clone https:``/``/``github.com``/``LeadroyaL``/``llvm``-``pass``-``tutorial` |
|-|-|

1. 修改 CMakeLists.txt，在`project()`后加上

| 123 | `set``(CMAKE_C_COMPILER` `/``home``/``ylarod``/``ndk``-``r25c``/``clang``/``bin``/``clang)``set``(CMAKE_CXX_COMPILER` `/``home``/``ylarod``/``ndk``-``r25c``/``clang``/``bin``/``clang)``set``(ENV{LLVM_HOME}` `/``home``/``ylarod``/``ndk``-``r25c``/``clang)` |
|-|-|

这个时候`cmake ..`会报错

| 1234567891011121314151617181920 | `CMake Error at` `/``home``/``ylarod``/``ndk``-``r25c``/``clang``/``lib64``/``cmake``/``llvm``/``LLVMExports.cmake:``1036` `(message):``The imported target` `"LLVMDemangle"` `references the` `file` `"/home/ylarod/ndk-r25c/clang/lib64/libLLVMDemangle.a"` `but this` `file` `does` `not` `exist.  Possible reasons include:` `*` `The` `file` `was deleted, renamed,` `or` `moved to another location.` `*` `An install` `or` `uninstall procedure did` `not` `complete successfully.` `*` `The installation package was faulty` `and` `contained` `"/home/ylarod/ndk-r25c/clang/lib64/cmake/llvm/LLVMExports.cmake"` `but` `not` `all` `the files it references.` `Call Stack (most recent call first):``/``home``/``ylarod``/``ndk``-``r25c``/``clang``/``lib64``/``cmake``/``llvm``/``LLVMConfig.cmake:``251` `(include)``CMakeLists.txt:``14` `(find_package)` |
|-|-|

这个时候去注释掉`clang/lib64/cmake/llvm/LLVMExports.cmake` 下面这一段代码

 ![Untitled](https://bbs.kanxue.com/upload/attach/202305/892096_VGBWF4XUFSW4DQV.png)

 然后

| 123 | `mkdir build && cd build``cmake ..` `-``DCMAKE_BUILD_TYPE``=``Release` `-``G Ninja``ninja` |
|-|-|

![Untitled](https://bbs.kanxue.com/upload/attach/202305/892096_47WJJ2KBGFF79FK.png)

 测试代码来自 <https://github.com/bluesadi/Pluto-Obfuscator/tree/main/test/aes>

 build.sh:

| 1234 | `export CC``=``/``home``/``ylarod``/``Android``/``Sdk``/``ndk``/``25.2``.``9519653``/``toolchains``/``llvm``/``prebuilt``/``linux``-``x86_64``/``bin``/``clang``+``+` `$CC aes.cpp test.cpp` `-``o no_obf``$CC` `-``fpass``-``plugin``=``/``home``/``ylarod``/``ndk``-``r25c``/``llvm``-``pass``-``tutorial``/``build``/``Hikari``/``libHikari.so` `-``Xclang` `-``load` `-``Xclang` `/``home``/``ylarod``/``ndk``-``r25c``/``llvm``-``pass``-``tutorial``/``build``/``Hikari``/``libHikari.so` `-``mllvm` `-``split_num``=``3` `-``mllvm` `-``fw_prob``=``100` `-``mllvm` `-``fw_times``=``4` `-``mllvm` `-``bcf_prob``=``100` `-``mllvm` `-``bcf_loop``=``3` `aes.cpp test.cpp` `-``o obf` |
|-|-|

编译后：

 ![Untitled](https://bbs.kanxue.com/upload/attach/202305/892096_5K6WYQ2P2T3WWZ5.png)

 差不多鸟～

# 当我们来到macOS上

由于Google编译macOS工具链的系统版本太低，加载so的时候会报错

| 12345678910111213141516171819202122232425262728293031 | `In` `file` `included` `from` `aes.cpp:``1``:``.``/``aes.h:``6``:``10``: fatal error:` `'cstring'` `file` `not` `found``#include <cstring>``^~~~~~~~~``1` `error generated.``test.cpp:``1``:``10``: fatal error:` `'cstdio'` `file` `not` `found``#include <cstdio>``^~~~~~~~``1` `error generated.``error: unable to load plugin` `'/Users/ylarod/ndk-r25c/llvm-pass-tutorial/build/Hikari/libHikari.so'``:` `'dlopen(/Users/ylarod/ndk-r25c/llvm-pass-tutorial/build/Hikari/libHikari.so, 0x0009): symbol not found in flat namespace '``__ZN4llvm10CallbackVH6anchorEv''``clang (LLVM option parsing): Unknown command line argument` `'-split_num=3'``.  Try:` `'clang (LLVM option parsing) --help'``clang (LLVM option parsing): Did you mean` `'--print-bfi=3'``?``clang (LLVM option parsing): Unknown command line argument` `'-fw_prob=100'``.  Try:` `'clang (LLVM option parsing) --help'``clang (LLVM option parsing): Did you mean` `'--color=100'``?``clang (LLVM option parsing): Unknown command line argument` `'-fw_times=4'``.  Try:` `'clang (LLVM option parsing) --help'``clang (LLVM option parsing): Did you mean` `'--fast-isel=4'``?``clang (LLVM option parsing): Unknown command line argument` `'-bcf_prob=100'``.  Try:` `'clang (LLVM option parsing) --help'``clang (LLVM option parsing): Did you mean` `'--icp-lto=100'``?``clang (LLVM option parsing): Unknown command line argument` `'-bcf_loop=3'``.  Try:` `'clang (LLVM option parsing) --help'``clang (LLVM option parsing): Did you mean` `'--icp-lto=3'``?``error: unable to load plugin` `'/Users/ylarod/ndk-r25c/llvm-pass-tutorial/build/Hikari/libHikari.so'``:` `'dlopen(/Users/ylarod/ndk-r25c/llvm-pass-tutorial/build/Hikari/libHikari.so, 0x0009): symbol not found in flat namespace '``__ZN4llvm10CallbackVH6anchorEv''``clang (LLVM option parsing): Unknown command line argument` `'-split_num=3'``.  Try:` `'clang (LLVM option parsing) --help'``clang (LLVM option parsing): Did you mean` `'--print-bfi=3'``?``clang (LLVM option parsing): Unknown command line argument` `'-fw_prob=100'``.  Try:` `'clang (LLVM option parsing) --help'``clang (LLVM option parsing): Did you mean` `'--color=100'``?``clang (LLVM option parsing): Unknown command line argument` `'-fw_times=4'``.  Try:` `'clang (LLVM option parsing) --help'``clang (LLVM option parsing): Did you mean` `'--fast-isel=4'``?``clang (LLVM option parsing): Unknown command line argument` `'-bcf_prob=100'``.  Try:` `'clang (LLVM option parsing) --help'``clang (LLVM option parsing): Did you mean` `'--icp-lto=100'``?``clang (LLVM option parsing): Unknown command line argument` `'-bcf_loop=3'``.  Try:` `'clang (LLVM option parsing) --help'``clang (LLVM option parsing): Did you mean` `'--icp-lto=3'``?` |
|-|-|

解决办法：

 使用下载的clang替换掉ndk里面的clang

| 12 | `mv clang``-``14` `clang``-``14.bak``cp ~``/``ndk``-``r25c``/``clang``/``bin``/``clang``-``14` `clang``-``14` |
|-|-|

找不到头文件是macOS的问题，修改 `build.sh` 为

| 1234 | `export CC``=``/``Users``/``ylarod``/``Library``/``Android``/``sdk``/``ndk``/``25.2``.``9519653``/``toolchains``/``llvm``/``prebuilt``/``darwin``-``x86_64``/``bin``/``aarch64``-``linux``-``android33``-``clang``+``+` `$CC aes.cpp test.cpp` `-``o no_obf``$CC` `-``fpass``-``plugin``=``/``Users``/``ylarod``/``ndk``-``r25c``/``llvm``-``pass``-``tutorial``/``build``/``Hikari``/``libHikari.so` `-``Xclang` `-``load` `-``Xclang` `/``Users``/``ylarod``/``ndk``-``r25c``/``llvm``-``pass``-``tutorial``/``build``/``Hikari``/``libHikari.so` `-``mllvm` `-``split_num``=``3` `-``mllvm` `-``fw_prob``=``100` `-``mllvm` `-``fw_times``=``4` `-``mllvm` `-``bcf_prob``=``100` `-``mllvm` `-``bcf_loop``=``3` `aes.cpp test.cpp` `-``o obf` |
|-|-|

后重新编译，成功混淆

 ![Untitled](https://bbs.kanxue.com/upload/attach/202305/892096_YZ9HH9VNP9QWE5R.png)

# 参考

<https://www.leadroyal.cn/p/1008/>

 在我的博客中查看：
<https://xtuly.cn/article/ndk-load-llvm-pass-plugin>

---

# 回复

## 回复 by GitRoy (#2)

*2023-5-24 09:41*

大佬 666

## 回复 by mb_foyotena (#3)

*2023-5-24 10:34*

windows不支持, 其他系统简单

## 回复 by Ylarod (#4)

*2023-5-24 11:16*

>
> [mb_foyotena](https://bbs.kanxue.com/user-905000.htm)
>
>  windows不支持, 其他系统简单
>
>

实在要用Windows的话可以WSL用linux版本的NDK

## 回复 by guijingwen (#5)

*2023-5-24 11:16*

666

## 回复 by mb_vhmijwta (#6)

*2023-10-2 11:53*

请问大佬 能不能用来作为rust编译器

## 回复 by 小小布i (#7)

*2023-11-1 15:50*

这个混淆强度怎么样

## 回复 by mb_vhmijwta (#8)

*2024-3-19 20:48*

Rust的字符串是字符的结构体不是C字符串。不能混淆字符串 需要另外修改Pass实现的代码. 大佬有兴趣研究下不哇

## 回复 by virjar (#9)

*2024-3-20 09:01*

看起来安全sdk开始衍化为rust语言实现了

## 回复 by 秋狝 (#10)

*2024-3-20 09:22*

感谢分享

## 回复 by 4Chan (#11)

*2025-2-21 13:24*

666

## 回复 by xinfor (#12)

*2025-2-21 13:39*

小黑子![image](https://bbs.kanxue.com/view/img/face/065.gif)
