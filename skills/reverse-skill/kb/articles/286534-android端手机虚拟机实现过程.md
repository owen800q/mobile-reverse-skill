---
title: '[原创]android端手机虚拟机实现过程'
url: https://bbs.kanxue.com/thread-286534.htm
tid: 286534
author: ovo_帮我不c
date: '2025-04-18'
tags: [Android安全, 原创, 基础理论, 系统相关, 源码框架]
crawled_at: '2026-07-31T15:54:23+08:00'
replies: 79
---

## android端手机虚拟机实现过程

以下是**VirtualAPP的执行流程图**：

 ![image](https://bbs.kanxue.com/upload/attach/202504/971248_K4M5PXG6YVP4DWK.webp)

我们通过这样的一个开源的**virtualApp**来了解一下，一个应用程序是怎么去实现在虚拟机里面运行的。

### Virtual space

首先是应用程序的下载安装。实际上，在虚拟机中运行的应用程序是下载到的虚拟机空间（virtual space）中的。

### Virtual Framework

虚拟机中的 App（比如 App1、App2）原本会直接调用系统 Framework，但是在虚拟机中的APP需要的就不同

- “以为”自己访问的是系统服务，
- 实际上却访问的是 VA 模拟的服务（Hook 之后的）。

#### **Android Framework**

**Android Framework** 是 Android 系统提供的一整套 API，它是 **系统级服务（如 AMS、PMS、LocationService）** 的接口，比如：

- `ActivityManagerService (AMS)`：管理 Activity 的启动与调度。
- `PackageManagerService (PMS)`：管理应用包的安装与信息。
- `LocationManager`：提供位置信息。
- `ClipboardManager`：剪贴板服务。

这些都属于 **系统原生的 Android Framework**，运行在系统进程（如 `system_server`）中，不是用户 App 能随意改动的。而在虚拟机中的Framework，则是自开发的可改动的Framework。

而在Virtual Framework中，需要做的事情就是让**APP觉得自己是在原生系统下执行的**，根据Android Frameword中的应用程序的执行流程，我们可以知道的是

#### 一个**应用程序的执行流程**大体是这样的：

- 点击桌面程序
- 将Activity顶上第一个设置为**暂停状态**，**等待启动的应用**
- 判断进程，先进程再程序
- 通过**Zygote开始fork()**应用程序进程了
- 执行**ActivityThread.main()**
- ActivityThread 通过 Binder 将自身的 ApplicationThread 传给 AMS，方便**AMS**通过**ActivityThread启动应用**
- **AMS** 通过 ApplicationThread.scheduleLaunchActivity() 通知**启动 Activity**
- **ActivityThread** 通过反射加载目标 **Activity 类**
- 调用 Instrumentation.callActivityOnCreate()，执行程序的OnCreate()函数

应用的真正启动是 `ActivityThread` 执行的，但整个过程是由 `AMS` 控制调度的，双方通过 Binder 建立通信桥梁。

### 虚拟 App vs 原生安装 App

| 方面 | 虚拟机中的 App（VA App） | 系统安装的 App（原生 App） |
|-|-|-|
| **安装方式** | 并未真正通过系统 PMS 安装，仅在 VA 虚拟空间中注册 | 通过系统 PMS 安装，注册了 Activity、Service 等 |
| **运行路径** | 安装路径、数据路径等都是被 **重定向/虚拟的**（如 `/data/data/com.xxx -> /data/data/io.virtual.app/space/0/...`） | 使用 Android 系统真实的 `/data/data/com.xxx` 路径 |
| **访问系统服务** | 所有访问系统服务的调用（如 Location、Clipboard）都被 VA Hook 拦截和“伪造” | 调用系统原生 `ServiceManager` 提供的服务，直接连接 `system_server` |
| **AMS / PMS 管理** | 由 VA 模拟的 AMS/PMS 进行调度（Activity 启动、Service 调用等） | 由系统的 `ActivityManagerService` 和 `PackageManagerService` 控制 |
| **权限模型** | 权限请求和判断被 VA 接管（可以伪造授予，也可以强制拦截） | 权限由 Android 系统控制，用户手动授权 |
| **多开与隔离能力** | 可以任意多开，同一 App 多个实例之间相互隔离 | 系统默认一个包名只允许一个实例，数据也无法隔离 |
| **文件/IO 控制** | VA Hook 底层文件系统访问，可实现只读/禁止/伪造/隔离等策略 | 系统文件访问直接作用于真实文件系统 |
| **运行时感知** | 可以“欺骗” App，使其以为自己运行在正常系统中（比如感知不到虚拟环境） | 真实环境，App 可以访问所有支持的设备资源 |
| **安全性控制** | 更灵活，可以模拟环境、劫持函数、限制行为 | 安全性高但开放度小，无法灵活控制运行环境 |

那么实际上在虚拟机下应用程序的执行流程也应该是这样的，但是不同的是，这里的**Server服务不是Android 原生下的framework，而是虚拟机的framework**。

而这里就应用到的是APP HOOK的主要实现了

### APP HOOK

#### Hook 的目标是 **系统服务类**，主要分两种：

##### 1. Java 层服务（运行在 system_server）

VA 会通过 **反射、代理（比如 Binder 代理）或动态注入**，替换系统服务对象。

举个例子：

- App 调用 `Context.getSystemService("location")` 拿到 `LocationManager`。
- 正常系统下，它返回的是 Binder 连接到 system_server 的服务。
- VA Hook 后返回的是它自己实现的“假 LocationManager”，比如总是返回一个虚假的地理位置。

##### 2. Binder 接口 Hook

- VA 使用类似 **“Binder IPC 劫持”** 的方式，在 Java 层模拟 AMS、PMS 等 Binder 服务。
- 这就像劫持了一条“电话线”，App 以为在和系统通信，其实是和 VA 自己通信。

细节的说一下可能出现的具体实现：

- **App 调用 `ActivityManager.startActivity()`**
- **APP Hook 中的 AMS Hook** 通过代理劫持系统服务调用（比如修改 `IActivityManager` 的 Binder）
- 它并**不真的去调用系统 AMS**，而是把调用重定向到了 VirtualApp 自己实现的 **VA Server → AMS**
- VA Server 的 AMS 执行启动流程（比如在 VirtualActivityStack 中注册一个 Activity 记录）
- 最后，伪装成系统返回正常的 `ActivityResult`，App 觉得自己“真的启动了 Activity”

而在APP HOOK拦截完成之后，VA Server就需要开始去提供对应的服务来实现拦截之后的服务请求。

所以：APP Hook 是用来“**拦截”App 调用系统服务行为**的；而 VA Server 是用来**“虚拟提供”这些服务的实现端。**

### Virtual Native

在这一层主要为了完成2个工作，**IO重定向**和**VA APP与Android系统交互**的请求修改。

#### IO重定向

比如在一些APP中，会把一些配置、缓存、数据库等文件的路径**写死**在代码里

| 12 | `new` `File(``"/data/data/com.example.app/shared_prefs/config.xml"``)``fopen(``"/data/data/com.example.app/files/config.dat"``,` `"r"``);` |
|-|-|

这种情况下的，用虚拟机打开的程序就**无法获取适配对应路径的文件和配置信息**。

所以说出现了 **VA Native**的存在的意义：

- 拦截所有 `open`, `fopen`, `access`, `stat` 等系统调用
- 判断路径是否是虚拟 App 的目标路径
- 替换为虚拟路径，到真实的程序的虚拟路径的位置

不过这里应该算得上是Native层的HOOK了。

#### JNI Native函数

以上的APP HOOK 都是基于Java层进行的，但是相应的Android 有大量的系统行为是通过 Native 实现的。这时候对应的应用程序适配就需要Native HOOK来实现

| 情况 | 举例 | 解决方法 |
|-|-|-|
| 直接访问文件 | `open`, `fopen`, `access` | hook libc |
| 直接调用系统服务 | `getuid()`, `getpid()` | hook syscall |
| 访问特殊设备 | `/dev/*`, `/proc/*` | 重定向路径 |
| ART Runtime 优化 | `libart.so` 调用 | hook libart |
| 动态链接时 resolve | `dlsym` 取函数地址 | hook linker |

这里举例的程序应用就是需要通过HOOK so层来实现分析和获取适配对应路径的文件和配置信息。

## 源码分析部分

### mirror

在虚拟机中很多的细节其实是通过HOOK，或者通过反射的操作调用实现的。比如拦截真实的AMS,PMS等服务，返回自写的各种服务。而在虚拟机框架中为了使得调用拦截等更加方便则出来对于反射等的封装。而在这里的封装就叫**mirror**

正常执行下去拦截改定位:

| 1234567891011121314151617181920212223242526 | `private` `void` `hookInstrumentation() {``try` `{``// 加载 ActivityThread 类``Class<?> activityThreadClass = Class.forName(``"android.app.ActivityThread"``);` `// 获取 'currentActivityThread' 方法``Method currentActivityThreadMethod = activityThreadClass.getDeclaredMethod(``"currentActivityThread"``);``currentActivityThreadMethod.setAccessible(``true``);` `// 调用该方法获取当前的 ActivityThread 实例``Object currentThread = currentActivityThreadMethod.invoke(``null``);` `// 获取 'mInstrumentation' 字段``Field instrumentationField = activityThreadClass.getDeclaredField(``"mInstrumentation"``);``instrumentationField.setAccessible(``true``);` `// 获取原始的 Instrumentation 实例``Instrumentation originalInstrumentation = (Instrumentation) instrumentationField.get(currentThread);` `// 创建 InstrumentationDelegate 并替换原始的 Instrumentation``InstrumentationDelegate instrumentationDelegate =` `new` `InstrumentationDelegate(originalInstrumentation);``instrumentationField.set(currentThread, instrumentationDelegate);``}` `catch` `(Exception e) {``e.printStackTrace();``}``}` |
|-|-|

mirror**拦截改定位**

| 1234 | `private` `void` `hookInstrumentation(){``Object currentThread ActivityThread.currentActivityThread.call();``Instrumentation originInstrumentation   ActivityThread.mInstrumentation.get(currentThread);``ActivityThread.mInstrumentation.set(currentThread,``new` `InstrumentationDelegate(originInstrumentation));` |
|-|-|

这里实际上就去做了对应的函数封装，从而更加快速实现的代码逻辑

### Java层 HOOK

举例**应用调用AMS执行流程**的过程来看看Java层 HOOK

Android 系统中，所有四大组件的管理都要通过系统的 **ActivityManagerService（AMS）** 完成，客户端通过 **`IActivityManager` 接口** 调用 AMS。

所以 **Hook AMS = 控制所有组件的启动流程**！得到`IActivityManager` 接口就可以**拦截执行流程**

```
Activity.startActivity(Intent)
    ↓
Instrumentation.execStartActivity(...)
    ↓
ActivityManager.getService().startActivity(...)
```

这里会走**ActivityManager.getService()** ，而在android8.0的位置

| 1234567891011121314 | `// frameworks/base/core/java/android/app/ActivityManager.java``public` `static` `IActivityManager getService() {``return` `IActivityManagerSingleton.get();``}` `// frameworks/base/core/java/android/util/Singleton.java``private` `static` `final` `Singleton<IActivityManager> IActivityManagerSingleton =``new` `Singleton<IActivityManager>() {``@Override``protected` `IActivityManager create() {``// 注意这行``return` `ActivityManagerNative.getDefault();``}``};` |
|-|-|

```
getService() 会返回 IActivityManagerSingleton.get();
```

所以在

| 12345678910111213141516 | `public` `class` `ActivityManagerStub` `extends` `MethodInvocationProxy<MethodInvocationStub<IInterface>> {``public` `ActivityManagerStub() {``// 基于 mirror 获取 AMS 的 IActivityManager 接口对象，并创建其动态代理对象``super``(``new` `MethodInvocationStub<>(ActivityManagerNative.getDefault.call()));``//这里通过反射去获取系统 IActivityManager 实例。``}`  `public` `void` `inject()` `throws` `Throwable {``if` `(BuildCompat.isOreo()) {``// Android 8.x 及以上版本``Object singleton = ActivityManager.IActivityManagerSingleton.get();``// 替换原 AMS 对象为我们的动态代理对象``Singleton.mInstance.set(singleton, getInvocationStub().getProxyInterface());``}` `else` `{``// Android 8.x 以下的实现（略）``}``}` |
|-|-|

用反射将其 `mInstance` 替换成我们刚才构造的 **代理对象**，应用对 AMS 的所有调用（比如 `startActivity()`），都会经过我们这个 **Hook 代理对象**。

| 1234567891011121314 | `// 方法 hook 实现``static` `class` `StartActivity` `extends` `MethodProxy {``@Override``public` `String getMethodName() {``return` `"startActivity"``;``}``@Override``public` `Object call(Object who, Method method, Object... args)` `throws` `Throwable {``// 可以对参数进行处理``int` `res = VActivityManager.get().startActivity(args);``return` `res;``}``}``}` |
|-|-|

在这里去调用 int res = VActivityManager.get().**startActivity(args)**; 此处直接将调用转发到 `VActivityManager` 中（**VirtualApp 的虚拟 AMS**）。

**“拦截 AMS 服务”** 的核心目的，实际上就是为了拿到 `IActivityManager` 的实例，并用我们构造的 **代理对象**去**替换掉它**。因为 Android 应用中的 **组件调度**（包括启动 Activity、Service、广播等）全都需要通过这个接口来向系统发送请求。

| 123 | `ActivityManager.getService().startActivity(...)``ActivityManager.getService().broadcastIntent(...)``ActivityManager.getService().startService(...)` |
|-|-|

这些都是 `IActivityManager` 的方法。

### native层hook

上面也已经说过了Native层HOOK的原理，这里就执行来看看 io重定向，实现修改的文件读写的路径的操作

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748 | `@SuppressLint``(``"SdCardPath"``)``private` `void` `startIOUniformer() {``ApplicationInfo info = mBoundApplication.appInfo;``int` `userId = VUserHandle.myUserId();``String wifiMacAddressFile = deviceInfo.getwifiFile(userId).getPath();` `// 重定向 WiFi 相关地址``NativeEngine.redirectDirectory(``"/sys/class/net/wlan0/address"``, wifiMacAddressFile);``NativeEngine.redirectDirectory(``"/sys/class/net/eth0/address"``, wifiMacAddressFile);``NativeEngine.redirectDirectory(``"/sys/class/net/wifi/address"``, wifiMacAddressFile);` `// 重定向 data/data 路径``NativeEngine.redirectDirectory(``"/data/data/"` `+ info.packageName, info.dataDir);``NativeEngine.redirectDirectory(``"/data/user/0/"` `+ info.packageName, info.dataDir);` `if` `(Build.VERSION.SDK_INT > Build.VERSION_CODES.N) {``// Android 7.0 以上``NativeEngine.redirectDirectory(``"/data/user_de/0/"` `+ info.packageName, info.dataDir);` `String libPath = VEnvironment.getAppLibDirectory(info.packageName).getAbsolutePath();``String userLibPath =` `new` `File(``VEnvironment.getUserSystemDirectory(userId),``info.packageName +` `"/lib"``).getAbsolutePath();` `// 重定向 native lib 路径``NativeEngine.redirectDirectory(userLibPath, libPath);``NativeEngine.redirectDirectory(``"/data/data/"` `+ info.packageName +` `"/lib/"``, libPath);``NativeEngine.redirectDirectory(``"/data/user/0/"` `+ info.packageName +` `"/lib/"``, libPath);``}` `// 虚拟存储处理``VirtualStorageManager vsManager = VirtualStorageManager.get();``String vsPath = vsManager.getVirtualStorage(info.packageName, userId);``boolean` `enable = vsManager.isVirtualStorageEnable(info.packageName, userId);` `if` `(enable && vsPath !=` `null``) {``File vsDirectory =` `new` `File(vsPath);``if` `(vsDirectory.exists() \|\| vsDirectory.mkdirs()) {``HashSet<String> mountPoints = getMountPoints();``for` `(String mountPoint : mountPoints) {``NativeEngine.redirectDirectory(mountPoint, vsPath);``}``}``}` `NativeEngine.enableIORedirect();``}` |
|-|-|

可以看到这里利用redirectDirectory函数，去重定向了对应可能读取的位置，替换成了虚拟机对应位置的内容。

| 12345678 | `//int faccessat(int dirfd,const char *pathname,int mode,int flags);``HOOK DEF(``int``,faccessat,``int` `dirfd,``const` `char` `*pathname,``int` `mode,``int` `flags){``int` `res;``const` `char` `*redirect_path relocate_path(pathname,&res);``int` `ret syscall(_NR_faccessat,dirfd,redirect_path,mode,flags);``FREE(redirect_path,pathname);``return` `ret;``}` |
|-|-|

该宏会生成一个以 `new_` 为前缀的函数，例如：

| 1 | `int` `new_faccessat(...) { ... }` |
|-|-|

- 判断是否需要重定向（如 `/data/data/com.xxx` → `/virtual/data/com.xxx`）
- 如果是，则返回新的路径；否则返回原路径`res` 用于记录是否发生了实际替换

举个例子：
 `pathname = "/data/data/com.test/files/a.txt"`
 如果这个 app 被 VA 管控了，那路径会被转向
 `redirect_path = "/data/user/0/com.va.wrapper/files/a.txt"`

从这里就对于开头的那个图片进行了总体的大致讲解，但是其中虚拟机下运行应用的很多问题以及配置环境更多的是需要在实践运用上去体现。

**参考资料：**
https://github.com/asLody/VirtualApp
https://juejin.cn/post/7028124957141893150#heading-11
https://blog.csdn.net/weixin_33816300/article/details/88772462
https://blog.csdn.net/ganyao939543405/article/details/76146760

**文章PDF**：通过网盘分享的文件：
通过网盘分享的文件：Android虚拟机原理总.pdf
链接: https://pan.baidu.com/s/1lbpLG_SbsF21yzmJSJ6HCg 提取码: chen
--来自百度网盘超级会员v4的分享

---

# 回复

## 回复 by qqsunqiang (#2)

*2025-4-19 12:31*

谢谢楼主的

## 回复 by hacker521 (#3)

*2025-4-19 13:55*

VA原理哈~

## 回复 by uni7corn (#4)

*2025-4-21 11:41*

看看

## 回复 by 西瓜帅 (#5)

*2025-4-21 16:33*

我来看你

## 回复 by Imxz (#6)

*2025-4-21 18:01*

6666666

## 回复 by wolf_lc (#7)

*2025-4-21 19:01*

111

## 回复 by Motivar (#8)

*2025-4-21 22:03*

感谢分享

## 回复 by kingking888 (#9)

*2025-4-21 23:27*

666

## 回复 by 墨穹呢 (#10)

*2025-4-22 00:22*

感谢分享

## 回复 by artake (#11)

*2025-4-22 08:52*

666

## 回复 by jdong (#12)

*2025-4-22 09:46*

666

## 回复 by lookaside (#13)

*2025-4-22 11:18*

666

## 回复 by mb_kylehnha (#14)

*2025-4-22 11:51*

66666666

## 回复 by mb_crhelucl (#15)

*2025-4-22 16:50*

66666666

## 回复 by wx_插曲 (#16)

*2025-4-22 16:56*

6666

## 回复 by jiyuren (#17)

*2025-4-22 17:32*

66666666

## 回复 by 啊你好哇123 (#18)

*2025-4-23 00:35*

学习学习

## 回复 by 樊辉 (#19)

*2025-4-23 08:37*

66666

## 回复 by ONewTach (#20)

*2025-4-23 08:45*

666

## 回复 by 我是小奥 (#21)

*2025-4-23 08:54*

666

## 回复 by 学编程 (#22)

*2025-4-23 09:02*

666

## 回复 by 呼吸24K纯氧 (#23)

*2025-4-23 09:21*

看看

## 回复 by Tokameine (#24)

*2025-4-23 16:23*

这篇文章似乎来自52pojie，原链接https://www.52pojie.cn/thread-2025427-1-1.html，作者是同一个人么？感觉这复制粘贴似乎格式全都是混乱的，如果是原作者的话直接贴md都不至于这样吧？

## 回复 by 末日大哥 (#25)

*2025-4-23 17:20*

666

## 回复 by 哈。 (#26)

*2025-4-23 18:44*

666

## 回复 by ovo_帮我不c (#27)

*2025-4-25 09:23*

>
> [Tokameine](https://bbs.kanxue.com/user-924548.htm)
>
>  这篇文章似乎来自52pojie，原链接 ...
>
>

## 回复 by ovo_帮我不c (#28)

*2025-4-25 09:25*

>
> [Tokameine](https://bbs.kanxue.com/user-924548.htm)
>
>  这篇文章似乎来自52pojie，原链接https://www.52pojie.cn/thread-2025427-1-1.html，作者是同一个人么？感觉这复制粘贴似乎格式全都是混乱的，如果是原作者的 ...
>
>

是原作者，看雪和52 ID不同

## 回复 by ovo_帮我不c (#29)

*2025-4-25 09:28*

是原作者 52 ID：chenchenchen777  看雪ID 换不了了

## 回复 by kiwimi (#30)

*2025-4-25 09:41*

mark

## 回复 by supercuglong (#31)

*2025-4-25 14:43*

666666666666666

## 回复 by mb_cirblqqg (#32)

*2025-4-30 15:54*

有大佬可以帮忙追回被骗的钱吗，差不多被骗了七万多，报酬好说

## 回复 by mb_cirblqqg (#33)

*2025-4-30 15:56*

有大佬可以帮忙追回被骗的钱吗，差不多被骗了七万多，报酬好说

## 回复 by 边缘 (#34)

*2025-4-30 19:13*

66666

## 回复 by Vengeance (#35)

*2025-4-30 23:17*

666

## 回复 by mb_ebiwunmj (#36)

*2025-6-1 20:47*

66
6

## 回复 by mb_kgfqphsx (#37)

*2025-6-1 21:56*

6

## 回复 by ydscience (#38)

*2025-6-18 11:56*

666

## 回复 by mb_ktlyowcf (#39)

*2025-6-20 02:05*

666

## 回复 by mb_qwfbhbok (#40)

*2025-7-2 18:23*

6666666

## 回复 by A0x01 (#41)

*2025-7-2 19:25*

666666

## 回复 by taoying (#42)

*2025-7-3 18:12*

1

## 回复 by troops (#43)

*2025-7-15 22:01*

ddd

## 回复 by Asailor (#44)

*2025-7-16 08:55*

666

## 回复 by onlythis (#45)

*2025-7-24 16:23*

666

## 回复 by mb_cbgtaveo (#46)

*2025-7-24 16:30*

6666

## 回复 by 小白熊 (#47)

*2025-8-8 12:24*

666

## 回复 by guijingwen (#48)

*2025-8-8 13:42*

66

## 回复 by 飆汗吉米 (#49)

*2025-8-17 03:50*

6666

## 回复 by mb_tqskihwz (#50)

*2025-8-19 23:30*

666

## 回复 by mb_oksdecri (#51)

*2025-8-27 09:40*

666

## 回复 by huangjw (#52)

*2025-8-28 10:27*

好文章

## 回复 by JWPL (#53)

*2025-8-28 13:46*

666

## 回复 by 无视红绿灯 (#54)

*2025-8-28 14:16*

6666

## 回复 by Ankeys (#55)

*2025-8-28 14:36*

666

## 回复 by lamboo (#56)

*2025-9-12 18:19*

6666

## 回复 by xxjj678 (#57)

*2025-9-12 23:13*

666

## 回复 by mb_jnmxfjku (#58)

*2025-9-13 18:09*

666

## 回复 by XCicada (#59)

*2025-9-13 18:23*

学习

## 回复 by mb_pnyyaazf (#60)

*2025-9-18 12:52*

6

## 回复 by 随风而行aa (#61)

*2025-9-21 22:53*

看看

## 回复 by 学生的 (#62)

*2025-9-22 03:05*

期待更多优质内容的分享，论坛有你更精彩！

## 回复 by wx_coddvccwyh (#63)

*2025-12-3 01:24*

6666

## 回复 by 勒LI (#64)

*2025-12-3 16:57*

666

## 回复 by 有的是钱啊 (#65)

*2025-12-3 17:27*

111

## 回复 by mb_irhdtnzm (#66)

*2025-12-4 07:56*

111

## 回复 by darkya (#67)

*2025-12-4 14:19*

看看大佬的思路

## 回复 by zylyy (#68)

*2025-12-4 14:27*

666

## 回复 by GEKEZYX (#69)

*2025-12-5 09:49*

666

## 回复 by Harpyja (#70)

*2026-1-2 09:36*

666

## 回复 by Gryffindoss (#71)

*2026-1-23 15:28*

666666666

## 回复 by git_93836chaos-leo (#72)

*2026-3-3 17:28*

666

## 回复 by pan_634488 (#73)

*2026-3-25 13:22*

666

## 回复 by 白毅 (#74)

*2026-5-23 06:27*

牛逼

## 回复 by 简单的简单 (#75)

*2026-5-24 23:54*

666

## 回复 by 孤梦拾遗 (#76)

*2026-5-25 10:28*

看看

## 回复 by mb_rxntjwjh (#77)

*2026-6-9 17:53*

111

## 回复 by mb_degalzhb (#78)

*2026-7-20 10:21*

666

## 回复 by mb_qimctavn (#79)

*2026-7-20 10:48*

6

## 回复 by mb_gzmttlte (#80)

666
