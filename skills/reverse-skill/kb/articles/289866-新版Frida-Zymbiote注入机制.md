---
title: '[推荐]新版Frida-Zymbiote注入机制'
url: https://bbs.kanxue.com/thread-289866.htm
tid: 289866
author: Yangser
date: '2026-01-25'
tags: [Android安全, 推荐, HOOK注入]
crawled_at: '2026-08-08T10:28:50+00:00'
replies: 180
---

# Frida-Zymbiote注入机制

## 0x00 前言

Frida 17.6.0在Android端的Zygote注入机制上进行了一次值得关注的重构。它展示了一种更加稳定的注入设计思路

传统的ptrace注入方案虽然在功能上强大，但在实际应用中常常面临稳定性挑战：在子进程中残留痕迹容易被检测、与其他工具的兼容性也时有冲突等。而新引入的“zymbiote”机制采用了完全不同的实现路径——通过外部内存操作和轻量级通信，在几乎不留下痕迹的情况下完成了进程监控。

理解这套机制不仅能帮助我们更好地使用新版工具，更重要的是，它为我们思考Android系统层级的动态分析技术提供了新的视角。本文将详细解析zymbiote的技术原理和实现细节

## 0x01 回顾之前

去年我在这篇文章中介绍了spawn模式注入so的实现原理：[spawn模式注入so](https://yuuki.cool/posts/injectso2/)

它的核心思想是先向zygote进程注入一个mon.so，这样它运行在zygote进程，就可以轻而易举的实现对zygote进程中函数的hook，通过hook fork系列函数，在fork触发之后再安装对setArgV0的hook，在setArgV0函数触发时判断是否是目标app，从而确定是否dlopen需要注入的so，现在看来这套设计是有问题的，因为setArgV0函数是用于设置进程名的，在app启动时它会被稳定触发，所以完全可以跳过对fork函数的hook，直接hook setArgV0。其次就是zygote里驻留的so不是很好清理，以及selinux的问题处理的也很粗糙

当然，Frida之前的注入也有这些问题，server一启动，对libc的hook就安装了，这会导致很多app打开就闪退，我在校时吃饭需要用到`完美校园`这个app，经常付钱的时候才想起来刚用过frida，手机还没重启，就会很尴尬

## 0x02 正片

可以看到之前的注入方式(**开源的**，**公开的**)大多都是通过ptrace注入zygote，其中ptrace负责实现远程读写+远程调用，再通过hook监控fork相关的函数实现的，而这次Frida更新，带来了一种新的思路

但是核心逻辑是不变的，仍然需要远程读写+hook，但是这里它两个模块都做了优化

**远程读写：**

当前frida采用直接读写`/proc/<zygote>/mem`的形式进行远程读写(这个操作挂圈好像用的很多)。在我的理解中`/proc/[pid]/mem`是通过文件系统接口暴露的进程虚拟内存空间的直接读写通道，它像一个窗户，窗户内部是进程的完整虚拟地址空间，那么要如何精准的在这块空间里找到我们想要的东西呢？那就需要先去读`/proc/[pid]/maps`，map翻译过来是地图的意思，事实也的确如此，`maps`就像是这块空间的一张地图，通过它就可以定位到我们想要的位置

**hook**

再次回顾一下之前，我们的安装hook是通过运行在zygote进程内部的代码 修改目标函数开始处的指令为跳转指令，从而使运行到该函数时自动跳转到我们自己的hook函数的

frida选择的是setArgV0函数作为触发点，这个函数之前介绍过的，它会在app启动时稳定被调用

| 1 | `void` `android_os_Process_setArgV0(JNIEnv* env, jobject clazz, jstring name)` |
|-|-|

值得注意的是，这是一个JNI函数，对于JNI函数，它在java层就会有一个对应的java函数，那我们直接hook对应的java函数就好了。这个就很熟悉了，直接修改对应java函数的ArtMethod的`entry_point`即可，完全不需要inline hook了，frida就是这样做的，当然对于JNI函数，还有别的hook方法，但是frida在这个注入场景，修改`entry_point`是最简洁的做法

那么hook如何安装呢？回顾刚刚的hook方案，核心是修改目标函数的`entry_point`，而目标函数是系统库里的函数，那他在开机之后，app启动之前，就存在zygote进程的内存里面了。那么我们只需要在zygote的内存里找到目标函数的`entry_point`字段，然后把它的值修改到我们的hook函数的地址就行了，那么现在就需要解决两个问题

1. 如何定位目标函数的`entry_point`并修改
2. 我们的hook函数该如何注入到zygote进程

## 0x03 问题 一

Frida 采用了一个巧妙的方法来定位 `android_os_Process_setArgV0` 对应的 ArtMethod 的 entry_point：

#### step1：找到 JNI 函数的地址

首先，通过解析 `libandroid_runtime.so` 这个ELF 文件，找到 JNI 函数的符号地址：

\```
// src/linux/linux-host-session.vala:986-995
uint64 set_argv0_address = 0;
runtime.enumerate_exports (e => {
    // JNI 函数的 mangled name
    if (e.name == "_Z27android_os_Process_setArgV0P7_JNIEnvP8_jobjectP8_jstring") {
        // 计算运行时地址 = 基址 + 偏移
        set_argv0_address = runtime_entry.base_address + e.address;
        return false;
    }
    return true;
});
\```

这里得到的 `set_argv0_address` 是函数在内存中的实际地址

#### step2：在内存中搜索指向该地址的指针

Frida 通过读取 zygote 进程的堆内存，搜索包含这个地址的位置：

\```
// src/linux/linux-host-session.vala:1007-1027
uint pointer_size = ("/lib64/" in libc_path) ? 8 : 4;

var original_ptr = new uint8[pointer_size];
var replaced_ptr = new uint8[pointer_size];

// 将地址编码为字节数组
(new Buffer (new Bytes.static (original_ptr), ByteOrder.HOST, pointer_size))
    .write_pointer (0, set_argv0_address);
(new Buffer (new Bytes.static (replaced_ptr), ByteOrder.HOST, pointer_size))
    .write_pointer (0, payload_base);

var fd = open_process_memory (pid);

uint64 art_method_slot = 0;
bool already_patched = false;

// 遍历堆内存区域
foreach (var candidate in heap_candidates) {
    var heap = new uint8[candidate.size];
    var n = fd.pread (heap, candidate.base_address);

    // 在堆内存中搜索这个指针值
    void * p = memmem (heap, original_ptr);
    if (p == null) {
        p = memmem (heap, replaced_ptr);
        already_patched = p != null;
    }

    if (p != null) {
        // 找到了，计算 ArtMethod 的 entry_point 字段地址
        art_method_slot = candidate.base_address + ((uint8 *) p - (uint8 *) heap);
        break;
    }
}
\```

这样就拿到了`art_method_slot`的地址，即存储了指向`android_os_Process_setArgV0`地址的字段的地址，接下来通过上面提到的，读写`/proc/<zygote>/mem`来实现修改该字段，但在修改之前，需要备份一下原始指向的函数地址，后面注入成功/失败之后需要unhook，会用到原本的值

那么应该把`art_method_slot`里存储的值改成什么呢？这就该解决第二个问题了

## 0x04 问题 二

传统的做法是通过 ptrace 注入一个 .so 文件到 zygote 进程，hook 函数就在这个 .so 里。但 Frida 的 zymbiote 机制采用了不同的思路：**不注入 .so，而是注入一小段精心设计的机器码（payload）**

这个payload该如何设计我们放到后面再来讨论，目前先解决`该把它放在哪`的问题

payload 应该放在哪里？这个位置需要满足几个条件：

1. **已经具有执行权限**（避免调用 mprotect 修改权限，不然又要ptrace）
2. **有足够的空闲空间**（payload 大约 2KB）
3. **不会破坏原有代码**（不能覆盖正在使用的代码）

Frida 选择了 `libstagefright.so` 的最后一页：

\```
// 遍历 zygote 进程的内存映射
foreach (var entry in entries) {
    if (path.has_suffix ("/libstagefright.so") && "x" in flags) {
        // 选择该库的最后一页作为 payload 注入位置
        payload_base = iter.end_address - Gum.query_page_size ();
    }
}
\```

选择`libstagefright.so`的原因很简单，因为它的最后一页往往有未使用的空间，足够我们写入payload

#### payload的设计

先看一下frida的zymbiote吧，源代码 [zymbiote.c](https://github.com/frida/frida-core/blob/8c62357b94908f46fbcdae76942c3ef1c1989160/src/linux/helpers/zymbiote.c)

| 12345678910111213141516171819202122 | `struct` `_FridaApi``{``char` `name[64];` `// MAGIC` `void`    `** art_method_slot;` `// ArtMethod 的 entry_point 地址``void`    `(* original_set_argv0)();` `// 原始 JNI 函数地址` `// libc 函数指针``int`     `(* socket) (...);``int`     `(* connect) (...);``int` `*   (* __errno) (``void``);``pid_t   (* getpid) (``void``);``pid_t   (* getppid) (``void``);``ssize_t (* sendmsg) (...);``ssize_t (* recv) (...);``int`     `(* close) (``int` `fd);``int`     `(*` `raise``) (``int` `sig);``};` `static` `volatile` `const` `FridaApi frida = {``.name =` `"/frida-zymbiote-00000000000000000000000000000000"``,``};` |
|-|-|

这里定义了一些libc里的函数，运行时会被用到。但是由于这段代码并不是像linker加载so那样被加载进内存的，所以它缺少`重定位`步骤，后续需要自己手动重定位

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374757677787980818283848586878889909192939495 | `__attribute__ ((section (``".text.entrypoint"``)))``__attribute__ ((visibility (``"default"``)))``int``frida_zymbiote_replacement_set_argv0 (JNIEnv * env, jobject clazz, jstring name)``{``bool` `success =` `false``;``int` `fd = -1;``struct` `sockaddr_un addr;``socklen_t addrlen;``unsigned` `int` `name_len;` `// 1. 立即恢复原始 entry_point（避免重复触发）``*frida.art_method_slot = frida.original_set_argv0;` `// 2. 调用原始函数（保证 app 正常运行）``frida.original_set_argv0 (env, clazz, name);` `// 3. 创建 Unix socket``fd = frida.socket (AF_UNIX, SOCK_STREAM, 0);``if` `(fd == -1)``goto` `beach;` `// 4. 构造 socket 地址（abstract namespace）``addr.sun_family = AF_UNIX;``addr.sun_path[0] =` `'\0'``;` `// abstract socket 标志` `name_len = 0;``for` `(unsigned` `int` `i = 0; i !=` `sizeof` `(frida.name); i++)``{``if` `(frida.name[i] ==` `'\0'``)``break``;``if` `(1u + i >=` `sizeof` `(addr.sun_path))``break``;``addr.sun_path[1u + i] = frida.name[i];``name_len++;``}` `addrlen = (socklen_t) (offsetof (``struct` `sockaddr_un, sun_path) + 1u + name_len);` `// 5. 连接 Frida Server``if` `(frida_connect (fd, (``const` `struct` `sockaddr *) &addr, addrlen) == -1)``goto` `beach;` `// 6. 发送进程信息``{``const` `char` `* name_utf8;``struct``{``uint32_t pid;``uint32_t ppid;``uint32_t package_name_len;``} header;``struct` `iovec iov[2];` `name_utf8 = (*env)->GetStringUTFChars (env, name, NULL);` `header.pid = frida.getpid ();``header.ppid = frida.getppid ();``header.package_name_len = 0;``while` `(name_utf8[header.package_name_len] !=` `'\0'``)``header.package_name_len++;` `iov[0].iov_base = &header;``iov[0].iov_len =` `sizeof` `(header);``iov[1].iov_base = (``void` `*) name_utf8;``iov[1].iov_len = header.package_name_len;` `if` `(!frida_sendmsg_all (fd, iov, 2, MSG_NOSIGNAL))``goto` `beach;` `(*env)->ReleaseStringUTFChars (env, name, name_utf8);``}` `// 7. 等待 Frida Server 确认``{``uint8_t rx;``if` `(frida_recv (fd, &rx, 1, 0) != 1)``goto` `beach;``}` `success =` `true``;` `beach:``if` `(fd != -1)``frida.close (fd);` `// 8. 暂停进程``if` `(success)``{``__attribute__ ((musttail))``return` `frida_stop_and_return (env, clazz, name);``}` `return` `0;``}` |
|-|-|

这个就是android_os_Process_setArgV0的hook函数，流程总结下来就是 恢复 hook → 调用原始函数 → 连接 Server → 发送信息 → 等待确认 → 暂停进程

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455 | `__attribute__ ((``naked``,` `noinline``))``static` `int``frida_stop_and_return (JNIEnv * env, jobject clazz, jstring name)``{``#if defined (__aarch64__)``__asm__ __volatile__ (``"mov    w0, #%[sig]\n"`           `// 参数：SIGSTOP``"adrp   x16, frida\n"`            `// 获取 frida 地址（位置无关）``"add    x16, x16, :lo12:frida\n"``"ldr    x16, [x16, %[raise_off]]\n"` `// 读取 raise 函数指针``"br     x16\n"`                   `// 跳转（不会返回）``:``: [sig]` `"i"` `(SIGSTOP),``[raise_off]` `"i"` `(offsetof (FridaApi,` `raise``))``:` `"x16"``,` `"memory"``);``#elif defined (__arm__)``__asm__ __volatile__ (``"mov    r0, %[sig]\n"``"adr    r12, frida\n"``"ldr    r12, [r12, %[raise_off]]\n"``"bx     r12\n"``:``: [sig]` `"i"` `(SIGSTOP),``[raise_off]` `"i"` `(offsetof (FridaApi,` `raise``))``:` `"r12"``,` `"memory"``);``#elif defined (__x86_64__)``__asm__ __volatile__ (``"mov    $%c[sig], %%edi\n"``"leaq   frida(%%rip), %%r11\n"``"movq   %c[raise_off](%%r11), %%r11\n"``"jmp    *%%r11\n"``:``: [sig]` `"i"` `(SIGSTOP),``[raise_off]` `"i"` `(offsetof (FridaApi,` `raise``))``:` `"r11"``,` `"rdi"``,` `"memory"``);``#elif defined (__i386__)``__asm__ __volatile__ (``"movl   $%c[sig], 4(%%esp)\n"``"call   1f\n"``"1: pop %%eax\n"``"addl   $(frida-1b), %%eax\n"``"movl   %c[raise_off](%%eax), %%eax\n"``"jmp    *%%eax\n"``:``: [sig]` `"i"` `(SIGSTOP),``[raise_off]` `"i"` `(offsetof (FridaApi,` `raise``))``:` `"eax"``,` `"memory"``);``#else``# error Unsupported architecture``#endif``}` |
|-|-|

这个是暂停函数，用于发送`SIGSTOP`暂停进程。其他的辅助函数就不介绍了，感兴趣的自己去看

#### payload的重定位

前面提到，`_FridaApi` 结构体里定义了一些 libc 函数指针，但这些指针在编译时都是空的。因为 payload 是纯机器码，不会经过动态链接器的重定位过程，所以需要 Frida Server 手动填充这些函数地址。

**重定位过程：**

\```
// src/linux/linux-host-session.vala

var blob = (pointer_size == 8)
    ? Frida.Data.Android.get_zymbiote_arm64_bin_blob ()
    : Frida.Data.Android.get_zymbiote_arm_bin_blob ();

// 2. 在payload中通过MAGIC查找数据区
void * p = memmem (payload_template, "/frida-zymbiote-00000000000000000000000000000000".data);
size_t data_offset = (uint8 *) p - (uint8 *) payload_template;

// 3. 创建可写的 payload 副本
var payload = new Buffer (new Bytes (payload_template), ByteOrder.HOST, pointer_size);

// 4. 填充数据区
size_t cursor = data_offset;

// 写入 socket 名称
payload.write_string (cursor, server_name);  // "/frida-zymbiote-<UUID>"
cursor += 64;

// 写入 art_method_slot 地址
payload.write_pointer (cursor, art_method_slot);
cursor += pointer_size;

// 写入原始 setArgV0 函数地址
payload.write_pointer (cursor, set_argv0_address);
cursor += pointer_size;

// 5. 填充 libc 函数地址
string[] wanted = {
    "socket",
    "connect",
    "__errno",
    "getpid",
    "getppid",
    "sendmsg",
    "recv",
    "close",
    "raise",
};

// 从 libc.so 中查找这些函数的地址
var addrs = new uint64[wanted.length];
libc.enumerate_exports (e => {
    if (index_of.has_key (e.name)) {
        int idx = index_of[e.name];
        addrs[idx] = libc_entry.base_address + e.address;
        pending--;
    }
    return pending != 0;
});

// 将函数地址写入 payload
for (int i = 0; i != addrs.length; i++) {
    payload.write_pointer (cursor, addrs[i]);
    cursor += pointer_size;
}
\```

#### payload的注入

填充完数据后，就可以注入了：

\```
// 通过 /proc/[pid]/mem 将 payload 写入目标位置
fd.pwrite (payload.bytes, payload_base);

// 修改 ArtMethod 的 entry_point，使其指向 payload
fd.pwrite (replaced_ptr, art_method_slot);
\```

这里直接指向payload是因为链接脚本将hook函数所在的段放在了payload的起始位置（偏移 0）。通过在函数定义时指定section，再配合链接脚本控制段的顺序，就能确保hook函数位于payload开头。

| 1 | `__attribute__ ((section (``".text.entrypoint"``)))` |
|-|-|

| 123456789101112131415 | `SECTIONS {``. = 0;` `// 从地址 0 开始` `.payload : ALIGN(4096)``{``KEEP(*(.text.entrypoint))` `// 函数放在最前面``*(.text*)` `// 其他代码``*(.rodata*)` `// 只读数据``}` `// 其他段（会被 objcopy 去掉）``.dynstr : { *(.dynstr) }``.dynsym : { *(.dynsym) }``// ...``}` |
|-|-|

至此就完成了payload的注入与`android_os_Process_setArgV0`函数的hook

## 0x05 半小结

做完上面的工作，`setArgV0`就被替换了。在app启动之后，`setArgV0`被调用，然后走到`frida_zymbiote_replacement_set_argv0`里，执行里面的逻辑。这个函数上面介绍过了，Frida并没有选择直接在这里进行注入，而是仅仅获取了这个“时机”，拿到了这个时机之后，就启动Socket与外部通信，在外部通过ptrace把`frida-gadget.so`注入进目标进程，注入成功后再清理掉zygote进程里`libandroid_runtime.so`最后一页的数据，以此恢复对zygote的污染，从而避免了之前那种一启动server，一堆加壳软件就打不开的尴尬问题

## 0x06 实践

经过之前的学习，可以发现这种注入方式和之前的相比简洁了很多，核心代码也没有多少，而且只做注入的话，还有优化的空间，所以直接开抄，但是明天要上班了，我抄不动了

---

# 回复

## 回复 by Yangser (#2)

*2026-1-25 21:23*

看雪的markdown解析器好像不支持vala的，，，

## 回复 by Imxz (#3)

*2026-1-25 21:24*

tql

## 回复 by mb_asiwnxyv (#4)

*2026-1-25 21:35*

感谢分享

## 回复 by 酒仙桥之虎 (#5)

*2026-1-25 21:40*

666

## 回复 by MaYil (#6)

*2026-1-25 22:37*

感谢分享

## 回复 by wx_huhu_859 (#7)

*2026-1-25 22:39*

11

## 回复 by Kill_Log (#8)

*2026-1-25 23:00*

6666

## 回复 by Gryffindoss (#9)

*2026-1-25 23:18*

666

## 回复 by mb_ysegxpmv (#10)

*2026-1-26 00:02*

感谢分享

## 回复 by wx_Huber Barrientos (#11)

*2026-1-26 00:30*

为你点赞！

## 回复 by jw8888 (#12)

*2026-1-26 01:21*

6666666

## 回复 by XCicada (#13)

*2026-1-26 03:40*

为你点赞！

## 回复 by 黑屏 (#14)

*2026-1-26 08:00*

666

## 回复 by wx_插曲 (#15)

*2026-1-26 09:16*

66

## 回复 by wx_范迪塞尔 (#16)

*2026-1-26 09:29*

6666

## 回复 by GEKEZYX (#17)

*2026-1-26 09:45*

6666

## 回复 by mb_hxjodkds (#18)

*2026-1-26 09:51*

犇

## 回复 by hekes (#19)

*2026-1-26 09:53*

看看

## 回复 by fei3ei (#20)

*2026-1-26 10:07*

学习

## 回复 by 蜕无痕 (#21)

*2026-1-26 10:26*

大侠强啊

## 回复 by Yangser (#22)

*2026-1-26 10:57*

>
> [蜕无痕](https://bbs.kanxue.com/user-813639.htm)
>
>  大侠强啊
>
>

还是造哥更吊

## 回复 by wx_小白_266 (#23)

*2026-1-26 11:02*

666

## 回复 by mb_cbgtaveo (#24)

*2026-1-26 11:48*

66666666666

## 回复 by wx_霿凇 (#25)

*2026-1-26 12:07*

666

## 回复 by mb_roiscepd (#26)

*2026-1-26 12:10*

666

## 回复 by mb_ldbucrik (#27)

*2026-1-26 12:20*

向大佬学习

## 回复 by 云霄IT (#28)

*2026-1-26 12:55*

66

## 回复 by kingking888 (#29)

*2026-1-26 13:55*

非常 666

## 回复 by jdong (#30)

*2026-1-26 14:05*

66666666666

## 回复 by uni7corn (#31)

*2026-1-26 15:09*

感谢分享。

## 回复 by 金罡 (#32)

*2026-1-26 15:21*

不错！！！

## 回复 by mb_bvwbboty (#33)

*2026-1-26 15:37*

tql

## 回复 by Yangser (#34)

*2026-1-26 15:46*

>
> [金罡](https://bbs.kanxue.com/user-271698.htm)
>
>  不错！！！
>
>

向金罡大佬学习

## 回复 by 柳哈辣子 (#35)

*2026-1-26 16:00*

666

## 回复 by mb_pesxllvn (#36)

*2026-1-26 16:15*

666

## 回复 by 夜惜风雨 (#37)

*2026-1-26 17:48*

6666666666666

## 回复 by mb_qimctavn (#38)

*2026-1-26 18:33*

6

## 回复 by dxasqw (#39)

*2026-1-26 19:04*

666

## 回复 by Superoot (#40)

*2026-1-26 19:11*

66666666666666

## 回复 by 寻梦之璐 (#41)

*2026-1-26 20:32*

11

## 回复 by mb_xdqrjlmu (#42)

*2026-1-26 23:39*

感谢分享

## 回复 by pigsub (#43)

*2026-1-26 23:45*

666

## 回复 by SomeMx (#44)

*2026-1-27 06:11*

学习

## 回复 by huangjw (#45)

*2026-1-27 09:07*

看看先

## 回复 by wingsevil (#46)

*2026-1-27 10:32*

感谢分享

## 回复 by 带带弟弟吧 (#47)

*2026-1-27 11:21*

1

## 回复 by mb_ejwssbrk (#48)

*2026-1-27 15:55*

感谢感谢

## 回复 by Zepp7289 (#49)

*2026-1-27 19:47*

向大佬学习

## 回复 by koflfy (#50)

*2026-1-27 23:24*

mark，不错。

## 回复 by 我心向山 (#51)

*2026-1-28 01:10*

111

## 回复 by 逆向小呆呆 (#52)

*2026-1-28 02:10*

56666

## 回复 by 唱过阡陌 (#53)

*2026-1-28 04:24*

66

## 回复 by 小尘0000 (#54)

*2026-1-28 10:25*

666

## 回复 by 29o (#55)

*2026-1-28 11:04*

66

## 回复 by Thehepta (#56)

*2026-1-28 16:31*

1

## 回复 by xiaoc996 (#57)

*2026-1-28 16:41*

6666

## 回复 by k4y0z (#58)

*2026-1-28 17:29*

666

## 回复 by mb_vanjeoof (#59)

*2026-1-28 18:08*

你好，请问注入payload的时机是什么？如何保证注入时机比app代码早？

## 回复 by Yangser (#60)

*2026-1-28 18:09*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_vanjeoof](https://bbs.kanxue.com/user-1001929.htm)
>
>  你好，请问注入payload的时机是什么？如何保证注入时机比app代码早？
>
>

payload是注入进zygote进程的，app fork会继承zygote的内存

## 回复 by 9527vv7 (#61)

*2026-1-29 14:22*

6

## 回复 by mb_xgoaxxei (#62)

*2026-1-29 17:40*

感谢分享

## 回复 by 大魔头 (#63)

*2026-1-30 10:18*

![image](https://bbs.kanxue.com/view/img/face/056.gif)

## 回复 by 1sfans (#64)

*2026-1-30 11:45*

666

## 回复 by 肉蚌葱鸡 (#65)

*2026-1-30 18:36*

66666

## 回复 by 阳光宝贝 (#66)

*2026-1-31 00:06*

666

## 回复 by 阳光宝贝 (#67)

*2026-1-31 00:06*

666

## 回复 by mb_nbhpszaj (#68)

*2026-1-31 00:37*

123

## 回复 by 师太,借个吻 (#69)

*2026-1-31 03:31*

666

## 回复 by 墨点 (#70)

*2026-1-31 11:46*

666

## 回复 by wx_听书人 (#71)

*2026-1-31 13:09*

666

## 回复 by yikuaiyingbi (#72)

*2026-1-31 13:16*

66

## 回复 by zhao3261 (#73)

*2026-1-31 14:17*

看看

## 回复 by 我是小奥 (#74)

*2026-1-31 16:39*

666

## 回复 by mb_euhyowpw (#75)

*2026-2-1 16:05*

666

## 回复 by 财神爷999 (#76)

*2026-2-1 17:31*

6666

## 回复 by mb_nntqdxvc (#77)

*2026-2-2 00:12*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by 烬奇小云 (#78)

*2026-2-2 18:27*

666

## 回复 by l140w4n9 (#79)

*2026-2-2 20:42*

66666

## 回复 by wx_飞_847 (#80)

*2026-2-4 10:44*

6666

## 回复 by mb_xxezghuh (#81)

*2026-2-4 12:07*

学习

## 回复 by mb_uvyukvot (#82)

*2026-2-5 17:53*

666

## 回复 by didiid (#83)

*2026-2-6 11:38*

666

## 回复 by 我不是卷王 (#84)

*2026-2-6 11:43*

6666

## 回复 by 我不是卷王 (#85)

*2026-2-6 11:43*

666

## 回复 by 丶咖啡猫丶 (#86)

*2026-2-6 12:00*

666

## 回复 by geekbyte (#87)

*2026-2-6 13:57*

666

## 回复 by fjqisba (#88)

*2026-2-6 14:03*

菜鸟学习学习

## 回复 by mb_fidppcok (#89)

*2026-2-9 10:34*

牛。很了不起的技术。

## 回复 by mb_zknspvuz (#90)

*2026-2-9 11:31*

学习下

## 回复 by 无名之辈 (#91)

*2026-2-10 10:30*

感谢分享

## 回复 by mb_jhohnbzu (#92)

*2026-2-10 15:56*

666

## 回复 by 飆汗吉米 (#93)

*2026-2-10 16:54*

666

## 回复 by 司徒废人 (#94)

*2026-2-10 18:25*

向大佬学习

## 回复 by afishlong (#95)

*2026-2-13 23:39*

6666

## 回复 by baichisi (#96)

*2026-2-14 10:05*

666

## 回复 by merryfish (#97)

*2026-2-16 09:31*

thanks

## 回复 by qig (#98)

*2026-2-18 10:31*

为你点赞！

## 回复 by ExpertSunny (#99)

*2026-2-19 21:14*

66666666

## 回复 by Ankeys (#100)

*2026-2-22 11:12*

666

## 回复 by AYHMO (#101)

*2026-2-23 15:12*

6666

## 回复 by tmi (#102)

*2026-2-24 09:26*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by jyotidwi (#103)

*2026-2-24 23:44*

666

## 回复 by lotus* (#104)

*2026-2-25 10:19*

6666

## 回复 by Mr.He (#105)

*2026-2-25 10:46*

666

## 回复 by mb_pivwkzjg (#106)

*2026-2-26 11:49*

66666

## 回复 by amwait (#107)

*2026-2-27 10:23*

1111

## 回复 by mb_ktazlrdl (#108)

*2026-2-27 10:28*

666

## 回复 by yyyyy——— (#109)

*2026-2-27 14:03*

666

## 回复 by mb_jnmxfjku (#110)

*2026-2-28 13:55*

666

## 回复 by mb_hfpmtthz (#111)

*2026-2-28 14:42*

666

## 回复 by S_602205 (#112)

*2026-2-28 17:29*

666

## 回复 by 白红 (#113)

*2026-2-28 18:02*

666

## 回复 by axpol (#114)

*2026-2-28 18:43*

666

## 回复 by Whoami默 (#115)

*2026-2-28 18:47*

666

## 回复 by mb_tjqabdvq (#116)

*2026-2-28 21:21*

666![image](https://bbs.kanxue.com/view/img/face/086.gif)

## 回复 by xiaocaiji123 (#117)

*2026-3-2 10:35*

6666

## 回复 by 恋~ (#118)

*2026-3-3 09:09*

666666666666

## 回复 by 九黎 (#119)

*2026-3-3 09:21*

tql

## 回复 by xeiyu (#120)

*2026-3-3 12:34*

666

## 回复 by mb_xbsbbedj (#121)

*2026-3-3 19:39*

666

## 回复 by Arsylk (#122)

*2026-3-8 18:14*

66

## 回复 by guardia (#123)

*2026-3-9 16:20*

666

## 回复 by jaefern (#124)

*2026-3-9 16:40*

666

## 回复 by 3uiad (#125)

*2026-3-9 17:56*

666

## 回复 by God_li (#126)

*2026-3-9 19:27*

666

## 回复 by 飞猫的世界 (#127)

*2026-3-10 23:31*

666

## 回复 by 残枫 (#128)

*2026-3-12 10:50*

学习学习

## 回复 by mb_pmwkabcl (#129)

*2026-3-12 14:07*

666

## 回复 by wx_wyx (#130)

*2026-3-12 14:32*

tql

## 回复 by mb_bpqnxoxe (#131)

*2026-3-12 16:28*

666666

## 回复 by mb_lovhtcda (#132)

*2026-3-15 01:50*

666

## 回复 by chenwitch (#133)

*2026-3-18 19:19*

666

## 回复 by mb_cmdpqcqn (#134)

*2026-4-2 16:47*

1

## 回复 by mb_ecyhqrqd (#135)

*2026-4-7 12:36*

6666

## 回复 by Xx_gg (#136)

*2026-4-8 10:12*

6666

## 回复 by wx_weggfkdk (#137)

*2026-4-8 11:36*

666

## 回复 by mb_uktygsmq (#138)

*2026-4-9 17:29*

666

## 回复 by mb_halkmcvq (#139)

*2026-4-11 15:13*

666

## 回复 by git_24708cy3ber (#140)

*2026-4-13 09:14*

666

## 回复 by pan_634488 (#141)

*2026-4-17 16:27*

666

## 回复 by @=llfly (#142)

*2026-4-17 17:11*

666 学习

## 回复 by 桐人dx (#143)

*2026-4-22 22:49*

666

## 回复 by mb_ugnawvja (#144)

*2026-4-23 17:23*

学习

## 回复 by 梦菜菜 (#145)

*2026-4-28 11:11*

学习一下方法

## 回复 by DriftCode (#146)

*2026-4-28 14:39*

学习

## 回复 by mb_weufbroc (#147)

*2026-5-5 20:42*

这个是模块吗

## 回复 by 袁伟业 (#148)

*2026-5-5 21:29*

66

## 回复 by 需要渗透高手 (#149)

*2026-5-5 21:35*

点个赞

## 回复 by 需要渗透高手 (#150)

*2026-5-5 21:35*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>  还是造哥更吊
>

又吊又强

## 回复 by 亿万星辰 (#151)

*2026-5-6 00:26*

学习

## 回复 by mb_xflcgdik (#152)

*2026-5-8 09:34*

666

## 回复 by mb_lzotvdxv (#153)

*2026-5-9 19:32*

请在 Telegram 上联系我，我有一个重要的付费任务要交给你。 Telegram：@dlopenext

## 回复 by lokmal1995 (#154)

*2026-5-14 14:58*

good

## 回复 by lokmal1995 (#155)

*2026-5-14 14:58*

good

## 回复 by wx_Oh.漏 (#156)

*2026-5-14 15:18*

44444

## 回复 by 红皮西瓜 (#157)

*2026-5-14 15:52*

tql

## 回复 by byhk (#158)

*2026-5-19 10:40*

感谢分享

## 回复 by hanjiefang (#159)

*2026-5-27 10:13*

学习

## 回复 by talentmu (#160)

*2026-5-31 09:39*

学习

## 回复 by blx2024 (#161)

*2026-6-1 16:16*

666

## 回复 by mb_jegknedl (#162)

*2026-6-12 01:50*

这是什么？

## 回复 by Yangser (#163)

*2026-6-12 09:28*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_jegknedl](https://bbs.kanxue.com/user-953867.htm)
>  这是什么？
>
>

好吃的

## 回复 by mb_rbixrkdo (#164)

*2026-6-12 10:13*

学习一下啊

## 回复 by 温泉划水鱼 (#165)

*2026-6-12 10:52*

学习

## 回复 by wx_无法回头的伪装 (#166)

*2026-6-12 17:55*

6666

## 回复 by mb_dcjxxhsk (#167)

*2026-6-12 20:34*

666

## 回复 by mb_paopxhtx (#168)

*2026-6-13 20:30*

61661

## 回复 by emgelu48 (#169)

*2026-6-17 03:10*

nice

## 回复 by mb_ezmrnfsu (#170)

*2026-6-18 22:26*

666

## 回复 by zy (#171)

*2026-6-18 23:40*

666

## 回复 by 木魚· (#172)

*2026-7-1 12:05*

66666666

## 回复 by nuomida (#173)

*2026-7-1 13:42*

6666

## 回复 by mb_qqihqaoo (#174)

*2026-7-5 16:51*

6666666666666

## 回复 by git_84461osscv (#175)

*2026-7-5 21:07*

谢谢分享

## 回复 by shuaiaimei (#176)

*2026-7-8 19:21*

6666看下

## 回复 by mb_rooofjxx (#177)

*2026-7-20 14:56*

6666

## 回复 by Vengeance (#178)

*2026-7-22 17:48*

666

## 回复 by 龙飞雪 (#179)

*2026-7-24 16:49*

学习了

## 回复 by 龙飞雪 (#180)

*2026-7-24 16:49*

学习了

## 回复 by 补丁布丁 (#181)

*2026-7-26 01:58*

支持 支持
