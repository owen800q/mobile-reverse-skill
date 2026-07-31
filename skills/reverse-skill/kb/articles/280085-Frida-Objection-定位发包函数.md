---
title: '[原创]Frida Objection 定位发包函数'
url: https://bbs.kanxue.com/thread-280085.htm
tid: 280085
author: Alvinlight
date: '2024-01-04'
tags: [Android安全, 原创, 基础理论, 逆向分析, 协议分析, HOOK注入]
crawled_at: '2026-07-31T14:34:54+08:00'
replies: 10
---

# Frida定位发包函数

这里以移动TV(版本为12.2) [moveTV.apk](https://bbs.kanxue.com/assets/moveTV-20231222113342-ghv374t.apk) 这个APP为例

1）切换到 ~/.objection 目录下，删除旧的objection.log，然后按下图启动APP，并使用objection附加到APP进程，运行一下命令获取APP已加载的所有类

| 12 | `objection -g com.cz.babySister explore` `//``启动APP``android hooking list classes` `//Hook``所有类` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202401/930619_3Z3BMGZSTF9UP8B.png)

2）在加载所有类后，使用exit命令退出objection，为了之后运行所产生的日志不再继续影响本次产生的日志，需将objection.log进行重命名，并保存

| 1 | `mv` `~/.objection``/objection``.log ~``/objection_moveTV``.log` |
|-|-|

3）使用`cat`命令和`grep`管道符过滤出`HttpURLConnection`和`okhttp(3)`相关类

![image](https://bbs.kanxue.com/upload/attach/202401/930619_SZKQ28MC63NYQXM.png)

4）使用`>`符号，将上面过滤出来的类重定向到txt文件中，然后通过文本编辑器快速输入多行相同的数据来补全每一行中objection命令。以vscode为例，通过win系统 `Alt + Shift +鼠标` MAC系统 `option + shift + 鼠标`的方式对每一行行首进行全选并输入以下命令

| 1 | `android hooking` `watch` `class` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202401/930619_RQGYYUPDF5VE934.png)

5）使用以下命令，将objection附加到APP上，并自动执行文件中的所有命令。由于Hook过多类可能导致APP崩溃，这时将文本中的类分批Hook分批测试就可以了

| 1 | `objection -g com.cz.babySister explore -c` `"/Users/angel/1.txt"` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202401/930619_CPT2PNPZ4VN9M6P.png)

6）将所有类Hook之后，便可以在手机上对APP进行操作，这里主要想抓到登录时的网络通信数据，所有在登录框中输入用户名和密码后点击“确定”按钮。如果objection的界面中没有任何函数被调用，说明实际发包函数并没有使用对应的框架，这是应当更换包含Hook命令的文本文件，继续通过`-c`参数执行文件中所有Hook命令，如果在objection的界面上看到一堆函数被调用，则说明框架类型确认成功。

注意：这里虽然有一堆okhttp相关字眼，但并不是使用okhttp3网络框架，而是因为httpURLconnection这个原生库底层使用的是okhttp，与okhttp3第三方网络框架不是一个概念

 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/930619_Q4YXDFWDNFQX4BD.webp)

![image](https://bbs.kanxue.com/upload/attach/202401/930619_GGSBKKH87KU5HXF.png)

7）退出objection重新进入，对Hook到的方法进一步Hook，例如选择`com.android.okhttp.HttpHandler.openConnection` 函数进一步Hook。通过传参为URL，调用关键词HttpClient 猜测发包函数可能是 `com.cz.babySister.c.a.a(HttpClients.java:22)`

![image](https://bbs.kanxue.com/upload/attach/202401/930619_27SU7W24DD2T66S.png)

8）退出objection重新进入，对判断的函数进一步Hook，发现URL和用户名密码都清晰可见

![image](https://bbs.kanxue.com/upload/attach/202401/930619_YVP3SYJCA3YFZR9.png)

‍

---

# 回复

## 回复 by Damn7Kx (#2)

*2024-1-4 11:27*

Objection定位发包函数![image](https://bbs.kanxue.com/view/img/face/86.gif)

## 回复 by Alvinlight (#3)

*2024-1-4 11:41*

>
> [Damn7Kx](https://bbs.kanxue.com/user-869843.htm)
>
>  Objection定位发包函数[em_86]
>
>

有什么问题吗，都是Frida大类的，便于搜索

## 回复 by Damn7Kx (#4)

*2024-1-4 13:02*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Alvinlight](https://bbs.kanxue.com/user-930619.htm)
>
>  有什么问题吗，都是Frida大类的，便于搜索
>
>

没问题

## 回复 by 秋狝 (#5)

*2024-1-4 13:41*

感谢分享

## 回复 by 小木马 (#6)

*2024-1-5 16:51*

直接抓包就行了，再分析请求中参数怎么生成的，一般不用去分析是哪个是发包函数

## 回复 by mb_rgfytsxo (#7)

*2024-1-6 14:42*

objection一启动马上报错，这种怎么弄
    raise result.error
frida.core.RPCException: TypeError: cannot read property 'getApplicationContext' of null
    at getApplicationContext (/script1.js:19169)
    at <anonymous> (/script1.js:19801)
    at <anonymous> (/script1.js:19157)
    at <anonymous> (frida/node_modules/frida-java-bridge/lib/vm.js:12)
    at _performPendingVmOps (frida/node_modules/frida-java-bridge/index.js:250)
    at <anonymous> (frida/node_modules/frida-java-bridge/index.js:242)
    at apply (native)
    at ne (frida/node_modules/frida-java-bridge/lib/class-factory.js:673)
    at <anonymous> (frida/node_modules/frida-java-bridge/lib/class-factory.js:651)
Asking jobs to stop...
Unloading objection agent...

## 回复 by Alvinlight (#8)

*2024-2-2 10:14*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rgfytsxo](https://bbs.kanxue.com/user-989718.htm)
>
>  objection一启动马上报错，这种怎么弄
>  raise result.error
> frida.core.RPCException: TypeError: cannot read prop ...
>
>

这个可能是objection和Frida版本不兼容，百度一下，找一个相互兼容的版本应该就可以了

## 回复 by caolinkai (#9)

*2024-2-3 16:32*

感谢分享

## 回复 by 郑z (#10)

*2024-2-23 21:06*

感谢分享![image](https://bbs.kanxue.com/view/img/face/87.gif)

## 回复 by liruohrh (#11)

*2024-7-26 20:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rgfytsxo](https://bbs.kanxue.com/user-989718.htm)
>
>  objection一启动马上报错，这种怎么弄
>  raise result.error
> frida.core.RPCException: TypeError: cannot read prop ...
>
>

  https://github.com/sensepost/objection/pull/623，可能是启动太慢了，如果是模拟器，建议用雷电，我用MUMU不行，雷电就可以
