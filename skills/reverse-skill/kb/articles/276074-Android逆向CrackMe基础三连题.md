---
title: '[原创] Android逆向CrackMe基础三连题'
url: https://bbs.kanxue.com/thread-276074.htm
tid: 276074
author: 暮至夜寒
date: '2023-02-11'
tags: [Android安全, 原创, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:53:07+08:00'
replies: 2
---

闲来无事，去找一些CrackMe练练手，偶然发现一个网站有三个CrackMe，但都比较简单，只用到了Jadx-gui和Frida，现在把这三道题解法贴出来。
原站地址：<https://persianov.net/crackme-challenges-for-android>

## CrackMe0x01

这道题的介绍是： The very basic crackme challenge. Gives you chance to get familiar with all Android RE tools.
翻译过来就是这个题很简单，让你练练手熟悉一下。
我们先安装App看看（文末上传三个APP）
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_R69QG5K3K4C2SSC.jpeg)
可以看到只有一个密码的提交键
于是我们打开Jadx-gui来观赏一下。
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_TZMAN4KK88CSQJR.png)
打开Jdax-gui后先找到按键的onClick函数，然后便看到了明晃晃的大字**“Congratulations！”**。
成功的入口就是flag不为空，所以我们从getFlag继续点进去
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_7H82885QSMX45XZ.png)
点进去之后发现getFlag里面嵌套了一个equals判断，为true的话就成功了，我们进去看一下有没有密码。
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_92HW56ECCFVQDBW.png)
点开时候发现果然是练手题，明文密码就直接出现了，我们直接输入密码就可以进入程序了。
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_M5TWYRPA8NEE9Y2.jpeg)

## CrackMe0x02

这道题的介绍是： What if JD-GUI doesn’t show you the password?
翻译过来就是，这次Jadx-gui可就不显示密码了。
我们先安装App看看（文末上传三个APP）
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_RZETV8RQ26MMAUK.jpeg)
赫赫，如出一辙，那就继续用Jadx-gui看看
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_7336DCQMM6WB5RN.png)
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_5RXWG77H53DKUZ7.png)
可以看到前面的函数都是一样的操作，但题目说没有明文，那我们继续看getData里面是什么。
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_W9DFHBMFH3HVESC.png)
我们可以看到，这次的密码实在资源文件中，但资源文件中的secret是不可见明文的，那这时我们就要用到Frida来hook一下看看了。
新版Jadx-gui可以直接右键复制Frida代码，以下就是Frida代码了。

| 12345678910111213 | `function main() {``Java.perform( function(){``let Data` `=` `Java.use(``"com.entebra.crackme0x02.Data"``);``Data[``"getData"``].implementation` `=` `function (context) {``console.log(``'getData is called'` `+` `', '` `+` `'context: '` `+` `context);``let ret` `=` `this.getData(context);``console.log(``'getData ret value is '` `+` `ret);``return` `ret;``};``})``}` `setImmediate(main);` |
|-|-|

然后我我们启动hook，再随便输入一个字符串，触发一下getData函数
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_TFS6VYF9EGAFTYS.png)
这下我们就看到密码了，输入密码后就成功进去了。
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_GWW9FDJ2PKFZ5AF.jpeg)

## CrackMe0x03

这道题的介绍是： Some hashes, cats and strings generation.
翻译过来就是，这次Jadx-gui不仅不显示密码了，还用到了哈希。
我们先安装App看看（文末上传三个APP）
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_AFFRE7FK87DMUVR.jpeg)
赫赫，我就猜到还是一样的，老样子Jadx-gui
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_HJQER9KKWVRAQR9.png)
开局还是一样的操作，我们再进去看看
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_SKHVXGUVN27AGP5.png)
这次的getFlag中增加了一个isPassWorkOk函数，当这个函数返回true后，就会进入程序显示flag。
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_UQHG4ZXYG47SA66.png)
我们可以看到在isPassWorkOk里面是直接通过hash来进行比较了，被比较的hash值是：

>
> ac43bb53262e4edd82c0e82a93c84755
>
>
>

 我去了各个md5网站都没有找到这个值的明文，但我们可以看出来，这次的密码长度为6，所以如果暴力遍历的话有成百上千亿种方案，我先是把数字和小写字母的组合遍历一遍后没有结果，于是就想着只要拿到flag就可以了。
接着就开始写Frida代码，只要把isPassWork返回true就可以得到flag进入程序了，代码如下：

| 12345678910111213 | `function main() {``Java.perform( function(){``let Data` `=` `Java.use(``"net.persianov.crackme0x03.Data"``);``Data[``"isPasswordOk"``].implementation` `=` `function (``str``) {``console.log(``'isPasswordOk is called'` `+` `', '` `+` `'str: '` `+` `str``);``let ret` `=` `true;``console.log(``'isPasswordOk ret value is '` `+` `ret);``return` `ret;``};``})``}` `setImmediate(main);` |
|-|-|

hook之后随便输入一个6位数的字符串
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_QB6S6AVS6527SRF.png)
然后我们就得到flag进去了
 ![image](https://bbs.kanxue.com/upload/attach/202302/959049_XUKJQGEYMHRUVYJ.jpeg)

 三道基础题这就解完了，下次再找找有没有稍微提升一些的再分享给大家。

上传的附件：
- crackme_0x03.apk

（1.22MB，48次下载）

---

# 回复

## 回复 by dp_grost (#2)

*2023-2-22 00:08*

能请教一下，楼主是如何判断是6位的

## 回复 by fireworld (#3)

*2023-2-22 09:37*

>
> [dp_grost](https://bbs.kanxue.com/user-921443.htm)
>
>  能请教一下，楼主是如何判断是6位的
>
>

代码里面有
this.password_length = 6;
this.password_hash = "ac43bb53262e4edd82c0e82a93c84755";
