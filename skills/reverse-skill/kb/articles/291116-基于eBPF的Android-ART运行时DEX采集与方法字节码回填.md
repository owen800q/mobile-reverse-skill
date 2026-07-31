---
title: '[原创]基于eBPF的Android ART运行时DEX采集与方法字节码回填'
url: https://bbs.kanxue.com/thread-291116.htm
tid: 291116
author: PanzerT
date: '2026-05-06'
tags: [Android安全, 原创, 基础理论, 脱壳反混淆, 系统相关, 工具脚本]
crawled_at: '2026-07-31T15:07:14+08:00'
replies: 58
---

>
> 关键词：Android、ART、eBPF、uprobe、DEX、Nterp、CodeItem、Rust、aya
>
>
> 项目地址：<https://github.com/chinleez/eBPFDexDumper-rs>
>
>
> 适用环境：Android 13-17 / ARM64 / root / 支持 eBPF 的内核
>
>
>

---

## 摘要

Android 加固方案在高版本系统上逐渐从完整 DEX 加密演化为方法级抽取、运行时短暂回填、Nterp 路径覆盖以及 native buffer 中转等多种形态。传统依赖自定义 ROM、Frida inline hook 或 ptrace 的脱壳方式通常存在侵入性强、易被检测、跨 Android 版本维护成本高等问题。

本文以开源项目 `eBPFDexDumper-rs` 为例，介绍一种基于 Linux eBPF uprobe/uretprobe 的 Android ART 运行时 DEX 采集方案。该方案不向目标进程注入 so，也不修改目标进程中的用户态代码逻辑；它通过在内核侧观察 ART 解释器入口、DexFile 生命周期入口以及 libc native buffer 操作，捕获 DEX 起始地址、文件大小和执行过的方法字节码，再由 Rust 用户态完成分块拼装、缺页兜底读取、DEX 去重、CodeItem 反扫和方法字节码回填。

文章重点讨论四个工程问题：第一，如何在 Android 13-17 的 ART 变化中定位可用 hook 目标；第二，如何把 ART 私有对象布局以运行时参数注入 eBPF 程序，降低 ROM 差异带来的重编译成本；第三，如何在 BPF verifier 限制下传输大体积 DEX 与变长方法字节码；第四，如何把采集到的 `insns` 回填到 DEX 并重算 SHA-1 / Adler-32，使输出结果能被 jadx、baksmali 等工具继续处理。

需要说明的是，本文讨论的是授权设备、授权应用和安全研究场景下的动态观测技术。它不试图绕过所有反分析能力，也不保证覆盖完全 native 化或 VMP 化的极端样本。

---

## 1. 背景与问题

### 1.1 Android 高版本脱壳难点

近几年常见 Android 加固方案有几个明显趋势：

1. **方法级抽取**：原 DEX 中的 `class_data_item` 仍在，但部分方法的 `code_item.insns` 被清零、替换或延迟填充。方法真正执行前，壳在运行时短暂恢复字节码。
2. **Nterp 成为主路径**：Android 11 之后，ARM64 上的 Nterp 解释器覆盖了大量解释执行场景。只盯早期 `art::interpreter::Execute` 很容易漏方法。
3. **DexFile 生命周期被弱化**：高版本 ART 中部分构造函数会被内联，符号也可能被 strip。仅依赖 `DexFile::DexFile` 一类入口不够稳。
4. **native buffer 中转**：壳可能先在 native 层 `mmap` 一段内存，把解密后的 DEX 或片段拷贝进去，再交给 ART 或自定义加载逻辑。
5. **跨 ROM 布局漂移**：同为 Android 13+，不同 OEM ROM 中 `mirror::Class`、`DexCache` 等对象字段位置仍可能有细微变化。

因此，一个实用的运行时 DEX 采集工具不能只依赖单个 hook 点，也不能把 ART 私有布局写死在用户态或内核态逻辑里。

### 1.2 传统方案的局限

| 方案 | 典型做法 | 优点 | 局限 |
|-|-|-|-|
| 自定义 ROM | 修改 AOSP ART，在解释/调用路径中 dump | 覆盖面强，控制力高 | 一机一版本，维护成本高，ROM 指纹明显 |
| Frida hook | 注入 agent，hook ART/libc/native 函数 | 部署快，脚本化方便 | 注入痕迹明显，容易触发反 Frida / 反 hook |
| ptrace / 调试器 | 通过调试接口观察内存与调用 | 通用性较强 | 性能瓶颈明显，调试器存在本身可被检测 |
| maps 扫描 | 扫 `/proc/&lt;pid&gt;/maps` 中的可读区域 | 实现简单 | 对短暂解密、碎片化 DEX 覆盖不足 |
| eBPF uprobe | 内核侧挂用户态探针，ringbuf 输出事件 | 目标进程内无 so 注入，统一观测多进程 | 需要 root 和内核 eBPF 能力，仍可能被精细检测 uprobe |

eBPF 的价值在于把“观测点”放到内核侧：BPF 程序在 uprobe 命中时读取寄存器和用户态内存，然后把事件写入 ringbuf。用户态只负责加载程序、attach 探针、消费事件和落盘。

---

## 2. 项目结构与数据流

`eBPFDexDumper-rs` 是一个 Rust 项目，主二进制为 `eBPFDexDumper`。与本文相关的核心模块如下：

| 路径 | 作用 |
|-|-|
| `bpf/bpf.c` | eBPF 程序，定义 ART/libc uprobes、事件上报和内核侧缓存 |
| `bpf/header.h` | BPF map、事件结构、ART layout 结构定义 |
| `src/dump.rs` | 加载 BPF、attach 探针、消费 ringbuf、读取远程内存、落盘 |
| `src/art.rs` | 解析 `libart.so`，定位 hook 目标与 ART 默认布局 |
| `src/dex.rs` | DEX 基础解析、校验与方法信息读取 |
| `src/fix.rs` | 方法字节码回填、DEX checksum/signature 重算、`final/` 汇总 |
| `src/platform.rs` | Android 包名、UID、APK 路径和 oat 清理辅助 |

命令行分为三个子命令：

| 子命令 | 用途 |
|-|-|
| `dump` | attach eBPF 探针，采集 DEX 与方法字节码 |
| `fix` | 将 `_code.json` 中的方法字节码回填到已 dump 的 DEX |
| `offsets` | 单独解析 `libart.so`，输出 hook 目标和 ART layout，便于排查 |

整体数据流如下：

```
Target App / ART / libc
        |
        | uprobe / uretprobe
        v
bpf/bpf.c
        |
        | events / dex_chunks / method_events
        | read_failures / layout_debug_events / native_buffer_events
        v
Rust 用户态
        |
        | process_vm_readv fallback
        | maps scan / CodeItem backscan / native buffer scan
        v
/data/local/tmp/dex_out/&lt;package&gt;/
        |-- dex_&lt;begin&gt;_&lt;size&gt;.dex
        |-- dex_&lt;begin&gt;_&lt;size&gt;_code.json
        |-- fix/
        `-- final/
```

输出目录按目标自动分组：使用 `--name` 时以包名建目录；只指定 `--pid` 时尽量从 `/proc/&lt;pid&gt;/cmdline` 推断；只指定 `--uid` 时使用 `uid_&lt;num&gt;/`。

---

## 3. Hook 矩阵设计

### 3.1 ART 解释器入口

当前 `dump` 主流程默认 attach 的 ART 主入口包括：

```c
SEC("uprobe/libart_execute")          // art::interpreter::Execute
SEC("uprobe/libart_executeNterpImpl") // ExecuteNterpImpl / ExecuteNterpWithClinitImpl
SEC("uprobe/libart_nterpOpInvoke")    // nterp_op_invoke_* pattern targets
```

这组 hook 负责捕获“正在执行的方法”。入口参数根据 ABI 分为两类：

- `art::interpreter::Execute`：从寄存器参数中取得 `ShadowFrame*`，再读取其中的 `ArtMethod*`。
- `ExecuteNterpImpl`、`ExecuteNterpWithClinitImpl`、`nterp_op_invoke_*`：按当前实现假设 `x0` 中为 `ArtMethod*`。

拿到 `ArtMethod*` 后，BPF 程序尝试沿 ART 对象链解析 DEX：

```
ArtMethod*
  -> declaring_class_
  -> mirror::Class.dex_cache_
  -> mirror::DexCache.dex_file_
  -> art::DexFile.begin_
  -> DexHeader.file_size
```

Android 64 位 ART 通常使用 32-bit `HeapReference`。因此实现中会先判断压缩引用，避免把低 32 位对象引用当作 64 位用户态地址直接读取。同时，ARM64 顶字节可能带 MTE/PAC tag，读取前会统一 `untag`。

### 3.2 DexFile 生命周期入口

仅靠解释器入口会漏掉尚未执行的方法和某些 DexFile 生命周期事件。因此项目还会根据 `src/art.rs` 的解析结果 attach：

```c
SEC("uprobe/libart_dexFileCtor")       // DexFile::DexFile / DexFileLoader::OpenOne
SEC("uprobe/libart_registerDexFile")   // ClassLinker::RegisterDexFile
```

`DexFile::DexFile` 和 Android 16/17 上常见的 `DexFileLoader::OpenOne` 都符合“`x1` 位置可取得 DEX begin”的形态，因此可以复用同一个 BPF handler。`RegisterDexFile` 则从 `DexFile*` 读取 `begin_`，再检查 DEX header。

仓库中也包含 `uprobe_libart_verifyClass` 的 BPF handler 和 `VerifyClass` 目标定位逻辑，但当前 `dump` 主流程没有默认 attach 该探针。文档和使用预期应以实际 attach 路径为准，不能把它算作默认采集链路。

### 3.3 libc native buffer 入口

为覆盖“DEX 先在 native buffer 中短暂出现”的场景，项目默认尝试 attach 以下 libc 探针：

```rust
("memcpy",   "uprobe_libc_memcpy",   Some("uretprobe_libc_memcpy"))
("memmove",  "uprobe_libc_memmove",  Some("uretprobe_libc_memmove"))
("mmap",     "uprobe_libc_mmap",     Some("uretprobe_libc_mmap"))
("mmap64",   "uprobe_libc_mmap",     Some("uretprobe_libc_mmap"))
("mprotect", "uprobe_libc_mprotect", None)
```

entry probe 记录参数，uretprobe 在函数返回后检查目标地址是否出现 `dex\n` magic 和合理的 `file_size`。BPF 侧只做轻量判断，完整 DEX header 校验、范围扫描和解析放到用户态完成，以减少 verifier 压力。

---

## 4. ART 目标定位与布局注入

### 4.1 Hook 目标定位

Android 高版本中 `libart.so` 的符号保留情况差异很大。`src/art.rs` 使用纯 ELF 解析定位目标，不依赖在目标进程中 `dlopen` 或执行 ART 代码。主要策略包括：

1. **符号匹配**：优先匹配 `art::interpreter::Execute`、`ExecuteNterpImpl`、`ExecuteNterpWithClinitImpl`、`DexFile::DexFile`、`DexFileLoader::OpenOne`、`ClassLinker::RegisterDexFile` 等符号。
2. **字节模式扫描**：在符号缺失时，用 Nterp 入口和 `nterp_op_invoke_*` 的 ARM64 指令特征定位候选地址。
3. **分支扫描**：围绕 `ExecuteNterpImpl` 查找直接跳转目标，推断 `ExecuteNterpWithClinitImpl` 一类变体。
4. **字符串引用反推**：通过 `.rodata` 中的 `"Interpreting "` 字符串和 `.text` 中的 ADR/ADRP+ADD 引用反推 `Execute` 附近入口。
5. **手工兜底**：通过 `--execute-offset`、`--nterp-offset` 和 `--art-layout` 接管自动定位失败的 ROM。

代码里的 `TargetSource` 目前分为 `manual`、`symbol`、`pattern`、`string-ref` 四类；分支扫描属于 pattern 路径的一种实现细节。

### 4.2 ART layout 动态注入

eBPF 程序通过 `art_layout_t` 描述读取 ART/DEX 关键字段所需的偏移：

```c
struct art_layout_t {
    u32 shadow_frame_method_offset;
    u32 art_method_declaring_class_offset;
    u32 art_method_dex_method_index_offset;
    u32 art_method_data_offset;
    u32 class_dex_cache_offset;
    u32 dex_cache_dex_file_offset;
    u32 dex_file_begin_offset;
    u32 dex_header_file_size_offset;
    u32 code_item_insns_size_offset;
    u32 code_item_insns_offset;
};
```

默认布局对应 Android 13+ AOSP 主线 ARM64 常见结构：

```
ShadowFrame.method              = 0x08
ArtMethod.declaring_class       = 0x00
ArtMethod.dex_method_index      = 0x08
ArtMethod.data                  = 0x10
Class.dex_cache                 = 0x10
DexCache.dex_file               = 0x10
DexFile.begin                   = 0x08
DexHeader.file_size             = 0x20
CodeItem.insns_size             = 0x0c
CodeItem.insns                  = 0x10
```

用户态加载 BPF 后会把 layout 写入 `art_layout_map[0]`。这个 map 使用 `BPF_MAP_TYPE_HASH` 而不是单元素 array，是为了让 BPF 程序在用户态尚未写入时 `lookup` 返回 `NULL`，从而回退到内置的 `default_art_layout`，避免读到全 0 偏移。

### 4.3 ROM 偏移漂移处理

`Class.dex_cache_` 和 `DexCache.dex_file_` 在不同 ROM 上可能出现在相邻 slot。主路径失败时，BPF 会在有限范围内做 4x4 网格尝试：

```c
#pragma unroll
for (int class_slot = 0; class_slot < 4; class_slot++) {
    u32 class_dex_cache_offset = 0x10 + class_slot * 8;
    #pragma unroll
    for (int dex_cache_slot = 0; dex_cache_slot < 4; dex_cache_slot++) {
        u32 dex_cache_dex_file_offset = 0x10 + dex_cache_slot * 8;
        if (read_dex_from_art_method(...)) {
            return 1;
        }
    }
}
```

这里使用固定边界和 `#pragma unroll` 是为了满足 BPF verifier 对循环可证明性的要求。

---

## 5. 大体积 DEX 与方法字节码传输

### 5.1 DEX 分块续传

DEX 文件可能达到几十甚至上百 MiB，不能作为单条 ringbuf 记录输出。项目用 `dex_chunks` ringbuf 加 `dexProgress_map` 实现分块续传：

```
dexProgress_map[begin] = next_offset
```

每次同一个 DEX 再次被 hook 命中时，BPF 从 `next_offset` 继续发送固定大小 chunk。当前 chunk 记录大小为 `RINGBUF_SIZE = 1 << 17`，也就是 128 KiB；单次 BPF 调用最多推进 `MAX_CHUNKS_PER_CALL = 128` 个 chunk。

当 `bpf_ringbuf_reserve` 失败或 `bpf_probe_read_user` 读页失败时，BPF 发送 `read_failures` 事件，交给用户态兜底。

### 5.2 `process_vm_readv` 缺页兜底

`bpf_probe_read_user` 是非阻塞读取，不会替目标进程触发缺页换入。如果目标页尚未驻留，BPF 侧读取会失败。用户态收到 `read_failures` 后调用 `process_vm_readv`：

```rust
libc::syscall(
    libc::SYS_process_vm_readv,
    pid as libc::pid_t,
    &mut local,
    1usize,
    &mut remote,
    1usize,
    0usize,
)
```

在 root 场景下，这一 fallback 能把 BPF 侧不适合完成的阻塞式大块读取转移到用户态，降低 BPF 程序复杂度。

### 5.3 方法字节码事件

方法级抽取场景中，原始 DEX 文件本身可能存在，但目标方法的 `insns` 被抹掉。项目在解释器入口解析到 `ArtMethod*` 后，会进一步通过 `ArtMethod.data_` 读取 `CodeItem`，采集：

- `dex begin`
- `method_idx`
- `ArtMethod*`
- `codeitem_size`
- `insns` 字节

BPF 中用 `methodCodeCache_map` 对 `ArtMethod*` 去重，避免同一方法重复发送。由于方法字节码是变长数据，项目使用 per-cpu 16 KiB 缓冲作为中转，再通过 `bpf_ringbuf_output` 输出到 `method_events`。

用户态会把这些记录累计到：

```
dex_&lt;begin&gt;_&lt;size&gt;_code.json
```

记录中保存方法名、`method_idx` 和 hex 编码的字节码。方法名解析失败时，回退为 `method_idx_&lt;n&gt;`。

---

## 6. Fallback 采集链

实际样本里，任意单一路径都可能被绕开。因此项目把采集路径分成几层。

### 6.1 L0：ART 方法链

这是最准确的路径。解释器入口命中后，工具从 `ArtMethod*` 解析到 DEX begin/size，并同步采集当前方法的 `CodeItem.insns`。

适用场景：

- 普通解释执行
- 方法级抽取但执行前会恢复 `insns`
- 仍通过 ART/Nterp 分发的方法

### 6.2 L1：DexFile 注册/打开路径

`DexFile::DexFile`、`DexFileLoader::OpenOne`、`ClassLinker::RegisterDexFile` 用于捕获已经进入 ART DexFile 生命周期但尚未执行到具体方法的 DEX。

适用场景：

- DEX 被 ART 加载但方法还未触发
- 构造/注册阶段还能看到完整 DEX header

### 6.3 L2：CodeItem 反扫

当 ART 链路解 DEX 失败，但 `ArtMethod.data_` 仍像是 `CodeItem*` 时，BPF 发送 `layout_debug_events`。用户态从 `code_item_ptr` 所在页向前扫描 `dex\n` magic，最大回扫 64 MiB，并要求候选 DEX 范围包含该 `code_item_ptr`。

这条路径用于处理 `dex_cache` 链不稳定、字段偏移异常或部分 ART 私有路径失效的情况。

### 6.4 L3：maps / native buffer 扫描

`dump` 默认启动一次 `/proc/&lt;pid&gt;/maps` 扫描，跳过 `/apex/`、`/system/framework/`、`/data/dalvik-cache/` 等系统 DEX 路径，对可读 region 查找合法 DEX header。

native buffer 事件则来自 `mmap`、`mprotect`、`memcpy`、`memmove`。命中后，用户态会先尝试从事件地址读取 DEX；如果地址本身不是 DEX 起点，则在限定范围内继续扫描。

这两条路径覆盖率更宽，但精度低于 ART 链路，因此所有写盘前都要经过 DEX header 校验、`DexParser` 解析和 SHA-1 内容去重。

---

## 7. DEX 回填与输出整理

### 7.1 `method_idx -> code_off` 映射

`fix` 阶段不会依赖外部 dexlib，而是直接解析 DEX 的 `class_def_item` 和 `class_data_item`。核心过程如下：

1. 遍历 `class_defs`。
2. 读取每个类的 `class_data_off`。
3. 解 ULEB128，跳过 static/instance fields。
4. 读取 direct methods 与 virtual methods。
5. 按 DEX 规范累加 `method_idx_diff`，记录 `method_idx -> code_off`。

这样可以根据 dump 阶段记录的 `method_idx` 找回原 DEX 中对应 `code_item` 的位置。

### 7.2 回填 `insns`

标准 `code_item` 中：

```
code_off + 0x0c = insns_size_in_code_units
code_off + 0x10 = insns
```

回填时，工具会根据原 DEX 声明的 `insns_size` 计算期望长度，将采集到的字节码写入 `insns` 区域。若采集长度短于声明长度，剩余部分清零；若长度不一致，会记录 `length_mismatch`，便于后续人工审计。

### 7.3 重算 DEX 校验链

DEX 修改后必须重算 header 中的 SHA-1 与 Adler-32：

```
SHA-1   = sha1(dex[32..])
Adler32 = adler32(dex[12..])
```

项目会把修复版写入 `fix/`，再汇总到 `final/`：

- 有成功回填结果时，`final/` 使用修复版。
- 没有 `_code.json` 或修复失败时，`final/` 回退原始 DEX。

这种目录设计方便后续工具只消费 `final/`，同时保留原始采集结果用于对比。

---

## 8. 工程细节

### 8.1 关停状态机

运行中第一次收到 SIGINT/SIGTERM 时，工具停止主 ringbuf 循环，但仍允许 flush JSON 和 auto-fix；第二次信号会进入强制退出状态，跳过后处理。

这一设计解决的是大应用 dump 时的常见问题：用户希望 Ctrl-C 后尽快停止 attach，但又不希望已经采集的数据因为未 flush 而丢失。

### 8.2 先 detach 再 drain

退出主循环后，用户态会先 drop `ebpf`，让所有 uprobe detach，再做最后一轮 ringbuf drain。否则目标进程仍在运行时，ringbuf 可能一边 drain 一边继续增长，导致收尾阶段 livelock。

### 8.3 BTF 资源内嵌

部分 Android 内核没有暴露 `/sys/kernel/btf/vmlinux`。项目在 `assets/` 中内嵌了精简 BTF 资源：

```
assets/a12-5.10-arm64_min.btf
assets/rock5b-5.10-arm64_min.btf
```

用户态检测不到系统 BTF 时，会根据内核 release 选择内置 BTF 解析，提升在 Android 设备和开发板上的加载成功率。

### 8.4 oat 清理与自动修复

`dump` 默认会根据包名查找 APK 路径并清理目标应用的 `oat` 目录，促使下次启动更多走解释器或重新加载路径。退出时默认执行 auto-fix，将可回填的 DEX 直接整理到 `final/`。

这些行为都提供了关闭开关：

```bash
--no-clean-oat
--no-auto-fix
--no-code-item-fallback
--no-maps-scan
--no-native-buffer-scan
```

---

## 9. 复现与验证建议

本文不把单次本地样本结果写成普适性能结论。不同设备的内核配置、ROM ART 编译方式、目标应用规模和壳行为都会显著影响命中率与开销。更稳妥的验证方式是按以下步骤复现。

### 9.1 构建

macOS 宿主机示例：

```bash
brew install llvm
export CLANG=/opt/homebrew/opt/llvm/bin/clang
sh build_android.sh
```

产物路径：

```
target/aarch64-linux-android/release/eBPFDexDumper
```

### 9.2 目标定位检查

先在设备上检查 `libart.so` 的定位结果：

```bash
adb shell su -c '/data/local/tmp/eBPFDexDumper offsets \
  -l /apex/com.android.art/lib64/libart.so --json'
```

重点关注：

- 是否至少定位到 `ExecuteNterpImpl` 或其他主入口。
- `DexFile::DexFile` / `DexFileLoader::OpenOne` 是否命中。
- `ClassLinker::RegisterDexFile` 是否命中。
- ART layout 是否符合当前 ROM；不符合时用 `--art-layout` 覆盖。

### 9.3 dump 与 fix

```bash
adb push target/aarch64-linux-android/release/eBPFDexDumper /data/local/tmp/
adb shell su -c 'chmod +x /data/local/tmp/eBPFDexDumper'

adb shell su -c '/data/local/tmp/eBPFDexDumper dump \
  -n com.example.app \
  -o /data/local/tmp/dex_out'

adb shell su -c '/data/local/tmp/eBPFDexDumper fix \
  -d /data/local/tmp/dex_out/com.example.app'
```

建议验证：

- `dex_*.dex` 是否能被 `jadx` 或 `baksmali` 解析。
- `dex_*_code.json` 中是否出现目标业务方法。
- `fix/` 与 `final/` 中的 DEX 是否比原始 dump 多出有效方法体。
- 多次运行是否因 SHA-1 去重避免大量重复文件。

---

## 10. 局限性与威胁模型

### 10.1 平台限制

- 当前实现面向 Android ARM64。
- 需要 root 权限。
- 需要内核支持 eBPF、uprobe 和 ringbuf。
- ART 布局默认值面向 Android 13+ AOSP 常见布局，强定制 ROM 可能需要 `--art-layout`。

### 10.2 覆盖边界

以下场景可能无法完整恢复：

| 场景 | 影响 |
|-|-|
| 完全 native 化 / dex2c / VMP | 方法不再回到 ART 解释器，L0/L1 失效 |
| 指令级碎片化解密 | 内存中不出现连续合法 DEX 或完整 `insns` |
| 自定义 syscall 或绕过 libc wrapper | native buffer 探针可能漏掉分配/拷贝事件 |
| 强反 uprobe 检测 | 可通过探测断点、dirty page 或时序发现分析行为 |
| 非标准 ART 对象布局 | 需要人工 layout 或新增适配逻辑 |

### 10.3 可观测性与隐蔽性

uprobe 的实现会在目标 ELF 对应位置设置断点机制。虽然这不是 Frida 式 so 注入，也不需要改目标进程业务代码，但它并不是“不可检测”。具备精细自检能力的壳仍可能发现探针痕迹。

因此，本项目更适合定位为安全研究、取证分析和授权逆向环境中的低侵入采集工具，而不是对抗所有商业壳的隐蔽执行框架。

---

## 11. 结论

`eBPFDexDumper-rs` 展示了一条不同于 Frida 注入和 ROM 修改的 Android DEX 运行时采集路线：把 ART/libc 关键路径上的观测逻辑放在 eBPF uprobe 中，把复杂的 DEX 拼装、缺页读取、CodeItem 反扫和回填逻辑放在 Rust 用户态中完成。

这种分层让工具在 Android 13-17 ARM64 上具备较好的工程可维护性：BPF 侧只做短路径判断和事件输出，用户态负责高复杂度处理；ART 字段布局通过 map 注入，ROM 差异可以在运行时修正；DEX 和方法字节码分别通过分块续传和变长事件传输，最终再统一落盘、去重和修复。

它的边界同样明确：需要 root 和 eBPF-capable kernel，无法覆盖完全脱离 ART 的 native/VMP 方法，也可能被专门的反 uprobe 检测发现。只要在授权场景下使用，并把输出结果与样本行为、jadx/baksmali 解析结果结合验证，它可以作为 Android 高版本 DEX 采集与方法回填的一条实用工程路径。

---

## 参考资料

[1] LLeavesG. *eBPFDexDumper*. <https://github.com/LLeavesG/eBPFDexDumper>

[2] aya-rs. *aya: an eBPF library for Rust*. <https://github.com/aya-rs/aya>

[3] Android Open Source Project. *ART runtime source*. <https://android.googlesource.com/platform/art/>

[4] Android Developers. *Dalvik Executable format*. <https://source.android.com/docs/core/runtime/dex-format>

[5] Linux Kernel Documentation. *BPF Ring Buffer*. <https://www.kernel.org/doc/html/latest/bpf/ringbuf.html>

---

## 附录：使用速览

```bash
# 查看帮助
./eBPFDexDumper --help

# 按包名 dump，退出时默认 auto-fix
su -c './eBPFDexDumper dump \
  -n com.example.app \
  -o /data/local/tmp/dex_out'

# 按 UID dump
su -c './eBPFDexDumper dump \
  -u 10123 \
  -o /data/local/tmp/dex_out'

# 单独修复一个输出目录
su -c './eBPFDexDumper fix \
  -d /data/local/tmp/dex_out/com.example.app'

# 只解析 libart hook 目标
su -c './eBPFDexDumper offsets \
  -l /apex/com.android.art/lib64/libart.so --json'

# ROM layout 不匹配时手工覆盖
su -c './eBPFDexDumper dump \
  -n com.example.app \
  --art-layout 0x08,0x00,0x08,0x10,0x10,0x10,0x08,0x20,0x0c,0x10'
```

输出结构：

```
/data/local/tmp/dex_out/com.example.app/
|-- dex_&lt;begin&gt;_&lt;size&gt;.dex
|-- dex_&lt;begin&gt;_&lt;size&gt;_code.json
|-- fix/
|   `-- dex_&lt;begin&gt;_&lt;size&gt;_fix.dex
`-- final/
    `-- dex_&lt;begin&gt;_&lt;size&gt;.dex
```

请仅在你有权分析的设备、应用和数据上使用本项目。

注：本项目代码与本文内容均在 AI 辅助下完成。

---

# 回复

## 回复 by aut0run (#2)

*2026-5-6 12:06*

感觉有点东西啊

## 回复 by 墨穹呢 (#3)

*2026-5-6 12:47*

感谢分享

## 回复 by 温泉划水鱼 (#4)

*2026-5-6 13:46*

6

## 回复 by xianhuimin (#5)

*2026-5-6 14:39*

666

## 回复 by xingbing (#6)

*2026-5-6 16:50*

谢谢分享

## 回复 by Zepp7289 (#7)

*2026-5-6 17:23*

tql

## 回复 by mb_ssjlfpnk (#8)

*2026-5-6 20:20*

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by Viseris (#9)

*2026-5-6 22:25*

谢谢分享

## 回复 by jyotidwi (#10)

*2026-5-7 00:16*

tql

## 回复 by cecini (#11)

*2026-5-7 04:59*

这已经在生产上使用了吗

## 回复 by cecini (#12)

*2026-5-7 05:27*

1. [但是由于eBPF的局限性，其无法替代FART等基于主动调用的脱壳工具](https://blog.lleavesg.top/article/eBPFDexDumper)
有什么局限，导致功能上有什么区别吗
2 它不试图绕过所有反分析能力，也不保证覆盖完全 native 化或 VMP 化的极端样本。能具体详述吗？

## 回复 by PanzerT (#13)

*2026-5-7 10:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  cecini](https://bbs.kanxue.com/user-903862.htm)
>  1. [但是由于eBPF的局限性，其无法替代FART等基于主动调用的脱壳工具](https://blog.lleavesg.top/article/eBPFDexDumper)
> 有什么局限，导致功能 ...
>

1. eBPF 局限带来的功能区别
  eBPF/uProbe 方案的限制主要在“只能看到发生过的事”：

  - 没执行到的方法，不一定能拿到真实 CodeItem。壳如果按需解密方法体，只有方法真正进入解释器/ART 路径时，eBPF 才有机会记录。
  - 它不能主动枚举类和方法，也不能替你调用每个方法。FART 的强项正是主动遍历类方法、触发方法解密，再 dump CodeItem 并回填。
  - 如果代码走 AOT/JIT/native 快路径，绕开你挂的 ART 解释器点，eBPF 可能只能拿到整体 DEX，拿不到执行时还原的方法体。
  - 如果内存中没有连续合法 DEX，只是 native 层临时拼出碎片、解密后马上擦除，通用 eBPF DEX 扫描也不一定能拼回完整文件。
  - eBPF 内核侧不能随意做复杂逻辑，受 verifier、栈大小、ring buffer、用户内存读取限制影响。文章里也提到过内核侧分片传 DEX 容易丢数据，后来才转向用户态 process_vm_readv 读取。

  所以功能上可以这么理解：

  - eBPFDexDumper-rs 更适合：低侵入、被动捕获、拿运行时已加载的 DEX、记录已执行方法字节码、适合常规壳和动态加载场景。
  - FART 更适合：代码抽取壳、方法体被 nop/占位替换、需要主动触发每个方法恢复真实 CodeItem 的场景。
  - eBPF 的优势是隐蔽和部署轻；FART 的优势是覆盖率和主动性，但侵入更强，通常依赖 ART/系统改造或更重的运行时控制。

  2. “不绕过所有反分析，不保证 native/VMP 极端样本”具体指什么
  “反分析能力”这里不是一句泛泛而谈，具体包括这些：

  - 目标可以检测 root、调试环境、异常系统属性、可疑文件、SELinux 状态、Magisk 痕迹等。这个项目不会帮你隐藏这些环境特征。
  - uProbe 不是完全无痕。它通常会在目标映射上留下可检测的断点式痕迹，强对抗样本可以校验 libart.so 代码页、扫描异常指令、检测性能/时序异常。
  - 目标可以检测 BPF/tracing 相关状态，比如内核 tracing、perf/uProbe 行为、BPF program/map 痕迹。当前项目提供 --probe-mode lifecycle|maps-only 降低探针面，但不是“反检测框架”。
  - 目标可以不让敏感代码进入 ART 字节码路径，例如把核心逻辑搬到 native .so，Java 层只剩 JNI 壳或空方法。这种情况下 dump 出 DEX 也看不到核心算法。
  - “完全 native 化”指业务逻辑已经变成 ARM64 机器码，DEX 里只有声明、桥接、加载器或少量壳代码。eBPF 盯 ART/DexFile 只能拿 Java 层结构，不能自动还原 native 算法。
  - “VMP 化”指原始字节码被翻译成壳自定义虚拟机指令，运行时由 native VM 解释器执行。此时 DEX 里可能只剩 VM 入口和字节码 blob，真实语义在 native VM 指令集中，dump DEX 不等于还原源码。
  - “代码抽取”指 DEX 方法体被 nop、空实现或占位结构替代，真实 CodeItem 在执行前才临时恢复。被动方案只能覆盖触发过的部分；没触发的仍然缺失。

## 回复 by Gryffindoss (#14)

*2026-5-7 16:42*

666

## 回复 by cecini (#15)

*2026-5-7 19:49*

>
> [PanzerT](https://bbs.kanxue.com/user-598424.htm)
>  1. eBPF 局限带来的功能区别
>  eBPF/uProbe 方案的限制主要在“只能看到发生过的事”：
>
>  - 没执行到的方法，不一定能拿到真实 CodeItem。壳如果按需解密方法体，只有 ...
>

多谢详尽的解释

## 回复 by mb_eumnbkwy (#16)

*2026-5-7 20:35*

看看

## 回复 by Imxz (#17)

*2026-5-8 11:16*

tql

## 回复 by bujianshi (#18)

*2026-5-8 14:37*

tql

## 回复 by artake (#19)

*2026-5-8 17:51*

666

## 回复 by mb_tciajwop (#20)

*2026-5-9 11:20*

666

## 回复 by uni7corn (#21)

*2026-5-9 13:52*

感谢分享。学习了

## 回复 by Thehepta (#22)

*2026-5-9 14:00*

1

## 回复 by mb_lfwgtxdb (#23)

*2026-5-9 14:47*

感谢分享

## 回复 by mb_rbvykvqm (#24)

*2026-5-9 16:17*

感谢老铁

## 回复 by 小木马 (#25)

*2026-5-11 10:55*

6666

## 回复 by Ankeys (#26)

*2026-5-11 14:09*

666

## 回复 by huangjw (#27)

*2026-5-12 09:41*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by mb_ysikfhxt (#28)

*2026-5-12 22:01*

111

## 回复 by mb_qimctavn (#29)

*2026-5-13 10:34*

6

## 回复 by mb_rirvdrlh (#30)

*2026-5-14 15:33*

6666666666666

## 回复 by 随风而行aa (#31)

*2026-5-14 23:14*

看看

## 回复 by iBa0 (#32)

*2026-5-21 21:00*

111

## 回复 by mb_hcadvceu (#33)

*2026-5-25 18:39*

路过看看

## 回复 by 自称宅男 (#34)

*2026-5-25 19:11*

123

## 回复 by FloatGuy (#35)

*2026-5-29 11:47*

666

## 回复 by 船长弟弟 (#36)

*2026-5-31 10:04*

66666666

## 回复 by Migc (#37)

*2026-6-1 13:46*

666

## 回复 by tjytjy (#38)

*2026-6-1 16:04*

666

## 回复 by XCicada (#39)

*2026-6-2 15:11*

tql

## 回复 by x1a0f3n9 (#40)

*2026-6-2 17:27*

感谢分享![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 寻梦之璐 (#41)

*2026-6-4 10:12*

6666

## 回复 by 有的是钱啊 (#42)

*2026-6-4 11:12*

2

## 回复 by GEKEZYX (#43)

*2026-6-5 00:25*

666

## 回复 by mb_jnmxfjku (#44)

*2026-6-9 18:00*

666

## 回复 by wx_kx71647 (#45)

*2026-6-10 19:04*

6666![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by mb_qnrjnwyl (#46)

*2026-6-11 21:32*

牛

## 回复 by 蚂蚁驮大象 (#47)

*2026-6-12 09:50*

学习

## 回复 by wx_小白_266 (#48)

*2026-6-17 10:43*

看看

## 回复 by mb_audxeeaj (#49)

*2026-6-17 11:23*

学习了

## 回复 by 呼吸24K纯氧 (#50)

*2026-6-18 13:38*

看看分享

## 回复 by YooHaa (#51)

*2026-6-18 14:49*

666

## 回复 by 4ak5ra (#52)

*2026-6-19 15:39*

6666

## 回复 by mb_ntpggcsm (#54)

*2026-6-20 05:40*

6666

## 回复 by ulong9527 (#55)

*2026-6-26 09:48*

感谢分享，学习一下

## 回复 by ulong9527 (#56)

*2026-6-26 09:48*

感谢分享，学习一下

## 回复 by ulong9527 (#57)

*2026-6-26 09:48*

感谢分享，学习一下

## 回复 by wx_kx92911 (#58)

*2026-7-15 09:47*

感谢分析

## 回复 by mb_degalzhb (#59)

*2026-7-15 14:39*

666

## 回复 by caseone (#60)

![image](https://bbs.kanxue.com/view/img/face/079.gif)
