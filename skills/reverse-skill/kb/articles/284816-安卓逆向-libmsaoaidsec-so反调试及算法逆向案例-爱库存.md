---
title: '[原创]【安卓逆向】libmsaoaidsec.so反调试及算法逆向案例(爱库存)'
url: https://bbs.kanxue.com/thread-284816.htm
tid: 284816
author: 太岁又沐风
date: '2024-12-14'
tags: [Android安全, 原创, 协议分析, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:16:54+08:00'
replies: 10
---

# 1. 抓包并且hook

## 1.1 登录请求抓包`charles + 系统代理`就可以抓包

`charles + 系统代理`就可以抓包

```
POST /market-activity/register/intention?appid=38741001&did=c69583270de11ab95119c90cff96c59f&noncestr=69fc49&svs=v3&timestamp=1734095423&sign=a9be61f92bdee069d00b34e2415443332211a27fc0604a9d4b2fe3d972af0137 HTTP/1.1
Auth-Token:
User-Agent: AndroidSDKbuiltforarm64 android 9 7.59.0 2.0
token: 477c33c6-2f38-4363-a670-314393b47c1b
AKC-MODEL: AndroidSDKbuiltforarm64
AKC-OS: android
AKC-OS-VERSION: 9
AKC-APP-VERSION: 7.59.0
AKC-APP-API-VERSION: 2.0
AKC-APP-BUILD-VERSION: 75900
AKC-DID: c69583270de11ab95119c90cff96c59f
AKC-APP-CHANNEL: 2005
applicationId: com.aikucun.akapp
x-auth-token:
live-channel: 20
dtdToken: 675c3035o69t16VHDZSesSmuU0Saf7ahv6rlEk13
app2H5Token:
uid:
subUid:
APP-LOGIN-CHANNEL: akcApp
app-request-id: 3ed72013807d4df9a7896c6ad9a47e0e
PAGE-NAME: %E7%99%BB%E5%BD%95
TRACKER-SESSION-ID: 2a99dad141359a53
APP-USER-TYPE: 6
Content-Type: application/json; charset=UTF-8
Content-Length: 134
Host: zuul.aikucun.com
Connection: Keep-Alive
Accept-Encoding: gzip

{"smsChecking":false,"channelApp":"akapp","mobile":"13122223333","channel":"2005","deviceId":"358240051111110","channelPattern":"app"}
```

我们本次主要分析这个`sign`

## 1.2 frida检测

附加frida，发现秒退，这个时候我们已经是魔改的frida[GitHub - taisuii/rusda: 对frida 16.2.1的patch](https://github.com/taisuii/rusda)并且更换端口了

| 123456789101112131415161718 | `(base) r@R aikucun % frida -H 127.0.0.1:12345 -f com.aikucun.akapp``____``/ _  \|   Frida 16.2.1 - A world-class dynamic instrumentation toolkit``\| (_\| \|``> _  \|   Commands:``/_/` `\|_\|       help      -> Displays the help system``. . . .       object?   -> Display information about` `'object'``. . . .` `exit``/quit` `-> Exit``. . . .``. . . .   More info at https:``//frida``.re``/docs/home/``. . . .``. . . .   Connected to 127.0.0.1:12345 (``id``=socket@127.0.0.1:12345)``Spawned `com.aikucun.akapp`. Resuming main thread!` `[Remote::com.aikucun.akapp ]-> Process terminated``[Remote::com.aikucun.akapp ]->` `Thank you` `for` `using Frida!``(base) r@R aikucun %` |
|-|-|

hook 一下dlopen

| 12345678910111213141516171819202122 | `function` `hookdlopen() {``var` `dlopen = Module.findExportByName(``null``,` `"dlopen"``);``var` `android_dlopen_ext = Module.findExportByName(``null``,` `"android_dlopen_ext"``);``Interceptor.attach(dlopen, {``onEnter:` `function` `(args) {``var` `path_ptr = args[0];``var` `path = ptr(path_ptr).readCString();``console.log(``"[dlopen:]"``, path);``},``onLeave:` `function` `(retval) {``}``});``Interceptor.attach(android_dlopen_ext, {``onEnter:` `function` `(args) {``var` `path_ptr = args[0];``var` `path = ptr(path_ptr).readCString();``console.log(``"[dlopen_ext:]"``, path);``},``onLeave:` `function` `(retval) {``}``});``}` |
|-|-|

在 libmsaoaidsec.so 处退出，app没有结束，frida被杀掉了

| 123456789101112131415161718192021222324 | `(base) r@R aikucun % frida -H 127.0.0.1:12345 -f com.aikucun.akapp -l hook.js``____``/ _  \|   Frida 16.2.1 - A world-class dynamic instrumentation toolkit``\| (_\| \|``> _  \|   Commands:``/_/` `\|_\|       help      -> Displays the help system``. . . .       object?   -> Display information about` `'object'``. . . .` `exit``/quit` `-> Exit``. . . .``. . . .   More info at https:``//frida``.re``/docs/home/``. . . .``. . . .   Connected to 127.0.0.1:12345 (``id``=socket@127.0.0.1:12345)``Spawned `com.aikucun.akapp`. Resuming main thread!` `[Remote::com.aikucun.akapp ]-> [dlopen_ext:]` `/system/framework/oat/arm64/org``.apache.http.legacy.boot.odex``[dlopen_ext:]` `/data/app/com``.aikucun.akapp-Gqd0OXL0bAt7H-zUkRSKuA==``/oat/arm64/base``.odex``[dlopen_ext:]` `/data/app/com``.aikucun.akapp-Gqd0OXL0bAt7H-zUkRSKuA==``/lib/arm64/libc``++_shared.so``[dlopen_ext:]` `/data/app/com``.aikucun.akapp-Gqd0OXL0bAt7H-zUkRSKuA==``/lib/arm64/libmarsxlog``.so``[dlopen_ext:]` `/data/app/com``.aikucun.akapp-Gqd0OXL0bAt7H-zUkRSKuA==``/lib/arm64/libmmkv``.so``[dlopen_ext:]` `/data/app/com``.aikucun.akapp-Gqd0OXL0bAt7H-zUkRSKuA==``/lib/arm64/libmsaoaidsec``.so``Process terminated``[Remote::com.aikucun.akapp ]->` `Thank you` `for` `using Frida!``(base) r@R aikucun %` |
|-|-|

## 1.3 过检测

这个检测其实就是在加载so的时候，创建了检测线程，具体的话可以分析`libmsaoaidsec.so`的 `.init_proc`函数

那么其实已经有很多网友分析过这个了，hook`__system_property_get`函数寻找hook时机，找到创建线程的地方然后把它替换掉固然是个好方法

不过这里直接粗暴一点，hook `pthread_create`，只要是在`libmsaoaidsec.so`里面创建的线程，我们统统替换掉

| 123456789101112131415161718192021222324252627282930 | `function` `replace(addr) {``Interceptor.replace(addr,` `new` `NativeCallback(``function` `() {``console.log(`replace ${addr}`)``},` `'void'``, []));``}``function` `hook_pthread_create(soname) {``let replaces = [];` `// 用来记录已经替换的函数偏移``// int pthread_create(pthread_t *thread, const pthread_attr_t *attr, void *(*start_routine)(void*), void *arg);``let pthread_create = Module.findExportByName(``"libc.so"``,` `"pthread_create"``);``if` `(!pthread_create) {``console.log(``"pthread_create not found in libc.so"``);``return``;``}``Interceptor.attach(pthread_create, {``onEnter:` `function` `(args) {``let start_routine = args[2];``let libmsaoaidsec = Process.findModuleByAddress(start_routine);``if` `(libmsaoaidsec && libmsaoaidsec.name === soname) {``if` `(!replaces.includes(start_routine.toString())) {``let libmsaoaidsec_addr = libmsaoaidsec.base;``let func_offset = start_routine.sub(libmsaoaidsec_addr);``console.log(``"The thread function offset address in libmsaoaidsec.so("` `+ libmsaoaidsec_addr +` `") is "` `+ func_offset);``console.log(``"replace: "` `+ func_offset);``replaces.push(start_routine.toString());``replace(start_routine)``}``}``}``});``}` |
|-|-|

成功过掉检测，一共两处线程创建的地方：0x175f8和0x16d30，

| 12345678910111213141516 | `(base) r@R aikucun % frida -H 127.0.0.1:12345 -l hook.js -f com.aikucun.akapp``____``/ _  \|   Frida 16.2.1 - A world-class dynamic instrumentation toolkit``\| (_\| \|``> _  \|   Commands:``/_/` `\|_\|       help      -> Displays the help system``. . . .       object?   -> Display information about` `'object'``. . . .` `exit``/quit` `-> Exit``. . . .``. . . .   More info at https:``//frida``.re``/docs/home/``. . . .``. . . .   Connected to 127.0.0.1:12345 (``id``=socket@127.0.0.1:12345)``Spawned `com.aikucun.akapp`. Resuming main thread!` `[Remote::com.aikucun.akapp ]-> replace 0x7b6b55a5f8``replace 0x7b6b559d30``[Remote::com.aikucun.akapp ]->` |
|-|-|

这个检测在很多app中都是存在的，这个方式在其他app中不一定适用

# 2. 算法还原

## 2.1. java层

无套路定位到
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202412/957122_EHY3BQ8VC5NC2KN.png)

## 2.2. so层

无套路，可读性非常高，都是字符串拼接

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202412/957122_F9SQRDYRUJXKWEA.png)

这个digest函数是调用的java层进行加密的

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202412/957122_KX52J487D3C5KRT.png)

## 2.3 算法还原

获取加密参数以及sha256 的参数，结果一致

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253 | `function` `hook() {``if` `(Java.available) {` `console.log(``"Java hook start"``)``Java.perform(``function` `() {``let MXSecurity = Java.use(``"com.mengxiang.arch.security.MXSecurity"``);``MXSecurity[``"signV3"``].implementation =` `function` `(url, nonceStr, timestamp, body) {``console.log(`MXSecurity.signV3 is called: url=${url}, nonceStr=${nonceStr}, timestamp=${timestamp}, body=${body}`);``let result =` `this``[``"signV3"``](url, nonceStr, timestamp, body);``console.log(`MXSecurity.signV3 result=${result}`);``return` `result;``};` `let LoginModel = Java.use(``"com.aikucun.akapp.business.login.model.LoginModel"``);``LoginModel[``"authCode"``].implementation =` `function` `(phoneNum, userid, type, rcsTraceId, captchaToken) {``console.log(`LoginModel.authCode is called: phoneNum=${phoneNum}, userid=${userid}, type=${type}, rcsTraceId=${rcsTraceId}, captchaToken=${captchaToken}`);``let result =` `this``[``"authCode"``](phoneNum, userid, type, rcsTraceId, captchaToken);``console.log(`LoginModel.authCode result=${result}`);``return` `result;``};` `let MessageDigest = Java.use(``"java.security.MessageDigest"``);``MessageDigest.digest.overload(``"[B"``).implementation =` `function` `(input) {``const byteArray = Java.array(``'byte'``, input);``// 将 byte[] 转换为字符串``let plaintext =` `''``;``for` `(let i = 0; i < byteArray.length; i++) {``plaintext += String.fromCharCode(byteArray[i] & 0xff);``}``if``(plaintext.indexOf(``"38741001"``) != -1){``console.log(``"[+] MessageDigest.digest(byte[]) called"``);``console.log(``"Plaintext: "` `+ plaintext);``}``// 调用原始方法``return` `this``.digest(input);``};``});` `}` `else` `{``console.log(``"Java.available is false"``)``}``}``var` `hook_num = 0``function` `replace(addr) {``Interceptor.replace(addr,` `new` `NativeCallback(``function` `() {``console.log(`replace ${addr}`)``hook_num = hook_num + 1``if` `(hook_num >= 2) {``hook()``}``},` `'void'``, []));` `}` |
|-|-|

| 123456789101112131415161718192021222324252627282930313233343536 | `(base) r@R aikucun % frida -H 127.0.0.1:12345 -l hook.js -f com.aikucun.akapp``____``/ _  \|   Frida 16.2.1 - A world-class dynamic instrumentation toolkit``\| (_\| \|``> _  \|   Commands:``/_/` `\|_\|       help      -> Displays the help system``. . . .       object?   -> Display information about` `'object'``. . . .` `exit``/quit` `-> Exit``. . . .``. . . .   More info at https:``//frida``.re``/docs/home/``. . . .``. . . .   Connected to 127.0.0.1:12345 (``id``=socket@127.0.0.1:12345)``Spawned `com.aikucun.akapp`. Resuming main thread!` `[Remote::com.aikucun.akapp ]-> The thread` `function` `offset address` `in` `libmsaoaidsec.so(0x7b6b5e4000) is 0x175f8``replace: 0x175f8``The thread` `function` `offset address` `in` `libmsaoaidsec.so(0x7b6b5e4000) is 0x16d30``replace: 0x16d30``replace 0x7b6b5fb5f8``replace 0x7b6b5fad30``Java hook start``MXSecurity.signV3 is called: url=https:``//zuul``.aikucun.com``/akucun-base-data-new/base/address/selectAddrVersion``?appid=38741001&did=8e72f37ab5db201b91de47172047e760&noncestr=3d0f39&svs=v3&timestamp=1734184260, nonceStr=3d0f39, timestamp=1734184260, body=``[+] MessageDigest.digest(byte[]) called``Plaintext: appid=38741001&svs=v3&noncestr=3d0f39&timestamp=1734184260&secret=04fdc5e4d9c7420e896ee92b17c68e9f&url=https:``//zuul``.aikucun.com``/akucun-base-data-new/base/address/selectAddrVersion``?appid=38741001&did=8e72f37ab5db201b91de47172047e760&noncestr=3d0f39&svs=v3&timestamp=1734184260``MXSecurity.signV3 result=5c927464497d321ac3ff49d817cc571d696da21e828ea75bdc9e3465af8a17ae``MXSecurity.signV3 is called: url=https:``//m``.xiangdian.com``/api/mshop/mshop-aggr-prod/outer/common/bwl/isHitByBatch``?appid=38741001&did=8e72f37ab5db201b91de47172047e760&noncestr=22f096&svs=v3&timestamp=1734184260, nonceStr=22f096, timestamp=1734184260, body=398a40be5a2a6a5a742f35b1b606277a``[+] MessageDigest.digest(byte[]) called``Plaintext: appid=38741001&svs=v3&noncestr=22f096&timestamp=1734184260&secret=04fdc5e4d9c7420e896ee92b17c68e9f&url=https:``//m``.xiangdian.com``/api/mshop/mshop-aggr-prod/outer/common/bwl/isHitByBatch``?appid=38741001&did=8e72f37ab5db201b91de47172047e760&noncestr=22f096&svs=v3&timestamp=1734184260&398a40be5a2a6a5a742f35b1b606277a``MXSecurity.signV3 result=bd809e352277f9357b436ed424a8fd62b546f415e7f9e7875a05bda5aa5f6704``MXSecurity.signV3 is called: url=https:``//m``.xiangdian.com``/api/mshop/mshop-aggr-prod/outer/v1/material/create/createAuth``?appid=38741001&did=8e72f37ab5db201b91de47172047e760&noncestr=9908c3&svs=v3&timestamp=1734184261, nonceStr=9908c3, timestamp=1734184261, body=37a6259cc0c1dae299a7866489dff0bd``[+] MessageDigest.digest(byte[]) called``Plaintext: appid=38741001&svs=v3&noncestr=9908c3&timestamp=1734184261&secret=04fdc5e4d9c7420e896ee92b17c68e9f&url=https:``//m``.xiangdian.com``/api/mshop/mshop-aggr-prod/outer/v1/material/create/createAuth``?appid=38741001&did=8e72f37ab5db201b91de47172047e760&noncestr=9908c3&svs=v3&timestamp=1734184261&37a6259cc0c1dae299a7866489dff0bd``MXSecurity.signV3 result=1181b2330a12f04c2501193430b50712d6f0187a2f87eaf0fe861016e2e1f6a7``MXSecurity.signV3 is called: url=https:``//zuul``.aikucun.com``/appconfigmgt/api/v1/download/config``?appid=38741001&did=8e72f37ab5db201b91de47172047e760&noncestr=32a49b&svs=v3&timestamp=1734184263, nonceStr=32a49b, timestamp=1734184263, body=2288e58e8bda39d24cb10b10af923d50``[+] MessageDigest.digest(byte[]) called``Plaintext: appid=38741001&svs=v3&noncestr=32a49b&timestamp=1734184263&secret=04fdc5e4d9c7420e896ee92b17c68e9f&url=https:``//zuul``.aikucun.com``/appconfigmgt/api/v1/download/config``?appid=38741001&did=8e72f37ab5db201b91de47172047e760&noncestr=32a49b&svs=v3&timestamp=1734184263&2288e58e8bda39d24cb10b10af923d50``MXSecurity.signV3 result=4d9b7d406b6ce2e44dc602b8c83a49b4b20ec944bea69d72aae3790249ed7127` |
|-|-|

上传的附件：
- hook.js

（4.15kb，78次下载）

---

# 回复

## 回复 by mr2222 (#2)

*2024-12-15 16:23*

先赞再看

## 回复 by bbpk (#3)

*2024-12-16 12:25*

这个so是哪家的产品？在很多apk里都见过

## 回复 by 霸王茶几 (#4)

*2024-12-16 16:00*

大佬能讲下“hook__system_property_get函数寻找hook时机” 这个思路吗？我的情况直接hook不行

## 回复 by mb_ifqtwleh (#5)

*2024-12-17 15:17*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  bbpk](https://bbs.kanxue.com/user-163196.htm)
>
>  这个so是哪家的产品？在很多apk里都见过
>
>

msa ，移动安全联盟

## 回复 by 太岁又沐风 (#6)

*2024-12-18 10:43*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  霸王茶几](https://bbs.kanxue.com/user-1002632.htm)
>
>  大佬能讲下“hook__system_property_get函数寻找hook时机” 这个思路吗？我的情况直接hook不行
>
>

__system_property_get 是获取系统的一些信息的，参数是key和value，一般情况下这个so在创建检测线程之前会调用这个函数获取一些系统的信息，当这个函数在so中被调用的时候再hook线程创建，然后patch掉或者替换掉就可以过检测了

## 回复 by ZPastor (#7)

*2024-12-20 11:04*

延时检测应该怎么绕过呢，只hook dlopen函数不会闪退，hook其他函数才退出。

## 回复 by shmilyaxy (#8)

*2024-12-23 18:21*

暴力一点，试试在data/app...中直接删除这两个so看看会不会挂掉

## 回复 by vdaoren (#9)

*2024-12-23 20:31*

>
> [shmilyaxy](https://bbs.kanxue.com/user-941979.htm)
>
>  暴力一点，试试在data/app...中直接删除这两个so看看会不会挂掉
>
>

我在某一个app里面做过这种操作，完全没问题

## 回复 by bbpk (#10)

*2024-12-24 12:34*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ifqtwleh](https://bbs.kanxue.com/user-1009135.htm)
>
>  msa ，移动安全联盟
>
>

好的，谢谢

## 回复 by 盛宝不喝肾宝 (#11)

*2025-2-6 14:07*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  vdaoren](https://bbs.kanxue.com/user-714402.htm)
>
>  我在某一个app里面做过这种操作，完全没问题
>
>

我猜是某物![image](https://bbs.kanxue.com/view/img/face/065.gif)
