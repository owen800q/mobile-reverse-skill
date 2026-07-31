---
title: '[原创]Frida 实战 KGB Messenger'
url: https://bbs.kanxue.com/thread-278116.htm
tid: 278116
author: 复活甲
date: '2023-07-22'
tags: [Android安全, 原创, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:40:23+08:00'
replies: 2
---

## 0x01 前言

KGB Messenger是一个类似闯关的APP，有很多关卡，通过的方法有很多种，这里我们主要用frida进行闯关。中间有很多关于算法的实现和反推演的过程，其实对于新手还是很有挑战的，当然了对于我来说也是很有挑战的，接下分享下通关的思路和方法。

## 0x02 第一关：This app can only run on Russian devices.

打开APP，映入眼前的就是 This app can only run on Russian devices.的提示报错，如果不解决这个，后面将无法进行，我们将APP拖入jadx进行分析。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/961239_3HHDJ2AZ26FAPJE.png)
搜索到目标代码，我们分析发现 System.getProperty("user.home") = Russia 即可满足条件进入下一关。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/961239_5X7NK66WMUN36UM.png)
System.getProperty(String name)方法用于得到系统的属性.System是在lang包中的一个类，这个类中存在大
量和系统打交道的实用方法，而且一般都是类方法，.getProperty(String key)就是其中一个比较常用的方
法，用于返回系统参数文件中这个方法指定键所代表的值。

| 12345 | `var system` `=` `Java.use(``"java.lang.System"``);``system.getProperty.overload(``'java.lang.String'``).implementation` `=` `function (``str``) {``var re` `=` `this.getProperty(``str``);``return` `"Russia"``;``}` |
|-|-|

## 0x03 第二关：Must be on the user whitelist.

根据上面的图片，这一关的关键是System.getenv("USER") = getResources().getString(R.string.User)即可通过下一关。通过上一关的分析我知道getenv的类是java.lang.String用样的方法hook修改返回值即可。那返回值是什么呢？从getResources大概可以猜测是资源文件，再跳转到R.string.User。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/961239_5CCZPSVCMSP896R.png)
得到 User = 0x7f0d0000 应该是标记内存地址指向了某个元素，相互映射的关系，我们再搜索 0x7f0d0000
 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/961239_6Q45EPDYBQNBPED.png)
果然再资源文件里面，我再进行搜索。发现 对应的user字符串： RkxBR3s1N0VSTDFOR180UkNIM1J9Cg==
 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/961239_GGNQ2VFMVH8FXHV.png)

| 1234567 | `var system` `=` `Java.use(``"java.lang.System"``);``system.getenv.overload(``'java.lang.String'``).implementation` `=` `function (``str``) {``console.log(``"system.getenv : "``,` `str``)``var re` `=` `this.getenv(``str``);``console.log(``"system.getenv.re : "``, re)``return` `"RkxBR3s1N0VSTDFOR180UkNIM1J9Cg=="``;``}` |
|-|-|

## 0x04 第三关：User not recognized.

来到这一关是一个登录界面，随便输入账号密码，提示：User not recognized.，看来登录是有文章的，我们查看代码分析.
 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/961239_8ZKDV7KJTEN2B6Y.png)
通过第二关的分析，我们很容容易找到了R.string.username = codenameduchess

| 1 | `adb shell` `input` `text` `'codenameduchess'` |
|-|-|

## 0x05 第四关：Incorrect password.

随便输入密码 会提示 Incorrect password.，查看上面的图片我们可以知道，j()这函数是关键，满足true这个条件，即可跳入到下一关。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/961239_FBJTSASYQCWYJ6F.png)
让结果强行改true.

| 12345 | `var LoginActivity` `=` `Java.use(``"com.tlamb96.kgbmessenger.LoginActivity"``);``LoginActivity[``"j"``].implementation` `=` `function () {``var ret` `=` `this.j();``return` `true;``};` |
|-|-|

## 0x06 第五关：V@]EAASB\u0012WZF\u0012e,a$7(&am2(3.\u0003

来到这一关，我们进入到一个消息聊天界面，发送消息是没有反馈的，看代码：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/961239_ZA6NWPA268D9DFJ.png)
this.o.add(new com.tlamb96.kgbmessenger.b.a(R.string.user, obj, j(), false));这个是发送消息的模板，true是对方发送的，flase代表我发发送的消息。当然了这段代码和解密无关，但是地了解它的发送逻辑，排除掉无关的代码。a(obj.toString()).equals(this.p)是闯关的关键。 p="V@]EAASB\u0012WZF\u0012e,a$7(&am2(3.\u0003";输入的值经过a方法，返回值等于p值即可进入下一关。
a()

| 123456789 | `private String a(String` `str``) {``char[] charArray` `=` `str``.toCharArray();``for` `(``int` `i` `=` `0``; i < charArray.length` `/` `2``; i``+``+``) {``char c` `=` `charArray[i];``charArray[i]` `=` `(char) (charArray[(charArray.length` `-` `i)` `-` `1``] ^` `'2'``);``charArray[(charArray.length` `-` `i)` `-` `1``]` `=` `(char) (c ^` `'A'``);``}``return` `new String(charArray);``}` |
|-|-|

这个a方法是一个算法，只要我们反推出这个算法，就知道应该输入什么值，遇到这样的问题，我觉得我们应该先还原算法，不要硬反推，应该这样很烧脑，很浪费时间，正向还原比反向推导要简单的多，我们安装他的逻辑进行编写即可。
再写算法之前，我们先了解下python的异或^运算。

| 123 | `chr``()将数字（``10``进制）转化为中文` `ord``() 将中文转化为数字(``10``进制)` |
|-|-|

python a()还原：

| 12345678910111213141516 | `def` `a(str_m):``charArray2` `=` `list``(str_m)``for` `ii` `in` `range``(``0``,` `int``(``len``(charArray2)` `/` `2``)):``cc` `=` `charArray2[ii]``print``(``"ii "``, ii, cc,` `" charArray2[ii] :"``,` `len``(charArray2)` `-` `ii` `-` `1``, charArray2[``len``(charArray2)` `-` `ii` `-` `1``],``chr``(``ord``(charArray2[``len``(charArray2)` `-` `ii` `-` `1``]) ^` `ord``(``'2'``)),` `"charArray2[len(charArray2) - ii - 1] :"``,``len``(charArray2)` `-` `ii` `-` `1``,` `chr``(``ord``(cc) ^` `ord``(``'A'``)))``charArray2[ii]` `=` `chr``(``ord``(charArray2[``len``(charArray2)` `-` `ii` `-` `1``]) ^` `ord``(``'2'``))``charArray2[``len``(charArray2)` `-` `ii` `-` `1``]` `=` `chr``(``ord``(cc) ^` `ord``(``'A'``))``charArrayStr2` `=` `"".join(charArray2)``print``(``"charArrayStr2:"``, charArrayStr2)``return` `charArrayStr2` `if` `__name__` `=``=` `'__main__'``:``str_m` `=` `"abcdef"`  `# UTWd"` `# re = a(str_m)` |
|-|-|

"abcdef" 经过加密得到 #TWV"# ，当然了得必须验证下你得算法是否正确，万一写错误，不是陷入到了死胡同？所有hook a方法，输入 abcdef 看看打印的结果是不是TWV"#

| 1234567891011 | `var MessengerActivity` `=` `Java.use(``"com.tlamb96.kgbmessenger.MessengerActivity"``);``MessengerActivity[``"a"``].implementation` `=` `function (``str``) {``console.log(``'a is called'` `+` `', '` `+` `'str: '` `+` `str``);``var ret` `=` `this.a(``str``);``console.log(``'a ret value is '` `+` `ret);``return` `ret;``};` `结果：``a` `is` `called,` `str``: abcdef``a ret value` `is` `TWV"``#` |
|-|-|

得到了正向的加密，反推就简单多了，因为写了一遍，再反推和没写直接推演是不一样的。在这里我们要注意下 ^ 这个值的还原。记住这一点：当然也不一定对，欢迎批评指正，互相学习。

| 12 | `求y : x ^` `'值'` `=` `y``求x : y ^` `'值'` `=` `x` |
|-|-|

反推算法：

| 12345678910111213 | `def` `a_jie(str_m):``str_m_fanzhuan` `=` `str_m[::``-``1``]``charArray2` `=` `list``(str_m_fanzhuan)``for` `ii` `in` `range``(``0``,` `int``(``len``(charArray2)` `/` `2``)):``cc` `=` `charArray2[ii]``charArray2[ii]` `=` `chr``(``ord``(charArray2[``len``(charArray2)` `-` `ii` `-` `1``]) ^` `ord``(``'2'``))``charArray2[``len``(charArray2)` `-` `ii` `-` `1``]` `=` `chr``(``ord``(cc) ^` `ord``(``'A'``))``charArrayStr2` `=` `"".join(charArray2)``print``(``"charArrayStr2:"``, charArrayStr2)` `# fedcba``# 再反转：``str_m_fanzhuan` `=` `charArrayStr2[::``-``1``]``print``(str_m_fanzhuan)``return` `str_m_fanzhuan` |
|-|-|

我们输入 TWV"# 得到值 ：abcedf 完全正确。这个时候我们再输入p值：

| 12345 | `ss` `=` `"V@]EAASB\u0012WZF\u0012e,a$7(&am2(3.\u0003"``re` `=` `a_jie(ss)` `# Boris, give me the password`  `返回结果： Boris, give me the password` |
|-|-|

输入 ： Boris, give me the password 即可进入到下一关。

## 0x07 第六关：\u0000dslp}oQ\u0000 dks∣M0˘000h+AYQg0˘000P∗!M|M\u0000h +AYQg\u0000P*!M∣M0˘000h+AYQg0˘000P∗!MgQ\u0000

这一关的思路和第五关一样，他们的风控手段也是雷同的。主要是 b(String str) = r = "\u0000dslp}oQ\u0000 dks∣M0˘000h+AYQg0˘000P∗!M|M\u0000h +AYQg\u0000P*!M∣M0˘000h+AYQg0˘000P∗!MgQ\u0000";
b() 源码：

| 123456789101112 | `private String b(String` `str``) {``char[] charArray` `=` `str``.toCharArray();``for` `(``int` `i` `=` `0``; i < charArray.length; i``+``+``) {``charArray[i]` `=` `(char) ((charArray[i] >> (i` `%` `8``)) ^ charArray[i]);``}``for` `(``int` `i2` `=` `0``; i2 < charArray.length` `/` `2``; i2``+``+``) {``char c` `=` `charArray[i2];``charArray[i2]` `=` `charArray[(charArray.length` `-` `i2)` `-` `1``];``charArray[(charArray.length` `-` `i2)` `-` `1``]` `=` `c;``}``return` `new String(charArray);``}` |
|-|-|

b方法python正向还原：

| 12345678910111213141516 | `def` `b(str_m):``charArray` `=` `list``(str_m)``charArray2` `=` `list``(str_m)` `for` `i` `in` `range``(``len``(charArray)):``charArray[i]` `=` `chr``((``ord``(charArray[i]) >> (i` `%` `8``)) ^` `ord``(charArray[i]))``print``(i,charArray2[i],charArray[i])``print``(charArray)``for` `i2` `in` `range``(``int``(``len``(charArray)` `/` `2``)):``c` `=` `charArray[i2]``charArray[i2]` `=` `charArray[(``len``(charArray)` `-` `i2)` `-` `1``]``charArray[(``len``(charArray)` `-` `i2)` `-` `1``]` `=` `c``print``(i2,c, charArray[i2],` `len``(charArray)` `-` `i2` `-` `1``,charArray[(``len``(charArray)` `-` `i2)` `-` `1``])``print``(charArray)``charArrayStr2` `=` `"".join(charArray)``return` `charArrayStr2` |
|-|-|

我们发现以下代码是主要的加密位置，后面只是实现了一个倒序，只是他实现的过程比较复杂，如果用python 实现这个逻辑只要一行代码就行。废话不多说，只要实现以下代码的反推逻辑即可破解。

| 1234 | `char[] charArray` `=` `str``.toCharArray();``for` `(``int` `i` `=` `0``; i < charArray.length; i``+``+``) {``charArray[i]` `=` `(char) ((charArray[i] >> (i` `%` `8``)) ^ charArray[i]);``}` |
|-|-|

反推后的代码：

| 123456789101112131415161718 | `def` `b_jie(str_m):``str_m` `=` `"\000dslp}oQ\000 dks$\|M\000h +AYQg\000P*!M$gQ\000"``charArray` `=` `list``(``str``(str_m))``print``(str_m)``charArray.reverse()``print``(charArray)``for` `i` `in` `range``(``len``(charArray)):``if` `i` `%` `8` `=``=` `0``:``print``(``"_"``, end``=``"")``continue``for` `ch` `in` `string.printable:``final_ch` `=` `chr``((``ord``(ch) >> (i` `%` `8``)) ^` `ord``(ch))``if` `final_ch` `=``=` `charArray[i]:``print``(ch, end``=``"")` `结果：``[``'\x00'``,` `'Q'``,` `'g'``,` `'$'``,` `'M'``,` `'!'``,` `'*'``,` `'P'``,` `'\x00'``,` `'g'``,` `'Q'``,` `'Y'``,` `'A'``,` `'+'``,` `' '``,` `'h'``,` `'\x00'``,` `'M'``,` `'\|'``,` `'$'``,` `'s'``,` `'k'``,` `'d'``,` `' '``,` `'\x00'``,` `'Q'``,` `'o'``,` `'}'``,` `'p'``,` `'l'``,` `'s'``,` `'d'``,` `'\x00'``]``_ay I` `*``P_EASE``*` `h_ve the _assword_` |
|-|-|

得到 ： 补全单词：May I *PLEASE* have the password
总体来说hook的逻辑还是简单的，代码相信大家都能看得懂，唯一的难度就是a和b方法的加密算法的还原。

---

# 回复

## 回复 by 秋狝 (#2)

*2023-7-22 16:23*

又有bug了,不能收藏

## 回复 by mb_jippoctc (#3)

*2023-8-23 16:02*

最后是只要补相同的就可以了
