---
title: '[原创]React Native Hermes逆向'
url: https://bbs.kanxue.com/thread-283616.htm
tid: 283616
author: 一颗小草
date: '2024-09-24'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:20:13+08:00'
replies: 14
---

最近没什么事，找了个看视频App，发现又是广告又是视频植入的，烦不胜烦，想着花点时间去个广告捣鼓捣鼓。本文只为了技术分享讨论，切勿使用技术进行非法用途。
apk拿过来先拖动到jadx查看
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/973070_JCZW28CJGR2RAWD.webp)
loadAd大概率就是加载广告的地方，点到这个类中往下滑，发现有show方法，通过修改改对应dex的smail将show改为空，改好后将smail文件夹重新编译为dex，在放到jadx中验证是否错误。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/973070_XW83KT6D67GQHS6.webp)
上面这个是splash，然后依次将插屏，banner都像这样修改掉。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/973070_CKJS2DQNSG6ETDR.webp)
这都是基础的修改smail，不在本文中详细描述。
React native的代码打包都都放在assets下的index.android.bundle中，正常情况会将代码压缩，混淆，但是我这个apk中的index.android.bundle打开并未显示js代码，拖到notepad++中发现
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/973070_6EQP4EASCFACVDE.webp)
乱码显示，摸索了一下java代码发现
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/973070_9DPRAQ4JTNTGB86.webp)
这里比较可疑，应该是乱码的源头，然后搜索关键字Hermes，发现这是一个对于React native的JavaScript引擎，将js代码都编译为bytecode，Hermes引擎会优化React native应用的启动速度和文件大小。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/973070_UNR9EUCR3ZVKPEP.webp)
本来想使用frida大法，将assets读取文件内容，执行Js引擎时将内容直接打印出来，无奈，找了半天源码没发现好的切入点，发现一个开源的反编译工具，hbctool，官方也有hbcdump提供反编译工具，使用hbcdump执行反编译提示

| 1 | `Error: fail to deserializing bytecode: Wrong bytecode version. Expected` `96` `but got` `90` |
|-|-|

看上去是我的index.android.bundle样本的hbc版本是90，我下载的最新版本hbcdump为96，找到hbcdump 90的工具后执行

| 12 | `hbcdump.exe index.android.bundle` `-``mode``=``hbc` `-``out``=``myout.js``disassemble` |
|-|-|

在当前目录将会看到
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/973070_GNFHYSURKN5KSUF.webp)
反编译的结果，但是但是，还没这么快结束。由于我的目的是需要去广告，解锁会员功能，所以修改js代码后还需要回编译，但是官方的这个工具找了半天也没发现有什么文档说明怎么编译回去。无奈切换为另外一个作者的hbctool工具
 **<https://github.com/bongtrop/hbctool>**
这个工具在pull request中有90和94的反编译源码提供，感谢每一个开源的作者。在文章末尾我也会将我使用到的代码上传提供下载使用。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/973070_PX79P2WCJDGAYW8.webp)
将源码下载，在pycharm中打开，添加hbc90目录，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/973070_8K2DG45YWPP2RET.webp)
在__init__.py中添加90版本的处理，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/973070_AJ6VR3TZ38HR5QP.webp)
执行disasm将会反编译文件，执行asm将会把反编译修改的的文件夹编译回index.android.bundle
反编译后的文件夹内容
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/973070_9FXFJFJ9S9CB6GE.webp)
instruction.hasm便是源码，string.json是字符表，metadata.json看上去是文件的描述符和完整性验证使用的文件，没有仔细研究这个文件。
按照我的目的我应该去修改instruction.hasm，打开instruction.hasm查看。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/973070_REAFZHWFCV6KQWN.webp)
不认识这种代码，后来搜索到相关文章有描述操作符之类的说明，现在已经忘记了。
仔细看代码，和汇编有些相似，但是看上去比汇编简单很多，都是左边一个指令右边操作数，例如

| 12345678910 | `LoadConstTrue           Reg8:``22` `将一个``8``位的寄存器``22``设置为true``Mov                     Reg8:``22``, Reg8:``25`  `将``25``寄存器的值赋值給寄存器``22``LoadConstString         Reg8:``39``, UInt16:``16781`  `加载一个字符到``39``寄存器，字符``id``为``16781``，查看string.json可以找到这个字符的值。``{``"id"``:` `16781``,``"isUTF16"``: false,``"value"``:` `"contain"``}``LoadConstTrue           Reg8:``4` `将寄存器``4``设为true``LoadConstFalse          Reg8:``4` `将寄存器``4``设为false` |
|-|-|

接下来只要找到Vip字样相关的地方，修改为true,将反编译后的文件夹重新编译为index.android.bundle，替换assets下面的index.android.bundle，使用apktool重新打包就完成了。

上传的附件：
- hbc90.zip

（25.37kb，122次下载）

---

# 回复

## 回复 by bluegatar (#2)

*2024-9-26 00:09*

js现在都native化了啊，真的烦

## 回复 by 养只猫不好么 (#3)

*2024-9-26 13:18*

感谢分享

## 回复 by 一颗小草 (#4)

*2024-9-27 13:35*

>
> [bluegatar](https://bbs.kanxue.com/user-352825.htm)
>
>  js现在都native化了啊，真的烦
>
>

还好，就是不知道这个格式的时候看着有点蒙，看过了之后就简单了

## 回复 by 溅厷 (#5)

*2024-9-27 16:51*

支持一下 ，这个程序应该还算小，之前逆到了一个生成的strings都几十兆的应用，给我人看麻了![image](https://bbs.kanxue.com/view/img/face/78.gif)

## 回复 by 暴走的莎莉酱 (#6)

*2024-11-16 01:29*

佬 90的工具有链接吗

## 回复 by 一颗小草 (#7)

*2024-11-26 17:20*

>
> [暴走的莎莉酱](https://bbs.kanxue.com/user-893831.htm)
>
>  佬 90的工具有链接吗
>
>

看我文章中有写github地址，在项目中的pull request有90和94

## 回复 by mb_rqtugypo (#8)

*2025-1-22 18:39*

你好 请教一下 为什么我的hbcdump.exe 不能反编译为js  我复制了你文中的指令 执行提示只能输入一个参数 应该如何操作才能变成js

## 回复 by hhhaiai (#9)

*2025-1-24 13:06*

666666

## 回复 by mb_vqggfrzt (#10)

*2025-3-1 16:15*

老哥hbcdump.exe 90版本可以提供一下嘛

## 回复 by misskings (#11)

*2025-3-11 17:07*

羡慕不用改metadata。那个校验麻烦的很

## 回复 by iBa0 (#12)

*2025-3-12 10:19*

牛逼

## 回复 by 哇哈哈919 (#13)

*2025-4-30 11:15*

大哥，hbcdump.exe 90 这个90的版本在哪里找到的呀，求分享，官网最新的是96 次新的是 89版本

## 回复 by K4NG (#14)

*2025-6-9 18:28*

突然从人群中钻出来一个 hbcdump.exe

## 回复 by 掀起你的头盖骨 (#15)

*2025-12-10 16:23*

index.android.bundle没看到这个文件啊，倒是看到了common.bundle之类的文件
