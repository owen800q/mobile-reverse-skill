---
title: '[原创]无壳app的libmsaoaidsec.so frida反调试绕过姿势'
url: https://bbs.kanxue.com/thread-285811.htm
tid: 285811
author: Bileton
date: '2025-03-02'
tags: [Android安全, 原创, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:13:29+08:00'
replies: 11
---

# 前言

当前许多应用通过集成 `libmsaoaidsec.so` 实现针对 Frida 的反调试机制，其核心逻辑是在应用启动过程中，当加载 `libmsaoaidsec.so` 动态库时，会通过 `pthread_create()` 创建独立线程，并在该线程内执行反调试函数，主动扫描 Frida 进程、端口、内存特征等痕迹。若检测到 Frida 存在，则触发进程终止或崩溃。
针对这种机制的绕过思路可以从破坏反调试线程的加载或执行入手，文章会对不同的app进行测试，对于使用libmsaoaidsec.so来进行反调试的app，思路是一样的。

# 定位

通过hook dlopen()函数根据最后加载的so文件来确定程序是在加载哪个so之后退出的

| 123456789101112131415161718 | `function hook_dlopen(){``/``/``Android8.``0``之后加载so通过android_dlopen_ext函数``var android_dlopen_ext` `=` `Module.findExportByName(null,``"android_dlopen_ext"``);``console.log(``"addr_android_dlopen_ext"``,android_dlopen_ext);``Interceptor.attach(android_dlopen_ext,{``onEnter:function(args){``var pathptr` `=` `args[``0``];``if``(pathptr!``=``null && pathptr !``=` `undefined){``var path` `=` `ptr(pathptr).readCString();``console.log(``"android_dlopen_ext:"``,path);``}``},``onLeave:function(retvel){``console.log(``"leave!"``);``}``})``}``hook_dlopen()` |
|-|-|

如下，可以看到加载完libmsaoaidsec.so之后程序就退出了。
 ![image](https://bbs.kanxue.com/upload/attach/202503/993971_ANPP2BM5TBFQUKY.webp)
接下来我们找一个时机，就是在加载libmsaoaidsec.so的时候打印它里面创建的线程

| 123456789101112131415161718192021222324252627282930313233343536373839 | `function hook_dlopen(){``var android_dlopen_ext` `=` `Module.findExportByName(null,``"android_dlopen_ext"``);``console.log(``"addr_android_dlopen_ext"``,android_dlopen_ext);``Interceptor.attach(android_dlopen_ext,{``onEnter:function(args){``var pathptr` `=` `args[``0``];``if``(pathptr!``=``null && pathptr !``=` `undefined){``var path` `=` `ptr(pathptr).readCString();``if``(path.indexOf(``"libmsaoaidsec.so"``)!``=``-``1``){``console.log(``"android_dlopen_ext:"``,path);``hook_pthread()``}``}``},``onLeave:function(retvel){` `}``})``}` `function hook_pthread() {``var pth_create` `=` `Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``console.log(``"[pth_create]"``, pth_create);``Interceptor.attach(pth_create, {``onEnter: function (args) {``var module` `=` `Process.findModuleByAddress(args[``2``]);``if` `(module !``=` `null) {``console.log(``"address"``, module.name, args[``2``].sub(module.base));``}``},``onLeave: function (retval) {}``});``}` `function main(){``hook_dlopen()``}` `main()` |
|-|-|

如下看打印结果，有兴趣的小伙伴可以利用IDA反编译libmsaoaidsec.so跳转到这些地址去看这些函数都干了什么事情
![image](https://bbs.kanxue.com/upload/attach/202503/993971_VXW379PYFSY7MNX.webp)

# 反调试绕过

现在已经知道了是哪些函数来检测的frida，然后一个很重要的事情就是找到一个时机去把这几个函数都替换掉或者nop掉。
如果去IDA里分析的话，跳转到这几个函数的地址，通过交叉引用查看他们的上一级函数，会发现最终他们都会聚集到`init_proc`函数里，这是一个初始化函数，在so加载时会自动被调用，而且是so加载过程中最先执行的函数，那么就要找一个比`init_proc`函数执行更早的一个时机来把检测frida的函数替换掉或者nop掉。
在so文件的链接过程中linker里的`call_constructors()`函数会触发构造函数，对初始化函数进行注册，然后执行初始化函数，注册的初始化函数会放在`.init_array`函数列表里，可以在调用`call_constructors()`函数的时候动态替换so文件里检测frida的函数的地址，使它指向自定义的空函数。

## 姿势1

替换函数

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364 | `function hook_dlopen(){``/``/``Android8.``0``之后加载so通过android_dlopen_ext函数``var android_dlopen_ext` `=` `Module.findExportByName(null,``"android_dlopen_ext"``);``console.log(``"addr_android_dlopen_ext"``,android_dlopen_ext);``Interceptor.attach(android_dlopen_ext,{``onEnter:function(args){``var pathptr` `=` `args[``0``];``if``(pathptr!``=``null && pathptr !``=` `undefined){``var path` `=` `ptr(pathptr).readCString();``if``(path.indexOf(``"libmsaoaidsec.so"``)!``=``-``1``){``console.log(``"android_dlopen_ext:"``,path);``hook_call_constructors()``}``}``},``onLeave:function(retvel){``/``/``console.log(``"leave!"``);``}``})``}` `function hook_call_constructors() {``let linker` `=` `null;``if` `(Process.pointerSize` `=``=``=` `4``) {``linker` `=` `Process.findModuleByName(``"linker"``);``}` `else` `{``linker` `=` `Process.findModuleByName(``"linker64"``);``}``let call_constructors_addr, get_soname``let symbols` `=` `linker.enumerateSymbols();``for` `(let index` `=` `0``; index < symbols.length; index``+``+``) {``let symbol` `=` `symbols[index];``if` `(symbol.name` `=``=``=` `"__dl__ZN6soinfo17call_constructorsEv"``) {``call_constructors_addr` `=` `symbol.address;``}` `else` `if` `(symbol.name` `=``=``=` `"__dl__ZNK6soinfo10get_sonameEv"``) {``get_soname` `=` `new NativeFunction(symbol.address,` `"pointer"``, [``"pointer"``]);``}``}``console.log(call_constructors_addr)``var listener` `=` `Interceptor.attach(call_constructors_addr, {``onEnter: function (args) {``console.log(``"hooked call_constructors"``)``var module` `=` `Process.findModuleByName(``"libmsaoaidsec.so"``)``if` `(module !``=` `null) {``Interceptor.replace(module.base.add(``0x1c544``), new NativeCallback(function () {``console.log(``"0x1c544:替换成功"``)``},` `"void"``, []))``Interceptor.replace(module.base.add(``0x1b8d4``), new NativeCallback(function () {``console.log(``"0x1b8d4:替换成功"``)``},` `"void"``, []))``Interceptor.replace(module.base.add(``0x26e5c``), new NativeCallback(function () {``console.log(``"0x26e5c:替换成功"``)``},` `"void"``, []))``listener.detach()``}` `},``})``}``function main(){``hook_dlopen()``}` `main()` |
|-|-|

如下成功绕过了
 ![image](https://bbs.kanxue.com/upload/attach/202503/993971_H89DCEVXF45N5N5.webp)

## 姿势2

nop函数

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869 | `function nop_addr(addr) {``Memory.protect(addr,` `4` `,` `'rwx'``);``var w` `=` `new Arm64Writer(addr);``w.putRet();``w.flush();``w.dispose();``}` `function hook_dlopen(){``/``/``Android8.``0``之后加载so通过android_dlopen_ext函数``var android_dlopen_ext` `=` `Module.findExportByName(null,``"android_dlopen_ext"``);``console.log(``"addr_android_dlopen_ext"``,android_dlopen_ext);``Interceptor.attach(android_dlopen_ext,{``onEnter:function(args){``var pathptr` `=` `args[``0``];``if``(pathptr!``=``null && pathptr !``=` `undefined){``var path` `=` `ptr(pathptr).readCString();``if``(path.indexOf(``"libmsaoaidsec.so"``)!``=``-``1``){``console.log(``"android_dlopen_ext:"``,path);``hook_call_constructors()``}``}``},``onLeave:function(retvel){``/``/``console.log(``"leave!"``);``}``})``}` `function hook_call_constructors() {``let linker` `=` `null;``if` `(Process.pointerSize` `=``=``=` `4``) {``linker` `=` `Process.findModuleByName(``"linker"``);``}` `else` `{``linker` `=` `Process.findModuleByName(``"linker64"``);``}``let call_constructors_addr, get_soname``let symbols` `=` `linker.enumerateSymbols();``for` `(let index` `=` `0``; index < symbols.length; index``+``+``) {``let symbol` `=` `symbols[index];``if` `(symbol.name` `=``=``=` `"__dl__ZN6soinfo17call_constructorsEv"``) {``call_constructors_addr` `=` `symbol.address;``}` `else` `if` `(symbol.name` `=``=``=` `"__dl__ZNK6soinfo10get_sonameEv"``) {``get_soname` `=` `new NativeFunction(symbol.address,` `"pointer"``, [``"pointer"``]);``}``}``console.log(call_constructors_addr)``var listener` `=` `Interceptor.attach(call_constructors_addr, {``onEnter: function (args) {``console.log(``"hooked call_constructors"``)``var module` `=` `Process.findModuleByName(``"libmsaoaidsec.so"``)``if` `(module !``=` `null) {``nop_addr(module.base.add(``0x1c544``))``console.log(``"0x1c544:替换成功"``)``nop_addr(module.base.add(``0x1b8d4``))``console.log(``"0x1b8d4:替换成功"``)``nop_addr(module.base.add(``0x26e5c``))``console.log(``"0x26e5c:替换成功"``)``listener.detach()``}` `},``})``}``function main(){``hook_dlopen()``}` `main()` |
|-|-|

如下也可以绕过
![image](https://bbs.kanxue.com/upload/attach/202503/993971_GTREY75XA8EUJN9.webp)

参考文章：
https://mp.weixin.qq.com/s/mBJzRqP-0bGsiTqp6aJSAg
https://mp.weixin.qq.com/s/RyJiHrSO4CU9QLJitC7Tqg
https://bbs.kanxue.com/thread-284816.htm

---

# 回复

## 回复 by 黑屏 (#2)

*2025-3-3 10:11*

能否弄个中邮的分析下

## 回复 by iBa0 (#3)

*2025-3-3 17:24*

写的很nice，Android越来越卷啦????

## 回复 by bluegatar (#4)

*2025-3-6 02:22*

不错，现在方子越来月多了

## 回复 by 自己能 (#5)

*2025-3-7 11:17*

so 删掉就好了

## 回复 by weiyangs (#6)

*2025-3-14 14:57*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_Lyg_548](https://bbs.kanxue.com/user-894174.htm)
>
>  so 删掉就好了
>
>

兄弟不行啊，直接删除，应用都打不开了

## 回复 by weiyangs (#7)

*2025-3-14 14:58*

>
> [WMBa0](https://bbs.kanxue.com/user-971547.htm)
>
>  写的很nice，Android越来越卷啦????
>
>

卷死了，现在这个so又进化了，加了检测，反hook

## 回复 by fjqisba (#8)

*2025-3-14 15:21*

JNI_ONLOAD，INIT啥的，函数全部干掉试试呢

## 回复 by null0bj (#9)

*2025-4-2 18:20*

same
同样的库，甚至函数偏移都一样。
我以spawn模式启动，会出现空指针异常。
我跟踪了strstr函数，needle 记录依次为
"/system/bin/linker64",
"/bionic/bin/linker64",
"/apex/com.android.runtime/bin/linker64",
"solist"
经过多次测试当needle指向"solist" ，haystack为无效指针，然后进程终止。

LOAD:0000000000020CA8                 LDR             X0, [X20,#0x198] ; haystack

LOAD:0000000000020CAC                 CBZ             X0, loc_20CC0

LOAD:0000000000020CB0                 MOV             X1, X19 ; needle

LOAD:0000000000020CB4                 BL              strstr

LOAD:0000000000020CB8                 CMP             X0, #0

LOAD:0000000000020CBC                 CSEL            X21, X21, X20, EQ

上传的附件：
- crash.log

（2.33kb，5次下载）

## 回复 by mb_xaqlhidi (#10)

*2025-4-8 16:01*

一hook就crash，想了很久没想清楚怎么崩的

崩溃处附近的汇编

LOAD:0000000000018648 69 0A 40 F9                   LDR             X9, [X19,#0x10]

LOAD:000000000001864C 3F 01 08 EB                   CMP             X9, X8

LOAD:0000000000018650 40 F9 FF 54                   B.EQ            loc_18578

LOAD:0000000000018650

LOAD:0000000000018654 73 16 40 F9                   LDR             X19, [X19,#0x28]

LOAD:0000000000018658 93 FF FF B5                   CBNZ            X19, loc_18648

似乎是一直改X19的值然后直到空指针crash？

上传的附件：
- crash.log

（3.01kb，5次下载）

## 回复 by 倾天 (#11)

*2025-4-16 08:43*

厉害, 学习

## 回复 by kuku8888 (#12)

*2025-11-7 01:35*

厉害, 学习
