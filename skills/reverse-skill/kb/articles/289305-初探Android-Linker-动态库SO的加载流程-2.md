---
title: '[原创]初探Android Linker 动态库SO的加载流程（2）'
url: https://bbs.kanxue.com/thread-289305.htm
tid: 289305
author: Ayuer
date: '2025-12-02'
tags: [Android安全, 原创, 基础理论]
crawled_at: '2026-07-31T14:00:11+08:00'
replies: 28
---

上一篇文章初探Android Linker 动态库SO的加载流程（1），其中两步的内容，总结了核心重点是**如何进行加载so，映射了程序头表、节头表、dynamic section 到内存地址中**，这些地址都保存在了ElfReader当中。

这一篇我们来继续分析

## Step 2

这里进行load_list遍历，然后判断si如果不是已经链接的，然后调用std::find_if进行去重，传入函数闭包，shuffle则进行打乱load_list，随机化加载。

接着到重点了，遍历load_list然后调用task的load方法

代码如下

| 1234567891011121314151617181920212223242526272829303132333435 | `/**``* 步骤2：``*/``// Step 2: Load libraries in random order (see b/24047022)``LoadTaskList load_list;``//过滤并去重 load_list``for` `(``auto``&& task : load_tasks) {``soinfo* si = task->get_soinfo();``auto` `pred = [&](``const` `LoadTask* t) {``return` `t->get_soinfo() == si;``};` `if` `(!si->is_linked() &&``std::find_if(load_list.begin(), load_list.end(), pred) == load_list.end() ) {``load_list.push_back(task);``}``}``//随机化加载顺序``shuffle(&load_list);` `/**``* 重点``* 打开 so 文件（或使用 extinfo 中的 fd）``* 读取 ELF header``* 读取 Program Header Table``* 找到所有 PT_LOAD 段``* 使用 mmap() 将 PT_LOAD 段映射到内存``* 修正对齐、权限（PROT_READ/WRITE/EXEC）``* 构建 load_bias``* 找到加载后的 phdr 在内存中的实际地址``*/``for` `(``auto``&& task : load_list) {``if` `(!task->load()) {``return` `false``;``}``}` |
|-|-|

开始分析task的load方法

这里get_elf_reader获取了，前面步骤使用的ElfReader，然后开始调用ElfReader的Load方法，该方法的实现位于linker_phdr.cpp，上一节文章中，**如何进行加载so，映射了程序头表、节头表、dynamic section 到内存地址中**，从这里开始，加载程序头表的load类型。这里有三个核心方法ReserveAddressSpace和LoadSegments以及FindPhdr

代码如下

| 1234567891011121314151617181920212223242526272829303132 | `/**``* load``*/``bool` `load() {``ElfReader& elf_reader = get_elf_reader();``//核心是处理 ELF 文件的 Program Header (PT_LOAD)，把它们 mmap 进内存。``/**``* 准``* 打开 so 文件（或使用 extinfo 中的 fd）``* 读取 ELF header``* 读取 Program Header Table``* 找到所有 PT_LOAD 段``* 使用 mmap() 将 PT_LOAD 段映射到内存``* 修正对齐、权限（PROT_READ/WRITE/EXEC）``* 找到加载后的 phdr 在内存中的实际地址``*/``if` `(!elf_reader.Load(extinfo_)) {``return` `false``;``}` `/**``* 根据装载结果，更新 soinfo 的成员变量``*/``si_->base = elf_reader.load_start();``//so 被加载的位置``si_->size = elf_reader.load_size();``//表示整个 so 映射到内存的大小：``si_->set_mapped_by_caller(elf_reader.is_mapped_by_caller());``//判断 so 是否是外部提供的 mmap（如 dlopen_extinfo 指定了地址）。``si_->load_bias = elf_reader.load_bias();``//load_bias = real mmap 地址 - ELF p_vaddr 最小值，所有符号地址 = ELF st_value + load_bias，偏移地址``si_->phnum = elf_reader.phdr_count();``//Program Header 数量``si_->phdr = elf_reader.loaded_phdr();``//loaded_phdr 是 PT_PHDR 对应的 phdr 在内存中的实际地址` `return` `true``;``}` |
|-|-|

| 1234567891011121314151617 | `// 重点``bool` `ElfReader::Load(``const` `android_dlextinfo* extinfo) {``CHECK(did_read_);``if` `(did_load_) {``return` `true``;``}``/**``* ReserveAddressSpace和LoadSegments和FindPhdr``*/``if` `(ReserveAddressSpace(extinfo) &&``// 分配空间``LoadSegments() &&``// 按照 program header 指示装载 segments``FindPhdr()) {``// 找到装载后的 phdr 地址``did_load_ =``true``;``}` `return` `did_load_;``}` |
|-|-|

我们先来看第一个方法***ReserveAddressSpace***，我们开一下这个方法的注释，这里的意思是创建一段带有PROT_NONE的私有匿名mmap（），权限为PROT_NONE。

`PROT_NONE` 是 Unix/Linux 系统中用于**内存区域保护权限**的常量（定义在 `<sys/mman.h>` 头文件中），字面意思是 “**无任何访问权限**”—— 被标记为 `PROT_NONE` 的内存页，程序无法执行读（`read`）、写（`write`）、执行（`execute`）任何操作。

通过Linux系统调用，申请一段内存，然后用于后续程序头表的段加载（LOAD）。 **预留一整块连续的虚拟地址空间、 保证所有 PT_LOAD 段可以放进去 。**

代码如下

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273 | `// Reserve a virtual address range big enough to hold all loadable``// segments of a program header table. This is done by creating a``// private anonymous mmap() with PROT_NONE.``bool` `ElfReader::ReserveAddressSpace(``const` `android_dlextinfo* extinfo) {``ElfW(Addr) min_vaddr;``/**``* phdr_table_get_load_size 是 Android 动态链接器的辅助函数，作用是遍历 ELF 程序头表（phdr_table_），``* 统计所有「可加载段（PT_LOAD）」的总大小（load_size_），并输出这些段的「最小虚拟地址（min_vaddr）」。``*/``load_size_ = phdr_table_get_load_size(phdr_table_, phdr_num_, &min_vaddr);``if` `(load_size_ == 0) {``DL_ERR(``"\"%s\" has no loadable segments"``, name_.c_str());``return` `false``;``}``// min_vaddr 一般情况为零，如果不是则表明 SO 指定了加载基址``uint8_t* addr =``reinterpret_cast``<uint8_t*>(min_vaddr);``void``* start;``size_t` `reserved_size = 0;``bool` `reserved_hint =``true``;``bool` `strict_hint =``false``;``// Assume position independent executable by default.``void``* mmap_hint = nullptr;` `if` `(extinfo != nullptr) {``if` `(extinfo->flags & ANDROID_DLEXT_RESERVED_ADDRESS) {``reserved_size = extinfo->reserved_size;``reserved_hint =``false``;``}``else` `if` `(extinfo->flags & ANDROID_DLEXT_RESERVED_ADDRESS_HINT) {``reserved_size = extinfo->reserved_size;``}` `if` `(addr != nullptr && (extinfo->flags & ANDROID_DLEXT_FORCE_FIXED_VADDR) != 0) {``mmap_hint = addr;``}``else` `if` `((extinfo->flags & ANDROID_DLEXT_LOAD_AT_FIXED_ADDRESS) != 0) {``mmap_hint = extinfo->reserved_addr;``strict_hint =``true``;``}``}` `if` `(load_size_ > reserved_size) {``if` `(!reserved_hint) {``DL_ERR(``"reserved address space %zd smaller than %zd bytes needed for \"%s\""``,``reserved_size - load_size_, load_size_, name_.c_str());``return` `false``;``}``/**``* mmap映射``* ReserveAligned 中创建「私有匿名、无权限（PROT_NONE）」的虚拟内存映射，为后续加载 ELF 段（如代码段 .text、数据段 .data）占坑。``*/``start = ReserveAligned(mmap_hint, load_size_, kLibraryAlignment);``if` `(start == nullptr) {``DL_ERR(``"couldn't reserve %zd bytes of address space for \"%s\""``, load_size_, name_.c_str());``return` `false``;``}``if` `(strict_hint && (start != mmap_hint)) {``munmap(start, load_size_);``DL_ERR(``"couldn't reserve %zd bytes of address space at %p for \"%s\""``,``load_size_, mmap_hint, name_.c_str());``return` `false``;``}``}``else` `{``start = extinfo->reserved_addr;``mapped_by_caller_ =``true``;``}` `/**``* 写入成员变量``*/``load_start_ = start;``//实际地址``//load_bias_ 就是「实际地址比期望地址多出来的字节数」，后续所有 ELF 内部的地址（函数、变量、段），都要加上这个偏移量，才能转换成真正能访问的内存地址。``load_bias_ =``reinterpret_cast``<uint8_t*>(start) - addr;``//偏移量``return` `true``;``}` |
|-|-|

phdr_table_get_load_size方法，遍历程序头表，寻找p_type为PT_LOAD类型。

作用

给定一个 ELF 文件的 **Program Header Table (PHDR)**，这个方法要计算：

- 所有 `PT_LOAD` 段的 **最小虚拟地址（min_vaddr）**
- 所有 `PT_LOAD` 段的 **最大虚拟地址（max_vaddr）**
- 它们之间的区间大小：`max_vaddr - min_vaddr`
也就是 ELF 被加载后需要占据的虚拟地址空间范围。

原因

- 把多个 `PT_LOAD` segment（可执行段、数据段、只读数据段等）
**映射到连续的虚拟内存区域**
- address 必须是 **页对齐的**，否则 mmap/内存映射无法正常工作
- 计算好整个加载区域大小才能一次性 mmap 内存

这里拓展一下，PT_LOAD，需要加载到内存的段，例如

- .text
- .rodata
- .data
- .bss

代码如下

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344 | `size_t` `phdr_table_get_load_size(``const` `ElfW(Phdr)* phdr_table,``size_t` `phdr_count,``ElfW(Addr)* out_min_vaddr,``ElfW(Addr)* out_max_vaddr) {``ElfW(Addr) min_vaddr = UINTPTR_MAX;``ElfW(Addr) max_vaddr = 0;` `bool` `found_pt_load =``false``;``for` `(``size_t` `i = 0; i < phdr_count; ++i) {``const` `ElfW(Phdr)* phdr = &phdr_table[i];` `/**``* 程序头表项不是PT_LOAD就跳过``*/``if` `(phdr->p_type != PT_LOAD) {``continue``;``}``found_pt_load =``true``;` `// 找到最小起始地址，可能后续有更小的，然后继续更新``if` `(phdr->p_vaddr < min_vaddr) {``min_vaddr = phdr->p_vaddr;``}``// 找到最大起始地址，可能后续有更小的，然后继续更新``if` `(phdr->p_vaddr + phdr->p_memsz > max_vaddr) {``max_vaddr = phdr->p_vaddr + phdr->p_memsz;``}``}``if` `(!found_pt_load) {``min_vaddr = 0;``}` `// 全部遍历完了，这里开始进行页对齐，这是重点，因为mmap需要内存对齐``// min = 0x1005，page size = 0x1000，对齐之后就是PAGE_START(min) = 0x1000``min_vaddr = PAGE_START(min_vaddr);``max_vaddr = PAGE_END(max_vaddr);` `if` `(out_min_vaddr != nullptr) {``*out_min_vaddr = min_vaddr;``}``if` `(out_max_vaddr != nullptr) {``*out_max_vaddr = max_vaddr;``}``return` `max_vaddr - min_vaddr;``}` |
|-|-|

我们回到***ReserveAddressSpace***方法，phdr_table_get_load_size计算好需要申请的内存大小，接着看核心的流程，这里会进行调用ReserveAligned方法

int mmap_flags = MAP_PRIVATE | MAP_ANONYMOUS;这里设置成了，私有的、以及匿名的flags，根据size，调用mmap预留出地址空间，到此ElfReader::Load的ReserveAddressSpace结束了，所以ReserveAddressSpace计算出PT_LOAD需要的空间，然后mmap预留出地址空间。

代码如下

| 12345678910111213141516171819202122232425262728293031323334353637 | `// Reserve a virtual address range such that if it's limits were extended to the next 2**align``// boundary, it would not overlap with any existing mappings.``static` `void``* ReserveAligned(``void``* hint,``size_t` `size,``size_t` `align) {``int` `mmap_flags = MAP_PRIVATE \| MAP_ANONYMOUS;``// Address hint is only used in Art for the image mapping, and it is pretty important. Don't mess``// with it.``// FIXME: try an aligned allocation and fall back to plain mmap() if the former does not provide a``// mapping at the requested address?``if` `(align == PAGE_SIZE \|\| hint != nullptr) {``void``* mmap_ptr = mmap(hint, size, PROT_NONE, mmap_flags, -1, 0);``if` `(mmap_ptr == MAP_FAILED) {``return` `nullptr;``}``return` `mmap_ptr;``}` `// Allocate enough space so that the end of the desired region aligned up is still inside the``// mapping.``size_t` `mmap_size = align_up(size, align) + align - PAGE_SIZE;``uint8_t* mmap_ptr =``reinterpret_cast``<uint8_t*>(mmap(nullptr, mmap_size, PROT_NONE, mmap_flags, -1, 0));``if` `(mmap_ptr == MAP_FAILED) {``return` `nullptr;``}` `// 进行内存向上对齐``uint8_t* first = align_up(mmap_ptr, align);``// 向下对齐``uint8_t* last = align_down(mmap_ptr + mmap_size, align) - size;``// 计算页数``size_t` `n = arc4random_uniform((last - first) / PAGE_SIZE + 1);``// 计算起始地址``uint8_t* start = first + n * PAGE_SIZE;``munmap(mmap_ptr, start - mmap_ptr);``munmap(start + size, mmap_ptr + mmap_size - (start + size));``return` `start;``}` |
|-|-|

下来进行分析ElfReader::Load的中的***LoadSegments***，该方法是**mmap**所有的***Segments，**比如我们使用****readelf -l libc.so查看的时候。******![image](https://bbs.kanxue.com/upload/tmp/993044_8J7P8NAS98QE5Q5.webp)***

找出Segmen的p_type为PT_LOAD 。

segment 在内存空间中的起始地址 segstart 和结束地址 seg_end，seg_start 等于虚拟偏移加上基址load_bias，同时由于 mmap 的要求，都要对齐到页边界得到 seg_page_start 和 seg_page_end。
计算 segment 在文件中的页对齐后的起始地址 file_page_start 和长度 file_length。

使用 mmap 将 segment 映射到内存，指定映射地址为 seg_page_start，长度为 file_length，文件偏移为 file_page_start。，然后进行加载到上一步预留的地址空间当中

将seg_start和seg_end对齐后得到seg_page_start、seg_page_end，然后调用mmap64，本质就是mmap的别名，进行Segmen映射到seg_page_start的地址中。

代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105 | `bool` `ElfReader::LoadSegments() {``for` `(``size_t` `i = 0; i < phdr_num_; ++i) {``const` `ElfW(Phdr)* phdr = &phdr_table_[i];` `// 只处理PT_LOAD段``if` `(phdr->p_type != PT_LOAD) {``continue``;``}` `// Segment addresses in memory.``// 1. 计算段在内存中的实际地址（ELF 期望地址 + 加载偏移）``ElfW(Addr) seg_start = phdr->p_vaddr + load_bias_;``// 段在内存的起始地址（实际地址）``ElfW(Addr) seg_end   = seg_start + phdr->p_memsz;``// 段在内存的结束地址（含未初始化部分）` `// 2. 内存地址按页对齐（mmap 要求）``ElfW(Addr) seg_page_start = PAGE_START(seg_start);``// 内存页起始（向下对齐到 PAGE_SIZE）``ElfW(Addr) seg_page_end   = PAGE_END(seg_end);``// 内存页结束（向上对齐到 PAGE_SIZE）` `// 3. 计算段在文件中的范围（p_filesz 是文件中实际占用的大小，可能小于 p_memsz）``ElfW(Addr) seg_file_end   = seg_start + phdr->p_filesz;``// 文件内容在内存中的结束地址``// 4. 计算文件偏移的页对齐地址（mmap 读取文件需按页偏移）``// File offsets.``ElfW(Addr) file_start = phdr->p_offset;``ElfW(Addr) file_end   = file_start + phdr->p_filesz;` `ElfW(Addr) file_page_start = PAGE_START(file_start);``ElfW(Addr) file_length = file_end - file_page_start;` `if` `(file_size_ <= 0) {``DL_ERR(``"\"%s\" invalid file size: %"` `PRId64, name_.c_str(), file_size_);``return` `false``;``}` `if` `(file_end >``static_cast``<``size_t``>(file_size_)) {``DL_ERR(``"invalid ELF file \"%s\" load segment[%zd]:"``" p_offset (%p) + p_filesz (%p) ( = %p) past end of file (0x%"` `PRIx64``")"``,``name_.c_str(), i,``reinterpret_cast``<``void``*>(phdr->p_offset),``reinterpret_cast``<``void``*>(phdr->p_filesz),``reinterpret_cast``<``void``*>(file_end), file_size_);``return` `false``;``}` `//W+E 权限的段存在代码注入风险（攻击者可修改代码并执行），Android O 及以上直接禁止，低版本仅警告。``if` `(file_length != 0) {``int` `prot = PFLAGS_TO_PROT(phdr->p_flags);``if` `((prot & (PROT_EXEC \| PROT_WRITE)) == (PROT_EXEC \| PROT_WRITE)) {``// W + E PT_LOAD segments are not allowed in O.``if` `(get_application_target_sdk_version() >= __ANDROID_API_O__) {``DL_ERR_AND_LOG(``"\"%s\": W + E load segments are not allowed"``, name_.c_str());``return` `false``;``}``DL_WARN(``"\"%s\": W + E load segments are not allowed"``, name_.c_str());``add_dlwarning(name_.c_str(),``"W+E load segments"``);``}` `/**``* mmap64映射到地址上``*/``void``* seg_addr = mmap64(``reinterpret_cast``<``void``*>(seg_page_start),``file_length,``prot,``MAP_FIXED\|MAP_PRIVATE,``fd_,``file_offset_ + file_page_start);``if` `(seg_addr == MAP_FAILED) {``DL_ERR(``"couldn't map \"%s\" segment %zd: %s"``, name_.c_str(), i,``strerror``(``errno``));``return` `false``;``}``}` `// if the segment is writable, and does not end on a page boundary,``// zero-fill it until the page limit.``// 如果 segment 可写, 并且没有在页边界结束，那么就将 segemnt end 到页边界的内存清零。``if` `((phdr->p_flags & PF_W) != 0 && PAGE_OFFSET(seg_file_end) > 0) {``memset``(``reinterpret_cast``<``void``*>(seg_file_end), 0, PAGE_SIZE - PAGE_OFFSET(seg_file_end));``}` `seg_file_end = PAGE_END(seg_file_end);` `// seg_file_end is now the first page address after the file``// content. If seg_end is larger, we need to zero anything``// between them. This is done by using a private anonymous``// map for all extra pages.``/**``* ELF 中 p_memsz 可能大于 p_filesz（如 .bss 段在文件中不占空间，仅在内存中分配），这部分需要零填充（C 语言标准要求未初始化全局变量默认为 0）。``*/``// 将 (内存长度 - 文件长度) 对应的内存进行匿名映射，``if` `(seg_page_end > seg_file_end) {``size_t` `zeromap_size = seg_page_end - seg_file_end;``void``* zeromap = mmap(``reinterpret_cast``<``void``*>(seg_file_end),``zeromap_size,``PFLAGS_TO_PROT(phdr->p_flags),``MAP_FIXED\|MAP_ANONYMOUS\|MAP_PRIVATE,``-1,``0);``if` `(zeromap == MAP_FAILED) {``DL_ERR(``"couldn't zero fill \"%s\" gap: %s"``, name_.c_str(),``strerror``(``errno``));``return` `false``;``}` `prctl(PR_SET_VMA, PR_SET_VMA_ANON_NAME, zeromap, zeromap_size,``".bss"``);``}``}``return` `true``;``}` |
|-|-|

到此，***LoadSegments***到此结束，我们继续研究第三个方法**FindPhdr**，先说结论，比较简单，是找到装载后的 phdr 地址。

我们先看一下注释，大概说将loaded_phdr_设置为程序头表显示的地址

 const ElfW(Phdr)* phdr_limit = phdr_table_ + phdr_num_;这里是遍历程序头表，然后寻找p_type为PT_PHDR，找到装载后的 phdr 地址，该方法中，寻找Phdr有两种情况，第一中比较容易，就是在phdr_table_表中，查找p_type为PT_PHDR的；第二种情况，就是在PT_LOAD中且p_offset为0（理解这段代码，必须先记住一个 ELF 规范中的关键特性：如果 ELF 文件的第一个可加载段（PT_LOAD 类型）的「文件偏移（p_offset）= 0」）

代码如下

| 1234567891011121314151617181920212223242526272829303132333435363738 | `// Sets loaded_phdr_ to the address of the program header table as it appears``// in the loaded segments in memory. This is in contrast with phdr_table_,``// which is temporary and will be released before the library is relocated.``bool` `ElfReader::FindPhdr() {``const` `ElfW(Phdr)* phdr_limit = phdr_table_ + phdr_num_;` `// If there is a PT_PHDR, use it directly.``for` `(``const` `ElfW(Phdr)* phdr = phdr_table_; phdr < phdr_limit; ++phdr) {``if` `(phdr->p_type == PT_PHDR) {``return` `CheckPhdr(load_bias_ + phdr->p_vaddr);``}``}` `/**``* 要理解这段代码，必须先记住一个 ELF 规范中的关键特性：如果 ELF 文件的第一个可加载段（PT_LOAD 类型）的「文件偏移（p_offset）= 0」，``* 那么这个段必然包含 ELF 头（ElfW (Ehdr)） —— 因为 ELF 文件的起始位置（偏移 0）就是 ELF 头，``* 而 PT_LOAD 段是要加载到内存的，所以该段加载到内存后，ELF 头也会跟着映射到内存中。``* 而 ELF 头（ElfW(Ehdr)）里有个关键字段 e_phoff：表示「程序头表在 ELF 文件中的偏移地址」。``* 利用这个字段，就能从内存中的 ELF 头，反向找到内存中的程序头表地址。``*/``// Otherwise, check the first loadable segment. If its file offset``// is 0, it starts with the ELF header, and we can trivially find the``// loaded program header from it.``for` `(``const` `ElfW(Phdr)* phdr = phdr_table_; phdr < phdr_limit; ++phdr) {``if` `(phdr->p_type == PT_LOAD) {``if` `(phdr->p_offset == 0) {``ElfW(Addr)  elf_addr = load_bias_ + phdr->p_vaddr;``const` `ElfW(Ehdr)* ehdr =``reinterpret_cast``<``const` `ElfW(Ehdr)*>(elf_addr);``ElfW(Addr)  offset = ehdr->e_phoff;``return` `CheckPhdr(``reinterpret_cast``<ElfW(Addr)>(ehdr) + offset);``}``break``;``}``}` `DL_ERR(``"can't find loaded phdr for \"%s\""``, name_.c_str());``return` `false``;``}` |
|-|-|

到此结束，elf_reader.Load方法结束，我们继续回到linker.cpp的load()方法中，最后初始化si_

代码如下

| 123456789101112131415161718192021222324252627282930313233 | `/**``* load``*/``bool` `load() {``ElfReader& elf_reader = get_elf_reader();``//核心是处理 ELF 文件的 Program Header (PT_LOAD)，把它们 mmap 进内存。``/**``* 准``* 打开 so 文件（或使用 extinfo 中的 fd）``* 读取 ELF header``* 读取 Program Header Table``* 找到所有 PT_LOAD 段``* 使用 mmap() 将 PT_LOAD 段映射到内存``* 修正对齐、权限（PROT_READ/WRITE/EXEC）``* 构建 load_bias``* 找到加载后的 phdr 在内存中的实际地址``*/``if` `(!elf_reader.Load(extinfo_)) {``return` `false``;``}` `/**``* 根据装载结果，更新 soinfo 的成员变量``*/``si_->base = elf_reader.load_start();``//so 被加载的位置，申请为segment预留的空间起始地址``si_->size = elf_reader.load_size();``//表示整个 so 映射到内存的大小：``si_->set_mapped_by_caller(elf_reader.is_mapped_by_caller());``//判断 so 是否是外部提供的 mmap（如 dlopen_extinfo 指定了地址）。``si_->load_bias = elf_reader.load_bias();``//load_bias = real mmap 地址 - ELF p_vaddr 最小值，所有符号地址 = ELF st_value + load_bias，偏移地址``si_->phnum = elf_reader.phdr_count();``//Program Header 数量``si_->phdr = elf_reader.loaded_phdr();``//loaded_phdr 是 PT_PHDR 对应的 phdr 在内存中的实际地址` `return` `true``;``}` |
|-|-|

到此，Step 3，完结。

最后总结一下Step 3。

   * 打开 so 文件（或使用 extinfo 中的 fd）
    * 读取 ELF header
    * 读取 Program Header Table
    * 找到所有 PT_LOAD 段
    * 使用 mmap() 将 PT_LOAD 段映射到内存
    * 修正对齐、权限（PROT_READ/WRITE/EXEC）
    * 构建 load_bias
    * 找到加载后的 phdr 在内存中的实际地址

接下来的Step 3、Step 4比较容易

## Step 3

直接看核心方法，si->is_linked()如果没有被链接，然后调用prelink_image。

| 12345678910111213141516 | `/**``* 所有 DT_NEEDED 依赖的 so（所有 load_tasks）已经加载（load）``* prelink 解析 .dynamic 段（d_tag）``*/``// Step 3: pre-link all DT_NEEDED libraries in breadth first order.``for` `(``auto``&& task : load_tasks) {``soinfo* si = task->get_soinfo();``/**``* is_linked()当前的 so 是否已经被 linker 完整加载并链接成功``* prelink_image() 解析 ELF 的 .dynamic段,设置dynamic的地址和dynamic_flags``* 遍历dynamic section 设置各个d_tag对应的内存地址：``*/``if` `(!si->is_linked() && !si->prelink_image()) {``return` `false``;``}``}` |
|-|-|

我们直接查看***prelink_image***方法，这个方法比较长，以下截取部分代码。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308309310311312313314315316317318319320321322323324325326327328329330331332333334335336337338339340341342343344345346347348349350351352353354355356357358359360361362363364365366367368369370371372373374375376377378379380 | `bool` `soinfo::prelink_image() {``/* Extract dynamic section */``ElfW(Word) dynamic_flags = 0;``phdr_table_get_dynamic_section(phdr, phnum, load_bias, &dynamic, &dynamic_flags);` `/* We can't log anything until the linker is relocated */``bool` `relocating_linker = (flags_ & FLAG_LINKER) != 0;``if` `(!relocating_linker) {``INFO(``"[ Linking \"%s\" ]"``, get_realpath());``DEBUG(``"si->base = %p si->flags = 0x%08x"``,``reinterpret_cast``<``void``*>(base), flags_);``}` `if` `(dynamic == nullptr) {``if` `(!relocating_linker) {``DL_ERR(``"missing PT_DYNAMIC in \"%s\""``, get_realpath());``}``return` `false``;``}``else` `{``if` `(!relocating_linker) {``DEBUG(``"dynamic = %p"``, dynamic);``}``}` `#``if` `defined(__arm__)``(``void``) phdr_table_get_arm_exidx(phdr, phnum, load_bias,``&ARM_exidx, &ARM_exidx_count);``#endif` `// Extract useful information from dynamic section.``// Note that: "Except for the DT_NULL element at the end of the array,``// and the relative order of DT_NEEDED elements, entries may appear in any order."``//``// source: http://www.sco.com/developers/gabi/1998-04-29/ch5.dynamic.html``uint32_t needed_count = 0;``for` `(ElfW(Dyn)* d = dynamic; d->d_tag != DT_NULL; ++d) {``DEBUG(``"d = %p, d[0](tag) = %p d[1](val) = %p"``,``d,``reinterpret_cast``<``void``*>(d->d_tag),``reinterpret_cast``<``void``*>(d->d_un.d_val));``switch` `(d->d_tag) {``case` `DT_SONAME:``// this is parsed after we have strtab initialized (see below).``break``;` `case` `DT_HASH:``nbucket_ =``reinterpret_cast``<uint32_t*>(load_bias + d->d_un.d_ptr)[0];``nchain_ =``reinterpret_cast``<uint32_t*>(load_bias + d->d_un.d_ptr)[1];``bucket_ =``reinterpret_cast``<uint32_t*>(load_bias + d->d_un.d_ptr + 8);``chain_ =``reinterpret_cast``<uint32_t*>(load_bias + d->d_un.d_ptr + 8 + nbucket_ * 4);``break``;` `case` `DT_GNU_HASH:``gnu_nbucket_ =``reinterpret_cast``<uint32_t*>(load_bias + d->d_un.d_ptr)[0];``// skip symndx``gnu_maskwords_ =``reinterpret_cast``<uint32_t*>(load_bias + d->d_un.d_ptr)[2];``gnu_shift2_ =``reinterpret_cast``<uint32_t*>(load_bias + d->d_un.d_ptr)[3];` `gnu_bloom_filter_ =``reinterpret_cast``<ElfW(Addr)*>(load_bias + d->d_un.d_ptr + 16);``gnu_bucket_ =``reinterpret_cast``<uint32_t*>(gnu_bloom_filter_ + gnu_maskwords_);``// amend chain for symndx = header[1]``gnu_chain_ = gnu_bucket_ + gnu_nbucket_ -``reinterpret_cast``<uint32_t*>(load_bias + d->d_un.d_ptr)[1];` `if` `(!powerof2(gnu_maskwords_)) {``DL_ERR(``"invalid maskwords for gnu_hash = 0x%x, in \"%s\" expecting power to two"``,``gnu_maskwords_, get_realpath());``return` `false``;``}``--gnu_maskwords_;` `flags_ \|= FLAG_GNU_HASH;``break``;` `case` `DT_STRTAB:``strtab_ =``reinterpret_cast``<``const` `char``*>(load_bias + d->d_un.d_ptr);``break``;` `case` `DT_STRSZ:``strtab_size_ = d->d_un.d_val;``break``;` `case` `DT_SYMTAB:``symtab_ =``reinterpret_cast``<ElfW(Sym)*>(load_bias + d->d_un.d_ptr);``break``;` `case` `DT_SYMENT:``if` `(d->d_un.d_val !=``sizeof``(ElfW(Sym))) {``DL_ERR(``"invalid DT_SYMENT: %zd in \"%s\""``,``static_cast``<``size_t``>(d->d_un.d_val), get_realpath());``return` `false``;``}``break``;` `case` `DT_PLTREL:``#if defined(USE_RELA)``if` `(d->d_un.d_val != DT_RELA) {``DL_ERR(``"unsupported DT_PLTREL in \"%s\"; expected DT_RELA"``, get_realpath());``return` `false``;``}``#else``if` `(d->d_un.d_val != DT_REL) {``DL_ERR(``"unsupported DT_PLTREL in \"%s\"; expected DT_REL"``, get_realpath());``return` `false``;``}``#endif``break``;` `case` `DT_JMPREL:``#if defined(USE_RELA)``plt_rela_ =``reinterpret_cast``<ElfW(Rela)*>(load_bias + d->d_un.d_ptr);``#else``plt_rel_ =``reinterpret_cast``<ElfW(Rel)*>(load_bias + d->d_un.d_ptr);``#endif``break``;` `case` `DT_PLTRELSZ:``#if defined(USE_RELA)``plt_rela_count_ = d->d_un.d_val /``sizeof``(ElfW(Rela));``#else``plt_rel_count_ = d->d_un.d_val /``sizeof``(ElfW(Rel));``#endif``break``;` `case` `DT_PLTGOT:``#if defined(__mips__)``// Used by mips and mips64.``plt_got_ =``reinterpret_cast``<ElfW(Addr)**>(load_bias + d->d_un.d_ptr);``#endif``// Ignore for other platforms... (because RTLD_LAZY is not supported)``break``;` `case` `DT_DEBUG:``// Set the DT_DEBUG entry to the address of _r_debug for GDB``// if the dynamic table is writable``// FIXME: not working currently for N64``// The flags for the LOAD and DYNAMIC program headers do not agree.``// The LOAD section containing the dynamic table has been mapped as``// read-only, but the DYNAMIC header claims it is writable.``#if !(defined(__mips__) && defined(__LP64__))``if` `((dynamic_flags & PF_W) != 0) {``d->d_un.d_val =``reinterpret_cast``<``uintptr_t``>(&_r_debug);``}``#endif``break``;``#if defined(USE_RELA)``case` `DT_RELA:``rela_ =``reinterpret_cast``<ElfW(Rela)*>(load_bias + d->d_un.d_ptr);``break``;` `case` `DT_RELASZ:``rela_count_ = d->d_un.d_val /``sizeof``(ElfW(Rela));``break``;` `case` `DT_ANDROID_RELA:``android_relocs_ =``reinterpret_cast``<uint8_t*>(load_bias + d->d_un.d_ptr);``break``;` `case` `DT_ANDROID_RELASZ:``android_relocs_size_ = d->d_un.d_val;``break``;` `case` `DT_ANDROID_REL:``DL_ERR(``"unsupported DT_ANDROID_REL in \"%s\""``, get_realpath());``return` `false``;` `case` `DT_ANDROID_RELSZ:``DL_ERR(``"unsupported DT_ANDROID_RELSZ in \"%s\""``, get_realpath());``return` `false``;` `case` `DT_RELAENT:``if` `(d->d_un.d_val !=``sizeof``(ElfW(Rela))) {``DL_ERR(``"invalid DT_RELAENT: %zd"``,``static_cast``<``size_t``>(d->d_un.d_val));``return` `false``;``}``break``;` `// ignored (see DT_RELCOUNT comments for details)``case` `DT_RELACOUNT:``break``;` `case` `DT_REL:``DL_ERR(``"unsupported DT_REL in \"%s\""``, get_realpath());``return` `false``;` `case` `DT_RELSZ:``DL_ERR(``"unsupported DT_RELSZ in \"%s\""``, get_realpath());``return` `false``;` `#else``case` `DT_REL:``rel_ =``reinterpret_cast``<ElfW(Rel)*>(load_bias + d->d_un.d_ptr);``break``;` `case` `DT_RELSZ:``rel_count_ = d->d_un.d_val /``sizeof``(ElfW(Rel));``break``;` `case` `DT_RELENT:``if` `(d->d_un.d_val !=``sizeof``(ElfW(Rel))) {``DL_ERR(``"invalid DT_RELENT: %zd"``,``static_cast``<``size_t``>(d->d_un.d_val));``return` `false``;``}``break``;` `case` `DT_ANDROID_REL:``android_relocs_ =``reinterpret_cast``<uint8_t*>(load_bias + d->d_un.d_ptr);``break``;` `case` `DT_ANDROID_RELSZ:``android_relocs_size_ = d->d_un.d_val;``break``;` `case` `DT_ANDROID_RELA:``DL_ERR(``"unsupported DT_ANDROID_RELA in \"%s\""``, get_realpath());``return` `false``;` `case` `DT_ANDROID_RELASZ:``DL_ERR(``"unsupported DT_ANDROID_RELASZ in \"%s\""``, get_realpath());``return` `false``;` `// "Indicates that all RELATIVE relocations have been concatenated together,``// and specifies the RELATIVE relocation count."``//``// TODO: Spec also mentions that this can be used to optimize relocation process;``// Not currently used by bionic linker - ignored.``case` `DT_RELCOUNT:``break``;` `case` `DT_RELA:``DL_ERR(``"unsupported DT_RELA in \"%s\""``, get_realpath());``return` `false``;` `case` `DT_RELASZ:``DL_ERR(``"unsupported DT_RELASZ in \"%s\""``, get_realpath());``return` `false``;` `#endif``case` `DT_INIT:``init_func_ =``reinterpret_cast``<linker_ctor_function_t>(load_bias + d->d_un.d_ptr);``DEBUG(``"%s constructors (DT_INIT) found at %p"``, get_realpath(), init_func_);``break``;` `case` `DT_FINI:``fini_func_ =``reinterpret_cast``<linker_dtor_function_t>(load_bias + d->d_un.d_ptr);``DEBUG(``"%s destructors (DT_FINI) found at %p"``, get_realpath(), fini_func_);``break``;` `case` `DT_INIT_ARRAY:``init_array_ =``reinterpret_cast``<linker_ctor_function_t*>(load_bias + d->d_un.d_ptr);``DEBUG(``"%s constructors (DT_INIT_ARRAY) found at %p"``, get_realpath(), init_array_);``break``;` `case` `DT_INIT_ARRAYSZ:``init_array_count_ =``static_cast``<uint32_t>(d->d_un.d_val) /``sizeof``(ElfW(Addr));``break``;` `case` `DT_FINI_ARRAY:``fini_array_ =``reinterpret_cast``<linker_dtor_function_t*>(load_bias + d->d_un.d_ptr);``DEBUG(``"%s destructors (DT_FINI_ARRAY) found at %p"``, get_realpath(), fini_array_);``break``;` `case` `DT_FINI_ARRAYSZ:``fini_array_count_ =``static_cast``<uint32_t>(d->d_un.d_val) /``sizeof``(ElfW(Addr));``break``;` `case` `DT_PREINIT_ARRAY:``preinit_array_ =``reinterpret_cast``<linker_ctor_function_t*>(load_bias + d->d_un.d_ptr);``DEBUG(``"%s constructors (DT_PREINIT_ARRAY) found at %p"``, get_realpath(), preinit_array_);``break``;` `case` `DT_PREINIT_ARRAYSZ:``preinit_array_count_ =``static_cast``<uint32_t>(d->d_un.d_val) /``sizeof``(ElfW(Addr));``break``;` `case` `DT_TEXTREL:``#if defined(__LP64__)``DL_ERR(``"\"%s\" has text relocations"``, get_realpath());``return` `false``;``#else``has_text_relocations =``true``;``break``;``#endif` `case` `DT_SYMBOLIC:``has_DT_SYMBOLIC =``true``;``break``;` `case` `DT_NEEDED:``++needed_count;``break``;` `case` `DT_FLAGS:``if` `(d->d_un.d_val & DF_TEXTREL) {``#if defined(__LP64__)``DL_ERR(``"\"%s\" has text relocations"``, get_realpath());``return` `false``;``#else``has_text_relocations =``true``;``#endif``}``if` `(d->d_un.d_val & DF_SYMBOLIC) {``has_DT_SYMBOLIC =``true``;``}``break``;` `case` `DT_FLAGS_1:``set_dt_flags_1(d->d_un.d_val);` `if` `((d->d_un.d_val & ~SUPPORTED_DT_FLAGS_1) != 0) {``DL_WARN(``"\"%s\" has unsupported flags DT_FLAGS_1=%p"``, get_realpath(),``reinterpret_cast``<``void``*>(d->d_un.d_val));``}``break``;``#if defined(__mips__)``case` `DT_MIPS_RLD_MAP:``// Set the DT_MIPS_RLD_MAP entry to the address of _r_debug for GDB.``{``r_debug** dp =``reinterpret_cast``<r_debug**>(load_bias + d->d_un.d_ptr);``*dp = &_r_debug;``}``break``;``case` `DT_MIPS_RLD_MAP_REL:``// Set the DT_MIPS_RLD_MAP_REL entry to the address of _r_debug for GDB.``{``r_debug** dp =``reinterpret_cast``<r_debug**>(``reinterpret_cast``<ElfW(Addr)>(d) + d->d_un.d_val);``*dp = &_r_debug;``}``break``;` `case` `DT_MIPS_RLD_VERSION:``case` `DT_MIPS_FLAGS:``case` `DT_MIPS_BASE_ADDRESS:``case` `DT_MIPS_UNREFEXTNO:``break``;` `case` `DT_MIPS_SYMTABNO:``mips_symtabno_ = d->d_un.d_val;``break``;` `case` `DT_MIPS_LOCAL_GOTNO:``mips_local_gotno_ = d->d_un.d_val;``break``;` `case` `DT_MIPS_GOTSYM:``mips_gotsym_ = d->d_un.d_val;``break``;``#endif``// Ignored: "Its use has been superseded by the DF_BIND_NOW flag"``case` `DT_BIND_NOW:``break``;` `case` `DT_VERSYM:``versym_ =``reinterpret_cast``<ElfW(Versym)*>(load_bias + d->d_un.d_ptr);``break``;` `case` `DT_VERDEF:``verdef_ptr_ = load_bias + d->d_un.d_ptr;``break``;``case` `DT_VERDEFNUM:``verdef_cnt_ = d->d_un.d_val;``break``;` `case` `DT_VERNEED:``verneed_ptr_ = load_bias + d->d_un.d_ptr;``break``;` `case` `DT_VERNEEDNUM:``verneed_cnt_ = d->d_un.d_val;``break``;` `case` `DT_RUNPATH:``// this is parsed after we have strtab initialized (see below).``break``;` `default``:``if` `(!relocating_linker) {``DL_WARN(``"\"%s\" unused DT entry: type %p arg %p"``, get_realpath(),``reinterpret_cast``<``void``*>(d->d_tag),``reinterpret_cast``<``void``*>(d->d_un.d_val));``}``break``;``}``}` |
|-|-|

先看***phdr_table_get_dynamic_section***方法，上面写有注释，意思是返回ELF文件的dynamic section，但是这dynamic section在上一篇文章（1）中已经进行了，加载了映射了。但是这里为什么又再去加载呢，我们接着往下看。

这要要回顾上一篇文章中，介绍了load_bias_ = reinterpret_cast<uint8_t*>(start) - addr;这行代码的意思就是，当前elf加载到内存的地址，而addr是so在编译时期进行确定的，而start是每次mmap的地址，load_bias_则是偏移量，后续涉及so之类的地址访问，加载，都会加上这个偏移，才能正确访问到。下面这张图可以看到，确实是加上了，load_bias_偏移量。所以这个phdr_table_get_dynamic_section方法，获取了程序头表的dynamic_section的虚拟地址，这个地址是编译时确定，dynamic是soinfo的成员变量。所以这里就是设置了，内存的真实地址。以及设置了dynamic_flags的flags。flags具体的可以上一篇文章中推荐的书，当中有介，绍这里不赘述。

在上一篇文章的结论中，映射地址，**映射了程序头表、节头表、dynamic section 到内存地址中**，这些地址都保存在了ElfReader当中。

![image](https://bbs.kanxue.com/upload/attach/202512/EM6GDG8AQ2UMYQD.jpg)

| 12345678910111213141516171819202122232425262728 | `/* Return the address and size of the ELF file's .dynamic section in memory,``* or null if missing.``*``* Input:``*   phdr_table  -> program header table``*   phdr_count  -> number of entries in tables``*   load_bias   -> load bias``* Output:``*   dynamic       -> address of table in memory (null on failure).``*   dynamic_flags -> protection flags for section (unset on failure)``* Return:``*   void``*/``void` `phdr_table_get_dynamic_section(``const` `ElfW(Phdr)* phdr_table,``size_t` `phdr_count,``ElfW(Addr) load_bias, ElfW(Dyn)** dynamic,``ElfW(Word)* dynamic_flags) {``*dynamic = nullptr;``for` `(``size_t` `i = 0; i<phdr_count; ++i) {``const` `ElfW(Phdr)& phdr = phdr_table[i];``if` `(phdr.p_type == PT_DYNAMIC) {``*dynamic =``reinterpret_cast``<ElfW(Dyn)*>(load_bias + phdr.p_vaddr);``if` `(dynamic_flags) {``*dynamic_flags = phdr.p_flags;``}``return``;``}``}``}` |
|-|-|

继续回到***prelink_image***方法中，直接看主流程for (ElfW(Dyn)* d = dynamic; d->d_tag != DT_NULL; ++d)这个循环。遍历dynamic，这里需要扩展一个知识点，dynamic这个section的最后一项是DT_NULL，所以这个循环的结束就是DT_NULL。

遍历dynamic table，我们来看一下，elf.h对dynamic的每一项对应的结构体。这里拿64位的举例，Elf64_Dyn。这里结合本书来看会比较清晰。

![image](https://bbs.kanxue.com/upload/attach/202512/JUACSN27KNA5EGQ.jpg)

| 12345678910 | `// Dynamic table entry for ELF64.``struct` `Elf64_Dyn``{``Elf64_Sxword d_tag;``// Type of dynamic table entry.``union``{``Elf64_Xword d_val;``// Integer value of entry.``Elf64_Addr  d_ptr;``// Pointer value of entry.``} d_un;``};` |
|-|-|

以及d_tag的取值枚举

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129 | `// Dynamic table entry tags.``enum` `{``DT_NULL         = 0,``// Marks end of dynamic array.``DT_NEEDED       = 1,``// String table offset of needed library.``DT_PLTRELSZ     = 2,``// Size of relocation entries in PLT.``DT_PLTGOT       = 3,``// Address associated with linkage table.``DT_HASH         = 4,``// Address of symbolic hash table.``DT_STRTAB       = 5,``// Address of dynamic string table.``DT_SYMTAB       = 6,``// Address of dynamic symbol table.``DT_RELA         = 7,``// Address of relocation table (Rela entries).``DT_RELASZ       = 8,``// Size of Rela relocation table.``DT_RELAENT      = 9,``// Size of a Rela relocation entry.``DT_STRSZ        = 10,``// Total size of the string table.``DT_SYMENT       = 11,``// Size of a symbol table entry.``DT_INIT         = 12,``// Address of initialization function.``DT_FINI         = 13,``// Address of termination function.``DT_SONAME       = 14,``// String table offset of a shared objects name.``DT_RPATH        = 15,``// String table offset of library search path.``DT_SYMBOLIC     = 16,``// Changes symbol resolution algorithm.``DT_REL          = 17,``// Address of relocation table (Rel entries).``DT_RELSZ        = 18,``// Size of Rel relocation table.``DT_RELENT       = 19,``// Size of a Rel relocation entry.``DT_PLTREL       = 20,``// Type of relocation entry used for linking.``DT_DEBUG        = 21,``// Reserved for debugger.``DT_TEXTREL      = 22,``// Relocations exist for non-writable segments.``DT_JMPREL       = 23,``// Address of relocations associated with PLT.``DT_BIND_NOW     = 24,``// Process all relocations before execution.``DT_INIT_ARRAY   = 25,``// Pointer to array of initialization functions.``DT_FINI_ARRAY   = 26,``// Pointer to array of termination functions.``DT_INIT_ARRAYSZ = 27,``// Size of DT_INIT_ARRAY.``DT_FINI_ARRAYSZ = 28,``// Size of DT_FINI_ARRAY.``DT_RUNPATH      = 29,``// String table offset of lib search path.``DT_FLAGS        = 30,``// Flags.``DT_ENCODING     = 32,``// Values from here to DT_LOOS follow the rules``// for the interpretation of the d_un union.` `DT_PREINIT_ARRAY = 32,``// Pointer to array of preinit functions.``DT_PREINIT_ARRAYSZ = 33,``// Size of the DT_PREINIT_ARRAY array.` `DT_LOOS         = 0x60000000,``// Start of environment specific tags.``DT_HIOS         = 0x6FFFFFFF,``// End of environment specific tags.``DT_LOPROC       = 0x70000000,``// Start of processor specific tags.``DT_HIPROC       = 0x7FFFFFFF,``// End of processor specific tags.` `DT_GNU_HASH     = 0x6FFFFEF5,``// Reference to the GNU hash table.``DT_RELACOUNT    = 0x6FFFFFF9,``// ELF32_Rela count.``DT_RELCOUNT     = 0x6FFFFFFA,``// ELF32_Rel count.` `DT_FLAGS_1      = 0X6FFFFFFB,``// Flags_1.``DT_VERSYM       = 0x6FFFFFF0,``// The address of .gnu.version section.``DT_VERDEF       = 0X6FFFFFFC,``// The address of the version definition table.``DT_VERDEFNUM    = 0X6FFFFFFD,``// The number of entries in DT_VERDEF.``DT_VERNEED      = 0X6FFFFFFE,``// The address of the version Dependency table.``DT_VERNEEDNUM   = 0X6FFFFFFF,``// The number of entries in DT_VERNEED.` `// Mips specific dynamic table entry tags.``DT_MIPS_RLD_VERSION   = 0x70000001,``// 32 bit version number for runtime``// linker interface.``DT_MIPS_TIME_STAMP    = 0x70000002,``// Time stamp.``DT_MIPS_ICHECKSUM     = 0x70000003,``// Checksum of external strings``// and common sizes.``DT_MIPS_IVERSION      = 0x70000004,``// Index of version string``// in string table.``DT_MIPS_FLAGS         = 0x70000005,``// 32 bits of flags.``DT_MIPS_BASE_ADDRESS  = 0x70000006,``// Base address of the segment.``DT_MIPS_MSYM          = 0x70000007,``// Address of .msym section.``DT_MIPS_CONFLICT      = 0x70000008,``// Address of .conflict section.``DT_MIPS_LIBLIST       = 0x70000009,``// Address of .liblist section.``DT_MIPS_LOCAL_GOTNO   = 0x7000000a,``// Number of local global offset``// table entries.``DT_MIPS_CONFLICTNO    = 0x7000000b,``// Number of entries``// in the .conflict section.``DT_MIPS_LIBLISTNO     = 0x70000010,``// Number of entries``// in the .liblist section.``DT_MIPS_SYMTABNO      = 0x70000011,``// Number of entries``// in the .dynsym section.``DT_MIPS_UNREFEXTNO    = 0x70000012,``// Index of first external dynamic symbol``// not referenced locally.``DT_MIPS_GOTSYM        = 0x70000013,``// Index of first dynamic symbol``// in global offset table.``DT_MIPS_HIPAGENO      = 0x70000014,``// Number of page table entries``// in global offset table.``DT_MIPS_RLD_MAP       = 0x70000016,``// Address of run time loader map,``// used for debugging.``DT_MIPS_DELTA_CLASS       = 0x70000017,``// Delta C++ class definition.``DT_MIPS_DELTA_CLASS_NO    = 0x70000018,``// Number of entries``// in DT_MIPS_DELTA_CLASS.``DT_MIPS_DELTA_INSTANCE    = 0x70000019,``// Delta C++ class instances.``DT_MIPS_DELTA_INSTANCE_NO = 0x7000001A,``// Number of entries``// in DT_MIPS_DELTA_INSTANCE.``DT_MIPS_DELTA_RELOC       = 0x7000001B,``// Delta relocations.``DT_MIPS_DELTA_RELOC_NO    = 0x7000001C,``// Number of entries``// in DT_MIPS_DELTA_RELOC.``DT_MIPS_DELTA_SYM         = 0x7000001D,``// Delta symbols that Delta``// relocations refer to.``DT_MIPS_DELTA_SYM_NO      = 0x7000001E,``// Number of entries``// in DT_MIPS_DELTA_SYM.``DT_MIPS_DELTA_CLASSSYM    = 0x70000020,``// Delta symbols that hold``// class declarations.``DT_MIPS_DELTA_CLASSSYM_NO = 0x70000021,``// Number of entries``// in DT_MIPS_DELTA_CLASSSYM.``DT_MIPS_CXX_FLAGS         = 0x70000022,``// Flags indicating information``// about C++ flavor.``DT_MIPS_PIXIE_INIT        = 0x70000023,``// Pixie information.``DT_MIPS_SYMBOL_LIB        = 0x70000024,``// Address of .MIPS.symlib``DT_MIPS_LOCALPAGE_GOTIDX  = 0x70000025,``// The GOT index of the first PTE``// for a segment``DT_MIPS_LOCAL_GOTIDX      = 0x70000026,``// The GOT index of the first PTE``// for a local symbol``DT_MIPS_HIDDEN_GOTIDX     = 0x70000027,``// The GOT index of the first PTE``// for a hidden symbol``DT_MIPS_PROTECTED_GOTIDX  = 0x70000028,``// The GOT index of the first PTE``// for a protected symbol``DT_MIPS_OPTIONS           = 0x70000029,``// Address of `.MIPS.options'.``DT_MIPS_INTERFACE         = 0x7000002A,``// Address of `.interface'.``DT_MIPS_DYNSTR_ALIGN      = 0x7000002B,``// Unknown.``DT_MIPS_INTERFACE_SIZE    = 0x7000002C,``// Size of the .interface section.``DT_MIPS_RLD_TEXT_RESOLVE_ADDR = 0x7000002D,``// Size of rld_text_resolve``// function stored in the GOT.``DT_MIPS_PERF_SUFFIX       = 0x7000002E,``// Default suffix of DSO to be added``// by rld on dlopen() calls.``DT_MIPS_COMPACT_SIZE      = 0x7000002F,``// Size of compact relocation``// section (O32).``DT_MIPS_GP_VALUE          = 0x70000030,``// GP value for auxiliary GOTs.``DT_MIPS_AUX_DYNAMIC       = 0x70000031,``// Address of auxiliary .dynamic.``DT_MIPS_PLTGOT            = 0x70000032,``// Address of the base of the PLTGOT.``DT_MIPS_RWPLT             = 0x70000034``// Points to the base``// of a writable PLT.``};` |
|-|-|

在循环中，有个switch，就是挨个对应地址到soinfo这个结构体当中。这里挑选两个来讲解，我们看一下dynacmic表中的strtab，dynacmic内部有自己维护一个strtab。代码中可以看使用了load_bias个偏移量，来计算真是第内存地址。strtab_这个是在soinfo这个结构体中。

| 123 | `case` `DT_STRTAB:``strtab_ =``reinterpret_cast``<``const` `char``*>(load_bias + d->d_un.d_ptr);``break``;` |
|-|-|

再举一个例子

| 123456789101112131415161718192021222324252627282930313233343536 | `case` `DT_INIT:``init_func_ =``reinterpret_cast``<linker_ctor_function_t>(load_bias + d->d_un.d_ptr);``DEBUG(``"%s constructors (DT_INIT) found at %p"``, get_realpath(), init_func_);``break``;` `case` `DT_FINI:``fini_func_ =``reinterpret_cast``<linker_dtor_function_t>(load_bias + d->d_un.d_ptr);``DEBUG(``"%s destructors (DT_FINI) found at %p"``, get_realpath(), fini_func_);``break``;` `case` `DT_INIT_ARRAY:``init_array_ =``reinterpret_cast``<linker_ctor_function_t*>(load_bias + d->d_un.d_ptr);``DEBUG(``"%s constructors (DT_INIT_ARRAY) found at %p"``, get_realpath(), init_array_);``break``;` `case` `DT_INIT_ARRAYSZ:``init_array_count_ =``static_cast``<uint32_t>(d->d_un.d_val) /``sizeof``(ElfW(Addr));``break``;` `case` `DT_FINI_ARRAY:``fini_array_ =``reinterpret_cast``<linker_dtor_function_t*>(load_bias + d->d_un.d_ptr);``DEBUG(``"%s destructors (DT_FINI_ARRAY) found at %p"``, get_realpath(), fini_array_);``break``;` `case` `DT_FINI_ARRAYSZ:``fini_array_count_ =``static_cast``<uint32_t>(d->d_un.d_val) /``sizeof``(ElfW(Addr));``break``;` `case` `DT_PREINIT_ARRAY:``preinit_array_ =``reinterpret_cast``<linker_ctor_function_t*>(load_bias + d->d_un.d_ptr);``DEBUG(``"%s constructors (DT_PREINIT_ARRAY) found at %p"``, get_realpath(), preinit_array_);``break``;` `case` `DT_PREINIT_ARRAYSZ:``preinit_array_count_ =``static_cast``<uint32_t>(d->d_un.d_val) /``sizeof``(ElfW(Addr));``break``;` |
|-|-|

**DT_INIT / DT_FINI 是旧式单函数构造/析构；**DT_INIT_ARRAY / DT_FINI_ARRAY 是现代、多函数构造/析构数组。**现在几乎所有 C++ 全局对象初始化、静态变量初始化都靠 ARRAY 的机制实现。*

DT_INIT、DT_FINI、DT_INIT_ARRAY、DT_FINI_ARRAY我们再逆向分析so的时候，经常看到这个section。一般加壳的so解密的时机，或者是一些检测的时机，比如frida检测时机。

![image](https://bbs.kanxue.com/upload/attach/202512/YBUBB65WDVK4DXZ.jpg)

回到prelink_image方法，继续往下看，第二次遍历dynamic表，第一遍已经初始化好了strtab，这次就可以设置DT_SONAME就是so名字、以及DT_RUNPATH、运行时候解析库查找路径 。然后下面这一段看描述翻译，似乎说dt_soname不存在的时候，会停止运行。然后如何解决这个问题的，这里不关注。至此，prelink_image方法完结。

prelink_image方法片段，代码如下

| 123456789101112131415161718192021222324252627 | `// second pass - parse entries relying on strtab``for` `(ElfW(Dyn)* d = dynamic; d->d_tag != DT_NULL; ++d) {``switch` `(d->d_tag) {``case` `DT_SONAME:``set_soname(get_string(d->d_un.d_val));``break``;``case` `DT_RUNPATH:``set_dt_runpath(get_string(d->d_un.d_val));``break``;``}``}` `// Before M release linker was using basename in place of soname.``// In the case when dt_soname is absent some apps stop working``// because they can't find dt_needed library by soname.``// This workaround should keep them working. (applies only``// for apps targeting sdk version < M). Make an exception for``// the main executable and linker; they do not need to have dt_soname``if` `(soname_ == nullptr &&``this` `!= solist_get_somain() &&``(flags_ & FLAG_LINKER) == 0 &&``get_application_target_sdk_version() < __ANDROID_API_M__) {``soname_ = basename(realpath_.c_str());``DL_WARN(``"%s: is missing DT_SONAME will use basename as a replacement: \"%s\""``,``get_realpath(), soname_);``// Don't call add_dlwarning because a missing DT_SONAME isn't important enough to show in the UI``}` |
|-|-|

## 总结

 打开 so 文件（或使用 extinfo 中的 fd）

找到所有 PT_LOAD 段

使用 mmap() 将 PT_LOAD 段映射到内存

修正对齐、权限（PROT_READ/WRITE/EXEC）

找到加载后的 phdr 在内存中的实际地址

prelink_image() 是 so 加载流程中 “重定位之前的准备阶段”

解析 `.dynamic` 段，建立符号查找所需的全部元数据。
它不做重定位、也不做初始化，只做“符号表解析 + 构造 soinfo”

最后笔者能力有限，本文难免存在疏漏或者理解错误，恳请读者不吝赐教与指正。

---

# 回复

## 回复 by KanXue_NG (#2)

*2025-12-3 09:49*

学习

## 回复 by Sharp_Wang (#3)

*2025-12-3 13:54*

666

## 回复 by Imxz (#4)

*2025-12-3 14:22*

TQL

## 回复 by mb_jnmxfjku (#5)

*2025-12-3 15:08*

11

## 回复 by LQ6H (#6)

*2025-12-4 10:43*

666

## 回复 by iBa0 (#7)

*2025-12-4 10:44*

1

## 回复 by 钱钱钱￥ (#8)

*2025-12-8 15:40*

111

## 回复 by mb_uvyukvot (#9)

*2025-12-9 11:28*

tql

## 回复 by aceding (#10)

*2025-12-28 23:10*

感谢分享

## 回复 by 0x25519 (#11)

*2025-12-29 18:05*

学习

## 回复 by GEKEZYX (#12)

*2025-12-30 09:58*

666

## 回复 by 温泉划水鱼 (#13)

*2026-1-5 01:12*

666

## 回复 by XCicada (#14)

*2026-1-24 20:47*

回复来看看，先谢过楼主！

## 回复 by mb_pkoigpim (#15)

*2026-1-25 01:00*

666

## 回复 by Viseris (#16)

*2026-1-28 21:23*

6666

## 回复 by fengvmu (#17)

*2026-1-29 09:51*

6

## 回复 by 小今朝 (#18)

*2026-2-5 13:53*

666

## 回复 by 落花为谁 (#19)

*2026-2-10 14:50*

666

## 回复 by qig (#20)

*2026-2-13 11:30*

666

## 回复 by 饮岁 (#21)

*2026-2-24 10:14*

666

## 回复 by dsr000 (#22)

*2026-2-25 16:40*

666

## 回复 by xeiyu (#23)

*2026-3-4 00:33*

66

## 回复 by SomeMx (#24)

*2026-3-4 04:00*

看看

## 回复 by mb_ttdxmirg (#25)

*2026-3-14 17:57*

666

## 回复 by mb_ugryjzdr (#26)

*2026-3-16 16:57*

666

## 回复 by 晴空万里丶 (#27)

*2026-3-21 17:09*

学习下

## 回复 by 小迷糊ddd (#28)

*2026-4-7 09:17*

感谢分享，学习一下。

## 回复 by fzyspark (#29)

*2026-4-23 12:12*

![image](https://bbs.kanxue.com/view/img/face/079.gif)
