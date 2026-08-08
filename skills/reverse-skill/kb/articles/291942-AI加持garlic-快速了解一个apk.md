---
title: '[原创] AI加持garlic - 快速了解一个apk'
url: https://bbs.kanxue.com/thread-291942.htm
tid: 291942
author: neocanable
date: '2026-07-09'
tags: [Android安全, 原创, 逆向分析, 基础理论, 工具脚本, 源码框架, 程序开发]
crawled_at: '2026-08-08T10:03:35+00:00'
replies: 68
---

[garlic decompiler](https://github.com/neocanable/garlic) mcp-server可以跑起来了。

##  1. 效果

拿京东商城一个旧版本举例：

![image](https://bbs.kanxue.com/upload/attach/202607/586240_JM2C9AWGYAQPHYW.webp)![image](https://bbs.kanxue.com/upload/attach/202607/FURXPCUEGQ86B57.jpg)![image](https://bbs.kanxue.com/upload/attach/202607/586240_RBZG2S5ZCGK3326.webp)

流程： 反编译 + call graph + 综合分析(AI自己做的)

## 2. 原理

garlic mcp server和garlic decompiler都在一个二进制内, garlic mcp-server没有http形式的，完全是stdio的形式，我试验了几个http形式的mcp-server，太慢了，感觉难以接受

| 12 | `反编译： garlic xxx.apk -t 4 -o output``mcp-server: garlic -m` |
|-|-|

在AI分析一个apk的时候是什么流程呢？

1. 反编译apk
2. 反编译AndroidManifest.xm
3. 生成apk的call graph
4. 生成apk的strings和strings的xref
5. 导入call graph/strings到duckdb

如果需要可视化，也可以让AI或者自己生成这样的call graph：

![image](https://bbs.kanxue.com/upload/attach/202607/586240_TVRTGCWUZ4WNEV6.webp)

## 3. 优点/缺点

速度快 - garlic是c写的，速度上能得到保证

占用资源少 - 在分析完一个apk后，内存就释放掉，定位文件/方法都可以直接查db

追踪程序执行快 - duckdb支持递归形式的查询，不用追踪每一条路径都去grep file

没有windows的机器，windows版本的没有仔细测试。

## 4. mcp server配置方法

| 123456 | `{``"command"``:``"garlic"``,``// 这里直接写garlic的路径就ok了``"args"``: [``"-m"``]``}` |
|-|-|

## 5. native分析

native的分析是我正在做的另外一个东西，现在只支持arm64，现在能支持到的功能：

1. 反汇编
2. 控制流分析
3. 控制流还原
4. 数据流分析
5. IR
6. jumptable还原
7. vtable还原
8. 部分blr分析
9. xref 分析

native部分的分析也是c语言实现的，完全可以衔接到garlic上，没有任何三方库，比如capstone这些。

大部分功能还在调试，现在能实现的基础效果是将java的code和native的流程关联起来，我相信有AI的加持下，可以更容易的从java一直跟到native的代码，分析**微信**效果如下：

| 1234567891011121314151617181920212223242526272829303132333435363738394041 | `Waiting``for` `analysis to start...``[13:55:33] Started analysis``for` `weixin.apk``[13:55:33] Running aapt2 dump badging...``[13:55:34] Extracting APK metadata (package, version, permissions)...``[13:55:34] Parsing AndroidManifest.xml``for` `components...``[13:55:39] Extracting APK contents...``[13:55:43] APK extraction complete [10.2s]. Queueing decompilation...``[13:55:43] Starting Java decompilation with garlic...``[13:55:59] Generating Java call graph...``[13:56:08] Building Java call graph index...``[13:56:23] Call graph built: 770928 methods, 8998 native, 381196 strings``[13:56:23] Decompilation completed successfully [39.6s]``[13:56:26] Extracting native``function` `index...``[13:56:40] Queueing native SO analysis...``[13:56:40] Decompilation phase complete``[13:56:40] Found 182 native SO files to analyze``[13:56:40] [1``/182``] Analyzing libAdvanceP2P.so...``[13:56:40] [1``/182``] libAdvanceP2P.so: imported successfully [0.43s]``[13:56:40] [2``/182``] Analyzing libAudioFFmpegDecode.so...``[13:56:40] [2``/182``] libAudioFFmpegDecode.so: imported successfully [0.05s]``# ... 这里略过了，是一堆so的分析profile``[13:58:41] [174``/182``] Analyzing libwxperf-tkill.so...``[13:58:41] [174``/182``] libwxperf-tkill.so: imported successfully [0.02s]``[13:58:41] [175``/182``] Analyzing libxeffect_xlog.so...``[13:58:41] [175``/182``] libxeffect_xlog.so: imported successfully [0.01s]``[13:58:41] [176``/182``] Analyzing libxffmpeg.so...``[13:58:51] [176``/182``] libxffmpeg.so: imported successfully [9.55s]``[13:58:51] [177``/182``] Analyzing libxlabeffect.so...``[13:58:51] [177``/182``] libxlabeffect.so: imported successfully [0.07s]``[13:58:51] [178``/182``] Analyzing libxsummary.so...``[13:58:51] [178``/182``] libxsummary.so: imported successfully [0.08s]``[13:58:51] [179``/182``] Analyzing libxweb_hpatchz.so...``[13:58:51] [179``/182``] libxweb_hpatchz.so: imported successfully [0.02s]``[13:58:51] [180``/182``] Analyzing libxweb_linker.so...``[13:58:51] [180``/182``] libxweb_linker.so: imported successfully [0.03s]``[13:58:51] [181``/182``] Analyzing libz-ng.so...``[13:58:51] [181``/182``] libz-ng.so: imported successfully [0.03s]``[13:58:51] [182``/182``] Analyzing libzidl2.so...``[13:58:51] [182``/182``] libzidl2.so: imported successfully [0.09s]``[13:58:51] Importing native strings and cross-references...``[13:59:34] Native call graph analysis complete [174.2s]` |
|-|-|

可以达到追踪native函数的效果：

![image](https://bbs.kanxue.com/upload/attach/202607/586240_BSNFSK77CJXH3EG.webp)

-----------------

项目地址：<https://github.com/neocanable/garlic>，欢迎使用反馈。

---

# 回复

## 回复 by huluxia (#2)

*2026-7-10 01:18*

牛逼????

## 回复 by x1a0f3n9 (#3)

*2026-7-10 05:00*

看样子是能省时间的，谢谢分享

## 回复 by iBa0 (#4)

*2026-7-10 08:20*

1

## 回复 by mb_qimctavn (#5)

*2026-7-10 09:06*

6

## 回复 by koflfy (#6)

*2026-7-10 09:33*

mark

## 回复 by Gryffindoss (#7)

*2026-7-10 09:38*

66666

## 回复 by mb_ldbucrik (#8)

*2026-7-10 10:34*

感谢分享

## 回复 by mb_vghyvbhn (#9)

*2026-7-10 11:30*

666

## 回复 by Imxz (#10)

*2026-7-10 11:53*

tql

## 回复 by 小黄鸭爱学习 (#11)

*2026-7-10 15:15*

garlic是什么

## 回复 by mb_jnmxfjku (#12)

*2026-7-10 15:19*

666

## 回复 by neocanable (#13)

*2026-7-10 15:30*

>
> [小黄鸭爱学习](https://bbs.kanxue.com/user-832784.htm)
>  garlic是什么
>

是一个开源的反编译软件

## 回复 by 温泉划水鱼 (#14)

*2026-7-10 17:15*

看看

## 回复 by git_84461osscv (#15)

*2026-7-11 02:27*

谢谢分享

## 回复 by mb_dqctdtly (#16)

*2026-7-11 09:34*

666

## 回复 by mb_gjhmacqd (#17)

*2026-7-11 13:51*

111

## 回复 by mb_rztmbvgb (#18)

*2026-7-11 14:56*

666

## 回复 by vlinkstone (#19)

*2026-7-11 16:21*

为你点赞！

## 回复 by GeeKc (#20)

*2026-7-11 17:04*

123

## 回复 by shuaiaimei (#21)

*2026-7-11 17:15*

看看66

## 回复 by 我是土匪 (#22)

*2026-7-11 17:23*

效率还行，可以增强一下混淆对抗，对畸形的zip格式的处理等

## 回复 by 咸鱼…… (#23)

*2026-7-12 00:42*

666

## 回复 by gtacsr (#24)

*2026-7-12 00:44*

可以啊，学习中

## 回复 by apxar (#25)

*2026-7-12 11:55*

1

## 回复 by endlif (#26)

*2026-7-12 13:17*

666

## 回复 by mb_qqihqaoo (#27)

*2026-7-12 14:51*

6333333

## 回复 by wx_北极星_493 (#28)

*2026-7-13 02:27*

看看

## 回复 by yuanyouran (#29)

*2026-7-13 08:56*

666

## 回复 by 学计算机睡觉 (#30)

*2026-7-13 10:50*

111

## 回复 by nuomida (#31)

*2026-7-13 13:53*

感谢分享

## 回复 by 桐人dx (#32)

*2026-7-13 21:38*

666

## 回复 by sfl4800 (#33)

*2026-7-14 10:43*

厉害。对我们不懂的。能自动化就好了

## 回复 by 简单的简单 (#34)

*2026-7-14 11:33*

666

## 回复 by aจุ๊บ (#35)

*2026-7-14 13:34*

学习！

## 回复 by wdone (#36)

*2026-7-14 13:54*

来学习了

## 回复 by mb_ykavguun (#37)

*2026-7-15 13:00*

1

## 回复 by tubecityman (#38)

*2026-7-15 14:12*

6666

## 回复 by shuangmou (#39)

*2026-7-15 21:40*

感谢大佬分享

## 回复 by mb_zsmeyemp (#40)

*2026-7-15 22:57*

6666

## 回复 by 寒号鸟二代 (#41)

*2026-7-16 00:25*

6666

## 回复 by mb_otbrjfou (#42)

*2026-7-16 00:37*

666

## 回复 by 洪堡企鹅 (#43)

*2026-7-16 10:48*

666

## 回复 by wx_三生三世 (#44)

*2026-7-16 11:14*

多谢分享

## 回复 by Nijika (#45)

*2026-7-16 11:39*

1

## 回复 by 3cly (#47)

*2026-7-16 16:15*

1

## 回复 by neocanable (#48)

*2026-7-16 23:07*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  sfl4800](https://bbs.kanxue.com/user-16343.htm)
>  厉害。对我们不懂的。能自动化就好了
>

已经是自动化的了，需要配置的仅仅是个mcp server，如果在cc switch上，只需要配置：
{
  "command": "garlic", // 例如: /usr/bin/garlic
  "args": [
    "-m"
  ]
}

## 回复 by 29o (#49)

*2026-7-17 23:39*

1

## 回复 by SInnon (#50)

*2026-7-18 00:55*

666

## 回复 by FMNS (#51)

*2026-7-19 05:45*

6666

## 回复 by 钟白 (#52)

*2026-7-19 15:23*

6666

## 回复 by 特洛伊Troye (#53)

*2026-7-21 14:23*

666

## 回复 by 木魚· (#54)

*2026-7-21 14:49*

66666666

## 回复 by mb_yvuzbfvo (#55)

*2026-7-21 15:09*

777

## 回复 by wx_插曲 (#56)

*2026-7-21 15:13*

1

## 回复 by mb_obrkxtbn (#57)

*2026-7-21 15:19*

学习

## 回复 by mb_zpxizkoa (#58)

*2026-7-21 17:49*

1

## 回复 by method (#59)

*2026-7-22 14:22*

1

## 回复 by mb_myeogrox (#60)

*2026-7-22 14:23*

看看

## 回复 by s1nec-1o (#61)

*2026-7-22 14:28*

1

## 回复 by mb_isbmbfet (#62)

*2026-7-22 15:41*

666

## 回复 by qianyu123 (#63)

*2026-7-22 19:06*

6666

## 回复 by 英俊 (#64)

*2026-7-24 11:22*

lala

## 回复 by Trespassing (#65)

看看

## 回复 by dpzx (#66)

学习

## 回复 by GEKEZYX (#67)

666

## 回复 by mb_rtxtnuec (#68)

感谢分析

## 回复 by 大萨达 (#69)

不错

## 回复 by mb_irhdtnzm (#70)

1
