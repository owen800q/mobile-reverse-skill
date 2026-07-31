---
title: x-zse-96安卓端python纯算,查表AES(下)
url: https://bbs.kanxue.com/thread-281041.htm
tid: 281041
author: 杨如画
date: '2024-03-23'
tags: [Android安全, 逆向分析, 协议分析, HOOK注入]
crawled_at: '2026-07-31T14:29:22+08:00'
replies: 7
---

两天前发了一个x-zse-96的文章,当时遇到了点问题,只分析到了最后一个白盒AES函数里面,并且当时用dfa攻击还原出了秘钥,IV也确定了,但是加密结果不对,本来打算把下文鸽掉的,因为当时unidbg没跑起来,用frida去hook白盒AES中的每一行汇编有点麻烦,没有unidbg方便.后来小白大佬说unidbg可以跑通,并把还原算法的任务交给了我.我拿着小白提供的unidbg代码,开始了算法还原之旅.
还原算法,篇幅有点长,会介绍AES的10轮加密以及如何从汇编代码和伪c代码中还原出魔改的AES,由于so是从内存中dump下来的,反编译出来的伪代码准确性很差,主要看的就是汇编.
严格来说,这个AES魔改的已经完全不能算是AES了,但是他c中的函数名称还是叫wb_laes_encrypt,
白盒也不算.

# unidbg代码

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177 | `package` `com.zh2;` `import` `com.github.unidbg.AndroidEmulator;``import` `com.github.unidbg.Emulator;``import` `com.github.unidbg.Module;``import` `com.github.unidbg.arm.backend.Unicorn2Factory;``import` `com.github.unidbg.debugger.Debugger;``import` `com.github.unidbg.file.FileResult;``import` `com.github.unidbg.file.IOResolver;``import` `com.github.unidbg.linux.android.AndroidEmulatorBuilder;``import` `com.github.unidbg.linux.android.AndroidResolver;``import` `com.github.unidbg.linux.android.dvm.*;``import` `com.github.unidbg.linux.android.dvm.array.ByteArray;``import` `com.github.unidbg.linux.file.ByteArrayFileIO;``import` `com.github.unidbg.linux.file.SimpleFileIO;``import` `com.github.unidbg.memory.Memory;``import` `keystone.Keystone;``import` `keystone.KeystoneArchitecture;``import` `keystone.KeystoneEncoded;``import` `keystone.KeystoneMode;` `import` `java.io.File;``import` `java.io.IOException;``import` `java.util.ArrayList;``import` `java.util.List;` `public` `class` `zh` `extends` `AbstractJni` `implements` `IOResolver {``private` `final` `AndroidEmulator emulator;``private` `final` `DvmClass CryptoTool;``private` `final` `VM vm;``private` `final` `Module module;` `public` `zh()` `throws` `IOException {``emulator = AndroidEmulatorBuilder``.for32Bit()``.addBackendFactory(``new` `Unicorn2Factory(``true``))``.setProcessName(``"com.zhihu.android"``)``.build();``Memory memory = emulator.getMemory();``memory.setLibraryResolver(``new` `AndroidResolver(``23``));``vm = emulator.createDalvikVM(``new` `File(``"unidbg-android/apks/zh2/zh9.29.0.apk"``));``vm.setJni(``this``);``vm.setVerbose(``true``);``emulator.getSyscallHandler().addIOResolver(``this``);``DalvikModule dm2 = vm.loadLibrary(``"bangcle_crypto_tool"``,` `true``);``module = dm2.getModule();``CryptoTool = vm.resolveClass(``"com.bangcle.CryptoTool"``);``dm2.callJNI_OnLoad(emulator);``}``public` `static` `String bytesToHex(``byte``[] bytes) {``StringBuilder sb =` `new` `StringBuilder();``for` `(``byte` `b : bytes) {``int` `unsignedInt = b &` `0xff``;``String hex = Integer.toHexString(unsignedInt);``if` `(hex.length() ==` `1``) {``sb.append(``'0'``);``}``sb.append(hex);``}``return` `sb.toString();``}``public` `void` `x_zse_96_encrypt()` `throws` `IOException {``List<Object> list =` `new` `ArrayList<>(``5``);``list.add(vm.getJNIEnv());``list.add(``0``);``byte``[] byy1 = {-``118``,-``125``,-``125``,``41``,``41``,``34``,-``113``,-``115``,``42``,``35``,``34``,``42``,-``125``,-``128``,``40``,-``125``,-``125``,``33``,-``126``,``41``,``40``,-``118``,-``117``,``35``,-``125``,-``128``,-``117``,``35``,``42``,-``115``,``35``,-``113``};``byte``[] byy2 = {-``103``,``48``,``58``,``58``,``50``,``52``,``58``,``57``,-``110``,-``110``,``58``,``59``,``58``,-``103``,-``110``,-``110``};``ByteArray arr1 =` `new` `ByteArray(vm,byy1);``list.add(vm.addLocalObject(arr1));``list.add(vm.addLocalObject(``new` `StringObject(vm,` `"541a3a5896fbefd351917c8251328a236a7efbf27d0fad8283ef59ef07aa386dbb2b1fcbba167135d575877ba0205a02f0aac2d31957bc7f028ed5888d4bbe69ed6768efc15ab703dc0f406b301845a0a64cf3c427c82870053bd7ba6721649c3a9aca8c3c31710a6be5ce71e4686842732d9314d6898cc3fdca075db46d1ccf3a7f9b20615f4a303c5235bd02c5cdc791eb123b9d9f7e72e954de3bcbf7d314064a1eced78d13679d040dd4080640d18c37bbde"``)));``ByteArray arr2 =` `new` `ByteArray(vm,byy2);``list.add(vm.addLocalObject(arr2));``Number number = module.callFunction(emulator,` `0xa708``, list.toArray());``ByteArray resultArr = vm.getObject(number.intValue());``System.out.println(``"result:"``+ bytesToHex(resultArr.getValue()));``}``public` `static` `void` `main(String[] args)` `throws` `IOException {``zh zh =` `new` `zh();``zh.patchInstruction();``zh.x_zse_96_encrypt();``}``private` `void` `patchInstruction() {``try` `(Keystone keystone =` `new` `Keystone(KeystoneArchitecture.Arm, KeystoneMode.ArmThumb)) {``KeystoneEncoded assemble = keystone.assemble(``"nop;nop"``);``byte``[] machineCode = assemble.getMachineCode();``emulator.getMemory().pointer(module.base +` `0x8EBC``).write(``0``,machineCode,``0``,machineCode.length);` `KeystoneEncoded encoded = keystone.assemble(``"mov r3, 1"``);``byte``[] patchCode = encoded.getMachineCode();``emulator.getMemory().pointer(module.base +` `0x4e70``).write(``0``, patchCode,` `0``, patchCode.length);``KeystoneEncoded encoded1 = keystone.assemble(``"mov r3, 1"``);``byte``[] patchCode1 = encoded1.getMachineCode();``emulator.getMemory().pointer(module.base +` `0x4e84``).write(``0``, patchCode1,` `0``, patchCode1.length);``}` `catch` `(Exception e) {``e.printStackTrace();``}``}``@Override``public` `DvmObject<?> getStaticObjectField(BaseVM vm, DvmClass dvmClass, String signature) {``switch` `(signature) {``case` `"com/secneo/apkwrapper/H->PKGNAME:Ljava/lang/String;"``: {``String packageName = vm.getPackageName();``if` `(packageName !=` `null``) {``return` `new` `StringObject(vm, packageName);``}``break``;``}``case` `"com/secneo/apkwrapper/H->ISMPASS:Ljava/lang/String;"``: {``return` `new` `StringObject(vm,` `"###MPASS###"``);``}``}``return` `super``.getStaticObjectField(vm, dvmClass, signature);``}``@Override``public` `DvmObject<?> callObjectMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {``switch` `(signature) {``case` `"android/app/ActivityThread->getSystemContext()Landroid/app/ContextImpl;"``: {``return` `vm.resolveClass(``"android/app/ContextImpl"``).newObject(signature);``}``case` `"android/app/ContextImpl->getPackageManager()Landroid/content/pm/PackageManager;"``: {``return` `vm.resolveClass(``"android/content/pm/PackageManager"``).newObject(signature);``}``case` `"java/io/File->getPath()Ljava/lang/String;"``: {``System.out.println(``"PATH:"` `+ dvmObject.getValue());``if` `(dvmObject.getValue().equals(``"android/os/Environment->getExternalStorageDirectory()Ljava/io/File;"``)) {``return` `new` `StringObject(vm,` `"/mnt/sdcard"``);``}``}``case` `"java/lang/String->intern()Ljava/lang/String;"``: {``String string = dvmObject.getValue().toString();``return` `new` `StringObject(vm, string.intern());``}``case` `"java/lang/Class->getDeclaredFields()[Ljava/lang/reflect/Field;"``: {``DvmClass c = (DvmClass) dvmObject;``System.out.println(c.getClassName());``}``}``return` `super``.callObjectMethodV(vm, dvmObject, signature, vaList);``}``@Override``public` `DvmObject<?> getObjectField(BaseVM vm, DvmObject<?> dvmObject, String signature) {``switch` `(signature) {``case` `"android/content/pm/PackageInfo->applicationInfo:Landroid/content/pm/ApplicationInfo;"``: {``return` `vm.resolveClass(``"android/content/pm/ApplicationInfo"``).newObject(signature);``}``case` `"android/content/pm/ApplicationInfo->sourceDir:Ljava/lang/String;"``: {``return` `new` `StringObject(vm,` `"/data/app/com.zhihu.android-XnTWbKh_JrM9gUKdEn_Wug==/base.apk"``);``}``case` `"android/content/pm/ApplicationInfo->dataDir:Ljava/lang/String;"``: {``return` `new` `StringObject(vm,` `"/data/data/com.zhihu.android-XnTWbKh_JrM9gUKdEn_Wug=="``);``}``case` `"android/content/pm/ApplicationInfo->nativeLibraryDir:Ljava/lang/String;"``: {``return` `new` `StringObject(vm,` `"/data/app/com.zhihu.android-XnTWbKh_JrM9gUKdEn_Wug==/lib/arm"``);``}``}``return` `super``.getObjectField(vm, dvmObject, signature);``}``@Override``public` `DvmObject<?> callStaticObjectMethodV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {``switch` `(signature) {``case` `"android/os/Environment->getExternalStorageDirectory()Ljava/io/File;"``: {``return` `vm.resolveClass(``"java/io/File"``).newObject(signature);``}``}``return` `super``.callStaticObjectMethodV(vm, dvmClass, signature, vaList);``}``@Override``public` `FileResult resolve(Emulator emulator, String pathname,` `int` `oflags) {``if` `(pathname.equals(``"/proc/self/cmdline"``)) {``return` `FileResult.success(``new` `ByteArrayFileIO(oflags, pathname,` `"com.zhihu.android"``.getBytes()));``}``if` `(pathname.equals(``"/data/app/com.zhihu.android-XnTWbKh_JrM9gUKdEn_Wug==/base.apk"``)) {``return` `FileResult.success(``new` `SimpleFileIO(oflags,` `new` `File(``"D:\\code\\me\\app\\unidbg-master\\unidbg-android\\src\\test\\resources\\zhihu\\zhihu.apk"``), pathname));``}``return` `null``;``}``}` |
|-|-|

unidbg跑不起来的原因是有几个初始化的函数无法执行起来,当时我也是打了几个patch下去,最终没能跑起来,也许是版本有差异,我弄的是最新版的,这个unidbg中的版本是9.29.0.

# 还原算法

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_PBTC77FNGDJ7E52.jpg)

这个就是目标函数了,其实它有5个参数,ida识别出错了,参数一和参数2都是入参,结果通过a2返回回去
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_E98TPXN4JVQZX6T.jpg)
来看下函数最开始的地方,v3被赋值成了入参,v53 = *a3,v52 = a3[3] / 32 + 6
这里ida反汇编出来的有些问题,不过根据aes的算法特征也可以大概猜出这里是在做什么,v52 = a3[3] / 32 + 6,我们知道AES有10轮加密,第10轮没有mixcolumns(列混淆),并且aes的分组长度16字节128位,128/32+6=10,下面的从1开始到10结束正好是9轮.
![image](https://bbs.kanxue.com/upload/attach/202403/983110_ZQHD3VX3A4XBNT8.jpg)

# 初始轮秘钥加

这样的话框中的应该就是第一个轮秘钥加了.说是加其实是异或,比如秘钥k0是0x11111111111111111111111111111111,明文是0x22222222222222222222222222222222,异或就是他两直接异或就好了.
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_Y8J3XK9SRVYTVER.jpg)
因为c语言只能一个字节一个字节的异或,所以16个字节他这里有16轮.result是第一个入参,和第二个入参是同一个地址,这里我hook过了result经过9轮加密始终没变,所以上面result赋值的结果不用管,只需要看*(&v36 + i) = (byte_D914[*(v53 + i) & 0xF ^ (16 * *(v3 + i))] >> 4) ^ (16 * (byte_D914[(*(v53 + i) >> 4) & 0xF ^ (16 * (*(v3 + i) >> 4))] >> 4));这行就可以了,正常来说两个字节异或直接0x11^0x22就可以了,他这里那么长肯定是改了AES的,v3是入参,v53来自上面的*a3,接下来unidbg中看下这个v53是多少,鼠标选中这个星号,按tab转文本汇编
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_3MY2KDUQ6ZFA2HD.jpg)
STR R3, [R11,#-16] (Store Register),存储指令,结合着c代码,就是把寄存器r3的值存到R11偏移-16的位置,对应着v53=*a3,unidbg中下断看下R3是多少

| 12345 | `public` `void` `HookByConsoleDebugger() {``Debugger debugger = emulator.attach();``debugger.addBreakPoint(module.base+``0x6444``);``}``需要encrypt函数调用前执行` |
|-|-|

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_FDRM3QSEMCD36UH.jpg)
m某个寄存器可以直接看内存中的数据,默认是112字节,可以在后面加数组指定dump多少字节,好像后面还有![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_5TXKJDJDM5B8DVY.jpg)

长度是16*11,这个11好像是aes的11个轮秘钥,但是他的11个轮秘钥是没有联系的,标准的aes是第一轮可以推出后面的轮秘钥的.
*(&v36 + i) = (byte_D914[*(v53 + i) & 0xF ^ (16 * *(v3 + i))] >> 4) ^ (16 * (byte_D914[(*(v53 + i) >> 4) & 0xF ^ (16 * (*(v3 + i) >> 4))] >> 4)); 16轮循环下来,v53只消耗第一个轮秘钥,v3是入参,v36是结果,byte_D914是一个数组.这里看上去写的有点复杂,其实不然,就是byte_D914[*(v53 + i) & 0xF ^ (16 * *(v3 + i))] >> 4异或(16 * (byte_D914[(*(v53 + i) >> 4) & 0xF ^ (16 * (*(v3 + i) >> 4))] >> 4)),想要获得结果就需要知道byte_D914是多少
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_UYUZT9CG6GWTAB4.jpg)
点过去只有100字节,但是*(v53 + i) & 0xF ^ (16 * *(v3 + i))或者(*(v53 + i) >> 4) & 0xF ^ (16 * (*(v3 + i) >> 4))的结果在0x0到0xff之间有256个,所以一直带下面的256个应该都是byte_D914的.但是当你把这256个字节扣出来并且加密一遍后你会发现结果有几个字节是正确的,有几个字节是错误的,应该是因为dump下来的so有些问题.这里ida中的静态byte_D914是不准确的,真正准确的是内存中的,所以可以从unidbg中把这256个字节dump下来.![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_2GM5TDC4FHQSUR3.jpg)
鼠标选中byte_D914按tab转到文本汇编,后面的一些操作都需要汇编的基础,因为c的代码不准确,想要搞so的算法还原必须要懂汇编
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_XJH7RCPAAY5EB72.jpg)
LDRB R3, [R2, R3](Load Register Byte)字面意思,从R2+R3的地址加载一个字节到R3中,对应着c代码就是从byte_D914中取数据呗.

| 1 | `debugger.addBreakPoint(module.base+``0x64c0``);` |
|-|-|

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_ZKTQHSCMA9AJSMR.jpg)

r3 0x18就是偏移,偏移是从0x0到0xff,所以r2中的数据应该就是byte_D914
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_MK4UEY9YCUZTM5U.jpg)
这些字节都对的上,后面的就有些偏差了,这里我们只要unidbg中的结果
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_ZE4EC4S6S8AW6XU.jpg)
还原算法的话就把byte_D914转成数组就好了,用到的时候从里面取值.
经过上面一系列操作的话,入参和第一个秘钥加密的结果就好了.这个结果很重要

# 9轮循环

标准aes中的9轮循环里的内容是字节替换,循环左移,列混淆,轮秘钥加.轮秘钥加上面我们说过了,字节替换就是以自身数值为索引取出s盒里的内容,s盒256字节,类似上面的byte_D914.循环左移和列混淆这个魔改的aes不涉及,所以这里不说了,稍微有些麻烦,感兴趣的自行网上检索.
对照着这4个步骤来看这9轮循环
因为是魔改的,字节替换,循环左移,列混淆,轮秘钥加这4个步骤都改了,所以就按照标准aes中的叫法来给下面的4个循环取上对应的名字

# #字节替换

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_KCQ4CG9QWD42NGA.jpg)

## 循环左移

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_DPS4T4B4R68EF38.jpg)

## 列混淆和轮秘钥加

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_CMAKR3J2BSW4P7V.jpg)
这4个步骤看上去挺相似的,但是主要是v4,v20.v53这几个值在操作还有中间的数组取值操作,这个数组的我就不说了,和上面的数组获取的方式一样.
v53是11个轮秘钥,步骤4正好也是用的v53中的轮秘钥,v4和v20是主要需要关注的点,中间记录了他们的变化,我截图没截上而已.这两个值的变化说简单也不简单,说难也难不到哪去.
有那么一丝白盒AES查表的意味.
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_9NNPDED2NN2K74Y.jpg)
这是python还原的几个数组还有几张表,有点大,折叠了.
接着上面的分析.我只分析第一个字节替换的过程,后面的3个步骤和这个的分析是一模一样的,所以我尽可能写详细点.
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_NVVGZV8KKUH28PF.jpg)
主要是看v4和v20是怎么生成的.
v36也就是最开始的第一轮轮秘钥加得到的结果,先来看下结果是多少.
鼠标选中v36转到文本汇编
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_393A6RAWJF3WFRG.jpg)
LDRB R3, [R11,#-36] LDRB指令上面介绍过了,这行指令的意思就是从R11偏移-36(-0x24)的地方取下一个字节给R3,结合c代码,R11处地址-0x24中的数据就是v36
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_9SWRK8E5ERHHRRN.jpg)
0xbffff5ac-0x24=0xbffff588
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_D2NABVN36BZFN2H.jpg)
记住这16个字节,每一轮加密中的4组加密都需要这个值(每一轮不一样),根据这里的索引去查表,一次用4个字节,一共4次刚好16个字节,每次的4个字节从表中一次查4个字节也是16字节,对应的正好就是v4和v20的值,后面会说表怎么拿到. ![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_3Z84ZA3CGVWUAX6.jpg)
接下来先去看下经过68-99行,v20的值变成了多少.
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_GHHMAVU5HTEA337.jpg)

取地址处看下汇编
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_93T58SPMCPQMW7W.jpg)

ADD R3, R2, R3 将寄存器 R2 和寄存器 R3 中的值相加，并将结果存储到寄存器 R3中
unidbg中下断看下R2和R3是什么,根据&v4 + i不看断点处大概也能猜到,R3是i(偏移),R2就是v4

| 1 | `debugger.addBreakPoint(module.base+``0x69B4``);` |
|-|-|

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_ZACASVUQHH9RUHW.jpg)
结果也正好验证了,此处刚进入循环所有r3是0,,来看下r2的值,也就是v20
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_76CGDSUFJSRHHGE.jpg)
ok,结果我们知道了,接下来带着结果去看v20是怎么生成的.6574处
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_S877A58T2HUFJMZ.jpg)
LDR R3, [R3,R2,LSL#2]将寄存器 R2 中的值左移两位(相当于*4)+R3再赋给R3,unidbg中下断看下

| 1 | `debugger.addBreakPoint(module.base+``0x6574``);` |
|-|-|

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_5UKAQQTT2FGHQMQ.jpg)
r2这个0xc5有没有很眼熟,请看上面这张图
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_QMNZYQTAA27YZFX.jpg)
按照LDR R3, [R3,R2,LSL#2]汇编的操作来执行一下,0xc5*4=0x314,R3=0x4000dc14+0x314=0x4000df28,看下内存中的值是多少![image](https://bbs.kanxue.com/upload/attach/202403/983110_66ZBPSKQMVHA2PJ.jpg)
再看下v20的前4个字节
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_JPQGRTMRYY4SU9N.jpg)
00 BC BC 03变成 03 BC BC 00怎么变得相信不需要我多说了,后面的12个字节也是同理.
接下来说一下怎么获取这张大表,unidbg中hook即可.
因为LDR R3, [R3,R2,LSL#2],r2在0x0到0xff之间,*4后就是0x0到1020,以间隔4dump下unidbg中的内存即可

| 12345678910111213141516171819202122 | `debugger.addBreakPoint(module.base+``0x6574``,` `new` `BreakPointCallback() {``int` `num=``0``;``@Override``public` `boolean` `onHit(Emulator<?> emulator,` `long` `address) {``int` `i;``Backend backend = emulator.getBackend();``if``(num==``0``){``for` `(i=``0``;i<=``1020``;i+=``4``){``int` `x =``0x4000dc14``+Integer.parseInt(Integer.toHexString(i),` `16``);``byte``[] bytes = backend.mem_read(x,` `0x04``);``StringBuilder hexString =` `new` `StringBuilder();``for` `(``byte` `b : bytes) {``hexString.append(String.format(``"%02X "``, b &` `0xFF``));``}``System.out.println(Integer.parseInt(Integer.toHexString(i),` `16``)+``":"``+ hexString.toString().trim());``};``}``num+=``1``;``return` `true``;``}``});` |
|-|-|

结果就是这样的
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_E49VV2R2R53GDPX.jpg)
尝试搜索一下0x314也就是788
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_SE84DYY8XVFGGCK.jpg)
可以看到结果也是对的上的,后面的流程都是这样,自此,几个数和表的获取都说完了,接下来的流程就是细心点就没问题了.

## 第10轮

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_2TPR3J63ZWXWHZ6.jpg)
第10轮标准AES有字节替换,循环左移,轮秘钥加.这里它只有一个循环.
这个表的获取方式和上面的略有不同,不过我相信你如果把前9轮加密能搞定的话,最后一轮肯定是没问题的了.

# 总结

这样下来的话,这个白盒AES中的算法就搞定了,这里还有几个注意事项
1传进去的明文是32位的,刚好是两个分组长度,所以会再填充一个分组,这个填充模式也是魔改的,具体可以看下方的图
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_9F2NB6P5WS6AV5N.jpg)
因为传进去的md5值32位,所以只需要再填充一组就可以了,也就是9b9b9b9b9b9b9b9b9b9b9b9b9b9b9b9b,所以总的分组数就是3组.
2因为是cbc模式,每个分组加密的结果会和下一轮的明文进行异或.初始iv是99303a3a32343a3992923a3b3a999292
3python纯算代码太长了,有好几张表,这里我放不下就放到下方知识星球了,感兴趣的可以加一下.

# 最后

微信公众号
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_H49XAQMN26KKKK2.jpg)
知识星球
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_JWJFYG59QJKYZDX.jpg)
如果你觉得这篇文章对你有帮助也可请作者喝一杯咖啡
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_E4KJPKZWV7FNA79.jpg)

---

# 回复

## 回复 by 秋狝 (#2)

*2024-3-24 16:53*

感谢分享

## 回复 by 肉蚌葱鸡 (#3)

*2024-5-3 15:47*

![image](https://bbs.kanxue.com/upload/attach/202405/807763_3JEZSWQAN8JTTUX.webp)
感谢楼主分享 试了一下是可以补跑通的 都我没弄这个 没验证

## 回复 by 杨如画 (#4)

*2024-5-5 18:52*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  肉蚌葱鸡](https://bbs.kanxue.com/user-807763.htm)
>
>  感谢楼主分享 试了一下是可以补跑通的 都我没弄这个 没验证
>
>

大部分接口会验证,纯算也有

## 回复 by mb_nuxwsyal (#5)

*2024-10-24 22:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  肉蚌葱鸡](https://bbs.kanxue.com/user-807763.htm)
>
>  感谢楼主分享 试了一下是可以补跑通的 都我没弄这个 没验证
>
>

可以改成独立运行版本吗？ 我想要，可以付费

## 回复 by 杨如画 (#6)

*2024-10-25 10:39*

有python版纯算法

## 回复 by mb_nuxwsyal (#7)

*2024-10-25 10:48*

>
> [杨如画](https://bbs.kanxue.com/user-983110.htm)
>
>  有python版纯算法
>
>

在哪？

## 回复 by 杨如画 (#8)

*2024-10-25 12:54*

>
> [mb_nuxwsyal](https://bbs.kanxue.com/user-994499.htm)
>
>  在哪？
>
>

在我电脑上?![image](https://bbs.kanxue.com/view/img/face/16.gif)
