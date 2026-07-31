---
title: '[原创][Android]记一次艰难的Android11抓包过程'
url: https://bbs.kanxue.com/thread-281090.htm
tid: 281090
author: Shangwendada
date: '2024-03-25'
tags: [Android安全, 原创, 基础理论, 漏洞相关, 系统相关, 其他]
crawled_at: '2026-07-31T14:29:16+08:00'
replies: 10
---

## 前言

最近开始学习app渗透，抓包是必不可少的过程，接下来记录一下我遇到的一些小麻烦。

## 设备环境

![file](https://bbs.kanxue.com/upload/attach/202403/979679_RNT7Z248CJTXSXW.jpg)

## 问题

首先呢，由于Android版本大于等于7.0之后系统不再信任用户的CA证书（应用 targetSdkVersion >= 24 时生效，如果 targetSdkVersion < 24 即使系统是 7.0 + 依然会信任）简而言之就是如果只是用户CA证书那么https包就抓不到了。

### 方法一（手动将证书移动至/system/etc/security/cacerts/）（未解决）

由于我们采用的抓包工具是burpsuit，那我们这里就以burpsuit的抓包方式举例子。
首先下载burpsuit的证书（访问burpsuit的监听端口即可）
![file](https://bbs.kanxue.com/upload/attach/202403/979679_2UWGQHD8E5UKJFX.jpg)
下载好了之后，首先需要计算cacert.der的哈希值 ，命令如下。

| 1 | `openssl x509 -inform der -subject_hash_old -``in` `cacert.der -noout` |
|-|-|

得到的应该都是9a5ba575
那么将文件名称更改为9a5ba575.0，传入到我们手机中。
如果直接一步到位，大概率会出现如下情况
![file](https://bbs.kanxue.com/upload/attach/202403/979679_WJRJ4YC49ET8HBP.jpg)
出现这种情况的原因很多，有可能是没有使用adb root 来让adb终端的默认权限是root，如果adb root无法使用可能是因为io.debuggable不为1导致的。可以使用如下命令查询

| 1 | `adb shell getprop ro.debuggable` |
|-|-|

既然不能这样那么我们不妨先push到/data/local/tmp中，再移动到/system/etc/security/cacerts/，按理说这就是系统默认信任证书的文件夹，我们移动过去应该就可以成功装上证书了，但是奇怪的一幕发生了。
![file](https://bbs.kanxue.com/upload/attach/202403/979679_QV6CB2MHGS3CHDJ.jpg)
(崩溃...)

---

后经检查发现，是我的system分区没有解锁
别的版本解锁请看如下文章：
<http://m.romjd.com/reviews/content/7448>

### 方法二（Magisk模块大法）

到了安卓11和安卓12机型，已经不能通过TWRP或者syslock软件暴力解锁system分区啦，已知目前解锁system方法，都是对系统分区进行2次打包改造，实现解锁system分区的效果。

emm不会，本文到此结束！

当然，结束是不可能结束的，正所谓柳暗花明又一村，Magisk有一个模块可以完美解决我们的问题！
项目地址分享如下：<https://github.com/Bloody-Badboy/Move-User-Certificates>
刷上上模块之后我们将cacert.der改成cacert.cer
![file](https://bbs.kanxue.com/upload/attach/202403/979679_XPJRYTK6JUBPB4E.jpg)

直接安装证书就可以了，模块就会自动帮我们加载成系统证书

![file](https://bbs.kanxue.com/upload/attach/202403/979679_WSR8KZSG5K2UMWD.jpg)

## 上代理抓包！

### 记录主机地址

![file](https://bbs.kanxue.com/upload/attach/202403/979679_ERPYWAV9TMZWKX8.jpg)

### 记录手机地址

![file](https://bbs.kanxue.com/upload/attach/202403/979679_N5HYCNRUHYFECJE.jpg)

### 设置监听

![file](https://bbs.kanxue.com/upload/attach/202403/979679_W3ZE74UZ93R6DRX.jpg)

### 设置代理

![file](https://bbs.kanxue.com/upload/attach/202403/979679_Y8KU4W728VHWY3X.jpg)

### Over!!

![file](https://bbs.kanxue.com/upload/attach/202403/979679_4CCGQ9MVVH9DSC4.jpg)

---

# 回复

## 回复 by 疯狂玩家1号3 (#2)

*2024-3-25 22:14*

还有个模块这个用的比较多https://github.com/Magisk-Modules-Repo/movecert

## 回复 by gamehack (#3)

*2024-3-25 23:32*

感谢分享!

## 回复 by 秋狝 (#4)

*2024-3-26 09:19*

感谢分享

## 回复 by iyue_t (#5)

*2024-3-27 21:48*

https://github.com/ys1231/MoveCertificate 不要让证书成为分析的阻碍.

## 回复 by RiDiN (#6)

*2024-3-28 09:33*

redacted

## 回复 by Shangwendada (#7)

*2024-3-29 15:10*

>
> [RiDiN](https://bbs.kanxue.com/user-762254.htm)
>  redacted
>

谢谢分享

## 回复 by Shangwendada (#8)

*2024-3-29 15:15*

>
> [iyue_t](https://bbs.kanxue.com/user-853140.htm)
>
>  https://github.com/ys1231/MoveCertificate 不要让证书成为分析的阻碍.
>
>

感谢分享

## 回复 by PanLi77 (#9)

*2024-6-11 08:59*

The client failed to negotiate a TLS connection to atipv6.pinduoduo.com:443: Received fatal alert: certificate unknown；
Failed to connect to the configured Collaborator sever: polling.oastify.com.
证书都安装了，怎么会出现这种错误？

## 回复 by ThreeDCKM (#10)

*2024-9-29 00:48*

哪位大佬可以帮我破解一个软件，重金酬谢，最好是江浙沪地区的，谢谢！

## 回复 by aibot (#11)

*2024-9-29 16:29*

可以私信我发来看看
