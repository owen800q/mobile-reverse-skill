---
title: 教你玩转ida反编译（修改ida microcode）
url: https://bbs.kanxue.com/thread-288865.htm
tid: 288865
author: 孤恒
date: '2025-10-20'
tags: [Android安全, 基础理论, 逆向分析, 工具脚本]
crawled_at: '2026-07-31T15:28:55+08:00'
replies: 88
---

# 前言

看到了GhHei大佬的文章[OLLVM扁平化还原—更优雅的解法：IDA Hex-Rays Microcode](https://bbs.kanxue.com/thread-288691.htm)，迫不及待得尝试了一下，然后想对一些变种的OLLVM进行处理，由于大佬使用的方法没法添加新的分支，所以自己琢磨了一周，发现网上关于ida microcode的文章极少。这里查阅了[D810插件](https://github.com/joydo/d810)和[hrtng插件](https://github.com/KasperskyLab/hrtng)的源码才找到添加新分支的办法，最后也是写出了处理OLLVM的脚本。

# 修改反编译的两种方法

## 直接获取Pseudocode-A 中的 mba

通过find_widget 函数查找Pseudocode-A 界面，这里拿到的是TWidget再使用get_widget_vdui拿到vdui_t，从vdui_t中可以拿到 mba。

| 123456789101112131415 | `def` `find_pseudocode_view ( func_ea, auto_open``=``False` `):``widget` `=` `idaapi.find_widget(` `"Pseudocode-A"` `)``if` `widget` `and` `idaapi.get_widget_type( widget )` `=``=` `idaapi.BWN_PSEUDOCODE :``vu` `=` `idaapi.get_widget_vdui( widget )``if` `vu` `and` `vu.cfunc.entry_ea` `=``=` `func_ea :``return` `vu` `if` `auto_open :``idaapi.open_pseudocode( func_ea, idaapi.OPF_REUSE )``return` `find_pseudocode_view( func_ea,` `False` `)` `return` `None` `vu: ida_hexrays.vdui_t``=` `find_pseudocode_view(``0x113CC``,` `True``)``mba: ida_hexrays.mba_t` `=` `vu.cfunc.mba` |
|-|-|

这种方法拿到的 mba.maturity（成熟度） 是 8，已经是经过了所有优化之后的情况，没有办法添加新的块和删除块。

## 使用 ida hook 拦截中间的优化过程

ida python 里面有个Hexrays_Hooks 类，这个类里面可以拦截优化过程进度。根据类中的函数分别有以下进度：
● stkpnts：SP change points have been calculated.（SP 变化点已计算。）（mba maturity: 0）
● prolog：Prolog analysis has been finished.（前缀分析已完成。）（mba maturity: 0）
● microcode：Microcode has been generated.（微码已生成。）（mba maturity: 0）
● preoptimized：Microcode has been preoptimized.（微码已预先优化。）（mba maturity: 1）
● locopt：Basic block level optimization has been finished.（基本块级优化已完成。）（mba maturity: 2）
● calls_done：All calls have been analyzed.（所有调用都已分析。）（mba maturity: 3）
● prealloc：Local variables: preallocation step begins.（局部变量：预分配步骤开始。）（mba maturity: 5、6）
● glbopt：Global optimization has been finished. If microcode is modified, MERR_LOOP must be returned. It will cause a complete restart of the optimization.（全局优化已完成。如果微代码被修改，必须返回 MERR_LOOP。这将导致优化完全重启。）（mba maturity: 6）

| 12345678910111213141516171819202122232425262728293031323334353637 | `class` `HexraysDecompilationHook(Hexrays_Hooks):``def` `__init__(``self``):``super``().__init__()` `def` `prolog(``self``, mba: mbl_array_t, fc, reachable_blocks, decomp_flags)` `-``>` `"int"``:``print``(f``"prolog mba maturity: {mba.maturity}"``)``return` `0` `def` `glbopt(``self``, mba: mbl_array_t)` `-``>` `"int"``:``print``(f``"glbopt mba maturity: {mba.maturity}"``)``return` `MERR_OK` `def` `locopt(``self``, mba: mba_t)` `-``>` `int``:``print``(f``"locopt mba maturity: {mba.maturity}"``)``return` `0` `def` `prealloc(``self``, mba: mba_t)` `-``>` `int``:``print``(f``"prealloc mba maturity: {mba.maturity}"``)``return` `0``def` `calls_done(``self``, mba: mba_t):``print``(f``"calls_done mba maturity: {mba.maturity}"``)``return` `0` `def` `microcode(``self``, mba: mba_t):``print``(f``"microcode mba maturity: {mba.maturity}"``)``return` `0` `def` `stkpnts(``self``, mba: mba_t, _sps:ida_frame.stkpnts_t):``print``(f``"stkpnts mba maturity: {mba.maturity}"``)``return` `0` `def` `preoptimized(``self``, mba: mba_t):``print``(f``"preoptimized mba maturity: {mba.maturity}"``)``return` `0` `testHook` `=` `HexraysDecompilationHook()``print``(testHook.hook())` |
|-|-|

使用 hook 会在 F5 的时候都会执行，需要注意多个 hook 同一个优化进度可能会导致冲突。

# 在块中处理指令

在 ida mblock 中的指令是以双向链表进行连接的，mblock.head和 mblock.tail分别指向第一条指令和最后一条指令，指令使用的类型为minsn_t，以下为分析：
● minsn_t.opcode：操作码，如 goto、mov、jz 等
● minsn_t.d：目标操作数，可能是变量或寄存器
● minsn_t.l：左操作数，可能是变量、寄存器、常数、目标块
● minsn_t.r：右操作数，可能是变量或寄存器
举个例子：

| 1 | `mov` `#1.8, x8.8` |
|-|-|

mov 是 opcode，#1.8 是左操作数，x8.8 是右操作数

| 1 | `goto   @``34` |
|-|-|

goto 是 opcode，@34 是左操作数（块编号）

| 1 | `sub    x0.``8``{``34``},` `%``var_90.``8``{``3``}, x8.``8` |
|-|-|

sub 是 opcode，x0.8{34}是左操作数，%var_90.8{3}是右操作数，x8.8 是目标操作数
这些操作数使用的类是mop_t：
● mop_t.t：操作数类型，是个 int，后面会有说明
● mop_t.size：操作数大小，一般是 1、2、4、8 或者NOSIZE
● mop_t.r：微码寄存器，类型为 mreg_t
● mop_t.nnn：一个整数常量，类型为 mnumber_t
● mop_t.s：栈上变量的引用，类型为stkvar_ref_t
● mop_t.b：一般用于 goto 之后的 block_id
● mop_t.l：局部变量的引用，类型为lvar_ref_t
这里的操作数类型的宏定义如下：
● mop_r：寄存器，在 maturity 为MMAT_LVARS 之前使用，也就是说在MMAT_LVARS 之前使用的是mop_t.r，在其之后使用mop_t.l
● mop_n：立即数，对应mop_t.nnn
● mop_b：基本块（mblock），对应mop_t.b
● mop_l：局部变量，对应mop_t.l
● mop_S：局部栈变量，对应mop_t.s

## 修改指令

举个例子：

| 1234567 | `2.0` `;` `1WAY``-``BLOCK` `2` `FAKE INBOUNDS:` `1` `OUTBOUNDS:` `4` `[START``=``1143C` `END``=``11440``] MINREFS: STK``=``C0``/``ARG``=``2C0``, MAXBSP:` `0``2.0` `; DEF: w9.``4``2.0` `; DNU: w9.``4``2.0` `; VALRANGES: x20.``8``:``=``=``0``2.0` `mov` `#0x24279280.4, w9.4     ; 1143C split4 u=           d=w9.4``2.1` `goto   @``4`                      `;` `1143C` `u``=``2.1` |
|-|-|

这是第 2 个块（成熟度为 MMAT_GLBOPT3），可以通过 mba.get_mblock(2)拿到该块的数据，假如我要修改#0x24279280.4 这个立即数，首先使用 mblock.head 拿到第一条指令数据，然后这个立即数是左操作数那他对应的就是 minsn.l.nnn，在mnumber_t 里面成员 value 可以拿到具体数值，也就是说minsn.l.nnn.value 就是0x24279280，此时可以直接给minsn.l.nnn.value 赋值即可改变。代码如下：

| 123456789101112131415161718 | `from` `ida_hexrays` `import` `*``def` `change_minsn(mba: mba_t):``mblock:mblock_t` `=` `mba.get_mblock(``2``)``minsn:minsn_t` `=` `mblock.head``minsn.l.nnn.value` `=` `1``mba.verify(``True``)` `class` `HexraysDecompilationHook(Hexrays_Hooks):``def` `__init__(``self``):``super``().__init__()` `def` `glbopt(``self``, mba: mbl_array_t)` `-``>` `"int"``:``print``(f``"glbopt mba maturity: {mba.maturity}"``)``change_minsn(mba)``return` `MERR_OK` `testHook` `=` `HexraysDecompilationHook()``print``(testHook.hook())` |
|-|-|

改变前的反编译效果：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/979192_8M45DHVKN2VZ9VZ.webp)
加载脚本后，改变后的反编译效果
 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/979192_QDNPTDCMAWDFCZ9.webp)

## 新增指令

同样使用上面的例子，现在目标是在两行指令之间添加一行指令对w9.4 里面的值再次处理，新增一个减法指令，代码如下：

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647 | `from` `ida_hexrays` `import` `*``def` `add_new_minsn(mba: mba_t):``mblock:mblock_t` `=` `mba.get_mblock(``2``)` `# 新建左操作数，使用第一条指令的目标寄存器``new_mop_l` `=` `mop_t()``new_mop_l.t` `=` `mop_r``new_mop_l.r` `=` `mblock.head.d.r``new_mop_l.size` `=` `mblock.head.d.size` `# 新建右操作数，新建一个常数``new_mop_r` `=` `mop_t()``new_mop_r.t` `=` `mop_n``new_mop_r.nnn` `=` `mnumber_t(``0x24279280``)``new_mop_r.size` `=` `mblock.head.l.size` `# 新建目标操作数，使用第一条指令寄存器``new_mop_d` `=` `mop_t()``new_mop_d.t` `=` `mop_r``new_mop_d.r` `=` `mblock.head.d.r``new_mop_d.size` `=` `mblock.head.d.size` `# 新建指令，设定操作码和所有操作数``new_minsn` `=` `minsn_t(mblock.tail.ea)``new_minsn.opcode` `=` `m_sub``new_minsn.d` `=` `new_mop_d``new_minsn.l` `=` `new_mop_l``new_minsn.r` `=` `new_mop_r` `# 在参数二指令的后面添加新指令``mblock.insert_into_block(new_minsn, mblock.head)``# 用于打印mblock内容``vp` `=` `vd_printer_t()``mblock._print(vp)``mba.verify(``True``)` `class` `HexraysDecompilationHook(Hexrays_Hooks):``def` `__init__(``self``):``super``().__init__()` `def` `glbopt(``self``, mba: mbl_array_t)` `-``>` `"int"``:``print``(f``"glbopt mba maturity: {mba.maturity}"``)``change_minsn(mba)``return` `MERR_OK` `testHook` `=` `HexraysDecompilationHook()``print``(testHook.hook())` |
|-|-|

mblock 打印出来的内容如下：

| 123 | `2.0` `mov` `#0x24279280.4, w9.4     ; 1143C split4 u=           d=w9.4``2.1` `sub    w9.``4``,` `#0x24279280.4, w9.4 ; 1143C u=w9.4       d=w9.4``2.2` `goto   @``4`                      `;` `1143C` `u``=` |
|-|-|

再查看反编译后的内容：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/979192_PKA2VT4PCQ5EHHT.webp)

## 修改或新增跳转指令

修改或者新增跳转指令，不仅是对指令操作，还有对 mblock 的处理，包括 mblock 的上下文关系还有 mblock 的属性等。重新观察一下上面的例子：

| 1234567 | `2.0` `;` `1WAY``-``BLOCK` `2` `FAKE INBOUNDS:` `1` `OUTBOUNDS:` `4` `[START``=``1143C` `END``=``11440``] MINREFS: STK``=``C0``/``ARG``=``2C0``, MAXBSP:` `0``2.0` `; DEF: w9.``4``2.0` `; DNU: w9.``4``2.0` `; VALRANGES: x20.``8``:``=``=``0``2.0` `mov` `#0x24279280.4, w9.4     ; 1143C split4 u=           d=w9.4``2.1` `goto   @``4`                      `;` `1143C` `u``=``2.1` |
|-|-|

在第一行里有1WAY-BLOCK、INBOUNDS: 1、OUTBOUNDS: 4 这三个项是我们需要注意的，其中INBOUNDS 代表会有什么块跳转到本块，OUTBOUNDS 代表本块会跳转到什么块。那么 1WAY-BLOCK 是什么呢？我们来看下一个例子：

| 12345 | `6.0` `;` `2WAY``-``BLOCK` `6` `INBOUNDS:` `5` `OUTBOUNDS:` `7` `42` `[START``=``11494` `END``=``114A4``] MINREFS: STK``=``C0``/``ARG``=``2C0``, MAXBSP:` `0``6.0` `; USE: w8.``4``6.0` `; VALRANGES: w8.``4``:(``=``=``D61A7D2\|``=``=``24279280``),` `%``0xC``.``4``:(``=``=``24279280``\|``=``=``D6015831)``6.0` `jz     w8.``4``,` `#0xD61A7D2.4, @42 ; 114A0 inverted_jx u=w8.4``6.0` |
|-|-|

可以发现，当OUTBOUNDS 有 2 个的时候他是2WAY-BLOCK，这里代表两个分支。

### 修改 goto

从简单一点的入手，我们可以修改 mblock2 的 goto 让他直接跳转到结尾，代码如下：

| 1234567891011121314151617 | `def` `modify_edge(mba: mba_t, cur_block_id:` `int``, new_block_id:` `int` `=` `0``, old_block_id:` `int` `=` `0``):``cur_block: mblock_t` `=` `mba.get_mblock(cur_block_id)``new_block: mblock_t` `=` `mba.get_mblock(new_block_id)``old_block: mblock_t` `=` `mba.get_mblock(old_block_id)` `cur_block.succset._del(old_block_id)``old_block.predset._del(cur_block_id)` `cur_block.succset.push_back(new_block_id)``new_block.predset.push_back(cur_block_id)` `def` `change_goto(mba: mba_t):``mblock` `=` `mba.get_mblock(``2``)``minsn:minsn_t` `=` `mblock.tail``minsn.l.b` `=` `69``modify_edge(mba, cur_block_id``=``2``, old_block_id``=``4``, new_block_id``=``69``)``mba.verify(``True``)` |
|-|-|

mblock.succset 是后继块，mblock.predset 是前驱块，这个关联需要手动处理。
改完之后，这个 if else 直接到最后了。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/979192_S54G3QE2MGW6QWN.webp)

### 修改条件跳转

这会还是使用mblock2，把 goto 改成 jz 跳转，这里注意需要添加一个分支和修改1WAY-BLOCK，代码如下：

| 12345678910111213141516171819202122232425262728 | `def` `change_jz(mba: mba_t):``mblock:mblock_t` `=` `mba.get_mblock(``2``)``minsn:minsn_t` `=` `mblock.tail` `new_mop_l` `=` `mop_t()``new_mop_l.t` `=` `mop_r``new_mop_l.r` `=` `mblock.head.d.r``new_mop_l.size` `=` `mblock.head.d.size` `new_mop_r` `=` `mop_t()``new_mop_r.t` `=` `mop_n``new_mop_r.nnn` `=` `mnumber_t(``0x24279280``)``new_mop_r.size` `=` `mblock.head.l.size` `new_mop_d` `=` `mop_t()``new_mop_d.t` `=` `mop_b``new_mop_d.b` `=` `69``new_mop_d.size` `=` `NOSIZE` `minsn.opcode` `=` `m_jz``minsn.l` `=` `new_mop_l``minsn.r` `=` `new_mop_r``minsn.d` `=` `new_mop_d` `modify_edge(mba, cur_block_id``=``2``, new_block_id``=``3``, old_block_id``=``4``)``modify_edge(mba, cur_block_id``=``2``, new_block_id``=``69``)``mblock.``type` `=` `BLT_2WAY``mba.verify(``True``)` |
|-|-|

mblock.type 实际上就是1WAY-BLOCK，这里设置为BLT_2WAY 也就是 2WAY-BLOCK
 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/979192_7H8EJGFW56TSJGF.webp)
**特别需要注意的是，OUTBOUNDS 是有顺序的，例如 jz 的话第一个 id 是下一个 mblock，第二个才是 jz 跳转过去的 mblock**

# 新增块（mblock）

观察 ida 的微码可以发现，每个块的结尾都是一个跳转指令，那么如果我们想要添加一个分支判断也就是 jz 加 goto，那么我们需要新增一个块给 goto 使用。那么刚刚已经修改了 mblock2 的 goto 为 jz，这次新增一个 mblock3 写一个 goto 作为一个分支。代码如下：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051 | `def` `add_new_goto(mba: mba_t, cur_block_id:` `int``, new_block_id:` `int``, minsn_ea:` `int` `=` `None``):``new_mop` `=` `mop_t()``new_mop.t` `=` `mop_b``new_mop.b` `=` `new_block_id``new_mop.size` `=` `NOSIZE` `cur_block: mblock_t` `=` `mba.get_mblock(cur_block_id)``if` `minsn_ea:``new_goto` `=` `minsn_t(minsn_ea)``else``:``new_goto` `=` `minsn_t(cur_block.tail.ea)` `new_goto.opcode` `=` `m_goto``new_goto.l` `=` `new_mop` `if` `cur_block.tail:``cur_block.insert_into_block(new_goto, cur_block.tail)``else``:``cur_block.head` `=` `new_goto``cur_block.tail` `=` `new_goto` `def` `add_new_block(mba:mba_t):``mblock:mblock_t` `=` `mba.get_mblock(``2``)``new_mblock:mblock_t` `=` `mba.insert_block(mblock.serial` `+` `1``)``add_new_goto(mba, cur_block_id``=``new_mblock.serial, new_block_id``=``5``, minsn_ea``=``mblock.tail.ea)``modify_edge(mba, cur_block_id``=``new_mblock.serial, new_block_id``=``5``)``# 这里调整上一个块的后继块``modify_edge(mba, cur_block_id``=``mblock.serial, new_block_id``=``3``, old_block_id``=``3` `+` `1``)``# 调整顺序所以需要删除再push``modify_edge(mba, cur_block_id``=``mblock.serial, new_block_id``=``70``, old_block_id``=``70``)``new_mblock.make_lists_ready()``new_mblock.``type` `=` `BLT_1WAY``new_mblock.flags \|``=` `MBL_GOTO``# 设定地址``new_mblock.start` `=` `0x123456``new_mblock.end` `=` `0x123458``mba.verify(``True``)` `class` `HexraysDecompilationHook(Hexrays_Hooks):``def` `__init__(``self``):``super``().__init__()``self``.mba_change` `=` `False` `def` `glbopt(``self``, mba: mbl_array_t)` `-``>` `"int"``:``print``(f``"glbopt mba maturity: {mba.maturity}"``)``if` `self``.mba_change` `=``=` `False``:``change_jz(mba)``add_new_block(mba)``self``.mba_change` `=` `True``return` `MERR_LOOP``else``:``return` `MERR_OK` |
|-|-|

新增块有几个需要注意的点：

1. 插入块后，其他块的前驱后继连接都会自行改变，不用手动修改。
2. 新的块里面没有head 和 tail，新增指令时不能使用insert_into_block 而是直接赋给 head 和 tail。
3. 需要设定 mblock 的起始地址和结束地址，这里地址不一定是真实地址，但是结束地址必须大于起始地址。
4. 最重要的是在 hook 的时候，如果增删块的情况下需要返回MERR_LOOP 使其重新优化，否则会报错 50346。（你问我这个数字为什么记这么清楚，我只能说就是修这个报错修了两天）

---

# 回复

## 回复 by mb_uvyukvot (#2)

*2025-10-20 19:05*

感谢分享

## 回复 by 猫子 (#3)

*2025-10-20 19:18*

感谢分享

## 回复 by mb_irhdtnzm (#4)

*2025-10-20 19:44*

1

## 回复 by mb_ldbucrik (#5)

*2025-10-20 21:28*

感谢分享

## 回复 by mb_dmryhnwz (#6)

*2025-10-20 23:27*

66

## 回复 by mb_ndttieme (#7)

*2025-10-21 07:23*

这个讨论对我很有帮助，谢谢！

## 回复 by 善翁 (#8)

*2025-10-21 08:35*

谢谢分享

## 回复 by wx_插曲 (#9)

*2025-10-21 09:00*

66666

## 回复 by huangjw (#10)

*2025-10-21 09:23*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_ysegxpmv (#11)

*2025-10-21 09:30*

6666

## 回复 by KanXue_NG (#12)

*2025-10-21 09:34*

6666

## 回复 by MaYil (#13)

*2025-10-21 09:50*

感谢分享

## 回复 by Imxz (#14)

*2025-10-21 15:14*

tql

## 回复 by mb_tnkubkna (#15)

*2025-10-21 15:57*

111

## 回复 by 超级卡卡罗特 (#16)

*2025-10-21 17:27*

666

## 回复 by loudy (#17)

*2025-10-22 09:40*

6666

## 回复 by mb_qimctavn (#18)

*2025-10-23 13:21*

6

## 回复 by 威兹曼 (#19)

*2025-10-23 19:23*

666

## 回复 by kingking888 (#20)

*2025-10-24 00:05*

666

## 回复 by didiid (#21)

*2025-10-24 00:06*

666

## 回复 by mb_fywsujzf (#22)

*2025-10-24 01:14*

爸爸

## 回复 by fangliangz (#23)

*2025-10-24 10:26*

666

## 回复 by eroy (#24)

*2025-10-24 10:43*

666

## 回复 by baichisi (#25)

*2025-10-24 10:58*

6666

## 回复 by imliuxin (#26)

*2025-10-24 15:36*

好

## 回复 by git_27068Lych1e1 (#27)

*2025-10-24 17:56*

666

## 回复 by mb_uktygsmq (#28)

*2025-10-24 21:07*

66666

## 回复 by 温泉划水鱼 (#29)

*2025-10-25 03:48*

强

## 回复 by 寞叶_ (#30)

*2025-10-25 15:27*

谢谢分享

## 回复 by 嘎嘎真的很棒 (#31)

*2025-10-25 15:34*

6666

## 回复 by 青蓝梦 (#32)

*2025-10-25 17:21*

666

## 回复 by kagayaki (#33)

*2025-10-25 20:03*

感谢分享

## 回复 by mb_euhyowpw (#34)

*2025-10-25 22:07*

666

## 回复 by qqqiu (#35)

*2025-10-26 09:09*

6

## 回复 by zz胡 (#36)

*2025-10-26 13:47*

66666666

## 回复 by tshalan (#37)

*2025-10-26 15:18*

感谢分享

## 回复 by mb_cbgtaveo (#38)

*2025-10-27 10:49*

666666

## 回复 by Snowman_Liam (#39)

*2025-10-27 12:00*

6666

## 回复 by mb_zzzklvpa (#40)

*2025-10-27 14:16*

666

## 回复 by mb_mrjjcxgk (#41)

*2025-10-27 17:02*

666

## 回复 by zxc (#42)

*2025-10-28 07:50*

感谢分享

## 回复 by Oo风之恋oO (#43)

*2025-10-29 04:21*

太卷了

## 回复 by 夜惜风雨 (#44)

*2025-10-31 01:02*

66666

## 回复 by mb_jxoikqcy (#45)

*2025-11-1 02:43*

666666666

## 回复 by nng (#46)

*2025-11-1 18:28*

感谢分享

## 回复 by 枯藤舍 (#47)

*2025-11-3 11:47*

666

## 回复 by 鞠婧祎 (#48)

*2025-11-3 13:31*

看看隐藏

## 回复 by 鞠婧祎 (#49)

*2025-11-3 13:31*

看看隐藏

## 回复 by mb_cizqyhuh (#50)

*2025-11-3 16:43*

感谢分享！太实用了，特别是拦截优化过程和操作mblock的细节讲得透彻，对处理OLLVM混淆特别有帮助。参考[思维导图](https://www.anygraphanywhere.com/automap/mindmap.html?link=1762159949588-1762159949588)，简明归纳了核心方法。藏学习了～

![image](https://bbs.kanxue.com/upload/attach/202511/1040915_GQK5U4HCPC25GM2.webp)

## 回复 by 小青峰 (#51)

*2025-11-4 20:05*

66

## 回复 by 人模狗样 (#52)

*2025-11-7 00:48*

看看隐藏

## 回复 by git_46644wzxwhxcz (#53)

*2025-11-7 12:05*

看看666

## 回复 by 9494 (#54)

*2025-11-7 23:40*

6666

## 回复 by mb_wjytplsl (#55)

*2025-11-8 11:54*

666

## 回复 by wuaiwu (#56)

*2025-11-8 15:32*

6666

## 回复 by FindCall (#57)

*2025-11-10 16:23*

666

## 回复 by wssbwpp (#58)

*2025-11-10 17:17*

666

## 回复 by uni7corn (#59)

*2025-11-11 14:22*

感谢分享

## 回复 by wocaocou (#60)

*2025-11-15 14:14*

专业

## 回复 by GEKEZYX (#61)

*2025-11-21 13:58*

666

## 回复 by scpczc (#62)

*2025-11-28 16:25*

分享

## 回复 by wx_青竹 (#63)

*2025-12-9 17:04*

学习一下

## 回复 by asuralove (#64)

*2025-12-11 11:21*

666

## 回复 by mb_fhpfcoqp (#65)

*2025-12-18 16:15*

6666

## 回复 by scz (#66)

*2025-12-23 16:17*

改goto为jcond的示例非常好，降低了我的学习成本，专门找回此贴，感谢。

## 回复 by 毕索 (#67)

*2025-12-24 12:16*

666

## 回复 by mb_vxufgfcw (#68)

*2026-1-13 15:15*

孤恒666

## 回复 by 飆汗吉米 (#69)

*2026-1-16 21:34*

666

## 回复 by mb_bhkvnlqz (#70)

*2026-1-17 15:14*

66666666666

## 回复 by 万里星河 (#71)

*2026-1-17 16:49*

感谢分享

## 回复 by 万里星河 (#72)

*2026-1-18 20:47*

受教了

## 回复 by mb_cpziajgo (#73)

*2026-1-26 15:40*

666

## 回复 by mb_gvbpcqrf (#74)

*2026-1-28 09:14*

感谢分享

## 回复 by wx_飞_847 (#75)

*2026-2-4 09:32*

6666666

## 回复 by qig (#76)

*2026-2-4 12:42*

标记一下

## 回复 by water5555 (#77)

*2026-2-9 11:09*

6

## 回复 by 饮岁 (#78)

*2026-2-24 10:25*

666

## 回复 by caxfan (#79)

*2026-2-24 10:41*

感谢分享

## 回复 by cobe (#80)

*2026-2-24 17:34*

666

## 回复 by zzlfont (#81)

*2026-2-25 18:05*

666666666666

## 回复 by mb_lizfxfno (#82)

*2026-3-2 15:27*

66666666

## 回复 by Thehepta (#83)

*2026-3-2 19:06*

1

## 回复 by lookzo (#84)

*2026-3-3 09:11*

666

## 回复 by wx_code_258 (#85)

*2026-3-14 05:02*

看看隐藏

## 回复 by xeiyu (#86)

*2026-3-21 20:27*

666

## 回复 by iBa0 (#87)

*2026-4-6 14:43*

123

## 回复 by APlus (#88)

*2026-4-10 10:45*

666

## 回复 by dob_C (#89)

*2026-5-28 15:41*

感谢分享
