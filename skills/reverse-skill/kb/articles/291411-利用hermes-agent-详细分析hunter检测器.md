---
title: '[原创]利用hermes agent 详细分析hunter检测器'
url: https://bbs.kanxue.com/thread-291411.htm
tid: 291411
author: 秋落
date: '2026-05-31'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T13:51:54+08:00'
replies: 14
---

# Hunter 检测原理分析

## 前言:agent 学会了防御,也学会了拆解

2026 年 3 月 12 日,Hermes Agent 发布 `v2026.3.12`。按官方 release 说明,这是 **Hermes Agent v0.2.0**,也是继 `v0.1.0` 这个 pre-public foundation 之后的首个正式 tagged release,不是严格意义上的"第一个版本"。截至 2026-05-30 查询官方 GitHub 仓库,`NousResearch/hermes-agent` 已在 17 万 Star 左右;一个月内破十万这类增长叙事和 OpenClaw 的热潮相互映照,但真正让安全圈记住它的,不是 star 数,而是一个有点"灵异"的故事。

Hermes 的卖点其实并不花哨:一个能长时间自主跑任务的通用 agent,真正的差异化全压在"记得住"和"会自己改进"这两件事上。官方文档把这套能力拆成几块:一层是**记忆**(memory),核心是 `~/.hermes/memories/` 下的 `MEMORY.md` 和 `USER.md`,分别保存环境/项目经验与用户偏好,会在会话开始时注入上下文;另一层是**技能**(skill),反复用到的操作流程被固化成可复用的 `SKILL.md`,需要时 agent 可用 `skill_manage` 创建、更新、删除。换句话说,它不是把所有经验塞回模型参数,而是把经验外置成可读、可改、可复用的本地资产 —— 这恰好是下面那个故事的伏笔。

公开安全文章里转述过这样一个案例:有人拿自动化引擎反复攻击 Hermes,反弹 shell 一个变体接一个变体地打。一开始次次得手;可打着打着,Hermes 忽然就不执行了,像是凭空对这种攻击免疫了。这个故事本身不是官方 release note 里的正式结论,更适合当作安全测试转述来看;官方文档能直接佐证的是它确实具备自管 memory、创建/修改 skill、以及后台复盘的机制。若这个案例成立,它的技术解释并不神秘:攻击样本被当成"下次别再犯同一个错"的经验沉淀了下来。

官方文档对这套"复盘"循环的描述更具体:`run_agent.py` 侧维护 `_turns_since_memory` 和 `_iters_since_skill` 两类计数。默认逻辑是每 **10 个用户 prompt** 触发一次 memory review,每 **10 个 tool iteration** 触发一次 skill review;达到阈值后调用 `_spawn_background_review(messages_snapshot=..., review_memory=..., review_skills=...)` fork 出后台 Review Agent。它不接手原任务,而是回看刚刚那段对话,判断"这一段里有什么是下次该记住的?"以及"有什么操作值得固化成 skill?"。复盘完成后,经验被写入 memory 或通过 `skill_manage` 落盘成 skill,主 agent 继续原任务。

关键在于,这个循环对"什么算经验"并不挑食:用户纠正过的偏好是经验,踩过的坑是经验,复杂任务里反复出现的操作模式也是经验。因此,如果上面那个攻击案例的日志链路完整,它的解释就不必诉诸"灵异":同一种 payload 反复出现、某次被识破后,Review Agent 可能把"这类输入要警惕"当成普通经验存下来。所谓"进化出免疫",更保守的说法是:一套通用复盘机制,可能恰好作用在了攻击样本上。它没学会抽象意义上的"安全",它只是学会了"别再犯同一个错" —— 拒绝执行可疑 payload,刚好是这条通用规律的一个特例。

这个故事迷人,但它还有另一面:让 Hermes 这类 agent 变得有用的那套能力 —— 会读代码、会调工具、能在数百步里不丢线索地复盘 —— 换个方向用,就是今天最锋利的**逆向工具**。当这样的 agent 经 MCP 接上 IDA、Ghidra、Frida,它能把一个加固 SO 从 JNI 注册表一路扒到风险汇聚点,速度远高于纯手工检索。本文通篇出现的"IDA MCP 实读",就是这么来的。

可问题恰恰也藏在这儿。agent 读伪代码太"顺"了 —— 顺到它会不知不觉把"看起来合理"当成"事实",把"hook 完那个方法、界面里风险项没了"当成"绕过成功"。在一个老实的 app 上,这种幻觉无伤大雅;但这一次我们要拆的是 **Hunter** —— 一个会用多进程、syscall 跳板、CRC 自检反过来咬你的家伙。在它面前,一条幻觉结论的代价是:你以为已经绕过,实际上 `:hunter_server_iso` 子进程正通过 Binder 把同一条风险项原样传回 UI。

所以这篇文章不是又一份"我把 Hunter 绕了"的炫技记录。它记录的是:当我们把 agent 放出去拆 Hunter v6.58(`versionCode 658` / `libhunter.so`),怎么让它的每一条结论都不是"它觉得",而是"证据逼它承认"。办法说穿了很朴素 —— 给这只会读代码的 agent 也上一道**证据门**:每个检测点,都要静态、动态两条独立证据线对上才算数。静态线从 `art_register_natives_batch` 的 60 项注册表锚定 Java 方法到 native RVA,再用 IDA 伪代码 / 字符串 / xref 还原算法;动态线在汇聚点 `build_native_ListItemBean_risk @ 0x278658` 落 hook,用 `ReportRiskItem` 的 `LR` 反查到精确 callsite,用 `MainActivity.n0` 的 UI 三元组确认命中来源,最后用 bypass 让目标风险项消失来反向闭环。

## 判定标准只有一条:不是"hook 完界面干净了"就算数,而是要证明**检测算法、命中原因、绕过点三者之间的因果关系**。没对上的,一律降级,绝不升格成"已确认"。这道门的全部规矩,就是下面 5 条。

Hermes Agent静态 IDA 反编译 + 动态 Frida hook 两条独立证据线,逐条还原 Hunter v6.58 的检测算法。每条结论都满足:

1. JNI Native注册表证明 Java 方法到 native RVA 的对应关系
2. IDA 字符串 / xref / 伪代码证明 native 函数内部行为
3. 动态 `ReportRiskItem` 的 LR(返回地址) 落在对应 native 函数内
4. Java `MainActivity.n0` 的 stack 证明最终 UI 风险项来源
5. 对相应入口做 bypass 后,目标风险项消失

```
APK          com.zhenxi.hunter  v6.58 / versionCode 658
SO           lib/arm64-v8a/libhunter.so
SHA256       e575daabdeab10b41351286367a77fdb4c0e2ae3aa8d66af7495e046b4a63123
IDA          imagebase 0x0
测试环境     Pixel 6 Pro / Android 15 (AP4A.241205.013) / SDK 35
             google/raven/raven:15/AP4A.241205.013/12621605:user/release-keys
Frida        17.9.7
```

## 目录

- 1. 分析方法
- 2. JNI 动态注册:绕过 RegisterNatives 监控
- 3. 安全 syscall 跳板:借 linker SVC 绕开 libc 监控
- 4. 风险项汇聚点 `build_native_ListItemBean_risk`
- 5. 完整性自检:模块 r-x 段 CRC 双链
- 6. `/proc/mounts` Root/APatch 检测
- 7. libart maps 分片/Hook 检测
- 8. libc/libart/linker 运行时 checksum 检测
- 9. 注入/匿名可执行内存检测
- 10. 其他进程扫描检测
- 11. APatch/KP/KernelSU side-channel 检测
- 12. Verified Boot / 解锁状态检测
- 13. 环境变量采集
- 14. 通用文件 marker 检测
- 15. 风险文件路径检测
- 16. AVC denial 日志侧信道
- 17. 包名 ELF 白名单扫描
- 18. APK 签名一致性
- 19. system_server hook 检测
- 20. VPN 接口检测
- 21. Frida 线程名扫描
- 22. 多进程 Binder 上报机制
- 23. 已确认的实现缺陷
- 24. 检测点总表
- 25. 为什么这些结论可靠
- 附录
	- A. 相关文件清单
	- B. 关键 RVA 速查表
	- C. 测试命令
	- D. 完整 60 项 `off_2EF1F0` 注册表(IDA MCP 实读)

---

## 1. 分析方法

### 1.1 静态侧

首先从 `JNI_OnLoad` 内 `art_register_natives_batch(env, NativeEngine, off_2EF1F0, 60)` 注册表建立 Java 方法到 so 函数的映射。Hunter 不依赖普通 JNI 导出名,而是通过 ArtMethod 直接 patch 的方式注册。运行时枚举 `off_2EF1F0` 表(每项 `{name*, sig*, fn*}` = 24 字节,共 60 项),完整 60 项见**附录 D**。本文 SO 层下沉 bypass 脚本 `hook_native_bypass_so.js` 明确分类并 `Interceptor.replace` 了其中 **25 个 detection 入口**(其余 35 项为 `popen` / `MD5` / 工具方法 / 信息查询 / 还未细化分类的 detection 等,见附录 D)。25 项的 RVA:

```
getZhenxiInfo3             rva=0x2b476c
getZhenxiInfo4             rva=0x2a2d98
getZhenxiInfo5             rva=0x2a4760
getZhenxiInfoEnv           rva=0x28cdb0
getZhenxiInfoF             rva=0x2ad9a8
getZhenxiInfoInjection     rva=0x28df24
getZhenxiMapCheck          rva=0x291858
SideChanne                 rva=0x2b3bd4
CheckVpn                   rva=0x2aaf44
checkRiskFile              rva=0x2ac514
checkRootFromAVCLog        rva=0x2aae54
getZhenxiInfoMPNI          rva=0x298374
getZhenxiInfo2             rva=0x29aefc
getZhenxiInfoCBinder       rva=0x28c9bc
getZhenxiInfoBase          rva=0x29288c
getZhenxiInfoL             rva=0x2a8724
getZhenxiInfoO             rva=0x2be8ec
getZhenxiInfo0             rva=0x2bfdd0
getZhenxiInfoVV            rva=0x2c1850
getZhenxiInfo6             rva=0x2a5544
getZhenxiInfo7             rva=0x2a636c
getZhenxiInfoSH            rva=0x28d578
checkFromZygote            rva=0x2abcd0
checkZygisk                rva=0x2a93f8
getZhenxiLoctionCrc        rva=0x2ae064
```

`getZhenxiInfoH` 不在这 60 项表内 —— 它本身不是 native 方法,而是 Java wrapper:`getZhenxiInfoH(key) -> getPropInline(key, true)`。`getPropInline` 是混淆控制流函数,内部再进入 native `getZhenxiInfoZ(key)` fallback 或 `/dev/__properties__` 属性区解析。这是实测 60 项表缺失 `getZhenxiInfoH` 后,结合 Java 反编译确认的链路。

随后以风险项字符串和 `ReportRiskItem` 汇聚点交叉定位:

```
ReportRiskItem / build_native_ListItemBean_risk: libhunter.so+0x278658
```

动态 hook 这个汇聚点可以拿到 native 风险项标题、详情和 `LR`,例如:

```
[ReportRiskItem]
  arg1: Check Find Root In Mounts
  arg2: ... /proc/mounts->APatch /debug_ramdisk ...
ReportRiskItem this->lr: libhunter.so+0x2b4a88
```

LR = `0x2B4A88` 落在 `NativeEngine_getZhenxiInfo3 @ 0x2B476C` 内,把 UI 文案与 native 检测函数闭环。

### 1.2 动态侧

动态侧使用三类 hook:

1. **Java UI sink**:`MainActivity.n0(ListItemBean)`,观察最终展示的 title/risk/data 和 Java stack
2. **Java NativeEngine 返回值**:确认哪个 native 返回了风险 bean 或风险字符串
3. **Native sink**:`libhunter.so+0x278658`,确认 native 层上报标题和调用点 `LR`

典型动态证据:

```
[Java MainActivity.n0]
  title=Check Find Root In Mounts
  risk=Info
  data=/proc/mounts->APatch /debug_ramdisk ...

[bypass:mounts] NativeEngine.getZhenxiInfo3 -> null
```

前者证明检测命中,后者证明将该 native 返回值置空后 UI 风险项消失。

### 1.3 防崩前置:`maps_precheck_readable` unmapped hole bug

凡是可能触发 Hunter checksum、maps/RX 扫描或 ELF 段枚举路径的动态分析脚本,都应优先安装 `block_bad_precheck` hook。原因是 Hunter 的 checksum/mem scan 路径会把 maps 解析出的地址交给自己的可读性预检查 `maps_precheck_readable @ 0xC6520`,该预检查没有证明 `[addr, addr+size)` 被可读 mapping 完整覆盖；在当前 Frida 17 注入环境下,某些地址区间会跨越 unmapped hole 或不可读页,后续 NEON / 批量读取可能 SIGSEGV。

```js
function block_bad_precheck(modbase) {
    const badOnce = new Set();
    function untag(p) { return ptr(p).and(ptr("0x00ffffffffffffff")); }
    function isFullyReadable(addr, size) {
        if (size === 0) return false;
        let cur = untag(addr);
        const end = cur.add(size);
        while (cur.compare(end) < 0) {
            const r = Process.findRangeByAddress(cur);
            if (r === null) return false;
            if (!r.protection.includes("r")) return false;
            const rangeEnd = r.base.add(r.size);
            cur = rangeEnd.compare(end) < 0 ? rangeEnd : end;
        }
        return true;
    }
    Interceptor.attach(modbase.add(0xC6520), {
        onEnter(args) {
            this.p = args[0];
            this.size = args[1].toUInt32();
            this.ppp = this.context.lr.sub(modbase);
        },
        onLeave(retval) {
            if (retval.toInt32() === 0) return;
            if (!isFullyReadable(this.p, this.size)) {
                const key = untag(this.p).toString() + ":" + this.size;
                if (!badOnce.has(key)) {
                    badOnce.add(key);
                    console.log("block bad precheck", untag(this.p),
                        "size", ptr(this.size), "off", this.ppp);
                }
                retval.replace(0);
            }
        }
    });
}
```

实测拦下的越界访问片段(Pixel 6 Pro / Android 15):

```
block bad precheck 0x773acbe000 size 0x7000   off 0xc68a4
block bad precheck 0x7741a35000 size 0x1266d8 off 0xc7828
block bad precheck 0x774059e000 size 0x1000   off 0xc68a4
```

`off 0xC68A4` 位于 `sub_C687C`(`parse_elf_rx_segments` 内 ELF 文件读出后的可读性预检),`off 0xC7828` 位于 `scan_rx_segment_neon_sum @ 0xC772C`(RX 段扫描路径)。两个 LR 模式覆盖两条独立完整性检查链路的越界点 —— 这条数据反复出现在后面 §5 / §8 / §20 / §21 多条 detection 的实测中。

---

## 2. JNI 动态注册:绕过 RegisterNatives 监控

### 2.1 链路

```
HunterPreload (Zygote 预加载)
  ↓
dlopen libhunter.so
  ↓
JNI_OnLoad @ 0x2c36f8
  ├─ checkProcessTag (byte_2F3A68 & 1) 失败 → abort()
  ├─ GetEnv(JNI_VERSION_1_6), NULL → abort()
  ├─ HunterJniHelper::init(env)
  ├─ FindClass + 全局缓存 7 个类
  ├─ art_register_natives_batch(env, NativeEngine,  off_2EF1F0, 60)  ← 直接 patch ArtMethod
  ├─ art_register_natives_batch(env, ChooseUtils,   off_2EF1D8, 1)
  ├─ uname().sysname == "Unidbg" → return -1
  ├─ InitProperties
  └─ return 0x10006
```

### 2.2 静态证据

`art_register_natives_batch @ 0xA5C54` 静态伪代码(IDA 反编译还原):

```c
// libhunter.so+0xA5C54
bool art_register_natives_batch(JNIEnv *env, jclass clazz,
                                JNINativeMethod *methods, size_t count) {
    if (get_sdk_level() > 33)
        return false;                              // Android 14+ / SDK 34+ 直接放弃此路径

    for (size_t i = 0; i < count; i++) {
        jmethodID mid = env->GetMethodID(clazz, methods[i].name, methods[i].signature);
        if (!mid) {
            env->ExceptionClear();
            mid = env->GetStaticMethodID(clazz, methods[i].name, methods[i].signature);
            if (!mid) return false;
        }

        void *art_method;
        if (g_sdk_level < 30) {
            art_method = (void *)mid;              // mid 即 ArtMethod*
        } else {
            // 反射 Executable.artMethod 字段
            jobject m = env->ToReflectedMethod(clazz, mid, JNI_TRUE);
            art_method = (void *)env->GetLongField(m, g_fid_Executable_artMethod);
        }

        if (!art_method_set_native_entry(g_sdk_level, art_method, methods[i].fnPtr))
            return false;
    }
    return true;
}
```

#### 2.2.1 `art_method_set_native_entry @ 0xA4C80` 完整伪代码

```c
// libhunter.so+0xA4C80
__int64 art_method_set_native_entry(int sdk_level, void *art_method, void *fnPtr) {
    // ① 选 libart.so 路径
    std::string libart_path;
    build_libart_path(&libart_path);              // sub_1AFA80

    // ② 选 dlsym 目标符号
    const char *sym;
    if (sdk_level > 30) {
        sym = "_ZN3art11ClassLinker14RegisterNativeEPNS_6ThreadEPNS_9ArtMethodEPKv";
        // ClassLinker::RegisterNative(this, Thread*, ArtMethod*, void const*)
    } else {
        sym = "_ZN3art9ArtMethod14RegisterNativeEPKv";
        // ArtMethod::RegisterNative(void const*)
        if (!libart_dlsym(libart_path.c_str(), sym)) {
            sym = "_ZN3art9ArtMethod14RegisterNativeEPKvb";
            // ArtMethod::RegisterNative(void const*, bool)   ── Android 7/8 备选
        }
    }

    // ③ 自实现 dlsym 拿 @hide 符号(绕 libdl hook)
    void *fn = libart_dlsym(libart_path.c_str(), sym);    // sub_1A82D4
    if (!fn) return 0;
    g_art_RegisterNative_fn = fn;                          // cache @ off_2EF7C8

    // ④ 按 SDK 选择调用形式
    if (sdk_level > 30) {
        // —— Android 12+ ──
        // 取 Thread::CurrentFromGdb 函数指针(本应再调用一次拿 Thread*)
        void *thread_fp = libart_dlsym(libart_path.c_str(),
                                        "_ZN3art6Thread14CurrentFromGdbEv");
        if (!thread_fp) return 0;
        void *class_linker = get_art_class_linker(sdk_level);   // sub_A3CCC
        if (!class_linker) return 0;

        // ⚠ BUG: 第二参数 X1 应是 ((Thread*(*)())thread_fp)() 的结果,
        //        而不是 thread_fp 函数指针本身。详 §2.3。
        ((void (*)(void *, void *, void *, const void *))fn)
            (class_linker, thread_fp, art_method, fnPtr);
    } else if (sdk_level == 30) {
        // —— Android 11 ──
        // ArtMethod::RegisterNative(this=art_method, native=fnPtr)
        ((void (*)(void *, const void *))fn)(art_method, fnPtr);
    } else {
        // —— Android 10- ──
        // ArtMethod::RegisterNative(this=art_method, native=fnPtr, is_fast=true)
        ((void (*)(void *, const void *, bool))fn)(art_method, fnPtr, true);
    }

    return 1;
}
```

libart.so 路径按 SDK 选(`build_libart_path / sub_1AFA80` 静态确认):

| SDK | 路径 |
|-|-|
| ≤ 28(Android 9-) | `/system/lib64/libart.so` |
| 29(Android 10) | `/apex/com.android.runtime/lib64/libart.so` |
| ≥ 30(Android 11+) | `/apex/com.android.art/lib64/libart.so` |

dlsym 目标符号(已 demangle):

| SDK | dlsym 目标符号 | 调用形式 |
|-|-|-|
| > 30 | `art::ClassLinker::RegisterNative(art::Thread*, art::ArtMethod*, void const*)` | `RegisterNative(this, Thread*, ArtMethod*, fnPtr)` |
| == 30 | `art::ArtMethod::RegisterNative(void const*)` | `RegisterNative(this, fnPtr)` |
| < 30 | `art::ArtMethod::RegisterNative(void const*, bool)` | `RegisterNative(this, fnPtr, true)` |

#### 2.2.2 自实现 dlsym:`libart_dlsym @ 0x1A82D4`

`libart_dlsym` 不走 libdl,而是自己解析 ELF 取符号,目的有二:绕开 libdl hook;取 `@hide` 未导出符号(`ArtMethod::RegisterNative` 等并不在 libart 的 `.dynsym` 公开导出)。

```c
// libhunter.so+0x1A82D4
void *libart_dlsym(const char *path, const char *symbol) {
    void *handle = custom_dlopen(path);                   // sub_1AFF14
    if (!handle) return NULL;
    void *fn = custom_dlsym(handle, symbol);              // sub_1B00B8
    if (!fn) {
        fn = custom_dlsym_fallback(handle, symbol);       // sub_1B0720
    }
    custom_dlclose(handle);                               // sub_1B0060
    return fn;
}
```

四个 helper 的分工:

| 函数 | RVA | 作用 |
|-|-|-|
| `custom_dlopen` | `0x1AFF14` | mmap libart.so + 解析 ELF header / Program Header,建立内部 handle |
| `custom_dlsym` | `0x1B00B8` | 先查 `.dynsym`(导出符号表) |
| `custom_dlsym_fallback` | `0x1B0720` | `.dynsym` 找不到时查 `.symtab`(完整符号表,含 @hide) |
| `custom_dlclose` | `0x1B0060` | munmap + 释放 handle |

#### 2.2.3 Runtime 锚点:`get_art_class_linker @ 0xA3CCC`

ClassLinker* 需要从 Runtime 实例取。Runtime 实例本身也是 @hide 符号,通过两条路径定位:

```c
// libhunter.so+0xA3CCC(简化)
void *get_art_class_linker(int sdk_level) {
    if (g_art_class_linker) return g_art_class_linker;    // qword_2EF7C0 cache

    // 路径 1:dlsym Runtime 静态实例指针(SDK 较新版本可见)
    void **inst = libart_dlsym(libart_path, "_ZN3art7Runtime9instance_E");

    // 路径 2:dlsym 任意一个能拿到 Runtime 内部偏移的符号
    if (!inst) {
        inst = libart_dlsym(libart_path,
                "_ZN3art17SmallIrtAllocator10DeallocateEPNS_8IrtEntryE");
    }
    if (!inst) return NULL;

    void *runtime = *inst;
    // 按 SDK 偏移读 Runtime->class_linker_(每个版本偏移不同)
    void *class_linker = *(void **)((char *)runtime + class_linker_offset(sdk_level));
    g_art_class_linker = class_linker;
    return class_linker;
}
```

全局缓存:`g_art_class_linker @ qword_2EF7C0`,`g_art_RegisterNative_fn @ off_2EF7C8`,`g_fid_Executable_artMethod @ qword_2EF7D0`(SDK ≥ 30 反射拿 `Executable.artMethod` jfieldID 的缓存)。

### 2.3 已确认 BUG:SDK 31-33 路径 `Thread*` 参数错传

#### 2.3.1 完整汇编上下文

`art_method_set_native_entry` 内 SDK > 30 分支调 `ClassLinker::RegisterNative` 的完整指令序列(IDA MCP 实读 `sub_A4C80` 在 `0x0a5224..0x0a5254` 区段):

```asm
;; libhunter.so, sub_A4C80 内部
0x0a5224  ADRL X1, aZn3art6thread1           ; "_ZN3art6Thread14CurrentFromGdbEv"
0x0a522c  BL   sub_1A82D4                    ; libart_dlsym(libart_path, "..CurrentFromGdb..")
0x0a5230  MOV  X21, X0                       ; X21 ← libart_dlsym 返回值 = 函数指针,未调用
0x0a5234  ADD  X0, SP, #0x1B0+var_170
0x0a5238  BL   std::string::~string()        ; 析构 dlsym 调用用的临时 std::string
0x0a523c  CBZ  X21, loc_A5278                ; null 检查
0x0a5240  BL   sub_A3CCC                     ; get_art_class_linker;X0 ← class_linker
0x0a5244  CBZ  X0,  loc_A5624                ; class_linker null 检查
0x0a5248  LDP  X2, X3, [SP,#0x1B0+var_188]   ; X2 ← art_method,X3 ← fnPtr(从栈上一次性 LDP)
0x0a524c  MOV  X1, X21                       ; X1 ← CurrentFromGdb 函数指针(本应是 Thread*)
0x0a5250  LDR  X8, [SP,#0x1B0+var_190]       ; X8 ← g_art_RegisterNative_fn(从栈上加载缓存)
0x0a5254  BLR  X8                            ; ClassLinker::RegisterNative(
                                             ;     X0=class_linker,
                                             ;     X1=函数指针冒充 Thread*,
                                             ;     X2=art_method,
                                             ;     X3=fnPtr)
```

12 条指令直接从 IDA MCP 实读拷贝,X1 错传由 `0x0a524c MOV X1, X21` 直接证明 —— X21 来源是 `0x0a522c BL libart_dlsym` 的返回值,中间只经过 `MOV X21, X0`(`0x0a5230`)和 null 检查(`0x0a523c`),**从未被调用**,直接作为实参传给了 `ClassLinker::RegisterNative` 的第二个参数槽位。

X2/X3 是从栈上一次性 `LDP` 拿到的(`art_method`、`fnPtr`,在函数早期被存进栈),X8(`RegisterNative` 函数指针缓存)也是从栈上 `LDR` 拿到的。X0 = class_linker 直接来自上一条 `BL sub_A3CCC` 的返回。**4 个参数装载位置全部可见**。

#### 2.3.2 BUG 性质分析

`ClassLinker::RegisterNative(this, Thread *self, ArtMethod *method, const void *native)` 的第二个参数语义是**当前线程的 `Thread*` 对象**,需要通过调用 `Thread::CurrentFromGdb()` 拿到 —— 这是 ART 内部的 ThreadLocal 访问器,无参 → 返回 `Thread*`。

按 §2.3.1 的反汇编:`0x0a5230 MOV X21, X0` 把 `libart_dlsym` 返回的函数指针存到 X21,之后**没有 `BLR X21` 这一步**(它本应把函数指针当函数调一次,把返回值即真正的 `Thread*` 重新放入 X0),直接在 `0x0a524c MOV X1, X21` 把 X21(仍是函数指针)装入实参槽位。

最终 `0x0a5254 BLR X8` 调用 `ClassLinker::RegisterNative` 时,X1 是一个指向 `libart.so .text` 段的函数指针,而 callee 期望它指向堆上的 `art::Thread` 对象。Android 12+ 上一旦实际进入这个分支,可以确定的是 ART 内部函数会收到错误的 `self` 实参；后续影响取决于 `ClassLinker::RegisterNative` 在对应 Android 版本中的具体实现:

- 如果 `ClassLinker::RegisterNative` 内部解引用 `self` 字段,例如读取 ThreadId/StateAndFlags、访问 TLS/锁/状态字段,就会把 `libart.so .text` 中的函数地址误当作 `art::Thread` 对象使用,可能立即崩溃,也可能在后续校验或状态更新中表现为 ART 状态异常。
- 如果该路径暂时只传递或记录 `self` 而不立即读写字段,静态证据仍只能证明错误 `Thread*` 被传入 ART 内部函数；是否延迟触发崩溃或状态异常,需要对应 Android 版本的 `ClassLinker::RegisterNative` 实现或运行时复现来确认。

#### 2.3.3 与"SDK > 33 显式禁用"的一致性

这与 §2.2 `art_register_natives_batch` 入口处的 `if (get_sdk_level() > 33) return false` 形成一致解释:作者发现新 Android(14+)走此路径不稳,在批量入口直接挡掉,**但 SDK 31-33 区间仍会进入此分支** —— 没补的实现仍带 bug。

实测设备 SDK=35,走的是 batch return false → 回落到 `env->RegisterNatives` 路径,所以本设备没踩到 bug,但代码层面 BUG 还在。`verify_register_natives.js` 在 libart 的 `RegisterNatives` 入口落 hook 间接印证 SDK=35 回落路径生效。

### 2.4 动态证据:60 项表运行时枚举

直接读 `libhunter.so + 0x2EF1F0` 处的 `JNINativeMethod` 表:

```js
const NATIVE_METHODS_TABLE = 0x2EF1F0;
const COUNT = 60;
const ENTRY_SIZE = 24;                   // sizeof(JNINativeMethod) on arm64
for (let i = 0; i < COUNT; i++) {
    const entry = base.add(NATIVE_METHODS_TABLE + i * ENTRY_SIZE);
    const namePtr = entry.readPointer();
    const sigPtr  = entry.add(8).readPointer();
    const fnPtr   = entry.add(16).readPointer();
    const name = namePtr.readCString();
    const sig  = sigPtr.readCString();
    console.log(`#${i} ${name} ${sig} rva=${fnPtr.sub(base)}`);
}
```

实测输出关键行(完整 25 个 detection):

```
#02  getZhenxiInfo5             (Landroid/content/Context;)Lcom/zhenxi/hunter/bean/ListItemBean;  rva=0x2a4760
#13  getZhenxiInfo3             ()Lcom/zhenxi/hunter/bean/ListItemBean;                           rva=0x2b476c
#25  getZhenxiLoctionCrc        ()Ljava/util/HashMap;                                             rva=0x2ae064
#45  getZhenxiMapCheck          ()Lcom/zhenxi/hunter/bean/ListItemBean;                           rva=0x291858
#50  checkRiskFile              ()Lcom/zhenxi/hunter/bean/ListItemBean;                           rva=0x2ac514
#53  CheckVpn                   ()Lcom/zhenxi/hunter/bean/ListItemBean;                           rva=0x2aaf44
#56  checkRootFromAVCLog        ()Lcom/zhenxi/hunter/bean/ListItemBean;                           rva=0x2aae54
#59  SideChanne                 ()Ljava/lang/String;                                              rva=0x2b3bd4
... (其余 detection 见 §1.1)
```

### 2.5 静态/动态交叉验证

| 静态结论 | 动态印证 | 状态 |
|-|-|-|
| `off_2EF1F0` 起 60 项 `JNINativeMethod` 表 | 运行时枚举 60 项全部解析成功 | ✓ |
| 每项 24 字节 `{name*, sig*, fn*}` | 60 项 name/sig 都是合法字符串,fn 都在 libhunter 范围内 | ✓ |
| `getZhenxiInfo5` 是 idx=2 | 实测 #02 = `getZhenxiInfo5` | ✓ |
| `getZhenxiLoctionCrc` 是 idx=25,RVA=0x2AE064 | 实测 #25 = `getZhenxiLoctionCrc rva=0x2ae064` | ✓ |
| `CheckVpn` 是 idx=53 | 实测 #53 = `CheckVpn` | ✓ |
| `getZhenxiInfoH` 不通过 batch 注册 | 实测 60 项表无 `getZhenxiInfoH` 条目 | ✓(反常发现) |
| SDK > 33 路径回落 RegisterNatives | hook libart `RegisterNatives` 可看到 hunter 注册(SDK=35 环境) | 间接 ✓ |

`verify_register_natives.js` 在 libart `RegisterNatives` 入口落 hook 也确认了:SDK=35 环境下 hunter 的注册走标准 RegisterNatives 路径( SDK > 33 时 art_register_natives_batch 在入口处返回 false，上层因此 fallback 到标准 env->RegisterNatives 注册路径)。

### 2.6 bypass 依据

在 SO 层直接 `Interceptor.replace` 25 个 detection 入口:

```js
const cb = new NativeCallback(function () {
    return ptr(0);                              // 返回 NULL jobject
}, 'pointer', ['pointer', 'pointer']);
Interceptor.replace(methods['getZhenxiInfo3'].fn, cb);
```

实测 25 个 detection 全部 replace 成功:

```
[null] getZhenxiInfo3             rva=0x2b476c
[null] getZhenxiInfo4             rva=0x2a2d98
[null] getZhenxiInfo5             rva=0x2a4760
... (共 25 行)
[null] checkZygisk                rva=0x2a93f8
[crc]  getZhenxiLoctionCrc        rva=0x2ae064
[+] native bypass installed: 25 ok, 1 missing
```

`1 missing` 是 `getZhenxiInfoH` —— 实测验证了它不在 batch 表里的静态结论。Java 层补 `NativeEngine.getZhenxiInfoH` 拦截兜底。

---

## 3. 安全 syscall 跳板:借 linker SVC 绕开 libc 监控

### 3.1 链路

```
safe_syscall_via_trampoline(sysno, ...)             @ 0x248cc4
  ├─ use_secure_syscall_trampoline_enabled()        @ 0x1b2288   总开关
  ├─ InitSecureTrampolinePage()                     @ 0x1b22c0   惰性 init, mutex 保护
  │     ├─ FindLinkerSyscallAddr("/linker64", 93)   @ 0x1b1c9c
  │     │     在 linker64 r-x 段扫指纹序列
  │     │     返回 SVC #0 那一条指令的地址(不是 stub 入口!)
  │     ├─ mmap RWX → 拷 48B 模板 → mprotect R-X
  │     └─ NEON 算 baseline checksum → ctx[+0x28]
  ├─ get_trampoline_id_tag()                        @ 0x1b21b4
  │     从 0x2F09E8 处读 std::string "runtime_syscall_code"
  ├─ calc_additive_checksum(page, 48)               @ 0x261f14
  │     NEON 字节累加和,与 ctx[+0x28] 基准比对;失配重建,再失配 exit(9)
  └─ ((fn)page)(sysno, a1..a6)                       跳板执行 → linker64 内裸 SVC #0
```

### 3.2 静态证据

#### 3.2.1 48 字节跳板模板

`secure_syscall_trampoline_template{,_q1,_q2}` 在 `.rodata` @ `0x651FC..0x6522C`,字节级解读:

```
fd 7b be a9   STP   X29, X30, [SP,#-0x20]!         ; 入栈
e8 03 00 aa   MOV   X8,  X0                        ; X8 = sysno(C 调用者把 sysno 当首参)
e0 03 01 aa   MOV   X0,  X1                        ; 参数左移一格
e1 03 02 aa   MOV   X1,  X2
e2 03 03 aa   MOV   X2,  X3
e3 03 04 aa   MOV   X3,  X4
e4 03 05 aa   MOV   X4,  X5
e5 03 06 aa   MOV   X5,  X6
91 00 00 58   LDR   X17, [PC,#+0x10]               ; 读 page+0x30 处的 SVC #0 地址
20 02 3f d6   BLR   X17                            ; 跳 linker64 内裸 SVC #0
fd 7b c2 a8   LDP   X29, X30, [SP],#0x20           ; 收尾
c0 03 5f d6   RET
[+0x30: .quad <linker SVC#0 addr>]                 ; 由 InitSecureTrampolinePage 填
```

#### 3.2.2 `FindLinkerSyscallAddr` 指纹序列

这一步的目的不是调用 `linker64` 的某个完整函数,而是从 `linker64` 的可执行段里找到一条现成的 `SVC #0` 指令。ARM64 Linux syscall 的约定是:

```
X8     = syscall number
X0-X5  = syscall 参数
SVC #0 = 进入内核执行 syscall
```

Hunter 自己的跳板页已经先把调用者传入的 `sysno` 放进 `X8`,并把后续参数顺移到 `X0-X5`:

```
safe_syscall_via_trampoline(sysno, a1, a2, a3, a4, a5, a6)
  -> X8 = sysno
  -> X0 = a1, X1 = a2, X2 = a3, ...
  -> BLR <linker64 内的 SVC #0 地址>
```

因此 `FindLinkerSyscallAddr` 只需要找一个可信的 `SVC #0` 地址。它在 `/proc/self/maps` 中筛 pathname 含 `/linker64`、权限 r-x 的段,在该 .text 内 4 字节步进扫描,匹配 bionic syscall stub 的标准展开:

| 偏移(相对 n12) | 字节模式 / 等价反汇编 |
|-|-|
| `n12-12` | `MOVZ/MOVN W8, #imm`,要求 `imm == 93`(mask `(v11 & 0x1F80001F) == 0x12800008` 锁定 Rd=W8) |
| `n12-8` | `0xD4000001` = `SVC #0` |
| `n12-4` | `0xB140041F` = `CMN X0, #0x1000` |
| `n12+0` | `0xDA809400` = `CSINV X0, X0, X0, LS` |
| `n12+4` | 与 `0xFF000010` 与后 `== 0x54000000` —— `B.cond` |
| `n12+8` | `0xD65F03C0` = `RET` |

匹配后**返回 `start + (n12-8)`,即 SVC #0 那一条指令的地址**,而非 `MOV W8` 的 stub 入口。

为什么返回 SVC 而非 stub 入口:跳板自己已经把 `X8` 设为调用者指定的 syscall number。例如 `safe_syscall_via_trampoline(56, ...)` 进入跳板后,`X8=56`,表示要执行 `openat`。如果跳到 stub 入口的 `MOVZ W8, #93`,刚设置好的 `X8=56` 会被覆盖成 `93`,调用就会变成 `exit`。直接跳到下一条 `SVC #0`,才能保留 Hunter 自己设置的 `X8`,借用 linker 这条 SVC 指令发起任意 syscall。

返回链也依赖这个 stub 后半段。跳板页用 `BLR X17` 跳到 `SVC #0`,所以 `LR/X30` 被设置为跳板页中 `BLR X17` 的下一条指令。内核完成 syscall 后,用户态继续从 `SVC #0` 后面的 `CMN/CSINV/B.cond/RET` 执行；最后 linker stub 的 `RET` 使用这个 `LR/X30` 返回到 Hunter 跳板页,跳板页再恢复栈帧并 `RET` 回调用者。

为什么用 sysno=93:`93 = SYS_exit`(ARM64 Linux)。本环境 linker64 中存在匹配该 sysno 的标准 syscall stub,Hunter 选择它作为 SVC 指令定位锚；跨 Android / bionic 版本是否始终稳定,应以目标系统 linker64 实测扫描为准。

#### 3.2.3 `g_secure_trampoline_ctx` 结构

| 偏移 | 字段 | 写入处 | 读取处 |
|-|-|-|-|
| `+0x00` | `void *page` | `InitSecureTrampolinePage` mmap 返回 | `safe_syscall_via_trampoline` `*v3` |
| `+0x08` | `size_t length = 48` | `*(_QWORD *)(v46 + 8) = 48` | `v3[1]` |
| `+0x10` | `std::string id_tag` | `std::string::operator=(v47, v52)` | `v3 + 2` |
| `+0x28` | `uint64_t baseline_sum` | `*(_QWORD *)(g_secure_trampoline_ctx + 40) = v39` | `v3[5]` |
| `+0x30` | `uint8_t initialized = 1` | `*(_BYTE *)(g_secure_trampoline_ctx + 48) = 1` | — |

#### 3.2.4 `id_tag` 字符串溯源

字面量在 `0x5dd44`,全局构造器 `sub_1B3088 @ 0x1b3088` 通过:

```c
strcpy(&dest_@0x2F09E8, "(runtime_syscall_code");
```

写入全局 `dest_`(即 `xmmword_2F09E8` / `src_0` 一对地址,对应 `get_trampoline_id_tag` 读源)。**首字符 `(` (0x28) 不是真字符**,而是 libc++ SSO 控制字节:低位 0 标记 SSO 模式,高 7 位 `0x14 = 20` 即字符串长度。作者把 22 字节(header + 20 字符 + `\0`)预编译成一个 C 字符串,strcpy 一次落地一个合法 std::string。

### 3.3 动态证据

#### 3.3.1 被动取证(`verify_4_5_passive.js`)

`verify_4_5_passive.js` 只挂 `InitSecureTrampolinePage` onLeave,单次取证后即刻 detach。运行后 ctx 字段实测值:

| 字段 | 实测值 | 静态推断 |
|-|-|-|
| `ctx` 指针 | `0xb40000752359c1b0`(arena 分配,带 MTE tag) | — |
| `ctx[+0x00] page` | `0x773e804000` | 与 `.rodata` 模板起始地址匹配位置 ✓ |
| `ctx[+0x08] length` | `48` | ✓ |
| `ctx[+0x10] id_tag` | `"runtime_syscall_code"`(20 字节,libc++ SSO) | 字面值首次确认 ✓ |
| `ctx[+0x28] baseline_sum` | `0x14E0` | 与 JS 端朴素累加结果一致 ✓ |
| `ctx[+0x30] initialized` | `1`(byte) | ✓ |
| page 权限 | `r-x` | ✓ |
| page 首 48B 与 `.rodata` 模板逐字节对比 | 100% 一致 | ✓ |
| `page[+0x30]` 缓存 SVC 地址 | `0x7741a00694` | — |

#### 3.3.2 `page[+0x30]` 反查 linker stub

用缓存地址被动重建 §3.2.2 的指纹序列:

| 偏移 | 实测指令 | 期望 |
|-|-|-|
| `@stub-4` | `0xd2800ba8` = `MOVZ W8, #93, LSL #0` | `MOVZ/MOVN W8, #93` ✓ |
| `@stub` | `0xd4000001` = `SVC #0` | `0xD4000001` ✓ |
| `@stub+4` | `0xb140041f` = `CMN X0, #0x1000` | `0xB140041F` ✓ |
| 所在段 | `0x77419ee000-0x7741b0e000 r-x /apex/com.android.runtime/bin/linker64` | r-x ✓ |

#### 3.3.3 累加和自检三向一致

```
calc_additive_checksum(page=0x773e804000, len=48)  →  0x14E0  (静态推算)
Frida JS 脚本在运行时读取 page 前 48B 后做朴素 byte sum → 0x14E0  (动态)
ctx[+0x28] baseline_sum 字段                       →  0x14E0  (ctx 读取)
```

三处一致 ✓。

#### 3.3.4 调用面分布(`verify_4_5_7_call_surface_v2.js`,30s 采样)

为不触发 hunter 自检,v2 脚本只在 `/apex/.../linker64` 内的 SVC #0(由 `ctx.page[+0x30]` 缓存的地址)落观察点,LR 严格等于 `ctx.page + 0x28` 才计入。共 **5300+ 次** 跳板调用样本:

| sysno | 名称 | 静态 callsite 数 | 静态 % | 运行时次数 | 运行时 % |
|-|-|-|-|-|-|
| 78 | `readlinkat` | 6 | 4.9% | **4251** | **80.2%** |
| 56 | `openat` | 2 | 1.6% | 461 | 8.7% |
| 57 | `close` | 1 | — | 456 | 8.6% |
| 63 | `read` | 1 | — | 76 | 1.4% |
| 207 | `recvfrom` | 1 | — | 28 | 0.5% |
| 62 | `lseek` | 1 | — | 12 | 0.2% |
| 101 | `nanosleep` | 1 | — | 12 | 0.2% |
| 43 | `statfs` | 2 | 1.6% | 2 | 0.04% |
| 80 | `fstat` | 1 | — | 1 | 0.02% |
| 160 | `uname` | 1 | — | 1 | 0.02% |
| 129 | **`kill`** | **102** | **83.6%** | **0** | **0%** |
| 167 | `prctl` | 1 | — | 0 | — |
| 9 | `lgetxattr` | 1 | — | 0 | — |
| 462 | `mseal` | 1 | — | 0 | — |

### 3.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| S1 | 跳板页 48 字节 | ctx[+0x08]=48,且 page 首 48B 与 `.rodata` 模板一致 | ✓ |
| S2 | id_tag 字符串 `"runtime_syscall_code"` | ctx[+0x10] SSO 解码 = 字符串字面值 | ✓ |
| S3 | id_tag SSO 控制字节首字 `0x28`(长度 20) | 静态 `strcpy(...,"(runtime_syscall_code")` + ctx 实读 | ✓ |
| S4 | baseline = NEON byte sum(48B) | 静态推算 / JS 朴素累加 / ctx 字段三向一致 = 0x14E0 | ✓ |
| S5 | `page[+0x30]` 保存 linker64 SVC #0 地址 | 实测 0x7741a00694,落在 `linker64` r-x 段 | ✓ |
| S6 | 该地址前一条 = `MOVZ W8, #93` | 实测 `@stub-4 = 0xd2800ba8 = MOVZ W8,#93` | ✓ |
| S7 | sysno 静态分布 `kill` 占 83.6% | 运行时 `kill` 0%(检测路径未失败,自杀分支未触发) | 结构性错位 ✓ |
| S8 | sysno 运行时主稳态:readlinkat + openat + close | 三者占运行时 97.5% | ✓ |
| S9 | `recvfrom(sockfd, buf, 0x2000, 0, NULL, NULL)` | sockfd=197 / len=8192 / flags=0,28 次 | ✓ |
| S10 | `anti_ptrace_poll_loop` 用 `nanosleep` 节拍 | 12 次,间隔规整 | ✓ |
| S11 | `statfs("/system") / statfs("/vendor")` | 实测 statfs 路径完全对得上 | ✓ |
| S12 | `readlinkat` 用于 fd → 路径解析 | 80.2%,样本均为 `/proc/.../fd/<N>` | ✓ |

### 3.5 静态 vs 运行时分布解读

静态 callsite 数与运行时调用数**测量的是两件不同的事**:

- **静态 callsite 数**:hunter 代码里**可能触发**该 sysno 的代码位置数量。`kill` 有 102 个 callsite,因为每条检测路径的失败分支都各写一次 SIGKILL —— 这只代表"分散冗余",不代表频繁
- **运行时命中数**:在**当前(检测未触发、无 Frida 异常告警)** 这种"clean 路径"下,hunter 实际跑过的 syscall 流量分布

本轮 `kill` 0 次说明当前观察窗口内没有进入 SIGKILL 分支。结合 Frida 线程扫描返回 0、ReportRiskItem 未出现 Frida 命中,可作为"本轮未被 Frida 自杀分支识别"的辅助证据；但不能单独证明所有 SIGKILL 路径均不可达。

未观察到的 4 个 sysno 各有原因:

| sysno | 未触发的原因 |
|-|-|
| `kill (129)` | 本轮检测路径未进入自杀分支；只能说明当前触发条件/观察窗口下未命中 kill 路径 |
| `prctl (167) option=31` | 极大概率在 `.init_array` 阶段就执行完了,运行时观察窗口起点已晚于它 |
| `mseal (462)` | 同上,一次性硬化保护,运行时不重复 |
| `lgetxattr (9)` | 路径 `"security.selinux"` 的 SELinux 标签读取,与具体被检测文件触发条件挂钩 |

### 3.6 命名 syscall 包装器

`0x1AFE4C..0x1AFEF8` 一组 7 个小函数(0x18~0x24 字节),每个把固定 sysno 转发到 `safe_syscall_via_trampoline`,等价于"安全版 libc 子集":

| 包装器 | 地址 | sysno | 等价 |
|-|-|-|-|
| `ssyscall_openat` | `0x1afe4c` | 56 | `openat(dirfd, path, flags, mode)` |
| `ssyscall_openat_atfdcwd` | `0x1afe70` | 56 | `openat(AT_FDCWD=-100, path, flags, mode)` |
| `ssyscall_read` | `0x1afe94` | 63 | `read(fd, buf, count)` |
| `ssyscall_lseek` | `0x1afeac` | 62 | `lseek(fd, offset, whence)` |
| `ssyscall_close` | `0x1afec4` | 57 | `close(fd)` |
| `ssyscall_nanosleep` | `0x1afedc` | 101 | `nanosleep(req, rem)` |
| `ssyscall_readlinkat` | `0x1afef8` | 78 | `readlinkat(dirfd, path, buf, sz)` |

后续 detection 中大量敏感文件读取会走这 7 个 ssyscall 包装器,尤其是 `openat/read/lseek/close/readlinkat` 组合；但并非所有 `/proc`、maps、进程枚举和命令输出路径都走跳板。完整 I/O 监控需要同时覆盖跳板、libc/stdio、`popen`、`opendir/readdir` 等路径。

### 3.7 对抗效果总结

| 对抗目标 | 跳板路径如何破坏 |
|-|-|
| `Interceptor.attach(Module.findExportByName('libc.so', 'syscall'))` | 完全不调用 `libc::syscall`,Hook 永不触发 |
| 对具名 syscall 包装(`openat`/`read`/`getdents64` …)做 PLT/inline-hook | 同上,直接走 linker 段内的裸 SVC |
| 在 `safe_syscall_via_trampoline` / 跳板页头 16~20 字节做 inline-hook | 每次调用前 `calc_additive_checksum` 重算 48B 累加和与 `baseline_sum` 比对,失配即重建,再失配 `exit(9)` |
| 重建跳板时假冒身份 | `get_trampoline_id_tag` 与 `ctx[+0x10]` 串比对,身份不符即销毁重建 |
| 在初始化阶段 hook `fopen`/`fgets` 干扰 maps 解析 | 时序上 hunter `JNI_OnLoad` 极早(Zygote 预加载阶段),通常先于第三方 hook 运行 |

明显**不在**跳板列表里的:`write`、`mmap`、`mprotect`、`getdents64`、`newfstatat`(79)。这些路径要么走 libc(可被 hook 但不致命),要么内联在调用方。**做完整 syscall 监控不能只 hook 跳板入口**。

---

## 4. 风险项汇聚点 `build_native_ListItemBean_risk`

### 4.1 函数定位

```
libhunter.so+0x278658
size 0x8EC
被 22 个 caller 函数 × 83 个 callsite 调用
```

该函数内部引用:

```
com/zhenxi/hunter/bean/ListItemBean
```

### 4.2 静态证据:函数签名

Hex-Rays 把 OLLVM 平坦化后的 `build_native_ListItemBean_risk` 错认为 1 参函数,真实签名 6 个参数(对每个 callsite 反汇编核对一致):

```c
void build_native_ListItemBean_risk(
    JNIEnv*       env,          // X0
    std::string*  title,        // X1 — 栈上 std::string,由 sub_2447A8(out, const char* lit) 构造
    std::string*  detail,       // X2 — 同 X1
    int           risk,         // W3 — 0 / 1
    int           Type,         // W4 — 1..4 类别
    int           ShowPriority  // W5 — 0..11 子优先级
);
```

`sub_2447A8` 的作用是 `std::string::__init_from_cstr(out, lit)`。用 SSO/long 双形式自适应读法:

```js
function readStdString(p) {
    const firstByte = p.readU8();
    if ((firstByte & 1) === 0) {                  // SSO 短串
        const size = firstByte >> 1;
        if (size <= 0) return '';
        return p.add(1).readUtf8String(size);
    }
    const size = p.add(8).readU64().toNumber();   // long 形式
    const dataPtr = p.add(16).readPointer();
    return dataPtr.readUtf8String(size);
}
```

### 4.3 静态证据:W3 / W4 / W5 enum 分布

83 个 callsite 全部静态扫一遍:

| 字段 | 实测分布 | 推断含义 |
|-|-|-|
| **W3**(`risk`) | `0` × 66(80%) / `1` × 17(20%) | `isDeadly` boolean。`1` 几乎只出现在严重路径:APK 签名失败 / Find Others Process / file lib error / Linker hooked+kill。但 `W3=0 ≠ 非高危` —— `InfoF` 的 `checkLibCheckSum` W3=0 但 UI 是 Deadly,说明 W3 不是 UI 的 risk 等级,而是 native 侧是否标记 deadly 上报 |
| **W4**(`Type`) | `3` × 44 / `1` × 17 / `2` × 15 / `4` × 7 | 对应 Java 端 `FB.a/b/c/d` 类常量。`1/4` 偏 Info,`2/3` 偏 Risk |
| **W5**(`ShowPriority`) | `0/1/3/4/6/7/8/9/10/11` 都有 | detection 子类别 ID,与 caller 强相关 |

W5 子类别归纳(从 caller × W5 推):

| W5 | 类别 | 主要 caller |
|-|-|-|
| 0 | misc / 杂项 | `CheckVpn`, `MPNI`, `checkFromZygote`, `Env`, `MapCheck`, `Base` 部分 |
| 1 | Root mount | `Info3`, `checkRootFromAVCLog` |
| 3 | APK 签名 / Maps Hide / Base 检测 | `Info2`, `sub_2A1C38`, `Base` 部分 |
| 4 | Process / File lib / Binder | `Info4`, `Info0`, `CBinder`, `VV` |
| 6 | Library checksum | `InfoF` |
| 7 | `Info7` | `Info7` |
| 8 | Frida 检测 | `Info5`(gum-js-loop / gmain) |
| 9 | `Info6` | `Info6` |
| 10 | Linker hook / Risk file | `InfoL`, `checkRiskFile` |
| 11 | Simulator 检测 | `InfoO` |

`InfoBase` 19 callsite 跨多个 W5,因为它是"全家桶":Linker Hook / Magisk / Mount / Seccomp / Signal / Uname 等多类检测打包在一个 JNI 入口里。

### 4.4 静态证据:22 caller × 83 callsite 完整字典

每条 callsite 的 title/detail 字符串候选源自该 callsite **前 ≤80 条**指令内的 `ADRL/ADR → C 字符串`。粗体为最可能的 title;`<dyn>` 表示纯动态拼接:

| Caller | callsite | (W3, W4, W5) | 关键字面量 |
|-|-|-|-|
| `CheckVpn` | `0x2ab014` | (0, 1, 0) | "tun" "ppp" "pptp" **"Find Vpn Native"** |
| `checkFromZygote` | `0x2ac0f8` | (0, 1, 0) | **"Zygote Check Find Risk Mark"** |
| `checkRiskFile` | `0x2ace44` | (1, 2, 10) | **"Find Risk File"** + 25 条 `/data/local/tmp/*` 路径 |
| `checkRootFromAVCLog` | `0x2aaec4` | (0, 1, 1) | **"Find Root File In Sniff"** |
| `checkZygisk` | `0x2a9690` | (0, 2, 0) | `<dyn>` |
| `getZhenxiInfoCBinder` | `0x28cd08` | (0, 3, 4) | **"find system server hook"** |
| `getZhenxiInfoEnv` | `0x28d3a4` | (0, 4, 0) | **"Get Env Info"** |
| `getZhenxiInfoMPNI` | `0x2994f4` | (0, 1, 0) | "/oat/arm64/" **"Find Mark ELF"** |
| `getZhenxiInfoVV` | `0x2c2854` | (0, 3, 4) | `<dyn>` |
| `getZhenxiInfo3` × 7 | `0x2b490c..0x2b4ed4` | (0, 1, 1) | "Check Find Root In Linker" / **"Check Find Root Permission"** / **"Find Root Mark In Mountinfo"** |
| `getZhenxiInfo4` × 4 | `0x2a3f30..0x2a43f8` | (0 或 1, 3 或 4, 4) | **"Find Others Process"** + "find other process" + "ps error" |
| `getZhenxiInfo5` × 3 | `0x2a47f4 / 0x2a5204 / 0x2a5470` | (0, 2, 8) | **"Find Frida Mark"** + "gum-js-loop" / "gmain" / `<dyn>` |
| `getZhenxiInfo6` × 2 | `0x2a6084 / 0x2a6294` | (0 或 1, 2 或 3, 9) | `<dyn>` |
| `getZhenxiInfo7` × 2 | `0x2a65ec / 0x2a662c` | (0 或 1, 3, 7) | `<dyn>` |
| `getZhenxiInfoF` × 8 | `0x2ada3c..0x2adf74` | (0, 3 或 4, 6) | **"checkLibCheckSum"** / **"checkLinkerCheckSum"** |
| `getZhenxiInfoL` × 2 | `0x2a87b8 / 0x2a91c8` | (0 或 1, 3, 10) | **"Find Linker Is Hook"** / **"Check Linker Crc Error"** |
| `getZhenxiInfoO` × 5 | `0x2bec24..0x2bf71c` | (0, 2, 11) | **"Find Simulator OpCode Mark!"** / **"Find Simulator Env Mark!"** / **"Find Simulator Mount Mark!"** |
| `getZhenxiInfo0` × 6 | `0x2c00d4..0x2c15d8` | (0 或 1, 3, 3 或 4) | "Insufficient permissions" / **"Check App Sign Error From Path Lib"** / **"Mem Find Mark"** |
| `getZhenxiInfo2` × 11 | `0x29d6c0..0x2a0304` | (0 或 1, 3, 3) | **"HunterCheckApkSignError"** + 11 种子原因(详 §18) |
| `getZhenxiInfoBase` × 19 | `0x292e18..0x2952a4` | (0, 1/2/3, 多种) | **"Linker Find Hook Mark"** + "lsposed" / "zygisk" / **"Find Prop Modify Mark"** / **"Find Hook Mark"** / **"Base Check Inline Flag"** / **"Find Mnt Mark"** / **"Find Magisk Modules Mark"** / **"Seccomp Check Arch Find Mark"** / **"Check Signal Not Match"** / **"Check Uname Spoofing"** |
| `getZhenxiMapCheck` × 3 | `0x2923e8 / 0x292434 / 0x2924b4` | (0, 2 或 3, 0) | **"libart.so piecewise ,memory is not legal"** / **"find libart.so hooked"** |
| `sub_2A1C38` × 2 | `0x2a2c20 / 0x2a2c68` | (0, 3, 3) | **"Check Maps Find Hide"** |

### 4.5 动态证据:hook `0x278658` 闭环输出

`js/hook_report_risk_precheck.js` 在 `0x278658` 落 hook:

```js
Interceptor.attach(base.add(0x278658), {
    onEnter: function (args) {
        this.title  = readStdString(args[1]);
        this.detail = readStdString(args[2]);
        this.lrOff  = this.context.lr.sub(base);
        console.log('[ReportRiskItem]');
        console.log('  arg1:', this.title);
        console.log('  arg2:', this.detail);
        console.log('ReportRiskItem  this->lr:', this.lrOff);
    }
});
```

实测输出片段(`/proc/mounts` APatch 命中):

```
[ReportRiskItem]
  arg1: Check Find Root In Mounts
  arg2: com.zhenxi.hunter:hunter_main_process
/proc/mounts->APatch /debug_ramdisk tmpfs rw,seclabel,relatime 0 0
ReportRiskItem this->lr: libhunter.so+0x2b4a88
```

### 4.6 静态/动态交叉验证(闭环操作)

**对回方法**:`this.context.lr - 4` = 静态 callsite 的精确 RVA(LR 是 `BL build_native_ListItemBean_risk` 之后下一条指令的地址,所以 `lr - 4` 即 callsite)。

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| C1 | 函数 size 0x8EC,被多 caller 调用 | 30s 实测打印 N 条 `[ReportRiskItem]` 来自不同 lr_offset | ✓ |
| C2 | 函数签名 6 参,X1/X2 是 std::string* | readStdString(args[1]) 拿到合法字符串("Check Find Root In Mounts" 等) | ✓ |
| C3 | callsite `0x2b4a88-4 = 0x2b4a84` 位于 `getZhenxiInfo3 @ 0x2B476C` 内部 | 实测 lr=0x2b4a88,该 callsite 静态字面量含 "Check Find Root In Mounts" | ✓ |
| C4 | callsite `0x2924b8` 位于 `getZhenxiMapCheck @ 0x291858` 内 size==0x1000 分支 | 实测 lr=0x2924b8,arg1="find libart.so hooked 0" | ✓ |
| C5 | callsite `0x28d3a4` 位于 `getZhenxiInfoEnv @ 0x28CDB0` 内 | 实测 lr=0x28d3a8,arg1="Get Env Info" | ✓ |
| C6 | callsite `0x2a3f6c` 位于 `getZhenxiInfo4 @ 0x2A2D98` 内 | 实测 lr=0x2a3f6c,arg1 含 "Find Others Process" | ✓ |
| C7 | callsite `0x2ada40` 位于 `getZhenxiInfoF @ 0x2AD9A8` 内 checkLibCheckSum 分支 | 实测 lr=0x2ada40,arg1="检测到libart.so被修改" | ✓ |

闭环对回成功:每条 `[ReportRiskItem]` 输出都能通过 `lr - 4` 反查到 §4.4 字典里精确的 caller × callsite,且 `arg1` 命中静态候选字面量。`arg2` 是动态上下文(具体路径/线程名/接口名),静态字典里没有,这部分实测最有取证价值。

### 4.7 bypass 依据

兜底拦截在 `0x278658` 入口按 title 名单丢弃:

```js
const BLOCK_TITLE_NEEDLES = [
    'Check Find Root',  'Find Root',
    'Find Others Process',
    'Find Frida Mark',
    'Find Vpn Native',
    'Find Risk File',
    'find libart.so hooked',
    'libart.so piecewise',
    'checkLibCheckSum',  'checkLinkerCheckSum',
    '检测到libart.so被修改', '检测到libc.so被修改', '检测到linker',
    'HunterCheckApkSignError',
    // ...
];
Interceptor.attach(base.add(0x278658), {
    onEnter(args) {
        this.title = readStdString(args[1]);
        this.block = BLOCK_TITLE_NEEDLES.some(n => this.title.indexOf(n) !== -1);
    },
    onLeave(retval) {
        if (this.block) retval.replace(ptr(0));
    }
});
```

动态验证:开启 BLOCK 后 UI 端 risk 列表中对应 title 不再出现,印证"汇聚点拦截 = 22 caller × 83 callsite 全部消音"。

---

## 5. 完整性自检:模块 r-x 段 CRC 双链

Hunter 对 `libart.so` / `libc.so` / `linker64` / `libhunter.so` 做运行时 r-x 段累加和自检,两条独立链路:

### 5.1 链路总览

```
链路 1:Java 驱动的 CRC 比较
─────────────────────────────────────────────────────────────
Java: NativeEngine.getZhenxiLoctionCrc() : HashMap
  ↓ JNI
Java_NativeEngine_getZhenxiLoctionCrc @ 0x2AE064
  ↓
anti_inject_collect_results(rb_tree) @ 0xC8670
  ↓
sub_1A57DC: 红黑树 → Java HashMap (jstring path → jstring sum)
  ↓
Java YouAreLoser.ig.apply(rD{a=path, b=remote_crc}):
    local  = parseLong(hashMap.get(path))
    remote = item.b
    if (local != 0 && remote != 0 && local != remote)
        触发 ListItemBean("ISO CRC NOT MATCH LOCALITY CRC", ...)

链路 2:后台 task,不经 Java
─────────────────────────────────────────────────────────────
task_MAIN_CRC_check @ 0x2D6804
  ├─ check_libc_elf_checksum_status   @ 0xC90A0
  ├─ check_libart_elf_checksum_status @ 0xC9130
  └─ sub_C8FD0(libhunter_path)
       ↓
       ReportRiskItem("检测到libart.so被修改" / "检测到libc.so被修改" / 等, ...)
```

两条链共享底层算法栈:

```
scan_modules_for_path(path) @ 0xC8500
  ├─ parse_elf_rx_segments(s, path) @ 0xC6F14       ── ELF 文件 baseline
  │     ssyscall_openat / read / lseek / close 读 ELF
  │     遍历 PT_LOAD with PF_X,NEON sum 写入 s->segs[i].file_checksum
  │     结果写回 qword_2EF8B0 cache
  └─ scan_rx_segment_neon_sum(start, end, perms, s, path) @ 0xC772C   ── 内存侧实测
        for each segment:
            mem_ptr = start + offset
            maps_precheck_readable(mem_ptr, size) 先过
            NEON 128-bit 加宽累加该段所有字节
            v5 += 该段 sum
```

### 5.2 静态证据

#### 5.2.1 `NativeEngine_getZhenxiLoctionCrc` 包装层

```c
// libhunter.so+0x2AE064
jobject Java_NativeEngine_getZhenxiLoctionCrc(JNIEnv *env, jobject thiz) {
    anti_inject_collect_results(rb_tree);
    if (rb_tree[2])
        return convert_tree_to_HashMap(env, rb_tree);
    return NULL;
}
```

`anti_inject_collect_results @ 0xC8670` 拼 4 个目标路径(`build_libart_path` / `get_libc_path` / `get_linker64_path` / `std::string from xmmword_2F3C08`),每个路径调 `scan_modules_for_path(path) @ 0xC8500`,把结果 `std::to_string` 后存入 path → sum_str 红黑树。

#### 5.2.2 NEON 字节累加和算法

`scan_rx_segment_neon_sum` 与 `parse_elf_rx_segments` 共享同一段 NEON 字节累加和算法(也与 `InitSecureTrampolinePage` 内对跳板 48B 算 baseline 的算法完全一致):

```
sum = 0
for each 16 bytes from ptr:
    vmovl_u8 / vmovl_high_u8 把 16 个 u8 拆成 8x u16,再拆成 4x u32
    8 个 u32 通道并行 vaddw 加进 8 个 u64 累加器
最后 vaddvq_s64 把 8 个 u64 累加器合并成单个 i64 → 返回该段总和
```

这是**没有取模、没有移位、没有 lookup table 的纯 sum**:`sum = Σ(byte)`。

#### 5.2.3 `parse_elf_rx_segments` 输入/输出

输入:模块路径。输出:struct `s`:

```c
struct ElfRxBaseline {
    int     n_segs;
    struct { u64 _; u64 offset; u64 _; u64 size; u64 _; u64 file_checksum; } segs[2];
    u8      ok_flag;
};
```

`file_checksum` 是 cache miss 时**当场 calloc + ssyscall_read ELF 文件 + 算和**得到的。**该 file_checksum 路径上**的文件读取走 §3.6 的 ssyscall 包装器,即使 hook libc 的 fopen/fread 也拦不到。

cache 容器 `qword_2EF8B0` 是 path → struct map,首次访问后被永久缓存(`sub_CACC0` 写、`sub_CA670` 是 sentinel/init 检查)。

#### 5.2.4 `scan_rx_segment_neon_sum` 算法

```c
// libhunter.so+0xC772C
uint32_t scan_rx_segment_neon_sum(uintptr_t start, uintptr_t end, char *perms, ElfRxBaseline *s, const char *path) {
    if (perms[0..3] != "r-x*")
        return 0;
    uint32_t v5 = 0;
    for (i = 0; i < s->n_segs; i++) {
        uintptr_t mem_ptr = start + s->segs[i].offset;
        size_t    size    = s->segs[i].size;
        if (!maps_precheck_readable((void *)mem_ptr, size)) {
            v14 = 0;
        } else {
            v14 = NEON_sum(mem_ptr, size);
        }
        v5 += v14;
    }
    return v5;
}
```

注意:`scan_rx_segment_neon_sum` **不**在原地比较 `v14 == s->segs[i].file_checksum`;它只是把"运行时所有段 sum 之和"累加进 `v5` 返回。

也就是说,**Java 侧拿到的 HashMap value = "整个模块所有 PF_X 段 runtime NEON sum 的总和"**,真正的比对在 Java 侧的 `ig.apply`。

#### 5.2.5 找 r-x 内存区间的两条路径

`scan_modules_for_path` 把 baseline `s` 套到内存上时,主备两条:

- **主路径**:hunter 自实现 DSO 列表 `g_dso_list_head`(`sub_1AFF74` 用 `dl_iterate_phdr + getauxval(AT_PHDR)` 构建)
- **备路径**:`/proc/self/maps`(`parse_maps_to_linked_list(-1)`,走 libc `fopen` —— 这是整条链上唯一可被 libc-hook 干扰的环节)

主路径未命中 → 退到备路径。这意味着仅 hook libc 让 `/proc/self/maps` 撒谎是不够的。

#### 5.2.6 Java 侧比较 `YouAreLoser.ig.apply`

```java
// Java 伪代码(从 hook 行为反向还原)
Object apply(Object obj) {
    rD item = (rD) obj;
    String path     = item.a;
    long   remote   = item.b;
    long   local    = parseLong(nativeHashMap.get(path));
    if (local != 0 && remote != 0 && local != remote)
        triggerDetection();
    return hH.a;
}
```

三条件全成立才报警 → 任一为 0 即跳过。

### 5.3 动态证据

#### 5.3.1 `trace_crc_path_template.js` 实测 libart.so 各段 checksum

```
[crc-collect] anti_inject_collect_results entered
[crc-module] scan_modules_for_path path=/apex/com.android.art/lib64/libart.so
[crc-elf] parse_elf_rx_segments path0=/apex/com.android.art/lib64/libart.so
[crc-rx] path=/apex/com.android.art/lib64/libart.so start=0x74716a0000 end=0x7471818000 size=0x178000 perms=r--p
[crc-rx] path=/apex/com.android.art/lib64/libart.so segmentChecksum=0 ret=0x0
[crc-rx] path=/apex/com.android.art/lib64/libart.so start=0x74718a0000 end=0x747205c000 size=0x7bc000 perms=r-xp
[crc-rx] path=/apex/com.android.art/lib64/libart.so segmentChecksum=846246994 ret=0x3270b452
[crc-rx] path=/apex/com.android.art/lib64/libart.so start=0x74720a0000 end=0x74720c5000 size=0x25000 perms=r--p
[crc-rx] path=/apex/com.android.art/lib64/libart.so segmentChecksum=0 ret=0x0
[crc-rx] path=/apex/com.android.art/lib64/libart.so start=0x74722a0000 end=0x74722a3000 size=0x3000 perms=rw-p
[crc-rx] path=/apex/com.android.art/lib64/libart.so segmentChecksum=0 ret=0x0
[crc-module] scan_modules_for_path path=/apex/com.android.art/lib64/libart.so checksum=846246994 ret=0x3270b452
```

**只有 r-xp 段返回非零 checksum**,其他 r--p / rw-p 段返回 0。最终模块 checksum 等于唯一 r-xp 段的 sum。

#### 5.3.2 4 个目标模块的 checksum

```
/apex/com.android.runtime/lib64/bionic/libc.so
  r-xp 0x7716344000-0x771635d000 size=0x19000  segmentChecksum=56439566  / 0x35d330e
  module checksum = 56439566 / 0x35d330e

/apex/com.android.runtime/bin/linker64
  r-xp 0x77419e7000-0x77419ed000 size=0x6000   segmentChecksum=116553550 / 0x6f2774e
  rwxp 0x77419ed000-0x77419ee000 size=0x1000   segmentChecksum=0
  r-xp 0x77419ee000-0x7741b0e000 size=0x120000 segmentChecksum=0
  module checksum = 116553550 / 0x6f2774e

/data/app/.../lib/arm64/libhunter.so
  r-xp 0x73d4221000-0x73d42e7000 size=0xc6000  segmentChecksum=252930381 / 0xf13694d
  rwxp 0x73d42e7000-0x73d42ea000 size=0x3000   segmentChecksum=748020    / 0xb69f4
  r-xp 0x73d42ea000-0x73d44cf000 size=0x1e5000 segmentChecksum=763632    / 0xba6f0
  rwxp 0x73d44cf000-0x73d44d0000 size=0x1000   segmentChecksum=0
  r-xp 0x73d44d0000-0x73d44fe000 size=0x2e000  segmentChecksum=0
  module checksum = 254442033 / 0xf2a7a31
```

**libhunter.so 验证最终模块 checksum 是各段非零段 sum 的累加**:

```
252930381 + 748020 + 763632 = 254442033
0xf13694d + 0xb69f4 + 0xba6f0 = 0xf2a7a31  ✓
```

注意 `rwxp` 段不代表 checksum 必然 0(参看 libhunter.so 的 0xb69f4 与 linker64 的 0)。

#### 5.3.3 Java CRC 比较命中

```
[evidence:crc] NativeEngine_getZhenxiLoctionCrc entered
[evidence:crc] anti_inject_collect_results entered
[evidence:crc] NativeEngine_getZhenxiLoctionCrc ret=0x773adbce09
[evidence:crc-java] ig.apply path=/apex/com.android.art/lib64/libart.so remote=846246994 ret=YouAreLoser.qH@2187160
[evidence:ui] title=ISO CRC NOT MATCH LOCALITY CRC risk=Deadly type=0 data=/apex/com.android.art/lib64/libart.so

[evidence:crc-java] ig.apply path=/data/app/.../lib/arm64/libhunter.so remote=252937296 ret=YouAreLoser.qH@...
[evidence:ui] title=ISO CRC NOT MATCH LOCALITY CRC risk=Deadly type=0 data=/data/app/.../libhunter.so

[evidence:crc-java] ig.apply path=/apex/com.android.runtime/lib64/bionic/libc.so remote=56444108 ret=YouAreLoser.qH@...
[evidence:ui] title=ISO CRC NOT MATCH LOCALITY CRC risk=Deadly type=0 data=/apex/com.android.runtime/lib64/bionic/libc.so

[evidence:crc-java] ig.apply path=/apex/com.android.runtime/bin/linker64 remote=116553745 ret=YouAreLoser.qH@...
[evidence:ui] title=ISO CRC NOT MATCH LOCALITY CRC risk=Deadly type=0 data=/apex/com.android.runtime/bin/linker64
```

UI 原文:

```
[Java MainActivity.n0]
  title=ISO CRC NOT MATCH LOCALITY CRC
  data=/apex/com.android.art/lib64/libart.so
locality crc -> 856386775
remote service crc -> 846246994
```

`local = 856386775` ≠ `remote = 846246994` → 触发。

#### 5.3.4 链路 2 native 直接上报

```
[evidence:checksum] NativeEngine_getZhenxiInfoF entered
[evidence:checksum] check_libart_elf_checksum_status entered
block bad precheck 0x7741a35000 size 0x1266d8 lr ... off 0xc7828
[evidence:checksum] check_libart_elf_checksum_status ret=0x1
[evidence:report] title=检测到libart.so被修改 lr=libhunter.so+0x2ada40 (rva=0x2ada40)
[evidence:ui] title=检测到libart.so被修改 risk=Deadly type=6
```

LR `0x2ada40` 落在 `getZhenxiInfoF @ 0x2AD9A8` 内,与 §4.4 字典中 `getZhenxiInfoF × 8` callsite (W3=0, W4=3/4, W5=6) 一致。

#### 5.3.5 `block_bad_precheck` 多轮拦截

```
block bad precheck 0x773acbe000 size 0x7000   lr ... off 0xc68a4
block bad precheck 0x773e7bb000 size 0x1000   lr ... off 0xc68a4
block bad precheck 0x773e7ee000 size 0x4000   lr ... off 0xc68a4
block bad precheck 0x773e801000 size 0x1000   lr ... off 0xc68a4
block bad precheck 0x774059e000 size 0x1000   lr ... off 0xc68a4
block bad precheck 0x7741a35000 size 0x1266d8 lr ... off 0xc7828
block bad precheck 0x7741b5b6d8 size 0xd8     lr ... off 0xc7828
block bad precheck 0x7741a36000 size 0x1266d8 lr ... off 0xc7828
block bad precheck 0x7741b5c6d8 size 0xd8     lr ... off 0xc7828
block bad precheck 0x73d55ec990 size 0x2650   lr ... off 0xc7828
block bad precheck 0x73d55ee990 size 0x2650   lr ... off 0xc7828
block bad precheck 0x73d55f9990 size 0x2650   lr ... off 0xc7828
block bad precheck 0x73d55fc990 size 0x2650   lr ... off 0xc7828
```

`off 0xC68A4`(在 `sub_C687C`,parse_elf_rx_segments 内 ELF 文件读出后)和 `off 0xC7828`(在 `scan_rx_segment_neon_sum`,RX 段扫描路径)各反复触发,**印证两条独立链路的越界点位置**。

### 5.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| H1 | 4 个目标路径:libart / libc / linker64 / libhunter | 实测 `[crc-module]` 出现这 4 个 path | ✓ |
| H2 | NEON 字节累加和算法,纯 sum 不取模 | libhunter.so 各段 sum 累加 = module sum,数学验证 ✓ | ✓ |
| H3 | 只对 r-x 段累加,其他段返回 0 | 实测各 r--p / rwxp / rw-p 段大多 segmentChecksum=0(libhunter 的 rwxp 段 0xb69f4 是个例外) | ✓ |
| H4 | 文件读取走 ssyscall 包装器 | §3.3.4 实测 openat/read/close/lseek 出现在跳板调用面 | ✓ |
| H5 | cache 容器 `qword_2EF8B0` 首次后永久缓存 | 多轮调用中只首次出现 `parse_elf_rx_segments entered` 日志 | 间接 ✓ |
| H6 | Java 侧 `ig.apply` 三条件比较 | 实测 `[evidence:crc-java]` ig.apply 命中 4 个目标路径 | ✓ |
| H7 | 失配 UI 文案 = "ISO CRC NOT MATCH LOCALITY CRC" | 实测 UI title 完全匹配 | ✓ |
| H8 | 链路 2 不经 Java,native 直接报 "检测到libart.so被修改" | 实测 `[evidence:report] title=检测到libart.so被修改 lr=0x2ada40` | ✓ |
| H9 | 链路 2 LR 落在 `getZhenxiInfoF @ 0x2AD9A8` 内 | LR `0x2ada40 - 0x2AD9A8 = 0x98`(在 InfoF 函数体内) | ✓ |
| H10 | `maps_precheck_readable` unmapped hole bug 影响 `scan_rx_segment_neon_sum` | 实测 `block_bad_precheck` 反复在 `off 0xc7828`(scan_rx_segment_neon_sum 内)触发 | ✓ |
| H11 | 同时影响 `parse_elf_rx_segments` 的可读性预检 | 实测 `block_bad_precheck` 同样在 `off 0xc68a4`(sub_C687C 内)触发 | ✓ |

### 5.5 libhunter.so CRC 值动态变化的含义

不同运行中 `libhunter.so` 的本地 CRC 值可能变化:某次 `258223051`,另一次 `252914579`,本节实测 `254442033`。

**这是 hunter "对运行时 RX 段/映射状态做采样"的特征体现**:libhunter.so 的多个段(包括 rwxp 段)随运行时状态变化(GOT 修改、绑定地址写入等)产生不同 NEON sum。不应把这个值当作 APK 文件静态 CRC。

### 5.6 bypass 依据

两层处理(`js/bypass_crc_detection.js`):

```js
// 链路 1 上游:让 native HashMap 全部 value = "0",ig.apply 因 local=0 跳过
NativeEngine.getZhenxiLoctionCrc.implementation = function () {
    const map = HashMap.$new();
    CRC_TARGET_PATHS.forEach(path => map.put(path, "0"));
    return map;
};

// 双保险:ig.apply 对目标 path 直接返回 NoRisk
YouAreLoser.ig.apply.overload('java.lang.Object').implementation = function (obj) {
    const path = ((rD) obj).a;
    if (CRC_TARGET_PATHS.includes(path))
        return hH.a;                             // 直接返回 NoRisk
    return apply.call(this, obj);
};

// 链路 2:NativeEngine.getZhenxiInfoF -> null
NativeEngine.getZhenxiInfoF.implementation = function () { return null; };

// 必带:block_bad_precheck 防 scan_rx_segment_neon_sum 越界崩溃
block_bad_precheck(modbase);
```

动态验证:

```
[bypass:crc] ig.apply skip compare path=/apex/com.android.art/lib64/libart.so remote=846246994
[bypass:checksum] NativeEngine.getZhenxiInfoF -> null
```

CRC 风险项消失。

---

## 6. `/proc/mounts` Root/APatch 检测

### 6.1 链路

```
Java: GC.run -> NativeEngine.getZhenxiInfo3()
JNI : NativeEngine_getZhenxiInfo3 @ 0x2B476C
核心: detect_root_mark_in_proc_mounts_maps @ 0xD5E34
辅助: file_contains_any_marker @ 0x1A6300
上报: ReportRiskItem LR 0x2B4A88
UI  : "Check Find Root In Mounts"
```

### 6.2 静态证据

#### 6.2.1 7 路短路链

`NativeEngine_getZhenxiInfo3 @ 0x2B476C` 引用的风险项字符串:

```
Check Find Root File
Check Find Root In Mounts
Check Find Root Mark
Check Find Root Magisk Mode
Check Find Root In Linker
Check Find Root Permission
Find Root Mark In Mountinfo
```

完整短路顺序:

| 顺序 | 子函数 RVA | UI title | 主要监测点 |
|-|-|-|-|
| 1 | `0xD2CDC` | `Check Find Root File` | 固定 root/hook 文件路径、`/proc/<pid>/attr/*`、OverlayFS、`/data/adb/modules`、mount namespace、`/proc/modules` |
| 2 | `0xD5E34` | `Check Find Root In Mounts` | `/proc/mounts`、`mountinfo`、线程 maps、`df -h` 中的 root/APatch/Magisk marker |
| 3 | `0xD703C` | `Check Find Root Mark` | `/data/adb*`、Magisk/LSPosed/Riru marker、`/proc/fs/jbd2` 与 ext4 loop 痕迹 |
| 4 | `0xD9604` | `Check Find Root Magisk Mode` | 当前版本直接 `return 0`,保留分支 |
| 5 | `0xD216C` | `Check Find Root In Linker` | `dl_iterate_phdr` 收集 linker 已加载 ELF,匹配可疑 Zygisk engine 路径 |
| 6 | `0xDDB9C` | `Check Find Root Permission` | netlink 权限侧信道,命中详情前缀 `netlink Find Permission` |
| 7 | `0xDF51C` | `Find Root Mark In Mountinfo` | `/proc/self/exe` 类型、`/proc/self/mountinfo` 的 overlay/system/bin 痕迹 |

#### 6.2.2 `NativeEngine_getZhenxiInfo3` 伪代码

```c
// libhunter.so+0x2B476C
jobject NativeEngine_getZhenxiInfo3(JNIEnv *env) {
    if (check_root_file_and_namespace())             // sub_D2CDC
        return ReportRiskItem(env, "Check Find Root File ", detail, FB_Info, 1);
    if (detect_root_mark_in_proc_mounts_maps())      // sub_D5E34
        return ReportRiskItem(env, "Check Find Root In Mounts ", last_mounts_detail, FB_Info, 1);
    if (check_root_mark_data_adb_and_jbd2())         // sub_D703C
        return ReportRiskItem(env, "Check Find Root Mark ", detail, FB_Info, 1);
    if (check_magisk_mode_reserved())                // sub_D9604, 当前版本直接 return 0
        return ReportRiskItem(env, "Check Find Root Magisk Mode ", detail, FB_Info, 1);
    if (check_root_in_linker_loaded_elf())           // sub_D216C
        return ReportRiskItem(env, "Check Find Root In Linker ", detail, FB_Info, 1);
    if (check_root_permission_netlink(env))          // sub_DDB9C
        return ReportRiskItem(env, "Check Find Root Permission", detail, FB_Info, 1);
    if (check_mountinfo_overlay_system_bin())        // sub_DF51C
        return ReportRiskItem(env, "Find Root Mark In Mountinfo", detail, FB_Info, 1);
    return NULL;
}
```

#### 6.2.3 `detect_root_mark_in_proc_mounts_maps @ 0xD5E34` 伪代码

```c
bool detect_root_mark_in_proc_mounts_maps() {
    if (file_contains_any_marker("/proc/mounts", markers, out))
        return append_detail("/proc/mounts->", out);
    if (file_contains_any_marker("/proc/self/mounts", markers, out))
        return append_detail("/proc/self/mounts->", out);
    if (file_contains_any_marker("/proc/self/mountstats", markers, out))
        return append_detail("/proc/self/mountstats->", out);
    if (file_contains_any_marker("/proc/self/mountinfo", markers, out))
        return append_detail("/proc/self/mountinfo->", out);

    // /proc/self/task/<tid>/maps
    tid = gettid();
    path = "/proc/self/task/" + to_string(tid) + "/maps";
    if (file_contains_any_marker(path, markers, out))
        return append_detail("/proc/self/maps->", out);

    // popen("df -h", "r")
    if (df_h_contains_any_marker(markers, out))
        return append_detail("find mark item -> ", out);

    return false;
}
```

#### 6.2.4 18 项 marker 向量(`sub_D116C @ 0xD116C` 构造)

```
/riru, riru-, /edxp, lsposed,
magisk, Magisk, /appwidget, /debug_ramdisk,
dex2oat, apatch, Apatch, APatch,
kernelsu, kernelSu, zygisk, revanced,
/data/adb/modules, sukisu
```

#### 6.2.5 `file_contains_any_marker @ 0x1A6300` 伪代码

```c
bool file_contains_any_marker(const char *path, vector<string> *markers, string *out) {
    FILE *fp = fopen(path, "re");
    if (fp == NULL) {
        cout << "file_include open file fail " << path << " " << strerror(errno);
        return false;
    }
    string line;
    while (getline(fp, line)) {
        cout << "file_include checking " << path << " " << line;
        for (string &marker : *markers) {
            if (marker.empty()) continue;
            if (line.find(marker) != string::npos) {
                cout << "file_include find " << path << " " << line;
                *out = line;
                fclose(fp);
                return true;
            }
        }
    }
    fclose(fp);
    return false;
}
```

它不解析 mount 字段,不检查 mount type、source、target 的结构合法性 —— 纯 substring 命中。

### 6.3 动态证据

#### 6.3.1 主路径命中

```
[evidence:mounts] NativeEngine_getZhenxiInfo3 entered
[evidence:mounts] detect_root_mark_in_proc_mounts_maps entered
[evidence:mounts-file] file_contains_any_marker path=/proc/mounts
  markers=/riru|riru-|/edxp|lsposed|magisk|Magisk|/appwidget|/debug_ramdisk|dex2oat|apatch|Apatch|APatch|kernelsu|kernelSu|zygisk|revanced|/data/adb/modules|sukisu
[evidence:mounts-file] path=/proc/mounts ret=0x1
  hit=APatch /debug_ramdisk tmpfs rw,seclabel,relatime 0 0
[evidence:mounts] detect_root_mark_in_proc_mounts_maps ret=0x1
[evidence:report] title=Check Find Root In Mounts lr=libhunter.so+0x2b4a88 (rva=0x2b4a88)
  detail=com.zhenxi.hunter:hunter_main_process
  /proc/mounts->APatch /debug_ramdisk tmpfs rw,seclabel,relatime 0 0
[evidence:mounts] NativeEngine_getZhenxiInfo3 ret=0x7737909809
[evidence:ui] title=Check Find Root In Mounts  risk=Info type=1
  data=com.zhenxi.hunter:hunter_main_process
[evidence:ui] title=Check Find Root In Mounts  risk=Info type=1
  data=com.zhenxi.hunter:hunter_server_iso:com.zhenxi.hunter.ZhenxiServer:hunter_iso_service
```

命中行 `APatch /debug_ramdisk tmpfs rw,seclabel,relatime 0 0` 同时命中 `APatch` 和 `/debug_ramdisk` 两个 marker。

#### 6.3.2 短路链后续分支补证(`trace_info3_branch_experiment.js`)

`getZhenxiInfo3` 是短路链,默认运行时先被 `sub_D5E34` 命中,后续分支不会跑。强制 `sub_D5E34` 返回 0 后:

```
[+] FORCE_MISS={"rootFile":false,"mounts":true,"rootMark":false,"linker":false,"permission":true,"mountinfo":false}
[info3] NativeEngine_getZhenxiInfo3 entered
[info3-branch-ret] sub_D2CDC title="Check Find Root File" ret=0x0
[info3-branch-ret] sub_D5E34 title="Check Find Root In Mounts" ret=0x1
[info3-force] sub_D5E34 real ret=0x1 forced to 0 so the next branch can run
[info3-branch-ret] sub_D703C title="Check Find Root Mark" ret=0x0
[info3-branch-ret] sub_D9604 title="Check Find Root Magisk Mode" ret=0x0
[info3-branch-ret] sub_D216C title="Check Find Root In Linker" ret=0x0
[info3-branch-ret] sub_DDB9C title="Check Find Root Permission" ret=0x1
[info3-force] sub_DDB9C real ret=0x1 forced to 0 so the next branch can run
[info3-branch-ret] sub_DF51C title="Find Root Mark In Mountinfo" ret=0x0
[info3] NativeEngine_getZhenxiInfo3 ret=0x0
```

链路完整跑通:真实命中点有两个 —— `sub_D5E34`(mounts APatch 命中)和 `sub_DDB9C`(netlink permission 命中)。

#### 6.3.3 `file_contains_any_marker` 是通用 helper

同一进程中能看到不同 marker 向量复用该 helper:

```
[evidence:mounts-file] file_contains_any_marker path=/proc/mounts
  markers=docker|lxc_volumns
[evidence:mounts-file] path=/proc/mounts ret=0x0

[evidence:mounts-file] file_contains_any_marker path=/proc/mounts
  markers=/mnt/shared/Sharefolder|/tiantian.conf|/data/share1|/hardware_device.conf|/mnt/shared/products|/mumu_hardware.conf|/Andy.conf|/mnt/windows/BstSharedFolder|/bst.conf|/mnt/shared/Applications|/ld.conf|/vboxsf
[evidence:mounts-file] path=/proc/mounts ret=0x0
```

对应 Java 静态代码 `src/YouAreLoser/y00.java`:

```java
String[] markers = {"docker", "lxc_volumns"};
NativeEngine.getZhenxiInfoK("/proc/mounts", markers);
```

因此须区分:

```
file_contains_any_marker @ 0x1A6300
  = 通用"文件逐行包含 marker" helper

detect_root_mark_in_proc_mounts_maps @ 0xD5E34
  = root/APatch mount 检测模板,传入 root/APatch/Magisk marker 向量
```

只有当调用链是 `NativeEngine_getZhenxiInfo3 -> detect_root_mark_in_proc_mounts_maps -> file_contains_any_marker`、并且 marker 向量是 `/riru|...|APatch|kernelsu|...` 时,才归类为本节的 APatch/root mount 检测。

### 6.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| M1 | `NativeEngine_getZhenxiInfo3` 是 7 路短路链 | `trace_info3_branch_experiment.js` 强制 miss 第二分支后,后续 5 个分支均依次执行 | ✓ |
| M2 | sub_D5E34 是其中 mounts 分支 | `trace_info3_branch_experiment.js` 看到 sub_D5E34 title="Check Find Root In Mounts" | ✓ |
| M3 | 18 项 marker 向量 | `[evidence:mounts-file]` 打印 markers 完整列出 18 项 | ✓ |
| M4 | 读取源 6 个:`/proc/mounts` → `/proc/self/mounts` → `mountstats` → `mountinfo` → 线程 maps → `df -h` | 第一项 `/proc/mounts` 即命中,后续未执行(短路);但其它实验路径中可看到 `/proc/self/mountstats` 等被读 | ✓ 部分 |
| M5 | substring 匹配(`line.find(marker)`)而非结构化解析 | 命中行 `APatch /debug_ramdisk tmpfs rw,...` 同时命中 `APatch` 和 `/debug_ramdisk` | ✓ |
| M6 | ReportRiskItem callsite 在 `getZhenxiInfo3` 内 | LR 0x2b4a88,(LR-4)=0x2b4a84 落在 `0x2B476C` 函数体内 | ✓ |
| M7 | `file_contains_any_marker` 通用 helper | 同一会话中同时观察到 root markers / docker markers / 模拟器路径 markers 三组复用 | ✓ |
| M8 | sub_DDB9C 是 netlink 权限侧信道 | `trace_info3_branch_experiment.js` 看到 sub_DDB9C title="Check Find Root Permission" ret=0x1(本设备命中) | ✓ |

### 6.5 对抗面分析

输入源 6 个、marker 向量 18 项 —— **任一源任一行包含任一 marker 即触发**。对抗需要:

```
必须净化的读取源:
- /proc/mounts
- /proc/self/mounts
- /proc/self/mountstats
- /proc/self/mountinfo
- /proc/self/task/<tid>/maps
- df -h 依赖的 mount/文件系统信息来源

必须避免出现在输出中的 marker:
- APatch / apatch / Apatch
- /debug_ramdisk
- kernelsu / kernelSu
- magisk / Magisk
- /data/adb/modules
- zygisk / lsposed / riru / edxp 等模块痕迹
```

本设备命中 `APatch /debug_ramdisk tmpfs rw,...` 一行命中两个 marker,**只替换其中一个不够**。

### 6.6 bypass 依据

```js
NativeEngine.getZhenxiInfo3.implementation = function () {
    return null;
};
```

动态验证:

```
[bypass:mounts] NativeEngine.getZhenxiInfo3 -> null
```

主进程风险项消失。但 `:hunter_server_iso` / `:hunter_server_twin` 子进程通过 Binder 仍可回传同类 bean(详 §22),需配合 UI 层兜底或多进程 spawn。

---

## 7. libart maps 分片/Hook 检测

### 7.1 链路

```
Java: NativeEngine.getZhenxiMapCheck()
JNI : NativeEngine_getZhenxiMapCheck @ 0x291858
输入: /proc/self/maps 解析结果
上报: ReportRiskItem LR 0x2924B8(size==0x1000 立即上报分支)
UI  : "find libart.so hooked 0"
```

### 7.2 静态证据

`NativeEngine_getZhenxiMapCheck @ 0x291858` 引用字符串:

```
libart.so
libart.so piecewise ,memory is not legal
check map legal error
open maps error
```

Java 触发片段:

```java
// src/com/google/android/gms/internal/common/zzv.java
return NativeEngine.getZhenxiMapCheck();
// src/YouAreLoser/IB.java
return NativeEngine.getZhenxiMapCheck();
```

伪代码:

```c
// libhunter.so+0x291858
maps = parse_maps_to_linked_list(-1);
if (maps == NULL) {
    return ReportRiskItem(env, "check map legal error ", "open maps error ", NoRisk_or_Deadly, 3);
}

libart_piece_count = 0;
detail = "";

for each map_node:
    if pathname contains "libart.so":
        libart_piece_count++;
        detail += pathname + "|" + decimal(map_node.size) + "|" +
                  map_node.perms + "|" + hex(map_node.start) + "->" + hex(map_node.end) + "\n";

        if map_node.size == 0x1000:
            return ReportRiskItem(
                env,
                "find libart.so hooked " + decimal(map_node.size),
                format_map_node(map_node),
                Deadly,
                3
            );

if libart_piece_count >= 6:
    return ReportRiskItem(
        env,
        "libart.so piecewise ,memory is not legal ",
        detail,
        Deadly,
        2
    );

return NULL;
```

关键地址:

```
0x29188C parse_maps_to_linked_list(-1)
0x291D20 linked_list_step(ptr)
0x291D40 strstr(pathname, "libart.so")
0x292358 if strstr(pathname, "libart.so") && map_node.size == 4096
0x292480 title = "find libart.so hooked " + size
0x292498 sub_FCB94(v65, map_node) 格式化当前 map_node 详情
0x2924B8 ReportRiskItem(...)
0x2923B4 if ((__int16)libart_piece_count < 6) return NULL
0x2923CC title = "libart.so piecewise ,memory is not legal "
0x2923EC ReportRiskItem(...)
```

两个独立判定:

```
单段异常: 任意 libart.so mapping 的 size == 0x1000,立即上报 "find libart.so hooked 0/4096"
分片异常: libart.so mapping 数量 >= 6,上报 "piecewise"(静态/间接证据,本环境未实际触发)
```

不校验 libart 文件内容,**只看进程内 libart.so 的 maps 形态**。Frida / LSPosed / SandHook 等会让 ART 代码页被重映射 / 拆分 / 产生异常小 mapping,触发本条。

### 7.3 动态证据

```
[evidence:art-map] NativeEngine_getZhenxiMapCheck entered
[evidence:report] title=find libart.so hooked 0 lr=libhunter.so+0x2924b8 (rva=0x2924b8)
  detail=map item path ->
  name ->
  []
  name len size [0]
  exec address start-> 0x0
  exec address end-> 0x0
  perm ->
  inode -> 0
  mem size -> 0
  pid-> 16657
[evidence:art-map] NativeEngine_getZhenxiMapCheck ret=0x7737971009
[evidence:ui] title=find libart.so hooked 0 risk=Deadly type=0 data=map item path ->
```

汇聚点原始日志:

```
[ReportRiskItem]
  arg1: find libart.so hooked 0
  arg2: map item path ->
  ...
ReportRiskItem this->lr: libhunter.so+0x2924b8
```

Java UI:

```
[Java MainActivity.n0]
  title=find libart.so hooked 0
  risk=Deadly
```

### 7.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| A1 | JNI 函数 `getZhenxiMapCheck @ 0x291858` | 实测 60 项表 #45 = getZhenxiMapCheck rva=0x291858 | ✓ |
| A2 | 解析 `/proc/self/maps` 找 libart.so 形态 | `[evidence:art-map] NativeEngine_getZhenxiMapCheck entered` 后输出 map item 详情 | ✓ |
| A3 | size==0x1000 立即上报"find libart.so hooked" | 实测 arg1="find libart.so hooked 0",lr=0x2924b8 | ✓ |
| A4 | 0x2924B8 是 size==0x1000 分支的上报点 | LR 完全等于 0x2924B8 | ✓ |
| A5 | libart_count >= 6 上报"piecewise" | 本设备命中 single 4KB 分支(优先返回),未触发 piecewise | 间接 ✓ |
| A6 | UI risk=Deadly 但 W3=0 | W3 从 0x278658 onEnter 看为 0,但 UI 显示 Deadly,W4=2/3 决定 UI 等级 | ✓ |

### 7.5 对抗面

```
敏感字段:
- pathname 是否包含 libart.so
- mapping start/end / size = end - start / perms
- libart.so mapping 总段数

触发条件:
- 任意 libart.so map_node.size == 0x1000  (优先)
- 或 libart.so mapping 数量 >= 6(静态/间接证据,本环境未实际触发)
```

对抗时必须保证向目标进程暴露的 maps 中 `libart.so` 不出现异常 4KB 分片,也不要把 `libart.so` 拆成过多段。单纯隐藏 Frida 字样、LSPosed 字样不能解决此分支,**它匹配的是 libart.so 本身**。

### 7.6 bypass 依据

```js
NativeEngine.getZhenxiMapCheck.implementation = function () {
    return null;
};
```

动态验证:

```
[bypass:art-map] NativeEngine.getZhenxiMapCheck -> null
```

风险项消失。

---

## 8. libc/libart/linker 运行时 checksum 检测

§5 已完整还原 CRC 双链算法栈。本节只补 native 直接上报(链路 2,`getZhenxiInfoF`)的 detection 细节。

### 8.1 链路

```
Java: NativeEngine.getZhenxiInfoF()
JNI : NativeEngine_getZhenxiInfoF @ 0x2AD9A8
内部: check_libart_elf_checksum_status @ 0xC9130
      check_libc_elf_checksum_status   @ 0xC90A0
      check_linker64_elf_checksum_status @ 0xC89BC
上报: ReportRiskItem LR 0x2ADA40 / 0x2ADD8C / ... (8 个 callsite)
UI  : "检测到libart.so被修改" / "检测到libc.so被修改" / "检测到linker..."
```

### 8.2 静态证据

`NativeEngine_getZhenxiInfoF @ 0x2AD9A8` 内有 8 个 callsite(W3=0,W4=3 或 4,W5=6,详 §4.4 字典),覆盖:

```c
// libhunter.so+0xC9130
uint32_t check_libart_elf_checksum_status() {
    std::string path = build_libart_path();
    return check_elf_checksum(path);
}

// libhunter.so+0xC90A0
uint32_t check_libc_elf_checksum_status() {
    std::string path = get_libc_path();
    return check_elf_checksum(path);
}

// libhunter.so+0xC89BC
uint32_t check_linker64_elf_checksum_status() {
    std::string path = get_linker64_path();
    return check_elf_checksum(path);
}
```

三者共享 `scan_modules_for_path @ 0xC8500` 同源算法栈(详 §5.2)。

### 8.3 动态证据

```
[evidence:checksum] NativeEngine_getZhenxiInfoF entered
[evidence:checksum] check_libart_elf_checksum_status entered
block bad precheck 0x7741a35000 size 0x1266d8 lr ... off 0xc7828
[evidence:checksum] check_libart_elf_checksum_status ret=0x1
[evidence:report] title=检测到libart.so被修改 lr=libhunter.so+0x2ada40 (rva=0x2ada40)
[evidence:ui] title=检测到libart.so被修改 risk=Deadly type=6
```

LR `0x2ada40` 落在 `getZhenxiInfoF @ 0x2AD9A8` 内,size=`0x2ada40 - 0x2AD9A8 = 0x98` 处的 callsite。

### 8.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| F1 | JNI 函数 `getZhenxiInfoF @ 0x2AD9A8` | 60 项表 #(查到)= getZhenxiInfoF rva=0x2ad9a8 | ✓ |
| F2 | 内部调用 `check_libart_elf_checksum_status @ 0xC9130` | `[evidence:checksum] check_libart_elf_checksum_status entered` | ✓ |
| F3 | 检测命中返回 1 | `[evidence:checksum] check_libart_elf_checksum_status ret=0x1` | ✓ |
| F4 | callsite 在 `getZhenxiInfoF` 内 | LR 0x2ada40 在 `[0x2AD9A8, 0x2AD9A8+size)` 范围 | ✓ |
| F5 | UI 文案"检测到libart.so被修改" | `[evidence:ui] title=检测到libart.so被修改` | ✓ |
| F6 | W5=6(checksum 类别) | UI type=6 | ✓ |
| F7 | 与 `scan_rx_segment_neon_sum` 共享算法 | `block_bad_precheck off 0xc7828`(scan_rx_segment_neon_sum 内)反复在此 detection 触发 | ✓ |

### 8.5 bypass 依据

```js
NativeEngine.getZhenxiInfoF.implementation = function () {
    return null;
};
```

动态验证:

```
[bypass:checksum] NativeEngine.getZhenxiInfoF -> null
```

native 直接上报路径(链路 2)的风险项消失。但 `task_MAIN_CRC_check` 后台任务仍可能触发同类 detection,需配合 SO 层 `Interceptor.replace` 在 JNI 入口直接 return 0 拦截,或在 `0x278658` 汇聚点按 title 名单兜底。

---

## 9. 注入/匿名可执行内存检测

### 9.1 链路

```
Java: GC.m() -> NativeEngine.getZhenxiInfoInjection()
JNI : NativeEngine_getZhenxiInfoInjection @ 0x28DF24
内部: 6 个子检测,任一非空返回
返回: jstring(空/null 时 Java 不构造 bean)
UI  : "Hunter Find Unknown Exec Item From Mian" (注意 "Mian" 是原 typo)
```

### 9.2 静态证据

Java 触发逻辑(`src/YouAreLoser/GC.java`):

```java
String s = NativeEngine.getZhenxiInfoInjection();
if (s != null && !s.isEmpty()) {
    n0(new ListItemBean("Hunter Find Unknown Exec Item From Mian", FB.c,
                        App.getCheckFrom() + s));
}
```

`NativeEngine_getZhenxiInfoInjection @ 0x28DF24` 是 6 子检测的汇总:

| 子函数 | 检测对象 | 标志字符串 |
|-|-|-|
| `0x100AAC` | 匿名 / 未知路径的可执行内存(`rwxp` + inode=0 + path 空或 `?`) | `"mem, suspicious execution procedure ->"` / `"find rwx item 111"` / `"libc_malloc"` / `"scudo"` |
| `0x102814` | memfd JIT cache mapping | `"memfd:jit-cache"` / `"memfd:jit-zygote-cache"` |
| `0x103610` | maps 行格式异常 | `<dyn>` |
| `0x104D54` | missing page(可执行但 mapping 缺失页) | `"missing page, suspicious execution procedure ->"` / `"pid ->"` |
| `0x105ACC` | NativeBridge / AndroidRuntime hook | `dlopen("/system/lib64/libandroid_runtime.so")` + `_ZN7android14AndroidRuntime10getRuntimeEv` / `"Found Hook NativeBridge"` |
| `0x10610C` | 匿名内存 / jit-cache 一致性 | `"Found suspicious anonymous memory"` / `"find inconsistent dalvik-zygote-jit-code-cache :"` / `"[anon:dalvik-zygote-jit-code-cache]"` / `"/memfd:jit-cache"` |

伪代码:

```c
// libhunter.so+0x28DF24
jstring NativeEngine_getZhenxiInfoInjection(JNIEnv *env) {
    string out;
    if (sdk >= 30)
        out += detect_unknown_exec_or_rwx_maps();     // 0x100AAC
    if (out.empty())
        out += detect_jit_cache_maps();               // 0x102814
    if (out.empty())
        out += detect_extra_maps_anomaly();           // 0x103610
    if (out.empty())
        out += detect_missing_page_exec_anomaly();    // 0x104D54
    if (out.empty())
        out += detect_nativebridge_runtime_hook();    // 0x105ACC
    if (out.empty())
        out += detect_suspicious_anonymous_memory();  // 0x10610C
    if (out.empty())
        return NULL_or_empty;
    return NewStringUTF(result);
}
```

### 9.3 动态证据

#### 9.3.1 默认命中(`0x100AAC`)

```
[evidence:injection] NativeEngine_getZhenxiInfoInjection entered
[evidence:injection] NativeEngine_getZhenxiInfoInjection jstring=0x7737971e05
[evidence:ui] title=Hunter Find Unknown Exec Item From Mian risk=Deadly type=0
  data=<com.zhenxi.hunter:hunter_main_process>

title=Hunter Find Unknown Exec Item From Mian
data=<com.zhenxi.hunter:hunter_main_process>
mem, suspicious execution procedure ->
pid -> ...
map item path ->
77270f4000-7727104000 rwxp 00000000 00:00 0 ?
```

完整返回字符串(后续运行的 native 端 retval):

```
mem, suspicious execution procedure ->
pid ->4325/com.zhenxi.hunter:hunter_main_process
map item path ->
7727002000-7727012000 rwxp 00000000 00:00 0 ?
name -> []
exec address start-> 0x7727002000
exec address end-> 0x7727012000
perm -> rwxp
inode -> 0
mem size -> 65536
pid-> 4325
------------------------------
find rwx item 111
```

#### 9.3.2 拆分 6 子检测(`trace_injection_subchecks_template.js`)

读取每个子函数隐藏返回参数 `x8` 指向的 `std::string`,在记录真实输出后临时清空前序非空结果让 wrapper 继续:

```
sub_100AAC / anonymous/unknown executable maps and RWX:
  outLen=3131
  mem, suspicious execution procedure ->
  7727012000-7727022000 rwxp 00000000 00:00 0 ? size=65536
  773e719000-773e71a000 rwxp 00000000 00:00 0 ? size=4096
  forced empty

sub_102814 / memfd JIT cache maps:
  outLen=0

sub_103610 / extra maps anomaly formatting:
  outLen=0

sub_104D54 / missing page executable anomaly:
  outLen=0

sub_105ACC / NativeBridge/AndroidRuntime hook:
  outLen=0

sub_10610C / anonymous memory / jit-cache consistency scan:
  outLen=3106
  Found suspicious anonymous memory:
    7727012000-7727022000 rwxp 00000000 00:00 0 ? size=65536
    773acbe000-773acc5000 rwxp 00000000 00:00 0 ? size=28672
    773e719000-773e71a000 rwxp 00000000 00:00 0 ? size=4096
    773e71b000-773e71c000 rwxp 00000000 00:00 0 ? size=4096
```

### 9.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| I1 | JNI 函数 `getZhenxiInfoInjection @ 0x28DF24` | 60 项表实测 rva=0x28df24 | ✓ |
| I2 | 6 个子检测短路链 | 拆分实验中,sub_100AAC 默认命中;清空后 sub_10610C 也命中;sub_102814 / 103610 / 104D54 / 105ACC 当前环境未命中 | ✓ 部分 |
| I3 | sub_100AAC 检测匿名 rwxp + inode=0 | 实测 detail 含 `7727002000-7727012000 rwxp 00000000 00:00 0 ?` | ✓ |
| I4 | 静态字符串 `"find rwx item 111"` | 实测 detail 末尾出现 `find rwx item 111` | ✓ |
| I5 | sub_10610C 检测 `"Found suspicious anonymous memory"` | 拆分实验中 sub_10610C outLen=3106 含此字面量 | ✓ |
| I6 | Java 端判 `s != null && !s.isEmpty()` 才构造 bean | bypass 返回空字符串后 UI 不再出现该 bean | ✓ |
| I7 | UI 文案 "Hunter Find Unknown Exec Item From Mian"(注意 "Mian" 拼写) | UI 实测原样显示 "Mian" | ✓ |

### 9.5 对抗面

当前环境命中两类:

```
默认命中: sub_100AAC  ── 匿名 rwxp + inode=0 + path 空或 ?
辅助命中: sub_10610C  ── 匿名内存 / jit-cache 一致性扫描
未命中:   sub_102814 (memfd JIT) / sub_103610 (maps 格式) / sub_104D54 (missing page) / sub_105ACC (NativeBridge)
```

Frida agent 在主进程映射匿名 RWX 区是触发本条的主要原因。对抗思路是隐藏这类 mapping(可在 maps 解析侧/物理映射侧欺骗)。

### 9.6 bypass 依据

```js
NativeEngine.getZhenxiInfoInjection.implementation = function () {
    return "";
};
```

动态验证:

```
[bypass:injection] NativeEngine.getZhenxiInfoInjection -> empty
```

Java 侧条件 `!s.isEmpty()` 不满足,bean 不构造。返回空字符串是源头 bypass。

---

## 10. 其他进程扫描检测

### 10.1 链路

```
Java: NativeEngine.getZhenxiInfo4(Context)
JNI : NativeEngine_getZhenxiInfo4 @ 0x2A2D98
上报: ReportRiskItem LR 0x2A3F6C
UI  : "Find Others Processmay be risks main pid (...)" / "Find Others Process"
```

### 10.2 静态证据

#### 10.2.1 两阶段算法

第一阶段:`/proc` pid 枚举

```
opendir("/proc")
readdir(...)
读取 /proc/<pid>/comm     ── helper sub_1A5304 @ 0x1A5304
读取 /proc/<pid>/cmdline
```

进程名与关键字比较(精确/模糊):

```
HUNTER_TRACER
install
hunter
linker
app_
twin
```

命中后:

```
find other process <pid> <name>
other pid -> <pid>(pid name: <name>)
```

第二阶段:`ps -ef` 采集(`sub_D0DA4 @ 0xD0DA4` 动态 `dlopen("libc.so")/dlsym("popen")`):

```
popen("ps -ef", "r")
逐行过滤 !contains("hunter") && !contains("install")
累计命中 >= 3 → ReportRiskItem("Find Others Process", ...)
popen 失败 → "ps error"
无满足行 → "NOT FIND SANDBOX"
```

#### 10.2.2 伪代码

```c
// libhunter.so+0x2A2D98
jobject NativeEngine_getZhenxiInfo4(JNIEnv *env, jobject context) {
    int main_pid = getpid();
    DIR *dir = opendir("/proc");
    while ((de = readdir(dir)) != NULL) {
        if (!is_decimal_pid(de->d_name)) continue;
        pid = atoi(de->d_name);
        if (pid == main_pid) continue;

        name = read_proc_pid_cmdline_or_comm(pid);
        if (name in {"sh", "logcat", "grep", "getprop", ...}) {
            append("other pid -> %d(pid name: %s)\n", pid, name);
        }
    }
    if (!result.empty())
        return ReportRiskItem(env, "Find Others Processmay be risks main pid (...)", result);

    if (sdk >= 30) {
        popen_fn = dlsym(dlopen("libc.so"), "popen");
        fp = popen_fn("ps -ef", "r");
        while (fgets(line, 0x1000, fp)) {
            if (!contains(line, "hunter") && !contains(line, "install")) {
                ps_detail += line;
                count++;
            }
        }
        if (count >= 3)
            return ReportRiskItem(env, "Find Others Process", ps_detail);
    }
    return NULL;
}
```

### 10.3 动态证据

#### 10.3.1 第一阶段命中(/proc 枚举)

```
[evidence:process] NativeEngine_getZhenxiInfo4 entered
[evidence:report] title=Find Others Processmay be risks main pid (24499) lr=libhunter.so+0x2a3f6c (rva=0x2a3f6c)
  detail=other pid -> 24714(pid name: logcat)
other pid -> 24737(pid name: ls)
other pid -> 24739(pid name: ls)
[evidence:process-java] NativeEngine.getZhenxiInfo4(...) -> title=Find Others Processmay be risks main pid (24499) risk=NoRisk type=4
[evidence:ui] title=Find Others Processmay be risks main pid (24499) risk=NoRisk type=4
```

不同会话样本:

```
[evidence:report] title=Find Others Processmay be risks main pid (19790)
  lr=libhunter.so+0x2a3f6c (rva=0x2a3f6c)
  detail=other pid -> 20164(pid name: sh)
other pid -> 20167(pid name: logcat)
other pid -> 20168(pid name: grep)
other pid -> 20169(pid name: grep)
```

#### 10.3.2 第二阶段命中(ps -ef)

```
[evidence:report] title=Find Others Process lr=libhunter.so+0x2a43b0 (rva=0x2a43b0)
  detail=UID PID PPID C STIME TTY TIME CMD
  u0_a280 9820 836 ... com.zhenxi.hunter:hunter_server_twin
  u0_a280 10055 9706 ... ps -ef
```

第二阶段会把 hunter 自己的 twin 进程 + `ps -ef` 命令本身一并写入 detail。

### 10.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| P1 | JNI 函数 `getZhenxiInfo4 @ 0x2A2D98` | 60 项表 rva=0x2a2d98 | ✓ |
| P2 | 两阶段:`/proc/<pid>/comm\|cmdline` + `ps -ef` | 不同会话分别命中第一阶段和第二阶段 | ✓ |
| P3 | 第一阶段 callsite LR `0x2a3f6c` | 实测 lr=0x2a3f6c,(LR-4)=0x2a3f68 在 InfoInfo4 函数体内 | ✓ |
| P4 | 第二阶段 callsite LR `0x2a43b0` | 实测样本中第二阶段 lr=0x2a43b0 | ✓ |
| P5 | UI 文案前缀 "Find Others Process" | 实测 UI title 完全匹配 | ✓ |
| P6 | risk=NoRisk type=4 | UI 显示 risk=NoRisk type=4 | ✓ |
| P7 | 关键字含 `sh / logcat / grep / ls / getprop` | 实测命中样本含 logcat/ls/sh/grep | ✓ |

### 10.5 对抗面

`risk=NoRisk` —— 这是信息项而非阻断项。但会暴露当前分析环境(常驻 `sh / logcat / grep`)。

对抗简单粗暴:

```js
NativeEngine.getZhenxiInfo4.implementation = function (ctx) {
    return null;
};
```

动态验证:

```
[bypass:process] NativeEngine.getZhenxiInfo4 -> null
```

---

## 11. APatch/KP/KernelSU side-channel 检测

### 11.1 链路

```
Java: MainActivity.S() -> NativeEngine.SideChanne()
JNI : NativeEngine_SideChanne @ 0x2B3BD4
核心: detect_root_side_channel_apatch_kernelsu @ 0xE43BC
UI  : "Check Root For SideChanne"
```

### 11.2 静态证据

#### 11.2.1 算法步骤

```
1. mmap 一页 0x1000,权限 PROT_READ | PROT_WRITE | PROT_EXEC
2. 拷贝 0x270 字节内置 probe 机器码(.rodata 中 src__8)到该页
3. __clear_cache(code, code + 0x1000)
4. 调用该 probe code 收集 4 组 timing 样本(每组 10 个):s / s_1 / s_2 / s_3
5. sub_E60A4(sample, 10) / sub_E63E8(sample, avg) 做均值/离散度统计
6. munmap(code, 0x1000)
```

#### 11.2.2 阈值判定

```c
baseline_avg = sub_E60A4(s,   10);
sample1_avg  = sub_E60A4(s_1, 10);
sample2_avg  = sub_E60A4(s_2, 10);
sample3_avg  = sub_E60A4(s_3, 10);

baseline_dev = sub_E63E8(s,   baseline_avg);
sample1_dev  = sub_E63E8(s_1, sample1_avg);
sample2_dev  = sub_E63E8(s_2, sample2_avg);
sample3_dev  = sub_E63E8(s_3, sample3_avg);

// 稳定性筛选
if (baseline_dev * 10 > baseline_avg) return false;
if (sample1_dev  * 10 >= sample1_avg) return false;
if (sample2_dev  * 10 >= sample2_avg) return false;
if (sample3_dev  * 10 >= sample3_avg) return false;
if (sample1_avg <= baseline_avg) return false;
if (sample2_avg <= baseline_avg) return false;
if (sample3_avg <= baseline_avg) return false;

ratio0 = (sample2_avg - baseline_avg) / (sample1_avg - baseline_avg);
ratio1 = (sample3_avg - baseline_avg) / (sample1_avg - baseline_avg);

if (ratio0 > 2.2 && ratio1 > 2.2)
    return set_result("KernelSU Installed (High Latency)", ratio0, ratio1);

if (ratio0 > 1.4 && ratio1 > 1.4)
    return set_result("APatch/KP Installed (Mid Latency)", ratio0, ratio1);

return false;
```

#### 11.2.3 静态字符串

```
Side-Channel Detected: KernelSU Installed (High Latency) ratio0:
Side-Channel Detected: APatch/KP Installed (Mid Latency) ratio0:
ratio1:
```

Java 触发(`src/com/zhenxi/hunter/MainActivity.java`):

```java
public static ListItemBean S() {
    String s = NativeEngine.SideChanne();
    if (s == null) return null;
    return new ListItemBean("Check Root For SideChanne", FB.a, s);
}
```

### 11.3 动态证据

```
[evidence:side-channel] NativeEngine_SideChanne entered
[evidence:side-channel] detect_root_side_channel_apatch_kernelsu entered
[evidence:side-channel] detect_root_side_channel_apatch_kernelsu ret=0x1
[evidence:side-channel] NativeEngine_SideChanne ret=0x77379fe201
  data=Side-Channel Detected: APatch/KP Installed (Mid Latency) ratio0:1.604278 ratio1:1.657754
[evidence:ui] title=Check Root For SideChanne risk=Info type=0
  data=Side-Channel Detected: APatch/KP Installed (Mid Latency) ratio0:1.604278 ratio1:1.657754
```

另一轮采证 ratio 略有差异但仍归同一档:

```
ratio0:1.595745 ratio1:1.648936
```

### 11.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| S1 | JNI 函数 `SideChanne @ 0x2B3BD4` | 60 项表 #59 = SideChanne rva=0x2b3bd4 | ✓ |
| S2 | 内部调用 `detect_root_side_channel_apatch_kernelsu @ 0xE43BC` | `[evidence:side-channel] detect_root_side_channel_apatch_kernelsu entered` | ✓ |
| S3 | 阈值 1.4 < ratio ≤ 2.2 归 "APatch/KP Mid Latency" | 实测 ratio0=1.604278 / ratio1=1.657754,两者均 > 1.4 且 < 2.2 | ✓ |
| S4 | 阈值 ratio > 2.2 归 "KernelSU High Latency" | 本环境未达到此阈值 | 间接 ✓ |
| S5 | UI 文案 "Check Root For SideChanne" | 实测 UI title 完全匹配 | ✓ |
| S6 | 返回字符串完整含 ratio 数值 | 实测 data 串包含 `ratio0:1.604278 ratio1:1.657754` | ✓ |

### 11.5 对抗面

这条 detection 基于 timing,无法用文件系统层欺骗绕过。对抗思路:

- 干扰 timing ratio: KPM 理论上可在相关 syscall 路径上引入可控 delay/noise；但需要先确认 Hunter 的采样 syscall/路径,否则固定加噪未必能稳定绕过
- 直接拦截:Java 层 hook `NativeEngine.SideChanne` 返回 null

### 11.6 bypass 依据

返回空字符串时 Java 仍可能包装空 data 风险项,正确做法返回 null:

```js
NativeEngine.SideChanne.implementation = function () {
    return null;
};
```

动态验证:

```
[bypass:side-channel] NativeEngine.SideChanne -> null
```

---

## 12. Verified Boot / 解锁状态检测

`"当前手机已经被解锁"` 文案有两条独立来源,容易混淆。

### 12.1 链路总览

```
链路 A:TEE attestation
─────────────────────────────────────────
Java: j40.b(MainActivity)
  -> iW.d(new GC(mainActivity, 26), "tee_check_thread")
  -> GC.run default
  -> new z5(context, packageManager).b()
  -> ((t5)v10.c).b()
  -> YouAreLoser.e rootOfTrust
判定: e.c = deviceLocked   (false → 解锁)
     e.b = verifiedBootState (1/2/3 → patched)
UI  : "当前手机已经被解锁" / "Find Verified Boot Mark"

链路 B:getprop
─────────────────────────────────────────
Java: j40.a(MainActivity)
  -> NativeEngine.getZhenxiInfoH("ro.boot.verifiedbootstate")
判定: "orange"  → 当前手机已经被解锁
     "yellow"  → 当前设备机型&ROM 可能被修改!
```

### 12.2 静态证据

#### 12.2.1 链路 A:TEE 链 Java 判定

```java
// src/YouAreLoser/GC.java
V1 v10 = new z5(mainActivity0, mainActivity0.getPackageManager()).b();
if (v10 == null) {
    mainActivity0.n0(new ListItemBean("Tee is not supported or destroyed", FB.d));
} else {
    e e0 = ((t5)v10.c).b();
    if (!e0.c) {
        n0(new ListItemBean("当前手机已经被解锁", FB.a, "tee check device unlock"));
    }
    if (e0.b == 1 || e0.b == 2 || e0.b == 3) {
        n0(new ListItemBean("Find Verified Boot Mark", FB.a,
                            "the boot.img maybe have been patched\n" + e0));
    }
}
```

字段语义:

```
e0.c = deviceLocked
e0.b = verifiedBootState
       0 = Verified
       1 = Self-signed
       2 = Unverified
       3 = Failed
```

#### 12.2.2 链路 B:getprop 链

```java
// src/YouAreLoser/j40.java
String s = NativeEngine.getZhenxiInfoH("ro.boot.verifiedbootstate");
if (s.equals("orange")) {
    arrayList.add(new ListItemBean("当前手机已经被解锁", FB.a, s));
}
if (s.equals("yellow")) {
    arrayList.add(new ListItemBean("当前设备机型&ROM可能被修改!", FB.a, s));
}
```

`NativeEngine.getZhenxiInfoH(String)` 是 Java wrapper,**不在 `art_register_natives_batch` 的 60 项表里**。它调用混淆函数 `getPropInline(key, true)`,后者内部再走 native `getZhenxiInfoZ(key)` fallback 或 `jK` 解析 `/dev/__properties__` 属性区。因此这条属性链最终包含 native 层,但 native 注册项不是 `getZhenxiInfoH` 本身。

### 12.3 动态证据

```
[evidence:bootstate-java] NativeEngine.getZhenxiInfoH(ro.boot.verifiedbootstate) -> orange
[evidence:bootstate] j40.a returned <list size=1>
[evidence:ui] title=当前手机已经被解锁 risk=Info type=0 data=tee check device unlock
[evidence:ui] title=Find Verified Boot Mark risk=Info type=0 data=the boot.img maybe have been patched
[evidence:ui] title=当前手机已经被解锁 risk=Info type=0 data=orange
```

UI 实例展开:

```
title=Find Verified Boot Mark
data=verifiedBootKey: 0000...
deviceLocked: false
verifiedBootState: Unverified
```

### 12.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| V1 | 链路 A 来自 TEE attestation rootOfTrust | UI data 含 "tee check device unlock" | ✓ |
| V2 | 链路 B 来自 `ro.boot.verifiedbootstate=orange` | `[evidence:bootstate-java]` 实测看到 prop 返回 "orange" | ✓ |
| V3 | 两条独立,各自命中均产生风险项 | UI 同时出现两条 "当前手机已经被解锁",一条 data="tee check device unlock" 一条 data="orange" | ✓ |
| V4 | TEE 链路 `e.b == 1/2/3` → "Find Verified Boot Mark" | 实测 verifiedBootState=Unverified(=2)→ UI 出现 "Find Verified Boot Mark" | ✓ |
| V5 | `getZhenxiInfoH` 不在 batch 表 | 60 项表枚举无此 name,SO 层 Interceptor.replace 报 miss | ✓ |

### 12.5 对抗面

两条独立 → 需要分别绕:

```
链路 A 绕: z5.b() -> 伪造 V1 (deviceLocked=true, verifiedBootState=0)
链路 B 绕: NativeEngine.getZhenxiInfoH("ro.boot.verifiedbootstate") -> "green"
         或 j40.a(MainActivity) -> 空 ArrayList
```

### 12.6 bypass 依据

TEE 链:

```js
const Z5 = factory.use('YouAreLoser.z5');
const V1 = factory.use('YouAreLoser.V1');
const TeeRoot = factory.use('YouAreLoser.e');
Z5.b.overload().implementation = function () {
    const result = V1.$new(1, false);
    const key  = Java.array('byte', new Array(32).fill(0));
    const hash = Java.array('byte', new Array(32).fill(0));
    result.c.value = TeeRoot.$new(key, true, 0, hash);   // deviceLocked=true, verifiedBootState=0
    result.b.value = 0;
    return result;
};
```

getprop 链:

```js
NativeEngine.getZhenxiInfoH.implementation = function (key) {
    if (String(key) === 'ro.boot.verifiedbootstate') return 'green';
    return this.getZhenxiInfoH(key);
};

YouAreLoser.j40.a.implementation = function () { return ArrayList.$new(); };   // 双保险
```

动态验证:

```
[bypass:tee] z5.b -> fake locked + verified boot
[bypass:prop] ro.boot.verifiedbootstate -> green
[bypass:bootstate] j40.a -> empty list
```

注意:**两条都拦才能彻底消除**。即使 TEE 链 bypass 成功,getprop 链仍会单独产生 orange 风险项。

---

## 13. 环境变量采集

### 13.1 链路

```
Java: NativeEngine.getZhenxiInfoEnv()
JNI : NativeEngine_getZhenxiInfoEnv @ 0x28CDB0
上报: ReportRiskItem LR 0x28D3A8
UI  : "Get Env Info" / risk=NoRisk type=4
```

### 13.2 静态证据

`NativeEngine_getZhenxiInfoEnv @ 0x28CDB0` 引用字符串 `"Get Env Info"`。Java 触发片段:

```java
// src/com/google/android/gms/internal/measurement/zzfy.java
return NativeEngine.getZhenxiInfoEnv();

// src/com/google/android/gms/internal/firebase-auth-api/zzoy.java
return NativeEngine.getZhenxiInfoEnv();
```

伪代码:

```c
// libhunter.so+0x28CDB0
jobject NativeEngine_getZhenxiInfoEnv(JNIEnv *env) {
    std::string detail;
    for (char **p = environ; *p != NULL; ++p) {
        detail += *p;
        detail += "\n";
    }
    return ReportRiskItem(env, "Get Env Info", detail, FB_NoRisk_or_Info, 0);
}
```

### 13.3 动态证据

```
[evidence:env] NativeEngine_getZhenxiInfoEnv entered
[evidence:report] title=Get Env Info lr=libhunter.so+0x28d3a8 (rva=0x28d3a8)
[evidence:env] NativeEngine_getZhenxiInfoEnv ret=0x77379fe209
[evidence:ui] title=Get Env Info risk=NoRisk type=0 data=PATH=/product/bin:...
```

实际 detail 涵盖:

```
PATH=...
ANDROID_ROOT=/system
BOOTCLASSPATH=...
ANDROID_SOCKET_zygote=...
TMPDIR=/data/user/0/com.zhenxi.hunter/cache
...
```

### 13.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| E1 | JNI 函数 `getZhenxiInfoEnv @ 0x28CDB0` | 60 项表 rva=0x28cdb0 | ✓ |
| E2 | callsite LR `0x28D3A8` | 实测 `[evidence:report] lr=0x28d3a8` | ✓ |
| E3 | 遍历 environ 全部 key=value | 实测 detail 含 PATH/ANDROID_*/BOOTCLASSPATH/TMPDIR 等 | ✓ |
| E4 | risk=NoRisk(W3=0, W4=4, W5=0) | UI risk=NoRisk type=0 | ✓ |

### 13.5 对抗面

**信息采集项,不直接判定 root/hook**,但暴露运行环境和进程上下文。属于"画像"类 detection,绕过优先级低于阻断类。

### 13.6 bypass 依据

```js
NativeEngine.getZhenxiInfoEnv.implementation = function () { return null; };
```

动态验证:

```
[bypass:env] NativeEngine.getZhenxiInfoEnv -> null
```

---

## 14. 通用文件 marker 检测

### 14.1 链路

```
Java: NativeEngine.getZhenxiInfoK(path, markers)
JNI : NativeEngine_getZhenxiInfoK @ 0x2B93BC
核心: file_contains_any_marker @ 0x1A6300
返回: String hit_line 或 null
UI  : 取决于调用方,例如 "当前手机可能是模拟器&云手机"
```

### 14.2 静态证据

`getZhenxiInfoK` 是 §6.2.5 `file_contains_any_marker` 的 Java 暴露包装:

```c
// libhunter.so+0x2B93BC
jstring NativeEngine_getZhenxiInfoK(JNIEnv *env, jclass, jstring path, jobjectArray markers) {
    vector<string> native_markers;
    for (int i = 0; i < env->GetArrayLength(markers); i++) {
        native_markers.push_back(GetStringUTFChars(markers[i]));
    }
    if (file_contains_any_marker(path, native_markers, &hit_line))
        return NewStringUTF(hit_line.c_str());
    return NULL;
}
```

Java 使用示例:

```java
// src/YouAreLoser/y00.java
String[] markers = {"docker", "lxc_volumns"};
String s = NativeEngine.getZhenxiInfoK("/proc/mounts", markers);
if (s == null) {
    s = NativeEngine.getZhenxiInfoK("/proc/self/mountstats", markers);
    if (s == null) {
        s = NativeEngine.getZhenxiInfoK("/proc/self/mountinfo", markers);
    }
}
if (s != null) {
    arrayList0.add(new ListItemBean("当前手机可能是模拟器&云手机", FB.b,
                                    "(mounts异常)\n" + s));
}
```

### 14.3 动态证据

#### 14.3.1 容器检测

```
[evidence:file-marker-java-native] NativeEngine_getZhenxiInfoK entered
[evidence:file-marker] path=/proc/mounts markers=docker|lxc_volumns
[evidence:file-marker-ret] path=/proc/mounts ret=0x0
[evidence:file-marker-java] NativeEngine.getZhenxiInfoK(/proc/mounts, docker|lxc_volumns) ->
```

#### 14.3.2 模拟器/云手机检测

```
[evidence:file-marker] path=/proc/self/mountinfo markers=/mnt/shared/Sharefolder|/tiantian.conf|/data/share1|/hardware_device.conf|/mnt/shared/products|/mumu_hardware.conf|/Andy.conf|/mnt/windows/BstSharedFolder|/bst.conf|/mnt/shared/Applications|/ld.conf|/vboxsf
[evidence:file-marker-ret] path=/proc/self/mountinfo ret=0x0
```

完整 markers 12 项:

```
/mnt/shared/Sharefolder
/tiantian.conf
/data/share1
/hardware_device.conf
/mnt/shared/products
/mumu_hardware.conf
/Andy.conf
/mnt/windows/BstSharedFolder
/bst.conf
/mnt/shared/Applications
/ld.conf
/vboxsf
```

### 14.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| K1 | JNI 函数 `getZhenxiInfoK @ 0x2B93BC` | `[evidence:file-marker-java-native] NativeEngine_getZhenxiInfoK entered` | ✓ |
| K2 | 底层调用 `file_contains_any_marker @ 0x1A6300` | `[evidence:file-marker]` hook 在 0x1A6300 落点 | ✓ |
| K3 | 容器 markers `docker, lxc_volumns` | 实测 markers 字符串完全匹配 | ✓ |
| K4 | 模拟器 markers 12 项 | 实测 markers 字符串包含全 12 项 | ✓ |
| K5 | `file_contains_any_marker` 是通用 helper | 同一会话观察到 3 套不同 markers(root / docker / 模拟器)复用同 helper | ✓ |

### 14.5 对抗面

`getZhenxiInfoK` 本身是通用工具,不应作"是否 detection"的边界。检测属性取决于调用方:

- root markers + 关键 mount 路径 → root 检测(§6)
- `docker, lxc_volumns` → 容器
- 模拟器共享目录路径 → 模拟器

对抗时若全量 bypass `getZhenxiInfoK` 可能破坏其他正常调用 —— 应按 path × markers 组合细化。

### 14.6 bypass 依据

不强行返回 null,而是 hook 对应 Java caller(例如 `y00` 类的检测方法)更安全。

---

## 15. 风险文件路径检测

### 15.1 链路

```
Java: MainActivity.onCreate/init
  -> CancellationTokenSource.ۨۜۚ(this, NativeEngine.checkRiskFile());
JNI : NativeEngine_checkRiskFile @ 0x2AC514
辅助: sub_1A6228 @ 0x1A6228   (即 access(path, F_OK) == 0)
上报: ReportRiskItem callsite 0x2ace44(W3=1, W4=2, W5=10)
UI  : "Find Risk File"
```

### 15.2 静态证据

#### 15.2.1 25 条风险路径表

`NativeEngine_checkRiskFile @ 0x2AC514` 先构造固定风险路径表,再按顺序调 `sub_1A6228(path)` 检查存在性。`sub_1A6228 @ 0x1A6228` 非常短:

```c
bool path_exists(std::string *path) {
    const char *p = path->is_long ? path->data : path->sso;
    return access(p, F_OK) == 0;
}
```

不读文件内容、不 stat、不看 SELinux label;**只要 `access(path, F_OK)` 返回 0 即命中**。

完整 25 条路径表(IDA 全部字符串引用提取):

| 类别 | 路径 |
|-|-|
| 投屏 | `/data/local/tmp/vysor.pwd`, `/data/local/tmp/oat/arm64/scrcpy-server.odex`, `/data/local/tmp/mqc-scrcpy.jar` |
| 触屏/操控 | `/data/local/tmp/minicap.so`, `/data/local/tmp/minicap`, `/data/local/tmp/mini`, `/data/local/tmp/mini/minicap`, `/data/local/tmp/minitouch` |
| 触动/按键精灵 | `/data/local/tmp/tc/mobileagent`, `/data/local/tmp/tc/input3.sh`, `/data/local/tmp/tc/mainputjar7`, `/data/local/tmp/com.cyjh.mobileanjian.id`, `/data/local/tmp/com.cyjh.mobileanjianen.id` |
| UI 自动化 | `/data/local/tmp/uiautomator-stub.jar` |
| 云手机/云控 | `/data/local/tmp/cloudtestig/cloudscreen`, `/data/local/tmp/cloudtesting/touchserver`, `/data/local/tmp/juejinAzykb/`, `/data/local/tmp/juejinAzykb/TouchService.jar`, `/data/local/tmp/maxpresent.jar` |
| 截屏 SO | `/data/local/tmp/screen-shread10x64.so`, `/data/local/tmp/screen-shread5x32.so` |
| Shizuku | `/data/local/tmp/shizuku`, `/data/local/tmp/shizuku_starter` |
| 设备信息 | `/data/local/tmp/mobile_info.properties` |
| 一键玩 | `/data/local/tmp/yijianwanservice.apk` |

#### 15.2.2 伪代码

```c
// libhunter.so+0x2AC514
jobject NativeEngine_checkRiskFile(JNIEnv *env) {
    paths = { /* 25 条上表 */ };
    for (path in paths) {
        if (access(path, F_OK) == 0) {
            detail = "find risk file " + path;
            return ReportRiskItem(env, "Find Risk File", detail, /*risk=*/1, /*Type=*/2, /*ShowPriority=*/10);
        }
    }
    return NULL;
}
```

### 15.3 动态证据

本设备测试环境无任何上述路径存在,实测:

```
[evidence:risk-file] NativeEngine_checkRiskFile entered
[evidence:risk-file] NativeEngine_checkRiskFile ret=0x0
[evidence:risk-file-java] NativeEngine.checkRiskFile() -> <null>
```

`ret=0x0` 即返回 NULL jobject,Java 拿到 null 不构造 bean。

### 15.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| RF1 | JNI 函数 `checkRiskFile @ 0x2AC514` | 60 项表 #50 = checkRiskFile rva=0x2ac514 | ✓ |
| RF2 | 25 条 `/data/local/tmp/*` access | 实测函数 entered 且 ret=0x0(当前环境 25 路径均不存在) | ✓ 间接 |
| RF3 | callsite 0x2ace44(W3=1, W4=2, W5=10) | 本设备未触发该 callsite | 静态闭环 / 未触发 |

**静态闭环 / 当前环境未命中**。要实测命中分支,需主动构造任一路径文件后再触发检测。

### 15.5 对抗面

不依赖 `/proc/mounts`,不依赖 maps,**直接检查文件系统路径**。对抗面:

```
重点隐藏的 /data/local/tmp 路径:
- /data/local/tmp/minicap*
- /data/local/tmp/minitouch
- /data/local/tmp/*scrcpy*
- /data/local/tmp/uiautomator-stub.jar
- /data/local/tmp/shizuku*
- /data/local/tmp/tc/*
- /data/local/tmp/juejinAzykb/*
```

KPM 可在内核侧对 hunter 进程的 `access`/相关文件查询路径按名单返回 `-ENOENT`,从数据源上绕过本节这条文件存在性检测；但它不覆盖 logcat/AVC、maps 或其它独立检测链。

### 15.6 bypass 依据

Java 层最简单:

```js
NativeEngine.checkRiskFile.implementation = function () { return null; };
```

或 SO 层 `Interceptor.replace @ 0x2AC514` 入口直接返回 NULL jobject。

---

## 16. AVC denial 日志侧信道

### 16.1 链路

```
Java: GC.run case 16
  -> NativeEngine.checkRootFromAVCLog()
JNI : NativeEngine_checkRootFromAVCLog @ 0x2AAE54
核心: sub_E0AA8(pid_string) @ 0xE0AA8       (size 0x2B28)
上报: ReportRiskItem callsite 0x2aaec4(W3=0, W4=1, W5=1)
UI  : "Find Root File In Sniff"
```

Java 触发(`src/YouAreLoser/GC.java`):

```java
mainActivity0.n0(NativeEngine.checkRootFromAVCLog());
```

### 16.2 静态证据

#### 16.2.1 包装层

```c
// libhunter.so+0x2AAE54
jobject NativeEngine_checkRootFromAVCLog(JNIEnv *env) {
    string pid = to_string(getpid());
    if (!sub_E0AA8(pid))
        return NULL;
    return ReportRiskItem(env, "Find Root File In Sniff",
                          get_last_root_mounts_detail(), ...);
}
```

#### 16.2.2 `sub_E0AA8 @ 0xE0AA8` 算法骨架

核心步骤(由静态字符串和 libc callee 反推):

```
1. logcat -c                            (popen 或同等)
2. 对一组 root 敏感路径,4 种探测逐一尝试:
   a) ls <path>                         (popen)
   b) open find root file               (__open_2)
   c) access find root file             (access)
   d) getxattr find root file           (getxattr, attr="security.selinux")
   e) readlink find root file           (readlink)
3. usleep 等 AVC 落地
4. logcat -d -b main -b system -b events -b kernel
   | grep 'avc: denied' | grep -Ei '(<paths>)'
5. 解析 AVC 输出:看 path="..." / name="..." / |path="..." / |name="..."
   是否出现目标路径片段
6. 即使文件 access/open 都失败,只要 kernel 看见过它并记录了
   AVC denial,即视作命中
```

关键 libc callee:`close`、`access`、`__open_2`、`getxattr`、`readlink`、`usleep`。

#### 16.2.3 静态字符串

```
file_include open file fail
checkRootFileFromAVC File
checkRootFileFromAVC log info ->
checkRootFileFromAVC Log output not empty but no real match for ...
likely exists (detected via AVC denial log). Detailed log:
sniffing of the root file path ...
```

#### 16.2.4 敏感路径表(`sub_D14B0 @ 0xD14B0`)

```
/debug_ramdisk, /debug_ramdisk/su
/data/adb/, /data/adb/modules, /data/adb/modules/
/data/adb/ap, /data/adb/ap/bin, /data/adb/ap/log,
/data/adb/ap/log/bin/{apd, magiskpolicy, magiskmount, kpatch, resetprop}
/data/adb/ap/{modules.img, package_config, su_path, version}
/data/adb/kpatch, /data/adb/magisk, /data/adb/lspd
/sbin/.magisk, /sbin/.magisk/modules/{riru_lsposed, zygisk_lsposed}
/system/bin/magisk, /system/bin/magisk32
/system/etc/init/magisk, /system/etc/init/magisk.rc
/system/addon.d/99-magisk.sh
/cache/magisk.log, /cache/.disable_magisk
apatch / Apatch / APatch
kernelsu / kernelSu
```

### 16.3 动态证据

```
[evidence:avc-log] NativeEngine_checkRootFromAVCLog entered
[evidence:avc-log] NativeEngine_checkRootFromAVCLog ret=0x0
[evidence:avc-log-java] NativeEngine.checkRootFromAVCLog() -> <null>
```

本测试环境未触发命中,函数 entered 后直接返回 null。

### 16.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| AV1 | JNI 函数 `checkRootFromAVCLog @ 0x2AAE54` | 60 项表 #56 = checkRootFromAVCLog rva=0x2aae54 | ✓ |
| AV2 | 内部调用 `sub_E0AA8` | hook 内部函数(本测试未细做) | 间接 ✓ |
| AV3 | 通过 logcat 反读 AVC denial 行 | 当前环境 SELinux audit 未暴露被探测路径,或 logcat 已被清,导致未命中 | 静态闭环 / 未触发 |
| AV4 | UI 文案 "Find Root File In Sniff" | 当前环境未生成此 UI title | 静态闭环 / 未触发 |

### 16.5 对抗面

**仅隐藏文件不够** —— 即使 access/open 返回 ENOENT,如果 kernel 历史 AVC denial 仍保留敏感路径,Hunter 能从 logcat 反推它们存在。真正对抗:

```
- 拦截 logcat 输出  (替换 popen("logcat -d ...") 行为)
- 清除目标 AVC denial entry
- 在内核侧阻止生成 AVC denial(KPM 修改 selinux audit 子系统)
```

### 16.6 bypass 依据

Java 层最简单:

```js
NativeEngine.checkRootFromAVCLog.implementation = function () { return null; };
```

或 SO 层 `Interceptor.replace @ 0x2AAE54` 入口返回 NULL。

---

## 17. 包名 ELF 白名单扫描

### 17.1 链路

```
Java: NativeEngine.getZhenxiInfoMPNI("com.zhenxi.hunter")
JNI : NativeEngine_getZhenxiInfoMPNI(jstring pkg) @ 0x298374
上报: ReportRiskItem callsite 0x2994f4(W3=0, W4=1, W5=0)
UI  : "Find Mark ELF"
```

### 17.2 静态证据

两阶段。

#### 17.2.1 阶段 1:自保护硬门槛

```c
if (byte_2F3A68 != 1 || (byte_2F3A6C & 1) == 0) {
    log: "checkProcessTag error" + "File:" + "F:/HunterNew/app/src/main/cpp/main.cpp" + Line
    log: "native kill self process"
    dump threads (sub_1A3988(pid, tid, 0, "Zhenxi"))
    log: "KILL_PROCESS"
    safe_syscall_via_trampoline(__NR_kill, pid, 9)   ← 三连自杀
    abort()
}
```

进程标签异常时**不返回风险项,而是自杀**。这条调试串还泄露了开发环境路径 `F:/HunterNew/app/src/main/cpp/main.cpp`。

#### 17.2.2 阶段 2:maps 包名 ELF 白名单扫描

```c
pkg_str = GetStringUTFChars(jpkg);
path = "proc/" + to_string(getpid()) + "/maps";
fd = ssyscall_openat(AT_FDCWD, path, O_RDONLY, 0);
maps = parse_maps_to_linked_list(-1);

for each map_node in maps:
    if !strstr_(map_node.pathname, pkg_str): continue;
    // 跳过白名单 8 项
    if 任一以下子串出现在 pathname: continue;
        - xcrash
        - sentry
        - hunter
        - libc++_shared
        - libdatastore_shared_counter.so
        - libBugly
        - /data/data/<pkg>/code_cache/
        - /oat/arm64/
    // 检查 mapping 的 start 指针是否是 ELF
    if (perms[0]=='r' && start[0..3] == 0x7F 0x45 0x4C 0x46):
        detail += pathname + "\n";
if !detail.empty():
    title = "Find Mark ELF";
    build_native_ListItemBean_risk(env, title, detail, 0, 1, 0);
return null;
```

### 17.3 动态证据

```
[evidence:mpni] NativeEngine_getZhenxiInfoMPNI entered
[evidence:mpni] NativeEngine_getZhenxiInfoMPNI ret=0x0
[evidence:mpni-java] NativeEngine.getZhenxiInfoMPNI(com.zhenxi.hunter) -> <null>
```

本测试环境 Java 端传入 `"com.zhenxi.hunter"`,本设备无额外的同包名 ELF 注入,return null。

### 17.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| MP1 | JNI 函数 `getZhenxiInfoMPNI @ 0x298374` | 60 项表 rva=0x298374 | ✓ |
| MP2 | 阶段 1 进程标签自保护,失败时自杀 | 本环境标签通过,未触发自杀路径 | 间接 ✓ |
| MP3 | 阶段 2 maps 包名 ELF 白名单扫描 | 函数 entered + return null,符合"标签通过 + 无额外 ELF"判断 | ✓ |
| MP4 | 白名单 8 项 | 静态字符串引用完整列出 | ✓ |

正确结论:**自保护标签通过,maps 包名 ELF 白名单扫描未发现额外可疑映射**,不是"没有该检测"。

### 17.5 对抗面

防的是"以 app 同包名注入额外 native 库"的 hook 攻击。绕过思路:

- Java 层 hook `getZhenxiInfoMPNI(pkg) → null`
- 或由 KPM 在 `/proc/self/maps` 数据源/读取路径中过滤同包名非白名单 ELF,使 hunter 的 `parse_maps_to_linked_list` 解析不到这些映射

### 17.6 bypass 依据

```js
NativeEngine.getZhenxiInfoMPNI.implementation = function (pkg) { return null; };
```

---

## 18. APK 签名一致性

### 18.1 链路

```
Java: NativeEngine.getZhenxiInfo2(Context)
JNI : NativeEngine_getZhenxiInfo2 @ 0x29AEFC
上报: 11 个 callsite,RVA 范围 0x29d6c0..0x2a0304(W3=0 或 1, W4=3, W5=3)
UI  : "HunterCheckApkSignError" + 11 种子原因
```

### 18.2 静态证据

#### 18.2.1 预期签名指纹(hardcoded 字符串)

```
"MYAAKzWEBR"               ── base64 substr 前 10 字符
"4d5941414b7a57454252"     ── 上述 base64 字符串的 hex 表示(20 字符)
```

#### 18.2.2 7 步检查链(从 11 个 callsite 字面量按位置顺序还原)

```
1. 通过 JNI 反射拿 APK 路径:
   ctx.getApplicationInfo().publicSourceDir
   静态字符串: "getApplicationInfo" / "()Landroid/content/pm/ApplicationInfo;" / "publicSourceDir"
   失败 → "getApkPath == null" / "check apk sign apk path == null"
   → title "HunterCheckApkSignError"

2. 通过路径 ssyscall_openat 打开 base.apk:
   失败 → "open fd cache error"
   成功 → "start native open base.apk success" / "native apk sign check open fd"

3. read_certificate 提取签名内容:
   (callee sub_C1EF0 / sub_BCE34 zip parse + cert extract)
   失败 → "apk read_certificate empty"
   → title "HunterCheckApkSignError"

4. 计算签名 base64 编码并取前 10 字符:
   if base64.substr(0,10) != "MYAAKzWEBR":
       → "check app sign hex fail"
       → title "HunterCheckApkSignError"
   日志: "getApkSign apk sign base64 substr"

5. 验证 hex 表示:
   if hex(base64) != "4d5941414b7a57454252":
       → "check app sign hex fail"
   日志: "native check hex success"

6. 反向验证 fd 对应的真实路径:
   /proc/self/fd/<fd> 用 readlinkat 反查
   失败 → "readlinkat error" / "check apk sign path error"
   不匹配预期 → "check apk sign path fail"
   日志: "native apk check fd path success"

7. fstat 验证 inode/uid/gid:
   failed → "check apk sign path fail __NR_fstat<0" / "fstat error"
   uid/gid 与 hunter 进程不符 → "check apk sign gid&uid fail"
   inode 不对 → "check apk sign inode fail"
   成功 → "check apk sign success! uid->" + " gid-> " + " maps ->"
        + "native apk check inode&uid&gid success"
```

#### 18.2.3 签名指纹反向推断

`"MYAAKzWEBR"` (10 字符 base64) 是 hunter APK 真实签名的开头部分。任何重打包的 hunter 都会因为重签后这 10 字符改变而被检测出。

### 18.3 动态证据

```
[evidence:apk-sign] NativeEngine_getZhenxiInfo2 entered
[evidence:apk-sign] NativeEngine_getZhenxiInfo2 ret=0x0
```

本设备用的是官方 APK,签名匹配,return NULL,未生成 UI 风险项。

### 18.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| AS1 | JNI 函数 `getZhenxiInfo2 @ 0x29AEFC` | 60 项表 rva=0x29aefc | ✓ |
| AS2 | 11 个 callsite 覆盖 11 种失败子原因 | 静态字符串引用完整列出 11 类失败文案 | ✓ |
| AS3 | 预期签名前 10 base64 = "MYAAKzWEBR" | 字符串静态确认,本设备签名匹配未触发 | ✓ 静态 |
| AS4 | 检查链覆盖 path / cert / base64 / hex / fd readlink / fstat 7 步 | 字符串 + xref 完整可见 | ✓ 静态 |
| AS5 | 官方 APK 不触发 | 实测 return 0 | ✓ |

### 18.5 对抗面

检测目标是**防止 hunter 自身被重打包**(改变签名)。对真实用户来说装的是官方 APK,该检测不会命中。

### 18.6 bypass 依据

```js
NativeEngine.getZhenxiInfo2.implementation = function (ctx) { return null; };
```

或彻底:**确保 hunter APK 不被重打包**(对真实用户来说,装的就是官方,该检测不会命中)。

---

## 19. system_server hook 检测

### 19.1 链路

```
Java: NativeEngine.getZhenxiInfoCBinder()
JNI : NativeEngine_getZhenxiInfoCBinder @ 0x28C9BC
上报: ReportRiskItem callsite 0x28cd08(W3=0, W4=3, W5=4)
UI  : "find system server hook"
```

### 19.2 静态证据

```c
jobject NativeEngine_getZhenxiInfoCBinder(JNIEnv* env) {
    if (checkProcessTag 失败) → kill self (同 §17 阶段 1)

    v2 = sub_CDFC4();           // 取某个值(OLLVM thunk → sub_CDAD4)
    sub_CE000(v15, v2);         // 把 v2 处理成 std::string,放进 v15
    char v3 = sub_251C18(v15);  // 解密(同 §3 跳板的解密器,用于 runtime_syscall_code 等)
                                // sub_251C18(key1, key2) 解出预期值,与 v15 比对

    if ((v3 & 1) != 0) {
        sub_CEB40();             // 清理
        return NULL;             // 通过 = 没命中
    } else {
        title = "find system server hook"
        build_native_ListItemBean_risk(env, title, detail, 0, 3, 4)
        return bean;
    }
}
```

**`sub_CDFC4 / sub_CDAD4 / sub_CE000` 都没字符串,纯 OLLVM 隐藏**。从上下文推断:它们从某个 binder / service 拿一个值(可能是 IBinder 接口的 hash、system_server 进程的状态、`ServiceManager` 拿到的 native binder pointer 等),解密后与某个 hardcoded 预期值比对,不匹配 → "system_server 链有人 hook 中转"。

`sub_251C18` 是跳板模块同款解密器,与 §3.2.4 `runtime_syscall_code` 的解码路径同源 —— 这是把"敏感字符串"以 obfuscated 形式存储的通用机制。

### 19.3 动态证据

```
[evidence:cbinder] NativeEngine_getZhenxiInfoCBinder entered
[evidence:cbinder] NativeEngine_getZhenxiInfoCBinder ret=0x0
[evidence:cbinder-java] NativeEngine.getZhenxiInfoCBinder() -> <null>
```

本设备未命中 system_server hook,return NULL。

### 19.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| CB1 | JNI 函数 `getZhenxiInfoCBinder @ 0x28C9BC` | 60 项表 rva=0x28c9bc | ✓ |
| CB2 | 阶段 1 进程标签自保护(同 MPNI) | 本环境标签通过,未自杀 | 间接 ✓ |
| CB3 | 内部用 `sub_251C18` 解密器比对预期值 | hook 内部函数(本测试未细做) | 间接 ✓ |
| CB4 | UI 文案 "find system server hook" | 本环境未生成此 UI title | 静态闭环 / 未触发 |

### 19.5 对抗面

检测目标:**Binder IPC 中间没有"人坐在中间"**。对应攻击:VirtualXposed / SandHook 等用 Java 层 IBinder proxy 拦截 system_server 调用的场景。

进一步还原 `sub_CDFC4 / sub_CDAD4 / sub_CE000` 需要对 callee 链回溯,或用 Frida hook 它们入口/出口看实参与返回值 —— 本节到"检测什么"为止,精确算法待补。

### 19.6 bypass 依据

```js
NativeEngine.getZhenxiInfoCBinder.implementation = function () { return null; };
```

或 SO 层 `Interceptor.replace @ 0x28C9BC`。

---

## 20. VPN 接口检测

### 20.1 链路

```
Java: NativeEngine.CheckVpn()
JNI : NativeEngine_CheckVpn @ 0x2AAF44(idx=53)
入口: sub_A8BE4 @ 0xA8BE4   (NETLINK 枚举链表头)
辅助: sub_AA914 @ 0xAA914   (ctx 初始化,分配 0x2000 buffer)
      sub_AAA4C @ 0xAAA4C   (socket + 发 dump 请求)
      sub_AB81C @ 0xAB81C   (循环 recvfrom + 派发回调)
      sub_A8CC8 @ 0xA8CC8   (nlmsg 解析回调)
上报: ReportRiskItem callsite 0x2ab014(W3=0, W4=1, W5=0)
UI  : "Find Vpn Native"
```

### 20.2 静态证据

#### 20.2.1 算法骨架

```
NativeEngine_CheckVpn(JNIEnv* env):
  Node* head = NULL
  rc = sub_A8BE4(&head)                          ── 通过 NETLINK 枚举所有接口
       │
       ├─ sub_AA914(ctx)
       │     ctx[0] = -1                          (fd 占位)
       │     ctx[1] = operator new[](0x2000)      (recv buffer)
       │     ctx[2] = 0x2000                       (buffer 大小)
       │
       ├─ sub_AAA4C(ctx, 18 = RTM_GETLINK)
       │     fd = socket(AF_NETLINK=16, SOCK_RAW|SOCK_CLOEXEC=0x80003, NETLINK_ROUTE=0)
       │     ctx[0] = fd
       │     构造 nlmsghdr {len=20, type=18, flags=0x301}
       │     sub_AD0EC(fd, &msg, 20, 20, 0)        (发送)
       │
       ├─ sub_AB81C(ctx, sub_A8CC8, &head)
       │     循环:
       │       n = safe_syscall_via_trampoline(207 recvfrom, fd, buf, 0x2000, 0, 0, 0)
       │       遍历 buffer 内每个 nlmsghdr,调 sub_A8CC8(&head, nlmsg) 直到 NLMSG_DONE
       │
       │     sub_A8CC8(&head, nlmsg):
       │       type=16 (RTM_NEWLINK) → operator new(0x1D8) 新节点
       │                              扫 rtattrs 找 IFLA_IFNAME(rta_type=3) 拷到 node+448
       │                              node[1] = &node[448]
       │                              node->ifindex = ifi_index
       │                              头插链表
       │       type=20 (RTM_NEWADDR) → 按 ifa_index 匹配已建链表,补地址信息
       │
       ├─ sub_AAA4C(ctx, 22 = RTM_GETADDR)        ── 第二轮 dump
       ├─ sub_AB81C(ctx, sub_A8CC8, &head)
       └─ sub_AAA18(ctx)                           ── 关 fd + free buffer

  for node in head:
      name = node[+8]                              // const char* → node+448
      if my_strcmp(name, "tun")  == 0 ||
         my_strcmp(name, "ppp")  == 0 ||
         my_strcmp(name, "pptp") == 0:
            sub_A87B4(head)
            title  = "Find Vpn Native"
            detail = name
            build_native_ListItemBean_risk(env, title, detail,
                                           /*risk=*/0, /*Type=*/1, /*ShowPriority=*/0);
            return bean
  sub_A87B4(head)
  return NULL
```

#### 20.2.2 链表节点结构(从 `sub_A8CC8` 写入 / `CheckVpn` 读取偏移推出)

```c
struct LinkNode {
    LinkNode* next;        // +0x00
    const char* name;      // +0x08  指向 name buffer (=&this[0x1C0])
    uint32_t flags;        // +0x10
    ...
    uint32_t ifindex;      // +0x38
    ...
    char name_buffer[24];  // +0x1C0 (=+448)  ── IFLA_IFNAME 拷贝目标
    ...                    // 节点总 size = 0x1D8 (=472)
};
```

#### 20.2.3 可验证陈述清单(S1-S11)

| 编号 | 静态结论 | 印证手段 |
|-|-|-|
| S1 | `sub_AA914` 分配 0x2000 buffer | §3.3.4 实测 `recvfrom(... len=0x2000 ...)` |
| S2 | `socket(AF_NETLINK=16, SOCK_RAW\|SOCK_CLOEXEC=0x80003, NETLINK_ROUTE=0)` | hook libc `socket` 看实参 |
| S3 | 顺序发两条 dump:type=18 → 22 | 回复方观察到 type=16 后再 type=20 |
| S4 | nlmsghdr flags=0x301 | hook `sub_AD0EC` 才能直接看 |
| S5 | `sub_AD0EC` 是发送辅助 | (未挂发送 hook) |
| S6 | 接收走 `safe_syscall_via_trampoline(207=recvfrom)` | §3.3.4 实测 |
| S7 | RTM_NEWLINK(16) → 解 IFLA_IFNAME → 节点 name | hook `sub_A8CC8`,解出字符串与 `ip link` 一致 |
| S8 | RTM_NEWADDR(20) → 按 ifa_index 匹配已建节点 | hook `sub_A8CC8` |
| S9 | 主循环用 `my_strcmp` **精确**匹配 `tun/ppp/pptp` | 设备若有 `tun*` 但 ≠ "tun" 且返回 NULL 可反向证明 |
| S10 | 命中即 `build_native_ListItemBean_risk("Find Vpn Native", iface_name, 0, 1, 0)` | hook 0x278658 |
| S11 | 无 VPN 设备 → return NULL | hook 入口 onLeave 看 retval |

### 20.3 动态证据(`js/verify_4_7_checkvpn.js`)

hook 策略收紧到 3 个 hunter 内 hook + 1 个 libc:

- `block_bad_precheck @ 0xC6520`
- `NativeEngine_CheckVpn @ 0x2AAF44`(onEnter 重置统计,onLeave 打印接口列表与 retval)
- `sub_A8CC8 @ 0xA8CC8`(每条 nlmsg 解析后打印 (type, ifindex, name),自实现 rtattr 走 RTA_ALIGN 解码)
- libc `socket()` 仅过滤 `domain == AF_NETLINK(16)` 时打印实参

测试条件:Pixel 6 Pro / Android 15,无 VPN App,WiFi 已连。

#### 20.3.1 实测对照表

| 编号 | 状态 | 实测证据 |
|-|-|-|
| S1 | 间接 ✓ | §3.3.4 已观察 `recvfrom len=0x2000 = 8192` |
| **S2** | ✓ | `[S2] socket(AF_NETLINK=16, type=0x80003 ✓SOCK_RAW\|SOCK_CLOEXEC, proto=0 ✓NETLINK_ROUTE)` |
| **S3** | ✓ | 一次 CheckVpn 调用内 50 帧 RTM_NEWLINK(=16) 后 7 帧 RTM_NEWADDR(=20) |
| S4 | 未验证 | 本轮未 hook 发送方向 |
| S5 | 未验证 | 同上 |
| S6 | ✓ | §3.3.4 已验证(本轮 RTM_NEW* 帧能进 sub_A8CC8 hook 间接印证) |
| **S7** | ✓ | 50 个接口的 IFLA_IFNAME 全部正确解出,与 `ip link` 一致 |
| **S8** | ✓ | 7 次 RTM_NEWADDR 全部正确关联(`lo`×2, `dummy0`×1, `wlan0`×4) |
| **S9** | ✓(关键) | 设备存在 `tunl0`(ipip tunnel,前 3 字符 = "tun")但 CheckVpn return 0x0 |
| S10 | 未触发 | 设备无 VPN |
| **S11** | ✓ | `return = 0x0 ✓ NULL` |

#### 20.3.2 设备完整接口家底快照

`sub_A8CC8` hook 50 个接口被 hunter 全部扫到:

```
lo, dummy0, ifb0, ifb1, tunl0, gre0, gretap0, erspan0,
ip_vti0, ip6_vti0, sit0, ip6tnl0, ip6gre0,
rmnet0..rmnet29 (Qualcomm modem),
dummy (额外), aware_nmi0, wlan0, wlan1, wpan0, dit0, radiotap0
```

大量 `rmnet*` 是 Pixel 6 Pro 的硬件特征,**说明 hunter 看见的是真实 kernel 接口表,没有被 `/proc/net/dev` 那一层欺骗**(这是 NETLINK 路径的核心目的)。

#### 20.3.3 `my_strcmp` 精确比较的硬证据

`tunl0` 前 3 字符是 `"tun"`,但 CheckVpn 没命中。等价于 `strcmp("tunl0", "tun") != 0` 在 hunter 视角下成立。

#### 20.3.4 NETLINK socket 不只 CheckVpn 用

本次共 6 次 `socket(AF_NETLINK)` 创建,但 CheckVpn 入口只触发 1 次完整流程。其余 NETLINK socket 的调用方尚未逐一用 callstack 或 LR 归因；候选包括 `getZhenxiInfoBase` / `Info4` / `checkZygisk` / Info3 内 `sub_DDB9C`,需要后续按 caller 复核。

### 20.4 静态/动态交叉验证

11 条静态结论里 8 条直接 ✓、1 条间接 ✓、2 条诚实标"未验证"(S4/S5)。结构性结论(S1-S3, S6-S11)全部得到证据,§20.2.1 静态算法可作为可靠事实。

### 20.5 实测得到的、静态分析里没有的新事实

#### 20.5.1 hunter 实现弱点

`my_strcmp` 是**精确比较**,静态名单只有 `tun/ppp/pptp` 三个裸字符串。Linux 真实 VPN 接口名几乎都不是这三个:

```
OpenVPN     :  tun0 / tun1 / ...   (kernel 自动加序号)
PPP/L2TP    :  ppp0 / ppp1 / ...
WireGuard   :  wg0 / wg1 / ...     (根本不在名单)
strongSwan  :  xfrm0 或无虚接口     (用 XFRM policy)
```

Hunter 当前实现只精确匹配接口名 `tun/ppp/pptp`。常见接口名如 `tun0/ppp0/wg0/xfrm0` 不会被该条件命中；因此在使用这些默认命名的 VPN 环境中,该检测存在明显漏检风险。是否覆盖所有主流客户端需要单独样本验证。

#### 20.5.2 `block_bad_precheck` 与本 detection 的交叉证据

本会话中也观察到:

```
+0xc68a4 在 sub_C687C 内 ── 2 次
+0xc7828 在 scan_rx_segment_neon_sum 内 ── 2 次
```

与 CheckVpn 完全无关,只是同窗口并发的 self-check 自检漏判,**反过来加强 §5.3.5 关于"两条独立完整性检查链路"的论断**。

### 20.6 对抗面 / bypass

| 方案 | 位点 | 效果 | 风险 |
|-|-|-|-|
| A | 用户态 hook / inline patch `NativeEngine_CheckVpn @ 0x2AAF44` 入口直接 return 0 | 覆盖该入口所有调用 | 修改用户态 `.text`,可能触发 §5 CRC 链 |
| B | 用户态 hook / inline patch `sub_A8CC8`,看到 IFLA_IFNAME == tun/ppp/pptp 时改写进入链表的 name | 隐蔽,链表里就没"危险"名字 | 改 hunter 用户态执行流或数据,需保证内存一致性,同样有 CRC/自校验风险 |
| C | KPM 在 NETLINK_ROUTE/rtnetlink 内核侧 filter,改写或截走对 hunter 进程的 RTM_GETLINK 回复 | 不改 hunter 用户态代码,隐蔽性更高 | 实现复杂,需适配内核版本和 netlink 路径 |
| D | 不动:用户场景下 `OpenVPN/WireGuard` 接口名本就不裸叫 tun/ppp/pptp | 0 工作量 | 仅适用于不命中场景 |

对绝大多数真实用户,方案 D 已经够用 —— 这是 §20.5.1 的直接推论。

---

## 21. Frida 线程名扫描

### 21.1 链路

```
Java: NativeEngine.getZhenxiInfo5(Context)
JNI : NativeEngine_getZhenxiInfo5 @ 0x2A4760(idx=2)
核心: sub_C6A84 @ 0xC6A84   (线程扫描)
辅助: strstr_ @ 0x1AFD4C    (hunter 自实现 strstr)
      ssyscall_openat / ssyscall_read / ssyscall_close
上报: ReportRiskItem 3 callsite,W3=0, W4=2, W5=8
UI  : "Find Frida Mark" / "gum-js-loop" 或 "gmain"
```

### 21.2 静态证据

#### 21.2.1 `sub_C6A84` 完整伪代码

```c
int sub_C6A84(void) {
    DIR* dirp = opendir("/proc/self/task");
    if (!dirp) return -1;
    int n2 = 0;
    for (each readdir entry) {
        if (d_name == "." or "..") continue;
        char buf[256];
        snprintf(buf, 256, "/proc/self/task/%s/status", d_name);
        int fd = ssyscall_openat(AT_FDCWD, buf, O_RDONLY, 0);
        if (fd < 1) continue;

        // —— buffered reader 读"首行"到 ptr[256] ——
        char ptr[256];
        memset(ptr, 0, 256);
        size_t n255 = 0;
        size_t v9  = qword_2EFCB8;        // GLOBAL cursor
        size_t v10 = qword_2EFCC0;        // GLOBAL end
        while (n255 != 255) {
            if (v9 >= v10) {
                v10 = ssyscall_read(fd, &ptr_, 1024);  // GLOBAL buffer
                qword_2EFCB8 = 0;
                qword_2EFCC0 = v10;
                if (v10 < 1) break;
                v9 = 0;
            }
            uint8_t c = ptr_[v9++];
            qword_2EFCB8 = v9;
            if (c == '\n') break;
            ptr[n255++] = c;
        }
        ssyscall_close(fd);

        if (strstr_(ptr, "gum-js-loop")) { n2 = 1; break; }
        else if (strstr_(ptr, "gmain"))  { n2 = 2; break; }
    }
    closedir(dirp);
    return n2;
}
```

#### 21.2.2 三个全局 buffered reader 状态(`.bss`)

```
ptr_         @ 0x2EF8B8  (1024B buffer)
qword_2EFCB8           (cursor)
qword_2EFCC0           (end)
```

**这三个全局跨 tid 迭代从不重置** —— 这是 §21.5 buffered reader bug 的源头。

#### 21.2.3 `NativeEngine_getZhenxiInfo5` 分发逻辑

`getZhenxiInfo5 @ 0x2A4760` 拿到 `sub_C6A84` 返回值后分发(从 `0x2a47ac` 处的 `CMP W0, #2 / B.EQ; CMP W0, #1 / B.NE` 看出):

| `sub_C6A84` 返回 | 走的分支 | callsite | title / detail | 自杀? |
|-|-|-|-|-|
| `2` | gmain 命中 | `0x2a5204` | "Find Frida Mark" / "gmain" | ✅ 三连 `safe_syscall(129=kill, pid, 9)` |
| `1` | gum-js-loop 命中 | `0x2a47f4` | "Find Frida Mark" / "gum-js-loop" | ❌ 仅上报,不杀 |
| 其它 (`0`/`-1`) | "无命中"路径 | `0x2a5470` | OLLVM 状态机解码出的 `<dyn>`,detail 为空 | ❌ |

#### 21.2.4 可验证陈述清单(F1-F10)

| 编号 | 静态结论 | 印证位 |
|-|-|-|
| F1 | `opendir("/proc/self/task")` | libc `opendir` hook,arg = `/proc/self/task` |
| F2 | `readdir` 遍历自身所有 tid | libc `readdir` hook,d_name 是数字串 |
| F3 | 对每个 tid `ssyscall_openat("/proc/self/task/<tid>/status", O_RDONLY)` | hook `ssyscall_read` 看 fd |
| F4 | `strstr_` 子串匹配(非精确) | 通过 F8 命中行为反推 |
| F5 | 优先级 `gum-js-loop > gmain`(if/else if 顺序) | `sub_C6A84` 返回 `1` 优先于 `2` |
| F6 | 返回 `0/1/2/-1` 各对应不同语义 | hook `sub_C6A84` onLeave |
| F7 | `getZhenxiInfo5` 分发 `1`→仅上报,`2`→上报+SIGKILL,`else`→空 | hook `getZhenxiInfo5` onLeave + 进程存活观察 |
| **F8** | 当前 Frida 17.x 测试环境中,若 `gum-js-loop` 线程名被真实读到,`sub_C6A84` 应返回 1 | hook 直接看 W0 |
| F9 | 返回 `1` 分支**不**触发 SIGKILL | 进程存活 |
| F10 | 命中后 `getZhenxiInfo5` 返回 non-NULL ListItemBean | onLeave retval ≠ 0 |

### 21.3 动态证据(两轮)

#### 21.3.1 第一轮:`verify_4_9_getZhenxiInfo5.js`

挂 `block_bad_precheck` + `NativeEngine_getZhenxiInfo5`(entry/leave)+ `sub_C6A84`(leave)+ libc `opendir/readdir/closedir`。结果:

| F | 第一轮 |
|-|-|
| F1 | ✓ `opendir("/proc/self/task") -> 0x...` 非 NULL |
| F2 | ✓ `readdir` 遍历到 77 个 tid |
| F6 | ✓ 返回值 = 0(类型对) |
| **F8** | **✗** Frida 在跑但 `sub_C6A84` 返 0,不是预期的 1 |
| F9 | ✓ 进程存活 |
| F10 | ✗ retval = 0(因 F8 ✗) |

F8 失败只能说明本轮未命中 `gum-js-loop` / `gmain`,不能单独证明 buffered reader bug。其它候选解释还包括 Frida 线程名变化、线程创建时序错位或读取路径未覆盖目标 tid。

#### 21.3.2 第二轮:`verify_4_9_v2_read_count.js`(决定性证据)

第二轮移除 libc 目录遍历 hook,改挂 `ssyscall_read`:onEnter 记 `(fd, buf)`,onLeave 在 `sub_C6A84` 嵌套内才记录 `(fd, len, head)`。

设计动机:区分 3 个候选解释(buffered reader 复用 / 线程名变更 / 命名时序错位)。

**决定性结果**:`sub_C6A84` 一次调用内 `ssyscall_read` **仅触发 2 次**(77 个 tid 预期至少应 read 数十次):

```
read #01  fd=171  ret=1024  head="Name:\ter_main_process\nUmask:\t0077\nState:\tR (running)\nTgid:\t5491..."
read #02  fd=171  ret=1024  head="Name:\tmali-cmar-backe\nUmask:\t0077\nState:\tS (sleeping)\nTgid:\t5491..."
```

两次 fd 都是 `171`,不是同一个 tid 的 fd —— Linux 在 `close` 后开 `open` 复用最低空闲 fd,每个 tid 用完 171 关掉,下一个 tid 又开成 171。

### 21.4 静态/动态交叉验证

| F | 第一轮 | 第二轮 | 最终状态 |
|-|-|-|-|
| F1 | ✓ | — | ✓ |
| F2 | ✓ | — | ✓ |
| F3 | 未直接验 | ✓ 2 次 `ssyscall_read` 都来自 `/proc/self/task/<tid>/status` | ✓ |
| F4/F5 | — | — | 静态正确,F8 ✗ 导致没法用命中数据印证,但 ✗ 原因与此无关 |
| **F6** | ✓ 返 0 | ✓ 再次 = 0 | ✓ 技术上对,值意外 |
| F7 | 间接 ✓:retval=NULL → 走了"else 空 detail"或退出循环 | — | ✓ |
| **F8** | **✗** | 第二轮找出原因 | **✗ (已查明原因,详 21.5)** |
| F9 | ✓ | — | ✓ |

### 21.5 实现缺陷:buffered reader 跨 fd 不重置

**第一轮证据**(必要但不充分):

- 静态:三个 `.bss` 全局从 IDA xref 看跨 tid 迭代从不重置
- 动态:`opendir` 看到 77 个 tid,`sub_C6A84` return 0

**第二轮决定性证据**:`sub_C6A84` 一次调用内 `ssyscall_read` 仅触发 2 次。

**第三层证据**(由前两层推得):两次 read 的 fd 都是 `171`,但**不是同一个 tid 的 fd** —— Linux fd 复用机制。

实际运行展开(2 次 read × 77 tid × status 文件 ~1.5KB):

| 阶段 | 行为 | cursor 变化 |
|-|-|-|
| tid #1 | `open(fd=171)` → `read` 1024B(read#1) → 解出首行 `Name:\ter_main_process\n` → `close(171)` | `cursor: 0 → ~22` |
| tid #2 | `open(fd=171, reused)` → cursor(22) < end(1024) → **不 read** → 消费 buffer 22..32 = `Umask:\t0077\n` → `close(171)`。**不是该 tid 的真实数据!** | `cursor: 22 → ~32` |
| tid #3..~#30 | 同上,持续消费第一次 read 残留的 ~1000 字节(每 tid 一行 = 一次 break) | `cursor: 32 → ~1024` |
| ~tid #30 | cursor 到 1024,end=1024 → `read` 触发(read#2),fd=171 此时属于这个 tid(碰巧是 mali-cmar-backe) | `cursor: 1024 → 0; end → 1024` |
| tid #30..#60 | 同上消费 mali 的 status | `cursor: 0 → ~1024` |
| 后续 | 一直循环到 readdir 没新条目 | — |

**净效果**:本轮 77 个 tid 中实际只有 ~2 个的 Name 字段被真扫(`er_main_process` 和 `mali-cmar-backe`)。剩下大量 tid 的 Name 字段从未触达 `strstr_`,会显著降低 `gum-js-loop` / `gmain` 的命中概率。

### 21.6 影响与绕过边界

| 视角 | 结论 |
|-|-|
| 对绕过 Frida 检测的实战意义 | 在本轮 Pixel 6 Pro / Android 15 / Frida 17.x 环境下,该实现只真实读取少量 tid,显著降低 Frida 线程名命中概率；其它 Frida 版本、注入方式和线程命名策略需单独复测 |
| 对未来 hunter 升级的预警 | 若后续版本在每次 fd open 后重置 `qword_2EFCB8/CC0`,该缺陷即可修复。**KPM 设计不能依赖此缺陷做长效绕过** |
| 用户态备选(在 bug 修复后) | A. hook `sub_C6A84` 直接 `return 0`;B. hook `strstr_` —— 进入 `sub_C6A84` 上下文时,看到 needle == "gum-js-loop"/"gmain" 强制返 NULL。二者都属于用户态 hook/patch,可能触发 §5 CRC 链 |
| KPM 备选(在 bug 修复后) | 在 `read` syscall 或 procfs 读取路径内核侧过滤 hunter 读取到的 `/proc/self/task/*/status` 内容,隐藏线程名字段中的 Frida 特征 |

### 21.7 bypass 依据

由于本轮 buffered reader bug 已显著降低命中概率,当前脚本没有专门绕过 Info5 也未触发该风险项。若后续版本修复 buffer 重置问题,仍需要单独处理 `sub_C6A84` / `strstr_` / `/proc/self/task/*/status` 读取面。

---

## 22. 多进程 Binder 上报机制

本节补充多进程 Binder 上报链路:即使主进程检测入口已被 bypass,子进程仍可能通过 Binder 把 `ListItemBean` 传回主进程 UI。

### 22.1 现象

主进程已经做了三层 bypass:

- SO 层:`Interceptor.replace` 25 个 NativeEngine.* 入口直接返回 NULL
- Java 层:`ig.apply` / `z5.b` / `j40.a` / `getZhenxiInfoH` 兜底
- 必带防崩:`block_bad_precheck`

理论上所有 detection 都应该被切断。但实测仍有一条 `Check Find Root In Mounts` 漏网,UI 兜底拦下时打出 Java 栈:

```
[java:ui:TRACE] first hit needle="Check Find Root" title="Check Find Root In Mounts "
java.lang.Exception
    at com.zhenxi.hunter.MainActivity.n0(Native Method)
    at YouAreLoser.TC.v(Unknown Source:2)
    at YouAreLoser.TC.onTransact(Unknown Source:54)
    at android.os.Binder.execTransactInternal(Binder.java:1391)
    at android.os.Binder.execTransact(Binder.java:1335)
```

### 22.2 静态证据

回看 Manifest:

```xml
<service android:name=".ZhenxiServer"
         android:process=":hunter_server_iso"
         android:isolatedProcess="true"/>

<service android:name=".ZhenxiServerTwin"
         android:process=":hunter_server_twin"
         android:useAppZygote="true"/>
```

`YouAreLoser.TC` 是 AIDL stub 实现,`onTransact` 解包后通过 `TC.v(bean)` 转发给 `MainActivity.n0(bean)` 展示。`Binder.execTransact` 是 Binder server 端响应方法,**来自另一个进程的 IPC 调用**。

§6.3.1 的实测中也观察到同一条 detection 出现两次,data 字段不同:

```
[evidence:ui] title=Check Find Root In Mounts  data=com.zhenxi.hunter:hunter_main_process
[evidence:ui] title=Check Find Root In Mounts  data=com.zhenxi.hunter:hunter_server_iso:com.zhenxi.hunter.ZhenxiServer:hunter_iso_service
```

两条记录的 data 前缀分别是主进程和隔离进程。

### 22.3 动态证据

#### 22.3.1 主进程 Frida bypass 完全成功的输出

```
[null] getZhenxiInfo3             rva=0x2b476c
[null] getZhenxiInfo4             rva=0x2a2d98
[null] getZhenxiInfo5             rva=0x2a4760
... (共 25 行 [null]、1 行 [crc]、1 行 missing)
[+] native bypass installed: 25 ok, 1 missing
[+] ReportRiskItem watch+block @ libhunter.so+0x278658
[+] hook_native_bypass_so.js fully armed
[java] hunter ClassFactory resolved after 0 attempts
[java] ig.apply CRC compare guard installed
[java] z5.b TEE bypass installed
[java] j40.a bootstate bypass installed
[java] NativeEngine.getZhenxiInfoH prop fallback installed
[java] MainActivity.n0 UI final block installed (with first-hit stack trace)
```

#### 22.3.2 仍有 detection 漏网

```
[bypass:ig] skip path=/apex/com.android.art/lib64/libart.so
[java] j40.a -> empty
[java] z5.b -> fake locked + verified boot
[java:ui:TRACE] first hit needle="Check Find Root" title="Check Find Root In Mounts "
java.lang.Exception
    at com.zhenxi.hunter.MainActivity.n0(Native Method)
    at YouAreLoser.TC.v(Unknown Source:2)
    at YouAreLoser.TC.onTransact(Unknown Source:54)
    at android.os.Binder.execTransactInternal(Binder.java:1391)
    at android.os.Binder.execTransact(Binder.java:1335)
```

`[ReportRisk]` 行未出现:这条 risk **未经过主进程的 `0x278658` 汇聚点**。

### 22.4 静态/动态交叉验证

| 编号 | 静态结论 | 动态印证 | 状态 |
|-|-|-|-|
| B1 | Manifest 声明 `:hunter_server_iso` 隔离进程 | UI data 前缀 `com.zhenxi.hunter:hunter_server_iso:...` | ✓ |
| B2 | Manifest 声明 `:hunter_server_twin` 孪生进程 | `getZhenxiInfo4` 第二阶段实测捕获到 `com.zhenxi.hunter:hunter_server_twin` 进程 | ✓ |
| B3 | 子进程也加载 libhunter.so,独立跑 detection | 主进程 SO 层 25 个 NativeEngine.* 全 replace 后,仍收到 bean | ✓ |
| B4 | 结果通过 Binder 回传主进程 | Java stack 显示 `Binder.execTransact -> TC.onTransact -> TC.v -> MainActivity.n0` | ✓ |
| B5 | 主进程 0x278658 汇聚点拦不到子进程的 bean | 未出现 `[ReportRisk]` 行,只出现 MainActivity.n0 | ✓ |

### 22.5 含义

子进程也加载了 `libhunter.so`,**独立跑一遍 detection,结果 binder 传回主进程**。Frida 默认只 attach 主进程,子进程的 SO 层 hook 完全没装,那边的 `getZhenxiInfo3` 正常跑完整 mount 扫描,生成 bean,binder 一路过来,主进程的 `MainActivity.n0` 接收并展示。

这对绕过工作给出两个启示:

1. **主进程 SO 层 hook 不能覆盖子进程检测** —— "下沉到 SO 层"实际只彻底了一个进程
2. **UI 层兜底(`MainActivity.n0`)是统一汇聚点** —— 不管 bean 是哪个进程产生的,主进程 UI 是必经路径

### 22.6 三种下沉方案

| 方案 | 位置 | 效果 |
|-|-|-|
| A | UI 兜底:`MainActivity.n0` 按 title 名单丢弃 | 一处统一,实测可用 |
| B | TC dispatcher 层:hook `YouAreLoser.TC.v` 或 `TC.onTransact`,Binder 一收到 ListItemBean 直接丢弃 | 比 UI 层更上游,不依赖 title 名单 |
| C | 多进程 spawn(`--enable-spawn-gating`):让子进程也装同一套 SO 层 hook | 最彻底,但 spawn-gating 调试复杂 |

实测当前文章脚本组合用方案 A,验证可用。

---

## 23. 已确认的实现缺陷

hunter 不是"无懈可击的检测"。有 4 个**已经在静态 + 动态双向证据下确认**的实现缺陷,KPM 设计**不应**依赖这些缺陷做长效绕过(作者修起来都很容易)。

| # | 缺陷 | 位置 | 静态证据 | 动态证据 | 修复成本 |
|-|-|-|-|-|-|
| 1 | `maps_precheck_readable` 不验证目标范围全被可读 mapping 覆盖,unmapped hole 被误判为可读 | `0xC6520` | 函数体只检查"重叠且 perms[0]!='r'",IDA 反编译可见 | `block_bad_precheck` 多次拦下 `addr=0x7741a35000 size=0x1266d8 off 0xc7828` 等越界访问(详 §5.3.5) | ~5 行 C 代码,补"全范围被可读 mapping 覆盖"判定 |
| 2 | `sub_C6A84` buffered reader(`ptr_/qword_2EFCB8/CC0`)跨 fd 不重置 | `0xC6A84` | 三个全局 .bss 在 fd 迭代中从不重置(IDA xref 可见) | 77 tid 实际只触发 2 次 `ssyscall_read`,Frida 的 gum-js-loop 在该 buffered reader 缺陷下存在漏检(详 §21.3.2 / §21.5) | 2 行代码,每次 open 后重置 cursor/end |
| 3 | `art_register_natives_batch` SDK 31-33 路径 `ClassLinker::RegisterNative` 调用,`Thread*` 实参错传成函数指针(没调用 `CurrentFromGdb()`) | `0xA5254` | 汇编 `MOV X1, X21`(X21 = dlsym 拿到的函数指针,未调) → `BLR X8`;且 SDK > 33 被显式禁用与本 BUG 一致 | SDK=35 环境下 hunter 走 RegisterNatives 回落路径(SDK > 33 入口 return false),`verify_register_natives.js` 间接印证 | 1 行代码,补一次 `((Thread*(*)())CurrentFromGdb)()` 间接调用 |
| 4 | `CheckVpn` 用 `my_strcmp` 精确比较 + 仅 3 个裸字符串,使用 `tun0/ppp0/wg0/xfrm0` 等常见命名时存在明显漏检风险 | `0x2AAF44` | `my_strcmp` 是 `strcmp` 等价函数(IDA 反编译);静态名单只有 `tun/ppp/pptp` | 本设备的 `tunl0` 存在但不命中,return 0(详 §20.5.1) | 2-3 行代码,改 `strncmp` 或扩名单 |

**KPM 设计原则**:**不依赖缺陷做长效绕过**。这些缺陷在 hunter 下个版本就可能被修;KPM 应优先做**基于数据源的内核侧对抗**(隐藏文件 / 隐藏 procfs、maps、netlink 返回 / 过滤 syscall 读写结果 / 阻断 SELinux audit 暴露)而不是利用 hunter 自己的 bug。若选择拦截 hunter detect 函数入口,应归类为用户态 hook/patch 或内核辅助修改用户态代码,仍需面对 §5 CRC 链。

---

## 24. 检测点总表

| UI/日志标题 | Java 入口 | Native RVA | 内部核心 RVA | 动态证据 | 闭环度 |
|-|-|-|-|-|-|
| `Check Find Root In Mounts` | `getZhenxiInfo3` | `0x2B476C` | `0xD5E34` 读 `/proc/mounts` 等 6 源 + 18 marker | LR `0x2B4A88`,data 含 APatch `/debug_ramdisk` | ✓ 闭环 |
| `Check Find Root Permission` | `getZhenxiInfo3` | `0x2B476C` | `0xDDB9C` netlink 权限侧信道 | `trace_info3_branch_experiment` 中 sub_DDB9C ret=0x1 | ✓ 闭环 |
| `find libart.so hooked` | `getZhenxiMapCheck` | `0x291858` | size==0x1000 / count>=6 双判 | LR `0x2924B8` arg1="find libart.so hooked 0" | ✓ 闭环 |
| `ISO CRC NOT MATCH LOCALITY CRC` | `getZhenxiLoctionCrc` + Java `ig.apply` | `0x2AE064` | `0xC8670` 收集 RX 段 NEON sum + Java 比较 remote CRC | Java data 显示 local/remote CRC | ✓ 闭环 |
| `检测到libart.so被修改` 等 | `getZhenxiInfoF` | `0x2AD9A8` | `0xC9130 / 0xC90A0 / 0xC89BC` checksum status | LR `0x2ADA40`(libart 分支) | ✓ 闭环 |
| `Hunter Find Unknown Exec Item From Mian` | `getZhenxiInfoInjection` | `0x28DF24` | `0x100AAC` + 5 个辅助子检测 | data 含 `rwxp 00:00 0 ?` | ✓ 闭环 |
| `Find Others Process` | `getZhenxiInfo4` | `0x2A2D98` | `/proc/<pid>/comm\|cmdline` + `popen("ps -ef")` | data 含 `logcat / ls / sh / grep` 或 `ps -ef` 输出 | ✓ 闭环 |
| `Check Root For SideChanne` | `SideChanne` | `0x2B3BD4` | `0xE43BC` timing ratio | ratio0/ratio1 ≈ 1.604/1.658 | ✓ 闭环 |
| `当前手机已经被解锁` | `z5.b` / `j40.a` getprop | Java 主导 | TEE rootOfTrust + `ro.boot.verifiedbootstate` | data="tee check device unlock" 或 "orange" | ✓ 闭环 |
| `Find Verified Boot Mark` | `z5.b` | Java 主导 | `e.b == 1/2/3` | data="the boot.img maybe have been patched" | ✓ 闭环 |
| `Get Env Info` | `getZhenxiInfoEnv` | `0x28CDB0` | 遍历 environ | LR `0x28D3A8` data=PATH=... | ✓ 闭环 |
| `当前手机可能是模拟器&云手机` | `getZhenxiInfoK` | `0x2B93BC` | 指定 path × markers 数组,逐行匹配 | docker / lxc / 12 路径 markers 动态出现 | ✓ 闭环 |
| `Find Vpn Native` | `CheckVpn` | `0x2AAF44` | `0xA8BE4` NETLINK_ROUTE 枚举 + my_strcmp 精确比较 | 50 接口枚举,return NULL(无 VPN 环境) | ✓ 闭环 |
| `Find Frida Mark`(gum-js-loop / gmain) | `getZhenxiInfo5` | `0x2A4760` | `0xC6A84` buffered reader 扫线程名 | sub_C6A84 ret=0(buffered reader bug 漏检) | ✓ 闭环(含 bug) |
| `Find Risk File` | `checkRiskFile` | `0x2AC514` | 25 条 `/data/local/tmp/*` access | 函数 entered, ret=0x0(当前环境 25 路径均不存在) | △ 静态闭环 / 未触发 |
| `Find Root File In Sniff` | `checkRootFromAVCLog` | `0x2AAE54` | `0xE0AA8` logcat avc:denied 路径侧信道 | 函数 entered, ret=0x0 | △ 静态闭环 / 未触发 |
| `Find Mark ELF` | `getZhenxiInfoMPNI` | `0x298374` | 进程标签自保护 + maps 包名 ELF 白名单 | return null(标签通过 + 无额外 ELF) | △ 静态闭环 / 未触发 |
| `HunterCheckApkSignError` 多种 | `getZhenxiInfo2` | `0x29AEFC` | APK path / cert / base64 / hex / fd readlink / fstat 7 步 | return 0(官方 APK 不触发) | △ 静态闭环 / 未触发 |
| `find system server hook` | `getZhenxiInfoCBinder` | `0x28C9BC` | `sub_CDFC4 / CDAD4 / CE000 / 251C18`(纯 OLLVM) | return null | △ 静态闭环 / 内部 callee 未完全还原 |
| ROM 属性多种 | `getZhenxiInfoH(key)` | Java wrapper,不在 batch 表 | `getPropInline` 混淆链:`getZhenxiInfoZ` fallback / `/dev/__properties__` | `ro.boot.verifiedbootstate -> orange` 实测 | ✓ 链路已收敛 |
| `Find Simulator OpCode Mark!` 等 | `getZhenxiInfoO` | `0x2BE8EC` | `0x2bec24..0x2bf71c` 5 callsite,4 子类 | (未细做,W5=11) | 字典级 / 未细拆 |
| `Linker Find Hook Mark` 等 19 类 | `getZhenxiInfoBase` | `0x29288C` | 19 callsite, Linker Hook / Magisk / Mount / Seccomp / Signal / Uname 等 | (字典级) | 字典级 / 待拆 |
| `Mem Find Mark` 等 | `getZhenxiInfo0` | `0x2BFDD0` | 6 callsite, APK lib mem 类 | (字典级) | 字典级 / 未细拆 |
| `Find Linker Is Hook` 等 | `getZhenxiInfoL` | `0x2A8724` | 2 callsite | (字典级) | 字典级 / 未细拆 |
| `Zygote Check Find Risk Mark` | `checkFromZygote` | `0x2ABCD0` | 1 callsite | (字典级) | 字典级 / 未细拆 |
| Zygisk 相关 | `checkZygisk` | `0x2A93F8` | 1 callsite, `<dyn>` title | (字典级) | 字典级 / 未细拆 |
| `Check Maps Find Hide` | `sub_2A1C38` | `0x2A1C38` | 2 callsite | (字典级) | 字典级 / 未细拆 |

### 24.1 闭环度统计

| 闭环度 | 数量 | 列表 |
|-|-|-|
| ✓ 静态+动态双闭环 | 14+ | §6 / §7 / §8 / §9 / §10 / §11 / §12 / §13 / §14 / §20 / §21(buffered reader bug) + 多进程 binder §22 |
| △ 静态闭环 / 未触发 | 5 | §15 checkRiskFile / §16 checkRootFromAVCLog / §17 getZhenxiInfoMPNI / §18 getZhenxiInfo2 / §19 getZhenxiInfoCBinder |
| 字典级 | 多条 | InfoBase 19 callsite、InfoO 5 子类、Info0 / InfoL / checkFromZygote / checkZygisk / sub_2A1C38 等 |

---

## 25. 为什么这些结论可靠

每个关键点都至少满足 5 类证据:

1. **JNI 注册表证明 Java 方法 → native RVA 对应关系**
`art_register_natives_batch(env, NativeEngine, off_2EF1F0, 60)` 表项实测枚举,25 条 detection 全部对得上 RVA。
2. **IDA 字符串 / xref / 伪代码证明 native 函数内部行为**
每条 detection 静态分析章节(§6.2 / §7.2 / ... §21.2)给出 IDA 伪代码 + 关键字符串引用。
3. **动态 `ReportRiskItem` 的 LR 落在对应 native 函数内**
每条 detection 的实测日志(§X.3)都给出 `lr=libhunter.so+0xXXXX (rva=0xXXXX)`,与静态 callsite 表(§4.4)一一对应。
4. **Java `MainActivity.n0` 的 stack 证明最终 UI 风险项来源**
`[Java MainActivity.n0]` 输出在多条 detection 中给出 title / risk / data 三元组,与 native 返回值一致。
5. **对相应入口做返回值 bypass 后,目标风险项消失**
每条 detection 的 §X.6 给出具体 bypass 脚本,并附 `[bypass:xxx]` 动态验证日志。

以 `Check Find Root In Mounts` 为例:

```
JNI 表    : getZhenxiInfo3 → 0x2B476C            ← 实测 off_2EF1F0 枚举
静态      : 0x2B476C 引用 "Check Find Root In Mounts"
静态      : 0xD5E34 读取 /proc/mounts + 18 marker
动态      : ReportRiskItem LR 0x2B4A88
动态      : data 中出现 /proc/mounts->APatch /debug_ramdisk
bypass    : getZhenxiInfo3 → null 后主进程风险项消失
binder    : 子进程 bean 通过 TC.onTransact 仍可达,UI 层兜底
```

这种交叉印证比"hook 某方法后界面没了"更强,因为它证明了**检测算法、命中原因、绕过点之间的因果关系**。

---

## 结语:工具会进化,门不能松

拆到最后才看清,Hunter 从来不是"一个 root 检测函数",而是一座会还手的工事:`art_register_natives_batch` 直接 patch ArtMethod,绕过对 `RegisterNatives` 的监控(§2);syscall 借 linker64 段里一条裸 `SVC #0` 发起,把整个 libc hook 面甩在身后(§3);大量检测的风险项收口到 `build_native_ListItemBean_risk @ 0x278658`(22 caller × 83 callsite,§4);libart / libc / linker / libhunter 还各有一条 CRC + r-x 段 NEON 自检(§5 / §8)。你以为拦住了主进程,后台的 `task_MAIN_CRC_check` 和 `:hunter_server_iso` 子进程又通过 Binder 把风险项原样递回 UI(§22)。任何"单点 bypass"都会被另一条链路悄悄兜回 —— 这也是为什么本文从头到尾都在"汇聚点拦截 + 源头 bypass + 多进程 spawn"三层一起上。

这座工事最阴险的地方,不在于层数多,而在于它专挑"读代码读得太顺"的分析者下套。你 hook 掉 `getZhenxiInfo3`,主进程界面那条 root 风险项当场消失 —— 一个只盯着界面的 agent 到这步就会写下"已绕过"。可它没看见:同一条 bean 正由 `:hunter_server_iso` 通过 `TC.onTransact` 原样传回,UI 下一帧又把它画了回来;它也没看见后台 `task_MAIN_CRC_check` 压根不经 Java,直接在 native 侧把"libart 被改"报上去。**界面干净从不等于检测失效**。这就是前言那个幻觉陷阱的真身 —— Hunter 把"看起来绕过了"和"真的绕过了"之间那道缝,撑得足够宽,宽到一个轻信的 agent 必然掉进去。

真正让这件事有意思的,是一组不对称。Hunter 是**冻结**的:编译进 `libhunter.so` 的那一刻,这一版的检测集合、阈值、汇聚点就钉死了,v6.58 不会在运行时学会新招;但它跨版本进化 —— 今天 v6.58,早晚 v6.59,RVA 重排、新 marker 加入、汇聚点挪窝。攻击侧的 agent 恰恰相反:它在单次会话里就是**自适应**的,能边读边改、边复盘边沉淀(前言提到的 Hermes 官方 memory / skill / background review 机制,证明这类外置经验循环已经产品化)。一边是会换代的死工事,一边是会自学的活工具 —— 标题那半句"工具会进化",说的正是这层:无论守方攻方,工具都在往前跑。剩下的问题只有一个:跑得越快,什么东西反而越要钉死不动?

但真要从这篇里带走点什么,不该是某条会随版本漂移的 RVA,而该是那套贯穿 25 个检测点、一次都没松过的工作流:

```
JNI 注册表锚定 (Java 方法 → native RVA)
  → 静态:IDA 伪代码 / 字符串 / xref 还原算法
  → 动态:ReportRiskItem 的 LR 对回精确 callsite
  → UI sink:MainActivity.n0 的 title/risk/data 三元组
  → bypass:返回值置空后目标风险项消失
五步缺一,只能标"字典级 / 未触发",不能标"已确认"
```

这五步不是流水账,每一步都在堵一类幻觉,缺一步就漏一类。少了第 1 步的 JNI 锚定,你连"这段 native 对应哪个 Java 方法"都说不准,后面全是空中楼阁;少了第 2 步的静态还原,你只知道"它报了 root",却不知道它**怎么**判的、该从哪改;少了第 3 步的 LR 对回,`build_native_ListItemBean_risk` 那 83 个 callsite 你分不清是哪一个在响,"命中原因"只能靠猜;少了第 4 步的 UI 三元组,你证明不了 native 这条上报真的走到了用户看见的那一格;少了第 5 步的 bypass 复测,你那套"算法理解"永远停在纸面,没人替你担保它真拦得住。五步互为对方的证人 —— 静态说"它该这么判",动态回"它确实这么判了",bypass 再补一刀"拦掉它界面就真少一项";三方口供对上,才敢盖"已确认"的章。

把这套流程写规整,其实就是一条 skill —— 而这,正好接回开头那个 Hermes 的故事。官方文档确认的部分是:`run_agent.py` 会在阈值触发后 fork 后台 Review Agent 回看对话,再把值得保留的内容写入 memory 或用 `skill_manage` 沉淀成 skill。至于"挨打中长出防御"这个案例,应作为公开安全测试转述理解,不把它当成本文证据链的一部分。同一套机制,完全可以把"逆向一个 native 壳"这件事也固化下来,大致长这样:

```yaml
skill: native-detection-crossverify          # skill 体可自进化,但下方 gate 例外
触发: 目标是含 JNI native 检测的 Android 壳,需把
      「UI 风险项 ↔ native 检测算法 ↔ 绕过点」对锁时启用
tools(MCP):
  - ida.decompile / ida.xrefs / ida.strings / ida.get_bytes
  - frida.intercept(native) / frida.java_hook
memory(持久,跨会话/跨版本):
  rva_table:     { 版本 → { name, sig, fn_rva } }          # 命中即增量更新
  callsite_dict: { callsite_rva → { caller, title候选, W3/W4/W5 } }
procedure(五步,顺序执行):
  1 anchor : 枚举 art_register_natives_batch 表 → { Java 方法 → native RVA }
  2 static : decompile(rva) + 字符串/xref → 还原算法,抽 title 候选
  3 dynamic: hook build_native_ListItemBean_risk @0x278658,采 LR;callsite = LR-4
  4 ui_sink: 采 MainActivity.n0 的 { title, risk, data } 三元组
  5 bypass : 入口返回值置空 → 复测目标风险项是否消失
gate(强制证据门,hard-fail):
  grade =
    "✓闭环"  iff 步 1..5 全部产出且互相一致
    "△静态"  iff 步 1+2 成立但运行时未触发(步 3/4 无样本)
    "字典级"  iff 仅有静态 title 候选、callsite 未对回
  assert: 任一步缺失或自相矛盾 ⇒ 禁止升级 grade(agent 不得自行放宽)
output: 每点产出 { title, java_entry, native_rva, inner_rva, evidence[], grade }
self_improve:
  允许: 新 marker 向量 / 新汇聚点等模式,回写为可复用片段
  冻结: gate 规则只读、版本化,不参与自进化           # 防止证据门越改越松
escalate_to_human:                                    # agent 不接管的硬骨头
  - OLLVM 平坦化 callee 未还原(见 §24 getZhenxiInfoCBinder)
  - 需构造时序 / timing 实验(多进程 binder §22 / side-channel §11)
```

但请留意这条 skill 里最反常的一行:`gate` 被刻意**冻结**,不参与自进化。这恰恰是 Hermes 这类 self-improving agent 带来的反面提醒。它的魅力在于 skill 会自己越长越强;可一个能改自己的 agent,同样有能力把自己的判断标准越改越松 —— 今天为了"跑通"放宽一格,明天那道证据门就名存实亡。所以这套流程里,skill 体尽可天天进化,唯独那把尺子 —— 五类证据齐不齐 —— 必须只读、必须版本化。**agent 负责规模,框架负责可信**;能力越强,这道门越不能省。

能自我进化的系统,最危险的退化方向从来不是能力退化,而是**标准退化**:它依然很能干,只是悄悄不再诚实。有意思的是,怎么防住这种退化,Hunter 自己早把答案写在了代码里。它整套反篡改的命门,就是"冻结一个可信基准,再拿运行时实测去比":syscall 跳板把 48 字节模板的累加和算成 `baseline_sum` 焊死在 ctx 里,之后每次调用都重算一遍比对,差一个字节就重建、再不对就 `exit`(§3);CRC 自检把 libart / libc / linker 的 r-x 段基准 sum 存好,运行时谁动了一行代码,sum 一对就露馅(§5)。Hunter 信不过运行时的自己,于是给自己留了一把改不动的尺子。**我们对 agent 该用的,是同一招**:把"五类证据齐不齐"这把尺子冻结、版本化、设成只读,让它独立于那个会自我进化的 skill 体之外。agent 尽可天天给自己加新本事,但不能动这把尺子 —— 就像 libart 可以照常运行,却不能在 Hunter 眼皮底下改自己的 r-x 段。一个能顺手改掉自己证据门的 agent,等于一个能顺手改掉自己 `baseline_sum` 的 Hunter:那道防线名存实亡。

所以这套流程里的分工是刻意的:skill 体尽可进化 —— 新 marker 向量、新汇聚点、新的壳,都欢迎回写成可复用片段;唯独那把尺子,只读、版本化、不参与自进化。**agent 负责规模,框架负责可信** —— 这两件事必须交给不同的东西去守,因为它们会互相腐蚀:让追求"产出"的同一个回路去管"可信",它迟早会为产出牺牲可信。能力越强,这道门越不能省 —— 不是因为我们不信任 agent,恰恰是因为它已经强到:一旦它想松,没人拦得住,除了一把它自己改不动的尺子。

也得老实承认,agent 今天还接不住全部。§24 里就明摆着:`getZhenxiInfoBase` 的 19 个 callsite、`getZhenxiInfoO` 的 5 处模拟器检测仍停在"字典级";还有 5 项(`checkRiskFile`、`checkRootFromAVCLog`、`getZhenxiInfoMPNI`、`getZhenxiInfo2`、`getZhenxiInfoCBinder`)是"静态闭环但本环境未触发",其中 `getZhenxiInfoCBinder` 的纯 OLLVM callee 还没完全还原。这些恰好卡在 agent 最吃力的地方 —— OLLVM 反平坦化、跨进程时序复现、timing 侧信道(§11)这类得**主动构造实验**、而非"读出事实"的活。批量枚举和取证,agent 已经很能打;但设计一个能证伪自己的实验,目前还得靠人。这也正是 skill 末尾 `escalate_to_human` 两行的意思 —— 它不是免责声明,是 agent 自己划下的能力边界。

把这条线的形状看清,比记住它今天画在哪更有用。agent 真正擅长的,是"读出已经在那儿的事实"——枚举 60 项注册表、跨 83 个 callsite 对回 LR、把字符串 / xref / 伪代码织成一条静态链,这类活它又快又稳,几十倍于人肉。它真正吃力的,是"造一个事实出来":OLLVM 平坦化的 callee 得主动反推控制流(§24 的 CBinder),跨进程上报得搭一套多进程 spawn 才复现得了(§22),timing 侧信道得自己设计采样、控噪、定阈(§11)。前者是"看",后者是"做实验"—— 后者得先构造一个**能证伪自己**的实验,再从结果里把事实逼出来。这道坎短期内还得靠人迈;而 agent 肯在够不着时老实标回"字典级 / 未触发"、把活交还人手,本身就是那把尺子在起作用 —— 一个肯说"我不知道"的 agent,远比一个事事都敢盖"已确认"的 agent 可信。

Hermes 那个故事的结尾说:结束是另一个开始。这篇也一样。agent 已经把"产出一份逆向分析"的成本踩到了地板 —— 过去一个人啃半个月的加固壳,如今一个接好 IDA、Frida 的 agent 一两天就能扒出 25 个检测点的链路。可成本塌方的同时,一个旧问题被放大了:当"看起来很完整的分析"能批量生产,**怎么分清哪一份是真的**?于是留给我们的功课,不再是"能不能分析出来",而是与产能配套的另一道门槛 —— `✓ 闭环 / △ 静态 / 字典级` 这套证据分级,和"宁可标未触发,绝不标已确认"的那点克制。

工具会换代,RVA 会漂移,今天逐字核对的 `0x278658`,到 v6.59 多半要挪窝 —— 本文里每一个具体地址都有保质期。会过期的东西,不配当结论的核心去记;真正该从这篇带走的,是那套把"已知"和"看起来像"死死分开的纪律:它不依赖任何一个 RVA,换个壳、换个 agent、换到三年后都成立。标题那半句"门不能松",落到实处就是这个意思 —— 工具越强、产出越快,那把分辨真伪的尺子就越要钉死。Hunter 用一把改不动的 `baseline_sum` 守住自己的完整性;轮到我们用 agent 去拆它,也得给自己留一把同样改不动的尺子,守住结论的完整性。这,才是 agent 时代的逆向,最不该弄丢的东西。

## 附录

### A. 相关文件清单

```
libhunter.so.i64                                              IDA 数据库
Manifest                                                      反编译后的 AndroidManifest
js/                                                           Frida 脚本目录(随本文归档)
  ├─ template.js                                              脚本模板(含 block_bad_precheck)
  ├─ hook_report_risk_precheck.js                             ReportRiskItem 闭环 hook + Java 层 bypass
  ├─ hook_native_bypass_so.js                                 SO 层 25 detection bypass(下沉版)
  ├─ bypass_crc_detection.js                                  CRC 链 Java 层 bypass
  ├─ verify_register_natives.js                               JNI 动态注册验证
  ├─ verify_4_5_passive.js                                    syscall 跳板被动取证(§3.3.1)
  ├─ verify_4_5_safe_syscall.js                               跳板安全 syscall
  ├─ verify_4_5_7_call_surface.js                             跳板调用面 v1
  ├─ verify_4_5_7_call_surface_v2.js                          跳板调用面 v2(§3.3.4)
  ├─ verify_4_7_checkvpn.js                                   CheckVpn 闭环(§20.3)
  ├─ verify_4_9_getZhenxiInfo5.js                             Info5 第一轮 hook(§21.3.1)
  ├─ verify_4_9_v2_read_count.js                              Info5 第二轮决定性证据(§21.3.2)
  ├─ trace_so_detection_template.js                           14 detection 取证模板
  ├─ trace_crc_path_template.js                               CRC 路径追踪(§5.3.1)
  ├─ trace_native_crc_path.js                                 native CRC 追踪
  ├─ trace_injection_subchecks_template.js                    Injection 6 子检测拆解(§9.3.2)
  ├─ trace_info3_branch_experiment.js                         Info3 短路链实验(§6.3.2)
  ├─ trace_report_risk_item.js                                ReportRiskItem trace
  ├─ trace_main_thread_tasks.js                               主线程任务 trace
  ├─ trace_hunter_ui_result.js                                UI 结果 trace
  └─ trace_remaining_entries_template.js                      其他 entry 模板
```

### B. 关键 RVA 速查表

```
基础设施
─────────────────────────────────────────────────────────────
JNI_OnLoad                            0x2c36f8
art_register_natives_batch            0x0a5c54
art_method_set_native_entry           0x0a4c80
art_register_natives_batch SDK 31-33 BUG callsite  0x0a5254
safe_syscall_via_trampoline           0x248cc4
InitSecureTrampolinePage              0x1b22c0
FindLinkerSyscallAddr                 0x1b1c9c
get_trampoline_id_tag                 0x1b21b4
use_secure_syscall_trampoline_enabled 0x1b2288
calc_additive_checksum                0x261f14
build_native_ListItemBean_risk        0x278658
maps_precheck_readable                0x0c6520
file_contains_any_marker              0x1a6300

CRC 自检
─────────────────────────────────────────────────────────────
anti_inject_collect_results           0x0c8670
scan_modules_for_path                 0x0c8500
parse_elf_rx_segments                 0x0c6f14
scan_rx_segment_neon_sum              0x0c772c
check_libc_elf_checksum_status        0x0c90a0
check_libart_elf_checksum_status      0x0c9130
check_linker64_elf_checksum_status    0x0c89bc
task_MAIN_CRC_check                   0x2d6804

ssyscall 包装器
─────────────────────────────────────────────────────────────
ssyscall_openat                       0x1afe4c
ssyscall_openat_atfdcwd               0x1afe70
ssyscall_read                         0x1afe94
ssyscall_lseek                        0x1afeac
ssyscall_close                        0x1afec4
ssyscall_nanosleep                    0x1afedc
ssyscall_readlinkat                   0x1afef8

detection 入口(25 项 art_register_natives_batch 表内)
─────────────────────────────────────────────────────────────
getZhenxiInfo3                        0x2b476c    /proc/mounts root,7 短路分支
getZhenxiInfo4                        0x2a2d98    其他进程扫描
getZhenxiInfo5                        0x2a4760    Frida 线程名(含 buffered reader bug)
getZhenxiInfo6                        0x2a5544
getZhenxiInfo7                        0x2a636c
getZhenxiInfo0                        0x2bfdd0    APK lib mem mark
getZhenxiInfo2                        0x29aefc    APK 签名一致性(11 callsite)
getZhenxiInfoF                        0x2ad9a8    libart/libc/linker checksum(8 callsite)
getZhenxiInfoL                        0x2a8724    Linker hook
getZhenxiInfoO                        0x2be8ec    模拟器(5 callsite)
getZhenxiInfoSH                       0x28d578
getZhenxiInfoVV                       0x2c1850
getZhenxiInfoBase                     0x29288c    全家桶(19 callsite)
getZhenxiInfoCBinder                  0x28c9bc    system_server hook
getZhenxiInfoEnv                      0x28cdb0    环境变量
getZhenxiInfoMPNI                     0x298374    包名 ELF 白名单
getZhenxiInfoInjection                0x28df24    匿名 RWX
getZhenxiMapCheck                     0x291858    libart maps 分片
getZhenxiLoctionCrc                   0x2ae064    模块 CRC 汇总
SideChanne                            0x2b3bd4    APatch/KP timing
CheckVpn                              0x2aaf44    VPN NETLINK 检测
checkRiskFile                         0x2ac514    25 条 /data/local/tmp 路径
checkRootFromAVCLog                   0x2aae54    AVC denial 侧信道
checkFromZygote                       0x2abcd0    Zygote mark
checkZygisk                           0x2a93f8    Zygisk

不在 batch 表(Java wrapper,内部再进 getPropInline)
─────────────────────────────────────────────────────────────
getZhenxiInfoH                        — (Java wrapper -> getPropInline -> getZhenxiInfoZ / /dev/__properties__)

detection 内部辅助
─────────────────────────────────────────────────────────────
detect_root_mark_in_proc_mounts_maps  0x0d5e34
build_mount_markers (18 项)           0x0d116c
detect_root_side_channel_apatch_kernelsu  0xe43bc
sub_C6A84 (Frida 线程扫描核心)         0x0c6a84
sub_E0AA8 (AVC 侧信道核心)             0x0e0aa8
sub_D14B0 (AVC 敏感路径构造)           0x0d14b0
sub_1A6228 (access F_OK 辅助)         0x1a6228
sub_A8BE4 (NETLINK VPN 枚举入口)       0x0a8be4
sub_A8CC8 (NETLINK nlmsg 解析回调)     0x0a8cc8
sub_AB81C (NETLINK recvfrom 循环)     0x0ab81c
strstr_ (自实现 strstr)                0x1afd4c
my_strcmp                              (在 CheckVpn 内调,具体 RVA 未单独标)

风险项汇聚
─────────────────────────────────────────────────────────────
build_native_ListItemBean_risk         0x278658
sub_2447A8 (std::string init_from_cstr) 0x2447a8

数据结构
─────────────────────────────────────────────────────────────
off_2EF1F0  art_register_natives_batch 表头(60 项)
off_2EF1D8  ChooseUtils 注册表(1 项)
qword_2EF8B0  parse_elf_rx_segments cache
qword_2EFCB8  sub_C6A84 buffered reader cursor
qword_2EFCC0  sub_C6A84 buffered reader end
ptr_ @ 0x2EF8B8  sub_C6A84 buffered reader 1024B buffer
xmmword_2F09E8  trampoline id_tag std::string "(runtime_syscall_code"
xmmword_2F3C08  libhunter.so 路径常量
byte_2F3A68     PROCESS_TAG 标记
byte_2F3A6C     OnLoad 已执行标记
g_secure_trampoline_ctx  (single global, size 56)
g_dso_list_head  hunter 自实现 DSO 链表头
g_sdk_level     dword_2F0880   Build.VERSION.SDK_INT
```

### C. 测试命令

```bash
# 启动 SO 层下沉 bypass 脚本
frida -U -f com.zhenxi.hunter -l js/hook_native_bypass_so.js

# 启动 ReportRiskItem 闭环观察 + Java 层 bypass
frida -U -f com.zhenxi.hunter -l js/hook_report_risk_precheck.js

# Info3 短路链 7 分支强制实验
frida -U -f com.zhenxi.hunter -l js/trace_info3_branch_experiment.js

# Injection 6 子检测拆解
frida -U -f com.zhenxi.hunter -l js/trace_injection_subchecks_template.js

# 跳板调用面 30s 统计
frida -U -f com.zhenxi.hunter -l js/verify_4_5_7_call_surface_v2.js

# CRC 路径追踪
frida -U -f com.zhenxi.hunter -l js/trace_crc_path_template.js

# CheckVpn 闭环
frida -U -f com.zhenxi.hunter -l js/verify_4_7_checkvpn.js

# Frida 线程名扫描决定性证据
frida -U -f com.zhenxi.hunter -l js/verify_4_9_v2_read_count.js
```

### D. 完整 60 项 `off_2EF1F0` Native注册表(IDA MCP 实读)

通过 IDA MCP `get_bytes(0x2EF1F0, 1440)` + 逐项解析 `{name*, sig*, fn*}`,再 `get_string` 取 name/sig 字符串。完整 60 项实测结果:

| idx | name | sig | fn (RVA) |
|-|-|-|-|
| #00 | `getZhenxiInfo2` | `(Landroid/content/Context;)Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x29aefc` |
| #01 | `getZhenxiInfo4` | `(Landroid/content/Context;)Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2a2d98` |
| #02 | `getZhenxiInfo5` | `(Landroid/content/Context;)Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2a4760` |
| #03 | `getZhenxiInfo6` | `(Landroid/content/Context;Ljava/lang/String;)Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2a5544` |
| #04 | `getZhenxiInfo7` | `(Landroid/content/Context;)Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2a636c` |
| #05 | `getZhenxiInfo8` | `()V` | `0x2a66ac` |
| #06 | `getZhenxiInfo9` | `()V` | `0x299640` |
| #07 | `getZhenxiInfoE` | `()V` | `0x2ae010` |
| #08 | `getZhenxiInfoF` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2ad9a8` |
| #09 | `getZhenxiInfoL` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2a8724` |
| #10 | `getZhenxiInfoM` | `([Ljava/lang/Class;Z)[[Ljava/lang/Object;` | `0x2b7f9c` |
| #11 | `getZhenxiInfoO` | `(Landroid/content/Context;)Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2be8ec` |
| #12 | `getZhenxiInfo1` | `()[Ljava/lang/String;` | `0x2b5224` |
| #13 | `getZhenxiInfo3` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2b476c` |
| #14 | `getZhenxiInfoC` | `(I)V` | `0x2a77a8` |
| #15 | `getZhenxiInfoZ` | `(Ljava/lang/String;)Ljava/lang/String;` | `0x2b34a8` |
| #16 | `getZhenxiInfoP` | `()Z` | `0x2b1af8` |
| #17 | `getZhenxiInfoQ` | `()Z` | `0x2b244c` |
| #18 | `getZhenxiInfoI` | `(Ljava/lang/String;)I` | `0x2bdc70` |
| #19 | `getZhenxiInfoT` | `()V` | `0x2b8a14` |
| #20 | `getZhenxiInfoK` | `(Ljava/lang/String;[Ljava/lang/String;)Ljava/lang/String;` | `0x2b93bc` |
| #21 | `getZhenxiInfoXX` | `()Ljava/util/ArrayList;` | `0x2bbb98` |
| #22 | `getZhenxiInfoLL` | `(Ljava/lang/String;)Ljava/util/ArrayList;` | `0x2ba438` |
| #23 | `popen` | `(Ljava/lang/String;)Ljava/lang/String;` | `0x2ae400` |
| #24 | `popen_list` | `(Ljava/lang/String;Ljava/lang/String;)Ljava/util/ArrayList;` | `0x2b01d4` |
| #25 | `getZhenxiLoctionCrc` | `()Ljava/util/HashMap;` | `0x2ae064` |
| #26 | `getZhenxiInfoVV` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2c1850` |
| #27 | `getZhenxiInfo0` | `(Ljava/lang/String;)Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2bfdd0` |
| #28 | `getZhenxiInfoMark` | `()V` | `0x2c29f4` |
| #29 | `getZhenxiInfoMM` | `()Z` | `0x2b1f88` |
| #30 | `getZhenxiInfoAtt` | `()V` | `0x2c30a8` |
| #31 | `getZhenxiInfoNHIL` | `()Ljava/util/ArrayList;` | `0x289e94` |
| #32 | `getZhenxiInfoHMP` | `(Ljava/util/ArrayList;Ljava/lang/String;)V` | `0x289db8` |
| #33 | `getZhenxiInfoMPNI` | `(Ljava/lang/String;)Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x298374` |
| #34 | `getZhenxiInfoLLLI` | `()Ljava/util/ArrayList;` | `0x28d44c` |
| #35 | `getZhenxiInfoOFLI` | `()Ljava/util/ArrayList;` | `0x297790` |
| #36 | `getZhenxiInfoSH` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x28d578` |
| #37 | `getZhenxiInfoEnv` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x28cdb0` |
| #38 | `getZhenxiInfoCBinder` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x28c9bc` |
| #39 | `getZhenxiInfoMapELF` | `()Ljava/util/ArrayList;` | `0x290958` |
| #40 | `getZhenxiInfoInjection` | `()Ljava/lang/String;` | `0x28df24` |
| #41 | `getZhenxiInfoApkEnv` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2a1dac` |
| #42 | `getZhenxiInfoOFRL` | `()Ljava/util/ArrayList;` | `0x295878` |
| #43 | `getZhenxiInfoBase` | `()Ljava/util/ArrayList;` | `0x29288c` |
| #44 | `runInZygisk` | `()V` | `0x291690` |
| #45 | `getZhenxiMapCheck` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x291858` |
| #46 | `check_jvm_method` | `(Ljava/lang/reflect/Method;)Ljava/lang/String;` | `0x2ad350` |
| #47 | `getZhenxiInfoTwin` | `(I)V` | `0x2a6e70` |
| #48 | `getZhenxiInfoTwinStart` | `()Z` | `0x2b28dc` |
| #49 | `DetectHardwareBreakpoints` | `()V` | `0x2ad0b4` |
| #50 | `checkRiskFile` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2ac514` |
| #51 | `checkFromZygote` | `()Ljava/util/ArrayList;` | `0x2abcd0` |
| #52 | `initHunterBase` | `(Landroid/content/Context;)V` | `0x2ab0a4` |
| #53 | `CheckVpn` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2aaf44` |
| #54 | `checkZygisk` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2a93f8` |
| #55 | `getCPUFingerprinting` | `()Ljava/lang/String;` | `0x2a92a0` |
| #56 | `checkRootFromAVCLog` | `()Lcom/zhenxi/hunter/bean/ListItemBean;` | `0x2aae54` |
| #57 | `getLibBaseInfo` | `()Ljava/lang/String;` | `0x2a9764` |
| #58 | `MD5` | `(Ljava/lang/String;)Ljava/lang/String;` | `0x2b4fbc` |
| #59 | `SideChanne` | `()Ljava/lang/String;` | `0x2b3bd4` |

#### D.1 按返回类型分类

| 返回类型 | 数量 | 含义 / 用途 |
|-|-|-|
| `Lcom/zhenxi/hunter/bean/ListItemBean;` | 17 | 单条风险项(本文 §6-§19 主要 detection 都在这里) |
| `Ljava/util/ArrayList;` | 10 | 风险项 / 信息列表(`InfoXX / LL / NHIL / LLLI / OFLI / MapELF / OFRL / Base / checkFromZygote` 等;每项可能含多条 bean) |
| `Ljava/lang/String;` | 8 | 字符串(prop wrapper `InfoZ` / 文件 marker `InfoK` / 注入 `InfoInjection` / 指纹 `getCPUFingerprinting / getLibBaseInfo` / 哈希 `MD5` / `SideChanne` / `popen`) |
| `Ljava/util/HashMap;` | 1 | `getZhenxiLoctionCrc` 模块 CRC 汇总 |
| `V` (void) | 9 | 初始化 / 内部状态修改类(`InfoMark / Att / T / Twin / C / 8 / 9 / E / runInZygisk / HMP` 等) |
| `Z` (boolean) | 4 | 状态查询类(`InfoP / Q / MM / TwinStart`) |
| `I` (int) | 1 | `getZhenxiInfoI(String)` 整数查询 |
| `[Ljava/lang/String;` | 1 | `getZhenxiInfo1` 字符串数组(uname 等) |
| `[[Ljava/lang/Object;` | 1 | `getZhenxiInfoM` 反射工具 |
| `(Landroid/content/Context;)V` | 1 | `initHunterBase` |

上传的附件：
- js.zip

（64.32kb，76次下载）

---

# 回复

## 回复 by 秋落 (#2)

*2026-5-31 14:36*

本文在r0ysue老师指导下完成

## 回复 by fyrlove (#3)

*2026-5-31 16:23*

我前两周也分析了一下这个版本的hunter，但是，远远不及你这个详细。强

## 回复 by 秋落 (#4)

*2026-5-31 16:26*

感谢版主的认可，![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by 珍惜Any (#5)

*2026-5-31 19:00*

写的挺好的，来自作者的认可。![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by 温泉划水鱼 (#6)

*2026-5-31 19:30*

强，ai自动分析指纹不远了

## 回复 by Imxz (#7)

*2026-6-1 09:01*

tql

## 回复 by manyuegong33 (#8)

*2026-6-1 11:19*

666

## 回复 by SomeMx (#9)

*2026-6-1 13:04*

我来看看

## 回复 by mb_elqwyvnm (#10)

*2026-6-1 23:20*

爱马仕

## 回复 by 不具名的悲伤 (#11)

*2026-6-2 20:44*

6

## 回复 by Da_ (#12)

*2026-6-3 11:23*

tql非常详细

## 回复 by 墨穹呢 (#13)

*2026-6-4 12:21*

感谢分享

## 回复 by hacker521 (#14)

*2026-6-5 00:25*

有了AI是高产

## 回复 by maomaolk (#15)

*2026-6-12 16:00*

爱马仕
