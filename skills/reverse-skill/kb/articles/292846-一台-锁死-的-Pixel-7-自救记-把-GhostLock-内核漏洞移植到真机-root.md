---
title: '[原创]一台"锁死"的 Pixel 7 自救记：把 GhostLock 内核漏洞移植到真机 root'
url: https://bbs.kanxue.com/thread-292846.htm
tid: 292846
author: 世界美景
date: '2026-09-04'
tags: [Android安全, 原创]
crawled_at: '2026-09-04T08:08:10+00:00'
replies: 18
---

> 关键词:CVE-2026-43499 / GhostLock / futex / 内核提权 / Pixel 7 / 无 root 侦察 / KASLR
> 适用读者:手里有一台 bootloader 回不去、想救回来的测试机的人;或者想把一个内核 exploit 移植到自己设备上的人。
> 前置要求:会 adb,看得懂一点 C,愿意接受手机重启几十次。
>
>

---

0. 事情的起因

我有一台 Pixel 7 测试机(欧版)。它之前是解锁 + 自刷 AOSP + Magisk root 的状态。某次我用谷歌官方网页刷机工具刷了个安卓 17 测试版,刷完之后:**开发者选项里的"OEM 解锁"开关彻底变灰,回不去了**。

没有 root 的测试机,对我来说就是一块好看的砖头。而且因为是测试机,里面什么都没有——随便折腾,大不了重启。

正好看到 Nebula Security 公开的 IonStack 利用链里有一个 2026 年 7 月披露的内核漏洞 **GhostLock(CVE-2026-43499)**,以及吾爱破解上一篇把它适配到一加 13T 的文章。这个漏洞理论上存在于**几乎所有 2011 年之后的 Linux 内核**(安卓当然在内),而且利用它不需要任何权限——只要能跑一段自己编译的程序(adb shell 就够)。

于是就有了这个项目。最终成果:**在这台 bootloader 锁死的 Pixel 7 上,通过漏洞拿到了 uid=0 + kernel 域 + 全局 SELinux permissive 的真 root**,虽然重启会掉(tethered),但测试机够用了。

这篇文章记录完整过程,重点写我踩过的、**前面两篇文章里都没有写到的坑**。如果你想把一个内核 exploit 移植到自己的设备,这些坑大概率你也会遇到。

---

## 1. 先说人话版原理:GhostLock 到底是个啥

先解释几个词:

- **futex**:Linux 里线程间"等锁"用的系统调用。你程序里的 `pthread_mutex_lock` 抢不到锁时,最后就是调它去内核里排队睡觉。
- **PI(优先级继承)**:一种防优先级反转的机制。排队睡在 PI 锁上的线程,会把自己挂到一棵红黑树里,按优先级排序,锁的主人会被临时"提级"。
- **栈 UAF**:内核在清理一段已经失效的栈内存时还在读写它。栈是每个线程在内核里的临时小本本,用完就扔——如果有人还攥着旧页码不放,而我们又能往同一页上写我们自己的内容,那内核读到的就是我们写的东西。

GhostLock 的 bug 出在内核 `rtmutex.c` 的 `remove_waiter()` 函数:它清理一个"排队者"时,**认错了人**——把发起 requeue 的线程的标记清了,真正排队的那个线程的标记没清。于是一个本该死掉的 rt_mutex_waiter 结构体,就这么"幽灵"一样地挂在优先级树上,指向一块已经作废的内核栈。

**怎么触发**(只要三个 futex 变量 + 三个线程,全是普通权限):

1. waiter 线程:先拿住 `f_pi_chain`,然后在 `f_wait` 上等,说自己等着被转到 `f_pi_target` 去;
2. owner 线程:先拿住 `f_pi_target`,再去抢 `f_pi_chain`(被 waiter 拿着)——卡死;
3. 主线程:发起 `FUTEX_CMP_REQUEUE_PI`,想把 waiter 转到 `f_pi_target`。

内核一查:waiter 等 target,target 在 owner 手里,owner 等 chain,chain 在 waiter 手里——**死锁!** 于是内核走"回滚"流程,回滚里就踩中了这个 15 年的 bug,waiter 的标记没被清掉。

之后,waiter 线程回到用户态,它那页作废的内核栈就可以被我们"重印":随便挑一个带大块栈缓冲区的系统调用(pselect、prctl、TCP zerocopy 都行),把伪造的 waiter 结构写回去。然后另一个线程对 waiter 调一下 `sched_setattr`(改个 nice 值,普通权限),内核就会沿着这个幽灵指针走一遍优先级链——读到的全是我们伪造的内容。伪造得当,红黑树的一次删除操作就能变成**往内核任意地址写一个指针**。

后面的事就顺理成章了:先改掉 `boot_id` 系统参数的指针,读回来就泄露了内核基址(破 KASLR);再改掉 `ashmem` 设备的函数表(配合 configfs 的合法函数绕过 CFI),拿到内核任意读写;最后 patch 自己进程的 cred,uid 变 0。

**理论上是完美的。难的是落地。** 原利用只支持 Pixel 10(安卓 17);吾爱破解那位作者适配了一加 13T(6.6 内核,但他有 root);我的 Pixel 7 是 6.1.145 内核,**没有 root、bootloader 锁死、调试通道全被封**。以下是真正的移植实战。

---

## 2. 第一步:没有 root,怎么摸清内核家底?

适配 exploit 需要三类数据:内核符号地址(相对 `_text`)、结构体字段偏移(task_struct/cred/rt_mutex_waiter 这些)、内存布局常数(物理加载基址之类)。

一加作者是真机 root 后直接读 `/proc/kallsyms` 和 BTF。我连 root 都没有,shell 下这些文件全部 Permission denied。

**但 Pixel 是谷歌亲儿子:官方工厂镜像公开下载,镜像里就有完整内核。** 流程:

1. 从设备读准确构建号:`adb shell getprop ro.build.fingerprint`(我是 `BP4A.251205.006`);
2. 下载对应工厂镜像,**校验 SHA-256**(谷歌官网页面有,校验过了才是真·同版本);
3. 解包 → `boot.img` → 按头部分离出内核(压缩的);
4. 用开源工具 **vmlinux-to-elf** 把压缩内核还原成带 10 万+符号表的 ELF;
5. 结构体偏移:GKI 内核内嵌 BTF(可以理解成内核自带的"结构体说明书"),我手写了一个 BTF 解析器直接导出所有结构体字段;
6. kallsyms 里没有的静态变量(`ashmem_misc`、`random_table` 里的 boot_id 项):写了个小工具直接在 ELF 里按指针特征反查出来。

到这里,**全部偏移在没有 root 的情况下拿齐了**,而且因为是同一份镜像,偏移天然精确。

### 小插曲:谷歌下载被限流

`dl.google.com` 的工厂镜像路径对我的出口 IP 直接 429(反爬)。另外谷歌中国镜像 `googledownloads.cn` 同样 429,别浪费时间,直接浏览器搜 panther-bp4a.251205.006-factory-4455f800.zip 最终在印度佬的网站下到了 废了好大力气！

---

## 3. 第二步:确认漏洞还在不在

漏洞 2026 年 5 月修复,6/7 月进安卓补丁。我的机器停在 2025 年 12 月补丁,理论上在。但"理论上"不作数,要实测。

社区有个现成的检测 App([CakesTwix/Android-CVE-2026-43499](https://github.com/CakesTwix/Android-CVE-2026-43499)),装上一跑:**手机当场内核 panic 重启**。

听起来吓人,其实是好消息:panic 说明漏洞路径可达且存在。测试机重启而已,无所谓。

> ⚠️ 这一步开始,你的手机会经历很多次 panic 重启,这是内核 exploit 开发的日常。别把重要数据放上面。
>
>

---

## 4. 第三步:选对模板,事半功倍

NebuSec 的仓库里,通用链是给 Pixel 10(6.6/6.12 内核)的;但 targets 目录里藏着一个 **oriole(Pixel 6)的独立完整版**——Pixel 6 和我的 Pixel 7 同属 `android14-6.1` GKI 分支,结构体布局几乎一样,而且它是"从 adb shell 直接跑"的独立可执行文件,正好符合我的处境。

所以路线定为:**以 oriole 版为模板,只换 panther 的偏移和布局常数**。

接下来的五个坑,一个比一个隐蔽,全部是真机实测 + 大量推理才定位的。

---

### 坑 1:kernelsnitch 找不到工作区——slab 步进不是结构体大小

exploit 里有个叫 KernelSnitch 的时序侧信道,用来在内核堆里找到我们自己的"工作区页面"(伪造 waiter 要放在一个地址已知的内核页面上)。原理很巧:内核 futex 哈希表的桶下标混入了 `mm_struct` 的地址,通过测量 futex 唤醒的耗时差异,可以反推出这个地址。

它暴力反推时按 `sizeof(mm_struct)` 在 slab 页里步进。我从 BTF 里读到的结构体大小是 **960 字节**,填进去——找不到。

原因:**slab 里的对象步长不等于结构体大小**。`mm_struct` 的缓存带 `SLAB_HWCACHE_ALIGN`,要按 CPU 的 cache 写回粒度(CWG)对齐,ARM64 上通常是 128 字节。960 补齐到 128 的倍数 = **1024**。oriole 模板里写的本来就是 1024,我"自作聪明"改成 960 反而错了。

> 教训:BTF 告诉你结构体逻辑大小,slab 步进是对齐后的物理大小。内核里这两者经常不一样。
>
>

### 坑 2:EDEADLK 有了、链走有了、写没落——"消崩溃探针"定位法

修好步进后,kernelsnitch 能找到工作区了,漏洞触发也成功了(每次 requeue 都稳定返回 EDEADLK),栈喷洒的伪造 waiter 也被内核读了(故意写个垃圾指针进去,手机立刻 panic——说明读到了)。**但红黑树那次关键的"写"就是不发生。**

没有任何内核日志通道(dmesg/pstore 全部要 root),怎么办?我的办法是**把"会不会崩"当成探针**:

- 把伪造 waiter 的 `task` 字段填成 `0x4141414141414141` → 崩了 → 说明链走读到了我的伪造 waiter;
- 写目标换成我自己页面的地址 → 又崩了 → 说明写的目标地址有问题;
- 一层层缩圈,最后定位到两处真问题(坑 3、坑 4)。

没有 kgdb 的时候,"崩不崩 + 崩在哪一步"就是你唯一的调试器。

### 坑 3:红黑树里的优先级竞速——把 0 改成 1000

这是全文最绕的一个坑,我尽量简单说。

那次关键写入发生在内核调整优先级链的 `[11]` 分支:只有当**被伪造的 waiter 成为锁上"最高优先级排队者"**时,内核才会执行那次删除-写入。

问题在于:回滚时内核在旧 waiter 的红黑树节点上留了个"已删除"的自闭环标记(RB_EMPTY_NODE)。oriole 上,栈喷洒会把这个标记恰好盖掉;**在我的内核构建上,TCP zerocopy 的栈帧错位了 8 字节,这个标记盖不掉**,于是一个清理路径直接跳过,伪造 waiter 永远当不上"最高优先级",写入永不发生。

解法简单粗暴但有效:把伪造树里另一个节点(w0)的优先级写成 **1000**(超级大、超级不优先),这样我们的伪造 waiter 怎么排都能赢,`[11]` 分支必然触发,写入落地。

> 教训:同一个栈喷洒原语,换个编译器版本/小版本号,栈帧布局就错位几字节。这类"隐性偏移"不在任何头文件里,只能真机试。
>
>

### 坑 4:内核物理加载基址——0x80000000 还是 0x80010000?

破 KASLR 的第一步(slide 泄漏)用的是**线性映射别名**(物理内存的固定虚址映射,不受 KASLR 影响),它依赖"内核镜像被加载到哪个物理地址"。业内惯例是 DRAM 起点 + 0x10000,一加那台实测也是这个值,我就照抄了。

结果:所有前置条件都对、写入也触发了——然后直接 panic。因为那一步写操作的落点错了 0x10000,戳进了内核代码段(只读),一写就崩。

真值是多少?**0x80000000**——Pixel 7 的 bootloader 严格按内核 Image 头的 `text_offset=0` 把内核放在了 DRAM 起点。修正后,泄漏一次成功:从 `/proc/sys/kernel/random/boot_id` 读出一串"假的 UUID",解码就是内核基址。

> 教训:物理布局三件套(DRAM 基址、内核物理加载点、线性映射基址)必须按本机核实,不能照抄。验证手段:设备树节点名(`/sys/firmware/devicetree/base/memory@80000000`)+ 镜像头 text_offset + 真机试跑。
>
>

### 坑 5:调试 print 本身会打乱竞态

最气人的一个:链路第二阶段的"栈喷洒 vs sched_setattr 链走"是个**亚毫秒级竞态**。我为了调试,在 consumer 线程每次触发时加了一行 `printf`——结果 100% 不成功了。因为这一行 print 的几毫秒延迟,刚好让竞态窗口错开。

**去掉热路径 print,立刻恢复成功。**

> 教训:竞态型 exploit 的调试,只能加"一次性"日志(初始化、阶段切换),绝不能在每次循环里打印。观察行为本身会改变被观察对象——内核 exploit 界的测不准原理。
>
>

### 坑 6:Android 16 的 ashmem 改名了

安卓 16 起,ashmem 设备节点名变成了 `/dev/ashmem<本次开机的boot_id>`。而 slide 泄漏的第一步恰恰会临时污染 boot_id……于是第二轮运行时,按 boot_id 拼出来的设备路径就不存在了,直接"no usable ashmem device"。

解法:别拼名字,直接扫 `/dev/ashmem*`。

---

## 5. 成功那一刻

修完所有坑,exploit 全流程跑通:

\```
[+] stage 1 complete base=ffffffd1d2c00000        <- KASLR 破
[+] stage 2 workspace ready                       <- fops 劫持
[*] phys step probed read done ok=1               <- 任意物理读写
[+] root ready uid=2000->0 ...                    <- cred patch
uid=0(root) gid=0(root) ... context=u:r:kernel:s0 <- 真 root
Permissive                                        <- SELinux 全局放行
\```

我在 exploit 末尾加了个小守护进程(rootd),监听 `127.0.0.1:7777`,谁连上就给谁一个 root shell。又写了个 127.0.0.1 的本地网页终端,浏览器里直接敲命令。重启后跑一遍 `reroot.sh`,两分钟恢复 root。

---

## 6. 没能完成的最后一步:永久 root

诚实交代:这是 **tethered root,重启即失**。想要持久,得解锁 bootloader 刷 Magisk;而我的 bootloader 翻不回来。

root 之后我做了这些尝试:

- **把 Citadel(Titan M 安全芯片)里的 DEVICE 锁位翻成 0**:成功,且重启不掉。做法是 root 后直接调 `android.hardware.oemlock.IOemLock` 这个 AIDL HAL(跳过设置界面)。
- **但 fastboot 的 `get_unlock_ability` 只看 CARRIER 锁位**,它还是 1。翻它需要 `CarrierUnlockRequest{version, nonce, signature}`——签名是谷歌服务器对设备 challenge 签发的(正常流程就是"联网 check-in → 拨动设置开关"那一步),离线伪造不了。

所以永久解锁这条路目前卡在一颗安全芯片的签名上。剩下的思路(留给有兴趣继续的人):

1. 直调 citadeld,走 AVB app 的 `CarrierLock(locked=false, device_data)`——这个请求**没有签名字段**,可能直接就收;
2. 逆向 ABL(bootloader)确认 `get_unlock_ability` 的精确判定式;
3. 研究 AVB app 的 owner-key 面(`SetOwnerLock`/`GetOwnerKey`),看能不能自签 token。

---

## 7. 方法论小结:一套可复用的跨设备移植流程

如果你要把一个内核 exploit 移植到自己的设备,这是我的清单:

1. **别急着上真机**。先拿同版本官方镜像,静态提取一切:kallsyms(vmlinux-to-elf)、结构体(BTF)、静态变量(指针特征反查)、内存布局(镜像头 + 设备树)。
2. **结构体字段偏移会静默漂移**。同一大版本的不同小版本都可能不一样(我这次 file*operations、task_struct.pi**、mm_struct 都和模板有出入),必须用本机 BTF 逐个核对,别只抄 target 头文件。
3. **hardened 配置决定哪些子技术能用**。UBSAN_TRAP、PANIC_ON_OOPS、KASAN/MTE、INIT_ON_ALLOC……先读 `config.gz`,再想路线。
4. **没有日志就用"崩溃探针"**。填垃圾指针看崩不崩、换目标地址看崩不崩,每一步把"无响应"变成"有信息"。
5. **竞态 exploit 不能加热路径日志**。要调试就先调静态部分,竞态部分靠推理 + 运气参数化。
6. **一次只改一个变量**。编译两个变体 A/B 轮流跑,比瞎猜快得多。

---

## 8. 参考与致谢

- Nebula Security 的 IonStack 系列(漏洞发现与原始利用):
- Part II(GhostLock 原理):<https://nebusec.ai/research/ionstack-part-2>
- Part III(安卓 17 root):<https://nebusec.ai/research/ionstack-part-3>
- 仓库:<https://github.com/NebuSec/CyberMeowfia>

- 吾爱破解《[原创]一加ACE5至尊版 kernel 6.6.89 尝试利用 GhostLock / IonStack 进行 root 提权》(一加 13T 6.6 内核适配,本文的出发点)
- 漏洞检测 App:<https://github.com/CakesTwix/Android-CVE-2026-43499>
- vmlinux-to-elf:<https://github.com/marin-m/vmlinux-to-elf>
- 内核精确源码:AOSP `kernel/common` 的 `android14-6.1.145_r00` 标签(国内可从清华 TUNA 镜像拉)

*本文只针对我自己的测试设备进行研究。漏洞信息均已公开多时并已有官方修复。请不要把这套方法用于任何不属于你的设备。*

![image](https://bbs.kanxue.com/upload/attach/202609/735880_GCTWQPUGYQ32EQX.webp)

> ## ???? 完整 PoC 已开源

> **[GitHub 仓库](https://github.com/1998lixin/Root_panther-BP4A.251205.006)**： https://github.com/1998lixin/Root_panther-BP4A.251205.006

>

> 包含完整 exploit 源码、适配脚本和详细使用文档。

---

# 回复

## 回复 by guijingwen (#2)

66

## 回复 by mb_jnmxfjku (#3)

666

## 回复 by iBa0 (#4)

牛逼啊

## 回复 by Zepp7289 (#5)

tql

## 回复 by 残废小菜比 (#6)

这个安卓的提权漏洞，直接把小米的BL锁干碎了，但是这CVE 对X86设备的exp 极少极少，是利用比较难吗？

## 回复 by doduhuang (#7)

学到了.点个 赞

## 回复 by YoungBai (#8)

666

## 回复 by lixianhuei (#9)

666

## 回复 by mb_lzdkguat (#10)

>
> [残废小菜比](https://bbs.kanxue.com/user-704893.htm)
>  这个安卓的提权漏洞，直接把小米的BL锁干碎了，但是这CVE 对X86设备的exp 极少极少，是利用比较难吗？
>

说不定是小米漏出来的，不能解锁可玩性就很低了

## 回复 by mb_iesvmzqc (#11)

太黑客了

## 回复 by k4y0z (#12)

666

## 回复 by mb_zzuxywot (#13)

666

## 回复 by 夜惜风雨 (#14)

666666666

## 回复 by pan_634488 (#15)

666

## 回复 by 肉蚌葱鸡 (#16)

666 感谢记录

## 回复 by mb_cbgtaveo (#17)

6666

## 回复 by wx_大冰 (#18)

666 感谢记录

## 回复 by xingbing (#19)

点个 赞 ![image](https://bbs.kanxue.com/view/img/face/079.gif)
