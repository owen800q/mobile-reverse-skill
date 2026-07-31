---
title: '[原创]自實現Linker加載so'
url: https://bbs.kanxue.com/thread-282316.htm
tid: 282316
author: ngiokweng
date: '2024-06-28'
tags: [Android安全, 原创, 基础理论, 程序开发]
crawled_at: '2026-07-31T14:24:32+08:00'
replies: 40
---

# 前言

前一陣子在研究so加固，發現其中涉及自實現的Linker加載so的技術，而我對此知之什少，因此只好先來學習下Linker的加載流程。

本文參考AOSP源碼和[r0ysue大佬的文章](https://bbs.kanxue.com/thread-269484.htm)( 不知為何文中給出的那個demo我一直跑不起來 )來實現一個簡單的自實現Linker Demo。

環境：`Pixel1XL`、`AOSP - Oreo - 8.1.0_r81`

# Demo實現

Linker在加載so時大致可以分成五步：

1. 讀取so文件：讀取ehdr( Elf header )、phdr( Program header )等信息。
2. 載入so：預留一片內存空間，隨後將相關信息加載進去，最後修正so。
3. 預鏈接：主要處理`.dynamic`節的內容。
4. 正式鏈接：處理重定位的信息。
5. 調用`.init`、`.init_array`

## `Read`

利用`open`+`mmap`來將待加載的so文件映射到內存空間，存放在`start_addr_`中。然後調用`Read`函數來獲取ehdr、phdr等信息。

| 123456789101112 | `int` `fd;``struct` `stat sb;``fd = open(path, O_RDONLY);``fstat(fd, &sb);``start_addr_ =` `static_cast``<``void` `**>(mmap(NULL, sb.st_size, PROT_READ \| PROT_WRITE, MAP_PRIVATE, fd, 0));` `// 1. 讀取so文件``if``(!Read(path, fd, 0, sb.st_size)){``LOGD(``"Read so failed"``);``munmap(start_addr_, sb.st_size);``close(fd);``}` |
|-|-|

`Read`函數實現如下，調用`ReadElfHeader`和`ReadProgramHeaders`來讀取ehdr和phdr。

AOSP源碼的`Read`中還會讀取Section Headers和Dynamic節，一開始我也有實現這部份的邏輯，但後來發現讀取後的信息根本沒有被用到，因此就把這部份給刪了。

| 123456789101112131415 | `bool` `MyLoader::Read(``const` `char``* name,` `int` `fd, off64_t file_offset, off64_t file_size) {``bool` `res =` `false``;` `name_ = name;``fd_ = fd;``file_offset_ = file_offset;``file_size_ = file_size;` `if` `(ReadElfHeader() &&``ReadProgramHeaders()) {``res =` `true``;``}` `return` `res;``}` |
|-|-|

`ReadElfHeader`的實現如下，直接通過`memcpy`來賦值。

| 123 | `bool` `MyLoader::ReadElfHeader() {``return` `memcpy``(&(header_),start_addr_,``sizeof``(header_));``}` |
|-|-|

`ReadProgramHeaders`的實現直接copy源碼就可以，本質上還是內存映射的過程。

| 1234567891011121314151617181920212223242526272829303132333435363738 | `bool` `MyLoader::ReadProgramHeaders() {` `phdr_num_ = header_.e_phnum;` `size_t` `size = phdr_num_ *` `sizeof``(ElfW(Phdr));` `void``* data = Utils::getMapData(fd_, file_offset_, header_.e_phoff, size);``if``(data == nullptr) {``LOGE(``"ProgramHeader mmap failed"``);``return` `false``;``}``phdr_table_ =` `static_cast``<ElfW(Phdr)*>(data);` `return` `true``;``}` `void``* Utils::getMapData(``int` `fd, off64_t base_offset,` `size_t` `elf_offset,` `size_t` `size) {``off64_t offset;``safe_add(&offset, base_offset, elf_offset);` `off64_t page_min = page_start(offset);``off64_t end_offset;` `safe_add(&end_offset, offset, size);``safe_add(&end_offset, end_offset, page_offset(offset));` `size_t` `map_size =` `static_cast``<``size_t``>(end_offset - page_min);` `uint8_t* map_start =` `static_cast``<uint8_t*>(``mmap64(nullptr, map_size, PROT_READ, MAP_PRIVATE, fd, page_min));` `if` `(map_start == MAP_FAILED) {``return` `nullptr;``}` `return` `map_start + page_offset(offset);` `}` |
|-|-|

## `Load`

### 載入so基本信息

調用`Load`來載入so。

| 123456 | `// 2. 載入so``if``(!Load()) {``LOGD(``"Load so failed"``);``munmap(start_addr_, sb.st_size);``close(fd);``}` |
|-|-|

`Load`的實現如下：

`ReserveAddressSpace`用於生成一片新的內存空間，之後的操作基本上都是在這片內存空間進行。`LoadSegments`、`FindPhdr`用於將待加載so的對應信息填充到此內存空間。

最後要修正so，將當前so修正為待加載的so，這部份放到後面來解析。

| 1234567891011121314151617181920212223242526272829303132 | `bool` `MyLoader::Load() {``bool` `res =` `false``;``if` `(ReserveAddressSpace() &&``LoadSegments() &&``FindPhdr()) {` `LOGD(``"Load Done........."``);``res =` `true``;``}` `// 獲取當前so (加載器的so)``si_ = Utils::get_soinfo(``"libnglinker.so"``);` `if``(!si_) {``LOGE(``"si_ return nullptr"``);``return` `false``;``}``LOGD(``"si_ -> base: %lx"``, si_->base);` `// 使si_可以被修改``mprotect((``void``*) PAGE_START(``reinterpret_cast``<ElfW(Addr)>(si_)), 0x1000, PROT_READ \| PROT_WRITE);` `// 修正so``si_->base = load_start();``si_->size = load_size();``//        si_->set_mapped_by_caller(elf_reader.is_mapped_by_caller());``si_->load_bias = load_bias();``si_->phnum = phdr_count();``si_->phdr = loaded_phdr();` `return` `res;``}` |
|-|-|

`ReserveAddressSpace`的具體實現如下，先計算出`load_size_`後`mmap`一片內存，在我這個demo中`min_vaddr`是`0`，因此`load_start_ == load_bias_`，`load_bias_`代表的就是這片內存，而這片內存是用來存放待加載的so。

| 1234567891011121314151617181920212223 | `bool` `MyLoader::ReserveAddressSpace() {``ElfW(Addr) min_vaddr;``load_size_ = phdr_table_get_load_size(phdr_table_, phdr_num_, &min_vaddr);``LOGD(``"load_size_: %x"``, load_size_);``if` `(load_size_ == 0) {``LOGE(``"\"%s\" has no loadable segments"``, name_.c_str());``return` `false``;``}` `uint8_t* addr =` `reinterpret_cast``<uint8_t*>(min_vaddr);` `void``* start;` `// Assume position independent executable by default.``void``* mmap_hint = nullptr;` `start = mmap(mmap_hint, load_size_, PROT_NONE, MAP_PRIVATE \| MAP_ANONYMOUS, -1, 0);` `load_start_ = start;``load_bias_ =` `reinterpret_cast``<uint8_t*>(start) - addr;` `return` `true``;``}` |
|-|-|

`LoadSegments`的具體實現如下，遍歷Program Header Table將所有type為`PT_LOAD`的段加載進內存，源碼中是采用`mmap`來映射，但我嘗試後發現會有權限問題，因而采用`memcpy`的方案。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374757677787980 | `bool` `MyLoader::LoadSegments() {``// 在這個函數中會往 ReserveAddressSpace``// 裡mmap的那片內存填充數據` `for` `(``size_t` `i = 0; i < phdr_num_; ++i) {``const` `ElfW(Phdr)* phdr = &phdr_table_[i];` `if` `(phdr->p_type != PT_LOAD) {``continue``;``}` `// Segment addresses in memory.``ElfW(Addr) seg_start = phdr->p_vaddr + load_bias_;``ElfW(Addr) seg_end   = seg_start + phdr->p_memsz;` `ElfW(Addr) seg_page_start = PAGE_START(seg_start);``ElfW(Addr) seg_page_end   = PAGE_END(seg_end);` `ElfW(Addr) seg_file_end   = seg_start + phdr->p_filesz;` `// File offsets.``ElfW(Addr) file_start = phdr->p_offset;``ElfW(Addr) file_end   = file_start + phdr->p_filesz;` `ElfW(Addr) file_page_start = PAGE_START(file_start);``ElfW(Addr) file_length = file_end - file_page_start;` `if` `(file_size_ <= 0) {``LOGE(``"\"%s\" invalid file size: %"``, name_.c_str(), file_size_);``return` `false``;``}` `if` `(file_end >` `static_cast``<``size_t``>(file_size_)) {``LOGE(``"invalid ELF file"``);``return` `false``;``}` `if` `(file_length != 0) {``// 按AOSP裡那樣用mmap會有問題, 因此改為直接 memcpy``mprotect(``reinterpret_cast``<``void` `*>(seg_page_start), seg_page_end - seg_page_start, PROT_WRITE);``void``* c = (``char``*)start_addr_ + file_page_start;``void``* res =` `memcpy``(``reinterpret_cast``<``void` `*>(seg_page_start), c, file_length);` `LOGD(``"[LoadSeg] %s  seg_page_start: %lx   c : %lx"``,` `strerror``(``errno``), seg_page_start, c);` `}` `// if the segment is writable, and does not end on a page boundary,``// zero-fill it until the page limit.``if` `((phdr->p_flags & PF_W) != 0 && PAGE_OFFSET(seg_file_end) > 0) {``memset``(``reinterpret_cast``<``void``*>(seg_file_end), 0, PAGE_SIZE - PAGE_OFFSET(seg_file_end));``}` `seg_file_end = PAGE_END(seg_file_end);` `// seg_file_end is now the first page address after the file``// content. If seg_end is larger, we need to zero anything``// between them. This is done by using a private anonymous``// map for all extra pages.` `if` `(seg_page_end > seg_file_end) {``size_t` `zeromap_size = seg_page_end - seg_file_end;``void``* zeromap = mmap(``reinterpret_cast``<``void``*>(seg_file_end),``zeromap_size,``PFLAGS_TO_PROT(phdr->p_flags),``MAP_FIXED\|MAP_ANONYMOUS\|MAP_PRIVATE,``-1,``0);``if` `(zeromap == MAP_FAILED) {``LOGE(``"couldn't zero fill \"%s\" gap: %s"``, name_.c_str(),` `strerror``(``errno``));``return` `false``;``}` `// 分配.bss節``prctl(PR_SET_VMA, PR_SET_VMA_ANON_NAME, zeromap, zeromap_size,` `".bss"``);``}``}` `return` `true``;``}` |
|-|-|

`FindPhdr`的具體實現如下，簡單來說就是將Phdr信息填充進`load_bias_`那片內存。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748 | `bool` `MyLoader::FindPhdr() {` `const` `ElfW(Phdr)* phdr_limit = phdr_table_ + phdr_num_;` `// If there is a PT_PHDR, use it directly.``for` `(``const` `ElfW(Phdr)* phdr = phdr_table_; phdr < phdr_limit; ++phdr) {``if` `(phdr->p_type == PT_PHDR) {``return` `CheckPhdr(load_bias_ + phdr->p_vaddr);``}``}` `// Otherwise, check the first loadable segment. If its file offset``// is 0, it starts with the ELF header, and we can trivially find the``// loaded program header from it.``for` `(``const` `ElfW(Phdr)* phdr = phdr_table_; phdr < phdr_limit; ++phdr) {``if` `(phdr->p_type == PT_LOAD) {``if` `(phdr->p_offset == 0) {``ElfW(Addr)  elf_addr = load_bias_ + phdr->p_vaddr;``const` `ElfW(Ehdr)* ehdr =` `reinterpret_cast``<``const` `ElfW(Ehdr)*>(elf_addr);``ElfW(Addr)  offset = ehdr->e_phoff;``return` `CheckPhdr(``reinterpret_cast``<ElfW(Addr)>(ehdr) + offset);``}``break``;``}``}` `LOGE(``"can't find loaded phdr for \"%s\""``, name_.c_str());``return` `false``;``}` `bool` `MyLoader::CheckPhdr(ElfW(Addr) loaded) {``const` `ElfW(Phdr)* phdr_limit = phdr_table_ + phdr_num_;``ElfW(Addr) loaded_end = loaded + (phdr_num_ *` `sizeof``(ElfW(Phdr)));``for` `(``const` `ElfW(Phdr)* phdr = phdr_table_; phdr < phdr_limit; ++phdr) {``if` `(phdr->p_type != PT_LOAD) {``continue``;``}``ElfW(Addr) seg_start = phdr->p_vaddr + load_bias_;``ElfW(Addr) seg_end = phdr->p_filesz + seg_start;``if` `(seg_start <= loaded && loaded_end <= seg_end) {``loaded_phdr_ =` `reinterpret_cast``<``const` `ElfW(Phdr)*>(loaded);``return` `true``;``}``}``LOGE(``"\"%s\" loaded phdr %p not in loadable segment"``,``name_.c_str(),` `reinterpret_cast``<``void``*>(loaded));``return` `false``;``}` |
|-|-|

### 修正so

`Load`函數最後是在對soinfo的修正，將當前so( 加載器 )修正為待加載的so。AOSP源碼中的`si_`是通過特定方法new出來的全新soinfo，而我看大多數文章都是獲取當前so作為`si_`，然後修正其中的信息。

本來是想嘗試按AOSP源碼那樣new一個soinfo看看結果有什麼不同，但最終被soinfo結構的複雜性勸退了。

修正so的第一步是要獲取當前so的soinfo對象，從[這篇文章](https://nszdhd1.github.io/2020/07/03/%E7%BD%91%E6%98%93%E4%BF%9D%E6%8A%A4%E5%88%86%E6%9E%90/#/%E7%BD%91%E6%98%93%E4%BF%9D%E6%8A%A4%E7%A0%94%E7%A9%B6)發現`find_containing_library`這個函數，似乎可以一步到位直接獲取soinfo對象。該函數位於`linker64`中，將它拉入IDA，能直接搜尋到該函數，這意味著能夠「借用」這個函數。

 ![image](https://bbs.kanxue.com/upload/attach/202406/946537_WWU84M766JKG24C.webp)

想要「借用」`linker64`裡的`find_containing_library`，需要知道`linker64`在內存的基址和`find_containing_library`的函數偏移( 相對基址的偏移 )，前者可以通過遍歷`/proc/self/maps`來取得，而後者的獲取有以下兩種思路：

1. 直接從IDA查看其偏移( `0x9AB0` )
2. 解析`linker64`的文件，自動獲取，具體實現在`Utils::get_export_func`中。

成功獲取`find_containing_library`地址後，強轉成`FunctionPtr`函數指針後即可調用，參數為當前so的地址( 同樣是遍歷maps取得的 )，最終會返回當前so的soinfo對象。

| 123456789101112131415161718192021222324252627282930313233 | `soinfo* Utils::get_soinfo(``const` `char``* so_name) {``typedef` `soinfo* (*FunctionPtr)(ElfW(Addr));` `char` `line[1024];``ElfW(Addr) linker_base = 0;``ElfW(Addr) so_addr = 0;``FILE` `*fp=``fopen``(``"/proc/self/maps"``,``"r"``);``while` `(``fgets``(line,` `sizeof``(line), fp)) {``if` `(``strstr``(line,` `"linker64"``) && !linker_base) {``char``* addr =` `strtok``(line,` `"-"``);``linker_base = strtoull(addr, NULL, 16);` `}``else` `if``(``strstr``(line, so_name) && !so_addr) {``char``* addr =` `strtok``(line,` `"-"``);``so_addr = strtoull(addr, NULL, 16);` `}` `if``(linker_base && so_addr)``break``;` `}` `ElfW(Addr) func_offset = Utils::get_export_func(``"/system/bin/linker64"``,` `"find_containing_library"``);``if``(!func_offset) {``LOGE(``"func_offset == 0? check it ---> get_soinfo"``);``return` `nullptr;``}``//    ElfW(Addr) find_containing_library_addr =  static_cast<ElfW(Addr)>(linker_base + 0x9AB0);``ElfW(Addr) find_containing_library_addr =` `static_cast``<ElfW(Addr)>(linker_base + func_offset);``FunctionPtr find_containing_library =` `reinterpret_cast``<FunctionPtr>(find_containing_library_addr);` `return` `find_containing_library(so_addr);``}` |
|-|-|

`get_export_func`的實現如下，主要依賴於elf的文件結構，可以參考下[我之前寫的文章](https://ngiokweng.github.io/2024/05/30/elf%E6%96%87%E4%BB%B6%E7%B5%90%E6%A7%8B/)，大致原理如下：

1. elf header的`e_shstrndx`是一個索引，指向了`.shstrtab`節區，而`.shstrtab`節區存儲著所有節區的名字。
2. 遍歷所有節區，找到名為`.symtab`和`.strtab`的節區( `.symtab`節每項都有一個`st_name`屬性，是`.strtab`節區的一個索引值，指向某符號名 )
3. 遍歷`.symtab`節區，對比`func_name`，匹配則返回對應的函數偏移。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162 | `ElfW(Addr) Utils::get_export_func(``char``* path,` `char``* func_name) {` `struct` `stat sb;``int` `fd = open(path, O_RDONLY);``fstat(fd, &sb);``void``* base = mmap(NULL, sb.st_size, PROT_READ \| PROT_WRITE, MAP_PRIVATE, fd, 0);` `// 讀取elf header``ElfW(Ehdr) header;``memcpy``(&(header), base,` `sizeof``(header));` `// 讀取Section header table``size_t` `size = header.e_shnum *` `sizeof``(ElfW(Shdr));``void``* tmp = mmap(nullptr, size, PROT_READ \| PROT_WRITE, MAP_PRIVATE \| MAP_ANONYMOUS, -1, 0);` `// 注: 必須要 MAP_ANONYMOUS``LOGD(``"error: %s"``,` `strerror``(``errno``));``ElfW(Shdr)* shdr_table;``memcpy``(tmp, (``void``*)((ElfW(Off))base + header.e_shoff), size);``shdr_table =` `static_cast``<ElfW(Shdr)*>(tmp);` `char``* shstrtab =` `reinterpret_cast``<``char``*>(shdr_table[header.e_shstrndx].sh_offset + (ElfW(Off))base);` `void``* symtab = nullptr;``char``* strtab = nullptr;``uint32_t symtab_size = 0;` `// 遍歷獲取.symtab和.strtab節``for` `(``size_t` `i = 0; i < header.e_shnum; ++i) {``const` `ElfW(Shdr) *shdr = &shdr_table[i];``char``* section_name = shstrtab + shdr->sh_name;``if``(!``strcmp``(section_name,` `".symtab"``)) {``//            LOGD("[test] %d: shdr->sh_name = %s", i, (shstrtab + shdr->sh_name));``symtab =` `reinterpret_cast``<``void``*>(shdr->sh_offset + (ElfW(Off))base);``symtab_size = shdr->sh_size;``}``if``(!``strcmp``(section_name,` `".strtab"``)) {``//            LOGD("[test] %d: shdr->sh_name = %s", i, (shstrtab + shdr->sh_name));``strtab =` `reinterpret_cast``<``char``*>(shdr->sh_offset + (ElfW(Off))base);``}` `if``(strtab && symtab)``break``;``}` `// 讀取 Symbol table``ElfW(Sym)* sym_table;``tmp = mmap(nullptr, symtab_size, PROT_READ \| PROT_WRITE, MAP_PRIVATE \| MAP_ANONYMOUS, -1, 0);``memcpy``(tmp, symtab, symtab_size);``sym_table =` `static_cast``<ElfW(Sym)*>(tmp);` `int` `sym_num = symtab_size /` `sizeof``(ElfW(Sym));` `// 遍歷 Symbol table``for``(``int` `i = 0; i < sym_num; i++) {``const` `ElfW(Sym) *sym = &sym_table[i];``char``* sym_name = strtab + sym->st_name;``if``(``strstr``(sym_name, func_name)) {``return` `sym->st_value;``}` `}` `return` `0;``}` |
|-|-|

成功獲取`si_`後要修改其對應屬性。在這裡我遇到一個很玄學的問題，就是一開始不知為什麼死活修改不了`si_`的屬性，一改就會報內存讀寫的錯，即使`mprotect`賦予可讀可寫權限也無用，嘗試了各種方法都無用，在這卡了我好幾天，直到某次重啟手機後就突然好了？？？

| 12345678910 | `// 使si_可以被修改``mprotect((``void``*) PAGE_START(``reinterpret_cast``<ElfW(Addr)>(si_)), 0x1000, PROT_READ \| PROT_WRITE);` `// 修正so``si_->base = load_start();``si_->size = load_size();``//        si_->set_mapped_by_caller(elf_reader.is_mapped_by_caller());``si_->load_bias = load_bias();``si_->phnum = phdr_count();``si_->phdr = loaded_phdr();` |
|-|-|

### 補充：soinfo結構( 巨TM坑 )

soinfo結構體定義在`bionic/linker/linker_soinfo.h`中。

將它copy到本地後會有很多報錯，一開始我是將那些沒有用到又報紅的直接刪掉，但後來發現這樣做會間接導致最後發生「`android linker java.lang.unsatisfiedlinkerror: no implementation found for XXX`」的錯誤( 這個錯誤我排查了很久很久，最終才發現是soinfo結構的問題，果然細節決定成敗…… )。

正確的做法是必須要保留所有的成員變量( 即使該變量用不到也要留下來占位 )，函數由於不占空間可以隨便刪掉。

## `prelink_image`

預鏈接，主要是在遍歷`.dynamic`節獲取各種動態信息並保存在修正後的soinfo中。

| 12 | `// 3. 預鏈接, 主要處理 .dynamic節``si_->prelink_image()` |
|-|-|

`prelink_image`的具體實現太長( 基本上是copy源碼的 )就不展示了，比較大的改動是在`DT_NEEDED`時手動保存對應的依賴庫，之後重定向時會用到。

| 1234567891011121314151617181920212223242526 | `bool` `soinfo::prelink_image() {``/* Extract dynamic section */``ElfW(Word) dynamic_flags = 0;``Utils::phdr_table_get_dynamic_section(phdr, phnum, load_bias, &dynamic, &dynamic_flags);` `if` `(dynamic == nullptr) {``return` `false``;``}` `else` `{``}` `for` `(ElfW(Dyn)* d = dynamic; d->d_tag != DT_NULL; ++d) {``LOGD(``"d = %p, d[0](tag) = %p d[1](val) = %p"``,``d,` `reinterpret_cast``<``void``*>(d->d_tag),` `reinterpret_cast``<``void``*>(d->d_un.d_val));``switch` `(d->d_tag) {``// ...``case` `DT_NEEDED:``// 手動保留所有依賴庫, 用於之後的重定位``myneed[needed_count] = d->d_un.d_val;``++needed_count;``break``;``// ...``}``}` `return` `true``;``}` |
|-|-|

## `link_image`

`link_image`裡處理重定向信息。

| 12 | `// 4. 正式鏈接, 在這裡處理重定位的信息``si_->link_image();` |
|-|-|

`link_image`的實現如下，`android_relocs_`的重定向我沒有處理( 嘗試處理過，但有點問題就刪了 )，好像問題不大？

之後調用`relocate`對`rela_`和`plt_rela_`的內容進行重定向。

| 123456789101112131415161718192021222324252627282930313233343536373839 | `bool` `soinfo::link_image() {``local_group_root_ =` `this``;` `if` `(android_relocs_ != nullptr) {``LOGD(``"android_relocs_ 不用處理?"``);` `}` `else` `{``LOGE(``"bad android relocation header."``);``//        return false;``}` `///*``#if defined(USE_RELA)``if` `(rela_ != nullptr) {``LOGD(``"[ relocating %s ]"``, get_realpath());``if` `(!relocate(plain_reloc_iterator(rela_, rela_count_))) {``return` `false``;``}``}``if` `(plt_rela_ != nullptr) {``LOGD(``"[ relocating %s plt ]"``, get_realpath());``if` `(!relocate(plain_reloc_iterator(plt_rela_, plt_rela_count_))) {``return` `false``;``}``}``#else``LOGE(``"TODO: !defined(USE_RELA) "``);``#endif` `LOGD(``"[ finished linking %s ]"``, get_realpath());` `// We can also turn on GNU RELRO protection if we're not linking the dynamic linker``// itself --- it can't make system calls yet, and will have to call protect_relro later.``if` `(!((flags_ & FLAG_LINKER) != 0) && !protect_relro()) {``return` `false``;``}` `return` `true``;``}` |
|-|-|

`relocate`函數的實現如下，在重定位時最需要確定的就是目標函數的真實地址。

這裡采用一種偷懶的方式，直接遍歷所有依賴庫( 之前保存在`myneed`中 )，調用`dlopen`+`dlsym`查找對應函數地址，找到的結果會保存在`sym_addr`中，後續再根據`type`來決定重定位的方式；而如果遍歷完所有依賴庫都沒有找到，則嘗試從`symtab_[sym].st_value`裡獲取。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154 | `template``<``typename` `ElfRelIteratorT>``bool` `soinfo::relocate(ElfRelIteratorT&& rel_iterator) {``for` `(``size_t` `idx = 0; rel_iterator.has_next(); ++idx) {``const` `auto` `rel = rel_iterator.next();``if` `(rel == nullptr) {``return` `false``;``}` `ElfW(Word) type = ELFW(R_TYPE)(rel->r_info);``ElfW(Word) sym = ELFW(R_SYM)(rel->r_info);` `// reloc 指向需要重定向的內容, 根據type來決定重定向成什麼``ElfW(Addr) reloc =` `static_cast``<ElfW(Addr)>(rel->r_offset + load_bias);``ElfW(Addr) sym_addr = 0;``const` `char``* sym_name = nullptr;``ElfW(Addr) addend = Utils::get_addend(rel, reloc);` `//        LOGD("Processing \"%s\" relocation at index %zd", get_realpath(), idx);``if` `(type == R_GENERIC_NONE) {``continue``;``}` `const` `ElfW(Sym)* s = nullptr;``soinfo* lsi = nullptr;` `if` `(sym != 0) {` `sym_name = get_string(symtab_[sym].st_name);``LOGD(``"sym = %lx   sym_name: %s   st_value: %lx"``, sym, sym_name, symtab_[sym].st_value);` `for``(``int` `s = 0; s < needed_count; s++) {``void``* handle = dlopen(get_string(myneed[s]),RTLD_NOW);``sym_addr =` `reinterpret_cast``<Elf64_Addr>(dlsym(handle, sym_name));``if``(sym_addr)` `break``;` `}` `if``(!sym_addr) {``if``(symtab_[sym].st_value != 0) {``sym_addr = load_bias + symtab_[sym].st_value;``}``else` `{``LOGE(``"%s find addr fail"``, sym_name);``}` `}``else` `{``LOGD(``"%s find addr success : %lx"``, sym_name, sym_addr);``}``}` `LOGD(``"reloc addr: %x"``, (reloc - base));``LOGD(``"type: %x"``, type);``switch` `(type) {``case` `R_GENERIC_JUMP_SLOT:``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = (sym_addr + addend);``break``;``case` `R_GENERIC_GLOB_DAT:``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = (sym_addr + addend);``break``;``case` `R_GENERIC_RELATIVE:``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = (load_bias + addend);``break``;``case` `R_GENERIC_IRELATIVE:``{` `ElfW(Addr) ifunc_addr = Utils::call_ifunc_resolver(load_bias + addend);``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = ifunc_addr;``}``break``;` `#if defined(__aarch64__)``case` `R_AARCH64_ABS64:``LOGD(``"R_AARCH64_ABS64  %lx    addend: %lx"``, sym_addr + addend, addend);``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = sym_addr + addend;``break``;``case` `R_AARCH64_ABS32:``{``const` `ElfW(Addr) min_value =` `static_cast``<ElfW(Addr)>(INT32_MIN);``const` `ElfW(Addr) max_value =` `static_cast``<ElfW(Addr)>(UINT32_MAX);``if` `((min_value <= (sym_addr + addend)) &&``((sym_addr + addend) <= max_value)) {``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = sym_addr + addend;``}` `else` `{``LOGE(``"0x%016llx out of range 0x%016llx to 0x%016llx"``,``sym_addr + addend, min_value, max_value);``return` `false``;``}``}``break``;``case` `R_AARCH64_ABS16:``{``const` `ElfW(Addr) min_value =` `static_cast``<ElfW(Addr)>(INT16_MIN);``const` `ElfW(Addr) max_value =` `static_cast``<ElfW(Addr)>(UINT16_MAX);``if` `((min_value <= (sym_addr + addend)) &&``((sym_addr + addend) <= max_value)) {``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = (sym_addr + addend);``}` `else` `{``LOGE(``"0x%016llx out of range 0x%016llx to 0x%016llx"``,``sym_addr + addend, min_value, max_value);``return` `false``;``}``}``break``;``case` `R_AARCH64_PREL64:``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = sym_addr + addend - rel->r_offset;``break``;``case` `R_AARCH64_PREL32:``{``const` `ElfW(Addr) min_value =` `static_cast``<ElfW(Addr)>(INT32_MIN);``const` `ElfW(Addr) max_value =` `static_cast``<ElfW(Addr)>(UINT32_MAX);``if` `((min_value <= (sym_addr + addend - rel->r_offset)) &&``((sym_addr + addend - rel->r_offset) <= max_value)) {``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = sym_addr + addend - rel->r_offset;``}` `else` `{``LOGE(``"0x%016llx out of range 0x%016llx to 0x%016llx"``,``sym_addr + addend - rel->r_offset, min_value, max_value);``return` `false``;``}``}``break``;``case` `R_AARCH64_PREL16:``{``const` `ElfW(Addr) min_value =` `static_cast``<ElfW(Addr)>(INT16_MIN);``const` `ElfW(Addr) max_value =` `static_cast``<ElfW(Addr)>(UINT16_MAX);``if` `((min_value <= (sym_addr + addend - rel->r_offset)) &&``((sym_addr + addend - rel->r_offset) <= max_value)) {``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = sym_addr + addend - rel->r_offset;``}` `else` `{``LOGE(``"0x%016llx out of range 0x%016llx to 0x%016llx"``,``sym_addr + addend - rel->r_offset, min_value, max_value);``return` `false``;``}``}``break``;` `case` `R_AARCH64_COPY:``LOGE(``"%s R_AARCH64_COPY relocations are not supported"``, get_realpath());``return` `false``;``case` `R_AARCH64_TLS_TPREL64:``LOGD(``"RELO TLS_TPREL64 *** %16llx <- %16llx - %16llx\n"``,``reloc, (sym_addr + addend), rel->r_offset);``break``;``case` `R_AARCH64_TLS_DTPREL32:``LOGD(``"RELO TLS_DTPREL32 *** %16llx <- %16llx - %16llx\n"``,``reloc, (sym_addr + addend), rel->r_offset);``break``;``#endif``default``:``LOGE(``"unknown reloc type %d @ %p (%zu)  sym_name: %s"``, type, rel, idx, sym_name);``return` `false``;``}``//    */``}``return` `true``;``}` |
|-|-|

## `call_constructors`

調用soinfo的構建函數：`.init`和`.init_array`內所有函數

| 123456 | `// 使被加載的so有執行權限, 否則在調用.init_array時會報錯``mprotect(``reinterpret_cast``<``void` `*>(load_bias_), sb.st_size, PROT_READ \| PROT_WRITE \| PROT_EXEC);``//...` `// 5. 調用.init和.init_array``si_->call_constructors();` |
|-|-|

原版Linker在調用`.init`和`.init_array`時傳入的是`0, nullptr, nullptr`，我這裡與其保持一致。

| 12345678910111213141516 | `void` `soinfo::call_constructors() {``// 對於so文件來說, 由於沒有_start函數``// 因此init_func_和init_array_都無法傳參, 只能是默認值` `if``(init_func_) {``LOGD(``"init func: %p"``, init_func_);``init_func_(0, nullptr, nullptr);``}``if``(init_array_) {``for``(``int` `i = 0; i < init_array_count_; i++) {``if``(!init_array_[i])``continue``;``init_array_[i](0, nullptr, nullptr);``}``}` `}` |
|-|-|

## 完整代碼

項目地址：<https://github.com/ngiokweng/ng1ok-linker>

# 測試

隨便寫一個so作為待加載的so( 名為`libdemo1.so` )，內容如下，將它push到`/data/local/tmp`。

| 12345678910111213141516171819202122232425262728293031323334353637 | `#include <jni.h>``#include <string>``#include <android/log.h>` `#define  TAG    "nglog"` `#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,TAG,__VA_ARGS__)``#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, TAG, __VA_ARGS__)``#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR,TAG,__VA_ARGS__)` `extern` `"C"` `JNIEXPORT jstring JNICALL``Java_ng1ok_demo1_NativeLib_stringFromJNI(``JNIEnv* env,``jobject` `/* this */``) {``std::string hello =` `"Hello from C++"``;``return` `env->NewStringUTF(hello.c_str());``}` `extern` `"C"``JNIEXPORT jstring JNICALL``Java_ng1ok_linker_MainActivity_demo1Func(JNIEnv *env, jobject thiz) {``LOGD(``"Java_ng1ok_linker_MainActivity_demo1Func calleeeeeeeddddddddd"``);``std::string str =` `"Java_ng1ok_linker_MainActivity_demo1Func"``;` `return` `env->NewStringUTF(str.c_str());``}` `__attribute__((constructor()))``void` `sayHello(){``LOGD(``"[from libdemo1.so .init_array] Hello~~~"``);``}` `extern` `"C"` `{``void` `_init(``void``){``LOGD(``"[from libdemo1.so .init] _init~~~~"``);``}``}` |
|-|-|

Demo的用例如下，實例化`MyLoader`，調用`run`函數加載指定路徑的so。

 ![image](https://bbs.kanxue.com/upload/attach/202406/946537_WVFSPB37WEBBZ8W.webp)

Java層的`onCreate`如下，在`test`之後調用待加載so裡的`demo1Func`函數。

 ![image](https://bbs.kanxue.com/upload/attach/202406/946537_N7Q8MDC9KX325KE.webp)

輸出如下，大功告成~

 ![image](https://bbs.kanxue.com/upload/attach/202406/946537_MR6CWDCH246FMQJ.webp)

# 結語

前前後後弄了兩、三周的時間，最終總算是弄好了這一個小Demo。自知該Demo仍有很多不足之處( 如無法捕獲try…catch )，而且只經過簡單的測試，定然存在諸多的BUG，歡迎各位大佬的指正！！有任何也問題歡迎評論，或者私聊我/找我聊聊天都可以！！！

---

# 回复

## 回复 by 逆天而行 (#2)

*2024-6-28 17:32*

感谢！楼主我也最近想实现这个linker加固，看了很多文章，r0ysue的那个demo我可以运行！给你大大的点个赞！走在我前面

## 回复 by ngiokweng (#3)

*2024-6-28 17:43*

>
> [逆天而行](https://bbs.kanxue.com/user-957038.htm)
>
>  感谢！楼主我也最近想实现这个linker加固，看了很多文章，r0ysue的那个demo我可以运行！给你大大的点个赞！走在我前面
>
>

對你有幫助就好![image](https://bbs.kanxue.com/view/img/face/13.gif) 雖然r0ysue大佬那個demo我跑不起來(可能是環境問題?), 但真的很有參考價值![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 哆啦噩梦 (#4)

*2024-6-28 17:58*

都在自定义linker...越来越不好玩了

## 回复 by mudebug (#5)

*2024-6-29 02:06*

666

## 回复 by 你瞒我瞒 (#6)

*2024-7-3 10:39*

TQL

## 回复 by 珍惜Any (#7)

*2024-7-3 16:16*

我有个问题，你虽然自定义linker加载了，我遍历系统的linker加载文件列表能找到么？能找到就可以dump出来。

## 回复 by ngiokweng (#8)

*2024-7-3 19:20*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  我有个问题，你虽然自定义linker加载了，我遍历系统的linker加载文件列表能找到么？能找到就可以dump出来。
>
>

遍歷系統的linker加載文件列表是指linker_main.cpp裡的solist嗎? 如果是的話應該能找到, 因為有一步是將當前so(加載器so)修正為目標so, 就是不知道修正的效果如何。

## 回复 by 珍惜Any (#9)

*2024-7-4 11:47*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  遍歷系統的linker加載文件列表是指linker_main.cpp裡的solist嗎? 如果是的話應該能找到, 因為有一步是將當前so(加載器so)修正為目標so, 就是不知道修正的效果如何。
>
>

那就是还可以dump出来的，现在一般so的脱壳机都是直接遍历这玩意，从开始地址-结束地址dump出来

## 回复 by ngiokweng (#10)

*2024-7-4 14:04*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  那就是还可以dump出来的，现在一般so的脱壳机都是直接遍历这玩意，从开始地址-结束地址dump出来
>
>

嗯, 畢竟我大部分代碼都是抄源碼的, 沒有做魔改, 以後看看有沒有機會研究下對抗的方法![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by zx_994305 (#11)

*2024-7-5 11:14*

好文当赏

## 回复 by xxRea (#12)

*2024-7-11 18:09*

好文当赏

## 回复 by pureGavin (#13)

*2024-7-11 19:04*

感谢分享，不过怎么都是繁体字？楼主你很机车哦 ![image](https://bbs.kanxue.com/view/img/face/86.gif)

## 回复 by ngiokweng (#14)

*2024-7-12 09:59*

>
> [pureGavin](https://bbs.kanxue.com/user-777502.htm)
>
>  感谢分享，不过怎么都是繁体字？楼主你很机车哦 [em_86]
>
>

我只會打繁體啊, 而且我人很nice一點都不機車![image](https://bbs.kanxue.com/view/img/face/86.gif)

## 回复 by 7lsu (#15)

*2024-7-30 09:56*

谢谢楼主分享，学到很多~

## 回复 by ngiokweng (#16)

*2024-7-30 15:24*

>
> [7lsu](https://bbs.kanxue.com/user-817910.htm)
>
>  谢谢楼主分享，学到很多~
>
>

![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by mb_vjpiriil (#17)

*2024-7-31 11:57*

tql

## 回复 by 恋一世的爱 (#18)

*2024-8-1 23:04*

我有个问题哈，就是如果改包形式注入的so，在maps下都会留下痕迹吧，用这个技术，是不是也只能做到把第二个so的痕迹抹除掉，但第一个so也有痕迹，本身第一个so怎么抹除呢

## 回复 by 养只猫不好么 (#19)

*2024-8-2 10:34*

感谢分享

## 回复 by ngiokweng (#20)

*2024-8-2 12:06*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  恋一世的爱](https://bbs.kanxue.com/user-825246.htm)
>
>  我有个问题哈，就是如果改包形式注入的so，在maps下都会留下痕迹吧，用这个技术，是不是也只能做到把第二个so的痕迹抹除掉，但第一个so也有痕迹，本身第一个so怎么抹除呢
>
>

我看過一個方法是利用memfd_create創建一個匿名共享內存, 然後用dlopen來加載, 通過這個方式來加載第一個so或許可以做到。

## 回复 by 恋一世的爱 (#21)

*2024-8-4 23:35*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  我看過一個方法是利用memfd_create創建一個匿名共享內存, 然後用dlopen來加載, 通過這個方式來加載第一個so或許可以做到。
>
>

但是你要怎么清除第一个so在maps里的信息呢，我是改包（反编译回编译），不是改系统哈

## 回复 by enmmmm (#22)

*2025-1-31 22:09*

看不懂繁体字怎么办

## 回复 by exit0 (#23)

*2025-2-2 02:36*

萌新的我 最近也是刚接触到二进制 如何只是为了注入 放到内存 修复重定向 就能跑起来了 ...

## 回复 by ngiokweng (#24)

*2025-2-5 12:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  exit0](https://bbs.kanxue.com/user-887576.htm)
>
>  萌新的我 最近也是刚接触到二进制 如何只是为了注入 放到内存 修复重定向 就能跑起来了 ...
>
>

什麼意思？？

## 回复 by 东方玻璃 (#25)

*2025-2-28 23:09*

看样子网上基本都是使用soinfo,请问师傅能直接加载so到内存手动链接和重定位从而调用so吗

## 回复 by ngiokweng (#26)

*2025-2-28 23:48*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  看样子网上基本都是使用soinfo,请问师傅能直接加载so到内存手动链接和重定位从而调用so吗
>
>

直接加載so到內存是指？文中實現的linker就是從本地將so加載到內存, 然後手動執行prelink, reloc等操作

## 回复 by 东方玻璃 (#27)

*2025-3-1 00:05*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  直接加載so到內存是指？文中實現的linker就是從本地將so加載到內存, 然後手動執行prelink, reloc等操作
>
>

就是执行其他操作，但不利用soinfo，能这样加载so调用吗

## 回复 by ngiokweng (#28)

*2025-3-1 10:55*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  就是执行其他操作，但不利用soinfo，能这样加载so调用吗
>
>

應該不行吧

## 回复 by xianyuuuan (#29)

*2025-3-14 16:01*

楼主你好 这几天在复现il2cpp游戏逆向，参考的一篇文章也是繁体，今天有幸刷到了您的文章，准备认真学习，不知道哪篇加固逆向的文章是不是您的！写的非常详细，受益匪浅orz![image](https://bbs.kanxue.com/view/img/face/038.gif)

## 回复 by ngiokweng (#30)

*2025-3-14 19:19*

>
> [xianyuuuan](https://bbs.kanxue.com/user-1002959.htm)
>
>  楼主你好 这几天在复现il2cpp游戏逆向，参考的一篇文章也是繁体，今天有幸刷到了您的文章，准备认真学习，不知道哪篇加固逆向的文章是不是您的！写的非常详细，受益匪浅orz
>
>

哪篇文章![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by xianyuuuan (#31)

*2025-3-16 17:35*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  哪篇文章[em_065]
>
>

![image](https://bbs.kanxue.com/view/img/face/020.gif)某盾那篇

## 回复 by ngiokweng (#32)

*2025-3-16 18:43*

>
> [xianyuuuan](https://bbs.kanxue.com/user-1002959.htm)
>
>  [em_020]某盾那篇
>
>

應該是的![image](https://bbs.kanxue.com/view/img/face/056.gif)

## 回复 by mb_wpnapfpn (#33)

*2025-5-21 20:39*

>
> [xianyuuuan](https://bbs.kanxue.com/user-1002959.htm)
>
>  [em_020]某盾那篇
>
>

大佬，您那篇某盾，小弟实在想参考学习，能不能私发一下

## 回复 by Yangser (#34)

*2025-6-5 15:58*

请问一下大佬，我最近在做so的脱壳，我有两个疑惑
1.为什么最后要修复soinfo呢，主so已经被loader加载到内存里并且完成了重定位了，按理说不是已经可以正常运行了吗
2.可不可以在直接把loader加载完毕主so之后，把loader的soinfo断链，这样可以预防攻击者通过拿到soinfo的首地址根据偏移直接dump内存中的so

## 回复 by ngiokweng (#35)

*2025-6-9 20:14*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  请问一下大佬，我最近在做so的脱壳，我有两个疑惑
> 1.为什么最后要修复soinfo呢，主so已经被loader加载到内存里并且完成了重定位了，按理说不是已经可以正常运行了吗
> 2.可不可以在直接把l ...
>
>

個人愚見，僅供參考:
1. 為了讓子so存在於linker的soinfo鏈表。
2. 在我的實現中, loader加載後被修正成了子so，或許你可以試試看通過操作soinfo鏈表來插入子so，這時再把loader的soinfo斷鏈才有意義。

## 回复 by Yangser (#36)

*2025-6-12 13:24*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>
>
>
>
>
>
>  Yangser
>
>
>
>  请问一下大佬，我最近在做so的脱壳，我有两个疑惑
> 1.为什么最后要修复soinfo呢，主so已经被loader加载到内存 ...
>
>

好的谢谢大佬指点，看了您的文章我也自己写了个loader
https://github.com/SoyBeanMilkx/soLoader

## 回复 by ngiokweng (#37)

*2025-6-12 19:55*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  好的谢谢大佬指点，看了您的文章我也自己写了个loader
> https://github.com/SoyBeanMilkx/soLoader
>
>

![image](https://bbs.kanxue.com/view/img/face/092.gif)![image](https://bbs.kanxue.com/view/img/face/092.gif)

## 回复 by 灬哈密瓜 (#38)

*2025-12-1 14:53*

看了一下. 使用find_containing_library方式替换soinfo. 感觉兼容性不怎么好. 需要保证soinfo值要全部对齐. (如果rom二次修改. 就会崩溃![image](https://bbs.kanxue.com/view/img/face/065.gif))

## 回复 by ngiokweng (#39)

*2025-12-2 09:24*

>
> [灬哈密瓜](https://bbs.kanxue.com/user-593544.htm)
>
>  看了一下. 使用find_containing_library方式替换soinfo. 感觉兼容性不怎么好. 需要保证soinfo值要全部对齐. (如果rom二次修改. 就会崩溃[em_065])
>
>

是的, 兼容性是個難題![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by fei3ei (#40)

*2025-12-2 09:34*

>
> [灬哈密瓜](https://bbs.kanxue.com/user-593544.htm)
>
>  看了一下. 使用find_containing_library方式替换soinfo. 感觉兼容性不怎么好. 需要保证soinfo值要全部对齐. (如果rom二次修改. 就会崩溃[em_065])
>
>

这种方法确实，还有什么别的思路吗？

## 回复 by 灬哈密瓜 (#41)

*2025-12-2 14:33*

>
> [fei3ei](https://bbs.kanxue.com/user-977795.htm)
>
>  这种方法确实，还有什么别的思路吗？
>
>

目前没有想到什么好的思路. 看到的方案最多就是替换soinfo
