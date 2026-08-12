---
title: '[原创]Claude Cowork 全自动跑通：海外加固 DexProtector 反 Frida 检测绕过实战'
url: https://bbs.kanxue.com/thread-291748.htm
tid: 291748
author: Little_Z
date: '2026-06-22'
tags: [Android安全, 原创]
crawled_at: '2026-08-12T04:00:39+00:00'
replies: 10
---

# Claude Cowork 全自动跑通：海外加固 DexProtector 反 Frida 检测绕过实战

>
> 本文仅用于授权安全测试、自研样本分析和学习交流。文中所有分析均发生在本人可控测试环境中，目的在于理解移动应用加固与反调试对抗机制，不涉及接口滥用、数据获取、商业风控绕过或未授权攻击。
>
>
>

---

>
>  **生成说明**
>
>
> 本文由 **Claude Cowork**（Anthropic 桌面版 AI 协作工具）全程自动辅助完成。**从样本首次注入崩溃，到 `antifrida.js` 稳定跑通、本文输出完毕，总计耗时约 4 小时 17 分钟。** 这里"跑通"的判定标准是：在 Frida 注入状态下，App 完整启动并进入指定主页，进程全程不闪退、不出现意外终止。同样的分析路径如果纯手动完成——手写每一版探针、人工 grep 日志、逐条更新假设记录——保守估计需要 2 到 3 天。
>
>
> Claude Cowork 在整个分析过程中自动读取 IDA Pro 导出的伪代码文件和 maps 文本、自动生成并迭代 Frida 探针脚本、自动执行 adb 命令采集运行时日志、自动归纳每轮实验结论并更新假设，最终输出本文及 `antifrida.js` 的完整注释版本。人工介入仅限于：确认每一轮实验方案、在手机上触发 App 启动、以及对最终结论做最后核查。
>
>
> 换句话说，Claude Cowork 扮演的是一个能持续工作、不怕日志长的分析搭子——它把"读伪代码 → 写探针 → 看日志 → 更新结论"这条循环跑通了，人只需要在关键节点做判断。时间压缩的核心不是 AI 更聪明，而是它不需要在"写代码 → 切终端 → 复制日志 → 回编辑器"这些上下文切换上消耗时间。
>
>
>

---

## 0x00 AI 不是魔法棒，而是逆向现场的第二块屏幕

过去做 Android 逆向，遇到 Java 层逻辑还算友好：`jadx` 搜关键词、看调用链、Frida 打点，基本能很快建立入口视图。但一旦样本进入 native 加固，节奏会明显变慢。

这类场景里，真正耗时的通常不是"会不会写一段 Hook"，而是下面这些问题：

- 加固库什么时候加载，关键逻辑是不是藏在 `JNI_OnLoad` 后面；
- Java 层看到的壳类、真实业务 dex、匿名 native 代码段之间是什么关系；
- Frida 注入后到底触发了哪一种检测，是 `/proc/self/maps`，线程巡检，inline hook 字节校验，还是代码段自哈希；
- 某个 Hook 点到底是在解决问题，还是制造新的完整性污染；
- 大量日志、偏移、伪代码和运行结果如何沉淀成可复现证据。

这次 Claude Cowork 全程接管了整个分析链路：从最初的环境搭建、工具安装，到探针脚本生成、日志采集、IDA 伪代码归纳、假设迭代，一直到最终输出稳定绕过脚本和本文，全部自动完成。人工介入只有三件事：在手机上点启动、在关键分叉点确认方向、做最后核查。

本文选择一个公开分发的海外 App 样本作为案例，核心目标是绕过 `libdexprotector.so` 中的 Frida/注入/完整性检测，让 App 能在 Frida 注入状态下稳定运行。最终稳定脚本保存在本地的 `antifrida.js`，本文重点记录从环境搭建、崩溃定位、试错到稳定绕过的完整自动化过程。

## 0x01 目标与环境

样本信息如下：

\```
App 类型: 海外加固样本
包名:     com.Hyatt.hyt
版本:     World of Hyatt 6.8.0
核心库:   libdexprotector.so
目标:     绕过 Frida/注入/完整性检测
重点:     native 反检测、匿名代码段、字符串解密、线程巡检、自哈希
\```

样本来源：

\```
下载地址: https://www.apkmirror.com/apk/hyatt-corporation/world-of-hyatt/world-of-hyatt-6-8-0-release/world-of-hyatt-6-8-0-android-apk-download/
版本:     World of Hyatt 6.8.0
格式:     APKMirror APK Bundle / APKM
\```

测试环境：

| 项目 | 配置 |
|-|-|
| 测试机 | 红米 K50 |
| 系统版本 | Android 14 |
| Root 方案 | APatch |
| Frida 版本 | 16.7.19 |
| native 分析 | IDA Pro 9.3 |
| 辅助工具 | Claude Cowork、PowerShell、adb、frida-tools |

从业务角度看，这类样本并不是单纯的"壳对抗练手题"。酒店、出行、金融、IoT 门禁等 App 往往会集成账号、会员、支付、证书、蓝牙钥匙或设备可信状态判断，一旦反调试和运行环境校验逻辑被误配、过度依赖客户端，安全测试人员就需要验证它到底能挡住什么、会不会影响正常业务、是否存在被动态分析绕过后的风险暴露。

AI 辅助逆向已经从"帮忙解释几行伪代码"进入到"全程自动化分析闭环"的阶段。本文记录的不是一组手动操作步骤，而是 Claude Cowork 如何从零开始自动搭建环境、采集日志、生成脚本、归纳结论，最终输出可复现的完整报告。

### 环境自动搭建

Claude Cowork 在启动分析前，自动检测并完成了以下环境配置：

```powershell
# 1. 检测 Python/pip 环境，自动安装 frida-tools
pip install frida-tools

# 2. 根据设备 Android 版本和 CPU 架构，自动选择并下载对应的 frida-server
#    (设备: Android 14 arm64-v8a → frida-server-16.7.19-android-arm64)
Invoke-WebRequest -Uri "https://github.com/frida/frida/releases/download/16.7.19/frida-server-16.7.19-android-arm64.xz" `
  -OutFile frida-server.xz

# 3. 解压并通过 adb 推送到测试机
7z e frida-server.xz
adb push frida-server /data/local/tmp/
adb shell chmod 755 /data/local/tmp/frida-server

# 4. 验证 adb 连接和 frida-server 可用性
adb shell /data/local/tmp/frida-server &
frida-ls-devices
\```

以上步骤由 Claude Cowork 全部自动执行，输出确认环境就绪后才进入样本分析阶段。

APKM 安装方式：

```powershell
Expand-Archive -LiteralPath .\World-of-Hyatt-6.8.0.apkm `
  -DestinationPath .\hyatt_680_apkm -Force

Get-ChildItem .\hyatt_680_apkm -Recurse -Filter *.apk

adb install-multiple `
  .\hyatt_680_apkm\base.apk `
  .\hyatt_680_apkm\split_config.arm64_v8a.apk `
  .\hyatt_680_apkm\split_config.xxxhdpi.apk
\```

以上命令由 Claude Cowork 自动生成并执行，安装完成后自动验证 App 可正常启动。

![环境自动搭建：推送 frida-server、解压安装 Hyatt APKM、确认包名已安装](https://bbs.kanxue.com/upload/attach/202606/734635_U9BARJ9M98G9DQ3.png)

随后 Claude Cowork 自动通过 spawn 模式注入空脚本，记录到 App 立即闪退。

![spawn 模式下注入近乎空白的 antifrida.js，App 在 resume 后立刻抛出 java.lang.RuntimeException: DP: 786，FATAL EXCEPTION 显示是 MessageGuardException](https://bbs.kanxue.com/upload/attach/202606/734635_KXKPC3HM269ZPD4.png)

这说明检测发生得非常早，Claude Cowork 据此自动判断：优先分析 native 加固层，而不是普通 Java 层业务逻辑，并进入下一阶段的加载链路探测。

## 0x02 从加载链路入手：先知道谁杀了进程

第一轮不急着写绕过代码。Claude Cowork 自动读取了当前目录下的 IDA 分析备注和已有的 adb 日志，判断当前阶段需要一个最小加载链路探针，随即生成了第一版脚本：只 Hook `dlopen` 和 `android_dlopen_ext`，观察 App 启动阶段加载了哪些 so，然后通过 adb 自动推送执行，采集回日志。

```javascript
function hook(name) {
  var addr = Module.findGlobalExportByName
    ? Module.findGlobalExportByName(name)
    : Module.findExportByName(null, name);

  if (!addr) return;

  Interceptor.attach(addr, {
    onEnter: function (args) {
      this.path = args[0].isNull() ? '<null>' : args[0].readCString();
    },
    onLeave: function (retval) {
      console.log(name + ' ' + this.path + ' => ' + retval);
    }
  });
}

setImmediate(function () {
  hook('dlopen');
  hook('android_dlopen_ext');
});
\```

日志里可以看到关键加载顺序：

\```
libalice.so
libdpboot.so
libdexprotector.so
\```

![把 dlopen 探针通过 frida -U -f 注入后的真实终端日志：android_dlopen_ext 依次加载 libframework-connectivity-jni.so、libforcedarkimpl.so、libalice.so、libdpboot.so、libdexprotector.so，随后进程崩溃并抛出 DP: 786 异常](https://bbs.kanxue.com/upload/attach/202606/734635_GMTD9MK32699BGE.png)

Claude Cowork 把这次日志归纳成一份简短结论：崩溃前最后加载成功的是 `libdexprotector.so`，崩溃点位于 `ProtectedTopHyattApplication.onCreate` 里的一处 native 调用 `com.Hyatt.hyt.ProtectedTopHyattApplication.ttghdCr(Native Method)`，异常信息里也明确出现了 `DP`，说明是 DexProtector 的检测逻辑触发了终止——这进一步坐实了"重点转向 `libdexprotector.so`"的判断。

![image](https://bbs.kanxue.com/upload/attach/202606/734635_39E3BVVJ8DNEY3N.png)

崩溃发生在 `libdexprotector.so` 加载之后，因此重点转向该库。继续观察 `JNI_OnLoad`，IDA 里可以看到 `JNI_OnLoad` 并不直接承载全部逻辑，而是从全局位置取出一个函数指针继续执行。

关键点在 `libdexprotector.so + 0xC838`。

![image](https://bbs.kanxue.com/upload/attach/202606/734635_J8EC4DX6DAAHZN5.png)

Claude Cowork 分析完日志后，自动在上一版脚本基础上迭代：当 `android_dlopen_ext` 捕获到 `libdexprotector.so` 后，定位导出符号 `JNI_OnLoad`，在进入 `JNI_OnLoad` 时读取 `base + 0xC838` 保存的指针。

```javascript
var DP_SLOT_OFFSET = 0xC838;

Interceptor.attach(jniOnLoad, {
  onEnter: function () {
    var slot = module.base.add(DP_SLOT_OFFSET);
    var entry = slot.readPointer();
    console.log('libdexprotector.so[0xC838] @ ' + slot + ' => ' + entry);
  }
});
\```

一次运行结果：

\```
libdexprotector.so base=0x763b529000 JNI_OnLoad=0x763b52cc50
libdexprotector.so[0xC838] @ 0x763b535838 => 0x763b4ea984
\```

这个地址并不在 `libdexprotector.so` 的 ELF 映射范围内。继续读取 `/proc/self/maps`：

\```
763b49c000-763b518000 r-xp 00000000 00:00 0 [anon:15f1e]
\```

也就是说，真正执行的保护逻辑被搬到了一个匿名可执行映射中。后续分析里的 `DP image` 指的就是这一段匿名代码镜像。

## 0x03 Dump 匿名代码段：把运行时保护逻辑拖回 IDA

接下来需要把该匿名段 dump 出来，保存到应用私有目录，再 `adb pull` 到本地。

核心逻辑是先根据地址查找 maps，再按映射范围读取内存：

```javascript
function findMapByAddress(addr) {
  var lines = File.readAllText('/proc/self/maps').split('\n');
  for (var i = 0; i < lines.length; i++) {
    var m = /^([0-9a-f]+)-([0-9a-f]+)\s+(\S+)\s+\S+\s+\S+\s+\S+\s*(.*)$/i.exec(lines[i]);
    if (!m) continue;

    var start = ptr('0x' + m[1]);
    var end = ptr('0x' + m[2]);
    if (addr.compare(start) >= 0 && addr.compare(end) < 0) {
      return { line: lines[i], start: start, end: end, perms: m[3], path: m[4] };
    }
  }
  return null;
}
\```

Dump 后保存为 `anon.so`。它不是正常 ELF，所以在 IDA 中以 ARM64 little-endian 原始二进制方式打开。

这里需要说明一下后面反复出现的 `0x4F254` 是怎么来的。

第一步是把 `0xC838` 读出的运行时地址换算成匿名段内偏移。由于 Android 开了 ASLR，每次运行时基址都会变化，所以不能直接拿 `0x763b4ea984` 这类运行时地址去 IDA 里找。正确做法是用同一次运行里 `/proc/self/maps` 找到的匿名段起始地址做减法：

\```
匿名段入口偏移 = 0xC838 保存的函数指针 - 该指针所在 maps 段的 start
\```

例如某次运行中日志如下：

\```
libdexprotector.so[0xC838] @ 0x763b535838 => 0x763b4ea984
maps: 0x763b49c000-0x763b518000 r-xp ... [anon:15f1e]
\```

那么入口偏移就是：

\```
0x763b4ea984 - 0x763b49c000 = 0x4E984
\```

也就是说，`0x4E984` 是 `JNI_OnLoad` 后真正跳进匿名保护镜像的入口。把 dump 出来的 `anon.so` 放进 IDA 后，先跳到 `0x4E984` 看入口函数，再沿着它的调用链和动态 Hook 日志继续追。

第二步才定位到 `0x4F254`。在 `0x4E984` 入口附近继续跟进后，可以看到它会进入一个更大的保护调度函数；动态打点时也发现该函数返回了非零值，是导致后续保护流程中断的关键路径。这个函数在匿名镜像中的偏移就是：

\```
0x4F254
\```

所以本文后面分析的 `0x4F254` 并不是从 ELF 静态符号表里来的，也不是固定运行时地址，而是：

\```
运行时读 0xC838 指针 -> 根据 maps 换算匿名段入口 0x4E984 -> 在 IDA/Hook 中沿调用链定位关键检测主函数 0x4F254
\```

由于 dump 出来的匿名段缺少完整段信息，IDA 里会出现一些红色的 `MEMORY[0x8A800]` 访问。手动补一个覆盖常量区的 segment 后，伪代码可读性会提升很多。

## 0x04 Claude Cowork + IDA MCP 分析 Frida 检测的总体思路

拿到 `anon.so` 后，如果直接从某个函数开始硬啃，很容易陷入两个问题：一是函数数量多、偏移跳转频繁，二是加固代码里大量函数名都是 `sub_xxx`，看一会儿就会失去全局方向。所以这里采用的是"先搭架构，再逐点验证"的方式。Claude Cowork 自动接入 IDA MCP，完成了一轮全局梳理。

Claude Cowork 在这一阶段的工作方式是：自动读取 IDA 导出的伪代码文本文件（每次 IDA MCP 返回新内容后 Claude Cowork 直接接收），在本地工作目录维护一份函数假设表，并在每轮 Frida 日志回来后自动更新状态。

整体流程可以拆成五步：

\```
1. 入口确认
   通过 Frida 读取 libdexprotector.so + 0xC838，定位匿名段入口 0x4E984。

2. 静态展开
   在 IDA 中从 0x4E984 开始看调用链，找出直接调用、间接调用和关键返回值。

3. 语义分组
   Claude Cowork 自动结合伪代码、字符串引用、交叉引用，把 sub_xxx 按功能分组，输出带置信度的候选名称表。

4. 函数重命名
   对已确认功能的函数临时重命名，避免后续分析一直在 sub_161E8、sub_61974 之间来回跳。

5. 动态验证
   Claude Cowork 自动生成对应的 Frida Hook 脚本，通过 adb 推送执行，采集参数、返回值和崩溃点后自动更新 IDA 中的命名和注释。
\```

这里 Claude Cowork 不是单独看一段伪代码就下结论，而是和 IDA MCP 形成一个闭环：IDA 负责提供真实反汇编、伪代码、交叉引用、调用树；Claude Cowork 负责把这些碎片整理成"哪些函数像字符串解密，哪些像 maps 收集，哪些像哈希，哪些像线程巡检"的候选列表；最后再由 Frida 动态日志确认。

我在分析时大致按下面这套架构拆分：

\```
libdexprotector.so
  └─ JNI_OnLoad
       └─ 读取 +0xC838 指针
            └─ [anon:15f1e] DP image
                 ├─ 0x4E984  运行时入口
                 ├─ 0x4F254  保护调度 / 检测主路径
                 ├─ 0x40814  字符串解密
                 ├─ 0x55650  字符串解密
                 ├─ 0x161E8  自哈希 / SipHash 类逻辑
                 ├─ 0x310D8  大块区域哈希 / SHA256 类逻辑
                 ├─ 0x61974  maps 解析入口
                 ├─ 0x61D08  maps item 收集器
                 ├─ 0x5B70C  inline hook 检测
                 ├─ 0x5BE28  maps 巡检线程入口
                 └─ 0x5D1A4  CRC/完整性巡检线程入口
\```

这些名字不是一开始就知道的，而是在"静态观察 + 动态命中 + 日志复盘"后逐步改出来的。比如 `sub_40814` 和 `sub_55650` 最初只是两个普通函数，直到 Hook 返回值能看到 `ActivityThread`、`/proc/self/maps`、`DexFile` 等字符串，才把它们命名为字符串解密函数。`sub_161E8` 也是先通过 IDA 里大量向量运算特征怀疑为哈希，再通过运行时命中和自校验污染现象确认它参与了 DP 镜像自哈希。

实际操作时，Claude Cowork 通过 IDA MCP 自动完成了两件事：先批量读取目标函数伪代码、调用者和被调用者，再根据确认后的语义批量重命名。大致命名如下：

| 原始偏移 | 分析后的临时名称 | 命名依据 |
|-|-|-|
| `sub_4E984` | `dp_runtime_entry` | `0xC838` 指针直接跳入的匿名段入口 |
| `sub_4F254` | `dp_protection_dispatch` | 入口后进入的大型保护调度函数，返回值影响启动流程 |
| `sub_40814` | `dp_decrypt_string_jni` | Hook 返回大量 JNI/ART 相关字符串 |
| `sub_55650` | `dp_decrypt_string_app` | Hook 返回真实 Application 类名和业务相关字符串 |
| `sub_14F7C` | `dp_kdf_absorb` | 向 136 字节上下文持续喂入环境材料和检测结果 |
| `sub_15128` | `dp_kdf_final` | 对上下文做收尾，输出 32 字节材料 |
| `sub_14F48` | `dp_kdf_clean` | 清理派生上下文，避免敏感材料残留 |
| `sub_27A9C` | `dp_crypto_get_algorithm` | 通过算法编号取 crypto vtable，`9` 被后续派生函数反复使用 |
| `sub_27308` | `dp_crypto_extract_or_init` | 使用固定常量和 32 字节输入生成中间密钥材料 |
| `sub_27398` | `dp_crypto_expand` | HKDF expand 风格函数，使用 8 字节 info/nonce 扩展出不同长度密钥 |
| `sub_206E0` | `dp_crypto_final_verify_tag` | 加密上下文 final，并做 16 字节 tag 校验 |
| `sub_161E8` | `dp_siphash_region` | 向量运算特征明显，运行时命中自哈希路径 |
| `sub_310D8` | `dp_sha256_region` | 处理大块镜像区域，和后续完整性校验相关 |
| `sub_61974` | `dp_parse_proc_maps` | 读取并解析 `/proc/self/maps` |
| `sub_61D08` | `dp_collect_map_item` | 对单条 maps item 做权限和路径收集 |
| `sub_5B70C` | `dp_check_inline_hook` | 返回非零时命中 libc/libart 函数头检测 |
| `sub_5BE28` | `dp_maps_scan_worker` | maps 巡检线程入口 |
| `sub_5D1A4` | `dp_crc_scan_worker` | 完整性巡检线程入口 |

![image](https://bbs.kanxue.com/upload/attach/202606/734635_GNXWBEFCPMD2TS3.png)

函数重命名很重要。未重命名前，笔记里只能写"`sub_61974` 调了 `sub_61D08`，然后影响 `sub_4F254` 返回值"，读两遍就乱了；重命名后就能表达为"maps 解析入口调用 maps item 收集器，最终影响保护调度主路径"。这一步会直接影响后面写 Hook 时的判断质量。

Claude Cowork 每轮自动输出两类结果：

\```
第一类：分析表
偏移、候选函数名、证据、可信度、下一步验证方式。

第二类：Hook 计划
应该 Hook 哪个地址、打印哪些参数、返回值是否能改、改返回值可能有什么副作用。
\```

这样做的好处是不会一开始就陷入"把所有可疑点都 return 0"。对于 Frida 检测，最怕的就是粗暴 Hook：有些检测确实可以改返回值，有些检测必须修输入，有些检测不能碰父流程，只能处理工作线程入口。Claude Cowork 的作用是帮我把这些可能性列出来，再用最小 Hook 去验证。

除了普通 Hook 日志，我还在脚本最开始放了一个 `installExceptionLogger()`。它不是绕过函数，而是崩溃定位器。反 Frida 对抗里最麻烦的情况是 App 直接闪退：logcat 只能看到 native crash 或进程消失，但不知道是 DP 匿名段哪个偏移触发的，也不知道是访问非法地址、非法指令，还是 Frida 修改代码后导致的校验副作用。

![编写 exception_logger_probe.js 并通过 spawn_test.py 反复试跑、排查 frida-server 异常退出的过程](https://bbs.kanxue.com/upload/attach/202606/734635_W46PZURPTJPV4VX.png)

`installExceptionLogger()` 使用 Frida 的 `Process.setExceptionHandler` 注册异常回调，只关注三类异常：

```javascript
Process.setExceptionHandler(function (details) {
  if (details.type !== 'access-violation' &&
      details.type !== 'segmentation-fault' &&
      details.type !== 'illegal-instruction') {
    return false;
  }

  var pc = details.context.pc;
  var map = findMapByAddress(pc);
  var inDpImage = dpBase && pc.compare(dpBase) >= 0 &&
    pc.sub(dpBase).compare(ptr(DP_IMAGE_MAX_SIZE)) < 0;

  if (!inDpImage) return false;

  console.log('[exception] pc=' + pc +
    ' DP+0x' + pc.sub(dpBase).toString(16) +
    ' lr=' + details.context.lr +
    ' fault=' + details.memory.address);

  return false;
});
\```

这里最后返回 `false` 很重要，表示异常仍交还给系统处理。也就是说，它不负责"吞异常"或"救活进程"，只负责在进程死前把关键现场打印出来。

通过这种方式，反 Frida 追踪会从黑盒变成白盒：

\```
原始状态:
App 闪退 -> logcat 看到 crash -> 不知道是哪个检测点

加入 exception logger 后:
App 闪退 -> 打印 pc / lr / fault address / maps -> 换算 DP+offset -> 回 IDA 定位函数
\```

例如日志里如果出现：

\```
[exception] type=access-violation pc=0x7bc3d0a258 DP+0x16258 lr=...
\```

就可以直接回到 IDA 的 `0x16258` 附近看代码，再结合 `lr` 和栈上的返回地址判断是谁调用了它。如果 `pc` 不在 DP image，而是在 `libart.so` 或 oat 里，也能反向说明问题可能已经进入 Java/ART 层，比如保护 dex 的栈检查、dex_pc 一致性检查或业务 SDK 异常。

这个方法在本文里主要解决三个问题：

1. **判断崩溃归属**：确认 crash 是发生在 DP 匿名镜像、`libdexprotector.so`，还是 ART/业务层；
2. **定位静态地址**：把运行时 `pc` 换算成 `DP+offset`，然后回 IDA 找具体函数；
3. **区分检测和副作用**：如果某个 Hook 后崩溃点变成哈希、解密或 tag 校验相关地址，往往说明 Hook 本身污染了上游输入，而不是找到了真正的检测返回值。

所以 `installExceptionLogger()` 的思路不是"异常来了就跳过"，而是把每一次崩溃当成定位信号。很多关键结论，比如自哈希污染、`0x206E0` tag 失败、保护 dex 上取 Java 栈导致 ART 崩溃，都是靠这种异常现场和 IDA 偏移互相印证出来的。

接下来进入具体分析：Claude Cowork 自动读取 `0x4F254` 及其调用链的 IDA MCP 伪代码，开始分析保护调度主路径到底在检查什么。

## 0x05 从 0x4F254 开始：第一次误判不是所有非零返回都来自 Frida bitmask

Claude Cowork 自动读取 `0x4F254` 附近的伪代码后，给出了第一个分析方向：很多加固会把环境检测结果按位叠加到 bitmask 中，例如：

\```
bit0: 默认端口
bit1: 内存特征
bit2: 异常线程
bit3: 命名管道
...
\```

如果检测到多个特征，就不断执行：

```c
flags |= DETECT_FRIDA_PORT;
flags |= DETECT_FRIDA_MEMORY;
flags |= DETECT_FRIDA_THREAD;
\```

最后只要 `flags != 0` 就触发保护。

这个模型在很多样本里有效，但这次动态验证后发现：部分可疑检测函数返回值都是 `0`，而 `0x4F254` 的最终返回 `1` 并不是来自那组最直观的 Frida/root/env bitmask。

这里是 AI 辅助逆向时很重要的一点：Claude Cowork 能给出方向，但方向必须被日志验证。它的输出不能直接当结论，只能当下一轮实验计划。

当时我把检测思路重新拆成七类：

| 类型 | 常见方式 |
|-|-|
| 网络通信特征 | 扫描 `27042`、D-Bus 握手 |
| maps 检测 | 扫 `/proc/self/maps`、查 `frida`、查异常可执行段 |
| 线程检测 | 查 `gmain`、`gdbus`、`gum-js-loop` |
| 代码段破坏 | 函数头字节校验、CRC、磁盘内存比对 |
| 文件残留 | `/data/local/tmp/frida-server`、`.frida` |
| 异常信号 | `SIGTRAP`、非法指令、异常处理器 |
| 符号来源 | `dladdr`、导出表、可疑地址归属 |

结合"加载后立即崩溃"和"Hook 之后行为变化"两个现象，后续重点转向代码完整性检测和 maps 归一化。

## 0x06 密钥派生链路：为什么自校验会影响后续解密

继续看 `0x4F254` 时，一个很关键的发现是：它并不是简单地"检测到 Frida 后返回错误码"。在多处环境检测之前和之后，它都在维护一块上下文 `v76`，不断把运行时材料喂进去，最后派生出后续解密/校验要用的密钥材料。

这类逻辑可以理解成 KDF，也就是 Key Derivation Function，密钥派生函数。它的作用不是直接保存一个固定密钥，而是把多个输入材料混合起来，生成当前运行环境下才成立的临时密钥。常见输入包括：

\```
固定常量
JNI 传入的 32 字节参数
当前设备 / 系统 / ART 信息
/proc/self/maps 等环境检测结果
加固匿名代码段的自哈希结果
不同用途的 info / nonce 常量
\```

这样设计的好处是：检测逻辑和解密逻辑被绑在一起。即使某个检测点被绕过，只要绕过方式污染了输入材料，后面派生出来的密钥就会不一致，最终表现为解密失败、tag 校验失败或者业务 dex 加载失败。

在 `0x4F254` 里，KDF 相关路径大致如下：

```c
sub_14F2C(v76);                  // 初始化派生上下文
sub_14F58(v76, v77);             // 喂入 JNI 传入的 32 字节材料

sub_3E6F4(v76, cached_arg, n);    // 喂入系统/文件状态类材料
sub_3EA0C(v76);                  // 计算代码区域哈希并喂入上下文
sub_14F7C(v76, byte_872AC, 64);   // 喂入保护配置

if (unk_8A810 != sub_161E8(unk_82948, unk_82990 - unk_82948, &tmp)) {
    sub_14F7C(v76, "\x00", 1);    // 自哈希不匹配时改变派生输入
}

sub_15128(v76, v77);             // 输出 32 字节派生材料
sub_14F48(v76);                  // 清理上下文
\```

其中 `0x14F7C` 很像"吸收输入"的 update 函数，负责把不同来源的数据喂进上下文；`0x15128` 是 final，输出 32 字节结果；`0x14F48` 负责清零 136 字节上下文。这里的结构和普通哈希/KDF 很像：init、update、final、clean。

![image](https://bbs.kanxue.com/upload/attach/202606/734635_7MP3PYR2UXNJ5PR.png)

后面还有一组更标准的派生接口：

```c
v39 = sub_27A9C(9);
sub_27308(v39, &unk_87164, 32, v77, 32, &v74);

v73 = 0x91A4FB076B659459;
sub_27398(v39, &v74, 32, &v73, 8, &v72, 4);
\```

`0x27A9C` 根据算法编号取 crypto vtable，编号 `9` 在多个函数里反复出现。`0x27308` 使用固定常量和前面得到的 32 字节材料生成中间状态，`0x27398` 则很像 HKDF expand：它接收输入密钥材料、8 字节用途常量、输出缓冲区和输出长度，内部按 block counter 一轮轮扩展。

这个判断不是只靠函数名猜的。`0x27398` 的伪代码里可以看到典型结构：

\```
取算法输出长度
计算需要多少个 block
循环写入 counter: 1, 2, ...
把前一轮输出、info 常量、counter 一起喂入
每轮生成一段输出，直到填满目标长度
\```

在其他分支里也能看到同一套模式，比如：

\```
0x3F3B8:  sub_27398(..., info=0x873552BC11E8FF0E, out_len=0x20)
0x40944:  sub_27398(..., info=0xF9A939C6FCAE9717, out_len=0x2C)
0x52174:  sub_27398(..., info=0xE5CADA586D49689A, out_len=0x24)
0x536E4:  sub_27398(..., info=0x9F5ADC9EE0B3913B, out_len=0x2C)
0x53E40:  sub_27398(..., info=0x37265C912A43CDAC, out_len=0x14)
0x563E8:  sub_27398(..., info=0xEC1AAD7D6B3AA721, out_len=0x20)
\```

这些 8 字节常量可以理解成不同用途的 domain separation。也就是说，同一个上游密钥材料，会因为用途不同派生出不同的子密钥或配置块。

再往后看，`0x206E0` 是加密上下文的 final/tag 校验点：

```c
result = sub_205A8(ctx, 1, out_len, key, ..., cipher, ...);
if (!result) {
    result = sub_20CF0(expected_tag, local_tag, 16);
    if (result) {
        memzero(out, out_len);
        return -86;
    }
}
\```

这里 `0x20CF0` 是常量时间风格的 16 字节比较函数：把两边逐字节异或并 OR 到一起，最后只返回是否存在差异。早期运行日志里可以看到：

\```
[206E0-trace] enter crypto_ctx_final_206E0 ...
[206E0-trace] leave ret=-86
\```

这个 `-86` 就是 tag 校验失败的表现。它说明前面某个输入材料已经不一致，导致派生密钥不对，最后解密自然失败。

因此这条链路给绕过策略提供了一个重要约束：不能只盯着最后的 `0x206E0` 把返回值改成 0。那样可能会让流程继续走，但输出明文、dex 内容或后续状态仍然是错的。真正稳定的做法是回到上游，让 `0x161E8`、`0x310D8` 等自校验函数读取干净镜像，保证 KDF 输入本身一致。

这也是后面脚本里没有默认启用 `bypassCryptoFinal206E0()` 的原因。`0x206E0` 只保留为窄范围兜底，真正修复点在 KDF 上游。

## 0x07 字符串解密与反 inline hook：Hook 点也会污染样本

Claude Cowork 自动读取 `0x3F12C` 附近的伪代码并分析调用链后，归纳出两个字符串解密函数：

\```
sub_55650
sub_40814
\```

直接 Hook `sub_55650` 有输出，但 Hook `sub_40814` 一开始没有输出。回到 IDA 看函数头，发现这里存在对函数入口字节的校验：一旦用 Frida inline hook 改了函数头，它不会立刻崩溃，而是改变后续解密种子，导致解出来的字符串全错。

这个设计很典型：加固不一定在发现 Hook 后马上杀进程，它也可以悄悄污染数据流，让分析者拿到一堆假线索。

处理方式是避开函数入口，在函数头后偏移几条指令的位置再挂点，避免破坏被校验的头部字节。

最早一版验证用的偏移量是 `0x40814 + 4*4`，注释里写得很直接：「向下偏移 4*4 是因为前面有反 inline hook 检测，如果不偏移就会被检测到，导致无法 hook 到真正的函数」。同时为了对比，`sub_55650` 因为没有入口自检，直接挂入口就有正确输出。

![image](https://bbs.kanxue.com/upload/attach/202606/734635_UJ2E7G29ZYYEMU2.png)

这一版偏移量较小，跑出来的是 `ttghdCr`、`getAssets`、`AAssetManager_open`、`/proc/self/fd/`、`classes.dex` 这类资源加载和 asset 相关字符串，已经能确认"避开入口字节、往后挂点"这个思路是对的。后续随着对 `sub_40814` 自检范围的进一步摸排，安全偏移量在 `string_decrypt_probe.js` 里被扩大到 `0x40814 + 0x80`，这时才稳定挂到主循环开始之前、寄存器还没被挪用的位置，拿到下面这组覆盖 `ActivityThread`/`ClassLoader`/`DexFile` 链路的完整字符串。

成功后可以看到大量真实字符串：

\```
android/app/ActivityThread
currentActivityThread
mBoundApplication
mClassLoader
loadClass
/proc/self/exe
/proc/self/maps
libc.so
__system_property_get
ro.build.version.sdk
java/lang/reflect/Executable
artMethod
dalvik/system/DexFile
dalvik/system/BaseDexClassLoader
pathList
dexElements
\```

这些字符串把保护逻辑轮廓串了起来：

- 它会拿 `ActivityThread`、`LoadedApk`、`ClassLoader` 做真实 dex 装载；
- 它会读取 `/proc/self/maps` 和 `/proc/self/exe`；
- 它会关注 `libc.so`、`__system_property_get`、ART 内部结构；
- 它会构造 `DexFile`、`ByteBuffer`，动态恢复真实业务 dex。

也就是说，反 Frida 不是孤立检测点，而是壳加载、dex 恢复、ART 结构访问和 native 自校验混在一起的一条链。

## 0x08 关键突破：代码段自哈希不是 CRC32，而是 SipHash/SHA256 链路

一开始怀疑有 CRC32 检测，Claude Cowork 自动在 IDA 里查找了 CRC32 风格实现和相关引用，确实找到过可疑点，但动态 Hook 不理想，没有命中关键路径。

随后 Claude Cowork 调整策略：现代编译器优化后的哈希/向量计算不一定保留清晰的 CRC32 函数形态，改为在伪代码中搜索 ARM64 常见向量运算特征，例如：

\```
addq_s64
veorq_s8
vorrq_s8
\```

这次命中了 `0x161E8`。运行时也能看到它被调用。结合调用上下文和返回值行为，最终确认它参与了 DP 匿名镜像的自哈希。

![image](https://bbs.kanxue.com/upload/attach/202606/734635_H4ZW6YUJ8JNSTZX.png)

最终稳定脚本中对应的处理是：

```javascript
function bypassSelfSiphash161E8(base) {
  var imageEnd = base.add(DP_IMAGE_MAX_SIZE);
  dpAttach(base.add(0x161E8), {
    onEnter: function (args) {
      var p = args[0];
      var len = args[1].toUInt32();
      this.lrOff = this.context.lr.sub(base).toUInt32();

      if (p.compare(base) >= 0 && p.compare(imageEnd) < 0 &&
          len > 0 && len < 0x200000) {
        args[0] = buildCleanShadow(p, len);
        this.redirected = true;
      }
    },
    onLeave: function (ret) {
      if (!this.redirected || this.lrOff < 0x4f500 || this.lrOff > 0x4f6e0) return;

      var expected = base.add(0x8A810).readU64();
      ret.replace(ptr('0x' + expected.toString(16)));
    }
  });
}
\```

这段代码的重点不是"把返回值改掉"，而是先把输入改对。

Frida 的 `Interceptor.attach/replace` 会在目标代码区域写入跳板，导致原始代码字节变化。如果保护逻辑读取的是已经被 Frida 改过的匿名镜像，自哈希结果自然会变化，后续密钥派生、完整性校验、AEAD tag 都可能失败。

因此我在安装 Hook 前先复制一份干净的 DP 镜像：

```javascript
function captureCleanDpSnapshot(map) {
  dpCleanSize = map.end.sub(map.start).toUInt32();
  dpClean = Memory.alloc(dpCleanSize);
  Memory.copy(dpClean, map.start, dpCleanSize);
  dpCleanEnd = map.start.add(dpCleanSize);
}
\```

后续凡是自哈希读取 DP 镜像，就重定向到干净快照：

```javascript
function buildCleanShadow(start, len) {
  if (dpClean && dpBase && dpCleanEnd) {
    var end = start.add(len);
    if (start.compare(dpBase) >= 0 && end.compare(dpCleanEnd) <= 0) {
      return dpClean.add(start.sub(dpBase).toUInt32());
    }
  }

  var buf = Memory.alloc(len);
  Memory.copy(buf, start, len);
  return buf;
}
\```

这里是整篇分析的核心：不要把所有检测都理解成"命中后返回 0"。有些保护的关键在于保持它的输入世界一致，让它自然算出正确结果。

## 0x09 maps 检测：不是删 Frida 字符串，而是归一化库映射

`/proc/self/maps` 是 Frida 检测的高频入口。常见绕法是过滤 `frida`、`gum-js` 等字符串，但这次 DP 的检查点更细。

在 `0x61974` 和 `0x61D08` 附近，它会收集 `libc.so`、`libart.so`、`libandroid_runtime.so` 的可执行映射段，并检查它们是否被切成异常多段。Frida 注入后，这些库的映射形态确实会发生变化。

稳定脚本没有直接伪造整个 `/proc/self/maps`，而是在 DP 的 maps 收集器内部做归一化：

```javascript
function bypassMapsCollector786(base) {
  var libs = ['/libc.so', '/libart.so', '/libandroid_runtime.so'];
  var spans = {};
  var seen = {};

  function computeExecutableSpans() {
    var result = {};
    var lines = readProcMaps();

    for (var i = 0; i < lines.length; i++) {
      var m = /^([0-9a-f]+)-([0-9a-f]+)\s+(\S+).*\s(\S+)$/.exec(lines[i]);
      if (!m || m[3].indexOf('x') < 0) continue;

      // 统计目标库所有可执行段的最小起点和最大终点
    }
    return result;
  }

  dpAttach(base.add(0x61974), {
    onEnter: function () {
      spans = computeExecutableSpans();
      seen = {};
    }
  });
}
\```

在收集单个 item 时，如果是第一个目标库可执行段，就把它的 end 扩展到最大 end；如果后面再次遇到同一个库的可执行段，就清掉它的执行权限位，让 DP 看到"每个库只有一个完整可执行段"。

![编辑 maps 收集器归一化探针代码并在设备上跑通的过程](https://bbs.kanxue.com/upload/attach/202606/734635_2GVCQA3WGCM2UYR.png)

这个策略比全局替换 `open/read` 更窄，副作用也更小。

值得一提的是，786 这个检测点不只在 native 层起作用。Claude Cowork 后续解码 logcat 里的崩溃现场时发现，App 在 native 层之外还会抛出一个 Java 层的 `com.Hyatt.hyt.MessageGuardException`，错误码同样是 `DP: 786`，payload 是一段编码后的十六进制字符串，解码后能看到设备指纹、系统版本等环境信息。这说明 786 的判定结果不只用于 native 流程内部分支，还会被回传到 Java 层做二次终止；同时也发现 `jni_onload_probe.js` 里用 `setTimeout(armDpProbe, 0)` 异步挂载存在竞态——`dlopen_ext` 返回后目标线程会同步紧接着调用 `JNI_OnLoad`，异步调度的 Hook 经常装晚了。修复方式是把 `armDpProbe()` 改成在 `onLeave` 里同步调用，不再依赖 `setTimeout`。

![logcat 中解码出的 DP: 786 MessageGuardException payload，以及修复 jni_onload_probe.js 异步挂载竞态的过程](https://bbs.kanxue.com/upload/attach/202606/734635_ZSKEMN83UUYUTMV.png)

## 0x0A inline hook 检测：让检测照常跑，只改命中结果

另一个检测点在 `0x5B70C`。它会检查 `libc/libart` 等函数开头是否存在 Frida 跳板特征。

这里的处理方式是让检测函数照常执行，只在返回非零时改回 0：

```javascript
function bypassLibcHookDetect751(base) {
  dpAttach(base.add(0x5B70C), {
    onLeave: function (ret) {
      var code = ret.toInt32();
      if (code !== 0) {
        console.log('[751] inline-hook detector ret=' + code + ' -> 0');
        ret.replace(0);
      }
    }
  });
}
\```

这个点和前面的自哈希不同。自哈希需要修输入，inline hook detector 可以修输出。两者不能混用思路。

如果在自哈希那里粗暴改返回，后面可能出现 AEAD tag 不一致、密钥派生错误、解密异常；如果在 inline hook detector 这里重构输入，则成本反而更高。

## 0x0B 线程巡检：不要拆父流程，只禁工作线程入口

DP 还会启动一些异步巡检线程。早期我尝试过直接替换父级 create/join 包装函数，结果后续状态不一致，反而更容易崩。

稳定方案只禁用工作线程入口：

```javascript
function bypassDirectThreadGuards(base) {
  dpReplaceReturn0(base.add(0x5BE28), 'sub_5BE28 maps scan thread');
  dpReplaceReturn0(base.add(0x5D1A4), 'sub_5D1A4 CRC scan thread');
}
\```

这种处理保留了父级创建、等待、状态更新流程，只让实际巡检体返回 0。对加固壳来说，流程形态仍然完整，状态机不容易被破坏。

## 0x0C 业务层阻断：DP 过了，还会遇到 MobileKeys 的 25

DP 绕过之后，App 进入真实业务 `Application.onCreate`。此时又遇到一个新的阻断：`MobileKeysApi.initialize` 抛出 `25 / Check failed`。

这已经不是 DexProtector 壳的 native 检测，而是业务 SDK 初始化阶段的环境检查。稳定脚本里只在业务层捕获这类异常，不碰 DP 壳包装方法：

```javascript
function isMobileKeysInitFailure(error) {
  var text = '' + error;
  return text.indexOf('RuntimeException: 25') >= 0 ||
    text.indexOf('IllegalStateException: Check failed.') >= 0 ||
    text === 'Error: 25' ||
    text.indexOf(': 25') >= 0;
}
\```

目标方法：

\```
com.assaabloy.mobilekeys.api.MobileKeysApi.initialize
com.hyt.network.mobilekey.assaabloy.AssaMobileKey.u
com.hyt.network.mobilekey.assaabloy.AssaMobileKey.v
\```

处理方式是保持原方法执行，只有捕获到特定错误时才吞掉，并按返回类型给默认值：

```javascript
overload.implementation = function () {
  try {
    return overload.apply(this, arguments);
  } catch (e) {
    if (!isMobileKeysInitFailure(e)) throw e;
    if (overload.returnType.name === 'void' || overload.returnType.name === 'V') return;
    return defaultReturnForJavaType(overload.returnType);
  }
};
\```

这里也踩过坑：之前在保护 dex 上取 Java 栈，触发过 ART 的 `dex_pc` 一致性检查崩溃。因此最终方案不做多余栈追踪，只等真实类加载后挂业务方法。

## 0x0D 最终稳定脚本结构

最终 `antifrida.js` 的结构如下：

\```
setImmediate
  ├─ installExceptionLogger()
  └─ hookAndroidDlopenExt()
       └─ libdexprotector.so loaded
            └─ hook JNI_OnLoad
                 ├─ read base + 0xC838
                 ├─ locate DP anonymous image
                 ├─ installMobileKeys25Bypass()
                 ├─ captureCleanDpSnapshot()
                 └─ installDpBypasses()
                      ├─ bypassMapsCollector786()
                      ├─ bypassSelfSiphash161E8()
                      ├─ bypassLibcHookDetect751()
                      ├─ fixDpSha256Region310D8()
                      └─ bypassDirectThreadGuards()
\```

这里把 `installExceptionLogger()` 放在最前面，是为了覆盖 `libdexprotector.so` 加载前后的早期崩溃窗口。它只记录异常现场，不改变异常处理结果，所以不会掩盖真正问题。

稳定运行日志可以看到关键绕过点安装成功：

\```
[dp] libdexprotector base=... JNI_OnLoad=...
[dp] DP image base=... entry=...
[dp-clean] snapshot base=... size=...
[786] maps collector normalized
[714] SipHash self-check redirected
[751] libc hook detector bypassed
[714] SHA256 region hash redirected
[thread-guard] worker entries disabled
[dp] stable bypass set installed
[mobilekeys] waiting for target classes
\```

Claude Cowork 持续监控进程状态，直到 App 完整进入指定主页、进程无闪退、无意外终止，才判定本轮分析目标达成，随即输出最终脚本和本文。

最终脚本保留了几个重要原则：

1. **先定位真实保护镜像**：不在 `libdexprotector.so` ELF 内盲目搜索，先从 `JNI_OnLoad` 和 `0xC838` 找匿名代码入口；
2. **Hook 前保存干净镜像**：解决 Frida 自己写跳板导致的自校验污染；
3. **按检测类型分策略**：自哈希修输入，inline hook detector 修输出，线程巡检修工作体；
4. **绕壳和绕业务分层**：DP 的 native 检测和 MobileKeys 的业务初始化异常分开处理；
5. **所有结论都经过日志验证**：Claude Cowork 给出假设，人来做动态验证和取舍。

## 0x0E Claude Cowork 在这次分析中真正有用的地方

这次 Claude Cowork 帮上忙的地方主要有四类。

**第一类是全自动生成探针脚本。** 每当分析遇到新节点，Claude Cowork 直接读取 IDA 伪代码文件，在本地生成下一版 `.js` 并自动通过 adb 推送到测试机执行——包括 `dlopen/android_dlopen_ext` 监控、`JNI_OnLoad` 拦截、maps 地址归属判断、匿名段 dump，全程不需要手动写代码。

**第二类是把 IDA 伪代码转换成实验计划。** 比如它从 `0x4F254`、`0x3F12C`、`0x161E8` 等位置整理出疑似检测点，再给出 Hook 验证方案。Claude Cowork 的价值不是"一眼看穿"，而是让试错更有序——它在本地工作目录里维护一张实时更新的"假设 → 验证状态"表，每轮日志回来后自动标注哪些假设命中、哪些作废。

**第三类是全自动日志归纳。** 动态运行会产生大量偏移、返回值、字符串、异常寄存器上下文。Claude Cowork 自动解析每轮 logcat 输出，归纳"哪些点没命中""哪个返回值不是来自 bitmask""哪些字符串指向 ClassLoader 和 maps 链路"，并输出更新后的分析摘要。

**第四类是沉淀文章和脚本注释。** 逆向过程如果只停留在脑子里，很快就会变成不可复现的经验。Claude Cowork 边分析边整理，每完成一个检测点就向本文草稿追加对应章节，最终形成的 `antifrida.js` 注释和本文结构都能直接复盘。

但有一点必须强调：**Claude Cowork 的判断会错。** 比如早期它给出的 bitmask 方向很合理，但动态验证证明不是关键路径。AI 在这里更像一个能连续工作的分析搭子，不是最终裁判——人仍然是结论的负责方。

## 0x0F 绕过检测的本质，是恢复双方看到的"同一个世界"

很多反 Frida 文章容易写成"检测点 A 返回 0，检测点 B 返回 0，App 就跑起来了"。这次样本让我印象更深的是另一件事：真正难的不是让某个函数返回成功，而是让加固壳看到一个自洽的运行世界。

Frida 注入会改变 maps，会改变函数头，会改变代码页字节，会引入线程和通信痕迹。加固壳并不是只问"有没有 frida 字符串"，它会把这些变化串成一条完整证据链。粗暴 Hook 某个点，可能刚绕过第一关，就污染了下一关的哈希输入。

最终稳定方案的关键，是把问题拆开：

- 对 maps 检测，让它看到归一化后的系统库可执行段；
- 对自哈希，让它读取 Hook 前的干净 DP 镜像；
- 对 inline hook 检测，只在命中时收窄修改返回值；
- 对线程巡检，保留父流程，只关闭工作体；
- 对业务 SDK 初始化失败，放到业务层单独处理。

这也是我认为 Claude Cowork 适合参与逆向工作的原因：它不替代判断，但能让分析过程更连续，让每一次失败都留下可追踪的证据。逆向最终还是人的工作，只是现在我们多了一块不会嫌日志长的第二屏幕。

完整稳定脚本见本地 `antifrida.js`。如果复现本文流程，建议不要直接照搬最终脚本，而是按本文顺序逐步验证每个检测点。因为在 native 对抗里，最重要的不是"有一个能跑的 Hook"，而是知道它为什么能跑。

上传的附件：
- attachment.zip

（260.64kb，63次下载）

---

# 回复

## 回复 by Little_Z (#2)

*2026-6-22 16:53*

本文在r0ysue老师指导下完成

## 回复 by bluegatar (#3)

*2026-6-22 18:02*

牛逼，就是喜欢这样的ai分析文

## 回复 by wx_Huber Barrientos (#4)

*2026-6-23 01:26*

666

## 回复 by mb_gpgkjjvd (#5)

*2026-6-23 21:41*

6

## 回复 by lackone (#6)

*2026-6-24 00:23*

6666

## 回复 by mb_rooofjxx (#7)

*2026-6-24 16:51*

666

## 回复 by 木志本柯 (#8)

*2026-6-25 12:50*

arm处理器的指令指针应该叫PC吧？x86的是rip，如果pc=0，你的这个异常记录器，还能记录有效的代码位置不。

## 回复 by 风铃i (#9)

*2026-6-25 13:49*

很难不怀疑你和卖Claude CVP是不是有什么交易, Frida 还没起来呢就Cyber了, 反而Codex一点问题没有

## 回复 by Imxz (#10)

*2026-6-25 15:43*

tql

## 回复 by birdlily (#11)

*2026-6-29 10:08*

很有技术含量的AI分析实战，辛苦了，感谢分享
