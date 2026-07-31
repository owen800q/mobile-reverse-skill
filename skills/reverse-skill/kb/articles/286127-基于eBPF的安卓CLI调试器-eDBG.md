---
title: '[原创] 基于eBPF的安卓CLI调试器——eDBG'
url: https://bbs.kanxue.com/thread-286127.htm
tid: 286127
author: ShinoLeah
date: '2025-03-21'
tags: [Android安全, 原创, 逆向分析, 混淆加固, 脱壳反混淆, 源码框架, 工具脚本]
crawled_at: '2026-07-31T14:12:24+08:00'
replies: 13
---

## 简介

eDBG 是一款基于 eBPF 技术实现的调试工具，为强对抗场景下的安卓 native 逆向工作打造，提供调试器应有的基本功能，在调试时**不产生任何附加到目标进程的行为**，不使用传统的调试方案，调试器与被调试程序**相互独立**，仅各自与内核产生交互行为，难以被目标进程调试或干扰。

除此之外，eDBG 和被调试程序运行状态互不干扰，断点注册不基于运行时地址，即使一方意外退出或重启，另一方也依旧能正常工作。

eDBG 的使用方式与 gdb 的使用方式几乎相同，无需学习便可直接上手使用。

项目地址：<https://github.com/ShinoLeah/eDBG>
直接从 [Release](https://github.com/ShinoLeah/eDBG/releases) 下载即可使用。

## 主要功能

主要支持的功能如下：

- 断点：基于 uprobes 功能实现，在断点处可暂停程序并且读取任意想要的上下文。
- 单步调试：支持步入或步过。
- 内存读写：在断点触发时可以读取任意地址内存，也可以自由写入任意有写权限的地址。
- 线程过滤：你可以仅调试一个或多个想要的线程。
- 符号解析、反汇编等其他调试器应该有的功能。

支持的 gdb 指令列表：`break / continue / step / next / finish / until / examine / display / quit / list / info / thread`

额外的，你可以使用 `write` 指令写入内存，`set` 指令为指定的地址标注你的自定义符号。

eDBG 也支持将你的进度保存到文件或读取工程文件，以便下一次调试。

详细的使用方式请移步[README](https://github.com/ShinoLeah/eDBG/blob/main/README.md)

## 运行环境

- 目前仅支持 ARM64 架构的 Android 系统，需要 ROOT 权限，推荐搭配 [KernelSU](https://github.com/tiann/KernelSU) 使用
- 系统内核版本5.10+ （可执行`uname -r`查看）

## 功能演示

整体的界面设计和信息展示参考了 [pwndbg](https://github.com/pwndbg/pwndbg)，会在断点处自动分析当前代码和寄存器信息，当然你可以在选项里关掉这些显示。

![image](https://bbs.kanxue.com/upload/attach/202503/1029543_N84D796THRKJT2E.png)

## 进阶使用

[eDBG 使用进阶：避免 uprobes 产生可被察觉的特征](https://www.sh1no.icu/posts/28348c4/)

## 其他

本项目主要受到 [stackplz](https://github.com/SeeFlowerX/stackplz) 启发，在实际逆向工作中我常常使用 stackplz 辅助 ida 进行动态调试，但常常被堆积如山的反调试手段或蜜罐打得鼻青脸肿...(菜菜)，因此突发奇想将 eBPF 技术直接用于打造一个调试器，虽然比 ida 缺少了图形化界面和反编译（但是现在的 app 还有可以直接 F5 的吗），但是我认为功能也足够作为一个逆向辅助工具进行日常使用。

喜欢的话可以[赏个小星星](https://github.com/ShinoLeah/eDBG) QAQ
也欢迎提出建议或 issue 或 PR 喵

---

# 回复

## 回复 by Imxz (#2)

*2025-3-21 16:36*

真牛逼

## 回复 by Imxz (#3)

*2025-3-21 16:43*

是否能支持硬件断点呢?

## 回复 by ShinoLeah (#4)

*2025-3-21 16:47*

>
> [Imxz](https://bbs.kanxue.com/user-656334.htm)
>
>  是否能支持硬件断点呢?
>
>

暂时还没有实现这部分..

## 回复 by seeeseee (#5)

*2025-3-22 15:55*

一直希望有这样一个工具，终于来了！![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 海带 (#6)

*2025-3-22 22:39*

牛逼大佬66666666666666

## 回复 by 王麻子本人 (#7)

*2025-3-22 22:45*

优雅了

## 回复 by 嘎嘎真的很棒 (#8)

*2025-3-24 15:34*

牛逼大佬6666666666666

## 回复 by 逆天而行 (#9)

*2025-3-30 18:10*

强啊  感觉楼主 是pwn选手

## 回复 by mb_uhwfeasa (#10)

*2025-4-7 11:20*

可以不写so文件，只针对一个内存地址下断点调试吗

## 回复 by ShinoLeah (#11)

*2025-4-7 12:22*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_uhwfeasa](https://bbs.kanxue.com/user-950562.htm)
>
>  可以不写so文件，只针对一个内存地址下断点调试吗
>
>

uprobe是基于文件的，暂时不行哦

## 回复 by netsniffer (#12)

*2025-4-23 12:42*

-b 支持个符号名呗

## 回复 by mb_ldbucrik (#13)

*2025-5-18 10:14*

可否支持内核trace呢

## 回复 by zx_987352 (#14)

*2025-9-23 17:04*

牛逼cls
