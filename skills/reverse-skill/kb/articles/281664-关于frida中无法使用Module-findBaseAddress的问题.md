---
title: '[求助]关于frida中无法使用Module.findBaseAddress的问题'
url: https://bbs.kanxue.com/thread-281664.htm
tid: 281664
author: wx_鸳鸳相爆
date: '2024-05-09'
tags: [Android安全, 求助, 协议分析, HOOK注入, 逆向分析, 基础理论, 工具脚本]
crawled_at: '2026-08-11T08:45:26+00:00'
replies: 12
---

最近刚刚入门frida
跟着大佬的教程学习
谁知道第一句代码就运行不了
大佬的帖子地址<https://bbs.pediy.com/thread-272579.htm>
 ![图片描述](https://bbs.kanxue.com/upload/attach/202405/869889_NK5ZWU7GGK5QUY8.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202405/869889_UM2S595HXJDZPSD.webp)
但是我的没有地址
但是如果换成系统的so
 ![图片描述](https://bbs.kanxue.com/upload/attach/202405/869889_56QXAPRXXQ7XA5Q.webp)
就有地址输出
 ![图片描述](https://bbs.kanxue.com/upload/attach/202405/869889_7FJ29J2DZZ66T4V.webp)
请各位大佬批评指点 谢谢

---

# 回复

## 回复 by lipengzhu (#2)

*2024-5-9 10:11*

先hook android_dlopen_ext，等libnative-lib.so加载后再hook里面的东西

## 回复 by 寻梦之璐 (#3)

*2024-5-9 14:21*

你用frida启动app，你自己写的so都还没加载，找不到，等so加载完之后你的脚本已经执行完了

## 回复 by wx_鸳鸳相爆 (#4)

*2024-5-10 03:15*

>
> [寻梦之璐](https://bbs.kanxue.com/user-917635.htm)
>
>  你用frida启动app，你自己写的so都还没加载，找不到，等so加载完之后你的脚本已经执行完了
>
>

那应该怎么写 我还以为是模拟器有问题

## 回复 by KerryS (#5)

*2024-5-10 04:48*

看看这个so被谁调用了，或者在哪加载的，没加载肯定是找不到地址

## 回复 by wx_鸳鸳相爆 (#6)

*2024-5-10 14:28*

>
> [lipengzhu](https://bbs.kanxue.com/user-235931.htm)
>
>  先hook android_dlopen_ext，等libnative-lib.so加载后再hook里面的东西
>
>

已经尝试过了，也hook成功了，加载之后再调用Module.findBaseAddress还是返回null

## 回复 by wx_鸳鸳相爆 (#7)

*2024-5-10 14:29*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  KerryS](https://bbs.kanxue.com/user-844633.htm)
>
>  看看这个so被谁调用了，或者在哪加载的，没加载肯定是找不到地址
>
>
>

加载结束了 因为APK调用so层随机生成加密算法了

## 回复 by 寻梦之璐 (#8)

*2024-5-10 14:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_鸳鸳相爆](https://bbs.kanxue.com/user-869889.htm)
>
>  那应该怎么写 我还以为是模拟器有问题
>
>

试试加载后进行attach附加呢？attach能打印出来么

## 回复 by kinglinzi (#9)

*2024-5-11 15:18*

模拟器是x86的，还是用真机吧

## 回复 by wx_鸳鸳相爆 (#10)

*2024-5-14 22:00*

>
> [kinglinzi](https://bbs.kanxue.com/user-794100.htm)
>
>  模拟器是x86的，还是用真机吧
>
>

大佬说对了 真机就内有问题

## 回复 by jfztaq (#11)

*2024-8-24 07:42*

我也遇到了，用的是真机

## 回复 by 日暮归途 (#12)

*2024-8-26 13:34*

用frida-U-f包名启动，再给一秒钟启动加载时间试试

## 回复 by 小秃秃驴 (#13)

*2025-2-13 18:47*

我用真机也遇到了
