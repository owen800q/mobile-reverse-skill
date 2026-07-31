---
title: '[原创]安卓证书助手AndroidCertHelper'
url: https://bbs.kanxue.com/thread-280510.htm
tid: 280510
author: xsSkyFall
date: '2024-02-12'
tags: [Android安全, 原创, 系统相关, 程序开发]
crawled_at: '2026-07-31T14:32:32+08:00'
replies: 0
---

写了个小工具：安卓证书助手 AndroidCertHelper

当前版本默认加载`/ststem/etc/security/cacerts/`路径。
帮助你快速找到过期的证书文件，安卓逆向分析中我之前证书就是因为过期了，还有证书重复，导致无法抓包，当时饶了好久。

由于安卓7以上抓包证书要放到系统目录，不能像之前安卓版本那样了，所以目前app支持安卓最小版本也为android 7.0。

git项目地址再这里:<https://github.com/xs-alpha/AndroidCertHelper>

编译好的apk下载可以点击这里：<https://devilwst.lanpv.com/ikvib1o2j9hi>

编译后的apk无壳无花，放心使用，也欢迎各位大佬提pr。

没学过安卓开发，纯现学现用，写的比较丑，大佬们见谅！
 ![image](https://bbs.kanxue.com/upload/attach/202402/853504_DBA496UBHT83DUW.webp)
