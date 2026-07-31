---
title: '[原创]frida-qbdi-tracer'
url: https://bbs.kanxue.com/thread-276523.htm
tid: 276523
author: Imyang
date: '2023-03-17'
tags: [Android安全, 原创, 工具脚本, 其他]
crawled_at: '2026-07-31T14:51:52+08:00'
replies: 25
---

## ida

好几年前，工具没有那么丰富，只用ida进行慢速的trace来分析算法。速度非常慢，曾经分析某个vmp算法，trace了大半个月。

 使用方法可以看我的课程 <https://www.kanxue.com/book-53-900.htm>

## unidbg

[unidbg](https://github.com/zhkl0228/unidbg) 出来后，大大的提升了分析算法的速度。trace速度比ida trace快了非常多。

 在unidbg的测试用例中，先补全环境，然后调用算法函数前加一下三行代码，即可开启trace

| 123 | `emulator.traceRead();``emulator.traceWrite();``emulator.traceCode();` |
|-|-|

## frida stalker

有时候遇到补环境比较麻烦，或者不想写unidbg的时候，可以用frida stalker

 使用方法可以看我的课程 <https://www.kanxue.com/book-84-1830.htm>

## frida-qbdi-tracer

最近QBDI更新了新功能，支持aarch64，于是基于他的frida-qbdi写了一个trace工具

 和frida stalker比，速度比frida stalker快。

 和unidbg比，不用补环境。

 Github地址：<https://github.com/lasting-yang/frida-qbdi-tracer>

---

# 回复

## 回复 by 黑龙lilad (#2)

*2023-3-17 17:36*

感谢分享![image](https://bbs.kanxue.com/view/img/face/71.gif)

## 回复 by Class___ (#3)

*2023-3-17 17:51*

感谢分享

## 回复 by xiaofeicc (#4)

*2023-3-17 18:54*

感谢分享![image](https://bbs.kanxue.com/view/img/face/71.gif)

## 回复 by mb_vvplvyor (#5)

*2023-3-17 19:01*

感谢![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by 龙飞雪 (#6)

*2023-3-17 22:46*

感谢分享

## 回复 by BlackMaGou (#7)

*2023-3-18 02:41*

感谢大佬分享

## 回复 by lxcoder (#8)

*2023-3-20 02:18*

666！目前一直用的是stalker，主要是用起来顺手灵活，测试了一下stalker的trace主要耗时在putcallout这块上面，里面再加一点js指令解析相关代码，耗时成几何倍数增加，如果能使用CModule的方式替换这一步的话应该也还算比较可观![image](https://bbs.kanxue.com/view/img/face/12.gif)

## 回复 by 金坷垃彩虹 (#9)

*2023-3-20 09:40*

感谢分享 IDA的trace主要是寄存器看不到东西 有时候是字符串都不知道 只显示一个地址

## 回复 by 值得怀疑 (#10)

*2023-3-20 10:37*

>
> [lxcoder](https://bbs.kanxue.com/user-719948.htm)
>
>  666！目前一直用的是stalker，主要是用起来顺手灵活，测试了一下stalker的trace主要耗时在putcallout这块上面，里面再加一点js指令解析相关代码，耗时成几何倍数增加，如果能使用 ...
>
>

看了这作者的一些免费视频说 stalker如果遇到复杂的函数可能会有问题？

## 回复 by lxcoder (#11)

*2023-3-20 14:46*

>
> [值得怀疑](https://bbs.kanxue.com/user-396746.htm)
>
>  看了这作者的一些免费视频说 stalker如果遇到复杂的函数可能会有问题？
>
>
>

会，特别是在arm32下面，arm64相对来说稳定很多，常规情况下够用了，特殊情况特殊处理

## 回复 by Imyang (#12)

*2023-3-21 17:32*

stalker执行起来耗时比较严重，遇到LDAXR STLXR这样的指令，就会获取不到值，需要特殊处理才能绕过

## 回复 by seeeseee (#13)

*2023-3-22 09:18*

感谢分享![image](https://bbs.kanxue.com/view/img/face/71.gif)

## 回复 by shmilyaxy (#14)

*2023-4-25 09:16*

大佬们，我在使用frida-qbdi-tracer的时候出现一个错误，提示找不到QBDI/frida-qbdi.js；这个该如何解决？

## 回复 by 秋狝 (#15)

*2023-4-25 10:04*

感谢分享

## 回复 by wx_倾尽天下 (#16)

*2023-4-29 20:01*

感谢大佬分享工具~![image](https://bbs.kanxue.com/view/img/face/71.gif)

## 回复 by 教教我吧~ (#17)

*2023-5-24 16:17*

>
> [shmilyaxy](https://bbs.kanxue.com/user-941979.htm)
>
>  大佬们，我在使用frida-qbdi-tracer的时候出现一个错误，提示找不到QBDI/frida-qbdi.js；这个该如何解决？
>
>

我也遇到这种情况，请问有解决方案了吗？

## 回复 by kakasasa (#18)

*2023-5-24 18:37*

话说有用frida这些trace搞过windows平台的没，能trace vmp tmd这些么？

## 回复 by mb_ldbucrik (#19)

*2024-1-10 13:33*

>
> [lxcoder](https://bbs.kanxue.com/user-719948.htm)
>
>  会，特别是在arm32下面，arm64相对来说稳定很多，常规情况下够用了，特殊情况特殊处理
>
>

大佬，trace遇到那种插入的死循环代码怎么处理呢

## 回复 by mb_ldbucrik (#20)

*2024-7-23 11:32*

yang神请问trace指令崩溃是什么原因呢，有什么解决方案不

## 回复 by chenfuzhi (#21)

*2024-8-8 11:23*

>
> [lxcoder](https://bbs.kanxue.com/user-719948.htm)
>
>  666！目前一直用的是stalker，主要是用起来顺手灵活，测试了一下stalker的trace主要耗时在putcallout这块上面，里面再加一点js指令解析相关代码，耗时成几何倍数增加，如果能使用 ...
>
>

有碰到过stalker 跟踪多个线程，卡死问题吗？

## 回复 by 阳光宝贝 (#22)

*2024-8-8 13:04*

感谢大佬分享，最近在学习so层逆向，学到了

## 回复 by 郑z (#23)

*2025-5-14 17:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  chenfuzhi](https://bbs.kanxue.com/user-181524.htm)
>
>  有碰到过stalker 跟踪多个线程，卡死问题吗？
>
>

解决了吗，我最近也在研究stalker，在回调里打印寄存器就会卡死，只打印指令正常

## 回复 by whe (#24)

*2025-6-27 11:12*

“遇到LDAXR STLXR这样的指令，就会获取不到值，需要特殊处理才能绕过”，这个需要如何特殊处理呢？

## 回复 by 慈悲佛祖 (#25)

*2025-7-9 22:57*

libQBDI.so library not found...有没有已经解决的？我直接把so push到手机上，还是报错~ 到底是没找到电脑上的so还是没找到手机上的so?

## 回复 by fengvmu (#26)

*2025-12-30 18:37*

>
> [Imyang](https://bbs.kanxue.com/user-548459.htm)
>
>  stalker执行起来耗时比较严重，遇到LDAXR STLXR这样的指令，就会获取不到值，需要特殊处理才能绕过
>
>

怎么特殊处理啊 能讲讲吗![image](https://bbs.kanxue.com/view/img/face/055.gif)
