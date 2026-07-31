---
title: '[原创]shopee app算法分析第一篇'
url: https://bbs.kanxue.com/thread-284570.htm
tid: 284570
author: 杨如画
date: '2024-11-27'
tags: [Android安全, 原创, 逆向分析, 协议分析, HOOK注入]
crawled_at: '2026-07-31T14:18:23+08:00'
replies: 30
---

shopee app算法分析第一篇

分析完整算法大概要好几篇,耐心等待下

# 抓包

![image-20241126220341011](https://bbs.kanxue.com/upload/attach/202411/983110_85TPU3TEYPZ36F9.png)

抓的搜索接口,get请求,核心的有3个4字节键和x-sap-ri,如果是post,就是4个4字节键和值,多出来的一个和post的表单有关

![image-20241126220612188](https://bbs.kanxue.com/upload/attach/202411/983110_Y25GE3FTSDJ99JE.png)

后续内容都是post的,post会了,get肯定也会了,4个4字节3个短的,一个长的.这5个参数来着同一个so,libshpssdk.so,后面说怎么定位到的.

4字节的key和value也是一直变化的,最好摸清楚生成机制,随机可能引起风控.(有9套算法)

# 定位加密位置

| 1234567891011 | `Java.perform(``function` `(){``//     HashMap.put``var` `hashMap = Java.use(``"java.util.HashMap"``);``hashMap.put.implementation =` `function` `(a, b) {``if``(a!=``null` `&& a.equals(``"x-sap-ri"``)){``console.log(Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Throwable"``).$``new``()))``console.log(``"hashMap.put: "``, a, b);``}``return` `this``.put(a, b);``}``})` |
|-|-|

太长了,放前面的结果

| 1234567891011 | `java.lang.Throwable``at java.util.HashMap.put(Native Method)``at org.json.JSONObject.put(JSONObject.java:``276``)``at org.json.JSONTokener.readObject(JSONTokener.java:``394``)``at org.json.JSONTokener.nextValue(JSONTokener.java:``104``)``at org.json.JSONObject.<init>(JSONObject.java:``168``)``at org.json.JSONObject.<init>(JSONObject.java:``185``)``at com.shopee.shpssdk.SHPSSDK.uvwvvwvvw(Unknown Source:``81``)``at com.shopee.shpssdk.SHPSSDK.requestDefense(Unknown Source:``59``)` `hashMap.put:  x``-``sap``-``ri` `443e41678c54f44f62b70d1901d115bc703ebab92a5b4251176d` |
|-|-|

在com.shopee.shpssdk.SHPSSDK.uvwvvwvvw方法里,这个app有很多站点的,初步看了只是包名不一样,函数,so偏移都是一样的,包名是com.shopee.xx xx是域名后面的,我使用的样本是ph,3.37.31

| 12345678 | `马来西亚：https:``/``/``shopee.my``新加坡：https:``/``/``shopee.sg``泰国：https:``/``/``shopee.th``印度尼西亚：https:``/``/``shopee.``id``越南：https:``/``/``shopee.vn``菲律宾：https:``/``/``shopee.ph``台湾：https:``/``/``shopee.tw``大陆：https:``/``/``shopee.cn` |
|-|-|

![image-20241126221616280](https://bbs.kanxue.com/upload/attach/202411/983110_6DDZ83J3MVK4C2D.png)

这个位置值已经生成了,往上找调用,就一个,结果来自wvvvuwwu.vuwuuwvw(str.getBytes(), bArr),hook发现,第一个参数url,第二个表单(get就是null)

![image-20241126221714102](https://bbs.kanxue.com/upload/attach/202411/983110_FUNA4SQAM52VZB7.png)

点过去来到native注册的地方

![image-20241126221845356](https://bbs.kanxue.com/upload/attach/202411/983110_R4TSKUV74EERQ39.png)

hook下libart

| 12345 | `[RegisterNatives] method_count:` `0x4``name: com.shopee.shpssdk.wvvvuwwu vuwuuwvv sig: (I)V module_name: libshpssdk.so offset:` `0x1bef84``name: com.shopee.shpssdk.wvvvuwwu vuwuuwvu sig: (Lcom``/``shopee``/``shpssdk``/``wvvvuvvv;)I module_name: libshpssdk.so offset:` `0x1bf478``name: com.shopee.shpssdk.wvvvuwwu vuwuuwvw sig: ([B[B)Ljava``/``lang``/``String; module_name: libshpssdk.so offset:` `0x995dc``name: com.shopee.shpssdk.wvvvuwwu vuwuuwvvw sig: ([B)V module_name: libshpssdk.so offset:` `0x9932c` |
|-|-|

so名字libshpssdk,偏移0x995dc,到lib目录下找发现一个so都没有,hook下dlopen

| 123456789101112131415161718192021222324 | `var` `dlopen = Module.findExportByName(``null``,` `"dlopen"``);``//6.0``var` `android_dlopen_ext = Module.findExportByName(``null``,` `"android_dlopen_ext"``);``//高版本8.1以上` `Interceptor.attach(dlopen, {``onEnter:` `function` `(args) {``var` `path_ptr = args[0];``var` `path = ptr(path_ptr).readCString();``console.log(``"[dlopen:]"``, path);``},``onLeave:` `function` `(retval) {``// Thread.sleep(3);``}``});` `Interceptor.attach(android_dlopen_ext, {``onEnter:` `function` `(args) {``var` `path_ptr = args[0];``var` `path = ptr(path_ptr).readCString();``console.log(``"[dlopen_ext:]"``, path);``},``onLeave:` `function` `(retval) {``// Thread.sleep(3);``}``});` |
|-|-|

| 1 | `/``data``/``app``/``~~KVEKJlJur2r6197VML5LRw``=``=``/``com.shopee.sg``-``ZyVbLWincySSEAiqQSuPLQ``=``=``/``split_config.arm64_v8a.apk!``/``lib``/``arm64``-``v8a``/``libshpssdk.so` |
|-|-|

可以看到so是压缩了下,拖出来即可.

# hook和主动调用

## hook 固定一组入参

| 123456789101112131415161718 | `Java.perform(``function` `(){``console.log(``'======================'``)``let wvvvuwwu = Java.use(``"com.shopee.shpssdk.wvvvuwwu"``);``wvvvuwwu[``"vuwuuwvw"``].implementation =` `function` `(bArr, bArr2) {``var` `ByteString = Java.use(``"com.android.okhttp.okio.ByteString"``);``if``(bArr!==``null``){``try``{``console.log(``'111111111'``)``console.log(`wvvvuwwu.vuwuuwvw is called: bArr=${ByteString.of(bArr).utf8()}, bArr2=${bArr2}`);``}``catch` `(e) {``}``}``// console.log(`wvvvuwwu.vuwuuwvw is called: bArr=${bArr}, bArr2=${bArr2}`);``let result =` `this``[``"vuwuuwvw"``](bArr, bArr2);``console.log(`wvvvuwwu.vuwuuwvw result=${result}`);``return` `result;``};``})` |
|-|-|

注意脚本写法(排除空,异常字段),很多时候排除掉手机,app,frida版本这些的问题, 为什么明明确定是这个位置hook脚本就是没输出,考虑下是不是脚本有问题,有时候有问题是不会输出东西的,也不报错,然后你以为没走这,就是因为你对参数进行了错误操作,比如类型没判断正确,空没有排除掉导致脚本什么都不打印.好几个人问我,这里统一回复下.

## call

都是基本写法,不熟悉多google,自己琢磨才能记得住.

| 123456789101112 | `function` `call(){``Java.perform(``function` `(){``let wvvvuwwu = Java.use(``"com.shopee.shpssdk.wvvvuwwu"``);``var` `str =` `'https://mall.shopee.ph/api/v4/pages/bottom_tab_bar'``var` `StringClass = Java.use(``'java.lang.String'``);``var` `byteArray = StringClass.$``new``(str).getBytes();``var` `str2 =` `'{"img_size":"3.0x","latitude":"","location":"[]","longitude":"","new_arrival_reddot_last_dismissed_ts":0,"feed_reddots":[{"timestamp":0,"noti_code":28}],"client_feature_meta":{"is_live_and_video_merged_tab_supported":false},"video_reddot_last_dismissed_ts":0,"view_count":[{"count":1,"source":0,"tab_name":"Live"}]}'``var` `byteArray2 = StringClass.$``new``(str2).getBytes();``var` `res = wvvvuwwu[``"vuwuuwvw"``](byteArray,byteArray2)``console.log(``'res==>'``,res)``})``}` |
|-|-|

连续调用会有一个4字节key不变,1A9EC9B9,这个只和url有关,后续写还原,这个键对应的值解密出来是16字节随机+9套算法中的哪3套,第二篇写算法还原

| 123456789 | `url` `=` `'/api/v4/pages/bottom_tab_bar'``def` `getKey1(url):``tmp` `=` `0``for` `i` `in` `bytearray(url.encode()):``tmp` `=` `tmp``*``0x334b` `&` `0xffffffff``tmp``=``(tmp``+``i) &` `0xffffffff``key` `=` `tmp&``0x7fffffff``return` `f``"{key:04X}"``print``(``'getKey1'``,getKey1(url))` `# 1A9EC9B9 还原这个只需要url` |
|-|-|

## native call

native call的作用是方便确定哪些是so的初始化函数(不管有没有),可以节省后续很多时间.

| 12345678910111213141516171819202122232425262728293031323334 | `function` `stringToHexArray(str) {``var` `hexArray = [];``for` `(``var` `i = 0; i < str.length; i++) {``var` `hex = str.charCodeAt(i);``hexArray.push(0x00 + hex);``}``return` `hexArray;``}` `function` `call2(){``var` `soAddr = Module.findBaseAddress(``"libshpssdk.so"``);``var` `funAddr = soAddr.add(0x995dc);``var` `fun =` `new` `NativeFunction(funAddr,` `'pointer'``, [``"pointer"``,` `"pointer"``,``'pointer'``,``'pointer'``]);``var` `JNIEnv = Java.vm.getEnv();` `var` `byteArray = stringToHexArray(``'https://mall.shopee.ph/api/v4/pages/bottom_tab_bar'``);``var` `byteArrayPtr = Memory.alloc(byteArray.length);``Memory.writeByteArray(byteArrayPtr, byteArray);` `var` `byteArray2 = stringToHexArray(``'{"img_size":"3.0x","latitude":"","location":"[]","longitude":"","new_arrival_reddot_last_dismissed_ts":0,"feed_reddots":[{"timestamp":0,"noti_code":28}],"client_feature_meta":{"is_live_and_video_merged_tab_supported":false},"video_reddot_last_dismissed_ts":0,"view_count":[{"count":1,"source":0,"tab_name":"Live"}]}'``);``var` `byteArrayPtr2 = Memory.alloc(byteArray2.length);``Memory.writeByteArray(byteArrayPtr2, byteArray2);`  `var` `arr1 = JNIEnv.newByteArray(byteArray.length);``JNIEnv.setByteArrayRegion(arr1,0,byteArray.length,byteArrayPtr)` `var` `arr2 = JNIEnv.newByteArray(byteArray2.length);``JNIEnv.setByteArrayRegion(arr2,0,byteArray2.length,byteArrayPtr2)` `var` `res = fun(JNIEnv, ptr(0x0),arr1,arr2)``var` `s = Java.cast(res, Java.use(``"java.lang.Object"``));``console.log(s)``}` |
|-|-|

在so刚加载后直接native call如果有正确结果就没有初始化,如果有需要一步步调用初始化直到生成正确结果,方便后续模拟执行

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970 | `function delay_hook(so_name, hook_func) {``var dlopen` `=` `Module.findExportByName(null,` `"dlopen"``);` `/``/` `6.0``以下``var android_dlopen_ext` `=` `Module.findExportByName(null,` `"android_dlopen_ext"``);` `/``/` `8.1``以上` `Interceptor.attach(dlopen, {``onEnter: function (args) {``var path_ptr` `=` `args[``0``];``var path` `=` `ptr(path_ptr).readCString();``this.path` `=` `path;``}, onLeave: function (retval) {``if` `(this.path.indexOf(so_name) !``=``=` `-``1``) {``console.log(``"[dlopen:]"``, this.path);``hook_func();` `}``}``});` `Interceptor.attach(android_dlopen_ext, {``onEnter: function (args) {``var path_ptr` `=` `args[``0``];``var path` `=` `ptr(path_ptr).readCString();``this.path` `=` `path;``},``onLeave: function (retval) {``if` `(this.path.indexOf(so_name) !``=``=` `-``1``) {``console.log(``"\nandroid_dlopen_ext加载："``, this.path);``hook_func();``}``}``});``}`  `function stringToHexArray(``str``) {``var hexArray` `=` `[];``for` `(var i` `=` `0``; i <` `str``.length; i``+``+``) {``var` `hex` `=` `str``.charCodeAt(i);``hexArray.push(``0x00` `+` `hex``);``}``return` `hexArray;``}` `function do_hook() {``var soAddr` `=` `Module.findBaseAddress(``"libshpssdk.so"``);``var funAddr` `=` `soAddr.add(``0x995dc``);``var fun` `=` `new NativeFunction(funAddr,` `'pointer'``, [``"pointer"``,` `"pointer"``,``'pointer'``,``'pointer'``]);``var JNIEnv` `=` `Java.vm.getEnv();` `var byteArray` `=` `stringToHexArray(``'https://mall.shopee.ph/api/v4/pages/bottom_tab_bar'``);``var byteArrayPtr` `=` `Memory.alloc(byteArray.length);``Memory.writeByteArray(byteArrayPtr, byteArray);` `var byteArray2` `=` `stringToHexArray(``'{"img_size":"3.0x","latitude":"","location":"[]","longitude":"","new_arrival_reddot_last_dismissed_ts":0,"feed_reddots":[{"timestamp":0,"noti_code":28}],"client_feature_meta":{"is_live_and_video_merged_tab_supported":false},"video_reddot_last_dismissed_ts":0,"view_count":[{"count":1,"source":0,"tab_name":"Live"}]}'``);``var byteArrayPtr2` `=` `Memory.alloc(byteArray2.length);``Memory.writeByteArray(byteArrayPtr2, byteArray2);`  `var arr1` `=` `JNIEnv.newByteArray(byteArray.length);``JNIEnv.setByteArrayRegion(arr1,``0``,byteArray.length,byteArrayPtr)` `var arr2` `=` `JNIEnv.newByteArray(byteArray2.length);``JNIEnv.setByteArrayRegion(arr2,``0``,byteArray2.length,byteArrayPtr2)` `var res` `=` `fun(JNIEnv, ptr(``0x0``),arr1,arr2)``var s` `=` `Java.cast(res, Java.use(``"java.lang.Object"``));``console.log(s)` `}``delay_hook(``"libshpssdk.so"``, do_hook);` `/``/` `改so的名字和do_hook的方法体` |
|-|-|

-f启动,很幸运没有初始化,国内大厂没有没有初始化的,这块占逆向比重也很大.

# 模拟执行

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869 | `package` `com.shopee.fun;` `import` `com.github.unidbg.AndroidEmulator;``import` `com.github.unidbg.Emulator;``import` `com.github.unidbg.Module;``import` `com.github.unidbg.file.FileResult;``import` `com.github.unidbg.file.IOResolver;``import` `com.github.unidbg.linux.android.AndroidEmulatorBuilder;``import` `com.github.unidbg.linux.android.AndroidResolver;``import` `com.github.unidbg.linux.android.dvm.*;``import` `com.github.unidbg.linux.android.dvm.array.ByteArray;``import` `com.github.unidbg.memory.Memory;``import` `com.github.unidbg.virtualmodule.android.AndroidModule;` `import` `java.io.File;` `public` `class` `demo3` `extends` `AbstractJni` `implements` `IOResolver {``private` `final` `AndroidEmulator emulator;``private` `final` `VM vm;``private` `final` `Module module;``@Override``public` `FileResult resolve(Emulator emulator, String pathname,` `int` `oflags) {``System.out.println(``"open file:"` `+ pathname);``return` `null``;``}``demo3(){``// 创建模拟器实例``emulator = AndroidEmulatorBuilder.for64Bit().setProcessName(``"com.shopee.ph"``).build();``emulator.getSyscallHandler().addIOResolver(``this``);``// 获取模拟器的内存操作接口``final` `Memory memory = emulator.getMemory();``// 设置系统类库解析``memory.setLibraryResolver(``new` `AndroidResolver(``23``));``// 创建Android虚拟机,传入APK，Unidbg可以替我们做部分签名校验的工作``vm = emulator.createDalvikVM(``new` `File(``"unidbg-android/src/test/java/com/shopee/files/xiap_ph3.37.31.apk"``));``// 设置JNI``vm.setJni(``this``);``// 打印日志``vm.setVerbose(``true``);``new` `AndroidModule(emulator, vm).register(memory);``// 加载目标SO``DalvikModule dm = vm.loadLibrary(``new` `File(``"unidbg-android/src/test/java/com/shopee/files/libshpssdk2.so"``),` `true``);``//获取本SO模块的句柄,后续需要用它``module = dm.getModule();``// 调用JNI OnLoad``dm.callJNI_OnLoad(emulator);``};``public` `void` `callByAPI(){` `DvmClass RequestCryptUtils = vm.resolveClass(``"com/shopee/shpssdk/wvvvuwwu"``);`  `//        byte[] bytes = "https://mall.shopee.ph/api/v4/pages/bottom_tab_bar".getBytes();``byte``[] bytes =` `"https://mall.shopee.ph/api/v4/pages/bottom_tab_bar"``.getBytes();``ByteArray arr1 =` `new` `ByteArray(vm,bytes);` `byte``[] bytes2 =` `"{\"img_size\":\"3.0x\",\"latitude\":\"\",\"location\":\"[]\",\"longitude\":\"\",\"new_arrival_reddot_last_dismissed_ts\":0,\"feed_reddots\":[{\"timestamp\":0,\"noti_code\":28}],\"client_feature_meta\":{\"is_live_and_video_merged_tab_supported\":false},\"video_reddot_last_dismissed_ts\":0,\"view_count\":[{\"count\":1,\"source\":0,\"tab_name\":\"Live\"}]}"``.getBytes();``ByteArray arr2 =` `new` `ByteArray(vm,bytes2);` `//        emulator.traceCode(module.base,module.base+module.size);``StringObject result = RequestCryptUtils.callStaticJniMethodObject(emulator,` `"vuwuuwvw([B[B)Ljava/lang/String;"``, arr1,arr2);``//        StringObject result = RequestCryptUtils.callStaticJniMethodObject(emulator, "vuwuuwvw([B[B)Ljava/lang/String;", arr1,null);``System.out.println(result.toString());``};``public` `static` `void` `main(String[] args) {``demo3 demo =` `new` `demo3();``//        demo.callByAPI();``}``}` |
|-|-|

执行无异常

![image-20241126225427782](https://bbs.kanxue.com/upload/attach/202411/983110_DC447ZM73KWQYGU.png)

然后调用函数. callByAPI放开

![image-20241126225522242](https://bbs.kanxue.com/upload/attach/202411/983110_FVPV996TW7KFYDR.png)

上来就查找异常,上面验证了没有初始化,也就是说直接调用理论上是可以的.很明显上来就走到异常了. 要么放弃unidbg,用stalker,要么硬干,排除异常.

| 1 | `emulator.traceCode(module.base, module.base+module.size);` |
|-|-|

我选择试试排除异常,在刚调用函数的位置开启trace,运行

![image-20241126230214931](https://bbs.kanxue.com/upload/attach/202411/983110_7ZAZTF7MFHBMX75.png)

刚开始异常的位置是0x980b8,ida中看看

![image-20241126230610607](https://bbs.kanxue.com/upload/attach/202411/983110_PJVJ69FWKJYR7CW.png)

没有有用的信息

![image-20241126230701341](https://bbs.kanxue.com/upload/attach/202411/983110_BSEVJJS53ZXF95S.png)

往上找了找,看到了都是和异常相关的字段,判断应该是走入这个函数导致的异常,如果不让函数执行到这里是不是就可以绕过了?可以尝试一下,没有好的办法,不试你就只能扔到回收站.

## 排除异常

异常函数是sub_9646C

![image-20241126231121159](https://bbs.kanxue.com/upload/attach/202411/983110_NXWX22ZXA7S7KMC.png)

日志中看到由9a204跳到异常

![image-20241126231217854](https://bbs.kanxue.com/upload/attach/202411/983110_7UUNVZ7YA629S9F.png)

off_345F20里放的都是函数地址,有点罕见这种.

![image-20241126231239173](https://bbs.kanxue.com/upload/attach/202411/983110_UT7T7H5D99YCX3V.png)

复制出来搜索发现只有一处走向异常,之前尝试了不让他走到这个判断里面,有些困难

![image-20241126231558702](https://bbs.kanxue.com/upload/attach/202411/983110_ARB8G64ZD8YGHER.png)

最好的办法是把这个跳转直接nop掉

| 12345 | `public` `void` `patch(){``UnidbgPointer pointer = UnidbgPointer.pointer(emulator,module.base +` `0x9A208``);``byte``[] code =` `new` `byte``[]{(``byte``)` `0x1f``, (``byte``)` `0x20``,(``byte``)` `0x03``, (``byte``)` `0xD5``};``//  1F 20 03 D5  异常位置``pointer.write(code);``}` |
|-|-|

运行

![image-20241126231916020](https://bbs.kanxue.com/upload/attach/202411/983110_A9892UPYCVXZJVQ.png)

进入到正常逻辑了,后续的补环境交给你相信也是信手拈来.

补环境代码中可能有东西参与了计算,需要注意,另外大部分结果由随机数构成,需要处理好哪些随机是对应的.走的是/dev/urandom

x-sap-ri算法

| 12345678910111213 | `import` `random``import` `time` `def` `generate_hex_string():``hex_string` `=` `'``'.join(random.choice('``0123456789ABCDEF``')` `for` `_` `in` `range``(``44``))``hex_list` `=` `list``(hex_string)``hex_list[``14``]` `=` `'1'`  `# 第15位（索引从0开始）``hex_list[``17``]` `=` `'1'`  `# 第18位（索引从0开始）``return` `''.join(hex_list)` `timestamp` `=` `int``(time.time()).to_bytes(``4``,byteorder``=``'little'``).``hex``()``random_hex_string` `=` `timestamp``+``generate_hex_string()``print``(``"x-sap-ri"``, random_hex_string)` |
|-|-|

# 正确结果

![image-20241126233036721](https://bbs.kanxue.com/upload/attach/202411/983110_WQ4WT2RENGGMETG.png)

不要觉得看上去很简单,想一想没有资料你能不能搞的出来? 后续预计3-4篇算法

后续这种简单的定位,脚本什么可能一笔带过了,默认都会了,我觉得这篇还是很详细的,后续算法远比这些复杂

---

# 回复

## 回复 by wx_插曲 (#2)

*2024-11-27 07:40*

大佬 牛逼

## 回复 by Eureka777 (#3)

*2024-11-27 11:06*

学习学习

## 回复 by bluegatar (#4)

*2024-11-27 12:00*

跟老大学习

## 回复 by mb_ldbucrik (#5)

*2024-11-27 12:38*

期待大佬更多的trace技巧

## 回复 by 熊趴趴来 (#6)

*2024-11-27 15:37*

look looook

## 回复 by jjcat (#7)

*2024-11-27 17:03*

????????

## 回复 by wantwill (#8)

*2024-11-27 18:22*

look looook

## 回复 by lxcxc (#9)

*2024-11-27 19:32*

好脚本

## 回复 by Tokameine (#10)

*2024-11-27 21:53*

牛的，看看

## 回复 by mb_zcfhleoj (#11)

*2024-11-27 22:15*

来了

## 回复 by 墨穹呢 (#12)

*2024-11-27 22:17*

感谢分享

## 回复 by 养只猫不好么 (#13)

*2024-11-28 13:28*

感谢分享

## 回复 by 刘qi刘 (#14)

*2024-11-28 16:14*

感谢分享

## 回复 by 易码 (#15)

*2024-11-28 16:53*

细看

## 回复 by mb_sslwzxww (#16)

*2024-11-28 17:47*

感谢分享

## 回复 by 杨如画 (#17)

*2024-11-28 18:13*

已关闭回复可看,勿回复无用内容

## 回复 by 杨如画 (#19)

*2024-12-9 15:50*

>
> [青春小时代](https://bbs.kanxue.com/user-914582.htm)
>
>  想高价请您做一个软件，
> VX，AK1988DA
>
>

不做这些,你找别人吧

## 回复 by Loopher (#20)

*2024-12-10 09:09*

感谢分享

## 回复 by CC小白p (#21)

*2024-12-18 15:50*

感谢分享  一步步学习吧

## 回复 by wx_梦里不知身是客 (#22)

*2024-12-20 15:45*

感谢分享，不过我没看错的话虽然最后生成出来，但这些参数如果找一个具体的pdp接口或者其他接口带入进去测试的话应该是会被服务器判定为生成有问题的。

## 回复 by 杨如画 (#23)

*2024-12-23 12:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_梦里不知身是客](https://bbs.kanxue.com/user-941716.htm)
>
>  感谢分享，不过我没看错的话虽然最后生成出来，但这些参数如果找一个具体的pdp接口或者其他接口带入进去测试的话应该是会被服务器判定为生成有问题的。
>
>

还有其他校验

## 回复 by wx_梦里不知身是客 (#24)

*2024-12-23 14:18*

>
> [杨如画](https://bbs.kanxue.com/user-983110.htm)
>
>  还有其他校验
>
>

我这里指的就是只针对这组生成的sign的校验，而不涉及sz-token之类的设备指纹，你生成出来的看起来是太短了

## 回复 by chenxia0 (#25)

*2025-1-3 22:25*

话说虾皮还可以通过协议刷商品详情数据吗？

## 回复 by mb_vcgryrxs (#26)

*2025-3-18 22:23*

seem to have kinda solution: https://github.com/tramps

## 回复 by 杨如画 (#27)

*2025-3-22 14:20*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_梦里不知身是客](https://bbs.kanxue.com/user-941716.htm)
>
>  我这里指的就是只针对这组生成的sign的校验，而不涉及sz-token之类的设备指纹，你生成出来的看起来是太短了
>
>

![image](https://bbs.kanxue.com/upload/attach/202503/983110_A2XMBXWYD6FXAYB.webp)

我解了真机的长值,多出来的主要就是抓包时触发异常的堆栈信息,里面本身指纹没多少,测试可以直接跑search和detail

## 回复 by mb_gnzzfers (#28)

*2025-4-12 16:28*

你好，可以私聊一下吗？付费咨询一下问题

## 回复 by 自己能 (#29)

*2025-5-21 16:35*

虾皮的设备指纹有研究吗

## 回复 by 自己能 (#30)

*2025-5-21 16:59*

大佬 你知道虾皮的设置唯一相关的是哪个参数吗

## 回复 by 自己能 (#31)

*2025-5-21 16:59*

设备唯一

## 回复 by leap frog (#32)

*2025-8-11 17:06*

您有试过直接更改device hex那个长串中的sz-token然后再进行加密请求的效果吗？
