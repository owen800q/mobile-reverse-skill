---
title: '[原创]Frida Hook JNI 基本应用'
url: https://bbs.kanxue.com/thread-279826.htm
tid: 279826
author: 复活甲
date: '2023-12-10'
tags: [Android安全, 原创, 基础理论, 逆向分析]
crawled_at: '2026-07-31T14:35:56+08:00'
replies: 1
---

### 一、前言

JNI（Java Native Interface）是 Java 提供的一种机制，用于实现 Java 程序与本地（Native）代码之间的交互。通过 JNI，Java 程序可以调用本地代码，而本地代码也可以调用 Java 程序中的方法。
不管APP应用程序自身的so文件如何混淆，系统的函数都是不变的，通常可以hook一些系统函数来定位关键代码。linker、libc.so、libdl.so、libart.so都有很多被hook的系统函数，其中libart.so中的jni函数在so文件的分析中发挥重要的作用。通过hook JNI函数，可以大体上知道so代码的逻辑。

### 二、JNI 函数的Hook

#### 1.JNIENV 的获取

要hook或者调用这些JNI函数，都需要先获取JNIENV * 指针变量的内存地址。

| 1234567891011121314 | `Java.vm.getEnv()``Java.vm.tryGetEnv()`  `function hook_jni_1(){``Java.perform(function () {``var getEnv` `=` `Java.vm.tryGetEnv();``console.log(JSON.stringify(getEnv));` `/``/``{``"handle"``:``"0xd802bc00"``,``"vm"``:{}}``})``}` `/``/` `JNIEnv 的结构体地址：``getEnv.handle.readPointer()``ptr(getEnv).readPointer()` |
|-|-|

handle属性记录的就是原始的JNIEnv*的指针变量的内存地址。

#### 2.枚举libart符号表来hook

比如：在so文件分析中，我们hook GetStringUTFChars ，打印他的返回值，可以验证我们的猜想。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_SW46P2F8ZB68MZW.webp)

| 12345678910111213141516171819202122232425 | `function hook_jni_2(){``Java.perform(function () {``var symbols` `=` `Process.getModuleByName(``"libart.so"``).enumerateSymbols();``var addr_GetStringUTFChars` `=` `NULL;``for` `(var index` `=` `0``; index < symbols.length; index``+``+``) {``const symbols_one` `=` `symbols[index];``if` `(symbols_one.name.indexOf(``"art"``) >``=` `0``){``if` `(symbols_one.name.indexOf(``"checkJNI"``)` `=``=` `-``1` `&& symbols_one.name.indexOf(``"GetStringUTFChar"``)>``=` `0``){``console.log(``"GetStringUTFChar "``,JSON.stringify(symbols_one));``addr_GetStringUTFChars` `=` `symbols_one.address;``break``}` `}` `}``Interceptor.attach(addr_GetStringUTFChars,{``onEnter:function(args){``var env` `=` `args[``0``];``var param1` `=` `args[``1``];``console.log(``"env :"``,env,``"param1 "``,ptr(param1).readAnsiString);``},onLeave:function (retval) {``console.log(``"addr_GetStringUTFChars retval :"``,ptr(retval).readCString())``}``})``})``}` |
|-|-|

要得到原始的JNIEnv * 指针变量的内存地址，通过hook一些函数，他的第一个参数就是他的地址（var env = args[0];）。

### 三、主动调用so函数

#### 1.主动调用JNI函数

先通过Java.vm.tryGetEnv()获取到frida包装后的JNIEnv对象，接着再调用frida提供的API来调用JNI函数。

| 1234567891011 | `function hook_jni_3(){``Java.perform(function () {``var jstr` `=` `"kanxue and xibei"``;``var env` `=` `Java.vm.getEnv();``var cstr` `=` `env.newStringUtf(jstr);``console.log(``"============================================="``)``var ss` `=` `env.getStringUtfChars(cstr);``console.log(``"---------------------------------------------"``)``console.log(``"ss : "``,hexdump(ss))``});``}` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_Q5FYWFNWUPTGV4H.webp)

#### 2.so层文件打印函数栈

通过hook某些系统函数并打印函数栈是快捷定位关键代码的方法之一。可以通过Thread.backTrace来获取函数栈。

| 12 | `var backInfo` `=` `Thread.backtrace(this.context,Backtracer.ACCURATE);``console.log(backInfo.``map``(DebugSymbol.fromAddress).join(``"\n"``)``+``"\n"``);` |
|-|-|

#### 3.so 层主动调用任意函数

new NativeFunction 创建函数指针，有了这个函数指针，即可再代码中主动调用so函数，传入自定义的实参。

| 1234567891011121314151617181920212223 | `function write_reg_dat2() {` `/``/``把C函数定义为NativeFunction来写文件``var addr_fopen` `=` `Module.findExportByName(``"libc.so"``,` `"fopen"``);``var addr_fputs` `=` `Module.findExportByName(``"libc.so"``,` `"fputs"``);``var addr_fclose` `=` `Module.findExportByName(``"libc.so"``,` `"fclose"``);` `console.log(``"addr_fopen:"``, addr_fopen,` `"addr_fputs:"``, addr_fputs,` `"addr_fclose:"``, addr_fclose);``var fopen` `=` `new NativeFunction(addr_fopen,` `"pointer"``, [``"pointer"``,` `"pointer"``]);``var fputs` `=` `new NativeFunction(addr_fputs,` `"int"``, [``"pointer"``,` `"pointer"``]);``var fclose` `=` `new NativeFunction(addr_fclose,` `"int"``, [``"pointer"``]);` `var filename` `=` `Memory.allocUtf8String(``"/sdcard/reg.dat"``);``var open_mode` `=` `Memory.allocUtf8String(``"w+"``);``var` `file` `=` `fopen(filename, open_mode);``console.log(``"fopen file:"``,` `file``);` `var` `buffer` `=` `Memory.allocUtf8String(``"EoPAoY62@ElRD"``);``var ret` `=` `fputs(``buffer``,` `file``);``console.log(``"fputs ret:"``, ret);` `fclose(``file``);``}` |
|-|-|

#### 4.通过NativeFunction主动调用JNI函数

| 12345678910111213141516171819202122232425262728293031323334353637383940414243 | `function hook_jni_func(){``Java.perform(function(){``var symbols` `=` `Process.getModuleByName(``"libart.so"``).enumerateSymbols();``var NewStringUTF_addr` `=` `NULL;``var GetStringUTFChars_addr` `=` `NULL;` `for` `(var index` `=` `0``; index < symbols.length; index``+``+``) {``const symbol` `=` `symbols[index];``if` `(symbol.name.indexOf(``"CheckJNI"``)``=``=``-``1` `&&  symbol.name.indexOf(``"NewStringUTF"``) >``=``0``){``NewStringUTF_addr` `=` `symbol.address;``}` `if` `(symbol.name.indexOf(``"CheckJNI"``)``=``=``-``1` `&&  symbol.name.indexOf(``"GetStringUTFChars"``) >``=``0``){``GetStringUTFChars_addr` `=` `symbol.address;``}` `}` `console.log(``"NewStringUTF_addr :"``,NewStringUTF_addr,``"GetStringUTFChars_addr :"``,GetStringUTFChars_addr);` `var NewStringUTF` `=` `new NativeFunction(NewStringUTF_addr,``'pointer'``,[``'pointer'``,``'pointer'``])` `var GetStringUTFChars` `=` `new NativeFunction(GetStringUTFChars_addr,``'pointer'``,[``'pointer'``,``'pointer'``,``'pointer'``]);` `var env` `=` `Java.vm.tryGetEnv().handle;``console.log(``"Java.vm.tryGetEnv() "``,JSON.stringify(Java.vm.tryGetEnv()));``var string_eg_addr` `=` `Memory.allocUtf8String(``"xibei"``);``console.log(``"string_ex_addr :"``,string_eg_addr);``var jString` `=` `NewStringUTF(env,string_eg_addr);``console.log(``"jString :"``,jString);` `var cStr` `=` `GetStringUTFChars(env,jString,ptr(``0``));``console.log(``"cStr :"``,cStr.readCString());` `});``}` `打印值：` `NewStringUTF_addr :` `0xeff56c71` `GetStringUTFChars_addr :` `0xeff573e1``Java.vm.tryGetEnv()  {``"handle"``:``"0xea01bb00"``,``"vm"``:{}}``string_ex_addr :` `0xd38e4a80``jString :` `0x1``cStr : xibei` |
|-|-|

### 四、JNI 函数注册的快速定位

#### 1.Hook dlsym获取函数地址

dlsym 函数返回值地址有可能为0。静态注册的native函数首次被调用才会经过dlsym函数，之后不再触发。JNI_OnLoad 不属于静态注册函数，只是系统在so文件加载完毕后，去获取JNI_OnLoad函数地址，使用的也是dlsym。

| 12345678910111213141516171819202122 | `function hook_jni_6(){``Java.perform(function(){``var dlsym_addr` `=` `Module.findExportByName(``"libdl.so"``,``"dlsym"``);``var argsl` `=` `NULL;``Interceptor.attach(dlsym_addr,{``onEnter:function(args){``this.argsl` `=` `args[``1``];``},onLeave:function(retval){``var modeule` `=` `Process.findModuleByAddress(retval);``if` `(modeule` `=``=``null)` `return``;``if` `(this.argsl.readCString().indexOf(``"JNI_OnLoad"``) >``=``0``){``console.log(``"modeule info :"``,modeule.base,modeule.name)``console.log(this.argsl.readCString(),retval)``}``}``});``});``}`  `modeule info :` `0xd638d000` `libmyjni.so``JNI_OnLoad` `0xd638e509` |
|-|-|

#### 2.Hook RegisterNatives 获取函数地址

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344 | `function hook_jni_7(){``Java.perform(function(){``var symbols` `=` `Process.getModuleByName(``"libart.so"``).enumerateSymbols();``var RegisterNatives_addr` `=` `NULL;``for` `(var index` `=` `0``; index < symbols.length; index``+``+``) {``const symbol` `=` `symbols[index];``if` `(symbol.name.indexOf(``"CheckJNI"``)``=``=``-``1` `&&  symbol.name.indexOf(``"RegisterNatives"``) >``=``0``){``RegisterNatives_addr` `=` `symbol.address;``}` `}` `console.log(``"RegisterNatives_addr :"``,RegisterNatives_addr);` `Interceptor.attach(RegisterNatives_addr,{``onEnter:function(args){``var env` `=` `Java.vm.tryGetEnv();``var class_name` `=` `env.getClassName(args[``1``]);``console.log(``"class_name "``,class_name)``var method_count` `=` `args[``3``].toInt32();``for` `(var index` `=` `0``; index < method_count; index``+``+``) {``var method_name` `=` `args[``2``].add(Process.pointerSize``*``3``*``index).readPointer().readCString();``console.log(``"method_name "``,method_name);` `var signature` `=` `args[``2``].add(Process.pointerSize``*``3``*``index).add(Process.pointerSize).readPointer().readCString();``console.log(``"signature "``,signature);` `var fnPtr` `=` `args[``2``].add(Process.pointerSize``*``3``*``index).add(Process.pointerSize``*``2``).readPointer();``console.log(``"fnPtr "``,fnPtr);` `var modeule` `=` `Process.findModuleByAddress(fnPtr);``console.log(``"modeule "``,JSON.stringify(modeule))` `console.log(``" func in IDA addr 32 :"``,fnPtr.sub(modeule.base).sub(``1``))``console.log(``" func in IDA addr 64 :"``,fnPtr.sub(modeule.base))``}` `},onLeave:function(retval){` `}``})` `});``}` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_EQV7FACPET5DGCT.webp)

再来看下IDA里面的代码：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_KPQVSA4ACNNEXKQ.webp)

initSN : 0x13b0
n1 : 000013B0
n1 = initSN 可以快速锁定对应的函数

---

# 回复

## 回复 by 秋狝 (#2)

*2023-12-11 09:39*

感谢分享
