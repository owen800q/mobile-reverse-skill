---
title: '[原创]owasp level1-level3'
url: https://bbs.kanxue.com/thread-279335.htm
tid: 279335
author: 4Chan
date: '2023-10-24'
tags: [Android安全, 原创, 基础理论, 逆向分析, NDK分析, 协议分析, 程序开发, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T14:37:21+08:00'
replies: 6
---

# OWASP 实战

这篇文章详细介绍了解决OWASP人员（Bernhard Mueller）发布的Android `crackme`程序(owasp uncrackable)的几种方法。

### 题目链接

链接：<https://pan.baidu.com/s/1VJ7Y3psWoSi5NnlOpaohEw>
提取码：1234

### owasp uncrackable 安全机制

>
> 在`owasp uncrackable` 能够找到的安全机制:
>
>
> 1. `Java` 反调试
> 2. `Java` 完整性校验(`CRC`)
> 3. `java Root` 检测
> 4. `Native` 层的反调试
>
>
>

### 使用到的工具

Java层的反编译工具(`Dalvik bytecode`)：

- Jadx-gui.
- JEB.

`So层`反编译程序:

- IDA Pro

动态二进制检测框架:

- Frida.

编译工具

- vscode

# owasp level1

使用`Jadx`反编译工具打开`apk`如下所示

来到`MainActivity`入口

![image-20231024105859256](https://bbs.kanxue.com/upload/attach/202310/940967_KG3S6RGA7792U9D.png)

猜测会有`root`权限的检测工具,顺着这个猜测，我们可以有两种思路解决这个`root`检测

>
> 1. 动态调试`smail`代码，修改代码绕过`root`检测
> 2. 使用`frida` `hook`绕过
>
>
>

继续往下看

![image-20231024105911197](https://bbs.kanxue.com/upload/attach/202310/940967_NCF6J7Q4TZMEFTB.png)

| 123456789101112131415161718192021222324 | `public` `void` `verify(View view) {``String str;``//获取输入框的字符串``String obj = ((EditText) findViewById(R.id.edit_text)).getText().toString();``AlertDialog create =` `new` `AlertDialog.Builder(``this``).create();``//我们需要进入的地方``if` `(a.a(obj)) {``create.setTitle(``"Success!"``);``str =` `"This is the correct secret."``;``}` `else` `{``create.setTitle(``"Nope..."``);``str =` `"That's not it. Try again."``;``}``create.setMessage(str);``// 设置对话框的按钮``create.setButton(-``3``,` `"OK"``,` `new` `DialogInterface.OnClickListener() {` `// from class: sg.vantagepoint.uncrackable1.MainActivity.2``@Override` `// android.content.DialogInterface.OnClickListener``public` `void` `onClick(DialogInterface dialogInterface,` `int` `i) {``dialogInterface.dismiss();``}``});``// 显示对话框``create.show();``}` |
|-|-|

我们进入`a`类

![image-20231024105925372](https://bbs.kanxue.com/upload/attach/202310/940967_5CBMVTAS43Y9BUT.png)

进入后,内容如下

![image-20231024105932772](https://bbs.kanxue.com/upload/attach/202310/940967_5U4VGAB785BFJ8U.png)

| 123456789101112131415161718192021222324252627 | `public` `class` `a {``// 判断字符串是否与加密后的字符串相等``public` `static` `boolean` `a(String str) {``byte``[] bArr;``byte``[] bArr2 =` `new` `byte``[``0``];``try` `{``// 对字符串进行AES解密``bArr = sg.vantagepoint.a.a.a(b(``"8d127684cbc37c17616d806cf50473cc"``), Base64.decode(``"5UJiFctbmgbDoLXmpL12mkno8HT4Lv8dlat8FxR2GOc="``,` `0``));``}` `catch` `(Exception e) {``// 打印AES解密错误信息``Log.d(``"CodeCheck"``,` `"AES error:"` `+ e.getMessage());``bArr = bArr2;``}``// 判断解密后的字符串与给定字符串是否相等``return` `str.equals(``new` `String(bArr));``}``// 将字符串转换为字节数组``public` `static` `byte``[] b(String str) {``int` `length = str.length();``byte``[] bArr =` `new` `byte``[length /` `2``];``for` `(``int` `i =` `0``; i < length; i +=` `2``) {``// 将字符串中的每两个字符转换为对应的字节``bArr[i /` `2``] = (``byte``) ((Character.digit(str.charAt(i),` `16``) <<` `4``) + Character.digit(str.charAt(i +` `1``),` `16``));``}``return` `bArr;``}``}` |
|-|-|

经过观察，发现如果成功返回`equals`(`true`)，就能`suceeful`，由于没有涉及到`so`层(没看到`native`),所以我们直接在`Java`层进行代码分析

1. `Base64`解密字节数组

![image-20231024105952256](https://bbs.kanxue.com/upload/attach/202310/940967_23YYZQBKDPRB8H8.png)

手写一下伪代码

java

| 123456789 | `public` `static` `byte``[] getdecode(String word){``byte``[] base64decodedBytes = Base64.getDecoder().decode(word);``byte``[] newbase64decodedBytes =Base64.getDecoder().decode(word);``String strcode =` `new` `String(newbase64decodedBytes);``System.out.println(strcode);``System.out.println(newbase64decodedBytes);` `return` `base64decodedBytes;``}` |
|-|-|

js实现上述`java`函数

| 12345678 | `getBase64decode =` `function` `(){``var` `encode =` `"5UJiFctbmgbDoLXmpL12mkno8HT4Lv8dlat8FxR2GOc="``;``let decrypted = atob(encode);``//转成字节数组``let base64decodedBytes =` `new` `Uint8Array(atob(encode).split(``''``).map((char) => char.charCodeAt(0)));``return` `base64decodedBytes;` `}` |
|-|-|

2. 对字符串"`8d127684cbc37c17616d806cf50473cc`" 使用`sg.vantagepoint.a.a.a` 进行处理

![image-20231024110009106](https://bbs.kanxue.com/upload/attach/202310/940967_QE7GHHMYRUAD6AK.png)

java

| 12345678 | `public` `static` `byte``[] b(String str) {``int` `length = str.length();``byte``[] bArr =` `new` `byte``[length /` `2``];``for` `(``int` `i =` `0``; i < length; i +=` `2``) {``bArr[i /` `2``] = (``byte``) ((Character.digit(str.charAt(i),` `16``) <<` `4``) + Character.digit(str.charAt(i +` `1``),` `16``));``}``return` `bArr;``}` |
|-|-|

使用`js`完成`java`的功能

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051 | `const byte = (x) => ((((x \| 0) & 0xff) + 128) % 256) - 128;``//判断是否大小写``Judgment_capitalization =` `function` `(input){``if` `(` `'A'``<=input &&input <=``'Z'``){``return` `true``;``}``else``return` `false``;``}``//判断是否小写``Determine_whether_to_lower  =` `function` `(input){``if` `(` `'a'``<=input &&input <=``'z'``){``return` `true``;``}``else``return` `false``;``}``digit =` `function` `(input,radis) {` `try` `{``if` `(!isNaN(parseInt(input))) {``if` `(parseInt(input) < 10 && parseInt(input) > -1) {``return` `parseInt(input) < parseInt(radis) ? parseInt(input) : -1;``}``}``}` `catch` `(err) {``}``try` `{``if` `(Judgment_capitalization(input)) {``return` `input.charCodeAt(0) < radis +` `'A'``.charCodeAt(0) - 10 ? input.charCodeAt(0) -` `'A'``.charCodeAt(0) + 10 : -1;``}``}` `catch` `(err) {` `}``try` `{``if` `(Determine_whether_to_lower(input)) {``return` `input.charCodeAt(0) < radis +` `'a'``.charCodeAt(0) - 10 ? input.charCodeAt(0) -` `'a'``.charCodeAt(0) + 10 : -1;``}``}` `catch` `(err) {``}` `}``b =` `function` `(paramString){``var` `nlength  = paramString.length;``//直接使用intarrybuffer``var` `arrofByte =` `new` `Int8Array(nlength/2);``for``(``var` `i=0;i<nlength;i+=2){``arrofByte[i/2] = (byte)(((digit(paramString.charAt(i),16)<<4)+digit(paramString.charAt(i+1),16)));``}``return` `(arrofByte);``}` |
|-|-|

3. 查看外层函数直接`sg.vantagepoint.a`,点击进入
![image-20231024110034117](https://bbs.kanxue.com/upload/attach/202310/940967_R5TQYGPTPR3VC82.png)

类如下

| 12345678 | `public class a {``public static byte[] a(byte[] bArr, byte[] bArr2) {``SecretKeySpec secretKeySpec =` `new` `SecretKeySpec(bArr,` `"AES/ECB/PKCS7Padding"``);``Cipher cipher = Cipher.getInstance(``"AES"``);``cipher.init(2, secretKeySpec);``return` `cipher.doFinal(bArr2);``}``}` |
|-|-|

这个时候，我们综合之前的分析

可以写出`java`脚本

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667 | `import org.bouncycastle.jce.provider.BouncyCastleProvider;``import javax.crypto.Cipher;``import javax.crypto.spec.SecretKeySpec;``import java.nio.charset.StandardCharsets;``import java.security.Security;``import java.util.Base64;` `public class AES128ECBwithPKCS7 {` `private static final String SECRET =` `"AES"``;``private static final String CIPHER_ALGORITHM =` `"AES/ECB/PKCS7Padding"``;` `// Decrypts the given byte array using AES 128 ECB with PKCS7 padding``public static String newaes256ECBPkcs7PaddingDecrypt(byte[] bArr, byte[] bArr2) throws Exception {``String strbrr =` `new` `String(bArr);``String strbrr2 =` `new` `String(bArr2);` `// Create a new instance of the Cipher class with the specified algorithm``Cipher cipher = Cipher.getInstance(CIPHER_ALGORITHM);` `// Initialize the cipher in decryption mode with the secret key``cipher.init(Cipher.DECRYPT_MODE,` `new` `SecretKeySpec(bArr, SECRET));` `// Perform the decryption operation``byte[] doFinal = cipher.doFinal(bArr2);` `// Convert the decrypted byte array to a string and return it``return` `new` `String(doFinal);``}` `// Converts a hexadecimal string to a byte array``public static byte[] b(String str) {``int length = str.length();``byte[] bArr =` `new` `byte[length / 2];` `// Iterate over the hexadecimal string and convert each pair of characters to a byte``for` `(int i = 0; i < length; i += 2) {``bArr[i / 2] = (byte) ((Character.digit(str.charAt(i), 16) << 4) + Character.digit(str.charAt(i + 1), 16));``}` `// Print the byte array``System.out.println(bArr);` `return` `bArr;``}` `// Decodes a Base64-encoded string and returns the decoded byte array``public static byte[] getdecode(String word) {``byte[] base64decodedBytes = Base64.getDecoder().decode(word);``byte[] newbase64decodedBytes = Base64.getDecoder().decode(word);``String strcode =` `new` `String(newbase64decodedBytes);` `// Print the decoded string and byte array``System.out.println(strcode);``System.out.println(newbase64decodedBytes);` `return` `base64decodedBytes;``}` `public static void main(String[] args) throws Exception {``// Decrypt the given text using AES 128 ECB with PKCS7 padding``String text = newaes256ECBPkcs7PaddingDecrypt(b(``"8d127684cbc37c17616d806cf50473cc"``), getdecode(``"5UJiFctbmgbDoLXmpL12mkno8HT4Lv8dlat8FxR2GOc="``));` `// Print the decrypted text``System.out.println(text);``}``}` |
|-|-|

`js`脚本

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161 | `const CryptoJS = require(``'crypto-js'``)` `//转化为byte``const base = require(``"./Crypted/Base64"``);``const byte = (x) => ((((x \| 0) & 0xff) + 128) % 256) - 128;` `//判断是否大小写``Judgment_capitalization =` `function` `(input){``if` `(` `'A'``<=input &&input <=``'Z'``){``return` `true``;``}``else``return` `false``;``}` `//判断是否小写``Determine_whether_to_lower  =` `function` `(input){``if` `(` `'a'``<=input &&input <=``'z'``){``return` `true``;``}``else``return` `false``;` `}` `digit =` `function` `(input,radis) {` `try` `{``if` `(!isNaN(parseInt(input))) {``if` `(parseInt(input) < 10 && parseInt(input) > -1) {``return` `parseInt(input) < parseInt(radis) ? parseInt(input) : -1;``}``}` `}` `catch` `(err) {``}``try` `{``if` `(Judgment_capitalization(input)) {``return` `input.charCodeAt(0) < radis +` `'A'``.charCodeAt(0) - 10 ? input.charCodeAt(0) -` `'A'``.charCodeAt(0) + 10 : -1;``}``}` `catch` `(err) {` `}``try` `{``if` `(Determine_whether_to_lower(input)) {``return` `input.charCodeAt(0) < radis +` `'a'``.charCodeAt(0) - 10 ? input.charCodeAt(0) -` `'a'``.charCodeAt(0) + 10 : -1;``}``}` `catch` `(err) {``}` `}``b =` `function` `(paramString){``var` `nlength  = paramString.length;``//直接使用intarrybuffer``var` `arrofByte =` `new` `Int8Array(nlength/2);``for``(``var` `i=0;i<nlength;i+=2){``arrofByte[i/2] = (byte)(((digit(paramString.charAt(i),16)<<4)+digit(paramString.charAt(i+1),16)));``}``return` `(arrofByte);``}` `/**``*@description:将string转为UTF-8格式signed char字节数组``*``*/``function` `byteToString(arr) {``if``(``typeof` `arr ===` `'string'``) {``return` `arr;``}``var` `str =` `''``,``_arr = arr;``for``(``var` `i = 0; i < _arr.length; i++) {``var` `one = _arr[i].toString(2),``v = one.match(/^1+?(?=0)/);``if``(v && one.length == 8) {``var` `bytesLength = v[0].length;``var` `store = _arr[i].toString(2).slice(7 - bytesLength);``for``(``var` `st = 1; st < bytesLength; st++) {``store += _arr[st + i].toString(2).slice(2);``}``str += String.fromCharCode(parseInt(store, 2));``i += bytesLength - 1;``}` `else` `{``str += String.fromCharCode(_arr[i]);``}``}``return` `str;``}`  `//网络传输``function` `stringToByte(str) {``var` `len, c;``len = str.length;``var` `bytes = [];``for``(``var` `i = 0; i < len; i++) {``c = str.charCodeAt(i);``if``(c >= 0x010000 && c <= 0x10FFFF) {``bytes.push(((c >> 18) & 0x07) \| 0xF0);``bytes.push(((c >> 12) & 0x3F) \| 0x80);``bytes.push(((c >> 6) & 0x3F) \| 0x80);``bytes.push((c & 0x3F) \| 0x80);``}` `else` `if``(c >= 0x000800 && c <= 0x00FFFF) {``bytes.push(((c >> 12) & 0x0F) \| 0xE0);``bytes.push(((c >> 6) & 0x3F) \| 0x80);``bytes.push((c & 0x3F) \| 0x80);``}` `else` `if``(c >= 0x000080 && c <= 0x0007FF) {``bytes.push(((c >> 6) & 0x1F) \| 0xC0);``bytes.push((c & 0x3F) \| 0x80);``}` `else` `{``bytes.push(c & 0xFF);``}``}``return` `new` `Int8Array(bytes);``}``getBase64decode =` `function` `(){`  `var` `encode =` `"5UJiFctbmgbDoLXmpL12mkno8HT4Lv8dlat8FxR2GOc="``;``let decrypted = atob(encode);``let base64decodedBytes =` `new` `Int8Array(atob(encode).split(``''``).map((char) => char.charCodeAt(0)));``// var bytedecode = new Int8Array(100)``// bytedecode =stringToByte(decrypted);``const  strbrr = String.fromCharCode.apply(``null``,base64decodedBytes);` `console.log(strbrr);``return` `base64decodedBytes;` `}`  `//AES_ECB模式解密``deCryptedByAes_ECB =` `function` `(data,AESkey){``var`  `strdata = byteToString(data);``var` `strAESKey = byteToString(AESkey)``var` `key = CryptoJS.enc.Utf8.parse(AESkey);``var` `decrypt = CryptoJS.AES.decrypt(data, key, {``mode: CryptoJS.mode.ECB,``padding: CryptoJS.pad.Pkcs7,``});``return` `CryptoJS.enc.Utf8.stringify(decrypt).toString();``把加密的内容和秘钥转化为wordarry对象``// const encryptedwordarry = CryptoJS.enc.Hex.parse(data.join(''));``// const keywordArry = CryptoJS.enc.Utf8.parse(AESkey.join(''));``// //解密``// const decrypted = CryptoJS.AES.decrypt(``//     {ciphertext:encryptedwordarry},``//     keywordArry,{mode:CryptoJS.mode.ECB,padding:CryptoJS.pad.Pkcs7}``// )``// return decrypted.toString(CryptoJS.enc.Utf8);` `}` `const  str = byteToString(b(``"8d127684cbc37c17616d806cf50473cc"``))` `gettext =` `function` `() {``var` `text = deCryptedByAes_ECB(b(``"8d127684cbc37c17616d806cf50473cc"``),getBase64decode(``"5UJiFctbmgbDoLXmpL12mkno8HT4Lv8dlat8FxR2GOc="``))``console.log(text);``}` `console.log(gettext())` |
|-|-|

跑出的结果是
![image-20231024110050256](https://bbs.kanxue.com/upload/attach/202310/940967_EM4KJZM4YR9M5HB.png)

就是我们想要的`flag`

注意，此时并没有绕过`root`检测，就已经完成了分析过程，但为了尊重开发者，我们按照之前的两个思路进行解题

## 1.1. 使用AS动态修改smail代码进行绕过

1. 使用`Apk killer`进行反编译

![image-20231024110100715](https://bbs.kanxue.com/upload/attach/202310/940967_F6MVTT9ZA8PZ3UQ.png)

把**smali**文件丢到其他目录下，方便我们接下来使用AS导入

![image-20231024110111305](https://bbs.kanxue.com/upload/attach/202310/940967_RP62UAMFPRRD5BX.png)

丢到`H`盘，把`smail`修改该名字为`src`

![image-20231024110121550](https://bbs.kanxue.com/upload/attach/202310/940967_RS5D52T6F3ZR8GV.png)

在`AS`(`Android Studio`下面统称AS)导入`smalidea-0.06.zip`

![image-20231024110130446](https://bbs.kanxue.com/upload/attach/202310/940967_MJUUJ3TAYBZWBPD.png)

![image-20231024110137854](https://bbs.kanxue.com/upload/attach/202310/940967_3VYFMZAZUETVPFZ.png)

导入后会提示**重启**`AS`

重启`AS`,然后开始进行下面修改

![image-20231024110147513](https://bbs.kanxue.com/upload/attach/202310/940967_HCDAT4VDG9X4MPE.png)

| 1 | `file``-``>setting``-``>editor``-``>filetype `选择 `smail Files`,然后点击右上方的``+``号，输入```*``.smail` |
|-|-|

如果没有找到`smail Files` 说明在第三步(AS(`Android Studio`下面统称AS)导入`smalidea-0.06.zip`)出错，错误原因可能是当前AS的版本太低(低于`4.0`)应该使用`smalidea-0.05.zip`或者是当前`AS`版本(高于`4.0`)较高,但导入了低版本的`smalidea-0.05.zip`

新建项目,导入文件`smail`文件

![image-20231024110157275](https://bbs.kanxue.com/upload/attach/202310/940967_EGQCDBBPGG8UUDU.png)

在`Oncreate`函数下断点

![image-20231024110204244](https://bbs.kanxue.com/upload/attach/202310/940967_N5J5Y2ZU35PASV9.png)

1. 输入命令开启调试 `adb shell am start -D -n owasp.mstg.uncrackable1/sg.vantagepoint.uncrackable1.MainActivity`

| 1234 | `这是一条用于在Android设备上启动应用程序的ADB命令。具体含义如下：``● `adb shell`：通过adb连接到设备的shell终端。``● `am start`：启动ActivityManager服务，用于启动应用程序。 ●` `-``D：在启动应用程序时，将应用程序置于调试模式。``● ```-``n wasp.mstg.uncrackable1``/``sg.vantagepoint.uncrackable1.MainActivity`：指定要启动的应用程序的包名和主Activity的类名。 总体来说，这条命令的作用是以调试模式启动包名为`owasp.mstg.uncrackable1`的应用程序，并打开其`MainActivity`。` |
|-|-|

运行如下

 <img src="upload/attach/202310/940967_RFDNEHHANPPKYHD.png" alt="image-20231024110212864" style="zoom:50%;" />

1. 找到包名对应的**pid**  `adb shell ps | grep owasp.mstg.uncrackable1`

这里是`8980` 使用`adb` 命令 转发本地端口

![image-20231024110221959](https://bbs.kanxue.com/upload/attach/202310/940967_Y67VUUX86FPYPQS.png)

| 1 | `adb forward tcp:``8800` `jdwp:``8980` |
|-|-|

设置远程调试

点击右上方 `AddConfiguration ...`

![image-20231024110230719](https://bbs.kanxue.com/upload/attach/202310/940967_R2FTWCGVNCF26GN.png)

点击`Remote JVM Debug`

![image-20231024110238082](https://bbs.kanxue.com/upload/attach/202310/940967_BPGQ3UJFKS4D6EJ.png)

![image-20231024110247462](https://bbs.kanxue.com/upload/attach/202310/940967_P9376KR9RWJR69X.png)

设置端口`8800`和名字`app1`

选择设备，并开始调试

![image-20231024110256360](https://bbs.kanxue.com/upload/attach/202310/940967_JPRSYWA3BM3N9AX.png)

由于`root`检测，远程调试无法进入`OnCreated`界面，所以选择直接看`smaile`源码

![image-20231024110305138](https://bbs.kanxue.com/upload/attach/202310/940967_9JV6ME25S33YDEF.png)

思路是:直接在`smail`层绕过`Root`和`debug`检测

来到`smail`代码层需要修改~~绕过~~(`Root`函数代码)代码如下

![image-20231024110313031](https://bbs.kanxue.com/upload/attach/202310/940967_JC6VDJNK2AUVERZ.png)

修改完后使用`killer`重新编译一下

![image-20231024110322603](https://bbs.kanxue.com/upload/attach/202310/940967_74N5KK3CEBX55MC.png)

安装`apk`到手机，显示已经没有`root` 检测窗口了

![image-20231024110333005](https://bbs.kanxue.com/upload/attach/202310/940967_XJXRTMJG9JJMXZE.png)

这个时候可以开启动态调试了，如图

![image-20231024110341761](https://bbs.kanxue.com/upload/attach/202310/940967_SYQH68UAZPDDX7C.png)

按照这个思路，我们也可以直接跳转到登录成功的界面，修改的`smail`代码如下

![image-20231024110349079](https://bbs.kanxue.com/upload/attach/202310/940967_4PA7PBF7NYHV69V.png)

重新编译，无论输入什么都能成功登录

## 1.2. 使用Frida进行hook java层

没什么好说的，直接`hook`一把梭

| 12345678910111213141516171819202122232425262728293031 | `setImmediate(``function` `(){` `// 在下一个事件循环中执行以下代码` `Java.perform(``function``() {``// 重写MainActivity类中的a方法``Java.use(``"sg.vantagepoint.uncrackable1.MainActivity"``).a.implementation =` `function` `(x) {``// 注释：这里是a方法的重写实现``// this.a(x);``}` `// 获取sg.vantagepoint.a.a类的实例``var` `a = Java.use(``"sg.vantagepoint.a.a"``);` `// 重写a类中的a方法``a[``"a"``].implementation =` `function` `(bArr, bArr2) {``// 注释：这里是a方法的重写实现``console.log(``'a is called'` `+` `', '` `+` `'bArr: '` `+ bArr +` `', '` `+` `'bArr2: '` `+ bArr2);` `// 调用原始的a方法并获取返回值``var` `ret =` `this``.a(bArr, bArr2);` `// 打印返回值``console.log(``'a ret value is '` `+ ret);` `// 将返回值转换为字符串并打印``console.log(Java.use(``"java.lang.String"``).$``new``(ret));`  `// 返回原始的返回值``return` `ret;``};``})``})` |
|-|-|

![image-20231024110402301](https://bbs.kanxue.com/upload/attach/202310/940967_Z2F9RKM6TETG695.png)

# 2. owasp level2

速战速决

思路:绕过JAVA层的`root` 检测

1. 先丢`jadx`里面进行反编译

![image-20231024110410838](https://bbs.kanxue.com/upload/attach/202310/940967_7K6HERHEXKCFAYM.png)

1. `hook` `root` 检测函数(`b.a`)

右键复制`frida`代码

![image-20231024110422164](https://bbs.kanxue.com/upload/attach/202310/940967_5BXP68UMX9XRGBK.png)

把代码丢到`vscode`一把梭

使用命令`frida -U -l 11.js -f owasp.mstg.uncrackable2`

![image-20231024110434618](https://bbs.kanxue.com/upload/attach/202310/940967_269372H348HBZYJ.png)

于是我们过了`root`检测

![image-20231024110442546](https://bbs.kanxue.com/upload/attach/202310/940967_KNMFX39HT5YQATZ.png)

1. 来到`sucees!` 所在的验证(`verify`)函数位置

![image-20231024110452982](https://bbs.kanxue.com/upload/attach/202310/940967_E2NSVH7M85FWEWA.png)

在使用`JNI` 在`native`层调用了`bar`函数，直接开始在`so`分析

![image-20231024110504662](https://bbs.kanxue.com/upload/attach/202310/940967_9NEQBF88JAKBE9B.png)

1. `unzip UnCrackable-Level2.apk -d fileso`解压`apk`获取`so`

![image-20231024110515722](https://bbs.kanxue.com/upload/attach/202310/940967_5ZM5FSEVAX9VJMG.png)

把`so`丢`ida`中，然后查看左边的字符栏,输入关键字`bar`

![image-20231024110522989](https://bbs.kanxue.com/upload/attach/202310/940967_MKCF4G8ZAGDRWJM.png)

我们点进去，然后`F5`反汇编

![image-20231024110530456](https://bbs.kanxue.com/upload/attach/202310/940967_8JT5WTCKJF3EVXX.png)

`flag` 直接出来

flag：`Thanks for all the fish`

# 3. owasp level3

题目难度变大

## 3.1. JAVA层

 把`apk`丢到`JADX-GUI`查看`MainActivity`界面

![image-20231024110541120](https://bbs.kanxue.com/upload/attach/202310/940967_DTX43D922YZQ5H2.png)

简化一下界面如下

| 1234567891011121314151617181920212223242526272829303132333435363738394041 | `/* loaded from: classes.dex */``public class MainActivity extends AppCompatActivity {``private static final String TAG =` `"UnCrackable3"``;``static int tampered = 0;``private static final String xorkey =` `"pizzapizzapizzapizzapizz"``;``private native long baz();``private native void init(byte[] bArr);` `/* JADX INFO: Access modifiers changed from: private */``public void showDialog(String str) {``}` `private void verifyLibs() {``}` `/* JADX INFO: Access modifiers changed from: protected */``/* JADX WARN: Type inference failed for: r0v2, types: [sg.vantagepoint.uncrackable3.MainActivity$2] */``@Override` `// android.support.v7.app.AppCompatActivity, android.support.v4.app.FragmentActivity, android.support.v4.app.SupportActivity, android.app.Activity``public void onCreate(Bundle bundle) {``verifyLibs();``init(xorkey.getBytes());``super``.onCreate(bundle);``setContentView(owasp.mstg.uncrackable3.R.layout.activity_main);``}` `public void verify(View view) {``String obj = ((EditText) findViewById(owasp.mstg.uncrackable3.R.id.edit_text)).getText().toString();``AlertDialog create =` `new` `AlertDialog.Builder(``this``).create();``if` `(``this``.check.check_code(obj)) {``create.setTitle(``"Success!"``);``create.setMessage(``"This is the correct secret."``);``}` `else` `{``create.setTitle(``"Nope..."``);``create.setMessage(``"That's not it. Try again."``);``}``}` `static {``System.loadLibrary(``"foo"``);``}``}` |
|-|-|

得到的信息

1. 两个常量`"pizzapizzapizzapizzapizz"`和`"UnCrackable3"`
2. 两个`native`层的调用`baz`和`init`(通过JNI调用会把字节数组"`pizzapizzapizzapizzapizz`",发送到`native`层)
3. `CRC`校验（注意，没有加密对app进行签名）

由于`CRC`校验和比较弱，我们也许能通过修改反编译得到的函数和`native`层中的函数，直接绕过所有安全的检测

三个检测`root`函数来检测设备是否可能存在`root`权限

![image-20231024115227008](https://bbs.kanxue.com/upload/attach/202310/940967_JE9U5DPA5BJBW7Y.png)

![image-20231024110555164](https://bbs.kanxue.com/upload/attach/202310/940967_7X5MXFHF625UBDS.png)

- `checkRoot1()`检查文件系统中是否存在含有`SU`内容的二进制文件来获取权限。
- `checkRoot2()`检查 的 `BUILD` 标记。检测Android版本是开发者还是官方
- `checkRoot3()`检查是否存在有`root`权限的apk

## 3.2. Native层

`unzip xxx.apk -d fileso(文件夹名)`，进行解压

丢到`ida`进行静态分析，结合`jadx`,会发现`so`层有个`init`函数对字符数组(由`private static final String xorkey = "pizzapizzapizzapizzapizz"`字符串得到字节数组）进行处理

![image-20231024110605314](https://bbs.kanxue.com/upload/attach/202310/940967_9796AE9HGAK5V45.png)

ida里面搜索`Init`

![image-20231024110615116](https://bbs.kanxue.com/upload/attach/202310/940967_GJEBE9Z9ZPGZTGK.png)

反编译一下

![image-20231024110625467](https://bbs.kanxue.com/upload/attach/202310/940967_BPG78C6BZ7TZJXV.png)

看到这里的思路是，能不能用动态`ida`调试查看一下，不过我们继续静态分析

这里介绍一下`JNI`调用`Java`方法的传参逻辑

1. 第一个参数一般是`JNIEnv`指针，它是一个指向`JNI`环境的指针，用于调用JNI函数
2. 第二个参数一般是`Java`对象或者`Java`类的引用(一般写作jClass)，用于指定要调用的Java方法所属的对象或类
3. 第二个参数一般是`Java`对象或者`Java`类的引用，用于指定要调用的Java方法所属的对象或类或者参数

用`frida`脚本演示可能更加直观一些

| 1234567891011121314151617181920 | `function` `main() {``Java.perform(``function``(){``// 下面代码指定了要Hook的文件函数名和So文件名``Interceptor.attach(Module.findExportByName(``'libfridaso.so'``,``'Java_com_example_fridaso_FridaSoDefine_FridaSo'``),{``onEnter:` `function``(args){` `//顾名思义，OnEnter就是我们进入改函数前的方法，args是传入的第一个参数，一般so层函数第一个参数都是JniENv,第二个参数是jClass，从第三个参数开始才是我们传入Java层的第三个参数``send(``'Hook Start'``);``send(``'args[2] ==>'` `+ args[2]);` `//打印我们JAVA层传入的第一个参数``send(``'arhs[3]==>'` `+args[3]);` `//打印我们JAVA层传入的第二个参数``},``// reval就是返回的值``onLeave:``function``(reval){``send(``"return:"` `+reval);``// 切割``console.log(reval);``reval.replace(0);``console.log(reval);` `}``})``})` |
|-|-|

根据上面的知识，我们`在Java_sg_vantagepoint_uncrackable3_MainActivity_init`(`init`),对传入参数的名字进行修改（选中参数，快捷键**n**）

![image-20231024110635396](https://bbs.kanxue.com/upload/attach/202310/940967_9FSHJRWNABRNSJ2.png)

因为传入的`a3`是我们在`jadx`看到的字节数组(`pizzapizzapizzapizzapizz`)

![image-20231024110646233](https://bbs.kanxue.com/upload/attach/202310/940967_W2CQUDXPJVGAMKJ.png)

所以`result`肯定和前面的字节数组(`pizzapizzapizzapizzapizz`)有关(具体情况目前不明朗)

---

思路中断不妨查看一下启动时的`so`时候的`ELF`文件，该部分执行程序启动时候的函数指针(`JNI`)

![image-20231024110656618](https://bbs.kanxue.com/upload/attach/202310/940967_6R4R7NGJRUPPFXW.png)

![image-20231024111830602](https://bbs.kanxue.com/upload/attach/202310/940967_8B5TZ6RMUPUEPXC.png)

其中的`.init_array`里面`sub_31B0`的引起了注意，点击进入

![image-20231024110705756](https://bbs.kanxue.com/upload/attach/202310/940967_GV232UCGFVQX3R2.png)

反编译

![image-20231024110715246](https://bbs.kanxue.com/upload/attach/202310/940967_X37JHEXFREE6YUR.png)

大概意思是`sub_30D0`创建了一个线程，线程调用了`sub_30D0`来里面是否有`frida`和`xpose`检测

![image-20231024110731235](https://bbs.kanxue.com/upload/attach/202310/940967_N9QQ2GK39D7CN3K.png)

绕过这个函数可以通过hook `pthread_create`来阻止进程的创建来进行绕过也可以通过`hooksub_30D0`进行绕过

在这里选择后者

这里先贴一下相关知识点

>
> linker64 是 Android 64 位系统中的动态链接器，它负责加载和链接共享库，以及解析符号引用，使得程序能够正确执行。在 Android 系统中，linker64 是一个重要的组件，它在应用程序启动时被调用，负责加载应用程序所需的共享库，并建立共享库之间的依赖关系。
>
>
> linker64 的主要功能包括：
>
>
> - 加载共享库：根据程序指定的共享库路径，加载共享库到内存中。
> - 符号解析：解析程序中对共享库的符号引用，找到符号在内存中的地址，以便正确执行程序。
> - 重定位：对共享库中的重定位表进行处理，将符号引用重定位到正确的地址。
> - 初始化：执行共享库中的 init_array 段，调用初始化函数进行必要的初始化操作。
> - 启动程序：最后，linker64 调用程序的入口函数（一般是 main 函数），启动应用程序的执行。
>
>
> 在 Android 64 位系统中，init_array 一般会被 linker64 中的 call_array 函数调用。call_array 函数负责遍历共享库中的 init_array 段，并依次执行其中的函数指针所指向的初始化函数。它会在动态链接器加载共享库时被调用，确保在程序启动时执行这些初始化函数。
>
>
>

由于反调试函数(`sub_30D0`)启动线程是在`init_array` 中,而`so`层的`init_array`都是被`linker64`中的`call_array`调用，所以我们直接去**Hook**`linker64 call_array`，在这之前需要动态调试so获得`linker64 call_array`的地址

### 3.2.1. 动态调试so获取`linker64.so call_array`的函数地址

#### 3.2.1.1. 使用adb命令打开手机上的android_server64

1. 搜索自己IDA下面的android_server64

![image-20231024110741053](https://bbs.kanxue.com/upload/attach/202310/940967_KDVKQDZCMNZTQSB.png)

1. 把android_server64使用adb push命令发送到自己的手机文件夹 /data/local/tmp下面
2. 启动android_server64

![image-20231024110751007](https://bbs.kanxue.com/upload/attach/202310/940967_XCHKZGD62GYYGX4.png)

#### 3.2.1.2. 使用WINDOWS端的IDA连接手机端

1. 打开`ida`，不要`new`新工程,直接go进去，选择Remote ARM Linux/Android debugger

![image-20231024110838726](https://bbs.kanxue.com/upload/attach/202310/940967_MAUUYSCZFDSNZV4.png)

1. 操作如下

![image-20231024110827803](https://bbs.kanxue.com/upload/attach/202310/940967_ZHCTGK5C27ET6SY.png)

点击OK

![image-20231024110845019](https://bbs.kanxue.com/upload/attach/202310/940967_6KKBMN4N83MG95K.png)

弹出一个列表框,`search`搜素`app`的包名

![image-20231024110850905](https://bbs.kanxue.com/upload/attach/202310/940967_TGUZPSZT9QMT9V3.png)

#### 3.2.1.3. 下面会有个坑

我们在右边的`Module`板块搜索我们在`IDA`之前找到的重要`call`或者so的关键字，会发现有时候根本搜索不到

![image-20231024110859179](https://bbs.kanxue.com/upload/attach/202310/940967_75Z2V4DTHFMM7HB.png)

因为没有`F9`加载

原因如下

>
> ida pro附加成功之后，会先调到其他so，比如libc.so这些，这个时候，需要先f9跳过，等没得跳之后，才需要执行jdb。
>
>
> 按`F9`加载就行
>
>
>

搜索`Module` : `linker64`

![image-20231024110904940](https://bbs.kanxue.com/upload/attach/202310/940967_NKTXZ2PGQ9RJZ7S.png)

在`Module` : `linker64` 下搜索`call_array`

![image-20231024110924940](https://bbs.kanxue.com/upload/attach/202310/940967_QFZF6TKNCAA6WXN.png)

记录一下`call_array`地址`0000007D68B58764`减去`linker64`的基地址(`7D68B38000`) =`00020764`(偏移地址)

![image-20231024110932115](https://bbs.kanxue.com/upload/attach/202310/940967_3RVRGVTUZNGMR4U.png)

开始编写`frida`的`Hook`脚本

| 1234567891011121314151617 | `// 获取linker64模块的基地址``var` `linker64_module = Module.getBaseAddress(``"linker64"``);``//使用拦截器附加linker64模块的偏移地址``// 7D68B58764 - 7D68B38000 = 0x20764``Interceptor.attach(linker64_module.add(0x20764),{``// 进入函数，代码检查参数args[3]指向的字符串是否匹配libfoo.s``onEnter:``function``(args) {``if``(args[3].readCString().match(``"libfoo.so"``)) {``// 获取libfoo.so的基地址``var` `libfoo_module  = Module.findBaseAddress(``'libfoo.so'``);``console.log(``"获取libfoo.so的基地址==>"``+libfoo_module)``Interceptor.replace(libfoo_module.add(0x30D0),``new` `NativeCallback(``function``(){``return``;``},``'void'``,[]));``}``},onLeave:``function``(result){}``})` |
|-|-|

运行之后发现仍然存在检测，继续往下分析 `native`层的`init`函数

1. 调用`sub_323C(JNIenv, JClass);`
2. 保存字符串"`pizzapizzapizzapizzapizz`"

![image-20231024110942230](https://bbs.kanxue.com/upload/attach/202310/940967_6VNEDM8Q8DXG9FU.png)

我们查看`sub_323C`的调用次数以便把握`Hook`时机(选中函数后按下`x`查看引用次数)

![image-20231024110948552](https://bbs.kanxue.com/upload/attach/202310/940967_W9SWPFPKT9F2DWB.png)

只调用了一次，由于`sub_323C`只在`init`函数中,`init`函数在`apk`启动(`oncreate`)才被调用，所以我们选择在`libfool.so`加载的时候进行`Hook`，`libfoo.so`是`apk`在`java`层调用`System.loadLibrary("foo")`进行加载，调用的底层逻辑是通过`libandroid_runtime.so`的`android_dlopen_ext`来加载的`so`

>
> 具体的调用逻辑如下：
>
>
> 1. 应用程序通过JNI接口调用libandroid_runtime.so中的android_dlopen_ext函数。
> 2. android_dlopen_ext函数接收一个参数，即libfoo.so的路径。它会根据路径加载libfoo.so动态链接库。
> 3. 在加载libfoo.so之前，android_dlopen_ext函数会检查是否已经加载过该库。如果已经加载过，则直接返回之前加载的库的句柄。
> 4. 如果libfoo.so还没有被加载过，则android_dlopen_ext函数会通过系统调用打开libfoo.so文件，并获取到动态链接库的句柄。
> 5. android_dlopen_ext函数会将libfoo.so的句柄保存在一个全局的缓存中，以便在后续的调用中能够直接使用。
> 6. android_dlopen_ext函数返回libfoo.so的句柄给应用程序。
> 7. 应用程序可以通过句柄来调用libfoo.so中的函数，实现底层逻辑。
>
>
>

需要注意的是，`android_dlopen_ext`函数是`Android Runtime`中的一个函数，用于加载动态链接库。它是通过JNI接口提供给应用程序使用的。在调用`android_dlopen_ext`函数之前，应用程序需要先加载`libandroid_runtime.so`，并通过JNI接口导入`android_dlopen_ext`函数。这样才能在`Java`层调用`android_dlopen_ext`函数，并实现加载`libfoo.so`的功能。

根据这些信息, 继续编写`Frida`脚本

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960 | `Java.perform(``function``(){``// 获取linker64模块的基地址``var` `linker64_module = Module.getBaseAddress(``"linker64"``);``//使用拦截器附加linker64模块的偏移地址``// 7D68B58764 - 7D68B38000 = 0x20764``Interceptor.attach(linker64_module.add(0x20764),{``// 进入函数，代码检查参数args[3]指向的字符串是否匹配libfoo.s``onEnter:``function``(args) {``if``(args[3].readCString().match(``"libfoo.so"``)) {``// 获取libfoo.so的基地址``var` `libfoo_module  = Module.findBaseAddress(``'libfoo.so'``);``console.log(``"获取libfoo.so的基地址==>"``+libfoo_module)``Interceptor.replace(libfoo_module.add(0x30D0),``new` `NativeCallback(``function``(){``return``;``},``'void'``,[]));``}``},onLeave:``function``(result){}``})` `// hook android_dlopen_ext``var` `libfoo_loaded_flag = 0;` `//定义一个变量用于标记是否已加载libfoo.so``// 获取libandroid_runtime.so中的android_dlopen_ext函数的地址``var` `android_dlopen_ext_addr = Module.getExportByName(``"libandroid_runtime.so"``,` `"android_dlopen_ext"``);``// 拦截android_dlopen_ext函数``Interceptor.attach(android_dlopen_ext_addr, {``// 进入android_dlopen_ext函数时执行的操作``onEnter:``function``(args){``// 判断传入的参数中是否包含"libfoo.so"的字符串``if``(-1 != args[0].readCString().indexOf(``"libfoo.so"``)){``// 如果包含，则将libfoo_loaded_flag标记为1，表示已加载libfoo.so``libfoo_loaded_flag = 1;``}``},``// 离开android_dlopen_ext函数时执行的操作``onLeave:``function``(result){``// 如果libfoo_loaded_flag为1，表示已加载libfoo.so``if``(libfoo_loaded_flag == 1){``// 通过Interceptor.replace方法替换libfoo.so中偏移为0x323C的函数``var` `libfoo_module = Module.findBaseAddress(``"libfoo.so"``);``Interceptor.replace(libfoo_module.add(0x323C),` `new` `NativeCallback(``function``(){` `console.log(``"获取反调试地址sub_323c==>"``+libfoo_module)``return``;``},` `'void'``, []));``libfoo_loaded_flag = 0;``}``}``})``// var RootDetection = Java.use("sg.vantagepoint.util.RootDetection");``// RootDetection["checkRoot1"].implementation = function () {``//   console.log('checkRoot1 is called');``//   var ret = this.checkRoot1();``//   console.log('checkRoot1 ret value is ' + ret);``//   return false;``// };` `}``)}``// 立即开始执行函数``setImmediate(main);` |
|-|-|

#### 3.2.1.4. 回到JAVA层

开始过`java`层的`root`检测

![image-20231024111001233](https://bbs.kanxue.com/upload/attach/202310/940967_FDA5P28VPGPUCXM.png)

直接选择`checkRoot1`右键获取`Frida`脚本

![image-20231024111012120](https://bbs.kanxue.com/upload/attach/202310/940967_VXU6ZGFNXS3733M.png)

添加到我们的之前的脚本上，返回`false`

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960 | `Java.perform(``function``(){``// 获取linker64模块的基地址``var` `linker64_module = Module.getBaseAddress(``"linker64"``);``//使用拦截器附加linker64模块的偏移地址``// 7D68B58764 - 7D68B38000 = 0x20764``Interceptor.attach(linker64_module.add(0x20764),{``// 进入函数，代码检查参数args[3]指向的字符串是否匹配libfoo.s``onEnter:``function``(args) {``if``(args[3].readCString().match(``"libfoo.so"``)) {``// 获取libfoo.so的基地址``var` `libfoo_module  = Module.findBaseAddress(``'libfoo.so'``);``console.log(``"获取libfoo.so的基地址==>"``+libfoo_module)``Interceptor.replace(libfoo_module.add(0x30D0),``new` `NativeCallback(``function``(){``return``;``},``'void'``,[]));``}``},onLeave:``function``(result){}``})` `// hook android_dlopen_ext``var` `libfoo_loaded_flag = 0;` `//定义一个变量用于标记是否已加载libfoo.so``// 获取libandroid_runtime.so中的android_dlopen_ext函数的地址``var` `android_dlopen_ext_addr = Module.getExportByName(``"libandroid_runtime.so"``,` `"android_dlopen_ext"``);``// 拦截android_dlopen_ext函数``Interceptor.attach(android_dlopen_ext_addr, {``// 进入android_dlopen_ext函数时执行的操作``onEnter:``function``(args){``// 判断传入的参数中是否包含"libfoo.so"的字符串``if``(-1 != args[0].readCString().indexOf(``"libfoo.so"``)){``// 如果包含，则将libfoo_loaded_flag标记为1，表示已加载libfoo.so``libfoo_loaded_flag = 1;``}``},``// 离开android_dlopen_ext函数时执行的操作``onLeave:``function``(result){``// 如果libfoo_loaded_flag为1，表示已加载libfoo.so``if``(libfoo_loaded_flag == 1){``// 通过Interceptor.replace方法替换libfoo.so中偏移为0x323C的函数``var` `libfoo_module = Module.findBaseAddress(``"libfoo.so"``);``Interceptor.replace(libfoo_module.add(0x323C),` `new` `NativeCallback(``function``(){` `console.log(``"获取反调试地址sub_323c==>"``+libfoo_module)``return``;``},` `'void'``, []));``libfoo_loaded_flag = 0;``}``}``})``var` `RootDetection = Java.use(``"sg.vantagepoint.util.RootDetection"``);``RootDetection[``"checkRoot1"``].implementation =` `function` `() {``console.log(``'checkRoot1 is called'``);``var` `ret =` `this``.checkRoot1();``console.log(``'checkRoot1 ret value is '` `+ ret);``return` `false``;``};` `}``)}``// 立即开始执行函数``setImmediate(main);` |
|-|-|

#### 3.2.1.5. 再次来到`Native`看bar判断函数进行代码分析

![image-20231024111034939](https://bbs.kanxue.com/upload/attach/202310/940967_TSYESFE99SSQ4G8.png)

简单概括一下，`bar`函数通过生成key1和字符串`pizzapizzapizzapizzapizz`进行异或来获取新的字符串，我们的思路就是`hook`生成`key1`函数(`v6 = sub_10E0(v9);`)得到key1，再和`"pizzapizzapizzapizzapizz"`进行异或

完整脚本如下

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576777879808182838485868788 | `// hook linker64's call_array``function` `main() {``Java.perform(``function``(){``// 获取linker64模块的基地址``var` `linker64_module = Module.getBaseAddress(``"linker64"``);``//使用拦截器附加linker64模块的偏移地址``// 7D68B58764 - 7D68B38000 = 0x20764``Interceptor.attach(linker64_module.add(0x20764),{``// 进入函数，代码检查参数args[3]指向的字符串是否匹配libfoo.s``onEnter:``function``(args) {``if``(args[3].readCString().match(``"libfoo.so"``)) {``// 获取libfoo.so的基地址``var` `libfoo_module  = Module.findBaseAddress('libfoo.so``');``console.log("获取libfoo.so的基地址==>"+libfoo_module)``Interceptor.replace(libfoo_module.add(0x30D0),new NativeCallback(function(){``return;``},'``void``',[]));``}``},onLeave:function(result){}``})` `// hook android_dlopen_ext``var libfoo_loaded_flag = 0;``var android_dlopen_ext_addr = Module.getExportByName("libandroid_runtime.so", "android_dlopen_ext");``Interceptor.attach(android_dlopen_ext_addr, {``onEnter:function(args){``if(-1 != args[0].readCString().indexOf("libfoo.so")){``libfoo_loaded_flag = 1;``}``},onLeave:function(result){``if(libfoo_loaded_flag == 1){``// hook libfoo.so + 0x323C , pass call ptrace``var libfoo_module = Module.findBaseAddress("libfoo.so");``Interceptor.replace(libfoo_module.add(0x323C), new NativeCallback(function(){``console.log("获取反调试地址sub_323c==>"+libfoo_module)``return;``}, '``void``', []));``libfoo_loaded_flag = 0;``}``}``})``var RootDetection = Java.use("sg.vantagepoint.util.RootDetection");``RootDetection["checkRoot1"].implementation = function () {``console.log('``checkRoot1 is called``');``var ret = this.checkRoot1();``console.log('``checkRoot1 ret value is` `' + ret);``return false;``};` `// hook异或``var str_xor_key1 = 0;``//获取hook so的基地址``var target_module= Module.findBaseAddress('``libfoo.so``');` `//用拦截器 获取libfoo.so的函数sub10E0(v8)偏移地址``if(target_module){``console.log("start read libfoo.so")``Interceptor.attach(target_module.add(0x10E0),{``onEnter:function(args) {``// v8处理前``str_xor_key1 = args[0];` `},``// v8处理后``onLeave:function(result) {``//readByteArray返回的是ArrayBuffer，转化成JS类型``console.log('``\n``',str_xor_key1.readByteArray(0x18));``var key1_bytes = new Uint8Array(str_xor_key1.readByteArray(0x18))``var key2 = "pizzapizzapizzapizzapizz";``var flag = '``';``// 开始异或``for(var i=0;i<0x18;i++){``flag = flag+ String.fromCharCode(key2.charCodeAt(i) ^ key1_bytes[i]);``}``console.log("flag:",flag);``console.log("flag:",flag);` `}``})``}    else{``console.log("can'``t read libfoo.so")``}` `}``)}`  `// 立即开始执行函数``setImmediate(main);` |
|-|-|

![image-20231024111045694](https://bbs.kanxue.com/upload/attach/202310/940967_JRWNPJER9VZ4B89.png)

分析结束

## 总结:

1. 对于分析`APK`程序来说动静态结合必不可少
2. `Native`层从`ELF` 初始化字符串到`so`文件的`root` 检测都不可忽略
3. 只要分析正确, `Frida` 几乎可以帮我们绕过所有的安全检查
4. 和 `Dalvik` 代码不同，`Native` 层的代码更难分析，也代表更有挑战性

---

# 回复

## 回复 by mb_fidppcok (#2)

*2023-10-25 11:07*

mark下。感觉大佬思路清晰

## 回复 by 你瞒我瞒 (#3)

*2023-10-27 09:12*

感谢分享

## 回复 by mb_eiaothcj (#4)

*2023-11-24 11:22*

其实没有必要用到ida的，第三题只要用frida枚举linker64的symbol，然后indexOf进行查找关键字就可以获得地址了

## 回复 by 4Chan (#5)

*2023-11-28 22:22*

学到了

## 回复 by 梦_魇 (#6)

*2023-12-6 23:33*

感谢分享

## 回复 by st0ne (#7)

*2023-12-6 23:37*

瀚总牛逼
