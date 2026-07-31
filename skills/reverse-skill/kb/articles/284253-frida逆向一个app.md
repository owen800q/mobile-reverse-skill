---
title: '[原创]frida逆向一个app'
url: https://bbs.kanxue.com/thread-284253.htm
tid: 284253
author: mb_vcrwlkem
date: '2024-11-05'
tags: [Android安全, 原创, 基础理论, 逆向分析]
crawled_at: '2026-07-31T14:18:56+08:00'
replies: 6
---

# 今天收到了一个APP让我研究一下登录 登录已经研究完成 下面则是我的整体思路

| 12 | `为了安全考虑这个app我就不说是那个了 我就说整体的思路``仅供交流学习 严谨非法使用` |
|-|-|

## 开始进行抓包

| 12 | `手机使用代理连接charles``之后开始点击app登录 进行抓包` |
|-|-|

![我用的是这个app代理](https://bbs.kanxue.com/upload/attach/202411/1004574_NSUQGC5RA2XAAJ8.png)
![开始代理](https://bbs.kanxue.com/upload/attach/202411/1004574_BU4V889J2UEVC36.png)

| 1 | `下面则是我抓到的包` |
|-|-|

![抓包](https://bbs.kanxue.com/upload/attach/202411/1004574_XWZVK5PQBC296HU.png)

| 12345 | `抓包之后j进行改包``也就是去掉form中的随机一个参数进行请求发送 这一步的目的就是去除掉没用的参数``这样的话就可以在逆向的时候减少工作量` `下面我告诉大家如何该报` |
|-|-|

![改包点击](https://bbs.kanxue.com/upload/attach/202411/1004574_WM2YCXJHMRMSQZQ.png)
![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202411/1004574_452PU3MUGCG7XG6.png)

| 1 | `按照上面的步骤进行改包 然后发送请求看是否能够成功 如果不能成功的话这个参数是不能去除的` |
|-|-|

## 将app进行反编译

| 12345678 | `这里我用的是jadx``反编译成功之后 如下 注意看箭头标记的位置 如果包很多并没有乱码或者包少初步可以判断是没有加固``如果初步判断没有进行加壳那么就可以进行搜索` `这里有两个搜索方案` `搜索url 也就是发请求的那个 login.ashx``搜索关键字 也就是form中的  而我搜索的是关键字` |
|-|-|

![注意看这里](https://bbs.kanxue.com/upload/attach/202411/1004574_3YTFAS2XKX59CCK.png)

| 1 | `我 搜索到了第一个` |
|-|-|

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202411/1004574_JJHRP5J5KNBSUCC.png)

| 123 | `看起来是个常量` `按照开发的逻辑来说常量是一个经常使用并且不变的 那么就是他了 咱们翻翻这一页的代码``很遗憾 并不是 继续看下一个 也就上面图中的最后一个` |
|-|-|

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202411/1004574_FUH42WDNP8V6N6H.png)

| 1 | `最后一个让我找到了可能是 因为有好多我发现的参数 也就是请求的参数里面看起来都有` |
|-|-|

![在这里插入图片描述](https://bbs.kanxue.com/upload/attach/202411/1004574_7G3ANYVY57N55UF.png)

## 既然找到了 那么就一个个进行破解

| 12345 | `首先是``KEY_APP_ID``这个是个常量的Key 值话也是个常量 那么好 第一个参数已经破解完成``channelid``这个key 并不是个常量 这时候可以用frida进行调用` |
|-|-|

## 开始用frida

| 12 | `先进行注入检测 也就是随便一个函数看看是否有检测` `很幸运 这个app并没有任何检测` |
|-|-|

## 开始接下来的一步开始进行破译

| 12 | `上面说到了 channelid这个值``getChannelId 是这个函数产生的 那么我就开始用frida检测这个值看看他的参数是什么` |
|-|-|

| 123456789101112131415161718192021222324252627 | `import` `frida``import` `sys` `rdev` `=` `frida.get_remote_device()``pid` `=` `rdev.spawn([``"xxxx"``])``session` `=` `rdev.attach(pid)``scr` `=` `"""``Java.perform(function(){` `var AppUtils = Java.use("xxxx.util.AppUtils")``AppUtils.getChannelId.implementation = function(c){``var res = this.getChannelId(c)``console.log(res,"getChannelId")``return res``}` `})``"""` `script` `=` `session.create_script(scr)`  `def` `on_message(message, data):``print``(message, data)` `script.on(``"message"``, on_message)``script.load()``rdev.resume(pid)``sys.stdin.read()` |
|-|-|

| 12345678910111213 | `我的经验是多hook几次看看是否是同一个值 如果是的话那么就直接用就好了` `这里我多试了几次值是一样的 那么我就可以直接用了` `好 接下来就开始破译下一个``KEY_APP_VERSION``这个看起来是个版本号` `按照上面的代码 继续使用getCannelId这个hook脚本继续开始hook  还是建议多hook几次``好 我发现还是一样的 那么好！ 那还是继续用` `接下来就是下一个参数``udid``这个get_uuid 还是用上面的代码进行hook(记得改函数和包 xxx 哪里)` `这个参数 我还是按照习惯多来了几次 发现每次都是不一样的 好那么深入进行探究！` |
|-|-|

| 123 | `public` `static` `String getUDID(Context context) {``return` `SecurityUtil.encode3Des(context, getIMEI(context) + HiAnalyticsConstant.REPORT_VAL_SEPARATOR + System.nanoTime() + HiAnalyticsConstant.REPORT_VAL_SEPARATOR + SPUtils.getDeviceId());``}` |
|-|-|

| 1234567 | `这个是代码我发现了有时间生成 那确实每次都会不一样``好 接下来继续深层次研究除了时间的每个参数``getIMEI  多hook 几次看看是不是值是一样的``REPORT_VAL_SEPARATOR  这个是个常量` `getDeviceId  多hook 几次看看是不是值是一样的` `根据验证 上面的值每次都是一样的! 好 接下来那么就继续下一步 用python进行组装` |
|-|-|

| 12345678910111213141516 | `def` `make_uuid(``imei,``report_val_separator,``nano_time,``getDeviceId,``):``make_str` `=` `imei` `+` `report_val_separator` `+` `str``(nano_time)` `+` `report_val_separator` `+` `getDeviceId``return` `make_str`  `uuid` `=` `make_uuid(``imei``=``"xxxx"``,``report_val_separator``=``"xxxx"``,``nano_time``=``time.time_ns(),``getDeviceId``=``"xxxx"``,``)` |
|-|-|

| 123456 | `很好那么看起来``context, getIMEI(context)` `+` `HiAnalyticsConstant.REPORT_VAL_SEPARATOR` `+` `System.nanoTime()` `+` `HiAnalyticsConstant.REPORT_VAL_SEPARATOR` `+` `SPUtils.getDeviceId()` `encode3Des 这个第二个参数已经破译好了`  `这次开始破译 encode3Des` |
|-|-|

| 123456789101112131415 | `public` `static` `String encode3Des(Context context, String str) {``String desKey = AHAPIHelper.getDesKey(context);``byte``[] bArr =` `null``;``if` `(TextUtils.isEmpty(desKey)) {``return` `null``;``}``try` `{``SecretKey generateSecret = SecretKeyFactory.getInstance(``"desede"``).generateSecret(``new` `DESedeKeySpec(desKey.getBytes()));``Cipher instance = Cipher.getInstance(``"desede/CBC/PKCS5Padding"``);``instance.init(``1``, generateSecret,` `new` `IvParameterSpec(iv.getBytes()));``bArr = instance.doFinal(str.getBytes(``"UTF-8"``));``}` `catch` `(Exception unused) {``}``return` `encode(bArr).toString();``}` |
|-|-|

| 12 | `这段代码看起来就是个加密` `3DES``（Triple DES）加密，也称为 DESede``那么好 代码里面也没什么难的地方  那么就改成Python吧` |
|-|-|

| 12345678910111213141516171819202122232425262728 | `from` `Crypto.Cipher` `import` `DES3``from` `Crypto.Util.Padding` `import` `pad``import` `base64` `def` `encode_3des(des_key, data, iv):``if` `len``(des_key) !``=` `24``:``raise` `ValueError(``"The DES key must be 24 bytes long for 3DES."``)` `# 确保密钥长度为 24 字节``des_key` `=` `des_key.encode(``'utf-8'``)[:``24``]` `cipher` `=` `DES3.new(des_key, DES3.MODE_CBC, iv.encode(``'utf-8'``))` `# 对输入数据进行 padding``padded_data` `=` `pad(data.encode(``'utf-8'``), DES3.block_size)` `# 加密数据``encrypted_data` `=` `cipher.encrypt(padded_data)` `# 返回加密后的数据，并进行 base64 编码``return` `base64.b64encode(encrypted_data).decode(``'utf-8'``)` `# 示例调用``des_key` `=` `"your_24_byte_key_here"``iv` `=` `"your_8_byte_iv_here"`  `# IV 长度为 8 字节``data` `=` `"The data to encrypt"``encoded_data` `=` `encode_3des(des_key, data, iv)``print``(f``"Encrypted data: {encoded_data}"``)` |
|-|-|

| 1 | `其中des_key需要拿到` |
|-|-|

![发现是个so文件](https://bbs.kanxue.com/upload/attach/202411/1004574_NYG4D5G35Y8BNYK.png)

| 12345678910 | `看起来是个so文件``按照我的经验来说继续hook这个 多hook几次看看值是不是一样的  经验看 很多都是死值 除了大型app` `很好 这个是个死值``那俺么我就得到了 des_key``IV``现在还差一IV  但是他这个IV是常量``private static final String iv` `=` `"appapich"``;` `很好很好 UUID 我已经完成` |
|-|-|

| 123456789101112131415 | `import` `frida``import` `sys` `rdev` `=` `frida.get_remote_device()``pid` `=` `rdev.spawn([``"xxxx"``])``session` `=` `rdev.attach(pid)``scr` `=` `"""``Java.perform(function(){` `var AppUtils` `=` `Java.use(``"xxxx.util.AppUtils"``)``AppUtils.getChannelId.implementation` `=` `function(c){``var res` `=` `this.getChannelId(c)``console.log(res,``"getChannelId"``)``return` `res``}` `})` |
|-|-|

| 12345678910111213141516 | `接下来看下一个参数``userkey 这个在请求中并没有发现这个值 如果下面没有引用的话 那么就不管` `checkNullParams(treeMap); 这个干了什么 去看看``private static void checkNullParams(``Map``<String, String>` `map``) {``for` `(String` `str` `:` `map``.keySet()) {``if` `(``map``.get(``str``)` `=``=` `null) {``map``.put(``str``, "");``}``}``}``这段 Java 代码的目的是检查给定的` `Map``<String, String> 中的每个键值对，``如果某个值是 null，则将该值替换为空字符串 ""``接下来看这个代码``String signByType` `=` `SignManager.INSTANCE.signByType(i, treeMap);``还是进行hook下面的代码` |
|-|-|

| 12345678910111213141516171819202122232425262728293031 | `public` `final` `String signByType(``@SignType` `int` `i, TreeMap<String, String> paramMap) {``Intrinsics.checkNotNullParameter(paramMap,` `"paramMap"``);``StringBuilder sb =` `new` `StringBuilder();``String str = KEY_V1;``if` `(i !=` `0``) {``if` `(i ==` `1``) {``str = KEY_V2;``}` `else` `if` `(i ==` `2``) {``str = KEY_SHARE;``}` `else` `if` `(i ==` `3``) {``str = KEY_AUTOHOME;``}``}``sb.append(str);``for` `(String str2 : paramMap.keySet()) {``sb.append(str2);``sb.append(paramMap.get(str2));``}``sb.append(str);``String encodeMD5 = SecurityUtil.encodeMD5(sb.toString());``if` `(encodeMD5 !=` `null``) {``Locale ROOT = Locale.ROOT;``Intrinsics.checkNotNullExpressionValue(ROOT,` `"ROOT"``);``String upperCase = encodeMD5.toUpperCase(ROOT);``Intrinsics.checkNotNullExpressionValue(upperCase,` `"this as java.lang.String).toUpperCase(locale)"``);``if` `(upperCase !=` `null``) {``return` `upperCase;``}``}``return` `""``;``}` |
|-|-|

| 1 | `这个下面进行kook` |
|-|-|

| 1234567891011121314151617 | `import` `frida``import` `sys` `rdev` `=` `frida.get_remote_device()``pid` `=` `rdev.spawn([``"xxxx"``])``session` `=` `rdev.attach(pid)``scr` `=` `"""``Java.perform(function(){` `var AppUtils` `=` `Java.use(``"xxxx.util.AppUtils"``)``AppUtils.signByType.implementation` `=` `function(i,tree){``console.log(i,``"getChannelId i"``)``console.log(tree,``"getChannelId tree"``)``var res` `=` `this.signByType(i,tree)``console.log(res,``"getChannelId"``)``return` `res``}` `})` |
|-|-|

| 123456789101112131415161718192021222324252627 | `接下来也是一行行查看``Intrinsics.checkNotNullParameter(paramMap,` `"paramMap"``);``StringBuilder sb` `=` `new StringBuilder();``String` `str` `=` `KEY_V1;``if` `(i !``=` `0``) {``if` `(i` `=``=` `1``) {``str` `=` `KEY_V2;``}` `else` `if` `(i` `=``=` `2``) {``str` `=` `KEY_SHARE;``}` `else` `if` `(i` `=``=` `3``) {``str` `=` `KEY_AUTOHOME;``}``}``sb.append(``str``);``for` `(String str2 : paramMap.keySet()) {``sb.append(str2);``sb.append(paramMap.get(str2));``}``sb.append(``str``);``上面就是按照i进行了是那个i进行了拼接 没什么可看的 那就按照他的做``下面就是按照MD5进行了加密``String encodeMD5` `=` `SecurityUtil.encodeMD5(sb.toString());``Locale ROOT` `=` `Locale.ROOT;``Intrinsics.checkNotNullExpressionValue(ROOT,` `"ROOT"``);``String upperCase` `=` `encodeMD5.toUpperCase(ROOT);``Intrinsics.checkNotNullExpressionValue(upperCase,` `"this as java.lang.String).toUpperCase(locale)"``);``这个代码就是可以理解成转换成大写  从这里开看 已经完成了大部分的参数 下面是我的python实现` |
|-|-|

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113 | `def` `encode_md5(s):``# 创建 MD5 哈希对象``md5` `=` `hashlib.md5()` `# 更新哈希对象``md5.update(s.encode(``'utf-8'``))` `# 获取十六进制格式的哈希值``return` `md5.hexdigest()`  `def` `make_uuid(``imei,``report_val_separator,``nano_time,``getDeviceId,``):``make_str` `=` `imei` `+` `report_val_separator` `+` `str``(nano_time)` `+` `report_val_separator` `+` `getDeviceId``return` `make_str`  `uuid` `=` `make_uuid(``imei``=``"x"``,``report_val_separator``=``"x"``,``nano_time``=``time.time_ns(),``getDeviceId``=``"x"``,``)``print``(uuid)`  `def` `make_3DES(desKey, data):``from` `Crypto.Cipher` `import` `DES3``from` `Crypto.Util.Padding` `import` `pad``from` `Crypto.Random` `import` `get_random_bytes``import` `base64``# 你提供的 IV 值，或者可以动态生成``iv` `=` `b``"appapich"`  `# 或者使用一个更安全的随机IV``if` `len``(desKey) !``=` `24``:``raise` `ValueError(``"The DES key must be 24 bytes long for 3DES."``)` `# 确保 key 的长度是 24 字节``desKey` `=` `desKey.encode(``'utf-8'``)[:``24``]` `cipher` `=` `DES3.new(desKey, DES3.MODE_CBC, iv)` `# 对输入数据进行 padding``padded_data` `=` `pad(data.encode(``'utf-8'``), DES3.block_size)` `# 加密数据``encrypted_data` `=` `cipher.encrypt(padded_data)` `# 返回加密后的数据，并进行 base64 编码``return` `base64.b64encode(encrypted_data).decode(``'utf-8'``)`  `desKey` `=` `"xxxxxxxx"`  `# 用你自己的 desKey 替换``encoded_data` `=` `make_3DES(desKey[``0``:``24``], uuid)`  `def` `sign_type(param_map):``import` `hashlib``# 密钥定义 (替换成相应的密钥)``KEY_V1` `=` `"W@oC!AH_6Ew1f6%8"``KEY_V2` `=` `"W@oC!AH_6Ew1f6%8"``KEY_SHARE` `=` `"W@oC!AH_6Ew1f6%8"``KEY_AUTOHOME` `=` `"W@oC!AH_6Ew1f6%8"` `def` `sign_by_type(i, param_map):``# 参数检查``if` `not` `isinstance``(param_map,` `dict``):``raise` `ValueError(``"param_map must be a dictionary"``)` `# 根据 i 选择密钥``if` `i` `=``=` `0``:``key` `=` `KEY_V1``elif` `i` `=``=` `1``:``key` `=` `KEY_V2``elif` `i` `=``=` `2``:``key` `=` `KEY_SHARE``elif` `i` `=``=` `3``:``key` `=` `KEY_AUTOHOME``else``:``raise` `ValueError(``"Invalid value for 'i'"``)` `# 拼接字符串``sb` `=` `key``for` `key_str, value_str` `in` `param_map.items():``sb` `+``=` `key_str` `+` `value_str``sb` `+``=` `key` `# 计算 MD5``md5_result` `=` `hashlib.md5(sb.encode(``'utf-8'``)).hexdigest().upper()` `return` `md5_result` `# 示例用法``i` `=` `1`  `# 用你提供的类型值``signed_result` `=` `sign_by_type(i, param_map)``return` `signed_result`  `_sign` `=` `sign_type(``param_map``=``{``'_appid'``:` `'xxxx'``,``'appversion'``:` `'xxxx'``,``'channelid'``:` `'xxxx'``,``'pwd'``:` `'96e79218965eb72c92a549dd5a330112'``,``'signkey'``: '',``'type'``: '',``'udid'``: encoded_data,``'username'``:` `'15633624055'``}``)` |
|-|-|

| 1234567 | `完成到现在还差一个那就是密码加密``那么就开始查看密码加密``这个时候就不能搜索pwd  经过上面的排查 应该是每个请求都会带这些参数看起来就像中间件一样 那么就搜索url` `第一个是常量 第二个是引用``SecurityUtil.encodeMD5(str3)``就是普通的MD5加密` |
|-|-|

| 1 | `public` `static` `final` `String LOGIN_URL =` `"/tradercloud/sealed/login/login.ashx"``;` |
|-|-|

| 123456 | `public` `static` `void` `loginByPassword(String str, String str2, String str3, String str4, String str5, ResponseCallback<UserBean> responseCallback) {``HttpUtil.Builder builder =` `new` `HttpUtil.Builder();``builder.tag(str).method(HttpUtil.Method.POST).signType(``1``).url(LOGIN_URL).param(``"username"``, str2).param(``"type"``, str4).param(``"signkey"``, str5).param(``"pwd"``, SecurityUtil.encodeMD5(str3));``doRequest(builder, responseCallback,` `new` `TypeToken<BaseResult<UserBean>>() {` `// from class: com.che168.autotradercloud.user.model.UserModel.5``}.getType());``}` |
|-|-|

# 结束

| 12 | `下面就是我的完成整合后的python代码` `已经完成了登录加密破解 涉密参数我用的X` |
|-|-|

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182 | `import` `time` `import` `requests`  `def` `start(pwd,``_appid,``channelid,``appversion,``_sign,``signkey,``type_,``udid,``username):``import` `requests` `url` `=` `'x'` `headers` `=` `{``'Host'``:` `'x'``,``'Cache-Control'``:` `'public, max-age=0'``,``'Traceid'``:` `'x'``,``'Content-Type'``:` `'application/x-www-form-urlencoded'``,``'User-Agent'``:` `'okhttp/3.14.9'``,``}``data` `=` `{``'pwd'``: pwd,``'_appid'``: _appid,``'channelid'``: channelid,``'appversion'``: appversion,``'_sign'``: _sign,``'signkey'``: signkey,``'type'``: type_,``'udid'``: udid,``'username'``: username,``}` `# 禁用代理``proxies` `=` `{``"http"``:` `None``,``"https"``:` `None``,``}` `try``:``response` `=` `requests.post(url, headers``=``headers, data``=``data, proxies``=``proxies)``print``(response.text)` `# 打印响应内容``except` `requests.exceptions.RequestException as e:``print``(f``"请求失败: {e}"``)`  `import` `hashlib`  `def` `encode_md5(s):``# 创建 MD5 哈希对象``md5` `=` `hashlib.md5()` `# 更新哈希对象``md5.update(s.encode(``'utf-8'``))` `# 获取十六进制格式的哈希值``return` `md5.hexdigest()`  `def` `make_uuid(``imei,``report_val_separator,``nano_time,``getDeviceId,``):``make_str` `=` `imei` `+` `report_val_separator` `+` `str``(nano_time)` `+` `report_val_separator` `+` `getDeviceId``return` `make_str`  `uuid` `=` `make_uuid(``imei``=``"x"``,``report_val_separator``=``"x"``,``nano_time``=``time.time_ns(),``getDeviceId``=``"x"``,``)``print``(uuid)`  `def` `make_3DES(desKey, data):``from` `Crypto.Cipher` `import` `DES3``from` `Crypto.Util.Padding` `import` `pad``from` `Crypto.Random` `import` `get_random_bytes``import` `base64``# 你提供的 IV 值，或者可以动态生成``iv` `=` `b``"appapich"`  `# 或者使用一个更安全的随机IV``if` `len``(desKey) !``=` `24``:``raise` `ValueError(``"The DES key must be 24 bytes long for 3DES."``)` `# 确保 key 的长度是 24 字节``desKey` `=` `desKey.encode(``'utf-8'``)[:``24``]` `cipher` `=` `DES3.new(desKey, DES3.MODE_CBC, iv)` `# 对输入数据进行 padding``padded_data` `=` `pad(data.encode(``'utf-8'``), DES3.block_size)` `# 加密数据``encrypted_data` `=` `cipher.encrypt(padded_data)` `# 返回加密后的数据，并进行 base64 编码``return` `base64.b64encode(encrypted_data).decode(``'utf-8'``)`  `desKey` `=` `"appapiche168comappapiche168comap"`  `# 用你自己的 desKey 替换``encoded_data` `=` `make_3DES(desKey[``0``:``24``], uuid)`  `def` `sign_type(param_map):``import` `hashlib``# 密钥定义 (替换成相应的密钥)``KEY_V1` `=` `"x"``KEY_V2` `=` `"x"``KEY_SHARE` `=` `"x"``KEY_AUTOHOME` `=` `"x"` `def` `sign_by_type(i, param_map):``# 参数检查``if` `not` `isinstance``(param_map,` `dict``):``raise` `ValueError(``"param_map must be a dictionary"``)` `# 根据 i 选择密钥``if` `i` `=``=` `0``:``key` `=` `KEY_V1``elif` `i` `=``=` `1``:``key` `=` `KEY_V2``elif` `i` `=``=` `2``:``key` `=` `KEY_SHARE``elif` `i` `=``=` `3``:``key` `=` `KEY_AUTOHOME``else``:``raise` `ValueError(``"Invalid value for 'i'"``)` `# 拼接字符串``sb` `=` `key``for` `key_str, value_str` `in` `param_map.items():``sb` `+``=` `key_str` `+` `value_str``sb` `+``=` `key` `# 计算 MD5``md5_result` `=` `hashlib.md5(sb.encode(``'utf-8'``)).hexdigest().upper()` `return` `md5_result` `# 示例用法``i` `=` `1`  `# 用你提供的类型值``signed_result` `=` `sign_by_type(i, param_map)``return` `signed_result`  `_sign` `=` `sign_type(``param_map``=``{``'_appid'``:` `'x'``,``'appversion'``:` `'x'``,``'channelid'``:` `'x'``,``'pwd'``:` `'x'``,``'signkey'``: '',``'type'``: '',``'udid'``: encoded_data,``'username'``:` `'x'``}``)`  `start(``pwd``=``encode_md5(``"x"``),``_appid``=``"x"``,``channelid``=``"x"``,``appversion``=``"x"``,``udid``=``encoded_data,``_sign``=``_sign,``signkey``=``"",``type_``=``"",``username``=``"x"``,` `)` `# 示例用法` |
|-|-|

---

# 回复

## 回复 by NT10086 (#2)

*2024-11-6 09:06*

感谢分享，现在慢慢不让抓包了

## 回复 by azd放 (#3)

*2024-11-6 10:15*

感谢分享

## 回复 by 五彩斑斓的黑 (#4)

*2024-12-4 10:25*

佬,什么app啊

## 回复 by 果冻大砍刀 (#5)

*2024-12-4 18:58*

很不错,唯一能看懂的文章![image](https://bbs.kanxue.com/view/img/face/038.gif)

## 回复 by xiayutian_ (#6)

*2025-1-23 10:49*

>
> [五彩斑斓的黑](https://bbs.kanxue.com/user-1002595.htm)
>
>  佬,什么app啊
>
>
>

车智赢

## 回复 by mb_elqwyvnm (#7)

*2025-1-23 11:08*

你想学习
