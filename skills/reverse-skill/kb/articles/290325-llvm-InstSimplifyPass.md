---
title: '[原创]llvm: InstSimplifyPass'
url: https://bbs.kanxue.com/thread-290325.htm
tid: 290325
author: nothing233
date: '2026-03-15'
tags: [Android安全, 原创, 源码框架]
crawled_at: '2026-08-08T10:18:56+00:00'
replies: 11
---

## 前言

简化和移除冗余的指令

## 正文

依旧从入口函数开始:

```cpp
PreservedAnalyses InstSimplifyPass::run(Function &F,
                                        FunctionAnalysisManager &AM) {
  auto &DT = AM.getResult&lt;DominatorTreeAnalysis&gt;(F);    // 支配树
  auto &TLI = AM.getResult&lt;TargetLibraryAnalysis&gt;(F);   // 库信息
  auto &AC = AM.getResult&lt;AssumptionAnalysis&gt;(F);       // 存储函数中的assume指令/调用约定等假设信息
  const DataLayout &DL = F.getDataLayout();             // 平台的类型大小、对齐、端序等
  const SimplifyQuery SQ(DL, &TLI, &DT, &AC);
  bool Changed = runImpl(F, SQ);
  if (!Changed)
    return PreservedAnalyses::all();

  PreservedAnalyses PA;
  PA.preserveSet&lt;CFGAnalyses&gt;();
  return PA;
}
\```

来到 `runImpl`:

```cpp
static bool runImpl(Function &F, const SimplifyQuery &SQ) {
  // S1/S2 用于存储, ToSimplify 指向「本轮需要简化的指令集合」, Next 指向「本轮发现的、下轮需要简化的指令集合」
  SmallPtrSet&lt;const Instruction *, 8&gt; S1, S2, *ToSimplify = &S1, *Next = &S2;
  bool Changed = false;

  // do-while 大循环
  do {
    // 遍历函数中的每个基本块
    for (BasicBlock &BB : F) {
      // 依据支配树跳过不可达基本块, 不可达代码可能包含异常指令, 处理易出错且无意义
      if (!SQ.DT->isReachableFromEntry(&BB))
        continue;

      // 当前基本块中可删除的死指令
      SmallVector&lt;WeakTrackingVH, 8&gt; DeadInstsInBB;
      for (Instruction &I : BB) {
        // 第一轮: ToSimplify 为空 → 处理所有指令
        // 后续轮: 仅处理 ToSimplify 中有的, 也就是上一轮标记的指令
        if (!ToSimplify->empty() && !ToSimplify->count(&I))
          continue;

        // isInstructionTriviallyDead 是判断指令无任何使用, 指令无副作用, 这个在 DCEPass 中有讲
        if (isInstructionTriviallyDead(&I)) {
          DeadInstsInBB.push_back(&I);
          Changed = true;
        } else if (!I.use_empty()) {
          // 尝试简化当前指令
          if (Value *V = simplifyInstruction(&I, SQ)) {
            // 原指令被替换后, 使用着它的其他指令可能变得可简化, 将他们转换为 Instruction* 后加入 Next 集合
            for (User *U : I.users())
              Next->insert(cast&lt;Instruction&gt;(U));
            I.replaceAllUsesWith(V);    // 用简化后的 Value 替换原指令的所有使用
            ++NumSimplified;
            Changed = true;
            // 简化后检查原指令是否变成死指令
            if (isInstructionTriviallyDead(&I))
              DeadInstsInBB.push_back(&I);
          }
        }
      }
      // 删除 DeadInstsInBB 中的指令
      RecursivelyDeleteTriviallyDeadInstructions(DeadInstsInBB, SQ.TLI);
    }

    // 交换 ToSimplify 和 Next 的指向, 准备进入下一轮
    std::swap(ToSimplify, Next);
    Next->clear();
  } while (!ToSimplify->empty());

  return Changed;
}
\```

InstSimplifyPass 的核心逻辑相比 DCEPass 只是多了一个调用 `simplifyInstruction` 尝试简化指令, 然后在对简化后的指令进行死代码删除.

`isInstructionTriviallyDead` 与 `RecursivelyDeleteTriviallyDeadInstructions`, 这里不在讲, 和 DCEPass 中的逻辑基本一致, 只看 `simplifyInstruction` 方法:

```cpp
Value *llvm::simplifyInstruction(Instruction *I, const SimplifyQuery &SQ) {
  SmallVector&lt;Value *, 8&gt; Ops(I->operands());
  Value *Result = ::simplifyInstructionWithOperands(I, Ops, SQ, RecursionLimit);

  /// If called on unreachable code, the instruction may simplify to itself.
  /// Make life easier for users by detecting that case here, and returning a
  /// safe value instead.
  return Result == I ? PoisonValue::get(I->getType()) : Result;
}

static Value *simplifyInstructionWithOperands(Instruction *I,
                                              ArrayRef&lt;Value *&gt; NewOps,
                                              const SimplifyQuery &SQ,
                                              unsigned MaxRecurse) {
  assert(I->getFunction() && "instruction should be inserted in a function");
  assert((!SQ.CxtI || SQ.CxtI->getFunction() == I->getFunction()) &&
         "context instruction should be in the same function");

  const SimplifyQuery Q = SQ.CxtI ? SQ : SQ.getWithInstruction(I);

  switch (I->getOpcode()) {
  default:
    // 若所有操作数都是常量 → 执行常量折叠
    if (all_of(NewOps, IsaPred&lt;Constant&gt;)) {
      SmallVector&lt;Constant *, 8&gt; NewConstOps(NewOps.size());
      transform(NewOps, NewConstOps.begin(),
                [](Value *V) { return cast&lt;Constant&gt;(V); });
      // 对指令操作数进行常量计算
      return ConstantFoldInstOperands(I, NewConstOps, Q.DL, Q.TLI);
    }
    return nullptr;
  case Instruction::FNeg:
    return simplifyFNegInst(NewOps[0], I->getFastMathFlags(), Q, MaxRecurse);
  case Instruction::FAdd:
    return simplifyFAddInst(NewOps[0], NewOps[1], I->getFastMathFlags(), Q,
                            MaxRecurse);
  case Instruction::Add:
    return simplifyAddInst(
        NewOps[0], NewOps[1], Q.IIQ.hasNoSignedWrap(cast&lt;BinaryOperator&gt;(I)),
        Q.IIQ.hasNoUnsignedWrap(cast&lt;BinaryOperator&gt;(I)), Q, MaxRecurse);
  case Instruction::FSub:
    return simplifyFSubInst(NewOps[0], NewOps[1], I->getFastMathFlags(), Q,
                            MaxRecurse);
  case Instruction::Sub:
    return simplifySubInst(
        NewOps[0], NewOps[1], Q.IIQ.hasNoSignedWrap(cast&lt;BinaryOperator&gt;(I)),
        Q.IIQ.hasNoUnsignedWrap(cast&lt;BinaryOperator&gt;(I)), Q, MaxRecurse);
  case Instruction::FMul:
    return simplifyFMulInst(NewOps[0], NewOps[1], I->getFastMathFlags(), Q,
                            MaxRecurse);
  case Instruction::Mul:
    return simplifyMulInst(
        NewOps[0], NewOps[1], Q.IIQ.hasNoSignedWrap(cast&lt;BinaryOperator&gt;(I)),
        Q.IIQ.hasNoUnsignedWrap(cast&lt;BinaryOperator&gt;(I)), Q, MaxRecurse);
  case Instruction::SDiv:
    return simplifySDivInst(NewOps[0], NewOps[1],
                            Q.IIQ.isExact(cast&lt;BinaryOperator&gt;(I)), Q,
                            MaxRecurse);
  case Instruction::UDiv:
    return simplifyUDivInst(NewOps[0], NewOps[1],
                            Q.IIQ.isExact(cast&lt;BinaryOperator&gt;(I)), Q,
                            MaxRecurse);
  case Instruction::FDiv:
    return simplifyFDivInst(NewOps[0], NewOps[1], I->getFastMathFlags(), Q,
                            MaxRecurse);
  case Instruction::SRem:
    return simplifySRemInst(NewOps[0], NewOps[1], Q, MaxRecurse);
  case Instruction::URem:
    return simplifyURemInst(NewOps[0], NewOps[1], Q, MaxRecurse);
  case Instruction::FRem:
    return simplifyFRemInst(NewOps[0], NewOps[1], I->getFastMathFlags(), Q,
                            MaxRecurse);
  case Instruction::Shl:
    return simplifyShlInst(
        NewOps[0], NewOps[1], Q.IIQ.hasNoSignedWrap(cast&lt;BinaryOperator&gt;(I)),
        Q.IIQ.hasNoUnsignedWrap(cast&lt;BinaryOperator&gt;(I)), Q, MaxRecurse);
  case Instruction::LShr:
    return simplifyLShrInst(NewOps[0], NewOps[1],
                            Q.IIQ.isExact(cast&lt;BinaryOperator&gt;(I)), Q,
                            MaxRecurse);
  case Instruction::AShr:
    return simplifyAShrInst(NewOps[0], NewOps[1],
                            Q.IIQ.isExact(cast&lt;BinaryOperator&gt;(I)), Q,
                            MaxRecurse);
  case Instruction::And:
    return simplifyAndInst(NewOps[0], NewOps[1], Q, MaxRecurse);
  case Instruction::Or:
    return simplifyOrInst(NewOps[0], NewOps[1], Q, MaxRecurse);
  case Instruction::Xor:
    return simplifyXorInst(NewOps[0], NewOps[1], Q, MaxRecurse);
  case Instruction::ICmp:
    return simplifyICmpInst(cast&lt;ICmpInst&gt;(I)->getCmpPredicate(), NewOps[0],
                            NewOps[1], Q, MaxRecurse);
  case Instruction::FCmp:
    return simplifyFCmpInst(cast&lt;FCmpInst&gt;(I)->getPredicate(), NewOps[0],
                            NewOps[1], I->getFastMathFlags(), Q, MaxRecurse);
  case Instruction::Select:
    return simplifySelectInst(NewOps[0], NewOps[1], NewOps[2], Q, MaxRecurse);
  case Instruction::GetElementPtr: {
    auto *GEPI = cast&lt;GetElementPtrInst&gt;(I);
    return simplifyGEPInst(GEPI->getSourceElementType(), NewOps[0],
                           ArrayRef(NewOps).slice(1), GEPI->getNoWrapFlags(), Q,
                           MaxRecurse);
  }
  case Instruction::InsertValue: {
    InsertValueInst *IV = cast&lt;InsertValueInst&gt;(I);
    return simplifyInsertValueInst(NewOps[0], NewOps[1], IV->getIndices(), Q,
                                   MaxRecurse);
  }
  case Instruction::InsertElement:
    return simplifyInsertElementInst(NewOps[0], NewOps[1], NewOps[2], Q);
  case Instruction::ExtractValue: {
    auto *EVI = cast&lt;ExtractValueInst&gt;(I);
    return simplifyExtractValueInst(NewOps[0], EVI->getIndices(), Q,
                                    MaxRecurse);
  }
  case Instruction::ExtractElement:
    return simplifyExtractElementInst(NewOps[0], NewOps[1], Q, MaxRecurse);
  case Instruction::ShuffleVector: {
    auto *SVI = cast&lt;ShuffleVectorInst&gt;(I);
    return simplifyShuffleVectorInst(NewOps[0], NewOps[1],
                                     SVI->getShuffleMask(), SVI->getType(), Q,
                                     MaxRecurse);
  }
  case Instruction::PHI:
    return simplifyPHINode(cast&lt;PHINode&gt;(I), NewOps, Q);
  case Instruction::Call:
    return simplifyCall(
        cast&lt;CallInst&gt;(I), NewOps.back(),
        NewOps.drop_back(1 + cast&lt;CallInst&gt;(I)->getNumTotalBundleOperands()), Q);
  case Instruction::Freeze:
    return llvm::simplifyFreezeInst(NewOps[0], Q);
#define HANDLE_CAST_INST(num, opc, clas) case Instruction::opc:
#include "llvm/IR/Instruction.def"
#undef HANDLE_CAST_INST
    return simplifyCastInst(I->getOpcode(), NewOps[0], I->getType(), Q,
                            MaxRecurse);
  case Instruction::Alloca:
    // No simplifications for Alloca and it can't be constant folded.
    return nullptr;
  case Instruction::Load:
    return simplifyLoadInst(cast&lt;LoadInst&gt;(I), NewOps[0], Q);
  }
}
\```

就是做了一件事: 根据 opcode 做不同的常量折叠的处理, 我们跟着 `simplifyAddInst` 看一下:

```cpp
static Value *simplifyAddInst(Value *Op0, Value *Op1, bool IsNSW, bool IsNUW,
                              const SimplifyQuery &Q, unsigned MaxRecurse) {
  // 常量折叠, 如果操作数中都是常量直接计算出来返回
  if (Constant *C = foldOrCommuteConstant(Instruction::Add, Op0, Op1, Q))
    return C;

  // X + poison -> poison, poison 是"无效值", 与任何值运算结果仍为 poison
  if (isa&lt;PoisonValue&gt;(Op1))
    return Op1;

  // X + undef -> undef, undef 是"任意值", 与任何值运算结果仍为 undef
  if (Q.isUndefValue(Op1))
    return Op1;

  // X + 0 -> X
  if (match(Op1, m_Zero()))
    return Op0;

  // 相反数相加
  if (isKnownNegation(Op0, Op1))
    return Constant::getNullValue(Op0->getType());

  // 代数抵消
  // X + (Y - X) -> Y
  // (Y - X) + X -> Y
  // 如果能匹配正确的话, Y 会被填充
  Value *Y = nullptr;
  if (match(Op1, m_Sub(m_Value(Y), m_Specific(Op0))) ||
      match(Op0, m_Sub(m_Value(Y), m_Specific(Op1))))
    return Y;

  // 位运算代数规则
  // X + ~X -> -1
  Type *Ty = Op0->getType();
  if (match(Op0, m_Not(m_Specific(Op1))) || match(Op1, m_Not(m_Specific(Op0))))
    return Constant::getAllOnesValue(Ty);

  // add nsw/nuw (xor Y, signmask), signmask --> Y
  // signmask 是符号位掩码, 如 i32 的 0x80000000, Y ^ signmask 表示翻转 Y 的符号位
  // nsw/nuw 标记保证加法无溢出, 符号位翻转后加符号位, 等价于还原
  if ((IsNSW || IsNUW) && match(Op1, m_SignMask()) &&
      match(Op0, m_Xor(m_Value(Y), m_SignMask())))
    return Y;

  // add nuw %x, -1  ->  -1
  // nuw 标记保证无符号加法无溢出
  // 无符号数中 -1 是全是 1 的常量, 也就是最大值, 无溢出的唯一可能是 %x 为 0
  if (IsNUW && match(Op1, m_AllOnes()))
    return Op1;

  /// 一个比特位的加法等价于 xor: 0+0=0、0+1=1、1+0=1、1+1=0, 调用 simplifyXorInst 处理函数
  if (MaxRecurse && Op0->getType()->isIntOrIntVectorTy(1))
    if (Value *V = simplifyXorInst(Op0, Op1, Q, MaxRecurse - 1))
      return V;

  // 尝试结合律相关的通用简化: (a+b)+c → a+(b+c) 等
  if (Value *V =
          simplifyAssociativeBinOp(Instruction::Add, Op0, Op1, Q, MaxRecurse))
    return V;

  return nullptr;
}
\```

这些处理函数都以 `simplify` 开头, 而 `simplifyAddInst` 这个处理函数比较全面也不是很长, 所以选择了写这个, 在这些处理函数中还会调用别的处理, 这样会出现递归调用, 我调用你, 你在调用回来这种, 所以用 `MaxRecurse` 限制最大递归次数, 防止无限递归. 总的来说是进行模式匹配进行化简, 列出了大量的匹配.

在看一下 `foldOrCommuteConstant` 常量折叠:

```cpp
static Constant *foldOrCommuteConstant(Instruction::BinaryOps Opcode,
                                       Value *&Op0, Value *&Op1,
                                       const SimplifyQuery &Q) {
  if (auto *CLHS = dyn_cast&lt;Constant&gt;(Op0)) {
    if (auto *CRHS = dyn_cast&lt;Constant&gt;(Op1)) {
      switch (Opcode) {
      default:
        break;
      case Instruction::FAdd:
      case Instruction::FSub:
      case Instruction::FMul:
      case Instruction::FDiv:
      case Instruction::FRem:
        // 上下文不为 nullptr 使用带上下文指令的浮点常量折叠
        if (Q.CxtI != nullptr)
          return ConstantFoldFPInstOperands(Opcode, CLHS, CRHS, Q.DL, Q.CxtI);
      }
      // 通用常量折叠
      return ConstantFoldBinaryOpOperands(Opcode, CLHS, CRHS, Q.DL);
    }

    // 仅左操作数是常量 → 交换律优化, 常量移到右侧, 规范常量位置
    if (Instruction::isCommutative(Opcode))
      std::swap(Op0, Op1);
  }
  return nullptr;
}
\```

我们就看下通用常量折叠 `ConstantFoldBinaryOpOperands`, 浮点常量折叠 `ConstantFoldFPInstOperands` 是同样要使用了 `ConstantFoldBinaryOpOperands`, 可以确定的是 `Op0` `Op1` 都是常量是才会调用 `ConstantFoldBinaryOpOperands`:

```cpp
Constant *llvm::ConstantFoldBinaryOpOperands(unsigned Opcode, Constant *LHS,
                                             Constant *RHS,
                                             const DataLayout &DL) {
  assert(Instruction::isBinaryOp(Opcode));
  // 处理 ConstantExpr 类型操作数
  if (isa&lt;ConstantExpr&gt;(LHS) || isa&lt;ConstantExpr&gt;(RHS))
    if (Constant *C = SymbolicallyEvaluateBinop(Opcode, LHS, RHS, DL))
      return C;

  if (ConstantExpr::isDesirableBinOp(Opcode))
    return ConstantExpr::get(Opcode, LHS, RHS);
  // 核心折叠函数
  return ConstantFoldBinaryInstruction(Opcode, LHS, RHS);
}
\```

只看 `ConstantFoldBinaryInstruction`:

```cpp
Constant *llvm::ConstantFoldBinaryInstruction(unsigned Opcode, Constant *C1,
                                              Constant *C2) {
  assert(Instruction::isBinaryOp(Opcode) && "Non-binary instruction detected");

  // getBinOpIdentity 根据 Opcode 和 操作是类型获取运算的单位元, 通常是 0 或者 1 之类的, 将 X + 0 = X, X & -1 = X, X + -0.0 = X 这样的式子化简
  // 如果当前运算有单位元 Identity, 并且两个操作数中有一个是单位元, 那么就可以化简
  if (Constant *Identity = ConstantExpr::getBinOpIdentity(
          Opcode, C1->getType(), /*AllowRHSIdentity*/ false)) {
    if (C1 == Identity)
      return C2;
    if (C2 == Identity)
      return C1;
  } else if (Constant *Identity = ConstantExpr::getBinOpIdentity(
                 Opcode, C1->getType(), /*AllowRHSIdentity*/ true)) {
    if (C2 == Identity)
      return C1;
  }

  // poison 与任何值运算结果都是 poison
  if (isa&lt;PoisonValue&gt;(C1) || isa&lt;PoisonValue&gt;(C2))
    return PoisonValue::get(C1->getType());

  // 处理 undef
  bool IsScalableVector = isa&lt;ScalableVectorType&gt;(C1->getType());
  bool HasScalarUndefOrScalableVectorUndef =
      (!C1->getType()->isVectorTy() || IsScalableVector) &&
      (isa&lt;UndefValue&gt;(C1) || isa&lt;UndefValue&gt;(C2));
  if (HasScalarUndefOrScalableVectorUndef) {
    switch (static_cast&lt;Instruction::BinaryOps&gt;(Opcode)) {
    case Instruction::Xor:
      if (isa&lt;UndefValue&gt;(C1) && isa&lt;UndefValue&gt;(C2))
        // undef ^ undef -> 0
        return Constant::getNullValue(C1->getType());
      [[fallthrough]];
    case Instruction::Add:
    case Instruction::Sub:
      return UndefValue::get(C1->getType());          // X + undef / undef - X → undef
    case Instruction::And:
      if (isa&lt;UndefValue&gt;(C1) && isa&lt;UndefValue&gt;(C2)) // undef & undef -> undef
        return C1;
      return Constant::getNullValue(C1->getType());   // undef & X -> 0
    case Instruction::Mul: {
      // undef * undef -> undef
      if (isa&lt;UndefValue&gt;(C1) && isa&lt;UndefValue&gt;(C2))
        return C1;
      const APInt *CV;
      // X * undef -> undef   if X is odd
      if (match(C1, m_APInt(CV)) || match(C2, m_APInt(CV)))
        if ((*CV)[0])
          return UndefValue::get(C1->getType());

      // X * undef -> 0       otherwise
      return Constant::getNullValue(C1->getType());
    }
    case Instruction::SDiv:
    case Instruction::UDiv:
      // X / undef -> poison
      // X / 0 -> poison
      if (match(C2, m_CombineOr(m_Undef(), m_Zero())))
        return PoisonValue::get(C2->getType());
      // undef / X -> 0       otherwise
      return Constant::getNullValue(C1->getType());
    case Instruction::URem:
    case Instruction::SRem:
      // X % undef -> poison
      // X % 0 -> poison
      if (match(C2, m_CombineOr(m_Undef(), m_Zero())))
        return PoisonValue::get(C2->getType());
      // undef % X -> 0       otherwise
      return Constant::getNullValue(C1->getType());
    case Instruction::Or:                          // X | undef -> -1
      if (isa&lt;UndefValue&gt;(C1) && isa&lt;UndefValue&gt;(C2)) // undef | undef -> undef
        return C1;
      return Constant::getAllOnesValue(C1->getType()); // undef | X -> ~0
    case Instruction::LShr:
      // X >>l undef -> poison
      if (isa&lt;UndefValue&gt;(C2))
        return PoisonValue::get(C2->getType());
      // undef >>l X -> 0
      return Constant::getNullValue(C1->getType());
    case Instruction::AShr:
      // X >>a undef -> poison
      if (isa&lt;UndefValue&gt;(C2))
        return PoisonValue::get(C2->getType());
      // TODO: undef >>a X -> poison if the shift is exact
      // undef >>a X -> 0
      return Constant::getNullValue(C1->getType());
    case Instruction::Shl:
      // X << undef -> undef
      if (isa&lt;UndefValue&gt;(C2))
        return PoisonValue::get(C2->getType());
      // undef << X -> 0
      return Constant::getNullValue(C1->getType());
    case Instruction::FSub:
      // -0.0 - undef --> undef (consistent with "fneg undef")
      if (match(C1, m_NegZeroFP()) && isa&lt;UndefValue&gt;(C2))
        return C2;
      [[fallthrough]];
    case Instruction::FAdd:
    case Instruction::FMul:
    case Instruction::FDiv:
    case Instruction::FRem:
      // [any flop] undef, undef -> undef
      if (isa&lt;UndefValue&gt;(C1) && isa&lt;UndefValue&gt;(C2))
        return C1;
      // [any flop] C, undef -> NaN
      // [any flop] undef, C -> NaN
      return ConstantFP::getNaN(C1->getType());
    case Instruction::BinaryOpsEnd:
      llvm_unreachable("Invalid BinaryOp");
    }
  }

  assert((!HasScalarUndefOrScalableVectorUndef) && "Unexpected UndefValue");

  // 处理右操作数是 ConstantInt 的场景
  if (ConstantInt *CI2 = dyn_cast&lt;ConstantInt&gt;(C2)) {
    if (C2 == ConstantExpr::getBinOpAbsorber(Opcode, C2->getType(),
                                             /*AllowLHSConstant*/ false))
      return C2;

    switch (Opcode) {
    case Instruction::UDiv:
    case Instruction::SDiv:
      if (CI2->isZero())
        return PoisonValue::get(CI2->getType());              // X / 0 == poison
      break;
    case Instruction::URem:
    case Instruction::SRem:
      if (CI2->isOne())
        return Constant::getNullValue(CI2->getType());        // X % 1 == 0
      if (CI2->isZero())
        return PoisonValue::get(CI2->getType());              // X % 0 == poison
      break;
    case Instruction::And:
      assert(!CI2->isZero() && "And zero handled above");
      if (ConstantExpr *CE1 = dyn_cast&lt;ConstantExpr&gt;(C1)) {
        // 全局变量指针转整数后 And 常量掩码 → 预判结果是否为 0
        if ((CE1->getOpcode() == Instruction::PtrToInt ||
             CE1->getOpcode() == Instruction::PtrToAddr) &&
            isa&lt;GlobalValue&gt;(CE1->getOperand(0))) {
          GlobalValue *GV = cast&lt;GlobalValue&gt;(CE1->getOperand(0));

          Align GVAlign; // defaults to 1

          if (Module *TheModule = GV->getParent()) {
            const DataLayout &DL = TheModule->getDataLayout();
            GVAlign = GV->getPointerAlignment(DL);
            if (isa&lt;Function&gt;(GV) && !DL.getFunctionPtrAlign())
              GVAlign = Align(4);
          } else if (isa&lt;GlobalVariable&gt;(GV)) {
            GVAlign = cast&lt;GlobalVariable&gt;(GV)->getAlign().valueOrOne();
          }

          if (GVAlign > 1) {
            unsigned DstWidth = CI2->getBitWidth();
            unsigned SrcWidth = std::min(DstWidth, Log2(GVAlign));
            APInt BitsNotSet(APInt::getLowBitsSet(DstWidth, SrcWidth));

            if ((CI2->getValue() & BitsNotSet) == CI2->getValue())
              return Constant::getNullValue(CI2->getType());
          }
        }
      }
      break;
    }
  } else if (isa&lt;ConstantInt&gt;(C1)) {
    // 左操作数是常量, 右操作数不是 → 交换操作数
    if (Instruction::isCommutative(Opcode))
      return ConstantExpr::isDesirableBinOp(Opcode)
                 ? ConstantExpr::get(Opcode, C2, C1)
                 : ConstantFoldBinaryInstruction(Opcode, C2, C1);
  }

  // 处理两个操作数都是 ConstantInt 的场景
  if (ConstantInt *CI1 = dyn_cast&lt;ConstantInt&gt;(C1)) {
    if (ConstantInt *CI2 = dyn_cast&lt;ConstantInt&gt;(C2)) {
      const APInt &C1V = CI1->getValue();
      const APInt &C2V = CI2->getValue();
      switch (Opcode) {
      default:
        break;
      case Instruction::Add:
        return ConstantInt::get(C1->getType(), C1V + C2V);
      case Instruction::Sub:
        return ConstantInt::get(C1->getType(), C1V - C2V);
      case Instruction::Mul:
        return ConstantInt::get(C1->getType(), C1V * C2V);
      case Instruction::UDiv:
        assert(!CI2->isZero() && "Div by zero handled above");
        return ConstantInt::get(CI1->getType(), C1V.udiv(C2V));
      case Instruction::SDiv:
        assert(!CI2->isZero() && "Div by zero handled above");
        if (C2V.isAllOnes() && C1V.isMinSignedValue())
          return PoisonValue::get(CI1->getType());   // MIN_INT / -1 -> poison
        return ConstantInt::get(CI1->getType(), C1V.sdiv(C2V));
      case Instruction::URem:
        assert(!CI2->isZero() && "Div by zero handled above");
        return ConstantInt::get(C1->getType(), C1V.urem(C2V));
      case Instruction::SRem:
        assert(!CI2->isZero() && "Div by zero handled above");
        if (C2V.isAllOnes() && C1V.isMinSignedValue())
          return PoisonValue::get(C1->getType()); // MIN_INT % -1 -> poison
        return ConstantInt::get(C1->getType(), C1V.srem(C2V));
      case Instruction::And:
        return ConstantInt::get(C1->getType(), C1V & C2V);
      case Instruction::Or:
        return ConstantInt::get(C1->getType(), C1V | C2V);
      case Instruction::Xor:
        return ConstantInt::get(C1->getType(), C1V ^ C2V);
      case Instruction::Shl:
        if (C2V.ult(C1V.getBitWidth()))
          return ConstantInt::get(C1->getType(), C1V.shl(C2V));
        return PoisonValue::get(C1->getType()); // 位数超限 → Poison
      case Instruction::LShr:
        if (C2V.ult(C1V.getBitWidth()))
          return ConstantInt::get(C1->getType(), C1V.lshr(C2V));
        return PoisonValue::get(C1->getType()); // 位数超限 → Poison
      case Instruction::AShr:
        if (C2V.ult(C1V.getBitWidth()))
          return ConstantInt::get(C1->getType(), C1V.ashr(C2V));
        return PoisonValue::get(C1->getType()); // 位数超限 → Poison
      }
    }

    if (C1 == ConstantExpr::getBinOpAbsorber(Opcode, C1->getType(),
                                             /*AllowLHSConstant*/ true))
      return C1;
  } else if (ConstantFP *CFP1 = dyn_cast&lt;ConstantFP&gt;(C1)) {
    // 处理两个操作数都是 ConstantFP 的场景
    if (ConstantFP *CFP2 = dyn_cast&lt;ConstantFP&gt;(C2)) {
      const APFloat &C1V = CFP1->getValueAPF();
      const APFloat &C2V = CFP2->getValueAPF();
      APFloat C3V = C1V;  // copy for modification
      switch (Opcode) {
      default:
        break;
      case Instruction::FAdd:
        (void)C3V.add(C2V, APFloat::rmNearestTiesToEven);
        return ConstantFP::get(C1->getType(), C3V);
      case Instruction::FSub:
        (void)C3V.subtract(C2V, APFloat::rmNearestTiesToEven);
        return ConstantFP::get(C1->getType(), C3V);
      case Instruction::FMul:
        (void)C3V.multiply(C2V, APFloat::rmNearestTiesToEven);
        return ConstantFP::get(C1->getType(), C3V);
      case Instruction::FDiv:
        (void)C3V.divide(C2V, APFloat::rmNearestTiesToEven);
        return ConstantFP::get(C1->getType(), C3V);
      case Instruction::FRem:
        (void)C3V.mod(C2V);
        return ConstantFP::get(C1->getType(), C3V);
      }
    }
  }

  // 处理向量类型运算
  if (auto *VTy = dyn_cast&lt;VectorType&gt;(C1->getType())) {
    // 处理广播常量(所有元素相同的向量)
    if (Constant *C2Splat = C2->getSplatValue()) {
      // 整数除法/取余中, 右操作数是 0 → 返回 Poison
      if (Instruction::isIntDivRem(Opcode) && C2Splat->isNullValue())
        return PoisonValue::get(VTy);
      // 两个操作数都是广播常量 → 折叠标量后重新广播
      if (Constant *C1Splat = C1->getSplatValue()) {
        Constant *Res =
            ConstantExpr::isDesirableBinOp(Opcode)
                ? ConstantExpr::get(Opcode, C1Splat, C2Splat)
                : ConstantFoldBinaryInstruction(Opcode, C1Splat, C2Splat);
        if (!Res)
          return nullptr;
        return ConstantVector::getSplat(VTy->getElementCount(), Res);
      }
    }
    // 固定长度向量, 按元素逐个折叠, 再组合成向量常量
    if (auto *FVTy = dyn_cast&lt;FixedVectorType&gt;(VTy)) {
      SmallVector&lt;Constant*, 16&gt; Result;
      Type *Ty = IntegerType::get(FVTy->getContext(), 32);
      for (unsigned i = 0, e = FVTy->getNumElements(); i != e; ++i) {
        Constant *ExtractIdx = ConstantInt::get(Ty, i);
        Constant *LHS = ConstantExpr::getExtractElement(C1, ExtractIdx);
        Constant *RHS = ConstantExpr::getExtractElement(C2, ExtractIdx);
        Constant *Res = ConstantExpr::isDesirableBinOp(Opcode)
                            ? ConstantExpr::get(Opcode, LHS, RHS)
                            : ConstantFoldBinaryInstruction(Opcode, LHS, RHS);
        if (!Res)
          return nullptr;
        Result.push_back(Res);
      }

      return ConstantVector::get(Result);
    }
  }

  // 处理 ConstantExpr 重组, 结合律优化
  if (ConstantExpr *CE1 = dyn_cast&lt;ConstantExpr&gt;(C1)) {
    // 若 b + c 可折叠, ((a + b) + c) → (a + (b + c))
    if (Instruction::isAssociative(Opcode) && CE1->getOpcode() == Opcode) {
      Constant *T = ConstantExpr::get(Opcode, CE1->getOperand(1), C2);
      if (!isa&lt;ConstantExpr&gt;(T) || cast&lt;ConstantExpr&gt;(T)->getOpcode() != Opcode)
        return ConstantExpr::get(Opcode, CE1->getOperand(0), T);
    }
  } else if (isa&lt;ConstantExpr&gt;(C2)) {
    // 右操作数是 ConstantExpr → 交换操作数后折叠
    if (Instruction::isCommutative(Opcode))
      return ConstantFoldBinaryInstruction(Opcode, C2, C1);
  }

  // 处理 i1(一个比特位) 类型运算,
  if (C1->getType()->isIntegerTy(1)) {
    switch (Opcode) {
    case Instruction::Add:
    case Instruction::Sub:
      return ConstantExpr::getXor(C1, C2);  // // i1 加法/减法 → 异或
    case Instruction::Shl:
    case Instruction::LShr:
    case Instruction::AShr:
      // 移位: 移位位数 ≥ 1 → 未定义, 默认返回原数; 移位 0 → 返回原数
      return C1;
    case Instruction::SDiv:
    case Instruction::UDiv:
      // i1 除法: 除数只能是1, 结果 = 被除数
      return C1;
    case Instruction::URem:
    case Instruction::SRem:
      // i1 取余: 除数 1 → 结果 0
      return ConstantInt::getFalse(C1->getContext());
    default:
      break;
    }
  }

  // 无法折叠 → 返回 nullptr
  return nullptr;
}
\```

这里的常数折叠就是对各种情况进行处理, 按优先级一一处理, 特殊值特殊处理.

实验一下:

```ir
define i32 @common_sub_operand(i32 %X, i32 %Y) {
  %Z = sub i32 %X, %Y
  %Q = add i32 %Z, %Y
  ret i32 %Q
}

define i32 @negated_operand(i32 %x) {
  %negx = sub i32 0, %x
  %r = add i32 %negx, %x
  ret i32 %r
}

define <2 x i8> @or_or_not_commute2(<2 x i8> %x, <2 x i8> %y) {
  %ynot = xor <2 x i8> %y, &lt;i8 poison, i8 -1&gt;
  %xory = or <2 x i8> %x, %y
  %xorynot = or <2 x i8> %ynot, %x
  %and = and <2 x i8> %xory, %xorynot
  ret <2 x i8> %and
}
\```

```bash
./build/bin/opt -passes=instsimplify -S /tmp/a.ll
\```

```ir
; ModuleID = '/tmp/a.ll'
source_filename = "/tmp/a.ll"

define i32 @common_sub_operand(i32 %X, i32 %Y) {
  ret i32 %X
}

define i32 @negated_operand(i32 %x) {
  ret i32 0
}

define <2 x i8> @or_or_not_commute2(<2 x i8> %x, <2 x i8> %y) {
  ret <2 x i8> %x
}
\```

更新地址: https://github.com/nothing-2333/llvm-pass-learn

---

# 回复

## 回复 by 温泉划水鱼 (#2)

*2026-3-16 15:25*

看看

## 回复 by Steesha (#3)

*2026-3-22 20:14*

666

## 回复 by fjqisba (#4)

*2026-3-22 20:24*

222

## 回复 by mb_4nrpVMxJ (#5)

*2026-3-22 20:42*

666

## 回复 by k4y0z (#6)

*2026-3-23 10:10*

666

## 回复 by guijingwen (#7)

*2026-3-23 10:12*

66

## 回复 by 拍拖 (#8)

*2026-3-23 16:27*

感谢分享

## 回复 by XCicada (#9)

*2026-3-23 16:49*

666

## 回复 by dx苹果的心愿 (#10)

*2026-3-23 17:33*

6

## 回复 by mb_nkjfyhkg (#11)

*2026-3-30 21:19*

mark

## 回复 by mb_ysikfhxt (#12)

*2026-4-1 22:29*

666
