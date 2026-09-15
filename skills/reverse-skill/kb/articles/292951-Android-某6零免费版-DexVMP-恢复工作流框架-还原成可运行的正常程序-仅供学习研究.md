---
title: '[原创]Android 某6零免费版 DexVMP 恢复工作流框架：还原成可运行的正常程序,仅供学习研究'
url: https://bbs.kanxue.com/thread-292951.htm
tid: 292951
author: LeoChen..
date: '2026-09-15'
tags: [Android安全, 原创, 逆向分析, 脱壳反混淆]
crawled_at: '2026-09-15T08:48:45+00:00'
replies: 26
---

## 前言

最近整理了一套 Android 某6零免费版 DexVMP 学习研究工作流，目标是把符合条件的某6零免费版加固样本还原为可运行的正常程序，同时避免把流程做成“点一下就脱壳”的黑盒脚本。APK 分析被拆成可暂停、可复核、可追溯的阶段：每一步都保存输入、配置、日志、产物和 SHA-256，遇到证据不足就停下来，而不是用旧样本参数硬套当前 APK。

完整环境要求、JADX/IDA Pro MCP/Apktool 配置、ADB/root 真机准备、命令模板和结果验收均在上述文档中。

这套框架已经在实际研究中成功完成过程序还原流程。按照当前设计，理论上对某6零免费版加固样本具有通用的分析与还原路径；但不同 APK、Android 版本、ABI、加固版本和业务校验差异很大，是否适用必须以当前样本的证据链为准，不能理解为无需适配即可覆盖所有某6零免费版或所有程序。

>
> **适用范围（请先阅读）**：本文和仓库只针对某6零免费版样本的学习研究和授权分析。付费版、商业版及其专属保护方案不在提供范围内，不提供对应样本、参数、适配、还原服务或技术支持；任何付费版请求均不受理。
>
>
>

>
> **重要声明**：本文和仓库仅用于 Android 安全、逆向工程和软件保护机制的学习研究。请只分析自己拥有或明确获准分析的 APK、DEX、SO 和设备，不要用于盗版、绕过商业授权、账号风控或其他未授权用途。文中流程不会保证对所有 Android 版本、所有保护版本或所有业务校验有效。
>
>
>

## 使用范围、法律风险与下架联系

本项目及本文仅限个人学习、技术交流和经授权的安全研究，非商业用途。付费版、商业版及其专属保护方案不提供任何分析、适配、还原或技术支持。请勿将本文用于破解收费软件、绕过商业授权、签名校验、账号风控、盗版分发、侵犯著作权或其他未经授权的行为。使用者必须自行确认拥有目标 APK、DEX、SO、设备和数据的合法分析权限，并自行承担使用过程中的法律、合规和安全责任。

本文不提供任何商业化授权，也不保证对特定程序、特定版本或特定保护方案有效。若内容涉及您的权利、隐私、授权范围或其他需要处理的问题，请联系 `leochen-job@outlook.com`，并提供具体文章/仓库链接、涉及文件和处理理由。收到有效通知后，我会及时核查并配合下架相关内容。

项目地址：<https://github.com/LeoChen-CoreMind/android-vmp-recovery-workflow>

如果这个工作流对你的学习研究有帮助，欢迎在 GitHub 点个 Star

**开源协议（请先阅读）**：
https://github.com/LeoChen-CoreMind/android-vmp-recovery-workflow/blob/main/LICENSE.md

本文和仓库采用上述某6零免费版 DexVMP 学习研究源代码许可。该许可仅允许某6零免费版的个人学习、技术交流和经授权的非商业研究；付费版、商业版及其专属保护方案不提供样本、参数、适配、还原服务或技术支持。由于明确限制商业使用，该协议属于自定义源代码许可，不是 OSI 认证的标准开源许可证。

**使用方法（请点击下面的完整链接）**：
https://github.com/LeoChen-CoreMind/android-vmp-recovery-workflow/blob/main/docs/%E4%BD%BF%E7%94%A8%E6%96%B9%E6%B3%95.md

## 能学到什么

- 建立 APK、DEX、SO、IDA 响应和运行日志之间的 SHA-256 证据链；
- 理解 spawn-gating、私有 linker、手工映射代码区和 `JNI_OnLoad` 前取证的时序；
- 使用 IDA Pro MCP 从当前 fixed SO 提取 dispatcher/handler 表，并用 Unicorn 对同一份 SO 做原生交叉验证；
- 判断什么时候存在真实 VMP method records，如何避免把普通 DEX dump 误报成已恢复 DEX；
- 使用 dexdump、JADX、Apktool、zipalign 和 apksigner 完成独立检查；
- 学习按当前 APK/revision 生成 adapter，而不是照搬其他版本的偏移、调用次数或 DEX 布局。

## 一、为什么要把流程拆开

DexVMP 类保护通常同时涉及 Java 层启动壳、运行时 DEX、私有 linker、手工映射代码区和 native dispatcher。单独拿到一份“能反编译的 DEX”并不等于完成了方法恢复；同样，Frida 能启动也不代表已经取得了正确的私有 linker。

因此工作流把结论分成不同证据等级：

1. APK/DEX 输入是否可复现；
2. 真机目标和 ABI 是否匹配；
3. 私有 linker/SO 是否有完整运行时元数据；
4. SO 修复和 IDA dispatcher 表是否来自同一份二进制；
5. Unicorn 是否对 256 个 dispatcher 路径完成原生确认；
6. 是否存在真实 VMP method records，能否进行方法级 DEX 恢复；
7. dexdump、JADX、哈希和重打包验收是否独立通过。

## 二、整体流程

\```
APK/运行时 DEX
  -> ingest 与 SHA-256
  -> ADB/root/ABI 目标确认
  -> Frida spawn-gating
  -> 私有 linker/SO dump
  -> SoFixer 修复
  -> IDA Pro MCP 导出 dispatcher/handler 表
  -> Unicorn 对同一 SO 二次确认
  -> 有 method records 时恢复 DEX
  -> dexdump/JADX 独立验证
  -> 当前版本 adapter 去特征、重打包和签名
\```

整个过程由 `vmpwf` 驱动。案件目录保存在 `cases/<package>/<case-id>/`，包括 `input`、`dump`、`fix`、`ida`、`simulation`、`repack`、`reports` 和 `logs` 等目录，以及 `case.json`、`checkpoint.json`、`questions.json`、`events.jsonl`、`artifacts.json` 状态文件。

## 三、流程原理详解

### 1. 为什么先做 DEX dump

DEX 是 Java/Kotlin 层逻辑的入口。加固后的磁盘 DEX 可能只有启动壳、占位方法或被替换的指令流，直接用 JADX 阅读往往只能看到壳代码。因此第一步先提取 APK 中的 `classes*.dex`，必要时再登记运行时 dump 的 DEX，建立当前 APK 的可分析基线。

这里重点不是“先拿到一份能反编译的文件”，而是确认输入事实：包名、版本、ABI、DEX 数量、文件大小、SHA-256、header/map_list 是否合理，以及 LM/VMP inventory 中的 `method_records` 数量。普通 dump 只代表输入证据，不能因为 checksum 正确就称为“已恢复”。

如果 `method_records=0`，说明当前 DEX 没有可进入方法流恢复的记录；流程仍可继续做 SO、dispatcher 和运行时研究，但最终必须明确写成“本案没有可恢复的 VMP 方法”。

### 2. Frida 脚本为什么要在启动时 dump SO

磁盘里的保护 SO 可能经过压缩、加密、重定位或只保留了加载所需内容；真正执行的代码和动态表是在进程启动后由 loader/私有 linker 组织出来的。因此需要在已授权的 root 真机上使用 Frida spawn-gating：先启动目标进程，再在其恢复执行前加载脚本，观察模块加载和关键初始化时序。

采集的重点包括当前进程、`loadStart`、`loadSize`、私有 `soinfo`（或等价动态表证据）、ELF program headers、`PT_LOAD`、`PT_DYNAMIC`、动态字符串/符号表以及必要的运行时指针。这样得到的不是“随便一段内存”，而是能支撑后续修复和静态分析的私有 linker/SO 证据。

这里使用 spawn-gating 而不是 late attach，是为了在目标 `JNI_OnLoad` 和反调试初始化前完成取证。普通外层 `libjiagu` 映射或 APK 资产副本缺少运行时动态表证据，不能直接当作私有 linker。

### 3. 为什么要导出 dispatcher/handler 表

DexVMP 的 native 虚拟机通常把字节码 opcode 分派到一组 handler。仅凭函数名或单个反汇编片段无法确认完整语义，所以先对当前案件的 fixed SO 做结构化分析：从调用链、指针槽、交叉引用和反汇编中定位 dispatcher，再导出 opcode 到 handler 的映射、宽度候选、证据路径和二进制哈希。

IDA Pro MCP 的价值是让函数、反汇编、交叉引用和 JSON 响应可重复记录，而不是依赖手工截图。`image_base` 表示静态文件在 IDA 中的装载基准，`pointer_base` 表示运行时重定位后的指针基准，两者必须分开，不能把 ASLR 地址直接当作可复用 RVA。

表的最低完整性要求是覆盖 `0..255` 的 256 个 opcode，每一项 handler 都落在当前 SO 的合法代码范围内，并且响应中的 SO SHA-256 与 `so-repair` 产物一致。缺项、重复项、多个未决宽度或哈希不匹配时应停在 `BLOCKED`。

### 4. 为什么还要用模拟器确认

这里的“模拟器”指 Unicorn/native simulator，用来执行真实 AArch64 指令路径，不是 Android GUI 模拟器。IDA 证明的是静态结构，Unicorn 用同一份 fixed SO 做第二条独立证据链，可以发现表项错误、地址换算错误、非法内存访问或未知外部调用。

确认阶段会把 dispatcher 输入逐项送入真实代码，要求 256/256 匹配、零 mismatch、零 invalid memory、零 unknown external calls，并绑定 SO、IDA 响应和 simulation 配置哈希。模拟器不能替代真机 dump，也不能把 fixture 的常量或 handler 语义带入当前 APK；它的作用是验证当前二进制的原生路径确实与导出的表一致。

### 5. 详细恢复为什么必须后置

方法级 DEX 恢复依赖前面的输入、SO、表和语义都已经闭合。只有 `method_records>0` 时，才对每个方法解析 opcode、引用和操作数宽度；每个方法都要满足引用索引合法、指令宽度连续覆盖、最终 PC 恰好等于 `insns_size`，并保持 code unit 数量、class_data 编码和 DEX 布局约束。

恢复不是简单把字节写回 DEX。还要生成覆盖全部预期方法的 repair manifest，重新计算 checksum/signature，并保留每个输入和输出哈希。任何未知 opcode、宽度歧义、引用越界、PC 无法闭合或 DEX 回写冲突都不能通过“补齐 padding”掩盖，应回到对应阶段补充证据。

### 6. 为什么必须独立运行 dexdump、JADX 和 Apktool

恢复代码不应自己给自己打分。独立验收会重新检查 DEX header、文件大小、SHA-1、Adler-32、map_list 和 manifest 覆盖，再运行 Android `dexdump` 与 Java-backed JADX。JADX 的退出码、错误数量和错误方法集合都要记录，不能只看 GUI 是否打开或是否出现首屏。

某6零免费版去特征和重打包同样依赖 Apktool：先解码当前 APK，依据当前 revision 的 inventory 精确处理 Manifest、smali、壳资产和 DEX 映射，再构建、zipalign 和签名。不能按文件名关键词批量删除，也不能复用其他版本的 Application、DEX 顺序、bridge 调用次数或签名结论。

### 7. BLOCKED 与阶段边界 resume

这个流程故意允许停下来。未知偏移、多个 dispatcher 候选、root/ABI 不匹配、工具缺失、哈希冲突或 adapter 证据不足时，保留原始产物和日志，写入结构化问题并进入 `BLOCKED`。补充信息后使用 `vmpwf resume` 在阶段边界重新加载配置，归档失效阶段，保留旧 revision 证据；不要手工修改 checkpoint、question 或 stage record。

### 8. 端到端证据链小结

\```
原始 APK/运行时 DEX
  -> 输入清单与 SHA-256
  -> Frida spawn-gating 运行时 SO/私有 linker 证据
  -> SoFixer fixed SO
  -> IDA Pro MCP dispatcher/handler JSON
  -> Unicorn 256 路径原生确认
  -> 有 method records 时的 DEX 方法恢复
  -> dexdump/JADX/Apktool/签名独立验收
  -> 当前版本可运行 APK（若设备验收也通过）
\```

每一箭头都应能在案件目录找到输入、输出、日志和哈希。只有整条链条闭合，才能把结论写成“当前样本已验证”；单独的 DEX dump、Frida 成功启动、IDA 表或 APK 可安装，都不等于完成还原。

## 四、关键原理

### 1. Spawn-gating 的时序

设备阶段使用 profile 固定的 `tools/frida/media-server`。框架先验证本地和设备端 SHA-256，再启用 spawn-gating、启动目标并在 `resume()` 前加载 agent。这样可以在目标应用自己的 Java/JNI 反调试初始化前获取证据，避免把 late attach 的结果误认为可靠取证。

手机重启后 root 服务端和 Frida 会话都会失效，必须重新部署和校验 `media-server`。对手工映射的私有代码区，默认只做只读采集；未经当前案件证据证明，不直接对任意地址做 inline hook。

### 2. 私有 linker 不是普通 so dump

接受的 SO 证据需要包含当前进程上下文、`loadStart`、`loadSize`、私有 `soinfo`（或等价动态表证据）、program headers 和解密后的动态表。简单复制外层 `libjiagu` 映射或 APK 里的 SO 资产，不能支撑后续 IDA 分析。

### 3. IDA 与 Unicorn 必须绑定同一份 SO

IDA Pro MCP 只分析当前案件 revision 的 exact fixed SO，并记录 SO 哈希、`image_base` 和运行时 `pointer_base`。导出的 dispatcher 表要求完整覆盖 `0..255`。随后 Unicorn 使用同一个 fixed SO 做 AArch64 原生确认，至少要求 256/256 匹配、零非法内存和零未知外部调用。

### 4. DEX 恢复有前置条件

框架先读取 LM/VMP inventory。只有 `method_records > 0` 才进入方法流恢复；每个方法都要满足引用合法、opcode 闭合、宽度覆盖完整、最终 PC 等于 `insns_size`，并保持 DEX code unit 和 class-data 编码约束。如果记录数为 0，流程仍可以验证 SO/dispatcher，但必须明确报告没有可恢复的 VMP 方法，不能伪造 `vmp_repaired=true`。

### 5. 重打包必须按版本独立取证

某6零去特征不是按文件名关键字批量删除。当前 APK 必须重新盘点壳资产、壳 DEX、Manifest、Stub/bridge 调用点、DEX 布局和签名，再生成绑定当前 revision 的 adapter。每个删除项、同路径替换、descriptor 替换和 smali 正则都要有精确文件名、命中数量、证据和输出哈希。

## 四、环境准备

学习研究环境至少需要：

- Windows PowerShell、Python 3、Git；
- Android SDK Platform-Tools 和 Build Tools；
- Java、JADX；
- Apktool（APK 解码、smali 检查和重建）；
- Frida 17.9.1 主机工具及仓库 profile 的 `media-server`；
- IDA Pro 与 IDA Pro MCP；
- SoFixer、Unicorn；
- 一台 ADB 在线、ARM64、具备 `su`/root 权限的真机。

可以先在仓库目录运行：

```powershell
py -3 .\vmpwf.py doctor
adb devices -l
adb shell su -c id
jadx --version
frida --version
\```

完整命令模板、Apktool/JADX/IDA Pro MCP 环境要求和每个阶段的输入输出见：
https://github.com/LeoChen-CoreMind/android-vmp-recovery-workflow/blob/main/docs/%E4%BD%BF%E7%94%A8%E6%96%B9%E6%B3%95.md

## 五、如何阅读结果

不要只看最终 APK 是否能安装。建议按以下顺序审阅：

- `artifacts.json`：输入和产物哈希是否闭合；
- `questions.json`：是否仍有 `BLOCKED` 问题；
- `ida/responses/` 与 `simulation/`：SO、表和配置哈希是否一致；
- `reports/`：dexdump、JADX、aapt2、zipalign、apksigner 的真实退出码；
- `repack/`：adapter 是否绑定当前 APK/revision，DEX 布局和 Manifest 是否符合证据；
- `logs/`：设备启动、spawn 事件、logcat、崩溃和超时原因。

fixture 只能证明框架编排和文件合同，不能当作当前 APK 的语义证据。不同 APK、不同某6零版本或不同运行时 revision 的 RVA、handler 含义、方法 key、调用次数和常量都不能直接复用。

## 六、总结

这套工作流的重点是把“逆向经验”变成可验证的证据链：

\```
当前输入 -> 当前 SO -> 当前 IDA 响应 -> 当前 Unicorn 报告 -> 当前 DEX/重打包结果
\```

只要链条中有一步无法由当前证据唯一确定，就保留原始产物并进入 `BLOCKED`，等待补充最小信息后从阶段边界恢复。对于学习研究来说，这比得到一个无法解释、无法复现的“一键结果”更有价值。

这套框架实测可以还原所有免费的程序，谢谢大家观看

---

# 回复

## 回复 by iBa0 (#2)

666

## 回复 by 阿捏利 (#3)

点赞要token是什么情况？

## 回复 by 末日大哥 (#4)

666

## 回复 by wx_coddvccwyh (#5)

666

## 回复 by mb_jhhtbaex (#6)

感谢分享

## 回复 by mb_elqwyvnm (#7)

666666

## 回复 by xianhuimin (#8)

看看

## 回复 by mb_rdqxdjmw (#9)

牛啊牛啊

## 回复 by mb_mddfhmcj (#10)

看看

## 回复 by Gryffindoss (#11)

55

## 回复 by 简单的简单 (#12)

666

## 回复 by guijingwen (#13)

66

## 回复 by ugvnui (#14)

666

## 回复 by Snark (#15)

1

## 回复 by mb_lizfxfno (#16)

666

## 回复 by 小黄鸭爱学习 (#17)

111

## 回复 by 小黄鸭爱学习 (#18)

说实话 我没看懂这篇文章，还原细节太少了。我看的云里雾里

## 回复 by 夜惜风雨 (#19)

66666666666666

## 回复 by mb_rqlksylg (#20)

666

## 回复 by mb_rqlksylg (#21)

666

## 回复 by hhwwyy (#22)

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by k4y0z (#23)

666

## 回复 by Midsw (#24)

9999999999999999

## 回复 by huangjw (#25)

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by Imxz (#26)

tql

## 回复 by lbunknow (#27)

666
