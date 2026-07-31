---
title: '[原创]入门实战-Rui幸app白盒aes'
url: https://bbs.kanxue.com/thread-289093.htm
tid: 289093
author: 卡卡骨
date: '2025-11-16'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T15:26:57+08:00'
replies: 63
---

# 寻找加密入口

 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_6K7QTSD9D9HBRRE.webp)
定位到 `libcryptoDD.so`文件
ida打开查看，发现不是静态注册
直接丢入`unidbg`,不做任何开启日志打印一下，发现了它的动态注册
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_NPUKAU7YP3BWXMZ.webp)
地址是0x41ed8， 上ida中按下G， 跳转到这个地址，到此我们发现了so中函数的入口
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_U5HGVBBMP9BFJN9.webp)

# 判断`aes`加密是什么类型

## 理论部分

- **ECB（Electronic Codebook）模式**：
	- `ECB`模式将数据分成块，然后对每个块进行独立的加密，不考虑上下文。这意味着相同的明文块会产生相同的密文块
	>
	> 将明文分组，解密后直接成为密文分组，分组之间没有关系
	>
	>
	>
- **CBC（Cipher Block Chaining）模式**：
	- `CBC`模式使用前一个块的密文作为当前块的初始向量（IV），从而在相同的明文块和相同的密钥下产生不同的密文块。这增加了安全性，因为每个块的加密依赖于前一个块的密文。`CBC`模式适用于大多数加密应用，包括文件加密和网络通信。

---

这里我是使用frida， hook,先打印一下参数

| 1234567 | `let CryptoHelper = Java.use(``"com.luckincoffee.safeboxlib.CryptoHelper"``);``CryptoHelper[``"localAESWork"``].implementation =` `function` `(bArr, i10, bArr2) {``console.log(`CryptoHelper.localAESWork is called: bArr=${bArr}, i10=${i10}, bArr2=${bArr2}`);``let result =` `this``[``"localAESWork"``](bArr, i10, bArr2);``// console.log(`CryptoHelper.localAESWork result=${result}`);``return` `result;``};` |
|-|-|

发现实际请求中 `bArr2`是固定的，且长度是`32`， 合理怀疑是`key`， 或者`iv`
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_8MBPMJJQQSX2ZXY.webp)

而i10值有时候是2， 有时候是3， 这个分析java层代码可以知道，应该就是标识不同类型的请求的
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_32P428234ZCHC4H.webp)

所`bArr`这里就是我们的`input_data`, 我们自己构造加密判断一下它到底是`ecb`还是`cbc`

| 12345678910111213141516171819 | `var` `fragInstances = [];``// 要查找的类名``const targetClassName =` `'com.luckincoffee.safeboxlib.CryptoHelper'``;``console.log(`[+] 开始扫描堆，查找所有 ${targetClassName} 实例...`);``Java.choose(targetClassName, {``onMatch:` `function` `(instance) {``fragInstances.push(instance);``},``onComplete:` `function` `() { }``});` `var` `frag = fragInstances && fragInstances.length > 0 ? fragInstances[0] :` `null``;``let v1 = Java.array(``'byte'``,` `new` `Array(32).fill(0))``let v2 = 2``let v3 = Java.array(``'byte'``, [-39,-11,119,92,32,-11,-15,28,107,-40,-69,-126,113,-96,42,-30,7,64,65,79,-113,48,84,98,-86,49,-120,-43,105,70,-49,55]);` `let res = frag.localAESWork(v1,v2,v3)` `console.log(``"res:"``, res)` |
|-|-|

返回内容如下：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_JYQAJ6U9DZE7M4F.webp)
至此， 可以得知，他是`ecb`加密，而且是`128`位的分组加密

# `unidbg`简单调试返回内容

将参数增加，`hook`调用一下`so`中的`localAESWork`这个函数看看是否存在问题
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_CHD7EA6BTPS7M9C.webp)

>
> 看到了出现了问题，这时候打印一下trace日志，看看问题出现的具体位置
>
>
>

| 1 | `androidEmulator.traceCode(cryptoDDmodule.base, cryptoDDmodule.base + cryptoDDmodule.size);` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_7TCKY7ZEP7X3MT7.webp)

>
> 可以清晰的看到，`pc`指针执行到`0x17e6c`的位置的时候，出现了错误
> 我们直接到`ida`中按下`G`， 找到这个位置看看具体什么情况
>
>
>

 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_2HHGCD2UD9R4X68.webp)
看到了，他是一个free函数
而`unidbg`本质是无法处理`free`函数的(虽然有的`so`中有`free`它有时候不报错，好像是因为`malloc`和`free`同时使用的原因？？？)
所以这里我们在`unidbg`中直接`hook`掉`free`函数的使用看看

| 12345678910111213 | `public` `void` `hookZz_hook_free_func() {` `System.out.println(``"hookZz_hook_free_func"``);` `// hook free函数` `HookZz hookZz = HookZz.getInstance(androidEmulator);` `Module module = memory.findModule(``"libc.so"``);` `hookZz.replace(module.findSymbolByName(``"free"``).getAddress(),` `new` `ReplaceCallback() {` `@Override` `public` `HookStatus onCall(Emulator<?> emulator, HookContext context,` `long` `originFunction) {` `return` `HookStatus.RET(emulator, context.getLR());` `// return super.onCall(emulator, context, originFunction);` `}` `});` `}` |
|-|-|

再次运行发现成功返回值
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_XPECK4RCXVQWXZY.webp)

此时，使用`unidbg`打印一次加密的完整trace留待后用

# unidbg + ida算法分析

返回值： `9b4174988fdd7be26d28bb9d970b63b9`
`trace`文件也拿到了

直接在trace文件中查找 `0xb9` 这个关键词，然后从后往前看，可以发现：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_2T33FR37P4XNWJ5.webp)

直接根据`trace`中这些点的`pc`地址，在`ida`中查找，可以找到这个位置

>
> 发现代码中存在大量的`while`, `if`, `elseif` 等控制语句
> 这种情况就是内部进行了控制流平坦化的混淆
>  ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_MJKZYQXYFK72VTJ.webp)
> 这里代码就对应了起来，这个函数是`sub_189C4`，在这里用`unidbg console debugger`下断点简单查看下
>  ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_G4NFKKH7JXPZRFG.webp)
> 其参数x0寄存器中存储的就是input_data值，
>
>
>

所以，`sub_189C4`这里应该就是`aes`函数的主要逻辑部分了

# `sub_189C4`函数分析

这里面的代码也是混淆过的，不太容易看出来具体逻辑
但是发现其中有一些高频出现的函数，比如
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_PUJQMN56AUVAXN3.webp)
这就和aes中的分组加密有点相似的意思了。

详细具体的查看一下几个高频函数内部逻辑

### `sub_219CC`

其中几乎都是异或操作，
是轮密钥加逻辑的可能性比较大
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_5VWCVEERMPEADQQ.webp)

### `sub_22810`

大量异或操作，
怀疑轮密钥加过程，也可能是列混淆过程
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_77VCQXV273MF4YP.webp)

### `sub_223E0`

看着有点像是行行位移操作
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_CMUVBACXC67E9ME.webp)

### `sub_21BEC`

这个就很明显了，字节代换
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_XKTQDCFAGJV7FTE.webp)

>
> 段落引用
> aes有`9`轮循环运算和`1`轮最终轮运算，
> 循环运算中又有四个板块 ：`字节代换`，`行位移`，`列混淆`，`轮密钥加`
> 最终轮缺少 `列混淆`
>
>
>

我需要查看一下一个加密过程中，这四个函数分别都被调用了多少次

直接在trace文件中进行搜索
0x219cc
0x223e0
0x21bec
0x22810
已经确定了`sub_21BEC`是字节代换的流程，先查找`pc`指针到`0x21bec`的次数
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_K6UC3E2CG2HY9YT.webp)
可以看到是10次
同理查找其他函数的次数，发现
0x219cc 33次
0x223e0 10次
0x21bec 10次
0x22810 9次
重点查看下`0x219cc` 次数这个，因为字节代换都是从`77841`行开始，所以`77841`行之前的`0x219cc`的计数不能算，
减去的话，就是刚好`10`次
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_N9T3ZK233MYUP9K.webp)

至此，这四个函数的整体逻辑也算是明白了

# 白盒AES差分攻击

>
> 这时候已经知道了四轮过程，只要通过dfa差分攻击即刻获取到aes的密钥值
>
>
>

![图片描述](https://bbs.kanxue.com/upload/attach/202511/1000016_YPXXA6DYQN2YGEJ.webp)

到这里算法分析就算是结束了，至于差分攻击如何使用，可以详细问问chatgpt

# 总结

整体分析流程涉及了jadx + unidbg + frida + ida + trace分析 + aes算法，
适合新手入门

---

# 回复

## 回复 by wx_插曲 (#2)

*2025-11-16 10:22*

大佬 牛逼

## 回复 by mb_ldbucrik (#3)

*2025-11-16 10:53*

感谢分享

## 回复 by 温泉划水鱼 (#4)

*2025-11-16 11:58*

66

## 回复 by 破绽百出 (#5)

*2025-11-16 13:50*

>
> [wx_插曲](https://bbs.kanxue.com/user-953711.htm)
>
>  大佬 牛逼
>
>

罗哥带我

## 回复 by FMNS (#6)

*2025-11-16 13:51*

666

## 回复 by KanXue_NG (#7)

*2025-11-16 14:52*

学习学习

## 回复 by NshIdE (#8)

*2025-11-16 16:20*

学习

## 回复 by daiviswang (#9)

*2025-11-16 18:39*

646546464644646

## 回复 by huangjw (#10)

*2025-11-17 09:32*

大佬非你莫属

## 回复 by jiyuren (#11)

*2025-11-17 09:53*

大佬非你莫属

## 回复 by passself (#12)

*2025-11-17 09:59*

666

## 回复 by mb_xjdhrmck (#13)

*2025-11-17 10:05*

666

## 回复 by edisonhu (#14)

*2025-11-17 10:15*

11

## 回复 by Imxz (#15)

*2025-11-17 10:31*

tql

## 回复 by 逆道而行 (#16)

*2025-11-17 10:32*

666

## 回复 by mb_qimctavn (#17)

*2025-11-17 10:32*

6

## 回复 by LQ6H (#18)

*2025-11-17 10:36*

666

## 回复 by mb_cbgtaveo (#19)

*2025-11-17 11:42*

6666

## 回复 by axpol (#20)

*2025-11-17 14:44*

666

## 回复 by mb_euhyowpw (#21)

*2025-11-17 15:41*

666

## 回复 by wx_霿凇 (#22)

*2025-11-17 16:12*

666

## 回复 by cpannn (#23)

*2025-11-17 20:19*

666

## 回复 by wx_Huber Barrientos (#24)

*2025-11-18 03:39*

为你点赞！

## 回复 by mb_mlzpqbvy (#25)

*2025-11-18 10:24*

感谢分享

## 回复 by artake (#26)

*2025-11-18 10:29*

好文

## 回复 by 小尘0000 (#27)

*2025-11-18 17:31*

666

## 回复 by 不具名的悲伤 (#28)

*2025-11-18 20:04*

6

## 回复 by pyth0nDev (#29)

*2025-11-19 17:47*

666

## 回复 by 丶咖啡猫丶 (#30)

*2025-11-19 18:20*

666

## 回复 by 踏水流 (#31)

*2025-11-20 14:22*

666

## 回复 by mb_uvyukvot (#32)

*2025-11-20 15:03*

学习

## 回复 by YooHaa (#33)

*2025-11-20 16:44*

666

## 回复 by style (#34)

*2025-11-20 18:01*

666

## 回复 by kzx0808 (#35)

*2025-11-21 11:49*

6

## 回复 by 洋少QQ (#36)

*2025-11-23 18:38*

感谢感谢

## 回复 by 铭天星 (#37)

*2025-11-23 22:39*

666

## 回复 by mb_tawwmfks (#38)

*2025-11-27 15:15*

666

## 回复 by AK1988DA (#39)

*2025-11-27 16:39*

3

## 回复 by mb_ibdjhpre (#40)

*2025-11-30 07:12*

大佬牛逼

## 回复 by wx_Timedout (#41)

*2025-11-30 15:42*

6

## 回复 by qiantang (#42)

*2025-12-2 12:21*

感谢分享

## 回复 by mb_uoktlvrn (#43)

*2025-12-23 09:49*

666

## 回复 by mb_srmwcgoy (#44)

*2025-12-23 11:33*

66666666666

## 回复 by mb_dcjxxhsk (#45)

*2025-12-25 14:16*

666

## 回复 by System's (#46)

*2025-12-26 12:34*

66666

## 回复 by wx_故事与酒 (#47)

*2026-1-18 02:21*

6666666666666666666

## 回复 by mb_auylfslb (#48)

*2026-1-20 11:27*

6

## 回复 by 浮夸进进 (#49)

*2026-1-21 14:27*

666

## 回复 by 不具名的悲伤 (#50)

*2026-1-26 15:29*

6

## 回复 by mb_hbosztvl (#51)

*2026-2-1 00:34*

666

## 回复 by xinhu (#52)

*2026-2-5 16:49*

666

## 回复 by mb_fglogyec (#53)

*2026-2-7 12:55*

666

## 回复 by 和风起 (#54)

*2026-3-1 18:05*

666

## 回复 by 小今朝 (#55)

*2026-3-5 11:14*

666

## 回复 by mb_stdlrcgp (#56)

*2026-4-2 09:48*

5666

## 回复 by iBa0 (#57)

*2026-4-6 19:51*

123

## 回复 by cx52038 (#58)

*2026-4-15 21:07*

666

## 回复 by 学不懂 (#59)

*2026-4-22 11:36*

强的一

## 回复 by The0dore (#60)

*2026-4-24 22:40*

感谢分享

## 回复 by niama (#61)

*2026-5-20 12:17*

666

## 回复 by mb_lraqkkcj (#62)

*2026-6-22 10:48*

6666666666666

## 回复 by buluo533 (#63)

*2026-6-23 08:51*

666

## 回复 by mb_gjhmacqd (#64)

666
