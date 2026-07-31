---
title: '[原创]某ttEncrypt算法的简单分析'
url: https://bbs.kanxue.com/thread-279953.htm
tid: 279953
author: 陈可牛
date: '2023-12-20'
tags: [Android安全, 原创, 逆向分析, 协议分析]
crawled_at: '2026-07-31T14:35:28+08:00'
replies: 16
---

## 捣鼓背景

## 其实就是今晚无聊整个乐子打发一下时间了吧？？？

-

-

- 害，真实的原因是发现身边的大佬不是已经分析完某x了，就是在分析的路上了。再不跟上大佬的步伐，估计以后车尾灯都看不到了，再想抱紧大佬大腿当个挂件都难了，
- 既然是刚开始分析的，那就找点简单的吧！
- 大佬们自行跳过
- 大佬们自行跳过
- 大佬们自行跳过

## 因为这是今晚无聊分析的一个小样本，大佬们自行跳过就好啦！

-

-

## 分析总结

花了几个小时快速分析的，所以并未能的完全的分析他的整个流程。只能是通过一些快速分析的手段进行快速的定位以及验证！
到最后才发现他的整个基本都是这个样子比如一开始的JNI_OnLoad方法，有空还想把那个指令的执行也分析一下，看一下他是如何入参出参以及执行方法！

看完整篇文章可以收获为：

- unidbg的简单调试
- so的方法简单修正
- aes的key初始化流程

然后大佬们就可以判断是否有必要继续看下去了

## 目标选取

既然都是用unidbg分析，，，那就肯定绕不开凯神的小demo了

那就是：

- [unidbg-android/src/test/java/com/bytedance/frameworks/core/encrypt/TTEncrypt.java](https://github.com/zhkl0228/unidbg/blob/master/unidbg-android/src/test/java/com/bytedance/frameworks/core/encrypt/TTEncrypt.java)

刚入门捣鼓的时候，学习unidbg的各种hook脚本的时候，就是通过捣鼓这几个小demo进行学习的了，那这次就当作交了拖了很久很久的作业了
既然目标已经确定了，那就开始吧！

## 开发环境

- 开发环境：Unidbg，对，就这个就够了
- 电脑环境：Windows11
- app板本：26.1.0（是大佬发给我的，所以没得下载链接）

## 模拟执行

既然是交作业第一步就是先把凯神的复制过来改改先，然后把apk配置为我们目标的板本！

由于分析的版本是64的，加载方式是通过apk加载的，所以第一步将for32Bit()改成for64Bit()；然后再向createDalvikVM传入apk的当前路径；接着修改一下loadLibrary的传递参数为：ttEncrypt，顺便将第二个参数设置为：true；让他执行一下so的初始化方法！

他的有一些hook的demo跟ida pro调试代码我们目前用不着，那就先删除！

改完就成这个样子了！

- ![image](https://bbs.kanxue.com/upload/attach/202312/93_2JRC2E3FESW992K.png)
- 然后跑起来！
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_M3FV27PHS69ZX26.png)
- 紧接着就翻车了~~害，按照提示我们去看一下apk中是否存在这个依赖了~~
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_E8MHGXMB6QB5DPF.png)
- 确实没有我们要加载名称为：ttEncrypt的库，那我们就去手机中看看吧！
- 既然没有这个依赖库，那我们通过凯神的代码得知是调用ttEncrypt([BI)[B，那我们就试试这个吧！试试手机中是否有这个导出的符号了来碰碰运气了！
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_J8R55RBXYP97USG.png)
- 瞎猫碰着死耗子！嘿嘿，还不用去分析apk了，今天的运气还不错，继续冲冲冲！
- 那我们就把依赖库的名称从“ttEncrypt”改成“Encryptor”再试试！
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_3UTDJFBUN85VDR9.png)
- 这次还不赖，发现是找不到“ttEncrypt([BI)[B”方法，既然我们可以通过符号定位到so，那必定是存在这个方法的！
- 那为什么找不到呢？通过观察上面的前三条可以发现，现在的类名已经变更为：com/bytedance/frameworks/encryptor/EncryptorUtil，而不再是：com/bytedance/frameworks/core/encrypt/TTEncryptUtils！
- 那我们修正一下再试试！
- 参数为第一个参数为0x10个byte！第二个参数byte[]的长度！
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_QDEZP3RVPABFB7S.png)
- 竟然就可以跑起来了~
- 还有结果了呢~
- 那就关机睡觉！
-
-
-
- 那肯定不会就到此结束的啦~还得把算法移植出来呢！

## 算法移植

### 算法入口

- 说的算法移植，那第一步必定就是：原神启动！
- 哈哈哈，走错片场了呢！
- 是ida pro启动，打开我们的女神软件ida pro！
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_Q6DDQURCA7YVSV8.png)
- 然后把so拖入进行分析！
- 按照惯例，我们先看一下导出符号都有啥
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_STEKKEVESFFZA9Z.png)
- 只有两个导出函数，JNI_OnLoad跟start
- 我们都知道JNI_OnLoad是动态注册方法的一个时机，start是作为直接启动so的一个入口。那我们就看看JNI_OnLoad中都有啥吧！
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_BTHDSY97FZRYHEK.png)]
- 啥都没，那我们进入一下sub_da0吧
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_XFJBRYJ65BNJ4UR.png)
- 看不懂！所以我们简单看一下sub_da0的程序流程图
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_PVA25H6K4XWVB23.png)]
- 发现都是密密麻麻的块，直接劝退我这种密集恐惧症患者了！直接关闭了！
- 既然我们不想通过分析JNI_OnLoad找到他动态注册代码的地方，我们就通过unidbg的log直接得知他的运行入口！那就是：

| 1 | `Find native function Java_com_bytedance_frameworks_encryptor_EncryptorUtil_ttEncrypt => RX@0x40007a38[libEncryptor.so]0x7a38` |
|-|-|

- 通过这个告诉我们有时候不知道该咋办的时候可以多看看log！看看有没有一些蛛丝马迹的！
- 那我现在就知道他的代码入口点为：0x7a38

### 算法分析

#### so方法修正

- ![image](https://bbs.kanxue.com/upload/attach/202312/93_HX5AC2N8P6Z3GEV.png)
- 哦豁，打开之后全部爆红，而且不能按f5，那可咋办了？？？
- 别着急，那我们就作为一个简单的修正即可！
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_9J8C37A2EYJYVGQ.png)
- 我们先从0x7a38开始往下选选择一块区域，选择一些就可以了，然后按一下p即可！（这种为强制将选择的区域代码创建方法）
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_FHPDGAWM38RE63D.png)
- 然后我们发现下面还有一些红色的块，此时别着急。我们往下拉直到找到RET这个指令的上一个红色快的最后一条代码。也就是0x7B58处，我们在这里按一下e即可！
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_2W5W5BS5EMGDMJH.png)
- 然后就正常啦！
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_QA9BCT6YZS947QC.png)
- 但是我们往上滑动的时候发现0x7B04也是有一块红色的！
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_WTYX5UPCYUQQXR6.png)
- 那我们也按照上面的方式，就在这一行按一下e即可！修正后就如图所示啦~
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_JPU68VMUGXFD7CV.png)
- 接着我们就可以愉快的F5啦~
- 嘿嘿，其实有些大佬看到这里会觉得这样子做太复杂了，还不如在0x7a38直接上直接按一下p直接完事！
- 哈哈哈，这个样本确实在0x7a38行上直接按一下p就不需要修复其他的块了~但是我们还是要学习一下这种选择块的修正方式，毕竟后面的样本呢，按一下p是没啥用的！还是选块好使！

#### JNI方法的修正

- 这里就直接上手啦，结构体导入啥的就直接看其他的大佬的文章就好啦~
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_TU5SRY9HJAT32PZ.png)
- 通过修正&ida的提示，我们就知道核心方法是sub_2AC4，且他的参数依次分别为：bytes（输入的字节数组）、length（字节数组的大小）、output（输出、也就是我们的结果了）、size（结果的大小）
- 那我们紧接着分析一下sub_2ac4了
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_2JCBRTVBCFW6P52.png)
- 发现她会把我们的参数都放在一个数组里面了（结构体）
- 其中
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_YJ2ZQ52J29NMR6Y.png)
- 在rodata有一大长长的东西我们看不懂，那我们就先不管它了
- 通过分析2ac4我们发现他会进一步调用2c18，他的第一个参数就是0xb090、第二个是我们传过来的参数以及返回值、第三个像是一个index、第四个一样看不懂，应该跟第一个类似，先不管了、第五个像是一个回调的方法（下面很关键）
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_2H2MH9DMX699M9G.png)
- 我们会发现他跟JNI_OnLoad的sub_da0方法很相似！
- 那我们继续摆烂吧，这种代码不优化一下，压根就没法看了。没办法不会写优化，emmm。既然此路不通，那我们再寻寻其他的方法！

#### traceWrite

- 那直接分析代码我们分析不了，那我们就只剩下trace了，这次我们不直接trace code，而是trace write！
- 为什么不选择直接trace code然后通过结果来写呢！因为这是一个混淆过的代码，trace的log会是非常大的！所以我们要化简！
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_AK6CVFDN9YMJ6DA.png)
- 上面就是通过trace的log了有十多万行！移植起来会是非常棘手的！所以我们选择了trace write！这时候就会有一些大佬说为啥不用trace read呢？嘿嘿，我们要以结果为导向！所以选择的是trace write的out！
- 既然我们要选择trace write，那么我们就选择address跟size了
- 这时候我们回到sub_783a
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_R93R3DJ8CG6QEVE.png)
- 发现malloc这里分配了一个length + 118大小的内存了，这样子我们就直到size是length + 118了，那么我们就剩下addres了
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_EF2YX2PSSSY99AU.png)
- 通过测试发现，0x7AA8执行后他的地址是固定的！那么我们就可以确定address为0x40358000，而且还是一个固定值！（如果不是固定值咋办呢？嘿嘿，其实加多一个backend.hook_add_new来获取实际的即可！）（time、rand、srand这些其实都可以固定的，有兴趣可以翻一下源码或者写hook进行固定）
- 那么就可以愉快的写trace write啦！！！

| 12 | `// 0x10为传进来的byte[]大小，这个是已知的``emulator.traceWrite(``0x40358000``,` `0x40358000` `+` `0x10` `+` `118``);` |
|-|-|

- ![image](https://bbs.kanxue.com/upload/attach/202312/93_HRXGPQBYHRA39FJ.png)
- ![image](https://bbs.kanxue.com/upload/attach/202312/93_8TK2EFS8MEVZYHN.png)
- 屏幕太小，只能截图两次，哈哈哈
- 通过分析trace代码，我们可以得知他的数据是由四个部分三个方法（0x2be0、0x3c2c（pc在libc.so所以看lr，看他返回到哪里）、0x2a58（0x2a58跟0x2a88应该也是在同一个方法内的））组成的

| 1234567891011121314151617181920212223242526272829 | `74 63 05 10 ==>0x10056374``00 00 ==> 0x2be0` `// 0x1c184``A0 BB 10 FA EC 38 50 03 EA 42 C6 94 15 ED CD 30（0x35038ecfa10bba0、0x30cded1594c642ea）``B6 5F F5 E8 25 43 A3 66 D4 B8 E7 FB D7 F3 89 77 （0x66a34325e8f55fb6、0x7789f3d7fbe7b8d4）` `// 0x2a58``[01:48:41 773] Memory WRITE at 0x40358026, data size = 8, data value = 0xeb12c44a6b02c09, PC=RX@0x40002a58[libEncryptor.so]0x2a58, LR=RX@0x40002a4c[libEncryptor.so]0x2a4c``[01:48:41 773] Memory WRITE at 0x4035802e, data size = 8, data value = 0x632b08e36313439e, PC=RX@0x40002a58[libEncryptor.so]0x2a58, LR=RX@0x40002a4c[libEncryptor.so]0x2a4c``[01:48:41 773] Memory WRITE at 0x40358036, data size = 8, data value = 0x241e2a664df9f031, PC=RX@0x40002a58[libEncryptor.so]0x2a58, LR=RX@0x40002a4c[libEncryptor.so]0x2a4c``[01:48:41 773] Memory WRITE at 0x4035803e, data size = 8, data value = 0x2bee5c58693bd0fc, PC=RX@0x40002a58[libEncryptor.so]0x2a58, LR=RX@0x40002a4c[libEncryptor.so]0x2a4c``[01:48:41 773] Memory WRITE at 0x40358046, data size = 8, data value = 0x468e9bebbf9629eb, PC=RX@0x40002a58[libEncryptor.so]0x2a58, LR=RX@0x40002a4c[libEncryptor.so]0x2a4c``[01:48:41 773] Memory WRITE at 0x4035804e, data size = 8, data value = 0x2a698ed9942a3431, PC=RX@0x40002a58[libEncryptor.so]0x2a58, LR=RX@0x40002a4c[libEncryptor.so]0x2a4c``[01:48:41 773] Memory WRITE at 0x40358056, data size = 8, data value = 0x713bbf110c38b4, PC=RX@0x40002a58[libEncryptor.so]0x2a58, LR=RX@0x40002a4c[libEncryptor.so]0x2a4c``[01:48:41 773] Memory WRITE at 0x4035805e, data size = 8, data value = 0x217a8beac056e0c6, PC=RX@0x40002a58[libEncryptor.so]0x2a58, LR=RX@0x40002a4c[libEncryptor.so]0x2a4c``[01:48:41 773] Memory WRITE at 0x40358066, data size = 8, data value = 0xdc330f68f180331e, PC=RX@0x40002a58[libEncryptor.so]0x2a58, LR=RX@0x40002a4c[libEncryptor.so]0x2a4c``[01:48:41 773] Memory WRITE at 0x4035806e, data size = 8, data value = 0xe121d61a37fcf7dc, PC=RX@0x40002a58[libEncryptor.so]0x2a58, LR=RX@0x40002a4c[libEncryptor.so]0x2a4c``[01:48:41 773] Memory WRITE at 0x40358076, data size = 8, data value = 0x77f78e1f1dd196d1, PC=RX@0x40002a88[libEncryptor.so]0x2a88, LR=RX@0x40002a84[libEncryptor.so]0x2a84``[01:48:41 773] Memory WRITE at 0x4035807e, data size = 8, data value = 0x2e7d43264681b810, PC=RX@0x40002a88[libEncryptor.so]0x2a88, LR=RX@0x40002a84[libEncryptor.so]0x2a84`  `09 2C B0 A6 44 2C B1 0E 9E 43    .....w.,..D,...C``0030: 13 63 E3 08 2B 63 31 F0 F9 4D 66 2A 1E 24 FC D0    .c..+c1..Mf*.$..``0040: 3B 69 58 5C EE 2B EB 29 96 BF EB 9B 8E 46 31 34    ;iX\.+.).....F14``0050: 2A 94 D9 8E 69 2A B4 38 0C 11 BF 3B 71 00 C6 E0    *...i*.8...;q...``0060: 56 C0 EA 8B 7A 21 1E 33 80 F1 68 0F 33 DC DC F7    V...z!.3..h.3...``0070: FC 37 1A D6 21 E1 D1 96 D1 1D 1F 8E F7 77 10 B8    .7..!........w..``0080: 81 46 26 43 7D 2E                                  .F&C}.` |
|-|-|

- 那这样子的话，我们重点分析：0x2be0、0x3c2c（pc在libc.so所以看lr，看他返回到哪里）、0x2a58（0x2a58跟0x2a88应该也是在同一个方法内的）这三个方法即可完成协议移植！

### 0x2be0

- 首先看一下0x2be0！
- ![img.png](https://bbs.kanxue.com/upload/attach/202312/93_SBHZN5WS89URH24.png)
- 好像有点眼熟
- 将268788596转成十六进制再看看？
- ![img_1.png](https://bbs.kanxue.com/upload/attach/202312/93_CX25KHSQ6PDHWXE.png)
- 那不就是第一段的0x10056374跟0x0吗？
- 哈哈哈，那看到这里我们就已经完成了三分之一了！非常快了~果然还是有运气的buf的！

### 0x3c2c

![image](https://bbs.kanxue.com/upload/attach/202312/93_4A48MD4NRXXV7Q3.png)

- 发现他又回到了sub_2C18了，而且调用的是blr x20，而且这个x20的值是啥我们也不知道，那我们就下个断点再看看吧！
- 在0x3C28处下断点，看看x20的值是多少了？

| 1 | `debugger.addBreakPoint(module,` `0x3C28``);` |
|-|-|

- ![img_1.png](https://bbs.kanxue.com/upload/attach/202312/93_2UT5GVZCT9GS7D8.png)
- 发现的是调用sub_2c0c
- 那我们看看sub_2c0c方法是做什么的呢？
- ![img_2.png](https://bbs.kanxue.com/upload/attach/202312/93_ZK6ZM22D3XMJW75.png)
- 原来是一个跳板方法，然后将x0跟x1传进入，然后在sub_2c0c中调用x0，参数为1
- 那我们看一下x0跟x1的值都是啥？
- ![img.png](https://bbs.kanxue.com/upload/attach/202312/93_PSRYQE87TFN6R2K.png)
- 调用的是sub_2b40方法，传递的参数是：
- ![img.png](https://bbs.kanxue.com/upload/attach/202312/93_NZ7RT5P7JK6PVH9.png)
- 是啥我们不知道，那我们先看一下sub_2b40是做啥的？
- ![img.png](https://bbs.kanxue.com/upload/attach/202312/93_W2RUG8RXEVPU7EZ.png)
- 好像是一个动态分配内存的代码？好像与我们一开始分析的不一致诶！那该咋办？会不会这次的执行时机并非我们要执行的时候？
- 那就多次执行看看都会执行那些方法吧！
- ![img.png](https://bbs.kanxue.com/upload/attach/202312/93_GYG852U4E7D9YRH.png)
- 执行了sub_2b5c
- ![img_2.png](https://bbs.kanxue.com/upload/attach/202312/93_R4BP7UNWF9SBB9V.png)
- 好像是时间跟随机数的诶
- ![img_1.png](https://bbs.kanxue.com/upload/attach/202312/93_3EAF62KB4HZ4YPC.png)
- 咋又执行了呢？这好像都不知道得执行多久才执行到我们的方法了，害！那就写代码进行处理吧！

| 1234567891011121314151617181920212223 | `backend.hook_add_new(``new` `CodeHook() {``@Override``public` `void` `hook(Backend backend,` `long` `address,` `int` `size, Object user) {``if` `(address == module.base +` `0x3C28``){``Number x0 = backend.reg_read(Arm64Const.UC_ARM64_REG_X0);``Number x20 = backend.reg_read(Arm64Const.UC_ARM64_REG_X20);``long` `m0 = x20.longValue()-module.base;``long` `m1 = x0.longValue()-module.base;``System.out.println(``"直接调用的是-->"` `+ Long.toHexString(m0));``System.out.println(``"间接调用的是-->"` `+ Long.toHexString(m1));``}``}` `@Override``public` `void` `onAttach(UnHook unHook) {` `}` `@Override``public` `void` `detach() {` `}``}, module.base, module.base + module.size,` `null``);` |
|-|-|

- 得到如下的输出

| 12345678910111213141516171819202122232425262728 | `直接调用的是-->2c0c``间接调用的是-->2b40``直接调用的是-->2c0c``间接调用的是-->2b5c``直接调用的是-->2c0c``间接调用的是-->2b40``直接调用的是-->2c0c``间接调用的是-->2b40``直接调用的是-->2c0c``间接调用的是-->2b94``直接调用的是-->2c0c``间接调用的是-->2b40``直接调用的是-->2c0c``间接调用的是-->2ba8``直接调用的是-->2c0c``间接调用的是-->2bb8``直接调用的是-->2c0c``间接调用的是-->2bb8``直接调用的是-->2c0c``间接调用的是-->2bc8``直接调用的是-->2c0c``间接调用的是-->2be8``直接调用的是-->2c0c``间接调用的是-->2c04``直接调用的是-->2c0c``间接调用的是-->2c04``直接调用的是-->2c0c``间接调用的是-->2c04` |
|-|-|

- 那么我们就简单分析一下这些间接调用的方法作用吧，顺便都打印出来（只分析核心的两个方法，其他的不做分析，读者可以自行研究分析！）
- 分析后我们可以这样子改写一下代码，然后再看一下输出

| 1234567891011121314151617181920212223242526272829303132333435 | `Map<Integer, String> map =` `new` `HashMap<>();``map.put(``0x2c0c``,` `"跳板函数，x0为要执行的函数，x1为参数（指针）"``);``map.put(``0x2b40``,` `"malloc"``);``map.put(``0x2b5c``,` `"time、srand、rand随机数函数"``);``map.put(``0x2b94``,` `"又跳到另外一个大的函数过去了（跟入口的0x2C18是一致）"``);``map.put(``0x2ba8``,` `"散列家族算法（6A58）"``);``map.put(``0x2bb8``,` `"memcpy1"``);``map.put(``0x2bc8``,` `"memcpy2"``);``map.put(``0x2be8``,` `"aes相关函数"``);``map.put(``0x2c04``,` `"free"``);` `Backend backend = emulator.getBackend();``backend.hook_add_new(``new` `CodeHook() {``@Override``public` `void` `hook(Backend backend,` `long` `address,` `int` `size, Object user) {``if` `(address == module.base +` `0x3C28``){``Number x0 = backend.reg_read(Arm64Const.UC_ARM64_REG_X0);``Number x20 = backend.reg_read(Arm64Const.UC_ARM64_REG_X20);``long` `m0 = x20.longValue()-module.base;``long` `m1 = x0.longValue()-module.base;``System.out.println(``"直接调用的是-->"` `+ Long.toHexString(m0)+` `"\t"` `+ map.get((``int``)m0));``System.out.println(``"间接调用的是-->"` `+ Long.toHexString(m1)+` `"\t"` `+ map.get((``int``)m1));``}``}` `@Override``public` `void` `onAttach(UnHook unHook) {` `}` `@Override``public` `void` `detach() {` `}``}, module.base, module.base + module.size,` `null``);` |
|-|-|

- 然后看一下输出

| 12345678910111213141516171819202122232425262728 | `直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2b40    malloc``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2b5c    time、srand、rand随机数函数``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2b40    malloc``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2b40    malloc``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2b94    又跳到另外一个大的函数过去了（跟入口的0x2C18是一致）``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2b40    malloc``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2ba8    散列家族算法（6A58）``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2bb8    memcpy1``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2bb8    memcpy1``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2bc8    memcpy2``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2be8    aes相关函数``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2c04    free``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2c04    free``直接调用的是-->2c0c    跳板函数，x0为要执行的函数，x1为参数（指针）``间接调用的是-->2c04    free` |
|-|-|

- 通过分析这段代码后，我们发现了另外一个sub_2b94调用sub_45C8跟JNI_OnLoad的sub_DA0以及ttEncrypt的sub_2C18差不多的！
- ![img.png](https://bbs.kanxue.com/upload/attach/202312/93_5BGJKF4XMVP26W4.png)
- ![img_1.png](https://bbs.kanxue.com/upload/attach/202312/93_CTY5HH2RSYM3CFP.png)
- ![img_2.png](https://bbs.kanxue.com/upload/attach/202312/93_N6RQ4MAARVFM8BX.png)
- 所以我们用同样的方法去处理sub_45C8的0x55D8（类似sub_2C18，也就只有一处的函数调用，所以可以快速得出），得出一下完整的代码（JNI_OnLoad不处理，因为暂时没有看到与他相关的）

| 123456789101112131415161718192021222324252627282930313233343536373839404142 | `Map<Integer, String> map =` `new` `HashMap<>();``map.put(``0x2c0c``,` `"跳板函数，x0为要执行的函数，x1为参数（指针）"``);``map.put(``0x2b40``,` `"malloc"``);``map.put(``0x2b5c``,` `"time、srand、rand随机数函数"``);``map.put(``0x2b94``,` `"又跳到另外一个大的函数过去了（跟入口的0x2C18是一致）"``);``map.put(``0x2ba8``,` `"散列家族算法（6A58）"``);``map.put(``0x2bb8``,` `"memcpy1"``);``map.put(``0x2bc8``,` `"memcpy2"``);``map.put(``0x2be8``,` `"aes相关函数"``);``map.put(``0x2c04``,` `"free"``);` `map.put(``0x45bc``,` `"跳板函数，x0为要执行的函数，x1为参数（指针）"``);``map.put(``0x44c4``,` `"malloc"``);``map.put(``0x44e0``,` `"散列家族算法（6A58）"``);``map.put(``0x44f0``,` `"memcpy"``);``map.put(``0x4500``,` `"查表"``);``map.put(``0x45B4``,` `"free"``);` `Backend backend = emulator.getBackend();``backend.hook_add_new(``new` `CodeHook() {``@Override``public` `void` `hook(Backend backend,` `long` `address,` `int` `size, Object user) {``if` `(address == module.base +` `0x3C28` `\|\| address == module.base +` `0x55D8``){``Number x0 = backend.reg_read(Arm64Const.UC_ARM64_REG_X0);``Number x20 = backend.reg_read(Arm64Const.UC_ARM64_REG_X20);``long` `m0 = x20.longValue()-module.base;``long` `m1 = x0.longValue()-module.base;``System.out.println(``"直接调用的是-->"` `+ Long.toHexString(m0)+` `"\t"` `+ map.get((``int``)m0));``System.out.println(``"间接调用的是-->"` `+ Long.toHexString(m1)+` `"\t"` `+ map.get((``int``)m1));``}``}` `@Override``public` `void` `onAttach(UnHook unHook) {` `}` `@Override``public` `void` `detach() {` `}``}, module.base, module.base + module.size,` `null``);` |
|-|-|

- ![img_3.png](https://bbs.kanxue.com/upload/attach/202312/93_CZE9PCZV6ZQ4QXB.png)
- 通过上面的代码我们就可以发现它的规律以及我们以后重点要分析的方法了，即2be8、（2ba8、44E0都是调用6A58）2b5c和这三个，其他的都是一些分配内存释放内存，内存复制等基本方法（可以map的映射）

#### 2ba8、44e0（6A58）

- ![img_11.png](https://bbs.kanxue.com/upload/attach/202312/93_2QYE2J3GT2UN2HB.png)
- 进来发现调用的是6a58
- ![img_4.png](https://bbs.kanxue.com/upload/attach/202312/93_MVDFUFKRHT8BE47.png)
- 进入6a58后我们就看到一个长度为4的数组以及0x5BE0CD19137E2179LL;、还有128。不管三七二十一，先都看看0x5BE0CD19137E2179LL是啥的先把！
- ![img_5.png](https://bbs.kanxue.com/upload/attach/202312/93_4E3C9SU4HT3WTGD.png)
- 嘿，像是sha512，那我们再看看数组是否为sha512的常量了！
- ![img_6.png](https://bbs.kanxue.com/upload/attach/202312/93_7348V45WTA6FRY5.png)
- 好像都对的上诶，哈哈哈。那么调试一下
- ![img_7.png](https://bbs.kanxue.com/upload/attach/202312/93_JEVB264Q3Y595GT.png)
- 发现第二个参数为0x20像是输入的长度，那我们看一下他的内容
- ![img_8.png](https://bbs.kanxue.com/upload/attach/202312/93_9ZQFTS73PPYC6EG.png)
- 看了这个输出，那我们就可以猜测：第一个是输入的字节数组，第二个为长度，第三个为输出
- 这种就得写hook代码了，哈哈哈

| 1234567891011121314151617181920 | `// 这里使用Dobby会异常，别问我为啥知道。嘿嘿。想知道这个又可以水一篇文章了，哈哈哈哈``IHookZz hookZz = HookZz.getInstance(emulator);` `// 加载HookZz，支持inline hook，文档看https://github.com/jmpews/HookZz``hookZz.wrap(module.base +` `0x6A58``,` `new` `WrapCallback<HookZzArm64RegisterContext>() {` `// inline wrap导出函数``@Override``public` `void` `preCall(Emulator<?> emulator, HookZzArm64RegisterContext ctx, HookEntryInfo info) {``UnidbgPointer x0 = ctx.getPointerArg(``0``);``int` `x1 = ctx.getIntArg(``1``);``UnidbgPointer x2 = ctx.getPointerArg(``2``);``byte``[] input = x0.getByteArray(``0``, x1);``Inspector.inspect(input,` `"input(sha512)"``);``ctx.push(x2);``emulator.getUnwinder().unwind();``}``@Override``public` `void` `postCall(Emulator<?> emulator, HookZzArm64RegisterContext ctx, HookEntryInfo info) {``UnidbgPointer x2 = ctx.pop();``int` `length =` `0x40``;``Inspector.inspect(x2.getByteArray(``0``, length),` `"正式结果"``);``}``});` |
|-|-|

- ![img_9.png](https://bbs.kanxue.com/upload/attach/202312/93_5BZMUCXY6ETCZQ9.png)
- 有输入跟输出了，那我们就可以进行验证一下自己分析的是否对了！

| 1234567891011121314 | `>-----------------------------------------------------------------------------<``[02:55:46 216]input(sha512), md5=7e6de8344f55d460143710510155b657, hex=2ad949a94f9867924645bdfc952302dea3193a95cbe9913e3bbea28a659eaa90``size: 32``0000: 2A D9 49 A9 4F 98 67 92 46 45 BD FC 95 23 02 DE    *.I.O.g.FE...#..``0010: A3 19 3A 95 CB E9 91 3E 3B BE A2 8A 65 9E AA 90    ..:....>;...e...` `>-----------------------------------------------------------------------------<``[02:55:46 234]正式结果, md5=bed9304b171af26ae94b5fcaccd1fd6b, hex=17b4b1b1094010ca669a8c2116ad14a25b40302b693684f23686cad7817f5295064c06ab34f5f55a8dfceee08bd2ae3a8cb12d52fbc7981e0b4ed5f995b921eb``size: 64``0000: 17 B4 B1 B1 09 40 10 CA 66 9A 8C 21 16 AD 14 A2    .....@..f..!....``0010: 5B 40 30 2B 69 36 84 F2 36 86 CA D7 81 7F 52 95    [@0+i6..6.....R.``0020: 06 4C 06 AB 34 F5 F5 5A 8D FC EE E0 8B D2 AE 3A    .L..4..Z.......:``0030: 8C B1 2D 52 FB C7 98 1E 0B 4E D5 F9 95 B9 21 EB    ..-R.....N....!.``^-----------------------------------------------------------------------------^` |
|-|-|

- ![img_10.png](https://bbs.kanxue.com/upload/attach/202312/93_7CU2YF7VUKN4EYH.png)
- 嘿，竟然一致！
- 那我们再分析一个~

#### 2b5c

- ![img_12.png](https://bbs.kanxue.com/upload/attach/202312/93_D7SNASGB739SH6Z.png)
- 太简单了，直接上代码了啦~

| 123456789101112 | `hookZz.wrap(module.base +` `0x2B5C``,` `new` `WrapCallback<HookZzArm64RegisterContext>() {` `// inline wrap导出函数``@Override``public` `void` `preCall(Emulator<?> emulator, HookZzArm64RegisterContext ctx, HookEntryInfo info) {``UnidbgPointer x0 = ctx.getPointerArg(``0``);``ctx.push(x0);``}``@Override``public` `void` `postCall(Emulator<?> emulator, HookZzArm64RegisterContext ctx, HookEntryInfo info) {``UnidbgPointer x0 = ctx.pop();``Inspector.inspect(x0.getPointer(``0``).getByteArray(``0``,` `0x100``),` `"测试哦"``);``}``});` |
|-|-|

- ![img_13.png](https://bbs.kanxue.com/upload/attach/202312/93_PT5E4UPUG4ZFXZH.png)
- 发现别的地方还有引用，那么就看看是在哪里被使用了，好像我们就只有一次sha512？难不成就是他？
- ![img_14.png](https://bbs.kanxue.com/upload/attach/202312/93_HCTYGSU26QQ33TN.png)
- 果然是他！没有白白分析！

#### 2be8

- ![img_15.png](https://bbs.kanxue.com/upload/attach/202312/93_FZ55UGZVM7M6MGS.png)
- sub_2be8调用的是sub_2948
- ![img_16.png](https://bbs.kanxue.com/upload/attach/202312/93_6URZVVDKRST7U95.png)
- 看到这里特别是下面的16位一轮的循环，还看不到啥，那我们就点击一下第一个函数瞧瞧sub_5DF4
- ![img_17.png](https://bbs.kanxue.com/upload/attach/202312/93_BMHX39JTNZDY6MZ.png)
- 经验丰富的大佬一眼就大概直到是啥了吧？哈哈哈哈
- 如果经验不丰富的咋办呢？是否有看到很多的不同数组，然后进去瞧瞧？
- ![img_18.png](https://bbs.kanxue.com/upload/attach/202312/93_9Q5HAKCXSZ2N3DB.png)
- 就看一下这个
- ![img_19.png](https://bbs.kanxue.com/upload/attach/202312/93_CXYT4W3GK4CDRBU.png)
- 好巧不巧sbox！
- 那就是aes了啦
- 那就可以猜测sub_5DF4是initKey了呢！毕竟那么早执行的就只有他了
- ![img_20.png](https://bbs.kanxue.com/upload/attach/202312/93_4N657JYCEKDV9XS.png)
- sub_6380好像没啥用不用管他
- ![img_21.png](https://bbs.kanxue.com/upload/attach/202312/93_U6UKEW6DWCNRH3R.png)
- 嘿嘿，跟这个就像是跟ctx的sk进行异或了
- ![img_22.png](https://bbs.kanxue.com/upload/attach/202312/93_QBSHJBEF37WXNYY.png)
- 又是老熟人了
- 那就到确认key&value的环境了，害
- 那还是得调试一下下了诶

| 1 | `debugger.addBreakPoint(module,` `0x2948``);` |
|-|-|

- ![img_23.png](https://bbs.kanxue.com/upload/attach/202312/93_Y8E6EDT4EDY4U8Y.png)
- 那按照惯例都看一下他们的实际值了
- x0
- ![img_24.png](https://bbs.kanxue.com/upload/attach/202312/93_ZF2R35R2GV5AKYH.png)
- 嘿，还有引用，看看又是哪里
- ![img_25.png](https://bbs.kanxue.com/upload/attach/202312/93_79AU7MJAGCUQWV8.png)
- 是sha512哪里的结果
- x1-->0x10
- x2
- ![img_26.png](https://bbs.kanxue.com/upload/attach/202312/93_85TCYGAS9SVPNE4.png)
- 紧接着x0，也是sha512的结果来的
- 推测：x0为key，x2为iv
- x3
- ![img_27.png](https://bbs.kanxue.com/upload/attach/202312/93_VCW2H2JZFW7MWMM.png)
- x4-->0x50
- 由一般的c++开发规律，前面的是地址后面的是大小
- 所以猜测：x3是代加密的文本、x4是文本大小
- x5
- ![img_28.png](https://bbs.kanxue.com/upload/attach/202312/93_6VEXPUN5978YGFA.png)
- 那么空白的像是输出
- x6
- ![img_29.png](https://bbs.kanxue.com/upload/attach/202312/93_48R5BJ78PEM9T6A.png)
- 像是输出的结果长度
- x7
- ![img_30.png](https://bbs.kanxue.com/upload/attach/202312/93_AM25QXVD8NWYMCS.png)
- 好像必要的参数都已经有了，也没必要继续分析了
- 那就直接写hook代码了！

| 1234567891011121314151617181920212223242526272829 | `hookZz.wrap(module.base +` `0x2948``,` `new` `WrapCallback<HookZzArm64RegisterContext>() {` `@Override``public` `void` `preCall(Emulator<?> emulator, HookZzArm64RegisterContext ctx, HookEntryInfo info) {``UnidbgPointer x0 = ctx.getPointerArg(``0``);``int` `x1 = ctx.getIntArg(``1``);``UnidbgPointer x2 = ctx.getPointerArg(``2``);``UnidbgPointer x3 = ctx.getPointerArg(``3``);``int` `x4 = ctx.getIntArg(``4``);` `byte``[] key = x0.getByteArray(``0``, x1);``byte``[] iv = x2.getByteArray(``0``, x1);``byte``[] input = x3.getByteArray(``0``, x4);` `Inspector.inspect(key,` `"key"``);``Inspector.inspect(iv,` `"iv"``);``Inspector.inspect(input,` `"input(aes)"``);` `UnidbgPointer x5 = ctx.getPointerArg(``5``);``int` `x6 = ctx.getPointerArg(``6``).getInt(``0``);``ctx.push(x5, x6);``}``@Override``public` `void` `postCall(Emulator<?> emulator, HookZzArm64RegisterContext ctx, HookEntryInfo info) {``UnidbgPointer x5 = ctx.pop();``int` `x6 = ctx.pop();``Inspector.inspect(x5.getByteArray(``0``, x6),` `"aes加密结果"``);``}``});` |
|-|-|

- ![img_31.png](https://bbs.kanxue.com/upload/attach/202312/93_CBG5H7JNPZU9BS2.png)
- 有输出了！那我们就比对一下看看能否解密！看看能否印证为aes！
- 通过我们的分析他有key又有iv像是cbc模式，所以我们去蒙一下，看看是否能蒙中！
- ![img_32.png](https://bbs.kanxue.com/upload/attach/202312/93_SF8VGFU5BC3XPXD.png)
- 好像直接就蒙中了？
-

#### 分析整理

- 其实分析到这里就有点蒙了，一下子出现那么多方法，其中又有三个是我们认为比较重要的，，，那我们该如何分析？答案是：我们还是以结果为导向，逆推分析！
- 毕竟我们分析了三个方法，看看他是否都有用得到呢~

##### 最后一段

- ![img_33.png](https://bbs.kanxue.com/upload/attach/202312/93_22ZMB475GJCX55S.png)
- 好像我们的结果最后一段就是aes加密后的诶
- 那我们回过头继续看看，看看是aes的input又在是啥
- ase的input
- ![img_34.png](https://bbs.kanxue.com/upload/attach/202312/93_G4979Y986ZM5GF4.png)
- 在这里有被传入！
- ![img_35.png](https://bbs.kanxue.com/upload/attach/202312/93_BNQ7JVZ8UY8Z7KB.png)
- 看着像是sha512（bytes）+bytes的拼接！

##### 中间段

- ![img_36.png](https://bbs.kanxue.com/upload/attach/202312/93_A5H5RVJMCWJ4PV3.png)
- 恰好我们的中间段也有在别的地方引用诶
- ![img_37.png](https://bbs.kanxue.com/upload/attach/202312/93_ZW3MBV6J2EYQ8EM.png)
- 刚好是在这里随机生成的诶！

#### 到这里我们就剩下最后一个问题了了，aes的key/iv如何生成？

- ![img_38.png](https://bbs.kanxue.com/upload/attach/202312/93_3GB5TTZTFV6PDCP.png)
- 也是有引用的诶！！！看看在哪！
- ![img_39.png](https://bbs.kanxue.com/upload/attach/202312/93_XMKCRC78V653224.png)
- 是sha512的值诶
- 那看看sha512的输入是啥
- ![img_40.png](https://bbs.kanxue.com/upload/attach/202312/93_ZSEZDMNJJQ899DZ.png)
- 又有引用诶，再看看这个引用又是啥？
- ![img_41.png](https://bbs.kanxue.com/upload/attach/202312/93_T6W8GTAPM32A4YU.png)
- 看着这个： 5C A5 E7 F7 3C 2B 01 CE CA BB DE C0 5C 8E A2 B9有点熟悉，是不是刚才出现过的！？？？
- 正是上面的随机数值诶！
- 那生成的还有一半的值呢？
- ![img_42.png](https://bbs.kanxue.com/upload/attach/202312/93_638YSUZSHN9RJPY.png)

| 1234 | `0040: 4D D4 C2 E6 B8 31 62 09 0E 52 B3 C7 A6 73 3B A4    M....1b..R...s;.``0050: 1C B2 46 2B 82 9A B5 8A 19 6B 39 DB 57 17 75 24    ..F+.....k9.W.u$``0060: F4 9B AF 7F 08 E8 D6 8D 26 A7 2E 37 C1 A9 5A 2F    ........&..7..Z/``0070: 1F 05 A5 18 92 AE F2 94 97 32 B6 2A 38 AA DD 58    .........2.*8..X` |
|-|-|

- 经过多次的测试，发现是固定值！

## 最后总结![img.png](https://bbs.kanxue.com/upload/attach/202312/93_S4V3FNZ2JJR87ZQ.png)

- 分析到这里基本整个流程都分析完毕了。
- 最终的逻辑代码我也没写，我也不会写。因为我没有这个业务的需求，如果需要的话，那么对着写就完事了，毕竟整个流程也是一目了然了。分析花了四五个小时，把整个过程水一遍写成文章也花费了四个小时。截至现在已经是2023年12月20日04点01分了。
- 害。狗命重要。明天再发上去了。。。
- 另外大佬们有好玩的类抽取壳，可以发样本给小弟我玩玩，最近捣鼓了一小玩具，测试的样本也有好几十个了，想继续完善一下。希望大佬们可以发一些有趣的类抽取样本，特别是那种不能回填到code_item上去的那种！
- 如果哪里写的不对，请大佬们多多赐教了，谢谢啦

## 2023年12月20日10点34分更新

- 通过大佬的反馈，那并不是固定值的！而是我们漏掉的！之所以为固定的是因为我们输入的固定！通过日志我们可以发现我们还少处理一个方法！这里备注为：查表的那个就是了~
- 那就把这个漏网之鱼抓捕回来看看它究竟是长的咋样子呢！

| 1 | `debugger.addBreakPoint(module,` `0x4500``);` |
|-|-|

- ![img_1.png](https://bbs.kanxue.com/upload/attach/202312/93_7ZWCDQUQAT92Q4B.png)
- 看着也像是一个指针，那就看看指针指向的内容吧！
- ![img.png](https://bbs.kanxue.com/upload/attach/202312/93_8YQ7QJ8PUAK6VAT.png)
- 好像有引用，那就看看他在哪里被用到了
- ![img_2.png](https://bbs.kanxue.com/upload/attach/202312/93_AEHD38HN9YRZ8JK.png)
- sha512的结果！
- 那就看看sha512的输入文本是啥呢？
- ![img_3.png](https://bbs.kanxue.com/upload/attach/202312/93_M967AAZK3VE6GQ2.png)
- 嘿嘿又有引用
- ![img_4.png](https://bbs.kanxue.com/upload/attach/202312/93_MUTS3TSAK7YBXVP.png)
- 还是随机值，那我们就知道他的输入为随机值的sha512的结果了
- 就简单分析一下这个方法，先看传递的参数只有一个result，然后又从result中获取三个值，那么这三个值就是：

| 12345678910 | `0-->80 60 35 40` `1-->00 00 00 00` `2-->40 00 00 00` `v1 = result[2];``v2 = *result;``v3 = result[1];` `就可以直到v1=0x40，v2为0x40356080，v3为0``v1 =` |
|-|-|

- ![img_5.png](https://bbs.kanxue.com/upload/attach/202312/93_WSG4Q65S75MY9JR.png)
- 这样子看的话，第一个ifif ( v1 )是true的，第二个if ( v1 < 0x20 )就为false了！
- 再往下看只有这里对地址写入内容了，那我们调试一下看看？
- ![img_6.png](https://bbs.kanxue.com/upload/attach/202312/93_F9KCWRTX3UT8GUD.png)
- 汇编对应的就是
- ![img_7.png](https://bbs.kanxue.com/upload/attach/202312/93_FKDAUEY9RCP7GAV.png)
- 那我们下一个断点看一下！

| 1 | `b0x4560` |
|-|-|

- ![img_8.png](https://bbs.kanxue.com/upload/attach/202312/93_7WYR5XFQMG59XV4.png)

| 1 | `>>> q0=0xa43b73a6c7b3520e096231b8e6c2d44d(1.8056244479338115E-263, -3.7768713601031674E-134) q1=0x24751757db396b198ab59a822b46b21c(-4.496232995265719E-257, 4.642831181428702E-133)` |
|-|-|

- 这两个q0跟q1是什么鬼，那我们咦好像就是我们上面所说的定值的了诶~
- 那再执行一下看看？
- ![img_9.png](https://bbs.kanxue.com/upload/attach/202312/93_93WCSV2HHDZAEGC.png)

| 1 | `q0=0x2f5aa9c1372ea7268dd6e8087faf9bf4(-5.367597597728704E-242, 1.4054386263309782E-80) q1=0x58ddaa382ab6329794f2ae9218a5051f(-9.09210480120694E-208, 1.1969099196948154E120)` |
|-|-|

- 让我们执行到底再看看？再结合一下我们上面所说的定值

| 1234 | `0040: 4D D4 C2 E6 B8 31 62 09 0E 52 B3 C7 A6 73 3B A4    M....1b..R...s;.``0050: 1C B2 46 2B 82 9A B5 8A 19 6B 39 DB 57 17 75 24    ..F+.....k9.W.u$``0060: F4 9B AF 7F 08 E8 D6 8D 26 A7 2E 37 C1 A9 5A 2F    ........&..7..Z/``0070: 1F 05 A5 18 92 AE F2 94 97 32 B6 2A 38 AA DD 58    .........2.*8..X` |
|-|-|

- 好像就完全的对的上了诶
- 嘿嘿，其实就是在这里来的。。。成功把这条漏网之鱼给补抓上了啦

---

# 回复

## 回复 by 陈可牛 (#2)

*2023-12-20 14:13*

图片加载不出来是因为chrome不支持加载http的协议图片了

微信中正常

![image](https://bbs.kanxue.com/upload/attach/202312/794149_DH4T9GAQZZGWHUH.webp)

## 回复 by 陈可牛 (#3)

*2023-12-20 14:14*

稍后会重新将https的协议处理一下就可以在chrome上查看图片了，很抱歉！

## 回复 by 陈可牛 (#4)

*2023-12-20 15:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  斯文这个禽兽](https://bbs.kanxue.com/user-794149.htm)
>
>  稍后会重新将https的协议处理一下就可以在chrome上查看图片了，很抱歉！
>
>

已经支持https的证书了。嘿嘿

## 回复 by mb_ldbucrik (#5)

*2023-12-21 08:50*

还是有些图片看不到呢

## 回复 by 陈可牛 (#6)

*2023-12-21 09:20*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>  还是有些图片看不到呢
>
>

不知道为啥，图片的地址都成了：https://bbs.kanxue.com/upload/attach/202312/794149_A3Y3XP6XFVXDCEY.jpg导致打开失败了~~~
而不是我的图床的地址了

## 回复 by Editor (#7)

*2023-12-21 09:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  斯文这个禽兽](https://bbs.kanxue.com/user-794149.htm)
>
>  不知道为啥，图片的地址都成了：https://bbs.kanxue.com/upload/attach/202312/794149_A3Y3XP6XFVXDCEY.jpg导致打开失败了~~~
> 而不是 ...
>
>

将原始md文件发邮件我一下，估计是图片本地化出问题了：service@kanxue.com

## 回复 by 陈可牛 (#8)

*2023-12-21 10:39*

>
> [Editor](https://bbs.kanxue.com/user-236762.htm)
>
>  将原始md文件发邮件我一下，估计是图片本地化出问题了：service@kanxue.com
>
>

已经发送过去了呢！

## 回复 by 哆啦噩梦 (#9)

*2023-12-21 11:15*

看完了，学不会

## 回复 by IamHuskar (#10)

*2023-12-21 11:26*

看完了，学不会

## 回复 by 陈可牛 (#11)

*2023-12-21 11:26*

大佬别说笑啦

## 回复 by LowRebSwrd (#12)

*2023-12-21 18:49*

赞！

## 回复 by m2kar (#13)

*2023-12-26 00:47*

膜拜大佬，精品TT分析

## 回复 by lizhenzhe (#14)

*2024-1-3 11:17*

分析的很详细，想问下楼主有没有遇到unidbg trace arm64的汇编指令，有的函数trace不到的情况

## 回复 by 陈可牛 (#15)

*2024-1-3 14:07*

>
> [lizhenzhe](https://bbs.kanxue.com/user-409601.htm)
>
>  分析的很详细，想问下楼主有没有遇到unidbg trace arm64的汇编指令，有的函数trace不到的情况
>
>

没有，但是可以选择trace更大的范围，比如Long.MIN_VALUE, Long.MAX_VALUE。这样子基本所有的模块都包含在内了。//        TraceHook trace = emulator.traceCode(Long.MIN_VALUE, Long.MAX_VALUE, new TraceCodeListener() {
//            @Override
//            public void onInstruction(Emulator<?> emulator, long address, Instruction insn) {
//            }
//        });

## 回复 by mb_zfqvurgb (#16)

*2024-10-1 11:50*

牛逼，大佬四五小时分析完，我四五小时差不多看明白

## 回复 by hmlyn (#17)

*2025-11-4 15:02*

666
