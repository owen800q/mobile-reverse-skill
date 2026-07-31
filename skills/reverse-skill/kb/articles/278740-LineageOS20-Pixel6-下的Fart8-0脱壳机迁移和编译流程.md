---
title: '[原创]LineageOS20+Pixel6 下的Fart8.0脱壳机迁移和编译流程'
url: https://bbs.kanxue.com/thread-278740.htm
tid: 278740
author: 败类制造
date: '2023-09-05'
tags: [Android安全, 原创, 脱壳反混淆, 程序开发, 系统相关, 源码框架]
crawled_at: '2026-07-31T14:38:26+08:00'
replies: 8
---

# LineageOS20+Pixel6 下的Fart8.0脱壳机迁移和编译流程

## 一.LineageOS20源码下载和编译

### 1.选择LineageOS20系统的原因

 之前将Fart8.0的代码编译到Android13下，运行发现在将Java的Method对象转换成C的ArtMethod对象时报错，没找到原因。再加上AOSP的系统太素了，就琢磨是否可以用LineageOS来编译，所以就有了这篇文章。

 先罗列一下我的环境吧，编译环境是Kali2022,用的r0ysue大佬的集成版，手机是Pixel6，选择的系统是LineageOS20版(基于AOSP13)的，原本想用基于AOSP10的Lineage17的，但是官网同步源码后发现缺少device blob,遂决定就用20版。

### 2. LineageOS20源码下载和编译

#### 1.2.1.虚拟机设置

我的虚拟机设置了32G内存，8核CPU，500G的硬盘，实际下载编译完成占用了快300G空间。这里坑的地方在于同样的配置，我的AOSP能顺利编译完成，但在编译LineageOS时中途报错，检查原因发现是因为swap只有1G大小，在设置了swap为20G后，才编译成功。

| 12345 | `swapoff -a``dd` `if``=``/dev/zero` `of=``/var/swapfile` `bs=1M count=20480``mkswap` `/var/swapfile``swapon` `/var/swapfile``free` `-m  --查看当前分区` |
|-|-|

#### 1.2.2 编译环境配置

- 安装编译必须的组件

| 1234 | `apt-get update``apt-get` `install` `bc` `bison build-essential ccache curl flex g++-multilib gcc-multilib git git-lfs gnupg gperf imagemagick``lib32ncurses5-dev lib32readline-dev lib32z1-dev libelf-dev liblz4-tool libncurses5 libncurses5-dev``libsdl1.2-dev libssl-dev libxml2 libxml2-utils lzop pngcrush` `rsync` `schedtool squashfs-tools xsltproc zip zlib1g-dev m4` |
|-|-|

- 安装好git和 platform-tools 并配置环境变量
- 创建源码所需目录（默认在kali root账户下）

| 12 | `mkdir` `-p ~``/bin``mkdir` `-p ~``/android/lineage` |
|-|-|
- 安装repo命令行工具

| 12 | `curl https:``//storage``.googleapis.com``/git-repo-downloads/repo` `> ~``/bin/repo``chmod` `a+x ~``/bin/repo` |
|-|-|
- 将bin目录添加进环境变量。

 使用下面的命令打开~/.bashrc文件，

| 1 | `vim ~/.bashrc` |
|-|-|

 在文件最后添加下面的代码:

| 1234 | `# set PATH so it includes user's private bin if it exists``if` `[ -d` `"$HOME/bin"` `] ;` `then``PATH=``"$HOME/bin:$PATH"``fi` |
|-|-|

- 配置git

| 12 | `git config --global user.email` `"you@example.com"``#替换成你的邮件 随便写``git config --global user.name` `"Your Name"`  `#替换成你的用户名 随便写` |
|-|-|

查看git lfs是否安装

| 123 | `curl` `-``s https:``/``/``packagecloud.io``/``install``/``repositories``/``github``/``git``-``lfs``/``script.deb.sh \| sudo bash``apt``-``get install git``-``lfs``git lfs install` `#查看是否安装成功。` |
|-|-|
- 配置缓存，加快编译速度

| 12 | `export USE_CCACHE``=``1``export CCACHE_EXEC``=``/``usr``/``bin``/``ccache` |
|-|-|

可将其加入到~/.bashrc文件中，并在命令行执行下行

| 1 | `ccache` `-``M` `50G` |
|-|-|

#### 1.2.3 下载LineageOS源码

- 初始化LineageOS source repository

| 12 | `cd ~``/``android``/``lineage``repo init` `-``u https:``/``/``github.com``/``LineageOS``/``android.git` `-``b lineage``-``20.0` `-``-``git``-``lfs` |
|-|-|

这里最好不要换成国内源，因为国内源同步出来的代码，我在编译时碰到浏览器app编译失败的问题，重新从官方源同步才解决，查看清华的issue发现有同样的问题，坑死了。
- 下载源码

| 1 | `repo sync` `-``j8` |
|-|-|

上面的-j8是启动8个线程下载,可以不要，默认是4个线程。取决于你的虚拟机cpu内核数。由于网络问题，如果同步完成后报错，可根据提示，将线程数减为1，重新执行该命令即可。
- 下载设备内核代码

确保你在源码根目录下 ( <font color='red'>cd ~/android/lineage</font> )

| 12 | `source build``/``envsetup.sh``breakfast oriole` `#这里也可使用lunch 选择官方提供的机型  如果没有的你要的机型需要到git上搜索相应机型的kernel` |
|-|-|

下载源码整个过程根据网速会有1段时间，我自己搭建了科学上网的软路由，整个时间有3个小时左右。

下载完kernel源码后会报如下的错误，这是因为还没有下载device blob的缘故，暂时不用管，下载完device blob后再重新执行上面的命令即可

![image-20230905183014828](https://bbs.kanxue.com/upload/attach/202309/975093_G87MMT6NUUC8PGC.png)

#### 1.2.4 提取专有device blob

这里是个大坑。我按照官方推荐的方式直接从已经安装了LineageOS的piexl6手机上提取blob,结果有几千个文件没有找到，害的我折腾了2天。总算使用官方镜像提取成功。下面是过程。

- 创建提取目录

| 12 | `mkdir ~``/``android``/``system_dump``/``cd ~``/``android``/``system_dump``/` |
|-|-|
- 下载官方镜像 [LineageOS Downloads](https://download.lineageos.org/devices/oriole/builds)

![image-20230905185252612](https://bbs.kanxue.com/upload/attach/202309/975093_TEJ3WAR953M6URH.png)
- 从zip文件中解压出 payload.bin文件

| 1 | `unzip` `/path/to/lineage-``*.zip payload.bin` |
|-|-|
- 安装 python-protobuf

| 1 | `apt-get` `install` `python-protobuf` |
|-|-|
- 下载官方提供的导出脚本，然后用python运行脚本，注意脚本目录路径

| 12 | `git clone https:``//github``.com``/LineageOS/scripts``python scripts``/update-payload-extractor/extract``.py payload.bin --output_dir ./` |
|-|-|

成功运行后，应该能在system_dump目录下看到如下一些.img文件
![image-20230905190110559](https://bbs.kanxue.com/upload/attach/202309/975093_7QG9VSYMZHCHZPU.png)

然后使用mout命令挂载这些img文件

| 12345 | `mkdir system``/``sudo mount` `-``o ro system.img system``/``sudo mount` `-``o ro vendor.img system``/``vendor``/``sudo mount` `-``o ro product.img system``/``product``/``sudo mount` `-``o ro system_ext.img system``/``system_ext``/` |
|-|-|

- 进入<font color='red'>~/android/lineage/device/google/oriole</font>文件夹 运行如下命令 导出blob文件

| 12 | `cd` `~``/android/lineage/device/google/oriole``.``/extract-files``.sh ~``/android/system_dump/` |
|-|-|
- 重新执行如下命令

| 12 | `source` `build``/envsetup``.sh``breakfast oriole` |
|-|-|

#### 1.2.5 编译源码

| 12 | `croot``brunch oriole` |
|-|-|

编译时间在2小时左右，尤其最后阶段编译kernel会持续50多分钟，这里即使我的内存设置到了32G，也不够用，需要设置swap,而且每次修改源码再编译 都会要重新编译这个kernel，很耗费时间，暂时没找到不重复编译的办法，在XDA上看到可以下载prebuild的内核，避免重复编译，实在懒折腾了，所以没尝试。

编译成功后会在/root/android/lineage/out/target/product/oriole目录下生成boot.img 和 lineage-20.0****.zip文件。按照官方文档替换官方镜像刷机即可。
![image-20230905192434053](https://bbs.kanxue.com/upload/attach/202309/975093_4U9NJCCY89NUMGP.png)

#### 1.2.6 刷机过程

按照官方文档操作即可。实在懒翻译了

[Install LineageOS on oriole | LineageOS Wiki](https://wiki.lineageos.org/devices/oriole/install)

#### 1.2.7 源码导入AndroidStudio和CLion

为了方便修改源码，减少报错，可以将源码中的Java代码导入AndroidStudio，C语言代码导入CLionAS导入Android源码

- Java代码导入AndroidStudio

1. 先成功编译一次，再使用以下方法导入
2. 在ubuntu系统下，进入源码根目录，运行如下命令, 会在源码目录下的out/host/linux-x86/framework目录下生成了idegen.jar文件

| 123 | `source` `build``/envsetup``.sh` `mmm development``/tools/idegen/` |
|-|-|
3. 在源码根目录下继续执行如下命令，会在根目录下生成android.iml和android.ipr两个文件，这两个文件是AndroidStudio的工程配置文件

| 1 | `development``/tools/idegen/idegen``.sh` |
|-|-|

4. 安装并打开AndroidStudio，选择Open an existing Android Studio project，找到源码根目录，点击Android.ipr
5. 具体参考：<https://wuxiaolong.me/2018/08/15/AOSP3/>

我在AOSP中成功导入了AS,但在LineageOS源码中在执行到第3步时长时间卡住，等了30个小时不动，没辙只好放弃。改用VSCode编辑java代码。

- C/C++代码导入CLion

	1. 生成用于将源码导入Clion的CMakeLists.txt

| 12345 | `source build``/``envsetup.sh``#打开开关，编译时生成CMakeLists.txt``export SOONG_GEN_CMAKEFILES``=``1``export SOONG_GEN_CMAKEFILES_DEBUG``=``1``breakfast oriole` |
|-|-|

CMakeLists.txt会生成在out/development/ide/clion/art/runtime/libart-arm64-android/CMakeLists.txt

	2. 用Clion打开CMakeLists.txt
	3. tools--->cmake-->Change Project Root 选择aosp源码根路径，等解析完毕即可

### 二. Fart8.0源码迁移

#### 2.1修改Fart脱壳机的Java层代码

Java代码可按上面导入的步骤，用AS编辑

- 修改LineageOS源码的/root/android/lineage/frameworks/base/core/java/android/app/ActivityThread.java文件，将Fart8.0对应文件中添加的部分复制到该文件中，并导入对应的包，为了防止加固厂商的检测，修改了函数名和日志输出。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298 | `//add``public` `static` `Field getClassField(ClassLoader classloader, String class_name,``String filedName) {` `try` `{``Class obj_class = classloader.loadClass(class_name);``//Class.forName(class_name);``Field field = obj_class.getDeclaredField(filedName);``field.setAccessible(``true``);``return` `field;``}` `catch` `(SecurityException e) {``e.printStackTrace();``}` `catch` `(NoSuchFieldException e) {``e.printStackTrace();``}` `catch` `(IllegalArgumentException e) {``e.printStackTrace();``}` `catch` `(ClassNotFoundException e) {``e.printStackTrace();``}``return` `null``;` `}` `public` `static` `Object getClassFieldObject(ClassLoader classloader, String class_name, Object obj,``String filedName) {` `try` `{``Class obj_class = classloader.loadClass(class_name);``//Class.forName(class_name);``Field field = obj_class.getDeclaredField(filedName);``field.setAccessible(``true``);``Object result =` `null``;``result = field.get(obj);``return` `result;``}` `catch` `(SecurityException e) {``e.printStackTrace();``}` `catch` `(NoSuchFieldException e) {``e.printStackTrace();``}` `catch` `(IllegalArgumentException e) {``e.printStackTrace();``}` `catch` `(ClassNotFoundException e) {``e.printStackTrace();``}` `catch` `(IllegalAccessException e) {``e.printStackTrace();``}``return` `null``;` `}` `public` `static` `Object invokeStaticMethod(String class_name,``String method_name, Class[] pareTyple, Object[] pareVaules) {` `try` `{``Class obj_class = Class.forName(class_name);``Method method = obj_class.getMethod(method_name, pareTyple);``return` `method.invoke(``null``, pareVaules);``}` `catch` `(SecurityException e) {``e.printStackTrace();``}` `catch` `(IllegalArgumentException e) {``e.printStackTrace();``}` `catch` `(IllegalAccessException e) {``e.printStackTrace();``}` `catch` `(NoSuchMethodException e) {``e.printStackTrace();``}` `catch` `(InvocationTargetException e) {``e.printStackTrace();``}` `catch` `(ClassNotFoundException e) {``e.printStackTrace();``}``return` `null``;` `}` `public` `static` `Object getFieldOjbect(String class_name, Object obj,``String filedName) {``try` `{``Class obj_class = Class.forName(class_name);``Field field = obj_class.getDeclaredField(filedName);``field.setAccessible(``true``);``return` `field.get(obj);``}` `catch` `(SecurityException e) {``e.printStackTrace();``}` `catch` `(NoSuchFieldException e) {``e.printStackTrace();``}` `catch` `(IllegalArgumentException e) {``e.printStackTrace();``}` `catch` `(IllegalAccessException e) {``e.printStackTrace();``}` `catch` `(ClassNotFoundException e) {``e.printStackTrace();``}` `catch` `(NullPointerException e) {``e.printStackTrace();``}``return` `null``;` `}` `public` `static` `ClassLoader getClassloader() {``ClassLoader resultClassloader =` `null``;``Object currentActivityThread = invokeStaticMethod(``"android.app.ActivityThread"``,` `"currentActivityThread"``,``new` `Class[]{},` `new` `Object[]{});``Object mBoundApplication = getFieldOjbect(``"android.app.ActivityThread"``, currentActivityThread,``"mBoundApplication"``);``Application mInitialApplication = (Application) getFieldOjbect(``"android.app.ActivityThread"``,``currentActivityThread,` `"mInitialApplication"``);``Object loadedApkInfo = getFieldOjbect(``"android.app.ActivityThread$AppBindData"``,``mBoundApplication,` `"info"``);``Application mApplication = (Application) getFieldOjbect(``"android.app.LoadedApk"``, loadedApkInfo,` `"mApplication"``);``resultClassloader = mApplication.getClassLoader();``return` `resultClassloader;``}``public` `static` `void` `loadClassAndCall(ClassLoader appClassloader, String eachclassname, Method saveMethodCode) {``Class resultclass =` `null``;``Log.i(``"wayne"``,` `"go into loadClassAndCall->"` `+` `"classname:"` `+ eachclassname);``try` `{``resultclass = appClassloader.loadClass(eachclassname);``}` `catch` `(Exception e) {``e.printStackTrace();``return``;``}` `catch` `(Error e) {``e.printStackTrace();``return``;``}``if` `(resultclass !=` `null``) {``try` `{``Constructor<?> cons[] = resultclass.getDeclaredConstructors();``for` `(Constructor<?> constructor : cons) {``if` `(saveMethodCode !=` `null``) {``try` `{``saveMethodCode.invoke(``null``, constructor);``}` `catch` `(Exception e) {``e.printStackTrace();``continue``;``}` `catch` `(Error e) {``e.printStackTrace();``continue``;``}``}` `else` `{``Log.e(``"wayne"``,` `"saveMethodCode is null "``);``}` `}``}` `catch` `(Exception e) {``e.printStackTrace();``}` `catch` `(Error e) {``e.printStackTrace();``}``try` `{``Method[] methods = resultclass.getDeclaredMethods();``if` `(methods !=` `null``) {``for` `(Method m : methods) {``if` `(saveMethodCode !=` `null``) {``try` `{``saveMethodCode.invoke(``null``, m);``}` `catch` `(Exception e) {``e.printStackTrace();``continue``;``}` `catch` `(Error e) {``e.printStackTrace();``continue``;``}``}` `else` `{``Log.e(``"wayne"``,` `"saveMethodCode is null "``);``}``}``}``}` `catch` `(Exception e) {``e.printStackTrace();``}` `catch` `(Error e) {``e.printStackTrace();``}``}``}``public` `static` `void` `wayne() {``ClassLoader appClassloader = getClassloader();``ClassLoader tmpClassloader=appClassloader;``ClassLoader parentClassloader=appClassloader.getParent();``if``(appClassloader.toString().indexOf(``"java.lang.BootClassLoader"``)==-``1``)``{``wayneDoWithClassloader(appClassloader);``}``while``(parentClassloader!=``null``){``if``(parentClassloader.toString().indexOf(``"java.lang.BootClassLoader"``)==-``1``)``{``wayneDoWithClassloader(parentClassloader);``}``tmpClassloader=parentClassloader;``parentClassloader=parentClassloader.getParent();``}``}``public` `static` `void` `wayneDoWithClassloader(ClassLoader appClassloader) {``List<Object> dexFilesArray =` `new` `ArrayList<Object>();``Field pathList_Field = (Field) getClassField(appClassloader,` `"dalvik.system.BaseDexClassLoader"``,` `"pathList"``);``Object pathList_object = getFieldOjbect(``"dalvik.system.BaseDexClassLoader"``, appClassloader,` `"pathList"``);``Object[] ElementsArray = (Object[]) getFieldOjbect(``"dalvik.system.DexPathList"``, pathList_object,` `"dexElements"``);``Field dexFile_fileField =` `null``;``try` `{``dexFile_fileField = (Field) getClassField(appClassloader,` `"dalvik.system.DexPathList$Element"``,` `"dexFile"``);``}` `catch` `(Exception e) {``e.printStackTrace();``}` `catch` `(Error e) {``e.printStackTrace();``}``Class DexFileClazz =` `null``;``try` `{``DexFileClazz = appClassloader.loadClass(``"dalvik.system.DexFile"``);``}` `catch` `(Exception e) {``e.printStackTrace();``}` `catch` `(Error e) {``e.printStackTrace();``}``Method _getClassNameList =` `null``;``Method _saveMethodCode =` `null``;` `for` `(Method field : DexFileClazz.getDeclaredMethods()) {``if` `(field.getName().equals(``"getClassNameList"``)) {``_getClassNameList = field;``_getClassNameList.setAccessible(``true``);``}``if` `(field.getName().equals(``"saveMethodCode"``)) {``_saveMethodCode = field;``_saveMethodCode.setAccessible(``true``);``}``}``Field mCookiefield = getClassField(appClassloader,` `"dalvik.system.DexFile"``,` `"mCookie"``);``Log.e(``"wayne->methods"``,` `"dalvik.system.DexPathList.ElementsArray.length:"` `+ ElementsArray.length);``//5个``for` `(``int` `j =` `0``; j < ElementsArray.length; j++) {``Object element = ElementsArray[j];``Object dexfile =` `null``;``try` `{``dexfile = (Object) dexFile_fileField.get(element);``}` `catch` `(Exception e) {``e.printStackTrace();``}` `catch` `(Error e) {``e.printStackTrace();``}``if` `(dexfile ==` `null``) {``Log.e(``"ActivityThread"``,` `"dexfile is null"``);``continue``;``}``if` `(dexfile !=` `null``) {``dexFilesArray.add(dexfile);``Object mcookie = getClassFieldObject(appClassloader,` `"dalvik.system.DexFile"``, dexfile,` `"mCookie"``);``if` `(mcookie ==` `null``) {``Object mInternalCookie = getClassFieldObject(appClassloader,` `"dalvik.system.DexFile"``, dexfile,` `"mInternalCookie"``);``if``(mInternalCookie!=``null``)``{``mcookie=mInternalCookie;``}``else``{``Log.e(``"wayne->err"``,` `"get mInternalCookie is null"``);``continue``;``}` `}``String[] classnames =` `null``;``try` `{``classnames = (String[]) _getClassNameList.invoke(dexfile, mcookie);``}` `catch` `(Exception e) {``e.printStackTrace();``continue``;``}` `catch` `(Error e) {``e.printStackTrace();``continue``;``}``if` `(classnames !=` `null``) {``for` `(String eachclassname : classnames) {``loadClassAndCall(appClassloader, eachclassname, _saveMethodCode);``}``}` `}``}``return``;``}` `public` `static` `void` `wayneThread() {``new` `Thread(``new` `Runnable() {` `@Override``public` `void` `run() {``// TODO Auto-generated method stub``try` `{``Log.e(``"wayne"``,` `"start sleep......"``);``Thread.sleep(``1` `*` `60` `*` `1000``);``}` `catch` `(InterruptedException e) {``// TODO Auto-generated catch block``e.printStackTrace();``}``Log.e(``"wayne"``,` `"sleep over and start myshell"``);``wayne();``Log.e(``"wayne"``,` `"myshell run over"``);` `}``}).start();``}``//add` |
|-|-|

在文件中的performLaunchActivity方法最后添加 wayneThread()方法的调用。

 ![1693921584305](https://bbs.kanxue.com/upload/attach/202309/975093_ZVQTWM6JJAMB3P5.png)

- 修改源码 /root/android/lineage/libcore/dalvik/src/main/java/dalvik/system/DexFile.java文件，将Fart8.0中添加的方法定义复制过来，并修改方法命名，

| 123 | `/``/``add``private static native void saveMethodCode(``Object` `m);``/``/``add` |
|-|-|

#### 2.2修改Fart8.0 SO层代码

SO层的c\c++代码可按上面的步骤导入CLion编辑。

- 在DexFile.java文件对应的so实现文件，即/root/android/lineage/art/runtime/native/dalvik_system_DexFile.cc文件中添加之前saveMethodCode方法的so层实现。

| 1234567891011121314 | `//addfunction``static` `void` `DexFile_saveMethodCode(JNIEnv* env, jclass,jobject method) {``if``(method!=nullptr)``{``LOG(ERROR) <<` `"wayne +++++++++++"``;``ArtMethod* proxy_method = jobject2ArtMethod(env, method);``LOG(ERROR) <<` `"wayne -----------"``;``myWayneCall(proxy_method);``LOG(ERROR) <<` `"wayne -+-+-+-+-+-+-+"``;``}` `return``;``}``//addfunction` |
|-|-|

- 修改该文件最开始的art命名空间

| 123456 | `//add``#include "scoped_fast_native_object_access.h"``namespace` `art {``extern` `"C"` `void` `myWayneCall(ArtMethod* artmethod);``extern` `"C"` `ArtMethod* jobject2ArtMethod(JNIEnv* env, jobject javaMethod);``//addend` |
|-|-|
- 在该文件最末尾添加saveMethodCode函数的函数名命名定义，<font color='red'>注意在上一行末尾添加逗号</font>
![image-20230905220022645](https://bbs.kanxue.com/upload/attach/202309/975093_TG3X34AU6TDJUDB.png)
- 编辑 /root/android/lineage/art/runtime/native/java_lang_reflect_Method.cc文件，添加上面用到的jobject2ArtMethod函数

```
//add
    extern "C" ArtMethod* jobject2ArtMethod(JNIEnv* env, jobject javaMethod) {
        ScopedFastNativeObjectAccess soa(env);
        ArtMethod* method = ArtMethod::FromReflectedMethod(soa, javaMethod);
        return method;
    }
//add
```

- 编辑/root/android/lineage/art/runtime/art_method.cc文件，将Fart8.0源码同名文件中添加的代码复制到该代码中，并修改函数名和日志输出内容。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308309310311312313 | `//add` `uint8_t* codeitem_end(``const` `uint8_t **pData)``{``uint32_t num_of_list = DecodeUnsignedLeb128(pData);``for` `(;num_of_list>0;num_of_list--) {``int32_t num_of_handlers=DecodeSignedLeb128(pData);``int` `num=num_of_handlers;``if` `(num_of_handlers<=0) {``num=-num_of_handlers;``}``for` `(; num > 0; num--) {``DecodeUnsignedLeb128(pData);``DecodeUnsignedLeb128(pData);``}``if` `(num_of_handlers<=0) {``DecodeUnsignedLeb128(pData);``}``}``return` `(uint8_t*)(*pData);``}` `extern` `"C"` `char` `*base64_encode(``char` `*str,``long` `str_len,``long``* outlen){``long` `len;``char` `*res;``int` `i,j;``const` `char` `*base64_table=``"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"``;``if``(str_len % 3 == 0)``len=str_len/3*4;``else``len=(str_len/3+1)*4;` `res=(``char``*)``malloc``(``sizeof``(``char``)*(len+1));``res[len]=``'\0'``;``*outlen=len;``for``(i=0,j=0;i<len-2;j+=3,i+=4)``{``res[i]=base64_table[str[j]>>2];``res[i+1]=base64_table[(str[j]&0x3)<<4 \| (str[j+1]>>4)];``res[i+2]=base64_table[(str[j+1]&0xf)<<2 \| (str[j+2]>>6)];``res[i+3]=base64_table[str[j+2]&0x3f];``}` `switch``(str_len % 3)``{``case` `1:``res[i-2]=``'='``;``res[i-1]=``'='``;``break``;``case` `2:``res[i-1]=``'='``;``break``;``}` `return` `res;``}``extern` `"C"` `void` `saveDexFileByExeMethod(ArtMethod* artmethod)  REQUIRES_SHARED(Locks::mutator_lock_) {``char` `*dexfilepath=(``char``*)``malloc``(``sizeof``(``char``)*1000);``if``(dexfilepath==nullptr)``{``LOG(ERROR)<<` `"wayne::saveDexFileByExeMethod,methodName:"``<<artmethod->PrettyMethod().c_str()<<``"malloc 1000 byte failed"``;``return``;``}``int` `result=0;``int` `fcmdline =-1;``char` `szCmdline[64]= {0};``char` `szProcName[256] = {0};``int` `procid = getpid();``sprintf``(szCmdline,``"/proc/%d/cmdline"``, procid);``fcmdline = open(szCmdline, O_RDONLY\|O_CREAT,0644);``if``(fcmdline >0)``{``result=read(fcmdline, szProcName,256);``if``(result<0)``{``LOG(ERROR) <<` `"wayne::saveDexFileByExeMethod,open cmdline file error"``;``}``close(fcmdline);` `}` `if``(szProcName[0])``{` `const` `DexFile* dex_file = artmethod->GetDexFile();``const` `uint8_t* begin_=dex_file->Begin();` `// Start of data.``size_t` `size_=dex_file->Size();` `// Length of data.` `memset``(dexfilepath,0,1000);``int` `size_int_=(``int``)size_;`  `memset``(dexfilepath,0,1000);``sprintf``(dexfilepath,``"/data/data/%s/wayne"``,szProcName);``mkdir(dexfilepath,0777);` `memset``(dexfilepath,0,1000);``sprintf``(dexfilepath,``"/data/data/%s/wayne/%d_dexfile_execute.dex"``,szProcName,size_int_);``if``(access(dexfilepath,F_OK)!=-1){``LOG(ERROR) << dexfilepath <<` `"File have exist"``;``}``else``{``int` `fp=open(dexfilepath,O_CREAT\|O_APPEND\|O_RDWR,0666);``if``(fp>0)``{``result=write(fp,(``void``*)begin_,size_);``if``(result<0)``{``LOG(ERROR) <<` `"wayne::saveDexFileByExeMethod,open dexfilepath error"``;``}``fsync(fp);``close(fp);``memset``(dexfilepath,0,1000);``sprintf``(dexfilepath,``"/data/data/%s/wayne/%d_classlist_execute.txt"``,szProcName,size_int_);``int` `classlistfile=open(dexfilepath,O_CREAT\|O_APPEND\|O_RDWR,0666);``if``(classlistfile>0)``{``for` `(``size_t` `ii= 0; ii< dex_file->NumClassDefs(); ++ii)``{``const` `dex::ClassDef& class_def = dex_file->GetClassDef(ii);``const` `char``* descriptor = dex_file->GetClassDescriptor(class_def);``result=write(classlistfile,(``void``*)descriptor,``strlen``(descriptor));``if``(result<0)``{``LOG(ERROR) <<` `"wayne::saveDexFileByExeMethod,write classlistfile file error"``;` `}``const` `char``* temp=``"\n"``;``result=write(classlistfile,(``void``*)temp,1);``if``(result<0)``{``LOG(ERROR) <<` `"wayne::saveDexFileByExeMethod,write classlistfile file error"``;` `}``}``fsync(classlistfile);``close(classlistfile);` `}``}`  `}`  `}` `if``(dexfilepath!=nullptr)``{``free``(dexfilepath);``dexfilepath=nullptr;``}` `}` `extern` `"C"` `void` `saveArtMethod(ArtMethod* artMethod)  REQUIRES_SHARED(Locks::mutator_lock_) {``char` `*dexfilepath=(``char``*)``malloc``(``sizeof``(``char``)*1000);``if``(dexfilepath==nullptr)``{``LOG(ERROR) <<` `"wayne::saveArtMethod,methodname:"``<<artMethod->PrettyMethod().c_str()<<``"malloc 1000 byte failed"``;``return``;``}``int` `result=0;``int` `fcmdline =-1;``char` `szCmdline[64]= {0};``char` `szProcName[256] = {0};``int` `procid = getpid();``sprintf``(szCmdline,``"/proc/%d/cmdline"``, procid);``fcmdline = open(szCmdline, O_RDONLY\|O_CREAT,0644);``if``(fcmdline >0)``{``result=read(fcmdline, szProcName,256);``if``(result<0)``{``LOG(ERROR) <<` `"wayne::saveArtMethod,open cmdline file file error"``;``}``close(fcmdline);``}` `if``(szProcName[0])``{``const` `DexFile* dex_file = artMethod->GetDexFile();``const` `uint8_t* begin_=dex_file->Begin();` `// Start of data.``size_t` `size_=dex_file->Size();` `// Length of data.` `memset``(dexfilepath,0,1000);``int` `size_int_=(``int``)size_;`  `memset``(dexfilepath,0,1000);``sprintf``(dexfilepath,``"/data/data/%s/wayne/"``,szProcName);``mkdir(dexfilepath,0777);` `memset``(dexfilepath,0,1000);``sprintf``(dexfilepath,``"/data/data/%s/wayne/%d_dexfile.dex"``,szProcName,size_int_);``if``(access(dexfilepath,F_OK) != -1){``LOG(ERROR) <<` `"invoke DexFile have exist "``;``}``else``{``int` `fp=open(dexfilepath,O_CREAT\|O_APPEND\|O_RDWR,0666);``if``(fp>0)``{``result=write(fp,(``void``*)begin_,size_);``if``(result<0)``{``LOG(ERROR) <<` `"wayne::saveArtMethod,open dexfilepath file error"``;` `}``fsync(fp);``close(fp);``memset``(dexfilepath,0,1000);``sprintf``(dexfilepath,``"/data/data/%s/wayne/%d_classlist.txt"``,szProcName,size_int_);``int` `classlistfile=open(dexfilepath,O_CREAT\|O_APPEND\|O_RDWR,0666);``if``(classlistfile>0)``{``for` `(``size_t` `ii= 0; ii< dex_file->NumClassDefs(); ++ii)``{``const` `dex::ClassDef& class_def = dex_file->GetClassDef(ii);``const` `char``* descriptor = dex_file->GetClassDescriptor(class_def);``result=write(classlistfile,(``void``*)descriptor,``strlen``(descriptor));``if``(result<0)``{``LOG(ERROR) <<` `"wayne::saveArtMethod,write classlistfile file error"``;` `}``const` `char``* temp=``"\n"``;``result=write(classlistfile,(``void``*)temp,1);``if``(result<0)``{``LOG(ERROR) <<` `"wayne::saveArtMethod,write classlistfile file error"``;` `}``}``fsync(classlistfile);``close(classlistfile);` `}``}`  `}``const` `dex::CodeItem* code_item = artMethod->GetCodeItem();``if` `(LIKELY(code_item != nullptr))``{`  `uint8_t *item=(uint8_t *) code_item;``uint32_t code_item_len = dex_file->GetCodeItemSize(*code_item);``//                if (code_item->tries_size_>0) {``//                    const uint8_t *handler_data = (const uint8_t *)(DexFile::GetTryItems(*code_item, code_item->tries_size_));``//                    uint8_t * tail = codeitem_end(&handler_data);``//                    code_item_len = (int)(tail - item);``//                }else{``//                    code_item_len = 16+code_item->insns_size_in_code_units_*2;``//                }``memset``(dexfilepath,0,1000);``int` `size_int = (``int``)dex_file->Size();``uint32_t method_idx = artMethod->GetDexMethodIndex();``sprintf``(dexfilepath,``"/data/data/%s/wayne/%d_ins_%d.bin"``,szProcName,size_int,(``int``)gettidv1());``int` `fp2=open(dexfilepath,O_CREAT\|O_APPEND\|O_RDWR,0666);``if``(fp2>0){``lseek(fp2,0,SEEK_END);``memset``(dexfilepath,0,1000);``int` `offset=(``int``)(item - begin_);``sprintf``(dexfilepath,``"{name:'%s',method_idx:'%d',offset:'%d',code_item_len:'%d',ins:'"``,artMethod->PrettyMethod().c_str(),method_idx,offset,code_item_len);``int` `contentlength=0;``while``(dexfilepath[contentlength]!=0) contentlength++;``result=write(fp2,(``void``*)dexfilepath,contentlength);``if``(result<0)``{``LOG(ERROR) <<` `"wayne::saveArtMethod,write ins file error"``;` `}``long` `outlen=0;``char``* base64result=base64_encode((``char``*)item,(``long``)code_item_len,&outlen);``result=write(fp2,base64result,outlen);``if``(result<0)``{``LOG(ERROR) <<` `"wayne::saveArtMethod,write ins file error"``;` `}``result=write(fp2,``"'};"``,3);``if``(result<0)``{``LOG(ERROR) <<` `"wayne::saveArtMethod,write ins file error"``;` `}``fsync(fp2);``close(fp2);``if``(base64result!=nullptr){``free``(base64result);``base64result=nullptr;``}``}` `}`  `}` `if``(dexfilepath!=nullptr)``{``free``(dexfilepath);``dexfilepath=nullptr;``}` `}``extern` `"C"` `void` `myWayneCall(ArtMethod* artmethod)  REQUIRES_SHARED(Locks::mutator_lock_) {``JValue *result=nullptr;``Thread *self=nullptr;``uint32_t temp=6;``uint32_t* args=&temp;``uint32_t args_size=6;``artmethod->Invoke(self, args, args_size, result,` `"aaa"``);``}``//addend` |
|-|-|

为了防止加固厂商的检测，修改了dex文件保存的目录，由原来的sdcard目录全部改为 "/data/data/%s/wayne/%d_classlist.txt",szProcName,size_int_);"

同时修改了invoke脱壳点的脱壳函数saveArtMethod和Execute脱壳点的脱壳函数saveDexFileByExeMethod中提示错误的部分，如下所列

1. 打开文件添加O_CREATE方式
 ![image-20230905224354735](https://bbs.kanxue.com/upload/attach/202309/975093_9B6N5QHTF58UP3F.png)
2. 修改文件是否存在的判断方式
![image-20230905224447643](https://bbs.kanxue.com/upload/attach/202309/975093_XYSP34Q9J6P5CMD.png)
3. 修改类型定义变化的出错
![image-20230905224609024](https://bbs.kanxue.com/upload/attach/202309/975093_YTUCX9GQTKA9BBR.png)

![image-20230905224648865](https://bbs.kanxue.com/upload/attach/202309/975093_VTQWK5HV5YR3NCZ.png)

4. 修改saveArtMethod函数中计算codeItem长度的方式
![image-20230905224844797](https://bbs.kanxue.com/upload/attach/202309/975093_ZBSXVYKASD6CT79.png)
5. 在该文件最开始添加gettidv1()的宏定义

![image-20230905224942005](https://bbs.kanxue.com/upload/attach/202309/975093_3H6WUKYCWRTVWDF.png)

6. 导入需要的.h文件
7. 在Invoke函数中添加对saveArtMethod函数的调用
![image-20230905225136707](https://bbs.kanxue.com/upload/attach/202309/975093_28J4JXTB6X7FDKR.png)

- 在 /root/android/lineage/art/runtime/interpreter/interpreter.cc文件中的Execute函数脱壳点添加脱壳函数的调用。
![image-20230905225255689](https://bbs.kanxue.com/upload/attach/202309/975093_JUJBFGCAKG7BTEE.png)

在该文件最前面的art命名空间添加脱壳函数的引入：

![image-20230905225454188](https://bbs.kanxue.com/upload/attach/202309/975093_4AQFDWGMM4DCHMC.png)

#### 2.3 编译后刷机

刷机完毕，将待脱壳的apk安装后运行，等待一会，进入/data/data/包名/XXX目录下可看到脱壳下来的dex文件和方法的bin文件，copy到/sdcard目录
再使用adb pull命令拖到虚拟机中修复即可。 测试发现Execute脱壳点没有生效，需要进一步查找原因。

---

# 回复

## 回复 by ty1937 (#2)

*2023-9-8 09:41*

排查出原因了吗？ 为啥没有走Execute

## 回复 by vigiles (#3)

*2023-9-8 09:55*

300G！几何倍数增长啊。

## 回复 by Elice (#4)

*2023-9-13 08:52*

求分享r0ysue大佬的集成版Kali2022

## 回复 by 秋狝 (#5)

*2023-9-13 09:19*

感谢分享

## 回复 by woaiziyou (#6)

*2023-9-14 09:01*

>
> [Elice](https://bbs.kanxue.com/user-566456.htm)
>
>  求分享r0ysue大佬的集成版Kali2022
>
>

同求

## 回复 by wpfpzw (#7)

*2023-9-16 20:23*

为什么最后编译成功了进去一直有factory data reset 可以请教一下这是什么原因引起的，，我是lineageos17.1 手机oneplus5

## 回复 by wpfpzw (#8)

*2023-9-16 20:26*

execute问题是不是因为目录只能逐级建立

## 回复 by wpfpzw (#9)

*2023-9-17 15:33*

>
> [wpfpzw](https://bbs.kanxue.com/user-977324.htm)
>
>  为什么最后编译成功了进去一直有factory data reset 可以请教一下这是什么原因引起的，，我是lineageos17.1 手机oneplus5
>
>

已解决
