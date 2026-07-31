---
title: '[讨论][原创]安卓lua解密——opcode修改后dump反编译'
url: https://bbs.kanxue.com/thread-282259.htm
tid: 282259
author: packets_64
date: '2024-06-23'
tags: [Android安全, 讨论, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:24:57+08:00'
replies: 4
---

随着近些年lua语言在安卓游戏大火，lua逆向已经越来越重要。早期游戏的lua源码放在安装包的assets目录，但随着对抗的升级，越来越多的游戏使用动态更新和扩展应用功能的方式，特别是在需要频繁更新脚本或配置的情况下。这种方法在游戏开发、插件系统、远程配置等场景中有较多应用。而且这种方法是网络上加载Lua代码，你在安装包,APK是得不到lua的代码的。遇到这种我们首先要确认是否是lua语言的应用：

![image](https://bbs.kanxue.com/upload/attach/202406/995191_DWG5E5WRVM2CY66.webp)

打开apk\lib\arm64-v8a\目录，如果发现libxlua.so,libslua.so等等类似目录，那么有很大可能是lua。（lua又分luajit与普通lua，判断是不是luajit，将so文件放进IDA，字符串搜索luajit即可）

再使用IDA或者frida hook lual_loadbuffer获取字节码，使用unluac网址（[unluac download | SourceForge.net](https://sourceforge.net/projects/unluac/)）进行反编译。

java -jar unluac.jar 你的字节码文件>存放文件

![image](https://bbs.kanxue.com/upload/attach/202406/995191_VEVMP9MH279TW67.webp)

反编译成功一般不会有输出信息，但看到类似上面的情况大概有3种可能：

    1.文件头被改

    2.opcode修改

    3.文件头和opcode都被改

关于文件头：

![image](https://bbs.kanxue.com/upload/attach/202406/995191_884ATYV32NDAPYB.webp)

**0到3字节：1B 4C 75 61**表示这是一个Lua字节码文件。

**第4字节：****51**：版本号，表示Lua 5.1。

**第5字节：00**：格式号，表示标准格式。01为非官方，魔改lua。

**第6字节：01**：endianness标识，表示大端格式。字节码文件需要指示其数据的字节顺序，以确保在不同平台和硬件架构上的正确解析。不同平台可能采用不同的字节序，比如大多数x86和x86-64架构采用小端序，而一些嵌入式系统和网络协议采用大端序。

**第8字节到11字节：**Lua整数大小，指令大小等。

关于opcode修改：liblua.so文件是lua源码文件编译的，lua源码的"lua-5.1.5\src\lopcodes.h"文件定义了opcode：![image](https://bbs.kanxue.com/upload/attach/202406/995191_RXW2KTBJ6YBTN3B.webp)

如果在编译的时候将opcode的顺序修改，比如OP_MOVE在OP_GETUPVAL前面，改为OP_GETUPVAL在OP_MOVE前面，再编译为so，这时再使用unluac反编译会报错。

解决办法有两个：

一：将正常的so文件与修改后的so文件，放进IDA反编译，搜索函数：luaV_execute找到case，进行对比，还原opcode的顺序。

![image](https://bbs.kanxue.com/upload/attach/202406/995191_K6HERUR4JHKKVNU.webp)

还原opcode之后，修改unluac的源码的src/unluac/decompile/OpcodeMap.java文件：

![image](https://bbs.kanxue.com/upload/attach/202406/995191_UEWMVZNA49CPQP6.webp)

再使用unluac反编译。

二：[[原创]用 Lua 简单还原 OpCode 顺序-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-250618.htm)

大佬的办法，从应用内部运行lua脚本，获取字节码。再将同一个lua脚本运行在未被修改的环境。

![image](https://bbs.kanxue.com/upload/attach/202406/995191_37ZMATSZ5AJGDEM.webp)

使用python将两个字节码文件对比，将红色的部分使用python替换，然后使用unluac反编译.

![image](https://bbs.kanxue.com/upload/attach/202406/995191_MJXSGKZKVMQQDDX.webp)

反编译成功！

---

# 回复

## 回复 by miyuecao (#2)

*2024-6-25 14:45*

厉害，来学下下

## 回复 by Kissnero (#3)

*2024-6-26 11:45*

以前有个游戏 安卓lual_loadbuffer dump出来的还需要解密 iOS dump出来的直接就是原始lua文件 注释都在![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by adnin (#4)

*2024-6-27 00:08*

巧了，最近在研究相关的东西，正好用上，mark一下

## 回复 by packets_64 (#5)

*2024-6-29 15:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Kissnero](https://bbs.kanxue.com/user-923759.htm)
>
>  以前有个游戏 安卓lual_loadbuffer dump出来的还需要解密 iOS dump出来的直接就是原始lua文件 注释都在[em_13]
>
>

是的，有些游戏是明文
