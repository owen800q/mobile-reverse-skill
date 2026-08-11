---
title: '[分享] 安卓逆向课题之6, mobile spider get started. Object的自动化动态分析和快速定位(笔记完毕)'
url: https://bbs.kanxue.com/thread-279541.htm
tid: 279541
author: calleng
date: '2023-11-14'
tags: [Android安全, 分享, 基础理论]
crawled_at: '2026-08-11T08:46:40+00:00'
replies: 11
---

## 入门学习逆向的个人笔记,预览(欢迎探讨)

[[原创] 肉丝的r0env2022(kali linux)配置xrdp远程桌面,以及Genymotion安卓11的ssh登陆问题和11系统amr64转译问题.](https://bbs.kanxue.com/thread-279543.htm)
[[分享] (Android) 逆向入门记录 一篇杂文, 记录.](https://bbs.kanxue.com/thread-279407.htm)
[[分享] Adndroid逆向的基础环境准备 的一些记录 , 抄袭royuse的课 第3课](https://bbs.kanxue.com/thread-279435.htm)
[[分享] 安卓逆向课题之4, Activity,service,content provider,broadcast receiver和实例演示,完毕](https://bbs.kanxue.com/thread-279459.htm)
[[分享] 安卓逆向课题之5, mobile spider get started. 两天高度集中学习, 承上启下的流程,a明白,b上手练.(5th完结)](https://bbs.kanxue.com/thread-279478.htm)
[[分享] 安卓逆向课题之6, mobile spider get started. Object的自动化动态分析和快速定位(笔记完毕)](https://bbs.kanxue.com/thread-279541.htm)
[[分享] 安卓逆向课题之7, mobile spider get started. 看电视直播App(未加固)去广告升级 (笔记待完善)](https://bbs.kanxue.com/thread-279583.htm)
[[分享] 安卓逆向课题之8, 真实App实操带壳App重打包去强制升级(部分抄袭别人笔记)(一次不完美的实践)](https://bbs.kanxue.com/thread-279686.htm)
[[讨论] Android Reverse Project No.9, "Types of App Security Protection, Identification and Handling Methods"](https://bbs.kanxue.com/thread-280082.htm)
[[原创] Android Reverse Project No.9, "Types of App Protection“ ---- Video Course](https://bbs.kanxue.com/thread-280099.htm)

---

## 本课目前(2023)的结论

1,　RPC 应用场景不是太广, 除非, 是类似多人协作的 Ghidra
2, 目前直接 非root 环境,要frida 调试,需要重打包apk,遇到强壳带保护,基本不会成功. 除非根据课程演示, 20年的 apk 可行, 技术过时非常快, 基本功掌握,和理解原理实战升级技能是才能走在壳的前面.绕过保护.
3, 葫芦娃的 dexdump 已经独立于 objection插件存在, base on Frida-tools. 目前不再更新(基于2020年课程而言.)
4, 手写,手敲才不会忘记. 要常常回去看看你做的的笔记. 不看不如不写.

## 自动化动态分析和快速定位

- objection(免)root动态调试 apk
- objection 内存漫游和组件控制
- objection 类和方法动态 trace
- objection + DEXDump 内存暴力脱壳机
- objection RPC 可以直接 curl 的 RPC

静态的都需要加上自己的动态分析, 否则不会准确.
中文的普通话，如果正确的使用是不会出错的。
动态分析，他是绝对不会骗人的。都是100%执行到那里才会被触发的。
从内存中打印出来类的列表都是可以被hook的。
如果内存中没有打印出来，那么则是不能被hook的。

 Hook就是给函数加一个钩子，如果函数执行了。那么这个钩子也会跟着执行。现在所有动态调试的方法都是基于hook。

 hook如果玩的好的话，小城市基本上是2万。

 Frida 就是hook native和Java.
Java是写APP的主要语言, 更难一点的话，APP会将对抗下放到Native层.
最近开始要从so里面去做对抗.

### objection(免)root动态调试 apk

现在需要一个免root的方式来调试.

非root调试, 本质就是重打包, APP重新解包,解完包之后其实是可以用工具，Apk本质是一个zip压缩档, 解包后,我们重新对它进行修改，然后再进行重签名后,打包为apk ,传到手机安装.

 Objection有一个功能，就是把Frida的插件, 重新打包塞到apk文件里面去。
 这样就免去了手机需要root的情况。在任何手机上你都可以去调试。

 限制的话，你不能root,你就不能hook系统的设置。
 如果去调试一些进程，那么你就是没有办法通过以任何的方式去实现的。

With Frida, you write JavaScript programs and inject them into arbitrary processes, to hook and modify and call whatever you please.

使用 Frida，你可以编写 JavaScript 程序，并将它们注入到任意进程中，以挂钩、修改和调用任何你喜欢的东西。

Frida trace 嗯。可以非常快速的定位操作流程和hook的关键点。可以说成为目前事实上的Trace标准都不为过。

Trace就是说把你怀疑所有的class和method 全部hook上。然后手机去执行一下，点一下。然后他就把你怀疑的这些路径全部打印出来.如果他执行了，那么他所有的调用栈就会被全部显示出来。从上到下一个完整的执行流就会被你看见。

因为Java层是没有秘密的. 绝多数的厂商都是把 逻辑写在Native层, C写的动态库so里面.

Objection 虽然强大, 但是 精准控制还是需要Frida.

RPC, 远程调用. android上执行后,执行结果,返回到本地client上.

每个类它只要有一个生命周期。他只要没有被内存回收。他在内存里都有一个实例的。
一个 string , 再次 string new,string, 或者一个person ,new person.
他只要没有被内存回收。他在内存里都有一个实例的。一串数字，一串代码，指向内存的一个区域。

虚拟机 Genymotion 8.1 nextus 5x 安装错误

![picture 0](https://bbs.kanxue.com/upload/attach/202311/304186_FUFY299FX9FRH8D.png)

虚拟机 网易mumu 正常

![picture 0](https://bbs.kanxue.com/upload/attach/202311/304186_SE8P62QJAT6BZMN.png)

继续下载最新版本

kali, Firefox
![picture 1](https://bbs.kanxue.com/upload/attach/202311/304186_JQ4FVD5X2J7ZDKD.png)

![picture 2](https://bbs.kanxue.com/upload/attach/202311/304186_3AJEMRE4ECRMAB6.png)

获取最新apk 下载 时隔 3年, 还活着. 牛逼, 课程老去了.

[样本 url 地址 2023年11月存活](https://bbs.kanxue.com/http/storage.suyunxia.net/fulao2_202B.apk)

安装 Genymotion-ARM-Translation_for_8.0 翻译 arm 的, 安装OK,启动报错.

网易mumu模拟器,

[Objection Wiki Patching Android Applications](https://github.com/sensepost/objection/wiki/Patching-Android-Applications)

The objection patchapk is a command that basically wraps around several other system commands, automating the patching process as far as possible. Naturally, those commands need to be installed and available first. They are:

| 1234 | `aapt` `-` `from``: http:``/``/``elinux.org``/``Android_aapt``adb` `-` `from``: https:``/``/``developer.android.com``/``studio``/``command``-``line``/``adb.html``jarsigner` `-` `from``: http:``/``/``docs.oracle.com``/``javase``/``7``/``docs``/``technotes``/``tools``/``windows``/``jarsigner.html``apktool` `-` `from``: https:``/``/``ibotpeaches.github.io``/``Apktool``/` |
|-|-|

Most of these dependencies are really easy to solve and can be installed using homebrew on macOS, or apt in Kali Linux. If you choose to manually install the dependencies, ensure that they are available in your current PATH.

可以直接搜索aapt
![picture 3](https://bbs.kanxue.com/upload/attach/202311/304186_ABXRQ4W5VK4N6J8.png)

![picture 4](https://bbs.kanxue.com/upload/attach/202311/304186_ASXR8JWU5G3DNHQ.png)

测试, genymotion pixel 2, pie 9.0 system, + Genymotion-ARM-Translation_for_8.0 翻译 arm 的, 安装OK, 启动OK

![picture 5](https://bbs.kanxue.com/upload/attach/202311/304186_MEWYZTK2E69R4X7.png)

| 12345678 | `【apk免root重打包连接objection``/``frida】``objection的patchapk需要aapt、adb、jarsigner、apktool，其中apktool需要官网下载下，其他前仨在android``-``studio中就有：``ln` `-``s` `/``root``/``Documents``/``android``-``studio``/``jre``/``bin``/``jarsigner` `/``usr``/``bin``ln` `-``s` `/``root``/``Android``/``Sdk``/``build``-``tools``/``33.0``.``0``/``aapt` `/``usr``/``bin``ln` `-``s` `/``root``/``Android``/``Sdk``/``build``-``tools``/``33.0``.``0``/``aapt2` `/``usr``/``bin` `r0env2022可以不用执行下句``ln` `-``s` `/``root``/``Android``/``Sdk``/``platform``-``tools``/``adb` `/``usr``/``bin` |
|-|-|

然后就是解压apk看下它里面的lib是哪个架构的，按架构来运行：

### objection patchapk --architecture armeabi-v7a --use-aapt2 --source yourAPK.apk

app启动后用objection/frida直接连上即可。

aapt 是android studio 3.0 之前 老版本用.
aapt 是3.0 后.

![picture 6](https://bbs.kanxue.com/upload/attach/202311/304186_R4K5FG4MVYWSYJX.png)

![picture 7](https://bbs.kanxue.com/upload/attach/202311/304186_553QGUUU2HZCABF.png)

| 1234567891011121314151617181920 | `使用方式：objection patchapk [选项]` `使用 frida``-``gadget.so 对 APK 进行修补。` `选项：``-``s,` `-``-``source TEXT 要修补的源 APK [必需]``-``a,` `-``-``architecture TEXT 执行修补后的 APK 将运行的设备架构。可以使用 adb shell getprop ro.product.cpu.abi 来确定。如果未指定，此命令将尝试自动确定。``-``V,` `-``-``gadget``-``version TEXT 要使用的 gadget 版本。如果未指定，将使用最新版本。``-``p,` `-``-``pause 在重新构建 APK 前暂停修补程序。``-``k,` `-``-``skip``-``cleanup 完成后不清理临时文件。``-``d,` `-``-``enable``-``debug 在应用程序清单中将 android:debuggable 标志设置为 true。``-``N,` `-``-``network``-``security``-``config 包含一个 network_security_config.xml 文件，允许在 Android` `7` `及更高版本上信任用户添加的 CA。此选项不能与` `-``-``skip``-``resources 标志一起使用。``-``D,` `-``-``skip``-``resources 跳过作为 apktool 处理的资源解码。``-``t,` `-``-``target``-``class` `TEXT 要修补的目标类。``-``2``,` `-``-``use``-``aapt2 使用 aapt2 二进制文件而不是 aapt 作为 apktool 处理的一部分。``-``c,` `-``-``gadget``-``config TEXT 要使用的 gadget 配置文件。有关更多信息，请参阅 https:``/``/``frida.re``/``docs``/``gadget``/``。``-``l,` `-``-``script``-``source TEXT 与` `"path"` `配置类型一起使用的脚本文件。在您的配置中，将` `"path"` `指定为` `"libfrida-gadget.script.so"``。``-``n,` `-``-``ignore``-``nativelibs 不更改 AndroidManifest.xml 中的 extractNativeLibs 标志。``-``m,` `-``-``manifest TEXT 要读取的已解码 AndroidManifest.xml 文件。``-``-``help` `显示此消息并退出。` |
|-|-|

由于上述的Fulao 2, 2023.11月版本加装了欧洲版本的强壳, 暂时啃不动. 所以,注入保护的存在的关系,无法在非root环境下进行Frida调试.

所以.我们在 root 环境下,进行直接调试.

![picture 8](https://bbs.kanxue.com/upload/attach/202311/304186_DRD8PWFU55JTB4V.png)

arm32 架构,.armeabi-v7a
直接从打包命令

| 1 | `proxychains objection patchapk  --architecture armeabi-v7a  --gadget-version 15.2.2 --``source` `.``/sou``.apk` |
|-|-|

安装 模拟器是 x86 的32 位架构的

![picture 9](https://bbs.kanxue.com/upload/attach/202311/304186_NJJDP9QF22ERYHS.png)

![picture 10](https://bbs.kanxue.com/upload/attach/202311/304186_UEDTM5CHFRVPSWF.png)

以上正常

以下, 加了强壳. 反调试,被弹回来了
![picture 11](https://bbs.kanxue.com/upload/attach/202311/304186_W7P7CMGSV4GYQB2.png)

<https://www.anquanke.com/post/id/197657>

![picture 12](https://bbs.kanxue.com/upload/attach/202311/304186_8AV96BZ89G864NX.png)

![picture 13](https://bbs.kanxue.com/upload/attach/202311/304186_3XRZXZATNHSCQ88.png)

![picture 14](https://bbs.kanxue.com/upload/attach/202311/304186_XK9HJ26HNJ6CB9V.png)

![picture 15](https://bbs.kanxue.com/upload/attach/202311/304186_FAUK8H9S77J3DRF.png)

| 1234 | `com.ilulutv.fulao2 on (Google:` `8.1``.``0``) [usb]` `# help android hooking watch` `Contains subcommands to watch` `for` `various bits of information on` `class` `invocations.``包含子命令，用于监视类调用的各种信息。` |
|-|-|

## 提取内存信息

查看内存中加载的库

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180 | `运行命令 memory` `list` `modules` `com.ilulutv.fulao2 on (Google:` `8.1``.``0``) [usb]` `# memory list modules``Save the output by adding ```-``-``json modules.json` to this command``Name                                          Base        Size                  Path``app_process32` `0x628bc000`  `28672` `(``28.0` `KiB)` `/``system``/``bin``/``app_process32``libandroid_runtime.so` `0xeb417000`  `1929216` `(``1.8` `MiB)` `/``system``/``lib``/``libandroid_runtime.so``libbinder.so` `0xea484000`  `630784` `(``616.0` `KiB)` `/``system``/``lib``/``libbinder.so``libcutils.so` `0xe8569000`  `77824` `(``76.0` `KiB)` `/``system``/``lib``/``libcutils.so``libhwbinder.so` `0xe9bc8000`  `172032` `(``168.0` `KiB)` `/``system``/``lib``/``libhwbinder.so``liblog.so` `0xe8785000`  `102400` `(``100.0` `KiB)` `/``system``/``lib``/``liblog.so``libnativeloader.so` `0xebe4c000`  `28672` `(``28.0` `KiB)` `/``system``/``lib``/``libnativeloader.so``libutils.so` `0xe91c9000`  `135168` `(``132.0` `KiB)` `/``system``/``lib``/``libutils.so``libwilhelm.so` `0xe8be4000`  `274432` `(``268.0` `KiB)` `/``system``/``lib``/``libwilhelm.so``libc``+``+``.so` `0xebb81000`  `1024000` `(``1000.0` `KiB)` `/``system``/``lib``/``libc``+``+``.so``libc.so` `0xeacd1000`  `962560` `(``940.0` `KiB)` `/``system``/``lib``/``libc.so``libm.so` `0xeb600000`  `237568` `(``232.0` `KiB)` `/``system``/``lib``/``libm.so``libdl.so` `0xebdb8000`  `20480` `(``20.0` `KiB)` `/``system``/``lib``/``libdl.so``libmemtrack.so` `0xe8a39000`  `16384` `(``16.0` `KiB)` `/``system``/``lib``/``libmemtrack.so``libandroidfw.so` `0xeaf48000`  `356352` `(``348.0` `KiB)` `/``system``/``lib``/``libandroidfw.so``libappfuse.so` `0xea8e1000`  `57344` `(``56.0` `KiB)` `/``system``/``lib``/``libappfuse.so``libbase.so` `0xe8a6b000`  `73728` `(``72.0` `KiB)` `/``system``/``lib``/``libbase.so``libcrypto.so` `0xe8c9d000`  `1142784` `(``1.1` `MiB)` `/``system``/``lib``/``libcrypto.so``libnativehelper.so` `0xe91a1000`  `32768` `(``32.0` `KiB)` `/``system``/``lib``/``libnativehelper.so``libdebuggerd_client.so` `0xeaff0000`  `24576` `(``24.0` `KiB)` `/``system``/``lib``/``libdebuggerd_client.so``libui.so` `0xe8588000`  `151552` `(``148.0` `KiB)` `/``system``/``lib``/``libui.so``libgraphicsenv.so` `0xec4ed000`  `16384` `(``16.0` `KiB)` `/``system``/``lib``/``libgraphicsenv.so``libgui.so` `0xea2c6000`  `675840` `(``660.0` `KiB)` `/``system``/``lib``/``libgui.so``libsensor.so` `0xe860c000`  `98304` `(``96.0` `KiB)` `/``system``/``lib``/``libsensor.so``libinput.so` `0xeab8b000`  `188416` `(``184.0` `KiB)` `/``system``/``lib``/``libinput.so``libcamera_client.so` `0xeac4b000`  `360448` `(``352.0` `KiB)` `/``system``/``lib``/``libcamera_client.so``libcamera_metadata.so` `0xe89ea000`  `40960` `(``40.0` `KiB)` `/``system``/``lib``/``libcamera_metadata.so``libskia.so` `0xe9200000`  `9936896` `(``9.5` `MiB)` `/``system``/``lib``/``libskia.so``libsqlite.so` `0xe9e5b000`  `1196032` `(``1.1` `MiB)` `/``system``/``lib``/``libsqlite.so``libEGL.so` `0xea389000`  `172032` `(``168.0` `KiB)` `/``system``/``lib``/``libEGL.so``libGLESv1_CM.so` `0xeaec4000`  `45056` `(``44.0` `KiB)` `/``system``/``lib``/``libGLESv1_CM.so``libGLESv2.so` `0xeb903000`  `90112` `(``88.0` `KiB)` `/``system``/``lib``/``libGLESv2.so``libvulkan.so` `0xea710000`  `147456` `(``144.0` `KiB)` `/``system``/``lib``/``libvulkan.so``libziparchive.so` `0xeabc1000`  `53248` `(``52.0` `KiB)` `/``system``/``lib``/``libziparchive.so``libETC1.so` `0xe85c2000`  `20480` `(``20.0` `KiB)` `/``system``/``lib``/``libETC1.so``libhardware.so` `0xeaac6000`  `16384` `(``16.0` `KiB)` `/``system``/``lib``/``libhardware.so``libhardware_legacy.so` `0xe9bba000`  `16384` `(``16.0` `KiB)` `/``system``/``lib``/``libhardware_legacy.so``libselinux.so` `0xea662000`  `98304` `(``96.0` `KiB)` `/``system``/``lib``/``libselinux.so``libicuuc.so` `0xe8e98000`  `1662976` `(``1.6` `MiB)` `/``system``/``lib``/``libicuuc.so``libmedia.so` `0xea940000`  `999424` `(``976.0` `KiB)` `/``system``/``lib``/``libmedia.so``libaudioclient.so` `0xe8881000`  `491520` `(``480.0` `KiB)` `/``system``/``lib``/``libaudioclient.so``libjpeg.so` `0xea840000`  `524288` `(``512.0` `KiB)` `/``system``/``lib``/``libjpeg.so``libusbhost.so` `0xeb8ee000`  `24576` `(``24.0` `KiB)` `/``system``/``lib``/``libusbhost.so``libharfbuzz_ng.so` `0xeadcc000`  `552960` `(``540.0` `KiB)` `/``system``/``lib``/``libharfbuzz_ng.so``libz.so` `0xea756000`  `98304` `(``96.0` `KiB)` `/``system``/``lib``/``libz.so``libpdfium.so` `0xebe96000`  `5279744` `(``5.0` `MiB)` `/``system``/``lib``/``libpdfium.so``libimg_utils.so` `0xe9d1b000`  `86016` `(``84.0` `KiB)` `/``system``/``lib``/``libimg_utils.so``libnetd_client.so` `0xe89ac000`  `20480` `(``20.0` `KiB)` `/``system``/``lib``/``libnetd_client.so``libsoundtrigger.so` `0xea45a000`  `77824` `(``76.0` `KiB)` `/``system``/``lib``/``libsoundtrigger.so``libminikin.so` `0xeba99000`  `147456` `(``144.0` `KiB)` `/``system``/``lib``/``libminikin.so``libprocessgroup.so` `0xeaa8c000`  `32768` `(``32.0` `KiB)` `/``system``/``lib``/``libprocessgroup.so``libnativebridge.so` `0xe87f3000`  `20480` `(``20.0` `KiB)` `/``system``/``lib``/``libnativebridge.so``libmemunreachable.so` `0xec3c3000`  `192512` `(``188.0` `KiB)` `/``system``/``lib``/``libmemunreachable.so``libhidlbase.so` `0xe9157000`  `151552` `(``148.0` `KiB)` `/``system``/``lib``/``libhidlbase.so``libhidltransport.so` `0xe9d61000`  `606208` `(``592.0` `KiB)` `/``system``/``lib``/``libhidltransport.so``libvintf.so` `0xe8700000`  `466944` `(``456.0` `KiB)` `/``system``/``lib``/``libvintf.so``libnativewindow.so` `0xe84d7000`  `24576` `(``24.0` `KiB)` `/``system``/``lib``/``libnativewindow.so``libhwui.so` `0xeb015000`  `1122304` `(``1.1` `MiB)` `/``system``/``lib``/``libhwui.so``libbacktrace.so` `0xeb31c000`  `122880` `(``120.0` `KiB)` `/``system``/``lib``/``libbacktrace.so``libvndksupport.so` `0xe9cdc000`  `12288` `(``12.0` `KiB)` `/``system``/``lib``/``libvndksupport.so``libaudiomanager.so` `0xebc8c000`  `49152` `(``48.0` `KiB)` `/``system``/``lib``/``libaudiomanager.so``libstagefright.so` `0xe9f8c000`  `3334144` `(``3.2` `MiB)` `/``system``/``lib``/``libstagefright.so``libstagefright_foundation.so` `0xebd2b000`  `270336` `(``264.0` `KiB)` `/``system``/``lib``/``libstagefright_foundation.so``libstagefright_http_support.so` `0xe894e000`  `24576` `(``24.0` `KiB)` `/``system``/``lib``/``libstagefright_http_support.so``android.hardware.memtrack@``1.0``.so` `0xeaa55000`  `139264` `(``136.0` `KiB)` `/``system``/``lib``/``android.hardware.memtrack@``1.0``.so``android.hardware.graphics.allocator@``2.0``.so` `0xea40c000`  `131072` `(``128.0` `KiB)` `/``system``/``lib``/``android.hardware.graphics.allocator@``2.0``.so``android.hardware.graphics.mapper@``2.0``.so` `0xe8850000`  `172032` `(``168.0` `KiB)` `/``system``/``lib``/``android.hardware.graphics.mapper@``2.0``.so``android.hardware.configstore@``1.0``.so` `0xe8b07000`  `229376` `(``224.0` `KiB)` `/``system``/``lib``/``android.hardware.configstore@``1.0``.so``android.hardware.configstore``-``utils.so` `0xe880c000`  `16384` `(``16.0` `KiB)` `/``system``/``lib``/``android.hardware.configstore``-``utils.so``libsync.so` `0xea6b6000`  `16384` `(``16.0` `KiB)` `/``system``/``lib``/``libsync.so``android.hidl.token@``1.0``-``utils.so` `0xeb3db000`  `20480` `(``20.0` `KiB)` `/``system``/``lib``/``android.hidl.token@``1.0``-``utils.so``android.hardware.graphics.bufferqueue@``1.0``.so` `0xeb198000`  `409600` `(``400.0` `KiB)` `/``system``/``lib``/``android.hardware.graphics.bufferqueue@``1.0``.so``libdng_sdk.so` `0xea54e000`  `929792` `(``908.0` `KiB)` `/``system``/``lib``/``libdng_sdk.so``libexpat.so` `0xea3d2000`  `172032` `(``168.0` `KiB)` `/``system``/``lib``/``libexpat.so``libft2.so` `0xe909a000`  `532480` `(``520.0` `KiB)` `/``system``/``lib``/``libft2.so``libheif.so` `0xe8c41000`  `32768` `(``32.0` `KiB)` `/``system``/``lib``/``libheif.so``libicui18n.so` `0xeb64e000`  `2400256` `(``2.3` `MiB)` `/``system``/``lib``/``libicui18n.so``libpiex.so` `0xe86c2000`  `114688` `(``112.0` `KiB)` `/``system``/``lib``/``libpiex.so``libpng.so` `0xeb349000`  `225280` `(``220.0` `KiB)` `/``system``/``lib``/``libpng.so``libpcre2.so` `0xe8b93000`  `147456` `(``144.0` `KiB)` `/``system``/``lib``/``libpcre2.so``libpackagelistparser.so` `0xe9e05000`  `16384` `(``16.0` `KiB)` `/``system``/``lib``/``libpackagelistparser.so``libclang_rt.ubsan_standalone``-``i686``-``android.so` `0xeb951000`  `880640` `(``860.0` `KiB)` `/``system``/``lib``/``libclang_rt.ubsan_standalone``-``i686``-``android.so``android.hardware.media.omx@``1.0``.so` `0xeb22d000`  `823296` `(``804.0` `KiB)` `/``system``/``lib``/``android.hardware.media.omx@``1.0``.so``android.hardware.media@``1.0``.so` `0xeaf0f000`  `32768` `(``32.0` `KiB)` `/``system``/``lib``/``android.hardware.media@``1.0``.so``libsonivox.so` `0xebdd4000`  `385024` `(``376.0` `KiB)` `/``system``/``lib``/``libsonivox.so``libaudioutils.so` `0xea919000`  `86016` `(``84.0` `KiB)` `/``system``/``lib``/``libaudioutils.so``libmedia_helper.so` `0xeba49000`  `94208` `(``92.0` `KiB)` `/``system``/``lib``/``libmedia_helper.so``libmediadrm.so` `0xe8b42000`  `249856` `(``244.0` `KiB)` `/``system``/``lib``/``libmediadrm.so``libmediametrics.so` `0xe9c68000`  `69632` `(``68.0` `KiB)` `/``system``/``lib``/``libmediametrics.so``libhidlmemory.so` `0xeb389000`  `20480` `(``20.0` `KiB)` `/``system``/``lib``/``libhidlmemory.so``android.hidl.memory@``1.0``.so` `0xe864b000`  `217088` `(``212.0` `KiB)` `/``system``/``lib``/``android.hidl.memory@``1.0``.so``android.hardware.graphics.common@``1.0``.so` `0xeab2d000`  `53248` `(``52.0` `KiB)` `/``system``/``lib``/``android.hardware.graphics.common@``1.0``.so``libtinyxml2.so` `0xea815000`  `73728` `(``72.0` `KiB)` `/``system``/``lib``/``libtinyxml2.so``libprotobuf``-``cpp``-``lite.so` `0xebae3000`  `286720` `(``280.0` `KiB)` `/``system``/``lib``/``libprotobuf``-``cpp``-``lite.so``libRScpp.so` `0xea79e000`  `278528` `(``272.0` `KiB)` `/``system``/``lib``/``libRScpp.so``libunwind.so` `0xea6cf000`  `176128` `(``172.0` `KiB)` `/``system``/``lib``/``libunwind.so``libdrmframework.so` `0xeac16000`  `159744` `(``156.0` `KiB)` `/``system``/``lib``/``libdrmframework.so``libmediautils.so` `0xec4a6000`  `65536` `(``64.0` `KiB)` `/``system``/``lib``/``libmediautils.so``libvorbisidec.so` `0xe869e000`  `139264` `(``136.0` `KiB)` `/``system``/``lib``/``libvorbisidec.so``libstagefright_omx_utils.so` `0xeab6c000`  `32768` `(``32.0` `KiB)` `/``system``/``lib``/``libstagefright_omx_utils.so``libstagefright_flacdec.so` `0xe9c91000`  `118784` `(``116.0` `KiB)` `/``system``/``lib``/``libstagefright_flacdec.so``libstagefright_xmlparser.so` `0xeb158000`  `65536` `(``64.0` `KiB)` `/``system``/``lib``/``libstagefright_xmlparser.so``android.hidl.allocator@``1.0``.so` `0xe8508000`  `131072` `(``128.0` `KiB)` `/``system``/``lib``/``android.hidl.allocator@``1.0``.so``android.hardware.cas@``1.0``.so` `0xec403000`  `442368` `(``432.0` `KiB)` `/``system``/``lib``/``android.hardware.cas@``1.0``.so``android.hardware.cas.native@``1.0``.so` `0xe9055000`  `155648` `(``152.0` `KiB)` `/``system``/``lib``/``android.hardware.cas.native@``1.0``.so``libpowermanager.so` `0xebb52000`  `24576` `(``24.0` `KiB)` `/``system``/``lib``/``libpowermanager.so``android.hidl.token@``1.0``.so` `0xebcc8000`  `135168` `(``132.0` `KiB)` `/``system``/``lib``/``android.hidl.token@``1.0``.so``libstdc``+``+``.so` `0xe8936000`  `20480` `(``20.0` `KiB)` `/``system``/``lib``/``libstdc``+``+``.so``libspeexresampler.so` `0xe9c16000`  `24576` `(``24.0` `KiB)` `/``system``/``lib``/``libspeexresampler.so``android.hardware.drm@``1.0``.so` `0xe8dc6000`  `745472` `(``728.0` `KiB)` `/``system``/``lib``/``android.hardware.drm@``1.0``.so``liblzma.so` `0xeae8c000`  `188416` `(``184.0` `KiB)` `/``system``/``lib``/``liblzma.so``libmedia_omx.so` `0xe8a8b000`  `352256` `(``344.0` `KiB)` `/``system``/``lib``/``libmedia_omx.so``libart.so` `0xe7bcd000`  `7413760` `(``7.1` `MiB)` `/``system``/``lib``/``libart.so``liblz4.so` `0xe7b96000`  `94208` `(``92.0` `KiB)` `/``system``/``lib``/``liblz4.so``libtombstoned_client.so` `0xec733000`  `24576` `(``24.0` `KiB)` `/``system``/``lib``/``libtombstoned_client.so``libsigchain.so` `0xec8de000`  `12288` `(``12.0` `KiB)` `/``system``/``lib``/``libsigchain.so``boot.oat` `0x6f916000`  `8851456` `(``8.4` `MiB)` `/``system``/``framework``/``x86``/``boot.oat``boot``-``core``-``libart.oat` `0x70187000`  `3543040` `(``3.4` `MiB)` `/``system``/``framework``/``x86``/``boot``-``core``-``libart.oat``boot``-``conscrypt.oat` `0x704e8000`  `466944` `(``456.0` `KiB)` `/``system``/``framework``/``x86``/``boot``-``conscrypt.oat``boot``-``okhttp.oat` `0x7055a000`  `630784` `(``616.0` `KiB)` `/``system``/``framework``/``x86``/``boot``-``okhttp.oat``boot``-``bouncycastle.oat` `0x705f4000`  `475136` `(``464.0` `KiB)` `/``system``/``framework``/``x86``/``boot``-``bouncycastle.oat``boot``-``apache``-``xml.oat` `0x70668000`  `36864` `(``36.0` `KiB)` `/``system``/``framework``/``x86``/``boot``-``apache``-``xml.oat``boot``-``legacy``-``test.oat` `0x70671000`  `32768` `(``32.0` `KiB)` `/``system``/``framework``/``x86``/``boot``-``legacy``-``test.oat``boot``-``ext.oat` `0x70679000`  `278528` `(``272.0` `KiB)` `/``system``/``framework``/``x86``/``boot``-``ext.oat``boot``-``framework.oat` `0x706bd000`  `24449024` `(``23.3` `MiB)` `/``system``/``framework``/``x86``/``boot``-``framework.oat``boot``-``telephony``-``common.oat` `0x71e0e000`  `3006464` `(``2.9` `MiB)` `/``system``/``framework``/``x86``/``boot``-``telephony``-``common.oat``boot``-``voip``-``common.oat` `0x720ec000`  `94208` `(``92.0` `KiB)` `/``system``/``framework``/``x86``/``boot``-``voip``-``common.oat``boot``-``ims``-``common.oat` `0x72103000`  `106496` `(``104.0` `KiB)` `/``system``/``framework``/``x86``/``boot``-``ims``-``common.oat``boot``-``org.apache.http.legacy.boot.oat` `0x7211d000`  `634880` `(``620.0` `KiB)` `/``system``/``framework``/``x86``/``boot``-``org.apache.http.legacy.boot.oat``boot``-``android.hidl.base``-``V1.``0``-``java.oat` `0x721b8000`  `24576` `(``24.0` `KiB)` `/``system``/``framework``/``x86``/``boot``-``android.hidl.base``-``V1.``0``-``java.oat``boot``-``android.hidl.manager``-``V1.``0``-``java.oat` `0x721be000`  `45056` `(``44.0` `KiB)` `/``system``/``framework``/``x86``/``boot``-``android.hidl.manager``-``V1.``0``-``java.oat``libhoudini.so` `0xe2948000`  `7151616` `(``6.8` `MiB)` `/``system``/``lib``/``libhoudini.so``libandroid.so` `0xe2909000`  `131072` `(``128.0` `KiB)` `/``system``/``lib``/``libandroid.so``libaaudio.so` `0xe28c6000`  `208896` `(``204.0` `KiB)` `/``system``/``lib``/``libaaudio.so``libcamera2ndk.so` `0xe2891000`  `126976` `(``124.0` `KiB)` `/``system``/``lib``/``libcamera2ndk.so``libmediandk.so` `0xe27e3000`  `110592` `(``108.0` `KiB)` `/``system``/``lib``/``libmediandk.so``libmedia_jni.so` `0xe2704000`  `425984` `(``416.0` `KiB)` `/``system``/``lib``/``libmedia_jni.so``libmidi.so` `0xe2799000`  `94208` `(``92.0` `KiB)` `/``system``/``lib``/``libmidi.so``libmtp.so` `0xe2851000`  `176128` `(``172.0` `KiB)` `/``system``/``lib``/``libmtp.so``libexif.so` `0xe280d000`  `204800` `(``200.0` `KiB)` `/``system``/``lib``/``libexif.so``libGLESv3.so` `0xe26cf000`  `90112` `(``88.0` `KiB)` `/``system``/``lib``/``libGLESv3.so``libjnigraphics.so` `0xe26a8000`  `12288` `(``12.0` `KiB)` `/``system``/``lib``/``libjnigraphics.so``libneuralnetworks.so` `0xe240d000`  `2306048` `(``2.2` `MiB)` `/``system``/``lib``/``libneuralnetworks.so``libtextclassifier_hash.so` `0xe264b000`  `28672` `(``28.0` `KiB)` `/``system``/``lib``/``libtextclassifier_hash.so``android.hardware.neuralnetworks@``1.0``.so` `0xe2390000`  `430080` `(``420.0` `KiB)` `/``system``/``lib``/``android.hardware.neuralnetworks@``1.0``.so``libOpenMAXAL.so` `0xe237b000`  `16384` `(``16.0` `KiB)` `/``system``/``lib``/``libOpenMAXAL.so``libOpenSLES.so` `0xe231e000`  `16384` `(``16.0` `KiB)` `/``system``/``lib``/``libOpenSLES.so``libRS.so` `0xe22c7000`  `81920` `(``80.0` `KiB)` `/``system``/``lib``/``libRS.so``android.hardware.renderscript@``1.0``.so` `0xe220a000`  `667648` `(``652.0` `KiB)` `/``system``/``lib``/``android.hardware.renderscript@``1.0``.so``libwebviewchromium_plat_support.so` `0xe21c2000`  `20480` `(``20.0` `KiB)` `/``system``/``lib``/``libwebviewchromium_plat_support.so``libjavacore.so` `0xe214f000`  `282624` `(``276.0` `KiB)` `/``system``/``lib``/``libjavacore.so``libopenjdk.so` `0xe0a05000`  `233472` `(``228.0` `KiB)` `/``system``/``lib``/``libopenjdk.so``libssl.so` `0xe0a9a000`  `307200` `(``300.0` `KiB)` `/``system``/``lib``/``libssl.so``libopenjdkjvm.so` `0xe0a4a000`  `40960` `(``40.0` `KiB)` `/``system``/``lib``/``libopenjdkjvm.so``libart``-``compiler.so` `0xe0769000`  `2711552` `(``2.6` `MiB)` `/``system``/``lib``/``libart``-``compiler.so``libart``-``dexlayout.so` `0xe0703000`  `237568` `(``232.0` `KiB)` `/``system``/``lib``/``libart``-``dexlayout.so``libsoundpool.so` `0xddf1f000`  `53248` `(``52.0` `KiB)` `/``system``/``lib``/``libsoundpool.so``libjavacrypto.so` `0xddec4000`  `217088` `(``212.0` `KiB)` `/``system``/``lib``/``libjavacrypto.so``android.hardware.graphics.mapper@``2.0``-``impl.so` `0xddd71000`  `45056` `(``44.0` `KiB)` `/``system``/``vendor``/``lib``/``hw``/``android.hardware.graphics.mapper@``2.0``-``impl.so``libcompiler_rt.so` `0xddd0b000`  `217088` `(``212.0` `KiB)` `/``system``/``lib``/``libcompiler_rt.so``libwebviewchromium_loader.so` `0xddc7b000`  `16384` `(``16.0` `KiB)` `/``system``/``lib``/``libwebviewchromium_loader.so``frida``-``agent``-``32.so`                             `0xcea80000`  `23855104` `(``22.8` `MiB)` `/``data``/``local``/``tmp``/``re.frida.server``/``frida``-``agent``-``32.so``base.odex` `0xd0780000`  `262144` `(``256.0` `KiB)` `/``data``/``app``/``com.ilulutv.fulao2``-``TRtWkDMSd4YzhkgjSGJtqQ``=``=``/``oat``/``x86``/``base.odex``libtcb.so` `0xe000000`   `675840` `(``660.0` `KiB)` `/``system``/``lib``/``arm``/``nb``/``libtcb.so``libEGL_emulation.so` `0xc8f14000`  `81920` `(``80.0` `KiB)` `/``system``/``vendor``/``lib``/``egl``/``libEGL_emulation.so``libOpenglSystemCommon.so` `0xc8c68000`  `40960` `(``40.0` `KiB)` `/``system``/``vendor``/``lib``/``libOpenglSystemCommon.so``lib_renderControl_enc.so` `0xc8eea000`  `45056` `(``44.0` `KiB)` `/``system``/``vendor``/``lib``/``lib_renderControl_enc.so``libGLESv2_enc.so` `0xc8c84000`  `405504` `(``396.0` `KiB)` `/``system``/``vendor``/``lib``/``libGLESv2_enc.so``libGLESv1_enc.so` `0xc8f43000`  `196608` `(``192.0` `KiB)` `/``system``/``vendor``/``lib``/``libGLESv1_enc.so``libOpenglCodecCommon.so` `0xc8e92000`  `139264` `(``136.0` `KiB)` `/``system``/``vendor``/``lib``/``libOpenglCodecCommon.so``libGLESv1_CM_emulation.so` `0xc8c1d000`  `81920` `(``80.0` `KiB)` `/``system``/``vendor``/``lib``/``egl``/``libGLESv1_CM_emulation.so``libGLESv2_emulation.so` `0xc8950000`  `110592` `(``108.0` `KiB)` `/``system``/``vendor``/``lib``/``egl``/``libGLESv2_emulation.so``gralloc.vbox86.so` `0xc7bcc000`  `32768` `(``32.0` `KiB)` `/``system``/``vendor``/``lib``/``hw``/``gralloc.vbox86.so``linux``-``vdso.so.``1`                               `0xeccc0000`  `4096` `(``4.0` `KiB)        linux``-``vdso.so.``1``linker` `0xeccc1000`  `1146880` `(``1.1` `MiB)` `/``system``/``bin``/``linker` |
|-|-|

列出 内存中 某一动态库 的详细导出函数

| 1 | `# memory list exports libGLESv1_enc.so` |
|-|-|

![picture 16](https://bbs.kanxue.com/upload/attach/202311/304186_XGW42H68C3BJSWM.png)

| 1 | `#  memory list exports libGLESv1_enc.so --json /root/Desktop/ulao.ligbcipher.json` |
|-|-|

![picture 17](https://bbs.kanxue.com/upload/attach/202311/304186_Y567NFV5EQYENTX.png)

![picture 18](https://bbs.kanxue.com/upload/attach/202311/304186_YF2C7QFVRK648CC.png)

这样可以看到所有的某个动态库的导出函数.

## 内存堆搜索与执行

### 在堆上搜索实例

安卓通过, Bitmap这个类来加载图片
![picture 22](https://bbs.kanxue.com/upload/attach/202311/304186_23FYTJBF8MJ5T2D.png)

当我们启动APP时候.
![picture 23](https://bbs.kanxue.com/upload/attach/202311/304186_K7P72UV23B8EY7Q.png)

出现图片, 所以发现存在着Bitmap类，可以在堆上搜索是否存在着该类的实例

显示内存中的图片, Android内存中,图片资源一般以 Bitmap方式显示

| 1 | `android heap search instances android.graphics.Bitmap` |
|-|-|

![picture 20](https://bbs.kanxue.com/upload/attach/202311/304186_NYKBFGBKC5FYS3F.png)

![picture 19](https://bbs.kanxue.com/upload/attach/202311/304186_GFBF8JYVDXFDKNU.png)

### 调用实例的方法

查看google android api 得知 Bitmap 类有着getHeight()方法，这样就可以直接调用该实例的getHeight()方法得到图片高，用excute命令。返回使用 --return-string

| 1234567891011 | `# android heap execute 125528671 getHeight --return-string``Handle` `125528671` `is` `to` `class``android.graphics.Bitmap``Executing method: getHeight()``1731` `# android heap execute 125528671 getWidth``Handle` `125528671` `is` `to` `class``android.graphics.Bitmap``Executing method: getWidth()``1080` |
|-|-|

![picture 20](https://bbs.kanxue.com/upload/attach/202311/304186_NYKBFGBKC5FYS3F.png)
 ![picture 21](https://bbs.kanxue.com/upload/attach/202311/304186_7H53GK3TNV4EFE2.png)

### 在实例上执行js代码 ( 如果 API 带参数怎么办 )

实例上直接编写js脚本(使用evaluate参数可以)，输入android heap evaluate 125528671命令后，会进入一个迷你编辑器环境，输入console.log(clazz.getPixel(10,20))这串脚本，按ESC退出编辑器，然后按回车，即会开始执行这串脚本，输出结果

| 12345 | `# android heap evaluate 125528671``(The hashcode at ```125528671``` will be available as the `clazz` variable.)` `JavaScript edit mode. [ESC]` `and` `then [ENTER] to accept. [CTRL]` `+` `C to cancel.``（“``125528671``”处的哈希码将作为“clazz”变量提供。` |
|-|-|

没有结果,原来是 没有打印. console.log

| 1234567 | `# android heap evaluate 125528671``(The hashcode at ```125528671``` will be available as the `clazz` variable.)``console.log(clazz.getPixel(``10``,``20``))``JavaScript capture complete. Evaluating...``Handle` `125528671` `is` `to` `class``android.graphics.Bitmap``-``1189677` |
|-|-|

因为里面的一些API是需要传递传输的, functionA(x,y) 这样,需要传递参数.

### 主动调用(事实上,上面已经做了讲解,这里陈述非常明确)

主动调用APP的内部的 API获取返回结果

### 启动activity或service

查看当前可用的activity

| 123456789101112131415161718192021222324252627282930 | `# android hooking list activities``cn.bingoogolapple.swipebacklayout.BaseSwipeBackActivity``com.google.android.gms.common.api.GoogleApiActivity``com.ilulutv.fulao2.actor.ActorProfileActivity``com.ilulutv.fulao2.explore.RankingActivity``com.ilulutv.fulao2.explore.longfilm.CategoryActivity``com.ilulutv.fulao2.film.PlayerActivity``com.ilulutv.fulao2.``filter``.FilterActivity``com.ilulutv.fulao2.main.MainActivity``com.ilulutv.fulao2.me.account.AccountActivity``com.ilulutv.fulao2.me.account.ChangePasswordActivity``com.ilulutv.fulao2.me.account.ResetPasswordActivity``com.ilulutv.fulao2.me.contract.AppealActivity``com.ilulutv.fulao2.me.contract.BuyMemberActivity``com.ilulutv.fulao2.me.contract.ContractManagementActivity``com.ilulutv.fulao2.me.coupon.CouponActivity``com.ilulutv.fulao2.me.coupon.ShareActivity``com.ilulutv.fulao2.me.news.NewsActivity``com.ilulutv.fulao2.me.news.NewsDetailActivity``com.ilulutv.fulao2.me.policy.PolicyActivity``com.ilulutv.fulao2.me.setting.SettingActivity``com.ilulutv.fulao2.me.watchHistory.WatchHistoryActivity``com.ilulutv.fulao2.offline.OfflineListActivity``com.ilulutv.fulao2.offline.OfflinePlayerActivity``com.ilulutv.fulao2.screen_lock.ScreenLockActivity``com.ilulutv.fulao2.search.SearchActivity``com.ilulutv.fulao2.search.result.SearchResultActivity``com.ilulutv.fulao2.welcome.WelcomeActivity` `Found` `27` `classes` |
|-|-|

直接启动activity

直接上代码，想要进入缓存管理界面，可以在任意界面直接运行以下代码进入

| 123 | `android intent launch_activity com.ilulutv.fulao2.search.SearchActivity``(agent) Starting activity com.ilulutv.fulao2.search.SearchActivity...``(agent) Activity successfully asked to start.` |
|-|-|

![picture 24](https://bbs.kanxue.com/upload/attach/202311/304186_K86G7TER8F9A2VA.png)

查看当前可用的广播

| 1234567891011 | `# android intent launch_activity com.ilulutv.fulao2.offline.OfflineListActivity``(agent) Starting activity com.ilulutv.fulao2.offline.OfflineListActivity...``(agent) Activity successfully asked to start.``com.ilulutv.fulao2 on (Google:` `9``) [usb]` `# android hooking list receivers``com.crashlytics.android.core.DevicePowerStateListener$``1``com.crashlytics.android.core.DevicePowerStateListener$``2``com.google.android.gms.analytics.AnalyticsReceiver``com.google.android.gms.measurement.AppMeasurementReceiver``com.google.firebase.iid.FirebaseInstanceIdReceiver` `Found` `5` `classes` |
|-|-|

查看当前可用的services

| 12345678910111213 | `# android hooking list services``androidx.room.MultiInstanceInvalidationService``c.b.a.b.c.e.t``com.google.android.gms.analytics.AnalyticsJobService``com.google.android.gms.analytics.AnalyticsService``com.google.android.gms.measurement.AppMeasurementJobService``com.google.android.gms.measurement.AppMeasurementService``com.google.firebase.components.ComponentDiscoveryService``com.ilulutv.fulao2.other.OnClearFromRecentService``com.ilulutv.fulao2.other.service.RemoveApkService``com.ilulutv.fulao2.service.DownloadService` `Found` `10` `classes` |
|-|-|

反编译情况下直接搜索类名,就可以直接得到它的源码

直接启动services

| 12 | `# android intent launch_service com.ilulutv.fulao2.other.service.RemoveApkService``(agent) Starting service com.ilulutv.fulao2.other.service.RemoveApkService...` |
|-|-|

把所有的 安卓图片加载函数, 在内存中的展现形式全部列出来.
android.graphics.Bitmap

| 12345 | `# android hooking watch class android.graphics.Bitmap``(agent) Hooking android.graphics.Bitmap.access$``000``(android.os.Parcel)``(agent) Hooking android.graphics.Bitmap.checkHardware(java.lang.String)``(agent) Hooking android.graphics.Bitmap.checkPixelAccess(``int``,` `int``)``(agent) Hooking android.graphics.Bitmap.checkPixelsAccess(``int``,` `int``,` `int``,` `int``,` `int``,` `int``, [I)` |
|-|-|

Hook 任务可以多线程工作, 可以用job 命令进行切换/管理/终止 task.

| 1234 | `# jobs list``Job` `ID`  `Hooks` `Type``-``-``-``-``-``-`  `-``-``-``-``-`  `-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``913209`    `129`  `watch``-``class` `for``: android.graphics.Bitmap` |
|-|-|

APP 界面只要有加载的图片就会触发.显示出来

| 123456 | `# (agent) [913209] Called android.graphics.Bitmap.nativeHasAlpha(long)``(agent) [``913209``] Called android.graphics.Bitmap.nativeHasAlpha(``long``)``(agent) [``913209``] Called android.graphics.Bitmap.nativeHasAlpha(``long``)``(agent) [``913209``] Called android.graphics.Bitmap.nativeHasAlpha(``long``)``(agent) [``913209``] Called android.graphics.Bitmap.nativeIsPremultiplied(``long``)``....` |
|-|-|

终止 有加载的图片 的 hooking

| 1 | `# jobs kill 913209` |
|-|-|

继续hook 加载的子函数,主要APi都会被触发

| 1234567891011121314 | `# android hooking watch class_method android.graphics.Bitmap.nativeRowBytes --dump-args --dump-backtrace --dump-return``(agent) Attempting to watch` `class` `android.graphics.Bitmap` `and` `method nativeRowBytes.``(agent) Hooking android.graphics.Bitmap.nativeRowBytes(``long``)``(agent) Registering job` `401763.` `Type``: watch``-``method` `for``: android.graphics.Bitmap.nativeRowBytes``com.ilulutv.fulao2 on (Google:` `11``) [usb]` `# (agent) [401763] Called android.graphics.Bitmap.nativeRowBytes(long)``(agent) [``401763``] Backtrace:``android.graphics.Bitmap.nativeRowBytes(Native Method)``android.graphics.Bitmap.getRowBytes(Bitmap.java:``1633``)``android.graphics.Bitmap.getByteCount(Bitmap.java:``1650``)``android.graphics.RecordingCanvas.throwIfCannotDraw(RecordingCanvas.java:``278``)``android.graphics.BaseRecordingCanvas.drawBitmap(BaseRecordingCanvas.java:``88``)``pl.droidsonroids.gif.b.draw(GifDrawable.java:``4``)``android.widget.ImageView.onDraw(ImageView.java:``1436``)``android.view.View.draw(View.java:``22350``)` |
|-|-|

直接获取,图片数据

![picture 25](https://bbs.kanxue.com/upload/attach/202311/304186_54YKTKE8TEF6A9N.png)

![picture 26](https://bbs.kanxue.com/upload/attach/202311/304186_TC28EHVK634658D.png)

| 12345 | `# android hooking watch class_method android.graphics.BitmapFactory.decodeByteArray --dump-args --dump-backtrace --dump-return``(agent) Attempting to watch` `class` `android.graphics.BitmapFactory` `and` `method decodeByteArray.``(agent) Hooking android.graphics.BitmapFactory.decodeByteArray([B,` `int``,` `int``)``(agent) Hooking android.graphics.BitmapFactory.decodeByteArray([B,` `int``,` `int``, android.graphics.BitmapFactory$Options)``(agent) Registering job` `778699.` `Type``: watch``-``method` `for``: android.graphics.BitmapFactory.decodeByteArray` |
|-|-|

![c 1](https://bbs.kanxue.com/upload/attach/202311/304186_NCSC3A8DQESXN2W.png)

从开发的角度, 直接打调用栈,打回溯, 这个定位速度是最快的.

## objection RPC 可以直接 curl 的 RPC

直接调用 objection 的 RPC, 远程调用,被 curl 直接调用.objection自带集成flask，可以跑预置的命令，也可以自己传脚本到手机上跑

| 1 | `# objection -g com.ilulutv.fulao2 explore --enable-api` |
|-|-|

![picture 28](https://bbs.kanxue.com/upload/attach/202311/304186_55C5CYUT647MAX8.png)

| 1 | `# curl -s "http://127.0.0.1:8888/rpc/invoke/androidHookingListActivities"` |
|-|-|

![picture 29](https://bbs.kanxue.com/upload/attach/202311/304186_B3G6VW5723CGCQN.png)

| 1 | `# curl -s "http://127.0.0.1:8888/rpc/invoke/androidHookingGetClasses"` |
|-|-|

![picture 30](https://bbs.kanxue.com/upload/attach/202311/304186_KBY2VBU9SPN3H84.png)

远程调用,直接get ,并且返回(不是hook上)

| 1 | `androidHookingGetClassMethods: (className: string): Promise<string[]>` `=``> hooking.getClassMethods(className),` |
|-|-|

![picture 32](https://bbs.kanxue.com/upload/attach/202311/304186_BCJ8DHMM37KCNDK.png)

| 1 | `curl` `-``s` `-``X POST` `"http://127.0.0.1:8888/rpc/invoke/androidHookingGetClassMethods"` `-``H` `"Content-Type: application/json"` `-``d` `'{"className": "android.graphics.BitmapFactory"}'` |
|-|-|

![picture 31](https://bbs.kanxue.com/upload/attach/202311/304186_UH5G7NMA6243X4Q.png)

用法

| 1 | `androidHookingWatch: (pattern: string, watchArgs: boolean, watchBacktrace: boolean, watchRet: boolean): Promise<void>` `=``>` |
|-|-|

举例

| 1 | `# curl -s -X POST "http://127.0.0.1:8888/rpc/invoke/androidHookingWatchClass" -H "Content-Type: application/json" -d '{"clazz": "android.graphics.BitmapFactory"}'` |
|-|-|

![picture 33](https://bbs.kanxue.com/upload/attach/202311/304186_SSTUA42ZMYFGM5B.png)

![picture 34](https://bbs.kanxue.com/upload/attach/202311/304186_UMJBY235M7BZRCM.png)

相当于远程发送命令调用.

还可以上传自己的脚本调用.

## objection + DEXDump 内存暴力脱壳机

| 123 | `给有壳的APP打包``# objedtion patchapk --architecture arm64-v8a --source 20200713movetv.apk``结果失败` |
|-|-|

旧版本的脱壳命令
 ![image](https://bbs.kanxue.com/upload/attach/202401/304186_USWYQQADGJJ3Y5A.webp)
在magisk下刷机,root, 才可以处理有壳的应用.

<https://github.com/hluwa/frida-dexdump>

最新版本的 DExdump 已经不再作为 objection 的插件形式存在, 基于 Frida-tools.

| 12 | `# proxychains pip3 install frida-dexdump``# frida-dexdump -FU` |
|-|-|

![picture 35](https://bbs.kanxue.com/upload/attach/202311/304186_BJB4JDC9Z4JJVXX.png)

![picture 36](https://bbs.kanxue.com/upload/attach/202311/304186_BQ6NZKPX9XFHNQQ.png)

可以使用 jdex-gui 可以使用.

#### 确定主界面在哪个dex文件里面

 ![image](https://bbs.kanxue.com/upload/attach/202401/304186_9EK6BSDHADBNUX4.webp)

---

# 回复

## 回复 by calleng (#2)

*2023-11-14 12:44*

以上课程,我购买后的自己写的课程笔记,目前虽然有盗版课程出现,但是解决问题,还是需要作者指导. 如果喜欢r0yuse的课,可以组队学习, (需加入请留言).用少量的时间学明白基础,节省时间..

 # 参考  AD 附上 , (抄自肉丝的课)

 狗皮膏药

![image](https://bbs.kanxue.com/upload/attach/202311/304186_Q22NYCX6SN5RN4W.webp)

## 回复 by New对象处 (#3)

*2023-11-15 09:37*

"hook如果玩的好的话，小城市基本上是2万。"

## 回复 by mb_cvotgqtr (#4)

*2023-11-30 08:42*

"由于上述的Fulao 2, 2023.11月版本加装了欧洲版本的强壳, 暂时啃不动"
这个现在能啃动吗，已经啃了好多天了

## 回复 by calleng (#5)

*2023-12-2 01:19*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_cvotgqtr](https://bbs.kanxue.com/user-990294.htm)
>
>  "由于上述的Fulao 2, 2023.11月版本加装了欧洲版本的强壳, 暂时啃不动"
> 这个现在能啃动吗，已经啃了好多天了
>
>

基本，啃不动了，等到后面基础扎实后，慢慢啃。 ![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by 万里星河 (#6)

*2023-12-4 18:56*

>
> [calleng](https://bbs.kanxue.com/user-304186.htm)
>
>
>  以上课程,我购买后的自己写的课程笔记,目前虽然有盗版课程出现,但是解决问题,还是需要作者指导. 如果喜欢r0yuse的课,可以组队学习, (需加入请留言).用少量的时间学明白基础,节省时间 ...
>
>

你不说我都不知道有盗版课程

## 回复 by calleng (#7)

*2024-1-20 13:02*

2024-01-20 跟新，看来做了笔记， 还是可以查阅。

## 回复 by 小不点的纯洁 (#8)

*2024-7-24 01:40*

20200713movetv这个app可以给一下吗

## 回复 by 小不点的纯洁 (#9)

*2024-7-24 02:08*

>
> [calleng](https://bbs.kanxue.com/user-304186.htm)
>
>  2024-01-20 跟新，看来做了笔记， 还是可以查阅。
>
>

我买了课程，怎么加入

## 回复 by calleng (#10)

*2024-7-24 13:42*

笔记处于暂停状态，目前在专心弄 协议分析。

## 回复 by calleng (#11)

*2024-7-24 13:58*

但是 r0yuse 的课，已经列了大纲，还要继续深入研究他们

## 回复 by calleng (#12)

*2024-7-29 14:05*

>
> [小不点的纯洁](https://bbs.kanxue.com/user-848902.htm)
>
>  我买了课程，怎么加入
>
>

联系 r0yuse , 他可以给你. 你需要的.
