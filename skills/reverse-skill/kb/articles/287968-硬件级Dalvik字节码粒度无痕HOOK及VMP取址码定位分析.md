---
title: '[原创]硬件级Dalvik字节码粒度无痕HOOK及VMP取址码定位分析'
url: https://bbs.kanxue.com/thread-287968.htm
tid: 287968
author: 万里星河
date: '2025-08-10'
tags: [Android安全, 原创, 基础理论, 逆向分析, 程序开发, HOOK注入, 系统相关]
crawled_at: '2026-07-31T14:05:29+08:00'
replies: 16
---

# 引言

在安卓java层的dex的逆向分析中 类似以下的smali代码时常会被遇到：

| 1234 | `if``-eqz v1，:cond``xxx``:cond``yyy` |
|-|-|

为了逆向分析的继续推进 确定执行流在if-eqz的之后是走向xxx 还是 yyy就显得尤为重要。

然后遗憾的是 主流的hook框架 无论是xposed亦或是frida 在java层 都只能在函数调用级别进行拦截 且 极其容易被检测。

本文即将探讨的是 如何在硬件级别实现dalvik bytecode粒度的无痕拦截技术 并实现鼠标点击一键hook 指哪儿打哪儿 感受 button power 的强大魅力！

# 已知方案

要追踪像引言中那样的smali的执行流 目前笔者已知且实现过的有以下方案：

1. 修改AOSP源码 在art解释器相关位置插入打印日志。优点是简单 缺点是笨重 不灵活 适用面窄 不够优雅。
2. idapro 逆向分析 libart.so 找到art解释器相关代码 inline hook之。优点是通用 缺点是实现难度较高。
3. 直接解析指定方法的smali文件 对每行smali都附加smali打印日志 重新编译成dex 基于dex热修复技术注入 通过日志查看smali执行流。

 以上方式 要么要重编译系统 要么要基于xposed或frida 操作复杂 被检测面广 侵入性太强 皆不符合笔者的需求。

# 硬件级Dalvik字节码粒度无痕HOOK 实现原理

众所周知 dalvik字节码会被art解释器解释执行 。

解释器在解释执行前必会读取内存中的bytecode 。

因此只要对bytecode所在内存下硬件读写断点即可。

断点触发了意味着这条smali执行了 否则便没有执行。

具体思路如下:

| 12345 | `ps -elf \| grep pkg_name 获取进程pid` `cat /proc/pid/maps \| grep classess.dex 获取dex在内存中的基址 加上codeItem偏移 得到目标地址 \|通过dex cookie获取dex内存基址 \| 通过GG CE等内存搜索工具搜索dalvik字节码序列直接定位到地址` `手机安装arm64硬件断点内核驱动 对目标地址打硬件读写断点` |
|-|-|

借助于GDA对dex的强大解析能力 使用python脚本通过adb执行相关程序调用驱动 可将上述步骤自动化。

# 效果展示:

![image](https://bbs.kanxue.com/upload/attach/202508/892665_UPZ8N37J3J9MDBB.webp)

原理很简单 py程序接受pid addr_base参数 并在后台监听系统剪切版 在GDA中复制最右端dalvik字节码偏移 python读取到后 相加即可获取到绝对地址 通过adb调用安卓端的bp可执行程序 其中连接arm64硬件读写驱动 下硬件只读断点 就可以了。只要当前smali指令被读取执行 就会被断下。结合这张图 很容易理解。

这种方式的优点：

首先是操作简单 鼠标点哪里就断哪里。

其次是基于硬件断点 聚形散气，无痕无迹。

最后断点状态是同步的 实时的 不像perf那样是事后异步收集信息。

# 相关思考

1.基于GDA的dalvik字节码静态编译技术 以及 arm64硬件读写驱动 可以实现smali指令的inline hook.

2.通过硬件读写断点的输出信息 可知pc寄存器就是art解释器的取码地址 直接硬件执行断点在这个pc 即可直接trace所有的smali执行流 通杀所有机型系统。将执行流数据导入idapro 可实现执行流可视化。

3.vmp取自定义操作码的取码操作也可以使用上述思路快捷定位 秒出指令映射表。

4.由于硬件断点是同步的 断下后可随时硬件dump下这一瞬间的app内存映像 写入unicorn的内存模拟执行。 导入了unicorn 想怎么搞 都尽在掌握之中。

---

# 回复

## 回复 by 安卓逆向test (#2)

*2025-8-10 23:48*

用内核驱动来搞smali指令的hook还是很麻烦的吧，rwprocmem33应该就提供了setpc的接口，其他寄存器的写入好像没有接口

## 回复 by 万里星河 (#3)

*2025-8-11 03:05*

>
> [安卓逆向test](https://bbs.kanxue.com/user-973348.htm)
>
>  用内核驱动来搞smali指令的hook还是很麻烦的吧，rwprocmem33应该就提供了setpc的接口，其他寄存器的写入好像没有接口
>
>

鼠标点哪就hook哪 不麻烦的

## 回复 by WanQing (#4)

*2025-8-11 12:32*

已经有hook框架支持指令粒度的hook哈
https://bbs.kanxue.com/thread-287777.htm

## 回复 by mb_wpitiize (#5)

*2025-8-11 14:33*

用的是rwProcMem33吗，脚本方便开源学习一下吗

## 回复 by 万里星河 (#6)

*2025-8-11 14:56*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_wpitiize](https://bbs.kanxue.com/user-962678.htm)
>
>  用的是rwProcMem33吗，脚本方便开源学习一下吗
>
>

是的 用的rwProcMem33 py脚本太简单了 总共不到10行代码 我都没好意思发 其实只要复制文中有关原理的那段话给AI 直接就有啦![image](https://bbs.kanxue.com/view/img/face/051.gif)

## 回复 by 葫芦娃 (#7)

*2025-8-11 15:40*

>  众所周知 dalvik字节码会被art解释器解释执行 。解释器在解释执行前必会读取内存中的bytecode 。

JIT：啊？
AOT：啊？？

## 回复 by 万里星河 (#8)

*2025-8-11 16:13*

>
> [葫芦娃](https://bbs.kanxue.com/user-715510.htm)
>
>  &gt;&nbsp;&nbsp;众所周知 dalvik字节码会被art解释器解释执行 。解释器在解释执行前必会读取内存中的bytecode 。JIT：啊？AOT：啊？？
>
>

似乎都是有办法过掉的 不必啊？

## 回复 by 万里星河 (#9)

*2025-8-11 16:16*

而且壳里的代码几乎都是解释执行

## 回复 by 陈可牛 (#10)

*2025-8-11 16:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  而且壳里的代码几乎都是解释执行
>
>

某些加固的类抽取实现，有回填的跟偏移的，如果是偏移的话，那就不行了。那就变成，如何定位code_item不在dex范围的问题了

## 回复 by 万里星河 (#11)

*2025-8-11 17:26*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  某些加固的类抽取实现，有回填的跟偏移的，如果是偏移的话，那就不行了。那就变成，如何定位code_item不在dex范围的问题了
>
>

嗯 具体问题具体分析 文章提供的是通用的一般思路

## 回复 by 万里星河 (#12)

*2025-8-11 17:29*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  已经有hook框架支持指令粒度的hook哈
> https://bbs.kanxue.com/thread-287777.htm
>
>

| 12345678910111213 | `static` `{``System.loadLibrary(``"albatross_base"``);``System.loadLibrary(``"native-lib"``);``}` `Albatross.hookInstruction(onClick,``0``,``10``,``new` `InstructionCallback() {``@Override``public` `void` `onEnter(Member member, Object self,``int` `dexPc, InvocationContext invocationContext)``{``Log.d(``"Albatross"``,``"dex_Pc:"` `+ dexPc);``}``});` |
|-|-|

2025-08-11 18:20:19.748 11904-11904/? E/AndroidRuntime: FATAL EXCEPTION: main

    Process: me.stevenzack.langenius, PID: 11904

    java.lang.UnsatisfiedLinkError: No implementation found for long qing.albatross.core.InstructionListener.hookInstructionNative(java.lang.reflect.Member, int, int, java.lang.Object) (tried Java_qing_albatross_core_InstructionListener_hookInstructionNative and Java_qing_albatross_core_InstructionListener_hookInstructionNative__Ljava_lang_reflect_Member_2IILjava_lang_Object_2) - is the library loaded, e.g. System.loadLibrary?

        at qing.albatross.core.InstructionListener.hookInstructionNative(Native Method)

        at qing.albatross.core.Albatross.hookInstruction(Albatross.java:447)

        at qing.albatross.core.Albatross.hookInstruction(Albatross.java:434)

## 回复 by 葫芦娃 (#13)

*2025-8-11 19:31*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  似乎都是有办法过掉的 不必啊？
>
>

愿闻其详

## 回复 by 万里星河 (#14)

*2025-8-11 19:36*

>
> [葫芦娃](https://bbs.kanxue.com/user-715510.htm)
>
>  愿闻其详
>
>

建议自己研究

## 回复 by WanQing (#15)

*2025-8-12 21:29*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>
>
>
>
>
>
>  WanQing
>
>
>
>  已经有hook框架支持指令粒度的hook哈
> https://bbs.kanxue.com/thread-287777.h ...
>
>

需要提前初始化库的![image](https://bbs.kanxue.com/view/img/face/051.gif)

## 回复 by WanQing (#16)

*2025-8-13 08:50*

因为我不用这个功能，没有经过充分测试，抱歉啦，修复了，如果还有问题，可以把测试手机的libart邮件发给我。后续会加入代码追踪和内存读写的功能。加了壳的app不会所有的代码都走vmp，不然速度会特别慢。不过我一直好奇加固的怎么aot编译。如果只单纯依赖jit，那内存占用会比aot高，执行速度也会大打折扣。

## 回复 by 万里星河 (#17)

*2025-8-13 12:00*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  因为我不用这个功能，没有经过充分测试，抱歉啦，修复了，如果还有问题，可以把测试手机的libart邮件发给我。后续会加入代码追踪和内存读写的功能。加了壳的app不会所有的代码都走vmp，不然速度会特别慢 ...
>
>

加固的应该不能aot aot主要是在软件安装的时候进行的 但安装时壳保护的dex肯定还没解密 也就aot不了 不过由于安卓7之后的aot+jit混合编译模式 解释器会在运行时记录代码热度  在设备空闲时将热点代码编译为本地机器码 效率还是可以的
