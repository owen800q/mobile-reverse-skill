---
title: '[原创] 京东 jdgs 签名参数逆向：OLLVM + 自定义 VM 双重保护下七字段全还原'
url: https://bbs.kanxue.com/thread-293313.htm
tid: 293313
author: xiao_qi_lin
date: '2026-10-24'
tags: [Android安全, 原创]
crawled_at: '2026-10-24T08:16:28+00:00'
replies: 10
---

>
> 平台：Android / ARM64 · 目标：`com.jingdong.app.mall`（京东 App）· 目标参数：HTTP/2 请求头 `jdgs`
> 工具：eCapture、jadx、Frida、IDA Pro、Python
> 耗时：约一天 · 结果：**jdgs 七个字段 b1~b7 全部还原并离线复现**
>
>
> 本文是一篇完整的实战复盘，按时间线还原我从「抓到 1386 个错误码」到「七字段签名全部离线复现」的全过程，包括我走过的每一条死路和犯过的每一个错。
>
>
> 关于脱敏：设备根密钥 KEY_B（及其派生 KEY_A）已打码；设备指纹 UUID、eid、证书 MD5 保留真实值（作者自己的测试机）。
>
>
>

---

## 摘要：一句话链路

```python
eCapture 抓包 → 全部是 -3107（环境检测错误码）
  → jadx 还原 Java 层调用链（canonical 规范化 + Bridge.main(101)）
  → IDA 静态还原 libjdg.so（OLLVM 混淆 + RegisterNatives 动态注册）
  → Frida 过反调试拿到真实 jdgs → 推翻静态结论（是 JSON 不是拼接串）
  → 受控差分 + 故障注入 + 雪崩测试钉死 b5 是 160-bit 哈希
  → 方法表 + 全 crypto 入口 hook 排除 SHA-1/AES/RIPEMD（后被推翻一半）
  → 发现 SHA-1 其实存在（IV 与 MD5 共用，是误判根因）
  → 逆向自定义 VM 破解 X25 = POST(SHA256)
  → 破解 XOR 密钥流 = KEY_A（是 KEY_B 与 UUID 的派生）
  → 破解 b4 = base64(RC4(zlib(明文JSON)))
  → 定位 KEY_B 来源 = 一张 60×60 的 Data Matrix 二维码
\```

真正卡死我的三块硬骨头：**OLLVM 控制流平坦化、一个 85 条指令的自定义 VM、一个"IV 和 MD5 共用导致 SHA-1 被误判不存在"的陷阱**。

---

## 起因

目标是还原京东 App 网络请求里的 `jdgs` 签名参数。这个参数出现在每一个 HTTPS 请求的自定义头里，是京东风控/防刷的一部分——签名不对，服务端直接拒绝。

我手头的环境：

| 项 | 值 |
|-|-|
| 宿主机 | Windows 11（Git Bash） |
| 测试机 | Pixel 6 (oriole)，Android 15，内核 `5.10.209-android13-4`（aarch64/GKI），已 root（Magisk） |
| 抓包 | eCapture v1.0.1（基于 eBPF/uProbe 抓 conscrypt 明文，免装 CA 证书） |
| 反编译 | jadx 1.5.5（关 dex checksum） |
| 动态 | Frida 17.16.4（宿主 + 设备端同版本） |
| 静态 | IDA Pro 9（无头 `idat.exe` + IDAPython） |
| 目标 APK | `demo4.apk`，包名 `com.jingdong.app.mall`，当前 UID 10252 |

>
> 一点说明：测试机是一台定制系统（带内核级 hook 能力），但本文用到的抓包、Frida、IDA 都是通用能力，你在普通 root 机上也能复现大半。
>
>
>

---

## 第一回合：eCapture 抓到 1386 个 -3107

`jdgs` 在 HTTPS 请求的 header 里，明文被 TLS 加密。我不打算装 CA 证书去劫持（京东 App 很可能有证书校验），直接用 eCapture 走 eBPF/uProbe 在 `libssl.so`（conscrypt/BoringSSL）的加密函数入口抓明文，天然绕开证书固定。

命令（设备侧，后台跑，按 UID 过滤）：

```bash
adb shell su -c 'sh /data/local/tmp/run_jd_ecapture.sh -u 10252 ...'
adb shell am start ...  # 启动京东
\```

抓了 13.99MB 日志，筛 `jdgs` 字段。结果出来了，但全是一个值：

```python
jdgs: -3107   （共 1386 处，无一例外）
\```

`-3107` 明显不是签名，是个**错误码**。真实 jdgs 应该是长字符串（base64/hex）。这说明 Guard SDK 检测到了"风险环境"（root + 定制系统插桩），拒绝生成真实签名。

第一个坑就这么来了：**环境太"干净"反而拿不到真实签名**。逆向签名算法，第一步先要"过检测拿到真实样本"，否则后面全是空转。

---

## 第二回合：Java 层调用链还原（jadx）

先不管检测，把签名生成逻辑在 Java 层定位清楚。jadx 反编译 APK，搜 `jdgs` 字符串，很快定位到调用链：

```python
JDGuardHelper.getJDGuardPlugin().genSign(uri, bytes, str, str2, z)
  → pc.a.a()                              // 设置 jdgs 头
       if (oc.a.d.get()) {                // disabled 开关
           map.put("jdgs", "-3107");      // ← -3107 就出自这里
           return;
       }
  → pc.e 构造 canonical 规范化字符串
  → qc.i.I(bytes)                          // native 签名包装
  → Bridge.main(101, new Object[]{ canonical, v(), u(), w(), s() })
\```

几个关键点：

1. **`-3107` 是 Java 层的硬编码出口**，不是 native 检测失败。触发条件是 `oc.a.d`（一个 `AtomicBoolean`）为 true。
2. **canonical 规范化字符串**（这是签名的核心输入）：

```python
canonical = HTTP方法 + " " + path + " " + 排序后的 k=v 参数
\```

参数先各自 URL 编码，然后**先按 value 排序、再按 key 排序**；如果 body 不是 `application/x-www-form-urlencoded`，就在末尾追加 body 的 SHA-256 hex。
3. **`Bridge.main(int, Object[])` 是通用分发器**，第二个参数是 `Object[]`，五个元素：

	- `args[0]` = canonical 字节
	- `args[1]` = `v()`（设备 flags 串，含 `§§` 分隔符）
	- `args[2]` = `u()`（dfpEid 设备指纹）
	- `args[3]` = `w()`（app 版本，值 "1.0"）
	- `args[4]` = `s()`（配置 `ano`，默认 "83"）

`-3107` 的根因也定位了：`JDGuardHelper.enable()` 读远程配置 `enable_jdguard`，本机返回非 "1"，于是 `oc.a.d=true`，Java 层直接短路，**native 的 `main(101)` 从未被真正调用过**。

```python
-3107 = enable_jdguard 远程配置 ≠ "1" → oc.a.d=true → Java 短路
\```

到这里我意识到：要拿真实签名，得先让 `enable()` 返回 true，让流程真正走到 native。

---

## 第三回合：native 静态还原（OLLVM 初现）

native 库是 `libjdg.so`（`System.loadLibrary("jdg")`）。先看 ELF 结构：

```bash
llvm-readelf -h libjdg.so
llvm-nm -D libjdg.so
\```

结果：

- 688KB，ELF64 aarch64，**只导出一个动态符号 `JNI_OnLoad` @ 0x29a30**，其余全部动态注册。
- 两个 PT_LOAD 段：`off=0x0→vaddr=0x0`（RX，delta 0）、`off=0x98e48→vaddr=0x99e48`（RW，**delta +0x1000**）。
- 没有 OpenSSL/BoringSSL 导入，只有 zlib（`compress/inflate/adler32`）+ libc。**密码学是静态编译进 so 的**。

完整的段布局（手解 ELF64 得到，后面分析常量全靠它）：

| 段 | VA | 文件偏移 | delta | 说明 |
|-|-|-|-|-|
| `.text` | 0xd2a0 | 0xd2a0 | 0 | 代码段，size 0x714ec |
| `.rodata` | 0x7e790 | 0x7e790 | 0 | 只读常量，0x7e790–0x863cd |
| `.data.rel.ro` | 0x99e98 | 0x98e98 | **+0x1000** | 重定位只读 |
| `.data` | 0x9e000 | 0x9d000 | **+0x1000** | 可写数据，0x9e000–0xac890 |

>
> 关键记忆点：`.rodata` 的 VA 等于文件偏移（delta 0），但 `.data`/`.data.rel.ro` 要 **+0x1000**。两个 LOAD 段的边界就在这——seg1 覆盖 0x0 起、seg2 从 off=0x98e48 起对应 vaddr=0x99e48。后面所有常量（IV、K 表、方法表）的地址都要按这张表核对，否则差 0x1000 会指向完全错误的位置。
>
>
>

>
> ⚠️ 这里埋了第一个大坑，我后来才踩到：第二个 LOAD 段 file offset 和 vaddr 差 **+0x1000**。读 `.data.rel.ro`/`.rodata` 里的常量时，必须把文件偏移 +0x1000 才是真实 VA。我一开始没注意，导致 SHA-256 IV 地址算错，白白绕了一段路。**这个 delta 写进笔记里，后面所有常量地址都要核对一遍。**
>
>
>

### JNI 注册链

`JNI_OnLoad` @0x29a30 是个跳转壳，真实函数体在 @0x29a78。它调 `RegisterNatives`（JNI 偏移 0x6b8）注册了方法表 @**0xa03b0**：

```python
name = "main"
sig  = "(I[Ljava/lang/Object;)[Ljava/lang/Object;"
fn   = 0x29ce4 → 跳转壳 → 0x29d1c（Bridge.main 分发器）
\```

`main` 分发器 @0x29d1c 的逻辑：

```python
sub w8, w2, #0x65          ; op - 101
cmp w8, #3
跳转表 @0x82354：
  op=101（签名）  → 0x29d94
  op=102（封装）  → 0x29e08
  op=103（init）  → 0x29e7c
  op=104（crypto）→ 0x2b4a0
\```

我要追的是 **op=101（jdgs 签名）→ 0x29d94**。

### OLLVM 混淆：识别 + 对抗（本文技术含量最重的一节）

#### 它长什么样

一进 op-101 就发现不对，每个基本块开头都重复出现两行：

```asm
str wzr, [x20, #0x154]
str wzr, [x21, #0x150]
\```

这是 OLLVM 的**虚假控制流（BCF，Bogus Control Flow）**：往几个永远没人读的固定栈偏移写 0，再基于这些恒定的值制造大量永远不会走的垃圾分支。效果是 IDA 的 F5 反编译出一屏又一屏 `if ( v20 == 0x154 )` 之类的死代码，把真实逻辑淹没掉。识别特征就是这种「`str wzr` 到固定栈偏移」在基本块里**高频重复**。

第二个特征是**跳转壳**。几乎每个函数——`JNI_OnLoad`、`Bridge.main`、所有 hash 入口——它的"入口"都不是真实函数体，而是一小段：

```asm
; 0x29a30（JNI_OnLoad 的"入口"）
;   保存 x0-x2（前三个参数）
;   adrp + add  算出真实函数体地址
;   br x9       间接跳过去
; 真实函数体在 0x29a78
\```

它把「函数入口」和「真实函数体」拆成两段，中间用 `br x9` 间接跳转。IDA 默认无法确定 `br x9` 的目标，于是**函数边界被击穿**——一个函数被切成几段、几个函数被粘成一段。`JNI_OnLoad @0x29a30 → 0x29a78`、`Bridge.main fn_ptr 0x29ce4 → 0x29d1c` 都是这个套路。

第三个特征是**控制流平坦化（CFG flattening）**：op-101 主体是一个大 `switch(状态变量)`，真实逻辑被打散成一堆 case 块，靠状态变量决定下一个块。crypto 调用又经 `blr` / `br x9` 间接跳转，静态调用图上连不起来。

#### 它带来的三个致命后果

1. **函数边界识别失效**：`bl` 边扫描、IDA 交叉引用，全被跳转壳切断。
2. **调用者分析失效**：我早期用「`bl` 边扫描调用者」得出「HMAC-SHA1 0x15314 无调用者 = 死代码」「base64 无调用者 = 死代码」——**全是错的**。OLLVM 下 hash 入口全是 `br x9` 跳转壳、调用全是间接调用，`bl` 边扫不到 ≠ 没被调用。
3. **纯静态读代码基本报废**：F5 出来全是垃圾分支，靠读伪代码还原算法走不通。

#### 对抗第一步：放弃 IDA 默认反汇编，capstone 全量重扫

arm64 是定长 4 字节指令，我直接用 capstone 逐 4 字节扫整个 `.text`，绕开两个坑：① IDA 被跳转壳切碎的函数边界；② capstone 一次性 `disasm` 遇到「非法指令」就提前停（我第一版只扫出 **719 条 `bl`、337 个 `decrypt_str`，其实都是漏的**）。

全量扫出的真实数字：

```python
.text：115290 条指令 / 6971 条 bl / 946 个 decrypt_str 调用点
\```

`719 → 6971`，差了近 10 倍。**如果信了第一版的 719，后面所有"调用者分析"都建立在一张残缺的图上。** 这是 OLLVM 对抗的第一条铁律：先拿到一张完整的、可信的静态图，再谈分析。

#### 对抗思路总纲（后面几回合逐步成形，这里提前收拢）

1. **capstone 全量重扫**，拿到完整指令/bl/调用点。
2. **不猜入口，枚举方法表**：OLLVM 下每个 hash 都配一张「函数指针对 + IV + 常量表」，扫 `.data` 段挖方法表，再对函数指针去壳（具体落地见第六回合）。
3. **静态只做定位，结论用动态兜底**：静态负责找到方法表、入口、可 hook 的 offset，不负责读出完整算法——真正走通靠的是后面几回合的 hook + 受控差分。

#### 一个因 OLLVM 埋下的误判（教训）

`sub_46F50` / `sub_47240` 一开始被我标记成「签名核心」。后来解密它们的字符串才发现全是 `/proc/net/tcp`、`TracerPid:`、`/memfd`……**是反调试函数，不是签名**。OLLVM 把控制流打散后，光看「谁调了谁」很容易把「签名前被调用的函数」误当成「签名的一部分」——它确实在 op-101 路径上被调用，但只是签名前跑一遍环境检测。

>
> **教训：OLLVM 下「谁调了谁」≠「谁参与了算法」。** 一个函数在签名路径上被调用，不代表它参与计算，可能是前置的环境检测、日志、参数准备。判定一个函数是不是算法核心，唯一可靠的手段是**动态看它的输入输出**，而不是静态看它被谁调用。
>
>
>

### 密码学原语定位（第一版，后来有修正）

- **MD5**：core @0x18190（上下文 88B）、wrapper @0x232cc
- **SHA-256**：IV @0x9e5b0、K 表 @0x9e5d0
- **base64**：字母表 @0x80fb8、函数 @0x14f4c
- **HMAC-SHA1**：@0x15314（后来确认是死代码）

### 字符串混淆（这个很快破了）

`decrypt_str` @0x19ddc 是个**滚动 XOR**：

```c
dst[i] = src[i] ^ ((key + 3*i) & 0xff)
\```

key 是初始值，每字节 +3。我写了个脚本 `decrypt_strings.py` 把 so 里所有加密字符串批量解密，验证用类名命中：

```python
src=0xa03f0, key=2, len=35 → "com/jd/security/jdguard/core/Bridge" ✓
\```

用 capstone 逐 4 字节反汇编（arm64 定长指令，一次性 disasm 遇到非法指令就停，会漏），全 `.text` 扫出 **115290 条指令 / 6971 条 `bl` / 946 个 `decrypt_str` 调用点**，批量解密后得到一批关键字符串：

| 解密结果 | 来源地址 / key | 归属 |
|-|-|-|
| `0102030405060708` | 0x9e0f0 | eva 模块（**不在 jdgs 路径**） |
| `WU@EVA` | 0x9e11c / 0x9e1c8 | SHA-1 盐（eva 模块） |
| `F1D3FF8443297732862DF21DC4E57262` | 0xa8040 | eva 模块 |
| `waes_enc` / `make_header` / `make_eva_data` | 0xa03a0 等 | eva 模块标记 |
| `b1`~~`b7`、`e1`~~`e4`、`a11`、`a3`、`a6`、`a7` | — | JSON 字段名 / map key |
| `%lld;%d` | 0xa1600 | jdgs 格式串 |
| `IHDR`/`IDAT`/`IEND`/`PLTE`/`tRNS` | 0x9e0xx | PNG chunk 类型（后面 Data Matrix 解码用） |

>
> 一个反向可达分析的重要结论：`0102030405060708`、`WU@EVA`、`F1D3FF...` 这些"看起来像密钥/盐"的字符串，**全部属于独立的 eva 上传/加密模块，不在 jdgs(op-101) 签名路径上**。jdgs 路径里没有 AES 密钥/盐。这是用调用链反向可达分析排除的——**别看到密钥材料就往签名里套**，先确认它在不在你要追的那条链上。
>
>
>

### 反调试/检测链全景（这块决定后面必须过检测）

op-101 在真正签名前会先跑一遍环境检测，libjdg.so 里藏着一条完整检测链：

1. **seccomp BPF 过滤器**：`stub_p_none_r_int`，arm32/arm64 两套 bytecode，限制 syscall。
2. **TracerPid 检测**：读 `/proc/self/status` 的 `TracerPid:` 字段，非 0 即判定被调试。
3. **环境指纹**：`/proc/net/tcp`、`/proc/self/maps`、`/memfd`、`/proc/%s/cmdline`。
4. **反 Frida/反注入特征串**（解密出来的字符串里躺着这些）：`frida`、`gum-js-loop`、`gmain`、`linjector`、`Xposed`、`app_process`、`libart.so`、`dvm`、`adbd`、`init.svc.adbd`、`fake-libs`、`sepolicy`、`.magisk`、`/sbin`、`dkplugin`、`http.proxyHost/Port`。

这就是为什么 Frida attach 即被杀、root 环境拿不到真实签名。它解释了 `-3107` 背后那层"环境检测"到底是什么。

---

## 中途一次自证：我犯过的错（比成功更重要）

逆向写到一半，我发现**之前几个"板上钉钉"的结论是错的**。这些错单独拎出来，因为它们恰恰是最值得记的。

### 错 1：把 MD5 当成了 SHA-1

早期我看 wrapper @0x232cc 里有 NEON 指令：

```asm
vcgtq_u32 ...   ; 比较
vaddq_s32 ...   ; 加 0x09 / 0x30 / 0x37
vbslq_s8   ...  ; 按位选择
\```

这是把每个字节拆成两个 nibble，映射到 `'0'-'9' + 'A'-'F'` 的**大写 hex 编码**。我当时判断它是"证书指纹的哈希"，但归因成了 SHA-1。

**真相**：它调的是 MD5 core（0x18190），得到 16 字节，再用 NEON 转成 32 字符大写 hex。证书指纹 = **MD5(DER) 的大写 hex**，不是 SHA-1。

### 错 2：据此得出"SHA-1 不存在"

我搜遍了 so 找 SHA-1 的轮常量 `0x5a827999`、`0x6ed9eba1`、`0x8f1bbcdc`、`0xca62c1d6` 和第五个 IV 字 `0xc3d2e1f0`，**磁盘上搜不到**。于是下结论"SHA-1 不存在"。

这个结论**后来被推翻**，而且推翻的方式很打脸：SHA-1 的前 4 个 IV 和 MD5 完全一样，共用同一个 `xmmword_81000`；只有第 5 个 IV 字 `0xC3D2E1F0` 是 SHA-1 独有，而它是用 `MOV/MOVK` 立即数构造的，**不是常量表**，所以字节搜索永远搜不到。

>
> **教训：搜不到常量 ≠ 算法不存在。** 常量可能用立即数构造、可能被混淆、可能在运行时解密。字节搜索只能做"阳性"证据，做不了"阴性"证据。
>
>
>

### 错 3：把 hex 表当成 jdgs 路径的东西

`0123456789abcdefABCDEFxX+-pPiInN` @0x82600，我一度以为 jdgs 用它做 hex 编码。全 so 一搜，只有 4 个引用，全在 printf/money 模块（`0x5759c`、`0x59128`），**跟 jdgs 没关系**。

### 错 4：把反调试函数当成签名核心

`sub_46F50` / `sub_47240`，我一开始标记为"签名核心"。解密它们的字符串后发现全是 `/proc/net/tcp`、`TracerPid:`、`/proc/self/maps`、`/memfd`、`/proc/%s/cmdline`——**是反调试函数，不是签名**。op-101 只是在签名前调它们做环境检测。

### 错 5：Frida 无法 hook 静态 native 方法的原始实现

过检测时我想 hook 静态 native `Bridge.main` 保存原实现，结果 `this.main` / saved impl 都拿不到（静态 native 方法的 Frida 保存实现不可用）。最后改成 hook 实例方法 `qc.i.I()` 捕获入参/出参才绕过去。

---

## 第四回合：过反 Frida 检测，拿到真实 jdgs

前面提过 Frida attach 会直接被检测（进程被杀）。实测：

```python
frida -U -l scripts/jdg_probe.js -p 21043
→ Failed to load script: connection is closed   （进程已死）
\```

所以动态要非常小心。我的过检测方案（`route_a_v4.js`）：

```js
Java.perform(function () {
    // 1. 强制 enable() 返回 true，让 -3107 短路失效
    Java.use('com.jingdong.common.guard.JDGuardHelper').enable.implementation = function () { return true; };
    // 2. 强制 init 通过，让签名真正走到 native Bridge.main(101)
    Java.use('qc.f').m.implementation = function () { return true; };
});
\```

然后在实例方法 `qc.i.I()` 上 hook，捕获 `Bridge.main(101)` 的入参和返回值。

**结果出来了，直接推翻了我之前的静态结论。**

真实 jdgs 长这样：

```json
{"b1":"6bbc8976-d0fe-44ef-9776-ab9da0c127e8","b2":"3.2.8.4_0","b3":"2.1","b4":"<base64 328字符>","b5":"<40hex>","b7":"1792754231507","b6":"<40hex>"}
\```

**jdgs 是一个 JSON 对象 `{b1..b7}`，不是我之前静态推的 "MD5大写hex + SHA256 + 时间戳;计数 + 包信息" 拼接串！**

静态分析在 OLLVM 的掩盖下，把 JSON 装配误判成了字符串拼接。动态一跑，真相大白。这再次说明：**OLLVM 混淆下的纯静态分析，结论必须用动态验证兜底。**

### 字段依赖关系（受控实验）

我写了 `route_a_controlled.js` 直接调 `Bridge.main(101, {canonical, v, u, w, s})`，一次只改一个变量：

| 字段 | 值 | 依赖 |
|-|-|-|
| b1 | 常量 UUID `6bbc8976-...` | 设备/会话固定 |
| b2 | `3.2.8.4_0`（SDK 版本 + `_0`） | 固定 |
| b3 | `2.1` | 固定 |
| b4 | base64，245B，二进制，不随 canonical 长度缩放 | canonical + s + 时间戳 |
| b5 | 40hex（20B），**确定性** | **canonical + s**（改 v/u/w 不变；改 s 83→84 变；改 canonical 变） |
| b6 | 40hex | canonical + s + 时间戳 |
| b7 | 13 位毫秒时间戳 | 时间 |

关键观察：同 canonical 连调两次，**b5 相同、b4/b6 不同**（时间戳影响 b4/b6，不影响 b5）。

这给我一个重要线索：**b5 是 canonical 的纯函数，不含时间戳；b6 含时间戳。**

---

## 第五回合：受控差分 + 故障注入 + 雪崩测试

b5 是 40 hex（20 字节），明显是某种 160-bit 哈希。但要确定它到底是什么，静态 OLLVM 太硬，我改用动态"黑盒"手段。

### 5.1 canonical 到 MD5 输入的变换

hook MD5 core @0x18190，抓 MD5#1 的输入（= 变换后的 canonical）。做受控差分（多个 canonical，s=83）：

| canonical | 变换后（MD5 输入） | XOR 密钥流 |
|-|-|-|
| `A`(0x41) | `0x23` | `62` |
| `B`(0x42) | `0x20` | `62` |
| `AA` | `77 23` | `36 62` |
| `AB` | `77 20` | `36 62` |
| `ABC` | `37 74 21` | `76 36 62` |
| `hello` | `0a 23 19 1a 59` | `62 46 75 76 36` |

结论：变换是**逐字节 XOR**，同长度不同内容 → 密钥流相同（内容无关），但密钥流随长度变化。

```python
L=1 → 62
L=2 → 36 62
L=3 → 76 36 62
L=5 → 62 46 75 76 36
\```

我当时卡在这里：序列 `62→46→75→76→36→62` 像个 5 元环，但 L=5 起点异常，缺 L=4 样本。后来证明这个"长度依赖密钥流"的表象是个**假象**——真相是 KEY_A 的循环 XOR 折叠（见第九回合）。

### 5.1.5 一个重要的旁路：s=0 的简化分支

受控差分时我把 `s()`（配置 `ano`）从 83 改成 0，意外发现签名走了一条**完全不同的简化路径**：

```python
s=0：  b5 = SHA256( canonical_raw || key )    # 33B 输入 → 32B 输出
       key = 固定 32B（跨会话不变）
\```

这个 s=0 分支帮我把两个前提先钉死：

1. **key 是固定的**：跨两次 App 启动，s=0 的 SHA256 输入 `canonical_raw || key` 抓到**完全相同的 32B key**（`<32B固定key>`，打码，见脱敏说明），实测 `SHA256('A' || key)` 与 s=0 的 b5 完全一致。
2. **同一套代码，不同 s 走不同 hash 分支**：s=0 是裸 SHA256，s=83 才是完整的 MD5→POST(SHA256)→SHA1 链。**s（ano）是 hash 分发开关**，不能把某个 s 下的样本当唯一真相。

>
> 教训：逆向签名时先摸清每个入参各自控制哪个分支。`ano` 这种"看着像版本号"的字段实际是算法选择器——不试 s=0 就不知道存在一条更简单的路，也不会顺手拿到"key 固定"这个免费结论。
>
>
>

### 5.2 故障注入 + 雪崩

篡改 MD5#1 的输出，观察 b5 变化：

| 注入的 m1 | b5 |
|-|-|
| 正常 `01abfc75...` | `fe5caa73d169e6c43493a1259975d6db69f61391` |
| `00×16` | `074fdcfbfdcbb0835274b4d868ce243a8ff7585f` |
| `01 00×15` | `49703d3163848e7e0d2d4f3efa9236044751bde9` |
| `00×15 01` | `9b762789537adff02040dc7840686a560ca2ff8b` |
| `ff×16` | `6c59618ba07b631996bb046179174c5ae6fc79d9` |

- 单字节 00→01，b5 完全改变（`074fdcfb`→`49703d31`）→ **哈希式雪崩，非线性**。
- b5 只依赖 MD5#1（canonical 的哈希），不依赖 MD5#2。

于是 b5 的形态锁定为：

```python
b5 = H(MD5(变换后 canonical))     # 160-bit 输出，有雪崩
\```

但 H 是什么？我用 SHA-1 / SHA-256 截断 / MD5 对 m1 的各种拼接做了离线穷举，**无一匹配**。于是陷入了"SHA-1 不存在"的死胡同（这就是第三回合错 2 的由来）。

---

## 第六回合：方法表 + 全 crypto 入口 hook

既然猜哈希猜不出来，我换思路：**不猜，直接用证据钉死 s=83 到底调了哪些哈希。**

两条线并行：

1. 静态挖 so 里所有"方法表"（每个 hash 应有 函数指针对 + IV + 常量表）。
2. 动态运行时扫描 + 全 crypto 入口 hook。

### 线1：方法表枚举 + 跳转壳去壳

OLLVM 下每个 hash 都配一张方法表：`{函数指针0, 函数指针1} + IV + 常量表`。直接扫 `.data` 段里「相邻两个指向 `.text` 的指针 + 后面跟着已知常量」的模式，挖出 3 张表：

| 方法表地址 | 函数指针对 | 判定 |
|-|-|-|
| `@0x9e5a0` | `{0x26ac0, 0x26ac8}` + SHA256 IV@0x9e5b0 + K@0x9e5d0 | **SHA-256 方法表** |
| `@0x9e140` | `{0x1edd8, 0x1f020, 0x1f39c}` + 72B 数据 | **反检测模块**（非 hash） |
| `@0xac868` | vtable + `ffffffffffffffff` + clang 编译串 | 误报（编译器信息） |

但方法表里的函数指针本身也是跳转壳，要手动去壳追 `br x9` 的真实目标：

```python
0x26ac0 → 0x25118:  cbz x0, ret  /  b 0xcb50     （SHA-256 一个入口）
0x26ac8 → 0x25124:  b 0xcae0                     （另一个入口）
\```

去壳后的地址才是真实函数体。这一步把「方法表」和「真实算法」连上了。

`@0x9e140` 那三张表值得单独说：我一度怀疑它是"第三个 160-bit hash"，因为它的 72B 数据里 f3（`0x1f404`）有一处 `decrypt_str(dst=0x9e196, src=0x9e210, key=0xb, len=0x14)`，离线用滚动 XOR（key=0xb）解密出 `ro.build.version.sdk`——**是环境检测字符串，不是 hash 常量**。再全 `.text` 扫 `adrp 0x9e000 + add #0x140`（引用这张表的指令）= **0 处**（对照 SHA256 方法表 `add #0x5a0` 只有 `0x26a68` 一处）→ `@0x9e140` 是死数据/反检测，与签名路径无关。

>
> 方法表枚举 + 去壳，是 OLLVM 下**绕开"函数边界被击穿"的最有效静态手段**：不依赖 IDA 的交叉引用，直接靠「数据段里的函数指针对 + 已知常量」定位入口，再手工追 `br x9`。
>
>
>

### 线2：运行时扫描（决定性）

`scan_sha1.js` 在签名前后扫描 libjdg.so 内存，找各类哈希的 IV/常量：

```python
[签名前] MD5_IV_le     => 1 处 @0x81000      （阳性对照，命中）
[签名前] SHA256_IV_le  => 1 处 @0x9e5b0      （阳性对照，命中）
[签名前] SHA1_IV_le    => 0 处
[签名前] SHA1_IV_be    => 0 处
[签名前] SHA1_K_le     => 0 处
[签名前] SHA1_K_be     => 0 处
[签名前] RIPEMD_IV_le  => 0 处
[签名前] RIPEMD_IV_be  => 0 处
[签名后] ...（同样全是 0 处）
\```

阳性对照（MD5/SHA256）都命中了，说明扫描方法有效。SHA-1/RIPEMD-160 的常量**签名前后都不存在**。

静态搜字节：AES S-box/invSbox/Rcon、ChaCha20/Salsa20 的 `expand 32-byte k`、Blake2s IV，**全部 0 命中**。

结论：**libjdg.so 里只有 MD5 + SHA256 两个哈希原语**。

### 全 crypto 入口 hook（一锤定音）

`hook_all_crypto.js` 同时 hook 所有已知 crypto 入口，看 s=83 签名到底调了什么：

```python
s=83 完整调用 = base64(1次, b4) + MD5_core(2次, len=1 和 len=478)
SHA256 / HMAC / hash_generic / MD5_wrapper 全部 0 次
\```

也就是说，b5(20B) + b6(20B) = 40B 输出，只能由 m1(16B) + m2(16B) + key(32B) 通过**纯字节操作**构造，签名路径上没有任何额外哈希调用。

这跟"b5 是 160-bit 哈希有雪崩"的现象矛盾了——没有哈希，哪来的雪崩？这个矛盾是全文最关键的一个疑点，它逼着我去查 0x63xxx 区到底藏了什么。

### MD5 调用栈

```python
MD5#1(len=1, canonical):  0x2b8bc → 0x205cc → 0x63dcc → 0x21004 → 0x215ac → MD5_core
MD5#2(len=478, blob):     0x2b8bc → 0x206c4 → 0x215ac → MD5_core
\```

`0x63dcc` 只出现在 MD5#1 链里，正好落在可疑的 0x63xxx 区。canonical → m1 → b5 的关键路径确实经过 0x63xxx。

---

## 第七回合：SHA-1 其实存在（IV 与 MD5 共用的陷阱）

上一回合的"运行时扫描排除 SHA-1"是错的，或者说是不完整的。我后来在 hook 分发器时，抓到了 SHA-1 的真实输入输出，才揭开真相。

hook 分发器 `0x22b50` + SHA-1 入口 `0x1554c` + MD5 后处理 `0x22850`，样本 canonical="A" s=83：

```python
[POST] data=01abfc750a0c942167651c40d088531d len=16 mode=83   ← m1 = MD5(变换后 canonical)
[MODE] sub_22E74(83) = 1
[DISP] a1=41 a2=1 a3=83 a4=8ebf5e0c...967f83c62 a5=32
[SHA1] data=418ebf5e0cf2954d7be3f852b094fd95c7cd658c41c920dd1da32c38e967f83c62 len=33
       ↑ SHA-1 输入 = "A"(0x41) || X25(32字节)，总长 33
\```

离线验证：

```python
>>> hashlib.sha1(b'A' + x25).hexdigest()
'fe5caa73d169e6c43493a1259975d6db69f61391'   # == b5 ✓
\```

**SHA-1 确实存在！** 我之前"搜不到常量所以不存在"的结论是错的，根因就是错 2 里说的：

- SHA-1 前 4 个 IV（`67452301 EFCDAB89 98BADCFE 10325476`）**与 MD5 完全相同**，共用 `xmmword_81000`。
- 第 5 个 IV 字 `0xC3D2E1F0` 是 SHA-1 独有，用 `MOV W9,#0xE1F0` + `MOVK W9,#0xC3D2,LSL#16` 立即数构造，**非常量表**。

所以无论磁盘搜字节还是运行时扫常量，都永远找不到 SHA-1 的**完整 5 字 IV 序列**——前 4 字虽然与 MD5 共用 0x81000（会被当成 MD5 命中），但第 5 字 `0xC3D2E1F0` 是立即数构造，导致 5 字完整序列在内存里根本不存在。这就是第六回合运行时扫描"排除 SHA-1"却漏判的真正原因：扫描的是完整 5 字序列，而它在内存里不存在。

最终确认的函数语义：

| 函数 | 地址 | 真实语义 |
|-|-|-|
| `sub_1554C` | 0x1554c | **SHA-1**(data,len,out) |
| `sub_2349C` | 0x2349c | **hex 编码器**（`sprintf "%02x"`） |
| `sub_22B50` | 0x22b50 | 通用 hash 分发器 |
| `sub_22E74` | 0x22e74 | mode→分类，`sub_22E74(83)=1` |
| `sub_22850` | 0x22850 | MD5 结果后处理 → 调 `sub_27688` |
| `sub_27688` | 0x27688 | **X25 生成器**（16B→32B） |
| `sub_226E0` | 0x226e0 | 循环 XOR 工具 |

于是 b5 公式清晰了一半：

```python
b5 = SHA1( canonical || X25 )
X25 = sub_27688(m1, 16)        # 16B → 32B，待破解
m1  = MD5( canonical ^ keystream )
\```

只剩 **X25** 和 **keystream** 两个未知。

---

## 第八回合：X25 = 一个 85 条指令的自定义 VM

`sub_27688` 是 16B → 32B 的变换。走到这一步，前面 OLLVM 的账该还了——上一回合我能靠 hook 绕过去，这一回合绕不过去：X25 的算法藏在控制流混淆**下面**，不把这一层撕开，永远只能黑盒猜。

### 8.1 反编译出来的是一具"空壳"

先在 IDA 里对 `sub_27688` 按 F5，得到的伪代码只有一行：

```c
void sub_27688()
{
  JUMPOUT(0x276E0LL);
}
\```

`JUMPOUT` 说明函数入口是 OLLVM 的**跳转 thunk**——真正的函数体被藏到了 0x276E0，控制流先过一层间接跳转才到。dump 出真身汇编，能看清这层"接力"是怎么做的：

```asm
0x27688: STP  X0, X1, [SP,#var_20]!     ; thunk 入口：压两个寄存器
0x27690: ADR  X1, unk_276B0
0x27694: SUBS X1, X1, #0xC
0x276ac: BR   X9                        ; 间接跳转 → 0x276E0 真身
\```

跳过 thunk 看真身，`sub_27688` 的结构豁然开朗——标准的**哈希函数三段式**：

```asm
0x27724: BL   sub_2777C   ; init
0x27734: BL   sub_27908   ; update(m1, 16)
0x27740: BL   sub_27AC4   ; finalize → 32B 输出
\```

`init / update / finalize` 这个骨架，做哈希的人一眼就认得。但怪就怪在：三个函数里**看不到任何 SHA/MD5 的轮运算**，只有一堆 `memcpy` 和函数调用。真正的算法去哪儿了？

### 8.2 三步走：dump 表 → 解析表头 → 反汇编字节码

继续挖 `sub_2777C`（init），关键线索就藏在开头这几行：

```asm
0x27820: ADRL X20, unk_9E6D0                     ; 目标缓冲区
0x27828: ADRL X1,  unk_9F510                     ; 源表（磁盘上是加密的）
0x27830: MOV  W2,  #2                            ; 解密 key = 2
0x27834: MOV  W3,  #0x1AF                        ; 长度 = 431 字节
0x2783c: BL   decrypt_str                        ; 就地解密
0x27840: STRB WZR, [X20,#(byte_9E87F-0x9E6D0)]   ; 末尾补一个 0
0x2785c: BL   .memcpy                            ; 拷贝 0x1B0 = 432 字节
0x27880: BL   sub_241FC                          ; 加载字节码
0x278a8: BL   sub_24420                          ; 解释器执行！
\```

`decrypt_str` + `sub_241FC`（加载）+ `sub_24420`（执行）这三件套一出现，性质就定了：**这是一台带自解密字节码的 VM**。`sub_24420` 是解释器，`unk_9F510` 是它吃的字节码。

于是我用 IDA 脚本 `ida_dump_vm_full.py` 把解释器整段（0x24478–0x24F00）导出来，第一眼就是决定性证据：

```asm
0x244e4: LDRB W8, [X20]          ; 取指：从 IP 读一个字节
0x244f0: CMP  W8, #0x54          ; switch 85 cases
0x244f4: B.HI def_24508          ; > 0x54 走 default
0x244fc: ADR  X9, loc_2450C
0x24500: LDRH W10, [X26,X8,LSL#1] ; 查跳转表
0x24508: BR   X9                 ; 分发
\```

一个 `LDRB` 取指 + 一张 85 项的跳转表 + `BR` 分发——这是教科书级的字节码解释器主循环。到这里，"它是个 VM"不再是猜测，而是摆在面前的汇编事实。

三张字节码表，每张都有 magic 头 `0xB3B6A81B`：

| 表 | 地址 | 大小 | 解密 | 字节码段 | 重定位 |
|-|-|-|-|-|-|
| init 表 | unk_9F510 | 431B（磁盘加密态） | key=2 解密后补 1 字节 | lenA=408 | 0 条 |
| update 表 | unk_81920 | 648B | 明文 | lenA=576 + lenB=16 | 4 条 |
| finalize 表 | unk_81BA8 | 1784B | 明文 | lenA=1728 + lenB=16 | 2 条 |

表头结构（之前理解错了，dump 出真实字节后才修正）：

```python
偏移 0x00: magic   0xB3B6A81B
偏移 0x04: lenA    主数据段长度
偏移 0x08: lenB    附加数据段长度
偏移 0x0C: dataoff
偏移 0x10: nreloc  重定位条目数
偏移 0x18: 重定位表（每条 8 字节，存数据段内偏移）
偏移 0x18 + nreloc*8: 字节码段（lenA + lenB 字节）
\```

验证一下：update 表总大小 = 0x18 + 4*8 + 576 + 16 = 648B，finalize 表 = 0x18 + 2*8 + 1728 + 16 = 1784B，和磁盘上看到的完全一致。表结构对了，后面的反汇编才有意义。

### 8.3 init 表是加密态：key=2 的流式异或

init 表在磁盘上是加密的，`decrypt_str` 的还原很简单，是**位置相关的流式异或**：

```python
def decrypt_str(src, key):
    return bytes((b ^ ((key + 3 * i) & 0xff)) for i, b in enumerate(src))
\```

key=2，所以第 `i` 字节 XOR `(2 + 3i) mod 256`。这个"步进 3"的异或不是为了加密强度，纯粹是**防静态扫描**——让 `strings` 和 IDA 的常量搜索永远抓不到明文字节码。这也解释了为什么一开始对着磁盘 so 分析会一头雾水：真正的字节码要等运行时才现形。

### 8.4 反汇编器与 85 条指令

表结构清楚后，写反汇编器就是体力活：把解释器每个 case 的语义读出来，映射成指令。`sub_24420` 是**栈机**，寄存器约定：

- `X20` = IP（指令指针，`LDRB W8,[X20]` 就是取指）
- `X21` = SP（操作数栈指针）
- `X23` = 数据基址
- `X22` = 第二寄存器（辅助）

完整指令集 85 条，我反汇编器（`vm_disasm.py`）里的 `INSN` 映射：

| 操作码 | 语义 | 操作码 | 语义 |
|-|-|-|-|
| 0x00 | nop | 0x01–0x06 | ld_i8 / ld_u8 / ld_i16 / ld_u16 / ld_i32 / ld_i64 |
| 0x07 | push_i32（4B 立即数） | 0x08 | push_i64（8B 立即数） |
| 0x09 | push_addr_x23+（基址+偏移压栈） | 0x0a | push_addr_sp+ |
| 0x0b–0x0e | st_i8 / st_i16 / st_i32 / st_i64 | 0x0f–0x2c | 加减乘除模 / 位运算 / 移位（32/64 位） |
| 0x2d–0x38 | 比较（lt/le/eq/ne/ltu/leu） | 0x39–0x42 | trunc / sext / zext（截断与扩展） |
| 0x43 | nip | 0x44 / 0x45 | brz / brnz（条件跳） |
| 0x46 | jmp | 0x47 / 0x48 | dup32 / dup64 |
| 0x49 / 0x4a | drop4 / drop8 | 0x4b / 0x4c | rev64 / swap8_16 |
| 0x4d | add_sp | 0x4e | pop64_x23 |
| 0x4f | **syscall**（5B，走 sub_24F00） | 0x50 | halt |
| 0x51 / 0x52 | pop32_st_x23 / pop32_st_x22 | 0x53 / 0x54 | push_ld_x23 / push_ld_x22 |

立即数长度：push_i32 / push_addr_* / br* / jmp / add_sp 是 4 字节，push_i64 是 8 字节，其余 0 字节。指令总长 = 1（opcode）+ 立即数长度，反汇编器据此线性扫描。

### 8.5 syscall 分发器：VM 与外界的唯一接口

85 条指令里最特殊的是 `0x4f syscall`。它跳进 `sub_24F00`，一个 **11-case 的分发器**：

```asm
0x24f68: SUB W8, W8, #1   ; switch 11 cases（syscall 编号 1..11）
0x24f6c: CMP W8, #0xA
0x24f70: B.HI def_24F98   ; default
0x24f78: ADRL X9, jpt_24F98
0x24f84: LDRB W11, [X9,X8] ; 查跳转表
0x24f98: BR  X10          ; 分发
\```

11 个 case 的**共同套路**是同一个：从 VM 栈顶取函数指针，`BLR X9` 间接调用，区别只在于参数个数/宽度和返回宽度。举两个：

```asm
; case 1（1 个 32 位参数）
0x24fa4: LDR X8, [X19]
0x24fa8: LDR X9, [X8]          ; 函数指针
0x24fac: LDR W0, [X8,#8]       ; 参数 1
0x24fb0: BLR X9

; case 9（多参数 + 64 位返回）
0x25090: LDR  X8, [X19]
0x25094: LDP  X9, X0, [X8]     ; 函数指针 + 64 位参数
0x25098: LDR  W1, [X8,#0x10]   ; 32 位参数
0x2509c: LDUR X2, [X8,#0x14]   ; 64 位参数
0x250a0: BLR  X9
0x250a4: LSR  X8, X0, #0x20    ; 64 位结果拆两半存回
0x250a8: STR  W0, [X20]
0x250ac: STR  W8, [X21]
\```

也就是说，VM **自己不算 SHA-256**——它通过 `syscall` 把函数指针和参数从字节码里取出来，`BLR X9` 调宿主的原生函数。VM 的职责是"编排"：喂数据、调度压缩函数、再套一层后处理。

### 8.6 破解一：SHA-256 的 IV 被"双立即数 XOR"藏起来了

有了反汇编器，init 表的字节码现了原形。开头一段长这样：

```asm
000b: push_i32  -1778937903 (0x95f78fd1)
0010: push_i32  -104010    (0xfffe69b6)
0015: xor32
0016: push_addr_x23+  +16
001b: ld_i64
...
0037: st_i32                      ; 把 xor 结果写进状态

0038: push_i32  1150928688 (0x4499c730)
003d: push_i32  -104011    (0xfffe69b5)
0042: xor32
...
\```

`push_i32 + push_i32 + xor32` 这个模式重复了 8 次。把 xor 一个个算出来：

```python
0x95f78fd1 ^ 0xfffe69b6 = 0x6a09e667
0x4499c730 ^ 0xfffe69b5 = 0xbb67ae85
0xc3909ac6 ^ 0xfffe69b4 = 0x3c6ef372
0x5ab19c89 ^ 0xfffe69b3 = 0xa54ff53a
0xaef03bcd ^ 0xfffe69b2 = 0x510e527f
0x64fb013d ^ 0xfffe69b1 = 0x9b05688c
0xe07db01b ^ 0xfffe69b0 = 0x1f83d9ab
0xa41ea4b6 ^ 0xfffe69af = 0x5be0cd19
\```

`6A09E667 BB67AE85 3C6EF372 A54FF53A 510E527F 9B05688C 1F83D9AB 5BE0CD19`——这是 **SHA-256 的 8 个标准初始 IV**，一个不差。

关键在第二个立即数：`0xfffe69b6, 0xfffe69b5, 0xfffe69b4, ...` 是一串**递减 1 的密钥序列**，第一个立即数才是被它"加密"过的 IV 原值。VM 把 SHA-256 的魔数故意拆成"两数异或"，让 `strings` 和常量扫描永远搜不到裸的 `6A09E667`。你只有把字节码还原、把 xor 真正执行出来，才能看到它。

这就是"逆向 VM 本身"和"拿 unidbg 跑起来黑盒猜"的分水岭：黑盒永远看不到这一层混淆，只能靠比对标准 SHA-256 输出发现"对不上"，却不知道为什么对不上。

### 8.7 破解二：重定位表把立即数换成函数指针

反汇编 update / finalize 表时，有几处 `push_i64` 的立即数长得像"假地址"，我在反汇编器里标成了 `RELOC`：

```asm
008c: push_i64  0x240   ; RELOC(8d) -> 函数指针!
0095: push_i64  0x0
009e: add64
009f: ld_i64
00a0: syscall   #8
\```

表头的 `nreloc` 字段记录的就是这些位置：update 表 4 处（`0x8d / 0x156 / 0x186 / 0x1e7`，立即数全是占位值 `0x240`），finalize 表 2 处（`0xc4 / 0x1f3`，占位值 `0x6c0`）。这些 8 字节立即数在**加载时被替换成宿主函数的真实地址**——所以字节码不是自包含的，它和宿主 so 的函数绑定在一起。静态 dump 看到的 `0x240` 是占位符，必须理解重定位语义，`ld_i64` 才不是"从一个野地址读"，而是"取出真正的函数指针"。

### 8.8 破解三：POST 后处理，t1/t2 就埋在 finalize 表末尾

finalize 表末尾，先**逐字节 push 两张 32 字节常量表**，再一个循环做后处理。push 出来的字节（按偏移排）正好就是之前黑盒死活匹配不上的那两个表：

```asm
; t1（写入 -80 偏移）→ 78 8a 04 09 a5 38 ff 39 a0 b9 20 c0 e7 d5 e8 ec ...
; t2（写入 -48 偏移）→ 4c 90 7a 16 1b c9 b6 69 7a 65 84 73 82 c3 04 11 ...
\```

然后是核心循环：

```asm
0647: push_addr_x23+ +24
0655: ld_i8                 ; 取 sha256[i]
0664: ld_i8                 ; 取 t1[i]（-80）
0666: add32                 ; sha256[i] + t1[i]
0675: st_i8                 ; 存回
0684: ld_i8                 ; 再取出来
0693: ld_i8                 ; 取 t2[i]（-48）
0694: xor32                 ; (sha256[i] + t1[i]) ^ t2[i]
06a4: st_i8
\```

翻译成伪代码就是一层后处理：

```python
out[i] = (sha256[i] + t1[i]) ^ t2[i]   (mod 256)
\```

之前测 `SHA256(m1)` 匹配不上，正是漏了这层 POST。它是 VM 在标准 SHA-256 输出上额外套的一步混淆，两张常量表直接埋在 finalize 表的字节码尾部。

于是 X25 的完整真相：

```python
X25 = POST(SHA256(m1))  =  (sha256[m1] + t1) ^ t2  逐字节

t1[32] = 78 8a 04 09 a5 38 ff 39 a0 b9 20 c0 e7 d5 e8 ec
         ae 1d 24 f0 75 9a 5b a3 fd b8 2a 68 29 e1 a6 38
t2[32] = 4c 90 7a 16 1b c9 b6 69 7a 65 84 73 82 c3 04 11
         94 ab 22 db 6c ed 9d 80 f1 72 c0 73 eb 47 4a 5f
\```

**验证：8/8 黑盒样本命中**（`scripts/verify_x25.py`）。

>
> 这里揭示了一个很有代表性的保护手法：**OLLVM 混淆 + 自定义 VM 双重保护**。OLLVM 让每个函数入口都变成 `BR X9` 的跳转 thunk，控制流读不懂；VM 再把真正的 SHA-256 压缩函数藏进一段自解密字节码里——初始化向量用"双立即数异或"藏、函数调用用重定位表藏、后处理常量塞进字节码尾、最后还套一层"加 t1 再异或 t2"的混淆。四重手段叠下来，黑盒既匹配不上标准 SHA-256，静态分析也看不到任何裸魔数。唯一的出路就是**把 VM 本身反汇编出来**，逐条还原它的字节码语义。
>
>
>

---

## 第九回合：XOR 密钥流 = KEY_A（其实是 KEY_B 的派生）

X25 破了，b5 就剩 keystream（`sub_226E0` 的 XOR 密钥）没还原。

我一开始把 `sub_226E0` 当成"keystream 生成器"，看汇编后发现**又错了**——它是一个**通用循环 XOR 工具函数**：

```c
sub_226E0(buf_a, len_a, buf_b, len_b) → malloc(len_a)
  if (len_a > len_b):  out[i] = buf_a[i] ^ buf_b[i % len_b]
  else:                for (i in len_b): out[i % len_a] = buf_a[i % len_a] ^ buf_b[i]
                       // 末尾覆盖语义
\```

真正的密钥是调用方传入的 `buf_b`，由 `sub_1E228 + sub_22410` 从全局单例 + 入参生成。

hook `sub_226E0` 抓到两个静态密钥（跨冷启动稳定）：

1. **KEY_A（36B）**：XOR canonical（b5 路径）和 478B JSON（b6 路径）
2. **KEY_B（64B，ASCII）**：XOR UUID（b1/b4 路径）

>
> 脱敏说明：本文隐藏 KEY_B（64B 设备根密钥）和 KEY_A（36B，是 KEY_B 的派生，公开可反推 KEY_B），以 `<KEY_B>` / `<KEY_A>` 占位。KEY_B 是一段 64 字符的 ASCII 串（形如 `iy0yIVKJ…`，已打码），KEY_A 是一段 36 字节的二进制（hex 形如 `7e11060b…`，已打码）。此外 s=0 简化分支里还有一把 32B 固定 key（`<32B固定key>`），与 KEY_B 的派生关系尚未建立，同样打码。**读者需在自己设备抓取这些值**，抓取方法见后文（第十回合）。
>
>
>

于是 b5 全链打通：

```python
b5 = SHA1( canonical || X25 )
X25 = POST( SHA256( m1 ) )
m1  = MD5( sub_226E0(canonical, KEY_A) )
\```

`verify_full_b5.py` **10/10 命中**：

```python
canonical="A" → xored=23 → m1=01abfc750a0c942167651c40d088531d
             → X25=8ebf5e0cf2954d7be3f852b094fd95c7cd658c41c920dd1da32c38e967f83c62
             → b5=fe5caa73d169e6c43493a1259975d6db69f61391
\```

第五回合那个"长度依赖的 5 元环密钥流"，真相就是 KEY_A 的循环 XOR 折叠——因为它对短于自己的 canonical 做"末尾覆盖"，才表现出那种诡异的长度相关规律。

具体拆一个例子（canonical="hello"，5 字节，KEY_A 长 36 字节）。`sub_226E0` 走 `len_a < len_b` 分支：

```python
out = bytearray(5)
for i in range(36):            # i = 0..35，KEY_A 的每个字节都参与
    out[i % 5] = buf_a[i % 5] ^ KEY_A[i]   # 覆盖写
\```

因为 36 不是 5 的倍数，每个 `out[j]` 最终保留的是 **最后一个 `i % 5 == j` 的那次 XOR**：

```python
out[0] = 'h' ^ KEY_A[35]   # i=35 最后覆盖 i=0,5,...,30
out[1] = 'e' ^ KEY_A[31]   # i=31 最后覆盖
out[2] = 'l' ^ KEY_A[32]   # i=32
out[3] = 'l' ^ KEY_A[33]   # i=33
out[4] = 'o' ^ KEY_A[34]   # i=34
\```

所以 L=5 的密钥流 = `[KEY_A[35], KEY_A[31], KEY_A[32], KEY_A[33], KEY_A[34]]`。KEY_A 末尾字节是 `...46 75 76 36 62`，对应算出来正是 `62 46 75 76 36`——跟第五回合差分测到的一模一样。

>
> 这就是为什么 L=1 时"密钥流"恒为 `0x62`（= KEY_A 最后一个字节），L=2 是 `36 62`，L=3 是 `76 36 62`——它们全是 KEY_A 末尾字节的**错位切片**，根本不是独立生成的 keystream。第五回合那个"5 元环起点异常"的困惑，就是 36 不能被 5 整除导致的相位差。
>
>
>

### b6 同理（1/1 命中）

```python
b6 = SHA1( JSON前缀 || POST(SHA256(MD5(JSON前缀 XOR KEY_A))) )

JSON前缀(478B) = {"b1":"<UUID>","b2":"3.2.8.4_0","b3":"2.1","b4":"<b4>","b5":"<b5>","b7":"<b7>"}
\```

关键：b6 的 JSON 前缀**包含 b5 和 b7**（即结果里 b6 之前的全部字段）。

---

## 第十回合：密钥派生——整个算法只有一个真正秘密

抓到的 KEY_A 和 KEY_B 一开始被我当成两个独立静态密钥。验证后发现**又是错的**：

```python
KEY_A = sub_226E0(UUID, KEY_B)
\```

即 KEY_A 是 KEY_B 与 UUID 的循环 XOR 派生，不是独立常量。`verify_key_derivation.py` 逐字节验证命中。

因为 UUID（b1）是安装时固定的随机串，所以 KEY_A 看起来"静态、跨冷启动稳定"，实则是对 KEY_B 的确定性派生。

**结论：整个签名算法只有一个真正的秘密 = KEY_B（64B）。**

这也解释了 hook 里观察到的 4 次 `sub_226E0` 调用：

| 序 | buf_a | buf_b | 作用 |
|-|-|-|-|
| 1 | UUID(36B) | KEY_B(64B) | 派生 KEY_A |
| 2 | canonical | KEY_A(36B) | b5 的 xored |
| 3 | UUID(36B) | KEY_B(64B) | 重算 KEY_A（b6 路径） |
| 4 | JSON(478B) | KEY_A(36B) | b6 的 xored |

### 怎么抓 KEY_B / KEY_A

前面脱敏里说"抓取方法见后文"，就是这里。抓法很直接——**hook `sub_226E0`，把每次调用的 buf_a / buf_b 都打出来**：

```javascript
// hook_226e0_key.js 核心
Interceptor.attach(Module.getBaseAddress('libjdg.so').add(0x226E0), {
  onEnter(args) {
    const lenA = args[1].toInt32(), lenB = args[3].toInt32();
    console.log(`sub_226E0 lenA=${lenA} lenB=${lenB}`);
    console.log(`  A = ${hexdump(args[0], {length: Math.min(lenA, 64)})}`);
    console.log(`  B = ${hexdump(args[2], {length: Math.min(lenB, 64)})}`);
  }
});
\```

按上表，第一次调用 `buf_a = UUID(36B)`、`buf_b = KEY_B(64B)`——**buf_b 就是 KEY_B**。UUID 是 b1 的明文，抓包里直接有。拿到 KEY_B + UUID，`sub_226E0(UUID, KEY_B)` 一算就是 KEY_A，所以**只需抓 KEY_B 一把，KEY_A 不必单独抓**。

>
> 更省事的入口：KEY_B 存在全局 map 的 `"a6"` 键里（见第十二回合），直接 hook `sub_1DE30`（map 查找）在 key=`"a6"` 时 dump 返回值也能拿到。两者等价，`sub_226E0` 那个对不熟悉 map 结构的读者更直观。
>
>
>

---

## 第十一回合：b4 破解（RC4 + zlib 设备指纹负载）

七个字段里 b4 是最复杂的——245B 二进制、base64 328 字符、每请求变。它的构造链：

```python
b4 构造函数 sub_216C4（真身 0x216fc）
  → 拼字符串(decrypt_str + append)
  → .rand/.random/.atoll（随机 + 时间）
  → .compress（zlib 压缩）
  → sub_2349C（hex 编码）
  → sub_1DE30（KEY 派生）
  → RC4 KSA + PRGA
  → base64
\```

base64 调用链：`0x2b8bc(main) → 0x205cc → 0x20f60 → sub_216C4 → 0x22354 → base64(0x2390c→0x14f4c)`。

### 完整 b4 算法

```python
# 输入
eid   = u()    # dfpEid 设备指纹
pkg   = "com.jingdong.app.mall"
devid = MD5(APK 签名证书 DER) 大写 hex
ver   = "13.1.0"
flags = v()    # 设备 flags 串（含 §§ 分隔符）
ts    = 毫秒时间戳

# 1. b4 明文（392B JSON）
plain = {"e1":"<eid>","e2":"1.0§§0§§<pkg>|<devid>|<ver>§§<flags>","e3":<ts>,"e4":""}

# 2. zlib 压缩 → 244B（首字节 78 9c）
comp = zlib.compress(plain)

# 3. RC4 加密 → 244B
rc4_key = str(ts) + SHA1(UUID)     # 53B
enc = RC4(comp, rc4_key)

# 4. 加前缀 0x07 + base64 → 328 字符
b4 = base64(0x07 + enc)
\```

### 关键识别

- **RC4 原语**：KSA `sub_15148`（`S[i]=i; j=(j+S[i]+key[i%kl])&0xFF` 交换）、PRGA `sub_15220`（标准流加密），跳转壳 `0x1EDD0/0x1EDD4`。
- **RC4 密钥固定后缀 = SHA1(UUID)**：`SHA1("6bbc8976-d0fe-44ef-9776-ab9da0c127e8") = 966479bf34cb1eae71c4d44bfce0421893f29a24`，精确命中。
- **devid = MD5(APK 签名证书 DER) 大写 hex**：keytool 提取证书 DER（587B）算 MD5 大写，精确命中。

b4 明文结构：

```json
{
  "e1": "eidA2d0e8122a7s4HiyOlHjySiC4wtkkpv4HVB4skDXdMgetjyjINgLw8AuMLPaSIaiDpVN1dc3Yz/dPKu86YVe18dxGIE7rtM1fEZUERZk++zQq0gdC",
  "e2": "1.0§§0§§com.jingdong.app.mall|E0D1A70367C58D5D41C4678DFD05F84F|13.1.0§§<flags串>",
  "e3": 1792757438778,
  "e4": ""
}
\```

- **e1** = dfpEid（u() 传入）
- **e2** = `w()§§0§§<包名|MD5(证书)|版本>§§<flags串>`，分隔符是 UTF-8 的 `§`（字节 `c2 a7`）
- **e3** = 毫秒时间戳
- **e4** = 空字符串

离线复现：zlib 解压 RC4 输入得 392B 明文 JSON；RC4 复现 out 与 hook 逐字节相等。

**至此 b1~b7 七字段全部还原。**

---

## 第十二回合：KEY_B 从哪来——一张 60×60 的 Data Matrix 二维码

最后追 KEY_B 的出生地。动态 hook `sub_1DE30`（map 查找函数），发现每次签名调它 2 次：

| 调用 | key | 输出 | 含义 |
|-|-|-|-|
| #1 | `"a11"` | `966479bf...`(40B) | SHA1(UUID) |
| #2 | `"a6"` | `<KEY_B>`(64B) | 设备根密钥 |

KEY_B 和 SHA1(UUID) 都是全局对象 map 里的条目。继续追初始化函数 `sub_1DBA4`：

| 参数 | 值 | 含义 |
|-|-|-|
| a2 | anon rw- 堆指针 | **Data Matrix PNG 数据** |
| a3 | 6406 | PNG 长度 |
| a4 | `"com.jingdong.app.mall"` | 包名 |
| a5 | `"E0D1A70367C58D5D41C4678DFD05F84F"` | MD5(证书) 大写，全局固定 |

a2 内容前 8 字节 `89504e470d0a1a0a` = PNG magic，IHDR 显示 **60×60**、位深 8、颜色类型 6（RGBA）。

追下去发现 `sub_1C450` 是一个 **Data Matrix（ECC200）解码器**（我之前误判成 QR 码，纠正了），内嵌完整 PNG 解码器：

- `sub_1BF6C` = PNG 头解析（IHDR/CRC）
- `sub_1D450` = PNG 去滤波（filter 0-4 = None/Sub/Up/Average/Paeth）
- `sub_1C264` = RGB→RGBA 扩展（PLTE 调色板）
- `sub_1C35C` = tRNS 透明解析

Data Matrix 区域表：`dword_81794=[1,0,3,1,2,0,4]` 等 5 张。

**KEY_B 不是 so 内置常量、不是 apk 静态资源，而是编码在一张 60×60 的 Data Matrix 二维码里，运行时解码进 map。**

这张 PNG 在 so 里和 apk 资源里都搜不到，是运行时 anon 堆数据 → 要么运行时生成，要么从加密数据解密，要么网络下发。**来源尚未定位**（这是本文最后一个未决项，见诚实边界）。

---

## 结果：完整算法 + 离线复现脚本

把整条链拼起来，jdgs 的完整算法如下：

```python
# ============ 输入 ============
canonical  # 规范化请求串 = HTTP方法 + " " + path + " " + 排序后 k=v
UUID       # b1，安装时随机
ts         # b7，毫秒时间戳
eid        # dfpEid 设备指纹
flags      # 设备 flags 串
pkg / ver / devid  # 全局固定

# ============ 密钥 ============
KEY_B   # 设备根秘密（64B，唯一秘密）
KEY_A   = sub_226E0(UUID, KEY_B)          # 派生 36B

# ============ b5 ============
xored = sub_226E0(canonical, KEY_A)
m1    = MD5(xored)
X25   = POST(SHA256(m1))                  # out[i]=(sha[i]+t1[i])^t2[i]
b5    = SHA1(canonical || X25)            # 40 hex

# ============ b4 ============
plain = {"e1":eid,"e2":"1.0§§0§§pkg|devid|ver§§flags","e3":ts,"e4":""}
comp  = zlib.compress(plain)
enc   = RC4(comp, str(ts) + SHA1(UUID))
b4    = base64(0x07 + enc)                # 328 字符

# ============ b6 ============
prefix = {"b1":UUID,"b2":"3.2.8.4_0","b3":"2.1","b4":b4,"b5":b5,"b7":ts}
xored2 = sub_226E0(prefix, KEY_A)
m2     = MD5(xored2)
X25_2  = POST(SHA256(m2))
b6     = SHA1(prefix || X25_2)            # 40 hex

# ============ 输出 ============
jdgs = {"b1":UUID,"b2":"3.2.8.4_0","b3":"2.1","b4":b4,"b5":b5,"b7":ts,"b6":b6}
\```

### 密码学原语总表

| 原语 | 位置 | 说明 |
|-|-|-|
| MD5 | core 0x18190 / wrapper 0x232cc | wrapper 内 NEON 转大写 hex |
| SHA-1 | 0x1554c | IV 前 4 个与 MD5 共用，h4=0xC3D2E1F0 用立即数构造 |
| SHA-256 | init 0x272ac / 方法表 off_9E5A0 | IV@0x9e5b0 + K@0x9e5d0 |
| POST | VM finalize 表 | out[i]=(sha[i]+t1[i])^t2[i] |
| RC4 | KSA 0x15148 / PRGA 0x15220 | 跳转壳 0x1EDD0/0x1EDD4 |
| zlib | compress/inflate 导入 | b4 明文压缩 |
| base64 | 0x14f4c / wrapper 0x2390c | 表@0x80fb8 |
| XOR | sub_226E0 (0x22738) | 循环 XOR 工具 |
| 字符串混淆 | decrypt_str 0x19ddc | 滚动 XOR `dst[i]=src[i]^((key+3*i)&0xff)` |

### 离线复现脚本

我把整条链固化成了一个脚本 `jdgs_sign.py`，喂入 KEY_B + 当次输入，直接吐出完整 jdgs：

核心实现（节选自 `scripts/jdgs_sign.py`，逐行对应 libjdg.so 的原语）：

```python
# ---------- 原语：逐一复刻 libjdg.so ----------
def sub_226e0(buf_a, buf_b):
    """sub_226E0：循环 XOR + 末尾覆盖语义。"""
    len_a, len_b = len(buf_a), len(buf_b)
    out = bytearray(len_a)
    if len_a > len_b:
        for i in range(len_a):
            out[i] = buf_a[i] ^ buf_b[i % len_b]
    else:
        for i in range(len_b):
            out[i % len_a] = buf_a[i % len_a] ^ buf_b[i]   # 覆盖写
    return bytes(out)

def rc4(key, data):                      # KSA 0x15148 + PRGA 0x15220
    S = list(range(256)); j = 0; kl = len(key)
    for i in range(256):
        j = (j + S[i] + key[i % kl]) & 0xff
        S[i], S[j] = S[j], S[i]
    i = j = 0; out = bytearray()
    for b in data:
        i = (i + 1) & 0xff; j = (j + S[i]) & 0xff
        S[i], S[j] = S[j], S[i]
        out.append(S[(S[i] + S[j]) & 0xff] ^ b)
    return bytes(out)

T1 = bytes.fromhex("788a0409a538ff39a0b920c0e7d5e8ecae1d24f0759a5ba3fdb82a6829e1a638")
T2 = bytes.fromhex("4c907a161bc9b6697a65847382c3041194ab22db6ced9d80f172c073eb474a5f")

def post_sha256(m):                      # X25 = POST(SHA256(m))
    sha = hashlib.sha256(m).digest()
    return bytes(((sha[i] + T1[i]) & 0xff) ^ T2[i] for i in range(32))

# ---------- 三段签名 ----------
def calc_b5(canonical, key_a):
    xored = sub_226e0(canonical, key_a)
    m1 = hashlib.md5(xored).digest()
    return hashlib.sha1(canonical + post_sha256(m1)).hexdigest()

def calc_b4(eid, flags, ts, uuid):
    plain = ('{"e1":"%s","e2":"1.0§§0§§%s|%s|%s§§%s","e3":%s,"e4":""}'
             % (eid, PKG, DEVID, VER, flags, ts)).encode("utf-8")
    key = (ts + hashlib.sha1(uuid.encode("utf-8")).hexdigest()).encode("utf-8")
    return base64.b64encode(b"\x07" + rc4(key, zlib.compress(plain))).decode("ascii")

def calc_b6(uuid, b4, b5, ts, key_a):
    prefix = ('{"b1":"%s","b2":"3.2.8.4_0","b3":"2.1","b4":"%s","b5":"%s","b7":"%s"}'
              % (uuid, b4, b5, ts)).encode("utf-8")
    xored = sub_226e0(prefix, key_a)
    m2 = hashlib.md5(xored).digest()
    return hashlib.sha1(prefix + post_sha256(m2)).hexdigest()

def sign_jdgs(KEY_B, uuid, eid, flags, canonical, ts=None):
    key_a = sub_226e0(uuid.encode(), KEY_B.encode())
    ts = ts or str(int(time.time() * 1000))
    b5 = calc_b5(canonical.encode(), key_a)
    b4 = calc_b4(eid, flags, ts, uuid)
    b6 = calc_b6(uuid, b4, b5, ts, key_a)
    return ('{"b1":"%s","b2":"3.2.8.4_0","b3":"2.1","b4":"%s","b5":"%s","b7":%s,"b6":"%s"}'
            % (uuid, b4, b5, ts, b6))
\```

三个容易被忽略、但一旦写错就全错的细节：

1. **`sub_226e0` 的覆盖写语义**：短串异或长密钥时**不是**循环取模，而是"末尾覆盖"——这就是第九回合 L=5 相位差的根因。
2. **`§` 是 UTF-8 的 `c2 a7`**：b4 明文 e2 里的分隔符是 §（U+00A7），不是 ASCII。`.encode("utf-8")` 会正确处理，但别手写 `\xa7` 或 ASCII 分隔符。
3. **b4 前导 `\x07`**：`base64(0x07 + RC4(...))` 这个 0x07 是版本标记字节，解包时要先跳过再 RC4。

自测结果（`python jdgs_sign.py --self-test`）：

```python
[KEY_A] sub_226E0(UUID, KEY_B) = ... OK
[b5] 10/10 命中
[b6] = ... OK
自测结果：ALL PASS
\```

---

## 诚实边界（做到了什么 / 没做到什么）

1. **七字段 b1~b7 全部还原并黑盒验证命中**（b5 10/10、b6 1/1、b4 逐字节）。
2. **KEY_B 的生成链没有还原**：我只定位到"KEY_B 编码在一张 60×60 的 Data Matrix 码里、运行时解码进 map"，但**这张 PNG 从哪来**（运行时生成 / 加密数据解密 / 网络下发）还没查到。
3. **KEY_B 是全局固定还是设备相关，未验证**：需要重装 App 看 KEY_B 变不变。若全局固定，直接硬编码即可彻底脱离设备；若设备相关，才需要继续追 PNG 生成/下发链。
4. **canonical 的精确构造没有在脚本里 1:1 复刻**：脚本里的 `build_canonical` 是参考实现，真实规则（参数 key/value 各自 URL 编码、先 value 再 key 排序、非 form body 追加 SHA-256）在 Java 层 `pc.e.q()`，需要时用 jadx 精确还原。
5. **b4 端到端未在自测里重算**：自测的 b6 是拿已知 b4 串算的，没从 eid/flags 端到端重算 b4（缺真实样本硬编码）。

---

## 复盘：真正的转折点

回头看，把死路串起来，真正的转折点有这几个：

1. **意识到 `-3107` 是 Java 层短路，不是 native 检测**——否则会在 native 里空找半天。
2. **动态拿到真实 jdgs，推翻静态的"拼接串"结论**——OLLVM 下的纯静态分析，结论必须动态兜底。
3. **从"猜哈希"转向"方法表 + 全入口 hook"**——不再猜，直接钉死调用面。
4. **发现 SHA-1 的 IV 与 MD5 共用**——这是"搜不到常量所以不存在"误判的根因，也是全文最有价值的一个坑。
5. **KEY_A = XOR(UUID, KEY_B)**——把两个"独立密钥"收敛成一个根秘密，问题规模瞬间缩小。

### 方法论（可迁移）

- **OLLVM 混淆下，纯静态分析是不可靠的**。正确的姿势是"静态定位 + 动态验证"双轨，动态用受控差分/故障注入/雪崩测试做黑盒收敛，静态用来理解代码结构。
- **搜不到常量 ≠ 算法不存在**。字节搜索只能做阳性证据，做不了阴性证据。常量可能用立即数构造（SHA-1 的 h4）、可能被混淆（滚动 XOR）、可能在运行时解密。
- **一次只改一个变量**。受控差分实验是逆向签名算法最有效的武器，比硬啃 OLLVM 快得多。

### 留一句给同行

>
> 逆向里最贵的不是"看不懂的代码"，而是"自以为看懂了、其实是错的"的结论。**每一个"板上钉钉"，都值得再用动态证据锤一遍。**
>
>
>

---

# 回复

## 回复 by mb_adiebzjv (#2)

你这个纯ai的吧，我看到了好多熟悉的词。ai面前所有客户端防御就如同渣渣一样，只有服务端能挡住了

## 回复 by mb_adiebzjv (#3)

所有的主流app已经全部纯算了

## 回复 by mb_ldbucrik (#4)

666

## 回复 by xiao_qi_lin (#5)

没那么简单

## 回复 by mb_adiebzjv (#6)

>
> [xiao_qi_lin](https://bbs.kanxue.com/user-1071700.htm)
>  没那么简单
>

我刚入门，用ai都随便解这个app了，在ai面前没有啥难度的。不用学，不用会，谨慎点说花一个星期学会个入门就行。剩下的就是花token的事。

## 回复 by mb_ykavguun (#7)

666

## 回复 by everme (#8)

666

## 回复 by 威兹曼 (#9)

666

## 回复 by MaYil (#10)

感谢分享

## 回复 by fixother (#11)

滴滴滴
