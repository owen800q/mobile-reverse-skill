---
title: '[原创]Frida 17.6.2 魔改 rusda：编译实践与反检测 Patch 的技术剖析'
url: https://bbs.kanxue.com/thread-290651.htm
tid: 290651
author: 太岁又沐风
date: '2026-04-04'
tags: [Android安全, 原创, 源码框架, 工具脚本]
crawled_at: '2026-08-08T10:13:28+00:00'
replies: 266
---

# Frida 17.6.2 魔改 rusda：编译实践与反检测 Patch 的技术剖析

---

本文以 Frida **17.6.2**、父仓库基线提交 `1ce4396d6e43d93c8604c4cd4578ff84871bcfa1`（见 `patches/deliver/README.txt`）上的 **rusda** 定制为主线。

开源和编译产物地址：<https://github.com/taisuii/rusda>

Frida 17.6 发布没多久的时候，这边其实就已经开干了，只是前段时间一直比较忙，没来得及整理出来分享。

![image](https://bbs.kanxue.com/upload/attach/202604/957122_VDNBC83V7ERA3A8.png)

编译相关的 skill 和 patch 基本都已经放到 GitHub 里了。基础编译流程这里就不再展开，一方面 Frida 官网本身已有教程，另一方面也可以参考看雪这篇文章：

<https://bbs.kanxue.com/thread-284739.htm>

## 前言

现阶段魔改 Frida 的项目其实已经不少了，之前 16.2.1 版本也有过一轮比较集中的改动。这次重新折腾 17.6.2，主要还是因为 **Frida 17.6 之后和以前确实有一些比较明显的区别**，不少旧思路不能直接平移。

另外现在工具链迭代很快，很多东西更新也很快，继续盯着老版本做文章，意义没有以前那么大。所以与其反复围绕旧版本打补丁，不如多看看新版本到底改了什么、哪些地方值得跟进。

![image](https://bbs.kanxue.com/upload/attach/202604/957122_CKC3R8G5ZJYEWN2.png)

## 检测从哪里来

常见的 Frida 检测面，大致可以分成下面几类：

| 类型 | 典型特征 | 常见手段 |
|-|-|-|
| 只读段字符串 | `frida:rpc`、`FridaScriptEngine`、`GumScript` 等 | `strings`、内存扫 `.rodata` |
| 线程名 | `gum-js-loop`、`gmain`、`gdbus`、`frida-gadget-tcp-*` 等 | 读 `/proc/.../comm` |
| 符号 | `frida_agent_main`、`frida*` 前缀 | `nm`、内存导出符号 |
| maps 路径 | `memfd:frida-agent` 等 | 扫 `/proc/pid/maps` |
| 文件/进程名 | `frida-server`、`frida-gadget.so` | 文件系统、进程列表 |
| 配置指纹 | 默认端口 `27042`/`27052`、固定临时路径等 | 扫描、启发式 |

这些检测项看起来都像“字符串问题”，但实际上并不在一个层面上。

有些只是暴露名字，改掉就行；有些则直接参与运行时逻辑，尤其是协议相关字符串，这种东西不能简单全局替换，否则表面上看是把特征抹掉了，实际上是把功能也一起改坏了。

## 怎么过：按层处理，而不是全文替换

rusda 的处理思路并不是把 `frida` 两个字全局抹掉，而是分层来做。

### 1. 协议相关明文字：不直接写明文，运行时再还原

像 `frida:rpc` 这种字符串，不只是“好扫出来”那么简单，它本身就在 RPC JSON 里参与协议。

这类字符串如果直接在源码里替换成其它常量，协议就变了。要想既保留官方协议，又尽量不在磁盘和静态反汇编里直接暴露原串，就得换一种方式处理。

这里采用的是 **XOR + 十六进制字面量**：

- 源码里不直接出现 `frida:rpc`
- 编译产物里只保留 XOR 后的 hex 串
- 运行时再解码回官方字符串

这样处理之后，磁盘文件和静态分析阶段看不到原始明文，但运行时内存里仍然会恢复成和官方一致的协议内容。

实现位置：

`subprojects/frida-core/lib/base/obfuscate.vala`

```vala
public static string decode_hex_xor (string hex) {
    var len = hex.length / 2;
    var sb = new StringBuilder.sized (len);
    for (var i = 0; i < len; i++) {
        int64 val;
        int64.try_parse (hex.substring (i * 2, 2), out val, null, 16);
        var b = (uint8) val;
        sb.append_c ((char) (b ^ XOR_KEY));
    }
    return sb.str;
}
\```

`subprojects/frida-core/lib/base/rpc.vala`

```vala
private static string get_rpc_str (bool quoted) {
    var s = Obfuscate.decode_hex_xor ("33273c31346f272536");
    return quoted ? "\"" + s + "\"" : s;
}
\```

这里顺带提一句，Frida-gum 里内嵌的一些 JS 资源如果仍然带着 `frida:rpc`，那么只改 core 这一层并不能完全覆盖。所以这种处理方式更准确地说，是把核心路径先处理掉，而不是宣称“全仓库所有相关明文都已经消失”。

### 2. `.rodata` 中的类型名和组件名：做等长反转

像 `FridaScriptEngine`、`GLib-GIO`、`GDBusProxy`、`GumScript` 这一类字符串，更多属于类型注册名、组件名或者调试可见名，常见于只读段，比较适合做静态处理。

这部分采用的是 **等长反转写回 `.rodata`**。思路比较直接：不改长度，只把原字符串字节序反过来，这样既不会引入额外长度问题，也能避免被简单的固定模式直接命中。

`subprojects/frida-core/src/topatch.py`

```python
all_patch_string = ["FridaScriptEngine", "GLib-GIO", "GDBusProxy", "GumScript"]

for section in binary.sections:
    if section.name != ".rodata":
        continue
    for patch_str in all_patch_string:
        addr_all = section.search_all(patch_str)

        for addr in addr_all:
            patch = [ord(n) for n in list(patch_str)[::-1]]
            binary.patch_address(section.file_offset + addr, patch)
\```

这种方式的优点是实现简单、对布局影响小，缺点也很明显：可读性会下降，而且它只适合处理这种“能改外观、不影响语义约定”的字符串，不适合拿去处理协议 token。

### 3. 符号：统一改名前缀

符号表同样是很常见的一层特征，尤其是导出符号或者内存导出之后，很多名字是比较显眼的。

这里的处理主要有两类：

- `frida_agent_main` 直接改成 `main`
- 其余包含 `frida`/`FRIDA` 的符号，统一替换为约定前缀，例如 `rusda`

对应实现：

```python
for symbol in binary.symbols:
    if symbol.name == "frida_agent_main":
        symbol.name = "main"
    if "frida" in symbol.name:
        symbol.name = symbol.name.replace("frida", random_name)
    if "FRIDA" in symbol.name:
        symbol.name = symbol.name.replace("FRIDA", random_name)
\```

这里有一个比较容易忽略的点：**符号改名是有联动影响的**。

比如 core 侧把 `frida_agent_main` 改成了 `main`，那么 gum 或测试代码里凡是仍然引用旧名字的地方，也要同步跟上。否则有可能出现一种比较烦的情况：构建阶段没报错，结果运行阶段符号解析失败。

### 4. 线程名：哪些能直接换，哪些不能乱动

线程名这层的检测很常见，很多检测脚本就是直接读 `/proc/pid/task/*/comm`。

典型特征包括：

- `gum-js-loop`
- `gmain`
- `gdbus`
- `frida-gadget-tcp-&lt;port&gt;`

对于前面几类，直接做二进制级替换问题不大，例如：

- `gum-js-loop` → `russellloop`
- `gmain` → `rmain`
- `gdbus` → `rubus`

但是 **`frida-gadget` 不能简单全文替换**。这点在实操里很关键，因为它不只是一个线程名字面量，还是 `frida-gadget-tcp-&lt;port&gt;` 的前缀子串，injector 那边往往会按这个格式去匹配。

如果这里粗暴做全局替换，就很容易把原本依赖 `^frida-gadget-tcp-(\d+)$` 这一类规则的逻辑给破坏掉。

所以 topatch 里不会对 `frida-gadget` 做无差别 sed。Gadget 相关前缀更适合在源码层通过约定方式处理，而不是在最终产物上全局替换。

这一点其实也能说明一个问题：**不是所有暴露出来的字符串都能按同一种方式“抹掉”**。只要某个字符串还参与匹配、协商或者逻辑分支，就必须按语义来处理，而不是只看它长得像不像特征。

### 5. maps 上的路径和 memfd 显示名

Frida 17 开始，后端已经更多尝试通过 memfd 加载。这样做之后，maps 里原本为空的 Pathname，往往会变成类似：

\```
/memfd:frida-agent (deleted)
\```

它确实不再是传统意义上的“匿名映射”了，这能规避掉一部分专门盯着 `00:00 0` 节点号的简易检测脚本；但问题在于，**名字本身还是很显眼**。

因此这部分也可以继续往前走一步，把 memfd 显示名改成和 `frida` 无关的常量，比如 `jit-cache` 之类，以减少基于 maps 路径前缀的直接命中。

### 6. 产物命名：把最表层特征先压下去

还有一层最直接的检测面，就是文件名和进程名本身。

这一层虽然最浅，但也确实最容易被命中，所以 Meson 产出的二进制名称也做了统一调整，例如：

- `frida-server` → `rusda-server`
- `frida-inject` → `rusda-inject`
- `frida-gadget.so` → `rusda-gadget.so`

它不能解决深层问题，但能有效降低文件系统、进程列表这类最表层扫描的命中率。

## 关键实现节选

这里放一下几个核心片段，基本就能对应上前面提到的几层处理。

`subprojects/frida-core/lib/base/obfuscate.vala`

```vala
public static string decode_hex_xor (string hex) {
    var len = hex.length / 2;
    var sb = new StringBuilder.sized (len);
    for (var i = 0; i < len; i++) {
        int64 val;
        int64.try_parse (hex.substring (i * 2, 2), out val, null, 16);
        var b = (uint8) val;
        sb.append_c ((char) (b ^ XOR_KEY));
    }
    return sb.str;
}
\```

`subprojects/frida-core/lib/base/rpc.vala`

```vala
private static string get_rpc_str (bool quoted) {
    var s = Obfuscate.decode_hex_xor ("33273c31346f272536");
    return quoted ? "\"" + s + "\"" : s;
}
\```

`subprojects/frida-core/src/topatch.py`

```python
for symbol in binary.symbols:
    if symbol.name == "frida_agent_main":
        symbol.name = "main"
    if "frida" in symbol.name:
        symbol.name = symbol.name.replace("frida", random_name)
    if "FRIDA" in symbol.name:
        symbol.name = symbol.name.replace("FRIDA", random_name)

all_patch_string = ["FridaScriptEngine", "GLib-GIO", "GDBusProxy", "GumScript"]

for section in binary.sections:
    if section.name != ".rodata":
        continue
    for patch_str in all_patch_string:
        addr_all = section.search_all(patch_str)

        for addr in addr_all:
            patch = [ord(n) for n in list(patch_str)[::-1]]
            binary.patch_address(section.file_offset + addr, patch)
\```

## Frida 17 带来的变化

这次重新看 17.6.2，还有一个比较直观的感受：不少以前很敏感的暴露点，官方自己也在往收敛的方向做。

### 方法 A：利用 memfd_create 消除“匿名”标签

Frida 17 在后端加载链路里已经开始尝试通过 memfd 装载，更新记录里也能看到类似 *Load backend through memfd with fallback* 的描述。

原理上，就是用 `memfd_create` 在 RAM 中创建一个虚拟文件，再对该文件执行 `mmap`。

效果是，maps 里原本可能为空的 Pathname，会显示成 `/memfd:frida-agent (deleted)` 这一类形式。虽然仍然有痕迹，但它已经不属于传统的匿名映射，对于那种专门扫 `00:00 0` 的极简脚本来说，确实能避开一部分。

### 方法 B：使用 Frida 17 收敛后的 `Memory.patchCode`

以前很多人的习惯是 `Memory.alloc` 之后直接配合 `Memory.protect(..., 'rwx')`，或者自己长期维护一块可写可执行内存。这种方式在现在这个环境下其实是比较显眼的。

Frida 17 对代码修补路径做了一些收敛，官方更倾向于在真正写入 trampoline 的瞬间才短暂打开写权限，而不是长时间维持 `rwx`。

在实践里，如果直接走 `Interceptor` 或 `Process.setExceptionHandler` 这类官方路径，很多时候权限切换会由 Frida 自己处理，大多数时间内相关页面仍然可以保持为 `r-x`。这一点虽然谈不上“隐身”，但相比老习惯，暴露面确实小一些。

### 方法 C：代码空洞注入（Code Cave）

再往前走一步，就是尽量不申请新的可疑映射，而是去找已有合法映射中的 padding、对齐空洞或者可利用区域，把跳板直接写进文件支撑的映射空间。

这样 maps 里看到的还是正常库路径，例如 `/system/lib/libc.so`，而不是一块新出现的可疑匿名页或临时页。

不过这一层已经超出本文仓库当前 patch 的范围了。更准确地说，它属于更深层的注入落点设计问题，可以作为后续方向讨论，但不应和本文这套字符串、符号、线程名层面的处理混在一起。

## 为什么魔改之后依旧无法彻底过掉检测

这个问题其实反而是最值得说清楚的。

魔改能做的，主要还是处理一部分比较显式、比较浅层的特征，比如：

- `.rodata` 里的明文字符串
- `/proc/pid/task/*/comm` 里的线程名
- ELF 符号
- `/proc/pid/maps` 里的路径前缀
- 文件名、进程名、默认端口等配置级指纹

这些东西处理完之后，确实能降低被简单规则直接命中的概率；但它解决不了所有问题，尤其解决不了更深层的完整性校验。

比如有些检测并不关心你是不是叫 Frida，而是直接检查：

- `libc` 或其它关键 so 的代码段、数据段有没有被改动
- GOT 表里关键函数地址还在不在原始 libc 范围内
- inline hook 之后的指令字节有没有变化
- 某些关键 API 或 syscall 的行为有没有偏离预期

这类检测关注的是“有没有被动过”，而不是“名字有没有改干净”。

所以说，魔改 Frida 本质上只是把一些浅层特征做了处理，**不是改完就能过所有检测**。如果有人把这件事讲成“改个字符串、改个线程名就天下无敌”，那大概率还是噱头更多一点。

## 与旧版本思路的区别

如果你用的是更早期的一些方案，常见问题一般集中在下面两点：

1. 通过 ptrace 长时间跟踪 Zygote，再配合比较复杂的 syscall 追踪去等注入时机。这种方式容易因为 `TracerPid` 异常被 RASP 检测到，而且稳定性也一般，严重时还可能把系统拖崩。
2. 依赖 `frida-java-bridge` 注入 `system_server`。这种方案对系统版本和环境变化比较敏感，很多时候兼容性问题会比想象中多。

而 Frida 17 的方向，明显是在尽量减轻这些旧路径带来的高暴露问题：

- Android 注入机制更轻量化
- 不再长期占用旧式 ptrace 路径
- 对 `system_server` 的依赖降低

这些改动确实让一些老检测点不再像以前那样有效，但也不能因此就把新版本理解成“天然免疫检测”。它只是把问题从过去那种特别显眼的系统层暴露，往更细、更深的层面重新分布了而已。

## 结语

rusda 这套魔改的意义，我觉得不在于宣称“完全绕过检测”，而在于提供了一套比较清晰的工程化思路：

- 协议相关字符串，不直接改语义，而是隐藏其静态落盘形式
- 非协议字符串、符号、线程名、maps 显示名、产物名称，分别按层处理
- 能借用 Frida 17 新机制降低暴露面的地方，就尽量顺着新机制走

但也必须承认，它主要解决的还是“特征隐藏”层的问题。真要面对完整性校验、行为检测、系统调用追踪或者更深层的运行时对抗，单靠这一层 patch 远远不够。

如果把它理解成“让产物不那么容易被简单扫出来”，这个方向是成立的；如果把它理解成“改完就能全面免疫检测”，那就高估它了。

## 效果展示

检测工具：<https://github.com/taisuii/sentry>

### 原版

![image](https://bbs.kanxue.com/upload/attach/202604/957122_D427U8JC9FVFBAC.png)

### 魔改版

![image](https://bbs.kanxue.com/upload/attach/202604/957122_7XTGWUSPTEBCG6T.png)

---

# 回复

## 回复 by jyotidwi (#2)

*2026-4-4 22:50*

tql

## 回复 by JuneKill (#3)

*2026-4-4 22:54*

感谢分享

## 回复 by Imxz (#4)

*2026-4-4 23:13*

rbq

## 回复 by tonykros (#5)

*2026-4-4 23:26*

666

## 回复 by mb_ldbucrik (#6)

*2026-4-5 00:34*

感谢分享

## 回复 by mb_elqwyvnm (#7)

*2026-4-5 00:36*

魔改 rusda

## 回复 by xianhuimin (#8)

*2026-4-5 00:49*

666

## 回复 by 熊猫吃鱼 (#9)

*2026-4-5 08:56*

666

## 回复 by lixianhuei (#10)

*2026-4-5 09:36*

6666

## 回复 by mb_qimctavn (#11)

*2026-4-5 11:19*

6

## 回复 by mb_cqcrdwgm (#12)

*2026-4-5 14:51*

666

## 回复 by 龙飞雪 (#13)

*2026-4-5 15:00*

謝謝分享。

## 回复 by Gryffindoss (#14)

*2026-4-5 20:15*

6+666

## 回复 by Kill_Log (#15)

*2026-4-5 20:17*

666666

## 回复 by wx_插曲 (#16)

*2026-4-5 21:16*

牛逼啊

## 回复 by git_55111Empycity (#17)

*2026-4-5 22:40*

666

## 回复 by 宛枫 (#18)

*2026-4-6 08:37*

看隐藏学习一下

## 回复 by 桐人dx (#19)

*2026-4-6 11:13*

看看

## 回复 by linclsky (#20)

*2026-4-6 11:36*

66666

## 回复 by mb_ohekqrwa (#21)

*2026-4-6 16:04*

6666

## 回复 by tubecityman (#22)

*2026-4-6 18:28*

66666

## 回复 by Zepp7289 (#23)

*2026-4-6 18:48*

tql

## 回复 by YANG、 (#24)

*2026-4-6 19:13*

6666

## 回复 by 我今年6岁 (#25)

*2026-4-6 21:37*

tql

## 回复 by 小迷糊ddd (#26)

*2026-4-6 22:47*

感谢楼主，参考一下。

## 回复 by FMNS (#27)

*2026-4-6 22:51*

666

## 回复 by wx_妳还是不懂 (#28)

*2026-4-6 23:24*

非常感谢

## 回复 by 鞠婧祎 (#29)

*2026-4-6 23:34*

6666

## 回复 by 猫毛茂 (#30)

*2026-4-7 00:05*

6666

## 回复 by 口艾口牙女马口牙 (#31)

*2026-4-7 00:46*

66666

## 回复 by mystica (#32)

*2026-4-7 08:41*

感谢分享

## 回复 by huangjw (#33)

*2026-4-7 09:18*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by mb_xflcgdik (#34)

*2026-4-7 09:29*

66

## 回复 by k4y0z (#35)

*2026-4-7 09:45*

666

## 回复 by 我就是小熊猫 (#36)

*2026-4-7 09:45*

6666

## 回复 by GEKEZYX (#37)

*2026-4-7 09:49*

666

## 回复 by huangbof (#38)

*2026-4-7 10:04*

看隐藏学习一下

## 回复 by 七浪 (#39)

*2026-4-7 10:21*

文章把协议类字符串和纯特征串分层处理的思路讲得很清楚，17.6 之后 memfd、权限收敛这些点也有参考价值，先收藏慢慢啃。

## 回复 by XCicada (#40)

*2026-4-7 12:20*

>
> [JuneKill](https://bbs.kanxue.com/user-676726.htm)
>  感谢分享
>

绿蛙

## 回复 by 一栋奥特曼 (#41)

*2026-4-7 12:28*

tql

## 回复 by 夜惜风雨 (#42)

*2026-4-7 12:46*

66666666666

## 回复 by mb_pesxllvn (#43)

*2026-4-7 14:09*

666

## 回复 by mb_cbgtaveo (#44)

*2026-4-7 14:33*

66666666666666

## 回复 by xingbing (#45)

*2026-4-7 15:32*

謝謝分享。

## 回复 by amwait (#46)

*2026-4-7 16:20*

66

## 回复 by mb_euhyowpw (#47)

*2026-4-7 16:21*

666

## 回复 by mb_jqtgqcds (#48)

*2026-4-7 17:27*

zan

## 回复 by Snark (#49)

*2026-4-7 18:17*

1111

## 回复 by fjqisba (#50)

*2026-4-7 18:38*

999

## 回复 by ZACSN12 (#51)

*2026-4-7 21:37*

学习

## 回复 by 带带弟弟吧 (#52)

*2026-4-8 09:54*

1

## 回复 by pan_634488 (#53)

*2026-4-8 10:41*

666

## 回复 by lackone (#54)

*2026-4-8 12:01*

666666

## 回复 by 秃顶 (#55)

*2026-4-8 13:33*

感谢分享

## 回复 by 寻梦之璐 (#56)

*2026-4-8 14:13*

666

## 回复 by 墨穹呢 (#57)

*2026-4-8 15:06*

感谢分享

## 回复 by mb_ybvqgbkl (#58)

*2026-4-8 16:00*

6666666

## 回复 by Ld1ng (#59)

*2026-4-8 17:29*

666

## 回复 by 徐天意 (#60)

*2026-4-8 17:37*

支持

## 回复 by 乐活 (#61)

*2026-4-8 17:56*

666

## 回复 by wx_听书人 (#62)

*2026-4-8 18:48*

666

## 回复 by 丶咖啡猫丶 (#63)

*2026-4-9 09:25*

666

## 回复 by Aar0n (#64)

*2026-4-9 13:31*

666

## 回复 by hekes (#65)

*2026-4-9 15:52*

看一看

## 回复 by mb_uktygsmq (#66)

*2026-4-9 16:26*

666

## 回复 by wx_春风十里 (#67)

*2026-4-9 19:47*

6666

## 回复 by 苏幻墨 (#68)

*2026-4-9 20:42*

这个讨论对我很有帮助，谢谢！

## 回复 by 孤梦拾遗 (#69)

*2026-4-10 10:04*

感谢分享

## 回复 by tjytjy (#70)

*2026-4-10 16:31*

666

## 回复 by 残枫 (#71)

*2026-4-10 16:42*

66666

## 回复 by wx_fly_397447 (#72)

*2026-4-10 21:40*

6666

## 回复 by kingking888 (#73)

*2026-4-10 22:26*

666

## 回复 by mb_nkjfyhkg (#74)

*2026-4-11 02:12*

mark

## 回复 by zz胡 (#75)

*2026-4-11 09:46*

6666666

## 回复 by git_59284capslock199299 (#76)

*2026-4-11 11:52*

666

## 回复 by mb_ysikfhxt (#77)

*2026-4-11 14:15*

111

## 回复 by 外交 (#78)

*2026-4-11 15:45*

mack

## 回复 by x_power (#79)

*2026-4-11 16:28*

66666

## 回复 by fangliangz (#80)

*2026-4-11 16:37*

666

## 回复 by jw8888 (#81)

*2026-4-11 16:57*

111

## 回复 by mb_iyozxdcx (#82)

*2026-4-12 05:13*

感谢分享

## 回复 by vdaoren (#83)

*2026-4-12 10:59*

![image](https://bbs.kanxue.com/view/img/face/039.gif)

## 回复 by guijingwen (#84)

*2026-4-12 11:08*

66

## 回复 by 毛毛毛毛虫 (#85)

*2026-4-12 11:16*

看看

## 回复 by mb_sucnifie (#86)

*2026-4-12 14:54*

66

## 回复 by 花情 (#87)

*2026-4-13 06:03*

看看隐藏

## 回复 by git_24708cy3ber (#88)

*2026-4-13 09:10*

xiexie

## 回复 by 中文fjja (#89)

*2026-4-13 09:29*

感谢分享

## 回复 by 云觞 (#90)

*2026-4-13 11:01*

666666666

## 回复 by mb_tcheuwvg (#91)

*2026-4-13 11:46*

qqqq

## 回复 by jccforever (#92)

*2026-4-13 11:56*

谢谢分享

## 回复 by iBa0 (#93)

*2026-4-13 14:45*

牛逼

## 回复 by koflfy (#94)

*2026-4-13 15:21*

mark

## 回复 by mb_zyqgxkzt (#95)

*2026-4-14 09:09*

感谢分享

## 回复 by r0reborn (#96)

*2026-4-14 09:33*

6666

## 回复 by uni7corn (#97)

*2026-4-14 14:01*

感谢分享

## 回复 by wgetlaidu (#98)

*2026-4-14 14:08*

666666

## 回复 by mb_chjjqnap (#99)

*2026-4-15 09:24*

学习

## 回复 by mb_exxfhcyj (#100)

*2026-4-15 09:39*

66
6

## 回复 by mb_bzkmcyjt (#101)

*2026-4-15 11:02*

666

## 回复 by Am1re (#102)

*2026-4-15 17:35*

666

## 回复 by KOKOA (#103)

*2026-4-15 19:08*

tql

## 回复 by Freax (#104)

*2026-4-15 20:25*

666

## 回复 by mb_ykavguun (#105)

*2026-4-15 20:40*

111

## 回复 by git_14248bibinocode (#106)

*2026-4-15 21:16*

66666666666666666

## 回复 by qiepei (#107)

*2026-4-16 11:50*

感谢分享

## 回复 by wx_无法回头的伪装 (#108)

*2026-4-16 15:04*

66666

## 回复 by mb_unkmqemn (#109)

*2026-4-16 20:54*

666

## 回复 by git_28196hllpdfreader (#110)

*2026-4-17 09:40*

tql

## 回复 by git_28196hllpdfreader (#111)

*2026-4-17 09:40*

thanks

## 回复 by mb_pivwkzjg (#112)

*2026-4-17 16:44*

66666666666

## 回复 by pangzibupang (#113)

*2026-4-18 03:02*

感谢分享

## 回复 by mb_agxdcibq (#114)

*2026-4-18 13:33*

111

## 回复 by wx_人土土可可 (#115)

*2026-4-18 13:54*

学习

## 回复 by mb_bwxyybya (#116)

*2026-4-19 20:41*

66666

## 回复 by 0x25519 (#117)

*2026-4-21 15:42*

感谢分享

## 回复 by 斗转南see雪 (#118)

*2026-4-21 16:20*

666

## 回复 by git_33309Jackie1018 (#119)

*2026-4-21 20:33*

学习

## 回复 by 末日大哥 (#120)

*2026-4-21 21:48*

666

## 回复 by 木魚· (#121)

*2026-4-22 09:51*

qqqq

## 回复 by mb_julmypgz (#122)

*2026-4-22 10:58*

1111

## 回复 by lr04d (#123)

*2026-4-22 11:08*

666

## 回复 by wx_Dispa1r (#124)

*2026-4-23 14:01*

1

## 回复 by mb_cehqmdor (#125)

*2026-4-23 14:48*

667

## 回复 by shuangmou (#126)

*2026-4-24 16:48*

感谢分享

## 回复 by mb_yjiuccxa (#127)

*2026-4-24 17:37*

666

## 回复 by mb_rirvdrlh (#128)

*2026-4-25 02:00*

66666

## 回复 by mb_hbqdmtuz (#129)

*2026-4-25 12:51*

6666

## 回复 by qqqiu (#130)

*2026-4-25 14:41*

4

## 回复 by AGSFGBKILO (#131)

*2026-4-25 15:13*

牛啊

## 回复 by mb_mlyojneh (#132)

*2026-4-26 15:03*

感谢分享

## 回复 by davan (#133)

*2026-4-26 19:57*

666666

## 回复 by mb_miylylso (#134)

*2026-4-29 15:04*

1

## 回复 by cs_jackw (#135)

*2026-4-29 18:29*

牛

## 回复 by cs_jackw (#136)

*2026-4-29 18:29*

牛

## 回复 by cs_jackw (#137)

*2026-4-29 18:30*

666

## 回复 by PPTV (#138)

*2026-4-29 18:54*

魔改 rusda

## 回复 by huangze (#139)

*2026-4-29 18:54*

感谢分享！

## 回复 by PPTV (#140)

*2026-4-29 18:55*

魔改 rusda

## 回复 by huangze (#141)

*2026-4-29 18:55*

感谢分享！

## 回复 by PPTV (#142)

*2026-4-29 18:55*

魔改rusda

## 回复 by PPTV (#143)

*2026-4-29 18:55*

魔改frida

## 回复 by PPTV (#144)

*2026-4-29 18:55*

魔改

## 回复 by PPTV (#145)

*2026-4-29 18:55*

666

## 回复 by PPTV (#146)

*2026-4-29 18:55*

666

## 回复 by 4Chan (#147)

*2026-4-30 14:14*

学习了

## 回复 by Mix_Xuan (#148)

*2026-4-30 20:11*

太强了

## 回复 by mb_eumnbkwy (#149)

*2026-5-1 17:28*

33

## 回复 by ClPrada (#150)

*2026-5-1 17:48*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_hztwvrcw (#151)

*2026-5-4 08:55*

666

## 回复 by 樊辉 (#152)

*2026-5-4 11:39*

感谢分享

## 回复 by Wolfxyb (#153)

*2026-5-5 09:13*

6666666666

## 回复 by yyyyy——— (#154)

*2026-5-6 10:30*

666

## 回复 by 水下游泳 (#155)

*2026-5-6 14:44*

666

## 回复 by git_86585flowclouds (#156)

*2026-5-6 19:13*

学习学习

## 回复 by mb_lzsjiukj (#157)

*2026-5-8 20:49*

666

## 回复 by Harden13 (#158)

*2026-5-11 16:35*

666

## 回复 by wx_Oh.漏 (#159)

*2026-5-11 19:59*

66666

## 回复 by 鼻屎怪 (#160)

*2026-5-12 13:33*

tql

## 回复 by 学计算机睡觉 (#161)

*2026-5-12 17:10*

tql

## 回复 by mb_jbrcpjfk (#162)

*2026-5-12 17:25*

想看看

## 回复 by 落雪无尘V (#163)

*2026-5-13 19:01*

支持一下啊啊

## 回复 by mb_tewbhakr (#164)

*2026-5-15 03:02*

太酷啦

## 回复 by LeYiAo (#165)

*2026-5-15 03:38*

支持一下

## 回复 by 心在o (#166)

*2026-5-15 05:46*

太感谢了

## 回复 by mb_ivovcbzr (#167)

*2026-5-15 07:16*

看看。。

## 回复 by 猛学 (#168)

*2026-5-15 09:39*

123

## 回复 by mb_ezmrnfsu (#169)

*2026-5-15 22:25*

6666

## 回复 by Ruinv6 (#170)

*2026-5-17 00:37*

11111111111111111

## 回复 by shuaiaimei (#171)

*2026-5-17 13:50*

KANX看下隐藏的内容

## 回复 by git_107370xcmore (#172)

*2026-5-17 23:18*

666

## 回复 by mb_ofgyxagz (#173)

*2026-5-19 20:17*

看看

## 回复 by wx_！_336 (#174)

*2026-5-19 21:13*

1

## 回复 by mb_guzdnhio (#175)

*2026-5-20 20:26*

666

## 回复 by uboluo (#176)

*2026-5-21 16:13*

666

## 回复 by mb_rbaigqfb (#177)

*2026-5-21 16:23*

学习一下

## 回复 by mb_utwoxiqj (#178)

*2026-5-21 17:26*

666

## 回复 by ljfifa2002 (#179)

*2026-5-23 12:27*

膜拜大神，学习。。。

## 回复 by mb_aimnntrv (#180)

*2026-5-23 13:18*

666

## 回复 by mb_uohfzjqw (#181)

*2026-5-23 15:28*

666

## 回复 by 呆萌的小白 (#182)

*2026-5-23 16:23*

魔改frida,真好

## 回复 by mb_weufbroc (#183)

*2026-5-23 21:20*

这可是好东西啊

## 回复 by wx_故事与酒 (#184)

*2026-5-23 23:27*

666666666666666666

## 回复 by 洋少QQ (#185)

*2026-5-24 11:37*

很不错啊

## 回复 by 逆向小龙 (#186)

*2026-5-24 12:39*

tql

## 回复 by mb_njwchjvd (#187)

*2026-5-24 21:24*

666666

## 回复 by mb_zurizkle (#188)

*2026-5-25 07:08*

66666

## 回复 by mb_mxsesokv (#189)

*2026-5-25 14:46*

666

## 回复 by mb_kumzialx (#190)

*2026-5-25 19:14*

666

## 回复 by mb_paeqogwt (#191)

*2026-5-26 10:57*

66666

## 回复 by jygzyc (#192)

*2026-5-26 11:04*

666

## 回复 by git_73135NiaLark (#193)

*2026-6-3 11:09*

感谢

## 回复 by 这谁写的代码 (#194)

*2026-6-4 04:25*

6666

## 回复 by mb_xjdhrmck (#195)

*2026-6-6 19:03*

45646

## 回复 by sbmatch (#196)

*2026-6-7 07:57*

666666

## 回复 by 笑对VS人生 (#197)

*2026-6-10 00:02*

支持下

## 回复 by mb_enbuhisq (#198)

*2026-6-10 11:18*

666666

## 回复 by mb_gndxmsix (#199)

*2026-6-10 14:02*

6666

## 回复 by mb_awqgymxv (#200)

*2026-6-10 14:05*

666

## 回复 by Bileton (#201)

*2026-6-10 16:17*

666

## 回复 by mb_gywomfeb (#202)

*2026-6-10 17:13*

学习一下！！

## 回复 by 猜我是谁_610897 (#203)

*2026-6-11 16:34*

666

## 回复 by 北口 (#204)

*2026-6-11 16:42*

![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by mb_girssugh (#205)

*2026-6-12 15:32*

V5可口可乐了

## 回复 by 过我眼即我有 (#206)

*2026-6-13 18:02*

kkyc

## 回复 by gegon (#207)

*2026-6-13 22:50*

github 上的 rusda-gadget-17.6.2-android-arm64.so.xz
 是不是打包错了？实际是个32位的
ELF 32-bit LSB shared object, ARM, EABI5

## 回复 by mb_jegknedl (#208)

*2026-6-15 03:29*

酷酷酷

## 回复 by 钱钱钱￥ (#209)

*2026-6-15 09:14*

666

## 回复 by E_Obj (#210)

*2026-6-15 10:07*

6666

## 回复 by mb_kgneopde (#211)

*2026-6-15 12:30*

666

## 回复 by mb_wcqyrmzd (#212)

*2026-6-15 15:42*

11

## 回复 by mb_wvpaswat (#213)

*2026-6-18 10:25*

6666

## 回复 by YooHaa (#214)

*2026-6-18 16:05*

666

## 回复 by method (#215)

*2026-6-18 16:24*

1

## 回复 by 无名之辈 (#216)

*2026-6-18 17:10*

厉害了我的哥

## 回复 by 在下猫猫 (#217)

*2026-6-18 17:15*

66666666666

## 回复 by 袁伟业 (#218)

*2026-6-18 19:13*

666

## 回复 by mb_ejzdqciv (#219)

*2026-6-19 06:26*

嗯嗯嗯

## 回复 by JWPL (#220)

*2026-6-19 07:15*

666

## 回复 by mb_dxpfahkh (#221)

*2026-6-21 16:42*

666666666666666

## 回复 by mb_dcjxxhsk (#222)

*2026-6-22 11:01*

6666

## 回复 by lbunknow (#223)

*2026-6-22 16:18*

高手

## 回复 by buluo533 (#224)

*2026-6-23 08:45*

6666

## 回复 by mb_huiwuebg (#225)

*2026-6-23 08:58*

tql

## 回复 by mb_qnrjnwyl (#226)

*2026-6-23 20:36*

看看

## 回复 by mb_tdijwbiu (#227)

*2026-6-26 17:06*

1

## 回复 by nuomida (#228)

*2026-7-3 15:56*

学习一下

## 回复 by mb_hktfsykj (#229)

*2026-7-5 10:21*

6666

## 回复 by wx_宇克鴻 (#230)

*2026-7-5 12:28*

6666

## 回复 by mb_htgkuynr (#231)

*2026-7-5 14:20*

kankn

## 回复 by mb_veedqzbk (#232)

*2026-7-6 05:49*

666

## 回复 by wangez8 (#233)

*2026-7-6 07:46*

感谢分享![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by hzzheyang (#234)

*2026-7-8 15:18*

666

## 回复 by lazybulazy (#235)

*2026-7-9 10:06*

666

## 回复 by as-jhan (#236)

*2026-7-9 11:09*

6666

## 回复 by 西瓜很大 (#237)

*2026-7-9 11:31*

666

## 回复 by 番茄丶 (#238)

*2026-7-11 15:53*

6666

## 回复 by is王瑜 (#239)

*2026-7-13 16:52*

66

## 回复 by GeaC (#240)

*2026-7-13 17:50*

好，支持

## 回复 by wx_Z._538 (#241)

*2026-7-14 00:42*

111

## 回复 by ~时光荏苒 (#242)

*2026-7-14 04:44*

6666

## 回复 by 黑屏 (#243)

*2026-7-14 08:35*

tql

## 回复 by wx_Y_786749 (#244)

*2026-7-15 14:23*

safe

## 回复 by ikunnn (#245)

*2026-7-15 15:28*

1111

## 回复 by mb_iiumogmn (#246)

*2026-7-15 17:36*

感谢分享rusda的详细技术剖析

## 回复 by wx_寻_333 (#247)

*2026-7-17 14:53*

![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by dob_C (#248)

*2026-7-17 16:21*

感谢分享

## 回复 by mb_qupzepyf (#249)

*2026-7-20 09:59*

66666

## 回复 by chaego (#250)

*2026-7-20 10:10*

好东西啊啊啊

## 回复 by Vengeance (#251)

*2026-7-20 10:26*

666

## 回复 by mb_wiuhlhwy (#252)

*2026-7-23 10:27*

学习一下

## 回复 by Yuuuual (#253)

*2026-7-23 13:31*

学习记录，感谢分享

## 回复 by zhao3261 (#254)

*2026-7-24 23:54*

学习一下

## 回复 by qihui (#255)

*2026-7-25 10:32*

感谢分享

## 回复 by xtyuns (#256)

*2026-7-25 10:43*

感谢分享

## 回复 by haris4687 (#257)

*2026-7-25 11:42*

6

## 回复 by git_51684xuexijiaoben (#258)

*2026-7-25 12:00*

好好学习一下只

## 回复 by 逆向小龙 (#259)

*2026-7-28 17:05*

tql

## 回复 by v5w7crq3 (#260)

*2026-7-31 12:58*

666

## 回复 by 道友请留步 (#261)

*2026-7-31 14:02*

111111111111111111

## 回复 by zckeyer (#262)

谢谢分钟

## 回复 by 尤瑟努 (#263)

6666

## 回复 by mb_fhsaoxbf (#264)

tql

## 回复 by mb_bobdxdrc (#265)

看看隐藏

## 回复 by 阿沁· (#266)

感谢分享，学习一下

## 回复 by 天路 (#267)

11
