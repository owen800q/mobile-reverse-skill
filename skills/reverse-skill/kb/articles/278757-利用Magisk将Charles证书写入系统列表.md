---
title: '[原创]利用Magisk将Charles证书写入系统列表'
url: https://bbs.kanxue.com/thread-278757.htm
tid: 278757
author: kzzll
date: '2023-09-07'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:38:21+08:00'
replies: 8
---

>
> 通过Magisk将Charles证书写入到系统列表
>
>
>

# 前言

 自从Android 7以后直接通过chls.pro/ssl安装证书也无法成功解密SSL数据包。
并且大部分系统无法使用adb root以进行挂载/system
如果你恰好使用了Magisk进行root，那么可以通过更加轻而易举的办法写入证书文件到/system/etc/security/cacerts

# 准备工作

1、Pixel 3
2、Charles
3、openSSL
4、Drony

# 写入证书流程

## 提取证书文件

打开Charles->Help->SSL Proxying->Save Charles Root……
拿到pem证书文件并获取它的hash，之前已经发过相关的提取方法：
<https://bbs.kanxue.com/thread-258996.htm>

| 1 | `openssl x509` `-``inform PEM` `-``subject_hash_old` `-``in` `charles.pem` |
|-|-|

并将chalres.pem重命名为 xxx.0 （数字0）

## 编辑Magisk模板

下载已经准备好的Magisk模板（其实已经搞完了）
<https://github.com/cih1996/write-charles-ssl>

仓库项目的READMEY已经讲述了，直接把你的xxx.0放到system/etc/security/cacerts

## 打包Magisk

将整个文件夹打包成ZIP，通过adb push 到手机上

## 安装Magisk模块

打开Magisk，安装上传的压缩包模块，重启设备即可

## 验证

通过 adb shell ls /system/etc/security/cacerts/ | findstr "xxx.0" 验证是否已经成功

# 开始抓包

某些APP会验证你是否开启了Wifi代理，这里通过Drony应用来实现VPN的方式进行转发即可，具体流程X度，X哥

---

# 回复

## 回复 by 秋狝 (#2)

*2023-9-7 09:19*

感谢分享

## 回复 by poppig (#3)

*2023-9-7 18:47*

还有另外一种方式
https://httptoolkit.com/docs/guides/android/#adb-interception

https://github.com/httptoolkit/httptoolkit-server/blob/main/src/interceptors/android/adb-commands.ts#L263

## 回复 by kzzll (#4)

*2023-9-7 22:36*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  poppig](https://bbs.kanxue.com/user-764.htm)
>
>  还有另外一种方式
> https://httptoolkit.com/docs/guides/android/#adb-interception
>
> https://github.com/httpto ...
>
>

又涨姿势了，大佬！

## 回复 by RiDiN (#5)

*2023-9-10 15:17*

<https://github.com/rev1si0n/lamda>

三行代码就搞定

```
from lamda.client import *

d = Device("192.168.x.x")
d.install_ca_certificate('charles.pem')
exit(0)
```

## 回复 by 王叔叔 (#6)

*2023-10-1 17:49*

这个跟adb push上去有何区别

## 回复 by xinsui (#7)

*2023-10-20 17:27*

>
> [RiDiN](https://bbs.kanxue.com/user-762254.htm)
>
>  https://github.com/rev1si0n/lamda 三行代码就搞定from&nbsp;lamda.client&nbsp;import&nbsp;*
>
> d& ...
>
>

帅哥，Packet Capture 这个抓包工具的证书，怎么提取出来哪

## 回复 by HerryLee (#8)

*2024-3-1 16:18*

move certificates这个插件好像行，我目前没遇到什么问题

## 回复 by mb_hicppwkc (#9)

*2024-5-23 15:50*

大佬有联系方式么
