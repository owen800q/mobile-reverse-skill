---
title: '[原创]smali修改+log动态插桩在Android题目的应用'
url: https://bbs.kanxue.com/thread-279336.htm
tid: 279336
author: iBa0
date: '2023-10-24'
tags: [Android安全, 原创, 基础理论, 逆向分析]
crawled_at: '2026-07-31T14:37:15+08:00'
replies: 2
---

本次题目来自NSSCTF-2nd，题目附件会打包上传
比赛的时候采用了frida-hook的方法来解题，近期在复现总结基础

想到了可以用smali修改来做，顺带记录了一下（两种方法）

## 1、samli修改跳转+赋值

app自己开了debug
 ![图片描述](https://bbs.kanxue.com/upload/attach/202310/971547_6PADBWWH88F936Q.webp)
使用aapt获得启动包名
 ![图片描述](https://bbs.kanxue.com/upload/attach/202310/971547_YW7BDN2WQ7ADQV3.webp)
smali修改，调用目标函数直接传参数
 ![图片描述](https://bbs.kanxue.com/upload/attach/202310/971547_9XSUF78Q5Y43CYX.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202310/971547_Y92X4MV786UR57R.webp)
我的Android killer有点小问题，只能结合jdax来进行定位分析
 ![图片描述](https://bbs.kanxue.com/upload/attach/202310/971547_N6MDJZ37RP7G9KS.webp)
Android killer上手修改
 ![图片描述](https://bbs.kanxue.com/upload/attach/202310/971547_XJYGAA6EDEHED6W.webp)

| 12 | `if``-``ne  v1,v2  ;v1!``=``v2则跳转``if``-``eq  v1,v2  ;v1``=``=``v2则跳转` |
|-|-|

改为相反条件即可
 ![图片描述](https://bbs.kanxue.com/upload/attach/202310/971547_SCAYBS839T8UFK8.webp)
将v5赋值为对应的值
 ![图片描述](https://bbs.kanxue.com/upload/attach/202310/971547_5GB98N39JJZNEYN.webp)
Android killer 保存编译
 ![图片描述](https://bbs.kanxue.com/upload/attach/202310/971547_5BRZGUZZV9GFDXQ.webp)
flag：
NSSCTF{1a74ee530fafa690dcddd0ce38260755}

## 2、smali动态插桩

前面的准备工作都是一样的

（动态插桩的做法在这道题，显得比较鸡肋，但是顺带练习一下哈哈哈）

在某些题目，动态插桩的做法会输出很多重要的值，帮助我们来进行分析
前面的修改不要动
 ![图片描述](https://bbs.kanxue.com/upload/attach/202310/971547_AFPSS6YTMW5FY3A.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202310/971547_NH3V638HCFZRBPE.webp)
动态插桩的模板：
（注意：v0在原samli中可能会被用到，此时v0要替换为任意一个非重要寄存器，本题的v0在后面用到了，因此我替换为v4）

| 1234567 | `move``-``result``-``object` `v6` `#v6是某个重要的值，需要我们来输出的值` `const``-``string v0,``"自定义:"`  `#v0自定义标签值，方便我们观察` `invoke``-``static {v0,v6}, Landroid``/``util``/``Log;``-``>d(Ljava``/``lang``/``String;Ljava``/``lang``/``String;)I` `#传入对应的值（string类型）` `move``-``result v0` `#调用即可` |
|-|-|

不报错的动态插桩smali代码

| 12345 | `const``-``string v4,` `"myobject_soso:"`  `invoke``-``static {v4,v3}, Landroid``/``util``/``Log;``-``>d(Ljava``/``lang``/``String;Ljava``/``lang``/``String;)I`  `move``-``result v4` |
|-|-|

然后在logcat里面查看输出

| 1 | `adb logcat \| find` `"myobject_soso:"` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202310/971547_CEHJYF3CG4RK5AM.webp)

分享结束~！

上传的附件：
- MyAPK.apk

（3.39MB，28次下载）

---

# 回复

## 回复 by 秋狝 (#2)

*2023-10-26 16:41*

感谢分享

## 回复 by gamehack (#3)

*2023-10-26 18:43*

感谢分享
