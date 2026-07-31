---
title: '[原创]NDK集成OLLVM模块流程记录'
url: https://bbs.kanxue.com/thread-277728.htm
tid: 277728
author: blx2024
date: '2023-06-23'
tags: [Android安全, 原创, 基础理论, 混淆加固]
crawled_at: '2026-07-31T14:42:55+08:00'
replies: 3
---

>
> 欢迎关注个人的微信公众号《[Android安全工程](http://baihonghua.cn/Android%E5%AE%89%E5%85%A8%E5%B7%A5%E7%A8%8B)》（可点击进行扫码关注）。个人微信公众号主要围绕 Android 应用的安全防护和逆向分析， 分享各种安全攻防手段、Hook 技术、ARM 汇编等 Android 相关的知识。
>
>
>

## 集成流程

>
> 具体的编译NDK的LLVM的流程可参考文章：[编译NDK特定的LLVM版本的流程记录](https://bbs.kanxue.com/thread-277727.htm)
>
>
>

获取 ollvm 混淆部分代码：<https://github.com/isrc-cas/flounder>

1. 复制混淆部分 pass 到 llvm12 中：

| 123 | `flounder``/``llvm``/``include``/``llvm``/``Transforms``/``Obfuscation` `-``> toolchain``/``llvm``-``project``/``llvm``/``include``/``llvm``/``Transforms``/``Obfuscation` `flounder``/``llvm``/``lib``/``Transforms``/``Obfuscation` `-``> toolchain``/``llvm``-``project``/``llvm``/``lib``/``Transforms``/``Obfuscation` |
|-|-|
2. 添加下面这行到 llvm-project\llvm\lib\Transforms\CMakeLists.txt 的第13行:

| 1 | `add_subdirectory(Obfuscation)` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_6R5KUWAMT5PM6QF.png)
3. 添加下面这行到 llvm-project\llvm\lib\Transforms\IPO\CMakeLists.txt 的 73 行：

| 1 | `Obfuscation` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_Z6EFCCU8DBHBPKE.png)
4. 在 `llvm-project\llvm\lib\Transforms\IPO\PassManagerBuilder.cpp` 导入头文件：

| 123456 | `#include "llvm/Transforms/Obfuscation/BogusControlFlow.h"``#include "llvm/Transforms/Obfuscation/Flattening.h"``#include "llvm/Transforms/Obfuscation/Split.h"``#include "llvm/Transforms/Obfuscation/Substitution.h"``#include "llvm/Transforms/Obfuscation/CryptoUtils.h"``#include "llvm/Transforms/Obfuscation/StringObfuscation.h"` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_UEWW8GA8Y589KNY.png)

 在同一个文件的第 93 行：

| 123456789 | `/``/` `Flags` `for` `obfuscation``static cl::opt<std::string> Seed(``"seed"``, cl::init("``"), cl::desc("``seed` `for` `the random"));``static cl::opt<std::string> AesSeed(``"aesSeed"``, cl::init("``"), cl::desc("``seed` `for` `the AES``-``CTR PRNG"));``static cl::opt<``bool``> StringObf(``"sobf"``, cl::init(false), cl::desc(``"Enable the string obfuscation"``));` `static cl::opt<``bool``> Flattening(``"fla"``, cl::init(false), cl::desc(``"Enable the flattening pass"``));``static cl::opt<``bool``> BogusControlFlow(``"bcf"``, cl::init(false), cl::desc(``"Enable bogus control flow"``));``static cl::opt<``bool``> Substitution(``"sub"``, cl::init(false), cl::desc(``"Enable instruction substitutions"``));``static cl::opt<``bool``> Split(``"split"``, cl::init(false), cl::desc(``"Enable basic block splitting"``));``/``/` `Flags` `for` `obfuscation` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_DY4X2PEJ7SV27NG.png)

 在同一个文件的第 569 行：

| 123456 | `//obfuscation related pass``MPM.add(createSplitBasicBlockPass(Split));``MPM.add(createBogusPass(BogusControlFlow));``MPM.add(createFlatteningPass(Flattening));``MPM.add(createStringObfuscationPass(StringObf));``MPM.add(createSubstitutionPass(Substitution));` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_MJQF7YB38FDRQRY.png)
5. 在 `llvm-project\llvm\lib\Transforms\Obfuscation\StringObfuscation.cpp` 文件：

 在第 10 行把 `#include "llvm/IR/CallSite.h"` 改为 `#include "llvm/IR/AbstractCallSite.h"`

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_U2EEKNG9YASHT7J.png)

 在第 15 行加入：

| 1 | `#include "llvm/IR/Instructions.h"` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_77VU63479MGT7KK.png)

 在同一个文件的第 174 处（共三处地方）：

| 12345678 | `LoadInst` `*``ptr_19` `=` `new LoadInst(gvar``-``>getType()``-``>getArrayElementType(),``gvar, "", false, label_for_body);``ptr_19``-``>setAlignment(Align(``8``));``...``LoadInst``*` `int8_20` `=` `new LoadInst(ptr_arrayidx``-``>getType()``-``>getArrayElementType(), ptr_arrayidx, "", false, label_for_body);``int8_20``-``>setAlignment(Align(``1``));``...``void_21``-``>setAlignment(Align(``1``));` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_K4FKW2Z2BRNEXJQ.png)
6. 在 `llvm-project\llvm\lib\Transforms\Obfuscation\Substitution.cpp` 文件的第 215 行：

| 123456789101112131415161718192021 | `// Implementation of a = -(-b + (-c))` `void` `Substitution::addDoubleNeg(BinaryOperator *bo) {` `BinaryOperator *op, *op2 = NULL;` `UnaryOperator *op3, *op4;` `if` `(bo->getOpcode() == Instruction::Add) {` `op = BinaryOperator::CreateNeg(bo->getOperand(0),` `""``, bo);` `op2 = BinaryOperator::CreateNeg(bo->getOperand(1),` `""``, bo);` `op = BinaryOperator::Create(Instruction::Add, op, op2,` `""``, bo);` `op = BinaryOperator::CreateNeg(op,` `""``, bo);` `bo->replaceAllUsesWith(op);` `// Check signed wrap` `//op->setHasNoSignedWrap(bo->hasNoSignedWrap());` `//op->setHasNoUnsignedWrap(bo->hasNoUnsignedWrap());` `}` `else` `{` `op3 = UnaryOperator::CreateFNeg(bo->getOperand(0),` `""``, bo);` `op4 = UnaryOperator::CreateFNeg(bo->getOperand(1),` `""``, bo);` `op = BinaryOperator::Create(Instruction::FAdd, op3, op4,` `""``, bo);` `op3 = UnaryOperator::CreateFNeg(op,` `""``, bo);` `bo->replaceAllUsesWith(op3);` `}` `}` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_B9YF3BS62YA2N48.png)

 在第 319 行（原 299 行）修改 `Substitution::subNeg` 函数

| 123456789101112131415 | `// Implementation of a = b + (-c)` `void` `Substitution::subNeg(BinaryOperator *bo) {` `BinaryOperator *op = NULL;` `if` `(bo->getOpcode() == Instruction::Sub) {` `op = BinaryOperator::CreateNeg(bo->getOperand(1),` `""``, bo);` `op = BinaryOperator::Create(Instruction::Add, bo->getOperand(0), op,` `""``, bo);` `// Check signed wrap` `//op->setHasNoSignedWrap(bo->hasNoSignedWrap());` `//op->setHasNoUnsignedWrap(bo->hasNoUnsignedWrap());` `}` `else` `{` `auto` `op1 = UnaryOperator::CreateFNeg(bo->getOperand(1),` `""``, bo);` `op = BinaryOperator::Create(Instruction::FAdd, bo->getOperand(0), op1,` `""``, bo);` `}` `bo->replaceAllUsesWith(op);` `}` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_49Q3QXR8P9YWP57.png)
7. 在文件 `llvm-project\llvm\lib\Transforms\Obfuscation\BogusControlFlow.cpp`文件 380 添加：

| 1 | `UnaryOperator *op2;` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_25GBCKREDGMAZKC.png)

 在同一个文件的 422 行：

| 1 | `case` `1: op2 = UnaryOperator::CreateFNeg(i->getOperand(0),*var,&*i);` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_9Q6XSP7X9JEW3TK.png)

 在同一个文件的 573 行：

| 12 | `opX =` `new` `LoadInst (x->getType()->getElementType(), (Value *)x,` `""``, (*i));``opY =` `new` `LoadInst (x->getType()->getElementType(), (Value *)y,` `""``, (*i));` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_35CVDCZ9C5XE3WE.png)

 在文件 `llvm-project\llvm\include\llvm\InitializePasses.h` 的第 453 行添加：

| 1 | `void` `initializeFlatteningPass(PassRegistry&);` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_5ZNEP5MWGSJTE5E.png)

 在文件 `llvm-project\llvm\lib\Transforms\Obfuscation\Flattening.cpp` 的 17 行添加：

| 1 | `#include "llvm/InitializePasses.h"` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_T33UE55U9DNYPR8.png)

 在相同文件的 123 修改:

| 1 | `load =` `new` `LoadInst(switchVar->getType()->getElementType(), switchVar,` `"switchVar"``, loopEntry);` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_ZTDW4VARSTCEW9R.png)

 在相同文件的 239 修改：
 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_NSTJWJX9T5ZRKYW.png)

## 混淆效果

`Android.mk`的参数配置(全局)：

| 1 | `LOCAL_CFLAGS` `+``=` `-``mllvm` `-``bcf` `-``mllvm` `-``bcf_loop``=``4` `-``mllvm` `-``bcf_prob``=``100` `-``mllvm` `-``sub` `-``mllvm` `-``sub_loop``=``2` `-``mllvm` `-``fla` `-``mllvm` `-``sobf` `-``mllvm` `-``split` |
|-|-|

指定函数(局部):

| 1 | `int` `binaryInsertionSort() __attribute((__annotate__((``"bcf"``))));` |
|-|-|

 `CMakeLists.txt` 的参数配置(全局)：

| 12345 | `set``(CMAKE_C_FLAGS_RELEASE` `"${CMAKE_C_FLAGS_RELEASE} -mllvm -sub -mllvm -sobf -mllvm -fla "``)``set``(CMAKE_CXX_FLAGS_RELEASE` `"${CMAKE_CXX_FLAGS_RELEASE} -mllvm -sub -mllvm -sobf -mllvm -fla"``)` `set``(CMAKE_C_FLAGS_DEBUG` `"${CMAKE_C_FLAGS_DEBUG} -mllvm -sub -mllvm -sobf -mllvm -fla"` `)``set``(CMAKE_CXX_FLAGS_DEBUG` `"${CMAKE_CXX_FLAGS_DEBUG} -mllvm -sub -mllvm -sobf -mllvm -fla"` `)` |
|-|-|

指定函数混淆（局部）：

| 123456 | `__attribute((__annotate__(``"bcf"``)))``__attribute((__annotate__(``"fla"``)))``__attribute((__annotate__(``"sub"``)))``__attribute((__annotate__(``"split"``)))``__attribute((__annotate__(``"sobf"``)))``void binaryInsertionSort(``int` `arr[],` `int` `n) {}` |
|-|-|

**混淆效果：**

![image](https://bbs.kanxue.com/upload/attach/202306/928718_9H385QQ2AUGK4EB.png)

![image](https://bbs.kanxue.com/upload/attach/202306/928718_Q9K85CRUE6MMV4R.png)

## 总结

这里只是参考网上的帖子对 ollvm 整个源码下载，到编译集成到特定的 NDK 版本的过程做一个学习记录，但具体每个 pass 的性能、具体的防护效果、以及可能存在的问题在这里是暂还没深入考究，这个系列待后续继续待补充完善。

同时这块的源码、以及编译产物因体积较大，读者感兴趣可通过关注微信公众号《Android安全工程》回复关键字 `ollvm` 获取相关下载链接。

## 参考资料

<https://github.com/0x3f97/ollvm-12.x>

<https://github.com/yangyiyu08/ollvm-project>

<https://android.googlesource.com/toolchain/llvm-project>

---

# 回复

## 回复 by 秋狝 (#2)

*2023-6-23 23:13*

感谢分享

## 回复 by 淡定小胖子 (#3)

*2025-2-22 01:09*

感谢????

## 回复 by 淡定小胖子 (#4)

*2025-2-22 20:51*

大佬， 你是在Mac上编译的吗？我在Mac上编译遇到个问题
llvm-project/llvm/include/llvm/Transforms/Obfuscation/CryptoUtils.h:84:2: error: "Unknown endianness of the compilation platform, check this header aes_encrypt.h"
