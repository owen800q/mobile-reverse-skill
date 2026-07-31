---
title: '[原创]某cocos2djs游戏jsc以及资源文件解密'
url: https://bbs.kanxue.com/thread-284809.htm
tid: 284809
author: REerr
date: '2024-12-14'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:16:59+08:00'
replies: 1
---

# 前言

本篇文章仅为学习交流所用，涉及的数据已做脱敏处理，请勿用于不当途径，侵权请联系

# 分析环境

- 生产环境：Windows 10
- 主机环境：Mi 11 Pro
- 工具：Frida 16、IDA 7.7

# 分析步骤

## 资源文件解密

首先解包APP后打开assets\resources文件夹后发现png文件，但是直接打开提示图片已破损，我勒个豆，顿感不妙，遂换一个工具试试，使用010打开后有了新发现。如下图：

 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_Q48S644RC5TP39V.webp)

这小子竟然偷偷换了PNG的魔术头，那么他有木有可能偷懒只是改了魔术头呢？于是乎我就准备把头在给他安装回去，让他不在那么不正常！！！填充头部8字节的魔术头(89 50 4E 47 0D 0A 1A 0A)，保存，重新打开，发现还是不行。这小子是一点懒也不偷啊！年度最佳员工奖得给他！
那没办法了，轻易得到的总不是最珍惜的！干他！！！
首先观察几张加密的PNG文件后发现头部7字节仿佛是flag，是固定的，7字节后可能就是加密数据。
加载图片的话，一般会调用open、fopen之类的函数，我们使用frida hook 这些API，看看是否会有所收获。经过一堆输出然后检索信息后得到了有效信息如下：

>
> [Libc::fopen] fopen filename /data/user/0/com.xxxx.xxx/files/gamecaches/mnpanda/17340646274751859.png
> [INFO][12/13/2024, 00:37:11 PM][PID:6478][Thread-25][6654][showNativeStacks]: Backtrace:
>  0x7493b6edfc libcocos2djs.so!0x766dfc
>  0x7493b6edfc libcocos2djs.so!0x766dfc
>  0x7493b58664 libcocos2djs.so!0x750664
>  0x7493b6ed0c libcocos2djs.so!0x766d0c
>  0x7493c792dc libcocos2djs.so!0x8712dc
>  0x7493befe48 libcocos2djs.so!0x7e7e48
>  0x7493c81d4c libcocos2djs.so!0x879d4c
>  0x7493c82808 libcocos2djs.so!0x87a808
>  0x75c6b0c5cc libc.so!_ZL15__pthread_startPv+0xd4
>  0x75c6aa5fc0 libc.so!__start_thread+0x48
>  0x75c6aa5fc0 libc.so!__start_thread+0x48
>
>
>

通过上面的信息我们可以发现解密函数可能来自libcocos2djs.so，IDA加载该so后跳转到

0x766dfc 这个地址看一下。如下图：
 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_EQ8TJSF7ENGC57A.webp)

这里只是文件操作相关，说明加密函数还在上一层，继续追，找到其调用位置，如下图：
 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_H52BGZ36CTG7KA6.webp)

该函数主要是尝试从 OBB（扩展）文件或 Android 资产系统加载文件内容，在往上追......
 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_GH27MMNG496KTDP.webp)

直到这里，一切就变得明了了。我们跟进cocos2d::Image::initWithImageData函数看看。

 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_3VH5QU8AGH855HA.webp)

cocos2d::Image::deEncryptPng函数中，密钥固定为1f8fd1612362fdd6f753f2ee55107d2b，跟进函数看看
 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_TMQ8TZ34SUNJ72M.webp)

hook看一下参数
 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_99KP34HRKV5R4FA.webp)

果然跟上面的猜测一样，原始数据偏移7字节后即为加密数据，然后key和每个字节做异或运算得到明文数据。按照原始程序将此还原为C。主要逻辑代码如下：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758 | `int` `deEncryptPng(``const` `unsigned` `char` `*inputData,` `// 本地读取的加密PNG数据（不含PNG头和IEND）``size_t` `inputLen,` `// inputData长度``const` `char` `*key,` `// 异或密钥字符串``unsigned` `char` `*outputData` `// 输出的完整解密PNG数据``)``{``// 计算密钥长度``size_t` `keyLen =` `strlen``(key);` `// 总输出长度 = 输入长度 + 8字节PNG头 + 12字节IEND = inputLen + 20``size_t` `outputLen = inputLen + 20;` `// 写入PNG标准头部：89 50 4E 47 0D 0A 1A 0A``// (标准PNG文件头)``outputData[0] = 0x89;``outputData[1] = 0x50;``outputData[2] = 0x4E;``outputData[3] = 0x47;``outputData[4] = 0x0D;``outputData[5] = 0x0A;``outputData[6] = 0x1A;``outputData[7] = 0x0A;` `// 将输入数据拷贝到outputData的第8字节开始的位置``memcpy``(outputData + 8, inputData, inputLen);` `// 写入IEND块到尾部``// IEND块共12字节：00 00 00 00 49 45 4E 44 AE 42 60 82``size_t` `endPos = outputLen - 12;``outputData[endPos + 0]  = 0x00;``outputData[endPos + 1]  = 0x00;``outputData[endPos + 2]  = 0x00;``outputData[endPos + 3]  = 0x00;``outputData[endPos + 4]  = 0x49;` `// 'I'``outputData[endPos + 5]  = 0x45;` `// 'E'``outputData[endPos + 6]  = 0x4E;` `// 'N'``outputData[endPos + 7]  = 0x44;` `// 'D'``outputData[endPos + 8]  = 0xAE;``outputData[endPos + 9]  = 0x42;``outputData[endPos + 10] = 0x60;``outputData[endPos + 11] = 0x82;` `// 异或处理区域：从offset=8一直到(outputLen - 13)字节位置``// 这对应原代码中v8 = a4 - 13的逻辑``if` `(outputLen > 20) {``size_t` `start = 8;``size_t` `stop = outputLen - 13;` `// 包含此位置``size_t` `idx = 0;``for` `(``size_t` `i = start; i <= stop; i++) {``if` `(idx >= keyLen) idx = 0;``outputData[i] ^= (unsigned` `char``)key[idx++];``}``}` `// 返回密钥长度（根据原函数返回值逻辑）``return` `(``int``)keyLen;``}` |
|-|-|

尝试解密，发现姿势正确！！！
 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_3JX884V9QZ2FMHV.webp)

## jsc文件解密

在查找PNG文件的途中，发现了jsc文件，那就顺便研究一下姿势吧！
通过询问GPT得到了一定的思路，GPT回答如下：
 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_WQJP8MN9WRDAH3H.webp)

按照这个思路，我们去IDA里面搜一下xxtea。
 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_FDUKDAKGHXUBQRV.webp)

发现有个设置key的地方，跟进去看一下。
 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_TKKVQ4H835BQX7Z.webp)

代码逻辑比较简单，就是根据传入指针 result 的内容，对一个全局字符串变量 byte_1BD9AC8进行设置，记住这个全局变量，一会要考！！！！
那我们就交叉引用看一下调用它的地方。

 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_UUCUZS7GVPNCTR4.webp)

这时候我们就发现key固定为bc337194-20c1-45。既然找到密钥了，再回去看xxtea的解密函数。
 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_EDT4GEP3GDXHJV9.webp)

对于参数对应关系不太清楚，这时候需要查阅一下源码[xxtea_decrypt](https://github.com/cocos/engine-native/blob/f4a387d614691101c79ef75d1dbce705c834cad3/cocos/scripting/js-bindings/manual/jsb_global.cpp#L141) 通过源码可知，参数一为加密数据，参数二为加密数据长度，参数三为解密key，参数四为key的长度，参数为解密数据长度。
验证是否和源码描述一样，我们可以通过查看静态代码和hook的方式去确认。首先我们查看调用解密方法的地方。主要逻辑如下图：

 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_THQTA55YYNNMVWK.webp)

这时候我们基本上确定和分析的一样，我们可以hook看一下数据。在打开加密的jsc文件，在hook 结果中搜索一下加密数据的前几位，就可以确定是否是我们想要的数据。
 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_NYWS9QU8WP55BP7.webp)

那么接下来就可以写代码验证了，解密方法为xxtea_decrypt, 密钥为bc337194-20c1-45。主要代码如下：

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344 | `def` `export_data(``jsc_file_path:` `str``, encryption_key_str:` `str``, output_file_path:` `str``)` `-``> Optional[``tuple``]:``"""``Function for decrypting JSC files``"""``logger.info(``"Starting export_data..."``)` `code, status` `=` `check_file(jsc_file_path,` `".JSC"``,` `True``)``if` `code !``=` `"OK"``:``return` `code, status` `jsc_file` `=` `open``(jsc_file_path,` `"rb"``)``jsc_file_data` `=` `jsc_file.read()``jsc_file.close()` `logger.info(f``"Decrypting with key = {encryption_key_str}"``)``output_data` `=` `xxtea.decrypt(jsc_file_data, encryption_key_str, padding``=``False``)``if` `len``(output_data)` `=``=` `0``:``return` `"WRONG_KEY"``,` `"Invalid encryption key!"` `is_gzip_file` `=` `True``try``:``output_data` `=` `zlib.decompress(output_data,` `32` `+` `15``)``logger.info(``"IT IS a GZIP archive."``)``except` `zlib.error as error:``logger.info(``"It's NOT a GZIP archive."``)``is_gzip_file` `=` `False` `if` `not` `is_gzip_file:``try``:``zip_file` `=` `io.BytesIO(output_data)``ZipFile(zip_file)``output_file_path` `+``=` `".zip"``logger.info(``"IT IS a ZIP archive."``)``except` `BadZipFile as error:``logger.info(``"It is NOT a ZIP archive."``)` `js_file` `=` `open``(output_file_path,` `"wb"``)``js_file.write(output_data)` `js_file.close()``logger.info(f``"File exported: {output_file_path}"``)``return` `"OK"``, ""` |
|-|-|

运行后查看，解密成功~~~~~~
 ![image](https://bbs.kanxue.com/upload/attach/202412/951706_C62G6Q8PEQD7H4U.webp)

至此，涉及jsc和资源文件的解密就结束了！！！那位同学的最佳员工可能暂时没了，不过新的KPI又有了！！！你就说吧，我对你好不好！哈哈哈哈哈~~~
项目完整代码：[cocos2dx_decryption](https://github.com/xiaokanghub/cocos2dx_decryption.git)

---

# 回复

## 回复 by aqingadmin (#2)

*2024-12-14 22:06*

无尽冬日 luajit解密 不知大佬有没有玩过
