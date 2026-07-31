---
title: '[原创]开源一个 c 语言实现的 Android/Java 反编译器'
url: https://bbs.kanxue.com/thread-287081.htm
tid: 287081
author: neocanable
date: '2025-06-03'
tags: [Android安全, 原创, 基础理论, 逆向分析, 源码框架, 程序开发]
crawled_at: '2026-07-31T14:09:20+08:00'
replies: 26
---

磕磕碰碰的写了一年多的 Android/java 反编译软件开源了。

项目地址：<https://github.com/neocanable/garlic>，欢迎使用反馈。

---

**反编译apk速度**
反编译最新（2025-06-16）的微信，200M+大小, 19万+个类，需要12秒左右，默认4线程

| 1234567 | `garlic ~``/wechat/wechat``.apk``[Garlic] APK` `file` `analysis``File     : ~``/wechat/wechat``.apk``Save to  : ~``/wechat/wechat_apk``Thread   : 4``Progress : 192538 (192538)``[Done]` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202507/586240_24F5Z5AY4U45D5M.webp)

**现有功能**：

- 反编译.class文件
- 反编译.jar文件
- 反编译.dex文件
- 反编译.apk文件

**反编译效果**：

- lambda表达式还原
- 内部类和匿名还原
- 变量类型还原
- 变量名还原
- visibility annotation还原
- StringConcatFactory
- 赋值链还原
- 三元表达式还原
- synchronized还原

**开发中**：

- apk资源解码
- c# pe文件解码

**优点**：

- 贼快
- 占用资源少
- 没有过多的依赖库
- 轻松编译和运行

**缺点**：

- 代码路子比较野
- 单元测试还在补充中

**收获**：

- 更恨c++了
- c 语言不完全掌握，三级指针不敢用，二级指针用的哆哆嗦嗦

 **感谢**

- [vasthao](https://bbs.kanxue.com/homepage-422740.htm)老哥的帖子里面理论支持
- [aana_h2](https://space.bilibili.com/1535266)老哥的视频受益良多

---

效果：

参见附件

**更新2025-7-22**

- 支持apk
- 支持dex

上传的附件：
- ArrayUtils.java

（89.20kb，17次下载）
- ArrayUtils.class

（46.70kb，10次下载）
- PFiles.java

（18.69kb，10次下载）
- PFiles.class

（15.21kb，8次下载）

---

# 回复

## 回复 by mb_sigfdqjp (#2)

*2025-6-5 22:55*

不太懂，Java反编译是啥，smali反编译成Java吗？

## 回复 by neocanable (#3)

*2025-6-5 23:36*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_sigfdqjp](https://bbs.kanxue.com/user-1036563.htm)
>
>  不太懂，Java反编译是啥，smali反编译成Java吗？
>
>

.class和jar文件的反编译

## 回复 by huangjw (#4)

*2025-6-10 09:54*

关注

## 回复 by Canrad (#5)

*2025-6-10 16:28*

为啥用C写

## 回复 by neocanable (#6)

*2025-6-10 19:25*

>
> [Canrad](https://bbs.kanxue.com/user-970980.htm)
>
>  为啥用C写
>
>

就是为了练习练习c语言，没用c写过什么项目，所以这个用c写，发现c语言太纯粹了，而且代码行数多了，开发效率几乎都是差不多的了

## 回复 by 星雨心愿 (#7)

*2025-7-21 10:56*

不错，又可以复习下C

## 回复 by 恋一世的爱 (#8)

*2025-7-21 22:40*

是不是没办法在windows下运行

## 回复 by neocanable (#9)

*2025-7-22 12:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  恋一世的爱](https://bbs.kanxue.com/user-825246.htm)
>
>  是不是没办法在windows下运行
>
>

没有适配windows，你提个issue吧，我可以适配一下![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by neocanable (#10)

*2025-7-22 15:32*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  恋一世的爱](https://bbs.kanxue.com/user-825246.htm)
>
>  是不是没办法在windows下运行
>
>

我在win10上编译过了，感谢老哥提issue![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by neocanable (#11)

*2025-7-24 20:25*

哪位老哥在windows下提的deepseek的issue，已经处理了

## 回复 by 恋一世的爱 (#12)

*2025-7-25 00:03*

小伙子，能不能编译一个安卓用的arm64的版本

## 回复 by neocanable (#13)

*2025-7-25 12:56*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  恋一世的爱](https://bbs.kanxue.com/user-825246.htm)
>
>  小伙子，能不能编译一个安卓用的arm64的版本
>
>

老哥，提个issue，我搞个交叉编译的环境

## 回复 by k4y0z (#14)

*2025-7-25 17:15*

666

## 回复 by k4y0z (#15)

*2025-7-25 17:17*

666

## 回复 by neocanable (#16)

*2025-7-25 17:47*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  k4y0z](https://bbs.kanxue.com/user-1045151.htm)
>
>  666
>
>

麻烦发下你的运行环境，我找个机器测试一下

## 回复 by k4y0z (#17)

*2025-7-25 17:55*

>
> [neocanable](https://bbs.kanxue.com/user-586240.htm)
>
>  麻烦发下你的运行环境，我找个机器测试一下
>
>

666

## 回复 by neocanable (#18)

*2025-7-25 18:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  k4y0z](https://bbs.kanxue.com/user-1045151.htm)
>
>
>
>
>
>
>
>  neocanable
>
>
>
>  麻烦发下你的运行环境，我找个机器测试一下
>
>  666
>
>

是32还是64，或者是arm的？

## 回复 by neocanable (#19)

*2025-7-26 10:35*

android的aarch64编译出来了，可以测试一下

## 回复 by neocanable (#20)

*2025-7-26 10:36*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  k4y0z](https://bbs.kanxue.com/user-1045151.htm)
>
>
>
>
>
>
>
>  neocanable
>
>
>
>  麻烦发下你的运行环境，我找个机器测试一下
>
>  666
>
>

win版本的32位和64位的都弄出来了，可以测试一下

## 回复 by k4y0z (#21)

*2025-7-28 09:52*

>
> [neocanable](https://bbs.kanxue.com/user-586240.htm)
>
>  是32还是64，或者是arm的？
>
>

666

## 回复 by k4y0z (#22)

*2025-7-28 10:43*

>
> [neocanable](https://bbs.kanxue.com/user-586240.htm)
>
>  win版本的32位和64位的都弄出来了，可以测试一下
>
>

666

## 回复 by neocanable (#23)

*2025-7-28 12:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  k4y0z](https://bbs.kanxue.com/user-1045151.htm)
>
>
>
>
>
>
>
>  neocanable
>
>
>
>  win版本的32位和64位的都弄出来了，可以测试一下
>
>  666
>
>

cpu是什么的？是intel的还是arm的啊？

## 回复 by k4y0z (#24)

*2025-7-28 13:52*

>
> [neocanable](https://bbs.kanxue.com/user-586240.htm)
>
>  cpu是什么的？是intel的还是arm的啊？
>
>

666

## 回复 by neocanable (#25)

*2025-7-29 21:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  k4y0z](https://bbs.kanxue.com/user-1045151.htm)
>
>
>
>
>
>
>
>  neocanable
>
>
>
>  cpu是什么的？是intel的还是arm的啊？
>
>  666
>
>

不好意思，我实在复现不出你的错误，项目里有我的wechat，可以加一下测测不？

## 回复 by neocanable (#26)

*2025-11-23 22:16*

x86 win 支持

## 回复 by zylyy (#27)

*2025-11-23 22:42*

66666666
