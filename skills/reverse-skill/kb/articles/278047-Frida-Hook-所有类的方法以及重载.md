---
title: '[原创]Frida Hook 所有类的方法以及重载'
url: https://bbs.kanxue.com/thread-278047.htm
tid: 278047
author: 复活甲
date: '2023-07-16'
tags: [Android安全, 原创, 基础理论, 逆向分析]
crawled_at: '2026-08-11T08:47:14+00:00'
replies: 13
---

## 0x01 前言

理论上我们可以通过反射的思想，写出一个脚本hook住所有的类，以及类的方法和重载，这样也就不用考虑定位了，自动化的实现我们快速hook的需求，将hook的所有日志保留，然后我们去搜索我们需要的东西。现在人工智能、大数据、AI这么火，怎么让我们逆向也变得智能呢？输入一个简单的指令，程序自我hook，快速计算，然后反馈关键的类、方法给我们。也许这样的工具已经有大佬实现了。

## 0x02 枚举所有的加载的类

enumerateLoadedClassesSync 列出当前已经加载的类,但是有很多，打印出来的数据多的看不清，全部hook APP 肯定会奔溃。

| 12345678 | `Java.perform(function(){` `var classz` `=` `Java.enumerateLoadedClassesSync()``console.log(classz)``})` `on.Animator$AnimatorListener,android.animation.AnimatorSet$SeekState,android.os.Registrant,android.app.ActivityManager$StackId,com.android.internal.telephony.ISub$Stub$Proxy,android.widget.FastScroller$``6``,android.media.EncoderCapabilities,android.hardware.camera2.CaptureResult$``2``,android.app.job.JobInfo$TriggerContentUri,android.app.ApplicationPackageManager$OnPermissionsChangeListenerDelegate,android.text.method.TextKeyListener,android.app.job.JobService,android.widget.GridLayout$``5``,android.app.WindowConfiguration,android.widget.TextView$``3``,android.app.ActivityManager$RunningAppProcessInfo,android.security.net.config.CertificateSource,android.app.assist.AssistStructure$ViewNode,android.media.Utils,android.database``...` |
|-|-|

可以过滤出我们需要的类

| 12345678910 | `Java.perform(function(){` `var classz` `=` `Java.enumerateLoadedClassesSync();``for``(var i``=``0``;i<classz.length;i``+``+``){``if` `(classz[i].indexOf(``"com.xiaojianbang.app"``) !``=` `-``1``){``console.log(classz[i])` `}``}``})` |
|-|-|

返回的结果，可以看出，从几百，几千缩减了到几个几十个，在对他们进行hook，此时问题应该不大。先来看结果：

| 123456789101112131415 | `[Xiaomi MI` `8``::HookTestDemo]``-``> com.xiaojianbang.app.DESede``com.xiaojianbang.app.Money$innerClass``com.xiaojianbang.app.Money``com.xiaojianbang.app.MainActivity$``1``com.xiaojianbang.app.MainActivity``com.xiaojianbang.app.SHA``com.xiaojianbang.app.RSA``com.xiaojianbang.app.MAC``com.xiaojianbang.app.Utils``com.xiaojianbang.app.AES``com.xiaojianbang.app.DES``com.xiaojianbang.app.NativeHelper``com.xiaojianbang.app.RSAHex``com.xiaojianbang.app.MD5``com.xiaojianbang.app.ShufferMap` |
|-|-|

## 0x03 枚举一个类的所有方法

现在我们要 获取一个类的所有方法：

| 12345 | `var MainActivity` `=` `Java.use(``"com.xiaojianbang.app.MainActivity"``);``var methods` `=` `MainActivity.``class``.getDeclaredMethods();``for``(var i``=``0``;i<methods.length;i``+``+``){``console.log(methods[i].getName())``}` |
|-|-|

返回结果：

| 12345 | `[Xiaomi MI` `8``::HookTestDemo]``-``> decrypt``onClick``onCreate``showMap_``toastPrint` |
|-|-|

对比源代码 太多了所以部分截图，方法名也是一一对上的。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/961239_KWMKHA536KK4AUS.png)

## 0x04 hook 一个类其中的某个方法的所有重载

如果方法的重载只有2、3个可以手动写，但是有10个？100个？所有看代码：

| 12345678910111213141516 | `var Utils` `=` `Java.use(``"com.xiaojianbang.app.Utils"``);``Utils[``"test"``].implementation` `=` `function () {``console.log(``"test is called"``);``var ret` `=` `this.test();``console.log(``'test ret value is '` `+` `ret);``return` `ret;``};`  `结果：可以看出有三个重载``[Xiaomi MI` `8``::HookTestDemo]``-``> Error: test(): has more than one overload, use .overload(<signature>) to choose` `from``:``.overload()``.overload(``'com.xiaojianbang.app.Money'``)``.overload(``'int'``)``at throwOverloadError (frida``/``node_modules``/``frida``-``java``-``bridge``/``lib``/``class``-``factory.js:``1020``)``at frida``/``node_modules``/``frida``-``java``-``bridge``/``lib``/``class``-``factory.js:``707` |
|-|-|

利用反射的思想，来一次性hook住他们

| 12345678910111213 | `var Utils` `=` `Java.use(``"com.xiaojianbang.app.Utils"``);``var overloads` `=` `Utils[``"test"``].overloads;``for` `(var i``=``0``;i< overloads.length;i``+``+``){``overloads[i].implementation` `=` `function () {``var params` `=` `"";``for``(var j``=``0``;j<arguments.length;j``+``+``){``params` `=` `params` `+``arguments[j]``+``" "``}``console.log(``"params"``,params)` `return` `this.test.``apply``(this,arguments);``};``}` |
|-|-|

## 0x05 综合上面所有的，一次性hook多个类的所有方法及重载

### 完整代码如下：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051 | `var classz` `=` `Java.enumerateLoadedClassesSync();``for` `(var i` `=` `0``; i < classz.length; i``+``+``) {``if` `(classz[i].indexOf(``"om.xiaojianbang.app.Utils"``) !``=` `-``1``) {``var class_name` `=` `classz[i];` `console.log(``"class_name"``, class_name);` `var cz` `=` `Java.use(class_name);``var methods` `=` `cz.``class``.getDeclaredMethods();``for` `(var i1` `=` `0``; i1 < methods.length``-``1``; i1``+``+``) {``var classz_method_name` `=` `methods[i1].getName();` `console.log(``"classz_method_name => "``, class_name, classz_method_name)``try` `{``var overloadAyy` `=` `cz[classz_method_name].overloads;``console.log(overloadAyy)``if` `(overloadAyy && overloadAyy.length>``0``){``for` `(var i2` `=` `0``; i2 < overloadAyy.length; i2``+``+``) {``overloadAyy[i2].implementation` `=` `function () {``var params` `=` `"";``for` `(var j` `=` `0``; j < arguments.length; j``+``+``) {``params` `=` `params` `+` `arguments[j]` `+` `" "``}``console.log(``"params"``, class_name, classz_method_name, params)``return` `this[classz_method_name].``apply``(this, arguments);` `};``}``}``else``{``cz[classz_method_name].implementation` `=` `function () {``var params` `=` `"";``for` `(var j` `=` `0``; j < arguments.length; j``+``+``) {``params` `=` `params` `+` `arguments[j]` `+` `" "``}``console.log(``"params"``, class_name, classz_method_name, params)``return` `cz[classz_method_name].``apply``(this, arguments);`  `};``}`  `} catch (error) {``console.log(``"异常类的加载，请特殊处理"``, class_name, classz_method_name)` `}` `}` `}``}` |
|-|-|

---

# 回复

## 回复 by mb_lpcoesnt (#2)

*2023-7-16 20:22*

感谢分享

## 回复 by 秋狝 (#3)

*2023-7-16 23:29*

感谢分享

## 回复 by youxiaxy (#4)

*2023-7-17 07:57*

感谢分享

## 回复 by LowRebSwrd (#5)

*2023-7-20 11:13*

感谢分享

## 回复 by aqingadmin (#6)

*2023-7-20 14:44*

你是小肩膀学员吧

## 回复 by 复活甲 (#7)

*2023-7-20 21:20*

>
> [aqingadmin](https://bbs.kanxue.com/user-912974.htm)
>
>  你是小肩膀学员吧
>
>

哈哈哈 不是的。小肩膀的课B站有呢，课太贵了买不起呢

## 回复 by wyfe (#8)

*2023-7-21 19:33*

>
> [西贝巴巴](https://bbs.kanxue.com/user-961239.htm)
>
>  哈哈哈 不是的。小肩膀的课B站有呢，课太贵了买不起呢
>
>

那是哪机构的学员？你的文章像内部学习资料似的

## 回复 by 复活甲 (#9)

*2023-7-22 10:31*

小肩膀有本安卓逆向的书，内容还是很精辟的，推荐看下，对frida的介绍还是很详细的。还有肉师傅的课，看完会有不一样的体会。![image](https://bbs.kanxue.com/view/img/face/27.gif)

## 回复 by zxk1ng (#10)

*2023-8-14 09:05*

>
> [西贝巴巴](https://bbs.kanxue.com/user-961239.htm)
>
>  小肩膀有本安卓逆向的书，内容还是很精辟的，推荐看下，对frida的介绍还是很详细的。还有肉师傅的课，看完会有不一样的体会。[em_27]
>
>

请问小肩膀出的逆向书叫什么

## 回复 by 月淼Ym (#11)

*2024-2-19 18:10*

感谢分享

## 回复 by Kimerpa (#12)

*2024-2-27 15:32*

谢谢分享，但是看类名怎么感觉是小肩膀的课程啊

## 回复 by 蓝色之冰 (#13)

*2024-5-22 22:51*

var methods = cz.class.getDeclaredMethods();
        for (var i1 = 0; i1 < methods.length-1; i1++) {
            var classz_method_name = methods[i1].getName(); //getName()返回很多重复的方法名 下面代码使用classz_method_name会有问题
}

## 回复 by 复活甲 (#14)

*2024-5-23 09:11*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  蓝色之冰](https://bbs.kanxue.com/user-71864.htm)
>
>  var&nbsp;methods&nbsp;=&nbsp;cz.class.getDeclaredMethods();&nbsp;&nbsp;&nbsp ...
>
>

好的，感谢指出问题。一个类下除了方法重载，还能用到很多重复的方法名？（内部类/匿名类？继承？）APP样本能发我一份吗，互相学习下
