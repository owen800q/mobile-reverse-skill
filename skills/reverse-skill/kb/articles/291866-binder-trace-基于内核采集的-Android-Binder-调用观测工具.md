---
title: binder-trace：基于内核采集的 Android Binder 调用观测工具
url: https://bbs.kanxue.com/thread-291866.htm
tid: 291866
author: fuqiuluo73
date: '2026-07-03'
tags: [Android安全, 工具脚本]
crawled_at: '2026-08-08T10:04:36+00:00'
replies: 56
---

项目地址：https://github.com/fuqiuluo/binder-trace

最近整理了一个 Android Binder 调用观测工具 `binder-trace`。它不是在 Java/Native 层做 hook，而是通过内核模块采集 Binder transaction，在用户态提供 WebUI、TUI、JSONL 和 MCP 查询接口，适合排查系统服务调用、接口频率、payload 和 reply 关联关系。

## 为什么做这个

Android 上很多跨进程行为最后都会落到 Binder。平时看 logcat、Frida hook 都能解决一部分问题，但如果想从 Binder transaction 这一层持续观察系统服务调用，常见需求会变成：

- 某个 UID / PID / TGID 在和哪些 Binder interface 交互；
- 某个服务接口是不是被异常高频调用；
- 一次 request 和 reply 如何对应；
- payload / 原始事件如何保存下来，后续再分析；
- 不想每次都写临时脚本，希望有一个可视化和终端都能用的工具。

`binder-trace` 的目标就是把这类观察流程收敛成一个工具链：内核侧负责采集，用户态负责控制、解析、存储和展示。

## 功能速览

- 实时采集 Android Binder transaction。
- WebUI：表格、搜索、方向 / 接口筛选、详情侧栏、payload / 原始 JSON、关联调用、按需分页、可调列宽。
- TUI：终端内实时事件列表、频率统计、hexdump 和解析详情。
- JSONL：输出稳定的事件消息，方便接入脚本或保存后分析。
- 支持按 `tgid`、`pid`、`uid` 缩小采集范围。
- MCP：提供 Streamable HTTP `/mcp` endpoint，方便 AI assistant 在线查询 Binder trace。

## 准备条件

需要一台已 root 的 Android 设备，并准备：

- 本机 `adb`；
- 与设备 ABI 匹配的 `binder-trace` 用户态二进制；
- 与设备内核版本匹配的 `bt-kmod.ko` 内核模块。

先确认设备信息：

```bash
adb shell getprop ro.product.cpu.abi
adb shell uname -r
adb shell su -c id
\```

把文件推到设备：

```bash
adb shell mkdir -p /data/local/tmp/binder-trace
adb push binder-trace /data/local/tmp/binder-trace/binder-trace
adb push bt-kmod.ko /data/local/tmp/binder-trace/bt-kmod.ko
adb shell chmod 755 /data/local/tmp/binder-trace/binder-trace
\```

加载内核模块并确认功能：

```bash
adb shell su -c 'insmod /data/local/tmp/binder-trace/bt-kmod.ko'
adb shell su -c 'lsmod | grep bt_kmod'
adb shell su -c '/data/local/tmp/binder-trace/binder-trace ipc feature'
\```

如果设备已经加载过旧模块，可以先卸载：

```bash
adb shell su -c 'rmmod bt_kmod'
\```

这里要注意，`rmmod` 会等待已经进入 Binder hook 的线程退出。如果设备上存在长时间阻塞的 Binder read / looper 线程，卸载可能需要等一段时间。

## WebUI 用法

日常查看推荐用 WebUI。先转发端口：

```bash
adb forward tcp:5173 tcp:5173
\```

在设备侧启动：

```bash
adb shell
su
cd /data/local/tmp/binder-trace
./binder-trace webui --listen 127.0.0.1:5173
\```

电脑浏览器打开：

\```
http://127.0.0.1:5173/
\```

常见过滤方式：

```bash
./binder-trace webui --uid 1000
./binder-trace webui --tgid 12345
./binder-trace webui --pid 12345
./binder-trace webui --no-enable
./binder-trace webui --android-sdk 35
\```

`--no-enable` 用于只读取现有事件流，不主动修改内核捕获配置。WebUI 的过滤和分页在后端执行，浏览器只渲染当前窗口，不会因为前端窗口大小丢掉后端已捕获事件。

## TUI / JSONL

如果只是临时排查，TUI 更适合直接在终端里看：

```bash
adb shell
su
cd /data/local/tmp/binder-trace
./binder-trace tui --rows 1024 --refresh-ms 100
\```

也可以按目标缩小范围：

```bash
./binder-trace tui --uid 1000
./binder-trace tui --tgid 12345
./binder-trace tui --pid 12345
./binder-trace tui --no-enable
\```

如果要接脚本或后续分析，可以输出 JSONL：

```bash
adb shell
su
cd /data/local/tmp/binder-trace
./binder-trace --output trace.jsonl
\```

事件外层是统一消息信封，`object` 表示事件类型，`data` 是对应载荷。这样后面用 `jq`、Python 或其他工具处理会比较直接。

## MCP 查询

MCP 入口适合让 AI assistant 在线查询 Binder trace。先转发端口：

```bash
adb forward tcp:5174 tcp:5174
\```

设备侧启动 MCP 服务：

```bash
adb shell
su
cd /data/local/tmp/binder-trace
./binder-trace mcp --listen 127.0.0.1:5174
\```

桌面 MCP client 连接本机转发后的地址即可，核心是 Streamable HTTP，并指向 `/mcp`：

```json
{
  "mcpServers": {
    "binder-trace": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:5174/mcp"
    }
  }
}
\```

默认 MCP 只读取实时事件流，不修改内核捕获配置。如果需要允许 AI 开关 Binder trace，需要显式加 `--allow-control`，也可以配合 `--enable --uid 1000` 这类参数启动。

---

# 回复

## 回复 by FMNS (#2)

*2026-7-3 04:26*

66666

## 回复 by tonykros (#3)

*2026-7-3 07:56*

6666

## 回复 by mb_qimctavn (#4)

*2026-7-3 08:07*

6

## 回复 by huangjw (#5)

*2026-7-3 09:35*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by mb_jnmxfjku (#6)

*2026-7-3 10:02*

666

## 回复 by Gryffindoss (#7)

*2026-7-3 10:06*

222

## 回复 by mb_iesvmzqc (#8)

*2026-7-3 10:31*

6666

## 回复 by mb_nkgphjuz (#9)

*2026-7-3 10:47*

6666

## 回复 by Thehepta (#10)

*2026-7-3 10:52*

1

## 回复 by wx_Huber Barrientos (#11)

*2026-7-3 12:08*

666

## 回复 by 夜惜风雨 (#12)

*2026-7-3 14:29*

66666666666666666666

## 回复 by Ankeys (#13)

*2026-7-3 18:55*

666

## 回复 by wx_Kerberos (#14)

*2026-7-3 19:56*

![image](https://bbs.kanxue.com/view/img/face/062.gif)

## 回复 by mb_4nrpVMxJ (#15)

*2026-7-3 20:16*

666

## 回复 by mb_liueenqt (#16)

*2026-7-3 21:10*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by jyotidwi (#17)

*2026-7-4 01:40*

666

## 回复 by guardia (#18)

*2026-7-4 04:28*

666

## 回复 by Nigthwish (#19)

*2026-7-4 05:09*

666

## 回复 by x1a0f3n9 (#20)

*2026-7-4 05:20*

感谢分享

## 回复 by 我就是小熊猫 (#21)

*2026-7-4 11:26*

666

## 回复 by shuangmou (#22)

*2026-7-5 13:58*

感谢分享

## 回复 by 独一无二_370133 (#23)

*2026-7-6 11:39*

666

## 回复 by 丶咖啡猫丶 (#24)

*2026-7-6 13:51*

666

## 回复 by ivy1 (#25)

*2026-7-6 14:28*

666

## 回复 by 随风而行aa (#26)

*2026-7-6 15:28*

看看

## 回复 by 寻梦之璐 (#27)

*2026-7-6 19:26*

6666

## 回复 by iBa0 (#28)

*2026-7-6 20:24*

123

## 回复 by 宛枫 (#29)

*2026-7-7 00:28*

感谢分享

## 回复 by git_84461osscv (#30)

*2026-7-7 00:36*

感谢分享 看看

## 回复 by wx_北极星_493 (#31)

*2026-7-7 03:12*

66

## 回复 by Imxz (#32)

*2026-7-7 16:10*

tql

## 回复 by mb_aszywhsj (#33)

*2026-7-7 16:45*

666

## 回复 by wx_三生三世 (#34)

*2026-7-7 20:43*

学习

## 回复 by huangbof (#35)

*2026-7-8 01:11*

666

## 回复 by wx_kx92911 (#36)

*2026-7-9 09:52*

感谢分析

## 回复 by 中文fjja (#37)

*2026-7-9 09:58*

谢谢分享

## 回复 by wx_插曲 (#38)

*2026-7-9 17:59*

666

## 回复 by 浅黑 (#39)

*2026-7-9 18:01*

6666666666666666666666666666

## 回复 by mb_sjowddqi (#40)

*2026-7-9 20:03*

777

## 回复 by 熊猫吃鱼 (#41)

*2026-7-9 20:42*

66666

## 回复 by dfJerry (#42)

*2026-7-10 10:03*

666666666

## 回复 by ltaiyang (#43)

*2026-7-10 10:31*

感谢分享

## 回复 by 嘉心糖 (#44)

*2026-7-13 08:23*

看看隐藏

## 回复 by mb_srxvlszh (#45)

*2026-7-14 19:57*

66

## 回复 by mb_lfwgtxdb (#46)

*2026-7-16 14:28*

感谢分享

## 回复 by 3cly (#47)

*2026-7-16 16:17*

1

## 回复 by uni7corn (#48)

*2026-7-20 16:13*

感谢分享

## 回复 by uni7corn (#49)

*2026-7-20 16:46*

感谢分享

## 回复 by mb_yvuzbfvo (#50)

*2026-7-20 18:26*

666

## 回复 by mb_ahyhoece (#51)

*2026-7-21 15:19*

12312312312

## 回复 by X14Nuy7 (#52)

*2026-7-26 10:47*

666

## 回复 by Bean3ai (#53)

*2026-7-29 19:50*

66

## 回复 by git_51354IsoumaNaN (#54)

*2026-7-30 00:25*

666

## 回复 by git_51354IsoumaNaN (#55)

*2026-7-30 00:26*

666

## 回复 by wx_Dispa1r (#56)

1

## 回复 by mb_irhdtnzm (#57)

1
