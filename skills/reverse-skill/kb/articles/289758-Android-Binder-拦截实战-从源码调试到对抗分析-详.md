---
title: Android Binder 拦截实战：从源码调试到对抗分析（详）
url: https://bbs.kanxue.com/thread-289758.htm
tid: 289758
author: silver5563
date: '2026-01-14'
tags: [Android安全, 基础理论, 协议分析, 系统相关]
crawled_at: '2026-07-31T13:57:35+08:00'
replies: 25
---

>
> 导读：本文为[Android Binder 拦截实战：从源码调试到对抗分析](https://mp.weixin.qq.com/s/xib7-741-eOOT8YgR--7UA)的详细版，鉴于本文较长，可能会花费一些时间，建议各位读者可以先阅读原文了解大概，其次原文未有工作机会哟～
>
>
>

目录- 一. 前言
- 二. 环境准备
- 2.1 调试环境准备
- 三. 以一次android_id的获取理解binder通信
- 3.1 源码分析
- 3.2 调试
- 3.3 android_id的获取
- 3.4 应用数据在binder里的表现形式
- 四. binder拦截实践
- 4.1 binder数据的解析
- 4.2 hook ioctl
- 4.3 拦截请求及响应
- 五. binder拦截在攻防对抗上的思考
- 5.1 binder拦截对防守方的启示
- 5.2 binder拦截对攻击方的启示
- 5.2.1 内核改机
- 5.2.2 非root环境应用漏洞改机
- 5.2.3 重打包
- 5.3 其他
- 六. 总结
# 一. 前言

android binder是android系统中最为核心的跨进程通信（IPC）机制，android四大组件以及几乎所有的系统服务、框架层都通过binder进行通信。

15年前，有一篇非常硬核的binder文章: [Android Bander设计与实现 - 设计篇](https://blog.csdn.net/universus/article/details/6211589)（[备用链接](https://blog.csdn.net/u011477661/article/details/9411289)），该文章系统性地阐述了binder的设计概念，并通过与传统IPC做对比，全面的涵盖了Binder的核心机制、通信协议、内核驱动等多个层面。直到今天，这对深入理解Binder仍然有很高的参考价值。不过美中不足的是，原文虽非常详尽地描述了Binder的设计理念，但对于Binder源码的实现却涉及甚少。这就导致这篇文章的阅读门槛相对较高，往往在实际工作中碰到并解决Binder相关的问题后，回过头看，才会对该文章的理解更上一个层次。

对于本文主题将以上述文章作为背景基调（后续提到“原文”一词均指此文章），以源码调试的方式让大家对binder通信有个整体的了解。其次笔者从事移动安全相关工作，将从binder底层机制对android指纹android_id的采集进行分析/拦截实践。最后，再探讨binder拦截技术对于攻防双方的对抗起到了什么样的思路。

# 二. 环境准备

为了深入理解binder通信的机制，本文所述将对android源码进行调试，本文所选环境为：宿主机ubuntu 22.04 + aosp android 13源码 + 模拟器 + ASfP(Android Studio for Platform，Android 官方推出的为 AOSP 开发者打造的 Android Studio)

## 2.1 调试环境准备

首先可参考官方文档或网上教程下载aosp源码、设置编译目标，我这里所选为：sdk_phone_x86_64-userdebug。源码编译成功后，可通过emulator命令启动模拟器

| 12345678910111213 | `➜  aosp_android13` `source` `build``/envsetup``.sh``➜  aosp_android13 lunch sdk_phone_x86_64-userdebug``============================================``......``OUT_DIR=out``PRODUCT_SOONG_NAMESPACES=device``/generic/goldfish` `device``/generic/goldfish-opengl` `hardware``/google/camera` `hardware``/google/camera/devices/EmulatedCamera` `device``/generic/goldfish` `device``/generic/goldfish-opengl``============================================``➜  aosp_android13 emulator` `INFO    \| Android emulator version 31.3.9.0 (build_id 8748233) (CL:N``/A``)``INFO    \| Storing crashdata` `in``:` `/tmp/android-silverbullet/emu-crash``.db, detection is enabled``INFO    \| Duplicate loglines will be removed,` `if` `you wish to see each indiviudal line launch with the -log-nofilter flag.``INFO    \| Info: Warning: Ignoring XDG_SESSION_TYPE=wayland on Gnome. Use QT_QPA_PLATFORM=wayland to run on Wayland anyway. ((null):0, (null))``......` |
|-|-|

然后下载并安装ASfP https://developer.android.com/studio/platform?hl=zh-cn（目前仅支持 Linux 环境）后导入aosp源码路径

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_GRBZHDM7FBJH76D.webp)

将**Lunch target** 填入刚刚编译的目标: sdk_phone_x86_64-userdebug。**Module paths**这里我们选择frameworks

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_K8CRMWADJRCFNHT.webp)

 点击Finish，等待asfp进行同步构建后，就可以开启源码的调试了

>
> 注：如果无法调试，可在/frameworks/base/core/java/com/android/internal/os/Zygote.java
>
>
>
>
> | 1234567 | `static` `void` `applyDebuggerSystemProperty(ZygoteArguments args) {``if` `(RoSystemProperties.DEBUGGABLE) {``args.mRuntimeFlags \|= Zygote.DEBUG_ENABLE_JDWP;``}``//增加这一行，对所有应用开启调试``args.mRuntimeFlags \|= Zygote.DEBUG_ENABLE_JDWP;``}` |
> |-|-|
>
>
>

# 三. 以一次android_id的获取理解binder通信

本节以android_id为例，分析其在binder通信里是如何表现的。常见的获取方式如下:

| 1 | `Settings.Secure.getString(getContentResolver(), Settings.Secure.ANDROID_ID);` |
|-|-|

在深入代码前，先看一张全景图，概括了获取android_id时所涉及的binder通信流程。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_M89VMRK5CC2S8SN.webp)

## 3.1 源码分析

首次看上述图的话，其实还是有点复杂，流程较多，那我们先从getString的源码入手开始探索：

| 123456789101112131415161718192021 | `// frameworks/base/core/java/android/provider/Settings.java``public` `static` `String getString(ContentResolver resolver, String name) {``return` `getStringForUser(resolver, name, resolver.getUserId());``}` `@UnsupportedAppUsage``public` `String getStringForUser(ContentResolver cr, String name,` `final` `int` `userHandle) {``...``// 1. 首先获取客户端binder的引用``IContentProvider cp = mProviderHolder.getProvider(cr);``...``Bundle b;``if` `(Settings.isInSystemServer() && Binder.getCallingUid() != Process.myUid()) {``...``}` `else` `{``// 2. 远程执行方法``b = cp.call(cr.getAttributionSource(),``mProviderHolder.mUri.getAuthority(), mCallGetCommand, name, args);``}` `}` |
|-|-|

首先通过getProvider方法获取了IContentProvider的对象，在首次调用时，主要通过ActivityManager.getService().getContentProvider()获取

| 1234567891011121314151617181920212223242526272829303132333435 | `// frameworks/base/core/java/android/app/ActivityThread.java``@UnsupportedAppUsage``public` `final` `IContentProvider acquireProvider(``Context c, String auth,` `int` `userId,` `boolean` `stable) {``// 获取缓存``final` `IContentProvider provider = acquireExistingProvider(c, auth, userId, stable);``if` `(provider !=` `null``) {``return` `provider;``}``......``try` `{``synchronized` `(key) {``// 首次获取！``holder = ActivityManager.getService().getContentProvider(``getApplicationThread(), c.getOpPackageName(), auth, userId, stable);``// 存入缓存``......` `return` `holder.provider;``}` `// frameworks/base/core/java/android/app/ActivityManager.java``public` `static` `IActivityManager getService() {``return` `IActivityManagerSingleton.get();``}``private` `static` `final` `Singleton<IActivityManager> IActivityManagerSingleton =``new` `Singleton<IActivityManager>() {``@Override``protected` `IActivityManager create() {``// 向ServiceManager里查询名为"activity"binder实体的引用``final` `IBinder b = ServiceManager.getService(Context.ACTIVITY_SERVICE);` `// activity``final` `IActivityManager am = IActivityManager.Stub.asInterface(b);``return` `am;``}``};` |
|-|-|

在第1步里，我们便遇到了首次的binder通信，**ServiceManager.getService("activity");**
ServiceManager是Android Binder中的服务注册/管理中心，每个系统服务启动时都会向ServiceManager注册一个字符串标识符（服务名）。每一个进程都可以通过预定义的服务名，去查询对应的服务对象。比如"package"对应PackageManagerService，"input_method"对应InputMethodManagerService等等。

在这里通过"activity"这个服务名，去查询并返回持有AMS服务（ActivityManagerService）在客户端的binder代理对象（也可称为binder引用），可参考原文**3.3 Client获得实名Binder的引用**所述。当客户端拿到引用后便可与运行在系统服务进程中的真实服务进行IPC通信，其后的 **getContentProvider(...)** 方法就是如此。

| 1234567 | `// frameworks/base/core/java/android/app/IActivityManager.aidl``interface` `IActivityManager {``...``ContentProviderHolder getContentProvider(in IApplicationThread caller, in String callingPackage,``in String name,` `int` `userId,` `boolean` `stable);``...``}` |
|-|-|

该方法定义在后缀名为aidl的文件中，对android开发了解的小伙伴可能比较清楚，哦！这就是一个在Binder通信中规定的接口格式嘛。确实如此，AIDL（Android接口定义语言）的作用就是为Binder通信定义双方都能理解的“通话协议”

系统在编译时会根据这个aidl文件**自动生成**对应的java接口，其中最关键的是两个内部类：**Stub**—代表服务端的抽象层，**Proxy**—代表客户端的代理类。

简单说，AIDL定义了一套“通话规则”——规定了双方通信的方法签名、参数、返回值。

| 1234567891011121314151617181920 | `// 编译后自动生成的骨架代码``public` `interface` `IActivityManager` `extends` `android.os.IInterface {``// Stub：服务端的抽象基类``public` `static` `abstract` `class` `Stub` `extends` `android.os.Binder` `implements` `IActivityManager {``// 实现onTransact()，按code将请求分发给具体方法``}` `// Proxy：客户端的代理实现``private` `static` `class` `Proxy` `implements` `IActivityManager {``private` `android.os.IBinder mRemote;` `@Override``public` `ContentProviderHolder getContentProvider(...) {``// 1. 将参数打包成Parcel``// 2. 通过mRemote.transact()发送``// 3. 读取返回的Parcel并解包``}``}``}` |
|-|-|

当定义了aidl文件后，只需要编译代码，编译器就会自动生成相应的客户端和服务端的通信代码。因此真正的实现，在编译后的文件里。所以接下来，我们进入调试。

## 3.2 调试

接下来，我们要进行多进程的调试环节，在第二节中我们已经准备好了源码调试环境，因此我们可以自己写一个demo，比如写一个按钮点击触发android_id的获取，在app打开且按钮触发android_id之前，使用asfp分别对两个进程（app客户端进程，系统服务进程system_server）的断点调试，在工具栏Run -> Attach Android Debugger To，选择进程Attach（framework的native进程调试需要root权限，使用adb root命令即可）

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_858ZZMBR7WGUA9H.webp)

刚刚分析到，客户端持有了AMS服务的binder引用，并调用getContentProvider函数获取ContentProviderHolder，但该函数调用时机非常早，因此我们可以使用命令将进程启动并挂起

| 1 | `adb shell am start -D -n 包名/类名` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_AN537DZZ72MAYZT.webp)

此时应用进程被挂起，并等待调试器附加，我们必须在源码位置处先下断点，否则调试器挂上后会自动运行，比如在上述所说ActivityManager.getService().getContentProvider()位置断点，然后我们打开进程调试列表，对demo app应用进行attach

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_73H4M26VZV6TJ8W.webp)

attach后就会断点到上述位置

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_A5YHZHSEZA3QKFY.webp)

单步执行进入getContentProvider内部

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_7QQAP6EQS2JZSA4.webp)

可以发现最终通过mRemote.transact()方法进行数据传输。到这里我们需要先了解binder通信在上层应用中的体现

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_YZ226J42KD75DEP.webp)

简单来说，就是每次发生binder通信时，客户端通过transact()方法**发送客户端请求数据**并**接受服务端响应数据**，服务端通过onTransact()方法**接收客户端请求数据**并**返回服务端回复数据**，其中**transact()运行在客户端进程**，**onTransact()运行在服务端进程**，分别运行在两个进程里的方法具有相同的参数：

| 123456 | `// frameworks/base/core/java/android/os/Binder.java``protected` `boolean` `onTransact(``int` `code,` `@NonNull` `Parcel data,` `@Nullable` `Parcel reply,``int` `flags)` `throws` `RemoteException;` `public` `final` `boolean` `transact(``int` `code,` `@NonNull` `Parcel data,` `@Nullable` `Parcel reply,``int` `flags)` `throws` `RemoteException` |
|-|-|

- int code：代表跨进程通信的方法，如当前getContentProvider()方法；详细分析可参考原文**5.1.1 Binder在Server端的表述 – Binder实体**，**5.1.2 Binder在Client端的表述 – Binder引用**所述
- Parcel data：代表当前进程的请求数据；
- Parcel reply：代表当前进程的回复数据；
- int flags：代表当前进程传输类型，如同步，异步，是否文件传输等等

为了更直观的理解，我们在服务进程的onTransact()断点，然后运行程序

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_26HJ4TQ25C2JRBX.webp)

此时断点在服务端进程，可以发现，服务进程onTransact()方法在android.os.Parcel data里read出来的_arg0 ~ _arg4，全都是客户端进程调用transact()方法之前通过android.os.Parcel data里write进去的。也即客户端写入的参数caller对应服务端提取出的 _arg0，客户端参数callingPackage对应服务端的 _arg1等。
不过看的仔细的小伙伴可能就会提问了，在客户端进程里android.os.Parcel data首次写入的不是caller啊，而是 **_data.writeInterfaceToken(DESCRIPTOR)；** 没错，那是因为在onTransact()方法最开始便解析并校验DESCRIPTOR的一致性，如下源码所示：

| 12345678 | `// out/soong/.intermediates/frameworks/base/framework-minus-apex/android_common/gen/aidl/aidl0.srcjar!/android/app/IActivityManager.java 该文件由系统编译后自动生成``@Override` `public` `boolean` `onTransact(``int` `code, android.os.Parcel data, android.os.Parcel reply,` `int` `flags)` `throws` `android.os.RemoteException``{``java.lang.String descriptor = DESCRIPTOR;``if` `(code >= android.os.IBinder.FIRST_CALL_TRANSACTION && code <= android.os.IBinder.LAST_CALL_TRANSACTION) {``data.enforceInterface(descriptor);` `// 提取并校验通信数据里的descriptor，如果和服务端定义的DESCRIPTOR不一致，则报错数据传输错误``}``}` |
|-|-|

然后通过`this.getContentProvider(_arg0, _arg1, _arg2, _arg3, _arg4)`调用到实际处理的服务函数，最终将结果写入到android.os.Parcel reply里，并传回客户端，我们继续运行程序

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_RZU6PPQJJTU5E7S.webp)

断点回到客户端进程，并在reply里提取出服务端的响应数据，解析并返回结果。至此一次binder通信完成，简单概括如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_NTRPD56W6WV4HH6.webp)

## 3.3 android_id的获取

上述我们完成了第一步，返回的ContentProviderHolder是对IContentProvider的包装，而IContentProvider实际上是一个binder服务的引用，还记得这个引用是通过AMS进程获取的吗？而非通过ServiceManager.getService(name)获取的，因此这个引用是一个**匿名binder**的引用，可参考原文**3.4 匿名Binder**所述

| 123456 | `public` `String getStringForUser(ContentResolver cr, String name,` `final` `int` `userHandle) {``// 1. 首先获取客户端binder的引用``IContentProvider cp = mProviderHolder.getProvider(cr);``// 2. 远程执行方法``b = cp.call(cr.getAttributionSource(),mProviderHolder.mUri.getAuthority(), mCallGetCommand, name, args);``}` |
|-|-|

通过上述binder通信，我们知道当前客户端binder的引用——cp对象，所调用的call方法，实际上就是将请求数据通过binder通信传递给服务端，而真正获取android_id的方法会在服务端执行，并将结果写回客户端。我们继续调试，巩固上一小节所说的binder通信

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_FDAXDFJ63PTNUVT.webp)

进入客户端的代理，源码位置`frameworks/base/core/java/android/content/ContentProviderNative.java`

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_AXGAB4PT7ZSXBX8.webp)

接下来我们需要找到**服务进程里onTransact()** 的代码位置并下断点，一般来说，可以通过code(方法名)来查找c/s双方的位置，比如这里的code是IContentProvider.CALL_TRANSACTION（21）

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_3J3TVBJEVNRHEZ2.webp)

然后我们下断点，运行程序，会断到服务端进程，并且本次请求的参数`attributionSource, authority, method,stringArg, extras`也都可以接受到

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_TPNE7DJYQM6F5U8.webp)

然后调用到服务端call方法

| 12345678910111213 | `// frameworks/base/core/java/android/content/ContentProvider.java``public` `abstract` `class` `ContentProvider` `implements` `ContentInterface, ComponentCallbacks2 {``...``class` `Transport` `extends` `ContentProviderNative {``@Override``public` `Bundle call(``@NonNull` `AttributionSource attributionSource, String authority,``String method,` `@Nullable` `String arg,` `@Nullable` `Bundle extras) {``...``// 分发到不同业务的call``return` `mInterface.call(authority, method, arg, extras);``}``}``}` |
|-|-|

最终会调用到SettingsProvider.java里获取android_id的值，并返回到bundle结构里

| 123456789101112131415 | `// frameworks/base/packages/SettingsProvider/src/com/android/providers/settings/SettingsProvider.java``public` `class` `SettingsProvider` `extends` `ContentProvider {``@Override``public` `Bundle call(String method, String name, Bundle args) {``final` `int` `requestingUserId = getRequestingUserId(args);``switch` `(method) {``// 请求传进来的GET_secure``case` `Settings.CALL_METHOD_GET_SECURE: {``Setting setting = getSecureSetting(name, requestingUserId);``// 返回结构``return` `packageValueForCallResult(setting, isTrackingGeneration(args));``}``}``}``}` |
|-|-|

reply里写入传回客户端的数据
 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_GKQJ9XZK2NRUQ3K.webp)

此时断点回客户端进程，查看其接收的数据

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_9XKB2Z7X74V3ADC.webp)

最终从bundle里提取android_id加入缓存并返回

| 12345678910111213 | `public` `String getStringForUser(ContentResolver cr, String name,` `final` `int` `userHandle) {``// 1. 首先获取客户端binder的引用``IContentProvider cp = mProviderHolder.getProvider(cr);``// 2. 远程执行方法``b = cp.call(cr.getAttributionSource(),mProviderHolder.mUri.getAuthority(), mCallGetCommand, name, args);``if` `(b !=` `null``) {``// 获取到android_id``String value = b.getString(Settings.NameValueTable.VALUE);``// 将value加入缓存，防止多次获取产生多次binder通信``...``return` `value;``}``}` |
|-|-|

## 3.4 应用数据在binder里的表现形式

上面我们完整的跟踪了java层获取android_id在binder通信中的流转，但如果我们想知道binder数据是怎样的，那么我们必须深入到native层。在java层中我们知道**数据的请求**和**数据的回复**都是通过Parcel来传递的，但是java层的parcel只是native层的一个封装，所有对parcel数据进行的操作都是在native层进行的。关键的入口点从transact()方法开始，我们将进入native层！

回顾一下transact()代码位置:

| 123456789101112131415161718192021222324252627282930 | `// frameworks/base/core/java/android/content/ContentProviderNative.java``final` `class` `ContentProviderProxy` `implements` `IContentProvider``{``@Override``public` `Bundle call(``@NonNull` `AttributionSource attributionSource, String authority,``String method, String request, Bundle extras)` `throws` `RemoteException {``Parcel data = Parcel.obtain();``Parcel reply = Parcel.obtain();``try` `{``// descriptor: "android.content.IContentProvider"``data.writeInterfaceToken(IContentProvider.descriptor);` `attributionSource.writeToParcel(data,` `0``);` `// 将attributionSource内容序列化并写入到 Parcel 对象 data``data.writeString(authority);` `// "settings"``data.writeString(method);` `// "GET_secure"``data.writeString(request);` `// request: "android_id"``data.writeBundle(extras);` `// Bundle[{_track_generation=null}]` `// 远程执行方法, IContentProvider.CALL_TRANSACTION = 21``mRemote.transact(IContentProvider.CALL_TRANSACTION, data, reply,` `0``);` `DatabaseUtils.readExceptionFromParcel(reply);``Bundle bundle = reply.readBundle();``return` `bundle;``}` `finally` `{``data.recycle();``reply.recycle();``}``}``}` |
|-|-|

深入mRemote.transact()源码如下：

| 1234567891011121314151617181920212223242526272829303132333435363738394041 | `// frameworks/base/core/java/android/os/BinderProxy.java``public` `boolean transact(``int` `code, Parcel data, Parcel reply,` `int` `flags) throws RemoteException {``......``try` `{``// 调用到 framework/base/core/jni/android_util_Binder.cpp``final boolean result = transactNative(code, data, reply, flags);``// binder 传输完成``if` `(reply != null && !warnOnBlocking) {``reply.addFlags(Parcel.FLAG_IS_REPLY_FROM_BLOCKING_ALLOWED_OBJECT);``}``return` `result;``} finally {``......``}``}` `// frameworks/base/core/jni/android_util_Binder.cpp``static` `jboolean android_os_BinderProxy_transact(JNIEnv* env, jobject obj,``jint code, jobject dataObj, jobject replyObj, jint flags)` `// throws RemoteException``{``if` `(dataObj == NULL) {``jniThrowNullPointerException(env, NULL);``return` `JNI_FALSE;``}``// java层parcel转c++层``Parcel* data = parcelForJavaObject(env, dataObj);``if` `(data == NULL) {``return` `JNI_FALSE;``}``Parcel* reply = parcelForJavaObject(env, replyObj);``if` `(reply == NULL && replyObj != NULL) {``return` `JNI_FALSE;``}``// target->getInterfaceDescriptor(): (const android::String16)  (mString = u"android.content.IContentProvider")``IBinder* target = getBPNativeData(env, obj)->mObject.get();``......``// 进入native层BpBinder的transact方法``status_t err = target->transact(code, *data, reply, flags);``//if (reply) printf("Transact from Java code to %p received: ", target); reply->print();``......``}` |
|-|-|

继续往下走

| 123456789101112131415 | `// frameworks/native/libs/binder/BpBinder.cpp``status_t BpBinder::transact(``uint32_t code,` `const` `Parcel& data, Parcel* reply, uint32_t flags)``{``......``status_t status;``if` `(CC_UNLIKELY(isRpcBinder())) {``status = rpcSession()->transact(sp<IBinder>::fromExisting(``this``), code, data, reply,``flags);``}` `else` `{``// 进入这里``status = IPCThreadState::self()->transact(binderHandle(), code, data, reply, flags);``}` `......` `}` |
|-|-|

最终会调用到IPCThreadState::self()->transact()方法。IPCThreadState是binder通信中用户空间里最为重要的一个类，他代表着一个线程的实例，负责跟内核里的binder驱动进行频繁的数据交互，这也是我们在native层重点分析的对象。

| 123456789101112131415 | `// frameworks/native/libs/binder/IPCThreadState.cpp``status_t IPCThreadState::transact(int32_t handle, uint32_t code,` `const` `Parcel& data, Parcel* reply,``uint32_t flags) {``// 进行binder数据的封装``err = writeTransactionData(BC_TRANSACTION, flags, handle, code, data, nullptr);``......``if` `(reply) {``// 跟binder驱动进行交互``err = waitForResponse(reply);``}` `else` `{``Parcel fakeReply;``err = waitForResponse(&fakeReply);``}``......``}` |
|-|-|

IPCThreadState::transact()方法里，有两步操作，第一步通过**writeTransactionData**将我们的请求数据封装成binder通信时的数据格式，因为我们在上层执行远程函数调用时，如当前的call函数，只需要将请求参数构造好即可，并不关心底层是如何将数据发送出去的，但是当我们深入binder通信时，就必须了解其binder自己的通信协议以及数据交互。

binder通信在用户空间与内核空间的交互，主要通过**ioctl**这个系统调用，其Binder协议基本格式为，命令1+数据1（命令2 + 数据2），其中命令1主要是最外层给ioctl使用，用于标识本次通信的类型，通常对于读写操作来说命令为**BINDER_WRITE_READ**这也是我们最为关心的通信类型，其定义如下，可参考**原文4 Binder协议**

| 123456789 | `// bionic/libc/kernel/uapi/linux/android/binder.h``#define BINDER_WRITE_READ _IOWR('b', 1, struct binder_write_read)``#define BINDER_SET_IDLE_TIMEOUT _IOW('b', 3, __s64)``#define BINDER_SET_MAX_THREADS _IOW('b', 5, __u32)``#define BINDER_SET_IDLE_PRIORITY _IOW('b', 6, __s32)``#define BINDER_SET_CONTEXT_MGR _IOW('b', 7, __s32)``#define BINDER_THREAD_EXIT _IOW('b', 8, __s32)``#define BINDER_VERSION _IOWR('b', 9, struct binder_version)``...` |
|-|-|

数据1的格式同样也是（命令+数据），比如上述writeTransactionData方法的第一个参数**BC_TRANSACTION**，这个命令非常重要，而且同样重要的命令还有3个，分别是BC_REPLY，BR_TRANSACTION，BR_REPLY。

我们必须要深刻理解这4个命令的含义，才能理解binder通信的机制，所以我们在这里先把其含义交代清楚。在binder协议里，首先我们要知道，以BC_ 开头的，代表用户空间向内核空间写入数据；以 BR_ 开头的，代表从内核空间向用户空间写入数据；

- BC_TRANSACTION：Client -> Kernel。我要发送请求！
- BR_TRANSACTION：Kernel -> Server。Server，你有新请求！
- BC_REPLY：Server -> Kernel。这是我的处理结果！
- BR_REPLY：Kernel -> Client。Client，这是你的返回值！

为了更清晰的理解，我们还是继续调试分析，断点到writeTransactionData处，看看用户层的数据如何封装成binder通信格式

| 1234567891011121314151617181920212223242526272829303132333435 | `status_t IPCThreadState::writeTransactionData(int32_t cmd, uint32_t binderFlags, int32_t handle,``uint32_t code,` `const` `Parcel& data,``status_t* statusBuffer) {``binder_transaction_data tr;` `tr.target.ptr = 0;` `/* Don't pass uninitialized stack data to a remote process */``tr.target.handle = handle;``tr.code = code;``tr.flags = binderFlags;``tr.cookie = 0;``tr.sender_pid = 0;``tr.sender_euid = 0;` `const` `status_t err = data.errorCheck();``if` `(err == NO_ERROR) {``tr.data_size = data.ipcDataSize();``tr.data.ptr.buffer = data.ipcData();``tr.offsets_size = data.ipcObjectsCount() *` `sizeof``(binder_size_t);``tr.data.ptr.offsets = data.ipcObjects();``}` `else` `if` `(statusBuffer) {``tr.flags \|= TF_STATUS_CODE;``*statusBuffer = err;``tr.data_size =` `sizeof``(status_t);``tr.data.ptr.buffer =` `reinterpret_cast``<``uintptr_t``>(statusBuffer);``tr.offsets_size = 0;``tr.data.ptr.offsets = 0;``}` `else` `{``return` `(mLastError = err);``}``// 将命令（BC_TRANSACTION） + 数据（tr），写入mOut，后续会发送给内核的binder驱动``mOut.writeInt32(cmd);``mOut.write(&tr,` `sizeof``(tr));` `return` `NO_ERROR;``}` |
|-|-|

上述源码可以看到，writeTransactionData主要就是进行数据赋值，将client请求数据的parcel，赋值给binder_transaction_data的结构，这个结构在binder通信中也是极为重要！详细可以参考原文**4.3 struct binder_transaction_data：收发数据包结构**。然后将命令（BC_TRANSACTION） + 数据（tr），写入mOut，后续会发送给内核的binder驱动，这里我们可以用lldb查看当前结构：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_GEEWV9P6FC69U3T.webp)

可以看到当前的data_size数据大小是308字节，实际的请求数据内容在tr.data.ptr.buf指针内，打印查看如下：

| 123456789101112131415161718192021 | `(lldb) x -c308` `tr``.data.ptr.buffer``0x77c90742d240: 04 00 00 c2 ff ff ff ff 54 53 59 53 20 00 00 00  ........TSYS ...``0x77c90742d250: 61 00 6e 00 64 00 72 00 6f 00 69 00 64 00 2e 00  a.n.d.r.o.i.d...``0x77c90742d260: 63 00 6f 00 6e 00 74 00 65 00 6e 00 74 00 2e 00  c.o.n.t.e.n.t...``0x77c90742d270: 49 00 43 00 6f 00 6e 00 74 00 65 00 6e 00 74 00  I.C.o.n.t.e.n.t.``0x77c90742d280: 50 00 72 00 6f 00 76 00 69 00 64 00 65 00 72 00  P.r.o.``v``.i.d.e.r.``0x77c90742d290: 00 00 00 00 58 00 00 00 ff ff ff ff 89 27 00 00  ....X........'..``0x77c90742d2a0: 0f 00 00 00 63 00 6f 00 6d 00 2e 00 66 00 61 00  ....c.o.m...f.a.``0x77c90742d2b0: 6b 00 65 00 2e 00 62 00 69 00 6e 00 64 00 65 00  k.e...b.i.n.d.e.``0x77c90742d2c0: 72 00 00 00 ff ff ff ff 85 2a 62 73 13 01 00 00  r........*bs....``0x77c90742d2d0: e0 c3 7a 47 c8 77 00 00 d0 f9 45 77 c8 77 00 00  ..zG.w....Ew.w..``0x77c90742d2e0: 0c 00 00 00 00 00 00 00 00 00 00 00 08 00 00 00  ................``0x77c90742d2f0: 73 00 65 00 74 00 74 00 69 00 6e 00 67 00 73 00  s.e.t.t.i.n.g.s.``0x77c90742d300: 00 00 00 00 0a 00 00 00 47 00 45 00 54 00 5f 00  ........G.E.T._.``0x77c90742d310: 73 00 65 00 63 00 75 00 72 00 65 00 00 00 00 00  s.e.c.u.r.e.....``0x77c90742d320: 0a 00 00 00 61 00 6e 00 64 00 72 00 6f 00 69 00  ....a.n.d.r.o.i.``0x77c90742d330: 64 00 5f 00 69 00 64 00 00 00 00 00 30 00 00 00  d._.i.d.....0...``0x77c90742d340: 42 4e 44 4c 01 00 00 00 11 00 00 00 5f 00 74 00  BNDL........_.t.``0x77c90742d350: 72 00 61 00 63 00 6b 00 5f 00 67 00 65 00 6e 00  r.a.c.k._.g.e.n.``0x77c90742d360: 65 00 72 00 61 00 74 00 69 00 6f 00 6e 00 00 00  e.r.a.t.i.o.n...``0x77c90742d370: ff ff ff ff                                      ....` |
|-|-|

这份传输的数据正是我们在call方法里，通过parcel data写入后序列化的原始数据

| 123456 | `data.writeInterfaceToken(IContentProvider.descriptor);``// descriptor: "android.content.IContentProvider"``attributionSource.writeToParcel(data,` `0``);``// 将 attributionSource 对象的内容序列化并写入到 Parcel 对象 data``data.writeString(authority);` `// "settings"``data.writeString(method);` `// "GET_secure"``data.writeString(request);` `// request: "android_id"``data.writeBundle(extras);` `// Bundle[{_track_generation=null}]` |
|-|-|

数据封装之后，就要进行传输，我们继续往下走到waitForResponse方法

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_GFYKM33ME2JC577.webp)

talkWithDriver()方法，源码简化如下，就是再次封装一层数据结构**binder_write_read**，作为ioctl的第三个参数传递到内核，

| 12345678910111213141516 | `status_t IPCThreadState::talkWithDriver(``bool` `doReceive) {``...``binder_write_read bwr;``bwr.write_size = outAvail;``bwr.write_buffer = (``uintptr_t``)mOut.data();``...``do` `{``#if defined(__ANDROID__)``// ioctl最终走到系统调用,进入内核执行``if` `(ioctl(mProcess->mDriverFD, BINDER_WRITE_READ, &bwr) >= 0)``err = NO_ERROR;``#endif``}` `while` `(err == -EINTR);``...``return` `err;``}` |
|-|-|

这个binder_write_read是一个结构体，而非上述的BINDER_WRITE_READ命令，其结构定义如下：

| 123456789101112 | `// bionic/libc/kernel/uapi/linux/android/binder.h``struct` `binder_write_read {``// 请求数据：用户空间 ----> 内核空间``binder_size_t        write_size;` `/* bytes to write， 进程用户态地址空间传递到内核数据的大小*/``binder_size_t        write_consumed;` `/* bytes consumed by driver 进程用户态地址空间传递到内核数据中已经被内核态处理的大小*/``binder_uintptr_t     write_buffer;` `/* 进程用户态地址空间传递到内核数据的起始地址，（命令BC_开头 + 数据）*/` `// 回复数据: 内核空间  ----> 用户空间``binder_size_t        read_size;` `/* bytes to read， 总共可供给驱动写入的字节数，read_buffer可供内核使用的大小*/``binder_size_t        read_consumed;` `/* bytes consumed by driver， 内核Binder驱动发送给用户态进程的字节数*/``binder_uintptr_t     read_buffer;` `/* 内核驱动发送给进程数据buffer的起始地址，（命令BR_开头 + 数据）*/``};` |
|-|-|

该结构共占用48个字节，主要分为两个部分：

- 请求数据（Client -> Kernel）：也即write_xxx字段，用户空间向内核写入数据，其数据格式为：（命令BC_开头 + 数据）多条命令可以连续存放
- 回复数据（Kernel -> Client）：也即read_xxx字段，内核向用户空间返回数据，其数据格式为：（命令BR_开头 + 数据）多条命令可以连续存放

我们打印数据格式如下：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_ACDW4T528G96C6X.webp)

- write_size：68，代表本次通信向内核传输68字节的数据，数据为BC_TRANSACTION（0x40406300）+ struct binder_transaction_data
- write_consumed: 0，代表当前没有消费写入的数据
- read_size：256，代表期望最多读256个字节数据
- read_consumed：0，代表目前没有回复数据写入

接下来，继续执行ioctl将会进入内核，如下图所示

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_4PPQH8V76VU5KZG.webp)

简单来说如下几步：

1. 内核查找对应的服务端进程，**挂起（睡眠）** 当前客户端的调用线程
2. Kernel -> Server，将客户端请求数据重新封装（BR_NOOP + BR_TRANSACTION + struct binder_transaction_data请求数据），**唤醒**服务端进程
3. 服务端拿到并解析客户端请求数据后（如android_id的请求），将生成回复数据（android_id的具体值），并封装数据（BC_REPLY + struct binder_transaction_data回复数据）
4. 此时服务端进程也会通过IPCThreadState类里同样的方法writeTransactionData，talkWithDriver等，最终通过ioctl将封装好的回复数据写入内核
5. 再次进入内核后，内核将封装数据（BR_NOOP + BR_REPLY + 服务端的回复数据）写入客户端进程的read_buffer里，同时**唤醒**刚刚被挂起的客户端线程
6. 客户端线程被唤醒后，回到用户空间，处理服务端的回复数据

为了描述简洁，以上几步中均省略了BR_TRANSACTION_COMPLETE这个命令的使用，可参考原文**4.2 BINDER_WRITE_READ：从Binder读出数据**

回过头来，我们继续调试，客户端进程进入ioctl内核后被挂起，此时唤醒服务端，进入BR_TRANSACTION命令的处理

| 12345678910111213141516171819202122232425262728293031323334353637 | `status_t IPCThreadState::executeCommand(int32_t cmd) {``BBinder* obj;``RefBase::weakref_type* refs;``status_t result = NO_ERROR;` `switch` `((uint32_t)cmd) {``......``case` `BR_TRANSACTION: {``binder_transaction_data_secctx tr_secctx;``binder_transaction_data& tr = tr_secctx.transaction_data;` `if` `(tr.target.ptr) {``if` `(``reinterpret_cast``<RefBase::weakref_type*>(tr.target.ptr)``->attemptIncStrong(``this``)) {``// 经由binder驱动，将客户端的请求转发给服务端处理``error =` `reinterpret_cast``<BBinder*>(tr.cookie)->transact(tr.code, buffer, &reply,``tr.flags);``reinterpret_cast``<BBinder*>(tr.cookie)->decStrong(``this``);``}` `else` `{``error = UNKNOWN_TRANSACTION;``}` `if` `((tr.flags & TF_ONE_WAY) == 0) {` `// 服务端处理好结果后，将继续通过内核将回复数据转发给客户端，客户端会通过BR_REPLY接收``sendReply(reply, (tr.flags & kForwardReplyFlags));``}` `else` `{``......``}``}` `else` `{``error = the_context_object->transact(tr.code, buffer, &reply, tr.flags);``}``......``}` `break``;``}` `}` |
|-|-|

首先进入`reinterpret_cast<BBinder*>(tr.cookie)->transact(tr.code, buffer, &reply, tr.flags);`这一行

| 12345678910111213 | `// frameworks/native/libs/binder/Binder.cpp``status_t BBinder::transact(uint32_t code,` `const` `Parcel& data, Parcel* reply, uint32_t flags) {``......``switch` `(code) {``......``default``:``// android_util_Binder.cpp重载了这个方法，最终会调用到JavaBBinder处理``err = onTransact(code, data, reply, flags);``break``;``}` `return` `err;``}` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_TCS9JVCDDCAGXD9.webp)

当前处于服务进程，这里为了方便调试，修改了源码，主要是通过uid的比较，方便下断点`if (IPCThreadState::self()->getCallingUid() >= 10121) {}`；当前断点处可以看到是一个jni方法，也就是说该方法会调回java层处理

| 123456789101112131415161718192021222324 | `// frameworks/base/core/java/android/os/Binder.java``@UnsupportedAppUsage``private` `boolean` `execTransact(``int` `code,` `long` `dataObj,` `long` `replyObj,``int` `flags) {``return` `execTransactInternal(code, dataObj, replyObj, flags, callingUid);``}``private` `boolean` `execTransactInternal(``int` `code,` `long` `dataObj,` `long` `replyObj,` `int` `flags,``int` `callingUid) {``Parcel data = Parcel.obtain(dataObj);``Parcel reply = Parcel.obtain(replyObj);``......``if` `((flags & FLAG_COLLECT_NOTED_APP_OPS) !=` `0``) {``AppOpsManager.startNotedAppOpsCollection(callingUid);``try` `{``// 调用到不同的服务的onTransact的方法，这里是ContentProviderNative``res = onTransact(code, data, reply, flags);``}` `finally` `{``AppOpsManager.finishNotedAppOpsCollection();``}``}` `else` `{``res = onTransact(code, data, reply, flags);``}``......``}` |
|-|-|

最终会通过onTransact分发到不同的实现里（可参考原文**5.1.1 Binder在Server端的表述 – Binder实体**），这里就是我们之前在3.3节分析过的onTransact()方法

| 123456789101112131415161718192021222324 | `/frameworks/base/core/java/android/content/ContentProviderNative.java``@Override``public` `boolean` `onTransact(``int` `code, Parcel data, Parcel reply,` `int` `flags)``throws` `RemoteException {``...``switch` `(code) {``case` `CALL_TRANSACTION:``{``data.enforceInterface(IContentProvider.descriptor_IContentProvider);``AttributionSource attributionSource = AttributionSource.CREATOR``.createFromParcel(data);``String authority = data.readString();` `// "settings"``String method = data.readString();` `// "GET_secure"``String stringArg = data.readString();` `// request: "android_id"``Bundle extras = data.readBundle();` `// Bundle[{_track_generation=null}]``Bundle responseBundle = call(attributionSource, authority, method,``stringArg, extras);``reply.writeNoException();``// responseBundle: Bundle[{_track_generation=android.util.MemoryIntArray@a3, value=91da8ab19abf378b, _generation_index=2, _generation=5}]``reply.writeBundle(responseBundle);``return` `true``;``}``}``}` |
|-|-|

由于该方法是native层通过jni反射调用的，因此在获取到android_id的实际值后（value=91da8ab19abf378b），会继续回到native层，我们查看回复数据

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_HTZWX9NCSTVM9NS.webp)

| 123456789101112131415161718192021222324 | `(lldb) x -c364 replyMData``0x77c907449090: 00 00 00 00 60 01 00 00 42 4e 44 4c 04 00 00 00  ....`...BNDL....``0x77c9074490a0: 11 00 00 00 5f 00 74 00 72 00 61 00 63 00 6b 00  ...._.t.r.a.c.k.``0x77c9074490b0: 5f 00 67 00 65 00 6e 00 65 00 72 00 61 00 74 00  _.g.e.n.e.r.a.t.``0x77c9074490c0: 69 00 6f 00 6e 00 00 00 04 00 00 00 9c 00 00 00  i.o.n...........``0x77c9074490d0: 1b 00 00 00 61 00 6e 00 64 00 72 00 6f 00 69 00  ....a.n.d.r.o.i.``0x77c9074490e0: 64 00 2e 00 75 00 74 00 69 00 6c 00 2e 00 4d 00  d...u.t.i.l...M.``0x77c9074490f0: 65 00 6d 00 6f 00 72 00 79 00 49 00 6e 00 74 00  e.m.o.r.y.I.n.t.``0x77c907449100: 41 00 72 00 72 00 61 00 79 00 00 00 1f 00 00 00  A.r.r.a.y.......``0x77c907449110: 61 00 6e 00 64 00 72 00 6f 00 69 00 64 00 2e 00  a.n.d.r.o.i.d...``0x77c907449120: 6f 00 73 00 2e 00 50 00 61 00 72 00 63 00 65 00  o.s...P.a.r.c.e.``0x77c907449130: 6c 00 46 00 69 00 6c 00 65 00 44 00 65 00 73 00  l.F.i.l.e.D.e.s.``0x77c907449140: 63 00 72 00 69 00 70 00 74 00 6f 00 72 00 00 00  c.r.i.p.t.o.r...``0x77c907449150: 00 00 00 00 85 2a 64 66 7f 01 00 00 fe 01 00 00  .....*``df``........``0x77c907449160: 00 00 00 00 01 00 00 00 00 00 00 00 05 00 00 00  ................``0x77c907449170: 76 00 61 00 6c 00 75 00 65 00 00 00 00 00 00 00` `v``.a.l.u.e.......``0x77c907449180: 10 00 00 00 39 00 31 00 64 00 61 00 38 00 61 00  ....9.1.d.a.8.a.``0x77c907449190: 62 00 31 00 39 00 61 00 62 00 66 00 33 00 37 00  b.1.9.a.b.f.3.7.``0x77c9074491a0: 38 00 62 00 00 00 00 00 11 00 00 00 5f 00 67 00  8.b........._.g.``0x77c9074491b0: 65 00 6e 00 65 00 72 00 61 00 74 00 69 00 6f 00  e.n.e.r.a.t.i.o.``0x77c9074491c0: 6e 00 5f 00 69 00 6e 00 64 00 65 00 78 00 00 00  n._.i.n.d.e.x...``0x77c9074491d0: 01 00 00 00 02 00 00 00 0b 00 00 00 5f 00 67 00  ............_.g.``0x77c9074491e0: 65 00 6e 00 65 00 72 00 61 00 74 00 69 00 6f 00  e.n.e.r.a.t.i.o.``0x77c9074491f0: 6e 00 00 00 01 00 00 00 0d 00 00 00              n...........` |
|-|-|

这份回复数据将会在服务进程再次通过ioctl，以（BC_REPLY + struct binder_transaction_data）的方式写入内核

| 123456789 | `// frameworks/native/libs/binder/IPCThreadState.cpp``status_t IPCThreadState::sendReply(``const` `Parcel& reply, uint32_t flags) {``status_t err;``status_t statusBuffer;``// 服务端写入 BC_REPLY + binder_transaction_data``err = writeTransactionData(BC_REPLY, flags, -1, 0, reply, &statusBuffer);``if` `(err < NO_ERROR)` `return` `err;``return` `waitForResponse(nullptr, nullptr);``}` |
|-|-|

进入内核后将唤醒客户端，并将数据转发给客户端，在BR_REPLY里进行接收，此时回到客户端进程！

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_CDTJBWMSE9HHDZ8.webp)

断点waitForResponse()在BR_REPLY命令处理的分支，查看响应数据和服务端写入的数据完全一致，后面将会把该数据传给上层使用。

到这里，我们完整的走完了binder通信中数据流转

# 四. binder拦截实践

通过上文可知，如果我们想在binder通信中，找到一个可以完美拦截client请求/server响应数据的拦截点，那么最好的地方就是ioctl函数。因此本节将基于上述对binder通信/协议的理解，通过在应用中hook ioctl函数，拦截binder数据里android_id。

首先我们要回顾binder的数据结构，哪些是外层包装数据，哪些是内层核心数据

对于binder"请求数据"的结构如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_S3PX55SP5GEQ2Y5.webp)

对于binder"回复数据"的结构如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202601/804803_YATKCPCZD5Q5EZK.webp)

由于客户端挂起(睡眠)的时机不同，回复数据里的命令可能有2种格式，但是真实数据之前一定是BR_REPLY命令

1. BR_NOOP + BR_TRANSACTION_COMPLETE + BR_REPLY + 数据
2. BR_NOOP + BR_REPLY + 数据

## 4.1 binder数据的解析

在android_id完整调试的环节中，我们已经打印出业务数据了，也即上图中的parcel，所以我们需要先对其反序列化，可以参考aosp中parcel相关的源码。我们先对上述数据进行"离线"解析

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374757677787980 | `void` `test_BC_TRANSTION() {``// BC_TRANSACTION  上述hexdump里的android_id的请求数据``const` `char``* hexString =` `"040000c2ffffffff545359532000000061006e00640072006f00690064002e0063006f006e00740065006e0074002e00490043006f006e00740065006e007400500072006f00760069006400650072000000000058000000ffffffff892700000f00000063006f006d002e00660061006b0065002e00620069006e006400650072000000ffffffff852a627313010000e0c37a47c8770000d0f94577c87700000c000000000000000000000008000000730065007400740069006e0067007300000000000a0000004700450054005f00730065006300750072006500000000000a00000061006e00640072006f00690064005f00690064000000000030000000424e444c01000000110000005f0074007200610063006b005f00670065006e00650072006100740069006f006e000000ffffffff"``;` `unsigned` `char` `buffer[1024] = {0};` `int` `result = hexStringToBytes(hexString, buffer,` `sizeof``(buffer));` `const` `char``* descriptor_IContentProvider =` `"android.content.IContentProvider"``;` `Parcel* parcel =` `new` `Parcel();``parcel->setData((``const` `uint8_t*)buffer,result);``// check descriptor_IContentProvider``String16* anInterface = parcel->enforceInterface();``if` `(parcel->checkInterface(*anInterface, String16(descriptor_IContentProvider))) {``size_t` `attr_start = parcel->dataPosition();``// 读attributionSource结构``size_t` `attr_size = read_attributionSource(parcel);``parcel->setDataPosition(attr_start+attr_size);``// authority``String16 auth16 = parcel->readString16();``std::string authority = std::string(String8(auth16).string(),String8(auth16).size());``// method``String16 method16 = parcel->readString16();``std::string method = std::string(String8(method16).string(),String8(method16).size());``// request``String16 req16 = parcel->readString16();``std::string request = std::string(String8(req16).string(),String8(req16).size());``LOGD(``"authority:%s,method:%s,request:%s"``,authority.c_str(),method.c_str(),request.c_str());` `}``return` `;``}``// log输出：authority:settings,method:GET_secure,request:android_id`  `void` `test_BR_REPLY() {``// BR_REPLY  上述hexdump里的android_id的回复数据``const` `char``* hexString =` `"0000000060010000424e444c04000000110000005f0074007200610063006b005f00670065006e00650072006100740069006f006e000000040000009c0000001b00000061006e00640072006f00690064002e007500740069006c002e004d0065006d006f007200790049006e0074004100720072006100790000001f00000061006e00640072006f00690064002e006f0073002e00500061007200630065006c00460069006c006500440065007300630072006900700074006f007200000000000000852a64667f010000fe01000000000000010000000000000005000000760061006c007500650000000000000010000000390031006400610038006100620031003900610062006600330037003800620000000000110000005f00670065006e00650072006100740069006f006e005f0069006e00640065007800000001000000020000000b0000005f00670065006e00650072006100740069006f006e000000010000000d000000"``;``unsigned` `char` `buffer[1024] = {0};` `// 存储字节数组的内存``int` `result = hexStringToBytes(hexString, buffer,` `sizeof``(buffer));` `int` `BUNDLE_MAGIC = 0x4C444E42;` `// 'B' 'N' 'D' 'L'``Parcel* parcel =` `new` `Parcel();``parcel->setData((``const` `uint8_t*)buffer,result);``parcel->readInt32();``size_t` `size = parcel->readInt32();``LOGD(``"reply parcel size: %d"``,size)``int` `bndl = parcel->readInt32();``if` `(BUNDLE_MAGIC != bndl) {``LOGE(``"parseBinderWrite reply parcel header error"``);``return``;``}``int` `mapSize = parcel->readInt32();``LOGD(``"reply parcel mapSize: %d"``,mapSize)``for` `(``int` `i = 0; i < mapSize; ++i) {``// request``String16 key16 = parcel->readString16();``std::string key = std::string(String8(key16).string(), String8(key16).size());``LOGD(``"key: %s"``,key.c_str());``int` `type = parcel->readInt32();``if` `(type == 0) {``String16 value16 = parcel->readString16();``std::string value = std::string(String8(value16).string(), String8(value16).size());``LOGD(``"value: %s"``,value.c_str());``break``;``}` `else` `if``(type == 4) {``int` `size = parcel->readInt32();``LOGD(``"skip: %d"``,size);``parcel->setDataPosition(parcel->dataPosition()+size);``}` `}``}``// log输出：``// reply parcel size: 352``// reply parcel mapSize: 4``// key: _track_generation``// skip: 156``// key: value``// value: 91da8ab19abf378b  //android_id的实际值!!!` |
|-|-|

上述代码的关键问题是，我们如何解析这份业务数据的结构呢？通常来说，可以从源码中找到答案，对于请求/响应数据分别有两个参考点：

1. mRemote.transact方法前后的数据包装

| 12345678910111213141516171819202122 | `final` `class` `ContentProviderProxy` `implements` `IContentProvider {` `public` `Bundle call(``@NonNull` `AttributionSource attributionSource, String authority,String method, String request, Bundle extras)` `throws` `RemoteException {``Parcel data = Parcel.obtain();``Parcel reply = Parcel.obtain();``try` `{``// 请求数据的写入参考点``data.writeInterfaceToken(IContentProvider.descriptor);``// 写入descriptor``attributionSource.writeToParcel(data,` `0``);` `// 写入attributionSource对象``data.writeString(authority);` `// 写入"settings"字符串``data.writeString(method);` `// 写入"GET_secure"字符串``data.writeString(request);` `// 写入"android_id"字符串``data.writeBundle(extras);` `// 写入Bundle[{_track_generation=null}]对象` `// 远程执行方法, IContentProvider.CALL_TRANSACTION = 21``mRemote.transact(IContentProvider.CALL_TRANSACTION, data, reply,` `0``);` `// 回复数据的读取参考点``DatabaseUtils.readExceptionFromParcel(reply);``Bundle bundle = reply.readBundle();``return` `bundle;``......` |
|-|-|

1. 服务端onTransact实际方法（这里是call方法）调用前后的包装

| 1234567891011121314151617181920 | `public` `boolean` `onTransact(``int` `code, Parcel data, Parcel reply,` `int` `flags)``throws` `RemoteException {``case` `CALL_TRANSACTION:``{``// 请求数据的读取参考点``data.enforceInterface(IContentProvider.descriptor_IContentProvider);` `// 读descriptor``AttributionSource attributionSource = AttributionSource.CREATOR``.createFromParcel(data);` `// 读attributionSource对象``String authority = data.readString();` `// 读"settings"字符串``String method = data.readString();` `// 读"GET_secure"字符串``String stringArg = data.readString();` `// 读"android_id"字符串``Bundle extras = data.readBundle();` `// 读Bundle[{_track_generation=null}]对象` `Bundle responseBundle = call(attributionSource, authority, method,``stringArg, extras);` `// call方法` `// 回复数据的写入参考点``reply.writeNoException();``reply.writeBundle(responseBundle);``......` |
|-|-|

只需要参考上述源码，对照着使用parcel提供的方法进行解析即可，比如源码里写个string，我就读个string，写个int，就读出个int

## 4.2 hook ioctl

对binder数据进行解析后，就可以hook ioctl拦截整个binder通信，比如我们使用dobby进行hook

| 123456789101112131415161718192021222324252627 | `typedef` `int` `(*ioctl_t)(``int` `fd, unsigned` `long` `request, ...);``ioctl_t original_ioctl = NULL;` `// 自定义的 ioctl 函数``int` `my_ioctl(``int` `fd, unsigned` `long` `request,` `void` `*arg) {``if` `(request != BINDER_WRITE_READ \|\| !arg) {``// 判断是否是读写命令: 0xc0306201``return` `original_ioctl(fd, request, arg);``}``struct` `binder_write_read* bwr = (``struct` `binder_write_read*)arg;``// 拦截请求``bool` `is = intercept_write(bwr);``int` `result = original_ioctl(fd, request, arg);``if` `(is) {``// 拦截响应``intercept_read((``struct` `binder_write_read*)arg);``}``return` `result;``}` `int` `hook_ioctl() {``void` `*handle = dlopen(``"libc.so"``, RTLD_LAZY);``original_ioctl = (ioctl_t)dlsym(handle,` `"ioctl"``);``// 使用 Dobby hook ioctl 函数``DobbyHook((``void` `*)original_ioctl, (``void` `*)my_ioctl, (``void` `**)&original_ioctl);``dlclose(handle);``return` `0;``}` |
|-|-|

## 4.3 拦截请求及响应

拦截请求和拦截响应，主要是拦截bwr里的write_buffer和read_buffer。我们知道binder协议的格式，主要是命令+数据（binder_transaction_data），因此我们首要做的就是要解析cmd命令，这一步我们可以参考用户空间的IPCThreadState.cpp和内核驱动，都有对命令解析的详细示例，我们解析如下：

| 12345678910111213141516171819202122232425262728 | `bool` `intercept_write(binder_write_read *bwr) {``bool` `is_intercept =` `false``;``uint8_t* ptr = (uint8_t*)bwr->write_buffer;``const` `void``* end = ((``const` `uint8_t*)ptr)+bwr->write_size;``while` `(ptr < end) {``if` `(ptr){``static` `const` `size_t` `N =` `sizeof``(kCommandStrings) /` `sizeof``(kCommandStrings[0]);``const` `int32_t* cmd = (``const` `int32_t*)ptr;``uint32_t code = (uint32_t)*cmd++;``size_t` `cmdIndex = code & 0xff;``switch` `(code) {``......``case` `BC_TRANSACTION:{``LOGD(``"handle_write opcode: BC_TRANSACTION %d"``,cmd)``binder_transaction_data *txn = (binder_transaction_data *)cmd;``// 将txn->data.ptr.buffer转成parcel解析，过滤descriptor(android.content.IContentProvider)，判断请求参数是否包含"android_id"，解析逻辑如4.1所示``is_intercept = handle_transact_write(txn);``break``;``}``......``}` `ptr = (uint8_t *)cmd;``}` `}``return` `is_intercept;``}` |
|-|-|

当拦截到本次binder数据请求android_id时，我们就要拦截回复数据，否则不做处理

| 12345678910111213141516171819202122 | `void` `intercept_read(binder_write_read *bwr) {``void``* ptr = (``void` `*)bwr->read_buffer;``if` `(ptr == NULL)` `return``;` `const` `void``* end = (uint8_t*)ptr + bwr->read_size;``static` `const` `size_t` `N =` `sizeof``(kReturnStrings) /` `sizeof``(kReturnStrings[0]);` `while` `(ptr < end) {``uint32_t code = *(uint32_t*)ptr;``ptr = (``char``*)ptr +` `sizeof``(uint32_t);``size_t` `cmdIndex = code & 0xff;``// 根据命令码处理不同情况``switch` `(code) {``case` `BR_REPLY:{``// 将txn->data.ptr.buffer转成parcel解析,提取出里边的k-v结构，key为"value",value即为android_id值，如上述4.1所示``binder_transaction_data *txn = (binder_transaction_data *)ptr;``handle_transact_read(txn);``}` `break``;``.......``}``}``}` |
|-|-|

至此我们也完成了回复数据的解析，其中txn->data.ptr.buffer所指向的parcel是一个用户空间的指针，所以如果我们想伪造一份假的binder数据，传回给用户层，自然也不是难事。

# 五. binder拦截在攻防对抗上的思考

随着近年来移动安全领域攻防双方的激烈对抗，从设备层面说，防守方总是要尽可能多的采集设备参数、异常环境来做多维度的风控策略；而攻击方总是要尽可能的避免防守方捕捉异常信息，因而刷机、改机等对抗手段最为流行。通过上文对android binder的理解，本节将讨论binder的拦截在攻防对抗上有什么实际的意义？

## 5.1 binder拦截对防守方的启示

对防守方来讲，设备指纹的采集以及判定指纹归因的准确率，往往是比较重要的工作内容之一。简单来说，使用你的指纹，能否有效的识别黑产？而对于设备异常检测来说，往往又是比较重要的工作之一。能否识别出用户是否改机？能否识别用户设备是否异常？能否识别出模拟点击？等等。

本文所述的binder拦截，似乎在端防上有了一点新思考。比如android_id的获取，在用户层面有多重多样的api获取方式，但归因到binder通信里，只有两种获取方式，一种是call，一种是query。那么我们能否在上层获取的同时，在底层一起拦截，比对数据一致性，从而判断是否有应用层改机的嫌疑呢？再比如oaid，drmid，network，battery等等等等，甚至屏幕的点击事件，生物探针信息，这些可都是通过binder通信的。

的确，这是一项非常具有挑战的工作。同时，在底层拦截binder数据，更要考虑不同的android版本，不同厂商是否有魔改结构等一系列的兼容操作。再其次，作为端防开发人员，在某些时候极致的安全也并不是那么重要，更多时候要兼顾业务，对于ioctl的底层拦截，一定会增加程序耗时，一定会影响启动时间，一定会造成性能瓶颈，那么做这件事的价值还会有那么高吗？

**总结：**对于防守方来说，binder拦截会很复杂，虽能一定程度提高安全性，但可玩性不高。

## 5.2 binder拦截对攻击方的启示

对攻击方来讲，我认为binder拦截技术的可玩性非常高，首先对于防守方里提出的兼容适配，在攻方这里只需要兼容某个系统或者某个品牌的手机即可，这大大的减少了开发难度，其次再提出以下几个场景仅供参考：

### 5.2.1 内核改机

传统的基于Xposed的应用层注入改机特征太多，很容易被检测；

而基于系统服务的改机，虽说应用层无法检测，但不同的系统服务有不同的hook点（甚至不同服务进程），工程上难以调度，而且同样有兼容问题，不同型号、系统版本的系统服务hook点不一致等问题。

内核改机通过hook ioctl系统调用（如基于kernelpatch）从而在内核拦截binder通信，无痕解析并替换binder数据。

相较于应用层改机，内核改机可以完全无侵入式，无需注入目标进程hook，从而减少很多注入特征的对抗。其次可以配合ecapture实现无侵入式抓包，无侵入式改机。相较于系统服务改机内核改机会有一个统一的收口，但内核同样需要考虑的更多，而且内核解析应用层数据也更加复杂。

### 5.2.2 非root环境应用漏洞改机

一方面，从系统角度看，某些系统版本上可能有root提权漏洞，因此可以配合内核hook 拦截ioctl实现binder hook

另一方面，从应用角度说，某些app可能会有应用漏洞，能够任意注入so，从而可以hook libc ioctl实现非root环境改机

### 5.2.3 重打包

可以通过重打包注入so，在底层进行拦截，如拦截PackageManageService修改包相关信息，拦截SettingsProvider修改系统设置等等。

**总结：** 对于攻击方来说，binder拦截同样很复杂，但应用场景多，且更隐蔽，可玩性更高。

## 5.3 其他

其他场景，比如隐私合规检测理论上也可用binder拦截技术，但可能并不必要

# 六. 总结

binder通信是一个非常复杂的机制，本文依托于原文《Android Bander设计与实现 - 设计篇》进行了一次binder通信的实践，但也仅停留在用户空间的binder分析并未深入内核。其次本文探讨binder拦截在攻防对抗双方上有什么应用场景，或许会有一些不同的思考。

参考文章：

1. [Android Binder 拦截实战：从源码调试到对抗分析](https://mp.weixin.qq.com/s/xib7-741-eOOT8YgR--7UA)
2. [Android Bander设计与实现 - 设计篇](https://blog.csdn.net/universus/article/details/6211589) （原本可能被吞，[备用链接](https://blog.csdn.net/u011477661/article/details/9411289)）
3. [Gityuan binder系列文章](https://gityuan.com/2015/10/31/binder-prepare/)
4. [细读《深入理解 Android 内核设计思想》系列](https://yhaolpz.github.io/a8eae25c/)
5. [Binder驱动之设备控制系列](https://bbs.kanxue.com/!%5B%5D(upload/attach/202601/804803_Y9XTER5PEYGAF2H.webp)

---

# 回复

## 回复 by 简单的简单 (#2)

*2026-1-15 02:36*

沙发

## 回复 by iBa0 (#3)

*2026-1-15 17:10*

牛逼啊

## 回复 by 随风而行aa (#4)

*2026-1-15 21:49*

写的很不错

## 回复 by huangjw (#5)

*2026-1-16 15:47*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by wx_小友 (#6)

*2026-1-28 22:38*

mark

## 回复 by MsScotch (#7)

*2026-2-2 10:23*

好文！

## 回复 by mb_yalauklc (#8)

*2026-2-15 14:04*

内核改机有项目可以学习吗

## 回复 by silver5563 (#9)

*2026-3-1 10:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_yalauklc](https://bbs.kanxue.com/user-1001535.htm)
>
>  内核改机有项目可以学习吗
>
>

没找到开源的内核改机项目，目前我这通过kernelpatch hook内核binder函数，实现一些系统服务的拦截和替换，有兴趣可以加v聊哈私发你了～

## 回复 by mb_mihutdve (#10)

*2026-3-4 21:10*

强

## 回复 by mb_mihutdve (#11)

*2026-3-4 22:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  silver5563](https://bbs.kanxue.com/user-804803.htm)
>
>  没找到开源的内核改机项目，目前我这通过kernelpatch hook内核binder函数，实现一些系统服务的拦截和替换，有兴趣可以加v聊哈私发你了～
>
>

大佬 可以给个v不

## 回复 by silver5563 (#12)

*2026-3-5 18:09*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_mihutdve](https://bbs.kanxue.com/user-965737.htm)
>
>  大佬 可以给个v不
>
>

已发～

## 回复 by mb_stdlrcgp (#13)

*2026-3-18 20:42*

666666

## 回复 by mb_xyoslnox (#14)

*2026-3-18 22:37*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  silver5563](https://bbs.kanxue.com/user-804803.htm)
>  没找到开源的内核改机项目，目前我这通过kernelpatch hook内核binder函数，实现一些系统服务的拦截和替换，有兴趣可以加v聊哈私发你了～
>

能发我一份吗？我最近也在研究相关的

## 回复 by silver5563 (#15)

*2026-3-23 11:54*

>
> [mb_xyoslnox](https://bbs.kanxue.com/user-1018487.htm)
>  能发我一份吗？我最近也在研究相关的
>

我这没成品，，就是测试可行，核心就是解析binder结构/数据，对于不同的服务可以在aosp源码里对应的解析逻辑

## 回复 by YoungBai (#16)

*2026-3-23 18:08*

感谢分享.

## 回复 by 温泉划水鱼 (#17)

*2026-4-4 17:49*

大佬求个v，我最近也在看内核改

## 回复 by mb_zcfhleoj (#18)

*2026-4-22 16:38*

感谢分享

## 回复 by 铁头葫芦娃 (#19)

*2026-6-9 11:19*

大佬能够发我一份资料吗

## 回复 by buluo533 (#20)

*2026-6-22 09:16*

学习了

## 回复 by 从黎明到衰落 (#21)

*2026-6-22 09:33*

大佬可以加个V吗，最近也想看看

## 回复 by Payne-Wu (#22)

*2026-6-22 13:30*

大佬可以加个V吗，最近也在梳理和学习这块。

## 回复 by uni7corn (#23)

*2026-6-24 11:13*

大佬你好，能加个好友v嘛。我是不正经Android开发。

## 回复 by mb_xyoslnox (#24)

*2026-7-1 13:55*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  silver5563](https://bbs.kanxue.com/user-804803.htm)
>  我这没成品，，就是测试可行，核心就是解析binder结构/数据，对于不同的服务可以在aosp源码里对应的解析逻辑
>

佬，可以加V学习一下吗

## 回复 by Da_ (#25)

*2026-7-1 15:18*

大佬 可以给个v不

## 回复 by mb_mihutdve (#26)

666
