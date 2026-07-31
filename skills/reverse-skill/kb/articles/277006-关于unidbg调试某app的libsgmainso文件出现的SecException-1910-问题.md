---
title: 关于unidbg调试某app的libsgmainso文件出现的SecException(1910)问题
url: https://bbs.kanxue.com/thread-277006.htm
tid: 277006
author: shmilyaxy
date: '2023-04-26'
tags: [Android安全, 逆向分析, 协议分析, 混淆加固, 其他]
crawled_at: '2026-07-31T14:49:40+08:00'
replies: 26
---

# 分析过程：

【文章使用unidbg以及代码下载】
<https://pan.baidu.com/s/1UCodd31iBgqCUztKKdZZpg>
提取码：5ifo
1.网上看了某帖子关于对sgmain的doCommandNative函数调用的复现，进一步了解了关于sgmain系列的安全措施，于是萌生了复现的想法，帖子链接：<https://f5.pm/go-129256.html>
2.由于之前对某航app进行过研究，并且发现其对wToken参数加密时也使用了sgmain系列进行保护，所以想要针对次app进行unidbg复现sagmain.so的调用
3.关于在复现前，网查了很多关于sagmain的帖子，其中有汇编的大致分析逻辑和unidbg复现的相关逻辑，感谢前辈大佬的帖子
<https://bbs.kanxue.com/thread-267741.htm#msg_header_h2_7>
<https://cloud.tencent.com/developer/article/1923148>
<https://blog.csdn.net/John_Lenon/article/details/129572217>
<https://blog.csdn.net/qq_32955223/article/details/120500351>
<https://bbs.kanxue.com/thread-265017.htm>
4.关于doCommandNative调用前，还需要进行初始化的操作，可以从启动app开始对次函数调用进行hook，打印参数的内容和返回值，然后unidbg模拟一步步的执行

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250 | `AOSP on blueline::com.rytong.ceair ]``-``> libDexHelper.so detect:` `0x9ec5c``libDexHelper.so detect:` `0xaa97c``libDexHelper.so detect:` `0x9d73c``libDexHelper.so detect:` `0xe3fd0``0x6fbe7e40ac``【``2023``-``θ``4``-``19` `22``:``25``:``00``:``983``】 目标app正在加载so文件：``/``data``/``app``/``com.rytong.ceair``-``2joxiTDNb8xd68``-``9jbFtkA``=``=``/``lib``/``arm64``/``libdexjni.so``【``2023``-``θ``4``-``19` `22``:``25``:``02``:``925``】 目标app正在加载so文件：``/``vendor``/``lib64``/``hw``/``gralloc.sdm845.so``【``2023``-``θ``4``-``19` `22``:``25``:``02``:``938``】 目标app正在加载so文件：``/``vendor``/``lib64``/``hw``/``android.hardware.graphics.mapper@``2.0``-``impl``-``qti``-``display.so``【``2023``-``θ``4``-``19` `22``:``25``:``35``:``687``】 目标app正在加载so文件：``/``data``/``app``/``com.rytong.ceair``-``2joxiTDNb8xd68``-``9jbFtkA``=``=``/``lib``/``arm64``/``libsgmainso``-``5.4``.``193.so``【``2023``-``θ``4``-``19` `22``:``25``:``35``:``687``】 目标so已经加载,正在寻找目标类....``my_log``-``>com.taobao.wireless.security.adapter.JNICLibrary,doCommandNative,,,,true,true``doCommandNative   hooking....``【``2023``-``θ``4``-``19` `22``:``25``:``35``:``699``】 已找到目标类：com.taobao.wireless.security.adapter.JNICLibrary，正在切换classLoader....``-``-``-``-``-``-``-``-``-``-``-``-``-``-``【``2023``-``θ``4``-``19` `22``:``25``:``35``:``715``】``-``-``-``-``-``-``-``-``-``-``-``-``-``com.taobao.wireless.security.adapter.JNICLibrary.doCommandNative` `is` `called``参数长度：``2``参数``0``：【类型：number】``10101``参数``1``：【类型：``object``】``com.rytong.ceair.CeairApp@``407804a``,``3``,,``/``data``/``user``/``0``/``com.rytong.ceair``/``app_SGLib,``返回结果：【类型：``object``】 【类名：``class` `java.lang.Integer】``0``调用栈：``java.lang.Throwable``at com.taobao.wireless.security.adapter.JNICLibrary.doCommandNative(Native Method)``at com.alibaba.wireless.security.mainplugin.a.doCommand(Unknown Source:``0``)``at com.alibaba.wireless.security.mainplugin.SecurityGuardMainPlugin.onPluginLoaded(Unknown Source:``147``)``at com.alibaba.wireless.security.framework.d.a(Unknown Source:``1134``)``at com.alibaba.wireless.security.framework.d.d(Unknown Source:``67``)``at com.alibaba.wireless.security.framework.d.getPluginInfo(Unknown Source:``3``)``at com.alibaba.wireless.security.``open``.initialize.b.a(Unknown Source:``38``)``at com.alibaba.wireless.security.``open``.initialize.a.loadLibrarySync(Unknown Source:``5``)``at com.alibaba.wireless.security.``open``.initialize.a.initialize(Unknown Source:``0``)``at com.alibaba.wireless.security.``open``.SecurityGuardManager.getInstance(Unknown Source:``20``)``at com.alibaba.wireless.security.``open``.SecurityGuardManager.getInstance(Unknown Source:``1``)``at aej.a(AliPreWorm.java:``54``)``at com.rytong.ceair.CeairApp.agreeConcealPrivacyToInit(CeairApp.java:``86``)``at com.rytong.ceair.main.SplashActivity$l.onClick(SplashActivity.kt:``477``)``at zm.onClick(ClickProxy.java:``55``)``at android.view.View.performClick(View.java:``7259``)``at android.view.View.performClickInternal(View.java:``7236``)``at android.view.View.access$``3600``(View.java:``801``)``at android.view.View$PerformClick.run(View.java:``27892``)``at android.os.Handler.handleCallback(Handler.java:``883``)``at android.os.Handler.dispatchMessage(Handler.java:``100``)``at android.os.Looper.loop(Looper.java:``214``)``at android.app.ActivityThread.main(ActivityThread.java:``7699``)``at java.lang.reflect.Method.invoke(Native Method)``at com.android.internal.os.RuntimeInit$MethodAndArgsCaller.run(RuntimeInit.java:``492``)``at com.android.internal.os.ZygoteInit.main(ZygoteInit.java:``930``)`  `-``-``-``-``-``-``-``-``-``-``-``-``-``-``【``2023``-``θ``4``-``19` `22``:``25``:``36``:``173``】``-``-``-``-``-``-``-``-``-``-``-``-``-``com.taobao.wireless.security.adapter.JNICLibrary.doCommandNative` `is` `called``参数长度：``2``参数``0``：【类型：number】``10102``参数``1``：【类型：``object``】``main,``5.4``.``193``,``/``data``/``app``/``com.rytong.ceair``-``2joxiTDNb8xd68``-``9jbFtkA``=``=``/``lib``/``arm64``/``libsgmainso``-``5.4``.``193.so``返回结果：【类型：``object``】 【类名：``class` `java.lang.Integer】``0``调用栈：``java.lang.Throwable``at com.taobao.wireless.security.adapter.JNICLibrary.doCommandNative(Native Method)``at com.alibaba.wireless.security.mainplugin.a.doCommand(Unknown Source:``0``)``at com.alibaba.wireless.security.framework.d.a(Unknown Source:``1207``)``at com.alibaba.wireless.security.framework.d.d(Unknown Source:``67``)``at com.alibaba.wireless.security.framework.d.getPluginInfo(Unknown Source:``3``)``at com.alibaba.wireless.security.``open``.initialize.b.a(Unknown Source:``38``)``at com.alibaba.wireless.security.``open``.initialize.a.loadLibrarySync(Unknown Source:``5``)``at com.alibaba.wireless.security.``open``.initialize.a.initialize(Unknown Source:``0``)``at com.alibaba.wireless.security.``open``.SecurityGuardManager.getInstance(Unknown Source:``20``)``at com.alibaba.wireless.security.``open``.SecurityGuardManager.getInstance(Unknown Source:``1``)``at aej.a(AliPreWorm.java:``54``)``at com.rytong.ceair.CeairApp.agreeConcealPrivacyToInit(CeairApp.java:``86``)``at com.rytong.ceair.main.SplashActivity$l.onClick(SplashActivity.kt:``477``)``at zm.onClick(ClickProxy.java:``55``)``at android.view.View.performClick(View.java:``7259``)``at android.view.View.performClickInternal(View.java:``7236``)``at android.view.View.access$``3600``(View.java:``801``)``at android.view.View$PerformClick.run(View.java:``27892``)``at android.os.Handler.handleCallback(Handler.java:``883``)``at android.os.Handler.dispatchMessage(Handler.java:``100``)``at android.os.Looper.loop(Looper.java:``214``)``at android.app.ActivityThread.main(ActivityThread.java:``7699``)``at java.lang.reflect.Method.invoke(Native Method)``at com.android.internal.os.RuntimeInit$MethodAndArgsCaller.run(RuntimeInit.java:``492``)``at com.android.internal.os.ZygoteInit.main(ZygoteInit.java:``930``)`  `【``2023``-``θ``4``-``19` `22``:``25``:``36``:``236``】 目标app正在加载so文件：``/``data``/``app``/``com.rytong.ceair``-``2joxiTDNb8xd68``-``9jbFtkA``=``=``/``lib``/``arm64``/``libsgsecuritybodyso``-``5.4``.``112.so``-``-``-``-``-``-``-``-``-``-``-``-``-``-``【``2023``-``θ``4``-``19` `22``:``25``:``36``:``240``】``-``-``-``-``-``-``-``-``-``-``-``-``-``com.taobao.wireless.security.adapter.JNICLibrary.doCommandNative` `is` `called``参数长度：``2``参数``0``：【类型：number】``10102``参数``1``：【类型：``object``】``securitybody,``5.4``.``112``,``/``data``/``app``/``com.rytong.ceair``-``2joxiTDNb8xd68``-``9jbFtkA``=``=``/``lib``/``arm64``/``libsgsecuritybodyso``-``5.4``.``112.so``返回结果：【类型：``object``】 【类名：``class` `java.lang.Integer】``0``调用栈：``java.lang.Throwable``at com.taobao.wireless.security.adapter.JNICLibrary.doCommandNative(Native Method)``at com.alibaba.wireless.security.mainplugin.a.doCommand(Unknown Source:``0``)``at com.alibaba.wireless.security.framework.d.a(Unknown Source:``1207``)``at com.alibaba.wireless.security.framework.d.d(Unknown Source:``67``)``at com.alibaba.wireless.security.framework.d.a(Unknown Source:``301``)``at com.alibaba.wireless.security.framework.d.a(Unknown Source:``340``)``at com.alibaba.wireless.security.framework.d.d(Unknown Source:``67``)``at com.alibaba.wireless.security.framework.d.getPluginInfo(Unknown Source:``3``)``at com.alibaba.wireless.security.framework.d.getInterface(Unknown Source:``64``)``at com.alibaba.wireless.security.``open``.SecurityGuardManager.getInterface(Unknown Source:``2``)``at aej.a(AliPreWorm.java:``54``)``at com.rytong.ceair.CeairApp.agreeConcealPrivacyToInit(CeairApp.java:``86``)``at com.rytong.ceair.main.SplashActivity$l.onClick(SplashActivity.kt:``477``)``at zm.onClick(ClickProxy.java:``55``)``at android.view.View.performClick(View.java:``7259``)``at android.view.View.performClickInternal(View.java:``7236``)``at android.view.View.access$``3600``(View.java:``801``)``at android.view.View$PerformClick.run(View.java:``27892``)``at android.os.Handler.handleCallback(Handler.java:``883``)``at android.os.Handler.dispatchMessage(Handler.java:``100``)``at android.os.Looper.loop(Looper.java:``214``)``at android.app.ActivityThread.main(ActivityThread.java:``7699``)``at java.lang.reflect.Method.invoke(Native Method)``at com.android.internal.os.RuntimeInit$MethodAndArgsCaller.run(RuntimeInit.java:``492``)``at com.android.internal.os.ZygoteInit.main(ZygoteInit.java:``930``)`  `【``2023``-``θ``4``-``19` `22``:``25``:``36``:``268``】 目标app正在加载so文件：``/``data``/``user``/``0``/``com.rytong.ceair``/``app_SGLib``/``app_1681789435``/``main``/``libsgavmpso``-``5.4``.``1002.so``-``-``-``-``-``-``-``-``-``-``-``-``-``-``【``2023``-``θ``4``-``19` `22``:``25``:``36``:``270``】``-``-``-``-``-``-``-``-``-``-``-``-``-``com.taobao.wireless.security.adapter.JNICLibrary.doCommandNative` `is` `called``参数长度：``2``参数``0``：【类型：number】``10102``参数``1``：【类型：``object``】``avmp,``5.4``.``1002``,``/``data``/``user``/``0``/``com.rytong.ceair``/``app_SGLib``/``app_1681789435``/``main``/``libsgavmpso``-``5.4``.``1002.so``返回结果：【类型：``object``】 【类名：``class` `java.lang.Integer】``0``调用栈：``java.lang.Throwable``at com.taobao.wireless.security.adapter.JNICLibrary.doCommandNative(Native Method)``at com.alibaba.wireless.security.mainplugin.a.doCommand(Unknown Source:``0``)``at com.alibaba.wireless.security.framework.d.a(Unknown Source:``1207``)``at com.alibaba.wireless.security.framework.d.d(Unknown Source:``67``)``at com.alibaba.wireless.security.framework.d.getPluginInfo(Unknown Source:``3``)``at com.alibaba.wireless.security.framework.d.getInterface(Unknown Source:``64``)``at com.alibaba.wireless.security.``open``.SecurityGuardManager.getInterface(Unknown Source:``2``)``at aej.a(AliPreWorm.java:``54``)``at com.rytong.ceair.CeairApp.agreeConcealPrivacyToInit(CeairApp.java:``86``)``at com.rytong.ceair.main.SplashActivity$l.onClick(SplashActivity.kt:``477``)``at zm.onClick(ClickProxy.java:``55``)``at android.view.View.performClick(View.java:``7259``)``at android.view.View.performClickInternal(View.java:``7236``)``at android.view.View.access$``3600``(View.java:``801``)``at android.view.View$PerformClick.run(View.java:``27892``)``at android.os.Handler.handleCallback(Handler.java:``883``)``at android.os.Handler.dispatchMessage(Handler.java:``100``)``at android.os.Looper.loop(Looper.java:``214``)``at android.app.ActivityThread.main(ActivityThread.java:``7699``)``at java.lang.reflect.Method.invoke(Native Method)``at com.android.internal.os.RuntimeInit$MethodAndArgsCaller.run(RuntimeInit.java:``492``)``at com.android.internal.os.ZygoteInit.main(ZygoteInit.java:``930``)`  `-``-``-``-``-``-``-``-``-``-``-``-``-``-``【``2023``-``θ``4``-``19` `22``:``25``:``36``:``281``】``-``-``-``-``-``-``-``-``-``-``-``-``-``com.taobao.wireless.security.adapter.JNICLibrary.doCommandNative` `is` `called``参数长度：``2``参数``0``：【类型：number】``60901``参数``1``：【类型：``object``】``0335_mwua``,sgcipher``返回结果：【类型：``object``】 【类名：``class` `java.lang.``Long``】``475517112478``调用栈：``java.lang.Throwable``at com.taobao.wireless.security.adapter.JNICLibrary.doCommandNative(Native Method)``at com.alibaba.wireless.security.mainplugin.a.doCommand(Unknown Source:``0``)``at com.alibaba.wireless.security.avmpplugin.b.b.a(Unknown Source:``18``)``at com.alibaba.wireless.security.avmpplugin.b.a.createAVMPInstance(Unknown Source:``7``)``at com.alibaba.wireless.security.avmpplugin.a.a.initialize(Unknown Source:``14``)``at aej.a(AliPreWorm.java:``55``)``at com.rytong.ceair.CeairApp.agreeConcealPrivacyToInit(CeairApp.java:``86``)``at com.rytong.ceair.main.SplashActivity$l.onClick(SplashActivity.kt:``477``)``at zm.onClick(ClickProxy.java:``55``)``at android.view.View.performClick(View.java:``7259``)``at android.view.View.performClickInternal(View.java:``7236``)``at android.view.View.access$``3600``(View.java:``801``)``at android.view.View$PerformClick.run(View.java:``27892``)``at android.os.Handler.handleCallback(Handler.java:``883``)``at android.os.Handler.dispatchMessage(Handler.java:``100``)``at android.os.Looper.loop(Looper.java:``214``)``at android.app.ActivityThread.main(ActivityThread.java:``7699``)``at java.lang.reflect.Method.invoke(Native Method)``at com.android.internal.os.RuntimeInit$MethodAndArgsCaller.run(RuntimeInit.java:``492``)``at com.android.internal.os.ZygoteInit.main(ZygoteInit.java:``930``)`  `【``2023``-``θ``4``-``19` `22``:``25``:``36``:``449``】 目标app正在加载so文件：``/``data``/``app``/``com.rytong.ceair``-``2joxiTDNb8xd68``-``9jbFtkA``=``=``/``lib``/``arm64``/``libdeviceid_1.``0.so``【``2023``-``θ``4``-``19` `22``:``25``:``37``:``564``】 目标app正在加载so文件：``/``data``/``app``/``com.rytong.ceair``-``2joxiTDNb8xd68``-``9jbFtkA``=``=``/``lib``/``arm64``/``libencrypt.so``【``2023``-``θ``4``-``19` `22``:``25``:``37``:``619``】 目标app正在加载so文件：``/``data``/``app``/``com.rytong.ceair``-``2joxiTDNb8xd68``-``9jbFtkA``=``=``/``lib``/``arm64``/``libentryexpro.so``【``2023``-``θ``4``-``19` `22``:``25``:``40``:``819``】 目标app正在加载so文件：``/``data``/``dalvik``-``cache``/``arm64``/``product@app@webview@webview.apk@classes.dex``【``2023``-``θ``4``-``19` `22``:``25``:``40``:``839``】 目标app正在加载so文件：libwebviewchromium.so``【``2023``-``θ``4``-``19` `22``:``25``:``40``:``927``】 目标app正在加载so文件：``/``product``/``app``/``webview``/``webview.apk!``/``lib``/``arm64``-``v8a``/``libwebviewchromium.so``【``2023``-``θ``4``-``19` `22``:``25``:``40``:``934``】 目标app正在加载so文件：``/``system``/``lib64``/``libwebviewchromium_plat_support.so``【``2023``-``θ``4``-``19` `22``:``25``:``42``:``838``】 目标app正在加载so文件：``/``data``/``app``/``com.rytong.ceair``-``2joxiTDNb8xd68``-``9jbFtkA``=``=``/``lib``/``arm64``/``libwbsk_crypto_tool.so``-``-``-``-``-``-``-``-``-``-``-``-``-``-``【``2023``-``θ``4``-``19` `22``:``25``:``42``:``894``】``-``-``-``-``-``-``-``-``-``-``-``-``-``com.taobao.wireless.security.adapter.JNICLibrary.doCommandNative` `is` `called``参数长度：``2``参数``0``：【类型：number】``60902``参数``1``：【类型：``object``】``475517112478``,sign,``class` `[B,[Ljava.lang.``Object``;@``8058bb``返回结果：【类型：``object``】 【类名：``class` `[B】``"QllUUl9yUncwbkFVNFNpWTg5WnlnVldBcnZ2bmZuYXhVZnY4WHE4WDREcGhvNmNYSkdzM2dMMjZ5YUV6dndoRUorSjF5V1ZRVHNxZnBndk1PdVdQc1ZMdktGcHloZ256WXorNHAyWWJJWlhCbW5zNVdyMzg3cFM2VTJiakFPZTExZ1NzakNSRWplcEJ0NmVYU2w0eHNtWll2UFV0MmYxVTM5TEFyN01ZbzVoZDMzS0gzKzQ1aXd4aDY0TGdVaVVicUlBR3VNQnBKalQxc2lhMENTcTJEbGxHQlBPaXRTRjExTmNoRnpjcHlyOFE3Q2NZPSZBV0VSX2EwMDEzOTIzNzc5M2I1YWE5YjJiYWVkZWI4NWYwOWM1ZDAwYWYxZDU3ZTE4NQ=="``调用栈：``java.lang.Throwable``at com.taobao.wireless.security.adapter.JNICLibrary.doCommandNative(Native Method)``at com.alibaba.wireless.security.mainplugin.a.doCommand(Unknown Source:``0``)``at com.alibaba.wireless.security.avmpplugin.b.b.invokeAVMP(Unknown Source:``30``)``at com.alibaba.wireless.security.avmpplugin.a.a.avmpSign(Unknown Source:``63``)``at aej.a(AliPreWorm.java:``86``)``at acc.intercept(EncodeRequestInterceptor.kt:``92``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.java:``142``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.java:``117``)``at aco.intercept(TransactionIdInterceptor.kt:``59``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.java:``142``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.java:``117``)``at ack.intercept(IntervalRequestInterceptor.java:``34``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.java:``142``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.java:``117``)``at acd.intercept(HeaderInterceptor.kt:``77``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.java:``142``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.java:``117``)``at okhttp3.RealCall.getResponseWithInterceptorChain(RealCall.java:``229``)``at okhttp3.RealCall.execute(RealCall.java:``81``)``at retrofit2.OkHttpCall.execute(OkHttpCall.java:``190``)``at gya.a(CallObservable.java:``41``)``at hxb.f(Observable.java:``12284``)``at gxz.a(BodyObservable.java:``34``)``at hxb.f(Observable.java:``12284``)``at iqa$b.run(ObservableSubscribeOn.java:``96``)``at hxj$a.run(Scheduler.java:``578``)``at io.reactivex.internal.schedulers.ScheduledRunnable.run(ScheduledRunnable.java:``66``)``at io.reactivex.internal.schedulers.ScheduledRunnable.call(ScheduledRunnable.java:``57``)``at java.util.concurrent.FutureTask.run(FutureTask.java:``266``)``at java.util.concurrent.ScheduledThreadPoolExecutor$ScheduledFutureTask.run(ScheduledThreadPoolExecutor.java:``301``)``at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:``1167``)``at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:``641``)``at java.lang.Thread.run(Thread.java:``919``)` |
|-|-|

5.最终目的时调用参数60902参数的doCommandNative方法对请求内容进行加密获得wToken值，思路明确后准备unidbg进行如下的调用：（这里借用：https://f5.pm/go-129256.html 帖子大佬分析的执行流程图）
 ![图片描述](https://bbs.kanxue.com/upload/attach/202304/941979_P56JKBJC39NNNRB.png)
6.在unidbg复现过程中，在第一个10101的调用时候，返回值一直是null，而不是hook的0，经过多方测试，最终在unidbg低版本并且对32位so进行模拟执行时，会返回0（猜测：新版本unidbg应该是帮我们补了一些环境，而旧版本则没有，所以旧版本运行会提示补环境，照补即可，这里补充环境参考了以下两个链接的帖子：https://blog.csdn.net/John_Lenon/article/details/129572217 和 https://blog.csdn.net/qq_32955223/article/details/120500351）
7.unidbg代码如下：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308309310311312313314315316317318319320321322323324325326327328329330331332333334335336337338339340341342343344345346347348349350351352353 | `package com.taobao.wireless.security.adapter.JNICLibrary;` `import` `com.alibaba.fastjson.util.IOUtils;``import` `com.github.unidbg.AndroidEmulator;``import` `com.github.unidbg.Module;``import` `com.github.unidbg.Emulator;``import` `com.github.unidbg.``file``.FileResult;``import` `com.github.unidbg.``file``.IOResolver;``import` `com.github.unidbg.``file``.linux.AndroidFileIO;``import` `com.github.unidbg.linux.android.AndroidARMEmulator;``import` `com.github.unidbg.linux.android.AndroidResolver;``import` `com.github.unidbg.linux.android.dvm.``*``;``import` `com.github.unidbg.linux.android.dvm.array.ArrayObject;``import` `com.github.unidbg.linux.android.dvm.array.ByteArray;``import` `com.github.unidbg.linux.android.dvm.wrapper.DvmInteger;``import` `com.github.unidbg.linux.android.dvm.wrapper.DvmLong;``import` `com.github.unidbg.memory.Memory;` `import` `java.io.``File``;``import` `java.util.HashMap;``import` `java.util.``Set``;` `public` `class` `MyAli extends AbstractJni implements IOResolver<AndroidFileIO> {``private final AndroidEmulator emulator;``private final VM vm;``Module module;``DalvikModule dm;``static public` `long` `slot;``private final DvmClass MYJNICLibrary;``private final boolean logging;` `@Override``public FileResult<AndroidFileIO> resolve(Emulator<AndroidFileIO> emulator, String pathname,` `int` `oflags){``System.out.println(``"[files open]->"``+``pathname);` `switch (pathname){``case` `"/data/app/com.rytong.ceair.apk"``:``return` `FileResult.success(emulator.getFileSystem().createSimpleFileIO(``new` `File``(``"unidbg-android/src/test/java/com/taobao/wireless/security/adapter/JNICLibrary/rootfs"``, pathname), oflags, pathname));``}``return` `null;``}``public MyAli(boolean logging) {``this.logging` `=` `logging;``emulator``=``new AndroidARMEmulator(``"com.rytong.ceair"``);` `final Memory memory` `=` `emulator.getMemory();` `/``/` `模拟器的内存操作接口``emulator.getSyscallHandler().addIOResolver(this);``memory.setLibraryResolver(new AndroidResolver(``23``));` `/``/` `设置系统类库解析` `vm` `=` `emulator.createDalvikVM(new` `File``(``"unidbg-android/src/test/java/com/taobao/wireless/security/adapter/JNICLibrary/donghang9.3.0.apk"``));``vm.setVerbose(logging);` `/``/` `设置是否打印Jni调用细节``vm.setJni(this);``MYJNICLibrary` `=` `vm.resolveClass(``"com/taobao/wireless/security/adapter/JNICLibrary"``);``}` `void destroy() {``IOUtils.close(emulator);``if` `(logging) {``System.out.println(``"destroy"``);``}``}` `public static void main(String[] args) throws Exception {` `MyAli test` `=` `new MyAli(true);``test.Call_doCommandNative();` `test.destroy();``}` `void Call_doCommandNative(){` `dm` `=` `vm.loadLibrary(new` `File``(``"unidbg-android/src/test/java/com/taobao/wireless/security/adapter/JNICLibrary/libsgmainso-5.4.193.so"``), true);` `/``/` `加载libttEncrypt.so到unicorn虚拟内存，加载成功以后会默认调用init_array等函数``dm.callJNI_OnLoad(emulator);` `/``/` `手动执行JNI_OnLoad函数``module` `=` `dm.getModule();` `System.out.println(``"TAG Vison ------------------- [1] -------------------"``);``/``/``【``1``】``-``10101` `So初始化``ArrayObject initSo_arg``=``new ArrayObject(``vm.resolveClass(``"android/content/Context"``).newObject(null),``DvmInteger.valueOf(vm,``3``),``new StringObject(vm,""),``new StringObject(vm,``"/data/user/0/com.rytong.ceair/app_SGLib"``),``new StringObject(vm,"")``);``DvmObject<?> dvmObject_initSo` `=` `MYJNICLibrary.callStaticJniMethodObject(emulator,` `"doCommandNative(I[Ljava/lang/Object;)Ljava/lang/Object;"``,` `10101``,initSo_arg);``System.out.println(``"TAG Vison ----- 10101 initSo ----- [res]:"``+``dvmObject_initSo.getValue());` `System.out.println(``"TAG Vison ------------------- [2] -------------------"``);``/``/``【``2``】``-``10102` `libsgmainso插件初始化``ArrayObject initSosgmain_arg``=``new ArrayObject(``new StringObject(vm,``"main"``),``new StringObject(vm,``"5.4.193"``),``new StringObject(vm,``"/data/app/com.rytong.ceair-yoTJTWpoydDKBU49a55E_A==/lib/arm/libsgmainso-5.4.193.so"``)``);``DvmObject<?> dvmObject_initSosgmain` `=` `MYJNICLibrary.callStaticJniMethodObject(emulator,` `"doCommandNative(I[Ljava/lang/Object;)Ljava/lang/Object;"``,` `10102``,initSosgmain_arg);``System.out.println(``"TAG Vison ----- 10102 initSosgmain ----- [res]:"``+``dvmObject_initSosgmain.getValue());``System.out.println(``"TAG Vison ------------------- [2-3 load-so] -------------------"``);``DalvikModule dm1` `=` `vm.loadLibrary(new` `File``(``"unidbg-android/src/test/java/com/taobao/wireless/security/adapter/JNICLibrary/libsgsecuritybodyso-5.4.112.so"``), true);` `/``/` `加载libttEncrypt.so到unicorn虚拟内存，加载成功以后会默认调用init_array等函数``dm1.callJNI_OnLoad(emulator);` `System.out.println(``"TAG Vison ------------------- [3] -------------------"``);``/``/``【``3``】``-``10102` `libsgsecuritybodyso插件初始化``ArrayObject initSosgsecuritybody_arg``=``new ArrayObject(``new StringObject(vm,``"securitybody"``),``new StringObject(vm,``"5.4.112"``),``new StringObject(vm,``"/data/app/com.rytong.ceair-yoTJTWpoydDKBU49a55E_A==/lib/arm/libsgsecuritybodyso-5.4.112.so"``)``);``DvmObject<?> dvmObject_initSosgsecuritybody` `=` `MYJNICLibrary.callStaticJniMethodObject(emulator,` `"doCommandNative(I[Ljava/lang/Object;)Ljava/lang/Object;"``,` `10102``,initSosgsecuritybody_arg);``System.out.println(``"TAG Vison ----- 10102 initSosgsecuritybody ----- [res]:"``+``dvmObject_initSosgsecuritybody.getValue());``System.out.println(``"TAG Vison ------------------- [3-4 load-so] -------------------"``);``DalvikModule dm2` `=` `vm.loadLibrary(new` `File``(``"unidbg-android/src/test/java/com/taobao/wireless/security/adapter/JNICLibrary/libsgavmpso-5.4.1002.so"``), true);` `/``/` `加载libttEncrypt.so到unicorn虚拟内存，加载成功以后会默认调用init_array等函数``dm2.callJNI_OnLoad(emulator);` `System.out.println(``"TAG Vison ------------------- [4] -------------------"``);``/``/``【``4``】``-``10102` `libsgavmpso插件初始化``ArrayObject initSosgavmp_arg``=``new ArrayObject(``new StringObject(vm,``"avmp"``),``new StringObject(vm,``"5.4.1002"``),``new StringObject(vm,``"/data/user/0/com.rytong.ceair/app_SGLib/app_1682143210/main/libsgavmpso-5.4.1002.so"``)``);``DvmObject<?> dvmObject_initSosgavmp` `=` `MYJNICLibrary.callStaticJniMethodObject(emulator,` `"doCommandNative(I[Ljava/lang/Object;)Ljava/lang/Object;"``,` `10102``,initSosgavmp_arg);``System.out.println(``"TAG Vison ----- 10102 initSosgavmp ----- [res]:"``+``dvmObject_initSosgavmp.getValue());` `System.out.println(``"TAG Vison ------------------- [5] -------------------"``);``/``/``【``5``】``-``60901` `AVMP初始化``ArrayObject initVmp_arg``=``new ArrayObject(``new StringObject(vm,``"0335_mwua"``),``new StringObject(vm,``"sgcipher"``)``);``DvmObject<?> dvmObject_initVmp` `=` `MYJNICLibrary.callStaticJniMethodObject(emulator,` `"doCommandNative(I[Ljava/lang/Object;)Ljava/lang/Object;"``,` `60901``,initVmp_arg);``long` `createAVMPInstance` `=` `Long``.valueOf(dvmObject_initVmp.getValue().toString());``createAVMPInstance``=``createAVMPInstance&` `0xffffffffL``;``System.out.println(``"TAG Vison ----- 60901 initVmp ----- [res]:"``+``createAVMPInstance);`  `/``/``long` `createAVMPInstance``=``2242459650L``;``System.out.println(``"TAG Vison ------------------- [6] -------------------"``);``/``/``【``6``】``-``60902` `wToken加密调用` `String strbody` `=` `"{\"req\":\"S6TVWfiiBE2ZEXY9ldOr4oz9JB6+/EaSHqY1/vILbUs/6L2Eqv3e8m2QToNujniIPYeDZRK4Gr6fVX+hRS4f9aWHsJaevbhzM+qiHoS2nsFagR+T3pTsKJmkNRObOuYk0POOaSRogMRZ+1tkiG7RuzxfZ8fVZ47CKz6dGB1jsC2z4KGQDRp8iGkKlhzP65+DqgbazzCBhv3nFhKXFL/GtBnmJnoVktVmCGVp/tCMLmybMF+EniB7nejy3nlCoJ512ZOeuYNCWnYgz2KjnYr913ksgfGfewxGXJtLr8A3KjbGHAEAs/IOohWkoR8k+2X1+q4myAypJ+jh5cRj8ghYuz149+lGJan68aaZgeMOBYL1jdtAL71E8zPHCJ66Ap33flyIfK/D2SxzIaGvVjWttsMvCBTsd5xkqUiGgDOXCHb0MPez3c+fzBtg+LTsFbdNWBWdEKV+uVw/xJByHUncxmT/cT7cgQHt55qNvdULzpCYOFxh5tqQgFAs3lM27Y1Z6WYm5noXLO24gUoehhxCC2Rw/duiowt+yw2iHhi3UpLbjvGSudkDUyDIYb7ij7xpkIt6HD2O5avNJIBh2aYuRmcpcHPUQItbf/PoQwlB8BEy+tce6Pp7ZeOFUudo3yBOuWo2yP5KyKjL8nkstRDwKwjcplZPZfKwJQJvz+osen1oGdfyhseJEuBLGzHcc1g3pJbf9OqIoQ3iniQcne3IY7IB0Y5hWfMfgvCv5BbZjYD8Ofw5OkuvBOY7WKS0TuahsnucIVKtqhcy/C9NzAM9Zx1Ge2q+aK4zKjQJckgs6R4EXB4V+6ZlJx4rwFMXRs/WeJFE2TtIX83XND+KilCLvnI3BUfbDLAyvZk3e6EXaSDZtTxWGAr+sRrlk66dRZydCVe8Eu00bHTP7fV3MBcldb5RXoW3JAg0DyXJaPRUh7VL7w091OoUoW/9Kb0pbXjlent4Tvg/VKb5HBQ/BmV+HUcScDLm4ra7aPmYFR1v5SmXxRw1snKXgoM6Cu/pd1Z2epLsm2dqiaHO99B5bq853tKdtYDwXcXLh8Fr9MtyftqGy25cxVGK4sfzwvEAt9wzGX1xHKFROq4bJXEcFSDB2zifdx9QUjDIezIBiMNzg2nSYeAMsf/aymk8HnEAwPL7DjrvmzooFKI0IbVF+wT8mjsbAXmFyRLeuBQyKm9HSvNuoz7E9Z6xN8ZSnZyYpJ0KAovs59k9/HpHWMvXxK+7mjVDeUhk/LErE1d36LAxK0rAp10iwHqeXCPdwZr3+y/0/YKNgkXGV0IYrljD8X2ue13+cu3bMtDgaxACee0l57qzGr/bTcbW6RDzlwtZf/R8kNrvjTybLs+gwFl6wFHZbNxwJ3ED8k0Nxt/RO0ZBXdFtGJSQ+uppc5yh2OJJKXB3aYy7IsmCY8f02jI1qM/UfkGy3WGbToWtV0bEVV1SHIApX1+G10+9Lqc84JABPbwB26Zd+TljMcBCIzB2ltL/68kiId7EGlcUK3Y0C02XjVFGxqCz1+6Z/P+2IhpxzJCRfRWIXWImq76MfAIu3Xacmw9lLscd/pR9Saaj1/DMPSTU=\"}"``;` `ArrayObject aryobj1``=``new ArrayObject(``DvmInteger.valueOf(vm,``3``),``new ByteArray(vm,strbody.getBytes()),``DvmInteger.valueOf(vm,strbody.length()),``new StringObject(vm,""),``new ByteArray(vm,new byte[``4``]),``DvmInteger.valueOf(vm,``0``)``);``ArrayObject aryobj2``=``new ArrayObject(``DvmLong.valueOf(vm,createAVMPInstance),``new StringObject(vm,``"sign"``),``vm.resolveClass(``"[B"``),``aryobj1``);``DvmObject<?> dvmObject_entry` `=` `MYJNICLibrary.callStaticJniMethodObject(emulator,` `"doCommandNative(I[Ljava/lang/Object;)Ljava/lang/Object;"``,` `60902``,aryobj2);` `/``/` `执行Jni方法``System.out.println(``"TAG Vison ----- 60902 wToken ----- [res]:"``+``dvmObject_entry);``}` `@Override``public DvmObject<?> callObjectMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {``switch (signature){``case` `"android/content/Context->getPackageCodePath()Ljava/lang/String;"``:{``return` `new StringObject(vm,` `"/data/app/com.rytong.ceair.apk"``);``}``case` `"android/content/Context->getFilesDir()Ljava/io/File;"``:{``return` `vm.resolveClass(``"java/io/File"``).newObject(new` `File``(``"/data/data/com.rytong.ceair/files"``));``}``/``/` `固定写法``case` `"java/io/File->getAbsolutePath()Ljava/lang/String;"``: {``return` `new StringObject(vm, ((``File``) dvmObject.getValue()).getAbsolutePath());``}``case` `"[B->getClass()Ljava/lang/Class;"``:{``return` `vm.resolveClass(``"[B"``);``}``case` `"android/app/ActivityThread->getSystemContext()Landroid/app/ContextImpl;"``:{``return` `vm.resolveClass(``"android/app/ContextImpl"``).newObject(null);``}``case` `"android/app/ContextImpl->getPackageManager()Landroid/content/pm/PackageManager;"``:{` `return` `vm.resolveClass(``"android/content/pm/PackageManager"``).newObject(null);` `}``case` `"android/app/ContextImpl->getSystemService(Ljava/lang/String;)Ljava/lang/Object;"``:{``String str1``=` `(String) varArg.getObject(``0``).getValue();``System.out.println(``"[getSystemService str1]->"``+``str1);``return` `vm.resolveClass(``"android/net/wifi/WifiManager"``).newObject(null);``}``case` `"android/net/wifi/WifiManager->getConnectionInfo()Landroid/net/wifi/WifiInfo;"``:{` `return` `vm.resolveClass(``"android/net/wifi/WifiInfo"``).newObject(null);``}``case` `"android/net/wifi/WifiInfo->getMacAddress()Ljava/lang/String;"``:{` `return` `new StringObject(vm,``"02:00:00:00:00:00"``);``}``case` `"java/util/HashMap->keySet()Ljava/util/Set;"``:{``HashMap<?,?>` `map` `=` `(HashMap<?, ?>) dvmObject.getValue();``return` `vm.resolveClass(``"java/util/Set"``).newObject(``map``.keySet());``}``case` `"java/util/Set->toArray()[Ljava/lang/Object;"``:{``Set``<?>` `set``=` `(``Set``<?>) dvmObject.getValue();``Object``[] array``=``set``.toArray();``DvmObject<?>[] objects``=``new DvmObject[array.length];``for``(``int` `i``=``0``;i<array.length;i``+``+``){``if``(array[i] instanceof String){``objects[i]``=``new StringObject(vm, (String) array[i]);``}``else``{``/``/``throw new IllegalAccessException(``"array="``+``array[i]);``}``}``return` `new ArrayObject(objects);``}``case` `"java/util/HashMap->get(Ljava/lang/Object;)Ljava/lang/Object;"``:{``HashMap<?,?>` `map` `=` `(HashMap<?, ?>) dvmObject.getValue();``Object` `key` `=` `varArg.getObject(``0``).getValue();``Object` `obj` `=` `map``.get(key);``if``(obj instanceof String){``return` `new StringObject(vm, (String) obj);``}``else``{``/``/``throw new IllegalAccessException(``"array="``+``obj);``}` `}``}``return` `super``.callObjectMethod(vm, dvmObject, signature, varArg);``}` `@Override``public DvmObject<?> getObjectField(BaseVM vm, DvmObject<?> dvmObject, String signature) {``switch (signature){``case` `"android/content/pm/ApplicationInfo->nativeLibraryDir:Ljava/lang/String;"``: {``return` `new StringObject(vm,` `"/data/app/com.rytong.ceair-yoTJTWpoydDKBU49a55E_A==/lib/arm"``);``}``}``return` `super``.getObjectField(vm, dvmObject, signature);``}` `@Override``public void callStaticVoidMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {``switch (signature){``case` `"com/alibaba/wireless/security/open/edgecomputing/ECMiscInfo->registerAppLifeCyCleCallBack()V"``: {``return``;``}``}``super``.callStaticVoidMethod(vm, dvmClass, signature, varArg);``}` `@Override``public` `int` `callStaticIntMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {``switch (signature){``case` `"com/alibaba/wireless/security/framework/utils/UserTrackMethodJniBridge->utAvaiable()I"``: {``return` `1``;``}``}``return` `super``.callStaticIntMethod(vm, dvmClass, signature, varArg);``}` `@Override``public DvmObject<?> newObject(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {``switch (signature){``/``/` `固定写法``case` `"java/lang/Integer-><init>(I)V"``: {``int` `value` `=` `varArg.getInt(``0``);``return` `vm.resolveClass(``"java/lang/Integer"``).newObject(value);``}``case` `"java/lang/Long-><init>(J)V"``: {``int` `value` `=` `varArg.getInt(``0``);``return` `vm.resolveClass(``"java/lang/Long"``).newObject(value);``}` `case` `"com/alibaba/wireless/security/open/SecException-><init>(Ljava/lang/String;I)V"``: {``int` `value` `=` `varArg.getInt(``1``);``System.out.println(``"[TAG-SecException]->"``+``value);``return` `vm.resolveClass(``"com/alibaba/wireless/security/open/SecException"``).newObject(value);``}``}``return` `super``.newObject(vm, dvmClass, signature, varArg);``}` `@Override``public` `long` `getStaticLongField(BaseVM vm, DvmClass dvmClass, String signature) {``switch (signature) {``case` `"com/alibaba/wireless/security/framework/SGPluginExtras->slot:J"``: {``return` `slot;``}``}``return` `super``.getStaticLongField(vm, dvmClass, signature);``}` `@Override``public void setStaticLongField(BaseVM vm, DvmClass dvmClass, String signature,` `long` `value) {``switch (signature) {``case` `"com/alibaba/wireless/security/framework/SGPluginExtras->slot:J"``: {``slot` `=` `value;``return``;``}``}``super``.setStaticLongField(vm, dvmClass, signature, value);``}` `@Override``public` `int` `getStaticIntField(BaseVM vm, DvmClass dvmClass, String signature) {``switch (signature){``case``"android/os/Build$VERSION->SDK_INT:I"``:{``return` `23``;``}``}``return` `super``.getStaticIntField(vm, dvmClass, signature);``}` `@Override``public DvmObject<?> callStaticObjectMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {``switch (signature){``case``"android/app/ActivityThread->currentPackageName()Ljava/lang/String;"``:{``return` `new StringObject(vm,``"com.rytong.ceair"``);``}``case` `"android/app/ActivityThread->currentActivityThread()Landroid/app/ActivityThread;"``:{``return` `dvmClass.newObject(null);``}``case` `"android/os/SystemProperties->get(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;"``:{``String str1``=` `(String) varArg.getObject(``0``).getValue();``String res``=``"";``System.out.println(``"[SystemProperties str1]->"``+``str1);``System.out.println(``"[SystemProperties str2]->"``+``varArg.getObject(``1``).getValue());``if``(str1.indexOf(``"ro.serialno"``)!``=``-``1``){``res``=``"94CX1Z56A"``;``}``return` `new StringObject(vm,res);``}``}``return` `super``.callStaticObjectMethod(vm, dvmClass, signature, varArg);``}`  `@Override``public DvmObject<?> getStaticObjectField(BaseVM vm, DvmClass dvmClass, String signature) {``switch (signature){``case` `"android/os/Build->BRAND:Ljava/lang/String;"``:``return` `new StringObject(vm,``"Ljava/lang/String;"``);``case` `"android/os/Build->MODEL:Ljava/lang/String;"``:``return` `new StringObject(vm,``"Ljava/lang/String;"``);``case` `"android/os/Build$VERSION->RELEASE:Ljava/lang/String;"``:``return` `new StringObject(vm,``"Ljava/lang/String;"``);``case` `"android/os/Build->DEVICE:Ljava/lang/String;"``:``return` `new StringObject(vm,``"Ljava/lang/String;"``);``}``return` `super``.getStaticObjectField(vm,dvmClass,signature);``}` `}` |
|-|-|

8.以上代码虽然能够正确的执行一些逻辑，但是在最后的60902调用时，返回值出错了，并且提示SecException（1910），通过如下链接查找，https://help.aliyun.com/document_detail/160578.html 该错误的原来可能是：非法的avmpInstance实例
 ![图片描述](https://bbs.kanxue.com/upload/attach/202304/941979_NQ4SGGMKK9J3NKF.png)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202304/941979_W98HGHF5U99PR4R.png)
10.补充说明：使用unidbg 080版本进行复现

# 求助各路大佬一起探讨一下原因

【注】文章中如有任何侵权，请联系说明修改！！
【注】本文仅用于学习讨论，不做任何商务用途！！

---

# 回复

## 回复 by zxvv (#2)

*2023-4-26 14:29*

我跑的其他调用，一开始也会有这个secException，我就把它当常规补环境，自己构造一个SecException返回，最后可以正常出结果。。

## 回复 by bluegatar (#3)

*2023-4-26 18:21*

为什么不用096版本？还有你这个  log是怎么得到的？？？

AOSP on blueline::com.rytong.ceair ]-> libDexHelper.so detect:  0x9ec5c
libDexHelper.so detect:  0xaa97c
libDexHelper.so detect:  0x9d73c
libDexHelper.so detect:  0xe3fd0

## 回复 by shmilyaxy (#4)

*2023-4-26 21:09*

>
> [zxvv](https://bbs.kanxue.com/user-869099.htm)
>
>  我跑的其他调用，一开始也会有这个secException，我就把它当常规补环境，自己构造一个SecException返回，最后可以正常出结果。。
>
>

我这里补了com/alibaba/wireless/security/open/SecException-><init>(Ljava/lang/String;I)V这个环境，一开始在10101调用都会报错SecException - 0xc7 ，一直找不到原因，后面降低了unidbg版本，发现存在环境修补，补充后在最后调用出现了SecException 报错，这个是我一直无法解决的。不知道你补的是这个环境吗？还是其他的调用？方便告之我试一试吗？

## 回复 by shmilyaxy (#5)

*2023-4-26 21:11*

>
> [bluegatar](https://bbs.kanxue.com/user-352825.htm)
>
>  为什么不用096版本？还有你这个 log是怎么得到的？？？
>
> AOSP on blueline::com.rytong.ceair ]-> libDexHelper.so detect: ...
>
>

我用过最新的unidbg，但是直接报SecException - 0xc7错误，后面更换低版本才发现原来是有环境需要补，新版本的不知道是不是默认给修补了。
后面的是hook代码，我的研究的这个app有frida检测，所以我在判断检测frida线程，并且将其杀死。

## 回复 by 万里星河 (#6)

*2023-4-26 23:53*

mark

## 回复 by zxvv (#7)

*2023-4-27 11:10*

>
> [shmilyaxy](https://bbs.kanxue.com/user-941979.htm)
>
>  我这里补了com/alibaba/wireless/security/open/SecException->(Ljava/lang/String;I)V这个环境，一开始在10101调用都会报错S ...

就是这个，我unidbg是0.9.7版本，10101没报错，看了你图里面补的，初始化传了个int，我是直接null初始化

## 回复 by shmilyaxy (#8)

*2023-4-27 13:18*

>
> [zxvv](https://bbs.kanxue.com/user-869099.htm)
>
>
>
>
>
>
>
>  shmilyaxy
>
>  我这里补了com/alibaba/wireless/security/open/SecException-&gt;(L ...
>
>

我刚才试了下，“return vm.resolveClass("com/alibaba/wireless/security/open/SecException").newObject(null);”，最后得调用还是返回null，不过我用新版本试试看，能不能实现第一个10101得调用-返回0

## 回复 by wx_justght (#9)

*2023-10-8 17:40*

mark

## 回复 by mb_ddzpjlyg (#10)

*2023-12-6 11:24*

你好，请问可以付费交流吗？ q 2075335452

## 回复 by meetpet (#11)

*2023-12-19 18:53*

>
> [zxvv](https://bbs.kanxue.com/user-869099.htm)
>
>  我跑的其他调用，一开始也会有这个secException，我就把它当常规补环境，自己构造一个SecException返回，最后可以正常出结果。。
>
>

是长mini-wua么

## 回复 by 西瓜帅 (#12)

*2023-12-25 11:10*

解决了 吗 哥们返回的是 125 我干

## 回复 by 西瓜帅 (#13)

*2023-12-25 14:12*

各位想解决 这个com/alibaba/wireless/security/open/SecException 导致返回为 null的话建议用unidbg 0.9.5就行了

## 回复 by shmilyaxy (#14)

*2024-1-5 11:44*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  西瓜帅](https://bbs.kanxue.com/user-823551.htm)
>
>  各位想解决 这个com/alibaba/wireless/security/open/SecException 导致返回为 null的话建议用unidbg 0.9.5就行了
>
>

我好像也是换了unidbg版本之后就没提示这个SecException 错误了，有点玄学，我没搞懂真正问题点

## 回复 by 西瓜帅 (#16)

*2024-2-1 13:50*

>
> [shmilyaxy](https://bbs.kanxue.com/user-941979.htm)
>
>  我好像也是换了unidbg版本之后就没提示这个SecException 错误了，有点玄学，我没搞懂真正问题点
>
>

顶级玄学

## 回复 by 寻梦之璐 (#17)

*2024-2-1 14:46*

不吹不黑，我用ida调试都能碰到这个报错。。。。

## 回复 by 蜡笔晓辉 (#18)

*2024-2-13 19:04*

版本都太老了。

## 回复 by 秋狝 (#19)

*2024-2-13 21:09*

感谢分享

## 回复 by cobe (#20)

*2024-2-29 17:19*

调用没有报错，加密结果也出来了，但加密的和app加密出来的不一样，

## 回复 by shmilyaxy (#21)

*2024-3-1 22:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  cobe](https://bbs.kanxue.com/user-979190.htm)
>
>  调用没有报错，加密结果也出来了，但加密的和app加密出来的不一样，
>
>

能用不？加密用到很多信息，unidbg和真机是不一样的

## 回复 by mb_bjqspbxy (#22)

*2024-8-27 13:18*

>
> [shmilyaxy](https://bbs.kanxue.com/user-941979.htm)
>
>  我好像也是换了unidbg版本之后就没提示这个SecException 错误了，有点玄学，我没搞懂真正问题点
>
>

换了版本还是没跑通作者上面的例子

## 回复 by mb_pkmnczqg (#23)

*2024-8-30 19:23*

付费求个 ybs3788

## 回复 by mb_schfdowz (#24)

*2024-12-10 15:10*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  西瓜帅](https://bbs.kanxue.com/user-823551.htm)
>
>  解决了 吗 哥们返回的是 125 我干
>
>

大兄弟， 125的问题解决了吗？ 我现在也报错125

## 回复 by 安缘 (#25)

*2025-3-19 18:07*

能搞，这种报错肯定是环境没补对

## 回复 by seenlao (#26)

*2025-7-14 01:37*

.

## 回复 by seenlao (#27)

*2025-7-19 00:43*

>
> [shmilyaxy](https://bbs.kanxue.com/user-941979.htm)  I added the environment com/alibaba/wireless/security/open/SecException->(Ljava/lang/String;I)V. At the beginning, I will report an error S when I call it in 10101...

## 回复 by seenlao (#28)

*2025-7-31 02:07*

人们是如何在不导致Frida崩溃的情况下拦截“doCommandNative”调用的？
