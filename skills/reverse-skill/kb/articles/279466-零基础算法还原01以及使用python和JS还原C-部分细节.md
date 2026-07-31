---
title: '[原创]零基础算法还原01以及使用python和JS还原C++部分细节'
url: https://bbs.kanxue.com/thread-279466.htm
tid: 279466
author: 4Chan
date: '2023-11-05'
tags: [Android安全, 原创, 基础理论, 逆向分析, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T14:36:49+08:00'
replies: 4
---

# 导读

你能从本文中学到apk中的so层简单算法还原以及使用js和python还原C代码的部分细节

题目链接

链接：<https://pan.baidu.com/s/1HbkzNZqIQYj6rwDpSYt_aQ>
提取码：1234

# 题目一

使用`jadx` 打开`algorithmbase_10.apk`

![image-20231101144427292](https://bbs.kanxue.com/upload/attach/202311/940967_8ZVX7SRD3KKT7KX.png)

## JAVA层

使用`Frida`获取先生成的随机字符串

| 12345678910111213141516171819202122232425262728293031 | `// 定义一个名为hook_js的JavaScript函数``function` `hook_js(){``// 使用Java.perform()函数来执行JavaScript代码``Java.perform(``function``(){``// 使用Java.use()函数来获取Java类com.kanxue.algorithmbase.MainActivity``var` `m_randomAscii = Java.use(``"com.kanxue.algorithmbase.MainActivity"``)` `// 检查获取的类对象是否存在``if``(m_randomAscii!=undefined){``console.log(``"开始Hook"``);` `// 打印开始Hook的消息` `// 重写函数encodeFromJni_11的实现``m_randomAscii.encodeFromJni_11.implementation =` `function``(input){``// 获取输入参数input``var` `res =` `this``.encodeFromJni_11(input);` `// 打印输入参数和返回值``console.log(``"input:==>"``+input);``console.log(``"res:==>"``+res);` `// 返回结果``return` `res;``}``}``})``}``function` `main(){``hook_js();``}` `setImmediate(main);` |
|-|-|

传入的随机字符串和字符串在**Native**层加密后的结果如下

| 12 | `input``:``=``=``> meUx3DppB``%``Gj]``-``2J``res:``=``=``> LCllTadbMHYZ0kNnDitri5``=``=` |
|-|-|

- 随机字符串:meUx3DppB%Gj]-2J
- 加密后的结果: LCllTadbMHYZ0kNnDitri5==

![image-20231101145832850](https://bbs.kanxue.com/upload/attach/202311/940967_VWHACV5MC76M9PA.png)

我们进入`Native`层查看加密后的结果

## Native层

使用`unzip`命令解压`apk`获取`so`文件

`unzip algorithmbase_10.apk -d fileso10`

![image-20231101144703961](https://bbs.kanxue.com/upload/attach/202311/940967_R6NDGMZ7ZN5ZV9D.png)

使用`Ida`打开`so`文件，在`Export`表输入`JNI`查看加密函数的位置

![image-20231101150231637](https://bbs.kanxue.com/upload/attach/202311/940967_DR79857G5B5DP2C.png)

使用快捷键`Y`和`N`修改传入的参数名称，以便我们方便我们后续分析

![image-20231101150546220](https://bbs.kanxue.com/upload/attach/202311/940967_PMG3RMQRPWCT4F9.png)

返回值是**v13**

我们从下往上回溯来到 `sub_EE38(v9, v10, v11)` 函数

使用`Frida` 对`sub_EE38` 函数进行`hook`，目的是为了查看传入的参数和传出的参数

脚本如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748 | `function` `hook_js(){``Java.perform(``function``(){``var` `m_randomAscii = Java.use(``"com.kanxue.algorithmbase.MainActivity"``)` `//获取MainActivity类``if``(m_randomAscii!=undefined){``console.log(``"开始Hook"``);``m_randomAscii.encodeFromJni_11.implementation =` `function``(input){` `//找到encodeFromJni_11方法，并拦截调用``var` `res =` `this``.encodeFromJni_11(input);` `//调用原始方法``console.log(``"input:==>"``+input);` `//打印输入参数``console.log(``"res:==>"``+res);` `//打印返回结果``return` `res;` `//返回结果` `}``}``})``}` `function` `hook_native(){``Java.perform(``function``(){``//找到基地址``var` `base_address = Module.getBaseAddress(``"libnative-lib.so"``)` `//获取libnative-lib.so的基地址``var` `sub_EE38 = base_address.add(0xEE38);` `//计算函数偏移地址``//开启拦截器``Interceptor.attach(sub_EE38,{``//进入函数``onEnter:``function``(args){``this``.arg0 = args[0];` `//保存第一个参数``console.log(``"======>onENter<=========="``);``console.log(``"第一个参数未处理前===>"``+args[0].readCString());` `//打印第一个参数内容``console.log(``"第二个参数未处理前===>"``+args[1].readCString());` `//打印第二个参数内容``console.log(``"第三个参数未处理前===>"``+args[2]);` `//打印第三个参数内容``},``onLeave:``function``(nresult){` `console.log(``"======>onLeave<=========="``);``console.log(``"第一个参数处理后======>"``+``this``.arg0.readCString());` `//打印处理后的第一个参数`  `}``})``})``}`  `function` `main(){``hook_js();``hook_native();``}` `setImmediate(main);` |
|-|-|

点击app按钮，Hook的代码如下所示

![image-20231101151718613](https://bbs.kanxue.com/upload/attach/202311/940967_K7ZVX5SVAT8M3GU.png)

我们获取到如下参数

| sub_EE38(_BYTE *a1, __int64 a2, int a3) | 第一个参数 | 第二个参数 | 第三个参数 |
|-|-|-|-|
| 未处理前 | "" | meUx3DppB%Gj]-2J | 0x10 |
| 处理后后 | LCllTadbMHYZ0kNnDitri5== |  |  |

| 1234567 | `第一个参数未处理前``=``=``=``>``第二个参数未处理前``=``=``=``>meUx3DppB``%``Gj]``-``2J``第三个参数未处理前``=``=``=``>``0x10``=``=``=``=``=``=``>onLeave<``=``=``=``=``=``=``=``=``=``=``第一个参数处理后``=``=``=``=``=``=``>LCllTadbMHYZ0kNnDitri5``=``=``input``:``=``=``>meUx3DppB``%``Gj]``-``2J``res:``=``=``>LCllTadbMHYZ0kNnDitri5``=``=` |
|-|-|

也就是说 `sub_EE38` 就是我们找的加密call

我们不妨进入`sub_EE38` 查看加密细节

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061 | `__int64` `__fastcall sub_EE38(_BYTE *a1,` `__int64` `a2,` `int` `a3)``{``__int64` `v3;` `// x9，循环计数器``_BYTE *v4;` `// x12，用于存储结果的指针``unsigned` `__int8` `*v5;` `// x10，用于指向输入数据的指针``unsigned` `__int64` `v6;` `// x13，临时变量``_BYTE *v7;` `// x10，下一个结果的存储位置``__int64` `v8;` `// x11，临时变量``char` `v9;` `// w8，临时变量``__int64` `v10;` `// x9，临时变量``__int64` `result;` `// x0，函数返回值` `if` `(a3 - 2 < 1)` `// 当数据长度小于等于2时``{``LODWORD(v3) = 0;``v7 = a1;``if` `(a3 <= 0)``goto` `LABEL_11;``}``else``{``v3 = 0LL;``v4 = a1;``do``{``v5 = (unsigned` `__int8` `*)(a2 + v3);` `// 从输入数据中取出三个字节进行处理``v6 = *(unsigned` `__int8` `*)(a2 + v3);``v3 += 3LL;``*v4 = aAyzabfghz0cmbd[v6 >> 2];` `// 取出第一个字节的前6位对应的字符``v4[1] = aAyzabfghz0cmbd[(16 * (unsigned` `int``)*v5) & 0x30LL \| ((unsigned` `__int64``)v5[1] >> 4)];` `// 取出第二个字节的前4位和第一个字节的后2位所对应的字符``v4[2] = aAyzabfghz0cmbd[(4 * (unsigned` `int``)v5[1]) & 0x3CLL \| ((unsigned` `__int64``)v5[2] >> 6)];` `// 取出第三个字节的前2位和第二个字节的后4位所对应的字符``LOBYTE(v6) = aAyzabfghz0cmbd[v5[2] & 0x3F];` `// 取出第三个字节的后6位对应的字符``v7 = v4 + 4;` `// 指向下一个结果的存储位置``v4[3] = v6;` `// 存储刚才取出的字符``v4 += 4;` `// 指向下一个处理位置``}``while` `(v3 < a3 - 2);` `// 处理到倒数第三个字节为止``if` `((``int``)v3 >= a3)` `// 如果处理到倒数第二个字节或最后一个字节``goto` `LABEL_11;``}``*v7 = aAyzabfghz0cmbd[(unsigned` `__int64``)*(unsigned` `__int8` `*)(a2 + (unsigned` `int``)v3) >> 2];` `// 取出最后一个字节的前6位对应的字符``v8 = (16 * (unsigned` `int``)*(unsigned` `__int8` `*)(a2 + (unsigned` `int``)v3)) & 0x30LL;` `// 取出最后一个字节的前4位``if` `((_DWORD)v3 == a3 - 1)` `// 如果只有最后一个字节``{``v7[1] = aAyzabfghz0cmbd[v8];` `// 存储最后一个字节的前4位对应的字符``v9 = 61;` `// 存储'='字符``}``else``{``v10 = a2 + (unsigned` `int``)v3;` `// 最后两个字节的指针``v7[1] = aAyzabfghz0cmbd[v8 \| ((unsigned` `__int64``)*(unsigned` `__int8` `*)(v10 + 1) >> 4)];` `// 存储最后一个字节的前4位和倒数第二个字节的后2位对应的字符``v9 = aAyzabfghz0cmbd[(4 * (unsigned` `int``)*(unsigned` `__int8` `*)(v10 + 1)) & 0x3CLL];` `// 存储倒数第二个字节的后4位对应的字符``}``v7[2] = v9;` `// 存储倒数第二个字节的后4位或'='字符``v7[3] = 61;` `// 存储'='字符``v7 += 4;` `// 指向下一个结果的存储位置``LABEL_11:``result = (unsigned` `int``)((_DWORD)v7 - (_DWORD)a1 + 1);` `// 计算结果的长度``*v7 = 0;` `// 结果字符串结尾添加NULL字符``return` `result;` `// 返回结果长度``}` |
|-|-|

根据call，还原加密算法

用C代码还原加密算法如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475 | `// 01.cpp : 此文件包含 "main" 函数。程序执行将在此处开始并结束。``//` `#include <iostream>``#include <memory>``#include <Windows.h>` `#include <minwindef.h>``#include <rpcndr.h>` `using` `namespace` `std;` `unsigned` `char``* sub_EE38(``char``* strResult,` `long` `long` `inPut,` `signed` `int` `nCnt)``{``long` `long` `v3 = 0;``unsigned` `char``* v4 =` `new` `unsigned` `char``[100];``unsigned` `char``* v5 = nullptr;``unsigned` `long` `long` `v6 = 0;``char` `aAyzabfghz0cmbd[] =` `"AYZabFGHz0cmBdefghijklCDE1KLMNTU56789+/VWXnopq23IJrstuvwOPQRSxy4"``;``long` `long` `result = 0;``unsigned` `long` `long` `v8 = 0;``char` `v9;``unsigned` `char``* v7;``long` `long` `v10;``//记录v4初始``unsigned` `char``* vCount = v4;``do``{``*v4 = 0;``v5 = (unsigned` `char``*)(inPut + v3);``v6 = *(unsigned` `char``*)(inPut + v3);``v3 += 3;``*v4 = aAyzabfghz0cmbd[v6 >> 2];``v4[1] = aAyzabfghz0cmbd[(16 * (unsigned` `int``)*v5) & 0x30 \| ((unsigned` `long` `long``)v5[1] >> 4)];``v4[2] = aAyzabfghz0cmbd[(4 * (unsigned` `int``)v5[1]) & 0x3C \| ((unsigned` `long` `long``)v5[2] >> 6)];``unsigned` `char` `lowByte = aAyzabfghz0cmbd[v5[2] & 0x3F];``v6 = (v6 & ~(0xFFull)) \| lowByte;``v7 = v4 + 4;``v4[3] = v6;``v4 += 4;``}` `while` `(v3 < nCnt - 2);``if` `((``int``)v3 >= nCnt)``goto` `LABEL_11;``*v7 = aAyzabfghz0cmbd[(unsigned` `long` `long``) * (unsigned` `char``*)(inPut + (unsigned` `int``)v3) >> 2];``v8 = (16 * (unsigned` `int``)*(unsigned` `__int8``*)(inPut + (unsigned` `int``)v3)) & 0x30LL;``if` `(v3 == nCnt - 1)``{``v7[1] = aAyzabfghz0cmbd[v8];``v9 = 61;``}``else``{``v10 = inPut + (unsigned` `int``)v3;``v7[1] = aAyzabfghz0cmbd[v8 \| ((unsigned` `long` `long``) * (unsigned` `char``*)(v10 + 1) >> 4)];``v9 = aAyzabfghz0cmbd[(4 * (unsigned` `int``)*(unsigned` `char``*)(v10 + 1)) & 0x3CLL];``}``v7[2] = v9;``v7[3] = 61;``v7 += 4;``std::cout << (unsigned` `char``*)vCount;``return` `(unsigned` `char``*)vCount;` `LABEL_11:``result = (unsigned` `int``)((``DWORD``)v7 - (``DWORD``)strResult + 1);``*v7 = 0;``delete``[] v4;``std::cout << result;``return` `(unsigned` `char``*)result;``}` `int` `main()``{``char` `str[] =` `""``;``unsigned` `char``* str2=  sub_EE38(str, (``__int64``)``"meUx3DppB%Gj]-2J"``, 0x10);``std::cout << str2;``}` |
|-|-|

![image-20231101171459516](https://bbs.kanxue.com/upload/attach/202311/940967_AH2AS8MHV8JXVS8.png)

还原得到加密结果

| 1 | `LCllTadbMHYZ0kNnDitri5``=``=` |
|-|-|

使用JS还原加密算法如下

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950 | `function` `stringToUint8Array(str){``var` `arr = [];``for` `(``var` `i=0;i<str.length;i++)``{``arr.push(str.charCodeAt(i));``}` `var` `outputbytes =` `new` `Uint8Array(arr);``return` `outputbytes;``}`  `function` `sub_EE38(str,input,nCnt){``var` `input_bytes = stringToUint8Array(input);``var` `aAyzabfghz0cmbd =` `"AYZabFGHz0cmBdefghijklCDE1KLMNTU56789+/VWXnopq23IJrstuvwOPQRSxy4"``;``var` `result =0;``var` `v4 =``""``;``var`  `v7=0;``var` `v3 =0;``var` `v6 =0``var` `v8 =0``var` `v9 =` `""` `while` `(v3 <nCnt-2){``var` `v5 = input_bytes[v3];``var` `v5_1 = input_bytes[v3+1]``var` `v5_2 = input_bytes[v3+2]``v6 = input_bytes[v3];``v3 +=3;``v4 +=  aAyzabfghz0cmbd.charAt(v6 >>2)``v4 +=  aAyzabfghz0cmbd.charAt(((16*v5)& 0x30) \| v5_1 >>4);``v4 += aAyzabfghz0cmbd.charAt((4*v5_1)&0x3C \|v5_2 >>6 );``v6 = aAyzabfghz0cmbd[v5_2 & 0x3F]``v4 += v6;``}``v4 +=aAyzabfghz0cmbd[(input_bytes[v3]) >> 2];``v8 = 16 * input_bytes[v3] & 0x30``if` `(v3 >= nCnt -1){``v4 += aAyzabfghz0cmbd[v8]``v9 =` `"="``}``else``{``v4 += aAyzabfghz0cmbd[v8 \|(v4[v3+1] >>4)]``v9 = aAyzabfghz0cmbd[(4*v4[v3+1] & 0x3C)]``}``v4 += v9``v4 +=` `"="``return` `v4``}` `console.log(sub_EE38(``""``,``"meUx3DppB%Gj]-2J"``,0x10))` |
|-|-|

![image-20231101171616527](https://bbs.kanxue.com/upload/attach/202311/940967_E3XY59V7BJKX8U2.png)

使用Python还原算法如下

| 1234567891011121314151617181920212223242526272829303132333435363738 | `def` `sub_EE38(strResult,``inPut``,nCnt):``v3` `=``0``v4` `=` `bytes(``inPut``,` `"utf-8"``)``aAyzabfghz0cmbd` `=``"AYZabFGHz0cmBdefghijklCDE1KLMNTU56789+/VWXnopq23IJrstuvwOPQRSxy4"``v6``=``0``result` `=``0``v8``=``0``output` `=` `""``v7` `=``0``while` `True``:``v5``=` `v4[v3]``v5_1` `=` `v4[v3``+``1``]``v5_2` `=` `v4[v3``+``2``]``v6` `=``v4[v3]``v3` `+``=``3``output` `+``=` `aAyzabfghz0cmbd[v6>>``2``]``output``+``=` `aAyzabfghz0cmbd[(``16``*``v5) &` `0x30` `\| (v5_1 >>``4``)]``output``+``=` `aAyzabfghz0cmbd[(``4``*``v5_1)&``0x3C` `\| (v5_2>>``6``)]``v6` `=` `aAyzabfghz0cmbd[v5_2&``0x3F``]``output` `+``=``v6``v7` `+``=``4``if` `v3>``=``nCnt``-``2``:``break``output` `+``=` `aAyzabfghz0cmbd[v4[v3] >>``2``]``v8` `=` `16` `*` `v4[v3] &` `0x30``if``(v3 >``=``nCnt` `-``1``):``output` `+``=`  `aAyzabfghz0cmbd[v8]``v9` `=` `'='``else``:``output` `+``=` `aAyzabfghz0cmbd[v8 \| (v4[v3``+``1``]>>``4``)]``v9` `=` `aAyzabfghz0cmbd[(``4``*``v4[v3``+``1``]&``0x3C``)]` `output` `+``=` `v9``output` `+``=` `'='``return` `output``# Press the green button in the gutter to run the script.``if` `__name__` `=``=` `'__main__'``:``print``(sub_EE38("``","``meUx3DppB``%``Gj]``-``2J``",``0x10``))` |
|-|-|

![image-20231101171651251](https://bbs.kanxue.com/upload/attach/202311/940967_B8SY26TNVSGCQ5U.png)

# 题目二

algorithmbase_12.apk

![image-20231104100416930](https://bbs.kanxue.com/upload/attach/202311/940967_Z3H69ZZRH6ZUECD.png)

使用apkInfo打开发现是32位程序

### JAVA层

![image-20231104100119863](https://bbs.kanxue.com/upload/attach/202311/940967_NQFRZ58DXDFBYE4.png)

分析如图，先生成随机字符串(我们可以通过`Hook` `encodeFromJni_12` 函数来查看生成的随机字符串的值)，然后把生成的随机字符串丢到`encodeFromJni_12`里面处理

我们先Hook一下`encodeFromJni_12`函数，查看加密前的字符串和加密后的字符串

| 123456789101112131415161718192021222324 | `// 定义一个名为hook_js的函数``function` `hook_js() {``// 使用Java.perform方法执行函数体``Java.perform(``function``() {``// 定义变量enrandomcode并使用Java.use方法获取com.kanxue.algorithmbase.MainActivity类``var` `enrandomcode = Java.use(``"com.kanxue.algorithmbase.MainActivity"``)``// 如果enrandomcode已定义``if``(enrandomcode != undefined) {``// 打印开始JAVA层Hook``console.log(``"开始JAVA层Hook"``);``// 重写encodeFromJni_12方法的实现``enrandomcode.encodeFromJni_12.implementation =` `function``(intput) {``// 调用原始的encodeFromJni_12方法，并将结果赋值给变量res``var` `res =` `this``.encodeFromJni_12(intput);``// 打印传入参数的值``console.log(``"传入参数是====>"` `+ intput);``// 打印加密后的参数的值``console.log(``"加密后的参数是====>"` `+ res);``// 返回加密后的结果``return` `res;``}``}``})``}` |
|-|-|

结果如下

![image-20231104101314842](https://bbs.kanxue.com/upload/attach/202311/940967_CY7PCKEA8CNVT4E.png)

| 12 | `传入参数是``=``=``=``=``>xVjHx``-``D&nji8i``*``rBZ)j``加密后的参数是``=``=``=``=``>`!^fZFrxI^q~[``+``\~p<yT``#p~F==` |
|-|-|

加密的结果看起来很像是`Base64` ，我们用**64**编码后的结果对比一下
![image-20231104101716116](https://bbs.kanxue.com/upload/attach/202311/940967_6EJYCURRDNFSYUX.png)

不是64编码，但是结果很像。猜测可能是换了码表或并非完全的`base64`加密

### so

打开`IDA`，来到加密函数`Java_com_kanxue_algorithmbase_MainActivity_encodeFromJni_112(int a1, int a2, int a3, char *a4)` 里面 进行分析

从下往上回溯，定位到`sub_8B04` 函数

![image-20231104103843906](https://bbs.kanxue.com/upload/attach/202311/940967_D74RT9U8KJ5NWW4.png)

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576 | `// 定义一个名为sub_8B04的函数，参数为a1、a2和a3，返回值为_BYTE类型的指针``_BYTE *__fastcall sub_8B04(``int` `a1,` `int` `a2,` `int` `a3)``{``int` `v3;` `// r12``int` `v6;` `// r6``int` `v7;` `// r5``_BYTE *v8;` `// r3``int` `v9;` `// r2``unsigned` `int` `v10;` `// r0``char` `v11;` `// r4``int` `v12;` `// r6``char` `v13;` `// r1` `// 计算v3的值``v3 = a3 - 2;``v6 = 0;``v7 = 0;``// 进入while循环，直到v7 >= v3``while` `( 1 )``{``// 获取a1+v6处的_BYTE类型指针``v8 = (_BYTE *)(a1 + v6);``if` `( v7 >= v3 )``break``;``// 计算v9的值``v9 = a2 + v7;``// v6加上4``v6 += 4;``// 将aAyzpq23ijrtffg[*(unsigned __int8 *)(a2 + v7) >> 2]的值赋给v8指向的地址``*v8 = aAyzpq23ijrtffg[*(unsigned` `__int8` `*)(a2 + v7) >> 2];``// 计算v10的值``v10 = *(unsigned` `__int8` `*)(a2 + v7 + 1);``// 获取a2+v7处的值``v11 = *(_BYTE *)(a2 + v7);``// v7加上3``v7 += 3;``// 将aAyzpq23ijrtffg[(v10 >> 4) & 0xFFFFFFCF \| (16 * (v11 & 3))]的值赋给v8指向的地址+1处``v8[1] = aAyzpq23ijrtffg[(v10 >> 4) & 0xFFFFFFCF \| (16 * (v11 & 3))];``// 将aAyzpq23ijrtffg[(*(unsigned __int8 *)(v9 + 2) >> 6) & 0xFFFFFFC3 \| (4 * (*(_BYTE *)(v9 + 1) & 0xF))]的值赋给v8指向的地址+2处``v8[2] = aAyzpq23ijrtffg[(*(unsigned` `__int8` `*)(v9 + 2) >> 6) & 0xFFFFFFC3 \| (4 * (*(_BYTE *)(v9 + 1) & 0xF))];``// 将*(_BYTE *)(v9 + 2) & 0x3F的值赋给v8指向的地址+3处``v8[3] = aAyzpq23ijrtffg[*(_BYTE *)(v9 + 2) & 0x3F];``}``// 如果v7 < a3，执行以下代码``if` `( v7 < a3 )``{``// 将aAyzpq23ijrtffg[*(unsigned __int8 *)(a2 + v7) >> 2]的值赋给v8指向的地址``*v8 = aAyzpq23ijrtffg[*(unsigned` `__int8` `*)(a2 + v7) >> 2];``// 计算v12的值``v12 = (16 * *(unsigned` `__int8` `*)(a2 + v7)) & 0x30;``// 如果a3 - 1 == v7，执行以下代码``if` `( a3 - 1 == v7 )``{``v13 = 61;``// 将aAyzpq23ijrtffg[v12]的值赋给v8指向的地址+1处``v8[1] = aAyzpq23ijrtffg[v12];``}``else``{``// 将aAyzpq23ijrtffg[v12 \| (*(unsigned __int8 *)(a2 + v7 + 1) >> 4)]的值赋给v8指向的地址+1处``v8[1] = aAyzpq23ijrtffg[v12 \| (*(unsigned` `__int8` `*)(a2 + v7 + 1) >> 4)];``// 将aAyzpq23ijrtffg[4 * (*(_BYTE *)(a2 + v7 + 1) & 0xF)]的值赋给v13``v13 = aAyzpq23ijrtffg[4 * (*(_BYTE *)(a2 + v7 + 1) & 0xF)];``}``// 将61的值赋给v8指向的地址+3处``v8[3] = 61;``// 将v13的值赋给v8指向的地址+2处``v8[2] = v13;``// v8加上4``v8 += 4;``}``// 将0赋给v8指向的地址``*v8 = 0;``// 返回&v8[-a1 + 1]的值``return` `&v8[-a1 + 1];``}` |
|-|-|

进行hook

这里有个坑，就是在使用拦截器对`sub_8B04` 位置进行定位，如果使用`var sub_8B04 = base_address.add(0x8B04);` 拦截出错就加一

这样才能进入函数里面

| 1 | `var` `sub_8B04 = base_address.add(0x8B04+1);` |
|-|-|

hook代码如下

| 123456789101112131415161718192021222324252627282930313233343536 | `function` `hook_native(){``Java.perform(``function``(){``var` `base_address = Module.getBaseAddress(``"libnative-lib.so"``);``if``(base_address !=undefined){``console.log(``"开始native层hook"``);``//定位拦截位置``var` `sub_8B04 = base_address.add(0x8B04+1);``console.log(``"sub_8b04:"``,sub_8B04)``if``(sub_8B04!=undefined){``console.log(``"进入native层0x8B04"``);``}``else``{``console.log(``"拦截器加载失败"``);``}``//使用拦截器``Interceptor.attach(sub_8B04,{``//开始进入函数,传入了三个参数依次打印``onEnter:``function``(args){``//保存参数``this``.arg0 = args[0];``this``.arg1 = args[1];``this``.arg2 = args[2];` `console.log(``"========>ENTER<========"``);``console.log(``"sub_8B04未初始化时第一个参数是===>"``+``this``.arg0.readCString());``console.log(``"sub_8B04未初始化时第二个参数是===>"``+``this``.arg1.readCString());``console.log(``"sub_8B04未初始化时第三个参数是===>"``+``this``.arg2.readCString());` `},``onLeave:``function``(result){``console.log(``"========>LEAVE<========"``);``console.log(``"sub_8B04已经初始化时第一个参数是===>"``+``this``.arg0.readCString());``}``}``)``}``})``}` |
|-|-|

hook显示的结果如下

| 1234 | `sub_8B04未初始化时第一个参数是``=``=``=``>``sub_8B04未初始化时第二个参数是``=``=``=``>xVjHx``-``D&nji8i``*``rBZ)j``sub_8B04未初始化时第三个参数是``=``=``=``>``0x13``(传入参数的字符串大小)``sub_8B04已经初始化时第一个参数是``=``=``=``>`!^fZFrxI^q~[``+``\~p<yT``#p~F==` |
|-|-|

使用`IDA` 对`libnative-lib.so`进行[动态调试](https://bbs.kanxue.com/thread-279335-1.htm#msg_header_h1_3)的时候会发现 `aAyzpq23ijrtffg` 字符串和我们之前记录的字符串(`aAyzpq23ijrtffg DCB "AYZpq23IJrTFfghijklCDE1KLMmBdestU5678GHz0cuvwabN9+/VWXnoOPQRSxy4",0`)并不相同，结合前面的思考，换了码表可能性更大

![image-20231104105122522](https://bbs.kanxue.com/upload/attach/202311/940967_9K6WBENU82Y2TPN.png)

我们开始`hook` `aAyzpq23ijrtffg` 码表(`0x1B000`),这个有个`hook`技巧: 复制使用`readCString`打印字符串 可能会造成数据丢失，所以我们使用`hexdump`(16进制)显示码表的内容会更精确

hook代码如下

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344 | `function` `hook_native_sub_8B04(){``Java.perform(``function``(){``var` `base_address = Module.getBaseAddress(``"libnative-lib.so"``);``if``(base_address !=undefined){``console.log(``"开始native层hook"``);``//定位拦截位置``var` `sub_8B04 = base_address.add(0x8B04+1);``if``(sub_8B04){``console.log(``"进入native层0x8B04"``);``}``else``{``console.log(``"拦截器加载失败"``);``}``//使用拦截器``Interceptor.attach(sub_8B04,{``//开始进入函数,传入了三个参数依次打印``onEnter:``function``(args){` `//保存第一个参数``this``.arg0 = args[0];``this``.arg1 = args[1];``this``.arg2 = args[2];``console.log(``"========>ENTER<========"``);``// console.log("sub_8B04未初始化时第一个参数是===>"+hexdump(this.arg0,{length:32,header:false}));``// console.log("sub_8B04未初始化时第一个参数是===>"+hexdump(this.arg1,{length:32,header:false}));``//console.log("sub_8B04未初始化时第一个参数是===>"+hexdump(this.arg2,{length:32,header:false}));``var` `hook_aAyzpq23ijrtffg = base_address.add(0x1B000);``if``(hook_aAyzpq23ijrtffg!=undefined){console.log(``"aAyzpq23ijrtffg进入8B04的形状=====>"``+hexdump(hook_aAyzpq23ijrtffg))};`   `},``onLeave:``function``(result){``console.log(``"========>LEAVE<========"``);``console.log(``"sub_8B04第一个参数处理后======>"``+hexdump(``this``.arg0));` `//打印处理后的第一个参数``//console.log("sub_8B04得到的结果是====>"+result.readCString());``// console.log("sub_8B04处理后第一个参数是===>"+hexdump(this.arg0,{length:32,header:false}));``console.log(``"sub_8B04处理后时第一个参数是===>"``+result);``// console.log("sub_8B04处理后时第一个参数是===>"+hexdump(this.arg2,{length:32,header:false}));` `}``})``}``})``}` |
|-|-|

码表果然发生改变

![image-20231104105804418](https://bbs.kanxue.com/upload/attach/202311/940967_X69KSGSS6857WVM.png)

看看是不是只是简单换了码表，其他地方有没有进行加密

![image-20231104110924545](https://bbs.kanxue.com/upload/attach/202311/940967_RJ2T69G7JYSNRFF.png)

是的，和猜测的结果完全一致！

再来看看码表是在哪个位置发生改变的，在`sub_8ABC` 找到码表发生变化的位置,并且发现传参(a1)就是加密前的字符串被int强转

![image-20231104111158979](https://bbs.kanxue.com/upload/attach/202311/940967_FV6AC424K65UVQH.png)

完整的hook代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158 | `function` `hook_js(){``Java.perform(``function``(){``var` `enrandomcode = Java.use(``"com.kanxue.algorithmbase.MainActivity"``)``//如果定义好了``if``(enrandomcode !=undefined)``{``console.log(``"开始JAVA层Hook"``);``enrandomcode.encodeFromJni_12.implementation =` `function``(intput){``var` `res =` `this``.encodeFromJni_12(intput);``console.log(``"传入参数是====>"``+intput);``console.log(``"加密后的参数是====>"``+res);``return` `res;``}` `}` `})` `}` `function` `hook_native(){``Java.perform(``function``(){``var` `base_address = Module.getBaseAddress(``"libnative-lib.so"``);``if``(base_address !=undefined){``console.log(``"开始native层hook"``);``//定位拦截位置``var` `sub_8B04 = base_address.add(0x8B04+1);``console.log(``"sub_8b04:"``,sub_8B04)``if``(sub_8B04){``console.log(``"进入native层0x8B04"``);``}``else``{``console.log(``"拦截器加载失败"``);``}``//使用拦截器``Interceptor.attach(sub_8B04,{``//开始进入函数,传入了三个参数依次打印``onEnter:``function``(args){` `//保存第一个参数``this``.arg0 = args[0];``this``.arg1 = args[1];``this``.arg2 = args[2];` `console.log(``"========>ENTER<========"``);``// console.log("sub_8B04未初始化时第一个参数是===>"+this.arg0.readCString());``// console.log("sub_8B04未初始化时第二个参数是===>"+this.arg1.readCString());``//console.log("sub_8B04未初始化时第三个参数是===>"+hexdump(this.arg2,{length:64,header:false}));``var` `hook_aAyzpq23ijrtffg = base_address.add(0x1B000);` `if``(hook_aAyzpq23ijrtffg!=undefined){console.log(``"aAyzpq23ijrtffg进入8B04的形状=====>"``+hook_aAyzpq23ijrtffg.readCString().length())};`  `},``onLeave:``function``(result){``console.log(``"========>LEAVE<========"``);``// console.log("sub_8B04已经初始化时第一个参数是===>"+hexdump(this.arg0,{length:64,header:false}));``// console.log("sub_8B04已经初始化时第二个参数是===>"+hexdump(this.arg1,{length:64,header:false}));``//console.log("sub_8B04已经初始化时第三个参数是===>"+hexdump(this.arg2,{length:64,header:false}));``}``}``)``}``})``}` `function` `hookencodeFromJni(){``Java.perform(``function``(){``var` `base_address = Module.getBaseAddress(``"libnative-lib.so"``);``var` `base_address_method = Module.findExportByName(``"libnative-lib.so"``,``"Java_com_kanxue_algorithmbase_MainActivity_encodeFromJni_112"``)``if``(base_address_method!=undefined)``{``console.log(``"=======>进入初始界面进行Hook<======="``);``//使用拦截器``Interceptor.attach(base_address_method,{``onEnter:``function``(args){``//打印我们想要的param1和param2``// console.log("args[0]===>"+args[0]);``// console.log("args[1]===>"+args[1]);` `// console.log("args[2]===>"+args[2]);``// console.log("args[3]===>"+args[3]);``var` `hook_aAyzpq23ijrtffghijklmn = base_address.add(0x1B000+1);``console.log(``"aAyzpq23ijrtffghijklmn在导出函数里面=====>"``+hook_aAyzpq23ijrtffghijklmn.readCString());` `},``onLeave:``function``(nreval){``nreval.replace(0);``console.log(nreval);``}` `})` `}` `})`  `}`  `function` `hook_native_sub_8B04(){``Java.perform(``function``(){``var` `base_address = Module.getBaseAddress(``"libnative-lib.so"``);``if``(base_address !=undefined){``console.log(``"开始native层hook"``);``//定位拦截位置``var` `sub_8B04 = base_address.add(0x8B04+1);``if``(sub_8B04){``console.log(``"进入native层0x8B04"``);``}``else``{``console.log(``"拦截器加载失败"``);``}``//使用拦截器``Interceptor.attach(sub_8B04,{``//开始进入函数,传入了三个参数依次打印``onEnter:``function``(args){` `//保存第一个参数``this``.arg0 = args[0];``this``.arg1 = args[1];``this``.arg2 = args[2];``console.log(``"========>ENTER<========"``);``// console.log("sub_8B04未初始化时第一个参数是===>"+hexdump(this.arg0,{length:32,header:false}));``// console.log("sub_8B04未初始化时第一个参数是===>"+hexdump(this.arg1,{length:32,header:false}));``//console.log("sub_8B04未初始化时第一个参数是===>"+hexdump(this.arg2,{length:32,header:false}));``var` `hook_aAyzpq23ijrtffg = base_address.add(0x1B000);``if``(hook_aAyzpq23ijrtffg!=undefined){console.log(``"aAyzpq23ijrtffg进入8B04的形状=====>"``+hexdump(hook_aAyzpq23ijrtffg))};`   `},``onLeave:``function``(result){``console.log(``"========>LEAVE<========"``);``console.log(``"sub_8B04第一个参数处理后======>"``+hexdump(``this``.arg0));` `//打印处理后的第一个参数``//console.log("sub_8B04得到的结果是====>"+result.readCString());``// console.log("sub_8B04处理后第一个参数是===>"+hexdump(this.arg0,{length:32,header:false}));``console.log(``"sub_8B04处理后时第一个参数是===>"``+result);``// console.log("sub_8B04处理后时第一个参数是===>"+hexdump(this.arg2,{length:32,header:false}));` `}``})``}``})``}`     `function` `main(){` `hook_js();``hook_native_sub_8B04()``hook_native();``hookencodeFromJni()``}` `setImmediate(main);` |
|-|-|

使用C++还原加密流程

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133 | `#include <iostream>``#include <memory>``#include <Windows.h>` `#include <minwindef.h>``#include <rpcndr.h>``#include <intsafe.h>``#include <iostream>``#include <sstream>``#include <string>``#include <vector>``#define  _DWORD DWORD` `using` `namespace` `std;``DWORD` `v16[2] = { 1, 2 };` `// 将数组的所有元素初始化为0` `string Hex2Ascii(string input) {``std::stringstream ss(input);``std::string token;``std::vector<``char``> characters;` `while` `(std::getline(ss, token,` `' '``)) {``int` `ascii = std::stoi(token, nullptr, 16);``char` `c =` `static_cast``<``char``>(ascii);``characters.push_back(c);``}` `std::string result(characters.begin(), characters.end());``return` `result;`  `}`  `unsigned` `char``* sub_8B04(``int` `a1,` `int` `a2,` `int` `a3)``{``int` `v3 =0;` `// r12``int` `v6 =0;` `// r6``int` `v7 =0;` `// r5``unsigned` `char``* v8 =` `new` `unsigned` `char``[100];` `// r3``unsigned` `char``* address = v8;``//保存v8的首地址``memset``(v8,` `'\0'``, 100);` `// 将 v8 的所有元素都设置为 '1'``int` `v9 =0;` `// r2``unsigned` `int` `v10 =0;` `// r0``char` `v11 =``'\0'``;` `// r4``int` `v12 =0;` `// r6``char` `v13 =``'\0'``;` `// r1``std::string input =` `"52 4a 49 63 62 21 20 5a 59 61 47 55 75 74 7b 7a 79 78 7f 50 57 56 22 58 5f 5e 7e 51 77 76 60 67 46 26 25 24 2b 54 5b 69 23 70 66 65 64 72 71 5d 2a 38 3c 45 44 4b 7d 7c 5c 43 42 41 40 6b 6a 27"``;``string aAyzpq23ijrtffg = Hex2Ascii(input);` `v3 = a3 - 2;``v6 = 0;``v7 = 0;``while` `(1)``{` `v8 = (unsigned` `__int8``*)(address + v6);``if` `(v7 >= v3)``break``;``v9 = a2 + v7;` `//开始出现a2(传进来的参数)``v6 += 4;``*v8 = aAyzpq23ijrtffg[*(unsigned` `__int8``*)(a2 + v7) >> 2];``v10 = *(unsigned` `__int8``*)(a2 + v7 + 1);``v11 = *(unsigned` `char``*)(a2 + v7);``v7 += 3;``v8[1] = aAyzpq23ijrtffg[(v10 >> 4) & 0xFFFFFFCF \| (16 * (v11 & 3))];``v8[2] = aAyzpq23ijrtffg[(*(unsigned` `__int8``*)(v9 + 2) >> 6) & 0xFFFFFFC3 \| (4 * (*(unsigned` `char``*)(v9 + 1) & 0xF))];``v8[3] = aAyzpq23ijrtffg[*(unsigned` `char``*)(v9 + 2) & 0x3F];`   `}``if` `(v7 < a3)``{``*v8 = aAyzpq23ijrtffg[*(unsigned` `__int8``*)(a2 + v7) >> 2];``v12 = (16 * *(unsigned` `__int8``*)(a2 + v7)) & 0x30;``if` `(a3 - 1 == v7)``{``v13 = 61;``v8[1] = aAyzpq23ijrtffg[v12];``}``else``{``v8[1] = aAyzpq23ijrtffg[v12 \| (*(unsigned` `__int8``*)(a2 + v7 + 1) >> 4)];``v13 = aAyzpq23ijrtffg[4 * (*(unsigned` `__int8``*)(a2 + v7 + 1) & 0xF)];``}` `v8[2] = v13;``v8[3] = 61;``v8 += 4;``}``*v8 = 0;``return` `&v8[-a1 + 1];``}`  `__int64` `sub_882C(``__int64` `result)``{``int` `i;` `// r2` `result &= 0xFFFFFFFFFFFFFFFFULL;` `// 将result的低64位保留，高64位设置为0``for` `(i = 0; i != 3; ++i)``*(_DWORD*)(result + 4 * i) = 0;``return` `result;`  `}``DWORD``* sub_8740(``__int64` `a1)``{``int` `v1=0;` `// r4` `v1 = a1;``*(_DWORD*)a1 = 0;``*(_DWORD*)(a1 + 4) = 0;``*(_DWORD*)(a1 + 8) = 0;``sub_882C(a1);``return` `(_DWORD*)v1;``}`   `int` `main()``{`  `char` `str1[] =` `"xVjHx-D&nji8i*rBZ)j"``;``string str(str1);``int` `n = str.length();``int` `param2 = 0;``char``* v17=nullptr;``v17 = (``char``*)param2;` `unsigned` `char``* str2 = sub_8B04(``int``(``""``), (``int``)str1, n);` `}` |
|-|-|

![image-20231104111904900](https://bbs.kanxue.com/upload/attach/202311/940967_RGZ8WNNR2N74ENS.png)

使用JS对加密算法进行还原

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071 | `function` `Hex2Ascii(string){``var` `hexArray = string.split(``" "``);` `// 拆分字符串为数组` `var` `asciiArray = hexArray.map(``function``(hex) {``var` `decimal = parseInt(hex, 16);` `// 将16进制数转换为10进制数``return` `String.fromCharCode(decimal);` `// 将10进制数转换为对应的ASCII字符``});``var` `result = asciiArray.join(``""``);` `// 将字符数组合并为一个字符串``return` `result;``}` `function` `stringToUint8Array(str){``var` `arr = [];``for` `(``var` `i=0;i<str.length;i++)``{``arr.push(str.charCodeAt(i));``}` `var` `outputbytes =` `new` `Uint8Array(arr);``return` `outputbytes;``}` `function` `sub_8B04(str,len){``var` `string =` `"52 4a 49 63 62 21 20 5a 59 61 47 55 75 74 7b 7a 79 78 7f 50 57 56 22 58 5f 5e 7e 51 77 76 60 67 46 26 25 24 2b 54 5b 69 23 70 66 65 64 72 71 5d 2a 38 3c 45 44 4b 7d 7c 5c 43 42 41 40 6b 6a 27"``var` `aAyzpq23ijrtffg = Hex2Ascii(string);` `//生成码表``var` `v8 =``""``;``var` `v3 = len-2;``var` `v6 =0;``var` `v7=0;``var` `v9=0;``var` `v12 =0;``var` `a2 = stringToUint8Array(str);``while` `(1){``if` `(v7>=v3){``break``;``}``v9 = a2[v7];``var` `v9_1 = a2[v7+1];``var` `v9_2 =a2[v7+2];``v6 +=4;``v8 += aAyzpq23ijrtffg.charAt(a2[v7] >>2 );``var` `v10 = a2[v7+1];``var` `v11 = a2[v7];``v7 +=3;``v8 += aAyzpq23ijrtffg.charAt((v10>>4)&0xFFFFFFCF \|(16* (v11 &3)));``v8 += aAyzpq23ijrtffg.charAt(((v9_2) >>6)& 0xFFFFFFC3 \| 4*((v9_1)&0xF));``v8 += aAyzpq23ijrtffg[(v9_2)&0x3F]``}` `if``(v7 <len){``v8+=aAyzpq23ijrtffg[a2[v7]];``v12 =(16 * a2[v7])&0x03;``if` `(len -1 ==v7){``var` `v13 = 61;``v8 += aAyzpq23ijrtffg[v12];``}``else` `{``v8 +=aAyzpq23ijrtffg[v12 \| (a2[v7+1]) >>4];``v13 = aAyzpq23ijrtffg[4*a2[v7+1] & 0xF]``}``v8 += String.fromCharCode(v13);``v8 += String.fromCharCode(61);``return` `v8;`  `}` `}` `var` `str =` `"xVjHx-D&nji8i*rBZ)j"``;``console.log(sub_8B04(str,str.length))` |
|-|-|

![image-20231104111644647](https://bbs.kanxue.com/upload/attach/202311/940967_74FCUJCRYTJZKNG.png)

使用python还原加密流程

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354 | `def` `Hex2Ascii(string):``hex_list` `=` `string.split()` `# 分割字符串生成包含十六进制数的列表` `ascii_list` `=` `[]``for` `hex_str` `in` `hex_list:``decimal` `=` `int``(hex_str,` `16``)` `# 将十六进制数转换为十进制数``ascii_char` `=` `chr``(decimal)` `# 将十进制数转换为ASCII字符``ascii_list.append(ascii_char)` `result` `=` `''.join(ascii_list)` `# 将ASCII字符列表合并为一个字符串``return`  `result` `def` `sub_8B04(``str``,``len``):``string` `=` `"52 4a 49 63 62 21 20 5a 59 61 47 55 75 74 7b 7a 79 78 7f 50 57 56 22 58 5f 5e 7e 51 77 76 60 67 46 26 25 24 2b 54 5b 69 23 70 66 65 64 72 71 5d 2a 38 3c 45 44 4b 7d 7c 5c 43 42 41 40 6b 6a 27"``# 生成码表``aAyzpq23ijrtffg` `=` `Hex2Ascii(string)``v8` `=``""``v3` `=` `len``-``2``v6` `=``0``v7``=``0``v9``=``0``a2` `=` `bytes(``str``,``"utf-8"``)``while` `True``:``if` `v7>``=``v3:``break``v9``=``a2[v7]``v9_1` `=` `a2[v7``+``1``]``v9_2` `=``a2[v7``+``2``]``v6``+``=``4``v8` `+``=` `aAyzpq23ijrtffg[a2[v7] >>``2``]``v10` `=``a2[v7``+``1``]``v11` `=` `a2[v7]``v7``+``=``3``v8``+``=``aAyzpq23ijrtffg[(v10>>``4``)&``0xFFFFFFCF` `\|(``16``*` `(v11 &``3``))]``v8``+``=``aAyzpq23ijrtffg[((v9_2) >>``6``)&` `0xFFFFFFC3` `\|` `4``*``((v9_1)&``0xF``)]``v8``+``=``aAyzpq23ijrtffg[(v9_2)&``0x3F``]``if` `v7<``len``:``v8` `+``=` `aAyzpq23ijrtffg[a2[v7] >>``2``]``v12` `=` `(``16``*` `a2[v7]) &``0x30``if``(``len` `-``1` `=``=` `v7):``v13` `=``61``v8` `+``=``aAyzpq23ijrtffg[v12]``else``:``v8``+``=``aAyzpq23ijrtffg[v12 \| (a2[v7``+``1``]) >>``4``]``v13` `=` `aAyzpq23ijrtffg[``4``*``a2[v7``+``1``] &``0xF``]``v8``+``=``chr``(v13)``v8``+``=``chr``(``61``)``return` `v8`  `if` `__name__` `=``=` `'__main__'``:``str1``=``"xVjHx-D&nji8i*rBZ)j"``result``=``sub_8B04(str1,``len``(str1))``print``(result)` |
|-|-|

![image-20231104112034664](https://bbs.kanxue.com/upload/attach/202311/940967_FUZJKCQEXHT9QS9.png)

# 题目三:

## JAVA层

`algorithmbase_13.apk`

使用`JADX`打开`apk`文件

![image-20231104215709725](https://bbs.kanxue.com/upload/attach/202311/940967_XK5V4SECH7FM8CV.png)

通过调用MainActivity类中的encodeFromJni_12方法，将randomAscii字符串进行加密，并将加密后的结果存储在encodeFromJni_12字符串中。然后，使用Log.e方法将randomAscii字符串和加密后的结果一起打印出来，以便进行调试和分析。

## SO

使用`IDA`打开，按照以前的思路继续从下往上分析

按照第二题的思路，来到`sub_8B04`

![image-20231104220620285](https://bbs.kanxue.com/upload/attach/202311/940967_PJT4YQE5A9ABGDK.png)

发现和上一题加密没啥区别就只是多了和参数`a3`的异或

使用`Frida Hook` 一下传入参数和传出参数

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061 | `function` `hook_js(){``Java.perform(``function``(){``var` `enrandomcode = Java.use(``"com.kanxue.algorithmbase.MainActivity"``)``//如果定义好了``if``(enrandomcode !=undefined)``{``console.log(``"开始JAVA层Hook\r\n"``);``enrandomcode.encodeFromJni_13.implementation =` `function``(intput){``var` `res =` `this``.encodeFromJni_13(intput);``console.log(``"\n传入参数是====>"``+intput);``console.log(``"加密后的参数是====>"``+res);``return` `res;``}` `}``})` `}` `function` `hook_native(){``Java.perform(``function``(){``var` `base_address = Module.getBaseAddress(``"libnative-lib.so"``);``if``(base_address!=undefined)``{``console.log(``"获取到基地址"``);``var` `sub_8B04=base_address.add(0x8B04+1);``//开启拦截器``Interceptor.attach(sub_8B04,{``onEnter:``function``(args){``this``.arg0 = args[0];``this``.arg1 = args[1];``this``.arg2 = args[2];``console.log(``"sub_80B4传进来的第一个参数是===>"``+``this``.arg0.readCString());``console.log(``"sub_80B4传进来的第二个参数是===>"``+``this``.arg1.readCString());``//console.log("sub_80B4传进来的第三个参数是===>"+this.arg2.readCString());``var` `sub_1B000 = base_address.add(0x1B000);``if``(sub_1B000!=undefined){``console.log(``"aAyzpq23ijrtffg===>"``+ hexdump(sub_1B000));` `}`  `},onLeave:``function``(nresult){``console.log(``"sub_80B4对传入参数处理后的结果是===>"``+nresult);``console.log(``"sub_80B4对传入参数处理后的结果是===>"``+``this``.arg0.readCString());` `}``})``}` `})``}`   `function` `main(){` `hook_js();``hook_native();``}` `setImmediate(main);` |
|-|-|

![image-20231104220256358](https://bbs.kanxue.com/upload/attach/202311/940967_Y7YU7X34B8SFXEJ.png)

| 123456789101112131415161718192021222324 | `[LGE Nexus` `5X``::com.kanxue.algorithmbase]``-``> 开始JAVA层Hook` `获取到基地址``sub_80B4传进来的第一个参数是``=``=``=``>``sub_80B4传进来的第二个参数是``=``=``=``>cPN~zk)\|Kpehw7zZn;PU6Gg_kj``*``[Z``aAyzpq23ijrtffg``=``=``=``>` `0`  `1`  `2`  `3`  `4`  `5`  `6`  `7`  `8`  `9`  `A  B  C  D  E  F` `0123456789ABCDEF``ca86a000` `5c` `44` `47` `6d` `6c` `2f` `2e` `54` `57` `6f` `49` `5b` `7b` `7a` `75` `74`  `\DGml``/``.TWoI[{zut``ca86a010` `77` `76` `71` `5e` `59` `58` `2c` `56` `51` `50` `70` `5f` `79` `78` `6e` `69`  `wvq^YX,VQPp_yxni` `ca86a020` `48` `28` `2b` `2a` `25` `5a` `55` `67` `2d` `7e` `68` `6b` `6a` `7c` `7f` `53`  `H(``+``*``%``ZUg``-``~hkj\|.S``ca86a030` `24` `36` `32` `4b` `4a` `45` `73` `72` `52` `4d` `4c` `4f` `4e` `65` `64` `29`  `$``62KJEsrRMLONed``)``ca86a040` `00` `00` `00` `00` `fd` `91` `85` `ca d9` `92` `85` `ca b8` `47` `86` `ca  .............G..``ca86a050` `78` `a2` `86` `ca` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `x...............``ca86a060` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `................``ca86a070` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `................``ca86a080` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `................``ca86a090` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `................``ca86a0a0` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `................``ca86a0b0` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `................``ca86a0c0` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `................``ca86a0d0` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `................``ca86a0e0` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `................``ca86a0f0` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00` `00`  `................``sub_80B4对传入参数处理后的结果是``=``=``=``>``0x29``sub_80B4对传入参数处理后的结果是``=``=``=``>LEYutgckTV``+``[d.E``-``eKeL1UOOD``/``Dskseims0h,E``-``=` |
|-|-|

hook的结果更加验证了我们的思路

直接开始还原算法验证

C++代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131 | `#include <iostream>``#include <memory>``#include <Windows.h>` `#include <minwindef.h>``#include <rpcndr.h>``#include <intsafe.h>``#include <iostream>``#include <sstream>``#include <string>``#include <vector>``#define  _DWORD DWORD` `using` `namespace` `std;``DWORD` `v16[2] = { 1, 2 };` `// 将数组的所有元素初始化为0` `string Hex2Ascii(string input) {``std::stringstream ss(input);``std::string token;``std::vector<``char``> characters;` `while` `(std::getline(ss, token,` `' '``)) {``int` `ascii = std::stoi(token, nullptr, 16);``char` `c =` `static_cast``<``char``>(ascii);``characters.push_back(c);``}` `std::string result(characters.begin(), characters.end());``return` `result;`  `}``unsigned` `char``* sub_8B04(``int` `a1,` `int` `a2,` `int` `a3)``{``int` `v3 = 0;` `// r12``int` `v6 = 0;` `// r6``int` `v7 = 0;` `// r5``unsigned` `char``* v8 =` `new` `unsigned` `char``[100];` `// r3``unsigned` `char``* address = v8;``//保存v8的首地址` `memset``(v8,` `'\0'``, 100);` `// 将 v8 的所有元素都设置为 '1'`  `int` `v9 = 0;` `// r2``unsigned` `int` `v10 = 0;` `// r0``char` `v11 =` `'\0'``;` `// r4``int` `v12 = 0;` `// r6``char` `v13 =` `'\0'``;` `// r1``std::string input =` `"5c 44 47 6d 6c 2f 2e 54 57 6f 49 5b 7b 7a 75 74 77 76 71 5e 59 58 2c 56 51 50 70 5f 79 78 6e 69 48 28 2b 2a 25 5a 55 67 2d 7e 68 6b 6a 7c 7f 53 24 36 32 4b 4a 45 73 72 52 4d 4c 4f 4e 65 64 29"``;``string aAyzpq23ijrtffg = Hex2Ascii(input);` `v3 = a3 - 2;``v6 = 0;``v7 = 0;``while` `(1)``{` `v8 = (unsigned` `__int8``*)(address + v6);``if` `(v7 >= v3)``break``;``v9 = a2 + v7;` `//开始出现a2(传进来的参数)``v6 += 4;``*v8 = aAyzpq23ijrtffg[*(unsigned` `__int8``*)(a2 + v7) >> 2] ^a3;``v10 = *(unsigned` `__int8``*)(a2 + v7 + 1);``v11 = *(unsigned` `char``*)(a2 + v7);``v7 += 3;``v8[1] = aAyzpq23ijrtffg[(v10 >> 4) & 0xFFFFFFCF \| (16 * (v11 & 3))];``v8[2] = aAyzpq23ijrtffg[(*(unsigned` `__int8``*)(v9 + 2) >> 6) & 0xFFFFFFC3 \| (4 * (*(unsigned` `char``*)(v9 + 1) & 0xF))] ^ a3;``v8[3] = aAyzpq23ijrtffg[*(unsigned` `char``*)(v9 + 2) & 0x3F];``}``if` `(v7 < a3)``{``*v8 = aAyzpq23ijrtffg[*(unsigned` `__int8``*)(a2 + v7) >> 2];``v12 = (16 * *(unsigned` `__int8``*)(a2 + v7)) & 0x30;``if` `(a3 - 1 == v7)``{``v13 = 61;``v8[1] = aAyzpq23ijrtffg[v12];``}``else``{``v8[1] = aAyzpq23ijrtffg[v12 \| (*(unsigned` `__int8``*)(a2 + v7 + 1) >> 4)];``v13 = aAyzpq23ijrtffg[4 * (*(unsigned` `__int8``*)(a2 + v7 + 1) & 0xF)];``}` `v8[2] = v13;``v8[3] = 61;``v8 += 4;``}``*v8 = 0;``return` `&v8[-a1 + 1];``}`  `__int64` `sub_882C(``__int64` `result)``{``int` `i;` `// r2` `result &= 0xFFFFFFFFFFFFFFFFULL;` `// 将result的低64位保留，高64位设置为0``for` `(i = 0; i != 3; ++i)``*(_DWORD*)(result + 4 * i) = 0;``return` `result;`  `}` `DWORD``* sub_8740(``__int64` `a1)``{``int` `v1 = 0;` `// r4` `v1 = a1;``*(_DWORD*)a1 = 0;``*(_DWORD*)(a1 + 4) = 0;``*(_DWORD*)(a1 + 8) = 0;``sub_882C(a1);``return` `(_DWORD*)v1;``}`  `int` `main()``{` `char` `str1[] =` `"cPN~zk)\|Kpehw7zZn;PU6Gg_kj*[Z"``;``string str(str1);``int` `n = str.length();``int` `param2 = 0;``char``* v17 = nullptr;``v17 = (``char``*)param2;``unsigned` `char``* str2 = sub_8B04(``int``(``""``), (``int``)str1, n);``std::cout << str2 << std::endl;` `}` |
|-|-|

![image-20231104220755239](https://bbs.kanxue.com/upload/attach/202311/940967_JJFHY88Y2G4V4DE.png)

JS代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172 | `function` `Hex2Ascii(string){``var` `hexArray = string.split(``" "``);` `// 拆分字符串为数组` `var` `asciiArray = hexArray.map(``function``(hex) {``var` `decimal = parseInt(hex, 16);` `// 将16进制数转换为10进制数``return` `String.fromCharCode(decimal);` `// 将10进制数转换为对应的ASCII字符``});``var` `result = asciiArray.join(``""``);` `// 将字符数组合并为一个字符串``return` `result;``}` `function` `stringToUint8Array(str){``var` `arr = [];``for` `(``var` `i=0;i<str.length;i++)``{``arr.push(str.charCodeAt(i));``}` `var` `outputbytes =` `new` `Uint8Array(arr);``return` `outputbytes;``}` `function` `sub_8B04(str,len){``var` `string =` `"5c 44 47 6d 6c 2f 2e 54 57 6f 49 5b 7b 7a 75 74 77 76 71 5e 59 58 2c 56 51 50 70 5f 79 78 6e 69 48 28 2b 2a 25 5a 55 67 2d 7e 68 6b 6a 7c 7f 53 24 36 32 4b 4a 45 73 72 52 4d 4c 4f 4e 65 64 29"``;``var` `aAyzpq23ijrtffg = Hex2Ascii(string);` `//生成码表``var` `v8 =``""``;``var` `v3 = len-2;``var` `v6 =0;``var` `v7=0;``var` `v9=0;``var` `v12 =0;``var` `a2 = stringToUint8Array(str);``var` `a3 = len;``while` `(1){``if` `(v7>=v3){``break``;``}``v9 = a2[v7];``var` `v9_1 = a2[v7+1];``var` `v9_2 =a2[v7+2];``v6 +=4;``v8 += String.fromCharCode(aAyzpq23ijrtffg.charCodeAt(a2[v7] >>2 ) ^ a3);``var` `v10 = a2[v7+1];``var` `v11 = a2[v7];``v7 +=3;``v8 += aAyzpq23ijrtffg.charAt((v10>>4)&0xFFFFFFCF \|(16* (v11 &3))) ;``v8 += String.fromCharCode(aAyzpq23ijrtffg.charCodeAt(((v9_2) >>6)& 0xFFFFFFC3 \| 4*((v9_1)&0xF)) ^ a3);``v8 += aAyzpq23ijrtffg[(v9_2)&0x3F]``}` `if``(v7 <a3){``v8+=aAyzpq23ijrtffg[a2[v7] >>2];``v12 =(16 * a2[v7])& 0x30;``if` `(len -1 ==v7){``var` `v13 = 61;``v8 += aAyzpq23ijrtffg[v12];``}``else` `{``v8 +=aAyzpq23ijrtffg[v12 \| (a2[v7+1]) >>4];``v13 = aAyzpq23ijrtffg[4*(a2[v7+1] & 0xF)]``}``v8 += v13;``v8 += String.fromCharCode(61);``return` `v8;`  `}` `}` `var` `str =` `"cPN~zk)\|Kpehw7zZn;PU6Gg_kj*[Z"``;``console.log(sub_8B04(str,str.length))` |
|-|-|

![image-20231104224728140](https://bbs.kanxue.com/upload/attach/202311/940967_AK675BXHRDYMUYN.png)

python代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657 | `def` `Hex2Ascii(string):``hex_list` `=` `string.split()` `# 分割字符串生成包含十六进制数的列表` `ascii_list` `=` `[]``for` `hex_str` `in` `hex_list:``decimal` `=` `int``(hex_str,` `16``)` `# 将十六进制数转换为十进制数``ascii_char` `=` `chr``(decimal)` `# 将十进制数转换为ASCII字符``ascii_list.append(ascii_char)` `result` `=` `''.join(ascii_list)` `# 将ASCII字符列表合并为一个字符串``return`  `result` `def` `sub_8B04(``str``,``len``):``string` `=` `"5c 44 47 6d 6c 2f 2e 54 57 6f 49 5b 7b 7a 75 74 77 76 71 5e 59 58 2c 56 51 50 70 5f 79 78 6e 69 48 28 2b 2a 25 5a 55 67 2d 7e 68 6b 6a 7c 7f 53 24 36 32 4b 4a 45 73 72 52 4d 4c 4f 4e 65 64 29"``;``# 生成码表``aAyzpq23ijrtffg` `=` `Hex2Ascii(string)``v8` `=``""``v3` `=` `len``-``2``v6` `=``0``v7``=``0``v9``=``0``a2` `=` `bytes(``str``,``"utf-8"``)``a3` `=` `len`  `while` `True``:``if` `v7>``=``v3:``break``v9``=``a2[v7]``v9_1` `=` `a2[v7``+``1``]``v9_2` `=``a2[v7``+``2``]``v6``+``=``4``v8` `+``=` `chr``(``ord``(aAyzpq23ijrtffg[a2[v7] >>``2``]) ^ a3)``v10` `=``a2[v7``+``1``]``v11` `=` `a2[v7]``v7``+``=``3``v8``+``=``aAyzpq23ijrtffg[(v10>>``4``)&``0xFFFFFFCF` `\|(``16``*` `(v11 &``3``))]``v8``+``=` `chr``(``ord``(aAyzpq23ijrtffg[((v9_2) >>``6``)&` `0xFFFFFFC3` `\|` `4``*``((v9_1)&``0xF``)])^ a3)``v8``+``=``aAyzpq23ijrtffg[(v9_2)&``0x3F``]``if` `v7<a3:``v8` `+``=` `aAyzpq23ijrtffg[a2[v7] >>``2``]``v12` `=` `(``16``*` `a2[v7]) &``0x30``if``(a3` `-``1` `=``=` `v7):``v13` `=``61``v8` `+``=``aAyzpq23ijrtffg[v12]``else``:``v8``+``=``aAyzpq23ijrtffg[v12 \| (a2[v7``+``1``]) >>``4``]``v13` `=` `aAyzpq23ijrtffg[``4``*``(a2[v7``+``1``] &``0xF``)]``v8``+``=``v13``v8``+``=``chr``(``61``)``return` `v8`  `if` `__name__` `=``=` `'__main__'``:``str1``=``"cPN~zk)\|Kpehw7zZn;PU6Gg_kj*[Z"``result``=``sub_8B04(str1,``len``(str1))``print``(result)` |
|-|-|

![image-20231104231103817](https://bbs.kanxue.com/upload/attach/202311/940967_NSH7TAD9UE8HJ8F.png)

# JS还原C++函数总结

#### 字符串篇

#### C++字符串型的传参在JS中的变化

C++的函数传参是如果char数组,当使用`JS`对其进行还原时候，为了方便后面字符串型参数在`JS`中计算字符串偏移，最好把字符串转为8位无符号整型数组**Uint8Array**（对应是`C++`中的(`unsigned char*`)）

如下

| 12345678910 | `function` `stringToUint8Array(str){``var` `arr = [];``for` `(``var` `i=0;i<str.length;i++)``{``arr.push(str.charCodeAt(i));``}` `var` `outputbytes =` `new` `Uint8Array(arr);``return` `outputbytes;``}` |
|-|-|

这么看不太直观。拿刚才的第三题举例
C++中

| 1234567 | `char` `str1[] =` `"cPN~zk)\|Kpehw7zZn;PU6Gg_kj*[Z"``;``string str(str1);``int` `n = str.length();``int` `param2 = 0;``char``* v17 = nullptr;``v17 = (``char``*)param2;``unsigned` `char``* str2 = sub_8B04(``int``(``""``), (``int``)str1, n);` |
|-|-|

这里面**str1**是char数组被强转为整型当成传参进入的`sub_8B04` 函数

但在`JS`中，我们进入`sub_8B04` 就是传参**str**是字符串，不需要变整型

![image-20231105115216312](https://bbs.kanxue.com/upload/attach/202311/940967_C9QHA9QNUNXD6EN.png)

为了方便后面的字节偏移计算，我们再把字符串**str** 转为**8**位无符号整型数组

| 1 | `var` `a2 = stringToUint8Array(str);` |
|-|-|

#### C++ 函数里面与字符串类型传参相关的参数 在JS中的还原

| 12345 | `unsigned` `char``* sub_8B04(``int` `a1,` `int` `a2,` `int` `a3)``{` `int` `v7 = 0;` `// r5``v9 = a2 + v7;` `//开始出现a2(传进来的参数)``}` |
|-|-|

在JS中还原C++函数**sub_8B04**里面的参数V9思路:

因为`a2` 原先是被int强转char数组。v9是(`char*`)a2数组偏移v7个字节后的参数
在前面的步骤中，a2在JS中已经被我们设置为8位无符号整型数组，所以v9=a2[v7]

| 1234 | `function` `sub_8B04(str,len){``var` `a2 = stringToUint8Array(str);``v9 = a2[v7];``}` |
|-|-|

根据这个思路

使用JS还原一下C++代码中* (unsigned __int8*)(v9 + 2) 和 * (unsigned __int8*)(v9 + 2) 代码如下

| 12 | `var` `v9_1 = a2[v7+1];``var` `v9_2 =a2[v7+2];` |
|-|-|

#### 字节运算

由于JS语言的特性，不能直接把字符和数字进行直接的运算，所以要把字符转为`Unicode` 编码与数字进行运算后，再把得到的结果重新转为字符

需要用js的`charat` `charCodeAt` `fromCharCode` 三个函数进行转化这里面贴一下介绍

>
> `charAt` 方法用于返回指定索引位置的字符。索引位置从0开始计数。
>
>
> 语法: `string.charAt(index)`
>
>
> 示例:
>
>
> Copy
>
>
>
>
> | 123 | `var` `str =` `"Hello World"``;``console.log(str.charAt(0));` `// 输出 "H"``console.log(str.charAt(6));` `// 输出 "W"` |
> |-|-|
>
>
> `charCodeAt` 方法返回指定索引位置的字符的Unicode编码。索引位置从0开始计数。
>
>
> 语法: `string.charCodeAt(index)`
>
>
> 示例:
>
>
>
>
> | 123 | `var` `str =` `"Hello World"``;``console.log(str.charCodeAt(0));` `// 输出 72``console.log(str.charCodeAt(6));` `// 输出 87` |
> |-|-|
>
>
> `fromCharCode` 方法从Unicode编码创建一个字符串。
>
>
> 语法: `String.fromCharCode(number1, number2, ... , numberX)`
>
>
> 示例:
>
>
>
>
> | 1 | `console.log(String.fromCharCode(72, 101, 108, 108, 111));` `// 输出 "Hello"` |
> |-|-|
>
>
>

现在分析一下前面第三题贴的C代码

| 1 | `*v8 = aAyzpq23ijrtffg[*(unsigned` `__int8``*)(a2 + v7) >> 2] ^a3;` |
|-|-|

这段C代码的含义是将变量a2和v7的和作为地址，取出该地址处的一个字节数据，将其右移两位后转换为无符号8位整数，然后使用这个值作为索引，从数组aAyzpq23ijrtffg中取出对应位置的值，与变量a3进行异或操作，并将结果赋给变量v8。

在JS中`aAyzpq23ijrtffg[*(unsigned __int8*)(a2 + v7) >> 2]` 这个字符要和a3进行异或，a3是整型不能和字符异或，所以我们要把先把字符转为Unicode码再和a3进行异或运算，然后转为字符串如下

| 1 | `v8 += String.fromCharCode(aAyzpq23ijrtffg.charCodeAt(a2[v7] >>2 ) ^ a3);` |
|-|-|

# Python 还原C++函数总结

#### 字符串篇

#### C++字符串型的传参在python中的变化

C++的函数传参是如果char数组,当使用`python`对其进行还原时候，为了方便后面字符串型参数在`python`中计算字符串偏移，最好把字符串转为bytes数组（对应是`C++`中的(`unsigned char*`)）

如下

| 12 | `def` `sub_8B04(``str``,``len``):``a2` `=` `bytes(``str``,``"utf-8"``)` |
|-|-|

#### C++ 函数里面与字符串类型传参相关的参数 在python中的还原

| 12345 | `unsigned` `char``* sub_8B04(``int` `a1,` `int` `a2,` `int` `a3)``{` `int` `v7 = 0;` `// r5``v9 = a2 + v7;` `//开始出现a2(传进来的参数)``}` |
|-|-|

在python中还原C++函数**sub_8B04**里面的参数V9思路:

因为`a2` 原先是被int强转char数组。v9是(`char*`)a2数组偏移v7个字节后的参数
在前面的步骤中，a2在python中已经被我们设置为`bytes`数组，所以v9=a2[v7]

| 1 | `v9` `=` `a2[v7];` |
|-|-|

根据这个思路

使用python还原一下C++代码中* (unsigned __int8*)(v9 + 2) 和 * (unsigned __int8*)(v9 + 2) 代码如下

| 12 | `v9_1` `=` `a2[v7``+``1``]``v9_2` `=``a2[v7``+``2``]` |
|-|-|

#### 字节运算

由于python语言的特性，不能直接把字符和数字进行直接的运算，所以要把字符转为`Unicode` 编码与数字进行运算后，再把得到的结果重新转为字符

>
> chr和ord是Python中的内置函数，用于字符和对应的Unicode编码之间的转换。
>
>
> chr函数接受一个整数参数，返回对应的字符。例如：
>
>
>
>
> | 123 | `print``(``chr``(``65``))` `# 输出A``print``(``chr``(``97``))` `# 输出a``print``(``chr``(``8364``))` `# 输出€` |
> |-|-|
>
>
> ord函数接受一个字符参数，返回对应的Unicode编码。例如：
>
>
>
>
> | 123 | `print``(``ord``(``'A'``))` `# 输出65``print``(``ord``(``'a'``))` `# 输出97``print``(``ord``(``'€'``))` `# 输出8364` |
> |-|-|
>
>
> 通过chr和ord函数，我们可以方便地在字符和对应的Unicode编码之间进行转换。
>
>
>

现在分析一下前面第三题贴的C代码

| 1 | `*v8 = aAyzpq23ijrtffg[*(unsigned` `__int8``*)(a2 + v7) >> 2] ^a3;` |
|-|-|

这段C代码的含义是将变量a2和v7的和作为地址，取出该地址处的一个字节数据，将其右移两位后转换为无符号8位整数，然后使用这个值作为索引，从数组aAyzpq23ijrtffg中取出对应位置的值，与变量a3进行异或操作，并将结果赋给变量v8。

在python中`aAyzpq23ijrtffg[*(unsigned __int8*)(a2 + v7) >> 2]` 这个字符要和a3进行异或，a3是整型不能和字符异或，所以我们要把先把字符转为Unicode码再和a3进行异或运算，然后转为字符串如下

| 1 | `v8 += chr(ord(aAyzpq23ijrtffg[a2[v7] >>2]) ^ a3)` |
|-|-|

---

# 回复

## 回复 by 秋狝 (#2)

*2023-11-5 15:23*

感谢分享

## 回复 by 哇哈哈919 (#3)

*2023-11-5 17:23*

冯哥厉害！

## 回复 by 外交 (#4)

*2023-11-6 09:44*

支持楼主。

## 回复 by mb_fssslkzs (#5)

*2023-11-6 18:53*

感谢分享
