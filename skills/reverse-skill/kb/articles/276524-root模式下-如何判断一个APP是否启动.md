---
title: '[求助]root模式下。如何判断一个APP是否启动。'
url: https://bbs.kanxue.com/thread-276524.htm
tid: 276524
author: Troy
date: '2023-03-17'
tags: [Android安全, 求助, 程序开发, 系统相关]
crawled_at: '2026-08-12T04:02:31+00:00'
replies: 10
---

我有个root服务进程。我怎么去判断一个app是否启动呢 。其实可以遍历linux进程名。但是我想判断这个app是否前台。。。

如果没有启动。我想启动他 。感觉Android不像ios 。好多在java虚拟机里面。root进程都不好实现。

---

# 回复

## 回复 by vay (#2)

*2023-3-17 18:51*

判断APP在前台，可以了解一下无障碍模式中的“获取当前Activity”功能

## 回复 by chinester (#3)

*2023-3-17 18:53*

是否在前台 Shell执行下 dumpsys activity

## 回复 by Troy (#4)

*2023-3-17 19:29*

>
> [chinester](https://bbs.kanxue.com/user-39042.htm)
>
>  是否在前台 Shell执行下 dumpsys activity
>
>

嗯 用命令确实可以判断 。主要是怎么启动一个app。。。这个好像用linux的方法不太好搞。。

## 回复 by 小木马 (#5)

*2023-3-18 16:17*

am start可以启动app

## 回复 by Troy (#6)

*2023-3-19 13:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  小木马](https://bbs.kanxue.com/user-917329.htm)
>
>  am start可以启动app
>
>

感谢 我就是用的am start启动的 但是这个启动要获取包的活动名字。获取这个费了下力。

## 回复 by 琳宇 (#7)

*2023-3-19 21:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Troy](https://bbs.kanxue.com/user-56685.htm)
>
>  感谢 我就是用的am start启动的 但是这个启动要获取包的活动名字。获取这个费了下力。
>
>

这个并不难，你只需要找到mainActivity就可以了。有这个main属性的

## 回复 by Troy (#8)

*2023-3-20 11:28*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  琳宇](https://bbs.kanxue.com/user-853393.htm)
>
>  这个并不难，你只需要找到mainActivity就可以了。有这个main属性的
>
>

我是直接找到安装包 然后解出apk里面的那个xml然后去分析的 。还是有点按麻烦。

## 回复 by Gordonhat (#9)

*2023-3-20 17:32*

getPackageManager().getLaunchIntentForPackage("xxx.xxx") 这个不就启动指定应用了么

## 回复 by TrumpWY (#10)

*2023-3-21 09:25*

在Root模式下，可以通过以下方式判断一个 APP 是否启动：

1.查看进程列表：可以使用命令行工具（如Terminal）或者 Android 应用（如 Root Explorer）来查看当前系统中的进程列表。可以在进程列表中查找相应的 APP 进程是否存在，如果存在则说明 APP 已经启动。

2.监听日志输出：可以使用命令行工具（如 logcat）或者 Android 应用（如 CatLog）来监听系统日志输出，通过过滤日志信息来判断是否有相应的 APP 启动信息。例如，可以通过过滤包名或者应用名称，来查看相应的 APP 是否有启动日志输出。

3.查看应用状态：可以使用命令行工具（如 am）或者 Android 应用（如 Tasker）来查看应用状态。通过使用 am 命令中的 get-task-state 参数，可以获取应用的状态信息，包括是否在前台运行或者后台运行等。

需要注意的是，以上方法都需要在 Root 权限下运行，否则可能无法访问系统进程或者系统日志。同时，这些方法也可能存在一定的局限性，例如如果应用采用了隐藏进程或者加密日志的方式，那么以上方法可能无法起作用。

from ChatGPT

## 回复 by 冷冻猫咪 (#11)

*2023-3-22 13:49*

取进程pid判断是否有指定应用包名！![image](https://bbs.kanxue.com/upload/attach/202303/915097_ANYA9FRRYE8G4BP.jpg)
