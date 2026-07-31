---
title: '[分享]某咖啡DFA AES+ollvm混淆分析'
url: https://bbs.kanxue.com/thread-284992.htm
tid: 284992
author: 绿豆粥
date: '2024-12-26'
tags: [Android安全, 分享, 逆向分析]
crawled_at: '2026-07-31T14:15:40+08:00'
replies: 7
---

# 前言

本文目标 app 使用了 白盒 AES，且进行了一定程度的 ollvm。使用 unidbg 作为主要的分析工具，配合 DFA 攻击找到了 AES的 key。

# 关键参数定位

登录接口：<https://capi.xxxxx.com/resource/m/user/login>

版本：5001

目标参数 ：sign 和 q

![image-20241216104140721](https://bbs.kanxue.com/upload/attach/202412/791353_44GQ9P4299QH6R3.png)

jadx 打开 apk。这标致 某60的加固。

![image-20241216104500964](https://bbs.kanxue.com/upload/attach/202412/791353_FM25DF2RZ43F8VR.png)

拿出神器 xrt 脱壳完成之后搜索 sign ，没找到。可能是字符串做了加密。换方案，使用 hook 。

![image-20241216102701992](https://bbs.kanxue.com/upload/attach/202412/791353_Z7VYAP8WYHFJ5QY.png)

| 123456789101112 | `function` `call_HashMap() {``Java.perform(``function` `() {``var` `hashMap = Java.use(``"java.util.HashMap"``);``hashMap.put.implementation =` `function` `(a, b) {``if` `(a !=` `null` `&& a.equals(``"sign"``)) {``console.log(Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Throwable"``).$``new``()))``console.log(``"hashMap.put: "``, a, b);``}``return` `this``.put(a, b);``}``})``}` |
|-|-|

分析有包名的地方

![image-20241216105607449](https://bbs.kanxue.com/upload/attach/202412/791353_M97PJ8STG4G3PME.png)

从 com.lucky.lib.http2.AbstractLcRequest.getRequestParams 开始分析 。有几个可疑的数值，写个主动调用看看是什么。

![image-20241216105754525](https://bbs.kanxue.com/upload/attach/202412/791353_3STMXD774Y6SUA3.png)

| 1234567891011121314 | `function` `call_so() {``Java.perform(``function` `() {``var` `Class = Java.use(``'com.stub.StubApp'``);``// var result = Class['getString2']('7719'); //sign``// console.log(result);``// var result = Class['getString2']('16944'); // uid``// console.log(result);``// var result = Class['getString2']('4005'); // cid``// console.log(result);``// var result = Class['getString2']('457'); // q``// var result = Class['getString2']('30491'); // cryptoDD``console.log(result);``})``}` |
|-|-|

![image-20241225100216448](https://bbs.kanxue.com/upload/attach/202412/791353_DG5HNQS3EF72V39.png)

先分析 q ，它来自 b2，b2从 c.b 的函数来。

![image-20241225100315389](https://bbs.kanxue.com/upload/attach/202412/791353_5XBTA58HWMTH44Z.png)

![image-20241225100454250](https://bbs.kanxue.com/upload/attach/202412/791353_WGKJC2HYFN78YNQ.png)

看到这里有两个aes加密，且最后函数返回的时候，还做了 base64 的编码。把 + 替换成 - 。把 / 替换成 _ 。

继续跟进。两个都是 native 层的函数了。具体是调用了那个函数，之后通过 hook 就可以知道。

![image-20241225100707796](https://bbs.kanxue.com/upload/attach/202412/791353_3HSKWZGQCQ6SFVS.png)

再回头分析 sign 。 7719 是我们的目标参数 sign 。那么就跟进后面的函数 r.a() 。

![image-20241225100216448](https://bbs.kanxue.com/upload/attach/202412/791353_DG5HNQS3EF72V39.png)

![image-20241225101039903](https://bbs.kanxue.com/upload/attach/202412/791353_K3K59D3HGFTHXNM.png)

同样进入了 CryptoHelper

![image-20241225101133345](https://bbs.kanxue.com/upload/attach/202412/791353_T5SGSFVWVGNYEMT.png)

这个函数最后面调用了 md5_crypt ，也是个 native 函数。md5_crypt 第二个参数应该传入的是 int 型，有兴趣的可以打印输出一下。

![image-20241225101258429](https://bbs.kanxue.com/upload/attach/202412/791353_7VX9M5G6VB8S5G7.png)

到这里我们可以大概做了总结 sign 来自 md5_crypt 结果， q 值来自 aes 的结果。

分辨 hook CryptoHelper 中的几个 native 函数。看看在登录接口使用了哪个函数。

| 123456789101112131415161718192021222324252627282930313233343536 | `function` `crypt_test() {` `Java.perform(``function` `() {``if` `(Java.available) {``let CryptoHelper = Java.use(``"com.luckincoffee.safeboxlib.CryptoHelper"``);``CryptoHelper[``"localAESWork"``].implementation =` `function` `(bArr, i2, bArr2) {``console.log(`CryptoHelper.localAESWork is called: bArr=${bytesToString(bArr)}, i2=${i2}, bArr2=${bArr2}`);``// console.log(`CryptoHelper.localAESWork is called: bArr=${bArr}, i2=${i2}, bArr2=${bArr2}`);``let result =` `this``[``"localAESWork"``](bArr, i2, bArr2);``// console.log(`CryptoHelper.localAESWork result=${result}`);``return` `result;``};` `CryptoHelper[``"localAESWork4Api"``].implementation =` `function` `(bArr, i2) {``console.log(`CryptoHelper.localAESWork4Api is called: bArr=${bytesToString(bArr)}, i2=${i2}`);``let result =` `this``[``"localAESWork4Api"``](bArr, i2);``// console.log(`CryptoHelper.localAESWork4Api result=${result}`);``return` `result;``};``CryptoHelper[``"localConnectWork"``].implementation =` `function` `(bArr, bArr2) {``console.log(`CryptoHelper.localConnectWork is called: bArr=${bytesToString(bArr)}, bArr2=${bArr2}`);``let result =` `this``[``"localConnectWork"``](bArr, bArr2);``// console.log(`CryptoHelper.localConnectWork result=${result}`);``return` `result;``};``CryptoHelper[``"md5_crypt"``].implementation =` `function` `(bArr, i2) {``console.log(`CryptoHelper.md5_crypt is called: bArr=${bytesToString(bArr)}, i2=${i2}`);``let result =` `this``[``"md5_crypt"``](bArr, i2);``// console.log(`CryptoHelper.md5_crypt result=${result}`);``return` `result;``};``}``})`  `}` |
|-|-|

hook 之后发现 先调用了 localAESWork4Api 再调用了 md5_crypt。也就可以理解为先生成 q 再生成 sign

![image-20241216113453394](https://bbs.kanxue.com/upload/attach/202412/791353_TPQMXX29F45ZTCB.png)

接下来就进入 native 层分析

# native 层分析

so 导入 IDA 搜索 java 没有找到导出函数

![image-20241224151629825](https://bbs.kanxue.com/upload/attach/202412/791353_8CRXHCA74QQ3HHR.png)

翻了 davadiv 这个特征，这是 ollvm 的特征，说明 so 的代码被混淆了。不过依然是可以分析的。

首先需要找到入口函数的地址。这里肯定是就是动态注册函数了。有两种方案获取到对应的地址，第一 unidbg 第二通过 frida Hook RegisterNative 获取到对应的地址。两种都演示一下

1. 通过 unidbg

这里运气比较好，这个SO 不用补环境就可以跑起来

| 1234567891011121314151617181920212223242526272829303132 | `public` `class` `fkLucky` `extends` `AbstractJni {``private` `AndroidEmulator emulator;``private` `VM vm;``private` `final` `Module module;` `public` `fkLucky() {``emulator = AndroidEmulatorBuilder.for32Bit()``.setProcessName(``"com.lucky.luckyclient"``)``.build();`  `final` `Memory memory = emulator.getMemory();``memory.setLibraryResolver(``new` `AndroidResolver(``23``));`  `vm = emulator.createDalvikVM(``new` `File(``"unidbg-android/src/test/java/com/com/cloudy/linglingbang/linglingbang8.2.4.apk"``));``vm.setJni(``this``);``vm.setVerbose(``true``);`  `DalvikModule dm = vm.loadLibrary(``new` `File(``"unidbg-android/src/test/java/com/com/lucky/luckyclient/libcryptoDD5001.so"``),` `true``);``//如果 so 中依赖了 app 的其他 so，可以使用这种方式加载，unidbg 会自动取寻找对应的so``//        DalvikModule dm = vm.loadLibrary(new File("encrypt"),true);``module = dm.getModule();``dm.callJNI_OnLoad(emulator);``}`  `public` `static` `void` `main(String[] args) {``fkLucky lucky =` `new` `fkLucky();``}``}` |
|-|-|

![image-20241224151938734](https://bbs.kanxue.com/upload/attach/202412/791353_Q736FW348YDKDUC.png)

注册了 4 个函数

1. frida Hook

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546 | `function` `hook_dynamic_register_func() {``// 获取 RegisterNatives 函数的内存地址，并赋值给addrRegisterNatives。``var` `addrRegisterNatives =` `null``;``var` `symbols = Module.enumerateSymbolsSync(``"libart.so"``);``for` `(``var` `i = 0; i < symbols.length; i++) {``var` `symbol = symbols[i];``if` `(symbol.name.indexOf(``"art"``) >= 0 &&``symbol.name.indexOf(``"JNI"``) >= 0 &&``symbol.name.indexOf(``"RegisterNatives"``) >= 0 &&``symbol.name.indexOf(``"CheckJNI"``) < 0) {``addrRegisterNatives = symbol.address;``console.log(``"RegisterNatives is at "``, symbol.address, symbol.name);``break``}``}``if` `(addrRegisterNatives) {``Interceptor.attach(addrRegisterNatives, {``onEnter:` `function` `(args) {``var` `env = args[0];` `// jni对象``var` `java_class = args[1];` `// 类``var` `class_name = Java.vm.tryGetEnv().getClassName(java_class);``var` `taget_class =` `"com.luckincoffee.safeboxlib.CryptoHelper"``;` `//111 某个类中动态注册的so``if` `(class_name === taget_class) {``console.log(``"\n[RegisterNatives] method_count:"``, args[3]);``var` `methods_ptr = ptr(args[2]);``var` `method_count = parseInt(args[3]);``for` `(``var` `i = 0; i < method_count; i++) {``// Java中函数名字的``var` `name_ptr = Memory.readPointer(methods_ptr.add(i * Process.pointerSize * 3));``// 参数和返回值类型``var` `sig_ptr = Memory.readPointer(methods_ptr.add(i * Process.pointerSize * 3 + Process.pointerSize));``// C中的函数内存地址``var` `fnPtr_ptr = Memory.readPointer(methods_ptr.add(i * Process.pointerSize * 3 + Process.pointerSize * 2));``var` `name = Memory.readCString(name_ptr);``var` `sig = Memory.readCString(sig_ptr);``var` `find_module = Process.findModuleByAddress(fnPtr_ptr);``// 地址、偏移量、基地址``var` `offset = ptr(fnPtr_ptr).sub(find_module.base);``console.log(``'class_name:'``, class_name,` `"name:"``, name,` `"sig:"``, sig,` `'module_name:'``, find_module.name,` `"offset:"``, offset);``}``}``}``});``}` `}` |
|-|-|

![image-20241224152546391](https://bbs.kanxue.com/upload/attach/202412/791353_MQA9T3X2YZAKX9N.png)

同样可以看到注册了 4 个函数

# 参数 q

使用 unidbg 进行算法分析。

前面的 unidbg 运行起来后最前面有一行日志

![image-20241224153310103](https://bbs.kanxue.com/upload/attach/202412/791353_5NPH3Q3WVYP4NMZ.png)

加载了 libandroid.so 失败，这个 so 是android 系统自带的 so 。同时它也依赖了很多其他的 so 。不好同时都导入。这里使用 unidbg 的VirtualModule 导入一个虚拟的 so。就没有这个错误日志了

![image-20241224153556486](https://bbs.kanxue.com/upload/attach/202412/791353_XAKQV68S7PA587U.png)

主动调用算法 localAESWork4Api

| 1234567891011121314151617 | `private` `void` `callNativeFunc() {``//args``List<Object> args =` `new` `ArrayList<>(``10``);``args.add(vm.getJNIEnv());``args.add(``0``);``//jclass` `String par1 =` `"lvdouzhou"``;``args.add(vm.addLocalObject(``new` `ByteArray(vm, par1.getBytes())));` `args.add(``0``);``//最后一个参数` `//主动调用功能``Number retNum = module.callFunction(emulator,``0x1b1cd``,args.toArray());``ByteArray retByteArr = vm.getObject(retNum.intValue());``String retStr = Base64.getEncoder().encodeToString(retByteArr.getValue());``System.out.println(``"retBs64:"``+retStr);``}` |
|-|-|

![image-20241224154238287](https://bbs.kanxue.com/upload/attach/202412/791353_J57BCUT5VAWVNHZ.png)

IDA 分析SO 。入口在 localAESWork4Api 0x1b1cd，IDA 中 按 G 跳转。这个函数看着名字像白盒 AES

![image-20241224152739481](https://bbs.kanxue.com/upload/attach/202412/791353_SYU6W8V7NB266YZ.png)

一眼看过去 就是调用了 android_native_wbaes_jni ，进入分析。

![image-20241224154433228](https://bbs.kanxue.com/upload/attach/202412/791353_N8M8STDG2CVNB4C.png)

这个函数里面有很多的虚假控制流，不能按常规的直接直接分析。我们向下滑动看看有没有什么特征函数。

![image-20241224154544420](https://bbs.kanxue.com/upload/attach/202412/791353_7DE2XWMDCQG7WNY.png)

可以看到 PKCS5Padding wbaes_decrypt_ecb 。继续向下看看有没有加密的

![image-20241224154743044](https://bbs.kanxue.com/upload/attach/202412/791353_ZYP6RBDJ89SJUBN.png)

找到了 wbaes_encrypt_ecb ，这个好了 ecb 不用找 iv 了。下个断点看看情况，目标地址 17BD4。

![image-20241224154846093](https://bbs.kanxue.com/upload/attach/202412/791353_B4629FWBDXMGTRH.png)

| 12345678910 | `private` `void` `hookNativeFunc() {``Debugger debugger = emulator.attach();``// wbaes_encrypt_ecb``debugger.addBreakPoint(module.base +` `0x17BD4``,` `new` `BreakPointCallback() {``@Override``public` `boolean` `onHit(Emulator<?> emulator,` `long` `address) {``return` `false``;``}``});``}` |
|-|-|

第一个参数是传入的要加密的数据，第二参数是数据的长度，第三个参数返回的数据，第四个参数是 mode =0

![image-20241224155612171](https://bbs.kanxue.com/upload/attach/202412/791353_8FGVNZXDSRJBT93.png)

r1=0x10 也就是十进制的 16 ，表示一个分组的长度 。AES 一个分组长度固定是 16字节 。

再看看第一个参数，确实是我们的数据。整个数据 16 字节，填充了 07 。传入的是 lvdouzhou 长度为 6 ，16 -9 = 7 。十六进制就是 0x07。刚好印证了前面的 PKCS5 填充。

![image-20241224155447737](https://bbs.kanxue.com/upload/attach/202412/791353_JETQB9THBSZAVAS.png)

再验证一个是否是 ECB 模式。ECB 模式将明文数据分成固定大小的块，然后对每个块独立进行加密。也是因为每一块是独立加密的，所以如果有两个 16 字节的数据是相同的，加密的结果也相同。根据这一个特点，修改入参为两个 相同的16字节数据 lvdouzhoulvdouzhlvdouzhoulvdouzh。

![image-20241224161021144](https://bbs.kanxue.com/upload/attach/202412/791353_VS9THRB8ZHYFHXX.png)

lr 寄存器存放是函数返回的地址。在 lr 下一个断点，就可以知道这个函数返回的数据。在命令输入 blr 回车之后，按 c 继续执行。函数执完返回时，会自动触发断点。

![image-20241224161155464](https://bbs.kanxue.com/upload/attach/202412/791353_XF5EPBDSMJBJYZC.png)

第三个参数是返回值 也就是 mr2 的地址

![image-20241224161307880](https://bbs.kanxue.com/upload/attach/202412/791353_CNB3DC3JGHCBXJ3.png)

读取这个地址的数据

![image-20241224161337417](https://bbs.kanxue.com/upload/attach/202412/791353_AQT82QB6C7RN36C.png)

可以看到两个 16 字节的数据都是相同的，确认是 ecb 模式啦 ！

接着这个函数继续分析 ，依然是控制流平坦化，也就是 ollvm 。先跟着参数分析一下，第三个是返回值，我们选中它。按 x 查看引用。

![image-20241224161859372](https://bbs.kanxue.com/upload/attach/202412/791353_5Y3C5QV6Y8VJW5V.png)

先看第一个引用

![image-20241224161918873](https://bbs.kanxue.com/upload/attach/202412/791353_2XZJ73Y3JP8J5UE.png)

应该是把 v29 复制给了 out 。x 查看 v29 的引用。我们往前查看引用，因为 v29 一定是在前面生成的。

![image-20241224162024275](https://bbs.kanxue.com/upload/attach/202412/791353_UUR93K7HT367WG6.png)

![image-20241224162037877](https://bbs.kanxue.com/upload/attach/202412/791353_5KMPJMATJMYRX3H.png)

找到了 aes128_enc_wb_coff ，一目了然 aes 算法。没什么说的，继续跟进。

![image-20241224162156686](https://bbs.kanxue.com/upload/attach/202412/791353_DXC2JNEXRV2FDXP.png)

大概浏览一下，也是做了 ollvm 混淆。但是还有很多特征的。例如看到一个 行位移。

![image-20241224162553751](https://bbs.kanxue.com/upload/attach/202412/791353_P4PJP97BVSK4PE6.png)

其中的 Tboxes 通过名字猜测可能是 aes 的查表法。

>
> AES 的某些步骤（如字节替换和列混淆）可以通过预先计算的表格来实现，从而避免在运行时进行复杂的计算。
>
>
>

点击跳转过去也是一个很大的数组，应该就是提前计算好的数据了。

![image-20241224162452916](https://bbs.kanxue.com/upload/attach/202412/791353_P74PSGZMQX37VJS.png)

到这里可以确定是一个白盒的 AES，使用的的 ecb 模式。

## DFA 攻击

确认十轮运算的位置 。因为里面有两个 wbShiftRows 分别 hook 看那个是我们目标攻击点。

0x15AD6 0x154E8

![image-20241224163520085](https://bbs.kanxue.com/upload/attach/202412/791353_3N4NSYN8TK33BZK.png)

![image-20241224163507471](https://bbs.kanxue.com/upload/attach/202412/791353_A6N72FDZERZWWTV.png)

0x15AD6 没有走。0x154E8 进入了 10 ，记得把入参限制在16 个字节内，让 AES 加密一次即可。

![image-20241224163821540](https://bbs.kanxue.com/upload/attach/202412/791353_96E4W7MYWEK79J8.png)

dfa 攻击。在第 9 轮循环注入我们的故障文。通过 Inspect 确定一下注入是否正常

| 123456789101112131415161718192021 | `private` `void` `call_dfa() {``// void __fastcall wbShiftRows(uint8_t *out)``// 这个函数的入参就是明文 state``emulator.attach().addBreakPoint(module.base +` `0x14F98``,` `new` `BreakPointCallback() {``int` `count =` `0``;``UnidbgPointer r0pointer;``RegisterContext ctx = emulator.getContext();``@Override``public` `boolean` `onHit(Emulator<?> emulator,` `long` `address) {``r0pointer =  ctx.getPointerArg(``0``);``count++;``if` `(count %` `9` `==` `0``) {``System.out.println(``"hit-> "``+count);``Inspector.inspect(r0pointer.getByteArray(``0``,``16``),``"r0pointer->before"``);``r0pointer.setByte(randint(``0``,``15``),(``byte``)randint(``0``,``0xff``));``Inspector.inspect(r0pointer.getByteArray(``0``,``16``),``"r0pointer->after"``);``}``return` `true``;``}``});``}` |
|-|-|

可以看到只影响了一个字节的数据，达到了预期。

![image-20241224174915209](https://bbs.kanxue.com/upload/attach/202412/791353_4SCRM2NUSBJ4HPC.png)

对比最终结果。影响了 4 个字节，达到了预期 。

![image-20241224174821962](https://bbs.kanxue.com/upload/attach/202412/791353_9CCTJ3T2TWDBH6C.png)

批量注入故障文，获取故障结果

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159 | `public` `class` `fkLucky` `extends` `AbstractJni {``private` `AndroidEmulator emulator;``private` `VM vm;``private` `final` `Module module;` `public` `fkLucky() {``emulator = AndroidEmulatorBuilder.for32Bit()``.setProcessName(``"com.lucky.luckyclient"``)``.build();`  `final` `Memory memory = emulator.getMemory();``memory.setLibraryResolver(``new` `AndroidResolver(``23``));`  `vm = emulator.createDalvikVM(``new` `File(``"unidbg-android/src/test/java/com/com/cloudy/linglingbang/linglingbang8.2.4.apk"``));``vm.setJni(``this``);``vm.setVerbose(``true``);` `new` `AndroidModule(emulator, vm).register(memory);``DalvikModule dm = vm.loadLibrary(``new` `File(``"unidbg-android/src/test/java/com/com/lucky/luckyclient/libcryptoDD5001.so"``),` `true``);``//如果 so 中依赖了 app 的其他 so，可以使用这种方式加载，unidbg 会自动取寻找对应的so``module = dm.getModule();``dm.callJNI_OnLoad(emulator);``}` `private` `void` `callNativeFunc() {``//args``List<Object> args =` `new` `ArrayList<>(``10``);``args.add(vm.getJNIEnv());``args.add(``0``);``//jclass` `//        String par1 = "lvdouzhoulvdouzhlvdouzhoulvdouzh";``String par1 =` `"lvdouzhou"``;``args.add(vm.addLocalObject(``new` `ByteArray(vm, par1.getBytes())));` `args.add(``0``);``//最后一个参数` `//主动调用功能``Number retNum = module.callFunction(emulator,` `0x1b1cd``, args.toArray());``ByteArray retByteArr = vm.getObject(retNum.intValue());``String retStr = Base64.getEncoder().encodeToString(retByteArr.getValue());``System.out.println(``"retBs64:"` `+ retStr);``}` `public` `static` `String bytesToHex(``byte``[] bytes) {``StringBuilder sb =` `new` `StringBuilder();``for` `(``byte` `b : bytes) {``int` `unsignedInt = b &` `0xff``;``String hex = Integer.toHexString(unsignedInt);``if` `(hex.length() ==` `1``) {``sb.append(``'0'``);``}``sb.append(hex);``}``return` `sb.toString();``}` `public` `static` `byte``[] hexToBytes(String hexString) {``// 将十六进制字符串转换为字节数组``return` `DatatypeConverter.parseHexBinary(hexString);``}` `private` `void` `call_wbaes_encrypt_ecb() {``//调用  wbaes_encrypt_ecb``MemoryBlock inputBlock = emulator.getMemory().malloc(``16``,` `true``);``UnidbgPointer inDataPointer = inputBlock.getPointer();``MemoryBlock outputBlock = emulator.getMemory().malloc(``16``,` `true``);``UnidbgPointer outDataPointer = inputBlock.getPointer();``// 传入的数据要填充满``byte``[] inByteData = hexToBytes(``"6c76646f757a686f7507070707070707"``);``//lvdouzhou``assert` `inByteData !=` `null``;``inDataPointer.write(``0``, inByteData,` `0``, inByteData.length);``//wbaes_encrypt_ecb(const uint8_t *in, uint32_t in_len, uint8_t *out, uint32_t mode)``module.callFunction(emulator,` `0x17bd5``, inDataPointer,` `16``, outDataPointer,` `0``);` `String ret = bytesToHex(outDataPointer.getByteArray(``0``,` `0x10``));``//16字节``System.out.println(ret);``inputBlock.free();``;``outputBlock.free();` `}` `private` `void` `hookNativeFunc() {``Debugger debugger = emulator.attach();``// wbaes_encrypt_ecb``debugger.addBreakPoint(module.base +` `0x17BD4``,` `new` `BreakPointCallback() {``@Override``public` `boolean` `onHit(Emulator<?> emulator,` `long` `address) {``return` `false``;``}``});``}` `private` `void` `dfa() {``Debugger debugger = emulator.attach();``debugger.addBreakPoint(module.base +` `0x154E8``,` `new` `BreakPointCallback() {``int` `count =` `0``;` `@Override``public` `boolean` `onHit(Emulator<?> emulator,` `long` `address) {``RegisterContext ctx = emulator.getContext();``count++;``System.out.println(``"0x154E8->"` `+ count);` `// 在函数返回的地方下断点，获取到返回值``emulator.attach().addBreakPoint(ctx.getLRPointer().peer,` `new` `BreakPointCallback() {``@Override``public` `boolean` `onHit(Emulator<?> emulator,` `long` `address) {` `return` `true``;``}``});``return` `true``;``}``});``}` `public` `static` `int` `randint(``int` `min,` `int` `max) {``Random rand =` `new` `Random();``return` `rand.nextInt((max - min) +` `1``) + min;``}` `private` `void` `call_dfa() {``// void __fastcall wbShiftRows(uint8_t *out)``// 这个函数的入参就是明文 state``emulator.attach().addBreakPoint(module.base +` `0x14F98``,` `new` `BreakPointCallback() {``int` `count =` `0``;``UnidbgPointer r0pointer;``RegisterContext ctx = emulator.getContext();` `@Override``public` `boolean` `onHit(Emulator<?> emulator,` `long` `address) {``r0pointer = ctx.getPointerArg(``0``);``count++;``if` `(count %` `9` `==` `0``) {``//                    System.out.println("hit-> "+count);``//                    Inspector.inspect(r0pointer.getByteArray(0,16),"r0pointer->before");``r0pointer.setByte(randint(``0``,` `15``), (``byte``) randint(``0``,` `0xff``));``//                    Inspector.inspect(r0pointer.getByteArray(0,16),"r0pointer->after");``}``return` `true``;``}``});``}` `public` `static` `void` `main(String[] args) {``fkLucky lucky =` `new` `fkLucky();``//        lucky.hookNativeFunc();``//        lucky.dfa();``//        lucky.callNativeFunc();` `for` `(``int` `i =` `0``; i <` `200``; i++) {``lucky.call_dfa();``lucky.call_wbaes_encrypt_ecb();``}``}``}` |
|-|-|

的到的故障文，第一行放入正确的密文

![image-20241224175047478](https://bbs.kanxue.com/upload/attach/202412/791353_8M8KBSX8DHQWYJV.png)

使用 phoenixAES 推到 k10

| 123 | `import` `phoenixAES` `phoenixAES.crack_file(r``".\ruixin5001dfa.log"``,[],``True``,``False``,verbose``=``2``)` |
|-|-|

![image-20241224175100141](https://bbs.kanxue.com/upload/attach/202412/791353_QVBVDCAZ7CVBB9M.png)

用phoenixAES库得到第10轮秘钥 869D92BBB700D0D25BD9FD3E224B5DF2。

在用 stark 推导 k00

| 1 | `.\starkAES.exe 869D92BBB700D0D25BD9FD3E224B5DF2  10` |
|-|-|

![image-20241224171634905](https://bbs.kanxue.com/upload/attach/202412/791353_9T2VD5ZY8Y4WUEA.png)

推导出的秘钥为 644A4C64434A69566E44764D394A5570

验证一下

![image-20241224175203189](https://bbs.kanxue.com/upload/attach/202412/791353_VENCJDXV7U33V7E.png)

没问题，和正常密文一样。

## 验证结果

重新hook一下 java层获取到实际的入参

| 12345678910111213141516171819202122232425262728293031323334353637 | `function` `bytesToHex(arr) {``/**``* byte 转换成 hex``*/``var` `str =` `''``;``var` `k, j;``for` `(``var` `i = 0; i < arr.length; i++) {``k = arr[i];``j = k;``if` `(k < 0) {``j = k + 256;``}``if` `(j < 16) {``str +=` `"0"``;``}``str += j.toString(16);``}``return` `str;``}``function` `crypt_test() {` `Java.perform(``function` `() {``if` `(Java.available) {``let CryptoHelper = Java.use(``"com.luckincoffee.safeboxlib.CryptoHelper"``);` `CryptoHelper[``"localAESWork4Api"``].implementation =` `function` `(bArr, i2) {``console.log(`CryptoHelper.localAESWork4Api is called: bArr=${bytesToString(bArr)}, i2=${i2}`);``let result =` `this``[``"localAESWork4Api"``](bArr, i2);``console.log(`CryptoHelper.localAESWork4Api result=${bytesToHex(result)}`);``return` `result;``};` `}``})`  `}` |
|-|-|

![image-20241225094309296](https://bbs.kanxue.com/upload/attach/202412/791353_M56KV727R96ZVRQ.png)

>
> {"blackBox":"eyJvcyI6ImFuZHJvaWQiLCJ2ZXJzaW9uIjoiMy4zLjciLCJwYWNrYWdlcyI6ImNvbS5sdWNreS5sdWNreWNsaWVudComNS4wLjAxIiwicHJvZmlsZV90aW1lIjoxNDcsImludGVydmFsX3RpbWUiOjIxNzMsInRva2VuX2lkIjoibk9cL2VhbHJjQkY2WU5wUGF0dDk4Q292T1FUYkRFUEM4NHFVM1ozSThLa2xcL1RNb1J1WUZWcGd6QVwvOGZ4T01zcHJvYXFmaEZXSWpNb2RHWENnYkw3SzFHYzBTdDY2cjFpZE5tNXFJS1Zkc2M9In0=","uniqueCode":"DU5SBJsdw1JfKSzzQ22IzTIOzNbvm6BpYQd8RFU1U0JKc2R3MUpmS1N6elEyMkl6VElPek5idm02QnBZUWQ4c2h1","regionId":"CO0001","mobile":"15712170935","countryNo":"86","validateCode":"111111","regId":"","appversion":"5001","type":1,"deviceId":"android_lucky_d169e58de60a856d","systemVersion":"29","deviceBrand":"google"},
>
>
>

返回值

>
> f2947f561248ad6af3fed66d57a0421d589a5be55cb087a6d4713acfbc4d458c95b4af52a9682bae07dbde2164288106b1fad28d1ddd4215d24cb5460911c48a0b122278984d473519b59a3cc4b594e63dbd9db1df3d262bb80dcdaf6553d87c37e4b306663585e7a3030a4a01a186657729123bd72acb773f17a4567cbdb829c991f5ba5546edf952866d04b57aff503d0ff0e69370466258da89bffa296987510c12704172f9d3f276ec47556dad9c251342d87b938188ebc3489241795ae0e8cf5d3dafbebbeff75731fe42ed3452f081275c8632fe1b9a4447f5bb40c3f1fd5f0e29416f5548fc64f5e15460d58aa5fbd9de0d44edaf5e502efee22e2df8ebe38fef2d839b2c9a4c9c10433eb0f8751705162db79cf73ea6c25ce3c96df92a674c84bf65fc92073df7d305d81ab94039e8c655d9fe253147db3197def0b970ddd0744b4ef458ed9c5ac523643c276662a0a7cec3a5a28b17b7b601f9e012640b82cbbd195205c62da34d2e82632d5c2233b242c2bbf38ea17bfe68def166e850c806de0c018ce2cbcfc6a6bb05fa79a1f2c73fc309bd70bb57b48942aff1c17534ec96cddfa265e32baa759553bdf0f2f1af9ba704e52f5977a132cb157bab0700b6d61e0749fca0f5ef1bc870915de3862bb151a9b9af3b17eb3cd369109072a14f977d43fb82069b09578cb28c6e325ac12e917dcf135f89d815bd429aef6ef28bb6d7d89adeea1d4f5106b03e316b7afd934630f4138bcba2a9dfc7d79c5bdcd9a1c8e4791e698e2dde4063dff86f2a8f5e8ad9a7089bdf6121995f82e8a15896b6f883f9b41fda7a1a820074caa3b13027d7945012ba38fa4e3c97bc13ad3e6d747936475b59990c8aa2f02c20f4e2e3eaf18d0cc2339bb457db167fae462346059e4c1153d3ca59aba55108
>
>
>

修改 unidbg的入参

| 12345678910111213141516171819 | `private` `void` `callNativeFunc() {``//args``List<Object> args =` `new` `ArrayList<>(``10``);``args.add(vm.getJNIEnv());``args.add(``0``);``//jclass` `//        String par1 = "lvdouzhoulvdouzhlvdouzhoulvdouzh";``//        String par1 = "lvdouzhou";``String par1 =` `"{\"blackBox\":\"eyJvcyI6ImFuZHJvaWQiLCJ2ZXJzaW9uIjoiMy4zLjciLCJwYWNrYWdlcyI6ImNvbS5sdWNreS5sdWNreWNsaWVudComNS4wLjAxIiwicHJvZmlsZV90aW1lIjoxNDcsImludGVydmFsX3RpbWUiOjIxNzMsInRva2VuX2lkIjoibk9cL2VhbHJjQkY2WU5wUGF0dDk4Q292T1FUYkRFUEM4NHFVM1ozSThLa2xcL1RNb1J1WUZWcGd6QVwvOGZ4T01zcHJvYXFmaEZXSWpNb2RHWENnYkw3SzFHYzBTdDY2cjFpZE5tNXFJS1Zkc2M9In0=\",\"uniqueCode\":\"DU5SBJsdw1JfKSzzQ22IzTIOzNbvm6BpYQd8RFU1U0JKc2R3MUpmS1N6elEyMkl6VElPek5idm02QnBZUWQ4c2h1\",\"regionId\":\"CO0001\",\"mobile\":\"15712170935\",\"countryNo\":\"86\",\"validateCode\":\"111111\",\"regId\":\"\",\"appversion\":\"5001\",\"type\":1,\"deviceId\":\"android_lucky_d169e58de60a856d\",\"systemVersion\":\"29\",\"deviceBrand\":\"google\"}"``;``args.add(vm.addLocalObject(``new` `ByteArray(vm, par1.getBytes())));` `args.add(``0``);``//最后一个参数` `//主动调用功能``Number retNum = module.callFunction(emulator,` `0x1b1cd``, args.toArray());``ByteArray retByteArr = vm.getObject(retNum.intValue());``String retHex = bytesToHex(retByteArr.getValue());``//16字节``System.out.println(``"retHex->"``+retHex);``}` |
|-|-|

得到结果

![image-20241225094557882](https://bbs.kanxue.com/upload/attach/202412/791353_PKKQSAHAJKN5FNJ.png)

一毛一样

![image-20241225094646772](https://bbs.kanxue.com/upload/attach/202412/791353_WSTYVZFZBTUQRHP.png)

自此 q 就分析出来啦 。需要注意的是，根据之前 java 层的分析，生成 q 之后要进行 base64 编码。且替换掉对应的字符串

![image-20241225100454250](https://bbs.kanxue.com/upload/attach/202412/791353_WGKJC2HYFN78YNQ.png)

# 参数 sign

参数 sign 来自 md5 ，前面知 md_crypt 的地址是 0x1a981

![image-20241224151938734](https://bbs.kanxue.com/upload/attach/202412/791353_Q736FW348YDKDUC.png)

先主动调用

| 12345678910111213141516171819 | `private` `void` `call_md5(){``// 0x1a981``// android_native_md5(JNIEnv *env, jclass clazz, jbyteArray jarray, jint jmode)` `List<Object> args =` `new` `ArrayList<>(``10``);``args.add(vm.getJNIEnv());``args.add(``0``);``//jclass``String par1 =` `"lvdouzhou"``;` `args.add(vm.addLocalObject(``new` `ByteArray(vm,par1.getBytes())));``args.add(``1``);``//jmode` `Number retNum = module.callFunction(emulator,` `0x1a981``, args.toArray());``ByteArray retByteArr = vm.getObject(retNum.intValue());retNum.intValue();``String md5result =` `new` `String(retByteArr.getValue(), StandardCharsets.UTF_8);``System.out.println(``"md5result:"``+md5result);`  `}` |
|-|-|

得到的结果为 306551304117879571918511965941451501018 长度为 39

跳转到 0x1a981 看看这个函数，也都是控制流混淆。同样的套路，先大概看下有没有什么特征函数

![image-20241225104418834](https://bbs.kanxue.com/upload/attach/202412/791353_FMGGW2KNH9EQBVA.png)

![image-20241225105013456](https://bbs.kanxue.com/upload/attach/202412/791353_88QY4ZNN3QWXZGX.png)

找到了两个 doMD5sign 和 md5 hook两个函数看看是否调用

| 12345678910111213141516171819 | `private` `void` `md5_hook(){``Debugger debugger = emulator.attach();``//md5(indata_jarray, initial_len, v25)``debugger.addBreakPoint(module.base +` `0x13E3C``,` `new` `BreakPointCallback() {``@Override``public` `boolean` `onHit(Emulator<?> emulator,` `long` `address) {``System.out.println(``"md5 0x13E3C "``);``return` `true``;``}``});``// doMD5sign(v41, initial_len + 20, &v53);``debugger.addBreakPoint(module.base +` `0x14D54``,` `new` `BreakPointCallback() {``@Override``public` `boolean` `onHit(Emulator<?> emulator,` `long` `address) {``System.out.println(``"doMD5sign 0x14D54 "``);``return` `true``;``}``});``}` |
|-|-|

![image-20241225105115226](https://bbs.kanxue.com/upload/attach/202412/791353_FAQ3SDBZP8DCVZZ.png)

先调用了 doMD5sign 。那先看看这个函数的参数。第一个参数是要加密的字符串。第二个参数是长度。第三个参数应该就是返回值了 。

![image-20241225105247814](https://bbs.kanxue.com/upload/attach/202412/791353_D97A6XCFFSU5CNN.png)

记住 r2 的地址 0xbffff6f4，等下要用来查看返回值的。同时注意到 第三个参数是 **digest 这种的格式是二级指针的意思。 *digest 表示 digest 的地址。 *digest 本身也存放在内存的某个地址中，*digest 的地址为 **digest 。也就是说第三个参数其实是一个指针地址，如果要获取里面实际的内容。我们要把这个内容当一个地址，然后再去读取这个地址里面的内容。有点绕，后面直接看演示吧。

| 123 | `int` `a = 10;``int` `*p = &a;``int` `**pp = &p;` |
|-|-|

内存布局

![image-20241225110745273](https://bbs.kanxue.com/upload/attach/202412/791353_PCBYCTF6ET5E7WR.png)

>
> - `a` 是一个整型变量，存储值 `10`。
> - `p` 是一个一级指针，存储 `a` 的地址。
> - `pp` 是一个二级指针，存储 `p` 的地址。
>
>
>

![image-20241225105758773](https://bbs.kanxue.com/upload/attach/202412/791353_SQ2HT968Z7DSQU6.png)

![image-20241225105237096](https://bbs.kanxue.com/upload/attach/202412/791353_5YBVP4CHAYCZZMA.png)

在我们传入的字符串后面有加盐的操作，加了 dJLdCJiVnDvM9JUpsom9。下一个 lr 断点。c 继续执行

m0xbffff6f4

![image-20241225110620135](https://bbs.kanxue.com/upload/attach/202412/791353_FMWDBS62VH6HYU6.png)

这里有个知识点就是 unidbg中的地址都是 40 开头的。还有一个就是在 md5的运算过程中数据在内存中都是用小端序的形成存放的。

>
> 4个字节的数据 0x12345678
>
>
> 大端序 ： 12 34 56 78
>
>
> 小端序 ： 78 56 34 12
>
>
>

且因为前面说过了，第三个参数是一个二级指针。所以这里的数据起始是指向原始数据的地址，这个地址转换过来就是 0x402D2000。

然后读取这个地址的数据 m0x402D2000

![image-20241225111250514](https://bbs.kanxue.com/upload/attach/202412/791353_J3TQT5V7AJ3MW7R.png)

unidbg 运行得到的结果为 306551304117879571918511965941451501018 ，两个对比就是我们的目标结果。

但是标准的 md5 lvdouzhou 得到的值为 b2cf7dd26f44f87f74d67885a026c96c。所以里面应该还做了其他处理。在前面的hook 知道。里面还调用了一个 md5 的函数 。我们先进入 doMD5sign

![image-20241225112131719](https://bbs.kanxue.com/upload/attach/202412/791353_55QTF9GSN6N55CG.png)

可以看到的确是调用了 md5 ，但是后面还有一个可疑的 bytesToInt 函数。这里的 md5 hook之后查看返回值后，是一个标准的md5 。

代码下面还有三个 strcat ，把4 个数据进行拼接得到最终的数据。hook strcat 查看拼接的数据

![image-20241225172724417](https://bbs.kanxue.com/upload/attach/202412/791353_8W5P4GYWGDVV9UZ.png)

![image-20241225172733961](https://bbs.kanxue.com/upload/attach/202412/791353_UK78MJQ2K7WZVRN.png)

这两个数据就是我们最终值的 306551304117879571918511965941451501018 的前面部分。所以只要分析清楚 bytesToInt 这里面是如何操作。就可以得到最终的sign值。这里就暂时不做分析了。因为不是本篇文章的目的。

q 来自白盒 aes，然后进行了base64编码，且对bs64结果的字符进行了替换。sign 来自 md5算法，md5的结果再进行了 bytesToInt 拼接得到最终的结果。

# 总结

此次通过hook haskmap 定位了 java 的加密参数的位置。跟踪进入native 层，虽然代码被 ollvm 混淆过。通过个别函数我们也猜测到对应的算法。结合unidbg 下断点找到 DFA攻击的时间点。最终得到了 AES 的key 。总体难度适中，适合练手。到此，多谢各位大佬时间。

---

# 回复

## 回复 by hzqhacker (#2)

*2024-12-29 12:52*

感谢发出 我们尽快做一下弥补
你不发都不知道问题在哪儿

## 回复 by 墨穹呢 (#3)

*2024-12-31 10:40*

感谢分享

## 回复 by koflfy (#4)

*2024-12-31 11:48*

好文章，mark

## 回复 by mb_bptrvouw (#5)

*2025-1-15 21:15*

大佬文章中的xrt是什么工具ART吗还是别的可以分享不

## 回复 by scllqk (#6)

*2025-1-30 18:18*

>
> [mb_bptrvouw](https://bbs.kanxue.com/user-982873.htm)
>
>  大佬文章中的xrt是什么工具ART吗还是别的可以分享不
>
>

同问，这是啥工具啊？

## 回复 by 绿豆粥 (#7)

*2025-2-5 11:05*

>
> [scllqk](https://bbs.kanxue.com/user-936543.htm)
>
>  同问，这是啥工具啊？
>
>

fart魔改的脱壳工具

## 回复 by hanjiefang (#8)

*2025-12-9 13:58*

大佬请教下，frida检测采用什么方式绕过的呢？
