---
title: '[原创]libEnccryptor vm 还原的探索'
url: https://bbs.kanxue.com/thread-283731.htm
tid: 283731
author: zhuzhu_biu
date: '2024-09-30'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:19:45+08:00'
replies: 25
---

## 前言

vm 对我也说一直是个很有意思的东西,自想还原vmp失败以来,一有机会了解vm都会去看一下,js的vm有很多教程了,对我启发很大,这篇文章的实现方案是我的一种对vm还原的尝试,按照我最开始的想法是要还原到binja的 il 然后去构建一个函数的,但是我懒癌犯了,就不打算继续了(这个绝对是可以这么干的)

由于我懒得搭建 unidbg 去模拟执行(菜是原罪),所以本文全程使用静态分析去完成

此文更多的是解释我的vm还原的代码,以及对还原vm的一种尝试,而不是具体的介绍我代码是怎么写的(如果有需要的话,我可能会出一个视频来讲解怎么实现的代码,打字太累了),我的还原思路应该是可以通用还原别的vm的,我设计的时候也是尽可能的这么做的
阅读此文的前置条件:

1: 对参考文章中内容有一定了解

2: 对angr(符号执行)有一定了解

### 参考文章

 某短视频虚拟机分析和还原 <https://bbs.kanxue.com/thread-282300.htm>

### 主要思路

我是这么划分 vm 解释器的(应改看不清 该函数偏移为 0x2c18)
![alt text](https://bbs.kanxue.com/upload/attach/202409/878476_PEPYFMGX4P7A8NS.png)

本文解释我还原的代码主要围绕调用外部函数
![alt text](https://bbs.kanxue.com/upload/attach/202409/878476_JZH2VBZM4A5A2JD.png)

#### 错误的探索

在我上一篇还原 ollvm 的文章中,我还原的主要思路 是用 angr在分发器设置 负责跳转的寄存器的值,然后angr就可以把这个值对应的执行的过程全部记录下来,一直到下一次重新跳转到分发器,这次分析vm我最开始也是这个思路的,但是后面发现了问题,在ollvm中,我只是为了还原控制流,所以跟代码实际执行逻辑是不相关的,但 vm就不一样了,vm执行的过程是跟前面变量有关的,就导致无法像上次一样去还原
稍微解释下

| 1234567 | `opcode       执行逻辑``0xdfbdfc16     vreg0=3``0xdfbdfc15``0xdfbdfc14``0xdfbdfc13` `if` `(vreg0 > 1) ip+=8``0xdfbdfc12    vreg0+=2``0xdfbdfc11    vreg0+=1` |
|-|-|

这里 opcode 0xdfbdfc13 对应的就是判断虚拟寄存器0的值大于1走一个流程,如果我 使用之前的方法,从分发器设置 opcode的值,然后一直符号执行直到下一次到分发器,就会出现分支(可能会很多),也有的时候,后面的opcode 会使用前面设置的虚拟寄存器,在符号执行后面的opcode的时候,不知道这个值.也会产生分支

#### 正确思路

为了尽可能的减少分支,让符号执行的执行流尽可能的去接近 opcodes 对应的流程,而不包含解释器执行过程产生的分支,就需要用一个state(里面包含内存信息),从解释器开始执行一直到解释完所有opcode

还原出来的伪代码:

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189 | `sp` `=` `sp` `+` `-``0x210``sp` `+` `0x208` `=` `vreg_31``sp` `+` `0x200` `=` `vreg_30``sp` `+` `0x1f8` `=` `vreg_23``sp` `+` `0x1f0` `=` `vreg_22``sp` `+` `0x1e8` `=` `vreg_21``sp` `+` `0x1e0` `=` `vreg_20``sp` `+` `0x1d8` `=` `vreg_19``sp` `+` `0x1d0` `=` `vreg_18``sp` `+` `0x1c8` `=` `vreg_17``sp` `+` `0x1c0` `=` `vreg_16``vreg_16` `=` `x0 \| vreg_7``vreg_11` `=` `x4` `+` `0x10``vreg_12` `=` `x4` `+` `0x0``vreg_2` `=` `vreg_6` `+` `0x0``x3` `=` `vreg_6` `+` `0x8``vreg_5` `=` `vreg_6` `+` `0x10``vreg_7` `=` `vreg_6` `+` `0x18``vreg_8` `=` `vreg_6` `+` `0x20``vreg_9` `=` `vreg_6` `+` `0x28``vreg_18` `=` `x4` `+` `0x18``vreg_10` `=` `vreg_6` `+` `0x30``vreg_6` `=` `vreg_6` `+` `0x38``vreg_19` `=` `x4` `+` `0x8``x1` `=` `vreg_19` `+` `0x76``sp` `+` `0x88` `=` `x1``x4` `=` `vreg_18` `+` `0x0``branch0(先不处理)``未知``x1` `=` `0xffffffffff220000``x1` `=` `x1 \| (``0x5870`  `&` `0xffff``)``x4` `=` `x1` `+` `vreg_6``sp` `+` `0x40` `=` `x4``x4` `=` `x1` `+` `vreg_10``sp` `+` `0x38` `=` `x4``x4` `=` `x1` `+` `vreg_9``sp` `+` `0x30` `=` `x4``x4` `=` `x1` `+` `vreg_8``sp` `+` `0x20` `=` `x4``x4` `=` `x1` `+` `vreg_7``sp` `+` `0x18` `=` `x4``x4` `=` `x1` `+` `vreg_5``sp` `+` `0x0` `=` `x4``vreg_23` `=` `x1` `+` `x3``vreg_30` `=` `x1` `+` `vreg_2``vreg_20` `=` `x0` `+` `0x20``sp` `+` `0x1b0` `=` `vreg_20``vreg_5` `=` `sp` `+` `0x1b0``x4` `=` `x0 \| vreg_30``vreg_25` `=` `x0 \| vreg_16``sp` `+` `0x28` `=` `vreg_11``vreg_31` `=` `ip``+``8``sp` `+` `0x8` `=` `vreg_12``call` `0x2b40``sp` `+` `0x1a8` `=` `vreg_20``vreg_21` `=` `sp` `+` `0x1b8``sp` `+` `0x1a0` `=` `vreg_21``vreg_5` `=` `sp` `+` `0x1a0``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``x4` `=` `x0 \| vreg_23``call` `0x2b5c``vreg_5` `=` `sp` `+` `0x190``vreg_22` `=` `x0` `+` `0x10``sp` `+` `0x190` `=` `vreg_22``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``x4` `=` `x0 \| vreg_30``call` `0x2b40``vreg_5` `=` `sp` `+` `0x180``sp` `+` `0x180` `=` `vreg_22``vreg_17` `=` `sp` `+` `0x198``sp` `+` `0x10` `=` `vreg_17``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``x4` `=` `x0 \| vreg_30``call` `0x2b40``sp` `+` `0x150` `=` `vreg_21``sp` `+` `0x158` `=` `vreg_20``sp` `+` `0x160` `=` `vreg_17``sp` `+` `0x168` `=` `vreg_22``sp` `+` `0x178` `=` `vreg_22``vreg_20` `=` `sp` `+` `0x188``sp` `+` `0x170` `=` `vreg_20``x4` `=` `sp` `+` `0x0``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``vreg_5` `=` `sp` `+` `0x150``call` `0x2b94``vreg_17` `=` `vreg_19` `+` `0x40``vreg_5` `=` `sp` `+` `0x140``sp` `+` `0x140` `=` `vreg_17``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``x4` `=` `x0 \| vreg_30``call` `0x2b40``vreg_30` `=` `sp` `+` `0x48``vreg_22` `=` `sp` `+` `0x148``sp` `+` `0x130` `=` `vreg_19``vreg_23` `=` `sp` `+` `0x8``sp` `+` `0x128` `=` `vreg_23``sp` `+` `0x138` `=` `vreg_30``x4` `=` `sp` `+` `0x18``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``vreg_5` `=` `sp` `+` `0x128``call` `0x2ba8``vreg_5` `=` `sp` `+` `0x110``x1` `=` `x0` `+` `0x40``sp` `+` `0x118` `=` `vreg_30``sp` `+` `0x110` `=` `vreg_22``sp` `+` `0x120` `=` `x1``vreg_30` `=` `sp` `+` `0x20``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``x4` `=` `x0 \| vreg_30``call` `0x2bb8``vreg_5` `=` `sp` `+` `0xf8``x1` `=` `vreg_22` `+` `0x40``sp` `+` `0x100` `=` `vreg_23``sp` `+` `0xf8` `=` `x1``sp` `+` `0x108` `=` `vreg_19``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``x4` `=` `x0 \| vreg_30``call` `0x2bb8``x1` `=` `x0` `+` `32``sp` `+` `0xe8` `=` `vreg_21``vreg_19` `=` `sp` `+` `0x28``sp` `+` `0xe0` `=` `vreg_19``sp` `+` `0xf0` `=` `x1``x4` `=` `sp` `+` `0x30``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``vreg_5` `=` `sp` `+` `0xe0``call` `0x2bc8``x1` `=` `vreg_19` `+` `0x26``vreg_19` `=` `sp` `+` `0x10``vreg_2` `=` `x0` `+` `16``x3` `=` `sp` `+` `0x88``sp` `+` `0xa8` `=` `vreg_19``sp` `+` `0xb0` `=` `vreg_2``sp` `+` `0xb8` `=` `vreg_20``sp` `+` `0xc0` `=` `vreg_22``sp` `+` `0xc8` `=` `vreg_17``sp` `+` `0xd0` `=` `x1``sp` `+` `0xd8` `=` `x3``x1` `=` `sp` `+` `0x88``x1` `=` `x1` `+` `-``0x26``sp` `+` `0x88` `=` `x1``x4` `=` `sp` `+` `0x38``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``vreg_5` `=` `sp` `+` `0xa8``call` `0x2be8``vreg_2` `=` `sp` `+` `0x88``未知``x1` `=` `vreg_2` `+` `0x26``vreg_18` `+` `0x0` `=` `x1``sp` `+` `0xa0` `=` `vreg_21``vreg_5` `=` `sp` `+` `0xa0``vreg_17` `=` `sp` `+` `0x40``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``x4` `=` `x0 \| vreg_17``call` `0x2c04``sp` `+` `0x98` `=` `vreg_19``vreg_5` `=` `sp` `+` `0x98``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``x4` `=` `x0 \| vreg_17``call` `0x2c04``vreg_5` `=` `sp` `+` `0x90``sp` `+` `0x90` `=` `vreg_22``vreg_25` `=` `x0 \| vreg_16``vreg_31` `=` `ip``+``8``x4` `=` `x0 \| vreg_17``call` `0x2c04``vreg_16` `=` `sp` `+` `0x1c0``vreg_17` `=` `sp` `+` `0x1c8``vreg_18` `=` `sp` `+` `0x1d0``vreg_19` `=` `sp` `+` `0x1d8``vreg_20` `=` `sp` `+` `0x1e0``vreg_21` `=` `sp` `+` `0x1e8``vreg_22` `=` `sp` `+` `0x1f0``vreg_23` `=` `sp` `+` `0x1f8``vreg_30` `=` `sp` `+` `0x200``vreg_31` `=` `sp` `+` `0x208``sp` `=` `sp` `+` `0x210` |
|-|-|

#### 对调用外部函数的分析

| 1234567891011 | `246 @ 00003c18  x0 = [x4].q` `//  跳转的 地址``247 @ 00003c1c  x1 = [x5].q` `// 跳转的参数指针``248 @ 00003c20  x24 = x4``249 @ 00003c24  x22 = x5``250 @ 00003c28  call(x20)` `// call_trampline 0x2c0c`  `call_register_trampoline_2c0c:``0 @ 00002c0c  x2 = x0``1 @ 00002c10  x0 = x1``❓   2 @ 00002c14  jump(x2)` |
|-|-|

0x2c0c 是跳板函数,x4 存储的是要调用的函数的地址, x5 存储的是被调用函数的参数指针,每次调用外部函数的时候都会给 x4,x5赋值,在binja中把llil整个函数复制下来,搜索当前函数可以得到x4,x5在哪使用的

| 12 | `00002c50` `void``* x4 = x19 - 0x110``00002c54` `void``* x5 = x19 - 0x108` |
|-|-|

所以只需要给 x19 - 0x110 和 x19 - 0x108 赋值,就可以控制好调用外部函数了,通过阅读 金罡 大佬的文章获得了 vm解释器的内存布局

![alt text](https://bbs.kanxue.com/upload/attach/202409/878476_P83VCWD8JKQABTH.png)

可以看到 x4 就是 vreg4,x5就是 vreg5,所以给 vreg4 vreg5 设置值就可以完成跳转

这里拿出我还原的代码,第一次调用外部函数开始解释

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354 | `sp = sp + -0x210``sp + 0x208 = vreg_31``sp + 0x200 = vreg_30``sp + 0x1f8 = vreg_23``sp + 0x1f0 = vreg_22``sp + 0x1e8 = vreg_21``sp + 0x1e0 = vreg_20``sp + 0x1d8 = vreg_19``sp + 0x1d0 = vreg_18``sp + 0x1c8 = vreg_17``sp + 0x1c0 = vreg_16``vreg_16 = x0 \| vreg_7``vreg_11 = x4 + 0x10``vreg_12 = x4 + 0x0``vreg_2 = vreg_6 + 0x0``x3 = vreg_6 + 0x8``vreg_5 = vreg_6 + 0x10``vreg_7 = vreg_6 + 0x18``vreg_8 = vreg_6 + 0x20``vreg_9 = vreg_6 + 0x28``vreg_18 = x4 + 0x18``vreg_10 = vreg_6 + 0x30``vreg_6 = vreg_6 + 0x38``vreg_19 = x4 + 0x8``x1 = vreg_19 + 0x76``sp + 0x88 = x1``x4 = vreg_18 + 0x0``branch0(先不处理)``未知``x1 = 0xffffffffff220000``x1 = x1 \| (0x5870  & 0xffff)``x4 = x1 + vreg_6``sp + 0x40 = x4``x4 = x1 + vreg_10``sp + 0x38 = x4``x4 = x1 + vreg_9``sp + 0x30 = x4``x4 = x1 + vreg_8``sp + 0x20 = x4``x4 = x1 + vreg_7``sp + 0x18 = x4``x4 = x1 + vreg_5``sp + 0x0 = x4``vreg_23 = x1 + x3``vreg_30 = x1 + vreg_2``vreg_20 = x0 + 0x20``sp + 0x1b0 = vreg_20``vreg_5 = sp + 0x1b0``x4 = x0 \| vreg_30``vreg_25 = x0 \| vreg_16``sp + 0x28 = vreg_11``vreg_31 = ip+8``sp + 0x8 = vreg_12``call 0x2b40` |
|-|-|

>
> tips: 部分虚拟寄存器的做了改变(让分析起来更加方便), x4 就是 vreg4, x5就是 vreg5, sp就是 vreg29,上面伪代码中的 branch 是产生分支的位置,因为我没得打算完整还原所有分支,所以忽略了,未知的位置一般都是设置标志位,也可以忽略
>
>
>

调用的 0x2b40 是被前面的 vm代码计算出来的,我用angr符号执行的时候直接得到了地址,然后记录了下来,先来验证下我符号执行的得到的 伪代码的正确性

x4就是存储的跳转的地址,拿到上面给x4设置值的部分进行分析

| 12345 | `x1 = 0xffffffffff220000``x1 = x1 \| (0x5870  & 0xffff)``vreg_2 = vreg_6 + 0x0``vreg_30 = x1 + vreg_2``x4 = x0 \| vreg_30` |
|-|-|

总的来说,x4是 x0 | vreg_30

x0 = 0, vreg_30 = x1 + vreg_2

vreg_6 根据上面内存布局知道 是 ext_func_list_21d10,这里面全部都是被加密的外部函数地址

| 12345678910111213 | `00021d10` `void``* vm2_external_func_list_21d10 = 0xddd2d0``00021d18` `void``* data_21d18 = 0xddd2ec``00021d20` `void``* data_21d20 = 0xddd324``00021d28` `void``* data_21d28 = 0xddd338``00021d30` `void``* data_21d30 = 0xddd348``00021d38` `void``* data_21d38 = 0xddd358``00021d40` `void``* data_21d40 = 0xddd378``00021d48` `void``* data_21d48 = 0xddd394``00021d50` `void``* data_21d50 = 0xddec54``00021d58` `void``* data_21d58 = 0xddec70``00021d60` `void``* data_21d60 = 0xddec80``00021d68` `void``* data_21d68 = 0xddec90``00021d70` `void``* data_21d70 = 0xdded44` |
|-|-|

vreg_6 + 0x0 = 0xddd2d0

x1是个常数 0xffffffffff225870

| 123 | `>>>` `hex``(``0xffffffffff225870` `+` `0xddd2d0``)``'0x10000000000002b40'``>>>` |
|-|-|

vreg 最大是 8字节 ,所以溢出的不管, 这个值就是 2b40,跟 angr 符号执行得到的结果是对上的

继续分析参数

| 123 | `vreg_20 = x0 + 0x20``sp + 0x1b0 = vreg_20``vreg_5 = sp + 0x1b0` |
|-|-|

vreg_5 最终就等于 0x20

这里看一下 金罡 大佬 还原的汇编

| 1 | `000000D8`  `8320FACB`  `11``(``0x0B``)` `43``(``0x2B``)  BR      x25                     ;LR``=``lr，``-``-``-``-``-``-``> pRandNumber``=``vm2_malloc(``0x20``)` |
|-|-|

汇编中显示的就是 x20,所以基本确定我还原的是没问题的

再来看一下 0x2bd0 对应的 汇编

| 1234567891011 | `0` `@` `00002b40`  `sp` `=` `sp` `-` `0x10``1` `@` `00002b40`  `[sp {__saved_x19}].q` `=` `x19``2` `@` `00002b40`  `[sp` `+` `8` `{__saved_x30}].q` `=` `x30``3` `@` `00002b44`  `x19` `=` `x0``4` `@` `00002b48`  `x0` `=` `[x19].q``5` `@` `00002b4c`  `call(malloc)``6` `@` `00002b50`  `[x19` `+` `8``].q` `=` `x0``7` `@` `00002b54`  `x19` `=` `[sp {__saved_x19}].q``8` `@` `00002b54`  `x30` `=` `[sp` `+` `8` `{__saved_x30}].q``9` `@` `00002b54`  `sp` `=` `sp` `+` `0x10``10` `@` `00002b58`  `<``return``> jump(x30)` |
|-|-|

可以看到函数的返回值是放在了 [x19 + 8].q 的,x19就是上面 的x5

再稍微多拿一点 还原的伪代码

| 1234567891011121314151617 | `vreg_20 = x0 + 0x20``sp + 0x1b0 = vreg_20``vreg_5 = sp + 0x1b0``x4 = x0 \| vreg_30``vreg_25 = x0 \| vreg_16``sp + 0x28 = vreg_11``vreg_31 = ip+8``sp + 0x8 = vreg_12``call 0x2b40``sp + 0x1a8 = vreg_20``vreg_21 = sp + 0x1b8``sp + 0x1a0 = vreg_21``vreg_5 = sp + 0x1a0``vreg_25 = x0 \| vreg_16``vreg_31 = ip+8``x4 = x0 \| vreg_23``call 0x2b5c` |
|-|-|

调用 0x2b5c 准备的参数 x5 是 sp + 0x1a0 = vreg_21 = sp + 0x1b8
调用 0x2b40 准备的参数 x5 是 sp + 0x1b0

0x1b8 = 0x1b0 + 8

所以这里可以看到 调用 0x2b40的参数是 0x2b5c的返回值,逻辑上基本与金罡大佬文章中还原的代码一致(下面的就是,randNumberSize我没写出来,但读者可以试着分析下我还原的伪代码,不难得出也是 0x20)

| 123456789101112 | `000000CC`  `03C021CB`  `11``(``0x0B``)` `07``(``0x07``)  ORR     x4, x0, x30             ;准备跳板目标: base` `+` `0x2B40` `=` `vm2_malloc``000000D0`  `8200C1CB`  `11``(``0x0B``)` `07``(``0x07``)  ORR     x25, x0, x16            ;跳板函数：pCallRegisterTrampolineFunction``000000D4`  `03AB0A17`  `23``(``0x17``)` `-``-``-``-``-``-``-``-`  `STR`     `x11, [sp,` `#0x28]        ;pDstBuffer``000000DC`  `03AC0217`  `23``(``0x17``)` `-``-``-``-``-``-``-``-`  `STR`     `x12, [sp,` `#0x8]         ;>> pScrBuffer``000000D8`  `8320FACB`  `11``(``0x0B``)` `43``(``0x2B``)  BR      x25                     ;LR``=``lr，``-``-``-``-``-``-``> pRandNumber``=``vm2_malloc(``0x20``)``000000E0`  `1BB40A17`  `23``(``0x17``)` `-``-``-``-``-``-``-``-`  `STR`     `x20, [sp,` `#0x1a8]       ;arg2: randNumberSize=0x20``000000E4`  `1BB50E28`  `40``(``0x28``)` `-``-``-``-``-``-``-``-`  `LDR     x21, [sp,` `#0x1b8]       ;取出返回值 pRandNumber``000000E8`  `1BB50817`  `23``(``0x17``)` `-``-``-``-``-``-``-``-`  `STR`     `x21, [sp,` `#0x1a0]       ;arg1: pRandNumber``000000EC`  `1BA50815`  `21``(``0x15``)` `-``-``-``-``-``-``-``-`  `ADD     x5, sp,` `#0x1a0``000000F0`  `8200C1CB`  `11``(``0x0B``)` `07``(``0x07``)  ORR     x25, x0, x16``000000F8`  `02E021CB`  `11``(``0x0B``)` `07``(``0x07``)  ORR     x4, x0, x23             ;准备跳板目标``000000F4`  `8320FACB`  `11``(``0x0B``)` `43``(``0x2B``)  BR      x25                     ;LR``=``lr,` `-``-``-``-``-``-``> generate_rand(pRandNumber,randNumberSize),生成指定``len``长度的随机数` |
|-|-|

更多的对我还原 伪代码的验证就不再进行, 借助我还原的伪代码,去分析 原始opcode的执行过程到底做了什么事,是可以很容易分析出来的

### 开源地址

 <https://github.com/zhuzhu-Top/de_vm>

### 遇到的问题

>
> 本来这部分是准备变写代码的时候边记录的,但是问题太多了,后面就没记录了
>
>
>

1. 分发器开始执行当前opcode,但是 没有进入 ip++
>
> 按照我的理解,所有 opcode 都要从分发器分发,直到 ip++ 位置的
> 实际的时候发现,确实 分发器的位置,捕获到的所有 opcode 都是对的,
> 但是部分 opcode 没有在 ip++ 位置出现
>
>
>

![alt text](https://bbs.kanxue.com/upload/attach/202409/878476_4ZXWUWFQME8RB5P.png)

解决:

>
> 忘记在 extra_stop_points 里面加 ip++位置的偏移,以为会停在那,实际没有,所以 以后想在哪
> 里做处理,都需要添加上去
>
>
>

上传的附件：
- vm内存布局（不一定正确）.xlsx

（12.60kb，52次下载）

---

# 回复

## 回复 by zhuzhu_biu (#2)

*2024-9-30 15:22*

注意：本文并没有介绍具体如何实现的，可以自行阅读源码，或者马上国庆了，我可以搞个群，然后约个时间开个腾讯会议啥的，大家一起交流下vm的还原

## 回复 by 一颗小草 (#3)

*2024-9-30 15:38*

是dy吗

## 回复 by 金罡 (#4)

*2024-9-30 16:51*

好复杂看不懂![image](https://bbs.kanxue.com/view/img/face/85.gif)，学习了。

## 回复 by mb_ldbucrik (#5)

*2024-9-30 17:11*

>
> [金罡](https://bbs.kanxue.com/user-271698.htm)
>
>  好复杂看不懂[em_85]，学习了。
>
>

大佬多写几篇安卓的vmp分析文章吧

## 回复 by mb_ldbucrik (#6)

*2024-9-30 17:13*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zhuzhu_biu](https://bbs.kanxue.com/user-878476.htm)
>
>  注意：本文并没有介绍具体如何实现的，可以自行阅读源码，或者马上国庆了，我可以搞个群，然后约个时间开个腾讯会议啥的，大家一起交流下vm的还原
>
>

期待建个群

## 回复 by zhuzhu_biu (#7)

*2024-9-30 17:19*

>
> [金罡](https://bbs.kanxue.com/user-271698.htm)
>
>  好复杂看不懂[em_85]，学习了。
>
>

大佬别搞，我都是看的你的文章![image](https://bbs.kanxue.com/view/img/face/58.gif)

## 回复 by zhuzhu_biu (#8)

*2024-9-30 17:22*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>
>
>
>
>
>
>  金罡
>
>
>
>  好复杂看不懂[em_85]，学习了。
>
>  大佬多写几篇安卓的vmp分析文章吧
>
>

我还原的思路其实很简单的，而且我觉得是通用的，也可以拿来还原别的vm，但是真要把我全部写代码的过程记录下来，以及为什么这么写，会写很多的，键盘都要敲烂的![image](https://bbs.kanxue.com/view/img/face/85.gif)

## 回复 by 金罡 (#9)

*2024-9-30 20:36*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>
>
>
>
>
>
>  金罡
>
>
>
>  好复杂看不懂[em_85]，学习了。
>
>  大佬多写几篇安卓的vmp分析文章吧
>
>

写文章太费时了

## 回复 by mb_ldbucrik (#10)

*2024-9-30 20:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zhuzhu_biu](https://bbs.kanxue.com/user-878476.htm)
>
>  我还原的思路其实很简单的，而且我觉得是通用的，也可以拿来还原别的vm，但是真要把我全部写代码的过程记录下来，以及为什么这么写，会写很多的，键盘都要敲烂的[em_85]
>
>

可以详细讲讲trace指令这一块，或者难点的几块

## 回复 by zhuzhu_biu (#11)

*2024-9-30 21:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>  可以详细讲讲trace指令这一块，或者难点的几块
>
>

我是符号执行，你可以多了解下

## 回复 by mb_ldbucrik (#12)

*2024-10-1 09:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zhuzhu_biu](https://bbs.kanxue.com/user-878476.htm)
>
>  我是符号执行，你可以多了解下
>
>

好的

## 回复 by mb_ldbucrik (#13)

*2024-10-1 22:18*

>
> [金罡](https://bbs.kanxue.com/user-271698.htm)
>
>  写文章太费时了
>
>

录制视频是不是更直观，更快捷呢![image](https://bbs.kanxue.com/view/img/face/87.gif)

## 回复 by zhuzhu_biu (#14)

*2024-10-2 16:27*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>  录制视频是不是更直观，更快捷呢[em_87]
>
>

我本来就想的是国庆，大家都有时间，开个腾讯会议啥的，录个屏，然后讨论vm还原的技术，可惜，似乎很多人都对vm的还原不太感冒

## 回复 by mb_zfqvurgb (#15)

*2024-10-3 08:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zhuzhu_biu](https://bbs.kanxue.com/user-878476.htm)
>
>  我本来就想的是国庆，大家都有时间，开个腾讯会议啥的，录个屏，然后讨论vm还原的技术，可惜，似乎很多人都对vm的还原不太感冒
>
>

不是不感冒， 是看不懂

## 回复 by zhuzhu_biu (#16)

*2024-10-3 09:34*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_zfqvurgb](https://bbs.kanxue.com/user-990506.htm)
>
>  不是不感冒， 是看不懂
>
>
>

我建议去了解下 js 的 vm, 我有的时候看他们分析js vm的会得到一些启发(能搞js vm的人已经挺多了)

## 回复 by 龟仙人 (#17)

*2024-10-3 20:54*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zhuzhu_biu](https://bbs.kanxue.com/user-878476.htm)
>
>  注意：本文并没有介绍具体如何实现的，可以自行阅读源码，或者马上国庆了，我可以搞个群，然后约个时间开个腾讯会议啥的，大家一起交流下vm的还原
>
>

搞呀，能拉我一个嘛？

## 回复 by flashgg (#18)

*2024-10-4 07:32*

金罡老师的文章刚刚看懂一些，又出现个更难的

## 回复 by zhuzhu_biu (#19)

*2024-10-4 10:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  flashgg](https://bbs.kanxue.com/user-78213.htm)
>
>  金罡老师的文章刚刚看懂一些，又出现个更难的
>
>

没有很难,angr一把梭,vm里面的分支也可以还原的(我开源代码里面只处理的最长的一条分支),然后转换成binja的il,就可以拿到伪c代码(还有多个优化级别的il),分析起来基本就没难度了,但是这么做太费时间了,我只要验证可行就ok了,剩下的会有人知道的

## 回复 by zhuzhu_biu (#20)

*2024-10-4 10:03*

无

## 回复 by zhuzhu_biu (#21)

*2024-10-4 10:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  flashgg](https://bbs.kanxue.com/user-78213.htm)
>
>  金罡老师的文章刚刚看懂一些，又出现个更难的
>
>

放弃了,没啥人弄这个,多读读我的代码吧,写的也不是很难,也是有注释的

## 回复 by 墨穹呢 (#22)

*2024-10-4 11:49*

感谢分享

## 回复 by 养只猫不好么 (#23)

*2024-10-10 13:22*

感谢分享

## 回复 by wx_ ╰☆L玄V0心E☆╮ (#24)

*2024-10-14 21:15*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zhuzhu_biu](https://bbs.kanxue.com/user-878476.htm)
>
>  注意：本文并没有介绍具体如何实现的，可以自行阅读源码，或者马上国庆了，我可以搞个群，然后约个时间开个腾讯会议啥的，大家一起交流下vm的还原
>
>

大佬，国庆都过了，群建好了吗？![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by 陈某人 (#25)

*2024-11-9 15:37*

学习了

## 回复 by mb_ldbucrik (#26)

*2024-11-24 20:43*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zhuzhu_biu](https://bbs.kanxue.com/user-878476.htm)
>
>  我是符号执行，你可以多了解下
>
>

大佬，在trace过程中遇到原子操作，你是如何处理的呢
