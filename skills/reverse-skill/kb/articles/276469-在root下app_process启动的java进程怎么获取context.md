---
title: '[求助]在root下app_process启动的java进程怎么获取context'
url: https://bbs.kanxue.com/thread-276469.htm
tid: 276469
author: Troy
date: '2023-03-14'
tags: [Android安全, 求助, 程序开发, 系统相关]
crawled_at: '2026-08-11T08:48:32+00:00'
replies: 12
---

最近在写一个root下的服务进程 。本来想获取下设备的一些基础信息 。看到好多信息都是要拿到context才可以获取 。。但是用app_process启动的进程没有这个东西 。。有没有什么办法拿到这个呢。

---

# 回复

## 回复 by seeeseee (#2)

*2023-3-14 13:39*

只能拿一点点

https://github.com/Genymobile/scrcpy/blob/master/server/src/main/java/com/genymobile/scrcpy/Workarounds.java

## 回复 by Troy (#3)

*2023-3-14 16:39*

>
> [seeeseee](https://bbs.kanxue.com/user-941366.htm)
>
>  只能拿一点点https://github.com/Genymobile/scrcpy/blob/master/server/src/main/java/com/genymobile/scrcpy/Wo ...

感觉这个办法拿到过后 好多东西还是用不了 要异常。。

其实我主要是想拿到屏幕的分辨率 。但是自己并没有app。就一个root服务和app_process启动的服务。。很蛋疼。看了下scrcpy代码。感觉他获取分辨率都是通过adb传进来的参数。不知道是不是。

## 回复 by 你瞒我瞒 (#4)

*2023-3-15 09:53*

你想要系统属性的信息，可以通过Runtime.exec方法执行getprop获取，包括上面说的分辨率

## 回复 by hekes (#5)

*2023-3-15 09:54*

我也研究了几天，好像是拿不到的，反射调用也拿不到

## 回复 by seeeseee (#6)

*2023-3-15 10:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Troy](https://bbs.kanxue.com/user-56685.htm)
>
>
>
>
>
>
>
>  seeeseee
>
>  只能拿一点点https://github.com/Genymobile/scrcpy/blob/master/server/sr ...
>
>

所以我说只能拿一点点，很多东西是拿不到的。有root建议把自己注入到system_server或者Settings中去。![image](https://bbs.kanxue.com/view/img/face/27.gif)

## 回复 by hekes (#7)

*2023-3-15 11:18*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  你想要系统属性的信息，可以通过Runtime.exec方法执行getprop获取，包括上面说的分辨率
>
>

分辨率倒是可以通过反射获取到

## 回复 by Troy (#8)

*2023-3-15 13:11*

其实我是想抓个图片。分辨率我抄scrcpy 反射android.hardware.display.DisplayManagerGlobal可以拿到了 。抓图手机屏幕过后。。Bitmap 我要传走。转换成2进制bmp.compress(Bitmap.CompressFormat.PNG, 100, stream); 这一句居然执行了1秒 。什么情况。我记得现在的CPU 抓屏到把数据传走也就毫秒级的 。这个玩意这么慢么。

## 回复 by t1n9 (#9)

*2023-3-15 15:32*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Troy](https://bbs.kanxue.com/user-56685.htm)
>
>  其实我是想抓个图片。分辨率我抄scrcpy 反射android.hardware.display.DisplayManagerGlobal可以拿到了 。抓图手机屏幕过后。。Bitmap 我要传走。转换 ...
>
>

shell执行 wm size

## 回复 by mb_ootltcss (#10)

*2023-5-11 22:23*

我做过一个跟楼主几乎完全一样的事情，甚至抄的也是scrcpy，传图片用内存映射就可以做到几十毫秒了。
但是我遇到那个代理进程我不知道怎么保活，在一些虚拟机上面经常被杀。如果楼主知道告诉我一下。

## 回复 by mb_ootltcss (#11)

*2023-5-11 22:40*

>
> [seeeseee](https://bbs.kanxue.com/user-941366.htm)
>
>  所以我说只能拿一点点，很多东西是拿不到的。有root建议把自己注入到system_server或者Settings中去。[em_27]
>
>

老大能不能讲讲app_process启动的进程如何做保活

## 回复 by WindStormy (#12)

*2023-5-13 16:20*

1. 反射调用ActivityThread的getSystemContext获取到systemcontext；
2. 反射调用Context的createPackageContext方法，传入包名，获取到指定包的context对象
然后你就可以愉快的屏幕分辨率了。

## 回复 by hmlyn (#13)

*2025-7-30 15:27*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ootltcss](https://bbs.kanxue.com/user-978470.htm)
>
>  我做过一个跟楼主几乎完全一样的事情，甚至抄的也是scrcpy，传图片用内存映射就可以做到几十毫秒了。
> 但是我遇到那个代理进程我不知道怎么保活，在一些虚拟机上面经常被杀。如果楼主知道告诉我一下。
>
>

我也想做一个按需截图，能分享下吗？
