---
title: '[原创] c-sktrace：基于 C 实现的 sktrace 性能优化 demo'
url: https://bbs.kanxue.com/thread-288909.htm
tid: 288909
author: vwvw
date: '2025-10-26'
tags: [Android安全, 原创, 基础理论, 逆向分析, 程序开发, 工具脚本]
crawled_at: '2026-08-08T10:38:55+00:00'
replies: 64
---

# c-sktrace：基于 C 实现的 sktrace 性能优化 demo

## 前言

这是一个学习性质的项目，研究如何通过 Frida 的 CModule 实现高性能指令追踪。虽然 Frida 官方已经有了 [frida-itrace](https://github.com/frida/frida-itrace) 这个成熟方案，但直接用 CModule 手写可以更深入理解 Stalker 的工作原理和性能优化思路。

项目地址：https://github.com/vwww-droid/c-sktrace

---

## 解决了什么问题

原始的 JavaScript 实现在进行密集指令追踪时存在严重的卡顿问题，主要体现在：

- **热代码路径卡顿**：追踪循环体、频繁调用的函数时响应缓慢
- **数据输出延迟**：大量指令执行后才能看到结果
- **目标进程被拖慢**：被追踪的应用明显变慢甚至无响应

通过 C 实现后，性能提升约两三个数量级（没细测，不过提升明显），实现了无卡顿的实时追踪。

---

## 性能瓶颈分析

### JS 版本执行流程

| 123456789101112131415 | `function` `stalkerTraceRange(tid, base, size) {``Stalker.follow(tid, {``transform: (iterator) => {``do` `{``iterator.keep();``if` `(isModuleCode) {``// ! 性能问题：每条指令都注册 JS 回调``iterator.putCallout((context) => {``send({...})` `// Native → JS 切换``})``}``}` `while` `(iterator.next() !==` `null``);``}``})``}` |
|-|-|

### Runtime 阶段开销

| 123456789 | `目标代码执行到被 trace 的指令``↓``Callout 触发：Native 代码暂停``↓ 切换到 JS 引擎``执行 JS 回调函数``↓ JSON 序列化 context``调用 send()（进程间通信）``↓ 切回 Native``恢复目标代码执行` |
|-|-|

**示例**：追踪一个执行 10,000 次的循环

- 每次循环 before + after callout = 2 次切换
- **总计：20,000 次 Native ↔ JS 引擎切换**

### 引擎切换的开销

每次切换需要：

1. 保存/恢复 CPU 上下文（所有寄存器）
2. 切换 JS 引擎执行上下文
3. 数据序列化/反序列化（`context` 对象 → JSON）
4. 进程间通信

**还是很大的性能消耗**

---

## 解决方案：CModule + Python 异步处理

### 核心思路

既然无法消除所有 JS 交互，那就：

1. **C 层**：只负责快速读取并输出寄存器值
2. **Python 层**：异步接收数据并进行比较、统计

### 优势

- ✅ 消除 JSON 序列化开销
- ✅ 使用简洁的管道分隔格式
- ✅ C 层只做读取，稳定高效
- ✅ Python 异步处理不阻塞 trace

---

## 实现细节

### 1. Transform 函数

| 1234567891011121314151617181920212223242526272829303132333435363738 | `void` `transform(GumStalkerIterator *iterator,``GumStalkerOutput *output,``gpointer user_data)``{``cs_insn *insn;``gpointer base = *(gpointer*)user_data;``gpointer end = *(gpointer*)(user_data +` `sizeof``(gpointer));` `while` `(gum_stalker_iterator_next(iterator, &insn))``{``gboolean in_target = (gpointer)insn->address >= base &&` `(gpointer)insn->address < end;` `if``(in_target)``{``// 输出指令信息（tab 分隔）``log``(``"%p\t%s\t%s"``, (gpointer)insn->address,` `insn->mnemonic, insn->op_str);` `// 注册 before callout``gum_stalker_iterator_put_callout(iterator,` `on_arm64_before,` `(gpointer)insn->address,` `NULL);``}` `gum_stalker_iterator_keep(iterator);` `if``(in_target)` `{``// 注册 after callout``gum_stalker_iterator_put_callout(iterator,` `on_arm64_after,` `(gpointer)insn->address,` `NULL);``}``}``}` |
|-|-|

### 2. Callout 函数

| 12345678910111213141516171819202122232425262728 | `static` `void``on_arm64_before(GumCpuContext *cpu_context, gpointer user_data)``{``// 空 - 不做任何操作``}` `static` `void``on_arm64_after(GumCpuContext *cpu_context, gpointer user_data)``{``// 输出所有寄存器，Python 端做比较``// 格式: addr\|x0\|x1\|x2\|...\|x28\|fp\|lr\|sp\|pc``if` `(cpu_context) {``log``(``"%p\|%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|"``"%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|"``"%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|%llx\|"``"%llx\|%llx\|%llx\|%llx"``,``user_data,``cpu_context->x[0], cpu_context->x[1], cpu_context->x[2], cpu_context->x[3],``cpu_context->x[4], cpu_context->x[5], cpu_context->x[6], cpu_context->x[7],``cpu_context->x[8], cpu_context->x[9], cpu_context->x[10], cpu_context->x[11],``cpu_context->x[12], cpu_context->x[13], cpu_context->x[14], cpu_context->x[15],``cpu_context->x[16], cpu_context->x[17], cpu_context->x[18], cpu_context->x[19],``cpu_context->x[20], cpu_context->x[21], cpu_context->x[22], cpu_context->x[23],``cpu_context->x[24], cpu_context->x[25], cpu_context->x[26], cpu_context->x[27],``cpu_context->x[28],``cpu_context->fp, cpu_context->lr, cpu_context->sp, cpu_context->pc);``}``}` |
|-|-|

### 3. 数据传输格式

通过不同的分隔符区分两种消息：

**指令信息**（tab 分隔）：

| 1 | `0x75669d71c0`    `add x0, x1, x2` |
|-|-|

**寄存器信息**（管道分隔，34 个字段）：

| 1 | `0x75669d71c0``\|f1\|``7828a7654c``\|``7828a7654c``\|``7fdce415f8``\|``30``\|``7fdce414a0``\|...\|``7fdce41630``\|``75669d71c0` |
|-|-|

### 4. Python 端处理

| 1234567891011121314151617181920212223242526272829 | `def` `on_message(``self``, payload):``type` `=` `payload[``'type'``]` `if` `type` `=``=` `'c_output'``:``message` `=` `payload[``'message'``]` `if` `'\|'` `in` `message:``# 寄存器信息``parts` `=` `message.split(``'\|'``)``if` `len``(parts)` `=``=` `34``:``addr` `=` `parts[``0``]``x_regs` `=` `[``int``(parts[i],` `16``)` `for` `i` `in` `range``(``1``,` `30``)]``fp` `=` `int``(parts[``30``],` `16``)``lr` `=` `int``(parts[``31``],` `16``)``sp` `=` `int``(parts[``32``],` `16``)``pc` `=` `int``(parts[``33``],` `16``)` `ctx` `=` `Arm64Ctx(pc, sp,` `*``x_regs, fp, lr)``self``.inst_dict[addr].add_execed_ctx(ctx)``self``.inst_dict[addr].cal_regs_change(``self``.pre_ctx, ctx)``self``.pre_ctx` `=` `ctx` `elif` `'\t'` `in` `message:``# 指令信息``parts` `=` `message.split(``'\t'``)``if` `len``(parts)` `=``=` `3``:``addr, mnem, op` `=` `parts``inst` `=` `Inst(addr, addr,` `4``, mnem, op)``self``.inst_dict[addr]` `=` `inst` |
|-|-|

---

## 性能对比

| 场景 | JS 实现 | C 实现 |
|-|-|-|
| Transform 阶段 | 每条指令切换一次 | **在 C 层完成，零切换** |
| Runtime Callout | 每次执行切换一次 | **在 C 层完成，零切换** |
| 数据输出 | 每条指令 JSON 序列化 + send() | **简洁文本格式，批量输出** |
| 实际体验 | 密集 trace 时卡顿明显 | **无卡顿，实时输出** |

**性能提升**：约两三个数量级（没细测，不过提升明显）

---

## 总结

**为什么慢？**

- 每条指令执行时 Native ↔ JS 切换开销巨大
- 热代码路径中累积成灾难性性能损失

**怎么改？**

- 用 CModule 把 transform 和 callout 实现为 C 代码
- C 层只做数据采集，Python 层做复杂处理
- 保持在 Native 层执行，消除引擎切换

**效果？**

- 密集 trace 场景下无卡顿
- 实时输出响应快速
- 目标进程基本不受影响

---

## 参考资料

- **源项目地址**: https://github.com/bmax121/sktrace
- **项目地址**: https://github.com/vwww-droid/c-sktrace
- **Frida 官方 itrace**: https://github.com/frida/frida-itrace
- **Frida C API**: https://frida.re/docs/c-api/
- **Frida Stalker**: https://frida.re/docs/javascript-api/#stalker

上传的附件：
- ollvm9.apk

（1.60MB，30次下载）

---

# 回复

## 回复 by KanXue_NG (#2)

*2025-10-26 20:40*

学习学习

## 回复 by MaYil (#3)

*2025-10-26 21:35*

感谢分享

## 回复 by cpannn (#4)

*2025-10-26 21:47*

区别是什么

## 回复 by mb_ldbucrik (#5)

*2025-10-26 23:39*

感谢分享

## 回复 by mb_xxezghuh (#6)

*2025-10-27 05:35*

学习学习

## 回复 by 丶咖啡猫丶 (#7)

*2025-10-27 09:21*

666

## 回复 by 西瓜帅 (#8)

*2025-10-27 09:22*

学习徐诶

## 回复 by mb_irhdtnzm (#9)

*2025-10-27 09:38*

1

## 回复 by Ram98 (#10)

*2025-10-27 09:49*

666

## 回复 by iBa0 (#11)

*2025-10-27 09:50*

看看

## 回复 by wx_范迪塞尔 (#12)

*2025-10-27 10:14*

原理还是没改变，跟踪的指令pc指向的地址都变成new出来的了

## 回复 by Imxz (#13)

*2025-10-27 10:17*

6

## 回复 by mb_cbgtaveo (#14)

*2025-10-27 10:42*

6666666666666

## 回复 by einsteinzl (#15)

*2025-10-27 10:42*

666

## 回复 by kingking888 (#16)

*2025-10-27 13:04*

666

## 回复 by mb_qimctavn (#17)

*2025-10-27 13:08*

6

## 回复 by 夏洛魂 (#18)

*2025-10-27 13:47*

看看

## 回复 by xianhuimin (#19)

*2025-10-27 13:52*

学习，感谢分享

## 回复 by lbunknow (#20)

*2025-10-27 15:37*

hh

## 回复 by 随风而行aa (#21)

*2025-10-27 15:55*

看看

## 回复 by bobbiedev (#22)

*2025-10-27 16:04*

看看

## 回复 by mb_wuevwbec (#23)

*2025-10-27 17:52*

看看

## 回复 by fangliangz (#24)

*2025-10-28 09:05*

看看

## 回复 by huangjw (#25)

*2025-10-28 09:13*

66666

## 回复 by tyeying (#26)

*2025-10-28 11:29*

666

## 回复 by ldehua (#27)

*2025-10-28 13:08*

666

## 回复 by 快乐的小跳蛙 (#28)

*2025-10-28 13:50*

为什么不实现一个c++的so文件通过外部调用trace功能的方案呢

## 回复 by Thehepta (#29)

*2025-10-28 14:05*

1

## 回复 by 黑屏 (#30)

*2025-10-29 08:47*

666

## 回复 by wx_huhu_859 (#31)

*2025-10-29 14:02*

11

## 回复 by Sharp_Wang (#32)

*2025-10-30 10:33*

666

## 回复 by 心如芷水 (#33)

*2025-10-30 14:10*

66666

## 回复 by TeamAR (#34)

*2025-10-30 14:34*

66666

## 回复 by Freax (#35)

*2025-10-30 15:29*

666

## 回复 by 温泉划水鱼 (#36)

*2025-10-30 20:01*

nice

## 回复 by 任拓数据 (#37)

*2025-10-31 15:28*

6666

## 回复 by mb_4nrpVMxJ (#38)

*2025-11-2 07:34*

666

## 回复 by Gryffindoss (#39)

*2025-11-2 11:15*

66

## 回复 by 毛毛毛毛虫 (#40)

*2025-11-2 13:59*

学习一下

## 回复 by wx_插曲 (#41)

*2025-11-2 17:44*

6666

## 回复 by ben_ (#42)

*2025-11-3 17:02*

学习

## 回复 by mb_nkjfyhkg (#43)

*2025-11-8 02:27*

mark

## 回复 by 温泉划水鱼 (#44)

*2025-11-10 14:00*

全在c++处理最快

## 回复 by 贪欲. (#45)

*2025-11-10 14:48*

6666666666

## 回复 by uni7corn (#46)

*2025-11-10 15:18*

感谢分享。

## 回复 by logeye (#47)

*2025-11-10 15:59*

6666

## 回复 by mb_lnulnxbg (#48)

*2025-11-12 13:57*

666

## 回复 by FMNS (#49)

*2025-11-14 21:17*

66666

## 回复 by jw8888 (#50)

*2025-11-16 15:49*

6666666

## 回复 by Majh (#51)

*2025-11-21 22:07*

12

## 回复 by wx_听书人 (#52)

*2025-11-25 01:08*

666

## 回复 by mb_atdqqbte (#53)

*2025-11-25 13:56*

666

## 回复 by 曰你 (#54)

*2025-11-25 18:02*

111

## 回复 by schao (#55)

*2025-11-26 11:51*

6

## 回复 by ovo_帮我不c (#56)

*2025-11-28 15:40*

1

## 回复 by dawnsky1111 (#57)

*2025-12-11 16:54*

6

## 回复 by amwpecel (#58)

*2025-12-19 08:25*

坎坎坷坷

## 回复 by sorely (#59)

*2026-1-19 01:20*

学习学习

## 回复 by mb_rewimxhj (#60)

*2026-1-19 07:21*

看看

## 回复 by mb_ttdxmirg (#61)

*2026-3-16 20:57*

666666

## 回复 by 嘎嘎真的很棒 (#62)

*2026-4-12 19:07*

66666

## 回复 by XCicada (#63)

*2026-4-12 20:25*

感谢

## 回复 by mb_xjdhrmck (#64)

*2026-5-21 12:20*

6666

## 回复 by wx_Huber Barrientos (#65)

*2026-6-27 08:01*

666
