---
title: '[原创]Albatross Android——快速、优雅的强大安卓hook框架'
url: https://bbs.kanxue.com/thread-287679.htm
tid: 287679
author: WanQing
date: '2025-07-20'
tags: [Android安全, 原创, 逆向分析, 程序开发, HOOK注入, 系统相关, 源码框架, 工具脚本]
crawled_at: '2026-07-31T15:44:52+08:00'
replies: 207
---

# Albatross Android：一个高性能的 Android Hook 框架

[项目地址](https://github.com/AlbatrossHook/AlbatrossAndroid)

## 前言

该项目是两年前开发的，一年前已经开始尝试集成到沙箱中，最近根据功能需求，后续的代码都使用自研的框架。非常的好用，所以特定分享出来。现在是自己写的`albatros-server`用于hook的system_server和app，可用于hook和反射，能极大的简化代码逻辑,可以强制将被hook的类转换成hooker，直接调用方法和访问字段，避免反射的开销

## 项目概述

**Albatross Android** 是一个专为 Android 平台（支持 Android 8.0 到 Android 16）设计的高性能、低影响的 Hook 框架。

Albatross Android 的核心机制是通过定义“Hooker 类”（镜像类）来描述需要 Hook 的类和字段。框架会自动推导出目标方法和字段，并实现对目标类的无缝调用和访问。与传统的反射机制不同，Albatross 几乎没有性能损耗，同时兼顾了安全性和兼容性。

---

## 设计理念

Albatross 基于 YAHFA 框架进行了大量优化和功能扩展，使其在Android系统上具备更强的稳定性和性能表现。

其设计目标包括：

1. **高效性**：追求极致的执行速度，保留 Profile 生成和方法内联（被 Hook 方法除外）。
2. **代码优雅**：编写代码可读性强，优雅，不繁琐，简化hook逻辑。
3. **系统影响最小化**：不提前初始化类、不绕过非公开 API 限制、hook不挂起虚拟机。

---

## 核心功能

### 1. 镜像类 Hook 机制

通过定义 Hooker 类（即镜像类）来描述目标类的方法和字段，框架会自动推导出目标类并进行 Hook。例如：

| 1234567891011 | `@TargetClass``(Activity.``class``)``public` `class` `ActivityHooker {``@FieldRef``public` `boolean` `mCalled;` `@MethodHookBackup``private` `void` `onCreate(Bundle savedInstanceState) {``// Hook 后可以调用原始方法``onCreate(savedInstanceState);``}``}` |
|-|-|

### 2. 批量 Hook 与依赖解析

Albatross 支持基于事务的批量 Hook，自动解决 Hook 类之间的依赖关系，确保 Hook 流程的原子性和稳定性。

### 3. 零反射机制

不同于传统 Hook 框架依赖反射调用方法和访问字段的方式，Albatross 直接使用本地机器码调用方法和访问字段，几乎没有任何性能损耗。

### 4. 延迟 Hook（Pending Hook）

支持在目标类加载时自动触发 Hook，无需关心类何时加载。框架会在新 DEX 被加载时主动寻找目标类并进行 Hook。

### 5. 反射的替代

不仅可以作为 Hook 框架使用，还可以作为高性能的反射库使用，避免传统反射带来的性能开销。

---

## 平台支持

### Android 版本支持

| Android 版本 | 支持状态 | 说明 |
|-|-|-|
| Android 8 - Android 16 | 完全支持 | 支持方法和字段 Hook |
| Android 7 (API 24-25) | 有限支持 | 方法 Hook 支持，字段 Hook 因 dex优化限制被禁用 |
| Android 6 及以下版本 | 不支持 | 没有JIT,dex指令优化原因Field特性无法实现 |

### CPU 架构支持

- x86
- x86_64
- ARM
- ARM64

---

## 安全与稳定性

- 不提前初始化被 Hook 的类
- 不绕过非公开 API 限制，但仍可访问隐藏字段和方法
- 保留 Profile 生成和方法内联（仅被 Hook 方法不允许内联）
- 支持 Debug 和 Release 模式优化：
	- Debug 模式：稳定运行,jdwp调试不出错
	- Release 模式：如果不是是AOT，则会JIT 编译，保证hooker和be hooked的类都是已机器码方式运行

---

## 使用示例

### 1. Hook Activity 方法并访问字段

| 12345678910111213141516171819 | `@TargetClass``(Activity.``class``)``public` `class` `ActivityH {``@TargetClass``(Bundle.``class``)``public` `static` `class` `BundleH {``@FieldRef``public` `static` `Bundle EMPTY;``}` `@FieldRef``public` `boolean` `mCalled;` `@MethodHookBackup``private` `void` `onCreate(BundleH savedInstanceState) {``assert` `BundleH.EMPTY == Bundle.EMPTY;``assert` `!mCalled;``onCreate(savedInstanceState);``assert` `mCalled;``}``}` |
|-|-|

### 2. Hook 系统服务类 `LocationManagerService`

| 1234567 | `@TargetClass``(className = {``"com.android.server.LocationManagerService"``,` `"com.android.server.location.LocationManagerService"``})``public` `class` `LocationManagerServiceH {``@MethodHookBackup``private` `void` `requestLocationUpdates(LocationRequest request, Object listener, PendingIntent intent, String packageName) {``requestLocationUpdates(request, listener, intent, packageName);``}``}` |
|-|-|

### 3. 事务性 Hook 与依赖解析

| 1234567891011121314151617181920212223242526272829303132333435363738394041 | `@TargetClass``public` `static` `class` `ActivityClientRecord {``@FieldRef``public` `LoadedApk packageInfo;``@FieldRef``public` `Intent intent;``}` `@TargetClass``public` `static` `class` `LoadedApk {``@FieldRef``public` `String mPackageName;``}` `@TargetClass``(className =` `"android.app.ActivityThread"``)``public` `static` `class` `ActivityThreadH {``public` `static` `Class<?> Class;` `@StaticMethodBackup``public` `static` `native` `Application currentApplication();` `@MethodBackup``(option = MethodDefOption.NOTHING)``private` `native` `Activity performLaunchActivity(ActivityClientRecord r, Intent customIntent);` `@FieldRef``Map<IBinder, ActivityClientRecord> mActivities;` `@StaticMethodBackup``public` `static` `native` `ActivityThreadH currentActivityThread();``}` `public` `static` `void` `test()` `throws` `AlbatrossErr {``assert` `Albatross.hookClass(ActivityThreadH.``class``) !=` `0``;``ActivityThreadH activityThread = ActivityThreadH.currentActivityThread();``assert` `activityThread.getClass() == ActivityThreadH.Class;``Application app = ActivityThreadH.currentApplication();``String targetPackage = app.getPackageName();``for` `(ActivityClientRecord record : activityThread.mActivities.values()) {``assert` `targetPackage.equals(record.packageInfo.mPackageName);``}``}` |
|-|-|

### 4. binder hook

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546 | `@TargetClass``static` `class` `ParceledListSlice<T> {``@FieldRef``(option = DefOption.VIRTUAL, required =` `true``)``public` `List<T> mList;``}`  `@TargetClass``static` `class` `IPackageManager {``public` `static` `int` `count =` `0``;` `@MethodHookBackup``private` `ParceledListSlice<ResolveInfo> queryIntentActivities(Intent intent, String resolvedType,` `long` `flags,` `int` `userId) {` `ParceledListSlice<ResolveInfo> res = queryIntentActivities(intent, resolvedType, flags, userId);``count = res.mList.size();``return` `res;``}` `@MethodHookBackup``private` `ParceledListSlice<ResolveInfo> queryIntentActivities(Intent intent, String resolvedType,` `int` `flags,` `int` `userId) {``ParceledListSlice<ResolveInfo> res = queryIntentActivities(intent, resolvedType, flags, userId);``count = res.mList.size();``return` `res;``}``}`  `public` `static` `class` `PackageManagerH {``@FieldRef``(option = DefOption.INSTANCE)``private` `IPackageManager mPM;``}` `public` `static` `void` `test(``boolean` `hook)` `throws` `AlbatrossErr {``if` `(!Albatross.isFieldEnable())``return``;``PackageManager packageManager = Albatross.currentApplication().getPackageManager();``if` `(hook) {``Albatross.hookObject(PackageManagerH.``class``, packageManager);``}` `else``IPackageManager.count = -``1``;``Intent resolveIntent =` `new` `Intent(Intent.ACTION_MAIN,` `null``);``resolveIntent.addCategory(Intent.CATEGORY_LAUNCHER);``List<ResolveInfo> res = packageManager.queryIntentActivities(resolveIntent,` `0``);``assert` `res.size() == IPackageManager.count;``}` |
|-|-|

---

## 优势对比

| 功能 | 传统框架 | Albatross |
|-|-|-|
| 类初始化 | 主动触发类初始化 | 不初始化 |
| 性能 | 存在反射开销 | 接近原生机器码速度 |
| 系统影响 | 关闭 Profile/内联 | 保留编译器优化 |
| 安全性 | 绕过非公开API限制 | 能访问隐藏api，事务结束隐藏api仍不可见 |
| 批量 Hook | 无法原子化 Hook类及其依赖 | 自动激活依赖Hooker |
| 延迟 Hook | 不支持（已经resolved的类严格不算延迟hook） | 通过指定className,类一旦初始化了立即触发hooker，对于加壳的app进行hook非常有用 |

---

## 未来规划

Albatross 正在持续开发中，计划引入以下功能（根据反馈优先级实现）：

- 适配低版本android(android7及其以下field的特性是一定无法使用的)
- Unhook 功能
- Hook 调用链支持
- 动态 Hook（一个方法 Hook 多个类）
- Java 字节码 Hook
- Java 代码追踪

开发Albatross的目标是淘汰掉Xposed，这种基于callback根本不是好的实现方式，导致后面的新框架都认为callback是理所应当的，成了一种规范。所以计划后面开发多开软件，免root方案加载基于albatross开发的插件，一点点蚕食掉xposed的份额。

---

# 回复

## 回复 by bluegatar (#2)

*2025-7-20 23:11*

是要不用frida，自己来，厉害了

## 回复 by WanQing (#3)

*2025-7-20 23:22*

是的,不需要，项目里的arm64 hook也是最完美的方案,会代码分析，选出合适的临时寄存器，java aot或jit短的代码，都能被完美hook.

## 回复 by 恋一世的爱 (#4)

*2025-7-21 01:31*

so层代码没开源吗

## 回复 by SomeMx (#5)

*2025-7-21 03:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  恋一世的爱](https://bbs.kanxue.com/user-825246.htm)
>
>  so层代码没开源吗
>
>

不是写了其他模块陆续开源嘛

## 回复 by A冷忆 (#6)

*2025-7-22 13:27*

666

## 回复 by mb_umadhuev (#7)

*2025-7-22 13:40*

666

## 回复 by sk97 (#8)

*2025-7-22 13:55*

tql

## 回复 by guijingwen (#9)

*2025-7-22 14:23*

66

## 回复 by mb_iesvmzqc (#10)

*2025-7-22 14:31*

666

## 回复 by huangjw (#11)

*2025-7-22 14:32*

注解是hook框架吗，  niubplus

## 回复 by 4Chan (#12)

*2025-7-22 14:39*

niubplus

## 回复 by 九黎 (#13)

*2025-7-22 14:45*

niubi

## 回复 by mb_4nrpVMxJ (#14)

*2025-7-22 14:59*

看看

## 回复 by flice (#15)

*2025-7-22 16:20*

66666666666

## 回复 by koflfy (#16)

*2025-7-22 16:25*

mark..........

## 回复 by Light紫星 (#17)

*2025-7-22 17:36*

好东西，支持一下

## 回复 by 无所从来 (#18)

*2025-7-22 17:43*

m

## 回复 by twsxtd (#19)

*2025-7-22 18:26*

如果类名和方法名是在运行时动态找出来的，怎么 hook？如果实现不了这个，很难取代 Xposed。

## 回复 by WanQing (#20)

*2025-7-22 18:52*

支持pending hook的，类似demo中的@TargetClass(className = {"name1", "name2"},pendingHook=true)，把可能的类名写进去。如果能拿到对象，可以调用hookObject

## 回复 by WanQing (#21)

*2025-7-22 19:01*

>
> [twsxtd](https://bbs.kanxue.com/user-672243.htm)
>
>  如果类名和方法名是在运行时动态找出来的，怎么 hook？如果实现不了这个，很难取代 Xposed。
>
>

如果想要一个方法去hook多个类，就比如okhttp，sdk可能和app都集成了，app中有好几个，我的方案是拷贝好几个OkHttphooker，在一个类的数组中，去用可用的hooker去hook去加载出来的okhttp。还有一种方案是方案签名多一个参数，用于区分是调用哪个方法，但field特性就不能用了，字段偏移不一样。

## 回复 by _雨化田 (#22)

*2025-7-22 21:56*

太强了，qqqqq

## 回复 by Snowman_Liam (#23)

*2025-7-23 13:47*

6666

## 回复 by mb_nsxzyazh (#24)

*2025-7-23 14:10*

康康

## 回复 by 夜惜风雨 (#25)

*2025-7-23 14:15*

6666

## 回复 by mb_jacxgcwv (#26)

*2025-7-23 14:25*

66666

## 回复 by aerfaxing (#27)

*2025-7-23 15:23*

感谢分享

## 回复 by dfJerry (#28)

*2025-7-23 15:47*

666666

## 回复 by mb_ynpgeaep (#29)

*2025-7-23 16:10*

666

## 回复 by mb_pesxllvn (#30)

*2025-7-23 16:11*

666

## 回复 by homea_qwq (#31)

*2025-7-23 16:47*

666

## 回复 by 一只笨猫 (#32)

*2025-7-23 17:08*

看看

## 回复 by 希梦☆奈何 (#33)

*2025-7-23 17:23*

路过看看

## 回复 by hpphpp (#34)

*2025-7-23 17:37*

能hook so里面的 native code吗?

## 回复 by Vengeance (#35)

*2025-7-23 17:47*

666

## 回复 by WanQing (#36)

*2025-7-23 21:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  hpphpp](https://bbs.kanxue.com/user-226208.htm)
>
>  能hook so里面的 native code吗?
>
>

如果是通过java hook那就得有很大限制，libc和art等jvm依赖的库不能hook,app的是可以回调java方法在java层hook。项目的albatross_base是能hook方法和指令，和监控内存读写的，不过只实现x86,x64,arm,arm64常见的读写指令解释。

## 回复 by k4y0z (#37)

*2025-7-25 16:55*

666

## 回复 by WanQing (#38)

*2025-7-25 23:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  k4y0z](https://bbs.kanxue.com/user-1045151.htm)
>
>  666
>
>

底层和用法差距都很大，这个也可以当反射库使用。callback的个人觉得应该用于hook指令，用于恢复上下文，不管hook java函数还是native，都不是最佳实践。

## 回复 by KerryS (#39)

*2025-7-26 04:55*

frida不好吗,动态,而且各种hook,trace,如此强大,如此完美

## 回复 by TeamAR (#40)

*2025-7-26 05:13*

6666

## 回复 by WanQing (#41)

*2025-7-26 08:39*

>
> [KerryS](https://bbs.kanxue.com/user-844633.htm)
>
>  frida不好吗,动态,而且各种hook,trace,如此强大,如此完美
>
>

frida只适合调试逆向，并不适合集成到app中，底层是通过jni调用方法和访问字段，性能差，复杂了维护性也差。albatross有点类似c的文件头，将方法和字段定义出来，然后访问和调用，由于非调试情况下会强制将方法已机器码的形式运行，性能甚至会比以前快。

## 回复 by WanQing (#42)

*2025-7-26 08:40*

而且也不支持java代码的trace,这个功能正在开发中。

## 回复 by troops (#43)

*2025-7-26 11:53*

是666

## 回复 by yyamcom (#44)

*2025-7-26 12:09*

康康

## 回复 by KerryS (#45)

*2025-7-26 17:44*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  frida只适合调试逆向，并不适合集成到app中，底层是通过jni调用方法和访问字段，性能差，复杂了维护性也差。albatross有点类似c的文件头，将方法和字段定义出来，然后访问和调用，由于非调试情 ...
>
>

如果用纯c或者c++,去实现java层的hook,那就好了,配合frida的gum,再加llvm 的jit,就能既高性能,又动态,完美,曾经想用gum来实现,但是java hook,工程量有点多,大佬有没有兴趣做这个

## 回复 by WanQing (#46)

*2025-7-26 18:12*

>
> [KerryS](https://bbs.kanxue.com/user-844633.htm)
>
>  如果用纯c或者c++,去实现java层的hook,那就好了,配合frida的gum,再加llvm 的jit,就能既高性能,又动态,完美,曾经想用gum来实现,但是java hook,工程量有点多,大佬 ...
>
>

为什么要c和c++,肯定是java是最佳实践，访问java永远最佳的语言就是java语言自身。c和c++底层调用字段和方法都是jni，中间检验参数构建堆栈，甚至比java层反射性能还差，albatross写的java代码如果没有debug最终都是走机器码的。

## 回复 by WanQing (#47)

*2025-7-26 18:22*

可以让hooker的方法为native就可以的，不过jni的代码jvm是无法优化的，并不推荐。

## 回复 by KerryS (#48)

*2025-7-27 20:06*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  为什么要c和c++,肯定是java是最佳实践，访问java永远最佳的语言就是java语言自身。c和c++底层调用字段和方法都是jni，中间检验参数构建堆栈，甚至比java层反射性能还差，albatro ...
>
>

因为c足够精简,而且可以动态执行,就像js脚本一样,java的话,在Android中,好像只能编译成dex然后动态去用,这就很冗重了,不像c和js一样一个代码片段就可以动态执行

## 回复 by WanQing (#49)

*2025-7-27 21:00*

>
> [KerryS](https://bbs.kanxue.com/user-844633.htm)
>
>  因为c足够精简,而且可以动态执行,就像js脚本一样,java的话,在Android中,好像只能编译成dex然后动态去用,这就很冗重了,不像c和js一样一个代码片段就可以动态执行
>
>

是的，不过用c语言当脚本，不适合写太复杂的逻辑，不然调试排查问题很困难。不过你这个想法确实是可以。

## 回复 by iBa0 (#50)

*2025-7-27 21:07*

fsdfsdf

## 回复 by XCicada (#51)

*2025-7-28 14:49*

tql

## 回复 by xx_dd_y (#52)

*2025-7-28 15:51*

666

## 回复 by 废人one (#53)

*2025-7-30 11:30*

1111111111111111111

## 回复 by mb_hiqkelrh (#54)

*2025-7-30 15:24*

666

## 回复 by ziyunlll (#55)

*2025-7-30 20:21*

666

## 回复 by 乐在囧途 (#56)

*2025-7-31 08:52*

这个可不可以全局hook？就是监控所有的方法调用，放到日志中

## 回复 by 海带 (#57)

*2025-7-31 09:40*

6666

## 回复 by 无视红绿灯 (#58)

*2025-7-31 10:01*

66666

## 回复 by mb_kfexwtvm (#59)

*2025-7-31 11:04*

试试看稳不稳定

## 回复 by FMNS (#60)

*2025-8-3 12:27*

6666

## 回复 by 程序原 (#61)

*2025-8-3 13:27*

支持一下

## 回复 by hyz111 (#62)

*2025-8-3 14:23*

6666

## 回复 by WanQing (#63)

*2025-8-3 16:07*

>
> [乐在囧途](https://bbs.kanxue.com/user-981662.htm)
>
>  这个可不可以全局hook？就是监控所有的方法调用，放到日志中
>
>

这个和它的设计原则有违背了，Albatross追求的是极致的性能，下周会提交OceanTracker的代码，这个可以是java版的stalker，可以监控方法和字段访问，代码执行跳转。

## 回复 by WanQing (#64)

*2025-8-3 16:10*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_kfexwtvm](https://bbs.kanxue.com/user-981760.htm)
>
>  试试看稳不稳定
>
>

那必须的，在标准的aosp rom上又稳又快，现在刚出来，在各种加固的app上都是正常运行的，有些强对抗的可能跑不起来。

## 回复 by qqsunqiang (#65)

*2025-8-3 19:54*

66666

## 回复 by zzw_xjx (#66)

*2025-8-3 20:40*

太强了，qqqqq

## 回复 by mb_lzotvdxv (#67)

*2025-8-4 02:32*

O

## 回复 by Ram98 (#68)

*2025-8-4 11:45*

666

## 回复 by mb_pobqzscg (#69)

*2025-8-4 16:31*

666

## 回复 by wx_此情可待成追忆 (#70)

*2025-8-4 18:05*

666

## 回复 by 舞梦月影 (#71)

*2025-8-4 22:21*

看看

## 回复 by mb_tnkubkna (#72)

*2025-8-8 12:37*

111

## 回复 by 阿杨` (#73)

*2025-8-8 13:51*

学习学习，有没有那种可以绕过加固的hook。这样就可以不用修复，仅脱壳就可以hook了

## 回复 by GuL1ng (#74)

*2025-8-8 14:01*

66666

## 回复 by WanQing (#75)

*2025-8-9 22:57*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  阿杨`](https://bbs.kanxue.com/user-982558.htm)
>
>  学习学习，有没有那种可以绕过加固的hook。这样就可以不用修复，仅脱壳就可以hook了
>
>

我测试在很多加固的app上都能跑，有些强对抗的那就是什么hook框架都不行

## 回复 by dadadasda (#76)

*2025-8-11 12:36*

从jni里面看起来整合了不少frida的写法啊

## 回复 by mb_xjdhrmck (#77)

*2025-8-11 14:01*

666666

## 回复 by xdcs100 (#78)

*2025-8-11 14:18*

6666

## 回复 by 烬奇小云 (#79)

*2025-8-11 20:33*

66

## 回复 by mb_irhdtnzm (#80)

*2025-8-12 09:06*

1

## 回复 by WanQing (#81)

*2025-8-13 20:48*

>
> [dadadasda](https://bbs.kanxue.com/user-1006186.htm)
>
>  从jni里面看起来整合了不少frida的写法啊
>
>

是的，底层native的hook是借鉴了frida，frida c代码太啰嗦，不同架构有太多冗余代码，核心功能都重构了一遍。

## 回复 by 智取琪 (#82)

*2025-8-14 10:14*

????牛牛

## 回复 by 阿杨` (#83)

*2025-8-14 14:09*

我想写一个Demo，来测试。
我在Application中的onCreate中调用：

 private void initHooks() {
        try {
            //
            try {
                Albatross.init(0);
                assert Albatross.transactionLevel() == 0;
                Albatross.hookClass(ActivityHooker.class);
            } catch (AlbatrossException e) {
                throw new RuntimeException(e);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

发生报错：                                                                                                    java.lang.UnsatisfiedLinkError: No implementation found for int qing.albatross.core.Albatross.initMethodNative(java.lang.reflect.Method, java.lang.reflect.Method, int, java.lang.Class) (tried Java_qing_albatross_core_Albatross_initMethodNative and Java_qing_albatross_core_Albatross_initMethodNative__Ljava_lang_reflect_Method_2Ljava_lang_reflect_Method_2ILjava_lang_Class_2)

我应该如何解决。是我的调用流程有问题吗？

## 回复 by mb_ogvnfpfi (#84)

*2025-8-14 15:35*

6666

## 回复 by didiid (#85)

*2025-8-14 17:09*

666

## 回复 by WanQing (#86)

*2025-8-14 19:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  阿杨`](https://bbs.kanxue.com/user-982558.htm)
>
>  我想写一个Demo，来测试。
> 我在Application中的onCreate中调用：
>
>  private void initHooks() {
>  try {
>  ...
>
>

设计的时候，除了native方法，都可以混淆的，所以需要你需要将类Albatross在jni方法中注册，具体看demo。

## 回复 by mb_skkbqlsl (#87)

*2025-8-14 21:57*

太强了，qqqqq

## 回复 by mb_eltlxelx (#88)

*2025-8-15 17:13*

6666666

## 回复 by mb_clkpejqc (#89)

*2025-8-16 23:26*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by 飆汗吉米 (#90)

*2025-8-17 03:27*

6666

## 回复 by mb_nazusqig (#91)

*2025-8-17 17:04*

666

## 回复 by 阿杨` (#92)

*2025-8-18 21:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  设计的时候，除了native方法，都可以混淆的，所以需要你需要将类Albatross在jni方法中注册，具体看demo。
>
>

我运行了Demo在雷电模拟器9，运行的64位的Demo。点击Load是报错的。我附报错日志如下。

上传的附件：
- 报错日志.txt

（86.91kb，5次下载）

## 回复 by mb_qqihqaoo (#93)

*2025-8-19 12:59*

666666666666

## 回复 by WanQing (#94)

*2025-8-19 19:44*

>
> [阿杨`](https://bbs.kanxue.com/user-982558.htm)
>
>  我运行了Demo在雷电模拟器9，运行的64位的Demo。点击Load是报错的。我附报错日志如下。
>
>

代码和so库要一致。你的代码没更新，最新的代码backup添加了一个额外的参数。 int qing.albatross.core.Albatross.backupNative(java.lang.Object, java.lang.reflect.Method, int, int)

## 回复 by mb_tqskihwz (#95)

*2025-8-19 23:26*

666

## 回复 by 金钱蒲 (#96)

*2025-8-20 09:39*

好好学习天天向上

## 回复 by wen55444 (#97)

*2025-8-20 18:42*

感谢分享

## 回复 by wx_最爱老大 (#98)

*2025-8-21 16:34*

666

## 回复 by wx_插曲 (#99)

*2025-8-22 12:23*

666

## 回复 by KanXue_NG (#100)

*2025-8-24 17:36*

学习了

## 回复 by 随风而行aa (#101)

*2025-8-24 19:55*

看看

## 回复 by tonglei (#102)

*2025-8-24 21:18*

学习一下

## 回复 by 问心无愧 (#103)

*2025-8-24 23:34*

6666

## 回复 by mb_akowpmjs (#104)

*2025-8-26 19:52*

6666

## 回复 by Crack999 (#105)

*2025-8-27 14:18*

来学习下

## 回复 by mb_ugfkvowp (#106)

*2025-8-31 23:40*

666

## 回复 by leishop (#107)

*2025-9-1 09:02*

6666

## 回复 by fangliangz (#108)

*2025-9-1 09:26*

666

## 回复 by wx_范迪塞尔 (#109)

*2025-9-1 10:07*

66666

## 回复 by mb_ebiwunmj (#110)

*2025-9-1 10:56*

66666666

## 回复 by fvduan (#111)

*2025-9-2 23:19*

666666

## 回复 by farendaibiao (#112)

*2025-9-3 00:06*

来看看神器，感觉新一代的破译方法

## 回复 by cobe (#113)

*2025-9-5 10:17*

666

## 回复 by Mattermon (#114)

*2025-9-5 10:47*

先赞后看。对于非root环境下的系统app逆向分析能用吗？

## 回复 by 带带弟弟吧 (#115)

*2025-9-5 10:51*

11

## 回复 by WanQing (#116)

*2025-9-5 21:15*

>
> [Mattermon](https://bbs.kanxue.com/user-467471.htm)
>
>  先赞后看。对于非root环境下的系统app逆向分析能用吗？
>
>

非root系统app只能通过多开的方式免root注入

## 回复 by wx_听书人 (#117)

*2025-9-5 23:06*

666666

## 回复 by 野狼 (#118)

*2025-9-8 00:29*

66666

## 回复 by Arsylk (#119)

*2025-9-9 10:50*

66

## 回复 by wx_软钉子 (#120)

*2025-9-15 10:10*

真的很流弊呀

## 回复 by 479159 (#121)

*2025-9-16 01:44*

6666

## 回复 by lbunknow (#122)

*2025-9-17 09:20*

666

## 回复 by mb_alksjkud (#123)

*2025-9-17 09:27*

学习

## 回复 by wx_郑泽科 (#124)

*2025-9-17 09:46*

关注

## 回复 by wx_！_336 (#125)

*2025-9-20 09:56*

6666

## 回复 by ClPrada (#126)

*2025-9-21 02:04*

学习

## 回复 by mb_pnyyaazf (#127)

*2025-9-21 16:48*

感谢分享

## 回复 by mb_nhphjyjb (#128)

*2025-10-7 14:45*

感谢分享

## 回复 by mb_qimctavn (#129)

*2025-10-7 14:58*

6

## 回复 by mb_xyoslnox (#130)

*2025-10-12 22:43*

牛逼

## 回复 by Gryffindoss (#131)

*2025-10-13 14:20*

666

## 回复 by mb_maiyudos (#132)

*2025-10-17 13:56*

66666

## 回复 by 偶尔.c (#133)

*2025-10-18 08:44*

看看隐藏，感谢分享

## 回复 by mb_ugxtlzlx (#134)

*2025-10-18 15:22*

研究一下看看

## 回复 by mb_jerxzakl (#135)

*2025-10-25 14:48*

6666

## 回复 by 情迁 (#136)

*2025-10-29 17:16*

kank

## 回复 by 镜中人24 (#137)

*2025-10-30 17:10*

666

## 回复 by mb_nneyyucj (#138)

*2025-11-1 16:28*

66666

## 回复 by coolifish (#139)

*2025-11-4 11:44*

666

## 回复 by wx_kx15109 (#140)

*2025-11-12 23:37*

感谢分享

## 回复 by wuxiping (#141)

*2025-11-13 10:33*

4444

## 回复 by 曰你 (#142)

*2025-11-13 10:54*

1

## 回复 by wx_马 (#143)

*2025-11-17 11:39*

6666

## 回复 by mb_cbgtaveo (#144)

*2025-11-17 11:46*

6666

## 回复 by wx_Mr.Wr (#145)

*2025-11-17 11:59*

????????????

## 回复 by 黑屏 (#146)

*2025-11-17 13:23*

666

## 回复 by axpol (#147)

*2025-11-17 14:32*

6666

## 回复 by xxxxxxx_798269 (#148)

*2025-11-17 14:36*

`11

## 回复 by wx_霿凇 (#149)

*2025-11-17 16:25*

666

## 回复 by YoungBai (#150)

*2025-11-18 18:20*

666

## 回复 by 饺子和皮特 (#151)

*2025-11-20 20:13*

666

## 回复 by cyixlq (#152)

*2025-11-21 11:31*

太厉害了

## 回复 by tigericon (#153)

*2025-11-28 11:14*

66

## 回复 by mb_erzjnsic (#154)

*2025-12-11 14:54*

666

## 回复 by mb_jvgnqejw (#155)

*2025-12-16 18:37*

8888

## 回复 by 叶晓枫A (#156)

*2025-12-20 09:38*

看看新的hook框架

## 回复 by 爬山的小脑虎 (#157)

*2025-12-22 14:37*

666

## 回复 by l140w4n9 (#158)

*2025-12-22 17:03*

666666666

## 回复 by wx_故事与酒 (#159)

*2025-12-23 23:14*

66666666666666666666666

## 回复 by xeiyu (#160)

*2026-1-3 15:48*

66

## 回复 by 八嘎boy (#161)

*2026-1-7 13:12*

666

## 回复 by mb_ztqcemce (#162)

*2026-1-7 13:27*

看看检查

## 回复 by mb_nbakwvoe (#163)

*2026-1-14 09:44*

666

## 回复 by mb_aiyhfydo (#164)

*2026-1-22 10:39*

666

## 回复 by mb_lnesxqxz (#165)

*2026-1-24 19:14*

66

## 回复 by Ruinv6 (#166)

*2026-1-26 14:56*

666

## 回复 by git_82373rj (#167)

*2026-1-26 19:34*

666

## 回复 by 2580369 (#168)

*2026-2-4 20:48*

666

## 回复 by Makato (#169)

*2026-2-4 23:27*

1

## 回复 by K4NG (#170)

*2026-2-26 16:06*

6666

## 回复 by atompure (#171)

*2026-2-26 18:24*

看看，学习一下，谢谢分享

## 回复 by git_56701jackt88 (#172)

*2026-3-1 02:53*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_ctvcfsmy (#173)

*2026-3-1 23:23*

看看

## 回复 by mb_ugryjzdr (#174)

*2026-3-3 09:52*

66

## 回复 by mb_itoltjbv (#175)

*2026-3-3 15:10*

66

## 回复 by 淡然出尘 (#176)

*2026-3-9 09:27*

6666

## 回复 by mb_tcheuwvg (#177)

*2026-3-19 14:32*

111111111

## 回复 by mb_njmrwrqv (#178)

*2026-3-20 00:19*

6666

## 回复 by qig (#179)

*2026-3-20 11:06*

6666

## 回复 by wx_韩信 (#180)

*2026-3-22 00:42*

6666

## 回复 by Kill_Log (#181)

*2026-3-22 22:04*

666

## 回复 by 0x7 (#182)

*2026-3-23 10:45*

666

## 回复 by mb_ndotvqat (#183)

*2026-3-23 14:43*

666

## 回复 by Big权 (#184)

*2026-3-27 20:15*

666666

## 回复 by 星辰北天 (#185)

*2026-3-29 19:59*

大佬666666

## 回复 by 黎明BAM (#186)

*2026-3-30 04:17*

666

## 回复 by 刻骨柔情 (#187)

*2026-4-6 23:42*

666

## 回复 by zylyy (#188)

*2026-4-6 23:58*

666

## 回复 by KingSelyF (#189)

*2026-4-10 13:20*

康康

## 回复 by mb_rmwvchlr (#190)

*2026-4-14 02:53*

66666666

## 回复 by wx_coddvccwyh (#191)

*2026-5-5 17:45*

6666

## 回复 by mb_ibmhjpga (#192)

*2026-5-6 11:28*

学习了

## 回复 by wx_北极星_493 (#193)

*2026-5-6 13:24*

666666

## 回复 by 学计算机睡觉 (#194)

*2026-5-22 11:38*

6666

## 回复 by จุ๊บ习惯性的回下头 (#195)

*2026-5-22 18:33*

66666

## 回复 by NSpron (#196)

*2026-6-7 09:35*

666

## 回复 by mb_dlljjfcf (#197)

*2026-6-28 23:06*

6666888

## 回复 by 太岁又沐风 (#198)

*2026-6-29 11:08*

native层代码没开源吗

## 回复 by mb_tcgbcnew (#199)

*2026-6-29 13:57*

6666

## 回复 by 发烧小孩 (#200)

*2026-6-29 14:12*

66

## 回复 by nuomida (#201)

*2026-6-30 11:20*

感谢分享

## 回复 by mb_dswynejo (#202)

*2026-7-1 20:23*

厉害

## 回复 by ReverseApp (#203)

*2026-7-13 11:49*

学习了

## 回复 by mb_vrcwxcxq (#204)

*2026-7-16 20:03*

AI在网络安全威胁中的应用越来越广泛，威胁行为者利用AI工具加速恶意软件开发，确实给安全防护带来了新的挑战。开发者需要时刻保持警惕，及时更新防护措施。

## 回复 by mb_oxqwhbqt (#205)

这个项目真的很厉害！通过自研框架实现了高效的Hook功能，避免了反射的性能开销，还能支持多版本的Android系统，确实是个不错的解决方案。期待后续功能的开发，希望能逐步取代Xposed，为开发者提

## 回复 by mb_bnjbcdzy (#206)

这个项目真的很厉害！Albatross Android作为高性能、低影响的Hook框架，几乎完全替代了传统反射机制，性能几乎没有损耗，还能支持批量Hook和自动解决依赖关系，确实是个里程碑式的开发！

## 回复 by wx_hubert_270063 (#207)

666

## 回复 by 猜我是谁_610897 (#208)

6666666
