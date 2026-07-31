---
title: '[原创]一步到位动态调试AliCrackme的so文件'
url: https://bbs.kanxue.com/thread-277806.htm
tid: 277806
author: 杰孑
date: '2023-06-28'
tags: [Android安全, 原创, 基础理论, 逆向分析]
crawled_at: '2026-07-31T14:42:21+08:00'
replies: 6
---

# [安卓逆向]一步到位动态调试AliCrackme的so文件

## 写在前面

**续写文章：** [[原创]超级详细的实战分析一个Crackme的过程](https://bbs.kanxue.com/thread-263810.htm)

>
> 之前分析的这个AliCrackme后总结过程有些繁琐，需要几次替换APK内文件及签名和不断需要从头重复调试才可以，这次直接在完全不动原始APK包的情况下，通过动态调试JNI_OnLoad及目标函数，直接一步到位过反调试及分析最后出Flag。
>
>
>

## 动态调试

>
> 真机动态调试前一定要给APP加上可调试权限，`android:debuggable="true"`，[Android修改ro.debuggable的四种方法](https://amarao.blog.csdn.net/article/details/111355867)，推荐以下几种可长期使用的方法：
>
>
>

### 方法一(重启失效)：

已 root 的手机修改手机系统的全局debuggable标志值为 true（即将/default.prop中的ro.debuggable的默认字段值0修改为 1），这样此手机上各种AP都可以调试了，**若手机重启后需要再次进行修改操作**。修改 ro.debuggable 的步骤：

| 1234567891011 | `连接Google Nexus 真机：adb devices``检查Google Nexus 架构：adb shell getprop ro.product.cpu.abi``下载架构相同的mprop：https:``//github``.com``/wpvsyou/mprop``将文件push 进手机的指定目录下：adb push mprop` `/data/local/tmp``进入手机端命令：adb shell``切换获取手机的root权限：``su``查找push的文件是否在手机中：``cd` `/data/local/tmp/``查看路径下的文件以及权限：``ls` `-l``拥有root权限更改文件的权限为777：``chmod` `777 mprop``修改 ro.debuggable的值为 1：.``/mprop` `ro.debuggable 1``获取 ro.debuggable值：getprop ro.debuggable` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_JWHZ3DYXMKPMYGB.png)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_GP52SQXVBS8R6MJ.png)

### 方法二(永久有效)：

前提：手机需要有magisk环境，可通过安装`MagiskHide Props Config` 模块修改(永久有效)

开源地址： <https://github.com/Magisk-Modules-Repo> 请下载使用 MagiskHide Props Config5.3.6版本：<https://github.com/Magisk-Modules-Repo/MagiskHidePropsConf/releases/tag/v5.3.6>

1.通过命令推送到手机 `adb push MagiskHidePropsConf-v5.3.6.zip /sdcard/` 从Magisk→模块→本地安装→选择压缩包安装即可！
2.重启手机，手机进入adb shell模式
3.执行props
4.选择需要操作的选项，首先选择4 - Edit MagiskHide props 之后选择1- ro.debuggable
5.最后查看`getprop ro.debuggable` 重启手机后再次查看`getprop ro.debuggable`查看是否仍然为1。
接下来先需要配置IDA调试的一些环境，步骤如下：

| 12345678910 | `连接Google Nexus 真机：adb devices``检查Google Nexus 架构：adb shell getprop ro.product.cpu.abi``将文件push 进手机的指定目录下：adb push android_server` `/data/local/tmp/``进入手机端命令：adb shell``切换获取手机的root权限：``su``查找push的文件是否在手机中：``cd` `/data/local/tmp/``查看路径下的文件以及权限：``ls` `-l``拥有root权限更改文件的权限为777：``chmod` `777 android_server``在手机中启动运行该文件：.``/android_server``windows运行 端口转发到PC：adb forward tcp:23946 tcp:23946` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_3AGCMQQQYWHMSNA.png)
再开启一个 命令行 做一下端口的转发，如下图所示：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_56JU355STCT6U2M.png)
全部执行完毕之后，可以看到正在监听这个端口，这时候我们打开 IDA 并且点击GO 然后按照下图选择所使用的
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_DRTH3KHXJ8K68SX.png)
并输入 127.0.0.1 后面的端口是默认的，上面的命令也在监听这个端口。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_NB2NY2CKQ4RKSDS.png)
找到要动态调试的软件的包名，直接选中，点击 ok 打开即可！
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_JK8NJFSRYBP8N9F.png)
打开之后，直接使用下图的方式，或者 快捷键 Ctrl+s 找到到要调试的libcrackme.so文件 带x权限的文件。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_5SDNVWFXPR9RWZV.png)
在所有的so文件中直接使用快捷键Ctrl+f 搜索，并找到 Start地址先执行且有 X(可执行权限) 的 选中点击OK进入，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_YSZXTMTZRRZ8MKM.png)
打开so文件之后我们要定位到要调试函数`Java_com_yaotong_crackme_MainActivity_securityCheck`的一个内存的**绝对地址=so文件的基地址+函数的偏移量**
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_A66RDUN23FK3HNP.png)
经计算可知，函数的绝对地址就是`F49591A8`在IDA中 使用快捷键G跳转到地址的位置，也就是要调试的函数位置
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_CGQ87DJS7KCNZU4.png)
找到函数名之后，鼠标右键 选择 Add breakpoint 或者 直接使用快捷键F2打断点，然后让程序恢复执行，使用快捷键F8往下走。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_W7EBMJGRGENB4H9.png)
点击 F8 给so文件中已打断点的函数单步调试，结果直接就退出或出现错误弹窗等等！如下图所示：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_24DH6WARKT9WB8J.png)
证明软件有反调试的机制，先看一下软件是通过何种方式反调试的，又是如何检测被调试的呢？

### 检测是否被调试

利用Linux系统 ptrace 来实现，当应用被调试时应用内存里的TracerPid字段就不为0，只要是不为0的时候，就会直接的退出程序达到反调试的目的。

接下来进入设备查看一下ptrace字段：

| 1234 | `进入设备：adb shell``获取Root权限：``su``获得APP的进程ID：``ps` `\|` `grep` `软件的包名``查看进程的信息及TracerPid值：``cat`  `/proc/``进程ID``/status` `\|` `grep` `TracerPid` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_UR333Y34X5WSNTC.png)
知道了软件有反调试之后，接下来就需要对其**反反调试**了。

## 反反调试

**如何反反调试**： 程序的so文件在加载阶段会先执行JNI_OnLoad，之后就不再执行，在程序的so文件加载阶段才能给JNI_OnLoad打断点调试即可！

| 123 | `//``调试APP挂在加载界面``adb shell am start -D -n 包名/.类名``adb shell am start -D -n com.yaotong.crackme/.MainActivity` |
|-|-|

用调试模式启动APP，APP此时会挂在启动界面，现在并没有开始加载so文件。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_7SHK3ZTX73CRB5F.png)
打开 IDA 并动态调试上面挂载的程序，进入之后点击Debugger->Debugger options... 选项如下图：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_8ZNUZEVJZW2AQBY.png)
勾选这两项Suspend on thread start/exit、Suspend on library load/unload，之后ok，**之后点击下图左上角的运行符号**，让它运行起来。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_HPZRKPBECGW8WQM.png)
然后让APP也运行起来，用过下面的这些命令运行APP,即可

| 12345 | `进入设备：adb shell``获取Root权限：``su``获得APP的进程ID：``ps` `\|` `grep` `com.yaotong.crackme``监听进程的ID：adb forward tcp:8700 jdwp:4495（4495为上面获得的APP进程ID）``运行进程：jdb -connect com.sun.jdi.SocketAttach:``hostname``=127.0.0.1,port=8700` |
|-|-|

获取APP的进程的ID以及再开启一个命令行，直接做端口的监听转发，并直接的运行进程，如下图：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_4HTNFGV6R6TG97M.png)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_3T6QVHBMZ9BV3Z9.png)
`注意：`卡在`运行进程`这一步的不出现上图的`正在初始化jdb...` ，应该是你漏掉了一个步骤，我就是因为截图过之后忘记了在IDA 动态调试的时候，`忘记点击了一下IDA左上角的运行符号` ，而导致的一致不出来`正在初始化jdb...` 的情况，出现初始化后，APP处于这个没有控件的界面，此时的APP并没有完全的运行起来,只是挂在这里。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_Q8JW6T3GVT8PNFY.png)
然后我们回到 IDA 的动态调试 找到要调试的crackme.so 文件，按Ctrl+s找so文件，之后按Ctrl+f搜索crackme，`如果没有就点击左上角的运行` 运行一步继续操作，直到可以在所有的so文件中搜索到crackme.so文件，并且找到可执行的X权限的文件。如下图：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_JTT8Z377NWGXXJX.png)
然后我们要进入 JNI_ONLoad ,接下来算`绝对地址=执行so文件的基地址+函数的偏移量` 最终如下图所示：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_GCXFWMKAUMVA3JP.png)
最终的计算结果如下图所示：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_DNRTRF7N3PYBUAH.png)
跳转到 JNI_ONLoad 里去了，先结合静态分析看一下这个文件流程图的大致逻辑，然后在动态调试里给 JNI_ONLoad 打断点，点击IDA左上角的运行恢复程序的运行，并一直F8调试往下走，如下图所示：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_KTZ6UGTAJPSKDCV.png)
一直到BLX R7的位置跳了出去，很可疑的位置需要重点注意，尝试修补so文件的这个位置，看一下，如下图所示：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_B9RHVXVR3ERHPT7.png)
然后在IDA 动态调试中点击`BLX`，找到导航栏的`Edit→Patch program→Changer byte`。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_UYF3PBY3R6ABUZW.png)
把 `3F FF 2F E1`修改为`00 00 00 00`，然后直接ok即可！
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_BN46EBVNGK2ZSCV.png)
修改了关于程序反调试的TracerPid 指令`37 FF 2F E1` 改为 `00 00 00 00` 就不会再有反调试的防护机制了，然后找到`JNI_OnLoad`下断点的地方并点击F2取消之前下的断点，在IDA导航栏中点击`Debugger->Debugger options...` 并取消勾选下图两项：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_JTZM3YFEWFS42PS.png)
接下来就是再次动态调试`Java_com_yaotong_crackme_MainActivity_securityCheck`

## 再动态调试

有了上次动态调试的经验，很快通过Ctrl+s和Ctrl+f找到了`libcrackme.so`的基地址，**通过绝对地址=so文件的基地址+函数的偏移量**定位到要调试的函数`Java_com_yaotong_crackme_MainActivity_securityCheck`所在的位置，如下图所示：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_B7RW35B99RVCC4V.png)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_K9HB44SEZ2UNY74.png)
打断点后让程序恢复执行，让手机进入正常的界面并输入`yimingrj`点击`输入密码`将其存到寄存器，点击F8会在下断处断下，一直F8向下走找到有跳转的地方，鼠标查看寄存器的值：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_X8Y7YXJCZDP2272.png)
之后我们看一下R3的值，直接使用快捷键F5看一下伪C代码，又根据之前的静态调试分析可知v6就是真实密码，最后分析出了这个软件**真实的进入密码为：aiyou,bucuoo(哎呦，不错哦)！**
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_S6HET83T4A7R5FC.png)
输入密码在程序中验证后进入软件成功！这个软件的密码分析到这里**这部分**就结束了。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/909733_BKUM3Y3NKWNRG2C.png)

## 最后总结

这次调试用了更便捷的方式，不用很多次反编译修改和回编译打包每次再重头再来的操作了。
处在不同阶段来看待相同问题，真的会有不一样感觉，会有不同且更加简单方便的处理方法。

---

# 回复

## 回复 by 教教我吧~ (#2)

*2023-6-30 11:37*

讨论一下，请问：”一直到BLX R7的位置跳了出去，很可疑的位置需要重点注意，尝试修补so文件的这个位置”，为什么挑选BLX R7的位置，是根据什么呀？（因为不清楚此处BLX R7功能，如果此处是程序自带的对so代码解密函数，那么直接NOP会造成影响的呀），请解惑一下，谢谢

## 回复 by 杰孑 (#3)

*2023-6-30 16:17*

>
> [教教我吧~](https://bbs.kanxue.com/user-940077.htm)
>
>  讨论一下，请问：”一直到BLX R7的位置跳了出去，很可疑的位置需要重点注意，尝试修补so文件的这个位置”，为什么挑选BLX R7的位置，是根据什么呀？（因为不清楚此处BLX R7功能，如果此处是程序 ...
>
>

根据程序的反调试情景来的。可理解成是指令集跳转到指令中反调试的位置，NOP掉可让程序不走反调试。

## 回复 by Ruinv6 (#4)

*2023-7-1 18:29*

真的是非常详细

## 回复 by 秋狝 (#5)

*2023-7-1 23:45*

感谢分享

## 回复 by 我想你了 (#6)

*2023-7-3 22:30*

感谢分享

## 回复 by 教教我吧~ (#7)

*2023-7-4 20:50*

>
> [杰孑](https://bbs.kanxue.com/user-909733.htm)
>
>  根据程序的反调试情景来的。可理解成是指令集跳转到指令中反调试的位置，NOP掉可让程序不走反调试。
>
>

谢谢
