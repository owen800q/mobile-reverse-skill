---
title: 某反作弊 VMP Native 层深度逆向：从 643KB 混淆 SO 到 RC4-like Mixer 的完整穿透路径
url: https://bbs.kanxue.com/thread-291336.htm
tid: 291336
author: qqqiu
date: '2026-05-24'
tags: [Android安全]
crawled_at: '2026-08-08T10:08:08+00:00'
replies: 110
---

## 零：

逆向只是我的一个乐趣而已，风控才有意思欧，ios流量太少了来安卓圈子玩玩，写的不好多担当打开一看 ![图片描述](https://bbs.kanxue.com/upload/tmp/1053738_8YFTVX5BG2KHCV4.webp) 插件好像秒不了，无语。

---

## 一、样本元信息与 30 秒段表判断法

### 1.1 样本概况

| 字段 | 值 |
|-|-|
| 文件名 | target.so |
| 架构 | ARMv7 32-bit (armeabi-v7a) |
| 文件大小 | 0x99544 (627,012 bytes) |
| 内存大小 | 0x9CD5C (642,396 bytes) |
| MD5 | [已脱敏] |
| SHA256 | [已脱敏] |

### 1.2 五层穿透策略

在逆向重度混淆样本时，不要一来f5。按"由表及里、由元信息到代码"的层级逐级穿透：

| 层级 | 工具 | 回答的问题 | 耗时 |
|-|-|-|-|
| 1. 元信息 | readelf / IDA meta | 架构、大小、哈希 | 10 秒 |
| 2. 段布局 | IDA segments | 是否有壳？.init_array？字符串加密？ | 30 秒 |
| 3. 入口符号 | imports / exports | 攻击面 + 依赖能力 | 1 分钟 |
| 4. 函数画像 | Functions window | 热点函数、大函数、异常函数 | 5 分钟 |
| 5. 目标 decompile | F5 | 只对层 1-4 锁定的目标做 | 按需 |

**这个顺序非常重要。** 30 秒的段表扫描能告诉你的信息量，远超在错误的函数上花 3 天做 F5。

### 1.3 段表告诉我们什么

用 `readelf -l` 看 PT_LOAD 段：

```bash
$ readelf -l target.so

Program Headers:
  Type           Offset   VirtAddr   PhysAddr   FileSiz  MemSiz   Flg Align
  LOAD           0x000000 0x00000000 0x00000000 0x96d79  0x96d79  R E 0x1000
  LOAD           0x097a40 0x00098a40 0x00098a40 0x014d0  0x042ac  RW  0x1000
  DYNAMIC        0x097a40 0x00098a40 0x00098a40 0x00100  0x00100  RW  0x4
\```

整理成表：

| 段 | vaddr | file offset | filesz | memsz | perm | 说明 |
|-|-|-|-|-|-|-|
| LOAD 0 | 0x00000000 | 0x000000 | 0x96D79 | 0x96D79 | r-x | 代码 + rodata，file-backed |
| LOAD 1 | 0x00098A40 | 0x097A40 | 0x014D0 | 0x042AC | rw- | .data + .bss |

几个立即能得出的结论：

1. **没有加壳。** 如果加壳，LOAD 0 的 filesz 会远小于 memsz（壳在运行时解压填充）。这里两者相等（都是 `0x96D79`），说明代码段是明文的。
2. **.bss 区域很大。** LOAD 1 的 memsz(`0x42AC`) - filesz(`0x14D0`) = `0x2DDC` (11740 bytes)。对应地址范围 `0x99F10..0x9CCEC`。这意味着有大量全局变量在运行时初始化。后面会发现 CRC32 的 256-entry runtime table `dword_9B1F8` 和 frame pivot 用到的 `0x9B547` 就在这里。
3. **只有一个可执行段。** 没有额外的 JNI bridge 段或 trampoline 段。所有代码都在 LOAD 0 里。

在 IDA 里看 `.init_array`：

```python
.init_array:00098D54  DCD sub_55C0+1    ; index 0, Thumb
.init_array:00098D58  DCD sub_7738+1    ; index 1, Thumb
\```

`.init_array[0] = 0x55C1` 基本只做 stack canary / 版本噪声检查；`.init_array[1] = 0x7739` 更有意思——它会做一批环境路径探测：

```python
stat64 /data/data/org.autojs.autojs
stat64 /data/data/yk.juejin
stat64 /data/data/com.cyjh.mobileanjian
stat64 /data/data/com.touchsprite.android
stat64 /dev/input/event0
\```

**这些是自动化测试工具（AutoJS、按键精灵、触动精灵）和 root 框架的特征目录。** `.init_array` 阶段就开始做环境检测，比 JNI_OnLoad 更早。

### 1.4 导入表：只有 24 个符号

这是本样本最有信息量的元信息之一。一个 643KB 的 SO 文件，导入表里只有 24 个符号。正常的 Android native 库（同等大小）通常有 100-300 个导入符号。

24 个符号意味着：**这个库极度自包含，几乎不依赖外部 libc 函数。** 它很可能在内部实现了自己的内存管理、字符串处理、甚至系统调用封装。事实上，后续分析确认了这一点——target.so 使用 `SVC #0` 直接系统调用，绕过 libc wrapper，让 `strace` 级别的 hook 失效。

更关键的是：**没有 `Java_*` 导出符号。** 这意味着 JNI native method 的注册不是通过标准的静态绑定（函数名匹配），而是通过 `JNI_OnLoad` 里的 `RegisterNatives` 动态注册。后续的 unidbg 实验证实了这一点。

---

## 二、VMP 解释器的发现与识别

### 2.1 从函数大小入手

在 IDA 的 Functions 窗口里按大小排序，`sub_275CC` 以 1404 条 ARM 指令（约 5.6KB）排在前列。对于一个混淆库来说，单个函数 1404 条指令不算离谱，但它有两个异常特征：

1. **5 个不同的 caller 调用它。** 其他大函数通常只有 1-2 个调用者。
2. **每个 caller 传入不同的 `.rodata` 区域指针作为第一参数。** 5 个 caller 分别传入 `dword_8EBE0`、`dword_8EC60`、`dword_8F360`、`dword_900E0`、`dword_8FFA0`。

这个模式非常像解释器——同一个执行引擎，不同的字节码程序。

### 2.2 关键判据：`ADD PC, LR, R1`

打开 `sub_275CC` 的反汇编，主循环的核心 dispatch 序列如下：

```asm
; === VM Fetch ===
0x27638  LDR     R5, [R0]        ; R0 = current VM PC, R5 = fetched bytecode word
0x2763C  ADD     R0, R0, #4      ; advance VM PC by 4

; === Opcode Extraction ===
0x27640  AND     R1, R5, #0x3F   ; R1 = primary opcode = word & 0x3F
0x27644  LDR     R1, [LR, R1, LSL#2]  ; R1 = dispatch_table[primary] (4-byte offset)

; === Computed Goto ===
0x276C4  ADD     PC, LR, R1      ; PC = table_base + offset → jump to handler

; === Dispatch Table starts here ===
0x276C8  DCD 0x100               ; opcode 0 → handler at 0x276C4 + 0x100 = 0x277C8 (GROUP_A_BRANCH)
0x276CC  DCD 0x1E44              ; opcode 1 → handler at 0x276C4 + 0x1E44 = 0x2950C (DEFAULT)
0x276D0  DCD 0x81C               ; opcode 2 → handler at 0x276C4 + 0x81C = 0x27EE4 (SLT_IMM_SIGNED)
0x276D4  DCD 0x1E44              ; opcode 3 → DEFAULT
...
0x277C4  DCD 0x5A4               ; opcode 63 → handler at 0x276C4 + 0x5A4 = 0x27C6C (GROUP_D_ALU_IMM)
\```

`0x27638` 的 `LDR R5, [R0]` 是 VM 的 **fetch 指令**——它从当前 VM PC（R0）处读取一个 32-bit bytecode word 到 R5。这个地址是后续所有动态 hook 的主锚点。

`0x276C4` 的 `ADD PC, LR, R1` 是 dispatch 的核心——它是一个 **computed goto**，直接跳转到 `dispatch_table[opcode]` 对应的 handler。这里 `LR` 不是返回地址，而是被预设为 dispatch 表基址附近的地址。

**注意一个容易犯的错误：** dispatch 表的起点是 `0x276C8`（`ADD PC` 的下一个 4 字节对齐地址），而不是 `0x276C4`。如果误把 `0x276C4` 当表起点，所有 handler 地址会整体偏 4 字节，后续还原全部会错。

每个 handler 执行完毕后，会跳回 `0x27638` 重新 fetch 下一条指令，形成经典的 fetch-decode-execute 循环。

### 2.3 dispatch 表提取

`ADD PC, LR, R1` 的下一条指令地址是 `0x276C8`，这就是 dispatch 表的起点。表中每个条目是一个 4 字节的偏移量，加上 `0x276C4`（`ADD PC` 指令的地址）就得到对应 handler 的入口地址。

**注意一个容易犯的错误：** dispatch 表的起点是 `0x276C8` 而不是 `0x276C4`。如果误把 `0x276C4` 当表起点，所有 handler 地址会整体偏 4 字节，后续还原全部会错。

提取出的 64 条 dispatch 表：

| primary opcode | handler 类型 | handler 地址 | 说明 |
|-|-|-|-|
| 0, 10, 19, 24, 29, 57, 59, 61 | GROUP_A_BRANCH | 0x277C8 | 条件分支 |
| 26, 30, 32, 33, 38, 43, 46, 53 | GROUP_B_LOAD | 0x27A5C | LOAD 族 |
| 20, 27, 35, 48, 54 | GROUP_C_STORE | 0x27B58 | STORE 族 |
| 7, 51, 52, 63 | GROUP_D_ALU_IMM | 0x27C6C | 立即数 ALU |
| 12, 55 | GROUP_E_UNKNOWN | 0x27CC8 | 待细化 |
| 17, 50 | GROUP_F_ALU_IMM | 0x27E70 | 立即数加法 |
| 11 | OP11_ALU_REG | 0x27F30 | 寄存器 ALU 主战场 |
| 14 | OP14_ALU_MUL_ACC | 0x2807C | 乘法累加 |
| 25 | OP25_BIT_ROUTER | 0x280D4 | 位操作路由 |
| 41 | OP41_BIT_MUL_ROUTER | 0x28268 | 位/乘法路由 |
| 2 | SLT_IMM_SIGNED | 0x27EE4 | 有符号比较 |
| 56 | SLT_IMM_UNSIGNED | 0x282CC | 无符号比较 |
| 其余 29 个 | DEFAULT | 0x2950C | 默认处理 |

64 个 opcode 中有 29 个指向同一个 DEFAULT handler，这意味着**实际有效的指令类型只有 13 种**。29 个 DEFAULT opcode 的存在不是浪费——它们是 **opcode 空间膨胀**的结果，让逆向者无法简单地通过 opcode 出现频率来推断指令语义。

### 2.4 三份克隆与反分析诱饵

target.so 里有三份几乎完全相同的解释器实现：

| 克隆 | 地址范围 | 大小 | xref 数 |
|-|-|-|-|
| 克隆 1 (sub_275CC) | 0x275CC..0x295B0 | ~8KB | 5 个 wrapper 调用 |
| 克隆 2 (sub_29CC8) | 0x29CC8..0x2BCAC | ~8KB | 1 个 inline thumb caller |
| 克隆 3 | 0x49560..0x4B544 | ~8KB | **0 个 xref** |

用脚本做 byte-level 对比：

```python
# 三克隆 byte diff
clone1 = read_bytes(0x275CC, 8164)  # sub_275CC
clone2 = read_bytes(0x29CC8, 8164)  # sub_29CC8
clone3 = read_bytes(0x49560, 8164)  # IDA 未识别的死代码块

diffs_1v2 = [(i, clone1[i], clone2[i]) for i in range(8164) if clone1[i] != clone2[i]]
# 结果: 仅 4 个字节不同, 全部在 BL 指令的 PC-relative 偏移字段
# offset  clone1  clone2
# 0x07A4  0xFE    0x6C    ← BL target 的高 8 位
# 0x07A5  0x61    0x64    ← BL target 的低 8 位
# 0x0B9C  0x43    0xB1    ← 另一个 BL
# 0x0B9D  0x59    0x5C
\```

差异全部集中在 `BL`（Branch with Link）指令的立即数偏移字段——因为 `BL` 使用 PC-relative 寻址，三份克隆在不同的 .text 地址上，所以同一个目标函数的偏移量自然不同。反汇编后，三份 `BL` 的目标地址完全相同。

**克隆 3 有 0 个交叉引用——它是死代码。** 没有任何函数调用它、没有任何指针引用它。它存在的唯一目的是：**让逆向者在找到它之后多花一周时间分析，最后发现它根本不被执行。** 8KB × 2 份无用克隆 = 16KB 的 .text 空间，换来的是逆向者的时间成本。

这也从侧面证实了"通用 IR 解释器"假说——只有解释器才值得被克隆 3 份。如果是普通的算法函数，克隆它没有意义。

---

## 三、VM 指令集架构（ISA）逆向

### 3.1 指令字段编码

每条 VM 指令是一个 32-bit word。通过分析 `sub_275CC` 中各 handler 对指令 word 的位提取操作，还原出以下字段布局：

```python
31 30 29 28 27 26 25 24 23 22 21 20 19 18 17 16 15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
 d  ─  ─  ─  ─  ─  rB─ ─  ─  ─  ─  rA─ ─  ─  ─  ─  ──────────── imm16 ────────────────────────
 │                                                        dd dd     ──── ext ────  ── primary ──
 └─────────────────────────────────────────────────────────┘└─┘
                                                            dst (5-bit, 非连续)
\```

| 字段 | 位域 | 提取公式 | 含义 |
|-|-|-|-|
| primary | [5:0] | `word & 0x3F` | 一级 opcode，索引 dispatch 表 |
| ext | [11:0] | `word & 0xFFF` | OP11/OP14/OP41 的二级语义选择 |
| rA | [20:16] | `(word >> 16) & 0x1F` | 源寄存器 A |
| rB | [25:21] | `(word >> 21) & 0x1F` | 源寄存器 B |
| dst | [12:11]+[31] | `((word >> 11) & 0x1E) \| (word >> 31)` | 目的寄存器 |
| imm16 | [15:0] | sign-extended | 立即数（分支/加载/存储） |

对应的 native 汇编（在 OP11 handler `0x27F30` 附近）：

```asm
; 提取 rA
0x27F3C  UBFX    R2, R5, #16, #5   ; R2 = (R5 >> 16) & 0x1F = rA

; 提取 rB
0x27F40  UBFX    R3, R5, #21, #5   ; R3 = (R5 >> 21) & 0x1F = rB

; 提取 dst (非连续!)
0x27F48  UBFX    R4, R5, #11, #4   ; R4 = (R5 >> 11) & 0xF → 取 bit[14:11]
0x27F4C  BFI     R4, R5, #0, #1    ; R4[0] = R5[31] → 把最高位插入最低位
                                    ; 最终 dst = ((R5 >> 11) & 0x1E) | (R5 >> 31)
\```

Python 版的解码器：

```python
def decode_vm_word(word):
    primary = word & 0x3F
    ext     = word & 0xFFF
    rA      = (word >> 16) & 0x1F
    rB      = (word >> 21) & 0x1F
    dst     = ((word >> 11) & 0x1E) | ((word >> 31) & 1)
    imm16   = word & 0xFFFF
    if imm16 & 0x8000:
        imm16 -= 0x10000  # sign extend
    return {
        'primary': primary, 'ext': ext,
        'rA': rA, 'rB': rB, 'dst': dst, 'imm16': imm16
    }

# 示例：mixer 入口的 UDIVMOD 指令
>>> decode_vm_word(0x0072054B)
{'primary': 11, 'ext': 0x54B, 'rA': 18, 'rB': 3, 'dst': 0, 'imm16': 1355}
# primary=11 → OP11_ALU_REG handler
# ext=0x54B → UDIVMOD (unsigned div/mod)
# rA=18 → 除数 = reg18
# rB=3  → 被除数 = reg3
\```

`dst` 字段的编码方式值得注意——它不是连续的 5 位，而是 bit[12:11] 拼上 bit[31]。这种非标准的字段拆分是 VMP 设计者有意为之，让自动化反汇编工具难以正确提取寄存器号。

### 3.2 VM 寄存器文件与 Frame 布局

VM 有 32 个通用寄存器（R0-R31）和一个 64-bit 累加器（acc_lo + acc_hi），累加器主要用于 div/mod 运算的商和余数。

frame 布局从 `sub_275CC` 的入口参数推导：

```python
frameTop  = a4[1]           // 第 5 个参数的第二个 dword
frameBase = frameTop - 0x9C
regsBase  = frameBase + 4

reg[i]    = *(regsBase + i * 4)
acc_lo    = *(frameTop - 0x18)
acc_hi    = *(frameTop - 0x14)
cur_vm_pc = *(frameTop - 0x9C)
\```

这个公式是后续所有动态观测的基础。**算错 frame 布局，所有寄存器值都会变成假数据。**

### 3.3 OP11 的二级路由机制

在 13 种 handler 中，OP11（primary = 11）是最复杂的一个。它不是一个单一操作，而是一个**二级路由器**——通过 `ext` 字段（word 的低 12 位）选择具体的 ALU 操作。

OP11 handler 的入口 native 汇编（`0x27F30`）：

```asm
; === OP11 handler entry @ 0x27F30 ===
0x27F30  AND     R1, R5, #0xFFF      ; R1 = ext = word & 0xFFF
0x27F34  CMP     R1, #0x40B          ;
0x27F38  BEQ     handler_0x40B       ; ext == 0x40B → ADD
0x27F3C  CMP     R1, #0x4B           ;
0x27F40  BEQ     handler_0x4B        ; ext == 0x4B → SUB

; --- 字段提取 ---
0x27F48  UBFX    R2, R5, #16, #5     ; rA = (word >> 16) & 0x1F
0x27F4C  UBFX    R3, R5, #21, #5     ; rB = (word >> 21) & 0x1F

; --- 读 VM 寄存器值 ---
0x27F54  LDR     R2, [R7, R2, LSL#2] ; R2 = vm_regs[rA]
0x27F58  LDR     R3, [R7, R3, LSL#2] ; R3 = vm_regs[rB]

; --- ext 路由 ---
0x27F60  AND     R1, R5, #0xFFF      ; 再取 ext
0x27F64  CMP     R1, #0x54B          ;
0x27F68  BEQ     handler_udivmod     ; ext == 0x54B → UDIVMOD
0x27F6C  CMP     R1, #0x10B          ;
0x27F70  BEQ     handler_idivmod     ; ext == 0x10B → IDIVMOD
0x27F74  CMP     R1, #0x5CB          ;
0x27F78  BEQ     handler_acc_hi      ; ext == 0x5CB → reg[dst] = acc_hi
0x27F7C  CMP     R1, #0x2CB          ;
0x27F80  BEQ     handler_acc_lo      ; ext == 0x2CB → reg[dst] = acc_lo
0x27F84  CMP     R1, #0xB8B          ;
0x27F88  BEQ     handler_eor         ; ext == 0xB8B → EOR
; ... 更多 ext 分支 ...
\```

UDIVMOD handler 的关键实现（`0x293E0` 附近）：

```asm
; === UDIVMOD: acc = (rB /u rA, rB %u rA) ===
; 输入: R2 = vm_regs[rA], R3 = vm_regs[rB]
0x293D0  MOV     R0, R3              ; R0 = dividend = rB
0x293D4  MOV     R1, R2              ; R1 = divisor = rA
0x293D8  BL      sub_89AB0           ; R0 = R0 / R1 (unsigned div helper)
0x293DC  MLS     R1, R0, R2, R3      ; R1 = R3 - R0 * R2 = remainder
0x293E0  STR     R0, [R7, #-0x18]    ; acc_lo = quotient
0x293E4  STR     R1, [R7, #-0x14]    ; acc_hi = remainder
\```

这里 `[R7, #-0x18]` 和 `[R7, #-0x14]` 就是 acc_lo 和 acc_hi 在 frame 中的位置。`sub_89AB0` 是 compiler runtime 的 `__aeabi_uidiv`（unsigned integer division）。`MLS` 是 "Multiply and Subtract"：`R1 = R3 - R0 * R2`，即余数。

关键的 ext 值及其语义：

| ext | 语义 | native 实现 | 在算法中的角色 |
|-|-|-|-|
| 0x54B | UDIVMOD（无符号除法/取模） | bl sub_89AB0 + MLS | **硬锚点**：mixer 的核心取模操作 |
| 0x10B | IDIVMOD（有符号除法/取模） | bl sub_89B78 + MLS | 硬锚点 |
| 0x5CB | reg[dst] = acc_hi | 直接赋值 | 取模结果物化到寄存器 |
| 0x2CB | reg[dst] = acc_lo | 直接赋值 | 商结果物化到寄存器 |
| 0xB8B | EOR（异或） | reg[dst] = rA ^ rB | mixer 的 XOR 输出 |
| 0x4B | SUB（减法） | reg[dst] = rB - rA | 普通 ALU |
| 0x64B | MOV / 状态传递 | reg[dst] = f(R0) | frame continuation |
| 0xF8B | Frame Transition | route by R31 + side effects | **极其特殊** |
| 0xACB | 某种 ALU | 待细化 | 业务 wrapper 高频使用 |

**反直觉点：** 标准的 MAC/Hash 主循环通常不需要除法操作。`0x54B` UDIVMOD 的存在说明这不是传统的密码学算法——它更像是一个自定义的 byte-index mixing 方案，用除法余数作为表索引。

### 3.4 F8B：不是跳转的"跳转"

在分析过程中发现了一条极其特殊的指令——ext = 0xF8B。它的表面行为像是一个间接跳转（`PC = R31` 指向的地址），但实际上它做了三件事：

1. 用 R31 的值决定下一个代码块的入口
2. 推进 R29（观察到 +0x300 的增量），即移动 frame 指针
3. 触发 saved register restore 的副作用

这不是普通的 branch 或 call，而是一个 **协程式的 continuation passing** 指令。每次 F8B 相当于一个 `longjmp` 到一个新的执行帧。

动态验证确认了这一点：patch R31 为不同的地址，F8B 确实会跳到对应位置，同时 R29 发生非零偏移——而普通的 branch 不会改变 frame 指针。

---

## 四、从 5 个 Wrapper 中锁定算法入口

### 4.1 Wrapper 概览与 IDA 反编译

5 个函数调用 `sub_275CC`，每个传入不同的 bytecode program 指针：

| Wrapper | Bytecode Base | 大小 | 角色 |
|-|-|-|-|
| sub_22BB4 | 0x8EBE0 | 4096 bytes | 业务程序 |
| sub_22C10 | 0x8EC60 | 4096 bytes | 业务程序 |
| sub_24C4C | 0x8F360 | 4096 bytes | 业务程序 |
| **sub_24CBC** | **0x900E0** | **4096 bytes** | **算法候选** |
| **sub_270E8** | **0x8FFA0** | **4096 bytes** | **算法候选** |

两个算法 wrapper 的 IDA 反编译对比：

```c
// sub_24CBC 反编译（简化）
int sub_24CBC(int a1, int a2, int a3, int a4) {
    int v6[8];
    v6[0] = a1;     // 输入参数打包到局部数组
    v6[1] = a2;
    v6[2] = a3;
    v6[3] = a4;
    sub_275CC(dword_900E0, v6);   // 调解释器，bytecode = 0x900E0
    return v6[4];                  // 返回第 5 个元素 = 签名结果
}

// sub_270E8 反编译（简化）
int sub_270E8(int *a1) {
    int v3[8];
    v3[0] = a1[0];  // 从结构体取前三个字段
    v3[1] = a1[1];
    v3[2] = a1[2];
    int old = dword_9AD78;
    sub_275CC(dword_8FFA0, v3);   // 调解释器，bytecode = 0x8FFA0
    return dword_9AD78 - old;     // 返回全局计数器的增量
}
\```

核心区别：24CBC 返回 `v6[4]`（计算出的签名值），270E8 返回全局变量 `dword_9AD78` 的增量（可能是 nonce 或 sequence 推进）。但两者传入 `sub_275CC` 的 bytecode 在所有 1024 个 dword 上是 **逐位一致的**。

### 4.2 不能用的指纹：0xCB 密度

在早期分析中，我曾经试图用 `0xCB` 字节出现的频率来区分算法 wrapper 和业务 wrapper。这是一个**误判**。

`0xCB` 实际上只是 `primary_opcode = 11`（OP11）的编码副产物——因为 `11` 的十六进制是 `0x0B`，而 VM 指令的低 12 位（ext 字段）经常以 `xCB` 的形式出现。业务 wrapper 里的 OP11 数量（291-327 条）反而远高于算法 wrapper（180-204 条），所以 `0xCB` 密度不仅不能区分算法，反而会指向错误的方向。

### 4.3 真正有区分力的指标：程序化差分

为了避免主观判断，我写了一套自动化脚本对 5 个 wrapper 做全面差分。结果极其清晰：

| 指标 | 业务 (22BB4/22C10/24C4C) | 算法 (24CBC/270E8) | 差异 |
|-|-|-|-|
| hard anchor (0x10B/0x54B) | **0** | **2** | 算法独有 |
| 数据岛数量 | 0 | 3 | 算法独有 |
| 数据岛总 word 数 | 0 | 134 | 算法独有 |
| OP11 ext 0x54B (UDIVMOD) | 0 | 1 | 算法独有 |
| OP11 ext 0x10B (IDIVMOD) | 0 | 1 | 算法独有 |
| OP11 总数 | 291-327 | 180-204 | 业务更多 |
| Branch density | 0.057-0.064 | 0.065-0.075 | 略有差异 |

更细致地看 OP11 ext 频率分布，差异更加明显。以下是各 wrapper 的 OP11 ext 出现次数：

```python
22BB4:  0x68B:96  0x1CB:66  0x64B:59  0xACB:39  ...  0x54B:0  0x10B:0
22C10:  0x68B:96  0x1CB:69  0x64B:59  0xACB:41  ...  0x54B:0  0x10B:0
24C4C:  0x68B:102 0x1CB:72  0x64B:70  0xACB:43  ...  0x54B:0  0x10B:0
24CBC:  0x68B:58  0x1CB:44  0x64B:13  0xACB:24  ...  0x54B:1  0x10B:1
270E8:  0x68B:62  0x1CB:53  0x64B:18  0xACB:27  ...  0x54B:1  0x10B:1
\```

**算法 wrapper 独有的 ext 集合**（业务 wrapper 中出现次数 = 0）：

```python
algorithm-only OP11 ext = {0x10B, 0x4B, 0x54B, 0x8CB, 0xECB, 0xF4B}
business-only  OP11 ext = {0x78B, 0x80B, 0xBCB}
\```

`0x10B`（IDIVMOD）和 `0x54B`（UDIVMOD）只出现在算法 wrapper 中——这不是密度差异，是**有/无的二元差异**，是最硬的判据。

**区分算法 wrapper 的判据不是单一指标，而是三件套同时成立：**

1. 存在 `0x10B / 0x54B` hard anchor（div/mod 操作）
2. 存在数据岛（内嵌常量表）
3. 共享 `0x90AC4..0x90BC8` 的 mixer 核心窗口

前三个业务 wrapper 没有任何一项满足。

OP11 ext 的完整分布更加直观地展示了差异：

```python
业务 wrapper 独有的 ext:
  0x78B  (1次, 22BB4/22C10)     — 某种 ALU, 算法里不用
  0x80B  (1次)                  — 同上
  0xBCB  (1次)                  — 同上

算法 wrapper 独有的 ext:
  0x10B  (1次) = IDIVMOD        — 有符号除法/取模 ★
  0x54B  (1次) = UDIVMOD        — 无符号除法/取模 ★
  0x4B   (1次) = SUB            — 减法
  0x8CB  (2次) = EXEC_REJECTED  — 被 handler 拒绝
  0xECB  (1次)                  — 待细化
  0xF4B  (1次)                  — 待细化

两者共享的高频 ext:
  0x68B  业务=96-102次, 算法=58-62次   — 某种状态传递/MOV
  0x1CB  业务=66-72次, 算法=44-53次   — 某种 ALU
  0x64B  业务=59-70次, 算法=13-18次   — 某种 accumulate
  0xACB  业务=39-43次, 算法=24-27次   — 某种 ALU
\```

**反直觉点：** 业务 wrapper 的 OP11 密度（30%）远高于算法 wrapper（23%）。算法的"特殊"不在于计算量大，而在于它用了业务不用的操作类型——特别是 div/mod。

### 4.4 业务 Wrapper 的共享模板

对比三个业务 wrapper 的 bytecode，在绝对 VA 地址 `0x8F470..0x8FB8C` 区间内发现了 **476 个 dword 完全一致**。这说明 VMP 工具链在生成 bytecode 时会把一段通用的"运行时支撑代码"（类似 prologue/epilogue/状态管理模板）内联到每个 program 中。

### 4.5 24CBC 和 270E8 的 Bytecode 是 Bit-Identical 的

最强的证据：24CBC 和 270E8 的 1024 个 dword 在所有位置上逐位一致。两者的区别只在 wrapper 层——24CBC 返回 `v6[4]`（局部数组的第 5 个元素），270E8 返回 `dword_9AD78` 的增量。

**它们不是两套不同的算法，而是同一套算法的两个入口视图。**

---

## 五、RC4-like Byte Mixer 的静态闭合

### 5.1 定位 Mixer 窗口

在确认 24CBC/270E8 是算法 wrapper 之后，下一步是在 4096 字节的 bytecode 中找到算法核心。

线索是 **hard anchor**：`0x54B`（UDIVMOD）在 bytecode VA `0x90AC4` 处只出现一次。

**核心窗口 raw hex dump** (`0x90AC4..0x90BC8`，66 条 VM word)：

```python
90AC4: 0072054B 1E4008CB 800005CB ...
90B24: 00280021 00E80023 00290023 ...
90B34: FC20F8F9 ...
90B94: 012A0021 002A0023 01280023 ...
90BA8: 0C210FFF ...
90BB8: 81010B8B 00C10023 ...
90BC4: 80D009CB FC20F879
\```

IDA 内 handler recovery trace 确认的完整事件表：

| VM PC | raw | handler | kind | rA | rB | dst | 语义 |
|-|-|-|-|-|-|-|-|
| `0x90AC4` | `0x0072054B` | OP11_ALU_REG | ACCEPTED | 18 | 3 | 0 | `UDIVMOD acc=(R3 /u R18, R3 %u R18)` |
| `0x90AC8` | `0x1E4008CB` | OP11_ALU_REG | **REJECTED** | 0 | 18 | 0 | ext=0x8CB 被路由器拒绝 |
| `0x90ACC` | `0x800005CB` | OP11_ALU_REG | ACCEPTED | 0 | 0 | 1 | `R1 = acc_hi` (取模结果) |
| ... |  |  |  |  |  |  | (中间约 20 条 ALU/LOAD 准备地址) |
| `0x90B24` | `0x00280021` | GROUP_B_LOAD | ACCEPTED | 8 | 1 | 0 | `LDRB R8, [R1 + imm]` |
| `0x90B28` | `0x00E80023` | GROUP_C_STORE | ACCEPTED | 8 | 7 | 0 | `STRB R8, [R7 + imm]` (swap pt1) |
| `0x90B2C` | `0x00290023` | GROUP_C_STORE | ACCEPTED | 9 | 1 | 0 | `STRB R9, [R1 + imm]` (swap pt2) |
| `0x90B34` | `0xFC20F8F9` | GROUP_A_BRANCH | BRANCH | 0 | 1 | 31 | `BEQ.var R1,R0` (imm=-29) |
| `0x90B44` | `0x80D009CB` | OP11_ALU_REG | **REJECTED** | 16 | 6 | 1 | ext=0x9CB 被路由器拒绝 |
| `0x90B48` | `0x00200858` | GROUP_A_BRANCH | BRANCH | 0 | 1 | 0 | `BEQ.loop R1,R0` (imm=+33) |
| ... |  |  |  |  |  |  | (中间约 15 条第二段准备) |
| `0x90B94` | `0x012A0021` | GROUP_B_LOAD | ACCEPTED | 10 | 9 | 0 | `LDRB R10, [R9 + imm]` |
| `0x90B98` | `0x002A0023` | GROUP_C_STORE | ACCEPTED | 10 | 1 | 0 | `STRB R10, [R1 + imm]` (swap2 pt1) |
| `0x90B9C` | `0x01280023` | GROUP_C_STORE | ACCEPTED | 8 | 9 | 0 | `STRB R8, [R9 + imm]` (swap2 pt2) |
| ... |  |  |  |  |  |  |  |
| `0x90BA8` | `0x0C210FFF` | GROUP_D_ALU_IMM | ACCEPTED | 1 | 1 | 0 | `R1 = low16(R1) & 0xFF` (byte clamp) |
| `0x90BB8` | `0x81010B8B` | OP11_ALU_REG | ACCEPTED | 1 | 8 | 1 | `R1 = R1 ^ R8` (XOR output) |
| `0x90BBC` | `0x00C10023` | GROUP_C_STORE | ACCEPTED | 1 | 6 | 0 | `STRB R1, [R6 + imm]` (write output byte) |
| `0x90BC4` | `0x80D009CB` | OP11_ALU_REG | **REJECTED** | 16 | 6 | 1 | ext=0x9CB 被路由器拒绝 |
| `0x90BC8` | `0xFC20F879` | GROUP_A_BRANCH | BRANCH | 0 | 1 | 31 | `BEQ.var R1,R0` (imm=-31, **loop back**) |

注意 3 个 **EXEC_REJECTED** 点（`0x90AC8`、`0x90B44`、`0x90BC4`）：它们的 ext 值（`0x8CB`、`0x9CB`）不被 OP11 handler 的 ext-router 接受。这不是"mixer 窗口错了"——它们说明需要 branch-aware / path-sensitive trace，不能把窗口内所有 word 都当顺序执行。这些 rejected word 更可能是 **branch delay guard**：在语义断点之后放一条保证被拒绝的指令，防止线性 fetch 意外执行。

从这个表追踪数据流：

```python
0x90AC4  UDIVMOD  acc = (reg3 /u reg18, reg3 %u reg18)
0x90ACC  MOV      reg1 = acc_hi    // reg1 = reg3 % reg18
          ↓
0x90B24  LDRB     reg8 = M8[reg2 + derived_addr]
0x90B28  STRB     M8[reg7_addr] = reg8     // swap part 1
0x90B2C  STRB     M8[reg1_addr] = reg9     // swap part 2
          ↓
0x90B94  LDRB     reg10 = M8[reg9_addr]
0x90B98  STRB     M8[reg1_addr] = reg10    // swap part 1
0x90B9C  STRB     M8[reg9_addr] = reg8     // swap part 2
          ↓
0x90BA8  AND      reg1 = reg1 & 0xFF       // byte clamp
0x90BB8  EOR      reg1 = reg1 ^ reg8       // XOR output
0x90BBC  STRB     M8[output_addr] = reg1   // write output byte
          ↓
0x90BC8  BRANCH   loop back
\```

### 5.2 保守伪代码

```c
// 第一段：swap-like byte permutation
idx = reg3 % reg18;             // 0x90AC4 UDIVMOD
left  = S[base + reg3];         // 0x90B24 LDRB
right = S[base + idx];
S[base + idx]  = left;          // 0x90B28 STRB
S[base + reg3] = right;         // 0x90B2C STRB

// 第二段：第二组 swap + XOR output
t1 = S[base + derived_i'];      // 0x90B94 LDRB
S[base + derived_j'] = t1;      // 0x90B98 STRB
S[base + derived_i'] = t2;      // 0x90B9C STRB

// 第三段：clamp + XOR + output
v = reg1 & 0xFF;                // 0x90BA8 AND
out = v ^ reg8;                 // 0x90BB8 EOR
M8[output + reg6] = out;        // 0x90BBC STRB

// 回边
if (cond) goto loop_head;       // 0x90BC8 BRANCH
\```

这个结构和 RC4 的 PRGA 非常相似：`i/j` 通过取模生成 → 查 S-box → swap → 用 swap 后的值索引 S-box 生成 keystream byte → XOR 输出。

但我**不把它命名为标准 RC4**，因为还缺几个关键证据：

1. `reg18`（除数/S-table 大小）的 concrete 值未知。标准 RC4 用 `& 0xFF`（因为 N=256），这里用的是 UDIVMOD 取模，暗示 `reg18` 可能不是 256。
2. `j` 的更新公式未完全确认。标准 RC4 是 `j = (j + S[i] + key[i % keylen]) % 256`，这里的更新链条还没有动态验证。
3. S-table 的初始状态未知。标准 RC4 初始化为 identity permutation `S[i] = i`，这里可能有不同的初始化方式。

因此，最保守的命名是 **RC4-like byte permutation / XOR mixer**。

### 5.3 窗口边界

```python
core mixer     : 0x90AC4..0x90BC8  (66 条 VM word)
loop A         : 0x90AC4..0x90B34
loop B         : 0x90B50..0x90BC8
boundary       : 0x90BFC / 0x90C08
data corridor  : 0x90C00..0x90E50  (不是代码)
\```

---

## 六、数据岛识别与密码学常量硬匹配

### 6.1 什么是数据岛

VMP bytecode 中不是所有 dword 都是指令。有些区域是**内嵌的常量数据**（lookup table、密码学常量、配置参数），被 LOAD 指令通过地址偏移引用。我把这些区域叫做"数据岛"。

数据岛的识别方法是：在线性 sweep 时，如果一段连续的 dword 的 primary opcode 几乎全部落在 DEFAULT handler 上（概率约 45%），而且这段区域被某个远跳转（branch target 大于 data island end）跳过，那它大概率是数据岛。

24CBC/270E8 共有 4 段数据岛，134 个 dword。业务 wrapper 有 0 段。

### 6.2 Blowfish π 常量命中

对 `0x90944..0x909FC` 这段数据岛做已知密码学常量匹配，结果非常明确。

**Blowfish P-array 连续命中（10 个 dword）：**

```python
VA         Value       标准 P-array   Index
0x90980    0x452821E6  P[8]           ✓ 精确匹配
0x90984    0x38D01377  P[9]           ✓ 精确匹配
0x90988    0xBE5466CF  P[10]          ✓ 精确匹配
0x9098C    0x34E90C6C  P[11]          ✓ 精确匹配
0x90990    0xC0AC29B7  P[12]          ✓ 精确匹配
0x90994    0xC97C50DD  P[13]          ✓ 精确匹配
0x90998    0x3F84D5B5  P[14]          ✓ 精确匹配
0x9099C    0xB5470917  P[15]          ✓ 精确匹配
0x909A0    0x9216D5D9  P[16]          ✓ 精确匹配
0x909A4    0x8979FB1B  P[17]          ✓ 精确匹配
\```

**Blowfish S-box[0] 前缀连续命中（22 个 dword）：**

```python
VA         Value       标准 S-box[0]  Index
0x909A8    0xD1310BA6  S[0][0]        ✓
0x909AC    0x98DFB5AC  S[0][1]        ✓
0x909B0    0x2FFD72DB  S[0][2]        ✓
0x909B4    0xD01ADFB7  S[0][3]        ✓
0x909B8    0xB8E1AFED  S[0][4]        ✓
0x909BC    0x6A267E96  S[0][5]        ✓
0x909C0    0xBA7C9045  S[0][6]        ✓
0x909C4    0xF12C7F99  S[0][7]        ✓
0x909C8    0x24A19947  S[0][8]        ✓
0x909CC    0xB3916CF7  S[0][9]        ✓
0x909D0    0x0801F2E2  S[0][10]       ✓
0x909D4    0x858EFC16  S[0][11]       ✓
0x909D8    0x636920D8  S[0][12]       ✓
0x909DC    0x71574E69  S[0][13]       ✓
0x909E0    0xA458FEA3  S[0][14]       ✓
0x909E4    0xF4933D7E  S[0][15]       ✓
0x909E8    0x0D95748F  S[0][16]       ✓
0x909EC    0x728EB658  S[0][17]       ✓
0x909F0    0x718BCD58  S[0][18]       ✓
0x909F4    0x82154AEE  S[0][19]       ✓
0x909F8    0x7B54A41D  S[0][20]       ✓
0x909FC    0xC25A59B5  S[0][21]       ✓
\```

**总计 32 个连续 dword 精确命中标准密码学常量。** 这些值全部是 π（圆周率）的十六进制分段——Blowfish 算法使用它们作为 "nothing-up-my-sleeve" 初始化常量，意思是"常量来源于数学常数，没有后门"。

同时，脚本还对所有数据岛做了 16-byte 块的 Shannon 熵分析：

```python
段 0x90880..0x90940: 每个 16-byte 块熵 = 4.0（最大值），无低熵块 → 高熵常量
段 0x90944..0x909FC: 每个 16-byte 块熵 = 3.58-4.0 → 密码学常量（符合预期）
段 0x90D70..0x90E44: 熵 3.75-4.0，1 个低熵块 → 结构化数据
段 0x90E90..0x90F10: 熵 3.88-4.0，1 个低熵块 → 结构化数据
\```

只有 `0x90944..0x909FC` 能被已知密码学常量库硬匹配。其他三段更像结构化数据、指针或混淆缓冲区。

### 6.3 但不是标准 Blowfish

尽管命中了 Blowfish 常量，但这段数据岛不是从 P-array[0] 开始的。标准 Blowfish P-array 起始值是 `0x243F6A88 / 0x85A308D3 / 0x13198A2E`，而 `0x90944..0x9097C` 的前 15 个 dword 不匹配任何已知 Blowfish 常量。

我做了一个验证：把前 8 个不匹配的 dword 分别 XOR 标准 P[0..7]，看结果是否有 key 模式。**结论是没有——XOR 结果无规律、非 ASCII、无周期性。** 所以这不是 "P[0..7] 被 key schedule 覆写"的情况。

更准确的说法是：**该样本的开发者借用了 π 常量作为初始化种子，但算法不是标准 Blowfish。** 这些常量可能用在 key derivation 或 whitening 阶段，而不是作为 Blowfish 的 P-array 直接使用。

### 6.4 数据走廊的 XOR 字符串反证

`0x90C00..0x90E50` 曾经在线性 sweep 中被"解码"出一些看起来像 OP11 指令的 word。但 IDA xref 分析揭示了真相——这段区域实际上是 XOR 编码的 ELF/JNI 辅助字符串。

以 `0x90CD8` 为例，线性解码会得到：

```python
0x90CD8: raw = 0xE712C04B
primary = 0x4B & 0x3F = 11 → OP11_ALU_REG handler
ext     = 0x04B → SUB (减法)
rA      = 18, rB = 0, dst = 24
→ 看起来像: R24 = R0 - R18
\```

一个"完美"的 OP11 SUB 指令。但 IDA xref 揭示 `sub_33134` 会用逐字节 XOR 解密 `0x90CD5..0x90CD8`：

```python
# sub_33134 的解密逻辑（IDA 反编译还原）
key = [0xF9, 0x9F, 0x07, 0x4B]  # 从上下文中推导

raw_bytes = [0xD1, 0xB6, 0x5D, 0x4B]  # 0x90CD5..0x90CD8

for i in range(4):
    print(chr(raw_bytes[i] ^ key[i]), end='')

# 输出:
# D1 ^ F9 = 0x28 = '('
# B6 ^ 9F = 0x29 = ')'
# 5D ^ 07 = 0x5A = 'Z'
# 4B ^ 4B = 0x00 = '\0'
# → "()Z\0" = JNI 方法签名片段！
\```

`0x90CD8` 不是 VM 的 `SUB` 指令——它是 JNI 签名 `()Z`（返回 boolean 的无参方法）的 NUL 终止字节！

同样的方法还原了其他字符串：

| 地址范围 | 引用函数 | 解密结果 | 含义 |
|-|-|-|-|
| `0x90C2B..0x90C31` | sub_2FAC4 | `<self>` | ELF 自身基址查找 |
| `0x90C32..0x90C36` | sub_2FC3C | `\x7FELF` | ELF magic 验证 |
| `0x90C37..0x90C3E` | sub_2FD7C | `/linker` | linker 映射检查 |
| `0x90C53..0x90C5A` | sub_30E6C | `.rodata` | 节区定位 |
| `0x90C5B..0x90C62` | sub_30B44 | `.dynsym` | 符号表解析 |
| `0x90C63..0x90C6A` | sub_30B44 | `.dynstr` | 字符串表解析 |
| `0x90C6B..0x90C72` | sub_30B44 | `.symtab` | 符号表解析 |
| `0x90C73..0x90C7A` | sub_30B44 | `.strtab` | 字符串表解析 |
| `0x90CD5..0x90CD8` | sub_33134 | `()Z\0` | JNI 方法签名 |

这些函数的命名（`find_self_elf_base`、`validate_elf_header`、`check_linker_mapping`、`find_rodata_section`）也印证了它们的用途：**target.so 的反篡改/自检子系统在运行时解析自身的 ELF 结构。**

**核心教训：**

```python
native handler accepts ext ≠ 该地址一定是 VM code
\```

只要高熵数据的 4 字节碰巧满足 OP11 的形态，线性解码就会产生"漂亮但错误"的算法指令。**在 VMP 分析中，任何线性 sweep 的结果都必须经过 native xref / branch-aware CFG 的独立交叉验证。**

---

## 七、CRC32 自检轨道与双轨架构

### 7.1 独立的反篡改系统

target.so 有一个完全独立于签名算法的 CRC32 自检系统：

| 组件 | 地址 | 功能 |
|-|-|-|
| sub_75C58 | 0x75C58 | IEEE CRC32 slicing-by-4 实现 |
| CRC32 表 | 0x93B44..0x94B44 | 4 张连续表，共 4KB |
| 任务对象 | vtable 驱动 | 48 字节 OOP 结构 |
| 期望值 | = 0 | 藏在数学性质里 |

`sub_75C58` 的核心循环是典型的 slicing-by-4 优化 CRC32：

```c
// sub_75C58 反编译（简化）
uint32_t crc32_slicing_by_4(uint32_t crc, const uint8_t *buf, size_t len) {
    // table[0..3] 在 0x93B44..0x94B44，每张 256 entries
    while (len >= 4) {
        uint32_t val = crc ^ *(uint32_t *)buf;
        crc = table[3][val & 0xFF]
            ^ table[2][(val >> 8) & 0xFF]
            ^ table[1][(val >> 16) & 0xFF]
            ^ table[0][(val >> 24) & 0xFF];
        buf += 4; len -= 4;
    }
    while (len--) {
        crc = table[0][(crc ^ *buf++) & 0xFF] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFF;
}
\```

CRC32 的调用方式很特别——通过 vtable / 任务对象间接调用：

```c
// 任务对象结构（48 bytes）
struct CrcTaskObject {
    uint32_t state_lo;     // offset 0x00
    uint32_t state_hi;     // offset 0x04 (框架透传，CRC32 不用)
    // ... 中间字段 ...
    void (*crc_func)(...); // offset 0x28 = 函数指针
    uint8_t *buf;          // offset 0x2C
    uint32_t len;          // offset 0x30
};

// 调用方式
(*obj->crc_func)(obj->state_lo, obj->state_hi, obj->buf, obj->len);
\```

**反逆向效果：** hook `sub_75C58` 无效——只要攻击者换掉 vtable 里的函数指针，就绕过了整个 CRC32 校验。CRC32 是可替换的"叶子算法"，真正的防线在 vtable 框架层。

### 7.2 期望值 = 0 的反逆向手法

CRC32 校验的期望值不是硬编码的魔数，而是利用了 CRC32 的数学性质：如果在数据末尾追加一个预计算的 4 字节 CRC32 值，那么整段数据（包括追加的 4 字节）的 CRC32 **必然归零**。

代码中的判断就是：

```asm
cmp r0, #0
bne fail_handler
\```

逆向者即使理解了 CRC32 的计算逻辑，也找不到一个"期望值"来比对——因为期望值就是 0，而 0 不是一个有辨识度的常量。

### 7.3 双轨并行架构

该样本的反作弊是**双轨并行**设计：

```python
轨道 1：主签名
  VMP bytecode → byte mixer → 签名输出
  目的：防伪造

轨道 2：CRC32 自检
  slicing-by-4 CRC32 → 扫 .text 段 → 期望值 = 0
  目的：防篡改
\```

两轨完全解耦，无共享代码/数据。但存在**单向依赖**：CRC32 扫描整个 .text 段，所以如果你 patch 了轨道 1 的 native handler 来做动态分析，轨道 2 的 CRC32 校验会失败。

---

## 八、def-use 链与 reg18 的追踪

### 8.1 为什么 reg18 是关键

在 mixer 入口 `0x90AC4`，`UDIVMOD acc = (reg3 /u reg18, reg3 %u reg18)` 中，`reg18` 是除数。它决定了：

1. **S-table 的大小。** 如果 reg18 = 256，S-table 有 256 个条目，和标准 RC4 一致。
2. **取模的行为。** 标准 RC4 用 `& 0xFF`（因为 256 是 2 的幂），不需要除法。这里用 UDIVMOD，说明 reg18 很可能不是 2 的幂。
3. **算法的定性。** reg18 的值是区分 "RC4 变体" 和 "完全自定义 cipher" 的关键数字。

### 8.2 静态 Backward Slice

用 handler-aware 的 def-use 分析（排除 DEFAULT handler 的字段噪声），从 idx 633（`0x90AC4`）的 `rA = 18` 反向追踪。完整的 def-use 链：

```python
R18 ← idx 595 @ 0x90A2C  raw=0x00920235 GROUP_B_LOAD   ext=0x235  uses=[R4]
│    语义: R18 = M32[R4 + imm]  从 R4 指向的内存装载
│
└─ R4 ← idx 513 @ 0x908E4  raw=0x1A048FC7 GROUP_D_ALU_IMM ext=0xFC7 uses=[R16]
   │    语义: R4 = R16 +/- 立即数  地址偏移计算
   │
   └─ R16 ← idx 476 @ 0x90850  raw=0x2FB00635 GROUP_B_LOAD ext=0x635 uses=[R29]
      │    语义: R16 = M32[R29 + offset]  从 frame 的 saved register 区装载
      │
      └─ R29 ← idx 224 @ 0x90460  raw=0xD3BDF011 GROUP_F_ALU_IMM ext=0x11 uses=[R29]
         │    语义: R29 = R29 + 立即数  frame 指针推进
         │
         └─ R29 ← idx 220 @ 0x90450  raw=0x17BD0811 GROUP_F_ALU_IMM ext=0x811 uses=[R29]
            │
            └─ R29 ← idx 0 @ 0x900E0  raw=0xEBBDF811 GROUP_F_ALU_IMM ext=0x811 uses=[R29]
               │
               └─ R29 = INPUT  ★ wrapper 的入口参数
\```

**结论：reg18 是从 wrapper 入口参数经 6 层 frame 状态链派生的。** 这条链的每一步都依赖运行时值——GROUP_B_LOAD 从内存读数据，GROUP_F_ALU_IMM 对 frame 指针做偏移。静态分析可以告诉你"reg18 来自 frame"，但无法告诉你"reg18 等于多少"。

作为对比，`reg3`（UDIVMOD 的被除数）的 backward slice 也追到了 INPUT：

```python
R3  ← idx 627 @ 0x90AAC  GROUP_F_ALU_IMM   uses=[R0]
└─ R0 ← idx 626 @ 0x90AA8  OP11_ALU_REG 0x64B  uses=[R0]
   └─ R0 ← idx 486 @ 0x90878  OP11_ALU_REG 0xF8B  uses=[R0, R31]  ← F8B frame transition!
      └─ R0 ← idx 454 @ 0x907F8  OP11_ALU_REG 0x64B  uses=[R0]
         └─ ... (11 层 0x64B 链) ...
            └─ R0 = INPUT
\```

注意 `reg3` 的 slice 经过了 `0xF8B`（F8B frame transition 指令），这进一步证实了 mixer 的输入状态依赖 frame continuation 机制。

### 8.3 Dead Def 统计的额外信息

def-use 分析还产出了一个副产品——**dead def 统计**。在 1024 条指令中有 186 个 dead def（写了某个寄存器但后续从未读取），覆盖 29 个寄存器。

| 寄存器 | dead defs | 总 defs | 总 uses | 解释 |
|-|-|-|-|-|
| R31 | 26 | 30 | 9 | R31 几乎只被写不被读，它是 F8B 的"地址源" |
| R1 | 34 | 109 | 132 | 大量中间值在被覆写前就失效了 |
| R5 | 31 | 43 | 28 | 大量 GROUP_F_ALU_IMM 写 R5 但不读 |
| R4 | 27 | 41 | 38 | 地址计算中间值 |
| ACC_LO | 2 | 2 | 0 | **商从未被使用！** 只用了余数 |

**ACC_LO 的所有 def 都是 dead** —— 这意味着 UDIVMOD 的商（R3 / R18）**从来没被使用过**，只用了余数（R3 % R18）。这完全符合 RC4 的 `i % N` 模式——你只需要取模的结果，不需要商。

### 8.4 Handler-aware 的重要性

一个容易掉进去的坑：如果用朴素的字段提取公式（`dst = ((word >> 11) & 0x1E) | (word >> 31)`）做 def-use，会在 DEFAULT handler 上产生大量假定义。例如 `idx 516 / 0x908F0` 的 raw = `0x399198D0`，按字段公式提取出 `dst = 18`，但它的 handler 是 DEFAULT——DEFAULT handler 不会写 reg18。

**规则：凡是做 VM register slice，必须使用 handler-aware 的 def/use 集合。** 裸字段公式只适合做候选点枚举。

---

## 九、CRC32 Runtime Table 的非对齐 Pivot 机制

这是整个研究中最巧妙的发现之一。

### 9.1 问题：Frame Transition 链断裂

在 unidbg 模拟执行中，VM 程序能跑到 `0x90878`（F8B frame transition），但之后的 continuation 链断裂：

```python
0x90878  F8B route → 0x908E0
0x908E0  R25 = R0 ^ 0x0000CFA2
0x908FC  R29 = sign_extend_16(*(uint16_t *)(R25 - 0x1293))
         ← 读到 0，R29 坏了，后续 frame 不成立
\```

`R25 - 0x1293` 指向的地址是 `0x9B547`（image-relative），落在 `.bss` 段内——运行时才初始化的区域。在 dummy frame 下这里全是零。

### 9.2 发现：pivot 地址落在 CRC32 Runtime Table 内部

`0x9B547` 不是一个孤立的 `.bss` 地址。IDA xref 复核发现：

```python
dword_9B1F8 = 256-entry IEEE CRC32 runtime table base
0x9B547     = dword_9B1F8 + 0x34F
            = table[0xD3] 的第 3 字节偏移
\```

`sub_274E0` 在首次调用 CRC32 时按 IEEE reflected polynomial `0xEDB88320` 生成这张表。按照标准 CRC32 表生成公式计算：

```python
table[0xD3] = 0x1FDA836E   little-endian: 6E 83 DA 1F
table[0xD4] = 0x81BE16CD   little-endian: CD 16 BE 81

bytes @ 0x9B547 = 1F CD 16 BE 81 5B 26 B9 ...
uint16_le       = 0xCD1F
sign_extend_16  = 0xFFFFCD1F
\```

### 9.3 动态验证

在 unidbg 中先调用 `sub_274E0+1`（Thumb 模式）初始化 CRC32 table，再跑 `sub_275CC`。

CRC32 表生成函数 `sub_274E0` 的核心逻辑：

```c
// sub_274E0 反编译（简化）
void crc32_init_table(uint32_t *state) {
    if (!byte_9B5F8) {  // 初始化标志
        for (int i = 0; i < 256; i++) {
            uint32_t crc = i;
            for (int j = 0; j < 8; j++) {
                if (crc & 1)
                    crc = (crc >> 1) ^ 0xEDB88320;  // IEEE reflected polynomial
                else
                    crc >>= 1;
            }
            dword_9B1F8[i] = crc;  // .bss 区域的 runtime table
        }
        byte_9B5F8 = 1;
    }
    // ... 后续 CRC 计算 ...
}
\```

unidbg 测试命令：

```bash
mvn -o -pl unidbg-android -am \
  -Dtest=com.github.unidbg.android.TargetSub275CCTest#testSub275CcDirectCall \
  -Dtarget.callCrcInitBeforeEntry=true \
  -Dtarget.enableFetchTrap=true \
  -Dtarget.patchRegsAtVmPc=0x9044c:31:module+0x90460,0x90878:31:module+0x908e0,0x90878:0:module+0x90878 \
  -Dtarget.dumpVmMemAtVmPc=0x908FC:25:-0x1293:16 \
  -Dtarget.watchVmPc=0x90878,0x908E0,0x908FC,0x90900,0x90A00,0x90AC4 \
  test
\```

关键输出日志：

```python
[crc-init.before] byte_9B5F8=0x00 table[D3]=0x00000000 table[D4]=0x00000000
                  half@9B547=0x0000 word@9B547=0x00000000 addr=0x120db547

[crc-init] call sub_274E0+1 ret=302133248 elapsed=33ms

[crc-init.after]  byte_9B5F8=0x01 table[D3]=0x1fda836e table[D4]=0x81be16cd
                  half@9B547=0xcd1f word@9B547=0xbe16cd1f addr=0x120db547
\```

CRC32 表初始化前后的对比一目了然。`table[0xD3]` 从 0 变成了 `0x1FDA836E`，`0x9B547` 处的 uint16 从 `0x0000` 变成了 `0xCD1F`。

继续跑到 `0x908FC`，pivot 读取的日志：

```python
[pivot-before] vm_pc=0x000908fc
  r25=0x120dc7da
  addr=r25-0x1293=0x120db547
  half=0xcd1f
  word=0xbe16cd1f
  r29_before=0xe4fff640

[vm-mem] vm_pc=0x000908fc r25=0x120dc7da offset=-4755
  address=0x120db547 size=16
  bytes=1fcd16be815b26b9f6e177b06f7747b7

[pivot-after] prev_vm_pc=0x000908fc next_vm_pc=0x00090900
  r29_after=0xffffcd1f      ← 完美匹配 sign_extend_16(0xcd1f)
\```

验证链条：

```python
R0  = module + 0x90878  = 0x120D0878
R25 = R0 ^ 0xCFA2       = 0x120DC7DA
addr = R25 - 0x1293      = 0x120DB547
0x120DB547 - module_base = 0x0009B547   (落在 .bss CRC32 table 内)

*(uint16_le *)0x9B547    = 0xCD1F
R29 = sign_extend_16(0xCD1F) = 0xFFFFCD1F   ✓
\```

### 9.4 设计意图分析

这个机制极其精巧：

1. **pivot 地址通过 `R0 ^ 常量 - 偏移` 计算**，让人无法直接从 bytecode 中读出 pivot 目标。
2. **pivot 数据来自运行时生成的 CRC32 table**，而不是 ELF 文件中的静态常量。这意味着如果不先初始化 CRC32 表，frame continuation 会自然断裂。
3. **读取位置是非 4 字节对齐的**，横跨 `table[0xD3]` 的最高字节和 `table[0xD4]` 的最低字节。这不是常规 C 代码的访问模式，是刻意利用大表中的稳定字节窗口。
4. **CRC32 self-check 系统和签名算法通过这个 pivot 产生了隐式耦合**——表面上两轨解耦，实际上签名算法的 frame transition 依赖 CRC32 表的初始化。

---

## 十、JNI 注册表与环境门控 Pipeline

### 10.1 JNI_OnLoad 跑出 4 个 RegisterNatives

通过 unidbg 的 Unicorn2 后端执行完整的 Dalvik 初始化链路：

```java
// unidbg 测试代码
AndroidEmulator emulator = AndroidEmulatorBuilder.for32Bit()
    .setProcessName("com.example.target.app")
    .addBackendFactory(new Unicorn2Factory(true))
    .build();
Memory memory = emulator.getMemory();
memory.setLibraryResolver(new AndroidResolver(23));
VM vm = emulator.createDalvikVM();
vm.setVerbose(true);
DalvikModule dm = vm.loadLibrary(new File("target.so"), false);
dm.callJNI_OnLoad(emulator);
\```

`.init_array` 执行日志（Unicorn2 下可以承接坏写异常并继续）：

```python
[dalvik-init] init.pre  module=target.so index=0 off=0x55c1
[dalvik-init] init.post module=target.so index=0 off=0x55c1
[dalvik-init] init.pre  module=target.so index=1 off=0x7739

stat64 /data/data/org.autojs.autojs       → ENOENT
stat64 /data/data/yk.juejin                → ENOENT
stat64 /data/data/com.cyjh.mobileanjian    → ENOENT
stat64 /data/data/com.touchsprite.android  → ENOENT

Write memory failed: address=0x93223c2a, size=4, value=0x3,
  PC=RX@0x1200a1ce[target.so]0xa1ce
emulate RX@0x1200b5f4[target.so]0xb5f4 exception
  msg=unicorn.UnicornException: Invalid memory write (UC_ERR_WRITE_UNMAPPED)

[dalvik-init] init.post module=target.so index=1 off=0x7739
[dalvik-init] loaded module=target.so base=0x12000000 size=0x9d000
\```

`.init_array[1]` 的坏写（`0x93223c2a`）是环境探测的副产物——在 unidbg 模拟环境下某些全局指针未被正确初始化。Unicorn2 可以吞掉这个异常并继续执行，Dynarmic 则会直接 abort 整个进程。

`JNI_OnLoad` 的注册输出：

```python
[dalvik-init] JNI_OnLoad symbol address=0x12004bf1 off=0x4bf1
JNIEnv->FindClass(com/example/sdk/core/a)
JNIEnv->NewGlobalRef(class com/example/sdk/core/a)
JNIEnv->RegisterNatives(com/example/sdk/core/a, unidbg@..., 4)

RegisterNative(com/example/sdk/core/a,
    meta(ILandroid/content/Context;Ljava/lang/Object;)Ljava/lang/Object;,
    RX@0x1206e2f5[target.so]0x6e2f5)

RegisterNative(com/example/sdk/core/a,
    funcA(II[B)[B,
    RX@0x120611c1[target.so]0x611c1)

RegisterNative(com/example/sdk/core/a,
    decode(I[B)[B,
    RX@0x12029bd1[target.so]0x29bd1)

RegisterNative(com/example/sdk/core/a,
    encode([B)[B,
    RX@0x12029b09[target.so]0x29b09)
\```

4 个注册方法的角色分析：

| 方法 | native 入口 | 推测角色 |
|-|-|-|
| `meta(I,Context,Object)Object` | 0x6E2F5 | 初始化 / 环境配置 |
| `funcA(II,[B)[B` | 0x611C1 | **主签名** |
| `decode(I,[B)[B` | 0x29BD1 | 解码 / 解密 |
| `encode([B)[B` | 0x29B09 | 编码 / 加密 |

**`funcA(II[B)[B` 是主签名的 Java 入口。** 它接收两个 int 参数和一个 byte[] 输入，返回签名 byte[]。该函数与其他几个签名接口（`funcB`、`funcC` 等）均以神话生物命名，共同构成反作弊的签名接口矩阵。

### 10.2 funcA 的环境门控 Pipeline

`funcA` 在进入 VMP bytecode 之前，会通过一连串 JNI 回调做环境指纹采集：

```python
Thread.currentThread() → getStackTrace() → getName()
  → ActivityThread.currentApplication()
    → faccessat(/data/data/.../files/assets.dat)
      → njss(235, null)  // Java 侧 selector dispatcher
        → ApplicationInfo.sourceDir
          → getPackageName()
            → ContentResolver → Uri.parse("content://settings/system")
              → ContentResolver.call(...)  // 读 android_id
                → ... → 最终进入 sub_24CBC → sub_275CC → mixer
\```

### 10.3 njss 的真面目

从 APK 反编译（`com/example/sdk/core/a.java`）拿到了 `njss` 的真实实现——它是一个 **selector dispatcher**，接收 `(int selector, Object obj)` 参数，按 selector 值分发到不同的 Java 桥接逻辑：

- **selector 120-130 区间**：返回环境/设备字符串（CPU型号、系统版本等）
- **selector 136**：返回 APK 签名证书 byte[]
- **selector 235**：触发 `assets.dat` 的落盘/读取
- **selector 132/234**：副作用型操作，返回 null

`njss` 不是黑盒占位函数，而是该 SDK 在 native 和 Java 之间的标准化桥接器。native 侧通过 `CallStaticObjectMethodV` 调用它，按 selector 获取设备指纹、签名材料和配置信息。

---

## 十一、走过的弯路

坑啊：

| 误判 | 纠正后的理解 | 教训 |
|-|-|-|
| 把 sub_275CC 当 主签名 算法函数 | 它是通用 VMP 解释器 | 大函数不等于算法函数 |
| 用 0xCB 密度做算法指纹 | 0xCB 是 OP11 编码副产物 | 频率指纹需要考虑编码方式 |
| 把 0x90CB0 的 IDIVMOD 并入 mixer | 它在数据走廊里，是线性 sweep 假阳性 | handler accepts ext ≠ 是代码 |
| 把 sub_2F80 当字符串解密函数 | 它是全局 dword 指针表初始化 | 不要被函数内的字节操作误导 |
| 认为 CRC32 和签名轨道完全解耦 | 通过 CRC32 table pivot 有隐式耦合 | "解耦"需要验证到数据层面 |
| 直接命名标准 RC4 | 证据只支持 RC4-like | 缺 concrete trace 不能定性 |
| 用裸字段公式做 def-use | DEFAULT handler 会产生假定义 | 必须 handler-aware |
| 裸调 sub_275CC 做动态分析 | frame 状态链全是垃圾 | 必须走真实调用路径 |

---

## 十二、设计哲学总结

通过这轮深度分析，可以提炼出该反作弊框架的几个核心设计哲学：

### 12.1 分离算法与实现

native 层是通用的 IR 解释器，上面跑的 bytecode 才是真正的算法。逆向者必须同时拿到三层才能重建：

1. **native 层**：解释器的 handler 语义（怎么执行）
2. **bytecode 层**：program 的具体指令序列（执行什么）
3. **数据层**：运行时的 frame 状态和输入参数（用什么数据）

### 12.2 热更新能力

由于算法在 bytecode 层而不是 native 层，开发者可以**不发版就换掉整个签名算法**——只要 ISA 不变，替换 `.rodata` 中的 bytecode program 就够了。这是传统 native 混淆做不到的。

### 12.3 多层 Anti-Analysis

| 层次 | 手法 | 效果 |
|-|-|-|
| 静态 | 3 份解释器克隆 + 死代码诱饵 | 浪费逆向者时间 |
| 静态 | opcode 空间膨胀（29/64 是 DEFAULT） | 频率分析失效 |
| 静态 | 数据岛内嵌在 code stream 中 | 线性 sweep 产生假指令 |
| 静态 | XOR 编码字符串在数据走廊中 | 看起来像算法代码 |
| 动态 | F8B frame transition 改变 R29 | 不是简单的 branch |
| 动态 | CRC32 table pivot 做 frame continuation | 环境不对就断裂 |
| 动态 | njss selector dispatcher 采集设备指纹 | 模拟执行缺 Java 状态 |
| 系统 | SVC #0 直接系统调用 | 绕过 libc hook |
| 系统 | stat64 检测自动化工具目录 | 检测 Frida/AutoJS 等 |

---

## 十三、穿透环境门控：从 30+ 个 JNI Stub 到 VMP 入口

### 13.1 环境门控的完整 JNI 调用链

`funcA` 在进入 VMP bytecode 之前，会通过 JNI 密集回调 Java 层采集设备指纹。整个门控链路按实际触发顺序排列：

**第一层：线程与应用上下文**

```java
Thread.currentThread()
  → getStackTrace()        // 检查调用栈是否包含可疑 frame
  → getName()              // 检查线程名是否被修改
ActivityThread.currentApplication()  // 获取 Application 实例
\```

**第二层：资产与签名验证**

```java
faccessat("/data/data/.../files/assets.dat")   // 检查资产文件是否存在
njss(235, null)                                  // selector dispatcher: 触发资产初始化
ApplicationInfo.sourceDir                        // APK 安装路径
getPackageName()                                 // 包名验证
\```

**第三层：系统设置与设备标识**

```java
ContentResolver cr = context.getContentResolver();
Uri uri = Uri.parse("content://settings/system");
cr.call(uri, "GET_system", "__MTA_DEVICE_INFO__", null);  // SDK 设备信息缓存
cr.call(uri, "GET_secure", "android_id", null);            // Android 设备唯一标识
cr.call(uri, "GET_secure", "accessibility_enabled", null); // 无障碍服务检查
\```

**第四层：反调试与反自动化**

```java
Debug.isDebuggerConnected()                    // → 返回 false
ActivityManager.isUserAMonkey()                // → 返回 false (monkey test 检查)
NetworkInterface.getByName("wlan0")            // WiFi MAC 地址采集
  → getHardwareAddress()
\```

**第五层：反 Hook 与反 Xposed**

```java
// 通过反射检查 Instrumentation 是否被替换
Class<?> atClass = Class.forName("android.app.ActivityThread");
Method currentAT = atClass.getDeclaredMethod("currentActivityThread");
Object at = currentAT.invoke(null);
Field instrField = atClass.getDeclaredField("mInstrumentation");
Object instr = instrField.get(at);
instr.getClass()  // 检查类名是否是标准的 android.app.Instrumentation

// 检查 IActivityManager 是否被代理
IActivityManager.getClass()  // 检查是否是 Proxy 类
\```

**第六层：设备指纹汇总**

```java
Build.FINGERPRINT   // "google/oriole/oriole:12/SQ3A.220705.003/..."
Build.MODEL         // "Pixel 6"
Build.MANUFACTURER  // "Google"
Build.BRAND         // "google"
Build.DEVICE        // "oriole"
Build.PRODUCT       // "oriole"
TelephonyManager.getDeviceId()  // IMEI (已过时但仍被采集)
PackageManager.getInstallerPackageName()  // "com.android.vending" (Google Play)
\```

**第七层：环境指纹打包**

```java
njss(0xEA, byte[26])  // selector 234: 把 26 字节环境摘要写入 sMetaData
                       // 注意：26 字节是输入参数，不是返回值
                       // Java 侧把它缓存进静态字段后返回 null
\```

### 14.2 逐层 Stub 的工程实践

在 unidbg 中，每一层的 mock 策略遵循同一个原则：**只记录参数，返回最小合理值，绝不伪造复杂对象。**

```java
// AbstractJni handler 中的典型 stub 模式
@Override
public DvmObject<?> callStaticObjectMethodV(BaseVM vm, DvmClass dvmClass,
                                             String signature, VaList vaList) {
    switch (signature) {
        // === 第三层：系统设置 ===
        case "android/content/ContentResolver->call(...):
            String method = vaList.getObjectArg(1).getValue().toString();
            String arg = vaList.getObjectArg(2).getValue().toString();
            System.out.printf("[jni-stub] ContentResolver.call method=%s arg=%s%n",
                method, arg);
            // 返回空 Bundle，不伪造 android_id 的具体值
            return vm.resolveClass("android/os/Bundle").newObject(null);

        // === 第四层：反调试 ===
        case "android/os/Debug->isDebuggerConnected()Z":
            System.out.println("[jni-stub] Debug.isDebuggerConnected → false");
            return DvmObject.newDvmObject(false);

        case "android/app/ActivityManager->isUserAMonkey()Z":
            System.out.println("[jni-stub] isUserAMonkey → false");
            return DvmObject.newDvmObject(false);

        // === 第六层：设备指纹 ===
        case "android/os/Build->FINGERPRINT:Ljava/lang/String;":
            return new StringObject(vm, "google/oriole/oriole:12/...");

        case "android/os/Build->MODEL:Ljava/lang/String;":
            return new StringObject(vm, "Pixel 6");

        // ... 更多 stub ...
    }
}
\```

总计补了 **30+ 个最小 stub**，覆盖 7 层环境检测。整个过程是纯机械的迭代循环：

```python
跑测试 → UnsupportedOperationException → 看方法签名 → 加最小 stub → 重跑
         ↓
没有新异常 → 检查 watchVmPc → 全 0 → 检查 funcA 返回值 → 继续分析
\```

### 14.3 30 个 Stub 之后的发现：VMP 在跑，但跑的不是算法 Bytecode

补完所有 JNI stub 后，`funcA` 不再抛任何异常，能完整执行并返回。在 `sub_275CC` 入口断点上观测到：

```python
[sub_275CC] call #1 r0=0x1208f360 bytecode_base=0x8f360
\```

但 watchVmPc（监控 `0x900E0` / `0x90AC4` 等算法 bytecode 地址）全部为 0。

**bytecode base `0x8F360` 对应的是 `sub_24C4C`——一个业务 wrapper，不是算法 wrapper。**

回看 wrapper 表：

| Wrapper | Bytecode Base | Hard Anchors | 数据岛 | 角色 |
|-|-|-|-|-|
| sub_22BB4 | 0x8EBE0 | 0 | 0 | 业务 |
| sub_22C10 | 0x8EC60 | 0 | 0 | 业务 |
| sub_24C4C | **0x8F360** | 0 | 0 | 业务 |
| sub_24CBC | 0x900E0 | 2 | 3 | 算法 |
| sub_270E8 | 0x8FFA0 | 2 | 3 | 算法 |

这解释了 watchVmPc 全 0：**监控地址全在算法 bytecode 范围内（`0x900E0..0x910E0`），而 VMP 实际执行的是业务 bytecode（`0x8F360..0x90360`）。** VM 解释器确实在正常工作，只是跑的是另一段字节码。

### 14.4 多阶段 VMP 执行模型

结合静态分析和动态观测，`funcA` 的完整执行模型很可能是：

```python
funcA @ 0x611C1
  │
  ├─ 阶段 0: 环境门控 (30+ JNI 回调)
  │    Thread → Application → Settings → Debug → Build → njss
  │
  ├─ 阶段 1: 业务 bytecode (0x8F360)  ← 当前走到这里
  │    sub_24C4C → sub_275CC(0x8F360)
  │    可能做: 环境校验 / 状态初始化 / token 生成
  │
  ├─ 阶段 2: 算法 bytecode (0x900E0)  ← 目标
  │    sub_24CBC → sub_275CC(0x900E0)
  │    做: RC4-like mixer → 签名输出
  │
  └─ return byte[]
\```

当前停在阶段 1 没进入阶段 2 的原因，最可能是 **`meta()` 没有被提前调用**。

### 14.5 `meta()` 初始化假说

JNI 注册表中 `meta` 排在 `funcA` 前面：

```python
RegisterNative: meta(I,Context,Object)Object  → 0x6E2F5  // 初始化
RegisterNative: funcA(II,[B)[B                 → 0x611C1  // 签名
RegisterNative: decode(I,[B)[B                 → 0x29BD1  // 解码
RegisterNative: encode([B)[B                   → 0x29B09  // 编码
\```

在真实 app 中，Java 层的调用序列大概率是：

```java
// Application.onCreate 或 ContentProvider 中
a.meta(0, context, null);           // 初始化全局状态

// 网络请求拦截器中
byte[] signature = a.funcA(type, timestamp, payload);  // 生成签名
\```

`meta()` 可能做以下几件事：

1. 设置某些全局标志位，让 `funcA` 知道"初始化已完成，可以走算法路径"
2. 预热 CRC32 table（我们已经确认 `sub_274E0` 可以初始化它）
3. 解析 `assets.dat` 并把密钥/配置写入全局变量
4. 初始化 VMP 解释器的某些共享状态

**如果不先调 `meta()`，`funcA` 可能检测到全局状态未就绪，就只跑业务 bytecode 做降级处理（比如返回一个占位签名或空值），而不进入算法路径。**

## 十四、未完成（设备还没有搞好）

| 里程碑 | 卡点 |
|-|-|
| reg18 的 concrete value | 需要真实 JNI 路径执行到 0x90AC4 |
| S-table 初始状态 dump | 依赖 reg18 |
| mixer 完整一轮 I/O trace | 依赖 S-table |
| 算法公式拟合（RC4 vs 自定义） | 依赖 mixer I/O |
| 完整算法文档 | 依赖上述全部 |

### 动态验证的最短路径

当前 unidbg 实验已经走到 `funcA` 的环境门控层（`ContentResolver.call`）。后续需要：

1. 逐层 mock JNI 回调（Uri.parse → ContentResolver.call → 可能还有几层）
2. 穿过环境门控后，`funcA` 应该会调用 `sub_24CBC` 或等价的 VMP wrapper
3. `sub_24CBC` 会构造正确的 frame 并进入 `sub_275CC`
4. 在 BKPT fetch trap 上观测 `0x90AC4` 的首达
5. 首达瞬间 dump reg18 + S-table + mixer 一轮 I/O

**一旦 `0x90AC4` 被真实路径命中，reg18 的值就定了，算法还原从"猜骨架"变成"拟合公式"，剩下的只是体力活而已。**

---

上传的附件：
- unidbg_android_tests_20260524.zip

（97.96kb，60次下载）

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2026-5-24 17:33*

感谢分享

## 回复 by 温泉划水鱼 (#3)

*2026-5-24 19:52*

看看

## 回复 by SomeMx (#4)

*2026-5-24 20:30*

学习一下

## 回复 by mb_ghcouuzx (#5)

*2026-5-24 21:10*

大佬能出一篇ollvm混淆的么？  或者有已经好的ndk,我自己在编译ollvm,用的时候会有错误，导致有一些东西用不了混淆，我的是windows,

## 回复 by 墨穹呢 (#6)

*2026-5-24 21:26*

感谢分享

## 回复 by flysea (#7)

*2026-5-24 23:15*

大佬的思路清晰，分析手法纯熟，值得学习

## 回复 by 随风而行aa (#8)

*2026-5-25 10:01*

看看

## 回复 by mb_xjdhrmck (#9)

*2026-5-25 10:16*

6666

## 回复 by method (#10)

*2026-5-25 10:37*

1

## 回复 by 钱钱钱￥ (#11)

*2026-5-25 10:43*

111

## 回复 by TeamAR (#12)

*2026-5-25 11:22*

666

## 回复 by baichisi (#13)

*2026-5-25 11:33*

666

## 回复 by apxar (#14)

*2026-5-25 13:44*

1

## 回复 by 不具名的悲伤 (#15)

*2026-5-25 13:48*

6

## 回复 by mb_mlyojneh (#16)

*2026-5-25 13:50*

感谢分享

## 回复 by Imxz (#17)

*2026-5-25 16:12*

tql

## 回复 by dob_C (#18)

*2026-5-25 16:38*

感谢分享

## 回复 by ben_ (#19)

*2026-5-25 17:20*

学习

## 回复 by wx_北极星_493 (#20)

*2026-5-25 17:22*

看看

## 回复 by mb_cbgtaveo (#21)

*2026-5-25 17:42*

666666

## 回复 by XCicada (#22)

*2026-5-25 20:19*

看看

## 回复 by mb_ebihoycp (#23)

*2026-5-25 22:06*

666

## 回复 by 末日大哥 (#24)

*2026-5-25 22:13*

666

## 回复 by 阿腊婆 (#25)

*2026-5-26 00:17*

1

## 回复 by iBa0 (#26)

*2026-5-26 11:48*

123

## 回复 by mb_ykavguun (#27)

*2026-5-26 12:23*

1

## 回复 by huangjw (#28)

*2026-5-26 14:07*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by 发烧小孩 (#29)

*2026-5-26 15:18*

666

## 回复 by wx_Dispa1r (#30)

*2026-5-26 15:48*

123

## 回复 by wx_Dispa1r (#31)

*2026-5-26 15:58*

梦到哪里写哪里，夸张哦

## 回复 by mb_pesxllvn (#32)

*2026-5-26 18:24*

666

## 回复 by 抬头望月 (#33)

*2026-5-26 18:50*

111

## 回复 by wx_huhu_859 (#34)

*2026-5-26 20:14*

11

## 回复 by ycdear (#35)

*2026-5-26 21:18*

2

## 回复 by kingking888 (#36)

*2026-5-26 21:27*

666

## 回复 by AGSFGBKILO (#37)

*2026-5-26 21:47*

太强了大佬，学到了

## 回复 by Dircou (#38)

*2026-5-26 23:11*

为过检测而来

## 回复 by zz胡 (#39)

*2026-5-27 00:58*

6666666

## 回复 by 聂风云 (#40)

*2026-5-27 07:39*

666

## 回复 by mJqalJqN (#41)

*2026-5-27 11:22*

1

## 回复 by s1nec-1o (#42)

*2026-5-27 11:35*

1

## 回复 by 乐活 (#43)

*2026-5-27 11:39*

1

## 回复 by Zkeleven (#44)

*2026-5-27 14:05*

6666666

## 回复 by B.M.K (#45)

*2026-5-28 00:01*

1

## 回复 by GEKEZYX (#46)

*2026-5-28 00:27*

666

## 回复 by 淡然他徒弟 (#47)

*2026-5-28 01:07*

mark

## 回复 by wx_插曲 (#48)

*2026-5-28 07:55*

6

## 回复 by maomaolk (#49)

*2026-5-28 11:39*

666

## 回复 by mb_euhyowpw (#50)

*2026-5-28 11:39*

wqe

## 回复 by taeyeon_ss (#51)

*2026-5-28 11:51*

999

## 回复 by mb_aopnnvxb (#52)

*2026-5-28 13:45*

mark

## 回复 by guijingwen (#53)

*2026-5-28 21:22*

66

## 回复 by chaoi (#54)

*2026-5-29 01:25*

6666

## 回复 by 一只鸭子 (#55)

*2026-5-29 08:22*

感谢分析

## 回复 by k4y0z (#56)

*2026-5-29 11:14*

666

## 回复 by k4y0z (#57)

*2026-5-29 11:24*

CRC(M | CRC(M)) = 0, 这样做的目的明显是为了方便后期插入CRC预期值

## 回复 by jamlops (#58)

*2026-5-29 23:32*

看看我看看

## 回复 by mb_uejrlqsu (#59)

*2026-5-30 01:59*

感谢分享

## 回复 by mb_nkjfyhkg (#60)

*2026-5-31 14:11*

mark

## 回复 by mb_bfghjvta (#61)

*2026-5-31 18:43*

看看 vmp 内容

## 回复 by @@@ (#62)

*2026-5-31 20:10*

666666

## 回复 by Zepp7289 (#63)

*2026-5-31 20:15*

tql

## 回复 by fuqiuluo73 (#64)

*2026-6-1 14:03*

111

## 回复 by 章康 (#65)

*2026-6-1 20:49*

666

## 回复 by mb_ahwcqero (#66)

*2026-6-3 08:44*

学习

## 回复 by Squirre17 (#67)

*2026-6-3 20:01*

求问这个是什么样本呢

## 回复 by 简单的简单 (#68)

*2026-6-3 22:08*

666

## 回复 by 夜惜风雨 (#69)

*2026-6-4 09:44*

66666666666

## 回复 by hanjiefang (#70)

*2026-6-5 15:27*

1

## 回复 by mb_nggigxxl (#71)

*2026-6-5 23:16*

666

## 回复 by wx_RickBron_553664 (#72)

*2026-6-8 09:48*

11

## 回复 by Bonquer (#73)

*2026-6-8 09:52*

666

## 回复 by 啊你好哇123 (#74)

*2026-6-9 01:13*

学习学习

## 回复 by mb_agxdcibq (#75)

*2026-6-9 01:31*

6

## 回复 by Ahzn (#76)

*2026-6-9 04:35*

敖包相会  寄层器

## 回复 by Ahzn (#77)

*2026-6-9 04:39*

敖包相会 寄存器

## 回复 by hhoun (#78)

*2026-6-9 09:09*

666

## 回复 by mb_njwchjvd (#79)

*2026-6-14 10:59*

666

## 回复 by つきよみ (#80)

*2026-6-17 10:28*

6666

## 回复 by mb_zndfsnle (#81)

*2026-6-17 12:03*

看看

## 回复 by mb_audxeeaj (#82)

*2026-6-17 16:36*

看看

## 回复 by wx_leo_346548 (#83)

*2026-6-18 11:24*

1

## 回复 by wx_白鸟之诗 (#84)

*2026-6-18 16:15*

666

## 回复 by bullyxy (#85)

*2026-6-22 00:02*

谢谢分享！

## 回复 by blackr0ck (#86)

*2026-6-22 00:52*

1

## 回复 by 易始 (#87)

*2026-6-22 19:53*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by 何森 (#88)

*2026-6-24 10:44*

允许楼主上二楼

## 回复 by 袁伟业 (#89)

*2026-6-24 11:14*

6666

## 回复 by Sungt. (#90)

*2026-6-24 11:29*

1

## 回复 by mb_sdskxvsq (#91)

*2026-6-25 08:18*

666

## 回复 by mb_jnmxfjku (#92)

*2026-6-26 16:53*

666

## 回复 by 伊苏尔德 (#93)

*2026-6-28 15:38*

1

## 回复 by Circ1e (#94)

*2026-6-30 10:07*

1

## 回复 by mb_vdakxenl (#95)

*2026-7-6 16:57*

6666

## 回复 by git_84461osscv (#96)

*2026-7-7 00:12*

学习一下

## 回复 by wx_kx92911 (#97)

*2026-7-9 10:05*

感谢分析

## 回复 by git_46644wzxwhxcz (#98)

*2026-7-10 11:34*

看看

## 回复 by mb_sezgvuqb (#99)

*2026-7-10 11:45*

111

## 回复 by blx2024 (#100)

*2026-7-11 12:31*

感谢分享

## 回复 by mb_iiumogmn (#101)

*2026-7-12 22:59*

感谢分享

## 回复 by 天涯共何时 (#102)

*2026-7-15 11:40*

666

## 回复 by mb_mnqaubnh (#103)

*2026-7-18 00:34*

6

## 回复 by mb_sjnafgkp (#104)

*2026-7-18 00:46*

1

## 回复 by mb_efxrdkzw (#105)

*2026-7-18 13:59*

6666

## 回复 by haris4687 (#106)

*2026-7-19 09:01*

66

## 回复 by mb_qztkkwxt (#107)

*2026-7-24 10:53*

666

## 回复 by 看风听雨 (#108)

*2026-7-24 12:01*

1

## 回复 by 跟哥哥有糖 (#109)

*2026-7-27 03:41*

1

## 回复 by mb_exfahkom (#110)

666

## 回复 by mb_irhdtnzm (#111)

1
