---
title: '[原创]深入浅出 Keystone 框架学习'
url: https://bbs.kanxue.com/thread-289573.htm
tid: 289573
author: xiusi
date: '2025-12-26'
tags: [Android安全, 原创, 逆向分析, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T15:17:26+08:00'
replies: 30
---

# 深入浅出 Keystone 框架学习

## 一、前言

通过此前的文章，我们已经掌握了两大框架。在逆向工程的工具链中，它们各司其职：

- **Unicorn (大脑)** ：负责**跑**代码。它模拟 CPU 的状态流转与内存交互。

>
> [[原创]深入浅出 Unicorn 框架学习](https://bbs.kanxue.com/thread-289502.htm)
>
>
>
- **Capstone (眼睛)** ：负责**看**代码。它将枯燥的机器码翻译成人类可读的汇编语言。

>
> [[原创]深入浅出 Capstone 框架学习](https://bbs.kanxue.com/thread-289541.htm)
>
>
>

然而，仅有“大脑”和“眼睛”是不够的。当我们想要修改程序的逻辑（例如 Patch 掉反调试检查、注入 Shellcode）时，我们需要——**Keystone (双手)** 。

### 1. 什么是 Keystone？

**Keystone** 是一个轻量级、多平台、多架构的汇编框架。它的作用与 Capstone 正好相反：**Capstone 将机器码转为汇编，而 Keystone 将汇编代码编译回机器码。**

### 2. Keystone 的核心价值

- **人类可读 -> 机器可读**
例如，将 `INC RAX` 瞬间转换为 `\x48\xFF\xC0`。
- **多架构支持**
一套 API 搞定 x86, ARM, MIPS, PowerPC, SPARC 等所有主流架构，无需安装笨重的 GCC 或各种交叉编译工具链。
- **动态灵活**
它是一个库（Library），而不是一个独立的编译器。这意味着你可以在 Python 脚本运行时动态生成代码，无需调用外部程序。

---

## 二、环境准备与基础概念

### 1. 环境安装

| 12345 | `# 正确做法：安装 Keystone 汇编引擎``pip` `install` `keystone-engine` `# 错误做法：安装 'keystone'``# 'keystone' 是 OpenStack 的身份认证组件，装错会导致冲突！` |
|-|-|

### 2. 核心类解析

在 Python 脚本中，我们主要使用以下两个类：

- **`Ks`** **(Keystone Engine)**
这是汇编引擎的主入口。你需要实例化它来创建一个汇编器对象。

	- *初始化*：`ks = Ks(arch, mode)`
	- *核心方法*：`ks.asm(code_string, addr)`
- **`KsError`** **(Exception)**
异常处理类。当你的汇编代码有语法错误（如拼写错误、操作数不匹配）时，Keystone 会抛出此异常。

### 3. 架构与模式 (Architecture & Mode)

Keystone 的常量命名规范与 Unicorn/Capstone 保持高度一致，只需将前缀 `UC_` 或 `CS_` 换成 **`KS_`** 即可。

**常用组合对照表**：

| 目标环境 | Unicorn | Capstone | Keystone |
|-|-|-|-|
| **x86 (32位)** | `UC_ARCH_X86`,`UC_MODE_32` | `CS_ARCH_X86`,`CS_MODE_32` | **`KS_ARCH_X86`** **,****`KS_MODE_32`** |
| **x64 (64位)** | `UC_ARCH_X86`,`UC_MODE_64` | `CS_ARCH_X86`,`CS_MODE_64` | **`KS_ARCH_X86`** **,****`KS_MODE_64`** |
| **ARM (32位)** | `UC_ARCH_ARM`,`UC_MODE_ARM` | `CS_ARCH_ARM`,`CS_MODE_ARM` | **`KS_ARCH_ARM`** **,****`KS_MODE_ARM`** |
| **ARM Thumb** | `UC_ARCH_ARM`,`UC_MODE_THUMB` | `CS_ARCH_ARM`,`CS_MODE_THUMB` | **`KS_ARCH_ARM`** **,****`KS_MODE_THUMB`** |

### 4. 语法格式 (Syntax)

对于 x86 架构，汇编语言有不同的格式。Keystone 允许通过 `KS_OPT_SYNTAX` 选项来切换语法风格。

- **`KS_OPT_SYNTAX_INTEL`** (默认)：Intel 语法。

	- *特点*：`mov dst, src`。绝大多数逆向工具（IDA, x64dbg）的默认风格。
	- *示例*：`mov eax, 1`
- **`KS_OPT_SYNTAX_ATT`**：AT&T 语法。

	- *特点*：`mov src, dst`，寄存器前加 `%`，立即数加 `$`。Linux/GDB 常用。
	- *示例*：`mov $1, %eax`
- **`KS_OPT_SYNTAX_NASM`**：NASM 语法。

	- *特点*：与 Intel 类似，但在内存寻址和宏处理上更严格。

**设置方法**：

| 123 | `ks` `=` `Ks(KS_ARCH_X86, KS_MODE_64)``# 切换到 AT&T 语法``ks.syntax` `=` `KS_OPT_SYNTAX_ATT` |
|-|-|

---

## 三、静态汇编初体验

在将 Keystone 集成到 Unicorn 之前，我们先单独运行它，体验一下如何将一句汇编代码翻译成机器码。

**目标**

将汇编指令 `"xor rax, rax; inc rax"` 编译为 x64 机器码。

**示例代码：**

| 1234567891011121314151617181920212223242526272829303132 | `from` `keystone` `import` `*` `# 1. 准备汇编代码``# 使用分号 ; 分隔多条指令``ASSEMBLY` `=` `"xor rax, rax; inc rax"` `try``:``# 2. 初始化汇编引擎``# 架构: x86, 模式: 64位``ks` `=` `Ks(KS_ARCH_X86, KS_MODE_64)` `# 3. 执行编译 (Assemble)``# ks.asm(code, addr=0)``# code: 汇编字符串``# addr: (可选) 起始地址，用于计算相对跳转偏移，默认为 0``encoding, count` `=` `ks.asm(ASSEMBLY)` `# 4. 输出结果``print``(f``"Assembly: {ASSEMBLY}"``)``print``(f``"Encoding: {encoding}"``)` `# 原始列表``print``(f``"Count   : {count}"``)` `# 指令数量` `# 关键步骤：将 list[int] 转换为 bytes``# Unicorn 的 mem_write 需要 bytes 类型``machine_code` `=` `bytes(encoding)``print``(``"Machine Code: "``,end``=``"")``for` `i` `in` `range``(``len``(machine_code)):``print``(f``"{machine_code[i]:02x}"``, end``=``" "``)``print``()` `except` `KsError as e:``print``(f``"ERROR: {e}"``)` |
|-|-|

**运行结果：**

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_USMDN6B2X23RQQA.png)

### 核心 API 详解：`ks.asm()`

`ks.asm()` 方法的返回值是一个元组 `(encoding, count)` ：

1. **`encoding`** **(list[int])** ：

	- 这是一个**整数列表**，例如 `[0x48, 0x31, 0xC0]`。
	- **注意**：它**不是** Python 的 `bytes` 对象！如果直接把它传给 `uc.mem_write`，Unicorn 会报错。
	- **正确做法**：使用 `bytes(encoding)` 将其转换为二进制字节流。
2. **`count`** **(int)** ：

	- 表示成功编译的汇编语句数量（以 `;` 分隔）。
	- 如果编译失败（如语法错误），Keystone 会抛出 `KsError` 异常，而不是返回错误码。

---

## 四、核心实战：Unicorn + Keystone Patch

### 场景 1：NOP 填充

**需求**：
在逆向分析中，我们经常遇到反调试指令（如 `RDTSC`、`CPUID`）或者不需要执行的垃圾代码。
假设在地址 `0x400000` 处有一条复杂的指令（例如 `XOR EAX, EAX`，长度 2 字节），我们希望将其“抹去”，替换为 `NOP`（空指令），让 CPU 什么都不做直接滑过去。

**示例代码**：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354 | `from` `unicorn` `import` `*``from` `unicorn.x86_const` `import` `*``from` `keystone` `import` `*``from` `capstone` `import` `*` `# 1. 初始化所有引擎``mu` `=` `Uc(UC_ARCH_X86, UC_MODE_64)``ks` `=` `Ks(KS_ARCH_X86, KS_MODE_64)``cs` `=` `Cs(CS_ARCH_X86, CS_MODE_64)` `# 2. 准备内存环境``ADDRESS` `=` `0x400000``MEM_SIZE` `=` `2` `*` `1024` `*` `1024``mu.mem_map(ADDRESS, MEM_SIZE)` `# 写入原始代码: xor eax, eax (2字节) + inc eax (2字节)``# 机器码: 31 c0 ff c0``ORIGINAL_CODE` `=` `b``"\x31\xc0\xff\xc0"``mu.mem_write(ADDRESS, ORIGINAL_CODE)` `print``(``"--- [Before Patch] ---"``)``for` `insn` `in` `cs.disasm(mu.mem_read(ADDRESS,` `4``), ADDRESS):``print``(f``"0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}"``)` `# ==========================================``# 3. 核心操作：NOP Patch``# ==========================================``TARGET_ADDR` `=` `0x400000``PATCH_LEN` `=` `2`  `# 需要覆盖的长度 (xor eax, eax 是 2 字节)` `print``(f``"\n[*] Patching {TARGET_ADDR:x} with {PATCH_LEN} NOPs..."``)` `# 生成 NOP 机器码 ("nop; nop")``# encoding -> [0x90, 0x90]``encoding, _` `=` `ks.asm(``"nop; "` `*` `PATCH_LEN)` `# 写入内存覆盖原指令``mu.mem_write(TARGET_ADDR, bytes(encoding))` `# ==========================================``# 4. 验证结果``# ==========================================``print``(``"\n--- [After Patch] ---"``)``# 读取内存查看变化``patched_code` `=` `mu.mem_read(ADDRESS,` `4``)``for` `insn` `in` `cs.disasm(patched_code, ADDRESS):``print``(f``"0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}"``)` `# 模拟执行验证``print``(``"\n[*] Executing..."``)``mu.reg_write(UC_X86_REG_RAX,` `10``)` `# 初始值 10``mu.emu_start(ADDRESS, ADDRESS` `+` `4``)``print``(f``"RAX = {mu.reg_read(UC_X86_REG_RAX)}"``)` `# 结果应为 11 (因为 XOR 被 NOP 掉了，只有 INC 执行了)` |
|-|-|

**运行结果**：

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_XE6ZWE7NEJY48Y3.png)

---

### 场景 2：逻辑篡改 (Hook & Modify)

**需求**：
在破解 CrackMe 或去除混淆时，我们经常遇到关键的分支跳转，例如 `TEST EAX, EAX; JZ 0xTarget`。如果验证失败，程序会跳转到错误处理分支。
我们的目标是：强制将 `JZ`（条件跳转）修改为 `JMP`（无条件跳转），确保程序始终走向我们预期的路径，从而绕过校验。

**核心挑战 (JIT 陷阱)** ：
Unicorn 使用 JIT（即时编译）技术。如果在 `UC_HOOK_CODE` 回调中动态修改当前指令的内存，CPU 实际上已经完成了该指令的取指和解码，Patch 仅对**下一次**执行有效。
因此，对于确定的逻辑修改，最佳实践是在**模拟启动前 (Pre-Patch)** 就完成内存修改。

**示例代码：**

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576777879 | `from` `unicorn` `import` `*``from` `unicorn.x86_const` `import` `*``from` `keystone` `import` `*``from` `capstone` `import` `*` `# 1. 初始化引擎``mu` `=` `Uc(UC_ARCH_X86, UC_MODE_64)``ks` `=` `Ks(KS_ARCH_X86, KS_MODE_64)``cs` `=` `Cs(CS_ARCH_X86, CS_MODE_64)` `# 2. 准备内存与代码``ADDRESS` `=` `0x400000``MEM_SIZE` `=` `2` `*` `1024` `*` `1024``mu.mem_map(ADDRESS, MEM_SIZE)` `# --- 构造模拟场景 ---``# 汇编逻辑：``# 0x400000: XOR EAX, EAX  (EAX = 0)``# 0x400002: INC EAX       (EAX = 1, ZF = 0)``# 0x400004: JZ  0x40000A  (关键跳转：此时不应跳转)``# 0x400006: INC EAX       (EAX = 2, 正常路径)``# 0x40000A: DEC EAX       (EAX = 0, 跳转目标)` `CODE_ASM` `=` `"""``xor eax, eax;``inc eax;``jz 0x40000a;``inc eax;``nop; nop;``dec eax;``"""` `# 编译并写入原始代码``code_bytes, _` `=` `ks.asm(CODE_ASM, ADDRESS)``mu.mem_write(ADDRESS, bytes(code_bytes))` `print``(``"--- [Original Logic] ---"``)``print``(``"Expectation: EAX=1, ZF=0 -> JZ NOT taken -> EAX becomes 2"``)``for` `insn` `in` `cs.disasm(bytes(code_bytes), ADDRESS):``print``(f``"0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}"``)` `# ==========================================``# 3. 核心操作：静态 Patch (Pre-Patch)``# ==========================================``# 目标：将 0x400004 处的 JZ 修改为 JMP``KEY_JUMP_ADDR` `=` `0x400004``PATCH_ASM` `=` `"jmp 0x40000a"` `print``(f``"\n[*] Patching {KEY_JUMP_ADDR:x} to '{PATCH_ASM}'..."``)` `# 编译新指令``# 关键：传入 KEY_JUMP_ADDR 以计算相对偏移``patch_code, _` `=` `ks.asm(PATCH_ASM, KEY_JUMP_ADDR)` `# 覆盖内存``mu.mem_write(KEY_JUMP_ADDR, bytes(patch_code))` `# ==========================================``# 4. 执行验证``# ==========================================``print``(``"[*] Executing..."``)` `try``:``# 从头开始执行``mu.emu_start(ADDRESS, ADDRESS` `+` `len``(code_bytes))``except` `UcError as e:``print``(e)` `# 检查结果``final_eax` `=` `mu.reg_read(UC_X86_REG_EAX)``print``(f``"\n[*] Execution finished. Final EAX = {final_eax}"``)` `# 逻辑验证：``# 原逻辑：1 -> inc -> 2``# Patch后：1 -> jmp -> dec -> 0``if` `final_eax` `=``=` `0``:` `print``(``">>> SUCCESS: Jump taken (Logic altered)!"``)``else``:``print``(``">>> FAILED: Jump not taken."``)` |
|-|-|

**运行结果：**

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_23XB5QTHTFAQP3S.png)

通过这种方式，我们成功地利用 Keystone 改变了程序的控制流，让它按照我们的意愿执行了跳转逻辑。

---

### 场景 3：Shellcode 注入

**需求**：
有时我们需要在程序的空白区域（Cave）注入一段全新的逻辑，比如打印调试信息、Dump 内存数据等。
我们需要在内存 `0x500000` 处写入一段 Shellcode，调用 Linux 的 `write` 系统调用打印 "HACKED"，然后控制 CPU 跳转执行。

**示例代码：**

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172 | `from` `unicorn` `import` `*``from` `unicorn.x86_const` `import` `*``from` `keystone` `import` `*``import` `sys` `# 1. 初始化引擎``mu` `=` `Uc(UC_ARCH_X86, UC_MODE_64)``ks` `=` `Ks(KS_ARCH_X86, KS_MODE_64)` `# 2. 准备内存``# 映射主程序区域（模拟宿主）``mu.mem_map(``0x400000``,` `1024` `*` `1024``)``# 映射 Shellcode 区域``SHELLCODE_ADDR` `=` `0x500000``mu.mem_map(SHELLCODE_ADDR,` `1024` `*` `1024``)` `# 3. 编写 Shellcode (使用三引号编写多行汇编)``# 逻辑：打印 "HACKED" 到 stdout，然后无限循环``CODE_ASM` `=` `"""``mov rdi, 1;``mov rsi, 0x500100;``mov rdx, 6;``mov rax, 1;``syscall;``loop:``jmp loop;``"""` `# 4. 编译并注入``print``(f``"[*] Compiling shellcode at 0x{SHELLCODE_ADDR:x}..."``)``# 传入基址以处理相对跳转``encoding, _` `=` `ks.asm(CODE_ASM, SHELLCODE_ADDR)``machine_code` `=` `bytes(encoding)` `# 写入代码``mu.mem_write(SHELLCODE_ADDR, machine_code)``# 写入字符串数据``mu.mem_write(``0x500100``, b``"HACKED"``)`  `# ==========================================``# 5. 关键步骤：处理 SYSCALL``# ==========================================``# Unicorn 不认识 syscall，必须手动 Hook 模拟``def` `hook_syscall(uc, user_data):``rax` `=` `uc.reg_read(UC_X86_REG_RAX)``if` `rax` `=``=` `1``:``fd` `=` `uc.reg_read(UC_X86_REG_RDI)``buf` `=` `uc.reg_read(UC_X86_REG_RSI)``cnt` `=` `uc.reg_read(UC_X86_REG_RDX)``data` `=` `uc.mem_read(buf, cnt)``print``(f``">>> write({fd}, {data.decode()}, {cnt})"``)` `# 手动推进 RIP``rip` `=` `uc.reg_read(UC_X86_REG_RIP)``uc.reg_write(UC_X86_REG_RIP, rip` `+` `2``)`  `mu.hook_add(UC_HOOK_INSN, hook_syscall,` `None``,` `1``,` `0``, UC_X86_INS_SYSCALL)` `# ==========================================``# 6. 执行 Shellcode``# ==========================================``print``(``"[*] Jumping to shellcode..."``)` `# 强制修改 RIP 指向 Shellcode 入口``mu.reg_write(UC_X86_REG_RIP, SHELLCODE_ADDR)` `try``:``mu.emu_start(SHELLCODE_ADDR, SHELLCODE_ADDR` `+` `len``(machine_code))``except` `UcError as e:``print``(f``"[*] Execution stopped: {e}"``)` |
|-|-|

**运行结果**：

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_YPAY4T39UJWKXH3.png)

通过 Keystone，我们无需手动拼凑机器码，直接用汇编语言就实现了复杂的代码注入功能。

---

## 五、进阶技巧：处理复杂指令与符号

在基础用法之外，Keystone 还提供了一些高级特性来应对特定的编译需求，比如切换汇编风格、处理相对地址计算以及解析符号标签。

### 1. 语法格式 (Syntax Dialects)

对于 x86 架构，汇编语言存在多种格式。Keystone 默认使用逆向工程中最通用的 **Intel 语法**，但也完美支持 Linux/GDB 风格的 **AT&T 语法** 以及更严格的 **NASM 语法**。

**支持的语法常量：**

- **`KS_OPT_SYNTAX_INTEL`** (默认)：Intel 语法。

	- *特点*：`op dst, src`（目标在前）。IDA, x64dbg, MSVC 常用。
- **`KS_OPT_SYNTAX_ATT`**：AT&T 语法。

	- *特点*：`op src, dst`（源在前）。寄存器前加 `%`，立即数前加 `$`。GCC, GDB 常用。
- **`KS_OPT_SYNTAX_NASM`**：NASM 语法。

	- *特点*：与 Intel 类似，但在内存引用和宏处理上更规范。

下面的代码展示了如何切换语法，并验证两种写法的编译结果是否一致。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445 | `from` `keystone` `import` `*``from` `capstone` `import` `*` `# 初始化``ks` `=` `Ks(KS_ARCH_X86, KS_MODE_64)``cs` `=` `Cs(CS_ARCH_X86, CS_MODE_64)` `# --- 场景 A: Intel 语法 (默认) ---``intel_asm` `=` `"mov eax, 1"``print``(f``"[*] Compiling Intel Syntax: '{intel_asm}'"``)` `encoding, _` `=` `ks.asm(intel_asm)``machine_code_intel` `=` `bytes(encoding)` `# 打印机器码 hex``print``(f``"    Machine Code: "``,end``=``"")``for` `i` `in` `machine_code_intel:``print``(f``"{i:02x}"``,end``=``" "``)``print``()` `# --- 场景 B: AT&T 语法 ---``# 切换语法模式``ks.syntax` `=` `KS_OPT_SYNTAX_ATT` `att_asm` `=` `"mov $1, %eax"``print``(f``"\n[*] Compiling AT&T Syntax : '{att_asm}'"``)` `encoding, _` `=` `ks.asm(att_asm)``machine_code_att` `=` `bytes(encoding)` `print``(f``"    Machine Code: "``,end``=``"")``for` `i` `in` `machine_code_att:``print``(f``"{i:02x}"``,end``=``" "``)``print``()` `# --- 验证结果 ---``print``(``"\n[-] Verification:"``)``if` `machine_code_intel` `=``=` `machine_code_att:``print``(``"    Success! Both syntaxes produced the same machine code."``)``# 反汇编看一眼``print``(``"    Disasm Result:"``)``for` `insn` `in` `cs.disasm(machine_code_att,` `0``):``print``(f``"    0x{insn.address:x}: {insn.mnemonic} {insn.op_str}"``)``else``:``print``(``"    Failed! Logic mismatch."``)` |
|-|-|

**运行结果**：

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_QEKYNFY4KVCT6T5.png)

### 2. 符号解析 (Symbol Resolver)

在编写汇编代码时，使用标签（Label）跳转是人类的本能，例如 `jmp loop_start`。然而，Keystone 是一个轻量级编译器，在 Python 绑定中默认并不支持复杂的符号解析回调（Symbol Resolver Callback）。

**Pythonic 解决方案**：利用 Python 强大的字符串格式化功能（**f-string**），在将代码送入 Keystone 编译之前，手动完成符号的“链接”工作。

**示例：**

假设我们需要在地址 `0x401020` 处编写一段逻辑，其中包含跳转到 `0x401000` 和 `0x401050` 的指令。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748 | `from` `keystone` `import` `*``from` `capstone` `import` `*` `# 1. 初始化引擎 (x86-64)``ks` `=` `Ks(KS_ARCH_X86, KS_MODE_64)``cs` `=` `Cs(CS_ARCH_X86, CS_MODE_64)` `# 2. 定义符号表 (Symbol Table)``# 模拟程序中的关键地址``SYMBOLS` `=` `{``"LOOP_START"``:` `0x401000``,``"FUNC_EXIT"``:` `0x401050``}` `# 当前代码的写入地址 (基址)``# Keystone 需要这个地址来计算相对跳转的偏移量``CURRENT_ADDR` `=` `0x401020` `# 3. 编写汇编 (使用 f-string 动态替换符号)``# Python 会自动将 {SYMBOLS['...']} 替换为对应的整数地址``asm_code` `=` `(f``"inc rax;"``f``"cmp rax, 10;"``f``"jne {SYMBOLS['LOOP_START']};"`  `# 跳转到 0x401000``f``"jmp {SYMBOLS['FUNC_EXIT']}"``)` `# 跳转到 0x401050` `print``(f``"[*] Assembling code at 0x{CURRENT_ADDR:x}:"``)``print``(``"-"` `*` `30``)``print``(asm_code)``print``(``"-"` `*` `30``)` `try``:``# 4. 执行编译``# 关键：必须传入 CURRENT_ADDR 作为第二个参数``# 否则 Keystone 会认为基址是 0，导致生成的跳转偏移量错误``encoding, count` `=` `ks.asm(asm_code, CURRENT_ADDR)``machine_code` `=` `bytes(encoding)` `# 5. 输出机器码``print``(f``"[*] Encoded {count} instructions."``)``print``(f``"[*] Machine Code : {machine_code.hex()}"``)` `# 6. 反汇编验证 (使用 Capstone)``print``(``"\n[-] Disassembly Verification:"``)``for` `insn` `in` `cs.disasm(machine_code, CURRENT_ADDR):``print``(f``"    0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}"``)` `except` `KsError as e:``print``(f``"[!] Error: {e}"``)` |
|-|-|

**运行结果：**

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_G7SJAJD4WZCM7QW.png)

---

## 六、总结

至此，我们已经学完了二进制分析与逆向工程的“三剑客”。

这三个框架各司其职，共同构成了一个完整的操控闭环：

- **Unicorn (Run)：** 模拟执行。
负责维护寄存器状态、内存数据，并真实地执行每一条指令。
- **Capstone (Read)：** 反汇编。
将 Unicorn 内存中的 `0101` 机器码翻译成我们可以理解的汇编语言。
- **Keystone (Write)：** 汇编。
将我们的逻辑（汇编代码）编译回机器码，并注入到 Unicorn 的内存中，实现对程序行为的干预。

**协作流程图：**

 ![图片描述](https://bbs.kanxue.com/upload/attach/202512/1036360_AK5D4TU8NW5GHQ2.webp)

---

‍

---

# 回复

## 回复 by wx_插曲 (#2)

*2025-12-26 10:21*

66

## 回复 by Imxz (#3)

*2025-12-26 10:26*

tql

## 回复 by KanXue_NG (#4)

*2025-12-26 10:26*

学习一下

## 回复 by mb_lizfxfno (#5)

*2025-12-26 10:27*

6

## 回复 by mb_asiwnxyv (#6)

*2025-12-26 11:10*

学习一下

## 回复 by MaYil (#7)

*2025-12-26 11:59*

感谢分享

## 回复 by mb_ldbucrik (#8)

*2025-12-26 14:39*

向大佬学习

## 回复 by iamshy (#9)

*2025-12-29 13:42*

学习一下

## 回复 by tjytjy (#10)

*2025-12-30 11:36*

学习一下

## 回复 by 神奇的人鱼 (#11)

*2025-12-30 14:00*

学习了

## 回复 by mb_uvyukvot (#12)

*2025-12-31 18:01*

666

## 回复 by mb_fwxjxcgi (#13)

*2026-1-1 03:40*

123

## 回复 by l1s00t (#14)

*2026-1-10 18:22*

学习！

## 回复 by x1aob1n (#15)

*2026-1-18 15:57*

学习

## 回复 by Snowman_Liam (#16)

*2026-1-21 06:16*

学习！

## 回复 by mb_qqihqaoo (#17)

*2026-1-22 13:20*

6666666666

## 回复 by uni7corn (#18)

*2026-1-26 18:07*

学习了，感谢分享

## 回复 by qig (#19)

*2026-2-17 14:49*

感谢分享

## 回复 by mb_ggnlrzcs (#20)

*2026-2-18 10:08*

学习一下

## 回复 by 饮岁 (#21)

*2026-2-24 09:44*

666

## 回复 by Mr.He (#22)

*2026-3-4 16:41*

66

## 回复 by mb_criqjxad (#23)

*2026-3-21 22:23*

666

## 回复 by iBa0 (#24)

*2026-4-13 09:32*

123

## 回复 by git_49999huanptd2011 (#25)

*2026-4-21 01:17*

666

## 回复 by maomaolk (#26)

*2026-5-18 16:58*

666

## 回复 by mb_lfqytcls (#27)

*2026-5-25 02:31*

1

## 回复 by 一只鸭子 (#28)

*2026-5-29 13:07*

6666

## 回复 by tianwenle (#29)

*2026-5-31 08:06*

好东西看看把

## 回复 by buluo533 (#30)

*2026-5-31 09:21*

学习一下

## 回复 by Tanuyoki0 (#31)

*2026-6-15 21:21*

学习一下
