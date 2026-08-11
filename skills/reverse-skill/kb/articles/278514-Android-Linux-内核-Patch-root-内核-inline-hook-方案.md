---
title: '[原创] Android(Linux) 内核 Patch (root + 内核 inline hook) 方案'
url: https://bbs.kanxue.com/thread-278514.htm
tid: 278514
author: bmax
date: '2023-08-22'
tags: [Android安全, 原创, 基础理论, 程序开发, HOOK注入, 系统相关, 源码框架, 工具脚本]
crawled_at: '2026-08-11T08:47:09+00:00'
replies: 28
---

0

---

# 回复

## 回复 by mb_lpcoesnt (#2)

*2023-8-22 08:24*

这个和skroot很像啊

## 回复 by 秋狝 (#3)

*2023-8-22 09:17*

感谢分享

## 回复 by wx_晚风_407 (#4)

*2023-8-22 10:34*

强!!  支持!

## 回复 by New对象处 (#5)

*2023-8-22 10:34*

666，start先，坐等大佬实现syscall hook

## 回复 by bmax (#6)

*2023-8-22 10:50*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  New对象处](https://bbs.kanxue.com/user-807696.htm)
>
>  666，start先，坐等大佬实现syscall hook
>
>

已经有了现在，KernelPatch 中有实现了两种模式，一种使替换 syscall table 的，但是这种方式在高版本的android内核（我测过5.10）会因为有 Control Flow Integrity 出问题，还需要适配，低版本没问题。另一种模式是 inline-hook 的，现在使用的是这种。你可以看看 KernelPatch 的 kernel/init/include/syscall.h 和
 kernel/init/accctl/supercall.c 是如何使用的。不过现在模块模块功能没开发，可能需要直接改 KernelPatch 代码

## 回复 by 不吃早饭 (#7)

*2023-8-22 11:03*

666，强的

## 回复 by 月落之汀 (#8)

*2023-8-22 11:36*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  bmax](https://bbs.kanxue.com/user-804232.htm)
>
>  已经有了现在，KernelPatch 中有实现了两种模式，一种使替换 syscall table 的，但是这种方式在高版本的android内核（我测过5.10）会因为有 Control Flow In ...
>
>

早上就在奇怪cfi的问题，不过之前看过cfi的具体实现，感觉hook下就能过掉，不是很难，这个patch的思路真的挺不错的，读完代码研习下dalao的操作

## 回复 by NPC2000 (#9)

*2023-8-22 12:10*

太强了

## 回复 by Loopher (#10)

*2023-8-22 12:39*

这么强悍6666

## 回复 by bmax (#11)

*2023-8-22 13:11*

>
> [月落之汀](https://bbs.kanxue.com/user-706309.htm)
>
>  早上就在奇怪cfi的问题，不过之前看过cfi的具体实现，感觉hook下就能过掉，不是很难，这个patch的思路真的挺不错的，读完代码研习下dalao的操作
>
>

但是其实 inline hook 也有问题，如果是内核运行中进行 hook， 因为不是原子操作，还会引入同步问题，需要 stop_machine，并且如果某个task正运行在 需要 patch 的指令上，或者 patch 指令的地方有跳转且某个task堆栈正好就在这，会很麻烦，不过概率很小，可以检测到就 hook 失败重新来。具体我也没细研究

## 回复 by bmax (#12)

*2023-8-22 13:16*

>
> [月落之汀](https://bbs.kanxue.com/user-706309.htm)
>
>  早上就在奇怪cfi的问题，不过之前看过cfi的具体实现，感觉hook下就能过掉，不是很难，这个patch的思路真的挺不错的，读完代码研习下dalao的操作
>
>

有个思路，如果只是 syscall table hook，其实可以尝试下跳过 xxx.cfi 函数，不知道可不可行

## 回复 by 月落之汀 (#13)

*2023-8-22 16:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  bmax](https://bbs.kanxue.com/user-804232.htm)
>
>  有个思路，如果只是 syscall table hook，其实可以尝试下跳过 xxx.cfi 函数，不知道可不可行
>
>

之前尝试过是不行的，当然也可能是我的方法有问题，过段时间我试试能不能把kcfi bypass了

## 回复 by 智取棋 (#14)

*2023-8-23 14:59*

很好

## 回复 by fangkang (#15)

*2023-8-25 10:35*

Meizu M5 Note5
kernel 是 Linux version 3.18.35+ (flyme@Mz-Builder-l7) (gcc version 4.9 20150123 (prerelease) (GCC) ) #1 SMP PREEMPT Thu Jul 9 20:02:30 CST 2020

使用kptools patch 后得到新kernel，使用AIK重新打包后再使用mtk-client写入boot分区后无法启动，
主板上的URAT脚位也不知道，不好抓preloader的启动日志信息。
不知道有没有朋友了解 MTK平台的BOOT解包、修改、打包中的注意事项

## 回复 by miyuecao (#16)

*2023-8-25 15:00*

支持下，持续关注

## 回复 by mb_ckpefbiq (#17)

*2023-8-25 16:13*

app的状态栏和kernelsu 好像，实测骁龙 5.15的设备无法开机，

## 回复 by abcz316 (#18)

*2023-8-26 13:12*

楼主思路不错，但不是所有内核的banner都是Linux version开头，而且不是所有的内核都会开放kallsyms_lookup_name，楼主是否有考虑这点呢？

## 回复 by 万里星河 (#19)

*2023-8-26 15:04*

mark

## 回复 by 万里星河 (#20)

*2023-8-26 23:14*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  楼主思路不错，但不是所有内核的banner都是Linux version开头，而且不是所有的内核都会开放kallsyms_lookup_name，楼主是否有考虑这点呢？
>
>

活捉一位读烂了十多本内核书的大佬 ![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by mb_ipugnluu (#21)

*2023-8-28 04:56*

厉害大佬

## 回复 by bmax (#22)

*2023-8-28 07:51*

确实是，没有开 CONFIG_KALLSYMS 确实不行，还没见过，不过这种设备应该只有少部分路由器啥的内存少才会这么配吧

## 回复 by bmax (#23)

*2023-8-28 07:53*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  楼主思路不错，但不是所有内核的banner都是Linux version开头，而且不是所有的内核都会开放kallsyms_lookup_name，楼主是否有考虑这点呢？
>
>

确实是，没有开 CONFIG_KALLSYMS 确实不行，还没见过，不过这种设备应该只有少部分路由器啥的内存少才会这么配吧

## 回复 by bmax (#24)

*2023-8-28 08:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  fangkang](https://bbs.kanxue.com/user-84291.htm)
>
>  Meizu&nbsp;M5&nbsp;Note5kernel&nbsp;是&nbsp;Linux&nbsp;version&nbsp;3.18.35+& ...
>
>

3.18 没测过，uart 搞了几天没搞明白就不搞了，现在都是一块块的注释代码定位问题在哪![image](https://bbs.kanxue.com/view/img/face/85.gif)，实在不行也可以把手机寄给我我搞一下

## 回复 by fangkang (#25)

*2023-8-28 09:52*

@bmax 这个魅族M5 Note中的kallsyms的读取需要在kallsyms.c的593行修改成
int32_t target_offset = info->linux_banner_offset - 0x1000
主要是他的起始地址是 0xffffffc000081000 而不是 0xffffffc000080000

然后我尝试手动修补bytecode 试着在某个函数的开头使用B指令跳转到新的偏移，然后平衡堆栈后在跳回原处，但无法启动，我觉得如果您知道手动修补的注意事项，告诉我们，我们可以试试看只做简单修补，看能否完成刷机启动最好不过

如果需要手机，请私信。

## 回复 by 龙飞雪 (#26)

*2023-8-28 10:27*

感谢分享，持续关注

## 回复 by bmax (#27)

*2023-8-28 13:58*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  fangkang](https://bbs.kanxue.com/user-84291.htm)
>
>  @bmax 这个魅族M5 Note中的kallsyms的读取需要在kallsyms.c的593行修改成
> int32_t target_offset = info->linux_banne ...

## 回复 by bmax (#28)

*2023-8-28 14:10*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  fangkang](https://bbs.kanxue.com/user-84291.htm)
>
>  @bmax 这个魅族M5 Note中的kallsyms的读取需要在kallsyms.c的593行修改成
> int32_t target_offset = info->linux_banne ...
>
>

新建了个电报群，github 上有链接

## 回复 by mb_fosmxidi (#29)

*2023-9-14 22:18*

插个眼 等发布
