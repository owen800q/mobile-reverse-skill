---
title: '[原创]Android第一代加壳的验证和测试'
url: https://bbs.kanxue.com/thread-277240.htm
tid: 277240
author: satadrover
date: '2023-05-16'
tags: [Android安全, 原创, 基础理论, 混淆加固, 脱壳反混淆]
crawled_at: '2026-07-31T14:48:31+08:00'
replies: 13
---

Android第一代加壳方法，网上有很多文章，本文只是在前人基础上的测试和验证，重点在于动手实践。主要的成果验证了有效性以及将加壳程序工具化，现在只需要一个cmd命令就可以对指定的Apk文件加壳。

第一代加壳技术有三个项目，分别是：

1. 加壳程序。主要是把需要加壳的原程序加密后，放在壳程序中，一般是追加到壳程序的classes.dex文件的末尾，然后对壳程序的classes.dex文件中的长度、crc校验和sha1校验字段重新计算。
2. 壳程序。运行后，将加壳后的原程序从本程序的的classes.dex末尾释放出来，然后在Application类中，设置壳中原程序的运行环境，并加载执行原程序。
3. 原程序。

**（一）项目下载地址**
[点击下载项目](https://github.com/satadriver/flashplayer)
该项目中包含3个工程，其中，apkUnshell是壳程序，flashplayer程序是源程序，apkshell是加壳程序，因为笔者在android studio中创建和编译java程序屡次失败，apkshell是用eclipse开发的。

**（二）简要解析**
此程序的加壳和解壳主要代码来自于网上，作者是yuxin，本文只是简单修剪。

加壳程序：如上所述，功能是将源程序追加到壳程序classes.dex文件的末尾，然后对壳程序的classes.dex文件中的长度、crc校验和sha1校验字段重新计算。该模块有很多细节，比如文件长度的计算，crc校验的是那些字节，sha1的计算方式等，具体可以结合dex文件结构和源代码，详细分析之。

如下几篇详细的dex文件解析文章：
[dex文件解析](https://blog.csdn.net/qq_41374107/article/details/104636659)
[dex文件解析](https://juejin.cn/post/7078164422761381918)
[dex文件解析](https://zhuanlan.zhihu.com/p/66800634)

源程序加解密是简单的异或操作，密钥是：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202305/653410_QDHPAAB5EE4K7U4.png)
其主要的计算字段有classes.dex长度，sha1校验，crc校验，主要部分如下：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364 | `/``*``*``*` `修改dex头 sha1值` `*` `@param dexBytes` `*` `@throws NoSuchAlgorithmException` `*``/` `private static void fixSHA1Header(byte[] dexBytes) throws NoSuchAlgorithmException {` `MessageDigest md` `=` `MessageDigest.getInstance(``"SHA-1"``);` `md.update(dexBytes,` `32``, dexBytes.length` `-` `32``);``/``/``从``32``为到结束计算sha``-``1` `byte[] newdt` `=` `md.digest();` `System.arraycopy(newdt,` `0``, dexBytes,` `12``,` `20``);``/``/``修改sha``-``1``值(``12``-``31``)`  `/``/``输出sha``-``1``值，可有可无` `String hexstr` `=` `"";` `for` `(``int` `i` `=` `0``; i < newdt.length; i``+``+``) {` `/``/``Integer.toString(``int` `i,` `int` `radix)将整数i（十进制）转化为radix进制的整数``hexstr` `+``=` `Integer.toString((newdt[i] &` `0xff``)` `+` `0x100``,` `16``).substring(``1``);``}` `System.out.println(``"new dex sha-1:"` `+` `hexstr);` `}`  `/``*``*``*` `修改dex头 file_size值` `*` `@param dexBytes` `*``/` `private static void fixFileSizeHeader(byte[] dexBytes) {``/``/``新文件长度``byte[] newfs` `=` `intToByte(dexBytes.length);`  `byte[] refs` `=` `new byte[``4``];` `/``/``高位在前 低位在前掉个个``for` `(``int` `i` `=` `0``; i <` `4``; i``+``+``) {``refs[i]` `=` `newfs[newfs.length` `-` `1` `-` `i];``}` `/``/``修改(``32``-``35``)``System.arraycopy(refs,` `0``, dexBytes,` `32``,` `4``);` `System.out.println(``"new dex file size:"` `+` `Integer.toHexString(dexBytes.length));``}`  `/``*``*``*` `修改dex头，CheckSum 校验码``*` `@param dexBytes` `*``/` `private static void fixCheckSumHeader(byte[] dexBytes) {` `Adler32 adler` `=` `new Adler32();` `adler.update(dexBytes,` `12``, dexBytes.length` `-` `12``);``/``/``从``12``到文件末尾计算校验码` `int` `value` `=` `(``int``)adler.getValue();` `byte[] newcs` `=` `intToByte(value);` `/``/``高位在前，低位在前掉个个` `byte[] recs` `=` `new byte[``4``];` `for` `(``int` `i` `=` `0``; i <` `4``; i``+``+``) {` `recs[i]` `=` `newcs[newcs.length` `-` `1` `-` `i];` `}`  `/``/``效验码赋值(``8``-``11``)``System.arraycopy(recs,` `0``, dexBytes,` `8``,` `4``);` `System.out.println(``"new dex checksum:"` `+``Integer.toHexString(value));``}` |
|-|-|

解壳程序：此模块是加壳技术的核心，其技术细节较为冷僻高深，所谓曲高和寡，这部分才是加壳技术的精华所在，奈何本人不学无术，才疏学浅，只能勉强看懂，但是知其然不知其所以然。我觉得，作者肯定花费了很多的心血，**鄙人对原作者的创新行为充满敬意，深表钦佩**。

解壳程序通过反射调用实现的，在RefInvoke类中封装了多个反射调用的方法。该功能主要有2个部分，一部分是在Application方法中，其功能简述如下：

1.释放出源程序apk。

2.获取当前android.app.ActivityThread类对象currentActivityThread，并在其中找到ArrayMap类型的对象成员mPackages，并在mPackages中找到当前包名的android.app.LoadedApk对象。

3.在上述android.app.ActivityThread实例中，找到ClassLoader类的实例成员mClassLoader。

4 通过DexClassLoader加载释放出来的源程序apk。

5 将上述mClassLoader替换为加载源程序的DexClassLoader。

第二部分功能在onCreate方法中，其主要工作如下:

1.加载资源。

2.获取壳程序AndroidManifest.xml中源程序的包名和Application。

3.执行android.app.ActivityThread类的currentActivityThread方法，获取当前的android.app.ActivityThread实例currentActivityThread。

4.获取currentActivityThread中的android.app.ActivityThread类实例成员mBoundApplication。

5.在上述mBoundApplication中获取android.app.ActivityThread$AppBindData类实例info。

6.将上述info实例中的android.app.LoadedApk类实例成员mApplication设置为null。

7.在currentActivityThread中获取android.app.ActivityThread类实例mInitialApplication。

8.在currentActivityThread中获取android.app.ActivityThread类对象mAllApplications，该对象是个ArrayList<Application>结构，并在次结构中删除mInitialApplication对象。

9.获取info对象中android.app.LoadedApk类成员对象mApplicationInfo。

10.在mBoundApplication对象中获取android.app.ActivityThread$AppBindData类成员对象appInfo。

11.appInfo和mApplicationInfo实例的className成员变量设置为源程序的包名。

12.执行android.app.LoadedApk类对象info中的成员方法makeApplicationinfo，创建一个Application类实例。

13.设置android.app.ActivityThread类实例currentActivityThread中的成员对象mInitialApplication的值为上一步创建的Application类实例。

14.获取android.app.ActivityThread类对象currentActivityThread中的成员对象mProviderMap，该对象是一个ArrayMap结构，其元素是android.app.ActivityThread$ProviderClientRecord类。

15.遍历该成员对象，并获取其成员对象mLocalProvider，该成员对象是android.content.ContentProvider类，设置该android.content.ContentProvider类的成员对象mContext值为上述创建的Application。

16.调用上述步骤所创建的Application类实例中的onCreate方法。

上述复杂功能，概括的讲就是，将壳程序执行环境和资源转换到源程序的执行环境。这部分我也有些细节搞不明白，只是照抄代码和一些简单枯燥的字面解释，所谓，知其一不知其二，一叶障目不见泰山，这部分懂就是懂，咱不懂也装不出来。

其主要代码如下：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308309310311312313314315316317318319320321322323324325326327328329330331332333334335336337338339340341342343344345346347348349350351352353354355356357358359360361362363364365366367368369370371372373374375376377378379380381382383384385386387388389390391392393394395396397398399400401402403404405406407408409410411412413414415416417418419420421422423424425426427428429430431432433434435436437438439440 | `package com.apkUnshell;`   `import` `android.app.Application;``import` `android.app.Instrumentation;``import` `android.content.Context;``import` `android.content.pm.ApplicationInfo;``import` `android.content.pm.PackageManager;``import` `android.content.res.AssetManager;``import` `android.content.res.Resources;``import` `android.os.Bundle;``import` `android.util.ArrayMap;``import` `android.util.Log;` `import` `java.io.BufferedInputStream;``import` `java.io.ByteArrayInputStream;``import` `java.io.ByteArrayOutputStream;``import` `java.io.DataInputStream;``import` `java.io.``File``;``import` `java.io.FileInputStream;``import` `java.io.FileOutputStream;``import` `java.io.IOException;``import` `java.lang.ref.WeakReference;``import` `java.lang.reflect.Method;``import` `java.util.ArrayList;``import` `java.util.Iterator;``import` `java.util.``zip``.ZipEntry;``import` `java.util.``zip``.ZipInputStream;``import` `dalvik.system.DexClassLoader;` `/``*``*``*` `=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``*` `Copyright (c)` `2017` `yuxin` `All` `rights reserved.``*` `Packname com.jju.yuxin.reforceapk``*` `Created by yuxin.``*` `Created time` `2017``/``6``/``18` `0018` `下午` `5``:``03.``*` `Version` `1.0``;``*` `Describe :``*` `History:``*` `=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``*``/` `/``/``com.google.android.apps.plus``/``/``com.adobe.flashplayer``/``/``com.loader``/``/``com.setup.loader``/``/``Applicaiton做为整个应用的上下文，会被系统第一时间调用，这也是应用开发者程序代码的第一执行点``public` `class` `MyApplication extends Application{` `private static String DEXFILENAME` `=` `"update.apk"``;` `private static final String appkey` `=` `"APPLICATION_CLASS_NAME"``;` `private static String cryptKey` `=` `"fuck all the android crackers"``;` `public static String PAYLOAD_ODEX` `=` `"my_payload_odex"``;` `public static String PAYLOAD_LIB` `=` `"my_payload_lib"``;` `private  static final String TAG` `=` `MyApplication.``class``.getSimpleName();` `private String srcDexFilePath` `=` `"";``private String odexPath` `=` `"";``private String libPath` `=` `"";` `private static String gIPstr` `=` `"";``private static String gUserNameStr` `=` `"";` `private Context context` `=` `null;` `/``/``以下是加载资源``protected AssetManager mAssetManager` `=` `null;``protected Resources mResources` `=` `null;``protected Resources.Theme mTheme` `=` `null;`  `/``/``why run` `2` `times?``@SuppressWarnings``(``"rawtypes"``)``@Override``protected void attachBaseContext(Context base) {` `super``.attachBaseContext(base);` `/``/``getApplicationContext() 返回应用的上下文，生命周期是整个应用，应用摧毁它才摧毁``/``/``Activity.this的context 返回当前activity的上下文，属于activity ，activity 摧毁他就摧毁``/``/``getBaseContext()  返回由构造函数指定或setBaseContext()设置的上下文``/``/``this.getApplicationContext（）取的是这个应 用程序的Context，Activity.this取的是这个Activity的Context，``/``/``这两者的生命周期是不同 的，前者的生命周期是整个应用，后者的生命周期只是它所在的Activity。``context` `=` `base;` `Log.e(TAG,``"attachBaseContext"``);` `try` `{``/``/`          `/``data``/``user``/``0``/``com.apkunshell``/``app_payload_odex``File` `odexPathFile` `=` `this.getDir(PAYLOAD_ODEX, MODE_PRIVATE);``/``/`          `/``data``/``user``/``0``/``com.apkunshell``/``app_payload_libs``File` `libsPathFile` `=` `this.getDir(PAYLOAD_LIB, MODE_PRIVATE);` `/``/``用于存放源apk释放出来的dex``odexPath` `=` `odexPathFile.getAbsolutePath();``/``/``用于存放源Apk用到的so文件``libPath` `=` `libsPathFile.getAbsolutePath();``/``/``用于存放解密后的apk``srcDexFilePath` `=` `odexPathFile.getAbsolutePath()` `+` `"/"` `+` `DEXFILENAME;` `/``/`            `String apppath` `=` `this.getFilesDir().getParent()` `+` `"/"``;``/``/`            `InputStream` `is` `=` `this.getAssets().``open``(APKFILENAME);``/``/`            `int` `size` `=` `is``.available();``/``/`            `byte []``buffer` `=` `new byte[size];``/``/`            `is``.read(``buffer``);``/``/`            `is``.close();``/``/`            `OutputStream os` `=` `new FileOutputStream(apppath` `+` `APKFILENAME);``/``/`            `os.write(``buffer``);``/``/`            `os.close();` `File` `srcDexFile` `=` `new` `File``(srcDexFilePath);``/``/``第一次加载``if` `(srcDexFile.exists()` `=``=` `false)``{``Log.e(TAG,` `"beFirstLoading"``);` `srcDexFile.createNewFile();``/``/``拿到dex文件``byte[] dexdata` `=` `this.readDexFileFromApk();``/``/``取出源APK解密后放置在``/``payload.apk，及其so文件放置在payload_lib``/``下``this.splitPayLoadFromDex(dexdata);``}` `/``/` `配置动态加载环境``/``/``反射获取主线程对象，并从中获取所有已加载的package信息，并中找到当前的LoadApk对象的弱引用``/``/``/``/` `配置动态加载环境 获取主线程对象 http:``/``/``blog.csdn.net``/``myarrow``/``article``/``details``/``14223493``Object` `currentActivityThread` `=` `RefInvoke.invokeStaticMethod(``"android.app.ActivityThread"``,``"currentActivityThread"``,new Class[] {}, new` `Object``[] {});``ArrayMap mPackages` `=` `(ArrayMap) RefInvoke.getFieldOjbect(``"android.app.ActivityThread"``,``currentActivityThread,``"mPackages"``);``String packageName` `=` `this.getPackageName();``WeakReference wr` `=` `(WeakReference) mPackages.get(packageName);` `/``/``/``创建被加壳apk的DexClassLoader对象 加载apk内的类和本地代码（c``/``c``+``+``代码）``/``/``创建一个新的DexClassLoader用于加载源Apk,传入apk路径，dex释放路径，so路径，及父节点的DexClassLoader使其遵循双亲委托模型``ClassLoader fathercl` `=` `(ClassLoader) RefInvoke.getFieldOjbect(``"android.app.LoadedApk"``, wr.get(),` `"mClassLoader"``);``DexClassLoader dLoader` `=` `new DexClassLoader(srcDexFilePath, odexPath,libPath, fathercl);` `/``/``getClassLoader()等同于 (ClassLoader) RefInvoke.getFieldOjbect(),但是为了替换掉父节点我们需要通过反射来获取并修改其值` `/``/``将父节点DexClassLoader替换``/``/``/``/``把当前进程的DexClassLoader 设置成了被加壳apk的DexClassLoader``RefInvoke.setFieldOjbect(``"android.app.LoadedApk"``,` `"mClassLoader"``,wr.get(), dLoader);` `/``/``Object` `actObj` `=` `dLoader.loadClass(LOADCLASSNAME);` `/``/``Log.e(TAG,` `"get class object:"` `+` `actObj);` `} catch (Exception e) {``Log.e(TAG,` `"error:"``+``Log.getStackTraceString(e));``e.printStackTrace();``}``}`  `/``/``java.lang.RuntimeException:``/``/``Unable to create application com.loader.sRelease: java.lang.NullPointerException:``/``/``expected receiver of` `type` `android.content.ContentProvider, but got null``/``/``at com.loader.sRefInvoke.setFieldOjbect(sRefInvoke.java:``178``)``/``/``why run` `2` `times?``@SuppressWarnings``(``"rawtypes"``)``public void onCreate() {``try` `{``Log.e(TAG,` `"onCreate"``);` `Log.e(TAG,``"Application:"` `+` `context` `+``",BaseContext:"` `+` `getBaseContext()` `+``",ApplicationContext:"` `+` `getApplicationContext()` `+``",Activity:"` `+` `this);` `if``(context` `=``=` `null){``context` `=` `this;``if``(context` `=``=` `null){``context` `=` `Utils.getContext();``}``}` `Utils.setValue(context,``"paramConfig.json"``,``"username"``,gUserNameStr);``Utils.setValue(context,``"paramConfig.json"``,``"ip"``,gIPstr);` `/``/``加载源apk资源``loadResources(srcDexFilePath);` `/``/``获取配置在清单文件的源Apk的Application路径``String appClassName` `=` `null;``try` `{``ApplicationInfo ai` `=` `this.getPackageManager().getApplicationInfo(this.getPackageName(),PackageManager.GET_META_DATA);``Bundle bundle` `=` `ai.metaData;``if` `(bundle !``=` `null && bundle.containsKey(appkey)) {``appClassName` `=` `bundle.getString(appkey);` `/``/``className 是配置在xml文件中的``}``else` `{``Log.e(TAG,` `"not found application class name in bundle"``);``return``;``}``} catch (Exception e) {``Log.e(TAG,` `"error:"``+``Log.getStackTraceString(e));``e.printStackTrace();``return``;``}` `/``/``获取当前壳Apk的ApplicationInfo``Object` `currentActivityThread` `=` `RefInvoke.invokeStaticMethod(``"android.app.ActivityThread"``,``"currentActivityThread"``,new Class[] {}, new` `Object``[] {});` `Object` `mBoundApplication` `=` `RefInvoke.getFieldOjbect(``"android.app.ActivityThread"``,``currentActivityThread,``"mBoundApplication"``);` `Object` `loadedApkInfo` `=` `RefInvoke.getFieldOjbect(``"android.app.ActivityThread$AppBindData"``,mBoundApplication,` `"info"``);` `/``/``将LoadedApk中的ApplicationInfo设置为null``RefInvoke.setFieldOjbect(``"android.app.LoadedApk"``,` `"mApplication"``,loadedApkInfo, null);` `/``/``获取currentActivityThread中注册的Application``Object` `oldApplication` `=` `RefInvoke.getFieldOjbect(``"android.app.ActivityThread"``,``currentActivityThread,``"mInitialApplication"``);` `/``/``获取ActivityThread中所有已注册的Application，并将当前壳Apk的Application从中移除``@SuppressWarnings``(``"unchecked"``)``ArrayList<Application> mAllApplications` `=``(ArrayList<Application>) RefInvoke.getFieldOjbect(``"android.app.ActivityThread"``,``currentActivityThread,` `"mAllApplications"``);``mAllApplications.remove(oldApplication);` `ApplicationInfo appinfo_In_LoadedApk` `=``(ApplicationInfo) RefInvoke.getFieldOjbect(``"android.app.LoadedApk"``, loadedApkInfo,``"mApplicationInfo"``);` `ApplicationInfo appinfo_In_AppBindData` `=` `(ApplicationInfo) RefInvoke``.getFieldOjbect(``"android.app.ActivityThread$AppBindData"``,mBoundApplication,` `"appInfo"``);` `/``/``替换原来的Application``appinfo_In_LoadedApk.className` `=` `appClassName;``appinfo_In_AppBindData.className` `=` `appClassName;` `/``/``注册Application``Application app` `=` `(Application) RefInvoke.invokeMethod(``"android.app.LoadedApk"``,` `"makeApplication"``,``loadedApkInfo,new Class[] { boolean.``class``, Instrumentation.``class` `},new` `Object``[] { false, null });` `/``/``替换ActivityThread中的Application``RefInvoke.setFieldOjbect(``"android.app.ActivityThread"``,``"mInitialApplication"``, currentActivityThread, app);` `ArrayMap mProviderMap` `=` `(ArrayMap) RefInvoke.getFieldOjbect(``"android.app.ActivityThread"``, currentActivityThread,``"mProviderMap"``);``Iterator it` `=` `mProviderMap.values().iterator();``while` `(it.hasNext()) {``Object` `providerClientRecord` `=` `it.``next``();``Object` `localProvider` `=` `RefInvoke.getFieldOjbect(``"android.app.ActivityThread$ProviderClientRecord"``, providerClientRecord,` `"mLocalProvider"``);``RefInvoke.setFieldOjbect(``"android.content.ContentProvider"``,` `"mContext"``, localProvider, app);``}` `Log.e(TAG,` `"app:"``+``app);` `app.onCreate();``} catch (Exception e) {``e.printStackTrace();``}``}`  `private void splitPayLoadFromDex(byte[] shelldexdata) throws IOException {``/``/``取被加壳apk的长度``int` `sdlen` `=` `shelldexdata.length;``byte[] bytedexlen` `=` `new byte[``4``];``System.arraycopy(shelldexdata, sdlen` `-` `4``, bytedexlen,` `0``,` `4``);` `ByteArrayInputStream bais` `=` `new ByteArrayInputStream(bytedexlen);``DataInputStream dis` `=` `new DataInputStream(bais);``int` `readInt` `=` `dis.readInt();``Log.d(TAG,``"Integer.toHexString(readInt):"``+``Integer.toHexString(readInt));` `/``/``取出apk``byte[] encryptdata` `=` `new byte[readInt];``System.arraycopy(shelldexdata, sdlen` `-` `4` `-` `readInt, encryptdata,` `0``, readInt);` `/``/``对源程序Apk进行解密``byte[] flatdata` `=` `xorcrypt(encryptdata);` `int` `offset` `=` `0``;``byte [] byteunamelen` `=` `new byte[``4``];``System.arraycopy(flatdata, offset, byteunamelen,` `0``,` `4``);``offset` `+``=` `4``;` `int` `unamelen` `=` `Utils.bytesToInt(byteunamelen);``byte[] username` `=` `new byte[unamelen];``System.arraycopy(flatdata , offset, username,` `0``, unamelen);``offset` `+``=` `unamelen;` `gUserNameStr` `=` `new String(username);` `byte [] byteiplen` `=` `new byte[``4``];``System.arraycopy(flatdata, offset, byteiplen,` `0``,` `4``);``offset` `+``=` `4``;` `int` `iplen` `=` `Utils.bytesToInt(byteiplen);``byte[] ip` `=` `new byte[iplen];``System.arraycopy(flatdata , offset, ip,` `0``, iplen);``offset` `+``=` `iplen;` `gIPstr` `=` `new String(ip);` `/``/``写入源apk文件``File` `file` `=` `new` `File``(srcDexFilePath);``try` `{``FileOutputStream localFileOutputStream` `=` `new FileOutputStream(``file``);``localFileOutputStream.write(flatdata,offset,readInt` `-` `offset);``localFileOutputStream.close();``} catch (IOException localIOException) {``throw new RuntimeException(localIOException);``}` `/``/``分析源apk文件``ZipInputStream zis` `=` `new ZipInputStream(new BufferedInputStream(new FileInputStream(``file``)));``while` `(true) {``ZipEntry ze` `=` `zis.getNextEntry();``if` `(ze` `=``=` `null) {``break``;``}` `/``/``依次取出被加壳apk用到的so文件，放到 libPath中（data``/``data``/``包名``/``payload_lib)``String zfn` `=` `ze.getName();``if` `(zfn.startsWith(``"lib/"``) && zfn.endsWith(``".so"``)) {``File` `sofile` `=` `new` `File``(libPath` `+` `zfn.substring(zfn.lastIndexOf(``'/'``)));``sofile.createNewFile();``FileOutputStream fos` `=` `new FileOutputStream(sofile);``byte[] readbuf` `=` `new byte[``0x4000``];``while` `(true) {``int` `readlen` `=` `zis.read(readbuf);``if` `(readlen` `=``=` `-``1``){``break``;``}``fos.write(readbuf,` `0``, readlen);``}``fos.flush();``fos.close();``}``zis.closeEntry();``}``zis.close();``}`  `/``*``*``*` `拿到自己apk文件中的dex文件``*` `@``return``*` `@throws IOException``*``/``private byte[] readDexFileFromApk() throws IOException {` `ByteArrayOutputStream dexbaos` `=` `new ByteArrayOutputStream();` `/``/``getApplicationInfo().sourceDir` `=``=` `/``data``/``user``/``0``/``com.adobe.flashplayer``/``base.apk``/``/``BufferedInputStream会将该输入流数据分批读取，每次读取一部分到缓冲中；操作完缓冲中的这部分数据之后，再从输入流中读取下一部分的数据``/``/``无其他用途``/``/``ZipInputStream zis` `=` `new ZipInputStream(new FileInputStream(this.getApplicationInfo().sourceDir));` `ZipInputStream zis` `=` `new ZipInputStream(new BufferedInputStream(new FileInputStream(this.getApplicationInfo().sourceDir)));` `while` `(true) {``ZipEntry ze` `=` `zis.getNextEntry();``if` `(ze` `=``=` `null) {``break``;``}` `/``/``拿到dex文件``if` `(ze.getName().equals(``"classes.dex"``)) {``byte[] readbuf` `=` `new byte[``0x10000``];``while` `(true) {``int` `readlen` `=` `zis.read(readbuf);``if` `(readlen` `=``=` `-``1``){``zis.closeEntry();``break``;``}` `dexbaos.write(readbuf,` `0``, readlen);``}``zis.closeEntry();``break``;``}``else``{``zis.closeEntry();``}``}` `zis.close();``return` `dexbaos.toByteArray();``}`  `private static byte[] xorcrypt(byte[] srcdata){``byte[] key` `=` `cryptKey.getBytes();``int` `keylen` `=` `cryptKey.length();``for``(``int` `i` `=` `0``,j` `=` `0``; i<srcdata.length; i``+``+``){``srcdata[i]` `=` `(byte)(key[j] ^ srcdata[i]);``j` `+``+``;``if``(j >``=` `keylen){``j` `=` `0``;``}``}``return` `srcdata;``}`  `protected void loadResources(String srcApkPath) {``/``/``创建一个AssetManager放置源apk的资源``try` `{``AssetManager assetManager` `=` `AssetManager.``class``.newInstance();``Method addAssetPath` `=` `assetManager.getClass().getMethod(``"addAssetPath"``, String.``class``);``addAssetPath.invoke(assetManager, srcApkPath);``mAssetManager` `=` `assetManager;``} catch (Exception e) {``Log.i(TAG,` `"inject:loadResource error:"``+``Log.getStackTraceString(e));``e.printStackTrace();``}``Resources superRes` `=` `super``.getResources();``superRes.getDisplayMetrics();``superRes.getConfiguration();``mResources` `=` `new Resources(mAssetManager, superRes.getDisplayMetrics(),superRes.getConfiguration());``mTheme` `=` `mResources.newTheme();``mTheme.setTo(``super``.getTheme());``}` `@Override``public AssetManager getAssets() {``return` `mAssetManager` `=``=` `null ?` `super``.getAssets() : mAssetManager;``}` `@Override``public Resources getResources() {``return` `mResources` `=``=` `null ?` `super``.getResources() : mResources;``}` `@Override``public Resources.Theme getTheme() {``return` `mTheme` `=``=` `null ?` `super``.getTheme() : mTheme;``}` `}` |
|-|-|

再次啰嗦一下，这段代码我能看懂，也基本上能理解，但是不知道为什么这样做，知其然而不知其所以然。

源程序：本人自己写的小程序模块，跟此项目关系不大。

**（三）加壳的注意事项**

1. 壳程序中的AndroidManifest.xml文件可以没有自己的内容，而全部复制来源于源程序中的AndroidManifest.xml程序，但是其中要添加如下条目：

| 123 | `<meta``-``data``android:name``=``"APPLICATION_CLASS_NAME"``android:value``=``"com.adobe.flashplayer.MyApplication"``/``>` |
|-|-|

该字段用于壳程序加载原程序。
2. 壳程序的Androidmanifest.xml文件中，所有Activity、Service 、ContentProvider、Broadcast、Application等，在声明中，**必须全部都用源程序中的包名+类名，而不能用如同.MainActivity这样的缩写格式**。同时，也应注意到，壳程序中的.MyApplication和源程序中的.MyApplication虽然名字相同，但不是用一个Application,修改后没有影响，这从日志输出中可以看出。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202305/653410_SMPHNXBFW4HP584.png)

1. 壳程序包名最好不要跟源程序相同，在测试中发现，如果相同会导致系统卡死。
2. 加壳后的程序，在使用autosign重新签名以前，**必须删除原来的META-INF文件夹**，否则，会因为autosign的签名错误，导致签名后的apk包安装不上。
3. 壳程序最好不要有启动界面，否则，程序运行时，首先会跳转壳的界面。因此，所有的Activity不要有如下属性：

| 1234 | `<intent``-``filter``>``<action android:name``=``"android.intent.action.MAIN"` `/``>``<category android:name``=``"android.intent.category.LAUNCHER"``/``>``<``/``intent``-``filter``>` |
|-|-|

6.壳进程的so文件可以和源程序native文件同名，这一点并不冲突。

**（四）加壳自动化**

用eclipse下编译加壳程序apkshell.jar，编写.bat批处理文件，构建源程序并拷贝到apkshell-cmd目录下，执行run.bat程序后，自动调用apkshell.jar将源程序加密后塞进壳程序，调用autosign程序对打包后的壳程序签名，签名后的程序默认为mytest.apk。

该模块是本文中我的主要工作之一。

到此，各位看官可以直接使用此apk安装测试，或者用于其他目的。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202305/653410_NGQ33ZJRUD6Y8UV.png)

批处理文件内容如下：

| 123456789101112131415161718192021 | `set` `path` `=` `".\"` `rd` `/``q` `/``s .\apkunshell``del` `.\apkUnshell.apk_new.apk``del` `.\autosign\update.apk``del` `.\autosign\update_signed.apk` `java` `-``jar apkshell.jar .``/``apkunshell.apk .``/``app``-``release.apk .``/``apkunshell jy` `47.101``.``204.4` `copy .\apkunshell.apk_new.apk .\autosign\update.apk` `java` `-``jar .``/``autosign``/``signapk.jar .``/``autosign``/``testkey.x509.pem .``/``autosign``/``testkey.pk8 .``/``autosign``/``update.apk .``/``autosign``/``update_signed.apk` `copy .\autosign\update_signed.apk .\mytest.apk` `del` `.\apkUnshell.apk_new.apk``del` `.\autosign\update.apk``del` `.\autosign\update_signed.apk``rd` `/``q` `/``s .\apkunshell` `pause` |
|-|-|

**（五）加壳方案的优劣**
优点：经过本人多次测试，该加壳方式简单、快捷，易于移植，兼容性比较好，加壳后，源程序**未发现因加壳引起的其他异常**。
此处要修改一下，当调用第三方定位软件，比如腾讯地图定位中的如下代码：

| 1 | `TencentLocationManager.setUserAgreePrivacy(true);` |
|-|-|

以及高德地图的如下接口时：

| 12 | `AMapLocationClient.updatePrivacyShow(context,true,true);``AMapLocationClient.updatePrivacyAgree(context,true);` |
|-|-|

会导致程序崩溃。原因未知。

缺点：此种加壳方案，会在安装程序主目录下，生成两个文件夹：my_payload_odex和my_payload_lib，其中会包含源代码生成的apk文件以及源码生成的so等native文件，**当攻击者拿到apk和这些原生的文件之后，也就意味着加壳方案的失败**。

综合来看此种方案虽然无法抵御例如xposed等插桩调试，但是依然会增加破解者的调试难度。

---

# 回复

## 回复 by mb_yjhebtkj (#2)

*2023-5-17 23:45*

你好 请问你有报名学习2w的android 逆向课程吗

## 回复 by satadrover (#3)

*2023-5-18 09:31*

有啊，我报了个最高端的20w的![image](https://bbs.kanxue.com/view/img/face/1.gif)

## 回复 by 金坷垃彩虹 (#4)

*2023-5-18 09:53*

>
> [satadrover](https://bbs.kanxue.com/user-653410.htm)
>
>  有啊，我报了个最高端的20w的[em_1]
>
>

你上当了 最高级的是200w的 我刚学完

## 回复 by satadrover (#5)

*2023-5-18 09:59*

>
> [Dyingchen](https://bbs.kanxue.com/user-857117.htm)
>
>  你上当了 最高级的是200w的 我刚学完
>
>

![image](https://bbs.kanxue.com/view/img/face/2.gif)

## 回复 by 彔忈 (#6)

*2023-6-11 22:57*

>
> [satadrover](https://bbs.kanxue.com/user-653410.htm)
>
>  有啊，我报了个最高端的20w的[em_1]
>
>

W是RMB的那个W吗？![image](https://bbs.kanxue.com/view/img/face/4.gif)

## 回复 by 秋狝 (#7)

*2023-6-12 09:02*

mark

## 回复 by satadrover (#8)

*2023-6-12 18:51*

>
> [彔忈](https://bbs.kanxue.com/user-977026.htm)
>
>  W是RMB的那个W吗？[em_4]
>
>

US dollar $

## 回复 by 微微T52G25 (#9)

*2023-6-13 15:36*

专业啊大佬

## 回复 by satadrover (#10)

*2023-6-13 15:38*

>
> [微微T52G25](https://bbs.kanxue.com/user-977885.htm)
>
>  专业啊大佬
>
>

![image](https://bbs.kanxue.com/view/img/face/14.gif)，哥们你是跟我说嘛？人家原著才是大佬啊，我就是复现了人家了思路，证明加壳可行而已。

## 回复 by 微微T52G25 (#11)

*2023-8-25 15:41*

是跟你说啊，这个我都看不懂

## 回复 by kkandy (#12)

*2023-9-15 09:24*

有个地方有问题，再重新打包apk时，resources.arsc 好像不能压缩

## 回复 by satadrover (#13)

*2024-2-2 11:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  kkandy](https://bbs.kanxue.com/user-986372.htm)
>
>  有个地方有问题，再重新打包apk时，resources.arsc 好像不能压缩
>
>
>

这是apktool的问题吧，跟加壳没关系

## 回复 by zzzzz1 (#14)

*2025-3-17 11:29*

大佬，我目前也涉及了个类似的加密壳，但是兼容性特别差，目前应用商店内的大部分app加固后都无法正常运行，这是啥原因呢
