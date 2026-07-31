---
title: '[原创]某加固新版frida检测绕过-trace一把嗦'
url: https://bbs.kanxue.com/thread-289545.htm
tid: 289545
author: 东方玻璃
date: '2025-12-24'
tags: [Android安全, 原创, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T15:18:18+08:00'
replies: 359
---

# 前言

学习frida检测原理后, 向朋友寻找样本练手, 正好是某*加固企业版

根据网上资料成功绕过大部分样本的检测, 但某icbc是新版加固, 原方案不起作用

最终通过trace成功定位检测点并绕过, 写下此篇分享思路

**注意: 由于复现时疏忽, 在Pixel6a上绕过旧版加固时使用了[florida](https://github.com/Ylarod/Florida), 原版frida hook clone时进程仍然会被杀而非打印线程函数, 在Pixel3XL上绕过新版加固全程使用原版frida, 可参考新版定位和绕过思路 (我的锅)**

工具:

- IDA Pro 9.2
- Frida 16.1.4
- Unidbg 0.9.8
- 010 editor
- [vm-trace](https://github.com/jiqiu2022/vm-trace-release)
- [SoFixer](https://github.com/LunFengChen/SoFixer)

设备环境:

- Pixel 3XL Android 10
- Pixel 6A Android 14
- Apatch 11142
- ZygiskNext 1.3.1
- Zygisk LSPosed 1.10.2

文中样本均下载自应用商店,日期为12.8-12.10

**声明**:

1. 本文所述内容仅为技术研究与学习交流之目的, 所分析的 App 版权归其所属公司所有
2. 作者未对任何 App 进行非法篡改, 破解, 数据窃取或商业利用, 亦不鼓励或支持任何违反法律法规的行为
3. 读者不得将本文内容用于任何非法用途, 由此产生的一切法律责任由使用者自行承担
4. 请遵守《中华人民共和国网络安全法》及相关法律法规

# 某*加固(旧版)

关键SO: libDexHelper.so

样本: com.jxbank.mbank

## 基本信息搜集

搜集包名,加固方案,lib库等信息

## 定位检测so

hook dlopen 定位检测so, 低版本使用"dlopen", 高版本"android_dlopen_ext"

| 123456789101112131415161718192021222324252627282930 | `function` `hook_dlopen() {``const funcName =` `"android_dlopen_ext"``;` `// old version is "dlopen",` `const libc = Module.findBaseAddress(``"libc.so"``);``var` `funcPtr = Module.findExportByName(``null``, funcName);` `// 查找导出函数 (null 代表搜索所有模块)` `if` `(funcPtr !==` `null` `&& funcPtr !== undefined) {``console.log(`[*] Hooking ${funcName} at libc.so!0x${(funcPtr - libc.base).toString(16)}`);``// hook dlopen``Interceptor.attach(funcPtr, {``onEnter:` `function` `(args) {``this``.pathPtr = args[0];``if` `(``this``.pathPtr !==` `null` `&&` `this``.pathPtr !== undefined) {``try` `{``// 读取加载的so名称字符串并打印``var` `path =` `this``.pathPtr.readCString();` `console.log(``"\x1b[36m[dlopen] \x1b[0m"` `+ path);``}` `catch` `(e) {``console.log(``"[!] Error reading path string in "` `+` `this``.funcName);``}``}``}``});``}` `else` `{``console.log(``"[-] Warning: "` `+ funcName +` `" not found in exports."``);``}``}``function` `main(){``hook_dlopen();``}``setImmediate(main);` |
|-|-|

如果加载该so时, 在init, init_array, JNI_OnLoad等位置检测, 则加载该so后会立马杀掉进程

但在加载libDexHelper.so后一段时间才退出进程, 说明该so中创建了子线程进行检测

![6-dlopen-load-so](https://bbs.kanxue.com/upload/attach/202512/968342_55EN39KKWZ49WRQ.png)

## 定位检测线程

linux中最常用的线程创建函数是pthread_create, 定义如下

| 12345 | `#include <pthread.h>``int` `pthread_create(pthread_t *``thread``,` `//  保存新创建线程的线程标识符tid``const` `pthread_attr_t *attr,` `//  线程属性对象的指针``void` `*(*start_routine)(``void` `*),` `//  线程入口函数地址``void` `*arg);` `//  线程函数的参数` |
|-|-|

在hook dlopen中添加代码, 当加载libDexHelper.so时hook pthread_create减少多余输出(libart也会创建很多线程)

hook_pthread_create函数中打印创建的线程函数所在so以及偏移地址

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950 | `function` `hook_pthread_create() {``var` `pthread_create_addr = Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``console.log(``"pthread_create addr: "``, pthread_create_addr);``Interceptor.attach(pthread_create_addr, {``onEnter:` `function` `(args) {``var` `thread_func_addr = args[2];``var` `module = Process.findModuleByAddress(thread_func_addr);``console.log(`pthread_create thread func: ${module.name}+0x${(thread_func_addr - module.base).toString(16)}`);``}, onLeave:` `function` `(retval) {``}``});``}` `function` `hook_dlopen() {``const funcName =` `"android_dlopen_ext"``;``const libc = Module.findBaseAddress(``"libc.so"``);``var` `funcPtr = Module.findExportByName(``null``, funcName);` `if` `(funcPtr !==` `null` `&& funcPtr !== undefined) {``console.log(`[*] Hooking ${funcName} at libc.so!0x${(funcPtr - libc.base).toString(16)}`);` `Interceptor.attach(funcPtr, {``onEnter:` `function` `(args) {``this``.pathPtr = args[0];` `if` `(``this``.pathPtr !==` `null` `&&` `this``.pathPtr !== undefined) {``try` `{``var` `path =` `this``.pathPtr.readCString();``console.log(``"\x1b[36m[dlopen] \x1b[0m"` `+ path);``if` `(path.indexOf(``"libDexHelper.so"``) !== -1) {``this``.isTarget =` `true``;``}``}` `catch` `(e) {``console.log(``"[!] Error reading path string in "` `+` `this``.funcName);``}``}``}, onLeave:` `function` `(retval) {``if` `(``this``.isTarget) {``hook_pthread_create();``}``}``});``}` `else` `{``console.log(``"[-] Warning: "` `+ funcName +` `" not found in exports."``);``}``}``function` `main(){``hook_dlopen();``}``setImmediate(main);` |
|-|-|

结果如下, 没有成功打印

![7-hook-pthread-create](https://bbs.kanxue.com/upload/attach/202512/968342_P246ZV8UGUX6DDB.png)

所以可能并没有走pthread_create创建线程,而是更底层的系统调用clone

| 1234 | `#define _GNU_SOURCE``#include <sched.h>``// clone参数: 函数地址, 栈, 共享资源flag, 函数参数``int` `clone(``int` `(*fn)(``void` `*),` `void` `*stack,` `int` `flags,` `void` `*arg, ...);` |
|-|-|

hook clone, 打印线程函数所在模块和偏移

注意: 不能同时hook pthread_thread, 否则崩溃, 推测是因为libDexHelper检测了有没有hook libc的pthread_thread

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061 | `function` `hook_clone() {``// int clone(int (*fn)(void *), void *child_stack, int flags, void *arg, ...);``var` `clone_addr = Module.findExportByName(``"libc.so"``,` `"clone"``);``if` `(clone_addr) {``Interceptor.attach(clone_addr, {``onEnter:` `function` `(args) {``var` `addr = args[0];``if` `(!addr.isNull()) {``var` `mod = Process.findModuleByAddress(addr);` `// 获取地址所在的模块` `if` `(mod) {``var` `offset = addr.sub(mod.base);` `// 计算偏移``console.log(`[+]${mod.name}!${offset}`);``}` `else` `{``console.log(`[+] Unknown Module (Anonymous Memory), Addr: ${addr}`);``}``}``}``});``}` `else` `{``console.log(``"[-] clone export not found in libc.so"``);``}``}``function` `hook_dlopen() {``const funcName =` `"android_dlopen_ext"``;``const libc = Module.findBaseAddress(``"libc.so"``);``var` `funcPtr = Module.findExportByName(``null``, funcName);` `if` `(funcPtr !==` `null` `&& funcPtr !== undefined) {``console.log(`[*] Hooking ${funcName} at libc.so!0x${(funcPtr - libc.base).toString(16)}`);` `Interceptor.attach(funcPtr, {``onEnter:` `function` `(args) {``this``.pathPtr = args[0];` `if` `(``this``.pathPtr !==` `null` `&&` `this``.pathPtr !== undefined) {``try` `{``var` `path =` `this``.pathPtr.readCString();``console.log(``"\x1b[36m[dlopen] \x1b[0m"` `+ path);``if` `(path.indexOf(``"libDexHelper.so"``) !== -1) {``this``.isTarget =` `true``;``}``}` `catch` `(e) {``console.log(``"[!] Error reading path string in "` `+` `this``.funcName);``}``}``}, onLeave:` `function` `(retval) {``if` `(``this``.isTarget) {``//hook_pthread_create();    // 注意: 不能同时hook pthread_thread, 否则崩溃``hook_clone();``}``}``});``}` `else` `{``console.log(``"[-] Warning: "` `+ funcName +` `" not found in exports."``);``}``}``function` `main() {``hook_dlopen();``}``setImmediate(main);` |
|-|-|

结果如下, 输出的线程函数都在libc.so+0xc9c00中
**注意: 由于复现时疏忽, 在Pixel6a上绕过旧版加固使用了[florida](https://github.com/Ylarod/Florida), 原版frida hook clone时进程仍然会被杀而非打印线程函数**
**在Pixel3XL上绕过新版加固全程使用原版frida, 可参考新版定位和绕过思路**
![19-hook-clone-libc](https://bbs.kanxue.com/upload/attach/202512/968342_CYF6FHBHQUN2N36.png)

拉取libc.so扔进ida分析该地址

| 1 | `adb pull` `/system/lib64/libc``.so .``/libc64``.so` |
|-|-|

0xc9c00对应函数是"__pthread_start", 交叉引用发现在libc的"pthread_create"函数中通过clone封装了该函数

即**pthread_create本质上通过clone创建子线程**, 子线程函数地址作为clone的参数传递

可以发现pthread_create的参数3线程函数地址传给此处v30+96, 封装后作为clone的参数4

![image](https://bbs.kanxue.com/upload/attach/202512/968342_BAHE7CH2GQVDMSJ.png)

所以, 修改hook_clone, 通过参数4+96即可拿到真正的子线程函数地址

参考文章[【APP 逆向百例】某当劳 Frida 检测](https://www.freebuf.com/articles/others-articles/447681.html) 中的解释

| 1234567891011121314 | `function` `hook_clone() {``var` `clone = Module.findExportByName(``'libc.so'``,` `'clone'``);``Interceptor.attach(clone, {``onEnter:` `function` `(args) {``//只有当 args[3] 不为 NULL 时，才说明上层确实把 “线程控制块指针” 传进来了``if` `(args[3] != 0) {``var` `thread_func_addr = args[3].add(96).readPointer()` `// 真正的用户线程函数地址``var` `module = Process.findModuleByAddress(thread_func_addr);` `// 根据线程函数地址 addr，找它属于哪个模块``var` `offset = (thread_func_addr - module.base);` `// 获取相对于 base 的偏移``console.log(`[+]libc.so clone thread func: ${module.name}+0x${offset.toString(16)}`);``}``}``});``}` |
|-|-|

可以发现成功输出libDexHelper.so中创建了哪些线程检测函数

![8-hook-clone](https://bbs.kanxue.com/upload/attach/202512/968342_QTJ5MXAXQJTAE2A.png)

## 绕过检测线程

一个简单的思路是直接nop检测函数

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758 | `function` `nopFunc(addr) {``Memory.protect(addr, 4,` `'rwx'``);` `// 修改该地址的权限为可读可写``var` `writer =` `new` `Arm64Writer(addr);``writer.putRet();` `// 直接将函数首条指令设置为ret指令``writer.flush();` `// 写入操作刷新到目标内存，使得写入的指令生效``writer.dispose();` `// 释放 Arm64Writer 使用的资源``console.log(``"nop "` `+ addr +` `" success"``);``}``function` `bypass_detect_func() {``var` `base = Module.findBaseAddress(``"libDexHelper.so"``)``// jxbank``nopFunc(base.add(0x561d0));``nopFunc(base.add(0x52cc0));``nopFunc(base.add(0x5ded4));``nopFunc(base.add(0x5e410));``nopFunc(base.add(0x5fb48));``nopFunc(base.add(0x592c8));``nopFunc(base.add(0x69470));``}``function` `hook_dlopen() {``const funcName =` `"android_dlopen_ext"``;``const libc = Module.findBaseAddress(``"libc.so"``);``var` `funcPtr = Module.findExportByName(``null``, funcName);` `if` `(funcPtr !==` `null` `&& funcPtr !== undefined) {``console.log(`[*] Hooking ${funcName} at libc.so!0x${(funcPtr - libc.base).toString(16)}`);` `Interceptor.attach(funcPtr, {``onEnter:` `function` `(args) {``this``.pathPtr = args[0];` `if` `(``this``.pathPtr !==` `null` `&&` `this``.pathPtr !== undefined) {``try` `{``var` `path =` `this``.pathPtr.readCString();``console.log(``"\x1b[36m[dlopen] \x1b[0m"` `+ path);``if` `(path.indexOf(``"libDexHelper.so"``) !== -1) {``this``.isTarget =` `true``;``}``}` `catch` `(e) {``console.log(``"[!] Error reading path string in "` `+` `this``.funcName);``}``}``}, onLeave:` `function` `(retval) {``if` `(``this``.isTarget) {``//hook_pthread_create();``//hook_clone();``bypass_detect_func();``}``}``});``}` `else` `{``console.log(``"[-] Warning: "` `+ funcName +` `" not found in exports."``);``}``}``function` `main() {``hook_dlopen();``}``setImmediate(main);` |
|-|-|

成功绕过检测进入app

![9-nop-detect-thread](https://bbs.kanxue.com/upload/attach/202512/968342_NVDZEGD9KZX3SGC.png)

至此某*加固旧版的frida检测成功绕过, 但检测函数到底做了什么? 有待进一步分析

## dump libDexHelper.so

想分析检测函数中具体做了什么需要分析libDexHelper.so, 直接提取apk中的so可以发现是加密状态

start没有指令全是数据, init_proc则是有elf相关结构, 可能是自定义linker

![11-init-start](https://bbs.kanxue.com/upload/attach/202512/968342_EEVRMVHWDTEKCPF.png)

在dlopen刚加载该so后进行dump, 此时从文件加载到内存中, 应是解密状态

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748 | `function` `dump_so(so_name, package_name) {``var` `libso = Process.getModuleByName(so_name);``console.log(``"[name]:"``, libso.name);``console.log(``"[base]:"``, libso.base);``console.log(``"[size]:"``, ptr(libso.size));``console.log(``"[path]:"``, libso.path);``//包名需要设置``var` `file_path =` `"/data/data/"` `+ package_name +` `"/"` `+ libso.name +` `"_"` `+ libso.base +` `"_"` `+ ptr(libso.size) +` `".so"``;``var` `file_handle =` `new` `File(file_path,` `"wb"``);``if` `(file_handle && file_handle !=` `null``) {``Memory.protect(ptr(libso.base), libso.size,` `'rwx'``);``var` `libso_buffer = ptr(libso.base).readByteArray(libso.size);``file_handle.write(libso_buffer);``file_handle.flush();``file_handle.close();``console.log(``"[dump]:"``, file_path);``}``}` `function` `hook_dlopen_dump_so(soName, package_name) {``// hook android_dlopen_ext,该函数是Android系统加载so的函数``// 当使用该函数加载指定so时,设置is_can_hook为true,表示可以hook,之后执行dump_so``// 也就是加载so后马上dump,可以防止被反调试``var` `once_flag =` `true``;``Interceptor.attach(Module.findExportByName(``null``,` `"android_dlopen_ext"``),``{``onEnter:` `function` `(args) {``var` `pathptr = args[0];``if` `(pathptr !== undefined && pathptr !=` `null``) {``var` `path = ptr(pathptr).readCString();``if` `(path.indexOf(soName) >= 0) {``this``.is_can_hook =` `true``;``}``}``},``onLeave:` `function` `(retval) {``if` `(``this``.is_can_hook && once_flag) {``dump_so(soName, package_name);``once_flag =` `false``;``}``}``}``);``}``function` `main(){``hook_dlopen_dump_so(``"libDexHelper.so"``,``"com.icbc"``);``}``setImmediate(main);` |
|-|-|

dump成功, 进入手机端的shell复制到"/sdcard/Download"下方便pull

![10-dump-so](https://bbs.kanxue.com/upload/attach/202512/968342_9YYQ9DEU9BXX9QA.png)

adb pull到电脑端后使用SoFixer修复

![12-FixSO](https://bbs.kanxue.com/upload/attach/202512/968342_ZJSSUCJTZFMXCU5.png)

修复后可以正常分析so, 这里贴上2个检测函数

![14-detect-thread-5d8cc-status-maps](https://bbs.kanxue.com/upload/attach/202512/968342_S3VT492SVQTB5QU.png)![13-detect-thread-func](https://bbs.kanxue.com/upload/attach/202512/968342_Q8GZ9FNEXTZDXGH.png)

## 通杀脚本

经过以上分析, 可以总结出通杀脚本如下

首次执行时注释bypass_detect_func, 打印libDexHelper.so创建的线程函数地址

之后修改bypass_detect_func中nopFunc的偏移地址, 再次执行即可绕过

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687 | `function` `hook_pthread_create() {``var` `pthread_create_addr = Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``console.log(``"pthread_create addr: "``, pthread_create_addr);``Interceptor.attach(pthread_create_addr, {``onEnter:` `function` `(args) {``var` `thread_func_addr = args[2];``var` `module = Process.findModuleByAddress(thread_func_addr);``console.log(`pthread_create thread func: ${module.name}+0x${(thread_func_addr - module.base).toString(16)}`);``}, onLeave:` `function` `(retval) {``}``});``}` `function` `hook_clone() {``var` `clone = Module.findExportByName(``'libc.so'``,` `'clone'``);``Interceptor.attach(clone, {``onEnter:` `function` `(args) {``//只有当 args[3] 不为 NULL 时，才说明上层确实把 “线程控制块指针” 传进来了``if` `(args[3] != 0) {``var` `thread_func_addr = args[3].add(96).readPointer()` `// 真正的用户线程函数地址``var` `module = Process.findModuleByAddress(thread_func_addr);` `// 根据线程函数地址 addr，找它属于哪个模块``var` `offset = (thread_func_addr - module.base);` `// 获取相对于 base 的偏移``console.log(`[+]libc.so clone thread func: ${module.name}+0x${offset.toString(16)}`);``}``}``});``}` `function` `nopFunc(addr) {``Memory.protect(addr, 4,` `'rwx'``);` `// 修改该地址的权限为可读可写``var` `writer =` `new` `Arm64Writer(addr);``writer.putRet();` `// 直接将函数首条指令设置为ret指令``writer.flush();` `// 写入操作刷新到目标内存，使得写入的指令生效``writer.dispose();` `// 释放 Arm64Writer 使用的资源``console.log(``"nop "` `+ addr +` `" success"``);``}` `function` `bypass_detect_func() {``var` `base = Module.findBaseAddress(``"libDexHelper.so"``)``// jxbank``nopFunc(base.add(0x561d0));``nopFunc(base.add(0x52cc0));``nopFunc(base.add(0x5ded4));``nopFunc(base.add(0x5e410));``nopFunc(base.add(0x5fb48));``nopFunc(base.add(0x592c8));``nopFunc(base.add(0x69470));``}``function` `hook_dlopen() {``const funcName =` `"android_dlopen_ext"``;``const libc = Module.findBaseAddress(``"libc.so"``);``var` `funcPtr = Module.findExportByName(``null``, funcName);` `if` `(funcPtr !==` `null` `&& funcPtr !== undefined) {``console.log(`[*] Hooking ${funcName} at libc.so!0x${(funcPtr - libc.base).toString(16)}`);` `Interceptor.attach(funcPtr, {``onEnter:` `function` `(args) {``this``.pathPtr = args[0];` `if` `(``this``.pathPtr !==` `null` `&&` `this``.pathPtr !== undefined) {``try` `{``var` `path =` `this``.pathPtr.readCString();``console.log(``"\x1b[36m[dlopen] \x1b[0m"` `+ path);``if` `(path.indexOf(``"libDexHelper.so"``) !== -1) {``this``.isTarget =` `true``;``}``}` `catch` `(e) {``console.log(``"[!] Error reading path string in "` `+` `this``.funcName);``}``}``}, onLeave:` `function` `(retval) {``if` `(``this``.isTarget) {``//hook_pthread_create(); // 如果hook会由于检测libc.so而崩溃``hook_clone();` `// hook clone打印检测线程正常运行``bypass_detect_func();``}``}``});``}` `else` `{``console.log(``"[-] Warning: "` `+ funcName +` `" not found in exports."``);``}``}``function` `main() {``hook_dlopen();``}``setImmediate(main);` |
|-|-|

## 其他案例

除此之外, 其他bank样本也可以使用相同方法绕过检测

大部分bank是某*企业版, 招商是网易易盾, 兴业是爱加密

BOC

![14-BOC](https://bbs.kanxue.com/upload/attach/202512/968342_2HT8YNRN95R4FWA.png)

ABC

![15-ABC](https://bbs.kanxue.com/upload/attach/202512/968342_7UUJNDQZQAN2CA3.png)

CCB

![16-CCB](https://bbs.kanxue.com/upload/attach/202512/968342_KEMW7VPXT4NJHH2.png)

四大行中ICBC比较特殊, 是新版某*加固, 且无法使用旧版的思路定位检测点

## 问题

假设hook clone, 绕过了线程检测函数, 此时再hook pthread_create进程仍会结束

不难猜测是libDexHelper.so中检测了libc.so的pthread_create是否被hook

整理文章时发现此问题, 但由于新版加固中已经绕过该检测, 故不再深究旧版

![image](https://bbs.kanxue.com/upload/attach/202512/968342_HXEZ9CX5C5VERWE.png)

# 某*加固(新版)

## 定位新检测点

继续使用上述通杀脚本, 分别hook pthread_create和clone, 均没有打印出线程函数, 进程直接被杀

hook pthread_create

![image](https://bbs.kanxue.com/upload/attach/202512/968342_CKRFUB57UANGW2P.png)

hook clone

![23-bangbang-new-hook-clone](https://bbs.kanxue.com/upload/attach/202512/968342_SAT77SG32QGZ74X.png)

进程被杀, 没有其他信息, 但可以尝试trace进程崩溃前的函数执行流从而定位检测点

oacia师傅的 [stalker_trace_so](https://github.com/oacia/stalker_trace_so) 插件可以实现该功能, 使用插件前需要dump so, 同上操作类似不多赘述

将stalker_trace_so.py复制到ida的plugins目录下即可使用

使用方式为Edit > Plugins > stalker trace so, 自动生成trace脚本, spawn模式运行即可

![image](https://bbs.kanxue.com/upload/attach/202512/968342_DENANU4TSBYFUSD.png)

脚本需要修改so_name为app运行时so的真实名称 (默认为ida打开的文件名)

hook_dlopen 当加载目标so时, 执行trace

![image](https://bbs.kanxue.com/upload/attach/202512/968342_GM87ZPHXSX48PZ5.png)

spawn模式执行脚本

| 1 | `frida` `-``Uf com.icbc` `-``l trace_libDexHelper_fixed_icbc_kwajw.js` |
|-|-|

trace结果如下

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576777879 | `[Pixel` `3` `XL::com.icbc ]``-``> start Stalker!``Stalker end!``call1:JNI_OnLoad``call2:readlink``call3:j_p5SS$Sl5S5IS55I5_5ISI5I5SS5SIS0SlSISlS5S55_SOSI5lS0SlSIS_SOS05$S0``call4:p5SS$Sl5S5IS55I5_5ISI5I5SS5SIS0SlSISlS5S55_SOSI5lS0SlSIS_SOS05$S0` `call5:j_pSO5_5SSI5$S$SI5I5l5ISlSOS05l5ISISISIS0SISISI5$``5_S``$SISIS5S05S5$SI``call6:pSO5_5SSI5$S$SI5I5l5ISlSOS05l5ISISISIS0SISISI5$``5_S``$SISIS5S05S5$SI` `call7:j_pS_5$SlSO5SS$SI5ISlSISOSl5SSIS0Sl5I5S5I5S5IS$S_SISI5I5ISl5I5_S$S5``call8:pS_5$SlSO5SS$SI5ISlSISOSl5SSIS0Sl5I5S5I5S5IS$S_SISI5I5ISl5I5_S$S5``call9:sub_41FE0``call10:setsockopt``call11:j_pS$SlS_S_S$``5ISI5_5S5ISlSI5_SlS55lSIS0SI5IS``$SIS0SOS05_5IS_Sl5_SI5I``call12:pS$SlS_S_S$``5ISI5_5S5ISlSI5_SlS55lSIS0SI5IS``$SIS0SOS05_5IS_Sl5_SI5I``call13:j_pSl5I5$S5Sl5lSOSISOSIS0Sl5$``5lSlS05lSlSI5_SISlS5SlSOSl5S5I5ISlSIS0``call14:pSl5I5$S5Sl5lSOSISOSIS0Sl5$``5lSlS05lSlSI5_SISlS5SlSOSl5S5I5ISlSIS0``call15:getppid``call16:j_p5lS05ISISOSl5lS$SIS$``5S5I5ISIS``$S_5lSIS05S5I5SS_5I5lSO5_SOSI5_S05I``call17:p5lS05ISISOSl5lS$SIS$``5S5I5ISIS``$S_5lSIS05S5I5SS_5I5lSO5_SOSI5_S05I``call18:sub_32B78``call19:sched_yield``call20:socket``call21:fscanf``call22:atoi``call23:strrchr``call24:__strlen_chk``call25:__strncpy_chk2``call26:__vsprintf_chk``call27:connect``call28:fread``call29:regfree``call30:readdir``call31:__strncpy_chk``call32:wcstoul``call33:__errno``call34:sub_42098``call35:fputc``call36:dl_iterate_phdr``call37:j__ZN63p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISIS5Sl5IS0SI5S5S5SI5lSl5C2ENSt6__ndk117basic_string_viewIcNS1_11char_traitsIcEEEE``call38:_ZN63p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISIS5Sl5IS0SI5S5S5SI5lSl5C2ENSt6__ndk117basic_string_viewIcNS1_11char_traitsIcEEEE``call39:j__ZN63p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISIS5Sl5IS0SI5S5S5SI5lSl562p5lS_SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SIlS5_Ev` `call40:_ZN63p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISIS5Sl5IS0SI5S5S5SI5lSl562p5lS_SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SIlS5_Ev` `call41:fileno``call42:__sF``call43:sub_309C0``call44:sub_72CA8``call45:sub_308E0``call46:sub_45D38``call47:sub_2F8A0``call48:sub_B3B40``call49:sub_30270``call50:sub_B85DC``call51:sub_30E50``call52:sub_33590``call53:sub_335FC``call54:sub_3360C``call55:strtoll``call56:j_j_strtol``call57:j_strtol``call58:strtol``call59:sub_31500``call60:sub_35E24``call61:memcmp``call62:strtoul``call63:pthread_mutex_lock``call64:j__ZN63p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISIS5Sl5IS0SI5S5S5SI5lSl55parseEP9elf64_hdr``call65:_ZN63p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISIS5Sl5IS0SI5S5S5SI5lSl55parseEP9elf64_hdr``call66:__strchr_chk``call67:j__ZNK63p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISIS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISISSISlS5Sl5IS0SI5S5S5SI5lSl5Ev` `call68:_ZNK63p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISIS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISISSISlS5Sl5IS0SI5S5S5SI5lSl5Ev` `call69:fdopen``call70:j__ZNK63p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISIS5Sl5IS0SI5S5S5SI5lSl512validAddressEPvS1_``call71:_ZNK63p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISIS5Sl5IS0SI5S5S5SI5lSl512validAddressEPvS1_``call72:__open_2``call73:mprotect``Process terminated``[Pixel` `3` `XL::com.icbc ]``-``>` `Thank you` `for` `using Frida!` |
|-|-|

不难看出在JNI_OnLoad中执行了一系列操作以及检测, 调用 "_ZNK63p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SI5lSl563p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISIS5Sl5IS0SI5S5S5SI5lSl512validAddressEPvS1" 后进程被杀

直接搜索validaddress, 向上交叉引用发现JNI_OnLoad中调用了

"p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISlS5Sl5IS0SI5S5S5SI5lSl5::p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISI5SISIS5Sl5IS0SI5S5S5SI5lSl5::p5lS5SISISlSl5lSlSl5SIS05l5SIS5I5ISISSISlS5Sl5IS0SI5S5S5SI5lSl5"

很明显的检查操作并根据返回值决定是否杀掉进程, 没有调用exit, kill等函数, 而是jump 非法内存

![image](https://bbs.kanxue.com/upload/attach/202512/968342_RGGR4XP99U4AET8.png)

## 绕过新检测点

观察if条件, 当该函数返回0时, if条件必定不满足, 那么hook replace该函数, 强制返回值为0便可以绕过

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748 | `function` `hook_36390() {``var` `targetAddr = Module.findBaseAddress(``"libDexHelper.so"``).add(0x36390);``// 定义替换函数``var` `patch_detection =` `new` `NativeCallback(``function` `(arg0) {``console.log(``">>> 检测函数 sub_36390 已触发, 拦截并返回 0"``);``return` `0;` `// 这里的返回值会自动存入 x0``},` `'int'``, [``'pointer'``]);``// 实施替换``Interceptor.replace(targetAddr, patch_detection);` `}``function` `hook_dlopen() {``const funcName =` `"android_dlopen_ext"``;``const libc = Module.findBaseAddress(``"libc.so"``);``var` `funcPtr = Module.findExportByName(``null``, funcName);` `if` `(funcPtr !==` `null` `&& funcPtr !== undefined) {``console.log(`[*] Hooking ${funcName} at libc.so!0x${(funcPtr - libc.base).toString(16)}`);` `Interceptor.attach(funcPtr, {``onEnter:` `function` `(args) {``this``.pathPtr = args[0];` `if` `(``this``.pathPtr !==` `null` `&&` `this``.pathPtr !== undefined) {``try` `{``var` `path =` `this``.pathPtr.readCString();``console.log(``"\x1b[36m[dlopen] \x1b[0m"` `+ path);``if` `(path.indexOf(``"libDexHelper.so"``) !== -1) {``this``.isTarget =` `true``;``}``}` `catch` `(e) {``console.log(``"[!] Error reading path string in "` `+` `this``.funcName);``}``}``}, onLeave:` `function` `(retval) {``if` `(``this``.isTarget) {``hook_36390();``}``}``});``}` `else` `{``console.log(``"[-] Warning: "` `+ funcName +` `" not found in exports."``);``}``}``function` `main() {``hook_dlopen();``}``setImmediate(main);` |
|-|-|

成功绕过该检测, 但仍有其他检测

![image](https://bbs.kanxue.com/upload/attach/202512/968342_35PAWDAU4P5T4H9.png)

绕过该检测后继续尝试hook pthread_create 和 clone

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081 | `function` `hook_pthread_create() {``var` `pthread_create_addr = Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``console.log(``"pthread_create addr: "``, pthread_create_addr);``Interceptor.attach(pthread_create_addr, {``onEnter:` `function` `(args) {``var` `thread_func_addr = args[2];``var` `module = Process.findModuleByAddress(thread_func_addr);``console.log(`pthread_create thread func: ${module.name}+0x${(thread_func_addr - module.base).toString(16)}`);``}, onLeave:` `function` `(retval) {``}``});``}` `function` `hook_clone() {``var` `clone = Module.findExportByName(``'libc.so'``,` `'clone'``);``Interceptor.attach(clone, {``onEnter:` `function` `(args) {``//只有当 args[3] 不为 NULL 时，才说明上层确实把 “线程控制块指针” 传进来了``if` `(args[3] != 0) {``var` `thread_func_addr = args[3].add(96).readPointer()` `// 真正的用户线程函数地址``var` `module = Process.findModuleByAddress(thread_func_addr);` `// 根据线程函数地址 addr，找它属于哪个模块``var` `offset = (thread_func_addr - module.base);` `// 获取相对于 base 的偏移``if``(module.name.indexOf(``"libDexHelper.so"``) != -1){``console.log(`[+]libc.so clone thread func: ${module.name}+0x${offset.toString(16)}`);``}``}``}``});``}` `function` `hook_36390() {``var` `targetAddr = Module.findBaseAddress(``"libDexHelper.so"``).add(0x36390);``// 定义替换函数``var` `patch_detection =` `new` `NativeCallback(``function` `(arg0) {``//console.log(">>> 检测函数 sub_36390已触发, 拦截并返回 0");``return` `0;` `// 这里的返回值会自动存入 x0``},` `'int'``, [``'pointer'``]);``// 实施替换``Interceptor.replace(targetAddr, patch_detection);` `}` `function` `hook_dlopen() {``const funcName =` `"android_dlopen_ext"``;``const libc = Module.findBaseAddress(``"libc.so"``);``var` `funcPtr = Module.findExportByName(``null``, funcName);` `if` `(funcPtr !==` `null` `&& funcPtr !== undefined) {``console.log(`[*] Hooking ${funcName} at libc.so!0x${(funcPtr - libc.base).toString(16)}`);` `Interceptor.attach(funcPtr, {``onEnter:` `function` `(args) {``this``.pathPtr = args[0];` `if` `(``this``.pathPtr !==` `null` `&&` `this``.pathPtr !== undefined) {``try` `{``var` `path =` `this``.pathPtr.readCString();``console.log(``"\x1b[36m[dlopen] \x1b[0m"` `+ path);``if` `(path.indexOf(``"libDexHelper.so"``) !== -1) {``this``.isTarget =` `true``;``}``}` `catch` `(e) {``console.log(``"[!] Error reading path string in "` `+` `this``.funcName);``}``}``}, onLeave:` `function` `(retval) {``if` `(``this``.isTarget) {``hook_36390();``hook_clone();``//hook_pthread_create();// hook后进程依然会崩溃, 存在libc.so的pthread_create检测``}``}``});``}` `else` `{``console.log(``"[-] Warning: "` `+ funcName +` `" not found in exports."``);``}``}``function` `main() {``hook_dlopen();``}``setImmediate(main);` |
|-|-|

结果如下, hook pthread_create和旧版类似, 仍然会被杀(检测libc.so的pthread_create是否被hook)

但hook clone成功输出创建的检测线程 (此处可能出现6或7个, 似乎有2个并不是检测frida)

![image](https://bbs.kanxue.com/upload/attach/202512/968342_NHC9H6QJBYMYA28.png)

基于此, 同旧版类似, 尝试直接nop线程检测函数

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869 | `function` `hook_36390() {``var` `targetAddr = Module.findBaseAddress(``"libDexHelper.so"``).add(0x36390);``// 定义替换函数``var` `patch_detection =` `new` `NativeCallback(``function` `(arg0) {``//console.log(">>> 检测函数 sub_36390已触发, 拦截并返回 0");``return` `0;` `// 这里的返回值会自动存入 x0``},` `'int'``, [``'pointer'``]);``// 实施替换``Interceptor.replace(targetAddr, patch_detection);` `}``function` `nopFunc(addr) {``Memory.protect(addr, 4,` `'rwx'``);` `// 修改该地址的权限为可读可写``var` `writer =` `new` `Arm64Writer(addr);``writer.putRet();` `// 直接将函数首条指令设置为ret指令``writer.flush();` `// 写入操作刷新到目标内存，使得写入的指令生效``writer.dispose();` `// 释放 Arm64Writer 使用的资源``console.log(``"nop "` `+ addr +` `" success"``);``}``function` `bypass_detect_func() {``var` `base = Module.findBaseAddress(``"libDexHelper.so"``);``// nop 检测线程函数``nopFunc(base.add(0x58404));``nopFunc(base.add(0x54ef4))``nopFunc(base.add(0x5fd78));``nopFunc(base.add(0x5b218));``nopFunc(base.add(0x602b0));``nopFunc(base.add(0x667f4));``}` `function` `hook_dlopen() {``const funcName =` `"android_dlopen_ext"``;``const libc = Module.findBaseAddress(``"libc.so"``);``var` `funcPtr = Module.findExportByName(``null``, funcName);` `if` `(funcPtr !==` `null` `&& funcPtr !== undefined) {``console.log(`[*] Hooking ${funcName} at libc.so!0x${(funcPtr - libc.base).toString(16)}`);` `Interceptor.attach(funcPtr, {``onEnter:` `function` `(args) {``this``.pathPtr = args[0];` `if` `(``this``.pathPtr !==` `null` `&&` `this``.pathPtr !== undefined) {``try` `{``var` `path =` `this``.pathPtr.readCString();``console.log(``"\x1b[36m[dlopen] \x1b[0m"` `+ path);``if` `(path.indexOf(``"libDexHelper.so"``) !== -1) {``this``.isTarget =` `true``;``}``}` `catch` `(e) {``console.log(``"[!] Error reading path string in "` `+` `this``.funcName);``}``}``}, onLeave:` `function` `(retval) {``if` `(``this``.isTarget) {``hook_36390();``//hook_clone();``bypass_detect_func();``}``}``});``}` `else` `{``console.log(``"[-] Warning: "` `+ funcName +` `" not found in exports."``);``}``}``function` `main() {``hook_dlopen();``}``setImmediate(main);` |
|-|-|

绕过线程检测函数后成功进入app

![image](https://bbs.kanxue.com/upload/attach/202512/968342_KZ249YV9YNUZHYT.png)

至此可以得出结论: 新版相对旧版额外添加了检测函数0x36390, 绕过后和旧版思路基本相同

## libc & libart检测点

新旧版都检测了libc.so的pthread_create, 到底在哪里检测? 这是接下来的重点内容

在stalker_trace_so脚本中绕过检测并trace

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970 | `function` `hook_36390() {``var` `targetAddr = Module.findBaseAddress(``"libDexHelper.so"``).add(0x36390);``// 定义替换函数``var` `patch_detection =` `new` `NativeCallback(``function` `(arg0) {``//console.log(">>> 检测函数 sub_36390已触发, 拦截并返回 0");``return` `0;` `// 这里的返回值会自动存入 x0``},` `'int'``, [``'pointer'``]);``// 实施替换``Interceptor.replace(targetAddr, patch_detection);` `}``function` `hook_pthread_create() {``var` `pthread_create_addr = Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``console.log(``"pthread_create addr: "``, pthread_create_addr);``Interceptor.attach(pthread_create_addr, {``onEnter:` `function` `(args) {``var` `thread_func_addr = args[2];``var` `module = Process.findModuleByAddress(thread_func_addr);``//console.log("pthread_create called!")``if``(module&& module.name.indexOf(``"libDexHelper.so"``)>=0){``console.log(`pthread_create thread func: ${module.name}+0x${(thread_func_addr - module.base).toString(16)}`);``}``}, onLeave:` `function` `(retval) {``}``});``}``function` `nopFunc(addr) {``Memory.protect(addr, 4,` `'rwx'``);` `// 修改该地址的权限为可读可写``var` `writer =` `new` `Arm64Writer(addr);``writer.putRet();` `// 直接将函数首条指令设置为ret指令``writer.flush();` `// 写入操作刷新到目标内存，使得写入的指令生效``writer.dispose();` `// 释放 Arm64Writer 使用的资源``console.log(``"nop "` `+ addr +` `" success"``);``}``function` `bypass_detect_func() {``var` `base = Module.findBaseAddress(``"libDexHelper.so"``);``// nop 检测线程函数``nopFunc(base.add(0x58404));``nopFunc(base.add(0x54ef4))``nopFunc(base.add(0x5fd78));``nopFunc(base.add(0x5b218));``nopFunc(base.add(0x602b0));``nopFunc(base.add(0x667f4));``// nopFunc(base.add(0x594c8));``}``function` `hook_dlopen() {``Interceptor.attach(Module.findExportByName(``null``,` `"android_dlopen_ext"``),``{``onEnter:` `function` `(args) {``var` `pathptr = args[0];``if` `(pathptr !== undefined && pathptr !=` `null``) {``var` `path = ptr(pathptr).readCString();``//console.log(path);``if` `(path.indexOf(so_name) >= 0) {``this``.is_can_hook =` `true``;``}``}``},``onLeave:` `function` `(retval) {``if` `(``this``.is_can_hook) {``// note: you can do any thing before or after stalker trace so.``trace_so();``hook_36390();``bypass_detect_func();``hook_pthread_create();``}``}``}``);``}` |
|-|-|

可以发现最后崩溃时调用了几个函数,逐一查看后发现sub_54B20函数疑似检测libc和libart

![image](https://bbs.kanxue.com/upload/attach/202512/968342_RVMQQU3FAQ6X8KF.png)

交叉引用可以发现该函数有多处调用, 并且传入了libart.so

![image](https://bbs.kanxue.com/upload/attach/202512/968342_ADQJUTPYQWDQHNA.png)

libc.so有1处调用, 并且根据结果判断是否要jump 非法内存退出

![33-bangbang-new-func-54b20-libc](https://bbs.kanxue.com/upload/attach/202512/968342_KUDCDQ546AKANXR.png)

绕过思路同上类似, replace该函数, 强制返回0, 打印函数参数观察检测了哪些东西

同时hook pthread_create观察进程是否会被杀

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116 | `function` `hook_pthread_create() {``var` `pthread_create_addr = Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``console.log(``"pthread_create addr: "``, pthread_create_addr);``Interceptor.attach(pthread_create_addr, {``onEnter:` `function` `(args) {``var` `thread_func_addr = args[2];``var` `module = Process.findModuleByAddress(thread_func_addr);``//console.log("pthread_create called!")``if``(module&& module.name.indexOf(``"libDexHelper.so"``)>=0){``console.log(`pthread_create thread func: ${module.name}+0x${(thread_func_addr - module.base).toString(16)}`);``}``}, onLeave:` `function` `(retval) {``}``});``}``function` `hook_36390() {``var` `targetAddr = Module.findBaseAddress(``"libDexHelper.so"``).add(0x36390);``// 定义替换函数``var` `patch_detection =` `new` `NativeCallback(``function` `(arg0) {``//console.log(">>> 检测函数 sub_36390已触发, 拦截并返回 0");``return` `0;` `// 这里的返回值会自动存入 x0``},` `'int'``, [``'pointer'``]);``// 实施替换``Interceptor.replace(targetAddr, patch_detection);` `}``function` `nopFunc(addr) {``Memory.protect(addr, 4,` `'rwx'``);` `// 修改该地址的权限为可读可写``var` `writer =` `new` `Arm64Writer(addr);``writer.putRet();` `// 直接将函数首条指令设置为ret指令``writer.flush();` `// 写入操作刷新到目标内存，使得写入的指令生效``writer.dispose();` `// 释放 Arm64Writer 使用的资源``console.log(``"nop "` `+ addr +` `" success"``);``}``function` `bypass_detect_func() {``var` `base = Module.findBaseAddress(``"libDexHelper.so"``);``// nop 检测线程函数``nopFunc(base.add(0x58404));``nopFunc(base.add(0x54ef4))``nopFunc(base.add(0x5fd78));``nopFunc(base.add(0x5b218));``nopFunc(base.add(0x602b0));``nopFunc(base.add(0x667f4));``nopFunc(base.add(0x594c8));``}``// 检测libart关键函数``function` `hook_54b20() {``var` `targetAddr = Module.findBaseAddress(``"libDexHelper.so"``).add(0x54b20);``// 定义替换函数``var` `patch_detection =` `new` `NativeCallback(``function` `(arg0, arg1, arg2) {``console.log(``">>> 检测函数 sub_54b20 已触发, 拦截并返回 0"``);``console.log(``"   arg0:"``, arg0);``console.log(``"   arg1:"``, arg1.readCString());``console.log(``"   arg2:"``, arg2.readCString());``return` `0;` `// 这里的返回值会自动存入 x0``},` `'int64'``, [``'int'``,` `'pointer'``,` `'pointer'``]);``// 实施替换``Interceptor.replace(targetAddr, patch_detection);``}``function` `hook_clone() {``var` `clone = Module.findExportByName(``'libc.so'``,` `'clone'``);``Interceptor.attach(clone, {``onEnter:` `function` `(args) {``//只有当 args[3] 不为 NULL 时，才说明上层确实把 “线程控制块指针” 传进来了``if` `(args[3] != 0) {``var` `thread_func_addr = args[3].add(96).readPointer()` `// 真正的用户线程函数地址``var` `module = Process.findModuleByAddress(thread_func_addr);` `// 根据线程函数地址 addr，找它属于哪个模块``var` `offset = (thread_func_addr - module.base);` `// 获取相对于 base 的偏移``if``(module.name.indexOf(``"libDexHelper.so"``) != -1){``console.log(`[+]libc.so clone thread func: ${module.name}+0x${offset.toString(16)}`);``}``}``}``});``}``function` `hook_dlopen() {``const funcName =` `"android_dlopen_ext"``;``const libc = Module.findBaseAddress(``"libc.so"``);``var` `funcPtr = Module.findExportByName(``null``, funcName);` `if` `(funcPtr !==` `null` `&& funcPtr !== undefined) {``console.log(`[*] Hooking ${funcName} at libc.so!0x${(funcPtr - libc.base).toString(16)}`);` `Interceptor.attach(funcPtr, {``onEnter:` `function` `(args) {``this``.pathPtr = args[0];` `if` `(``this``.pathPtr !==` `null` `&&` `this``.pathPtr !== undefined) {``try` `{``var` `path =` `this``.pathPtr.readCString();``console.log(``"\x1b[36m[dlopen] \x1b[0m"` `+ path);``if` `(path.indexOf(``"libDexHelper.so"``) !== -1) {``this``.isTarget =` `true``;``}``}` `catch` `(e) {``console.log(``"[!] Error reading path string in "` `+` `this``.funcName);``}``}``}, onLeave:` `function` `(retval) {``if` `(``this``.isTarget) {``hook_36390();``bypass_detect_func();``hook_54b20();` `hook_clone();``hook_pthread_create();``}``}``});``}` `else` `{``console.log(``"[-] Warning: "` `+ funcName +` `" not found in exports."``);``}``}``function` `main() {``hook_dlopen();``}``setImmediate(main);` |
|-|-|

可以发现成功绕过了检测libc.so

![image](https://bbs.kanxue.com/upload/attach/202512/968342_QYHGQWHYE63C7CP.png)

那么libart.so在哪里检测的呢? 只需要注释 bypass_detect_func (nop线程检测函数) 即可

![image](https://bbs.kanxue.com/upload/attach/202512/968342_QNX3VXEZ2968EGF.png)

完整日志如下, libart主要检测用于注册/注销native方法的函数, 以及修复静态类的跳板函数

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344 | `>>> 检测函数 sub_54b20 已触发, 拦截并返回` `0``arg0:` `29``arg1: libc.so` `arg2: pthread_create``>>> 检测函数 sub_54b20 已触发, 拦截并返回` `0``arg0:` `29``arg1: libart.so``arg2: _ZN3art6mirror9ArtMethod14RegisterNativeEPNS_6ThreadEPKvb``>>> 检测函数 sub_54b20 已触发, 拦截并返回` `0``arg0:` `29``arg1: libart.so``arg2: _ZN3art6mirror9ArtMethod16UnregisterNativeEPNS_6ThreadE``>>> 检测函数 sub_54b20 已触发, 拦截并返回` `0``arg0:` `29``arg1: libart.so``arg2: _ZN3art9ArtMethod14RegisterNativeEPKvb``>>> 检测函数 sub_54b20 已触发, 拦截并返回` `0``arg0:` `29``arg1: libart.so``arg2: _ZN3art9ArtMethod16UnregisterNativeEv``>>> 检测函数 sub_54b20 已触发, 拦截并返回` `0``arg0:` `29``arg1: libart.so``arg2: _ZN3art9ArtMethod14RegisterNativeEPKv``>>> 检测函数 sub_54b20 已触发, 拦截并返回` `0``arg0:` `29``arg1: libart.so``arg2: _ZN3art11ClassLinker14RegisterNativeEPNS_6ThreadEPNS_9ArtMethodEPKv``>>> 检测函数 sub_54b20 已触发, 拦截并返回` `0``arg0:` `29``arg1: libart.so``arg2: _ZN3art11ClassLinker16UnregisterNativeEPNS_6ThreadEPNS_9ArtMethodE``>>> 检测函数 sub_54b20 已触发, 拦截并返回` `0``arg0:` `29``arg1: libart.so``arg2: _ZN3art11ClassLinker22FixupStaticTrampolinesENS_6ObjPtrINS_6mirror5ClassEEE``>>> 检测函数 sub_54b20 已触发, 拦截并返回` `0``arg0:` `29``arg1: libart.so``arg2: _ZN3art11ClassLinker22FixupStaticTrampolinesEPNS_6ThreadENS_6ObjPtrINS_6mirror5ClassEEE``>>> 检测函数 sub_54b20 已触发, 拦截并返回` `0``arg0:` `29``arg1: libart.so``arg2: _ZN3art11ClassLinker22FixupStaticTrampolinesEPNS_6mirror5ClassE` |
|-|-|

关于绕过某*加固的新版和旧版frida检测的绕过至此结束, 以上分析比较基础, 没有深入检测原理, 以及深究是否存在其他检测

整理时发现不够细心没考虑到不同情况导致走了很多弯路, 下面介绍trace指令流定位而非函数调用链定位

以下内容基于最初认为: 新版加固没有创建线程检测函数 (不走pthread_create以及clone,可能有其他创建线程的骚操作), 而是在JNI_OnLoad进行所有检测, 仅通过stalker_trace_so无法成功定位, 必须使用更强大的trace工具, 从trace函数调用链向指令流进发

## VM Trace

那么,回到最开始的地方: hook pthread_create , 并通过trace JNI_OnLoad的指令流定位检测点

工具使用追佬的 [vm-trace](https://github.com/jiqiu2022/vm-trace-release) , 详情可参考文章[[原创]基于VM的全新Trace框架发布!功能强大,一分钟1.5g，提高你的逆向体验~](https://bbs.kanxue.com/thread-285471.htm)

使用前需要准备环境:

1. Android 14以下的测试机
2. 推送test.so到app私有目录 "/data/data/<package_name>/"

由于我的Pixel 3XL Android10关闭selinux后有bug, 不能spawn启动app

所以不将test.so推送到/data/local/tmp, 而是app私有目录

虽然提取log更麻烦但不需要额外权限

脚本如下:

- hook_soload 和 prepareArgs 是原脚本自带的函数

hook_soload主动加载了test.so到app中, 加载目标so后执行hook和trace函数
- hook_JNI_OnLoad 是hook函数模版, 用于hook指定地址的函数, 可自定义

设置好函数偏移地址即可, 注意函数参数个数和类型不能弄错

调用了test.so的vmtrace进行trace
- test.so和log均使用app私有目录

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122 | `function` `prepareArgs(args) {``if` `(args === undefined \|\| !Array.isArray(args)) {``args = [];``}``var` `argNum = args.length;``var` `argSize = Process.pointerSize * argNum;``var` `argsPtr = Memory.alloc(argSize);` `for` `(``var` `i = 0; i < argNum; i++) {``var` `arg = args[i];``var` `argPtr;``if` `(!arg) {``arg = 0``}``if` `(arg` `instanceof` `NativePointer) {``// 如果是 NativePointer，直接使用``argPtr = arg;``}` `else` `if` `(``typeof` `arg ===` `'number'``) {``// 如果是数字，直接转换为指针``argPtr = ptr(arg);``}` `else` `if` `(``typeof` `arg ===` `'string'``) {``// 如果是字符串，分配内存并获取指针``argPtr = Memory.allocUtf8String(arg);``}` `else` `if` `(``typeof` `arg ===` `'object'` `&& arg.hasOwnProperty(``'handle'``)) {``// 如果是带有 handle 属性的对象（如 JNIEnv）``argPtr = arg.handle;``}` `else` `if` `(``typeof` `arg ===` `'object'` `&& arg` `instanceof` `ArrayBuffer) {``// 如果是二进制数据，分配内存并写入数据``var` `dataPtr = Memory.alloc(arg.byteLength);``Memory.writeByteArray(dataPtr, arg);``argPtr = dataPtr;``}` `else` `{``console.error(``'Unsupported argument type at index '` `+ i +` `':'``,` `typeof` `arg);``throw` `new` `TypeError(``'Unsupported argument type at index '` `+ i +` `': '` `+` `typeof` `arg);``}` `// 将参数指针写入参数数组``Memory.writePointer(argsPtr.add(i * Process.pointerSize), argPtr);``}` `return` `{``argsPtr: argsPtr,``argNum: argNum``};``}` `var` `vmtraceAddr;``var` `vmtrace;` `function` `hook_pthread_create() {``var` `pthread_create_addr = Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``console.log(``"pthread_create addr: "``, pthread_create_addr);``Interceptor.attach(pthread_create_addr, {``onEnter:` `function` `(args) {``var` `thread_func_addr = args[2];``var` `module = Process.findModuleByAddress(thread_func_addr);``if``(module&& module.name.indexOf(``"libDexHelper.so"``)>=0){``console.log(`pthread_create thread func: ${module.name}+0x${(thread_func_addr - module.base).toString(16)}`);``}``}, onLeave:` `function` `(retval) {``}``});``}` `function` `hook_JNI_OnLoad() {``var` `aimbase = Module.findBaseAddress(``"libDexHelper.so"``);``console.log(``"start hook libDexHelper.so JNI_OnLoad"``);``var` `targetFuncAddr = aimbase.add(0x36618);``Interceptor.replace(targetFuncAddr,` `new` `NativeCallback(``function` `(arg0, arg1) {` `// 注意参数个数``console.log(``"[+] trace JNI_OnLoad"``);``Interceptor.revert(targetFuncAddr);``Interceptor.flush();``var` `args = [arg0, arg1];` `// 注意函数参数个数``var` `{ argsPtr, argNum } = prepareArgs(args);``var` `argPtr1 = Memory.allocUtf8String(``"/data/data/com.icbc/log.txt"``);` `// log写入app私有目录``var` `res = vmtrace(targetFuncAddr, argsPtr, argNum, argPtr1, 0);` `// 开始trace``console.log(res)``return` `res;``},` `'int'``, [``'pointer'``,` `'pointer'``]));` `// 注意参数和返回值类型``}` `function` `hook_soload() {``var` `dlopenPtr = Module.findExportByName(``null``,` `'dlopen'``);``var` `dlopen =` `new` `NativeFunction(dlopenPtr,` `'pointer'``, [``'pointer'``,` `'int'``]);``var` `soPath =` `"/data/data/com.icbc/test.so"``;` `var` `soPathPtr = Memory.allocUtf8String(soPath);``var` `handle = dlopen(soPathPtr, 2);` `// 主动加载so用于trace``console.log(handle);``vmtraceAddr = Module.findExportByName(``"test.so"``,` `'vm_call'``);``console.log(``"vmtraceAddr: "``, vmtraceAddr);``vmtrace =` `new` `NativeFunction(vmtraceAddr,` `'pointer'``, [``'pointer'``,` `'pointer'``,` `'uint32'``,` `'pointer'``,` `'uint32'``]);` `var` `isinit = 0;``var` `dlopen_addr = Module.findExportByName(``null``,` `"android_dlopen_ext"``);``var` `find = 0;``console.log(``"android_dlopen_ext: "``, dlopen_addr);``Interceptor.attach(dlopen_addr, {``onEnter:` `function` `(args) {``var` `addr = args[0];``var` `str = ptr(addr).readCString();``this``.name = str;` `console.log(``"dlopen: "` `+ str);``if` `(str.indexOf(``"libDexHelper.so"``) >= 0) {``console.log(``"dlopen==> "` `+ (str));``find = 1;``}` `else` `{``find = 0;``}``},``onLeave:` `function` `(retval) {``if` `(find > 0) {``if` `(isinit == 0) {``hook_JNI_OnLoad();``hook_pthread_create();``isinit = 1;``}``}``}``})``}``setImmediate(hook_soload)` |
|-|-|

spawn模式启动

| 1 | `frida` `-``Uf com.icbc` `-``l vmtrace.js` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202512/968342_MN4X84X9ZKS3EH6.png)

这里有个小技巧:

我们的主要目的是定位崩溃点和检测函数, 而非根据trace还原算法

log.txt可能几千万行代码, 4-5GB, 提取到pc再分析太慢, 使用tail命令打印最后几行trace即可

tail命令默认打印10行, 可通过-n参数指定行数

不难发现在0x382c4处跳转到非法内存0x12dc导致app进程被杀

![image](https://bbs.kanxue.com/upload/attach/202512/968342_55EG4KNCA3EUXWR.png)

跟进so发现关键检测函数, 根据上述内容, 直接hook replace该函数并强制返回0即可绕过

![image](https://bbs.kanxue.com/upload/attach/202512/968342_5F3NUJAWXSQQSHV.png)

绕过函数

| 12345678910 | `function` `hook_36390() {``var` `targetAddr = Module.findBaseAddress(``"libDexHelper.so"``).add(0x36390);``// 定义替换函数``var` `patch_detection =` `new` `NativeCallback(``function` `(arg0) {``console.log(``">>> 检测函数 sub_36390 已触发, 拦截并返回 0"``);``return` `0;` `// 这里的返回值会自动存入 x0``},` `'int'``, [``'pointer'``]);``// 实施替换``Interceptor.replace(targetAddr, patch_detection);``}` |
|-|-|

trace结果, 成功绕过

![image](https://bbs.kanxue.com/upload/attach/202512/968342_75Q5264UK6VBVE2.png)

新的崩溃点在0x3a5d8

![40-bangbang-new-vmtrace-result2](https://bbs.kanxue.com/upload/attach/202512/968342_WUHDYSQBAQD29K4.png)

跟进后发现调用sub_54B20后根据返回值判断是否jump非法内存

而54b20前文提到过, 用于检测libc.so和libart.so的关键函数是否被hook

![image](https://bbs.kanxue.com/upload/attach/202512/968342_AEKMP53P7QXYBCC.png)

同上, replace该函数, 强制返回0

| 12345678910111213 | `function` `hook_54b20() {``var` `targetAddr = Module.findBaseAddress(``"libDexHelper.so"``).add(0x54b20);``// 定义替换函数``var` `patch_detection =` `new` `NativeCallback(``function` `(arg0, arg1, arg2) {``console.log(``">>> 检测函数 sub_54b20 已触发, 拦截并返回 0"``);``console.log(``"   arg0:"``, arg0);``console.log(``"   arg1:"``, arg1.readCString());``console.log(``"   arg2:"``, arg2.readCString());``return` `0;` `// 这里的返回值会自动存入 x0``},` `'int64'``, [``'int'``,` `'pointer'``,` `'pointer'``]);``// 实施替换``Interceptor.replace(targetAddr, patch_detection);``}` |
|-|-|

绕过该检测后trace发现hook pthread_create成功, 打印出检测线程函数

![image](https://bbs.kanxue.com/upload/attach/202512/968342_U59GTUG4Z2KT9H3.png)

同上nop这些检测函数即可

| 12345678910111213141516171819 | `function` `nopFunc(addr) {``Memory.protect(addr, 4,` `'rwx'``);` `// 修改该地址的权限为可读可写``var` `writer =` `new` `Arm64Writer(addr);``writer.putRet();` `// 直接将函数首条指令设置为ret指令``writer.flush();` `// 写入操作刷新到目标内存，使得写入的指令生效``writer.dispose();` `// 释放 Arm64Writer 使用的资源``console.log(``"nop "` `+ addr +` `" success"``);``}``function` `bypass_detect_func() {``var` `base = Module.findBaseAddress(``"libDexHelper.so"``);``// nop 检测线程函数``nopFunc(base.add(0x58404));``nopFunc(base.add(0x54ef4))``nopFunc(base.add(0x5fd78));``nopFunc(base.add(0x5b218));``nopFunc(base.add(0x602b0));``nopFunc(base.add(0x667f4));``nopFunc(base.add(0x594c8));``}` |
|-|-|

绕过检测函数后成功进入app

![image](https://bbs.kanxue.com/upload/attach/202512/968342_2QJJN98J3XJZAMK.png)

另外虽然此处崩溃, 但trace结果反复循环一段代码, 即单字节读取maps的内容

![43-bangbang-new-vmtrace-result3](https://bbs.kanxue.com/upload/attach/202512/968342_AAFCHS8NT6EKRMJ.png)

跟进发现代码属于sub_5d368函数, 扫描maps

![image](https://bbs.kanxue.com/upload/attach/202512/968342_KBB9E4N5AXQ5WHH.png)

值得一提的是之前使用stalker_trace_so没有发现该函数, 不hook该函数也能正常绕过检测

测试发现如果trace JNI_OnLoad, 无论是否hook该函数都会崩溃, 推测有其他检测, 或者trace对环境有影响

不hook 5D368时

![image](https://bbs.kanxue.com/upload/attach/202512/968342_5RC5HJKCM2ZMYEH.png)

hook 5D368时

![image](https://bbs.kanxue.com/upload/attach/202512/968342_GTTK7EPN7QNBJZ3.png)

trace结果如下 (两次trace报错结果一致)

![48-bangbang-new-vmtrace-result4](https://bbs.kanxue.com/upload/attach/202512/968342_9WA3FA98ESV5962.png)

## 其他检测函数

列举分析过程中遇到的检测函数和疑似的检测函数

### inline hook 0xae1f4

函数内部有多处疑似inline hook检测的特征

![46-inline-hook-detect](https://bbs.kanxue.com/upload/attach/202512/968342_XRJJSFFJBBZP8D9.png)

交叉引用该函数发现疑似hook 了自身的read, open, openat等函数

![image](https://bbs.kanxue.com/upload/attach/202512/968342_3CPYJJ2TPBB49AH.png)

所以该函数大概率是hook自身的read/open系列函数, 使用自定义的函数, 防止被逆向人员hook

在尝试hook ae1f4后会导致崩溃, 即执行到frida的hook跳转代码后被识别为非法内存

### maps检测 0x42098

0x42098函数伪代码如下, 打开maps后单字节读取指定so的部分内存属性, 但没有杀进程

![image](https://bbs.kanxue.com/upload/attach/202512/968342_SDAXC53NVNBNKG7.png)

### 特征检测 0x32e64

检测root, frida, xposed, hook等特征

![image](https://bbs.kanxue.com/upload/attach/202512/968342_HH2AW9PD9S73MER.png)

# SoFixer导入表符号问题

使用原版[SoFixer](https://github.com/F8LEFT/SoFixer)会出现导入表符号不匹配问题
如图所示左边是正确符号,右边是错误符号, 非常影响分析
 ![image](https://bbs.kanxue.com/upload/attach/202512/968342_67X2FEH66VZPRWJ.webp)
修复方案参考 [[原创] SoFixer导入表问题修复及ELF解析简记](https://bbs.kanxue.com/thread-282221.htm)  但修复版 [SoFixer](https://github.com/Chenyangming9/SoFixer) 没有Release包
感谢小风提供编译好的修复版 [SoFixer](https://github.com/LunFengChen/SoFixer)

# References

[【APP 逆向百例】某当劳 Frida 检测](https://www.freebuf.com/articles/others-articles/447681.html)

[从inlinehook角度检测frida](https://bbs.kanxue.com/thread-269862.htm)

[[原创]《安卓逆向这档事》第十九课、表哥，你也不想你的Frida被检测吧!(下)](https://bbs.kanxue.com/thread-282623.htm)

[[原创]基于VM的全新Trace框架发布!功能强大,一分钟1.5g，提高你的逆向体验~](https://bbs.kanxue.com/thread-285471.htm)

---

# 回复

## 回复 by 寻梦之璐 (#2)

*2025-12-24 11:21*

666

## 回复 by ChenSem (#3)

*2025-12-24 11:34*

表哥牛逼

## 回复 by 夜惜风雨 (#4)

*2025-12-24 11:37*

66666666666

## 回复 by 棕熊 (#5)

*2025-12-24 11:46*

太强了，支持一波～

## 回复 by 东方玻璃 (#6)

*2025-12-24 11:47*

>
> [棕熊](https://bbs.kanxue.com/user-967562.htm)
>
>  太强了，支持一波～
>
>

感谢佬的vmtrace,强推![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by 丶咖啡猫丶 (#7)

*2025-12-24 11:52*

666

## 回复 by git_94730eaydwshawke-gif (#8)

*2025-12-24 11:53*

前排

## 回复 by _thouger (#9)

*2025-12-24 11:54*

牛逼

## 回复 by mb_mlyojneh (#10)

*2025-12-24 11:56*

太强了

## 回复 by mb_lakweznz (#11)

*2025-12-24 11:56*

太厉害了

## 回复 by bullyxy (#12)

*2025-12-24 11:58*

太厉害了!!

## 回复 by 嘎嘎真的很棒 (#13)

*2025-12-24 12:01*

太厉害了!!

## 回复 by 机车王子 (#14)

*2025-12-24 12:11*

你的帖子非常有用，感谢分享！

## 回复 by ldehua (#15)

*2025-12-24 12:20*

太厉害了!!

## 回复 by artake (#16)

*2025-12-24 12:29*

很经典的过检测文章。

## 回复 by 我不是卷王 (#17)

*2025-12-24 12:40*

66

## 回复 by Yangser (#18)

*2025-12-24 12:48*

已严肃学习

## 回复 by mb_asiwnxyv (#19)

*2025-12-24 12:57*

感谢分享

## 回复 by wx_故事与酒 (#20)

*2025-12-24 12:58*

666666666666666666666666666

## 回复 by mb_qimctavn (#21)

*2025-12-24 13:12*

6

## 回复 by cpannn (#22)

*2025-12-24 13:12*

66666

## 回复 by xianhuimin (#23)

*2025-12-24 13:22*

tql，666

## 回复 by mb_ldbucrik (#24)

*2025-12-24 13:23*

感谢分享

## 回复 by 黑屏 (#25)

*2025-12-24 13:25*

6666

## 回复 by mb_dfcqyqvn (#26)

*2025-12-24 13:29*

感谢分享

## 回复 by mb_dcjxxhsk (#27)

*2025-12-24 13:35*

666

## 回复 by 华中区总舵之 (#28)

*2025-12-24 13:42*

666

## 回复 by 我心向山 (#29)

*2025-12-24 13:58*

666

## 回复 by ReverseApp (#30)

*2025-12-24 14:03*

777

## 回复 by wx_huhu_859 (#31)

*2025-12-24 14:10*

11

## 回复 by tigericon (#32)

*2025-12-24 14:13*

666

## 回复 by zylyy (#33)

*2025-12-24 14:24*

666

## 回复 by nhtr (#34)

*2025-12-24 14:26*

6666

## 回复 by mb_uzmffdbw (#35)

*2025-12-24 14:28*

6666

## 回复 by mb_pesxllvn (#36)

*2025-12-24 14:29*

666

## 回复 by AYHMO (#37)

*2025-12-24 14:35*

666

## 回复 by 飞机上唱山歌 (#38)

*2025-12-24 14:40*

1

## 回复 by mb_vitsvelx (#39)

*2025-12-24 14:48*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by doduhuang (#40)

*2025-12-24 14:48*

绝对干货啊.太牛逼了.![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by HuanYue_sec (#41)

*2025-12-24 15:17*

66666666

## 回复 by lqfcugo (#42)

*2025-12-24 15:24*

666

## 回复 by mb_xjdhrmck (#43)

*2025-12-24 15:49*

6666

## 回复 by 钱钱钱￥ (#44)

*2025-12-24 15:51*

111

## 回复 by Ram98 (#45)

*2025-12-24 15:57*

666

## 回复 by 带带弟弟吧 (#46)

*2025-12-24 16:02*

太厉害le

## 回复 by mb_vjpiriil (#47)

*2025-12-24 16:04*

大佬666

## 回复 by upcj (#48)

*2025-12-24 16:08*

666

## 回复 by 眩晕症 (#49)

*2025-12-24 16:37*

666

## 回复 by mb_kozxrjqu (#50)

*2025-12-24 16:42*

学习

## 回复 by Imxz (#51)

*2025-12-24 16:58*

tql

## 回复 by spdfdfer (#52)

*2025-12-24 16:59*

6666

## 回复 by jw8888 (#53)

*2025-12-24 19:55*

6666

## 回复 by 暗香沉浮 (#54)

*2025-12-24 20:06*

111

## 回复 by MaYil (#55)

*2025-12-24 20:34*

感谢分享

## 回复 by JOE_TR13 (#56)

*2025-12-24 21:07*

太强了

## 回复 by cpannn (#57)

*2025-12-24 21:58*

我复现了，楼主用的是葫芦魔改的frida吧，原版的出不了这样的效果，葫芦魔改的frida才行

## 回复 by darbra (#58)

*2025-12-24 22:17*

6666

## 回复 by buluo533 (#59)

*2025-12-24 22:18*

太强了，大佬

## 回复 by 一只鸭子 (#60)

*2025-12-24 22:22*

太强了

## 回复 by 东方玻璃 (#61)

*2025-12-24 22:45*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  cpannn](https://bbs.kanxue.com/user-977484.htm)
>
>  我复现了，楼主用的是葫芦魔改的frida吧，原版的出不了这样的效果，葫芦魔改的frida才行
>
>

旧版复现时Pixel6a好像用了魔改的,新版用Pixel3XL没有,全原版,可能有点出入

## 回复 by 逆向小白一号 (#62)

*2025-12-24 23:05*

6666666

## 回复 by 东方玻璃 (#63)

*2025-12-24 23:07*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  cpannn](https://bbs.kanxue.com/user-977484.htm)
>
>  我复现了，楼主用的是葫芦魔改的frida吧，原版的出不了这样的效果，葫芦魔改的frida才行
>
>

已添加声明,感谢师傅指出

## 回复 by mb_ukycmyfn (#64)

*2025-12-24 23:14*

牛逼

## 回复 by 啊你好哇123 (#65)

*2025-12-24 23:38*

学习

## 回复 by wx_Huber Barrientos (#66)

*2025-12-25 01:18*

感谢分享

## 回复 by 阳光宝贝 (#67)

*2025-12-25 01:54*

感谢分享

## 回复 by mb_fhpfcoqp (#68)

*2025-12-25 09:24*

6666

## 回复 by GEKEZYX (#69)

*2025-12-25 09:52*

tql

## 回复 by 不具名的悲伤 (#70)

*2025-12-25 10:22*

6

## 回复 by mb_pmgifpme (#71)

*2025-12-25 11:28*

1

## 回复 by mb_ypgiyonb (#72)

*2025-12-25 12:51*

1

## 回复 by SomeMx (#73)

*2025-12-25 13:15*

学习一下

## 回复 by 一颗大山楂 (#74)

*2025-12-25 13:33*

亲测可用，真牛比

## 回复 by rookie江 (#75)

*2025-12-25 15:29*

666

## 回复 by 土豆爱学习 (#76)

*2025-12-25 16:31*

谢谢分享

## 回复 by 司徒废人 (#77)

*2025-12-25 16:43*

感谢分享

## 回复 by woaiziyou (#78)

*2025-12-26 09:26*

太强了，支持一波～

## 回复 by mb_zzzqbbim (#79)

*2025-12-26 09:29*

1

## 回复 by mb_cbgtaveo (#80)

*2025-12-26 09:35*

6666666

## 回复 by 街道办事处 (#81)

*2025-12-26 09:54*

666

## 回复 by matrump (#82)

*2025-12-26 10:14*

666

## 回复 by fangliangz (#83)

*2025-12-26 10:23*

666

## 回复 by 莱茵 (#84)

*2025-12-26 10:45*

感谢

## 回复 by kingking888 (#85)

*2025-12-26 14:19*

666

## 回复 by Snark (#86)

*2025-12-26 15:12*

1

## 回复 by Migc (#87)

*2025-12-26 15:33*

666666

## 回复 by dsr000 (#88)

*2025-12-26 17:50*

666

## 回复 by mb_dqwgdsem (#89)

*2025-12-26 19:16*

牛

## 回复 by cpannn (#90)

*2025-12-26 21:05*

楼主什么时候出 ai jia mi 的 比如wordscan app 和网 上 国 网 app

## 回复 by AMy_德友 (#91)

*2025-12-27 03:18*

666

## 回复 by mb_qlcfffdd (#92)

*2025-12-27 08:52*

66666666666666666666

## 回复 by 上官兮唐 (#93)

*2025-12-27 13:25*

看看

## 回复 by uniking (#94)

*2025-12-27 14:53*

666

## 回复 by wx_IT_717 (#95)

*2025-12-27 16:27*

666，真是太厉害了

## 回复 by mb_fhshpiln (#96)

*2025-12-27 20:04*

6

## 回复 by 魔童 (#97)

*2025-12-28 10:43*

66666666

## 回复 by mb_weyfdhks (#98)

*2025-12-28 12:50*

666

## 回复 by 烬奇小云 (#99)

*2025-12-28 14:49*

666

## 回复 by Crack999 (#100)

*2025-12-28 16:23*

6666

## 回复 by wx_筟鈈疋 (#101)

*2025-12-28 22:42*

666

## 回复 by l140w4n9 (#102)

*2025-12-29 09:13*

ddddd

## 回复 by mb_rccklaew (#103)

*2025-12-29 16:20*

66666666

## 回复 by Whoami默 (#104)

*2025-12-29 17:44*

6

## 回复 by 司徒废人 (#105)

*2025-12-29 18:06*

icbc10.1.1.1.0版本过了dexhelp的检测后，还有tongdun.so的检测，会提示环境不安全，但是这个so貌似加密了,dump下来比原来的的大了几倍，用sofixer提示has bad ELF magic,这种情况怎么搞

## 回复 by 东方玻璃 (#106)

*2025-12-29 18:20*

error

## 回复 by 东方玻璃 (#107)

*2025-12-29 18:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  司徒废人](https://bbs.kanxue.com/user-641235.htm)
>
>  icbc10.1.1.1.0版本过了dexhelp的检测后，还有tongdun.so的检测，会提示环境不安全，但是这个so貌似加密了,dump下来比原来的的大了几倍，用sofixer提示has bad ...
>
>

hook弹窗,打印堆栈,定位检测类,再hook过掉

## 回复 by 陈文杰真开心 (#108)

*2025-12-29 18:43*

非常感谢东方大佬

## 回复 by 颜如玉qaq (#109)

*2025-12-30 09:06*

666

## 回复 by 0x25519 (#110)

*2025-12-30 10:19*

学习学习

## 回复 by 云觞 (#111)

*2025-12-30 10:31*

666666

## 回复 by mb_dqwgdsem (#112)

*2025-12-30 10:43*

666

## 回复 by fengvmu (#113)

*2025-12-30 11:36*

感谢分享 ![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by wx_无法回头的伪装 (#114)

*2025-12-30 11:41*

666666

## 回复 by passself (#115)

*2025-12-30 15:11*

666

## 回复 by godiand (#116)

*2025-12-30 15:26*

tql 666

## 回复 by git_34874ucupucup8991-lgtm (#117)

*2025-12-30 15:59*

great

## 回复 by 司徒废人 (#118)

*2025-12-30 16:11*

pixel7 android13 貌似vm-trace不太好使，log中没有br非法地址，就结束了

## 回复 by mb_bhsrdtqf (#119)

*2025-12-30 17:43*

666

## 回复 by mb_ykavguun (#120)

*2025-12-30 17:58*

6666

## 回复 by maxfire (#121)

*2025-12-31 16:49*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by xinhu (#122)

*2025-12-31 17:02*

11111111

## 回复 by mb_uvyukvot (#123)

*2025-12-31 18:02*

666

## 回复 by mb_vylvorjm (#124)

*2026-1-1 14:14*

支持一下

## 回复 by mb_emwvcbiq (#125)

*2026-1-3 00:49*

666

## 回复 by Bileton (#126)

*2026-1-3 00:50*

666

## 回复 by Cure. (#127)

*2026-1-3 15:08*

6

## 回复 by Cure. (#128)

*2026-1-3 20:14*

第一个案例现在不行了![image](https://bbs.kanxue.com/view/img/face/055.gif)

## 回复 by xeiyu (#129)

*2026-1-4 00:26*

666

## 回复 by 小尘0000 (#130)

*2026-1-4 16:53*

666

## 回复 by wx_Dispa1r (#131)

*2026-1-4 17:41*

1

## 回复 by birdcard (#132)

*2026-1-5 10:53*

6666666666

## 回复 by 4Chan (#133)

*2026-1-5 11:42*

6666

## 回复 by didiid (#134)

*2026-1-5 16:51*

666

## 回复 by fenfei331 (#135)

*2026-1-6 11:57*

666

## 回复 by 带篮子 (#136)

*2026-1-6 14:07*

66666666666666666

## 回复 by mb_ugnawvja (#137)

*2026-1-7 22:15*

感谢分享![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 青衫不负雪 (#138)

*2026-1-8 23:41*

请教一下，“直接搜索validaddress, 向上交叉引用发现JNI_OnLoad中调用了”，这个validaddress是在IDA里面哪里搜索的？

## 回复 by 青衫不负雪 (#139)

*2026-1-9 11:09*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  青衫不负雪](https://bbs.kanxue.com/user-1020078.htm)
>
>  请教一下，“直接搜索validaddress, 向上交叉引用发现JNI_OnLoad中调用了”，这个validaddress是在IDA里面哪里搜索的？
>
>

找到了，没注意是左侧搜索，不过10号的没找到，我的是12-21号的，左侧搜索之后查找交叉引用直接进入死循环了，没有JNI_OnLoad的调用

## 回复 by iBa0 (#140)

*2026-1-9 14:27*

看看怎么个事

## 回复 by HahApInK (#141)

*2026-1-9 16:30*

666

## 回复 by 木槿any (#142)

*2026-1-9 17:17*

nb666

## 回复 by woainihehe (#143)

*2026-1-9 21:11*

太强了，支持一波～

## 回复 by 飆汗吉米 (#144)

*2026-1-10 07:59*

6666

## 回复 by 小路不迷路 (#145)

*2026-1-10 16:34*

6

## 回复 by pigsub (#146)

*2026-1-11 15:31*

已严肃学习

## 回复 by Kill_Log (#147)

*2026-1-11 16:05*

66666

## 回复 by mb_slviktph (#148)

*2026-1-11 18:04*

666

## 回复 by Viseris (#149)

*2026-1-11 22:32*

66666

## 回复 by mb_dmjhowok (#150)

*2026-1-12 15:46*

是大佬！

## 回复 by lingyi223 (#151)

*2026-1-13 09:14*

6666666666

## 回复 by ookyo (#152)

*2026-1-13 13:04*

感谢分享

## 回复 by 伊苏尔德 (#153)

*2026-1-13 15:19*

666

## 回复 by mb_vmvqwahj (#154)

*2026-1-13 15:47*

666666

## 回复 by mb_hznlyhhf (#155)

*2026-1-14 10:30*

感谢分享，受益匪浅

## 回复 by passwords404 (#156)

*2026-1-14 11:02*

太强了，感谢分享

## 回复 by wx_？_992 (#157)

*2026-1-14 16:33*

666

## 回复 by Arvin.liu (#158)

*2026-1-14 22:59*

66666

## 回复 by mb_enmenpdg (#159)

*2026-1-15 18:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  青衫不负雪](https://bbs.kanxue.com/user-1020078.htm)
>
>  找到了，没注意是左侧搜索，不过10号的没找到，我的是12-21号的，左侧搜索之后查找交叉引用直接进入死循环了，没有JNI_OnLoad的调用
>
>

validAddress应该可以搜到两个函数吧，一个是实际函数，一个是跳转桩，可以继续查跳转桩的交叉引用

## 回复 by LQ6H (#160)

*2026-1-15 18:22*

tql

## 回复 by mb_ysegxpmv (#161)

*2026-1-15 22:09*

太强了

## 回复 by chqi (#162)

*2026-1-16 17:04*

666

## 回复 by 溜溜菜 (#163)

*2026-1-16 17:27*

太强了

## 回复 by mb_hyhfavas (#164)

*2026-1-16 18:54*

支持支持

## 回复 by git_97580helord (#165)

*2026-1-16 19:44*

ciool

## 回复 by mb_weyfdhks (#166)

*2026-1-16 20:14*

666

## 回复 by xxrens (#167)

*2026-1-16 20:46*

tql

## 回复 by mb_evapxmjh (#168)

*2026-1-17 22:37*

66666

## 回复 by wx_HK_888 (#169)

*2026-1-18 01:20*

这个确实厉害，太强了

## 回复 by mb_rewimxhj (#170)

*2026-1-19 07:33*

看看

## 回复 by 3cly (#171)

*2026-1-19 11:15*

1

## 回复 by mb_4nrpVMxJ (#172)

*2026-1-19 14:35*

666

## 回复 by mb_auylfslb (#173)

*2026-1-19 16:15*

666

## 回复 by mb_ysegxpmv (#174)

*2026-1-20 12:44*

希望贴主出一个爱加密新版的，我已经通过你的方式去hook了新线程，但还是terminate了

## 回复 by pingsky (#175)

*2026-1-20 12:53*

666plus

## 回复 by mb_qlbmqqmd (#176)

*2026-1-20 18:10*

666

## 回复 by tjytjy (#177)

*2026-1-20 21:36*

666

## 回复 by pexillove (#178)

*2026-1-21 01:25*

大佬我试了你的那个新版例子icbc，不联网的时候没有问题，但联网后hook报环境不安全，然后过一会儿就退出了

## 回复 by A0tem (#179)

*2026-1-21 13:04*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by 东方玻璃 (#180)

*2026-1-21 13:49*

>
> [pexillove](https://bbs.kanxue.com/user-956077.htm)
>
>  大佬我试了你的那个新版例子icbc，不联网的时候没有问题，但联网后hook报环境不安全，然后过一会儿就退出了
>
>

这是因为风控,定位弹窗组件,打印调用栈hook下检测函数就能绕过![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by mb_ejdcofcz (#181)

*2026-1-21 14:13*

666

## 回复 by ouduomi (#182)

*2026-1-21 14:57*

感谢分享

## 回复 by pexillove (#183)

*2026-1-21 15:02*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  这是因为风控,定位弹窗组件,打印调用栈hook下检测函数就能绕过[em_065]
>
>

是的大佬我就是这么做的![image](https://bbs.kanxue.com/view/img/face/044.gif)

## 回复 by wgetlaidu (#184)

*2026-1-21 16:40*

666

## 回复 by shibaking (#185)

*2026-1-22 12:30*

66666

## 回复 by mb_hfjfruhl (#186)

*2026-1-22 14:05*

666

## 回复 by mb_dmtcuvoh (#187)

*2026-1-22 14:22*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by 独一无二_370133 (#188)

*2026-1-22 15:32*

123123

## 回复 by csyjyy (#189)

*2026-1-22 15:49*

66

## 回复 by 白鹿 (#190)

*2026-1-22 18:01*

感谢分享

## 回复 by euw (#191)

*2026-1-22 18:46*

tql

## 回复 by mb_enmenpdg (#192)

*2026-1-23 10:41*

大佬，我按照文章的方法找了其他的旧版加固复现，前面的结果完全都能对上，但是nop检测线程后还是退出了

## 回复 by owlTest (#193)

*2026-1-23 11:24*

看看到底有

## 回复 by wx_插曲 (#194)

*2026-1-23 14:44*

666

## 回复 by mb_msgksrpq (#195)

*2026-1-23 15:07*

tql，666

## 回复 by 逆向小呆呆 (#196)

*2026-1-26 00:53*

太强了吧

## 回复 by mb_xcxzqumw (#197)

*2026-1-26 07:55*

66666

## 回复 by mb_ijqgkvwm (#198)

*2026-1-26 11:04*

666666

## 回复 by baichisi (#199)

*2026-1-26 14:26*

6666

## 回复 by uni7corn (#200)

*2026-1-26 17:01*

感谢分享，确实不错。值得学习

## 回复 by mb_hbosztvl (#201)

*2026-1-27 20:29*

6666

## 回复 by yyyyy——— (#202)

*2026-1-28 14:47*

666

## 回复 by 墨穹呢 (#203)

*2026-1-28 15:17*

感谢分享

## 回复 by wxtaaaa (#204)

*2026-1-28 17:30*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by xuhe123 (#205)

*2026-1-29 09:35*

666666

## 回复 by 落雪无尘V (#206)

*2026-1-31 11:50*

支持一下啊

## 回复 by 莲花 (#207)

*2026-1-31 12:28*

6666666

## 回复 by mb_mrobgkew (#208)

*2026-2-2 09:53*

6666

## 回复 by mb_oqgsbwvm (#209)

*2026-2-2 23:37*

学习逆向

## 回复 by xkow4dnkw7cusncz (#210)

*2026-2-3 07:16*

学习一下，感谢

## 回复 by mb_gilgovuj (#211)

*2026-2-3 08:39*

666

## 回复 by mb_lrzszndq (#212)

*2026-2-3 20:19*

666

## 回复 by mb_kfrkwwjb (#213)

*2026-2-4 00:32*

666

## 回复 by SparkHolder (#214)

*2026-2-5 10:49*

6666

## 回复 by mb_zuiylqkn (#215)

*2026-2-5 13:07*

666

## 回复 by mb_iyeoluxk (#216)

*2026-2-5 13:23*

666

## 回复 by mb_rrwegvyc (#217)

*2026-2-5 17:29*

6666

## 回复 by puppet_w (#218)

*2026-2-5 19:02*

牛牛牛

## 回复 by mb_urvhdxxp (#219)

*2026-2-7 16:25*

666

## 回复 by hanjiefang (#220)

*2026-2-9 16:46*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_kxikBxpy (#221)

*2026-2-11 18:24*

6666

## 回复 by 九黎 (#222)

*2026-2-12 11:48*

666

## 回复 by mb_naasfhhh (#223)

*2026-2-13 13:04*

666666

## 回复 by mb_deisgjrb (#224)

*2026-2-15 16:42*

1

## 回复 by mb_iftcqehs (#225)

*2026-2-16 21:20*

感谢分享

## 回复 by Mr.ghost (#226)

*2026-2-17 11:55*

666

## 回复 by 夜微凉的流伤 (#227)

*2026-2-21 23:31*

666

## 回复 by 一酷一酷 (#228)

*2026-2-24 03:24*

66666

## 回复 by Noguess9 (#229)

*2026-2-24 15:29*

66

## 回复 by xiaoc996 (#230)

*2026-2-25 15:20*

66

## 回复 by mb_zvzuwqdn (#231)

*2026-2-26 16:34*

6666

## 回复 by amwait (#232)

*2026-2-27 14:13*

111

## 回复 by mb_jdstnsbm (#233)

*2026-2-27 15:07*

666

## 回复 by codming (#234)

*2026-2-28 13:51*

6666，感谢

## 回复 by @NoBody (#235)

*2026-2-28 16:15*

你好，我自己做了一个二进制静态动态结合的创新的方案(我研究过学术界关于二进制跟踪的很多论文)，可以记录ios程序起始到结束堆内存读写和函数调用(普通的类似stalker的方法太慢了是无法实现的)，速度只减少50%。不过最近不做逆向了，有需要的朋友我可以出这套系统找10个人每个人500块。WX:jiqizaisikao

## 回复 by mb_oaufhyol (#236)

*2026-2-28 16:25*

nb

## 回复 by GX552 (#237)

*2026-3-1 13:19*

59999999999

## 回复 by jyotidwi (#238)

*2026-3-1 13:35*

666

## 回复 by git_26260defidead (#239)

*2026-3-4 15:32*

66666

## 回复 by k26 (#240)

*2026-3-4 22:06*

学习了

## 回复 by heting0 (#241)

*2026-3-4 22:47*

99999966666

## 回复 by taoying (#242)

*2026-3-5 10:48*

6

## 回复 by win柠初 (#243)

*2026-3-5 11:33*

真的牛逼卧槽

## 回复 by 林懋 (#244)

*2026-3-5 15:28*

6

## 回复 by 土豆爱学习 (#245)

*2026-3-5 20:33*

666

## 回复 by 东方玻璃 (#246)

*2026-3-5 21:04*

>
> [土豆爱学习](https://bbs.kanxue.com/user-988857.htm)
>  666
>

clone有检测libc, florida才能复现, 文章开头有说明, 这是写文章时的失误, 江西银行当时是旧版本, 现在可能有更新

## 回复 by 土豆爱学习 (#247)

*2026-3-5 21:08*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  clone有检测libc, florida才能复现, 文章开头有说明, 这是写文章时的失误, 江西银行当时是旧版本, 现在可能有更新
>
>

666

## 回复 by 东方玻璃 (#248)

*2026-3-5 21:33*

>
> [土豆爱学习](https://bbs.kanxue.com/user-988857.htm)
>
>
>
>
>
>
>  东方玻璃
>
>
>
>  clone有检测libc, florida才能复现, 文章开头有说明, 这是写文章时的失误, 江西银行当时是旧版本, 现在可能有 ...
>

样本直接发你吧
链接: https://pan.baidu.com/s/1vzUxfUOAdwzFud0F_auwmA?pwd=pc77 提取码: pc77

## 回复 by MaxPotato (#249)

*2026-3-6 10:41*

6666666

## 回复 by mb_fglogyec (#250)

*2026-3-6 21:34*

666

## 回复 by qig (#251)

*2026-3-7 13:43*

严肃学习

## 回复 by mb_sqetvntx (#252)

*2026-3-7 16:50*

xx

## 回复 by wx_西门浪 (#253)

*2026-3-7 21:07*

6666

## 回复 by mb_joablzkk (#254)

*2026-3-7 21:35*

666

## 回复 by mb_ysikfhxt (#255)

*2026-3-8 17:48*

1

## 回复 by 土豆爱学习 (#256)

*2026-3-9 10:58*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  样本直接发你吧
> 链接: https://pan.baidu.com/s/1vzUxfUOAdwzFud0F_auwmA?pwd=pc77 提取码: pc77
>
>

感谢大佬，今天刚看到消息，过期了，能不能再发一下![image](https://bbs.kanxue.com/view/img/face/092.gif)

## 回复 by 东方玻璃 (#257)

*2026-3-9 13:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  土豆爱学习](https://bbs.kanxue.com/user-988857.htm)
>
>  感谢大佬，今天刚看到消息，过期了，能不能再发一下[em_092]
>
>

链接: https://pan.baidu.com/s/14QTq8RFXX7BNi2eajgpqZQ?pwd=vape 提取码: vape

## 回复 by 土豆爱学习 (#258)

*2026-3-9 13:45*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  链接: https://pan.baidu.com/s/14QTq8RFXX7BNi2eajgpqZQ?pwd=vape 提取码: vape
>
>

谢谢![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 土豆爱学习 (#259)

*2026-3-9 16:02*

已经解决

## 回复 by 猪肉炖粉条lr (#260)

*2026-3-9 21:13*

666

## 回复 by git_14248bibinocode (#261)

*2026-3-10 00:21*

6666

## 回复 by 土豆爱学习 (#262)

*2026-3-10 14:46*

666

## 回复 by 土豆爱学习 (#263)

*2026-3-10 15:03*

6

## 回复 by 东方玻璃 (#264)

*2026-3-10 19:07*

>
> [土豆爱学习](https://bbs.kanxue.com/user-988857.htm)
>  6
>

大概率设备问题,我是android10

## 回复 by 东方玻璃 (#265)

*2026-3-10 19:08*

>
> [土豆爱学习](https://bbs.kanxue.com/user-988857.htm)
>  666
>

我文章里说了,最开始stalker定位不到,改用vmtrace才定位到,stalker和设备环境也有关系,而且脚本差一个函数结果都不一样,比如多或者少hook了某个函数

## 回复 by 东方玻璃 (#266)

*2026-3-10 19:11*

另外这种恰好在检测点附近崩溃的情况确实难得,因为构造内存访问错直接kill,最新版的已经trace不到了,而且还有反trace检测

## 回复 by mb_lyqehpis (#267)

*2026-3-10 20:42*

学到了大佬

## 回复 by 土豆爱学习 (#268)

*2026-3-11 10:44*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  另外这种恰好在检测点附近崩溃的情况确实难得,因为构造内存访问错直接kill,最新版的已经trace不到了,而且还有反trace检测
>
>

谢谢大佬回复我，我用你给我的工商app，使用vmtrace依然没有定位到，可不可以告诉我，你的PC是哪个还有系统版本是哪个，手机是安卓模拟器还是真机，我想完全模仿你的环境，再尝试一下

## 回复 by 东方玻璃 (#269)

*2026-3-11 13:31*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  土豆爱学习](https://bbs.kanxue.com/user-988857.htm)
>
>  谢谢大佬回复我，我用你给我的工商app，使用vmtrace依然没有定位到，可不可以告诉我，你的PC是哪个还有系统版本是哪个，手机是安卓模拟器还是真机，我想完全模仿你的环境，再尝试一下
>
>

R7000P 2021款,Windows10, Pixel 3XL Android10, Pixel 6a,Android14,全真机无模拟器

## 回复 by 土豆爱学习 (#270)

*2026-3-11 13:41*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  R7000P 2021款,Windows10, Pixel 3XL Android10, Pixel 6a,Android14,全真机无模拟器
>
>

万分感谢![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 土豆爱学习 (#271)

*2026-3-11 19:56*

6

## 回复 by 东方玻璃 (#272)

*2026-3-11 20:32*

>
> [土豆爱学习](https://bbs.kanxue.com/user-988857.htm)
>  6
>

感谢支持,期待红薯相关文章,trace工具可以考虑深入学stalker和qbdi

## 回复 by 土豆爱学习 (#273)

*2026-3-11 20:43*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  感谢支持,期待红薯相关文章,trace工具可以考虑深入学stalker和qbdi
>
>

谢谢大佬指点![image](https://bbs.kanxue.com/view/img/face/089.gif)

## 回复 by mb_ttdxmirg (#274)

*2026-3-12 00:19*

66666

## 回复 by lamorm (#275)

*2026-3-12 14:37*

666666

## 回复 by 残枫 (#276)

*2026-3-13 09:00*

学习

## 回复 by mb_adlxcbkt (#277)

*2026-3-13 10:27*

666

## 回复 by mb_fbijwlgg (#278)

*2026-3-13 10:56*

66

## 回复 by wx_荼风 (#279)

*2026-3-13 11:27*

太厉害了!!

## 回复 by mb_jnkpzfyq (#280)

*2026-3-14 01:43*

支持大佬

## 回复 by mb_ugryjzdr (#281)

*2026-3-16 17:04*

6666

## 回复 by mb_gqtfyqhu (#282)

*2026-3-17 23:12*

厉害了

## 回复 by 陳學城 (#283)

*2026-3-18 10:36*

1

## 回复 by mb_atwurgje (#284)

*2026-3-20 10:45*

6

## 回复 by tonykros (#285)

*2026-3-21 21:38*

6666

## 回复 by mb_criqjxad (#286)

*2026-3-21 22:24*

666

## 回复 by artake (#287)

*2026-3-23 09:35*

膜拜大佬

## 回复 by 费小会 (#288)

*2026-3-25 19:00*

6666

## 回复 by qqqiu (#289)

*2026-3-25 19:38*

1

## 回复 by Matchman33 (#290)

*2026-3-27 17:32*

6666

## 回复 by mb_igkkxzil (#291)

*2026-3-28 00:28*

66666666

## 回复 by lackone (#292)

*2026-3-28 13:15*

66666

## 回复 by mb_blhyvqfj (#293)

*2026-3-28 22:10*

感谢分享

## 回复 by 芙兰朵布丁 (#294)

*2026-3-29 01:35*

6666

## 回复 by mb_yxcltfyb (#295)

*2026-3-29 03:18*

太牛了

## 回复 by mb_ivheaebz (#296)

*2026-3-29 17:57*

厉害

## 回复 by mb_gatolgsc (#297)

*2026-3-30 02:20*

6666

## 回复 by mb_dmryuxbw (#298)

*2026-3-30 08:49*

感谢分享

## 回复 by 呆萌的小白 (#299)

*2026-3-30 09:35*

收藏了,学习学习

## 回复 by xifgg (#300)

*2026-3-30 10:05*

666

## 回复 by mb_pheahdjz (#301)

*2026-3-30 12:06*

666

## 回复 by 吃饭去2 (#302)

*2026-3-30 16:28*

666

## 回复 by mb_bmkfgrxv (#303)

*2026-3-31 00:15*

感谢分享

## 回复 by mb_evlxbmwv (#304)

*2026-3-31 21:04*

666666

## 回复 by mb_xwexdtil (#305)

*2026-4-2 12:50*

6666666

## 回复 by 自由的翅膀 (#306)

*2026-4-3 10:26*

感谢大佬分享

## 回复 by 小迷糊ddd (#307)

*2026-4-7 09:16*

感谢分享，学习一下。

## 回复 by Gryffindoss (#308)

*2026-4-7 22:18*

666

## 回复 by mb_uktygsmq (#309)

*2026-4-9 17:34*

666

## 回复 by 一栋奥特曼 (#310)

*2026-4-10 01:37*

6666

## 回复 by 秃顶 (#311)

*2026-4-10 09:37*

感谢分享

## 回复 by APlus (#312)

*2026-4-10 14:29*

6

## 回复 by 啥也不会2 (#313)

*2026-4-10 14:46*

6666666666

## 回复 by mb_mxsesokv (#314)

*2026-4-12 04:27*

6666

## 回复 by 乌鸡哥 (#315)

*2026-4-12 18:30*

6666

## 回复 by B.M.K (#316)

*2026-4-12 18:54*

666

## 回复 by mb_qnsuegcb (#317)

*2026-4-13 17:59*

666

## 回复 by mb_qszrihil (#318)

*2026-4-15 17:50*

666

## 回复 by mb_lojlzfoa (#319)

*2026-4-15 17:50*

666

## 回复 by wx_窒息 (#320)

*2026-4-19 14:26*

666

## 回复 by mb_uohfzjqw (#321)

*2026-4-23 13:04*

666

## 回复 by mb_rtyzyhmr (#322)

*2026-4-23 15:33*

6666

## 回复 by 里予 (#323)

*2026-4-23 17:49*

666

## 回复 by wx_coddvccwyh (#324)

*2026-4-23 22:03*

66666

## 回复 by mb_stdlrcgp (#325)

*2026-4-27 20:45*

666

## 回复 by git_86585flowclouds (#326)

*2026-4-30 14:13*

感谢分享

## 回复 by mb_twbjvgyf (#327)

*2026-5-3 19:55*

1

## 回复 by mb_dsvrufqa (#328)

*2026-5-6 12:03*

6666

## 回复 by mb_lzotvdxv (#329)

*2026-5-10 00:27*

请在 Telegram 上联系我，有个重要的 2000 美元任务。
 Telegram：@dlopenext

## 回复 by 洋少QQ (#330)

*2026-5-11 11:39*

6666

## 回复 by mb_wckjnnha (#331)

*2026-5-12 11:06*

感谢分享

## 回复 by 风的晚安 (#332)

*2026-5-14 17:01*

66666

## 回复 by mb_halkmcvq (#333)

*2026-5-19 14:10*

66

## 回复 by wx_完美 (#334)

*2026-5-22 11:13*

感谢分享

## 回复 by wx_黑色柳丁 (#335)

*2026-5-22 19:43*

这个讨论对我很有帮助，谢谢！

## 回复 by mb_rirvdrlh (#336)

*2026-5-23 01:02*

666666

## 回复 by Himly (#337)

*2026-5-24 15:54*

牛逼

## 回复 by 简单的简单 (#338)

*2026-5-24 23:41*

666

## 回复 by mb_ehjovrwo (#339)

*2026-5-24 23:51*

感谢分享

## 回复 by wx_coddvccwyh (#340)

*2026-5-27 00:25*

dump后的icbc so文件trace会失败，有人知道是什么情况吗？ ![图片描述](https://bbs.kanxue.com/upload/attach/202605/992780_PUZFM4D727N2TTQ.webp)

## 回复 by 天路 (#341)

*2026-6-3 00:37*

1

## 回复 by 末日大哥 (#342)

*2026-6-4 19:30*

666学习一下

## 回复 by 祝今朝 (#343)

*2026-6-7 23:38*

666

## 回复 by yangshuang (#344)

*2026-6-16 10:47*

6666

## 回复 by mb_tdijwbiu (#345)

*2026-7-2 13:41*

66

## 回复 by wanderdeng (#346)

*2026-7-2 19:17*

很厉害啊啊啊啊啊啊啊啊啊啊啊

## 回复 by mb_vdakxenl (#347)

*2026-7-6 17:29*

牛逼

## 回复 by SamPoson (#348)

*2026-7-7 19:21*

666

## 回复 by 逆向小龙 (#349)

*2026-7-13 14:59*

666666

## 回复 by l1s00t (#350)

*2026-7-14 10:53*

tql![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 你的忠实粉丝 (#351)

*2026-7-16 02:46*

![image](https://bbs.kanxue.com/view/img/face/026.gif)支持

## 回复 by mb_afrensag (#352)

*2026-7-17 15:35*

666

## 回复 by Vengeance (#353)

*2026-7-17 16:12*

6666666

## 回复 by mb_mnqaubnh (#354)

*2026-7-18 14:16*

66![image](https://bbs.kanxue.com/view/img/face/002.gif)

## 回复 by mb_nlygxmzo (#355)

*2026-7-19 22:11*

66666

## 回复 by mb_nlygxmzo (#356)

*2026-7-19 22:11*

谢谢分享666

## 回复 by v5w7crq3 (#357)

666

## 回复 by 我不是QI (#358)

非常好

## 回复 by scllqk (#359)

太牛了

## 回复 by mb_jhohnbzu (#360)

666
