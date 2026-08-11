---
title: '[原创] android脱壳第二发：grpc-dumpdex加修复'
url: https://bbs.kanxue.com/thread-281359.htm
tid: 281359
author: Thehepta
date: '2024-04-15'
tags: [Android安全, 原创, 工具脚本, 脱壳反混淆, 基础理论]
crawled_at: '2026-08-11T08:45:40+00:00'
replies: 16
---

上一篇我写的dex脱壳，写到银行类型的app的dex修复问题，因为dex中被抽取出来的函数的code_item_off 的偏移所在的内存，不在dex文件范围内，所以需要进行一定的修复，然后就停止了。本来不打算接着搞得，但是写了个框架总得有点真正实用的东西。

### 内存中所有dex遍历

我们所要做的是脱壳，即找到保护的dex,有些dex直接在当前classloader中，有些是自定义classloader然后加载的dex,所以如何找到所有的classloader那，java代码可是没有提供过这种功能。但是frida提供了这种功能，通过符号导出调用虚拟机底部函数对所有类进行遍历（这个不多写了，以前写过）

jobjectArray getClassLoaders(JNIEnv *env, jint targetSdkVersion) {

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445 | `JavaVM` `*``javaVM;``env``-``>GetJavaVM(&javaVM);``JavaVMExt` `*``javaVMExt` `=` `(JavaVMExt` `*``) javaVM;``void` `*``runtime` `=` `javaVMExt``-``>runtime;` `LOGV(``"runtime ptr: %p, vmExtPtr: %p"``, runtime, javaVMExt);``LOGV(``"std::unique_ptr<PartialRuntime13> size: %d"``,  sizeof (std::unique_ptr<PartialRuntime13>));``LOGV(``"get_heap_to_jvm_offset size: %d"``,  get_heap_to_jvm_offset());` `const` `int` `MAX` `=` `5000``;``int` `offsetOfVmExt` `=` `findOffset(runtime,` `0``,` `MAX``, (void``*``) javaVMExt);``LOGV(``"offsetOfVmExt: %d"``, offsetOfVmExt);``int` `head_offset` `=` `offsetOfVmExt``-``get_heap_to_jvm_offset()``+``sizeof (void``*``);``LOGV(``"head_offset: %d"``, head_offset);``void` `*` `heap` `=` `(char``*``)runtime` `+` `head_offset;``AndroidRunAPI``*` `androidRunApi` `=` `AndroidRunAPI::getInstance();``LOGV(``"1"``);``androidRunApi``-``>partialRuntime` `=` `static_cast<PartialRuntime` `*``>(heap);``getAndroidSystemFunction();``LOGV(``"1"``);``LookupClassesVisitor visitor(env, javaVMExt);``LOGV(``"1 %p"``,androidRunApi``-``>VisitClassLoaders);` `androidRunApi``-``>VisitClassLoaders(androidRunApi``-``>partialRuntime``-``>class_linker_,&visitor);``LOGV(``"1"``);` `std::vector<jobject>  vectorObject` `=`  `visitor.getVecObj();``jclass  ClassLoader_cls` `=` `env``-``>FindClass(``"java/lang/ClassLoader"``);``LOGV(``"2"``);` `for` `(auto it` `=` `vectorObject.begin(); it !``=` `vectorObject.end();` `/``*` `no increment here` `*``/``) {``jboolean re` `=`  `env``-``>IsInstanceOf(``*``it,ClassLoader_cls);``if``(!re){``it` `=` `vectorObject.erase(it);``}` `else``{``+``+``it;``}``}` `jobjectArray objectArray` `=` `env``-``>NewObjectArray(vectorObject.size(), ClassLoader_cls, NULL);` `for``(``int` `i``=``0``;i<vectorObject.size();i``+``+``){``env``-``>SetObjectArrayElement(objectArray, i, vectorObject[i]);``}``return` `objectArray;` |
|-|-|

}
我们能遍历系统中所有的类，找到所有类加载，然后通过类加载器找到dex文件（有些cdex文件是系统文件）

用smali开源项目修dex code_item_off错误的文件
越来越懒了，不想多bb了，本来还想多写点扫盲和基础知识点的，懒得写了，直接上才艺。
 ![image](https://bbs.kanxue.com/upload/attach/202404/767217_5QMM6J3D84APZDC.webp)

就上个图片这里，dex文件的code_item 是超过了文件大小的，对于这种是没有办法修复的
花了半个月将grpc项目修了一下
 ![image](https://bbs.kanxue.com/upload/attach/202404/767217_SN2S2VBS4JTDEQP.webp)
连接和使用方式跟以前一样，但是具体的代码在test中
● dumpDexFixCodeItem
从内存中dump dex的codeitem形成修复文件,传入baksmali中作为修复参数

● dumpDexToPC 直接dumpdex 到本地目录
直接将dex dump到电脑上体验一站式dexdump

● dumpDexToAndroidLocal
dumpdex到android上，因为太大的apk中，dex文件过大内存直接爆了比如银行。

● baksmali
调用的smali，传入dex和需要修的codeitem可以将dex反编译成smali，然后将codeitem 也反编译进去

● smali
将 baksmali 编译出来的 smali工程编译为dex

### 使用顺序

● 使用dumpDexToPC 和 dumpDexToAndroidLocal 向dump dex文件
● 使用dumpDexFixCodeItem dump dex文件的code_item 到修复文件中
● 使用baksmali 传入dex文件和 code_item 修复文件反编译为smali工程
● 使用smali 将smali 工程反编译为dex

### 效果图

这个上次的文章中某银行dex最终的修复结果
 ![1231](https://bbs.kanxue.com/upload/attach/202404/767217_FMU3PYNHKGV4MP5.webp)
使用中存在的问题
● dump出来的dex文件格式有问题：可能是cdex文件，也有可能是dex文件格式已经被破坏，如果是dex文件格式被破坏，可以通过自己编写更早时期的dex加载时dump来找到dex文件
● dumpDexToPC 导致程序崩溃了，这是因为文件太大内存爆满了，用dumpDexToAndroidLocal 手动去下载吧。
● 修复失败，修完了以后函数仍然找不到，我目前是用的是类加载，如果抽取函数是通过类加载还原的，这种方式是可以dump出code_item的，如果函数是通过必须要执行函数实体一次才能还原的话，这个可能需要你想办法让函数执行，并且确保被抽取的函数已经还原了，没有再次加密回去。
● baksmail 反编译中会剥离调试信息，参数名。smali回编译经过修改会忽略某些函数没有执行实体的错误。

### 废话

相比fart还是差了半截，活太多了只能先到这，不过比fart优雅多了，毕竟优雅永不过时

### future

如果你想接着研究，但是又不知道该怎么继续研究下去，不知道我这个方向是不是死胡同，那我给点建议。
● 修复，如果逆向继续研究修复，用smali编译来编译去优雅程度还是有所欠缺的，而且我写的不完善要一个类一个类的还原，这方面我建议去看看dexmaker这类动态生成dex的源码，在内存中动态生成dex进行修复，或者android源码dex优化部分（我在调试dump debug模式的dex的时候发现dex和apk安装中的dex是不太一样的，查了一下说是优化了）
● dump dex，我目前采用的是程序运行中间dump,这个时候dex容易被破坏，可以hook开始的位置dumpdex
● dump code item ,这个是个坑，如果是函数运行一次还原还好一点，但是我不太确定是否有非常恶心的那些，比如不断覆盖重复运行，或者运行完再次加密，只要他能牺牲效率什么都做得出来，自己保重。

项目地址：
<https://github.com/Thehepta/androidGRPC>

最后
smali 和baksmali的jar包扔在项目里，就暂时不开源了，扔知识星球了，有几位老哥加了我的知识星球，总得搞点有用的东西。jar都扔出来了，也不算食言吧。
发个公众号
 ![image](https://bbs.kanxue.com/upload/attach/202404/767217_4R7C46G6PDCFDXC.webp)

补：
有兄弟说工具太复杂了，这个工具开发者可能才能玩的6，脱壳分四步，我博客里写的分为4个test,每个test都需要执行一步。
1.先脱dex,dumpDexToPC
2.dump code_item ,会形成一个修复文件
3.用baksmali 将dex和修复文件一起调用，会反编译为经过修复的smali工程
4.用smali将smali工程回编译为dex

有时间录个视频吧，或者你可以等下次项目更新，估计能做到一键式脱壳

---

# 回复

## 回复 by tDasm (#2)

*2024-4-15 22:16*

既然是工具，就应该编译好让别人直接用。大家只需悟原理就行。看了你二篇也没搞懂你到底要表达什么意思？如何重构dex文件估计10年前就有一大把！
怎么使用我猜是这样，不知道对不对？
1安装你写的Rxposed
2安装你这个远程调用模块
3运行pc端客户连接远程模块执行远程调用并dumpdex
不知道你怎么修复抽取代码？你调用类的每个方法怎么构造入口参数？

## 回复 by Thehepta (#3)

*2024-4-16 00:03*

加了两张照片

## 回复 by tDasm (#4)

*2024-4-16 08:32*

为什么要远程调用？你不觉得多余吗？
Rxposed把dump模块注入到目标进程在适当时机直接dumpdex即可，为什么非要远程调用dump？

## 回复 by 秋狝 (#5)

*2024-4-16 09:18*

感谢分享

## 回复 by Thehepta (#6)

*2024-4-16 09:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  tDasm](https://bbs.kanxue.com/user-382.htm)
>
>  为什么要远程调用？你不觉得多余吗？
> Rxposed把dump模块注入到目标进程在适当时机直接dumpdex即可，为什么非要远程调用dump？
>
>

我先回答你这个问题，为什么非要远程调用：远程调用可以直接在pc上将dex直接dump到pc目录中，不用adb 再去将dex pull出来，这不方便吗
另外你用过我这个grpc，你都不懂grpc的价值，fart脱壳必须要先脱壳，然后脱下来修复，用grpc，以后做好了可以一键式脱壳，grpc脱到pc直接修复。
你在上面说的，你调用类的每个方法怎么构造入口参数？我博客了里有些，目前不支持方法主动调用，只支持类加载主动调用。

## 回复 by Thehepta (#7)

*2024-4-16 09:32*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  tDasm](https://bbs.kanxue.com/user-382.htm)
>
>  为什么要远程调用？你不觉得多余吗？
> Rxposed把dump模块注入到目标进程在适当时机直接dumpdex即可，为什么非要远程调用dump？
>
>

如何重构dex文件估计10年前就有一大把，你给我找找，除了fart 寒冰大佬提供的修复工具，目前有那个项目能修复code_item 偏移错误

## 回复 by tDasm (#8)

*2024-4-16 11:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Thehepta](https://bbs.kanxue.com/user-767217.htm)
>
>  如何重构dex文件估计10年前就有一大把，你给我找找，除了fart 寒冰大佬提供的修复工具，目前有那个项目能修复code_item 偏移错误
>
>

这也难怪你重复造轮子？你要善于搜索，这个论坛就有。在内存中重构dex文件然后dump。

## ZjDroid是基于Xposed Framewrok的动态逆向分析模块，逆向分析者可以通过ZjDroid完成以下工作： 1、DEX文件的内存dump 2、基于Dalvik关键指针的内存BackSmali，有效破解主流加固方案 3、敏感API的动态监控 4、指定内存区域数据dump 5、获取应用加载DEX信息。 6、获取指定DEX文件加载类信息。 7、dump Dalvik [Java](http://lib.csdn.net/base/java)堆信息。 8、在目标进程动态运行lua脚本。

## 回复 by tDasm (#9)

*2024-4-16 11:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Thehepta](https://bbs.kanxue.com/user-767217.htm)
>
>  我先回答你这个问题，为什么非要远程调用：远程调用可以直接在pc上将dex直接dump到pc目录中，不用adb 再去将dex pull出来，这不方便吗
> 另外你用过我这个grpc，你都不懂grpc的价值 ...
>
>

你说的这些完全不需要远程调用。fart既可以本地修复也可以把dump下来的数据复制到pc上在pc上修复。

## 回复 by 熊趴趴来 (#10)

*2024-4-16 11:22*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  tDasm](https://bbs.kanxue.com/user-382.htm)
>
>  既然是工具，就应该编译好让别人直接用。大家只需悟原理就行。看了你二篇也没搞懂你到底要表达什么意思？如何重构dex文件估计10年前就有一大把！
> 怎么使用我猜是这样，不知道对不对？
> 1安装你写的Rxp ...
>
>

只会在这里吹毛求疵，怎么不搞一个工具共享出来，别人共享的工具是影响到你的利益了吗，MDZZ

## 回复 by Thehepta (#11)

*2024-4-16 11:23*

算了，免费开源，喜欢支持下，不喜欢可以不用，ZjDroid 这个确实能修复，我得承认，但是我需要dump下来修复，本来也不是给小白用的，我这个框架也不是给小白用的，就这样

## 回复 by tDasm (#12)

*2024-4-16 11:40*

>
> [熊趴趴来](https://bbs.kanxue.com/user-307313.htm)
>
>  只会在这里吹毛求疵，怎么不搞一个工具共享出来，别人共享的工具是影响到你的利益了吗，MDZZ
>
>

你用了别人的工具，只是你不知道是谁？因为你没有思维逻辑！

## 回复 by tDasm (#13)

*2024-4-16 11:42*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Thehepta](https://bbs.kanxue.com/user-767217.htm)
>
>  算了，免费开源，喜欢支持下，不喜欢可以不用，ZjDroid 这个确实能修复，我得承认，但是我需要dump下来修复，本来也不是给小白用的，我这个框架也不是给小白用的，就这样
>
>

我只是帮你搜了一下10年前的东西。当然不只这一个修复dex工具.记得还有一个用python写的内存组装修复dex并dump的代码

## 回复 by mb_fidppcok (#14)

*2024-4-19 14:46*

个人还是得看视频 才懂。。感觉看大佬的文章太复杂 了

## 回复 by huluxia (#15)

*2024-4-19 15:24*

感觉太复杂了。

## 回复 by Thehepta (#16)

*2024-4-19 21:54*

>
> [huluxia](https://bbs.kanxue.com/user-629109.htm)
>
>  感觉太复杂了。
>
>

是的，要分四步。确实有一点。这个更的有点仓促了，等过段时间等我第三次更新吧，我准备搞成一件自动脱壳的

## 回复 by leisurely (#17)

*2024-4-20 09:42*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Thehepta](https://bbs.kanxue.com/user-767217.htm)
>
>  是的，要分四步。确实有一点。这个更的有点仓促了，等过段时间等我第三次更新吧，我准备搞成一件自动脱壳的
>
>

学习了，感谢无私的分享知识，也期待更新。![image](https://bbs.kanxue.com/view/img/face/63.gif)
