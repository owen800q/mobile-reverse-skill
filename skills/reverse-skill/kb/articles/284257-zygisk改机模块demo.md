---
title: '[原创]zygisk改机模块demo'
url: https://bbs.kanxue.com/thread-284257.htm
tid: 284257
author: 螺丝兔
date: '2024-11-05'
tags: [Android安全, 原创, 基础理论, 工具脚本]
crawled_at: '2026-07-31T14:18:51+08:00'
replies: 10
---

# 前置知识

做这个的话推荐使用Andoridstudio。

## Zygote 进程

init 进程在解析 init.rc 脚本时，会创建 Zygote 进程，只有该进程才会建立起真正的 Android 运行空间，它是 Android 系统最重要的进程之一。后续 Android 中的应用进程都是由 Zygote 进程 Fork 出来的，因此，Zygote 是 Android 系统所有应用的父进程（即 Java 进程的鼻祖）。
注：Zygote 进程的出现是为了能更快的启动应用。因为在 Android 中，每个应用都有对应一个虚拟机实例（VM）为应用分配不同的内存地址。如果 Android 系统为每一个应用启动不同的 VM 实例，就会消耗大量的内存以及时间。因此，更好的办法应当是通过创建一个虚拟机进程，由该 VM 进程预加载以及初始化核心库类，然后，由该 VM 进程 Fork 出其他虚拟机进程，这样就能达到代码共享、低内存占用以及最小的启动时间，而这个 VM 进程就是 Zygote。
这里因为其他进程都是由zygote fork出去的，所以如果实现了注入zygote，那么就对几乎所有进程实现HOOK。

## LD_PRELOAD

设置该属性可以强制给指定进程优先加载指定库，但是这里的优先感觉有点强制的感觉吧，我试过给ls指定一个自定义的库，然后观察日志发现ls时该库里的init函数立刻执行了。LD_PRELOAD的具体讲解也有文章不再详说。

## Zygisk

magisk实现zygote注入的方式，使用zygisk可以编写zygisk格式的模块来便宜进行HOOK。具体实现有文章可以看看。

## zygisk模块编写

示例模块：<https://github.com/topjohnwu/zygisk-module-sample>
这个github项目中module->jni->libcxx在另一个项目地址，需要单独下载的样子，直接在项目中点击libcxx那个跳转前往下载，可能git拉取下来的话不需要这样？
 ![图片描述](https://bbs.kanxue.com/upload/attach/202411/992277_5R4U5W9XUFERA2S.webp)

jni下的example.cpp存储着主要的HOOK逻辑。
Android.mk存储着编译逻辑，当然，这是使用ndk-build来编译的话，使用Cmake的话想必也是可以的，但是我想的是实现最基础的使用所以先按照项目示例中所说使用的ndk-build，具体编译就是确认mk文件无差后在module目录下使用ndk-build即可。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202411/992277_987TGZQGQ42JWFR.webp)
生成文件会在对应的这里。
然后按照zygisk模块的格式打包即可。
如图： ![图片描述](https://bbs.kanxue.com/upload/attach/202411/992277_ZBW3UUC77BHUW25.webp)
应该是只要有zygisk这个文件夹就可以识别出，因为我为了方便直接放在了之前做实验的magisk模块中也成功识别。这里要注意的是把相应架构的so文件放到zygisk文件夹下并重命名为相应架构。
然后就是正常安装模块。

## Dobby

一个HOOK用的轻量化的框架。
在github上有项目，但是，至少我查看的时候release里，应该，是没有android的相应文件叭，我的环境似乎也无法正常编译，于是找到了一个旧的22年的：<https://github.com/LSPosed/Dobby/tree/latest>
该项目release有着android的相应文件，但是使用时还是出了些问题，解决方法我没记错的话是在cmake文件中加上一句set(CMAKE_POSITION_INDEPENDENT_CODE ON)后重新编译dobby.a解决问题。这个的编译我是正常通过的。

# 模块编写

首先肯定是要找一些改机模块进行学习，但是大都是通过magisk的resetprop这种来设置属性，这样的话对我的学习没有任何作用，还好还是找到了一篇通过riru实现对system_property_get进行HOOK改机的文章<https://www.cnblogs.com/luoyesiqiu/p/magisk_riru.html>
这篇文章真的是帮大忙了，学习了它的编写逻辑，大致思路就是通过riru的zygote注入，再结合dobby编写了riru模块对system_property_get进行了HOOK，修改返回系统属性实现。
但是riru已经停更好久了，而且在实验中我也编译了riru的模块来使用，但是对于安卓十三来说应该是不适用了，然后对于该原因的分析也没有找到文章，遂自己去小看了下源码，不过也没有找到具体原因。虽然有看到源码的部分变化处，比如 ![图片描述](https://bbs.kanxue.com/upload/attach/202411/992277_NJ5BVQSM53E28DJ.webp)
![图片描述](https://bbs.kanxue.com/upload/attach/202411/992277_X99Q5ER2PZB8QQ4.webp)
但是感觉我看到的变化似乎影响不是很大，在查看日志的时候我也故意使用不规范的命名，但是没有看到报错日志，所以我怀疑可能我的手机可能根本没有启用nativebridge？唉，主要还是关于riru停更后关于这种注入方式的文章我几乎找不到，也没有太多时间花在这上面，遂使用的zygisk。

riru扯得有些多了，还是把话题说回到zygisk模块编写上吧。既然有了riru的改机模块示例，那么要做的就是学习他的方法，并移植到zygisk上，然后我查看了riru和zygisk示例模块中的函数，发现相似度还是很高的。
比如riru改机模块中是将HOOK的实现放在forkAndSpecializePost函数下 ![图片描述](https://bbs.kanxue.com/upload/attach/202411/992277_NTKHSQ493M2VJV4.webp)
forkAndSpecializePost 钩子允许开发者在新进程创建之后立即对其进行调整，而相应的我只要把HOOK的实现放在zygisk的preAppSpecialize函数中即可。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202411/992277_MJQ258H9ZNVZ662.webp)

## 模块代码的具体实现

### init函数

| 12345678910111213141516 | `void initDobby(){``if` `(hook_initialized) {``LOGD(``"HOOK already initialized, skipping..."``);``return``;``}``hook_initialized` `=` `true;``LOGD(``"HOOK_init"``);``void``*` `sym``=``DobbySymbolResolver(NULL,``"__system_property_get"``);``/``/``获取函数指针？``if``(NULL!``=``sym){``DobbyHook((void``*``)sym,(dobby_dummy_func_t) my_system_property_get,(dobby_dummy_func_t` `*``) &origin__system_property_get);` `}``else``{``LOGD(``"can not found the sym of __system_property_get"``);``}``}` |
|-|-|

获取__system_property_get的函数指针，使用DobbyHOOK把原始函数替换为我们的自定义函数。

| 12345678910111213141516 | `static` `int` `my_system_property_get(const char``*` `_Nonnull name, char``*`  `_Nonnull value){` `readPropFile(PROP_CONF_PATH,propMap);``if``(NULL``=``=``name \|\| NULL``=``=``value){``LOGD(``"内容为空"``);``return` `origin__system_property_get(name,value);``}``auto ret``=``propMap.find(name);``if``(ret!``=``propMap.end()){``LOGD(``"find key '%s'"``,ret``-``>first.c_str());``const char``*` `valueChs``=``ret``-``>second.c_str();``/``/``value的值``strcpy(value,valueChs);``return` `strlen(valueChs);``}``return` `origin__system_property_get(name,value);``}` |
|-|-|

如果我们设置的值在被查询，则替换并返回，如果不是则调用原始函数。
除了native层还要修改java层。

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849 | `static void setBuild(JNIEnv``*` `env) {``/``/` `查找 Build 类``jclass BuildClass` `=` `env``-``>FindClass(``"android/os/Build"``);``if` `(BuildClass` `=``=` `NULL) {``LOGD(``"Failed to find class android/os/Build"``);``return``;``}` `/``/` `遍历 buildMap 设置属性``for` `(auto it` `=` `buildMap.begin(); it !``=` `buildMap.end();` `+``+``it) {``LOGD(``"Setting build prop -> key = %s, value = %s"``, it``-``>first.c_str(), it``-``>second.c_str());` `/``/` `创建 key 和 value 的 JNI 字符串``jstring key` `=` `env``-``>NewStringUTF(it``-``>first.c_str());``jstring value` `=` `env``-``>NewStringUTF(it``-``>second.c_str());` `/``/` `检查创建结果``if` `(key` `=``=` `NULL \|\| value` `=``=` `NULL) {``LOGD(``"Failed to create JNI string for key or value."``);``if` `(key !``=` `NULL) env``-``>DeleteLocalRef(key);``if` `(value !``=` `NULL) env``-``>DeleteLocalRef(value);``continue``;``}` `/``/` `获取属性字段` `ID``jfieldID buildField` `=` `env``-``>GetStaticFieldID(BuildClass, it``-``>first.c_str(),` `"Ljava/lang/String;"``);``if` `(env``-``>ExceptionCheck() \|\| buildField` `=``=` `NULL) {``env``-``>ExceptionClear();``LOGD(``"Failed to get field ID for key = %s"``, it``-``>first.c_str());``env``-``>DeleteLocalRef(key);``env``-``>DeleteLocalRef(value);``continue``;``}` `/``/` `设置字段值``env``-``>SetStaticObjectField(BuildClass, buildField, value);``if` `(env``-``>ExceptionCheck()) {``env``-``>ExceptionClear();``LOGD(``"Failed to set field for key = %s"``, it``-``>first.c_str());``}` `/``/` `释放局部引用``env``-``>DeleteLocalRef(key);``env``-``>DeleteLocalRef(value);``}` `/``/` `释放 BuildClass 的引用``env``-``>DeleteLocalRef(BuildClass);``}` |
|-|-|

这就是主要的代码，全部的代码我会传附件，但是是学习的rirugaiji，所以代码的实现和其大差不差，这里还是很感谢那位师傅能够将知识分享出来。
编译后在pixel6手机上安装模块效果图：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202411/992277_JRVWN59RR6WW86J.webp)
这个也算先告一段落了，因为这个月有很多考试，所以恐怕没有时间来完善这个改机。打算的是这个月学些零散的东西，下个月有大块时间的话想要再改进完善这个模块或者学习其他吧。这毕竟只是个小demo，实在过于简陋，下一步设想的是仿照riru添加守护进程及交互等，并尝试整合进Apatch的kp模块。

代码附件有点大，传不了，放云盘了。
通过网盘分享的文件：zygisk-module-sample-master.zip
链接: <https://pan.baidu.com/s/1J6dmiAXhrv9V1_cLiBY3tw?pwd=rea1> 提取码: rea1
--来自百度网盘超级会员v4的分享

使用需要在data/local/tmp下写入文件，然后会读取。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202411/992277_EECVAVK7NC5KYR2.webp)

上传的附件：
- gaiji.zip

（1.05MB，165次下载）

---

# 回复

## 回复 by 果冻大砍刀 (#2)

*2024-12-13 18:18*

这两个文件格式是啥样的呀

## 回复 by vmoveq (#3)

*2024-12-14 11:20*

```
void* sym=DobbySymbolResolver(NULL,"__system_property_get");
```
这样写可能会引起崩溃，应该传入一个实际的路径给他

## 回复 by mb_cawopqfr (#4)

*2025-8-6 16:08*

大佬, 请问下zygisk怎么改java层的?

## 回复 by younghare (#5)

*2025-9-12 16:49*

libc++_shared.so 是否也得发布在模块的zygisk目录下？
我改为不生成共享库
# APP_STL      := c++_shared  # 使用共享的 C++ 标准库  这个方法回多生成一个ibc++_shared.so
APP_STL      := c++_static  # 不使用共享的 C++ 标准库，只要求生成一个libexample.so

## 回复 by 螺丝兔 (#6)

*2025-9-17 11:43*

>
> [younghare](https://bbs.kanxue.com/user-746297.htm)
>
>  libc++_shared.so 是否也得发布在模块的zygisk目录下？
> 我改为不生成共享库
> # APP_STL := c++_shared # 使用共享的 C++ 标准库 这个方 ...
>
>

可以的，我写的时候这块一知半解只追求了个能跑![image](https://bbs.kanxue.com/view/img/face/055.gif)

## 回复 by mb_eapusocg (#7)

*2025-9-26 10:24*

大佬，有能直接使用的成品吗

## 回复 by oscar99999 (#8)

*2025-10-31 11:37*

ro.product.manufacturer=samsung
ro.product.brand=samsung
ro.product.model=SM-S9160 大佬格式，内容大概是这样的么

## 回复 by 螺丝兔 (#9)

*2025-11-1 21:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  oscar99999](https://bbs.kanxue.com/user-874764.htm)
>
>  ro.product.manufacturer=samsung
> ro.product.brand=samsung
> ro.product.model=SM-S9160 大佬格式，内容大概是这样的么
>  ...
>
>

是这样，其实看下那个github项目就可以了，我整体都是参考的这位佬的操作，而且这个demo还需要去完善很多

## 回复 by zmguozi (#10)

*2025-11-4 16:00*

这个zip哪里下载

## 回复 by mb_lpuubxuh (#11)

*2025-11-29 01:13*

大佬怎么联系？这边有开发需求
