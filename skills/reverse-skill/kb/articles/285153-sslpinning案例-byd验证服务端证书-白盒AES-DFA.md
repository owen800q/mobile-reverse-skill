---
title: '[分享]sslpinning案例 ，byd验证服务端证书+白盒AES DFA'
url: https://bbs.kanxue.com/thread-285153.htm
tid: 285153
author: 绿豆粥
date: '2025-01-07'
tags: [Android安全, 分享, 基础理论, 逆向分析, 协议分析, 混淆加固]
crawled_at: '2026-08-12T04:01:31+00:00'
replies: 10
---

# 前言

之前发了一个 ssl pinning 的文章。里面没有什么案例。最近刚好看到BYD的这个app，在网络请求的过程中使用了 ssl pinning 。且是通过 X509Manager 方式实现的。所以这里就记录下分析过程。另外这个 app 的native 层也是 白盒AES 与五菱app一模一样的。

# 目标信息

版本：770

接口：进入app首页任意接口

是否有壳：bangbang壳

参数：request

# 参数定位

### ssl pinning

打开抓包工具，这个提示就是 app 做了证书绑定。直接上 sslbypass

![image-20241226153412492](https://bbs.kanxue.com/upload/attach/202501/791353_BAVHQD2P3UPBSBK.png)

根据之前的文章 Platform,checkServerTrusted 就是使用 x509 来验证服务器的证书，它调用的就是 app 继承实现了的 x509

所以就是 a.d&1

![image-20250102112033503](https://bbs.kanxue.com/upload/attach/202501/791353_FWDY57MBSZ3SBX6.png)

| 123456 | `var x509` `=` `Java.use(``"com.byd.aeri.core.net.a.d$1"``);``console.log(``"x509 "``,x509)``x509[``'checkServerTrusted'``].implementation` `=``function(arg0,arg1){``console.log(``"x509 check"``);``return` `;``}` |
|-|-|

数据就出来了

![image-20250102112853207](https://bbs.kanxue.com/upload/attach/202501/791353_8UB2XDUR8365NRD.png)

charles 能看到数据了， 请求数据和返回的数据都被加密了。这次的目标就是 request。

![image-20250102155335857](https://bbs.kanxue.com/upload/attach/202501/791353_YVUJXXX3V3TZE7B.png)

![image-20250102160127084](https://bbs.kanxue.com/upload/attach/202501/791353_GQKW6787XZXDTZK.png)

### request 参数分析

硬邦邦的壳，上次分析wu菱app也是用的邦邦。没啥说的，上老演员 xrt 把它脱了。

![image-20241226152318018](https://bbs.kanxue.com/upload/attach/202501/791353_TY7SQJ8QS6SF2PW.png)

演员表演完毕

![image-20241226155352135](https://bbs.kanxue.com/upload/attach/202501/791353_TEDVP9QW2KEVVR9.png)

搜索关键词 request ，没有找到。再换一个方式搜索 “request” 有几个可疑的地方

![image-20250107095838278](https://bbs.kanxue.com/upload/attach/202501/791353_KN8GCN5GUWND2U4.png)

第一个像是检查长度的，先分析第二个

![image-20250107100103140](https://bbs.kanxue.com/upload/attach/202501/791353_Y7VHY2FNYKEC9R2.png)

数据来自 checkCodeUtil.checkcode("F" + a2, 1)

![image-20250107100208515](https://bbs.kanxue.com/upload/attach/202501/791353_PWSFJ9BJJHPZBFV.png)

checkcode 就是到native 层了

![image-20250107100324617](https://bbs.kanxue.com/upload/attach/202501/791353_GCWC7Q2R5ZRSKBM.png)

在 CheckCodeUtils 最下方也找到了对应的 so

![image-20250107100404625](https://bbs.kanxue.com/upload/attach/202501/791353_86E34QNDDMQVUHU.png)

hook 来获取传入的参数

目标接口

>
> [https://dilinkappserver-cn.byd.auto/club/?s=ForInterfaceApp.forwardInformationFlow&serviceDir=App.Community.TopicList](https://dilinkappserver-cn.byd.auto/club/?s=ForInterfaceApp.forwardInformationFlow&amp;serviceDir=App.Community.TopicList)
>
>
>

对应的 request 的参数为

![image-20250107101203646](https://bbs.kanxue.com/upload/attach/202501/791353_GP4WNJ33UM3TU3G.png)

对比之后 frida hook 结果中有我们的目标数据

![image-20250107101245462](https://bbs.kanxue.com/upload/attach/202501/791353_U395PS45SUABH94.png)

>
> CheckCodeUtil.checkcode is called: str=F{"encryData":"D4761015BF05FD9400E1440CADB654F398C9DD70EE8838DEE4A6C4093D3894A7B66C09A0927F8FEDA8C15B0F56A6FC6DF1787ACC97228B5894C8DFFD5272752B","orderType":1,"identifier":"club100","reqTimestamp":"1736215765773","imeiMD5":"B17C3F7EEE64C071B136EE850685A81C","sign":"2Ce9D2d38B28AC4f71da48a8BC75A96a8Da3Ddf","numPerPage":5,"identifierType":2,"pageNum":1,"appChannel":"1","status":"3","objective":""}, i=1, str2=1736215765774
>
>
> CheckCodeUtil.checkcode result=FwQZ914rbytVRu2pdCt5ACvoOYn1jwSDfdo3UCMN3efYq1W6xNKqIzHCnpCk4DC82ADR+PD5orUlcbwkVe92Yr5NSKc5zoPcQGKvgwxMJztBnVRIp4610zdP9ZXtK3WKBaB03qVfxr2OTO0DkR+++0sM91EPQDPl9JNSjhZKqbTutbj6BrFTWtTC8nliGnoLj4AcJlWxdr+WSfFd0t09oHy1Bz77ndYXpYB7xYnqGaNTR7g08WxV4NC73s1jZmR0xCl4c2MN6+oplcOLEtT38KWZkkucwJah2FJ0dloXGmNmLwZV5I7LINep2x1k1PECO0Ib1Hs/ibMk1zqiMNSuHT0mS3vYJf4EiDxjo7GEohhHSJgk2ipQN/SprfeV0dCvWTJI+cnrbIgs5O6gnzGihNGfh0v51/92gngul3gz+ZCBqdPhaKOtxWR9wagkaT90UCvYpXWTvqpLX2cV3R1p9y/f3AOUv5nI0zPxZDnZlRCORLqOn99uQCmkf3x63x0Pv/f3GQ7+q45QT80PzKzo0nQlxunJ1stmjNUi6O7VAttQBRp8tQ7vdIhnoE6amXOT+2sRpgd4CfH6lsd6FHP78WtSadsYbFGPsyLHJlHk2uToaWusi+MKTsclM3Fqz1YuBccSIijrV5qxlfQ3p+naUYzTO6zdBuk/TVhH527vds0UZIMWwLege5McHTtVmTfNbVYxBlyQcX5pV77F0nrbwm0P81XicGIA+I9wRLCydo+9uRX+kGKnQ3vHmB+D1SXsV
>
>
>

参数搞定，接下来基操进入 native 层。

# native 分析

IDA 打开 encrypt ，搜索 java 能够找到对应方法，说明是静态注册的。

![image-20250103153736295](https://bbs.kanxue.com/upload/attach/202501/791353_Q83SE7WAVJNH99X.png)

进入 checkcode 查看发现是没有汇编指令的，猜测应该是 so 加固了。这个时候需要先dump内存中的so。因为内存中的 so 在 app 运行起来之后一定是解密状态的。

| 12345678910111213141516171819202122 | `function` `dump_so(so_name) {``Java.perform(``function` `() {``var` `currentApplication = Java.use(``"android.app.ActivityThread"``).currentApplication();``var` `dir = currentApplication.getApplicationContext().getFilesDir().getPath();``var` `libso = Process.getModuleByName(so_name);``console.log(``"[name]:"``, libso.name);``console.log(``"[base]:"``, libso.base);``console.log(``"[size]:"``, ptr(libso.size));``console.log(``"[path]:"``, libso.path);``var` `file_path = dir +` `"/"` `+ libso.name +` `"_"` `+ libso.base +` `"_"` `+ ptr(libso.size) +` `".so"``;``var` `file_handle =` `new` `File(file_path,` `"wb"``);``if` `(file_handle && file_handle !=` `null``) {``Memory.protect(ptr(libso.base), libso.size,` `'rwx'``);``var` `libso_buffer = ptr(libso.base).readByteArray(libso.size);``file_handle.write(libso_buffer);``file_handle.flush();``file_handle.close();``console.log(``"[dump]:"``, file_path);` `}``});``}` |
|-|-|

dump出来的so信息是不完整的，需要修复 so。使用开源工具 <https://github.com/F8LEFT/SoFixer>

| 1 | `.\soFixer-Windows-64.exe -s D:\pyworkSpace\frida-code\app\byd\libencrypt.so_0x7026013000_0x1d9000.so -o D:\pyworkSpace\frida-code\app\byd\libencrypt.so_0x7026013000_0x1d9000_fix.so  -m 0x7026013000  -d` |
|-|-|

使用修复后的 so 导入 unidbg，并补上环境。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566 | `public` `class` `fbyd` `extends` `AbstractJni {``private` `AndroidEmulator emulator;``private` `VM vm;``private` `final` `Module module;`  `public` `fbyd() {``emulator = AndroidEmulatorBuilder.for64Bit()``.setProcessName(``"com.byd.aeri.caranywhere"``)``.build();``final` `Memory memory = emulator.getMemory();``memory.setLibraryResolver(``new` `AndroidResolver(``23``));` `vm = emulator.createDalvikVM(``new` `File(``"unidbg-android/src/test/java/com/byd/aeri/caranywhere/byd770.apk"``));``vm.setJni(``this``);``vm.setVerbose(``true``);``// libandroid.so 用一个虚拟的 so 来代替``new` `AndroidModule(emulator, vm).register(memory);` `//so 模块``DalvikModule dm = vm.loadLibrary(``new` `File(``"unidbg-android/src/test/java/com/byd/aeri/caranywhere/libencrypt.so_0x7026013000_0x1d9000_fix.so"``),` `true``);``module = dm.getModule();``dm.callJNI_OnLoad(emulator);` `}` `@Override``public` `DvmObject<?> callStaticObjectMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {``switch` `(signature) {``case` `"android/app/ActivityThread->currentActivityThread()Landroid/app/ActivityThread;"``:``return` `vm.resolveClass(``"android/app/ActivityThread"``).newObject(``null``);``case` `"android/os/SystemProperties->get(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;"``:``String arg = varArg.getObjectArg(``0``).getValue().toString();``System.out.println(``"SystemProperties get arg===>"` `+ arg);``if` `(arg.equals(``"ro.serialno"``)) {``return` `new` `StringObject(vm,` `"9B131FFBA001Y5"``);``}` `}``return` `super``.callStaticObjectMethod(vm, dvmClass, signature, varArg);``}` `@Override``public` `DvmObject<?> callObjectMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {``switch` `(signature){``case` `"android/app/ActivityThread->getSystemContext()Landroid/app/ContextImpl;"``:``return` `vm.resolveClass(``"android/app/ContextImpl"``).newObject(``null``);``case` `"android/app/ContextImpl->getPackageManager()Landroid/content/pm/PackageManager;"``:``return` `vm.resolveClass(``"android/content/pm/PackageManager"``).newObject(``null``);``case` `"android/app/ContextImpl->getSystemService(Ljava/lang/String;)Ljava/lang/Object;"``:``String arg = varArg.getObjectArg(``0``).getValue().toString();``System.out.println(``"getSystemService arg ===> "``+arg);``return` `vm.resolveClass(``"android.net.wifi"``).newObject(signature);``case` `"android/net/wifi->getConnectionInfo()Landroid/net/wifi/WifiInfo;"``:``return` `vm.resolveClass(``"android/net/wifi/WifiInfo"``).newObject(``null``);``case` `"android/net/wifi/WifiInfo->getMacAddress()Ljava/lang/String;"``:``return` `new` `StringObject(vm,` `"02:00:00:00:00:00"``);` `}``return` `super``.callObjectMethod(vm, dvmObject, signature, varArg);``}` `public` `static` `void` `main(String[] args) {``fbyd b =` `new` `fbyd();``}``}` |
|-|-|

来个主动调用

| 12345678910111213141516 | `private` `void` `call_native(){``//        253AC Java_com_bangcle_comapiprotect_CheckCodeUtil_checkcode``List<Object> args =` `new` `ArrayList<>();``args.add(vm.getJNIEnv());``args.add(``0``);``String arg1 =` `"F{\"encryData\":\"5D8B849FC54256C755A5B15BB96F7E9F0BE482FA77C91EF02960172AC72B4FFD\",\"identifier\":\"club100\",\"reqTimestamp\":\"1736215765786\",\"imeiMD5\":\"B17C3F7EEE64C071B136EE850685A81C\",\"sign\":\"E4f996d9FC2eAEb460aeFCf4DC8eB732CC95E539\",\"numPerPage\":10,\"identifierType\":2,\"pageNum\":0,\"appChannel\":\"1\",\"objective\":\"\"}"``;``int` `arg2 =` `1``;``String tm =` `"1736215765788"``;` `args.add(vm.addLocalObject(``new` `StringObject(vm,arg1)));``args.add(arg2);``args.add(vm.addLocalObject(``new` `StringObject(vm,tm)));``Number retNum = module.callFunction(emulator,``0x253AC``,args.toArray());``StringObject ret = vm.getObject(retNum.intValue());``System.out.println(``"md5result:"` `+ ret);` `}` |
|-|-|

得到的结果

>
>  md5result:FwQZ914rbytVRu2pdCt5ACvoOYn1jwSDfdo3UCMN3efYq1W6xNKqIzHCnpCk4DC82ADR+PD5orUlcbwkVe92Yr5NSKc5zoPcQGKvgwxMJztBnVRIp4610zdP9ZXtK3WKBaB03qVfxr2OTO0DkR+++0sM91EPQDPl9JNSjhZKqbTutbj6BrFTWtTC8nliGnoLj4AcJlWxdr+WSfFd0t09oHy1Bz77ndYXpYB7xYnqGaNTR7g08WxV4NC73s1jZmR0xCl4c2MN6+oplcOLEtT38KWZkkucwJah2FJ0dloXGmNmLwZV5I7LINep2x1k1PECO0Ib1Hs/ibMk1zqiMNSuHT0mS3vYJf4EiDxjo7GEohhHSJgk2ipQN/SprfeV0dCvWTJI+cnrbIgs5O6gnzGihNGfh0v51/92gngul3gz+ZCBqdPhaKOtxWR9wagkaT90UCvYpXWTvqpLX2cV3R1p9y/f3AOUv5nI0zPxZDnZlRCORLqOn99uQCmkf3x63x0Pv/f3GQ7+q45QT80PzKzo0nQlxunJ1stmjNUi6O7VAttTt3ppZQgP3muw4h7H4zynlWGbC3EAFOA0mVto3K+8zH1TOIO+d83jEXqBf1OWImvHPcj6RTJB5e5CvIMRKUfO0Xd0BHoHTI88wl8kLr/sf1oIbjWjdOEbwZTwLidUa9m1Aw21JlKg+JnFo+MsYP1QccR5nA13FeyKYIukW39P1ehAvGMP406PLkLaEb9rzVuZWGH2S5aeOp408aIoIgxgpeJuybaB0h++FFlmzuvglkA==
>
>
>

和抓包的一致。然后接着分析 so 算法

so 算法起始和 五菱那篇的 AES DFA 一模一样的。可以转去看那篇文章哈。

[okhttp 证书绑定流程 ssl pinning分析](https://bbs.kanxue.com/thread-285064.htm)

[五菱AES DFA。如今弯道今犹在，不见当年过弯人](https://bbs.kanxue.com/thread-284612.htm)

# 总结

算上水了一篇文章吧，主要是学习怎么过 ssl pinning 。多谢各位大佬的时间啦！！

---

# 回复

## 回复 by 我想你了 (#2)

*2025-1-7 18:08*

学习了。

## 回复 by mb_ldbucrik (#3)

*2025-1-7 23:04*

感谢分享

## 回复 by mb_elqwyvnm (#4)

*2025-1-8 01:41*

学习新知识

## 回复 by gtict (#5)

*2025-1-8 09:50*

xrt 这个是啥工具，，

## 回复 by 荧光之夏 (#6)

*2025-1-8 10:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  gtict](https://bbs.kanxue.com/user-346783.htm)
>
>  xrt 这个是啥工具，，
>
>

同问

## 回复 by xiayutian_ (#7)

*2025-1-8 14:15*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  gtict](https://bbs.kanxue.com/user-346783.htm)
>
>  xrt 这个是啥工具，，
>
>

fart吧 可能它自己改了

## 回复 by 绿豆粥 (#8)

*2025-1-8 21:09*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  xiayutian_](https://bbs.kanxue.com/user-1009165.htm)
>
>  fart吧 可能它自己改了
>
>

是的，按照fart改的，就少了fart特征 ![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by xiayutian_ (#9)

*2025-1-9 14:37*

>
> [绿豆粥](https://bbs.kanxue.com/user-791353.htm)
>
>  是的，按照fart改的，就少了fart特征 [em_014]
>
>

![image](https://bbs.kanxue.com/view/img/face/005.gif)太强啦

## 回复 by mb_bmkfgrxv (#10)

*2025-8-31 22:21*

有联系方式嘛博主

## 回复 by schimmer (#11)

*2025-9-10 10:52*

大佬，这个用unidbg模拟执行最后的得出来的值也跟抓包的值不一样吧。我复现了一遍，发现传入参数和抓包对应完全相同，最后一部分加密值也会不一样，看了下dump下来的so发现有一些拼接系统属性的内容。最后在unidbg中同样的参数和环境执行两次最后有一部分加密内容也不同，不知道拼接的什么。
