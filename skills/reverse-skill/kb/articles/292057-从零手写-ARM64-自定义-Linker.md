---
title: '[原创]从零手写 ARM64 自定义 Linker'
url: https://bbs.kanxue.com/thread-292057.htm
tid: 292057
author: 北袅
date: '2026-07-17'
tags: [Android安全, 原创, 程序开发]
crawled_at: '2026-07-31T15:01:00+08:00'
replies: 40
---

# 从零手写 ARM64 自定义 Linker

## 前言

学完 ELF 文件格式和 Android linker 的加载流程后,一直有种意犹未尽的感觉——原理看懂了,却没动手实操一遍,总觉得稍有遗憾。本文就是把这次从零实现的完整过程记录下来,拆解其中的思路与落地。一是温习前面所学,把散落的知识点串成一条完整链路;二是为后续理解主流加壳、脱壳的手法打地基——知己知彼,方能百战不殆。本文只是建立好这个地基,而地基之上的种种骚操作,或许在下一篇文章中会出现？

## 环境

真机 Pixel 3、Android 12，架构 arm64-v8a；编译使用 NDK 25.1.8937393。as版本：2026.1.1

## 大体思路

整体目标很清晰：不借助系统的 dlopen/dlsym，用 C++ 手写一个 ARM64 加载器，把一个 .so 从文件变成内存里可调用的代码，最终通过自己实现的符号查找拿到导出函数地址并成功调用。

在做法上，先用系统 dlopen 跑通一次目标 so，留作后续比对的标准答案。之后照着系统 linker 的真实流程，把整条链路拆成几个阶段逐一实现。

装载，是按 program header 的描述把 so 的各个段映射进内存，并算出文件地址到内存地址的关键偏移 load_bias，后面每一步都要用它换算地址。解析 dynamic 段，是遍历其中的各个 tag，把符号表、字符串表、重定位表、初始化函数这些散落的元信息收集进自己的 soinfo 结构。符号查找，是手写 gnu_hash 的查找算法，按名字从 so 里定位符号地址；对本 so 未定义的外部符号如 printf，则采用受控的兜底解析。重定位，是遍历两张 RELA 表，按 ARM64 的四种类型逐条修正内存中的地址，把 GOT 填成正确的函数地址。初始化，是按先 DT_INIT 后 DT_INIT_ARRAY 的顺序，手动触发 so 的构造函数。最后收官，实现自己的 dlsym，从加载好的 so 里查出导出函数 add 的地址，强转成函数指针调用，验证结果与系统 dlopen 一致。

## **环境准备与目标 SO 构建**

### 目标 SO 的交叉编译

创建libtarget.c文件，写入以下内容：

```c
#include <stdio.h>

int add(int a, int b) {
    return a + b;
}

static const char* g_msg = "hello from libtarget";

__attribute__((constructor))
static void my_constructor(void) {
    printf("[target] my_constructor called (init_array), g_msg=%s\n", g_msg);
}
```

去NDK路径下找这个cmd命令

```c
D:\environment\_SDK\ndk\25.1.8937393\toolchains\llvm\prebuilt\windows-x86_64\bin\aarch64-linux-android31-clang.cmd
```

如果找不到可以使用这个命令去检索（搜哪个磁盘下面的path后的路径就换成哪个）

```c
Get-ChildItem -Path D:\ -Recurse -Filter "aarch64-linux-android31-clang.cmd" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
```

```c
& "把找到的路径粘贴到这里" -shared -fPIC -o "$PWD\libtarget.so" "$PWD\libtarget.c"
```

```c
& "D:\environment\_SDK\ndk\25.1.8937393\toolchains\llvm\prebuilt\windows-x86_64\bin\aarch64-linux-android31-clang.cmd" -shared -fPIC -o "$PWD\libtarget.so" "$PWD\libtarget.c"
```

![image](https://bbs.kanxue.com/upload/attach/202607/951483_CTP42CFR488V7RC.png)

像这样啥也没输出就是成功了，目录下会产出一个libtarget.so。

![image](https://bbs.kanxue.com/upload/attach/202607/951483_WYTHJQMEW3KFK7K.png)

### 用系统 dlopen 跑通一次

as创建一个Native项目

![image](https://bbs.kanxue.com/upload/attach/202607/951483_EWUM328FE89JFNG.png)

---

在左侧 `app/src/main/` 上右键 → New → Directory,输入 `jniLibs/arm64-v8a`(一次性带斜杠创建两层)。然后把那个编好的 `libtarget.so` 复制进 `app/src/main/jniLibs/arm64-v8a/libtarget.so`。

注意！！！

这里创建的是arm64的 需要在真机上运行

![image](https://bbs.kanxue.com/upload/attach/202607/951483_Y6CQN87S25TTB3B.png)

#### MainActivity： 去除掉了没用的内容尽可能保证代码干净一点

这里private native void runLoaderRef() 去手敲 然后用ALT+回车去创建

![image](https://bbs.kanxue.com/upload/attach/202607/951483_BPGZDXGQVVYFTCX.png)

```c
package com.example.myapplication;

import androidx.appcompat.app.AppCompatActivity;

import android.os.Bundle;
import android.widget.TextView;

import com.example.myapplication.databinding.ActivityMainBinding;

public class MainActivity extends AppCompatActivity {

    static {
        System.loadLibrary("myapplication");
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        runLoaderRef();
    }

    private native void runLoaderRef();
}
```

#### native-lib.cpp:

```c
#include <jni.h>
#include <string>
#include <dlfcn.h>
#include <unistd.h>
#include <android/log.h>

#define LOG(...) __android_log_print(ANDROID_LOG_INFO, "myloader", __VA_ARGS__)

extern "C"
JNIEXPORT void JNICALL
Java_com_example_myapplication_MainActivity_runLoaderRef(JNIEnv *env, jobject thiz) {
    // TODO: implement runLoaderRef()
    LOG("======1.5 loader_ref start ======");
    LOG("pid=%d", getpid());

    void *h = dlopen("libtarget.so", RTLD_NOW);
    if (!h) {
        LOG("dlopen FAILED:%s", dlerror());
        return;
    }
    LOG("dlopen OK, handle=%p", h);

    typedef int (*add_t)(int, int);
    add_t add_fn = (add_t) dlsym(h, "add");
    if (!add_fn) {
        LOG("dlsym(add) FAILED: %s", dlerror());
        dlclose(h);
        return;
    }
    LOG("dlsym(add) = %p", (void *) add_fn);

    int r = add_fn(3, 4);
    LOG("add(3,4) = %d (expect 7)", r);

    LOG("===== 1.5 loader_ref end =====");
};
```

运行测试：

![image](https://bbs.kanxue.com/upload/attach/202607/951483_X8GJSZUQ6DGMQ9M.png)

## **程序骨架：soinfo 结构与主流程**

>
> 目标：不实现任何实际加载逻辑，先把整个程序的类结构、调用链、数据结构搭出来，能编译能跑能打印，确立后续所有代码的填充位置。
>
>
>

### 精简版 soinfo 结构体

新建 `cpp/soinfo.h`。

#### 被裁剪的字段

本文只保留加载并调用单个 SO 所需的字段，其余一并裁去。

fini_func / fini_array（析构相关）裁去，加载后的 SO 不支持优雅卸载。本文不涉及卸载，进程退出时由系统回收。

TLS 字段（线程局部存储）裁去，SO 若使用 `__thread` 变量将崩溃。目标 SO 未使用。

符号版本字段（verdef / verneed）裁去，无法处理带符号版本的 SO。目标 SO 不含此类信息。

ARM_exidx（异常处理表）裁去，C++ 异常展开可能出错。目标 SO 为 C 代码且不抛异常。

sysv hash 字段裁去，目标 SO 仅含 gnu_hash。

next 指针与 soinfo 链表裁去，该结构用于串联全部已加载 SO 以支持全局符号查找。本文只加载单个 SO，无此需要。

这里按照类型分成五个组方便后续的字段新增与修改

```c
#ifndef MYLINKER_SOINFO_H
#define MYLINKER_SOINFO_H

#include <elf.h>
#include <link.h>
#include <cstddef>
#include <cstdint>
#include <vector>
#include <string>

typedef void (*linker_ctor_function_t)(void);

class soinfo {
public:
//    组一：装载信息
    const char *name;
    ElfW(Addr) base;
    size_t size;
    ElfW(Addr) load_bias;
    const ElfW(Phdr) *phdr;
    size_t phnum;

//    组二：符号信息
    const char *strtab;
    ElfW(Sym) *symtab;

    size_t gnu_nbucket;
    uint32_t *gnu_bucket;
    uint32_t *gnu_chain;
    uint32_t gnu_maskwords;
    uint32_t gnu_shift2;
    ElfW(Addr) *gnu_bloom_filter;
    uint32_t gnu_symndx;

//    组三：重定位信息
    ElfW(Rela) *rela;
    size_t rela_count;

    ElfW(Rela) *plt_rela;
    size_t plt_rela_count;

//    组四：初始化信息
    linker_ctor_function_t init_func;
    linker_ctor_function_t *init_array;
    size_t init_array_count;

//    组五：依赖与状态
    ElfW(Dyn) *dynamic;
    std::vector<std::string> needed_names;
    bool constructors_called;
    uint32_t flags;

    bool load(const char *path);
    bool parse_dynamic();
    bool relocate();
    void call_constructors();
    ElfW(Addr) lookup_symbol(const char *name);

};

#endif
```

### MyLinker 调用链框架

这节主要就是将框架和流程跑通 不需要做具体的内容实现 搭建宏观上的调用链 然后在后续填坑就行

新建 `cpp/mylinker.h`

```c
#ifndef MYLINKER_MYLINKER_H
#define MYLINKER_MYLINKER_H

#include "soinfo.h"

class Mylinker {
public:
    soinfo *dlopen(const char *path);

    ElfW(Addr) dlsym(soinfo *si, const char *name);
};

#endif
```

新建 `cpp/mylinker.cpp`

这里是没有find_library步骤的。系统要在一堆路径找到so文件、检查是否加载过、处理依赖....

我们这里只加载一个so 并且知道路径，因此不需要find_library这个逻辑。

```c
#include "mylinker.h"
#include <android/log.h>

#define LOG(...)__android_log_print(ANDROID_LOG_INFO,"myloader",__VA_ARGS__)

soinfo *Mylinker::dlopen(const char *path) {
    LOG("[dlopen] === start:%s ===", path);

    soinfo *si = new soinfo();
    si->name = path;

    if (!si->load(path)) {
        LOG("[dlopen] load failed");
        delete si;
        return nullptr;
    };

    if (!si->parse_dynamic()) {
        LOG("[dlopen] parse_dynamic failed");
        delete si;
        return nullptr;
    }

    if (!si->relocate()) {
        LOG("[dlopen] relocate failed");
        delete si;
        return nullptr;
    }

    si->call_constructors();

    LOG("[dlopen] === done: %s === ", path);
    return si;
}

ElfW(Addr) Mylinker::dlsym(soinfo *si, const char *name) {
    LOG("[dlsym] lookup: %s", name);
    return si->lookup_symbol(name);
}
```

新建 `cpp/soinfo.cpp`

这里先做空实现和日志打印就行

```c
#include "soinfo.h"
#include <android/log.h>

#define LOG(...)__android_log_print(ANDROID_LOG_INFO,"myloader",__VA_ARGS__)

bool soinfo::load(const char *path) {
    LOG("[load] entering (path=%s)", path);
    return true;
}

bool soinfo::parse_dynamic() {
    LOG("[parse_dynamic] entering ");
    return true;
}

bool soinfo::relocate() {
    LOG("[relocate] entering ");
    return true;
}

void soinfo::call_constructors() {
    LOG("[call_constructors] entering ");
}

ElfW(Addr) soinfo::lookup_symbol(const char *name) {
    LOG("[lookup_symbol] entering ");
    return 0;
}
```

在cmakelists里面新增这两个.cpp文件

![image](https://bbs.kanxue.com/upload/attach/202607/951483_WN5HBQVXNDESVXH.png)

修改native-lib.cpp

将系统的dlopen替换成自己dlopen去加载so

```c
#include <jni.h>
#include <android/log.h>
#include "soinfo.h"
#include "mylinker.h"
#define LOG(...) __android_log_print(ANDROID_LOG_INFO, "myloader", __VA_ARGS__)

extern "C"
JNIEXPORT void JNICALL
Java_com_example_myapplication_MainActivity_runLoaderRef(JNIEnv *env, jobject thiz) {
    Mylinker linker;
    soinfo* si = linker.dlopen("libtarget.so");
    if (!si) {
        LOG("my dlopen failed");
        return;
    }

    ElfW(Addr) add_addr = linker.dlsym(si,"add");
};
```

![image](https://bbs.kanxue.com/upload/attach/202607/951483_SJCM2XV6SXCAJD2.png)

一个小坑：这里写完这节的逻辑后最好先在菜单 **Build → Clean Project**,然后 **Build → Rebuild Project**,再运行。

不然有可能跑的还是旧的app就会出现下图这样 运行流程对不上

![image](https://bbs.kanxue.com/upload/attach/202607/951483_77E3UC76DJRV9DR.png)

### ELF 文件头的读取与校验

native-lib.cpp 改回带参数版本,并把绝对路径传给 dlopen

```c
extern "C" JNIEXPORT void JNICALL
Java_com_example_myapplication_MainActivity_runLoaderRef(
        JNIEnv* env, jobject, jstring nativeLibDir) {
    const char* dir = env->GetStringUTFChars(nativeLibDir, nullptr);
    std::string path = std::string(dir) + "/libtarget.so";
    env->ReleaseStringUTFChars(nativeLibDir, dir);

    MyLinker linker;
    soinfo* si = linker.dlopen(path.c_str());
    if (!si) { LOG("my dlopen failed"); return; }
    linker.dlsym(si, "add");
}
```

MainActivity.java 对应改成传参

```c
runLoaderRef(getApplicationInfo().nativeLibraryDir);
private native void runLoaderRef(String nativeLibDir);
```

![image](https://bbs.kanxue.com/upload/attach/202607/951483_MNF3DWWH4YAZ2H3.png)

接下来实现 `soinfo::load` 的第一段，只做到读文件头与校验。

soinfo.cpp 顶部补头文件:

```c
#include <fcntl.h>
#include <unistd.h>
#include <cstring>
```

soinfo 中新增两个字段保存 fd 与文件头，装载阶段需跨函数使用。

```c
// soinfo.h 组一里加:
int         fd = -1;
ElfW(Ehdr)  header;
```

soinfo.h 成员方法里加一个声明:

```c
bool verify_elf_header();
```

load 实现如下，依次打开文件、读取 ELF 文件头、校验。

```c
bool soinfo::load(const char* path) {
    LOG("[load] entering (path=%s)", path);

    fd = open(path, O_RDONLY);
    if (fd == -1) {
        LOG("[load] open failed: %s", path);
        return false;
    }

    ssize_t n = read(fd, &header, sizeof(header));
    if (n != sizeof(header)) {
        LOG("[load] read ehdr failed, got %zd bytes", n);
        close(fd);
        return false;
    }

    if (!verify_elf_header()) {
        close(fd);
        return false;
    }

    LOG("[load] header OK: entry=0x%lx phoff=%lu phnum=%d",
        (unsigned long)header.e_entry,
        (unsigned long)header.e_phoff,
        header.e_phnum);
    return true;
}
```

verify_elf_header 沿用系统 linker 的校验逻辑，逐项确认文件为 64 位、小端、ARM64 的共享库，任一不符即返回 false。

```c
bool soinfo::verify_elf_header() {
    if (memcmp(header.e_ident, ELFMAG, SELFMAG) != 0) {
        LOG("[verify] bad magic, not ELF");
        return false;
    }
    if (header.e_ident[EI_CLASS] != ELFCLASS64) {
        LOG("[verify] not ELFCLASS64");
        return false;
    }
    if (header.e_ident[EI_DATA] != ELFDATA2LSB) {
        LOG("[verify] not little-endian");
        return false;
    }
    if (header.e_type != ET_DYN) {
        LOG("[verify] not ET_DYN (type=%d)", header.e_type);
        return false;
    }
    if (header.e_machine != EM_AARCH64) {
        LOG("[verify] not EM_AARCH64 (machine=%d)", header.e_machine);
        return false;
    }
    if (header.e_version != EV_CURRENT) {
        LOG("[verify] bad version");
        return false;
    }
    return true;
}
```

运行结果：

![image](https://bbs.kanxue.com/upload/attach/202607/951483_JJK8Z294RYWG4WX.png)

![image](https://bbs.kanxue.com/upload/attach/202607/951483_SYHKMBQWTEKQQCM.png)

## **装载：手动映射 SO 至内存**

>
> 本节手动实现段的映射流程，使加载器映射的段能在 /proc/pid/maps 中被观察到。为便于调试，先采用 file-backed 方式打通整条链路。
>
>
>

### 读取 Program Header Table

先定义页对齐宏，新建 `cpp/linker_common.h`。PAGE_START 向下取整到页边界，PAGE_END 向上取整，PAGE_OFFSET 取页内偏移。

```c
#ifndef MYLINKER_COMMON_H
#define MYLINKER_COMMON_H

#include <elf.h>
#include <link.h>

// Pixel3 / Android12 是 4KB 页
#define PAGE_SIZE 4096
#define PAGE_MASK (~(PAGE_SIZE - 1))

// 向下对齐到页边界
#define PAGE_START(x)  ((x) & PAGE_MASK)
// x 在所在页内的偏移
#define PAGE_OFFSET(x) ((x) & (PAGE_SIZE - 1))
// 向上对齐到页边界
#define PAGE_END(x)    PAGE_START((x) + (PAGE_SIZE - 1))

#endif
```

soinfo.h 新增字段与方法声明。此处的 phdr_table 指向从文件临时映射读到的 PHT，与前面声明的 phdr 不同——后者指向 SO 映射进内存后、内存中的 PHT。

```c
// 组一里加:临时映射 PHT 用
void*  phdr_mmap = nullptr;
size_t phdr_mmap_size = 0;
const ElfW(Phdr)* phdr_table = nullptr;

// 方法声明:
bool read_program_headers();
```

soinfo.cpp 补充头文件与实现。mmap 的 offset 参数必须页对齐，而 e_phoff（64）并非页对齐，因此将起点向下对齐到 page_min（0），映射一整页，再令 phdr_table 指向页内 `PAGE_OFFSET(64) = 64` 处。

```c
#include <sys/mman.h>
#include "linker_common.h"

bool soinfo::read_program_headers() {
    phnum = header.e_phnum;

    ElfW(Addr) phdr_start = header.e_phoff;
    size_t     phdr_size  = phnum * header.e_phentsize;

    ElfW(Addr) page_min   = PAGE_START(phdr_start);
    ElfW(Addr) page_max   = PAGE_END(phdr_start + phdr_size);
    size_t     map_size   = page_max - page_min;

    void* mmap_result = mmap(nullptr, map_size, PROT_READ,
                             MAP_PRIVATE, fd, page_min);
    if (mmap_result == MAP_FAILED) {
        LOG("[read_phdr] mmap failed");
        return false;
    }

    phdr_mmap      = mmap_result;
    phdr_mmap_size = map_size;

    phdr_table = reinterpret_cast<const ElfW(Phdr)*>(
        reinterpret_cast<char*>(mmap_result) + PAGE_OFFSET(phdr_start));

    LOG("[read_phdr] mapped %zu phdrs at %p", phnum, phdr_table);
    return true;
}
```

在 load 里调用

![image](https://bbs.kanxue.com/upload/attach/202607/951483_EGD5RGVF3WHK4SJ.png)

这里可以在read_program_headers 的 return 前把PHT的段进行遍历打印看看是不是对的

```c
    for (size_t i = 0; i < phnum; i++) {
        const ElfW(Phdr)* p = &phdr_table[i];
        LOG("  phdr[%zu] type=%u vaddr=0x%lx memsz=0x%lx flags=0x%x",
            i, p->p_type,
            (unsigned long)p->p_vaddr,
            (unsigned long)p->p_memsz,
            p->p_flags);
    }
```

打印结果与预期一致，没啥问题。

![image](https://bbs.kanxue.com/upload/attach/202607/951483_NPGD6PK2R8RFMHA.png)

### 计算 load_size 并预留地址空间

一个 SO 可能包含多个 PT_LOAD 段，它们在虚拟地址空间中彼此间隔固定。为保证这些段映射后相对位置正确，须先一次性预留一块足以容纳全部段的连续地址空间，再逐段填入。预留空间的大小 load_size，等于最高段末尾（向上页对齐）减去最低段起始（向下页对齐）。

load_bias 是文件虚拟地址到内存实际地址的偏移，等于 mmap 返回的真实起始地址减去页对齐后的最小 p_vaddr，后续所有地址换算均依赖它。

soinfo.h 新增一个方法声明。

```c
bool reserve_address_space();
```

实现分四步。先遍历所有 PT_LOAD 段，求出最小的 p_vaddr 和最大的 p_vaddr + p_memsz；再将两端页对齐，低地址向下、高地址向上，二者之差即 load_size；随后以 PROT_NONE、匿名方式一次性 mmap 出这块连续空间，此时只占位、不设权限、不映射内容；最后由预留空间的起始地址与页对齐后的最小 p_vaddr 算出 load_bias。之所以用 PROT_NONE 占位，是因为此处目的仅是圈定一段连续且不被其他分配占用的地址范围，段的真实内容与权限留待下一节逐段映射时覆盖。

soinfo.cpp 实现:

```c
bool soinfo::reserve_address_space() {
    ElfW(Addr) min_vaddr = UINTPTR_MAX;
    ElfW(Addr) max_vaddr = 0;
    bool found_load = false;

    for (size_t i = 0; i < phnum; i++) {
        const ElfW(Phdr)* p = &phdr_table[i];
        if (p->p_type != PT_LOAD) {
            continue;
        }
        found_load = true;

        if (p->p_vaddr < min_vaddr) {
            min_vaddr = p->p_vaddr;
        }
        if (p->p_vaddr + p->p_memsz > max_vaddr) {
            max_vaddr = p->p_vaddr + p->p_memsz;
        }
    }

    if (!found_load) {
        LOG("[reserve] no PT_LOAD found");
        return false;
    }

    min_vaddr = PAGE_START(min_vaddr);
    max_vaddr = PAGE_END(max_vaddr);

    size = max_vaddr - min_vaddr;

    void* start = mmap(nullptr, size, PROT_NONE,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (start == MAP_FAILED) {
        LOG("[reserve] mmap reserve failed, size=%zu", size);
        return false;
    }

    base = reinterpret_cast<ElfW(Addr)>(start);

    load_bias = base - min_vaddr;

    LOG("[reserve] base=0x%lx size=0x%lx load_bias=0x%lx (min_vaddr=0x%lx)",
        (unsigned long)base,
        (unsigned long)size,
        (unsigned long)load_bias,
        (unsigned long)min_vaddr);

    return true;
}
```

在load函数调用

```c
    if (!reserve_address_space()) {
        close(fd);
        return false;
    }
```

![image](https://bbs.kanxue.com/upload/attach/202607/951483_P4Y9PBFMCP5NRHC.png)

![image](https://bbs.kanxue.com/upload/attach/202607/951483_XRFBZB3WS2D6RNP.png)

### PT_LOAD 段的映射与 BSS 补零

前面以 PROT_NONE 预留了一块连续空地，本节将每个 PT_LOAD 段映射进去并设置权限。段在内存中的位置为 `load_bias + p_vaddr`，load_bias 至此首次参与地址换算。

映射同样使用 mmap，但与预留时不同：带 fd 真实读取文件，带 MAP_FIXED 指定地址，权限取自段本身，形式为 `mmap(对齐后的 load_bias+p_vaddr, 段长, 段权限, MAP_FIXED|MAP_PRIVATE, fd, 对齐后的 p_offset)`。

MAP_FIXED 要求映射到指定地址，不允许系统另择位置——段与段之间的相对距离在编译期已固定，不能改变。之所以能这样用，是因为该地址范围已在上一节被 PROT_NONE 占下，此处以真实内容覆盖。因此顺序不可颠倒，必须先预留后映射。

地址与文件偏移都需页对齐，而 p_vaddr、p_offset 未必对齐，处理方式是两者一并向下取整到页边界。二者能够对应，是因为 ELF 保证同一段的 p_vaddr 与 p_offset 具有相同的页内偏移。权限由 p_flags 的 PF_R/W/X 转为 PROT_R/W/X，代码段为 r-x，数据段为 rw-。

BSS 补零仅在 memsz 大于 filesz 时发生，且最易遗漏。filesz 是段在文件中的大小，memsz 是段在内存镜像中的大小，二者之差即 BSS，需以零填充。上面的 mmap 只映射了 filesz，其余分两种情况补齐：一是段尾不足一页的部分，从 filesz 处到本页末尾，该范围已被 mmap 读入但属文件的脏数据，用 memset 清零；二是超出一页的部分，另做一次匿名 mmap（fd = -1）补齐零页。

soinfo.h 新增一个方法声明，其后在 soinfo.cpp 中实现（其中 flags_to_prot 负责将 p_flags 转为 mmap 的权限位）。

```c
bool load_segments()
```

soinfo.cpp 实现:

```c
static int flags_to_prot(ElfW(Word) p_flags) {
    int prot = 0;
    if (p_flags & PF_R) prot |= PROT_READ;
    if (p_flags & PF_W) prot |= PROT_WRITE;
    if (p_flags & PF_X) prot |= PROT_EXEC;
    return prot;
}

bool soinfo::load_segments() {
    for (size_t i = 0; i < phnum; i++) {
        const ElfW(Phdr)* p = &phdr_table[i];
        if (p->p_type != PT_LOAD) {
            continue;
        }

        ElfW(Addr) seg_start = load_bias + p->p_vaddr;
        ElfW(Addr) seg_file_end = seg_start + p->p_filesz;
        ElfW(Addr) seg_mem_end  = seg_start + p->p_memsz;

        ElfW(Addr) seg_page_start = PAGE_START(seg_start);
        ElfW(Addr) file_page_start = PAGE_START(p->p_offset);
        ElfW(Addr) file_end_aligned = PAGE_END(seg_file_end);
        size_t map_size = file_end_aligned - seg_page_start;

        int prot = flags_to_prot(p->p_flags);

        void* seg = mmap(reinterpret_cast<void*>(seg_page_start),
                         map_size, prot,
                         MAP_FIXED | MAP_PRIVATE, fd, file_page_start);
        if (seg == MAP_FAILED) {
            LOG("[load_seg] mmap seg[%zu] failed", i);
            return false;
        }

        LOG("[load_seg] seg[%zu] vaddr=0x%lx -> mem=0x%lx size=0x%zx prot=%d",
            i, (unsigned long)p->p_vaddr,
            (unsigned long)seg_page_start, map_size, prot);

        if (p->p_memsz > p->p_filesz) {
            ElfW(Addr) zero_start = seg_file_end;
            ElfW(Addr) zero_page_end = PAGE_END(seg_file_end);
            if (zero_start < zero_page_end) {
                memset(reinterpret_cast<void*>(zero_start), 0,
                       zero_page_end - zero_start);
            }

            ElfW(Addr) mem_end_aligned = PAGE_END(seg_mem_end);
            if (mem_end_aligned > zero_page_end) {
                void* zero_map = mmap(
                        reinterpret_cast<void*>(zero_page_end),
                        mem_end_aligned - zero_page_end, prot,
                        MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
                if (zero_map == MAP_FAILED) {
                    LOG("[load_seg] bss anon mmap failed seg[%zu]", i);
                    return false;
                }
            }
        }
    }
    return true;
}
```

在 load 里调用(接在 reserve_address_space 之后):

```c
    if (!reserve_address_space()) {
        close(fd);
        return false;
    }

    if (!load_segments()) {
        close(fd);
        return false;
    }
```

![image](https://bbs.kanxue.com/upload/attach/202607/951483_M4PUCRBDWCZXWTU.png)

### 内存中 Program Header 的定位

读取 Program Header Table 一节曾为读 PHT 临时 mmap 了文件头所在的一页（phdr_mmap）。如今各段已映射进内存，PHT 作为文件内容也随之进入镜像，本节在镜像中重新定位它，存入 phdr，再释放此前那份临时映射。

不继续沿用临时映射有两个原因：其一，它本就约定用完即弃；其二，后续查找 dynamic、symtab 等一律以 load_bias + p_vaddr 在镜像内换算地址，若混用一份镜像外的 PHT，概念上并不统一。系统 linker 同样在镜像中重新定位，此处与之保持一致。

定位有两种方式，按优先级选取。首选 PT_PHDR 段，它专门记录 PHT 自身在内存中的位置，存在时直接取 load_bias + p_vaddr，最为准确。若无 PT_PHDR，则退而取 p_offset 为 0 的第一个 PT_LOAD 段：ELF 文件头位于文件起始，PHT 紧随其后，这一区域必被某个从偏移 0 起始的 PT_LOAD 映入内存，地址为 load_bias + p_vaddr + e_phoff。两种方式算出的是同一地址，PT_PHDR 更为直接。

此处有一个顺序需注意：遍历查找 PT_PHDR 时用的仍是 phdr_table（指向临时映射），因此必须先算出新地址存好，最后再 munmap 临时映射。若顺序颠倒，phdr_table 将成为悬空指针。

find_phdr 是 load 的最后一步，成功后即可 close(fd)——各段已在内存中，不再依赖文件描述符。

soinfo.h 新增一个方法声明，其后在 soinfo.cpp 中实现。

```c
bool find_phdr();
```

soinfo.cpp 实现:

```c
bool soinfo::find_phdr() {
    const ElfW(Phdr)* phdr_in_mem = nullptr;

    for (size_t i = 0; i < phnum; i++) {
        const ElfW(Phdr)* p = &phdr_table[i];
        if (p->p_type == PT_PHDR) {
            phdr_in_mem = reinterpret_cast<const ElfW(Phdr)*>(
                    load_bias + p->p_vaddr);
            LOG("[find_phdr] via PT_PHDR");
            break;
        }
    }

    if (phdr_in_mem == nullptr) {
        for (size_t i = 0; i < phnum; i++) {
            const ElfW(Phdr)* p = &phdr_table[i];
            if (p->p_type == PT_LOAD && p->p_offset == 0) {
                phdr_in_mem = reinterpret_cast<const ElfW(Phdr)*>(
                        load_bias + p->p_vaddr + header.e_phoff);
                LOG("[find_phdr] via PT_LOAD(offset=0)");
                break;
            }
        }
    }

    if (phdr_in_mem == nullptr) {
        LOG("[find_phdr] cannot locate phdr in memory");
        return false;
    }

    phdr = phdr_in_mem;

    LOG("[find_phdr] phdr in memory = %p (phnum=%zu)", phdr, phnum);

    if (phdr_mmap != nullptr) {
        munmap(phdr_mmap, phdr_mmap_size);
        phdr_mmap = nullptr;
        phdr_mmap_size = 0;
        phdr_table = nullptr;
    }

    return true;
}
```

在 load 里调用(接在 load_segments 之后,这也是 load 的最后一步):

```c
    if (!load_segments()) {
        close(fd);
        return false;
    }

    if (!find_phdr()) {
        close(fd);
        return false;
    }

    close(fd);
    LOG("[load] done: base=0x%lx load_bias=0x%lx",
        (unsigned long)base, (unsigned long)load_bias);
    return true;
```

![image](https://bbs.kanxue.com/upload/attach/202607/951483_CE5NMD3A9F3HA7B.png)

## **解析 Dynamic 段**

>
> 本节遍历 dynamic 段，采用 ARM64 的 tag 集合，将散落在文件各处的元信息收集进 soinfo。
>
>
>

### PT_DYNAMIC 的定位

装载阶段已将 SO 搬入内存，但符号表、重定位表、构造函数等所在位置尚未可知——这些信息全部记录在 dynamic 段中，是整个链接过程的信息中枢。本节只做一件事：定位 PT_DYNAMIC，算出其内存地址存入 dynamic，作为后续解析的入口。

定位方式与查找内存中 PHT 时相同：遍历 phdr，找到 `p_type == PT_DYNAMIC` 的项，取 `load_bias + p_vaddr`。dynamic 段是一个 `ElfW(Dyn)` 数组，以 `ElfW(Dyn)*` 保存。

只取第一个，找到即停，与系统一致。

soinfo.h 新增一个方法声明，其后在 soinfo.cpp 中实现。

```c
bool find_dynamic();
```

soinfo.cpp 实现:

```c
bool soinfo::find_dynamic() {
    for (size_t i = 0; i < phnum; i++) {
        const ElfW(Phdr)* p = &phdr[i];
        if (p->p_type == PT_DYNAMIC) {
            dynamic = reinterpret_cast<ElfW(Dyn)*>(load_bias + p->p_vaddr);
            LOG("[find_dynamic] dynamic at %p (vaddr=0x%lx)",
                dynamic, (unsigned long)p->p_vaddr);
            return true;
        }
    }
    LOG("[find_dynamic] no PT_DYNAMIC found");
    return false;
}
```

调用放在 parse_dynamic 开头

```c
bool soinfo::parse_dynamic() {
    LOG("[parse_dynamic] entering");

    if (!find_dynamic()) {
        return false;
    }

    return true;
}
```

![image](https://bbs.kanxue.com/upload/attach/202607/951483_ZTF7YKRTBP5VNQY.png)

### 遍历 d_tag 的 switch-case

上一步已取得 dynamic 入口，即一个 ElfW(Dyn) 数组。本节从头遍历，每项是一组 <tag, value>，通过一个大 switch 按 tag 将元信息填入 soinfo，遇到 DT_NULL（tag 为 0）终止。

value 有两种含义，切勿混淆，这也是本节最主要的出错点。地址型的 tag（如 STRTAB、SYMTAB、RELA 等）需以 load_bias + d_ptr 换算为内存地址；数值型的 tag（如 RELASZ 及各类计数）则直接取用，不加 bias。

需要处理的 tag 按用途分为几组。字符串表与符号表，分别记录 strtab、symtab 的地址。gnu_hash 此处只保存表的起点地址，各字段（bucket、chain、bloom）的拆解留到符号查找一节与查找逻辑一并说明；DT_HASH 现代 SO 一般不含，忽略即可。

重定位相关，ARM64 使用 RELA 而非 32 位的 REL：RELA 为 .rela.dyn 地址，RELASZ 除以 24 得表项数；JMPREL 为 .rela.plt 地址，PLTRELSZ 除以 24 得表项数。PLTREL 的值必须为 DT_RELA，若为 REL 则报错；dynamic 中一旦出现 DT_REL、DT_RELSZ 也报错——以此与 32 位划清界限。

初始化相关，INIT 为老式的单个初始化函数，INIT_ARRAY 为构造函数数组，INIT_ARRAYSZ 除以指针大小得表项数。依赖相关，NEEDED 的 value 是 strtab 中的偏移而非地址，须以 strtab + d_val 才能取到名字；由于遍历到 NEEDED 时 strtab 未必已确定，此处先攒下偏移，遍历结束后再统一翻译成名字。

soinfo.h 新增两个临时字段：一个保存 gnu_hash 表起点，一个保存尚未翻译的 needed 偏移列表。随后在 soinfo.cpp 中实现完整的遍历逻辑，接在 find_dynamic 之后：遍历时按上述分组填充各字段，遍历结束后将字节数换算为表项数、翻译 needed 名字，并打印各项结果以便核对。

```c
// 组二里加:先只存 gnu_hash 表起点,第五章再拆字段
ElfW(Addr) gnu_hash_base = 0;

// 组五附近加:先攒 needed 的 strtab 偏移,遍历完再翻译
std::vector<ElfW(Xword)> needed_offsets;
```

soinfo.cpp 实现(接在 find_dynamic 之后):

```c
bool soinfo::parse_dynamic() {
    LOG("[parse_dynamic] entering");

    if (!find_dynamic()) {
        return false;
    }

    ElfW(Xword) relaent = 0;
    ElfW(Xword) relasz  = 0;
    ElfW(Xword) pltrelsz = 0;
    ElfW(Xword) init_array_bytes = 0;

    for (ElfW(Dyn)* d = dynamic; d->d_tag != DT_NULL; d++) {
        switch (d->d_tag) {

            case DT_STRTAB:
                strtab = reinterpret_cast<const char*>(load_bias + d->d_un.d_ptr);
                break;
            case DT_SYMTAB:
                symtab = reinterpret_cast<ElfW(Sym)*>(load_bias + d->d_un.d_ptr);
                break;

            case DT_GNU_HASH:
                gnu_hash_base = load_bias + d->d_un.d_ptr;
                break;
            case DT_HASH:
                LOG("[parse_dynamic] found DT_HASH (ignored, using gnu_hash)");
                break;

            case DT_RELA:
                rela = reinterpret_cast<ElfW(Rela)*>(load_bias + d->d_un.d_ptr);
                break;
            case DT_RELASZ:
                relasz = d->d_un.d_val;
                break;
            case DT_RELAENT:
                relaent = d->d_un.d_val;
                break;

            case DT_JMPREL:
                plt_rela = reinterpret_cast<ElfW(Rela)*>(load_bias + d->d_un.d_ptr);
                break;
            case DT_PLTRELSZ:
                pltrelsz = d->d_un.d_val;
                break;
            case DT_PLTREL:
                if (d->d_un.d_val != DT_RELA) {
                    LOG("[parse_dynamic] DT_PLTREL is not DT_RELA, abort");
                    return false;
                }
                break;

            case DT_REL:
            case DT_RELSZ:
                LOG("[parse_dynamic] found REL (32-bit style) on ARM64, abort");
                return false;

            case DT_INIT:
                init_func = reinterpret_cast<linker_ctor_function_t>(
                        load_bias + d->d_un.d_ptr);
                break;
            case DT_INIT_ARRAY:
                init_array = reinterpret_cast<linker_ctor_function_t*>(
                        load_bias + d->d_un.d_ptr);
                break;
            case DT_INIT_ARRAYSZ:
                init_array_bytes = d->d_un.d_val;
                break;

            case DT_NEEDED:
                needed_offsets.push_back(d->d_un.d_val);
                break;

            default:
                break;
        }
    }

    if (relaent != 0 && relaent != sizeof(ElfW(Rela))) {
        LOG("[parse_dynamic] RELAENT mismatch: %lu", (unsigned long)relaent);
        return false;
    }
    rela_count      = relasz   / sizeof(ElfW(Rela));
    plt_rela_count  = pltrelsz / sizeof(ElfW(Rela));
    init_array_count = init_array_bytes / sizeof(ElfW(Addr));

    if (strtab != nullptr) {
        for (ElfW(Xword) off : needed_offsets) {
            needed_names.push_back(std::string(strtab + off));
        }
    }

    LOG("[parse_dynamic] strtab=%p symtab=%p", strtab, symtab);
    LOG("[parse_dynamic] rela=%p count=%zu | plt_rela=%p count=%zu",
        rela, rela_count, plt_rela, plt_rela_count);
    LOG("[parse_dynamic] init_func=%p init_array=%p count=%zu",
        (void*)init_func, (void*)init_array, init_array_count);
    LOG("[parse_dynamic] gnu_hash_base=0x%lx, needed=%zu",
        (unsigned long)gnu_hash_base, needed_names.size());
    for (auto& n : needed_names) {
        LOG("[parse_dynamic]   needed: %s", n.c_str());
    }

    return true;
}
```

![image](https://bbs.kanxue.com/upload/attach/202607/951483_UA36MK2Z3MF6Z23.png)

## **符号解析**

>
> 本节解决脱离 dlopen 后符号从何而来的问题：实现自己的符号查找函数，并厘清完全脱离系统的现实边界。
>
>
>

### 实现符号查找函数 my_lookup_symbol

先拆解 gnu_hash 表的布局。从 gnu_hash_base 起，头部是 4 个 uint32，依次为 nbucket、symndx、bloom_size（以 size−1 的形式保存，直接作掩码用）、shift2；其后依次是 bloom 数组、bucket 数组、chain 数组。保存 chain 指针时预先前移 symndx，如此查找时可直接以 gnu_chain[符号下标] 索引，省去一次减法。

查找分三步。第一步算出符号名的 hash，查 bloom 过滤器，只要有一位为 0 即可判定符号不存在，直接返回 0。第二步以 `b`ucket[h % nbucket] 取得起始符号下标，若为 0 表示空桶，返回 0。第三步从起始下标起连续加一遍历：先比较 (chain 值 | 1) == (h | 1)，即抹掉最低位后的高位是否匹配，匹配再用 strcmp 核对真实符号名；chain 值最低位为 1 表示到达链尾，比对完即结束。命中时返回 symtab[n].st_value + load_bias。

命中后必须拦截 SHN_UNDEF。符号有两类：本 SO 定义的，其 st_shndx 为正常段号，加 load_bias 即得真实地址；外部未定义的，其 st_shndx 等于 SHN_UNDEF，如 printf，真身在 libc。即便名字匹配到一个 UNDEF 项，也返回 0，以便重定位阶段知晓该走外部兜底。也就是说，lookup_symbol 只对本 SO 真正定义的符号返回有效地址。

弱符号在此不特殊处理。本实现只加载一个 SO，不存在同名符号的取舍问题，定义了就返回、未定义（含 UNDEF）则返回 0，了解即可。

验证方式：查 add 应得到 base 附近的非零地址；查 printf 应走到 found but UNDEF 分支返回 0，正好验证 UNDEF 逻辑，其真实地址由外部兜底一节解决。

实现分两部分。soinfo.h 新增 init_gnu_hash 声明，负责将 gnu_hash_base 拆解为各段字段，其实现接在 parse_dynamic 末尾、gnu_hash_base 已确定之后调用。随后在 soinfo.cpp 中实现 gnu_hash 值的计算函数（djb2 变体）与查找主体 lookup_symbol。

```c
bool init_gnu_hash();   // 把 gnu_hash_base 拆成各段字段
```

soinfo.cpp,先实现 init_gnu_hash:

```c
bool soinfo::init_gnu_hash() {
    if (gnu_hash_base == 0) {
        LOG("[gnu_hash] no DT_GNU_HASH");
        return false;
    }

    uint32_t* h = reinterpret_cast<uint32_t*>(gnu_hash_base);

    gnu_nbucket   = h[0];
    gnu_symndx    = h[1];
    gnu_maskwords = h[2] - 1;
    gnu_shift2    = h[3];

    gnu_bloom_filter = reinterpret_cast<ElfW(Addr)*>(h + 4);

    gnu_bucket = reinterpret_cast<uint32_t*>(
            gnu_bloom_filter + (gnu_maskwords + 1));

    gnu_chain = gnu_bucket + gnu_nbucket - gnu_symndx;

    LOG("[gnu_hash] nbucket=%zu symndx=%u maskwords=%u shift2=%u",
        gnu_nbucket, gnu_symndx, gnu_maskwords, gnu_shift2);
    return true;
}
```

把它接到 parse_dynamic 结尾(dynamic 都解析完、gnu_hash_base 有了之后):

```c
    if (!init_gnu_hash()) {
        return false;
    }
    return true;
```

然后是 gnu_hash 函数和查找主体:

```c
static uint32_t gnu_hash_calc(const char* name) {
    uint32_t h = 5381;
    for (const char* p = name; *p != '\0'; p++) {
        h = (h << 5) + h + static_cast<uint8_t>(*p);
    }
    return h;
}

ElfW(Addr) soinfo::lookup_symbol(const char* name) {
    uint32_t h = gnu_hash_calc(name);

    constexpr uint32_t kBits = 64;
    ElfW(Addr) word = gnu_bloom_filter[(h / kBits) & gnu_maskwords];
    uint32_t bit1 = h % kBits;
    uint32_t bit2 = (h >> gnu_shift2) % kBits;
    if (((word >> bit1) & 1) == 0 || ((word >> bit2) & 1) == 0) {
        LOG("[lookup] %s: bloom reject", name);
        return 0;
    }

    uint32_t n = gnu_bucket[h % gnu_nbucket];
    if (n == 0) {
        LOG("[lookup] %s: empty bucket", name);
        return 0;
    }

    do {
        uint32_t chain_hash = gnu_chain[n];

        if (((chain_hash | 1) == (h | 1))) {
            const ElfW(Sym)* sym = &symtab[n];
            const char* sym_name = strtab + sym->st_name;
            if (strcmp(sym_name, name) == 0) {
                if (sym->st_shndx == SHN_UNDEF) {
                    LOG("[lookup] %s: found but UNDEF (external)", name);
                    return 0;
                }
                ElfW(Addr) addr = sym->st_value + load_bias;
                LOG("[lookup] %s: found at 0x%lx", name, (unsigned long)addr);
                return addr;
            }
        }

        if (chain_hash & 1) {
            break;
        }
        n++;
    } while (true);

    LOG("[lookup] %s: not found", name);
    return 0;
}
```

单独测一下这个查找函数。可以在 parse_dynamic 成功之后(重定位之前也行)临时加一行,查 add 看看:

```c
    ElfW(Addr) a = si->lookup_symbol("add");
    LOG("[test] lookup add = 0x%lx", (unsigned long)a);
```

![image](https://bbs.kanxue.com/upload/attach/202607/951483_BRUM4SK2DBS5QJJ.png)

### 外部符号的边界与兜底

加载目标 SO 的全过程——装载、解析、符号处理、重定位、初始化——均由本实现手动完成，不调用系统加载器。但目标 SO 依赖 libc、libm 等系统基础库中的外部符号，如 printf，这类符号的地址需要另行获取。此处采用有限度的兜底：从系统中查询这些符号已有的地址。这些系统库本就存在于当前进程空间，此处只是查询其现成地址，并非重新加载它们。

获取外部符号地址有两种方案。其一，用 dlsym 在当前进程已加载的全部库中按序查找该符号。其二，读取 /proc/self/maps 找到目标库的基址，将其也视作一个内存中的 SO，套用前面查找 dynamic、拆解 gnu_hash、lookup_symbol 的整套流程，在它的符号表中查 printf。第二种方案更为繁琐，此处采用第一种。

需要说明，这一步是整个实现中唯一借助系统能力的地方，也是完全脱离 dlopen 的现实边界所在。若要做到彻底不依赖，须走第二种方案，把 libc 也当作一份内存镜像自行解析——本实现为求简洁选择了第一种。

soinfo.h 新增 resolve_symbol 声明，soinfo.cpp 顶部补充 dlfcn.h 头文件。实现逻辑为：先用自写的 lookup_symbol 在本 SO 内查找，命中即返回；本地没有（如 SHN_UNDEF）时，再用 `dlsym(RTLD_DEFAULT, name)` 向系统兜底；两者皆无则判定符号无法解析。

```c
ElfW(Addr) resolve_symbol(const char* name);
```

soinfo.cpp 顶部加头文件:

```c
#include <dlfcn.h>
```

soinfo.cpp实现：

```c
ElfW(Addr) soinfo::resolve_symbol(const char* name) {

    ElfW(Addr) local = lookup_symbol(name);
    if (local != 0) {
        return local;
    }

    void* ext = dlsym(RTLD_DEFAULT, name);
    if (ext != nullptr) {
        LOG("[resolve] %s: external via dlsym = %p", name, ext);
        return reinterpret_cast<ElfW(Addr)>(ext);
    }

    LOG("[resolve] %s: UNRESOLVED", name);
    return 0;
}
```

![image](https://bbs.kanxue.com/upload/attach/202607/951483_CWDGJDRTNBUY7XV.png)

## **重定位：ARM64 RELA 修正**

### 重定位流程与 RELA 表项解析

重定位的作用在于：SO 加载到运行前才确定的基址（load_bias），代码与数据中大量地址在编译期无法确定，需在加载时按表逐条修正为正确值。

重定位信息存于两张表。.rela.dyn（对应 rela）管数据类，如全局指针、GOT 数据项；.rela.plt（对应 plt_rela）管 PLT 跳转，如 printf 这类外部函数。两表结构均为 Elf64_Rela，处理逻辑相同，仅来源不同，因此实现一个处理单表的函数，relocate 对两表各调用一次。

Elf64_Rela 有三个字段。r_offset 是被修正的位置，为文件虚拟地址，实际内存地址为 r_offset + load_bias。r_info 打包了类型与符号下标，用 ELF64_R_TYPE 取类型、ELF64_R_SYM 取符号表下标；64 位下类型在低 32 位、符号在高 32 位，而 32 位下类型占低 8 位、符号占高 24 位，这是与 32 位差异最大、最易出错之处，须使用 ELF64_ 宏，不可手写位运算。r_addend 是显式加数，也是 RELA 相对 REL 的本质区别所在——REL 没有此字段，须从被修改位置读取原值作为隐式加数，而 RELA 直接使用 r_addend，无需读取原内存；ARM64 统一使用 RELA。

本节只搭骨架：遍历两表，拆出 type、sym_index、addend，算出修正地址 r_offset + load_bias，进入 switch。各类型的具体公式在下一节实现，本节 switch 的分支暂时留空并打印日志。

soinfo.h 新增一个处理单张表的私有方法声明，其后在 soinfo.cpp 中实现 relocate 与 relocate_table。

```c
bool relocate_table(ElfW(Rela)* table, size_t count);
```

soinfo.cpp 实现 relocate 与 relocate_table:

```c
bool soinfo::relocate() {
    LOG("[relocate] entering");

    if (rela != nullptr && rela_count > 0) {
        LOG("[relocate] .rela.dyn: %zu entries", rela_count);
        if (!relocate_table(rela, rela_count)) {
            return false;
        }
    }

    if (plt_rela != nullptr && plt_rela_count > 0) {
        LOG("[relocate] .rela.plt: %zu entries", plt_rela_count);
        if (!relocate_table(plt_rela, plt_rela_count)) {
            return false;
        }
    }

    LOG("[relocate] done");
    return true;
}

bool soinfo::relocate_table(ElfW(Rela)* table, size_t count) {
    for (size_t i = 0; i < count; i++) {
        ElfW(Rela)* r = &table[i];

        uint32_t type      = ELF64_R_TYPE(r->r_info);
        uint32_t sym_index = ELF64_R_SYM(r->r_info);
        ElfW(Sxword) addend = r->r_addend;

        ElfW(Addr)* reloc = reinterpret_cast<ElfW(Addr)*>(load_bias + r->r_offset);

        LOG("[reloc] [%zu] type=%u sym=%u offset=0x%lx addend=%ld -> reloc=%p",
            i, type, sym_index,
            (unsigned long)r->r_offset, (long)addend, reloc);

        switch (type) {
            // TODO
            default:
                LOG("[reloc] [%zu] type %u not handled yet", i, type);
                break;
        }
    }
    return true;
}
```

### 四类 ARM64 重定位的实现

本节填充上一节 switch 的四个分支，各按公式算出结果写入 reloc，完成后 SO 内的地址即全部修正到位。

其中 GLOB_DAT、JUMP_SLOT、ABS64 三类需要符号地址，处理前先以 sym_index 在 symtab 中取出符号、取到符号名，调用 resolve_symbol 得到 sym_addr；RELATIVE 不涉及符号，跳过此步。

四种类型的公式与含义如下。R_AARCH64_RELATIVE 为 *reloc = load_bias + addend，修正指向本 SO 内部的指针，目标由基址决定，不查符号，对应 32 位的 R_ARM_RELATIVE（后者无 addend，须读原值），前面验证点中的 g_msg 即属此类。R_AARCH64_GLOB_DAT 为 *reloc = sym_addr + addend，用于 GOT 数据项，指向某符号，须先查出符号地址。R_AARCH64_JUMP_SLOT 为 *reloc = sym_addr，用于 PLT 跳转，对应外部函数如 printf，addend 恒为 0。R_AARCH64_ABS64 为 *reloc = sym_addr + addend，写入符号的 64 位绝对地址。

RELATIVE 用 load_bias、其余用 sym_addr，原因在于：RELATIVE 的目标必在本 SO 内部，地址由 load_bias 决定；其余指向具名符号，须查出其真实所在，可能位于 libc。addend 在各类型中统一表示基址之上的固定偏移。

失败处理上，JUMP_SLOT 等外部符号在 resolve_symbol 返回 0 时报错终止，绝不填 0——填 0 会在调用时崩溃且难以排查。弱符号允许为 0，但本实现不涉及，一律按查不到即报错处理。

在 soinfo.cpp 中将上一节 relocate_table 的 switch 补全。

```c
bool soinfo::relocate_table(ElfW(Rela)* table, size_t count) {
    for (size_t i = 0; i < count; i++) {
        ElfW(Rela)* r = &table[i];

        uint32_t type      = ELF64_R_TYPE(r->r_info);
        uint32_t sym_index = ELF64_R_SYM(r->r_info);
        ElfW(Sxword) addend = r->r_addend;

        ElfW(Addr)* reloc = reinterpret_cast<ElfW(Addr)*>(load_bias + r->r_offset);

        ElfW(Addr) sym_addr = 0;
        if (type == R_AARCH64_GLOB_DAT ||
            type == R_AARCH64_JUMP_SLOT ||
            type == R_AARCH64_ABS64) {
            const char* sym_name = strtab + symtab[sym_index].st_name;
            sym_addr = resolve_symbol(sym_name);
            if (sym_addr == 0) {
                LOG("[reloc] [%zu] cannot resolve symbol: %s", i, sym_name);
                return false;
            }
        }

        switch (type) {
            case R_AARCH64_RELATIVE:
                *reloc = load_bias + addend;
                break;

            case R_AARCH64_GLOB_DAT:
                *reloc = sym_addr + addend;
                break;

            case R_AARCH64_JUMP_SLOT:
                *reloc = sym_addr;
                break;

            case R_AARCH64_ABS64:
                *reloc = sym_addr + addend;
                break;

            default:
                LOG("[reloc] [%zu] unknown type %u, skip", i, type);
                break;
        }
    }
    return true;
}
```

## **初始化：手动触发构造函数**

### call_constructors实现

至此 SO 已装载、解析、重定位完毕，本节手动触发它的构造函数，使其初始化逻辑真正执行。

构造函数有两个来源，须按固定顺序调用：先执行 DT_INIT 指向的老式单个初始化函数，再执行 DT_INIT_ARRAY 数组中的各构造函数。call_constructors 即负责这一流程，并以 constructors_called 标志防止重复初始化。

soinfo.h 新增两个工具方法声明——call_function 与 call_array，其实现放在下一节。随后在 soinfo.cpp 中实现 call_constructors，call_function 与 call_array 此处先留空。

```c
void call_function(linker_ctor_function_t func);
void call_array(linker_ctor_function_t* array, size_t count);
```

soinfo.cpp 实现 call_constructors

```c
void soinfo::call_constructors() {
    if (constructors_called) {
        return;
    }
    constructors_called = true;

    LOG("[call_constructors] start");

    if (init_func != nullptr) {
        LOG("[call_constructors] calling DT_INIT %p", (void*)init_func);
        call_function(init_func);
    }

    if (init_array != nullptr && init_array_count > 0) {
        LOG("[call_constructors] calling DT_INIT_ARRAY, count=%zu",
            init_array_count);
        call_array(init_array, init_array_count);
    }

    LOG("[call_constructors] done");
}

void soinfo::call_function(linker_ctor_function_t func) {

}

void soinfo::call_array(linker_ctor_function_t *array, size_t count) {

}
```

### call_function 与 call_array 的实现

本节在 soinfo.cpp 中实现这两个函数。call_function 调用单个函数，调用前先排除两个哨兵值——0（空）和 -1（全 1），二者都不是合法地址，遇到即跳过，其余视为合法地址直接调用。call_array 正序遍历数组（从 0 到 count−1），对每一项调用 call_function。

```c
void soinfo::call_function(linker_ctor_function_t func) {
    if (func == nullptr ||
        reinterpret_cast<ElfW(Addr)>(func) == static_cast<ElfW(Addr)>(-1)) {
        return;
    }

    func();
}

void soinfo::call_array(linker_ctor_function_t* array, size_t count) {
    for (size_t i = 0; i < count; i++) {
        LOG("[call_array] [%zu] %p", i, (void*)array[i]);
        call_function(array[i]);
    }
}
```

至此 整个so已经加载完毕了 理论上来说是可以看得到`libtarget`init函数打印的日志的，但是你会发现日志无论怎么筛选都死活找不到init函数答应的那段日志。构造函数其实一直执行成功,只是原来的 printf 输出到了 stdout,而 Android app 的 stdout 默认不接入 logcat,所以看不见——换成 `__android_log_print` 后就显示了,加载器全程没有任何问题。

这里就需要对`libtarget`代码做小小的修改即可 把 libtarget.c 的 my_constructor 改成用 `__android_log_print`

```c
#include <android/log.h>
__attribute__((constructor))
static void my_constructor(void) {
    __android_log_print(ANDROID_LOG_INFO, "target",
        "my_constructor called (init_array), g_msg=%s", g_msg);
}
```

将修改后的so重新编译，注意：需要在之前的编译命令基础上末尾新增一个-llog就行了

```c
& "D:\environment\_SDK\ndk\25.1.8937393\toolchains\llvm\prebuilt\windows-x86_64\bin\aarch64-linux-android31-clang.cmd" -shared -fPIC -o "$PWD\libtarget.so" "$PWD\libtarget.c" -llog
```

编译完把新的 libtarget.so 复制到 `app/src/main/jniLibs/arm64-v8a/` 覆盖旧的,然后照旧 Clean Project → Rebuild → 运行。

![image](https://bbs.kanxue.com/upload/attach/202607/951483_JE4YEPUQEY9KN9C.png)

## **收官：自实现 dlsym 与函数调用**

### my_dlsym 的实现

这一步实际无需新增代码。搭建 MyLinker 调用链框架时，MyLinker::dlsym 已写好这段转发——它打印查找日志，再调用 soinfo 的 lookup_symbol 返回符号地址。因此此处日志中早已有相应输出。

```c
ElfW(Addr) Mylinker::dlsym(soinfo* si, const char* name) {
    LOG("[dlsym] lookup: %s", name);
    return si->lookup_symbol(name);
}
```

![image](https://bbs.kanxue.com/upload/attach/202607/951483_7HA6Y3H7YUP8VP6.png)

### 函数指针转换与结果验证

```c
#include <jni.h>
#include <string>
#include <android/log.h>
#include "soinfo.h"
#include "mylinker.h"

#define LOG(...) __android_log_print(ANDROID_LOG_INFO, "myloader", __VA_ARGS__)

extern "C" JNIEXPORT void JNICALL
Java_com_example_myapplication_MainActivity_runLoaderRef(
        JNIEnv* env, jobject, jstring nativeLibDir) {

    const char* dir = env->GetStringUTFChars(nativeLibDir, nullptr);
    std::string path = std::string(dir) + "/libtarget.so";
    env->ReleaseStringUTFChars(nativeLibDir, dir);

    Mylinker linker;

    soinfo* si = linker.dlopen(path.c_str());
    if (!si) {
        LOG("my dlopen failed");
        return;
    }

    ElfW(Addr) add_addr = linker.dlsym(si, "add");
    if (add_addr == 0) {
        LOG("my dlsym(add) failed");
        return;
    }

    typedef int (*add_t)(int, int);
    add_t add_fn = reinterpret_cast<add_t>(add_addr);

    int r = add_fn(3, 4);
    LOG("[MVP] add(3,4) = %d (expect 7)", r);

    if (r == 7) {
        LOG("[MVP] SUCCESS: custom linker works end-to-end!");
    } else {
        LOG("[MVP] FAILED: got %d", r);
    }
}
```

![image](https://bbs.kanxue.com/upload/attach/202607/951483_SZ9KS556ZDJE6E4.png)

![image](https://bbs.kanxue.com/upload/attach/202607/951483_HXKDQG4Q5AV6VDY.png)

## 结语

至此，一个不依赖系统 dlopen / dlsym 的 ARM64 加载器已完整跑通：从读文件头、映射段、解析 dynamic，到符号查找、重定位、触发构造，最终用自写的 dlsym 取到 add 的地址并调用成功，结果与系统 dlopen 一致。这套流程只覆盖了单个 SO 的加载与调用，析构、TLS、符号版本等一律略去，外部符号也仍借助系统查询兜底，算不上完全脱离。这份实现是后续理解加壳与脱壳的地基。匿名内存加载、抹除 ELF 头、运行时解密段等对抗手法，都建立在这条链路之上 留待下一篇 欢迎大佬对本文误述内容进行勘正与讨论。

## 参考

https://bbs.kanxue.com/thread-269891.htm#msg_header_h2_2

https://bbs.kanxue.com/thread-282316.htm#msg_header_h2_5

https://bbs.kanxue.com/thread-287254.htm#msg_header_h2_4

‍

---

# 回复

## 回复 by 你瞒我瞒 (#2)

*2026-7-17 17:08*

厉害啊

## 回复 by mb_ldbucrik (#3)

*2026-7-17 23:33*

向大佬学习

## 回复 by Zepp7289 (#4)

*2026-7-18 14:53*

自实现linker最后再调用一次dlopen是为了啥，那不是又走了一遍系统link

## 回复 by 学计算机睡觉 (#5)

*2026-7-18 17:31*

看看

## 回复 by SomeMx (#6)

*2026-7-18 17:37*

过来瞧瞧

## 回复 by iBa0 (#7)

*2026-7-18 22:17*

去

## 回复 by 珍惜Any (#8)

*2026-7-19 00:31*

这个支持的版本是多少，我最近想搞一个，就是ptrace注入so文件不在目标进程调用dlopen打开，防止目标app hook dlopen被检测。

## 回复 by mb_urzqsoer (#9)

*2026-7-19 00:45*

66666666666

## 回复 by 北袅 (#10)

*2026-7-19 13:59*

Mylinker linker;

    soinfo* si = linker.dlopen(path.c_str());
    if (!si) {
        LOG("my dlopen failed");
        return;
    }这里走的是自己申明的linker

## 回复 by 北袅 (#11)

*2026-7-19 14:00*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  Zepp7289](https://bbs.kanxue.com/user-993285.htm)
>  自实现linker最后再调用一次dlopen是为了啥，那不是又走了一遍系统link
>

    Mylinker linker;

    soinfo* si = linker.dlopen(path.c_str());
    if (!si) {
        LOG("my dlopen failed");
        return;
    }这里走的是自己申明的linker

## 回复 by 北袅 (#12)

*2026-7-19 14:00*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>  这个支持的版本是多少，我最近想搞一个，就是ptrace注入so文件不在目标进程调用dlopen打开，防止目标app hook dlopen被检测。
>

这套方案能跑安卓12,再高点版本（15、16）或者稍微复杂点so需要做一些细节上的调整，page size、soinfo结构、析构...... 唯一用到一个dlsym也可以用自解析maps去定位外部符号

## 回复 by 珍惜Any (#13)

*2026-7-19 14:23*

>
> [北袅](https://bbs.kanxue.com/user-951483.htm)
>  这套方案能跑安卓12,再高点版本（15、16）或者稍微复杂点so需要做一些细节上的调整，page size、soinfo结构、析构...... 唯一用到一个dlsym也可以用自解析maps去定位外部符 ...
>

那不行 ，我需要一个12+都可以兼容的，你让AI看看源码，看看能不能兼容一下。

## 回复 by mb_bvvcoitr (#14)

*2026-7-19 17:55*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>  这个支持的版本是多少，我最近想搞一个，就是ptrace注入so文件不在目标进程调用dlopen打开，防止目标app hook dlopen被检测。
>

你看下rezygisk有个远程的csoloader。zn也有，但是不能开源。主要就是自行重定位。

## 回复 by uni7corn (#15)

*2026-7-20 23:31*

感谢分享

## 回复 by mb_audxeeaj (#16)

*2026-7-21 17:04*

向大佬学习

## 回复 by 丶咖啡猫丶 (#17)

*2026-7-22 19:04*

666

## 回复 by Thehepta (#18)

*2026-7-22 19:35*

1

## 回复 by koflfy (#19)

*2026-7-23 15:43*

mark

## 回复 by CheRevir (#20)

*2026-7-23 16:42*

666

## 回复 by mb_euhyowpw (#21)

*2026-7-23 17:35*

666

## 回复 by mb_jhohnbzu (#22)

*2026-7-23 18:19*

666

## 回复 by 櫬木汐 (#23)

*2026-7-23 18:28*

111

## 回复 by xxjj678 (#24)

*2026-7-23 18:51*

6666

## 回复 by mb_cbgtaveo (#25)

*2026-7-23 21:38*

66666666

## 回复 by 恋一世的爱 (#26)

*2026-7-24 08:45*

大神，如果只想用到一个so，可以吗，因为你这样需要用2个so，一个是安装器，一个是要干坏事的so，比较麻烦，可以集成到一个so吗，load后再自定义load自己，然后卸载原来自己那个

## 回复 by GEKEZYX (#27)

*2026-7-24 09:46*

666

## 回复 by mb_ugnawvja (#28)

*2026-7-24 10:38*

666

## 回复 by 北袅 (#29)

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  恋一世的爱](https://bbs.kanxue.com/user-825246.htm)
>  大神，如果只想用到一个so，可以吗，因为你这样需要用2个so，一个是安装器，一个是要干坏事的so，比较麻烦，可以集成到一个so吗，load后再自定义load自己，然后卸载原来自己那个
>

理论上是可以的 业务so被编译好后 在当前项目里是以本地文件形式存在的 loader通过fd去open这个文件 再mmap到内存 而你说的就是不希望业务so以文件形式出现在本地 那就可以把业务so的字节内容直接写死到数组里 但是这里也就不能走fd和文件映射 嘚改成匿名内存 卸载的话是做不了的 mylinker的加载逻辑和业务so的字节数组是在同一个壳so里的

## 回复 by 阳光宝贝 (#30)

感谢分享，学习一下

## 回复 by niama (#31)

6666

## 回复 by Kill_Log (#32)

6666

## 回复 by 看风听雨 (#33)

66666

## 回复 by mb_ifkqwpjq (#34)

6666666666666

## 回复 by 有的是钱啊 (#35)

111

## 回复 by mb_uvyukvot (#36)

666

## 回复 by 简单的简单 (#37)

666

## 回复 by jsjsj (#38)

77777

## 回复 by mb_irhdtnzm (#39)

1

## 回复 by huangbof (#40)

66666666

## 回复 by Je2em1ah (#41)

1
