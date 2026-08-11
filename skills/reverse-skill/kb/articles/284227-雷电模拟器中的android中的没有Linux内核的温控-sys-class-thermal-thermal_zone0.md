---
title: '[求助]雷电模拟器中的android中的没有Linux内核的温控/sys/class/thermal/thermal_zone0'
url: https://bbs.kanxue.com/thread-284227.htm
tid: 284227
author: hmlyn
date: '2024-11-04'
tags: [Android安全, 求助, 逆向分析, 系统相关]
crawled_at: '2026-08-11T08:44:19+00:00'
replies: 11
---

有个游戏检测是否为模拟器，它检查了是否存在/sys/class/thermal/thermal_zone0这个文件夹，如果没有就判定是模拟器，我看了。雷电所有系列的，都没有这个温控。

而/sys目录又属于虚拟文件系统，雷电的虚拟机镜像包里面并没有这个目录，需要系统启动后动态添加的，由于是虚拟文件系统，所有这个目录不管你是否有root权限，也无法任何修改，或者新建一个文件夹。

然后我把游戏里的检测代码，复制一份，自己写了个app

![image](https://bbs.kanxue.com/upload/attach/202411/636222_WBERGYTJH6RKVCB.webp)

检查如果没有thermal_zone0目录，就返回32

![image](https://bbs.kanxue.com/upload/attach/202411/636222_NHKCHFKFM7YFRAQ.webp)

然后我想到的办法是通过frida，hook一下。

![image](https://bbs.kanxue.com/upload/attach/202411/636222_926HNFW5AJDQW9N.webp)

![image](https://bbs.kanxue.com/upload/attach/202411/636222_G4D8F4MRP47BVZD.webp)

这个方法确实可行，但是由于游戏使用了爱加固企业版，使用frida直接崩溃了。

所以，我想，有没办法，直接底层，虚拟创建一个文件夹就好了，来解决。。

![image](https://bbs.kanxue.com/upload/attach/202411/636222_H4JGT83K5RT7B8P.webp)

---

# 回复

## 回复 by tDasm (#2)

*2024-11-4 14:12*

root下可以建立该文件夹，不是虚拟建立而是真实建立。
爱加密在模拟器上不能运行还有root检测等。

## 回复 by hmlyn (#3)

*2024-11-4 14:39*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  tDasm](https://bbs.kanxue.com/user-382.htm)
>
>  root下可以建立该文件夹，不是虚拟建立而是真实建立。
> 爱加密在模拟器上不能运行还有root检测等。
>
>

![image](https://bbs.kanxue.com/upload/attach/202411/636222_QEEHEQ6MEMD9X9J.webp)

我早测试了，创建不了的。

## 回复 by gailium (#4)

*2024-11-4 15:48*

挂载vmdk加吧

## 回复 by hmlyn (#5)

*2024-11-4 15:51*

vmdk里也没有

## 回复 by DawnDawnDawn (#6)

*2024-11-4 16:21*

把设置里面的system挂载可读写打开 然后创建就行

## 回复 by hmlyn (#7)

*2024-11-4 16:32*

>
> [DawnDawnDawn](https://bbs.kanxue.com/user-889655.htm)
>
>  把设置里面的system挂载可读写打开 然后创建就行
>
>

这些我都尝试过的了，不行的。

## 回复 by 你瞒我瞒 (#8)

*2024-11-7 10:37*

要不你模仿一下证书挂载那个模块，自己挂一个文件进去

## 回复 by DawnDawnDawn (#9)

*2024-11-9 15:50*

>
> [hmlyn](https://bbs.kanxue.com/user-636222.htm)
>
>  这些我都尝试过的了，不行的。
>
>

你要不直接hook sys层的函数 看看能不能捕获到java层的file调用进行一个替换

## 回复 by hmlyn (#10)

*2024-11-10 23:42*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  要不你模仿一下证书挂载那个模块，自己挂一个文件进去
>
>

挂载那些，是在system目录，肯定可以写的。问题是sys目录，它是一个Linux层的虚拟目录，无法挂载哦

## 回复 by taoying (#11)

*2024-11-14 09:29*

bind mount?

## 回复 by hacker521 (#12)

*2024-11-14 15:45*

mount bind应该可行
