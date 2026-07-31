---
title: '[原创]使用unicorn模拟执行去除混淆'
url: https://bbs.kanxue.com/thread-280231.htm
tid: 280231
author: st0ne
date: '2024-01-17'
tags: [Android安全, 原创, 脱壳反混淆, 混淆加固, NDK分析, 逆向分析]
crawled_at: '2026-07-31T14:33:28+08:00'
replies: 30
---

# 0. 前言

在分析某app的so时遇到了间接跳转类型的混淆，不去掉的话无法使用ida f5来静态分析，f5之后就长下面这样：

![Alt text](https://bbs.kanxue.com/upload/attach/202401/887003_EM4XH3E722FRESP.png)

本文记录一下使用python+unicorn模拟执行来去掉混淆的过程。

# 1. 分析混淆的模式

混淆的汇编代码如下：
![Alt text](https://bbs.kanxue.com/upload/attach/202401/887003_V55JDNX9XPTFTJM.png)
可以看到，这个代码块进行了一通运算，然后通过 br x8，跳转到寄存器x8中保存的地址，仔细分析这个x8的来源，可以观察到如下的固定模式：

| 123456789101112 | `CMP`             `X19,` `#0``MOV             W9,` `#0x40 ; '@'         ; X9 = 0x40``MOV             W10,` `#0x38 ; '8'        ; X10 = 0x38``ADRP            X25,` `#off_212C70@PAGE``CSEL            X9, X10, X9, EQ         ;` `if` `X19` `=``=` `0` `then X9` `=` `X10``ADD             X25, X25,` `#off_212C70@PAGEOFF ; X25 = 0x212C70``LDR             X8, [X25,X9]            ; X8` `=` `qword[X25` `+` `X9]``MOV             W9,` `#0xFE53             ; X9 = 0xFE53``MOV             W10,` `#0x82B4            ; X10 = 0x82B4``CSEL            X9, X10, X9, EQ         ;` `if` `X19` `=``=` `0` `then X9` `=` `X10``SUB             X8, X8, X9              ; X8` `=` `X8` `-` `X9``BR              X8                      ; 跳转到X8` |
|-|-|

先看 LDR X8, [X25,X9]，X25寄存器是一张偏移表的基址， 这条指令从偏移表+X9出取出8字节数据放到了X8中，而X9的值来源于csel指令是0x38或者是0x40，由cmp的结果决定，如果X19等于0，则X9此时等于0x38，负责等于0x40。

再看 SUB X8, X8, X9，从偏移表取出一个8字节数据到X8之后，用X8减X9，结果放到X8,X9的值也是来源于csel指令，0x82B4或者是0xFE53

最后，通过br X8跳转到目标地址

也就是说，根据X9值的不同，最终跳转的地址会有两个，把正常的分支指令混淆成了上面这种模式，手动还原混淆可以把br X8 patch成：

| 12 | `beq addr1``b addr2` |
|-|-|

# 2. 去混淆的方式

本来想的是直接用python来匹配这种模式，然后手动计算出两个分支的地址，最后patch，但是后面发现，一个被混淆的函数中只有第一个混淆块会给X25赋值偏移表的地址，其他的块就直接用X25的值了，不会再次赋值，比如下面这个：
![Alt text](https://bbs.kanxue.com/upload/attach/202401/887003_6G4HXM488KUH5VV.png)

这样的话就不能把这些被混淆的块单独的拿出来看，因为缺少计算分支地址的必要条件，必须从函数的第一个被混淆的块出发，获取到偏移表的地址才行。如果还想通过手动的计算出目的地址，那就需要手动去确定函数的边界，这样就太麻烦了。

所以最后还是选择使通过模拟执行的方式，从函数头开始执行，跑通每一个块，在执行到混淆块的时候，计算出分支地址，最后进行patch

这里模拟执行的框架选择unicorn，之前学习过无名侠大佬用unicorn去ollvm混淆的文章，这里借鉴一下思路

# 3. 写脚本

## 3.1 加载so

由于代码中有需要访问偏移表，这些偏移表是在so的第二个segment，这个segment的内存便宜和文件便宜不一样，跟windows加载pe一样存在一个拉伸的效果，所以为了模拟执行代码时可以正常访问到偏移表的数据，我们手动将so拉伸成内存视图：

| 12345678910111213141516171819 | `def` `load_elf(filename):``global` `img_size``global` `out_data``segs` `=` `[]``with` `open``(filename,` `'rb'``) as f:``out_data` `=` `f.read()``for` `seg` `in` `ELFFile(f).iter_segments(``'PT_LOAD'``):``print``(``'file_off:%s, va: %s, size: %s'` `%``(``hex``(seg[``'p_offset'``]),` `hex``(seg[``'p_vaddr'``]),` `hex``(seg[``'p_filesz'``])))``segs.append((seg[``'p_offset'``],seg[``'p_vaddr'``], seg[``'p_filesz'``], seg.data()))` `img_size` `=` `segs[``-``1``][``1``]` `+` `segs[``-``1``][``2``]``byte_arr` `=` `bytearray([``0``]` `*` `img_size)``for` `seg` `in` `segs:``vaddr` `=` `seg[``1``]``size` `=` `seg[``2``]``data` `=` `seg[``3``]``byte_arr[vaddr: vaddr` `+` `size]` `=` `bytearray(data)` `return` `byte_arr` |
|-|-|

## 3.2 初始化unicorn

| 12345678910111213141516171819202122 | `def` `init_unicorn(file_name):``global` `bin_data``global` `uc` `#装载一下so到内存``bin_data` `=` `bytes(load_elf(file_name))` `uc` `=` `Uc(UC_ARCH_ARM64, UC_MODE_ARM)` `uc.mem_map(``0x80000000``,` `8` `*` `0x1000` `*` `0x1000``)``uc.mem_map(``0``,` `8` `*` `0x1000` `*` `0x1000``)``# 写入so数据``uc.mem_write(``0``, bin_data)``#设置sp寄存器``uc.reg_write(UC_ARM64_REG_SP,` `0x80000000` `+` `0x1000` `*` `0x1000` `*` `6``)``#设置指令执行hook，执行每条指令都会走hook_code``uc.hook_add(UC_HOOK_CODE, hook_code)``#设置非法内存访问hook``uc.hook_add(UC_HOOK_MEM_UNMAPPED, hook_mem_access)` `barr` `=` `uc.mem_read(``0x144320``,` `8``)``print``(barr)` |
|-|-|

## 3.3 如何跑通一个函数的所有路径

这里借鉴无名侠大佬的思路，先把入口节点放到队列中，然后不停从队列中取节点，以这个节点为起点模拟执行，直到下一个br reg，或者是ret。

一个节点包括地址和上下文环境(寄存器)，在模拟执行之前，需要把寄存器的值设置好，同时在找到分支之后，也需要保存现场的上下文环境。

在找到下一个br reg之后，计算出分支地址，将分支地址放到队列中，继续循环即可。

| 123456789101112131415161718192021222324252627282930313233343536373839 | `def` `deobf():``# 初始化unicorn``filename` `=` `'libxxxx.so'``patched_filename` `=` `'out.so'``start_addr` `=` `0x0103168` `init_unicorn(filename)` `q` `=` `queue.Queue()``q.put((start_addr,` `None``))` `# 入口函数是第一个节点，放到队列中去，队列中是(地址，上下文)``traced` `=` `{}` `# 跑过的节点``while` `not` `q.empty():` `#一直循环，直到队列为空``addr, context` `=` `q.get()``traced[addr]` `=` `1` `# 跑过了``s` `=` `run(addr, context)` `#开始模拟执行，找br reg` `if` `s` `is` `None``:``continue` `if` `len``(s)` `=``=` `2``:` `#单分支``if` `s[``0``]` `not` `in` `traced:``q.put(s)` `#将分支节点放到队列中``else``:` `#双分支``if` `s[``0``]` `not` `in` `traced:``q.put((s[``0``], s[``2``]))``#将分支节点放到队列中``if` `s[``1``]` `not` `in` `traced:``q.put((s[``1``], s[``2``]))``#将分支节点放到队列中` `def` `run(addr, context):``global` `uc``global` `is_success``global` `block_flow` `#开始模拟执行，函数返回说明在hook_code中执行了emu_stop``set_context(uc, context)``#设置寄存器环境``uc.emu_start(addr,` `0x10000``)``if` `is_success` `=``=` `True``:``is_success` `=` `False``return` `block_flow[addr]` `#返回分支信息和context` |
|-|-|

## 3.4 hook_code

hook_code是在unicorn中注册的指令执行回调，当执行uc.emu_start(addr, 0x10000)之后，就会开始模拟执行指令，同时调用hook_code，在hook_code中有很多重要的逻辑。

### 保存指令栈

进入hook_code之后，需要保存执行的汇编指令以及上下文环境，供后续判断是否到达混淆块使用：

| 12345678910111213141516 | `def` `hook_code(uc, address, size, user_data):``global` `ins_stack``global` `is_success` `if` `is_success` `=``=` `True``:``uc.emu_stop()``return` `ins_help` `=` `InsHelp()``code` `=` `uc.mem_read(address, size)``ins` `=` `list``(ins_help.disasm(code, address,` `False``))[``0``]` `print``(``"[+] tracing instruction\t0x%x:\t%s\t%s"` `%` `(ins.address, ins.mnemonic, ins.op_str))` `#记录指令和上下文环境``ins_stack.append((address, get_context(uc)))` |
|-|-|

### 遇到ret或者bl .__stack_chk_fail需要停止

这两个是函数的边界，执行到这里就需要停下，我没有找到如何优雅的判断执行到了bl .__stack_chk_fail，所以就判断bl后面的地址了。

| 123456789101112131415 | `#遇到ret直接挺停止``if` `ins.mnemonic.lower()` `=``=` `'ret'``:``#uc.reg_write(UC_ARM64_REG_PC, 0)``print``(``"[+] encountered ret, stop"``)``ins_stack.clear()``uc.emu_stop()``return` `#遇到bl .__stack_chk_fail停止``if` `ins.mnemonic.lower()` `=``=` `'bl'` `and` `ins.operands[``0``].imm` `=``=` `0x237C0``:``#uc.reg_write(UC_ARM64_REG_PC, 0)``print``(``"[+] encountered bl .__stack_chk_fail, stop"``)``ins_stack.clear()``uc.emu_stop()``return` |
|-|-|

### 跳过函数调用、非栈或者so本身的内存访问、svc

需要跳过这些指令，并不影响寻路

| 12345678910111213141516171819202122232425262728 | `#跳过bl、非栈、so本身内存访问、svc``if` `ins.mnemonic.lower().startswith(``'bl'``)` `or` `is_ref_ilegel_emm(uc, ins)` `or` `ins.mnemonic.lower().startswith(``'svc'``):``print``(``"[+] pass instruction 0x%x\t%s\t%s"` `%` `(ins.address, ins.mnemonic, ins.op_str))``uc.reg_write(UC_ARM64_REG_PC, address` `+` `size)``return` `def` `is_ref_ilegel_emm(mu, ins):``if` `ins.op_str.find(``'['``) !``=` `-``1``:``if` `ins.op_str.find(``'[sp'``)` `=``=` `-``1``:` `# 不是通过sp访问内存``for` `op` `in` `ins.operands:``if` `op.``type` `=``=` `ARM64_OP_MEM:``addr` `=` `0``if` `op.value.mem.base !``=` `0``:``addr` `+``=` `mu.reg_read(reg_ctou(ins.reg_name(op.value.mem.base)))``if` `op.value.mem.index !``=` `0``:``addr` `+``=` `mu.reg_read(reg_ctou(ins.reg_name(op.value.mem.index)))``if` `op.value.mem.disp !``=` `0``:``addr` `+``=` `op.value.mem.disp``if` `0x0` `<``=` `addr <``=` `img_size:` `# 访问so中的数据，允许``return` `False``elif` `0x80000000` `<``=` `addr <` `0x80000000` `+` `0x1000` `*` `0x1000` `*` `8``:` `#访问栈中的数据，允许``return` `False``else``:``return` `True``else``:``# 是通过sp的内存访问，允许``return` `False``else``:``return` `False` |
|-|-|

### 特征是否到达混淆块、计算分支地址

先判断是否是br指令，如果是，调用get_double_branch尝试去进一步匹配特征

| 12345678910111213141516171819202122 | `if` `ins.mnemonic` `=``=` `"br"``:``#判断是否到达间接跳转``is_success` `=` `True``block_base` `=` `ins_stack[``0``][``0``]``jmp_addr` `=` `ins_stack[``-``1``][``0``]``ret` `=` `get_double_branch(uc, ins_stack)``if` `ret !``=` `None``:``print``(``'find double branch: %x => %x, %x'` `%` `(block_base, ret[``0``], ret[``1``]))``block_flow[ins_stack[``0``][``0``]]` `=` `ret``patch_double_branch(uc, jmp_addr, ret)``else``:``ret` `=` `get_single_branch(uc, ins_stack)``if` `ret` `=``=` `None``:``print``(``"[+] find dest failed 0x%x\t%s\t%s"` `%` `(ins.address, ins.mnemonic, ins.op_str))``is_success` `=` `False``else``:``print``(``'find single branch: %x => %x'` `%` `(block_base, ret[``0``]))``block_flow[block_base]` `=` `ret``patch_single_branch(jmp_addr, ret[``0``])``ins_stack.clear()``uc.emu_stop()``return` |
|-|-|

进入get_double_branch，遍历指令栈，判断是否存在特定的指令，如果有则获取指定寄存器的值，最后计算出两个分支地址，这几个指令存在先后顺序，所以需要几个标志变量来控制。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475 | `def` `get_double_branch(uc, ins_stack):``#变量声明略` `ins_help` `=` `InsHelp()``cond` `=` `''` `for` `tup` `in` `ins_stack[::``-``1``]:``addr` `=` `tup[``0``]``context` `=` `tup[``1``]``ins` `=` `list``(ins_help.disasm(bin_data[addr: addr``+``5``], addr,` `False``))[``0``]` `# BR              X8``if` `ins.mnemonic.lower()` `=``=` `'br'` `and` `flag_br` `=``=` `False``:``flag_br` `=` `True``br_reg` `=` `ins.operands[``0``].reg` `# SUB             X8, X8, X9``if`  `flag_br` `=``=` `True` `and` `(ins.mnemonic.lower()` `=``=` `'add'` `or` `ins.mnemonic.lower()` `=``=` `'sub'``) \``and` `ins.operands[``0``].reg` `=``=` `br_reg` `and` `flag_sub_add` `=``=` `False``:``if` `ins.operands[``1``].``type` `=``=` `1` `and` `ins.operands[``2``].``type` `=``=` `1``:``op_reg1` `=` `ins.operands[``1``].reg``op_reg2` `=` `ins.operands[``2``].reg``flag_sub_add` `=` `True` `# CSEL            X9, X10, X9, EQ``if` `flag_sub_add` `=``=` `True` `and` `ins.mnemonic.lower()` `=``=` `'csel'` `and` `ins.operands[``0``].reg` `=``=` `op_reg2 \``and` `flag_csel1` `=``=` `False``:``cond` `=` `ins.op_str.split(``', '``)[``-``1``]``regname1` `=` `ins.reg_name(ins.operands[``1``].reg)``regname2` `=` `ins.reg_name(ins.operands[``2``].reg)``# index1 = reg_ctou(regname1) - arm64_const.UC_ARM64_REG_X0``# index2 = reg_ctou(regname2) - arm64_const.UC_ARM64_REG_X0``reg2_value1` `=` `0` `if` `regname1.lower()` `=``=` `'xzr'` `else` `context[reg_ctou(regname1)` `-` `arm64_const.UC_ARM64_REG_X0]``reg2_value2` `=` `0` `if` `regname2.lower()` `=``=` `'xzr'` `else` `context[reg_ctou(regname2)` `-` `arm64_const.UC_ARM64_REG_X0]``flag_csel1` `=` `True` `#  LDR             X8, [X25,X9]``if` `flag_sub_add` `=``=` `True` `and` `ins.mnemonic.lower()` `=``=` `'ldr'` `and` `ins.operands[``0``].reg` `=``=` `op_reg1 \``and` `flag_ldr` `=``=` `False``:``pattern` `=` `r``'\[(.*?)\]'``matches` `=` `re.findall(pattern, ins.op_str)``assert` `len``(matches)` `=``=` `1``,` `'not find []: %x\t%s\t%s'` `%` `(addr, ins.mnemonic, ins.op_str)``op2_str` `=` `matches[``0``]``regs` `=` `op2_str.split(``', '``)``assert` `len``(regs)` `=``=` `2``,` `'ins invalid!: %x\t%s\t%s'` `%` `(addr, ins.mnemonic, ins.op_str)``table_base` `=` `context[reg_ctou(regs[``0``])` `-` `arm64_const.UC_ARM64_REG_X0]``op_reg3` `=` `reg_ctou(regs[``1``])``flag_ldr` `=` `True` `#  CSEL            X9, X10, X9, EQ``if` `flag_ldr` `=``=` `True` `and` `ins.mnemonic.lower()` `=``=` `'csel'` `and` `reg_ctou(ins.reg_name(ins.operands[``0``].reg))` `=``=` `op_reg3 \``and` `flag_csel2` `=``=` `False``:``regname1` `=` `ins.reg_name(ins.operands[``1``].reg)``regname2` `=` `ins.reg_name(ins.operands[``2``].reg)``# index1 = reg_ctou(regname1) - arm64_const.UC_ARM64_REG_X0``# index2 = reg_ctou(regname2) - arm64_const.UC_ARM64_REG_X0``reg3_value1` `=` `0` `if` `regname1.lower()` `=``=` `'xzr'` `else` `context[reg_ctou(regname1)` `-` `arm64_const.UC_ARM64_REG_X0]``reg3_value2` `=` `0` `if` `regname2.lower()` `=``=` `'xzr'` `else` `context[reg_ctou(regname2)` `-` `arm64_const.UC_ARM64_REG_X0]``flag_csel2` `=` `True` `if` `flag_csel1` `=``=` `True` `and` `flag_csel2` `=``=` `True``:``# 满足条件时走的分支``barr1` `=` `uc.mem_read(table_base` `+` `reg3_value1,` `8``)` `#直接从文件中读数据，注意内存偏移和文件偏移的转换`  `base1` `=` `struct.unpack(``'q'``,barr1)``offset1` `=` `base1[``0``]` `-` `reg2_value1` `# 不满足条件时走的分支``barr2` `=` `uc.mem_read(table_base` `+` `reg3_value2,` `8``)``base2` `=` `struct.unpack(``'q'``,barr2)``offset2` `=` `base2[``0``]` `-` `reg2_value2``return` `(offset1, offset2, get_context(uc), cond)``else``:``return` `None` |
|-|-|

除了双分支，还有单分支的情况：
![Alt text](https://bbs.kanxue.com/upload/attach/202401/887003_FXHYPQRH85J5GDF.png)

这种只有一个固定的分支，所以直接patch成 b 0xxxxxxxxx即可
所以如果上述特征匹配不成功，则认为是单分支

## 3.5 patch

当遇到混淆块，计算出分支地址之后，就要进行patch了，双分支的patch需要两条指令的空间，但是有时候混淆块的倒数第二个指令是原来的指令，不能被覆盖，那么能用的就只有一条指令的空间。

那就只能找代码段中别的的空闲空间，调b跳转到空闲空间，然后在跳转到两个分支，找一个跳板。

当我在so中搜索nop时，居然发现了一段很长的nop，那用这里不就行了吗，反正去混淆也只是为了静态分析，不需要塞回去让so正常跑。

patch代码:

| 1234567891011121314151617181920212223242526272829303132 | `def` `patch_double_branch(uc, addr, branch):``global` `out_data` `nop_addr` `=` `find2nop(uc)``assert` `nop_addr` `is` `not` `None``,` `'no find 2 nop'` `offset1` `=` `branch[``0``]``offset2` `=` `branch[``1``]``cond` `=` `branch[``3``]` `ks` `=` `keystone.Ks(keystone.KS_ARCH_ARM64, keystone.KS_MODE_LITTLE_ENDIAN)` `# 1. 把bx reg修改成跳转到nop_addr``jmp1_asm` `=` `'b '` `+` `hex``(nop_addr)``jmp1_bin` `=` `ks.asm(jmp1_asm, addr)[``0``]` `# 2. bcond addr1``jmp2_asm` `=` `'b'` `+` `cond` `+` `' '` `+` `hex``(offset1)``jmp2_bin` `=` `ks.asm(jmp2_asm, nop_addr)[``0``]` `#3. b addr2``jmp3_asm` `=` `'b '` `+` `hex``(offset2)``jmp3_bin` `=` `ks.asm(jmp3_asm, nop_addr` `+` `4``)[``0``]``#print(jmp3_bin)` `#patching``print``(``'patch code: %x\t%s => %s'` `%` `(addr,` `list``(out_data[addr: addr` `+` `4``]), jmp1_bin))``out_data` `=` `patch_bytes(out_data, bytearray(jmp1_bin), addr,` `4``)``print``(``'patch code: %x\t%s => %s'` `%` `(nop_addr,` `list``(out_data[nop_addr: nop_addr` `+` `4``]), jmp2_bin))``out_data` `=` `patch_bytes(out_data, bytearray(jmp2_bin), nop_addr,` `4``)``print``(``'patch code: %x\t%s => %s'` `%` `(nop_addr` `+` `4``,` `list``(out_data[nop_addr` `+` `4``: nop_addr` `+` `8``]), jmp3_bin))``out_data` `=` `patch_bytes(out_data, bytearray(jmp3_bin) , nop_addr` `+` `4``,` `4``)` |
|-|-|

最后将so数据写回文件

| 123 | `#保存patch后的so``with` `open``(patched_filename,` `'wb'``) as f:``f.write(out_data)` |
|-|-|

# 4. 效果

还存在一些虚假控制流，但是已经不影响分析了
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/887003_HMY5NDQF4AJYAPX.webp)

# 5. 问题

1. 如果没有找到那一长串nop，就需要给代码段扩展一下放跳板，不知道咋搞
2. 混淆块的特征可能还需要进一步测试修改，只测了几个函数

# 6. 参考

- [[原创]ARM64 OLLVM反混淆](https://bbs.kanxue.com/thread-252321.htm)
- [[原创]记一次基于unidbg模拟执行的去除ollvm混淆](https://bbs.kanxue.com/thread-277086.htm)

上传的附件：
- main.py

（14.92kb，353次下载）

---

# 回复

## 回复 by mb_rjdrqvpa (#2)

*2024-1-17 10:41*

佬，能给个样本链接或者版本号不？这个APP，我去年分析签名算法时，混淆与文章不一样，所以有点困惑你文章的样本是什么时候的？
此外，友情提醒：它家主要难点是在风控上，非常激进。如果是业务需求搞它，建议早日更换目标

## 回复 by mudebug (#3)

*2024-1-17 12:27*

ida中可以手动添加节区

## 回复 by 秋狝 (#4)

*2024-1-17 13:50*

感谢分享

## 回复 by iyue_t (#5)

*2024-1-17 16:38*

感谢分享

## 回复 by wx_Deity (#6)

*2024-1-17 17:16*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rjdrqvpa](https://bbs.kanxue.com/user-932635.htm)
>
>  佬，能给个样本链接或者版本号不？这个APP，我去年分析签名算法时，混淆与文章不一样，所以有点困惑你文章的样本是什么时候的？此外，友情提醒：它家主要难点是在风控上，非常激进。如果是业务需求搞它，建议早日 ...
>
>

都脱敏了还能看出APP吗![image](https://bbs.kanxue.com/view/img/face/4.gif)

## 回复 by 星斗 (#7)

*2024-1-17 17:40*

某【x】黄【x】书？

## 回复 by mb_rjdrqvpa (#8)

*2024-1-17 21:44*

>
> [wx_Deity](https://bbs.kanxue.com/user-951489.htm)
>
>  都脱敏了还能看出APP吗[em_4]
>
>

脚本里面连so名字都给了，相当于已经告诉你是什么APP了

## 回复 by st0ne (#9)

*2024-1-17 22:23*

删除此评论

## 回复 by st0ne (#10)

*2024-1-17 22:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rjdrqvpa](https://bbs.kanxue.com/user-932635.htm)
>
>  佬，能给个样本链接或者版本号不？这个APP，我去年分析签名算法时，混淆与文章不一样，所以有点困惑你文章的样本是什么时候的？此外，友情提醒：它家主要难点是在风控上，非常激进。如果是业务需求搞它，建议早日 ...
>
>

版本号是12.17.404，就是在官网下的最新的。
感谢提示，不过我就是分析着玩的，不是业务需求。

## 回复 by st0ne (#11)

*2024-1-17 22:24*

好的，感谢大佬

## 回复 by st0ne (#12)

*2024-1-17 22:25*

>
> [mudebug](https://bbs.kanxue.com/user-696317.htm)
>
>  ida中可以手动添加节区
>
>

感谢大佬

## 回复 by st0ne (#13)

*2024-1-17 22:25*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rjdrqvpa](https://bbs.kanxue.com/user-932635.htm)
>
>  脚本里面连so名字都给了，相当于已经告诉你是什么APP了
>
>

大意了，忘记删了

## 回复 by st0ne (#14)

*2024-1-17 22:25*

>
> [星斗](https://bbs.kanxue.com/user-891470.htm)
>
>  某【x】黄【x】书？
>
>

可不敢

## 回复 by wx_Deity (#15)

*2024-1-18 09:18*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rjdrqvpa](https://bbs.kanxue.com/user-932635.htm)
>
>  脚本里面连so名字都给了，相当于已经告诉你是什么APP了
>
>

啊，我没下载脚本![image](https://bbs.kanxue.com/view/img/face/16.gif)

## 回复 by Roger (#16)

*2024-1-18 10:11*

膜拜大佬

## 回复 by mb_cmrpibxs (#17)

*2024-2-8 11:22*

大佬，ins_help这个包找不到怎么办

## 回复 by mb_cmrpibxs (#18)

*2024-2-8 12:25*

大佬  有技术交流群吗

## 回复 by st0ne (#19)

*2024-2-20 17:19*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_cmrpibxs](https://bbs.kanxue.com/user-994265.htm)
>
>  大佬，ins_help这个包找不到怎么办
>
>

这个是自己封装的包

## 回复 by st0ne (#20)

*2024-2-21 17:29*

这个暂时没有

## 回复 by mb_cmrpibxs (#21)

*2024-2-28 10:26*

>
> [st0ne](https://bbs.kanxue.com/user-887003.htm)
>
>  这个暂时没有
>
>

大佬  能加个qq交流下吗

## 回复 by 我是红领巾 (#22)

*2024-2-28 16:05*

佬，学习了

## 回复 by st0ne (#23)

*2024-2-28 22:12*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_cmrpibxs](https://bbs.kanxue.com/user-994265.htm)
>
>  大佬 能加个qq交流下吗
>
>

我加你吧

## 回复 by mb_cmrpibxs (#24)

*2024-2-29 08:52*

>
> [st0ne](https://bbs.kanxue.com/user-887003.htm)
>
>  我加你吧
>
>

qq   1654554961

## 回复 by mb_xfbrbpeu (#25)

*2024-6-25 11:13*

大佬能发下ins_help嘛，qq_base64: MTI3NzYwMTE1Nw==

## 回复 by 养只猫不好么 (#26)

*2024-8-9 10:17*

感谢分享

## 回复 by ben_ (#27)

*2024-11-28 18:09*

>
> [st0ne](https://bbs.kanxue.com/user-887003.htm)
>
>  这个是自己封装的包
>
>

大佬能上传一下你封装的这个包么

## 回复 by bluegatar (#28)

*2024-11-29 23:24*

有意思，这个br就是很讨厌的

## 回复 by kingking888 (#29)

*2024-11-29 23:52*

大佬能发下ins_help嘛，qq_base64: MTg0MTA4Mjcw

## 回复 by wx_Q道长 (#30)

*2025-8-18 18:09*

双分支的patch，可以把CSEL XX,XX,NE指令patch为对应的B.NE，然后把配对的BR XX指令patch为另外分支的B XX

## 回复 by todzhang (#31)

*2025-8-21 17:48*

我来补一个ins_help的简单实现哪边
# from ins_help import *

from capstone import *
from capstone.arm64 import *

# 简单利用 capstone 实现 InsHelp
def InsHelp():
    md = Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    md.detail = True #enable detail analyise
    return md
