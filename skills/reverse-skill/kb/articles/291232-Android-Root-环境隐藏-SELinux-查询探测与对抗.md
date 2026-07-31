---
title: '[原创] Android Root 环境隐藏：SELinux 查询探测与对抗'
url: https://bbs.kanxue.com/thread-291232.htm
tid: 291232
author: 用户名null
date: '2026-05-15'
tags: [Android安全, 原创, HOOK注入, 源码框架, 工具脚本]
crawled_at: '2026-07-31T15:06:36+08:00'
replies: 117
---

# Android Root 检测之 SELinux 查询探测的对抗

LSPosed 团队公布的一个新的 root 检测方案，把查询SELinux policy这种检测方式进行了开源。

如果系统里加载过额外 sepolicy，可能会多出一些 domain、type 或 allow 规则。普通应用虽然不能直接读很多 root 相关文件，但它可以通过系统接口查询某些 SELinux 结果。只要返回值和正常环境不一样，就能变成检测点。

DirtySepolicy 的实现可以简单理解为：用 `isolatedProcess` 配合 `useAppZygote` 触发应用私有 Zygote，再通过 `zygotePreloadName` 把检测代码放到 `app_zygote` 上下文里执行。只要这个载体能调用 `SELinux.checkSELinuxAccess()` 向内核查询当前策略，额外 sepolicy 规则就会变成普通应用能读到的信号。

## 1. DirtySepolicy介绍

DirtySepolicy 通过 AppZygote 这条链路检测。

配置上大概是这样：

```xml
<application
    android:zygotePreloadName="org.lsposed.dirtysepolicy.AppZygote">
    <service
        android:name=".DirtySepolicyService"
        android:isolatedProcess="true"
        android:useAppZygote="true" />
</application>
```

`isolatedProcess` 配合 `useAppZygote` 会触发应用私有 Zygote，`zygotePreloadName` 指向的类会在 preload 阶段执行。DirtySepolicy 在正式查询前还会做一些自检，比如确认 UID 没被换掉、当前 context 是 `app_zygote`，并比对 `getContext()`、`getPidContext()` 和 `/proc/self` 文件上下文。

自检通过以后，检测点主要落在两个地方。

### 1.1 SELinux.checkSELinuxAccess

Java 层可以通过类似下面的接口查询 SELinux 访问结果：

```java
SELinux.checkSELinuxAccess(source, target, clazz, perm)
```

DirtySepolicy 里查询面比较宽，类似这些：

```
u:r:system_server:s0 -> u:r:system_server:s0 process execmem
u:r:fsck_untrusted:s0 -> u:r:fsck_untrusted:s0 capability sys_admin
u:r:shell:s0 -> u:r:su:s0 process transition
u:r:adbd:s0 -> u:r:adbroot:s0 binder call
u:r:untrusted_app:s0 -> u:r:magisk:s0 binder call
u:r:untrusted_app:s0 -> u:object_r:ksu_file:s0 file read
u:r:untrusted_app:s0 -> u:object_r:lsposed_file:s0 file read
u:r:untrusted_app:s0 -> u:object_r:xposed_data:s0 file read
u:r:zygote:s0 -> u:object_r:adb_data_file:s0 dir search
```

如果这些查询返回 true，应用就能判断 live sepolicy 里可能存在额外规则。

底层会走到 SELinux 的 context 转换和 AV 计算：

```
context string -> sid
sid + class + perm -> av_decision
```

对应到内核函数，大概就是：

```
security_context_to_sid
security_context_str_to_sid
security_compute_av_user
```

### 1.2 /proc/self/attr/current

另一种方式是写：

```
/proc/self/attr/current
```

写入一个目标 context 后，内核会走 SELinux procattr 和 transition 检查。如果返回值不是预期的 `EINVAL`，也可能被拿来做判断。

对应路径大概是：

```
selinux_setprocattr
security_bounded_transition
security_validate_transition
```

## 2. selinux-query-guard

检测出来了，那就产生了对抗，最近写了对抗的KPM 模块： [selinux-query-guard](https://github.com/OoOIOoOIOoO/selinux-query-guard)，用来处理这类 SELinux 查询探测。

做法是在内核 SELinux 相关函数上挂 hook，应用 UID 走到查询入口时，对一些敏感结果做过滤。实现还比较粗，更多是一次针对 DirtySepolicy 思路的 KPM 侧尝试。

`selinux-query-guard` 加载后会直接安装 hook。
入口：

```c
KPM_INIT(selinux_query_guard_init);
KPM_CTL0(selinux_query_guard_control0);
KPM_EXIT(selinux_query_guard_exit);
```

初始化时调用：

```c
return install_hooks();
```

`install_hooks()` 里通过 `kallsyms_lookup_name()` 找符号，再用 KernelPatch 的 `hook_wrap()` 挂回调。

## 3. hook的函数说明

按用途分几类。

### 3.1 context 转 SID

```
security_context_to_sid
security_context_str_to_sid
security_context_to_sid_force
security_secctx_to_secid
security_secid_to_secctx
```

这里主要用来观察应用在查什么 context。

如果普通 app 或 isolated app 解析了下面这类 context，就先把这个来源记下来：

```
u:r:magisk:s0
u:r:ksu:s0
u:object_r:ksu_file:s0
u:object_r:lsposed_file:s0
u:object_r:xposed_data:s0
```

### 3.2 AV 查询

```
security_compute_av_user
security_compute_av
```

`SELinux.checkSELinuxAccess()` 最后关心的是 `av_decision.allowed`。

命中敏感来源后，模块会把：

```c
avd->allowed
```

改成：

```c
0
```

这样应用看到的就是 deny。

这里没有把所有查询都改掉。代码里保留了一个基础查询能力：

```c
if (avd->allowed == SELINUX_ACCESS_QUERY_ALLOWED) {
    p->reason = "preserve-selinux-access-query-capability";
    return;
}
```

如果把 SELinux 查询能力本身破坏掉，检测样本可能直接报环境异常，所以这块不能粗暴处理。

### 3.3 procattr

```
security_setprocattr
selinux_setprocattr
```

这里处理 `/proc/self/attr/current`。

before hook 里记录写入的 name 和 value。
如果是 `current`，并且 value 是敏感 context，after hook 里再判断是否需要改返回值。

命中后返回：

```c
-EINVAL
```

### 3.4 transition

```
security_bounded_transition
security_validate_transition
security_validate_transition_user
```

写 attr current 后，有些内核会继续走 transition 检查。这里也做了返回值过滤，避免从另一条路径露出差异。

## 4. 如何过滤敏感查询

模块里放了一个列表：

```c
static const char *interesting_contexts[] = {
    "u:r:app_zygote:s0",
    "u:r:isolated_app:s0",
    "u:r:ksu:s0",
    "u:r:ksu_file:s0",
    "u:r:magisk:s0",
    "u:r:magisk_file:s0",
    "u:r:lsposed_file:s0",
    "u:r:xposed_data:s0",
    "u:r:system_server:s0",
    "u:r:fsck_untrusted:s0",
    "u:r:shell:s0",
    "u:r:su:s0",
    "u:r:adbd:s0",
    "u:r:adbroot:s0",
    "u:r:untrusted_app:s0",
    "u:r:zygote:s0",
    "u:object_r:ksu_file:s0",
    "u:object_r:lsposed_file:s0",
    "u:object_r:xposed_data:s0",
    "u:object_r:adb_data_file:s0",
};
```

另外还做了前缀判断：

```
u:r:ksu*
u:r:magisk*
u:r:lsposed*
u:r:xposed*
u:object_r:ksu*
u:object_r:magisk*
u:object_r:lsposed*
u:object_r:xposed*
```

这块现在写得比较直接。好处是简单，坏处是后续要维护。后面可以考虑把模块加载时机再提前，在 SELinux 初始化完成但脏规则加载之前，先抓一份干净 policy，后续把这份干净策略当白名单来判断查询结果。

## 5. 怎么区分是否需要hook

不能只看context进行区分。因为系统进程、shell、root 管理器自己也可能查这些东西。直接拦会误伤。

所以模块会记录当前 task 的信息：

```c
struct source_info
{
    pid_t pid;
    pid_t tgid;
    uid_t uid;
    uid_t euid;
    uid_t fsuid;
    const char *comm;
    const char *source_class;
    bool is_app_uid;
    bool is_isolated_uid;
    bool is_privileged_uid;
    bool is_root_manager_comm;
    bool is_sniffer;
};
```

分类时先放行 root manager 和 system 这类来源：

```c
if (src->is_root_manager_comm) return "root-manager";
if (src->is_privileged_uid) return "privileged/system";
```

然后再判断是否是已经记录过的探测来源：

```c
if (source_matches_learned_probe(src)) {
    src->is_sniffer = true;
    return "sensitive-selinux-prober";
}
```

如果普通 app 或 isolated uid 命中了敏感 context，就记录 UID 和 TGID：

```c
if (sensitive_probe && (src->is_app_uid || src->is_isolated_uid)) {
    if (src->is_isolated_uid) learned_probe_isolated_uid = src->uid;
    if (src->is_app_uid) learned_probe_uid = src->uid;
    learned_probe_tgid = src->tgid;
    src->is_sniffer = true;
    return "sensitive-selinux-prober";
}
```

这样做是为了兼容 AppZygote 和 isolatedProcess。检测逻辑可能不在主进程里跑，前一次 context 解析和后一次 AV 查询也不一定完全在同一个进程状态里。

## 6. 实际修改位置

实际修改只有两处。

第一处是返回值：

```c
p->proposed_ret = -ERRNO_EINVAL;
args->ret = (uint64_t)(int64_t)p->proposed_ret;
```

用于 procattr 和 transition。

第二处是 AV decision：

```c
p->proposed_allowed = 0;
avd->allowed = p->proposed_allowed;
```

用于 `security_compute_av_user`。

这两个修改都要先判断来源。不是 app UID，或者没有命中过敏感 context，不会触发改动。

## 7. 内核版本处理

不同内核版本里，SELinux 函数参数位置不一样。这里用了一个简单判断：

```c
static bool need_selinux_compat_signature(void)
{
    return kver >= VERSION(4, 17, 0) && kver < VERSION(6, 4, 0);
}
```

如果命中这个区间，就走 `*_compat` 回调。主要是取参数的位置不同：

```
context 可能是 arg0，也可能是 arg1
avd 可能是 arg3，也可能是 arg4
oldsid/newsid 的位置也可能不同
```

## 8. 编译

目录：

```
KernelPatch/kpms/selinux-query-guard
```

编译：

```sh
make
```

产物：

```
selinux_query_guard.kpm
```

如果工具链路径不同，可以自己传：

```sh
make KP_DIR=/path/to/KernelPatch TARGET_COMPILE=/path/to/aarch64-none-elf-
```

## 9. 不足

这个版本能用，但是没有完全自适应root的selinux policy

目前的问题：

```
敏感 context 是硬编码
UID/TGID 没有过期机制
isolated UID 有复用风险
没有读取 current task 的 SELinux context
AV 查询里没有还原完整 source/target/class/perm
不同设备上符号可能不全
```

如果继续做，比较值得改的是白名单来源。现在是看到敏感 context 就学习来源，后面可以在 SELinux 初始化前后找一个更早的时机，保存一份干净 policy。应用查询时，优先用这份干净策略判断：干净策略里没有的 context 或 allow，就按普通失败处理。再加上 UID/TGID 过期机制，误伤会少一些。

特别感谢 LSPosed 和 DirtySepolicy 项目的开源分享

---

# 回复

## 回复 by helloWld (#2)

*2026-5-15 23:33*

酷酷

## 回复 by 随风而行aa (#3)

*2026-5-15 23:50*

看看

## 回复 by 086Love (#4)

*2026-5-16 09:33*

学习

## 回复 by huangjw (#5)

*2026-5-16 10:08*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by 温泉划水鱼 (#6)

*2026-5-16 11:02*

学习

## 回复 by 墨穹呢 (#7)

*2026-5-16 12:03*

感谢分享

## 回复 by mb_ltyedidm (#8)

*2026-5-16 14:18*

1

## 回复 by mb_ldbucrik (#9)

*2026-5-16 14:36*

感谢分享

## 回复 by mb_elqwyvnm (#10)

*2026-5-16 17:33*

感谢分享

## 回复 by mb_euhyowpw (#11)

*2026-5-16 18:45*

12 3;

## 回复 by supercuglong (#12)

*2026-5-17 00:54*

66666666666666

## 回复 by guardia (#13)

*2026-5-17 12:50*

66

## 回复 by xianhuimin (#14)

*2026-5-17 18:09*

看看

## 回复 by nqminhquan (#15)

*2026-5-17 20:57*

6666666

## 回复 by mb_tjqabdvq (#16)

*2026-5-17 21:36*

这个讨论对我很有帮助，谢谢！

## 回复 by 院士 (#17)

*2026-5-17 21:56*

来学习了。

## 回复 by wx_范迪塞尔 (#18)

*2026-5-17 22:45*

66666

## 回复 by dob_C (#19)

*2026-5-18 09:58*

感谢分享

## 回复 by 不具名的悲伤 (#20)

*2026-5-18 10:18*

6

## 回复 by cdline (#21)

*2026-5-18 11:04*

学习

## 回复 by mb_cbgtaveo (#22)

*2026-5-18 11:12*

6666666666666666

## 回复 by Imxz (#23)

*2026-5-18 12:10*

666

## 回复 by mb_uzmffdbw (#24)

*2026-5-18 15:26*

666

## 回复 by xingbing (#25)

*2026-5-18 15:54*

学习学习

## 回复 by uni7corn (#26)

*2026-5-18 17:05*

感谢分享。

## 回复 by SomeMx (#27)

*2026-5-18 17:53*

学习一下

## 回复 by dreameriii (#28)

*2026-5-18 18:04*

66666

## 回复 by k4y0z (#29)

*2026-5-18 18:14*

666

## 回复 by 三点水的湫 (#30)

*2026-5-18 19:38*

666

## 回复 by mb_jnmxfjku (#31)

*2026-5-19 14:17*

666

## 回复 by baichisi (#32)

*2026-5-19 18:05*

666

## 回复 by HangNam (#33)

*2026-5-19 19:38*

66

## 回复 by 夜惜风雨 (#34)

*2026-5-19 23:07*

666666666666

## 回复 by 桐人dx (#35)

*2026-5-20 01:49*

11111111111111

## 回复 by mb_cqabxiww (#36)

*2026-5-20 10:07*

view

## 回复 by YoungBai (#37)

*2026-5-20 10:32*

666

## 回复 by mb_qimctavn (#38)

*2026-5-20 10:57*

6

## 回复 by mb_bfghjvta (#39)

*2026-5-20 11:19*

学习学习

## 回复 by Mr.He (#40)

*2026-5-20 11:20*

666

## 回复 by mb_ahyhoece (#41)

*2026-5-20 17:25*

666

## 回复 by 带壳的蜗牛 (#42)

*2026-5-20 17:47*

666

## 回复 by kingking888 (#43)

*2026-5-20 18:25*

666

## 回复 by XCicada (#44)

*2026-5-21 12:17*

学习

## 回复 by 4Chan (#45)

*2026-5-21 14:00*

学习一下

## 回复 by pan_634488 (#46)

*2026-5-21 17:42*

666

## 回复 by mb_wgkjepnf (#47)

*2026-5-21 17:54*

666

## 回复 by 无视红绿灯 (#48)

*2026-5-21 19:52*

6666

## 回复 by GEKEZYX (#49)

*2026-5-22 00:11*

666

## 回复 by git_66480p0-tato (#50)

*2026-5-22 10:55*

66666666666666

## 回复 by B.M.K (#51)

*2026-5-22 21:58*

66

## 回复 by 呆萌的小白 (#52)

*2026-5-23 16:26*

挺好,可是我是模拟器啊,模拟器不能被自定义

## 回复 by mb_mihutdve (#53)

*2026-5-24 16:57*

学习

## 回复 by 简单的简单 (#54)

*2026-5-25 00:31*

666

## 回复 by mb_tplhoxah (#55)

*2026-5-25 09:50*

1zhichi

## 回复 by mb_kqsajzds (#56)

*2026-5-26 11:01*

666

## 回复 by mb_uvyukvot (#57)

*2026-5-26 11:07*

666

## 回复 by mb_cviyuksx (#58)

*2026-5-26 11:35*

学习

## 回复 by blx2024 (#59)

*2026-5-26 12:19*

学习

## 回复 by uboluo (#60)

*2026-5-26 15:11*

666

## 回复 by mb_jerxzakl (#61)

*2026-5-26 16:09*

6666

## 回复 by 有的是钱啊 (#62)

*2026-5-27 18:11*

111

## 回复 by wx_岁月真好_475628 (#63)

*2026-5-27 18:12*

66666

## 回复 by 偶尔.c (#64)

*2026-5-28 20:18*

学习一下，感谢分享

## 回复 by 寒号鸟二代 (#65)

*2026-5-28 21:08*

66666

## 回复 by git_73135NiaLark (#66)

*2026-5-30 03:14*

6666

## 回复 by 数字云信息 (#67)

*2026-6-1 18:53*

magisk有解决方案吗，如果强制改掉一些特征 环境就会暴雷

## 回复 by drf520 (#68)

*2026-6-3 18:29*

666666666666666666

## 回复 by hanjiefang (#69)

*2026-6-5 15:33*

1

## 回复 by mb_jzyasacd (#70)

*2026-6-6 10:28*

111

## 回复 by Snowman_Liam (#71)

*2026-6-6 10:35*

99999

## 回复 by byhk (#72)

*2026-6-8 10:59*

谢谢分享

## 回复 by mb_jnkpzfyq (#73)

*2026-6-8 11:30*

学习学习

## 回复 by mb_czqyztmr (#74)

*2026-6-10 14:20*

666

## 回复 by mb_otoynfkv (#75)

*2026-6-10 14:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  xingbing](https://bbs.kanxue.com/user-935.htm)
>  学习学习
>

nice

## 回复 by koftnt (#76)

*2026-6-11 17:11*

学习学写

## 回复 by 曦曦大牛子 (#77)

*2026-6-12 07:01*

牛而逼之

## 回复 by 蚂蚁驮大象 (#78)

*2026-6-12 09:53*

学习

## 回复 by mb_kgneopde (#79)

*2026-6-15 12:29*

666

## 回复 by mb_sqetvntx (#80)

*2026-6-15 13:07*

学习

## 回复 by qianfeng_mi (#81)

*2026-6-16 15:02*

学习学习

## 回复 by blackr0ck (#82)

*2026-6-17 20:38*

学习

## 回复 by 白毅 (#83)

*2026-6-18 02:35*

膜拜大佬

## 回复 by veluboii (#84)

*2026-6-23 16:32*

6666

## 回复 by mb_ajqftfbv (#85)

*2026-6-24 03:40*

学习学习

## 回复 by ulong9527 (#86)

*2026-6-26 09:44*

感谢分享，学习一下

## 回复 by mb_ntslceij (#87)

*2026-6-28 17:17*

学习一下

## 回复 by lamboo (#88)

*2026-6-29 20:15*

6666666

## 回复 by mb_zndfsnle (#89)

*2026-6-30 23:34*

学习学习

## 回复 by dædalus (#90)

*2026-7-2 00:08*

66

## 回复 by cavan (#91)

*2026-7-2 00:14*

学习学习

## 回复 by 枯藤舍 (#92)

*2026-7-3 11:14*

666

## 回复 by 枯藤舍 (#93)

*2026-7-3 11:14*

666

## 回复 by ldz666 (#94)

*2026-7-3 15:10*

666

## 回复 by mb_audxeeaj (#95)

*2026-7-3 15:11*

学习学习

## 回复 by mb_rybwnplq (#96)

*2026-7-3 15:13*

666

## 回复 by CheRevir (#97)

*2026-7-3 16:07*

666

## 回复 by Circ1e (#98)

*2026-7-6 18:24*

666

## 回复 by apxar (#99)

*2026-7-7 23:05*

1

## 回复 by iBa0 (#100)

*2026-7-8 21:47*

123

## 回复 by 好听的网名 (#101)

*2026-7-9 20:01*

学习学习

## 回复 by mb_sjowddqi (#102)

*2026-7-9 20:10*

777

## 回复 by mb_fbijwlgg (#103)

*2026-7-10 10:54*

学习学习

## 回复 by mb_ysikfhxt (#104)

*2026-7-10 12:06*

111

## 回复 by wx_kx92911 (#105)

*2026-7-15 09:44*

感谢分析

## 回复 by mb_degalzhb (#106)

*2026-7-15 14:36*

666

## 回复 by 3cly (#107)

*2026-7-16 16:21*

1

## 回复 by Kazusa (#108)

*2026-7-16 17:18*

学习学习

## 回复 by simpleness (#109)

*2026-7-16 19:43*

6

## 回复 by liowmark (#110)

*2026-7-17 14:12*

学习学习

## 回复 by wx_Kerberos (#111)

*2026-7-18 18:55*

![image](https://bbs.kanxue.com/view/img/face/062.gif)

## 回复 by mb_khbfrikh (#112)

*2026-7-19 23:16*

强力学习

## 回复 by Yuuuual (#113)

*2026-7-23 13:42*

学习记录，感谢分享

## 回复 by didiid (#114)

*2026-7-23 13:56*

666

## 回复 by mb_tzhmhmxv (#115)

学习学习

## 回复 by 发烧小孩 (#116)

111

## 回复 by mb_ujrqdalt (#117)

观摩一下

## 回复 by 乐子人 (#118)

牛逼，已经被某大厂抄进风控sdk了
