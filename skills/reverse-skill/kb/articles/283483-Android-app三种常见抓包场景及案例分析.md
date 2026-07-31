---
title: '[原创]Android app三种常见抓包场景及案例分析'
url: https://bbs.kanxue.com/thread-283483.htm
tid: 283483
author: scllqk
date: '2024-09-15'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:20:30+08:00'
replies: 18
---

## 一、未校验：配置证书就能抓

1.这种情况是最简单的情况，Android 7.0之前的设备，直接配置用户证书，就能进行抓包，Android 7.0之后的设备，需要获取root权限1后，把用户证书移到系统证书目录下，或者配置系统强制信任用户证书。
对于移动用户证书到系统证书目录下的情况，推荐使用这个插件：<https://github.com/ys1231/MoveCertificate>
对于强制信任用户证书的这种情况，推荐使用这个插件：<https://github.com/NVISOsecurity/MagiskTrustUserCerts>
2.对于这种情况，我们安装完证书后，直接使用代理/vpn的方式进行抓包就可以了，这里我们以某浏览器为例，进行抓包演示，因为我用的设备是Android 7.0以上的，所以我们首先是配置系统强制信任用户证书的插件。

![image](https://bbs.kanxue.com/upload/attach/202409/936543_R2YVV6CNWP9WQMW.png)

3.配置完成后，我们在抓包软件上导出证书，然后在设备上进行安装。

![image](https://bbs.kanxue.com/upload/attach/202409/936543_2HAEG4CWP3G75WD.png)

4.接下来，我们就可以进行抓包了，抓包成功。

![image](https://bbs.kanxue.com/upload/attach/202409/936543_QA4A7Z93K7TWJPU.png)

## 二、单向证书认证：客户端校验服务器证书--SSL Pinning

1.这是第二种情况，也就是我们常说的sslpinning，想具体了解sslpining技术，可以去看这2篇文章：
<https://shunix.com/ssl-pinning/>
<https://yu-jack.github.io/2020/03/02/ssl-pinning/>

2.针对这种情况，我们以x答x单app为例，进行抓包，上面我们已经试过了，用我们的测试设备是可以正常抓到https的数据包的，然后我们再去抓一下x答x单这个app的包，点击发送验证码按钮后会提示发送失败，请重试 ，说明我们抓包失败了。

![image](https://bbs.kanxue.com/upload/attach/202409/936543_SRYAE49F8H3ASZN.png)

![image](https://bbs.kanxue.com/upload/attach/202409/936543_CGMUBK22SFY6JVJ.png)

3.这里报错：Client closed the connection before a request was made. Possibly the SSL certificate was rejected，表明在 SSL/TLS 握手阶段，客户端在没有发送 HTTP 请求之前就关闭了连接，客户端拒绝了服务器的证书，也就是上面我们所说的sslpinning技术，还有另外一种报错得情况：SSL handshake with client failed: An unknown issue occurred processing the certificate (certificate_unknown)，也是用到了sslpinning技术。那遇到上述这2种情况，我们应该怎么处理呢？使用frida进行hook，我们这里直接用大佬们写好的脚本进行hook，地址：<https://github.com/WooyunDota/DroidSSLUnpinning/blob/master/ObjectionUnpinningPlus/hooks.js>

4.用了大佬的脚本后，发现还是不行，还是失败了，只能换一个再试试了，又尝试了justtrustme，地址：[https://github.com/Fuzion24/JustTrustMe，结果还是不行。](https://github.com/Fuzion24/JustTrustMe%EF%BC%8C%E7%BB%93%E6%9E%9C%E8%BF%98%E6%98%AF%E4%B8%8D%E8%A1%8C%E3%80%82)

![image](https://bbs.kanxue.com/upload/attach/202409/936543_7ABGZVVH6Z5QFS4.png)

5.在辗转反侧之时，我想起之前用算法助手时，里面带着一个justtruatme的升级版，于是就拿来试了试，结果成功拿下。可以正常进行抓包了。

![image](https://bbs.kanxue.com/upload/attach/202409/936543_T5CFX3GKT9UQ7GV.png)

6.经过上述尝试，我们针对sslpinning这种，可以先用市面上已有的sslunpinning工具进行尝试，如果遇到都无法进行成功的情况，那就需要我们去手工进行hook了，大致有两种思路，一是对所有HTTP字符串相关类进行Hook，二是考虑到App在验证证书时会打开证书文件判断是否是App自身所信任的，因此一定会使用File类的构造函数打开证书文件获得文件的句柄，所以我们在测试时可以Hook上所有File类的构造函数，即对File.init函数进行hook。这里我用了objection进行hook的：`objection -N -h 127.0.0.1 -p 26666 -g cn.ticktick.task explore -P ~/.objection/plugins -s "android hooking watch class_method java.io.File.\init --dump-args --dump-backtrace --dump-return"`，这里因为$在命令行中有特殊含义，所以用\对它进行转义，避免被当成命令行变量。hook之后，我们在得到的数据里面搜索/system/etc/security/cacerts

![image](https://bbs.kanxue.com/upload/attach/202409/936543_4SBM723ZMYESYH6.png)

7.我们在搜到的数据里面，找到了一个关于证书的堆栈信息，我们用jadx反编译后，找到这个方法

![image](https://bbs.kanxue.com/upload/attach/202409/936543_RYZ27CKXXXTGRE7.png)

8.复制一下，丢给chatgpt分析一下，得出结论，这段代码是关于处理 SSL 证书验证的逻辑，是基于域名和证书的哈希值进行匹配，检查传入的证书是否符合某些预期的标准，那我们尝试hook它，并让它返回空，这样不就能绕过证书校验了嘛。

| 1234567891011 | `function` `main(){``Java.perform(``function``(){``console.log(``"启动"``);``let f = Java.use(``"ll.f"``);``f[``"a"``].implementation=``function``(str, list){``console.log(`f.a is called: str=${str}, list=${list}`);``return``;``};``});``}``setTimeout(main,500)` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202409/936543_U64DJVPZYDATBJX.png)

9.非常幸运，经过hook后，我们成功抓到了这个数据包，至此完成。

## 三、双向证书认证：服务器校验客户端证书。

1.这是第三种情况，我们以x利蜂app为例，进行抓包尝试，经过尝试，还是和之前一样报错：SSL handshake with client failed: An unknown issue occurred processing the certificate (certificate_unknown)

![image](https://bbs.kanxue.com/upload/attach/202409/936543_JVUV39FN6P8R5MR.png)

2.我们先使用objection的android sslpinning disable把这个sslpinning过掉，过掉之后，我们再抓包，发现请求正常发出，响应返回报错：400 No required SSL certificate was sent。判断为服务器校验客户端证书。

![image](https://bbs.kanxue.com/upload/attach/202409/936543_756VV9GNKGNJEMK.png)

3.当我们遇到这种情况，需要我们从app中找到内置的客户端证书，导入到抓包工具中，才能正常进行抓包，那怎么才能找到客户端的证书呢？通常是有二种方法，第一种是用r0ysue大佬写的r0capture进行hook导出，第二种是去hook Keystore，找到加载证书的地方，手动分析源码去找到证书和密码。我们先用一下第一种方案：直接上r0capture，有枣没枣打一杆子试试。

![image](https://bbs.kanxue.com/upload/attach/202409/936543_Z7ZSZD3CQ6FJXPC.png)

4.运气不错，证书找到了，我们直接在dowload目录下把证书拿出来，安装到Charles里

![image](https://bbs.kanxue.com/upload/attach/202409/936543_42YRXMGQMWYWBB9.png)

5.然后，再次进行抓包，可以看到，我们成功绕过了双向证书认证。

![image](https://bbs.kanxue.com/upload/attach/202409/936543_7KWFKQEBBA4VWVH.png)

6.我们去看一下r0ysue大佬的脚本，简单来解释一下原理，在安卓开发中，系统包是无法混淆的，例如java.security.KeyStore不会被混淆，所以可以去hook这个类，并且在 Java 中，KeyStore$PrivateKeyEntry 是存储在 KeyStore 中，包含私鑰和相關的證書，即getPrivateKey() 和 getCertificateChain() 這兩個方法，也就是说当應用程序調用 getPrivateKey() 或 getCertificateChain() 方法來獲取私鑰和證書時，会被脚本拦截并提取返回的私钥和证书数据，然后storeP12() 函數，將提取的私鑰和證書組合起來，存儲為一個 .p12 文件，并使用密码r0ysue進行加密並寫入到指定的文件路徑。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253 | `Java.perform(``function``(){``functionuuid(len, radix){``var` `chars =``'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'``.split(``''``);``var` `uuid =[], i;``radix = radix \|\| chars.length;``if``(len){``// Compact form``for``(i =0; i < len; i++) uuid[i]= chars[0\| Math.random()* radix];``}``else``{``// rfc4122, version 4 form``var` `r;``// rfc4122 requires these characters``uuid[8]= uuid[13]= uuid[18]= uuid[23]=``'-'``;``uuid[14]=``'4'``;``// Fill in random data. At i==19 set the high bits of clock sequence as``// per rfc4122, sec. 4.1.5``for``(i =0; i <36; i++){``if``(!uuid[i]){``r =0\| Math.random()*16;``uuid[i]= chars[(i ==19)?(r &0x3)\|0x8: r];``}``}``}``return` `uuid.join(``''``);``}``functionstoreP12(pri, p7, p12Path, p12Password){``var` `X509Certificate = Java.use(``"java.security.cert.X509Certificate"``)``var` `p7X509 = Java.cast(p7, X509Certificate);``var` `chain = Java.array(``"java.security.cert.X509Certificate"``,[p7X509])``var` `ks = Java.use(``"java.security.KeyStore"``).getInstance(``"PKCS12"``,``"BC"``);``ks.load(``null``,``null``);``ks.setKeyEntry(``"client"``, pri, Java.use(``'java.lang.String'``).$``new``(p12Password).toCharArray(), chain);``try``{``var` `out = Java.use(``"java.io.FileOutputStream"``).$``new``(p12Path);``ks.store(out, Java.use(``'java.lang.String'``).$``new``(p12Password).toCharArray())``}``catch``(exp){``console.log(exp)``}``}``// 在服务器校验客户端的情形下，帮助dump客户端证书，并保存为p12的格式，证书密码为r0ysue``Java.use(``"java.security.KeyStore$PrivateKeyEntry"``).getPrivateKey.implementation=``function``(){``var` `result =``this``.getPrivateKey()``var` `packageName = Java.use(``"android.app.ActivityThread"``).currentApplication().getApplicationContext().getPackageName();``storeP12(``this``.getPrivateKey(),``this``.getCertificate(),``'/sdcard/Download/'``+ packageName +uuid(10,16)+``'.p12'``,``'r0ysue'``);``return` `result;``}``Java.use(``"java.security.KeyStore$PrivateKeyEntry"``).getCertificateChain.implementation=``function``(){``var` `result =``this``.getCertificateChain()``var` `packageName = Java.use(``"android.app.ActivityThread"``).currentApplication().getApplicationContext().getPackageName();``storeP12(``this``.getPrivateKey(),``this``.getCertificate(),``'/sdcard/Download/'``+ packageName +uuid(10,16)+``'.p12'``,``'r0ysue'``);``return` `result;``}``});` |
|-|-|

7.这个x利蜂的例子到此为止，我们再拿出某Location，它也是双向证书认证，这次我们自己去找一下证书，还是一样启动charles进行抓包。

![image](https://bbs.kanxue.com/upload/attach/202409/936543_Q9WV5M76N5RDNGC.png)

8.可以看到，报错和之前是一样的，我们之前说过了，这种是sslpinning的情况，我们用objection的android sslpinning disable把它过掉，过掉之后，再重新抓包，发现报错变了，请求包正常，响应包400的情况。

![image](https://bbs.kanxue.com/upload/attach/202409/936543_W9W63UURWPJ383G.png)

9.这种情况就是双向证书校验了，我们需要去解包找证书搜索.p12，.bks，.pem，还是一样没找到，我们只能去脱壳反编译代码，这次脱壳我用的是大佬给分享的一个脱壳网站：<https://nop.gs/>

![image](https://bbs.kanxue.com/upload/attach/202409/936543_X9P3NA3HMB3M7WV.png)

10.然后我们去代码里找找看，这里我们直接搜索keystore，发现就这几个，而且就这俩货带着BKS的关键字样。

![image](https://bbs.kanxue.com/upload/attach/202409/936543_Z8WYFMTWHY38TQD.png)

11.点进去看看，终于知道为啥我解包后，搜索常见证书后缀搜不着的原因了，原来是用了图片做证书。md

![image](https://bbs.kanxue.com/upload/attach/202409/936543_DTUPUY7QJ4BANJU.png)

12.证书找到了，接下来就是找密码了，怎么找呢？当然是hook了，上脚本。之前也说过了，因为java.security.KeyStore是系统的类是不会被混淆的，所以我们hook它就行了。

| 123456789101112131415161718192021 | `function` `hook_KeyStore_load(){``Java.perform(``function``(){``var` `StringClass = Java.use(``"java.lang.String"``);``var` `KeyStore = Java.use(``"java.security.KeyStore"``);``KeyStore.load.overload(``'java.security.KeyStore$LoadStoreParameter'``).implementation=``function``(arg0){``// printStack("KeyStore.load1");``// 输出调用栈``console.log(Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Throwable"``).$``new``()));``console.log(``"KeyStore.load1:"``, arg0);``this``.load(arg0);``};``KeyStore.load.overload(``'java.io.InputStream'``,``'[C'``).implementation=``function``(arg0, arg1){``// printStack("KeyStore.load2");``console.log(Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Throwable"``).$``new``()));``console.log(``"KeyStore.load2:"``, arg0, arg1 ? StringClass.$``new``(arg1):``null``);``this``.load(arg0, arg1);``};``console.log(``"hook_KeyStore_load..."``);``});``}``hook_KeyStore_load()` |
|-|-|

13.来，让我们来看看hook的效果如何？hook出来了，密码是lerist.key.2021

![image](https://bbs.kanxue.com/upload/attach/202409/936543_UYYJW9MU2VNKERV.png)

14.然后我们把证书拿出来

![image](https://bbs.kanxue.com/upload/attach/202409/936543_SET5K3S86UQ5JQN.png)

15.这里我用了keystore explorer对证书进行格式的转换

![image](https://bbs.kanxue.com/upload/attach/202409/936543_G7M2994QCCJY5MA.png)

16.我们得把证书转成p12格式，才能在charles里安装，安装完成后，虽然是加密得，但是可以正常抓包了。

![image](https://bbs.kanxue.com/upload/attach/202409/936543_B2RXX25H6DZ743S.png)

## 四、总结

在Android应用的抓包过程中，处理不同类型的证书验证机制的方法有所不同：

无证书校验：如果应用没有进行证书验证，我们只需配置抓包工具的证书即可进行抓包。

单向证书认证（SSL Pinning）：对于SSL Pinning的应用，我们通常需要使用Frida等工具进行hook，以绕过SSL Pinning机制。在某些情况下，可能需要尝试多种方法，如使用JustTrustMe脚本，才能成功进行抓包。

双向证书认证：对于双向证书认证，我们可以使用r0capture直接dump证书。此外，也可以通过代码中找到证书和密码，然后将其转换为.p12证书，并导入到抓包工具中进行抓包。

---

# 回复

## 回复 by 逆天而行 (#2)

*2024-9-17 08:56*

很不错的的文章

## 回复 by scllqk (#3)

*2024-9-17 13:31*

>
> [逆天而行](https://bbs.kanxue.com/user-957038.htm)
>
>  很不错的的文章
>
>
>

感谢，互相学习，互相进步![image](https://bbs.kanxue.com/view/img/face/71.gif)

## 回复 by mb_ygxdlbdi (#4)

*2024-9-23 09:08*

师傅有联系方式嘛，最近也遇到了一个双向证书校验的app，各种方式都尝试了，但还是无果，想请教下师傅

## 回复 by coneco (#5)

*2024-9-23 10:11*

感谢分享！

## 回复 by ChrQwQ (#6)

*2024-9-23 10:58*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ygxdlbdi](https://bbs.kanxue.com/user-972883.htm)
>
>  师傅有联系方式嘛，最近也遇到了一个双向证书校验的app，各种方式都尝试了，但还是无果，想请教下师傅
>
>

装个xposed模块，justtrustme就行了

## 回复 by mb_ygxdlbdi (#7)

*2024-9-23 11:58*

>
> [ChrQwQ](https://bbs.kanxue.com/user-730747.htm)
>
>  装个xposed模块，justtrustme就行了
>
>

我的机子都是环境配好了的，哪些方式都不能开箱使用，分析就是双向证书校验，目前分析代码是找到了证书，但是密码hook不出来

## 回复 by ChrQwQ (#8)

*2024-9-24 09:32*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ygxdlbdi](https://bbs.kanxue.com/user-972883.htm)
>
>  我的机子都是环境配好了的，哪些方式都不能开箱使用，分析就是双向证书校验，目前分析代码是找到了证书，但是密码hook不出来
>
>

app是什么，看看

## 回复 by koflfy (#9)

*2024-9-24 10:52*

mark

## 回复 by mb_ygxdlbdi (#10)

*2024-9-25 13:40*

>
> [ChrQwQ](https://bbs.kanxue.com/user-730747.htm)
>
>  app是什么，看看
>
>

师傅加个qq吧，2114674524，我发你

## 回复 by ChrQwQ (#11)

*2024-9-25 14:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ygxdlbdi](https://bbs.kanxue.com/user-972883.htm)
>
>  师傅加个qq吧，2114674524，我发你
>
>

加了

## 回复 by @=llfly (#12)

*2024-9-30 10:57*

学习   ![image](https://bbs.kanxue.com/view/img/face/67.gif)

## 回复 by jfztaq (#13)

*2024-10-4 09:53*

我这里测试的时候用哪个脚本app闪退？楼主没有闪退吗

## 回复 by scllqk (#14)

*2024-10-8 09:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  jfztaq](https://bbs.kanxue.com/user-404618.htm)
>
>  我这里测试的时候用哪个脚本app闪退？楼主没有闪退吗
>
>

没有呀

## 回复 by 菜鸟也想飞 (#15)

*2024-10-8 11:18*

感谢分享

## 回复 by mb_ifmdtwve (#16)

*2024-11-11 11:48*

trustme 升级版是什么?

## 回复 by Savoor (#17)

*2024-11-11 12:36*

感谢分享,学习了

## 回复 by mb_fhpfcoqp (#18)

*2025-12-1 16:18*

真厉害啊

## 回复 by 外交 (#19)

*2026-4-12 17:26*

666
