---
title: '[原创]非标准OLLVM-fla反混淆分析还原'
url: https://bbs.kanxue.com/thread-286549.htm
tid: 286549
author: 九天666
date: '2025-04-21'
tags: [Android安全, 原创, 混淆加固, 脱壳反混淆, 源码框架, 工具脚本]
crawled_at: '2026-07-31T15:54:07+08:00'
replies: 185
---

基于angr和idapython的非标准OLLVM-fla反混淆分析还原

## 序言

本文章主要是采用angr框架和idapython脚本相结合,实现对非标准ollvm-fla控制流平坦化反混淆的分析和处理,以及对angr和idapython相关api进项讲解。

## 为什么要用angr解决fla

要解决fla的混淆,需要实现三大步骤:

1. 找到函数的所有真实块
2. 找到真实块之间的连接关系
3. 重建真实块之间的控制流

步骤1,3相对简单,这里可以看大家的喜好,愿意用angr也是可以的,我倾向于在分析fla混淆的时候能够实时的观测到修改块的实时现象,我就采用了idapython脚本处理。

这里主要说的是步骤2,比如,当我们拿到了所有真实块,我们应该怎么去找到真是块之间的连接关系。遇到混淆程度不高的,可以尝试体力活修改。那么遇到下面的这种混淆,请问阁下该如何应对。

![image-20250420205824935](https://bbs.kanxue.com/upload/attach/202504/947335_N33BYGFWBURYQGE.png)

所以,这里我们需要用到angr的一个强大功能:**符号执行**（angr更多的原理需自行百度查阅）

这里又衍生出一个新问题,什么是**符号执行**？

它的运行和unidbg类似,都是通过模拟执行,但是不同的是,unidbg的模拟执行需要传入具体的数值,而angr可以不需要。

比如下面一个简单的加法函数,unidbg要模拟执行它,就需要传入a和b具体的数值,假设传入a=1,b=2,这里unidbg的执行结果就是3。

而angr不需要,它执行直接传入符号a和b,注意这里是符号,不是具体的值,最后通过模拟执行,输出结果a+b。

| 123 | `int` `add(``int` `a ,``int` `b){``return`  `a``+``b;``}` |
|-|-|

所以我们就是利用angr符号执行的特性,用到其中主要的路径探索的能力,当执行到第一个真实块A的时候 ,把它标记为主块,然后让其继续运行,当它碰到的第一个真实块B的时候,这里就是A的后继块,那么A和B的连接关系就被我们给找到了。这里也要注意到angr的一个路径爆炸的问题,后面会说怎么去规避。

## 反混淆

此函数作为本章内容的分析目标,这是一个非标准的ollvm，其有两个循环头

![image-20250420212618796](https://bbs.kanxue.com/upload/attach/202504/947335_GAMZ5YRUK5RU7KK.png)

### 找真实块

反混淆的第一步,找到函数的所有真实块。用idapython脚本处理

##### 获取函数的所有基本块

| 1 | `blocks` `=` `idaapi.FlowChart(idaapi.get_func(func_ea))` |
|-|-|

##### 获取函数的所有循环头

通过循环头我们可以直接获取到所有对应的真实块

采用广度搜索的原理实现循环头的获取

| 123456789101112131415 | `def` `find_loop_heads(func):``loop_heads` `=` `set``()``queue` `=` `deque()``block` `=` `get_block_by_address(func)``queue.append((block, []))``while` `len``(queue) >` `0``:``cur_block, path` `=` `queue.popleft()``if` `cur_block.start_ea` `in` `path:``loop_heads.add(cur_block.start_ea)``continue``path` `=` `path``+` `[cur_block.start_ea]``queue.extend((succ, path)` `for` `succ` `in` `cur_block.succs())``all_loop_heads` `=` `list``(loop_heads)``all_loop_heads.sort()``#升序排序,保证函数开始的主循环头在第一个``return` `all_loop_heads` |
|-|-|

##### 获取汇聚块

这里要处理标准fla和非标准fla的获取方式

非标准fla的循环头地址和汇聚块的地址是相等的

![image-20250420213954952](https://bbs.kanxue.com/upload/attach/202504/947335_229FX34NU6CNV2R.png)

标准fla的循环头地址和汇聚块的地址是不相等的，其循环头的前驱只有两个基本块,一个是序言块,一个是汇聚块。

![image-20250420214117412](https://bbs.kanxue.com/upload/attach/202504/947335_R8F9XBKEAU834RW.png)

| 12345678910111213 | `def` `find_converge_addr(loop_head_addr):``converge_addr` `=` `None``block` `=` `get_block_by_address(loop_head_addr)``preds` `=` `block.preds()``pred_list` `=` `list``(preds)``if` `len``(pred_list)` `=``=` `2``:``#循环头的前驱有两个基本块,这种一般是标准ollvm``for` `pred` `in` `pred_list:``tmp_list` `=` `list``(pred.preds())``if` `len``(tmp_list) >``1``:``#``converge_addr` `=` `pred.start_ea``else``:``#非标准ollvm``converge_addr``=` `loop_head_addr``return` `converge_addr` |
|-|-|

##### 得到所有真实块

有了汇聚块,就可以通过block所属的preds()方法获得所有的前驱块,也就是它的真实块。标准fla还得注意循环头的前驱块中，需要保留序言块

| 12345678910111213141516171819202122232425 | `real_blocks` `=` `[]` `if` `loop_head_addr !``=` `converge_addr:``loop_head_preds_addr.remove(converge_addr)``#移除汇聚块,剩下的一个是序言块``real_blocks.extend(loop_head_preds_addr)` `converge_block` `=` `get_block_by_address(converge_addr)``list_preds` `=` `list``(converge_block.preds())``for` `pred_block` `in` `list_preds:``if` `pred_block.start_ea` `=``=` `loop_head_addr:``#过滤循环头``continue``end_ea` `=` `pred_block.end_ea``last_ins_ea` `=` `idc.prev_head(end_ea)``mnem` `=` `idc.print_insn_mnem(last_ins_ea)` `# 获取基本块最后一条指令的操作符` `size` `=` `get_basic_block_size(pred_block)``if` `size >` `4` `and` `"B."` `not` `in` `mnem:``start_ea` `=` `pred_block.start_ea``mnem` `=` `idc.print_insn_mnem(start_ea)``if` `mnem` `=``=` `"CSEL"``:``csel_preds` `=` `pred_block.preds()``for` `csel_pred` `in` `csel_preds:``real_blocks.append(csel_pred.start_ea)``else``:``real_blocks.append(pred_block.start_ea)` |
|-|-|

| 123456 | `start_ea` `=` `pred_block.start_ea``mnem` `=` `idc.print_insn_mnem(start_ea)``if` `mnem` `=``=` `"CSEL"``:``csel_preds` `=` `pred_block.preds()``for` `csel_pred` `in` `csel_preds:``real_blocks.append(csel_pred.start_ea)` |
|-|-|

这个真实块的获取也需要注意,有的会出现多个基本块的尾部指令是相同的,ida会把它单独提取出来共享,如果我们直接使用0x42288的基本块作为真实块,会出现真实块遗漏,导致反混淆的代码不全。所以这里需要取0x42288的所有前驱作为真实块。

![image-20250420215954233](https://bbs.kanxue.com/upload/attach/202504/947335_M8P653C6N5TNEVR.png)

ret块的获取

像标准fla,我们就需要0xA66C作为ret块

![image-20250420220442863](https://bbs.kanxue.com/upload/attach/202504/947335_XFX65JCJBXTMV6V.png)

非标准fla,我们就需要0x42AB0作为ret块,为什么不选择0x42AC4为ret块呢?有两个原因:1.0x42AB0块中出有变量初始化的指令,如果直接选择0x42AC4,会导致反汇编后的真实代码遗漏。2.0x42AE4这条分支也没有后继。

从这里也可以引申出为社么标准fla要选择0xA66C作为ret块,如果选择0x96EC,因为0x9700分支有后继,还是会存在混淆代码，导致反混淆无效,虽然去除了一部分,但是还是无法直观分析代码。

![image-20250420220811211](https://bbs.kanxue.com/upload/attach/202504/947335_NRKP9ZVJNQTQTY9.png)

##### 完整代码

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191 | `from` `collections` `import` `deque``import` `idaapi``import` `idc` `def` `get_block_by_address(ea):``# 获取地址所在的函数``func` `=` `idaapi.get_func(ea)``blocks` `=` `idaapi.FlowChart(func)``for` `block` `in` `blocks:``if` `block.start_ea <``=` `ea < block.end_ea:``return` `block``return` `None` `def` `find_loop_heads(func):``loop_heads` `=` `set``()``queue` `=` `deque()``block` `=` `get_block_by_address(func)``queue.append((block, []))``while` `len``(queue) >` `0``:``cur_block, path` `=` `queue.popleft()``if` `cur_block.start_ea` `in` `path:``loop_heads.add(cur_block.start_ea)``continue``path` `=` `path``+` `[cur_block.start_ea]``queue.extend((succ, path)` `for` `succ` `in` `cur_block.succs())``all_loop_heads` `=` `list``(loop_heads)``all_loop_heads.sort()``#升序排序,保证函数开始的主循环头在第一个``return` `all_loop_heads` `def` `find_converge_addr(loop_head_addr):``converge_addr` `=` `None``block` `=` `get_block_by_address(loop_head_addr)``preds` `=` `block.preds()``pred_list` `=` `list``(preds)``if` `len``(pred_list)` `=``=` `2``:``#循环头的前驱有两个基本块,这种一般是标准ollvm``for` `pred` `in` `pred_list:``tmp_list` `=` `list``(pred.preds())``if` `len``(tmp_list) >``1``:``#``converge_addr` `=` `pred.start_ea``else``:``#非标准ollvm``converge_addr``=` `loop_head_addr``return` `converge_addr` `def` `get_basic_block_size(bb):``return` `bb.end_ea` `-` `bb.start_ea` `def` `add_block_color(ea):``block` `=` `get_block_by_address(ea)``curr_addr` `=` `block.start_ea``while` `curr_addr <block.end_ea:``idc.set_color(curr_addr,idc.CIC_ITEM,``0xffcc33``)``curr_addr` `=` `idc.next_head(curr_addr)` `#清除函数中的颜色渲染``def` `del_func_color(curr_addr):``end_ea` `=` `idc.find_func_end(curr_addr)``while` `curr_addr < end_ea:``idc.set_color(curr_addr, idc.CIC_ITEM,` `0xffffffff``)``curr_addr` `=` `idc.next_head(curr_addr)` `def` `find_ret_block_addr(blocks):``for` `block` `in` `blocks:``succs` `=` `block.succs()` `# 获取后继块``succs_list` `=` `list``(succs)` `# 转为list结构` `end_ea` `=` `block.end_ea``last_ins_ea` `=` `idc.prev_head(end_ea)``mnem` `=` `idc.print_insn_mnem(last_ins_ea)` `if` `len``(succs_list)` `=``=` `0``:``if` `mnem` `=``=` `"RET"``:``# 如果直接去把RET指令所在的块作为返回块的表示 最后可能会出现反混淆代码赋值错误``# 所以这里取RET指令的前驱块并且前驱块的大小不能只有一条指令,一般这个块都是有分支的``ori_ret_block` `=` `block``while` `True``:``tmp_block` `=` `block.preds()``pred_list` `=` `list``(tmp_block)``if` `len``(pred_list)` `=``=` `1``:``block` `=` `pred_list[``0``]``if` `get_basic_block_size(block)` `=``=` `4``:``continue``else``:``break``else``:``break` `# 此处while循环是为了解决当上述的ret块作为子分发器时,需要重新更改ret块为带ret指令的块``block2` `=` `block``num` `=` `0``i` `=` `0``while` `True``:``i` `+``=` `1``succs_block` `=` `block2.succs()``for` `succ` `in` `succs_block:``child_succs` `=` `succ.succs()``succ_list` `=` `list``(child_succs)``if` `len``(succ_list) !``=` `0``:``block2` `=` `succ``num` `+``=` `1``if` `num >` `2``:``block` `=` `ori_ret_block``break``if` `i >` `2``:``break``return` `block.start_ea` `def` `find_all_real_block(func_ea):` `blocks` `=` `idaapi.FlowChart(idaapi.get_func(func_ea))` `loop_heads` `=` `find_loop_heads(func_ea)``#获取所有循环头 非标准ollvm出现在多个主分发器``print``(f``"循环头数量:{len(loop_heads)}----{[hex(loop_head) for loop_head in loop_heads]}"``)` `all_real_block``=``[]``for` `loop_head_addr` `in` `loop_heads:``loop_head_block` `=` `get_block_by_address(loop_head_addr)``#获取循环头``loop_head_preds` `=` `list``(loop_head_block.preds())``#获取循环头的所有前驱块``loop_head_preds_addr` `=` `[loop_head_pred.start_ea` `for` `loop_head_pred` `in` `loop_head_preds]``#把所有前驱块转为数组` `converge_addr` `=` `find_converge_addr(loop_head_addr)``#获取汇聚块地址` `real_blocks` `=` `[]` `if` `loop_head_addr !``=` `converge_addr:``loop_head_preds_addr.remove(converge_addr)``#移除汇聚块,剩下的一个是序言块``real_blocks.extend(loop_head_preds_addr)` `converge_block` `=` `get_block_by_address(converge_addr)``list_preds` `=` `list``(converge_block.preds())``for` `pred_block` `in` `list_preds:` `end_ea` `=` `pred_block.end_ea``last_ins_ea` `=` `idc.prev_head(end_ea)``mnem` `=` `idc.print_insn_mnem(last_ins_ea)` `# 获取基本块最后一条指令的操作符` `size` `=` `get_basic_block_size(pred_block)``if` `size >` `4` `and` `"B."` `not` `in` `mnem:``start_ea` `=` `pred_block.start_ea``mnem` `=` `idc.print_insn_mnem(start_ea)``if` `mnem` `=``=` `"CSEL"``:``csel_preds` `=` `pred_block.preds()``for` `csel_pred` `in` `csel_preds:``real_blocks.append(csel_pred.start_ea)``else``:``real_blocks.append(pred_block.start_ea)` `real_blocks.sort()``#排序后第一个元素始终序言块``all_real_block.append(real_blocks)``print``(``"子循环头:"``, [``hex``(child_block_ea)` `for` `child_block_ea` `in` `real_blocks])` `#获取return块``ret_addr` `=` `find_ret_block_addr(blocks)``all_real_block.append(ret_addr)``print``(``"all_real_block:"``,all_real_block)` `all_real_block_list` `=` `[]``for` `real_blocks` `in` `all_real_block:``if` `isinstance``(real_blocks,` `list``):` `# 如果是列表，用 extend``all_real_block_list.extend(real_blocks)``else``:` `# 如果不是列表，用 append``all_real_block_list.append(real_blocks)` `for` `real_block_ea` `in` `all_real_block_list:``# idc.add_bpt(real_block_ea)#断点``add_block_color(real_block_ea)``#渲染颜色` `print``(``"\n所有真实块获取完成"``)``print``(``"===========INT==============="``)``print``(all_real_block_list)``print``(``"===========HEX==============="``)``print``(f``"数量:{len(all_real_block_list)}"``)``print``([``hex``(real_block_ea)` `for` `real_block_ea` `in` `all_real_block_list],``"\n"``)` `#移除ret地址和主序言块相关真实块,保留子序言块相关的真实块``all_child_prologue_addr` `=` `all_real_block.copy()``all_child_prologue_addr.remove(ret_addr)``all_child_prologue_addr.remove(all_child_prologue_addr[``0``])``print``(``"所有子序言块相关的真实块地址:"``,all_child_prologue_addr)` `all_child_prologue_last_ins_ea` `=` `[]``for` `child_prologue_array` `in` `all_child_prologue_addr:``child_prologue_addr` `=` `child_prologue_array[``0``]``child_prologue_block` `=` `get_block_by_address(child_prologue_addr)``child_prologue_end_ea` `=` `child_prologue_block.end_ea``child_prologue_last_ins_ea` `=` `idc.prev_head(child_prologue_end_ea)``all_child_prologue_last_ins_ea.append(child_prologue_last_ins_ea)``# print("所有子序言块的最后一条指令的地址:", [hex(ea) for ea in all_child_prologue_last_ins_ea])``print``(``"所有子序言块的最后一条指令的地址:"``, all_child_prologue_last_ins_ea)``return` `all_real_block,all_child_prologue_addr,all_child_prologue_last_ins_ea` `func_ea` `=` `0x41D08``reals` `=` `find_all_real_block(func_ea)` |
|-|-|

![image-20250421000959458](https://bbs.kanxue.com/upload/attach/202504/947335_6NRX4W2ZJM348AG.png)

![image-20250420221600877](https://bbs.kanxue.com/upload/attach/202504/947335_JQXPFD4XS5BJSU5.png)

调用后,通过颜色标记了所有的真实块

### 找真实块连接关系

反混淆的第二步,找到函数的所有真实块连接关系。用angr处理

这里就解决前面说到的在探索路径时遇到的路径爆炸的问题,一般常出现在一个循环里带一个if条件判断,这个时候angr就会由一条路径分裂出两条路径,这两条路径分别是if为true时的路径,和为false的路径,然后继续执行循环循环,此时2条路径就会变成4条路径,继续循环,4条路径就会出现8条路径......所以遇到这种情况,路径会以指数的形式增加,最后路径会膨胀到非常大,导致程序卡死。

![image-20250420222444505](https://bbs.kanxue.com/upload/attach/202504/947335_EB7VE9N3V45JFFV.png)

real_blocks是我上面获取到的所有真实块

所以接下来我采用的方式是,不让它整个程序一次性执行完,而是每次取一个真实块地址real_blocks[0],作为主块A,让其运行,当再次遇到的一个B地址在我保存的真实块地址里时我就停止运行,把这个块连接A->B保存下来。然后再取real_blocks[1]为主块,从头开始继续运行,再次遇到的一个地址在真实块地址里就停止运行。重复这个操作,我也就不用担心路径爆炸的问题,并且也会获得所有真实块的连接关系。

##### angr基本模板

| 12345 | `proj` `=` `angr.Project(file_path, auto_load_libs``=``False``)``#加载so``base` `=` `proj.loader.min_addr``#so基地址``func_addr` `=` `base` `+` `func_offset``#函数地址``init_state` `=` `proj.factory.blank_state(addr``=``func_addr)``#获取函数地址状态``init_state.options.add(angr.options.CALLLESS)` |
|-|-|

在一般情况下，加载程序都会将 `auto_load_libs` 置为 `False` ，这是因为如果将外部库一并加载，那么 `Angr` 就也会跟着一起去分析那些库了，这对性能的消耗是比较大的。

- blank_state：构造一个“空白板”空白状态，其中大部分数据未初始化。当访问未初始化的数据时，将返回一个不受约束的符号值。
- entry_state：造一个准备在主二进制文件的入口点执行的状态。
- full_init_state：构造一个准备好通过任何需要在主二进制文件入口点之前运行的初始化程序执行的状态，例如，共享库构造函数或预初始化程序。完成这些后，它将跳转到入口点。
- call_state：构造一个准备好执行给定函数的状态。

##### 执行流程构建

在序言块里会有许多寄存器的赋值操作,这些都是一些基本块的条件判断,通过寄存器值判断应该走哪条路径

![image-20250420234601190](https://bbs.kanxue.com/upload/attach/202504/947335_5ZBD74SZRX33K4C.png)

典型的就是以基本块最后一条指令的B.EQ，B.GT等等作为判断,这些都是子分发器。

![image-20250420234903713](https://bbs.kanxue.com/upload/attach/202504/947335_ZCBVRNAUGP9W835.png)

通过hook操作,当程序执行到主序言块的最后一条指令时,将pc寄存器赋值为真实块的值,这样可以避免执行大量的无用指令,减少性能消耗,节约更多的时间。

这里主要处理主序言块所有的真实块的操作,相关流程:

| 1 | `主序言块` `-``-``> 主块` `-``-``>后继块` |
|-|-|

| 1234567 | `def` `jump_to_address(state):``state.regs.pc` `=` `base` `+` `real_block_addr` `-` `4` `if` `prologue_block_addr` `=``=` `0``:``#当序言块执行完后(初始化后续条件判断的寄存器),将最后一条指令的pc寄存器指向真实块地址``if` `real_block_addr !``=` `func_offset:``proj.hook(first_block_last_ins.address, jump_to_address, first_block_last_ins.size)` |
|-|-|

![image-20250420235255542](https://bbs.kanxue.com/upload/attach/202504/947335_GHRBMJZF939335T.png)

这个是第二个循环头的序言块,后面就叫它子序言块

![image-20250420235418715](https://bbs.kanxue.com/upload/attach/202504/947335_D3KEHVK4BHHUCJ2.png)

![image-20250420235529132](https://bbs.kanxue.com/upload/attach/202504/947335_ZDFE54YBFSB6QYW.png)

| 12345 | `def` `jump_to_child_prologue_address(state):``state.regs.pc` `=` `prologue_block_addr` `-` `4``else``:``proj.hook(first_block_last_ins.address, jump_to_child_prologue_address, first_block_last_ins.size)``proj.hook(child_prologue_last_ins_ea, jump_to_address,` `4``)` |
|-|-|

这里也是一样用hook操作,改变pc寄存器的值。但是这里多了一步hook,多的 proj.hook(first_block_last_ins.address, jump_to_child_prologue_address, first_block_last_ins.size)这个hook是为了初始化子序言块里的寄存器值,因为子序言块0x42258里也有一些条件判断的寄存器赋值操作。

所以这里的流程是:

| 1 | `主序言块` `-``-``> 子序言块` `-``-``> 主块` `-``-``>后继块` |
|-|-|

![image-20250420235824033](https://bbs.kanxue.com/upload/attach/202504/947335_T66KBR9SVP2SQDC.png)

##### 完整代码

构建流程分析完了,这里就直接贴上相关脚本,脚本里也注释了相关代码的作用

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174 | `import` `logging``import` `time` `import` `angr``from` `tqdm` `import` `tqdm` `logging.getLogger(``'angr'``).setLevel(logging.ERROR)``#过滤angr日志,只显示ERROR日志,里面许多的WARNING输出影响日志分析` `def` `capstone_decode_csel(insn):``operands` `=` `insn.op_str.replace(``' '``, '``').split('``,')``dst_reg` `=` `operands[``0``]``condition` `=` `operands[``3``]``reg1` `=` `operands[``1``]``reg2` `=` `operands[``2``]``return` `dst_reg,reg1, reg2,condition` `def` `print_reg(state,reg_name):``value` `=` `state.regs.get(reg_name)``print``(f``"地址:{hex(state.addr)},寄存器:{reg_name},value:{value}"``)` `def` `find_state_succ(proj,base,local_state,flag,real_blocks,real_block_addr,path):``ins` `=` `local_state.block().capstone.insns[``0``]``dst_reg, reg1, reg2,condition` `=` `capstone_decode_csel(ins)``val1` `=` `local_state.regs.get(reg1)``val2` `=` `local_state.regs.get(reg2)``# print(f"寄存器值 {reg1}:{val1},{reg2}:{val2}")` `sm` `=` `proj.factory.simgr(local_state)``sm.step(num_inst``=``1``)``tmp_state` `=` `sm.active[``0``]``if` `flag:``setattr``(tmp_state.regs, dst_reg, val1)` `# 给寄存器的条件判断结果设为真``else``:``setattr``(tmp_state.regs, dst_reg, val2)` `# 给寄存器的条件判断结果设为假` `# print(f"开始运行的寄存器:{sm.active[0].regs.get(dst_reg)}")``while` `len``(sm.active):``# print(sm.active)``for` `active_state` `in` `sm.active:``ins_offset` `=` `active_state.addr` `-` `base``# if ins_offset == 0x41DC0:``#     print_reg("x8")``if` `ins_offset` `in` `real_blocks:``value` `=` `path[real_block_addr]``if` `ins_offset` `not` `in` `value:``#如果当前后继块不在path里,则添加,否则继续循环寻找``value.append(ins_offset)``return` `ins_offset``sm.step(num_inst``=``1``)` `def` `find_block_succ(proj,base,func_offset,state, real_block_addr, real_blocks, path):``msm` `=` `proj.factory.simgr(state)` `#构造模拟器` `# 第一个while的作用:寻找到传入的真实块地址作为主块,再复制一份当前state,准备后继块获取的操作``while` `len``(msm.active):``# print(f"路径{msm.active}")``for` `active_state` `in` `msm.active:``offset` `=` `active_state.addr` `-` `base``if` `offset` `=``=` `real_block_addr:` `# 找到真实块``mstate` `=` `active_state.copy()` `#复制state,为后继块的获取做准备``msm2` `=` `proj.factory.simgr(mstate)``msm2.step(num_inst``=``1``)` `# 防止下个while里获取后继块的时候key和value重复``#第二个while的作用:寻找真实块的所有后继块``while` `len``(msm2.active):``# print(msm2.active)``for` `mactive_state` `in` `msm2.active:``ins_offset` `=` `mactive_state.addr` `-` `base``if` `ins_offset` `in` `real_blocks:``#无分支块``#在无条件跳转中,并且有至少两条路径同时执行到真实块时,取非ret块的真实块``msm2_len` `=` `len``(msm2.active)``if` `msm2_len >` `1``:``tmp_addrs` `=` `[]``for` `s` `in` `msm2.active:``moffset` `=` `s.addr``-``base``tmp_value` `=` `path[real_block_addr]``if` `moffset` `in` `real_blocks` `and` `moffset` `not` `in` `tmp_value:``tmp_addrs.append(moffset)``if` `len``(tmp_addrs) >` `1``:``print``(``"当前至少有两个路径同时执行到真实块:"``,[``hex``(tmp_addr)` `for` `tmp_addr` `in` `tmp_addrs])``ret_addr` `=` `real_blocks[``len``(real_blocks)``-``1``]``if` `ret_addr` `in` `tmp_addrs:``tmp_addrs.remove(ret_addr)``ins_offset` `=` `tmp_addrs[``0``]``print``(``"两个路径同时执行到真实块最后取得:"``,``hex``(ins_offset))` `value` `=` `path[real_block_addr]``if` `ins_offset` `not` `in` `value:``value.append(ins_offset)``print``(f``"无条件跳转块关系:{hex(real_block_addr)}-->{hex(ins_offset)}"``)``return` `ins` `=` `mactive_state.block().capstone.insns[``0``]``if` `ins.mnemonic` `=``=` `'csel'``:``#有分支块``state_true` `=` `mactive_state.copy()``state_true_succ_addr` `=` `find_state_succ(proj,base,state_true,` `True``, real_blocks,real_block_addr, path)` `state_false` `=` `mactive_state.copy()``state_false_succ_addr` `=` `find_state_succ(proj,base,state_false,` `False``, real_blocks,real_block_addr, path)` `if` `state_true_succ_addr` `is` `None` `or` `state_false_succ_addr` `is` `None``:``print``(``"csel错误指令地址:"``,``hex``(ins_offset))``# print(f"csel后继有误:{hex(real_block_addr)}-->{state_true_succ_addr},{state_false_succ_addr}")``print``(f``"csel后继有误:{hex(real_block_addr)}-->{hex(state_true_succ_addr) if state_true_succ_addr is not None else state_true_succ_addr},"``f``"{hex(state_false_succ_addr) if state_false_succ_addr is not None else state_false_succ_addr}"``)``return` `"erro"` `print``(f``"csel分支跳转块关系:{hex(real_block_addr)}-->{hex(state_true_succ_addr)},{hex(state_false_succ_addr)}"``)``return``msm2.step(num_inst``=``1``)``return`  `# 真实块集合中的最后一个基本块如果最后没找到后继,说明是return块,直接返回``msm.step(num_inst``=``1``)` `def` `angr_main(real_blocks,all_child_prologue_addr,all_child_prologue_last_ins_ea,func_offset,file_path):``proj` `=` `angr.Project(file_path, auto_load_libs``=``False``)``base` `=` `proj.loader.min_addr``func_addr` `=` `base` `+` `func_offset``init_state` `=` `proj.factory.blank_state(addr``=``func_addr)``init_state.options.add(angr.options.CALLLESS)` `path` `=` `{key: []` `for` `key` `in` `real_blocks}` `# 初始化所有键的值为空列表``ret_addr` `=` `real_blocks[``len``(real_blocks)` `-` `1``]` `first_block` `=` `proj.factory.block(func_addr)``first_block_insns` `=` `first_block.capstone.insns``# 获取主序言块的最后一条指令``first_block_last_ins` `=` `first_block_insns[``len``(first_block_insns)` `-` `1``]` `for` `real_block_addr` `in` `tqdm(real_blocks):``if` `ret_addr` `=``=` `real_block_addr:``continue` `prologue_block_addr` `=` `0``child_prologue_last_ins_ea` `=` `0``if` `len``(all_child_prologue_addr)>``0``:``for` `index,child_prologue_array` `in` `enumerate``(all_child_prologue_addr):``if` `real_block_addr` `in` `child_prologue_array:``prologue_block_addr` `=` `child_prologue_array[``0``]``+``base``child_prologue_last_ins_ea` `=` `all_child_prologue_last_ins_ea[index]` `state` `=` `init_state.copy()``#拷贝初始化state,独立state``print``(``"正在寻找:"``,``hex``(real_block_addr))` `def` `jump_to_address(state):``state.regs.pc` `=` `base` `+` `real_block_addr` `-` `4` `def` `jump_to_child_prologue_address(state):``state.regs.pc` `=` `prologue_block_addr` `-` `4` `if` `prologue_block_addr` `=``=` `0``:``#当序言块执行完后(初始化后续条件判断的寄存器),将最后一条指令的pc寄存器指向真实块地址``if` `real_block_addr !``=` `func_offset:``proj.hook(first_block_last_ins.address, jump_to_address, first_block_last_ins.size)``else``:``proj.hook(first_block_last_ins.address, jump_to_child_prologue_address, first_block_last_ins.size)``proj.hook(child_prologue_last_ins_ea, jump_to_address,` `4``)` `ret` `=` `find_block_succ(proj,base,func_offset,state, real_block_addr, real_blocks, path)``if` `ret` `=``=` `"erro"``:``return` `hex_dict` `=` `{``hex``(key): [``hex``(value)` `for` `value` `in` `values]``for` `key, values` `in` `path.items()``}` `print``(``"真实块控制流:\n"``,hex_dict)``# 返回重建的控制流``return` `hex_dict`  `all_real_blocks` `=``[``269576``,` `269728``,` `269844``,` `269936``,` `270092``,` `270180``,` `270252``,` `270348``,` `270424``,` `270516``,` `270588``,` `270636``,` `270652``,` `270676``,` `270768``,` `270788``,` `270808``,` `270832``,` `270856``,` `270876``,` `270908``,` `272968``,` `273000``,` `273024``,` `273040``,` `270936``,` `271096``,` `271208``,` `271324``,` `271444``,` `271536``,` `271640``,` `271728``,` `271800``,` `271916``,` `271980``,` `272072``,` `272152``,` `272276``,` `272344``,` `272392``,` `272480``,` `272496``,` `272552``,` `272576``,` `272612``,` `272664``,` `272688``,` `272728``,` `272796``,` `272828``,` `272856``,` `272872``,` `272900``,` `272924``,` `272940``,` `273072``]``all_child_prologue_addr` `=`  `[[``270936``,` `271096``,` `271208``,` `271324``,` `271444``,` `271536``,` `271640``,` `271728``,` `271800``,` `271916``,` `271980``,` `272072``,` `272152``,` `272276``,` `272344``,` `272392``,` `272480``,` `272496``,` `272552``,` `272576``,` `272612``,` `272664``,` `272688``,` `272728``,` `272796``,` `272828``,` `272856``,` `272872``,` `272900``,` `272924``,` `272940``]]``all_child_prologue_last_ins_ea` `=` `[``270980``]` `angr_main(all_real_blocks,all_child_prologue_addr,all_child_prologue_last_ins_ea,``0x41D08``,``"libgeiri.so"``)` |
|-|-|

![image-20250421000806032](https://bbs.kanxue.com/upload/attach/202504/947335_4VA2GPRPDX3TZH5.png)

### 重建真实块之间的控制流

反混淆的第三步,重建真实块之间的控制流。用idapython处理

重建控制流主要对两种方式进行处理

1.带csel指令的分支跳转

![image-20250421001513924](https://bbs.kanxue.com/upload/attach/202504/947335_SWBHPCRN6HV86NG.png)

2.无分支跳转

![image-20250421001524817](https://bbs.kanxue.com/upload/attach/202504/947335_PB23F2GQY5GNC2A.png)

##### 完整代码

脚本里写好了相关注释,这里直接贴代码

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120 | `from` `collections` `import` `deque` `import` `ida_funcs``import` `idaapi``import` `idautils``import` `idc``import` `keystone` `#初始化Ks arm64架构的so,模式:小端序``ks` `=` `keystone.Ks(keystone.KS_ARCH_ARM64, keystone.KS_MODE_LITTLE_ENDIAN)``def` `patch_ins_to_nop(ins):``size` `=` `idc.get_item_size(ins)``for` `i` `in` `range``(size):``idc.patch_byte(ins` `+` `i,``0x90``)` `def` `get_block_by_address(ea):``func` `=` `idaapi.get_func(ea)``blocks` `=` `idaapi.FlowChart(func)``for` `block` `in` `blocks:``if` `block.start_ea <``=` `ea < block.end_ea:``return` `block``return` `None`   `def` `patch_branch(patch_list):` `for` `ea` `in` `patch_list:``values` `=` `patch_list[ea]``if` `len``(values)` `=``=` `0``:``#如果后继块为0,基本都是return块,不需要patch,直接跳过``continue``block` `=` `get_block_by_address(``int``(ea,` `16``))``start_ea` `=` `block.start_ea``end_ea` `=` `block.end_ea``last_ins_ea` `=` `idc.prev_head(end_ea)``#因为block.end_ea获取的地址是块最后一个地址的下一个地址,所以需要向上取一个地址``if` `len``(values)` `=``=` `2``:``#分支块的patch``flag` `=` `False``for` `ins` `in` `idautils.Heads(start_ea,end_ea):``#获取指定范围内的所有指令``if` `idc.print_insn_mnem(ins)` `=``=` `"CSEL"``:``condition` `=` `idc.print_operand(ins,``3``)``encoding, count` `=` `ks.asm(f``'B.{condition} {values[0]}'``,ins)``#生成CSEL指令处patch的汇编``encoding2, count2` `=` `ks.asm(f``'B {values[1]}'``, last_ins_ea)``#生成块最后一个地址指令处patch的汇编``for` `i` `in` `range``(``4``):``idc.patch_byte(ins``+` `i, encoding[i])``for` `i` `in` `range``(``4``):``idc.patch_byte(last_ins_ea` `+` `i, encoding2[i])``flag` `=` `True``if` `not` `flag:``#如果在有分支跳转的情况下没有找到CSEL指令,就要在当前基本块的最后两条指令做处理。此基本块的下一条指令就是csel``ins` `=` `idc.prev_head(last_ins_ea)``succs` `=` `block.succs()``succs_list` `=` `list``(succs)``csel_ea` `=` `succs_list[``0``].start_ea``condition` `=` `idc.print_operand(csel_ea,` `3``)``#获取csel指令的条件判断``encoding, count` `=` `ks.asm(f``'B.{condition} {values[0]}'``, ins)` `# 生成CSEL指令处patch的汇编``encoding2, count2` `=` `ks.asm(f``'B {values[1]}'``, last_ins_ea)` `# 生成块最后一个地址指令处patch的汇编``try``:``for` `i` `in` `range``(``4``):``idc.patch_byte(ins` `+` `i, encoding[i])``for` `i` `in` `range``(``4``):``idc.patch_byte(last_ins_ea` `+` `i, encoding2[i])``except` `:``print``(``"except"``)` `else``:``#无分支块的patch``encoding, count` `=` `ks.asm(f``'B {values[0]}'``, last_ins_ea)``for` `i` `in` `range``(``4``):``idc.patch_byte(last_ins_ea` `+` `i, encoding[i])``print``(``"pach over!!!"``)` `def` `find_all_useless_block(func_ea,real_blocks):``blocks` `=` `idaapi.FlowChart(idaapi.get_func(func_ea))``local_real_blocks` `=` `real_blocks.copy()``useless_blocks` `=` `[]``ret_block_addr` `=` `local_real_blocks[``len``(local_real_blocks)``-``1``]``queue` `=` `deque()``ret_block` `=` `get_block_by_address(ret_block_addr)``queue.append(ret_block)``while` `len``(queue) >` `0``:``#处理ret块相关的后继块``cur_block``=` `queue.popleft()``queue.extend(succ` `for` `succ` `in` `cur_block.succs())``ret_flag` `=` `False``for` `succ` `in` `cur_block.succs():``local_real_blocks.append(succ.start_ea)``end_ea` `=` `succ.end_ea``last_ins_ea` `=` `idc.prev_head(end_ea)``mnem` `=` `idc.print_insn_mnem(last_ins_ea)``if` `mnem` `=``=` `"RET"``:``ret_flag` `=` `True``if` `ret_flag:``break``# local_real_blocks.extend(succ.start_ea for succ in cur_block.succs())``for` `block` `in` `blocks:``start_ea` `=` `block.start_ea``if` `start_ea` `not` `in` `local_real_blocks:``useless_blocks.append(start_ea)``print``(``"所有的无用块:"``,[``hex``(b)``for` `b` `in` `useless_blocks])``return` `useless_blocks` `def` `patch_useless_blocks(func_ea,real_blocks):``useless_blocks` `=` `find_all_useless_block(func_ea, real_blocks)``# print(useless_blocks)``for` `useless_block_addr` `in` `useless_blocks:``block` `=` `get_block_by_address(useless_block_addr)``start_ea` `=` `block.start_ea``end_ea` `=` `block.end_ea` `insns` `=` `idautils.Heads(start_ea, end_ea)``for` `ins` `in` `insns:``patch_ins_to_nop(ins)``print``(``"无用块nop完成"``)` `patch_list` `=` `{``'0x41d08'``: [``'0x4221c'``],` `'0x41da0'``: [``'0x421c4'``,` `'0x42258'``],` `'0x41e14'``: [``'0x41fac'``],` `'0x41e70'``: [``'0x4213c'``],` `'0x41f0c'``: [``'0x42a80'``,` `'0x4200c'``],` `'0x41f64'``: [``'0x42ab0'``],` `'0x41fac'``: [``'0x42a80'``,` `'0x421d8'``],` `'0x4200c'``: [``'0x42a90'``],` `'0x42058'``: [``'0x41f64'``,` `'0x42ab0'``],` `'0x420b4'``: [``'0x41e70'``,` `'0x42208'``],` `'0x420fc'``: [``'0x42ab0'``,` `'0x421f0'``],` `'0x4212c'``: [``'0x42a68'``],` `'0x4213c'``: [``'0x4212c'``,` `'0x42ab0'``],` `'0x42154'``: [``'0x420b4'``],` `'0x421b0'``: [``'0x41fac'``],` `'0x421c4'``: [``'0x41f0c'``],` `'0x421d8'``: [``'0x42258'``,` `'0x42ab0'``],` `'0x421f0'``: [``'0x42ab0'``,` `'0x4223c'``],` `'0x42208'``: [``'0x4213c'``],` `'0x4221c'``: [``'0x42154'``,` `'0x4212c'``],` `'0x4223c'``: [``'0x41da0'``],` `'0x42a48'``: [``'0x42058'``],` `'0x42a68'``: [``'0x420fc'``,` `'0x42ab0'``],` `'0x42a80'``: [``'0x421d8'``],` `'0x42a90'``: [``'0x421b0'``,` `'0x41e14'``],` `'0x42258'``: [``'0x42a1c'``],` `'0x422f8'``: [``'0x42a48'``],` `'0x42368'``: [``'0x4266c'``],` `'0x423dc'``: [``'0x42368'``],` `'0x42454'``: [``'0x429d8'``,` `'0x426c8'``],` `'0x424b0'``: [``'0x42570'``,` `'0x42860'``],` `'0x42518'``: [``'0x42454'``],` `'0x42570'``: [``'0x42a04'``],` `'0x425b8'``: [``'0x428e4'``],` `'0x4262c'``: [``'0x429d8'``],` `'0x4266c'``: [``'0x42930'``,` `'0x428a8'``],` `'0x426c8'``: [``'0x42a2c'``],` `'0x42718'``: [``'0x428c0'``],` `'0x42794'``: [``'0x428a8'``,` `'0x42718'``],` `'0x427d8'``: [``'0x42918'``,` `'0x422f8'``],` `'0x42808'``: [``'0x427d8'``,` `'0x423dc'``],` `'0x42860'``: [``'0x42870'``],` `'0x42870'``: [``'0x42808'``,` `'0x42a48'``],` `'0x428a8'``: [``'0x427d8'``],` `'0x428c0'``: [``'0x4266c'``],` `'0x428e4'``: [``'0x42958'``,` `'0x42808'``],` `'0x42918'``: [``'0x429e8'``],` `'0x42930'``: [``'0x42794'``],` `'0x42958'``: [``'0x424b0'``],` `'0x4299c'``: [``'0x425b8'``],` `'0x429bc'``: [``'0x4299c'``],` `'0x429d8'``: [``'0x42a48'``],` `'0x429e8'``: [``'0x42518'``],` `'0x42a04'``: [``'0x42860'``],` `'0x42a1c'``: [``'0x429bc'``],` `'0x42a2c'``: [``'0x4262c'``,` `'0x429d8'``],` `'0x42ab0'``: []}``patch_branch(patch_list)`  `# func_ea =0x41D08``# real_blocks = [269576, 269728, 269844, 269936, 270092, 270180, 270252, 270348, 270424, 270516, 270588, 270636, 270652, 270676, 270768, 270788, 270808, 270832, 270856, 270876, 270908, 272968, 273000, 273024, 273040, 270936, 271096, 271208, 271324, 271444, 271536, 271640, 271728, 271800, 271916, 271980, 272072, 272152, 272276, 272344, 272392, 272480, 272496, 272552, 272576, 272612, 272664, 272688, 272728, 272796, 272828, 272856, 272872, 272900, 272924, 272940, 273072]``# patch_useless_blocks(func_ea,real_blocks)``# ida_funcs.reanalyze_function(ida_funcs.get_func(func_ea))#刷新函数控制流图``# print("控制流图已刷新")` |
|-|-|

![image-20250421001839203](https://bbs.kanxue.com/upload/attach/202504/947335_8FR7EYJ74XX2JUE.png)

查看重建结果,可以看到已经反混淆成功了

![image-20250421002303308](https://bbs.kanxue.com/upload/attach/202504/947335_3TZM2X2FUJSVZ4T.png)

针对上述的脚本最后也是归纳到一起了,内容较多,就不贴代码了,脚本文件会放置在github地址下载

使用的时候只需要提供函数地址即可

![image-20250421005731294](https://bbs.kanxue.com/upload/attach/202504/947335_MEV28ZA2WTFVDS6.png)

## 其他案例

1.cfg图

![image-20250421002705851](https://bbs.kanxue.com/upload/attach/202504/947335_DV38SJY6GA8FBBE.png)

![image-20250421004548913](https://bbs.kanxue.com/upload/attach/202504/947335_PVJ239HAKNUM9G9.png)

2.cfg图

![image-20250421004622746](https://bbs.kanxue.com/upload/attach/202504/947335_RM5QNK2JP68EXQ3.png)

![image-20250421004902168](https://bbs.kanxue.com/upload/attach/202504/947335_5X7SYVXD66JGFZF.png)

## 结尾

ollvm-fla的混淆围绕三大步骤展开可以实现反混淆,脚本不是全部通用,如果遇到混淆程度非常复杂的,还得需要针对性去完善相关功能。

分析样本可以用上篇文章的

相关文件下载地址:https://github.com/jiutian666/xdefla.git

---

# 回复

## 回复 by wx_插曲 (#2)

*2025-4-21 05:31*

牛逼大佬

## 回复 by fireworld (#3)

*2025-4-21 06:01*

感谢楼主分享

## 回复 by mb_vjpiriil (#4)

*2025-4-21 06:32*

666

## 回复 by fujing (#5)

*2025-4-21 07:34*

看看技术贴

## 回复 by 猫子 (#6)

*2025-4-21 07:44*

学习一下

## 回复 by 丶咖啡猫丶 (#7)

*2025-4-21 09:19*

大佬666

## 回复 by cobe (#8)

*2025-4-21 09:32*

666

## 回复 by mb_ncfbmciq (#9)

*2025-4-21 09:36*

大佬牛B

## 回复 by 我不是卷王 (#10)

*2025-4-21 09:37*

666

## 回复 by mb_ldbucrik (#11)

*2025-4-21 09:52*

感谢分享，大佬yyds

## 回复 by 4Chan (#12)

*2025-4-21 09:55*

666

## 回复 by MaYil (#13)

*2025-4-21 10:25*

感谢分享

## 回复 by 西瓜帅 (#14)

*2025-4-21 11:10*

感谢分享

## 回复 by uni7corn (#15)

*2025-4-21 11:36*

感谢分享

## 回复 by dextoart (#16)

*2025-4-21 13:04*

666

## 回复 by A冷忆 (#17)

*2025-4-21 13:13*

666

## 回复 by wulibeiai (#18)

*2025-4-21 13:28*

666

## 回复 by ptr1234565 (#19)

*2025-4-21 14:39*

666

## 回复 by New对象处 (#20)

*2025-4-21 14:45*

6

## 回复 by mb_cbgtaveo (#21)

*2025-4-21 15:43*

66666666666

## 回复 by 风远丶扬 (#22)

*2025-4-21 17:21*

666

## 回复 by koflfy (#23)

*2025-4-21 17:29*

大佬牛逼

## 回复 by hacker521 (#24)

*2025-4-21 17:36*

牛逼大佬

## 回复 by Imxz (#25)

*2025-4-21 18:03*

太牛了 哥们

## 回复 by mb_kgfqphsx (#26)

*2025-4-21 19:18*

666

## 回复 by kingking888 (#27)

*2025-4-21 23:22*

666

## 回复 by 带带弟弟吧 (#28)

*2025-4-22 10:48*

1

## 回复 by FMNS (#29)

*2025-4-22 11:06*

感谢分享

## 回复 by Ms135 (#30)

*2025-4-22 17:02*

太牛了 哥们

## 回复 by 烟花易冷丶 (#31)

*2025-4-22 17:45*

6666

## 回复 by ONewTach (#32)

*2025-4-23 08:44*

666

## 回复 by 呼吸24K纯氧 (#33)

*2025-4-23 09:23*

看看

## 回复 by gusong (#34)

*2025-4-23 09:59*

感谢大佬分享

## 回复 by 蜕无痕 (#35)

*2025-4-23 10:44*

感谢大佬分享

## 回复 by mb_hfpmtthz (#36)

*2025-4-23 10:58*

牛逼大佬

## 回复 by 天水姜伯约 (#37)

*2025-4-23 19:33*

hi大佬，可以分享一下样本吗

## 回复 by 九天666 (#38)

*2025-4-23 19:45*

>
> [天水姜伯约](https://bbs.kanxue.com/user-783210.htm)
>
>  hi大佬，可以分享一下样本吗
>
>

上个文章的样本

## 回复 by whale (#39)

*2025-4-23 20:17*

66666666666

## 回复 by 炒米肉松 (#40)

*2025-4-24 11:46*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by DirtyAngle (#41)

*2025-4-24 14:31*

大几把刘等你逆vmp

## 回复 by 孤恒 (#42)

*2025-4-24 16:29*

牛的

## 回复 by mb_vanjeoof (#43)

*2025-4-25 13:37*

1111

## 回复 by guijian (#44)

*2025-4-25 15:08*

赞一个

## 回复 by pianpu (#45)

*2025-4-25 15:28*

学习

## 回复 by lidongyooo (#46)

*2025-4-27 22:39*

1

## 回复 by 钱钱钱￥ (#47)

*2025-4-28 10:53*

厉害

## 回复 by 怪难听的 (#48)

*2025-4-28 13:49*

666

## 回复 by 自己能 (#49)

*2025-4-28 17:59*

1

## 回复 by mb_hrtasvnf (#50)

*2025-4-28 18:48*

6

## 回复 by 蜡笔晓辉 (#51)

*2025-4-28 21:01*

牛逼大佬

## 回复 by Thehepta (#52)

*2025-4-30 10:25*

1

## 回复 by 哈哥 (#53)

*2025-5-2 14:09*

关于其中的一些判定逻，以及样本中其他函数发生的路径爆炸问题，想和楼主请教，方便加个联系方式吗？

## 回复 by mb_ihwsaggc (#54)

*2025-5-2 20:05*

太牛了

## 回复 by XCicada (#55)

*2025-5-3 06:48*

牛逼大佬

## 回复 by wx_sj_644 (#56)

*2025-5-4 19:06*

好

## 回复 by xxjj678 (#57)

*2025-5-10 20:11*

666

## 回复 by manmade (#58)

*2025-5-10 22:04*

666

## 回复 by adnin (#59)

*2025-5-10 22:53*

学习

## 回复 by wx_ ╰☆L玄V0心E☆╮ (#60)

*2025-5-10 23:41*

感谢分享![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 奋斗der小鸟 (#61)

*2025-5-11 10:31*

牛逼大佬

## 回复 by 菜鸟泽 (#62)

*2025-5-12 15:02*

dalao 666

## 回复 by mb_vgsbqhdw (#63)

*2025-5-13 08:59*

学一下

## 回复 by AAA撒拉嘿 (#64)

*2025-5-14 03:18*

大佬牛逼

## 回复 by blx2024 (#65)

*2025-5-14 08:59*

感谢分享

## 回复 by frankpi (#66)

*2025-5-14 09:51*

636

## 回复 by Ankeys (#67)

*2025-5-15 14:45*

666

## 回复 by mb_ifjlatem (#68)

*2025-5-18 16:47*

太牛了

## 回复 by 大魔头 (#69)

*2025-5-20 11:37*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by Bondzhen (#70)

*2025-5-20 14:27*

666

## 回复 by mb_pesxllvn (#71)

*2025-5-20 14:40*

学习了

## 回复 by 像风一样呢 (#72)

*2025-5-22 19:35*

666666666666

## 回复 by 李小木子 (#73)

*2025-5-24 07:39*

6

## 回复 by mb_tkmdaluu (#74)

*2025-5-24 21:16*

66666666

## 回复 by bluegatar (#75)

*2025-5-25 00:53*

不错啊，看来通用工具来了

## 回复 by Love 2016 (#76)

*2025-5-25 20:17*

666

## 回复 by baichisi (#77)

*2025-5-27 09:28*

666666

## 回复 by yyyyy——— (#79)

*2025-5-27 14:13*

大佬牛逼

## 回复 by 王钺 (#80)

*2025-5-30 18:30*

666

## 回复 by αβγδεξπ (#81)

*2025-6-3 21:10*

![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by 太岁又沐风 (#82)

*2025-6-6 17:54*

66666666666

## 回复 by 慈悲佛祖 (#83)

*2025-6-12 22:20*

学习

## 回复 by 肖安111 (#84)

*2025-6-16 14:23*

6

## 回复 by iBa0 (#85)

*2025-6-16 18:50*

牛逼

## 回复 by godiand (#86)

*2025-6-17 14:33*

6666

## 回复 by dreameriii (#87)

*2025-6-17 17:08*

niu bi !  666

## 回复 by mb_uvyukvot (#88)

*2025-6-18 14:57*

666

## 回复 by mb_ppbnomlu (#89)

*2025-6-18 16:31*

666

## 回复 by spdfdfer (#90)

*2025-6-20 14:16*

666

## 回复 by 寻梦之璐 (#91)

*2025-6-20 17:20*

1

## 回复 by 寻梦之璐 (#92)

*2025-6-20 21:10*

不得不说，你是真牛逼

## 回复 by mb_zgqmhvbn (#93)

*2025-6-21 22:48*

666

## 回复 by mb_otvoasfd (#94)

*2025-6-24 21:29*

太牛了 哥们

## 回复 by xifgg (#95)

*2025-6-25 09:33*

aa

## 回复 by 2445809596 (#96)

*2025-6-25 18:06*

6

## 回复 by 冷瞳 (#97)

*2025-7-2 09:08*

666

## 回复 by mb_pivwkzjg (#98)

*2025-7-2 17:35*

666

## 回复 by 易码 (#99)

*2025-7-2 20:05*

1

## 回复 by mb_yxcltfyb (#100)

*2025-7-6 22:14*

太牛啦

## 回复 by SGSGsama (#101)

*2025-7-10 19:14*

学习

## 回复 by 不想起名字a (#102)

*2025-7-14 14:10*

大佬666![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by mb_zzeuzvsd (#103)

*2025-8-3 23:02*

看看隐藏

## 回复 by 温泉划水鱼 (#104)

*2025-8-4 00:48*

666

## 回复 by mb_bagxbdgw (#105)

*2025-8-5 17:06*

太牛了 哥们

## 回复 by heting0 (#106)

*2025-8-14 18:06*

66666

## 回复 by mb_dcjxxhsk (#107)

*2025-8-14 22:17*

666

## 回复 by 飆汗吉米 (#108)

*2025-8-17 03:34*

6666

## 回复 by mb_donutrph (#109)

*2025-8-22 09:36*

666

## 回复 by homea_qwq (#110)

*2025-8-22 22:05*

666

## 回复 by mb_kvdaxpms (#111)

*2025-8-25 05:47*

666

## 回复 by lookzo (#112)

*2025-8-25 07:23*

666

## 回复 by Obuchi (#113)

*2025-8-27 21:55*

nb

## 回复 by Forgo7ten (#114)

*2025-9-3 15:33*

重建控制流步骤中

在真实块寻找到CSEL指令后 进行patch

```
encoding, count = ks.asm(f'B.{condition} {values[0]}',ins)#生成CSEL指令处patch的汇编
encoding2, count2 = ks.asm(f'B {values[1]}', last_ins_ea)#生成块最后一个地址指令处patch的汇编
```

这里没有兼容CSEL指令就是块的最后一条指令的情况呢？导致这两patch的是一个地方(示例so中的0x41da0地址处)，丢失了一个后继。
然后真实块后面也没有多余的空间去patch了![image](https://bbs.kanxue.com/view/img/face/002.gif)

## 回复 by lotus* (#115)

*2025-9-4 10:35*

6666

## 回复 by wx_kx15923 (#116)

*2025-9-4 10:50*

666

## 回复 by mb_frdfmupk (#117)

*2025-9-6 22:58*

6666

## 回复 by xx_dd_y (#118)

*2025-9-8 18:20*

666

## 回复 by iceblue007007 (#119)

*2025-9-10 22:54*

总算有点眉目了

## 回复 by mb_qsmzglfy (#120)

*2025-9-13 00:37*

太牛了 哥们

## 回复 by 华达州 (#121)

*2025-9-15 17:23*

666

## 回复 by wx_霉菌与野蜂蜜 (#122)

*2025-9-26 14:25*

学习一下

## 回复 by mb_mrjjcxgk (#123)

*2025-9-26 14:32*

66

## 回复 by KanXue_NG (#124)

*2025-9-26 22:37*

学习一波

## 回复 by mb_koixqizd (#125)

*2025-10-5 21:19*

666

## 回复 by Viseris (#126)

*2025-10-7 21:04*

6666

## 回复 by 秃顶 (#127)

*2025-10-8 23:09*

学习

## 回复 by ovo_帮我不c (#128)

*2025-10-9 19:59*

1111

## 回复 by Oo风之恋oO (#129)

*2025-10-19 17:24*

楼主可以出课程吗

## 回复 by mb_jxoikqcy (#130)

*2025-10-20 01:42*

牛大了，看看思路

## 回复 by Mr.He (#131)

*2025-10-30 11:00*

6666

## 回复 by mb_vccutmkx (#132)

*2025-11-2 13:48*

666

## 回复 by wx_五角星 (#133)

*2025-11-4 00:25*

6666666

## 回复 by ldehua (#134)

*2025-11-4 16:02*

牛逼大佬

## 回复 by 不怎么飘逸 (#135)

*2025-11-12 17:44*

66666666666

## 回复 by mb_nulzrwjk (#136)

*2025-11-12 18:24*

666

## 回复 by mb_irhdtnzm (#137)

*2025-11-12 19:03*

1

## 回复 by 嘎嘎真的很棒 (#138)

*2025-11-18 17:27*

牛逼大佬

## 回复 by jasonxgw (#139)

*2025-11-21 11:20*

tql

## 回复 by sanyechon (#140)

*2025-11-24 10:17*

学习了,大佬

## 回复 by Hidd3n_c0d3r (#141)

*2025-11-24 13:12*

![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by mJqalJqN (#142)

*2025-11-25 14:42*

1

## 回复 by 乐活 (#143)

*2025-12-5 10:56*

66666

## 回复 by Heiyiren123 (#144)

*2025-12-8 16:08*

非常有用的资料！

## 回复 by 孤至 (#145)

*2025-12-9 11:25*

666

## 回复 by asuralove (#146)

*2025-12-11 11:30*

666

## 回复 by mb_maiyudos (#147)

*2025-12-11 14:19*

牛逼

## 回复 by wx_小白_266 (#148)

*2025-12-21 19:00*

1

## 回复 by DifierLine (#149)

*2025-12-21 23:48*

谢谢分享

## 回复 by mb_qnsuegcb (#150)

*2025-12-28 13:35*

6666

## 回复 by System's (#151)

*2025-12-28 21:23*

6666

## 回复 by ChiefWin (#152)

*2025-12-29 00:26*

厉害

## 回复 by GeQ1an (#153)

*2025-12-31 15:53*

666666666

## 回复 by 29o (#154)

*2025-12-31 20:33*

学习一下

## 回复 by hanjiefang (#155)

*2026-1-6 17:12*

![image](https://bbs.kanxue.com/view/img/face/062.gif)

## 回复 by 渐渐72 (#156)

*2026-1-6 23:16*

看看。

## 回复 by lost_answer (#157)

*2026-1-9 18:43*

666

## 回复 by l1s00t (#158)

*2026-1-17 15:22*

牛啊 学习！

## 回复 by Superoot (#159)

*2026-1-19 14:36*

学习学习，感谢

## 回复 by ouduomi (#160)

*2026-1-21 14:35*

牛逼大佬

## 回复 by GEKEZYX (#161)

*2026-1-21 17:53*

666

## 回复 by maomaolk (#162)

*2026-1-21 18:13*

牛逼大佬

## 回复 by wx_coddvccwyh (#163)

*2026-1-27 05:40*

77777

## 回复 by wx_ln (#164)

*2026-1-28 18:06*

二哥

## 回复 by mb_npsajqlx (#165)

*2026-1-29 13:50*

666

## 回复 by wx_热血青年 (#166)

*2026-2-5 01:35*

6666666666666

## 回复 by water5555 (#167)

*2026-2-13 14:30*

感谢分享

## 回复 by 黑洞yyh (#168)

*2026-2-25 23:18*

牛逼

## 回复 by Cynosure2sec (#169)

*2026-2-27 14:37*

1111

## 回复 by mb_ysikfhxt (#170)

*2026-3-10 18:20*

1

## 回复 by FindCall (#171)

*2026-3-13 19:01*

666

## 回复 by lixianhuei (#172)

*2026-3-26 16:54*

6666

## 回复 by APlus (#173)

*2026-3-26 17:57*

666

## 回复 by wx_妳还是不懂 (#174)

*2026-4-9 18:04*

这个值得看

## 回复 by 菟丝子 (#175)

*2026-4-21 10:14*

学习

## 回复 by 0x25519 (#176)

*2026-4-22 17:18*

学习学习

## 回复 by 伊苏尔德 (#177)

*2026-5-3 13:22*

6

## 回复 by mb_zatbyyvv (#178)

*2026-5-19 14:12*

牛逼大佬

## 回复 by mb_mrgbywba (#179)

*2026-5-22 21:35*

牛啊

## 回复 by 逆向小龙 (#180)

*2026-5-25 14:33*

111

## 回复 by pan_634488 (#181)

*2026-6-3 16:35*

666

## 回复 by ZXC傲视 (#182)

*2026-6-7 22:39*

学习一下

## 回复 by Hades一KXXY (#183)

*2026-6-7 23:20*

太牛了 哥们

## 回复 by mb_mwcsdecc (#184)

*2026-6-8 13:55*

牛

## 回复 by Da_ (#185)

*2026-6-8 15:31*

牛

## 回复 by ma0ma0 (#186)

*2026-7-12 14:53*

666

## 回复 by mb_degalzhb (#187)

*2026-7-20 10:21*

666
