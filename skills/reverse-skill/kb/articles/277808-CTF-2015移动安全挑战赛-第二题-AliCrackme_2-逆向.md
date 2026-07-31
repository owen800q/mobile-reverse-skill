---
title: '[原创]CTF 《2015移动安全挑战赛》第二题 AliCrackme_2 逆向'
url: https://bbs.kanxue.com/thread-277808.htm
tid: 277808
author: 行简
date: '2023-06-28'
tags: [Android安全, 原创, 逆向分析, 漏洞相关, HOOK注入]
crawled_at: '2026-07-31T14:42:17+08:00'
replies: 1
---

# 0x01 前言

路漫漫其修远兮，吾将上下而求索。
看雪ctf板块中：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_2F528UFADDGUATP.png)

# 0x02 入手点定位

安装apk，需逆向寻找正缺的密码：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_JZDPS3U885GW7B7.png)
将AliCrackme_2.apk使用jadx打开，从提示信息入手，搜索：校验码校验失败。
可定位到MainActivity中onCreate()方法中的onClick()方法：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_CHVJ58B5TBEMYW7.png)
获取用户输入后，使用 securityCheck() 方法检查 result 变量中的验证码是否通过校验。
从代码中可以看出securityCheck()是个native方法，需在so文件中进行分析。
目标明确了分析libcrackme.so文件中的securityCheck()方法。

# 0x03 so 静态分析

ida打开so文件，Function界面搜索securityCheck即可定位到该函数，双击进入后按F5反汇编，将函数的参数一和参数二改写：JNIEnv *env, jobject obj。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_YMRQG6DGKFUD7QJ.png)
主要看一下这几行代码，一并写好注释了：

| 123456789101112131415 | `v5` `=` `(``*``env)``-``>GetStringUTFChars(env, password,` `0``);` `/``/` `v5为用户输入的密码``v6` `=` `off_628C;` `/``/` `off_628C：aWojiushidaan``while` `(` `1` `)` `/``/` `while``循环判断用户输入内容``{``v7` `=` `*``v6;` `/``/` `v6 指针所指向的地址中的字符，赋值给 v7 变量``if` `( v7 !``=` `*``v5 )` `/``/` `检查 v7 和 v5 变量中存储的字符是否相等。如果不相等，则跳出循环。``break``;``+``+``v6;` `/``/` `这两行代码将 v6 和 v5 的值递增，使它们指向下一个字符。``+``+``v5;``v8` `=` `1``;` `if` `( !v7 )` `/``/` `如果 v7 中的字符为空（即字符串结束符），则返回 v8 的值。``return` `v8;` `}``return` `0``;` `/``/` `如果前面的循环没有提前退出并且未返回 v8 的值，则说明字符串不匹配，函数返回` `0` `表示不相等。``}` |
|-|-|

看似 aWojiushidaan 这串字符就是密码了，输入依旧报：校验码校验失败。
果然没那么简单！！！

# 0x04 反调试方式确认

题目中已给出说明：程序中利用So反调试。既然有反调试，那肯定得进行反反调试。
首先用firda进行附加，发现程序并不会推出，代码也能正常附加，那么就不是反frida调试了！
再用ida进行调试，发现一附加程序就关闭，可以确定是反ida调试，那么就需要进一步确定是什么反调方式了。
我很不赞同一个点，那就是无论什么apk有反调施就从零开始一步一步分析，不是不行是费时间。大可先从常见的反调手段入手。

## 4.1 IDA调试端口检测

读取/proc/net/tcp，查找IDA远程调试所用的23946端口，若发现说明进程正在被IDA调试。
反反调试：
更改IDA调式默认端口：

| 1 | `root@phone:``/``data``/``local``/``tmp` `# ./as_64 -p12346` |
|-|-|

附加程序关闭，要么就是不是检测这个，要么就是还有别的检测手段，继续分析。

## 4.2 特征文件检测

android_server 特征文件名检测，我这边已经更改过文件名，附加程序关闭，继续分析。

## 4.3 Tracepid 检测

安卓的native下，通过读取进程的status或stat来检测Tracepid ，它主要原理是调试状态下的进程Tracepid不为0。
当检测到Tracepid 不为0时，app会kill掉进程，从而达到反调试的目的。
一般情况下当 app 只有一个进程时，附加后程序不会立即退出，而是等待运行到相关退出函数时才会退出，原因很简单，只有一个进程时程序会断下但没办法继续往下执行，便不能够杀死自己，针对这种情况一般会 fork 出一个子进程，让子进程负责 kill 父进程，再优化便是父子进程相互检测是否被调试。
反反调试：
让Tracepid在调试的状态下，Tracepid 仍然为0，并且以为万一让kill失效，但能让 app 退出的函数并不止这一个。
编写hook代码：

| 12345678910111213141516171819 | `function Tracepid() {``console.warn(``"............."``)``var fgetsPtr` `=` `Module.findExportByName(``"libc.so"``,` `"fgets"``);``var fgets` `=` `new NativeFunction(fgetsPtr,` `'pointer'``, [``'pointer'``,` `'int'``,` `'pointer'``]);``Interceptor.replace(fgetsPtr, new NativeCallback(function (``buffer``, size, fp) {``var retval` `=` `fgets(``buffer``, size, fp);``var bufstr` `=` `Memory.readUtf8String(``buffer``);``if` `(bufstr.indexOf(``"TracerPid:"``) >` `-``1``) {``Memory.writeUtf8String(``buffer``,` `"TracerPid:\t0"``);``}``return` `retval;``},` `'pointer'``, [``'pointer'``,` `'int'``,` `'pointer'``]));``var killptr` `=` `Module.findExportByName(``"libc.so"``,` `"kill"``);``var kill` `=` `new NativeFunction(fgetsPtr,` `'int'``, [``'int'``,` `'int'``]);``Interceptor.replace(killptr, new NativeCallback(function (pid,sig) {``console.log(``"kill"``)``return` `0``;``},` `'int'``, [``'int'``,` `'int'``]));``}` |
|-|-|

frida 先执行hook代码后，ida进行附加调试，程序并不退出，反调试点就确定了，Tracepid值检测。

# 0x05 so 动态分析

ida 调试后,按G输入：Java_com_yaotong_crackme_MainActivity_securityCheck，进行跳转，再定位到如图位置，按下tab键，查看汇编代码：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_PS6K8DJPPG563BG.png)
可以发现此处从原来的：wojiushidaan，变成了：aiyou,bucuoo。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_S6C67Q6G7MWNRRG.png)
输入字符：aiyou,bucuoo，跳到如下界面，破解成功：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_GXF8GKXN6E2W69S.png)

此处还有一个坑，虽说破解成功，但使用ida进行调试时总是失败，仅可以附加查看信息，不可下断点进行调试。
最后找到原因时应为应用程序本身未开启debuggable权限，需要在AndroidMinifest.xml文件中添加android:debuggable="true"后进行重编译！
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_2RTS6M88W3AVVQQ.png)

还有一个办法就是使用 mprop 工具修改 ro.debuggable 的值修改为 1，这个方法就是有个缺点，没此手机重启都需重新操作一边：
下载 mprop 工具：<https://github.com/wpvsyou/mprop> ，具体操作步骤如下：

| 12345678910 | `adb push mprop` `/``data``/``local``/``tmp` `# 将下载好的 mprop 工具放入 /data/local/tmp 当中``adb shell``su``cat default.prop \| grep debug` `# 查看default.prop里面的配置值，此处是 0``getprop ro.debuggable` `# 获取ro.debuggable 此处应该是 0``cd` `/``data``/``local``/``tmp``chmod` `777` `mprop` `# 修改权限``.``/``mprop ro.debuggable` `1`       `# 修改 ro.debuggable 1 的值为 1``cat default.prop \| grep debug` `# 查看default.prop里面的配置值，此处是应该还是 0``getprop ro.debuggable` `# 获取 ro.debuggable 此处应该是 1` |
|-|-|

修改完成后，执行命令adb shell getprop | findstr debuggable查看手机的ro.debuggable参数值。
提示：[ro.debuggable]: [1] 即成功。
至此完结。

---

# 回复

## 回复 by 秋狝 (#2)

*2023-11-12 22:55*

感谢分享
