---
title: '[原创]CTF新手合集：Flag算法分析'
url: https://bbs.kanxue.com/thread-279888.htm
tid: 279888
author: 复活甲
date: '2023-12-14'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:35:42+08:00'
replies: 1
---

### 一、前言

为什么是新手合集呢？主要是以下的CTF项目难度都不大，仅限于java层。接下来，我们将详细分析和算法还原下。

### 二、CTF:Android20

这题主要在于算法的还原，代码逻辑是比较清晰的，MainActivity.this.check()为真，.check()函数内字符串满足条件则完成flag.
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_56SSU7FEN3DFMP9.webp)
接下来对算法进行还原：
从代码分析来看，只要循环内满足 ：this.s[i] = (chars[i] ^ 23) 我们用python 来还原这个逻辑：

| 12345678 | `s` `=` `[``113``,` `123``,` `118``,` `112``,` `108``,` `94``,` `99``,` `72``,` `38``,` `68``,` `72``,` `87``,` `89``,` `72``,` `36``,` `118``,` `100``,` `78``,` `72``,` `87``,` `121``,` `83``,` `101``,` `39``,` `62``,` `94``,` `62``,` `38``,` `107``,` `115``,` `106``]` `ss``=` `[]``for` `one` `in` `s:``b` `=` `one ^` `23``ss.append(b)``ss_b` `=` `bytes(ss)``print``(ss_b.decode(``'utf-8'``))` `# flag{It_1S_@N_3asY_@nDr0)I)1\|d}` |
|-|-|

flag{It_1S_@N_3asY_@nDr0)I)1|d}

### 三、CTF:简单校验

这一题的利用到数学里面的二元一次方程来求解。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_Z3ZMBVRQZ8SH5EQ.webp)
满足 a.a(editText.getText().toString()) 为真则成功，那么a()函数里面满足这个条件则成功。a[i2] != (b[i2] * iArr[i2] * iArr[i2]) + (c[i2] * iArr[i2]) + d[i2] || a[i2 + 1] != (b[i2] * iArr[i2 + 1] * iArr[i2 + 1]) + (c[i2] * iArr[i2 + 1]) + d[i2]。这个函数 我拆开来开 就是满足：
a[i2]-d[i2] = (b[i2] * iArr[i2] * iArr[i2]) + (c[i2] * iArr[i2])
类似： y = x^2+x，就是一个【一元二次方程】 已知 y 求 x ,再把 x的值拼接起来，就是我们输入的字符串。
算法还原：

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950 | `from` `sympy` `import` `symbols, Eq, solve` `a` `=` `[``0``,` `146527998``,` `205327308``,` `94243885``,` `138810487``,` `408218567``,` `77866117``,` `71548549``,` `563255818``,` `559010506``,` `449018203``,``576200653``,` `307283021``,` `467607947``,` `314806739``,` `341420795``,` `341420795``,` `469998524``,` `417733494``,` `342206934``,` `392460324``,``382290309``,` `185532945``,` `364788505``,` `210058699``,` `198137551``,` `360748557``,` `440064477``,` `319861317``,` `676258995``,` `389214123``,``829768461``,` `534844356``,` `427514172``,` `864054312``]` `b` `=` `[``13710``,` `46393``,` `49151``,` `36900``,` `59564``,` `35883``,` `3517``,` `52957``,` `1509``,` `61207``,` `63274``,` `27694``,` `20932``,` `37997``,` `22069``,` `8438``,` `33995``,``53298``,` `16908``,` `30902``,` `64602``,` `64028``,` `29629``,` `26537``,` `12026``,` `31610``,` `48639``,` `19968``,` `45654``,` `51972``,` `64956``,` `45293``,` `64752``,``37108``]` `c` `=` `[``38129``,` `57355``,` `22538``,` `47767``,` `8940``,` `4975``,` `27050``,` `56102``,` `21796``,` `41174``,` `63445``,` `53454``,` `28762``,` `59215``,` `16407``,` `64340``,``37644``,` `59896``,` `41276``,` `25896``,` `27501``,` `38944``,` `37039``,` `38213``,` `61842``,` `43497``,` `9221``,` `9879``,` `14436``,` `60468``,` `19926``,` `47198``,` `8406``,``64666``]` `d` `=` `[``0``,` `-``341994984``,` `-``370404060``,` `-``257581614``,` `-``494024809``,` `-``135267265``,` `54930974``,` `-``155841406``,` `540422378``,` `-``107286502``,``-``128056922``,` `265261633``,` `275964257``,` `119059597``,` `202392013``,` `283676377``,` `126284124``,` `-``68971076``,` `261217574``,` `197555158``,``-``12893337``,` `-``10293675``,` `93868075``,` `121661845``,` `167461231``,` `123220255``,` `221507``,` `258914772``,` `180963987``,` `107841171``,` `41609001``,``276531381``,` `169983906``,` `276158562``]`  `def` `solve_quadratic_equation(a, b, c):``# 定义符号变量``x` `=` `symbols(``'x'``)` `# 定义方程``equation` `=` `Eq(a` `*` `x` `*``*` `2` `+` `b` `*` `x` `+` `c,` `0``)` `# 解方程``solutions` `=` `solve(equation, x)` `return` `solutions`  `print``(``"len(a) "``,` `len``(a),` `"len(c) "``,` `len``(c))``my_string` `=` `"adksisjhewadksisjhewadksisjhewwwert"``ascii_values` `=` `[``ord``(char)` `for` `char` `in` `my_string]``iArr` `=` `ascii_values``print``(iArr)` `i` `=` `0``iArr_new` `=` `[]``while` `i <` `len``(c):``a1` `=` `a[i]``a2` `=` `a[i` `+` `1``]``print``(``"a1 :"``, a1,` `" a2 :"``, a2)``# a1 = (b[i] * iArr[i] * iArr[i]) + (c[i] * iArr[i]) + d[i]``# a2 = (b[i] * iArr[i + 1] * iArr[i + 1]) + (c[i] * iArr[i + 1]) + d[i]``solutions` `=` `solve_quadratic_equation(b[i], c[i], d[i]` `-` `a1)``sign_v` `=` `solutions``print``(``"sign_v : "``, sign_v)``iArr_new.append(sign_v)``i` `=` `i` `+` `1` `iArr_new_str` `=` `bytes(iArr_new)``print``(``"iArr_new_str : "``, iArr_new_str)` `结果 ：``[``0``,` `102``,` `108``,` `97``,` `103``,` `123``,` `77``,` `65``,` `116``,` `104``,` `95``,` `105``,` `38``,` `95``,` `71``,` `79``,` `79``,` `100``,` `95``,` `68``,` `79``,` `78``,` `55``,` `95``,` `57``,` `48``,` `86``,` `95``,` `55``,` `104``,` `73``,` `110``,` `75``,` `63``]``iArr_new_str :  b``'\x00flag{MAth_i&_GOOd_DON7_90V_7hInK?'` |
|-|-|

flag{MAth_i&_GOOd_DON7_90V_7hInK?

### 四、CTF：easy_Android

这题对于之前2个来说稍微复杂点。核心思想就是字符MD5加密与给定的字符的比较。不过它难就难在你知道MD5加密的结果，反向推算字符串，但是MD5又是不可逆的，怎么反推回去呢？挺有意思是不，接下来我们分析看看。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_64RK8CFVQ7AJFTS.webp)
要想成功，必需满足红框内的条件为真。接着我们到a()方法中：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_2X6WVCNKDZR5NCG.webp)
输入的字符长度"flag{this_is_a_fake_flag_ahhhhh}"长度相同，满足e().a的条件：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_H6GATMF7U8G7RVD.webp)
满足 b.a(a(str, str2).toString().substring(0, 4), "utf8").equals(this.a) 以此类推。求解str的值，根据代码逻辑，a(str, str2)字符换算转换后调用b.a（）完成MD5加密返回值 等于 a、b、c等。
通过代码分析，我们还得验证我们的分析结果，万一里面的MD5加密是魔改的，搞了半天不就是很尴尬。

| 123456789101112131415161718192021 | `function hook_so() {``Java.perform(function () {` `var e` `=` `Java.use(``"com.he.tian.easymix.e"``);``e[``"a"``].overload(``'java.lang.String'``,` `'java.lang.String'``).implementation` `=` `function (``str``, str2) {``console.log(``'a is called'` `+` `', '` `+` `'str: '` `+` `str` `+` `', '` `+` `'str2: '` `+` `str2);``var ret` `=` `this.a(``str``, str2);``console.log(``'a ret value is '``, ret);``return` `ret;``};` `var b` `=` `Java.use(``"com.he.tian.easymix.b"``);``b[``"a"``].overload(``'java.lang.String'``,` `'java.lang.String'``).implementation` `=` `function (``str``, str2) {``console.log(``'a is called'` `+` `', '` `+` `'str: '` `+` `str` `+` `', '` `+` `'str2: '` `+` `str2);``var ret` `=` `this.a(``str``, str2);``console.log(``'a ret value is '` `+` `ret);``return` `ret;``};` `})``}` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_2WBUP87A3R9U6U2.webp)

通过hook 验证了我们的分析。通过 a(String str, String str2) 的到的字符串，在切成8段，每段四个字符 MD5 得到的结果就是 a、b、c、d、e、f、g、h字符串。
既然如此 我们就暴力破解，组成相应的字符，进行加密 一一比对就好了。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566 | `import` `hashlib``import` `time``def` `calculate_md5(input_string):``md5_hash` `=` `hashlib.md5()``md5_hash.update(input_string.encode())``return` `md5_hash.hexdigest()`  `def` `xor_strings(str1, str2):``bytes1` `=` `str1.encode()``bytes2` `=` `str2.encode()` `max_length` `=` `max``(``len``(bytes1),` `len``(bytes2))``min_length` `=` `min``(``len``(bytes1),` `len``(bytes2))` `bytes1` `=` `bytes1[:min_length]``bytes2` `=` `bytes2[:min_length]` `result_bytes` `=` `bytearray(min_length)` `for` `i` `in` `range``(min_length):``result_bytes[i]` `=` `bytes1[i] ^ bytes2[i]` `return` `result_bytes.decode()`  `# 示例用法 flag{this_is_a_fake_flag_ahhhhh}``str1` `=` `"6666"``stra` `=` `"flag"``strb` `=` `"{thi"``strc` `=` `"s_is"``strd` `=` `"_a_f"``stre` `=` `"ake_"``strf` `=` `"flag"``strg` `=` `"_ahh"``strh` `=` `"hhh}"`   `if` `__name__` `=``=` `'__main__'``:``a` `=` `"2061e19de42da6e0de934592a2de3ca0"``b` `=` `"a81813dabd92cefdc6bbf28ea522d2d1"``c` `=` `"4b98921c9b772ed5971c9eca38b08c9f"``d` `=` `"81773872cbbd24dd8df2b980a2b47340"``e` `=` `"73b131aa8e4847d27a1c20608199814e"``f` `=` `"bbd7c4e20e99f0a3bf21c148fe22f21d"``g` `=` `"bf268d46ef91eea2634c34db64c91ef2"``h` `=` `"0862deb943decbddb87dbf0eec3a06cc"``i` `=` `"7a59d932e8184ae963c40a759cc38fec"` `str_list` `=``[``'0'``,` `'1'``,` `'2'``,` `'3'``,` `'4'``,` `'5'``,` `'6'``,` `'7'``,` `'8'``,` `'9'``,` `'a'``,` `'b'``,` `'c'``,` `'d'``,` `'e'``,` `'f'``,` `'g'``,` `'h'``,` `'i'``,` `'j'``,` `'k'``,` `'l'``,` `'m'``,` `'n'``,` `'o'``,` `'p'``,` `'q'``,` `'r'``,` `'s'``,` `'t'``,` `'u'``,` `'v'``,` `'w'``,` `'x'``,` `'y'``,` `'z'``]` `for` `one` `in` `str_list:``for` `two` `in` `str_list:``for` `three` `in` `str_list:``for` `four` `in` `str_list:``s` `=` `str``(one)` `+` `str``(two)` `+` `str``(three)` `+` `str``(four)``print``(s)``result` `=` `xor_strings(s, strh)``print``(result)``result_md5` `=` `calculate_md5(result)``print``(result_md5)``if` `result_md5` `=``=` `h:``print``(``"扎到数值："``, s)``time.sleep(``1000``)``break` |
|-|-|

得到结果：bd1d6ba7f1d3f5a13ebb0a75844cccfa
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_W37JP9W6RHFWHQ7.webp)

上传的附件：
- easy_Android.apk

（1.50MB，25次下载）
- 简单校验.apk

（660.48kb，18次下载）
- android20.apk

（1.14MB，21次下载）

---

# 回复

## 回复 by 秋狝 (#2)

*2023-12-15 23:36*

感谢分享
