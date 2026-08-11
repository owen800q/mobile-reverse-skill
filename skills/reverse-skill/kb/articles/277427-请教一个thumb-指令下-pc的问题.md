---
title: '[求助]请教一个thumb 指令下 pc的问题'
url: https://bbs.kanxue.com/thread-277427.htm
tid: 277427
author: method
date: '2023-05-30'
tags: [Android安全, 求助, 基础理论]
crawled_at: '2026-08-11T08:47:42+00:00'
replies: 12
---

![图片描述](https://bbs.kanxue.com/upload/attach/202305/856431_MPQF2FRHC9V38QT.png)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202305/856431_D7PPM3HJRU24MQN.png)
以上两张图分别有一个adr指令 用于switch查表的地址 但是通过我的计算

| 12345 | `addr:` `0xBF5FF1E4` `ADR R2,``#8``R2` `=` `PC` `+``8``R2` `=` `0xBF5FF1E4` `+``4` `+``8` `(Pc在thumb模式下 指向地址``+``4``的位置)``R2` `=` `BF5FF1F0` `R2` `=` `jpt_BF5FF1EC(``0xBF5FF1F0``)` |
|-|-|

然而 这个计算公式在我的第二张图中发生了冲突

| 12345 | `addr:` `0xBF5FF29E` `ADR R3,``#8``R3` `=` `PC` `+``8``R3` `=` `0xBF5FF29E` `+``4` `+``8` `(Pc在thumb模式下 指向地址``+``4``的位置)``R3` `=` `0xBF5FF2AA``R3 !``=` `jpt_BF5FF2A6(``0xBF5FF2A8``)` |
|-|-|

而在我的动态调试下 图一二都能够正确的拿到table的地址
搞得我人麻了
有没有大哥指点一二，小弟感激不尽

---

# 回复

## 回复 by xzqc (#2)

*2023-5-30 19:00*

thumb下我记得是pc地址要mod4，就是这么sb

## 回复 by 风间仁 (#3)

*2023-5-30 19:59*

Register-relative and PC-relative expressions

In ARM state, the value of the PC is the address of the current instruction plus 8 bytes.

In Thumb state:

For B, BL, CBNZ, and CBZ instructions, the value of the PC is the address of the current instruction plus 4 bytes.

For all other instructions that use labels, the value of the PC is the address of the current instruction plus 4 bytes, with bit[1] of the result cleared to 0 to make it word-aligned.

## 回复 by 万里星河 (#4)

*2023-5-30 20:56*

>
> [风间仁](https://bbs.kanxue.com/user-30337.htm)
>
>  Register-relative and PC-relative expressionsIn&nbsp;ARM&nbsp;state,&nbsp;the&nbsp;v ...

应该是正解

## 回复 by method (#5)

*2023-5-30 22:40*

>
> [风间仁](https://bbs.kanxue.com/user-30337.htm)
>
>  Register-relative and PC-relative expressionsIn&nbsp;ARM&nbsp;state,&nbsp;the&nbsp;v ...
>
>

大哥威武![image](https://bbs.kanxue.com/view/img/face/67.gif)

## 回复 by method (#6)

*2023-5-31 10:39*

>
> [xzqc](https://bbs.kanxue.com/user-786724.htm)
>
>  thumb下我记得是pc地址要mod4，就是这么sb
>
>

之前尝试过，并不一定 ，3楼正解

## 回复 by xzqc (#7)

*2023-6-1 08:41*

>
> [method](https://bbs.kanxue.com/user-856431.htm)
>
>  之前尝试过，并不一定 ，3楼正解
>
>

模4不就是4字节对齐了。。。

## 回复 by xzqc (#8)

*2023-6-1 08:45*

>
> [xzqc](https://bbs.kanxue.com/user-786724.htm)
>
>  模4不就是4字节对齐了。。。

低2位都为0了

## 回复 by 0x指纹 (#9)

*2023-6-1 09:38*

>
> [风间仁](https://bbs.kanxue.com/user-30337.htm)
>
>  Register-relative and PC-relative expressionsIn&nbsp;ARM&nbsp;state,&nbsp;the&nbsp;v ...
>
>

大哥V5![image](https://bbs.kanxue.com/view/img/face/67.gif)

## 回复 by method (#10)

*2023-6-2 14:19*

有这种意外![image](https://bbs.kanxue.com/upload/attach/202306/856431_2346GHQ243378VX.jpg)

## 回复 by method (#11)

*2023-6-2 14:19*

>
> [xzqc](https://bbs.kanxue.com/user-786724.htm)
>
>
>
>
>
>
>
>  xzqc
>
>  模4不就是4字节对齐了。。。 低2位都为0了
>
>

![image](https://bbs.kanxue.com/upload/attach/202306/ERZCP6CQ9ZQZCR4.jpg)有这种情况

## 回复 by 狐与虎 (#12)

*2025-3-5 23:07*

有大佬解释一下，为啥第一张图可以计算出来，第一张图也是Thumb 状态下吖，bit[1]没有清除为0

## 回复 by method (#13)

*2025-3-5 23:20*

>
> [狐与虎](https://bbs.kanxue.com/user-919914.htm)
>
>  有大佬解释一下，为啥第一张图可以计算出来，第一张图也是Thumb 状态下吖，bit[1]没有清除为0
>
>

第一张pc地址4字节对齐的
