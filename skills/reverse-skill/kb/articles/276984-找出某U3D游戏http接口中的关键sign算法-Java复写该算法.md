---
title: '[原创]找出某U3D游戏http接口中的关键sign算法，Java复写该算法'
url: https://bbs.kanxue.com/thread-276984.htm
tid: 276984
author: 易码
date: '2023-04-24'
tags: [Android安全, 原创, 逆向分析, 协议分析, 脱壳反混淆, 漏洞相关]
crawled_at: '2026-07-31T14:49:44+08:00'
replies: 0
---

该游戏所有登录接口都会有一个code字段（类似sign），只要突破这个字段的算法，所有接口均可自动化脚本运行，实现脱机。
我们以登录接口为入口进行分析
1，抓包比对，发现在用户登录不同的账号时，除了账号密码，只有code字段会变化，其它不变。说明code字段就是类似sign的字段。
 ![image](https://bbs.kanxue.com/upload/attach/202304/871277_F58PEE6TGFBGMFQ.png)
 ![image](https://bbs.kanxue.com/upload/attach/202304/871277_U6JWM2S2FYSBQPZ.png)

 2，寻找计算code的接口，因为是u3d游戏，关键数据在libil2cpp.so和 global-metadata.dat文件中。解压apk，找到这两个文件。用il2cppdumper进行dump。在out目录中找到dump.cs.
 ![image](https://bbs.kanxue.com/upload/attach/202304/871277_CJNX2KFVAK5REYB.jpg)

 执行上面的exe，输出目录在output中：
 ![image](https://bbs.kanxue.com/upload/attach/202304/871277_CPYWB5CX4MZBQSV.jpg)

 3, 浏览接口列表，搜索code，发现疑似接口。so中地址:0xD55700.

  ![image](https://bbs.kanxue.com/upload/attach/202304/871277_NK6AVDPE87ZAQUG.jpg)

 上面这个接口，可能就是code的计算方法，输入为一个hashmap，可能是url中各个参数，我们进去看看。

 4,进入ida，加载so，定位到地址。为了更好的关联函数名字，需要运行脚本,需要把output中的两个json后缀文件：
script.json
stringliteral.json
通过上述py脚本加载运行，这样就可以看到函数名。

 之后在ida中打开libil2cpp.so,定位到地址：0xD55700，按F5，看伪代码：
 ![image](https://bbs.kanxue.com/upload/attach/202304/871277_D4NK34YCB2QCCX5.jpg)

 先遍历url中各个参数，在拼接，用0补齐位数，满足长度为8的整数倍，为下面的des算法做准备。看到，现实用des，再MD5进行编码。
进去看看Des是怎么操作的。

  ![image](https://bbs.kanxue.com/upload/attach/202304/871277_2EGFKUDYV7T43JB.jpg)

 用的是DesEcb算法。在des前，将ulr个字段拼写的字符串a1的基础上加上首位拼接字符串，这两个首位字符串可以在汇编窗口看到：

  ![image](https://bbs.kanxue.com/upload/attach/202304/871277_T7CZSA7NTEZKQEY.jpg)

 DesEcb算法当中看看des的加密：

 那么，ulrparam中各参数是如何拼接的呢？需要动态调试一下，再打开一个ida用于动态调试，通过静态代码分析定位到将拼接结果存入寄存器x0的指令地址，
据此计算动态地址地址（so基地址+指令偏移）：

  ![image](https://bbs.kanxue.com/upload/attach/202304/871277_TS7F5ZRQVS5C2FA.jpg)

 运行程序，断到该指令出，查看结果x0的值：

  ![image](https://bbs.kanxue.com/upload/attach/202304/871277_C99CJ3V86GRZ6GU.jpg)

 看到字符串是通过对url个字段拼接： 头部字符串 + key1=vlaue & key2=vlaue2 &key3=vlaue3 & key4=vlaue4 + 尾字符串，这种形式。

 于是整个算法明确 ： 头部字符串 + key1=vlaue&key2=vlaue2&key3=vlaue3&key4=vlaue4+尾字符串，先进行desecb，然后 base64，最后md5.

 据此复写算法的Java版本：

 / **secretKey:密码
encData：要加密的数据**/
public static String Encrypt(String secretKey, String encData) throws Exception {
 if (secretKey == null) {
 return null;
 }

| 1234567891011121314151617181920212223242526272829303132333435363738394041 | `Cipher cipher` `=` `Cipher.getInstance(` `"DES/ECB/NoPadding"``);``SecretKeySpec skeySpec` `=` `new SecretKeySpec(getKey(secretKey),` `"DES"``);``cipher.init(Cipher.ENCRYPT_MODE, skeySpec);``byte[] encrypted` `=` `cipher.doFinal(encData.getBytes());``MessageDigest md` `=` `MessageDigest.getInstance(``"MD5"``);``String base64Str``=` `Base64.encodeToString(encrypted,``0``);``base64Str` `=` `base64Str.replaceAll(``"[\\s*\t\n\r]"``, "");``String result` `=` `MD5Utils.encrypt(base64Str);``return` `result;``}` `public static byte[] getKey(String keyRule) {``Key key` `=` `null;``byte[] keyByte` `=` `keyRule.getBytes();``byte[] byteTemp` `=` `new byte[``8``];``for` `(``int` `i` `=` `0``; i < byteTemp.length && i < keyByte.length; i``+``+``) {``byteTemp` `=` `keyByte;``}``key` `=` `new SecretKeySpec(byteTemp,` `"DES"``);``return` `key.getEncoded();``}` `private static String toHexString(byte[] digest) {``StringBuilder sb` `=` `new StringBuilder();``String hexStr;``for` `(byte b : digest) {``hexStr` `=` `Integer.toHexString(b &` `0xFF``);``if` `(hexStr.length()` `=``=` `1``) {``hexStr` `=` `"0"` `+` `hexStr;``}``sb.append(hexStr);``}``return` `sb.toString();``}` `private static SecretKey keyGenerator(String keyStr) throws Exception {``DESKeySpec desKey` `=` `new DESKeySpec(keyStr.getBytes());``SecretKeyFactory keyFactory` `=` `SecretKeyFactory.getInstance(``"DES"``);``SecretKey securekey` `=` `keyFactory.generateSecret(desKey);``return` `securekey;``}` |
|-|-|

}

 注：本分析研究过程，仅用于学习交流，请勿用于非法目的！
