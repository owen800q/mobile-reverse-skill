---
title: '[求助]Root过的华为手机，如何让应用一直在后台运行，不受电池优化、Doze影响'
url: https://bbs.kanxue.com/thread-280776.htm
tid: 280776
author: mb_nywyielj
date: '2024-03-05'
tags: [Android安全, 求助, 系统相关]
crawled_at: '2026-08-12T04:01:57+00:00'
replies: 10
---

Root过的华为手机，如何让应用一直在后台运行，不受起电池、后台运行影响。现在目前是，应用退入后台，会受到后台运行权限影响，导致应用被挂起，息屏后，受到Doze影响，应用被挂起。
有什么方法可以突破系统限制嘛，针对Root过的手机

---

# 回复

## 回复 by mb_nywyielj (#2)

*2024-3-6 13:28*

除了手动设置外，还有其他方式嘛

## 回复 by mb_fidppcok (#3)

*2024-3-6 14:11*

好像把目标应用设为系统 应用就好了？

## 回复 by 小黄鸭爱学习 (#4)

*2024-3-6 19:00*

root还不简单吗 写个守护进程注入到系统应用就行

## 回复 by mb_nywyielj (#5)

*2024-3-7 10:07*

>
> [小黄鸭爱学习](https://bbs.kanxue.com/user-832784.htm)
>
>  root还不简单吗 写个守护进程注入到系统应用就行
>
>

是怎样的方式，有github嘛

## 回复 by mb_nywyielj (#6)

*2024-3-7 10:07*

>
> [mb_fidppcok](https://bbs.kanxue.com/user-986312.htm)
>
>  好像把目标应用设为系统 应用就好了？
>
>

没用，而且变成系统应用还得借助magisk等方式

## 回复 by 珍惜Any (#7)

*2024-3-7 10:17*

最笨的方法，root以后直接把apk挂载成系统apk ，再写个shell脚本定时启动 。

## 回复 by mb_nywyielj (#8)

*2024-3-7 10:23*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  最笨的方法，root以后直接把apk挂载成系统apk ，再写个shell脚本定时启动 。
>
>

我试过变成系统应用，但是依旧逃不过后台运行优化和息屏后的Doze优化

## 回复 by 情迁 (#9)

*2024-3-7 10:48*

xposed hook 桌面 通话等高优先级系统应用写一些保活检测逻辑试试

## 回复 by mb_nywyielj (#10)

*2024-3-7 11:16*

>
> [情迁](https://bbs.kanxue.com/user-769855.htm)
>
>  xposed hook 桌面 通话等高优先级系统应用写一些保活检测逻辑试试
>
>

写保活检测逻辑的目的是什么？

## 回复 by mb_nywyielj (#11)

*2024-3-10 16:57*

嘀嘀嘀
