---
title: '[原创]安卓root方案APatch SELinux_hide mmap ABI漏洞分析'
url: https://bbs.kanxue.com/thread-293210.htm
tid: 293210
author: Lun_OS
date: '2026-10-13'
tags: [Android安全, 原创]
crawled_at: '2026-10-20T08:40:47+00:00'
replies: 10
attachments:
- {filename: KP139_SElinux-hide-check.zip, aid: '406599', path: ../attachments/293210/KP139_SElinux-hide-check.zip, url: 'https://bbs.kanxue.com/attach-download-406599-eb020e8e5a2a9c69bfaf650b4677948c@9fnY+rO6Ok7Z3hieR52UlQ==.htm', size: 13.99kb，10次下载, downloaded: false}
---

=# KP 0.13.9 SELinux 隐藏功能漏洞技术分析

——`/sys/fs/selinux/status` mmap ABI 违规分析（检测验证示例见附录）

>
> 分析对象：KP（KernelPatch）0.13.9 内置 `selinux_hide` 功能，`kernel/patch/common/selinux_hide.c`。
>
>
> 影响范围：当前所有AP系管理器root方案（APatch、FolkPatch、Aster...）
>
>
> 结论：`selinux_hide` 在替换 `sel_mmap_handle_status` 时未保留上游全部四项 ABI 检查，普通权限 app 通过发送"stock 内核必然拒绝、hook 实现必然放行"的请求组合即可判定该功能是否存在。判定依据为上游内核源码的规格约束（对参考值测量无依赖），因此在任何设备、任何内核版本上都不会对干净内核产生误报。此外，其中一项违规伴随内核内存可写性问题，属于应按安全缺陷处理的问题。
>
>
>

---

## 1. 背景：selinux_hide 的功能结构

KP 0.13.9 的 SELinux 隐藏功能（`selinux_hide.c`，约 980 行）目标是使 uid >= 10000 的 app 在 SELinux 层面观察到修改前的系统状态，掩盖 APatch/KernelSU 类方案留下的痕迹。核心机制四条：

| 机制 | 挂载点 | 效果 |
|-|-|-|
| 干净策略快照 | `post-fs-data before` 深拷贝 boot policy | context/access/setprocattr 对 app 按快照作答，Magisk/apd 之后的 policy reload 不可见 |
| 假 status 页 | hook `sel_read_handle_status` + `sel_mmap_handle_status` | app 读/mmap `/sys/fs/selinux/status` 观察到 `enforcing=1`、干净 seqno |
| seqno 补丁 | hook `sel_write_access` | DirtySepolicy 探针（`untrusted_app → untrusted_app, tclass=0`）的应答 seqno 被改写为 1，其余字段原样保留 |
| setprocattr 净化 | hook `selinux_setprocattr` | app 切 context 时按干净快照校验 |

启用路径：`/data/adb/ap/selinux_hide` 控制文件存在 → `post-fs-data before` 快照策略、`after` 安装 hook。仅支持 kernel >= 4.19。

hook 安装方式分两档：符号解析成功时走 inline hook；失败时对 `write_op[]` 表和 `sel_handle_status_ops` fops 结构做数据指针替换（不修改内核 text，规避 text 完整性校验）。本文的分析范围限于替换后的 handler 是否保留了上游 ABI，问题集中在该环节。

## 2. 上游契约：stock 内核对 status 节点的四项检查

`/sys/fs/selinux/status` 是 libselinux 做 avc 无锁 fast-path 查询的节点。本地核对的 `security/selinux/selinuxfs.c` 4.19 与 5.10 源码中 `sel_mmap_handle_status()` 逐字一致（4.19 :246-266，5.10 :246-266）：

```c
static int sel_mmap_handle_status(struct file *filp,
				  struct vm_area_struct *vma)
{
	struct page    *status = filp->private_data;
	unsigned long	size = vma->vm_end - vma->vm_start;

	BUG_ON(!status);

	/* only allows one page from the head */
	if (vma->vm_pgoff > 0 || size != PAGE_SIZE)
		return -EIO;
	/* disallow writable mapping */
	if (vma->vm_flags & VM_WRITE)
		return -EPERM;
	/* disallow mprotect() turns it into writable */
	vma->vm_flags &= ~VM_MAYWRITE;

	return remap_pfn_range(vma, vma->vm_start,
			       page_to_pfn(status),
			       size, vma->vm_page_prot);
}
\```

四项检查（6.x 内核该函数的检查块与此相同）：

1. **偏移必须为 0**（`vm_pgoff > 0 → -EIO`）；
2. **长度必须恰好一页**（≠ PAGE_SIZE → -EIO）；
3. **拒绝可写请求**（`VM_WRITE → -EPERM`）；
4. **清除 `VM_MAYWRITE`**。这一项的作用：status 节点为 `S_IRUGO`（0444）且 fops 无 `.write`（4.19/5.10 `sel_fill_super` :1920 `[SEL_STATUS] = {"status", &sel_handle_status_ops, S_IRUGO}`），普通只读文件映射在默认路径下允许 `mprotect(PROT_READ|PROT_WRITE)`（走 COW）；只有 handler 显式清除 VM_MAYWRITE，mprotect 才会被 VFS 以 `-EACCES` 拒绝。因此 mprotect 被拒这一行为本身就是 handler 存在且执行了该项清除的可观测特征。

同文件 `sel_write_access()`（5.10 :813-862）的应答格式：

```c
	length = scnprintf(buf, SIMPLE_TRANSACTION_LIMIT,
			  "%x %x %x %x %u %x",
			  avd.allowed, 0xffffffff,
			  avd.auditallow, avd.auditdeny,
			  avd.seqno, avd.flags);
\```

`security_compute_av_user()` 从 `avd_init()` 出发（allowed=0, auditallow=0, auditdeny=0xffffffff），tclass==0 时直接返回。因此对探测串 `u:r:untrusted_app:s0 u:r:untrusted_app:s0 0`，真内核的 6 字段应答必然满足 field[1]==ffffffff 且 field[3]==ffffffff。该推导构成 `/access` 查询面的检测依据（见附录 A Oracle [2]）。

## 3. KP 0.13.9 的实现问题

### 3.1 根因：`my_sel_mmap_handle_status` 缺失全部四项检查

KP 的替换实现（selinux_hide.c :570-625）核心逻辑：

```c
start = vm[KP_VMA_VM_START_OFF / sizeof(unsigned long)];   /* 按偏移读取 vma 字段 */
prot  = vm[kp_vma_page_prot_off() / sizeof(unsigned long)];

ret = kp_remap_pfn_range(vma, start, pa >> page_shift, KP_PAGE_SIZE, prot);
\```

实现只检查 vm_start 页对齐和假页物理地址可解析，然后直接 `remap_pfn_range` 一页假 status 到 vma 上：

- 不检查 `vm_pgoff` → 非零偏移的 mmap 被放行；
- 不检查 `vm_end - vm_start` → 任意长度 mmap 被放行；
- 不检查 `VM_WRITE` → `PROT_READ|PROT_WRITE` 的 MAP_PRIVATE 请求被放行；
- 不清除 `VM_MAYWRITE`，且 `remap_pfn_range` 自身会设置 `VM_PFNMAP`——两者叠加的后果见 3.4。

对照上游，四项检查全部缺失。能 open 该节点的进程发送任一非法请求，stock 内核返回 -EIO/-EPERM、KP 返回成功，应答差异构成检测依据。

### 3.2 漏洞清单：四项可探测的 ABI 违规

以基线映射（`mmap(0, 4096, PROT_READ, MAP_PRIVATE)`，libselinux 自身使用的参数）为参照，以下四个探测请求在 stock 与 KP 下行为不同：

| # | 探测请求 | stock 行为 | KP 0.13.9 行为 | 判定 |
|-|-|-|-|-|
| a | `mmap(0, 8192, PROT_READ, MAP_SHARED)` | -EIO | 放行（只 remap 一页，第二页保留在 VMA 中未映射） | 放行即判定违规；探测方应避免访问第二页（未映射会 SIGSEGV），测完即 munmap |
| b | `mmap(4096, 4096, PROT_READ, MAP_SHARED)` | -EIO | 放行（假页被映射到 vm_start） | 同上 |
| c | `mmap(0, 4096, PROT_READ\|PROT_WRITE, MAP_PRIVATE)` | -EPERM（handler 检查 VM_WRITE） | 放行 | 同上；后续影响见 3.4 |
| d | 对基线映射 `mprotect(PROT_READ\|PROT_WRITE)` | -EACCES（仅因 handler 清了 VM_MAYWRITE） | 成功 | 单项即可判定：普通只读文件映射允许 mprotect 升级（COW），EACCES 出自 handler 的 `~VM_MAYWRITE`，该项缺失即成立 |

探测设计需遵守的判定规则（避免误报）：

- 只有 GRANTED 计为违规；任何 errno 拒绝一律视为通过（errno 合法地随 VFS fast path / LSM / 内核版本变化，判定不依赖具体错误码）；
- 不探测 `PROT_WRITE + MAP_SHARED`——VFS 在 handler 之前就会因节点 0444 无 FMODE_WRITE 拒绝该请求，该探测无信息量；
- 授予的映射不解引用（a 的 2 页 grant 只映射了第 1 页，访问第 2 页会 SIGSEGV），测完即 munmap；
- 基线映射失败时报告 UNTESTABLE，与"未检出"严格区分。

该判定为对上游内核源码行为的规格断言，跨设备可移植，对干净内核不产生误报。附件检测工程实现了上述探测组合，验证结果与本节一致。

### 3.3 语义不一致：mmap 与 read() 的偏移行为矛盾

KP 下，app 对 status fd 执行 `read(buf, n)` 且 pos=4096 时返回 EOF（假页有效内容 20 字节），而 `mmap(fd, ..., offset=4096)` 却成功并展示完整 status 头部。"offset 4096 读为空、mmap offset 4096 却有内容"这一组合没有任何真内核会产生——即使不做 3.2 的四项探测，单对比 read/mmap 语义也能判定替换实现存在。这是 3.1 中"不检查 vm_pgoff"的直接推论。

### 3.4 严重项：探测 c 直接建立指向内核内存的可写 PTE（安全问题）

上游清除 `VM_MAYWRITE` 是安全边界的一部分。KP 的映射由 `remap_pfn_range` 建立（`VM_PFNMAP`，页背后无 struct page），且 KP 将读取自 vma 的 `vm_page_prot` 原样传给该函数。两条路径的行为不同：

- **探测 c（`MAP_PRIVATE + PROT_WRITE` 直接请求）**：VFS 层对 MAP_PRIVATE 不校验 FMODE_WRITE，请求到达 handler；由于 KP 未拒 VM_WRITE，`vm_page_prot` 含可写位，`remap_pfn_range` 按该 prot 建立 PTE——用户态拿到的映射**从一开始就是可写的**，写操作经页表直接落在内核 vmalloc 分配的假 status 页（`kp_vmalloc(4096)`，PA 由 `pgtable_phys_kernel` 解析），不经过任何缺页/COW 环节。推导依据：`remap_pfn_range` 按 handler 传入的 prot 建 PTE，主线内核对该调用无"私有 COW 映射禁止可写"的前置检查；此条属源码推导，建议以实机写验证确认。
- **探测 d（mprotect 升级基线映射）**：mprotect 成功本身构成 3.2 的判定依据；此后私有 PFNMAP 映射的写缺页在主线内核走 `do_wp_page → wp_page_copy`（COW 到匿名页，原页内容经 `copy_from_user` 复制），写操作落在匿名副本上，不修改内核假页。该路径的风险限于"mprotect 被放行"这一检测面。

综合：探测 c 使 uid >= 10000 的普通 app 可能获得对内核 vmalloc 内存的写映射。当前可写范围限于假 status 页本身（20 字节有效内容），破坏面有限，但这破坏了"status 节点对用户态只读"的上游保证，应按内核安全缺陷处理。

### 3.5 其他次级问题

1. **假 status 值部分硬编码**（`fill_fake_status_bytes`，:190-210）：`kver >= 6.7` 时 `pload=1` 否则 0，seqno 随后被 `selinux_sepolicy_clean_seq()` 覆盖，但 policyload/deny_unknown(=1)/enforcing(=1) 为常量。对一台真实的 6.7+ 干净设备，若其真实 policyload ≠ 1，该常量值本身构成弱特征（常规检测面可读取的证据有限）。
2. **vma 字段偏移按内核版本取值**：`vm_page_prot` 偏移 6.1+ 取 24、否则 72（注释称来自 6.12 BTF），仅有 `kp_pgprot_plausible()` 的 arm64 pgprot 形状检查兜底；4.19 上偏移 72 是否恒成立缺少按版本校验，错位时靠 plausible 检查回退到原 handler——行为正确性有兜底，但退化是静默的。
3. **seqno 探针分支注释与实现不一致**：注释写"change only the seqno to 0"，实现 `seqno = 1`（与 `KP_AVD_CLEAN_SEQNO` 一致），影响后续维护判断。
4. **死代码**：`fill_fake_status_bytes` 中 `kver >= 6.7` 的 `seq=4/pload=1` 赋值被紧接着的 `seq = selinux_sepolicy_clean_seq()` 覆盖（pload 未覆盖，见问题 1）。
5. **sscanf 依赖**：seqno 探针用 `sscanf("%63s %63s %hu", ...)` 解析用户输入，tclass 经 `%hu` 截断；探针判定基于前缀匹配（`u:r:untrusted_app:s0` 后允许 `\0` 或 `:`），非探针查询走干净快照路径——路径分叉正确，无安全问题，仅实现风格问题。

## 4. 上游修复状态核查（2026-10-13，master @ f36f3d13）

对照 `bmax121/KernelPatch` master 分支（最新提交 `f36f3d1377004871f8c964f7cd3276712eeba943`，2026-10-10 "refine selinux_hide"，已拉取该提交 patch 及 master 全文核对）：

**本文 3.1 的问题未修复。** master 的 `my_sel_mmap_handle_status`（master 版 selinux_hide.c :711-766）与本地 0.13.9 版本一致——仍只检查 vm_start 页对齐和假页物理地址可解析，`vm_pgoff`、`vm_end - vm_start`、`VM_WRITE` 三项检查缺失，`VM_MAYWRITE` 未清除。3.2 的四项探测（a/b/c/d）在 master 上仍然全部命中，`fill_fake_status_bytes`（master :188-208）的硬编码常量也未修改。

master 近期两次 selinux_hide 相关提交修复的是其他类别的可观测差异：

- `81ff19ad`（#320，10-01）"answer policy queries from the clean snapshot"：废弃 0.13.9 的 symbol-redirect 窗口机制，context/access/setprocattr 改为完全独立地从快照作答；seqno 应答补丁器（`kp_patch_response_seqno`）删除，DirtySepolicy 探针由"快照应答携带 stock seqno"覆盖。新版 `my_write_access_new` 走独立计算路径（`lib_memset(&avd,0,...); avd.auditdeny=0xffffffff`）——对 tclass=0 探测，其应答 field[1]=ffffffff、field[3]=ffffffff 由代码显式构造，形状仍与内核一致。
- `f36f3d13`（10-10）"refine selinux_hide"：修复两个时序/计数侧信道——① `kp_context_to_sid_clean` 只对快照接受的 context 做 live 侧注册（被拒查询不再导致 `ss/sidtab_hash_stats` 可见计数增长，封住按计数枚举隐藏域的通道）；② `my_setprocattr_new` 将 `PROCESS__SETCURRENT` 权限检查移回 context 解析之前（消除"合法 context 的拒绝比非法的慢一次解析"的时序差，即 KernelSU a85dcbcf 修复的同类问题），且 qlog 移到权限判定之后。

总结：上游在收敛语义/时序类可观测差异，但 status mmap 的 ABI 级问题未处理，3.2 的探测组合对当前 master 仍然有效。

## 5. 结论

KP 0.13.9 `selinux_hide` 的策略快照/seqno 补丁链路设计合格——应答形状保持内核一致。但 status mmap 路径的替换实现丢弃了上游 handler 的全部输入校验与 vma flag 副作用：四项 ABI 违规均可被无 root 探测，其中 mprotect 项单项即可判定；且探测 c 的路径使普通 app 可能获得对内核 vmalloc 内存的直接写映射，已超出"可检测"范畴构成安全缺陷。

核心结论：替换内核 handler 时，原 handler 对用户态输入的全部校验与 vma flag 修改均需逐项保留；返回值与安全边界同属被替换行为的组成部分，二者都须维持与上游一致。

---

## 附录 A：附件检测工程概述（KP139_SElinux-hide-check）

附件工程 `KP139_SElinux-hide-check` 为本文漏洞的验证示例，包含 `libkpsc.so`（native 探测，`native/check.c`）与 App 载体两部分。判定逻辑概要：
https://github.com/Lun-OS/Download/releases/tag/vip.lunos.kpselinuxhide.check.demo1

### A.1 Oracle [1]：status mmap ABI 违规（对应本文 3.2）

对基线映射执行探测 a/b/c/d，任一 GRANTED 即判定 KP 0.13.9 的 `selinux_hide` 存在。判定规则与 3.2 节一致：拒绝视为通过、基线失败报 UNTESTABLE（值 2），三态结果为 0=clean / 1=detected / 2=untestable。

### A.2 Oracle [2]：老版 SELinux_hook KPM 的固定应答

老版 SELinux_hook KPM 1.1.7 对 `/access` 查询固定应答 `"0 0 0 0 1 0"`：field[1]（decided）= 0、field[3]（auditdeny）= 0。按第 2 节推导，真内核对 tclass=0 探测只能给出 ffffffff/ffffffff，存活节点返回该形状即表明 hook 存在且为老版本。

防误报与防交叉干扰设计：

- KP 0.13.9（及 master `my_write_access_new`）的应答只涉及第 5 字段（seqno）或保持六字段内核一致形状，Oracle [2] 对其无判定能力，两个 oracle 互不干扰；
- 探测串 `u:r:untrusted_app:s0 u:r:untrusted_app:s0 0` 不含 magisk/ksu 等标记子串，避免被其他隐藏层的 deny-list 拦截后产生错误归类；
- 应答字段数非 6 或解析失败时报 UNTESTABLE。

### A.3 载体设计

1. **双域探测**：AOSP 策略下普通 `untrusted_app` 只能读 status 节点；唯一被允许 read/write selinuxfs 事务节点的无特权域是 `u:r:app_zygote:s0`。工程用 `isolatedProcess + useAppZygote` 的 `ProbeService` 触发 system_server 创建 App Zygote（`android:zygotePreloadName` → `ZygotePreloadImpl.doPreload` 在该域内执行探测），再从 App Zygote fork 出 isolated 进程，通过 fork 继承静态字段 + Binder transact(1) 将结果带回 activity（app_zygote 域无法写 app 数据目录，fork 继承为可行通道）。主进程与 app_zygote 域任一命中即判定检出。
2. **UNTESTABLE 不计入 clean**：任何载体失败都无权独立产生未检出结论，封住"破坏检测环境使结果显示干净"的对抗路径。

## 附件

- [KP139_SElinux-hide-check.zip](../attachments/293210/KP139_SElinux-hide-check.zip) — 13.99kb，10次下载

---

# 回复

## 回复 by mb_ldbucrik (#2)

感谢分享

## 回复 by iBa0 (#3)

111

## 回复 by Aar0n (#4)

kk

## 回复 by 大魔头 (#5)

666

## 回复 by xianhuimin (#6)

看看

## 回复 by Ascend_202904 (#7)

6666

## 回复 by mb_xgrnikfg (#8)

66666

## 回复 by xingbing (#9)

感谢分享。

## 回复 by C0rax (#10)

kk

## 回复 by uboluo (#11)

666
