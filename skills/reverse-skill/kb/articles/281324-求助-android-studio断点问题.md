---
title: '[讨论][求助]android studio断点问题'
url: https://bbs.kanxue.com/thread-281324.htm
tid: 281324
author: mb_maiyudos
date: '2024-04-14'
tags: [Android安全, 讨论, NDK分析]
crawled_at: '2026-08-11T08:45:45+00:00'
replies: 15
---

突然发现在android studio调试cpp代码,给cpp代码下断点，模拟器能断下来，然而真机上断不下来，真机上能给java代码断下来，然而c++的代码下了断点，却断不下来，这是什么原因，有大佬知道吗

---

# 回复

## 回复 by 严启真 (#2)

*2024-4-14 20:53*

有可能是ADB版本不吻合…

## 回复 by 你瞒我瞒 (#3)

*2024-4-15 09:23*

换个设备试试

## 回复 by mb_maiyudos (#4)

*2024-4-15 13:28*

>
> [严启真](https://bbs.kanxue.com/user-753452.htm)
>
>  有可能是ADB版本不吻合…
>
>

换了和android studio里面的adb也没用

## 回复 by 严启真 (#5)

*2024-4-15 14:25*

应该是要与终端API匹配…

## 回复 by 西瓜帅 (#6)

*2024-4-15 16:30*

有没有可能你手机用了magisk 并且开了zygote

## 回复 by 万里星河 (#7)

*2024-4-15 16:59*

楼上应该是正解

## 回复 by mb_maiyudos (#8)

*2024-4-15 18:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  西瓜帅](https://bbs.kanxue.com/user-823551.htm)
>
>  有没有可能你手机用了magisk 并且开了zygote
>
>

唉，关了，也没用了

## 回复 by mb_maiyudos (#9)

*2024-4-15 18:54*

之前确实开了，但我现在关了，而且重启了 并且删了，也没用

## 回复 by mb_maiyudos (#10)

*2024-4-15 19:00*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  西瓜帅](https://bbs.kanxue.com/user-823551.htm)
>
>  有没有可能你手机用了magisk 并且开了zygote
>
>

之前确实开了，但我现在关了，而且重启了 并且删了，也没用

## 回复 by mb_maiyudos (#11)

*2024-4-15 22:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  西瓜帅](https://bbs.kanxue.com/user-823551.htm)
>
>  有没有可能你手机用了magisk 并且开了zygote
>
>

就离谱了，用visual studio 就能断下来，还是cpp代码，android studio就不行了

## 回复 by mb_maiyudos (#12)

*2024-4-16 11:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  西瓜帅](https://bbs.kanxue.com/user-823551.htm)
>
>  有没有可能你手机用了magisk 并且开了zygote
>
>

应该是android studio 的原因，我用了vs的调试器和gdb调试器和ida的调试器都能下断点，就as不行

## 回复 by mb_maiyudos (#13)

*2024-4-16 18:00*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  西瓜帅](https://bbs.kanxue.com/user-823551.htm)
>
>  有没有可能你手机用了magisk 并且开了zygote
>
>

确实是zygisk的原因，我不知道还要在设置里关，我以为模块里关了就行了，感谢大佬。

## 回复 by wx_倾尽天下 (#14)

*2024-4-24 19:17*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_maiyudos](https://bbs.kanxue.com/user-987947.htm)
>
>  确实是zygisk的原因，我不知道还要在设置里关，我以为模块里关了就行了，感谢大佬。
>
>

学习了，感谢~

## 回复 by 西瓜帅 (#15)

*2024-6-28 15:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_maiyudos](https://bbs.kanxue.com/user-987947.htm)
>
>  确实是zygisk的原因，我不知道还要在设置里关，我以为模块里关了就行了，感谢大佬。
>
>

解决了 就好

## 回复 by wx_晴天_847 (#16)

*2024-6-28 15:36*

趋势是zygisk的原因，我不知道还要再设置里关，我以为模块里关了就行了，感谢大佬
