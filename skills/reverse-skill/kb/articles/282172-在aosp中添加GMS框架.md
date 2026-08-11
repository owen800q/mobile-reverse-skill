---
title: '[原创]在aosp中添加GMS框架'
url: https://bbs.kanxue.com/thread-282172.htm
tid: 282172
author: 琳宇
date: '2024-06-15'
tags: [Android安全, 原创, 基础理论, 系统相关]
crawled_at: '2026-08-11T08:45:09+00:00'
replies: 17
---

看到不少朋友考虑在aosp中添加GMS而没找到办法，故而发帖

本次测试是在android12.0.0_r3测试
1.下载GMS相关包，放到目录/vendor下
2.然后找到我们需要编译的配置文件，我这里编译的是piexl4，所以文件是aosp_flame.mk。flame就是piexl4的代号，大家自己根据要编译的型号自己寻找对应的mk文件。
在该文件的最下方添加
$(call inherit-product, vendor/partner_gms/gms.mk)
3.在build/envsetup.sh文件的最上方添加
export DISABLE_ARTIFACT_PATH_REQUIREMENTS="true"
4.在privapp-permissions-platform.xml文件中添加服务的权限，添加到最下面就可以了
 <privapp-permissions package="com.google.android.gms">
 <permission name="android.permission.ACCESS_VIBRATOR_STATE"/>
 <permission name="android.permission.WRITE_EMBEDDED_SUBSCRIPTIONS"/>
 <permission name="android.permission.MODIFY_DEFAULT_AUDIO_EFFECTS"/>
 <permission name="android.permission.MEDIA_CONTENT_CONTROL"/>
 </privapp-permissions>
然后正常编译即可。

partner_gms目录分享在
<https://www.alipan.com/t/0pG6TgHXqWPT2g3f4JHK>

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2024-6-15 18:31*

楼主，阿里的链接失效了呦

## 回复 by 琳宇 (#3)

*2024-6-16 20:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>  楼主，阿里的链接失效了呦
>
>

https://www.alipan.com/t/5CGnx5vPFmh2ghjQRao6

## 回复 by 琳宇 (#4)

*2024-6-16 20:25*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>  楼主，阿里的链接失效了呦
>
>

因为这个网盘不让分享tar文件所以没法整一个永久的链接

## 回复 by 你瞒我瞒 (#5)

*2024-6-17 14:15*

楼主，换一个网盘分享吧，链接又没了。![image](https://bbs.kanxue.com/view/img/face/38.gif)

## 回复 by Gungnir_V (#6)

*2024-6-17 18:28*

感谢楼主 困扰很久了 能否再分享一下链接呢

## 回复 by 琳宇 (#7)

*2024-6-19 14:41*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_三叶](https://bbs.kanxue.com/user-925028.htm)
>
>  感谢楼主 困扰很久了 能否再分享一下链接呢
>
>
>

https://www.alipan.com/t/rJKHaPjxPrnSW1SmEmER

## 回复 by Gungnir_V (#8)

*2024-6-19 17:52*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  琳宇](https://bbs.kanxue.com/user-853393.htm)
>
>  https://www.alipan.com/t/rJKHaPjxPrnSW1SmEmER
>
>

感谢

## 回复 by clz3216 (#9)

*2024-6-19 18:28*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  琳宇](https://bbs.kanxue.com/user-853393.htm)
>
>  https://www.alipan.com/t/rJKHaPjxPrnSW1SmEmER
>
>

失效了

## 回复 by 琳宇 (#10)

*2024-6-22 10:09*

>
> [clz3216](https://bbs.kanxue.com/user-963838.htm)
>
>  失效了
>
>
>

https://www.alipan.com/t/OzAFpPAwnvdEUvwiopGP

## 回复 by gtict (#11)

*2024-6-24 11:07*

可以传个个稳定的链接么。~~

## 回复 by huaerxiela (#12)

*2024-7-15 16:44*

可以传个个稳定的链接么。~~

## 回复 by Gungnir_V (#13)

*2024-8-1 17:07*

楼主能否定位呢？按方法编译后都无法使用定位服务感觉gms服务有缺失，uber也无法使用提示不支持Google Play服务，应该不是官方的GMS

## 回复 by 琳宇 (#14)

*2024-8-5 00:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_三叶](https://bbs.kanxue.com/user-925028.htm)
>
>  楼主能否定位呢？按方法编译后都无法使用定位服务感觉gms服务有缺失，uber也无法使用提示不支持Google Play服务，应该不是官方的GMS
>
>
>

这个里面GMS服务是不够的，但我们可以自己添加啊，里面的服务可以根据自己的需求，随意添加的。我们只需要提取一个正常的GMS的apk即可。

## 回复 by Gungnir_V (#15)

*2024-8-6 11:22*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  琳宇](https://bbs.kanxue.com/user-853393.htm)
>
>  这个里面GMS服务是不够的，但我们可以自己添加啊，里面的服务可以根据自己的需求，随意添加的。我们只需要提取一个正常的GMS的apk即可。
>
>

感谢回复，但是还有点不懂，添加是指在系统里面配置这个GMS APK未启动的服务还是值需要手动去实现相关服务再打入系统的包里面呢。

## 回复 by 你瞒我瞒 (#16)

*2024-10-7 19:39*

可以整一个百度的网盘链接，或者把mk的内容发出来也行。因为apk可以自己去下载。

## 回复 by hacker521 (#17)

*2025-2-25 15:45*

又失效了，能否更新下？

## 回复 by 小七烤地瓜 (#18)

*2025-5-13 16:05*

佬  有没有aosp 14的gms包
