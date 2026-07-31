---
title: '[原创]某加固onCreate的vmp分析'
url: https://bbs.kanxue.com/thread-286006.htm
tid: 286006
author: 海带
date: '2025-03-13'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T14:12:35+08:00'
replies: 18
---

# 某加固onCreate的Vmp分析

## 前言

复现完oacia师傅的文章，[360加固dex解密流程分析 | oacia = oaciaのBbBlog~ = DEVIL or SWEET](https://oacia.dev/360-jiagu/)

想继续来看看onCreate怎么实现的，继续使用oacia师傅的加固app

## 定位onCreate函数

onCreate函数被注册为native函数

![image](https://bbs.kanxue.com/upload/attach/202503/933207_DZG2Y994E6XFZKP.png)

Init函数，attachBaseContext函数，都没有什么可用的线索。发现static函数里有一个jni函数interface11，

![image](https://bbs.kanxue.com/upload/attach/202503/933207_ZTH4NZN74XFCUD9.png)

在attachBaseContext执行之前。所有 `static {}` 代码块会在类加载时执行（`Application` 类的 `constructor` 之前)

使用yang神的脚本，拦截JNI注册函数RegisterNative找到函数的地址

| 1 | `[RegisterNatives] java_class: com.stub.StubApp name: interface11 sig: (I)V fnPtr:` `0x73fd0bb9d8` `module_name: libjiagu_64.so module_base:` `0x73fcf82000` `offset:` `0x1399d8` |
|-|-|

直接来看汇编代码,前面都是一些线程检测，以及寄存器操作等，来到最后跳转的是x8寄存器的值，没法直接反编译

![image](https://bbs.kanxue.com/upload/attach/202503/933207_9PQSQRYTJNYY36J.png)

用stalker，跟踪x8寄存器的变化，来打印跳转

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667 | `function` `hookTargetFunc() {``var` `baseAddr = Module.findBaseAddress(TargetLibName)``//console.log(TargetLibName + " Module Base: " + baseAddr);``if` `(baseAddr ==` `null``) {``console.log(``'Please makesure '` `+ TargetLibName +` `' is Loaded, by setting extractNativeLibs true.'``);``return``;``}``// hook指定的函数地址``Interceptor.attach(baseAddr.add(TargetFuncOffset), {``onEnter:` `function` `(args) {``console.log(``'\nCall '` `+ TargetFuncOffset.toString(16).toUpperCase() +` `' In'``)``this``.tid = Process.getCurrentThreadId();``var` `so_addr = Module.findBaseAddress(so_name);``var` `so_size = Process.getModuleByName(so_name).size;``Stalker.follow(``this``.tid, {``events: {``call:` `true``,` `// CALL instructions: yes please``// Other events:``ret:` `false``,` `// RET instructions``exec:` `false``,` `// all instructions: not recommended as it's``//                   a lot of data``block:` `false``,` `// block executed: coarse execution trace``compile:` `false` `// block compiled: useful for coverage``},``onReceive:` `function` `() {``},` `transform:` `function` `(iterator) {``var` `instruction = iterator.next();``const startAddress = instruction.address;``if` `(startAddress){``do``{``if` `(instruction.mnemonic.startsWith('br``')\|\|instruction.mnemonic.startsWith('``blr``')\|\|instruction.mnemonic.startsWith('``bl``')) {` `try {` `iterator.putCallout(function (context) {``var pc = context.pc; //获取pc寄存器，当前地址``var lr = context.lr;` `var x8 = context.x8; //获取x8寄存器，``var module = Process.findModuleByAddress(pc);``if (module) {``try{``console.log(module.name + "!" +Memory.readCString(ptr(x8)));` `}``catch (e){``}` `console.log("x8 ====" + DebugSymbol.fromAddress(ptr(x8)));``}``});``} catch (e) {``console.log("error", e)``}``}``iterator.keep();``} while ((instruction = iterator.next()) !== null);``}``},` `onCallSummary(summary) {``}``})``}, onLeave: function (retVal) {``console.log('``Call` `' + TargetFuncOffset.toString(16).toUpperCase() + '` `Out\n')``Stalker.unfollow(``this``.tid)``}``})``}` |
|-|-|

根据trcace发现了两处oncreate，看看的后一个地址干了什么

| 123456789101112131415161718192021222324 | `x8 ====0x7bfee7fe0c libjiagu_64.so!0x139e0c``x8 ====0x7bfee7fe64 libjiagu_64.so!0x139e64``x8 ====0x7bfee7fe7c libjiagu_64.so!0x139e7c``//似乎是重点的``x8 ====0x7bfee80460 libjiagu_64.so!0x13a460``//拷贝操作``x8 ====0x7bfee7fe8c libjiagu_64.so!0x139e8c``x8 ====0x7bfee7ff60 libjiagu_64.so!0x139f60` `//来到复杂函数 sub_19DCA4``x8 ====0x7bfee7ffa0 libjiagu_64.so!0x139fa0``//拷贝``x8 ====0x7bfee7ffc4 libjiagu_64.so!0x139fc4``x8 ====0x7bfee8010c libjiagu_64.so!0x13a10c``x8 ====0x7bfee80140 libjiagu_64.so!0x13a140``x8 ====0x7bfee80170 libjiagu_64.so!0x13a170``//oncreate``x8 ====0x7bfee80194 libjiagu_64.so!0x13a194``x8 ====0x7bfee801fc libjiagu_64.so!0x13a1fc``x8 ====0x7bfee804e4 libjiagu_64.so!0x13a4e4``x8 ====0x7bfee8024c libjiagu_64.so!0x13a24c``x8 ====0x7bfee80264 libjiagu_64.so!0x13a264``//进程检测mutex_lock``//前面似乎一些栈的操作，然后寄存器发生变化``x8 ====0x7bfee802e8 libjiagu_64.so!0x13a2e8``//``x8 ====0x7bfee80328 libjiagu_64.so!0x13a328``//内存``x8 ====0x7bfee7fe64 libjiagu_64.so!0x139e64``x8 ====0x7bfee80600 libjiagu_64.so!0x13a600``x8 ====0x7bfee8061c libjiagu_64.so!0x13a61c``//然后出现下一个oncreate` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202503/933207_VJF7GZCSDNSA5ME.png)

后一个oncreate,都是一些内存和栈的操作。

| 1234567891011121314151617181920 | `x8 ====0x7bfee807ac libjiagu_64.so!0x13a7ac``//下一步跳转``x8 ====0x7bfee807b8 libjiagu_64.so!0x13a7b8``x8 ====0x7bfee807f4 libjiagu_64.so!0x13a7f4``x8 ====0x7bfee80808 libjiagu_64.so!0x13a808``x8 ====0x7bfee80810 libjiagu_64.so!0x13a810``x8 ====0x7bfee8082c libjiagu_64.so!0x13a82c``x8 ====0x7bfee80854 libjiagu_64.so!0x13a854``x8 ====0x7bfee80854 libjiagu_64.so!0x13a854``x8 ====0x7bfee80838 libjiagu_64.so!0x13a838``x8 ====0x7bfee807e0 libjiagu_64.so!0x13a7e0``x8 ====0x7bfee807f4 libjiagu_64.so!0x13a7f4``x8 ====0x7bfee80870 libjiagu_64.so!0x13a870``x8 ====0x7bfee8087c libjiagu_64.so!0x13a87c``x8 ====0x7bfee80894 libjiagu_64.so!0x13a894``x8 ====0x7bfee80894 libjiagu_64.so!0x13a894``x8 ====0x7bfee80894 libjiagu_64.so!0x13a894``x8 ====0x7bfee80894 libjiagu_64.so!0x13a894``x8 ====0x7bfee808c4 libjiagu_64.so!0x13a8c4``x8 ====0x7bfee808dc libjiagu_64.so!0x13a8dc``x8 ====0x7bfee808e8 libjiagu_64.so!0x13a8e8` |
|-|-|

0x13a170函数之后出现了第一个onCreate，blr x8进入关键部分。

jnitrace看一下流程

| 1 | `jnitrace` `-``l libjiagu_64.so com.oacia.apk_protect` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202503/933207_JJ32H225BEUTSZH.png)

| 1234567891011121314 | `x8` `=``=``=``=``0x7c166e43c0` `libart.so!_ZN3art3JNI11GetMethodIDEP7_JNIEnvP7_jclassPKcS6_``/``/``JNIEnv``-``>GetMethodID()``x8` `=``=``=``=``0x7c164d6a1c` `libart.so!_ZN3art11ClassLinker15InitializeClassEPNS_6ThreadENS_6HandleINS_6mirror5ClassEEEbb``libart.so!<clinit>` `/``/``在类加载过程中执行``libart.so!<clinit>``libart.so!<init>``libart.so!<init>``bytesToHex``bytesToHex``libart.so!enc2``/``/``似乎是m进程检测的关键数据``libart.so!enc2``libart.so!onCreate``libart.so!onCreate``libart.so!Landroid``/``os``/``Bundle;``libart.so!Landroid``/``os``/``Bundle;` |
|-|-|

接下来关键操作分析0x13a61c函数之后出现了第二个oncreate，同样是blr x8,进入jni函数了。

![image](https://bbs.kanxue.com/upload/attach/202503/933207_595GEBMSZFWUWY8.png)

| 12345678910 | `x8` `=``=``=``=``0x7c1671e4d4` `libart.so!_ZN3art3JNI15RegisterNativesEP7_JNIEnvP7_jclassPK15JNINativeMethodi``/``/``JNIEnv``-``>RegisterNatives()``libart.so!enc2``libart.so!enc2``libart.so!onCreate``libart.so!onCreate``libart.so!Landroid``/``os``/``Bundle;``libart.so!Landroid``/``os``/``Bundle;``x8` `=``=``=``=``0x7c169d0160` `libart.so!_ZN3art7Runtime9instance_E``x8` `=``=``=``=``0x7c169d0160` `libart.so!_ZN3art7Runtime9instance_E``x8` `=``=``=``=``0x7c16723374` `libart.so!_ZN3art3JNI14ExceptionCheckEP7_JNIEnv``/``/` `JNIEnv``-``>ExceptionCheck()` |
|-|-|

可以确定，interface11方法将onCreate注册某个native方法上

我们去hook一下 _ZN3art3JNI15RegisterNativesEP7_JNIEnvP7_jclassPK15JNINativeMethodi找地址

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556 | `function` `traceRegisterNatives() {``var` `RegisterNativesaddr =` `null``;``var` `libartmodule = Process.getModuleByName(``"libart.so"``);``libartmodule.enumerateSymbols().forEach(``function` `(symbol) {``if` `(symbol.name ==` `"_ZN3art3JNI15RegisterNativesEP7_JNIEnvP7_jclassPK15JNINativeMethodi"``) {``RegisterNativesaddr = symbol.address;``}``})``console.log(``"RegisterNativesaddr->"` `+ RegisterNativesaddr);``if` `(RegisterNativesaddr !=` `null``) {``Interceptor.attach(RegisterNativesaddr, {``onEnter:` `function` `(args) {``console.log(``"go into RegisterNativesaddr"``);``var` `methodsptr = ptr(args[2]);``var` `method_count = args[3];``var` `i = 0;``console.log(``"["` `+ Process.getCurrentThreadId() +` `"]RegisterNatives->"` `+ method_count);``for` `(i = 0; i < method_count; i++) {``var` `name = methodsptr.add(i * Process.pointerSize * 3 + 0).readPointer().readUtf8String();``var` `signature = methodsptr.add(i * Process.pointerSize * 3 + 1 * Process.pointerSize).readPointer().readUtf8String();``var` `fnPtr = methodsptr.add(i * Process.pointerSize * 3 + 2 * Process.pointerSize).readPointer();``var` `find_module = Process.findModuleByAddress(fnPtr);``console.log(``"["` `+ Process.getCurrentThreadId() +` `"]RegisterNatives->name:"` `+ name +` `",sig:"` `+ signature +` `",addr:"` `+ fnPtr);` `}``if` `(name ==` `"onCreate"``) {``console.log(hexdump(fnPtr));``var` `code = Instruction.parse(fnPtr);``var` `next_code = code.next;``console.log(code.address,` `":"``, code);``for` `(``var` `i = 0; i < 10; i++) {``var` `next_c = Instruction.parse(next_code);``console.log(next_c.address,` `":"``, next_c);``next_code = next_c.next;``}``var` `onCreate_fun_ptr = next_c.next.add(0xf);``var` `onCreate_fun_addr = Memory.readPointer(onCreate_fun_ptr);``console.log(``"onCreate_function_address:"``,onCreate_fun_addr,``"offset:"``,ptr(onCreate_fun_addr));``}``}, onLeave:` `function` `(retval) {`  `}``})``}` `}`  `function` `main() {``var` `module = Module.findBaseAddress(``"libjiagu_64.so"``);``console.log(``"libjiagu_64.so base address: "` `+ module);``traceRegisterNatives();``}` `setImmediate(main);` |
|-|-|

输出了oncreate

![image](https://bbs.kanxue.com/upload/attach/202503/933207_WKJ44UFZXVUCGVG.png)

但是是动态注册，找不到moudel的名字,无法直接打印地址。我们直接去so里面寻找字节码。在0x178c50+0xe7000=0x26FC50

![image](https://bbs.kanxue.com/upload/attach/202503/933207_4E6UHHSYN59YX8W.png)

在ida中找到onCreate地址

![image](https://bbs.kanxue.com/upload/attach/202503/933207_9ZBV29GH3GRRFC9.png)

## 定位vmp解释器

交叉引用onCreate，发现他被sub_1A1908调用。

再看看sub_1A1908的交叉引用

![image](https://bbs.kanxue.com/upload/attach/202503/933207_28BD2XXFGKX2D77.png)

来到函数sub_12DFE4,这里应该就是函数绑定的地方。

![image](https://bbs.kanxue.com/upload/attach/202503/933207_TXE7JSNB3UFKZ4W.png)

参数0ff_265F20,指向sub_137978，进入

![image](https://bbs.kanxue.com/upload/attach/202503/933207_2TKYJAU9754W8T4.png)

sub_137978这个函数是关键操作,可以Edit->other->specify switch idiom,修复。

sub_137978的逻辑大概是先保存栈帧，然后开辟新的空间，跳转跟之前一样，继续打印x8的变化，跟踪函数

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455 | `Call 137978 In``x8 ====0x7164d7d568 libjiagu_64.so!0x139568``x8 ====0x7164d7b9c0 libjiagu_64.so!0x1379c0``x8 ====0x7164d7b9e0 libjiagu_64.so!0x1379e0``x8 ====0x7164d7ba04 libjiagu_64.so!0x137a04``x8 ====0x7164d7ba7c libjiagu_64.so!0x137a7c``x8 ====0x717c4e9ec4 libart.so!_ZN3art3JNI14PushLocalFrameEP7_JNIEnvi``x8 ====0x7164d7bbe8 libjiagu_64.so!0x137be8` `//存在异或``x8 ====0x7164d7cd58 libjiagu_64.so!0x138d58` `x8 ====0x7164d7cd68 libjiagu_64.so!0x138d68``x8 ====0x7164d7cdf4 libjiagu_64.so!0x138df4``x8 ====0x7164d7cf04 libjiagu_64.so!0x138f04``x8 ====0x7164d7cf0c libjiagu_64.so!0x138f0c``x8 ====0x717c4eb8ec libart.so!_ZN3art3JNI11NewLocalRefEP7_JNIEnvP8_jobject``x8 ====0x7164d7cde8 libjiagu_64.so!0x138de8``x8 ====0x7164d7cdf4 libjiagu_64.so!0x138df4``x8 ====0x7164d7d70c libjiagu_64.so!0x13970c` `//来到了sub_144EF0``x8 ====0x7164d7d70c libjiagu_64.so!0x13970c` `//来到了sub_144EF0``x8 ====0x7164d88f4c libjiagu_64.so!0x144f4c` `//把sj8uwp\}{}r赋值给寄存器``x8 ====0x717c52d374 libart.so!_ZN3art3JNI14ExceptionCheckEP7_JNIEnv``x8 ====0x717c52d374 libart.so!_ZN3art3JNI14ExceptionCheckEP7_JNIEnv``x8 ====0x7164d89018 libjiagu_64.so!0x145018``x8 ====0x7164da3a54 libjiagu_64.so!0x15fa54` `//寄存器赋值``x8 ====0x717c4eaa68 libart.so!_ZN3art3JNI12NewGlobalRefEP7_JNIEnvP8_jobject``x8 ====0x7164d89024 libjiagu_64.so!0x145024``x8 ====0x7164d89040 libjiagu_64.so!0x145040` `x8 ====0x7164d89058 libjiagu_64.so!0x145058``x8 ====0x7164d890b8 libjiagu_64.so!0x1450b8``x8 ====0x7164d890fc libjiagu_64.so!0x1450fc` `//存在EOR W8, W8, #31，存入 X0 + 8 位置。把x0的值给了x28``x8 ====0x7164d89148 libjiagu_64.so!0x145148``x8 ====0x7164d9e630 libjiagu_64.so!0x15a630``//跳转到sub_16CE0C 存在花指令，似乎是重要函数，调用sub_15FC34``x8 ====0x7164d89154 libjiagu_64.so!0x145154``//CMP             W0, #129``x8 ====0x7164d8916c libjiagu_64.so!0x14516c/CMP             W0,` `#191``x8 ====0x7164d89184 libjiagu_64.so!0x145184``//CMP             W0, #224``x8 ====0x7164d89508 libjiagu_64.so!0x145508``//来到switch的分发快 CMP      W0, #206``x8 ====0x7164d89520 libjiagu_64.so!0x145520` `//CMP             W0, #215``x8 ====0x7164d8a274 libjiagu_64.so!0x146274``//CMP             W0, #210``x8 ====0x7164d8a28c libjiagu_64.so!0x14628c``//CMP             W0, #212``x8 ====0x7164d8cca4 libjiagu_64.so!0x148ca4` `//CMP             W0, #211 很像二分法有没有``x8 ====0x7164d8f3cc libjiagu_64.so!0x14b3cc` `//来到sub_160D7C解释器，且之前的x28给了x7，也就是参数a8``x8 ====0x717c52d374 libart.so!_ZN3art3JNI14ExceptionCheckEP7_JNIEnv``x8 ====0x717c52d374 libart.so!_ZN3art3JNI14ExceptionCheckEP7_JNIEnv``x8 ====0x717c4eaa68 libart.so!_ZN3art3JNI12NewGlobalRefEP7_JNIEnvP8_jobject``x8 ====0x717c52d374 libart.so!_ZN3art3JNI14ExceptionCheckEP7_JNIEnv``x8 ====0x717c4ee3c0 libart.so!_ZN3art3JNI11GetMethodIDEP7_JNIEnvP7_jclassPKcS6_``x8 ====0x717c52d374 libart.so!_ZN3art3JNI14ExceptionCheckEP7_JNIEnv``x8 ====0x717c52d374 libart.so!_ZN3art3JNI14ExceptionCheckEP7_JNIEnv``libjiagu_64.so!p:}\|q``libjiagu_64.so!p:}\|q``libjiagu_64.so!p:}\|q``libjiagu_64.so!p:}\|q``x8 ====0x7164da9f8c libjiagu_64.so!0x165f8c``x8 ====0x7164da5df0 libjiagu_64.so!0x161df0``x8 ====0x717c5093dc libart.so!_ZN3art3JNI25CallNonvirtualVoidMethodAEP7_JNIEnvP8_jobjectP7_jclassP10_jmethodIDP6jvalue``//奔溃` |
|-|-|

定位到我们的解释器sub_160D7C

## 定位opcode与解密

使用ida8.3进行动态调试

关键从0x1450fc处开始 ，从这里开始hook会遇到rtld_db_dlactivity反调试，而且会引导我们进入错误的分支。

tld_db_dlactivity函数默认情况下为空函数，当有调试器时将被改为断点指令。Android反调试对抗中，SIGTRAP信号反调试可通过判断该函数的数值来判断是否处于被调试状态

我们直接hook0x15a630，从这里开始调试，我们可以找到加密的opcode

![image](https://bbs.kanxue.com/upload/attach/202503/933207_M6PPY77XCP67ES4.png)

指向他地址的指针被存在x0寄存器之中

![image](https://bbs.kanxue.com/upload/attach/202503/933207_653BA8PK5D6GMZ3.png)

### 第一部分解密

sub_16CE0C是第一个解密函数

存在花指令，直接nop掉，重新定义为函数，对数据进行异或操作。

![image](https://bbs.kanxue.com/upload/attach/202503/933207_X73DEXU879V52CK.png)

步入跟踪，来到花指令后的代码

```
loc_16CF9C
ADR             X8, loc_16D09C
SUB             X8, X8, #236
LDR             X30, [SP,#0xA0+var_A0]
MOV             X30, X8
RET
```

**ADR（Address of Label）** 是 ARM64 特有的伪指令，用于**将当前 PC 相对的某个地址加载到寄存器**。

这里，它将 `loc_16D09C` 的地址加载到 `X8`，然后让 X8 的值减少 236（0xEC）

然后从栈中保存x30的地址，`X30` 通常用于**存储返回地址**，把 `X8`赋值给 `X30`，ret时就会返回我们设定的地址

进入真正的解密，解密逻辑为

从加密的opcode读取第一字节给w8，再从存加密opcode地址的地方读取第八个字节给w13 （c5）

w9存取的是加密的opcode读取第二字节，再减去w12（存加密opcode地址的地方读取第八个字节，和w13相等），这里结果为7

赋值，比较，与取`W9`低八位（07），相减，如果 `EQ`（ZF=1，前面 `TST` 结果是 0）`W8 = W11`（0xE2）否则`W8 = W10`（0xE7）

然后异或得w9=e5，保留 `W13` 低 8 位，来到左边分支，异或得到w10=6B

![image](https://bbs.kanxue.com/upload/attach/202503/933207_53JHW44SJPCNEQ5.png)

然后和之前一样的操作来到另外一部分解密操作，w8恢复到c5，把w9插入到w10的高位，然后把w8的低位复制到高位

然后w8和w10异或得到解密的opcode 20ae

![image](https://bbs.kanxue.com/upload/attach/202503/933207_Q3G7W2XNEQBZCJ7.png)

### 第二部分解密

把刚刚解密的opcode，和加密的opcode传入函数sub_15FC34，这里应该是下一步解密，来看看关键部分

x8赋值为主dex文件的地址，w9是存加密opcode地址+18的值（A0AF）,然后从主dex文件加载值w10 w8

W11 = W9 / W10 （整数除法）
W9 = W9 - (W11 * W10)（求余数）
W9 = W9 << 8 （左移 8 位）
然后X9 的低 8 位用 X19 的低 8 位替换得到最后值23AE，得到偏移

最后再从他查询得到值 D2赋值给w0

![image](https://bbs.kanxue.com/upload/attach/202503/933207_WRN8FD8YVNWJ22P.png)

接着会根据w0的值来进行二分查找。且这个值是会变化的，如果从前面的函数开始调试，会出现错误的值，正确查找来到解释器的位置。

解释器函数入参如下，重点关注a5 a6（加密的opcode）和a7 (已经解密的opcode),并且这里的a4就是我们之前得到的解密的主dex文件地址

| 12345678910111213141516 | `x0 MOV             W0,` `#3  ; n4` `1 MOV             W1, WZR ; a2``2 MOV             X2, X20 ; JNIEnv``3 MOV             X3, X21 ; a4``4 MOV             X4, X19 ; a5``5 MOV             X5, X22 ; a6``6 MOV             W6, W25 ; a7``7 MOV             X7, X28 ; a8``X0  0000000000000003``X1  0000000000000000``X2  0000007FC4CEE0A0 -> 0000007971A27800 -> 000000797C933118 (libart.so ! _ZN3art3JNI14NewObjectArrayEP7_JNIEnviP7_jclassP8_jobject)``X3  000000797CC43680 -> 0000007962CE6000 (debug003) -> (``"dex\n038"``)``X4  0000007971A26600 ([anon:libc_malloc]) -> 0000000000000000``X5  000000797CD00380 -> 00000079632ACEE0 (debug003) -> EA743718C721CC4E``X6  00000000000020AE``*X7  000000797CCE6C40 -> 0000007FC4CEE0A0 -> 0000007971A27800 -> [...] (libart.so ! _ZN3art3JNI14NewObjectArrayEP7_JNIEnviP7_jclassP8_jobject)` |
|-|-|

### 第三处解密

sub_16CB4C 存在同样的花指令，去除，函数和sub_16CE0C，套路都是一样的，直接从最后的真实逻辑开始分析

 X8 = X20 << 1（2），读取 X19+8 处的字节到 W13（c5），从 X26 + X8 处读取 1 字节到 W8（就是第三个加密的opcode21）

W9 = W9 - W12（c7-c5=2）,赋值，测试 W9 的 bit 5 是否为 1，W12 = W9 & 0xFF，W13 = W8 - W13，W8 = (Z == 1) ? W11 : W10

W9 = W8 XOR W12，W8 = W13 & 0xFF，W10 = W8 XOR W11（8E）

![image](https://bbs.kanxue.com/upload/attach/202503/933207_SJQPKYHUCHDZ8U7.png)

再来到，和之前的逻辑差不多，最后返回0x154b=5451

![image](https://bbs.kanxue.com/upload/attach/202503/933207_7E28YSGX69EZT7K.png)

而5451对应method_id 正是onCreate

### 第四处opcode解密

sub_16C918发现也存在异或，分析关键部分

w8读取第五六位的加密opcode，（3718）w9取其高位。

这里w12依旧是之前的c5，四处解密都是用的同一个密钥。

W9 = W9 - W12，W12 = W8 - W12，W8 = W9 & 0xFF，W9 = (Z == 1) ? W11 : W10，W8 = W9 XOR W8

W9 = W12 & 0xFF，后面的逻辑跟前面基本上一样，最后返回0x0021。

![image](https://bbs.kanxue.com/upload/attach/202503/933207_HJ8KBFCMJ3TRKNB.png)

## 总结

以上我们得到最后解密的opcode，逆序一下

ae20（d2）4b152100，这里d2是二分查找的关键。

与源apk的字节码对比，只有操作数不同。剩下的以此类推。

![image](https://bbs.kanxue.com/upload/attach/202503/933207_3A7NDVT6N5RFEMH.png)

参考：

[360加固dex解密流程分析 | oacia = oaciaのBbBlog~ = DEVIL or SWEET](https://oacia.dev/360-jiagu/)

[[原创]app加固分析狗尾续貂之dex vmp还原-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-285212.htm)

[[分享]某vmp壳原理分析笔记-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-225798.htm)

[[原创] 某DEX_VMP安全分析与还原-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-270799.htm)

[vmp入门(一)：android dex vmp还原和安全性论述](https://mp.weixin.qq.com/s/x6xIZ3cQ8fsVRpWORC45HA)

---

# 回复

## 回复 by 逆天而行 (#2)

*2025-3-13 17:28*

太强了！

## 回复 by 海带 (#3)

*2025-3-13 17:35*

图片好像寄了，图层要挂梯子

## 回复 by wx_‮ ‮ ‮ ‮ ‮ ‮ ‮ (#4)

*2025-3-15 20:25*

tql

## 回复 by 蓝色之冰 (#5)

*2025-3-15 22:10*

>
> [海带](https://bbs.kanxue.com/user-933207.htm)
>
>  图片好像寄了，图层要挂梯子
>
>

## 回复 by 软件君子 (#6)

*2025-3-16 16:19*

厉害的

## 回复 by 软件君子 (#7)

*2025-3-16 16:21*

有个思路 主动调用加固so＋文件重定向 能不能实现免修复vmp 相当于过签名校验

## 回复 by 海带 (#8)

*2025-3-17 13:34*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  软件君子](https://bbs.kanxue.com/user-992177.htm)
>
>  有个思路 主动调用加固so＋文件重定向 能不能实现免修复vmp 相当于过签名校验
>
>

复杂一点的应该就不行了

## 回复 by 墨穹呢 (#9)

*2025-3-17 18:44*

感谢分享

## 回复 by 花天狂骨 (#10)

*2025-3-17 19:20*

1

## 回复 by mb_vsnoaavk (#11)

*2025-3-24 19:21*

感谢分享

## 回复 by 好好好好尼玛 (#12)

*2025-7-28 16:34*

"与源apk的字节码对比，只有操作数不同。剩下的以此类推。"  ?
解密出来的opcode  "ae20（d2）4b152100 "， 怎么转换为 第一个 字节码 " 6f204c152100 " ?

## 回复 by ikunnn (#13)

*2025-11-10 22:32*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  好好好好尼玛](https://bbs.kanxue.com/user-794617.htm)
>
>  "与源apk的字节码对比，只有操作数不同。剩下的以此类推。" ?
> 解密出来的opcode "ae20（d2）4b152100 "， 怎么转换为 第一个 ...
>
>

找操作码映射关系吧我记得指令最前面两位好像是操作码吧，

## 回复 by 好好好好尼玛 (#14)

*2025-11-14 10:20*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  ikunnn](https://bbs.kanxue.com/user-1051261.htm)
>
>  找操作码映射关系吧我记得指令最前面两位好像是操作码吧，
>
>

几个月前我试过了，他这里没写完整。没有这么简单 “与源apk的字节码对比，只有操作数不同”。前面的二分 是两种情况，一个是 普通的指令直接自行实现如加减乘除，还一个是需要通过 art 接口调用jvm方法函数的指令。他这里走的都是第二种情况。

## 回复 by ikunnn (#15)

*2025-11-14 12:54*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  好好好好尼玛](https://bbs.kanxue.com/user-794617.htm)
>
>  几个月前我试过了，他这里没写完整。没有这么简单 “与源apk的字节码对比，只有操作数不同”。前面的二分 是两种情况，一个是 普通的指令直接自行实现如加减乘除，还一个是需要通过 art 接口调用jvm方 ...
>
>

你成功还原了吗兄弟

## 回复 by 好好好好尼玛 (#16)

*2025-11-14 16:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  ikunnn](https://bbs.kanxue.com/user-1051261.htm)
>
>  你成功还原了吗兄弟
>
>

不需要完全还原啊。通过看这里调用的 jni  的几个接口 就大致猜到那几行 dex代码了，我样本里面的oncreate总共也没多少行代码。这篇文章中的 总共好像是～21条指令，这里的断点只有～7个被断住了，即只有第二种情况。

## 回复 by ikunnn (#17)

*2025-11-14 22:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  好好好好尼玛](https://bbs.kanxue.com/user-794617.htm)
>
>  不需要完全还原啊。通过看这里调用的 jni 的几个接口 就大致猜到那几行 dex代码了，我样本里面的oncreate总共也没多少行代码。这篇文章中的 总共好像是～21条指令，这里的断点只有～7个被断 ...
>
>

兄弟你可以私信我吗，我等级不够，我想加你要个联系方式，我最近正在研究vmp相关的，我有一些问题想请教，谢谢

## 回复 by ikunnn (#18)

*2025-11-14 22:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  好好好好尼玛](https://bbs.kanxue.com/user-794617.htm)
>
>  不需要完全还原啊。通过看这里调用的 jni 的几个接口 就大致猜到那几行 dex代码了，我样本里面的oncreate总共也没多少行代码。这篇文章中的 总共好像是～21条指令，这里的断点只有～7个被断 ...
>
>

那也就是说根据jni日志就差不多知道大致了对吧

## 回复 by ikunnn (#19)

*2025-11-15 10:39*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  好好好好尼玛](https://bbs.kanxue.com/user-794617.htm)
>
>  不需要完全还原啊。通过看这里调用的 jni 的几个接口 就大致猜到那几行 dex代码了，我样本里面的oncreate总共也没多少行代码。这篇文章中的 总共好像是～21条指令，这里的断点只有～7个被断 ...
>
>

哥能不能加个联系方式![image](https://bbs.kanxue.com/view/img/face/001.gif)
