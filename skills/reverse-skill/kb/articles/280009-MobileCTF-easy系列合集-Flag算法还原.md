---
title: '[原创]MobileCTF easy系列合集：Flag算法还原'
url: https://bbs.kanxue.com/thread-280009.htm
tid: 280009
author: 复活甲
date: '2023-12-27'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:35:06+08:00'
replies: 4
---

### 0x01 背景

这是由一系列CTF easy项目组成的，难度系数也是逐渐增加的。不管是简单还是复杂，获取flag不是目的，目的是分析和解决问题的方法和思路，不管多少道题，还是逆向其他网站，解决问题的方式是差不多，接下来我们将详细的分析每个项目的算法。

### 0x02 easy_apk

这题考察的是base64算法的知识点，通过Base64Encode()对输入的字符串进行加密，然后与字符串5rFf7E2K6rqN7Hpiyush7E6S5fJg6rsi5NBf6NGT5rs=进行比较，如果相等就完成破解。这题我们用2种解法来获取flag,先来看代码：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_6YYQBPQC6WRRBUZ.webp)
既然如此，我们前期不考虑验证通过的问题，先正向还原他的加密，输入一个简单的数据：例如 abcd 编码结果: JHqKyv==
有了输入值，和返回值，我们用python 还原他的算法：

#### 解法1：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849 | `class` `Base64New:``RANGE` `=` `255``Base64ByteToStr` `=` `[``'v'``,` `'w'``,` `'x'``,` `'r'``,` `'s'``,` `'t'``,` `'u'``,` `'o'``,` `'p'``,` `'q'``,` `'3'``,` `'4'``,` `'5'``,` `'6'``,` `'7'``,` `'A'``,` `'B'``,` `'C'``,` `'D'``,``'E'``,` `'F'``,` `'G'``,` `'H'``,` `'I'``,` `'J'``,` `'y'``,` `'z'``,` `'0'``,` `'1'``,` `'2'``,` `'P'``,` `'Q'``,` `'R'``,` `'S'``,` `'T'``,` `'K'``,` `'L'``,` `'M'``,``'N'``,` `'O'``,` `'Z'``,` `'a'``,` `'b'``,` `'c'``,` `'d'``,` `'U'``,` `'V'``,` `'W'``,` `'X'``,` `'Y'``,` `'e'``,` `'f'``,` `'g'``,` `'h'``,` `'i'``,` `'j'``,` `'k'``,``'l'``,` `'m'``,` `'n'``,` `'8'``,` `'9'``,` `'+'``,` `'/'``]``StrToBase64Byte` `=` `{char: idx` `for` `idx, char` `in` `enumerate``(Base64ByteToStr)}` `def` `Base64Encode(``self``, bytes):``res` `=` `[]``for` `i` `in` `range``(``0``,` `len``(bytes),` `3``):``enBytes` `=` `[``0``]` `*` `4``tmp` `=` `0``for` `k` `in` `range``(``3``):``if` `i` `+` `k <` `len``(bytes):``enBytes[k]` `=` `((bytes[i` `+` `k] &` `255``) >> ((k` `*` `2``)` `+` `2``)) \| tmp``tmp` `=` `(((bytes[i` `+` `k] &` `255``) << ((``2` `-` `k)` `*` `2` `+` `2``)) &` `255``) >>` `2``else``:``enBytes[k]` `=` `tmp``tmp` `=` `64``enBytes[``3``]` `=` `tmp``for` `k2` `in` `range``(``4``):``if` `enBytes[k2] <``=` `63``:``res.append(``self``.Base64ByteToStr[enBytes[k2]])``else``:``res.append(``'='``)` `return` `''.join(res)` `def` `Base64Decode(``self``, encoded_str):``decoded_bytes` `=` `bytearray()` `for` `i` `in` `range``(``0``,` `len``(encoded_str),` `4``):``enChars` `=` `encoded_str[i:i` `+` `4``]``deBytes` `=` `[``0``]` `*` `4` `for` `k` `in` `range``(``4``):``if` `enChars[k] !``=` `'='``:``deBytes[k]` `=` `self``.StrToBase64Byte[enChars[k]]` `decoded_bytes.extend((((deBytes[``0``] <<` `2``) &` `255``) \| (deBytes[``1``] >>` `4``)).to_bytes(``1``,` `'big'``))` `if` `enChars[``2``] !``=` `'='` `and` `len``(enChars) >` `2``:``decoded_bytes.extend((((deBytes[``1``] <<` `4``) &` `255``) \| (deBytes[``2``] >>` `2``)).to_bytes(``1``,` `'big'``))` `if` `enChars[``3``] !``=` `'='` `and` `len``(enChars) >` `3``:``decoded_bytes.extend((((deBytes[``2``] <<` `6``) &` `255``) \| deBytes[``3``]).to_bytes(``1``,` `'big'``))` `return` `decoded_bytes` |
|-|-|

再将 5rFf7E2K6rqN7Hpiyush7E6S5fJg6rsi5NBf6NGT5rs= 值代入其中，解密后得到：05397c42f9b6da593a3644162d36eb01
输入到APP 显示验证成功。

#### 解法2：

还有一种处理的办法，从他的代码其实可以看出他是一个base64加密的换表算法，因为加密的逻辑是符合base64的原理的，然后我们写代码来验证下：

| 12345678910111213 | `import` `base64``s1` `=` `"vwxrstuopq34567ABCDEFGHIJyz012PQRSTKLMNOZabcdUVWXYefghijklmn89+/"``s2` `=` `'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'` `# abcdefghijklmnopqrstuvwxyz0123456789+/ABCDEFGHIJKLMNOPQRSTUVWXYZ` `data` `=` `"5rFf7E2K6rqN7Hpiyush7E6S5fJg6rsi5NBf6NGT5rs="` `print``(``str``.maketrans(s1, s2))``print``(data.translate(``str``.maketrans(s1, s2)).encode(``'utf-8'``))``key` `=` `str``(base64.b64decode(data.translate(``str``.maketrans(s1, s2)).encode(``'utf-8'``)), encoding``=``"utf-8"``)``print``(``" key = "``, key)` `#  key =  05397c42f9b6da593a3644162d36eb01` |
|-|-|

结果是一样的，所以算法的底层逻辑是很重要的，必要时候能节省很多时间。

### 0x03 easy_java

这题是基于java层的，算法是层层嵌套，代码逻辑是非常清晰的，将输入的字符串经过层层处理，得到一个新的字符串，满足sb.toString().equals("wigwrkaugala")即可破解，我们来分析下：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_W6AWSXE4SSNW2HR.webp)
我们先来分析他正常逻辑的算法：
这段代码看起来是在处理一个形如 "flag{...}" 的字符串，通过某种特定的处理和比较，最终确定是否符合特定的条件。

1. if (str.startsWith("flag{") && str.endsWith("}")) 可以看出 输入的字符串必须包含flag{}
2. aVar.a(bVar.a(str)) 这里面计算出来的值很关键。
frida hook aVar.a(bVar.a(str))方法：

| 1234567891011121314151617181920212223242526272829303132 | `function hook_java() {``Java.perform(function () {``var MainActivity` `=` `Java.use(``"com.a.easyjava.MainActivity"``);``MainActivity[``"a"``].overload(``'java.lang.String'``,` `'com.a.easyjava.b'``,` `'com.a.easyjava.a'``).implementation` `=` `function (``str``, bVar, aVar) {``console.log(``"MainActivity.a is called: str=${str}, bVar=${bVar}, aVar=${aVar}"``,``str``,bVar,aVar);``var result` `=` `this[``"a"``](``str``, bVar, aVar);``console.log(``"MainActivity.a result=${result}"``, result);``return` `result;``};``var a` `=` `Java.use(``"com.a.easyjava.a"``);``a[``"a"``].overload(``'java.lang.Integer'``).implementation` `=` `function (num) {``console.log(``"a.a is called: num=${num}"``, num);``var result` `=` `this[``"a"``](num);``console.log(``"a.a result=${result}"``, result);``return` `result;``};` `var b` `=` `Java.use(``"com.a.easyjava.b"``);``b[``"a"``].overload(``'java.lang.String'``).implementation` `=` `function (``str``) {``console.log(``"b.a is called: str=${str}"``,` `str``);``var result` `=` `this[``"a"``](``str``);``console.log(``"b.a result=${result}"``, result);``return` `result;``};``})``}` `function main() {``hook_java()``}` `setImmediate(main)` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_8MZAVJ24A2XHHHA.webp)
拿到值之后，我们先分析下：
输入abced
b方法: a 9、b 8、c 7、e 1、d 21
a方法：9 h、8 w、7 x、1 v、21 a
用python 还b方法验证：

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950 | `class` `B:``a` `=` `[]``b` `=` `"abcdefghijklmnopqrstuvwxyz"``d` `=` `0` `c` `=` `[``8``,` `25``,` `17``,` `23``,` `7``,` `22``,` `1``,` `16``,` `6``,` `9``,` `21``,` `0``,` `15``,` `5``,` `10``,` `18``,` `2``,` `24``,` `4``,` `11``,` `3``,` `14``,` `19``,` `12``,` `20``,` `13``]` `def` `__init__(``self``, num):``for` `value` `in` `self``.c[num:]:``self``.a.append(value)``for` `value` `in` `self``.c[:num]:``self``.a.append(value)``self``.a` `=` `self``.a[:``len``(``self``.c)``-``1``]``print``(``self``.a)``@staticmethod``def` `process_input():``global` `b, d``value` `=` `B.a[``0``]``B.a.pop(``0``)``B.a.append(value)``b` `+``=` `b[``0``]``b` `=` `b[``1``:``27``]``d` `+``=` `1` `def` `process_string(``self``, string):``i` `=` `0``if` `string.lower()` `in` `b:``value` `=` `b.index(string.lower())``for` `i2` `in` `range``(``len``(``self``.a)` `-` `1``):``if` `self``.a[i2]` `=``=` `value:``i` `=` `i2``else``:``i` `=` `-``10` `if` `" "` `in` `string` `else` `-``1``B.process_input()``return` `i` `def` `get_d(``self``):``return` `d` `# 示例用法：``b` `=` `"abcdefghijklmnopqrstuvwxyz"``d` `=` `0``q` `=` `2``jiami_str` `=` `"abced"``for` `jstr` `in` `jiami_str:``print``(``"jstr "``,jstr)``obj` `=` `B(q)``result` `=` `obj.process_string(jstr)``print``(result)` `# 示例返回：2``q` `=` `q` `+``1` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_A8SWXK3GCD5HUVB.webp)
和hook的值一样 没有问题。
再还原a方法进行验证：

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647 | `class` `A:``a` `=` `[]``b` `=` `"abcdefghijklmnopqrstuvwxyz"``d` `=` `0` `c` `=` `[``7``,` `14``,` `16``,` `21``,` `4``,` `24``,` `25``,` `20``,` `5``,` `15``,` `9``,` `17``,` `6``,` `13``,` `3``,` `18``,` `12``,` `10``,` `19``,` `0``,` `22``,` `2``,` `11``,` `23``,` `1``,` `8``]` `def` `__init__(``self``, num):``for` `value` `in` `self``.c[num:]:``self``.a.append(value)``for` `value` `in` `self``.c[:num]:``self``.a.append(value)` `@staticmethod``def` `process_input():``global` `d``d` `+``=` `1``if` `d` `=``=` `25``:``value` `=` `A.a[``0``]``A.a.pop(``0``)``A.a.append(value)``d` `=` `0` `def` `process_string(``self``, num):``num2` `=` `0``if` `num` `=``=` `-``10``:``A.process_input()``return` `" "``for` `i` `in` `range``(``len``(``self``.a)` `-` `1``):``if` `self``.a[i]` `=``=` `num:``num2` `=` `i``A.process_input()``return` `self``.b[num2]`  `# 示例用法：``a` `=` `"abcdefghijklmnopqrstuvwxyz"``d` `=` `0` `obj` `=` `A(``3``)``num_str` `=` `[``9``,``8``,``7``,``1``,``21``]``for` `n` `in` `num_str:``print``(``"输入值："``,n)``result` `=` `obj.process_string(n)``print``(result)` `# 示例返回：c``print``(``"----------------------------"``)``obj.process_string(``-``10``)` `# 示例返回：' '` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_3CZAYZZJWPR32MS.webp)
和hook的值一样，说明算法还原没问题。
现在知道结果 wigwrkaugala 进行反推a方法 再反推 b方法。
反推的算法如下：先输入我们之前输入的abced 将得到结果 hwxva 输入其中，看看能不能得到 abced :

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445 | `def` `a(a_str):``index_str` `=` `"abcdefghijklmnopqrstuvwxyz"``index_list` `=` `[``21``,` `4``,` `24``,` `25``,` `20``,` `5``,` `15``,` `9``,` `17``,` `6``,` `13``,` `3``,` `18``,` `12``,` `10``,` `19``,` `0``,` `22``,` `2``,` `11``,` `23``,` `1``,` `8``,` `7``,` `14``,` `16``]``index` `=` `0``i` `=` `0``for` `a` `in` `index_str:``if` `a` `=``=` `a_str:``index` `=` `i``break``i` `=` `i` `+` `1``return_num` `=` `index_list[index]``return` `return_num`  `def` `b(b_num, index_list, index_str):``print``(index_list,index_str)``print``(index_list[b_num``-``1``])``print``(index_str[index_list[b_num]])``index_b_str` `=` `index_str[index_list[b_num``-``1``]]``return` `index_b_str`  `a_strs` `=` `"hwxva"``a_num_list` `=` `[]``for` `a_s` `in` `a_strs:``a_num` `=` `a(a_s)``a_num_list.append(a_num)``print``(a_num_list)` `# [9, 8, 7, 1, 21]` `index_str` `=` `"abcdefghijklmnopqrstuvwxyz"``index_list` `=` `[``23``,` `7``,` `22``,` `1``,` `16``,` `6``,` `9``,` `21``,` `0``,` `15``,` `5``,` `10``,` `18``,` `2``,` `24``,` `4``,` `11``,` `3``,` `14``,` `19``,` `12``,` `20``,` `13``,` `8``,` `25``,` `17``]``i` `=` `0``input_str` `=` `[]``for` `b_n` `in` `a_num_list:``index_list_new` `=` `[]``for` `value` `in` `index_list[i:]:``index_list_new.append(value)``for` `value` `in` `index_list[:i]:``index_list_new.append(value)` `input_str.append(b(b_n, index_list_new, index_str))``index_str` `+``=` `index_str[``0``]``index_str` `=` `index_str[``1``:``27``]``i` `=` `i` `+` `1``print``(input_str)` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_PUEYTEEA7FP32US.webp)
反推算法没问题，我们再输入输入：wigwrkaugala 得到：['v', 'e', 'n', 'i', 'v', 'i', 'd', 'i', 'v', 'k', 'c', 'r']
flag : flag{venividivkcr} APP验证成功

### 0x04 easy_jni

这题是java层和so层相结合的算法逆向，但从代码上看，逻辑还是很清晰的。如果认真分析过easy_apk这个项目，很容易看出，他就是一个base64的换表算法。我们同样采用2种解题的方法。不过以后如果遇到类似的，直接采用第二种方法就行。先来看代码：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_AG73BU3Z39HHAFN.webp)
hook a()方法，方便后面进行验证：

| 1234567891011121314151617 | `function hook_jni() {``Java.perform(function () {``var a` `=` `Java.use(``"com.a.easyjni.a"``);``a[``"a"``].implementation` `=` `function (bArr) {``console.log(``"a.a is called: bArr=${bArr}"``, bArr);``var result` `=` `this[``"a"``](bArr);``console.log(``"a.a result=${result}"``, result);``return` `result;``};``})``}` `function main() {``hook_jni()``}` `setImmediate(main)` |
|-|-|

输入：abcdefgabcdefgabcdefgab 结果：2eXTQS8AQC7I2CntQAkO2A1/QeQx2eG=
输入的字符串经过 a(byte[] bArr) 加密后，带入so里面经过处理，剩下逻辑在so里面，我们来看so里面的代码：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_R6MXFT7HKJHJUP3.webp)

对于这段代码我们分析下：
这个函数的主要逻辑是对字符串进行一系列处理，包括颠倒、移位等操作，然后将结果与预定义字符串进行比较。如果最终处理后的字符串与预定义字符串相等，函数返回 true；否则，返回 false。

根据so的代码逻辑，我们还原她的正向和逆向算法：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546 | `def` `ncheck(v5):``if` `len``(v5)` `=``=` `32``:``v12` `=` `[``0``]` `*` `32` `for` `i` `in` `range``(``16``):``v7` `=` `v12[i]``v12[i]` `=` `v5[i` `+` `16``]``v8` `=` `v5[i]``v12[i` `+` `16``]` `=` `v8` `v9` `=` `0``while` `v9 <` `30``:``v10` `=` `v9 <` `30``v13` `=` `v12[v9]``v12[v9]` `=` `v12[v9` `+` `1``]``v12[v9` `+` `1``]` `=` `v13``v9` `+``=` `2``print``("".join(v12))``return` `"".join(v12)``else``:``return` `0`   `def` `reverse_ncheck(ciphertext):``if` `len``(ciphertext)` `=``=` `32``:``v12` `=` `[``'\x00'``]` `*` `32` `# 第一步：将逆向处理后的字符串进行逆颠倒``for` `i` `in` `range``(``16``):``v12[i]` `=` `ciphertext[i` `+` `16``]``v12[i` `+` `16``]` `=` `ciphertext[i]` `# 第二步：将处理后的字符串进行逆移位操作``v9` `=` `0``while` `v9 <` `30``:``v13` `=` `v12[v9]``v12[v9]` `=` `v12[v9` `+` `1``]``v12[v9` `+` `1``]` `=` `v13``v9` `+``=` `2` `# 输出逆向还原的字符串``reversed_result` `=` `"".join(v12)``return` `reversed_result``else``:``return` `0` |
|-|-|

解密函数reverse_ncheck(ciphertext) 带入MbT3sQgX039i3g==AQOoMQFPskB1Bsc7 得到：
QAoOQMPFks1BsB7cbM3TQsXg30i9g3==
so函数的分析到此为止。
现在来还原下，java层的a()方法：

| 123456789101112131415161718192021222324252627282930 | `class` `A:``a` `=` `[``'i'``,` `'5'``,` `'j'``,` `'L'``,` `'W'``,` `'7'``,` `'S'``,` `'0'``,` `'G'``,` `'X'``,` `'6'``,` `'u'``,` `'f'``,` `'1'``,` `'c'``,` `'v'``,` `'3'``,` `'n'``,` `'y'``,` `'4'``,` `'q'``,` `'8'``,` `'e'``,` `'s'``,` `'2'``,` `'Q'``,` `'+'``,` `'b'``,` `'d'``,` `'k'``,` `'Y'``,` `'g'``,` `'K'``,` `'O'``,` `'I'``,` `'T'``,` `'/'``,` `'t'``,` `'A'``,` `'x'``,` `'U'``,` `'r'``,` `'F'``,` `'l'``,` `'V'``,` `'P'``,` `'z'``,` `'h'``,` `'m'``,` `'o'``,` `'w'``,` `'9'``,` `'B'``,` `'H'``,` `'C'``,` `'M'``,` `'D'``,` `'p'``,` `'E'``,` `'a'``,` `'J'``,` `'R'``,` `'Z'``,` `'N'``]` `@staticmethod``def` `base64_encode(bArr):``sb` `=` `[]``for` `i` `in` `range``(``0``,` `len``(bArr),` `3``):``bArr2` `=` `[``0``]` `*` `4``b` `=` `0``for` `i2` `in` `range``(``3``):``if` `i` `+` `i2 <``=` `len``(bArr)` `-` `1``:``bArr2[i2]` `=` `b \| ((bArr[i` `+` `i2] &` `255``) >> ((i2` `*` `2``)` `+` `2``))``b` `=` `((((bArr[i` `+` `i2] &` `255``) << (((``2` `-` `i2)` `*` `2``)` `+` `2``)) &` `255``) >>` `2``)``else``:``bArr2[i2]` `=` `b``b` `=` `64``bArr2[``3``]` `=` `b``for` `i3` `in` `range``(``4``):``if` `bArr2[i3] <``=` `63``:``sb.append(A.a[bArr2[i3]])``else``:``sb.append(``'='``)` `return` `''.join(sb)`  `# 示例用法：``obj` `=` `A()``result` `=` `obj.base64_encode(b``"abcdefgabcdefgabcdefgab"``)``print``(result)` |
|-|-|

那么逆向还原这个算法：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657 | `class` `Base64New:``RANGE` `=` `255``Base64ByteToStr` `=``[``'i'``,` `'5'``,` `'j'``,` `'L'``,` `'W'``,` `'7'``,` `'S'``,` `'0'``,` `'G'``,` `'X'``,` `'6'``,` `'u'``,` `'f'``,` `'1'``,` `'c'``,` `'v'``,` `'3'``,` `'n'``,` `'y'``,` `'4'``,` `'q'``,` `'8'``,` `'e'``,` `'s'``,` `'2'``,` `'Q'``,` `'+'``,` `'b'``,` `'d'``,` `'k'``,` `'Y'``,` `'g'``,` `'K'``,` `'O'``,` `'I'``,` `'T'``,` `'/'``,` `'t'``,` `'A'``,` `'x'``,` `'U'``,` `'r'``,` `'F'``,` `'l'``,` `'V'``,` `'P'``,` `'z'``,` `'h'``,` `'m'``,` `'o'``,` `'w'``,` `'9'``,` `'B'``,` `'H'``,` `'C'``,` `'M'``,` `'D'``,` `'p'``,` `'E'``,` `'a'``,` `'J'``,` `'R'``,` `'Z'``,` `'N'``]` `StrToBase64Byte` `=` `{char: idx` `for` `idx, char` `in` `enumerate``(Base64ByteToStr)}` `def` `Base64Encode(``self``, bytes):``res` `=` `[]``for` `i` `in` `range``(``0``,` `len``(bytes),` `3``):``enBytes` `=` `[``0``]` `*` `4``tmp` `=` `0``for` `k` `in` `range``(``3``):``if` `i` `+` `k <` `len``(bytes):``enBytes[k]` `=` `((bytes[i` `+` `k] &` `255``) >> ((k` `*` `2``)` `+` `2``)) \| tmp``tmp` `=` `(((bytes[i` `+` `k] &` `255``) << ((``2` `-` `k)` `*` `2` `+` `2``)) &` `255``) >>` `2``else``:``enBytes[k]` `=` `tmp``tmp` `=` `64``enBytes[``3``]` `=` `tmp``for` `k2` `in` `range``(``4``):``if` `enBytes[k2] <``=` `63``:``res.append(``self``.Base64ByteToStr[enBytes[k2]])``else``:``res.append(``'='``)` `return` `''.join(res)` `def` `Base64Decode(``self``, encoded_str):``decoded_bytes` `=` `bytearray()` `for` `i` `in` `range``(``0``,` `len``(encoded_str),` `4``):``enChars` `=` `encoded_str[i:i` `+` `4``]``deBytes` `=` `[``0``]` `*` `4` `for` `k` `in` `range``(``4``):``if` `enChars[k] !``=` `'='``:``deBytes[k]` `=` `self``.StrToBase64Byte[enChars[k]]` `decoded_bytes.extend((((deBytes[``0``] <<` `2``) &` `255``) \| (deBytes[``1``] >>` `4``)).to_bytes(``1``,` `'big'``))` `if` `enChars[``2``] !``=` `'='` `and` `len``(enChars) >` `2``:``decoded_bytes.extend((((deBytes[``1``] <<` `4``) &` `255``) \| (deBytes[``2``] >>` `2``)).to_bytes(``1``,` `'big'``))` `if` `enChars[``3``] !``=` `'='` `and` `len``(enChars) >` `3``:``decoded_bytes.extend((((deBytes[``2``] <<` `6``) &` `255``) \| deBytes[``3``]).to_bytes(``1``,` `'big'``))` `return` `decoded_bytes`  `# 示例用法:``data_to_encode` `=` `b``'abcdefgabcdefgabcdefgab'``base64_encoder` `=` `Base64New()``encoded_data` `=` `base64_encoder.Base64Encode(data_to_encode)``print``(``"编码结果:"``, encoded_data)` `decoded_data` `=` `base64_encoder.Base64Decode(encoded_data)``print``(``"解码结果:"``, decoded_data)` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_Q4M99AAB558K2V9.webp)
算法加解密验证没问题。
将QAoOQMPFks1BsB7cbM3TQsXg30i9g3== 带入解密函数中，得到结果：flag{just_ANot#er_@p3}

### 0x05 easy_so

这题的整体逻辑并不复制，加密算法主要在so里面，读懂代码，并能推导出来，这个很重要。接下来我们详细的分析，先来看代码：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_4V47R3CD3KZG4RT.webp)
java层的代码逻辑非常清晰，就是验证输入值在so里面的检测，来看so代码：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_GV9A4QZQ4G963Q5.webp)
1.首先获取字符串的长度 v4，然后根据长度动态分配内存。这里使用了 malloc 函数，它会分配 v6 个字节的内存空间，并将其起始地址存储在 v7 中
2.将字符串 v3 的内容复制到动态分配的内存中。首先判断内存是否足够，如果不够则进行相应的内存清零操作。然后使用 memcpy 将字符串复制到动态分配的内存中
3.对字符串的每两个字符进行交换，即将字符串的第一个字符与第二个字符、第三个字符与第四个字符交换位置
4.对字符串进行了更多的字符交换操作，将第一个字符与第二个字符交换，然后每两个字符交换一次，直到字符串末尾
5.return strcmp(v8, "f72c5a36569418a20907b55be5bf95ad") == 0最后，通过 strcmp 函数比较经过处理的字符串 v8 是否与固定字符串 "f72c5a36569418a20907b55be5bf95ad" 相等，如果相等则返回 0，表示字符串相等。
算法还原：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960 | `def` `TestDec(a1):``v2` `=` `0` `if` `len``(a1) >``=` `2``:``while` `v2 <` `len``(a1)` `/``/` `2``:``a1[v2], a1[v2` `+` `16``]` `=` `a1[v2` `+` `16``], a1[v2]``v2` `+``=` `1` `result` `=` `ord``(a1[``0``])` `if` `a1` `else` `0` `if` `a1:``a1[``0``], a1[``1``]` `=` `a1[``1``],` `chr``(result)``result` `=` `len``(a1)` `if` `result >``=` `3``:``v6` `=` `0` `while` `v6` `+` `4` `<``=` `result:``a1[v6` `+` `2``], a1[v6` `+` `3``]` `=` `a1[v6` `+` `3``], a1[v6` `+` `2``]``v6` `+``=` `2` `return` `a1`   `def` `reverse_TestDec(encrypted_str):``a1` `=` `list``(encrypted_str)` `v2` `=` `0` `if` `len``(a1) >``=` `2``:``while` `v2 <` `len``(a1)` `/``/` `2``:``a1[v2], a1[v2` `+` `16``]` `=` `a1[v2` `+` `16``], a1[v2]``v2` `+``=` `1` `result` `=` `len``(a1)` `if` `result >``=` `3``:``v6` `=` `result` `-` `4` `while` `v6 >``=` `0``:``a1[v6` `+` `2``], a1[v6` `+` `3``]` `=` `a1[v6` `+` `3``], a1[v6` `+` `2``]``v6` `-``=` `2` `if` `result >` `0``:``a1[``0``], a1[``1``]` `=` `a1[``1``],` `chr``(``ord``(a1[``0``]))` `return` `"".join(a1)` `# Example usage:``original_str` `=` `"f72c5a36569418a20907b55be5bf95ad"``encrypted_result` `=` `TestDec(``list``(original_str))``print``(encrypted_result)``encrypted_result` `=` `list``(``"f72c5a36569418a20907b55be5bf95ad"``)``print``(encrypted_result)``decrypted_str` `=` `reverse_TestDec(encrypted_result)` `print``(``"Original String:"``, original_str)``print``(``"Encrypted Result:"``, "".join(encrypted_result))``print``(``"Decrypted String:"``, decrypted_str)` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/961239_N5HVYDSG7ZF57A2.webp)

90705bb55efb59da7fc2a5636549812a 验证成功

上传的附件：
- easy_apk.apk

（1.50MB，19次下载）
- easy_java.apk

（776.95kb，17次下载）
- easy_jni.apk

（782.20kb，17次下载）
- easy_SO.apk

（1.49MB，16次下载）

---

# 回复

## 回复 by 秋狝 (#2)

*2023-12-28 09:13*

感谢分享

## 回复 by mb_ldbucrik (#3)

*2023-12-28 10:17*

感谢分享

## 回复 by 你瞒我瞒 (#4)

*2023-12-28 17:52*

感谢分享

## 回复 by 小旺不正经 (#5)

*2023-12-29 08:25*

顶一下
