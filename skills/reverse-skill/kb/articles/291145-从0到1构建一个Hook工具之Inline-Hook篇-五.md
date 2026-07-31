---
title: '[原创]从0到1构建一个Hook工具之Inline Hook篇（五）'
url: https://bbs.kanxue.com/thread-291145.htm
tid: 291145
author: n_1ng
date: '2026-05-08'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T15:06:59+08:00'
replies: 23
---

## 前言

上一篇把 `PLT Hook` 跑通之后， native hook 能力其实已经能覆盖一批很常见的场景了。但很快就会碰到一个更现实的问题：并不是所有 native 函数调用都会经过导入表，也不是所有我们想接管的目标，都适合用 `PLT Hook` 去处理。

`PLT Hook` 改的是导入调用链，准确地说，是“调用方通过 `PLT/GOT` 去找目标函数”这条路径。
可如果目标函数根本不是一个导入函数，或者它在模块内部是直接跳转，甚至我们就是想改掉这个函数本体的执行入口，那么 `PLT Hook` 就到头了。这时候真正该上场的，就是 `Inline Hook`。文章中有讲的不对的欢迎在评论指出！

项目地址：https://github.com/x1aon1ng/Nook

## 目标

这一篇我希望把下面这几件事讲清楚：

1. `Inline Hook` 的核心原理是什么
2. 当前这套 `arm64 Inline Hook` 是怎么一步步落地的
3. 一次inline hook过程在框架内部经历了哪些步骤
4. 对目标函数hook之后是如何调用原方法的

## 知道这些基础后会更好的理解下文

### 1.ARM64指令集

ARM64 的所有 A64 指令都是固定 32 位，也就是 4 字节，patch 时必须按 4 字节为单位覆盖。

ARM64 的每条指令虽然都是 32 位，但这 32 位并不是一个“整体数值”，而是由若干个 bit 字段组成的。

可以先把它粗略理解成：

```python
[ 操作码区 ][ 寄存器字段 ][ 立即数字段 ][ 条件字段 ]
```

 所以你后面看到类似这样的判断：

```python
  if ((instruction & 0xFC000000u) == 0x14000000u) {
      return Arm64InstructionType::kB;
  }
```

其实是在按 ARM64 文档规定的 opcode 编码方式做匹配。它做的事情本质上就是：用`掩码 0xFC000000` 把高位中和“指令类型”有关的部分保留下来，看看它是不是 `B` 指令对应的固定模式 `0x14000000`

以`B`指令为例，它的 32 位编码格式可以写成：

```python
  31          26 25                             0
  +-------------+--------------------------------+
  |   opcode    |            imm26               |
  +-------------+--------------------------------+

```

其中`opcode` 用来说明“这是一条 `B` 指令”，`imm26` 用来表示跳转偏移

`B` 指令的高 6 位固定是：000101

`B somewhere`它的机器码可能长这样：

```python
000101 xxxxxxxxxxxxxxxxxxxxxxxxxx
```

在当前项目里，最基础的工具函数之一是：

```c
  static uint32_t GetBits32(uint32_t value, uint32_t start, uint32_t end) {
      return (value >> end) & ((1u << (start - end + 1u)) - 1u);
  }
```

它的作用就是从一条 32 位指令里，取出第 start 位到第 end 位之间的那一段 bit 字段。

例如

```python
const uint64_t imm26 = GetBits32(instruction, 25u, 0u);
```

表示取出低 26 位，这正是 ARM64 B/BL 指令里的立即数字段。

顺便提一下ARM64 最常用的是 x0 ~ x30 这 31 个 64 位通用寄存器，在前面的文章中简单提到过函数调用约定的概念，在inline hook中也需要了解这个调用约定。

```python
  - x0 ~ x7：常用于函数参数和返回值。
  - x8：常作间接结果寄存器或系统调用相关用途。
  - x9 ~ x15：临时寄存器。
  - x19 ~ x28：被调用者保存寄存器。
  - x29：通常作为帧指针 fp。
  - x30：链接寄存器 lr，保存返回地址。
  - sp：栈指针。
  - pc：程序计数器，通常不能像普通寄存器那样随意直接操作。

  - 前 8 个整型/指针参数走 x0 ~ x7
  - 返回值一般放在 x0
  - 浮点参数走 v0 ~ v7
  - x29 常作帧指针，x30 存返回地址
```

### 2.PC-relative 指令

ARM64 里有一类非常关键的指令，叫 PC-relative 指令，也就是执行结果依赖当前 PC 地址的指令。比如常见的 adr、adrp、ldr literal 之类，很多都不是“单纯执行当前寄存器计算”，而是会根据指令所在位置去算目标地址。这类指令在原函数入口处执行时没有问题，但如果你把它原封不动搬到 trampoline 里，指令所在位置变了，PC 也变了，最终算出来的地址就可能错掉。

所以 inline hook 不能只做“复制字节”，还必须做“指令重定位”：识别哪些指令依赖PC，再在搬到新地址后重新修正它们。

比如

```python
  adrp x0, some_page
  add  x0, x0, #offset
```

这通常是先拿到某个页基址，再加页内偏移，最终形成完整地址。这种写法在访问全局变量、字符串、GOT 表项时非常常见。问题在于这条指令在原位置执行，算出来的地址是对的，但是一旦搬到 trampoline，PC 变了，结果就可能错。

### 3.trampoline

站在 inline hook 的角度看，trampoline 可以理解成“原函数入口的替身执行区”。它的设计目标不是单纯跳一下，而是同时解决两个问题：1.原函数入口已经被 patch 掉了，旧代码不能直接从原地址开始执行；2.replacement 里通常还需要“继续调用所以，trampoline 的本质就是：把被覆盖掉的原始指令搬到新地址，修正它们，再从那里跳回原函数剩余部分。原逻辑”，所以必须给调用方一个新的、可安全执行的 original 入口。入口被 patch、replacement 仍需调用 original，所以trampoline 里的代码并不是“原样副本”，而是“语义等价副本”，这和上面提到的PC-relative指令有关。

### 4.改内存权限，再刷新指令缓存

inline hook 最后要修改的是代码段内存，而代码段默认通常不是可写的。所以真正 patch 之前，必须先把目标页改成可写，修改完成后再恢复权限。但只改内存权限还不够。ARM 平台还要考虑指令缓存一致性。CPU 可能已经把原来的指令缓存进 I-Cache 里了，如果你只是把内存内容写掉，CPU 仍然可能继续执行旧缓存。所以在 patch 完之后，还必须刷新指令缓存。Nook 会结合 __clear_cache 这一类机制，确保新写入的跳转指令真的能被 CPU 执行到。

### 5.linker、soinfo、call_constructors

linker、soinfo、call_constructors 这几个东西，主要不是为了“实现入口 patch”本身，而是为了实现目标 so 还没加载时先登记，等模块真正进来后再安装。这时候就必须接触动态链接器的加载流程。

linker 指 Android 的动态链接器。它负责把 ELF so 加载进进程，完成这些事情：

```python
  - 映射 so 到内存
  - 解析依赖库
  - 做重定位
  - 解析导入符号
  - 执行构造函数
```

如果我们想要hook某一个so中的函数，但此时该so还没有被加载，我们就必须先知道so是什么时候被加载进来的，因此需要引入linker相关逻辑。

soinfo 可以理解成 linker 内部用来描述一个已加载 so 的对象。它不是标准 ELF 概念，而是 Android linker 自己维护的运行时结果。这个结构里面通常会有：模块路径、基址base、大小、动态段信息等等，我们这里关心的是它能提供“这个模块是谁、它被加载到哪、接下来能不能对它安装 hook”这些信息。

call_constructors 是动态库加载过程中很关键的一步，它的名字已经很直白了，就是“调用构造函数”。之前的文章里面也简单提到过一个 so 被加载时，通常流程不是只把它 mmap 进来就结束了，还会继续做：

```python
  - 重定位
  - 解析依赖
  - 准备运行时状态
  - 最后执行 .init_array / 构造函数
```

call_constructors 就处在这个比较靠后的阶段。

对 hook 框架来说，这个位置很有价值，因为当执行到这里时，通常意味着这个模块已经完成了基本加载，他的内存映射和重定位大多已经可用了。

## 从一个最小例子理解Inline Hook

假设我们有这样一个普通函数：

```python
  int Add(int a, int b) {
      return a + b;
  }
```

现在我们的目标是：当程序调用 Add(1, 2) 时，不再直接进入原函数，而是先进入我们自己的替换函数，在里面打印参数、调用原逻辑、再修改返回值。

从接口语义上，这件事通常会写成这样：

```python
  static int (*orig_Add)(int a, int b) = nullptr;

  int Hook_Add(int a, int b) {
      int ret = orig_Add(a, b);
      return ret + 100;
  }

  void InstallHook() {
      NookInlineHookAddress(
          (void*)Add,
          (void*)Hook_Add,
          (void**)&orig_Add
      );
  }
```

这段代码里最重要的是三个角色：

```python
  - Add：目标函数，也就是要被 hook 的函数。
  - Hook_Add：替换函数，hook 生效后会先执行它。
  - orig_Add：原函数入口，但这里的“原函数入口”并不是 Add 本身，而通常是 trampoline。
```

安装完成后，执行流就会从原来的：

```python
  调用 Add
      -> 直接执行 Add
      -> 返回结果
```

变成

```python
  调用 Add
      -> 先跳到 Hook_Add
      -> Hook_Add 内部调用 orig_Add
      -> orig_Add 进入 trampoline
      -> trampoline 执行被覆盖掉的原始指令
      -> 跳回 Add 剩余部分
      -> 原函数执行结束
      -> 返回到 Hook_Add
      -> Hook_Add 修改结果后再返回
```

也就是说，inline hook 做的并不是“把函数指针换掉”，而是直接改写目标函数入口处的机器码。原来程序一调用 Add，CPU 会从 Add的第一条指令开始执行；而 hook 之后，这个入口已经被 patch 成了一段跳转代码，所以 CPU 一进去就被重定向到 Hook_Add 了。

但问题也随之出现：如果 Add 的前几条指令已经被改写了，那 orig_Add 为什么还能继续执行“原函数”？答案就是 trampoline。

框架在安装 hook 时，会先把 Add 入口处即将被覆盖的那几条原始指令搬到另一块新的可执行内存里，再在那块内存的末尾补一段“跳回 Add + 覆盖长度”的代码。这样，orig_Add 实际指向的就是这段 trampoline。它不是回到 Add 的原始入口，而是先执行“被搬走的前几条指令”，然后再接回原函数后半段。

所以从这个最小例子里，其实已经能看清 inline hook 的本质：

```python
1. 找到目标函数入口。
2. 备份并搬走即将被覆盖的原始指令。
3. 构造 trampoline，保证原逻辑仍然可调用。
4. 在目标函数入口写入跳转，让它先进入 replacement。
5. 把 trampoline 作为 original 返回给调用方。
```

上面的其实是C/C++的视角来看，真正在运行时中，CPU并不知道什么叫orig_Add、Hook_Add，它只认识一条条 ARM64 指令。所以从机器执行的角度看，inline hook 本质上是在改三样东西：

```python
  - 原函数入口处的指令。
  - 一段新申请出来的 trampoline 代码。
  - original 指针最终指向哪里。
```

假设 Add 编译成 ARM64 后，函数开头大致是这样：

```python
  Add:
      stp x29, x30, [sp, #-16]!
      mov x29, sp
      add w0, w0, w1
      ldp x29, x30, [sp], #16
      ret
```

如果需要在这里写入一段“跳到 Hook_Add”的 patch，而假设这个 patch 正好需要 16 字节，那么它就必须覆盖前 4 条指令。覆盖之后，原函数入口就不再是原来的样子了。

hook 安装完成后，Add 的入口逻辑上会变成这样：

```python
  Add:
      ; 跳到 Hook_Add 的 patch
      jump Hook_Add
```

这里的 jump Hook_Add 只是逻辑表达，不一定真的是汇编里单独一条 b Hook_Add。在 ARM64 里，框架为了兼容任意地址，通常不会假设目标地址一定在短跳范围内，而更倾向于构造一种“绝对跳转模板”，比如逻辑上等价于：

```python
  ldr x17, =Hook_Add
  br  x17
```

或者别的等价实现，核心思想只有一个：原函数入口不再执行旧指令，而是立刻把控制流转交给 replacement，这个具体会在后面讲。

这一步做完之后，后续任何对 Add 的调用，都会先进入 Hook_Add。

原本 Add 的前几条指令是：

```python
  stp x29, x30, [sp, #-16]!
  mov x29, sp
  add w0, w0, w1
  ldp x29, x30, [sp], #16
```

现在它们已经被 patch 覆盖掉了。也就是说，如果不做额外处理，原函数逻辑其实已经断了。orig_Add 也就根本不可能存在。

所以必须在 patch 原入口之前，先把这些即将被覆盖的指令搬到别处。这个“别处”就是 trampoline。

逻辑上，trampoline 可能会长成这样：

```python
  trampoline:
      stp x29, x30, [sp, #-16]!
      mov x29, sp
      add w0, w0, w1
      ldp x29, x30, [sp], #16

      jump Add + 16
```

最后这一句 jump Add + 16 的意思是：前面被覆盖掉的 16 字节我已经帮你执行完了，现在回到原函数第 5 条指令继续往下跑。 这样，原函数的执行流就被接起来了。

original 为什么能继续调用原逻辑呢？这时就可以重新看 orig_Add 的意义了，它并不是：

```python
orig_Add = Add;
```

因为 Add 的入口已经被改写成跳到 Hook_Add 了，你如果还把 orig_Add 指向 Add，那它一调用又会重新进入 hook，自然就死循环了。

真正正确的做法是：

```python
orig_Add = trampoline;
```

所以当 Hook_Add 里调用：

```python
int ret = orig_Add(a, b);
```

实际发生的事情是：

```python
  Hook_Add
      -> trampoline
      -> 执行被搬过去的原始指令
      -> 跳回 Add + 覆盖长度
      -> 原函数后半段继续执行
      -> 返回结果
```

## 一次Inline Hook调用链

 先看最短主线：

```python
  NookInlineHookAddress
      -> NookInlineHookInitialize（如果还没初始化）
      -> NookInlineHookInternal::InstallInlineHook
          -> 备份目标入口前 5 条指令
          -> 计算 trampoline 所需空间
          -> AllocateExecutableTrampoline
          -> RelocateArm64InstructionSequence
          -> 在 trampoline 尾部补回跳 patch
          -> ClearInstructionCache(trampoline)
          -> ActivateInlineHookRecord
          -> WriteAbsoluteJumpPatch(target, replacement)
          -> *original = trampoline.address
          -> *hook_handle = handle
```

 如果站在“调用方写代码”的角度，这次 hook 往往是这样发起的：

```python
  void* original = nullptr;
  void* handle = nullptr;

  NookInlineHookAddress(target_address,
                        replacement,
                        &original,
                        &handle);
```

 这里传入的 4 个参数分别是：

```python
  - target_address：目标函数入口地址
  - replacement：替换函数地址
  - original：用于接收“原函数入口”
  - hook_handle：用于接收这次 hook 的管理句柄
```

框架先校验参数是否合法等，最终进入真正的安装函数`InstallInlineHook`

它要完成的事情可以概括成五步：

```python
1. 检查目标地址是否可 hook。
2. 计算入口处需要覆盖多少条指令。
3. 构造 trampoline，保存原始逻辑。
4. 在原函数入口写入跳转到 replacement 的 patch。
5. 保存这次 hook 的状态，标记安装完成。
```

一旦决定要 hook 某个函数，接下来第一件关键事情就是申请 trampoline 内存，用来放“被搬走的原始指令”和后续的回跳代码。这一步就是上面的`AllocateExecutableTrampoline`。他承担了两个角色：1. 作为原入口前半段代码的新执行位置；2. 作为 original 最终暴露给调用方的可调用入口。

接着是重定位原始指令`RelocateArm64InstructionSequence`，这和上面提到的PC-Relative指令有关，他的职责是：

```python
  - 从 target 入口读取将被覆盖的若干条指令。
  - 分析这些指令的类型。
  - 判断它们是否依赖原始 PC，比如adr,adrp等。
  - 如果依赖，就按 trampoline 的新地址重写成等价形式。
  - 把修正后的结果写入 trampoline。
```

当被覆盖的原始指令已经重定位进 trampoline 后，trampoline 还差最后一块拼图，那就是“回跳”。因为 trampoline 只保存了原函数入口前面那一小段代码，它并不包含整个原函数。所以在执行完这几条搬运过去的指令之后，还必须继续回到原函数剩余部分，也就是：

```python
target + overwritten_size
```

这一步通常也是通过跳转 patch 来完成的。所以 trampoline 的完整逻辑其实就是：

```python
  重定位后的原始入口指令
      -> 跳回原函数剩余部分
```

然后才到了改写原入口`WriteAbsoluteJumpPatch`，这里的目标很明确，就是让所有原本进入 target 的执行流，先跳到 replacement。

当入口patch写好后，只要程序调用目标函数，就会先被重定向到 replacement。但是到这还并没有结束，还需要考虑后续的可管理性，比如：

```python
  - 后续能否 unhook
  - 能否避免重复安装
  - 能否找到这次 hook 对应的 trampoline
  - 能否恢复原始入口
```

所以框架还要把这次 hook 的信息登记起来，这就是`ActivateInlineHookRecord`的作用。

 一条 hook record 里通常会包含：

```python
  - target
  - replacement
  - trampoline
  - 原始入口备份
  - 覆盖长度
  - 当前激活状态
```

如果站在调用方角度，一次安装完成后的效果可以概括成这样：

```python
  - target 的入口已经被改写，调用它时会先进 replacement。
  - original 不再指向原始入口，而是指向 trampoline。
  - trampoline 会先执行被覆盖掉的原始指令，再跳回原函数后半段。
  - 所以 replacement 里仍然可以通过 original 调用旧逻辑。
```

 于是执行流从原来的：

```python
  call target
      -> target
      -> return
```

 变成：

```python
  call target
      -> replacement
      -> original
      -> trampoline
      -> target + overwritten_size
      -> return to replacement
      -> return
```

## 具体实现与细节

先从入口`InstallInlineHook`开始，函数签名设计为：

```c
  bool InstallInlineHook(void* target_address,
                         void* replacement,
                         void** original,
                         void** hook_handle)
```

这四个参数正好对应一次 inline hook 的四个核心对象：

```python
  - target_address：要 patch 的目标函数入口
  - replacement：新函数
  - original：返回给调用方的“原函数入口”，实际会指向 trampoline
  - hook_handle：这次 hook 的管理句柄，后面 unhook 要靠它
```

当前实现里，ARM64 入口 patch 固定占 5 条指令，也就是 20 字节

```c
  constexpr size_t kArm64InlineHookPatchWords = 5u;
  constexpr size_t kArm64InlineHookPatchSize = kArm64InlineHookPatchWords * sizeof(uint32_t);
```

并且上面也提到过original 最终拿到的，并不是 `target_address` 本身，而是 `trampoline.address`，因为 `target_address` 后面会被改写成“跳到 `replacement`”的入口 patch，如果还把 `original` 直接指向 `target_address`，那`replacement` 里一调 `original`，就会再次跳回 `replacement`，最后直接死循环。

### 创建InlineHookHandle

先创建 handle，再备份目标入口前 5 条指令，接着它分配一个 InlineHookHandle：

```c
  auto* handle = new (std::nothrow) InlineHookHandle();
  if (handle == nullptr) {
      return false;
  }
  #InlineHookHandle定义
  struct InlineHookHandle {
      InlineHookRecord record;
      TrampolineAllocation trampoline;
  };
```

 然后直接把目标函数入口前 5 条指令拷出来：

```c
  uint32_t original_words[kArm64InlineHookPatchWords] = {};
  std::memcpy(original_words, target_address, sizeof(original_words));
```

这里的 original_words 非常关键，它就是“即将被覆盖掉的原始入口指令”。后面会发生三件事：

```python
  - 用它来构造 trampoline
  - 用它来备份 original code
  - unhook 时再写回去
```

### 申请trampoline空间

```c
  size_t trampoline_words_required = kArm64InlineHookPatchWords;
  for (size_t i = 0; i < kArm64InlineHookPatchWords; ++i) {
      trampoline_words_required += GetArm64RelocatedInstructionLength(original_words[i]) /
                                   sizeof(uint32_t);
  }
```

 这段代码的意思是：

```python
  - 先预留 5 个 word，给 trampoline 尾部的“回跳 patch”
  - 再遍历被覆盖的 5 条原始指令
  - 对每条指令调用 GetArm64RelocatedInstructionLength
  - 把每条指令重定位后需要的长度累计起来
```

也就是说，trampoline 大小不是简单 5 * 4 字节，而是回跳 patch 的长度 + 前 5 条指令各自重定位后的展开长度，这个设计说明一件事：一条 ARM64 指令搬到 trampoline 后，未必还是 4 字节，有可能膨胀。

算完大小以后，才真正分配 trampoline：

```c
  if (!AllocateExecutableTrampoline(trampoline_words_required * sizeof(uint32_t),
                                    &handle->trampoline)) {
      delete handle;
      return false;
  }
```

后面会把重定位后的指令直接写到handle->trampoline的 address 上

```c
auto* trampoline_words = reinterpret_cast<uint32_t*>(handle->trampoline.address);
```

### 把原始入口前 5 条指令重定位进 trampoline

```c
  size_t rewritten_word_count = 0u;
  if (!RelocateArm64InstructionSequence(original_words,
                                        kArm64InlineHookPatchWords,
                                        reinterpret_cast<uintptr_t>(target_address),
                                        reinterpret_cast<uintptr_t>(handle->trampoline.address),
                                        trampoline_words,
                                        trampoline_words_required,
                                        &rewritten_word_count)) {
      FreeExecutableTrampoline(&handle->trampoline);
      delete handle;
      return false;
  }
```

这里传进去的参数含义：

```python
  - original_words：原始 5 条指令
  - kArm64InlineHookPatchWords：就是 5 条
  - target_address：原始代码块起点
  - handle->trampoline.address：重定位后的新地址
  - trampoline_words：输出位置
  - rewritten_word_count：最后到底写了多少条新指令
```

`RelocateArm64InstructionSequence` 的实现分两段。

第一段先预计算每条指令重写后的长度：

```c
  std::vector<size_t> rewritten_lengths(instruction_count, 0u);
  size_t total_output_words = 0u;
  for (size_t i = 0; i < instruction_count; ++i) {
      rewritten_lengths[i] = GetArm64RelocatedInstructionLength(instructions[i]);
      total_output_words += rewritten_lengths[i] / sizeof(uint32_t);
  }
  if (total_output_words > output_capacity_words) {
      return false;
  }
```

这里的含义在于：先不急着改写，而是去计算指令修复之后会膨胀成多长，并存进`rewritten_lengths`

用于后面：

```python
  - 判断某个跳转目标地址 address 是否还落在“原始被搬运的这 5 条指令块内部”
  - 如果不在，直接返回原地址
  - 如果在，就不能再返回原地址了，而是要换算成“它在 trampoline 里的新位置”
```

核心逻辑是：

```c
  const size_t target_index = static_cast<size_t>((address - source_block_start) / sizeof(uint32_t));
  size_t relocated_offset = 0u;
  for (size_t i = 0; i < target_index; ++i) {
      relocated_offset += relocated_instruction_lengths[i];
  }
  return relocated_block_start + relocated_offset;
```

如果原来某条分支跳到“被搬走的第 3 条指令”，那重定位以后，它就不能还跳到原地址了，而要跳到 trampoline 里“第 3 条重写后 指令块”的新地址。

第二段再逐条真正重写：

```c
  for (size_t i = 0; i < instruction_count; ++i) {
      size_t rewritten_words = 0u;
      if (!RewriteWithInternalContext(...)) {
          return false;
      }
      output_offset += rewritten_words;
  }
```

### Relocate到底做了什么

前面我们已经看到，InstallInlineHook 在构造 trampoline 时，关键的一步就是调用：

```c
  RelocateArm64InstructionSequence(original_words,
                                   kArm64InlineHookPatchWords,
                                   reinterpret_cast<uintptr_t>(target_address),
                                   reinterpret_cast<uintptr_t>(handle->trampoline.address),
                                   trampoline_words,
                                   trampoline_words_required,
                                   &rewritten_word_count)
```

其实就是把原来位于 `source_address` 的一段 ARM64 指令，搬到 `relocated_address` 对应的输出区里。

后面真正重写的工作核心：`RewriteWithInternalContext(...)`又是怎么工作的呢？

先做指令类型识别：

```c
  if ((instruction & 0xFC000000u) == 0x14000000u) {
      return Arm64InstructionType::kB;
  }
  if ((instruction & 0xFF000010u) == 0x54000000u) {
      return Arm64InstructionType::kBCond;
  }
  if ((instruction & 0xFC000000u) == 0x94000000u) {
      return Arm64InstructionType::kBl;
  }
  if ((instruction & 0x9F000000u) == 0x10000000u) {
      return Arm64InstructionType::kAdr;
  }
  if ((instruction & 0x9F000000u) == 0x90000000u) {
      return Arm64InstructionType::kAdrp;
  }
  ...
```

它告诉我们：当前项目重点处理的是这些会受位置变化影响的 ARM64 指令：

```python
  - B
  - BL
  - B.cond
  - ADR
  - ADRP
  - LDR literal
  - CBZ/CBNZ
  - TBZ/TBNZ
  - 一些 SIMD / PRFM literal 形式
```

#### B / BL 直接改写成“绝对跳转模板”

 比如无条件跳转和带链接跳转：

```c
  case Arm64InstructionType::kB:
  case Arm64InstructionType::kBl: {
      const uint64_t imm26 = GetBits32(instruction, 25u, 0u);
      uintptr_t target = instruction_address + SignExtend64(imm26 << 2u, 28u);
      target = TranslateAddressIfNeeded(...);
      return EmitAbsoluteBranch(output, ..., target, type == kBl, output_word_count);
  }
```

可以拆成四步理解：

1. 从原指令里把imm26取出来
2. 根据ARM64 B/BL的编码规则，算出原始目标地址
3. 如果这个目标地址其实落在”被搬运的原始5条指令块内部“，就调用TranslateAddressIfNeeded 把它改成 trampoline 内部对应地址
4. 不再保留原始相对跳转，而是直接改写成绝对跳转

由`EmitAbsoluteBranch`生成跳转函数：

```c
  output[0] = 0x58000051u;  // LDR X17, #8
  output[1] = 0x14000003u;  // B #12
  output[2] = low32(target_address);
  output[3] = high32(target_address);
  output[4] = link ? 0xD63F0220u : 0xD61F0220u;  // BLR/BR X17
```

`B` 被重写成 `BR X17`，`BL` 被重写成 `BLR X17`，也就是说，原来靠相对偏移跳转，现在统一变成“先加载绝对地址，再走寄存器跳转”。

#### ADR / ADRP 不再保留原编码，而是改成“加载绝对地址”

```c
  case Arm64InstructionType::kAdr:
  case Arm64InstructionType::kAdrp: {
      if (output_capacity_words < 4u) {
          return false;
      }
      const uint32_t rd = GetBits32(instruction, 4u, 0u);
      const uint64_t immlo = GetBits32(instruction, 30u, 29u);
      const uint64_t immhi = GetBits32(instruction, 23u, 5u);
      uintptr_t target = 0u;
      if (type == Arm64InstructionType::kAdr) {
          target = instruction_address + SignExtend64((immhi << 2u) | immlo, 21u);
      } else {
          target = (instruction_address & 0xFFFFFFFFFFFFF000ull) +
                   SignExtend64((immhi << 14u) | (immlo << 12u), 33u);
      }
      target = TranslateAddressIfNeeded(...);
      output[0] = 0x58000040u | rd;  // LDR Xd, #8
      output[1] = 0x14000003u;       // B #12
      output[2] = static_cast<uint32_t>(target & 0xffffffffu);
      output[3] = static_cast<uint32_t>(target >> 32u);
      *output_word_count = 4u;
      return true;
  }
```

这里做的事情也很清楚：先按ADR或ADRP的编码规则还原它本来要得到的地址，再把这个地址直接塞进字面量里，最后用`LDR Xd, #8`把绝对地址加载到目标寄存器`rd`

#### 条件跳转不是简单复制，而是拆成“短条件跳过 + 绝对跳转”

 以 B.cond 为例：

```c
  case Arm64InstructionType::kBCond: {
      if (output_capacity_words < 6u) {
          return false;
      }
      const uint64_t imm19 = GetBits32(instruction, 23u, 5u);
      uintptr_t target = instruction_address + SignExtend64(imm19 << 2u, 21u);
      target = TranslateAddressIfNeeded(...);
      output[0] = (instruction & 0xFF00001Fu) | 0x40u;  // B.<cond> #8
      output[1] = 0x14000005u;                          // B #20
      output[2] = 0x58000051u;                          // LDR X17, #8
      output[3] = 0xD61F0220u;                          // BR X17
      output[4] = static_cast<uint32_t>(target & 0xffffffffu);
      output[5] = static_cast<uint32_t>(target >> 32u);
      *output_word_count = 6u;
      return true;
  }
```

含义是： `output[0]` 仍然保留原来的条件判断，只是把分支偏移改成很短的 #8

如果条件成立，就跳过 `output[1]`，进入后面的绝对跳转逻辑

如果条件不成立，就执行 `output[1] = B #20`，直接越过整个“绝对跳转块”

 所以重定位后的控制流等价于：

```python
  if (cond) goto target;
  else continue;
```

只是这里的 `goto target` 已经变成了`“加载绝对地址 + BR”`。

`CBZ/CBNZ`、`TBZ/TBNZ`的处理几乎同构：

```c
  #CBZ/CBNZ
  output[0] = (instruction & 0xFF00001Fu) | 0x40u;  // CB(N)Z Rt, #8
  output[1] = 0x14000005u;                          // B #20
  output[2] = 0x58000051u;                          // LDR X17, #8
  output[3] = 0xD61F0220u;                          // BR X17
  output[4] = low32(target);
  output[5] = high32(target);

  #TBZ/TBNZ
  output[0] = (instruction & 0xFFF8001Fu) | 0x40u;  // TB(N)Z Rt, #imm, #8
  output[1] = 0x14000005u;                          // B #20
  output[2] = 0x58000051u;                          // LDR X17, #8
  output[3] = 0xD61F0220u;                          // BR X17
  output[4] = low32(target);
  output[5] = high32(target);
```

#### LDR literal 这类指令会重写成“先取绝对地址，再解引用”

 例如：

```python
  case Arm64InstructionType::kLdrLit32:
  case Arm64InstructionType::kLdrLit64:
  case Arm64InstructionType::kLdrswLit: {
      if (output_capacity_words < 5u) {
          return false;
      }
      const uint32_t rt = GetBits32(instruction, 4u, 0u);
      const uint64_t imm19 = GetBits32(instruction, 23u, 5u);
      const uintptr_t target = instruction_address + SignExtend64(imm19 << 2u, 21u);
      output[0] = 0x58000060u | rt;  // LDR Xt, #12
      if (type == Arm64InstructionType::kLdrLit32) {
          output[1] = 0xB9400000u | rt | (rt << 5u);  // LDR Wt, [Xt]
      } else if (type == Arm64InstructionType::kLdrLit64) {
          output[1] = 0xF9400000u | rt | (rt << 5u);  // LDR Xt, [Xt]
      } else {
          output[1] = 0xB9800000u | rt | (rt << 5u);  // LDRSW Xt, [Xt]
      }
      output[2] = 0x14000003u;  // B #12
      output[3] = static_cast<uint32_t>(target & 0xffffffffu);
      output[4] = static_cast<uint32_t>(target >> 32u);
      *output_word_count = 5u;
      return true;
  }
```

原来的 LDR literal 语义是：以当前 PC 为基准，算出某个 literal 地址，再从那个地址取数据。

重定位后不再依赖当前 PC，而是拆成两步：

```python
  1. LDR Xt, #12 把原 literal 的绝对地址读进 rt
  2. 再用 LDR Wt, [Xt] / LDR Xt, [Xt] / LDRSW Xt, [Xt] 去真正取值
```

#### SIMD literal / PRFM literal

```c
  case Arm64InstructionType::kPrfmLit:
  case Arm64InstructionType::kLdrSimdLit32:
  case Arm64InstructionType::kLdrSimdLit64:
  case Arm64InstructionType::kLdrSimdLit128: {
      if (output_capacity_words < 7u) {
          return false;
      }
      const uint32_t rt = GetBits32(instruction, 4u, 0u);
      const uint64_t imm19 = GetBits32(instruction, 23u, 5u);
      const uintptr_t target = instruction_address + SignExtend64(imm19 << 2u, 21u);
      output[0] = 0xA93F47F0u;  // STP X16, X17, [SP, #-0x10]
      output[1] = 0x58000091u;  // LDR X17, #16
      if (type == Arm64InstructionType::kPrfmLit) {
          output[2] = 0xF9800220u | rt;
      } else if (type == Arm64InstructionType::kLdrSimdLit32) {
          output[2] = 0xBD400220u | rt;
      } else if (type == Arm64InstructionType::kLdrSimdLit64) {
          output[2] = 0xFD400220u | rt;
      } else {
          output[2] = 0x3DC00220u | rt;
      }
      output[3] = 0xF85F83F1u;  // LDR X17, [SP, #-0x8]
      output[4] = 0x14000003u;  // B #12
      output[5] = static_cast<uint32_t>(target & 0xffffffffu);
      output[6] = static_cast<uint32_t>(target >> 32u);
      *output_word_count = 7u;
      return true;
  }
```

 这里的思路是：

```python
  - 先保存临时寄存器现场
  - 把原 literal 地址加载到 X17
  - 再发出对应的 PRFM 或 SIMD LDR
  - 然后恢复寄存器
  - 最后跟上 literal 地址数据
```

#### trampoline 尾部还要手工补一个“跳回原函数”的 patch

```c
  const uintptr_t return_address =
          reinterpret_cast<uintptr_t>(target_address) + kArm64InlineHookPatchSize;
  ...
  trampoline_words[rewritten_word_count + 0u] = 0x58000051u;
  trampoline_words[rewritten_word_count + 1u] = 0x14000003u;
  trampoline_words[rewritten_word_count + 2u] = static_cast<uint32_t>(return_address & 0xffffffffu);
  trampoline_words[rewritten_word_count + 3u] = static_cast<uint32_t>(return_address >> 32u);
  trampoline_words[rewritten_word_count + 4u] = 0xD61F0220u;
```

当 `RelocateArm64InstructionSequence` 完成后，trampoline 里只放好了“被覆盖的前 5 条原始指令的重定位版本”。这还不够，因为执行完它们之后，还要回到原函数剩余部分。

这里和前面的绝对跳转模板是同一套思路：

```python
  - LDR X17, #8
  - B #12
  - 低 32 位地址
  - 高 32 位地址
  - BR X17
```

唯一变化是，这次跳的不是 replacement，而是：

```python
target_address + kArm64InlineHookPatchSize
```

也就是 target + 20，即原函数被覆盖区域之后的地址。

#### 从一个简单的例子理解trampoline

假设目标函数 target 的入口地址是，0x100000

它前 5 条 ARM64 指令是：

```python
  0x100000: stp x29, x30, [sp, #-16]!
  0x100004: mov x29, sp
  0x100008: cbz x0, 0x100018
  0x10000c: bl  0x200000
  0x100010: add w0, w0, #1
```

最终生成的trampoline大概长这样：

```python
  trampoline @ 0x300000

  0x100000: stp x29, x30, [sp, #-16]!
  0x100004: mov x29, sp
  0x100008: cbz x0, 0x100018
  0x10000c: bl  0x200000
  0x100010: add w0, w0, #1

  那么按当前源码思路，生成出来的 trampoline 大致会长成这样：

  trampoline @ 0x300000

  ; 原始第 1 条
  0x300000: stp x29, x30, [sp, #-16]!

  ; 原始第 2 条
  0x300004: mov x29, sp

  ; 原始第 3 条 cbz 的重定位结果
  0x300008: cbz x0, 0x300010
  0x30000c: b   0x300020
  0x300010: ldr x17, =0x100018
  0x300014: br  x17
  0x300018: .word low32(0x100018)
  0x30001c: .word high32(0x100018)

  ; 原始第 4 条 bl 的重定位结果
  0x300020: ldr x17, =0x200000
  0x300024: b   0x300030
  0x300028: .word low32(0x200000)
  0x30002c: .word high32(0x200000)
  0x300030: blr x17

  ; 原始第 5 条
  0x300034: add w0, w0, #1

  ; trampoline 尾部回跳到 target + 20
  0x300038: ldr x17, =0x100014
  0x30003c: b   0x300048
  0x300040: .word low32(0x100014)
  0x300044: .word high32(0x100014)
  0x300048: br  x17
```

#### trampoline 写完后，先刷一次指令缓存

```c
ClearInstructionCache(handle->trampoline.address,
                        (rewritten_word_count + kArm64InlineHookPatchWords) * sizeof(uint32_t));
```

### hook record

接下来框架会先把这次 hook 的关键信息登记进 record:

```c
  ActivateInlineHookRecord(&handle->record,
                           target_address,
                           replacement,
                           handle->trampoline.address,
                           kArm64InlineHookPatchSize,
                           reinterpret_cast<const uint8_t*>(original_words),
                           sizeof(original_words));
```

这里把几个关键信息都塞进 record 里了：

```python
  - target_address：目标函数入口
  - replacement_address：替换函数
  - trampoline_address：trampoline 入口
  - patched_length：被覆盖的长度，当前固定是 20
  - active：标记这条 hook 记录已经处于激活状态
  - original_code：原始入口备份，也就是那 20 字节

  #record结构体
   struct InlineHookRecord {
      void* target_address = nullptr;
      void* replacement_address = nullptr;
      void* trampoline_address = nullptr;
      size_t patched_length = 0u;
      bool active = false;
      std::vector<uint8_t> original_code;
  };
```

### 真正覆盖目标入口

前面的准备都完成后，才来到真正的 patch 动作：

```c
  if (!WriteAbsoluteJumpPatch(target_address, replacement)) {
      FreeExecutableTrampoline(&handle->trampoline);
      delete handle;
      return false;
  }
```

`WriteAbsoluteJumpPatch`这一步会在 `target_address` 处构造一段固定 5 word 的绝对跳转模板：

```c
  patch[0] = 0x58000051u;  // LDR X17, #8
  patch[1] = 0x14000003u;  // B #12
  patch[2] = static_cast<uint32_t>(target & 0xffffffffu);
  patch[3] = static_cast<uint32_t>(target >> 32u);
  patch[4] = 0xD61F0220u;  // BR X17
```

这里的`target`实际上是：

```c
const uintptr_t target = reinterpret_cast<uintptr_t>(replacement);
```

也就是说，入口 patch 干的事情本质上就是：把 `replacement` 的绝对地址塞进模板，然后让 `target_address` 入口一执行就跳到 `replacement`

`WriteAbsoluteJumpPatch` 的真正写入过程是：

```c
  unsigned long old_protect = 0u;
  if (!SetPatchWritable(target_address, sizeof(patch), &old_protect)) {
      return false;
  }
  std::memcpy(target_address, patch, sizeof(patch));
  ClearInstructionCache(target_address, sizeof(patch));
  RestorePatchProtection(target_address, sizeof(patch), old_protect);
```

也就是运行时 patch 的三个关键动作：改权限、写机器码、刷新指令缓存。

安装成功后，original 指向的是 trampoline：

```c
  *original = handle->trampoline.address;
  *hook_handle = handle;
  return true;
```

### Uninstall InlineHook

最后看 `unhook`：

```c
  bool UninstallInlineHook(void* hook_handle) {
      if (hook_handle == nullptr) {
          return false;
      }

      auto* handle = reinterpret_cast<InlineHookHandle*>(hook_handle);
      if (!handle->record.active) {
          return false;
      }

      if (!RestoreOriginalCode(handle->record.target_address, handle->record)) {
          return false;
      }

      ResetInlineHookRecord(&handle->record);
      FreeExecutableTrampoline(&handle->trampoline);
      delete handle;
      return true;
  }
```

 它的执行顺序也很清楚：

```python
    1. 检查 hook_handle 是否为空
    2. 转回 InlineHookHandle*
    3. 检查 record.active 是否为 true
    4. 把 original_code 写回原函数入口
    5. 清空 record
    6. 释放 trampoline
    7. 释放 handle
```

其中真正负责“恢复原入口”的是：`RestoreOriginalCode`。

`RestoreOriginalCode` 会把 `record.original_code` 直接 memcpy 回原函数入口，再刷缓存

```c
  static bool RestoreOriginalCode(void* target_address, const InlineHookRecord& record) {
      if (target_address == nullptr || record.original_code.empty()) {
          return false;
      }

      unsigned long old_protect = 0u;
      if (!SetPatchWritable(target_address, record.original_code.size(), &old_protect)) {
          return false;
      }
      std::memcpy(target_address, record.original_code.data(), record.original_code.size());
      ClearInstructionCache(target_address, record.original_code.size());
      RestorePatchProtection(target_address, record.original_code.size(), old_protect);
      return true;
  }
```

恢复成功之后，源码再调用：

```c
  ResetInlineHookRecord(&handle->record);
  FreeExecutableTrampoline(&handle->trampoline);
  delete handle;
```

这一步意味着：

```python
  - 这条 hook 的状态记录被清空
  - trampoline 内存被释放
  - 整个 InlineHookHandle 生命周期结束
```

### deferred hook

deferred hook 就是为了实现：先把 hook 请求登记下来，等目标模块真正加载到进程后，再自动补装。这套逻辑不是新的 hook 类型，而是给普通 inline hook 外面加了一层“等待模块加载”的调度层。它的本质仍然是：最后把事情落回到 `NookInlineHookAddress -> InstallInlineHook` 这条主线上。

核心就是通过 pending registry、linker 观察器和符号解析，把“暂时无法安装的 symbol hook”转换成“模块加载后自动执行的 address hook”。

首先把这次 deferred 请求放进 pending registry，然后启动模块观察器

```c
  const PendingInlineHookRequest request = {
          module_name,
          symbol_name,
          replacement,
          original,
          hook_handle};
  if (!NookInlineHookInternal::RegisterPendingInlineHook(request)) {
      return NOOK_STATUS_INTERNAL_ERROR;
  }

  const NookStatus observer_status = NookInlineHookInternal::EnsureInlineHookModuleObserverAsync();
```

#### pending registry

entry 里存的是：

```python
  - module_name
  - symbol_name
  - replacement
  - original
  - hook_handle
  - installed
```

 注册逻辑在 pending_inline_hook_registry.cpp:54：

```c
  if (entry.module_name == request.module_name &&
      entry.symbol_name == request.symbol_name &&
      entry.replacement == request.replacement &&
      entry.original == request.original &&
      entry.hook_handle == request.hook_handle) {
      return true;
  }
  ...
  g_pending_inline_hook_registry.push_back(std::move(entry));
```

#### ModuleObserver

核心在于

```python
  - 找到 linker 的 call_constructors
  - 把它 hook 掉
  - 以后每次 so 进来，Nook 都能收到通知
```

上一步登记完请求后，异步启动Observer

```c
  std::lock_guard<std::mutex> lock(g_module_observer_async_mutex);
  if (g_module_observer_async_started) {
      return g_module_observer_async_schedule_status;
  }

  pthread_t thread = 0;
  if (pthread_create(&thread, nullptr, &InitializeInlineHookModuleObserverThreadMain, nullptr) != 0) {
      g_module_observer_async_schedule_status = NOOK_STATUS_INTERNAL_ERROR;
      return g_module_observer_async_schedule_status;
  }

  pthread_detach(thread);
  g_module_observer_async_started = true;
  g_module_observer_async_schedule_status = NOOK_STATUS_OK;
  return g_module_observer_async_schedule_status;
```

`InitializeInlineHookModuleObserverThreadMain`做了：

```c
  constexpr char kLinkerModuleName[] = "linker64";
  constexpr char kLinkerCallConstructorsSymbolLower[] = "__dl__ZN6soinfo17call_constructorsEv";
  constexpr char kLinkerCallConstructorsSymbolUpper[] = "__dl__ZN6soinfo16CallConstructorsEv";
```

明确了观察点在linker的soinfo::call_constructors。

然后先定位自身模块路径

```c
  Dl_info payload_info = {};
  if (dladdr(reinterpret_cast<void*>(&InitializeInlineHookModuleObserverOnce), &payload_info) == 0 ||
      payload_info.dli_fname == nullptr) {
      return;
  }
```

然后拼出一个 probe so 路径：

```c
  g_probe_module_path = JoinSiblingPath(payload_info.dli_fname, kProbeLibraryName);
  g_probe_module_basename = GetBasename(g_probe_module_path);
```

这一步的作用不是安装 hook，而是为后面“扫描 soinfo 内部字段偏移”准备一个已知样本模块。

再往下，真正开始找 `linker`和 `call_constructors`并hook：

```c
  void* linker_handle = xdl_open(kLinkerModuleName, XDL_DEFAULT);

  void* call_constructors_address = xdl_dsym(linker_handle, kLinkerCallConstructorsSymbolLower, nullptr);
  if (call_constructors_address == nullptr) {
      call_constructors_address = xdl_dsym(linker_handle, kLinkerCallConstructorsSymbolUpper, nullptr);
  }

    const bool observer_installed =
          TryInstallObserverHook(call_constructors_address,
                                 reinterpret_cast<void*>(HookedLinkerCallConstructors),
                                 &g_original_linker_call_constructors,
                                 &g_linker_call_constructors_handle);
```

然后主动加载一个自己知道路径和结构的 probe so，借这个过程让 HookedLinkerCallConstructors 先跑一遍，然后在里面扫描出 soinfo 关键字段偏移。

```c
  g_soinfo_scan_requested.store(true, std::memory_order_release);
  void* probe_handle = dlopen(g_probe_module_path.c_str(), RTLD_NOW);
  if (probe_handle != nullptr) {
      dlclose(probe_handle);
  }
  g_soinfo_scan_requested.store(false, std::memory_order_release);
```

它会遍历 soinfo：

```c
  for (size_t offset = 0u; offset < sizeof(uintptr_t) * kSoinfoScanWordCount; offset += sizeof(uintptr_t)) {
      uintptr_t value_0 = *(...);
      uintptr_t value_1 = *(...);
      uintptr_t value_2 = *(...);
      uintptr_t value_5 = *(...);
      uintptr_t value_6 = *(...);
      ......
```

然后拿 probe 模块的 phdr、phnum、dli_fbase、PT_DYNAMIC 地址、basename 等信息做比对，最终推导出：

```python
  - g_soinfo_offset_phdr
  - g_soinfo_offset_phnum
  - g_soinfo_offset_load_bias
  - g_soinfo_offset_name
  - g_soinfo_offset_constructors_called
```

当Observer装上后，后续每次 linker 调 call_constructors，都会先进入Hook逻辑

```c
  const char* module_path = nullptr;
  if (g_soinfo_offsets_ready.load(std::memory_order_acquire) && IsSoinfoLoading(soinfo)) {
      module_path = GetLoadedModulePathFromSoinfo(soinfo);
      if (module_path != nullptr && !g_probe_module_basename.empty() &&
          !EndsWith(module_path, g_probe_module_basename.c_str())) {
          (void)NotifyModuleLoaded(module_path);
      }
  }
```

这一段可以拆成三层理解：

```python
  - 只有当 soinfo 偏移已经准备好时，才能开始真正使用 soinfo。
  - IsSoinfoLoading(soinfo) 用 constructors_called == 0 作为“当前模块还处于构造阶段”的判据。
  - 一旦拿到模块路径且它不是 probe so，就调用 NotifyModuleLoaded(module_path)。
```

也就是说，deferred hook 的真正触发时机，就是某个新 so 进入 call_constructors 这一刻。

最后它会继续调用原始 linker 逻辑。

`NotifyModuleLoaded`最后会调用`TryInstallPendingInlineHooksForModule`扫描 registry收集candidate，然后逐个安装Hook：

```c
  const NookStatus status =
          dependencies.install_symbol_hook(candidate.module_path.c_str(),
                                           candidate.symbol_name.c_str(),
                                           candidate.replacement,
                                           candidate.original,
                                           candidate.hook_handle,
                                           dependencies.context);
  if (status != NOOK_STATUS_OK) {
      continue;
  }
```

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2026-5-9 08:50*

感谢分享

## 回复 by Zepp7289 (#3)

*2026-5-9 09:54*

tql

## 回复 by xingbing (#4)

*2026-5-9 15:24*

感谢分享

## 回复 by 勒LI (#5)

*2026-5-9 16:38*

666

## 回复 by tonykros (#6)

*2026-5-11 12:24*

666

## 回复 by Imxz (#7)

*2026-5-11 15:25*

ql

## 回复 by zzhone (#8)

*2026-5-11 23:37*

66666666

## 回复 by iBa0 (#9)

*2026-5-12 09:52*

111

## 回复 by Crack999 (#10)

*2026-5-12 14:08*

ql

## 回复 by 周凡_693405 (#11)

*2026-5-15 15:35*

666

## 回复 by bbpk (#12)

*2026-5-15 23:21*

666

## 回复 by llpplplp (#13)

*2026-5-16 17:10*

学习学习

## 回复 by wx_Huber Barrientos (#14)

*2026-5-17 00:03*

感谢分享

## 回复 by merryfish (#15)

*2026-5-19 02:36*

nice

## 回复 by mb_vrkpxsoe (#16)

*2026-5-19 19:37*

666

## 回复 by ljfifa2002 (#17)

*2026-5-22 11:30*

非常感谢，学习学习

## 回复 by git_94327axixa518 (#18)

*2026-5-28 19:14*

666

## 回复 by 简单的简单 (#19)

*2026-5-28 23:20*

666

## 回复 by mb_kgneopde (#20)

*2026-6-12 17:23*

666

## 回复 by ulong9527 (#22)

*2026-6-26 09:47*

感谢分享，学习一下

## 回复 by mb_zurizkle (#23)

*2026-6-29 19:05*

快看快看k

## 回复 by wx_kx92911 (#24)

*2026-7-15 09:47*

感谢分析

## 回复 by mb_degalzhb (#25)

*2026-7-15 14:38*

666
