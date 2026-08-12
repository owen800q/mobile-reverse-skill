---
title: '[求助]ida调试安卓15，一直卡在waiting for debugger'
url: https://bbs.kanxue.com/thread-289877.htm
tid: 289877
author: BsonJ
date: '2026-01-26'
tags: [Android安全, 求助]
crawled_at: '2026-08-12T04:00:52+00:00'
replies: 10
---

配置：Linux环境、ida 9.2、真机安卓15（已root、系统和app已开debuggable）、Android Studio Otter 3（已切换到Android 15 SDK Platforms）

问题：按照网上流程执行ida能attach到程序，但是卡在“waiting for debugger”的唤醒上。尝试过

方式1：执行 adb forward tcp:8700 jdwp:pid，然后jdb -attach 127.0.0.1:8700；结果一直卡着不动（单独使用也不行，报错：无法附加到目标 VM）。

![image](https://bbs.kanxue.com/upload/attach/202601/1065758_XGCEMVSSHVJBPX4.webp)

方式2：用ddms + jdb，结果跟前者一样（猜测：ddms在19年已经停更了，对后续系统支持不够）。

方式3：后来看到这篇文章[https://mp.weixin.qq.com/s](https://mp.weixin.qq.com/s?__biz=MzU2NTkxMTU1NA==&mid=2247488347&idx=1&sn=25f7277da348a0e374c29202905d5e17&chksm=fdb7670158372499fc012e591e0fa69569a86d633d3f726bf098eaec6f3110c334402d6e652b&mpshare=1&scene=1&srcid=0114td0Xhwju2vig99QxAHgW&sharer_shareinfo=712b1209f72723067e2fb9df21c1024a&sharer_shareinfo_first=712b1209f72723067e2fb9df21c1024a&poc_token=HG8fb2mj9GwKGJslz5-c1_dEZ-uIsZmYuBzis2pa)里面提到用Android studio 去attach程序；这回有点眉目了~在不使用ida的情况下执行“将调试器附加到Android进程”能顺利唤醒（另：选择“附加到进程”是空的），

![image](https://bbs.kanxue.com/upload/attach/202601/1065758_GFQD4Z58N4S33XV.webp)

但一配合ida用就又不行了，Android Studio卡在这里一动不动。

![image](https://bbs.kanxue.com/upload/attach/202601/1065758_E4KR3AHG5FRF249.webp)

哪位大佬有调试安卓高版本的经验呢，或者知道Android studio怎么attach程序的流程。望不吝赐教！

---

# 回复

## 回复 by 猫子 (#2)

*2026-1-26 20:41*

试试 9.3 b1吧 https://docs.hex-rays.com/release-notes/9_3beta#debuggers
 Debuggers: Android 14-17 native debugging, Stack view dereferencing

## 回复 by BsonJ (#3)

*2026-1-30 16:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  猫子](https://bbs.kanxue.com/user-560933.htm)
>
>  试试 9.3 b1吧 https://docs.hex-rays.com/release-notes/9_3beta#debuggers
>  Debuggers: Android 14-17 nati ...
>
>

虽然不是这个问题但还是谢谢大佬你的热心![image](https://bbs.kanxue.com/view/img/face/086.gif)

## 回复 by BsonJ (#4)

*2026-1-30 16:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  猫子](https://bbs.kanxue.com/user-560933.htm)
>
>  试试 9.3 b1吧 https://docs.hex-rays.com/release-notes/9_3beta#debuggers
>  Debuggers: Android 14-17 nati ...
>
>

## 回复 by BsonJ (#5)

*2026-1-30 16:52*

自己回答一下。关于执行jdb -attach 127.0.0.1:8700没反应的问题：在网上看到一个观点“高版本安卓设备的 JDWP 端口转发需要root 级的 adb 权限，普通 adb 无法穿透系统限制”，这里的操作流程是：
1、手机下载一个终端模拟器app。
2、在面具获取其它管理权限软件中授予终端模拟器root权限（不然执行的命令没有root效果）。
3、在终端模拟器中依次输入：
        su
        stop adbd
        start adbd
重启手机后就能正常jdb attach了

其它jdb问题可以参考：<https://www.cnblogs.com/ciml/p/13362610.html>

## 回复 by BsonJ (#6)

*2026-1-30 17:12*

体会：关于用安卓15做调试~虽然jdb的问题解决了，但后面还出现了别的坑ptrace的占位问题。我的需求情景是先 adb shell am start -D -n 程序等待调试，接着ida attach该进程，然后jdb attach恢复运行，目的是追踪so的调用（目标so由java调用）。如果你也是这个需求一定一定要用**安卓11以下的系统**，11开始对ptrace的限制收紧，很难实现网上教程的调试方法。原理是：ida在attach后，ptrace锁定ida的调试器，导致不能执行jdb attach（表现为卡住）；低版本系统是因为限制比较宽松可以调试器接力。

由于网上没有高版本调试的帖子，我也心累调不动，决定换机了。总得来说高版本安卓系统一堆坑。

## 回复 by bfloat16 (#7)

*2026-1-30 23:41*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  猫子](https://bbs.kanxue.com/user-560933.htm)
>
>  试试 9.3 b1吧 https://docs.hex-rays.com/release-notes/9_3beta#debuggers
>  Debuggers: Android 14-17 nati ...
>
>

9.3 b1也不行，得等9.3正式版再说

## 回复 by koflfy (#8)

*2026-2-2 00:08*

我用ida调试安卓13这样能正常调试啊，但是在调试过程中，我自己写的一个很普通的程序，也是一堆的信号异常，所以我现在调试也是在安卓10上。

## 回复 by BsonJ (#9)

*2026-2-3 15:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  bfloat16](https://bbs.kanxue.com/user-1001730.htm)
>
>  9.3 b1也不行，得等9.3正式版再说
>
>

兄弟别用高版本了，一堆坑。我现在用安卓10做调试没问题

## 回复 by BsonJ (#10)

*2026-2-3 16:00*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  koflfy](https://bbs.kanxue.com/user-111569.htm)
>
>  我用ida调试安卓13这样能正常调试啊，但是在调试过程中，我自己写的一个很普通的程序，也是一堆的信号异常，所以我现在调试也是在安卓10上。
>
>

我现在也用安卓10，高版本一堆莫名其妙的问题，网上还没资料

## 回复 by medmi (#11)

*2026-3-16 21:30*

>
> [BsonJ](https://bbs.kanxue.com/user-1065758.htm)
>  体会：关于用安卓15做调试~虽然jdb的问题解决了，但后面还出现了别的坑ptrace的占位问题。我的需求情景是先 adb shell am start -D -n 程序等待调试，接着ida attac ...
>

我说为啥我的ida从7.7,9.0,9.2都无法正常调试我的一加ace5的任意程序, ..., 痛苦死咯
