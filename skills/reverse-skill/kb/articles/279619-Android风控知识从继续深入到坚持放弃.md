---
title: '[原创]Android风控知识从继续深入到坚持放弃'
url: https://bbs.kanxue.com/thread-279619.htm
tid: 279619
author: 恋空
date: '2023-11-21'
tags: [Android安全, 原创, 基础理论, 逆向分析, 混淆加固, 程序开发, 系统相关]
crawled_at: '2026-08-11T08:46:35+00:00'
replies: 23
---

### 前言

继续前几篇的内容，最近研究国内几大电商App以及几大风控sdk有了一些深入了解，以及有一些有趣的检测方式的了解，本文主要给大家讲解一下我遇到的一些的奇葩检测方式。

有兴趣的朋友也可以了解一下前几篇的内容：
·常见参数讲解：<https://bbs.kanxue.com/thread-265169.htm>
·Binder黑科技：<https://bbs.kanxue.com/thread-278364.htm>
·设备指纹讲解：<https://bbs.kanxue.com/thread-275202.htm>

对了，想起来有些事情跟大家讲一下，本人既不卖课也不卖教程，各位不要再来找我要课了，不打算出书也不打算卖课，都是纯分享给新手解惑！

### 1、检测你手机有没有锁屏密码？

出处：某宝、某付宝SDK
奇葩程度：666 (三星中评)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202311/862224_3M82DRWQGQ8P39B.webp)

以上代码已被学习用于我公司的检测逻辑（感谢大厂的支招！）

###### 复现代码：

| 123456 | `/``/` `检测手机是否有锁屏密码``/``/` `Write By: Liankong xhew.new@qq.com``public static boolean isHasUnlockPassword(Context context) {``KeyguardManager km` `=` `(KeyguardManager) context.getSystemService(Context.KEYGUARD_SERVICE);``return` `km.isDeviceSecure() && km.isKeyguardSecure();``}` |
|-|-|

### 2、通过binder检测是否真的有SIM卡

出处：某多
奇葩程度：66666（五星好评）
=== 此处应有图，但是因为不方便贴出来(手动滑稽) ===

###### 复现代码：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202311/862224_MEBNFE4ZU9M9TVH.webp)

###### 获取远程binder接口：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202311/862224_7JUGGPNPMURJ7US.webp)
因为研究用只做了高版本的支持，低版本应该改一下getRemoteBinder的对IBinder的获取方式

### 3、build.prop修改时间

出处：某多、某东
奇葩程度：666（一般吧）
 ![图片描述](https://bbs.kanxue.com/upload/attach/202311/862224_98XH2U7REQAAYKT.webp)
因为高版本SELinux限制了无法读取/system/build.prop，但是有很多模拟器或者比较弱的黑产还是采用修改build.prop重启的方式修改数据。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202311/862224_UENUUPQQBCT4EPT.webp)
而且SELinux并未先对该文件的stat/statfs访问，所以可以通过读取改文件的修改时间判断是否修改（正常通过编译出来的build.prop的修改时间要么是1970年1月要么是2009年1月1日）

###### 复现代码：

| 123456 | `/``/` `检测build.prop是否安全``/``/` `Write By: Liankong xhsw.new@qq.com``public static boolean isBuildPropSecure() {``File` `file` `=` `new` `File``(``"/system/build.prop"``);``return` `file``.lastModified()` `/` `1000` `%` `1000` `=``=` `0``;``}` |
|-|-|

### 4、检测手机上的应用商店包名？

出处：某多、某某（编不下去了）
奇葩程度：66
 ![图片描述](https://bbs.kanxue.com/upload/attach/202311/862224_CGWWEPAE52J8Q6V.webp)

###### 复现代码：

| 1234567891011121314 | `/``/` `获取手机上的应用市场列表``/``/` `Write By: Liankong xhsw.new@qq.com``public static String[] getAppMarketList(Context context) {``PackageManager pm` `=` `context.getPackageManager();``Intent intent` `=` `new Intent();``intent.setAction(``"android.intent.action.MAIN"``);``intent.addCategory(``"android.intent.category.APP_MARKET"``);``List``<ResolveInfo>` `list` `=` `pm.queryIntentActivities(intent);``String res[]` `=` `new String[``list``.size()];``for``(``int` `i` `=` `0``;i <` `list``.size(); i``+``+``) {``res[i]` `=` `list``.get(i).activityInfo.packageName;``}``return` `res;``}` |
|-|-|

### 结语

先讲到这里吧，各位大厂手下留情，只为了让广大新手学习！同时，欢迎各位来交流，QQ：2928455383

---

# 回复

## 回复 by 恋空 (#2)

*2023-11-21 16:00*

后续内容正在加，莫急

## 回复 by 黑屏 (#3)

*2023-11-21 16:26*

期待ing...

## 回复 by hackdaliu (#4)

*2023-11-21 17:19*

期待ing

## 回复 by vigiles (#5)

*2023-11-21 19:46*

干货

## 回复 by vigiles (#6)

*2023-11-21 19:47*

![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 新气象 (#7)

*2023-11-22 08:09*

干货，学习了。

## 回复 by ty1937 (#8)

*2023-11-22 09:22*

真有意思，只有你想不到，没有做不了的风控![image](https://bbs.kanxue.com/view/img/face/41.gif)

## 回复 by 秋狝 (#9)

*2023-11-22 09:30*

感谢分享

## 回复 by wangzehua (#10)

*2023-11-22 09:54*

有点意思

## 回复 by 绝对小白 (#11)

*2023-11-22 11:57*

干货，thanks~!

## 回复 by 你瞒我瞒 (#12)

*2023-11-22 15:15*

>
> [恋空](https://bbs.kanxue.com/user-862224.htm)
>
>  后续内容正在加，莫急
>
>

在线等，急~![image](https://bbs.kanxue.com/view/img/face/41.gif)

## 回复 by pkiot (#13)

*2023-11-22 16:12*

不错

## 回复 by 万里星河 (#14)

*2023-11-22 17:03*

支持一下

## 回复 by 恋空 (#15)

*2023-11-22 17:41*

欢迎进群交流

![image](https://bbs.kanxue.com/upload/attach/202409/862224_H8YEBUDNGV55UJ8.webp)

## 回复 by StriveMario (#16)

*2023-12-8 18:06*

受教了

## 回复 by PoisonGZ (#17)

*2023-12-8 18:17*

Java 层同时抛出两个自定义错误，分别是Xposed 和 任意值，Xposed 堆栈 如果不存在Xposed 或者 任意值 堆栈包涵xposed 可以视为app被hook ，用来防小白特别好用

## 回复 by PoisonGZ (#18)

*2023-12-8 18:28*

自己的应用中创建一些比如Xposed 相关类，如果发现检测不到相关类，就可以默认用户使用了反检测模块

## 回复 by 恋空 (#19)

*2024-1-14 21:50*

>
> [PoisonGZ](https://bbs.kanxue.com/user-820516.htm)
>
>  Java 层同时抛出两个自定义错误，分别是Xposed 和 任意值，Xposed 堆栈 如果不存在Xposed 或者 任意值 堆栈包涵xposed 可以视为app被hook ，用来防小白特别好用
>
>

现在早就五花八门了，以前还是扫类名扫堆栈，现在风控都直接读maps提出地址，扫内存特征了。![image](https://bbs.kanxue.com/view/img/face/50.gif)

## 回复 by mb_joqmgxbb (#20)

*2024-4-27 15:55*

为什么要放弃？

## 回复 by 恋空 (#21)

*2024-4-27 23:15*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_joqmgxbb](https://bbs.kanxue.com/user-994954.htm)
>
>  为什么要放弃？
>
>

因为道高一尺，魔高一丈。

## 回复 by 淡然他徒弟 (#22)

*2024-4-28 06:06*

mark

## 回复 by 橘子皮儿 (#23)

*2024-5-8 19:29*

蹲更新

## 回复 by mb_ldbucrik (#24)

*2024-9-18 20:17*

期待更新
