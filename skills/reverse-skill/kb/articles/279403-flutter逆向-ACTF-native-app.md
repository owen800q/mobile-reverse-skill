---
title: '[原创]flutter逆向 ACTF native app'
url: https://bbs.kanxue.com/thread-279403.htm
tid: 279403
author: oacia
date: '2023-10-31'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:37:03+08:00'
replies: 35
---

# 前言

算了一下好长时间没打过CTF了,前两天看到ACTF逆向有道flutter逆向题就过来玩玩啦,花了一个下午做完了.说来也巧,我给DASCTF十月赛出的逆向题其中一道也是flutter,不过那题我难度降的相当之低啦,不知道有多少人做出来了呢~

# 还原函数名

flutter逆向的一大难点就是不知道`libapp.so`的函数名,虽然有工具`reflutter`可以帮助我们得到其中的符号,但是我个人认为基于对`libflutter.so`源码插桩后重编译再重打包apk的方式具有极大的不可预料性,极有可能导致apk闪退,这一题便出现了这种情况,所以接下来我将介绍的工具`blutter`是纯静态分析来还原函数名,更令人惊喜的是它提供了`IDApython`脚本来让我们可以在IDA中对函数进行重命名,而这个项目中提供的其他文件也相当好用

## blutter的编译及使用

blutter项目地址

| 1 | `https:``//github.com/worawit/blutter` |
|-|-|

在各个平台如何编译在这个项目的README.md中写的已经相当详细了,这里我就简单介绍一下Windows上的编译过程吧,注意一下这些命令需要全程运行在代理环境否则会导致无法下载

首先clone项目

| 1 | `git clone https:``//github``.com``/worawit/blutter` `--depth=1` |
|-|-|

随后运行初始化脚本

| 12 | `cd` `.\blutter\``python .\scripts\init_env_win.py` |
|-|-|

请注意,接下来我们需要打开`x64 Native Tools Command Prompt`,它可以在`Visual Studio`文件夹中找到

![image-20231031182720564](https://bbs.kanxue.com/upload/attach/202310/963320_MFVX569Z367GMZN.png)

然后运行`blutter.py`并提供`libapp.so`和`libflutter.so`的文件夹路径以及输出文件夹路径

| 1 | `python .\blutter.py ..\chall\lib\arm64-v8a\ .\output` |
|-|-|

![image-20231031183050383](https://bbs.kanxue.com/upload/attach/202310/963320_8SE9Q6XPXPQNKRG.png)

输出文件夹目录如下

![image-20231031183135453](https://bbs.kanxue.com/upload/attach/202310/963320_EXQ7X5P6KS763RX.png)

随后我们用ida反编译`libapp.so`,并运行输出文件夹中的IDApython脚本`ida_script/addNames.py`,符号就被全部恢复出来啦

![image-20231031183441477](https://bbs.kanxue.com/upload/attach/202310/963320_2YZJDCGNUYWEFE9.png)

# hook关键函数 获取函数参数

这里我们需要关注的函数是`flutter_application_1_main__LongPressDemoState::_onTap`,因为在flutter的开发中,onTap函数是按钮点击之后的响应函数

![image-20231031183702090](https://bbs.kanxue.com/upload/attach/202310/963320_7FHYGYEEZYMWY6Y.png)

随后我们进入`sub_1DE500`,在该函数中双击`sub_1DE59C`进入

![image-20231031183814522](https://bbs.kanxue.com/upload/attach/202310/963320_2NGTJ6XQQ6V2PWP.png)

在这个函数中我们发现了`256`,`%`,`^`这些特征,合理猜测一下算法可能是RC4![image-20231031185252569](https://bbs.kanxue.com/upload/attach/202310/963320_BQ4VDSEVN49PGKA.png)

![image-20231031185414233](https://bbs.kanxue.com/upload/attach/202310/963320_GM8G96YGJ2H8SBG.png)

![image-20231031185438467](https://bbs.kanxue.com/upload/attach/202310/963320_MC624UWY8EDGAN6.png)

接下来我们使用输出文件夹中的`blutter_frida.js`hook一下`sub_1DE59C`看看情况

![image-20231031185604019](https://bbs.kanxue.com/upload/attach/202310/963320_F32MESU23H6G8ZB.png)

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152 | `PS D:\hgame\ACTF\native app\work\blutter> frida -U -f` `"com.example.flutter_application_1"` `-l .\output\blutter_frida.js``[Pixel 3::com.example.flutter_application_1 ]->` `Unhandle class` `id``: 46, TypeArguments``GrowableList@6d00488c29 = [``188676,``0,``{``"key"``:` `"Unhandle class id: 46, TypeArguments"``},``34,``{``"key"``: [``184,``132,``137,``215,``146,``65,``86,``157,``123,``100,``179,``131,``112,``170,``97,``210,``163,``179,``17,``171,``245,``30,``194,``144,``37,``41,``235,``121,``146,``210,``174,``92,``204,``22``]``},``0,``0,``0``]` |
|-|-|

这里我们只hook到一个数组的值,另一个数组的类型是`TypeArguments`,研究了一下`blutter_frida.js`后发现作者还没有对这种数据类型格式提供hook支持

![image-20231031185952753](https://bbs.kanxue.com/upload/attach/202310/963320_NCJGBA8PY5RKHD3.png)

# IDA动态调试libapp.so

现在我们得到了一个数组,我们就暂时认为它就是flag经过加密之后得到的结果,接下来我们在IDA中对`sub_1DE59C`下断点动态调试来更加深入的研究一下

首先我们需要将IDA文件夹中的`dbgsrv/android_server64` push到手机上面,然后运行一下并且指定端口

| 123 | `blueline:``/data/local/tmp` `# ./as64 -p 11112``IDA Android 64-bit remote debug server(ST) v7.7.27. Hex-Rays (c) 2004-2022``Listening on 0.0.0.0:11112...` |
|-|-|

随后端口转发一下

| 12 | `PS C:\Users\oacia> adb forward tcp:11112 tcp:11112``11112` |
|-|-|

在IDA中选择调试器为`Android debugger`

![image-20231031190502580](https://bbs.kanxue.com/upload/attach/202310/963320_CWU2U7SEGDTUXEV.png)

随后点击`Debugger->Debugger options...`选择如下配置

![image-20231031190621711](https://bbs.kanxue.com/upload/attach/202310/963320_3WDWY3VANC7XDVA.png)

点击`Debugger->Process options...`,`Hostname`修改为`127.0.0.1`,`Port`修改为`11112`

![image-20231031190653343](https://bbs.kanxue.com/upload/attach/202310/963320_F5ZXSQ9S9F8PRHS.png)

然后点击`Debugger->Attach to process...`,附加到我们目标包名的进程上面

![image-20231031190932527](https://bbs.kanxue.com/upload/attach/202310/963320_T5PNZXHPZ2V2K83.png)

弹出该弹窗选择Same即可

![image-20231031191001330](https://bbs.kanxue.com/upload/attach/202310/963320_6DSHQUM3QAC9W9H.png)

在手机上点击按钮,然后在IDA中点击这个绿色的剪头,就可以动态调试啦

![image-20231031191049306](https://bbs.kanxue.com/upload/attach/202310/963320_RYU2BUUNECY5R5J.png)

![image-20231031191123141](https://bbs.kanxue.com/upload/attach/202310/963320_EJZA7BBN43NHQRT.png)

在动态调试之后,未知的变量也逐渐浮现了出来,这里我们发现了`v28>=256`,那么很有可能就是RC4了哦

![image-20231031191544680](https://bbs.kanxue.com/upload/attach/202310/963320_EDRUMJUKRPN897U.png)

既然这样,那么直接在这里唯一的异或的地方用IDA去trace一下,把异或的数组dump下来不就行了:)

![image-20231031192301154](https://bbs.kanxue.com/upload/attach/202310/963320_6F573XUGZBVAAEV.png)

于是我们得到了被异或的数组了

![image-20231031193001825](https://bbs.kanxue.com/upload/attach/202310/963320_B6TPMVQNHB8SVQ2.png)

但是在异或运算的地方下断点之后,我输入的数全都是`1`,这里被异或的数也全是`0xce`

![image-20231031194118997](https://bbs.kanxue.com/upload/attach/202310/963320_VAG2DFT5HDT9V4E.png)

所以莫非不是RC4?让0xce和`0x31`异或一下看看,竟然是`0xff`这么有意义的数字

![image-20231031194218233](https://bbs.kanxue.com/upload/attach/202310/963320_J7YU5M4WFBEMB2P.png)

所以exp也就能写出来啦~

| 12345678 | `final` `=` `[``184``,` `132``,` `137``,` `215``,` `146``,` `65``,` `86``,` `157``,` `123``,` `100``,` `179``,` `131``,` `112``,` `170``,` `97``,` `210``,` `163``,` `179``,` `17``,` `171``,` `245``,` `30``,` `194``,``144``,` `37``,` `41``,` `235``,` `121``,` `146``,` `210``,` `174``,` `92``,` `204``,` `22``]``xor` `=` `[``14``,` `14``,` `68``,` `80``,` `29``,` `201``,` `241``,` `46``,` `197``,` `208``,` `123``,` `79``,` `187``,` `55``,` `234``,` `104``,` `40``,` `117``,` `133``,` `12``,` `67``,` `137``,` `91``,` `31``,` `136``,``177``,` `64``,` `234``,` `24``,` `27``,` `26``,` `214``,` `122``,` `217``]` `flag` `=` `[``chr``(xor[i]^final[i]^``0xff``)` `for` `i` `in` `range``(``len``(final))]``print``(''.join(flag))``# Iu2xpwXLAK734btEt9kXIhfpRgTlu6KuI0` |
|-|-|

上传的附件：
- native app.zip.001

（8.00MB，157次下载）
- native app.zip.002

（8.00MB，141次下载）
- native app.zip.003

（1.09MB，128次下载）

---

# 回复

## 回复 by 果冻大砍刀 (#2)

*2023-10-31 23:01*

好贴,火钳刘明,明天试试手动复现一下

## 回复 by 秋狝 (#3)

*2023-11-1 09:50*

感谢分享

## 回复 by hpphpp (#4)

*2023-11-1 10:58*

flutter IDA动态调试断下一段时间后经常会无法恢复运行,然后报错

## 回复 by oacia (#5)

*2023-11-1 11:34*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  hpphpp](https://bbs.kanxue.com/user-226208.htm)
>
>  flutter IDA动态调试断下一段时间后经常会无法恢复运行,然后报错
>
>

先在输入框中输入字符串之后再点按钮,然后到IDA中点击绿色的箭头来动态调试,要是在IDA运行的时候弹出小键盘的话会有概率导致无法运行的

## 回复 by mb_eiaothcj (#6)

*2023-11-1 16:44*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>  先在输入框中输入字符串之后再点按钮,然后到IDA中点击绿色的箭头来动态调试,要是在IDA运行的时候弹出小键盘的话会有概率导致无法运行的
>
>

楼主，现在flutter app的抓包有什么工具么，最近遇到的几个只要一抓包就直接掉登录，之前的hook方法不起效果，wireshark抓包走的是https![image](https://bbs.kanxue.com/view/img/face/47.gif)，直接尬住了

## 回复 by wugming (#7)

*2023-11-2 18:06*

1、作者源码中只有这两种架构：EM_AARCH64、EM_IA_64，而我的so文件是em_arm架构，走到这里就报错了。

![image](https://bbs.kanxue.com/upload/attach/202311/989426_FA872C4K5FKJC4Y.webp)

2、修改了一下问题一里的架构判断，先绕了过去，后边又出现了报错，经过调试发现:executable为None,导致系统找不到要启动的进程

![image](https://bbs.kanxue.com/upload/attach/202311/989426_8AT3EG87VVE8KEJ.webp)

希望能够得到帮助。。。

## 回复 by zx_958536 (#8)

*2023-11-4 18:49*

感谢分享

## 回复 by hpphpp (#9)

*2023-11-6 11:59*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>  先在输入框中输入字符串之后再点按钮,然后到IDA中点击绿色的箭头来动态调试,要是在IDA运行的时候弹出小键盘的话会有概率导致无法运行的
>
>

即使调试自己的app,不涉及输入,断下分析一段时间后也会无法恢复,不知道怎么回事.

## 回复 by mb_ezphxtar (#10)

*2023-11-6 14:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_eiaothcj](https://bbs.kanxue.com/user-977000.htm)
>
>  楼主，现在flutter app的抓包有什么工具么，最近遇到的几个只要一抓包就直接掉登录，之前的hook方法不起效果，wireshark抓包走的是https[em_47]，直接尬住了
>
>

hookssl无效么?

## 回复 by mb_eiaothcj (#11)

*2023-11-9 00:36*

>
> [mb_ezphxtar](https://bbs.kanxue.com/user-909258.htm)
>
>  hookssl无效么?
>
>

不是一定要走ssl的，而且那个方法都出来多久了，老早不管用了

## 回复 by mb_ezphxtar (#12)

*2023-11-9 09:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_eiaothcj](https://bbs.kanxue.com/user-977000.htm)
>
>  不是一定要走ssl的，而且那个方法都出来多久了，老早不管用了
>
>

可否分享下app研究下?

## 回复 by 万里星河 (#13)

*2023-11-10 22:21*

支持一下 大佬的文章属实精彩

## 回复 by 你瞒我瞒 (#14)

*2023-11-13 15:49*

大佬你的博客崩溃了

## 回复 by oacia (#15)

*2023-11-13 16:39*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  大佬你的博客崩溃了
>
>

不是崩了是域名过期了![image](https://bbs.kanxue.com/view/img/face/78.gif)这个月比较忙,下个月初我把域名重新买回来![image](https://bbs.kanxue.com/view/img/face/84.gif)

## 回复 by mb_pweuvgeh (#16)

*2023-11-20 17:03*

[1/22] Building CXX object CMakeFiles/blutte...vm2.19.2_android_arm64.dir/cmake_pch.hxx.gch
FAILED: CMakeFiles/blutter_dartvm2.19.2_android_arm64.dir/cmake_pch.hxx.gch
/usr/bin/c++ -DDART_COMPRESSED_POINTERS -DDART_PRECOMPILED_RUNTIME -DDART_TARGET_OS_ANDROID -DDART_TARGET_OS_WINDOWS_UWP -DEXCLUDE_CFE_AND_KERNEL_PLATFORM -DFRIDA_TEMPLATE_DIR=\"/root/blutter/scripts\" -DHAS_TYPE_REF -DNDEBUG -DPRODUCT -DTARGET_ARCH_ARM64 -DU_USING_ICU_NAMESPACE=0 -D_HAS_EXCEPTIONS=0 -I/usr/include/capstone -isystem /root/blutter/packages/include/dartvm2.19.2 -O3 -DNDEBUG -O3 -fno-rtti -fvisibility=hidden -fvisibility-inlines-hidden -fno-omit-frame-pointer -std=c++20 -Winvalid-pch -x c++-header -include /root/blutter/build/blutter_dartvm2.19.2_android_arm64/CMakeFiles/blutter_dartvm2.19.2_android_arm64.dir/cmake_pch.hxx -MD -MT CMakeFiles/blutter_dartvm2.19.2_android_arm64.dir/cmake_pch.hxx.gch -MF CMakeFiles/blutter_dartvm2.19.2_android_arm64.dir/cmake_pch.hxx.gch.d -o CMakeFiles/blutter_dartvm2.19.2_android_arm64.dir/cmake_pch.hxx.gch -c /root/blutter/build/blutter_dartvm2.19.2_android_arm64/CMakeFiles/blutter_dartvm2.19.2_android_arm64.dir/cmake_pch.hxx.cxx
In file included from /root/blutter/build/blutter_dartvm2.19.2_android_arm64/CMakeFiles/blutter_dartvm2.19.2_android_arm64.dir/cmake_pch.hxx:5,
                 from <command-line>:
/root/blutter/blutter/src/pch.h:12:10: fatal error: format: No such file or directory
   12 | #include <format>
      |          ^~~~~~~~
compilation terminated.
ninja: build stopped: subcommand failed.
Traceback (most recent call last):
  File "/root/blutter/blutter.py", line 138, in <module>
    main(args.indir, args.outdir, args.rebuild, args.vs_sln)
  File "/root/blutter/blutter.py", line 120, in main
    cmake_blutter(blutter_name, dartlib_name, macros)
  File "/root/blutter/blutter.py", line 76, in cmake_blutter
    subprocess.run([NINJA_CMD], cwd=builddir, check=True)
  File "/usr/lib/python3.11/subprocess.py", line 571, in run
    raise CalledProcessError(retcode, process.args,
subprocess.CalledProcessError: Command '['ninja']' returned non-zero exit status 1.
我己经安装 g++13 了

## 回复 by aqingadmin (#17)

*2023-12-17 01:22*

C:\Users\Administrator\Desktop\blutter-main>python blutter.py ./app ./output
Dart version: 2.17.5, Snapshot: 1441d6b13b8623fa7fbf61433abebd31, Target: android arm64
libapp is loaded at 0x236e1a40000
Dart heap at 0x23700000000
Analyzing the application
C:\Users\Administrator\Desktop\blutter-main\blutter\src\CodeAnalyzer_arm64.cpp: 124: error: expected: dartCls->Id() >= dart::kNumPredefinedCids

C:\Users\Administrator\Desktop\blutter-main> 失败了

## 回复 by xzy____ (#18)

*2023-12-21 16:35*

https://segmentfault.com/a/1190000044464286
这个文章是搬运的吗？

## 回复 by oacia (#19)

*2023-12-21 18:37*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  xzy____](https://bbs.kanxue.com/user-934947.htm)
>
>  https://segmentfault.com/a/1190000044464286
> 这个文章是搬运的吗？
>
>

看了一下应该是别的师傅参考这里的文章复现了ACTF的这题,说明我写的内容还是有意义的:)

## 回复 by zxk1ng (#20)

*2023-12-21 22:00*

师傅，我运行那个blutter_frida脚本，然后let报语法错误，您知道如何解决吗,对这个还不是很熟悉

## 回复 by 浮虚千年 (#21)

*2023-12-28 21:57*

师傅我trace有问题，一直打印出14，具体的步骤可以教一下吗

## 回复 by oacia (#22)

*2023-12-29 19:44*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ykhckzcr](https://bbs.kanxue.com/user-962964.htm)
>
>  师傅我trace有问题，一直打印出14，具体的步骤可以教一下吗
>
>

你需要点一下这个勾号确认文本框的提交

,

![image](https://bbs.kanxue.com/upload/attach/202312/963320_GDJNJE89Z5Y59A3.webp)

点击提交之后在"submitted:"后面出现你输入的字符串才算是正确的把输入给输进去了,不然你的输入就是空字符串![image](https://bbs.kanxue.com/upload/attach/202312/963320_DHK8Q84K5WR5KXB.webp)

## 回复 by Light紫星 (#23)

*2024-1-23 13:20*

感谢分享，遇到了一个flutter app，按照步骤试一下

## 回复 by shmilyaxy (#24)

*2024-1-29 16:59*

请问以下使用blutter时候提示找不到dartsdk\v3.0.2该如何处理？
C:\Users\TDTX001\Downloads\blutter-main\blutter\dartsdk\v3.0.2
Traceback (most recent call last):
  File "C:\Users\TDTX001\Downloads\blutter-main\blutter\blutter.py", line 169, in <module>
    main(args.indir, args.outdir, args.rebuild, args.vs_sln, args.no_analysis)
  File "C:\Users\TDTX001\Downloads\blutter-main\blutter\blutter.py", line 131, in main
    fetch_and_build(dart_version, arch, os_name, has_compressed_ptrs, snapshot_hash)
  File "C:\Users\TDTX001\Downloads\blutter-main\blutter\dartvm_fetch_build.py", line 122, in fetch_and_build
    outdir = checkout_dart(ver, snapshot_hash)
  File "C:\Users\TDTX001\Downloads\blutter-main\blutter\dartvm_fetch_build.py", line 53, in checkout_dart
    subprocess.run([GIT_CMD, '-c', 'advice.detachedHead=false', 'clone', '-b', ver, '--depth', '1', '--filter=blob:none', '--sparse', '--progress', DART_GIT_URL, clonedir], check=True)
  File "C:\Users\TDTX001\AppData\Local\Programs\Python\Python310\lib\subprocess.py", line 501, in run
    with Popen(*popenargs, **kwargs) as process:
  File "C:\Users\TDTX001\AppData\Local\Programs\Python\Python310\lib\subprocess.py", line 969, in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
  File "C:\Users\TDTX001\AppData\Local\Programs\Python\Python310\lib\subprocess.py", line 1438, in _execute_child
    hp, ht, pid, tid = _winapi.CreateProcess(executable, args,
FileNotFoundError: [WinError 2] 系统找不到指定的文件。

## 回复 by 宛枫 (#25)

*2024-4-1 14:12*

这是什么问题?![image](https://bbs.kanxue.com/upload/attach/202404/981250_7NE96G78U2Q2HW8.webp)

## 回复 by vVv一 (#26)

*2024-4-3 17:47*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_wizwlvbj](https://bbs.kanxue.com/user-981250.htm)
>
>  这是什么问题?
>
>

pip install pyelftools

## 回复 by ccccl1180 (#27)

*2024-4-8 15:45*

为什么hook0x1de59c的参数就是最后的生成的enc密文呢

## 回复 by ccccl1180 (#28)

*2024-4-8 15:49*

为什么hook sub_1DE59C函数的参数就是加密flag最后的enc呢

## 回复 by wx_晨梦 (#29)

*2024-4-18 17:55*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_wizwlvbj](https://bbs.kanxue.com/user-981250.htm)
>
>  这是什么问题?
>
>

少py模块  装一下就行

## 回复 by wx_晨梦 (#30)

*2024-4-18 18:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_wizwlvbj](https://bbs.kanxue.com/user-981250.htm)
>
>  这是什么问题?
>
>

python ./blutter.py C:\Users\Administrator\Desktop\1111\blutter-main\lib\arm64-v8a ./out_dir
Dart version: 2.10.5, Snapshot: 8ee4ef7a67df9845fba331734198a953, Target: android arm64
Traceback (most recent call last):
  File "./blutter.py", line 138, in <module>
    main(args.indir, args.outdir, args.rebuild, args.vs_sln)
  File "./blutter.py", line 101, in main
    fetch_and_build(dart_version, arch, os_name)
  File "C:\Users\Administrator\Desktop\1111\blutter-main\dartvm_fetch_build.py", line 109, in fetch_and_build
    outdir = checkout_dart(ver)
  File "C:\Users\Administrator\Desktop\1111\blutter-main\dartvm_fetch_build.py", line 48, in checkout_dart
    subprocess.run([GIT_CMD, '-c', 'advice.detachedHead=false', 'clone', '-b', ver, '--depth', '1', '--filter=blob:none', '--sparse', '--progress', DART_GIT_URL, clonedir], check=True)
  File "D:\PythonEnv\Python3.8.5\lib\subprocess.py", line 489, in run
    with Popen(*popenargs, **kwargs) as process:
  File "D:\PythonEnv\Python3.8.5\lib\subprocess.py", line 854, in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
  File "D:\PythonEnv\Python3.8.5\lib\subprocess.py", line 1307, in _execute_child
    hp, ht, pid, tid = _winapi.CreateProcess(executable, args,
FileNotFoundError: [WinError 2] 系统找不到指定的文件。

运行工具报错  这是什么原因

## 回复 by wx_晨梦 (#31)

*2024-4-19 20:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  xzy____](https://bbs.kanxue.com/user-934947.htm)
>
>  https://segmentfault.com/a/1190000044464286
> 这个文章是搬运的吗？
>
>

subprocess.CalledProcessError: Command '['ninja']' returned non-zero exit status 1 你这个是怎么解决的

## 回复 by wx_晨梦 (#32)

*2024-4-20 12:44*

用博主的例子APP 就可以反编译成功  别的不行  不知道为什么

## 回复 by wx_晨梦 (#33)

*2024-4-20 13:08*

-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/include/dartvm2.10.5/vm/type_testing_stubs.h
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/include/dartvm2.10.5/vm/type_testing_stubs_test.h
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/include/dartvm2.10.5/vm/unibrow-inl.h
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/include/dartvm2.10.5/vm/unibrow.h
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/include/dartvm2.10.5/vm/unit_test.h
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/include/dartvm2.10.5/vm/uri.h
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/include/dartvm2.10.5/vm/v8_snapshot_writer.h
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/include/dartvm2.10.5/vm/version.h
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/include/dartvm2.10.5/vm/virtual_memory.h
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/include/dartvm2.10.5/vm/visitor.h
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/include/dartvm2.10.5/vm/zone.h
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/include/dartvm2.10.5/vm/zone_text_buffer.h
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/lib/cmake/dartvm2.10.5_android_arm64/dartvmTarget.cmake
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/lib/cmake/dartvm2.10.5_android_arm64/dartvmTarget-release.cmake
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/lib/cmake/dartvm2.10.5_android_arm64/dartvm2.10.5_android_arm64Config.cmake
-- Installing: C:/Users/Administrator/Desktop/flutter/blutter/dartsdk/v2.10.5/../../packages/lib/cmake/dartvm2.10.5_android_arm64/dartvm2.10.5_android_arm64ConfigVersion.cmake
-- Configuring done (2.4s)
-- Generating done (0.0s)
-- Build files have been written to: C:/Users/Administrator/Desktop/flutter/blutter/build/blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis
[1/22] Building CXX object CMakeFiles\blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis.dir\cmake_pch.cxx.obj
FAILED: CMakeFiles/blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis.dir/cmake_pch.cxx.obj
"C:\PROGRA~1\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.39.33519\bin\Hostx64\x64\cl.exe"  /nologo /TP -DDART_PRECOMPILED_RUNTIME -DDART_TARGET_OS_ANDROID -DDART_TARGET_OS_WINDOWS_UWP -DEXCLUDE_CFE_AND_KERNEL_PLATFORM -DFRIDA_TEMPLATE_DIR=\"C:/Users/Administrator/Desktop/flutter/blutter/scripts\" -DHAS_SHARED_CLASS_TABLE -DHAS_TYPE_REF -DNDEBUG -DNO_CODE_ANALYSIS -DNO_INIT_LATE_STATIC_FIELD -DNO_LAST_INTERNAL_ONLY_CID -DOLD_MAP_NO_IMMUTABLE -DOLD_MAP_SET_NAME -DPRODUCT -DTARGET_ARCH_ARM64 -DU_USING_ICU_NAMESPACE=0 -D_HAS_EXCEPTIONS=0 -external:IC:\Users\Administrator\Desktop\flutter\blutter\packages\include\dartvm2.10.5 -external:IC:\Users\Administrator\Desktop\flutter\blutter\blutter\..\external\capstone\include\capstone -external:W0 /DWIN32 /D_WINDOWS /EHsc /O2 /Ob2 /DNDEBUG -std:c++20 -MD /Oy /GR- /sdl- /Oi /GL /Gy /Zc:wchar_t /Zc:inline /YcC:/Users/Administrator/Desktop/flutter/blutter/build/blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis/CMakeFiles/blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis.dir/cmake_pch.hxx /FpC:/Users/Administrator/Desktop/flutter/blutter/build/blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis/CMakeFiles/blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis.dir/./cmake_pch.cxx.pch /FIC:/Users/Administrator/Desktop/flutter/blutter/build/blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis/CMakeFiles/blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis.dir/cmake_pch.hxx /showIncludes /FoCMakeFiles\blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis.dir\cmake_pch.cxx.obj /FdCMakeFiles\blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis.dir\ /FS -c C:\Users\Administrator\Desktop\flutter\blutter\build\blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis\CMakeFiles\blutter_dartvm2.10.5_android_arm64_no-compressed-ptrs_no-analysis.dir\cmake_pch.cxx
C:/Users/Administrator/Desktop/flutter/blutter/blutter/src/pch.h(43): error C2061: 语法错误: 标识符“LinkedHashSet”
C:/Users/Administrator/Desktop/flutter/blutter/blutter/src/pch.h(46): error C2061: 语法错误: 标识符“LinkedHashSet”
C:/Users/Administrator/Desktop/flutter/blutter/blutter/src/pch.h(54): error C2065: “kLinkedHashSetCid”: 未声明的标识符
C:/Users/Administrator/Desktop/flutter/blutter/blutter/src/pch.h(57): error C2065: “kLinkedHashSetCid”: 未声明的标识符
ninja: build stopped: subcommand failed.
Traceback (most recent call last):
  File "blutter.py", line 168, in <module>
    main(args.indir, args.outdir, args.rebuild, args.vs_sln, args.no_analysis)
  File "blutter.py", line 149, in main
    cmake_blutter(blutter_name, dartlib_name, name_suffix, macros)
  File "blutter.py", line 92, in cmake_blutter
    subprocess.run([NINJA_CMD], cwd=builddir, check=True)
  File "D:\PythonEnv\Python3.8.5\lib\subprocess.py", line 512, in run
    raise CalledProcessError(retcode, process.args,
subprocess.CalledProcessError: Command '['ninja']' returned non-zero exit status 1.这个是什么原因导致的

## 回复 by 请让我任性下 (#34)

*2024-6-22 13:50*

有没有大佬能指点一下的报错

![image](https://bbs.kanxue.com/upload/attach/202406/739668_UQ7QJWTNNSTQQRQ.webp)

## 回复 by 日暮归途 (#35)

*2024-9-1 00:51*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  请让我任性下](https://bbs.kanxue.com/user-739668.htm)
>
>  有没有大佬能指点一下的报错
>
>

你解决了没= =

## 回复 by jfztaq (#36)

*2024-9-1 06:18*

好详细，感谢
