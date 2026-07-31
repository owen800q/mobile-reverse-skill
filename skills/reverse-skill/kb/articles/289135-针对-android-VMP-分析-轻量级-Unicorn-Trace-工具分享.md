---
title: '[原创]针对 android VMP 分析，轻量级 Unicorn Trace 工具分享'
url: https://bbs.kanxue.com/thread-289135.htm
tid: 289135
author: vior
date: '2025-11-19'
tags: [Android安全, 原创, 逆向分析, 混淆加固, 工具脚本]
crawled_at: '2026-07-31T14:01:25+08:00'
replies: 33
---

项目地址：https://github.com/chenxvb/Unicorn-Trace

android trace 工具都不太好用，写了个 unicorn 的 ida trace 工具分享一下

Unicorn ARM64 动态追踪模拟器是一套基于 Unicorn 引擎的轻量级动态追踪工具，专为 ARM64 架构的逆向分析设计。该项目提供了与 IDA Pro 深度集成的插件版本和独立运行的模拟器版本，能够在保证执行准确性的同时，提供高效的代码追踪和内存转储能力。

本工具无需全量 dump 内存，只在使用时 dump，所以比传统 trace 工具都要方便，快速许多。ida 自带的 trace 基本用不了，frida 的 trace 限制多且麻烦，本 trace 工具可以解决这个问题

并且本工具在记录过后还可以重新本地执行，可以专注于一个分析样例并可以随时监控，更改内存，还有 tenet log 可以在 ida 中伪调试，针对大型混淆流程分析和 vm 纯算法分析比较好用

样例

ida 调试启动后，直接运行脚本/使用插件填入目标地址

![image](https://bbs.kanxue.com/upload/attach/202511/930478_KP6F9N7JCTM2GHF.webp)

运行完成后，对比模拟和 ida 一致，显示正常完成

![image](https://bbs.kanxue.com/upload/attach/202511/930478_GHSUYBF7QA38KAZ.webp)

生成 dump 在目录下，可以无缝使用 unicron 脚本模拟执行，并生成 tenet log

![image](https://bbs.kanxue.com/upload/attach/202511/930478_7ADFJ9PDJH9NRV8.webp)

看 uc log，或者 ida 加载 tenet log 分析 trace

![image](https://bbs.kanxue.com/upload/attach/202511/930478_QH9Z9V2TJZF9YD8.webp)

![image](https://bbs.kanxue.com/upload/attach/202511/930478_WCBMWR7JHQ4QFR8.webp)

事实上可以 模拟执行后可以玩很多花活了，比如监控某个汇编的访问，记录顺序，修改 vm 算法入参，记录所有的相关操作等：如

打印监控内存变化

![image](https://bbs.kanxue.com/upload/attach/202511/930478_3J5MQ6HSSEHEAUW.webp)

监控调用，并打印出对应参数和顺序

![image](https://bbs.kanxue.com/upload/attach/202511/930478_TQWV4XGHBJAJ52T.webp)

魔改数据看变化等等，在算法分析上优势很大，从此 ida 就只是 dump 工具罢了

---

# 回复

## 回复 by wx_插曲 (#2)

*2025-11-19 17:06*

大佬牛逼啊

## 回复 by k4y0z (#3)

*2025-11-19 17:41*

666

## 回复 by 随风而行aa (#4)

*2025-11-19 17:57*

不错

## 回复 by mb_ldbucrik (#5)

*2025-11-19 18:42*

文字都看不清，是不是颜色不对呢

## 回复 by vior (#6)

*2025-11-19 19:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>  文字都看不清，是不是颜色不对呢
>
>

深色模式看的没看出问题，发现正常看不出来，在改了

## 回复 by vior (#7)

*2025-11-19 19:07*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>  文字都看不清，是不是颜色不对呢
>
>

不过好像编辑不了，显示 Server Response Not JSON：123 ，先将就选择看吧

## 回复 by KanXue_NG (#8)

*2025-11-19 19:36*

路过学习

## 回复 by mb_asiwnxyv (#9)

*2025-11-19 19:58*

感谢分享

## 回复 by guijingwen (#10)

*2025-11-19 20:41*

66

## 回复 by git_94730eaydwshawke-gif (#11)

*2025-11-19 21:28*

123

## 回复 by vior (#12)

*2025-11-20 18:58*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>  文字都看不清，是不是颜色不对呢
>
>

修好了

## 回复 by 祝枝山 (#13)

*2025-11-21 14:29*

你不觉得多余吗？1个GB以上的日志你加载给我看看

## 回复 by mb_ysegxpmv (#14)

*2025-11-22 11:53*

大佬牛逼

## 回复 by 墨穹呢 (#15)

*2025-11-22 11:57*

感谢分享，看起来好像很厉害

## 回复 by huangjw (#16)

*2025-11-22 12:09*

火钳刘明

## 回复 by iCookiie (#17)

*2025-11-22 20:20*

遇到了SVC指令的话 是不是也要像unidbg一样需要补系统调用

## 回复 by vior (#18)

*2025-11-23 09:39*

>
> [iCookiie](https://bbs.kanxue.com/user-970595.htm)
>
>  遇到了SVC指令的话 是不是也要像unidbg一样需要补系统调用
>
>

不需要，遇到 libc 之类包含 svc 外部跳转的会直接调用 ida 跳过。对于 lib 内的用户函数调用 svc 也可以用 ida 跳过，但需要再脚本代码里加一下

## 回复 by method (#19)

*2025-11-25 11:41*

强的

## 回复 by hpphpp (#20)

*2025-11-26 10:08*

用ida调试,有的时候都走不到断点,报错.
有其他frida或者其他方式能dumps寄存内存吗?

## 回复 by vior (#21)

*2025-11-26 14:32*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  hpphpp](https://bbs.kanxue.com/user-226208.htm)
>
>  用ida调试,有的时候都走不到断点,报错.
> 有其他frida或者其他方式能dumps寄存内存吗?
>
>

如果是常规报错可以看看是不是在文档里有写
dump 内存走 frida 效率不高，建议用 ce dump 或者用 dd 命令 dump，如果会用 ida python 在我项目里 single_script/dump_single.py 的脚本也可以走 ida dump 一个段

## 回复 by iCookiie (#22)

*2025-11-26 15:15*

>
> [vior](https://bbs.kanxue.com/user-930478.htm)
>
>  不需要，遇到 libc 之类包含 svc 外部跳转的会直接调用 ida 跳过。对于 lib 内的用户函数调用 svc 也可以用 ida 跳过，但需要再脚本代码里加一下
>
>

我是说dump下来 模拟执行的时候![image](https://bbs.kanxue.com/view/img/face/006.gif)

## 回复 by vior (#23)

*2025-11-26 15:37*

>
> [iCookiie](https://bbs.kanxue.com/user-970595.htm)
>
>  我是说dump下来 模拟执行的时候[em_006]
>
>

我这边的处理方式就是动态加载了，现在是分割成多个小的部分接在前后，后面模拟执行就动态加载当时获取的上下文接着跑

## 回复 by hpphpp (#24)

*2025-11-26 17:24*

>
> [vior](https://bbs.kanxue.com/user-930478.htm)
>
>  我这边的处理方式就是动态加载了，现在是分割成多个小的部分接在前后，后面模拟执行就动态加载当时获取的上下文接着跑
>
>

没太理解, 我理解只是dump了入口点时候的上下文(寄存器和内存)， 后续执行的上下文是没有的，那跳过外部跳转后的执行还是会报错吧，没有执行外部跳转后的上下文了。

## 回复 by vior (#25)

*2025-11-26 18:31*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  hpphpp](https://bbs.kanxue.com/user-226208.htm)
>
>  没太理解, 我理解只是dump了入口点时候的上下文(寄存器和内存)， 后续执行的上下文是没有的，那跳过外部跳转后的执行还是会报错吧，没有执行外部跳转后的上下文了。
>
>

有的，我这边是调用了 ida 直接跑到后面一条指令，再次获取上下文接着跑，所以可以全部处理且不会丢数据。但外部调用密集的话效率会低很多，在外部调用较少的 vm 比较好用

## 回复 by XCicada (#26)

*2025-11-27 15:52*

感谢分享

## 回复 by iCookiie (#27)

*2025-12-1 18:07*

>
> [vior](https://bbs.kanxue.com/user-930478.htm)
>
>  我这边的处理方式就是动态加载了，现在是分割成多个小的部分接在前后，后面模拟执行就动态加载当时获取的上下文接着跑
>
>

可能是我太菜鸡了 跟着没跑起来 但是模拟执行的时候拿到了上下文 但是模拟执行遇到了SVC指令咋办? 我还是有点不太理解![image](https://bbs.kanxue.com/view/img/face/006.gif)

## 回复 by hpphpp (#28)

*2025-12-2 16:42*

>
> [vior](https://bbs.kanxue.com/user-930478.htm)
>
>
>
>
>
>
>
>  hpphpp
>
>
>
>  没太理解, 我理解只是dump了入口点时候的上下文(寄存器和内存)， 后续执行的上下文是没有的，那跳过外部跳转后的执行还是会 ...
>
>

那这样的话对有反调试的应用很不好适用,ida附件调试运行两步总是会报错.

## 回复 by vior (#29)

*2025-12-2 18:03*

>
> [iCookiie](https://bbs.kanxue.com/user-970595.htm)
>
>  可能是我太菜鸡了 跟着没跑起来 但是模拟执行的时候拿到了上下文 但是模拟执行遇到了SVC指令咋办? 我还是有点不太理解[em_006]
>
>

加个识别 svc 指令后运行跳过，需要加下代码，我后面改一下

## 回复 by vior (#30)

*2025-12-2 18:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  hpphpp](https://bbs.kanxue.com/user-226208.htm)
>
>  那这样的话对有反调试的应用很不好适用,ida附件调试运行两步总是会报错.
>
>

是的，要用这个工具首先得要能正常调试，得干掉反调。这个工具最好用的还是在外部调用较少的 vm 里

## 回复 by git_94730eaydwshawke-gif (#31)

*2025-12-9 19:20*

666

## 回复 by _0xA1pha (#32)

*2025-12-12 15:52*

666

## 回复 by ShinoLeah (#33)

*2025-12-12 15:55*

大佬牛逼666

## 回复 by 小今朝 (#34)

*2026-1-21 10:58*

大佬牛逼666
