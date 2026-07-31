---
title: '[原创]对pixel 2进行刷机并使用Magisk获取ROOT权限'
url: https://bbs.kanxue.com/thread-288559.htm
tid: 288559
author: 白衣23
date: '2025-09-20'
tags: [Android安全, 原创, 基础理论, 系统相关]
crawled_at: '2026-07-31T14:03:56+08:00'
replies: 2
---

使用Windows11系统进行操作

刷机的手机型号是`Pixel 2`，在设置->系统->开发者选项，打开开发者选项。然后在这个页面向下滑，打开USB调式。

要想刷机OEM锁必须解开。谷歌海外版的`Pixel 2`的OEM锁是可以在开发者选项中解开的，而`Verizon (V版)`是不能解开的。

并且还必须是欧版的，因为美版的`bootloader`锁是解不开的。

如果没有开发者选项可以在 设置->关于手机中找到版本号连击5次开启开发者模式即可

# 工具安装

## 安装platform-tools

在浏览器打开连接：`https://googledownloads.cn/android/repository/platform-tools-latest-windows.zip`

然后解压：

![image](https://bbs.kanxue.com/upload/attach/202509/973331_HRS5PT9WJ9EGFS5.jpg)

将该目录添加到环境变量中，右击文件夹里的此电脑

![image](https://bbs.kanxue.com/upload/attach/202509/973331_KVEYXT8ZJN7YGJE.jpg)

点击属性->高级系统设置->环境变量，找到系统变量中的`path`

![image](https://bbs.kanxue.com/upload/attach/202509/973331_N93MJJHM5CCFHPS.jpg)

点击编辑->新建，然后将目录路径复制进去

![image](https://bbs.kanxue.com/upload/attach/202509/973331_RG3T8G278WSC5VW.jpg)

然后点击确定->确定->确定

## 安装谷歌USB驱动

使用浏览器访问链接：`https://dl.google.com/android/repository/usb_driver_r13-windows.zip`，下载Google USB驱动

解压这个压缩包

![image](https://bbs.kanxue.com/upload/attach/202509/973331_KBC4CDHAUNKX5U3.jpg)

使用数据线将要刷机的手机和电脑链接起来。

接下来访问`https://zhuanlan.zhihu.com/p/366904302`，这是一个安装谷歌USB驱动的教程。

不过要划到下面这个地方开始看：

![image](https://bbs.kanxue.com/upload/attach/202509/973331_YD782ANDVKEYCYX.jpg)

## 下载系统包

访问：`https://developers.google.com/android/images?hl=zh-cn`，找到对应自己手机型号的系统

![image](https://bbs.kanxue.com/upload/attach/202509/973331_FH38RAABMR7N32T.jpg)

注意要找那些高于或等于手机原来系统版本的系统包。这是因为系统版本越高，bootloader的版本也会越高，，而bootloader是不允许降级的，从而导致无法刷机。

查看手机的系统版本：点击设置->关于手机

然后划到最后面的"版本号"，就是手机系统的版本

![image](https://bbs.kanxue.com/upload/attach/202509/973331_WU386S9D2HF7ENP.jpg)

将下载的压缩包解压：

![image](https://bbs.kanxue.com/upload/attach/202509/973331_UA5KKU4SQ5N4H9R.jpg)

# 刷入系统包

## 让手机进入fastboot模式

使用命令：`adb devices`，查看电脑是否链接了手机

![image](https://bbs.kanxue.com/upload/attach/202509/973331_8VWDAKZY4CDQZSZ.jpg)

链接上手机

使用命令：`adb reboot bootloader`，让手机进入`fastboot`模式，手机会变成下面这个样子，而且这个命令需要执行一段时间，执行完之后，手机就会变成这样。或者长按开机键和减音量键

![image](https://bbs.kanxue.com/upload/attach/202509/973331_TGAWNWZ775EMGX5.jpg)

如果`Device State`的值是locked，说明bootloader锁没有解开，可以使用命令`fastboot oem unclock`或`fastboot flashing unlock`解开bootloader锁。如果无法解开，说明手机是美版的，是无法解开bootloader锁的。

使用命令：`fastbooy devices`，查看与进入`fastboot`模式的手机是否连接正常

![image](https://bbs.kanxue.com/upload/attach/202509/973331_G9YR7W96F6R9NPQ.jpg)

## 刷机

双击`flash-all.bat`文件

会弹出一个cmd命令窗口，需要等待一段时间让这个脚本执行完。

如果最后的结果如下：

![image](https://bbs.kanxue.com/upload/attach/202509/973331_ZWR5DQK32GPMBKA.jpg)

说明执行成功，然后点任意键退出。

再打开一个cmd窗口执行命令：`fastboot reboot`，重启手机

![image](https://bbs.kanxue.com/upload/attach/202509/973331_83WBNH3DPNQVDA5.jpg)

这时可能会出现一个警告界面，如下：

![image](https://bbs.kanxue.com/upload/attach/202509/973331_BUFCXYDAXCGSMUU.jpg)

这是因为手机的bootloader锁被解开了，系统会提醒你。

你会发现手机跟恢复出厂设置了一样，这就说明刷机成功

![image](https://bbs.kanxue.com/upload/attach/202509/973331_YMUQ85GWD7WXW8T.jpg)

# 使用Magisk获取ROOT权限

## 安装Magisk

访问：`https://github.com/topjohnwu/Magisk/releases`，下载Magisk的apk

然后开启手机的开发者模式，并启动USB调试。

使用命令：`adb install <apk所在位置>`，安装Magisk

![image](https://bbs.kanxue.com/upload/attach/202509/973331_BSSJZ6KJNEAUHNM.jpg)

## 修复boot.img

然后进入到上面的那个系统包解压的文件夹里

![image](https://bbs.kanxue.com/upload/attach/202509/973331_X9QXZ97JTSF7K2F.jpg)

将这里的zip文件解压：

![image](https://bbs.kanxue.com/upload/attach/202509/973331_39RYW89HBKRE2ZV.jpg)

然后再该目录下打开cmd窗口，使用命令：`adb push boot.img /sdcard/Download`，将boot.img文件传入到手机的Download目录里

![image](https://bbs.kanxue.com/upload/attach/202509/973331_Y9T49A8CZC2SKQT.jpg)

然后启动安装的Magisk

![image](https://bbs.kanxue.com/upload/attach/202509/973331_JHEWPS6H3GSE7DF.jpg)

点击安装

![image](https://bbs.kanxue.com/upload/attach/202509/973331_R2HPC8HG8XVTYNV.jpg)

点击 选择并修补一个文件：

![image](https://bbs.kanxue.com/upload/attach/202509/973331_FQJWXPREQPYNQ5P.jpg)

然后点击搜索框左边的设置，或者向右划一下屏幕

![image](https://bbs.kanxue.com/upload/attach/202509/973331_PC96NNUGGA9CQKE.jpg)

点击下载：

![image](https://bbs.kanxue.com/upload/attach/202509/973331_HCGSQ6JKT2B4QDM.jpg)

点击boot.img文件

![image](https://bbs.kanxue.com/upload/attach/202509/973331_BBDCWJNH9YPHCD4.jpg)

点击开始

![image](https://bbs.kanxue.com/upload/attach/202509/973331_AHB7Z7AD7AEPJW2.jpg)出现这个界面的时候说明完成了，然后能可以看到它新生成了一个文件是：`/storage/emulated/0/Download/magisk_patched-25201_0juyi.img`，你的文件名和我的可能不一样，反正就是一个新的img文件，这个就是修补后的boot.img文件

## 刷入修补后的boot.img

在电脑端，使用命令`adb pull /storage/emulated/0/Download/magisk_patched-25201_0juyi.img`，将该文件拉入到电脑的任意一个目录下

![image](https://bbs.kanxue.com/upload/attach/202509/973331_QHW8VPSJU8TMYWF.jpg)

然后可以看到在该目录下多了一个magisk_patched-25201_0juyi.img文件

![image](https://bbs.kanxue.com/upload/attach/202509/973331_55GFHFW9473Y63Q.jpg)

然后使用命令：`adb reboot bootloader`，让手机再次进入fastboot模式

![image](https://bbs.kanxue.com/upload/attach/202509/973331_HTWSE84TMWPE6G7.jpg)

然后使用命令：`fastboot flash boot magisk_patched-25201_0juyi.img`

![image](https://bbs.kanxue.com/upload/attach/202509/973331_UUU3YSJWJXY8Z7J.jpg)

然后按一下手机的开机键重启，重启之后再打开Magisk

![image](https://bbs.kanxue.com/upload/attach/202509/973331_NBPHHCRUFRK4VYR.jpg)

可以看到超级用户和模块这两个按钮从之前的灰色变成了黑色，与日志一样。并且"当前"的值也不再是无法获取而一个编号，这说明成功获取了root权限。但是你使用adb shell还是无法获取root权限

## Shell获取ROOT权限

打开Magisk，点击超级用户，

![image](https://bbs.kanxue.com/upload/attach/202509/973331_PMU7UVEFVJCB2AY.jpg)

将Shell的按钮打开。

然后点击主页，

![image](https://bbs.kanxue.com/upload/attach/202509/973331_U4QXUPYQAF6HXVM.jpg)

点击右上角的设置，并划到下面的超级用户

![image](https://bbs.kanxue.com/upload/attach/202509/973331_XUEWCEFPX2DAF76.jpg)

点击"超级用户访问权限"

![image](https://bbs.kanxue.com/upload/attach/202509/973331_567TS8X3CFXZNKB.jpg)

点击"应用和ADB"，然后重启手机

重启之后在电脑端的cmd窗口，执行命令：`adb shell`

然后执行：`su`

![image](https://bbs.kanxue.com/upload/attach/202509/973331_SKSBFBYCB2J43UN.jpg)

可以看到成功获取root权限。

# 解决网络连接受限问题

pixel系列的手机在国内使用都会显示网络连接受限，这是因为它无法连接到谷歌服务器，要解决这个问题要么翻墙，要么将它连接的谷歌服务器地址改为国内的服务器地址。

将谷歌服务器地址改为国内的服务器地址的方法是：

```python
adb shell settings put global captive_portal_http_url http://connect.rom.miui.com/generate_204
adb shell settings put global captive_portal_https_url https://connect.rom.miui.com/generate_204
```

执行这两个命令，然后重启手机即可。

---

# 回复

## 回复 by mb_yqsvfqmf (#2)

*2025-10-5 09:29*

可以私聊吗

## 回复 by 白衣23 (#3)

*2025-10-5 10:16*

>
> [mb_yqsvfqmf](https://bbs.kanxue.com/user-1043871.htm)
>
>  可以私聊吗
>
>

可以
