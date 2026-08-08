---
title: '[原创] 使用 Kimi K3 进行脱壳工具迁移开发：R0DUMP —— 将 FART 迁移到 Android 16'
url: https://bbs.kanxue.com/thread-292107.htm
tid: 292107
author: Ivory0
date: '2026-07-21'
tags: [Android安全, 原创, 脱壳反混淆]
crawled_at: '2026-08-08T10:02:14+00:00'
replies: 110
---

# 使用 Kimi K3 进行脱壳工具迁移开发：R0DUMP —— 将 FART 迁移到 Android 16

![Kimi K3 正在分析项目](https://bbs.kanxue.com/upload/attach/202607/939147_SPMYRSKM7MCX6JQ.png)

- 项目地址：<https://github.com/tiwe0/r0dump>
- 测试环境：LineageOS 23.2 / Android 16；当前产品化验证目标是一加 9（`lemonade`），其他机型不在这次 patch bundle 的验证范围内
- 参考项目：FART / FART 6.0 源码、frida-fart、这次整理出的 r0dump 代码改动

## 前言

Kimi K3 模型刚出，听说效果非常的不错，给了老美一点小小的震撼。我也是第一时间入手严肃学习了一下，效果也是非常超出我的预期。几天加班加点的工作后，把这个脱壳系统赶了出来。震撼之感不亚于人生第一次吃麦当劳的薯条，我感觉以后不论是逆向还是工具链开发貌似都没人类什么事了（指工程落地方面）。脱完几个样本后，也是第一时间来分享一下成果。

进入正体，本文讨论的问题很具体：一个已经被公开 7 年的经典思路脱壳，如何借助 AI 的能力，再配合任务拆分与 Loop，把它更快地搬到新系统上，并把中间的代码、输出和修复流程适配甚至优化，整理成一套新的工具链。

这个经典项目就是 FART。FART 是逆向圈非常有名，非常具有代表性的脱壳定制系统项目，但该项目的上一个开源版本还停留在 Android 6/8 时代。

FART 的重点不是简单 dump dex，而是主动触达 Runtime 里的 `ArtMethod`，使用强制假调用的方式，强迫使二代壳中抽取出来的方法恢复（如偏移修正、方法恢复等），然后在把抽取壳运行时恢复出来的 `CodeItem` 记录下来。r0dump 做的事情，就是把这条主线迁到 LineageOS 23.2 / Android 16 上，再补上配置、输出、状态、repair 和 Manager。

本次工作的定位很明确：用 AI 作为长程工程协作者，再用 Loop 持续验证和修复 FART 迁移。人工判断路线和边界，工具辅助处理那些费时间、但可以验证的工作，比如读源码、对版本差异、草拟改动、整理日志和文档、patch、编译、remount 替换和测试。

## 声明

本文只讨论授权设备、授权应用和安全研究场景下的 Android Runtime 脱壳技术。文中工具不针对任何具体厂商或具体业务，不提供样本，不讨论绕过线上风控的操作细节，也不保证覆盖完全 native 化、VMP 化或强对抗样本，本项目亦没有刻意的特征隐藏。

另外请仅在你有权分析的设备、应用和数据上使用相关代码。

另外最重要的一点：刷机前先确认机器的 anti-rollback / bootloader 状态。

当前 patch 的设备集成目标是一加 9（`lemonade`）。刷机前仍应单独确认 bootloader 与 anti-rollback 状态；本文不把其他机型的降级行为写成通用结论。

不同厂商、不同机型、不同 bootloader 版本的反回滚策略不一样。有些机器一旦升级到带 anti-rollback 的版本，再回刷低版本系统就可能直接变砖。不要拿自己的主力机盲刷，也不要默认“能解锁 bootloader 就一定能回退”。

尤其是最近 Google 推送的 Android 16，几乎所有 piexl 设备升级 Android 16 后无法按照常规手段降级，随意降级极易变砖。

刷机需谨慎！！！
刷机需谨慎！！！
刷机需谨慎！！！

---

## 0. 产物

本次 patch bundle 围绕 FART 主线完成了一次面向 LineageOS 23.2 / Android 16 的源码级迁移。除了 ART 侧改动，还补了 framework 触发、Manager 控制台、输出目录、状态文件、repair 和系统集成。也就是 FART 思想在新版本系统上的复刻 + 增强。

当前 patch 归档（见 Github） `r0dump_lineage23_original_patches_20260721_225851.zip` 从功能上看，这次改动可以分成几块：

| 部分 | 做了什么 |
|-|-|
| Manager | 新增 privileged、platform-signed 的 `R0DUMPManager` 系统 App，用来选择目标 App、写入 `Settings.Global` 配置、控制策略、查看 status、扫描产物并执行 dex repair。 |
| ART runtime | 把 FART 的 `DexFile.dumpMethodCode()` / `ArtMethod` 方法级 dump 思路迁到 Android 16，补上 runtime 配置、输出、状态、去重和边界控制。 |
| framework 触发 | 在 `ActivityThread` 里读取 Manager 配置，按目标包、进程、class 前缀、策略和上限启动 dump thread，再通过 class walk 把 `Method` / `Constructor` 交给 ART。 |
| Android 16 输出 | 默认写到 `/sdcard/Download/R0DUMP/<process>`，必要时回退到目标 App 的 external-private 目录，避免外部存储策略导致产物写不出来。 |
| repair | Manager repair flow 支持标准 dex、`dexfixed_*.dex`，以及可选 raw mirror 的 `dexdata_*.bin` / `methods_raw_<pid>.jsonl`；可以生成 repaired dex、manifest 和 zip。 |
| 产品集成 | 把 `R0DUMPManager`、权限、构建开关、`R0DUMP_16` 版本展示和预置配置接进系统镜像，方便在目标测试机上直接操作。 |

能力状态如下：

| 能力 | 状态 |
|-|-|
| FART 等价 class walk 主线 | 已做：`ActivityThread` 启动 class walk，反射枚举 `Constructor` / `Method`，进入 `DexFile.dumpMethodCode()`。 |
| `Method/Constructor -> ArtMethod -> CodeItem` 方法级 dump | 已做：ART 侧通过反射对象拿到 `ArtMethod*`，再输出 dex 与方法体记录。 |
| Android 16 输出路径 | 已做：默认公开输出到 `/sdcard/Download/R0DUMP/<process>`，失败后回退到 app external-private `files/r0dump/<process>`。 |
| 状态与诊断 | 已做：`[R0DUMP]` log、`_r0dump_status.json` / `r0dump_status.json`、strategy/by-dex/skip 统计，以及 classloader、manifest、raw/async 计数。 |
| 方法记录格式 | 已做：`methods_<pid>.jsonl`，记录 dex key/hash/checksum、`method_idx`、offset、len、`code_item_b64`、strategy 等信息。 |
| repair | 已做：Manager repair flow 围绕 methods JSONL 回填 repaired dex，并生成 manifest / zip；这次 patch bundle 没有附带独立的 `repair_dex.py` 脚本。raw mirror 还支持按 header snapshot 重建或规范化 `dexdata_*.bin`。 |
| 默认策略 | 已收住：Manager/framework 默认预设是 `CLASS_WALK \| APP_CREATE \| ACTIVITY_CREATE \| IN_MEMORY_DEX \| DEFINE_CLASS`；`FORCE_BACKFILL` 和更激进的 hook 仍需显式打开。 |
| classloader / 动态 dex 观察 | 已做：可扫描 ART 已注册 classloader、loaded-class table、manifest component seed，并通过 Java `DexFile` / `BaseDexClassLoader` 路径观察 dex 打开和加载；class walk 默认 2 个 worker，最多 8 个。 |
| raw dexdata mirror | 已接入但默认关闭：启用后输出 `dexdata_*.bin` 和 `methods_raw_<pid>.jsonl`，保留运行时 dex header / map 等重建所需信息。 |
| oat/vdex、JIT、instrumentation 等更激进入口 | 这次保留了策略位和部分 hook 入口，但不能把它们写成所有场景都已完整验证。 |

完整刷机、样本 dump、repair 后静态工具打开这些结果，仍应以对应设备上的测试日志、status 和 manifest 为准。

---

## 1. 为什么这件事适合交给 AI + Loop

把 FART 思路迁到 Android 16，麻烦的地方不只是代码量。更烦的是来回切上下文：

- 要先读懂 FART 原始链路，不能把主动调用误写成普通 dex dump；
- 要理解 Android 6 到 Android 16 的 ART / framework 变化，知道旧 hook 点为什么不能原样搬；
- 要决定哪些是必须迁移，哪些只是实验策略或后续方向；
- 要让代码能合进去、系统能编译、进程能启动、文件能写出、runtime 能停下来；
- 还要把输出格式、repair 脚本、manifest 和最终结论接起来。

这种活很适合交给 AI 做总的上下文理解，再按源码分析、迁移实现、编译验证和结果整理几个阶段推进。我本地提前准备了两类代码：

- FART / FART 6.0 相关源码，用来还原原始主动调用链路；
- LineageOS 23.2 / Android 16 源码树，用来承载 r0dump 的迁移改动。

对 r0dump 这种要同时理解 FART 旧源码、Android 16 多仓库 patch、编译日志和测试截图的任务来说，Kimi K3 超长上下文的价值非常直接：可以少一点来回搬运，多一点连续推理。

实际工作按源码分析、迁移实现、编译验证和结果整理几个阶段推进。AI 主要用于串联这些阶段中的上下文，具体结果仍以代码、日志、设备状态和产物为准。

另外还有一个小技巧：多让 AI 提建议，多做“明知故问”，用问答把上下文垫厚。长上下文不是把所有东西一股脑塞进去，而是让模型能够保留决策、约束、失败记录和验证证据。输入越具体，后续的代码修改和结果核对就越容易展开。

接下来先我们先看技术本体。毕竟最终验收的还是人。如果你对 FART 什么都不懂，就只能一路无助地点击“接受，继续下一步”（无助的丈夫.jpg）。FART 的核心思路如果理解错了，模型只会更快地把错误放大。

从这个角度看，AI 带来的变化不是让专业知识失去价值，而是让专业知识的杠杆变大。没必要焦虑“万一我还没学会，AI 就已经超过我了”：模型可以把源码读得很快、把方案写得很漂亮，但路线选择、风险判断和最终验收仍然需要真正懂系统的人来负责。

![Kimi K3 在规划迁移任务](https://bbs.kanxue.com/upload/attach/202607/939147_CJMVC5EK2SJ9ABZ.png)

---

## 2. FART 真正值得迁移的是什么

FART 在 Android 逆向圈不用多介绍，是很经典的 ART 主动调用式脱壳方案。它的价值不只是 dump dex，而是通过主动触达 Runtime 中已经物化出来的 `ArtMethod`，把抽取壳运行时恢复出来的 `CodeItem` 记录下来，为后续方法体还原提供依据。

FART 6.0 的改动主要分布在四个地方：

- `frameworks/base/core/java/android/app/ActivityThread.java`
- `libcore/dalvik/src/main/java/dalvik/system/DexFile.java`
- `art/runtime/native/dalvik_system_DexFile.cc`
- `art/runtime/art_method.cc`

它的主线其实很清楚：**Java 层尽量把目标 App 的类和方法枚举出来；ART native 层把反射对象转成 `ArtMethod*`，再从 `ArtMethod` 定位 dex 和 `CodeItem`。**

### 2.1 Java 层：从 ActivityThread 启动 class walk

FART 在 `ActivityThread.performLaunchActivity()` 末尾调用 `fartthread()`。`fartthread()` 新起一个线程，默认 `sleep(1 * 60 * 1000)`，等待 App 先跑起来，然后执行 `fart()`。

`fart()` 的核心流程可以概括为：

\```
currentActivityThread()
-> mBoundApplication
-> LoadedApk.info
-> mApplication.getClassLoader()
-> BaseDexClassLoader.pathList.dexElements
-> Element.dexFile
-> DexFile.mCookie
-> DexFile.getClassNameList(mCookie)
-> appClassLoader.loadClass(eachClassName)
-> getDeclaredConstructors() / getDeclaredMethods()
-> DexFile.dumpMethodCode(Constructor / Method)
\```

几个关键点：

1. FART 不是被动等某个方法自然执行，而是主动遍历 `dexElements`，取每个 `DexFile` 的 class name list。
2. 对每个 class name，FART 会调用 `appClassLoader.loadClass(eachClassName)`，这一步本身就可能推动壳恢复类或方法体。
3. 类加载成功后，它会枚举构造函数和普通方法，把每个 `Constructor` / `Method` 通过反射传给 `dalvik.system.DexFile.dumpMethodCode(Object m)`。

所以 FART 里“主动调用”的重点，不是直接执行业务逻辑，而是主动把 Runtime 中能触达的类、构造函数和方法都触达一遍，再把这些反射对象送进 ART。

### 2.2 DexFile native：从 Method / Constructor 拿到 ArtMethod

FART 在 `DexFile.java` 里新增了一个私有 native 方法：

```java
private static native void dumpMethodCode(Object m);
\```

对应 native 注册在 `dalvik_system_DexFile.cc`：

```cpp
NATIVE_METHOD(DexFile, dumpMethodCode, "(Ljava/lang/Object;)V")
\```

native 实现非常短：如果传进来的 `method` 不为空，就通过：

```cpp
ArtMethod* artmethod = ArtMethod::FromReflectedMethod(soa, method);
myfartInvoke(artmethod);
\```

也就是说，Java 反射层的 `Method` / `Constructor` 到这里被转换成了 ART 内部的 `ArtMethod*`。FART 真正的脱壳点并不在 Java 反射本身，而在后面如何利用这个 `ArtMethod*`。

### 2.3 ART 层：用 self == nullptr 走 dumpArtMethod 分支

FART 在 `art_method.cc` 里加了两个关键函数：

```cpp
extern "C" void myfartInvoke(ArtMethod* artmethod) {
    JValue* result = nullptr;
    Thread* self = nullptr;
    uint32_t temp = 6;
    uint32_t* args = &temp;
    uint32_t args_size = 6;
    artmethod->Invoke(self, args, args_size, result, "fart");
}
\```

以及在 `ArtMethod::Invoke()` 开头增加判断：

```cpp
if (self == nullptr) {
    dumpArtMethod(this);
    return;
}
\```

这个设计比较巧妙：`myfartInvoke()` 并不是为了真的执行业务方法，而是故意传入 `self == nullptr`，让 `ArtMethod::Invoke()` 走到 FART 新增的 dump 分支。这样，FART 可以复用 `Invoke()` 这个入口携带当前 `ArtMethod`，但又避免真正调用目标业务逻辑。

`dumpArtMethod()` 做的事情包括：

- 从 `/proc/<pid>/cmdline` 读取当前进程名；
- 从 `ArtMethod` 取 `DexFile`、`PrettyMethod`、`method_idx`；
- 把所属 dex 写到 `/sdcard/fart/<process>/<dex_size>_dexfile.dex`；
- 通过 `artmethod->GetCodeItem()` 取方法体；
- 根据 `tries_size_` 判断是否需要走 try/catch handler 的 `codeitem_end()` 计算真实长度；
- 把 `{name, method_idx, offset, code_item_len, ins:<base64>};` 追加写入 `/sdcard/fart/<process>/<dex_size>_<tid>.bin`。

因此，FART 的输出分成两类：

\```
/sdcard/fart/<process>/<dex_size>_dexfile.dex
/sdcard/fart/<process>/<dex_size>_<tid>.bin
\```

前者是 dump 出来的 dex，后者是方法级 `CodeItem` 记录。`fart.py` 会解析 bin 中的 `{name, method_idx, offset, code_item_len, ins}`，按 `method_idx` 建表，并把 base64 解码后的方法体和 dex 中原始 `code_off` 对应的方法体做对照。这个脚本体现的是“用方法级记录还原方法体”的思路；这份源码里的 `fart.py` 更偏解析和对照，真正产出可用 repaired dex 还需要结合具体修复逻辑处理。

更详细的心路历程和技术介绍可以移步参考寒冰老师的几篇文章：

- [FART：ART环境下基于主动调用的自动化脱壳方案](https://bbs.kanxue.com/thread-252630.htm)
- [FART正餐前甜点：ART下几个通用简单高效的 dump 内存中 dex 方法](https://bbs.kanxue.com/thread-254028.htm)
- [拨云见日：安卓 App 脱壳的本质以及如何快速发现 ART 下的脱壳点](https://bbs.kanxue.com/thread-254555.htm)

### 2.4 FART 的可迁移主线

所以从源码看，FART 真正值得迁移的不是“找个地方 dump 一份 dex”，而是这条链路：

\```
ClassLoader / DexFile 枚举
-> 主动 loadClass
-> 反射拿 Method / Constructor
-> FromReflectedMethod 得到 ArtMethod
-> 从 ArtMethod 定位 DexFile + method_idx + CodeItem
-> 输出 dex + 方法体记录
\```

这条链路解决的是抽取壳场景下“dex 结构在，但方法体不完整”的问题。它希望在 Runtime 已经恢复或物化方法体之后，把 `CodeItem` 以方法粒度记录下来。

Android 16 迁移不只是“把 `dumpMethodCode()` 搬过去”这么简单。FART 原版实现里很多东西都比较粗：启动时机固定、所有进程都容易被扫、输出路径写死、dex 文件名只按 size 区分、bin 分散在 tid 文件里、缺少 status 和统计，也没有现代 Android 存储模型下的可靠输出策略。r0dump 要做的，就是保留这条主线，同时把工程边界收住。

---

## 3. r0dump 在 Android 16 上怎么改

r0dump 没有把 FART 原封不动搬到 Android 16，也不是简单堆 dump point (当然堆 dump point 也很重要)。它保留的是 FART 最关键的 `Method/Constructor -> ArtMethod -> CodeItem` 主线，但把原来比较粗放的触发、输出和后处理方式，改造成一个受控的 Runtime dump 工具链。

### 3.1 Framework 层：从“进程启动就扫”改成可控配置

FART 原始路径比较直接：在 `ActivityThread.performLaunchActivity()` 附近启动线程，延迟后获取当前 App 的 ClassLoader，遍历 dex 中的 class name，反射出构造函数和普通方法，再调用 `DexFile.dumpMethodCode()`。

r0dump 保留这条主线，但在 `ActivityThread` 侧加了一层运行时控制，并同时支持 `APP_CREATE` 和 `ACTIVITY_CREATE` 两个 App 启动触发点。内置系统应用 Manager 负责写入 `Settings.Global`，framework 负责读取这些 key 后决定当前进程是否应该启动 dump。`r0dump.dump.*` 命名空间保留下来，用于兼容已有 Manager/runtime 配置；新增用户界面方便调试。

关键配置包括：

- `r0dump.dump.enabled`：总开关；
- `r0dump.dump.global_runtime_enabled`：是否按全局 runtime 模式匹配所有 App；
- `r0dump.dump.target_package` / `r0dump.dump.target_process`：目标包名和进程；
- `r0dump.dump.process_mode`：主进程或指定进程控制；
- `r0dump.dump.output_root`：输出根目录，默认是 Downloads/R0DUMP；
- `r0dump.dump.delay_ms`：延迟启动，避免过早介入 App 初始化；
- `r0dump.dump.class_prefix`：class walk 过滤；
- `r0dump.dump.max_methods`、`r0dump.dump.max_records`、`r0dump.dump.max_seconds`：遍历、记录数和运行时间上限；
- `r0dump.dump.dump_constructors` / `r0dump.dump.dump_methods`：是否处理构造函数和普通方法；
- `r0dump.dump.class_walk_mode`：`load_all` 或 `loaded_only`；
- `r0dump.dump.class_walk.threads`：class walk 并行 worker 数，默认 2，最多 8；
- `r0dump.dump.art_classloader_scan.enabled`：是否扫描 ART 已注册的 classloader；
- `r0dump.dump.loaded_class_table_scan.enabled`：是否补充 loaded-class table；
- `r0dump.dump.manifest_component_seed.enabled`：是否用 manifest 组件作为 class seed；
- `r0dump.dump.raw_dexdata_mirror.enabled`：是否额外保留 raw dexdata 镜像，默认关闭；
- `r0dump.dump.async_export.enabled`：是否启用异步导出，默认关闭；
- `r0dump.dump.stop_after_complete`：class walk 完成后是否停止 native runtime；
- `r0dump.dump.force_backfill.*`：force backfill 的独立风险控制项。

这样改把脱壳行为从一上来全量触发，收成一次针对目标包、目标进程、目标类前缀和目标策略的受控实验。对 Android 16 上的真实样本来说，这一点比盲目增加 hook 点更重要，因为主动 load class、主动反射和主动触达 Runtime 都可能带来崩溃、卡顿或业务副作用。

经常做工程的朋友应该都知道，反复调试很费时间。有了 AI 辅助，把这些配置、日志和失败路径收进一个用户页面，可以明显提高调试效率；模型负责把反馈串起来，人负责决定下一轮到底改什么。

### 3.2 ART 层：方法级 CodeItem dump 仍然是主路径

ART 侧还是围绕 FART 最关键的思路来做：Java 反射对象进入 native 后，通过带 executable、cookie 和 class name 的 `dumpMethodCode()` 重载，把 cookie 里的候选 DexFile 交给 native 选择，再通过 `ArtMethod::FromReflectedMethod()` 拿到 `ArtMethod*`，最后从 `ArtMethod` 找到所属 dex、`method_idx`、`CodeItem` offset 和长度，把 dex 与方法体记录输出出来。

不同的是，r0dump 不再依赖 FART 原版 `myfartInvoke(self == nullptr)` 这个技巧作为唯一分发路径，而是把 `dumpMethodCode()` 直接接到统一的 dump 策略、状态和输出逻辑中处理。

在这个基础上，r0dump 主要补了几类工程能力：

- 统一 logcat tag 为 `[R0DUMP]`，方便调试；
- 默认公开输出根目录为 `/sdcard/Download/R0DUMP`，用于适配 Android 16 新收紧的安全策略；
- 如果 MediaStore 路径不可用，回退到 `/sdcard/Android/data/<package>/files/r0dump/<process>/`；
- Java `DexFile` / `BaseDexClassLoader` 路径也会记录 dex 打开、加载和 classloader 观察结果；
- Android 16 上 copied / obsolete `ArtMethod` 可能无法直接给出有效 DexFile，因此优先使用 cookie 和 class descriptor 选择 fallback DexFile，再回到 `ArtMethod` 映射；
- dex 文件名包含内容 hash、size、checksum、location hash、strategy 和来源信息，便于回溯；
- `DEFINE_CLASS` 路径可以生成 parser-friendly 的 `dexfixed_*.dex`；raw mirror 打开时还会生成 `dexdata_*.bin` 和 `methods_raw_<pid>.jsonl`；
- 维护已写 dex 文件名集合，避免同一 dex 在多个策略或多次触发中反复落盘；
- 方法记录写入 `methods_<pid>.jsonl`；
- status 主要写入 `_r0dump_status.json`，并兼容/回退写入 `r0dump_status.json`；
- 统计 `dex_files_written`、`method_records_written`、`duplicate_methods_skipped`、`invalid_methods_skipped`、`compact_dex_methods_skipped`；
- 按 strategy 和 dex 记录统计；
- 记录 classloader candidate、walked、dex element、cookie、loaded-class table、manifest component seed，以及 raw/async export 统计；
- force backfill 记录 attempts / success / failed，并在方法记录中保留 before / after hash 与 changed 结果。

重复 dex 抑制用于控制 I/O 和产物噪音。多策略或多时机可能反复看到同一个 dex，如果不做去重，产物目录会很快膨胀，后续 repair 也难判断哪份 dex 才是同一来源的代表文件。文件名里的 hash / checksum / strategy 用来降低误判风险。

### 3.3 输出这件小事：Android 16 上先保证“写得出来、找得到”

Android 6 时代 FART 直接写 `/sdcard/fart/<process>/` 这类外部存储路径。到了 Android 16，直接写外部存储顶层路径并不稳定，尤其是在 App 进程、scoped storage 和系统权限边界下更容易失败。

r0dump 的处理方式是：

\```
ART native
-> 判断是否使用默认 Downloads/R0DUMP 输出
-> 通过 JNI 调 ActivityThread.r0dumpWriteDownloadFile(...)
-> framework 用 MediaStore 写入 Download/R0DUMP/<process>/<dex>.dex
-> 如果 MediaStore 不可用，再回退到目标 App external-private files/r0dump/<process>
-> 同步写 methods_<pid>.jsonl、compact_skipped.jsonl、_r0dump_status.json / r0dump_status.json 等诊断文件
-> 按配置额外写出 dexfixed_*.dex、dexdata_*.bin 和 methods_raw_<pid>.jsonl
\```

对脱壳工具来说，dump 本身只是第一步；如果输出路径不可预测，后续 repair、复测和样本对比都会变成手工考古，没有心算 md5 能力的朋友估计胜任不了这项工作。

### 3.4 使用多策略尽可能覆盖脱壳路线

这次 Manager/framework 配置路径的默认策略是：

\```
CLASS_WALK | APP_CREATE | ACTIVITY_CREATE | IN_MEMORY_DEX | DEFINE_CLASS
\```

这里的 baseline 已经不是旧文章里的两个策略位：`APP_CREATE` 覆盖更早的 App 创建时机，`ACTIVITY_CREATE` 保留 FART 风格的 Activity 触发，`IN_MEMORY_DEX` 和 `DEFINE_CLASS` 则覆盖内存 dex 与类定义路径。更广的 `FORCE_BACKFILL`、oat/vdex、JIT、反射和 instrumentation 入口仍然需要显式配置，避免把实验性行为混入默认结果。

ART 侧这次保留的核心策略位包括：

\```
CLASS_WALK
APP_CREATE
ACTIVITY_CREATE
REAL_INVOKE
LOAD_METHOD
DEX_LOAD
REGISTER_DEX
IN_MEMORY_DEX
DEFINE_CLASS
LOAD_CLASS
RESOLVE_METHOD
FORCE_BACKFILL
FORCE_BACKFILL_BEFORE
FORCE_BACKFILL_AFTER
\```

当前 ART patch 的策略位已经扩展到 32 个入口，另外还包括 `OPEN_COMMON`、oat/vdex、verify、class init、interpreter、JIT、reflection、instrumentation、Java ClassLoader / Java DexFile route、oat register 和 image-space dex 等观察点。它们是可独立统计的实验入口，不等于每个入口都在本次设备运行中完成了覆盖验证。

这些策略不是“越多越强”，盲目开启过多脱壳点反而还会大幅降低效率。默认路径用于建立可复现 baseline；实验策略用于回答更细的问题，例如动态 dex 是否在注册时出现、某些方法是否在 resolve / load 阶段才具备有效 `CodeItem`、force backfill 前后 hash 是否变化。

Manager UI 里还暴露了这些实验策略位，便于按问题逐项打开；文章应把“代码中存在 hook / 策略位”和“设备上已验证有效”分开描述。

### 3.5 Manager：实验控制台

 ![r0dump manager](https://bbs.kanxue.com/upload/attach/202607/939147_V6CQSS37JKXDPXB.webp)

Manager 承担了以下几个功能：

- 作为 privileged system app 写入 `Settings.Global`，避免手工 adb 命令配置出错；
- 让 target package、process、class prefix、delay、limits、strategy mask 都可见；
- 把高风险策略分组，并对 `FORCE_BACKFILL`、`RESOLVE_METHOD + REAL_INVOKE` 等组合给出警告；
- 提供 start / stop / force-stop target 等操作，减少反复测试成本；
- 扫描输出目录，读取 `_r0dump_status.json` 或兼容的 `r0dump_status.json`，展示 artifacts；
- 内置 repair flow，把 `methods_<pid>.jsonl` 中的 `code_item_b64` 回填进 dex，并生成 repaired dex / zip / manifest；对 raw mirror 还支持 `dexdata_*.bin` 的重建和规范化。

Manager 是 r0dump 的一部分，不只是附带 UI。没有 Manager，r0dump 仍然可以通过 adb 配置；有了 Manager，测试流程更接近一个可交付工具链。

### 3.6 修复链路：从 methods JSONL 回填到 repaired dex

r0dump 落盘的东西并非终点。真正有分析价值的，是 repair 之后的 dex 文件。这次 patch bundle 中的 Manager 内置 repair flow：

```json
{
  "method_idx": 123,
  "code_item_offset": 45678,
  "code_item_len": 96,
  "code_item_b64": "..."
}
\```

修复逻辑会读取 `methods_<pid>.jsonl`，按 dex key / hash / checksum 找到对应 dex，把 `code_item_b64` 解码后回填到 `code_item_offset`。完成后生成 repaired dex，并输出一个 manifest，说明总输入、成功修复、跳过记录、重复 md5 和最终 zip 等信息。对启用 raw mirror 的产物，Manager 还会读取 `methods_raw_<pid>.jsonl` 和 header snapshot，重建或规范化 `dexdata_*.bin`。最后，所有修复并去重后的 dex 文件会压缩到一个 zip 中，方便直接拖入 jadx 等工具分析。

### 3.7 增强

这次 patch 相比旧版 FART 主线，真正新增的工程能力主要集中在四个方向：

- classloader 发现不再只依赖当前 App 的单一 `BaseDexClassLoader`，还可以合并 ART 已注册 classloader、loaded-class table 和 manifest component seed；class walk 默认使用 2 个 worker，最多放大到 8 个；
- Java `BaseDexClassLoader` / `DexFile` 路径会观察 dex element、cookie、构造和 `loadClass` 相关事件，让动态 dex 和后续加载路径有可追踪入口；
- `DEFINE_CLASS` 路径可以生成 `dexfixed_*.dex`，raw mirror 则在显式打开后生成 `dexdata_*.bin` 与 `methods_raw_<pid>.jsonl`，并保留 header / map 等重建所需数据；
- Android 16 的 copied / obsolete `ArtMethod` 映射不再只相信 `ArtMethod::GetDexFile()`，而是优先结合 Java cookie、class descriptor 和 class definition 选择 fallback DexFile，降低方法体映射到错误 dex 的风险。

这些增强让 r0dump 从“把 FART 的主动 class walk 搬过来”变成了“有多个可观测入口的运行时导出管线”。其中 raw mirror 默认关闭，应该根据样本和验证目标按需启用。

---

## 4. 测试部分：成功 dump 结果对比

下面是当前项目的三组测试对比，三个软件均使用 DexProtector 保护，分别是 `com.vietinbank.ipay`、`com.vnpay.bidv` 和 `com.VCB`。下文中的“未脱壳”指原始受保护 APK 对照，“r0dump repair 后”指 Manager repair flow 处理后产生的 `dexfixed_*.dex` 产物。

本节的核心验收标准是运行时是否成功 dump 出有效 dex、方法记录和 repair 产物；JADX 截图只是用来展示产物已经能够被加载和继续分析。完整覆盖率仍应结合 `methods_<pid>.jsonl`、status、manifest 和实际运行结果判断。

### 4.1 `com.vietinbank.ipay`：未脱壳原始 APK

![com.vietinbank.ipay 原始 APK 对照](https://bbs.kanxue.com/upload/attach/202607/939147_3PKGQQ5XSSAVQNG.png)

图中打开的是原始 APK 的 `AndroidManifest.xml` 和受保护应用结构，可以看到 `ProtectedIPAYApplication`、`ProtectedAppComponentFactory` 以及大量组件声明。这张图作为未脱壳基线，记录样本进入 r0dump 处理前的静态可见形态。可以看到右侧展示的 Activity 均不在左侧的类列表中，这些类目前还被以加密的形式存储在二进制文件中。

### 4.2 `com.vietinbank.ipay`：r0dump repair 后

![com.vietinbank.ipay r0dump repair 后](https://bbs.kanxue.com/upload/attach/202607/939147_GUHTZGH7NMNAPVM.png)

图中代码区显示从 `dexfixed_..._CLASS_WALK_...` 产物加载出的 `BookingHistoryActivity`，已经可以看到原始包名、import、Kotlin metadata、字段和方法体。这个结果与文章前面描述的 `DEFINE_CLASS` / fixed dex 输出和 Manager repair flow 对应。

### 4.3 `com.vnpay.bidv`：第二组测试

这是 `com.vnpay.bidv` 的独立测试样本。原始 APK 对照图中可以看到 `ProtectedMainApplication`、native 方法以及签名校验和字节处理逻辑；repair 后截图则显示 `com.vnpay.bidv_r0dump_repaired` 已经加载到 JADX，并展开到 `ConfirmSmartCounterActivity` 等业务包类。

![com.vnpay.bidv 原始 APK 对照](https://bbs.kanxue.com/upload/attach/202607/939147_67JZ4M9J3QDF78Q.png)

![com.vnpay.bidv r0dump repair 后](https://bbs.kanxue.com/upload/attach/202607/939147_7ZCGSG92PT5859Q.png)

repair 后截图中的 JADX 信息显示产物来自 `dexfixed_..._CLASS_WALK_...`，代码区能够看到 `com.vnpay.bidv.presentation.confirm.smart_counter` 包、AndroidX/业务层 import、Kotlin metadata 和 `ConfirmSmartCounterActivity`。

### 4.4 `com.VCB`：第三组测试

原始对照图对应 `com.VCB` 的原始 APK，可以看到 `ProtectedMainApplication`、`ProtectedAppComponentFactory` 以及原始 APK 的类结构。repair 后截图对应 `com.VCB_r0dump_repaired`，已经展开到 `com.VCB.ui.activities.accountlink` 包下的 `RegisterAccountLinkActivity`，并显示了业务层相关 import。

![com.VCB 原始 APK 对照](https://bbs.kanxue.com/upload/attach/202607/939147_VDN5SKYZ4CHNW4B.png)

![com.VCB r0dump repair 后](https://bbs.kanxue.com/upload/attach/202607/939147_9BQZPCFQ73KTWGW.png)

---

## 5. FART 与 r0dump 对比

| 维度 | FART | r0dump 这次实现 |
|-|-|-|
| 系统基线 | Android 6.0 为主 | LineageOS 23.2 / Android 16 |
| 核心思想 | 主动遍历 class + 主动触达 `ArtMethod` + 方法级 `CodeItem` dump | 保留这条主路径，并补上 runtime 配置、输出、诊断、repair 和产品打包 |
| Java 入口 | `ActivityThread.performLaunchActivity()` 后启动 `fartthread()` | `ActivityThread` 读取 `Settings.Global`，按包名、进程、前缀、策略和上限受控启动 |
| native 入口 | `dumpMethodCode()` -> `FromReflectedMethod()` -> `myfartInvoke(self=nullptr)` -> `dumpArtMethod()` | `dumpMethodCode(executable, cookie, className)` -> cookie-based DexFile 选择 -> `FromReflectedMethod()` -> 统一策略、状态和输出逻辑 |
| 默认策略 | class walk 主路径 | `CLASS_WALK \| APP_CREATE \| ACTIVITY_CREATE \| IN_MEMORY_DEX \| DEFINE_CLASS` |
| 实验策略 | 较少 | ART 中已有 load/resolve/register/in-memory/force-backfill 等实验策略；其他策略位按 patch 提供入口，但设备覆盖仍需逐项验证 |
| 输出路径 | `/sdcard/fart/<process>/` | `/sdcard/Download/R0DUMP/<process>`，失败后回退到 app external-private `files/r0dump/<process>`；可选生成 `dexfixed_*.dex` / `dexdata_*.bin` |
| 方法记录 | `<dex_size>_<tid>.bin` 中追加 `{name, method_idx, offset, code_item_len, ins}` | `methods_<pid>.jsonl`，字段包括 dex hash、method_idx、offset、len、`code_item_b64`、strategy；raw mirror 另有 `methods_raw_<pid>.jsonl` |
| 状态观测 | 主要依赖 logcat 和输出目录 | `[R0DUMP]` log、`_r0dump_status.json` / `r0dump_status.json`、strategy/by-dex/skip、classloader、manifest、raw/async 和 force-backfill 统计 |
| 后处理 | Python 2.7 `fart.py` 解析 bin、按 `method_idx` 对照方法体，体现修复思路 | Manager repair flow，生成 repaired dex / manifest / zip，并支持 raw dexdata 重建/规范化； |
| 风险控制 | 相对粗 | target/process/class prefix、record/time 上限、stop-after-complete、force-backfill 独立限制与 UI 警告 |
| 工程定位 | 原始主动调用式 ART 脱壳思想 | Android 16 迁移 + 可控实验 + 可诊断输出 + 可交付工具链 |

一句话概括：

>
> FART 的贡献是把脱壳推进到 Runtime 方法级 `CodeItem`；r0dump 这次的贡献，是在 Android 16 上保留这条核心路径，并把它改造成可配置、可观测、可修复、可打包的工程化工具链。
>
>
>

---

## 6. AI + Loop 在这次迁移中真正帮了什么

经常写逆向工具的朋友一眼就能看出 AI 在本案例中的价值：它把“理解一个跨多个 Android 仓库的迁移任务”从一次性的问答，推进成了可以持续跟踪、持续验证的工程过程。

- **长上下文**：可以同时保留 FART 旧实现、Android 16 迁移差异、patch、编译日志、status 和测试记录，减少反复复制上下文的损耗；
- **长程编程**：不只回答“这一行怎么写”，而是围绕目标持续导航仓库、处理终端反馈，再回到代码和验证结果中修正；
- **原生视觉与多模态**：可以把终端、JADX、流程图和截图当作工程材料一起理解，适合本文这种代码、日志和测试图混在一起的任务；
- **Loop 验证**：把源码修改、编译、运行、dump 和 repair 的结果反馈给下一轮，避免停留在一次性代码生成。

如果只看最后的代码改动，很容易低估中间过程的成本。真正耗时间的不是“写几行 hook”，而是不断确认：旧项目的核心到底是什么，新系统里哪个入口还能用，哪些策略会带来副作用，哪些输出能作为证据，哪些结果不能写过头。(逆向工具开发中的各种坑，谁踩谁知道)

| 阶段 | 目标 | 必须给出的证据 |
|-|-|-|
| FART 源码分析 | 还原原版主动调用链路 | `ActivityThread`、`DexFile.dumpMethodCode`、`ArtMethod::Invoke(self == nullptr)`、`fart.py` |
| Android 16 Runtime 分析 | 找迁移差异和可用入口 | ART / ClassLoader / DexFile / App process startup 的具体代码位置 |
| 实现 | 把差异落成最小改动 | `art`、`frameworks/base`、Manager、`Settings.Global`、产品集成 |
| 验证 | 核对输出闭环 | `[R0DUMP]` log、`_r0dump_status.json`、`methods_<pid>.jsonl`、repair manifest |
| 文档整理 | 区分事实、推断、设计目标和未验证结果 | 代码、日志、status、manifest 和测试截图 |

这次迁移里，AI 真正减少的是几类很耗人的体力活：

1. **源码定位**：在多个 Android 仓库中快速找到相关入口和调用链；
2. **改动草拟**：把重复性的配置、日志、状态和输出处理先搭出来；
3. **差异核对**：把 Android 6 思路和 Android 16 代码对齐；
4. **功能实现**：把业务需求按照实现文档落地成具体 hook，并辅助编译；
5. **验证归纳**：把 log、status、repair manifest 变成可复查证据；
6. **文档沉淀**：把“能跑一次”整理成“别人能看懂、自己能复现”的工具链。

人工主要负责：验收、以及指出 AI 干活期间犯的一些愚蠢错误。

AI 在这类迁移里的定位很简单：

>
> 它更适合辅助整理已经想清楚的技术路线，把工作拆成可以逐项推进、最后还能对账的工程任务，而不是凭空发明技术路线。
>
>
>

在这次迁移里，人负责决策层；AI 负责保持长链路上下文，辅助完成源码阅读、版本差异整理、改动草拟、实现和验证材料整理。模型没有替我做逆向判断，但它确实降低了把判断变成工具链的成本。

AI 再强，也不是输入一句话就能自动交付完整工程。真正让结果落地的是后面的 Loop：编译失败就看日志，运行异常就看 status 和 trace，dump 结果不对就回到策略和输出链路继续修。模型负责加速每一轮，人负责确认每一轮到底有没有接近可用。

而在这个环节，人的作用是不可或缺的。毕竟人是这个项目的最直接消费者。工程好不好，怎么调整，还得是人来起作用。AI 能把排查速度拉起来，但如何评判 dump 是否成功、哪些策略应该收住、哪些结果可以写进文章，仍然由使用者的专业素养决定。

---

## 7. 小结

FART 的价值在于提出了主动调用式 ART 脱壳思路：通过触达 Runtime 中的 `ArtMethod`，记录抽取壳运行时恢复出来的真实 `CodeItem`，把脱壳粒度从 dex 文件推进到方法体。

r0dump 做的事情，是把这条思路迁移到 LineageOS 23.2 / Android 16，并补齐现代 Android 环境下必须面对的工程问题：配置、作用域、存储、状态、日志、修复、Manager 和产品打包。

AI 在这里放大了逆向分析和系统开发能力。对个人研究者来说，这才是最值得重视的变化：经典技术路线仍然要人理解，风险边界仍然要人判断，但迁移、整理和验证这些耗时间的环节，可以拆成更小、更快、更容易复查的任务交给模型，再由人把关。

我直接用，最直白，最直接，最不绕弯子的话告诉各位我的感受：**AI 没办法替你产生安全研究里的核心判断，但它可以帮你更快地把判断变成代码、产物和文档，拓展一个人的工程边界，甚至给你一些思路上的启发。**

另外我还想探讨一些 AI 发展相关的问题：

很多朋友对 AI 这样的模型感到焦虑，实际大可不必。它越擅长长程工程，越需要有人能提出正确问题、识别错误结果，并为最终系统负责。

我们研究专业问题的大可不必因为 AI 而焦虑，因为我们做的是专业性问题，即便 AI 完全有能力替代我们的技术，但到了具体场景，还是要有人来拍板担责。

---

注：本项目代码和文章都在 AI 等 AI 工具辅助下完成，并经过作者精心审阅和调整，感谢 r0ysue 老师的指导和 hanbing 老师的开源 fart 项目。

请仅在授权设备、授权应用和合法安全研究场景中使用相关技术。本次 patch bundle 的设备集成目标是一加 9（`lemonade`）；其他机型刷机和降级行为请单独核验 anti-rollback / bootloader 状态。

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2026-7-22 03:21*

感谢分享

## 回复 by caolinkai (#3)

*2026-7-22 03:48*

好牛逼，感谢 分享

## 回复 by rooky2000 (#4)

*2026-7-22 08:55*

感谢分享

## 回复 by ulong9527 (#5)

*2026-7-22 09:27*

6

## 回复 by Zepp7289 (#6)

*2026-7-22 10:15*

tql

## 回复 by iBa0 (#7)

*2026-7-22 10:22*

1

## 回复 by amwpecel (#8)

*2026-7-22 10:49*

666

## 回复 by guijingwen (#9)

*2026-7-22 11:14*

66

## 回复 by Emil_796703 (#10)

*2026-7-22 11:24*

厉害，走在最前沿

## 回复 by roysue (#11)

*2026-7-22 13:08*

999

## 回复 by MaYil (#12)

*2026-7-22 13:27*

感谢分享

## 回复 by jdong (#13)

*2026-7-22 14:32*

感谢分享

## 回复 by xingbing (#14)

*2026-7-22 15:32*

感谢分享

## 回复 by mb_kozxrjqu (#15)

*2026-7-22 16:28*

感谢分享

## 回复 by git_51684xuexijiaoben (#16)

*2026-7-22 16:28*

首次回复，处女贴

## 回复 by mb_cqcrdwgm (#17)

*2026-7-22 16:36*

666

## 回复 by mb_jhohnbzu (#18)

*2026-7-22 16:53*

666

## 回复 by wx_插曲 (#19)

*2026-7-22 17:12*

666

## 回复 by 我是土匪 (#20)

*2026-7-22 17:28*

有了AI之后，网络安全的门槛降低了好多，只要提示词写得好，大多都能解决。不知道下一个阶段的攻防对抗会演变成什么样

## 回复 by mb_4nrpVMxJ (#21)

*2026-7-22 19:20*

666

## 回复 by 学着学逆向 (#22)

*2026-7-22 19:57*

学习下

## 回复 by Lion001 (#23)

*2026-7-22 22:07*

感谢分享

## 回复 by ~时光荏苒 (#24)

*2026-7-22 23:26*

学习下

## 回复 by mb_tewbhakr (#25)

*2026-7-22 23:37*

666

## 回复 by wx_Huber Barrientos (#26)

*2026-7-23 00:59*

666

## 回复 by mb_qimctavn (#27)

*2026-7-23 10:36*

6

## 回复 by westinyang (#28)

*2026-7-23 10:48*

666

## 回复 by byhk (#29)

*2026-7-23 11:04*

谢谢分享

## 回复 by r0reborn (#30)

*2026-7-23 11:24*

6666

## 回复 by mb_ysikfhxt (#31)

*2026-7-23 11:31*

111

## 回复 by 小尘0000 (#32)

*2026-7-23 13:51*

666

## 回复 by 聊表心意 (#33)

*2026-7-23 14:25*

k3好不好用，dp用的我头疼

## 回复 by 巷口的那只猫 (#34)

*2026-7-23 14:39*

我是让grok4.5帮我完成脱壳改机。fart源码来自yehan大佬的修改的fart，我也加了对dexprotect的so/dex处理，这里要感谢小佳大佬还有版主的帖子。我魔改了aosp 安卓13和15 效果均达到理想状态，我的机器不止于脱壳处理，还加了基础环境/hook反检测/摄像头注入以及对应的自动化工具等功能。AI真的很强大，如果一个人要独立完成这些功能，我个人认为要苦学2-3年至此，而如今即使你是逆向小白，你只需知道部分检测原理ai就可以帮推演出整体逻辑并给予相应方案。

## 回复 by dextoart (#35)

*2026-7-23 14:41*

666

## 回复 by 悠久之翼灬 (#36)

*2026-7-23 16:11*

666

## 回复 by huangbof (#37)

*2026-7-23 18:47*

感谢分享

## 回复 by mb_hcadvceu (#38)

*2026-7-23 19:21*

谢谢分享

## 回复 by 弄好了 (#39)

*2026-7-23 23:44*

666

## 回复 by mb_mrcxjlrd (#40)

*2026-7-24 00:15*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by shuangmou (#41)

*2026-7-24 11:15*

感谢分享

## 回复 by zengiswj (#42)

*2026-7-24 13:03*

6666666666

## 回复 by hyz111 (#43)

*2026-7-24 14:07*

![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by mb_btwdlppy (#44)

*2026-7-24 14:22*

666 学习下

## 回复 by mb_iemtkmio (#45)

*2026-7-24 14:30*

666

## 回复 by Snowman_Liam (#46)

*2026-7-24 15:26*

6666

## 回复 by mb_zanihjkx (#47)

*2026-7-24 17:18*

666

## 回复 by wx_白鸟之诗 (#48)

*2026-7-24 18:36*

66666666666

## 回复 by pangzibupang (#49)

*2026-7-24 20:50*

感谢分享

## 回复 by kudos5566 (#50)

*2026-7-25 01:42*

6

## 回复 by xwtwho (#51)

*2026-7-25 11:52*

666

## 回复 by mb_euhyowpw (#52)

*2026-7-25 11:54*

666

## 回复 by Weak chicken (#53)

*2026-7-25 12:09*

学习下

## 回复 by mb_cwtaoyyq (#54)

*2026-7-25 15:30*

666

## 回复 by 祝今朝 (#55)

*2026-7-26 00:39*

6

## 回复 by mb_ukrtiqtt (#56)

*2026-7-26 07:00*

学习下

## 回复 by tianhaoday (#57)

*2026-7-26 09:28*

666

## 回复 by buluo533 (#58)

*2026-7-26 09:45*

学习下

## 回复 by 毛毛毛毛虫 (#59)

*2026-7-26 09:56*

学习一下

## 回复 by Midsw (#60)

*2026-7-26 17:56*

mark . tql.

## 回复 by hacker521 (#61)

*2026-7-26 18:27*

AI真的高产

## 回复 by xianhuimin (#62)

*2026-7-26 18:27*

666

## 回复 by wx_huhu_859 (#63)

*2026-7-26 19:44*

11

## 回复 by lookthatsnow (#64)

*2026-7-26 21:39*

666

## 回复 by UncleChen (#65)

*2026-7-27 00:04*

学习下

## 回复 by UncleChen (#66)

*2026-7-27 00:19*

这个总结写太好了![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by RhaySF (#67)

*2026-7-27 01:21*

666

## 回复 by yushusu (#68)

*2026-7-27 10:07*

6

## 回复 by iamshy (#69)

*2026-7-27 10:53*

感谢分享

## 回复 by 寻梦之璐 (#70)

*2026-7-27 12:57*

6666

## 回复 by caseone (#71)

*2026-7-27 14:59*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by cmputer (#72)

*2026-7-27 16:44*

666

## 回复 by 随风而行aa (#73)

*2026-7-27 16:50*

看看

## 回复 by xinhu (#74)

*2026-7-27 19:08*

666

## 回复 by 红桃J (#75)

*2026-7-27 20:37*

666

## 回复 by myller (#76)

*2026-7-28 07:02*

666

## 回复 by 寒号鸟二代 (#77)

*2026-7-28 08:49*

66666

## 回复 by tt8369 (#78)

*2026-7-28 10:16*

666666

## 回复 by mb_jnmxfjku (#79)

*2026-7-28 10:42*

666

## 回复 by Darght (#80)

*2026-7-28 15:53*

6666

## 回复 by xekuns (#81)

*2026-7-28 16:13*

感谢分享

## 回复 by 木头子 (#82)

*2026-7-28 17:11*

666

## 回复 by kurtjerry (#83)

*2026-7-28 19:34*

感谢分享

## 回复 by wx_coddvccwyh (#84)

*2026-7-28 22:36*

9999

## 回复 by mb_qbqklzyt (#85)

*2026-7-28 23:24*

666

## 回复 by mb_cbgtaveo (#86)

*2026-7-29 00:37*

666666

## 回复 by wx_OME (#87)

*2026-7-29 04:26*

很强！！！

## 回复 by yyyyy——— (#88)

*2026-7-29 14:23*

666

## 回复 by tetora (#89)

*2026-7-29 15:39*

666

## 回复 by Ruinv6 (#90)

*2026-7-29 16:09*

666666

## 回复 by jsjsjwjs (#91)

*2026-7-29 21:40*

666

## 回复 by wwwywm (#92)

*2026-7-30 09:19*

666

## 回复 by console_ (#93)

*2026-7-30 11:05*

6

## 回复 by secflag (#94)

*2026-7-31 21:37*

学习下

## 回复 by mb_wzxcpnsa (#95)

6666学习下

## 回复 by 尤瑟努 (#96)

k3这套流程花了多少token，多少钱![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_tawwmfks (#97)

感谢分享

## 回复 by lbunknow (#98)

666

## 回复 by mb_hfeqoiiy (#99)

666

## 回复 by mb_gkbxtfri (#100)

666

## 回复 by mb_egqterpv (#101)

666

## 回复 by 太岁又沐风 (#102)

666

## 回复 by 52bug (#103)

![image](https://bbs.kanxue.com/view/img/face/003.gif)![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by IceSword (#104)

学习下。

## 回复 by 阿沁· (#105)

学习一下

## 回复 by mb_mnqaubnh (#106)

9

## 回复 by mb_xgoaxxei (#107)

感谢 分享

## 回复 by 卡坦精 (#108)

666

## 回复 by mb_sqetvntx (#109)

学习

## 回复 by wx_郑泽科 (#110)

6666

## 回复 by mb_irhdtnzm (#111)

1
