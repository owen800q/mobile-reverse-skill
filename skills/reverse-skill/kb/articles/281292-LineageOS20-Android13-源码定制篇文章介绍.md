---
title: '[原创] LineageOS20（Android13）源码定制篇文章介绍'
url: https://bbs.kanxue.com/thread-281292.htm
tid: 281292
author: smallnn
date: '2024-04-12'
tags: [Android安全, 原创, HOOK注入, 源码框架, 逆向分析, 系统相关, 基础理论, 脱壳反混淆]
crawled_at: '2026-08-11T08:45:49+00:00'
replies: 18
---

# 本文章分类主要是分享本人从事Android安全逆向三年来的各种技术成果以及经验。

# 从业几年来，发现关于源码定制的资料零散，要么误导，要么收费价格很高，踩坑众多，希望我的一些经验或者技术成果可以帮到想学技术的同学们。

# 如下是本人暂时想到的可以分享的一些技术或知识点，将按照目录不定期更新目录和文章，如有错误，希望各位大佬可以指正。

## 1.不进入开发者模式，自动开启USB调试，adb自动授权

## 2.LineageOS20 系统签名，编译user、release版本系统，去除任何Root特征，但保留ROOT权限可实现的功能，如访问APP沙箱等

## 3.定制非Root、反检测Hook框架Xtweak----兼容Xposed API、目前无任何厂商可以检测该Hook框架，插件管理类似LSPManager，插件安装实时生效无需重启。

## 4.移植Fart脱壳机到Android13,优化修改，以HTTP API方式访问脱壳，进度一目了然。增加被动调用，对抗主动调用检测。

## 5.APP通信流量加解密框架，可无视APP加密,直接截获明文流量到抓包工具，框架以插件开发，可适配任意APP，从此不再有加密数据流量。

---

# 回复

## 回复 by 你瞒我瞒 (#2)

*2024-4-12 09:12*

太强了吧，期待更新

## 回复 by 秋狝 (#3)

*2024-4-12 09:23*

感谢分享

## 回复 by yuzhouheike (#4)

*2024-4-12 10:12*

支持！等大佬更新

## 回复 by lanliqiang (#5)

*2024-4-12 15:54*

支持。![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by lanliqiang (#6)

*2024-4-12 15:55*

编译出来的LineageOS20 更改 prop 的相关设置后，可以过GMS 的droidgard吗？

## 回复 by Imxz (#7)

*2024-4-12 16:33*

牛逼啊 老哥 期待期待

## 回复 by vigiles (#8)

*2024-4-13 10:36*

期待博主更新，正想基于los做个老年机????

## 回复 by vigiles (#9)

*2024-4-13 10:38*

![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by MsScotch (#10)

*2024-4-13 15:05*

tql

## 回复 by wx_最爱老大 (#11)

*2024-4-16 08:10*

????

## 回复 by xiaoski (#12)

*2024-5-22 11:35*

坐等大佬更新，mark学习

## 回复 by caolinkai (#13)

*2024-5-22 12:33*

大佬牛逼

## 回复 by 琳宇 (#14)

*2024-5-22 15:01*

本人也在做，期待突破互相借鉴

## 回复 by vigiles (#15)

*2024-5-22 19:11*

期待大佬新作????

## 回复 by 拾海 (#16)

*2024-5-22 19:44*

期待期待

## 回复 by hacker521 (#17)

*2024-5-23 16:09*

你倒是更新啊？

## 回复 by mb_unumjnpi (#18)

*2024-9-22 02:25*

能定制个改机系统吗

## 回复 by 寻梦之璐 (#19)

*2024-9-24 15:16*

快半年了，你更新哇，佬
