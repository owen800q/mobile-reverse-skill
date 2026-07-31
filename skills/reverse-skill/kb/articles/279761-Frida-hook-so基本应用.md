---
title: '[分享]Frida hook so基本应用'
url: https://bbs.kanxue.com/thread-279761.htm
tid: 279761
author: 复活甲
date: '2023-12-04'
tags: [Android安全, 分享, 基础理论, HOOK注入]
crawled_at: '2026-07-31T14:36:18+08:00'
replies: 6
---

### 一、前言

整理了下frida关于so的一些基本应用常用的方法。因为大多数人应该和我一样，都是逆向界的小白，还有就是做爬虫的，平时逆向的也不多，时间久了，很多知识就忘记了，所以归纳总结了下，用到的时候，简单看下。

### 二、获取module的基本信息

#### enumerateModules

通过枚举的方式来获取模块列表，再通过筛选的方式，来大概定位我们需要的模块信息。这里通过包名的过滤，从几百个module里面找到了2条，其中一条就是我们需要的。

| 1234567891011121314 | `function hook_module1() {``Java.perform(function () {``var module_list` `=` `Process.enumerateModules();``for` `(var index` `=` `0``; index < module_list.length; index``+``+``) {``var module_one` `=` `module_list[index];``if` `(module_one.path.indexOf(``"com.gdufs.xman"``) !``=` `-``1``) {``console.log(``"module_one "``, JSON.stringify(module_one))``}``}``})``}` `module_one  {``"name"``:``"base.odex"``,``"base"``:``"0xde48c000"``,``"size"``:``2760704``,``"path"``:``"/data/app/com.gdufs.xman-ezNKFeRbVjUuHuaB1LWSdQ==/oat/arm/base.odex"``}``module_one  {``"name"``:``"libmyjni.so"``,``"base"``:``"0xde359000"``,``"size"``:``24576``,``"path"``:``"/data/app/com.gdufs.xman-ezNKFeRbVjUuHuaB1LWSdQ==/lib/arm/libmyjni.so"``}` |
|-|-|

#### getModuleByName 通过模块名来获取module

| 123456789 | `function hook_module2() {``Java.perform(function () {``var module_data` `=` `Process.getModuleByName(``"libmyjni.so"``);``console.log(JSON.stringify(module_data));``var module_base` `=` `module_data.base;``console.log(``"module_base : "``, module_base);``})``}``{``"name"``:``"libmyjni.so"``,``"base"``:``"0xde359000"``,``"size"``:``24576``,``"path"``:``"/data/app/com.gdufs.xman-ezNKFeRbVjUuHuaB1LWSdQ==/lib/arm/libmyjni.so"``}` |
|-|-|

#### getModuleByAddress 通过地址来获取module

| 12345678910 | `function hook_module3() {``Java.perform(function () {` `var module_data_addr` `=` `Process.getModuleByAddress(``0xde359000``);``console.log(``"module_data_addr : "``, JSON.stringify(module_data_addr));` `})``}` `{``"name"``:``"libmyjni.so"``,``"base"``:``"0xde359000"``,``"size"``:``24576``,``"path"``:``"/data/app/com.gdufs.xman-ezNKFeRbVjUuHuaB1LWSdQ==/lib/arm/libmyjni.so"``}` |
|-|-|

### 三、枚举符号

在so文件开发的过程中，不可避免的会使用到系统函数。

#### enumerateImports 枚举模块的导入表

| 1234567891011121314 | `function hook_so_1() {``Java.perform(function () {``var imports_data` `=` `Process.getModuleByName(``"libmyjni.so"``).enumerateImports();``for` `(var index` `=` `0``; index < imports_data.length; index``+``+``) {``const import_data` `=` `imports_data[index];``console.log(JSON.stringify(import_data))``}` `})``}``{``"type"``:``"function"``,``"name"``:``"__cxa_atexit"``,``"module"``:``"/system/lib/libc.so"``,``"address"``:``"0xf486c721"``}``{``"type"``:``"function"``,``"name"``:``"fopen"``,``"module"``:``"/system/lib/libc.so"``,``"address"``:``"0xf48647f1"``}``{``"type"``:``"function"``,``"name"``:``"__android_log_print"``,``"module"``:``"/system/lib/liblog.so"``,``"address"``:``"0xf4929b59"``}``{``"type"``:``"function"``,``"name"``:``"strlen"``,``"module"``:``"/system/lib/libc.so"``,``"address"``:``"0xf4821d85"``}``{``"type"``:``"function"``,``"name"``:``"fputs"``,``"module"``:``"/system/lib/libc.so"``,``"address"``:``"0xf486598d"``}` |
|-|-|

#### enumerateExports 枚举模块的导出表

| 1234567891011121314 | `function hook_so_2() {``Java.perform(function () {``var exports_data` `=` `Process.getModuleByName(``"libmyjni.so"``).enumerateExports();``for` `(var index` `=` `0``; index < exports_data.length; index``+``+``) {``const export_data` `=` `exports_data[index];``console.log(JSON.stringify(export_data))``}`  `})``}``{``"type"``:``"function"``,``"name"``:``"getValue"``,``"address"``:``"0xde35a321"``}``{``"type"``:``"function"``,``"name"``:``"setValue"``,``"address"``:``"0xde35a365"``}``{``"type"``:``"function"``,``"name"``:``"callWork"``,``"address"``:``"0xde35a445"``}``{``"type"``:``"function"``,``"name"``:``"JNI_OnLoad"``,``"address"``:``"0xde35a509"``}` |
|-|-|

#### enumerateSymbols 枚举模块的符号表

举例：得到libart.so中的RegisterNatives的内存地址，代码如下：

| 123456789101112131415161718 | `function hook_so_3() {``Java.perform(function () {``var symbols_data` `=` `Process.getModuleByName(``"libart.so"``).enumerateSymbols();``var RegisterNatives_addr` `=` `NULL;``for` `(var index` `=` `0``; index < symbols_data.length; index``+``+``) {``const symbol_data` `=` `symbols_data[index];``if``(symbol_data.name.indexOf(``"CheckJNI"``)` `=``=``-``1` `&& symbol_data.name.indexOf(``"RegisterNatives"``) !``=` `-``1``){``console.log(JSON.stringify(symbol_data))``RegisterNatives_addr` `=` `symbol_data.address;``}``}` `console.log(``"RegisterNatives_addr : "``,RegisterNatives_addr)`  `})``}` `{``"isGlobal"``:false,``"type"``:``"function"``,``"name"``:``"_ZN3art3JNI15RegisterNativesEP7_JNIEnvP7_jclassPK15JNINativeMethodi"``,``"address"``:``"0xf24ac1fd"``,``"size"``:``4632``}``RegisterNatives_addr :` `0xf24ac1fd` |
|-|-|

### 四、hook so 函数

想要对so函数进行hook必须先到到函数的内存地址。

#### hook 导出函数

获取导出函数的内存地址，除了枚举的方式，还有findExportByName和 getExportByName。获取到函数的地址之后（NativePointer）就可以使用Interceptor attach 进行hook

| 12345678910111213 | `function hook_so_func1() {``Java.perform(function () {``var func_addr` `=` `Module.findExportByName(``"libmyjni.so"``,``"n3"``);``console.log(func_addr);``Interceptor.attach(func_addr,{``onEnter:function(args){``console.log(args)``},onLeave:function (retval) {``console.log(retval)``}``})``})``}` |
|-|-|

#### hook 任意函数

在so文件中，获取到函数的内存地址，即可hook。而内存地址除了通过frida提供的API获取，还可以自己计算。
计算公式 ： so文件基址 + 函数相对偏移地址[+1]

| 123456789101112131415161718192021222324252627 | `function hook_so_func2() {``Java.perform(function () {``var module_addr` `=` `Module.findBaseAddress(``"libmyjni.so"``);``var func_addr` `=` `module_addr.add(``0x11F9``);``console.log(func_addr)``Interceptor.attach(func_addr,{``onEnter:function(args){``console.log(``"args"``,hexdump(args[``0``]))``},onLeave:function (retval) {``/``/` `console.log(hexdump(retval))``}``})` `})``}` `args` `0`  `1`  `2`  `3`  `4`  `5`  `6`  `7`  `8`  `9`  `A  B  C  D  E  F` `0123456789ABCDEF``f2793480` `78` `57` `67` `f2` `00` `80` `7c` `f2 e0 c3` `72` `f2` `07` `00` `00` `00`  `xWg...\|...r.....``f2793490` `07` `00` `00` `00` `00` `2a` `7f` `f2` `00` `10` `16` `f6` `01` `00` `00` `00`  `.....``*``..........``f27934a0` `00` `02` `00` `00` `00` `00` `00` `00` `07` `00` `00` `00` `01` `00` `00` `00`  `................``f27934b0` `10` `20` `a7 d6` `10` `20` `a7 d6` `18` `20` `a7 d6` `10` `6d` `6f` `6e`  `. ... ... ...mon``f27934c0` `69` `74` `6f` `72` `73` `00` `00` `00` `00` `35` `79` `f2` `00` `35` `79` `f2  itors....``5y``..``5y``.``f27934d0` `80` `35` `79` `f2` `00` `10` `00` `00` `28` `61` `67` `f2` `20` `07` `f9 eb  .``5y``.....(ag. ...` `f27934e0` `20` `07` `f9 eb` `28` `07` `f9 eb` `0a` `ac` `24` `00` `00` `00` `00` `00`   `...(.....$.....``f27934f0` `00` `00` `00` `00` `01` `00` `7b` `f2 e8 f2` `7b` `f2` `38` `f3` `7b` `f2  ......{...{.``8.``{.``f2793500` `80` `f9` `66` `13` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `..f.............``f2793510` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `................` |
|-|-|

### 五、修改函数参数与返回值

#### 修改函数数值参数与返回值

对于数值参数的修改，不能将参数直接等于100，比如args[1]=100,在C里面参数传递的都是指针形式的，那么100就不能直接传递了。可以通过 ptr(100)传递或者直接将100写入寄存器中。返回值retval也是一样的，修改的话用 replace

| 123456789101112131415 | `function hook_so_func3() {``Java.perform(function () {``var module_addr` `=` `Module.findBaseAddress(``"libmyjni.so"``);``var func_addr` `=` `module_addr.add(``0x11f9``);``Interceptor.attach(func_addr,{``onEnter:function(args){``console.log(``"args0"``,args[``0``].readCString())``args[``1``]` `=` `prt(``100``)``},onLeave:function (retval) {``console.log(retval)``retval .replace(``100``)``}``})``})``}` |
|-|-|

#### 修改字符串参数

注意：不能将字符串直接传入ptr中，ptr虽然可以接收string参数，但是必须是能转换成数值的。

#### (1) 修改参数指向的内存

writeByteArray用于从指定的地址写入内存数据。

#### (2) 将内存已有的字符串赋值给参数

#### (3) 在内存中创建新的字符串

在内存中申请空间，写入字符串后，将空间地址赋给参数。Memory的alloc方法可以用来申请指定的字节数的内存，会以NativePointer的形式返回这段内存的首地址。再通过NativePointer的writeByteArray写入字节数据。allocUtf8String这个函数内部封装了 直接用就行。

| 1234567891011121314151617181920212223 | `function hook_so_func4() {``Java.perform(function () {``var module_addr` `=` `Module.findBaseAddress(``"libmyjni.so"``);``var func_addr` `=` `module_addr.add(``0x11f9``);``var newStr` `=` `Memory.allocUtf8String(``"$$$"``)``var func_addr` `=` `module_addr.add(``0x11f9``);``var haveStrAddr` `=` `module_addr.add(``0x1234``);``Interceptor.attach(func_addr,{``onEnter:function(args){``console.log(``"args1"``,args[``1``],args[``1``].readCString())` `args[``1``]` `=` `newStr` `/``/``内存中创建` `args[``2``].writeByteArray(stringToBytes(``"xibei"``));``/``/``修改` `args[``3``]` `=` `haveStrAddr` `/``/``内存已有的` `},onLeave:function (retval) {``console.log(retval)``}``})``})``}` |
|-|-|

---

# 回复

## 回复 by mb_fidppcok (#2)

*2023-12-5 09:12*

先mark .以后可能得上哈

## 回复 by 秋狝 (#3)

*2023-12-5 11:13*

感谢分享

## 回复 by mb_fssslkzs (#4)

*2023-12-5 13:39*

yyds 永远的神

## 回复 by mb_ldbucrik (#5)

*2023-12-5 18:20*

![image](https://bbs.kanxue.com/view/img/face/85.gif)还是要看懂伪c代码才行

## 回复 by 万里星河 (#6)

*2023-12-5 22:48*

支持一下

## 回复 by mb_xsfdfkko (#7)

*2024-4-25 23:43*

args 可以得到函数参数的数量吗？
