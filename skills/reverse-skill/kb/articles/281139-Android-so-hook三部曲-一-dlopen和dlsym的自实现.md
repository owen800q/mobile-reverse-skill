---
title: '[原创]Android so hook三部曲(一)：dlopen和dlsym的自实现'
url: https://bbs.kanxue.com/thread-281139.htm
tid: 281139
author: Tom-gogo
date: '2024-03-29'
tags: [Android安全, 原创, 逆向分析, 脱壳反混淆, HOOK注入]
crawled_at: '2026-07-31T14:28:59+08:00'
replies: 15
---

# 自实现目的

对so hook有刚需的人应该都知道，hook的第一步就是要拿到被hook方法的地址，而想要获取方法地址就避不开dlopen()和dlsym()这两个好基友函数，但Android为了避免伤及友军便在Android 7.0以上版本对这两个函数的使用做了限制，以至于在获取很多未公开库方法时会获取失败，目的也是为了提高安全性和稳定性。出发点是好的，但我们有刚需，我们就得造它。

# 浅谈思路

## dlopen

目的就是将目标so文件模拟加载到内存中，大致分为以下几个步骤：

1. 打开文件，读取头表段表
2. 申请内存，映射LOAD段
3. 定位、解析动态段，获取有用信息
4. 重定位、初始化

## dlSym

dlsym则模拟源码实现方式

1. 通过hash判断目标字符是否存在
2. 遍历hash表获取目标位置

# 具体实现

## dlopen

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253 | `/``/``初始化函数``typedef void``*``(``*``PFN_INIT)();` `Elf64_Hash g_hash` `=` `{``0``};``char``*` `pStrTable` `=` `NULL;``Elf64_Sym``*` `pSymTable` `=` `NULL;` `char``*` `bufNedded[``256``]` `=` `{``0``};``size_t nNumOfNeede` `=` `0``;` `Elf64_Rela``*` `pRelaDyn` `=` `NULL;``size_t nNumOfRela``=``0``;``Elf64_Rela``*` `pRelaPlt` `=` `NULL;``size_t nNumOfRelaPlt` `=` `0``;` `PFN_INIT``*` `bufInis` `=` `NULL;``size_t nNumOfInis` `=` `0``;` `/``/``重定位函数``__attribute__((noinline))``void Relocate(uint8_t``*` `pBase, Elf64_Rela``*` `pRel,` `size_t nNumOfRels,Elf64_Sym``*` `pSym,void``*``hSos[],``size_t nNumOfSos,``const char``*` `pStr)``{``/``/``解析重定位表``for` `(size_t i` `=` `0``; i < nNumOfRels; i``+``+``)``{``uint32_t nSym` `=` `ELF64_R_SYM(pRel[i].r_info);` `/``/``索引``uint32_t nType` `=` `ELF64_R_TYPE(pRel[i].r_info);` `/``/``类型` `/``/``根据符号获取地址``void``*` `nAddr` `=` `NULL;``if``(pSym[nSym].st_value !``=` `0``)``{``/``/``导出符号，自己模块内部的符号``nAddr` `=` `pBase``+``pSym[nSym].st_value;``}``else``{``/``/``导入符号，其他模块符号``for``(size_t i``=``0``; i<nNumOfSos;i``+``+``)``{``nAddr` `=` `dlsym(hSos[i],pStr``+``pSym[nSym].st_name);``if``(nAddr!``=``NULL)``{``break``;` `/``/``找到了``}``}``}` `switch (nType)``{``case R_AARCH64_RELATIVE:` `/``/``相对``*``(uint64_t``*``)(pBase``+``pRel[i].r_offset)` `=` `(uint64_t)(pBase``+``pRel[i].r_addend);``break``;``case R_AARCH64_GLOB_DAT:` `/``/``全局偏移量``*``(uint64_t``*``)(pBase``+``pRel[i].r_offset)` `=` `(uint64_t)nAddr;``break``;` `case R_AARCH64_JUMP_SLOT:` `/``/``跳转槽``*``(uint64_t``*``)(pBase``+``pRel[i].r_offset)` `=` `(uint64_t)nAddr;``break``;``default:``break``;``}``}``}` `__attribute__((noinline))``void``*` `MyDlSym(uint8_t``*` `pBase, const char``*` `szName)``{``/``/``判断要查找的字符是否存在于此so内``uint32_t` `hash` `=`  `gnu_hash(szName);` `/``/``计算``hash``uint32_t h2` `=` `hash``>>g_hash.shift2;` `uint32_t bloom_mask_bits` `=` `64``;``uint32_t word_num` `=` `(``hash` `/` `bloom_mask_bits)& g_hash.maskswords;``uint64_t bloom_word` `=` `g_hash.gnu_bloom_filter_[word_num];` `if``( (``1``&(bloom_word>>(``hash``%``bloom_mask_bits)) & (bloom_word>>(h2``%``bloom_mask_bits)))` `=``=` `0` `)``{``/``/``不在模块内``return` `NULL;``}` `uint32_t n` `=` `g_hash.gnu_bucket_[``hash` `%` `g_hash.nbucket];` `do``{``Elf64_Sym``*` `s` `=` `pSymTable``+``n;``if``( ((g_hash.gnu_chain_[n] ^` `hash``) >>` `1``)` `=``=` `0` `&&``strcmp(pStrTable``+``s``-``>st_name, szName)``=``=``0` `)``{``/``/``找到了，返回地址``return` `pBase``+``s``-``>st_value;``}` `}` `while` `((g_hash.gnu_chain_[n``+``+``]&``1``)` `=``=` `0``);``}` `void``*` `MyDlopen(const char``*` `szName)``{``/``/``读取文件、文件头和段表``FILE``*` `file` `=` `fopen(szName,``"rb"``);``if``(``file` `=``=` `NULL)``{``printf(``"open file error!\n"``);``return` `0``;``}` `Elf64_Ehdr hdr` `=` `{``0``};` `/``/``elf hander``if``(fread(&hdr,` `1``, sizeof(hdr),` `file``) !``=` `sizeof(hdr))` `{``printf(``"read Ehdr error!\n"``);``return` `0``;``}` `size_t nSizeOfPhdrs` `=` `hdr.e_phentsize``*``hdr.e_phnum;` `/``/``段表大小``Elf64_Phdr``*` `phdrs` `=` `(Elf64_Phdr``*``)malloc(nSizeOfPhdrs);``if``( fread(phdrs,` `1``, nSizeOfPhdrs,``file``) !``=` `nSizeOfPhdrs)``{``printf(``"read phdr error!\n"``);``return` `0``;``}` `/``/``fclose(``file``);` `/``/``申请内存、映射` `size_t nLoadSize` `=` `0``;``for``(``int` `i``=``hdr.e_phnum``-``1``;i>``=``0``;i``-``-``)``{``if``(phdrs[i].p_type` `=``=` `PT_LOAD)``{``nLoadSize` `=` `((phdrs[i].p_vaddr``+``phdrs[i].p_memsz``+``PAGE_SIZE``-``1``)``/``PAGE_SIZE)``*``PAGE_SIZE;` `/``/``需要申请的内存大小``break``;``}``}` `uint8_t``*` `pBase` `=` `mmap64(NULL, nLoadSize, PROT_EXEC\|PROT_READ\|PROT_WRITE, MAP_PRIVATE\|MAP_ANONYMOUS,` `-``1``,` `0``);` `/``/``申请空间``if``(pBase` `=``=` `MAP_FAILED)``{``printf(``"mmap64 error: %s\n"``,strerror(errno));``return` `0``;``}`  `for``(size_t i``=``0``;i<hdr.e_phnum;i``+``+``)``{``if``(phdrs[i].p_type` `=``=` `PT_LOAD)``{``fseek(``file``, phdrs[i].p_offset,SEEK_SET);``fread(pBase``+``phdrs[i].p_vaddr,` `1` `, phdrs[i].p_filesz,``file``);` `/``/``读取文件到内存``}``}` `free(phdrs);` `/``/` `定位动态段``phdrs` `=` `(Elf64_Phdr``*``)(pBase``+``hdr.e_phoff);``int` `nDyncIdx` `=` `0``;` `/``/``动态段索引``Elf64_Dyn``*` `pDyns` `=` `NULL;``size_t nNumofDyns` `=` `0``;` `/``/``动态段元素个数` `for``(size_t i``=``0``;i<hdr.e_phnum;i``+``+``)``{``if``(phdrs[i].p_type` `=``=` `PT_DYNAMIC)``{``nDyncIdx` `=` `i;``pDyns` `=` `(Elf64_Dyn``*``)(pBase``+``phdrs[i].p_vaddr);``nNumofDyns` `=` `phdrs[i].p_filesz``/``sizeof(Elf64_Dyn);``break``;``}``}` `/``/``解析动态段``while``(pDyns``-``>d_tag!``=` `DT_NULL)``{``switch(pDyns``-``>d_tag)``{``case DT_STRTAB:` `/``/``字符串段``pStrTable` `=` `(char``*``)(pBase``+``pDyns``-``>d_un.d_ptr);` `/``/``模块基址``+``字符串表偏移``break``;` `case DT_SYMTAB:` `/``/``符号表``pSymTable` `=` `(Elf64_Sym``*``)(pBase``+``pDyns``-``>d_un.d_ptr);``break``;` `case DT_NEEDED:` `/``/``elf文件依赖项``bufNedded[nNumOfNeede``+``+``]` `=` `pDyns``-``>d_un.d_ptr;` `/``/``str``表还没解析，先拿偏移``break``;` `case DT_RELA:` `/``/``重定位表``pRelaDyn` `=` `(Elf64_Rela``*``)(pBase``+``pDyns``-``>d_un.d_ptr);``break``;``case DT_RELASZ:``nNumOfRela` `=` `pDyns``-``>d_un.d_val``/``sizeof(Elf64_Rela);``break``;``case DT_JMPREL:` `/``/``plt表``pRelaPlt` `=` `(Elf64_Rela``*``)(pBase``+``pDyns``-``>d_un.d_ptr);``break``;``case DT_PLTRELSZ:``nNumOfRelaPlt` `=` `pDyns``-``>d_un.d_val``/``sizeof(Elf64_Rela);``break``;` `case DT_GNU_HASH:` `/``/``hash``表``{``uint8_t``*` `pHashTable` `=` `pBase``+``pDyns``-``>d_un.d_ptr;``g_hash.nbucket` `=` `((uint32_t``*``)pHashTable)[``0``];``g_hash.symindex` `=` `((uint32_t``*``)pHashTable)[``1``];``g_hash.maskswords` `=` `((uint32_t``*``)pHashTable)[``2``];``g_hash.shift2` `=` `((uint32_t``*``)pHashTable)[``3``];``g_hash.gnu_bloom_filter_` `=` `(uint64_t``*``)(pHashTable``+``16``);``g_hash.gnu_bucket_` `=` `(uint32_t``*``)(g_hash.gnu_bloom_filter_``+``g_hash.maskswords);``g_hash.gnu_chain_` `=` `g_hash.gnu_bucket_``+``g_hash.nbucket``-``g_hash .symindex;` `-``-``g_hash.maskswords;``break``;``}` `case DT_INIT_ARRAY:` `/``/``初始化``bufInis` `=` `(PFN_INIT``*``)(pBase``+``pDyns``-``>d_un.d_ptr);``break``;``case DT_INIT_ARRAYSZ:``nNumOfInis` `=` `pDyns``-``>d_un.d_val``/``sizeof(void``*``);``break``;` `default:``break``;``}` `pDyns``+``+``;``}` `/``/``加载模块，此so需要依赖的elf，方便查找导入符号``void``*``*` `hSos` `=` `malloc(sizeof(void``*``)``*``nNumOfNeede);``for``(size_t i``=``0``;i<nNumOfNeede;i``+``+``)``{``bufNedded[i]` `=` `(uint64_t)bufNedded[i]``+``pStrTable;` `/``/``字符串表已加载，偏移加字符串表基址为目标字符串地址``hSos[i]` `=` `dlopen(bufNedded[i], RTLD_NOW);``}`  `/``/``重定位``Relocate(pBase, pRelaDyn, nNumOfRela,pSymTable,hSos,nNumOfNeede,pStrTable);``Relocate(pBase, pRelaPlt,nNumOfRelaPlt,pSymTable,hSos,nNumOfNeede,pStrTable);`  `/``/``调用初始化函数``for``(size_t i` `=` `0``;i<nNumOfInis;i``+``+``)``{``bufInis[i]();``}` `return` `pBase;``}` |
|-|-|

## dlsym

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253 | `typedef struct elf64_hash{``uint32_t nbucket;``uint32_t symindex;``uint32_t maskswords;``uint32_t shift2;``uint64_t``*` `gnu_bloom_filter_;``uint32_t``*` `gnu_bucket_;``uint32_t``*` `gnu_chain_;``}Elf64_Hash;` `/``/``hash``值计算``__attribute__((noinline))``uint32_t gnu_hash(const char``*` `name_)``{``uint32_t h``=``5381``;``const uint8_t``*` `name` `=` `(const uint8_t``*``)(name_);``while``(``*``name !``=` `0``){``h``+``=``(h<<``5``)``+``*``name``+``+``;``}``return` `h;``}` `__attribute__((noinline))``void``*` `MyDlSym(uint8_t``*` `pBase, const char``*` `szName)``{``/``/``判断要查找的字符是否存在于此so内``uint32_t` `hash` `=`  `gnu_hash(szName);` `/``/``计算``hash``uint32_t h2` `=` `hash``>>g_hash.shift2;` `uint32_t bloom_mask_bits` `=` `64``;``uint32_t word_num` `=` `(``hash` `/` `bloom_mask_bits)& g_hash.maskswords;``uint64_t bloom_word` `=` `g_hash.gnu_bloom_filter_[word_num];` `if``( (``1``&(bloom_word>>(``hash``%``bloom_mask_bits)) & (bloom_word>>(h2``%``bloom_mask_bits)))` `=``=` `0` `)``{``/``/``不在模块内``return` `NULL;``}` `uint32_t n` `=` `g_hash.gnu_bucket_[``hash` `%` `g_hash.nbucket];` `/``/``n为该桶对应的链数组的下标` `do``{``Elf64_Sym``*` `s` `=` `pSymTable``+``n;``if``( ((g_hash.gnu_chain_[n] ^` `hash``) >>` `1``)` `=``=` `0` `&&``strcmp(pStrTable``+``s``-``>st_name, szName)``=``=``0` `)``{``/``/``找到了，返回地址``return` `pBase``+``s``-``>st_value;``}` `}` `while` `((g_hash.gnu_chain_[n``+``+``]&``1``)` `=``=` `0``);``}` |
|-|-|

---

# 回复

## 回复 by huangjw (#2)

*2024-3-29 21:37*

可以哦，虽然有点基础

## 回复 by Tom-gogo (#3)

*2024-3-29 22:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  huangjw](https://bbs.kanxue.com/user-323039.htm)
>
>  可以哦，虽然有点基础
>
>

初学者，而且是第一次发帖，见谅

## 回复 by kinglinzi (#4)

*2024-4-4 09:00*

谢谢，学习了

## 回复 by koflfy (#5)

*2024-4-6 18:31*

mark，有完整的内存加载模块的源码吗？

## 回复 by 秋狝 (#6)

*2024-4-7 09:23*

感谢分享

## 回复 by dreameriii (#7)

*2024-4-7 09:59*

![image](https://bbs.kanxue.com/view/img/face/63.gif) 麻烦 标题能不能修正下 dlopen 不是 dlopne，看到时我一直在想open这个单词该怎么拼![image](https://bbs.kanxue.com/view/img/face/78.gif)

## 回复 by Tom-gogo (#8)

*2024-4-8 15:43*

>
> [dreameriii](https://bbs.kanxue.com/user-719252.htm)
>
>  [em_63] 麻烦 标题能不能修正下 dlopen 不是 dlopne，看到时我一直在想open这个单词该怎么拼[em_78]
>
>

![image](https://bbs.kanxue.com/view/img/face/78.gif)感谢指正

## 回复 by time.time (#9)

*2024-4-8 18:20*

期待剩下两部![image](https://bbs.kanxue.com/view/img/face/86.gif)

## 回复 by Tom-gogo (#10)

*2024-4-8 20:31*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  time.time](https://bbs.kanxue.com/user-967913.htm)
>
>  期待剩下两部[em_86]
>
>

![image](https://bbs.kanxue.com/view/img/face/86.gif)最近在找工作，等稳定下来就更新

## 回复 by mb_kbkqyusp (#11)

*2024-4-13 11:54*

这个代码看着好熟悉，不会是老王的吧![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by Tom-gogo (#12)

*2024-4-13 22:41*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_kbkqyusp](https://bbs.kanxue.com/user-934671.htm)
>
>  这个代码看着好熟悉，不会是老王的吧[em_13]
>
>

kr？

## 回复 by Black貓①呺 (#13)

*2024-4-24 10:38*

感谢分享，刚好正在学ELF文件格式

## 回复 by mb_hsxnkqcc (#14)

*2024-12-9 17:06*

长知识了，感谢分享，期待接下来的文章。

## 回复 by 刘宽森 (#15)

*2024-12-17 18:00*

老铁,赶紧更新

## 回复 by mb_ldbucrik (#16)

*2025-1-7 12:38*

期待大佬更新
