---
title: '[原创] unicorn-BinaryNinja 去除csel-br 间接跳转混淆'
url: https://bbs.kanxue.com/thread-287568.htm
tid: 287568
author: SGSGsama
date: '2025-07-10'
tags: [Android安全, 原创, 工具脚本]
crawled_at: '2026-07-31T14:07:42+08:00'
replies: 7
---

本文使用腾讯游戏安全大赛2023安卓初赛中的libsec2023.so作为样本
已知bug：
追溯时遇到循环会卡死
还未实现指令前移

### 什么是间接跳转

间接跳转指的是在程序原本正常的控制流中，将部分跳转指令的参数由常量改为寄存器值，并通过查表/实时计算地址的形式将原本的静态的地址隐藏起来，从而达到阻止反编译器分析的效果，目前主流的反编译器如ida，BinaryNinja对间接跳转的分析效果均不佳
一则间接跳转的例子如下
![image](https://bbs.kanxue.com/upload/attach/202507/1017025_SQNHX46DHHGFAMW.webp)
可以看到先对w0和0进行比较更新condition flag的值，然后初始化w8,w9两个寄存器值作为跳转的两种不同方向，在根据情况赋值x8的同时加载跳转表(0x72000+0xc20),然后把x8作为跳转表中的偏移获取对应的地址，注意此时的地址仍不是正确的，再最后执行一次add后才获得了正确的地址

### 如果我不会写自动化去除脚本该怎么办

如果你主要使用ida，那么恭喜你这个样本你可以扔回收站了，ida作为一款纯静态分析工具完全无法实时计算地址
对于BianryNinja，有两种方法可以凑合让反编译器恢复控制流，一是把data段的权限设置为只读，因为基于保守分析的原则如果data段可写的话反编译器完全不会去计算跳转地址（因为无法确认静态状态下的跳转表数据是否可信），当data段只读后对于一些计算相对简单的跳转翻译器会尝试去计算其目标，但是效果仍不佳，对于cset/csel这类带分支的间接跳转尤其

| 123456 | `CSET``/``CSEL是arm汇编中的两种条件赋值指令``CSEL的格式为  CESL dest source1 source2 cond``cond为条件标识，就是ge le eq之类的``当条件满足时dest会由source1赋值，否则由source2赋值``CSET的格式为  CSET dest cond``如果条件满足则dest被置``1``，否则置``0` |
|-|-|

这是一处修改data段权限的例子
 ![image](https://bbs.kanxue.com/upload/attach/202507/1017025_A6VSMC75WE49QUY.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202507/1017025_5G772YNK747E5D5.webp)
可以看到这处还算可以，整个跳转结构被解析成了一个switch

但并非每次都好用

可以看到这里就没有处理出来，注意到计算地址时用到了w8，而网上追溯w8的值由x0所指的地址读取而来，根据arm64调用约定x0是一个函数的第一个参数，所以这是一处跨函数的间接跳转，一些必要参数由函数外传入，反编译器获取不了足够的上下文自然无法计算地址

还有一种方法是自己算出跳转地址后在BinaryNinja的medium IL 或 high IL 视图下给jump里的参数指定user value即告诉反编译器这个参数的值确保为用户指定的值，这样也可以一定程度获得勉强能看的结果，不过这种办法要获取地址，还是有点麻烦的
 ![image](https://bbs.kanxue.com/upload/attach/202507/1017025_3MCJ5H8ZWATPKDK.webp)

### 解决这个问题需要什么

我们最终的目的是获取跳转的地址并把br修改成b #xxxxx 的常量跳转，还是上面的例子
 ![image](https://bbs.kanxue.com/upload/attach/202507/1017025_8N4NUBWBX57Y2TQ.webp)
我们注意到这个结构有一些特点

- 结尾的最后两行add和br指令完全与程序的正常业务无关，patch掉他们完全没影响
- 理论上可以设置一个很远栈变量或者寄存器值（比如上文提到的从函数外传进来的x0），然后在计算地址时用到这个值，即不能确定模拟执行的起点
- 中间可以添加类似frida检测的逻辑将我们导向错误的控制流，而因为我们很难静态分析去对抗检测，所以使用trace获取跳转表再patch未必好用

可以得出几个结论

- 显然这个跳转只有满足cond和不满足两种情况，以eq为例，我们可以把最后两行无用的指令替换成 b.eq xxx 和 b.ne xxx这样一对互补的指令，这样既能覆盖所有跳转情况，也不会因为过早跳转导致错过必要的指令导致程序逻辑错误
- 模拟执行的可以分为两步，第一步是执行到csel之前，这时我们暂停执行并保存所有寄存器值，用于获取csel前的上文信息,然后我们从csel开始执行两次模拟执行，每次执行完后恢复寄存器信息，第一次将dest设为source1，第二次将dest块再执行，极端情况就寻找交叉引用，跳转到调用间接跳转所在的设为source2，用于获取cmp两种情况时不同的地址
- 虽然我们不能确定模拟执行的起点，一次缺少上下文的模拟必然会有两种结果

	- 模拟过程中访问错误地址，直接让模拟执行抛出异常
	- 计算出来的地址歪的离谱，很可能在text段之外 所以我们可以考虑多次尝试模拟执行，如果模拟执行过程中捕获到错误，或者最后发现地址值很离谱，就往前追溯一个基本块再执行，这样一直往前追溯直到计算出的地址通过校验为止

所以最后我们的流程就是先获取csel/cset前的寄存器信息，然后分别执行两次获取不同分支的结果，如果遇到错误就将模拟的范围提前并重新执行，最后获取正确地址后patch到最后两条指令的位置

### 具体实现

#### 模拟执行的准备工作

因为so本身也不大，为了方便我们直接遍历所有段，把整个so都载入模拟执行
bv是BinaryNinja在脚本执行时全局维护的一个单例，是和bn交互的接口，我们的各种信息都是通过bv提供的方法获取的

| 1234567891011 | `uc` `=` `Uc(UC_ARCH_ARM64, UC_MODE_ARM)``uc.mem_map(CODE_BASE, CODE_SIZE, UC_PROT_ALL)` `# 分配text段内存``uc.mem_map(STACK_BASE, STACK_SIZE, UC_PROT_ALL)` `# 分配栈内存``for` `segment` `in` `bv.segments:` `# 用bn API遍历所有段``if` `segment.readable:``start` `=` `segment.start``end` `=` `segment.end``size` `=` `end``-``start``print``(``"[+] Mapping segment: [{}]"``.``format``(``hex``(segment.data_length)))``content` `=` `bv.read(start, size)` `# 读取段数据``uc.mem_write(start, content)` `# 写入uc模拟器` |
|-|-|

#### 寻找特征指令

之后我们遍历所有指令，从中寻找带有间接跳转特征的br指令，具体流程为记录遇到的最后一个csel或cset，在遇到br后检测记录的csel和cset是否和br在同一个函数内，并且查看这句br指令否有bn自动打上的Unresolved Indirect Control Flow 标记，如果有则可以认为这是一处需要修复的间接跳转

| 12345678910111213141516171819202122232425262728293031323334353637383940414243 | `lastCsel` `=` `None``lastCset` `=` `None``nextWork` `=` `None`   `# 记录最后遇到的是csel还是cset``for` `instruction` `in` `bv.instructions:` `# 遍历所有指令``curAddr` `=` `instruction[``1``]``# print(curAddr)``if` `instruction[``0``][``0``].text` `=``=` `"csel"``:``lastCsel` `=` `instruction``nextWork` `=` `"csel"``if` `instruction[``0``][``0``].text` `=``=` `"cset"``:``lastCset` `=` `instruction``nextWork` `=` `"cset"``if` `instruction[``0``][``0``].text` `=``=` `"br"``:``tags` `=` `bv.get_functions_containing(curAddr)[``0``].tags` `# 获取当前函数的所有tag``curTag` `=` `None``for` `tag` `in` `tags:``if` `tag[``1``]` `=``=` `curAddr:` `#寻找br指令上的tag``curTag` `=` `tag[``2``]``break``if` `curTag` `is` `None` `or` `not` `(curTag.``type``.name` `=``=` `"Unresolved Indirect Control Flow"``):` `# 查看是否为间接控制流``continue``# print(hex(curAddr))``curBB` `=` `bv.get_basic_blocks_at(curAddr)[``0``]` `# 获取当前指令所在的基本块``curFunc` `=` `bv.get_functions_containing(curAddr)[``0``]` `# 获取当前指令所在的函数``# print(curBB)``if` `nextWork` `is` `None``:``continue``try``:``if` `nextWork` `=``=` `"csel"``:``if` `lastCsel[``1``] < curFunc.start` `or` `lastCsel[``1``] > curBB.end:` `# 判断csel指令是否在当前函数内``continue``workCsel(uc, bv, lastCsel, instruction,``(curBB.start, curBB.end), (``0xf4c0``,` `0x591d0``), white``=``[curBB.start])``nextWork` `=` `None``elif` `nextWork` `=``=` `"cset"``:` `if` `lastCset[``1``] < curFunc.start` `or` `lastCset[``1``] > curBB.end:` `# 判断cset指令是否在当前函数内``continue``workCset(uc, bv, lastCset, instruction,``(curBB.start, curBB.end), (``0xf4c0``,` `0x591d0``), white``=``[curBB.start])``nextWork` `=` `None``except` `Exception as e:` `#  捕获预期外的异常``print``(``"[{}] Error: {}"``.``format``(``hex``(uc.reg_read(UC_ARM64_REG_PC)), e))` |
|-|-|

#### workCsel函数

workCset函数和workCsel函数基本没什么区别，这里以workCsel函数为例

| 1 | `def` `workCsel(uc: Uc, bv: BinaryView, lastCsel:` `list``, Brinstruction:` `list``, emuRange:` `Tuple``, textSecRange:` `Tuple``, white:` `list` `=` `[], depth:` `int` `=` `0``)` |
|-|-|

我们需要上一条csel指令的信息，br指令的信息，模拟执行的区间，text段的区间位置和一个白名单（后面会讲这个白名单有什么用），为了方便调试还记录当前搜索的深度depth

| 12345 | `Hook` `=` `uc.hook_add(UC_HOOK_CODE, avoidBlHook,``{``"bv"``: bv,` `"white"``: white})``print``(lastCsel)``print``(``"[+] work at {} -- {}"``.``format``(``hex``(emuRange[``0``]),` `hex``(emuRange[``1``])))``print``(``"[+] cur search depth: {}"``.``format``(depth))` |
|-|-|

我们要先添加一个code hook，codehook是unicorn的一种机制，hook添加的回调函数会在每条指令执行前执行，我们可以用这个机制跳过一些我们不想进入的函数，hook的第三个参数是一些传递给回调的变量

##### avoidBLHook的实现

模拟的过程肯定会遇到一些跳转指令，bl就是arm中的call指令，跳转后ret会恢复pc的值，我们可以假设bl跳过去的函数不对我们的计算产生影响，而且如果跳进系统调用里uc就无法模拟了（因为是导入函数），所以遇到bl我们就把pc+4（arm64指令的长度）跳过这条指令
然后是我们在往前追溯的过程中，可能会遇到当前基本块是由某个条件跳转到达的，因为我们无法保证顺着模拟的时候一定满足跳转条件，具体情况如下图
 ![image](https://bbs.kanxue.com/upload/attach/202507/1017025_TDWATTUF4V2SKNS.webp)
所以我们要把遇到的基本块的开头加入白名单，在bl时跳过不在白名单中的地址，在b.cond时强制跳转到在白名单中的地址

| 12345678910111213141516171819202122232425262728 | `def` `avoidBlHook(uc: Uc, address, size, user_data):``bv` `=` `user_data.get(``"bv"``)``white` `=` `user_data.get(``"white"``)` `# 把传过来的白名单和bv取出来``assert` `isinstance``(bv, BinaryView)` `# 不这样写编辑器不识别bv的类型``code` `=` `bv.get_disassembly(address)` `# 获取当前地址的指令``if` `"bl"` `in` `code:``for` `tar` `in` `white:``if` `hex``(tar)` `in` `code:``if` `debugMode:``print``(``"enter {}"``.``format``(``hex``(tar)))``break``else``:` `# 遍历白名单，如果遍历完都没有break，说明当前指令要被跳过``if` `debugMode:``print``(``"[not {}] [skip {}] {}"``.``format``(``list``(``map``(``hex``, white)),` `hex``(address), code))``uc.reg_write(UC_ARM64_REG_PC, address``+``4``)` `# 把pc设置为pc+4``if` `"b."` `in` `code:``for` `tar` `in` `white:``if` `hex``(tar)` `in` `code:``if` `debugMode:``print``(``"force jmp {}"``.``format``(``hex``(tar)))``# 这里如果遇到了白名单中的地址，直接把pc覆写成这个地址，即强制跳转``uc.reg_write(UC_ARM64_REG_PC, tar)``break``else``:``if` `debugMode:``print``(``"skip unknown jmp target"``)``uc.reg_write(UC_ARM64_REG_PC, address``+``4``)` `# 否则就跳过（不然也可能会被导到不知道哪里去）` |
|-|-|

##### 收集信息

我们在收集信息的时候重置栈状态（为了确保每次开始执行时栈都是干净的没有上次的脏数据）

| 12345678910111213141516171819202122232425262728 | `def` `save_regisers(uc: Uc):``regs` `=` `{}``for` `reg` `in` `ARM64_REG_MAP:``if` `ARM64_REG_MAP[reg]` `is` `not` `None``:``regs[reg]` `=` `uc.reg_read(ARM64_REG_MAP[reg])` `# 读取所有寄存器信息并储存``return` `regs` `def` `emuToGetRegInitState(uc: Uc, start:` `int``, end:` `int``)` `-``>` `dict``:``stack_top` `=` `STACK_BASE` `+` `STACK_SIZE` `-` `0x100``uc.reg_write(UC_ARM64_REG_SP, stack_top)` `# 设置栈指针``# 根据arm调用约定，初始的栈顶必须写8个0x00``uc.mem_write(stack_top, b``"\x00\x00\x00\x00\x00\x00\x00\x00"``)``uc.emu_start(start, end)` `# 开启模拟``return` `save_regisers(uc)`  `regs` `=` `emuToGetRegInitState(uc, emuRange[``0``], lastCsel[``1``])``# 获取进入CSEL之前的寄存器状态``# 然后因为CSEL的赋值选择第一个还是第二个参数是和cond对应的，br跳转必然前面跟一个add类的计算指令来计算地址``# 也就是说，这里提供了两条指令的空间来让我们构造一对互补的b.cond ，于是就规避了可能误修改业务相关指令的麻烦` `destReg` `=` `lastCsel[``0``][``2``].text``trueReg` `=` `lastCsel[``0``][``5``].text``falseReg` `=` `lastCsel[``0``][``8``].text``cond` `=` `lastCsel[``0``][``11``].text``brTarget` `=` `Brinstruction[``0``][``2``].text``curAddr` `=` `Brinstruction[``1``]``# 这里搜集一些指令的参数信息，具体为什么这么写因为bn的指令token就是这么约定的` |
|-|-|

##### 执行模拟以获取跳转地址

我们恢复寄存器状态，开始第一次执行

| 123456789101112131415161718 | `def` `emuToGetJumpReg(uc: Uc, start:` `int``, end:` `int``, brTarget:` `str``)` `-``>` `int``:``uc.emu_start(start, end)``return` `uc.reg_read(ARM64_REG_MAP[brTarget])` `def` `recover_regisers(uc: Uc, regs:` `dict``):``for` `reg` `in` `ARM64_REG_MAP:``if` `ARM64_REG_MAP[reg]` `is` `not` `None``:``uc.reg_write(ARM64_REG_MAP[reg], regs[reg])``# print("{}  =   {}".format(reg, hex(regs[reg])))` `recover_regisers(uc, regs)``if` `trueReg` `=``=` `"xzr"` `or` `trueReg` `=``=` `"wzr"``:` `# 这个主要是处理uc不能读取arm的0寄存器的问题，我们要手动赋0``uc.reg_write(ARM64_REG_MAP[destReg],` `0``)``else``:``uc.reg_write(ARM64_REG_MAP[destReg],``regs[trueReg])``# print(regs[trueReg])``trueDest` `=` `emuToGetJumpReg(uc, lastCsel[``1``]``+``4``, curAddr,  brTarget)` |
|-|-|

然后再次恢复寄存器状态，开始第二次执行

| 123456789101112131415 | `recover_regisers(uc, regs)``if` `falseReg` `=``=` `"xzr"` `or` `falseReg` `=``=` `"wzr"``:``uc.reg_write(ARM64_REG_MAP[destReg],` `0``)``else``:``uc.reg_write(ARM64_REG_MAP[destReg],``regs[falseReg])``# print(regs[falseReg])``falseDest` `=` `emuToGetJumpReg(``uc, lastCsel[``1``]``+``4``, curAddr, brTarget)``if` `debugMode:``print``(``"[+]  if ture then to:{} \n else to:{}"``.``format``(``hex``(trueDest),` `hex``(falseDest)))``# print("[asm to replace]{}\n[asm to replace]{}".format(bv.get_disassembly(``# curAddr-4), bv.get_disassembly(curAddr)))``uc.hook_del(Hook)` `# 在工作都做完后记得要解除hook，不然重复hook就挂了` |
|-|-|

##### 处理错误地址

当然模拟不可能那么快就做完，首先是校验地址是否正确

| 123456789101112131415161718 | `if` `not` `(textSecRange[``0``] <``=` `trueDest <``=` `textSecRange[``1``])` `or` `not` `(textSecRange[``0``] <``=` `falseDest <``=` `textSecRange[``1``]):` `# 检查地址是否在text段范围内``print``(``"[x] wrong dest occured,try to fix"``)``# 如果没有前驱基本块，说明此时处于函数的第一个基本块，要去找该函数的交叉引用``if` `len``(bv.get_basic_blocks_at(emuRange[``0``])[``0``].incoming_edges)` `=``=` `0``:``ref` `=` `list``(bv.get_code_refs(emuRange[``0``]))``print``(``"{}  ref {}"``.``format``(``hex``(emuRange[``0``]), ref))``preBB` `=` `bv.get_basic_blocks_at(ref[``0``].address)[``0``]` `# 获取交叉引用所处的基本块``white.append(preBB.start)` `# 把基本块开头加入跳转白名单``else``:``preBB` `=` `bv.get_basic_blocks_at(``emuRange[``0``])[``0``].incoming_edges[``0``].source` `# 如果有前驱基本块，就获取它``white.append(preBB.start)` `# 把基本块开头加入跳转白名单``print``(``"[x] try find missing arg at {}"``.``format``(preBB))``workCsel(uc, bv, lastCsel, Brinstruction, (preBB.start,``emuRange[``1``]), textSecRange, white``=``white, depth``=``depth``+``1``)` `# 递归向前追溯``else``:` `# 如果正常就组装指令并patch``buildOpAndPatch(bv, cond, trueDest, falseDest, curAddr)` |
|-|-|

##### 捕捉非法地址读写

除了错误地址外也可能模拟出现非法地址读写，我们捕获UcError并做和上文同样的处理

| 1234567891011121314151617181920 | `except` `UcError as e:` `# 捕获到错误地址读写或其他错误行为``uc.hook_del(Hook)``if` `e.errno` `=``=` `UC_ERR_READ_UNMAPPED` `or` `e.errno` `=``=` `UC_ERR_WRITE_UNMAPPED:``print``(``"[x] unmapped R/W occured,try to fix    [{}    {}]"``.``format``(``hex``(``uc.reg_read(UC_ARM64_REG_PC)), bv.get_disassembly(uc.reg_read(UC_ARM64_REG_PC))))``else``:``print``(``"[!!!] unhanddle error: {}   [{}    {}]"``.``format``(e,` `hex``(``uc.reg_read(UC_ARM64_REG_PC)), bv.get_disassembly(uc.reg_read(UC_ARM64_REG_PC))))``if` `len``(bv.get_basic_blocks_at(emuRange[``0``])[``0``].incoming_edges)` `=``=` `0``:``ref` `=` `list``(bv.get_code_refs(emuRange[``0``]))``print``(``"{}  ref {}"``.``format``(``hex``(emuRange[``0``]), ref))``preBB` `=` `bv.get_basic_blocks_at(ref[``0``].address)[``0``]``white.append(preBB.start)``else``:``preBB` `=` `bv.get_basic_blocks_at(``emuRange[``0``])[``0``].incoming_edges[``0``].source``white.append(preBB.start)``print``(``"[x] try find missing arg at {}"``.``format``(preBB))``workCsel(uc, bv, lastCsel, Brinstruction, (preBB.start,``emuRange[``1``]), textSecRange, white``=``white, depth``=``depth``+``1``)` |
|-|-|

##### 完整的workCsel函数

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576777879808182838485868788 | `def` `workCsel(uc: Uc, bv: BinaryView, lastCsel:` `list``, Brinstruction:` `list``, emuRange:` `Tuple``, textSecRange:` `Tuple``, white:` `list` `=` `[], depth:` `int` `=` `0``):``try``:``Hook` `=` `uc.hook_add(UC_HOOK_CODE, avoidBlHook,``{``"bv"``: bv,` `"white"``: white})``print``(lastCsel)``print``(``"[+] work at {} -- {}"``.``format``(``hex``(emuRange[``0``]),` `hex``(emuRange[``1``])))``print``(``"[+] cur search depth: {}"``.``format``(depth))``regs` `=` `emuToGetRegInitState(uc, emuRange[``0``], lastCsel[``1``])``# 获取进入CSEL之前的寄存器状态``# 然后因为CSEL的赋值选择第一个还是第二个参数是和cond对应的，br跳转必然前面跟一个add类的计算指令来计算地址``# 也就是说，这里提供了两条指令的空间来让我们构造一对互补的b.cond ，于是就规避了可能误修改业务相关指令的麻烦` `destReg` `=` `lastCsel[``0``][``2``].text``trueReg` `=` `lastCsel[``0``][``5``].text``falseReg` `=` `lastCsel[``0``][``8``].text``cond` `=` `lastCsel[``0``][``11``].text``brTarget` `=` `Brinstruction[``0``][``2``].text``curAddr` `=` `Brinstruction[``1``]``# 这里搜集一些指令的参数信息，具体为什么这么写因为bn的指令token就是这么约定的``# print(regs)``if` `debugMode:``print``(destReg, trueReg, falseReg, cond, brTarget)` `# hk = uc.hook_add(UC_HOOK_CODE, codeHook, {"bv": bv})` `recover_regisers(uc, regs)``if` `trueReg` `=``=` `"xzr"` `or` `trueReg` `=``=` `"wzr"``:` `# 这个主要是处理uc不能读取arm的0寄存器的问题，我们要手动赋0``uc.reg_write(ARM64_REG_MAP[destReg],` `0``)``else``:``uc.reg_write(ARM64_REG_MAP[destReg],``regs[trueReg])``# print(regs[trueReg])``trueDest` `=` `emuToGetJumpReg(``uc, lastCsel[``1``]``+``4``, curAddr,  brTarget)` `recover_regisers(uc, regs)``if` `falseReg` `=``=` `"xzr"` `or` `falseReg` `=``=` `"wzr"``:``uc.reg_write(ARM64_REG_MAP[destReg],` `0``)``else``:``uc.reg_write(ARM64_REG_MAP[destReg],``regs[falseReg])``# print(regs[falseReg])``falseDest` `=` `emuToGetJumpReg(``uc, lastCsel[``1``]``+``4``, curAddr, brTarget)``if` `debugMode:``print``(``"[+]  if ture then to:{} \n else to:{}"``.``format``(``hex``(trueDest),` `hex``(falseDest)))``# print("[asm to replace]{}\n[asm to replace]{}".format(bv.get_disassembly(``# curAddr-4), bv.get_disassembly(curAddr)))``uc.hook_del(Hook)``if` `not` `(textSecRange[``0``] <``=` `trueDest <``=` `textSecRange[``1``])` `or` `not` `(textSecRange[``0``] <``=` `falseDest <``=` `textSecRange[``1``]):` `# 检查地址是否在text段范围内``print``(``"[x] wrong dest occured,try to fix"``)``# 如果没有前驱基本块，说明此时处于函数的第一个基本块，要去找该函数的交叉引用``if` `len``(bv.get_basic_blocks_at(emuRange[``0``])[``0``].incoming_edges)` `=``=` `0``:``ref` `=` `list``(bv.get_code_refs(emuRange[``0``]))``print``(``"{}  ref {}"``.``format``(``hex``(emuRange[``0``]), ref))``preBB` `=` `bv.get_basic_blocks_at(ref[``0``].address)[``0``]` `# 获取交叉引用所处的基本块``white.append(preBB.start)` `# 把基本块开头加入跳转白名单``else``:``preBB` `=` `bv.get_basic_blocks_at(``emuRange[``0``])[``0``].incoming_edges[``0``].source` `# 如果有前驱基本块，就获取它``white.append(preBB.start)` `# 把基本块开头加入跳转白名单``print``(``"[x] try find missing arg at {}"``.``format``(preBB))``workCsel(uc, bv, lastCsel, Brinstruction, (preBB.start,``emuRange[``1``]), textSecRange, white``=``white, depth``=``depth``+``1``)``else``:` `# 如果正常就组装指令并patch``buildOpAndPatch(bv, cond, trueDest, falseDest, curAddr)``except` `UcError as e:` `# 捕获到错误地址读写或其他错误行为``uc.hook_del(Hook)``if` `e.errno` `=``=` `UC_ERR_READ_UNMAPPED` `or` `e.errno` `=``=` `UC_ERR_WRITE_UNMAPPED:``print``(``"[x] unmapped R/W occured,try to fix    [{}    {}]"``.``format``(``hex``(``uc.reg_read(UC_ARM64_REG_PC)), bv.get_disassembly(uc.reg_read(UC_ARM64_REG_PC))))``else``:``print``(``"[!!!] unhanddle error: {}   [{}    {}]"``.``format``(e,` `hex``(``uc.reg_read(UC_ARM64_REG_PC)), bv.get_disassembly(uc.reg_read(UC_ARM64_REG_PC))))``if` `len``(bv.get_basic_blocks_at(emuRange[``0``])[``0``].incoming_edges)` `=``=` `0``:``ref` `=` `list``(bv.get_code_refs(emuRange[``0``]))``print``(``"{}  ref {}"``.``format``(``hex``(emuRange[``0``]), ref))``preBB` `=` `bv.get_basic_blocks_at(ref[``0``].address)[``0``]``white.append(preBB.start)``else``:``preBB` `=` `bv.get_basic_blocks_at(``emuRange[``0``])[``0``].incoming_edges[``0``].source``white.append(preBB.start)``print``(``"[x] try find missing arg at {}"``.``format``(preBB))``workCsel(uc, bv, lastCsel, Brinstruction, (preBB.start,``emuRange[``1``]), textSecRange, white``=``white, depth``=``depth``+``1``)` |
|-|-|

#### 组装指令

| 123456789 | `def` `buildOpAndPatch(bv: binaryview, cond:` `str``, trueDest:` `int``, falseDest:` `int``, curAddr:` `int``):``trueJmp` `=` `"b.{} #{}"``.``format``(cond,` `hex``(trueDest``-``(curAddr``-``4``)))``falseJmp` `=` `"b.{} #{}"``.``format``(ARM64_CONDS[cond],` `hex``(falseDest``-``curAddr))``print``(``"[asm gen]{}  ->  {}"``.``format``(bv.get_disassembly(curAddr``-``4``), trueJmp))``print``(``"[asm gen]{}  ->  {}"``.``format``(bv.get_disassembly(curAddr), falseJmp))``# 使用bn提供的指令转换api获得机械码``bv.write(curAddr``-``4``, Architecture[``'aarch64'``].assemble(trueJmp))``bv.write(curAddr, Architecture[``'aarch64'``].assemble(falseJmp))``print``(``"==================================================="``)` |
|-|-|

### 完整代码

cest的处理和csel类似，只是把从源寄存器赋值改为了赋值为0/1，这里就不多赘述，直接给出完整的脚本代码

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308309310311312313314315316317318319320321322323324325326327328329330331332333334335336337338339340341342343344345346347348349350351352353354355356 | `from` `binaryninja` `import` `*``from` `unicorn` `import` `*``from` `unicorn.arm64_const` `import` `*` `CODE_BASE` `=` `0x0``CODE_SIZE` `=` `0x1200000``+``0x1000``STACK_BASE` `=` `0x30000000``STACK_SIZE` `=` `0x8000` `ARM64_REG_MAP` `=` `{``'x0'``: UC_ARM64_REG_X0,` `'x1'``: UC_ARM64_REG_X1,` `'x2'``: UC_ARM64_REG_X2,` `'x3'``: UC_ARM64_REG_X3,``'x4'``: UC_ARM64_REG_X4,` `'x5'``: UC_ARM64_REG_X5,` `'x6'``: UC_ARM64_REG_X6,` `'x7'``: UC_ARM64_REG_X7,``'x8'``: UC_ARM64_REG_X8,` `'x9'``: UC_ARM64_REG_X9,` `'x10'``: UC_ARM64_REG_X10,` `'x11'``: UC_ARM64_REG_X11,``'x12'``: UC_ARM64_REG_X12,` `'x13'``: UC_ARM64_REG_X13,` `'x14'``: UC_ARM64_REG_X14,` `'x15'``: UC_ARM64_REG_X15,``'x16'``: UC_ARM64_REG_X16,` `'x17'``: UC_ARM64_REG_X17,` `'x18'``: UC_ARM64_REG_X18,` `'x19'``: UC_ARM64_REG_X19,``'x20'``: UC_ARM64_REG_X20,` `'x21'``: UC_ARM64_REG_X21,` `'x22'``: UC_ARM64_REG_X22,` `'x23'``: UC_ARM64_REG_X23,``'x24'``: UC_ARM64_REG_X24,` `'x25'``: UC_ARM64_REG_X25,` `'x26'``: UC_ARM64_REG_X26,` `'x27'``: UC_ARM64_REG_X27,``'x28'``: UC_ARM64_REG_X28,` `'x29'``: UC_ARM64_REG_X29,``'x30'``: UC_ARM64_REG_X30,``'sp'``: UC_ARM64_REG_SP,``'w0'``: UC_ARM64_REG_X0,` `'w1'``: UC_ARM64_REG_X1,` `'w2'``: UC_ARM64_REG_X2,` `'w3'``: UC_ARM64_REG_X3,``'w4'``: UC_ARM64_REG_X4,` `'w5'``: UC_ARM64_REG_X5,` `'w6'``: UC_ARM64_REG_X6,` `'w7'``: UC_ARM64_REG_X7,``'w8'``: UC_ARM64_REG_X8,` `'w9'``: UC_ARM64_REG_X9,` `'w10'``: UC_ARM64_REG_X10,` `'w11'``: UC_ARM64_REG_X11,``'w12'``: UC_ARM64_REG_X12,` `'w13'``: UC_ARM64_REG_X13,` `'w14'``: UC_ARM64_REG_X14,` `'w15'``: UC_ARM64_REG_X15,``'w16'``: UC_ARM64_REG_X16,` `'w17'``: UC_ARM64_REG_X17,` `'w18'``: UC_ARM64_REG_X18,` `'w19'``: UC_ARM64_REG_X19,``'w20'``: UC_ARM64_REG_X20,` `'w21'``: UC_ARM64_REG_X21,` `'w22'``: UC_ARM64_REG_X22,` `'w23'``: UC_ARM64_REG_X23,``'w24'``: UC_ARM64_REG_X24,` `'w25'``: UC_ARM64_REG_X25,` `'w26'``: UC_ARM64_REG_X26,` `'w27'``: UC_ARM64_REG_X27,``'w28'``: UC_ARM64_REG_X28,``'wzr'``:` `None``,``'xzr'``:` `None``,``}``# 每个条件码逻辑上对应的互补的条件``ARM64_CONDS` `=` `{``'eq'``:` `'ne'``,``'ne'``:` `'eq'``,``'hs'``:` `'lo'``,``'lo'``:` `'hs'``,``'mi'``:` `'pl'``,``'pl'``:` `'mi'``,``'vs'``:` `'vc'``,``'vc'``:` `'vs'``,``'hi'``:` `'ls'``,``'ls'``:` `'hi'``,``'ge'``:` `'lt'``,``'lt'``:` `'ge'``,``'gt'``:` `'le'``,``'le'``:` `'gt'``,``'cs'``:` `'cc'``,``'cc'``:` `'cs'``,``}`  `def` `save_regisers(uc: Uc):``regs` `=` `{}``for` `reg` `in` `ARM64_REG_MAP:``if` `ARM64_REG_MAP[reg]` `is` `not` `None``:``regs[reg]` `=` `uc.reg_read(ARM64_REG_MAP[reg])` `# 读取所有寄存器信息并储存``return` `regs`  `def` `codeHook(uc: Uc, address, size, user_data):``bv` `=` `user_data.get(``"bv"``)``code` `=` `bv.get_disassembly(address)``assert` `isinstance``(bv, BinaryView)``if` `address >``=` `0x021e5c` `and` `address <``=` `0x21e74``:``print``(``"[{}]{}"``.``format``(``hex``(address), code))``if` `address >``=` `0x000355f0` `and` `address <``=` `0x00035668``:``print``(``"[{}]{}"``.``format``(``hex``(address), code))`  `def` `recover_regisers(uc: Uc, regs:` `dict``):``for` `reg` `in` `ARM64_REG_MAP:``if` `ARM64_REG_MAP[reg]` `is` `not` `None``:``uc.reg_write(ARM64_REG_MAP[reg], regs[reg])``# print("{}  =   {}".format(reg, hex(regs[reg])))`  `def` `emuToGetRegInitState(uc: Uc, start:` `int``, end:` `int``)` `-``>` `dict``:``stack_top` `=` `STACK_BASE` `+` `STACK_SIZE` `-` `0x100``uc.reg_write(UC_ARM64_REG_SP, stack_top)` `# 设置栈指针``# 根据arm调用约定，初始的栈顶必须写8个0x00``uc.mem_write(stack_top, b``"\x00\x00\x00\x00\x00\x00\x00\x00"``)``uc.emu_start(start, end)` `# 开启模拟``return` `save_regisers(uc)`  `def` `emuToGetJumpReg(uc: Uc, start:` `int``, end:` `int``, brTarget:` `str``)` `-``>` `int``:``uc.emu_start(start, end)``return` `uc.reg_read(ARM64_REG_MAP[brTarget])`  `debugMode` `=` `1`  `def` `avoidBlHook(uc: Uc, address, size, user_data):``bv` `=` `user_data.get(``"bv"``)``white` `=` `user_data.get(``"white"``)` `# 把传过来的白名单和bv取出来``assert` `isinstance``(bv, BinaryView)` `# 不这样写编辑器不识别bv的类型``code` `=` `bv.get_disassembly(address)` `# 获取当前地址的指令``if` `"bl"` `in` `code:``for` `tar` `in` `white:``if` `hex``(tar)` `in` `code:``if` `debugMode:``print``(``"enter {}"``.``format``(``hex``(tar)))``break``else``:` `# 遍历白名单，如果遍历完都没有break，说明当前指令要被跳过``if` `debugMode:``print``(``"[not {}] [skip {}] {}"``.``format``(``list``(``map``(``hex``, white)),` `hex``(address), code))``uc.reg_write(UC_ARM64_REG_PC, address``+``4``)` `# 把pc设置为pc+4``if` `"b."` `in` `code:``for` `tar` `in` `white:``if` `hex``(tar)` `in` `code:``if` `debugMode:``print``(``"force jmp {}"``.``format``(``hex``(tar)))``# 这里如果遇到了白名单中的地址，直接把pc覆写成这个地址，即强制跳转``uc.reg_write(UC_ARM64_REG_PC, tar)``break``else``:``if` `debugMode:``print``(``"skip unknown jmp target"``)``uc.reg_write(UC_ARM64_REG_PC, address``+``4``)` `# 否则就跳过（不然也可能会被导到不知道哪里去）``# input()`  `def` `buildOpAndPatch(bv: binaryview, cond:` `str``, trueDest:` `int``, falseDest:` `int``, curAddr:` `int``):``trueJmp` `=` `"b.{} #{}"``.``format``(cond,` `hex``(trueDest``-``(curAddr``-``4``)))``falseJmp` `=` `"b.{} #{}"``.``format``(ARM64_CONDS[cond],` `hex``(falseDest``-``curAddr))``print``(``"[asm gen]{}  ->  {}"``.``format``(bv.get_disassembly(curAddr``-``4``), trueJmp))``print``(``"[asm gen]{}  ->  {}"``.``format``(bv.get_disassembly(curAddr), falseJmp))``bv.write(curAddr``-``4``, Architecture[``'aarch64'``].assemble(trueJmp))``bv.write(curAddr, Architecture[``'aarch64'``].assemble(falseJmp))``print``(``"==================================================="``)`  `def` `workCsel(uc: Uc, bv: BinaryView, lastCsel:` `list``, Brinstruction:` `list``, emuRange:` `Tuple``, textSecRange:` `Tuple``, white:` `list` `=` `[], depth:` `int` `=` `0``):``try``:``Hook` `=` `uc.hook_add(UC_HOOK_CODE, avoidBlHook,``{``"bv"``: bv,` `"white"``: white})``print``(lastCsel)``print``(``"[+] work at {} -- {}"``.``format``(``hex``(emuRange[``0``]),` `hex``(emuRange[``1``])))``print``(``"[+] cur search depth: {}"``.``format``(depth))``regs` `=` `emuToGetRegInitState(uc, emuRange[``0``], lastCsel[``1``])``# 获取进入CSEL之前的寄存器状态``# 然后因为CSEL的赋值选择第一个还是第二个参数是和cond对应的，br跳转必然前面跟一个add类的计算指令来计算地址``# 也就是说，这里提供了两条指令的空间来让我们构造一对互补的b.cond ，于是就规避了可能误修改业务相关指令的麻烦` `destReg` `=` `lastCsel[``0``][``2``].text``trueReg` `=` `lastCsel[``0``][``5``].text``falseReg` `=` `lastCsel[``0``][``8``].text``cond` `=` `lastCsel[``0``][``11``].text``brTarget` `=` `Brinstruction[``0``][``2``].text``curAddr` `=` `Brinstruction[``1``]``# 这里搜集一些指令的参数信息，具体为什么这么写因为bn的指令token就是这么约定的``# print(regs)``if` `debugMode:``print``(destReg, trueReg, falseReg, cond, brTarget)` `# hk = uc.hook_add(UC_HOOK_CODE, codeHook, {"bv": bv})` `recover_regisers(uc, regs)``if` `trueReg` `=``=` `"xzr"` `or` `trueReg` `=``=` `"wzr"``:` `# 这个主要是处理uc不能读取arm的0寄存器的问题，我们要手动赋0``uc.reg_write(ARM64_REG_MAP[destReg],` `0``)``else``:``uc.reg_write(ARM64_REG_MAP[destReg],``regs[trueReg])``# print(regs[trueReg])``trueDest` `=` `emuToGetJumpReg(``uc, lastCsel[``1``]``+``4``, curAddr,  brTarget)` `recover_regisers(uc, regs)``if` `falseReg` `=``=` `"xzr"` `or` `falseReg` `=``=` `"wzr"``:``uc.reg_write(ARM64_REG_MAP[destReg],` `0``)``else``:``uc.reg_write(ARM64_REG_MAP[destReg],``regs[falseReg])``# print(regs[falseReg])``falseDest` `=` `emuToGetJumpReg(``uc, lastCsel[``1``]``+``4``, curAddr, brTarget)``if` `debugMode:``print``(``"[+]  if ture then to:{} \n else to:{}"``.``format``(``hex``(trueDest),` `hex``(falseDest)))``# print("[asm to replace]{}\n[asm to replace]{}".format(bv.get_disassembly(``# curAddr-4), bv.get_disassembly(curAddr)))``uc.hook_del(Hook)``if` `not` `(textSecRange[``0``] <``=` `trueDest <``=` `textSecRange[``1``])` `or` `not` `(textSecRange[``0``] <``=` `falseDest <``=` `textSecRange[``1``]):` `# 检查地址是否在text段范围内``print``(``"[x] wrong dest occured,try to fix"``)``# 如果没有前驱基本块，说明此时处于函数的第一个基本块，要去找该函数的交叉引用``if` `len``(bv.get_basic_blocks_at(emuRange[``0``])[``0``].incoming_edges)` `=``=` `0``:``ref` `=` `list``(bv.get_code_refs(emuRange[``0``]))``print``(``"{}  ref {}"``.``format``(``hex``(emuRange[``0``]), ref))``preBB` `=` `bv.get_basic_blocks_at(ref[``0``].address)[``0``]` `# 获取交叉引用所处的基本块``white.append(preBB.start)` `# 把基本块开头加入跳转白名单``else``:``preBB` `=` `bv.get_basic_blocks_at(``emuRange[``0``])[``0``].incoming_edges[``0``].source` `# 如果有前驱基本块，就获取它``white.append(preBB.start)` `# 把基本块开头加入跳转白名单``print``(``"[x] try find missing arg at {}"``.``format``(preBB))``workCsel(uc, bv, lastCsel, Brinstruction, (preBB.start,``emuRange[``1``]), textSecRange, white``=``white, depth``=``depth``+``1``)``else``:` `# 如果正常就组装指令并patch``buildOpAndPatch(bv, cond, trueDest, falseDest, curAddr)``except` `UcError as e:` `# 捕获到错误地址读写或其他错误行为``uc.hook_del(Hook)``if` `e.errno` `=``=` `UC_ERR_READ_UNMAPPED` `or` `e.errno` `=``=` `UC_ERR_WRITE_UNMAPPED:``print``(``"[x] unmapped R/W occured,try to fix    [{}    {}]"``.``format``(``hex``(``uc.reg_read(UC_ARM64_REG_PC)), bv.get_disassembly(uc.reg_read(UC_ARM64_REG_PC))))``else``:``print``(``"[!!!] unhanddle error: {}   [{}    {}]"``.``format``(e,` `hex``(``uc.reg_read(UC_ARM64_REG_PC)), bv.get_disassembly(uc.reg_read(UC_ARM64_REG_PC))))``if` `len``(bv.get_basic_blocks_at(emuRange[``0``])[``0``].incoming_edges)` `=``=` `0``:``ref` `=` `list``(bv.get_code_refs(emuRange[``0``]))``print``(``"{}  ref {}"``.``format``(``hex``(emuRange[``0``]), ref))``preBB` `=` `bv.get_basic_blocks_at(ref[``0``].address)[``0``]``white.append(preBB.start)``else``:``preBB` `=` `bv.get_basic_blocks_at(``emuRange[``0``])[``0``].incoming_edges[``0``].source``white.append(preBB.start)``print``(``"[x] try find missing arg at {}"``.``format``(preBB))``workCsel(uc, bv, lastCsel, Brinstruction, (preBB.start,``emuRange[``1``]), textSecRange, white``=``white, depth``=``depth``+``1``)`  `def` `workCset(uc: Uc, bv: BinaryView, lastCset:` `list``, Brinstruction:` `list``, emuRange:` `Tuple``, textSecRange:` `Tuple``, white:` `list` `=` `[], depth:` `int` `=` `0``):``try``:``Hook` `=` `uc.hook_add(UC_HOOK_CODE, avoidBlHook,``{``"bv"``: bv,` `"white"``: white,` `"end"``: emuRange[``1``]})``print``(lastCset)``print``(``"[+] work at {} -- {}"``.``format``(``hex``(emuRange[``0``]),` `hex``(emuRange[``1``])))``print``(``"[+] cur search depth: {}"``.``format``(depth))``regs` `=` `emuToGetRegInitState(uc, emuRange[``0``], lastCset[``1``])` `destReg` `=` `lastCset[``0``][``2``].text``cond` `=` `lastCset[``0``][``5``].text``brTarget` `=` `Brinstruction[``0``][``2``].text``curAddr` `=` `Brinstruction[``1``]``if` `debugMode:``print``(destReg, cond, brTarget)``recover_regisers(uc, regs)``uc.reg_write(ARM64_REG_MAP[destReg],` `1``)``trueDest` `=` `emuToGetJumpReg(``uc, lastCset[``1``]``+``4``, curAddr,  brTarget)``recover_regisers(uc, regs)``uc.reg_write(ARM64_REG_MAP[destReg],` `0``)``falseDest` `=` `emuToGetJumpReg(``uc, lastCset[``1``]``+``4``, curAddr, brTarget)``if` `debugMode:``print``(``"[+]  if ture then to:{} \n else to:{}"``.``format``(``hex``(trueDest),` `hex``(falseDest)))``# print("[asm to replace]{}\n[asm to replace]{}".format(bv.get_disassembly(``#     curAddr-4), bv.get_disassembly(curAddr)))``uc.hook_del(Hook)``if` `not` `(textSecRange[``0``] <``=` `trueDest <``=` `textSecRange[``1``])` `or` `not` `(textSecRange[``0``] <``=` `falseDest <``=` `textSecRange[``1``]):``print``(``"[x] wrong dest occured,try to fix"``)``print``(``"incoming edges: {}"``.``format``(``bv.get_basic_blocks_at(emuRange[``0``])[``0``].incoming_edges))``if` `len``(bv.get_basic_blocks_at(emuRange[``0``])[``0``].incoming_edges)` `=``=` `0``:``ref` `=` `list``(bv.get_code_refs(emuRange[``0``]))``print``(``"{}  ref {}"``.``format``(``hex``(emuRange[``0``]), ref))``preBB` `=` `bv.get_basic_blocks_at(ref[``0``].address)[``0``]``white.append(preBB.start)``else``:``preBB` `=` `bv.get_basic_blocks_at(``emuRange[``0``])[``0``].incoming_edges[``0``].source``white.append(preBB.start)``print``(``"[x] try find missing arg at {}"``.``format``(preBB))``workCset(uc, bv, lastCset, Brinstruction, (preBB.start,``emuRange[``1``]), textSecRange, white``=``white, depth``=``depth``+``1``)``else``:``buildOpAndPatch(bv, cond, trueDest, falseDest, curAddr)` `except` `UcError as e:``uc.hook_del(Hook)``if` `e.errno` `=``=` `UC_ERR_READ_UNMAPPED` `or` `e.errno` `=``=` `UC_ERR_WRITE_UNMAPPED:``print``(``"[x] unmapped R/W occured,try to fix    [{}    {}]"``.``format``(``hex``(``uc.reg_read(UC_ARM64_REG_PC)), bv.get_disassembly(uc.reg_read(UC_ARM64_REG_PC))))``else``:``print``(``"[!!!] unhanddle error: {}   [{}    {}]"``.``format``(e,` `hex``(``uc.reg_read(UC_ARM64_REG_PC)), bv.get_disassembly(uc.reg_read(UC_ARM64_REG_PC))))``if` `len``(bv.get_basic_blocks_at(emuRange[``0``])[``0``].incoming_edges)` `=``=` `0``:``ref` `=` `list``(bv.get_code_refs(emuRange[``0``]))``print``(``"{}  ref {}"``.``format``(``hex``(emuRange[``0``]), ref))``preBB` `=` `bv.get_basic_blocks_at(ref[``0``].address)[``0``]``white.append(preBB.start)``else``:``preBB` `=` `bv.get_basic_blocks_at(``emuRange[``0``])[``0``].incoming_edges[``0``].source``white.append(preBB.start)``print``(``"[x] try find missing arg at {}"``.``format``(preBB))``workCset(uc, bv, lastCset, Brinstruction, (preBB.start,``emuRange[``1``]), textSecRange, white``=``white, depth``=``depth``+``1``)`  `def` `solve(bv: BinaryView):``uc` `=` `Uc(UC_ARCH_ARM64, UC_MODE_ARM)``uc.mem_map(CODE_BASE, CODE_SIZE, UC_PROT_ALL)` `# 分配text段内存``uc.mem_map(STACK_BASE, STACK_SIZE, UC_PROT_ALL)` `# 分配栈内存``for` `segment` `in` `bv.segments:` `# 用bn API遍历所有段``if` `segment.readable:``start` `=` `segment.start``end` `=` `segment.end``size` `=` `end``-``start``print``(``"[+] Mapping segment: [{}]"``.``format``(``hex``(segment.data_length)))``content` `=` `bv.read(start, size)` `# 读取段数据``uc.mem_write(start, content)` `# 写入uc模拟器``lastCsel` `=` `None``lastCset` `=` `None``nextWork` `=` `None`   `# 记录最后遇到的是csel还是cset``for` `instruction` `in` `bv.instructions:` `# 遍历所有指令``curAddr` `=` `instruction[``1``]``# print(curAddr)``if` `instruction[``0``][``0``].text` `=``=` `"csel"``:``lastCsel` `=` `instruction``nextWork` `=` `"csel"``if` `instruction[``0``][``0``].text` `=``=` `"cset"``:``lastCset` `=` `instruction``nextWork` `=` `"cset"``if` `instruction[``0``][``0``].text` `=``=` `"br"``:``tags` `=` `bv.get_functions_containing(curAddr)[``0``].tags` `# 获取当前函数的所有tag``curTag` `=` `None``for` `tag` `in` `tags:``if` `tag[``1``]` `=``=` `curAddr:` `# 寻找br指令上的tag``curTag` `=` `tag[``2``]``break``# 查看是否为间接控制流``if` `curTag` `is` `None` `or` `not` `(curTag.``type``.name` `=``=` `"Unresolved Indirect Control Flow"``):``continue``# print(hex(curAddr))``curBB` `=` `bv.get_basic_blocks_at(curAddr)[``0``]` `# 获取当前指令所在的基本块``curFunc` `=` `bv.get_functions_containing(curAddr)[``0``]` `# 获取当前指令所在的函数``# print(curBB)``if` `nextWork` `is` `None``:``continue``try``:``if` `nextWork` `=``=` `"csel"``:``if` `lastCsel[``1``] < curFunc.start` `or` `lastCsel[``1``] > curBB.end:` `# 判断csel指令是否在当前函数内``continue``workCsel(uc, bv, lastCsel, instruction,``(curBB.start, curBB.end), (``0xf4c0``,` `0x591d0``), white``=``[curBB.start])``nextWork` `=` `None``elif` `nextWork` `=``=` `"cset"``:``if` `lastCset[``1``] < curFunc.start` `or` `lastCset[``1``] > curBB.end:` `# 判断cset指令是否在当前函数内``continue``workCset(uc, bv, lastCset, instruction,``(curBB.start, curBB.end), (``0xf4c0``,` `0x591d0``), white``=``[curBB.start])``nextWork` `=` `None``except` `Exception as e:` `# 捕获预期外的异常``print``(``"[{}] Error: {}"``.``format``(``hex``(uc.reg_read(UC_ARM64_REG_PC)), e))`  `solve(bv)` |
|-|-|

直接选择bn的run script files执行，看到修复效果还是很好的
因为bn是动态分析的，所以要多次运行脚本才能修复每次新识别的指令
 ![image](https://bbs.kanxue.com/upload/attach/202507/1017025_XEWMUNZ7MWX4FRX.webp)

### 鸣谢

感谢 @l4n 师傅的文章对本篇文章的启发 [一种基于unicorn的寄存器间接跳转混淆去除方式](https://bbs.kanxue.com/thread-285764.htm)
同样感谢 @Itlly 师傅 和 @Jerem1ah 师傅在脚本开发过程中提供的建议

---

# 回复

## 回复 by 值得怀疑 (#2)

*2025-7-10 22:13*

作者的Binary Ninja是买的吗

## 回复 by xianyuuuan (#3)

*2025-7-10 22:41*

支持![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by SGSGsama (#4)

*2025-7-11 10:34*

>
> [值得怀疑](https://bbs.kanxue.com/user-396746.htm)
>
>  作者的Binary Ninja是买的吗
>
>

买的

## 回复 by bluegatar (#5)

*2025-7-14 10:36*

这个文章有技术含量啊

## 回复 by yixinBC (#6)

*2025-7-17 17:32*

>
> [xianyuuuan](https://bbs.kanxue.com/user-1002959.htm)
>
>  支持[em_079]
>
>

强的![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by wx_ㅤ_683 (#7)

*2025-11-21 13:24*

陷入无限循环怎么处理

## 回复 by iBa0 (#8)

*2025-12-4 10:42*

![image](https://bbs.kanxue.com/view/img/face/014.gif)来偷学Binaryninja了
