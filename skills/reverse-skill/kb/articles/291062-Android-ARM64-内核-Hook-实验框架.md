---
title: '[原创]Android ARM64 内核 Hook 实验框架'
url: https://bbs.kanxue.com/thread-291062.htm
tid: 291062
author: mb_nkjfyhkg
date: '2026-04-30'
tags: [Android安全, 原创]
crawled_at: '2026-08-08T10:09:39+00:00'
replies: 51
---

# KernelHook - Android ARM64 内核 Hook 实验框架

## 项目概述

KernelHook 是一个面向 Android ARM64/GKI 内核的可加载内核模块（LKM）Hook 框架，源自B佬的KernelPatch 项目。该框架提供了完整的内核函数拦截与修改能力，支持多种 Hook 模式，可用于内核研究、安全分析、系统定制等场景。

>
> 接触到kpm不久后就移植了kp的hook和kpm加载框架，中途一直有涂涂改改，但没上什么应用场景测试，索性就开源，欢迎佬们进行应用测试，最终反哺回kp。当前代码框架基本与kp一致，底层稍微动了一下，但不影响kpm的转换
>
>
>

### 核心特性

- **Inline Hook**：直接修改目标函数入口指令，实现函数拦截
- **Inline Wrap**：支持在函数调用前后插入多个回调，形成链式拦截
- **Function Pointer Hook**：修改函数指针表（如 syscall table、ops 结构）
- **Function Pointer Wrap**：函数指针的链式包装与回调
- **ARM64 指令重定位**：自动处理 PC-relative 指令的重定位
- **KCFI 绕过**：兼容高版本内核的 CFI 安全机制
- **热补丁支持**：使用 fixmap + stop_machine 实现安全的代码修补

---

## 项目结构

```python
arm64_kernel_hook/
├── lkm.c                    # 模块入口、自测逻辑、vfs_open demo
├── hook.h                   # 对外 API 头文件
├── hook_types.h             # 核心数据类型定义
│
├── hook_chain.c             # Inline hook / wrap 实现
├── fp_hook.c                # 函数指针 hook / wrap 实现
├── hook_reloc.c             # ARM64 指令重定位
├── hook_chain_ops.h         # Hook 链槽位管理
│
├── hotpatch.c               # Text/data patch 后端
├── hmem.c                   # Hook 内存池管理
├── pgtable.c                # 页表操作与权限修改
├── cache.h                  # Cache/TLB flush 辅助
│
├── secpass.c                # KCFI 绕过实现
├── kallsyms_name.c          # 内核符号解析
├── syscall.c                # Syscall hook 封装
│
├── log.h                    # 日志输出宏
├── hook_utils.h             # 工具函数
│
├── hook_runtime.h           # 运行时定义
├── hook_transit_ops.h       # 跳转操作
│
└── loader/                  # Rust 编写的设备端加载器
    ├── src/main.rs
    ├── Cargo.toml
    └── .cargo/config.toml
\```

---

## 核心模块详解

### 1. Hook 类型

#### Inline Hook (`hook_chain.c`)

Inline Hook 通过直接修改目标函数入口的指令来实现拦截：

```python
原始函数入口:     备份并重定位的 trampoline:
  LDR X17, #8        ->  [原始指令1] NOP
  RET X17            ->  [原始指令2] NOP
                     ->  JUMP BACK
\```

**工作流程：**

1. 备份目标函数入口前 4-5 条指令
2. 生成跳转指令写入函数入口，跳转到替换函数
3. 将备份指令搬迁到可执行内存区域并重定位
4. 卸载时恢复原始指令

#### Inline Wrap (`hook_wrap`)

Wrap 模式允许在原函数执行前后插入多个回调：

```c
hook_wrap(func, argno, before, after, udata);
\```

**执行顺序：**

```python
before A
  before B
    origin_func()  // 原始函数
  after B
after A
\```

- `before` 回调可以修改参数（`fargs->arg0` 等）
- `after` 回调可以修改返回值（`fargs->ret`）
- 设置 `skip_origin = 1` 可跳过原函数

#### Function Pointer Hook (`fp_hook.c`)

针对函数指针表的 Hook，适用于：

- Syscall Table（`sys_call_table[nr]`）
- VFS operations（`file_operations`、`inode_operations`）
- 其他函数指针数组

```c
// 直接替换
fp_hook(fp_addr, replace_func, &backup);

// 包装模式
fp_hook_wrap(fp_addr, argno, before, after, udata);
\```

#### 回调函数签名

框架自动生成支持 0-12 个参数的回调类型：

```c
typedef void (*hook_chainN_callback)(hook_fargsN_t *fargs, void *udata);

// 使用示例
hook_wrap2(func, my_before, my_after, NULL);  // 2 参数
fp_hook_wrap4(fp_addr, before, after, udata);  // 4 参数
\```

---

### 2. 指令重定位 (`hook_reloc.c`)

Inline Hook 覆盖目标函数入口后，需要确保原函数能继续正确执行。ARM64 大量使用 PC-relative 指令，必须重写这些指令的目标地址。

**支持的指令类型：**

| 指令类型 | 说明 | 重定位长度 |
|-|-|-|
| `B`, `BL` | 相对跳转 | 6-8 条 |
| `B.cond` | 条件分支 | 8 条 |
| `ADR`, `ADRP` | 地址加载 | 4 条 |
| `LDR literal` | 常量池加载 | 6 条 |
| `CBZ/CBNZ` | 条件比较跳转 | 6 条 |
| `TBZ/TBNZ` | 位测试跳转 | 6 条 |
| 其他 | 原样复制 | 2 条 |

**重定位策略：**

1. 解码指令，提取目标地址
2. 如果目标在 trampoline 区域，映射到重定位后的新地址
3. 生成等价的绝对跳转序列

---

### 3. 内存管理 (`hmem.c`)

模块加载时分配一段可执行内存区域用于存储 Hook 元数据和 trampoline 代码：

```c
// 模块初始化
text = hook_alloc(PAGE_SIZE * 10);  // 分配 40KB
hook_mem_add((uint64_t)text, size); // 注册到分配器
\```

**内存布局：**

- 将分配区域划分为多个 `hook_mem_warp_t` 槽位
- 每个槽位可存储 `hook_t`、`hook_chain_t` 或 `fp_hook_chain_t`
- 使用位图快速查找空闲槽位
- 支持引用计数，防止提前释放

**生命周期管理：**

- `hook_mem_zalloc()`: 分配 Hook 内存
- `hook_mem_get()`: 增加引用计数
- `hook_mem_put()`: 减少引用计数
- `hook_mem_retire()`: 标记为已释放但不复用（防止野指针）

---

### 4. 热补丁 (`hotpatch.c`)

安全的代码修补后端，支持两种路径：

#### Hotpatch 路径（优先）

```c
stop_machine()  // 停止所有在线 CPU
  ↓
fixmap 映射目标页  // 临时映射物理页
  ↓
copy_to_kernel_nofault()写入  // 内核写入
  ↓
caches_clean_inval_pou()  // 按范围同步 I-cache
  ↓
其他 CPU isb()完成  // 同步完成
\```

#### Fallback 路径

- 临时修改页表权限为可写
- 直接内存写入
- flush I-cache
- 恢复页表权限

---

### 5. KCFI 绕过 (`secpass.c`)

高版本 Android 内核启用 KCFI（Kernel Control Flow Integrity）后，间接调用会检查函数类型。本框架通过 Hook CFI 检查函数来实现绕过：

```c
// 绑定的符号
report_cfi_failure
__cfi_slowpath_diag
__cfi_slowpath
__cfi_check
__cfi_check_fail
\```

**绕过逻辑：**

- 检查目标地址是否在本模块 Hook 内存范围内
- 如果是，直接返回/忽略，允许执行
- 模块卸载时恢复所有修改

---

### 6. Syscall Hook 封装 (`syscall.c`)

提供了对系统调用的便捷 Hook 支持：

```c
syscall_init();  // 初始化，解析 syscall table

// 自动选择最佳路径
hook_syscalln(nr, narg, before, after, udata);
unhook_syscalln(nr, before, after);
\```

**封装策略：**

- 如果能获取 `sys_call_table`，使用函数指针 hook
- 否则通过符号名解析，使用 inline hook
- 自动检测是否使用 syscall wrapper

---

## 设备端加载器 (`loader/`)

Rust 编写的模块加载器，简化设备端部署：

**功能：**

1. 解析 `.ko` ELF 文件
2. 从 `/proc/kallsyms` 补全未定义符号
3. 调用 `init_module` syscall 加载模块
4. 失败时抓取相关 `dmesg` 日志

**快速使用：**

```bash
# 一键 adb 部署
cargo run -- --adb-run \
  --device-loader target/aarch64-linux-android/release/hook-loader \
  --name hook_module \
  ../hook_module.ko \
  enable_selftests=0 enable_vfs_demo=1
\```

---

## 模块参数

| 参数 | 默认值 | 说明 |
|-|-|-|
| `enable_selftests` | `0` | 运行时执行本地自测 |
| `enable_inline_selftests` | `0` | 执行 inline hook/wrap 自测 |
| `enable_fp_selftests` | `0` | 执行函数指针 hook/wrap 自测 |
| `enable_syscall_selftests` | `0` | 执行 syscall hook 自测 |
| `enable_vfs_demo` | `1` | 安装 vfs_open demo hook |

**推荐测试组合：**

```bash
# 仅验证 fp hook
enable_selftests=1 enable_inline_selftests=0 enable_fp_selftests=1 enable_syscall_selftests=0 enable_vfs_demo=0

# 验证全部自测
enable_selftests=1 enable_inline_selftests=1 enable_fp_selftests=1 enable_syscall_selftests=1 enable_vfs_demo=0

# 验证真实 vfs hook
enable_selftests=0 enable_inline_selftests=0 enable_fp_selftests=0 enable_syscall_selftests=0 enable_vfs_demo=1
\```

---

## 构建指南

### 内核模块

```bash
推荐使用ddk进行构建，ci中也构建好了demo，可在action下载测试
\```

### Rust Loader

```bash
cd loader

# 检查编译
cargo check

# 构建 Android ARM64 版本
cargo build --target aarch64-linux-android --release
\```

---

## API 速查

### Inline Hook

```c
// 安装 Hook
hook_err_t hook(void *func, void *replace, void **backup);

// 卸载 Hook
void unhook(void *func);

// 安装 Wrap
hook_err_t hook_wrap(void *func, int32_t argno, void *before, void *after, void *udata);

// 卸载 Wrap
void hook_unwrap(void *func, void *before, void *after);

// 类型化辅助（0-12 参数）
hook_wrap0() ~ hook_wrap12()
\```

### Function Pointer Hook

```c
// 安装 Hook
int fp_hook(uintptr_t fp_addr, void *replace, void **backup);

// 卸载 Hook
int fp_unhook(uintptr_t fp_addr, void *backup);

// 安装 Wrap
hook_err_t fp_hook_wrap(uintptr_t fp_addr, int32_t argno, void *before, void *after, void *udata);

// 卸载 Wrap
void fp_hook_unwrap(uintptr_t fp_addr, void *before, void *after);

// 类型化辅助（0-12 参数）
fp_hook_wrap0() ~ fp_hook_wrap12()
\```

### 回调函数示例

```c
void my_before(hook_fargs4_t *fargs, void *udata) {
    // 修改参数
    fargs->arg0 += 1;
    // 设置跳过原函数
    // fargs->skip_origin = 1;
}

void my_after(hook_fargs4_t *fargs, void *udata) {
    // 修改返回值
    fargs->ret += 100;
}

// 使用
hook_wrap4(some_func, my_before, my_after, NULL);
\```

---

## 已知限制

1. **仅支持 ARM64**：架构相关，不支持 ARM32 或其他架构
2. **固定容量限制**：
	- `TRAMPOLINE_MAX_NUM = 6`
	- `RELOCATE_INST_NUM = 56`
	- `HOOK_CHAIN_NUM = 16`
	- `FP_HOOK_CHAIN_NUM = 32`
3. **参数限制**：最多支持 12 个整数/指针参数，不支持浮点/SIMD 参数
4. **ADRP 重定位限制**：如果 `ADRP` 目标在被覆盖区域，会返回错误
5. **依赖设备端 Loader**：需要 loader 补符号后加载，暂不支持标准 `insmod`

---

## 参考链接

- [KernelPatch 项目](https://github.com/bmax121/KernelPatch)
- ARM64 指令集架构参考
- Linux 内核内存管理文档

---

一些小说明

- 1.有的地方函数并没有适配的很好，因为默认测试6.1和6.6的设备，一些有问题的地方可以发issue
- 2.在hook_alloc和hook_module_prepare_text这个地方有需要的可以去改改
- 3.可以将hook函数gpl导出，安装hook模块后，编写新的模块直接用(后面有空会规范一下代码推上去，都测试好了的

[项目链接](https://github.com/niqiuqiux/arm64_kernel_hook) https://github.com/niqiuqiux/arm64_kernel_hook

---

# 回复

## 回复 by 温泉划水鱼 (#2)

*2026-4-30 17:03*

看看

## 回复 by 4Chan (#3)

*2026-4-30 19:23*

学习一下

## 回复 by Imxz (#4)

*2026-5-1 14:43*

tql

## 回复 by mb_eumnbkwy (#5)

*2026-5-1 17:24*

qq

## 回复 by Zepp7289 (#6)

*2026-5-1 22:10*

tql

## 回复 by mb_dmryhnwz (#7)

*2026-5-2 00:11*

66

## 回复 by GEKEZYX (#8)

*2026-5-2 01:21*

666

## 回复 by mb_jwevvolh (#9)

*2026-5-2 12:25*

66666

## 回复 by xianhuimin (#10)

*2026-5-2 12:48*

666

## 回复 by jyotidwi (#11)

*2026-5-2 19:54*

6666

## 回复 by tonykros (#12)

*2026-5-2 23:20*

666

## 回复 by mb_lvesdvhu (#13)

*2026-5-3 15:48*

666

## 回复 by ClPrada (#14)

*2026-5-4 01:11*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_mlyojneh (#15)

*2026-5-5 11:17*

666

## 回复 by 万里星河 (#16)

*2026-5-5 18:44*

学不完 根本学不完

## 回复 by 魔童 (#17)

*2026-5-5 21:10*

看看

## 回复 by 需要渗透高手 (#18)

*2026-5-5 21:14*

6666666

## 回复 by 袁伟业 (#19)

*2026-5-5 21:23*

6666

## 回复 by wx_范迪塞尔 (#20)

*2026-5-6 08:52*

6666

## 回复 by uni7corn (#21)

*2026-5-9 14:04*

感谢分享

## 回复 by mb_lzotvdxv (#22)

*2026-5-9 19:54*

请在 Telegram 上联系我，我有一个重要的付费任务要交给你。 2000$ 任务
Telegram：@dlopenext

## 回复 by mb_lzotvdxv (#23)

*2026-5-10 12:38*

请在 Telegram 上联系我，有个重要的 2000 美元任务。
 Telegram：@dlopenext

## 回复 by 0x7 (#24)

*2026-5-12 17:13*

666

## 回复 by XCicada (#25)

*2026-5-12 17:20*

666

## 回复 by nhtr (#26)

*2026-5-22 13:42*

666

## 回复 by hyz111 (#27)

*2026-5-25 09:58*

666

## 回复 by mb_xjdhrmck (#28)

*2026-5-25 10:16*

666

## 回复 by mb_kdmyzaoz (#29)

*2026-6-9 05:54*

看看

## 回复 by mb_vdqbqpou (#30)

*2026-6-9 10:02*

666

## 回复 by huangjw (#31)

*2026-6-9 10:24*

学习

## 回复 by 钱钱钱￥ (#32)

*2026-6-9 10:31*

学习

## 回复 by taotao_su (#33)

*2026-6-9 13:25*

666

## 回复 by 曦曦大牛子 (#34)

*2026-6-10 07:02*

666

## 回复 by mb_qimctavn (#35)

*2026-6-10 08:02*

6

## 回复 by mb_enbuhisq (#36)

*2026-6-10 11:11*

66666666666

## 回复 by 小尘0000 (#37)

*2026-6-14 17:14*

666

## 回复 by iBa0 (#38)

*2026-7-9 20:11*

123

## 回复 by mb_qwgxafvv (#39)

*2026-7-10 10:08*

66

## 回复 by git_73275XuanLong18 (#40)

*2026-7-12 23:42*

aaa

## 回复 by wx_kx92911 (#41)

*2026-7-15 09:56*

感谢分析

## 回复 by simpleness (#42)

*2026-7-16 17:29*

6

## 回复 by CheRevir (#43)

*2026-7-16 18:22*

666

## 回复 by 洪堡企鹅 (#44)

*2026-7-17 15:46*

666

## 回复 by Vengeance (#45)

*2026-7-17 15:53*

666

## 回复 by Ro0kie (#46)

*2026-7-17 17:14*

666

## 回复 by mb_fnnjknab (#47)

*2026-7-21 14:13*

666

## 回复 by mb_srxvlszh (#48)

*2026-7-22 03:02*

666

## 回复 by Yuuuual (#49)

*2026-7-23 13:39*

学习记录，感谢分享

## 回复 by er胡 (#50)

*2026-7-24 17:07*

666

## 回复 by mb_tewbhakr (#51)

*2026-7-26 01:37*

看看

## 回复 by mb_ldbucrik (#52)

感谢分享
