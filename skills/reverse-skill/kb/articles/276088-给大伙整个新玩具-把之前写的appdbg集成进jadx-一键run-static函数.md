---
title: '[原创]给大伙整个新玩具，把之前写的appdbg集成进jadx，一键run static函数。'
url: https://bbs.kanxue.com/thread-276088.htm
tid: 276088
author: asmjmp0
date: '2023-02-12'
tags: [Android安全, 原创, 逆向分析, 工具脚本]
crawled_at: '2026-08-12T04:02:39+00:00'
replies: 10
---

链接见：[AndroidRunnableJadx](https://github.com/asmjmp0/AndroidRunnableJadx)
 ![image](https://bbs.kanxue.com/upload/attach/202302/772806_NXJ9DG384Y3QXUH.png)

---

# 回复

## 回复 by DirtyAngle (#2)

*2023-2-13 10:06*

鸡哥牛批

## 回复 by 破绽百出 (#3)

*2023-2-14 08:13*

动态函数可以嘛 创建一个实例再调用

## 回复 by 你瞒我瞒 (#4)

*2023-2-14 09:23*

好工具，收藏！

## 回复 by TrumpWY (#5)

*2023-2-14 10:54*

不知道咋用啊，试了几个简单的函数  init都不行啊

## 回复 by asmjmp0 (#6)

*2023-2-14 14:22*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_uzklxgat](https://bbs.kanxue.com/user-873266.htm)
>
>  动态函数可以嘛 创建一个实例再调用
>
>

动态函数不明白意思，是类函数吗，如果是类函数需要用反射的一套找到构造函数，传参拿到实例，赋值给ins。

## 回复 by asmjmp0 (#7)

*2023-2-14 14:23*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  TrumpWY](https://bbs.kanxue.com/user-957821.htm)
>
>  不知道咋用啊，试了几个简单的函数 init都不行啊
>
>

报啥错呢？

## 回复 by TrumpWY (#8)

*2023-2-14 16:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  asmjmp0](https://bbs.kanxue.com/user-772806.htm)
>
>  报啥错呢？
>
>

win怎么配置appdbg-JDK路径啊，我配置JAVA_HOME = D:/DevTools/Java/zulu8.62.0.19-ca-jdk8.0.332-win_x64，报错：initialize failed, please use the jdk from appdbg-JDK...

## 回复 by asmjmp0 (#9)

*2023-2-14 21:08*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  TrumpWY](https://bbs.kanxue.com/user-957821.htm)
>
>  win怎么配置appdbg-JDK路径啊，我配置JAVA_HOME = D:/DevTools/Java/zulu8.62.0.19-ca-jdk8.0.332-win_x64，报错：initiali ...
>
>

github里面更新了下载地址，重新下载再看看

## 回复 by 破绽百出 (#10)

*2023-2-15 00:00*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  asmjmp0](https://bbs.kanxue.com/user-772806.htm)
>
>  动态函数不明白意思，是类函数吗，如果是类函数需要用反射的一套找到构造函数，传参拿到实例，赋值给ins。
>
>

就是没有static的函数

## 回复 by asmjmp0 (#11)

*2023-2-15 10:15*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_uzklxgat](https://bbs.kanxue.com/user-873266.htm)
>
>  就是没有static的函数
>
>

是的，如果是没有static，得手动用反射的那套机制获取instance。
