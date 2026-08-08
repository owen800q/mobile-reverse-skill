---
title: '[原创]某商业级加固 Native Loader 与 VMP 解释器逆向分析实战'
url: https://bbs.kanxue.com/thread-292331.htm
tid: 292331
author: kudos5566
date: '2026-08-06'
tags: [Android安全, 原创, 混淆加固, 逆向分析, 脱壳反混淆, HOOK注入, 系统相关, 其他]
crawled_at: '2026-08-08T10:01:21+00:00'
replies: 30
---

>
> 声明：本文仅用于安全技术研究与教学，所有分析均在隔离测试环境完成，不涉及任何真实业务数据。
>
>
>

## 摘要

这次把 **某商业级（com.mobile.demo_target）** 从加壳到加密算法完整啃了一遍。真机走 SysTrace 定制 ROM，用 unidbg 离线模拟，主要做了这几件事：

1. **环境与思路**：SysTrace 定制 ROM + unidbg 双路线，全程无 Frida
2. **加固识别**：某企业版加固（libDexHelper + libdexjni + libbangcle_risk/libsmkernel）识别
3. **反检测绕过**：定位 `0x79c` 异常、属性伪装、su 隐藏、名称规避
4. **DEX 脱壳**：sniffer → dex_dumper 演进，完整 dump 全部 payload DEX
5. **Native loader 逆向**：`libdexjni_target.so` 的 RC4 加密引擎 + 自定义 Dynamic Linker
6. **unidbg 动态脱壳**：突破 svc 63505 反模拟、JNIEnv 表修正、状态机绕过，完整解密 payload
7. **算法复现**：`cL(#239)` 触发 `KeyGenerator`，复现 AES-128 密钥生成
8. **VMP 语义级还原**：16-opcode 语义表 + W28 状态链符号化 + 自写模拟器复现 opcode 行为（注：模拟器未在真实 #238 指令流上跑通）
9. **加密链验证**：`#238 aesEncry` = AES/CBC/PKCS5Padding 全链路（Java 回环实证）
10. **反篡改对抗**：libDexHelper 四重检测面定位 + stealth_hook 完整对抗

**最终拿到**：可直接丢进 IDA 的干净脱壳文件 `payload_clean_full.so`（103 函数、9185 字符串）；加密链路全部跑通（#239 AES-128 key + #238 AES/CBC）；VMP 解释器 16 个 opcode 语义和 W28 状态链都还原了；libDexHelper 的反篡改也绕过了。

---

## 第 1 章 环境与总体思路

目标 App 具备多层反调试（`libantitrace.so` 反跟踪、内核级检测、`/proc/self/maps` 扫描），常规的 "root + frida" 方案会被直接检测。

**本项目全程排除 Frida**，真机侧使用 **SysTrace 定制 ROM**（AOSP 10 深度定制，内置 Dobby 注入、SandHook/Xposed 能力、ROM 打桩与 VMP 对抗工具），配合 **unidbg** 做离线模拟。两条路线各司其职：

| 环境 | 作用 |
|-|-|
| SysTrace 定制 ROM（真机） | 反检测对抗、真机 hook、DEX 内存 dump |
| unidbg（宿主机） | Native loader 模拟执行、全自动脱壳、算法复现 |

【整体环境与数据流示意】

\```
                        ┌─────────────────────────────────────────────┐
                        │  某商业级 App (com.mobile.demo_target)         │
                        │  某企业版(libDexHelper+libdexjni+bangcle_risk) │
                        └───────────────┬─────────────────────────────┘
                                        │ 反检测对抗（SysTrace 定制 ROM）
                        ┌───────────────▼─────────────────────────────┐
                        │ 真机 (AOSP10 定制 ROM)                       │
                        │  resetprop 属性伪装 → nsenter 隐藏 su         │
                        │  stealth_hook 改名 libanalytics 注入     │
                        │  GhostHWBP 内核断点 (hwbp_ghost.ko)          │
                        └───────────────┬─────────────────────────────┘
                                        │ /proc/pid/maps 匿名段 dump
                        ┌───────────────▼─────────────────────────────┐
                        │ DEX 脱壳: dex_dumper → fix_checksum     │
                        │   → payload_2_full_fixed.dex(2070类)          │
                        │   → payload_6_fixed.dex(198类 加密/HTTP)      │
                        └───────────────┬─────────────────────────────┘
                                        │ 关键 so: libdexjni_target.so
                        ┌───────────────▼─────────────────────────────┐
                        │ Native loader 逆向 (IDA)                      │
                        │  sub_13F8 主加载器 / sub_1184 RC4 / sub_CD0   │
                        │  key@0x2E1E00 → 解密 [0x4000,0x2E1E00)       │
                        └───────────────┬─────────────────────────────┘
                                        │ 离线模拟执行
                        ┌───────────────▼─────────────────────────────┐
                        │ unidbg: svc63505 + JNIEnv patch               │
                        │  → JNI_OnLoad → 10×RegisterNatives           │
                        │  → cL(#239) → AES-128 key                    │
                        │  → #238 AES/CBC 加密链 + VMP 全语义还原      │
                        │  → libDexHelper 反篡改完整对抗               │
                        └─────────────────────────────────────────────┘
\```

---

## 第 2 章 目标识别：加固矩阵

### 2.1 APK 结构

`lib/arm64-v8a/` 下 **60 个 .so**。按安全厂商分类：

| 加固/安全库 | 作用 |
|-|-|
| `libDexHelper.so` | **某企业版** 反篡改核心（扫描 maps + checksum） |
| `libdexjni_target.so` | **某企业版** 加密 loader（本文主角） |
| `libsmkernel.so` / `libbangcle_risk.so` / `libnllvm1623735669.so` | **某** 加固内核 / 风险检测 / LLVM 混淆（同属某体系） |
| `libantitrace.so` | **反跟踪**（ptrace 检测等） |
| `libtongdun.so` | 第三方风控 |
| `libHKESipCryptor.so` / `libSwipeLockCryptor.so` / `libSipCryptor.so` / `libcfcaMLog.so` | 某商业级专用加密/CFCA 国密 |

【demo_target_libs 库矩阵（关键 so）】

\```
demo_target_libs/                    （真机 dump + APK 提取）
├── libsmkernel.so         2,265,280  某加固内核
├── libnllvm1623735669.so  1,442,176  Bangcle LLVM 混淆引擎
├── libbangcle_risk.so       575,328  Bangcle 风险检测
└── arm/
    ├── libdexjni_target.so  2,677,789  ★ 某加密 loader（本文主角）
    ├── libDexHelper.so           627,610  ★ 某反篡改核心
    ├── libsmkernel.so          1,272,096  Bangcle
    ├── libnllvm1623735669.so     749,800  Bangcle
    ├── libbangcle_risk.so        448,100  Bangcle 风险检测
    ├── libantitrace.so            13,904  反跟踪（ptrace 检测）
    └── libDexHelper-x86.so     1,151,325  x86 版（模拟器用）

APK 内 lib/arm64-v8a/ 共 60 个 .so（demo_target_unzipped/lib/arm64-v8a/）
\```

**结论**：这是一个 **某企业版加固 + 多家 SDK 混合** 的典型某商业级 App——`libDexHelper.so`/`libdexjni_target.so`/`libbangcle_risk.so`/`libsmkernel.so` 均属同一套某加固体系（`com.secneo.apkwrapper` 即某企业版特征包名）。主加密逻辑在 `libdexjni_target.so`，`libDexHelper.so` 负责反篡改，`libtongdun.so` 等为独立第三方风控。

### 2.2 入口与包结构

- 包名：`com.mobile.demo_target`
- 主 Activity：`com.mobile.demo_target.ui.targetMainActivity`
- 壳入口：`com.secneo.apkwrapper.*`

---

## 第 3 章 反检测·用户态

### 3.1 问题定位：0x79c

首次注入 hook 后 App 异常退出。从 tombstone 分析：

```python
*** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
Build fingerprint: 'google/marlin/marlin:10/QP1A.190711.020'
pid: 4859, tid: 4859, name: .mobile.demo_target >>> com.mobile.demo_target <<<
signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x79c
Cause: null pointer dereference
\```

【tombstone 0x79c （logcat 实测）】

\```
19880 19880 F libc  : Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x79c in tid 19880
19930 19930 F DEBUG : *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
19930 19930 F DEBUG : pid: 19880, tid: 19880, name: .mobile.demo_target  >>> com.mobile.demo_target <<<
19930 19930 F DEBUG : signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x79c
19930 19930 F DEBUG : Cause: null pointer dereference
19930 19930 F DEBUG :     x0  0000000000000000  x1  00000000b6a2879d  x2  0000000000000fff  x3  00006f732e726f74
19930 19930 F DEBUG :     sp  0000000000000000  lr  0000000000000000  pc  000000000000079c
19930 19930 F DEBUG : backtrace:
19930 19930 F DEBUG :       #00 pc 000000000000079c  <unknown>
19930 19930 F DEBUG :       #01 pc 0000000000000000  <unknown>
\```

关键点：`sp/lr/pc` 全为 0 且 `pc=0x79c` —— 栈完全被清零后跳转到 0x79c，是典型的**扫描 maps 后主动自杀**（非随机崩溃）。

**问题根因**：

- `libDexHelper.so` 在后台线程（`WeexJSBridgeThr`）持续扫描 `/proc/self/maps`
- 发现注入的 `.so` 映射后，校验可执行段（如 libc.so），触发 **0x79c 空指针** 异常退出

>
> **区分两种检测**：① 环境检测（ro.debuggable=1、su 存在、USB 调试）触发的是 `Activity.finish()` **闪退**（进程仍在后台）；② 注入检测（maps 中发现未授权库）触发的是 **0x79c 空指针自杀**（进程直接崩溃）。本文 0x79c 属于后者。
>
>
>

**应对思路**：让注入的 so 在 maps 中"不可疑"。

### 3.2 反检测核心：setup_stealth 技术解析

对抗环境检测的核心工具是 **`setup_stealth`**。
它集成了 **5 类反检测技术**：

**① 属性物理覆写（绕过属性 API）**
加固壳会绕过 `__system_property_get` 直接 `mmap` 读取 `/dev/__properties__` 的**物理内存**（属性树），常规 `setprop` 无效。`setup_stealth` 反向利用这一点：

```c
// 1. 定位属性在属性树中的指针
const struct prop_info* pi = __system_property_find(name);
// 2. 扫 /proc/self/maps 找到属性所在文件（/dev/__properties__/u*）
// 3. mmap 映射该文件，按偏移找到 prop_info 结构
struct prop_info* target_pi = (struct prop_info*)((char*)map + offset);
// 4. 序列锁（seqlock）并发安全覆写：serial|1 → 写 value → 更新 serial
target_pi->serial = serial | 1;
__sync_synchronize();
strcpy(target_pi->value, new_val);
__sync_synchronize();
target_pi->serial = (new_len << 24) | ((old_counter + 2) & 0xfffffffe);
\```

关键点：**序列锁协议**（写前置 serial 奇数位、写后置偶数位 + 内存屏障），保证并发读属性时不撕裂。

**② Ghost Root 提权（setresuid 1337）**
`syscall(__NR_setresuid, 1337, 1337, 1337)` 触发定制内核 `kernel/sys.c` 的 setresuid hook，以 UID 1337 获得内核级能力，绕过 SELinux 对属性文件写入的限制。

**③ shadow 属性重定向**
`setresuid(1337,1337,1342)` 启用内核 `fs/namei.c` 的 **shadow 属性重定向**：把 `/dev/__properties__/xxx` 的读取重定向到 `/dev/__properties__/xxx.real`（`setup_stealth` 先备份原属性为 `.real`），实现"读真值、写假值"分离——壳读到的永远是伪装值，系统内部用真实值。

**④ 完整属性伪装集（20+ 个）**

```c
ro.debuggable=0  ro.secure=1  ro.build.tags=release-keys  ro.build.type=user
ro.build.fingerprint=google/marlin/marlin:10/QP1A.191005.007.A3/5972272:user/release-keys
ro.boot.verifiedbootstate=green  ro.boot.flash.locked=1
ro.boot.vbmeta.device_state=locked  ro.boot.veritymode=enforcing
sys.oem_unlock_allowed=0  init.svc.adbd=stopped  init.svc.magiskd=stopped
ro.secureboot.lockstate=locked  ro.boot.mac_address=40:4e:36:1f:e2:4e ...
\```

精确伪装成 Pixel 1 (marlin) Android 10 的出厂指纹，覆盖 root/调试/bootloader 全部检测面。

**⑤ Zygote 重启（清 Java 层属性缓存）**
`setprop ctl.restart zygote` 重启 Zygote，让 Java 层 `SystemProperties` 缓存重新读取伪装后的属性——否则 Java 与 Native 层属性不一致会被壳识破。

>
> **配套关系**：`setup_stealth` 是集成执行器；其属性覆写核心逻辑在 `resetprop_ult.c`（独立版单工具）中复用；`fake_build_prop.h` 定义内核态 `/proc/fake_build_prop` 的伪装内容（配合内核 namei.c 的 build.prop 重定向）。
>
>
>

**执行依赖**（设备侧）：`/data/local/tmp/setup_stealth`（属性伪装二进制）、`/data/local/tmp/send_cmd`（HWBP 控制）、内核侧 `hwbp_ghost.ko`（已加载）。

涉及文件：`setup_stealth.c`、`resetprop_ult.c`、`fake_build_prop.h`、`hide_root.c`

### 3.3 su 隐藏：nsenter + tmpfs

壳检测 `/system/xbin/su` 存在即自杀退出（`com.secneo.apkwrapper.H`）。

su 的隐藏用的是 `nsenter` 进 Zygote 挂载命名空间，拿空 `tmpfs` 盖住 `/system/xbin`，App 就看不到 su 了。

涉及文件：`setup_stealth.c`、`hide_root.c`

### 3.4 注入器与"双击启动"策略

注入靠 `ptrace_inject32.c` 做 ARM64 ptrace 注入。App 第一次启动基本都会因为内部逻辑/网络初始化**闪退**（`Bad file descriptor`），采用**双击启动策略**：

1. Ghost Root 调用 `hide_root`（不依赖 su）
2. 启动 App → 注入 `libanalytics.so` → 等 8 秒（等待首次初始化完成/异常退出）
3. 立即重启 App 并再次注入
4. App 进入稳定前台状态

【真机注入 + App 稳定运行（logcat 实测）】

\```
# 首次启动被 0x79c 杀掉（双击启动策略第 1 次）
F libc  : Fatal signal 11 (SIGSEGV) ... fault addr 0x79c
Zygote : Process 19841 exited cleanly (137)

# 第 2 次启动：注入 libanalytics.so 后 App 稳定
Zygote : Forked child process 20074
Zygote : Wrapped process has pid 20091
ActivityTaskManager: START u0 {act=android.intent.action.MAIN
ActivityTaskManager: Displayed com.mobile.demo_target/.ui.targetMainActivity: +641ms
\```

关键点：`Displayed targetMainActivity: +641ms` —— 改名 `libanalytics.so` 后 0x79c 不再触发，App 稳定进入主界面。

涉及文件：`ptrace_inject32.c`、`start_demo_target.sh`、`ghost_cold_sniper.c`

### 3.5 libDexHelper 反篡改完整对抗

`libDexHelper.so` 是某企业版反篡改核心（arm64 版 1MB、32 函数）。IDA 实证其与 `libdexjni_target.so` 是**同一壳框架**（相同 273/70/261/21 状态机混淆、相同 RC4 引擎、相同 libc 跳板表）：

\```
libDexHelper.so (arm64, 32 函数) 结构:
  sub_33F8 (0x1598)  主加载器: 读 /proc/self/maps 定位自身基址(qword_15048)
                     → mmap 自解密 → 自定义 linker 重定位 → init_array
  sub_3184 (0x274)   RC4 引擎: 256 S-box + 16B key(qword_15068) + PRGA
  sub_2xxx           libc 跳板: ADRP+LDR X17,[off_14F98~14FE0]→BR
                     （运行时解析 open/close/pread/mmap/read 填充）
\```

**四重检测面**（IDA 交叉确认）：

| # | 检测机制 | 证据 | 后果 |
|-|-|-|-|
| 1 | 环境检测 | ro.debuggable=1、su 存在、USB 调试（Bangbang/Secneo wrapper） | `finish()` 闪退 |
| 2 | maps 扫描 | WeexJSBridgeThr 线程例行扫 /proc/self/maps 找未授权库 | **0x79c** 空指针自杀 |
| 3 | 可执行段 checksum | 对 libc.so 等可执行映射做完整性校验 | 篡改即 0x79c |
| 4 | 第三方风控 SDK 检测 | 环境/注入检测 |  |

**对抗演进**：

\```
inline hook libc open/read + JNI 覆盖 SystemProperties → 改 libc 触发 checksum → 仍 0x79c
maps 自隐藏（过滤自身条目）
PIC 注入: 匿名 RWX mmap + RegisterNatives + dlclose 自卸载→ 0x79c 突破口（注入不占 maps 库条目）
修正 __system_property_get、页对齐指针
memfd_create("WEEX_IPC_SERVER") + MFD_CLOEXEC → RWX→ maps 显示 /memfd:WEEX_IPC_SERVER（伪装 Weex IPC，比 [anon:] 更隐蔽）
属性伪装补全（TingYun root）+ 无 stack protector + 源码清除 "stealth"/"hook" 字样（防 libDexHelper 内存字符串扫描, idx=8140）
改名 libanalytics.so + /data/data 路径 + 双击启动 → 最终落地
\```

**对抗原理**：

1. **属性伪装**（resetprop_ult / JNI RegisterNatives 覆盖 SystemProperties）——让 ro.debuggable/ro.build.tags 在 Java 与 Native 层一致，骗过环境检测；
2. **名称规避**——libDexHelper 按库名匹配可疑特征（stealth/hook 词），改名 `libanalytics.so` 后完全不可疑，`0x79c` 不再触发；
3. **匿名/memfd 执行**——注入代码不落地磁盘、不占 maps 库条目，checksum 只校验已映射可执行段（libc.so 等），匿名 RWX 不在校验列表；
4. **自卸载**（dlclose + unlink）——注入完成后原库卸载，maps 彻底消失。

**结论**：libDexHelper 的静态 patch 成本极高（多层状态机混淆 + 自校验 + 自解密），对抗重点在**运行时注入规避**而非修改其代码——通过"属性一致性 + 名称规避 + 匿名执行"组合拳完整绕过。

---

## 第 4 章 反检测·内核态

### 4.1 内核 HWBP 驱动

用户态反调试绕不过去，干脆搞了**内核硬件断点（HWBP）驱动**：

- `hwbp_ghost.c`：接管 ARM64 硬件 Debug 异常（LKM），编译产物 `hwbp_ghost.ko`
- `hwbp_resolver.c`：用户态守护进程，等待 App 启动、解析 `libart.so` 基址
- `hwbp_jni_tracer.c`：JNI 调用追踪

【内核模块加载日志（GhostHWBP，dmesg 实测）】

\```
[   78.053852] [GhostHWBP] Daemon Driver Loaded! Control via /proc/hwbp_cmd
[  132.655151] [GhostHWBP] SUCCESS! Arming PID 4203 at target_addr=0x71c94a1404
[  132.655210] [GhostHWBP] HWBP ARM SUCCESS on TID 4203
[  132.655232] [GhostHWBP] HWBP ARM SUCCESS on TID 4213
[  132.655255] [GhostHWBP] HWBP ARM SUCCESS on TID 4218
[  132.655277] [GhostHWBP] HWBP ARM SUCCESS on TID 4221
[  132.659346] [GhostHWBP] HWBP ARM SUCCESS on TID 5077
[  132.659389] [GhostHWBP] HWBP ARM SUCCESS on TID 5078
[  132.659433] [GhostHWBP] HWBP ARM SUCCESS on TID 5080
[  132.659522] [GhostHWBP] HWBP ARM SUCCESS on TID 5083
[  132.659751] [GhostHWBP] HWBP ARM SUCCESS on TID 5095
[  132.660180] [GhostHWBP] HWBP ARM SUCCESS on TID 5113
\```

关键点：驱动经 `/proc/hwbp_cmd` 控制，对 App 所有线程统一布防；`reg_offset=0x145404` 是 `libart.so` 中 **`RegisterNatives` 符号偏移**（由 `hwbp_resolver` 用 readelf 解析符号表得到）。

涉及文件：`hwbp_ghost.c`、`hwbp_resolver.c`、`hwbp_ghost.ko`

---

## 第 5 章 DEX 脱壳

### 5.1 内存 dump

某企业版壳把真实 DEX 解密后加载到**匿名内存**。脱壳 = 找到解密后的 DEX 段并 dump。核心思路是 **Zero-Break 读取**：不 attach、不 ptrace、不动调试寄存器，仅通过 `/proc/<PID>/mem` + `pread` 带外读取，避免触发壳的调试检测。

**关键技术（dex_dumper 演进）**：

\```
v1  扫 /proc/PID/maps 匿名段 → pread 读前 8 字节匹配 "dex\n035\0" magic
    → 从 DEX 头偏移 0x20 读 file_size，用其精确截断 dump 长度
    （不整段 dump：段常远大于 DEX，且可防读越界）
v2  三层策略（应对 Bangcle）:
    L1 Context-Pointer Scan — 利用 IDA 已知偏移: Bangcle_Dex_Decrypt_Engine_0x4BF4
       写解密 DEX 指针到 ctx[10]=ctx+0x50，扫 libDexHelper.so .data 段找该指针
    L2 /dev/ashmem + memfd 扫描 — Bangcle 常用 ashmem/memfd 匿名共享内存装 DEX
    L3 全可读段扫描 — 含 heap、odex 区，逐段匹配 magic
v3  IDA Context 提取 — 直接从 ctx[10] 或 DEX header 签名
    (header_size=0x70 + endian_tag=0x12345678) 定位，magic 被抹也能恢复
\```

**难点与关键点**：

1. **解密时机**：Bangcle DEX 解密需 **8~12 秒**（libDexHelper 加载后），必须在解密完成瞬间 dump，过早抓不到、过晚内存被复用。配套 `launch_and_dump.sh` 等待 libDexHelper 加载完成（`grep libDexHelper /proc/PID/maps`）+ 12s 后立即 dump。
2. **双击启动**：App 首次启动必然闪退（壳初始化检测），第二次启动才正常解密。`launch_and_dump.sh` 实现 LAUNCH#1（预期崩溃）→ 等 PID 重启 → LAUNCH#2（正常解密）→ 12s 后 dump。
3. **SELinux**：dump 前必须 `setenforce 0`，否则 `/proc/PID/mem` 读取被拒。
4. **magic 被抹**：Bangcle 可能抹掉 DEX magic 字节，v3 用 header 签名（`header_size=0x70` + `endian_tag=0x12345678`）识别并**恢复 magic**。
5. **多段**：DEX 可能分散在多个匿名段（含 ashmem/memfd），v2 三层策略确保全捕获，再合并。
6. **checksum/签名修复**：dump 出的 DEX 头部被壳篡改，`fix_dex_checksum_full.py` 重算后才能被 jadx 识别。修复偏移（DEX 头布局）：

```python
SHA-1 signature（20 字节）位于偏移 12，覆盖 data[32:]（即 0x20 起）计算
Adler32 checksum（4 字节）位于偏移 8，覆盖 data[12:] 计算
（顺序：先算 SHA-1 回写，再算 Adler32 回写）
\```

核心工具：

- `dex_dumper.c` / `dex_dumper_v2.c` / `dex_dumper_v3.c`：三层策略 + Context 提取（前述演进）
- `anon_dumper.c`：匿名段 dump
- `ghost_sniper_v2.c` / `sniper_dumper.c`：内核态 sniper dump（绕过用户态检测）
- `fix_dex_checksum_full.py`：修复 DEX checksum/签名（jadx 可识别的前提）
- `launch_and_dump.sh`：双击启动 + 12s 时机等待 + dump 一体化

【dumped_dex 产物（真机 dump + checksum 修复后）】

\```
dumped_dexes/                                 原始    修复后(checksum/signature)
├── payload_0.dex  / _fixed.dex          11,734,288
├── payload_1.dex  / _fixed.dex          12,149,888
├── payload_2.dex  / _fixed.dex          10,188,428
├── payload_2_full.dex / _full_fixed.dex 13,000,000  ★ 主业务
├── payload_3.dex  / _fixed.dex          11,773,024
├── payload_4.dex  / _fixed.dex           9,367,060
├── payload_5.dex  / _fixed.dex             461,176
└── payload_6.dex  / _fixed.dex           1,707,924  ★ 加密/HTTP 核心

payload_2_full_fixed.dex 头部（fix_dex_checksum_full.py 修复后，jadx 可识别）:
  magic     = dex\n035\0
  checksum  = 0x326a2e89
  signature = a11ab517cd848cc5...
  file_size = 13,000,000
  header    = 112 bytes
  endian    = 0x12345678 (little)
\```

反编译产出：`payload_2_full_fixed.dex` → **2070 类**（主业务）；`payload_6_fixed.dex` → **198 类**（加密/HTTP 核心）。

### 5.2 Java 层加密体系还原

完整还原了 App 的加密体系：

```python
请求明文 JSON
   │
   ├─► RSA 加密 AES Key（传给服务端）
   │
   └─► AES/CBC 或 AES/ECB/PKCS5 加密请求体
           │
           └─► Base64 编码 → respData 字段
响应: respData(AES) + mic(MAC) + respCode/respMessage
\```

>
> 注：`mic(MAC)` 消息认证码的生成/校验算法本次**未深入**——它属请求完整性保护，独立于 #239/#238 的加密链路。MAC 缺失不影响 AES 加解密的算法复现，但构造真实请求时需另行还原（常见 HMAC-SHA256，本文未覆盖）。
>
>
>

| 类 | 关键方法 | JNI ID |
|-|-|-|
| `AESUtil` | `generateAESKey()` | **#239** |
| `AESUtil` | `Encrypt/Decrypt/aesDncode/aesEncry` | #234/#232/#237/#238 |
| `EncryptUtil` | `Decrypts/EncryptUtil/Encrypts` | #243~#246 |
| `EncryptUtil` | `EncryptsGM`（国密） | #247 |
| `RsaUtil` | `RSA/ECB/PKCS1Padding` | 常量 |

>
> 注：RSA 用于加密 AES Key 传给服务端（非对称密钥交换）。本文未深入 RSA 公钥的来源与存放——若公钥硬编码在 Java 层则易被替换，若由 Native 白盒保护则更安全；此边界本次未评估。
>
>
>

`EncryptWithECB` 是里面**唯一纯 Java 不走 JNI** 的方法（`AES/ECB/PKCS5Padding`），可以直接 Hook；其余核心加密全在 JNI 派发里（#232~#247）。

服务端信息：

- 生产域名：`ts-mtarget.example.com:8009`、`h5.example.com`、`fpopen.example.com`
- 证书：CFCA SM2 国密 CA（Base64 DER 已还原）

---

## 第 6 章 Native Loader 逆向：libdexjni_target.so

### 6.1 ELF 结构

`libdexjni_target.so` 98% 内容为加密数据：

```python
Image size: 0x2F4150 (≈3MB)
  [rx]  0x0000   ~ 0x2CA0   — loader stub 代码（明文，仅 11KB）
  [rw]  0x12D08  ~ 0x13028  — .dynamic + GOT
  [bss] 0x13028  ~ 0x13090  — bss
  [rw]  0x13090  ~ 0x2F4150 — 【加密 payload，2.85MB】运行时解密
\```

### 6.2 三个关键函数

| 函数 | 作用 |
|-|-|
| `sub_13F8` | 主加载器（自定义 Dynamic Linker） |
| `sub_1184` | RC4 解密引擎 |
| `sub_CD0` | JNI_OnLoad 查找与调用 |

【sub_13F8 / sub_1184 / sub_CD0 关键逻辑（IDA 反编译摘要）】

```c
// ── sub_1184: RC4 解密引擎（每块 ≤0x40 字节） ──
__int64 __fastcall sub_1184(__int64 a1, int a2)   // a2 = 解密起点
{
  v2 = dword_13040;  v3 = dword_1307C;            // 全局解密范围 [0x4000, 0x2E1E00)
  ... 计算本块范围 v6/v7 ...
  // S-box 初始化 (KSA)
  do { v26[v9] = v9; ++v9; } while ( v9 != 256 );       // 0x12c0
  for ( j = (unsigned __int8)(qword_13068 + v26[0]); ... ) {
    *v12 = v26[j]; v26[j] = v11;
    v16 = *((_BYTE *)&qword_13068 + v13++);             // 16 字节 key 循环
    if ( v13 >= 16 ) v13 = 0;
  }
  // PRGA + XOR 写回
  do {
    v22 = *v21++;                                        // 0x1380
    v19 = (unsigned __int8)(v19 + 1);
    v23 = v26[v19];  v18 = (unsigned __int8)(v18 + v23);
    v26[v19] = v26[v18]; v26[v18] = v23;
    *(v21 - 1) = v26[(unsigned __int8)(v26[v19] + v23)] ^ v22;   // 0x13c4 解密写回
  } while ( v10 > ... );
}

// ── sub_13F8: 主加载器（自定义 Dynamic Linker）关键链 ──
sub_A70();                       // 0x14c4 init
sub_AE0();                       // 0x1644 open("/system/lib64/libdexjni...so")
sub_AC0();                       // 0x1668 pread(fd, &qword_13050, 0x14, off=0x2E1E00) 读 key
qword_13068 = qword_13050;       // 0x169c  ← 16 字节 RC4 key 写入全局
sub_AC0();                       // 0x16ac
sub_1184((__int64)v119, dword_13040);   // 0x16bc 首次 RC4 解密
v7 = sub_9E0();                  // 0x170c mmap 分配解密目标段
sub_B1C(v7, 0, v5);              // 0x1728
... 解析 DYNAMIC/重定位 GOT ...
sub_CD0(v97, v96, v101, v102, ...);     // 0x254c/0x256c JNI_OnLoad 查找并调用
v62(v47);                        // 0x1f08 调用 JNI_OnLoad
for ( i = 0; ... ) v49();        // 0x1f10 执行 init_array

// ── sub_CD0: JNI_OnLoad 查找器 ──
// 解析 DYNAMIC 段 strtab/symtab，用 sub_BF8 哈希查表:
v31 = *(_DWORD *)(v27 + 4LL * ((unsigned int)sub_BF8("JNI_OnLoad") % v26));  // 0x1104
... 遍历符号表验证后返回: return *(_QWORD *)(v32 + 8);  // 函数指针
\```

### 6.3 RC4 解密引擎（sub_1184）

标准 RC4（256 字节 S-box + 16 字节 key + PRGA XOR 写回），每次调用解密 ≤0x40 字节分块执行。关键参数：

- `dword_13040`：解密起点
- `dword_1307C`：解密终点
- `qword_13068`：16 字节 key（静态分析为全 0，位于 bss 区；**运行时由 pread 从文件偏移 0x2E1E00 写入**，见 6.4）

### 6.4 主加载器（sub_13F8）

调用链：

```python
open("/system/lib64/libdexjni_target.so")
  → pread key（文件偏移 0x2E1E00，20 字节）→ 写入 qword_13068
  → mmap 分段（seg0 代码 + seg1 数据）
  → 分块 RC4 解密
  → 自定义 linker 解析 DYNAMIC 表
  → 重定位 GOT
  → 调用 JNI_OnLoad
\```

RC4 key 是顺着 xrefs 追 `sub_AC0`（pread）的 offset 参数找到的，key 就在**文件偏移 0x2E1E00**：

```python
0x2E1E00: e0 67 0d d6 1a 2c 24 cc 92 b7 06 c2 fa 9f 2d 1c 34 00 00 00
          └──────────── 16 字节 RC4 key ────────────┘
\```

【0x2E1E00 处 key hexdump（原始 so 磁盘实测）】

\```
$ xxd -s 0x2E1E00 -l 32 libdexjni_target.so
2e1e60: e0 67 0d d6 1a 2c 24 cc 92 b7 06 c2 fa 9f 2d 1c  34 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
         └──────────── 16 字节 RC4 key ────────────┘
\```

`pread(fd, &qword_13050, 0x14, 0x2E1E00)` 读出的前 16 字节即 key，与 `qword_13068` 完全一致。

**key = `e0670dd6...`**

### 6.5 自定义 Dynamic Linker（sub_13F8 核心）

在 `sub_13F8` 中发现壳实现了独立的 ELF 重定位解析器：

- `DT_SYMTAB/DT_STRTAB`：重构内部符号表
- `DT_RELA/DT_RELASZ`：重定位 Native 内存
- `DT_INIT_ARRAY/DT_FINI_ARRAY`：执行初始化回调
- `DT_INIT`：触发算法模块初始化

解密产物：`libdexjni_decrypted_dump.so`（3.1MB，内存 dump 版）含 **80,708 个明文字符串** 与全套重定位数据；
与 7.7 的 `payload_clean_full.so`（9185 个 IDA 已识别字符串）是**不同文件**，统计口径不同。

---

## 第 7 章 unidbg 动态脱壳

### 7.1 遇到的问题：手动调用链不生效

最初尝试在 unidbg 中手动执行：

```java
module.callFunction(emulator, 0x13F8, vm.getJavaVM(), 0);   // 解密
module.callFunction(emulator, 0xCD0, module.base + 0x2f3000, module.base + 0x2f2000, ...);  // JNI 查找
\```

问题：`sub_CD0 运行后自动注册的 Natives 字典: {}`（空）、`FULL_HEAD_HEX` 全 0——**JNI_OnLoad 从未真正执行**。

**原因**：手动拆分调用链绕过了壳的完整流程。正确做法是让 sub_13F8 完整跑完，再触发 JNI_OnLoad。

### 7.2 关键问题：svc 63505（壳的反模拟检查）

运行 sub_13F8 时遇到未处理系统调用：

```python
svc number: 63505  (NR=222)
\```

这是壳的**自定义 mmap2 系统调用**（反模拟检查）。 测试代码中的 `SecneoUnpacker.java`，注册该 svc 即可让 sub_13F8 继续执行：

```java
svcMap.put(63505, new Arm64Svc() {
    @Override public long handle(Emulator<?> emulator) {
        long x5 = ctx.getXLong(5), x8 = ctx.getXLong(8);
        if (x8 == 222) {
            if (x5 > 0x10000000L || x5 < 0) return -1;  // 反模拟
            long mapped = emulator.getMemory().mmap2(...);
            return mapped;
        }
        return 0;
    }
});
\```

注册后 **sub_13F8 完整执行并返回**！mmap 分配出解密目标段。

【svc 63505 注册 + sub_13F8 执行日志（unidbg 实测）】

\```
>>> calling sub_13F8 ...
sys_mmap(start=0x0, length=4096,   prot=0x3, flags=0x2,  fd=3, offset=0x4000)   # 映射原始 so 页
sys_mmap(start=0x0, length=3026944, prot=0x3, flags=0x22, fd=-1, offset=0x0)     # 分配 3MB 解密目标
sys_mmap(start=0x12963000, length=531200, prot=0x3, flags=0x32, fd=0, offset=0x0)  # seg0 代码段(解密写入)
sys_mmap(start=0x129ea000, length=2467972, prot=0x3, flags=0x32, fd=0, offset=0x0) # seg1 数据段
====== dlopen called from ArmLD64: filename=liblog.so ... ======
>>> sub_13F8 returned
seg0: 0x12963000 seg1: 0x129ea000
\```

关键点：`sub_13F8` 内部经自定义 mmap2（svc 63505）分配 **seg0/seg1 两个 RWX 段**，解密产物写在这里（不是 module.base+0x13090）——这是此前静态 dump 基址错误的根因。

### 7.3 运行时基址动态定位

payload 每次运行 mmap 地址都是随机的（`0x12963000`/`0x12a47000` 这种），硬编码不行，只能从 memoryMap 里动态找：

```java
long seg0 = 0, seg1 = 0;
for (MemoryMap m : memory.getMemoryMap()) {
    if (m.base >= 0x12000000L && m.prot == 0x7) { seg0 = m.base; }              // RWX 代码
    else if (m.prot == 0x3 && m.size >= 0x250000) { seg1 = m.base; }            // RW 数据
}
\```

**"静态分析 dump"基址错误的根因**。

### 7.4 JNIEnv 表修正

payload 使用**定制 JNIEnv 布局**，与 unidbg 标准表不同：

| 问题 | 表现 | 修复 |
|-|-|-|
| `[0x30]` 入口检查 | payload 期望返回 0 的成功检查 | code hook 在 `0x2E00` 强制 W0=0 |
| `[0x480]` GetStaticFieldID | `SDK_INT` 查询失败 | 反射改 impl 表返回 23 |
| `[0x4B0]` GetStaticIntField | SDK 值获取失败 | 同上返回 23 |

```java
// 反射改 JNIEnv 表
Field f = vm.getClass().getDeclaredField("_JNIEnv");
UnidbgPointer ep = (UnidbgPointer) f.get(vm);
long implTable = ep.getLong(0);
UnidbgPointer.pointer(emulator, implTable).setLong(0x480, ret23);
UnidbgPointer.pointer(emulator, implTable).setLong(0x4B0, ret23b);
\```

【JNIEnv 表 patch 代码（DemotargetUnpack_final.java 实测）】

```java
// 反射改 JNIEnv 表: [0x480]=GetStaticFieldID → 恒返回 23 (SDK_INT)
Field jef = vm.getClass().getDeclaredField("_JNIEnv");
jef.setAccessible(true);
UnidbgPointer ep = (UnidbgPointer) jef.get(vm);
long implTable = ep.getLong(0);
UnidbgPointer ret23 = sm.registerSvc(new Arm64Svc() {
    @Override public long handle(Emulator<?> emulator) { return 23; }
});
UnidbgPointer.pointer(emulator, implTable).setLong(0x480, Pointer.nativeValue(ret23));
System.out.println("JNIEnv[0x480] -> return-23 (SDK_INT faked)");
// [0x4B0]=GetStaticIntField 同样返回 23

// code hook: 0x2E00 设 W0=0 (入口检查通过); 0x2E18 设 X0=JNIEnv
emulator.getBackend().hook_add_new(new CodeHook() {
    public void hook(Backend backend, long address, int size, Object user) {
        Arm64RegisterContext ctx = (Arm64RegisterContext) emulator.getContext();
        if (address == s0 + 0x2E00L) {
            ((EditableArm64RegisterContext) ctx).setXLong(0, 0);   // 入口检查通过
            System.out.println(">>> patched W0=0 at 0x2E00");
        } else if (address == s0 + 0x2E18L) {
            ((EditableArm64RegisterContext) ctx).setXLong(0, jeAddr); // 补 init 返回 JNIEnv
            System.out.println(">>> patched X0=JNIEnv at 0x2E18");
        }
    }
}, s0 + 0x2DE0L, s0 + 0x2E20L, null);
\```

配套：`svcMap.put(63505, ...)` 注册自定义 mmap2（见 7.2）、`0x101A8` 改分支跳主状态机、`0x90F8` canary NOP。

### 7.5 SDK 版本状态机绕过

payload 的 SDK 版本检查使用 ADRP 跳转表 dispatch，但 **ADRP 重定位缺失**（sub_13F8 只重定位 GOT 数据，没修 ADRP 页偏移），导致跳转表全 0 → BR 到错误地址。

状态机靠改两条指令绕过去：

```java
// 0x101A8: B.GE #0x1016C → B #0x8FD8（跳到主状态机）
UnidbgPointer.pointer(emulator, s0 + 0x101A8L).setInt(0, 0x14000000 | ...);
// 0x10168: B #0x10170 → B #0x101A8（跳过整个 switch）
UnidbgPointer.pointer(emulator, s0 + 0x10168L).setInt(0, ...);
// 0x90F8: CBNZ（canary 检查）→ NOP
UnidbgPointer.pointer(emulator, s0 + 0x90F8L).setInt(0, 0xD503201F);
\```

同时修复状态机跳转表基址（X23 = seg0 + 0x9120）。

### 7.6 RegisterNatives 全部触发

经过上述修正，JNI_OnLoad 完整执行，**10 个 JNI 方法全部注册**：

```python
HOOK RegisterNative: com/mobile/demo_target/JniLibtarget -> cL(...) @ RWX@0x12973690
HOOK RegisterNative: ... -> cV(...) @ RWX@0x129735e4
HOOK RegisterNative: ... -> cI(...) @ RWX@0x12973638
...（共 10 个）
\```

【RegisterNatives 全部注册日志（unidbg 实测）】

\```
JNIEnv->RegisterNatives(com/mobile/demo_target/JniLibtarget, RW@0x12c45480, 10) was called from RWX@0x1296c07c
RegisterNative(com/mobile/demo_target/JniLibtarget, cV([Ljava/lang/Object;)V, RWX@0x129735e4)
RegisterNative(com/mobile/demo_target/JniLibtarget, cI([Ljava/lang/Object;)I, RWX@0x12973638)
RegisterNative(com/mobile/demo_target/JniLibtarget, cL([Ljava/lang/Object;)Ljava/lang/Object;, RWX@0x12973690)
RegisterNative(com/mobile/demo_target/JniLibtarget, cS([Ljava/lang/Object;)S, RWX@0x129736e8)
RegisterNative(com/mobile/demo_target/JniLibtarget, cC([Ljava/lang/Object;)C, RWX@0x12973740)
RegisterNative(com/mobile/demo_target/JniLibtarget, cB([Ljava/lang/Object;)B, RWX@0x12973798)
RegisterNative(com/mobile/demo_target/JniLibtarget, cJ([Ljava/lang/Object;)J, RWX@0x129737f0)
RegisterNative(com/mobile/demo_target/JniLibtarget, cZ([Ljava/lang/Object;)Z, RWX@0x12973848)
RegisterNative(com/mobile/demo_target/JniLibtarget, cF([Ljava/lang/Object;)F, RWX@0x129738a0)
RegisterNative(com/mobile/demo_target/JniLibtarget, cD([Ljava/lang/Object;)D, RWX@0x129738f8)
>>> JNI_OnLoad returned
>>> nativesMap: {cB=..., cF=..., cS=..., cJ=..., cI=..., cV=..., cC=..., cD=..., cZ=..., cL=...}
\```

10 个方法全部注册成功，`cL` 入口在 **RWX@0x12973690**。

### 7.7 产出干净脱壳文件

`DemotargetDumpFull.java` 从正确基址连续 dump，产出 **`payload_clean_full.so`**：

```python
size: 0x2e2000
ELF magic: true
seg0: type=0x1 off=0x0 vaddr=0x0 fsz=0x81b00 msz=0x81b00   (RX 代码)
seg1: type=0x1 off=0x83d38 vaddr=0x87d38 fsz=0x259b4c      (RW 数据)
seg2: type=0x2  (PT_DYNAMIC)
\```

IDA 打开验证：**103 函数、9185 字符串、entry 0x2D80**，cL 函数体可反编译。

【payload_clean_full.so 全貌（IDA survey 实测）】

\```
模块    : payload_clean_full.so  (AArch64)
image   : 0x2e2818  (≈2.9MB)
MD5     : 246affafe5c033d716f54a532f88fcde

统计    : 103 函数 / 9185 字符串 / 2 段
[LOAD]  rx  0x000000 ~ 0x081B00   531KB  代码
[LOAD]  rw  0x087D38 ~ 0x2E2818   2.4MB  数据
entry   : 0x2D80  (start)

ELF program headers (dump 验证):
seg0: type=PT_LOAD off=0x0     vaddr=0x0     fsz=0x81b00  (RX)
seg1: type=PT_LOAD off=0x83d38 vaddr=0x87d38 fsz=0x259b4c (RW)
seg2: type=PT_DYNAMIC
\```

IDA 中 `cL` 函数体可正常反编译（103 个已识别函数之一），证明脱壳彻底、无残留加密。

---

## 第 8 章 算法复现与 VMP 分析

### 8.1 cL(#239) 调用

注册成功后，构造 Object[] 参数调用 `cL`：

```java
DvmObject<?>[] args = new DvmObject[5];
args[0] = vm.resolveClass("com/mobile/demo_target/encrypt/AESUtil").newObject(null); // class
args[1] = null; args[2] = null; args[3] = null;
args[4] = DvmInteger.valueOf(vm, 239);   // generateAESKey 的 method ID
ArrayObject arrayObj = new ArrayObject(args);
DvmObject<?> ret = jniLib.callStaticJniMethodObject(emulator,
    "cL([Ljava/lang/Object;)Ljava/lang/Object;", arrayObj);
\```

### 8.2 动态 JNI 日志实证算法

【cL(#239) 执行 JNI 日志（unidbg 实测关键行）】

\```
>>> calling cL(#239 generateAESKey) ...
Find native function Java_com_mobile_demo_target_JniLibtarget_cL => RWX@0x12973690
JNIEnv->GetArrayLength([AESUtil@..., null, null, null, Integer@...] => 5)
JNIEnv->GetObjectArrayElement(..., 4) => Integer@...          ← methodID=239 取出
JNIEnv->CallIntMethodV(Integer, intValue() => 0xef)
JNIEnv->NewObjectV(String, <init>([B@0x414553) => "AES")     ← 构造算法名
JNIEnv->CallObjectMethodV("AES", intern() => "AES")
JNIEnv->GetStaticMethodID(KeyGenerator.getInstance(String)KeyGenerator)
JNIEnv->CallStaticObjectMethodV(KeyGenerator, getInstance("AES") => KeyGenerator@...)
JNIEnv->CallVoidMethodV(KeyGenerator, init(0x80))            ← 128 位
JNIEnv->CallObjectMethodV(KeyGenerator, generateKey() => SecretKey@...)
JNIEnv->CallObjectMethodV(SecretKey, getEncoded() => [B@0x030a11181f262d343b424950575e656c)
>>> AES key: 030a11181f262d343b424950575e656c
\```

完整链：`239 → KeyGenerator.getInstance("AES") + init(128) + generateKey().getEncoded()`，即 **AES-128**。

unidbg 完整记录了 cL 内部执行序列：

```python
GetArrayLength(Object[5]) → 5
GetObjectArrayElement(,4) → Integer(0xEF=239)      ← methodID 取出
CallIntMethodV(Integer.intValue()) → 0xEF
NewObjectV(String <init>([B@0x414553)) → "AES"      ← 构造算法名
CallObjectMethodV("AES", intern()) → "AES"
GetStaticMethodID(KeyGenerator.getInstance(String)KeyGenerator)
CallStaticObjectMethodV → KeyGenerator.getInstance("AES")
CallVoidMethodV → KeyGenerator.init(0x80)           ← 128 位
CallObjectMethodV → KeyGenerator.generateKey() → SecretKey
CallObjectMethodV → SecretKey.getEncoded() → byte[16]
\```

**结论：generateAESKey(#239) = 标准 `KeyGenerator.getInstance("AES") + init(128) + generateKey().getEncoded()`**，即 AES-128 随机密钥。

运行结果：

```python
>>> AES key: 030a11181f262d343b424950575e656c   （unidbg mock 固定值）
\```

>
> 注：真实环境为 `SecureRandom` 随机值。unidbg 中通过 AbstractJni mock 了 `KeyGenerator`/`String.intern`/`Proxy.isProxyClass` 等 unidbg 不支持的方法。
>
>
>

### 8.3 VMP 解释器分析（loc_10950）

cL 函数体调用 `loc_10950`——一个 **VMP 数据混淆型字节码解释器**：

```python
主循环 0x109D4~0x109E8:
  UBFX X9, X8        ; 取 opcode
  LDRSW X8, [X27, X9, LSL#2]  ; 跳转表查表（X27 = 0x112B8）
  BR X8              ; 分发
\```

- **虚拟内存 X25**：栈上缓冲区（初始内容 = 0x7D492 处加密数据流）
- **状态寄存器 W28**：初始 0xE568AAEC，每 opcode 后更新
- **16 个 opcode**：统一模式 `byte[X25+addr] ^= key`，addr/key 由 W28 混淆算术派生

【VMP 16-opcode 跳转表反汇编（payload_clean_full.so @0x10950）】

```python
; VM 入口序言：压寄存器、建栈
10950: STP  X28, X27, [SP,#-0x60]!
10968: ADD  X29, SP, #0x50
1096c: SUB  SP, SP, #0x2A0
10984: ADRL X9, xmmword_7D492          ; 加密数据流(虚拟内存初始内容)
10994: MOV  W28, #0xE568AAEC           ; 状态寄存器 W28 初始值
1099c: ADRL X27, jpt_109E8             ; 主跳转表基址
109c0: STUR Q0, [X25,#0x1C]            ; 加载虚拟内存
109cc: B    def_109E8                  ; 进入解释循环

; 主循环 0x109D4~0x109E8（switch 16 cases）
109d0: MOV  W8, #0xF                   ; case 1
109d4: UBFX X9, X8, #0, #0x20          ; 取 opcode
109d8: CMP  W8, #0xF                   ; switch 16 cases
109dc: B.HI def_109E8                  ; >15 → default
109e0: LDRSW X8, [X27,X9,LSL#2]        ; 跳转表查表
109e4: ADD  X8, X8, X27                ; 相对偏移 → 绝对地址
109e8: BR   X8                         ; 分发
\```

关键点：16 个 opcode 统一模式 `byte[X25+addr] ^= key`，addr/key 由 W28 混淆算术派生——VMP 保护的是 **cL 参数解析与 methodID 分发**（Instruction Stealing），非 AES 算法本身。

**关键结论**：VMP 保护的是 **cL 的参数解析与 methodID 分发**（Instruction Stealing 型），**非 AES 算法本身**。算法 = 标准 KeyGenerator。

**16 opcode 语义表**（IDA 实测反汇编归纳）：

| opcode | 地址 | 操作模式 | next | 含svc |
|-|-|-|-|-|
| 0 | 0x109EC | 纯状态更新（无 X25 读写） | 0xC | 否 |
| 1 | 0x109D0 | 1 次 X25 字节 XOR | 0xC | 否 |
| 2 | 0x10A30 | 7 次 X25 字节 XOR | 0xD | 否 |
| 3 | 0x10AC8 | 4 次 X25 字节 XOR | 0xB | 否 |
| 4 | 0x10B44 | 3 次 X25 字节 XOR | 重分发 | 否 |
| 5 | 0x10BAC | 条件分支（W28 更新） | 1 | 否 |
| 6 | 0x10C0C | 纯状态更新 | 1 | 否 |
| 7 | 0x10C2C | 4 次 XOR + **svc 外部调用** | 6 | **是** |
| 8 | 0x10CE0 | 5 次 X25 字节 XOR | 0x95? | 否 |
| 9 | 0x10D90 | 操作 X29 栈区（寄存器文件） | ? | 否 |
| 10 | 0x10DC8 | **JNI 方法调用指令**（160 条，见下） | 9 | 否 |
| 11 | 0x11048 | 5 次 X25 字节 XOR | 0xE | 否 |
| 12 | 0x110E8 | X25 字节 XOR | 7 | 否 |
| 13 | 0x1116C | 3 次 XOR | 3 | 否 |
| 14 | 0x111D0 | 6 次 X25 字节 XOR（addr/key 均为 W28 仿射函数） | 8 | 否 |
| 15 | 0x1127C | **结束指令**：哨兵校验 → 弹栈 RET（失败走 sub_2C80） | — | 否 |

**W28 状态链符号化（4 类更新原语）**：`ADD/SUB`（仿射，op2/3/7/11/12/14）、`EOR`（仿射，op5/6/7/12）、`LSL/AND`（位混淆，op4/8/6）、`MUL/MADD`（非线性，op0/4/13）。addr/key 均 = `f(W28,W19,const)`。

**opcode 10 详解**（全解释器核心，JNI 方法调用指令）：

\```
入口: X21 = X0（JNIEnv/对象）, [SP,#0x18] = X1（参数数组）
10dc8: LDR X8, [X21]              ; JNIEnv
10dcc: LDR X8, [X8,#0x558]        ; → CallStaticObjectMethodV 槽位
10ddc: BLR X8                     ; 第一次 JNI 调用
10de0: LDR X8, [X21]; LDR X8,[X8,#0x568]  ; → CallObjectMethod 槽位
10de8: SUB W23, W0, #1            ; W23 = 返回值-1 = 方法索引
10df8: BLR X8                     ; 第二次 JNI 调用
10e10: BL sub_11328               ; JNI 调用包装（压栈+哨兵校验+间接调用）
10e14: BL loc_12BD4               ; methodID 解析: LDR X0, [qword_2E2580 表, W0*8]
10e18: MOV X24, X0                ; 解析结果 → X24（VM 寄存器文件基址）
10e20: B def_10E64                ; 进入内嵌二级分发器

内嵌二级 switch 0x10E64（12 case，W19 混淆算术算跳转目标）:
  case 0: W22=0, 读 X24+0x1C 存 [SP,#0x58]（布尔标志）
  case 1: W19 混淆 (MUL 0xEBBE, LSR 0x17, MADD 0x8B) → 布尔
  case 2: 经 JNIEnv[0x568] 再调一次, STR X0,[SP+0x60+W22*8]（存返回对象）
  case 3/4/6/7/8: W19 混淆算术 (MUL 0xBA2F/0xC438/0x9920 + LSR + MADD) → 索引/条件
  case 5/9: 从 X24 拷 8 字到 VM 寄存器文件 [SP,#0x30~0x4C]（返回类型匹配）
  case 10: CMP W22,W23 条件选择
\```

**语义**：opcode 10 = `methodID 查表(qword_2E2580) → JNIEnv 槽位调用 → 按返回类型(12 case)写 VM 寄存器文件`。cL(#239) 的 `KeyGenerator.getInstance("AES")` 等 JNI 调用完成。

### 8.4 #238 aesEncry 加密链验证（AES/CBC 全链路）

`AESUtil.aesEncry(byte[] bArr, String str, String str2)` 经 `JniLibtarget.cL(AESUtil.class, bArr, str, str2, 238)` 进入 Native。算法链已由四路证据交叉锁定：

\```
① payload 字符串（解密产物 payload_clean_full.so 实测）:
   0x129df4  "AES/CBC/PKCS5P"        ← 唯一 AES/ 算法串（无多分支）
   0x1230ae  "CIPHER_ALGORITHM"
   0x120339  "...o/Cipher"           ← javax/crypto/Cipher 类名

② unidbg JCA 调用日志（cL(#238) 动态）:
   FindClass(javax/crypto/spec/SecretKeySpec)
   → AllocObject → GetMethodID(SecretKeySpec.<init>([B, String))   ← 构造 key spec
   → （预期: Cipher.getInstance("AES/CBC/PKCS5Padding") + init + doFinal）
   （注: unidbg 在 opcode 10 大 case 执行时崩于模拟缺陷, 未到 doFinal。
   具体根因: opcode 10 入口要求 X21=JNIEnv、[SP,#0x18]=参数数组，
   但 unidbg 中执行到此处时 X21=0xe4ffefc9、SP=0xe4fff700 均为野指针——主解释器→opcode 10
   的寄存器/栈上下文传递在 unidbg 中失效，属壳多层状态保护的模拟缺陷，非 VMP 语义分析错误。
   推测: X21/SP 与 unidbg 的 JNIEnv 真实地址(0xfffe1640)同属 3.8GB 以上高位地址区，
   疑似壳在 opcode 9→10 的寄存器保存/恢复中发生了指针错位(高位指针被低 32 位截断/损坏)，
   而非 longjmp/异常处理切栈——解密后的 payload 中未发现 setjmp/longjmp/signal 特征。
   因此 VMP 模拟器只复现了 opcode 行为自洽性，并未真正驱动 #238 的 Native 指令流——
   #238 算法链由 ①静态字符串 ③参数映射 ④Java 回环交叉确认，不是模拟器跑通所得）

③ 参数映射（Java 签名 + CBC 约束）:
   bArr = 明文   str = key(16B hex)   str2 = IV(16B)

④ Java 标准库等价复现（AES/CBC/PKCS5Padding）:
   key=030a11181f262d343b424950575e656c, iv=1234567890abcdef
   "hello-238" → hex 3dd62fbbad0bbac61ffb16ae972accf0 / b64 PdYvu60LusYf+xaulyrM8A==
   加解密回环 6 组明文全 PASS（含 52B JSON）
\```

**结论**：`aesEncry(#238) = Cipher.getInstance("AES/CBC/PKCS5Padding") + SecretKeySpec(key) + IvParameterSpec(str2) + doFinal(明文)`，返回 Base64。与 `#237 aesDncode` 构成加解密配对；`#239 generateAESKey` 提供 16 字节 key。

---

## 第 9 章 总结

### 9.1 总览

| 层级 | 成果 |
|-|-|
| 环境 | SysTrace 定制 ROM + unidbg 模拟双环境 |
| 反检测 | `0x79c` 根因定位（libDexHelper maps 扫描+checksum）+ 完整对抗（属性伪装/名称规避/匿名 memfd 注入，v2→v13） |
| DEX 脱壳 | payload_2_full_fixed.dex + payload_6_fixed.dex（jadx 可分析） |
| Native 脱壳 | `payload_clean_full.so`（103 函数，IDA 可独立分析） |
| 算法复现 | #239 KeyGenerator AES-128 key + #238 aesEncry AES/CBC/PKCS5Padding 全链路（Java 回环实证） |
| VMP | 16-opcode 语义级还原（语义表 + W28 状态链 + 自写模拟器复现 opcode 行为） |
| 最后 | 未跑通真实 #238 指令流。 |

---

---

# 回复

## 回复 by mb_jnmxfjku (#2)

666

## 回复 by cpannn (#3)

xuexiba

## 回复 by didiid (#4)

666

## 回复 by TimeQvQ (#5)

666

## 回复 by tonykros (#6)

6666

## 回复 by mb_ykavguun (#7)

1

## 回复 by mb_gjhmacqd (#8)

666

## 回复 by mb_jhohnbzu (#9)

666

## 回复 by 天道happy (#10)

666666

## 回复 by mb_iemtkmio (#11)

666

## 回复 by guijingwen (#12)

66

## 回复 by mb_xjdhrmck (#13)

wqeqweq

## 回复 by 阿三 (#14)

666

## 回复 by xianhuimin (#15)

看看看

## 回复 by xingbing (#16)

学习

## 回复 by bluegatar (#17)

上rom![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_kbkqyusp (#18)

6666

## 回复 by 4ak5ra (#19)

强强强

## 回复 by mb_rztmbvgb (#20)

666

## 回复 by Thehepta (#21)

1

## 回复 by wx_插曲 (#22)

666

## 回复 by 小黄鸭爱学习 (#23)

111

## 回复 by 啊你好哇123 (#24)

学习信息

## 回复 by mb_ldbucrik (#25)

感谢分享

## 回复 by mb_ldbucrik (#26)

感谢分享

## 回复 by mb_ldbucrik (#27)

感谢分享

## 回复 by 正己 (#28)

感谢分享

## 回复 by wx_Huber Barrientos (#29)

666

## 回复 by mb_uulqeyon (#30)

1

## 回复 by GEKEZYX (#31)

666
