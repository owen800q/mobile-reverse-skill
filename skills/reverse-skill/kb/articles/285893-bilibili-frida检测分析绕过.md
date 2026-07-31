---
title: '[原创] bilibili frida检测分析绕过'
url: https://bbs.kanxue.com/thread-285893.htm
tid: 285893
author: ovo_帮我不c
date: '2025-03-06'
tags: [Android安全, 原创, 基础理论, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:13:15+08:00'
replies: 8
---

本文是对于了**版本7.26.1，以及版本7.76.0**的frida检测进行的分析研究以及绕过

# bilibili 7.26.1

bilibili的旧版本frida检测

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_55MANHSG5BSC2MD.webp)

可以看到按照Spawn的方式启动的时候，直接frida就被检测了。我们按照 hook dlopen去查看可能出现的对应frida检测的so文件。

| 12345678910111213141516 | `function` `hook_dlopen(soName =` `''``) {``Interceptor.attach(Module.findExportByName(``null``,` `"android_dlopen_ext"``), {``onEnter:` `function``(args) {``var` `pathptr = args[0];``if` `(pathptr) {``var` `path = ptr(pathptr).readCString();``console.log(``"Loading: "` `+ path);``if` `(path.indexOf(soName) >= 0) {``console.log(``"Already loading: "` `+ soName);``// hook_system_property_get();``}``}``}``});``}``setImmediate(hook_dlopen,` `"libmsaoaidsec.so"``);` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_ATYPJBJR9W2WSWB.webp)

可以看到的是libmsaoaidsec.so文件，在dlopen了之后，frida就被检测到了，所以大概率的可能是在libmsaoaidsec.so进行的frida检测。在这里之前，我们需要知道是在哪进行HOOK是最为有用的

这里我们可以通过在dlopen结束之后，去HOOK JNI_Onload函数，去判断检测函数在JNI_Onload之前还是之后，我们通过IDA可以去查看JNI_Onload的地址。这里是在JNI_Onload之前出现的frida检测。

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_JVQR8HKTWKMG92B.webp)

```
function hook_JNI_OnLoad(){
    let module = Process.findModuleByName("libmsaoaidsec.so")
    Interceptor.attach(module.base.add(0xC6DC + 1), {
        onEnter(args){
            console.log("JNI_OnLoad")
        }
    })
}
```

我们通过HOOK 进程创建，来看看对于frida检测的线程是在哪里启动的。在复现过程中，原作者使用了hook _system_property_get函数，这里是 init_proc函数较早的位置，这里涉及到了安卓源码中dlopen和.init_xx函数的执行流程比较，在我的so文件执行流程的过程中有细节分析。

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_VJKBH4F47NY78AP.webp)

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_BWRV996DN5UU42F.webp)

| 12345678910111213141516171819202122 | `function` `hook_system_property_get() {``var` `system_property_get_addr = Module.findExportByName(``null``,` `"__system_property_get"``);``if` `(!system_property_get_addr) {``console.log(``"__system_property_get not found"``);``return``;``}` `Interceptor.attach(system_property_get_addr, {``onEnter:` `function``(args) {``var` `nameptr = args[0];``if` `(nameptr) {``var` `name = ptr(nameptr).readCString();``if` `(name.indexOf(``"ro.build.version.sdk"``) >= 0) {``console.log(``"Found ro.build.version.sdk, need to patch"``);``// hook_pthread_create();``// bypass()``//这里可以开始进行HOOK``}``}``}``});``}` |
|-|-|

由于我们知道，frida检测的是在JNI_Onload函数之前，那么我们就要在init_proc的越早的地方可以进行HOOK，我们HOOK的地方就是线程创建的位置pthread_create。

| 12345678910111213141516171819202122232425262728 | `function` `hook_pthread_create() {``var` `pthread_create = Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``var` `libmsaoaidsec = Process.findModuleByName(``"libmsaoaidsec.so"``);` `if` `(!libmsaoaidsec) {``console.log(``"libmsaoaidsec.so not found"``);``return``;``}` `console.log(``"libmsaoaidsec.so base: "` `+ libmsaoaidsec.base);` `if` `(!pthread_create) {``console.log(``"pthread_create not found"``);``return``;``}` `Interceptor.attach(pthread_create, {``onEnter:` `function``(args) {``var` `thread_ptr = args[2];``if` `(thread_ptr.compare(libmsaoaidsec.base) < 0 \|\| thread_ptr.compare(libmsaoaidsec.base.add(libmsaoaidsec.size)) >= 0) {``console.log(``"pthread_create other thread: "` `+ thread_ptr);``}` `else` `{``console.log(``"pthread_create libmsaoaidsec.so thread: "` `+ thread_ptr +` `" offset: "` `+ thread_ptr.sub(libmsaoaidsec.base));``}``},``onLeave:` `function``(retval) {}``});``}` |
|-|-|

在这里我们通过去HOOK dlopen的位置，通过dlopen的位置去HOOK **system_property_get** 当参数是ro.build.version.sdk然后去hook pthread_create

dlopen ———>system_property_get————>pthread_create

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_3EA6CS8GYGG6VH5.webp)

这里去比较了对应所以由pthread_create 创建的线程，当对应的线程的地址在libmsaoaidsec.so的地址区域内的时候，打印对应的地址以及偏移。可以看到这里有两个线程出现了

我们可以去通过IDA看看

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_S3KT2F8D9AVGSXG.webp)

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_3XAYUAAM24KNPEX.webp)

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_WWJEV655QZ3VEPR.webp)

这些位置的像出现的 strcmp openat strstr.......很多的frida的检测，我们交叉引用一下看看pthread_create，然后直接实现NOP就可以了

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_X2M33CWVTU6RVCM.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_UP53H4RBDBQ6E7H.webp)

### 总体代码

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374757677787980818283 | `function` `hook_dlopen(soName =` `''``) {``Interceptor.attach(Module.findExportByName(``null``,` `"android_dlopen_ext"``), {``onEnter:` `function``(args) {``var` `pathptr = args[0];``if` `(pathptr) {``var` `path = ptr(pathptr).readCString();``console.log(``"Loading: "` `+ path);``if` `(path.indexOf(soName) >= 0) {``console.log(``"Already loading: "` `+ soName);``hook_system_property_get();``}``}``}``});``}` `function` `hook_system_property_get() {``var` `system_property_get_addr = Module.findExportByName(``null``,` `"__system_property_get"``);``if` `(!system_property_get_addr) {``console.log(``"__system_property_get not found"``);``return``;``}` `Interceptor.attach(system_property_get_addr, {``onEnter:` `function``(args) {``var` `nameptr = args[0];``if` `(nameptr) {``var` `name = ptr(nameptr).readCString();``if` `(name.indexOf(``"ro.build.version.sdk"``) >= 0) {``console.log(``"Found ro.build.version.sdk, need to patch"``);``hook_pthread_create();``// bypass()``}``}``}``});``}` `function` `hook_pthread_create() {``var` `pthread_create = Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``var` `libmsaoaidsec = Process.findModuleByName(``"libmsaoaidsec.so"``);` `if` `(!libmsaoaidsec) {``console.log(``"libmsaoaidsec.so not found"``);``return``;``}` `console.log(``"libmsaoaidsec.so base: "` `+ libmsaoaidsec.base);` `if` `(!pthread_create) {``console.log(``"pthread_create not found"``);``return``;``}` `Interceptor.attach(pthread_create, {``onEnter:` `function``(args) {``var` `thread_ptr = args[2];``if` `(thread_ptr.compare(libmsaoaidsec.base) < 0 \|\| thread_ptr.compare(libmsaoaidsec.base.add(libmsaoaidsec.size)) >= 0) {``console.log(``"pthread_create other thread: "` `+ thread_ptr);``}` `else` `{``console.log(``"pthread_create libmsaoaidsec.so thread: "` `+ thread_ptr +` `" offset: "` `+ thread_ptr.sub(libmsaoaidsec.base));``}``},``onLeave:` `function``(retval) {}``});``}``function` `nop_code(addr)``{``Memory.patchCode(ptr(addr),4,code => {``const cw =``new` `ThumbWriter(code,{pc:ptr(addr)});``cw.putNop();``cw.putNop();``cw.flush();``})``}` `function` `bypass()``{``let module = Process.findModuleByName(``"libmsaoaidsec.so"``)``nop_code(module.base.add(0x010AE4))``nop_code(module.base.add(0x113F8))``}``setImmediate(hook_dlopen,` `"libmsaoaidsec.so"``);` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_CFR4T6Q4VE524X2.webp)

这里就绕过frida了，或者通过直接在IDA中去patch掉上面两个位置的pthread_create，然后把补丁之后的so再放到APK中也可以。

参考文章：[[原创]绕过bilibili frida反调试-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-277034.htm)

# bilibili7.76.0

**7.26.1:**

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_J9H98EMZW3SAXSQ.webp)

在高一点的版本上面，pthread_create函数是被隐藏了的

**7.76.0:** ![image](https://bbs.kanxue.com/upload/attach/202503/971248_QKTJW38G6AJKDYB.webp)

但是其实我们通过之前的方法也能看到对应的pthead_create创建线程的位置

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667 | `function` `hook_dlopen(soName =` `''``) {``Interceptor.attach(Module.findExportByName(``null``,` `"android_dlopen_ext"``), {``onEnter:` `function``(args) {``var` `pathptr = args[0];``if` `(pathptr) {``var` `path = ptr(pathptr).readCString();``console.log(``"Loading: "` `+ path);``if` `(path.indexOf(soName) >= 0) {``console.log(``"Already loading: "` `+ soName);``hook_system_property_get();``}``}``}``});``}` `function` `hook_system_property_get() {``var` `system_property_get_addr = Module.findExportByName(``null``,` `"__system_property_get"``);``if` `(!system_property_get_addr) {``console.log(``"__system_property_get not found"``);``return``;``}` `Interceptor.attach(system_property_get_addr, {``onEnter:` `function``(args) {``var` `nameptr = args[0];``if` `(nameptr) {``var` `name = ptr(nameptr).readCString();``if` `(name.indexOf(``"ro.build.version.sdk"``) >= 0) {``console.log(``"Found ro.build.version.sdk, need to patch"``);``hook_pthread_create();``// bypass()``}``}``}``});``}` `function` `hook_pthread_create() {``var` `pthread_create = Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``var` `libmsaoaidsec = Process.findModuleByName(``"libmsaoaidsec.so"``);` `if` `(!libmsaoaidsec) {``console.log(``"libmsaoaidsec.so not found"``);``return``;``}` `console.log(``"libmsaoaidsec.so base: "` `+ libmsaoaidsec.base);` `if` `(!pthread_create) {``console.log(``"pthread_create not found"``);``return``;``}` `Interceptor.attach(pthread_create, {``onEnter:` `function``(args) {``var` `thread_ptr = args[2];``if` `(thread_ptr.compare(libmsaoaidsec.base) < 0 \|\| thread_ptr.compare(libmsaoaidsec.base.add(libmsaoaidsec.size)) >= 0) {``console.log(``"pthread_create other thread: "` `+ thread_ptr);``}` `else` `{``console.log(``"pthread_create libmsaoaidsec.so thread: "` `+ thread_ptr +` `" offset: "` `+ thread_ptr.sub(libmsaoaidsec.base));``}``},``onLeave:` `function``(retval) {}``});``}``setImmediate(hook_dlopen,` `"libmsaoaidsec.so"``);` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_3PWC86HVDT84YV7.webp)
这里可以看到在libmsaoaidsec.so中创建了三个新的线程，这里多半也就是进行frida检测的位置的了

```
pthread_create libmsaoaidsec.so thread: 0x76bcce0544 offset: 0x1c544
pthread_create libmsaoaidsec.so thread: 0x76bccdf8d4 offset: 0x1b8d4
pthread_create libmsaoaidsec.so thread: 0x76bcceae5c offset: 0x26e5c
```

同时这里我们进行HOOK的检测frida线程在哪的时候，也是在system_property_get的函数的位置进行HOOK的，但是实际上这里的位置也已经被混淆了，但是这个函数没有被混淆，可以直接在导入表里面找到的，那么我们就去交叉引用看看在哪引用的

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_CCNAKCPCF8HSQDU.webp)

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_9C2PSX5X28AC633.webp)

其实是能够发现还是在init_proc的sub_123F0函数的位置的

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_ZB9NV9EX2BRKP9C.webp)

但是这里去判断参数的为"ro.build.version.sdk"已经被混淆了，但是我们既然能通过这个代码找到对应的线程，说明实际上还是去执行了 **_system_property_get（"ro.build.version.sdk"）**这个函数的，而且既然代码可以直接检测得到frida检测的线程的地址，那么说明检测点还是再_system_property_get（"ro.build.version.sdk"）之前的。

我们同样按照交叉引用看看pthread_create 被混淆成了什么

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_7TTP6ZJBVPY7WCE.webp)

![image](https://bbs.kanxue.com/upload/attach/202503/971248_EQ4YD9ACGHP5DW7.webp)

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_5AJ89TYKGDR9YW7.webp)
其实通过参数的形式，我们就可以判断大概率就是被混淆了的pthead_create函数

## 正面对抗

按照之前旧版本的frida检测，我们的反检测是通过NOP掉对应的frida检测线程，在7.26.1中frida检测是有两个线程的，而在7.76.0中，这里的frida检测有了三个线程，那么我们也可以对于这里的三个线程进行NOP

这里按照最原始的方法，不去NOP掉**pthead_create函数**，而是去patch掉对应的frida函数。以及其中的NOP的实际，我选择的位置是在判断到进入libmsaoaidsec.so的时候，并且开始进行frida检测线程创建的pthead_create函数时期

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_NAFW5UKJTMNFFB5.webp)

| 12345678910111213141516171819202122232425262728293031323334353637 | `function` `hook_pthread_create() {``var` `pthread_create = Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``var` `libmsaoaidsec = Process.findModuleByName(``"libmsaoaidsec.so"``);` `if` `(!libmsaoaidsec) {``console.log(``"libmsaoaidsec.so not found"``);``return``;``}` `console.log(``"libmsaoaidsec.so base: "` `+ libmsaoaidsec.base);` `if` `(!pthread_create) {``console.log(``"pthread_create not found"``);``return``;``}` `Interceptor.attach(pthread_create, {``onEnter:` `function``(args) {``var` `thread_ptr = args[2];``if` `(thread_ptr.compare(libmsaoaidsec.base) < 0 \|\| thread_ptr.compare(libmsaoaidsec.base.add(libmsaoaidsec.size)) >= 0) {``console.log(``"pthread_create other thread: "` `+ thread_ptr);``}` `else` `{``console.log(``"pthread_create libmsaoaidsec.so thread: "` `+ thread_ptr +` `" offset: "` `+ thread_ptr.sub(libmsaoaidsec.base));``Interceptor.replace(libmsaoaidsec.base.add(0x1c544),``new` `NativeCallback(``function``(){``console.log(``"Interceptor.replace: 0x1c544"``)``},``"void"``,[]))``Interceptor.replace(libmsaoaidsec.base.add(0x1b8d4),``new` `NativeCallback(``function``(){``console.log(``"Interceptor.replace: 0x1c544"``)``},``"void"``,[]))``Interceptor.replace(libmsaoaidsec.base.add(0x26e5c),``new` `NativeCallback(``function``(){``console.log(``"Interceptor.replace: 0x1c544"``)``},``"void"``,[]))``}``},``onLeave:` `function``(retval) {}``});``}` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_W5C5V59VR2CQDX6.webp)

可以看到是直接绕过了frida检测的位置的。并且我写的一个frida打印函数也是成功执行了

## 取巧绕过

[绕过最新版bilibili app反frida机制-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-281584.htm)

在这一篇文章中，作者并没有去实现正面对抗，而且取巧绕过了，通过的方式就是在HOOK dlsym函数，在进入libmsaoaidsec.so之后去HOOK dlsym 判断调用pthead_create函数的次数，在前两次进行调用pthead_create函数时，去调用fake_pthead_create函数，从而实现frida线程不启动，达成绕过。

以下是取巧绕过的代码(复制于上面的网址)：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758 | `function` `create_fake_pthread_create() {``const fake_pthread_create = Memory.alloc(4096)``Memory.protect(fake_pthread_create, 4096,` `"rwx"``)``Memory.patchCode(fake_pthread_create, 4096, code => {``const cw =` `new` `Arm64Writer(code, { pc: ptr(fake_pthread_create) })``cw.putRet()``})``return` `fake_pthread_create``}` `function` `hook_dlsym() {``var` `count = 0``console.log(``"=== HOOKING dlsym ==="``)``var` `interceptor = Interceptor.attach(Module.findExportByName(``null``,` `"dlsym"``),``{``onEnter:` `function` `(args) {``const name = ptr(args[1]).readCString()``console.log(``"[dlsym]"``, name)``if` `(name ==` `"pthread_create"``) {``count++``}``},``onLeave:` `function``(retval) {``if` `(count == 1) {``retval.replace(fake_pthread_create)``}``else` `if` `(count == 2) {``retval.replace(fake_pthread_create)``// 完成2次替换, 停止hook dlsym``interceptor.detach()``}``}``}``)``return` `Interceptor``}` `function` `hook_dlopen() {``var` `interceptor = Interceptor.attach(Module.findExportByName(``null``,` `"android_dlopen_ext"``),``{``onEnter:` `function` `(args) {``var` `pathptr = args[0];``if` `(pathptr !== undefined && pathptr !=` `null``) {``var` `path = ptr(pathptr).readCString();``console.log(``"[LOAD]"``, path)``if` `(path.indexOf(``"libmsaoaidsec.so"``) > -1) {``hook_dlsym()``}``}``}``}``)``return` `interceptor``}` `// 创建虚假pthread_create``var` `fake_pthread_create = create_fake_pthread_create()``var` `dlopen_interceptor = hook_dlopen()` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202503/971248_S6GB9SH8M9EXADP.webp)

同样也可以实现绕过，不过，我们其实能知道，最开始的时候，其实是发现在libmsaoaidsec.so一共是开启了三个线程的，其实我觉得这里可以把count设置到三

| 12345678910111213 | `onLeave:` `function``(retval) {``if` `(count == 1) {``retval.replace(fake_pthread_create)``}``else` `if` `(count == 2) {``retval.replace(fake_pthread_create)``}``else` `if` `(count == 2) {``retval.replace(fake_pthread_create)``// 完成2次替换, 停止hook dlsym``interceptor.detach()``}``}` |
|-|-|

这样我尝试过，也能实现绕过的。

---

# 回复

## 回复 by iBa0 (#3)

*2025-3-15 23:35*

检测的函数JNI_Onload之前有两个init段函数和init_xxxx函数，android-dlopen-ext执行完的时候，init_xxx在其内部执行完了，所以要找一个函数处在init_xxxx和android-dlopen-ext函数之间，比如：call_constructor函数，大多数文章都是hook ro.build.version.sdk字段判断，其实也可以搞call_constructor函数的，也在init_xxxx之前执行，看so加载链接初始化的过程

## 回复 by wx_范迪塞尔 (#4)

*2025-3-26 09:56*

思路赞一个

## 回复 by ovo_帮我不c (#5)

*2025-4-1 10:56*

>
> [WMBa0](https://bbs.kanxue.com/user-971547.htm)
>
>  检测的函数JNI_Onload之前有两个init段函数和init_xxxx函数，android-dlopen-ext执行完的时候，init_xxx在其内部执行完了，所以要找一个函数处在init_xxx ...
>
>

是的哥

## 回复 by null0bj (#6)

*2025-4-1 13:42*

我dump了解密后的libmsaoaidsec.so，它没有显式导入pthread_create，而是通过调用dlsym获取pthread_create
但我碰到一个问题，在利用putRet patch线程调用的函数后，主线程调用strstr 函数时,haystack无效指针,导致进程崩溃。楼主有类似的情况吗

## 回复 by null0bj (#7)

*2025-4-1 13:45*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  null0bj](https://bbs.kanxue.com/user-890495.htm)
>
>  我dump了解密后的libmsaoaidsec.so，它没有显式导入pthread_create，而是通过init_array的函数解密字符串，调用dlsym获取pthread_create，虽然没有 ...
>
>

是否可能是主线程访问了共享的内容，由于子线程没有实际启动，导致共享内容没有被子线程处理，从而引发无效指针的问题。

## 回复 by zhonghuayi (#8)

*2025-5-11 22:54*

学习了，有时间练习看看

## 回复 by 海阔天空1688 (#9)

*2025-9-5 09:40*

666，学习了

## 回复 by git_55111Empycity (#10)

*2026-4-11 15:44*

666
