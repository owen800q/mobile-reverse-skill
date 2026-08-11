---
title: '[原创] 不碰/proc/pid/maps拿到目标App地址分布思路分享'
url: https://bbs.kanxue.com/thread-284041.htm
tid: 284041
author: vrolife
date: '2024-10-20'
tags: [Android安全, 原创, 程序开发, HOOK注入]
crawled_at: '2026-08-11T08:44:33+00:00'
replies: 29
---

禁止将此文章提及的技术和代码用于违法违规用途, 违者后果自负.

安卓 App 跨进程折腾时, 有一个经常遇到的需求就是要拿到目标 App 的地址布局, 用于远程内存读写或者用于调用相关函数实现注入和执行等等.

要实现这个需求, 通常的做法是读取 /proc/pid/maps 这个文件描述了进程的内存地址布局. 但是在一些特殊情况下, 我们没法直接访问这个文件, 具体不细说.

这里介绍一个那么不访问 /proc/pid/maps 拿到目标进程动态连接库地址分布的方法.

简而言之, 就是通过 App 的父进程, 也就是 zygote, 拿到 soinfo 的首地址, 然后直接远程内存读取遍历这个链表达. 这样我们就能拿到所有 so 的首地址和其他相关的信息了. 因为在 soinfo 挖坑风险很大, 所以很少有 App 在soinfo 挖坑, 所以通常可以直接 process_vm_readv.

我们先看 soinfo 的结构, 以安卓 15 为例

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465 | `struct` `soinfo {` `#if defined(__work_around_b_24465209__)` `private``:` `char` `old_name_[SOINFO_NAME_LEN];` `#endif` `public``:` `const` `ElfW(Phdr)* phdr;` `size_t` `phnum;` `#if defined(__work_around_b_24465209__)` `ElfW(Addr) unused0;` `// DO NOT USE, maintained for compatibility.` `#endif` `ElfW(Addr) base;` `size_t` `size;` `#if defined(__work_around_b_24465209__)` `uint32_t unused1;` `// DO NOT USE, maintained for compatibility.` `#endif` `ElfW(Dyn)* dynamic;` `#if defined(__work_around_b_24465209__)` `uint32_t unused2;` `// DO NOT USE, maintained for compatibility` `uint32_t unused3;` `// DO NOT USE, maintained for compatibility` `#endif` `soinfo* next;` `......` `public``:` `link_map link_map_head;` `bool` `constructors_called;` `// When you read a virtual address from the ELF file, add this` `// value to get the corresponding address in the process' address space.` `ElfW(Addr) load_bias;` `#if !defined(__LP64__)` `bool` `has_text_relocations;` `#endif` `bool` `has_DT_SYMBOLIC;` |
|-|-|

只要计算一下就可以拿到 soinfo->next 和 soinfo->load_bias 这两个关键信息了.

首先第一个问题是 soinfo 链表的 head在哪里? 同样以安卓15为例, head 其实是 linker 里的一个静态变量.

| 123 | `static` `uint8_t __libdl_info_buf[``sizeof``(soinfo)] __attribute__((aligned(8)));` `static` `soinfo* __libdl_info = nullptr;` |
|-|-|

虽然我们不方便访问目标进程的 maps 但是我们可以安全访问 zygote 的 maps. 而 App 是从 zygote fork出来的, 继承了一样的地址空间. 所以我们直接读 zygote 的 maps 然后解析 bionic 的 elf 拿到 __libdl_info_buf 地址. 接着根据这个地址在目标 App 进程里直接 process_vm_readv 读取即可.

思路是对的, 但是实践的时候我们会遇到一个很大的问题, 就是在不同的安卓版本中, soinfo 的结构是有较大差异的. 如果不能抹平这个思路就毫无用处了.

这里再介绍一个暴力扫搜 soinfo 成员结构的方法.

首先另起一个检测进程, 在这个检测进程中调用 dl_iterate_phdr 拿到头两个 so 的 一些信息, 主要是

| 123 | `const` `char``* strtab;` `ElfW(Sym)* symtab;` |
|-|-|

因为这两个成员在所有的版本的soinfo中都是相邻的, 所以紧接着在这个检测进程中, 遍历 maps 中每个可读的区域, 直接搜

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179 | `static` `int` `get_strtab_symtab(``struct` `dl_phdr_info* info,` `size_t` `size,` `void``* ptr)` `{` `auto``* data =` `reinterpret_cast``<Data*>(ptr);`   `if` `(data->index != data->target) {` `data->index += 1;` `return` `0;` `// continue` `}`   `#if DEBUG_LOG` `std::cout <<` `"name    "` `<< info->dlpi_name << std::endl;` `#endif`   `ElfW(Dyn)* dynamic{nullptr};` `ElfW(Addr) bias{0};` `bool` `first_phdr{``true``};`   `for``(``size_t` `i = 0; i < info->dlpi_phnum; ++i) {` `if` `(info->dlpi_phdr[i].p_type == PT_LOAD and first_phdr) {` `first_phdr =` `false``;` `bias = info->dlpi_addr - info->dlpi_phdr[i].p_vaddr;` `}` `if` `(info->dlpi_phdr[i].p_type == PT_DYNAMIC) {` `dynamic =` `reinterpret_cast``<ElfW(Dyn)*>(info->dlpi_phdr[i].p_vaddr + bias);` `}` `}`   `for` `(ElfW(Dyn)* d = dynamic; d->d_tag != DT_NULL; ++d) {` `switch``(d->d_tag) {` `case` `DT_SYMTAB:` `data->symtab =` `reinterpret_cast``<ElfW(Sym)*>(bias + d->d_un.d_ptr);` `break``;` `case` `DT_STRTAB:` `data->strtab =` `reinterpret_cast``<``const` `char``*>(bias + d->d_un.d_ptr);` `break``;` `}` `}`   `data->base = info->dlpi_addr;` `data->name = info->dlpi_name;`   `#if DEBUG_LOG` `std::cout <<` `"strtab  "` `<< (``void``*)data->strtab << std::endl;` `std::cout <<` `"symtab  "` `<< (``void``*)data->symtab << std::endl;` `std::cout <<` `"phdr    "` `<< info->dlpi_phdr << std::endl;` `std::cout <<` `"dynamic "` `<< dynamic << std::endl;` `std::cout <<` `"bias    "` `<< (``void``*)bias << std::endl;` `#endif` `return` `1;` `}`   `static` `Data get_soinfo_next_ptr(``size_t` `target)`  `{` `Data data { nullptr, nullptr, target, 0 };`   `dl_iterate_phdr(get_strtab_symtab, &data);`   `FILE``* fp =` `fopen``(``"/proc/self/maps"``,` `"re"``);` `if` `(fp == nullptr) {` `return` `{ 0, 0, 0, 0, 0, {}, 0 };` `}`   `char` `line[BUFSIZ];`   `while``(``fgets``(line,` `sizeof``(line), fp) != nullptr) {` `uintptr_t` `begin;` `uintptr_t` `end;` `char` `r,w;`   `if` `(``sscanf``(line,` `"%"` `SCNxPTR` `"-%"` `SCNxPTR` `" %c%c"``, &begin, &end, &r, &w) == 4) {` `if` `(r ==` `'r'``) {` `void``* ptr = memmem(``reinterpret_cast``<``void``*>(begin), end - begin, &data,` `sizeof``(``void``*) * 2);` `if` `(ptr != nullptr and ptr != &data) {` `#if DEBUG_LOG && 0` `printf``(``"%s"``, line);` `for` `(``int` `i = 0; i < 8; ++i) {` `std::cout << (``reinterpret_cast``<``void``**>(ptr)[-i+1]) << std::endl;` `}` `#endif` `data.next_ptr = &``reinterpret_cast``<``void``**>(ptr)[-2];` `break``;` `}` `}` `}` `}` `fclose``(fp);` `return` `data;` `}` |
|-|-|

由此可以拿到两个 soinfo 的所在区域了. 实际上头两个 soinfo 在地址空间中是距离相当远的, 一个在静态数据区, 一个在堆里, 理论上直接根据地址范围在第一个soinfo 直接可以搜到第二个soinfo的首地址. 给出的代码里我是偷懒直接假设 next 成员是在strtab 前面两个指针处两,在较新的版本中这样假设是可以的.

---

# 回复

## 回复 by 逆天而行 (#2)

*2024-10-20 23:48*

拿安卓每个版本的soinfo  ,然后switch 哈哈哈

## 回复 by Thehepta (#3)

*2024-10-21 00:41*

谁来执行这个代码，如果，你是app进程，并没有读取zygote的权限啊，如果是root进程，读哪里都一样，我对你这个思路的使用方式更感兴趣

## 回复 by 你瞒我瞒 (#4)

*2024-10-21 09:31*

"只要计算一下就可以拿到 soinfo->next 和 soinfo->load_bias 这两个关键信息了",小白懵了，这个具体是怎么计算的，可以给个例子嘛

## 回复 by 莫灰灰 (#5)

*2024-10-21 10:42*

全版本适配及稳定性是个大问题啊

## 回复 by Amun (#6)

*2024-10-21 10:58*

solist 是个坑，不如这样

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152 | `#include <linux/module.h>``#include <linux/sched.h> /* For task_struct */``#include <linux/pid.h>   /* For find_get_pid */``#include <linux/mm.h>    /* For mm_struct and vm_area_struct */` `void` `print_memory_maps(``struct` `task_struct *task)``{``struct` `mm_struct *mm;``struct` `vm_area_struct *vma;` `if` `(!task \|\| !task->mm)``return``;` `mm = task->mm;` `down_read(&mm->mmap_sem);` `// Lock the memory map``for` `(vma = mm->mmap; vma; vma = vma->vm_next) {``printk(KERN_INFO` `"Address: %lx-%lx, Flags: %08lx\n"``,``(unsigned` `long``)vma->vm_start,``(unsigned` `long``)vma->vm_end,``(unsigned` `long``)vma->vm_flags);``}``up_read(&mm->mmap_sem);` `// Unlock the memory map``}` `static` `int` `__init my_module_init(``void``)``{``struct` `pid *pid;``struct` `task_struct *task;` `pid = find_get_pid(1234);` `// Replace 1234 with the target PID``if` `(pid) {``task = pid_task(pid, PIDTYPE_PID);``if` `(task) {``print_memory_maps(task);``put_task_struct(task);``}``put_pid(pid);``}` `return` `0;``}` `static` `void` `__exit my_module_exit(``void``)``{``// Cleanup code here``}` `module_init(my_module_init);``module_exit(my_module_exit);` `MODULE_LICENSE(``"GPL"``);` |
|-|-|

## 回复 by Amun (#7)

*2024-10-21 11:05*

正向开发没必要踩这个坑。逆向开发有 root 怎么样都行。

## 回复 by vrolife (#8)

*2024-10-21 12:12*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Thehepta](https://bbs.kanxue.com/user-767217.htm)
>
>  谁来执行这个代码，如果，你是app进程，并没有读取zygote的权限啊，如果是root进程，读哪里都一样，我对你这个思路的使用方式更感兴趣
>
>

主要是这样过inotify方便一点

## 回复 by vrolife (#9)

*2024-10-21 12:14*

>
> [Amun](https://bbs.kanxue.com/user-850401.htm)
>
>  solist 是个坑，不如这样
> ```C
> #include
> #include /* For task_struct */
> #include /* For find_get_pid * ...
>
>

这样遇到不同的内核版本也完蛋, 只能弄payload module 我试过这个, 很累

## 回复 by vrolife (#10)

*2024-10-21 12:15*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  "只要计算一下就可以拿到 soinfo->next 和 soinfo->load_bias 这两个关键信息了",小白懵了，这个具体是怎么计算的，可以给个例子嘛
>
>

你可以不算的, 代码里的做法就是暴力搜这两个成员的偏移量

## 回复 by mudebug (#11)

*2024-10-21 12:36*

感谢大佬分享技术

## 回复 by blackr0ck (#12)

*2024-10-21 16:54*

可是这样只能过读maps的检测，获取到地址后vmread读内存还是会被inotify mem检测吧

## 回复 by Lnju (#13)

*2024-10-21 18:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_fycbgpri](https://bbs.kanxue.com/user-980456.htm)
>
>  可是这样只能过读maps的检测，获取到地址后vmread读内存还是会被inotify mem检测吧
>
>

inotify 是针对文件操作的 vmread读内存不会触发的

## 回复 by 你瞒我瞒 (#14)

*2024-10-22 11:08*

>
> [vrolife](https://bbs.kanxue.com/user-978503.htm)
>
>  你可以不算的, 代码里的做法就是暴力搜这两个成员的偏移量
>
>

感谢大佬的回答，上面是暴力搜索，其实我小白更想知道，如果要自己去算，针对某个版本的代码去算，应该怎么算，这个算的案例想学习，之前看到别人写好的偏移量，看起来就是个魔数，一脸懵。

## 回复 by vrolife (#15)

*2024-10-22 11:17*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  感谢大佬的回答，上面是暴力搜索，其实我小白更想知道，如果要自己去算，针对某个版本的代码去算，应该怎么算，这个算的案例想学习，之前看到别人写好的偏移量，看起来就是个魔数，一脸懵。
>
>

可以手动算, 根据成员大小和对齐一个个累加起来就能得到偏移量, 这主要涉及到c语言结构体和平台对齐规则相关的知识. 但是这样很累. 一般实践中, 都是拷结构体出来编译, 或者直接编译整套源码加自己的代码, 写点代码用offsetof直接取偏移量, 导出来用. 编译的时候注意一些宏, 因为宏可能会影响结构体的最终结构. 比如soinfo里的work_around宏.

## 回复 by blackr0ck (#16)

*2024-10-22 11:54*

>
> [Lnju](https://bbs.kanxue.com/user-661065.htm)
>
>  inotify 是针对文件操作的 vmread读内存不会触发的
>
>

非内核的外部读写访问/proc/pid/mem有痕迹

## 回复 by vrolife (#17)

*2024-10-22 12:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_fycbgpri](https://bbs.kanxue.com/user-980456.htm)
>
>
>
>
>
>
>
>  Lnju
>
>
>
>  inotify 是针对文件操作的 vmread读内存不会触发的
>
>  非内核的外部读写访问/proc/pid/mem有痕迹
>
>

process_vm_readv这是个系统调用, 不通过/proc/pid/mem的

## 回复 by 养只猫不好么 (#18)

*2024-10-22 13:17*

感谢分享

## 回复 by blackr0ck (#19)

*2024-10-22 16:17*

>
> [vrolife](https://bbs.kanxue.com/user-978503.htm)
>
>  process_vm_readv这是个系统调用, 不通过/proc/pid/mem的
>
>

https://pshocker.github.io/2022/05/08/Android%E5%86%85%E5%AD%98%E8%AF%BB%E5%86%99%E6%A3%80%E6%B5%8B-inotify/ 在这个例子里似乎是能检测到的

## 回复 by vrolife (#20)

*2024-10-22 16:43*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_fycbgpri](https://bbs.kanxue.com/user-980456.htm)
>
>  https://pshocker.github.io/2022/05/08/Android%E5%86%85%E5%AD%98%E8%AF%BB%E5%86%99%E6%A3%80%E6%B5%8B- ...
>
>

这个帖子是用inotify检测/proc/pid/mem读写, 但是process_vm_readv不是通过/proc/pid/mem实现的. process_vm_readv是内核的一个syscall, inotify是检测不到的. https://elixir.bootlin.com/linux/v6.1.81/source/include/linux/syscalls.h#L981

## 回复 by blackr0ck (#21)

*2024-10-22 16:56*

>
> [vrolife](https://bbs.kanxue.com/user-978503.htm)
>
>  这个帖子是用inotify检测/proc/pid/mem读写, 但是process_vm_readv不是通过/proc/pid/mem实现的. process_vm_readv是内核的一个syscal ...
>
>

他最后说的vm_read也可以，不过我刚才试了一下用的shell

\```
inotifyd - /proc/pid/mem
\```

读取内存代码用的

\```
int process_vm_readv_syscall = 270;
int process_vm_writev_syscall = 271;
syscall((iswrite ? process_vm_writev_syscall : process_vm_readv_syscall), __pid,
				   __local_iov, __local_iov_count, __remote_iov, __remote_iov_count, __flags);
\```

好像确实检测不到，不知道是不是程序里的那个inotify不一样。

之前有人说用户态有办法检测vm_read这个读取行为，那他们是咋检测的啊

## 回复 by vrolife (#22)

*2024-10-22 19:39*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_fycbgpri](https://bbs.kanxue.com/user-980456.htm)
>
>  他最后说的vm_read也可以，不过我刚才试了一下用的shell&nbsp;&nbsp;inotifyd&nbsp;-&nbsp;/proc/pid/mem读取内存代码 ...
>
>

inotify 是文件系统通知, 不可能检测到process_vm_readv这个syscall的. 要想检测process_vm_readv, 只有两个办法. 一个是常用的用mmap进行pfn挖坑,然后通过pagemap或者mincore检测. 另一个就不提了.![image](https://bbs.kanxue.com/view/img/face/19.gif)

## 回复 by mb_qvxwrrpg (#23)

*2024-10-23 05:22*

我想问一下 opendir会触发inotify吗 我直接读取 /proc/pid/map_files/呢?

## 回复 by vrolife (#24)

*2024-10-23 12:13*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_qvxwrrpg](https://bbs.kanxue.com/user-1004474.htm)
>
>  我想问一下 opendir会触发inotify吗 我直接读取 /proc/pid/map_files/呢?
>
>

会触发, 但是一些目标app是有一定的宽容度的, 因为很多系统工具也扫/proc

## 回复 by mb_qvxwrrpg (#25)

*2024-10-27 18:30*

除了缺页外还可能怎么进行检测

## 回复 by AunCss (#26)

*2024-10-28 11:17*

这是写驱动接口过检测吗

## 回复 by vrolife (#27)

*2024-10-28 15:24*

>
> [AunCss](https://bbs.kanxue.com/user-828379.htm)
>
>  这是写驱动接口过检测吗
>
>

不是驱动, 驱动搞这个兼容性太差了

## 回复 by mb_xqptnehm (#28)

*2024-12-8 17:17*

debug时那5个偏移的正常。但get_so_base的，总是invalid name。哪里出了问题？要怎么办啊？![image](https://bbs.kanxue.com/view/img/face/006.gif)

## 回复 by mb_xqptnehm (#29)

*2024-12-8 17:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_xqptnehm](https://bbs.kanxue.com/user-978986.htm)
>
>  debug时那5个偏移的正常。但get_so_base的，总是invalid name。哪里出了问题？要怎么办啊？[em_006]
>
>

解决了，我的那个进程不是zygote,就很猎奇

## 回复 by 珍惜Any (#30)

*2024-12-9 11:02*

我觉得有个更好的办法，直接读取proc/self/map_files就行了。
