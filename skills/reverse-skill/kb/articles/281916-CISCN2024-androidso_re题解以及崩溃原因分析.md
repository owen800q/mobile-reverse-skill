---
title: '[原创][CISCN2024]androidso_re题解以及崩溃原因分析'
url: https://bbs.kanxue.com/thread-281916.htm
tid: 281916
author: Shangwendada
date: '2024-05-27'
tags: [Android安全, 原创, HOOK注入, 逆向分析]
crawled_at: '2026-07-31T14:26:39+08:00'
replies: 10
---

## 前言

虽然没有参加CISCN，但在初赛赛题中遇到一个APK逆向的题目，对于最近学习安卓技能的我来说，正好是个练习的机会。对此题目，锐评一下：出题人可能在测题时不够严谨，或者故意为之，导致很多人可以直接hook关键点，秒破，但部分人却频繁遇到崩溃问题，导致这道题在不同选手手中的难度不一致。然而正好我就是那个频繁崩溃的那一批，由此分析了一下崩溃的原因并且分享一下解决方法。

## 分析

![file](https://bbs.kanxue.com/upload/attach/202405/979679_WEY4266HND8EQHA.jpg)
看上面的MainActivity其实可以发现程序非常简单明了，感觉都可以一把秒。主要在legal里面，首先对flag格式做了判断，后续才对flag内容进行判断，如果格式不通过则不会触发jni的内容。

| 1 | `paramString.length() ==` `38` `&& paramString.startsWith(``"flag{"``) && paramString.charAt(paramString.length() -` `1``) ==` `'}'` `&& !inspect.inspect(paramString.substring(``5``, paramString.length() -` `1``));` |
|-|-|

如上则为判断语句，规定了当Flag长度为38，且格式满足flag{xxx}的时候才进入inspect，主要判断逻辑也是在inspect中完成。

![file](https://bbs.kanxue.com/upload/attach/202405/979679_HJBYQAP42UPVV5C.jpg)

审计inspect的代码，可以发现其实就是一个普通的DES，这道题的槽点和难点其实也就集中在这里了，我们会发现程序的Key和Iv都来自于Native层，其实审计Native层代码之后，大家都会发现算法繁琐且复杂，但是我们可以通过直接Hook的方法，去获取Iv与Key。
在这之前，我们得先看看运行效果。
发现如果格式不满足，程序正常返回Wrong

![file](https://bbs.kanxue.com/upload/attach/202405/979679_ZRFQJTA4EZU73KT.jpg)

一旦格式满足，则程序直接崩溃了。
我们通过LogCat查看一下日志，究竟试什么原因崩溃。

![file](https://bbs.kanxue.com/upload/attach/202405/979679_77Z5PQEBFS2ER6V.jpg)

查看日志，崩溃原因就有点显然了，总结如下：

程序在调用 JNI 函数 NewStringUTF 时传递了一个非法的 UTF-8 编码字符串。具体来说，错误日志指出输入的字节序列 0x9d 0x80 0x99 0xd4 0xac 0xc9 0xd3 0xf8 包含非法的 UTF-8 起始字节 0x9d。

NewStringUTF 函数期望接收一个合法的 UTF-8 编码的字符串，而不是任意字节序列。如果传入的字节序列不符合 UTF-8 编码规范，就会导致 JNI 检测到错误并抛出异常。

看到这里就有点抽象了为啥会有非UTF8编码的字符串呢，我们只能分析一下Native的逻辑了

在这之前我们先看一下正常来说如果Native层需要返回一个Jstring应该怎么写呢

| 1234567 | `extern` `"C"` `JNIEXPORT jstring JNICALL``Java_com_swdd_ahandroid_MainActivity_stringFromJNI(``JNIEnv* env,``jobject` `/* this */``) {``std::string hello =` `"Hello from C++"``;``return` `env->NewStringUTF(hello.c_str());``}` |
|-|-|

没错在return的时候 使用`env->NewStringUTF(hello.c_str());`来返回Jstring，所以这里出现的情况就是NewStringUTF抛出了异常，对应Native层代码如下：
![file](https://bbs.kanxue.com/upload/attach/202405/979679_HJC4RDT8VXBESKF.jpg)

首先我们得想办法知道这个导致崩溃的八个字节究竟是什么东西
多运行，多崩溃几次发现，如果多尝试几次使用Hook主动调用GetKey和程序自主触发产生的居然不一致，至此开始玄学起来了。
![file](https://bbs.kanxue.com/upload/attach/202405/979679_HQMGNSUJSCUVUCU.jpg)
![file](https://bbs.kanxue.com/upload/attach/202405/979679_Z8VRSAYDFWNU5XV.jpg)

为了方便分析问题所在的地方，我们写脚本Hook NewStringUTF看看咋个事
hook脚本如下：

| 123456789101112131415161718192021222324252627282930313233343536373839404142 | `function` `hookNewStringUTF() {``Java.perform(``function` `() {``var` `modules = Process.enumerateModules();``var` `newStringUTFAddr =` `null``;` `for` `(``var` `i = 0; i < modules.length; i++) {``var` `module = modules[i];``try` `{``var` `symbols = module.enumerateSymbols();``for` `(``var` `j = 0; j < symbols.length; j++) {``if` `(symbols[j].name.indexOf(``"NewStringUTF"``) >= 0) {``newStringUTFAddr = symbols[j].address;``console.log(``"Found NewStringUTF in module: "` `+ module.name +` `" at: "` `+ newStringUTFAddr +` `" with name: "` `+ symbols[j].name);``break``;``}``}``}` `catch` `(e) {``console.warn(``"Failed to enumerate symbols for module: "` `+ module.name);``}``if` `(newStringUTFAddr) {``break``;``}``}` `if` `(newStringUTFAddr) {``// Hook NewStringUTF 函数``Interceptor.attach(newStringUTFAddr, {``onEnter:` `function``(args) {``// 获取传入的 char* 参数``var` `inputStr = args[1].readCString();``console.log(``"NewStringUTF called with: "` `+ inputStr);``},``onLeave:` `function``(retval) {``// 如果需要修改返回值，可以在这里进行``console.log(``"NewStringUTF returning: "` `+ retval);``}``});``}` `else` `{``console.log(``"NewStringUTF address not found!"``);``}``});``}` |
|-|-|

通过Hook得到的值如下，随后就崩溃了。
![file](https://bbs.kanxue.com/upload/attach/202405/979679_R3HUZVD7EWH5XVT.jpg)

## 结尾

其实这个解决方法，看似无解，但是我发现当我们使用attach对于getkey时，程序则正常返回，并且变得可以调试进入，示例代码如下：

| 123456789101112 | `function` `hook() {``let jni = Java.use(``"com.example.re11113.jni"``);``var` `iv = jni.getiv();``var` `getKeyBase = Module.findExportByName(``"libSecret_entrance.so"``,` `"Java_com_example_re11113_jni_getkey"``);` `Interceptor.attach(getKeyBase, {``onEnter:` `function``(args) {``},``onLeave:` `function``(retval) {``}``});``}` |
|-|-|

一旦我们附加这个代码，原本一调试就未响应的程序，变得可以调试了
![file](https://bbs.kanxue.com/upload/attach/202405/979679_ZKU4CTED8XY3VTR.jpg)
调试之后也可以看到正确的值
![file](https://bbs.kanxue.com/upload/attach/202405/979679_BME6Y94GYJ4PZPS.jpg)
那这样，整个程序就变得微妙了起来，测试了很多遍，都是只有在使用上述方法attach上之后程序就不再崩溃，并且目前没法找到原因。
既然正常，这个题的题的题解便是如此了
HOOK代码如下

| 123456789101112131415 | `function` `hook() {``let jni = Java.use(``"com.example.re11113.jni"``);``var` `iv = jni.getiv();``console.log(``"IV: "``+iv);``var` `getKeyBase = Module.findExportByName(``"libSecret_entrance.so"``,` `"Java_com_example_re11113_jni_getkey"``);` `Interceptor.attach(getKeyBase, {``onEnter:` `function``(args) {``},``onLeave:` `function``(retval) {``}``});``var` `key = jni.getKey();``console.log(``"Key: "` `+ key);``}` |
|-|-|

最后解des即可
![file](https://bbs.kanxue.com/upload/attach/202405/979679_2SEC77FHDGNS4GZ.jpg)

上传的附件：
- app-debug.apk

（3.91MB，40次下载）

---

# 回复

## 回复 by 你瞒我瞒 (#2)

*2024-5-28 09:22*

大佬，能否分享个样本呢

## 回复 by Shangwendada (#3)

*2024-5-28 09:40*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  大佬，能否分享个样本呢
>
>

放在附件啦

## 回复 by Shangwendada (#4)

*2024-5-28 09:43*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  大佬，能否分享个样本呢
>
>

## 回复 by Shangwendada (#5)

*2024-5-28 09:47*

目前还没有分析出具体原因，后续发现了会继续更新帖子

## 回复 by 你瞒我瞒 (#6)

*2024-5-29 16:57*

>
> [Shangwendada](https://bbs.kanxue.com/user-979679.htm)
>
>  放在附件啦
>
>

谢谢，下载了附件输入了flag{12345678901234567890123456789012}没有崩溃![image](https://bbs.kanxue.com/view/img/face/14.gif)提示wrong。

## 回复 by Shangwendada (#7)

*2024-5-29 18:01*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  谢谢，下载了附件输入了flag{12345678901234567890123456789012}没有崩溃[em_14]提示wrong。
>
>

是的，我在开头提到过，部分手机不会崩溃

## 回复 by 你瞒我瞒 (#8)

*2024-5-30 09:55*

>
> [Shangwendada](https://bbs.kanxue.com/user-979679.htm)
>
>  是的，我在开头提到过，部分手机不会崩溃
>
>

复现了AOSP12-pixel3不会，Android13官方系统pixel6，正确长度格式第一行不会崩溃，多按一次按钮就崩溃。05-30 09:53:25.042 15057 15057 F DEBUG   : uid: 10279
05-30 09:53:25.042 15057 15057 F DEBUG   : tagged_addr_ctrl: 0000000000000001 (PR_TAGGED_ADDR_ENABLE)
05-30 09:53:25.042 15057 15057 F DEBUG   : signal 6 (SIGABRT), code -1 (SI_QUEUE), fault addr --------
05-30 09:53:25.042 15057 15057 F DEBUG   : Abort message: 'JNI DETECTED ERROR IN APPLICATION: input is not valid Modified UTF-8: illegal continuation byte 0x43
05-30 09:53:25.042 15057 15057 F DEBUG   :     string: '�Cx�w'
05-30 09:53:25.042 15057 15057 F DEBUG   :     input: '0xc7 <0x43> 0x07 0x78 0x1d 0x7f 0xe5 0x77'
05-30 09:53:25.042 15057 15057 F DEBUG   :     in call to NewStringUTF
05-30 09:53:25.042 15057 15057 F DEBUG   :     from java.lang.String com.example.re11113.jni.getkey()'
05-30 09:53:25.042 15057 15057 F DEBUG   :     x0  0000000000000000  x1  00000000000039c8  x2  0000000000000006  x3  0000007fd0d59dc0
05-30 09:53:25.042 15057 15057 F DEBUG   :     x4  5151441f43445342  x5  5151441f43445342  x6  5151441f43445342  x7  7f7f7f7f7f7f7f7f
05-30 09:53:25.042 15057 15057 F DEBUG   :     x8  00000000000000f0  x9  00000076672979e0  x10 0000000000000001  x11 00000076672d9370
05-30 09:53:25.042 15057 15057 F DEBUG   :     x12 000000000000473d  x13 000000000000015a  x14 0000007fd0d58be0  x15 000000074337fa42
05-30 09:53:25.042 15057 15057 F DEBUG   :     x16 0000007667346d50  x17 0000007667321eb0  x18 000000767865a000  x19 00000000000039c8
05-30 09:53:25.042 15057 15057 F DEBUG   :     x20 00000000000039c8  x21 00000000ffffffff  x22 00000073c5215000  x23 000000000000000b
05-30 09:53:25.042 15057 15057 F DEBUG   :     x24 0000007fd0d59f98  x25 0000007678063000  x26 0000007678063000  x27 0000000000000002
05-30 09:53:25.042 15057 15057 F DEBUG   :     x28 0000007fd0d5a7f0  x29 0000007fd0d59e40
05-30 09:53:25.042 15057 15057 F DEBUG   :     lr  00000076672c91c8  sp  0000007fd0d59da0  pc  00000076672c91f4  pst 0000000000001000
05-30 09:53:25.042 15057 15057 F DEBUG   : backtrace:
05-30 09:53:25.042 15057 15057 F DEBUG   :       #00 pc 00000000000531f4  /apex/com.android.runtime/lib64/bionic/libc.so (abort+164) (BuildId: dc4001c2ef2dfc23467040797a96840c)
05-30 09:53:25.042 15057 15057 F DEBUG   :       #01 pc 00000000006d2a4c  /apex/com.android.art/lib64/libart.so (art::Runtime::Abort(char const*)+704) (BuildId: d307dc6adc4105b5e392ad710770385d)
05-30 09:53:25.042 15057 15057 F DEBUG   :       #02 pc 0000000000016ea8  /apex/com.android.art/lib64/libbase.so (android::base::SetAborter(std::__1::function<void (char const*)>&&)::$_3::__invoke(char const*)+80) (BuildId: 420d56eac27a210c92900f3ddb760c86)
05-30 09:53:25.042 15057 15057 F DEBUG   :       #03 pc 0000000000016450  /apex/com.android.art/lib64/libbase.so (android::base::LogMessage::~LogMessage()+352) (BuildId: 420d56eac27a210c92900f3ddb760c86)
05-30 09:53:25.042 15057 15057 F DEBUG   :       #04 pc 0000000000445224  /apex/com.android.art/lib64/libart.so (art::JavaVMExt::JniAbort(char const*, char const*)+1612) (BuildId: d307dc6adc4105b5e392ad710770385d)
05-30 09:53:25.042 15057 15057 F DEBUG   :       #05 pc 00000000003292a4  /apex/com.android.art/lib64/libart.so (art::JavaVMExt::JniAbortV(char const*, char const*, std::__va_list)+108) (BuildId: d307dc6adc4105b5e392ad710770385d)
05-30 09:53:25.042 15057 15057 F DEBUG   :       #06 pc 000000000048d59c  /apex/com.android.art/lib64/libart.so (art::(anonymous namespace)::ScopedCheck::AbortF(char const*, ...) (.__uniq.99033978352804627313491551960229047428)+144) (BuildId: d307dc6adc4105b5e392ad710770385d)
05-30 09:53:25.042 15057 15057 F DEBUG   :       #07 pc 0000000000453804  /apex/com.android.art/lib64/libart.so (art::(anonymous namespace)::ScopedCheck::Check(art::ScopedObjectAccess&, bool, char const*, art::(anonymous namespace)::JniValueType*) (.__uniq.99033978352804627313491551960229047428)+3932) (BuildId: d307dc6adc4105b5e392ad710770385d)
05-30 09:53:25.042 15057 15057 F DEBUG   :       #08 pc 00000000005cbb94  /apex/com.android.art/lib64/libart.so (art::(anonymous namespace)::CheckJNI::NewStringUTF(_JNIEnv*, char const*) (.__uniq.99033978352804627313491551960229047428.llvm.7740520650885256591)+192) (BuildId: d307dc6adc4105b5e392ad710770385d)
05-30 09:53:25.042 15057 15057 F DEBUG   :       #09 pc 00000000000021e4  /data/app/~~9Utdaw0X5V98d6siE81kRA==/com.example.re11113-POnDDkNb6UF7kwVDA6YKzw==/lib/arm64/libSecret_entrance.so (Java_com_example_re11113_jni_getkey+504) (BuildId: f4e4adeea9bf275a7b45d8a84851f159242ef093)
05-30 09:53:25.042 15057 15057 F DEBUG   :       #10 pc 0000000000440554  /apex/com.android.art/lib64/libart.so (art_quick_generic_jni_trampoline+148) (BuildId: d307dc6adc4105b5e392ad710770385d)
05-30 09:53:25.042 15057 15057 F DEBUG   :       #11 pc 0000000000209398  /apex/com.android.art/lib64/libart.so (nterp_helper+152) (BuildId: d307dc6adc4105b5e392ad710770385d)

## 回复 by Shangwendada (#9)

*2024-5-30 10:02*

依旧是NewStringUTF传参抛出的异常，现在就是不知道这个传参从何而来，程序正常逻辑传的参数应该是正确的UTF8字符

## 回复 by Shangwendada (#10)

*2024-5-30 10:03*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  复现了AOSP12-pixel3不会，Android13官方系统pixel6，正确长度格式第一行不会崩溃，多按一次按钮就崩溃。05-30 09:53:25.042 15057 15057 F DEBU ...
>
>

依旧是NewStringUTF传参抛出的异常，现在就是不知道这个传参从何而来，程序正常逻辑传的参数应该是正确的UTF8字符

## 回复 by Xierluo (#12)

*2024-5-31 23:34*

这题是真的抽象，arm64v8的那个有混淆，armv7的没有混淆，部分手机能跑通，大部分手机跑不通
