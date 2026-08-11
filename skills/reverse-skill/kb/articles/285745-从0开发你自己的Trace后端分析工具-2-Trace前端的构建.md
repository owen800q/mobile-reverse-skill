---
title: '[原创]从0开发你自己的Trace后端分析工具: (2) Trace前端的构建'
url: https://bbs.kanxue.com/thread-285745.htm
tid: 285745
author: FANGG3
date: '2025-02-25'
tags: [Android安全, 原创, NDK分析, 逆向分析, 基础理论, HOOK注入, 源码框架]
crawled_at: '2026-08-11T15:29:19+00:00'
replies: 11
---

# 从0开发你自己的Trace后端分析工具: (2) Trace前端的构建

Hello, 我是FANGG3. 这个系列鸽了一年多了, 这一年中发生了很多工作的变动, 也遇到了很多帮助我的人.谢谢哇! 我的朋友们.

哈哈, 作为年更(bushi)系列的第二篇, 并没有写很多深入的内容,更像是一个科普文, 如果有用词或逻辑错误, 欢迎大家斧正 ~

**相关链接:**

- 概述: [从0开发你自己的Trace后端分析工具: (1) 概述](https://bbs.kanxue.com/thread-281555.htm)
- Trace前端的构建: 从0开发你自己的Trace后端分析工具: (2) Trace前端的构建

在阅读本文时, 我们先明确几个概念:

- Record : Trace记录. 包含分析所需要的运行时信息
- Tracer : 前端采集器, 注入至目标进程并记录Record
- Backend : 后端分析器

## 一、Tracer的基本功能

当我们进行Trace分析时, 我们往往有以下常规需求:

- 汇编指令
- 寄存器信息
- 内存读写信息
- 符号信息

根据需求, 我在ATTD中制定了Record的相关格式,使用指令执行后作为记录点,以便Backend进行分析, 如下为一个例子:

`X8=0xa7baccc8585dee7d,PC=0x759d98cc9c,mr=768aea3048:12086197710850223741:8,inst=759d98cc98:081540f9:Java_com_f_testcase_testCase_stringFromJNI+16`

同时, 可以将maps信息保存下来.作为拓展,将当前指令地址与So对应起来.

## 二、Tracer的原理

在已有的Tracer实现中, 主要有两大类, 指令模拟器(Simulator)和动态插桩(Binary Dynamic Instrument).

### 1. 指令模拟器

指令模拟器, 也可以称作CPU模拟器、二进制翻译. 主要是将目标平台的机器码抽象成平台无关的中间语言IR的形式, 再过虚拟机(VM) 模拟执行IR, 从而达到跨平台运行的功能. 相对应的开源项目有[unicorn](https://github.com/unicorn-engine/unicorn)(qemu)、[dynamic](https://github.com/FANGG3/dynarmic)以及[vixl](https://github.com/Linaro/vixl).

这些开源项目中, 都有各自独特的中间语言IL(IR), 并且描述寄存器读写、内存读写信息.

![Clipboard_Screenshot_1740454933](https://bbs.kanxue.com/upload/attach/202502/855439_SAZXSF6UB87GHAN.png)

当我们需要实现Trace功能时, 可以通过循环读取PC地址对应的机器码, 再将每一种指令翻译成IR, 编写相对应的handler函数处理IR的执行, 直到函数返回.

我们对VM具有完整的操纵权, 还可以通过IR分析出内存访问信息,对于非自修改代码的样本还可以通过缓冲IL的形式加快Trace的效率.

但是指令模拟器方案实际上还存在很多问题:

1. 原子指令模拟: (cas,ldxr...) 原子指令是为了在多CPU中, 保障调度正常的特殊指令. 往往与内存屏障相关, 模拟这些指令时, VM很难实现像CPU一样将保证时序性和一致性. (这部分有兴趣的小伙伴可以查询内存屏障、原子性等相关资料)
2. 浮点寄存器模拟 : 在目标平台运行VM时, 模拟浮点操作的效率太慢
3. 特权指令模拟 : (这部分与内核模式相关, 实际模拟过程中几乎遇不到)

### 2. 动态插桩

二进制动态插桩, 相信大家对于这个概念并不陌生, Frida、DobbyHook都可以称为二进制动态插桩的代表. 劫持目标函数的控制流, 跳到自己编写的逻辑中去执行,从而获取到寄存器等信息, 简而言之即inlinehook, 要实现Trace功能,应当实现下述流程:

初始化: 替换目标地址指令, 跳转至自己的逻辑中

1. 备份原指令
2. 内联汇编获取寄存器(func_getRegs)
3. 重定位`func_getRegs + 原指令`, 处理地址相关指令
4. 内联汇编获取寄存器, 获取原指令执行结果
5. 根据执行结果, 计算下一条指令的地址
6. 循环执行, 直到函数结束

可以看到, 在此过程中, 需要自己计算内存读写信息, 并且在处理指令执行时, 将实际的执行权交由CPU去处理.

![image-20250225155433209](https://bbs.kanxue.com/upload/attach/202502/855439_R47UGQQ2MBPD8UV.png)

## 三、简单实现Trace前端的思路

综上两种Trace的实现, 我们可以选取 动态插桩 结合 IR 的形式, 去实现Tracer. 对于可以使用IR解释的指令, 使用VM执行, 其他指令使用插桩的形式执行.将指令提升为IR后可以得到内存读写信息, 即完成我们的需求了.

### 1. 寄存器信息

通常trace是针对函数粒度的, 通过inlinehook可以获取到函数进入时的寄存器信息, 也可以使用ptrace等方式获取, 同时修改控制流跳入我们的逻辑中.

但是要注意的是, 为了防止重入, 当执行到我们自己的逻辑时,应该第一时间将inlinehook取消(unhook).

### 2. 汇编指令和符号信息

其中, 我们只需要寄存器信息就可以简单地分析出汇编指令码和符号信息. 通过`PC`寄存器获取当前指令地址, 以ARM64为例, 取出4个字节即可. 通过`dladdr`获取各个寄存器对应的符号信息.

### 3. 内存读写信息

使用已有的库 vixl、RzIL或者Dynamic, 将机器码解析为IR, 使用实际的寄存器值,计算出对应内存地址以及读写值.

下面代码是使用RzIL计算内存读写信息的示例代码:

| 12345678910111213141516171819202122232425262728293031323334353637383940414243 | `int` `toOp(RzAnalysisOp *op, ut64 addr, uint32_t v) {``return` `plugin->op(rzAnalysis, op, addr, (``char` `*)&v, 4, RZ_ANALYSIS_OP_MASK_DISASM \| RZ_ANALYSIS_OP_MASK_IL);``}` `void` `print_vm_event(RzILVM *vm) {``void` `**it;` `RzStrBuf *t = rz_strbuf_new(``""``);``rz_pvector_foreach (vm->events, it) {``RzILEvent *evt = *it;``// 根据evt.type 获取下述事件``// RZ_IL_EVENT_EXCEPTION,``// RZ_IL_EVENT_PC_WRITE,``// RZ_IL_EVENT_MEM_READ,``// RZ_IL_EVENT_VAR_READ,``// RZ_IL_EVENT_MEM_WRITE,``// RZ_IL_EVENT_VAR_WRITE,``rz_il_event_stringify(evt, t);``rz_strbuf_append(t,` `"\n"``);``printf``(``"%s \n"``, rz_strbuf_get(t));``}``}` `void` `liftToIR(ut64 pc){``RzAnalysisPlugin *plugin;``RzAnalysis *rzAnalysis;``RzILVM *vm = rz_il_vm_new(pc, 64,` `false``);``init_vm_regs(vm);` `// 同步VM寄存器和实际寄存器``rzAnalysis = rz_analysis_new();``plugin = rz_arch_get_analysis_plugin(4);``// arm64 plugin``rzAnalysis->bits = 64;``rzAnalysis->big_endian =` `false``;``rzAnalysis->cpu =` `"aarch64-v8a"``;``printf``(``"%s\n"``, plugin->desc);``void` `*ctx;``plugin->init(&ctx);``rzAnalysis->plugin_data = ctx;``RzAnalysisOp op = { 0 };``int` `ret = toOp(&op, pc, *(ut64 *)pc);``printf``(``" %d %s\n"``,ret,op.mnemonic);``rz_il_vm_step(vm, op.il_op, pc + op.size);``print_vm_event(vm);``}` |
|-|-|

我使用了Dobby结合QBDI实现了一个简单的Demo,但是并不适合在实际场景中使用. 有助于大家的理解Tracer的大概过程[FANGG3/DobbyWithQBDI](https://github.com/FANGG3/DobbyWithQBDI)

### 拓展Unidbg

使用Unidbg 输出ATTD的Record格式, 作为使用Unidbg 的一个简单的插件(虽然速度很慢, 但是也不是不能用)

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266 | `package` `MyTool;`  `import` `com.github.unidbg.Emulator;``import` `com.github.unidbg.Module;``import` `com.github.unidbg.Symbol;``import` `com.github.unidbg.arm.backend.*;``import` `org.apache.commons.codec.binary.Hex;``import` `unicorn.Arm64Const;` `import` `java.io.FileNotFoundException;``import` `java.io.FileOutputStream;``import` `java.io.IOException;``import` `java.nio.ByteOrder;``import` `java.util.HashMap;``import` `java.util.Map;` `/**``* @author: FANGG3``* @date: 2022/10/24 14:20``* @desc:``*/``public` `class` `AttdTracer {``Emulator emulator;``String out_path;``FileOutputStream log_stream;``long` `base;``long` `end;``long` `init_sp;``static` `int` `memIndex =` `0``;``boolean` `isLog =` `false``;``Module module;``boolean` `isStart =` `false``;``String pre_instr;``String mem_record;``long` `pos =` `0``;``StringBuilder record =` `new` `StringBuilder();``private` `Map<Integer, String> REGS =` `new` `HashMap<Integer, String>() {{``put(Arm64Const.UC_ARM64_REG_X0,` `"X0"``);``put(Arm64Const.UC_ARM64_REG_X1,` `"X1"``);``put(Arm64Const.UC_ARM64_REG_X2,` `"X2"``);``put(Arm64Const.UC_ARM64_REG_X3,` `"X3"``);``put(Arm64Const.UC_ARM64_REG_X4,` `"X4"``);``put(Arm64Const.UC_ARM64_REG_X5,` `"X5"``);``put(Arm64Const.UC_ARM64_REG_X6,` `"X6"``);``put(Arm64Const.UC_ARM64_REG_X7,` `"X7"``);``put(Arm64Const.UC_ARM64_REG_X8,` `"X8"``);``put(Arm64Const.UC_ARM64_REG_X9,` `"X9"``);``put(Arm64Const.UC_ARM64_REG_X10,` `"X10"``);``put(Arm64Const.UC_ARM64_REG_X11,` `"X11"``);``put(Arm64Const.UC_ARM64_REG_X12,` `"X12"``);``put(Arm64Const.UC_ARM64_REG_X13,` `"X13"``);``put(Arm64Const.UC_ARM64_REG_X14,` `"X14"``);``put(Arm64Const.UC_ARM64_REG_X15,` `"X15"``);``put(Arm64Const.UC_ARM64_REG_X16,` `"X16"``);``put(Arm64Const.UC_ARM64_REG_X17,` `"X17"``);``put(Arm64Const.UC_ARM64_REG_X18,` `"X18"``);``put(Arm64Const.UC_ARM64_REG_X19,` `"X19"``);``put(Arm64Const.UC_ARM64_REG_X20,` `"X20"``);``put(Arm64Const.UC_ARM64_REG_X21,` `"X21"``);``put(Arm64Const.UC_ARM64_REG_X22,` `"X22"``);``put(Arm64Const.UC_ARM64_REG_X23,` `"X23"``);``put(Arm64Const.UC_ARM64_REG_X24,` `"X24"``);``put(Arm64Const.UC_ARM64_REG_X25,` `"X25"``);``put(Arm64Const.UC_ARM64_REG_X26,` `"X26"``);``put(Arm64Const.UC_ARM64_REG_X27,` `"X27"``);``put(Arm64Const.UC_ARM64_REG_X28,` `"X28"``);``put(Arm64Const.UC_ARM64_REG_LR,` `"X29"``);``put(Arm64Const.UC_ARM64_REG_FP,` `"X30"``);``put(Arm64Const.UC_ARM64_REG_PC,` `"PC"``);``put(Arm64Const.UC_ARM64_REG_NZCV,` `"NZCV"``);``}};`  `public` `AttdTracer(Emulator emulator, Module module, String out_path,` `boolean` `isLog) {``this``.emulator = emulator;``this``.out_path = out_path;``this``.isLog = isLog;``this``.module = module;``try` `{``this``.log_stream =` `new` `FileOutputStream(``this``.out_path);``}` `catch` `(FileNotFoundException e) {``throw` `new` `RuntimeException(e);``}``init_sp = emulator.getContext().getStackPointer().peer;` `if` `(module ==` `null``) {``base =` `0``;``end = -``1``;``return``;``}``base = module.base;``end = base + module.size;``}` `public` `String getSymbolByAddr(``long` `addr) {` `try` `{``Symbol symbol = emulator.getMemory().findModuleByAddress(addr).findClosestSymbolByAddress(addr,` `false``);``long` `offset = addr - symbol.getAddress();``if` `(offset >=` `0x1000``)` `return` `null``;``return` `String.format(``"%s+%x"``, symbol, offset);``}` `catch` `(Exception e) {``//ignore``return` `null``;``}``}` `public` `String getRegs(Backend backend) {``StringBuilder ret =` `new` `StringBuilder();` `REGS.forEach((id, s) -> {``long` `v = backend.reg_read(id).longValue();``String symbol = getSymbolByAddr(v);``if` `(symbol ==` `null``) {``ret.append(String.format(``"%s=%x,"``,s, v));``}` `else` `{``ret.append(String.format(``"%s=%x:%s,"``, s,v, symbol));``}``});``return` `ret.toString();``}` `private` `void` `writeTrace(String data){``try` `{``if` `(``this``.isLog){``System.out.println(data);``}``this``.log_stream.write(data.getBytes());``this``.log_stream.write(``'\n'``);``}` `catch` `(IOException e) {``throw` `new` `RuntimeException(e);``}``}``public` `void` `trace() {` `// here is pre hook``emulator.getBackend().hook_add_new(``new` `CodeHook() {``@Override``public` `void` `hook(Backend backend,` `long` `address,` `int` `size, Object user) {``String instrValue = Hex.encodeHexString(backend.mem_read(address,` `4``));``//                Instruction instr = emulator.disassemble(address, 4, 1)[0];``if` `(!isStart) {``//                    pre_instr = String.format("%s instr=%x:%s,", instr.toString(), address, instrValue);``String symbolByAddr = getSymbolByAddr(address);``if` `(symbolByAddr !=` `null``) {``pre_instr = String.format(``"inst=%x:%s:%s,"``,  address, instrValue, symbolByAddr);``}``else` `{``pre_instr = String.format(``"inst=%x:%s,"``,  address, instrValue);``}``isStart =` `true``;``return``;``}``String now_reg = getRegs(backend);` `record.append(pre_instr)``.append(now_reg)``.append(mem_record);` `writeTrace(record.toString());``record =` `new` `StringBuilder();``pos +=` `1``;``mem_record =` `""``;``pre_instr = String.format(``"inst=%x:%s,"``,  address, instrValue);``}` `@Override``public` `void` `onAttach(UnHook unHook) {``}``@Override``public` `void` `detach() {` `}``},` `0``, -``1``,` `null``);` `emulator.getBackend().hook_add_new(``new` `ReadHook() {``@Override``public` `void` `hook(Backend backend,` `long` `address,` `int` `size, Object user) {``Class c;``byte``[] bytes = backend.mem_read(address, size);``String v;``switch` `(size) {``case` `1``:``c = Byte.``class``;``v = String.valueOf(bytes[``0``] &` `0xFF``);``break``;``case` `2``:``c = Short.``class``;``Number number = bytesToNumber(bytes, c, ByteOrder.LITTLE_ENDIAN);``v = String.valueOf(Short.toUnsignedInt(number.shortValue()));``break``;``case` `4``:``c = Integer.``class``;``int` `i = bytesToNumber(bytes, c, ByteOrder.LITTLE_ENDIAN).intValue();``v = Integer.toUnsignedString(i);` `break``;``case` `8``:``c = Long.``class``;``long` `L = bytesToNumber(bytes, c, ByteOrder.LITTLE_ENDIAN).longValue();``v = Long.toUnsignedString(L);` `break``;``default``:``throw` `new` `IllegalStateException(``"convert mem bytes, size="` `+ size);``}``mem_record += String.format(``"mr=%x:%s:%d,"``, address, v, size);``}``@Override``public` `void` `onAttach(UnHook unHook) {}``@Override``public` `void` `detach() {}``},` `0``, -``1``,` `null``);` `emulator.getBackend().hook_add_new(``new` `WriteHook() {``@Override``public` `void` `hook(Backend backend,` `long` `address,` `int` `size,` `long` `value, Object user) {``mem_record += String.format(``"mw=%x:%s:%d,"``, address, Long.toUnsignedString(value), size);``}` `@Override``public` `void` `onAttach(UnHook unHook) {}``@Override``public` `void` `detach() {}``},` `0``, -``1``,` `null``);``}``public` `static` `short` `bytesToShort(``byte``[] bytes,` `int` `start, ByteOrder byteOrder) {``return` `ByteOrder.LITTLE_ENDIAN == byteOrder ? (``short``)(bytes[start] &` `255` `\| (bytes[start +` `1``] &` `255``) <<` `8``) : (``short``)(bytes[start +` `1``] &` `255` `\| (bytes[start] &` `255``) <<` `8``);``}``public` `static` `int` `bytesToInt(``byte``[] bytes,` `int` `start, ByteOrder byteOrder) {``return` `ByteOrder.LITTLE_ENDIAN == byteOrder ? bytes[start] &` `255` `\| (bytes[``1` `+ start] &` `255``) <<` `8` `\| (bytes[``2` `+ start] &` `255``) <<` `16` `\| (bytes[``3` `+ start] &` `255``) <<` `24` `: bytes[``3` `+ start] &` `255` `\| (bytes[``2` `+ start] &` `255``) <<` `8` `\| (bytes[``1` `+ start] &` `255``) <<` `16` `\| (bytes[start] &` `255``) <<` `24``;``}``public` `static` `long` `bytesToLong(``byte``[] bytes,` `int` `start, ByteOrder byteOrder) {``long` `values = 0L;``int` `i;``if` `(ByteOrder.LITTLE_ENDIAN == byteOrder) {``for``(i =` `7``; i >=` `0``; --i) {``values <<=` `8``;``values \|= (``long``)(bytes[i + start] &` `255``);``}``}` `else` `{``for``(i =` `0``; i <` `8``; ++i) {``values <<=` `8``;``values \|= (``long``)(bytes[i + start] &` `255``);``}``}``return` `values;``}``public` `static` `<T` `extends` `Number> T bytesToNumber(``byte``[] bytes, Class<T> targetClass, ByteOrder byteOrder)` `throws` `IllegalArgumentException {``Object number =` `null``;``if` `(Byte.``class` `== targetClass) {``number = bytes[``0``];``}` `else` `if` `(Short.``class` `== targetClass) {``number = bytesToShort(bytes,``0``, byteOrder);``}` `else` `if` `(Integer.``class` `== targetClass) {``number = bytesToInt(bytes,` `0``,byteOrder);``}` `else` `if` `(Long.``class` `== targetClass) {``number = bytesToLong(bytes,` `0``,byteOrder);``}` `else` `{``if` `(Number.``class` `!= targetClass) {``throw` `new` `IllegalArgumentException(``"Unsupported Number type: "` `+ targetClass.getName());``}``}``return` `(T) number;``}``}` |
|-|-|

## 其他

有小伙伴想要一起玩Arm64 Trace分析,反混淆的, 可以加入这个群聊一起讨论讨论~

![image-20250225154826614](https://bbs.kanxue.com/upload/attach/202502/855439_JXKZ6DXN9CJSMHW.png)

---

# 回复

## 回复 by wx_插曲 (#2)

*2025-2-25 15:58*

11

## 回复 by mb_ldbucrik (#3)

*2025-2-25 16:13*

感谢分享，向大佬学习

## 回复 by R0g (#4)

*2025-2-26 13:21*

mark

## 回复 by 墨穹呢 (#5)

*2025-2-26 13:42*

attd太强了 手撕vmp 脚踢ollvm

## 回复 by 逆向小玖 (#6)

*2025-2-26 18:54*

群满了欸

## 回复 by 简单的简单 (#7)

*2025-2-27 16:07*

群满了欸

## 回复 by 快乐的小跳蛙 (#8)

*2025-2-27 16:32*

群满了欸

## 回复 by Ankeys (#9)

*2025-3-4 21:07*

群满了欸

## 回复 by wx_phoronesis (#10)

*2025-3-20 10:05*

群满了,vx报一下

## 回复 by Qira (#11)

*2025-5-1 22:42*

最早接触ttd 还是ctf 里， geohot 使用的qira， 后来也尝试过基于qira 做一些trace的定制

## 回复 by mb_wjytplsl (#12)

*2025-6-13 20:47*

群满了欸
