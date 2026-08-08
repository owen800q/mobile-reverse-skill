---
title: '[原创][原创]LibCrypt.so 魔改MD5'
url: https://bbs.kanxue.com/thread-288023.htm
tid: 288023
author: 沈聽白
date: '2025-08-14'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-08T10:50:16+00:00'
replies: 21
---

>
> ## 在开始这篇文章之前，请阅读一下注意事项
>
>
> ## 本文章仅用于学习研究，如有侵犯贵司权益，请联系告知，会立即做出下架删除处理。
>
>
> ## 本文章不针对任何网站，APP ，禁止用于商业，转载，违法等用途。
>
>
> ## 观看则默认同意本约定，未经允许禁止任何形式的转载，保留追究法律责任的权利 !
>
>
>

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374757677787980818283848586878889909192939495969798 | `package` `com;` `import` `com.github.unidbg.AndroidEmulator;``import` `com.github.unidbg.Emulator;``import` `com.github.unidbg.LibraryResolver;``import` `com.github.unidbg.Module;``import` `com.github.unidbg.arm.backend.Unicorn2Factory;``import` `com.github.unidbg.debugger.Debugger;``import` `com.github.unidbg.file.FileResult;``import` `com.github.unidbg.file.IOResolver;``import` `com.github.unidbg.linux.android.AndroidEmulatorBuilder;``import` `com.github.unidbg.linux.android.AndroidResolver;``import` `com.github.unidbg.linux.android.dvm.*;``import` `com.github.unidbg.memory.Memory;``import` `com.github.unidbg.virtualmodule.android.AndroidModule;``import` `com.github.unidbg.virtualmodule.android.JniGraphics;``import` `com.github.unidbg.virtualmodule.android.MediaNdkModule;``import` `com.github.unidbg.virtualmodule.android.SystemProperties;` `import` `java.io.File;``import` `java.util.ArrayList;``import` `java.util.List;`  `public` `class` `模板` `extends` `AbstractJni` `implements` `IOResolver {` `private` `static` `final` `String PackName =` `"APP 包名"``;``private` `static` `final` `String AppPath =` `"传入 APP路径"``;``private` `static` `final` `String[] SoName = {``"SO名字或外部路径"``};` `// 可能会出现多个SO文件加载的情况``private` `final` `AndroidEmulator emulator;``private` `final` `VM vm;``private` `final` `Module module;``final` `Memory memory;`  `@Override``public` `FileResult resolve(Emulator emulator, String pathname,` `int` `oflags) {``System.out.println(``"Load File: "` `+ pathname);``return` `null``;``}` `private` `static` `LibraryResolver createLibraryResolver() {``return` `new` `AndroidResolver(``23``);``}` `private` `static` `AndroidEmulator createARMEmulator() {``return` `AndroidEmulatorBuilder.for64Bit()``.setProcessName(PackName)``.addBackendFactory(``new` `Unicorn2Factory(``false``))``.build();``}` `模板 () {``emulator = createARMEmulator();``// 创建模拟器的内存映射``emulator.getSyscallHandler().addIOResolver(``this``);``// 获取模拟器的内存操作接口``memory = emulator.getMemory();``// 设置系统类库解析 23``memory.setLibraryResolver(createLibraryResolver());``// 创建Android虚拟机,传入APK，Unidbg可以替我们做部分签名校验的工作``vm = emulator.createDalvikVM(``new` `File(AppPath));``// 虚拟模块部分``new` `AndroidModule(emulator,vm).register(memory);``new` `MediaNdkModule(emulator,vm).register(memory);``new` `JniGraphics(emulator,vm).register(memory);``// 设置JNI``vm.setJni(``this``);``// 打印日志``vm.setVerbose(``true``);``// 加载目标SO``DalvikModule dm = vm.loadLibrary(SoName[``0``],` `true``);``//获取本SO模块的句柄,后续需要用它``module = dm.getModule();``// 调用JNI OnLoad``dm.callJNI_OnLoad(emulator);``};` `public` `static` `void` `main(String[] args) {``模板 action =` `new` `模板();``action.Call();``}` `public` `void` `Call () {``List<Object> args =` `new` `ArrayList<>();``args.add(vm.getJNIEnv());` `// JNIEnv *``args.add(``0``);` `// 如果是静态方法，这个参数是 jclass（这里假设是静态方法）``args.add(``0``);` `// 输入字符串``args.add(vm.addLocalObject(``new` `StringObject(vm,` `"bcae572b84d20c385d6d9d2d7d9e645da29da3c0user/login18953675221WA89qByLlDeaGjmVNzXm/w=="``)));` `// 输入字符串``args.add(``3``);` `// 输入字符串``Number result = module.callFunction(emulator,` `0x2414``, args.toArray());``DvmObject<?> returnObj = vm.getObject(result.intValue());``String encrypted = ((StringObject) returnObj).getValue();``System.out.println(``"Encrypted String: "` `+ encrypted);``}`  `}` |
|-|-|

---

## 一天一个宏指令

在 IDA 反编译中，编译器计算出来的 习语 会通过IDA 反序列为 特殊的指令，这个叫 宏指令 这块的内容 也是很重要的内容，因为很多东西都是离不开这部分的内容 进行分析逻辑

### ****CFADD** ****指令**

**这个 **CFADD** ****指令****的 简单解释是 ****返回两个参数相加后的进位标志位 **

直接用当前的 案例进行解释，例如说，在当前案例中 有下述代码块

| 12 | `v7 = v24;``v8 = __CFADD__((_DWORD)v24, 8 * a3);` |
|-|-|

刚才 已经说了，**CFADD** 指令就是 当前 两个操作参数 进行相加的操作，那么 其实可以看看 对应的Trace 日志

| 1 | `[libCrypt.so 0x01e1c] 0x40001e1c:` `"adds w8, w9, w21, lsl #3"` `w9=0x0 w21=0x6 => nzcv: N=0, Z=0, C=0, V=0 w8=0x30` |
|-|-|

简单的分析已经得知，**w21 **实际上就是 输入的明文长度 我们入参输入的是 **123456**，那么 对应的 **w21**是**0x6**

在 伪代码中 显示的是 **8*a3 **在汇编中(逆向多是以汇编为主) ** lsl #3 那么就是 把原本输入的 w21 左移 << 3**

再加上 **w9 **得出最终的结果 **w8 ** 已知 **w9 **是 **0， **那么简单来计算一下 `print(6<<3)`

![image](https://bbs.kanxue.com/upload/attach/202508/948680_QZJ8PZZA7J5JDV9.png)

对比一下, 符合**Trace **出来的日志, **0x30** , 那么现在就又多掌握了一个基本的 **宏指令**** **CDADD****

---

### ****ROL4** ****指令**

再多讲一个，**ROL4** 指令 简单解释就是 循环左移

可以记忆一个小细节问题 部分加密算法是 全局贯穿着 循环左移的使用 例如

- MD5 主要使用 循环左移(ROL)
- SHA-1/SHA-256 也使用 ROL
- SM3 (国密3) 也使用 循环左移

| 12345678910 | `def` `rol(num, count):``#``# 循环左移``"""``:param num:``:param count:``:return:``"""``b` `=` `(num &` `0xffffffff``) << count``return` `(b &` `0xffffffff``)` `+` `(b >>` `32``)` |
|-|-|

---

## MD5的魔改方向

>
> 在 如今 安卓逆向的 行业来说，各种卷王 层出不跌。那么 魔改算法，就是某些卷王提出的一些方案，让保护提升安全性
>
>
>

>
> 这里呢 就简单介绍了一下 加密常数表的修改和四个初始化向量的修改，其他的内容，可以关注公众号
>
>
> 加群，后面会有更多的魔改/OLLVM/小众算法的实战内容，文章，视频分享
>
>
>

### 加密常数表修改

现在 结合 标准 MD5 加密的代码 去看一看 什么是 加密码表的修改

![image](https://bbs.kanxue.com/upload/attach/202508/948680_ZCE8K5F9FE2C55T.png)

标准常数表 T

**MD5** 加密 标准的常数表是 **64** 个常数，这也是 **MD5** 加密比较明显的特征点，结合该案例去看一看，就简单结合 **Trace** 去看一看。

例如 在该案例的 **Sub_AD8** 函数中 就能发现大量的计算 如果细心一点就能看出来，常数表是 **64** 个常数，那么实际上 最终的轮计算也是分为 **64** 调用

这 **64 ** 次调用 可以简单的称之为 **Round 1...4 **

| Round 1 | 逻辑函数 ff | 16 轮次 |
|-|-|-|
| Round 2 | 逻辑函数 gg | 16 轮次 |
| Round 3 | 逻辑函数 hh | 16 轮次 |
| Round 4 | 逻辑函数 ii | 16 轮次 |

那么 现在就结合 Trace 日志 简单的 看看 每个轮次的 加密的是 T 常量表里面的内容 是否是被修改过的 我们简单的去找 两三个位置吧

![0xfcefa3f8](https://bbs.kanxue.com/upload/attach/202508/948680_PMDMEAYWS36RMJ8.png)

![0xffeff47d](https://bbs.kanxue.com/upload/attach/202508/948680_TP2UW976CMC8HPG.png)

任意挑了 几个位置的 **T **表中的 常量 直接去 **Trace** 里面 搜一下，就很明显，都是存在的，那么其实就可以判断，**T** 表应该大概率没有被修改过的

>
> 修改 T 表的 魔改方式 其实是 频率 很高的，相对来说 技术成本低，就很容易出现在 魔改 MD5 的场景下
>
>
>

---

### 四个初始化向量修改

要 谈论 魔改之前，还是应该先看一看 标准情况下，四个初始化向量 是什么？

| 1 | `A` `=` `0x67452301`  `B` `=` `0xefcdab89` `C` `=` `0x98badcfe`  `D` `=` `0x10325476` |
|-|-|

那么 现在知道了 四个初始化的 **IV** 的值了 ，现在就应该要知道，这四个值 应该是用到哪里，怎么去找？ 在这里我 写一个 示意图

| 123456789101112 | `初始状态：A``=``0x67452301``, B``=``0xEFCDAB89``, C``=``0x98BADCFE``, D``=``0x10325476``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``处理第``1``个``512``-``bit块：``运行``64``轮压缩函数 → 更新A``/``B``/``C``/``D``将新A``/``B``/``C``/``D加到旧值上 → 得到新的链式值``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``处理第``2``个``512``-``bit块：``用新的A``/``B``/``C``/``D继续压缩 → 再次更新 → 再次累加``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``...``处理完最后一块：``最终A``/``B``/``C``/``D → 拼接 →` `128``-``bit MD5哈希` |
|-|-|

那么 就已经 简单知道了 四个初始化的 IV 是用到了 与每一个 消息块计算的过程中，但是 四个初始化的 IV 会变化吗？会变化的！

![写回IV的操作](https://bbs.kanxue.com/upload/attach/202508/948680_T7UMWRA5XVKXJS7.png)

这个操作 还是非常明显的 在 **MD5** 加密的末尾 是有一个明显的 **四个初始化向量 写回 的操作 ，那么 现在要做的事情就是 根据伪代码去定位疑似写回位置**

四个 初始化 IV 写回的位置是在 标准 MD5 加密的末尾，那么 同样 我们也可以去看 该 MD5 伪代码的末尾...............

![函数末尾](https://bbs.kanxue.com/upload/attach/202508/948680_HQUF6ZSAZTWZCPM.png)

`*a2,a2[1],a[2],a2[3]` 这个 很明显是一个入参值，那么就 Hook 简单的看一看

![第一轮次](https://bbs.kanxue.com/upload/attach/202508/948680_YEAFYGPZMG43DSX.png)

这里呢 要注意一下 在内存中是以小端序的形式体现出来的，a2 的入参是 看前面的 16 个字节 每四个字节分为一组，第一轮次的初始化向量是没问题的

![第二轮次](https://bbs.kanxue.com/upload/attach/202508/948680_QHTFT4993HRYD77.png)

但是 在这里 第二轮次 就已经发现 四个初始化的 IV 是被修改的 已经变了， 先不管这里的地方 继续往下看看。

![第三轮次](https://bbs.kanxue.com/upload/attach/202508/948680_4CWDMK4ZS9EQVHS.png)

经过 简单的分析 得知，入参为

| 1 | `"bcae572b84d20c385d6d9d2d7d9e645da29da3c0user/login18953675221WA89qByLlDeaGjmVNzXm/w=="` |
|-|-|

经过了 三轮的 MD5 加密 四个 IV 其中 **第一轮是正常的，第二轮是被修改的，第三轮是 正常的**

### 轮函数逻辑变换修改

### 加密前填充的修改

### 加密后消息体的破坏

## 逻辑分析

>
> 在 分析 里面逻辑加密之前呢 我们已经知道 有经过了 三次的 MD5 加密，那么 想一想，最终加密输出的值是一个 32 位的长度，但是有三次 MD5 加密的操作，那么三次的 MD5 肯定不会 平白无故 的出现，那么 现在应该做的事情就是 输出 三次 MD5 加密的结果
>
>
>

| 加密轮次 | 四个初始化 IV | 加密结果 |
|-|-|-|
| 第一轮 MD5 | 01 23 45 67 89 AB CD EF FE DC BA 98 76 54 32 10 | 09a03358 |
| 第二轮 MD5 | 09 A0 33 58 DA 58 1B E6 4E 42 9B CF CC 19 55 A3 | 4b8e8dd8 |
| 第三轮 MD5 | 01 23 45 67 89 AB CD EF FE DC BA 98 76 54 32 10 | eae2f8f6 |

上面可能有些是我写的有问题，别问，问就是 看的眼睛花

---

#### 第一次 MD5

那么 实际上 就是 发现，第一次加密出来的结果 实际上 就是 第二次加密的时候 使用的 四个初始化 IV 那么 我们应该尝试一下 进行 第一次 MD5 加密

| 123 | `bcae572b84d20c385d6d9d2d7d9e645da29da3c0user/login18953675221WA8``===========MD5===========``a5a18a787d4d84316767a34df258103e` |
|-|-|

调用 标准的 MD5 之后 发现 结果还是不一样，现在就要思考，为什么会不一样？到底是还有哪里被魔改了？ 现在对比一下 标准情况下 加密前的消息体

![标准的加密](https://bbs.kanxue.com/upload/attach/202508/948680_8J8TMKQN6CZWF69.png)

![image](https://bbs.kanxue.com/upload/attach/202508/948680_PWX9BPMGZ4U9VXD.png)

有点 明显啊 他就取了 前 64 个字节 对应就是 512bit 后面不够 64 个字节的 也没有填充 直接 **delete **

所以 现在就可以 尝试一下 第一次加密了 就按照 原本他的逻辑 取去，但是需要，需要你原本的明文数据就要够 64 个字节 如果不够的话 就会报错

贴一下辅证

| 1 | `"add w22, w7, w24"` `w7=0x38415731 w24=``0x2fde0b31` `=> w22=0x681f6262` |
|-|-|

![第一次MD5 完事](https://bbs.kanxue.com/upload/attach/202508/948680_BBZ8HTPGCZFG7ZG.png)

---

#### 第二次 MD5

现在 开始 讲一下 第二次 MD5

![第二次MD5](https://bbs.kanxue.com/upload/attach/202508/948680_8S2SG57FBUMVJZ7.png)

这里 我就简单讲一讲 需要注意点的 就是 第二次加密的时候 4 个初始化的 IV 就是 第一次 MD5 加密的结果

加密数据的内容就是 传输的明文数据 第一次 MD5 是取前 64 位 第二次加密的就是 前 64 位后面的内容 也就是 [64:str_len]

但是 大家看 这个明文数据的数据 是有填充的 看它的 前 64 个字节 有没有发现的 多了一个 02？

![标准情况下的填充](https://bbs.kanxue.com/upload/attach/202508/948680_EUNQQKKYHPP93J7.png)

这块的 内容 我就直接说了， 就不做过多详细的讲解了，认真看一看 伪代码 就能看出来，实际上 他是有一个判断的 如果长度 判断 256 大于小于 如果 然后会在 **填充 a8 的后面 加入 0x02 或者是 0x03 **

#### 第三次 MD5

我就不在这里多赘述了，后面会有视频在 B 站上发出，后面如果对这部分感兴趣的 都可以关注一下，第三次的 MD5 就是一个标准的 MD5 第二次 MD5 结果 进行 Base64 编码 然后进行 MD5 加密 直接看一下

![最后一次MD5](https://bbs.kanxue.com/upload/attach/202508/948680_DDF5WJ3HEYWVM2X.png)

---

## 加密流程图

![画板](https://bbs.kanxue.com/upload/attach/202508/948680_ZE6ES5KD6K7CABP.png)

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2025-8-14 08:10*

感谢分享

## 回复 by Imxz (#3)

*2025-8-14 08:31*

tql

## 回复 by wx_插曲 (#4)

*2025-8-14 09:00*

tal

## 回复 by mb_fidppcok (#5)

*2025-8-14 10:08*

666

## 回复 by bluegatar (#6)

*2025-8-16 01:36*

高产的一笔

## 回复 by mb_uvyukvot (#7)

*2025-8-22 17:24*

tql

## 回复 by mb_oxchypds (#8)

*2025-8-22 17:26*

lihai

## 回复 by hanjiefang (#9)

*2025-9-4 15:31*

学习

## 回复 by mb_cbgtaveo (#10)

*2025-9-15 14:13*

666

## 回复 by 小童net (#11)

*2025-9-30 16:11*

![image](https://bbs.kanxue.com/view/img/face/004.gif)![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by mb_xjdhrmck (#12)

*2025-10-5 12:38*

666

## 回复 by edisonhu (#13)

*2025-10-25 10:20*

11

## 回复 by mb_euhyowpw (#14)

*2026-1-4 10:39*

666

## 回复 by 9527vv7 (#15)

*2026-1-4 14:12*

1

## 回复 by SomeMx (#16)

*2026-1-4 15:10*

看看

## 回复 by 五彩斑斓的黑 (#17)

*2026-1-5 16:06*

666

## 回复 by 带篮子 (#18)

*2026-2-5 14:55*

666666666666666666

## 回复 by mb_fglogyec (#19)

*2026-2-7 14:07*

6666

## 回复 by LQ6H (#20)

*2026-2-9 16:59*

666

## 回复 by huangjw (#21)

*2026-2-9 17:12*

牛逼之轰轰

## 回复 by long_ (#22)

*2026-4-15 19:33*

666
