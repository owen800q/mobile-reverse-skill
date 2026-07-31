---
title: '[原创]frida动态加载和hook dex'
url: https://bbs.kanxue.com/thread-279732.htm
tid: 279732
author: 复活甲
date: '2023-12-01'
tags: [Android安全, 原创, HOOK注入]
crawled_at: '2026-07-31T14:36:21+08:00'
replies: 3
---

## 一、 frida 动态加载dex

首先我们自制一个dex,简单封装一个MD5的样例。代码如下：

| 1234567891011121314151617181920 | `package com.example.xibei;``import` `java.math.BigInteger;``import` `java.security.MessageDigest;` `public` `class` `SignMd5 {``public static String md5(String` `str``){` `try` `{``/``/` `生成一个MD5加密计算摘要``MessageDigest md` `=` `MessageDigest.getInstance(``"MD5"``);``/``/` `计算md5函数``md.update(``str``.getBytes());``return` `new BigInteger(``1``, md.digest()).toString(``16``);``} catch (Exception e) {``e.printStackTrace();``return` `null;``}` `}``}` |
|-|-|

然后我们开始打包编译成dex文件。

| 1 | `jar` `-``cvf xibei.jar com``/``example``/``xibei` |
|-|-|

| 1 | `/``root``/``Android``/``Sdk``/``build``-``tools``/``30.0``.``3``/``dx` `-``-``dex` `-``-``output xibei.dex xibei.jar` |
|-|-|

| 123 | `adb push` `/``data``/``local``/``tmp``/``xibei.dex` `chmod` `777` `xibei.dex` |
|-|-|

开始编写frida 脚本，代码如下：

| 1234567891011121314151617 | `function dy_dex() {``var xibei` `=` `Java.openClassFile(``"/data/local/tmp/xibei.dex"``);``Java.perform(function () {``xibei.load();``var md5Clazz` `=` `Java.use(``"com.example.xibei.SignMd5"``);``console.log(``"md5 sign :"``, md5Clazz.md5(``"123456"``));``})``}` `function main() {``dy_dex()` `}` `setImmediate(main)` `/``/` `结果 ： [Google Pixel` `2` `XL::WiFi ADB]``-``> md5 sign : e10adc3949ba59abbe56e057f20f883e` |
|-|-|

## 二、 frida hook dex

| 12345678910111213141516171819202122232425262728 | `function hook_dy_dex() {``Java.perform(function () {``Java.enumerateClassLoaders({``onMatch: function (loader) {``try` `{``if` `(loader.findClass(``"com.example.xibei.SignMd5"``)) {``console.log(loader)``Java.classFactory.loader` `=` `loader;``}``} catch (error) {` `}` `}, onComplete: function () {` `}``});``var dynamic_dex_clazz` `=` `Java.use(``"com.example.xibei.SignMd5"``);``dynamic_dex_clazz[``"md5"``].implementation` `=` `function (``str``) {``str` `=` `"111111"``console.log(``'md5 is called'` `+` `', '` `+` `'str: '` `+` `str``);``var ret` `=` `this.md5(``str``);``console.log(``'md5 ret value is '` `+` `ret);``return` `ret;``};` `})``}` |
|-|-|

---

# 回复

## 回复 by 秋狝 (#2)

*2023-12-3 22:59*

感谢分享

## 回复 by 万里星河 (#3)

*2023-12-4 17:56*

支持一下

## 回复 by iBa0 (#4)

*2023-12-5 17:09*

学习！
