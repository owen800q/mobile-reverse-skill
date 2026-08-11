---
title: '[原创]利用自制脱壳机配合ai暴力半自动化还原vmp完成app重打包'
url: https://bbs.kanxue.com/thread-282432.htm
tid: 282432
author: 程序员小潘
date: '2024-07-09'
tags: [Android安全, 原创, 脱壳反混淆]
crawled_at: '2026-08-11T08:45:04+00:00'
replies: 23
---

# 简单介绍

## [part脱壳分析机](https://github.com/panchoGG/PartImage/tree/main)是在fart基础上升级的脱壳机，基于安卓13，主要有以下几点修改：

### 1）百分百重写所有fart代码与流程，完全移除java层，脱壳逻辑全部转为c++层实现

### 2）支持一键脱壳，梦回fart8，内置完善过滤机制。直接打开app等几分钟即可脱全壳包括抽取的函数，截至发稿日期通杀所有厂商个人/企业版一二代壳

### 3）支持批量vmp函数jni调用流程详细跟踪

# 来波实战

豌豆荚上随便找个应用安装到脱壳机 ![image](https://bbs.kanxue.com/upload/attach/202407/877942_F84XQ7YX5BXDQCR.webp)
一条命令标记app，告诉脱壳机这是要脱壳的应用，然后直接打开app等待日志脱壳完成即可。
 ![image](https://bbs.kanxue.com/upload/attach/202407/877942_XDMRSG84H4B4KHA.webp)
脱下来会有这些东西：
 ![image](https://bbs.kanxue.com/upload/attach/202407/877942_SEM2ZN5TRWTVJVA.webp)
直接一键修复，这样的话，就把所有的抽取方法都回填回去了：
 ![image](https://bbs.kanxue.com/upload/attach/202407/877942_KDH2DU67ESUCSDH.webp)
把修复好的dex直接放回apk中，拖进jadx看看现在的样子：
 ![image](https://bbs.kanxue.com/upload/attach/202407/877942_VG49GXXWXGA7S8F.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202407/877942_AQF94AUV34WV6K8.webp)
除了native函数，其他的抽取/非抽取的都已经完全修复。那接下来就是还原这些native了

part支持批量jni调用跟踪，一条命令启用后跟踪下来的日志会以文件形式保存，内容如下：
 ![image](https://bbs.kanxue.com/upload/attach/202407/877942_TX7BJ5RR7EKFTGB.webp)

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308309310311312313314315316317318319320321322323324325326327328329330331332333334335336337338339340341342343344345346347348349350351352353354355356357358359360361362363364365366367368369370371372373374375376377378379380381382383384385386387388389390391392393394395396397398399400401402403404405406407408409410411412413414415416417418419420421422423424425426427428429430431432433434435436437438439440441 | `start trace method:void xxx.DocinHomeActivity.onCreate(android.os.Bundle) Addr:``0x703c3896e8``__android_log_print addr:` `0x70c5a0b714``so info` `not` `found``jni` `=``=``=``> PushLocalFrame: capacity` `=` `32``jni` `=``=``=``> NewLocalRef:` `class` `=` `null``jni` `=``=``=``> FindClass: com``/``slidingmenu``/``lib``/``app``/``SlidingFragmentActivity``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<com.slidingmenu.lib.app.SlidingFragmentActivity>, address:` `0x16c69f08``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<com.slidingmenu.lib.app.SlidingFragmentActivity>, method` `=` `onCreate, sig` `=` `(Landroid``/``os``/``Bundle;)V``jni` `=``=``=``> FindMethodID: name: onCreate sig: (Landroid``/``os``/``Bundle;)V is_static: false``Calling` `object` `public method: void com.slidingmenu.lib.app.SlidingFragmentActivity.onCreate(android.os.Bundle), args_size:` `8``, method address:` `0x70c7843288``this:` `0x12f56bc0``arg1:` `0x0``return``: void``jni` `=``=``=``> GetObjectClass: java.lang.Class<xxx.DocinHomeActivity>, address:` `0x12f56bc0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c69f08``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<com.slidingmenu.lib.app.SlidingFragmentActivity>, method` `=` `setContentView, sig` `=` `(I)V``jni` `=``=``=``> FindMethodID: name: setContentView sig: (I)V is_static: false``Calling` `object` `public method: void com.slidingmenu.lib.app.SlidingFragmentActivity.setContentView(``int``), args_size:` `8``, method address:` `0x70c78433a0``this:` `0x12f56bc0``arg1:` `2131427651``return``: void``jni` `=``=``=``> FindClass: t4``/``p``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<t4.p>, address:` `0x16c64ed8``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<t4.p>, method` `=` `k, sig` `=` `(Landroid``/``app``/``Activity;)V``jni` `=``=``=``> FindMethodID: name: k sig: (Landroid``/``app``/``Activity;)V is_static: true``Calling native static public method: void t4.p.k(android.app.Activity), args_size:` `4``, method address:` `0x702e572300``arg0:` `0x12f56bc0` `(xxx.DocinHomeActivity)``return``: void``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c64ed8``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<t4.p>, method` `=` `h, sig` `=` `(Landroid``/``app``/``Activity;)V``jni` `=``=``=``> FindMethodID: name: h sig: (Landroid``/``app``/``Activity;)V is_static: true``Calling native static public method: void t4.p.h(android.app.Activity), args_size:` `4``, method address:` `0x702e572288``arg0:` `0x12f56bc0` `(xxx.DocinHomeActivity)``return``: void``jni` `=``=``=``> FindClass: com``/``docin``/``home``/``DocinHomeActivity``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<xxx.DocinHomeActivity>, address:` `0x16c66f50``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity>, method` `=` `initView, sig` `=` `()V``jni` `=``=``=``> FindMethodID: name: initView sig: ()V is_static: false``Calling` `object` `private method: void xxx.DocinHomeActivity.initView(), args_size:` `4``, method address:` `0x70c7842db8``this:` `0x12f56bc0``return``: void``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c66f50``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity>, method` `=` `initData, sig` `=` `()V``jni` `=``=``=``> FindMethodID: name: initData sig: ()V is_static: false``Calling` `object` `private method: void xxx.DocinHomeActivity.initData(), args_size:` `4``, method address:` `0x70c7842d40``this:` `0x12f56bc0``return``: void``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c66f50``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity>, method` `=` `initSlidingMenu, sig` `=` `()V``jni` `=``=``=``> FindMethodID: name: initSlidingMenu sig: ()V is_static: false``Calling` `object` `private method: void xxx.DocinHomeActivity.initSlidingMenu(), args_size:` `4``, method address:` `0x70c7842d90``this:` `0x12f56bc0``return``: void``jni` `=``=``=``> FindClass: java``/``lang``/``String``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<java.lang.String>, method` `=` `intern``, sig` `=` `()Ljava``/``lang``/``String;``jni` `=``=``=``> FindMethodID: name:` `intern` `sig: ()Ljava``/``lang``/``String; is_static: false``jni` `=``=``=``> ExceptionClear``jni` `=``=``=``> NewStringUTF: DocinHomeActivity, address:` `0x13a0efe8``Calling` `object` `public method: java.lang.String java.lang.String.``intern``(), args_size:` `4``, method address:` `0x70acc578``this:` `0x13a0efe8``return``:` `0x138cbd60``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.String, address:` `0x138cbd60``jni` `=``=``=``> NewStringUTF: processIntentData >>> onCreate, address:` `0x13a0f010``Calling` `object` `public method: java.lang.String java.lang.String.``intern``(), args_size:` `4``, method address:` `0x70acc578``this:` `0x13a0f010``return``:` `0x13a0f010``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.String, address:` `0x13a0f010``jni` `=``=``=``> FindClass: t4``/``j``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<t4.j>, address:` `0x16c64c30``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<t4.j>, method` `=` `b, sig` `=` `(Ljava``/``lang``/``String;Ljava``/``lang``/``String;)V``jni` `=``=``=``> FindMethodID: name: b sig: (Ljava``/``lang``/``String;Ljava``/``lang``/``String;)V is_static: true``Calling native static public method: void t4.j.b(java.lang.String, java.lang.String), args_size:` `8``, method address:` `0x702e729560``arg0: DocinHomeActivity,` `0x138cbd60``arg1: processIntentData >>> onCreate,` `0x13a0f010``return``: void``jni` `=``=``=``> GetObjectClass: java.lang.Class<xxx.DocinHomeActivity>, address:` `0x12f56bc0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x70ef2040``Calling` `object` `public method: android.content.Intent android.app.Activity.getIntent(), args_size:` `4``, method address:` `0x71423898``this:` `0x12f56bc0``return``:` `0x12c40780``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c66f50``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity>, method` `=` `processIntentData, sig` `=` `(Landroid``/``content``/``Intent;)V``jni` `=``=``=``> FindMethodID: name: processIntentData sig: (Landroid``/``content``/``Intent;)V is_static: false``Calling` `object` `private method: void xxx.DocinHomeActivity.processIntentData(android.content.Intent), args_size:` `8``, method address:` `0x70c7842e30``this:` `0x12f56bc0``arg1:` `0x12c40780` `(android.content.Intent)``return``: void``jni` `=``=``=``> FindClass: com``/``docin``/``xxx``/``DocinApplication``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<xxx.xxx.DocinApplication>, address:` `0x16c629b8``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<xxx.xxx.DocinApplication>, method` `=` `getInstance, sig` `=` `()Lcom``/``docin``/``xxx``/``DocinApplication;``jni` `=``=``=``> FindMethodID: name: getInstance sig: ()Lcom``/``docin``/``xxx``/``DocinApplication; is_static: true``Calling native static public method: xxx.xxx.DocinApplication xxx.xxx.DocinApplication.getInstance(), args_size:` `0``, method address:` `0x70c783c3e8``return``:` `0x16c05118``jni` `=``=``=``> GetObjectClass: java.lang.Class<xxx.xxx.DocinApplication>, address:` `0x16c05118``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c629b8``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<xxx.xxx.DocinApplication>, method` `=` `getLocalBroadcastManager, sig` `=` `()Landroidx``/``localbroadcastmanager``/``content``/``LocalBroadcastManager;``jni` `=``=``=``> FindMethodID: name: getLocalBroadcastManager sig: ()Landroidx``/``localbroadcastmanager``/``content``/``LocalBroadcastManager; is_static: false``Calling` `object` `public method: androidx.localbroadcastmanager.content.LocalBroadcastManager xxx.xxx.DocinApplication.getLocalBroadcastManager(), args_size:` `4``, method address:` `0x70c783c5f0``this:` `0x16c05118``return``:` `0x16d26aa8``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c66f50``jni` `=``=``=``> GetFieldID:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity>, field` `=` `mLocalBroadcastManager, sig` `=` `Landroidx``/``localbroadcastmanager``/``content``/``LocalBroadcastManager;``jni` `=``=``=``> FindFieldID: name: mLocalBroadcastManager sig: Landroidx``/``localbroadcastmanager``/``content``/``LocalBroadcastManager;``jni` `=``=``=``> SetObjectField: xxx.DocinHomeActivity``-``>androidx.localbroadcastmanager.content.LocalBroadcastManager xxx.DocinHomeActivity.mLocalBroadcastManager` `=` `androidx.localbroadcastmanager.content.LocalBroadcastManager, obj address:` `0x12f56bc0``, java_value address:` `0x16d26aa8``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c629b8``Calling native static public method: xxx.xxx.DocinApplication xxx.xxx.DocinApplication.getInstance(), args_size:` `0``, method address:` `0x70c783c3e8``return``:` `0x16c05118``jni` `=``=``=``> GetObjectClass: java.lang.Class<xxx.xxx.DocinApplication>, address:` `0x16c05118``jni` `=``=``=``> FindClass: com``/``docin``/``reader``/``base``/``base``/``BaseApplication``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<xxx.reader.base.base.BaseApplication>, address:` `0x16c614e0``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<xxx.reader.base.base.BaseApplication>, method` `=` `addActivity, sig` `=` `(Landroid``/``app``/``Activity;)V``jni` `=``=``=``> FindMethodID: name: addActivity sig: (Landroid``/``app``/``Activity;)V is_static: false``Calling` `object` `public method: void xxx.reader.base.base.BaseApplication.addActivity(android.app.Activity), args_size:` `8``, method address:` `0x70c783cbb8``this:` `0x16c05118``arg1:` `0x12f56bc0` `(xxx.DocinHomeActivity)``return``: void``jni` `=``=``=``> FindClass: com``/``docin``/``reader``/``base``/``receiver``/``NetworkChangeReceiver``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<xxx.reader.base.receiver.NetworkChangeReceiver>, address:` `0x138caeb0``jni` `=``=``=``> GetStaticFieldID:` `class` `=` `java.lang.Class<xxx.reader.base.receiver.NetworkChangeReceiver>, field` `=` `a, sig` `=` `Ljava``/``util``/``ArrayList;``jni` `=``=``=``> FindFieldID: name: a sig: Ljava``/``util``/``ArrayList;``Calling native static public method: void xxx.reader.base.receiver.NetworkChangeReceiver.<clinit>(), args_size:` `0``, method address:` `0x702bfaaee0``return``: void``jni` `=``=``=``> FindClass: java``/``lang``/``reflect``/``Field``jni` `=``=``=``> FindClass: java``/``lang``/``Class``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<java.lang.Class>, method` `=` `getInterfaces, sig` `=` `()[Ljava``/``lang``/``Class;``jni` `=``=``=``> FindMethodID: name: getInterfaces sig: ()[Ljava``/``lang``/``Class; is_static: false``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<java.lang.reflect.Field>, method` `=` `getDeclaringClass, sig` `=` `()Ljava``/``lang``/``Class;``jni` `=``=``=``> FindMethodID: name: getDeclaringClass sig: ()Ljava``/``lang``/``Class; is_static: false``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x138caeb0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x138caeb0``jni` `=``=``=``> GetStaticFieldID:` `class` `=` `java.lang.Class<xxx.reader.base.receiver.NetworkChangeReceiver>, field` `=` `a, sig` `=` `Ljava``/``util``/``ArrayList;``jni` `=``=``=``> FindFieldID: name: a sig: Ljava``/``util``/``ArrayList;``Calling` `object` `public method: java.lang.Class[] java.lang.Class.getInterfaces(), args_size:` `4``, method address:` `0x70ad8590``this:` `0x138caeb0``return``:` `0x70b86008``jni` `=``=``=``> GetArrayLength:` `0``,` `type``: java.lang.Class[], address:` `0x70b86008``jni` `=``=``=``> GetSuperclass: java.lang.Class<xxx.reader.base.receiver.NetworkChangeReceiver> extends java.lang.Class<android.content.BroadcastReceiver>``jni` `=``=``=``> GetStaticFieldID:` `class` `=` `java.lang.Class<android.content.BroadcastReceiver>, field` `=` `a, sig` `=` `Ljava``/``util``/``ArrayList;``jni` `=``=``=``> FindFieldID: name: a sig: Ljava``/``util``/``ArrayList;``Calling` `object` `public method: void java.lang.NoSuchFieldError.<init>(java.lang.String), args_size:` `8``, method address:` `0x70a66400``this:` `0x13a2ced0``arg1: no` `"Ljava/util/ArrayList;"` `field` `"a"` `in` `class` `"Landroid/content/BroadcastReceiver;"` `or` `its superclasses,` `0x13a2cef0``return``: void``jni` `=``=``=``> ExceptionClear``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<xxx.reader.base.receiver.NetworkChangeReceiver>, address:` `0x138caeb0``jni` `=``=``=``> GetStaticObjectField: field` `=` `java.lang.Class<xxx.reader.base.receiver.NetworkChangeReceiver>``-``>java.util.ArrayList xxx.reader.base.receiver.NetworkChangeReceiver.a, obj address:` `0x13a2ceb8``jni` `=``=``=``> GetObjectClass: java.lang.Class<java.util.ArrayList>, address:` `0x13a2ceb8``jni` `=``=``=``> FindClass: java``/``util``/``ArrayList``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<java.util.ArrayList>, address:` `0x70998b40``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<java.util.ArrayList>, method` `=` `add, sig` `=` `(Ljava``/``lang``/``Object``;)Z``jni` `=``=``=``> FindMethodID: name: add sig: (Ljava``/``lang``/``Object``;)Z is_static: false``Calling` `object` `public method: boolean java.util.ArrayList.add(java.lang.``Object``), args_size:` `8``, method address:` `0x70a879c8``this:` `0x13a2ceb8``arg1:` `0x12f56bc0` `(xxx.DocinHomeActivity)``return``: true``jni` `=``=``=``> FindClass: a4``/``e``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<a4.e>, address:` `0x13189488``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<a4.e>, method` `=` `h, sig` `=` `()La4``/``e;``jni` `=``=``=``> FindMethodID: name: h sig: ()La4``/``e; is_static: true``Calling native static public method: void a4.e.<clinit>(), args_size:` `0``, method address:` `0x702e4e7b00``return``: void``Calling native static public method: a4.e a4.e.h(), args_size:` `0``, method address:` `0x702e4e7bf0``return``:` `0x13a2dc50``jni` `=``=``=``> GetObjectClass: java.lang.Class<a4.e>, address:` `0x13a2dc50``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x13189488``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<a4.e>, method` `=` `j, sig` `=` `(Landroid``/``app``/``Activity;)V``jni` `=``=``=``> FindMethodID: name: j sig: (Landroid``/``app``/``Activity;)V is_static: false``Calling` `object` `public method: void a4.e.j(android.app.Activity), args_size:` `8``, method address:` `0x702e4e7cb8``this:` `0x13a2dc50``arg1:` `0x12f56bc0` `(xxx.DocinHomeActivity)``return``: void``jni` `=``=``=``> FindClass: com``/``docin``/``newshelf``/``QrCodeScanDocReceiver``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<xxx.newshelf.QrCodeScanDocReceiver>, address:` `0x138cb0d0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x138cb0d0``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<xxx.newshelf.QrCodeScanDocReceiver>, method` `=` `<init>, sig` `=` `(Landroid``/``app``/``Activity;)V``jni` `=``=``=``> FindMethodID: name: <init> sig: (Landroid``/``app``/``Activity;)V is_static: false``Calling native static public method: void xxx.newshelf.QrCodeScanDocReceiver.<clinit>(), args_size:` `0``, method address:` `0x702bfaafc0``return``: void``jni` `=``=``=``> PushLocalFrame: capacity` `=` `1``jni` `=``=``=``> NewObjectA:` `class` `=` `java.lang.Class<xxx.newshelf.QrCodeScanDocReceiver>, method` `=` `void xxx.newshelf.QrCodeScanDocReceiver.<init>(android.app.Activity), address:` `0x13a2e368``Calling` `object` `public method: void xxx.newshelf.QrCodeScanDocReceiver.<init>(android.app.Activity), args_size:` `8``, method address:` `0x702bfaafe8``this:` `0x13a2e368``arg1:` `0x12f56bc0` `(xxx.DocinHomeActivity)``return``: void``jni` `=``=``=``> PopLocalFrame: survivor_class` `=` `xxx.newshelf.QrCodeScanDocReceiver``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c66f50``jni` `=``=``=``> GetFieldID:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity>, field` `=` `mScanDocReceiver, sig` `=` `Lcom``/``docin``/``newshelf``/``QrCodeScanDocReceiver;``jni` `=``=``=``> FindFieldID: name: mScanDocReceiver sig: Lcom``/``docin``/``newshelf``/``QrCodeScanDocReceiver;``jni` `=``=``=``> SetObjectField: xxx.DocinHomeActivity``-``>xxx.newshelf.QrCodeScanDocReceiver xxx.DocinHomeActivity.mScanDocReceiver` `=` `xxx.newshelf.QrCodeScanDocReceiver, obj address:` `0x12f56bc0``, java_value address:` `0x13a2e368``jni` `=``=``=``> FindClass: android``/``content``/``IntentFilter``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<android.content.IntentFilter>, address:` `0x70ee4280``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x138cb0d0``jni` `=``=``=``> GetStaticFieldID:` `class` `=` `java.lang.Class<xxx.newshelf.QrCodeScanDocReceiver>, field` `=` `b, sig` `=` `Ljava``/``lang``/``String;``jni` `=``=``=``> FindFieldID: name: b sig: Ljava``/``lang``/``String;``jni` `=``=``=``> FindClass: java``/``lang``/``reflect``/``Field``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x138cb0d0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x138cb0d0``jni` `=``=``=``> GetStaticFieldID:` `class` `=` `java.lang.Class<xxx.newshelf.QrCodeScanDocReceiver>, field` `=` `b, sig` `=` `Ljava``/``lang``/``String;``jni` `=``=``=``> FindFieldID: name: b sig: Ljava``/``lang``/``String;``Calling` `object` `public method: java.lang.Class[] java.lang.Class.getInterfaces(), args_size:` `4``, method address:` `0x70ad8590``this:` `0x138cb0d0``return``:` `0x70b86008``jni` `=``=``=``> GetArrayLength:` `0``,` `type``: java.lang.Class[], address:` `0x70b86008``jni` `=``=``=``> GetSuperclass: java.lang.Class<xxx.newshelf.QrCodeScanDocReceiver> extends java.lang.Class<android.content.BroadcastReceiver>``jni` `=``=``=``> GetStaticFieldID:` `class` `=` `java.lang.Class<android.content.BroadcastReceiver>, field` `=` `b, sig` `=` `Ljava``/``lang``/``String;``jni` `=``=``=``> FindFieldID: name: b sig: Ljava``/``lang``/``String;``Calling` `object` `public method: void java.lang.NoSuchFieldError.<init>(java.lang.String), args_size:` `8``, method address:` `0x70a66400``this:` `0x13a2e398``arg1: no` `"Ljava/lang/String;"` `field` `"b"` `in` `class` `"Landroid/content/BroadcastReceiver;"` `or` `its superclasses,` `0x13a2e3b8``return``: void``jni` `=``=``=``> ExceptionClear``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<xxx.newshelf.QrCodeScanDocReceiver>, address:` `0x138cb0d0``jni` `=``=``=``> GetStaticObjectField: field` `=` `java.lang.Class<xxx.newshelf.QrCodeScanDocReceiver>``-``>java.lang.String xxx.newshelf.QrCodeScanDocReceiver.b, obj address:` `0x13a2e2a8``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x70ee4280``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<android.content.IntentFilter>, method` `=` `<init>, sig` `=` `(Ljava``/``lang``/``String;)V``jni` `=``=``=``> FindMethodID: name: <init> sig: (Ljava``/``lang``/``String;)V is_static: false``jni` `=``=``=``> PushLocalFrame: capacity` `=` `1``jni` `=``=``=``> NewObjectA:` `class` `=` `java.lang.Class<android.content.IntentFilter>, method` `=` `void android.content.IntentFilter.<init>(java.lang.String), address:` `0x13a2e590``Calling` `object` `public method: void android.content.IntentFilter.<init>(java.lang.String), args_size:` `8``, method address:` `0x7128c5f8``this:` `0x13a2e590``arg1: xxx.qrcodescan.doc.RECEIVER,` `0x13a2e2a8``return``: void``jni` `=``=``=``> PopLocalFrame: survivor_class` `=` `android.content.IntentFilter``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c66f50``jni` `=``=``=``> GetObjectField: field` `=` `java.lang.Class<xxx.DocinHomeActivity>``-``>xxx.newshelf.QrCodeScanDocReceiver xxx.DocinHomeActivity.mScanDocReceiver, obj address:` `0x12f56bc0``jni` `=``=``=``> GetObjectClass: java.lang.Class<xxx.DocinHomeActivity>, address:` `0x12f56bc0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x70ef2040``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<android.app.Activity>, method` `=` `registerReceiver, sig` `=` `(Landroid``/``content``/``BroadcastReceiver;Landroid``/``content``/``IntentFilter;)Landroid``/``content``/``Intent;``jni` `=``=``=``> FindMethodID: name: registerReceiver sig: (Landroid``/``content``/``BroadcastReceiver;Landroid``/``content``/``IntentFilter;)Landroid``/``content``/``Intent; is_static: false``Calling` `object` `public method: android.content.Intent android.content.ContextWrapper.registerReceiver(android.content.BroadcastReceiver, android.content.IntentFilter), args_size:` `12``, method address:` `0x71290800``this:` `0x12f56bc0``arg1:` `0x13a2e368` `(xxx.newshelf.QrCodeScanDocReceiver)``arg2:` `0x13a2e590` `(android.content.IntentFilter)``return``:` `0x0``jni` `=``=``=``> FindClass: com``/``docin``/``home``/``DocinHomeActivity$i``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<xxx.DocinHomeActivity$i>, address:` `0x13a2ee78``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x13a2ee78``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity$i>, method` `=` `<init>, sig` `=` `(Lcom``/``docin``/``home``/``DocinHomeActivity;Lcom``/``docin``/``home``/``DocinHomeActivity$a;)V``jni` `=``=``=``> FindMethodID: name: <init> sig: (Lcom``/``docin``/``home``/``DocinHomeActivity;Lcom``/``docin``/``home``/``DocinHomeActivity$a;)V is_static: false``jni` `=``=``=``> PushLocalFrame: capacity` `=` `1``jni` `=``=``=``> NewObjectA:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity$i>, method` `=` `void xxx.DocinHomeActivity$i.<init>(xxx.DocinHomeActivity, xxx.DocinHomeActivity$a), address:` `0x13a2f288``Calling` `object` `public method: void xxx.DocinHomeActivity$i.<init>(xxx.DocinHomeActivity, xxx.DocinHomeActivity$a), args_size:` `12``, method address:` `0x702bed4c60``this:` `0x13a2f288``arg1:` `0x12f56bc0` `(xxx.DocinHomeActivity)``arg2:` `0x0``return``: void``jni` `=``=``=``> PopLocalFrame: survivor_class` `=` `xxx.DocinHomeActivity$i``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c66f50``jni` `=``=``=``> GetFieldID:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity>, field` `=` `mDocinHomeHandler, sig` `=` `Lcom``/``docin``/``home``/``DocinHomeActivity$i;``jni` `=``=``=``> FindFieldID: name: mDocinHomeHandler sig: Lcom``/``docin``/``home``/``DocinHomeActivity$i;``jni` `=``=``=``> SetObjectField: xxx.DocinHomeActivity``-``>xxx.DocinHomeActivity$i xxx.DocinHomeActivity.mDocinHomeHandler` `=` `xxx.DocinHomeActivity$i, obj address:` `0x12f56bc0``, java_value address:` `0x13a2f288``jni` `=``=``=``> FindClass: com``/``docin``/``broadcast``/``DocumentPurchaseReceiver``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<xxx.broadcast.DocumentPurchaseReceiver>, address:` `0x16de4fb0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c66f50``jni` `=``=``=``> GetObjectField: field` `=` `java.lang.Class<xxx.DocinHomeActivity>``-``>xxx.DocinHomeActivity$i xxx.DocinHomeActivity.mDocinHomeHandler, obj address:` `0x12f56bc0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16de4fb0``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<xxx.broadcast.DocumentPurchaseReceiver>, method` `=` `<init>, sig` `=` `(Landroid``/``os``/``Handler;)V``jni` `=``=``=``> FindMethodID: name: <init> sig: (Landroid``/``os``/``Handler;)V is_static: false``Calling native static public method: void xxx.broadcast.DocumentPurchaseReceiver.<clinit>(), args_size:` `0``, method address:` `0x702c298898``return``: void``jni` `=``=``=``> PushLocalFrame: capacity` `=` `1``jni` `=``=``=``> NewObjectA:` `class` `=` `java.lang.Class<xxx.broadcast.DocumentPurchaseReceiver>, method` `=` `void xxx.broadcast.DocumentPurchaseReceiver.<init>(android.os.Handler), address:` `0x13a2f350``Calling` `object` `public method: void xxx.broadcast.DocumentPurchaseReceiver.<init>(android.os.Handler), args_size:` `8``, method address:` `0x702c2988c0``this:` `0x13a2f350``arg1:` `0x13a2f288` `(xxx.DocinHomeActivity$i)``return``: void``jni` `=``=``=``> PopLocalFrame: survivor_class` `=` `xxx.broadcast.DocumentPurchaseReceiver``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c66f50``jni` `=``=``=``> GetFieldID:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity>, field` `=` `mDocumentPurchaseReceiver, sig` `=` `Lcom``/``docin``/``broadcast``/``DocumentPurchaseReceiver;``jni` `=``=``=``> FindFieldID: name: mDocumentPurchaseReceiver sig: Lcom``/``docin``/``broadcast``/``DocumentPurchaseReceiver;``jni` `=``=``=``> SetObjectField: xxx.DocinHomeActivity``-``>xxx.broadcast.DocumentPurchaseReceiver xxx.DocinHomeActivity.mDocumentPurchaseReceiver` `=` `xxx.broadcast.DocumentPurchaseReceiver, obj address:` `0x12f56bc0``, java_value address:` `0x13a2f350``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x70ee4280``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16de4fb0``jni` `=``=``=``> GetStaticFieldID:` `class` `=` `java.lang.Class<xxx.broadcast.DocumentPurchaseReceiver>, field` `=` `b, sig` `=` `Ljava``/``lang``/``String;``jni` `=``=``=``> FindFieldID: name: b sig: Ljava``/``lang``/``String;``jni` `=``=``=``> FindClass: java``/``lang``/``reflect``/``Field``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16de4fb0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16de4fb0``jni` `=``=``=``> GetStaticFieldID:` `class` `=` `java.lang.Class<xxx.broadcast.DocumentPurchaseReceiver>, field` `=` `b, sig` `=` `Ljava``/``lang``/``String;``jni` `=``=``=``> FindFieldID: name: b sig: Ljava``/``lang``/``String;``Calling` `object` `public method: java.lang.Class[] java.lang.Class.getInterfaces(), args_size:` `4``, method address:` `0x70ad8590``this:` `0x16de4fb0``return``:` `0x70b86008``jni` `=``=``=``> GetArrayLength:` `0``,` `type``: java.lang.Class[], address:` `0x70b86008``jni` `=``=``=``> GetSuperclass: java.lang.Class<xxx.broadcast.DocumentPurchaseReceiver> extends java.lang.Class<android.content.BroadcastReceiver>``jni` `=``=``=``> GetStaticFieldID:` `class` `=` `java.lang.Class<android.content.BroadcastReceiver>, field` `=` `b, sig` `=` `Ljava``/``lang``/``String;``jni` `=``=``=``> FindFieldID: name: b sig: Ljava``/``lang``/``String;``Calling` `object` `public method: void java.lang.NoSuchFieldError.<init>(java.lang.String), args_size:` `8``, method address:` `0x70a66400``this:` `0x13a2f368``arg1: no` `"Ljava/lang/String;"` `field` `"b"` `in` `class` `"Landroid/content/BroadcastReceiver;"` `or` `its superclasses,` `0x13a2f388``return``: void``jni` `=``=``=``> ExceptionClear``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<xxx.broadcast.DocumentPurchaseReceiver>, address:` `0x16de4fb0``jni` `=``=``=``> GetStaticObjectField: field` `=` `java.lang.Class<xxx.broadcast.DocumentPurchaseReceiver>``-``>java.lang.String xxx.broadcast.DocumentPurchaseReceiver.b, obj address:` `0x13a2f2c0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x70ee4280``jni` `=``=``=``> PushLocalFrame: capacity` `=` `1``jni` `=``=``=``> NewObjectA:` `class` `=` `java.lang.Class<android.content.IntentFilter>, method` `=` `void android.content.IntentFilter.<init>(java.lang.String), address:` `0x13a2f560``Calling` `object` `public method: void android.content.IntentFilter.<init>(java.lang.String), args_size:` `8``, method address:` `0x7128c5f8``this:` `0x13a2f560``arg1: xxx.document.purchase.action,` `0x13a2f2c0``return``: void``jni` `=``=``=``> PopLocalFrame: survivor_class` `=` `android.content.IntentFilter``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c66f50``jni` `=``=``=``> GetObjectField: field` `=` `java.lang.Class<xxx.DocinHomeActivity>``-``>androidx.localbroadcastmanager.content.LocalBroadcastManager xxx.DocinHomeActivity.mLocalBroadcastManager, obj address:` `0x12f56bc0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c66f50``jni` `=``=``=``> GetObjectField: field` `=` `java.lang.Class<xxx.DocinHomeActivity>``-``>xxx.broadcast.DocumentPurchaseReceiver xxx.DocinHomeActivity.mDocumentPurchaseReceiver, obj address:` `0x12f56bc0``jni` `=``=``=``> GetObjectClass: java.lang.Class<androidx.localbroadcastmanager.content.LocalBroadcastManager>, address:` `0x16d26aa8``jni` `=``=``=``> FindClass: androidx``/``localbroadcastmanager``/``content``/``LocalBroadcastManager``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<androidx.localbroadcastmanager.content.LocalBroadcastManager>, address:` `0x16c5e050``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<androidx.localbroadcastmanager.content.LocalBroadcastManager>, method` `=` `registerReceiver, sig` `=` `(Landroid``/``content``/``BroadcastReceiver;Landroid``/``content``/``IntentFilter;)V``jni` `=``=``=``> FindMethodID: name: registerReceiver sig: (Landroid``/``content``/``BroadcastReceiver;Landroid``/``content``/``IntentFilter;)V is_static: false``Calling` `object` `public method: void androidx.localbroadcastmanager.content.LocalBroadcastManager.registerReceiver(android.content.BroadcastReceiver, android.content.IntentFilter), args_size:` `12``, method address:` `0x70c783ef08``this:` `0x16d26aa8``arg1:` `0x13a2f350` `(xxx.broadcast.DocumentPurchaseReceiver)``arg2:` `0x13a2f560` `(android.content.IntentFilter)``return``: void``jni` `=``=``=``> FindClass: com``/``hwangjr``/``rxbus``/``RxBus``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<com.hwangjr.rxbus.RxBus>, address:` `0x138cb358``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<com.hwangjr.rxbus.RxBus>, method` `=` `get, sig` `=` `()Lcom``/``hwangjr``/``rxbus``/``Bus;``jni` `=``=``=``> FindMethodID: name: get sig: ()Lcom``/``hwangjr``/``rxbus``/``Bus; is_static: true``Calling native static public method: com.hwangjr.rxbus.Bus com.hwangjr.rxbus.RxBus.get(), args_size:` `0``, method address:` `0x702bfab0d0``return``:` `0x13a304e8``jni` `=``=``=``> GetObjectClass: java.lang.Class<com.hwangjr.rxbus.Bus>, address:` `0x13a304e8``jni` `=``=``=``> FindClass: com``/``hwangjr``/``rxbus``/``Bus``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<com.hwangjr.rxbus.Bus>, address:` `0x138cb618``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<com.hwangjr.rxbus.Bus>, method` `=` `register, sig` `=` `(Ljava``/``lang``/``Object``;)V``jni` `=``=``=``> FindMethodID: name: register sig: (Ljava``/``lang``/``Object``;)V is_static: false``Calling` `object` `public method: void com.hwangjr.rxbus.Bus.register(java.lang.``Object``), args_size:` `8``, method address:` `0x702bfab388``this:` `0x13a304e8``arg1:` `0x12f56bc0` `(xxx.DocinHomeActivity)``return``: void``jni` `=``=``=``> FindClass: com``/``umeng``/``message``/``PushAgent``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<com.umeng.message.PushAgent>, address:` `0x16c6c2f0``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<com.umeng.message.PushAgent>, method` `=` `getInstance, sig` `=` `(Landroid``/``content``/``Context;)Lcom``/``umeng``/``message``/``PushAgent;``jni` `=``=``=``> FindMethodID: name: getInstance sig: (Landroid``/``content``/``Context;)Lcom``/``umeng``/``message``/``PushAgent; is_static: true``Calling native static public method: com.umeng.message.PushAgent com.umeng.message.PushAgent.getInstance(android.content.Context), args_size:` `4``, method address:` `0x702e721d10``arg0:` `0x12f56bc0` `(xxx.DocinHomeActivity)``return``:` `0x16d1d180``jni` `=``=``=``> GetObjectClass: java.lang.Class<com.umeng.message.PushAgent>, address:` `0x16d1d180``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c6c2f0``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<com.umeng.message.PushAgent>, method` `=` `onAppStart, sig` `=` `()V``jni` `=``=``=``> FindMethodID: name: onAppStart sig: ()V is_static: false``Calling` `object` `public method: void com.umeng.message.PushAgent.onAppStart(), args_size:` `4``, method address:` `0x702e722260``this:` `0x16d1d180``return``: void``jni` `=``=``=``> FindClass: u2``/``g``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<u2.g>, address:` `0x13b40ac8``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<u2.g>, method` `=` `a, sig` `=` `()V``jni` `=``=``=``> FindMethodID: name: a sig: ()V is_static: true``Calling native static public method: void u2.g.a(), args_size:` `0``, method address:` `0x702bedc228``return``: void``jni` `=``=``=``> NewStringUTF: BackStatisticsManager, address:` `0x13b54b88``Calling` `object` `public method: java.lang.String java.lang.String.``intern``(), args_size:` `4``, method address:` `0x70acc578``this:` `0x13b54b88``return``:` `0x12f53740``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.String, address:` `0x12f53740``jni` `=``=``=``> NewStringUTF: APP启动进行数据统计, address:` `0x13b54bb0``Calling` `object` `public method: java.lang.String java.lang.String.``intern``(), args_size:` `4``, method address:` `0x70acc578``this:` `0x13b54bb0``return``:` `0x13b54bb0``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.String, address:` `0x13b54bb0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16c64c30``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<t4.j>, method` `=` `e, sig` `=` `(Ljava``/``lang``/``String;Ljava``/``lang``/``String;)V``jni` `=``=``=``> FindMethodID: name: e sig: (Ljava``/``lang``/``String;Ljava``/``lang``/``String;)V is_static: true``Calling native static public method: void t4.j.e(java.lang.String, java.lang.String), args_size:` `8``, method address:` `0x702e7295d8``arg0: BackStatisticsManager,` `0x12f53740``arg1: APP启动进行数据统计,` `0x13b54bb0``return``: void``jni` `=``=``=``> FindClass: y4``/``c``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<y4.c>, address:` `0x16d8dcf0``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<y4.c>, method` `=` `k, sig` `=` `()Ly4``/``c;``jni` `=``=``=``> FindMethodID: name: k sig: ()Ly4``/``c; is_static: true``Calling native static public method: y4.c y4.c.k(), args_size:` `0``, method address:` `0x702e5bb120``return``:` `0x13b55d30``jni` `=``=``=``> FindClass: com``/``docin``/``home``/``DocinHomeActivity$a``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<xxx.DocinHomeActivity$a>, address:` `0x13a2f1a0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x13a2f1a0``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity$a>, method` `=` `<init>, sig` `=` `(Lcom``/``docin``/``home``/``DocinHomeActivity;)V``jni` `=``=``=``> FindMethodID: name: <init> sig: (Lcom``/``docin``/``home``/``DocinHomeActivity;)V is_static: false``jni` `=``=``=``> PushLocalFrame: capacity` `=` `1``jni` `=``=``=``> NewObjectA:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity$a>, method` `=` `void xxx.DocinHomeActivity$a.<init>(xxx.DocinHomeActivity), address:` `0x13b55dc0``Calling` `object` `public method: void xxx.DocinHomeActivity$a.<init>(xxx.DocinHomeActivity), args_size:` `8``, method address:` `0x702bed4cd0``this:` `0x13b55dc0``arg1:` `0x12f56bc0` `(xxx.DocinHomeActivity)``return``: void``jni` `=``=``=``> PopLocalFrame: survivor_class` `=` `xxx.DocinHomeActivity$a``jni` `=``=``=``> GetObjectClass: java.lang.Class<y4.c>, address:` `0x13b55d30``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x16d8dcf0``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<y4.c>, method` `=` `j, sig` `=` `(Ljava``/``lang``/``Runnable;)V``jni` `=``=``=``> FindMethodID: name: j sig: (Ljava``/``lang``/``Runnable;)V is_static: false``Calling` `object` `public method: void y4.c.j(java.lang.Runnable), args_size:` `8``, method address:` `0x702e5bb170``this:` `0x13b55d30``arg1:` `0x13b55dc0` `(xxx.DocinHomeActivity$a)``return``: void``jni` `=``=``=``> FindClass: com``/``docin``/``home``/``DocinHomeActivity$b``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<xxx.DocinHomeActivity$b>, address:` `0x13b56030``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x13b56030``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity$b>, method` `=` `<init>, sig` `=` `(Lcom``/``docin``/``home``/``DocinHomeActivity;)V``jni` `=``=``=``> FindMethodID: name: <init> sig: (Lcom``/``docin``/``home``/``DocinHomeActivity;)V is_static: false``jni` `=``=``=``> PushLocalFrame: capacity` `=` `1``jni` `=``=``=``> NewObjectA:` `class` `=` `java.lang.Class<xxx.DocinHomeActivity$b>, method` `=` `void xxx.DocinHomeActivity$b.<init>(xxx.DocinHomeActivity), address:` `0x13b562d8``Calling` `object` `public method: void xxx.DocinHomeActivity$b.<init>(xxx.DocinHomeActivity), args_size:` `8``, method address:` `0x702bf47f78``this:` `0x13b562d8``arg1:` `0x12f56bc0` `(xxx.DocinHomeActivity)``return``: void``jni` `=``=``=``> PopLocalFrame: survivor_class` `=` `xxx.DocinHomeActivity$b``jni` `=``=``=``> FindClass: a5``/``e``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<a5.e>, address:` `0x13b563c8``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<a5.e>, method` `=` `e, sig` `=` `(Ljava``/``lang``/``Runnable;)V``jni` `=``=``=``> FindMethodID: name: e sig: (Ljava``/``lang``/``Runnable;)V is_static: true``Calling native static public method: void a5.e.e(java.lang.Runnable), args_size:` `4``, method address:` `0x702bf48248``arg0:` `0x13b562d8` `(xxx.DocinHomeActivity$b)``return``: void``jni` `=``=``=``> FindClass: x0``/``a``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<x0.a>, address:` `0x13b5fb68``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<x0.a>, method` `=` `e, sig` `=` `()Lx0``/``a;``jni` `=``=``=``> FindMethodID: name: e sig: ()Lx0``/``a; is_static: true``Calling native static public method: x0.a x0.a.e(), args_size:` `0``, method address:` `0x702bf49fd0``return``:` `0x13b60360``jni` `=``=``=``> GetObjectClass: java.lang.Class<x0.a>, address:` `0x13b60360``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x13b5fb68``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<x0.a>, method` `=` `c, sig` `=` `()V``jni` `=``=``=``> FindMethodID: name: c sig: ()V is_static: false``Calling` `object` `public method: void x0.a.c(), args_size:` `4``, method address:` `0x702bf4a048``this:` `0x13b60360``return``: void``jni` `=``=``=``> FindClass: w0``/``b``jni` `=``=``=``> NewGlobalRef: obj_class` `=` `java.lang.Class<w0.b>, address:` `0x13b670c0``jni` `=``=``=``> GetStaticMethodID:` `class` `=` `java.lang.Class<w0.b>, method` `=` `d, sig` `=` `()Lw0``/``b;``jni` `=``=``=``> FindMethodID: name: d sig: ()Lw0``/``b; is_static: true``Calling native static public method: w0.b w0.b.d(), args_size:` `0``, method address:` `0x702bf4e610``return``:` `0x13b677d0``jni` `=``=``=``> GetObjectClass: java.lang.Class<w0.b>, address:` `0x13b677d0``jni` `=``=``=``> NewLocalRef:` `class` `=` `java.lang.Class<java.lang.Class>, obj address:` `0x13b670c0``jni` `=``=``=``> GetMethodID:` `class` `=` `java.lang.Class<w0.b>, method` `=` `f, sig` `=` `()V``jni` `=``=``=``> FindMethodID: name: f sig: ()V is_static: false``Calling` `object` `public method: void w0.b.f(), args_size:` `4``, method address:` `0x702bf4e688``this:` `0x13b677d0``return``: void``jni` `=``=``=``> PopLocalFrame: survivor_class` `=` `null``end invoke.` |
|-|-|

拿着这份调用日志直接扔到ai（smali基础好的其实也可以自己写，但我觉得ai快捷一些）：
 ![image](https://bbs.kanxue.com/upload/attach/202407/877942_U2FDBPS3PMH8SKX.webp)
最终效果（最后一行我自己加的重打包flag）：
 ![image](https://bbs.kanxue.com/upload/attach/202407/877942_V7ZTTDARR9HJASS.webp)
用同样方法，把app的所有壳的native方法还原，并且去掉壳的静态代码块、把application入口改为目标app,以及修改壳获取context的方法后最后重打包成功，最终效果如图。app所有功能都能正常使用，说明代码逻辑还是没问题的：
 ![image](https://bbs.kanxue.com/upload/attach/202407/877942_XRKWTN68VHC76BV.webp)

补充下，对于下图这种加固，也是可以用此方法还原的（演示就只还原了一个getUrl）：
 ![image](https://bbs.kanxue.com/upload/attach/202407/877942_FAK4BGB7MDESRPU.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202407/877942_YUM22FUHPZW82ZH.webp)

# 总结

这种方法还原vmp比较粗暴但是也还是可以用，特别是对于中小型的app，业务逻辑简单，没有很多判断条件的，企图依靠一个壳保天下的这种，基本都是一把梭，一小时内可以把整个app从壳中脱离。缺点就是不够精准，像一些异常啊那些就没法处理，还有如果是Java层的算法那些应该也不好还原（但现在谁还会把app的算法写在java层）。优点自然不用说了，现在加壳厂商有些已经把vmp升级到双重甚至三重，手工逆的话难度极大，并且时间成本极高。现在不需要你会ida，不需要你写一行frida代码，即可把整个app的vmp保护去掉，简直就是降维打击，逆向小白也可轻松还原vmp。
另外源码就不打算公开了，想要这个镜像的话也可联系Q328366802（备注看雪），有偿代刷，仅供个人学习使用，请勿做违法事情。
PS：图中所有案例app都仅是测试学习，无任何复制以及传播、或其他恶意行为，如觉得侵权了请联系删除。

---

# 回复

## 回复 by xxhaishixx (#2)

*2024-7-9 02:38*

你说有没有一种可能，以后加壳这些如果用AI训练了，直接甩进去，AI自动给你脱壳了。

## 回复 by sunsjw (#3)

*2024-7-9 08:58*

>
> [xxhaishixx](https://bbs.kanxue.com/user-68284.htm)
>
>  你说有没有一种可能，以后加壳这些如果用AI训练了，直接甩进去，AI自动给你脱壳了。
>
>

以后都不用脱壳了，把功能描述一下，AI给你自动生成一个APP

## 回复 by 逆天而行 (#4)

*2024-7-9 10:35*

牛

## 回复 by hacker521 (#5)

*2024-7-9 11:08*

part脱壳机不开源吗![image](https://bbs.kanxue.com/view/img/face/48.gif)

## 回复 by wx_Yu.LQ (#6)

*2024-7-9 11:53*

![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by hhhaiai (#7)

*2024-7-9 13:14*

666

## 回复 by 文西哥 (#8)

*2024-7-9 14:16*

期待楼主分享成品

## 回复 by 苦瓜tim (#9)

*2024-7-9 14:49*

这是传说中的引流贴吗

## 回复 by 万里星河 (#10)

*2024-7-9 16:22*

我在想 用frida的jni_trace是否也可能达到类似效果

## 回复 by 程序员小潘 (#11)

*2024-7-9 16:37*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  我在想 用frida的jni_trace是否也可能达到类似效果
>
>

那得先把壳的frida检测过了再说

## 回复 by 哆啦噩梦 (#12)

*2024-7-9 16:51*

666 引流贴

## 回复 by 程序员小潘 (#13)

*2024-7-9 16:57*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  哆啦噩梦](https://bbs.kanxue.com/user-801972.htm)
>
>  666 引流贴
>
>

没什么引流不引流的，只是告诉大家有这种方法，可以这么做。至于你想直接要别人的成品，那付费也是理所当然的了

## 回复 by 万里星河 (#14)

*2024-7-10 14:28*

>
> [程序员小潘](https://bbs.kanxue.com/user-877942.htm)
>
>  那得先把壳的frida检测过了再说
>
>

确实

## 回复 by 月清晖 (#15)

*2024-7-19 03:21*

已经这么野了吗？楼主好强！

## 回复 by ldehua (#16)

*2024-7-19 15:58*

传说中的引流贴吗

## 回复 by mb_elqwyvnm (#17)

*2024-7-19 16:32*

看看就行

## 回复 by mb_uskgmuue (#18)

*2024-9-6 17:35*

ai这么叼吗？

## 回复 by hacker521 (#19)

*2024-9-7 19:55*

有大佬尝试了楼主的脱壳机吗？

## 回复 by 日暮归途 (#20)

*2024-9-7 23:57*

需要啥手机啊

## 回复 by 程序员小潘 (#21)

*2024-9-8 01:27*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  日暮归途](https://bbs.kanxue.com/user-1000607.htm)
>
>  需要啥手机啊
>
>

pixel4/4XL

## 回复 by xxhaishixx (#22)

*2024-9-17 13:26*

>
> [sunsjw](https://bbs.kanxue.com/user-26484.htm)
>
>  以后都不用脱壳了，把功能描述一下，AI给你自动生成一个APP
>
>

那确实牛啊，如果还能自动迭代，那不是更牛。

## 回复 by hacker521 (#23)

*2024-9-18 18:42*

>
> [程序员小潘](https://bbs.kanxue.com/user-877942.htm)
>
>  pixel4/4XL
>
>

代刷啥价啊？

## 回复 by Fre1heit (#24)

*2025-9-29 16:30*

博主，能搞cc出行吗？几维安全
