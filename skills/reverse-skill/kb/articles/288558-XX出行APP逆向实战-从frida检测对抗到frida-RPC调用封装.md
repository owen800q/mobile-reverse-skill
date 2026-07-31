---
title: '[原创]XX出行APP逆向实战:从frida检测对抗到frida-RPC调用封装'
url: https://bbs.kanxue.com/thread-288558.htm
tid: 288558
author: Dr_Knox
date: '2025-09-20'
tags: [Android安全, 原创, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:04:06+08:00'
replies: 28
---

## XX出行APP逆向实战:从frida检测对抗到frida-RPC调用封装

### 前言

对这个APP的逆向在8月份左右就已经完成，只是笔者本人最近在找工作，这才想着顺带将以前做过的项目整理一下，在看雪发篇文章让简历好看些，也算是复习了。

该APP在我看来相当有代表性，不是因为难度有多高，而是搭载了一堆花里胡哨的防护。

在这篇文章中，**你能碰见frida检测、SSL pinning 证书验证、设备风控**，但每个防护环节又都跟过家家闹着玩似的非常不严谨，并且由于该APP没有套壳，因而哪怕对新手而言，分析起来也不会太吃力。

### 工作环境

- hook库:

	- frida 15.2.2
- 反汇编:

	- jadx-gui-1.5.2
	- IDA PRO 9.0
- 编辑器: vscode
- IDE: IntelliJ
- 目标app: 5bCP5ouJ5Ye66KGMIDIzMDI=

### 达成目标

- 再封装目标的验证码接口，随后自动化调用
	- 绕过目标反调试
	- 绕过目标SSL证书验证
	- 分析目标内部验证字段的算法实现

### 反调试

通过frida的spawn模式启动目标app，可以看见进程很快便自动退出。

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_6KGKCMHY88BDBTJ.webp)
这就没什么好说的，目标app必定对frida的特征做了检测。

按照惯例，首先我们得定位检测点；

考虑到检测功能大多数情况下都会在Native层实现，那么hook加载so文件相关的标准库函数就成了首选，该案例中我们选择使用dlopen以及android_dlopen_ext这两个较为常用的函数

| 1234567891011121314151617 | `function` `loadSohook(){``var` `android_dlopen_ext_Addr = Module.findExportByName(``null``,``"android_dlopen_ext"``)``Interceptor.attach(android_dlopen_ext_Addr,{onEnter:` `function``(args){``let PathPtr = args[0]``let soPath = ptr(PathPtr).readCString()``console.log(``"[info] Load from android_dlopen_ext-> "``+soPath)``}})` `var` `dlopenAddr = Module.findExportByName(``null``,``"dlopen"``)``Interceptor.attach(dlopenAddr,{onEnter:` `function``(args){``let PathPtr = args[0]``let soPath = ptr(PathPtr).readCString()``console.log(``"[info] Load from dlopen-> "``+soPath)``}})``}` `setImmediate(loadSohook)` |
|-|-|

随后spawn模式注入

| 1 | `frida -U -l hook-loadso.js -f com.xiaolachuxing.user --no-pause` |
|-|-|

如图所示，目标进程在libmsaoaidsec.so加载后便退出，可以推测检测点就在该so文件内

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_MVUXA5UZSDSMTPZ.webp)
现在我们有两种方案：

1. 逆向so文件，patch掉检测功能的代码
2. hook android_dlopen_ext，判断第一个参数的路径名是否包含libmsaoaidsec.so，如果是则将路径参数替换为空

#### 跳过so加载

第二种方案是否适用取决于目标，大部分情况下都会导致目标进程的崩溃，但尝试一下也无妨

| 12345678910 | `Interceptor.attach(Module.findExportByName(``null``,``"android_dlopen_ext"``), {``onEnter:` `function``(args) {``var` `soName = ptr(args[0]).readCString();``console.log(soName);``if``(soName.includes(``"libmsaoaidsec.so"``)) {``console.log(``"Blocking:"``, soName);``args[0] = ptr(0);``}``}``});` |
|-|-|

出乎意料的是目标app没有崩溃，也就是说frida检测就这么被绕过了

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_6MYUA2GV6KNH648.webp)
如果懒得折腾的话，现在就可以继续分析了。

#### 逆向目标so

但考虑到这招并非总是管用，我们还是按照常规逆向的思路去so文件里看下检测逻辑的实现。

目标APP没有壳保护，可以直接从apk里将libmsaoaidsec.so拖取出来，随后丢入IDA分析。

考虑到检测逻辑大多会需要创建一个线程来运行，我们直接交叉搜索pthread_create的引用，如图所示

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_NRUPBY4C42CD6VJ.webp)
一共有四个引用被定位到，理论上来说我们只需要对pthread_create的第三个参数，也就是即将被创建的检测实例进行patch即可；

但在我们这么做之前可以向上跟踪调用逻辑，看看调用时机

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_4QNWNP2RKGFYJ2S.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_XKEP8NEAKZ56EN2.webp)
通过向前追溯，我们可以发现检测线程的创建逻辑是在init_proc内进行的

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_39QTZRSHUZ8Y276.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_CTZ2M5YM3CGR6NP.webp)
调用链条：.init_proc->sub_1A8A0->sub_1A5B0(包含全部检测逻辑)

而这对我们会产生哪些影响呢？首先你不能再直接hook pthread_create，**因为init_proc内的逻辑是先于*JNI_OnLoad* 之前执行的，这需要我们的hook时机非常靠前。**

其次，我试过直接对pthread_create进行hook随后判断当前实例地址是否属于目标so，这样做的后果就是导致目标卡死，并且会发现根本就没进入我们的Hook逻辑。

通过多次调试，我怀疑是由于对pthread_create进行hook的时机不对导致了死锁

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_MDTNQHEESYHX25V.webp)
那么如何在init_proc中的检测逻辑加载之前进行Hook呢？我们可以寻找.init_proc内调用的标准库函数，随后以标准库函数的参数作为特征，当参数特征符合，就进行hook，以此作为跳板安装新的hook。

而符合我们需求的标准库函数需要满足两个条件：

1. 调用时机在init_proc内部，又在检测线程创建之前
2. 参数特征足够独特能确保唯一性

现在我们回到init_proc的伪代码中:

| 1234567891011121314151617181920212223242526272829303132333435363738 | `__int64` `__fastcall init_proc()``{``__int64` `result;` `// x0``FILE` `*stream;` `// [xsp+30h] [xbp-1020h]``char` `s_1[2000];` `// [xsp+48h] [xbp-1008h] BYREF``char` `s[2000];` `// [xsp+818h] [xbp-838h] BYREF``__int64` `v5;` `// [xsp+FE8h] [xbp-68h]` `v5 = *(_QWORD *)(_ReadStatusReg(ARM64_SYSREG(3, 3, 13, 0, 2)) + 40);``*off_43FB8 = sub_118FC();``sub_11A50();``sub_1194C();``memset``(s, 0,` `sizeof``(s));``getpid();``_sprintf_chk((``__int64``)s, 0LL, 2000LL,` `"/proc/%d/cmdline"``);``stream =` `fopen``(s,` `"r"``);``if` `( stream )``{``memset``(s_1, 0,` `sizeof``(s_1));``fscanf``(stream,` `"%s"``, s_1);``fclose``(stream);``if` `( !``strchr``(s_1, 58) )``sub_1A8A0();``}``sub_12C28();``if` `( !(sub_16C08() & 1) )``sub_114B0();``if` `( (sub_18754() & 1) == 0 )``sub_114B0();``sub_23280();``sub_21D9C();``if` `( *off_43FB8 > 23 )``*off_43ED8 = 1;``result = sub_BE2C();``if` `( (_DWORD)result == 1 )``return` `sub_8C38();``return` `result;``}` |
|-|-|

根据之前的调用链追溯已知sub_1A8A0内创建了检测线程，那么我们就查看该函数之前的逻辑

首先进入sub_118FC函数，伪代码如下：

| 123456789 | `__int64` `sub_118FC()``{``_QWORD nptr[2];` `// [xsp+0h] [xbp-20h] BYREF` `nptr[1] = *(_QWORD *)(_ReadStatusReg(ARM64_SYSREG(3, 3, 13, 0, 2)) + 40);``nptr[0] = 0LL;``_system_property_get();``return` `atoi``((``const` `char` `*)nptr);``}` |
|-|-|

能大致看出该函数是通过atoi将字符串转换成整数返回，随后在init_proc内通过*off_43FB8接收sub_118FC的返回值，并与23比较；

写过一些简单安卓应用的朋友对23这个数字肯定不陌生，sub_118FC的功能大概率就是返回当前安卓的SDK版本，接着在后续做相应的版本兼容操作。

IDA对这段伪代码的生成明显有缺陷，可以看见_system_property_get没有被传入任何参数，我们切换成汇编来看看

| 1234567891011121314151617181920212223242526 | `LOAD:``00000000000118FC` `sub_118FC                               ; CODE XREF: .init_proc``+``2C``↓p``LOAD:``00000000000118FC`                                         `; sub_15064``+``630``↓p ...``LOAD:``00000000000118FC``LOAD:``00000000000118FC` `var_20` `=` `-``0x20``LOAD:``00000000000118FC` `var_18` `=` `-``0x18``LOAD:``00000000000118FC` `var_10` `=` `-``0x10``LOAD:``00000000000118FC` `var_8` `=` `-``8``LOAD:``00000000000118FC``LOAD:``00000000000118FC`                 `SUB             SP, SP,` `#0x20``LOAD:``0000000000011900`                 `STP             X19, X30, [SP,``#0x20+var_10]``LOAD:``0000000000011904`                 `MRS             X19, TPIDR_EL0``LOAD:``0000000000011908`                 `LDR             X8, [X19,``#0x28]``LOAD:``000000000001190C`                 `ADRL            X0, aRoBuildVersion ;` `"ro.build.version.sdk"``LOAD:``0000000000011914`                 `MOV             X1, SP``LOAD:``0000000000011918`                 `STR`             `X8, [SP,``#0x20+var_18]``LOAD:``000000000001191C`                 `STR`             `XZR, [SP,``#0x20+var_20]``LOAD:``0000000000011920`                 `BL              __system_property_get``LOAD:``0000000000011924`                 `MOV             X0, SP  ; nptr``LOAD:``0000000000011928`                 `BL              atoi``LOAD:``000000000001192C`                 `LDR             X8, [X19,``#0x28]``LOAD:``0000000000011930`                 `LDR             X9, [SP,``#0x20+var_18]``LOAD:``0000000000011934`                 `CMP`             `X8, X9``LOAD:``0000000000011938`                 `B.NE            loc_11948``LOAD:``000000000001193C`                 `LDP             X19, X30, [SP,``#0x20+var_10]``LOAD:``0000000000011940`                 `ADD             SP, SP,` `#0x20 ; ' '``LOAD:``0000000000011944`                 `RET` |
|-|-|

可以看见字符串参数"ro.build.version.sdk"被传递给了__system_property_get，而该函数就符合我们此前的所设立的条件，既处于.init_proc的开头，又有能够利用的特征参数，现在我们就可以将该函数作为安装hook的跳板了，代码如下

| 1234567891011121314151617181920 | `function` `hook_system_property_get() {``var` `system_property_get_addr = Module.findExportByName(``null``,``"__system_property_get"``)``if``(!system_property_get_addr){``console.log(``"[INFO] __system_property_get not found"``);``return``}``Interceptor.attach(system_property_get_addr, {``onEnter:` `function` `(args) {``var` `nameptr = args[0];``if` `(nameptr) {``var` `name = ptr(nameptr).readCString();``if` `(name.indexOf(``"ro.build.version.sdk"``) >= 0) {``console.log(``"Found ro.build.version.sdk, need to patch"``);``//hook_pthread_create()``}``}` `}``});``}` |
|-|-|

在跳板定位成功后我们就可以开始手动patch了，如果不嫌麻烦的话可以直接查看IDA的交叉引用搜索结果，一个个跳转过去查看线程地址，随后计算基址+偏移进行nop即可

| 12345678910111213141516171819202122232425262728293031323334 | `function` `nop_64(addr) {``Memory.protect(addr, 4 ,` `'rwx'``);``var` `w =` `new` `Arm64Writer(addr);``w.putRet();``w.flush();``w.dispose();``console.log(``"replace addr: "` `+ addr);``}` `function` `hook_system_property_get() {``var` `system_property_get_addr = Module.findExportByName(``null``,``"__system_property_get"``)``if``(!system_property_get_addr){``console.log(``"[INFO] __system_property_get not found"``);``return``}``console.log(``"[INFO] __system_property_get found"``);``Interceptor.attach(system_property_get_addr, {``onEnter:` `function` `(args) {``var` `nameptr = args[0];``if` `(nameptr) {``var` `name = ptr(nameptr).readCString();``if` `(name.indexOf(``"ro.build.version.sdk"``) >= 0) {``console.log(``"Found ro.build.version.sdk, need to patch"``);``var` `base = Process.getModuleByName(``"libmsaoaidsec.so"``).base``nop_64(base.add(0x18C88))``nop_64(base.add(0x199E0))``nop_64(base.add(0x1A574))``nop_64(base.add(0x1AEE4))``}``}` `}``});``}` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_BCAQB775Q7JDUVM.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_UK3JDKDPQE6FV5E.webp)
或者直接hook pthread_create，将实例参数替换成空函数

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354 | `function` `hook_pthread_create() {``var` `pthread_create = Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``var` `libmsaoaidsec = Process.findModuleByName(``"libmsaoaidsec.so"``);` `if` `(!libmsaoaidsec) {``console.log(``"libmsaoaidsec.so not found"``);``return``;``}` `//console.log("libmsaoaidsec.so base: " + libmsaoaidsec.base);` `if` `(!pthread_create) {``console.log(``"pthread_create not found"``);``return``;``}` `Interceptor.attach(pthread_create, {``onEnter:` `function``(args) {``var` `thread_ptr = args[2];``if` `(thread_ptr.compare(libmsaoaidsec.base) < 0 \|\| thread_ptr.compare(libmsaoaidsec.base.add(libmsaoaidsec.size)) >= 0) {``//console.log("pthread_create other thread: " + thread_ptr);``}` `else` `{``var` `offset = thread_ptr.sub(libmsaoaidsec.base)``console.log(``"pthread_create libmsaoaidsec.so thread: "` `+ thread_ptr +` `" offset: "` `+ offset);``Interceptor.replace(thread_ptr,``new` `NativeCallback(``function``(){``console.log(``"[hook] replace offset: "` `+ offset)``},``"void"``,[]))``}``},``onLeave:` `function``(retval) {}``});``}` `function` `hook_system_property_get() {``var` `system_property_get_addr = Module.findExportByName(``null``,``"__system_property_get"``)``if``(!system_property_get_addr){``console.log(``"[INFO] __system_property_get not found"``);``return``}``console.log(``"[INFO] __system_property_get found"``);``Interceptor.attach(system_property_get_addr, {``onEnter:` `function` `(args) {``var` `nameptr = args[0];``if` `(nameptr) {``var` `name = ptr(nameptr).readCString();``if` `(name.indexOf(``"ro.build.version.sdk"``) >= 0) {``console.log(``"Found ro.build.version.sdk, need to patch"``);``hook_pthread_create()``}``}` `}``});``}` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_N2TAFCTPTV63NYY.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_E3HF5GMHZ7X3STA.webp)
至此，目标app的frida检测便成功绕过了，目标程序也不再卡死或退出，总结一下可行的方案：

1. 直接对android_dlopen_ext进行Hook，判断第一个参数是否是我们的目标so，如果是就直接将指针指向的值置为空
2. 以__system_property_get为跳板，在其中手动patch掉检测routing的地址
3. 以__system_property_get为跳板，直接Hook pthread_create，将作为routing函数的参数replace为空函数

### 证书验证

接下来就是证书校验，哪怕我们的证书是系统证书，抓包仍旧会提示证书错误，也就是说目标app只会信任由后端传递的证书
 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_G9WF6TC87H8RQ8B.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_WVNCVRKRE7H9JX8.webp)
既然存在证书验证，那么就先做信息收集，确定目标使用的是哪个网路框架，由于系统包的类名不会受到编译期的控制，因而也不会出现类名混淆的情况，我们选择startHandshake进行Hook，打印堆栈(不过我还是建议你hook file$init)

| 123456789101112131415 | `function` `hookssl(){` `Java.perform(``function``(){``var`  `SSLSocket  = Java.use(``"com.android.org.conscrypt.ConscryptFileDescriptorSocket"``);``console.log(``"SSLSocket "``,SSLSocket);``SSLSocket.startHandshake.implementation =` `function` `() {``console.log(``"startHandshake"``);``console.log(Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Exception"``).$``new``()))``return` `this``.startHandshake();``}` `});``}` `hookssl()` |
|-|-|

| 12345678910111213141516171819202122232425262728293031323334353637383940414243 | `startHandshake``java.lang.Exception``at com.android.org.conscrypt.ConscryptFileDescriptorSocket.startHandshake(Native Method)``at com.android.org.conscrypt.ConscryptFileDescriptorSocket.waitForHandshake(ConscryptFileDescriptorSocket.java:476)``at com.android.org.conscrypt.ConscryptFileDescriptorSocket.getOutputStream(ConscryptFileDescriptorSocket.java:463)``at okio.Okio__JvmOkioKt.sink(JvmOkio.kt:127)``at okio.Okio.sink(Unknown Source:1)``at okhttp3.internal.connection.RealConnection.connectTls(RealConnection.kt:422)``at okhttp3.internal.connection.RealConnection.establishProtocol(RealConnection.kt:337)``at okhttp3.internal.connection.RealConnection.connect(RealConnection.kt:209)``at okhttp3.internal.connection.ExchangeFinder.findConnection(ExchangeFinder.kt:226)``at okhttp3.internal.connection.ExchangeFinder.findHealthyConnection(ExchangeFinder.kt:106)``at okhttp3.internal.connection.ExchangeFinder.``find``(ExchangeFinder.kt:74)``at okhttp3.internal.connection.RealCall.initExchange$okhttp(RealCall.kt:255)``at okhttp3.internal.connection.ConnectInterceptor.intercept(ConnectInterceptor.kt:32)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.kt:109)``at okhttp3.internal.cache.CacheInterceptor.intercept(CacheInterceptor.kt:95)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.kt:109)``at okhttp3.internal.http.BridgeInterceptor.intercept(BridgeInterceptor.kt:83)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.kt:109)``at okhttp3.internal.http.RetryAndFollowUpInterceptor.intercept(RetryAndFollowUpInterceptor.kt:76)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.kt:109)``at com.delivery.wp.argus.android.hook.okhttp.RecordBodyInterceptor.intercept(RecordBodyInterceptor.kt:35)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.kt:109)``at okhttp3.internal.connection.RealCall.getResponseWithInterceptorChain$okhttp(RealCall.kt:201)``at okhttp3.internal.connection.RealCall.execute(RealCall.kt:154)``at gnet.android.OkHttpRawCall$RawCallInterceptor.intercept(OkHttpRawCall.java:170)``at gnet.android.Interceptor$Chain.OOOO(Interceptor.java:33)``at gnet.android.OkHttpRawCall$MetricsInterceptor.intercept(OkHttpRawCall.java:125)``at gnet.android.Interceptor$Chain.OOOO(Interceptor.java:33)``at gnet.android.OkHttpRawCall.OO00(OkHttpRawCall.java:88)``at gnet.android.OkHttpRawCall.OOOO(OkHttpRawCall.java:61)``at gnet.android.GNetRawCall.OOoO(GNetRawCall.java:47)``at com.delivery.wp.argus.android.performance.performanceconfig.PerformanceConfig$Companion.OOOO(PerformanceConfig.kt:77)``at com.delivery.wp.argus.android.performance.performanceconfig.PerformanceConfig$Companion$createLooperGetConfig$1.realAction(PerformanceConfig.kt:269)``at com.delivery.wp.argus.android.schedule.AbstractFixedDelayPoller$scheduleAction$1.invoke(AbstractFixedDelayPoller.kt:17)``at com.delivery.wp.argus.android.schedule.AbstractFixedDelayPoller$scheduleAction$1.invoke(AbstractFixedDelayPoller.kt:17)``at com.delivery.wp.argus.android.schedule.GlobalTaskScheduler.schedule$lambda-0(GlobalTaskScheduler.kt:40)``at com.delivery.wp.argus.android.schedule.GlobalTaskScheduler.lambda$hMW5Kte4X_Lonty_nd3X3zcuuyg(Unknown Source:0)``at com.delivery.wp.argus.android.schedule.-$$Lambda$GlobalTaskScheduler$hMW5Kte4X_Lonty_nd3X3zcuuyg.run(Unknown Source:2)``at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1167)``at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:641)``at java.lang.Thread.run(Thread.java:919)` |
|-|-|

堆栈显示是okhttp，没啥可说，很常见的网络框架。

能看见一些混淆函数，但okhttp的类名未做混淆，进入connectTls函数查看，这里是okhttp库正式发起请求的地方

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990 | `private` `final` `void` `connectTls(ConnectionSpecSelector connectionSpecSelector)` `throws` `Throwable {``final` `Address address =` `this``.route.address();``SSLSocketFactory sslSocketFactory = address.sslSocketFactory();``SSLSocket sSLSocket =` `null``;``try` `{``Intrinsics.checkNotNull(sslSocketFactory);``Socket socketCreateSocket = sslSocketFactory.createSocket(``this``.rawSocket, address.url().host(), address.url().port(),` `true``);``if` `(socketCreateSocket ==` `null``) {``throw` `new` `NullPointerException(``"null cannot be cast to non-null type javax.net.ssl.SSLSocket"``);``}``SSLSocket sSLSocket2 = (SSLSocket) socketCreateSocket;``try` `{``ConnectionSpec connectionSpecConfigureSecureSocket = connectionSpecSelector.configureSecureSocket(sSLSocket2);``if` `(connectionSpecConfigureSecureSocket.supportsTlsExtensions()) {``Platform.INSTANCE.get().configureTlsExtensions(sSLSocket2, address.url().host(), address.protocols());``}``sSLSocket2.startHandshake();``SSLSession sslSocketSession = sSLSocket2.getSession();``Handshake.Companion companion = Handshake.INSTANCE;``Intrinsics.checkNotNullExpressionValue(sslSocketSession,` `"sslSocketSession"``);``final` `Handshake handshake = companion.get(sslSocketSession);``HostnameVerifier hostnameVerifier = address.hostnameVerifier();``Intrinsics.checkNotNull(hostnameVerifier);``if` `(hostnameVerifier.verify(address.url().host(), sslSocketSession)) {` `// HOST验证``final` `CertificatePinner certificatePinner = address.certificatePinner();``Intrinsics.checkNotNull(certificatePinner);``this``.handshake =` `new` `Handshake(handshake.tlsVersion(), handshake.cipherSuite(), handshake.localCertificates(),` `new` `Function0<List<?` `extends` `Certificate>>() {` `// from class: okhttp3.internal.connection.RealConnection.connectTls.1``/* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */``{``super(0);``}` `/* JADX DEBUG: Method merged with bridge method: invoke()Ljava/lang/Object; */``/* JADX DEBUG: Return type fixed from 'java.util.List<java.security.cert.Certificate>' to match base method */``@Override // kotlin.jvm.functions.Function0``public final List<? extends Certificate> invoke() {``CertificateChainCleaner certificateChainCleaner = certificatePinner.getCertificateChainCleaner();``Intrinsics.checkNotNull(certificateChainCleaner);``return certificateChainCleaner.clean(handshake.peerCertificates(), address.url().host());``}``});``certificatePinner.check$okhttp(address.url().host(), new Function0<List<? extends X509Certificate>>() { // from class: okhttp3.internal.connection.RealConnection.connectTls.2``{``super(0);``}` `/* JADX DEBUG: Method merged with bridge method: invoke()Ljava/lang/Object; */``/* JADX DEBUG: Return type fixed from 'java.util.List<java.security.cert.X509Certificate>' to match base method */``@Override` `// kotlin.jvm.functions.Function0``public` `final` `List<?` `extends` `X509Certificate> invoke() {``Handshake handshake2 = RealConnection.``this``.handshake;``Intrinsics.checkNotNull(handshake2);``List<Certificate> listPeerCertificates = handshake2.peerCertificates();``ArrayList arrayList =` `new` `ArrayList(CollectionsKt.collectionSizeOrDefault(listPeerCertificates,` `10``));``Iterator<T> it2 = listPeerCertificates.iterator();``while` `(it2.hasNext()) {``arrayList.add((X509Certificate) ((Certificate) it2.next()));``}``return` `arrayList;``}``});``String selectedProtocol = connectionSpecConfigureSecureSocket.supportsTlsExtensions() ? Platform.INSTANCE.get().getSelectedProtocol(sSLSocket2) : (String)` `null``;``this``.socket = sSLSocket2;``this``.source = Okio.buffer(Okio.source(sSLSocket2));``this``.sink = Okio.buffer(Okio.sink(sSLSocket2));``this``.protocol = selectedProtocol !=` `null` `? Protocol.INSTANCE.get(selectedProtocol) : Protocol.HTTP_1_1;``Platform.INSTANCE.get().afterHandshake(sSLSocket2);``return``;``}``List<Certificate> listPeerCertificates = handshake.peerCertificates();``if` `(!(!listPeerCertificates.isEmpty())) {``throw` `new` `SSLPeerUnverifiedException(``"Hostname "` `+ address.url().host() +` `" not verified (no certificates)"``);``}``X509Certificate x509Certificate = (X509Certificate) listPeerCertificates.get(``0``);``throw` `new` `SSLPeerUnverifiedException(StringsKt.trimMargin$``default``(``"\n              \|Hostname "` `+ address.url().host() +` `" not verified:\n              \|    certificate: "` `+ CertificatePinner.INSTANCE.pin(x509Certificate) +` `"\n              \|    DN: "` `+ ((Object) x509Certificate.getSubjectDN().getName()) +` `"\n              \|    subjectAltNames: "` `+ OkHostnameVerifier.INSTANCE.allSubjectAltNames(x509Certificate) +` `"\n              "``,` `null``,` `1``,` `null``));``}` `catch` `(Throwable th) {``th = th;``sSLSocket = sSLSocket2;``if` `(sSLSocket !=` `null``) {``Platform.INSTANCE.get().afterHandshake(sSLSocket);``}``if` `(sSLSocket !=` `null``) {``Util.closeQuietly((Socket) sSLSocket);``}``throw` `th;``}``}` `catch` `(Throwable th2) {``th = th2;``}``}` |
|-|-|

能看见做了两个校验，先是host验证，随后通过checkokhttphashhookcheckokhttp校验证书的hash值，我们hook checkokhttp校验证书的hash值，我们hookcheckokhttp，直接返回防止异常抛出。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647 | `function` `host_bypass(){``var` `HostnameVerifierInterface = Java.use(``'javax.net.ssl.HostnameVerifier'``)``const MyHostnameVerifier = Java.registerClass({``name:` `'org.dummyPackage.MyHostnameVerifier'``,``implements: [HostnameVerifierInterface],``methods: {` `verify: [{``returnType:` `'boolean'``,``argumentTypes: [``'java.lang.String'``,` `'javax.net.ssl.SSLSession'``],``implementation(hostname, session) {``console.log(``'[+] Hostname verification bypass'``);``return` `true``;``}``}],``}``});` `var` `hostnameVerifierRef = Java.use(``'okhttp3.OkHttpClient'``)[``'hostnameVerifier'``].overload();``hostnameVerifierRef.implementation =` `function``() {` `return` `MyHostnameVerifier.$``new``();``}``console.log(``"[+] Hostname verifier replaced"``)``}` `function` `check_bypass(){``let CertificatePinner = Java.use(``"okhttp3.CertificatePinner"``);``CertificatePinner[``"check$okhttp"``].implementation =` `function` `(hostname, cleanedPeerCertificatesFn) {``console.log(``"[hook] check bypass..."``);``//this["check$okhttp"](hostname, cleanedPeerCertificatesFn);``console.log(``"[info] host:"` `+ hostname)``var` `SSLstackread = Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Throwable"``).$``new``()).toString();``console.log(``"=================================="``)``console.log(``"[info] stack: "` `+ SSLstackread)``console.log(``"=================================="``)` `return``};``}`   `function` `main(){``host_bypass()``check_bypass()``}` `Java.perform(main)` |
|-|-|

| 12345678910111213141516171819202122232425262728293031323334 | `Attaching...``[``+``] Hostname verifier replaced``[LM G710::xx出行 ]``-``> [hook] check bypass...``[info] host:ip.qaros.com``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``[info] stack: java.lang.Throwable``at okhttp3.CertificatePinner.check$okhttp(Native Method)``at okhttp3.internal.connection.RealConnection.connectTls(RealConnection.kt:``410``)` `at okhttp3.internal.connection.RealConnection.establishProtocol(RealConnection.kt:``337``)``at okhttp3.internal.connection.RealConnection.connect(RealConnection.kt:``209``)``at okhttp3.internal.connection.ExchangeFinder.findConnection(ExchangeFinder.kt:``226``)``at okhttp3.internal.connection.ExchangeFinder.findHealthyConnection(ExchangeFinder.kt:``106``)``at okhttp3.internal.connection.ExchangeFinder.find(ExchangeFinder.kt:``74``)``at okhttp3.internal.connection.RealCall.initExchange$okhttp(RealCall.kt:``255``)``at okhttp3.internal.connection.ConnectInterceptor.intercept(ConnectInterceptor.kt:``32``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.kt:``109``)``at okhttp3.internal.cache.CacheInterceptor.intercept(CacheInterceptor.kt:``95``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.kt:``109``)``at okhttp3.internal.http.BridgeInterceptor.intercept(BridgeInterceptor.kt:``83``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.kt:``109``)``at okhttp3.internal.http.RetryAndFollowUpInterceptor.intercept(RetryAndFollowUpInterceptor.kt:``76``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.kt:``109``)``at com.delivery.wp.argus.android.hook.okhttp.RecordBodyInterceptor.intercept(RecordBodyInterceptor.kt:``56``)``at okhttp3.internal.http.RealInterceptorChain.proceed(RealInterceptorChain.kt:``109``)``at okhttp3.internal.connection.RealCall.getResponseWithInterceptorChain$okhttp(RealCall.kt:``201``)``at okhttp3.internal.connection.RealCall.execute(RealCall.kt:``154``)``at gnet.android.ClientIPReporter.fetchClientIPAddress$``lambda``-``1``(ClientIPReporter.kt:``60``)``at gnet.android.ClientIPReporter.``lambda``$``1G``-``0OwxFS5VN_JvFsG079eY3uKY``(Unknown Source:``0``)``at gnet.android.``-``$$Lambda$ClientIPReporter$``1G``-``0OwxFS5VN_JvFsG079eY3uKY``.run(Unknown Source:``6``)``at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:``1167``)``at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:``641``)``at java.lang.Thread.run(Thread.java:``919``)` `=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=` |
|-|-|

可以看见hook确实命中了，但证书校验仍旧存在，并且通过打印参数会发现是获取IP物理地址的网站请求以及某宝的第三方域名，而非我们的目标域名。

也就是说访问第三方域名的服务时走的是默认证书校验，而只有目标域名添加了SSL证书的保护逻辑。

这样的话，就很可能是client在build时重写了X509TrustManager类；

不过在继续分析之前我们先明确一下调用顺序，以下示例是一个典型的自实现重载X509TrustManager，信任全部证书的例子

| 1234567891011121314151617181920212223242526272829303132333435363738394041 | `public` `static` `OkHttpClient getUnsafeOkHttpClient() {``try` `{``final` `TrustManager[] trustAllCerts =` `new` `TrustManager[] {``new` `X509TrustManager() {``@Override``public` `void` `checkClientTrusted(java.security.cert.X509Certificate[] chain, String authType) {``}` `@Override``public` `void` `checkServerTrusted(java.security.cert.X509Certificate[] chain, String authType) {``}` `@Override``public` `java.security.cert.X509Certificate[] getAcceptedIssuers() {``return` `new` `java.security.cert.X509Certificate[]{};``}``}``};` `final` `SSLContext sslContext = SSLContext.getInstance(``"SSL"``);``sslContext.init(``null``, trustAllCerts,` `new` `java.security.SecureRandom());``final` `javax.net.ssl.SSLSocketFactory sslSocketFactory = sslContext.getSocketFactory();` `OkHttpClient.Builder builder =` `new` `OkHttpClient.Builder();``builder.sslSocketFactory(sslSocketFactory);``builder.hostnameVerifier(``new` `HostnameVerifier() {``@Override``public` `boolean` `verify(String hostname, SSLSession session) {``return` `true``;``}``});` `OkHttpClient okHttpClient = builder``.connectTimeout(``10``, TimeUnit.SECONDS)``//设置连接超时时间``.readTimeout(``20``, TimeUnit.SECONDS)``//设置读取超时时间``.build();``return` `okHttpClient;``}` `catch` `(Exception e) {``throw` `new` `RuntimeException(e);``}``}` |
|-|-|

X509TrustManager封装在SSLSocketFactory内部，设置sslContext，并传入自实现重载X509TrustManager后的trustAllCerts，再将sslSocketFactory交给builder，最后使用配置好的builder构建Client，而所有构建的request都通过该Client发送。

随后我们查看AOSP的源码，能看见 verifyCertificateChain被注册为doHandshake执行时的回调

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_QW5VPSR9YVSTKY3.webp)
此刻调用链条便可以简化为：

okHttpClient.newCall发送请求->connectTls->NativeSsl.doHandshake->触发callback函数->ConscryptFileDescriptorSocket.verifyCertificateChain->

信任证书->回到connectTls继续执行check->

不信任证书->抛出异常终止请求

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_2EWGKJKNT7Q885U.webp)
这再次证明了我们之前的推测，由于目标域名添加了自实现的验证逻辑，所有向目标域名发送的请求因为verifyCertificateChain验证不通过抛出了异常，导致根本就没有执行connectTls下面的逻辑，自然check也不会执行，而所有命中check hook的参数则都是未做证书验证的第三方域名。

我本试图hook verifyCertificateChain，直接返回，但目标app似乎对该函数也做了防护，一旦Hook就会退出进程，从头再去逆向对该函数的检测点太麻烦，先试着继续跟AOSP源码看看verifyCertificateChain内部的实现，是否存在其它hook点，AOSP源码如下

| 12345678910111213141516171819202122232425262728 | `@Override``public` `final` `void` `verifyCertificateChain(``byte``[][] certChain, String authMethod)``throws` `CertificateException {``try` `{``if` `(certChain ==` `null` `\|\| certChain.length ==` `0``) {``throw` `new` `CertificateException(``"Peer sent no certificate"``);``}``X509Certificate[] peerCertChain = SSLUtils.decodeX509CertificateChain(certChain);` `X509TrustManager x509tm = sslParameters.getX509TrustManager();``if` `(x509tm ==` `null``) {``throw` `new` `CertificateException(``"No X.509 TrustManager"``);``}``// Update the peer information on the session.``activeSession.onPeerCertificatesReceived(getHostnameOrIP(), getPort(), peerCertChain);` `if` `(getUseClientMode()) {``Platform.checkServerTrusted(x509tm, peerCertChain, authMethod,` `this``);``}` `else` `{``String authType = peerCertChain[``0``].getPublicKey().getAlgorithm();``Platform.checkClientTrusted(x509tm, peerCertChain, authType,` `this``);``}``}` `catch` `(CertificateException e) {``throw` `e;``}` `catch` `(Exception e) {``throw` `new` `CertificateException(e);``}``}` |
|-|-|

可以看见上半部分的异常抛出都是些常规检测，不涉及对证书本身进行校验的逻辑，那么就剩下checkServerTrusted与checkClientTrusted，问下gemini看看这两个函数的作用

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_D82DK75BQ3HK7M6.webp)
抓包的错误显示在握手阶段就失败了，我们可以假设是由客户端校验导致的，选择跟进checkServerTrusted查看逻辑

| 1234567891011 | `static` `void` `checkServerTrusted(X509TrustManager tm, X509Certificate[] chain, String authType,``AbstractConscryptSocket socket)` `throws` `CertificateException {``if` `(tm` `instanceof` `X509ExtendedTrustManager) {``X509ExtendedTrustManager x509etm = (X509ExtendedTrustManager) tm;``x509etm.checkServerTrusted(chain, authType, socket);``}` `else` `if` `(!checkTrusted(``"checkServerTrusted"``, tm, chain, authType, Socket.``class``, socket)``&& !checkTrusted(``"checkServerTrusted"``, tm, chain, authType, String.``class``,``socket.getHandshakeSession().getPeerHost())) {``tm.checkServerTrusted(chain, authType);``}``}` |
|-|-|

AOSP中没有多少有价值的信息，毕竟这只是个接口，你很难确定负责实现的tm从哪传来，不过既然该函数在必经之路，那么无论是自实现tm也好还是标准库也好，我们都可以选择hook此处，随后打印tm的源头。

实际上**使用以下脚本就已经能够过掉证书校验，进行抓包了**，无论tm从哪传来，我们直接hook该函数不做任何操作，自然就不会有任何异常被抛出，不过我们可以继续深入，看看校验逻辑是如何实现的。

| 12345678910111213141516 | `function` `hook_checkServerTrusted(){``var` `Platform = Java.use(``"com.android.org.conscrypt.Platform"``);``var` `checkServerTrusteds = Platform.checkServerTrusted.overloads;``checkServerTrusteds.forEach(``function``(overload){` `overload.implementation =` `function``(){``var` `args = Array.from(arguments);` `console.log(``"[hook] Bypass checkServerTrusteds..."``)``console.log(``"[hook] call from TrustManager: "` `+ args[0].$className)``}` `});``}` `Java.perform(hook_checkServerTrusted)` |
|-|-|

| 1234567891011121314151617181920212223242526 | `[LM G710::xx出行 ]-> [hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: com.xiaola.http.ssl.SSLSocketClient$MyTrustManager``[hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: android.security.net.config.RootTrustManager``[hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: android.security.net.config.RootTrustManager``[hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: android.security.net.config.RootTrustManager``[hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: android.security.net.config.RootTrustManager``[hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: android.security.net.config.RootTrustManager``[hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: android.security.net.config.RootTrustManager``[hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: android.security.net.config.RootTrustManager``[hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: android.security.net.config.RootTrustManager``[hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: com.xiaola.third.glide.UnsafeOkHttpClient$1``[hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: com.xiaola.third.glide.UnsafeOkHttpClient$1``[hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: com.xiaola.third.glide.UnsafeOkHttpClient$1``[hook] Bypass checkServerTrusteds...``[hook] call from TrustManager: $Proxy1` |
|-|-|

其中看起来最可疑的是自实现MyTrustManager与UnsafeOkHttpClient$1，而出乎意料的两者的自实现均没有任何验证证书的逻辑

| 123456789101112131415161718192021222324252627282930313233343536 | `public` `class` `UnsafeOkHttpClient {``public` `static` `OkHttpClient OOOO()` `throws` `NoSuchAlgorithmException, KeyManagementException {``try` `{``TrustManager[] trustManagerArr = {``new` `X509TrustManager() {` `// from class: com.xiaola.third.glide.UnsafeOkHttpClient.1``@Override` `// javax.net.ssl.X509TrustManager``public` `void` `checkClientTrusted(X509Certificate[] x509CertificateArr, String str)` `throws` `CertificateException {``}` `@Override` `// javax.net.ssl.X509TrustManager``public` `void` `checkServerTrusted(X509Certificate[] x509CertificateArr, String str)` `throws` `CertificateException {``}` `@Override` `// javax.net.ssl.X509TrustManager``public` `X509Certificate[] getAcceptedIssuers() {``return` `new` `X509Certificate[``0``];``}``}};``SSLContext sSLContext = SSLContext.getInstance(``"SSL"``);``sSLContext.init(``null``, trustManagerArr,` `new` `SecureRandom());``SSLSocketFactory socketFactory = sSLContext.getSocketFactory();``OkHttpClient.Builder builder =` `new` `OkHttpClient.Builder();``builder.sslSocketFactory(socketFactory, (X509TrustManager) trustManagerArr[``0``]);``builder.hostnameVerifier(``new` `HostnameVerifier() {` `// from class: com.xiaola.third.glide.UnsafeOkHttpClient.2``@Override` `// javax.net.ssl.HostnameVerifier``public` `boolean` `verify(String str, SSLSession sSLSession) {``return` `true``;``}``});``builder.connectTimeout(20L, TimeUnit.SECONDS);``builder.readTimeout(20L, TimeUnit.SECONDS);``return` `builder.build();``}` `catch` `(Exception e) {``throw` `new` `RuntimeException(e);``}``}``}` |
|-|-|

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051 | `public` `class` `SSLSocketClient {` `/* renamed from: com.xiaola.http.ssl.SSLSocketClient$1, reason: invalid class name */``class AnonymousClass1 implements HostnameVerifier {``@Override // javax.net.ssl.HostnameVerifier``public boolean verify(String str, SSLSession sSLSession) {``return true;``}``}` `public static SSLSocketFactory OOOO() throws NoSuchAlgorithmException, KeyManagementException {``try {``SSLContext sSLContext = SSLContext.getInstance("SSL");``sSLContext.init(null, OOO0(), new SecureRandom());``return sSLContext.getSocketFactory();``} catch (Exception e) {``throw new RuntimeException(e);``}``}` `private static TrustManager[] OOO0() {``return new TrustManager[]{OOOo()};``}` `public static X509TrustManager OOOo() {``return new MyTrustManager(null);``}` `private static final class MyTrustManager implements X509TrustManager {``@Override // javax.net.ssl.X509TrustManager``public void checkClientTrusted(X509Certificate[] x509CertificateArr, String str) throws CertificateException {``}` `@Override // javax.net.ssl.X509TrustManager``public void checkServerTrusted(X509Certificate[] x509CertificateArr, String str) throws CertificateException {``}` `@Override // javax.net.ssl.X509TrustManager``public X509Certificate[] getAcceptedIssuers() {``return new X509Certificate[0];``}` `private MyTrustManager() {``}` `/* JADX DEBUG: Can't inline method, not implemented redirect type for insn: 0x0000: CONSTRUCTOR  A[MD:():void (m)] (LINE:56) call: com.xiaola.http.ssl.SSLSocketClient.MyTrustManager.<init>():void type: THIS */``/* synthetic */` `MyTrustManager(AnonymousClass1 anonymousClass1) {``this``();``}``}``}` |
|-|-|

既然如此，就只能关注android.security.net.config.RootTrustManager了，我们再来问下gemini这个类的作用。

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_CRF4HDR7ZZRVF4K.webp)
而我们果真在app中找到了xml配置文件：

| 1234567891011121314151617181920212223242526272829303132 | `<?``xml` `version``=``"1.0"` `encoding``=``"utf-8"``?>``<``network-security-config``>``<``base-config` `cleartextTrafficPermitted``=``"true"``/>``<``domain-config``>``<``domain` `includeSubdomains``=``"true"``>xiaolachuxing.com``</``domain``>``<``pin-set``>``<``pin` `digest``=``"SHA-256"``>0QdOq6zRPCBV8L3UdcMBZSD3sPrJYweA5m7JX+yr+j8=``</``pin``>``</``pin-set``>``</``domain-config``>``<``domain-config``>``<``domain` `includeSubdomains``=``"true"``>huolala.cn``</``domain``>``<``pin-set` `expiration``=``"2022-05-20"``>``<``pin` `digest``=``"SHA-256"``>dtzoaWHJKesjr1lt6Lz18OoVGFr7mzjHKMwMQdPhXB0=``</``pin``>``<``pin` `digest``=``"SHA-256"``>17aK+v0yzQmK/PW4XMoQZwl/jYvQIy6BGI/ifagUkEI=``</``pin``>``</``pin-set``>``</``domain-config``>``<``debug-overrides``>``<``trust-anchors``>``<``certificates``overridePins``=``"true"``src``=``"system"``/>``<``certificates``overridePins``=``"true"``src``=``"user"``/>``</``trust-anchors``>``</``debug-overrides``>``</``network-security-config``>` |
|-|-|

至此，校验逻辑就很清晰了，目标并非如我们一开始猜测的那样通过重载tm内的校验逻辑来自实现证书验证，而是通过配置network_security_config.xml文件来验证证书，负责校验的tm并非是自定义逻辑，而是android.security.net.config.RootTrustManager内的默认配置。

那么理论上来说，连此前的脚本都用不上，直接修改xml随后重打包就可以绕过证书验证，感兴趣的可以尝试复现。

### 加密字段分析

现在，我们解决了frida检测、SSL证书校验，接下来就可以正式开始抓包分析了。

简单删减了请求包的几个字段来测试发包，发现后端真正检验的字段只有X-Sign-Signature、X-Sign-Timestamp、X-Sign-Nonce。

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_J72N94K5UKWFKFB.webp)
幸运的是在这些字段名并未被混淆，直接在jadx中明文搜索就能够定位到，jadx没能成功将这部分的smail完全反汇编成java，只留下一段伪代码，但好在逻辑很简单

| 12345678910111213141516171819202122232425262728 | `L1ce:``java.lang.String r7 =` `"X-Sign-Nonce"``gnet.android.RawRequest$Builder r3 = r3.OOOO(r7, r6)``java.lang.String r6 =` `"SecretId"``java.lang.Object r6 = r4.get(r6)``java.lang.String r6 = (java.lang.String) r6``if` `(r6 !=` `0``)` `goto` `L1df``r6 = r14``L1df:``java.lang.String r7 =` `"X-Sign-SecretId"``gnet.android.RawRequest$Builder r3 = r3.OOOO(r7, r6)``java.lang.String r6 =` `"Timestamp"``java.lang.Object r6 = r4.get(r6)``java.lang.String r6 = (java.lang.String) r6``if` `(r6 !=` `0``)` `goto` `L1f0``r6 = r14``L1f0:``java.lang.String r7 =` `"X-Sign-Timestamp"``gnet.android.RawRequest$Builder r3 = r3.OOOO(r7, r6)``java.lang.String r6 =` `"Signature"``java.lang.Object r4 = r4.get(r6)``java.lang.String r4 = (java.lang.String) r4``if` `(r4 !=` `0``)` `goto` `L201``r4 = r14``L201:``java.lang.String r6 =` `"X-Sign-Signature"``gnet.android.RawRequest$Builder r3 = r3.OOOO(r6, r4)``goto` `L217` |
|-|-|

一眼能看出r7作为字段名，r6则是对应的键值，r4.get(r6)根据不同的字段名返回键值给r6，最后通过r3.OOOO对两者进行组装。而对r4的声明如下

| 1 | `java.util.HashMap r4 = com.delivery.wp.EncryptUtil.genSignature2(r15, r16, r17, r18, r19, r20, r21)` |
|-|-|

这函数命名就已经说明一切了，hook genSignature2并打印参数来验证猜想

| 1234567891011 | `function` `hookGen2(){``var` `EncryptUtil = Java.use(``"com.delivery.wp.EncryptUtil"``);``EncryptUtil.genSignature2(``'android.content.Context'``,` `'java.lang.String'``,` `'java.lang.String'``,` `'java.util.HashMap'``,` `'java.lang.String'``,` `'boolean'``,` `'java.lang.String'``).implementation =` `function``(context, str1, str2, hashMap, str3, bool, str4){``console.log(``"[INFO] context: "` `+ context +` `"Str1:: "``+ str1 +` `" str2: "` `+ str2 +``" hashMap: "``+ hashMap+` `" str3: "` `+str3+``" str4: "` `+ str4)``let result =` `this``[``"genSignature2"``](context, str1, str2, hashMap, str3, bool, str4);``console.log(`EncryptUtil.genSignature2 result=${result}`);``return` `result;``};``}` `Java.perform(hookGen2)` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_ZX9MVFGTYGD46R3.webp)
确认无疑，genSignature2就是获得X-Sign-Signature、X-Sign-Timestamp、X-Sign-Nonce这三个键值的函数。

接下来我们自己将参数构建出来，写个基于python的RPC脚本，将得到返回字段字段加入到请求头中，最后调requests的包发请求就完工了

参数明文有些敏感数据，就不放出来了，该函数的各个参数分别是：

1. 当前context
2. 请求方法的字符串(POST/GET)
3. 字符串"uic-user.xiaolachuxing.com/api"
4. 构建的hashmap(hashmap中包含明文手机号等目标数据)
5. 时间戳
6. 默认为false的布尔值
7. 加密Key字符串 OA643HKcfWEEdZjE9dlXSoepw69BMLVb

我们的目标是再封装短信接口的api，那么需要传递的关键数据就是hashmap中的手机号，并且hashmap的值实际上就是请求包内的json格式请求体。

并且请求体/hashmap内的值同时也包含设备风控字段；如果你直接修改手机号，而没有解决风控问题，后端就会提示多个设备登录。

听起来挺高端，其实就是通过一个随机生成的唯一字符串来作为当前设备的标识，我们只需要在每次发送请求的时候按照这串字符的格式，随机生成一段新字符串替换掉，就能够绕过设备登录多个账号的限制。

先在js脚本内组装好大部分参数，而hashmap内的post_body字段才是真正与api对应业务相关的值，涉及的键值对较多，我们在RPC脚本内封装后再传入。

JS脚本：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243 | `rpc.exports = {``getsignature:` `function` `(postBodyString) {``var` `result =` `null``;``Java.performNow(``function``() {``var` `EncryptUtil = Java.use(``"com.delivery.wp.EncryptUtil"``);``var` `context = Java.use(``'android.app.ActivityThread'``).currentApplication();``var` `HashMap = Java.use(``'java.util.HashMap'``);` `var` `str1 =` `"POST"``;``var` `str2 =` `"uic-user.xiaolachuxing.com/api"``;``var` `str4 =` `"OA643HKcfWEEdZjE9dlXSoepw69BMLVb"``;` `// SecretId``var` `bool_param =` `false``;` `var` `hashMap_instance = HashMap.$``new``();``hashMap_instance.put(``"name"``,` `"user.login.getSmsCode"``);``hashMap_instance.put(``"post_body"``, postBodyString);``hashMap_instance.put(``"version"``,` `""``);` `var` `postBodyObj = JSON.parse(postBodyString);``var` `str3 = postBodyObj._t.toString();` `console.log(``"[Frida] 当前时间戳: "``+str3);`  `console.log(``"[Frida] 正在主动调用 genSignature2..."``);``var` `javaResult = EncryptUtil.genSignature2(context, str1, str2, hashMap_instance, str3, bool_param, str4);``if` `(javaResult) {``var` `nonce_str = String(javaResult.get(``'Nonce'``));``var` `signature_str = String(javaResult.get(``'Signature'``));``var` `timestamp_str = String(javaResult.get(``'Timestamp'``));` `result = {``'Nonce'``: nonce_str,``'Signature'``: signature_str,``'Timestamp'``: timestamp_str``};``console.log(``"[Frida] 成功获取签名 (明文): "` `+ JSON.stringify(result));``}``console.log(``"[Frida] 成功获取签名: "` `+ JSON.stringify(result));``});``return` `result` `}``};` |
|-|-|

frida rpc脚本：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113 | `import` `requests``import` `json``import` `frida``import` `uuid``import` `random``from` `urllib.parse` `import` `quote``import` `time` `#过设备风控``def` `genDeviceId():``UUID_str` `=` `str``(uuid.uuid4())``print``(f``"获得设备ID: {UUID_str}"``)``return` `UUID_str` `#过设备风控2``def` `genImei():``Seed` `=` `"0123456789abcdef"``imei` `=` `''.join(random.choices(Seed, k``=``16``))``print``(f``"获得Imei: {imei}"``)``return` `imei` `def` `getSignature(post_body_json_string):` `session` `=` `frida.get_usb_device().attach(``"xx出行"``)``with` `open``(``"hook-genSignature2_RPC.js"``, encoding``=``"UTF-8"``) as f:``script_content` `=` `f.read()``script` `=` `session.create_script(script_content)` `def` `on_message(message, data):``print``(f``"[Frida Message] {message}"``)``script.on(``'message'``, on_message)``script.load()` `apis` `=` `script.exports``print``(``"正在调用 Frida RPC 函数 'getsignature'..."``)``result` `=` `apis.getsignature(post_body_json_string)``session.detach()``return` `result`  `def` `SendSMS(PhoneNum):``DeviceID` `=` `genDeviceId()``imei` `=` `genImei()``su` `=` `250X0XX0X4X2X6X1X00X0X7X21XXXX7X``timestamp` `=` `str``(``1754671512``)``print``(f``"使用时间戳: {timestamp}"``)` `inner_data_dict` `=` `{``"phoneNo"``:``str``(PhoneNum),``"app"``:``"xl"``,``"token"``:"``","``os``":"``XL_ANDROID``","``os_version``":"``10``","``os_bran``":"``lge``","``xl_version``":"``2.3``.``2``","``xl_revision``":2302,"``_t``":int(timestamp),"``hf_version``":"``0``","``client_type``":"``1001``","``device_type``":"``LM``-``G710``","``device_id``":DeviceID,"``hDeviceId``":str(imei),"``city_id``":0,"``reg_city_id``":0,"``location_city_id``":0,"``order_city_id``":0,"``driver_md5``":"``","``_su``":str(su),"``ref``":"``YY``-``CY``-``A``-``GW``-``azgw``-``PC01``","``riskParam``":{"``xHllVersion``":2302,"``xHllBrand``":"``lge``","``xHllOsVersion``":29,"``xHllDeviceId``":DeviceID},"``devParam``":{"``imei``":str(imei),"``androidId``":str(imei),"``oaid``":"``","``hDeviceId":``str``(imei)}}` `inner_data_json_string` `=` `json.dumps(inner_data_dict, separators``=``(``','``,` `':'``))``encoded_data` `=` `quote(inner_data_json_string)` `post_body_dict` `=` `{``"name"``:``"user.login.getSmsCode"``,``"version"``:"``","``token``":"``","``imei``":str(imei),"``app``":"``xl``","``os``":"``XL_ANDROID``","``os_version``":"``10``","``os_bran``":"``lge``","``xl_version``":"``2.3``.``2``","``xl_revision``":XXXX,"``_t``":timestamp,"``hf_version``":"``0``","``client_type``":"``1001``","``device_type``":"``LM``-``G710``","``device_id``":DeviceID,"``hDeviceId``":str(imei),"``city_id``":0,"``reg_city_id``":0,"``location_city_id``":0,"``order_city_id``":0,"``driver_md5``":"``","``_su``":str(su),"``ref``":"``XX``-``XX``-``X``-``XX``-``XXXX``-``XXXX``","``devParam``":{"``imei``":str(imei),"``androidId``":str(imei),"``oaid``":"``","``hDeviceId``":str(imei)},"``brand``":"``lge``","``data":``str``(encoded_data)}`  `final_post_body_for_signing` `=` `json.dumps(post_body_dict, separators``=``(``','``,` `':'``))``print``(f``"构造的请求体: {final_post_body_for_signing}"``)` `sign_result` `=` `getSignature(final_post_body_for_signing)` `if` `not` `sign_result:``print``(``"程序因获取签名失败而终止"``)``return` `print``(f``"从Frida获得签名结果: {json.dumps(sign_result)}"``)` `PostRequest(final_post_body_for_signing,post_body_dict, sign_result)`  `def` `PostRequest(final_body_string, payload_dict, sign_info):``url` `=` `"https://uic-user.xiaolachuxing.com/api?name=user.login.getSmsCode&version="` `headers` `=` `{``'Host'``:` `'uic-user.xiaolachuxing.com'``,``'X-Sign-Nonce'``: sign_info.get(``'Nonce'``),``'X-Sign-Secretid'``:` `'OA643HKcfWEEdZjE9dlXSoepw69BMLVb'``,``'X-Sign-Timestamp'``:` `str``(sign_info.get(``'Timestamp'``)),``'X-Sign-Signature'``:` `str``(sign_info.get(``'Signature'``)),``'X-Hll-Net-Lib-Version'``:` `'2.2.0'``,``'X-Hll-Os'``:` `'android'``,``'X-Hll-Bd'``:` `'xl'``,``'X-Hll-Version'``: payload_dict.get(``'xl_version'``),``'X-Hll-Revision'``:` `str``(payload_dict.get(``'xl_revision'``)),``'X-Hll-Device-Id'``: payload_dict.get(``'device_id'``),``'X-Hll-Brand'``: payload_dict.get(``'brand'``),``'X-Hll-Device-Type'``: payload_dict.get(``'device_type'``),``'X-Hll-Os-Version'``:` `'29'``,``'X-Hll-User-Id'``: '',``'X-Hll-Loc'``: '',``'X-Hll-Loc-Time'``:` `'0'``,``'X-Hll-City-Id'``:` `'1017'``,``'X-Hll-Appid'``:` `'com.xiaolachuxing.user'``,``'X-Hll-Phone-Md5'``:` `'4cdc7e9f4af8749e7a5cbd2e00fc51ed'``,``'X-Hll-Sec-Ticket'``:` `'祛敏'``,``'X-Hll-Sec-Data'``: '',``'Content-Type'``:` `'application/json; charset=utf-8'``,``'Accept-Encoding'``:` `'gzip, deflate, br'``,``'User-Agent'``:` `'okhttp/4.10.0'``}`  `print``(``"============================ Headers ============================"``)``for` `key, value` `in` `headers.items():``print``(f``"{key}: {value}"``)``print``(``"============================= Body =============================="``)` `response` `=` `requests.post(url, headers``=``headers, data``=``final_body_string.encode(``'utf-8'``), timeout``=``10``)` `response.raise_for_status()` `print``(f``"请求成功,状态码: {response.status_code}"``)``print``(f``"{response.json()}"``)` `if` `__name__` `=``=` `"__main__"``:``SendSMS(xxxxxx)` |
|-|-|

| 1 | `python.exe .\RPC.py` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_7JMZ68T5DVV6EQM.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202509/974961_MGCNHSFF82ZHDH8.webp)

结束，收工！

---

# 回复

## 回复 by KanXue_NG (#2)

*2025-9-21 11:34*

其实吧 X-Sign-Signature这个参数的算法很简单的 就标准的hmac256+base64 so层调用java层的方法.

## 回复 by LQ6H (#3)

*2025-9-23 18:38*

666

## 回复 by 29o (#4)

*2025-9-23 18:50*

11

## 回复 by Wbeam (#5)

*2025-9-27 14:17*

你的帖子非常有用，感谢分享

## 回复 by kingking888 (#6)

*2025-9-27 14:31*

666

## 回复 by 机车王子 (#7)

*2025-9-28 14:57*

期待更多优质内容的分享，论坛有你更精彩！

## 回复 by Elice (#8)

*2025-9-28 15:32*

学习学习

## 回复 by zhashuyu (#9)

*2025-9-29 16:28*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 威兹曼 (#10)

*2025-9-29 16:44*

6666

## 回复 by 雅鸦歌 (#11)

*2025-9-29 17:23*

1

## 回复 by FMNS (#12)

*2025-9-29 23:54*

感谢分享

## 回复 by Imxz (#13)

*2025-9-30 15:52*

tql

## 回复 by mb_euhyowpw (#14)

*2025-10-1 08:10*

1

## 回复 by mb_qimctavn (#15)

*2025-10-1 08:56*

6

## 回复 by linix (#16)

*2025-10-1 09:18*

666

## 回复 by mb_tqevslwo (#17)

*2025-10-1 10:06*

666

## 回复 by mb_hfpmtthz (#18)

*2025-10-1 13:10*

666

## 回复 by shs (#19)

*2025-10-2 08:54*

果然是高手

## 回复 by 一栋奥特曼 (#20)

*2025-10-2 14:15*

666

## 回复 by lidongyooo (#21)

*2025-10-3 11:05*

666

## 回复 by mb_gxuzeogz (#22)

*2025-10-3 19:07*

666

## 回复 by mb_dmryhnwz (#23)

*2025-10-4 12:24*

666

## 回复 by mb_yqsvfqmf (#24)

*2025-10-5 09:28*

可以私聊吗

## 回复 by MaYil (#25)

*2025-10-5 17:22*

感谢分享

## 回复 by 魔童 (#26)

*2025-10-6 12:18*

66666666

## 回复 by 刘建龙 (#27)

*2025-10-8 15:21*

感谢分享

## 回复 by wx_宇克鴻 (#28)

*2025-10-8 17:38*

6667

## 回复 by mb_fdhbrqcn (#29)

*2025-10-9 18:19*

这个挺牛逼的
