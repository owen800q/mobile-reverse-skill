---
title: '[原创] 软解页表实现远程内存访问，可避免 mincore 检测。'
url: https://bbs.kanxue.com/thread-277144.htm
tid: 277144
author: vrolife
date: '2023-05-08'
tags: [Android安全, 原创, 基础理论]
crawled_at: '2026-08-11T08:47:54+00:00'
replies: 19
---

## 背景

众所周知 Linux 内核远程进程内存访问可通过 process_vm_readv 和 process_vm_writev 来进行。但是调用这两个 syscall 来实现远程进程访问的花，会被目标检测到。原理是通过是否内存缺页来判断特定内存是否被访问过，检测内存是否缺页可通过 mincore 来实现。

 绕过这个检测的方法有两个，一个是通过查询页表的方式绕过缺页的地址，二是通过软件解析页表得到物理地址再实现内存访问。因为第一个方法不实用，所以这里不作介绍。

## 原理

以 39 BIT ARM64 平台的 Linux 为例，这种配置的 Linux 内核使用3级页表。通过三级页表可以将虚拟地址转换为物理地址。
分别是 PGD PMD PTE 也就是下图中 L1 到 L3。每一个 64 BIT 的地址都可以按照下图分解出每一级页标的索引，进而查询到地址所在的页面和在页面中的偏移量。

| 1234567891011 | `+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``\|``63`    `56``\|``55`    `48``\|``47`    `40``\|``39`    `32``\|``31`    `24``\|``23`    `16``\|``15`     `8``\|``7`      `0``\|``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``+``\|                 \|         \|         \|         \|         \|``\|                 \|         \|         \|         \|         v``\|                 \|         \|         \|         \|   [``11``:``0``]` `in``-``page offset``\|                 \|         \|         \|` `+``-``> [``20``:``12``] L3 index``\|                 \|         \|` `+``-``-``-``-``-``-``-``-``-``-``-``> [``29``:``21``] L2 index``\|                 \|` `+``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``> [``38``:``30``] L1 index``\|` `+``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``> [``47``:``39``] L0 index``+``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``> [``63``] TTBR0``/``1` |
|-|-|

## 实现

在 Linux 内核中有一系列的宏和函数可用于虚拟地址到物理地址的转换。以下是提取自 39 BIT ARM64 Linux 内核的相关宏。

| 1234567891011121314151617181920212223 | `/``/` `48bit``#define PHYS_MASK 0x3FFFFFF000Ul` `/``/` `39bit``#define PAGE_OFFSET 0xffffffc000000000` `#define __paddr_to_vaddr(pa) ((unsigned long)((pa) - PHYS_OFFSET) \| PAGE_OFFSET)` `#define __page_paddr(entry) (PHYS_MASK & entry)` `#define __pgd_index(addr) (((addr) >> 30) & 0x1FF)``#define __pgd_offset(pgd, addr) ((pgd) + __pgd_index(addr))` `#define __pmd_index(addr) (((addr) >> 21) & 0x1FF)``#define __pmd_offset(dir, addr) ((pt_entry_t*)__paddr_to_vaddr(__page_paddr(*(dir)) + __pmd_index(addr) * sizeof(pt_entry_t)))` `#define __pte_index(addr) (((addr) >> 12) & 0x1FF)``#define __pte_offset(dir, addr) ((pt_entry_t*)__paddr_to_vaddr(__page_paddr(*(dir)) + __pte_index(addr) * sizeof(pt_entry_t)))` `#define __page_addr(dir, addr) ((pt_entry_t*)__paddr_to_vaddr(__page_paddr(*(dir))))``#define __page_base(addr) ((addr) & ~0xFFFUL)` `#define __offset_in_page(addr) ((addr) & 0xFFF)` |
|-|-|

转换方法如下

| 12345678910111213141516171819202122232425262728 | `void``*` `resolve_page(pt_entry_t``*``mm_pgd, uintptr_t addr)``{``DEBUG_LOG(``"-  vma = %p\n"``, (unsigned` `long``)addr);``DEBUG_LOG(``"+  pgd = %p\n"``, (unsigned` `long``)mm_pgd);` `pt_entry_t``*` `pgd` `=` `__pgd_offset(mm_pgd, addr);``DEBUG_LOG(``"+ *pgd = %016llx\n"``,` `*``pgd);` `if` `((``*``pgd &` `2``) !``=` `0``) {``pt_entry_t``*` `pmd` `=` `__pmd_offset(pgd, addr);` `DEBUG_LOG(``"+ *pmd = %016llx\n"``,` `*``pmd);` `if` `((``*``pmd &` `2``) !``=` `0``) {``pt_entry_t``*` `pte` `=` `__pte_offset(pmd, addr);``DEBUG_LOG(``"+ *pte = %016llx\n"``,` `*``pte);` `if` `((``*``pte &` `1``)) {``void``*` `page` `=` `__page_addr(pte, addr);` `DEBUG_LOG(``"+ page = %016llx\n"``, page);` `return` `page;``}``}``}``return` `NULL;``}` |
|-|-|

参数`mm_pgd`是目标进程页表地址，`addr`是要转换的虚拟地址。这一点点代码量，相信对本文有兴趣的人，都能看得懂，所以就不详细解释了。

## 实践

上文提供的代码可通过 Linux 内核模块的方式部署到目标设备中。这里提供一个简单的实现代码片段：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118 | `#define VMRW_VERSION 2` `struct Request {``int` `version;``int` `pid;``void``*` `remote;``void``*` `local;``size_t size;``ssize_t result;``};` `struct dentry` `*` `vmrw_file` `=` `NULL;` `static``ssize_t fop_read(struct` `file``*` `file``, char``*` `req_buffer, size_t size, loff_t``*` `offset)``{``struct Request req;` `if` `(size !``=` `sizeof(struct Request)) {``return` `-``EBADMSG;``}` `copy_from_user(&req, req_buffer, size);` `if` `(req.version !``=` `VMRW_VERSION) {``return` `-``EBADMSG;``}` `struct pid``*` `pid` `=` `find_get_pid(req.pid);` `if` `(pid` `=``=` `NULL) {``return` `-``ENOENT;``}` `struct task_struct``*` `task` `=` `get_pid_task(pid, PIDTYPE_PID);``if` `(task` `=``=` `NULL) {``return` `-``ENOENT;``}` `struct mm_struct``*` `mm` `=` `get_task_mm(task);``if` `(mm` `=``=` `NULL) {``return` `-``ENOENT;``}` `pt_entry_t``*` `mm_pgd` `=` `*``(pt_entry_t``*``*``)((char``*``)mm` `+` `rti.mm_pgd_offset);` `#ifdef __aarch64__``/``/` `#if ENABLE_DEBUG_LOG``/``/`     `typedef void (``*``show_pte_t)(unsigned` `long` `addr);``/``/`     `void``*` `kallsyms_lookup_name(const char``*` `name);``/``/`     `show_pte_t show_pte` `=` `(show_pte_t)kallsyms_lookup_name(``"show_pte"``);``/``/`     `show_pte((uintptr_t)req.remote);``/``/` `#endif``#endif` `size_t remain` `=` `req.size;``uint64_t src` `=` `(uintptr_t)req.remote;``char``*` `dst` `=` `(char``*``)req.local;` `DEBUG_LOG(``"=  read %016llx %lu to %016llx\n"``, req.remote, req.size, req.local);` `while``(remain) {``void``*` `page` `=` `resolve_page(mm_pgd, src);``if` `(page` `=``=` `NULL) {``DEBUG_LOG(``"+  invalid page %016llx\n"``, src);``break``;``}` `void``*` `page_ptr` `=` `((char``*``)page` `+` `__offset_in_page(src));` `size_t page_sz` `=` `__MIN(``0x1000` `-` `__offset_in_page(src), remain);` `DEBUG_LOG(``"!  copy %016llx %lu to %016llx\n"``, page_ptr, page_sz, dst);` `unsigned` `long` `r` `=` `copy_to_user(dst, page_ptr, page_sz);``if` `(r !``=` `0``) {``remain` `-``=` `page_sz` `-` `r;``break``;``}` `remain` `-``=` `page_sz;``src` `+``=` `page_sz;``dst` `+``=` `page_sz;``}` `req.result` `=` `req.size` `-` `remain;``copy_to_user(req_buffer, &req, sizeof(struct Request));` `mmput(mm);``return` `sizeof(struct Request);``}` `static``ssize_t fop_write(struct` `file``*` `file``, const char``*` `ptr, size_t size, loff_t``*` `offset)``{``return` `-``EPERM;``}` `struct file_operations vmrw_fop` `=` `{``.owner` `=` `&__this_module,``.read` `=` `fop_read,``.write` `=` `fop_write``};` `int` `TEXT_INIT module_init() {``DEBUG_LOG(``"vmrw init\n"``);``vmrw_file` `=` `debugfs_create_file(__this_module.name,` `0600``, NULL, NULL, &vmrw_fop);``if` `(vmrw_file` `=``=` `NULL) {``pr_error(``"failed to create vmrw debugfs file\n"``);``}``return` `0``;``}` `void TEXT_EXIT module_exit() {``DEBUG_LOG(``"vmrw exit\n"``);``debugfs_remove_recursive(vmrw_file);``vmrw_file` `=` `NULL;``}` |
|-|-|

正常情况下要部署内核模块，是需要目标内核的源代码来编译内核模块方可在目标设备上部署。因此这个内核模块虽然能正常工作，但仍是不实用的。

## 后记

要实用化本文分享的技术原理，需要泛用化内核模块的制作和部署。直白来说就是通过制作一个通用的内核模块二进制模板，然后部署的时候通过部署工具，将内核模块适配到实际运行的内核，使之可以被加载和运行。这个我目前还没有找到公开的方案，倒是有蛛丝马迹暗示类似技术在网上活跃。为防止技术被滥用，再三思考还是不放出了。只是想混个转正而已，不懂此文是否足够。

## 警告

本文提供的技术和代码仅供学习研究之用途，不可用于商业目的，不可用于违规违法目的，违者自行承当后果。

 本文展示的代码片段部分来自 Linux 内核源码，因此受到 Linux 的 GPLv2 授权感染。

## 参考链接

https://docs.kernel.org/arm64/memory.html

---

# 回复

## 回复 by ycmint (#2)

*2023-5-9 15:23*

文章目的是什么？process_vm_readv 和 process_vm_writev 自实现，绕过 调用检测？ 那为啥不直接参考 这辆syscall 的内核实现。。。。bug 还少。。。

## 回复 by vrolife (#3)

*2023-5-9 16:08*

>
> [ycmint](https://bbs.kanxue.com/user-356233.htm)
>
>  文章目的是什么？process_vm_readv 和 process_vm_writev 自实现，绕过 调用检测？ 那为啥不直接参考 这辆syscall 的内核实现。。。。bug 还少。。。
>
>

因为参考这两 syscall 的实现，最终效果就是本文提及的差不多的技术。而且按你的想法实现的话，是没办法和内核解耦的，更不可能在没有源码的情况下实现这效果。

## 回复 by ycmint (#4)

*2023-5-9 16:31*

没懂。。。。 没有源码咋就不能这效果。。。我解决掉preload ko 就能跑了。。。

## 回复 by ycmint (#5)

*2023-5-9 16:33*

>
> [vrolife](https://bbs.kanxue.com/user-978503.htm)
>
>  因为参考这两 syscall 的实现，最终效果就是本文提及的差不多的技术。而且按你的想法实现的话，是没办法和内核解耦的，更不可能在没有源码的情况下实现这效果。
>
>

或者，我压根不需要解决加载ko 这些事。。我找个合适的地方，binary 插入vmlinux进去就好。。。

## 回复 by vrolife (#6)

*2023-5-9 16:40*

>
> [ycmint](https://bbs.kanxue.com/user-356233.htm)
>
>  或者，我压根不需要解决加载ko 这些事。。我找个合适的地方，binary 插入vmlinux进去就好。。。
>
>

不是没考虑这样的方案，问题是这样子要解决很多符号和数据结构问题，不然就得为每份内核配置和每个内核版本编译一个ko。内核很多接口都是内联或者干脆是宏，无源码做兼容太难了。

## 回复 by ycmint (#7)

*2023-5-9 16:59*

>
> [vrolife](https://bbs.kanxue.com/user-978503.htm)
>
>  不是没考虑这样的方案，问题是这样子要解决很多符号和数据结构问题，不然就得为每份内核配置和每个内核版本编译一个ko。内核很多接口都是内联或者干脆是宏，无源码做兼容太难了。
>
>

那你的厉害方案是啥呢

## 回复 by vrolife (#8)

*2023-5-9 17:19*

>
> [ycmint](https://bbs.kanxue.com/user-356233.htm)
>
>  那你的厉害方案是啥呢
>
>

不厉害，也就是尽可能少引用内核符号罢了。然后部署的时候实时从内核binary里取几个偏移量就行了。开始我第一个念头也是仿那两个syscall, 结果兼容性一言难尽。而且那两个syscall核心原理就是锁内存页，不暂停目标进程的话，不安全，暂停了的话，性能太受影响。期待你分享别的方案![image](https://bbs.kanxue.com/view/img/face/71.gif)

## 回复 by shinratensei (#9)

*2023-5-10 13:03*

这......![image](https://bbs.kanxue.com/view/img/face/77.gif)

## 回复 by 不知世事 (#10)

*2023-5-15 19:52*

扫描内存的时候，使用mincore过滤掉缺页内存不就可以绕过检测了么，用魔法打败魔法

## 回复 by vrolife (#11)

*2023-5-16 00:25*

>
> [不知世事](https://bbs.kanxue.com/user-706599.htm)
>
>  扫描内存的时候，使用mincore过滤掉缺页内存不就可以绕过检测了么，用魔法打败魔法
>
>

不这么做，主要是考虑竞态条件的问题。这样做，只有过滤线程和陷阱线程是同一个线程的时候，才能经济地实现。

## 回复 by 不吃早饭 (#12)

*2023-5-16 01:32*

我看刑，说吧准备做哪个游戏![image](https://bbs.kanxue.com/view/img/face/87.gif)

## 回复 by vrolife (#13)

*2023-5-16 02:28*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  不吃早饭](https://bbs.kanxue.com/user-825489.htm)
>
>  我看刑，说吧准备做哪个游戏[em_87]
>
>

别开玩笑了，还是有方法能检测到这种类型的内存读写的，还不需要任何特殊权限。

## 回复 by 秋狝 (#14)

*2023-5-16 09:38*

感谢分享

## 回复 by fengyunabc (#15)

*2023-5-16 09:48*

感谢分享！

## 回复 by 袁伟业 (#16)

*2023-5-19 23:19*

>
> [vrolife](https://bbs.kanxue.com/user-978503.htm)
>
>  别开玩笑了，还是有方法能检测到这种类型的内存读写的，还不需要任何特殊权限。
>
>

有什么好办法对抗这种驱动读写吗？

## 回复 by vrolife (#17)

*2023-5-20 18:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  袁伟业](https://bbs.kanxue.com/user-751863.htm)
>
>  有什么好办法对抗这种驱动读写吗？
>
>

这是秘密

## 回复 by FraMeQ (#18)

*2023-5-22 16:39*

直接内核读写![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by 珍惜Any (#19)

*2024-1-8 16:00*

很好的帖子 ， 内核里面做读写确实可以逃逸mincore ，但是crc咋办 ![image](https://bbs.kanxue.com/view/img/face/85.gif)

## 回复 by huangjw (#20)

*2025-11-29 12:43*

学习到了。

楼主的发的几个文章都写的挺好的，思路和用到的技术，引用到逆向分析都有很大的帮助。 都没评优，版主要给个吧。
