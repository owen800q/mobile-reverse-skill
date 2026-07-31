---
title: '[原创]unidbg直接调用tiktok so生成签名'
url: https://bbs.kanxue.com/thread-285623.htm
tid: 285623
author: CCTV果冻爽
date: '2025-02-18'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T15:59:49+08:00'
replies: 613
---

Tiktok版本： 33.2.5 （24年1月25日）
1、前言
 通过对Tiktok抓包发现TikTok的所有http请求的头部增加了参数签名（x-argus、x-goron、x-khronos、x-ladon）：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/770147_DRQWH8YADN8T64F.webp)

2、获取关键函数
直接将apk文件用jadx工具反编译，搜索关键字x-argus等，未搜索到任何关键字：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/770147_NY3U8MVDU64WDHW.webp)

使用frida hook java层 Header对象的构造方法，发现有监控到https请求头设置，但是始终没有发现签名字段

| 12345 | `var Header` `=` `Java.use(``"X.2jn"``);``Header.$init.implementation` `=` `function(key, val) {``console.log(key` `+` `" : "` `+` `val);``this.$init(key, val);``}` |
|-|-|

接着尝试hook interceptor拦截器，打印出请求头部，结果输出的请求头部中还是没有签名字段

| 123456789101112131415161718192021222324252627282930 | `/``/``添加intercept``var Request` `=` `Java.use(``"X.LGn"``);``Request.LIZJ.implementation` `=` `function(intercept){``var newObj` `=` `Java.cast(intercept, Java.use(``"java.lang.Object"``));``/``/``console.log(newObj.getClass());``var new_cls` `=` `newObj.getClass();``var class_name` `=` `new_cls.getName();` `if``(!mmp[class_name]) {``mmp[class_name]` `=` `1``;``var hook_class` `=` `Java.use(class_name);``hook_class.intercept.implementation` `=` `function(tt){``var res` `=` `this.intercept(tt);``/``*`              `var rq` `=` `tt.request();``console.log(rq.getUrl());` `*``/` `var request` `=` `getFieldVal(res,` `"LIZ"``);``/``/``console.log(getFieldVal(request,` `"LIZ"``));``/``/``console.log(getFieldVal(request,` `"LIZJ"``));``/``/``console.log(getFieldVal(request,` `"LJI"``));` `var headers` `=` `getFieldVal(request,` `"LIZLLL"``);``/``/``console.log(headers);``/``/``console.log(``"----------------------------------------------------"``);``return` `res;``}``}` `this.LIZJ(intercept);``}` |
|-|-|

Java层找了一遍始终找不到签名关键字符串，那很大可能是在native层设置，在native层在 https请求发出时进行设置。TikTok使用 cronet网络库 。将libsscronet拖IDA反编译，搜索 x-gorfon 关键字，确实找到了：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/770147_22MQ8Z84NJQ7DR2.webp)

结合 cronet源码，找到Native层设置请求Header函数：

| 1234567891011 | `void HttpRequestHeaders::SetHeader(const base::StringPiece& key,``const base::StringPiece& value) {``DCHECK(HttpUtil::IsValidHeaderName(key.as_string()));``/``/` `TODO(ricea): Revert this. See crbug.com``/``627398.``CHECK(HttpUtil::IsValidHeaderValue(value.as_string()));``HeaderVector::iterator it` `=` `FindHeader(key);``if` `(it !``=` `headers_.end())``it``-``>value.assign(value.data(), value.size());``else``headers_.push_back(HeaderKeyValuePair(key, value));``}` |
|-|-|

定位到该libsscronet中偏移为：0x2C44BC，HOOK该地址并打印出参数：

| 1234567891011 | `var SetHeaders` `=` `lib.base.add(``0x2C44BC``);``Interceptor.attach(SetHeaders, {``onEnter: function (args) {``var key` `=` `args[``1``].readPointer().readUtf8String();` `/``/``第一个属性是字符串的地址, 第二个属性长度``var val` `=` `args[``2``].readPointer().readUtf8String();``console.log(key` `+` `" : "` `+` `val);``},``onLeave: function (retval) {` `}``});` |
|-|-|

这次全部头部都可以看到了，完美！
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/770147_MS3EUCUMMPVCWT8.webp)

然后打印设置参数签名字段时的调用栈：

| 12345678910111213141516 | `var SetHeaders` `=` `lib.base.add(``0x2C44BC``);``Interceptor.attach(SetHeaders, {``onEnter: function (args) {` `var key` `=` `args[``1``].readPointer().readUtf8String();` `/``/``第一个属性是字符串的地址, 第二个属性长度``var val` `=` `args[``2``].readPointer().readUtf8String();``if``(key.indexOf(``"X-Gorgon"``) !``=``=` `-``1``) {``console.log(key` `+` `" : "` `+` `val);``console.log(``'SetHeaders called from:\n'` `+` `Thread.backtrace(this.context, Backtracer.ACCURATE).``map``(DebugSymbol.fromAddress).join(``'\n'``)` `+` `'\n'``);``console.log(``"---------------------------end----------------------------------"``);``}``},``onLeave: function (retval) {` `}``});` |
|-|-|

有两处调用，分别是 0x3a662c 和 0x2c4b78：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/770147_63PS5URY4VJVH7P.webp)

分别对两处进行反编译分析，0x3a662c 更像是tiktok定制的设置相关header处，关键代码反编译：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/770147_PMWVEN4RS8MGYK5.webp)

v128是从某个函数调用返回的结果，对该结果分割处理就得到了参数签名字段，因此用frida hook这里，然后输出调用时的两个参数查看
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/770147_6SMEFXZJQY9D3VQ.webp)

直接对0x3A658C地址进行HOOK，并打印出x0和x1寄存器的值，同时打印出X23寄存器的值：

| 1234567891011 | `var test` `=` `lib.base.add(``0x3A658C``);``Interceptor.attach(test, {``onEnter: function (args) {``console.log(args[``0``].readUtf8String());``console.log(args[``1``].readUtf8String());``console.log(``"X23："` `+` `this.context.x23);``},``onLeave: function (retval) {` `}``});` |
|-|-|

输出如下：

| 1234567891011121314151617181920212223242526272829303132 | `https:``/``/``pitaya``-``ttp2.us.tiktokv.com``/``api``/``v2``/``pitaya``/``distribute``cookie``passport_csrf_token``=``5766c07398074a324465468bd4bab579``; passport_csrf_token_default``=``5766c07398074a324465468bd4bab579``; d_ticket``=``474b6c31b9b433d344ad9368558503f7c0b97``; multi_sids``=``7158650562190427178``%``3A41a587d2b1bda3bdf9a41a6ad5e966dd``; cmpl_token``=``AgQQAPNSF``-``RPsLNmTGWesB0T_9hlCYxU_4dFYNGQWw; sid_guard``=``41a587d2b1bda3bdf9a41a6ad5e966dd``%``7C1706690864``%``7C5183999``%``7CSun``%``2C``+``31``-``Mar``-``2024``+``08``%``3A47``%``3A43``+``GMT; uid_tt``=``7ea855d54c1e8757b958a57c70ae4460747f060968a2b87122b64b9885ef693c``; uid_tt_ss``=``7ea855d54c1e8757b958a57c70ae4460747f060968a2b87122b64b9885ef693c``; sid_tt``=``41a587d2b1bda3bdf9a41a6ad5e966dd``; sessionid``=``41a587d2b1bda3bdf9a41a6ad5e966dd``; sessionid_ss``=``41a587d2b1bda3bdf9a41a6ad5e966dd``; store``-``idc``=``useast5; store``-``country``-``code``=``us; store``-``country``-``code``-``src``=``uid; tt``-``target``-``idc``=``useast5; tt``-``target``-``idc``-``sign``=``TTaFL_``-``1FbxEnf7WPS8zSLktQ9q_ifo6_mDz3Av0v8FRvfiClSjLH0kitsJa9NPbyFwN8SuqcgAf5RVQ_6pupKVUrkkLUROrihSkzo6xgNW``-``cni9Upf7Cb8L``-``lH6iXsKuLG9rjNatWULp7Q0ttS4Hru25ZA2_piENXsxaYc_89Z_ZgwyZhzLe4dXLBLDW4YtWrXAazxRLpNwkL_LQ8fnueZBRmZgJ0QNA3SyztUm9UnjDrqCZtTsTqrOS6zSxPoOfEL0UFxY12F5qPCgX84eh3_gifeiXxcmNkHZgPTNwSX0NOpTEw9kYLc9zOEWQ1IPMgXEgGZueXyYE``-``gHE7GfSrGZq41r_KC6qgb26LryHaXNg324JZbTPRBbz``-``AwRyHE0YeexTdtw260Yid1TDSUQx6jbHI7zDxMfCE9cJCPJye25D3Uj3hP7TsPt4bBkCt5jaHGdXvMIHeGDXSDfnhZy0HU64KS3Yh9sVNSA3nniaYgC4T2mekD3k4KvvmFIB74; install_id``=``7330181047176857374``; ttreq``=``1``$ef5245324d322906a97679c1d5607b943302a796; odin_tt``=``1aa7c920ceb63edc6557473a4e1787da2c6a470b275459df0bc31298c6923c6e66dc4673cf75b9373e546e2654bc598fda5ba22e95d91ceb33de9a5ebdeb90ff7c27f43f5e7825b5ba92ac9ea05f8932``; msToken``=``7DDzVQRIMB7ctDaC0N7hcu7PbQ4dQmHhHa9Ggd1``-``kGq0ZuDkSXR3cxNzjfie5mEcNUksJSMEhiniITA8vwhqdOkXXJgm5tbe6``-``3Cf_ZdS8hSWMQBslxhNYshHyweLw``=``=``x``-``vc``-``bdturing``-``sdk``-``version``2.3``.``5.i18n``x``-``bd``-``kmsv``0``x``-``tt``-``dm``-``status``login``=``1``;ct``=``1``;rt``=``1``x``-``ss``-``req``-``ticket``1707126766871``x``-``bd``-``client``-``key``#baXvVHqzV2VM8S1JcXbNUSdy2etUU3s95T2Yea6/0XO4pibZxVQ/PXaR09LfGTqLTlCPYtNGJ26+tkzb``pns_event_id``75``content``-``type``application``/``json; charset``=``utf``-``8``content``-``length``919``x``-``tt``-``store``-``region``us``x``-``tt``-``store``-``region``-``src``uid``x``-``ss``-``dp``1233``x``-``tt``-``trace``-``id``00``-``78af3eb21065b9fc3a23cbc6058a04d1``-``78af3eb21065b9fc``-``01``user``-``agent``com.zhiliaoapp.musically``/``2023302050` `(Linux; U; Android` `11``; en; Mi` `9T` `Pro; Build``/``RKQ1.``200826.002``; Cronet``/``TTNetVersion:``996128d2` `2024``-``01``-``12` `QuicVersion:ce58f68a` `2024``-``01``-``12``)``accept``-``encoding``gzip, deflate, br``X23：``0x790584aee0` |
|-|-|

参数1是https请求的url，参数2看起来是https请求的header, X23的地址位于 libmetasec_ov.so模块的0x88ee0处。这样基本可以确定0x88ee0 是获取签名的关键函数。

对该函数HOOK并打印参数和返回值：

| 12345678910111213141516171819202122232425262728293031 | `function waitForModule(moduleName) {``return` `new Promise(resolve` `=``> {``const interval` `=` `setInterval(()` `=``> {``const module` `=` `Process.findModuleByName(moduleName);``if` `(module !``=` `null) {``clearInterval(interval);``resolve(module);``}``},` `0``);``});``}`  `waitForModule(``"libmetasec_ov.so"``).then((lib)` `=``> {``logger(`[``*``][``+``] Found libsscronet at: ${lib.base}`)``hook_tt_get_sig(lib);``});`  `function hook_tt_get_sig(lib) {``var get_sig` `=` `lib.base.add(``0x88ee0``);``Interceptor.attach(get_sig, {``onEnter: function (args) {``console.log(``"arg0："` `+` `args[``0``].readUtf8String());``console.log(``"arg1："` `+` `args[``1``].readUtf8String());``},``onLeave: function (retval) {``console.log(``"retval: "` `+` `retval.readUtf8String());``}``});``}` |
|-|-|

| 1234567891011121314151617181920212223242526272829303132333435363738394041 | `arg0：https:``/``/``log16``-``normal``-``useast8.us.tiktokv.com``/``service``/``2``/``app_alert_check``/``?device_id``=``7330167195161052677``&aid``=``1233``&tt_info``=``dGMFEAAAcbZMj0j60zx0QZ36CmqwscC_mg_FI33giq8TCyxwgZ0k7cu5UKyTp1L9dV``-``LfNfW4lXh``%``0Ar0nUiGJiKZ3gDTrfQD3ReFJzPYPt0nAafGTrwTYpE``-``PyqOZoVMC5oDuJFBWuFqqya6HwUuGxN5yO``%``0AP49E6kSu1rM_1``-``xY36xXTYPC8gekr5bUXyHyfmxJnNIap0t8JqKQW72gWlmb7RGJWnEqALZSuTrS``%``0ATlIvTOFF4LzJrprGoRGAbUs0pqvYanBTbQfZ8c``-``8VUd8A1FOepNFvxnnbv6168SjPh9alAq0NGfz``%``0AgYkwcsVvqb5POQBKWMJskxct2mcizBAqpKVQsDteOKuuci_QYcniwyQ7B5AF``-``nQsWAhLmuJVb_ya``%``0A3a3Dt6701GKDFSB7ObdAdK7JU5xlLCeevWdvdXCWvtDURvMiB1lhnCTf2lF``-``-``_UEmTCx5TxkHDnK``%``0AJUYq36SEDO1I1K5dy9PDtJ4HhgpdraMbymScFDrVVZAdflINaUbBcXSGrbjyRrfGke4Zi0LivqZq``%``0A1cRpYWELr9AoDT48PziFXh6Bmj3CXGRJAa``-``d0XdNtyDvvik5PhCeqN8PTH1PwA6vv7VsqkpnLny0``%``0APtL34eTrw0ThDdJQGH3UTr9jVNixJZ4dMTLhu8MZJCaNpEgAoWhWOPErTN9O3YkOutVsDXiqgjIJ``%``0AG8lpRCK2LGWEIoZXa0qKBtzG0nvO52hs6XRFER6t6wSm1Ix2alR_SlxnzdMnqRxTdHkc_KU``-``QJ2d``%``0A_fThvP_9TseeU1T1T5miiLEOsrRqlYEmV_h48Zh``-``lPteWeMnGb``-``h4T4c_K6k8B6nWSUA3blq1M6J``%``0A7qW6dmcdhNpRfXP3WGsLa0D1XqUkPhhIS5Y6bd5N3yLxy_Q``%``3D``%``0A``&iid``=``7330181047176857374``&ac``=``wifi&channel``=``googleplay&app_name``=``musical_ly&version_code``=``330205``&version_name``=``33.2``.``5``&device_platform``=``android&os``=``android&ab_version``=``33.2``.``5``&ssmix``=``a&device_type``=``Mi``+``9T``+``Pro&device_brand``=``Xiaomi&language``=``en&os_api``=``30``&os_version``=``11``&openudid``=``3e2d515cedf5f2b2``&manifest_version_code``=``2023302050``&resolution``=``1080``*``1920``&dpi``=``480``&update_version_code``=``2023302050``&_rticket``=``1707127562679``&is_pad``=``0``&current_region``=``NZ&app_type``=``normal&sys_region``=``US&mcc_mnc``=``53028``&timezone_name``=``Pacific``%``2FAuckland``&residence``=``NZ&app_language``=``en&carrier_region``=``NZ&ac2``=``wifi5g&uoo``=``0``&op_region``=``NZ&timezone_offset``=``43200``&build_number``=``33.2``.``5``&host_abi``=``arm64``-``v8a&locale``=``en&region``=``US&ts``=``1707127561``&cdid``=``5c3ed0c6``-``8aaf``-``4018``-``9fb1``-``f7ada8bcea34&cronet_version``=``996128d2_2024``-``01``-``12``&ttnet_version``=``4.2``.``137.48``-``tiktok&use_store_region_cookie``=``1``arg1：cookie``passport_csrf_token``=``5766c07398074a324465468bd4bab579``; passport_csrf_token_default``=``5766c07398074a324465468bd4bab579``; d_ticket``=``474b6c31b9b433d344ad9368558503f7c0b97``; multi_sids``=``7158650562190427178``%``3A41a587d2b1bda3bdf9a41a6ad5e966dd``; cmpl_token``=``AgQQAPNSF``-``RPsLNmTGWesB0T_9hlCYxU_4dFYNGQWw; sid_guard``=``41a587d2b1bda3bdf9a41a6ad5e966dd``%``7C1706690864``%``7C5183999``%``7CSun``%``2C``+``31``-``Mar``-``2024``+``08``%``3A47``%``3A43``+``GMT; uid_tt``=``7ea855d54c1e8757b958a57c70ae4460747f060968a2b87122b64b9885ef693c``; uid_tt_ss``=``7ea855d54c1e8757b958a57c70ae4460747f060968a2b87122b64b9885ef693c``; sid_tt``=``41a587d2b1bda3bdf9a41a6ad5e966dd``; sessionid``=``41a587d2b1bda3bdf9a41a6ad5e966dd``; sessionid_ss``=``41a587d2b1bda3bdf9a41a6ad5e966dd``; store``-``idc``=``useast5; store``-``country``-``code``=``us; store``-``country``-``code``-``src``=``uid; tt``-``target``-``idc``=``useast5; tt``-``target``-``idc``-``sign``=``TTaFL_``-``1FbxEnf7WPS8zSLktQ9q_ifo6_mDz3Av0v8FRvfiClSjLH0kitsJa9NPbyFwN8SuqcgAf5RVQ_6pupKVUrkkLUROrihSkzo6xgNW``-``cni9Upf7Cb8L``-``lH6iXsKuLG9rjNatWULp7Q0ttS4Hru25ZA2_piENXsxaYc_89Z_ZgwyZhzLe4dXLBLDW4YtWrXAazxRLpNwkL_LQ8fnueZBRmZgJ0QNA3SyztUm9UnjDrqCZtTsTqrOS6zSxPoOfEL0UFxY12F5qPCgX84eh3_gifeiXxcmNkHZgPTNwSX0NOpTEw9kYLc9zOEWQ1IPMgXEgGZueXyYE``-``gHE7GfSrGZq41r_KC6qgb26LryHaXNg324JZbTPRBbz``-``AwRyHE0YeexTdtw260Yid1TDSUQx6jbHI7zDxMfCE9cJCPJye25D3Uj3hP7TsPt4bBkCt5jaHGdXvMIHeGDXSDfnhZy0HU64KS3Yh9sVNSA3nniaYgC4T2mekD3k4KvvmFIB74; install_id``=``7330181047176857374``; ttreq``=``1``$ef5245324d322906a97679c1d5607b943302a796; odin_tt``=``1aa7c920ceb63edc6557473a4e1787da2c6a470b275459df0bc31298c6923c6e66dc4673cf75b9373e546e2654bc598fda5ba22e95d91ceb33de9a5ebdeb90ff7c27f43f5e7825b5ba92ac9ea05f8932``; msToken``=``KaEq98vvNTLCC9vvMJwobggElABP3DvaLMgNf9zMFpurwzHDGdnJbn7NJ53sdDQ6iyM_yaDcpgAxLQevASt6DqNlXZ7NNzYuOFnU6EHixIwVOy6KOhAVe2XkyGq47g``=``=``x``-``tt``-``multi``-``sids``7158650562190427178``%``3A41a587d2b1bda3bdf9a41a6ad5e966dd``sdk``-``version``2``x``-``bd``-``kmsv``0``x``-``tt``-``dm``-``status``login``=``1``;ct``=``1``;rt``=``1``x``-``tt``-``token``0441a587d2b1bda3bdf9a41a6ad5e966dd041679e9cfeb96c72898bb183b8222bb1073d351793c1da7dca678b7cfc8c54af218b43f5dd2a4e0c8a71da5e1c2c8c45699afd524957260286c4b116e0df117c1c87de2a72c1faf791269c934718e8616e``-``1.0``.``1``x``-``ss``-``req``-``ticket``1707127562691``x``-``bd``-``client``-``key``#baXvVHqzV2VM8S1JcXbNUSdy2etUU3s95T2Yea6/0XO4pibZxVQ/PXaR09LfGTqLTlCPYtNGJ26+tkzb``multi_login``1``passport``-``sdk``-``version``19``pns_event_id``22``x``-``vc``-``bdturing``-``sdk``-``version``2.3``.``5.i18n``x``-``ss``-``dp``1233``x``-``tt``-``trace``-``id``00``-``78bb64b11065b9fc3a23cbc6055904d1``-``78bb64b11065b9fc``-``01``user``-``agent``com.zhiliaoapp.musically``/``2023302050` `(Linux; U; Android` `11``; en; Mi` `9T` `Pro; Build``/``RKQ1.``200826.002``; Cronet``/``TTNetVersion:``996128d2` `2024``-``01``-``12` `QuicVersion:ce58f68a` `2024``-``01``-``12``)``accept``-``encoding``gzip, deflate, br``retval: X``-``Argus``DXfY6mO6hlrcmaQgpgzBwrXD6AJCuKss3FonR0C``+``ub``/``vtTBhj92rDuroEsi57jh6qUM04M1lRoxdSx2brJ7D``+``fkvjPnDFGwEbHLhGu8oR7wrdOU1TNIbzQoI``+``UMmLg8ySyqHEiFWG8l3XWHXbaJDgsmCZv1Zry2v9g0ORukQvDUfhxKgdBwPFAeQf8MxZDE4AuGzTWJ5QxZcIQUlGgAynnKqvPrzQiauq8xcD99TyYrrZVNfdBS5RsVfZZWTeI7dLjxMoV``+``grZVc9Bp7FViXJ7G4zIzkSvpEWMjI``+``fzUN3EClwzg``+``rcrCQOUZ1tsiREzOGnLoAAX91uXBq``/``QQ9xGy4``/``+``9Vw7W5izejUj0lamUT0eoi5hLFDxKFtrqgRzRVd6ABu8Pc7hT0Bt``/``WKDpUKn7WTZB8S95kv9MnN3sEkfsX42s1lhAGlI``+``ZbC8J8d5xWaTKpkIItRm289PHZ9iiSqhz6q8fpwPBEAz3mrqJbrJsXP6Zub6iUZajGTNg9lc0urDbHJb3SvsOB3TsM4TMk83Kf1zTy9xcEL8ScQtWXMvdvi21lc1Mm3oAdFU``+``LXQ6zwekz4yzEMqaIfCqPTThehF``/``H0z9zlzz6CNCCJQTdDneTfiA``=``=``X``-``Gorgon``8404203b0000114869cdb5ab8afdb91780878d0dc9ec86447c3f``X``-``Khronos``1707127563``X``-``Ladon``3iXZQdDtf``+``Q2E``+``rNj0dWBJ``+``O3XXJVszo5g4df4lQV1NNdQBz` |
|-|-|

如上，确定无误，四个签名字段和值是一块返回，以行分割后分别设置在请求头中。

3、直接调用
废话不说了，直接上代码：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157 | `package com.zhiliaoapp.musically;` `import` `capstone.api.Instruction;``import` `com.github.unidbg.AndroidEmulator;``import` `com.github.unidbg.Emulator;``import` `com.github.unidbg.Module;``import` `com.github.unidbg.arm.backend.Unicorn2Factory;``import` `com.github.unidbg.``file``.FileResult;``import` `com.github.unidbg.``file``.IOResolver;``import` `com.github.unidbg.``file``.linux.AndroidFileIO;``import` `com.github.unidbg.hook.HookListener;``import` `com.github.unidbg.linux.android.AndroidEmulatorBuilder;``import` `com.github.unidbg.linux.android.AndroidResolver;``import` `com.github.unidbg.linux.android.dvm.``*``;``import` `com.github.unidbg.linux.android.dvm.jni.ProxyClassFactory;``import` `com.github.unidbg.linux.``file``.SimpleFileIO;``import` `com.github.unidbg.listener.TraceCodeListener;``import` `com.github.unidbg.memory.Memory;``import` `com.github.unidbg.memory.MemoryBlock;``import` `com.github.unidbg.memory.SvcMemory;``import` `com.github.unidbg.pointer.UnidbgPointer;``import` `sun.rmi.runtime.Log;` `import` `java.io.``File``;``import` `java.io.FileInputStream;``import` `java.io.IOException;` `public` `class` `MetaSec extends AbstractJni implements IOResolver<AndroidFileIO> {` `private final AndroidEmulator emulator;``private final VM vm;``private final Module module;` `public MetaSec() {` `emulator` `=` `AndroidEmulatorBuilder.for64Bit()``.setProcessName(``"com.zhiliaoapp.musically"``)``.addBackendFactory(new Unicorn2Factory(true))``.build();` `/``/` `创建模拟器实例，要模拟``32``位或者``64``位，在这里区分``final Memory memory` `=` `emulator.getMemory();` `/``/` `模拟器的内存操作接口``/``/``SvcMemory svcMemory` `=` `emulator.getSvcMemory();``memory.setLibraryResolver(new AndroidResolver(``23``));` `/``/` `设置系统类库解析` `vm` `=` `emulator.createDalvikVM();` `/``/` `创建Android虚拟机``vm.setVerbose(false);` `/``/` `设置是否打印Jni调用细节``vm.setJni(this);` `/``/``载入依赖so库``vm.loadLibrary(new` `File``(``"unidbg-android/src/test/resources/example_binaries/libPitayaObject.so"``), false);``vm.loadLibrary(new` `File``(``"unidbg-android/src/test/resources/example_binaries/libAndroidPitayaProxy.so"``), false);``vm.loadLibrary(new` `File``(``"unidbg-android/src/test/resources/example_binaries/libc++_shared.so"``), false);` `/``/``模块绑定的java层类``DvmClass k` `=` `vm.resolveClass(``"ms/bd/o/k"``);``DvmClass a0` `=` `vm.resolveClass(``"ms/bd/o/a0"``,k);``vm.resolveClass(``"com/bytedance/mobsec/metasec/ov/MS"``, a0);` `/``/``加载目标模块``DalvikModule dm` `=` `vm.loadLibrary(new` `File``(``"unidbg-android/src/test/resources/example_binaries/libmetasec_ov.so"``), false);``module` `=` `dm.getModule();` `/``/``emulator.traceCode(module.base, module.base` `+` `module.size);``dm.callJNI_OnLoad(emulator);` `/``/` `手动执行JNI_OnLoad函数` `/``/``读取测试参数``String url` `=` `readFile(``"unidbg-android/src/test/resources/test_url.txt"``);``MemoryBlock block` `=` `memory.malloc(url.length(),true);``UnidbgPointer url_ptr` `=` `block.getPointer();``url_ptr.write(url.getBytes());` `String header` `=` `readFile(``"unidbg-android/src/test/resources/test_header.txt"``);``System.out.println(header);``MemoryBlock block_header` `=` `memory.malloc(header.length(),true);``UnidbgPointer header_ptr` `=` `block_header.getPointer();``header_ptr.write(header.getBytes());` `/``/``emulator.traceCode(module.base, module.base` `+` `module.size);``/``/``调用目标签名函数``Number number` `=` `module.callFunction(emulator,``0x88ee0``,``url_ptr, header_ptr);` `/``/``输出返回值``UnidbgPointer result` `=` `memory.pointer(number.longValue());``System.out.println(result.getString(``0``));``}`  `public static void main(String[] args) throws Exception {``new MetaSec();``}` `@Override``public FileResult<AndroidFileIO> resolve(Emulator<AndroidFileIO> emulator, String pathname,` `int` `oflags) {``System.out.println(``"PATHNAME:"` `+` `pathname);``/``/`        `if` `(pathname.equals(``"/system/lib/libc.so"``)){``/``/`            `System.out.println(``"LIBSO"``);``/``/`            `File` `reg` `=` `new` `File``(``"unidbg-android\\src\\main\\resources\\android\\sdk23\\lib\\libc.so"``);``/``/`            `return` `FileResult.<AndroidFileIO>success(new SimpleFileIO(oflags,reg,pathname));``/``/`        `}``/``/`        `if` `(pathname.equals(``"/proc/self/exe"``)){``/``/`            `System.out.println(``"EXE"``);``/``/`            `return` `FileResult.<AndroidFileIO>success(new SimpleFileIO(oflags, new` `File``(``"E:\\Douyin\\unidbg-0.9.7\\unidbg-android\\src\\test\\resources\\dylib\\base.apk"``), pathname));``/``/`        `}``/``/`        `if` `(pathname.equals(``"/sys/devices/system/cpu/online"``)){``/``/`            `System.out.println(``"ONLINE"``);``/``/`            `return` `FileResult.<AndroidFileIO>success(new SimpleFileIO(oflags, new` `File``(``"E:\\Douyin\\unidbg-0.9.7\\unidbg-android\\src\\test\\resources\\dylib\\online"``), pathname));``/``/`        `}` `return` `null;``}` `@Override``public` `int` `getStaticIntField(BaseVM vm, DvmClass dvmClass, String signature) {``System.out.println(``"getStaticIntField: "` `+` `signature);``if` `(``"com/bytedance/mobsec/metasec/ov/MS->a()V"``.equals(signature)) {``return` `0x40``;``}``throw new UnsupportedOperationException(signature);``}``@Override``public void callVoidMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {``System.out.println(``"callVoidMethod: "` `+` `signature);``switch (signature) {``case` `"com/bytedance/mobsec/metasec/ov/MS->a()V"``:``System.out.println(``"> Patched: com/bytedance/mobsec/metasec/ov/MS->a()V"``);``return``;``}``super``.callVoidMethod(vm, dvmObject, signature, varArg);``}` `@Override``public DvmObject<?> callStaticObjectMethodV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {``System.out.println(signature);``switch (signature) {``case` `"com/bytedance/mobsec/metasec/ov/MS->b(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;"``:``return` `null;``}``throw new UnsupportedOperationException(signature);``}` `private String readFile(String fileName) {``String res``=``"";``try``{``FileInputStream fin` `=` `new FileInputStream(new` `File``(fileName));``int` `length` `=` `fin.available();``byte []` `buffer` `=` `new byte[length];``fin.read(``buffer``);``res` `=` `new String(``buffer``);``fin.close();``}``catch(Exception e){``e.printStackTrace();``}``return` `res;``}``}` |
|-|-|

测试通过
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/770147_727M6TBNFMNPSAK.webp)

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2025-2-18 18:05*

感谢分享

## 回复 by mb_yvuzbfvo (#3)

*2025-2-18 18:19*

感谢楼主

## 回复 by Ann945 (#4)

*2025-2-18 18:20*

感谢分享

## 回复 by thus_Dasein (#5)

*2025-2-18 18:21*

感谢楼主

## 回复 by wx_木毅 (#6)

*2025-2-18 18:21*

感谢分享

## 回复 by 一栋奥特曼 (#7)

*2025-2-18 18:21*

感谢分享

## 回复 by 拆拆拆 (#8)

*2025-2-18 18:23*

666

## 回复 by mb_aoooaosd (#9)

*2025-2-18 18:41*

牛逼

## 回复 by fenfei331 (#10)

*2025-2-18 19:41*

666

## 回复 by Ann945 (#11)

*2025-2-18 20:16*

无

## 回复 by 快乐的小跳蛙 (#12)

*2025-2-18 20:33*

膜拜大佬

## 回复 by 西瓜帅 (#13)

*2025-2-18 20:38*

111

## 回复 by method (#14)

*2025-2-18 20:42*

1

## 回复 by xiaofeicc (#15)

*2025-2-18 20:48*

1

## 回复 by 破绽百出 (#16)

*2025-2-18 22:13*

1

## 回复 by wx_Noob (#17)

*2025-2-18 22:15*

1

## 回复 by 逍遥无极天 (#18)

*2025-2-18 22:15*

牛逼

## 回复 by 墨穹呢 (#19)

*2025-2-18 22:18*

火钳刘明

## 回复 by mb_lltiaawa (#20)

*2025-2-18 22:18*

牛逼

## 回复 by Chenwen5 (#21)

*2025-2-18 22:22*

学习学习

## 回复 by 知一Tracer (#22)

*2025-2-18 22:27*

非常好

## 回复 by kingking888 (#23)

*2025-2-18 22:34*

666

## 回复 by Rocky虞 (#24)

*2025-2-18 22:36*

666

## 回复 by mb_vjpiriil (#25)

*2025-2-18 22:47*

666

## 回复 by mb_ehupwxyu (#26)

*2025-2-18 22:48*

111

## 回复 by 机车王子 (#27)

*2025-2-18 22:58*

感谢分享

## 回复 by 寄予蓝y (#28)

*2025-2-18 23:01*

666

## 回复 by 像风一样呢 (#29)

*2025-2-18 23:06*

6666666666666

## 回复 by kreedz (#30)

*2025-2-18 23:14*

666

## 回复 by 猫喵叫 (#31)

*2025-2-18 23:35*

666666

## 回复 by mb_yaeaedrh (#32)

*2025-2-18 23:45*

666

## 回复 by 星落黎明 (#33)

*2025-2-18 23:54*

感谢分享

## 回复 by mb_iesvmzqc (#34)

*2025-2-19 01:09*

666

## 回复 by Mysterious77 (#35)

*2025-2-19 02:20*

6666

## 回复 by 黑屏 (#36)

*2025-2-19 07:59*

666

## 回复 by ONewTach (#37)

*2025-2-19 09:07*

666

## 回复 by onwyc123 (#38)

*2025-2-19 09:07*

666

## 回复 by mb_patxjnad (#39)

*2025-2-19 09:10*

感谢分享

## 回复 by mb_spwfptaa (#40)

*2025-2-19 09:18*

66

## 回复 by wx_雷火丰 (#41)

*2025-2-19 09:38*

666

## 回复 by mb_pesxllvn (#42)

*2025-2-19 09:38*

666

## 回复 by 丶咖啡猫丶 (#43)

*2025-2-19 09:48*

666

## 回复 by 天道happy (#44)

*2025-2-19 10:17*

感谢分享

## 回复 by mb_uvyukvot (#45)

*2025-2-19 10:18*

666

## 回复 by lotus* (#46)

*2025-2-19 10:28*

666

## 回复 by memoriaru (#47)

*2025-2-19 10:32*

666

## 回复 by MaYil (#48)

*2025-2-19 10:47*

感谢分享

## 回复 by mb_qimctavn (#49)

*2025-2-19 13:01*

感谢分享

## 回复 by 混 (#50)

*2025-2-19 13:28*

666

## 回复 by mb_gbckotgc (#51)

*2025-2-19 14:00*

大佬6666

## 回复 by mb_wuevwbec (#52)

*2025-2-19 14:11*

大佬牛

## 回复 by M.C (#53)

*2025-2-19 14:18*

3333

## 回复 by xxzzxxzz (#54)

*2025-2-19 14:41*

666

## 回复 by 王杰克 (#55)

*2025-2-19 14:51*

牛皮

## 回复 by wx_Deity (#56)

*2025-2-19 14:53*

666

## 回复 by linkin5epk (#57)

*2025-2-19 15:24*

666

## 回复 by mb_ljekykpn (#58)

*2025-2-19 15:33*

666

## 回复 by CuteHacker (#59)

*2025-2-19 15:36*

666

## 回复 by Imxz (#60)

*2025-2-19 15:38*

666666666

## 回复 by 逆向小白鼠 (#61)

*2025-2-19 16:24*

666

## 回复 by 小秃秃驴 (#62)

*2025-2-19 16:50*

666

## 回复 by 孟达浪 (#63)

*2025-2-19 17:06*

666

## 回复 by 上官兮唐 (#64)

*2025-2-19 17:47*

看看

## 回复 by LyonzzZ (#65)

*2025-2-19 17:54*

6

## 回复 by wx_小柚子 (#66)

*2025-2-19 20:56*

666

## 回复 by mb_mjqtnsjb (#67)

*2025-2-19 22:13*

666

## 回复 by Zev@@ (#68)

*2025-2-20 01:14*

学习吗![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by bluegatar (#69)

*2025-2-20 01:39*

666

## 回复 by wx_最爱老大 (#70)

*2025-2-20 08:26*

6666

## 回复 by 酒月 (#71)

*2025-2-20 08:39*

6666

## 回复 by amwait (#72)

*2025-2-20 08:42*

666

## 回复 by 口艾口牙女马口牙 (#73)

*2025-2-20 09:30*

感谢分享

## 回复 by mb_cbgtaveo (#74)

*2025-2-20 09:37*

666

## 回复 by 皮皮虾啊 (#75)

*2025-2-20 10:33*

666

## 回复 by Necopy (#76)

*2025-2-20 10:56*

强强强

## 回复 by mb_jqlkhzmt (#77)

*2025-2-20 11:00*

6666

## 回复 by manmade (#78)

*2025-2-20 11:38*

666

## 回复 by mb_vhkidljs (#79)

*2025-2-20 11:46*

666

## 回复 by wx_0.0_522 (#80)

*2025-2-20 12:57*

nb

## 回复 by xeiyu (#81)

*2025-2-20 13:24*

666

## 回复 by 铭天星 (#82)

*2025-2-20 14:02*

![image](https://bbs.kanxue.com/view/img/face/060.gif)

## 回复 by 晨曦遇晓 (#83)

*2025-2-20 14:14*

666

## 回复 by Shangwendada (#84)

*2025-2-20 14:31*

666

## 回复 by xxjj678 (#85)

*2025-2-20 15:41*

666

## 回复 by mb_mzwrvupz (#86)

*2025-2-20 16:03*

666

## 回复 by 红颜小学生 (#87)

*2025-2-20 16:09*

666

## 回复 by Ddddz (#88)

*2025-2-20 17:02*

![image](https://bbs.kanxue.com/view/img/face/071.gif)

## 回复 by suexian (#89)

*2025-2-20 18:52*

![image](https://bbs.kanxue.com/view/img/face/079.gif)![image](https://bbs.kanxue.com/view/img/face/079.gif)![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by PPTV (#90)

*2025-2-20 19:42*

字节系是否通用

## 回复 by mb_xwntdpxy (#91)

*2025-2-20 20:31*

666

## 回复 by doduhuang (#92)

*2025-2-21 00:47*

666

## 回复 by mb_ioszxyua (#93)

*2025-2-21 00:57*

Good

## 回复 by mb_ykavguun (#94)

*2025-2-21 07:59*

111

## 回复 by mb_ifqtwleh (#95)

*2025-2-21 10:42*

看一看

## 回复 by 逆天而行 (#96)

*2025-2-21 23:36*

强的

## 回复 by 错了而已~ (#97)

*2025-2-22 08:41*

6666666666666

## 回复 by 洪荒老道 (#98)

*2025-2-22 10:59*

666

## 回复 by cnhuaWu (#99)

*2025-2-22 15:55*

kankan

## 回复 by 星煞小帕菜 (#100)

*2025-2-22 17:54*

666

## 回复 by 看snowadfad (#101)

*2025-2-22 18:10*

666

## 回复 by 蜡笔晓辉 (#102)

*2025-2-22 18:11*

厉害了

## 回复 by 我不是大神丿 (#103)

*2025-2-23 10:11*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_rsxcfqlj (#104)

*2025-2-23 10:57*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by guijingwen (#105)

*2025-2-23 11:19*

666

## 回复 by mb_tmbvnlxt (#106)

*2025-2-23 15:50*

666

## 回复 by git_93060laohu898 (#107)

*2025-2-23 17:12*

1

## 回复 by myios (#108)

*2025-2-24 00:40*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by 五彩斑斓的黑 (#109)

*2025-2-24 09:04*

膜拜大佬

## 回复 by mb_kxvziwtt (#110)

*2025-2-24 09:30*

666

## 回复 by 郁磊 (#111)

*2025-2-24 13:17*

666666

## 回复 by 一个瓜瓜 (#112)

*2025-2-24 17:12*

![image](https://bbs.kanxue.com/view/img/face/079.gif)666

## 回复 by bisoso (#113)

*2025-2-25 05:29*

不错！学习一下

## 回复 by 嘎嘎真的很棒 (#114)

*2025-2-25 09:38*

66666

## 回复 by ben_ (#115)

*2025-2-25 10:07*

感谢分享

## 回复 by 天水姜伯约 (#116)

*2025-2-25 11:14*

这样生成的签名过不了风控校验吧，签名里面肯定有环境标志的字段，小规模请求可以，大规模请求会被风控策略封掉吧

## 回复 by CCTV果冻爽 (#117)

*2025-2-25 12:03*

>
> [天水姜伯约](https://bbs.kanxue.com/user-783210.htm)
>
>  这样生成的签名过不了风控校验吧，签名里面肯定有环境标志的字段，小规模请求可以，大规模请求会被风控策略封掉吧
>
>

这个还需要完善，还需要通过 native 层接口传递一些参数，比如签名用的key、版本信息、设备 id等。签名里还保存了签名接口调用的次数。如果是要跟真机的签名一样，还要做的很多

## 回复 by git_94998davethebeast (#118)

*2025-2-25 16:10*

thanks

## 回复 by icedheart (#119)

*2025-2-25 16:24*

666

## 回复 by git_94998davethebeast (#120)

*2025-2-25 16:30*

Do you offer android reverse engineering tutorial?

## 回复 by 光头才能变强 (#121)

*2025-2-25 17:17*

666

## 回复 by wx_6677758 (#122)

*2025-2-25 17:43*

6666

## 回复 by xifgg (#123)

*2025-2-25 17:52*

666

## 回复 by ldljlzw (#124)

*2025-2-25 19:45*

888

## 回复 by 黄石 (#125)

*2025-2-26 11:19*

666

## 回复 by pianpu (#126)

*2025-2-26 11:28*

学习一下

## 回复 by wx_H_535 (#127)

*2025-2-26 12:30*

666

## 回复 by 李成功 (#128)

*2025-2-26 16:17*

132

## 回复 by mb_homnvxow (#129)

*2025-2-26 16:20*

666

## 回复 by log2 (#130)

*2025-2-27 20:15*

666

## 回复 by mb_znafresj (#131)

*2025-2-28 10:29*

666

## 回复 by 大魔头 (#132)

*2025-2-28 10:46*

6666

## 回复 by 钱钱钱￥ (#133)

*2025-2-28 15:03*

厉害

## 回复 by CryingLee (#134)

*2025-2-28 17:37*

66666666666

## 回复 by mb_lgbrcvmf (#135)

*2025-3-2 17:09*

厉害大佬

## 回复 by woainihehe (#136)

*2025-3-2 18:06*

tql 666

## 回复 by ovo_帮我不c (#137)

*2025-3-2 18:57*

66

## 回复 by robey (#138)

*2025-3-2 19:51*

666

## 回复 by 云水泱泱 (#139)

*2025-3-3 10:36*

学习

## 回复 by Gryffindoss (#140)

*2025-3-3 10:47*

12111111

## 回复 by 暴强 (#141)

*2025-3-3 20:44*

好东西，学习下。

## 回复 by doraemonliu (#142)

*2025-3-4 10:05*

66666

## 回复 by mb_dcjxxhsk (#143)

*2025-3-4 19:42*

66666

## 回复 by uni7corn (#144)

*2025-3-5 10:00*

66666

## 回复 by 夫人十八岁 (#145)

*2025-3-5 10:05*

1111111111111111

## 回复 by mb_3yQjKCRx (#146)

*2025-3-5 10:47*

666

## 回复 by 华达州 (#147)

*2025-3-5 11:08*

666

## 回复 by st0ne31 (#148)

*2025-3-5 11:10*

666

## 回复 by sry4leave (#149)

*2025-3-5 17:12*

666

## 回复 by 51974055 (#150)

*2025-3-5 19:04*

666

## 回复 by 3eacon (#151)

*2025-3-6 15:46*

1

## 回复 by Just_Cracker (#152)

*2025-3-6 15:49*

666

## 回复 by lrzhao (#153)

*2025-3-7 16:35*

6666

## 回复 by mb_kbkqyusp (#154)

*2025-3-7 17:28*

6666666666

## 回复 by mb_miylylso (#155)

*2025-3-7 17:32*

牛逼

## 回复 by HappyKL (#156)

*2025-3-7 18:08*

666

## 回复 by 正常先生 (#157)

*2025-3-7 20:19*

1

## 回复 by GEKEZYX (#158)

*2025-3-8 19:21*

666

## 回复 by 走码观花 (#159)

*2025-3-8 21:03*

6

## 回复 by mb_dhaylnrk (#160)

*2025-3-10 13:52*

666

## 回复 by 窜天猴 (#161)

*2025-3-10 15:09*

666

## 回复 by 冰敷 (#162)

*2025-3-10 18:07*

![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by 绿豆粥 (#163)

*2025-3-10 20:57*

666

## 回复 by LeeLinux (#164)

*2025-3-11 10:19*

666

## 回复 by foxyier (#165)

*2025-3-11 10:21*

666

## 回复 by liyqxtu (#166)

*2025-3-11 10:29*

666

## 回复 by mb_wiuwknnh (#167)

*2025-3-11 10:58*

66

## 回复 by 3bbdyg (#168)

*2025-3-11 11:10*

感谢分享

## 回复 by mb_zmjeaykk (#169)

*2025-3-11 11:45*

牛逼！

## 回复 by WLonTG (#170)

*2025-3-11 11:48*

膜拜大佬

## 回复 by liuzijue (#171)

*2025-3-11 12:07*

666

## 回复 by tasyoung (#172)

*2025-3-11 12:16*

学习学习

## 回复 by ou-taku (#173)

*2025-3-11 12:47*

666

## 回复 by dextoart (#174)

*2025-3-11 13:14*

666

## 回复 by mb_osxdmntv (#175)

*2025-3-12 00:01*

666

## 回复 by 白毅 (#176)

*2025-3-12 01:55*

包现在怎么抓 可以开个帖子吗 大佬

## 回复 by mb_aprbabml (#177)

*2025-3-12 07:49*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by loudy (#178)

*2025-3-12 08:54*

6666

## 回复 by mb_sjnafgkp (#179)

*2025-3-12 09:08*

666

## 回复 by wx_拖拖 (#180)

*2025-3-12 09:46*

感谢分享

## 回复 by mb_uvprvset (#181)

*2025-3-12 15:49*

666

## 回复 by 9527vv7 (#182)

*2025-3-12 16:53*

66

## 回复 by wx527 (#183)

*2025-3-12 17:37*

66666

## 回复 by Cillo (#184)

*2025-3-12 19:01*

查看全文需要回复

## 回复 by 胖虎1103 (#185)

*2025-3-13 04:14*

6

## 回复 by tyeying (#186)

*2025-3-13 06:25*

666

## 回复 by mb_zpyvrtaq (#187)

*2025-3-13 08:30*

666

## 回复 by gaohaosk (#188)

*2025-3-13 10:51*

666

## 回复 by 藏锋守拙 (#189)

*2025-3-13 17:34*

666

## 回复 by mb_phovhqpu (#190)

*2025-3-13 23:40*

666

## 回复 by huluxia (#191)

*2025-3-14 05:07*

牛逼

## 回复 by fwww (#192)

*2025-3-14 07:53*

666

## 回复 by wumawork (#193)

*2025-3-14 10:00*

666

## 回复 by ogli324 (#194)

*2025-3-14 10:06*

666

## 回复 by wx_星图 (#195)

*2025-3-14 18:50*

666

## 回复 by 赛宾 (#196)

*2025-3-17 00:42*

666

## 回复 by wx_playmaker (#197)

*2025-3-17 09:03*

666

## 回复 by 带带弟弟吧 (#198)

*2025-3-18 12:27*

1111

## 回复 by 龙幽 (#199)

*2025-3-18 17:17*

666

## 回复 by wx_归期_856 (#200)

*2025-3-18 18:21*

1111

## 回复 by Sadmin (#201)

*2025-3-19 06:29*

火钳刘明

## 回复 by tjytjy (#202)

*2025-3-19 08:57*

666

## 回复 by 龟仙人 (#203)

*2025-3-19 16:58*

666

## 回复 by 呼吸24K纯氧 (#204)

*2025-3-19 17:35*

看看

## 回复 by 荷蒉丈人 (#205)

*2025-3-20 11:28*

666

## 回复 by git_82811c517021 (#206)

*2025-3-20 11:57*

666

## 回复 by wx-小萌新 (#207)

*2025-3-20 17:15*

666

## 回复 by Nickname知寒 (#208)

*2025-3-21 11:26*

起飞

## 回复 by luckbbs (#209)

*2025-3-22 09:51*

1

## 回复 by hacker521 (#210)

*2025-3-22 17:18*

楼主NB

## 回复 by mb_bhmtpskk (#211)

*2025-3-23 21:33*

666

## 回复 by wx_L_611 (#212)

*2025-3-25 09:49*

666

## 回复 by 小智_spider (#213)

*2025-3-25 10:42*

666

## 回复 by kx_小龙人 (#214)

*2025-3-25 13:44*

学习

## 回复 by zhczf (#215)

*2025-3-25 21:13*

unidbg直接调用tiktok so生成签名

## 回复 by ztxbeyond (#216)

*2025-3-26 18:01*

学习一下

## 回复 by mb_4nrpVMxJ (#217)

*2025-3-26 20:24*

看看

## 回复 by 墨点 (#218)

*2025-3-27 06:08*

666

## 回复 by mb_lfvhycml (#219)

*2025-3-27 11:04*

666

## 回复 by snowflake911 (#220)

*2025-3-27 14:23*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by xiaotuo (#221)

*2025-3-27 17:58*

666

## 回复 by mb_xeodfvew (#222)

*2025-3-27 18:59*

111

## 回复 by iao (#223)

*2025-3-27 20:22*

666

## 回复 by 百事可乐就好 (#224)

*2025-3-27 23:37*

666

## 回复 by ljsongljsong (#225)

*2025-3-31 12:17*

666

## 回复 by hy6ran (#226)

*2025-4-3 18:13*

学习学习

## 回复 by 梦馗色撩i (#227)

*2025-4-4 00:55*

666

## 回复 by 海带 (#228)

*2025-4-6 14:04*

6666

## 回复 by mb_yubqcabm (#229)

*2025-4-6 15:58*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by wx_不愿入赘老板郎 (#230)

*2025-4-7 11:24*

1

## 回复 by lizhenzhe (#231)

*2025-4-7 16:53*

1

## 回复 by console_ (#232)

*2025-4-8 08:31*

666

## 回复 by zhujian (#233)

*2025-4-8 10:02*

666

## 回复 by mb_mnqgzwiu (#234)

*2025-4-8 11:09*

66666666666666

## 回复 by mb_mnqgzwiu (#236)

*2025-4-8 12:13*

X23的地址位于 libmetasec_ov.so模块的0x88ee0处    ，0x3A658C这个地址是setHeader 方法地址    请问这个地址0x88ee0是怎么得到的

## 回复 by CCTV果冻爽 (#237)

*2025-4-8 12:32*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_mnqgzwiu](https://bbs.kanxue.com/user-888308.htm)
>
>  X23的地址位于 libmetasec_ov.so模块的0x88ee0处 ，0x3A658C这个地址是setHeader 方法地址 请问这个地址0x88ee0是怎么得到的
>
>

判断地址在哪个模块的地址范围内，或者 frida 有接口 DebugSymbol.fromAddress ，输出符号

## 回复 by CCTV果冻爽 (#238)

*2025-4-8 12:33*

搬砖没时间做项目

## 回复 by CCTV果冻爽 (#239)

*2025-4-8 12:33*

>
> [青春小时代](https://bbs.kanxue.com/user-914582.htm)
>
>  联系方式多少，找您做项目
>
>

搬砖没时间做项目

## 回复 by LuciferArmy (#240)

*2025-4-8 14:23*

学

## 回复 by 带壳的蜗牛 (#241)

*2025-4-8 15:17*

厉害 厉害

## 回复 by mb_fbqaobdh (#242)

*2025-4-8 16:29*

666

## 回复 by mb_cxmjsgrw (#243)

*2025-4-9 10:11*

666

## 回复 by mb_cbgtaveo (#244)

*2025-4-9 11:39*

66666

## 回复 by dreameriii (#245)

*2025-4-9 11:52*

66666

## 回复 by 小太子奶 (#246)

*2025-4-11 09:48*

6666

## 回复 by 小太子奶 (#247)

*2025-4-11 09:49*

6666

## 回复 by Freax (#248)

*2025-4-11 11:01*

666

## 回复 by git_38729Hellmessage (#249)

*2025-4-14 04:02*

666

## 回复 by 江月闲潭 (#250)

*2025-4-14 15:41*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by mb_vxsnzesk (#251)

*2025-4-15 14:12*

支持

## 回复 by mb_ybvqgbkl (#252)

*2025-4-16 08:15*

牛逼666

## 回复 by fujing (#253)

*2025-4-16 08:41*

为你点赞！

## 回复 by mb_euphpkii (#254)

*2025-4-18 14:31*

1

## 回复 by mb_weyfdhks (#255)

*2025-4-19 13:15*

厉害666

## 回复 by pingsky (#256)

*2025-4-20 10:49*

6

## 回复 by 假装在纽约啊 (#257)

*2025-4-20 11:59*

66

## 回复 by r8e8cd8 (#258)

*2025-4-20 14:02*

学到了

## 回复 by mb_guhauaix (#259)

*2025-4-21 12:23*

6666

## 回复 by 唱过阡陌 (#260)

*2025-4-21 13:55*

666

## 回复 by mb_mduuylza (#261)

*2025-4-21 14:19*

1

## 回复 by mb_ggnlrzcs (#262)

*2025-4-21 14:58*

66666

## 回复 by 风远丶扬 (#263)

*2025-4-21 17:28*

666

## 回复 by A冷忆 (#264)

*2025-4-21 20:02*

666

## 回复 by mb_bpqjsuuu (#265)

*2025-4-22 14:08*

666666

## 回复 by mb_cxmjsgrw (#266)

*2025-4-22 21:24*

666

## 回复 by wx_亦水难当 (#267)

*2025-4-23 13:20*

666

## 回复 by shuyangzjg (#268)

*2025-4-23 13:56*

学习下

## 回复 by fangliangz (#269)

*2025-4-23 14:08*

666

## 回复 by Vengeance (#270)

*2025-4-23 23:37*

666

## 回复 by 利叶增辉 (#271)

*2025-4-25 18:23*

感谢分享，前来学习

## 回复 by flice (#272)

*2025-4-25 23:45*

666

## 回复 by mb_blekbmgh (#273)

*2025-4-25 23:48*

感谢楼主

## 回复 by guijian (#274)

*2025-4-26 16:35*

6

## 回复 by 杨某人 (#275)

*2025-4-26 17:38*

厉害了

## 回复 by mb_hqlyrcyl (#276)

*2025-4-27 14:33*

谢谢分享

## 回复 by 5p4d37 (#277)

*2025-4-28 02:09*

学习一哈

## 回复 by 夜的静night (#278)

*2025-4-28 06:57*

感谢分享。。

## 回复 by zzw_xjx (#279)

*2025-4-29 18:56*

666

## 回复 by 季东 (#280)

*2025-4-29 21:12*

666

## 回复 by mb_hkqnanbs (#281)

*2025-4-30 15:01*

学习了

## 回复 by mb_ggxkozau (#282)

*2025-5-6 15:59*

666

## 回复 by mb_plggxgxz (#283)

*2025-5-6 16:40*

666

## 回复 by Thehepta (#284)

*2025-5-8 14:31*

666

## 回复 by SFQin (#285)

*2025-5-9 09:30*

666

## 回复 by adnin (#286)

*2025-5-9 09:33*

优秀额

## 回复 by SleepAlone (#287)

*2025-5-9 10:42*

学习

## 回复 by xuannaixi (#288)

*2025-5-9 10:49*

666

## 回复 by 上善若水No (#289)

*2025-5-9 11:39*

1

## 回复 by zhengyuqin (#290)

*2025-5-9 21:19*

666

## 回复 by Bonnie-Ran (#291)

*2025-5-13 00:03*

感谢大佬，学习一下嘞~

## 回复 by mb_vgsbqhdw (#292)

*2025-5-13 08:49*

学一下

## 回复 by 烬奇小云 (#293)

*2025-5-13 15:27*

666

## 回复 by frankpi (#294)

*2025-5-13 19:05*

636

## 回复 by edisonhu (#295)

*2025-5-14 02:34*

5+1

## 回复 by mb_xekgkzxw (#296)

*2025-5-15 14:38*

666

## 回复 by foryaoyaoho (#297)

*2025-5-16 11:12*

太厉害了

## 回复 by 祝枝山 (#298)

*2025-5-16 13:49*

666

## 回复 by 街道办事处 (#299)

*2025-5-17 08:30*

url单行 header多行格式吧，为啥无法得到输出结果呢null，前面一步一步跟着都没问题 — —

## 回复 by mb_qsmzglfy (#300)

*2025-5-23 12:19*

666

## 回复 by 禾夕夕 (#301)

*2025-5-24 16:44*

666

## 回复 by edisonwei (#302)

*2025-5-26 14:09*

厉害

## 回复 by mb_uwlfzzlj (#303)

*2025-5-26 17:42*

666

## 回复 by git_27041irregularlion (#304)

*2025-5-27 06:05*

goood :)

## 回复 by mb_szxvbgvd (#305)

*2025-6-1 16:38*

666

## 回复 by Harden13 (#306)

*2025-6-1 20:20*

????????

## 回复 by 浮事青云 (#307)

*2025-6-9 13:22*

666

## 回复 by j01y (#308)

*2025-6-10 12:01*

666

## 回复 by ^Stranger (#309)

*2025-6-13 16:21*

666

## 回复 by 王多余 (#310)

*2025-6-13 17:22*

膜拜大老！

## 回复 by mb_jhohnbzu (#311)

*2025-6-13 17:26*

666

## 回复 by mb_euphpkii (#312)

*2025-6-17 22:48*

这个算法是不是无效了，怎么发请求
接口原始返回内容： ''
接口返回状态码： 200
simplejson.errors.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

## 回复 by mb_vhwdzyqo (#313)

*2025-6-18 00:32*

1

## 回复 by eastXueLian (#314)

*2025-6-18 11:46*

666

## 回复 by blank、 (#315)

*2025-6-18 16:41*

请问大佬是如何准确抓到tiktok的包呢，
我Charles+socksdroid，
tiktok会出现没网的情况，
而且抓到的信息基本都是Unknow

## 回复 by CCTV果冻爽 (#316)

*2025-6-18 17:11*

>
> [blank、](https://bbs.kanxue.com/user-970706.htm)
>
>  请问大佬是如何准确抓到tiktok的包呢，
> 我Charles+socksdroid，
> tiktok会出现没网的情况，
> 而且抓到的信息基本都是Unknow
>
>

过掉 ssl pinning -> SSL_CTX_set_custom_verify

## 回复 by git_56701jackt88 (#317)

*2025-6-19 00:38*

6666

## 回复 by wx_Huber Barrientos (#318)

*2025-6-19 03:34*

感谢楼主

## 回复 by 篮猫不睁眼 (#319)

*2025-6-19 03:38*

6666

## 回复 by wx_宇克鴻 (#320)

*2025-6-19 10:08*

666

## 回复 by fkueihcy (#321)

*2025-6-19 11:47*

666

## 回复 by spdfdfer (#322)

*2025-6-20 11:22*

感谢分享

## 回复 by mb_mhontfmf (#323)

*2025-6-20 11:54*

6666

## 回复 by JWPL (#324)

*2025-6-20 13:29*

666

## 回复 by Dem0li (#325)

*2025-6-20 17:22*

6

## 回复 by zhusg (#326)

*2025-6-21 15:59*

学习一下大佬

## 回复 by wx_justght (#327)

*2025-6-22 00:42*

tql

## 回复 by mb_jmkwanzm (#328)

*2025-6-22 11:24*

666

## 回复 by mJqalJqN (#329)

*2025-6-22 11:24*

1

## 回复 by mb_fywsujzf (#330)

*2025-6-22 14:12*

哈哈哈哈

## 回复 by 三草儿 (#331)

*2025-6-26 02:08*

999

## 回复 by chinameme (#332)

*2025-6-26 09:48*

666

## 回复 by mb_gcthrymv (#333)

*2025-6-28 02:23*

666

## 回复 by xiayutian_ (#334)

*2025-6-28 18:48*

1

## 回复 by erichyx (#335)

*2025-6-28 22:20*

啥？

## 回复 by 等天黑 (#336)

*2025-7-3 09:57*

666

## 回复 by wx_printf (#337)

*2025-7-3 11:17*

观摩 观摩

## 回复 by Joobih (#338)

*2025-7-3 17:16*

666

## 回复 by 逆道而行 (#339)

*2025-7-3 18:11*

666

## 回复 by eyascn (#340)

*2025-7-4 09:33*

这是一个新思路

## 回复 by wx_阳_920 (#341)

*2025-7-4 10:22*

666

## 回复 by 不可思议BK (#342)

*2025-7-4 10:30*

666

## 回复 by 9494 (#343)

*2025-7-4 15:58*

666

## 回复 by y小白001 (#344)

*2025-7-4 16:17*

666

## 回复 by litianp (#345)

*2025-7-4 23:40*

感谢分享

## 回复 by mb_frspcrqz (#346)

*2025-7-6 04:15*

666

## 回复 by mb_yxcltfyb (#347)

*2025-7-7 03:33*

太强啦

## 回复 by mb_rjoxthlj (#348)

*2025-7-7 16:40*

6666

## 回复 by mb_udhcrwur (#349)

*2025-7-10 16:03*

666

## 回复 by mb_ygrvwqld (#350)

*2025-7-10 17:41*

666

## 回复 by robinhust (#351)

*2025-7-15 01:31*

你好，怎样才能制作出和真机一样的 Argus？目前有些界面无法再使用这个签名了。

## 回复 by CCTV果冻爽 (#352)

*2025-7-15 10:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  robinhust](https://bbs.kanxue.com/user-1022004.htm)
>
>  你好，怎样才能制作出和真机一样的 Argus？目前有些界面无法再使用这个签名了。
>
>
>

应该是部分协议还校验了 seed，直接调用没有触达 get_seed协议

## 回复 by mb_clkpejqc (#353)

*2025-7-15 23:46*

![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by mb_bqozkfsa (#354)

*2025-7-16 17:20*

看看666

## 回复 by mb_kfexwtvm (#355)

*2025-7-17 15:49*

666

## 回复 by mb_ynpgeaep (#356)

*2025-7-18 17:30*

666

## 回复 by maxcl (#357)

*2025-7-18 17:42*

6666

## 回复 by shawn996 (#358)

*2025-7-24 06:09*

666

## 回复 by lr04d (#359)

*2025-7-24 11:52*

666

## 回复 by git_86651mytich77 (#360)

*2025-7-25 11:58*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_snaaronp (#361)

*2025-7-25 11:59*

66666

## 回复 by wx_插曲 (#362)

*2025-7-25 15:53*

1

## 回复 by mb_xpqfmesy (#363)

*2025-7-25 17:52*

666

## 回复 by 温泉划水鱼 (#364)

*2025-7-26 00:52*

x

## 回复 by git_86651mytich77 (#365)

*2025-7-26 06:25*

你能把你的电报用户名发给我吗，我需要你的帮助

## 回复 by αβγδεξπ (#366)

*2025-7-26 08:38*

tql

## 回复 by mb_gnehsaia (#367)

*2025-7-29 09:57*

6

## 回复 by 29o (#368)

*2025-7-30 19:07*

3213123

## 回复 by AndroidDev (#369)

*2025-7-31 21:25*

6666

## 回复 by mb_fkfxzewm (#370)

*2025-8-1 16:02*

6

## 回复 by yaoye555 (#371)

*2025-8-1 17:19*

666

## 回复 by 菜菜Zn (#372)

*2025-8-1 17:31*

666

## 回复 by 4Chan (#373)

*2025-8-1 18:50*

666

## 回复 by 阳光宝贝 (#374)

*2025-8-2 14:05*

感谢楼主分享

## 回复 by kx_211103 (#375)

*2025-8-3 12:38*

666

## 回复 by jyotidwi (#376)

*2025-8-3 14:31*

感谢分享

## 回复 by Zireael (#377)

*2025-8-3 22:56*

学习

## 回复 by Freax (#378)

*2025-8-5 17:06*

最新版的unidbg跑不了吗？直接返回null也不报错

## 回复 by mb_tkqmdluq (#379)

*2025-8-7 17:02*

6666666666

## 回复 by darknight007 (#380)

*2025-8-7 17:14*

6666

## 回复 by wushuang双 (#381)

*2025-8-10 15:22*

学习学习

## 回复 by aq88 (#382)

*2025-8-10 18:16*

威武

## 回复 by git_98579rabbits0209 (#383)

*2025-8-11 21:40*

感谢

## 回复 by mb_hwpgtlcs (#384)

*2025-8-13 19:21*

666

## 回复 by 橘子皮儿 (#385)

*2025-8-15 19:57*

6666

## 回复 by Heiyiren123 (#386)

*2025-8-16 05:57*

学习一下

## 回复 by wx_丁丁丁 (#387)

*2025-8-17 13:43*

666

## 回复 by karma_2060 (#388)

*2025-8-18 14:52*

6666

## 回复 by jjjo (#389)

*2025-8-20 13:28*

6666

## 回复 by 乐活 (#390)

*2025-8-21 15:18*

66

## 回复 by mb_ifjlatem (#391)

*2025-8-21 22:46*

666

## 回复 by mb_uokrnlrg (#392)

*2025-8-22 16:46*

学习中

## 回复 by mb_hazlqgpq (#393)

*2025-8-23 20:08*

666

## 回复 by 温泉划水鱼 (#394)

*2025-8-24 05:01*

nice

## 回复 by wx_DJT (#395)

*2025-8-24 15:48*

666

## 回复 by mb_eawdyigy (#396)

*2025-8-25 22:30*

666

## 回复 by wx_汪洋大海 (#397)

*2025-8-26 15:36*

666

## 回复 by mb_xcdrmleb (#398)

*2025-8-26 17:34*

6666

## 回复 by git_79771lunchaohe (#399)

*2025-8-26 23:57*

666

## 回复 by 瞎搞就成了 (#400)

*2025-8-27 20:45*

性能怎么样

## 回复 by mb_okgzjrgl (#401)

*2025-8-28 16:43*

6666

## 回复 by Akira_ (#402)

*2025-8-29 17:48*

666

## 回复 by git_41454 (#403)

*2025-8-29 19:45*

666

## 回复 by mb_bdsectgg (#404)

*2025-8-29 22:53*

牛逼

## 回复 by huangjw (#405)

*2025-9-1 20:46*

感觉分析niubplus

## 回复 by mb_npylpnpl (#406)

*2025-9-2 16:00*

1

## 回复 by mb_cqcrdwgm (#407)

*2025-9-2 22:04*

666

## 回复 by 威兹曼 (#408)

*2025-9-2 22:23*

感谢分享

## 回复 by cobe (#409)

*2025-9-5 10:18*

666

## 回复 by Zkeleven (#410)

*2025-9-5 10:39*

666

## 回复 by 酋knave (#411)

*2025-9-8 13:56*

666

## 回复 by 云沐 (#412)

*2025-9-8 21:37*

6666

## 回复 by mb_hdgliaem (#413)

*2025-9-9 10:48*

666

## 回复 by zz1syyd (#414)

*2025-9-9 14:05*

666

## 回复 by git_99761marktristy (#415)

*2025-9-10 07:23*

com.github.unidbg.arm.backend.BackendException: mem_read address=0x8, size=4

## 回复 by mb_kumzialx (#416)

*2025-9-12 13:52*

666

## 回复 by mb_chyxytio (#417)

*2025-9-12 14:43*

大佬厉害

## 回复 by 流星沦落 (#418)

*2025-9-12 23:08*

666

## 回复 by mb_ipadxgzl (#419)

*2025-9-14 19:36*

6666

## 回复 by 奋斗的小趴菜 (#420)

*2025-9-15 14:36*

1

## 回复 by mb_fidispot (#421)

*2025-9-17 05:31*

666

## 回复 by wx_郑泽科 (#422)

*2025-9-17 11:19*

666

## 回复 by mb_ldjgenan (#423)

*2025-9-17 12:02*

66

## 回复 by 公众号坚毅猿 (#424)

*2025-9-19 10:42*

感谢分享

## 回复 by ocenamza (#425)

*2025-9-19 13:12*

thankies

## 回复 by ocenamza (#426)

*2025-9-19 13:46*

thankies

## 回复 by mb_yvpmmruh (#427)

*2025-9-19 16:26*

666

## 回复 by mb_ifahjmee (#428)

*2025-9-23 11:37*

![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by axpol (#429)

*2025-9-23 13:52*

666

## 回复 by mb_ajqftfbv (#430)

*2025-9-23 14:52*

666

## 回复 by capser (#431)

*2025-9-24 15:30*

来搬砖，楼主辛苦了![image](https://bbs.kanxue.com/view/img/face/092.gif)

## 回复 by mb_yxcltfyb (#432)

*2025-9-24 22:03*

厉害了

## 回复 by wx_一颗红心向党旗 (#433)

*2025-9-25 14:33*

6

## 回复 by 我心向山 (#434)

*2025-9-25 15:01*

666

## 回复 by Da_ (#435)

*2025-9-25 16:39*

666

## 回复 by dawnsky1111 (#436)

*2025-9-25 22:04*

66

## 回复 by manyuegong33 (#437)

*2025-9-26 09:32*

1

## 回复 by mb_kumzialx (#438)

*2025-9-27 15:44*

这是tiktok 哪个版本啊

## 回复 by mb_empsallg (#439)

*2025-9-28 11:41*

6666

## 回复 by mb_ogvnfpfi (#440)

*2025-9-29 16:10*

6666

## 回复 by 小童net (#441)

*2025-9-30 16:18*

![image](https://bbs.kanxue.com/view/img/face/004.gif)![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by Heary已被占 (#442)

*2025-9-30 16:31*

666

## 回复 by mb_xxeouezk (#443)

*2025-10-4 20:35*

666

## 回复 by 我一无所知 (#444)

*2025-10-6 17:09*

1

## 回复 by KanXue_NG (#445)

*2025-10-11 20:57*

666

## 回复 by mb_azbpkmqj (#446)

*2025-10-15 15:01*

1

## 回复 by 陈世已忘 (#447)

*2025-10-21 18:27*

666

## 回复 by Oo风之恋oO (#448)

*2025-10-22 01:22*

有算法还原吗

## 回复 by Mr.He (#449)

*2025-10-22 10:59*

6666

## 回复 by mb_mfdlvlhz (#450)

*2025-10-22 18:23*

1

## 回复 by mb_kgqnjuzv (#451)

*2025-10-23 09:28*

楼主太牛逼了！

## 回复 by 非洲棒棒 (#452)

*2025-10-23 09:39*

666

## 回复 by mb_uzmffdbw (#453)

*2025-10-23 10:21*

666

## 回复 by mb_tcirlmlq (#454)

*2025-10-23 15:33*

1

## 回复 by 月尘 (#455)

*2025-10-23 18:15*

牛皮啊

## 回复 by mb_ssnabqqf (#456)

*2025-10-30 17:45*

666

## 回复 by style (#457)

*2025-10-30 18:30*

666

## 回复 by Ms135 (#458)

*2025-10-31 08:13*

666

## 回复 by thouger_ (#459)

*2025-10-31 10:54*

感谢分享

## 回复 by 小辣鸡的id (#460)

*2025-11-3 11:29*

666

## 回复 by kinglcs (#461)

*2025-11-4 14:16*

感谢分享

## 回复 by mb_mihutdve (#462)

*2025-11-7 16:06*

1

## 回复 by FindCall (#463)

*2025-11-7 17:18*

good

## 回复 by mb_hrqmnpac (#464)

*2025-11-8 16:57*

6666

## 回复 by TheLuckyOne (#465)

*2025-11-8 19:35*

nb大佬

## 回复 by _Tomorrow (#466)

*2025-11-10 23:28*

666

## 回复 by gaoyanggnay (#467)

*2025-11-11 18:37*

666666

## 回复 by latucc (#468)

*2025-11-12 14:21*

666

## 回复 by AHook (#469)

*2025-11-12 16:56*

666

## 回复 by roysue (#470)

*2025-11-12 23:52*

666

## 回复 by mb_jkuospdr (#471)

*2025-11-18 15:38*

666

## 回复 by hejincai (#472)

*2025-11-18 16:08*

666

## 回复 by mb_qqihqaoo (#473)

*2025-11-18 17:31*

6666

## 回复 by wx_Ocean_414 (#474)

*2025-11-22 10:09*

感谢分享

## 回复 by fyrlove (#475)

*2025-11-22 12:21*

跟着大佬吃肉

## 回复 by 红皮西瓜 (#476)

*2025-11-22 14:54*

666

## 回复 by kekao (#477)

*2025-11-24 12:19*

学习学习![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by AK1988DA (#478)

*2025-11-27 15:53*

2

## 回复 by teshua (#479)

*2025-11-27 17:27*

具体怎么定位到该libsscronet中偏移为：0x2C44BC？有人能给说说吗

## 回复 by mb_goxtznal (#480)

*2025-11-28 11:05*

dadsaaaaaaaaaaa

## 回复 by scpczc (#481)

*2025-12-2 10:58*

感谢楼主

## 回复 by mb_ffsfxcfz (#482)

*2025-12-6 02:22*

666

## 回复 by KXLCN (#483)

*2025-12-11 16:03*

666

## 回复 by mb_uodtmdzg (#484)

*2025-12-11 17:31*

666

## 回复 by mb_fsotigwk (#485)

*2025-12-12 17:41*

666

## 回复 by git_78081miyukiwt2-pixel (#486)

*2025-12-14 22:14*

感谢分享

## 回复 by git_66341tikapiscom (#487)

*2025-12-16 06:26*

good!

## 回复 by buluo533 (#488)

*2025-12-16 08:39*

牛逼

## 回复 by 一只鸭子 (#489)

*2025-12-16 08:40*

666，这就给秒了

## 回复 by 司徒废人 (#490)

*2025-12-16 17:38*

666

## 回复 by chenwitch (#491)

*2025-12-16 17:49*

666

## 回复 by fengvmu (#492)

*2025-12-16 19:47*

照着楼主的来弄 执行最后报错 "result" 为空  是少了什么东西还是什么其他原因啊

## 回复 by fengvmu (#493)

*2025-12-16 19:49*

>
> [teshua](https://bbs.kanxue.com/user-338286.htm)
>
>  具体怎么定位到该libsscronet中偏移为：0x2C44BC？有人能给说说吗
>
>

找个包对照看一下就知道了 有字符串可以模糊定位

## 回复 by wx_Zeal_373 (#494)

*2025-12-17 09:33*

666

## 回复 by mb_dagesnbs (#495)

*2025-12-18 18:24*

666

## 回复 by cici5000 (#496)

*2025-12-18 20:43*

111

## 回复 by lingyi223 (#497)

*2025-12-19 09:29*

666

## 回复 by zkbutt (#498)

*2025-12-22 15:51*

666 怎么抓的包哦

## 回复 by mb_uoktlvrn (#499)

*2025-12-23 09:25*

学习一下

## 回复 by 我就是小熊猫 (#500)

*2025-12-24 09:29*

6666

## 回复 by 司徒废人 (#501)

*2025-12-24 11:34*

用的哪个版本的unidbg，模拟执行，函数返回0

## 回复 by mb_ensciepx (#502)

*2025-12-29 14:08*

学习了

## 回复 by mb_pmgifpme (#503)

*2025-12-30 16:18*

1

## 回复 by mb_xqitfkbz (#504)

*2025-12-30 21:00*

6

## 回复 by goongoon (#505)

*2025-12-31 17:48*

6666

## 回复 by git_37711evilbr43-glitch (#506)

*2026-1-2 07:33*

666

## 回复 by 这谁写的代码 (#507)

*2026-1-4 02:51*

666

## 回复 by swkl (#508)

*2026-1-6 10:32*

感谢楼主

## 回复 by git_75270yue-zi-xuan (#509)

*2026-1-6 17:28*

666

## 回复 by mb_lbbzcrfe (#510)

*2026-1-7 10:15*

666

## 回复 by 后来_797333 (#511)

*2026-1-7 12:14*

111

## 回复 by mb_nxuzsnnd (#512)

*2026-1-7 19:18*

666

## 回复 by mb_euhyowpw (#513)

*2026-1-8 12:00*

111

## 回复 by mb_qwzezjsr (#514)

*2026-1-8 18:55*

1

## 回复 by tjytjy (#515)

*2026-1-8 20:44*

666

## 回复 by 司徒废人 (#516)

*2026-1-14 11:07*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  街道办事处](https://bbs.kanxue.com/user-1024212.htm)
>
>  url单行 header多行格式吧，为啥无法得到输出结果呢null，前面一步一步跟着都没问题 — —
>
>

同样的问题，参数应该没错，就是返回的指针为0，无法取出结果，你解决了吗

## 回复 by 司徒废人 (#517)

*2026-1-14 11:08*

>
> [Freax](https://bbs.kanxue.com/user-920571.htm)
>
>  最新版的unidbg跑不了吗？直接返回null也不报错
>
>

用老的unidbg和最新的，都返回null,你解决了吗

## 回复 by 司徒废人 (#518)

*2026-1-14 11:09*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  fengvmu](https://bbs.kanxue.com/user-543388.htm)
>
>  照着楼主的来弄 执行最后报错 "result" 为空 是少了什么东西还是什么其他原因啊
>
>

同问

## 回复 by mb_aiyhfydo (#519)

*2026-1-17 18:58*

so逆向真的难

## 回复 by mb_aiyhfydo (#520)

*2026-1-17 18:58*

so逆向真的难

## 回复 by mb_nzvpsobt (#521)

*2026-1-19 01:13*

6666

## 回复 by WmSea (#522)

*2026-1-20 01:26*

666

## 回复 by mb_wbwiljrq (#523)

*2026-1-20 13:36*

牛逼

## 回复 by linix (#524)

*2026-1-21 21:54*

666

## 回复 by 持久的胜利 (#525)

*2026-1-23 18:46*

666

## 回复 by rookie江 (#526)

*2026-1-27 15:51*

66

## 回复 by wx_丁丁丁 (#527)

*2026-1-27 19:55*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  司徒废人](https://bbs.kanxue.com/user-641235.htm)
>
>  用老的unidbg和最新的，都返回null,你解决了吗
>
>

你决绝了吗？返回空？

## 回复 by mb_trortpvy (#528)

*2026-1-29 17:54*

感谢分享

## 回复 by 我喜欢你bcd (#529)

*2026-1-29 23:42*

666

## 回复 by mb_tjsboqui (#530)

*2026-1-30 22:49*

666

## 回复 by mb_tjsboqui (#531)

*2026-1-30 22:50*

666

## 回复 by mb_gpxzdoej (#532)

*2026-1-31 19:54*

感谢大佬分享

## 回复 by kami_mahou (#533)

*2026-2-2 08:05*

感谢分享

## 回复 by git_39829Makseeee (#534)

*2026-2-2 19:29*

1

## 回复 by 司徒废人 (#535)

*2026-2-3 11:22*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_丁丁丁](https://bbs.kanxue.com/user-959693.htm)
>
>  你决绝了吗？返回空？
>
>

没有呢，换了较新版本的app样本，重新定位函数地址，调用，也是返回null，没报错

## 回复 by wonhurry (#536)

*2026-2-3 15:14*

看看unidbg

## 回复 by wonhurry (#537)

*2026-2-3 15:24*

>
> [teshua](https://bbs.kanxue.com/user-338286.htm)
>
>  具体怎么定位到该libsscronet中偏移为：0x2C44BC？有人能给说说吗
>
>

输出so的地址，然后去ida里找相关函数

## 回复 by mb_opjxykbd (#538)

*2026-2-4 11:42*

666

## 回复 by git_34020Charlotte-z (#539)

*2026-2-4 14:40*

666

## 回复 by mb_uynabynn (#540)

*2026-2-6 15:38*

666

## 回复 by mb_knfqonrf (#541)

*2026-2-7 00:35*

你的帖子非常有用，感谢分享！

## 回复 by mb_fglogyec (#542)

*2026-2-7 14:13*

6666

## 回复 by zylrocket (#543)

*2026-2-7 14:57*

又看一次，很有道理

## 回复 by mb_npsajqlx (#544)

*2026-2-11 11:30*

666

## 回复 by 雨洛 (#545)

*2026-2-13 09:55*

666

## 回复 by mb_lqouyhhg (#546)

*2026-2-21 11:45*

1

## 回复 by kccp (#547)

*2026-2-21 14:09*

666

## 回复 by git_88273xtekky (#548)

*2026-2-27 21:24*

nice !

## 回复 by PangBai (#549)

*2026-3-1 22:55*

999

## 回复 by kelvin_IDA (#550)

*2026-3-3 10:08*

1112321

## 回复 by 大萨达 (#551)

*2026-3-14 20:58*

666

## 回复 by uniking (#552)

*2026-3-16 17:43*

6

## 回复 by ak8888 (#553)

*2026-3-17 16:03*

高手

## 回复 by wx_Yu_799 (#554)

*2026-3-20 10:03*

666

## 回复 by mb_vywouypi (#555)

*2026-3-26 21:45*

666666

## 回复 by 军哥i (#556)

*2026-3-30 18:34*

学习一下

## 回复 by 军哥i (#557)

*2026-3-30 18:37*

为什么我调用后返回的null，环境都补了

## 回复 by fancy繁星 (#558)

*2026-4-2 11:16*

6

## 回复 by XCicada (#559)

*2026-4-2 12:13*

感谢

## 回复 by Arsylk (#560)

*2026-4-2 15:08*

66

## 回复 by mb_ruvolmra (#561)

*2026-4-8 14:02*

666

## 回复 by hanjiefang (#562)

*2026-4-9 09:51*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_uktygsmq (#563)

*2026-4-9 17:05*

6666

## 回复 by mb_aigrbleb (#564)

*2026-4-9 17:08*

88888666666

## 回复 by git_47562Skill (#565)

*2026-4-10 15:49*

great content

## 回复 by mb_yvitjtil (#566)

*2026-4-11 12:51*

6666

## 回复 by wuxiping (#567)

*2026-4-11 19:59*

不明觉厉！！

## 回复 by mb_rfachdtw (#568)

*2026-4-14 09:17*

12

## 回复 by mb_leghawkh (#569)

*2026-4-15 21:31*

6666

## 回复 by sakmacc (#570)

*2026-4-16 09:57*

666

## 回复 by git_24708cy3ber (#571)

*2026-4-20 00:02*

666

## 回复 by nrllh (#572)

*2026-4-22 19:12*

666

## 回复 by git_23977jackmama12138 (#573)

*2026-4-23 11:40*

6666666

## 回复 by mb_ehrbohcl (#574)

*2026-4-24 15:00*

666

## 回复 by samosxin (#575)

*2026-4-25 13:25*

666

## 回复 by mb_idpcizst (#576)

*2026-5-7 13:08*

![image](https://bbs.kanxue.com/view/img/face/062.gif)

## 回复 by mb_pveclrmt (#577)

*2026-5-8 09:07*

666

## 回复 by Big权 (#578)

*2026-5-8 11:54*

666

## 回复 by stimexy (#579)

*2026-5-8 16:23*

666

## 回复 by mb_gzmqijnf (#580)

*2026-5-10 22:43*

7

## 回复 by njxxdx (#581)

*2026-5-11 10:58*

顶顶顶顶顶

## 回复 by mb_rrwegvyc (#582)

*2026-5-15 13:17*

6666666666666666666

## 回复 by 两颗大树 (#583)

*2026-5-18 11:13*

666

## 回复 by git_28990huynt00 (#584)

*2026-5-19 17:59*

666 ![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by mb_rzyawund (#585)

*2026-5-20 17:36*

666

## 回复 by mb_zvqaijnr (#586)

*2026-5-20 21:48*

999

## 回复 by ynssss (#587)

*2026-5-20 22:34*

1

## 回复 by mb_ysikfhxt (#588)

*2026-5-21 17:44*

111

## 回复 by flyocean (#589)

*2026-5-25 07:31*

![image](https://bbs.kanxue.com/view/img/face/038.gif) 学习

## 回复 by axx_rysgce (#590)

*2026-5-26 01:43*

999

## 回复 by bygrand (#591)

*2026-5-27 11:30*

666

## 回复 by 简单的简单 (#592)

*2026-5-27 22:42*

666

## 回复 by wx_._558 (#593)

*2026-5-29 12:59*

学习一下

## 回复 by git_57798nekiyotec (#594)

*2026-5-29 23:42*

656

## 回复 by mb_tcirlmlq (#595)

*2026-6-5 20:07*

1

## 回复 by git_96236530842318 (#596)

*2026-6-7 15:09*

1213

## 回复 by mb_sffewkkq (#597)

*2026-6-10 01:22*

666

## 回复 by johnwas (#598)

*2026-6-22 23:58*

666

## 回复 by Cherryl (#599)

*2026-6-23 01:04*

666

## 回复 by Timele (#600)

*2026-6-24 14:11*

666666

## 回复 by 田木果呦 (#601)

*2026-6-25 23:52*

666

## 回复 by jsjsjwjs (#602)

*2026-6-28 13:03*

666

## 回复 by mb_gcjwsflo (#603)

*2026-6-30 17:00*

666

## 回复 by mb_hltubdyg (#604)

*2026-7-2 20:59*

1

## 回复 by mb_hltubdyg (#605)

*2026-7-2 21:00*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_vjpiriil](https://bbs.kanxue.com/user-987993.htm)
>  666
>

666

## 回复 by mb_zazihpbz (#606)

*2026-7-7 19:33*

666

## 回复 by mb_kqoewvav (#607)

*2026-7-8 00:05*

666

## 回复 by nuomida (#608)

*2026-7-8 11:08*

学习一下

## 回复 by mb_mswsshte (#609)

*2026-7-16 16:55*

6

## 回复 by Joobih (#610)

*2026-7-17 11:10*

太有用了

## 回复 by jianxcao (#611)

*2026-7-17 17:52*

ok

## 回复 by mb_degalzhb (#612)

*2026-7-20 10:19*

666

## 回复 by mb_tykslmph (#613)

可以

## 回复 by git_69678tuantmtb (#614)

666

## 回复 by git_51354IsoumaNaN (#615)

666
