---
title: '[原创]记录一次BlackObfuscator去混淆流程'
url: https://bbs.kanxue.com/thread-283753.htm
tid: 283753
author: 棕熊
date: '2024-10-02'
tags: [Android安全, 原创, 逆向分析, 混淆加固, 脱壳反混淆, 工具脚本]
crawled_at: '2026-07-31T14:19:36+08:00'
replies: 15
---

# 前言

在一些CTF以及某些检测环境的APP中，在Java层会出现一种很奇怪的混淆，经过熊仔哥(看雪ID：白熊)的指点，这种混淆是一种开源的混淆方案，最早我是使用trace smali的方式解决掉的，不过最近有一场ctf比赛，这个混淆又出现了，并且有大佬给出了新的思路，以此契机我开始学习了Java层混淆对抗的路子，并开发出了几个脚本。感谢与我一起写反混淆脚本的实习生，我们一起完善解决了这个方案与脚本。

# 混淆的表现形式

Jadx-GUi

![CleanShot 2024-10-02 at 09.31.17.png](https://bbs.kanxue.com/upload/attach/202410/967562_Z93HASGTH3H8FRR.png)

![CleanShot 2024-10-02 at 09.31.34.png](https://bbs.kanxue.com/upload/attach/202410/967562_SN7ADXHM9RBMG3Y.png)

GDA

![CleanShot 2024-10-02 at 09.32.26.png](https://bbs.kanxue.com/upload/attach/202410/967562_HB2EHFDSRF4X46Z.png)

JEB

![CleanShot 2024-10-02 at 09.33.58.png](https://bbs.kanxue.com/upload/attach/202410/967562_E3M8NZJDZP2TNQK.png)

由于每种反编译器的反编译效果不同，表现出的伪代码形式也为不同。

# 为什么JEB自动反混淆失效了？

我们选择JEB来进行主力分析工具，因为JEB自带有一些神奇魔法，能帮我们做很多的事情。

<https://bbs.kanxue.com/thread-278648.htm>

在oacia大佬的帖子里，**jeb直接去除掉了控制流平坦化**

![CleanShot 2024-10-02 at 09.36.12.png](https://bbs.kanxue.com/upload/attach/202410/967562_A8TV5PPYAT8FMH5.png)

但是又是什么**神奇魔法让jeb的这种自动反混淆的能力失效了呢**，让我来带你详细分析。

jeb官方支持反控制流平坦化的文档

<https://www.pnfsoftware.com/blog/control-flow-unflattening-in-the-wild/>

如果jeb帮我们完成了处理，那么在函数的头部会留下一些注释。

![image.png](https://bbs.kanxue.com/upload/attach/202410/967562_AGQBXJCEMNK6AJV.png)

# 开始初步混淆失败的原因，并引出解决办法

首先，打开自动重命名工具，将奇怪的字符串重新命名，增强阅读体验

![CleanShot 2024-10-02 at 09.40.50.png](https://bbs.kanxue.com/upload/attach/202410/967562_4VZ6DK3DCHDD3S3.png)

我认为百分之20即可完美去除垃圾字符串(正因为不好看，所以好识别)

![CleanShot 2024-10-02 at 09.41.53.png](https://bbs.kanxue.com/upload/attach/202410/967562_BD8RHK34BUJGW68.png)

点击确定即可重新命名，获得一个比较好的阅读体验。

```
while(true) {
            switch(v1) {
                case 0xDC63: {
                    throw new ArithmeticException("divide by zero");
                }
                case 0xDCE0: {
                    char[] arr_c1 = (char[])CLS6886.n(4060);
                    v1 = CLS4747.FLD23111 / CLS5009.FLD24258 + 0x1AAB64;
                    arr_c = arr_c1;
                    break;
                }
                case 1747810: {
                    if(v2 < arr_c.length) {
                        v1 = CLS3999.FLD11077 <= 0 ? 0x1AC507 : CLS3609.FLD3439 + CLS3299.FLD190 + 1750708;
                        break;
                    }

                    v1 = CLS6392.FLD24345 >= 0 ? CLS3773.MTH9818("ۣۤ") : (CLS5453.FLD24321 | CLS4512.FLD22042) ^ 0x1AAC8F;
                    break;
                }
                case 0x1AAE85: {
                    v1 = 0x1AC8C8;
                    arr_c = arr_c;
                    break;
                }
                case 0x1AAF3C: {
                    ((int[])CLS6886.n(87336))[61] = 0;
                    if((CLS5973.FLD24338 ^ CLS5976.FLD24339 / 0xFFFFF0C6) >= 0) {
                        CLS4777.FLD23198 = 54;
                        v1 = CLS4443.MTH20030("ۣۤۨ");
                    }
                    else {
                        v1 = CLS3478.FLD2400 * CLS3441.FLD2185 ^ 0x1EA090;
                    }

                    break;
                }
                case 0x1AB246: {
                    int[] arr_v1 = (int[])CLS6886.n(87336);
                    arr_v1[arr_c[v2]] = v2;
                    v1 = 0x1AB2E1;
                    break;
                }
                case 0x1AB2E1: {
                    v = v2 + (CLS5411.FLD24315 ^ -493);
                    if(CLS5891.FLD24333 >= 0) {
                        CLS5456.FLD24322 = 7;
                        v1 = 0x1AB2E1;
                    }
                    else {
                        v1 = CLS4671.MTH23075("\u06E8\u06E6\u06E6");
                        arr_v = arr_v;
                    }

                    break;
                }
                case 1750562:
                case 1750625: {
                    v1 = CLS3577.FLD3076 - (CLS4202.FLD12410 | -8627) <= 0 ? 0xDC03 : CLS4369.FLD13819 - CLS3303.FLD192 + 0xDB7B;
                    break;
                }
                case 1750813: {
                    v1 = CLS4671.MTH23075("ۧۨۧ");
                    arr_v = new int[0x100];
                    break;
                }
                case 0x1ABA02: {
                    v1 = CLS3439.FLD2184 % CLS4368.FLD13818 + 1755107;
                    break;
                }
                case 0x1ABA60: {
                    strange.ALPHABET = (char[])CLS6886.n(0x9259, ((String)CLS6886.n(0xFA8C, null, new Object[]{((short[])CLS6886.n(70719)), ((int)0), ((int)(CLS3302.FLD191 ^ -750)), ((int)3052)})), new Object[0]);
                    v1 = CLS4038.FLD11440 >= 0 ? 0x1AC50B : (CLS5547.FLD24326 | CLS4873.FLD23694) ^ 1750971;
                    break;
                }
                case 0x1ABADF: {
                    v1 = CLS3873.FLD9991 % CLS3610.FLD3440 + 1755703;
                    break;
                }
                case 0x1ABDE7: {
                    v1 = CLS6392.FLD24345 >= 0 ? CLS3773.MTH9818("ۣۤ") : (CLS5453.FLD24321 | CLS4512.FLD22042) ^ 0x1AAC8F;
                    break;
                }
                case 0x1ABE48: {
                    v1 = CLS3773.MTH9818("ۣۢ۠");
                    break;
                }
                case 1753508: {
                    v1 = ((Boolean)CLS6886.n(72724, null, new Object[]{((int)(CLS3815.FLD9626 ^ 0xFFFF940E))})).booleanValue() ? 0xDC63 : CLS3873.FLD9991 % CLS3610.FLD3440 + 1755703;
                    break;
                }
                case 0x1AC507: {
                    CLS6886.n(92279, null, new Object[]{arr_v, ((int)(CLS4779.FLD23199 ^ -668))});
                    v1 = CLS4443.MTH20030("ۣۡ۟");
                    break;
                }
                case 0x1AC50B: {
                    strange.short = new short[]{0xB82, 0xB83, 0xB9C, 0xB9D, 0xB9E, 0xB9F, 0xB98, 0xBA8, 0xBA9, 0xBAA, 0xBAB, 2980, 0xBA5, 0xBA6, 0xBA7, 0xBA0, 0xB84, 0xB85, 2950, 0xB87, 0xB80, 3001, 3002, 3005, 3006, 3007, 3000, 3011, 3003, 0xBB4, 0xBB5, 0xBB6, 0xB8D, 0xB8E, 0xBAD, 2990, 0xBAF, 0xB8F, 0xB88, 0xB89, 0xB8A, 0xB8B, 0xB81, 0xB99, 2970, 3034, 3035, 3028, 3029, 3015, 0xB9B, 0xB94, 0xB95, 0xB96, 3036, 3037, 3038, 0xBDF, 3032, 3033, 0xBA1, 0xBA2, 0xBA3, 3004};
                    v1 = CLS4284.FLD12674 - CLS4029.FLD11433 ^ 0xFFE54538;
                    break;
                }
                case 0x1AC626: {
                    strange.LOOKUP = arr_v;
                    v1 = 0x1AC507;
                    break;
                }
                case 0x1AC8C8: {
                    v1 = 0xDCE0;
                    v2 = 0;
                    break;
                }
                case 1755560: {
                    v1 = 0x1ABE48;
                    v2 = v;
                    break;
                }
                case 0x1AC9E8: {
                    break alab1;
                }
            }
        }
```

首先我们先摘出来一段控制流平坦化，分析其为什么不能自动反控制流平坦化

在switch(v1) v1如果全部都是已知数值的情况下，jeb可以直接反控制流平坦化

**让我们看看是什么影响了v1的值**

![CleanShot 2024-10-02 at 09.46.37.png](https://bbs.kanxue.com/upload/attach/202410/967562_PWRX3ZYTNAB6FUT.png)

通过查看发现，有两种方式影响了v1的赋值，让我们点进去看一下

第一种形式：

![CleanShot 2024-10-02 at 09.47.41.png](https://bbs.kanxue.com/upload/attach/202410/967562_AHBD2UHMBZUFYF3.png)

第二种形式：

![CleanShot 2024-10-02 at 09.48.13.png](https://bbs.kanxue.com/upload/attach/202410/967562_RNSUWK8RQTBK76E.png)

当我们解决这两种混淆方式以后，jeb大哥会直接反混淆成功。

## 第一种形式的分析：

由于静态变量不是定植，在其他的地方可能被引用并修改，jeb理解这个值可能发生变化，所以不进行优化。

熟悉混淆的小伙伴可能脑子里立马迸发出一个想法：

这不**就是bcf吗**？ 通过全局变量的不透明谓词来干扰执行流程

让我们分析这个变量在后续有没有修改？

![CleanShot 2024-10-02 at 09.50.58.png](https://bbs.kanxue.com/upload/attach/202410/967562_SQMHWY5DRPS9QV8.png)

发现只有获取，并没有修改的形式。

那么我们该如何解决呢？其实非常简单。

<https://bbs.kanxue.com/thread-257213.htm>

参考葫芦娃大佬的帖子，我们可以改个标题了

**JEB: 十步杀一人，两步秒BlackObfuscator**

参考大佬的思路，我们可以把这个字段的权限从读写，改为只读

我们如何将这个字段变为只读字段呢？

### 方法一 修改字段属性，将public static 改为 public static final

熟悉java的朋友应该知道，final加入后只能读就不能写了

### 方法二 patch获取字段的smali语句，直接为静态赋值

我们来观察一下这个字段获取的语句：

```
00000400  sget                v0, CLS3873->FLD9991:I
00000404  sget                v2, CLS3610->FLD3440:I
```

那么我们就可以引出第二种修改方式,将sget语句patch为const语句，也可以让我们的jeb直接意识到，这个是不可变的。

## 第二种形式的分析:

![CleanShot 2024-10-02 at 10.03.27.png](https://bbs.kanxue.com/upload/attach/202410/967562_R6RCCMFMJQN4QQG.png)

关键的语句:

| 123 | `000003EE` `const``-string        v0,` `"\u06E7\u06E6\u06E0"``000003F2  invoke-``static`       `CLS5547->MTH27577(Object)I, v0``000003F8  move-result         v0` |
|-|-|

const-string v0, "\u06E7\u06E6\u06E0" 定义了一个固定的字符串 赋值给v0寄存器

invoke-static CLS5547->MTH27577(Object)I, v0 调用静态方法，v0参数传入这个函数

000003F8 move-result v0 将结果放回v0寄存器(这里和上面两句使用的寄存器的一般一致，但是我在后面还是处理了)

```
.method public static MTH27577(Object)I
          .registers 2
00000000  invoke-virtual      Object->hashCode()I, p0
00000006  move-result         v0
00000008  return              v0
.end method
```

调用的函数非常简单，就是取一个字符串的hashcode

众所周知，在字符串不变的情况下，hashcode也是不会变的，下面给出算法

![CleanShot 2024-10-02 at 10.07.19.png](https://bbs.kanxue.com/upload/attach/202410/967562_JC8S273QAU27T3C.png)

| 123456789101112 | `public` `int` `hashCode() {``int` `h = hash;``if` `(h ==` `0` `&& value.length >` `0``) {``char` `val[] = value;` `for` `(``int` `i =` `0``; i < value.length; i++) {``h =` `31` `* h + val[i];``}``hash = h;``}``return` `h;``}` |
|-|-|

第二种方式又是用一种巧妙的方法骗过了我们的jeb老大哥

如何解决？

查找所有静态调用的方法，查看方法体是否调用了hashcode(如果更快我觉得可以收集opcode特征打一个md5，但是没必要)，如果是，手动计算hashcode，并patch回原来的调用处。

为了给原来的smali方法体擦干净屁股，我们需要将三条smali指令替换为一条。

也就是把

| 123 | `000003EE` `const``-string        v0,` `"\u06E7\u06E6\u06E0"``000003F2  invoke-``static`       `CLS5547->MTH27577(Object)I, v0``000003F8  move-result         v0` |
|-|-|

替换为`const v0,计算后的hashcode`

# 踩坑，寻找修改的脚手架

这个部分更多的是引出两种去混淆方案的形式，为第二篇AST解混淆做出预告

最早我使用的方案是使用jeb脚本的方式来修改，当然幻想是美好的，实际却是残酷的。

在这里我想引入两种概念，借用看雪另外一位大佬(<https://bbs.kanxue.com/homepage-760871.htm>)的两个帖子来带大家领略这两个反混淆的概念。

<https://bbs.kanxue.com/thread-263011.htm>

<https://bbs.kanxue.com/thread-263012.htm>(选看，本帖没用上）

## 第一种形式:（本文主要围绕着第一种形式做反混淆）

| 1234567 | `DEX字节码层面(IDexUnit部件)``(``1``)访问DEX与Class``(``2``)遍历Field / Method``(``3``)访问某个Method``(``4``)访问指令``(``5``)访问基本块``(``6``)访问控制流数据流` |
|-|-|

下面我们开始讲如何用jeb。实现第一种形式的patch**(没有成功实现，大佬选看，只是记录踩坑过程)**

第一种想法，找到sget指令，获取到sget操作的字段，patch回去

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354 | `# -*- coding: UTF-``8` `-*-``from com.pnfsoftware.jeb.client.api` `import` `IScript``from com.pnfsoftware.jeb.core.units` `import` `UnitUtil``from com.pnfsoftware.jeb.core.units.code.android` `import` `IDexUnit``from com.pnfsoftware.jeb.core.units.code.android.dex` `import` `IDexClass``from com.pnfsoftware.jeb.core.actions` `import` `ActionContext``from com.pnfsoftware.jeb.core.actions` `import` `Actions``from com.pnfsoftware.jeb.client.api` `import` `IClientContext``from com.pnfsoftware.jeb.core` `import` `IRuntimeProject``from com.pnfsoftware.jeb.core.units` `import` `IUnit``from com.pnfsoftware.jeb.core.units.code` `import` `IFlowInformation``from com.pnfsoftware.jeb.core.units.code.android` `import` `IDexUnit` `class` `SGetRightOperandTree(IScript):``def run(self, ctx):``prj = ctx.getMainProject();``dexUnit =prj.findUnit(IDexUnit);` `# Check` `if` `the unit is a DEX unit``if` `not isinstance(dexUnit, IDexUnit):``print(``'The script must be run on a DEX unit.'``)``return` `# Specify the` `class` `name you're interested in``method_sign =` `'Lcom/example/bbandroid/strange;->encode([B)Ljava/lang/String;'` `method = dexUnit.getMethod(method_sign)` `dexMethodData = method.getData();``dexCodeItem= dexMethodData.getCodeItem();``for` `idx,insn in enumerate(dexCodeItem.getInstructions()):``if` `str(insn)==``"sget"``:``print insn``print idx,``"(01) getCode                      >>> "``,insn.getCode()               # 二进制``print idx,``"(02) getOpcode                    >>> "``,insn.getOpcode()             # 操作码``print idx,``"(03) getParameters:"`                                                 `# 指令操作数``for` `a,b in enumerate(insn.getParameters()):``print` `"<"``,a,``">"``,b.getType(),b.getValue()``if` `len(insn.getParameters()) >` `1``:``fieldRef = insn.getParameters()[``1``]``print(``"Field Reference: "``, fieldRef)``if` `len(insn.getParameters()) >` `1``:``fieldRef = insn.getParameters()[``1``].getValue()``field = dexUnit.getField(fieldRef)``print(field.getName())``# currentFlags = field.getAddress()``# print(``"currentFlags"``,currentFlags)``fieldData = field.getData()``print(field.getStaticInitializer())``fieldValue=field.getStaticInitializer()``#` `if` `field:``# 那么就patch回去` |
|-|-|

尴尬的来了，找了半天jeb文档，没有相关写入方法。（有大佬有写入方法的话带带，我能写出jeb脚本）

insn是属于`IDalvikInstruction`类下面的

我们打开jeb文档

<https://www.pnfsoftware.com/jeb/apidoc/reference/com/pnfsoftware/jeb/core/units/code/android/dex/IDalvikInstruction.html>

我们可以看到各种get方法，

![CleanShot 2024-10-02 at 10.36.46.png](https://bbs.kanxue.com/upload/attach/202410/967562_C5GGDUR3XN7R6HN.png)

也许可以拿到offset和offsetend 在针对性patch，但是我没有考虑这种方式。

总的来说，通过DEX字节码层面可以拿到所有我能拿到的信息，但是并没有一个方法来设置。

大体思路就是先拿到DEX模块，进一步拿到所有method，在拿到所有基本块，遍历所有基本块里的指令，如果遇到sget，则找到sget获取的Filed，然后修改sget这个指令。

也可以另外一种思路，收集所有静态字段，然后查找引用的地方，再去以字节码层面patch

同时也可以收集所有静态字段，拿到静态字段的权限，进行过滤，然后修改为只读（JEB可以拿到确切的权限，但是没法修改） 拿到权限那段代码我丢了，我后续会补上

---

### 实战: 如何彻底恢复控制流平坦化

既然jeb不能满足我们的需求，我们可以采用dex2lib这个库来进行反混淆操作。

首先先实现方案1，将所有静态字段增加final属性

[show me the code！](https://news.ycombinator.com/item?id=902216)

| 12345678910111213141516171819202122232425262728 | `@Override``public` `Rewriter<Field> getFieldRewriter(Rewriters rewriters) {``return` `new` `FieldRewriter(rewriters) {``@Override``public` `Field rewrite(Field field) {``int` `accessFlags = field.getAccessFlags();``// 检查是否为 public static``if` `((accessFlags & AccessFlags.PUBLIC.getValue()) !=` `0` `&&``(accessFlags & AccessFlags.STATIC.getValue()) !=` `0` `&&``(accessFlags & AccessFlags.FINAL.getValue()) ==` `0``) {``// 添加 FINAL 修饰符``accessFlags \|= AccessFlags.FINAL.getValue();``System.out.println(``"Modified field "` `+ field.getName() +` `" to public static final"``);``// 返回修改后的字段``return` `new` `ImmutableField(``field.getDefiningClass(),``field.getName(),``field.getType(),``accessFlags,``field.getInitialValue(),` `// initialValue``field.getAnnotations(),` `// annotations``field.getHiddenApiRestrictions()` `// hiddenApiRestrictions``);``}``return` `super``.rewrite(field);``}``};``}` |
|-|-|

![CleanShot 2024-10-02 at 10.51.31.png](https://bbs.kanxue.com/upload/attach/202410/967562_RRPEZBMYU9XD74G.png)

![CleanShot 2024-10-02 at 10.54.08.png](https://bbs.kanxue.com/upload/attach/202410/967562_FBMVCFEKJTNCQ77.png)

很多读者有疑问，为什么hashcode没有解析也可以识别了，我的答案是jeb牛逼。

当然我也针对了hashcode写了对抗的脚本，大家可以当demo参考。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374757677 | `@Override``public` `Rewriter<MethodImplementation> getMethodImplementationRewriter(Rewriters rewriters) {``return` `new` `MethodImplementationRewriter(rewriters) {``@Override``public` `MethodImplementation rewrite(MethodImplementation methodImpl) {``if` `(methodImpl ==` `null``) {``return` `null``;``}``List<Instruction> originalInstructions =` `new` `ArrayList<>();``for` `(Instruction instruction : methodImpl.getInstructions()) {``originalInstructions.add(instruction);``}``List<Instruction> newInstructions =` `new` `ArrayList<>();` `for` `(``int` `i =` `0``; i < originalInstructions.size(); i++) {``Instruction instruction = originalInstructions.get(i);` `if` `(instruction.getOpcode() == Opcode.INVOKE_STATIC) {``if` `(instruction` `instanceof` `ReferenceInstruction) {``ReferenceInstruction refInstr = (ReferenceInstruction) instruction;``Reference reference = refInstr.getReference();``if` `(reference` `instanceof` `MethodReference) {``MethodReference methodRef = (MethodReference) reference;``//拿到方法签名``String methodKey = getMethodKey(methodRef);``//拿到要调用的方法的签名``Method calledMethod = methodMap.get(methodKey);``if` `(calledMethod !=` `null` `&& calledMethod.getImplementation() !=` `null``) {``//这里就是判断是否调用了 hashCode 方法``if` `(methodContainsHashCodeInvocation(calledMethod)) {``// 获取参数寄存器``List<Integer> parameterRegisters = getInvokeInstructionParameterRegisters(instruction);``if` `(parameterRegisters.size() >` `0``) {``int` `paramRegister = parameterRegisters.get(``0``);``// 向上寻找赋值给 paramRegister 的指令，追踪源寄存器，直到找到 const-string``String stringValue = findStringAssignedToRegister(paramRegister, originalInstructions, i);``if` `(stringValue !=` `null``) {``// 计算哈希码``int` `hashCode = stringValue.hashCode();``// 获取结果寄存器``int` `resultRegister = getResultRegister(originalInstructions, i);``if` `(resultRegister != -``1``) {``// 创建 const 指令替换 invoke-static 和 move-result``Instruction constInstr = createConstInstruction(resultRegister, hashCode);``if` `(constInstr !=` `null``) {``newInstructions.add(constInstr);``System.out.println(``"Replaced invoke-static with const for method "` `+ methodRef.getName() +` `", hashCode: "` `+ hashCode);``// 跳过 invoke-static 和后续的 move-result 指令``if` `(i +` `1` `< originalInstructions.size()) {``Instruction nextInstr = originalInstructions.get(i +` `1``);``if` `(nextInstr.getOpcode() == Opcode.MOVE_RESULT \|\| nextInstr.getOpcode() == Opcode.MOVE_RESULT_OBJECT \|\| nextInstr.getOpcode() == Opcode.MOVE_RESULT_WIDE) {``i++;` `// 跳过 move-result 指令``}``}``continue``;``}``}``}``}``}``}``}``}``}``// 复制原始指令``newInstructions.add(instruction);``}` `return` `new` `ImmutableMethodImplementation(``methodImpl.getRegisterCount(),``newInstructions,``methodImpl.getTryBlocks(),``methodImpl.getDebugItems()``);``}``};``}` |
|-|-|

运行结果：

![CleanShot 2024-10-02 at 10.58.32.png](https://bbs.kanxue.com/upload/attach/202410/967562_8DRFKZKAZRP2DS7.png)

![CleanShot 2024-10-02 at 10.58.48.png](https://bbs.kanxue.com/upload/attach/202410/967562_4RHK7W4QU4UYR4B.png)

第三个思路：

收集所有sget指令，替换为const，这里涉及到一个搜索问题

第一个版本我是先拿到Feild，然后遍历所有类，找到相同的，导致速度很慢

第二个版本我先提前收集好所有Feild，然后建立一个hashmap做匹配，速度提升了不少

第一个版本：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657 | `@Override``public` `Rewriter<MethodImplementation> getMethodImplementationRewriter(Rewriters rewriters) {``return` `new` `MethodImplementationRewriter(rewriters) {``@Override``public` `MethodImplementation rewrite(MethodImplementation methodImpl) {``if` `(methodImpl ==` `null``) {``return` `null``;``}``Iterable<?` `extends` `Instruction> instructions = methodImpl.getInstructions();``List<Instruction> newInstructions =` `new` `ArrayList<>();` `for` `(Instruction instruction : instructions) {``if` `(instruction.getOpcode() == Opcode.SGET) {``// 替换 SGET 指令为 CONST 指令``// 这里的检查继承关系是保证不污染其他sget指令``if` `(instruction` `instanceof` `ReferenceInstruction && instruction` `instanceof` `OneRegisterInstruction) {``ReferenceInstruction refInstr = (ReferenceInstruction) instruction;``Reference reference = refInstr.getReference();``if` `(reference` `instanceof` `FieldReference) {``FieldReference fieldRef = (FieldReference) reference;``Number value = getStaticFieldValue(dexFile, fieldRef);``if` `(value !=` `null``) {``int` `registerA = ((OneRegisterInstruction) instruction).getRegisterA();``Instruction newInstr = createConstInstruction(registerA, value);``if` `(newInstr !=` `null``) {``newInstructions.add(newInstr);``System.out.println(``"Replaced SGET instruction with CONST for field "` `+ fieldRef.getName() +` `" with value "` `+ value);``continue``;``}``}` `else` `{``System.out.println(``"Field "` `+ fieldRef.getName() +` `" has non-numeric initial value."``);``newInstructions.add(instruction);` `// 保留原始指令``continue``;``}``}``else` `{``System.out.println(``"other type of sget instruction"``);``newInstructions.add(instruction);` `// 保留原始指令``continue``;``}``}``else` `{``System.out.println(``"other type of sget instruction"``);``newInstructions.add(instruction);` `// 保留原始指令``continue``;``}``}``newInstructions.add(instruction);``}` `return` `new` `ImmutableMethodImplementation(``methodImpl.getRegisterCount(),``newInstructions,``methodImpl.getTryBlocks(),``methodImpl.getDebugItems()``);``}``};``}` |
|-|-|

第一个版本的搜索算法(别喷）

| 12345678910111213141516171819202122 | `private` `static` `Number getStaticFieldValue(DexFile dexFile, FieldReference fieldRef) {``String fieldClass = fieldRef.getDefiningClass();``for` `(ClassDef classDef : dexFile.getClasses()) {``if` `(classDef.getType().equals(fieldClass)) {``for` `(Field field : classDef.getStaticFields()) {``if` `(field.getName().equals(fieldRef.getName())) {``EncodedValue encodedValue = field.getInitialValue();``if` `(encodedValue` `instanceof` `IntEncodedValue) {``return` `((IntEncodedValue) encodedValue).getValue();``}` `else` `if` `(encodedValue` `instanceof` `LongEncodedValue) {``return` `((LongEncodedValue) encodedValue).getValue();``}` `else` `if` `(encodedValue` `instanceof` `FloatEncodedValue) {``return` `((FloatEncodedValue) encodedValue).getValue();``}` `else` `if` `(encodedValue` `instanceof` `DoubleEncodedValue) {``return` `((DoubleEncodedValue) encodedValue).getValue();``}``}``}``}``}``return` `null``;``}` |
|-|-|

第二个版本:

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253 | `@Override``public` `Rewriter<MethodImplementation> getMethodImplementationRewriter(Rewriters rewriters) {``return` `new` `MethodImplementationRewriter(rewriters) {``@Override``public` `MethodImplementation rewrite(MethodImplementation methodImpl) {``if` `(methodImpl ==` `null``) {``return` `null``;``}``Iterable<?` `extends` `Instruction> instructions = methodImpl.getInstructions();``List<Instruction> newInstructions =` `new` `ArrayList<>();` `for` `(Instruction instruction : instructions) {``if` `(instruction.getOpcode() == Opcode.SGET) {``// 替换 SGET 指令为 CONST 指令``if` `(instruction` `instanceof` `ReferenceInstruction && instruction` `instanceof` `OneRegisterInstruction) {``ReferenceInstruction refInstr = (ReferenceInstruction) instruction;``Reference reference = refInstr.getReference();``if` `(reference` `instanceof` `FieldReference) {``FieldReference fieldRef = (FieldReference) reference;``String fieldKey = getFieldKey(fieldRef);` `EncodedValue encodedValue = fieldInitialValueMap.get(fieldKey);``if` `(encodedValue !=` `null``) {``Number value = getNumberFromEncodedValue(encodedValue);``if` `(value !=` `null``) {``int` `registerA = ((OneRegisterInstruction) instruction).getRegisterA();``Instruction newInstr = createConstInstruction(registerA, value);``if` `(newInstr !=` `null``) {``newInstructions.add(newInstr);``System.out.println(``"Replaced SGET instruction with CONST for field "` `+ fieldRef.getName() +` `" with value "` `+ value);``continue``;``}``}` `else` `{``System.out.println(``"Field "` `+ fieldRef.getName() +` `" has non-numeric initial value."``);``}``}` `else` `{``System.out.println(``"Initial value not found for field "` `+ fieldRef.getName());``}``}``}``}``newInstructions.add(instruction);``}` `return` `new` `ImmutableMethodImplementation(``methodImpl.getRegisterCount(),``newInstructions,``methodImpl.getTryBlocks(),``methodImpl.getDebugItems()``);``}``};``}` |
|-|-|

提前收集字段

| 12345678910111213141516171819202122232425 | `// 构建字段初始值映射，包括从 <clinit> 方法中提取的值``Map<String, EncodedValue> fieldInitialValueMap = buildFieldInitialValueMap(dexFile);``private` `static` `Map<String, EncodedValue> buildFieldInitialValueMap(DexFile dexFile) {``Map<String, EncodedValue> fieldValueMap =` `new` `HashMap<>();``for` `(ClassDef classDef : dexFile.getClasses()) {``String classType = classDef.getType();``// 从字段定义中获取初始值 作为初始化``for` `(Field field : classDef.getStaticFields()) {``EncodedValue encodedValue = field.getInitialValue();``if` `(encodedValue !=` `null``) {``String fieldKey = getFieldKey(classType, field.getName(), field.getType());``fieldValueMap.put(fieldKey, encodedValue);``}``}``// 分析 <clinit> 方法``for` `(Method method : classDef.getMethods()) {``if` `(method.getName().equals(``"<clinit>"``)) {``MethodImplementation methodImpl = method.getImplementation();``if` `(methodImpl !=` `null``) {``analyzeClinitMethod(methodImpl, fieldValueMap, classType);``}``break``;``}``}``}` |
|-|-|

最后还原后，还有一些函数在外面调用，我准备下一篇文章讲一下具体api，然后手把手带着做一下

![CleanShot 2024-10-02 at 11.05.46.png](https://bbs.kanxue.com/upload/attach/202410/967562_49MCCX62G8NKPWP.png)

![CleanShot 2024-10-02 at 11.06.12.png](https://bbs.kanxue.com/upload/attach/202410/967562_UPYWJNRJKX2ZK5V.png)

这个留给下一篇文章进行详细讲解然后解决，其实解决起来也非常的容易，大家可以尝试一下

坑点：app是多个dex的，有两种解决方式

第一种合并dex（我采用的）

第二种收集多个dex的静态字段，建立maps映射（朋友实现的）

我现在给出合并dex的思路和脚本（大家需要自行下载一下jar包）

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667 | `import` `os``import` `subprocess``import` `zipfile``import` `shutil` `# 定义路径``apk_file` `=` `"demo.apk"``baksmali_cmd` `=` `"java -jar /Users/mac/PycharmProject/jebmerge/baksmali-2.5.2.jar"``smali_cmd` `=` `"java -jar /Users/mac/PycharmProject/jebmerge/smali-2.5.2.jar"``tmp_dir` `=` `"tmp"``output_dex` `=` `"classesres.dex"` `def` `extract_apk(apk_path, output_dir):``print``(``"正在解压APK文件..."``)``with zipfile.ZipFile(apk_path,` `'r'``) as apk:``apk.extractall(output_dir)``print``(f``"APK文件已解压至 {output_dir}"``)` `# 第二步：使用 baksmali 解压 dex 文件``def` `dex_to_smali(dex_file, output_dir):``print``(f``"正在处理 {dex_file} 转换为 smali..."``)``subprocess.run(``[``'java'``,` `'-jar'``,` `'/Users/mac/PycharmProject/jebmerge/baksmali-2.5.2.jar'``,` `'d'``, dex_file,` `'-o'``, output_dir],``check``=``True``)` `# 第三步：合并smali文件生成新的 dex 文件``def` `smali_to_dex(smali_dir, output_dex):``print``(f``"正在合并 smali 生成新的 {output_dex} 文件..."``)``subprocess.run(``[``'java'``,` `'-jar'``,` `'/Users/mac/PycharmProject/jebmerge/smali-2.5.2.jar'``,` `'a'``, smali_dir,` `'-o'``, output_dex],``check``=``True``)` `# 执行流程``def` `main():``if` `os.path.exists(tmp_dir):``shutil.rmtree(tmp_dir)``os.makedirs(tmp_dir)` `extract_apk(apk_file, tmp_dir)` `dex_files` `=` `[os.path.join(tmp_dir, f)` `for` `f` `in` `os.listdir(tmp_dir)` `if``f.startswith(``"classes"``)` `and` `f.endswith(``".dex"``)]` `for` `dex_file` `in` `dex_files:``smali_output_dir` `=` `os.path.join(tmp_dir,` `"smali_"` `+` `os.path.basename(dex_file).replace(``".dex"``, ""))``dex_to_smali(dex_file, smali_output_dir)` `merged_smali_dir` `=` `os.path.join(tmp_dir,` `"merged_smali"``)``if` `os.path.exists(merged_smali_dir):``shutil.rmtree(merged_smali_dir)``os.makedirs(merged_smali_dir)` `for` `smali_dir` `in` `os.listdir(tmp_dir):``if` `smali_dir.startswith(``"smali_"``):``smali_subdir` `=` `os.path.join(tmp_dir, smali_dir)``for` `root, dirs, files` `in` `os.walk(smali_subdir):``for` `file` `in` `files:``file_path` `=` `os.path.join(root,` `file``)``rel_path` `=` `os.path.relpath(file_path, smali_subdir)` `# 获取相对路径``dest_path` `=` `os.path.join(merged_smali_dir, rel_path)``os.makedirs(os.path.dirname(dest_path), exist_ok``=``True``)``shutil.copyfile(file_path, dest_path)` `smali_to_dex(merged_smali_dir, output_dex)` `if` `__name__` `=``=` `"__main__"``:``main()` |
|-|-|

### 第二种形式：(下一篇文章主要围绕着这个形式）

| 123456 | `JAVA语法树层面(IJavaSourceUnit部件)``(``1``)遍历某Method所有AST元素``(``2``)解析``if``...``else``元素``(``3``)解析call元素``(``4``)解析``try``元素``(``5``)解析``for``元素` |
|-|-|

提前预告:JSAST的思路都可以引入进来，做自己的反混淆插件，比如常量折叠，反控制流平坦化。

这一篇章就是基于JEB提供的一系列AST接口来实现，而且我推断官方内置的就是使用这种方式来实现的，总的来看Java层面的混淆比较难做，碍于Java字节码的机制，对于调用树恢复的程度很高。

Java层面的反混淆的对抗成本和开发成本是对等的（混淆和去混淆都用的一个库，基于dex层面做）

脚本还有一些瑕疵需要完善，近期会上传。

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2024-10-2 11:18*

感谢分享

## 回复 by mie mie (#3)

*2024-10-2 11:46*

感谢分享![image](https://bbs.kanxue.com/view/img/face/34.gif)

## 回复 by walkline (#4)

*2024-10-2 22:03*

![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 墨穹呢 (#5)

*2024-10-2 22:20*

感谢分享

## 回复 by 正己 (#6)

*2024-10-3 11:13*

师傅牛逼！![image](https://bbs.kanxue.com/view/img/face/20.gif)

## 回复 by koflfy (#7)

*2024-10-8 11:41*

感谢分享

## 回复 by 养只猫不好么 (#8)

*2024-10-9 10:58*

感谢分享

## 回复 by wx_Dispa1r (#9)

*2024-10-15 09:25*

期待下一篇

## 回复 by coneco (#10)

*2024-11-12 09:47*

感谢分享！

## 回复 by 珍惜Any (#11)

*2024-11-12 14:54*

这种java混淆的贼简单，直接丢到dexlib2里面去做一次优化，出来就行了。

## 回复 by 棕熊 (#12)

*2024-11-12 16:51*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  这种java混淆的贼简单，直接丢到dexlib2里面去做一次优化，出来就行了。
>
>

是这样的，主要还是用的jeb自带的反混淆，不过反混淆和混淆的成本接近，不像native层那样

## 回复 by 陈某人 (#13)

*2024-11-12 19:20*

学习

## 回复 by bullyxy (#14)

*2024-12-11 21:39*

现在没法直接设为 final，里面有修改了。![image](https://bbs.kanxue.com/upload/attach/202412/790572_HDEJWGBJFP29P74.webp)

## 回复 by 棕熊 (#15)

*2025-1-10 14:50*

>
> [bullyxy](https://bbs.kanxue.com/user-790572.htm)
>
>  现在没法直接设为 final，里面有修改了。
>
>

麻烦发一下样本

## 回复 by 月清晖 (#16)

*2025-8-19 19:26*

期待下一篇，还有下文吗？
