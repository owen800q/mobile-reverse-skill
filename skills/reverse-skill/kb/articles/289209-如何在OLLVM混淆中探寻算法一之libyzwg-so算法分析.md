---
title: '[原创]如何在OLLVM混淆中探寻算法一之libyzwg.so算法分析'
url: https://bbs.kanxue.com/thread-289209.htm
tid: 289209
author: KanXue_NG
date: '2025-11-25'
tags: [Android安全, 原创, 协议分析]
crawled_at: '2026-08-08T10:37:31+00:00'
replies: 30
---

# 0x1-前言:

随着移动安全攻防的激进,裸奔的so出场率越来越少,取而代之的是基于OLLVM框架魔改的混淆的so.标题为了避显,延长文章存活时间,此篇以分析算法为主.文章内容仅供学习,切勿用于违法犯罪.
注:此文是我从vx公众号发布后复制过来的,可能有些图片,代码块会有点显示的问题,请移步我的原文地址:

| 1 | `aHR0cHM6Ly9tcC53ZWl4aW4ucXEuY29tL3MvQUJaNkxxc19wMDZIcnRoR2gxMWxIZw``=``=` |
|-|-|

也欢迎各位师傅关注我的公众号,不定期分享算法还原文章.

# 0x2-样本信息:

## 直达地址:

| 1 | `aHR0cHM6Ly93d3cud2FuZG91amlhLmNvbS9hcHBzLzYyMDIyMjIvaGlzdG9yeV92MTMxNDExMA``=``=` |
|-|-|

## 版本信息:

| 1 | `v13.``141` |
|-|-|

# 0x3-抓包分析:

 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1003959_KK4Y49V8AAVDW5A.webp)
读者不难发现,部分的接口的表单中以及响应数据都做了对应的反爬操作,表单中对请求参数做了加密以及签名,响应数据也做了加密处理.

# 0x4-加密参数初步分析:

## sig:

多次抓包发现,"V3.0"是一个固定的前缀,猜测是算法版本,后面拼接32位的16进制.

## sp:

从密文中分析不出有用的线索.

## 响应数据加密:

从密文中分析不出有用的线索.

# 0x5-定位入口:

跑一遍算法自吐,发现并没有实质的线索,那么加密逻辑可能在native层实现.
笔者通过hook NewStringUTF来快速定位,当然也可以选择反编译apk做关键字的检索,或者hook hashmap这种常见的数据类型,定位的方法很多,这里不做过多的赘述了.

| 12345678910111213141516171819202122232425262728293031 | `function hook_newStr() {``var symbols` `=` `Module.enumerateSymbolsSync(``"libart.so"``);``var addrNewStringUTF` `=` `null;``for` `(var i` `=` `0``; i < symbols.length; i``+``+``) {``var symbol` `=` `symbols[i];``if` `(symbol.name.indexOf(``"NewStringUTF"``) >``=` `0` `&& symbol.name.indexOf(``"CheckJNI"``) <` `0``) {``addrNewStringUTF` `=` `symbol.address;``}``}``if` `(addrNewStringUTF !``=` `null) {``Interceptor.attach(addrNewStringUTF, {``onEnter: function (args) {``var c_string` `=` `args[``1``];``var dataString` `=` `c_string.readCString();``/``/``筛选结果``if` `(dataString.includes(``"V3.0"``)) {``console.log(dataString);``/``/``打印堆栈``console.log(Thread.backtrace(this.context, Backtracer.ACCURATE).``map``(DebugSymbol.fromAddress).join(``'\n'``)` `+` `'\n'``);``console.log(Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Throwable"``).$new()));``}``if` `(dataString.includes(``"zwp"``)) {``console.log(dataString);``/``/``打印堆栈``console.log(Thread.backtrace(this.context, Backtracer.ACCURATE).``map``(DebugSymbol.fromAddress).join(``'\n'``)` `+` `'\n'``);``console.log(Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Throwable"``).$new()));``}``}``});``}``}` |
|-|-|

相信看了我之前写的文章的读者们,定位这一步应该不成问题,笔者这里就不带着去定位了,把文章的篇幅留给算法分析这一块,笔者贴一下对应的native方法信息.

sig

sp

响应解密

类

com.twl.signer.YZWG

com.twl.signer.YZWG

com.twl.signer.YZWG

native方法

private static native byte[] nativeSignature(byte[] bArr, String str);

private static native String nativeEncodeRequest(byte[] bArr, String str);

private static native nativeDecodeContent([BLjava/lang/String;III)[B

在yzwg.so偏移

0x21864

0x209a4

0x24dc8

参数解释

bArr是表单参数进行url编码结果,str是null

bArr是表单参数进行url编码结果,str是null

参数1为加密的响应数据字节数组,参数二为null,参数三-五为0,1,0

# 0x6-Unidbg搭架子与补环境:

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344 | `package com.bosszp;` `import` `com.github.unidbg.AndroidEmulator;``import` `com.github.unidbg.Module;``import` `com.github.unidbg.linux.android.AndroidEmulatorBuilder;``import` `com.github.unidbg.linux.android.AndroidResolver;``import` `com.github.unidbg.linux.android.dvm.``*``;``import` `com.github.unidbg.linux.android.dvm.array.ArrayObject;``import` `com.github.unidbg.memory.Memory;``import` `java.io.``*``;``import` `java.nio.charset.StandardCharsets;` `public` `class` `Boss_Signer extends AbstractJni{``private final AndroidEmulator emulator;``private final VM vm;``private final Module module;``private final DvmClass YZWG;` `/``/``初始化虚拟机``public Boss_Signer() {``/``/``创建模拟器实例 (ARM64架构)``emulator` `=` `AndroidEmulatorBuilder.for64Bit()``.setProcessName(``"com.xunmeng.pinduoduo"``)``.build();``/``/``获取内存接口``final Memory memory` `=` `emulator.getMemory();``memory.setLibraryResolver(new AndroidResolver(``23``));` `/``/` `Android` `6.0``/``/``创建Android虚拟机``vm` `=` `emulator.createDalvikVM(new` `File``(``"unidbg-android/src/test/resources/apks/BOSS直聘_v13.141.apk"``));` `/``/` `替换为实际APK路径``/``/``设置JNI接口``vm.setJni(this);``vm.setVerbose(true);` `/``/` `打印详细日志``/``/``加载目标SO库``DalvikModule dm` `=` `vm.loadLibrary(new` `File``(``"unidbg-android/src/test/resources/example_binaries/arm64-v8a/libyzwg.so"``), true);` `/``/` `替换为实际SO路径``dm.callJNI_OnLoad(emulator);` `/``/` `调用SO初始化函数``module` `=` `dm.getModule();``/``/``获取目标类``YZWG` `=` `vm.resolveClass(``"com/twl/signer/YZWG"``);``}``/``/``入口``public static void main(String[] args) {``Boss_Signer signer` `=` `new Boss_Signer();``}``}` |
|-|-|

运行一下,发现没有那么幸运,这回需要补一下环境才能正常运行.
图片
鼠标点击AbstractJni.java:103蓝色字体进入AbstractJni文件内.
图片
将鼠标对应位置的这一块方法给扣到我们自己写的架子中.
图片
然后做一点小小的改造.
图片
需要注意,我们自己写的类需要继承自AbstractJni.不然无法重写getStaticObjectField.
图片
对于此方法签名,他需要返回这种类型的静态字段Landroid/content/Context;
com/twl/signer/YZWG->gContext:Landroid/content/Context;
我们就给他返回一个这个类型的.
@Override
public DvmObject getStaticObjectField(BaseVM vm, DvmClass dvmClass, String signature) {
 switch (signature) {
 case "com/twl/signer/YZWG->gContext:Landroid/content/Context;":
 return vm.resolveClass("android/content/Context").newObject(null);
 }
 return super.getStaticObjectField(vm,dvmClass,signature);
}
接着运行,又报错
图片
此方法是根据UID（用户ID）获取对应的应用程序包名数组.
可以这样补
@Override
public DvmObject callObjectMethod(BaseVM vm, DvmObject dvmObject, String signature,VarArg varArg) {
 System.out.println("[callObjectMethod call]:::::signature=====>"+signature);
 switch (signature) {
 case "android/content/pm/PackageManager->getPackagesForUid(I)[Ljava/lang/String;":
 int uid = varArg.getIntArg(0);
 //System.err.println("uid:"+uid);
 return new ArrayObject(new StringObject(vm, vm.getPackageName()));
 }
 return super.callObjectMethod(vm,dvmObject,signature,varArg);
}
接着继续运行,又报错了
图片
这个可以这样补
@Override
public int callIntMethod(BaseVM vm, DvmObject dvmObject, String signature, VarArg varArg) {
 switch (signature) {
 case "java/lang/String->hashCode()I":
 System.out.println("java/lang/String->hashCode()I enter");
 String str = dvmObject.getValue().toString();
 return str.hashCode();
 }
 return super.callIntMethod(vm,dvmObject,signature,varArg);
}
补完发现没有别的报错了,接下来我们调用下目标方法.
图片
//主动调用方法
//sp
public String nativeEncodeRequest(byte[] bArr, String str){
 //调用静态native方法
 DvmObject<?> result = YZWG.callStaticJniMethodObject(
 emulator,
 "nativeEncodeRequest([BLjava/lang/String;)Ljava/lang/String;",
 bArr,
 str
 );
 //获取并返回结果
 return (String) result.getValue();
}

//sig
public byte[] nativeSignature(byte[] bArr, String str){
 //调用静态native方法
 DvmObject<?> result = YZWG.callStaticJniMethodObject(
 emulator,
 "nativeSignature([BLjava/lang/String;)[B",
 bArr,
 str
 );
 //获取并返回结果
 return (byte[]) result.getValue();
}

//decode content
public byte[] nativeDecodeContent(byte[] bArr, String str, int i11, int i12, int i13){
 //调用静态native方法
 DvmObject<?> result = YZWG.callStaticJniMethodObject(
 emulator,
 "nativeDecodeContent([BLjava/lang/String;III)[B",
 bArr,
 str,
 i11,
 i12,
 i13
 );
 //获取并返回结果
 return (byte[]) result.getValue();
}
unidbg结果需要和真机对比,看看是否一致.
完整unidbg代码如下
package com.bosszp;

import com.github.unidbg.AndroidEmulator;
import com.github.unidbg.Module;
import com.github.unidbg.linux.android.AndroidEmulatorBuilder;
import com.github.unidbg.linux.android.AndroidResolver;
import com.github.unidbg.linux.android.dvm.*;
import com.github.unidbg.linux.android.dvm.api.SystemService;
import com.github.unidbg.linux.android.dvm.array.ArrayObject;
import com.github.unidbg.memory.Memory;
import java.io.*;
import java.nio.charset.StandardCharsets;

public class Boss_Signer extends AbstractJni{

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122 | `private final AndroidEmulator emulator;``private final VM vm;``private final Module module;``private final DvmClass YZWG;` `/``/``初始化虚拟机``public Boss_Signer() {``/``/``创建模拟器实例 (ARM64架构)``emulator` `=` `AndroidEmulatorBuilder.for64Bit()``.setProcessName(``"com.xunmeng.pinduoduo"``)``.build();``/``/``获取内存接口``final Memory memory` `=` `emulator.getMemory();``memory.setLibraryResolver(new AndroidResolver(``23``));` `/``/` `Android` `6.0``/``/``创建Android虚拟机``vm` `=` `emulator.createDalvikVM(new` `File``(``"unidbg-android/src/test/resources/apks/BOSS直聘_v13.141.apk"``));` `/``/``替换为实际APK路径``/``/``设置JNI接口``vm.setJni(this);``vm.setVerbose(true);` `/``/` `打印详细日志``/``/``加载目标SO库``DalvikModule dm` `=` `vm.loadLibrary(new` `File``(``"unidbg-android/src/test/resources/example_binaries/arm64-v8a/libyzwg.so"``), true);` `/``/` `替换为实际SO路径``dm.callJNI_OnLoad(emulator);` `/``/` `调用SO初始化函数``module` `=` `dm.getModule();``/``/``获取目标类``YZWG` `=` `vm.resolveClass(``"com/twl/signer/YZWG"``);``}` `/``/``主动调用方法``/``/``sp``public String nativeEncodeRequest(byte[] bArr, String` `str``){``/``/``调用静态native方法``DvmObject<?> result` `=` `YZWG.callStaticJniMethodObject(``emulator,``"nativeEncodeRequest([BLjava/lang/String;)Ljava/lang/String;"``,``bArr,``str``);``/``/``获取并返回结果``return` `(String) result.getValue();``}` `/``/``sig``public byte[] nativeSignature(byte[] bArr, String` `str``){``/``/``调用静态native方法``DvmObject<?> result` `=` `YZWG.callStaticJniMethodObject(``emulator,``"nativeSignature([BLjava/lang/String;)[B"``,``bArr,``str``);``/``/``获取并返回结果``return` `(byte[]) result.getValue();``}` `/``/``decode content``public byte[] nativeDecodeContent(byte[] bArr, String` `str``,` `int` `i11,` `int` `i12,` `int` `i13){``/``/``调用静态native方法``DvmObject<?> result` `=` `YZWG.callStaticJniMethodObject(``emulator,``"nativeDecodeContent([BLjava/lang/String;III)[B"``,``bArr,``str``,``i11,``i12,``i13``);``/``/``获取并返回结果``return` `(byte[]) result.getValue();``}` `/``/``补环境部分``@Override``public DvmObject<?> getStaticObjectField(BaseVM vm, DvmClass dvmClass, String signature) {``System.out.println(``"[getStaticObjectField call]::::::signature======>"``+``signature);``switch (signature) {``case` `"com/twl/signer/YZWG->gContext:Landroid/content/Context;"``:``return` `vm.resolveClass(``"android/content/Context"``).newObject(null);``}``return` `super``.getStaticObjectField(vm,dvmClass,signature);``}` `@Override``public DvmObject<?> callObjectMethod(BaseVM vm, DvmObject<?> dvmObject, String signature,VarArg varArg) {``System.out.println(``"[callObjectMethod call]:::::signature=====>"``+``signature);``switch (signature) {``case` `"android/content/pm/PackageManager->getPackagesForUid(I)[Ljava/lang/String;"``:``int` `uid` `=` `varArg.getIntArg(``0``);``/``/``System.err.println(``"uid:"``+``uid);``return` `new ArrayObject(new StringObject(vm, vm.getPackageName()));``}``return` `super``.callObjectMethod(vm,dvmObject,signature,varArg);``}` `@Override``public` `int` `callIntMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {``switch (signature) {``case` `"java/lang/String->hashCode()I"``:``System.out.println(``"java/lang/String->hashCode()I enter"``);``String` `str` `=` `dvmObject.getValue().toString();``return` `str``.hashCode();``}``return` `super``.callIntMethod(vm,dvmObject,signature,varArg);``}`  `public static void main(String[] args) {``Boss_Signer signer` `=` `new Boss_Signer();` `String sp` `=` `signer.nativeEncodeRequest(``"account=vGMZRH2Mc2yGuEY%3D&client_info=%7B%22version%22%3A%2210%22%2C%22os%22%3A%22Android%22%2C%22start_time%22%3A%221756205896294%22%2C%22resume_time%22%3A%221756205896294%22%2C%22channel%22%3A%2228%22%2C%22model%22%3A%22google%7C%7CPixel+3%22%2C%22dzt%22%3A0%2C%22loc_per%22%3A0%2C%22uniqid%22%3A%223e818bd6-0d55-45de-8aca-44216661d569%22%2C%22oaid%22%3A%225752bf62-1e11-4a54-979a-c2786373ab6c%22%2C%22oaid_honor%22%3A%225752bf62-1e11-4a54-979a-c2786373ab6c%22%2C%22did%22%3A%22DUuJwkteNiOzCkxbSM3SoAheX_4j-JxcaP7dRFV1SndrdGVOaU96Q2t4YlNNM1NvQWhlWF80ai1KeGNhUDdkc2h1%22%2C%22tinker_id%22%3A%22Prod-arm64-v8a-release-13.141.1314110_0812-10-06-09%22%2C%22is_bg_req%22%3A0%2C%22network%22%3A%22wifi%22%2C%22operator%22%3A%22UNKNOWN%22%2C%22abi%22%3A1%7D&curidentity=0&identityType=-1&isWxLogin=false&phoneCode=2598&regionCode=%2B86&req_time=1756207770991&uniqid=3e818bd6-0d55-45de-8aca-44216661d569&v=13.141"``.getBytes(),null);``byte[] sig` `=` `signer.nativeSignature(``"/api/zppassport/user/codeLoginaccount=vGMZRH2Mc2yGuEY%3D&client_info=%7B%22version%22%3A%2210%22%2C%22os%22%3A%22Android%22%2C%22start_time%22%3A%221756205896294%22%2C%22resume_time%22%3A%221756205896294%22%2C%22channel%22%3A%2228%22%2C%22model%22%3A%22google%7C%7CPixel+3%22%2C%22dzt%22%3A0%2C%22loc_per%22%3A0%2C%22uniqid%22%3A%223e818bd6-0d55-45de-8aca-44216661d569%22%2C%22oaid%22%3A%225752bf62-1e11-4a54-979a-c2786373ab6c%22%2C%22oaid_honor%22%3A%225752bf62-1e11-4a54-979a-c2786373ab6c%22%2C%22did%22%3A%22DUuJwkteNiOzCkxbSM3SoAheX_4j-JxcaP7dRFV1SndrdGVOaU96Q2t4YlNNM1NvQWhlWF80ai1KeGNhUDdkc2h1%22%2C%22tinker_id%22%3A%22Prod-arm64-v8a-release-13.141.1314110_0812-10-06-09%22%2C%22is_bg_req%22%3A0%2C%22network%22%3A%22wifi%22%2C%22operator%22%3A%22UNKNOWN%22%2C%22abi%22%3A1%7D&curidentity=0&identityType=-1&isWxLogin=false&phoneCode=2369&regionCode=%2B86&req_time=1756207335188&uniqid=3e818bd6-0d55-45de-8aca-44216661d569&v=13.141"``.getBytes(),null);``byte[] decode_content` `=` `signer.nativeDecodeContent(``new byte[]{``-``10``,` `114``,` `76``,` `25``,` `44``,` `-``37``,` `100``,` `101``,` `-``128``,` `-``89``,` `82``,` `-``77``,` `-``46``,` `-``79``,` `-``105``,` `125``,` `-``105``,` `-``32``,` `-``97``,` `119``,` `58``,` `83``,` `-``13``,` `-``111``,` `-``30``,` `-``102``,` `-``103``,` `-``4``,` `-``64``,` `116``,` `71``,` `21``,` `-``99``,` `2``,` `-``95``,` `113``,` `-``79``,` `114``,` `8``,` `37``,` `105``,` `120``},``null,``0``,``1``,``0``);` `System.out.println(``"sig======>"``+``new String(sig, StandardCharsets.UTF_8));``System.out.println(``"sp======>"``+``sp);``System.out.println(``"decode_content======>"``+``new String(decode_content));``}` |
|-|-|

}

图片
对比真机
图片
结果一致,没有问题,响应解密出来也正常,不是乱码之类的东西.
0x7-Ida静态分析+Unidbg下断点还原算法:
0x01-sig(加盐md5算法):
由于nativeSignature方法返回值是字节数组,可以以JNIEnv->SetByteArrayRegion为切入点,ida按g跳转此偏移f5看看上下文.
图片
通过分析可得,v28是v27的长度,而v29是v27,那么研究对象就是这个v27是怎么来的,他是通过一个sub_1C38C方法调用所返回的,我们可以在这个下断点在这个方法.
图片
void sigDebug(){
 emulator.attach().addBreakPoint(module,0x1C38C);
}
图片
可以写出方法的形式方便管理.
这里ida识别的有点问题,应该是两个参数的,ida识别成了一个,鼠标放在这个位置,按一下f5,ida即可重写识别.
图片
运行我们搭好的架子,成功断下
mx0查看寄存器值,也就是我们第一个参数
图片
第二个参数是一个数值,是mx0这个值的长度,不是地址,不能通过mx1这样查看,不然会报错.
图片
通过这样的命令即可查看第一个参数完整的值了
mx0 0x3c9
拿到cyberchef里面from hexdump一下
可以发现前面是我们传入的签名数据,后面的32位不知道是啥
图片
a308f3628b3f39f7d35cdebeb6920e21
我们之前也有做过猜想,sig的值有可能是md5加密某个数据,这里我们也来验证一下.
图片
图片
发现是能够对的上的,现在我们未知的是这个32位的数据是从哪来的,是固定的还是动态的呢?我们通过改变签名数据发现,这个值不会变化,而且代入到我们真机hook的数据中也能签名一致,那么我们姑且相信他是固定的,读者也可以自行研究研究.
sig的算法是"V3.0"的前缀拼接md5加密urlpath+请求参数,至此sig算法分析结束.
0x02-sp(标准base64+标准rc4+魔改lz4压缩):
sp是调用的nativeEncodeRequest方法生成结果,返回值是字符串,调用NewStringUTF转换java和c层数据,这个可以是我们的切入点,上篇文章也有讲过,这篇我们换一个思路.
图片
通过搜索base64编码表来定位,
打开Strings这一栏
图片
搜索一下base64的码表
图片
发现确实有,点击跳转过去,鼠标放在上面按x查找交叉引用
图片
引用的位置都指向sub_29E90这个函数,f5反编译看看
图片
发现代码中有很多if-else,cfg流程图中块与块之间的联系变的很复杂,静态分析很难看出来块与块之间的联系,像这种是做了ollvm的混淆处理的,抗ida的静态分析,既然他用到了base64编码表,那么这个函数有没有可能是实现base64编码逻辑的呢?
我们可以在此函数下个断点看看,如果断住了,是不是就说明sp参数有用到这个算法呢?
emulator.attach().addBreakPoint(module,0x29E90);
sub_29E90(_BYTE *a1, __int64 a2, int a3)
这个函数有三个参数,我们看看分别是什么
图片
x0,x1是内存地址,而x2是x1这块内存地址的占用大小.
通过命令查看发现,这块内存地址什么都没有,这其实是个内存缓冲区,函数离开后会将结果写入到此处
mx0
图片
mx1 0x2b1
图片
x1这块内存地址看着不像我们的明文,对其进行标准base64编码看看与加密结果一致不一致.
图片
图片
对比之后,眼光好一点的读者,可以发现,base64码表做了一点小的改动,
/ ---> _

- --->-
= ---> ~
我们也可以通过cyberchef将码表改成下面这个
A-Za-z0-9-_~
图片
copy一下搜索发现确实是标准的只不过改了下码表
图片
那么我们现在的研究对象是这个编码的密文是哪来的,
鼠标放在这个函数上面,按住x查找交叉引用
图片
发现有多个引用位置,换一个方法,可以通过unidbg打印调用堆栈,这个比较快一些.
还是在我们刚刚的断点处,输入下面命令,即可打印调用堆栈
bt

图片
[0x040000000][0x040020ff4][libyzwg.so][0x020ff4]
ida跳转到这个偏移位置
0x020ff4
图片
第二个参数是我们需要研究的对象,也就是这个ptr,他来自于sub_2E91C这个函数,ptr应该是内存的缓冲区,通过这个函数执行后写入数据到这块内存的.
图片
对sub_2E91C下断点看看
emulator.attach().addBreakPoint(module,0x2E91C);
图片
sub_2E91C函数伪C代码
图片
第一个参数
图片

第二个参数
图片
第三个跟第二个相同,第四个是数据长度.
第二个参数看起来有点像我们的明文,但是不完全是.
通过分析sub_2E91C函数的伪C代码,我们发现这是一个rc4算法.
图片
这个函数是rc4主要的加密/解密函数,但是还有s盒的初始化算法,在他的上一个函数.
图片
v62就是对应的s盒.
s对应的是key.
v53是key的长度.
图片
下个断点看看key是什么.
emulator.attach().addBreakPoint(module,0x2E680);

图片
图片
发现其实是我们之前分析的sig的盐值.
拿到网站上面测试一下,看看是否是标准的,验证我们的猜想.
图片
图片
确实就是标准的,现在离成功又近了一步.
我们的研究对象现在是这个跟明文很像的东西是个啥.
通过查找交叉引用
图片
发现来自上面那个函数.
图片

那就下个断点看看情况.
emulator.attach().addBreakPoint(module,0x1D444);
图片
第一个参数是我们的明文数据,第三个是明文数据的长度
图片
第二个是一个内存的缓冲区
图片
sub_1D444函数伪C代码

图片
根据频繁出现的lz4字眼,猜测可能跟这个压缩算法有关.
通过互联网搜索LZ4_compress_limitedOutput关键字,发现了一个与lz4相关的开源项目.
图片
https://github.com/lz4/lz4
也许这个样本使用了开源的框架.但是他的压缩结果显然不符合标准的lz4.
图片
图片
仔细分析伪C的这部分
图片
发现他多分配了24个字节
sub_1D444函数内部

图片
也有对这24字节的写入相关的代码.

或许就改动了压缩的头部魔数.

python实现lz4压缩

import lz4.frame
import lz4.block
def lz4_compress_fast_extstate_python(data, acceleration=1):
 # 使用帧压缩（推荐，包含完整的帧头信息）
 compressed = lz4.frame.compress(
 data,
 compression_level=acceleration, # 1=最快，9=最高压缩率
 block_linked=True, # 使用链式块
 content_checksum=False, # 校验和
 block_checksum=False
 )
 return compressed
def lz4_decompress_python(compressed_data):
 """解压函数"""
 return lz4.frame.decompress(compressed_data)

# 测试

if **name** == "**main**":
 test_data = b"account=vGMZRH2Mc2yGuEY%3D&client_info=%7B%22version%22%3A%2210%22%2C%22os%22%3A%22Android%22%2C%22start_time%22%3A%221756205896294%22%2C%22resume_time%22%3A%221756205896294%22%2C%22channel%22%3A%2228%22%2C%22model%22%3A%22google%7C%7CPixel+3%22%2C%22dzt%22%3A0%2C%22loc_per%22%3A0%2C%22uniqid%22%3A%223e818bd6-0d55-45de-8aca-44216661d569%22%2C%22oaid%22%3A%225752bf62-1e11-4a54-979a-c2786373ab6c%22%2C%22oaid_honor%22%3A%225752bf62-1e11-4a54-979a-c2786373ab6c%22%2C%22did%22%3A%22DUuJwkteNiOzCkxbSM3SoAheX_4j-JxcaP7dRFV1SndrdGVOaU96Q2t4YlNNM1NvQWhlWF80ai1KeGNhUDdkc2h1%22%2C%22tinker_id%22%3A%22Prod-arm64-v8a-release-13.141.1314110_0812-10-06-09%22%2C%22is_bg_req%22%3A0%2C%22network%22%3A%22wifi%22%2C%22operator%22%3A%22UNKNOWN%22%2C%22abi%22%3A1%7D&curidentity=0&identityType=-1&isWxLogin=false&phoneCode=2598&regionCode=%2B86&req_time=1756207770991&uniqid=3e818bd6-0d55-45de-8aca-44216661d569&v=13.141"
 # 压缩
 compressed = lz4_compress_fast_extstate_python(test_data, acceleration=1)
 print(compressed.hex())
我们可以用python压缩数据得到一份和unidbg的做个对比.

通过两组数据对比,不难发现,这个样本魔改的lz4算法的魔改点是头部的魔数,也就是那24字节,主要的压缩逻辑没有做魔改.

通过对伪C的分析,我们确定了这24个字节的来源

1-8字节: 42 5a 50 42 6c 6f 63 6b 固定 (8字节)
9-16字节:00000000 (固定 4字节) + lz4算法压缩长度(不包含头和尾巴00)(4字节)
17-24字节:数据长度(4字节) + (数据长度 ^ lz4算法计算的结果)(4字节)
这个v9是压缩后的长度,通过python压缩的结果长度,去掉标准的头以及后面填充的00之后的长度就是压缩后的长度.

图片
至此sp算法分析结束.

0x03-响应数据的解密算法(rc4)

貌似无法根据已有的线索去推断,直接trace(踹死)一份汇编执行流.

//trace工具
void traceCode() {
 String traceFile = "unidbg-android/src/test/java/com/bosszp/sp_traceCode.log";// 输出的路径
 PrintStream traceStream = null;// 打印流
 try {
 traceStream = new PrintStream(new FileOutputStream(traceFile), true);
 } catch (FileNotFoundException e) {
 throw new RuntimeException(e);
 }
 // traceCode 对代码进行监控
 emulator.traceCode(module.base, module.base + module.size).setRedirect(traceStream);
}
在执行之前进行trace

图片
将trace的日志丢到010editor里面分析.

nativeDecodeContent最终返回的是byte[]类型我们把它转成了字符串,这里我们需要再把字符串转成hex在010editor里面进行检索.
图片
00000000 7b 22 63 6f 64 65 22 3a 30 2c 22 6d 65 73 73 61 |{"code":0,"messa|
00000010 67 65 22 3a 22 53 75 63 63 65 73 73 22 2c 22 7a |ge":"Success","z|
00000020 70 44 61 74 61 22 3a 7b 7d 7d |pData":{}}|
根据现有的信息,我们总结一下

因:
[-10, 114, 76, 25, 44, -37, 100, 101, -128, -89, 82, -77, -46, -79, -105, 125, -105, -32, -97, 119, 58, 83, -13, -111, -30, -102, -103, -4, -64, 116, 71, 21, -99, 2, -95, 113, -79, 114, 8, 37, 105, 120]
转16进制:
F6 72 4C 19 2C DB 64 65 80 A7 52 B3 D2 B1 97 7D 97 E0 9F 77 3A 53 F3 91 E2 9A 99 FC C0 74 47 15 9D 02 A1 71 B1 72 08 25 69 78

果:
[123, 34, 99, 111, 100, 101, 34, 58, 48, 44, 34, 109, 101, 115, 115, 97, 103, 101, 34, 58, 34, 83, 117, 99, 99, 101, 115, 115, 34, 44, 34, 122, 112, 68, 97, 116, 97, 34, 58, 123, 125, 125]
转16进制:
7b 22 63 6f 64 65 22 3a 30 2c 22 6d 65 73 73 61 67 65 22 3a 22 53 75 63 63 65 73 73 22 2c 22 7a 70 44 61 74 61 22 3a 7b 7d 7d

在汇编执行流中按单个字节搜索,然后定位由果溯因,数据溯源.

搜索的结果有156个

图片
定位的话,要花点时间,一个一个分析下断点,笔者定位到的最终位置是第151个

[12:44:45 923][libyzwg.so 0x02e9bc] [4d682f38] 0x4002e9bc: "strb w13, [x2, x15]" w13=0x7b x2=0x403d4000 x15=0x0 => w13=0x7b
010editor里面搜索这个偏移

0x02e9bc
图片
与结果是对的上的,那就是这个位置了,ida跳转到此处看看上下文.

图片
可以发现是我们刚刚分析过的rc4,用原来的key解密一下看看能否得到结果

a308f3628b3f39f7d35cdebeb6920e21
图片
图片
发现能够正常的解密

至此libyzwg.so的算法就分析完了.

这里额外提几个点,经过我的测试,新版本的算法差别不大,几乎没有改变.

新版本把64位的so换成了32位,算法没变,key也没变,同一个数据,修改apk路径和so路径的两个unidbg得到的结果一致.

图片
另外就是响应解密那个部分,有些接口,返回的数据过大会进行lz4压缩在rc4加密,lz4算法跟前面分析的差不多,知道压缩就能逆推解压的算法.

0x8-结语:

感谢各位读者的收听,如文章有分析不妥或错误的地方,欢迎各位师傅斧正,笔者本着是想一口气写完三个样本的分析,但是考虑到篇幅可能过长,所以循序渐进的来讲解案例,逐帧学习.

下期精彩:

libpdd_secure.so算法分析

libjdgs.so算法分析

---

# 回复

## 回复 by mb_asiwnxyv (#2)

*2025-11-25 21:47*

谢谢分享，不过图片好像没上传去

## 回复 by 29o (#3)

*2025-11-25 22:10*

感谢分享

## 回复 by KanXue_NG (#4)

*2025-11-25 22:12*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_asiwnxyv](https://bbs.kanxue.com/user-963863.htm)
>
>  谢谢分享，不过图片好像没上传去
>
>

我是复制的我公众号发布的文章到看雪的,图片和代码块啥的会丢失
原文可以看我公众号发的
aHR0cHM6Ly9tcC53ZWl4aW4ucXEuY29tL3MvQUJaNkxxc19wMDZIcnRoR2gxMWxIZw==
base64解码

## 回复 by LQ6H (#5)

*2025-11-26 10:49*

666

## 回复 by mb_ykavguun (#6)

*2025-11-26 13:07*

1

## 回复 by 九黎 (#7)

*2025-11-26 17:23*

tql

## 回复 by mb_cbgtaveo (#8)

*2025-11-27 10:15*

666666666

## 回复 by Imxz (#9)

*2025-11-27 11:27*

tql

## 回复 by 机车王子 (#10)

*2025-11-27 14:22*

你的帖子非常有用，感谢分享！

## 回复 by wx_插曲 (#11)

*2025-11-27 15:35*

大佬牛逼

## 回复 by XCicada (#12)

*2025-11-27 18:15*

感谢分享

## 回复 by mb_xjdhrmck (#13)

*2025-11-27 23:27*

666

## 回复 by 红皮西瓜 (#14)

*2025-11-28 09:56*

666

## 回复 by Ms135 (#15)

*2025-11-28 16:35*

666

## 回复 by dsr000 (#16)

*2025-11-28 17:40*

666

## 回复 by cpannn (#17)

*2025-11-29 08:55*

666

## 回复 by Freax (#18)

*2025-12-13 13:14*

666

## 回复 by wx_huhu_859 (#19)

*2025-12-15 02:17*

```1

## 回复 by xianhuimin (#20)

*2025-12-22 20:19*

感谢分享。

## 回复 by mb_lhhcvvel (#21)

*2025-12-26 20:10*

666666666

## 回复 by 不具名的悲伤 (#22)

*2026-1-12 11:08*

6

## 回复 by myios (#23)

*2026-2-21 22:10*

666

## 回复 by mb_ysikfhxt (#24)

*2026-3-3 10:32*

1

## 回复 by mb_vywouypi (#25)

*2026-3-30 02:00*

1

## 回复 by mb_uzmffdbw (#26)

*2026-3-31 17:36*

666

## 回复 by lamboo (#27)

*2026-5-15 18:11*

666666666

## 回复 by wx_岁月真好_475628 (#28)

*2026-5-19 17:25*

6666

## 回复 by mb_agaijsul (#29)

*2026-7-21 16:58*

66666

## 回复 by 温泉划水鱼 (#30)

*2026-7-21 17:12*

66

## 回复 by buluo533 (#31)

*2026-7-24 10:23*

学习了
