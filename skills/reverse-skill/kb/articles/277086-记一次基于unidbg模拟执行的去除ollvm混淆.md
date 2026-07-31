---
title: '[原创]记一次基于unidbg模拟执行的去除ollvm混淆'
url: https://bbs.kanxue.com/thread-277086.htm
tid: 277086
author: 乐子人
date: '2023-05-03'
tags: [Android安全, 原创, 逆向分析, NDK分析, 混淆加固, 脱壳反混淆, 程序开发, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T14:49:01+08:00'
replies: 66
---

# 0.前言

代码混淆是逆向分析中最令人头疼的问题之一。

 面对混淆，通常的做法是直接硬着头皮调试，因为混淆只能混淆代码的形，但是代码的神——执行逻辑是不会变的，单步调试下去往往能梳理出程序本身的执行逻辑。但是面对非常复杂的混淆，小弟我也是经常调试数十小时最终招架不住选择放弃。。。有位伟人曾经说过“安全保护的目的不在于让代码固若金汤，无法攻破，而是在于让破解者望而生畏，主动放弃”，正所谓“不战而屈人之兵，善之善也~”，小弟我深以为然。

 面对混淆更好的做法是去混淆，或者说反混淆，就是将混淆过的代码还原回去。还原后的代码通常逻辑清晰，通俗易懂，可以很简单的进行分析。但是反混淆往往比较难，抛开各种定制的混淆不说，即使是最基本的ollvm混淆，还原起来也不是那么容易。因为还原混淆通常要依赖于符号执行，模拟执行，指令trace等一系列高级的逆向手法。小弟我最近刚好遇到一个混淆的样本，趁着五一放假，研究了一下反混淆的方法，最终成功还原出了真实逻辑，故借此机会和看雪各位安全爱好者做一分享。
 ![image](https://bbs.kanxue.com/upload/attach/202305/872365_A99C7H8CJ84NXC5.png)

 混淆前的程序，可以看到在 br x9 后ida无法分析了，因为x9是一个寄存器，ida并不知道里面是什么值，所以无法继续向下分析。F5后可以看到，函数调用jni->GetEnv函数后就jumpout了。

  ![image](https://bbs.kanxue.com/upload/attach/202305/872365_B42EXRHYUWVR3U2.png)
往下查看汇编代码，可以看到函数里有许多根据寄存器跳转的指令：

  ![image](https://bbs.kanxue.com/upload/attach/202305/872365_ARURQ4UENRGUXF6.png)

# 1.unidbg环境搭建

去混淆通常要对代码进行模拟执行。

 模拟执行届扛把子的是unicorn引擎。不过unicorn引擎相对比较底层，需要手动的开辟内存，将指令写入，设置堆栈的位置，设置寄存器初始值，然后执行。unidbg是基于unicorn引擎的模拟执行框架，使用java语言编写，并且可以直接加载so，进行调用（unidbg在加载动态库时自动帮你完成了文件解析，映射，重定位，写入unicorn引擎等一系列底层操作），同时unidbg内置了Jni相关的环境，而unicorn本身没有相关环境，需要手动补充。同时，unidbg还内置了hookZz，xHook等一系列hook框架，可以很方便的进行函数级，指令级的各种hook。总之，unidbg大大方便了逆向人员进行模拟执行的流程，所以我们选用unidbg来进行模拟执行。

## 1.1 下载源码

unidbg的工作模式简单粗暴，直接git clone unidbg的项目，然后在项目里添加自己的模拟执行类，最终运行的时候是带着整个项目的源码一起运行的，这样做的好处是方便了定制化修改和源码调试。

  ![image](https://bbs.kanxue.com/upload/attach/202305/872365_AZUAZCW4GHCMWAY.png)

 下载好后使用idea进行打开。

## 1.2 模拟执行

直接在项目的unidbg-android/src/test/java目录下建立我们的模拟执行类：AntiOllvm

 在进行模拟执行之前，需要做以下准备工作：

 1.创建一个模拟器。

 2.设置android系统库的版本

 3.创建android虚拟机

 4.加载动态库

| 123456789101112131415161718 | `public AntiOllvm()``{``/``/``创建模拟器``emulator` `=` `AndroidEmulatorBuilder``.for64Bit()``.addBackendFactory(new Unicorn2Factory(true))``.setProcessName(``"com.example.antiollvm"``)``.build();``Memory memory` `=` `emulator.getMemory();``/``/``设置andorid系统库版本``memory.setLibraryResolver(new AndroidResolver(``26``));``/``/``创建虚拟机``vm` `=` `emulator.createDalvikVM();``vm.setVerbose(true);``/``/``加载动态库``dm` `=` `vm.loadLibrary(new` `File``(``"f:\\kshs\\libtprt.so"``), false);``module` `=` `dm.getModule();``}` |
|-|-|

这样，动态库就被unidbg加载了。

 加载后需要先执行jni_onload，而DalvikModule这个类已经实现了callJNI_OnLoad方法，我们直接调用即可。

| 123456789 | `public static void main(String[] args) {``AntiOllvm ao` `=` `new AntiOllvm();``ao.callJniOnload();``}` `public void callJniOnload()``{``dm.callJNI_OnLoad(emulator);``}` |
|-|-|

调用后，出现了报错和许多warning：

  ![image](https://bbs.kanxue.com/upload/attach/202305/872365_VEP2WYTHRF9DU6E.png)

 一方面，有许多libc的函数没有找到，另一方面，JNI返回了-1。

 我们先补充所需的libc函数，只需要把手机里/system/lib64/libc.so等系统库交给unidbg加载即可。

 将下列代码添加到加载目标so之前：

| 12345 | `vm.loadLibrary(new` `File``(``"f:\\androidlib\\libc.so"``),false);``vm.loadLibrary(new` `File``(``"f:\\androidlib\\libm.so"``),false);``vm.loadLibrary(new` `File``(``"f:\\androidlib\\libstdc++.so"``),false);``vm.loadLibrary(new` `File``(``"f:\\androidlib\\ld-android.so"``),false);``vm.loadLibrary(new` `File``(``"f:\\androidlib\\libdl.so"``),false);` |
|-|-|

再次执行，这次运行成功了，并且unidbg hook 了所有的jni掉用，也将他们打印了出来：

  ![image](https://bbs.kanxue.com/upload/attach/202305/872365_DZ6EH66SXZXUE4C.png)

 可以看到，在0x5e900处调用了registernative，注册的函数名叫：initialize，签名是：(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;[Ljava/lang/String;Ljava/lang/String;)I，函数的地址在0x5e1e8处。

 至此，我们成功使用unidbg加载了android的动态库，并且正常运行了动态库的jni_onload函数。

## 1.3 基本的hook

我们已经成功运行了目标动态库，接下来可以看看还能做些什么。我们做一个最基本的操作，使用指令hook，在每条指令执行之前将其打印出来。

| 12345678910111213141516171819202122 | `public void logIns()``{``emulator.getBackend().hook_add_new(new CodeHook() {``@Override``public void hook(Backend backend,` `long` `address,` `int` `size,` `Object` `user)  {``Capstone capstone` `=` `new Capstone(Capstone.CS_ARCH_ARM64,Capstone.CS_MODE_ARM);``byte[] bytes` `=` `emulator.getBackend().mem_read(address,` `4``);``Instruction[] disasm` `=` `capstone.disasm(bytes,` `0``);``System.out.printf(``"%x:%s %s\n"``,address``-``module.base ,disasm[``0``].getMnemonic(),disasm[``0``].getOpStr());``}` `@Override``public void onAttach(UnHook unHook) {` `}` `@Override``public void detach() {` `}``}, module.base, module.base``+``module.size, null);``}` |
|-|-|

使用到的是unicorn引擎提供的codehook，即指令hook。我们在指令执行前进行hook，然后初始化Capstone引擎（反汇编引擎），接着通过unicorn的接口从当前地址读取4字节机器码，再将机器码反汇编，然后打印输出。我们可以将hook的范围指定在一个函数中，这样就不会打印超出该函数范围的指令了：
 ![image](https://bbs.kanxue.com/upload/attach/202305/872365_XX57B726ED6D6BD.png)

 可以看到，打印的指令和ida中解析出的jnionload函数指令一致。当然，我们也看到了br x9之后的那条指令：
 ![image](https://bbs.kanxue.com/upload/attach/202305/872365_X3CKYP8N2ZXBYV8.png)

 跳转到0x5e480,又执行了若干组间接跳转。

 至此，我们已经可以通过unidbg的接口，进行指令trace。同时我们还可以使用unidbg提供的其他接口，在hook的同时读取，写入寄存器，查看内存，修改内存，设置断点等等。接下来我们就可以开始着手去混淆了。

# 2.去除间接跳转

首先要解决的是 br x9 的问题，至少让ida能F5吧。

 通过阅读汇编代码，可以看到该函数的混淆是这样做的：

 1.比较 w8 和 wk(另外一个寄存器，不固定)寄存器。

 2.根据比较的结果，选择xA或者xB寄存器的值赋值给X9

 3.从x9 + x19的地址处读取一个值，赋值给x9

 4.x9 = x9 + x24

 5.跳转到x9指向的位置。

 其中，x19和x24始终是固定的，我们看到，x19和x24在程序开始时被初始化了：

  ![image](https://bbs.kanxue.com/upload/attach/202305/872365_YBZGDHZ3CC3EGZ2.png)

  ![image](https://bbs.kanxue.com/upload/attach/202305/872365_ZP2BHV4Z6UB97GZ.png)

 可以看到，X19是0x140080，而0x140080是一个数组
![image](https://bbs.kanxue.com/upload/attach/202305/872365_35B5TWZQNHEHJQH.png)

 x24则为固定的值0x3a2cd438

 这里就理解这个间接跳转是怎么做的了，每次根据比较结果在数组中选择一个偏移，然后用偏移加上基数，得到真实的跳转地址。

 所以我们可以在每次执行到br x9的时候获取x9的真实值，然后将根据寄存器跳转的指令br 换成直接跳转b，这样ida就可以继续分析了。

 直接这样做有一个问题，因为偏移值是根据比较结果不同而不同，如果我们直接将最终的跳转地址写死，那就相当于将原来的条件跳转改为了直接跳转，改变了逻辑。

 所以正确的做法是保留条件，计算出条件成立与不成立时对应的跳转地址，然后将br x9改为一条条件跳转和一条直接跳转，这样做就和原来的逻辑完全一致了，并且所有的跳转都是有确定的地址，ida可以分析。

 于是我们用这样的算法进行还原：

 1.建立一个指令栈，每条指令执行前，保留该指令的地址，指令内容，当前所有寄存器的值。然后将当前指令的信息push进指令栈。

 2.对指令进行回溯，如果栈顶指令是br x9,则进行3，否则执行下一条指令。

 3.pop跳转指令，再次获取栈顶指令，检查是否为ADD x9,x9,x24指令，如果是，进行4，否则执行下一条指令。

 4.pop add指令，再次获取栈顶指令，检查是否为LDR x9,[x19,x9]指令，如果是，则进行5，否则执行下一条指令。

 5.pop 加载指令，再次获取栈顶指令，检查是否为条件选择指令。如果是，记录选择条件，记录为条件成立与不成立时对应的选择的值（通过保留的寄存器值获取）。否则执行下一条指令。

 6.pop 条件选择指令，获取到上一次 比较指令，检查是否是cmp x8,类型的指令，如果是，进行7，否则执行下一条指令。

 7.通过前六步，说明我们已经定位到了正确的间接跳转的位置。然后分别计算条件成立与不成立时对应的真实跳转地址，将Add 指令替换为 条件跳转->成立时地址，将br x9替换为直接跳转->条件不成立地址。

 以以下指令为例：

| 12345 | `CMP`             `W8, W27``CSEL            X9, X28, X23, LT``LDR             X9, [X19,X9]``ADD             X9, X9, X24``BR              X9` |
|-|-|

在csel 一步，当条件LT成立时，x9 = x28。真实的跳转地址为

| 1 | `*``（x19``+``x28）``+``x24` `/``/``记为addrT。` |
|-|-|

当条件不成立时，x9 = x23。真实的跳转地址为：

| 1 | `*``(x19``+``x23)``+``x24` `/``/``记为addrF。` |
|-|-|

然后将add X9, X9, X24指令替换为b.lt addrT,
将br x9 指令替换为 b addrF。
将条件选择和加载指令nop掉。
替换后的指令为：

| 12345 | `CMP`            `W8, W27``NOP``NOP``BLT            addrT``B              addrF` |
|-|-|

这样所有的间接跳转都变成了直接跳转，ida是可以分析的，并且逻辑与之前完全相同，我们所做的只不过是提前计算出目标地址，然后直接跳转罢了。

 对应的java代码如下：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251 | `/``/``保存指令和寄存器环境类：``class` `InsAndCtx``{``long` `addr;``Instruction ins;``List``<Number> regs;` `public` `long` `getAddr() {``return` `addr;``}` `public void setAddr(``long` `addr) {``this.addr` `=` `addr;``}` `public void setIns(Instruction ins) {``this.ins` `=` `ins;``}` `public Instruction getIns() {``return` `ins;``}` `public void setRegs(``List``<Number> regs) {``this.regs` `=` `regs;``}` `public` `List``<Number> getRegs() {``return` `regs;``}``}` `/``/``patch类``class` `PatchIns{``long` `addr;``/``/``patch 地址``String ins;``/``/``patch的指令` `public` `long` `getAddr() {``return` `addr;``}` `public void setAddr(``long` `addr) {``this.addr` `=` `addr;``}` `public String getIns() {``return` `ins;``}` `public void setIns(String ins) {``this.ins` `=` `ins;``}``}` `/``/` `指令栈` `private  Stack<InsAndCtx> instructions;` `/``/``所有需要patch的指令``private` `List``<PatchIns> patchs;` `/``/``保存指令寄存器环境``public` `List``<Number> saveRegs(Backend bk)``{``List``<Number> nb` `=` `new ArrayList<>();``for``(``int` `i``=``0``;i<``29``;i``+``+``)``{``nb.add(bk.reg_read(i``+``Arm64Const.UC_ARM64_REG_X0));``}``nb.add(bk.reg_read(Arm64Const.UC_ARM64_REG_FP));``nb.add(bk.reg_read(Arm64Const.UC_ARM64_REG_LR));``return` `nb;``}`  `/``/``指令hook，每条指令执行前保存环境``public void processBr()``{``emulator.getBackend().hook_add_new(new CodeHook() {``@Override``public void hook(Backend backend,` `long` `address,` `int` `size,` `Object` `user) {``Capstone capstone` `=` `new Capstone(Capstone.CS_ARCH_ARM64,Capstone.CS_MODE_ARM);``byte[] bytes` `=` `emulator.getBackend().mem_read(address,` `4``);``Instruction[] disasm` `=` `capstone.disasm(bytes,` `0``);``InsAndCtx iac` `=` `new InsAndCtx();``iac.setIns(disasm[``0``]);``iac.setRegs(saveRegs(backend));``iac.setAddr(address);``instructions.push(iac);``do_processbr();``}` `@Override``public void onAttach(UnHook unHook) {``System.out.println(``"attach"``);``}` `@Override``public void detach() {``System.out.println(``"detach"``);``}``},module.base``+``start, module.base``+``end,null);``}` `/``/``指令栈回溯，根据处理结果，生成patchIns，供最后统一patch``public void do_processbr()``{``Instruction ins` `=` `instructions.peek().getIns();``if``(ins.getMnemonic().equals(``"br"``) && ins.getOpStr().equals(``"x9"``))``{``boolean finish` `=` `false;``long` `base` `=` `-``1``;``long` `listoffset` `=` `-``1``;``long` `cond1` `=` `-``1``;``long` `cond2` `=` `-``1``;``String cond` `=` `"";``long` `addinstaddr` `=` `-``1``;``long` `brinsaddr` `=` `instructions.peek().getAddr()` `-` `module.base;``long` `selectaddr` `=` `-``1``;``long` `ldaaddr` `=` `-``1``;` `try` `{``while` `(!finish && !instructions.empty())``{``instructions.pop();``ins` `=` `instructions.peek().getIns();``if``(ins.getMnemonic().toLowerCase(Locale.ROOT).equals(``"add"``))``{``String[] split` `=` `ins.getOpStr().split(``","``);``if``(split.length` `=``=` `3``)``{``if``(split[``0``].toLowerCase(Locale.ROOT).trim().equals(``"x9"``) && split[``1``].toLowerCase(Locale.ROOT).trim().equals(``"x9"``))``{``String reg` `=` `split[``2``].trim().toLowerCase(Locale.ROOT);``base` `=` `getRegValue(reg,instructions.peek().getRegs()).longValue();``addinstaddr` `=` `instructions.peek().getAddr()` `-` `module.base;``}``else` `{``break``;``}``}``else``{``break``;``}``}` `if``(ins.getMnemonic().toLowerCase(Locale.ROOT).equals(``"ldr"``))``{``String[] sp` `=` `ins.getOpStr().toLowerCase().split(``","``);``if``(sp.length` `=``=` `3``)``{``if``(sp[``0``].trim().toLowerCase(Locale.ROOT).equals(``"x9"``) && sp[``2``].trim().toLowerCase(Locale.ROOT).equals(``"x9]"``))``{``String reg` `=` `sp[``1``].toLowerCase(Locale.ROOT).trim().substring(``1``);``listoffset` `=` `getRegValue(reg,instructions.peek().getRegs()).longValue()``-``module.base;``ldaaddr` `=`  `instructions.peek().getAddr()``-` `module.base;``}``}``}` `if``(ins.getMnemonic().trim().toLowerCase(Locale.ROOT).equals(``"csel"``))``{``String[] sp` `=` `ins.getOpStr().toLowerCase(Locale.ROOT).split(``","``);``if``(sp.length` `=``=` `4``)``{``cond` `=` `sp[``3``].trim();``if``(sp[``0``].trim().equals(``"x9"``))``{``String reg1` `=` `sp[``1``].trim();``String reg2` `=` `sp[``2``].trim();``cond1` `=` `getRegValue(reg1,instructions.peek().getRegs()).longValue();``cond2` `=` `getRegValue(reg2,instructions.peek().getRegs()).longValue();``selectaddr` `=` `instructions.peek().getAddr()` `-` `module.base;``}``}``}` `if``(ins.getMnemonic().trim().toLowerCase(Locale.ROOT).equals(``"cmp"``))``{``if``(base` `=``=` `-``1` `\|\| listoffset` `=``=` `-``1` `\|\| cond1` `=``=` `-``1` `\|\| cond2` `=``=` `-``1` `\|\| cond.equals("") \|\| addinstaddr` `=``=` `-``1` `\|\| ldaaddr` `=``=` `-``1` `\|\| selectaddr` `=``=` `-``1``)``{``break``;``}``else``{``long` `offset1` `=` `base` `+` `readInt64(emulator.getBackend(), module.base``+``listoffset``+``cond1)` `-` `module.base;``long` `offset2` `=` `base` `+` `readInt64(emulator.getBackend(),module.base``+``listoffset``+``cond2)` `-` `module.base;``if``( brinsaddr` `-` `addinstaddr !``=` `4``)``{``System.out.println(``"add ins and br ins gap more than 4 size,may make mistake"``);``}``String condBr` `=` `"b"``+``cond.toLowerCase(Locale.ROOT)` `+` `" 0x"``+` `Integer.toHexString((``int``) (offset1` `-` `addinstaddr));``String br` `=` `"b 0x"` `+` `Integer.toHexString((``int``)(offset2` `-` `brinsaddr));``PatchIns pi1` `=` `new PatchIns();``pi1.setAddr(addinstaddr);``pi1.setIns(condBr);``patchs.add(pi1);``PatchIns pi2` `=` `new PatchIns();``pi2.setAddr(brinsaddr);``pi2.setIns(br);``patchs.add(pi2);``PatchIns pi3` `=` `new PatchIns();``pi3.setAddr(selectaddr);``pi3.setIns(``"nop"``);``patchs.add(pi3);``PatchIns pi4` `=` `new PatchIns();``pi4.setAddr(ldaaddr);``pi4.setIns(``"nop"``);``patchs.add(pi4);``finish` `=` `true;``}``}``}``}catch (Exception e)``{``e.printStackTrace();``}``}``}` `/``/``遍历patch表，执行patch，生成新的so，使用Ketstone将汇编转为机器码。``public void patch()``{``try` `{``File` `f` `=` `new` `File``(inName);``FileInputStream fis` `=` `new FileInputStream(f);``byte[] data` `=` `new byte[(``int``) f.length()];``fis.read(data);``fis.close();``for``(PatchIns pi:patchs)``{``System.out.println(``"procrss addr:"``+``Integer.toHexString((``int``) pi.addr)``+``",code:"``+``pi.getIns());``Keystone ks` `=` `new Keystone(KeystoneArchitecture.Arm64, KeystoneMode.LittleEndian);``KeystoneEncoded assemble` `=` `ks.assemble(pi.getIns());``for``(``int` `i``=``0``;i<assemble.getMachineCode().length;i``+``+``)``{``data[(``int``) pi.addr``+``i]` `=` `assemble.getMachineCode()[i];``}``}``File` `fo` `=` `new` `File``(outName);``FileOutputStream fos` `=` `new FileOutputStream(fo);``fos.write(data);``fos.flush();``fos.close();``System.out.println(``"finish"``);``}``catch (Exception e)``{``e.printStackTrace();``}``}` |
|-|-|

patch完成后，再次使用ida打开原so，发现Jni_onLoad函数已经可以F5了：

  ![image](https://bbs.kanxue.com/upload/attach/202305/872365_ZDSR8F5KX84NM62.png)

 但是依然有一些jumpout。

 原因是因为在模拟执行的是后并没有走遍所有的分支，我们只是将走过的分支处理了。

 接下来需要在jumpout的地方手动修改寄存器的值，来控制他的走势，让unidbg最终走完所有分支。

 比如对于这一处br，在blt时才会跳转过去，
 ![image](https://bbs.kanxue.com/upload/attach/202305/872365_MZ5XZJH5NDC68Y6.png)

 可以看到这一处的跳转和w12有关，我们找到给w8赋值为w12的地方，通过修改寄存器来给其赋值：
 ![image](https://bbs.kanxue.com/upload/attach/202305/872365_TT8NKKZ3AY7V6P2.png)
 ![image](https://bbs.kanxue.com/upload/attach/202305/872365_4JREVVME3BAYZPT.png)

 重新跑一边代码，这一处的br x9 就修复了。将没有走到的分支处理完后，F5结果如下：
 ![image](https://bbs.kanxue.com/upload/attach/202305/872365_Y59FJNYRJ7MYKEY.png)

 可以看到是标准的ollvm的控制流平坦化。

 所以br x9的混淆其实是在ollvm控制流平坦化的基础上，将所有的跳转地址都加了一步运算。

# 3.去除控制流平坦化

间接跳转去除完后，需要去除控制流平坦化。根据控制流平坦化的工作原理，原来的代码会被打碎成代码片段，然后装进一个大的switch case里，最外层包一个while true循环，根据索引变量来按照原来的顺序执行代码。
 ![image](https://bbs.kanxue.com/upload/attach/202305/872365_T3F226Q4K8FV9VR.png)

 考虑到编译的结果要在逻辑上和原来的代码完全一致，所以一个重要的结论是——真实的代码块一定在cmp eq 之后。（switch case 的一个case）

 控制流平坦化对于顺序执行的处理比较简单，直接在前一个真实块的末尾，将索引值改为下一个真实块的索引，然后跳转到主分发器即可。

 对于分支执行（判断，循环），在条件的部分会有一个条件选择指令CSEl，将索引寄存器的值根据条件结果设置为不同的索引，然后跳转到主分发器。

 所以我们可以按照以下算法对控制流平坦化进行还原：

 1.建立一个指令栈，每条指令执行前，保留该指令的地址，指令内容，当前所有寄存器的值。然后将当前指令的信息push进指令栈。

 2.对指令进行回溯，如果栈顶指令是b.eq，则进行3（收集真实块），如果栈顶指令是直接跳转指令b，则进行5（处理分支块），否则继续执行下一条指令。

 3.向上回溯指令栈，找到第一条cmp 指令，判断是否为与索引寄存器w8 比较，如果是，则进行4，否则继续执行下一条指令。

 4.获取与w8比较的另一个寄存器的值，获取b.eq的目标地址，组成一个（索引，真实块）对。继续执行下一条指令。

 5.判断上一条指令是否为CSEL W8。如果是，则记录一个（条件成立块索引，条件不成立块索引）对。否则，继续执行下一条指令。

 同时，我们在主分发器处hook 指令，记录每次经过主分发器时的索引寄存器的值为索引值顺序。

 在模拟执行收集完成信息之后，做以下处理：

 1.去除索引值顺序中为条件块的索引。

 2.获取索引值顺序中的第一个值，找到对应的真实块。将主分发器处patch为跳转向第一个真实块的跳转指令。

 3.根据真实块结束时的新的索引值，寻找到对应的真实块，将结尾处patch为跳转到下一个真实块。

 4.在CSEL指令处，根据条件成立块索引和条件不成立索引找到对应的真实块。将CSEL指令和后面的跳转向主分发器的指令patch为两条指令：

 第一条为条件成立时的条件跳转，第二条为条件不成立时的直接跳转。

 对应的代码如下:

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170 | `/``/``用于记录条件块中，条件成立，条件不成立时对应的索引值，同时记录条件。``class` `selectBr``{``long` `insaddr;``long` `trueindex;``long` `falseindex;``String cond;``public String getCond() {``return` `cond;``}``public void setCond(String cond) {``this.cond` `=` `cond;``}``public` `long` `getInsaddr() {``return` `insaddr;``}``public void setInsaddr(``long` `insaddr) {``this.insaddr` `=` `insaddr;``}``public` `long` `getTrueindex() {``return` `trueindex;``}``public void setTrueindex(``long` `trueindex) {``this.trueindex` `=` `trueindex;``}``public` `long` `getFalseindex() {``return` `falseindex;``}``public void setFalseindex(``long` `falseindex) {``this.falseindex` `=` `falseindex;``}``}``/``/``真实块，索引值和开始地址``class` `TrueBlock{` `long` `index;``long` `startAddr;` `public TrueBlock(){}``public TrueBlock(``long` `l,``long` `s)``{``index` `=` `l;``startAddr` `=` `s;``}` `public` `long` `getIndex() {``return` `index;``}` `public void setIndex(``long` `index) {``this.index` `=` `index;``}` `public` `long` `getStartAddr() {``return` `startAddr;``}` `public void setStartAddr(``long` `startAddr) {``this.startAddr` `=` `startAddr;``}``}` `/``/``记录真实块``private` `List``<TrueBlock>tbs;``/``/``记录条件块``private` `List``<selectBr> sbs ;``/``/``记录索引顺序``private` `List``<``Long``> indexOrder;` `public void processFlt()``{``emulator.getBackend().hook_add_new(new CodeHook() {``@Override``public void hook(Backend backend,` `long` `address,` `int` `size,` `Object` `user) {``Capstone capstone` `=` `new Capstone(Capstone.CS_ARCH_ARM64,Capstone.CS_MODE_ARM);``byte[] bytes` `=` `emulator.getBackend().mem_read(address,` `4``);``Instruction[] disasm` `=` `capstone.disasm(bytes,` `0``);``InsAndCtx iac` `=` `new InsAndCtx();``iac.setIns(disasm[``0``]);``iac.setRegs(saveRegs(backend));``iac.setAddr(address);``instructions.add(iac);``do_processflt();``}` `@Override``public void onAttach(UnHook unHook) {``System.out.println(``"attach"``);``}` `@Override``public void detach() {``System.out.println(``"detach"``);``}``},module.base``+``start, module.base``+``end, null);``}``public void do_processflt()``{``if``(instructions.empty())``{``return``;``}``Instruction ins` `=` `instructions.peek().getIns();``if``(instructions.peek().getAddr()` `-` `module.base` `=``=` `dispatcher)``{``indexOrder.add(getRegValue(``"x8"``,instructions.peek().getRegs()).longValue());``}``if``(ins.getMnemonic().toLowerCase(Locale.ROOT).equals(``"b.eq"``)) {``InsAndCtx beq` `=` `instructions.peek();``/``/``等于跳转，检查是否为``cmp` `x8,``while` `(true)``{``if``(instructions.empty())``{``break``;``}``instructions.pop();``ins` `=` `instructions.peek().getIns();``if``(ins.getMnemonic().toLowerCase(Locale.ROOT).equals(``"cmp"``))``{``String[] sp` `=` `ins.getOpStr().toLowerCase(Locale.ROOT).split(``","``);``if``(sp[``0``].equals(``"w8"``))``{``/``/``找到一个真实块``TrueBlock tb` `=` `new TrueBlock();``long` `regValue` `=` `getRegValue(sp[``1``].trim(), instructions.peek().getRegs()).longValue();``long` `targetAddr` `=` `0``;``String offset` `=` `beq.getIns().getOpStr().toLowerCase(Locale.ROOT);``long` `offsetvalue` `=` `getLongFromOpConst(offset);``targetAddr` `=` `beq.getAddr()` `+` `offsetvalue` `-` `module.base;``tb.setIndex(regValue);``tb.setStartAddr(targetAddr);``tbs.add(tb);``break``;``}``}``}``}``/``/``处理分支块``if``(ins.getMnemonic().toLowerCase(Locale.ROOT).equals(``"b"``))``{``long` `offset` `=` `getLongFromOpConst(ins.getOpStr());``if``(offset !``=` `0``)``{``long` `target` `=` `offset` `+` `instructions.peek().getAddr()` `-` `module.base;``/``/``直接跳向主发生器``if``(target` `=``=` `dispatcher)``{``instructions.pop();``ins` `=` `instructions.peek().getIns();``if``(ins.getMnemonic().toLowerCase(Locale.ROOT).equals(``"csel"``))``{``String[] sp` `=` `ins.getOpStr().toLowerCase(Locale.ROOT).split(``","``);``if``(sp[``0``].trim().equals(``"w8"``))``{``String cond` `=` `sp[``3``].trim();``String reg1` `=` `sp[``1``].trim();``String reg2` `=` `sp[``2``].trim();``selectBr sb` `=` `new selectBr();``sb.setInsaddr(instructions.peek().getAddr()` `-` `module.base);``sb.setCond(cond);``sb.setTrueindex(getRegValue(reg1,instructions.peek().getRegs()).longValue());``sb.setFalseindex(getRegValue(reg2,instructions.peek().getRegs()).longValue());``sbs.add(sb);``}``}``}``}``}``}` |
|-|-|

在模拟执行完后，发现有一些索引值没有找到对应的块：
 ![image](https://bbs.kanxue.com/upload/attach/202305/872365_FM4PT5VNQ9WQGVY.png)

 查看他们的索引，发现刚好是条件块中的索引。这个也好理解，因为在模拟执行的时候我们只走了条件的一个分支，没有走另一个分支，所以就没有记录下对应的真实块。这里我们手动根据b.eq和寄存器的值，添加对应的真实块：
 ![image](https://bbs.kanxue.com/upload/attach/202305/872365_F3NFE72AA9UGAUW.png)

 添加完成后，再次运行程序，发现已经patch成功了。打开ida查看Jni_onload:

  ![image](https://bbs.kanxue.com/upload/attach/202305/872365_FCZ6TP6324NSFSQ.png)

 发现函数已经被完美的还原了。

# 4.总结

借着五一假期简单研究了一下模拟执行和去混淆，感慨unidbg是真的强。我认为我使用的方法应该是没有任何逻辑漏洞，可以完全等效的还原的。

 间接跳转的还原比较简单，控制流平坦化的还原则比较难。

 控制流平坦化还原的最大难点在与找到真实块与索引之间的关系。由于我这次使用的样本对于跳转做了混淆，虽然难住了ida，但是也可能难住了编译器，导致对控制流平坦化部分没有做复杂的编译优化——所有的真实块都在b.eq后面，并且只有一个主分发器，没有次分发器。同时真实块执行结束都很乖巧的跳转到了分发器（有的编译优化会直接将两个真实块连在一起）。

 总体来说，本次反混淆不是特别完美，有手工的部分，同时也不能通杀所有混淆，只能说提供一种反混淆思路和经验吧。

 ollvm反混淆感觉是永无止境的，目前还没有见到有什么非常强大，通杀，可以完美还原的方案，只能针对目标混淆器定制反混淆策略。

 安全攻防不息，吾辈仍需努力！

上传的附件：
- AntiOllvm.java

（22.16kb，640次下载）

---

# 回复

## 回复 by mb_rjdrqvpa (#2)

*2023-5-4 10:26*

大佬，请给个案例so

## 回复 by New对象处 (#3)

*2023-5-4 10:28*

666

## 回复 by 北辰清影 (#4)

*2023-5-4 10:41*

大佬，请给个案例so

## 回复 by Circ1e (#5)

*2023-5-4 10:54*

精彩

## 回复 by mb_wpitiize (#6)

*2023-5-4 10:59*

大佬，请给个案例so

## 回复 by koflfy (#7)

*2023-5-4 11:28*

nice ，mark

## 回复 by 乐子人 (#8)

*2023-5-4 11:30*

样本随便找几个国产游戏，米or腾的，找到里面的libtprt.so就行

## 回复 by guijian (#9)

*2023-5-4 17:56*

谢谢分享！

## 回复 by New对象处 (#10)

*2023-5-6 13:04*

大佬，我第一次patch后

![image](https://bbs.kanxue.com/upload/attach/202305/807696_FGAHEJCYJ73JU4Y.jpg)

按照大佬的思路，让0x62138 w8的寄存器改为0x1让其执行到loc_62158，拿第一次patch后的so去重新跑一次代码

![image](https://bbs.kanxue.com/upload/attach/202305/807696_99PVE4SMNQSFWHF.jpg)

修改w8寄存器值后，就报了JNI的错误，不修改是没问题的

> Exception in thread "main" java.lang.IllegalStateException: Illegal JNI version: 0xffffffff
>
>  at com.github.unidbg.linux.android.dvm.BaseVM.checkVersion(BaseVM.java:212)
>
>  at com.github.unidbg.linux.android.dvm.DalvikModule.callJNI_OnLoad(DalvikModule.java:39)
>
>  at AntiOllvmTest.callJniOnload(AntiOllvmTest.java:367)
>
>  at AntiOllvmTest.main(AntiOllvmTest.java:372)
>
>

上传的附件：
- libtprt.so

（1.48MB，303次下载）

## 回复 by 乐子人 (#11)

*2023-5-6 14:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  New对象处](https://bbs.kanxue.com/user-807696.htm)
>
>  大佬，我第一次patch后按照大佬的思路，让0x62138 w8的寄存器改为0x1让其执行到loc_62158，拿第一次patch后的so去重新跑一次代码修改w8寄存器值后，就报了JNI的错误，不修改 ...
>
>

因为改了分支之后，他原本的Jni_OnLoad函数就是会返回-1。但是unidbg源码里面如果jni_onload返回-1，就抛异常。这个可以修改Base.java第212行那里，在jni_onload返回-1的时候，让他打一条log而不是抛异常

## 回复 by Circ1e (#12)

*2023-5-11 14:24*

大佬，可以帮忙看看样本里0x68324偏移的函数吗，用同样的方法会有大概十几个间接跳转没有修复，我通过改NZCV寄存器强行走一些分支有的能成功，但有的会造成死循环。希望大佬可以指点一下。样本应该和你的是同一个。

## 回复 by 乐子人 (#13)

*2023-5-11 14:39*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Circ1e](https://bbs.kanxue.com/user-905978.htm)
>
>  大佬，可以帮忙看看样本里0x68324偏移的函数吗，用同样的方法会有大概十几个间接跳转没有修复，我通过改NZCV寄存器强行走一些分支有的能成功，但有的会造成死循环。希望大佬可以指点一下。样本应该和你的 ...
>
>

死循环这个问题可以这样做：设置一个强行patch标志位，当经过你修改分支的br x9的时候，标志位设置为true。然后下一次processbr的时候，检查标志位是否为true，如果是的话就立刻执行patch。这样就可以了。死循环在patch后强制结束就行

## 回复 by Circ1e (#14)

*2023-5-11 15:04*

好的，谢谢大佬

## 回复 by program杨 (#15)

*2023-5-26 08:47*

请问可以用这个方法 在pc上模拟x86 去除混淆么

## 回复 by 秋狝 (#16)

*2023-5-26 09:17*

感谢分享

## 回复 by 乐子人 (#17)

*2023-5-27 17:14*

>
> [program杨](https://bbs.kanxue.com/user-770991.htm)
>
>  请问可以用这个方法 在pc上模拟x86 去除混淆么
>
>

可以

## 回复 by qdesy (#18)

*2023-5-28 18:27*

大佬好，请问可否提供您分析的这个样例文件，代码里面的硬编码地址不是很会计算![image](https://bbs.kanxue.com/view/img/face/2.gif)

## 回复 by qdesy (#19)

*2023-5-28 22:25*

请问reorderblock()函数中最后的这段代码里，toend和0x5E674L都是怎么得到的。toend被硬编码成private static final long toend = 0x5E6BC; 请问这两个值是怎么设置的？
        PatchIns pie = new PatchIns();
        pie.setAddr(toend);
        pie.setIns("b 0x" + Integer.toHexString((int) (getIndexAddr(0x83a9af56L) - toend)));
        patchs.add(pie);
        PatchIns pie1 = new PatchIns();
        pie1.setAddr(0x5E674L);
        pie1.setIns("b 0x"+Integer.toHexString((int) (getIndexAddr(0x83a9af56L) - 0x5E674L)));
        patchs.add(pie1);

## 回复 by 乐子人 (#20)

*2023-5-28 23:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  qdesy](https://bbs.kanxue.com/user-622255.htm)
>
>  请问reorderblock()函数中最后的这段代码里，toend和0x5E674L都是怎么得到的。toend被硬编码成private static final long toend = 0x5E6B ...
>
>

这个toend其实写的不太好，sorry～。我现在改做法了，就是在结尾跳转是直接回主分发器的时候，获取x8寄存器的值。然后获取x8对应的真实块。再把结尾处直接往主分发器的跳转改成跳转到下一个真实块。

## 回复 by 乐子人 (#21)

*2023-5-28 23:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  qdesy](https://bbs.kanxue.com/user-622255.htm)
>
>  请问reorderblock()函数中最后的这段代码里，toend和0x5E674L都是怎么得到的。toend被硬编码成private static final long toend = 0x5E6B ...
>
>

关于这个toend怎么获取的。toend是包含ret的块的开始地址。我肉眼找的。。

## 回复 by 乐子人 (#22)

*2023-5-28 23:48*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  qdesy](https://bbs.kanxue.com/user-622255.htm)
>
>  请问reorderblock()函数中最后的这段代码里，toend和0x5E674L都是怎么得到的。toend被硬编码成private static final long toend = 0x5E6B ...
>
>

然后第二个值是第一个真实块的开始地址。把主分发器那里的第一个间接跳转改为直接跳转到第一个真实块。

## 回复 by 如斯咩咩咩 (#23)

*2023-5-29 09:25*

mark

## 回复 by coneco (#24)

*2023-5-29 15:22*

赞，感谢分享！

## 回复 by natpacket (#25)

*2023-5-30 17:10*

写的真好

## 回复 by yinX (#26)

*2023-6-1 19:51*

我发现可以不需要显式地load libc.so、libm.so等文件，\unidbg\unidbg-android\src\main\resources\android\ 这个地方自带了sdk19和sdk23，只要把AndroidResolver设为23，它就会自动加载所需的系统so

## 回复 by Ruinv6 (#27)

*2023-6-13 16:51*

大佬，有联系方式可以留个吗 请教下问题

## 回复 by alds (#28)

*2023-6-13 23:13*

大佬，有没有研究过java平坦流混淆去除？

## 回复 by 乐子人 (#29)

*2023-6-14 14:41*

>
> [alds](https://bbs.kanxue.com/user-549013.htm)
>
>  大佬，有没有研究过java平坦流混淆去除？
>
>

没有

## 回复 by zhonghuayi (#30)

*2023-6-28 09:53*

写的很好，大佬能多详细的分享一些基础的内容吗？让新人学习学习。

## 回复 by mb_jippoctc (#31)

*2023-7-4 11:30*

大牛，请问一下学习路线是怎样的

## 回复 by mb_kbkqyusp (#32)

*2023-7-8 11:48*

大佬这个AntiOllvm.java 下载过期了，可以在分享一次吗![image](https://bbs.kanxue.com/view/img/face/51.gif)

## 回复 by 橙子的肚子 (#33)

*2023-7-10 10:57*

感谢分享

## 回复 by @=llfly (#34)

*2023-7-25 10:42*

赞，感谢分享！

## 回复 by bluth (#35)

*2023-8-11 01:21*

![image](https://bbs.kanxue.com/upload/attach/202308/560009_JHFP9H7H7RJAMX4.jpg)

请教一下大佬，第一次跑完BR X9，之后，这些分支没有执行到，根据提示修改寄存器w8的值跳转

这里的这个跳转实际测试来看，好像没有跳转到，不知道是不是版本不一样的原因

是否有其他思路这里让没有执行到的分支执行一下

## 回复 by New对象处 (#36)

*2023-8-17 20:07*

>
> [bluth](https://bbs.kanxue.com/user-560009.htm)
>
>  请教一下大佬，第一次跑完BR X9，之后，这些分支没有执行到，根据提示修改寄存器w8的值跳转这里的这个跳转实际测试来看，好像没有跳转到，不知道是不是版本不一样的原因是否有其他思路这里让没有执行到的分支 ...
>
>

你将62144 的w8改为0，会执行62158

## 回复 by New对象处 (#37)

*2023-8-17 20:10*

>
> [bluth](https://bbs.kanxue.com/user-560009.htm)
>
>  请教一下大佬，第一次跑完BR X9，之后，这些分支没有执行到，根据提示修改寄存器w8的值跳转这里的这个跳转实际测试来看，好像没有跳转到，不知道是不是版本不一样的原因是否有其他思路这里让没有执行到的分支 ...
>
>

按照我说的，加入造成死循环，那么就按照楼主说的，标志当前位置，下次调用procBr时就patch，退出

## 回复 by wx_justght (#38)

*2023-11-16 19:20*

大佬，像getRegValue,readInt64是哪个库的![image](https://bbs.kanxue.com/view/img/face/85.gif)

## 回复 by wx_justght (#39)

*2023-11-17 14:44*

大佬，String condBr = "b"+cond.toLowerCase(Locale.ROOT) + " 0x"+ Integer.toHexString((int) (offset1 - addinstaddr)); 这个地方为什么还需要 减去 addinstaddr

## 回复 by 乐子人 (#40)

*2023-11-18 03:25*

>
> [wx_justght](https://bbs.kanxue.com/user-929554.htm)
>
>  大佬，像getRegValue,readInt64是哪个库的[em_85]
>
>

我自己写的hh

## 回复 by 万里星河 (#41)

*2023-11-18 18:48*

支持一下 不过使用frida stalker效果也不错

## 回复 by yxbbing (#42)

*2023-12-23 09:11*

memory.setLibraryResolver(new AndroidResolver(26)); 26版本这么来的有吗? unidbg原码里只有19,23

## 回复 by lemontree@me (#43)

*2024-1-17 18:15*

想问下代码里面的libtprt5.so和libtprt6.so是怎么来的，原apk里面就是这样的名字吗

## 回复 by 肉蚌葱鸡 (#44)

*2024-1-23 09:48*

写的真好 高级帖

## 回复 by 蜡笔晓辉 (#45)

*2024-2-21 12:48*

厉害了

## 回复 by mb_nprzkbju (#46)

*2024-2-25 11:59*

你好，冒昧问一句，这个地方你是不是写错了。
文章第一张截图可知W11=0x6E221A17，W12=0x6E142EC8
文章说用unidbg修改0x5E5AC处W8的值为1

![image](https://bbs.kanxue.com/upload/attach/202402/994980_S5BNS6B6SQANYG4.webp)

 可是
如果上面一条指令w8等于0,那么W8=W11>W12,下面会执行B loc_5E678
如果W8不等于0,那么W8=W12,依然会执行B loc_5E678，

b.lt是小于才会跳转,无论W8等于W11还是W12始终无法是进入B.LT loc_5E5CC，
你是怎么进入loc_5E5CC分支的。

另外感觉你这里面,好多值都是肉眼观察然后硬编码上去的，
你是不是看了程序运行流程，然后肉眼剔除掉多的部分，然后实现的还原，
那这样好像没多少意义了，想问一下目前有没有通用一点的办法。

## 回复 by mb_cmrpibxs (#47)

*2024-3-18 14:09*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  qdesy](https://bbs.kanxue.com/user-622255.htm)
>
>  请问reorderblock()函数中最后的这段代码里，toend和0x5E674L都是怎么得到的。toend被硬编码成private static final long toend = 0x5E6B ...
>
>

兄弟，能大家一起探讨下吗

## 回复 by mb_cmrpibxs (#48)

*2024-3-19 16:27*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  New对象处](https://bbs.kanxue.com/user-807696.htm)
>
>  666
>
>

大哥，能请教下相关问题吗

## 回复 by mb_cmrpibxs (#49)

*2024-3-19 16:29*

>
> [秋狝](https://bbs.kanxue.com/user-825507.htm)
>
>  感谢分享
>
>

大哥，能请教下问题吗

## 回复 by heyonly (#50)

*2024-4-17 11:54*

感谢大佬的分享，在还原平坦化的时候，代码中的tbs.add(new TrueBlock(0x6e142ec8L,0x5E6B0)); 这个 0x5E6B0，不知道怎么来的，要是上传在分析时的样本就好了，这样我们便能分析 猜这些值怎么来的，或者大佬在文中解释下。感谢

## 回复 by 教教我吧~ (#51)

*2024-6-20 16:04*

太棒了，非常感谢分享！![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 教教我吧~ (#52)

*2024-6-20 16:27*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  qdesy](https://bbs.kanxue.com/user-622255.htm)
>
>  请问reorderblock()函数中最后的这段代码里，toend和0x5E674L都是怎么得到的。toend被硬编码成private static final long toend = 0x5E6B ...
>
>

# 2.获取索引值顺序中的第一个值，找到对应的真实块。将主分发器处patch为跳转向第一个真实块的跳转指令。

![image](https://bbs.kanxue.com/upload/attach/202406/940077_7JMKCVWZ4B8RDKE.webp)

# 3.根据真实块结束时的新的索引值，寻找到对应的真实块，将结尾处patch为跳转到下一个真实块

【这里应该有两个真实块：True真实块、False真实块, 所以通过控制前面的

![image](https://bbs.kanxue.com/upload/attach/202406/940077_6N2WGENBTFS64YW.webp)

来控制分支走向。

假设认为W8 == 1 是走的【False真实块】分支

![image](https://bbs.kanxue.com/upload/attach/202406/940077_W4KF66WJ6BSXBKZ.webp)

 当修改程序走向来说时（更改W8的值为1），带有ret的最后一个真实块的起始地址为0x5E77C，其前一个真实块地址是0x5E6BC

![image](https://bbs.kanxue.com/upload/attach/202406/940077_K862T89DUWV5STT.webp)

那么需要将结尾处patch为跳转到下一个真实块

![image](https://bbs.kanxue.com/upload/attach/202406/940077_8TQV9XDTT2MKUEJ.webp)

即直接跳转到带有ret的真实块（不经过主分发器了）

![image](https://bbs.kanxue.com/upload/attach/202406/940077_22J396YC367V5HW.webp)

——————————————————————

同理W8 == 0的【真实块分支】，也是如此。

![image](https://bbs.kanxue.com/upload/attach/202406/940077_X3WH9N4EADJ69P3.webp)

】

## 回复 by 教教我吧~ (#53)

*2024-6-20 16:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  New对象处](https://bbs.kanxue.com/user-807696.htm)
>
>  按照我说的，加入造成死循环，那么就按照楼主说的，标志当前位置，下次调用procBr时就patch，退出
>
>

我是每次搞掉一个BR X9就生成一个so，这样可以防止死循环吧

## 回复 by blue_sky (#54)

*2024-6-22 10:13*

mark，向大佬学习

## 回复 by 养只猫不好么 (#55)

*2024-7-5 14:25*

赞，感谢分享！

## 回复 by 养只猫不好么 (#56)

*2024-7-11 18:03*

感谢分享

## 回复 by dkxzl (#57)

*2024-7-15 16:30*

在执行 vm.loadLibrary(new File("libc.so"),false);   的时候，
Exception in thread "main" java.lang.ArithmeticException: / by zero
        at net.fornwall.jelf.ElfDynamicStructure.<init>(ElfDynamicStructure.java:321)

int num_entries = pltRelSize / relEntrySize; 这行代码relEntrySize为0引发了异常

## 回复 by 乐子人 (#58)

*2024-7-15 21:56*

>
> [dkxzl](https://bbs.kanxue.com/user-258186.htm)
>
>  在执行 vm.loadLibrary(new File("libc.so"),false); 的时候，
> Exception in thread "main" ...
>
>

这个手动把relEntrySize赋值为0x18

## 回复 by mb_dmkmqsyg (#59)

*2024-11-8 11:08*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  heyonly](https://bbs.kanxue.com/user-860080.htm)
>
>  感谢大佬的分享，在还原平坦化的时候，代码中的tbs.add(new TrueBlock(0x6e142ec8L,0x5E6B0)); 这个 0x5E6B0，不知道怎么来的，要是上传在分析时的样本就好了 ...
>
>

大哥，这个值哪来的能教下吗

## 回复 by 呼吸24K纯氧 (#60)

*2025-3-27 20:18*

感谢分享

## 回复 by Aar0n (#61)

*2025-3-31 21:56*

大佬请问有修改后的文件和so案例学习一下吗

## 回复 by mb_tblcnbam (#62)

*2025-4-24 16:47*

加载so提示这个要怎么搞呢，Exception in thread "main" java.lang.ArithmeticException: / by zero
        at net.fornwall.jelf.ElfDynamicStructure.<init>(ElfDynamicStructure.java:321)
        at net.fornwall.jelf.ElfSegment$3.computeValue(ElfSegment.java:153)
        at net.fornwall.jelf.ElfSegment$3.computeValue(ElfSegment.java:150)
        at net.fornwall.jelf.MemoizedObject.getValue(MemoizedObject.java:21)
        at net.fornwall.jelf.ElfSegment.getDynamicStructure(ElfSegment.java:255)
        at com.github.unidbg.linux.AndroidElfLoader.loadInternal(AndroidElfLoader.java:434)
        at com.github.unidbg.linux.AndroidElfLoader.loadInternal(AndroidElfLoader.java:477)
        at com.github.unidbg.linux.AndroidElfLoader.loadInternal(AndroidElfLoader.java:175)
        at com.github.unidbg.linux.AndroidElfLoader.loadInternal(AndroidElfLoader.java:63)
        at com.github.unidbg.spi.AbstractLoader.load(AbstractLoader.java:237)
        at com.github.unidbg.linux.android.dvm.BaseVM.loadLibrary(BaseVM.java:333)
        at com.test.test2.AntiOllvm.<init>(AntiOllvm.java:71)
        at com.test.test2.AntiOllvm.main(AntiOllvm.java:112)

## 回复 by mb_ncfbmciq (#63)

*2025-6-20 09:18*

牛逼666

## 回复 by lemontree@me (#64)

*2025-11-17 23:52*

大佬请问下直接拿代码来跑libtprt.so文件加载系统库那里就异常了，去掉的话就跑到jni_onlad函数的时候返回非法版本-1，这个主要是什么原因呀，希望可以解答下疑惑

## 回复 by 土豆爱学习 (#65)

*2026-3-18 11:25*

666

## 回复 by 伊苏尔德 (#66)

*2026-5-2 18:11*

哥，可以給原so文件嗎？我太笨了我从网上找的复现不出来...

## 回复 by flyocean (#67)

*2026-5-23 21:05*

mark,学到了
