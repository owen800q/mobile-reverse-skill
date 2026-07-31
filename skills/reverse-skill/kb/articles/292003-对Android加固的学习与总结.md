---
title: '[原创]对Android加固的学习与总结'
url: https://bbs.kanxue.com/thread-292003.htm
tid: 292003
author: ODcat
date: '2026-07-13'
tags: [Android安全, 原创, 脱壳反混淆, 基础理论]
crawled_at: '2026-07-31T13:31:06+08:00'
replies: 3
---

以下是个人搜索资料修改以及使用ai辅助总结的学习笔记，本人小白一枚，如有错误，还请指正，感谢各位读者观看。

# 1、加固技术进化史

##  （1）一代：整体加密壳

 **原理**：在应用打包阶段，将原始的`classes.dex`文件用加密算法进行整体加密。

 **加固流程**：

 1）**打包新APK**：将加密后的DEX文件与一个用于解密的“壳程序”打包成新的APK。

 2）**壳程序解密**：应用启动时，壳程序首先获得控制权，在内存中将加密的DEX文件解密还原。

 3）**类加载器加载**：最后通过自定义的类加载器（`DexClassLoader`或`InMemoryDexClassLoader`）将解密后的DEX加载到内存中供程序运行。

 **加载方式**：

 1）**落地加载 (`DexClassLoader`)**：解密后的DEX文件会先以文件形式临时存放到设备的私有目录中，然后再通过`DexClassLoader`加载。

 2）**不落地加载 (`InMemoryDexClassLoader`)**：解密后的DEX文件不会写入磁盘，而是直接在内存中完成加载。

 **特征**：当DEX被解密并加载到内存后，其数据是完整且连续的内存块。

##  （2）二代：抽取壳

 **原理**：将DEX文件中每个方法的具体实现（Code Item）抽走并加密存储，在原位置置空。

 **加固流程**：

 1）**解析定位**：加固厂商在加壳阶段，会解析原始DEX文件，根据类名、方法名和签名等信息，定位到每个方法的指令集起始位置和长度。

 2）**抽取填充**：找到后，使用空指令或全0数据填充到原位置，将真正的字节码抽走并加密保存。
 3）**修正校验**：最后，重新计算并修正DEX文件的校验和与签名。

 4）**静态结果**：在静态分析的DEX文件里，关键方法都变成了空函数。

 **加载方式**：第一次运行某个被抽空的方法时，壳的代码会介入拦截并调用系统加载方法的函数。在方法真正执行前，壳解密出对应的原始字节码，并临时填回内存中该方法对应的区域。填充完成后，虚拟机执行该方法。执行完毕后，再次将字节码抽走，使其在内存中恢复为空状态。

 **特征**：

 1）内存中无完整DEX。

 2）被抽取的代码在内存中以碎片形式存在，仅在方法被调用的短暂瞬间才完整出现。

##  （3）三代：虚拟机保护 (VMP) 与 Java2C

###  A.VMP（Virtual Machine Protection）

 **原理**：用一套厂商自研的、非标准的“虚拟机”来替代Android原生虚拟机（Dalvik/ART）执行代码，从“语言”层面进行替换字节码。

 **加固流程**：

 1）**指令抽取与转换**：在加壳阶段，将DEX文件中受保护方法的原始Dalvik字节码抽取出来。

 2）**自定义指令集**：将这些标准字节码，按照厂商自定义的规则，转换（或映射）成一套只有自己“虚拟机”才能识别的自定义指令集。

 3）**原始指令销毁**：原始的Dalvik字节码被彻底销毁，不再存在于DEX文件中。

 4）**内置解释器**：在APK的Native层（.so文件）内置一个对应的“解释器”（Handler）。当应用运行到被保护的方法时，会进入这个解释器，由它来读取并执行那些自定义指令。

 **加载方式**：执行自定义指令时，解释器会通过一个巨大的`switch-case`结构来解析每一条指令的操作码（opcode）和操作数（operand），然后执行相应的处理函数。对于加减乘除等简单逻辑，解释器可直接处理；而对于`invoke`、`iget`等需要与系统交互的复杂指令，则需通过JNI调用Android原生接口来完成。

 **特征**：

 1）代码彻底“消失”，在`classes.dex`中，被保护的方法体被清空，取而代之的是一些无意义的桩代码或Native函数声明。

 2）所有函数共享解释器，对于VMP保护的函数，它们的执行都通过同一个解释器，导致其**注册地址（在内存中的入口点）非常相似，函数逻辑也高度雷同**。

###  B.Java2C (Dex2C)

 **原理**：将Java/Kotlin编写的核心代码，在编译成APK之前，就提前“编译”成C/C++代码，然后再编译成Native层的.so库文件。其灵感部分来源于Google的`DEX2OAT`技术（Android运行时将DEX预编译为机器码）。加固厂商将这个“编译”过程提前到了加固阶段。

 **加固流程**：

 1）**代码解析**：对DEX文件中的Java字节码进行词法和句法分析。

 2）**代码转换**：将分析后的逻辑等价地转换为C/C++代码。

 3）**编译成SO**：将生成的C/C++代码通过NDK编译成不可读的Native机器码（.so文件）。

 **特征**：

 1）核心逻辑从Java层完全转移到了Native层。

 2）每个函数独立编译。不同于VMP的共享解释器，Java2C为每个被保护的函数都生成了独立的、不同的Native代码。因此，**每个函数的注册地址和内部逻辑都是独一无二的**。

 3）不可逆。从编译原理上讲，从C/C++代码到机器码的编译过程是不可逆的，因此从Native代码还原出原始的Java逻辑几乎不可能。

# 2、对抗手段

##  （1）一代：整体加密壳

 **对抗思路**：内存DUMP，在DEX被解密并加载到内存的瞬间进行Dump。

 **常用手段**：

 1）**Hook脱壳法**：使用Frida或Xposed等框架，Hook与DEX加载相关的关键函数（如`dvmDexFileOpenPartial`或`ClassLoader.loadClass`）。

 2）**内存搜索Dump法**：在App运行时，通过分析进程的内存映射（`/proc/[pid]/maps`），搜索DEX文件特有的文件头魔数（如`dex.035`），定位DEX在内存中的位置后进行Dump。

 3）**动态调试脱壳法**：使用IDA Pro等调试器附加到App进程，在`dvmDexFileOpenPartial`等函数下断点，当断点触发时，通过脚本Dump出内存中的DEX数据。

 4）**缓存/定制系统脱壳法**：对于落地加载的壳，直接从`/data/dalvik-cache`目录获取优化后的`odex`文件；或修改Android系统源码，在系统加载DEX的关键函数中加入Dump逻辑。

 **一代壳的Dump点**：

 1）**Android版本**

| 虚拟机 | 对应Android版本 | 关键SO库 | 核心Dump函数 (举例) |
|-|-|-|-|
| **Dalvik** | Android 4.4及以下 | `libdvm.so` | `dvmDexFileOpenPartial`, `dexFileParse` |
| **ART** | Android 5.0及以上 | `libart.so` | `OpenMemory`, `DexFileLoader::OpenCommon`, `ClassLinker::DefineClass` |

 2）**厂商**

 不同加固厂商有自己的“个性化”Dump点，他们会通过各种技术来对抗通用脱壳方法，因此需要针对性地寻找Dump点。

 **1. 360加固**

 **Dalvik环境下的特殊性**：在Dalvik环境下，360加固**可能并未调用**系统标准的`dvmDexFileOpenPartial`接口，而是自己实现了从内存中加载DEX的代码，因此难以通过Hook标准系统函数找到Dump点。

 **ART环境下的Dump点**：在ART环境下，360加固的可操作空间相对较小。通常在`ClassLinker::DefineClass`函数处获取`dex_file`的`begin`和`size`，然后Dump出原始的`classes.dex`。

 **Hook `memcmp`的另类思路**：在系统校验DEX文件头魔数（Magic Number，如`dex.035`）时进行Dump。这是一种**迂回战术**，利用系统在校验DEX完整性时必须读取明文DEX数据这一特点来定位DEX在内存中的位置。

 **2. 腾讯乐固**

 **Java层Hook ClassLoader**：腾讯乐固的一种常用脱壳方式是在Java层**Hook `ClassLoader`的`loadClass`方法**，获得`loadClass`返回的`Class`对象，然后通过反射调用`getDex`方法获取`Dex`对象，将`Dex`对象提交给写文件线程，去除重复Dex并写出。

 **早期版本的文件头加密**：腾讯乐固的早期版本仅加密DEX文件头（约0x70字节），运行时解密文件头后即可正常加载。这一特征使得早期版本可以通过修复文件头的方式直接脱壳，而不需要完整的内存Dump。

 **3. 梆梆加固**

 **调用系统标准接口**：梆梆加固的免费版或企业版的某些版本，**依然会调用系统的`dvmDexFileOpenPartial`接口**，因此可以直接在该函数处添加Hook进行Dump。

 **ART下的Dump点**：在ART环境下，`dvmRawDexFileOpenArray`函数是一个关键的Dump点。梆梆的加载流程中，经过多个case之后会调用`dvmRawDexFileOpenArray`函数，此时可进行Dump。

 **4. 爱加密**

 **Dalvik下的Dump点**：在Dalvik环境下，爱加密常用的Dump点包括`dvmDexFileOpenPartial`和`dvmResolveClass`等函数。

 **5. 百度加固**

 **调用DvmDex.cpp中的函数**：百度加固常用的Dump点为`DvmDexFileOpenFromFd`，从文件描述符获取DexFile结构。

 **6.阿里加固**

 **核心脱壳点**：`dvmDexFileOpenPartial`。早期阿里加固的核心逻辑是将DEX入口隐藏，但在加载时仍需调用系统函数`dvmDexFileOpenPartial`来完成解析。因此，对该函数下断点并dump其`addr`和`len`参数，是当时最有效的脱壳方式。

##  （2）二代：抽取壳

 **对抗思路**：主动调用，迫使解密，精准Dump。

 **常用手段**：

 1）**被动Hook**：通过Hook类加载过程中的关键函数，在函数被调用、壳完成方法填充后，立即将内存中的方法体Dump下来。

 常见的Hook点包括：

 **Dalvik环境**：`LoadMethod`函数。

 **ART环境**：`ClassLinker::DefineClass`函数

 以ART环境为例，可以Hook `ClassLinker::DefineClass`函数，在该函数被调用时获取`DexFile`对象的`begin`和`size`，进而Dump出DEX文件。如果抽取壳是在`ClassLinker::LoadMethod`函数调用时才对抽取的函数进行回填，则需要Hook `LoadMethod`函数。注意，`LoadMethod`调用有两处——加载直接方法和加载虚方法，两处都需要进行Dump。

 被动Hook的**缺点在于“被动”**。只有当一个类被**显式加载**（通过`Class.forName()`或`ClassLoader.loadClass()`）或**隐式加载**（创建实例或访问静态成员）时，才会触发`LoadMethod`的调用，壳才会对抽取的函数进行回填。

 2）**主动调用**：为了解决被动Hook的局限，产生了“主动调用”的脱壳方案。其核心思路是在App启动后，主动遍历并加载DEX中的所有类，迫使壳为每一个方法都执行一遍“解密-填充”流程。

 **具体实现原理**（以Frida为例子）：

 **第一步：遍历所有ClassLoader**：通过`Java.enumerateClassLoadersSync()`获取应用中的所有`ClassLoader`。

 **第二步：通过ClassLoader获取所有DEX文件**：在Android的`ClassLoader`体系（如`BaseDexClassLoader`）中，每个ClassLoader都包含一个`DexPathList`对象，该对象内部有一个`Element[]`数组，数组的每一项对应一个DEX文件。

 具体反射链路如下：

```java
ClassLoader
  → pathList (DexPathList对象)
    → dexElements (Element[])
      → Element[i].dexFile (DexFile对象)
```

 **第三步：枚举所有类名并主动加载**：通过`DexFile.entries()`方法获取该DEX文件中所有的类名，然后调用`ClassLoader.loadClass(className)`进行主动加载。

```javascript
function dealwithClassLoader(classloader) {
    var dexFile = classloader.pathList.dexElements[i].dexFile;
    var classNames = dexFile.entries();  // 获取所有类名
    while (classNames.hasMoreElements()) {
        var className = classNames.nextElement();
        classloader.loadClass(className);  // 主动加载，触发壳解密
    }
}
```

 **第四步：配合Hook点进行Dump**：在主动调用的过程中，配合Hook点（如`LoadMethod`或`ClassLinker::DefineClass`）进行Dump，就能获取到一份相对完整的、所有方法体都已填充的DEX文件。需要注意内存中DEX的**起始地址和大小**，以及**正确的脱壳时机**和**Android版本兼容性**，因为Android 7.1及之前，Java层有`Dex#getBytes`方法可直接获取DEX数据；Android 8.0之后该方法被移除，需要通过`mCookie`字段在Native层获取`DexFile`。

##  （3）三代：虚拟机保护 (VMP) 与 Java2C

###  A.VMP（Virtual Machine Protection）

 **方法一、分析解释器逻辑**

 首先要了解VMP解释器的基本结构——VMP解释器的核心是经典的 **“取指-解码-执行”（Fetch-Decode-Execute）循环**。

```c
while (true) {
    // 1. 取值 (Fetch)
    unsigned char opcode = *vip++;  // 从指令流中读取操作码

    // 2. 译码 (Decode) 并 3. 执行 (Execute)
    switch (opcode) {  // 根据自定义操作码跳转到对应的处理函数
        case OP_ADD:   // 如果是加法指令
            // ... 执行加法的具体代码 ...
            break;
        case OP_MOV:   // 如果是移动数据指令
            // ... 执行移动数据的具体代码 ...
            break;
        // ... 其他成百上千的指令处理分支 ...
    }
}
```

 接下来要定位定位VMP入口（vm_entry）。被虚拟化的函数，其内部所有逻辑会变成只跳转到虚拟机入口`vm_entry`。利用这一特点，可以定位虚拟机入口。

 定位规则如下：

 1）**只有一个函数调用**。

 2）**调用完恢复栈帧。**

 3）**紧接着直接RET。**

 4）对于大型APK，同一个`vm_entry`很可能被多个地方调用——调用次数多也是一个特征。

 在IDA中定位到`vm_entry`后，通常会遇到反编译失效的问题。这是因为VMP常采用**间接跳转**来对抗静态分析。

 例如：

```c
目标地址 = 返回地址 + *(返回地址 + 索引 × 4)
```

 对应的，可以编写脚本将间接跳转变成直接跳转，然后将patch结果保存到SO文件，重新加载到IDA中进行完整分析。

 然后处理加密跳转表。因为在真实案例中，VMP方案会针对`switch-case`语句进行专门加固，特别是对VMP解释器函数的**跳转表进行加密保护**。

 **ARM64跳转表的标准结构**：

```assembly
; 加载跳转表基址
.text:0D3144  ADRL   X9, jpt_D3164    ; X9 = 跳转表基址 - offset_table
.text:0D314C  ADR    X10, loc_D3168   ; X10 = 标签计算基址 - base_address
; 从跳转表取出偏移量
.text:0D3150  LDRH   W11, [X9,X8,LSL#1]  ; W11 = offset_table[X8]
; 计算最终跳转地址
.text:0D3154  ADD    X10, X10, X11,LSL#2  ; X10 = base_addr + offset*4
.text:0D3164  BR     X10                  ; 跳转到目标地址
```

 跳转表在内存中的实际布局：

```c
.rodata:0171ACC  DCW  0x217   ; case 0 的偏移量
.rodata:0171ACE  DCW  0x22A   ; case 1 的偏移量
.rodata:0171AD0  DCW  0x22C   ; case 2 的偏移量
.rodata:0171AD2  DCW  0x2FA   ; case 3 的偏移量
```

 所有case标签地址都基于同一个基址计算，这是还原虚拟机控制流的关键。通过识别并解密加密的跳转表，可以让IDA正确识别VMP解释器的控制流结构。

 仅接着需要获取指令Trace，拿到Trace是VMP分析成功的关键一步。

 获取Trace的常用方法包括：

 1）**IDA Trace**：使用IDA的trace功能记录指令执行流。

 2）**Unidbg / AndroidNativeEmu**：在PC端模拟执行SO，获取完整trace。

 3）**Frida Stalker**：Frida的代码跟踪引擎，可精细跟踪每条指令。

 4）**Frida QBDI**：基于QBDI的动态二进制插桩。

 5）**Dobby Instrument**：轻量级指令级插桩框架。

 6）**Unicorn 虚拟CPU**：基于QEMU的CPU模拟器。

 最后定位取值（Fetch）,通过Trace分析定位取值阶段。

 具体方法：

 1）通过JNITrace分析函数大致执行逻辑，使用**指令级Trace**，通过指令块循环次数结合函数指令大小实现突破。

 2）利用有源码的函数开头的稳定特征，监控读取操作精准命中。

 实操中，可以通过分析函数开头的指令大小来定位内存中加密后的函数指令位置。例如：某`onCreate`函数存在58条指令，在Trace日志中发现某个代码块出现了58次——正好对应58条指令——即可标记该地址为**取指令行为**。确定取指令地址后，下监控断点验证，然后分析取值后的操作（如字节码解密处理）。

 **方法二、内存监控与映射还原**

 在VMP解释器执行过程中，会在内存中产生特定的数据流。通过实时监控VMP虚拟机的寄存器状态与内存访问模式，精准定位虚拟指令到真实指令的映射关系。

 具体来说，Dalvik有256个指令，意味着最多只需要破解255次。通过找到规律，可以将自定义字节码直接全部翻译。

 这种方法的核心在于**建立Opcode映射表**——将VMP的自定义操作码（Opcode）映射回标准的Dalvik/ARM指令。

 自动化方案，腾讯安全ApkPecker提供了一个自动化脱壳方案：ApkPecker在确定厂商字节码格式的基础上，通过**AI学习厂商解释器二进制中opcode handler的运行时行为**，从而自动化恢复出厂商解释器的opcode语义，还原出原始Dalvik字节码，并重写DEX文件。

 这种方法不依赖人工逆向每条指令，而是通过机器学习的方式自动建立映射关系。

 **方法三、针对性Hook**

 由于VMP最终仍需通过JNI调用系统API，可以Hook这些关键的系统函数，从运行时的行为反推其逻辑。

 1.）Hook JNI_OnLoad

 `JNI_OnLoad`是SO库加载时第一个被调用的函数，常在此时进行动态注册。通过Hook `JNI_OnLoad`，可以追踪哪些函数被注册到哪个地址和了解VMP的工作原理和初始化流程。

 2）Hook JNI函数调用链

 一种有效的穿透式Hook方法是——用Frida Hook住JNI_OnLoad后连续Hook住后续所有`env->CallObjectMethod`调用，逐层打印参数类型和返回值。

 这种方法完全不用关注指令如何混淆、控制流如何变化，而是根据Frida Hook日志去分析。

 3. Hook RegisterNatives

 通过Hook `RegisterNatives`函数，可以追踪Native方法的动态注册过程。

 4. Hook ShadowFrame（ART解释模式）

 在ART解释模式下，**ShadowFrame**包含了方法的局部变量数组、指向DexFile和Method对象的引用等关键信息。通过Frida Hook相关JNI函数并访问ShadowFrame，

 可以实时获取每一个被解释执行的方法名、获取所属类、参数值以及调用上下文和定位受VMP保护的关键函数。

###  B.Java2C (Dex2C)

 **方法一、Native层逆向**

 Java2C将Java代码通过词法、句法分析，生成对应的C代码，然后编译成SO动态库。因此面对的就是**汇编/LLVM IR**。与传统VMP不同，Java2C壳对每个Java函数进行独立编译，**每个函数的内容都是不同的，函数的注册地址也不同**。可通过分析SO文件还原算法逻辑。

 Java2C通常采用JNI动态注册方式。搜索`JNI_OnLoad`方法是分析Java2C的入口。在`JNI_OnLoad`中通过`FindClass`获取目标类（如`MainActivity`），然后调用`RegisterNatives`注册JNI方法，分析每个JNI方法对应一个Native函数地址

 **方法二、动态调试与Hook**

 1）Frida Hook JNI调用链

 与VMP类似，Java2C也通过JNI与Java层交互。通过Hook JNI函数调用，可以监控Java与Native层的交互数据，推断其逻辑。

 2）Unidbg模拟执行

 Unidbg可以在PC端模拟执行SO文件中的函数，无需真实手机环境。在模拟执行过程中，算法是黑盒，不直接分析这个黑盒，而是直接让程序运行，观察程序运行逻辑。

# 3、反加固工具

 对大家熟悉的IDA Pro、Jadx、AndroidStudio、MT管理器等工具就不过多介绍了。

 **（1）BlackDex**

 BlackDex是一款运行在Android手机上的脱壳工具，**无需Root权限**即可使用，支持多个Android版本以及已安装和未安装的APK，原理是利用系统漏洞直接从内存中提取DEX文件。

 **（2）drizzleDumper**

 drizzleDumper是一款基于**内存搜索**的Android脱壳工具。原理是基于内存暴力搜索DEX文件头魔数（`dex.035`）。

 **（3）FDex2**

 FDex2是一款基于Xposed框架的脱壳模块。通过Hook `ClassLoader`的`loadClass`方法，反射调用`getDex`方法取得`Dex`对象，再将里面的DEX写出。

 **（4）FunDex**

 FunDex是一款基于Xposed/LSPosed框架的脱壳工具，支持Android 5至13，支持类抽取型加固。

 **（5）dumpDex**

 dumpDex是一款基于Xposed的脱壳工具，通过Hook ClassLoader的loadClass方法实现DEX提取。

 **（6）frida-dexdump**

 由葫芦娃大佬开发的基于Frida的DEX脱壳工具。原理是利用Frida动态插桩技术，在目标应用运行时从内存中提取DEX文件。纯Python实现，可以通过pip安装

 **（7）FridaContainer**

 FridaContainer整合了网上流行的和开发者自己编写的常用Frida脚本，是模块化脚本集合。

 **（8）FART（FART-Fix）**

 FART是寒冰大佬开发的**ART环境下基于主动调用的自动化脱壳方案**。通过修改Android源码，在解释器执行路径中插入监控点，实现三步脱壳：Dump DEX → 主动调用 → 修复CodeItem。

 **（9）Youpk**

 Youpk是另一款基于ART的**主动调用脱壳机**，针对DEX整体加固和各种DEX抽取加固。其基本流程包括从内存中Dump DEX，然后通过主动调用类中的所有方法触发加固壳的解密逻辑。

 **（10）DexHunter**

 DexHunter是一款**基于Android运行时源码修改**的通用自动脱壳工具。它由修改后的ART和DVM运行时组成，需替换Android源码中的原始内容。

 **（11）Unidbg**

 Unidbg是一个基于Unicorn的逆向工具，可以在PC端**模拟执行Android和iOS的SO文件**。

---

# 回复

## 回复 by 陈芸欣 (#2)

*2026-7-13 21:02*

先收藏了，有空再看

## 回复 by ODcat (#3)

*2026-7-13 23:45*

>
> [陈芸欣](https://bbs.kanxue.com/user-1069722.htm)
>  先收藏了，有空再看
>

收到！![image](https://bbs.kanxue.com/view/img/face/062.gif)

## 回复 by Imxz (#4)

*2026-7-14 17:16*

tql
