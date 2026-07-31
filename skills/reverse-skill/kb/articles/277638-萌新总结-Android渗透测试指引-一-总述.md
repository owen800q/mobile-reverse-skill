---
title: '[原创]（萌新总结）Android渗透测试指引（一）：总述'
url: https://bbs.kanxue.com/thread-277638.htm
tid: 277638
author: mb_rdzyrhpc
date: '2023-06-15'
tags: [Android安全, 原创, 基础理论]
crawled_at: '2026-07-31T14:44:34+08:00'
replies: 4
---

萌新自己写的笔记，单纯作为记录，也希望能够帮到他人，如有错误请轻喷^ ^

# 0 adb常见命令

一般模拟器（非真机模拟器）的安装目录下会有一个adb.exe。如果安装了Android Studio的话也会附带一个adb。如果两种情况都没有则需要去自己下载一个。调试远端的设备（本机上的模拟器一般不用，如雷电模拟器）需要先使用adb connect进行连接再shell。

·         adb shell 进入shell，也就是获取一个手机命令行

·         adb push 电脑地址 手机地址 将电脑文件导入到手机指定位置

·         adb install 电脑地址 安装电脑地址上的apk

·         adb connect ip port 链接指定位置的手机（适用于远程调试）

·         adb devices 查看当前设备列表

·         adb forward agree:port agree:port 转发端口

·         adb shell pm uninstall -k --user 0 包名 卸载apk

# 1 代理

## 1.1 挂代理步骤

**（这个方法真机模拟器无法使用，真机挂代理方式请看下文第二节）**

使用burpsuite、mitmproxy、lamda。

lamda github页面：[https://github.com/rev1si0n/lamda/](https://github.com/rev1si0n/lamda/releases)

首先需要准备一个root权限的手机。下载lamda的安装脚本adb中使用sh运行安装（详细步骤请自行查看lamda的ReadMe）。主机中使用pip安装lamda的客户端。

手机如果是模拟器，配置到与主机同一个网段则需要使用桥接模式。使用桥接模式后互相能ping通就可以了。

启动lamda的命令：

sh /data/local/tmp/x86/bin/launch.sh

先启动手机上的lamda。使用lamda是为了挂代理+安装证书。

mitmproxy使用pip命令即可安装（它是一个python module）：

pip install mitmproxy

安装mitmproxy的证书（运行mitmdump挂起服务器，浏览器走mitm的代理访问mitm.it即可安装证书）并挂上mitmproxy的代理如下：

#启动代理
# sh /data/local/tmp/x86/bin/launch.sh

from lamda.client import *

d=Device("192.168.3.31")

profile = GproxyProfile()
profile.type = GproxyType.HTTP_CONNECT

# 此选项请根据实际情况选择你是否需要
profile.drop_udp = True
profile.host = "192.168.3.82"
profile.port = 8899
#d.install_ca_certificate("mitmproxy-ca-cert.cer")
d.start_gproxy(profile)
#d.stop_gproxy()
#d.uninstall_ca_certificate("cacert.der")

d.beep()

这个脚本在手机端lamda启动后运行一次，听到beep声表示运行成功。

install_ca_certificate就是安装证书的命令，只需要运行一次。

手机端的配置结束，接下来pip安装mitmproxy，使用upstram模式转发流量到上流代理服务器（即BP）即可。

命令为：

mitmdump --mode upstream:127.0.0.1:8080 --listen-port 8899 --ssl-insecure

上面的mitmweb也可以改成mitmproxy 或mitmdump 主要是中间流量的表现形式不同。

## 1.2 虚拟机、手机逃避代理检测

有时候直接使用系统的代理会被APK检测到。有些APK的包使用了参数NO_PROXY，会绕过系统代理发送，有些则会在检测到代理的时候停止发包。

目前知道的能够绕过代理的工具有两个，HTTPDroid和lamda。lamda挂代理参考上面的脚本，这个我测试过是可以绕过代理检测的。HTTPDroid及其他基于iptables的工具据称在原理上是可以绕过的。

但是HTTPDroid不能在夜神模拟器上安装。我的建议是普通模拟器上使用lamda，真机模拟器上使用HTTPDroid（因为lamda不能在真机模拟器上使用）或者真机宿主机安装小黄鸟（HTTPCanary）。

## 1.3 真机虚拟机逃避代理检测（真机虚拟机）

有时候APK会校验用户所处的环境是否是真机，这个时候建议直接使用真机或在真机上安装虚拟机。这个原理跟反反爬虫是一样的：再多的掩饰都是虚的，程序员总能从你想不到的角度进行检测，所以最好直接在真机里做操作。比如安装真机虚拟机如VMOS。

但是真机虚拟机是无法使用lamda的（实际的真机可以），用VMOS抓包的一个方式是代理到宿主机的小黄鸟（HTTPCanary），导出.0证书，小黄鸟设置目标应用，虚拟机安装证书。

也可以通过转换过的.0证书+模拟器挂代理代理到mitmproxy然后中转到burpsuite。一样的。

# 3 证书与双向认证

## 3.1 安装证书的小TIPS

由于虚拟机可能不能直接装证书，即使有ROOT（具体为什么我不知道），只能将证书导出为.0格式然后复制到/system/etc/security/cacerts/下。

cer、pem等格式的证书可以通过openssl转换为.0格式之后手动安装。

命令为（pem与cer都是这个）：

openssl x509 -inform PEM -subject_hash_old -in mitmproxy-ca-cert.pem -out out.0

## 3.2 证书校验绕过

有时候，APK会这样：

校验通信中证书的签发HOST。这种情况需要用户反编译找到hostname然后自行制作一个此hostname的证书。证书可以通过openssl生成。

## 3.3 双向认证（双签）绕过

双向认证，指的是APK与服务器各自有一个私钥，每次通信时，通信包会经过两次加密。或者换句话说，就是APK发送到服务器的包要被客户端证书签名，服务器发送到APK的包要被服务器证书签名（如果APK本身还设置了）。这就导致BP等使用的自签名证书不会被服务器端接受。

SSL双向认证体系中，客户端与服务端各拥有一对证书和密钥，在通信过程中：

(1)客户端建立通信，发送SSL版本等信息给服务端

(2)服务端发送服务端证书给客户端，客户端会校验服务端的证书是否在许可范围内

(3)客户端校验通过后，发送客户端证书给服务端，服务端也会校验客户端证书是否在许可范围内

综上所述，要成功抓到经过双向签名的包，需要同时绕过客户端和服务端双端的认证。客户端的认证可以通过Xposed模块SSLUnpinning或者JustTrustMe绕过，而服务端认证则需要获得APK文件中的证书。

反编译APK，找到APK中保存的客户端证书，还有它的密码。公私钥一般作为单独文件存储（也有APK直接写死在代码里，不过证书是有过期时间的，所以应该没什么APK会这么做），密钥则会写在代码里，需要反编译查找。

如果代码未经混淆，直接搜索ClientKeyStore.load即可找到打开bks证书的语句，第二个参数即为密码，第一个参数为证书文件名。

由于Android证书端的证书格式为bks，而BP需要的证书格式为p12，所以我们还需要转换证书的格式。下载portecle后转换证书的格式，然后在BP中导入即可抓到包：

# 4 使用Drozer扫描Android本地漏洞

drozer主要 用来查找androidAPK本身的漏洞，而非对应后端的漏洞。

## 4.1 安装与启动

下载地址：

<https://github.com/WithSecureLabs/drozer/releases>

需要先额外安装一个python2.7，再运行安装程序。如果环境中已经有其他版本的python了，请先看下节。

在运行drozer.bat文件无报错后，我们开始配置手机端的agent和依赖。搜索python2文件夹下的apk文件，找到standard-agent.apk，将其装在手机上，然后打开APK，点击右下角的开启打开agent。adb方面转发端口，使用命令：

.\adb.exe forward tcp:31415 tcp:31415

然后电脑处使用命令：

 .\drozer.bat console connect

运行成功应该如下：

## 4.2 额外安装py2下的各种问题

现在基本没人会使用py2编程了，所以很多人会先装py3。

在4.1安装python2时，如果想将py2不冲突的放进环境变量里，可以将py2文件夹里的python.exe更名为python2.exe然后将路径放在PATH下（不像放在PATH也可以，后面的python2替换为绝对路径）。

点击安装，选择之前安装的python2文件夹，进入\Scripts文件夹下，将drozer.bat文件中的python替换为python2再运行即可启动dozer。

然后我们开始配置依赖。移动到pip2.exe所在的文件夹使用与平时使用pip相同的命令安装service_identity、twisted、pyopenssl、pyyaml、protobuf即可。

有时候下载的py2里没有pip文件，需要在这里获取get-pip.py：

<https://bootstrap.pypa.io/pip/2.7/get-pip.py>

全文复制后保存为python文件，然后使用py2运行就行了。但是这样获取的pip有个问题就是没有能访问的镜像源，所以每次安装时带上选项，使用国内的镜像源即可：

 -i <http://pypi.douban.com/simple/> --trusted-host pypi.douban.com

## 4.3 常见命令（dz控制台下）

查看APK列表：

run app.package.list

-f 选项可以按照关键词查找APK。

查看APK暴露的activity列表：

run app.activity.info -a 包名

拉起Activity：

run app.activity.start --component 包名 活动名（activity）

枚举Provider：

run app.provider.info -a 包名

SQL注入扫描：

run scanner.provider.injection -a 包名

# 5 插件框架

这两个框架的模块安装方式都是一样的：模块本身就是一个APK，直接安装APK即会被识别。

## 5.1 安装使用Magisk

电脑端模拟器安装Magisk可以参照此文章：<https://www.52pojie.cn/thread-1583586-1-1.html>

使用Magisk而不使用XPOSED的原因是Magisk对文件系统的破坏性小，且不需要事先ROOT，适用范围广一些。并且Magisk上可以集成Xposed。

对于真机模拟器而言，已知光速模拟器可以安装Magisk，但是一般情况下需要付费VIP。VMOS据说安装之后并不好用，可能还是要用其自带的XPOSED。

可以使用Magisk Manager 安装Magisk。安装后，如果Manager提示更新但一直下载失败，请打开设置换源为<https://qianyegroup.gitee.io/magiskbuilds/updates/custom_md2.json>。

## 5.2 安装使用Xposed

这是真机模拟器的不得已之选。使用VMOS PRO的虚拟机会自带一个XPOSED。由于个人比较推荐Magisk，Xposed目前还没装过。

---

# 回复

## 回复 by mb_uulqeyon (#2)

*2023-6-15 22:25*

太好了，我也是萌新，顶顶

## 回复 by mb_itwfugbn (#3)

*2023-10-4 18:59*

大佬，请问bks转成p12文件是可以直接转么，还是说要先转成pxf再转p12文件呢

## 回复 by 秋狝 (#4)

*2023-10-4 23:05*

感谢分享

## 回复 by hyy19sec (#5)

*2023-11-27 17:50*

感谢分享
