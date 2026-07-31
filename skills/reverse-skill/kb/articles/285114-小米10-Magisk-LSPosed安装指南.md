---
title: '[原创]小米10 Magisk + LSPosed安装指南'
url: https://bbs.kanxue.com/thread-285114.htm
tid: 285114
author: uuhc
date: '2025-01-04'
tags: [Android安全, 原创, 基础理论, 逆向分析, 系统相关, 工具脚本]
crawled_at: '2026-07-31T16:02:23+08:00'
replies: 61
---

| 123 | `# 重要提示``1.` `尽量不使用主力机刷机，或提前备份重要资料``2.` `本文档使用设备为xiaomi` `10``，其他机型可能不通用` |
|-|-|

# 1. 设备及资源准备

- 小米10手机（miui 12.0.11）已解bootloader锁
	- 解锁步骤见下文
	- 解锁工具：<https://www.miui.com/unlock/index_en.html>
- 小米刷机工具
	- <https://cdn.alsgp0.fds.api.mi-img.com/micomm/MiFlash2020-3-14-0.rar>
- 系统对应安装包
	- <https://hugeota.d.miui.com/V12.0.11.0.QJBCNXM/miui_UMI_V12.0.11.0.QJBCNXM_03afa44d87_10.0.zip>
- adb环境
	- <https://developer.android.com/studio/releases/platform-tools?hl=zh-cn>
- Magisk
	- <https://github.com/topjohnwu/Magisk/releases/download/v27.0/Magisk-v27.0.apk>
- LSPosed（zygisk）
	- <https://github.com/LSPosed/LSPosed/releases/download/v1.9.2/LSPosed-v1.9.2-7024-zygisk-release.zip>
- JustTrustMe
	- <https://github.com/Fuzion24/JustTrustMe/releases/download/v.2/JustTrustMe.apk>

# 2. 资源下载

下载以上所有所需文件

# 3. 操作步骤

## 3.1 解BootLoader锁

### 3.1.1 打开开发者模式

设置->我的设备->全部参数->MIUI版本，连续多次点击MIUI版本，即可进入开发者模式
然后可看到 设置->更多设置->开发者选项
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/940902_B4W7RZV7X59QZXW.webp)

### 3.1.2 绑定账号和设备

首次绑定手机，需要在绑定帐号后等待 7 天，期间不要退出小米帐号
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/940902_64FFYH5JSZ238AW.webp)
3.1.3 官方工具解锁
下载解锁工具：[https://www.miui.com/unlock/index_en.html，解压后运行里面的](https://www.miui.com/unlock/index_en.html%EF%BC%8C%E8%A7%A3%E5%8E%8B%E5%90%8E%E8%BF%90%E8%A1%8C%E9%87%8C%E9%9D%A2%E7%9A%84) miflash_unlock.exe，按照提示登录已绑定设备的小米帐号。
进入fastboot模式，下面步骤二选一：

- 手机关机，按住音量下键 + 开机键进入 Fastboot 模式
- 执行adb reboot bootloader进入 Fastboot 模式
识别手机后，点击解锁按钮
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/940902_NJEQECAGVJM2EPJ.webp)
重启手机，解锁完成

## 3.2 手机刷入rom

>
> fastboot模式
>  ![图片描述](https://bbs.kanxue.com/upload/attach/202501/940902_BE9KPWEUQYVGV5E.webp)
>
>
>

## 3.3 获取boot.img

解压 miui_UMI_V12.0.11.0.QJBCNXM_03afa44d87_10.0.zip， 可直接获取
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/940902_RQAK43RPAT966HY.webp)
其他机型或系统可能多一个提取步骤

## 3.4 修复boot.img

使用magisk修复boot.img

| 1234 | `# 使用命令或文件管理器将boot.img推入手机``adb push boot.img` `/``sdcard``/``Download``# 使用magisk 安装-选择并修补一个文件，选择boot.img``# 安装完成后，目录下生成一个文件，如下图：magisk_patched-27700_**.img` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/940902_5CEJC75ETV2D2DU.webp)

## 3.5 刷入修复文件

 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/940902_HPQ8JYEFVEFVREK.webp)

| 1234567891011 | `# 将修复的文件pull到电脑``adb pull` `/``sdcard``/``magisk_patched``-``27700_``*``*``.img .``/``# 使用命令或长按电源键+音量下键进入fastboot模式``adb reboot bootloader``# 使用命令查看设备链接状态``fastboot devices` `# 刷入修补后的镜像``fastboot flash boot magisk_patched``-``27700_``*``*``.img``# 完成后重启``fastboot reboot` |
|-|-|

日志示例如下：

| 12345678 | `# fastboot flash boot magisk_patched-27000_F7Tcr.img``Sending` `'boot_b'` `(``196608` `KB)                       OKAY [` `5.297s``]``Writing` `'boot_b'`                                   `OKAY [` `0.690s``]``Finished. Total time:` `5.998s` `# fastboot reboot``Rebooting                                          OKAY [` `0.000s``]``Finished. Total time:` `0.001s` |
|-|-|

## 3.6 配置Zygisk

 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/940902_QPXB2EHGXK2KEC9.webp)

## 3.7 LSPosed

| 123 | `# 将下载的LSPosed-v1.9.2-7024-zygisk-release.zip push到手机``adb push LSPosed``-``v1.``9.2``-``7024``-``zygisk``-``release.``zip` `/``sdcard``/``Download``# 使用magisk 模块-从本地安装-选择LSPosed-v1.9.2-7024-zygisk-release.zip，如下图` |
|-|-|

LSPosed-v1.9.2-7024-zygisk-release.zip
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/940902_9VAY3VHS2KA8JG9.webp)
安装完成后重启，屏幕下拉，可看到LSPosed已加载，打开管理器，如下
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/940902_GB8JEY554ABYNN5.webp)

## 3.8 JustTrustMe

下载JustTrustMe.apk后安装即可
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/940902_2ZDNEMVETZJ675H.webp)

## 3.9 命令汇总

| 12345678910111213 | `# 如果手机区分A/B分区，后续刷机命令有区别``# 查询手机是否使用A/B分区，结果为true，即为A/B分区``adb shell getprop ro.build.ab_update` `# 使用命令或长按电源键+音量下键进入fastboot模式``adb reboot bootloader``# 使用命令查看设备链接状态``fastboot devices` `# 刷入修补后的镜像``fastboot flash boot magisk_patched-27700_**.img``# 完成后重启``fastboot reboot` |
|-|-|

# 参考文档

platform-tools：<https://developer.android.com/studio/releases/platform-tools?hl=zh-cn>
小米镜像下载地址：<https://github.com/mooseIre/update_miui_ota/blob/master/Stable/%E5%B0%8F%E7%B1%B310.md>
Magisk：<https://github.com/topjohnwu/Magisk>
LSPosed：<https://github.com/LSPosed/LSPosed>
JustTrustMe：<https://github.com/Fuzion24/JustTrustMe>

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2025-1-5 09:14*

感谢分享

## 回复 by 七星舞月 (#3)

*2025-1-5 10:47*

感谢分享

## 回复 by SpiderMan丶K (#4)

*2025-1-5 10:57*

感谢分享

## 回复 by kingking888 (#5)

*2025-1-5 12:38*

666

## 回复 by 院士 (#6)

*2025-1-5 13:11*

root也可以直接刷面具，不用修补了再刷修补文件这么麻烦。

## 回复 by RobinLi (#7)

*2025-1-6 10:36*

学习一下

## 回复 by abxy (#8)

*2025-1-6 19:41*

感谢分享

## 回复 by Imxz (#9)

*2025-1-6 23:32*

6666

## 回复 by mb_ygxdlbdi (#10)

*2025-1-7 09:42*

666

## 回复 by xianhuimin (#11)

*2025-1-7 13:40*

看看，然后试试

## 回复 by JWPL (#12)

*2025-1-7 14:11*

看看 ![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 我想你了 (#13)

*2025-1-7 18:12*

学习一下

## 回复 by ONewTach (#14)

*2025-1-8 08:53*

看一看

## 回复 by slbwgslz (#15)

*2025-1-8 20:09*

11111

## 回复 by mb_elqwyvnm (#16)

*2025-1-9 00:03*

很实用的教程

## 回复 by fangliangz (#17)

*2025-1-9 10:27*

看看，学习学习。。。

## 回复 by flyingx (#18)

*2025-1-11 01:30*

感谢分享

## 回复 by 寻梦之璐 (#19)

*2025-1-13 11:29*

6

## 回复 by uuhc (#20)

*2025-1-21 16:39*

>
> [院士](https://bbs.kanxue.com/user-682431.htm)
>
>  root也可以直接刷面具，不用修补了再刷修补文件这么麻烦。
>
>

回头我试下，![image](https://bbs.kanxue.com/view/img/face/087.gif)

## 回复 by 9527vv7 (#21)

*2025-1-21 19:38*

11

## 回复 by kuang110 (#22)

*2025-2-5 14:53*

学习

## 回复 by mb_spwfptaa (#23)

*2025-2-7 14:34*

666

## 回复 by mb_ngeoumzw (#24)

*2025-3-2 21:34*

666666

## 回复 by 马来 (#25)

*2025-3-3 20:44*

666666

## 回复 by wolf_lc (#26)

*2025-3-4 13:49*

kk

## 回复 by wx_罡 (#27)

*2025-3-4 20:45*

666666

## 回复 by LQ6H (#28)

*2025-3-5 22:24*

666

## 回复 by mb_pmgifpme (#29)

*2025-3-7 13:49*

6666

## 回复 by anenn (#30)

*2025-3-7 14:32*

6666

## 回复 by mb_jrrvhcpc (#31)

*2025-3-8 17:31*

666

## 回复 by darbra (#32)

*2025-3-10 14:02*

666666

## 回复 by mb_cfjwplfo (#33)

*2025-3-11 12:30*

666

## 回复 by 天山飞雪 (#34)

*2025-3-11 14:16*

谢谢 兄弟

## 回复 by Tiam (#35)

*2025-3-12 09:06*

666

## 回复 by jimxy (#36)

*2025-3-12 09:41*

感谢分享，学习一下

## 回复 by pianpu (#37)

*2025-3-12 14:09*

支持

## 回复 by eeeeelukou (#38)

*2025-3-14 16:33*

666666

## 回复 by mb_anbthlub (#39)

*2025-3-14 17:38*

1

## 回复 by Nickname知寒 (#40)

*2025-3-15 15:36*

感谢分享

## 回复 by mb_mukimslh (#41)

*2025-3-17 22:33*

66666666

## 回复 by myller (#42)

*2025-3-18 00:01*

73157

## 回复 by 藍色風火 (#43)

*2025-3-18 09:26*

666

## 回复 by Ram98 (#44)

*2025-3-18 09:49*

6666

## 回复 by 路易 (#45)

*2025-3-18 09:58*

111

## 回复 by wx_小小MAN (#46)

*2025-3-19 17:12*

感谢分享

## 回复 by yyyyy——— (#47)

*2025-5-18 13:19*

6666

## 回复 by 逆向雪花 (#48)

*2025-5-22 21:41*

1

## 回复 by hoyoo (#49)

*2025-10-11 09:25*

666

## 回复 by 无视红绿灯 (#50)

*2025-11-11 10:38*

6666

## 回复 by Heiyiren123 (#51)

*2025-12-8 20:40*

学习了，谢谢分享！

## 回复 by emmmme (#52)

*2026-2-15 19:08*

收藏备用

## 回复 by 我是小奥 (#53)

*2026-2-23 21:25*

感谢分享

## 回复 by mb_urefzhfu (#54)

*2026-3-4 14:51*

666

## 回复 by desedese (#55)

*2026-3-9 12:41*

感谢分享

## 回复 by iBa0 (#56)

*2026-4-1 21:38*

123

## 回复 by 五彩斑斓的黑 (#57)

*2026-4-1 23:24*

666

## 回复 by mb_ccvvhvhb (#58)

*2026-4-27 21:18*

666

## 回复 by xyzjhe (#59)

*2026-5-4 10:36*

回头我试下

## 回复 by mb_irrqcmsq (#60)

*2026-5-28 10:56*

谢谢，太厉害了

## 回复 by 天路 (#61)

*2026-5-30 11:21*

111

## 回复 by mb_degalzhb (#62)

*2026-7-20 10:17*

666
