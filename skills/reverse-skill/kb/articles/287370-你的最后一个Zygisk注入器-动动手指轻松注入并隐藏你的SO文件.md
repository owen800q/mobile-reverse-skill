---
title: '[原创]你的最后一个Zygisk注入器 - 动动手指轻松注入并隐藏你的SO文件'
url: https://bbs.kanxue.com/thread-287370.htm
tid: 287370
author: 棕熊
date: '2025-06-26'
tags: [Android安全, 原创, 程序开发, HOOK注入, 工具脚本]
crawled_at: '2026-08-09T04:47:51+00:00'
replies: 283
---

# Zygisk注入器 - 动动手指轻松注入并隐藏你的SO文件

## 2025 10.19进度

- 1.0 已经趋于稳定，开始开发内核隐藏相关
- 1.x 版本计划增加gadget自动下载，lspant自动注入、apk、dex注入逻辑 在内核模块做完后开发

## 前言

作者在去年发布了[Zygisk注入模块的实现](https://bbs.kanxue.com/thread-283790.htm)，成功实现了模块的自动注入和Riru隐藏功能。

然而，每次更换目标应用都需要重新编译，操作繁琐，导致用户采用率不高。为了解决这个问题，作者对项目进行了全面重构，带来了以下改进：

- **图形化界面**：告别命令行，操作更直观
- **一键安装**：面具模块快速部署
- **配套管理APP**：轻松管理注入配置

项目已完全开源，包含面具模块、管理APP以及所有打包脚本，并配置了GitHub CI自动构建。欢迎各位开发者贡献代码，提交PR。

### 版本规划&更新记录

版本规划:

- **v1.x**：专注功能添加，暂不考虑反检测
- **v2.x**：实现各种检测绕过，达到100%无痕注入

更新记录:

- **v1.2**: 增加gadget配置的自动生成，支持脚本和server模式，解决了若干bug，增加了全局注入延迟设置

## 致谢

**项目地址**：<https://github.com/jiqiu2022/Zygisk-MyInjector>

特别感谢以下项目和开发者（按时间顺序）：

- [Zygisk-Il2CppDumper](https://github.com/Perfare/Zygisk-Il2CppDumper) - 提供最原始的注入思路
- Riru - 提供隐藏思路
- 小佳大佬 - 提供App界面化的思路
- [soLoader](https://github.com/SoyBeanMilkx/soLoader) - 提供自定义linker注入的全部逻辑，期待认识作者和作者一起继续完善
- 感谢大佬提出的多个bug和建议，今天已经更新 https://github.com/Assistest

如果对自定义linker感兴趣的大佬，推荐soLoader作者的文章https://yuuki.cool/2025/06/15/CustomLinker/

## 使用教程

### 步骤一：下载并安装面具模块

1. 前往 [GitHub Release](https://github.com/jiqiu2022/Zygisk-MyInjector/tags) 页面下载最新版本的面具模块

本教程以 [v1.1.0](https://github.com/jiqiu2022/Zygisk-MyInjector/releases/tag/v1.1.0) 版本为例
2. 下载模块文件（如下图所示）：

![CleanShot_2025_06_26_at_20_33_37](https://bbs.kanxue.com/upload/attach/202506/967562_DQH38SPW5GHVSAT.png)
3. 安装到手机，支持所有面具模块相关的APP（如 KernelSU、APatch 等）

>
> **注意**：如果您的APP不支持Zygisk注入，请额外安装 Zygisk-Next 模块，否则可能导致注入失败。
>
>
>

### 步骤二：准备SO文件并配置

#### 1. 添加SO文件

进入"SO文件管理"，点击"增加SO文件"：

![CleanShot_2025_06_26_at_20_36_35](https://bbs.kanxue.com/upload/attach/202506/967562_XFBCAGZUNS7FVZV.png)

选择要注入的SO文件：

![CleanShot_2025_06_26_at_20_37_10](https://bbs.kanxue.com/upload/attach/202506/967562_VH34N4BMSB9GXFU.png)

本教程使用以下两个SO文件进行测试：

- `libmylib.so`（全注入测试）
- `libgadget.so`（普通注入方式）

>
> **提示**：后文将解释为什么自定义linker无法注入 `libgadget.so`。
>
>
>

#### 2. 处理原文件

选择SO后，系统会询问是否删除原文件：

![CleanShot_2025_06_26_at_20_38_42](https://bbs.kanxue.com/upload/attach/202506/967562_P4MEBUR4W3HE3D5.png)

>
> **设计理念**：此功能可防止某些APP扫描tmp目录中的SO文件进行风控检测。
>
>
>

添加成功后，SO管理界面会显示已添加的文件：

![CleanShot_2025_06_26_at_20_39_38](https://bbs.kanxue.com/upload/attach/202506/967562_STDPHCMZVP8WW87.png)

>
> **提示**：修改配置后，建议先关闭再开启注入开关，确保新配置生效。
>
>
>

## 编译指南

### 自动编译

参考项目中的 [CI配置文件](https://github.com/jiqiu2022/Zygisk-MyInjector/blob/main/.github/workflows/ci.yml)。

如果您fork了本项目，只需在本地修改代码并push，云端将自动编译。

### 本地编译

使用项目提供的 `build_all.sh` 脚本进行编译。

>
> **环境要求**：需要Java 17环境。
>
>
>

## 工作原理

### 注入流程详解

1. **SO文件管理**
	- 用户选择SO文件后，APP自动将其复制到 `/data/adb/modules/module-name` 目录下进行统一管理
2. **配置生成**
	- 完成APP配置后，管理器在 `/data/adb/modules/module-name` 下创建config文件
	- 面具模块启动时读取此配置，执行SO加载
3. **注入激活**
	- 开启注入时：APP将管理器中的SO复制到目标APP目录，并将config状态设置为开启
	- 关闭注入时：APP自动删除已复制的SO文件，将config状态设置为关闭

## 为什么自定义linker不能注入gadget

| 123 | `frida_KjnwyG_detect_location: assertion failed: (our_range !``=` `null)``Bail out! Frida:ERROR:..``/``lib``/``KjnwyG``/``KjnwyG.vala:``809``:frida_KjnwyG_detect_location: assertion failed: (our_range !``=` `null)``Aborted` |
|-|-|

因为gadget的init_array里面其中有一个函数，尝试使用maps和soinfo获取到自己模块的信息，防止递归调用。

但是自定义linker的soinfo和内存段都是自己分配的，导致gadget找不到自己，发生了断言失败，我们可以简单的去掉断言，但是可能造成其他bug，后续作者会和小佳一起修复。

当然还有一种复杂的方法，就是用注入的so的soinfo，替换成要注入的so的，多见于360等壳子，等后续作者会实现。

## 后续更新计划

- **深度隐藏**：联动面具模块，提供maps等更深层次的隐藏功能
- **用户体验优化**：
	- 提供更友好的界面交互

---

上传的附件：
- libmylib.so

（4.23kb，106次下载）

---

# 回复

## 回复 by mb_cfjwplfo (#2)

*2025-6-26 21:36*

1

## 回复 by 天水姜伯约 (#3)

*2025-6-26 21:36*

支持

## 回复 by SomeMx (#4)

*2025-6-26 21:42*

太强了 楼主

## 回复 by 我是小奥 (#5)

*2025-6-26 21:51*

1

## 回复 by mb_ebiwunmj (#6)

*2025-6-26 21:56*

学习

## 回复 by mie mie (#7)

*2025-6-26 22:02*

1![image](https://bbs.kanxue.com/view/img/face/086.gif)

## 回复 by dufumov (#8)

*2025-6-26 22:21*

学习

## 回复 by mb_kgsesxqm (#9)

*2025-6-26 22:54*

看看

## 回复 by mb_kgsesxqm (#10)

*2025-6-26 23:00*

楼主，开启注入时：APP将管理器中的SO复制到目标APP目录，这个目录是复制到data/data/包名下，还是说data/app/包名/lib下

## 回复 by mb_ldbucrik (#11)

*2025-6-26 23:16*

感谢分享

## 回复 by 清风jw (#12)

*2025-6-26 23:37*

感谢分享

## 回复 by uni7corn (#13)

*2025-6-27 00:37*

感谢分享。

## 回复 by wjwujian (#14)

*2025-6-27 01:38*

支持下吧

## 回复 by 资深老油条 (#15)

*2025-6-27 03:03*

感谢分享

## 回复 by Mark. (#16)

*2025-6-27 06:15*

感谢分享

## 回复 by zhengyuqin (#17)

*2025-6-27 06:41*

666

## 回复 by zhczf (#18)

*2025-6-27 07:04*

实现了模块的自动注入和Riru隐藏功能

## 回复 by byhk (#19)

*2025-6-27 08:10*

谢谢分享

## 回复 by mb_inxgtoge (#20)

*2025-6-27 08:15*

android 15支持吗?

## 回复 by mb_4nrpVMxJ (#21)

*2025-6-27 08:23*

看看

## 回复 by mb_inxgtoge (#22)

*2025-6-27 08:29*

SO文件还要自己去开发?

## 回复 by kxblah (#23)

*2025-6-27 09:18*

1111

## 回复 by matrump (#24)

*2025-6-27 09:34*

666

## 回复 by 棕熊 (#25)

*2025-6-27 09:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_kgsesxqm](https://bbs.kanxue.com/user-969771.htm)
>
>  楼主，开启注入时：APP将管理器中的SO复制到目标APP目录，这个目录是复制到data/data/包名下，还是说data/app/包名/lib下
>
>

目前是目录下的files文件夹下，后面可以自己定义

## 回复 by git_62308kangaroo2333 (#26)

*2025-6-27 09:35*

学习了

## 回复 by DirtyAngle (#27)

*2025-6-27 09:58*

1

## 回复 by wangzehua (#28)

*2025-6-27 10:02*

666

## 回复 by 世界美景 (#29)

*2025-6-27 10:44*

感谢分享  我自己写的面具模块注入器 貌似可以丢掉了  ![image](https://bbs.kanxue.com/view/img/face/060.gif)

## 回复 by lvchalove (#30)

*2025-6-27 10:47*

666

## 回复 by 肉蚌葱鸡 (#31)

*2025-6-27 11:02*

1. 你好 测试发现一个bug 当so文件过多的时候 选项就被顶下去了 无法使用自定义linker那个选项了
 2. 实际上可以在下面多一个配置项 注入gadget.so配置选项 的复选框 配置项为 端口和注入模式 如图
我拉了一下项目想编译的 但报错了 工作较忙没事加折腾 如果需要代码可以联系我 我处理好了这部分 以及zygisk部分 排除config.so加载的部分  感谢为爱发电
![image](https://bbs.kanxue.com/upload/attach/202506/807763_JAKHMRDS2QA7TT5.webp)![image](https://bbs.kanxue.com/upload/attach/202506/807763_ZZVUMX42GDQF6VA.webp)

## 回复 by mb_inxgtoge (#32)

*2025-6-27 11:17*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  肉蚌葱鸡](https://bbs.kanxue.com/user-807763.htm)
>
>  1. 你好 测试发现一个bug 当so文件过多的时候 选项就被顶下去了 无法使用自定义linker那个选项了&nbsp;2. 实际上可以在下面多一个配置项 注入gadget.so配置选项 的复 ...
>
>

你的SO文件是哪里来的，是要注入的APP里面的SO吗？

## 回复 by 晨曦遇晓 (#33)

*2025-6-27 11:17*

6666

## 回复 by mb_inxgtoge (#34)

*2025-6-27 11:18*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_inxgtoge](https://bbs.kanxue.com/user-931200.htm)
>
>  你的SO文件是哪里来的，是要注入的APP里面的SO吗？
>
>

这工具没明白用法，不知道SO是哪里来的,是自己开发,还是注入APP里面的SO文件?

## 回复 by 肉蚌葱鸡 (#35)

*2025-6-27 11:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_inxgtoge](https://bbs.kanxue.com/user-931200.htm)
>
>  这工具没明白用法，不知道SO是哪里来的,是自己开发,还是注入APP里面的SO文件?
>
>

注入自己的so到目标app 这个项目就是这个功能

## 回复 by dreameriii (#36)

*2025-6-27 11:23*

666666

## 回复 by 蜡笔晓辉 (#37)

*2025-6-27 12:18*

6666666

## 回复 by 院士 (#38)

*2025-6-27 12:40*

来学习新知识。

## 回复 by 安卓逆向test (#39)

*2025-6-27 13:33*

大佬有研究过在内核中直接使用uprobe吗，可以交流下

## 回复 by 西瓜帅 (#40)

*2025-6-27 13:47*

我来看看

## 回复 by lotus* (#41)

*2025-6-27 13:49*

666666

## 回复 by 棕熊 (#42)

*2025-6-27 13:55*

麻烦大佬提一个issues 我今天下午解决！

## 回复 by niceday (#43)

*2025-6-27 14:55*

感谢分享

## 回复 by xianhuimin (#44)

*2025-6-27 15:16*

看看 666

## 回复 by 珍惜Any (#45)

*2025-6-27 16:21*

用最新版的。老版本一堆bug 最新版本 6.21 。加我我发你最新版。

## 回复 by 棕熊 (#46)

*2025-6-27 17:01*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  用最新版的。老版本一堆bug 最新版本 6.21 。加我我发你最新版。
>
>

是的，老版本由于bug问题没有检测出来，珍惜大佬见谅，我后面补测新版的

## 回复 by 珍惜Any (#47)

*2025-6-27 18:46*

>
> [棕熊](https://bbs.kanxue.com/user-967562.htm)
>
>  是的，老版本由于bug问题没有检测出来，珍惜大佬见谅，我后面补测新版的
>
>

不是bug，是检测逻辑可能有问题 ![image](https://bbs.kanxue.com/view/img/face/002.gif) 毕竟只能检测到应用层的,,,,![image](https://bbs.kanxue.com/view/img/face/055.gif)![image](https://bbs.kanxue.com/view/img/face/055.gif)![image](https://bbs.kanxue.com/view/img/face/055.gif)

## 回复 by mb_qimctavn (#48)

*2025-6-27 19:08*

学习

## 回复 by zz胡 (#49)

*2025-6-27 19:48*

![image](https://bbs.kanxue.com/view/img/face/004.gif) 我就看看

## 回复 by mb_dybhojzi (#50)

*2025-6-27 20:00*

1111

## 回复 by mb_kqxwunfu (#51)

*2025-6-28 05:55*

你好我使用你这个项目APP内无法看见路径下的so文件，外部管理器能选择返回的路径是错误的，手动输入路径在data目录里的so文件选择注入无效果。几种方式都试了就是一个简单的so注入成功打印日志

## 回复 by 夜惜风雨 (#52)

*2025-6-28 10:06*

111111111

## 回复 by 文西哥 (#53)

*2025-6-28 11:42*

666

## 回复 by Yangser (#54)

*2025-6-28 12:11*

学习学习????

## 回复 by qqyspgj (#55)

*2025-6-28 14:35*

看看楼主的分享，感谢发布

## 回复 by mb_xvjarnta (#56)

*2025-6-28 14:58*

66666

## 回复 by 棕熊 (#57)

*2025-6-28 15:50*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_kqxwunfu](https://bbs.kanxue.com/user-1042110.htm)
>
>  你好我使用你这个项目APP内无法看见路径下的so文件，外部管理器能选择返回的路径是错误的，手动输入路径在data目录里的so文件选择注入无效果。几种方式都试了就是一个简单的so注入成功打印日志
>
>

你好 尝试一下最新版本 选择逻辑恢复了 注入也有修复

## 回复 by mb_kbkqyusp (#58)

*2025-6-28 16:25*

牛逼

## 回复 by mb_gpvapxrg (#59)

*2025-6-28 16:49*

SO文件还要自己去开发?

## 回复 by MaYil (#60)

*2025-6-28 16:57*

感谢分享

## 回复 by 正在更新中 (#61)

*2025-6-28 23:58*

学习提高共同进步

## 回复 by wx_ln (#62)

*2025-6-29 02:08*

6666666666666666

## 回复 by 末日大哥 (#63)

*2025-6-29 15:43*

666

## 回复 by cpannn (#64)

*2025-6-29 20:22*

注入libgadget.so,执行frida -U -F ,试了很多App,都是Unable to get frontmost application on Pixel 4 XL: unable to connect to remote frida-server: closed.![image](https://bbs.kanxue.com/view/img/face/011.gif)

## 回复 by fangliangz (#65)

*2025-6-30 09:38*

666

## 回复 by ccc9329 (#66)

*2025-6-30 10:52*

666666

## 回复 by 4Chan (#67)

*2025-6-30 10:55*

666

## 回复 by Ankeys (#68)

*2025-6-30 11:20*

666

## 回复 by mb_xjdhrmck (#69)

*2025-6-30 14:09*

66666

## 回复 by mb_eumnbkwy (#70)

*2025-6-30 15:54*

不错

## 回复 by torrent选手 (#71)

*2025-6-30 16:29*

怎么把xp模块转成so呀

## 回复 by 丶咖啡猫丶 (#72)

*2025-6-30 16:36*

6666

## 回复 by mb_patxjnad (#73)

*2025-6-30 16:37*

支持

## 回复 by 随风而行aa (#74)

*2025-6-30 16:43*

看看

## 回复 by mb_irhdtnzm (#75)

*2025-6-30 19:35*

1

## 回复 by 棕熊 (#76)

*2025-7-1 08:55*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  cpannn](https://bbs.kanxue.com/user-977484.htm)
>
>  注入libgadget.so,执行frida -U -F ,试了很多App,都是Unable to get frontmost application on Pixel 4 XL: unable to ...
>
>

尝试使用server模式映射127.0.0.1 adbforward转发端口

## 回复 by cubeeeee (#77)

*2025-7-1 13:27*

66666

## 回复 by 软件君子 (#78)

*2025-7-1 15:38*

佬能简单说一下Riru Hide的思路吗

## 回复 by 9527vv7 (#79)

*2025-7-1 16:27*

6

## 回复 by 撒空间zz (#80)

*2025-7-1 16:58*

66666

## 回复 by talentmu (#81)

*2025-7-1 20:55*

非常看好这个模块

## 回复 by 爱吃菠菜 (#82)

*2025-7-1 23:23*

以前还有个ptrace版本的rxposed注入器

## 回复 by 棕熊 (#83)

*2025-7-2 07:16*

>
> [talentmu](https://bbs.kanxue.com/user-215003.htm)
>
>  非常看好这个模块
>
>

可以私信给个联系方式吗，目前来看，是root没有开启

## 回复 by talentmu (#84)

*2025-7-2 08:23*

>
> [棕熊](https://bbs.kanxue.com/user-967562.htm)
>
>  可以私信给个联系方式吗，目前来看，是root没有开启
>
>

1. 就是安装模块时候会被magisk认为不是模块(是update-binary和updater-scirpt两个文件都是0字节)
2. 添加so文件，已经给root权限了的，浏览文件系统功能无法使用，显示此目录为空
相关错误堆栈(也看不出什么，就空指针，可能是虚拟机安卓9问题)

 E  java.lang.NullPointerException: Attempt to invoke virtual method 'void androidx.activity.result.ActivityResultLauncher.launch(java.lang.Object)' on a null object reference

07-02 09:52:15                  E       at com.jiqiu.configapp.GadgetConfigDialog.openFilePicker(GadgetConfigDialog.java:564)

## 回复 by mb_cfzkocqj (#85)

*2025-7-2 10:55*

感谢分享

## 回复 by mb_lfvhycml (#86)

*2025-7-2 13:01*

666666

## 回复 by 迷茫_720464 (#87)

*2025-7-2 18:42*

66666

## 回复 by mb_tewbhakr (#88)

*2025-7-2 23:42*

看看

## 回复 by mb_nwflotoa (#89)

*2025-7-3 01:11*

谢谢分享

## 回复 by agultiga (#90)

*2025-7-3 03:40*

学习！

## 回复 by 不知世事 (#91)

*2025-7-3 15:58*

1

## 回复 by AndroidDev (#92)

*2025-7-3 16:54*

666

## 回复 by mb_pobqzscg (#93)

*2025-7-3 17:16*

666

## 回复 by mb_epnrlpbr (#94)

*2025-7-3 17:29*

666

## 回复 by 呼吸24K纯氧 (#95)

*2025-7-4 09:56*

感谢分享。![image](https://bbs.kanxue.com/view/img/face/054.gif)

## 回复 by SamPoson (#96)

*2025-7-4 18:48*

66666

## 回复 by SInnon (#97)

*2025-7-8 12:30*

666

## 回复 by mb_syaqxuzh (#98)

*2025-7-9 16:12*

牛逼

## 回复 by 小太子奶 (#99)

*2025-7-10 10:03*

真不错的

## 回复 by A冷忆 (#100)

*2025-7-11 21:57*

666

## 回复 by Ms135 (#101)

*2025-7-12 20:53*

666

## 回复 by huangbof (#102)

*2025-7-13 01:05*

隐藏功能

## 回复 by troops (#103)

*2025-7-13 11:57*

qwerrew

## 回复 by wildwine (#104)

*2025-7-20 18:00*

强啊

## 回复 by 星雨心愿 (#105)

*2025-7-21 10:26*

实现过类似的功能，不过我的是基于APK，不是基于源码，兼容有点问题

## 回复 by dfJerry (#106)

*2025-7-21 10:39*

666666666

## 回复 by 无味 (#107)

*2025-7-21 11:49*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by lookaside (#108)

*2025-7-24 17:07*

可以在magisk管理器里安装吗？

## 回复 by flice (#109)

*2025-7-25 18:58*

666

## 回复 by heckerstone (#110)

*2025-7-25 19:31*

666

## 回复 by XCicada (#111)

*2025-7-28 15:04*

太强了

## 回复 by xx_dd_y (#112)

*2025-7-28 16:00*

6666

## 回复 by NopsSan (#113)

*2025-7-30 05:25*

666

## 回复 by GloryUnited (#114)

*2025-7-30 11:25*

666

## 回复 by yyyyy——— (#115)

*2025-8-4 14:58*

666

## 回复 by 自称宅男 (#116)

*2025-8-4 16:54*

123

## 回复 by mb_ynpgeaep (#117)

*2025-8-4 17:39*

1

## 回复 by CheRevir (#118)

*2025-8-4 18:18*

666

## 回复 by mb_eywdngzs (#119)

*2025-8-7 11:18*

666663

## 回复 by mb_clizznfj (#120)

*2025-8-7 17:15*

666

## 回复 by Firear (#121)

*2025-8-7 17:29*

六百六十六

## 回复 by mb_wnoxadfc (#122)

*2025-8-7 17:31*

大神 666

## 回复 by mb_tmbvnlxt (#123)

*2025-8-9 18:26*

11

## 回复 by aq88 (#124)

*2025-8-10 23:06*

学习下

## 回复 by Splite_1130 (#125)

*2025-8-11 21:59*

测试的so文件有大佬可以提供一个吗。

## 回复 by 鞠婧祎 (#126)

*2025-8-12 00:09*

1111

## 回复 by mb_gpiyrayj (#127)

*2025-8-12 16:43*

>
> [棕熊](https://bbs.kanxue.com/user-967562.htm)
>
>  目前是目录下的files文件夹下，后面可以自己定义
>
>

学习

## 回复 by mb_donutrph (#128)

*2025-8-13 15:00*

666

## 回复 by mb_tcandlos (#129)

*2025-8-14 14:26*

111

## 回复 by mb_tcandlos (#130)

*2025-8-14 14:26*

111

## 回复 by mb_skkbqlsl (#131)

*2025-8-14 21:59*

实现了模块的自动注入和Riru隐藏功能 66666

## 回复 by 飆汗吉米 (#132)

*2025-8-17 03:29*

6666

## 回复 by wx_插曲 (#133)

*2025-8-17 11:31*

牛逼

## 回复 by fkueihcy (#134)

*2025-8-18 16:22*

感谢分享

## 回复 by 日暮归途 (#135)

*2025-8-19 08:46*

我也想加群![image](https://bbs.kanxue.com/view/img/face/010.gif)

## 回复 by 程序猿007 (#136)

*2025-8-21 00:47*

666

## 回复 by myios (#137)

*2025-8-24 20:25*

666

## 回复 by isolands (#138)

*2025-8-25 13:22*

感谢大佬，很实用的工具

## 回复 by mb_mrjjcxgk (#139)

*2025-8-27 14:48*

6

## 回复 by 寄予蓝y (#140)

*2025-8-28 10:06*

666

## 回复 by wx_知行_889 (#141)

*2025-8-28 11:35*

123

## 回复 by 杨德勇 (#142)

*2025-8-30 15:38*

666

## 回复 by pigsub (#143)

*2025-9-1 01:13*

6666666666

## 回复 by omuitk (#144)

*2025-9-1 15:35*

666

## 回复 by 烬奇小云 (#145)

*2025-9-1 16:34*

ll

## 回复 by MsScotch (#146)

*2025-9-2 23:11*

mark

## 回复 by hejincai (#147)

*2025-9-4 15:09*

666

## 回复 by cobe (#148)

*2025-9-5 10:00*

666

## 回复 by mb_pnyyaazf (#149)

*2025-9-5 20:54*

666

## 回复 by 威兹曼 (#150)

*2025-9-7 10:16*

感谢分享

## 回复 by ovo_帮我不c (#151)

*2025-9-8 15:58*

111

## 回复 by 云霄IT (#152)

*2025-9-9 02:58*

1

## 回复 by 珍惜Any (#153)

*2025-9-9 10:12*

你哪来的hunter debug包呢？

## 回复 by Tanuyoki0 (#154)

*2025-9-10 23:07*

学习学习

## 回复 by Mr.He (#155)

*2025-9-11 17:12*

66666

## 回复 by 熊猫吃鱼 (#156)

*2025-9-11 17:40*

666666

## 回复 by wx_霿凇 (#157)

*2025-9-16 17:12*

666

## 回复 by mb_birmgglx (#158)

*2025-9-17 12:44*

学习学习

## 回复 by 3倍アイスクリーム! (#159)

*2025-9-19 17:24*

全剧设置那个地方咋设置啊

## 回复 by mb_qqlojqnm (#160)

*2025-9-20 14:09*

6666

## 回复 by 呆萌的小白 (#161)

*2025-9-20 14:49*

太需要了

## 回复 by xeiyu (#162)

*2025-9-26 23:15*

666

## 回复 by Gryffindoss (#163)

*2025-10-5 13:12*

6666

## 回复 by wx_z_329 (#164)

*2025-10-7 20:44*

666

## 回复 by 果冻大砍刀 (#165)

*2025-10-14 16:02*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by 边缘 (#166)

*2025-10-14 18:20*

666

## 回复 by dawnsky1111 (#167)

*2025-10-15 08:51*

666

## 回复 by huangjw (#168)

*2025-10-15 09:09*

好东西

## 回复 by xdcs100 (#169)

*2025-10-15 10:03*

学习

## 回复 by mb_ysegxpmv (#170)

*2025-10-15 21:42*

牛逼大佬，但是我用了没注入成功，点开app一直卡死，frida -U -F连接也是connect close，当然已经adb forward过了

## 回复 by 软乐科技 (#171)

*2025-10-15 21:49*

666666

## 回复 by 拾海 (#172)

*2025-10-17 12:22*

大佬，一直连不上，显示connection closed

## 回复 by 棕熊 (#173)

*2025-10-17 17:32*

>
> [拾海](https://bbs.kanxue.com/user-975047.htm)
>
>  大佬，一直连不上，显示connection closed
>
>

是不是没有socket权限 gadget需要socket权限

## 回复 by xxjj678 (#174)

*2025-10-19 12:49*

666

## 回复 by 旅途风景 (#175)

*2025-10-20 18:00*

goof

## 回复 by mb_bfghjvta (#176)

*2025-10-20 20:34*

很好的注入框架

## 回复 by 黑嘿黑 (#177)

*2025-10-24 13:04*

mark

## 回复 by 不再后悔 (#178)

*2025-10-24 15:01*

666

## 回复 by wx_YIN重启 (#179)

*2025-10-27 15:12*

看看 666

## 回复 by 小福仔 (#180)

*2025-10-29 21:30*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by Mrzh (#181)

*2025-10-29 22:22*

666

## 回复 by mb_iqkkgktq (#182)

*2025-10-31 07:28*

学习一下

## 回复 by 魔童 (#183)

*2025-10-31 10:52*

6666666

## 回复 by mb_ynogmhit (#184)

*2025-10-31 15:38*

111

## 回复 by 勒LI (#185)

*2025-10-31 16:04*

感谢分享

## 回复 by cnk8 (#186)

*2025-11-3 10:51*

如果依赖 Zygisk 检测工具应该直接检测 Zygisk

## 回复 by xuuhaoo (#187)

*2025-11-4 10:47*

康康

## 回复 by 倾心Deep (#188)

*2025-11-4 20:29*

学习

## 回复 by zxqi (#189)

*2025-11-9 16:19*

666

## 回复 by mb_jqqxasya (#190)

*2025-11-10 17:18*

666

## 回复 by 曰你 (#191)

*2025-11-10 21:21*

1

## 回复 by 努力的菜鸡 (#192)

*2025-11-17 11:27*

666

## 回复 by mb_sjxphvyl (#193)

*2025-11-23 04:45*

666

## 回复 by xifgg (#194)

*2025-11-25 10:11*

66

## 回复 by 李啊啊 (#195)

*2025-11-25 10:31*

666

## 回复 by mb_pmwkabcl (#196)

*2025-12-2 03:40*

6

## 回复 by git_71735namngsec-netizen (#197)

*2025-12-2 17:00*

666

## 回复 by mb_awbfnjrt (#198)

*2025-12-3 18:02*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by 屁屁 (#199)

*2025-12-5 14:39*

現在很多遊戲x掛都用此功能了

## 回复 by mb_yeiahmds (#200)

*2025-12-5 15:36*

666

## 回复 by manyuegong33 (#201)

*2025-12-6 10:59*

1111

## 回复 by 莱茵 (#202)

*2025-12-10 00:28*

666

## 回复 by mb_bsvittau (#203)

*2025-12-11 15:56*

1

## 回复 by 叶晓枫A (#204)

*2025-12-14 00:38*

感谢分享

## 回复 by zkbutt (#205)

*2025-12-14 23:56*

学习

## 回复 by TeamAR (#206)

*2025-12-15 00:34*

666

## 回复 by younghare (#207)

*2025-12-15 11:03*

看看如何使用

## 回复 by GEKEZYX (#208)

*2025-12-15 16:51*

666

## 回复 by mb_rbaigqfb (#209)

*2025-12-16 22:37*

感谢师傅分享！

## 回复 by wx_汪洋大海 (#210)

*2025-12-18 22:32*

666

## 回复 by mb_kgyloqxd (#211)

*2025-12-19 08:48*

TQL

## 回复 by mb_ckezvhox (#212)

*2025-12-19 09:35*

1

## 回复 by mb_xflcgdik (#213)

*2025-12-19 09:47*

1

## 回复 by <img> (#214)

*2025-12-19 09:56*

1

## 回复 by mb_yhlgzisk (#215)

*2025-12-19 11:30*

牛的

## 回复 by 盛宝不喝肾宝 (#216)

*2025-12-19 12:16*

学习

## 回复 by 许我浅笑而安 (#217)

*2025-12-20 18:52*

感谢分享~学习到了~

## 回复 by 我心向山 (#218)

*2025-12-23 10:29*

111

## 回复 by wx_五十度灰 (#219)

*2025-12-23 10:36*

666

## 回复 by wx_Huber Barrientos (#220)

*2025-12-23 11:00*

为你点赞！

## 回复 by wx_故事与酒 (#221)

*2025-12-23 18:00*

66666666666666666666666

## 回复 by 飞机上唱山歌 (#222)

*2025-12-25 15:09*

1

## 回复 by cici5000 (#223)

*2025-12-25 16:36*

1123213

## 回复 by 人海孤鸿_923598 (#224)

*2025-12-31 01:05*

很好的东西

## 回复 by mb_xixgoqzn (#225)

*2026-1-6 18:01*

感谢分享。

## 回复 by mb_lojlzfoa (#226)

*2026-1-12 18:22*

谢谢分享

## 回复 by mb_ionmhejx (#227)

*2026-1-13 10:35*

感谢分享

## 回复 by mb_uoktlvrn (#228)

*2026-1-13 16:41*

11

## 回复 by mb_qlanixyh (#229)

*2026-1-15 17:08*

666

## 回复 by timeromantic (#230)

*2026-1-15 20:54*

太强大了，谢谢

## 回复 by mb_ekitlujo (#231)

*2026-1-19 13:52*

66

## 回复 by mb_pwyrkrje (#232)

*2026-1-19 15:03*

学习

## 回复 by mb_pwyrkrje (#233)

*2026-1-19 15:03*

学习

## 回复 by 毛毛毛毛虫 (#234)

*2026-1-19 21:16*

学习一下

## 回复 by mb_sdvjpqrb (#235)

*2026-1-20 17:41*

看看隐藏

## 回复 by dob_C (#236)

*2026-1-21 13:45*

感谢分享

## 回复 by wx_lll_652 (#237)

*2026-1-22 02:53*

学习学习

## 回复 by 天路 (#238)

*2026-1-24 17:24*

666

## 回复 by mb_lakweznz (#239)

*2026-1-25 01:31*

看看臭臭

## 回复 by mb_vmirashm (#240)

*2026-2-3 09:25*

6

## 回复 by Manyu灬 (#241)

*2026-2-4 16:07*

111

## 回复 by mb_jnmxfjku (#242)

*2026-2-5 17:48*

666

## 回复 by mb_eahujfpt (#243)

*2026-2-5 17:52*

感谢分享

## 回复 by 大众 (#244)

*2026-2-7 01:58*

挺好的 学习到了

## 回复 by thinkhack (#245)

*2026-2-10 09:27*

看看怎么持久化frida

## 回复 by xiaohuaxxx (#246)

*2026-2-20 23:51*

666

## 回复 by mb_tkluuesh (#247)

*2026-2-24 15:11*

666

## 回复 by baichisi (#248)

*2026-2-25 10:26*

666

## 回复 by mb_kvunldll (#249)

*2026-2-25 23:26*

666666

## 回复 by  anyeguying (#250)

*2026-3-3 14:57*

magisk 提示 不是模块文件?

## 回复 by Migc (#251)

*2026-3-4 14:49*

666

## 回复 by lucifer11 (#252)

*2026-3-9 13:28*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by git_843361313113 (#253)

*2026-3-9 23:30*

学习

## 回复 by wohowo (#254)

*2026-3-10 10:54*

1

## 回复 by mb_ysikfhxt (#255)

*2026-3-11 11:57*

1

## 回复 by 残枫 (#256)

*2026-3-18 16:43*

学习学习

## 回复 by 老板大七 (#257)

*2026-3-18 17:04*

感谢分享

## 回复 by mb_hkqnanbs (#258)

*2026-3-18 18:51*

66666

## 回复 by 小尘0000 (#259)

*2026-3-22 17:40*

666

## 回复 by mb_duvnsehs (#260)

*2026-3-25 18:09*

666

## 回复 by 二狗的伤心 (#261)

*2026-3-26 21:17*

感谢分享

## 回复 by mb_rrwegvyc (#262)

*2026-3-29 10:11*

666

## 回复 by 星辰北天 (#263)

*2026-3-29 17:10*

666

## 回复 by mb_oqssebnp (#264)

*2026-3-30 20:43*

为你点赞！

## 回复 by wx_妳还是不懂 (#265)

*2026-4-3 19:16*

非常感谢，期待2.X版本，不要忘了这么好的项目了

## 回复 by JuneKill (#266)

*2026-4-9 22:30*

感谢分享

## 回复 by APlus (#267)

*2026-4-10 15:45*

666

## 回复 by mb_unkmqemn (#268)

*2026-4-17 11:47*

666

## 回复 by git_33309Jackie1018 (#269)

*2026-4-21 20:39*

学习

## 回复 by ClPrada (#270)

*2026-5-1 19:48*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by tjytjy (#271)

*2026-5-6 21:11*

666

## 回复 by 鼻屎怪 (#272)

*2026-5-11 22:16*

牛逼大佬

## 回复 by mb_tqskihwz (#273)

*2026-5-13 02:46*

666

## 回复 by mb_weufbroc (#274)

*2026-5-13 05:35*

看看新东西

## 回复 by mb_zurizkle (#275)

*2026-5-25 07:25*

6666

## 回复 by YoungBai (#276)

*2026-5-25 09:47*

666

## 回复 by 老资格 (#277)

*2026-6-8 22:22*

6666

## 回复 by git_34231nguyenvantiennani (#278)

*2026-6-25 14:57*

111

## 回复 by wx_HK_888 (#279)

*2026-6-25 23:19*

厉害了

## 回复 by git_69678tuantmtb (#280)

*2026-7-1 19:05*

666

## 回复 by 桐人dx (#281)

*2026-7-15 16:07*

666

## 回复 by veluboii (#282)

*2026-7-15 17:56*

6666

## 回复 by git_58319TheShuiLan (#283)

*2026-7-16 20:30*

6666666666666666

## 回复 by mb_qbvrapqs (#284)

666
