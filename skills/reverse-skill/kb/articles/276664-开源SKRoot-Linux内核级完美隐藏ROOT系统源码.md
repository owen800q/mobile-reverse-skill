---
title: '[原创]开源SKRoot-Linux内核级完美隐藏ROOT系统源码'
url: https://bbs.kanxue.com/thread-276664.htm
tid: 276664
author: abcz316
date: '2023-03-29'
tags: [Android安全, 原创, 基础理论, 协议分析, 漏洞相关, 程序开发, HOOK注入, 系统相关, 源码框架, 工具脚本]
crawled_at: '2026-07-31T14:51:25+08:00'
replies: 136
---

# SKRoot - SuperKernelRoot - Linux 内核级完美隐藏ROOT演示

## 特点：

- 新一代SKRoot，挑战全网root检测手段
- 跟面具完全不同思路，摆脱面具被检测的弱点，完美隐藏root功能，
- 全程不需要暂停SELinux，实现真正的SELinux 0%触碰，
- 通用性强，通杀所有内核，不需要内核源码，直接patch内核，
- 自带ROOT授权注入
- 兼容安卓APP直接JNI调用，稳定、流畅、不闪退。
 ![image](https://bbs.kanxue.com/upload/attach/202303/892833_CGJGKZMR34RNVBH.png)

# 功能特点：

**1.显示自身权限信息**
**2.获取ROOT权限**
**3.执行ROOT命令**
**4.执行原生内核命令**
**5.安装部署隐藏版su**
**6.注入su到指定进程**
**7.完全卸载清理su**

# 功能备注：

APP应用程序拿到ROOT权限的唯一方法就是得到ROOT密匙，此密匙为48位的随机字符串，安全可靠，如若感觉长度不够，可自行修改源码拓展长度。

其中`【注入su到指定进程】只支持授权su到64位的APP`，老式32位APP不再进行支持，因市面上几乎所有APP都是64位，例如MT文件管理器、Root Explorer文件管理器等等。

# 预览：

 ![image](https://bbs.kanxue.com/upload/attach/202303/892833_UBPKSJ2FA3F76R9.png)
 ![image](https://bbs.kanxue.com/upload/attach/202303/892833_M3A7NA27JA2RF5Z.png)
 ![image](https://bbs.kanxue.com/upload/attach/202303/892833_84MEJGAT226GFAG.png)
 ![image](https://bbs.kanxue.com/upload/attach/202303/892833_BMDMBSPB4R6APEY.png)

# 源码地址：

<https://github.com/abcz316/SKRoot-linuxKernelRoot>

==============================

# 流程：

1.将内核文件拖拽置`patch_kernel_root.exe`即可一键自动化流程补丁内核，同时会自动生成ROOT密匙。

2.编译并启动`PermissionManager`或者`testRoot`，输入ROOT密匙值，开始享受舒爽的ROOT环境。

# 效果：

- 实验设备包括红米K20\K30\K40\K50\K60、小米8\9\10\11\12\13、小米平板5\6、红魔5\6\7、联想、三星、一加、ROG2\3等，支持型号非常多。测试结果显示，SKRoot能够在所支持设备上非常稳定的运行。
- 过市面上所有主流APP的ROOT检测，如农业XX、交X12XX3等...
- 无需理会谷歌GKI
- 让所有的ROOT检测手段都回归尘土吧，愿世界迎来一个美好的ROOT时代！

# 提醒：

**本源码不针对任何程序，仅供交流、学习、调试Linux内核程序的用途，禁止用于任何非法用途**，Root是一把双刃剑，希望大家能营造一个良好的Linux内核Rootkit技术的交流环境。

---

# 回复

## 回复 by 白帽子黑客 (#2)

*2023-3-29 06:08*

大佬，这真是神级开源

## 回复 by sogohere (#3)

*2023-3-29 09:15*

严重关注本帖！

## 回复 by mb_lpcoesnt (#4)

*2023-3-29 09:56*

大佬tql

## 回复 by shinratensei (#5)

*2023-3-29 09:57*

tql![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by New对象处 (#6)

*2023-3-29 10:00*

大佬骚操作

## 回复 by wx_Ora (#7)

*2023-3-29 10:11*

大佬骚操作

## 回复 by 你瞒我瞒 (#8)

*2023-3-29 10:34*

很早就关注GitHub上面的项目了，今天，就在今天，开源了！![image](https://bbs.kanxue.com/view/img/face/71.gif)

## 回复 by chengtoreal (#9)

*2023-3-29 10:49*

大佬牛逼！

## 回复 by 小向i小葵 (#10)

*2023-3-29 10:53*

厉害

## 回复 by DirtyAngle (#11)

*2023-3-29 11:20*

没技术没文化只有一句牛的逼

## 回复 by 哈留 (#12)

*2023-3-29 11:31*

半开源。。。

## 回复 by abcz316 (#13)

*2023-3-29 12:04*

>
> [哈留](https://bbs.kanxue.com/user-721616.htm)
>
>  半开源。。。

手脚架部分自己解决

## 回复 by 万里星河 (#14)

*2023-3-29 15:24*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>
>
>
>
>
>
>  哈留
>
>  半开源。。。 手脚架部分自己解决
>
>

强迫症 不支持32位终究觉得不完美

## 回复 by 万里星河 (#15)

*2023-3-29 15:47*

对了 不知可否请教一个问题 一个没有root的手机 如果我连刷机包都没有 即没有现成的boot.img 是否有办法用大佬的这个工具来实现root

## 回复 by wx_范迪塞尔 (#16)

*2023-3-29 15:50*

大佬和你的procmem可以一起整合么，我看有内核代码执行

## 回复 by 小黄鸭爱学习 (#17)

*2023-3-29 19:18*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  对了 不知可否请教一个问题 一个没有root的手机 如果我连刷机包都没有 即没有现成的boot.img 是否有办法用大佬的这个工具来实现root
>
>

这种走漏洞提权吧

## 回复 by 凯文米特尼克 (#18)

*2023-3-30 09:42*

有大佬复现成功的吗？小白，不知道怎么做呢。

## 回复 by 凯文米特尼克 (#19)

*2023-3-30 09:44*

手脚架是啥意思![image](https://bbs.kanxue.com/view/img/face/9.gif)

## 回复 by mumuya (#20)

*2023-3-30 13:12*

肯定要关注大佬的帖子啦，大佬，现在用上kernelsu也感觉还不错，回头用你这个patch版本试一试

## 回复 by wx_私人账号定制 (#21)

*2023-3-30 13:39*

>
> [mumuya](https://bbs.kanxue.com/user-904675.htm)
>
>  肯定要关注大佬的帖子啦，大佬，现在用上kernelsu也感觉还不错，回头用你这个patch版本试一试
>
>

kernelsu需要新一些的系统才支持，谷歌一代不支持

## 回复 by mb_foyotena (#22)

*2023-3-30 16:44*

有这么麻烦啊, 我放着原来的su这些加固照样检测不到![image](https://bbs.kanxue.com/view/img/face/20.gif)

## 回复 by ssarg (#23)

*2023-3-30 16:45*

请问有release版吗？自己编译出错了。谢谢

## 回复 by MaouAce (#24)

*2023-3-30 17:50*

大佬能不能教一下怎么用IDA伪代码翻译找思路里 1. 2. 的值 ，android 12 不管 boot_a 还是 boot_b kernel 分离完 用 IDA 使用 droiding 脚本都打不开啊 难受![image](https://bbs.kanxue.com/view/img/face/35.gif)

## 回复 by 龙飞雪 (#25)

*2023-3-30 19:24*

厉害.....![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by y360u学逆向 (#26)

*2023-3-30 20:27*

后排围观![image](https://bbs.kanxue.com/view/img/face/51.gif)

## 回复 by dyboxoo (#27)

*2023-3-30 22:41*

目前卡在了patch_kernel_root编译这里。。。。

## 回复 by 罐罐灬 (#28)

*2023-3-31 06:59*

我最近也做了类似的尝试，http://t.csdn.cn/rk6Y8

## 回复 by 小调调 (#29)

*2023-3-31 10:13*

do_execve 没定位到![image](https://bbs.kanxue.com/view/img/face/40.gif)

## 回复 by 罐罐灬 (#30)

*2023-4-1 00:20*

该root方案运行imgui的可执行程序会报错：cmd: Can't find service: window
其他root权限正常，有人知道原因不？

## 回复 by abcz316 (#31)

*2023-4-1 02:47*

你只需要将service相关的命令的运行方式，由运行su替换成SafeRunRootCmd接口，此问题即可解决

## 回复 by abcz316 (#32)

*2023-4-1 02:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  罐罐灬](https://bbs.kanxue.com/user-975795.htm)
>
>  该root方案运行imgui的可执行程序会报错：cmd: Can't find service: window
> 其他root权限正常，有人知道原因不？
>
>

楼上

## 回复 by 韩七鹿 (#33)

*2023-4-1 03:22*

提升adb为root权限没有开源啊大佬

## 回复 by mb_jwdbdcms (#34)

*2023-4-1 03:27*

用解锁bl.吗大佬

## 回复 by 罐罐灬 (#35)

*2023-4-1 06:41*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  你只需要将service相关的命令的运行方式，由运行su替换成SafeRunRootCmd接口，此问题即可解决
>
>

我已经检查过imgui的代码了，似乎所有需要运行命令的地方均未使用su，且调用方法为popen，与你的run_root_cmd函数一致。后来我们发现是由于seLinux导致的（所以这个问题是由于seLinux没过全导致的），只需要临时关闭后，即可正常运行imgui程序。但是即使运行成功了也不能再打开seLinux，因为会导致imgui很卡。如果不打开seLinux将会导致隐藏root失去意义（seLinux会被检测）。
另外，我还发现skroot无法调用完美root所能调用到的函数，比如setuid函数。这是由于seccomp的相关权限字段没在内核中设置。

## 回复 by abcz316 (#36)

*2023-4-1 09:06*

请检查所处进程是否已调用get_root，只有已调用get_root的进程具有越过SELinux的权限。关于seccomp字段的设置，等待良辰吉日我会开放源代码

## 回复 by abcz316 (#37)

*2023-4-1 09:06*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  罐罐灬](https://bbs.kanxue.com/user-975795.htm)
>
>  我已经检查过imgui的代码了，似乎所有需要运行命令的地方均未使用su，且调用方法为popen，与你的run_root_cmd函数一致。后来我们发现是由于seLinux导致的（所以这个问题是由于seL ...
>
>

楼上

## 回复 by abcz316 (#38)

*2023-4-1 09:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  罐罐灬](https://bbs.kanxue.com/user-975795.htm)
>
>  我已经检查过imgui的代码了，似乎所有需要运行命令的地方均未使用su，且调用方法为popen，与你的run_root_cmd函数一致。后来我们发现是由于seLinux导致的（所以这个问题是由于seL ...
>
>

您可以注入init进程启动su daemon，进行su版本的通信，如果有必要，我会在今天或者晚些时候开放第二个具有su daemon版本的源代码

## 回复 by 罐罐灬 (#39)

*2023-4-1 09:43*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  您可以注入init进程启动su daemon，进行su版本的通信，如果有必要，我会在今天或者晚些时候开放第二个具有su daemon版本的源代码
>
>

设置seccomp相关的字段，我尝试过，直接设置手机会重启。据我所知，需要先设置thread_inof结构体中的字段才行，但是thread_inof结构体的地址是需要由current_thread_info()获取的，current_thread_info()函数被内联了。我找了一些内联了current_thread_info函数的地方也没看明白。你确定能搞定吗？

## 回复 by 罐罐灬 (#40)

*2023-4-1 09:57*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  您可以注入init进程启动su daemon，进行su版本的通信，如果有必要，我会在今天或者晚些时候开放第二个具有su daemon版本的源代码
>
>

注入init进程启动su？没太明白，跟面具一样的授权方式？

## 回复 by abcz316 (#41)

*2023-4-1 10:41*

您无需担心，我在两年前已经将此源代码写好，我认为这个东西非常简单，因为我运用了许多技巧，并且我将在良辰吉日进行公开

## 回复 by abcz316 (#42)

*2023-4-1 10:41*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  罐罐灬](https://bbs.kanxue.com/user-975795.htm)
>
>  设置seccomp相关的字段，我尝试过，直接设置手机会重启。据我所知，需要先设置thread_inof结构体中的字段才行，但是thread_inof结构体的地址是需要由current_thread_i ...

楼上。在内核中获取current_thread_info并不是一件很难的事情，如果您非常想知道如何获取current_thread_info，我建议你能仔细阅读我的patch_kernel_root源代码，同时配合arm64芯片手册，您将会自己思考出答案。或稍等我调个良辰吉日，我将会与另外一个重磅功能"内核无痕注入"，一同发布

## 回复 by 罐罐灬 (#43)

*2023-4-1 11:35*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  您无需担心，我在两年前已经将此源代码写好，我认为这个东西非常简单，因为我运用了许多技巧，并且我将在良辰吉日进行公开
>
>

好的，期待中

## 回复 by abcz316 (#44)

*2023-4-1 11:41*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  韩七鹿](https://bbs.kanxue.com/user-975796.htm)
>
>  提升adb为root权限没有开源啊大佬
>
>

这个功能属于拓展功能，并且我认为这个功能没有存在的必要，所以我进行了删除，但这并不影响手机获取root权限。如果你喜欢这个功能，你可以自己添加

## 回复 by 霸业 (#45)

*2023-4-1 15:22*

看到您hook代码空间在默认放在文件offset 0x300，我的内核这块数据有引用patch后会crash，我该怎么找到内核空间且可执行的地址呢：）

## 回复 by abcz316 (#46)

*2023-4-1 16:38*

>
> [霸业](https://bbs.kanxue.com/user-796003.htm)
>
>  看到您hook代码空间在默认放在文件offset 0x300，我的内核这块数据有引用patch后会crash，我该怎么找到内核空间且可执行的地址呢：）
>
>

那实在太多，如kernel_painc

## 回复 by 霸业 (#47)

*2023-4-1 21:57*

多谢指点，我在想还缺乏kprobe那样的功能
如果呀，找到kallsyms_lookup_name,kmalloc，更改执行权限的函数，往里面塞一个js引擎，实现内核版本的frida就吊炸天了 hhhh

## 回复 by abcz316 (#48)

*2023-4-3 15:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  罐罐灬](https://bbs.kanxue.com/user-975795.htm)
>
>  好的，期待中
>
>

看下42楼；我在patch_kernel_root里面已经教会你如何获取自身进程句柄了，甚至你只需稍做修改就能把addr_limit也一起修改了，这些并不是一件很难的事情

## 回复 by 不吃早饭 (#49)

*2023-4-3 17:45*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  罐罐灬](https://bbs.kanxue.com/user-975795.htm)
>
>  注入init进程启动su？没太明白，跟面具一样的授权方式？
>
>

seccomp是zygote设置的，你直接注入init进程来fork出su daemon自然就可以绕过seccomp的限制了

## 回复 by 罐罐灬 (#50)

*2023-4-4 00:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  不吃早饭](https://bbs.kanxue.com/user-825489.htm)
>
>  seccomp是zygote设置的，你直接注入init进程来fork出su daemon自然就可以绕过seccomp的限制了
>
>

那就跟面具一样的权限来源了，就不是kernrl root了

## 回复 by 不吃早饭 (#51)

*2023-4-4 03:27*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  罐罐灬](https://bbs.kanxue.com/user-975795.htm)
>
>  那就跟面具一样的权限来源了，就不是kernrl root了
>
>

如果你只是想让你的app能直接获得root权限，那你大可以注入zygote，拦截setuid等调用，屏蔽掉降权操作，一个magisk模块就能做到。su的目的是隐蔽性，不是让你的app直接获得root权限

## 回复 by Interupt (#52)

*2023-4-5 15:31*

牛逼![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by bullyxy (#53)

*2023-4-6 20:01*

![image](https://bbs.kanxue.com/upload/attach/202304/790572_EM8EWJEFAAY2NH6.jpg)

想问下大佬为啥从 boot 中提取出来的 kernel 是这样的，ida 也没法解析？

## 回复 by mb_iyfbfczl (#54)

*2023-4-7 01:22*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>
>
>
>
>
>
>  罐罐灬
>
>  设置seccomp相关的字段，我尝试过，直接设置手机会重启。据我所知，需要先设置thread_inof结构体中的字段才行，但是thread ...
>
>

大佬你有项目吗？

## 回复 by abcz316 (#55)

*2023-4-7 12:56*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  罐罐灬](https://bbs.kanxue.com/user-975795.htm)
>
>  好的，期待中
>
>

已更新全部find工具及seccomp的修改

## 回复 by yu1975 (#56)

*2023-4-9 01:55*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  已更新全部find工具及seccomp的修改
>
>

感谢，威武。

## 回复 by ssarg (#57)

*2023-4-14 11:22*

终于编译成功，但是在荣耀70手机上不能root啊，使用方法不对？我是依次点了左侧前三个按钮，见下图，请楼主看看，谢谢！

另外，左侧功能了少了三个跟原图比较？

![image](https://bbs.kanxue.com/upload/attach/202304/14494_P5GMN4PTN4UB2NE.jpg)

## 回复 by abcz316 (#58)

*2023-4-14 18:12*

恭喜你成功编译出APK，但你只完成了其中的步骤的50%

## 回复 by ssarg (#59)

*2023-4-15 13:59*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  恭喜你成功编译出APK，但你只完成了其中的步骤的50%

谢谢楼主分享，把流程5个步骤都走一遍对吧？内核文件具体指哪个？没root前，如何拿到内核文件呢？

## 回复 by abcz316 (#60)

*2023-4-15 15:08*

你可以参考下面具在没有root的情况下如何拿到内核文件

## 回复 by abcz316 (#61)

*2023-4-15 15:09*

比如询问厂商

## 回复 by ssarg (#62)

*2023-4-15 17:30*

新手，请多多指教。我以为是自动工具。

## 回复 by 凯文米特尼克 (#63)

*2023-4-15 23:10*

![image](https://bbs.kanxue.com/view/img/face/85.gif)

## 回复 by mb_rkvnduhc (#64)

*2023-4-17 01:03*

就是大佬我目前遇到的问题就是部署获取root然后删掉部署或者不删后台运行过不到10分钟超级权限就掉了，后台程序都还在没有被杀手机红米k40如何让他在后台超级权限不会掉

## 回复 by yu1975 (#65)

*2023-4-17 03:31*

>
> [bullyxy](https://bbs.kanxue.com/user-790572.htm)
>
>  想问下大佬为啥从 boot 中提取出来的 kernel 是这样的，ida 也没法解析？
>
>

这是lz4压缩的，需要安装lz4解压。解压后就能识别了。

## 回复 by .雨声 (#66)

*2023-4-20 10:08*

大佬我感觉已经完成这几个步骤的大部分，现在我顺利拿到两个地址和两个偏移值，并拿到密钥，写入后重新打包并填充了镜像，将PermissionManager安装在手机上，刷入image-new.img后输入密钥后还是没有用![image](https://bbs.kanxue.com/view/img/face/9.gif)

![image](https://bbs.kanxue.com/upload/attach/202304/952335_ENWH7QZ4WM6QA5W.jpg)

![image](https://bbs.kanxue.com/upload/attach/202304/952335_XAWYB259FAW662V.jpg)

![image](https://bbs.kanxue.com/upload/attach/202304/952335_YUZ5EPQFKCXXZXT.jpg)

## 回复 by ssarg (#67)

*2023-4-20 10:50*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  .雨声](https://bbs.kanxue.com/user-952335.htm)
>
>  大佬我感觉已经完成这几个步骤的大部分（纯小白生啃中），但是我在patch_kernel_root生成密钥时会爆出immediate out of range at operand 1的错误，但貌似不影 ...
>
>

如果楼主能将流程里前四步自动合并成一个那就更方便了，要想真机测试，只能先用以前淘汰的机子测试了，砖了也无所谓了。

## 回复 by mb_jbxawygx (#68)

*2023-4-21 23:29*

大佬我这里碰到了一个问题，ida逆向函数加载完成后，avc_denied，do_execve，revert_creds等函数不存在，而且find工具所获得的入口地址也无法跳转，这该如何寻找以上这些值

## 回复 by method (#69)

*2023-4-24 17:00*

老zhang？

## 回复 by 三草儿 (#70)

*2023-4-26 21:24*

能不能提供linux 的编译环境呀,没用windows很多年了 。。su 下面的都是vc的工程配置，还有find,patch 也都是exe。你项目介绍里面不是说，linux 多么讨你新欢吗, 怎么自己都用windows?![image](https://bbs.kanxue.com/view/img/face/5.gif)不是为了怼你，是真的难受，只有manager可以编译。这个工程和magisk 还差很多呀。难受。。。

## 回复 by 黑洛 (#71)

*2023-4-27 07:24*

6

## 回复 by abcz316 (#72)

*2023-4-27 11:14*

>
> [三草儿](https://bbs.kanxue.com/user-469657.htm)
>
>  能不能提供linux 的编译环境呀,没用windows很多年了 。。su 下面的都是vc的工程配置，还有find,patch 也都是exe。你项目 ...

已经附有.cpp源代码在工程目录里，想要哪个平台可自行编译。例如su工程，里面有jni文件夹，使用ndk即可正常编译；.exe与.vcpj是方便给网友们用的，对于技术人员我认为只需要阅读patch_kernel_root的源代码就已经能掌握所有精髓了，可自行开发，并不需要编译（此项目）。而且，我这个项目并不关心对Linux内核处于新手阶段的人，我认为这些都是作为Linux内核开发人员必须要掌握的基本功，不需要写解释，更也不需要做使用说明，因为我认为非常简单；比如1+1＝2，这不需要解释，因为它非常简单。

## 回复 by secjoy (#73)

*2023-4-28 16:34*

android 8.1 boot.img 拖转后显示text offset empty

## 回复 by bullyxy (#74)

*2023-5-4 23:40*

>
> [yu1975](https://bbs.kanxue.com/user-861808.htm)
>
>  这是lz4压缩的，需要安装lz4解压。解压后就能识别了。
>
>

是0到0x10b73这一段吗？

## 回复 by mb_ckfmrnqa (#75)

*2023-5-5 14:39*

大佬能不能给个例子怎么从ida查看内核文件f5找到对应的结构体，球球了

## 回复 by ssarg (#76)

*2023-5-5 15:27*

楼主能否就“使用流程”再详细写一篇图文并茂的使用说明？谢谢。自己找不到![image](https://bbs.kanxue.com/view/img/face/85.gif)

## 回复 by ele7enxxh (#77)

*2023-5-5 15:48*

起这么高的调，那么这玩意和magisk有什么本质的区别吗？？有什么场景是magisk做不到而这个工具能做到的吗？？

## 回复 by yu1975 (#78)

*2023-5-5 19:46*

楼上，https://github.com/lz4/lz4,去下载个lz4 ，lz4 -d kennel就能得到解压后的kennel了。不过我3.18内核，成功找到几个参数也没成功，卡logo无限循环。可能版本太低了。

## 回复 by mb_irpfojzi (#79)

*2023-5-6 12:12*

安装部署SU报错：install su err:-502, su_hide_full_path，是哪一步出错了吗

## 回复 by abcz316 (#80)

*2023-5-8 12:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  ele7enxxh](https://bbs.kanxue.com/user-722289.htm)
>
>  起这么高的调，那么这玩意和magisk有什么本质的区别吗？？有什么场景是magisk做不到而这个工具能做到的吗？？
>
>

那你得问他们了，1.5k的stars，他们用在什么地方，我也不知道，你可以猜猜看

## 回复 by abcz316 (#81)

*2023-5-8 12:55*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  ssarg](https://bbs.kanxue.com/user-14494.htm)
>
>  楼主能否就“使用流程”再详细写一篇图文并茂的使用说明？谢谢。自己找不到[em_85]
>
>

B站有其他小伙伴录制了视频

## 回复 by ele7enxxh (#82)

*2023-5-8 18:36*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  那你得问他们了，1.5k的stars，他们用在什么地方，我也不知道，你可以猜猜看
>
>

别扯这些，能不能root没有解锁BootLoader的手机？还是说唯一的不同就是你能隐藏root，然后让那些搞黑灰产的用？

## 回复 by abcz316 (#83)

*2023-5-9 09:42*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  ele7enxxh](https://bbs.kanxue.com/user-722289.htm)
>
>  别扯这些，能不能root没有解锁BootLoader的手机？还是说唯一的不同就是你能隐藏root，然后让那些搞黑灰产的用？

可以，例如红魔不需要解锁BL就能刷入，小米则需要9008强刷，功能是隐藏root，面具经过改造后也能达成隐藏root的目的，但SKRoot是从出生的一刻起，就具备隐藏的功能，网友们喜欢用哪个任凭他们自主选择，且他们用在具体到每个是什么项目，我无从知晓，也并不关心

## 回复 by 微微T52G25 (#84)

*2023-5-10 09:06*

这个专业

## 回复 by 微微T52G25 (#85)

*2023-5-10 09:07*

大佬，工具文件麻烦上传下呗。谢谢

## 回复 by mb_qrrqsddf (#86)

*2023-5-10 13:40*

![image](https://bbs.kanxue.com/view/img/face/63.gif)交流下

## 回复 by mb_btqgfrae (#87)

*2023-5-12 22:46*

do_execve 没定位到 怎么办大佬

## 回复 by ssarg (#88)

*2023-5-13 11:03*

请楼主帮忙看看这个附件的kernel文件，自己试了多次未成功，能否帮找一下前四步的值，谢谢。

链接: https://pan.baidu.com/s/1O3xhCIhukHc8jcwyg4nTpw?pwd=32nh

提取码: 32nh

## 回复 by mmp666 (#89)

*2023-5-16 12:03*

像kernelSU一样支持模块就好了

## 回复 by abcz316 (#90)

*2023-5-16 15:43*

>
> [mmp666](https://bbs.kanxue.com/user-929233.htm)
>
>  像kernelSU一样支持模块就好了
>
>

未来会开放一个隐藏Bootloader的模块

## 回复 by Concord (#91)

*2023-5-18 17:24*

我对红魔、小米能刷的这个地方有问题，在没有解锁的前提下，你都改boot分区了，系统还能起来吗？安全启动做的有问题吧 - -。

## 回复 by mb_brzwurxh (#92)

*2023-6-1 17:46*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  未来会开放一个隐藏Bootloader的模块

大佬，还是希望出一篇图文教程！B站的有点太快和粗糙了！感谢大佬分享

## 回复 by mb_fyshftge (#93)

*2023-6-3 11:04*

小白一个！大佬有没有直接能安装的工具！求一个

## 回复 by 韩七鹿 (#94)

*2023-6-13 20:50*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  未来会开放一个隐藏Bootloader的模块
>
>

大佬啥时候发布模块啊

## 回复 by abcz316 (#95)

*2023-6-14 13:44*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  韩七鹿](https://bbs.kanxue.com/user-975796.htm)
>
>  大佬啥时候发布模块啊
>
>

当github stars达到2k的时候

## 回复 by ID蝴蝶 (#96)

*2023-7-10 11:58*

大佬牛皮

## 回复 by ILA1992 (#97)

*2023-8-6 16:08*

大佬，你知不知道高风险和行为检测的原理，听说和环境有关，内核可以过

## 回复 by miyuecao (#98)

*2023-8-14 17:14*

看起来很厉害的样子![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by mb_ckpefbiq (#99)

*2023-8-25 16:23*

内核5.15的无法开机，大佬

## 回复 by abcz316 (#100)

*2023-8-26 13:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ckpefbiq](https://bbs.kanxue.com/user-978852.htm)
>
>  内核5.15的无法开机，大佬
>
>

内核5.15无法开机问题，只要将开头的300换下就可以了，我晚点提交一下代码

## 回复 by mb_ckpefbiq (#101)

*2023-8-27 11:24*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  内核5.15无法开机问题，只要将开头的300换下就可以了，我晚点提交一下代码
>
>

怎么确定空闲代码的位置，尝试自己改了下还是不开机，等待大哥操作....

## 回复 by z笑的样子 (#102)

*2023-9-7 18:31*

6666666666666666666

## 回复 by mb_sdxbepyu (#103)

*2023-9-8 04:45*

成功了， 但似乎一些app没能获取到root

## 回复 by 淡然他徒弟 (#104)

*2023-9-9 14:31*

mark

## 回复 by 韩七鹿 (#105)

*2023-9-11 06:47*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  未来会开放一个隐藏Bootloader的模块
>
>

什么时候开放模块大佬

## 回复 by Elice (#106)

*2023-11-13 10:37*

Star 2K了 期待大佬的模块

## 回复 by 韩七鹿 (#107)

*2023-12-7 22:04*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  当github stars达到2k的时候
>
>

2k了大佬什么时候开放

## 回复 by 晏子的土地 (#108)

*2024-1-9 15:19*

请问一下大佬，现在去年出的[APatch](https://github.com/bmax121/APatch)和您的SKRoot有什么关联性吗？还是说，只是使用了类似的技术？

## 回复 by dream的梦 (#109)

*2024-5-2 21:13*

目前5.15还是刷不进去但是以下的机型貌似都能刷不知道那个0x300修复了没有,但是尝试了一下5.10也是没有什么问题等待作者回复

## 回复 by abcz316 (#110)

*2024-5-9 01:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_fdxbgmiv](https://bbs.kanxue.com/user-978684.htm)
>
>  目前5.15还是刷不进去但是以下的机型貌似都能刷不知道那个0x300修复了没有,但是尝试了一下5.10也是没有什么问题等待作者回复
>
>

谢谢反馈，已经修复了

## 回复 by abcz316 (#111)

*2024-5-9 01:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  MaouAce](https://bbs.kanxue.com/user-944779.htm)
>
>  大佬能不能教一下怎么用IDA伪代码翻译找思路里 1. 2. 的值 ，android 12 不管 boot_a 还是 boot_b kernel 分离完 用 IDA 使用 droiding 脚本都打不开 ...
>
>

已经全面自动化了

## 回复 by abcz316 (#112)

*2024-5-9 01:42*

谢谢反馈，已经修复了

## 回复 by dream的梦 (#113)

*2024-5-11 04:08*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  谢谢反馈，已经修复了
>
>

感谢修复

## 回复 by dream的梦 (#114)

*2024-5-11 04:39*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  谢谢反馈，已经修复了
>
>

新版本的话也会有一些bug如果只是修复了那个问题的话
会更好因为手动的可能会比自动寻找很好内核有各种奇奇怪怪的
我的建议是继续采用旧版本方案自行寻找

## 回复 by dream的梦 (#115)

*2024-5-11 05:04*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  谢谢反馈，已经修复了
>
>

## 回复 by dream的梦 (#116)

*2024-5-11 05:05*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  谢谢反馈，已经修复了
>
>

![image](https://bbs.kanxue.com/upload/attach/202405/978684_UHT4PY7TQ3V9G5U.webp)归根结底还是5.15.148 || 5.15.94 出了问题5.10还是没问题hhh

## 回复 by dream的梦 (#117)

*2024-5-14 16:21*

感谢大佬修复目前5.15已经正常

## 回复 by 燃烧的羽翼 (#118)

*2024-7-11 21:03*

大佬您好，请问提到的隐藏引导解锁模块在哪可以下载![image](https://bbs.kanxue.com/view/img/face/1.gif)

## 回复 by mb_rpcivqkt (#119)

*2024-9-5 10:39*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>
>
>
>
>
>
>  ele7enxxh
>
>  别扯这些，能不能root没有解锁BootLoader的手机？还是说唯一的不同就是你能隐藏root，然后让那些搞黑灰产的用？ ...
>
>

红魔有思路吗大佬，求指条明路

## 回复 by mb_kilcggbx (#120)

*2024-9-14 16:49*

大佬隐藏bl模块啥时候发布啊

## 回复 by 养只猫不好么 (#121)

*2024-9-14 17:30*

感谢分享

## 回复 by 改了一下昵称 (#122)

*2024-9-17 02:03*

期待中

## 回复 by 改了一下昵称 (#123)

*2024-9-18 20:03*

有办法不依赖jni环境吗

## 回复 by mb_rpcivqkt (#124)

*2024-9-26 00:08*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>
>
>
>
>
>
>  ele7enxxh
>
>  别扯这些，能不能root没有解锁BootLoader的手机？还是说唯一的不同就是你能隐藏root，然后让那些搞黑灰产的用？ ...
>
>

红魔可以不解锁刷skroot？？

## 回复 by mb_kilcggbx (#125)

*2024-9-29 00:25*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rpcivqkt](https://bbs.kanxue.com/user-1004375.htm)
>
>  红魔可以不解锁刷skroot？？
>
>

听说有的机型可以

## 回复 by mb_rpcivqkt (#126)

*2024-9-29 14:50*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_kilcggbx](https://bbs.kanxue.com/user-1007007.htm)
>
>  听说有的机型可以
>
>

不知道有哪些机型可以吗

## 回复 by mb_gqzjdiys (#127)

*2024-11-6 11:10*

模块呢

## 回复 by mb_ldbucrik (#128)

*2024-11-22 19:42*

请问pixel1支持了吗

## 回复 by cs1001 (#129)

*2024-11-25 09:05*

提示failed...

## 回复 by mb_powghrzn (#130)

*2025-1-10 16:10*

非常棒的项目，但是不支持6.1内核吗

## 回复 by mb_kilcggbx (#131)

*2025-3-25 01:19*

小米 红魔等骁龙845老机器可以，不过没啥子意义

## 回复 by abcz316 (#132)

*2025-5-8 15:14*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_powghrzn](https://bbs.kanxue.com/user-990949.htm)
>
>  非常棒的项目，但是不支持6.1内核吗
>
>

已经支持上了，谢谢提醒

## 回复 by abcz316 (#133)

*2025-5-8 15:15*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  ssarg](https://bbs.kanxue.com/user-14494.htm)
>
>  楼主能否就“使用流程”再详细写一篇图文并茂的使用说明？谢谢。自己找不到[em_85]
>
>

已经升级到一键自动化了，谢谢反馈

## 回复 by wx_ln (#134)

*2025-5-15 04:27*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  已经升级到一键自动化了，谢谢反馈
>
>

作者啥时候更新隐藏BL啊啊

## 回复 by mb_yxdriklg (#135)

*2025-5-16 23:14*

大佬隐藏bl模块什么时候发啊？

## 回复 by QQ280712472 (#136)

*2025-9-7 23:44*

skroot pro什么时间上线

## 回复 by QQ765746002 (#137)

*2025-9-30 19:35*

版主大佬应该弄个群之类的 发布个小白教程 这个软件对我们小白不是 太友好，我在咸鱼找人教我都没有！弄个群发布在仓库吧。
