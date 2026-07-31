---
title: '[原创]从Java到Native，so中的函数是如何一步步被加载的？'
url: https://bbs.kanxue.com/thread-285950.htm
tid: 285950
author: xianyuuuan
date: '2025-03-10'
tags: [Android安全, 原创, 基础理论, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:13:00+08:00'
replies: 1
---

---

>
> so？what can i do?
>
>
>

## 0.一个so的加载流程

![image](https://bbs.kanxue.com/upload/attach/202503/1002959_TRKEFSNG6T2ZC8E.png)

首先在java层肯定是要去调用so层文件,本篇重点讲解native层的加载流程，此处不再赘述。

## 1.了解dlopen函数/android_dlopen_ext()

 ***“Dynamic Link”*** 动态装载库，我们会想到windows系统中，存在加载dll文件的动态加载类型，在linux中，类似的文件就是`.so`文件了，而加载文件的重要函数就是`dlopen`。

---

### dlopen系列函数

dlopen：该函数将打开一个新库，并把它装入内存。该函数主要用来加载库中的符号，这些符号在编译的时候是不知道的。这种机制使得在系统中添加或者删除一个模块时，都不需要重新进行编译。

函数原型

| 1 | `void` `*dlopen(``const` `char` `*filename,` `int` `flag);` |
|-|-|

第一个参数是头文件所在的文件名，也就是so文件，第二个标志参数有很多，例如有`RTLD_NOW`和`RTLD_LAZY`立即计算和需要时计算，以及`RTLD_GLOBAL`使得那些在以后才加载的库可以获得其中的符号。方式就是dlopen返回的句柄作为dlsym()的第一个参数，获取符号在库中的地址。

### android_dlopen_ext()函数

此函数作为安卓平台上特有的函数 是dlopen函数的拓展版本，进一步增强了dlopen函数的功能

函数原型

| 1 | `void``* android_dlopen_ext(``const` `char``* path,` `int` `flag,` `const` `void``* ext_data);` |
|-|-|

可以看到在原函数基础上增加了ext_data参数

参照源码可以大致了解增强的功能，其中大部分功能与第二个参数flag中的一些功能标志位相关联

| 1234567891011121314151617181920 | `typedef` `struct` `{``/** A bitmask of `ANDROID_DLEXT_` enum values. */``uint64_t flags;` `/** Used by `ANDROID_DLEXT_RESERVED_ADDRESS` and `ANDROID_DLEXT_RESERVED_ADDRESS_HINT`. */``void``*   _Nullable reserved_addr;``/** Used by `ANDROID_DLEXT_RESERVED_ADDRESS` and `ANDROID_DLEXT_RESERVED_ADDRESS_HINT`. */``size_t`  `reserved_size;` `/** Used by `ANDROID_DLEXT_WRITE_RELRO` and `ANDROID_DLEXT_USE_RELRO`. */``int`     `relro_fd;` `/** Used by `ANDROID_DLEXT_USE_LIBRARY_FD`. */``int`     `library_fd;``/** Used by `ANDROID_DLEXT_USE_LIBRARY_FD_OFFSET` */``off64_t library_fd_offset;` `/** Used by `ANDROID_DLEXT_USE_NAMESPACE`. */``struct` `android_namespace_t* _Nullable library_namespace;``} android_dlextinfo;` |
|-|-|

### dlopen函数后的流程

![image](https://bbs.kanxue.com/upload/attach/202503/1002959_8XZE82QS7N6V2VC.png)

## 2.do_dlopen 函数

>
> 此版本为安卓4源码分析，最新版本的安卓号的加载流程在代码量上有进一步的提升，但是基础原理类似。
>
>
>

上面的dlopen函数只是一个引子，真正的核心功能代码实现在do_dlopen函数中

| 1234567891011121314151617181920212223242526 | `void``* dlopen(``const` `char``* filename,` `int` `flags) {``ScopedPthreadMutexLocker locker(&gDlMutex);``soinfo* result = do_dlopen(filename, flags);``if` `(result == NULL) {``__bionic_format_dlerror(``"dlopen failed"``, linker_get_error_buffer());``return` `NULL;``}``return` `result;``}` `soinfo* do_dlopen(``const` `char``* name,` `int` `flags) {``//判断传入标志的类型``if` `((flags & ~(RTLD_NOW\|RTLD_LAZY\|RTLD_LOCAL\|RTLD_GLOBAL)) != 0) {``DL_ERR(``"invalid flags to dlopen: %x"``, flags);``return` `NULL;``}``//内存保护权限设置 此处为可读可写，目的是在加载find_library函数后可以对soinfo结构体的内容进行修改``set_soinfo_pool_protection(PROT_READ \| PROT_WRITE);``soinfo* si = find_library(name);` `//这里返回了so信息链``if` `(si != NULL) {``si->CallConstructors();` `//这里执行了此构造方法``}``//在这里就没有可写权限了``set_soinfo_pool_protection(PROT_READ);``return` `si;``}` |
|-|-|

此函数的类型为`soinfo`指针，`soinfo`代表的含义是“进程加载的so链”，其中包含了已经被加载的so 的信息。这里所返回的值也是si——进程加载的so链。

其中涉及的主要两步函数为`find_library`和`CallConstructor`下面会继续介绍。

## 3.find_library函数

find_library函数传入参数后也会进行进一步的函数调用，流程见注释

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465 | `static` `soinfo *find_loaded_library(``const` `char` `*name)``{``soinfo *si;``const` `char` `*bname;` `// TODO: don't use basename only for determining libraries``// http://code.google.com/p/android/issues/detail?id=6670` `bname =` `strrchr``(name,` `'/'``);` `//分割so文件的名称``bname = bname ? bname + 1 : name;` `for` `(si = solist; si != NULL; si = si->next) {``//递归查找是否存在so文件名称``if` `(!``strcmp``(bname, si->name)) {``return` `si;``}``}``return` `NULL;``}` `static` `soinfo* find_library_internal(``const` `char``* name) {``if` `(name == NULL) {``return` `somain;` `//返回共享库``}` `soinfo* si = find_loaded_library(name);``if` `(si != NULL) {``if` `(si->flags & FLAG_LINKED) {``// 前者检查是否有flag标志字段，后者检查是否被链接``return` `si;` `//如果被链接就直接加载``}``DL_ERR(``"OOPS: recursive link to \"%s\""``, si->name);``//报错递归链接错误。``//【递归链接：在动态库的加载过程中，如果同一个库被多次请求加载，可能会发生递归链接。通常这是不希望发生的情况，因为这会导致循环依赖或重复加载的错误。】``return` `NULL;``}` `TRACE(``"[ '%s' has not been loaded yet.  Locating...]"``, name);``//发现未被加载后会通过load_library重新加载``si = load_library(name);` `//load_library的函数在下面介绍``if` `(si == NULL) {` `//如果再次加载仍为null 则返回null``return` `NULL;``}` `// At this point we know that whatever is loaded @ base is a valid ELF``// shared library whose segments are properly mapped in.``//返回了基址，大小和名称``TRACE(``"[ init_library base=0x%08x sz=0x%08x name='%s' ]"``,``si->base, si->size, si->name);` `//通过此函数``if` `(!soinfo_link_image(si)) {``//此函数实现了动态链接库中section信息解析。``munmap(``reinterpret_cast``<``void``*>(si->base), si->size);``soinfo_free(si);``return` `NULL;``}` `return` `si;``}` `static` `soinfo* find_library(``const` `char``* name) {``soinfo* si = find_library_internal(name);``if` `(si != NULL) {``si->ref_count++;``}``return` `si;``}` |
|-|-|

### load_library()函数加载【待补充】

涉及知识点：elf文件格式，文件分区的加载

## 4.call_constructors 函数

此函数根据上面的soinfo链接映像函数分析的section动态节区中的信息，获取共享库依赖的所有的so文件名，所有的依赖库初始化完成后，执行init_func、init_array方法初始化该动态库。

| 1234567891011121314151617181920212223242526272829303132333435363738394041 | `void` `soinfo::CallConstructors() {``if` `(constructors_called) {``return``;``}` `// We set constructors_called before actually calling the constructors, otherwise it doesn't``// protect against recursive constructor calls. One simple example of constructor recursion``// is the libc debug malloc, which is implemented in libc_malloc_debug_leak.so:``// 1. The program depends on libc, so libc's constructor is called here.``// 2. The libc constructor calls dlopen() to load libc_malloc_debug_leak.so.``// 3. dlopen() calls the constructors on the newly created``//    soinfo for libc_malloc_debug_leak.so.``// 4. The debug .so depends on libc, so CallConstructors is``//    called again with the libc soinfo. If it doesn't trigger the early-``//    out above, the libc constructor will be called again (recursively!).``constructors_called =` `true``;` `if` `((flags & FLAG_EXE) == 0 && preinit_array != NULL) {``// The GNU dynamic linker silently ignores these, but we warn the developer.``PRINT(``"\"%s\": ignoring %d-entry DT_PREINIT_ARRAY in shared library!"``,``name, preinit_array_count);``}` `//确保库已被初始化加载``if` `(dynamic != NULL) {``for` `(Elf32_Dyn* d = dynamic; d->d_tag != DT_NULL; ++d) {``if` `(d->d_tag == DT_NEEDED) {``const` `char``* library_name = strtab + d->d_un.d_val;``TRACE(``"\"%s\": calling constructors in DT_NEEDED \"%s\""``, name, library_name);``find_loaded_library(library_name)->CallConstructors();``}``}``}` `TRACE(``"\"%s\": calling constructors"``, name);` `//最后进行初始化函数的执行``// DT_INIT should be called before DT_INIT_ARRAY if both are present.``CallFunction(``"DT_INIT"``, init_func);``CallArray(``"DT_INIT_ARRAY"``, init_array, init_array_count,` `false``);``}` |
|-|-|

## 5.init 和 init_array函数

### 函数简介

这两个函数是so文件在被加载或者卸载时自动执行的函数，用于初始化的操作，其中init函数优先于init_array函数。作为so层加载很早的函数，可以通过实现hook他来绕过一些关键的检测点。

也正是因为加载过早且初始化后只加载一次，我们如果直接去hook是无法get到的，通过上面的流程我们知道了这两个函数是在call_constructors中进行加载，我们就可以通过逆向hook相关的native函数进行加载hook。通过在`android_dlopen_ext`加载过程中进行hook操作。

### 关键突破口

这里有一步很关键的操作，关于call_constructors 函数，`call_constructors` 是在共享库加载时被调用的函数。意思就是他是存储在安卓本机中的本地链接库函数，而他的位置文件具体就在`/system/bin/linker64`中，我们将他从手机上pull下来进行反编译并查找相关函数可以看到。

![image](https://bbs.kanxue.com/upload/attach/202503/1002959_WDY2V9P357T4KA2.png)

![image](https://bbs.kanxue.com/upload/attach/202503/1002959_NBQ9Y93BQV9JFK4.png)

反编译的结果与我们上文看到的函数功能接近。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071 | `__int64` `__fastcall _dl__ZN6soinfo17call_constructorsEv(``__int64` `result)``{``char` `v1;` `// w8``__int64` `v2;` `// x19``const` `char` `*v3;` `// x2``_QWORD *i;` `// x20``__int64` `v5;` `// x1``__int64` `v6;` `// x0``__int64` `v7;` `// x8``char` `*v8;` `// x0``__int64` `v9;` `// x2``__int64` `v10;` `// x3``char` `v11[16];` `// [xsp+8h] [xbp-38h] BYREF``__int64` `v12;` `// [xsp+18h] [xbp-28h]``__int128 v13;` `// [xsp+20h] [xbp-20h] BYREF``char` `*v14;` `// [xsp+30h] [xbp-10h]` `if` `( !(_dl_g_is_ldd \| *(result + 248)) )``{``v1 = *(result + 48);``v2 = result;``*(result + 248) = 1;``if` `( (v1 & 4) == 0 && *(result + 136) && (_dl_g_ld_debug_verbosity & 0x80000000) == 0 )``{``if` `( (*(result + 432) & 1) != 0 )``v3 = *(result + 448);``else``v3 = (result + 433);``_dl__Z10linker_logiPKcz(0xFFFFFFFFLL,` `"\"%s\": ignoring DT_PREINIT_ARRAY in shared library!"``, v3);``}``for` `( i = *(v2 + 288); i; i = *i )``_dl__ZN6soinfo17call_constructorsEv(i[1]);``if` `( (*(v2 + 48) & 0x10) == 0 )``{``_dl__ZNSt3__112basic_stringIcNS_11char_traitsIcEENS_9allocatorIcEEEC2IDnEEPKc(v11,` `"calling constructors: "``);``if` `( (*(v2 + 432) & 1) != 0 )``v5 = *(v2 + 448);``else``v5 = v2 + 433;``v6 = _dl__ZNSt3__112basic_stringIcNS_11char_traitsIcEENS_9allocatorIcEEE6appendEPKc(v11, v5);``v7 = *(v6 + 16);``v13 = *v6;``v14 = v7;``*(v6 + 8) = 0LL;``*(v6 + 16) = 0LL;``*v6 = 0LL;``if` `( (v13 & 1) != 0 )``v8 = v14;``else``v8 = &v13 + 1;``_dl__Z18bionic_trace_beginPKc(v8);``if` `( (v13 & 1) != 0 )``_dl__ZdlPv(v14);``if` `( (v11[0] & 1) != 0 )``_dl__ZdlPv(v12);``}``if` `( (*(v2 + 432) & 1) != 0 )``v9 = *(v2 + 448);``else``v9 = v2 + 433;``_dl__ZL13call_functionPKcPFviPPcS2_ES0_(``"DT_INIT"``, *(v2 + 184), v9);``if` `( (*(v2 + 432) & 1) != 0 )``v10 = *(v2 + 448);``else``v10 = v2 + 433;``result = _dl__ZL10call_arrayIPFviPPcS1_EEvPKcPT_mbS5_(``"DT_INIT_ARRAY"``, *(v2 + 152), *(v2 + 160), v10);``if` `( (*(v2 + 48) & 0x10) == 0 )``return` `_dl__Z16bionic_trace_endv(result);``}``return` `result;``}` |
|-|-|

### hook init/init_array思路

通过hook`android_dlopen_ext`定位我们要hook的so文件，通过hook `linker64`中的 `call_constructors`函数可以修改init和init_array的流程。

这里需要注意的是关于偏移地址的查找，可以通过pie，ida等工具 或者在linux环境中执行命令

| 1234 | `$ readelf -d lib52pojie.so \|` `grep` `INIT``0x000000000000000c (INIT)               0x12edc``0x0000000000000019 (INIT_ARRAY)         0x39b50``0x000000000000001b (INIT_ARRAYSZ)       8 (bytes)` |
|-|-|

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859 | `var` `hooked =` `false``;``function` `hook_call_constructor(soName){``console.log(``"hook_call_constructor ->"``,soName)``var` `symbols = Process.getModuleByName(``"linker64"``).enumerateSymbols();``var` `callConstructorAdd =` `null``;``//暂时先空置此地址``for``(``var` `index = 0;index < symbols.length;index++){``const symbol = symbols[index];``if``(symbol.name.indexOf(``"__dl__ZN6soinfo17call_constructorsEv"``) != -1){``callConstructorAdd = symbol.address;``}``}` `console.log(``"call_constructors的地址为："``+ callConstructorAdd);` `var` `isHooked =` `false``;``Interceptor.attach(callConstructorAdd,{``onEnter:` `function``(agrs){``if``(!isHooked){``hook_init(soName);``hook_init_array(soName);``isHooked =` `true``}``},``onLeave:` `function``(retval){` `}``});``}` `function` `hook_init(soName){``if``(!hooked){``console.log(``"hook_init -> "``,soName);``var` `targetSoAddr = Module.findBaseAddress(soName);``var` `init_proc_addr = targetSoAddr.add(0x12edc);``Interceptor.replace(init_proc_addr,``new` `NativeCallback(``function``(){``console.log(``"init_proc 已hook"``);` `},``'void'``,[]));` `}``}` `function` `hook_init_array(soName){``if``(!hooked){``console.log(``"hook_init_array ->"``,soName);``var` `targetSoAddr = Module.findBaseAddress(soName);``var` `init_array = targetSoAddr.add(0x12F38);``Interceptor.replace(init_array ,` `new` `NativeCallback(``function``(){``console.log(``"init_array已hook"``);``},``'void'``,[]));``//hooked = true ;` `}``}` `function` `main(){``hook_dlopen();``}` `setImmediate(main);` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202503/1002959_AWH492HNJXWZS2Z.png)

## 6.JNI注册方法流程

### 理解静态注册与动态注册

#### 静态注册

>
> 通过 JNIEXPORT 和 JNICALL 两个宏定义声明，在虚拟机加载 so 时发现上面两个宏定义的函数时就会链接到对应的 native 方法。
>
>
>

#### 动态注册

>
> 通过 RegisterNatives 方法手动完成 native 方法和 so 中的方法的绑定，这样虚拟机就可以通过这个函数映射表直接找到相应的方法了。
>
>
>

流程如下。

![image](https://bbs.kanxue.com/upload/attach/202503/1002959_5UGPNEH5HZXX52U.png)

通过`RegisterNatives(JNI *env ,jclass clazz ,const JNINativeMethord *methord ,jint nmethods)`函数，参数分别代表：java环境，java类的描述符，待注册的方法集合，待注册方法数量。

其中“待注册方法集合”是名为`JNINativeMethord`的结构体，内容如下

| 12345 | `typedef` `struct` `{``const` `char``* name;` `// native方法名``const` `char``* signature;` `// 方法签名，例如()Ljava/lang/String;``void``*       fnPtr;` `// 函数指针``} JNINativeMethod;` |
|-|-|

这里的第二个参数为方法签名需要注意，类型为字符串，由一对小括号和若干签名符号组成，其中括号内写传入参数的签名符号，没有参数则不写，括号外写返回参数的签名符号。

| 签名符号 | C/C++ | java |
|-|-|-|
| V | void | void |
| Z | jboolean | boolean |
| I | jint | int |
| J | jlong | long |
| D | jdouble | double |
| F | jfloat | float |
| B | jbyte | byte |
| C | jchar | char |
| S | jshort | short |
| [Z | jbooleanArray | boolean[] |
| [I | jintArray | int[] |
| [J | jlongArray | long[] |
| [D | jdoubleArray | double[] |
| [F | jfloatArray | float[] |
| [B | jbyteArray | byte[] |
| [C | jcharArray | char[] |
| [S | jshortArray | short[] |
| L+完整包名+类名 | jobject | class |

实例：Java层函数`String getText(int a,byte[] b)`就是`(I[B)Ljava/lang/String;`

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849 | `#include <jni.h>``#include <string>` `std::string stringFromJNI(``JNIEnv* env,``jobject` `/* this */``) {``std::string hello =` `"Hello from C++"``;``//env->FindClass()` `return` `reinterpret_cast``<``const` `char` `*>(env->NewStringUTF(hello.c_str()));``}` `std::string myFunc(JNIEnv *env, jobject thiz, jint i_param) {``// TODO: implement myFunc()` `std::string retValue=``"input value is :===> "``;``std::string temp;` `temp=std::to_string(i_param);``retValue+=temp;``return` `reinterpret_cast``<``const` `char` `*>(env->NewStringUTF(retValue.c_str()));``}` `JNINativeMethod methods ={``{``"stringFromJNI"``,``"()Ljava/lang/String;"``,(``void``*)stringFromJNI},``{``"myFunc"``,``"(I)Ljava/lang/String;"``,(``void``*)f1}``//` `};` `jint JNI_OnLoad(JavaVM* vm,``void``* reserved){``JNIEnv *env=NULL;``if``(vm->GetEnv((``void``**)&env,JNI_VERSION_1_6)!=JNI_OK){``return` `JNI_ERR;``}` `jclass clazz = env->FindClass(``"com/example/myapplicationndk/MainActivity"``);``if``(clazz==NULL){``return`  `JNI_ERR;``}``jint iMethod=``sizeof``(methods)/` `sizeof``(methods[0]);` `//计算方法的数量` `jint result=env->RegisterNatives(clazz,methods,iMethod);` `if``(result<0){``return` `JNI_ERR;``}` `return` `JNI_VERSION_1_6;``}` |
|-|-|

可以看出，在动态加载的过程中，很关键的方法就是流程图中的`RegisterNatives`在这其中的参数有很多设置方法名的敏感信息。

### 通过hook查看动态注册

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162 | `function` `find_RegisterNatives(params) {``// 在 libart.so 库中枚举所有符号（函数、变量等）``let symbols = Module.enumerateSymbolsSync(``"libart.so"``);` `let addrRegisterNatives =` `null``;` `// 用于存储 RegisterNatives 方法的地址` `// 遍历所有符号来查找 RegisterNatives 方法``for` `(let i = 0; i < symbols.length; i++) {``let symbol = symbols[i];` `// 当前遍历到的符号` `// 检查符号名称是否符合 RegisterNatives 方法的特征``if` `(symbol.name.indexOf(``"art"``) >= 0 &&` `//RegisterNatives 是 ART（Android Runtime）环境的一部分``symbol.name.indexOf(``"JNI"``) >= 0 &&` `//RegisterNatives 是 JNI（Java Native Interface）的一部分``symbol.name.indexOf(``"RegisterNatives"``) >= 0 &&` `//检查符号名称中是否包含 "RegisterNatives" 字样。``symbol.name.indexOf(``"CheckJNI"``) < 0) {` `//CheckJNI 是用于调试和验证 JNI 调用的工具，如果不过滤，会有两个RegisterNatives，而带有CheckJNI的系统一般是关闭的，所有要过滤掉``addrRegisterNatives = symbol.address;` `// 保存方法地址``console.log(``"RegisterNatives is at "``, symbol.address, symbol.name);` `// 输出地址和名称``hook_RegisterNatives(addrRegisterNatives);` `// 调用hook函数``}``}``}` `function` `hook_RegisterNatives(addrRegisterNatives) {``// 确保提供的地址不为空``if` `(addrRegisterNatives !=` `null``) {``// 使用 Frida 的 Interceptor hook指定地址的函数``Interceptor.attach(addrRegisterNatives, {``// 当函数被调用时执行的代码``onEnter:` `function` `(args) {``// 打印调用方法的数量``console.log(``"[RegisterNatives] method_count:"``, args[3]);` `// 获取 Java 类并打印类名``let java_class = args[1];``let class_name = Java.vm.tryGetEnv().getClassName(java_class);` `let methods_ptr = ptr(args[2]);` `// 获取方法数组的指针``let method_count = parseInt(args[3]);` `// 获取方法数量` `// 遍历所有方法``//jni方法里包含三个部分：方法名指针、方法签名指针和方法函数指针。每个指针在内存中占用 Process.pointerSize 的空间（这是因为在 32 位系统中指针大小是 4 字节，在 64 位系统中是 8 字节）。为了提高兼容性，统一用Process.pointerSize，系统会自动根据架构来适配``for` `(let i = 0; i < method_count; i++) {``// 读取方法的名称、签名和函数指针``let name_ptr = Memory.readPointer(methods_ptr.add(i * Process.pointerSize * 3));``//读取方法名的指针。这是每个方法结构体的第一部分，所以直接从起始地址读取。``let sig_ptr = Memory.readPointer(methods_ptr.add(i * Process.pointerSize * 3 + Process.pointerSize));``//读取方法签名的指针。这是结构体的第二部分，所以在起始地址的基础上增加了一个指针的大小``let fnPtr_ptr = Memory.readPointer(methods_ptr.add(i * Process.pointerSize * 3 + Process.pointerSize * 2));``//读取方法函数的指针。这是结构体的第三部分，所以在起始地址的基础上增加了两个指针的大小（Process.pointerSize * 2）。` `// 将指针内容转换为字符串``let name = Memory.readCString(name_ptr);``let sig = Memory.readCString(sig_ptr);` `// 获取方法的调试符号``let symbol = DebugSymbol.fromAddress(fnPtr_ptr);` `// 打印每个注册的方法的相关信息``console.log(``"[RegisterNatives] java_class:"``, class_name,` `"name:"``, name,` `"sig:"``, sig,` `"fnPtr:"``, fnPtr_ptr,` `" fnOffset:"``, symbol,` `" callee:"``, DebugSymbol.fromAddress(``this``.returnAddress));``}``}``});``}``}` `setImmediate(find_RegisterNatives);` `// 立即执行 find_RegisterNatives 函数` |
|-|-|

### 通过hook查看静态注册

| 12345678910111213 | `function` `hook_dlsym() {``var` `dlsymAddr = Module.findExportByName(``"libdl.so"``,` `"dlsym"``);``Interceptor.attach(dlsymAddr, {``onEnter:` `function``(args) {``this``.args1 = args[1];``},``onLeave:` `function``(retval) {``var` `module = Process.findModuleByAddress(retval);``if` `(module ===` `null``)` `return``;` `console.log(``this``.args1.readCString(), module.name, retval, retval.sub(module.base));``}``});``}` |
|-|-|

---

## 参考文章

[《安卓逆向这档事》十七、你的RPCvs佬的RPC - 吾爱破解 - 52pojie.cn](https://www.52pojie.cn/thread-1892127-1-1.html)

[[原创] 细说So动态库的加载流程-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-255674.htm)

[android so加载 - vendanner - 博客园](https://www.cnblogs.com/vendanner/p/4979177.html)

<https://cs.android.com/android/platform/superproject/main/+/main:bionic/libc/include/android/dlext.h;l=174;drc=69e2b7c426ed5bef6be369b7e4d300e370dc39cd;bpv=0;bpt=1?hl=zh-cn>

[so逆向筑基-hook init init_array 和JNI_OnLoad](https://www.jianshu.com/p/59d1d3054abe)

---

# 回复

## 回复 by focaccia (#2)

*2025-9-18 19:20*

hook_RegisterNatives还是输出两个符号，怎么回事：
_ZN3art3JNIILb0EE15RegisterNativesEP7_JNIEnvP7_jclassPK15JNINativeMethodi
_ZN3art3JNIILb1EE15RegisterNativesEP7_JNIEnvP7_jclassPK15JNINativeMethodi
