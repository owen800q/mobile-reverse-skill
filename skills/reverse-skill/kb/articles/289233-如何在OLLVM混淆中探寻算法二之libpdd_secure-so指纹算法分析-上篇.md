---
title: '[原创]如何在OLLVM混淆中探寻算法二之libpdd_secure.so指纹算法分析(上篇)'
url: https://bbs.kanxue.com/thread-289233.htm
tid: 289233
author: KanXue_NG
date: '2025-11-27'
tags: [Android安全, 原创, 协议分析]
crawled_at: '2026-08-08T10:37:21+00:00'
replies: 37
---

0x1-前言:

这是<如何在OLLVM混淆中探寻算法>系列的第二篇文章,相信读者通过前面文章的学习,已经对unidbg有了初步的认识,这篇是unidbg的一个进阶,样本涉及的依赖相对前面文章的样本来说比较多,主要是jni调用与文件访问的问题,笔者将拆分成两篇来讲述,一篇是unidbg补环境,一篇是算法分析.国内有难度的样本有四个,分别是libmetasec_ml.so,libsgmain.so,libmtguard.so,libtiny.so,还有一个unidbg补环境的高峰--同盾样本,本篇的样本在这五个样本看来,难度上算简单的.此文是我公众号上面发布后复制过来的,图片和代码块可能会有显示的问题,请移步我的原文:

> aHR0cHM6Ly9tcC53ZWl4aW4ucXEuY29tL3MvT0NOUkFfVC1Fek1jRHNjUVBCSDJSUQ==
>
>

也欢迎各位师傅关注我的公众号.

0x2-样本信息:

链接直达:

\```
aHR0cHM6Ly93d3cud2FuZG91amlhLmNvbS9hcHBzLzY2NDk1OTEvaGlzdG9yeV92NzgwMDA=
\```

version:

\```
7.80.0
\```

0x3-抓包分析与入口定位:

![图片](https://bbs.kanxue.com/upload/attach/202511/MSUMEYF27UCKFPF.jpg)

每个接口的头部都会带上anti_token这个参数,且是2af为前缀的,这个就是我们的目标了,至于定位入口,关键字搜索/hook newstringutf都能定位到.

笔者就不带着大家去跟一遍了,看过我前面的文章,脚本拿过来改一改就能定位了,贴一下最终的入口.

\```
    package com.xunmeng.pinduoduo.secure;
\```

这个info2方法就是最终的入口位置了,他所属的so是libpdd_secure.so,他的入参是一个content和long类型,long类型的参数是时间戳,可以使用我这篇文章的脚本,把native方法的信息枚举出来.

> 文章跳转
>
> Fashion哥，公众号：Fashion哥的爬虫历险记[安卓Native层逆向-只通过一个native方法名枚举出native方法的所有信息](https://mp.weixin.qq.com/s/meqLKz8BoFTxbAfx97pDNg)
>
>

0x4-Unidbg搭架子补环境

先搭个架子:

\```
import com.github.unidbg.AndroidEmulator;
\```

读者也不必着急复制粘贴,文章末尾会贴一份补好的环境代码.

0x01-补Jni调用

右键运行,发现报了个错

\```
com/xunmeng/core/log/Logger->i(Ljava/lang/String;Ljava/lang/String;)V
\```

![图片](https://bbs.kanxue.com/upload/attach/202511/U27V2D2VGG2XQF5.jpg)

对于此方法,他的返回值是void,我们直接返回即可.

\```
@Overridepublic void callStaticVoidMethodV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {    switch (signature){        case "com/xunmeng/core/log/Logger->i(Ljava/lang/String;Ljava/lang/String;)V":            return;    }    super.callStaticVoidMethodV(vm,dvmClass,signature,vaList);}
\```

补完发现没有其他报错了,红色的日志是样本自己调用的打印方法,我们可以不管.

![图片](https://bbs.kanxue.com/upload/attach/202511/F29MEUCA7S47AJD.jpg)

接下来是主动调用目标函数,这里有两种方法一种是通过符号去调用,另一种是通过地址去调用,笔者比较习惯符号调用.

\```
//主动调用public String callInfo2(long jParam) {    //调用静态native方法    DvmObject<?> result = DeviceNative.callStaticJniMethodObject(            emulator,            "info2(Landroid/content/Context;J)Ljava/lang/String;",            vm.resolveClass("android/content/Context").newObject(null),            jParam    );    //获取并返回结果    return (String) result.getValue();}
\```

info2方法的参数有两个一个是android/content/Context,一个是long,

对于java的八大基本数据类型(byte,char,int,short,long,double,float)等不用做处理,可以直接原封不动的传递,其他的要做包装,像这样进行一层包装.

\```
vm.resolveClass("类型").newObject(null)
\```

在main进行调用

\```
public static void main(String[] args){    Pdd_Sec pdd_sec_test = new Pdd_Sec();    String antitoken = pdd_sec_test.callInfo2(1759120327158L);    System.out.println("Anti_token =======>" + antitoken);}
\```

运行

![图片](https://bbs.kanxue.com/upload/attach/202511/APRZ9VG77RR9U9X.jpg)

报了这个错误

\```
android/content/Context->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
\```

此方法是Android框架中用于获取系统级服务的方法

谷歌官网文档

\```
https://developer.android.com/reference/android/content/Context#getSystemService(java.lang.String)
\```

如果对方法不是很了解的可以看看谷歌的开发文档

\```
https://developer.android.com/reference/
\```

可以这样补

\```
@Overridepublic DvmObject<?> callObjectMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {    switch (signature) {        case "android/content/Context->getSystemService(Ljava/lang/String;)Ljava/lang/Object;":            // 获取服务名称            String serviceName = varArg.getObjectArg(0).getValue().toString();            System.out.println("请求系统服务: " + serviceName);            return null;    }    return super.callObjectMethod(vm,dvmObject,signature,varArg);}
\```

打印看看是获取了哪些系统服务

![图片](https://bbs.kanxue.com/upload/attach/202511/MDQEHV9QX5PQ9XW.jpg)

只获取了一个,可以写个判断,然后返回

\```
@Overridepublic DvmObject<?> callObjectMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {    switch (signature) {        case "android/content/Context->getSystemService(Ljava/lang/String;)Ljava/lang/Object;":            // 获取服务名称            String serviceName = varArg.getObjectArg(0).getValue().toString();            System.out.println("请求系统服务: " + serviceName);            // 根据服务名称返回不同的对象            if (serviceName.equals("phone")) {                // 返回TelephonyManager对象                return vm.resolveClass("android/telephony/TelephonyManager").newObject(null);            }    }    return super.callObjectMethod(vm,dvmObject,signature,varArg);}
\```

![图片](https://bbs.kanxue.com/upload/attach/202511/BS4VH8FRDR4K9H6.jpg)

这个需要frida去主动调用一下拿到结果,返回结果是个string类型,要用unidbg的api封装一下.

\```
@Overridepublic DvmObject<?> callStaticObjectMethodV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {    switch (signature) {        case "com/xunmeng/pinduoduo/secure/EU->gad()Ljava/lang/String;":            return new StringObject(vm,"49b8d5557d5bafd9");    }    return super.callStaticObjectMethodV(vm,dvmClass,signature,vaList);}
\```

![图片](https://bbs.kanxue.com/upload/attach/202511/HB9B4MYAVTE3Z6W.jpg)

同样的,用frida主动调用获取结果,返回时int,基本数据类型,就不用封装.

\```
@Overridepublic int callIntMethod(BaseVM vm, DvmObject<?> dvmObject, DvmMethod dvmMethod, VarArg varArg) {    if("android/telephony/TelephonyManager->getSimState()I".equals(dvmMethod.toString())){        return 1;    }    return super.callIntMethod(vm, dvmObject, dvmMethod, varArg);}
\```

接着是这个,主动调用获取结果

![图片](https://bbs.kanxue.com/upload/attach/202511/8BG39QBB6YUHMZT.jpg)

\```
case "android/telephony/TelephonyManager->getSimOperatorName()Ljava/lang/String;":    return new StringObject(vm, "");
\```

接着是这个,主动调用获取结果

![图片](https://bbs.kanxue.com/upload/attach/202511/GGX2FF3UYY3DUM2.jpg)

\```
case "android/telephony/TelephonyManager->getSimCountryIso()Ljava/lang/String;":    return new StringObject(vm, "");
\```

接着是这个

![图片](https://bbs.kanxue.com/upload/attach/202511/3MJARWKZ2J4VHMG.jpg)

\```
if("android/telephony/TelephonyManager->getNetworkType()I".equals(dvmMethod.toString())){    return 0;}
\```

下一个是

![图片](https://bbs.kanxue.com/upload/attach/202511/NFSV3ENF93QQ48A.jpg)

\```
case "android/telephony/TelephonyManager->getNetworkOperator()Ljava/lang/String;":    return new StringObject(vm, "");
\```

下一个是

![图片](https://bbs.kanxue.com/upload/attach/202511/QM6T7MUSNABYFHE.jpg)

\```
case "android/telephony/TelephonyManager->getNetworkOperatorName()Ljava/lang/String;":    return new StringObject(vm, "");
\```

下一个接着

![图片](https://bbs.kanxue.com/upload/attach/202511/WFHRDV9KVRTSP3P.jpg)

\```
case "android/telephony/TelephonyManager->getNetworkCountryIso()Ljava/lang/String;":    return new StringObject(vm, "cn");
\```

![图片](https://bbs.kanxue.com/upload/attach/202511/PDEGR2PE784KGBN.jpg)

\```
if("android/telephony/TelephonyManager->getDataState()I".equals(dvmMethod.toString())){    return 0;}
\```

![图片](https://bbs.kanxue.com/upload/attach/202511/WQ895QG6BPQVFFN.jpg)

\```
if("android/telephony/TelephonyManager->getDataActivity()I".equals(dvmMethod.toString())){    return 0;}
\```

![图片](https://bbs.kanxue.com/upload/attach/202511/9KMW8J4EXM9PGWE.jpg)

这个方法是判断是否处于调试连接,给他返回false

\```
@Overridepublic boolean callStaticBooleanMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {    switch (signature){        case "android/os/Debug->isDebuggerConnected()Z":            return false;    }    return super.callStaticBooleanMethod(vm,dvmClass,signature,varArg);}
\```

![图片](https://bbs.kanxue.com/upload/attach/202511/Z5EWTX98W3QW4QQ.jpg)

对于这种方法,不会补怎么办,看unidbg的示例代码,看unidbg如何写的,我们也跟着写.

点击(AbstractJni.java:753)跳转过去

![图片](https://bbs.kanxue.com/upload/attach/202511/J564FUV6GCGTCZJ.jpg)

unidbg提供了两个示例,我们也跟着改一改

\```
@Overridepublic DvmObject<?> newObject(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {    switch (signature) {        case "java/lang/Throwable-><init>()V":            return vm.resolveClass("java/lang/Throwable").newObject(new Throwable());    }    return super.newObject(vm, dvmClass, signature, varArg);}
\```

接着继续

![图片](https://bbs.kanxue.com/upload/attach/202511/BF5ZPF5QR84RH5T.jpg)

他需要的返回值是

\```
[Ljava/lang/StackTraceElement
\```

我们可以用unidbg提供的api嵌套返回.

\```
new ArrayObject(vm.resolveClass("java/lang/StackTraceElement").newObject(null),...,...)
\```

代码如下

\```
case "java/lang/Throwable->getStackTrace()[Ljava/lang/StackTraceElement;":    return new ArrayObject(            vm.resolveClass("java/lang/StackTraceElement").newObject(null),            vm.resolveClass("java/lang/StackTraceElement").newObject(null),            vm.resolveClass("java/lang/StackTraceElement").newObject(null)    );
\```

![图片](https://bbs.kanxue.com/upload/attach/202511/NFFKP7EM88R2E5T.jpg)

\```
case "java/lang/StackTraceElement->getClassName()Ljava/lang/String;":    return new StringObject(vm,"");
\```

下面是一个replaceall方法

![图片](https://bbs.kanxue.com/upload/attach/202511/G2NZTCFHVQRW8Z9.jpg)

可以点进去看看unidbg如何实现的,改一改代码即可

\```
@Overridepublic DvmObject<?> callObjectMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {    switch (signature) {        case "java/lang/String->replaceAll(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;":            // 获取原始字符串            String original = (String) dvmObject.getValue();            // 获取正则表达式参数            DvmObject<?> regexObj = vaList.getObjectArg(0);            String regex = (String) regexObj.getValue();            // 获取替换字符串参数            DvmObject<?> replacementObj = vaList.getObjectArg(1);            String replacement = (String) replacementObj.getValue();            // 执行正则替换            String result = original.replaceAll(regex, replacement);            return new StringObject(vm, result);    }    return super.callObjectMethodV(vm,dvmObject,signature,vaList);}
\```

当补到这个方法时,离成功已经很接近了,同时也要注意,这个jni调用也拖带出了第一个算法gzip

![图片](https://bbs.kanxue.com/upload/attach/202511/H8AGGQ2GYQF2SZ9.jpg)

\```
case "java/io/ByteArrayOutputStream-><init>()V":    ByteArrayOutputStream OutputMemoryBuffer = new ByteArrayOutputStream();    return vm.resolveClass("java/io/ByteArrayOutputStream").newObject(OutputMemoryBuffer);
\```

![图片](https://bbs.kanxue.com/upload/attach/202511/2RPAPFKHCP4GXDN.jpg)

\```
case "java/util/zip/GZIPOutputStream-><init>(Ljava/io/OutputStream;)V":    try{        ByteArrayOutputStream MemoryBuffer = (ByteArrayOutputStream) varArg.getObjectArg(0).getValue();        GZIPOutputStream GzipCompressiveFlow = new GZIPOutputStream(MemoryBuffer);        return vm.resolveClass("java/util/zip/GZIPOutputStream").newObject(GzipCompressiveFlow);    }catch (Exception e){}
\```

注意补这个方法要外层套上try-catch

![图片](https://bbs.kanxue.com/upload/attach/202511/KGR4ZM9BK64BVY5.jpg)

对于此方法,我们也可以看看unidbg内部时如何实现的,然后照猫画虎

![图片](https://bbs.kanxue.com/upload/attach/202511/E5AMYG898TNZWQJ.jpg)

\```
/**
\```

![图片](https://bbs.kanxue.com/upload/attach/202511/PNXG6BB7S4T475F.jpg)

\```
case "java/util/zip/GZIPOutputStream->finish()V":    GZIPOutputStream GzipCompressiveFlow1 = (GZIPOutputStream)dvmObject.getValue();    try{        GzipCompressiveFlow1.finish();    }catch(Exception e){}    return;
\```

![图片](https://bbs.kanxue.com/upload/attach/202511/V3WSFZFJMYPUEAR.jpg)

\```
case "java/io/ByteArrayOutputStream->toByteArray()[B":    ByteArrayOutputStream MemoryBuffer = (ByteArrayOutputStream)dvmObject.getValue();    byte[] compressedData = MemoryBuffer.toByteArray();    return new ByteArray(            vm,            compressedData    );
\```

![图片](https://bbs.kanxue.com/upload/attach/202511/SQN9WE73VFVA6UK.jpg)

\```
case "java/util/zip/GZIPOutputStream->close()V":    GZIPOutputStream GzipCompressiveFlow2 = (GZIPOutputStream)dvmObject.getValue();    try{        GzipCompressiveFlow2.close();    }catch(Exception e){}    return;
\```

补完这个方法过后,成功的出值了.

![图片](https://bbs.kanxue.com/upload/attach/202511/7D2EWFQF2XNATRB.jpg)

![图片](https://bbs.kanxue.com/upload/attach/202511/VEYJXEZQPREF8C3.jpg)

整体下来是这么多.

0x02-补文件访问

接下来是文件访问,这也是unidbg补环境最容易漏掉的问题.

unidbg开启文件访问记录

implements IOResolver<AndroidFileIO>

![图片](https://bbs.kanxue.com/upload/attach/202511/6QCQJ4GFMY8T42Y.jpg)

添加IOResolver

\```
emulator.getSyscallHandler().addIOResolver(this);
\```

实现resolve方法

\```
@Overridepublic FileResult<AndroidFileIO> resolve(Emulator<AndroidFileIO> emulator, String pathname, int oflags) {    System.out.println("file open:"+pathname);    return null;}
\```

运行后会发现访问了5个文件

\```
file open:/dev/__properties__file open:/proc/statfile open:/system/build.propfile open:/proc/versionfile open:/proc/5620/status
\```

笔者分别讲一下这几个文件是啥

\```
/dev/__properties__
\```

这个是一个文件夹,是Android属性系统的设备文件,用于系统属性存储和通信,当应用调用`System.setProperty()/系统服务更新属性/属性服务自动更新时,会发生变化.`

\```
/proc/stat
\```

`这是一个文件,包含CPU和系统统计信息,每次CPU时间片分配时/系统中断发生时/进程创建/销毁时,几乎实时高频变化.`

\```
/system/build.prop
\```

`这是一个文件,包含系统构建时的配置属性,正常情况下不会变化,当系统OTA更新时/刷机时/手动修改时.`

\```
/proc/version
\```

`这是一个文件,显示Linux内核版本,编译时间,编译器版本等信息,仅在内核重新编译或系统更新时变化.`

\```
/proc/5620/status
\```

`这是一个文件,特定进程的详细状态信息,当进程内存使用变化时/进程状态改变时/线程数变化时发生变化.`

`我们可以分别将这几个文件从手机上面pull到本地,直接返回.`

\```
@Overridepublic FileResult<AndroidFileIO> resolve(Emulator<AndroidFileIO> emulator, String pathname, int oflags) {    System.out.println("file open:"+pathname);    String statusPath = String.format("/proc/%d/status", emulator.getPid());    switch (pathname) {        case "/system/build.prop":            return FileResult.<AndroidFileIO>success(                    new SimpleFileIO(                            oflags,                            new File("unidbg-android/src/test/ApkResFile/pdd_files/build.prop"),                            pathname                    )            );        case "/proc/version":            return FileResult.<AndroidFileIO>success(                    new SimpleFileIO(                            oflags,                            new File("unidbg-android/src/test/ApkResFile/pdd_files/version"),                            pathname                    )            );        case "/proc/stat":            return FileResult.<AndroidFileIO>success(                    new SimpleFileIO(                            oflags,                            new File("unidbg-android/src/test/ApkResFile/pdd_files/stat"),                            pathname                    )            );        case "/dev/__properties__":            return null;    }    if(statusPath.equals(pathname)){        return FileResult.<AndroidFileIO>success(                new SimpleFileIO(                        oflags,                        new File("unidbg-android/src/test/ApkResFile/pdd_files/status"),                        pathname                )        );    }    return null;}
\```

`new File位置改成你们本地pull文件的路径.`

`最终的补环境代码笔者也贴出来供大家参考.`

\```
package com.pdd_anti_token;
\```

至此补环境就告一段落了,笔者最后还想提一下一个点,抛砖引玉,为下篇的算法分析做铺垫.

在我们补的这个方法当中,

\```
java/util/zip/GZIPOutputStream->write([B)V
\```

他传入了一个参数,我们打印了出来

![图片](https://bbs.kanxue.com/upload/attach/202511/D9VR9SKN435HF2F.jpg)

![图片](https://bbs.kanxue.com/upload/attach/202511/KQF2SH9UNAYBA3T.jpg)

那么这个数据是什么呢,我们放到cyberchef反hex一下

![图片](https://bbs.kanxue.com/upload/attach/202511/MD7DZRM5WU9WYCZ.jpg)

是这样的,其实这是算法的入参---指纹数据,只不过他做了点自定义的排序,把指纹分组进行排序.

\```
Ljava/io/ByteArrayOutputStream;-><init>()V,Ljava/util/zip/GZIPOutputStream;-><init>(Ljava/io/OutputStream;)V,Ljava/util/zip/GZIPOutputStream;->write([B)V,Ljava/util/zip/GZIPOutputStream;->finish()V,Ljava/io/ByteArrayOutputStream;->toByteArray()[B,Ljava/util/zip/GZIPOutputStream;->close()V
\```

我们刚刚补的这几个方法其实是实现一个gzip压缩算法

\```
import java.io.*;
\```

具体可以看看这个Java实现的gzip示例,与我们补环境的方法一一对应,那么gzip压缩算法肯定有参与到算法运算当中,本篇做一个开端,读者敬请期待下篇的算法分析,提前剧透一下涉及到了两个算法base64和aes,均为标准的.

下期预告:

<如何在OLLVM混淆中探寻算法二>之libpdd_secure.so指纹算法分析(下篇)

---

# 回复

## 回复 by 大萨达 (#2)

*2025-11-27 22:07*

666

## 回复 by huangyalei (#3)

*2025-11-28 00:17*

微信的图片链接都不能显示啊

## 回复 by 红皮西瓜 (#4)

*2025-11-28 09:53*

图片无法正常显示

## 回复 by KanXue_NG (#5)

*2025-11-28 09:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_tcktejwd](https://bbs.kanxue.com/user-1046416.htm)
>
>  图片无法正常显示
>
>

文章是我从我公众号发布后复制来的 图片 代码块格式可能会有问题,可以移步到我的公众号上看
aHR0cHM6Ly9tcC53ZWl4aW4ucXEuY29tL3MvT0NOUkFfVC1Fek1jRHNjUVBCSDJSUQ==

## 回复 by KanXue_NG (#6)

*2025-11-28 09:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  huangyalei](https://bbs.kanxue.com/user-8799.htm)
>
>  微信的图片链接都不能显示啊
>
>

文章是我从我公众号发布后复制来的 图片 代码块格式可能会有问题,可以移步到我的公众号上看
aHR0cHM6Ly9tcC53ZWl4aW4ucXEuY29tL3MvT0NOUkFfVC1Fek1jRHNjUVBCSDJSUQ==

## 回复 by Ms135 (#7)

*2025-11-28 14:09*

666

## 回复 by mb_pnyyaazf (#8)

*2025-11-28 18:00*

666

## 回复 by wx_插曲 (#9)

*2025-11-29 09:15*

666

## 回复 by KanXue_NG (#10)

*2025-11-29 10:47*

>
> [wx_插曲](https://bbs.kanxue.com/user-953711.htm)
>
>  666
>
>
>

灌饼哥 也来给我捧场了呀![image](https://bbs.kanxue.com/view/img/face/020.gif)

## 回复 by 夜惜风雨 (#11)

*2025-12-2 09:55*

6666

## 回复 by guijingwen (#12)

*2025-12-2 10:14*

66

## 回复 by mb_maiyudos (#13)

*2025-12-29 11:33*

666

## 回复 by mb_ssnabqqf (#14)

*2026-1-20 19:44*

11

## 回复 by ouduomi (#15)

*2026-1-21 00:53*

图片无法正常显示

## 回复 by mb_fglogyec (#16)

*2026-2-9 14:23*

6666

## 回复 by myios (#17)

*2026-2-14 19:17*

666

## 回复 by mb_rjyuyjmm (#18)

*2026-2-25 18:09*

大佬，图全裂了

## 回复 by mb_ysikfhxt (#19)

*2026-3-8 14:57*

1

## 回复 by 量凉 (#20)

*2026-3-17 15:21*

666

## 回复 by iBa0 (#21)

*2026-3-24 22:58*

看看

## 回复 by mb_dhqqovwu (#22)

*2026-3-30 21:35*

666

## 回复 by mb_uzmffdbw (#23)

*2026-3-31 17:34*

666

## 回复 by mb_jnmxfjku (#24)

*2026-3-31 17:41*

666

## 回复 by 小迷糊ddd (#25)

*2026-4-7 09:17*

感谢分享，学习一下。

## 回复 by mb_ofkncgmb (#26)

*2026-4-24 13:10*

666

## 回复 by guijian (#27)

*2026-5-11 17:21*

感谢分享，学习一下

## 回复 by 末日大哥 (#28)

*2026-5-12 09:54*

666学习一下

## 回复 by FMNS (#29)

*2026-5-16 21:05*

t'q'l

## 回复 by mb_cxcsoneg (#30)

*2026-5-21 21:13*

感谢分享，学习一下

## 回复 by 4ak5ra (#31)

*2026-5-22 14:20*

666

## 回复 by hanjiefang (#32)

*2026-5-28 15:21*

感谢

## 回复 by wossoneri (#33)

*2026-6-10 21:14*

pdd?

## 回复 by wx_人间有味是清欢 (#34)

*2026-6-25 22:05*

6

## 回复 by mb_agaijsul (#35)

*2026-7-21 17:00*

6666

## 回复 by 温泉划水鱼 (#36)

*2026-7-21 17:13*

66

## 回复 by Thehepta (#37)

1

## 回复 by 学习的小秦 (#38)

感谢分享，学习一下
