---
title: frida hook init_array自吐新解
url: https://bbs.kanxue.com/thread-280135.htm
tid: 280135
author: seeeseee
date: '2024-01-08'
tags: [Android安全, 逆向分析, 工具脚本]
crawled_at: '2026-07-31T14:33:58+08:00'
replies: 11
---

# 前言

frida的`CModule`是一个极其强大的模块，本文将使用`CModule`来完成`init_array`的信息输出

简单来说，就是借助`CModule`对`soinfo`结构体进行解析

# 实现

经过对比分析历代soinfo结构体的定义，可以确定从Android 8 ~ 14，结构体中`init_array`的位置都很稳定

于是通过下面的头文件中提取必要的内容，在CModule中定义一个soinfo结构体，这样frida就能自动完成相关偏移的处理

- <http://aosp.app/android-14.0.0_r1/xref/bionic/libc/include/link.h>
- <http://aosp.app/android-14.0.0_r1/xref/bionic/libc/kernel/uapi/asm-generic/int-ll64.h>
- <http://aosp.app/android-14.0.0_r1/xref/bionic/libc/kernel/uapi/linux/elf.h>
- <http://aosp.app/android-14.0.0_r1/xref/bionic/linker/linker_soinfo.h>

接着定义一个函数，接受一个`soinfo`指针参数和一个callback函数，优雅地输出`init_array`信息

| 123 | `void` `tell_init_info(soinfo* ptr,` `void` `(*cb)(``int``,` `void``*,` `void``*)) {``cb(ptr->init_array_count_, ptr->init_array_, ptr->init_func_);``}` |
|-|-|

那么哪里最早能获取到`soinfo`指针呢？答案是`soinfo->call_constructors`，这个函数符号一直很稳定

为了获取soname，则选择主动调用`soinfo->get_soname`，这个函数符号同样很稳定

- __dl__ZN6soinfo17call_constructorsEv
- __dl__ZNK6soinfo10get_sonameEv

在callback回到frida hook后，再借助frida的`JavaScript API`解析`init_array`数组，代码片段如下：

| 12345678910111213141516 | `Interceptor.attach(call_constructors_addr,{``onEnter:` `function``(args){``let soinfo = args[0];``let soname = get_soname(soinfo).readCString();``tell_init_info(soinfo,` `new` `NativeCallback((count, init_array_ptr, init_func) => {``console.log(`[call_constructors] ${soname} count:${count}`);``console.log(`[call_constructors] init_array_ptr:${init_array_ptr}`);``console.log(`[call_constructors] init_func:${init_func} -> ${get_addr_info(init_func)}`);``for` `(let index = 0; index < count; index++) {``let init_array_func = init_array_ptr.add(Process.pointerSize * index).readPointer();``let func_info = get_addr_info(init_array_func);``console.log(`[call_constructors] init_array:${index} ${init_array_func} -> ${func_info}`);``}``},` `"void"``, [``"int"``,` `"pointer"``,` `"pointer"``]));``}``});` |
|-|-|

Tips: `CModule`对象是有作用域的，所以通常赋给一个全局变量，以保证一直可用，否则可能引起崩溃

其他：对于Android 5/6/7，同样可以这样处理，据对比差异主要是`ElfW(Addr) base;`之前会多一个`ElfW(Addr) entry;`

效果示例：

![image](https://bbs.kanxue.com/upload/attach/202401/941366_84XTD5FHKJM2RXC.png)

![image](https://bbs.kanxue.com/upload/attach/202401/941366_M26XVGPM5BQDC7B.png)

脚本已完成32/64位的兼容，理论上适用于Android 8 ~ 14，测试Android 10通过

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257 | `let cm_include = ```#include <stdio.h>``#include <gum/gumprocess.h>```` `let cm_code = ```#if defined(__LP64__)``#define USE_RELA 1``#endif` `// http://aosp.app/android-14.0.0_r1/xref/bionic/libc/include/link.h``#if defined(__LP64__)``#define ElfW(type) Elf64_ ## type``#else``#define ElfW(type) Elf32_ ## type``#endif` `// http://aosp.app/android-14.0.0_r1/xref/bionic/libc/kernel/uapi/asm-generic/int-ll64.h``typedef signed char __s8;``typedef unsigned char __u8;``typedef signed short __s16;``typedef unsigned short __u16;``typedef signed int __s32;``typedef unsigned int __u32;``typedef signed long long __s64;``typedef unsigned long long __u64;` `// http://aosp.app/android-14.0.0_r1/xref/bionic/libc/kernel/uapi/linux/elf.h``typedef __u32 Elf32_Addr;``typedef __u16 Elf32_Half;``typedef __u32 Elf32_Off;``typedef __s32 Elf32_Sword;``typedef __u32 Elf32_Word;``typedef __u64 Elf64_Addr;``typedef __u16 Elf64_Half;``typedef __s16 Elf64_SHalf;``typedef __u64 Elf64_Off;``typedef __s32 Elf64_Sword;``typedef __u32 Elf64_Word;``typedef __u64 Elf64_Xword;``typedef __s64 Elf64_Sxword;` `typedef struct dynamic {``Elf32_Sword d_tag;``union {``Elf32_Sword d_val;``Elf32_Addr d_ptr;``} d_un;``} Elf32_Dyn;``typedef struct {``Elf64_Sxword d_tag;``union {``Elf64_Xword d_val;``Elf64_Addr d_ptr;``} d_un;``} Elf64_Dyn;``typedef struct elf32_rel {``Elf32_Addr r_offset;``Elf32_Word r_info;``} Elf32_Rel;``typedef struct elf64_rel {``Elf64_Addr r_offset;``Elf64_Xword r_info;``} Elf64_Rel;``typedef struct elf32_rela {``Elf32_Addr r_offset;``Elf32_Word r_info;``Elf32_Sword r_addend;``} Elf32_Rela;``typedef struct elf64_rela {``Elf64_Addr r_offset;``Elf64_Xword r_info;``Elf64_Sxword r_addend;``} Elf64_Rela;``typedef struct elf32_sym {``Elf32_Word st_name;``Elf32_Addr st_value;``Elf32_Word st_size;``unsigned char st_info;``unsigned char st_other;``Elf32_Half st_shndx;``} Elf32_Sym;``typedef struct elf64_sym {``Elf64_Word st_name;``unsigned char st_info;``unsigned char st_other;``Elf64_Half st_shndx;``Elf64_Addr st_value;``Elf64_Xword st_size;``} Elf64_Sym;``typedef struct elf32_phdr {``Elf32_Word p_type;``Elf32_Off p_offset;``Elf32_Addr p_vaddr;``Elf32_Addr p_paddr;``Elf32_Word p_filesz;``Elf32_Word p_memsz;``Elf32_Word p_flags;``Elf32_Word p_align;``} Elf32_Phdr;``typedef struct elf64_phdr {``Elf64_Word p_type;``Elf64_Word p_flags;``Elf64_Off p_offset;``Elf64_Addr p_vaddr;``Elf64_Addr p_paddr;``Elf64_Xword p_filesz;``Elf64_Xword p_memsz;``Elf64_Xword p_align;``} Elf64_Phdr;` `// http://aosp.app/android-14.0.0_r1/xref/bionic/linker/linker_soinfo.h``typedef void (*linker_dtor_function_t)();``typedef void (*linker_ctor_function_t)(int, char**, char**);` `#if defined(__work_around_b_24465209__)``#define SOINFO_NAME_LEN 128``#endif` `typedef struct {``#if defined(__work_around_b_24465209__)``char old_name_[SOINFO_NAME_LEN];``#endif``const ElfW(Phdr)* phdr;``size_t phnum;``#if defined(__work_around_b_24465209__)``ElfW(Addr) unused0;` `// DO NOT USE, maintained for compatibility.``#endif``ElfW(Addr) base;``size_t size;` `#if defined(__work_around_b_24465209__)``uint32_t unused1;` `// DO NOT USE, maintained for compatibility.``#endif` `ElfW(Dyn)* dynamic;` `#if defined(__work_around_b_24465209__)``uint32_t unused2;` `// DO NOT USE, maintained for compatibility``uint32_t unused3;` `// DO NOT USE, maintained for compatibility``#endif` `void* next;``uint32_t flags_;` `const char* strtab_;``ElfW(Sym)* symtab_;` `size_t nbucket_;``size_t nchain_;``uint32_t* bucket_;``uint32_t* chain_;` `#if !defined(__LP64__)``ElfW(Addr)** unused4;` `// DO NOT USE, maintained for compatibility``#endif` `#if defined(USE_RELA)``ElfW(Rela)* plt_rela_;``size_t plt_rela_count_;` `ElfW(Rela)* rela_;``size_t rela_count_;``#else``ElfW(Rel)* plt_rel_;``size_t plt_rel_count_;` `ElfW(Rel)* rel_;``size_t rel_count_;``#endif` `linker_ctor_function_t* preinit_array_;``size_t preinit_array_count_;` `linker_ctor_function_t* init_array_;``size_t init_array_count_;``linker_dtor_function_t* fini_array_;``size_t fini_array_count_;` `linker_ctor_function_t init_func_;``linker_dtor_function_t fini_func_;``} soinfo;` `void tell_init_info(soinfo* ptr, void (*cb)(int, void*, void*)) {``cb(ptr->init_array_count_, ptr->init_array_, ptr->init_func_);``}```` `let cm =` `null``;``let tell_init_info =` `null``;` `function` `setup_cmodule() {``if` `(Process.pointerSize == 4) {``cm_code = cm_include +` `"#define __work_around_b_24465209__ 1"` `+ cm_code;``}` `else` `{``cm_code = cm_include +` `"#define __LP64__ 1"` `+ cm_code;``}``cm =` `new` `CModule(cm_code, {});``tell_init_info =` `new` `NativeFunction(cm.tell_init_info,` `"void"``, [``"pointer"``,` `"pointer"``]);``}` `function` `get_addr_info(addr) {``let mm =` `new` `ModuleMap();``let info = mm.find(addr);``if` `(info ==` `null``)` `return` `"null"``;``return` ``[${info.name} + ${addr.sub(info.base)}]`;``}` `function` `hook_call_constructors() {``let get_soname =` `null``;``let call_constructors_addr =` `null``;``let hook_call_constructors_addr =` `true``;` `let linker =` `null``;``if` `(Process.pointerSize == 4) {``linker = Process.findModuleByName(``"linker"``);``}` `else` `{``linker = Process.findModuleByName(``"linker64"``);``}` `let symbols = linker.enumerateSymbols();``for` `(let index = 0; index < symbols.length; index++) {``let symbol = symbols[index];``if` `(symbol.name ==` `"__dl__ZN6soinfo17call_constructorsEv"``) {``call_constructors_addr = symbol.address;``}` `else` `if` `(symbol.name ==` `"__dl__ZNK6soinfo10get_sonameEv"``) {``get_soname =` `new` `NativeFunction(symbol.address,` `"pointer"``, [``"pointer"``]);``}``}``if` `(hook_call_constructors_addr && call_constructors_addr && get_soname) {``Interceptor.attach(call_constructors_addr,{``onEnter:` `function``(args){``let soinfo = args[0];``let soname = get_soname(soinfo).readCString();``tell_init_info(soinfo,` `new` `NativeCallback((count, init_array_ptr, init_func) => {``console.log(`[call_constructors] ${soname} count:${count}`);``console.log(`[call_constructors] init_array_ptr:${init_array_ptr}`);``console.log(`[call_constructors] init_func:${init_func} -> ${get_addr_info(init_func)}`);``for` `(let index = 0; index < count; index++) {``let init_array_func = init_array_ptr.add(Process.pointerSize * index).readPointer();``let func_info = get_addr_info(init_array_func);``console.log(`[call_constructors] init_array:${index} ${init_array_func} -> ${func_info}`);``}``},` `"void"``, [``"int"``,` `"pointer"``,` `"pointer"``]));``}``});``}``}` `function` `main(){``setup_cmodule();``hook_call_constructors();``}` `setImmediate(main);` `// frida -U -f pkg_name -l hook.js -o hook.log` |
|-|-|

---

# 回复

## 回复 by 陈可牛 (#2)

*2024-1-8 00:59*

感谢大佬的分享~~~

## 回复 by mb_ldbucrik (#3)

*2024-1-8 09:11*

感谢分享yyds

## 回复 by misskings (#4)

*2024-1-8 11:47*

![image](https://bbs.kanxue.com/view/img/face/13.gif)再来个样本就好了

## 回复 by mb_fssslkzs (#5)

*2024-1-8 13:30*

tql

## 回复 by 秋狝 (#6)

*2024-1-8 13:51*

感谢分享

## 回复 by 龙飞雪 (#7)

*2024-1-8 17:11*

感谢分享-frida hook init_array自吐新解.![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by seeeseee (#8)

*2024-1-8 17:11*

>
> [misskings](https://bbs.kanxue.com/user-659397.htm)
>
>  [em_13]再来个样本就好了
>
>

随便拿个有init_array测就可以啦，默认是打印所有加载库的。

## 回复 by 本菜很懒 (#9)

*2024-1-9 10:50*

强大

## 回复 by xxRea (#10)

*2024-4-12 15:14*

感谢分享-frida hook init_array自吐新解

## 回复 by zx_994305 (#11)

*2024-4-12 15:42*

strong

## 回复 by qig (#12)

*2024-5-18 14:54*

强大，我这里有一个apk ,init_array 里面有个thread_create的方法，经过测试，的确可以解析出来.

上传的附件：
- anti_source.apk

（1.41MB，20次下载）
