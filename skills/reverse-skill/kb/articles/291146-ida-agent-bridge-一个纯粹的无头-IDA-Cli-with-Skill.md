---
title: '[原创] ida-agent-bridge，一个纯粹的无头 IDA Cli with Skill'
url: https://bbs.kanxue.com/thread-291146.htm
tid: 291146
author: jikjgygjhg
date: '2026-05-08'
tags: [Android安全, 原创, 逆向分析, 工具脚本]
crawled_at: '2026-08-08T10:09:11+00:00'
replies: 75
---

# ida-agent-bridge

# 引言

项目地址：[ida-agent-bridge](https://github.com/TsingShui/ida-agent-bridge)，如果可以的话，可以给个 Star
**目前仅在 Macos \ Linux** 测试, Windows 不是我的常用工作环境，不过理论上是通用的。
结合 **IDA-No-Mcp**、**IDA-Pro-MCP**、**Agent Bash Tool** 我喜欢的部分进行设计，为 AI 静态分析提供更流畅的体验。

**核心能力速览：**

1. 常用能力 Cli 化：反编译、反汇编、Xref、Hexdump ，Agent Friendly 设计
2. 复杂脚本执行能力：支持完整的 IDA Domain Api、Ida Python 脚本执行能力
3. 实时的、增量刷新的 Ida-No-Mcp FileSystem，让 Ai 永远阅读最新的代码

# Readme

CLI 优先、无头、AI-Native 的 IDA Pro 分析桥，遵循 Unix 设计哲学。每条命令输出纯文本，与 `grep`、`sort`、`awk`、`jq` 等工具自然组合；反编译结果实时同步到本地文件系统——Agent 像读文件一样读二进制，脚本像管道一样串联分析流程。

## 安装

**环境要求：** IDA Pro 9.1.0+

```bash
# macOS 示例：export IDADIR="/Applications/IDA Professional 9.3.app/Contents/MacOS"
[ -z "$IDADIR" ] && echo "请先设置 IDADIR，示例：export IDADIR=\"/Applications/IDA Professional 9.3.app/Contents/MacOS\"" && exit 1

git clone https://github.com/TsingShui/ida-agent-bridge.git ~/.claude/skills/ida-agent-bridge
uv tool install ~/.claude/skills/ida-agent-bridge
\```

## 快速开始

```bash
ida-bridge a.out              # 启动，导出到 ./ida-bridge-a.out/
ida-bridge a.out --shell      # 同上，另开交互 shell（端口 13121）
ida-bridge a.out --repl-only  # 仅启动 REPL，跳过导出
\```

**首次启动**：IDA 自动分析 → 反编译预热（耗时随文件体积增长）→ 全量导出

**后续启动**：对比函数 hash，只导出变更函数，秒级完成。

## 核心能力示例

### 实时文件系统

启动后自动导出到本地目录，修改函数名、注释、字节等操作**实时同步**，调用方级联刷新：

```python
ida-bridge-<name>/
├── decompile/            每个函数一个 <ADDR>.c，内嵌 func-hash / callers / callees
├── function_index.tsv    函数索引（地址、名称、复杂度指标、调用关系）
├── strings.tsv           字符串表（addr、encoding、contents）
├── imports.tsv           导入表（addr、module、name）
└── exports.tsv           导出表（addr、name）
\```

以下操作会自动触发对应文件的重新导出：

| 操作 | 更新范围 |
|-|-|
| 重命名函数/符号 | 该函数 + 所有 caller |
| 修改注释（地址级、函数级、行内） | 该函数 |
| 重命名栈帧变量 | 该函数 |
| 修改类型信息 | 该函数 |
| patch 字节（代码段） | 该函数 |
| patch 字节（数据段） | strings.tsv |
| 删除函数 | 删除对应 .c 文件，更新索引 |

### 反编译

```bash
$ echo '!pdc _WPACKET_close' | nc localhost 13120   # 或用地址：!pdc 0x1388
; _WPACKET_close @ 0x1388
void __fastcall WPACKET_close(int64x2_t *a1)
{
  _QWORD *v1; // x1

  v1 = (_QWORD *)a1[2].i64[1];
  if ( v1 )
  {
    if ( *v1 )
      wpacket_intern_close(a1, v1, 1);
  }
}
\```

### 反汇编

```bash
$ echo '!pdf _WPACKET_close' | nc localhost 13120
; block 0  [0x1388 - 0x1390]
0x1388  LDR             X1, [X0,#0x28]; void *
0x138c  CBZ             X1, loc_13A0    ; true→ 0x13a0  false→ 0x1390
; block 1  [0x1390 - 0x1398]
0x1390  LDR             X8, [X1]
0x1394  CBZ             X8, loc_13A0    ; true→ 0x13a0  false→ 0x1398
; block 2  [0x1398 - 0x13a0]
0x1398  MOV             W2, #1
0x139c  B               _wpacket_intern_close    ; → 0x15b8
; block 3  [0x13a0 - 0x13a8]
0x13a0  MOV             W0, #0
0x13a4  RET
\```

### 交叉引用

```bash
$ echo '!axt _WPACKET_close' | nc localhost 13120
0x4030    CALL_NEAR  [in: _DTLSv1_listen]
0x403c    CALL_NEAR  [in: _DTLSv1_listen]
0x599f0   CALL_NEAR  [in: _tls_post_encryption_processing_default]
0x5c258   CALL_NEAR  [in: _tls_construct_extensions]
...（共 49 处调用）

$ echo '!axf _WPACKET_close' | nc localhost 13120
0x138c    ORDINARY_FLOW  [func: _WPACKET_close]
\```

## Command 支持

```python
$ echo '!?' | nc localhost 13120
!iz  [pat]               list strings
!afl [pat]               list functions
!afi <addr|name>         function details
!axt <addr|name>         xrefs to
!axf <addr|name>         xrefs from
!axi <name>              callers of import symbol
!pd  <addr|name> [n=16]  disassemble n instructions
!pdf <addr|name>         disassemble whole function
!pdc <addr|name> [-s]    pseudocode (-s strips var decls)
!deps <addr|name> [d=3]  recursive call chain
!cc  <addr|name> <text>  set function comment
!ca  <addr> <text>       set address comment
!afn <addr|name> <name>  rename function
!mc  <addr|name> [maturity]  microcode
!sb  <hex> [start] [end]     search byte sequence
!hd  <addr|name> [n=64]      hexdump
!pwd                         working directory
\```

`addr` 可用十六进制地址（`0x1388`）或符号名（`_WPACKET_close`）。

```bash
echo '__QUIT__' | nc localhost 13120   # 关闭 REPL
\```

## Python 脚本

REPL 支持发送任意 Python 脚本，`db`（ida-domain）已预注入，原生 `ida_*` 模块同样可用：

```bash
cat script.py | nc localhost 13120
\```

```python
# 批量找可疑大函数（高分支密度 + 未命名）
for func in db.functions.get_all():
    size = func.end_ea - func.start_ea
    name = db.functions.get_name(func)
    if size > 0x500 and name.startswith("sub_"):
        callers = list(db.functions.get_callers(func))
        print(f"{hex(func.start_ea)}  {size:#x}  callers={len(callers)}  {name}")

# 降级到原生 IDA Python
import ida_bytes
data = ida_bytes.get_bytes(0x1388, 16)
print(data.hex())
\```

脚本中的重命名、注释等修改自动触发文件系统同步。

## 交互 Shell

```bash
ida-bridge a.out --shell
rlwrap nc localhost 13121
\```

```python
> !afl jni
0x4012a0  JNI_OnLoad       0x80   callers=0
0x401320  jni_sign_data    0x1b4  callers=1
0x4014d8  jni_verify_sig   0xc8   callers=1

> !deps jni_sign_data 2
jni_sign_data  [0x401320]
  CRYPTO_sign  [0x402100]
    EVP_DigestSign  [0x403800]
    ...

> !afn 0x401320 Java_com_example_sign
renamed 0x401320: jni_sign_data → Java_com_example_sign

> exit
\```

---

# 回复

## 回复 by 墨穹呢 (#2)

*2026-5-8 23:18*

感谢分享

## 回复 by 温泉划水鱼 (#3)

*2026-5-8 23:18*

沙发

## 回复 by 夜惜风雨 (#4)

*2026-5-8 23:34*

66666666666666

## 回复 by mb_cbgtaveo (#5)

*2026-5-9 00:00*

666666

## 回复 by FMNS (#6)

*2026-5-9 09:27*

感谢分享

## 回复 by xifgg (#7)

*2026-5-9 09:59*

666

## 回复 by 4Chan (#8)

*2026-5-9 10:03*

学习一下

## 回复 by Gryffindoss (#9)

*2026-5-9 10:12*

6666

## 回复 by 梧桐生 (#10)

*2026-5-9 10:26*

学习一下

## 回复 by iBa0 (#11)

*2026-5-9 10:34*

666

## 回复 by PoorJack (#12)

*2026-5-10 15:37*

感谢分享

## 回复 by 乐活 (#13)

*2026-5-11 09:24*

11111

## 回复 by 夏洛魂 (#14)

*2026-5-11 09:37*

感谢分享

## 回复 by YiW (#15)

*2026-5-11 09:55*

666

## 回复 by mb_aopnnvxb (#16)

*2026-5-11 16:12*

mark

## 回复 by 深夜幻想家 (#17)

*2026-5-11 17:06*

mark

## 回复 by BitWarden (#18)

*2026-5-12 13:42*

支持学习

## 回复 by wx_白驹过郤 (#19)

*2026-5-13 10:10*

期待更多优质内容的分享，论坛有你更精彩

## 回复 by wx_插曲 (#20)

*2026-5-13 10:11*

6666

## 回复 by git_14248bibinocode (#21)

*2026-5-13 10:28*

66666666666

## 回复 by shuangmou (#22)

*2026-5-13 20:46*

感谢分享

## 回复 by mb_euhyowpw (#23)

*2026-5-13 20:54*

123

## 回复 by kienmanowa (#24)

*2026-5-14 11:18*

66666666666

## 回复 by mb_wyyxajmg (#25)

*2026-5-14 15:17*

666666666666666666666

## 回复 by GuililiX (#26)

*2026-5-14 16:57*

666666666666

## 回复 by 桐人dx (#27)

*2026-5-14 18:01*

6666

## 回复 by mb_pjrdprsx (#28)

*2026-5-14 18:41*

wasei

## 回复 by mb_elqwyvnm (#29)

*2026-5-14 19:20*

学习新知识

## 回复 by mb_ykavguun (#30)

*2026-5-14 19:22*

6666

## 回复 by 啥也不会2 (#31)

*2026-5-14 20:25*

66666666666

## 回复 by 学计算机睡觉 (#32)

*2026-5-15 00:45*

66666

## 回复 by 086Love (#33)

*2026-5-15 17:14*

学习

## 回复 by 孤梦拾遗 (#34)

*2026-5-16 10:40*

666

## 回复 by 彦0810 (#35)

*2026-5-17 12:03*

6666 学习学习

## 回复 by 拍拖 (#36)

*2026-5-18 14:37*

感谢分享！

## 回复 by Snowman_Liam (#37)

*2026-5-18 15:17*

6666

## 回复 by 矽阳 (#38)

*2026-5-18 19:31*

666666666666

## 回复 by 杀老师 (#39)

*2026-5-19 19:38*

6666

## 回复 by mb_jqalzdpk (#40)

*2026-5-21 02:12*

好东西看一下

## 回复 by wx_kx29662 (#41)

*2026-5-21 03:03*

66

## 回复 by belikewater (#42)

*2026-5-21 13:54*

6

## 回复 by wx_huhu_859 (#43)

*2026-5-21 14:04*

11

## 回复 by Am1re (#44)

*2026-5-21 14:57*

6666

## 回复 by 风_158566 (#45)

*2026-5-21 15:10*

感谢分享

## 回复 by visow (#46)

*2026-5-21 15:10*

mark

## 回复 by wx_蓝夜 (#47)

*2026-5-21 16:40*

666666

## 回复 by ClPrada (#48)

*2026-5-21 19:11*

66666

## 回复 by xixi樊凡 (#49)

*2026-5-29 09:27*

666666666666666

## 回复 by git_11829lalueandliuliu (#50)

*2026-5-30 22:29*

11

## 回复 by git_4711496613686 (#51)

*2026-6-1 11:13*

666666666666666666666

## 回复 by 千谦 (#52)

*2026-6-1 16:35*

前来学习

## 回复 by MaYil (#53)

*2026-6-1 19:05*

感谢分享

## 回复 by FacelessC (#54)

*2026-6-3 09:55*

6

## 回复 by wx_Oh.漏 (#55)

*2026-6-5 13:54*

11111

## 回复 by mb_cxmjsgrw (#56)

*2026-6-6 22:52*

66666

## 回复 by mb_depeeceu (#57)

*2026-6-7 00:05*

6666666666666

## 回复 by 熊猫吃鱼 (#58)

*2026-6-7 12:40*

66666

## 回复 by hungnguyen (#59)

*2026-6-7 13:18*

感谢分享

## 回复 by wx_听书人 (#60)

*2026-6-7 14:41*

666666

## 回复 by mb_vqzmyuiq (#61)

*2026-6-8 11:57*

666666666666666

## 回复 by amwait (#62)

*2026-6-9 09:37*

1111

## 回复 by mb_qupzepyf (#63)

*2026-6-9 10:28*

66666666666666666

## 回复 by huangjw (#64)

*2026-6-9 16:38*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by akarus (#65)

*2026-6-11 09:08*

真心不错啊，感谢LZ分享

## 回复 by mb_enbuhisq (#66)

*2026-6-11 10:02*

6666666

## 回复 by mb_paopxhtx (#67)

*2026-6-21 10:13*

看看怎么样

## 回复 by mb_ndzyrrkt (#68)

*2026-6-26 07:39*

66666666666666666

## 回复 by buluo533 (#69)

*2026-6-26 09:07*

666666

## 回复 by 丶咖啡猫丶 (#70)

*2026-6-26 09:10*

666

## 回复 by mb_hiqvmjsd (#71)

*2026-7-2 22:45*

66

## 回复 by wx_kx92911 (#72)

*2026-7-15 09:47*

感谢分析

## 回复 by Daoji (#73)

*2026-7-20 14:13*

66666

## 回复 by 9494 (#74)

*2026-7-20 19:08*

感谢分享

## 回复 by mb_cjvujiqx (#75)

6666

## 回复 by 祝今朝 (#76)

666
