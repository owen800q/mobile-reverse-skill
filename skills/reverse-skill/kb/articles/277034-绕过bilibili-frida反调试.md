---
title: '[原创]绕过bilibili frida反调试'
url: https://bbs.kanxue.com/thread-277034.htm
tid: 277034
author: 马到成功*
date: '2023-04-29'
tags: [Android安全, 原创, 逆向分析, NDK分析, HOOK注入]
crawled_at: '2026-07-31T14:49:26+08:00'
replies: 81
---

原创文章，首发至博客http://t.csdn.cn/Pd9aL

 文章仅供思路参考，请勿用作非法攻击

### 环境

- bilibili 7.26.1
- arm
- frida 15.2.2(去除特征版本)
- pixel 6 android 12

### 正文

使用frida以spawn模式启动应用，frida进程直接被杀掉了

  ![image](https://bbs.kanxue.com/upload/attach/202304/929475_PFPSN9V6JPNZPU9.jpg)

 我需要知道是那个so在检测frida，可以hook dlopen看一下so的加载流程

| 12345678910111213 | `function hook_dlopen() {``Interceptor.attach(Module.findExportByName(null,` `"android_dlopen_ext"``),``{``onEnter: function (args) {``var pathptr` `=` `args[``0``];``if` `(pathptr !``=``=` `undefined && pathptr !``=` `null) {``var path` `=` `ptr(pathptr).readCString();``console.log(``"load "` `+` `path);``}``}``}``);``}` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202304/929475_FNMGQ6BYPN7SXSY.jpg)

 由so的加载流程可知，当libmsaoaidsec.so被加载之后，frida进程就被杀掉了，因此监测点在libmsaoaidsec.so中。

 如果有了解过so的加载流程，那么就会知道linker会先对so进行加载与链接，然后调用so的.init_proc函数，接着调用.init_array中的函数，最后才是JNI_OnLoad函数，所以我需要先确定检测点大概在哪个函数中。

 使用frida hook JNI_OnLoad函数，如果调用了该函数就输出一行日志，如果没有日志输出，那么就说明检测点在.init_xxx函数中，注入的时机可以选择dlopen加载libmsaoaidsec.so完成之后。

| 12345678910111213141516171819202122232425262728293031 | `function hook_dlopen(soName` `=` `'') {``Interceptor.attach(Module.findExportByName(null,` `"android_dlopen_ext"``),``{``onEnter: function (args) {``var pathptr` `=` `args[``0``];``if` `(pathptr !``=``=` `undefined && pathptr !``=` `null) {``var path` `=` `ptr(pathptr).readCString();``if` `(path.indexOf(soName) >``=` `0``) {``this.is_can_hook` `=` `true;``}``}``},``onLeave: function (retval) {``if` `(this.is_can_hook) {``hook_JNI_OnLoad()``}``}``}``);``}` `function hook_JNI_OnLoad(){``let module` `=` `Process.findModuleByName(``"libmsaoaidsec.so"``)``Interceptor.attach(module.base.add(``0xC6DC` `+` `1``), {``onEnter(args){``console.log(``"call JNI_OnLoad"``)``}``})``}` `setImmediate(hook_dlopen,` `"libmsaoaidsec.so"``)` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202304/929475_3MNWXSB5QNYXFYA.jpg)

 并没有输出日志，那么说明检测的位置在JNI_OnLoad函数之前，所以我需要hook .init_xxx的函数，但这里有一个问题，dlopen函数调用完成之后.init_xxx函数已经执行完成了，这个时候不容易使用frida进行hook

  ![image](https://bbs.kanxue.com/upload/attach/202304/929475_2XY6FG3JTBDJM42.jpg)

 这个问题其实很麻烦的，因为你想要hook linker的call_function并不容易，这里面涉及到linker的自举，我想到了一个取巧的办法，请看接下来的操作。

 首先在.init_proc函数中找一个调用了外部函数的位置，时机越早越好

  ![image](https://bbs.kanxue.com/upload/attach/202304/929475_H3M92FC9ETTQETZ.jpg)

 我选择了_system_property_get函数，接下来使用frida hook dlopen函数，当加载libmsaoaidsec.so时，在onEnter回调方法中hook _system_property_get函数，以"ro.build.version.sdk"字符串作为过滤器。

 如果_system_property_get函数被调用了，那么这个时候也就是.init_proc函数刚刚调用的时候，在这个时机点可以注入我想要的代码，具体实现如下：

| 12345678910111213141516171819202122232425262728293031323334353637 | `function hook_dlopen(soName` `=` `'') {``Interceptor.attach(Module.findExportByName(null,` `"android_dlopen_ext"``),``{``onEnter: function (args) {``var pathptr` `=` `args[``0``];``if` `(pathptr !``=``=` `undefined && pathptr !``=` `null) {``var path` `=` `ptr(pathptr).readCString();``if` `(path.indexOf(soName) >``=` `0``) {``locate_init()``}``}``}``}``);``}` `function locate_init() {``let secmodule` `=` `null``Interceptor.attach(Module.findExportByName(null,` `"__system_property_get"``),``{``/``/` `_system_property_get(``"ro.build.version.sdk"``, v1);``onEnter: function (args) {``secmodule` `=` `Process.findModuleByName(``"libmsaoaidsec.so"``)``var name` `=` `args[``0``];``if` `(name !``=``=` `undefined && name !``=` `null) {``name` `=` `ptr(name).readCString();``if` `(name.indexOf(``"ro.build.version.sdk"``) >``=` `0``) {``/``/` `这是.init_proc刚开始执行的地方，是一个比较早的时机点``/``/` `do something``}``}``}``}``);``}` `setImmediate(hook_dlopen,` `"libmsaoaidsec.so"``)` |
|-|-|

在获取了一个非常早的注入时机之后，就可以定位具体的frida检测点了。网上对frida的检测通常会使用openat、open、strstr、pthread_create、snprintf、sprintf、readlinkat等一系列函数，从这里下手是一个不错的选择。

 我对pthread_create函数进行hook，打印一下新线程要执行的函数地址

| 123456789 | `function hook_pthread_create(){``console.log(``"libmsaoaidsec.so --- "` `+` `Process.findModuleByName(``"libmsaoaidsec.so"``).base)``Interceptor.attach(Module.findExportByName(``"libc.so"``,` `"pthread_create"``),{``onEnter(args){``let func_addr` `=` `args[``2``]``console.log(``"The thread function address is "` `+` `func_addr)``}``})``}` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202304/929475_M2527H4BAQPFJTY.jpg)

 这里面有两个线程是libmsaoaidsec.so创建的，对应的函数偏移分别是0x11129和0x10975

 这两个函数都检测了frida，想要了解具体检测方法的可以自己看看，这里不再深入。

 绕过的方法很简单，直接nop掉pthread_create或者替换检测函数的代码逻辑都可以，我是直接把pthread_create函数nop掉了，下面是完整代码。

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364 | `function hook_dlopen(soName` `=` `'') {``Interceptor.attach(Module.findExportByName(null,` `"android_dlopen_ext"``),``{``onEnter: function (args) {``var pathptr` `=` `args[``0``];``if` `(pathptr !``=``=` `undefined && pathptr !``=` `null) {``var path` `=` `ptr(pathptr).readCString();``if` `(path.indexOf(soName) >``=` `0``) {``locate_init()``}``}``}``}``);``}` `function locate_init() {``let secmodule` `=` `null``Interceptor.attach(Module.findExportByName(null,` `"__system_property_get"``),``{``/``/` `_system_property_get(``"ro.build.version.sdk"``, v1);``onEnter: function (args) {``secmodule` `=` `Process.findModuleByName(``"libmsaoaidsec.so"``)``var name` `=` `args[``0``];``if` `(name !``=``=` `undefined && name !``=` `null) {``name` `=` `ptr(name).readCString();``if` `(name.indexOf(``"ro.build.version.sdk"``) >``=` `0``) {``/``/` `这是.init_proc刚开始执行的地方，是一个比较早的时机点``/``/` `do something``/``/` `hook_pthread_create()``bypass()``}``}``}``}``);``}` `function hook_pthread_create() {``console.log(``"libmsaoaidsec.so --- "` `+` `Process.findModuleByName(``"libmsaoaidsec.so"``).base)``Interceptor.attach(Module.findExportByName(``"libc.so"``,` `"pthread_create"``), {``onEnter(args) {``let func_addr` `=` `args[``2``]``console.log(``"The thread function address is "` `+` `func_addr)``}``})``}` `function nop(addr) {``Memory.patchCode(ptr(addr),` `4``, code` `=``> {``const cw` `=` `new ThumbWriter(code, { pc: ptr(addr) });``cw.putNop();``cw.putNop();``cw.flush();``});``}` `function bypass(){``let module` `=` `Process.findModuleByName(``"libmsaoaidsec.so"``)``nop(module.base.add(``0x10AE4``))``nop(module.base.add(``0x113F8``))``}` `setImmediate(hook_dlopen,` `"libmsaoaidsec.so"``)` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202304/929475_3QFVB25SFRG9P4V.jpg)

 至此，frida检测也就成功绕过了。

---

# 回复

## 回复 by huluxia (#2)

*2023-4-29 17:30*

大佬牛逼。现在加固的壳脱壳搞不定，frida调试也搞不定。希望多出点frida过反调试的文章

## 回复 by 马到成功* (#3)

*2023-4-29 18:30*

也不是大佬![image](https://bbs.kanxue.com/view/img/face/12.gif)，感谢支持

## 回复 by MsScotch (#4)

*2023-4-29 21:38*

思路不错。

## 回复 by La0s (#5)

*2023-4-30 13:27*

好文好思路，学习了

## 回复 by 秋狝 (#6)

*2023-4-30 16:24*

好文

## 回复 by Abelly (#7)

*2023-5-3 12:49*

大佬，new ThumbWriter未定义咋处理？

## 回复 by st0ne (#8)

*2023-5-3 13:08*

666

## 回复 by 马到成功* (#9)

*2023-5-3 20:04*

>
> [Abelly](https://bbs.kanxue.com/user-800867.htm)
>
>  大佬，new ThumbWriter未定义咋处理？
>
>

不应该呀，是不是你的frida版本太低了？

## 回复 by Losir (#10)

*2023-5-4 11:57*

大佬牛逼

## 回复 by wx_水山 (#11)

*2023-5-4 18:35*

找注入点的操作实在太6了，学习了

## 回复 by 万里星河 (#12)

*2023-5-4 23:23*

mark

## 回复 by puppet_w (#13)

*2023-5-5 13:54*

大佬，我想问下前边找的  对应的函数偏移分别是0x11129和0x10975，为啥后边

nop(module.base.add(0x10AE4))

nop(module.base.add(0x113F8))

这俩地址

## 回复 by 马到成功* (#14)

*2023-5-5 14:08*

>
> [puppet_w](https://bbs.kanxue.com/user-929264.htm)
>
>  大佬，我想问下前边找的&nbsp;&nbsp;对应的函数偏移分别是0x11129和0x10975，为啥后边nop(module.base.add(0x10AE4))nop(module ...
>
>

0x11129和0x10975是线程需要执行的函数的地址，也就是pthread_create函数的第三个参数，0x10AE4和0x113F8是pthread_create函数被调用的地址。

## 回复 by puppet_w (#15)

*2023-5-5 14:26*

>
> [马到成功*](https://bbs.kanxue.com/user-929475.htm)
>
>  0x11129和0x10975是线程需要执行的函数的地址，也就是pthread_create函数的第三个参数，0x10AE4和0x113F8是pthread_create函数被调用的地址。
>
>

我看10776  10ad0地址好像也有调用pthread_create，，对吗

![image](https://bbs.kanxue.com/upload/attach/202305/CCFKJFPFU4P8TAR.jpg)

## 回复 by lamorm (#16)

*2023-5-5 16:00*

问下大佬，nop的这两个地址是怎么算出来的，0x10AE4和0x113F8

## 回复 by Circ1e (#17)

*2023-5-5 16:40*

精彩

## 回复 by 马到成功* (#18)

*2023-5-5 16:42*

>
> [puppet_w](https://bbs.kanxue.com/user-929264.htm)
>
>  我看10776 &nbsp;10ad0地址好像也有调用pthread_create，，对吗
>
>

并不是每个线程都是检测frida的

## 回复 by 马到成功* (#19)

*2023-5-5 16:42*

>
> [lamorm](https://bbs.kanxue.com/user-951242.htm)
>
>  问下大佬，nop的这两个地址是怎么算出来的，0x10AE4和0x113F8
>
>

根据交叉引用，找到检测frida的函数的调用处

## 回复 by 萌木盖 (#20)

*2023-5-5 19:27*

bilibili 是32位的   如果其他app是64位的地址是

| 12 | `nop(module.base.add(0x1A858));``nop(module.base.add(0x1B8A8));` |
|-|-|

且nop 方法要改为Arm64Writer  会报找不到ThumbWriter的问题  且cw.putNop()要变成四个

| 123456789101112 | `function` `nop(addr) {``Memory.patchCode(ptr(addr), 4,``code=>  {``const cw =``new` `Arm64Writer(code, { pc: ptr(addr) });``// const cw = new ThumbWriter(code, { pc: ptr(addr) });``cw.putNop();``cw.putNop();``cw.putNop();``cw.putNop();``cw.flush();``});``}` |
|-|-|

而且64位的还可以hook  strstr  把frida  osedBridge之类的一大堆都过滤掉也可解决

## 回复 by hnmy (#21)

*2023-5-6 10:13*

mark

## 回复 by 萌木盖 (#22)

*2023-5-6 16:10*

>
> [Abelly](https://bbs.kanxue.com/user-800867.htm)
>
>  大佬，new ThumbWriter未定义咋处理？
>
>

看我上条评论

## 回复 by wx_威郑天 (#23)

*2023-5-8 14:25*

mark

## 回复 by v0id_ (#24)

*2023-5-8 16:27*

mark了，又学到一个linker里的hook点

## 回复 by jianggiegie (#25)

*2023-5-9 18:04*

学习了,又涨新知识 了![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by 我的名字lym (#26)

*2023-5-10 09:00*

6

## 回复 by 微微T52G25 (#27)

*2023-5-10 09:03*

教程不错，过来支持下，辛苦了工程师

## 回复 by mb_fgiovfhq (#28)

*2023-5-16 15:37*

学到了佬哥，复现成功

## 回复 by aqingadmin (#29)

*2023-5-16 15:53*

nop(module.base.add(0x10AE4))
    nop(module.base.add(0x113F8)) 这两个地址怎么弄到的 好像没讲。

## 回复 by @=llfly (#30)

*2023-5-17 10:26*

学习了![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by wx_沉默的逗比 (#31)

*2023-5-17 17:32*

真棒！![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by wx_倾尽天下 (#32)

*2023-6-15 14:59*

有点意思，感谢大佬~

## 回复 by 0xEA (#33)

*2023-6-15 17:36*

直接不让这个so加载就过掉了![image](https://bbs.kanxue.com/view/img/face/86.gif)

## 回复 by ssw_ggggbaby (#34)

*2023-6-16 16:24*

牛

## 回复 by woaiziyou (#35)

*2023-6-25 10:04*

>
> [马到成功*](https://bbs.kanxue.com/user-929475.htm)
>
>  根据交叉引用，找到检测frida的函数的调用处
>
>

我也没懂这一步，能详细说下交叉引用找地址的步骤吗

## 回复 by ChrQwQ (#36)

*2023-6-25 10:34*

学习了，写的不错

## 回复 by xinghe@dy (#37)

*2023-6-27 15:43*

大佬，这个so文件的32位好像更新了，这种方法好像绕不过，参考某陌

## 回复 by xinghe@dy (#38)

*2023-6-27 15:53*

某陌这种方式绕不过，且是32位的

## 回复 by mb_oowzftna (#39)

*2023-6-27 23:30*

大佬我想问下我要是IDA动态调试想过这种检测指令该怎改呢直接00 00就报错

## 回复 by 果冻大砍刀 (#40)

*2023-6-28 11:08*

make一下

## 回复 by zx_958536 (#41)

*2023-6-29 15:15*

mark

## 回复 by mb_vawulafi (#42)

*2023-7-18 00:04*

学习学习了

## 回复 by mb_kbkqyusp (#43)

*2023-7-20 14:51*

大哥牛比，循序渐进的，很适合初学者

## 回复 by aqingadmin (#44)

*2023-8-1 00:15*

最新版的 已经不行了

## 回复 by ssuperrice (#45)

*2023-8-1 09:03*

先收藏

## 回复 by lqfcugo (#46)

*2023-8-1 09:34*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  xinghe@dy](https://bbs.kanxue.com/user-960234.htm)
>
>  某陌这种方式绕不过，且是32位的
>
>
>

讲的是过bilibili的反调试，和某陌有啥关系？不要刻舟求剑。。

## 回复 by 你瞒我瞒 (#47)

*2023-8-1 09:37*

>
> [0xEA](https://bbs.kanxue.com/user-803133.htm)
>
>  直接不让这个so加载就过掉了[em_86]
>
>

大佬我hook loadLib方法没有执行，直接挂了

## 回复 by mb_kbkqyusp (#48)

*2023-8-7 15:09*

感谢大佬的循序渐进的教程，复现成功了，过掉了最新版的frida检测

## 回复 by mb_ypnyvapc (#49)

*2023-8-21 07:48*

大佬，如果没有外部函数会应该咋hook

## 回复 by 任拓数据 (#50)

*2023-8-31 10:45*

？

## 回复 by lvcoffee (#51)

*2023-8-31 12:02*

膜拜大佬

## 回复 by 龙游天下178 (#52)

*2023-10-5 13:38*

思路清晰

## 回复 by wx_围城 (#53)

*2023-10-7 09:28*

请问frida去特征版本在哪里下载

## 回复 by moyujojo (#54)

*2023-10-12 21:53*

厉害

## 回复 by mb_sbtmhhae (#55)

*2023-11-2 16:20*

求问 这一步不知道怎么实现的

## 回复 by mb_sbtmhhae (#56)

*2023-11-2 16:21*

nop(module.base.add(0x10AE4))
    nop(module.base.add(0x113F8)) 这两个地址怎么弄到的

## 回复 by GeaC (#57)

*2023-11-2 17:33*

支持，学习了

## 回复 by wx_ruler_881 (#58)

*2023-11-8 17:16*

佬 ，NSString   转换类型 NSDictionary， 在frida 的js中要怎么实现

## 回复 by 混迹 (#59)

*2023-12-10 23:18*

![image](https://bbs.kanxue.com/view/img/face/63.gif)6，又新知识了。

## 回复 by t0hka1 (#60)

*2023-12-12 23:52*

学到了![image](https://bbs.kanxue.com/view/img/face/67.gif)

## 回复 by jobs0 (#61)

*2023-12-22 08:59*

小弟通过huluda大佬魔改的frida，也不行，而且都跟踪不到so检测是咋回事儿？

## 回复 by 健康之路 (#62)

*2023-12-22 09:42*

大佬牛逼

## 回复 by MANKVIS (#63)

*2024-1-22 17:38*

目前发现了一个app与这个app类似，也是有一个libmsaoaidsec.so，按照文章可以正常过掉，但是不能使用Java.use去hook，否则直接退出。目前无解，博主有遇到过吗

## 回复 by 郑z (#64)

*2024-2-1 16:02*

楼上跟我的情况一样，猜测可能有线程检测，因为过了一秒左右才闪，我把可疑线程也nop掉了还是闪，只要使用java.perform就闪，hook so不闪

## 回复 by 流星云手 (#65)

*2024-2-21 11:08*

我遇到一个样本so没有pthread_create,只看到一个pthread_once,这两个不一样呀！怎么处理？

## 回复 by hjjiel (#66)

*2024-2-24 12:24*

样本呢

## 回复 by 蓝色之冰 (#67)

*2024-2-29 13:09*

谁提供下提供下 libmsaoaidsec.so

## 回复 by 逆道而行 (#68)

*2024-3-25 12:30*

mark

## 回复 by 青头潜鸭 (#69)

*2024-4-5 09:24*

文章思路很好，初学者怎么定位两个地址。

## 回复 by taoying (#70)

*2024-4-17 18:06*

为什么要nop掉pthread_create函数，而不nop掉线程要执行的函数地址

## 回复 by Mrzh (#71)

*2024-4-28 11:29*

不用nop,replace掉pthread_create的偏移地址就可以的，目前64位的是0x1B8D4，0x26E5C，0x1c544

## 回复 by mb_mihutdve (#72)

*2024-5-20 09:34*

mark

## 回复 by mb_rugymctl (#73)

*2024-7-25 21:22*

老哥，私一个APP逆向，有偿

## 回复 by mb_rugymctl (#74)

*2024-7-26 14:18*

老哥，私一个APP逆向，有偿

## 回复 by mb_rugymctl (#75)

*2024-7-27 14:46*

老哥，私一个APP逆向，有偿

## 回复 by 青头潜鸭 (#76)

*2024-12-18 09:04*

nop(module.base.add(0x10AE4))
nop(module.base.add(0x113F8))

大神你好 这两个地址有详细的步骤计算吗

## 回复 by 青头潜鸭 (#77)

*2024-12-18 10:26*

nop(module.base.add(0x10AE4))
nop(module.base.add(0x113F8))

大神这两个值怎么定位的 有详细教程吗

## 回复 by 青头潜鸭 (#78)

*2024-12-24 20:56*

>
> [puppet_w](https://bbs.kanxue.com/user-929264.htm)
>
>  大佬，我想问下前边找的&nbsp;&nbsp;对应的函数偏移分别是0x11129和0x10975，为啥后边nop(module.base.add(0x10AE4))nop(module ...
>
>

F5之后pthread_create(dword_21590, 0, (void *(*)(void *))sub_10974, 0); 这个的地址是0x10AE4

## 回复 by frozenrain (#79)

*2024-12-27 17:30*

linker init那个点也是可以hook的，只不过是硬编码。

## 回复 by mb_ldbucrik (#80)

*2024-12-28 15:51*

>
> [frozenrain](https://bbs.kanxue.com/user-144246.htm)
>
>  linker init那个点也是可以hook的，只不过是硬编码。
>
>

请问怎么hook呢

## 回复 by mb_lyqehpis (#81)

*2025-3-19 16:20*

>
> [puppet_w](https://bbs.kanxue.com/user-929264.htm)
>
>  我看10776 &nbsp;10ad0地址好像也有调用pthread_create，，对吗
>
>

hi，大佬，这块的话是不是根据打印出来的0x11129和0x10975找到对应函数，然后将对应函数进行索引找到调用的地方，去nop调用的地方的地址么

## 回复 by Imxz (#82)

*2026-4-2 23:10*

tql
