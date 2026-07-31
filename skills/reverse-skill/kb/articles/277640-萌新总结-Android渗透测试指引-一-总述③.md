---
title: '[原创]（萌新总结）Android渗透测试指引（一）：总述③'
url: https://bbs.kanxue.com/thread-277640.htm
tid: 277640
author: mb_rdzyrhpc
date: '2023-06-15'
tags: [Android安全, 原创, 基础理论]
crawled_at: '2026-07-31T14:44:21+08:00'
replies: 4
---

真心没想到这么长。。。。这是第三段

萌新自己写的笔记，单纯作为记录，也希望能够帮到他人，如有错误请轻喷^ ^

# 8 使用apktool解包、修改、重新打包、签名APK

在进行动态调试之前，我们要先判断APK是否允许调试。如果APK不允许调试，我们就需要反编译解包APK，修改其中的AndroidManifest.xml文件并重新打包签名。

另外一些情况中，我们也需要通过修改APK的代码达到绕过校验等目的。

我们以第一种情况为例，下载apktool，这是Android官方的工具，下载方式应该很简单。

## 8.1 解包修改文件并重新打包

使用命令

java -jar .\apktool_2.7.0.jar d -f C:\Users\HONOR\Desktop\bosuu2501.apk

对APK进行反编译：

![image](https://bbs.kanxue.com/upload/attach/202402/93_W56YEUKDB67BKNP.webp)

编译完成后，切入文件夹，找到AndroidManifest.xml，修改：

在application标签里（理论上只会有一个这种标签）加上android:debuggable=“true”，然后保存：

![image](https://bbs.kanxue.com/upload/attach/202402/93_BCUJ3ZMDF6HAR7S.webp)

然后继续使用apktool

java -jar .\apktool_2.7.0.jar b .\bosuu2501\

将APK文件夹进行打包：

![image](https://bbs.kanxue.com/upload/attach/202402/93_P8HE7E6TWTPYJVU.webp)

## 8.2 签名

之前我们说过，APK包里会有一个META-INF文件夹用于签名。APK在运行时，安卓会先对APK的签名进行校验，所以我们需要将修改过的APK重新签名使其通过校验。

签名的话，方式有很多种，可以使用Android官方的工具jarsigner，也可以使用MT管理器等APK。

考虑到使用jarsigner的传统艺能是打一大段命令行，这里就直接使用MT管理器进行签名。adb push打包后的apk文件到手机中，打开MT管理器，切到目录下，长按文件，选择签名即可：

![image](https://bbs.kanxue.com/upload/attach/202402/93_JDT6N9GYMYJXUU9.webp)

签名后，会出现一个相同名字后缀为_sign的apk文件，直接安装此文件，成功。

# 9 使用JEB进行反编译与远程调试

不推荐单独使用JEB进行反编译，因为它初始给出的代码为Smali。

同时，JEB也挺容易卡的，可以在它的根目录下创建jvmopt.txt文件并输入参数-Xmx8G以提高其运行内存。

## 9.1 使用JEB对照查看Java代码与Smali代码

直接使用JEB打开APK文件，在文件树中选择要查看的JAVA类，右键选择解析：

![image](https://bbs.kanxue.com/upload/attach/202402/93_JS6NFB5TBHSZNKG.webp)

以打开Java代码。然后在选中行中右键再次点击解析，会定位到其Smali代码。

（这段未完 下面还有，提示超长，写不了了）

---

# 回复

## 回复 by 秋狝 (#2)

*2023-6-16 09:12*

感谢分享

## 回复 by mb_rdzyrhpc (#3)

*2023-6-16 09:32*

图全裂了 啊啊啊啊啊啊啊啊啊啊 大家意会一下- -

## 回复 by Editor (#4)

*2023-6-19 18:12*

建议下次将这3篇合成一篇，文章不是太长，分开发，不利于阅读。

## 回复 by mb_rdzyrhpc (#5)

*2023-6-28 11:18*

是的 本来想一起发 但是总提示超长 不知道什么原因只能这样 可能是因为我用语雀文档直接拷过来的![image](https://bbs.kanxue.com/view/img/face/5.gif)
