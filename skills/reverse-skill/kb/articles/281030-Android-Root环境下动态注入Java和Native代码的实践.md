---
title: Android Root环境下动态注入Java和Native代码的实践
url: https://bbs.kanxue.com/thread-281030.htm
tid: 281030
author: WindStormy
date: '2024-03-22'
tags: [Android安全, 基础理论, 程序开发, HOOK注入, 系统相关, 工具脚本]
crawled_at: '2026-07-31T14:29:32+08:00'
replies: 13
---

博客原文：[Android Root环境下动态注入Java和Native代码的实践](https://windysha.github.io/2024/03/22/%E4%B8%80%E7%A7%8DAndroid-Root%E7%8E%AF%E5%A2%83%E4%B8%8B%E5%8A%A8%E6%80%81%E6%B3%A8%E5%85%A5Java%E5%92%8CNative%E4%BB%A3%E7%A0%81%E7%9A%84%E6%96%B9%E6%A1%88/)

# 背景

在Android逆向开发中，我们通常会使用Frida工具在命令行中动态注入JavaScript代码到目标应用，编写JavaScript对Android新手来说可能会有些困难，假如能用Java代码Hook Java层方法，c/c++代码Hook native层函数指令，用起来可能会更顺手。
 
在Android正向开发中，我们往往需要在Release包上进行性能诊断或复杂问题的分析，然而，这并不是一件容易的事情。原因在于，Release包通常不方便调试，大型App的编译过程需要消耗大量时间，修改框架或第三方SDK代码也相对困难。因此，有时候我们就需要利用逆向工具，比如Xposed或者Frida，通过代码注入的方式来进行问题调试。
 
那么，如何实现在命令行中将Xposed插件动态地注入到目标应用中呢？
本文将探讨在Android Root设备上将Xposed插件动态注入到目标应用的一种实践。

# 思路分析

实现过程主要包括以下几部分：

- 注入过程的实现；
- ART Hook框架的封装；
- 插件APK的加载，包括插件中动态库的加载；
- native进入Java的入口实现；

具体的思路如下：

1. 注入的过程可以参考Frida，使用ptrace实现；
2. ART Hook库使用有点过时但还能用的SandHook，和加载插件功能一起打包成dex和so；
3. 在ptrace注入的native动态库中实现dex的加载并调用其入口方法；

# 实现过程

以上介绍了工具的实现思路，下面详细介绍其实现过程。
整体的流程图如下：
![image](https://bbs.kanxue.com/upload/attach/202403/849838_ZDHZ3SNQJXQ6B8Y.jpg)
整体功能分为三层：

- **注入层：**在命令行中，运行可执行文件，使用ptrace将指定so文件注入到目标进程；
- **胶水层：**在目标进程启动时，完成dex和so文件合并到App主ClassLoader中，并使用合并后的ClassLoader调用dex文件中的入口方法；
- **插件加载层：**完成ART HOOK库的初始化以及外部Xposed Apk插件的加载；

## 注入层

注入层的目的是将一个二进制可执行文件注入到目标进程中并运行其中的函数；
 
linux平台上，使用ptrace进行进程注入的技术方案已经非常成熟，刚好笔者之前专门研究过，并开源了一个相对稳定可靠的android平台的ptrace注入库：
[XInjector](https://github.com/WindySha/XInjector)
 
这里，直接使用这个仓库编译出来的动态可执行文件，即可轻松实现将动态库注入到指定应用中。
 

## 胶水层

胶水层主要是完成dex和so文件合并到App主ClassLoader中，并根据合并后的ClassLoader调用dex文件中的入口方法。
这一层最大的难点是：如何在native世界撬开Java世界的大门。
 
核心流程包含：

>
> 1. 获取当前线程的JNIEnv指针；
> 2. 寻找插件加载层初始化时机；
> 3. 执行插件加载层的入口方法；
>
>
>

 
这一部分三个步骤来讲解。

### 初始化时机

执行插件加载层初始化的时机选择是本方案面临的主要挑战之一，原因如下：

- 插件加载层的初始化应尽早执行，这样插件apk能Hook住更多的方法；
- 由于ptrace注入so的时机具有不确定性，过早注入可能会出现应用的包信息未被解析，LoadedApk对象未创建，因此无法构造Context对象，无法进入Java世界；
- 若在ptrace后的流程中，直接执行插件加载层的初始化，可能会引发未知的崩溃问题。比如，若ptrace到一个被CriticalNative注解的jni方法中，在这个方法的流程中使用JNIEnv指针可能导致意外崩溃。

 
对此，Frida库在开发过程中可能也会遇到类似的问题。它的解决方案是在注入代码时创建一个子线程来运行hook代码，从而成功地绕过了第三个问题。然而，由于代码是在子线程中执行的，这使得执行时机具有一定的不确定性。这可能会导致注入时机稍微延后，结果会导致一些方法被hook前可能已经被执行。
 
基于以上分析，运行插件加载层的初始化逻辑选择以下三个时机：

1. 如果ptrace注入到无法使用JNIEnv指针的jni方法中，使用ALooper将初始化逻辑发送到主线程Handler中执行，其缺点是，执行hook逻辑时机较晚，此时Application的attachBaseContext和onCreate已经执行完成，但可以作为一种兜底方案；
2. 如果ptrace注入时机非常早，此时ActivityThread的mLoadedApk成员还未创建出来，无法进入Java世界，因此，需要延迟初始化。这里选择使用 plt hook libcutils中`atrace_update_tags`函数，在此函数中执行初始化逻辑，选择这个函数是因为它在启动时只执行一次，并且此时应用的mLoadedApk已经被创建；
3. 非以上两种情况的话，直接在Ptrace注入的流程中执行初始化逻辑，完成dex和so合并到App的主ClassLoader，并调用dex中的入口方法；
 
伪代码如下：

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253 | `static void OnAtraceFuncCalled() {``void``*` `current_thread_ptr` `=` `runtime::CurrentThreadFunc();``JNIEnv``*` `env` `=` `runtime::GetJNIEnvFromThread(current_thread_ptr);` `if` `(!env) {``LOGE(``"Failed to get JNIEnv, Inject Xposed Module failed."``);``return``;``}``InjectXposedLibraryInternal(env);``}` `int` `DoInjection(JNIEnv``*` `env) {``runtime::InitRuntime();` `void``*` `current_thread_ptr` `=` `nullptr;``if` `(!env) {``current_thread_ptr` `=` `runtime::CurrentThreadFunc();``env` `=` `runtime::GetJNIEnvFromThread(current_thread_ptr);``}``if` `(!env) {``LOGE(``"Failed to get JNIEnv !!"``);``return` `-``1``;``}` `/``/` `ptrace到JNI方法Java_java_lang_Object_wait时，会出现由于等锁导致的env``-``>FindClass卡死的问题，这里Handler中加载xposed模块``/``/` `ptrace到JNIT方法Java_com_android_internal_os_ClassLoaderFactory_createClassloaderNamespace时，正在构造classLoader此时调用FindClass会卡死``/``/` `这里绕过这两个方法，发送任务到主线程Handler执行；``void``*` `art_method` `=` `runtime::GetCurrentMethod(current_thread_ptr, false, false);``if` `(art_method !``=` `nullptr) {``std::string name` `=` `runtime::JniShortName(art_method);``if` `(strcmp(name.c_str(),` `"Java_java_lang_Object_wait"``)` `=``=` `0``\|\| strcmp(name.c_str(),` `"Java_com_android_internal_os_ClassLoaderFactory_createClassloaderNamespace"``)` `=``=` `0``) {``/``/` `load xposed modules after` `in` `the main message handler, this` `is` `later than application's attachBaseContext` `and` `onCreate method.``InjectXposedLibraryByHandler(env);``return` `0``;``}``}` `/``/` `If the inject time` `is` `very early, then, the loadedapk info` `and` `the app classloader` `is` `not` `ready, so we` `try` `to hook atrace_set_debuggable function to make sure` `/``/` `the injection` `is` `early enough` `and` `the classloader has also been created.``jobject loaded_apk_obj` `=` `jni::GetLoadedApkObj(env);``LOGD(``"Try to get the app loaded apk info, loadedapk jobject: %p"``, loaded_apk_obj);` `if` `(loaded_apk_obj` `=``=` `nullptr) {``/``/` `load xposed modules after atrace_set_debuggable` `or` `atrace_update_tags` `is` `called.``HookAtraceFunctions(OnAtraceFuncCalled);``}``else` `{``/``/` `loadedapk` `and` `classloader` `is` `ready, so load the xposed modules directly.``InjectXposedLibraryInternal(env);``}``return` `0``;``}` |
|-|-|

虽然在主线程中执行代码注入能确保其发生的时机足够早，但在实际应用中，我们发现这个方案会导致注入后的应用启动崩溃或者卡死的概率非常高。这种现象可能是由于虚拟机的限制所导致，虚拟机的某些 JNI 函数内部无法运行 Java 代码。
 
因此，我们最终还是默认选择使用 Frida 的解决方案，在子线程中初始化和执行插件的入口方法。
这应该是一种更为稳定和可靠的方案。
代码如下：

| 12345678910111213141516171819202122232425 | `static void InjectXposedLibraryAsync(JNIEnv``*` `jni_env) {``JavaVM``*` `javaVm;``jni_env``-``>GetJavaVM(&javaVm);``std::thread worker([javaVm]() {``JNIEnv``*` `env;``javaVm``-``>AttachCurrentThread(&env, nullptr);` `int` `count` `=` `0``;``while` `(count <` `10000``) {``jobject app_loaded_apk_obj` `=` `jni::GetLoadedApkObj(env);``/``/` `wait here until loaded apk` `object` `is` `available``if` `(app_loaded_apk_obj` `=``=` `nullptr) {``usleep(``100``);``}` `else` `{``break``;``}``count``+``+``;``}``InjectXposedLibraryInternal(env);``if` `(env) {``javaVm``-``>DetachCurrentThread();``}``});``worker.detach();``}` |
|-|-|

### 合并Classloader

ptrace成功后，就可以执行我们的native代码，但为了能加载外置插件，我们需要使用Java代码来实现。为了能进入Java世界，需要在native层构造相关Classloader然后调Java层入口方法。
 
一般来说，使用Classloader加载Java代码有两种策略：

1. 依据目录dex文件路径，单独构造dex文件对应的Classloader，使用此Classloader加载入口类；
2. 将目标dex文件合并在App的主Classloader中，使用App的Classloader加载入口类；
 
考虑到实现的难易程度，这里选择了第二种策略：合并Classloader策略。
主要的实现思路是对App的PathClassLoader所对应的pathList成员变量进行修改。我们利用目标dex文件的路径，构造一个新的DexElement实例，并将这个实例加入到pathList的dexElements数组中。同时，我们将目标so文件的路径融入到pathList的nativeLibraryDirectories数组中。
 
具体实现起来，难点有：
3. 需要纯native代码实现；
4. 不同Android版本PathClassLoader中的成员变量和数据结构差异较大，需要针对各版本做好兼容；
 
解决办法是，先用java代码实现好完整的功能，并兼容好不同的Android版本，然后再“翻译”为c++代码的实现。

### 调用入口方法

将dex和so合并到App主ClassLoader之后，使用当前线程的JNIEnv指针反射调用dex文件中的入口类和入口方法时，会抛出类找不到的异常，原因暂不可知。
 
为了规避这个问题，这里使用一种“破釜沉舟”的办法：
直接使用App的ClassLoader调用loadClass方法加载目标类，然后再通过getDeclaredMethod获取目标方法，最后再调用Method.invoke()执行目标方法。
 
伪代码如下：

| 1234567891011121314151617181920212223242526272829303132 | `void CallStaticMethodByJavaMethodInvoke(JNIEnv``*` `env, const char``*` `class_name, const char``*` `method_name) {``ScopedLocalRef<jobject> app_class_loader(env, jni::GetAppClassLoader(env));` `const char``*` `classloader_class_name` `=` `"java/lang/ClassLoader"``;``const char``*` `class_class_name` `=` `"java/lang/Class"``;``const char``*` `method_class_name` `=` `"java/lang/reflect/Method"``;` `/``/` `Class<?> clazz` `=` `appClassLoader.loadClass(``"class_name"``);``ScopedLocalRef<jclass> classloader_jclass(env, env``-``>FindClass(classloader_class_name));``auto loadClass_mid` `=` `env``-``>GetMethodID(classloader_jclass.get(),` `"loadClass"``,` `"(Ljava/lang/String;)Ljava/lang/Class;"``);``ScopedLocalRef<jstring> class_name_jstr(env, env``-``>NewStringUTF(class_name));``ScopedLocalRef<jobject> clazz_obj(env, env``-``>CallObjectMethod(app_class_loader.get(), loadClass_mid, class_name_jstr.get()));` `/``/` `get Java Method mid: Class.getDeclaredMethod()``ScopedLocalRef<jclass> class_jclass(env, env``-``>FindClass(class_class_name));``auto getDeclaredMethod_mid` `=` `env``-``>GetMethodID(class_jclass.get(),` `"getDeclaredMethod"``,``"(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;"``);` `/``/` `Get the Method` `object``ScopedLocalRef<jstring> method_name_jstr(env, env``-``>NewStringUTF(method_name));``jvalue args[]` `=` `{ {.l` `=` `method_name_jstr.get()},{.l` `=` `nullptr} };``ScopedLocalRef<jobject> method_obj(env, env``-``>CallObjectMethodA(clazz_obj.get(), getDeclaredMethod_mid, args));` `ScopedLocalRef<jclass> method_jclass(env, env``-``>FindClass(method_class_name));``/``/` `get Method.invoke jmethodId``auto invoke_mid` `=` `env``-``>GetMethodID(method_jclass.get(),` `"invoke"``,``"(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;"``);` `/``/``Call Method.invoke()``jvalue args2[]` `=` `{ {.l` `=` `nullptr},{.l` `=` `nullptr} };``env``-``>CallObjectMethodA(method_obj.get(), invoke_mid, args2);``}` |
|-|-|

## 插件加载层

插件加载层的最终产物是Android App工程编译出来的dex文件和so文件。
 
这个Android工程主要包含基于SandHook的Xposed Api库，包含一个入口方法，用于初始化SandHook以及加载Xposed插件Apk。
 
核心逻辑有：

- ART Hook的初始化：构造App Context对象，并用context对象调用SandHook的初始化方法；
- 预处理插件Apk：根据插件apk文件路径，将Apk中的so文件解压到App私有目录下；
- 加载插件Apk：根据插件Apk文件路径，so文件路径，构造插件ClassLoader，加载插件入口类，并调用入口方法；
 
下面简单介绍这三个步骤的实现要点。

### ART Hook的初始化

由于SandHook库的初始化时需要传入context对象，但由于插件加载层被注入的时机很早，此时的应用的Application和App Context对象很可能并未创建出来，因此，需要自行创建一个应用的context对象。
 
ContextImpl类中有一个方法createAppContext可以用于创建context对象，参数包含两个，一个是当前进程的ActivityThread对象，另一个是LoadedApk对象。前者是个单例，通过反射很容易得到，后者是保存在ActivityThread的mBoundApplication成员变量中，也可以反射获取。
 
完整的构造context代码如下：

| 12345678910111213141516171819202122232425262728293031 | `public static Context createAppContext() {``/``/`        `ContextImpl appContext` `=` `ContextImpl.createAppContext(mActivityThread, mLoadedApk);``try` `{``Class activityThreadClass` `=` `Class.forName(``"android.app.ActivityThread"``);``Method currentActivityThreadMethod` `=` `activityThreadClass.getDeclaredMethod(``"currentActivityThread"``);``currentActivityThreadMethod.setAccessible(true);` `Object` `activityThreadObj` `=` `currentActivityThreadMethod.invoke(null);` `Field boundApplicationField` `=` `activityThreadClass.getDeclaredField(``"mBoundApplication"``);``boundApplicationField.setAccessible(true);``Object` `mBoundApplication` `=` `boundApplicationField.get(activityThreadObj);` `/``/` `AppBindData` `Field infoField` `=` `mBoundApplication.getClass().getDeclaredField(``"info"``);` `/``/` `info``infoField.setAccessible(true);``Object` `loadedApkObj` `=` `infoField.get(mBoundApplication);` `/``/` `LoadedApk` `Class contextImplClass` `=` `Class.forName(``"android.app.ContextImpl"``);``Method createAppContextMethod` `=` `contextImplClass.getDeclaredMethod(``"createAppContext"``, activityThreadClass, loadedApkObj.getClass());``createAppContextMethod.setAccessible(true);` `Object` `context` `=` `createAppContextMethod.invoke(null, activityThreadObj, loadedApkObj);` `if` `(context instanceof Context) {``return` `(Context) context;``}``} catch (ClassNotFoundException \| NoSuchMethodException \| IllegalAccessException \| InvocationTargetException \| NoSuchFieldException e) {``e.printStackTrace();``}``return` `null;``}` |
|-|-|

### 预处理插件Apk

 
为了实现在xposed插件中自动加载native代码，我们需对插件内的动态so库进行特别处理。
具体的处理方式是：先将插件APK中的so文件提取到指定的目录下，然后在构造插件的`DexClassLoader`时，将so文件的目录传入。这样，插件Apk在调用`System.loadLibrary()`时就可以成功加载插件的so库了。
 
在整个流程中，关键环节在于提取插件Apk中的so文件。
 
最常见的提取方式是首先解压apk压缩包，然后复制解压后的so文件到指定的目录下。
 
如果你对Android系统源码进行过详细了解，会发现源码中已经集成了提取Apk文件中so的相关功能。这个功能是由`NativeLibraryHelper.java`这个工具类提供的。
该工具主要用途是，在安装Apk过程中，如果Apk的manifest文件中配置了`android:extractNativeLibs = true`，系统会自动将apk文件中的so文件提取到指定目录下。然后在app启动时，构造App的ClassLoader并将该目录作为参数传入，从而实现native库的自动加载。
 

提取so文件的源码如下：
`com/android/internal/content/NativeLibraryHelper.java`

| 123456789101112131415161718 | `/``*``*``*` `Copies native binaries to a shared library directory.``*``*` `@param handle APK` `file` `to scan` `for` `native libraries``*` `@param sharedLibraryDir directory` `for` `libraries to be copied to``*` `@``return` `{@link PackageManager``#INSTALL_SUCCEEDED} if successful or another``*`         `error code` `from` `that` `class` `if` `not``*``/``public static` `int` `copyNativeBinaries(Handle handle,` `File` `sharedLibraryDir, String abi) {``for` `(``long` `apkHandle : handle.apkHandles) {``int` `res` `=` `nativeCopyNativeBinaries(apkHandle, sharedLibraryDir.getPath(), abi,``handle.extractNativeLibs, handle.debuggable);``if` `(res !``=` `INSTALL_SUCCEEDED) {``return` `res;``}``}``return` `INSTALL_SUCCEEDED;``}` |
|-|-|

这里，只需要先反射构造一个Handle对象，然后再反射调用copyNativeBinaries这个方法即可实现将so文件提取到指定目录下。
 

### 加载插件Apk

加载插件Apk的逻辑比较简单，参考Xposed原生代码的实现即可。
主要分为两个步骤：

1. 构造DexClassLoader，读取Apk的assets/xposed_init目录下配置的创建入口类的类全名；
2. 再次构造DexClassLoader，根据入口类的全名加载入口类，构造类的实例，并调用入口方法。
 
伪代码如下：

| 12345678910111213141516171819202122232425262728293031323334 | `/``/` `use system classloader to load asset to avoid the app has` `file` `assets``/``xposed_init``ClassLoader assetLoader` `=` `new DexClassLoader(moduleApkPath, moduleOdexDir, moduleLibPath, ClassLoader.getSystemClassLoader());``InputStream` `is` `=` `assetLoader.getResourceAsStream(``"assets/xposed_init"``);``if` `(``is` `=``=` `null) {``Log.i(TAG,` `"assets/xposed_init not found in the APK"``);``return` `false;``}` `ClassLoader mcl` `=` `new DexClassLoader(moduleApkPath, moduleOdexDir, moduleLibPath, appClassLoader);``BufferedReader moduleClassesReader` `=` `new BufferedReader(new InputStreamReader(``is``));` `String moduleClassName;``while` `((moduleClassName` `=` `moduleClassesReader.readLine()) !``=` `null) {``moduleClassName` `=` `moduleClassName.trim();``if` `(moduleClassName.isEmpty() \|\| moduleClassName.startsWith(``"#"``))``continue``;` `Class<?> moduleClass` `=` `mcl.loadClass(moduleClassName);` `final` `Object` `moduleInstance` `=` `moduleClass.newInstance();` `if` `(moduleInstance instanceof IXposedHookLoadPackage) {``IXposedHookLoadPackage.Wrapper wrapper` `=` `new IXposedHookLoadPackage.Wrapper((IXposedHookLoadPackage) moduleInstance);``XposedBridge.CopyOnWriteSortedSet<XC_LoadPackage> xc_loadPackageCopyOnWriteSortedSet` `=` `new XposedBridge.CopyOnWriteSortedSet<>();``xc_loadPackageCopyOnWriteSortedSet.add(wrapper);``XC_LoadPackage.LoadPackageParam lpparam` `=` `new XC_LoadPackage.LoadPackageParam(xc_loadPackageCopyOnWriteSortedSet);``lpparam.packageName` `=` `currentApplicationInfo.packageName;``lpparam.processName` `=` `getCurrentProcessName(currentApplicationInfo);;``lpparam.classLoader` `=` `appClassLoader;``lpparam.appInfo` `=` `currentApplicationInfo;``lpparam.isFirstApplication` `=` `true;``XC_LoadPackage.callAll(lpparam);``}``}` |
|-|-|

至此，完成插件Apk的加载。

## 产物目录

下面是最终产物文件目录结构，以及每个文件的用途：

| 12345678910111213141516 | `├── README.md` `/``/` `说明文档``├── glue` `/``/` `此文件夹中是胶水层的注入到目标进程的so文件，用于插件加载层的dex和so的注入和加载``│   ├── arm64``-``v8a``│   │   └── libinjector``-``glue.so``│   └── armeabi``-``v7a``│       └── libinjector``-``glue.so``├── injector` `/``/` `此文件夹中是注入层的可执行文件``│   ├── arm64``-``v8a``│   │   └── xinjector``│   └── armeabi``-``v7a``│       └── xinjector``├── plugin_loader` `/``/` `此文件夹中是插件加载层的编译出的dex和so文件，实现ART Hook和Xposed插件Apk的加载``│   ├── classes.dex``│   ├── libsandhook``-``64.so``│   └── libsandhook.so``└── start.sh` `/``/` `启动脚本(暂时只支持macOS)，用于复制所有的文件到Android Root设备的data``/``local``/``tmp目录下，并运行xinjector可执行文件` |
|-|-|

# 使用方法

## 基本用法

1. 下载[zip压缩包](https://github.com/WindySha/Poros/releases/download/v1.1/v1.1.zip)并解压；
2. 打开命令行，cd到解压后的目录下；
3. 执行以下命令，即可实现重启目标app，并将xposed插件注入到目标app进程中：

| 1 | `$ .``/``start.sh` `-``p com.android.settings` `-``f xposed_module_sample.apk` |
|-|-|

启动的App是: com.android.settings
注入的xposed插件apk路径是：xposed_module_sample.apk
 

## 其他用法

性能模式：使用参数 `-q`
默认情况下，会拷贝glue和plugin_loader目录下的dex和so文件到目标app的data/data/目录下，使用-q后便不拷贝这些文件，对同一个app进行第二次注入时使用此参数，可以提升注入性能。

| 1 | `$ .``/``start.sh` `-``p com.android.settings` `-``f xposed_module_sample.apk` `-``q` |
|-|-|

 
另外，如果对同一app第二次注入相同的xposed插件时，也可以省`-f xposed_module_sample.apk` 参数，此时会使用上次注入过的插件。
 
使用-h参数: 可在控制台输出帮助信息：

| 1 | `$ .``/``start.sh` `-``h` |
|-|-|

控制台输出结果：

| 123456789 | `[ Java And C``/``C``+``+` `Code Injection` `for` `Android Root Device]` `Usage: .``/``start.sh` `-``p package_name` `-``f xxx.apk` `-``h` `-``q` `Options:``-``p [package name]      the package name to be injected``-``f [apk path]          the xposed module apk path``-``h                     display this` `help` `message``-``q                     use quick mode, do` `not` `inject the xposed dex` `and` `so` `file``, this can only used when it` `is` `not` `the first time to inject target app.` |
|-|-|

# 已知问题

由于本工具实现比较仓促，目前还存在一些短期内无法修复的问题，主要有：

1. 偶现ptrace注入失败的情况，会导致app启动崩溃或者卡死，目前正在尝试修复中，可能会更换非ptrace的注入方案，比如此方案：[Code injection on Android without ptrace](https://erfur.github.io/blog/dev/code-injection-without-ptrace)，这个方案也可以规避反ptrace的应用；
2. ART Hook框架目前使用的是SandHook，在某些机型中可能存在稳定性问题，未来可能会更换成持续维护的Lsposed库；
3. 暂时只支持注入代码到应用的主进程，由于应用的子进程启动时机不确定，暂时无法统一支持；
4. 在android13及以上设备上，由于SankHook的缺陷，hook未解析类的静态方法可能会失败，一种规避的方法是调用下面的resolveStaticMethod()方法来提前解析这个静态方法所在的类，然后再执行hook：

| 123456789101112131415161718 | `public static void resolveStaticMethod(Member method) {``try` `{``if` `(method instanceof Method && Modifier.isStatic(method.getModifiers())) {``((Method) method).setAccessible(true);``((Method) method).invoke(new` `Object``(), getFakeArgs((Method) method));``}``} catch (Throwable throwable) {``}``}` `private static` `Object``[] getFakeArgs(Method method) {``Class[] pars` `=` `method.getParameterTypes();``if` `(pars` `=``=` `null \|\| pars.length` `=``=` `0``) {``return` `new` `Object``[]{new` `Object``()};``}` `else` `{``return` `null;``}``}` |
|-|-|

# 源码和规划

## 源码

<https://github.com/WindySha/Poros>
有能力的可提交PR，欢迎共建。

## 未来规划

- 优化Java Hook库的稳定性和兼容性或者更换为其他更稳定库；
- 注入流程支持非ptrace方案；
- 支持在windows，linux平台上编译和执行注入；
- 支持子进程注入；
- 支持多插件注入；

# 参考

- [Frida](https://github.com/frida/frida)
- [XInjector](https://github.com/WindySha/XInjector)
- [linjector-rs](https://github.com/erfur/linjector-rs)

# 写在结尾

写这个工具的动机是，笔者的工作是做某大型App的底层优化，经常要改ART虚拟机或者其他系统动态库的一些功能，由于大型App编译安装太耗时，通过这种注入的方式进行测试和开发确实能提升效率，因此就顺手撸了这个工具。
 
其实很久之前就写好了这个工具，最开始只是自己用，没打算开源出来，后来想想，如其让代码烂在电脑里，不如开源出来，说不定能给其他人带来一些帮助。
 
世界因开源而更加美好。

---

# 回复

## 回复 by huangjw (#2)

*2024-3-22 02:32*

系统层的文章不多，给一个精。

## 回复 by New对象处 (#3)

*2024-3-22 10:39*

好文

## 回复 by mb_lpcoesnt (#4)

*2024-3-22 11:34*

（感谢分享,不是觉得这个项目不好）就是有个小问题,既然root了为啥不直接用lsposed来进行xposedhook呢？这个项目好像ptrace+sandhook+xposed那不是检测拉满了嘛？

## 回复 by 陈可牛 (#5)

*2024-3-22 11:49*

感谢大佬的分享

## 回复 by caolinkai (#6)

*2024-3-22 11:58*

感谢大佬的分享

## 回复 by 秋狝 (#7)

*2024-3-22 14:11*

感谢分享

## 回复 by Amun (#8)

*2024-3-22 17:00*

学习了，优势在于在没有 Xposed Framework 的情况下，加载和使用 Xposed Module。

以前用 Frida 实现类似的需求，是这么搞的。

用 Frida 官方提供的 frida-inject ，启动一个 App 并注入 frida-agent 到进程

| 123 | `/data/local/tmp` `# echo "console.log('hijack ' + Process.id)" > ./hello.js``/data/local/tmp` `# ./frida-inject-16.2.1-android-arm64 -f icu.nullptr.nativetest -s ./hello.js``hijack 14381` |
|-|-|

| 12345 | `/``# cat /proc/14381/maps \| grep frida``730275c000-7303173000 r--p 00000000 00:05 2523545``/memfd``:frida-agent-64.so (deleted)``7303174000-7303ea1000 r-xp 00a17000 00:05 2523545``/memfd``:frida-agent-64.so (deleted)``7303ea1000-7303f71000 r--p 01743000 00:05 2523545``/memfd``:frida-agent-64.so (deleted)``7303f72000-7303f8e000 rw-p 01813000 00:05 2523545``/memfd``:frida-agent-64.so (deleted)` |
|-|-|

然后把 hello.js 换成 XposedFridaBridge.js 之类的东西，就可以启动 Xposed Module 了

## 回复 by KerryS (#9)

*2024-3-22 17:41*

这个工具我也想搞过，当时的想法是弄一个完全自己能掌控的工具，方便过检测，frida毕竟太庞大了，特征太多，注入其实可以用frida-inject

## 回复 by wx_嗨 (#10)

*2024-3-23 22:27*

佬，注入一个apk文件以后要怎么使用插件res内的资源文件

## 回复 by WindStormy (#11)

*2024-3-24 02:17*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_嗨](https://bbs.kanxue.com/user-953698.htm)
>
>  佬，注入一个apk文件以后要怎么使用插件res内的资源文件
>
>

可以在xposed插件里，根据插件类的classloader获取插件的文件路径，根据插件路径构造AssetManager，然后再构造Resource，然后就可以读取资源文件。
可以参考下这里对Resource的构造：https://github.com/WindySha/XSkinLoader/blob/master/xskinloader-lib/src/main/java/com/wind/me/xskinloader/pluginLoader/PluginLoadUtils.java#L140

## 回复 by WindStormy (#12)

*2024-3-24 02:25*

l

## 回复 by WindStormy (#13)

*2024-3-24 02:30*

>
> [mb_lpcoesnt](https://bbs.kanxue.com/user-974493.htm)
>
>  （感谢分享,不是觉得这个项目不好）就是有个小问题,既然root了为啥不直接用lsposed来进行xposedhook呢？这个项目好像ptrace+sandhook+xposed那不是检测拉满了嘛？
>
>

lsposed也可以。
这玩意儿貌似之前没人搞过，这里只是提供一种新思路，新方案，不一定是最优的，各有其优缺点。
至于检测，属于逆向对抗的范畴，需要针对性处理，我更多做正向开发，这方面也不太擅长。
frida这么强大，不是也没有专门处理被检测的问题。

## 回复 by tmi (#14)

*2024-3-25 15:03*

厉害了，我最近也在学习xposed源码，所以上面代码看着熟悉。我的做法是将抄写的xposed的启动代码直接塞到系统源码里面，在Zygote代码内加载apk（module），在ActivityThread类里面拿到cl和其它信息，启动module的代码，给自己用的，不通用
