---
title: x-zse-96,android端白盒AES(上)
url: https://bbs.kanxue.com/thread-281012.htm
tid: 281012
author: 杨如画
date: '2024-03-21'
tags: [Android安全, 混淆加固, 脱壳反混淆, HOOK注入, 逆向分析]
crawled_at: '2026-07-31T14:29:36+08:00'
replies: 2
---

# x-zse-96,android端,伪dex加固,so加固,白盒AES,字符串加密

上一篇某招聘软件的sig及sp参数被和谐掉了,所以懂得都懂啊!
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_SW62JKGTEXDUT4D.jpg)
因为web的api没有那么全,所以来看了下app的,ios的防护几乎没有,纸糊的一样,android端的有点复杂了,到最后我也没能完整的实现整个加密过程,我也只复现到DFA还原出了秘钥,iv也找到了,就是结果不对,也许是魔改AES的程度比较高,后续搞出来了的话再发下文吧.
网上找了下,都是分析web的,几乎没有分析app的,所以这篇应该算是首篇比较详细的文章了.

# 声明

本文章中所有内容仅供学习交流使用，不用于其他任何目的，不提供完整代码，抓包内容、敏感网址、数据接口等均已做脱敏处理，严禁用于商业用途和非法用途，否则由此产生的一切后果均与作者无关！

# 流程

## 抓包

抓包的话可以发现头部有个x-zse-96参数,和web是一样的名字.web的之前我也搞过,没什么难度说实话.
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_7CMF7DD4ZZHJHHE.jpg)

## 关键代码定位

正常来说是先查壳看看有没有加固,加固的脱壳,没加固的直接拖到jadx里反编译,因为我觉得这应该算是个大厂吧,凭着经验大厂很少加壳,所以我也没有查壳,直接扔到jadx里反编译了.
尝试搜索一下字符串x-zse-96
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_6KFZNMQNQ4YB96G.jpg)
什么也没有找到,其实是字符串被加密了
这个时候就有很多方法可以选择了,比如hook java层的系统hashmap,x-zse-96像是base64过的,也可以hook base64,又像是1.0_拼接后面一串得来的,也可以hook StringBuilder的tostring方法,甚至如果你觉得它是so层的加密也可以直接hook NewStringUTF函数.
这里我根据习惯先hook了hashmap

| 123456789 | `Java.perform(``function` `(){``var` `hashMap = Java.use(``"java.util.LinkedHashMap"``);` `//LinkedHashMap HashMap``hashMap.put.implementation =` `function` `(a, b) {``if``(a!=``null` `&& a.equals(``"X-Zse-96"``)){` `//X-Zse-96 x-zse-96``console.log(Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Throwable"``).$``new``()))``console.log(``"hashMap.put: "``, a, b);``}``return` `this``.put(a, b);``}}` |
|-|-|

什么也没有hook到,看来不是通过hashmap来添加的
接着我hook了StringBuilder的tostring方法,因为做过web的就知道,这个参数就是前面的1.0_拼接后面的得到的.事实上hook base64也是可以hook到的

| 123456789 | `var` `sb = Java.use(``"java.lang.StringBuilder"``);``sb.toString.implementation =` `function` `() {``var` `retval =` `this``.toString();``if` `(retval.indexOf(``"1.0_"``) != -1) {``console.log(``"StringBuilder.toString: "``, retval);``console.log(Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Throwable"``).$``new``()))``}``return` `retval;``}` |
|-|-|

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_ZRN8GHPNGFSN8XU.jpg)
从堆栈来看这个参数的生成是最后通过拦截器添加上去的,tostring的下面一行点进去看看
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_W42JZNSCPFYTNS9.jpg)
按堆栈的意思就是说这个sb.tostring就是结果了,hook了下b函数看看传进去的是不是x-zse-96,结果并不是,是一个32位的md5的结果,堆栈后面有一句native method,这里我也是比较困惑为什么按照堆栈里找的和反编译出来的结果不一样.
这里我以为是反编译出了什么问题,扔到pkid里查个壳看看
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_DX29KVHJF3N9WPD.jpg)
好家伙,不按常理出牌,正常来说大厂都不加壳的,看了一眼so的名字,dexhelper确实是梆梆企业版的
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_SGZS2GWHDPUK69F.jpg)
这个时候我拿出了我的px4定制的fart脱壳机,结果直接运行不起来,由于fart脱壳机太热门了,很多厂商对这个都有检测,我这个还是去过特征版的!
但是我记得这个梆梆加固主要是指令抽取,正常来说反编译的代码都是空的函数,为什么和jadx中的不一样,并且里面的dex都是有数据的.
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_VSEWNEHJ6QNM2VG.jpg)
用mt管理器看一下
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_GDTNMYCWKZB3NZQ.jpg)
发现是个伪加固,app虚晃一枪,要是正常人估计还在想办法怎么脱壳,这样的话也不用脱壳了,正好挺省事的.
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_WRFCC4ERU2X9XHU.jpg)

接着上面的逻辑,b2不为空,所以走了下面的逻辑,并且有一个addHeader的方法,这个像是往请求头里添加键值对.并且可以看到是添加了两组,hook一下

| 1234567891011 | `Java.perform(``function``(){``let Builder = Java.use(``"okhttp3.Request$Builder"``);``Builder[``"addHeader"``].implementation =` `function` `(str, str2) {``let result =` `this``[``"addHeader"``](str, str2);``if``(str==``'X-Zse-96'` `\|\| str==``'X-Zse-93'``){``console.log(`Builder.addHeader is called: str=${str}, str2=${str2}`);``console.log(`Builder.addHeader result=${result}`);``}``return` `result;``};``})` |
|-|-|

有结果,并且入参是x-zse-96的值
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_B7DZM7M3UU667S3.jpg)
这里的H.d("G51CEEF09BA7DF27F")其实就是字符串加密了,执行后结果就是x-zse-96,点进去是一个native方法.在so层加密了,现在很多app都弄成这样了,通过搜索几乎定位不到关键代码.
接着看
H.d("G38CD8525")就是1.0_了,hook H.d方法同样可以得到结果.真正的加密结果来自new String(this.c.a(a2)),a2是查询参数md5后的结果转为了字节数组.
接着一路跟下来到了native方法
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_8SY5P3KN68JHUPX.jpg)
看名字应该是一个aes.中间的str是一个很长的字符串,这个字符串每次都是一样的,但加密结果不一样,所以不用管这个,主要是1和3参数,分别是两个字节数组,1是params md5后的字节数组,第3个数组初步可以当成是aes的秘钥,如果是ecb模式的话(初步认为,其实是iv,一般人都会认为是秘钥的,因为标题说了白盒AES,秘钥内嵌在程序里)
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_5BT29EEWYCYZAPN.jpg)

so模块没有出现在代码里,前面我hook了jni方法NewStringUTF发现是libbangcle_crypto_tool.so,还可以hook libart.so来找动态注册以及libdl.so找静态注册.
接下来看libbangcle_crypto_tool.so,拖到ida里反汇编
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_WKWCJV7WHCW4PP8.jpg)
可以看到都是seg段,没有text段
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_JCHKSY332BHMMNW.jpg)
并且导出函数中也是有java中的静态注册函数
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_W3YSKWP3USF853J.jpg)
点过去也是这样,这里你应该感觉到不对劲了,似乎ida无法识别这个so,其实是so被加固了.

## dump so

so加固的碰到的比较少,这里我能想到的办法就是dump内存中的so,再修复一下.

| 1234567891011121314151617181920212223 | `function` `dump_so(so_name) {``Java.perform(``function` `() {``var` `currentApplication = Java.use(``"android.app.ActivityThread"``).currentApplication();``var` `dir = currentApplication.getApplicationContext().getFilesDir().getPath();``var` `libso = Process.getModuleByName(so_name);``console.log(``"[name]:"``, libso.name);``console.log(``"[base]:"``, libso.base);``console.log(``"[size]:"``, ptr(libso.size));``console.log(``"[path]:"``, libso.path);``var` `file_path = dir +` `"/"` `+ libso.name +` `"_"` `+ libso.base +` `"_"` `+ ptr(libso.size) +` `".so"``;``var` `file_handle =` `new` `File(file_path,` `"wb"``);``if` `(file_handle && file_handle !=` `null``) {``Memory.protect(ptr(libso.base), libso.size,` `'rwx'``);``var` `libso_buffer = ptr(libso.base).readByteArray(libso.size);``file_handle.write(libso_buffer);``file_handle.flush();``file_handle.close();``console.log(``"[dump]:"``, file_path);` `}``});``}``dump_so(``"libbangcle_crypto_tool.so"``)` |
|-|-|

dump下来后拖到电脑上修复一下就好了,工具<https://github.com/F8LEFT/SoFixer>
不过这样dump下来的效果不是很好,unidbg压根跑不起来这个so,里面还是有些数据无法访问,偏偏这些就是白盒aes中的关键数据s盒.折腾了大半天,一路打patch,最后还是放弃了unidbg这条路.
还是老老实实看so里的内容把,修复后的so至少可以看到代码段了.
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_K63M5R76S34X69S.jpg)
进来后先转jnienv对象,这样代码会好分析些.
这个函数稍微有点控制流混淆以及虚假指令
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_HYQTYMV4D6PH652.jpg)
不过从后往前推就可以看出来走的那个函数了,v12是返回值,v12来自v10创建的字节数组,v10来着上面的8E74函数,这个函数就是核心的加密流程了,点进去瞧瞧
v9是a1赋值过来的,所以也是env对象![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_8TDKZKKFDHGG9SQ.jpg)
进来后看左下角的流程图,用了好几个switch case来判断走哪个流程,还好我们知道我们的函数是laes,并且从提示来看知道是cbc模式,也就是说需要一个初始化iv,这个laes的意思应该是local aes,字面意思就是本地的aes.从这个函数进去看看.进去后再进入一个laes就到了下面这个图
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_T8ZFCNNCQH6RMUW.jpg)
前面那些内容函数最好hook看一下入参,其实我都hook过了,只是没写,写了篇幅太长了,后面还有白盒AES,这里有个a3>15,a3是明文的长度,aes分组长度都是16个字节,所以这里应该是判断明文的长度来决定加密几轮.这个a6是个函数
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_7QDWS3EPPG6KQWB.jpg)
直接点进去是这样,不知道是不是加固的原因,这里只好看汇编了,鼠标放到a6那,按tab转汇编视图
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_88BK75WBNQGXNVR.jpg)

blx R12,意思是跳到R12寄存器中的地址执行,这里直接看看不出跳到哪,可以用frida 的inlinehook看看

| 12345678910111213 | `function` `inlineHook() {``var` `nativePointer = Module.findBaseAddress(``"libbangcle_crypto_tool.so"``);``var` `hookAddr = nativePointer.add(0x6140);` `// 6140` `Interceptor.attach(hookAddr, {``onEnter:` `function` `(args) {``console.log(nativePointer)``console.log(``"onEnter: "``,` `this``.context.r12);``}, onLeave:` `function` `(retval) {` `}``});``}``inlineHook()` |
|-|-|

这个so是32位的,正常情况下地址是要加1的,但是因为这个so是从内存中dump下来的,所以不需要加1了,这个需要注意下.结果是0x6420.这个app的好几年都是用的这个so,一点都没变,偏移也没变,属于是so加固了以为高枕无忧了.
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_PDZRFPFNTEGM9BQ.jpg)
进来后看到一个名字WB white box,白盒的意思,现在的安卓逆向java层的加密已经几乎没有了,so的逆向上来就是各种白盒,各种魔改算法以及自写算法,不如直接去搞ios逆向,现在的ios逆向很多都是调用的系统函数,可以直接hook整个系统函数,类似安卓的那个算法助手,而且ios逆向的人少,对抗少,系统也闭源,风控也比安卓小得多,现在从0开始搞安卓逆向难度很大,就算你有天赋至少也需要半年的时间(ios的可以看看沐阳老哥的课程,当然只是题外话,后面也会出几篇文章从0开始搞ios逆向.)
之前我发过一篇白盒aes的文章,很多js逆向的反馈压根没听过这个词,感觉很高级的样子,正常,js逆向你可以直接扣js啊,ida中的这个伪c代码扣下来很难跑通,对c的要求有点高.我是扣了一下,跑不起来,放弃了.
看下面的内容前你最好了解下什么是白盒AES,这是我从网上找的一篇文章<https://blog.csdn.net/qq_37638441/article/details/128968233>
接着正题,前面java层传入了一个参数3,16个字节,如果是白盒aes的话,那这个大概率就是iv了.

| 123456789101112131415161718192021222324 | `function` `callAES(){``var` `base_addr = Module.findBaseAddress(``"libbangcle_crypto_tool.so"``);``var` `real_addr = base_addr.add(0x6420);``var` `wbaes_encrypt_ecb_func =` `new` `NativeFunction(real_addr,` `"void"``, [``"pointer"``,` `"pointer"``,` `"pointer"``,` `"pointer"``,``"pointer"``]);``inputPtr = Memory.alloc(0x10);``var` `inputArray = hexToBytes(``"b11812121a8886852e2e868786252e2e"``);``Memory.writeByteArray(inputPtr, inputArray)` `var` `inputPtr3 = Memory.alloc(0x10);``// var inputArray = hexToBytes("803d17b5b00000000400000080000000");``var` `inputArray = hexToBytes(``"401948d4b00000000400000080000000"``);``Memory.writeByteArray(inputPtr3, inputArray)` `var` `inputPtr4 = Memory.alloc(0x10);``var` `inputArray = hexToBytes(``"00000000000000000000000000000000"``);``Memory.writeByteArray(inputPtr4, inputArray)` `var` `inputPtr5 = Memory.alloc(0x10);``var` `inputArray = hexToBytes(``"00000000000000000000000000000000"``);``Memory.writeByteArray(inputPtr5, inputArray)` `wbaes_encrypt_ecb_func(inputPtr, inputPtr, inputPtr3, inputPtr4,inputPtr5);``console.log(hexdump(inputPtr,{length: 0x10}));``}` |
|-|-|

so主动调用这个函数,其实它有5个参数,ida识别成了3个.前两个是同一个参数,iv和明文异或的结果,cbc模式下比ecb模式多了个iv,后两个参数作用不大,不用管,关键是第3个参数,有点奇怪,现在我也没搞清楚它的作用是什么,后面再说吧.

## DFA攻击

调用后有结果,结果也是正确的.接下来寻找dfa攻击点,第8次列混淆到第9次列混淆之间,并且需要寻找到state块
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_TEPPHJNW2YEMWXR.jpg)
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_6EN9SNV2GS6XZV2.jpg)

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_6BFNNHYJD9JWXB7.jpg)

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_QTBMUKKZKKWNCG9.jpg)
按aes的算法应该是这样,最后面的第十轮少了列混淆,所以不在这个循环里面.
加下来寻找哪个是state块,初看选了result,每次核心运算都有他,一hook发现经过9轮他的值都不变,直到最后赋值结果的时候才变了.
后来仔细看了下v20也有可能,但是这个v20不太好hook他的变化,因为这里没有什么函数调用,所有没有入参什么的,要hook到这个v20的地址有些困难
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_WKP4G5ZPGCGQ3QT.jpg)

这里我寻找九轮循环最开始的地方hook上,这个赋值写的也有点复杂.鼠标放到v20的地方,转汇编更方便看.
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_8BJFPHVECNPBT4J.jpg)
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_7X2JNMP5DTMF54X.jpg)
这里鼠标放到var_34按h可以转成立即数.STRB R3, [R11,#-52]
这条指令的意思就是将寄存器 R3 中的值存储到距离 R11 寄存器所指向的内存位置偏移为 -52 的地方。所以v20的地址就是R11的地址减去52的偏移的位置处.

| 123456789101112 | `function` `hookwb(){``var` `count = 0;``var` `base_addr = Module.findBaseAddress(``"libbangcle_crypto_tool.so"``);``var` `real_addr = base_addr.add(0x6580)``Interceptor.attach(real_addr, {``onEnter:` `function` `(args) {``count += 1;``console.log(``"onEnter: "``,count, hexdump(``this``.context.r11.sub(0x24),{length:0x10}));``console.log(``"start:"``+count);``}``});``}` |
|-|-|

结果也确实是9轮,接下来进行dfa攻击.

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768 | `function` `hexToBytes(hex) {``for` `(``var` `bytes = [], c = 0; c < hex.length; c += 2)``bytes.push(parseInt(hex.substr(c, 2), 16));``return` `bytes;``}``var` `inputPtr;``function` `callAES(){``var` `base_addr = Module.findBaseAddress(``"libbangcle_crypto_tool.so"``);``var` `real_addr = base_addr.add(0x6420);``var` `wbaes_encrypt_ecb_func =` `new` `NativeFunction(real_addr,` `"void"``, [``"pointer"``,` `"pointer"``,` `"pointer"``,` `"pointer"``,``"pointer"``]);``inputPtr = Memory.alloc(0x10);``var` `inputArray = hexToBytes(``"b11812121a8886852e2e868786252e2e"``);``Memory.writeByteArray(inputPtr, inputArray)` `var` `inputPtr3 = Memory.alloc(0x10);``// var inputArray = hexToBytes("803d17b5b00000000400000080000000");``var` `inputArray = hexToBytes(``"401948d4b00000000400000080000000"``);``Memory.writeByteArray(inputPtr3, inputArray)` `var` `inputPtr4 = Memory.alloc(0x10);``var` `inputArray = hexToBytes(``"00000000000000000000000000000000"``);``Memory.writeByteArray(inputPtr4, inputArray)` `var` `inputPtr5 = Memory.alloc(0x10);``var` `inputArray = hexToBytes(``"00000000000000000000000000000000"``);``Memory.writeByteArray(inputPtr5, inputArray)` `wbaes_encrypt_ecb_func(inputPtr, inputPtr, inputPtr3, inputPtr4,inputPtr5);``// var output = Memory.readByteArray(inputPtr, 0x10);``// console.log(bufferToHex(output))``console.log(hexdump(inputPtr,{length: 0x10}));``}``function` `bufferToHex (buffer) {``return` `[...``new` `Uint8Array (buffer)]``.map (b => b.toString (16).padStart (2,` `"0"``))``.join (``""``);``}``function` `hookwb(){``var` `count = 0;``var` `base_addr = Module.findBaseAddress(``"libbangcle_crypto_tool.so"``);``var` `real_addr = base_addr.add(0x6580)``Interceptor.attach(real_addr, {``onEnter:` `function` `(args) {``count += 1;``console.log(``"onEnter: "``,count, hexdump(``this``.context.r11.sub(0x24),{length:0x10}));``if``(count===9){``this``.context.r11.sub(0x24).add(randomNum(0,15)).writeS8(randomNum(0, 0xff));``console.log(``"onEnter: "``, hexdump(``this``.context.r11.sub(0x24),{length:0x10}));``}``console.log(``"start:"``+count);``}``});``}``function` `randomNum(minNum,maxNum){``if` `(arguments.length === 1) {``return` `parseInt(Math.random() * minNum + 1, 10);``}` `else` `if` `(arguments.length === 2) {``return` `parseInt(Math.random() * (maxNum - minNum + 1) + minNum, 10);``}` `else` `{``return` `0;``}``}``function` `dfa(){``for``(``var` `i=0;i<300;i++){``hookwb()``callAES()``}``}` |
|-|-|

连续调用300次后取得故障密文再用phoenixAES拿到第10轮秘钥E48E8AA0E4449B580CF7ECC13CC17CD3,接着用aes_keyschedule还原出主密钥6BA6737912D31F3A1B53066645FABEA3
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_ZYA7X3VUBGE8HF4.jpg)
秘钥6BA6737912D31F3A1B53066645FABEA3,iv99303a3a32343a3992923a3b3a999292(java层的)都有了.事实上只有1轮的话,也可以直接用ecb模式,因为入参1就是明文和iv异或的结果,拿去加密一下发现结果不对......
前面我就说了这个参数3不太清楚是什么,因为这个入参这个时刻下主动调用是这个结果,重开app主动调用逻辑不变结果取变了.这里有个很大的问号?
这里先分析到这里吧,先埋个坑,后面有空再看看吧.

# 最后

微信公众号
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_CK7VKQDWET2654Y.jpg)
知识星球
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_FC7EDY4SG7GFBAM.jpg)
如果你觉得这篇文章对你有帮助,不妨请作者喝杯咖啡吧!
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202403/983110_TP63E7VZ5E875V4.jpg)

---

# 回复

## 回复 by 杨如画 (#2)

*2024-3-21 10:29*

app版本是9.41.0

## 回复 by code1024 (#3)

*2024-4-27 15:28*

现在还要过环境检测了
