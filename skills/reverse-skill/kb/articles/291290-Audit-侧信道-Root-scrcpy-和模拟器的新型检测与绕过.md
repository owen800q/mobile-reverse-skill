---
title: '[原创] Audit 侧信道: Root, scrcpy 和模拟器的新型检测与绕过'
url: https://bbs.kanxue.com/thread-291290.htm
tid: 291290
author: vwvw
date: '2026-05-20'
tags: [Android安全, 原创, 系统相关, 漏洞相关, 源码框架]
crawled_at: '2026-08-08T10:08:22+00:00'
replies: 47
---

260522 21:17:53 更新

## 概述

[Hide procfs related audit messages from appdomain](https://android-review.googlesource.com/c/platform/system/logging/+/3725346)

这个链接是一个 AOSP 的修复变更, 旨在修复一个 Audit 日志泄露的问题

在三方 App 受限沙箱中, 即使不能直接读取其他进程的 `/proc/<pid>` 信息, 通过访问 procfs 触发 SELinux Audit 日志, 也可能可以从 logcat 里的 `tcontext` 反推出目标进程的安全域

也可以说这是一个基于 audit 日志的侧信道检测思路.

基于这个思路, 先尝试了以下三类场景:

1. root 环境: 通过 `tcontext=u:r:magisk:s0` 观察 Magisk 相关安全域
2. 模拟器环境: 通过 `qemu_props`, `goldfish`, `ranchu` 相关安全域观察模拟器特征
3. 疑似正在投屏: 通过高 PID 的连续 `u:r:shell:s0` 安全域发现疑似 scrcpy 正在投屏

依旧是使用 [Mira](https://github.com/vwww-droid/Mira) 开源框架进行运行时风险分析. 介绍在 <https://bbs.kanxue.com/thread-291041.htm> 这篇文章

相对于不断打包安装和触发, Mira 只需 AI 自行对 shell 脚本不断进行微调和执行即可. 比如这次的改 PID 范围, 改 logcat 匹配规则, 改扫描窗口, 很快, 很省精力.

**文末为原理, 修复, 以及绕过方案.**

## 复现

### 狐妖 Magisk

让 AI 调用 Mira 的 MCP 功能, AI 这里使用分块扫描, 从 `900` 开始按窗口触碰 `/proc/<pid>`, 每个窗口 25 个 PID, 发现命中后停止.

 ![image](https://bbs.kanxue.com/upload/attach/202605/1054778_AJR99JGGNHK4NQR.webp)

可以直接看到, App 沙箱侧触碰 procfs 后, audit 日志暴露了 `tcontext=u:r:magisk:s0`.

```sh
[Magisk audit side-channel scan]
scan pid=900-924
scan pid=925-949
scan pid=950-974
scan pid=975-999
scan pid=1000-1024
scan pid=1025-1049
hit_window=1025-1049
05-20 21:48:56.216 ... avc: denied { getattr } for comm="sh" path="/proc/1028" dev="proc" ... scontext=u:r:untrusted_app_27:s0:... tcontext=u:r:magisk:s0 tclass=dir permissive=0 app=com.vwww.mira
05-20 21:48:56.216 ... avc: denied { getattr } for comm="sh" path="/proc/1029" dev="proc" ... scontext=u:r:untrusted_app_27:s0:... tcontext=u:r:magisk:s0 tclass=dir permissive=0 app=com.vwww.mira
05-20 21:48:56.219 ... avc: denied { getattr } for comm="sh" path="/proc/1048" dev="proc" ... scontext=u:r:untrusted_app_27:s0:... tcontext=u:r:magisk:s0 tclass=dir permissive=0 app=com.vwww.mira
\```

### AVD

AVD 即 Android Studio 自带模拟器, 这里使用 M 芯片 Mac android studio 的 Android 13 镜像作为演示样本

Magisk检测 中使用 AI 调用 MCP 用于展示 AI 快速微调的效率, 实际弄懂原理之后, 手动使用该受控三方权限 shell 会更快

先 adb 查看有什么进程, 进程名是什么

```sh
❯ adb shell
emu64a:/ $ ps -e | grep qemu
root           158     1 10780188  2184 0                   0 S qemu-props
emu64a:/ $
\```

试探一下, 发现了 `qemu_props` 特征

 ![image](https://bbs.kanxue.com/upload/attach/202605/1054778_38NUGHSRENAETB9.webp)

同样, 再找点其他模拟器特征, 比如

```bash
❯ adb shell
emu64a:/ $ ps -e | grep qemu
root           158     1 10780188  2184 0                   0 S qemu-props
emu64a:/ $ ps -e | grep goldfish
root           152     2       0      0 0                   0 S [irq/46-goldfish]
media          317     1 11086960  4008 0                   0 S android.hardware.media.c2@1.0-service-goldfish
radio          370     1 11113696  3372 0                   0 S libgoldfish-rild
emu64a:/ $ ps -e | grep anchu
gps            777     1 10949284  2056 0                   0 S android.hardware.gnss@2.0-service.ranchu
emu64a:/ $
\```

这些就不如 qemu 的特征明显, 但也可以被触发

 ![image](https://bbs.kanxue.com/upload/attach/202605/1054778_CGDTYANBVJRSDB6.webp)

### scrcpy 投屏

从 android 9 往后, 对 scrcpy 的检测就一直没有什么好方案, 因为特征隐藏的足够好, 而 audit 可以提供一种新的思路

分析 scrcpy 的源码, 发现新版本的 scrcpy 基于 adb shell 拉起 `app_process`, 启动 scrcpy 自己的 jar 包运行, 运行起来会删除 `/data/local/tmp/scrcpy-server.jar` 文件, 没有文件特征

参考 avd 的研究方法, 先 adb shell 查看, 可以看到投屏服务对应 `sh -> app_process -> app_process` 三个 pid 很相近的进程

```sh
emu64a:/ $ ps -e | grep shell
shell          351     1 11105424  7368 0                   0 S adbd
shell          508   351 10789444  2236 __arm64_sys_nanosleep 0 S process-tracker
shell         5615   351 10815908  3168 __do_sys_rt_sigsuspend 0 S sh
shell         6212   351 10858824  3256 unix_stream_data_wait 0 S abb

shell        27769   351 10797476  2632 __do_sys_rt_sigsuspend 0 S sh
shell        27771 27769 14129832 135132 do_epoll_wait      0 S app_process
shell        27800 27771 13609408 102484 pipe_read          0 S app_process
\```

audit 日志不能直接读出 `app_process`, 但能看到高 PID 中有三个离得很近的 `u:r:shell:s0` 特征:

 ![image](https://bbs.kanxue.com/upload/attach/202605/1054778_6NVXV8Q29U7NHDW.webp)

启停对比也符合预期: 关闭投屏后, 相同高 PID 范围扫描结果为:

```log
START=10000 END=18000 CHUNK=100 STEP=100
no_shell_domain_hit
\```

正常用户即使开启 adb, 不用 scrcpy 投屏也不会有这个特征, **因此连续 3 个 `u:r:shell:s0`** 可以作为判断正疑似使用 scrcpy 投屏的策略, 具体需要线上环境验证, 这里只是提供一个思路

若想隐藏, 要么使用修复后系统, 要么就是得 root 设备然后 hook 系统框架将这部改掉, 但就会引入新的特征进入 root 对抗的范畴. 提高攻击方的成本.

## 注意事项

### 扫描稳定性

该侧信道不适合无脑大范围扫描, **实验中出现过单点命中, 大窗口扫描反而漏检的情况**

原因主要有两个:

1. SELinux audit 日志存在限流
2. 大窗口会制造大量无关 denial, 目标 PID 落在窗口后段时可能被噪声淹没

推荐使用小窗口或重叠窗口:

```sh
START=1000
END=2500
CHUNK=10
STEP=10
WAIT_SEC=1
LOG_TAIL=400
MATCH='tcontext=u:r:qemu_props:s0|tcontext=u:r:[^ ]*(goldfish|ranchu|qemu)[^ ]*:s0'
\```

如果 `CHUNK=50` 漏检, 优先降低到 `CHUNK=10`, 或使用 `CHUNK=50 STEP=25`。不要只增加 `sleep`, 因为失败原因通常不是日志延迟, 而是 audit 限流和窗口噪声。

### 执行语法细节

当前 shell 触碰 `/proc/<pid>` 和 `sh script.sh` 新开子 shell 触碰, 不等价.

推荐方式:

1. 当前 shell 触碰
2. 或写入文件, 用 `. script.sh` 在当前 shell 加载执行

## AOSP 原代码泄露路径分析

问题核心在 `system/logging/logd/LogAudit.cpp` 的 `LogAudit::logPrint`

logd 收到 audit 消息后, 先格式化成字符串:

```cpp
char* str = nullptr;
va_start(args, fmt);
int rc = vasprintf(&str, fmt, args);
va_end(args);
\```

此时 `str` 中已经包含原始 audit 信息, 例如 `dev="proc"`, `scontext`, `tcontext`, `tclass`, `comm`, `path` 等字段。对本文场景来说, 关键是 `dev="proc"` 和 `tcontext` 同时存在

随后代码从 audit 字符串中查找 `pid=` 字段, 并用 `pidToUid` 找到触发 audit 的 UID:

```cpp
static const char pid_str[] = " pid=";
char* pidptr = strstr(str, pid_str);
...
uid = android::pidToUid(pid);
\```

这个 UID 后续会传给日志系统. 对于 App 触发的 procfs audit, 这里解析出的 UID 会落在 `AID_APP_START` 之后.

原代码会调用 `auditParse(str, uid)`:

```cpp
denial_metadata = auditParse(str, uid);
\```

`auditParse` 会解析 `scontext`, `tcontext`, `tclass`, 并尝试匹配 bug metadata. 更重要的是, 当 UID 属于 App 范围时, 它还会追加 App 包名:

```cpp
if (uid >= AID_APP_START && uid <= AID_APP_END) {
    char* uidname = android::uidToName(uid);
    if (uidname) {
        result.append(" app="s + uidname);
        free(uidname);
    }
}
\```

这说明 logd 不只是原样转发 audit 字符串, 还会把它加工成更适合定位问题的日志. 对系统调试来说这是正向能力, 但对 App 可见日志来说, 它强化了侧信道可读性.

原代码随后把 audit 字符串和追加元数据写入 events buffer:

```cpp
rc = logbuf->Log(LOG_ID_EVENTS, now, uid, pid, tid,
                 reinterpret_cast<char*>(event),
                 (message_len <= UINT16_MAX) ? (uint16_t)message_len : UINT16_MAX);
\```

这里使用的 `uid`, `pid`, `tid` 来自前面的解析结果. 也就是说, 这条 audit 日志会以触发方相关身份进入日志系统.

后续代码还会构造 main buffer 日志. 它会从 audit 字符串中解析 `comm="..."`, 构造新的日志内容, 再把 denial metadata 拼进去.

结果是, 同一条 procfs denial 可能进入 main buffer 和 events buffer. 只要 App 侧能够读取到对应日志面, `tcontext` 就会暴露.

根因可以概括为一句话:

`hidepid=2` 保护的是 procfs 正常读取面, 但原 logd 路径把 procfs 访问失败后的 audit 诊断信息转发到了 App 可见日志面.

因此 App 不需要直接读取 `/proc/<pid>`. 它只需要触碰 `/proc/<pid>` 触发 `getattr` denial, 再从 logcat 中读取 `tcontext`, 就能推断目标进程属于哪个 SELinux 安全域.

Android 上 audit 消息会通过 netlink socket 转发给 logd, logd 又可能把这些消息转发到 App 自身可见的日志面. 这样就形成了下面的信息流:

\```
App 触碰 /proc/<pid>
  -> SELinux 拒绝访问
  -> kernel 产生 audit 记录
  -> audit 记录通过 netlink 到 logd
  -> logd 写入 main 或 events 日志缓冲
  -> App 侧通过 logcat 看到 tcontext
\```

这条链路绕过的不是 SELinux 权限检查本身, 而是利用权限检查失败后的诊断信息.

## AOSP 补丁作者的修复思路

3725346 补丁新增的逻辑如下:

```cpp
// Hide procfs related audit messages from appdomain to prevent selinux context leak
if (uid >= AID_APP_START && strstr(str, "dev=\"proc\"")) {
    free(str);
    return 0;
}
\```

这段过滤有两个条件。

第一, `uid >= AID_APP_START`. 说明过滤对象是 App UID 触发的 audit, 而不是所有系统 audit. 这样可以避免影响系统服务和原生系统进程的正常诊断.

第二, `strstr(str, "dev=\"proc\"")`. 说明过滤对象是 procfs 相关 audit. 补丁没有泛化过滤所有 SELinux denial, 而是精准阻断这条通过 `/proc/<pid>` 泄露其他进程安全域的路径.

1. 不改变 SELinux 判定.
2. 不改变 procfs 权限模型.
3. 不完全丢弃系统调试信息.
4. 阻断 App 触发的 procfs audit 进入 main 和 events 日志缓冲.

修的是 logd 的转发边界. 访问失败可以继续失败, 系统也可以继续审计, 但 App 无法通过日志缓冲看到其他进程的 `tcontext`.

## SELinux audit 结构

一条典型的 SELinux 拒绝记录如下:

\```
avc: denied { getattr } for comm="sh" path="/proc/1030" dev="proc" ... scontext=u:r:untrusted_app:s0 ... tcontext=u:r:magisk:s0 tclass=dir permissive=0
\```

关键字段如下:

| 字段 | 含义 | 本文关注点 |
|-|-|-|
| `avc: denied` | SELinux 拒绝访问 | 表示进入拒绝路径 |
| `{ getattr }` | 访问动作 | 目录元数据探测即可触发 |
| `path` | 被访问路径 | 指向 `/proc/<pid>` |
| `dev="proc"` | 文件系统来源 | 标识 procfs 相关 audit |
| `scontext` | 发起方安全域 | 通常是 App 沙箱域 |
| `tcontext` | 目标方安全域 | 侧信道泄露的核心字段 |
| `tclass` | 目标对象类型 | 例如 `dir` |

AOSP SELinux 文档说明, SELinux denial 会进入 `dmesg` 和 `logcat`, 并且 `scontext`, `tcontext`, `tclass` 分别描述发起方, 目标方和目标对象类型. 也就是说, audit 日志的设计目标是帮助系统开发者定位策略问题, 但在特定日志可见性条件下, 它也可能成为信息侧信道.

## 绕过

260522 21:17:53 更新

https://github.com/aviraxp/ZN-AuditPatch/blob/master/module/src/main/cpp/hook.cpp#L36

```c
constexpr std::string_view target_context = "tcontext=u:r:priv_app:s0:c512,c768";
constexpr std::string_view source_contexts[] = {
        "tcontext=u:r:su:s0",
        "tcontext=u:r:magisk:s0"
};
\```

仅对 `magisk` 和 `su` 的情况做了过滤, 并替换为固定的字符串 `"tcontext=u:r:priv_app:s0:c512,c768"`

刚开始觉得这种写法有问题, 并提出了如下修改:

1. 只匹配 `"tcontext=u:r:magisk:s0"` 和 `"tcontext=u:r:su:s0"` , 无法解决所有类似的情况, 比如对本文提到的模拟器和投屏的特征无法适配, 不如 `path="/proc/..."` 都替换为 `priv_app`
2. 硬编码 `"tcontext=u:r:priv_app:s0:c512,c768"` 也是新的特征, 改成随机值算了, 比如 `u:r:priv_app:s0:c115,c371,c512,c768`

最后经过指正发现是我不够严谨, 随便下了结论, 如下是作者回复:

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/1054778_P2HCGAB6X5HEP23.webp)

哈哈哈, 赶紧修改, 并趁机学习新知识

`c512,c768` 不是随便写死的字符串, 它来自 Android libselinux 里的 MLS/MCS 计算逻辑, 参考 <https://android.googlesource.com/platform/external/selinux/+/main/libselinux/src/android/android_seapp.c#691>

```c
/* Sets the categories of ctx based on the level request */
int set_range_from_level(context_t ctx, enum levelFrom levelFrom, uid_t userid, uid_t appid)
{
    char level[255];
    switch (levelFrom) {
    case LEVELFROM_NONE:
        strncpy(level, "s0", sizeof level);
        break;
    case LEVELFROM_APP:
        snprintf(level, sizeof level, "s0:c%u,c%u",
             appid & 0xff,
             256 + (appid>>8 & 0xff));
        break;
    case LEVELFROM_USER:
        snprintf(level, sizeof level, "s0:c%u,c%u",
             512 + (userid & 0xff),
             768 + (userid>>8 & 0xff));
        break;
    case LEVELFROM_ALL:
        snprintf(level, sizeof level, "s0:c%u,c%u,c%u,c%u",
             appid & 0xff,
             256 + (appid>>8 & 0xff),
             512 + (userid & 0xff),
             768 + (userid>>8 & 0xff));
        break;
    default:
        return -1;
    }
    if (context_range_set(ctx, level)) {
        return -2;
    }
    return 0;
}
\```

其中 `LEVELFROM_USER` 分支写的是 `s0:c%u,c%u`, 分别按 `512 + (userid & 0xff)` 和 `768 + (userid >> 8 & 0xff)` 计算

`userid` 和 `appid` 的拆分在同文件 `seapp_context_lookup_internal()` 中, 代码是

```c
userid = uid / AID_USER_OFFSET;
appid = uid % AID_USER_OFFSET;
\```

所以主用户 `userId` 为 0 时, `LEVELFROM_USER` 会算出 `512 + 0 = c512` 和 `768 + 0 = c768`, 最终得到 `s0:c512,c768`

而 priv_app 为什么会走这个分支, 可以看 AOSP 的 [system/sepolicy/private/seapp_contexts](https://android.googlesource.com/platform/system/sepolicy/+/refs/heads/android16-release/private/seapp_contexts#201), 其中常见规则是 `user=_app isPrivApp=true domain=priv_app type=privapp_data_file levelFrom=user`, 也就是 priv_app 默认按 Android userId 生成类别, 而不是按具体 App 生成类别

当然, 如果是系统分身环境 uid 非 0 的情况, userid 就不是 `c512` 了, 不过这都是极端情况.

我原来的写法驴唇不对马嘴, priv_app 但是用了 untrusted_app 的特征

magisk 这种低 pid 的进程, 应该是 priv_app 更正常, 对 scrcpy 这种 shell 的, 倒是 untrusted_app 更正常一些, 毕竟 pid 靠后.

再次感谢 [@mb_bvvcoitr](https://bbs.kanxue.com/homepage-1006272.htm) 大佬指正!

## 沉淀记录

基于以下 Mira case 沉淀:

1. [Android proc audit 侧信道检测 Magisk SELinux 上下文](https://github.com/vwww-droid/Mira/blob/main/knowledge/cases/zh/2026/2026-05-19-android-proc-audit-magisk-sidechannel.md)
2. [Android 模拟器 proc audit 侧信道暴露 qemu SELinux 上下文](https://github.com/vwww-droid/Mira/blob/main/knowledge/cases/zh/2026/2026-05-20-android-emulator-proc-audit-sidechannel.md)
3. [Android 高 PID shell proc audit 侧信道提示 scrcpy 投屏](https://github.com/vwww-droid/Mira/blob/main/knowledge/cases/zh/2026/2026-05-20-android-high-pid-shell-audit-sidechannel-scrcpy.md)

## 参考链接

1. AOSP Gerrit: [Hide procfs related audit messages from appdomain](https://android-review.googlesource.com/c/platform/system/logging/+/3725346)
2. AOSP Docs: [Validate SELinux](https://source.android.com/docs/security/features/selinux/validate)
3. AOSP Docs: [Understand logging](https://source.android.com/docs/core/tests/debug/understanding-logging)

---

# 回复

## 回复 by vwvw (#2)

*2026-5-21 01:37*

检测方案: <https://github.com/vwww-droid/Mira/tree/main/knowledge/cases/zh/2026>

测试框架: <https://github.com/vwww-droid/Mira>

绕过模块: <https://github.com/aviraxp/ZN-AuditPatch>

## 回复 by dreameriii (#3)

*2026-5-21 09:51*

谢谢分享 ～![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by Imxz (#4)

*2026-5-21 10:54*

tql

## 回复 by apxar (#5)

*2026-5-21 11:56*

1

## 回复 by XCicada (#6)

*2026-5-21 12:14*

tql

## 回复 by mb_xjdhrmck (#7)

*2026-5-21 12:24*

666

## 回复 by 木木W (#8)

*2026-5-21 13:35*

666

## 回复 by mb_ldbucrik (#9)

*2026-5-21 14:00*

感谢分享

## 回复 by wx_范迪塞尔 (#10)

*2026-5-21 14:10*

6666

## 回复 by k4y0z (#11)

*2026-5-21 14:48*

666

## 回复 by liowmark (#12)

*2026-5-21 15:09*

学习学习

## 回复 by 温泉划水鱼 (#13)

*2026-5-22 13:24*

看看

## 回复 by mb_bvvcoitr (#14)

*2026-5-22 19:19*

我选择priv_app是有原因的，你的写法才会触发检测，比如path匹配proc的话，app可以自行找一个带proc的路径（比如/data/data/xxx/proc/（触发denial，结果发现日志里被改了

## 回复 by mb_bvvcoitr (#15)

*2026-5-22 19:20*

此外priv_app的后缀（mls特征）是固定的，随机化反而说明有问题

## 回复 by vwvw (#16)

*2026-5-22 19:42*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_bvvcoitr](https://bbs.kanxue.com/user-1006272.htm)
>  我选择priv_app是有原因的，你的写法才会触发检测，比如path匹配proc的话，app可以自行找一个带proc的路径（比如/data/data/xxx/proc/（触发denial，结果发现日志 ...
>

学到了大佬, 我明天研究下改下帖子, 感谢指导![image](https://bbs.kanxue.com/view/img/face/086.gif)

## 回复 by vwvw (#17)

*2026-5-22 21:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_bvvcoitr](https://bbs.kanxue.com/user-1006272.htm)
>  此外priv_app的后缀（mls特征）是固定的，随机化反而说明有问题
>

已修改, 再次感谢

## 回复 by 寻梦之璐 (#18)

*2026-5-22 23:19*

666

## 回复 by huangjw (#19)

*2026-5-23 11:02*

![image](https://bbs.kanxue.com/view/img/face/039.gif)

## 回复 by FMNS (#20)

*2026-5-23 11:56*

233

## 回复 by mb_qimctavn (#21)

*2026-5-23 12:05*

6

## 回复 by lixianhuei (#22)

*2026-5-23 20:44*

666

## 回复 by YoungBai (#23)

*2026-5-25 09:32*

666

## 回复 by hyz111 (#24)

*2026-5-25 09:48*

tql

## 回复 by fudugeek (#25)

*2026-5-26 15:40*

tql

## 回复 by wx_666_974 (#26)

*2026-5-27 09:01*

学习

## 回复 by 大魔头 (#27)

*2026-5-27 11:15*

666

## 回复 by uni7corn (#28)

*2026-5-27 16:14*

感谢分享

## 回复 by 不具名的悲伤 (#29)

*2026-5-27 16:37*

6

## 回复 by 有的是钱啊 (#30)

*2026-5-27 16:47*

1111

## 回复 by 学计算机睡觉 (#31)

*2026-5-27 17:02*

tql

## 回复 by 好听的网名 (#32)

*2026-6-2 10:28*

学习学习~

## 回复 by Thehepta (#33)

*2026-6-2 10:35*

1

## 回复 by ycdear (#34)

*2026-6-2 11:29*

111

## 回复 by veluboii (#35)

*2026-6-3 18:36*

666

## 回复 by mb_jnmxfjku (#36)

*2026-6-3 19:34*

666

## 回复 by mb_bnktnjyk (#37)

*2026-6-4 10:02*

看过

## 回复 by mb_dovsgrdo (#38)

*2026-6-5 21:18*

1

## 回复 by FloatGuy (#39)

*2026-6-5 22:56*

666

## 回复 by mb_jzyasacd (#40)

*2026-6-6 17:52*

1

## 回复 by mb_czqyztmr (#41)

*2026-6-8 16:06*

66666

## 回复 by mb_cpwlanod (#42)

*2026-6-9 10:27*

6

## 回复 by mb_qqihqaoo (#43)

*2026-6-11 12:48*

6666

## 回复 by 哈哥 (#44)

*2026-6-15 16:06*

1

## 回复 by qianfeng_mi (#45)

*2026-6-16 15:03*

学习学习

## 回复 by iBa0 (#46)

*2026-7-7 20:56*

1

## 回复 by wx_kx92911 (#47)

*2026-7-9 10:05*

感谢分析

## 回复 by 3cly (#48)

*2026-7-16 16:24*

1
