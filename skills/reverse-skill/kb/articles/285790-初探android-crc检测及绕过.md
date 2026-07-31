---
title: '[原创]初探android crc检测及绕过'
url: https://bbs.kanxue.com/thread-285790.htm
tid: 285790
author: 九天666
date: '2025-02-28'
tags: [Android安全, 原创, 基础理论, 逆向分析, 工具脚本]
crawled_at: '2026-07-31T15:57:22+08:00'
replies: 396
---

# 一、前言

在开始之前先说下什么是crc检测,通俗点讲就是,把本地文件中的数据和内存中的数据进行crc计算得到的结果进行比较,来校验结果是否一致,不一致则判定数据被篡改。

举个例子:以libc.so为目标so,当我们第一次用frida以spwan的方式注入hook 时,未对libc.so的函数进行hook的话,app未退出,一旦我们对libc.so中的函数或指令进行了修改注入(不考虑inline hoook的因素影响),app便直接崩溃退出,这种情况基本就是检测到了数据被篡改,也就是crc检测。

基本的介绍到这里,下面开始对crc相关途径的检测进行分析,以及如何去绕过。

本次分析以libc.so为目标,以下的绕过都是用frida去处理。

# 二、分析环境

app是我总结的一部分crc检测,会把链接放置在结尾。
 ![image](https://bbs.kanxue.com/upload/attach/202502/947335_PHEFHNPMNK69WJ4.webp)
frida版本: 16.5.9
目标app: LinkerDemo
分析so: libc.so
ELF工具:010Editor
arm平台: arm64

# 三、分析及绕过

## (一) 检测种类

目前crc的检测大的方向分两种:
1.本地文件与所属app的/proc/{id}/maps文件中so的内存范围作比较
2.本地文件与linker中获取到的so的内存范围作比较

## (二)本地文件与maps内存的校验

先说一下此校验方法的相关逻辑
描述:提取本地文件/apex/com.android.runtime/lib64/bionic/libc.so的可执行段数据和app在/proc/{id}/maps下映射的libc.so可执行段内存进行crc校验

### 1.用010Editor打开libc.so

 ![image](https://bbs.kanxue.com/upload/attach/202502/947335_F8XY5KH27U4JEP8.webp)
获取可执行段表中的 p_offset(在文件中的偏移)和 p_filesz(在文件中的大小)。后续都是以这个为参照物与内存进行crc校验

### 2.获取maps内存中libc.so的可执行段

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_885BJPFFUK4YMMY.webp)
(正常来说只有一行r-xp段，因为我使用了frida,所以会出现这种内存布局)
提取出里面带有x的内存段数据。

### 3.校验

最后通过相关算法计算出两种途径获取到的内存结果进行比较。
算法一般都是crc32，当然个例可能会使用其他的算法，比如md5,aes等等,很少见的。

### 4.hook现象

打开app,点击libc maps crc，可以在控制台看到如下输出:
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_YMVDDRQ7VQG7NX2.webp)
此时我们的环境是正常的。接着我们用frida注入,对libc.so中的pthread_create方法进行hook,得到以下输出:
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_38PBZXBZE2UTBN5.webp)
可以很明显的看出内存中可执行段的crc值与文件中可执行的不一致，并且检测出了环境是hook的。

### 5.绕过

针对上述的检测，我们可以在maps中模拟一段可执行段数据,并把libc.so原本的可执行段名称给抹去,变为匿名内存。最后app获取到的maps内存范围就是我们模拟的一段数据

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576 | `function hiddenSoExecSegmentInMaps(so_path) {``/``/`      `/``apex``/``com.android.runtime``/``lib64``/``bionic``/``libc.so``let mmap_addr` `=` `Module.findExportByName(``"libc.so"``,` `"mmap"``);``let mmapFunc` `=` `new NativeFunction(mmap_addr,` `'pointer'``, [``'pointer'``,` `'int'``,` `'int'``,` `'int'``,` `'int'``,` `'int'``])` `let munmap_addr` `=` `Module.findExportByName(``"libc.so"``,` `"munmap"``);``let munmapFunc` `=` `new NativeFunction(munmap_addr,` `'int'``, [``'pointer'``,` `'int'``])` `let mremap_addr` `=` `Module.findExportByName(``"libc.so"``,` `"mremap"``);``let mremapFunc` `=` `new NativeFunction(mremap_addr,` `'pointer'``, [``'pointer'``,` `'int64'``,` `'int64'``,` `'int64'``,` `'pointer'``])` `let open_addr` `=` `Module.findExportByName(``"libc.so"``,` `"open"``);``var openFunc` `=` `new NativeFunction(open_addr,` `'int'``, [``'pointer'``,` `'int'``]);` `let memset_addr` `=` `Module.findExportByName(``"libc.so"``,` `"memset"``);``var memsetFunc` `=` `new NativeFunction(memset_addr,` `'pointer'``, [``'pointer'``,` `'int'``,` `'int'``])` `let close_addr` `=` `Module.findExportByName(``"libc.so"``,` `"close"``);``var closeFunc` `=` `new NativeFunction(close_addr,` `'int'``, [``'int'``])` `const parts` `=` `so_path.split(``'/'``);``const so_name` `=` `parts.pop();``let soExecSegmentRangeFromMaps` `=` `findSoExecSegmentRangeFromMaps(so_name);``let startAddress` `=` `soExecSegmentRangeFromMaps.base;``let size` `=` `soExecSegmentRangeFromMaps.size;` `if` `(startAddress` `=``=``=` `0` `\|\| size` `=``=``=` `0``) {``console.log(``"可执行段未找到:"``, startAddress, size)``return``;``}` `let soExecSegmentFromFile` `=` `findSoExecSegmentFromFile(so_path);` `/``/``创建匿名内存,临时存储so可执行段内存``let new_addr` `=` `mmapFunc(ptr(``-``1``), size,` `7``,` `0x20` `\|` `2``,` `-``1``,` `0``);``/``/``0x20``:匿名内存标识符(MAP_ANONYMOUS),` `2``:私有(MAP_PRIVATE)``console.log(``"创建的可执行段匿名内存起始地址:"` `+` `new_addr);` `/``/``把so可执行段内存复制到创建的匿名内存中去``Memory.copy(new_addr, startAddress, size);``console.log(``"复制完毕"``)` `/``/``调整so,使传入的so可执行段内存变成匿名内存``let ret` `=` `mremapFunc(new_addr, size, size,` `1` `\|` `2``, startAddress);``if` `(ret` `=``=``=` `-``1``) {``console.log(``"mremap  调整失败"``)``return``;``}``console.log(``"匿名目标so可执行段完成 ret:"` `+` `ret)` `/``/` `打开需要模拟的文件路径，用于后续在maps中生成指定名称的内存区域``let moniter_path` `=` `so_path;``let moniter_path_addr` `=` `Memory.allocUtf8String(moniter_path);``var fd` `=` `openFunc(moniter_path_addr,` `0``);``if` `(fd` `=``=``=` `-``1``) {``console.log(``"open "` `+` `moniter_path` `+` `" is error"``)``return` `-``1``;``}` `/``/``在maps中创建传入so路径名称的内存区域``let target_addr` `=` `mmapFunc(ptr(``-``1``), size,` `7``,` `2``, fd,` `0``);``console.log(``"模拟的可执行段内存起始地址:"` `+` `target_addr);` `closeFunc(fd)` `/``/``给创建的so内存区域全部置``0``memsetFunc(target_addr,` `0``, size);` `/``/``把so文件中获取的可执行段内存复制到创建的so名称的内存区域中``Memory.copy(target_addr, soExecSegmentFromFile.start, soExecSegmentFromFile.size)``Memory.protect(target_addr, size,` `"r-x"``);` `/``/``卸载映射的匿名内存``/``/` `munmapFunc(new_addr, size);``console.log(``"maps中隐藏可执行段完成"``)` `}` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_6CRZUQJWF63NSMW.webp)
注入上述代码后再次点击按钮看控制台输出:
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_WQ2A7TZ9JRQN48X.webp)
可以看到两种方式获取到的值一致了，环境也是安全的了。

这里面主要使用到了mmap在maps中映射一段名称为libc.so的数据,用mremap把原本的可执行段数据给设置为匿名内存
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_2HBZN8KND5MW62G.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_MT7S9BN8WDVYQHQ.webp)
这里就可以看到maps中libc.so的可执行段已设置为匿名内存,并且map中也有我们模拟的可执行段内存。

## (三)本地文件与Linker获取的内存校验

本地文件获取的方式不再赘述了，直接看如何从Linker中获取内存。

### 1.获取libc.so soinfo结构体

linker作为so加载器,里面存放了所有已经加载的so,并把这些已经加载的so会依次存放进solist变量中,solist存储了所有so的soinfo结构体,它是一个soinfo结构体数组,我们可以从solist中获取到自己想要的so。

那么如何获取到libc.so的结构体呢?
带着这个疑问我们先了解下soinfo的相关结构组成。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274275 | `struct soinfo {``#if defined(__work_around_b_24465209__)``private:``char old_name_[SOINFO_NAME_LEN];``#endif``public:``const ElfW(Phdr)``*` `phdr;` `/``/``0``size_t phnum;` `/``/``1``#if defined(__work_around_b_24465209__)``ElfW(Addr) unused0;` `/``/` `DO NOT USE, maintained` `for` `compatibility.``#endif``ElfW(Addr) base;` `/``/``2``size_t size;` `/``/``3` `#if defined(__work_around_b_24465209__)``uint32_t unused1;` `/``/` `DO NOT USE, maintained` `for` `compatibility.``#endif` `ElfW(Dyn)``*` `dynamic;` `/``/``4` `#if defined(__work_around_b_24465209__)``uint32_t unused2;` `/``/` `DO NOT USE, maintained` `for` `compatibility``uint32_t unused3;` `/``/` `DO NOT USE, maintained` `for` `compatibility``#endif` `soinfo``*` `next``;` `/``/``5``private:``uint32_t flags_;` `/``/``6` `const char``*` `strtab_;` `/``/``7` `.dynstr``ElfW(Sym)``*` `symtab_;` `/``/``8`     `.dynsym` `size_t nbucket_;``size_t nchain_;``uint32_t``*` `bucket_;` `/``/``11``uint32_t``*` `chain_;` `/``/``12` `#if defined(__mips__) \|\| !defined(__LP64__)``/``/` `This` `is` `only used by mips` `and` `mips64, but needs to be here` `for``/``/` `all` `32``-``bit architectures to preserve binary compatibility.``ElfW(Addr)``*``*` `plt_got_;` `/``/``arm64未被使用``#endif` `#if defined(USE_RELA)``ElfW(Rela)``*` `plt_rela_;` `/``/``.real.plt` `13``size_t plt_rela_count_;` `ElfW(Rela)``*` `rela_;` `/``/``15` `/``/``real.dyn``size_t rela_count_;` `/``/``16``#else``ElfW(Rel)``*` `plt_rel_;` `size_t plt_rel_count_;` `ElfW(Rel)``*` `rel_;` `size_t rel_count_;` `#endif` `linker_ctor_function_t``*` `preinit_array_;``/``/``空` `17``size_t preinit_array_count_;``/``/``空` `18` `linker_ctor_function_t``*` `init_array_;``size_t init_array_count_;``linker_dtor_function_t``*` `fini_array_;``size_t fini_array_count_;` `linker_ctor_function_t init_func_;` `/``/``空` `23``linker_dtor_function_t fini_func_;``/``/`    `空` `24` `#if defined(__arm__)  //arm64不进入``public:``/``/` `ARM EABI section used` `for` `stack unwinding.``uint32_t``*` `ARM_exidx;``size_t ARM_exidx_count;``private:``#elif defined(__mips__)//arm64不进入``uint32_t mips_symtabno_;``uint32_t mips_local_gotno_;``uint32_t mips_gotsym_;``bool` `mips_relocate_got(const VersionTracker& version_tracker,``const soinfo_list_t& global_group,``const soinfo_list_t& local_group);``#if !defined(__LP64__)//arm64不进入``bool` `mips_check_and_adjust_fp_modes();``#endif``#endif``size_t ref_count_;` `/``/``25``public:``link_map link_map_head;` `/``/``26` `27` `28` `29` `30``/``/` `struct link_map {``/``/`     `ElfW(Addr) l_addr;``/``/`     `char``*` `l_name;``/``/`     `ElfW(Dyn)``*` `l_ld;``/``/`     `struct link_map``*` `l_next;``/``/`     `struct link_map``*` `l_prev;``/``/` `};``bool` `constructors_called;` `/``/` `When you read a virtual address` `from` `the ELF` `file``, add this``/``/` `value to get the corresponding address` `in` `the process' address space.``ElfW(Addr) load_bias;` `/``/``32` `#if !defined(__LP64__)``bool` `has_text_relocations;``#endif``bool` `has_DT_SYMBOLIC;` `public:``soinfo(android_namespace_t``*` `ns, const char``*` `name, const struct stat``*` `file_stat,``off64_t file_offset,` `int` `rtld_flags);``~soinfo();` `void call_constructors();``void call_destructors();``void call_pre_init_constructors();``bool` `prelink_image();``bool` `link_image(const soinfo_list_t& global_group, const soinfo_list_t& local_group,``const android_dlextinfo``*` `extinfo, size_t``*` `relro_fd_offset);``bool` `protect_relro();` `void add_child(soinfo``*` `child);``void remove_all_links();` `ino_t get_st_ino() const;``dev_t get_st_dev() const;``off64_t get_file_offset() const;` `uint32_t get_rtld_flags() const;``uint32_t get_dt_flags_1() const;``void set_dt_flags_1(uint32_t dt_flags_1);` `soinfo_list_t& get_children();``const soinfo_list_t& get_children() const;` `soinfo_list_t& get_parents();` `bool` `find_symbol_by_name(SymbolName& symbol_name,``const version_info``*` `vi,``const ElfW(Sym)``*``*` `symbol) const;` `ElfW(Sym)``*` `find_symbol_by_address(const void``*` `addr);``ElfW(Addr) resolve_symbol_address(const ElfW(Sym)``*` `s) const;` `const char``*` `get_string(ElfW(Word) index) const;``bool` `can_unload() const;``bool` `is_gnu_hash() const;` `bool` `inline has_min_version(uint32_t min_version __unused) const {``#if defined(__work_around_b_24465209__)``return` `(flags_ & FLAG_NEW_SOINFO) !``=` `0` `&& version_ >``=` `min_version;``#else``return` `true;``#endif``}` `bool` `is_linked() const;``bool` `is_linker() const;``bool` `is_main_executable() const;` `void set_linked();``void set_linker_flag();``void set_main_executable();``void set_nodelete();` `size_t increment_ref_count();``size_t decrement_ref_count();``size_t get_ref_count() const;` `soinfo``*` `get_local_group_root() const;` `void set_soname(const char``*` `soname);``const char``*` `get_soname() const;``const char``*` `get_realpath() const;``const ElfW(Versym)``*` `get_versym(size_t n) const;``ElfW(Addr) get_verneed_ptr() const;``size_t get_verneed_cnt() const;``ElfW(Addr) get_verdef_ptr() const;``size_t get_verdef_cnt() const;` `int` `get_target_sdk_version() const;` `void set_dt_runpath(const char` `*``);``const std::vector<std::string>& get_dt_runpath() const;``android_namespace_t``*` `get_primary_namespace();``void add_secondary_namespace(android_namespace_t``*` `secondary_ns);``android_namespace_list_t& get_secondary_namespaces();` `soinfo_tls``*` `get_tls() const;` `void set_mapped_by_caller(``bool` `reserved_map);``bool` `is_mapped_by_caller() const;` `uintptr_t get_handle() const;``void generate_handle();``void``*` `to_handle();` `private:``bool` `is_image_linked() const;``void set_image_linked();` `bool` `elf_lookup(SymbolName& symbol_name, const version_info``*` `vi, uint32_t``*` `symbol_index) const;``ElfW(Sym)``*` `elf_addr_lookup(const void``*` `addr);``bool` `gnu_lookup(SymbolName& symbol_name, const version_info``*` `vi, uint32_t``*` `symbol_index) const;``ElfW(Sym)``*` `gnu_addr_lookup(const void``*` `addr);` `bool` `lookup_version_info(const VersionTracker& version_tracker, ElfW(Word) sym,``const char``*` `sym_name, const version_info``*``*` `vi);` `template<typename ElfRelIteratorT>``bool` `relocate(const VersionTracker& version_tracker, ElfRelIteratorT&& rel_iterator,``const soinfo_list_t& global_group, const soinfo_list_t& local_group);``bool` `relocate_relr();``void apply_relr_reloc(ElfW(Addr) offset);` `private:``/``/` `This part of the structure` `is` `only available``/``/` `when FLAG_NEW_SOINFO` `is` `set` `in` `this``-``>flags.``uint32_t version_;` `/``/` `version >``=` `0``dev_t st_dev_;``ino_t st_ino_;` `/``/` `dependency graph``soinfo_list_t children_;``soinfo_list_t parents_;` `/``/` `version >``=` `1``off64_t file_offset_;``uint32_t rtld_flags_;``uint32_t dt_flags_1_;``size_t strtab_size_;` `/``/` `version >``=` `2` `size_t gnu_nbucket_;``uint32_t``*` `gnu_bucket_;``uint32_t``*` `gnu_chain_;``uint32_t gnu_maskwords_;``uint32_t gnu_shift2_;``ElfW(Addr)``*` `gnu_bloom_filter_;` `soinfo``*` `local_group_root_;` `uint8_t``*` `android_relocs_;``size_t android_relocs_size_;` `const char``*` `soname_;``std::string realpath_;` `const ElfW(Versym)``*` `versym_;` `ElfW(Addr) verdef_ptr_;``size_t verdef_cnt_;` `ElfW(Addr) verneed_ptr_;``size_t verneed_cnt_;` `int` `target_sdk_version_;` `/``/` `version >``=` `3``std::vector<std::string> dt_runpath_;``android_namespace_t``*` `primary_namespace_;``android_namespace_list_t secondary_namespaces_;``uintptr_t handle_;` `friend soinfo``*` `get_libdl_info(const char``*` `linker_path, const soinfo& linker_si);` `/``/` `version >``=` `4``ElfW(Relr)``*` `relr_;``size_t relr_count_;` `/``/` `version >``=` `5``std::unique_ptr<soinfo_tls> tls_;``std::vector<TlsDynamicResolverArg> tlsdesc_args_;``}` |
|-|-|

这里我已经标注了相关变量在内存中的指针索引。里面描述了so的基址和一些节表和大量的方法。当然这些不是我们这里的关注重点,我们只需要多关注以下的变量:

| 1234567891011 | `phdr:程序头表(段表)``base:   so基址``size:   so大小``dynamic: .dynamic节``next``： 下一个soinfo结构体``strtab_： .dynstr节``symtab_: .dynsym节``plt_rela_: .real.plt节``rela_：  .real.dyn节``link_map_head: 存储有so的基址和名字(dl_iterate_phdr方法可以获取)``load_bias: so基址` |
|-|-|

### 2.hook现象

检测逻辑:
lib base mem crc：获取本地文件的可执行段的偏移地址,计算soinfo结构体中的base与可执行段偏移地址的和,得到内存中的可执行段地址,再取内存中可执行段数据和本地文件可执行段数据作比较。
lib func mem crc: 通过dl_iterate_phdr方法获取到linker map,取linker map中的dlpi_addr获取到so的基址,获取本地文件的可执行段的偏移地址,计算基址和偏移的和,通过再取内存中可执行段数据和本地文件可执行段数据作比较。

分别点击libc base mem crc按钮和libc func mem crc按钮，控制台输出如下
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_ZNCW8T898HNK6RR.webp)

### 3.绕过

针对上述的检测，我们可以把soinfo结构体中的base,和link_map_head指针指向我们在maps中映射的地址,达到绕过检测的目的。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657 | `function hiddenSobaseInMem(so_path) {``/``/`  `/``apex``/``com.android.runtime``/``lib64``/``bionic``/``libc.so``let mmap_addr` `=` `Module.findExportByName(``"libc.so"``,` `"mmap"``);``let mmapFunc` `=` `new NativeFunction(mmap_addr,` `'pointer'``, [``'pointer'``,` `'int'``,` `'int'``,` `'int'``,` `'int'``,` `'int'``])` `const parts` `=` `so_path.split(``'/'``);``const so_name` `=` `parts.pop();` `let soExecSegmentFromFile` `=` `findSoExecSegmentFromFile(so_path);` `/``/``获取maps中so的内存``let soRangeFromMaps` `=` `findSoRangeFromMaps(so_name);``let startAddress` `=` `soRangeFromMaps.base;``let size` `=` `soRangeFromMaps.size;``console.log(startAddress,size)``/``/``创建匿名内存,存储so内存区域的内存``let new_addr` `=` `mmapFunc(ptr(``-``1``), size,` `7``,` `0x20` `\|` `2``,` `-``1``,` `0``);``console.log(``"创建的匿名内存起始地址:"` `+` `new_addr);` `/``/``把maps中so内存区域的内存复制到创建的匿名内存中去``Memory.copy(new_addr, startAddress, size);``console.log(``"复制完毕"``)` `/``/``把文件中的可执行段复制到匿名内存中去``Memory.copy(ptr(new_addr).add(soExecSegmentFromFile.p_offset), ptr(soExecSegmentFromFile.start), soExecSegmentFromFile.size);``console.log(``"真实节区复制成功"``)` `/``/``从linker中获取到soinfo结构链表``let solist` `=` `getSolist();` `let num` `=` `0``;``let soinfo_next;``let realpath;` `console.log(``"开始遍历"``)``do {``realpath` `=` `getRealpath(solist);``/``/``获取soinfo所属的名字``console.log(num` `+` `"-->"` `+` `realpath);` `if` `(realpath.indexOf(so_name) !``=``=` `-``1``) {` `Memory.protect(ptr(solist).add(Process.pointerSize` `*` `2``),` `4``,` `"rw"``);``ptr(solist).add(Process.pointerSize` `*` `2``).writePointer(new_addr);``/``/``so base` `Memory.protect(ptr(solist).add(Process.pointerSize` `*` `26``),` `4``,` `"rw"``);``ptr(solist).add(Process.pointerSize` `*` `26``).writePointer(new_addr);``/``/``linker` `map` `/``/``load_bias 没法直接修改 否则会因为找不到符号崩溃``break``;``}``soinfo_next` `=` `ptr(solist).add(Process.pointerSize` `*` `5``).readPointer();``/``/``soinfo结构体``num``+``+``;``solist` `=` `soinfo_next;``}` `while` `(soinfo_next.toUInt32() !``=``=` `0``);``console.log(``"遍历完成:"``)``console.log(``"内存中隐藏so首地址完成"``);``}` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_X2S7CTYHHXUW4TY.webp)
注入上述代码后,再次点击这两个按钮查看控制台输出：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_Q88TPCUR7VU6XC5.webp)
 此时环境也正常了
注:对base和load_bias进行修改,会有app崩溃的风险

4.libc section mem crc的绕过
这个我就简单说下检测及绕过思路：

#### 检测:

获取到soinfo结构体中的节表地址(这里以strtab_变量作检测),再与本地文件或取到的节表偏移相见得到so的基地址,计算基地址与可执行段的偏移得到可执行段的地址,最后提取内存中可执行段数据和本地文件可执行段数据作比较。

#### 绕过：

把soinfo结构体中的节表指针指向我们在maps中映射的地址,达到绕过检测的目的。

#### hook现象:

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_KCKURCVJPGYN73E.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_AEMF26EY2KN2NN7.webp)
注入代码后再次点击按钮:
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/947335_JBF9SX9BZF9C85W.webp)

# 总结

此次分享主要是提供个思路,仅供参考,包括libart.so也可以这样去弄,总之crc的大方向就是上述的两个,其次小方向的检测手段就是有很多细节去相互嵌套了。

上传的附件：
- module.js

（20.85kb，516次下载）
- LinkerDemo.apk

（3.12MB，542次下载）

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2025-2-28 20:46*

感谢分享

## 回复 by wx_插曲 (#3)

*2025-2-28 20:47*

11

## 回复 by 白鹿 (#4)

*2025-2-28 20:51*

感谢分享

## 回复 by jueqingqiai (#5)

*2025-2-28 20:54*

好东西

## 回复 by manyuegong33 (#6)

*2025-2-28 21:00*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by bluegatar (#7)

*2025-2-28 21:02*

感谢分享

## 回复 by koflfy (#8)

*2025-2-28 21:05*

好东西。

## 回复 by 猫子 (#9)

*2025-2-28 21:14*

看看

## 回复 by 像风一样呢 (#10)

*2025-2-28 21:18*

6666666

## 回复 by yggcwhat (#11)

*2025-2-28 21:23*

感谢分享

## 回复 by doduhuang (#12)

*2025-2-28 21:29*

感谢分享

## 回复 by mb_cbgtaveo (#13)

*2025-2-28 22:05*

6666

## 回复 by 逆天而行 (#14)

*2025-2-28 22:33*

我有个想法  对libc 的路径 进行 重定向 拿 错误的libc 去内存中对比 ，openat 进行 io 重定向  到 临时重内存dump 修复的so

## 回复 by Our_OT (#15)

*2025-2-28 22:53*

学习了

## 回复 by alds (#16)

*2025-2-28 22:59*

学习下

## 回复 by 九天666 (#17)

*2025-2-28 23:10*

>
> [逆天而行](https://bbs.kanxue.com/user-957038.htm)
>
>  我有个想法&nbsp;&nbsp;对libc 的路径 进行 重定向 拿 错误的libc 去内存中对比 ，openat&nbsp;进行&nbsp;io&nbsp; ...
>
>

可以的，只要是两边的校验值相等就行

## 回复 by mb_cfjwplfo (#18)

*2025-2-28 23:20*

太强了大佬

## 回复 by mb_jgdenpbg (#19)

*2025-2-28 23:52*

撒大苏打

## 回复 by mb_lvesdvhu (#20)

*2025-3-1 03:11*

太强了大佬

## 回复 by mb_kgsesxqm (#21)

*2025-3-1 04:36*

Mark

## 回复 by 混 (#22)

*2025-3-1 09:44*

666

## 回复 by 黑屏 (#23)

*2025-3-1 11:58*

6666

## 回复 by n_1ng (#24)

*2025-3-1 15:28*

666

## 回复 by Gryffindoss (#25)

*2025-3-1 15:39*

666666

## 回复 by SomeMx (#26)

*2025-3-1 16:31*

感谢分享

## 回复 by mb_pgjnbfct (#27)

*2025-3-1 16:47*

1

## 回复 by 随风而行aa (#28)

*2025-3-1 18:41*

不错

## 回复 by mb_drubcclw (#29)

*2025-3-1 19:19*

666

## 回复 by 流光岁影 (#30)

*2025-3-1 19:39*

感谢分享

## 回复 by FindCall (#31)

*2025-3-1 20:03*

6

## 回复 by Imxz (#32)

*2025-3-1 22:30*

6666666666

## 回复 by mb_dcjxxhsk (#33)

*2025-3-1 22:48*

666

## 回复 by Eirv (#34)

*2025-3-2 01:02*

不用这么麻烦，如果已经确定目标用的是极其不安全的crc32校验，可以直接crc碰撞，修改内存中可执行phdr最后4字节使其与原始文件crc32相同，耗时也就1毫秒

## 回复 by 九天666 (#35)

*2025-3-2 03:15*

>
> [Eirv](https://bbs.kanxue.com/user-981037.htm)
>
>  不用这么麻烦，如果已经确定目标用的是极其不安全的crc32校验，可以直接crc碰撞，修改内存中可执行phdr最后4字节使其与原始文件crc32相同，耗时也就1毫秒
>
>

看了你的回复，我有点疑问。1.你说的crc碰撞,基于目前的校验，基本都是自写的crc，并且有的还会魔改,既然我都去碰撞了，是不是前提得是我知道这个加密函数的地址，那我已经知道这个加密函数地址了，那我为什么还去碰撞，我直接解决这个校验点不就行了，像你说的去碰撞那不显得更麻烦。实现起来也更耗时。2.通常来说，对函数的hook至少也得需要改变函数头部的前8个字节吧，frida就是16个。你这边的只改变可执行段的后4个字节的操作我属实没看懂与函数hook的crc校验有什么关系。如果你想了解hook之后的crc校验什么东西，你可以尝试对我发的app进行一个libc的hook操作，查看下内存和本地文件的区别。相信你能更加理解到基于函数hook的crc校验。

## 回复 by cpannn (#36)

*2025-3-2 08:54*

无私精神

## 回复 by mb_kgfqphsx (#37)

*2025-3-2 09:28*

6666

## 回复 by 清风jw (#38)

*2025-3-2 11:47*

感谢分享

## 回复 by Arsylk (#39)

*2025-3-2 12:46*

6

## 回复 by 安卓逆向test (#40)

*2025-3-2 14:21*

我忽然想到一种自身获取某个so基址的方法不知道可不可行，就是直接通过dlopen获取指定so的基址，这个接口走的不知道是不是soinfo那边的

## 回复 by 5m10v3 (#41)

*2025-3-2 15:20*

感谢分享

## 回复 by mb_ykavguun (#42)

*2025-3-2 15:50*

666666

## 回复 by fjqisba (#43)

*2025-3-2 16:13*

依稀记得CRC都是提前算好的

## 回复 by wx_晚风_407 (#44)

*2025-3-2 16:24*

0666

## 回复 by 涿州飞神 (#45)

*2025-3-2 17:37*

6666

## 回复 by 毛毛毛毛虫 (#46)

*2025-3-2 18:05*

学习一下

## 回复 by ovo_帮我不c (#47)

*2025-3-2 18:59*

666

## 回复 by mb_mmodulik (#48)

*2025-3-2 19:03*

看看大佬文章

## 回复 by mb_qimctavn (#49)

*2025-3-2 19:11*

感谢分享

## 回复 by 九天666 (#50)

*2025-3-2 19:44*

>
> [安卓逆向test](https://bbs.kanxue.com/user-973348.htm)
>
>  我忽然想到一种自身获取某个so基址的方法不知道可不可行，就是直接通过dlopen获取指定so的基址，这个接口走的不知道是不是soinfo那边的
>
>

改soinfo里面的load bias参数就可以影响到dlopen返回的handle，但是会有崩溃的风险

## 回复 by 烬奇小云 (#51)

*2025-3-2 19:51*

666

## 回复 by method (#52)

*2025-3-2 20:16*

学到了

## 回复 by mb_zdectmvq (#53)

*2025-3-2 22:42*

Nb

## 回复 by Eirv (#54)

*2025-3-2 23:17*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  九天666](https://bbs.kanxue.com/user-947335.htm)
>
>  看了你的回复，我有点疑问。1.你说的crc碰撞,基于目前的校验，基本都是自写的crc，并且有的还会魔改,既然我都去碰撞了，是不是前提得是我知道这个加密函数的地址，那我已经知道这个加密函数地址了，那我为 ...
>
>

简单来说相当于是可以通过“仅修改文件最后4字节数据使文件本身crc32值不变”，生成这最后4字节的值仅需不到1毫秒

## 回复 by tyeying (#55)

*2025-3-3 00:25*

太强了大佬

## 回复 by kylinokok (#56)

*2025-3-3 04:04*

666666

## 回复 by 上官兮唐 (#57)

*2025-3-3 06:55*

看看

## 回复 by ONewTach (#58)

*2025-3-3 08:49*

tql

## 回复 by fangliangz (#59)

*2025-3-3 09:35*

666

## 回复 by mb_uvyukvot (#60)

*2025-3-3 10:09*

666

## 回复 by 丶咖啡猫丶 (#61)

*2025-3-3 10:09*

666

## 回复 by wgetlaidu (#62)

*2025-3-3 10:11*

666

## 回复 by AloneMonkey (#63)

*2025-3-3 10:43*

m

## 回复 by DirtyAngle (#64)

*2025-3-3 10:50*

1

## 回复 by 熊猫人大A (#65)

*2025-3-3 10:50*

666

## 回复 by 4Chan (#66)

*2025-3-3 10:52*

666

## 回复 by mb_kbkqyusp (#67)

*2025-3-3 11:19*

6

## 回复 by wx_钺 (#68)

*2025-3-3 11:49*

66666

## 回复 by Judong0x0 (#69)

*2025-3-3 11:51*

666666

## 回复 by Eureka777 (#70)

*2025-3-3 11:58*

666666

## 回复 by mb_bsvittau (#71)

*2025-3-3 13:48*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by Sadmin (#72)

*2025-3-3 13:55*

66666666666666

## 回复 by 肉蚌葱鸡 (#73)

*2025-3-3 14:07*

666 来试试能不能过![image](https://bbs.kanxue.com/view/img/face/025.gif)

## 回复 by ychangeol (#74)

*2025-3-3 14:12*

6666

## 回复 by mb_mzwrvupz (#75)

*2025-3-3 14:15*

666

## 回复 by chenshipei (#76)

*2025-3-3 14:24*

666666

## 回复 by lookaside (#77)

*2025-3-3 14:44*

流弊

## 回复 by darbra (#78)

*2025-3-3 15:00*

66666

## 回复 by Light紫星 (#79)

*2025-3-3 15:04*

大佬厉害啊，收益颇丰

## 回复 by 肖安111 (#80)

*2025-3-3 15:36*

6

## 回复 by Ar1etisPanda (#81)

*2025-3-3 15:45*

学习一下

## 回复 by mb_syvaqetv (#82)

*2025-3-3 17:48*

学习学习，66666

## 回复 by 不知世事 (#84)

*2025-3-3 19:55*

666

## 回复 by mb_hdptcgkk (#85)

*2025-3-3 22:01*

1

## 回复 by uni7corn (#86)

*2025-3-3 23:36*

6666666

## 回复 by 恋一世的爱 (#87)

*2025-3-4 02:53*

6666666666666666

## 回复 by yyamcom (#88)

*2025-3-4 08:38*

![image](https://bbs.kanxue.com/view/img/face/083.gif)

## 回复 by tjytjy (#89)

*2025-3-4 09:37*

666

## 回复 by Ankeys (#90)

*2025-3-4 10:28*

感谢分享

## 回复 by azd放 (#91)

*2025-3-4 10:58*

666666

## 回复 by mb_itfzfkdp (#92)

*2025-3-4 11:27*

6666

## 回复 by wolf_lc (#93)

*2025-3-4 13:37*

kankan

## 回复 by bowelr (#94)

*2025-3-4 15:38*

66666666

## 回复 by artake (#95)

*2025-3-4 18:29*

666

## 回复 by zhengyuqin (#96)

*2025-3-5 12:55*

6666

## 回复 by inono (#97)

*2025-3-5 13:56*

感谢分享

## 回复 by qihui (#98)

*2025-3-5 17:05*

66666

## 回复 by mb_tmbvnlxt (#99)

*2025-3-6 05:13*

666

## 回复 by jkloop (#100)

*2025-3-6 07:38*

66666

## 回复 by 黎明与黄昏 (#101)

*2025-3-6 08:12*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by huangjw (#102)

*2025-3-6 10:04*

又学到了新招数

## 回复 by mb_pduwmxiw (#103)

*2025-3-6 11:19*

6666

## 回复 by hlke (#104)

*2025-3-6 11:28*

看看

## 回复 by godiand (#105)

*2025-3-6 13:23*

感谢分享

## 回复 by xxjj678 (#106)

*2025-3-6 16:36*

6

## 回复 by lotus* (#107)

*2025-3-6 17:08*

666

## 回复 by nqminhquan (#108)

*2025-3-6 17:40*

66666666

## 回复 by mb_vkeacyrq (#109)

*2025-3-6 21:28*

感谢分享

## 回复 by ascend (#110)

*2025-3-6 22:43*

66666666666

## 回复 by mb_peeqldfc (#111)

*2025-3-7 02:01*

牛逼

## 回复 by glitchedpoke (#112)

*2025-3-7 04:33*

looks great

## 回复 by 绿豆粥 (#113)

*2025-3-7 09:50*

学习了

## 回复 by cpu_os (#114)

*2025-3-7 10:57*

想法不错

## 回复 by 光头才能变强 (#115)

*2025-3-7 11:09*

66666

## 回复 by 疯子Tear (#116)

*2025-3-7 12:18*

nice

## 回复 by 小木马 (#117)

*2025-3-7 14:22*

666

## 回复 by ben_ (#118)

*2025-3-7 16:14*

学习

## 回复 by 无味 (#119)

*2025-3-7 16:51*

666666666

## 回复 by mb_zzrqvdnp (#120)

*2025-3-7 17:15*

666

## 回复 by 蜡笔晓辉 (#121)

*2025-3-7 17:18*

77777

## 回复 by dofla (#122)

*2025-3-7 17:30*

666

## 回复 by xiaoc996 (#123)

*2025-3-7 17:45*

666

## 回复 by mb_xqptnehm (#124)

*2025-3-7 23:08*

6666

## 回复 by pigsub (#125)

*2025-3-8 04:27*

666666

## 回复 by laoli121 (#126)

*2025-3-8 18:20*

88

## 回复 by lov520ing (#127)

*2025-3-8 19:58*

6666

## 回复 by wjwujian (#128)

*2025-3-9 02:03*

谢谢分享

## 回复 by mb_4nrpVMxJ (#129)

*2025-3-9 12:08*

看看

## 回复 by mb_zpyvrtaq (#130)

*2025-3-9 14:35*

666

## 回复 by 华达州 (#131)

*2025-3-9 14:49*

6666

## 回复 by mb_rewimxhj (#132)

*2025-3-10 00:41*

看看吧

## 回复 by mb_kgsesxqm (#133)

*2025-3-10 05:30*

转为c或者c++代码好像有问题

## 回复 by amwait (#134)

*2025-3-10 09:37*

666

## 回复 by mb_hvjrpjio (#135)

*2025-3-10 10:09*

666666

## 回复 by 思睿 (#136)

*2025-3-10 12:02*

666

## 回复 by cnhuaWu (#137)

*2025-3-10 14:10*

kanyikan

## 回复 by 黄石 (#138)

*2025-3-10 14:23*

666

## 回复 by 橘子皮儿 (#139)

*2025-3-10 14:48*

666

## 回复 by mb_lizfxfno (#140)

*2025-3-10 14:50*

666666

## 回复 by 荧光之夏 (#141)

*2025-3-10 15:09*

6666666

## 回复 by 看这是什么 (#142)

*2025-3-10 16:44*

666666

## 回复 by mb_ozmrnffd (#143)

*2025-3-10 17:36*

![image](https://bbs.kanxue.com/view/img/face/079.gif)![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by _thouger (#144)

*2025-3-10 19:28*

nb！！！！

## 回复 by wx_范迪塞尔 (#145)

*2025-3-11 09:04*

回复可见就很6

## 回复 by Ms135 (#146)

*2025-3-11 09:52*

6666

## 回复 by Yang1k (#147)

*2025-3-11 10:22*

6

## 回复 by WADXH (#148)

*2025-3-11 14:46*

666

## 回复 by 飆汗吉米 (#149)

*2025-3-11 15:13*

謝謝博主分享

## 回复 by mb_ajgkdedt (#150)

*2025-3-11 20:16*

厉害，大佬，可以加个联系方式一起学习一下嘛

## 回复 by matrump (#151)

*2025-3-12 10:39*

666

## 回复 by creek_ (#152)

*2025-3-12 16:28*

感谢你的积极参与，期待更多精彩内容！

## 回复 by wlmf (#153)

*2025-3-12 16:30*

1

## 回复 by mb_bssqdqps (#154)

*2025-3-12 17:28*

6

## 回复 by mb_wnwwmdty (#155)

*2025-3-12 22:54*

111

## 回复 by Payne-Wu (#156)

*2025-3-13 05:42*

111

## 回复 by mb_lfwgtxdb (#157)

*2025-3-14 14:45*

感谢分享

## 回复 by lamboo (#158)

*2025-3-14 17:07*

666666

## 回复 by 胖虎1103 (#159)

*2025-3-14 20:17*

6

## 回复 by zxk1ng (#160)

*2025-3-14 22:28*

666

## 回复 by 小蜜蜂12138 (#161)

*2025-3-17 15:34*

666

## 回复 by Yangser (#162)

*2025-3-17 18:40*

"我们可以在maps中模拟一段可执行段数据,并把libc.so原本的可执行段名称给抹去,变为匿名内存"，正常的app环境中,maps里似乎不会存在可执行的匿名内存段

## 回复 by Yangser (#163)

*2025-3-17 18:42*

确实这样好一些，maps里不会留下可疑的痕迹

## 回复 by mb_kgsesxqm (#164)

*2025-3-17 22:24*

学习了几天了，总算吃下去第1种，正在吃第2种方案了，预计明天吃第3种跟第4种

## 回复 by niceday (#165)

*2025-3-18 16:29*

感谢分享

## 回复 by fzyspark (#166)

*2025-3-19 11:05*

6666

## 回复 by 带带弟弟吧 (#167)

*2025-3-19 11:05*

99

## 回复 by Xniko (#168)

*2025-3-19 11:24*

感谢分享

## 回复 by K4NG (#169)

*2025-3-19 11:25*

向大佬学习

## 回复 by caddor (#170)

*2025-3-19 11:44*

666

## 回复 by mb_jzyasacd (#171)

*2025-3-19 15:27*

66666

## 回复 by 呼吸24K纯氧 (#172)

*2025-3-19 16:44*

666

## 回复 by 无味 (#173)

*2025-3-19 16:49*

>
> [逆天而行](https://bbs.kanxue.com/user-957038.htm)
>
>  我有个想法&nbsp;&nbsp;对libc 的路径 进行 重定向 拿 错误的libc 去内存中对比 ，openat&nbsp;进行&nbsp;io&nbsp; ...
>
>

见过服务器对比吗?
服务器收集对比好的crc32值, 和本地的对比![image](https://bbs.kanxue.com/view/img/face/002.gif)

## 回复 by DKFATE (#174)

*2025-3-19 19:42*

1111

## 回复 by 问心无愧 (#175)

*2025-3-20 09:51*

666

## 回复 by 偶尔.c (#176)

*2025-3-20 20:11*

看看隐藏，感谢分享

## 回复 by lijjianyu (#177)

*2025-3-20 22:43*

膜拜

## 回复 by 櫬木汐 (#178)

*2025-3-20 22:48*

????????

## 回复 by mb_srdgpiky (#179)

*2025-3-21 10:55*

666

## 回复 by wx_霿凇 (#180)

*2025-3-21 14:29*

666

## 回复 by 恋一世的爱 (#181)

*2025-3-21 16:16*

没事了

## 回复 by 九天666 (#182)

*2025-3-22 00:26*

这个函数主要是从maps映射的内存里获取整个so，你看你的系统上的某个so的起始地址是多少，对应改就行了

## 回复 by 恋一世的爱 (#183)

*2025-3-22 01:52*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  恋一世的爱](https://bbs.kanxue.com/user-825246.htm)
>
>  大佬，findSoRangeFromMaps是用查找第一个"r--p"作为基地址，但9及之前系统要用第一个"r-xp"作为基地址(10系统后对于第3方so也是) ...
>
>

## 回复 by mb_mumzrqcs (#184)

*2025-3-22 18:05*

666666666

## 回复 by mb_vanjeoof (#185)

*2025-3-25 10:42*

学习

## 回复 by zhczf (#186)

*2025-3-25 21:12*

什么是crc检测

## 回复 by 看雪高研 (#187)

*2025-3-26 16:37*

6

## 回复 by mb_dmekqwtd (#188)

*2025-3-26 17:02*

66

## 回复 by wx_范迪塞尔 (#189)

*2025-3-28 11:45*

6666666

## 回复 by wx_二三_474827 (#190)

*2025-3-28 15:06*

666666

## 回复 by wx_二三_474827 (#191)

*2025-3-28 17:13*

运行报错了，楼主怎么运行起来的。
e_phnum:11
进来:0x7956a6f000
创建的匿名内存起始地址:0x767ed86000
[Logcat] {'type': 'error', 'description': 'Error: access violation accessing 0x7956ab2000', 'stack': 'Error: access violation accessing 0x7956ab2000\n    at hiddenSectionInMem (/script1.js:104)\n    at <eval> (/script1.js:2)', 'fileName': '/script1.js', 'lineNumber': 104, 'columnNumber': 1}

## 回复 by dadadasda (#192)

*2025-3-28 17:28*

都是inlinehook给大家惯的

## 回复 by exediy (#193)

*2025-3-28 19:39*

像 lsposed 之类的会在 linker64 上进行 hook 就比较麻烦

## 回复 by Crack999 (#194)

*2025-3-28 22:54*

感谢分享

## 回复 by 袁伟业 (#195)

*2025-3-29 05:58*

666666666

## 回复 by cobe (#196)

*2025-3-29 15:29*

666

## 回复 by wx_插曲 (#197)

*2025-3-31 17:25*

666

## 回复 by mb_zbynmbgf (#198)

*2025-4-4 11:28*

6666

## 回复 by 我不是卷王 (#199)

*2025-4-7 11:30*

666

## 回复 by mb_oskoghri (#200)

*2025-4-7 14:44*

66666666666666

## 回复 by wx_北极星_493 (#201)

*2025-4-8 10:20*

666

## 回复 by mb_hvrktlpi (#202)

*2025-4-11 14:57*

六百六十六

## 回复 by mb_zzzqbbim (#203)

*2025-4-11 16:30*

66666

## 回复 by 还没想好名字 (#204)

*2025-4-14 08:47*

666

## 回复 by mb_jwevvolh (#205)

*2025-4-14 21:10*

66666666666666666666

## 回复 by mb_fqzjlpub (#206)

*2025-4-15 13:07*

666

## 回复 by mb_yxskextg (#207)

*2025-4-16 17:59*

感谢分享

## 回复 by mb_xvjarnta (#208)

*2025-4-17 16:51*

666666

## 回复 by mb_tcandlos (#209)

*2025-4-18 10:16*

666

## 回复 by wx_R12-4 (#210)

*2025-4-20 16:19*

大佬

## 回复 by 夜惜风雨 (#211)

*2025-4-21 07:17*

66666

## 回复 by AYHMO (#212)

*2025-4-21 09:48*

学习学习

## 回复 by Va1ue (#213)

*2025-4-21 11:07*

666

## 回复 by mb_mwfzoyhc (#214)

*2025-4-23 03:22*

谢谢

## 回复 by 我是小奥 (#215)

*2025-4-23 08:50*

666

## 回复 by z0xc (#216)

*2025-4-23 18:14*

666

## 回复 by Losir (#217)

*2025-4-26 12:02*

感谢分享

## 回复 by hacker521 (#218)

*2025-5-2 16:52*

6666666

## 回复 by mb_gznromrh (#219)

*2025-5-10 01:08*

观摩学习一下

## 回复 by likeke (#220)

*2025-5-11 01:16*

6666

## 回复 by wx_huhu_859 (#221)

*2025-5-11 01:45*

11

## 回复 by wake0p (#222)

*2025-5-11 21:16*

你好，请问一下这篇中提供的hiddenSoExecSegmentInMaps函数中的findSoExecSegmentRangeFromMaps 和 findSoExecSegmentFromFile 函数实现是怎么样的，原文好像没有通过这个api

## 回复 by mb_seqzklna (#223)

*2025-5-12 17:13*

感谢分享，学习一下。

## 回复 by juziss (#224)

*2025-5-13 20:11*

666

## 回复 by 司徒废人 (#225)

*2025-5-14 09:43*

Mark

## 回复 by 烟花易冷丶 (#226)

*2025-5-14 10:23*

666

## 回复 by mb_pesxllvn (#227)

*2025-5-14 11:06*

学习下

## 回复 by mb_basgiwmq (#228)

*2025-5-15 17:33*

nb

## 回复 by 拾剑僧 (#229)

*2025-5-18 17:21*

666

## 回复 by 小黄鸭爱学习 (#230)

*2025-5-20 11:29*

1

## 回复 by 无心问世 (#231)

*2025-5-21 17:16*

666

## 回复 by mb_xkflsjah (#232)

*2025-5-22 08:34*

66666

## 回复 by mb_xkflsjah (#233)

*2025-5-22 08:43*

小白。。。我想知道如何使用测试

## 回复 by baichisi (#234)

*2025-5-22 15:11*

666666666

## 回复 by mb_jhohnbzu (#235)

*2025-5-23 18:02*

666

## 回复 by mb_ttaweivy (#236)

*2025-5-24 06:19*

1

## 回复 by mb_irhdtnzm (#237)

*2025-5-26 11:35*

1

## 回复 by mb_irhdtnzm (#238)

*2025-5-26 11:47*

11111

## 回复 by HL_Mcgrady (#239)

*2025-5-28 10:34*

666666

## 回复 by 雅鸦歌 (#240)

*2025-5-29 10:37*

11111111111111

## 回复 by wx_错爱 (#241)

*2025-5-31 00:31*

66666

## 回复 by mb_hoktzmpe (#242)

*2025-5-31 10:29*

>
> [九天666](https://bbs.kanxue.com/user-947335.htm)
>
>  看了你的回复，我有点疑问。1.你说的crc碰撞,基于目前的校验，基本都是自写的crc，并且有的还会魔改,既然我都去碰撞了，是不是前提得是我知道这个加密函数的地址，那我已经知道这个加密函数地址了，那我为 ...
>
>

文件的crc32可以直接修改

## 回复 by 虚空遁地猪 (#243)

*2025-6-2 19:13*

111

## 回复 by Big权 (#244)

*2025-6-5 10:49*

666666

## 回复 by 程序猿007 (#245)

*2025-6-8 19:49*

6666666

## 回复 by ldehua (#246)

*2025-6-9 08:58*

太强了大佬

## 回复 by mb_ghzqfgyt (#247)

*2025-6-9 21:15*

411

## 回复 by mb_lqtnraus (#248)

*2025-6-10 17:42*

学习一下

## 回复 by 曹无咎 (#249)

*2025-6-10 18:59*

感谢分享

## 回复 by dfJerry (#250)

*2025-6-11 17:22*

666666666

## 回复 by mb_mihutdve (#251)

*2025-6-13 17:46*

666

## 回复 by xianhuimin (#252)

*2025-6-14 17:21*

666学习下

## 回复 by mb_ebiwunmj (#253)

*2025-6-14 17:57*

大佬 xposed 可以做到这个功能吗

## 回复 by xifgg (#254)

*2025-6-16 11:09*

666

## 回复 by ChengQing (#255)

*2025-6-16 11:25*

111

## 回复 by 魔马 (#256)

*2025-6-16 12:35*

1

## 回复 by xianhuimin (#257)

*2025-6-16 21:49*

bb加固后检测lsposed框架是不是也可以这样实现

## 回复 by Ayuer (#258)

*2025-6-17 00:23*

太强了

## 回复 by 蜂助手HR (#259)

*2025-6-17 10:13*

佬，看广州岗位吗？

## 回复 by mb_lhmayubx (#260)

*2025-6-17 10:23*

感谢分享

## 回复 by yyyyy——— (#261)

*2025-6-19 16:57*

66666

## 回复 by 飞仙魔女舅 (#262)

*2025-6-21 17:58*

666

## 回复 by mb_ifjlatem (#263)

*2025-6-23 12:03*

学习

## 回复 by 咸鱼…… (#264)

*2025-6-23 14:00*

666666

## 回复 by wx_最爱老大 (#265)

*2025-6-23 17:30*

6666

## 回复 by mb_rjoxthlj (#266)

*2025-6-23 19:32*

666

## 回复 by Assclyon (#267)

*2025-6-25 16:27*

感谢大佬分享

## 回复 by mb_lfvhycml (#268)

*2025-6-26 10:46*

666666

## 回复 by mJqalJqN (#269)

*2025-6-26 11:21*

1

## 回复 by wx_Huber Barrientos (#270)

*2025-6-26 11:35*

感谢分享

## 回复 by mb_wjcopkxx (#271)

*2025-6-30 22:14*

666

## 回复 by 军哥i (#272)

*2025-7-2 16:43*

niubi

## 回复 by TonyNg (#273)

*2025-7-3 22:14*

666

## 回复 by mb_yxcltfyb (#274)

*2025-7-6 22:15*

厉害

## 回复 by mb_ufazkqax (#275)

*2025-7-8 09:40*

666

## 回复 by SGSGsama (#276)

*2025-7-10 11:53*

学习

## 回复 by wx_秋秋秋天！！ (#277)

*2025-7-11 11:16*

6

## 回复 by 寻梦之璐 (#278)

*2025-7-15 20:19*

1

## 回复 by ivy1 (#279)

*2025-7-17 14:29*

666666

## 回复 by 葡萄柿子 (#280)

*2025-7-17 23:53*

11111

## 回复 by mb_kfrkwwjb (#281)

*2025-7-22 04:00*

66

## 回复 by 胖虎汇邦 (#282)

*2025-7-22 14:16*

666

## 回复 by A冷忆 (#283)

*2025-7-22 14:23*

666

## 回复 by mb_wuwmtxuq (#284)

*2025-7-23 21:44*

6666

## 回复 by 酒仙桥之虎 (#285)

*2025-7-23 22:11*

6666

## 回复 by k4y0z (#286)

*2025-7-25 16:53*

666

## 回复 by python_joker (#287)

*2025-7-26 23:43*

6666

## 回复 by mb_lgwgxdmu (#288)

*2025-7-28 08:37*

666

## 回复 by gyugh (#289)

*2025-8-1 17:38*

666

## 回复 by 柳哈辣子 (#290)

*2025-8-4 02:00*

666

## 回复 by mb_lzotvdxv (#291)

*2025-8-4 02:25*

Ii

## 回复 by 西埔 (#292)

*2025-8-5 16:53*

感谢分享

## 回复 by enter_0909 (#293)

*2025-8-6 00:09*

66

## 回复 by 无视红绿灯 (#294)

*2025-8-12 10:07*

666666

## 回复 by heting0 (#295)

*2025-8-14 17:58*

6666

## 回复 by mb_homnvxow (#296)

*2025-8-14 18:47*

666

## 回复 by mb_eltlxelx (#297)

*2025-8-14 21:09*

66666

## 回复 by Old_Yuan (#298)

*2025-8-18 17:30*

666

## 回复 by wx_荼风 (#299)

*2025-8-18 17:45*

666

## 回复 by dsr000 (#300)

*2025-8-21 20:46*

1111

## 回复 by ADR66 (#301)

*2025-8-22 09:09*

毒贩夫妇sd

## 回复 by mb_mrjjcxgk (#302)

*2025-8-25 16:09*

6

## 回复 by wx_我叫木易杨 (#303)

*2025-8-27 17:17*

6666

## 回复 by Kill_Log (#304)

*2025-8-30 08:44*

66666

## 回复 by Snowman_Liam (#305)

*2025-8-30 10:13*

6666

## 回复 by 夫人十八岁 (#306)

*2025-8-30 14:08*

感谢分享

## 回复 by wx_kx31902 (#307)

*2025-8-30 21:55*

66666666

## 回复 by Sofia4041 (#308)

*2025-9-1 17:29*

学习了

## 回复 by mb_sajaoega (#309)

*2025-9-1 17:31*

666

## 回复 by 29o (#310)

*2025-9-2 10:14*

11

## 回复 by mb_okbxqrns (#311)

*2025-9-3 20:10*

![image](https://bbs.kanxue.com/view/img/face/026.gif)

## 回复 by rainb0w (#312)

*2025-9-7 21:27*

学习

## 回复 by 云霄IT (#313)

*2025-9-9 01:37*

1

## 回复 by fyrlove (#314)

*2025-9-9 10:34*

学习了，学习了

## 回复 by XCicada (#315)

*2025-9-9 10:50*

感谢

## 回复 by Melina (#316)

*2025-9-9 11:41*

666666666666666666

## 回复 by iceblue007007 (#317)

*2025-9-10 23:02*

每日一学

## 回复 by thouger_ (#318)

*2025-9-26 10:58*

牛逼

## 回复 by bullyxy (#319)

*2025-9-26 11:06*

6666

## 回复 by mb_auylfslb (#320)

*2025-9-26 14:13*

567

## 回复 by Siriusss (#321)

*2025-9-30 08:22*

1

## 回复 by bonder (#322)

*2025-10-3 20:03*

666

## 回复 by G33k3r (#323)

*2025-10-7 22:10*

mark

## 回复 by mb_jerxzakl (#324)

*2025-10-21 19:34*

6666666

## 回复 by Oo风之恋oO (#325)

*2025-10-23 23:48*

可以在内核做过crc检测吗

## 回复 by 梨树生果 (#326)

*2025-10-24 18:50*

牛呀

## 回复 by mb_rceuowlf (#327)

*2025-10-29 16:56*

666666

## 回复 by git_49737yousef20011112-max (#328)

*2025-11-5 16:39*

good 太强了大佬

## 回复 by LQ6H (#329)

*2025-11-5 17:34*

666

## 回复 by pyth0nDev (#330)

*2025-11-6 03:09*

![image](https://bbs.kanxue.com/view/img/face/087.gif)

## 回复 by 那么一下下 (#331)

*2025-11-6 06:47*

111111111

## 回复 by 该账号被弃用 (#332)

*2025-11-10 11:17*

1

## 回复 by mb_yjiuccxa (#333)

*2025-11-10 13:05*

学习

## 回复 by git_87065joelitondossantos0 (#334)

*2025-11-12 06:08*

good

## 回复 by AMy_德友 (#335)

*2025-11-14 04:08*

66666

## 回复 by 非洲男 (#336)

*2025-11-14 10:37*

感谢分享

## 回复 by wx_马 (#337)

*2025-11-16 10:18*

666666

## 回复 by mb_atdqqbte (#338)

*2025-11-17 22:50*

6

## 回复 by mickelfeng (#339)

*2025-11-18 19:55*

学习一下

## 回复 by 踏水流 (#340)

*2025-11-20 14:38*

666

## 回复 by taeyeon_ss (#341)

*2025-11-20 15:46*

6！

## 回复 by 3倍アイスクリーム! (#342)

*2025-11-24 20:47*

好文章学一下

## 回复 by 3倍アイスクリーム! (#343)

*2025-11-24 20:53*

大佬app下载老失败 换网也不行 能再发下不

## 回复 by mb_iqkkgktq (#344)

*2025-11-25 21:51*

学习一下

## 回复 by wx_五十度灰 (#345)

*2025-11-27 16:50*

666

## 回复 by FanciSun (#346)

*2025-12-2 20:52*

谢谢

## 回复 by lingyi223 (#347)

*2025-12-2 21:59*

1111

## 回复 by 诗卡叙 (#348)

*2025-12-3 13:29*

学习

## 回复 by wx_好饿想吃肉 (#349)

*2025-12-4 11:27*

6666

## 回复 by Heiyiren123 (#350)

*2025-12-8 18:42*

支持楼主，感谢分享！

## 回复 by 一只鸭子 (#351)

*2025-12-9 10:42*

tql

## 回复 by STCEN (#352)

*2025-12-11 11:37*

感谢分享！

## 回复 by mb_onetrtkl (#353)

*2025-12-11 16:02*

666666

## 回复 by zkbutt (#354)

*2025-12-15 11:06*

学习

## 回复 by 逆向小呆呆 (#355)

*2025-12-18 16:07*

感谢分享

## 回复 by 盛宝不喝肾宝 (#356)

*2025-12-21 23:00*

tql![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by wohowo (#357)

*2025-12-22 13:07*

6666666666666

## 回复 by wx_故事与酒 (#358)

*2025-12-22 16:46*

6666666666666666666

## 回复 by Viseris (#359)

*2026-1-5 13:20*

谢谢分享

## 回复 by hanjiefang (#360)

*2026-1-6 17:10*

![image](https://bbs.kanxue.com/view/img/face/085.gif)

## 回复 by mb_vlysoyke (#361)

*2026-1-7 16:08*

666

## 回复 by Ddddz (#362)

*2026-1-7 16:18*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by wx_tieL (#363)

*2026-1-15 17:18*

666

## 回复 by mb_ysikfhxt (#364)

*2026-1-16 14:02*

666

## 回复 by 大魔头 (#365)

*2026-1-16 14:30*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by Superoot (#366)

*2026-1-19 14:39*

感谢分享，学习一下

## 回复 by 我心向山 (#367)

*2026-1-21 20:32*

11

## 回复 by win柠初 (#368)

*2026-2-5 19:18*

好东西，赶紧来看看

## 回复 by mb_aelpsyuc (#369)

*2026-2-5 19:32*

6666

## 回复 by mb_qqlojqnm (#370)

*2026-2-6 09:32*

666

## 回复 by GEKEZYX (#371)

*2026-2-6 11:01*

666

## 回复 by mb_ywybutcg (#372)

*2026-2-8 10:29*

谢谢分享

## 回复 by kccp (#373)

*2026-2-21 14:13*

666

## 回复 by FuncWorld (#374)

*2026-3-1 11:33*

6

## 回复 by 王多余 (#375)

*2026-3-6 20:03*

感谢分享   学习了！

## 回复 by xeiyu (#376)

*2026-3-6 23:52*

666

## 回复 by pannifushe (#377)

*2026-3-7 00:52*

66666666666666666666

## 回复 by qkcoder (#378)

*2026-3-8 04:15*

666

## 回复 by nuoen (#379)

*2026-3-8 13:49*

顶

## 回复 by jyotidwi (#380)

*2026-3-15 11:06*

6666

## 回复 by veluboii (#381)

*2026-3-15 13:07*

888

## 回复 by 0x25519 (#382)

*2026-4-22 17:14*

学习学习

## 回复 by wx_窒息 (#383)

*2026-4-22 21:53*

666

## 回复 by ClPrada (#384)

*2026-5-2 20:27*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_joablzkk (#385)

*2026-5-18 09:07*

1

## 回复 by maomaolk (#386)

*2026-5-27 11:53*

好东西。

## 回复 by pan_634488 (#387)

*2026-6-3 16:37*

感谢分享

## 回复 by mb_hcadvceu (#388)

*2026-6-3 17:59*

谢谢分享

## 回复 by mb_enbuhisq (#389)

*2026-6-4 16:11*

6666666

## 回复 by mb_fdskejlh (#390)

*2026-6-13 15:45*

666

## 回复 by mb_unkmqemn (#391)

*2026-6-17 10:27*

666

## 回复 by mb_hktfsykj (#392)

*2026-7-18 18:47*

1

## 回复 by mb_degalzhb (#393)

*2026-7-20 10:20*

666

## 回复 by git_30584zhutou9527 (#394)

66666

## 回复 by xtyuns (#395)

学习一下，过 CRC 校验

## 回复 by 独狼自我修养 (#396)

666

## 回复 by guardia (#397)

666

## 回复 by haris4687 (#398)

6
