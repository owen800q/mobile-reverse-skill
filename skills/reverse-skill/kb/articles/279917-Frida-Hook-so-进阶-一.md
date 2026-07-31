---
title: '[原创]Frida Hook so 进阶(一)'
url: https://bbs.kanxue.com/thread-279917.htm
tid: 279917
author: 复活甲
date: '2023-12-17'
tags: [Android安全, 原创, 基础理论]
crawled_at: '2026-07-31T14:35:33+08:00'
replies: 4
---

### 一、前言

应对一些比较复杂的so文件分析的时候，简单的frida应用已经不能满足我们的需求了。有时候为了定位关键位置，需要做很多复杂的调试，好的工具往往会事半功倍。

### 二、内存数据操作

#### 1.修改内存权限

内存页是分权限的，权限通常用rwx来表示，r代表可读，w代表可写，x代表可执行。计算出指定内存地址后，在操作之前可以先用Memory的protect的方法来修改对应的内存区域权限。

| 1234567 | `function hook_so() {``Java.perform(function(){``var addr` `=` `Module.findBaseAddress(``"libhello-jni.so"``);``console.log(``"addr :"``,addr);``Memory.protect(addr.add(``0x3c30``),``16``,``'rwx'``);``});``}` |
|-|-|

#### 2.读取指定地址的字符串

计算出地址后,可以用NativePointer的readCString来读取字符串

| 123456789 | `function hook_so() {``Java.perform(function(){``var addr` `=` `Module.findBaseAddress(``"libhello-jni.so"``);``var v1` `=` `addr.add(``0x2d548``);``console.log(v1.readCString());``});``}` `[Google Pixel` `2` `XL::com.example.hellojni_sign2]``-``> N10__cxxabiv117__array_type_infoE` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_YT5JMD9KCSTB5HX.webp)

#### 3.导出指定地址的内存数据

计算出指定内存地址后，可以使用hexdump函数，显示一段hex的内存数据。

| 123456789101112131415 | `function hook_so2() {``Java.perform(function(){``var addr` `=` `Module.findBaseAddress(``"libhello-jni.so"``);``var v1` `=` `addr.add(``0x2d548``);``console.log(hexdump(v1));``});``}` `[Google Pixel` `2` `XL::com.example.hellojni_sign2]``-``>``0`  `1`  `2`  `3`  `4`  `5`  `6`  `7`  `8`  `9`  `A  B  C  D  E  F` `0123456789ABCDEF``72f01ee548`  `4e` `31` `30` `5f` `5f` `63` `78` `78` `61` `62` `69` `76` `31` `31` `37` `5f`  `N10__cxxabiv117_``72f01ee558`  `5f` `61` `72` `72` `61` `79` `5f` `74` `79` `70` `65` `5f` `69` `6e` `66` `6f`  `_array_type_info``72f01ee568`  `45` `00` `4e` `31` `30` `5f` `5f` `63` `78` `78` `61` `62` `69` `76` `31` `31`  `E.N10__cxxabiv11``72f01ee578`  `36` `5f` `5f` `65` `6e` `75` `6d` `5f` `74` `79` `70` `65` `5f` `69` `6e` `66`  `6__enum_type_inf``72f01ee588`  `6f` `45` `00` `4e` `31` `30` `5f` `5f` `63` `78` `78` `61` `62` `69` `76` `31`  `oE.N10__cxxabiv1``72f01ee598`  `32` `30` `5f` `5f` `73` `69` `5f` `63` `6c` `61` `73` `73` `5f` `74` `79` `70`  `20__si_class_typ` |
|-|-|

#### 4.读取指定地址的内存数据

计算出指定内存地址后，可以使用NativePointer的readByteArray方法读取一段内存数据。

| 1234567 | `function hook_so3() {``Java.perform(function(){``var addr` `=` `Module.findBaseAddress(``"libhello-jni.so"``);``var v1` `=` `addr.add(``0x2d548``);``console.log(v1.readByteArray(``32``));``});``}` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_3S6VGE3NFYP6YP5.webp)

#### 5.写入数据到指定的内存地址

计算出指定内存地址后，可以使用NativePointer的writeByteArray。他的参数接收的是一个字节数组，所有我们就写几个工具函数。

| 1234567891011121314151617181920212223 | `function stringToBytes(``str``){``return` `hexToBytes(stringToHex(``str``));``}` `function stringToHex(``str``){``return` `str``.split("").``map``(function(c){``return` `(``"0"``+``c.charCodeAt(``0``).toString(``16``)).``slice``(``-``2``);``}).join("");``}` `function hexToBytes(``hex``){``for` `(var bytes``=``[],c` `=` `0``; c <` `hex``.length; c``+``=``2``)` `bytes.push(parseInt(``hex``.substr(c,``2``),``16``));``return` `bytes;``}` `function hexToString(hexStr){``var` `hex` `=` `hexStr.toString();``var` `str` `=` `'';``for` `(var i` `=` `0``; i <` `hex``.length; i``+``=``2``)` `str` `+``=` `String.fromCharCode(parseInt(``hex``.substr(i,``2``),``16``));``return` `str``;``}` |
|-|-|

计算出地址后，写入字符串xibei

| 1234567891011 | `function hook_so4() {``Java.perform(function(){``var addr` `=` `Module.findBaseAddress(``"libhello-jni.so"``);``var v1` `=` `addr.add(``0x2d548``);``console.log(v1.readByteArray(``32``));``Memory.protect(v1,``16``,``'rwx'``);``v1.writeByteArray(stringToBytes(``"xibei\0"``));``console.log(v1.readByteArray(``16``));` `});``}` |
|-|-|

修改前和修改后的样子
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_UAH6N42DU7UF9K9.webp)

#### 6.分配内存

在逆向分析的过程中，有时需要主动调用一些so函数,这时候需要自己构建新数据来传递参数。通常不能直接写，需要先分配内存，在写入。可以使用Memory中的alloc函数来分配内存。

| 12345678 | `function hook_so5() {``Java.perform(function(){``var addr` `=` `Memory.alloc(``16``);``addr.writeByteArray(stringToBytes(``"xibei\0"``));``console.log(addr.readByteArray(``16``));` `});``}` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_ZEAWSKM792TSPR9.webp)

### 三、从内存中导出so函数

某些APP应用程序会对so文件进行加固，或者对SO函数中的字符串进行加密。而加载到内存中的so函数一般都是解密的状态，这时候可以使用内存读写的方法，将so函数从内存中保存下来。
 通过传入的模块名，扎到对应的Module,得到模块基址，模块大小等信息。然后生成保存的路径，接着使用Memory.protect修改内存权限，再使用NativePointer的readByteArray方法读取整个so文件对应的内存数据。

| 1234567891011121314151617181920 | `function hook_so6(so_name) {``Java.perform(function(){``var module` `=` `Process.getModuleByName(so_name);``console.log(``"module :"``,JSON.stringify(module));``var current_app` `=` `Java.use(``"android.app.ActivityThread"``).currentApplication();``var` `dir` `=` `current_app.getApplicationContext().getFilesDir().getPath();``var path` `=` `dir``+``"/"``+``module.name``+``"_"``+``module.base``+``"_"``+``module.size``+``".so"``;``var` `file` `=` `new` `File``(path,``"wb"``);``console.log(``"path start  : "``,path);` `if` `(``file``){``Memory.protect(module.base,module.size,``"rwx"``);``var` `buffer` `=` `module.base.readByteArray(module.size);``file``.write(``buffer``);``file``.flush();``file``.close();``console.log(``"path end : "``,path);``}``});``}` |
|-|-|

### 四、读写文件

fopen 打开文件，fputs 写入文件，fgets 得到文件，fclose 关闭文件

| 123456789101112131415161718192021222324252627282930 | `function hook_so7() {``Java.perform(function () {``var fopen_addr` `=` `Module.findExportByName(``"libc.so"``,` `"fopen"``);``var fputs_addr` `=` `Module.findExportByName(``"libc.so"``,` `"fputs"``);``var fgets_addr` `=` `Module.findExportByName(``"libc.so"``,` `"fgets"``);``var fclose_addr` `=` `Module.findExportByName(``"libc.so"``,` `"fclose"``);` `var fopen` `=` `new NativeFunction(fopen_addr,``"pointer"``,[``"pointer"``,``"pointer"``]);``var fputs` `=` `new NativeFunction(fputs_addr,``"int"``,[``"pointer"``,``"pointer"``]);``var fgets` `=` `new NativeFunction(fgets_addr,``"pointer"``,[``"pointer"``,``"int"``,``"pointer"``]);``var fclose` `=` `new NativeFunction(fclose_addr,``"int"``,[``"pointer"``]);` `var file_name` `=` `Memory.allocUtf8String(``"/data/data/com.example.hellojni_sign2/files/xibei.txt"``);``var open_mode` `=` `Memory.allocUtf8String(``"w"``);``var` `buffer` `=` `Memory.allocUtf8String(``"xxxxxxbbbbbb"``);` `var` `file` `=` `fopen(file_name,open_mode);``fputs(``buffer``,``file``);``fclose(``file``);` `var file_naqme2` `=` `Memory.allocUtf8String(``"/data/data/com.example.hellojni_sign2/files/xibei.txt"``);``var open_get_mode` `=` `Memory.allocUtf8String(``"r"``);``var file_red` `=` `fopen(file_naqme2,open_get_mode);``var buffer2` `=` `Memory.alloc(``600``);``var data` `=` `fgets(buffer2,``60``,file_red);``console.log(data.readCString());``fclose(file_red);` `});``}` |
|-|-|

---

# 回复

## 回复 by 秋狝 (#2)

*2023-12-18 09:56*

感谢分享

## 回复 by mb_ldbucrik (#3)

*2023-12-18 12:37*

大佬有时间研究下这个项目呗https://bbs.kanxue.com/thread-276523.htm

## 回复 by jobs0 (#4)

*2024-1-3 10:47*

对于加固的APK好像不怎么起作用吧？尤其是识别了Frida的。

## 回复 by 复活甲 (#5)

*2024-1-3 11:09*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  jobs0](https://bbs.kanxue.com/user-948749.htm)
>
>  对于加固的APK好像不怎么起作用吧？尤其是识别了Frida的。
>
>

嗯。。。。没有反检测的话，加固不加固没有影响。有反检测的话，得先解决反检测的问题。
