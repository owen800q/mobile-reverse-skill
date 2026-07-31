---
title: '[原创] 记一次成功的ollvm-fla简单魔改尝试'
url: https://bbs.kanxue.com/thread-287052.htm
tid: 287052
author: 櫬木汐
date: '2025-06-01'
tags: [Android安全, 原创, 混淆加固, 源码框架]
crawled_at: '2026-07-31T14:09:28+08:00'
replies: 4
---

最近在学习ollvm的时候，心血来潮地尝试着自己进行了一些魔改

如果有错误或者讲得不好的地方，欢迎各位大佬来指正

# LLVM14下的ollvm编译

[【清羽】Windows10下编译OLLVM-14.x_ollvm 编译优化后-CSDN博客](https://blog.csdn.net/qq_41923691/article/details/123258565)

参考这位大佬的文章

# 最终效果

原版ollvm的混淆效果

![image-20250601120351090](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)![image](https://bbs.kanxue.com/upload/attach/202506/991035_U56UQ9PZWVADNDR.webp)

魔改后的

![image](https://bbs.kanxue.com/upload/attach/202506/991035_RMM8FWENG5YW6ZV.webp)![image-20250601120510632](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)

d810无法生效

![image](https://bbs.kanxue.com/upload/attach/202506/991035_UTT7NMBQYAEBCRS.webp)![image-20250601124442731](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)

一些更复杂的例子

![o2](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)![image](https://bbs.kanxue.com/upload/attach/202506/991035_KK62SUPE7JU4CCD.webp)

![image](https://bbs.kanxue.com/upload/attach/202506/991035_VG7M8RPKAK73PEW.webp)

![image](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)

# 普通fla流程分析

```
set(OLLVM "-mllvm -fla -mllvm -split -mllvm -split_num=3")add_definitions(${OLLVM})
```

我们先从一个普通的fla样本开始分析，并思考可能的魔改思路

图片中各个块的名称，我都尽量使用ollvm的源码中的变量名，以便后续更方便地阅读和修改代码

![asm](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)![image](https://bbs.kanxue.com/upload/attach/202506/991035_8WEPXF64E3F9NRC.webp)

![image](https://bbs.kanxue.com/upload/attach/202506/991035_HSV2WTCJJ8CBURF.webp)![asm2](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)

流程大概就是，函数从insert块开始，然后进入loopEntry块开始匹配numCase，接着进入到相应的origBB块

在每个origBB块的结尾，都会给switchVar赋一个新的numCase，然后跳转到loopEnd块

loopEnd再跳回loopEntry块中的parentSwDefault块中，在这里，switchVar的值赋给了LoadSwitchVar

然后每一个childSwDefault块，都是对LoadSwitchVar进行匹配，再进行跳转。

# 魔改思路

思考一下我们在进行ollvm去混淆的时候，核心是什么？是寻找所有的origBB块

那么我们又是怎么去寻找origBB块的呢？一般而言，就是去判断当前块的后继，是否为loopEnd块

像普通的ollvm案例，我们只需做一个简单的判断就可以了

![image-20250601101307573](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)![image](https://bbs.kanxue.com/upload/attach/202506/991035_SYWY2RRB76DHQ3D.webp)

那如果我们每个origBB的后继不是loopEnd块，也就是说不单止跳转到parentSwDefault块，也随机跳转到里面的childSwDefault块呢

那么简单地通过后继寻找orignBB就不可行了

# idapython直接修改尝试与问题思考

## 代码

我们先用idapython尝试一下效果

```
import randomrandom.seed(1919810)class BLOCK:    def __init__(self, block, addr):        self.block = block        self.addr = addr        self.successors = []        self.branchType = None    def print_state(self):        print(f"addr {self.addr:x} => ", end='')        if(self.branchType != None):            print(f"  {self.branchType}", end="  ")        for succ in self.successors:            print(f"{succ:x}", end=" ")        print()base = 0x400000REAL_BLOCKS = {}DISPATCH_BLOCKS = {}def get_jmp_block(blocks):    successors = {}    successors_block = {}    for block in blocks:        #print(f"cur_block_addr {block.start_ea:x} => successor")        succ_blocks = list(block.succs())        if(len(succ_blocks) == 1):            if(succ_blocks[0].start_ea not in successors):                successors[succ_blocks[0].start_ea] = 1                successors_block[succ_blocks[0].start_ea] = succ_blocks[0]            else:                successors[succ_blocks[0].start_ea] += 1    for key in successors:        print(hex(key), successors[key])    max_successors_addr = max(successors, key=lambda k: successors[k])    print(hex(max_successors_addr))    return successors_block[max_successors_addr]def get_real_blocks1(blocks, main_dispatcher_block):    real_blocks = []    for block in blocks:        if(main_dispatcher_block.start_ea == block.start_ea):            continue                succ_addrs = []        #print(f"cur_block_addr {block.start_ea:x} => successor")        succ_blocks = list(block.succs())                for succ_block in succ_blocks:            succ_addrs.append(succ_block.start_ea)        if(main_dispatcher_block.start_ea in succ_addrs):            REAL_BLOCKS[block.start_ea] = BLOCK(block, block.start_ea)            real_blocks.append(block)    return real_blocks    def print_real_blocks(blocks):    print("---real_blocks---")    for block in blocks:        print(f"    {block.start_ea:x}")    print("---end---\n")def find_all_real_block(func_ea):    real_blocks = []    blocks = idaapi.FlowChart(idaapi.get_func(func_ea))    #获取主分发块    main_dispatch_block = blocks[1]    jmp_block = get_jmp_block(blocks)    print(f"jmp_block => {jmp_block.start_ea:x}")    #通过判断块的后继，检测是否为真实块    real_blocks = get_real_blocks1(blocks, jmp_block)    print_real_blocks(real_blocks)    #获取所有分发块    dispatcher_blocks = []    for i in blocks:        if(i.start_ea not in list(REAL_BLOCKS.keys()) and i.start_ea not in ret_blocks            and i.start_ea != head_blocks and i.start_ea != jmp_block.start_ea            and i.start_ea != main_dispatch_block.start_ea):            dispatcher_blocks.append(i)    return real_blocks, dispatcher_blocksimport structdef calculate_branch_offset(current_pc, target_address):    """    计算 ARM64 跳转指令的偏移量。    :param current_pc: 当前指令的地址    :param target_address: 跳转目标地址    :return: 偏移量，单位为 4 字节    """    # 计算偏移量（目标地址 - 当前地址） / 4    offset = (target_address - current_pc) // 4        # 确保偏移量在 26 位有符号整数范围内    if offset < -0x2000000 or offset > 0x1FFFFFFF:        raise ValueError("偏移量超出范围，无法表示")        return offsetdef generate_branch_instruction(current_pc, target_address):    """    根据当前地址和目标地址生成 ARM64 跳转指令的机器码。    :param current_pc: 当前指令的地址    :param target_address: 跳转目标地址    :return: 机器码（以字节表示）    """    # 计算偏移量    offset = calculate_branch_offset(current_pc, target_address)    # 生成 B 指令的机器码（imm26 是偏移量）    instruction = 0x14000000  # B 指令的基本操作码    instruction |= (offset & 0x03FFFFFF)  # 设置 26 位偏移量        # 将指令转化为字节    machine_code = struct.pack("<I", instruction)        return machine_codedef patch_jmp(block, addr):    end_addr = block.end_ea - 4    print(f"{block.start_ea:x} {end_addr:x} => {addr:x}")    code = generate_branch_instruction(end_addr, addr)    ida_bytes.patch_bytes(end_addr, code)    print(code)def patch_all(real_blocks, dispatcher_blocks):    for real_block in real_blocks:        #real_block = real_blocks[0]        jmp_addr = random.choice(dispatcher_blocks).start_ea        #jmp_addr = (dispatcher_blocks[random.randint(0, 4)]).start_ea        patch_jmp(real_block, jmp_addr)head_blocks = 0x000000000001E51Cret_blocks = [0x214F8, 0x215B0, 0x215B4, 0x21F50]real_blocks, dispatcher_blocks = find_all_real_block(head_blocks)patch_all(real_blocks, dispatcher_blocks)#print(list(BLOCKS.keys()))
```

可以看到已经生成了更难看的cfg

![QQ图片20250529092553](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)![image](https://bbs.kanxue.com/upload/attach/202506/991035_WN8AQTUEH66FAV2.webp)

## 问题

虽然修改成功，但实际上修改后的程序跑出来的结果是不对的，直接死循环

![asm2](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)![image](https://bbs.kanxue.com/upload/attach/202506/991035_9Y4DDYBJJQGBQJ3.webp)

我们再看回这张图，可以看到在每个origBB的末尾，将numCase赋值到的是switchVar

但在childSwDefault块中，进行判断的是loadSwitchVar值

将switchVar赋值给loadSwitchVar的操作只在parentSwDefault出现

而如果origBB直接跳转到childSwDefault块中，造成的结果将是loadSwitchVar值不变，因此可能会不断地进入一个origBB块造成死循环。

## 解决思路

那么解决方案就有几种

1. 将每个childSwDefault块都修改为判断switchVar的值
2. 在每个childSwDefault块中都添加loadSwitchVar = switchVar的指令

# OLLVM源码修改

有了大概的思路后，我们就可以尝试开始对源码进行修改

## 尝试1 (失败)

先尝试将switch的判断值改为switchVar

查看关键源码

```
 //这里在insert块中，新建了一个i32类型的switchVar变量，然后又添加了一个给他赋值为initNumCase的指令，用于进入第一个origBB  switchVar =      new AllocaInst(Type::getInt32Ty(f->getContext()), 0, "switchVar", insert);  new StoreInst(      ConstantInt::get(Type::getInt32Ty(f->getContext()),                       llvm::cryptoutils->scramble32(0, scrambling_key)),      switchVar, insert);      '''    //添加了loadSwitchVar = switchVar的指令    load = new LoadInst(switchVar->getType()->getElementType(), switchVar, "switchVar", loopEntry);'''//将loadSwitchVar的值设为该switch指令的conditionswitchI = SwitchInst::Create(&*f->begin(), swDefault, 0, loopEntry);    switchI->setCondition(load);
```

我们直接修改为

```
 //这里在insert块中，新建了一个i32类型的switchVar变量，然后又添加了一个给他赋值initNumCase的操作，用于进入第一个origBB  switchVar =      new AllocaInst(Type::getInt32Ty(f->getContext()), 0, "switchVar", insert);  new StoreInst(      ConstantInt::get(Type::getInt32Ty(f->getContext()),                       llvm::cryptoutils->scramble32(0, scrambling_key)),      switchVar, insert);      '''    //添加了loadSwitchVar = switchVar的操作    //load = new LoadInst(switchVar->getType()->getElementType(), switchVar, "switchVar", loopEntry);'''//将loadSwitchVar的值设为该switch指令的conditionswitchI = SwitchInst::Create(&*f->begin(), swDefault, 0, loopEntry);    switchI->setCondition(switchVar);
```

好好，编译运行一波试试，诶诶，怎么出问题了

![wrong1](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)![image](https://bbs.kanxue.com/upload/attach/202506/991035_K6HJEZCVBN8894F.webp)

试了几次，发现必须要添加loadSwitchVar = switchVar，对loadSwitchVar 进行判断，才能做到不报错

SwitchInst::setCondition()传入的参数类型应该为Value

![image-20250601110147744](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)![image](https://bbs.kanxue.com/upload/attach/202506/991035_CUGNW8HHKGZU384.webp)

![image](https://bbs.kanxue.com/upload/attach/202506/991035_URZNY2X4287EJRJ.webp)

最后查看一波IR发现

![image](https://bbs.kanxue.com/upload/attach/202506/991035_CX8B95RYRM9US2N.webp)

这里大概是因为switchVar实质是一个指针，所以必须要先进行一个load的操作，这样又不可避免地在IR中会产生一个新变量

那我们就干脆试一试每个case都加上一个load操作了

![image-20250601110434289](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)

## 尝试2 (成功)

通过上面的尝试，我们发现无法直接在switch的结构中直接对switchVar进行判断，而这里又会引出一个新问题

### 新问题

在源码中，每个origBB的结尾会进行这样一个操作，这是令当前origBB跳转到loopEnd

```
  for (std::vector<BasicBlock *>::iterator b = origBB.begin();       b != origBB.end(); ++b) {    BasicBlock *i = *b;        '''        BranchInst::Create(loopEnd, i);   }
```

在llvm-pass中，该建立跳转的指令为BranchInst::Create，他的含义为，创建一条从InsertAtEnd跳转到IfTrue块的指令

```
static BranchInst *Create(BasicBlock *IfTrue, BasicBlock *InsertAtEnd);
```

而对于他的所有重载，操作的单位都只能是BasicBlock类型

![image-20250601111228854](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)![image](https://bbs.kanxue.com/upload/attach/202506/991035_A6Y87384FBFAR4G.webp)

而一个switchI的类型为SwitchInst，每种case无法被拆为BasicBlock，这样是没有办法跳转过去的

### 解决思路

既然switch结构的问题这么多，那么我们为什么不改用if判断结构？

```
  //创建新的If块列表  std::vector<BasicBlock *> cmpDefaultList;    for(int i = 0; i < origBB.size(); i++) {    cmpDefaultList.push_back(BasicBlock::Create(f->getContext(), "cmpDefault", f, nullptr));  }    int count = 0;    // Put all BB in the switch  for (std::vector<BasicBlock *>::iterator b = origBB.begin();       b != origBB.end(); ++b) {    BasicBlock *i = *b;    ConstantInt *numCase = NULL;    // Move the BB inside the switch (only visual, no code logic)    i->moveBefore(loopEnd);    // Add case to switch    numCase = cast<ConstantInt>(ConstantInt::get(        switchI->getCondition()->getType(),        llvm::cryptoutils->scramble32(switchI->getNumCases(), scrambling_key)));    switchI->addCase(numCase, i);     //这里还是要使用load，不然变编译起来     load = new LoadInst(switchVar->getType()->getElementType(), switchVar, "switchVar", cmpDefaultList[count]);    //在每一个if块中，设置跳转的指令    CmpInst* cmpI = CmpInst::Create(Instruction::ICmp, CmpInst::ICMP_EQ, load, numCase, "CmpInst", cmpDefaultList[count]);    if(count < origBB.size() - 1) {      BranchInst::Create(i, cmpDefaultList[count + 1], cmpI, cmpDefaultList[count]);    } else {      BranchInst::Create(i, loopEnd, cmpI, cmpDefaultList[count]);    }    count++;  }
```

生成一波IR看看

这是原本的Switch结构，为一个大Block

![image](https://bbs.kanxue.com/upload/attach/202506/991035_KXS3NKQ7TD2BD4X.webp)![image-20250601112504815](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)

这是我们新添加的if块

![image-20250601112649890](https://bbs.kanxue.com/upload/attach/202506/3EDUM4BG234CW3W.jpg)![image](https://bbs.kanxue.com/upload/attach/202506/991035_BBU9JZPVFMBMTB8.webp)

那么接下来就是令每个origBB随机跳转到各个if块

```
  count = 0;  std::vector<int> randomArray = generateRandomArray(origBB.size() - 1);  // Recalculate switchVar  for (std::vector<BasicBlock *>::iterator b = origBB.begin();       b != origBB.end(); ++b) {    BasicBlock *i = *b;    ConstantInt *numCase = NULL;    // Ret BB    if (i->getTerminator()->getNumSuccessors() == 0) {      continue;    }    // If it's a non-conditional jump    if (i->getTerminator()->getNumSuccessors() == 1) {      // Get successor and delete terminator        '''        BranchInst::Create(cmpDefaultList[randomArray[count]], i);      count++;      continue;    }    // If it's a conditional jump    if (i->getTerminator()->getNumSuccessors() == 2) {      // Get next cases    '''        BranchInst::Create(cmpDefaultList[randomArray[count]], i);      count++;      continue;    }  }
```

最后将switch块从loopEntry后移除，改为我们的if块

```
  switchI->eraseFromParent();  BranchInst::Create(cmpDefaultList[0], loopEntry);
```

编译成功，可以看到其实编译器最后会帮我们进行优化，现在是直接对switchVar进行判断了

![image](https://bbs.kanxue.com/upload/attach/202506/991035_62ZJX2GT39WNZBC.webp)

## 最终代码

完整的项目贴在github仓库

[twogoat/ollvm-project at 14.x_modified1](https://github.com/twogoat/ollvm-project/tree/14.x_modified1)

# 总结

通过对真实块的后继的修改，实现了ollvm的简单魔改，可以令d810无法生效，当然也只能简单防一下脚本梭哈

这次的尝试令自己对ollvm-fla原理，llvm-pass的操作有了进一步的了解，接下来还会尝试更多的魔改方案

---

# 回复

## 回复 by mb_pesxllvn (#2)

*2025-6-1 22:05*

学习一下

## 回复 by mb_ldbucrik (#3)

*2025-6-2 09:18*

感谢分享

## 回复 by 王钺 (#4)

*2025-6-5 09:37*

感谢分享

## 回复 by Vchase (#5)

*2025-6-5 21:43*

基于CFG识别Origin BB实际已经作用不大，仔细看你会发现原始ollvm存在SwitchVar赋值语句的就是Origin BB，所以仅仅改变CFG的意义没那么大，另外关于if和switch结构的转换可以看看llvm中自带的LowerSwitch Pass（看了你文中if、switch变换想起）
