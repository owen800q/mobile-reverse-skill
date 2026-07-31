---
title: '[原创]Android下的art的ArtMethod一些学习分享'
url: https://bbs.kanxue.com/thread-289025.htm
tid: 289025
author: 陈可牛
date: '2025-11-07'
tags: [Android安全, 原创, 混淆加固, 脱壳反混淆]
crawled_at: '2026-07-31T15:27:14+08:00'
replies: 75
---

# Android下的art的ArtMethod一些学习分享

为什么会写这个呢？其实很多东西都是之前写的，最近又整理了一下，也算是一个温故而知新吧！
之前一直找看一下传说中的goto类抽取，也想看看到底是怎么实现的，以及对比bangbang/ijm等有什么区别。
也问了很多人，也委托几个大佬帮我留意一下样本，也是没了后续。
直到今年又有了几个新的样本，也蛮有意思的，分析完了就找到了那个goto样本，分析之后。这篇文章也就对我最近捣鼓的样本的一些总结吧！
如果看下去的话，请不要嫌弃文章的啰嗦，因为要照顾一些刚接触的。所以我会尽可能地完整的去过一遍流程。为了方便学习，这里以Android8.1，在Android12等高版本就有有很多的不适用性，但相应的也出现了一些配套的Api，这里不展开细说。

## 先放结论，好让大佬按需阅读

- 类加载/方法加载/类初始化/dex等等关键入口。
- 不同时期的加固技术发展的演变。
- 多种不同实现的类抽取以及一些小实验。
- 其他的一些东西，再说吧！
- 至于为什么会以这种方式去做分享，最后我们提到。
- 最后！如果有哪里有误，那就感谢大佬们的斧正！非常感谢！

## 开篇

本篇文章以一个Java的方法执行的全过程为切入点的，即如下的伪代码

| 1234 | `DexClassLoader classLoader = new DexClassLoader(file.getAbsolutePath(), null, null, classLoader);``Class<?> TestClass = classLoader.loadClass(clazz.getName());``Method TestMethod = TestClass.getDeclaredMethod(method.getName(), method.getParameterTypes());``int number = (int) method.invoke(null, args);` |
|-|-|

## 开始

谈到安卓的Java虚拟机，那必定离不开安卓的art虚拟机。早期还有dalvikvm虚拟器。不过也成为了一种过去式的历史。不过现在也一另外的形式存在。那就是[dexvmp](https://xrefandroid.com/android-4.3_r1.1/xref/dalvik/vm/mterp/)
那么我么今天就以Java的代码如何在Android的上运行做一个分享。

## [art](https://xrefandroid.com/android-8.1.0_r81/xref/art/)

![img_4.png](https://bbs.kanxue.com/upload/attach/202511/794149_FH5VDQTA9EMF4TB.png)

在Android中有几个版本跨域比较大，那就是4.4.4/7.12/8.1/12/15，art虚拟机就是在Android的4.4.4中发布，伴随这art虚拟机的引入，安卓也走入了一个全新的时代，即从解释型虚拟机到编译后的二进制文件。

## dex加载

如果有学习过Java的开发，那都会遇到jar，dex就是在Android上的“jar”。姑且可以这样子理解（jar可以直接改为.zip打开，dex不行，jar可以放一些资源，dex只能放smail文件）
涉及到jar/dex，那么就会有一个属性的东西类加载器“ClassLoader”，这个在上一次分享中，有介绍过不同JDK实现有提过类加载的一个过程，这次会比较详细的分享他的一些过程。

### [ClassLoader](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/ojluni/src/main/java/java/lang/ClassLoader.java)

![img_7.png](https://bbs.kanxue.com/upload/attach/202511/794149_U4GSKZ4HFFEHAD2.png)

![img_6.png](https://bbs.kanxue.com/upload/attach/202511/794149_NTM9VDJ9CCHQ3F5.png)

他的默认实现，从这里也很生动的体现他的“双亲委派机制”解决类加载器的重复加载问题，从中也可以发现，loadClass的会调用findClass进行查找，以及他们的权限修饰符，可以通过继承的形式进行覆盖。
下面三个就是他在Android的三个实现子类

### [InMemoryDexClassLoader](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/dalvik/src/main/java/dalvik/system/InMemoryDexClassLoader.java)

![img.png](https://bbs.kanxue.com/upload/attach/202511/794149_QDVSSADRSBH5Q4S.png)

### [DexClassLoader](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/dalvik/src/main/java/dalvik/system/DexClassLoader.java)

![img_1.png](https://bbs.kanxue.com/upload/attach/202511/794149_J85Q7CH6X7N6DVQ.png)

### [PathClassLoader](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/dalvik/src/main/java/dalvik/system/PathClassLoader.java)

![img_2.png](https://bbs.kanxue.com/upload/attach/202511/794149_2296U3GG4ZGW6CS.png)

通过上面的图片来看，他们并没有在这里实现什么，甚至也没什么区别，都是继承于BaseDexClassLoader这个类，那么我们重点就在这了。
上面三个实现ClassLoader的子类，我们也比较容易理解他们的作用。

[BootClassLoader](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/ojluni/src/main/java/java/lang/ClassLoader.java#1336)
这个看名字就知道啦，所以跳过咯

## 类加载

- 隐性加载
- 主动加载

### [BaseDexClassLoader](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/dalvik/src/main/java/dalvik/system/BaseDexClassLoader.java)

![img_3.png](https://bbs.kanxue.com/upload/attach/202511/794149_QYWDAUAJSGZVQSW.png)

通过ClassLoader的代码分析，我们知道loadClass会调用findClass去查找并加载类，那么我们只需要关注findClass的实现即可
![img_8.png](https://bbs.kanxue.com/upload/attach/202511/794149_Z9V8FYUWVZJCTUR.png)

在这里我们可以看到会调用pathList的findClass调用，以及下面的方法，addDexPath，也是调用pathList的.addDexPath方法

pathList的定义
![img_9.png](https://bbs.kanxue.com/upload/attach/202511/794149_QW8FGQBZHYX3RCQ.png)

### [DexPathList](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/dalvik/src/main/java/dalvik/system/DexPathList.java)

![img_10.png](https://bbs.kanxue.com/upload/attach/202511/794149_QK5S5S7E2VP7YD7.png)
这里我们可以看到DexPathList的findClass也是调用dexElements数组的中实现的findClass方法

dexElements初始化刚好在DexPathList的构造函数中，也就是在makeInMemoryDexElements这个函数中
![img_14.png](https://bbs.kanxue.com/upload/attach/202511/794149_3QVE6YFBXCQ4Q6J.png)

![img_15.png](https://bbs.kanxue.com/upload/attach/202511/794149_HFSSKNV9ZJDC6QQ.png)
dexElements是makeInMemoryDexElements返回的，Element初始化的过程中还会创建一个DexFile对象，

![img_16.png](https://bbs.kanxue.com/upload/attach/202511/794149_JDNU5G5U8CB7QVX.png)
可以通过这两个相邻的函数可以发现，这就是加载两种不同形式的dex的函数，上面的是通过ByteBuffer[]，下面的是通过List

那我们以文件加载的形式去分析Dex的加载，那也就是会调用makeDexElements方法中的loadDexFile中返回

那也就是
![img_17.png](https://bbs.kanxue.com/upload/attach/202511/794149_Z3HJBW7AJW6QPJQ.png)

![img_18.png](https://bbs.kanxue.com/upload/attach/202511/794149_GPF5H37WB6M3CRA.png)
我们跟一下DexFile的构造函数，这里也很明显可以看到有两个不同的构造函数，一个是传递的是ByteBuffer，一个是String的fileName

然后我们回到Element的findClass
[Element](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/dalvik/src/main/java/dalvik/system/DexPathList.java#559)
![img_12.png](https://bbs.kanxue.com/upload/attach/202511/794149_B9BBZDHZ9YE283J.png)

那么最终的类加载就会变成
DexFile的[defineClassNative](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/dalvik/src/main/java/dalvik/system/DexFile.java?fi=defineClassNative#384)
![img_19.png](https://bbs.kanxue.com/upload/attach/202511/794149_5AJ8WWMH9BHRXZZ.png)

正常逆向分析的思维就是，一路跟到底，最后才是看如何构造一个全链路。
先到初始化，再到查找嘛，????
这里我们就换一下，先看他如何出初始化再捣鼓的

####### 插眼

[openDexFile](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/dalvik/src/main/java/dalvik/system/DexFile.java#350)
这个是在DexFile的初始化的时候，可能会执行，取决于是传递byte[]还是dexPath，也就是不同类加载器的区别了。
现在我们以DexClassLoader的形式去加载的话（PathClassLoader也是一样的）去进行分析，也就是会执行dexPath的这个构造函数

![img_54.png](https://bbs.kanxue.com/upload/attach/202511/794149_VTW88EKEWDRP55D.png)

最终调用到native的方法，那么我们继续跟去
[dalvik_system_DexFile.cc](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/native/dalvik_system_DexFile.cc)

DexFile_openDexFileNative
![img_21.png](https://bbs.kanxue.com/upload/attach/202511/794149_KBF42CP5JAT967Q.png)
这里会调用OpenDexFilesFromOat返回，然后通过ConvertDexFilesToJavaArray函数处理之后返回到Java层

[OpenDexFilesFromOat](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/oat_file_manager.cc?r=&amp;mo=14092&amp;fi=382#382)

![img_53.png](https://bbs.kanxue.com/upload/attach/202511/794149_3DS32UFT52HXNSE.png)

会先判断是否加载oat相关的代码。这里我们默认第一次执行，也就不会涉及到oat/odex/vdex等相关的东西了，因为可以通过这里dump到完整的dex，壳代码会禁止相关的优化，或者是屏蔽了。。。
屏蔽也有一些好处，有一些inline的优化，也是很头疼，屏蔽之后就可以一劳永逸了，代价没那么快了。
这里的快的概念，是对于正常开发者的，而对于我们学习来说，也就没那么重要了。

![img_24.png](https://bbs.kanxue.com/upload/attach/202511/794149_U6CUUAKJFZZJT65.png)

![img_25.png](https://bbs.kanxue.com/upload/attach/202511/794149_2RUKMSEFC9DENJ3.png)
所以上面的dex_files就会为空，从而执行DexFile::Open

### oat的加载

，这里就不一路分析到底了，感兴趣的可以继续分析下去
[OatFile* OatFile::Open](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/oat_file.cc?r=&amp;mo=6007&amp;fi=192#1134)
[LoadDexFiles](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/oat_file_assistant.cc#330)
[OatFileAssistant::LoadDexFiles](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/oat_file_assistant.cc#330)
[std::unique_ptr](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/oat_file.cc#1413)
[OatFileBase* OatFileBase::OpenOatFile](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/oat_file.cc#152)

### dex的加载

[DexFile::Open](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/dex_file.cc#213)
这里的DexFile::Open也是一路执行到DexFile::OpenFile

[DexFile::OpenFile](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/dex_file.cc#273)

![img_26.png](https://bbs.kanxue.com/upload/attach/202511/794149_87K9JTFT5NK7U38.png)
在这里我们就会进入到一个特殊的点了，开始将dex文件映射到内存中去。至于为什么特殊？
等下会解释。

[MemMap* MapFile](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/mem_map.h?fi=MapFile#83)
![img_27.png](https://bbs.kanxue.com/upload/attach/202511/794149_VEND6T276S7K24X.png)
MapFile也是调用MapFileAtAddress

[MemMap::MapFileAtAddress](https://xrefandroid.com/android-8.1.0_r81/s?refs=MapFileAtAddress&amp;project=art)
![img_28.png](https://bbs.kanxue.com/upload/attach/202511/794149_V9FUWDU7EMF2MPT.png)
MapFileAtAddress进一步调用MapInternal

[MemMap::MapInternal](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/mem_map.cc?fi=MapFileAtAddress#902)
MapInternal之后就到了我们遇到的特殊点了，使用mmap去映射内存
![img_55.png](https://bbs.kanxue.com/upload/attach/202511/794149_5P3J8YPUU77HGR9.png)
我们可以往上翻，会注意到他的权限是PROT_READ,

![img_29.png](https://bbs.kanxue.com/upload/attach/202511/794149_Z355PWRZDMM64J8.png)

[DexFile::OpenCommon](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/dex_file.cc#481)

到这里我们就看完分配内存了，我们接下来往下看DexFile::OpenCommon

![img_30.png](https://bbs.kanxue.com/upload/attach/202511/794149_95W7W6QAZRFFJG4.png)

中也没存做啥，只是创建个DexFile对象，然后返回

## 彩蛋1

ConvertDexFilesToJavaArray
![img_22.png](https://bbs.kanxue.com/upload/attach/202511/794149_Y3ZWWKGS8U45AST.png)·
我们可以看到他是传递个oat_file以及DexFile的vec
细心的看的话，就知道她他会创建个数据，第一个元素放到的是oat的对象的地址，第二个就是DexFile（一个或多个）
然后返回，最终就是DexFile的mCookie对象了，下面会有图片比较直观的体现

[dalvik_system_DexFile.h](http://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/native/dalvik_system_DexFile.h?fi=kOatFileIndex#kOatFileIndex)

| 12 | `25  constexpr size_t kOatFileIndex = 0;``26  constexpr size_t kDexFileIndexStart = 1;` |
|-|-|

| 12345 | `96    long_data[kOatFileIndex] = reinterpret_cast<uintptr_t>(oat_file);``97` `for` `(size_t i = 0; i < vec.size(); ++i) {``98      long_data[kDexFileIndexStart + i] = reinterpret_cast<uintptr_t>(vec[i].get());``99    }``100` |
|-|-|

![img_74.png](https://bbs.kanxue.com/upload/attach/202511/794149_KG43KGKCFS4NA9E.png)
![img_75.png](https://bbs.kanxue.com/upload/attach/202511/794149_2V9FG3N9N6S27E2.png)

## 回来

刚才我们去看了DexFile的创建以及初始化过程，接下来我们继续看类的定义

DexFile_defineClassNative
![img_20.png](https://bbs.kanxue.com/upload/attach/202511/794149_PKBBD6SG6FCD5CK.png)
调用class_linker->DefineClass的

[class_linker.cc](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/class_linker.cc)

[ClassLinker::DefineClass](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/class_linker.cc#2828)
![img_31.png](https://bbs.kanxue.com/upload/attach/202511/794149_T8QV7JKUNNJZMKJ.png)
DefineClass中也是进一步调用LoadClass

[ClassLinker::LoadClass](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/class_linker.cc#3248)
![img_32.png](https://bbs.kanxue.com/upload/attach/202511/794149_NY77M8XJYZQPY4E.png)
LoadClass进一步调用LoadClassMembers

[ClassLinker::LoadClassMembers](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/class_linker.cc#3317)
![img_33.png](https://bbs.kanxue.com/upload/attach/202511/794149_GWP4Q2ZGQ4455W2.png)

在这里我们就可以看到比较的多东西了

## 方法加载

[ClassLinker::LoadMethod](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/class_linker.cc#3434)
![img_34.png](https://bbs.kanxue.com/upload/attach/202511/794149_U9N9AED3K5A29DF.png)

[static void LinkCode](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/class_linker.cc#3172)

| 123 | `3200      // For static methods excluding the class initializer, install the trampoline.``3201      // It will be replaced by the proper entry point by ClassLinker::FixupStaticTrampolines``3202      // after initializing class (see ClassLinker::InitializeClass method).` |
|-|-|

在这里我们就可以触发第二个彩蛋

## 彩蛋2

[Class_newInstance](http://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/native/java_lang_Class.cc?r=&amp;mo=26995&amp;fi=674#674)
![img_56.png](https://bbs.kanxue.com/upload/attach/202511/794149_PSVVV32P25NWMGG.png)
类实例的创建

![img_57.png](https://bbs.kanxue.com/upload/attach/202511/794149_JG5D7Z5UT65QYXA.png)
这里我们能看到类的初始化入口

或者这个路径（没有测试，只是代码搜素搜到这个）

[GetFieldID](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/jni_internal.cc#1303)
![img_36.png](https://bbs.kanxue.com/upload/attach/202511/794149_RM7BU7MKDS6MGF3.png)

[FindFieldID](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/jni_internal.cc#278)

![img_37.png](https://bbs.kanxue.com/upload/attach/202511/794149_UUPZSKUW7KRADSZ.png)

[EnsureInitialized](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/jni_internal.cc#214)

![img_35.png](https://bbs.kanxue.com/upload/attach/202511/794149_24B6KYNENFDWVK7.png)

最终也是会执行到ClassLinker::EnsureInitialized

[ClassLinker::EnsureInitialized](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/class_linker.cc#5345)

![img_38.png](https://bbs.kanxue.com/upload/attach/202511/794149_EY7C25C686W9W3C.png)
ClassLinker::EnsureInitialized调用ClassLinker::InitializeClass

[ClassLinker::InitializeClass](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/class_linker.cc#4785)

![img_39.png](https://bbs.kanxue.com/upload/attach/202511/794149_VQ2XJ3EXTZUV4AR.png)
ClassLinker::InitializeClass调用ClassLinker::FixupStaticTrampolines

[ClassLinker::FixupStaticTrampolines](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/class_linker.cc#3114)

![img_40.png](https://bbs.kanxue.com/upload/attach/202511/794149_F48C6P74U4PVDAH.png)

到这里我们就可以看到他的参数了klass，至于这个是什么，后面会有测试进行的说明

## 方法执行

既然我们说了类是怎么加载的，然后到类定义，方法的加载，类的初始化，那么就顺便把最后的一个：方法的执行

[Method](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/ojluni/src/main/java/java/lang/reflect/Method.java)

![img_42.png](https://bbs.kanxue.com/upload/attach/202511/794149_G4Q7CHEMUAK92A6.png)

Method继承于Executable。这个需要考的，现在先记住这个就好了

[invoke](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/ojluni/src/main/java/java/lang/reflect/Method.java#407)
![img_41.png](https://bbs.kanxue.com/upload/attach/202511/794149_QWAZQZUVBBW8UEZ.png)
这个就是Java的方法反射执行的入口了

[Method_invoke](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/native/java_lang_reflect_Method.cc#84)
![img_43.png](https://bbs.kanxue.com/upload/attach/202511/794149_8TK8ZQNHWX3BXDV.png)
Method_invoke调用InvokeMethod

[InvokeMethod](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/reflection.cc?fi=InvokeMethod#584)

![img_23.png](https://bbs.kanxue.com/upload/attach/202511/794149_F3AQQ9F32Y8UVKC.png)
InvokeMethod调用InvokeWithArgArray
同时我们也看到了

| 1234 | `595    ObjPtr<mirror::Executable> executable = soa.Decode<mirror::Executable>(javaMethod);``596    const bool accessible = executable->IsAccessible();``597    ArtMethod* m = executable->GetArtMethod();``598` |
|-|-|

这种奇怪的代码转换，在后面还会有很多，，哈哈哈

[InvokeWithArgArray](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/reflection.cc?fi=InvokeMethod#446)
![img_47.png](https://bbs.kanxue.com/upload/attach/202511/794149_HG6VG5AZJ5PVRSR.png)

InvokeWithArgArray做好准备参数检查的准备
就执行method->Invoke

![img_48.png](https://bbs.kanxue.com/upload/attach/202511/794149_9FGBBBR2KARWHBN.png)
[ArtMethod::Invoke](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/art_method.cc#311)
![img_49.png](https://bbs.kanxue.com/upload/attach/202511/794149_VS5TXKB3FUGR8WU.png)

到这一步我们就进入了ArtMethod的世界！
开源的类抽取还原框架fart，也就是以这个为入口进行虚假调用并触发方法的修复
这里我们可以看到一段描述

| 1234 | `329    // Call the invoke stub, passing everything as arguments.``330    // If the runtime is not yet started or it is required by the debugger, then perform the``331    // Invocation by the interpreter, explicitly forcing interpretation over JIT to prevent``332    // cycling around the various JIT/Interpreter methods that handle method invocation.` |
|-|-|

然后我们就执行到了
art::interpreter::EnterInterpreterFromInvoke
进入解释模式

[EnterInterpreterFromInvoke](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/interpreter/interpreter.cc?fi=EnterInterpreterFromInvoke#362)
![img_50.png](https://bbs.kanxue.com/upload/attach/202511/794149_DUYKWH3FXMC4BND.png)
在这里会判断是否为jni方法

| 12345678910111213141516 | `450`    `if` `(LIKELY(!method->IsNative())) {``451`      `JValue r = Execute(self, code_item, *shadow_frame, JValue(), stay_in_interpreter);``452`      `if` `(result != nullptr) {``453`        `*result = r;``454`      `}``455`    `}` `else` `{``456`      `// We don't expect to be asked to interpret native code (which is entered via a JNI compiler``457`      `// generated stub) except during testing and image writing.``458`      `// Update args to be the args in the shadow frame since the input ones could hold stale``459`      `// references pointers due to moving GC.``460`      `args = shadow_frame->GetVRegArgs(method->IsStatic() ?` `0` `:` `1``);``461`      `if` `(!Runtime::Current()->IsStarted()) {``462`        `UnstartedRuntime::Jni(self, method, receiver.Ptr(), args, result);``463`      `}` `else` `{``464`        `InterpreterJni(self, method, shorty, receiver, args, result);``465`      `}` |
|-|-|

我们此次分析的是普通的Java函数，所以会执行Execute

[Execute](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/interpreter/interpreter.cc?fi=EnterInterpreterFromInvoke#239)
![img_51.png](https://bbs.kanxue.com/upload/attach/202511/794149_VS8XUAA995C7XCQ.png)

| 1234567891011121314151617181920212223 | `265` `266`      `if` `(!stay_in_interpreter) {``267`        `jit::Jit* jit = Runtime::Current()->GetJit();``268`        `if` `(jit != nullptr) {``269`          `jit->MethodEntered(self, shadow_frame.GetMethod());``270`          `if` `(jit->CanInvokeCompiledCode(method)) {``271`            `JValue result;``272` `273`            `// Pop the shadow frame before calling into compiled code.``274`            `self->PopShadowFrame();``275`            `// Calculate the offset of the first input reg. The input registers are in the high regs.``276`            `// It's ok to access the code item here since JIT code will have been touched by the``277`            `// interpreter and compiler already.``278`            `uint16_t arg_offset = code_item->registers_size_ - code_item->ins_size_;``279`            `ArtInterpreterToCompiledCodeBridge(self, nullptr, &shadow_frame, arg_offset, &result);``280`            `// Push the shadow frame back as the caller will expect it.``281`            `self->PushShadowFrame(&shadow_frame);``282` `283`            `return` `result;``284`          `}``285`        `}``286`      `}``287`    `}` |
|-|-|

这里应该是执行到一些优化之后的代码吧？我们要看的是解释模式，所以忽略

[ArtInterpreterToCompiledCodeBridge](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/interpreter/interpreter_common.cc?fi=ArtInterpreterToCompiledCodeBridge#ArtInterpreterToCompiledCodeBridge)

![img_58.png](https://bbs.kanxue.com/upload/attach/202511/794149_NNYSTBZPAUT3TDV.png)
这里也是从新执行一遍method->Invoke，
最终应该会执行到EnterInterpreterFromInvoke的InterpreterJni去吗？

[ExecuteSwitchImpl](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/interpreter/interpreter_switch_impl.cc?fi=ExecuteSwitchImpl#154)
![img_52.png](https://bbs.kanxue.com/upload/attach/202511/794149_ETR8NYBDMX4HQSV.png)

在这里解析指令了咯？所以结束了？
不，这才刚开始。
上面的说那么多无非就是想引入一些点：LoadMethod、、DexFile::Open、Execute等等方法 还有mCookie等字段是什么？

## 结构体（类）介绍

https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/art_method.h

https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/mirror/class.h

https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/dex_file.h

https://xrefandroid.com/android-8.1.0_r81/xref/libcore/ojluni/src/main/java/java/lang/Class.java

![img_59.png](https://bbs.kanxue.com/upload/attach/202511/794149_3XCY6A8ZJXBXD4C.png)

看到这图，是不是一切都豁然开朗了？
那么费力的去讲解这么多的流程，无非就是想解释，最终的数据加载到内存了，都成了什么样子了？
到这里我们是不是会有很多奇怪的想法？

那我们以一个demo为例：
![img_60.png](https://bbs.kanxue.com/upload/attach/202511/794149_AUS36G9STWPZJTD.png)

比如我们可以拿到一个Method，进一步我们可以拿到他的类定义、然后就是dex缓存，从而拿到dexFile，然后是就是计算code_item的偏移？然后拿到指令？
对的，就顺便脱壳，也做了类修复
![img_67.png](https://bbs.kanxue.com/upload/attach/202511/794149_UKRFDZNRM7PCND8.png)
![img_66.png](https://bbs.kanxue.com/upload/attach/202511/794149_TVPGBZ37K8YAN8A.png)

既然可以拿到指令？ 那我是否可以修改指令？
是的，上面也提到了类加载的内存映射只有READ的权限，也就需要hook去修改，或者使用下面的方式（详情可以看dpt-shell的作者分析的文章）
![img_65.png](https://bbs.kanxue.com/upload/attach/202511/794149_5NMBMV7KWXXBMZD.png)
然后就根据实际需求去修改就好了

或者替换偏移？
![img_64.png](https://bbs.kanxue.com/upload/attach/202511/794149_FQD3D53QRKAD35X.png)

如果指令大小不够了怎么办？
直接mmap一个区域也给他弄个偏移就好了
![img_63.png](https://bbs.kanxue.com/upload/attach/202511/794149_RUWMK7Q725YGBKJ.png)

或者我们可以做一个动态的指令生成？ 如何动态的生成指令？
![img_62.png](https://bbs.kanxue.com/upload/attach/202511/794149_687BJ4P7QDWF6WH.png)
直接编译拿到之后直接整个方法定义长得差不多的，直接拿过来就可以用了（fid，mid，这些可能会错乱哈哈啊哈）

如何直接写指令去实现？
![img_61.png](https://bbs.kanxue.com/upload/attach/202511/794149_SXD6J2AQTETEAVX.png)
直接用asm去写就好了
这里的参数传递的规则有点奇怪，得从3/4开始的

上面的一个整体效果：：：

![img_76.png](https://bbs.kanxue.com/upload/attach/202511/794149_4QSKBXXGWQBGAMS.png)

输出
这两个是偏移替换的，可以看到run执行了fake/fake2的代码
![img_77.png](https://bbs.kanxue.com/upload/attach/202511/794149_C4WHNP7XD65KQ6Z.png)
![img_78.png](https://bbs.kanxue.com/upload/attach/202511/794149_MB2THEE3B352AUK.png)

......
动态修改&执行？提高我们的风控难度？对吧？

## 构造器

[Constructor](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/ojluni/src/main/java/java/lang/reflect/Constructor.java)
![img_46.png](https://bbs.kanxue.com/upload/attach/202511/794149_94776HC2R3SPYF4.png)
这里的是构造函数，同理分析也是差不多的，所以跳过吧！哈哈哈

## Executable

Executable

Executable的定义
![img_45.png](https://bbs.kanxue.com/upload/attach/202511/794149_ZEQWNHMC9UUTH2Z.png)

![img_44.png](https://bbs.kanxue.com/upload/attach/202511/794149_Y5GRSPMUYHP5VJ4.png)
artMethod指针

[private long artMethod;](https://xrefandroid.com/android-8.1.0_r81/xref/libcore/ojluni/src/main/java/java/lang/reflect/Executable.java#574)
这个东西就很关键了，那就是artMethod的地址

## 调试方法

还能有栈回溯方便吗？

### 调试器

![img_73.png](https://bbs.kanxue.com/upload/attach/202511/794149_VTGVQU7XKY7XJ2G.png)

### 主动打印

new Exception().printStackTrace();
abort

### 破坏指令，制造异常

![img_72.png](https://bbs.kanxue.com/upload/attach/202511/794149_28GRE6RAGSEYQYZ.png)

## [smali指令](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/dex_instruction.cc)

[Instruction::DumpString](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/dex_instruction.cc#155)

## [jmethodID跟ArtMethod的转换](https://www.cnblogs.com/lanrenxinxin/p/5207174.html)

ArtMethod *artmeth = reinterpret_cast<ArtMethod *>(methid);
还有上面的，很多的都是可以直接转换的了

## 代码动态编译

占坑，不填

## 安卓加固/安卓脱壳

如上

## 类初始化/方法加载/方法执行

![img_68.png](https://bbs.kanxue.com/upload/attach/202511/794149_UPNA65SMB4MP6QW.png)
![img_69.png](https://bbs.kanxue.com/upload/attach/202511/794149_EV2FMPXA3Z6SP94.png)
![img_70.png](https://bbs.kanxue.com/upload/attach/202511/794149_W2H59TQUT6AEAE5.png)

如上
为啥提到这个？因为我们需要有个事件告知我们，这里的都是被动触发的，或者我们主动出击！
我们也可以主动通过tls相关的代码判断环境，比如ArtThread，从而进一步提高对抗难度，相应的也会提高开发难度（稳定性方面）。

## 动态代理/类替换

有机会继续

这两个也可以作为通知的一种手段

### [jdwp](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/jdwp/)

### [jvmti](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/openjdkjvmti/)

https://source.android.google.cn/docs/core/runtime/art-ti?hl=zh-cn
https://docs.oracle.com/javase/7/docs/platform/jvmti/jvmti.html#SpecificationIntro

## 课后作业

[mmap](http://xrefandroid.com/android-8.1.0_r81/xref/bionic/libc/bionic/mmap.cpp)
[malloc](http://xrefandroid.com/android-8.1.0_r81/xref/bionic/libc/bionic/malloc_common.cpp)
为啥dexFile会选择mmap？

## 安卓加固发展历程

到这里，想必你的心里已经有答案了，下面的也已经说完了，也就没必要过多的介绍了
看看图心里也会有答案了
至于怎么脱壳/修复，这里给了那么多点了，随便找一些就好啦

### 整体加固

### goto类抽取/回填抽取/偏移型类抽取

#### goto类抽取

![20251106024356.png](https://bbs.kanxue.com/upload/attach/202511/794149_AE77H7U8J75JX7V.png)
![20251106024050.png](https://bbs.kanxue.com/upload/attach/202511/794149_M9C56Z3BKEYGPGW.png)
![20251106024116.png](https://bbs.kanxue.com/upload/attach/202511/794149_3FQM26BA84BQYVA.png)
![20251106024240.png](https://bbs.kanxue.com/upload/attach/202511/794149_ERPESKJYXWZE4PB.png)

### [dpt](https://github.com/luoyesiqiu/dpt-shell)

### [Dex2C](https://github.com/amimo/dcc)

### [dexvmp](https://github.com/maoabc/nmmp)

[dexvmp的实现](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/interpreter/interpreter_switch_impl.cc)
![img_5.png](https://bbs.kanxue.com/upload/attach/202511/794149_PWFNZ22CBHZEARN.png)
https://github.com/maoabc/nmmp/blob/master/nmmvm/nmmvm/src/main/cpp/vm/InterpC-portable.cpp

| 123 | `.class public Lcom/xgtl/aggregate/activities/SplashActivity;` `0x6A5868` |
|-|-|

| 123 | `byte``[] header = HexParser.parse(``"0100000001000000000000000F000000"``);``byte``[] code_item = HexParser.parse(``"28080000000000000000000000000E0014007B18000071104EDF000028F3"``);``byte``[] fix_code_item = HexParser.parse(``"000014002500000071104ddf00000e0014007b18000071104edf000028f3"``);` |
|-|-|

## 彩蛋3

### [栈回溯](https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/stack.cc#758)

https://xrefandroid.com/android-8.1.0_r81/xref/libcore/ojluni/src/main/java/java/lang/Thread.java#nativeCreate
https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/native/java_lang_Thread.cc
https://xrefandroid.com/android-8.1.0_r81/xref/art/runtime/thread.cc

![img_71.png](https://bbs.kanxue.com/upload/attach/202511/794149_BDZ3A34J2486MYV.png)

| 1234567891011121314 | `57  template <StackVisitor::CountTransitions kCount>``758  void StackVisitor::WalkStack(bool include_transitions) {``759` `if` `(check_suspended_) {``760      DCHECK(thread_ == Thread::Current() \|\| thread_->IsSuspended());``761    }``762    CHECK_EQ(cur_depth_, 0U);``763    bool exit_stubs_installed = Runtime::Current()->GetInstrumentation()->AreExitStubsInstalled();``764    uint32_t instrumentation_stack_depth = 0;``765    size_t inlined_frames_count = 0;``766` `767` `for` `(const ManagedStack* current_fragment = thread_->GetManagedStack();``768         current_fragment != nullptr; current_fragment = current_fragment->GetLink()) {``769      cur_shadow_frame_ = current_fragment->GetTopShadowFrame();``770      cur_quick_frame_ = current_fragment->GetTopQuickFrame();` |
|-|-|

### 致谢

#### [LSPosed](https://github.com/LSPosed/LSPosed)

#### [Dobby](https://github.com/jmpews/Dobby)

#### [dpt-shell](https://github.com/luoyesiqiu/dpt-shell)

#### [androidGRPC](https://github.com/Thehepta/androidGRPC)

以上排名不分前后！！！非常感谢开源的各位大佬们！！！
还有一些一下忘了的开源库，或者脚本，或者代码片段，等我识别出是那个库，我会在这里补充的，感谢！

能看到这里，你也是很最棒的！
这篇也就是浓缩了这些年的加固的一些变化，如果大佬们还有有趣的样本，可以分享出来，让我们一起学习有意思的东西，哈哈哈

---

# 回复

## 回复 by 陈可牛 (#2)

*2025-11-7 01:46*

前三是我的

## 回复 by 陈可牛 (#3)

*2025-11-7 01:46*

前三是我的

## 回复 by 陈可牛 (#4)

*2025-11-7 01:46*

前三是我的

## 回复 by SomeMx (#5)

*2025-11-7 01:58*

图片是不是挂了呀

## 回复 by 陈可牛 (#6)

*2025-11-7 02:05*

>
> [SomeMx](https://bbs.kanxue.com/user-926256.htm)
>
>  图片是不是挂了呀
>
>

是的，在私信处理了，这个我也不知道咋弄

## 回复 by mb_ldbucrik (#7)

*2025-11-7 10:08*

感谢分享

## 回复 by mb_mmlkqxal (#8)

*2025-11-7 12:54*

1111111111111111

## 回复 by baichisi (#9)

*2025-11-7 15:04*

hhh

## 回复 by xianhuimin (#10)

*2025-11-7 15:54*

学习学习

## 回复 by clz3216 (#11)

*2025-11-7 16:20*

6

## 回复 by mb_pesxllvn (#12)

*2025-11-7 17:00*

666

## 回复 by mb_xxezghuh (#13)

*2025-11-7 17:20*

学习学习

## 回复 by shutu (#14)

*2025-11-7 18:41*

666666666666

## 回复 by mb_euhyowpw (#15)

*2025-11-7 22:29*

666

## 回复 by mb_mrjjcxgk (#16)

*2025-11-8 10:32*

666

## 回复 by mb_asiwnxyv (#17)

*2025-11-8 11:14*

感谢分享

## 回复 by mb_wjytplsl (#18)

*2025-11-8 14:26*

666

## 回复 by LQ6H (#19)

*2025-11-8 15:40*

666

## 回复 by KanXue_NG (#20)

*2025-11-8 16:58*

666

## 回复 by huangjw (#21)

*2025-11-10 09:17*

好文章

## 回复 by fangliangz (#22)

*2025-11-10 09:28*

666

## 回复 by GEKEZYX (#23)

*2025-11-10 09:55*

666

## 回复 by NshIdE (#24)

*2025-11-10 11:49*

666

## 回复 by mb_qimctavn (#25)

*2025-11-10 12:20*

6

## 回复 by uni7corn (#26)

*2025-11-10 14:48*

6666

## 回复 by mb_uvyukvot (#27)

*2025-11-10 14:50*

666

## 回复 by artake (#28)

*2025-11-10 18:06*

888

## 回复 by Imxz (#29)

*2025-11-11 14:19*

tql

## 回复 by 龙飞雪 (#30)

*2025-11-11 17:20*

感谢分享

## 回复 by 学编程 (#31)

*2025-11-12 09:06*

666

## 回复 by time.time (#32)

*2025-11-12 15:18*

666

## 回复 by 唱过阡陌 (#33)

*2025-11-12 22:44*

6

## 回复 by focaccia (#34)

*2025-11-14 08:54*

学习了

## 回复 by iBa0 (#35)

*2025-11-14 10:20*

1234

## 回复 by mb_ogxrfmdz (#36)

*2025-11-16 19:40*

6666

## 回复 by axpol (#37)

*2025-11-17 15:05*

666

## 回复 by AK1988DA (#38)

*2025-11-17 17:43*

3

## 回复 by fastji (#39)

*2025-11-17 22:10*

6

## 回复 by 寻梦之璐 (#40)

*2025-11-17 22:41*

666

## 回复 by 黄石 (#41)

*2025-11-20 10:56*

666

## 回复 by mb_xyoslnox (#42)

*2025-11-20 14:12*

6

## 回复 by mb_benfvkcd (#43)

*2025-11-27 14:37*

6666

## 回复 by mb_dcjxxhsk (#44)

*2025-12-7 15:04*

666

## 回复 by zylyy (#45)

*2025-12-7 18:43*

666

## 回复 by Heiyiren123 (#46)

*2025-12-9 09:06*

支持技术分享！

## 回复 by mb_jnmxfjku (#47)

*2025-12-9 18:43*

111

## 回复 by xuhe123 (#48)

*2025-12-11 17:13*

666666

## 回复 by 温泉划水鱼 (#49)

*2025-12-19 00:06*

666

## 回复 by dædalus (#50)

*2025-12-19 02:38*

6

## 回复 by mb_bhsrdtqf (#51)

*2025-12-21 14:44*

6666

## 回复 by tigericon (#52)

*2025-12-22 19:42*

1111

## 回复 by lingyi223 (#53)

*2026-1-8 14:28*

学习

## 回复 by Va1ue (#54)

*2026-1-9 09:09*

6666

## 回复 by mb_ezphxtar (#55)

*2026-1-16 17:05*

66666

## 回复 by mb_jnjwaytf (#56)

*2026-2-2 10:46*

学习

## 回复 by Thehepta (#57)

*2026-2-2 11:38*

不错

## 回复 by mb_bcfbphwt (#58)

*2026-2-2 17:15*

学习了

## 回复 by mb_oksdecri (#59)

*2026-2-9 11:49*

666

## 回复 by qig (#60)

*2026-2-18 11:53*

感谢分享

## 回复 by 我不是卷王 (#61)

*2026-2-19 10:00*

666

## 回复 by mb_qssvgdgi (#62)

*2026-2-26 02:56*

1

## 回复 by 櫬木汐 (#63)

*2026-2-26 19:29*

666

## 回复 by MaxPotato (#64)

*2026-3-4 10:07*

6b

## 回复 by 猪肉炖粉条lr (#65)

*2026-3-10 21:55*

666

## 回复 by git_93836chaos-leo (#66)

*2026-3-24 19:10*

666

## 回复 by 小迷糊ddd (#67)

*2026-4-5 21:18*

感谢分享，认真学习。

## 回复 by nuomida (#68)

*2026-4-15 10:42*

太厉害了

## 回复 by wx_coddvccwyh (#69)

*2026-4-25 21:09*

6666

## 回复 by mb_mhoivioy (#70)

*2026-4-30 04:07*

对于学习帮助很大，十分感谢

## 回复 by Thehepta (#71)

*2026-4-30 10:11*

可以的

## 回复 by pan_634488 (#72)

*2026-4-30 10:26*

666

## 回复 by pan_634488 (#73)

*2026-4-30 10:27*

666

## 回复 by mb_tzeiolnm (#74)

*2026-5-11 08:04*

666

## 回复 by wx_小白_266 (#75)

*2026-6-17 10:41*

看看

## 回复 by mb_qqihqaoo (#76)

*2026-7-3 14:25*

6666
