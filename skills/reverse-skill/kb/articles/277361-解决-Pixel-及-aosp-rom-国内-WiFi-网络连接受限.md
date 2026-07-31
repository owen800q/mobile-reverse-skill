---
title: '[原创]解决 Pixel 及 aosp rom 国内 WiFi 网络连接受限'
url: https://bbs.kanxue.com/thread-277361.htm
tid: 277361
author: 行简
date: '2023-05-25'
tags: [Android安全, 原创, 系统相关, 工具脚本]
crawled_at: '2026-07-31T14:48:01+08:00'
replies: 8
---

# 前言

在用Pixel、及刷的像素rom，的时候老是提示网络连接受限，虽说能用，但是就恶心！

# 原因

自 Android 5.0 起，谷歌引入了「Captive Portal」的机制，用于检测 WiFi网络认证是否正常。

 该机制默认检测访问的是谷歌服务器，需要科学才能正常访问谷歌服务器，如若没有 WiFi就会出现网络受限的情况，WiFi图标上会出现一个感叹号标志，导致系统误以为你的网络不好，从而使网络不稳定。

 解决方法总是有的：

>
> 一、科学，dddd；
> 二、谷歌提供了参数变量设置，国内安卓手机系统都可以将其修改成自家的服务器地址或者高通中国的地址。
>
>
>

# 参数设置

## 方法一：已ROOT手机

已经 ROOT 的安卓机很简单，可以用面具模块、Scene、Captivemgr等工具来修改，这里推荐使用 Captivemgr 因为可以自定义服务器地址。

 默认提供了三个服务器，分别是小米、高通、V2EX，根据延迟选择就行了，然后应用。手机切换飞行模式，再切换回来就OK了。

## 方法二：没有ROOT情况 (adb命令要自行安装与配置)

没有 ROOT 的安卓机可以借助 ADB 命令来修改，首先下载ADB工具包，然后手机开启USB调试模式，接着运行 CMD 输入下面的命令就可以了。

### 步骤一：删除默认的地址

| 12 | `adb shell settings delete` `global` `captive_portal_https_url``adb shell settings delete` `global` `captive_portal_http_url` |
|-|-|

### 步骤二：修改新的地址

| 123 | `adb shell settings put` `global` `captive_portal_http_url http:``/``/``connect.rom.miui.com``/``generate_204` `adb shell settings put` `global` `captive_portal_https_url https:``/``/``connect.rom.miui.com``/``generate_204` |
|-|-|

改完同样把手机切换飞行模式，再切换回来就可以了。如果需要其它服务器地址，自行修改，如高通的地址是https://captive.v2ex.co/generate_204

---

# 回复

## 回复 by 万里星河 (#2)

*2023-5-25 19:40*

支持一下

## 回复 by 秋狝 (#3)

*2023-5-26 09:18*

感谢分享

## 回复 by mb_ckfmrnqa (#4)

*2023-5-26 09:28*

亲测有用

## 回复 by Lunction (#5)

*2023-5-28 11:14*

adb shell settings put global captive_portal_mode 0 关闭检测

## 回复 by R0g (#6)

*2023-5-28 22:39*

>
> [Lunction](https://bbs.kanxue.com/user-681174.htm)
>
>  adb shell settings put global captive_portal_mode 0 关闭检测
>
>

这个好

## 回复 by zhadan9527 (#7)

*2024-1-31 16:05*

感谢分享

## 回复 by MYIYOUHACK (#8)

*2025-11-27 23:46*

为什么我一进入adb后,z只要执行命令就后会重启系统，这是正常的情况吗？

## 回复 by wx_WantC (#9)

*2025-11-28 09:42*

感谢分享
