---
title: Flutter 逆向初探
url: https://bbs.kanxue.com/thread-275953.htm
tid: 275953
author: Mr_Holiday
date: '2023-02-03'
tags: [Android安全, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:53:41+08:00'
replies: 5
---

# 前言

最近看了很多flutter逆向绕过SSL验证的文章，发现有些细节比较模糊，新接触flutter的师傅们可能不太理解，所以搜到原文进行翻译加上自己的理解，简单梳理了下整个方法和逻辑。

# 一、Flutter简介

Flutter是Google构建在开源的Dart VM之上，使用Dart语言开发的移动应用开发框架，可以帮助开发者使用一套Dart代码就能快速在移动iOS 、Android上构建高质量的原生用户界面，同时还支持开发Web和桌面应用。

# 二、Flutter特征

在逆向分析前，我们首先要确定测试目标是否用Flutter开发的。当使用Flutter构建Android APP时，lib文件夹下的每个受支持的架构下会出现两个库：libapp.so和libflutter.so，如下图所示。如果出现这两个特殊的库，那可以判定这个APP是有部分或全部使用Flutter开发的。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_SAEM9VBSSWJNK4F.jpg)
其中，libapp.so库包含了开发过程中编写的所有编译过的Dart业务代码。libflutter.so库则存放了flutter的一些基础类库。

# 三、逆向Flutter解决HTTPS抓包问题

应用市场上有些APP核心的业务逻辑代码使用了Flutter开发，实际测试过程中发现无法使用Burpsuite、Charles等工具拦截相关的请求数据包。这是因为Dart使用Mozilla的NSS库生成并编译自己的Keystore，导致我们不能通过将代理CA添加到系统CA存储的方式来绕过SSL验证。
我们可以通过一个小实验复现上面提到的场景，目标APP主页面包括了三个按钮：HTTP Request, HTTPS Request and Pinned Request，分别用来测试拦截三种类型的请求。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_PCRHH3NR3PCTV6D.jpg)
其中的HTTP和HTTPS是通过HTTPClient类的getUrl方式发送指定请求，Pinned Request是通过使用Dio包执行SSLPinning，发送HTTPS请求并验证证书。主要的实现逻辑如下所示:
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_3WBHG3JRR2Z5BHU.jpg)
首先像抓包Android APP一样拦截Flutter的请求包，但会发现三种请求都无法被拦截，因为Flutter APP默认情况下不使用系统的代理设置，所以可以使用Drony + BurpSuite，将手机上的目标APP的流量都重定向到Drony自身，再转发到BurpSuite上。发现只能拦截到HTTP请求，如下图所示。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_SEZYTJSUFCBZGGX.jpg)
发送HTTPS和HTTPS (Pinned) 请求失败，可以用logcat看到相关报错信息，这部分我们之后分析：
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_9TWAQ2ZDPP84NZ7.jpg)
接下来就是通过逆向来绕过证书链校验，目前有两种方法可以解决这类场景：

1. 使用reFlutter开源逆向分析工具；
2. 使用Frida脚本hook libflutter.so中的函数。
**1. 使用reFlutter开源逆向分析工具**
reFlutter框架使用了已编译且重新封装的Flutter库来帮助广大研究人员对Flutter APP进行逆向工程分析，通过socket.cc可以执行流量拦截和监控。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_TAXW9HAX9AAQ2ST.jpg)
首先PC端命令行安装reFlutter：*pip3 install reflutter*。装完输入命令：*reflutter flutter_ssl_pinning_bypass_lab_android.apk*。选择[1]流量监控和拦截，输入PC端的IP地址后，将获取到release.RE.apk，但此apk尚未签名，需要我们手动签名。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_A4MT6VS2TKD93AV.jpg)
通过MT管理器或者uber-apk-signer jar签名，这里使用后者。输入命令：*java -jar uber-apk-signer-1.2.1.jar --apk release.RE.apk*。然后将重签名的apk安装到真机或者模拟器上。
下一步我们需要按照之前reFlutter的提示，设置BurpSuite的代理，端口为8083，绑定所有地址，并且勾选支持不可见代理，使非代理意识的客户端直接连接到侦听器。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_XHQB5WCREA6QS4C.jpg)
设置Drony的wifi代理主机名端口和BurpSuite一致。
完成以上步骤，点击Flutter APP的三种请求按钮，发现Burpsuite已经拦截到HTTPS请求和Pinned HTTPS请求。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_XK7UJJDK9CB4RRU.jpg)
使用reFlutter框架拦截HTTPS流量比较简单易上手，但是存在一个很大的弊端，就是需要重打包app，导致它的局限性较大，因为现在的应用市场很多Flutter APP是做了防二次打包的，虽然可以直接替换私有目录的libflutter.so，但需要root，很多APP也会检测root。对于这些防护倒是可以使用frida框架绕过签名校验和root代码，但这样也增加了攻击成本。
**2. 使用Frida脚本hook libflutter.so中的函数。**
当无法拦截HTTPS请求时，我们通过logcat查看日志发现错误被触发的位置是[handshake.cc:393]，而Handshake.cc是BoringSSL库的一部分，包含执行证书验证的逻辑。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_H5EWAEXKJTG9KKR.jpg)
因为BoringSSL是开源的，很容易就可以查到如下所示的393行代码段，其中的ret指的是SSL校验结果（验证通过是ssl_verify_ok），这段代码表示如果结果是ssl_verify_invalid，则报错提醒。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_8ZGDZSN7K2MKSXF.jpg)
这个判断逻辑是处于ssl_verify_peer_cert函数中的，这个函数最后会return ret。那么如果直接hook这个函数修改ret的值为ssl_verify_ok可以绕过SSL验证吗？答案是否定的。因为最有可能采用的代码路径是，注册了一个自定义验证回调，使得368行返回true，而在第369行执行的回调返回ssl_verify_invalid。然后代码跳转到392行，ret变量赋值为ssl_verify_invalid，因此在ssl_verify_peer_cert函数return ret之前就会显示警报（393-394行）。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_PXVJUHDNZ3MNXHZ.jpg)
继续观察上下文环境寻找更好hook的函数，发现Handshake.cc的386行代码段是验证链的方法的实际部分。这行的session_verify_cert_chain函数实际是在ssl_x509.cc的第361行定义，此函数返回布尔值类型，如果hook这个函数，修改返回值为true，则386行的ret为ssl_verify_ok。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_FERFUPKNGYW2AYW.jpg)
锁定hook的目标函数后，我们现在需要在libflutter.so中找到它。找到session_verify_cert_chain函数唯一性的特征方便后续IDA中定位该函数，如[ssl_client]或[ssl_server]。将libflutter.so导入IDA，使用Search -> Find Strings搜索关键词[ssl_client]，发现有4处交叉引用。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_3FFSMHGYFMUJPMQ.jpg)
第二处和第三处都是Function sub_3B1834中的，跳转到函数调用位置。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_8RZR6GK59WNB6Q6.jpg)
F5检查是不是目标函数，点击sub_7F4B14，查看代码逻辑与ssl_x509.cc中389行一致，确定是目标。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_2CDM3Y9UV2AC9R3.jpg)
这时我们计算这个函数与其中一个导出函数的偏移量，并将它hook。可以复制函数的前10个以上的字节，之后利用frida编写的脚本检查该模式出现的频率。如果它只发生一次，说明找到了函数，可以hook它。首先在IDA中的Options->General->Number of opcode bytes 设置为4，定位到sub_3B1834起始位置，复制前10个以上的字节。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_4PTRKBRAFC4J25Y.jpg)
接下来就是编写frida的脚本，使用之前复制的字节定位，在运行时使用Interceptor将返回值更改为1 (true)，这样就实现了绕过证书链检查拦截HTTPS和HTTPS(Pinned)的请求，代码如下所示。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_QWTWWQRYAJT5CBC.jpg)
其中注释说明的地址要add 0x01是因为在32位ARM上, 对于ARM函数, 此地址的最低有效位必须设置为0, 对于Thumb函数, 此地址必须设置为1。因为我们这里hook的libflutter.so是64位的，地址不需要再加1。
使用frida命令*frida -U -l XXX.js -f com.xxx.xxx --no-pause*执行脚本，发送HTTP/HTTPS/HTTPS (Pinned)三种请求，终端打印绕过证书链检查的日志。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_PVWV3Y4H2NS9SKN.jpg)
Flutter客户端界面显示请求成功。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_6FVGXPASP5DT3AG.jpg)
并且Burpsuite也可以拦截所有请求。
 ![image](https://bbs.kanxue.com/upload/attach/202302/971971_F577UJUJU284YXY.jpg)
如果将hook目标函数的前10多个字节找到规律部分使用通配符代替，上面的脚本会适用于大多数的Flutter APP，有兴趣的师傅们可以自己试试。

# 参考

1. <https://l33t-en0ugh.gitbook.io/infosec/android-pentesting/bypass-ssl-pinning-for-flutter-apps-using-reflutter-framework>
2. <https://blog.nviso.eu/2020/05/20/intercepting-flutter-traffic-on-android-x64/>
3. <https://blog.nviso.eu/2022/08/18/intercept-flutter-traffic-on-ios-and-android-http-https-dio-pinning/>
4. <https://github.com/google/boringssl/blob/master/ssl/ssl_x509.cc>
5. <https://github.com/google/boringssl/blob/master/ssl/handshake.cc>
6. <https://github.com/google/boringssl/blob/master/include/openssl/err.h>

---

# 回复

## 回复 by fjqisba (#2)

*2023-2-3 15:52*

抓包只是最简单的一步，事实上有不少算法是放在dart层的，关键是怎么去阅读dart汇编，还原算法呢。

## 回复 by Mr_Holiday (#3)

*2023-2-6 13:56*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  fjqisba](https://bbs.kanxue.com/user-729528.htm)
>
>  抓包只是最简单的一步，事实上有不少算法是放在dart层的，关键是怎么去阅读dart汇编，还原算法呢。
>
>

是的，你说的这点很关键，目前正在看libapp.so，里面很多这类dart业务代码。现在这篇文章只是以抓包为例初步了解。

## 回复 by 教教我吧~ (#4)

*2023-6-26 11:17*

你好，有一个疑惑：”请问本文通过hook修改 session_verify_cert_chain函数的返回值为true来过证书检测，但是session_verify_cert_chain处于if-else语句中的else分支，如果else分支不走，仅走if分支呢？这样hook无效了，那么对之前报错结果没有改变呀？“  （这一部分我没有理解清楚）

![image](https://bbs.kanxue.com/upload/attach/202306/940077_SE4ZZQVTVCKCKN8.jpg)

## 回复 by mb_ocigfxyo (#5)

*2025-3-11 15:51*

>
> [Mr_Holiday](https://bbs.kanxue.com/user-971971.htm)
>
>  是的，你说的这点很关键，目前正在看libapp.so，里面很多这类dart业务代码。现在这篇文章只是以抓包为例初步了解。
>
>

分享一下libapp.so逆向心得体会

## 回复 by @=llfly (#6)

*2025-5-21 17:20*

抓取flutter报文  ![image](https://bbs.kanxue.com/view/img/face/079.gif)
