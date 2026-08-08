---
title: '[原创]metadata案例分享与游戏菜单制作'
url: https://bbs.kanxue.com/thread-289817.htm
tid: 289817
author: rettozero
date: '2026-01-21'
tags: [Android安全, 原创, 逆向分析, 程序开发, 源码框架, 工具脚本]
crawled_at: '2026-08-08T10:29:00+00:00'
replies: 40
---

# metadata案例分享与游戏菜单制作

## 0x0 前言

1.分享第一篇文章中global-metadata加密的4个案例（附件下载地址）

2.metadata版本39无法dump的问题

3.手游Mod菜单制作如何制作

## 0x1 Il2CppInspectorRedux

由于[Il2CppDumper](https://github.com/Perfare/Il2CppDumper)的作者没有更新，很多人碰到metadata版本为39时无法dump。

观察39版本的metadata可以发现，整个头部结构体是有很大变化的。

但我们仍可以使用[Zygisk-Il2CppDumper](https://github.com/Perfare/Zygisk-Il2CppDumper)进行dump。

然而每次都要编译项目安装插件实在麻烦。这里分享一个工具。

[Il2CppInspectorRedux](https://github.com/LukeFZ/Il2CppInspectorRedux)

- Support for metadata version 29/29.1/31/35/38/39/104/105, with full reconstruction of custom attributes

简介中我们可以看见支持的版本信息，因此大家可以尝试使用这个工具，这里只做一个简单的使用介绍。
 ![image](https://bbs.kanxue.com/upload/attach/202601/931883_Q8PE2SCTFDZHD23.webp)

勾选指定的结果导出即可。

## 0x2 手游Mod菜单制作

**[Android-Mod-Menu](https://github.com/LGLTeam/Android-Mod-Menu)**

如果是第一次接触，对于如何制作游戏菜单肯定是毫无头绪或是不知从何下手。

直接拿开源的项目学习和使用是最方便。

这里也简单讲解一下。

### JAVA

如需修改菜单UI界面，如配色，字体大小样式等，在Menu.java文件中修改

| 1234567891011121314151617181920212223242526 | `public static final String TAG` `=` `"Mod_Menu"``;` `/``/``Tag` `for` `logcat` `int` `TEXT_COLOR` `=` `Color.parseColor(``"#82CAFD"``);``int` `TEXT_COLOR_2` `=` `Color.parseColor(``"#FFFFFF"``);``int` `BTN_COLOR` `=` `Color.parseColor(``"#1C262D"``);``int` `MENU_BG_COLOR` `=` `Color.parseColor(``"#EE1C2A35"``);` `/``/``#AARRGGBB``int` `MENU_FEATURE_BG_COLOR` `=` `Color.parseColor(``"#DD141C22"``);` `/``/``#AARRGGBB``int` `MENU_WIDTH` `=` `290``;``int` `MENU_HEIGHT` `=` `210``;``int` `POS_X` `=` `0``;``int` `POS_Y` `=` `100``;` `float` `MENU_CORNER` `=` `4f``;``int` `ICON_SIZE` `=` `45``;` `/``/``Change both width` `and` `height of image``float` `ICON_ALPHA` `=` `0.7f``;` `/``/``Transparent``int` `ToggleON` `=` `Color.GREEN;``int` `ToggleOFF` `=` `Color.RED;``int` `BtnON` `=` `Color.parseColor(``"#1b5e20"``);``int` `BtnOFF` `=` `Color.parseColor(``"#7f0000"``);``int` `CategoryBG` `=` `Color.parseColor(``"#2F3D4C"``);``int` `SeekBarColor` `=` `Color.parseColor(``"#80CBC4"``);``int` `SeekBarProgressColor` `=` `Color.parseColor(``"#80CBC4"``);``int` `CheckBoxColor` `=` `Color.parseColor(``"#80CBC4"``);``int` `RadioColor` `=` `Color.parseColor(``"#FFFFFF"``);``int` `CollapseColor` `=` `Color.parseColor(``"#232F2C"``);``String NumberTxtColor` `=` `"#41c300"``;` |
|-|-|

### JNI

3个hook库，分别对应64位、32位、内存读写修改

And64InlineHook

Substrate

KittyMemory

main.cpp

| 12345678910 | `jobjectArray GetFeatureList(JNIEnv` `*``env, jobject context) {``jobjectArray ret;` `const char` `*``features[]` `=` `{``OBFUSCATE(``"Toggle_No death"``),``OBFUSCATE(``"Button_Start Invcibility (30 sec duration)"``),``OBFUSCATE(``"SeekBar_Score multiplier_1_100"``),``OBFUSCATE(``"SeekBar_Coins multiplier_1_1000"``),``OBFUSCATE(``"Category_Examples"``),` `/``/``Not counted``OBFUSCATE(``"Toggle_The toggle"``),` |
|-|-|

菜单的命名、按钮、开关、滑条和绑定的数值可以通过这里直接修改，通过下划线断开。

例如Toggle_No death 设置一个开关 名字为No death 默认值为0。

| 12345678910111213141516171819202122 | `void Changes(JNIEnv` `*``env, jclass clazz, jobject obj, jint featNum, jstring featName, jint value, jlong Lvalue, jboolean boolean, jstring text) {` `switch (featNum) {``case` `0``:``{``if` `(boolean)``gPatches.noDeath.Modify();``else``gPatches.noDeath.Restore();``break``;``}``case` `1``:``btnPressed` `=` `true;``break``;``case` `2``:``scoreMul` `=` `value;``break``;``case` `3``:``coinsMul` `=` `value;``break``;``}``}` |
|-|-|

hook写法，4个参数，（目标so，偏移，rep函数，ori函数）

OBFUSCATE是字符串加密函数，引用这个库https://github.com/adamyaxley/Obfuscate，一个头文件即可，十分方便。

| 1234567 | `#define targetLibName OBFUSCATE("libil2cpp.so")` `HOOK(targetLibName, str2Offset(OBFUSCATE(``"0x107A2E0"``)), AddScore, old_AddScore);``HOOK(targetLibName, str2Offset(OBFUSCATE(``"0x107A2FC"``)), AddCoins, old_AddCoins);``HOOK(targetLibName, str2Offset(OBFUSCATE(``"0x1078C44"``)), Update, old_Update);` `gPatches.noDeath` `=` `MemoryPatch::createWithHex(il2cppBase` `+` `str2Offset(OBFUSCATE(``"0x1079728"``)),` `"C0 03 5F D6"``);` |
|-|-|

如需修改mod图标和其余界面内容修改Menu(Menu.cpp\Setup.cpp)即可，这里不多做介绍了。

上传的附件：
- 下载地址.txt

（0.03kb，24次下载）

---

# 回复

## 回复 by Imxz (#2)

*2026-1-22 16:03*

tql

## 回复 by xingbing (#3)

*2026-1-22 16:24*

学习

## 回复 by 恋一世的爱 (#4)

*2026-1-23 01:40*

看看

## 回复 by wx_Huber Barrientos (#5)

*2026-1-23 12:08*

为你点赞！

## 回复 by MaYil (#6)

*2026-1-23 13:38*

感谢分享

## 回复 by mb_kxnxllvw (#7)

*2026-1-31 18:16*

感谢分享

## 回复 by doglove (#8)

*2026-1-31 19:46*

学习了，支持 。

## 回复 by GEKEZYX (#9)

*2026-2-2 09:58*

666

## 回复 by 拍拖 (#10)

*2026-2-5 09:16*

为你点赞！

## 回复 by mb_uruwpimj (#11)

*2026-2-6 01:20*

学习学习

## 回复 by mb_yalauklc (#12)

*2026-2-15 22:23*

看看内容

## 回复 by 我是小奥 (#13)

*2026-2-21 12:22*

学习学习

## 回复 by mb_irhdtnzm (#14)

*2026-3-2 09:46*

1

## 回复 by 八神许愿 (#15)

*2026-3-3 08:30*

学习学习

## 回复 by 小尘0000 (#16)

*2026-3-3 13:44*

666

## 回复 by mb_qimctavn (#17)

*2026-3-5 12:14*

6

## 回复 by 漆黑火焰魔法使 (#18)

*2026-3-5 12:32*

感谢分享，学习了。

## 回复 by mb_zdoxkucm (#19)

*2026-3-5 15:25*

看看隐藏

## 回复 by wx_宇克鴻 (#20)

*2026-3-7 17:15*

666

## 回复 by mb_jzyasacd (#21)

*2026-3-8 00:57*

665

## 回复 by lackone (#22)

*2026-3-28 11:48*

6666

## 回复 by 勒LI (#23)

*2026-3-28 16:43*

666

## 回复 by 星辰北天 (#24)

*2026-3-29 19:45*

666666

## 回复 by mb_ecyhqrqd (#25)

*2026-3-31 03:28*

666666

## 回复 by huangjw (#26)

*2026-3-31 09:24*

学习了 ， 谢谢

## 回复 by 外交 (#27)

*2026-4-2 10:14*

6

## 回复 by netwolfer (#28)

*2026-4-16 10:23*

888

## 回复 by fffgggfg (#29)

*2026-4-17 14:07*

6666666666666

## 回复 by mb_ileraodd (#30)

*2026-4-25 17:08*

666

## 回复 by mb_kpzkkmql (#31)

*2026-4-30 08:51*

444

## 回复 by mb_kpzkkmql (#32)

*2026-4-30 08:51*

444

## 回复 by 4Chan (#33)

*2026-4-30 11:26*

学习一下

## 回复 by mb_rmwvchlr (#34)

*2026-4-30 12:37*

666666

## 回复 by mb_4nrpVMxJ (#35)

*2026-4-30 15:21*

555

## 回复 by Zepp7289 (#36)

*2026-4-30 15:28*

tql

## 回复 by nqminhquan (#37)

*2026-4-30 19:34*

6666666

## 回复 by B.M.K (#38)

*2026-5-27 23:30*

看看

## 回复 by mb_jegknedl (#39)

*2026-6-3 20:33*

学习学习

## 回复 by mb_cedxuhcp (#40)

*2026-6-22 22:56*

tql

## 回复 by 听闻 (#41)

*2026-7-14 17:32*

感谢分享
