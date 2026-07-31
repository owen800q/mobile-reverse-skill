---
title: '[原创]unicorn获取魔改ollvm平坦化控制流'
url: https://bbs.kanxue.com/thread-286992.htm
tid: 286992
author: 孤恒
date: '2025-05-27'
tags: [Android安全, 原创, 逆向分析, 脱壳反混淆, 工具脚本]
crawled_at: '2026-07-31T14:09:37+08:00'
replies: 15
---

现在企业 app 基本上都是 ollvm 平坦化，研究还原这玩意也是大势所趋。废话不多说，这篇文章主要是使用 unicorn 还原 ollvm 的执行流。

## 还原流程

1、获取所有的真实块

2、获取真实块之间的运行流程

3、还原实际工作流程

## 获取真实块

下面是经典老图（来自于<https://security.tencent.com/index.php/blog/msg/112>）

![image](https://bbs.kanxue.com/upload/attach/202505/979192_P9YYUM7BRXJAX9G.png)

这里我们主要关注真实块部分，其余的分发器和处理器都是 ollvm 中间生成的，并不是程序原本的运作流程。上图中的 ollvm 是标准的 ollvm，可以明显的发现所有的真实块都会跳转到预处理器块。但是现在基本都会魔改 ollvm 把这个预处理器给去除，或者说可能有多个预处理器，而且真实块也不一定会跳转到预处理器，也有直接跳转到到主分发器的。

### 获取办法

#### 无预处理器

具体情况具体分析，下图是没有预处理器的 ollvm。

![image](https://bbs.kanxue.com/upload/attach/202505/979192_MT3ADW3X9G8SCXM.png)

这里是所有的真实块都会跳转到主分发器，那么可以考虑将所有主分发器的前驱节点（序言块除外）当做真实块。

这里笔者使用 angr 获取真实块，也可以使用 IDApython 获取。载入文件到 angr，然后使用 angr 的analyses 模块获取 CFG 图，但是 angr 获取到的 CFG 图与 IDA 中看到的有点区别，可以使用<https://github.com/cq674350529/deflat>里的 am_graph.py 转换。

| 12345678910111213141516 | `import` `am_graph``import` `angr``import` `logging` `file_path` `=` `"文件地址"``start_addr` `=` `0x19D870` `#需要分析函数的起始地址` `project` `=` `angr.Project(file_path, load_options``=``{``'auto_load_libs'``:` `False``})``cfg` `=` `project.analyses.CFGFast(normalize``=``True``, force_complete_scan``=``False``)``base_addr` `=` `project.loader.main_object.mapped_base >>` `12` `<<` `12``target_function` `=` `cfg.functions.get(start_addr)``if` `target_function` `is` `None``:``target_function` `=` `cfg.kb.functions.get_by_addr(base_addr` `+` `start_addr)` `# 转为ida对应的块，angr的块不同``super_gragh` `=` `am_graph.to_supergraph(target_function.transition_graph)` |
|-|-|

接下来是识别所有块的类型

| 123456789101112131415161718192021222324252627282930313233 | `# 真实块``real_node` `=` `[]``real_node_addr` `=` `[]``ret_node` `=` `[]` `for` `node` `in` `super_gragh.nodes():``# 入度为0的是序言块``if` `super_gragh.in_degree(node)` `=``=` `0``:``prologue_node` `=` `node` `# 出度为0的是返回块``if` `super_gragh.out_degree(node)` `=``=` `0``:``ret_node.append(node)` `# 序言块后面的是主分发器``main_dispatcher_node` `=` `list``(super_gragh.successors(prologue_node))[``0``]` `# 遍历主分发器的前驱节点``for` `node` `in` `super_gragh.predecessors(main_dispatcher_node):``if` `node.addr !``=` `prologue_node.addr:``real_node.append(node)``real_node_addr.append(node.addr` `-` `base_addr)` `# 检查返回块数量` `if` `len``(ret_node) >` `1``:``ret_node` `=` `list``(super_gragh.predecessors(ret_node[``0``]))[``0``]``else``:``ret_node` `=` `ret_node[``0``]` `print``(``"序言块："``, prologue_node.addr` `-` `base_addr)``print``(``"返回块："``, ret_node.addr` `-` `base_addr)``print``(``"真实块："``, real_node_addr)``print``(``"主分发器："``, main_dispatcher_node.addr` `-` `base_addr)` |
|-|-|

这里的返回块判断后使用前驱节点是考虑到出度为 0 的返回块除了 ret 外还有堆栈检查

![image](https://bbs.kanxue.com/upload/attach/202505/979192_V3T2PES4A7NXZ7C.png)

如果没有堆栈检查的情况，返回块只有一个，这里返回块的前驱节点是子分发器，不能使用。

![image](https://bbs.kanxue.com/upload/attach/202505/979192_Q9KTCA94REQD7VD.png)

#### 有预处理器

下面这个里面看起来是有三个预处理器，而且真实块也不一定会跳转到预处理器，也可能是跳转到主分发器。

![image](https://bbs.kanxue.com/upload/attach/202505/979192_J5PXCB92G54QJNK.png)

这里通过观察其实可以发现以下特征：

主分发器的特征是入度很多，出度为 2（分到两个子分发器中）

子分发器的特征是入度为 1，出度为 2

预处理器的特征是入度大于 2，出度为 1（跳转到主分发器）

返回块的特征是没有出度

序言块的特征是没有入度，也不用分析，就在函数起始位置

真实块的特征是入度为 1，出度为 1

真实块里面也不一定是真正的程序流程使用到的指令，但是可以知道入度为 1，出度为 1 这个特征里面一定会包含真正的流程。根据这个特征，稍微修改一下上面的脚本即可。

| 12345678910111213141516171819202122232425262728293031323334353637 | `real_node` `=` `[]``real_node_addr` `=` `[]``preprocessor_node` `=` `[]``preprocessor_node_addr` `=` `[]``ret_node` `=` `[]``for` `node` `in` `super_gragh.nodes():``# 入度为0的是序言块``if` `super_gragh.in_degree(node)` `=``=` `0``:``prologue_node` `=` `node` `# 出度为0的是返回块``if` `super_gragh.out_degree(node)` `=``=` `0``:``ret_node.append(node)` `# 出度为1，入度为1的是真实块``if` `super_gragh.in_degree(node)` `=``=` `1` `and` `super_gragh.out_degree(node)` `=``=` `1``:``real_node.append(node)``real_node_addr.append(node.addr` `-` `base_addr)` `# 入度大于1，出度等于1的是预处理器``if` `super_gragh.in_degree(node) >` `1` `and` `super_gragh.out_degree(node)` `=``=` `1``:``preprocessor_node.append(node)``preprocessor_node_addr.append(node.addr` `-` `base_addr)` `# 序言块的后继节点是主分发器``main_dispatcher_node` `=` `list``(super_gragh.successors(prologue_node))[``0``]` `# 从预处理器列表中去除主分发器``if` `main_dispatcher_node` `in` `preprocessor_node:``preprocessor_node.remove(main_dispatcher_node)``preprocessor_node_addr.remove(main_dispatcher_node.addr` `-` `base_addr)` `# 判断是否有堆栈检查``if` `len``(ret_node) >` `1``:``ret_node` `=` `list``(super_gragh.predecessors(ret_node[``0``]))[``0``]``else``:``ret_node` `=` `ret_node[``0``]` |
|-|-|

自此拿到所有的真实块

## 获取控制流

这里使用 unicorn 模拟执行来拿到真实块之间的执行流。为什么不用 angr？（有可能是我太菜了不会用）因为笔者在使用 angr 进行还原时，会被 angr 的符号变量干扰。例如图中的第一个分支：

![image](https://bbs.kanxue.com/upload/attach/202505/979192_ARUJXVEDFP7UXV6.png)

使用 angr 模拟执行时，由于没有写入函数参数，这些参数在 angr 中会以符号变量进行表示，在后面某处的分发器时 angr 会自行生成两个状态机，但是这样子会干扰到分析流程，因为不只是真实块中的分支，其他块中的分支也会生成多个状态机。使用 unicorn 时可以直接将 csel 修改成两个分支，其他的可以过滤掉。

### 最初的思路

笔者根据网上的资料，从最初的思路是遍历每一个真实块，通过模拟执行拿到真实块的后继块，如果真实块中含有 csel 指令则可以认为含有判断分支，即后继块会有两个。因为真实块的末尾会更新主分发器所使用的索引，这个索引必定可以找到下一个真实块。但是在具体分析中发现序言块中含有两个 csel 指令。

![image](https://bbs.kanxue.com/upload/attach/202505/979192_YTGNQ84KEK6ADAJ.png)

除此之外，笔者发现用于主分发器的索引存在于 x28 寄存器中，而在当前真实块里面没有对 x28 寄存器进行写入的操作。

![image](https://bbs.kanxue.com/upload/attach/202505/979192_XWE9T9AMEG5Q6E2.png)

综上来说，通过遍历每一个真实块来获取后继块的方法无法在这里使用。

### 使用 BFS

在上文的分析中，可以知道想要还原控制流需要在每个真实块执行后保存当前状态，包括寄存器和内存。这种重新构建每一个真实块的控制流可以想象成有向图，deepseek 向笔者推荐了 BFS 算法（广度优先算法），相比于 DFS 算法（深度优先算法），DFS 算法可能会在执行过程中遇到循环导致无法跳出等问题。

在上文获取到真实块之后，还需要把返回块也放入到真实块列表中，然后为了下文所需要，还要拿到真实块中的地址和大小。

| 123456789 | `real_node_addr.append(prologue_node.addr` `-` `base_addr)``real_node_addr.append(ret_node.addr` `-` `base_addr)``real_node.append(prologue_node)``real_node.append(ret_node)``print``(``"所有块："``, real_node_addr)` `#输出地址``real_node_new` `=` `[]``for` `node` `in` `real_node:``real_node_new.append([node.addr` `-` `base_addr, node.size])``print``(``"所有块："``, real_node_new)``#输出地址和大小` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202505/979192_TH3SX6GM69KY4VG.png)

#### 初始化 unicorn

unicorn 不同于 angr，该模拟器只能模拟 cpu 指令，并且需要自行配置内存。

| 12345678910111213141516 | `BASE` `=` `0x400000``SIZE` `=` `0x100000000``PATH` `=` `"文件路径"``STACK_BASE` `=` `0``STACK_SIZE` `=` `0x1000` `def` `read(name):``with` `open``(name,` `'rb'``) as f:``return` `f.read()`  `def` `main():``mu` `=` `Uc(UC_ARCH_ARM64, UC_MODE_LITTLE_ENDIAN)``mu.mem_map(BASE, SIZE)``mu.mem_write(BASE, read(PATH))``mu.mem_map(STACK_BASE, STACK_SIZE)``mu.reg_write(UC_ARM64_REG_SP, STACK_BASE` `+` `STACK_SIZE` `-` `4``)` |
|-|-|

这里将文件读取后写入到模拟器内存中，然后再拓展出一个栈以供模拟器使用

#### 编写指令 hook

unicorn 可以使用hook_add 函数添加回调函数对每一次运行指令进行 hook。这里可以使用capstone 模块对指令进行反编译。

| 12345 | `md` `=` `Cs(CS_ARCH_ARM64, CS_MODE_ARM)``def` `hook_code(mu: Uc, address, size, user_data):``code` `=` `mu.mem_read(address, size)``for` `insn` `in` `md.disasm(code, address):``...` |
|-|-|

当指令是 csel 时进行处理，并且如果 csel 指令在真实块中执行的，则解析 csel 指令后面的四个操作数，并保存出两个分支。

| 123456789101112131415161718192021222324252627282930 | `def` `capstone_decode_csel(insn: CsInsn):``operands` `=` `insn.op_str.replace(``' '``, '``').split('``,')``dst_reg` `=` `operands[``0``]``condition` `=` `operands[``3``]``reg1` `=` `operands[``1``]``reg2` `=` `operands[``2``]``return` `dst_reg, reg1, reg2, condition` `def` `save_state(mu :Uc, func_addr):``global` `state_queue_new``state` `=` `{}``state[``'mem'``]` `=` `mu.mem_read(STACK_BASE, STACK_SIZE)``state[``"pc"``]` `=` `mu.reg_read(UC_ARM64_REG_PC)``state[``"reg"``]` `=` `mu.reg_read_batch([i` `for` `i` `in` `range``(``199``,` `228``)])``state[``"sp"``]` `=` `mu.reg_read(UC_ARM64_REG_SP)``state_queue_new.append((state, func_addr))` `if` `insn.mnemonic` `=``=` `'csel'``:``for` `node` `in` `real_node:``if` `insn.address` `-` `BASE >``=` `node[``0``]` `and` `insn.address` `-` `BASE < node[``0``]` `+` `node[``1``]:``pc` `=` `mu.reg_read(UC_ARM64_REG_PC)``mu.reg_write(UC_ARM64_REG_PC, pc` `+` `size)``dst, reg1, reg2, cond` `=` `capstone_decode_csel(insn)``reg1` `=` `mu.reg_read(reg_dict[reg1])``reg2` `=` `mu.reg_read(reg_dict[reg2])``mu.reg_write(reg_dict[dst], reg1)``save_state(mu, user_data[``0``])``mu.reg_write(reg_dict[dst], reg2)``save_state(mu, user_data[``0``])``mu.emu_stop()` |
|-|-|

当指令是 bl、blr 调用函数时，将其跳过

| 12 | `if` `insn.mnemonic` `=``=` `'bl'` `or` `insn.mnemonic` `=``=` `'blr'``:``mu.reg_write(UC_ARM64_REG_PC, address` `+` `size)` |
|-|-|

当运行到真实块时，则记录下来，并更新状态

| 123456789101112131415161718192021 | `def` `update_state(mu :Uc, func_addr, insn: CsInsn, state:``dict``):``global` `state_queue_new``state[``'mem'``]` `=` `mu.mem_read(STACK_BASE, STACK_SIZE)``state[``"pc"``]` `=` `mu.reg_read(UC_ARM64_REG_PC)``state[``"reg"``]` `=` `mu.reg_read_batch([i` `for` `i` `in` `range``(``199``,` `228``)])``state[``"sp"``]` `=` `mu.reg_read(UC_ARM64_REG_SP)``state[``"addr"``]` `=` `state.get(``"addr"``, {})` `# 如果不存在或为 None，初始化为 {}``state[``"addr"``][``hex``(insn.address)]` `=` `state[``"addr"``].get(``hex``(insn.address),` `0``)` `+` `1``# 用于判断是否进入循环的情况，由于可能会跨越多个真实块所以会将所有路径记录下来``if` `state[``"addr"``][``hex``(insn.address)] <` `5``:``state_queue_new.append((state, func_addr))``else``:``return` `if` `insn.address` `-` `BASE` `in` `real_node_addr:``if` `hex``(insn.address` `-` `BASE)` `not` `in` `flow[``hex``(user_data[``0``])]:``flow[``hex``(user_data[``0``])].append(``hex``(insn.address` `-` `BASE))``if` `insn.address` `-` `BASE !``=` `ret_node_addr:``update_state(mu, insn.address` `-` `BASE, insn, user_data[``1``])``# save_state(mu, insn.address - BASE)``mu.emu_stop()` |
|-|-|

这里可以衍生出一个笔者遇到的问题，由于 unicorn 没有单步执行功能，如果在下一次恢复状态后运行的情况下同样会进入该判断然后死循环。这里添加了一个公共变量用于跳过第一条指令进入后续判断流程。

| 123 | `if` `bool_first` `=``=` `False``:``bool_first` `=` `True``break` |
|-|-|

#### 总体思路

首先执行一次函数，无论是遇到分支还是后继块都是保存状态到队列中，然后循环执行队列中的状态，遇到后继块或分支则保存状态到新的队列中，最终执行到返回块，当队列中没有了新的状态则代表完成运行。针对陷入循环的情况，在更新状态时有一次剪枝判断，同时使用了两个队列，一个队列用于运行另一个队列用于保存新的状态，当一个队列执行完之后可以认定为一个轮次，当执行多个轮次后，如果控制流的记录列表没有再更新的情况下可以认为是进入了循环，直接结束。

| 1234567891011121314151617181920212223242526 | `state` `=` `{}``bool_first` `=` `False``end_addr` `=` `BASE` `+` `ret_node_addr``hook_hanle` `=` `mu.hook_add(UC_HOOK_CODE, hook_code, user_data``=``[start_addr, state])``mu.emu_start(BASE` `+` `start_addr, end_addr)``mu.hook_del(hook_hanle)``flow_state, time` `=` `0``,` `0``while` `len``(state_queue_new):``# print(len(state_queue))``if` `len``(state_queue)` `=``=` `0``:``state_queue` `=` `deque(state_queue_new)``state_queue_new.clear()``if` `flow_state` `=``=` `len``(flow):``time` `+``=` `1``if` `time >` `4``:``break``else``:``time` `=` `0``flow_state` `=` `len``(flow)``bool_first` `=` `False``state, func_addr` `=` `state_queue.popleft()``tmp` `=` `[func_addr, state]``hook_hanle` `=` `mu.hook_add(UC_HOOK_CODE, hook_code, user_data``=``tmp)``resume_state(mu, state)``mu.emu_start(state[``'pc'``], end_addr)``mu.hook_del(hook_hanle)` |
|-|-|

结果如下

![image](https://bbs.kanxue.com/upload/attach/202505/979192_W7G3ZQZYMZRD7MH.png)

## 还原控制流

这一部分还没有完成，从网上有的资料来看，基本上都是将 csel 直接修改成

b.{cond} addr

b addr

但是在该样本中，序言块会有两个 csel，并将结果存储下来到了后面的真实块再使用，在后续真实块时如果再改变指令为跳转的话无法与前面的 cmp 对应上。

| 1234567891011121314151617181920212223242526272829303132333435 | `.text:000000000001079C MOV             X19, X5``.text:00000000000107A0 MOV             X24, X4``.text:00000000000107A4 MOVK            W25, #0x5783,LSL#16``.text:00000000000107A8 MOVK            W28, #0x52B7,LSL#16``.text:00000000000107AC BL              sub_1E014``.text:00000000000107B0 MOV             W8, #0xFAA8``.text:00000000000107B4 CMP             X19, #0``.text:00000000000107B8 MOVK            W8, #0x8172,LSL#16``.text:00000000000107BC MOV             W9, #0x42A``.text:00000000000107C0 STR             X19, [SP,#0xC0+var_98]``.text:00000000000107C4 MOVK            W9, #0xE42D,LSL#16``.text:00000000000107C8 MOV             W22, #0x1C6B``.text:00000000000107CC MOV             W23, #0xB8FA``.text:00000000000107D0 MOV             W12, #0x82F1``.text:00000000000107D4 MOV             W20, #0xFAAC``.text:00000000000107D8 MOV             W27, #0xA7A4``.text:00000000000107DC MOV             W26, #0xE01A``.text:00000000000107E0 MOV             W19, #0x4730``.text:00000000000107E4 CSEL            W8, W25, W8, EQ``.text:00000000000107E8 STR             X24, [SP,#0xC0+var_A0]``.text:00000000000107EC CMP             X24, #0``.text:00000000000107F0 MOV             W24, #0x9206``.text:00000000000107F4 MOV             W10, #0x8A6B``.text:00000000000107F8 MOVK            W22, #0x160A,LSL#16``.text:00000000000107FC MOVK            W23, #0xCFF0,LSL#16``.text:0000000000010800 MOVK            W12, #0xA2B4,LSL#16``.text:0000000000010804 MOVK            W20, #0xF6A4,LSL#16``.text:0000000000010808 MOVK            W27, #0x4C1C,LSL#16``.text:000000000001080C MOVK            W26, #0x28EF,LSL#16``.text:0000000000010810 MOVK            W19, #0x6057,LSL#16``.text:0000000000010814 MOVK            W24, #0xA28B,LSL#16``.text:0000000000010818 CSEL            W9, W28, W9, EQ``.text:000000000001081C MOVK            W10, #0x842B,LSL#16``.text:0000000000010820 STR             W8, [SP,#0xC0+var_B8]``.text:0000000000010824 STR             W9, [SP,#0xC0+var_BC]` |
|-|-|

上传的附件：
- am_graph.py

（11.58kb，33次下载）
- get_real_block.py

（2.66kb，33次下载）
- unicorn_ollvm_fla.py

（7.91kb，42次下载）

---

# 回复

## 回复 by wx_御史神风 (#2)

*2025-5-27 18:35*

DFS和BFS都不会死循环的，看处理手法了，比如可以记录分析过的分支，这样就可以跳出循环了；另外unicorn有个上下文保存和恢复的功能的；另外unicorn是可以单步执行的，uc结束运行有三个附加的限制，地址、时间、指令数

## 回复 by 孤恒 (#3)

*2025-5-27 19:10*

>
> [wx_御史神风](https://bbs.kanxue.com/user-907036.htm)
>
>  DFS和BFS都不会死循环的，看处理手法了，比如可以记录分析过的分支，这样就可以跳出循环了；另外unicorn有个上下文保存和恢复的功能的；另外unicorn是可以单步执行的，uc结束运行有三个附加的 ...
>
>

DFS我写出来的路径回溯奇奇怪怪的，处理循环也不知道怎么构思（代码菜狗）。上下文保存选项这个一开始有使用到，后面为了调试方便所以自己实现了一个。至于单步执行我是没找到相关资料![image](https://bbs.kanxue.com/view/img/face/055.gif)。谢谢大佬

## 回复 by wx_御史神风 (#4)

*2025-5-27 19:23*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  孤恒](https://bbs.kanxue.com/user-979192.htm)
>
>  DFS我写出来的路径回溯奇奇怪怪的，处理循环也不知道怎么构思（代码菜狗）。上下文保存选项这个一开始有使用到，后面为了调试方便所以自己实现了一个。至于单步执行我是没找到相关资料[em_055]。谢谢大佬
>
>

emu_start后面还有两个参数，一个是时间限制，一个是指令数限制，默认都是0就没限制

## 回复 by method (#5)

*2025-5-27 19:36*

函数中带有bl怎么处理 的 其中 x0返回值可能会被当成状态 决定下一个分支 对应for

## 回复 by 孤恒 (#6)

*2025-5-27 19:59*

>
> [method](https://bbs.kanxue.com/user-856431.htm)
>
>  函数中带有bl怎么处理 的 其中 x0返回值可能会被当成状态 决定下一个分支 对应for
>
>

bl就直接跳过，不执行内容。x0作为返回值如果用于判断情况也会走cmp,csel流程，除非是x0返回值是ollvm的索引值

## 回复 by 孤恒 (#7)

*2025-5-27 20:01*

>
> [wx_御史神风](https://bbs.kanxue.com/user-907036.htm)
>
>  emu_start后面还有两个参数，一个是时间限制，一个是指令数限制，默认都是0就没限制
>
>

这样子调用的话，我下一次调用会有原来的上下文吗

## 回复 by hacker521 (#8)

*2025-5-27 23:55*

大佬可以加个好友么一起交流？

## 回复 by mb_ldbucrik (#9)

*2025-5-28 08:28*

请问可以提供样本学习吗

## 回复 by 孤恒 (#10)

*2025-5-28 09:54*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>  请问可以提供样本学习吗
>
>

这里放样本出来感觉有点风险

## 回复 by 孤恒 (#11)

*2025-5-28 10:05*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  大佬可以加个好友么一起交流？
>
>

wx：gujiwuyuan369

## 回复 by s626 (#12)

*2025-6-7 13:23*

赞

## 回复 by LotusRain (#13)

*2025-9-1 10:17*

大佬，序言块或者真实块中有多个CSEL的还原方案有思路了吗，这种我感觉开辟出新的地址空间填入指令是一种不太优雅的方案，不知道有没有原地patch的其他思路

## 回复 by 孤恒 (#14)

*2025-9-3 16:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  LotusRain](https://bbs.kanxue.com/user-1045364.htm)
>
>  大佬，序言块或者真实块中有多个CSEL的还原方案有思路了吗，这种我感觉开辟出新的地址空间填入指令是一种不太优雅的方案，不知道有没有原地patch的其他思路
>
>

没有咧，不想动汇编的话，可以尝试从ida伪指令生成中间改，但是没有什么好思路

## 回复 by GhHei (#15)

*2025-9-12 16:43*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  LotusRain](https://bbs.kanxue.com/user-1045364.htm)
>
>  大佬，序言块或者真实块中有多个CSEL的还原方案有思路了吗，这种我感觉开辟出新的地址空间填入指令是一种不太优雅的方案，不知道有没有原地patch的其他思路
>
>

用IDA Hex-Rays Microcode，不用考虑空间问题，随便加减指令，很舒服。

## 回复 by LotusRain (#16)

*2025-9-12 18:12*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  GhHei](https://bbs.kanxue.com/user-1000535.htm)
>
>  用IDA Hex-Rays Microcode，不用考虑空间问题，随便加减指令，很舒服。
>
>

实在没想到不拓展原地址空间的方法(在非真实块上操作也存在一定的风险)，我目前的想法是用add_segm相关的api来加text段，跟你说的是不是一个意思
