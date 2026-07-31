---
title: '[原创] 自定义Linker与SO加固技术'
url: https://bbs.kanxue.com/thread-287254.htm
tid: 287254
author: Yangser
date: '2025-06-15'
tags: [Android安全, 原创, 基础理论, 混淆加固, 其他]
crawled_at: '2026-07-31T15:50:13+08:00'
replies: 152
---

# 自定义Linker与SO加固技术

## 0x01 前言

在研究360加固方案时，我发现其采用了一种独特的保护机制：在主SO文件内部嵌套了另一个SO文件，相当于为主SO添加了一层保护壳。这种技术实现引起了我的兴趣，经过深入研究，整理出本文，分享自定义Linker的实现原理及SO加固技术

## 0x02 Linker源码分析

### PS：**这部分有点长，如果你只想看怎么实现的，可以直接跳到总结**

### 核心代码解析（只贴关键部分，不然太长了）

#### do_dlopen - 一切的起点

| 1234 | `soinfo* si = find_library(name);` `// 查找并加载SO到内存``if` `(si != NULL) {``si->CallConstructors();` `// 调用SO的初始化函数``}` |
|-|-|

看起来很简单对吧，让我们深入看看这两个函数都干了啥

#### find_library - 负责找SO的函数

| 1234567 | `static` `soinfo* find_library(``const` `char``* name) {``soinfo* si = find_library_internal(name);` `// 寻找相应的SO信息``if` `(si != NULL) {``si->ref_count++;` `// 这个计数很重要，用来判断SO是否已经加载过``}``return` `si;``}` |
|-|-|

#### CallConstructors - 调用构造函数

| 1234567891011121314 | `// 直接看重点``if` `(dynamic != NULL) {``for` `(Elf32_Dyn* d = dynamic; d->d_tag != DT_NULL; ++d) {``if` `(d->d_tag == DT_NEEDED) {` `// 先调用依赖库的构造函数``const` `char``* library_name = strtab + d->d_un.d_val;``TRACE(``"\"%s\": calling constructors in DT_NEEDED \"%s\""``, name, library_name);``find_loaded_library(library_name)->CallConstructors();``}``}``}``// DT_INIT要在DT_INIT_ARRAY之前调用``TRACE(``"\"%s\": calling constructors"``, name);``CallFunction(``"DT_INIT"``, init_func);` `// SO文件加壳的脱壳点！划重点！``CallArray(``"DT_INIT_ARRAY"``, init_array, init_array_count,` `false``);` |
|-|-|

这里有个有趣的地方：`DT_INIT`和`DT_INIT_ARRAY`是很多加固方案的脱壳点，因为这是SO被加载后最早执行的地方之一

#### find_library_internal - 真正干活的函数

| 12345678910111213141516171819202122232425262728293031 | `static` `soinfo* find_library_internal(``const` `char``* name) {``if` `(name == NULL) {``return` `somain;``}` `soinfo* si = find_loaded_library(name);``if` `(si != NULL) {``if` `(si->flags & FLAG_LINKED) {``return` `si;` `// 已经加载过了，直接返回``}``DL_ERR(``"OOPS: recursive link to \"%s\""``, si->name);``return` `NULL;``}` `TRACE(``"[ '%s' has not been loaded yet.  Locating...]"``, name);``si = load_library(name);` `// 真正加载SO文件的地方``if` `(si == NULL) {``return` `NULL;``}` `TRACE(``"[ init_library base=0x%08x sz=0x%08x name='%s' ]"``,``si->base, si->size, si->name);` `if` `(!soinfo_link_image(si)) {` `// 执行重定位（会用mmap，所以在/proc/pid/maps能看到）``munmap(``reinterpret_cast``<``void``*>(si->base), si->size);``soinfo_free(si);``return` `NULL;``}` `return` `si;``}` |
|-|-|

**关于重定位**：想象一下，你的SO文件里调用了`printf`函数，但编译的时候并不知道`printf`在内存的哪个位置，所以先用个占位符（比如`call 0x1234`）。重定位就是把这个占位符改成真实的地址

**基本流程梳理**：

1. **find_loaded_library()**：先看看是不是已经加载过了
2. **load_library()**：没加载过，那就加载
3. **soinfo_link_image()**：处理各种动态信息，执行重定位

#### load_library - 真正的加载器

| 1234567891011121314151617181920212223242526272829303132 | `static` `soinfo* load_library(``const` `char``* name) {``// 打开文件``int` `fd = open_library(name);``if` `(fd == -1) {``DL_ERR(``"library \"%s\" not found"``, name);``return` `NULL;``}` `// 读取ELF头并加载段``ElfReader elf_reader(name, fd);``if` `(!elf_reader.Load()) {` `// 注意：这里只读Program段！``return` `NULL;``}` `const` `char``* bname =` `strrchr``(name,` `'/'``);``// 为SO分配soinfo结构``soinfo* si = soinfo_alloc(bname ? bname + 1 : name);``if` `(si == NULL) {``return` `NULL;``}` `// 初始化soinfo对象``si->base = elf_reader.load_start();``si->size = elf_reader.load_size();``si->load_bias = elf_reader.load_bias();``si->flags = 0;``si->entry = 0;``si->dynamic = NULL;``si->phnum = elf_reader.phdr_count();``si->phdr = elf_reader.loaded_phdr();``return` `si;``}` |
|-|-|

#### ElfReader::Load()

| 12345678 | `bool` `ElfReader::Load() {``return` `ReadElfHeader() &&` `// 读ELF头``VerifyElfHeader() &&` `// 校验ELF头``ReadProgramHeader() &&` `// 读程序头``ReserveAddressSpace() &&` `// 分配内存空间``LoadSegments() &&` `// 加载段（脱壳的好地方）``FindPhdr();` `// 设置加载地址``}` |
|-|-|

**发现**：Android只读Program Header，而IDA依赖Section Header！这就是为什么很多加固会"抹头"——把Section Header搞坏，IDA就懵了，但Android照样能跑

#### soinfo_link_image - 链接的核心

在`si = load_library(name)`拿到SO信息后，就要开始一系列复杂操作了：

##### 1. 定位动态节

| 1234567891011121314151617181920212223242526272829 | `phdr_table_get_dynamic_section(``const` `Elf32_Phdr* phdr_table,``int`               `phdr_count,``Elf32_Addr        load_bias,``Elf32_Dyn**       dynamic,``size_t``*           dynamic_count,``Elf32_Word*       dynamic_flags)``{``const` `Elf32_Phdr* phdr = phdr_table;``const` `Elf32_Phdr* phdr_limit = phdr + phdr_count;` `for` `(phdr = phdr_table; phdr < phdr_limit; phdr++) {``if` `(phdr->p_type != PT_DYNAMIC) {` `// 找DYNAMIC段``continue``;``}` `*dynamic =` `reinterpret_cast``<Elf32_Dyn*>(load_bias + phdr->p_vaddr);``if` `(dynamic_count) {``*dynamic_count = (unsigned)(phdr->p_memsz / 8);``}``if` `(dynamic_flags) {``*dynamic_flags = phdr->p_flags;``}``return``;` `// 注意：找到第一个就返回了！``}``*dynamic = NULL;``if` `(dynamic_count) {``*dynamic_count = 0;``}``}` |
|-|-|

**又一个有趣的发现**：源码只处理第一个PT_DYNAMIC段！所以你可以加多个动态节来迷惑IDA，因为IDA会全部解析，而Android只看第一个。这算是个小技巧吧~

##### 2. 解析动态节

这部分代码太长了，主要就是初始化各种表：符号表、字符串表、重定位表等等。

##### 3. 加载依赖库

| 123456789101112131415 | `// 加载依赖库 (DT_NEEDED)``for` `(Elf32_Dyn* d = si->dynamic; d->d_tag != DT_NULL; ++d) {``if` `(d->d_tag == DT_NEEDED) {``const` `char``* library_name = si->strtab + d->d_un.d_val;``DEBUG(``"%s needs %s"``, si->name, library_name);``soinfo* lsi = find_library(library_name);` `// 递归加载依赖``if` `(lsi == NULL) {``strlcpy(tmp_err_buf, linker_get_error_buffer(),` `sizeof``(tmp_err_buf));``DL_ERR(``"could not load library \"%s\" needed by \"%s\"; caused by %s"``,``library_name, si->name, tmp_err_buf);``return` `false``;``}``*pneeded++ = lsi;``}``}` |
|-|-|

##### 4. 重定位操作

| 1234567891011121314151617181920212223 | `if` `(si->has_text_relocations) {``// 让代码段可写，这样才能修改``DL_WARN(``"%s has text relocations. This is wasting memory and is "``"a security risk. Please fix."``, si->name);``if` `(phdr_table_unprotect_segments(si->phdr, si->phnum, si->load_bias) < 0) {``DL_ERR(``"can't unprotect loadable segments for \"%s\": %s"``,``si->name,` `strerror``(``errno``));``return` `false``;``}``}` `if` `(si->plt_rel != NULL) {``DEBUG(``"[ relocating %s plt ]"``, si->name );``if` `(soinfo_relocate(si, si->plt_rel, si->plt_rel_count, needed)) {``return` `false``;``}``}``if` `(si->rel != NULL) {``DEBUG(``"[ relocating %s ]"``, si->name );``if` `(soinfo_relocate(si, si->rel, si->rel_count, needed)) {``return` `false``;``}``}` |
|-|-|

### 小结一下

说白了，Linker就是个搬运工，把磁盘上的SO文件按照一定的规则搬到内存里，让我们的程序能够调用。主要干这么几件事：

#### 1. **加载ELF文件**

- 用`mmap`把SO文件映射到内存（就像把文件"贴"到内存里）
- 解析各种头部信息
- 给`.bss`、`.data`这些段分配空间

#### 2. **处理依赖关系**

- 看看这个SO依赖哪些其他的SO
- 把依赖的SO也加载进来（递归的过程）
- 建立依赖关系图，避免重复加载

#### 3. **符号解析和重定位**

- 找到导出的函数和变量
- 修正函数调用地址
- 处理各种符号冲突

#### 4. **执行初始化**

- 按正确的顺序调用各个构造函数

## 0x03 自定义Linker实现

基于对Android Linker的理解，实现自定义Linker无需像AOSP源码那样考虑所有情况。我们可以专注于核心功能，实现一个精简版本

详细实现可参考：[自實現Linker加載so](https://bbs.kanxue.com/thread-282316.htm)

我实现的自定义Linker项目：[soLoader](https://github.com/SoyBeanMilkx/soLoader)

### 架构设计

**组件关系图**：

![Relationship](https://bbs.kanxue.com/upload/attach/202506/947037_2DJKKHKGVE5QHMJ.png)

**核心组件职责**：

| 组件名称 | 主要功能 | 关键操作 |
|-|-|-|
| `ElfLoader` | 系统协调器和公共API | `LoadLibrary()`, `GetSymbol()`, `CallConstructors()` |
| `ElfReader` | ELF文件解析与验证 | 读取头部、提取程序头、验证格式 |
| `MemoryManager` | 内存分配与保护 | `mmap()`操作、段加载、权限设置 |
| `SoinfoManager` | 共享对象元数据管理 | `soinfo`结构创建、依赖跟踪 |
| `Relocator` | 符号解析与重定位 | 处理重定位、解析符号、处理PLT/GOT |
| `Utils` | 系统工具与内省 | 系统调用、ELF结构辅助函数 |

具体实现原理请参考项目源码

## 0x04 SO加固实现

### 加固方案设计

以360加固为例，其核心思想是将主SO加密后嵌入壳SO中。壳SO作为loader被原生Linker加载后，负责解密、映射、链接、重定位主SO，最终调用主SO的函数来释放DEX

我们自己在设计的时候可以直接照搬这种模式，但是把两个so合并的操作有些麻烦，而且主SO本身就是被加密的，我个人觉得放在哪里都无所谓，你要想解密都得去分析壳SO，所以这里我实现了一个简化的版本，把主SO加密之后藏在了图片的后面，这样看上去它就是一张普通的图片

为简化实现，本方案采用以下设计：

- 不将两个SO合并，而是将加密的主SO隐藏在APK资源中
- 选择`res/mipmap/ic_launcher.webp`（应用图标）作为载体
- 使用RC4算法加密主SO，并添加魔数标识便于定位

### 加密实现

加密脚本的核心功能：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576 | `#!/usr/bin/env python3``"""``python prepare_hidden_so.py <so_file> <webp_image> <output_image> <key>``"""` `import` `sys``import` `os``import` `struct` `MAGIC_HEADER` `=` `b``"Yuuki"` `def` `rc4_init(key):``"""初始化RC4 S盒"""``S` `=` `list``(``range``(``256``))``j` `=` `0``key_len` `=` `len``(key)` `for` `i` `in` `range``(``256``):``j` `=` `(j` `+` `S[i]` `+` `key[i` `%` `key_len]) &` `0xFF``S[i], S[j]` `=` `S[j], S[i]` `return` `S` `def` `rc4_crypt(S, data):``"""RC4加密/解密"""``S` `=` `S.copy()``i` `=` `j` `=` `0``result` `=` `bytearray()` `for` `byte` `in` `data:``i` `=` `(i` `+` `1``) &` `0xFF``j` `=` `(j` `+` `S[i]) &` `0xFF``S[i], S[j]` `=` `S[j], S[i]``k` `=` `S[(S[i]` `+` `S[j]) &` `0xFF``]``result.append(byte ^ k)` `return` `bytes(result)` `def` `main():``# 参数验证``if` `len``(sys.argv) !``=` `5``:``print``(f``"Usage: {sys.argv[0]} <so_file> <webp_image> <output_image> <key>"``)``return` `1` `so_file` `=` `sys.argv[``1``]``webp_image` `=` `sys.argv[``2``]``output_image` `=` `sys.argv[``3``]``key` `=` `sys.argv[``4``].encode(``'utf-8'``)` `with` `open``(so_file,` `'rb'``) as f:``so_data` `=` `f.read()` `with` `open``(webp_image,` `'rb'``) as f:``webp_data` `=` `f.read()` `# RC4加密``S` `=` `rc4_init(key)``encrypted_so` `=` `rc4_crypt(S, so_data)` `S_verify` `=` `rc4_init(key)``decrypted` `=` `rc4_crypt(S_verify, encrypted_so)``if` `decrypted !``=` `so_data:``print``(``"Error: Encryption verification failed!"``)``return` `1` `with` `open``(output_image,` `'wb'``) as f:``f.write(webp_data)` `# 原始WebP数据``f.write(MAGIC_HEADER)` `# 魔数标识``f.write(struct.pack(``'<I'``,` `len``(so_data)))` `# 原始SO大小``f.write(encrypted_so)` `# 加密的SO数据` `print``(f``"加密完成！隐藏数据起始偏移: {len(webp_data)}"``)``return` `0` `if` `__name__` `=``=` `"__main__"``:``sys.exit(main())` |
|-|-|

### 解密流程

完整的解密加载流程：

1. **资源提取**（Java层）
2. **内存映射与解密**（Native层）
3. **加载执行**（自定义Linker）

#### 1. Java层资源提取

| 1234567891011121314151617181920212223242526272829303132333435363738 | `public` `static` `String getExtractedImagePath(Context context) {``File tempDir =` `new` `File(context.getCacheDir(),` `"yuuki_temp"``);``if` `(!tempDir.exists()) {``tempDir.mkdirs();``}``return` `new` `File(tempDir,` `"temp_image.webp"``).getAbsolutePath();``}` `public` `static` `boolean` `extractImageFromApk(Context context, String outputPath) {``String apkPath = context.getApplicationInfo().sourceDir;` `try` `(ZipInputStream zip =` `new` `ZipInputStream(``new` `FileInputStream(apkPath))) {``ZipEntry entry;``while` `((entry = zip.getNextEntry()) !=` `null``) {``if` `(entry.getName().equals(``"res/mipmap-xxxhdpi-v4/ic_launcher.webp"``)) {``File outFile =` `new` `File(outputPath);``File parent = outFile.getParentFile();``if` `(!parent.exists()) {``parent.mkdirs();``}` `try` `(FileOutputStream out =` `new` `FileOutputStream(outFile)) {``byte``[] buffer =` `new` `byte``[``1024``];``int` `len;``while` `((len = zip.read(buffer)) >` `0``) {``out.write(buffer,` `0``, len);``}``return` `true``;``}``}``zip.closeEntry();``}``}` `catch` `(IOException e) {``e.printStackTrace();``}` `return` `false``;``}` |
|-|-|

#### 2. Native层解密实现

在ElfReader中添加解密功能：

| 12345678910111213141516171819202122232425262728 | `bool` `ElfReader::HandleFileType() {``// 检查文件是否包含隐藏的SO``if` `(CryptoUtils::HasHiddenSO(mapped_file_, file_size_)) {``LOGI(``"检测到隐藏的SO文件，开始提取并解密..."``);` `void``* decrypted_data = nullptr;``size_t` `decrypted_size = 0;` `if` `(!CryptoUtils::ExtractAndDecryptHiddenSO(mapped_file_, file_size_,``&decrypted_data, &decrypted_size)) {``LOGE(``"提取和解密隐藏的SO失败"``);``return` `false``;``}` `// 替换映射数据为解密后的数据``decrypted_buffer_ = decrypted_data;``is_decrypted_ =` `true``;` `// 释放原始映射，使用解密缓冲区``munmap(mapped_file_, file_size_);``mapped_file_ = decrypted_buffer_;``file_size_ = decrypted_size;` `LOGI(``"隐藏SO提取和解密成功，大小: %zu"``, decrypted_size);``}` `return` `true``;``}` |
|-|-|

解密工具类的核心实现包括：

- 魔数头定位
- RC4解密算法
- ELF格式验证
- 内存管理

这样，自定义Linker就能透明地加载加密的SO文件，实现了简单的SO加固保护

## 0x05 总结

本文分析了Android Linker的工作原理，并基于此实现了自定义Linker和SO加固方案。整个项目涉及很多内存操作和底层知识，还是从中学到了很多东西的OvO。最后附上实现的小demo，希望这篇文章对想了解Linker的同学有所帮助。如果有什么问题或建议，欢迎交流

---

**参考资料**：

- [Android Open Source Project (AOSP) Linker源码](https://cs.android.com/android/platform/superproject/main/+/main:bionic/linker/)
- [ELF文件格式规范](https://ctf-wiki.org/executable/elf/structure/basic-info/)
- [自實現Linker加載so](https://bbs.kanxue.com/thread-282316.htm)

上传的附件：
- release.apk

（189.07kb，129次下载）

---

# 回复

## 回复 by 笑对VS人生 (#2)

*2025-6-15 13:50*

兼容性如何

## 回复 by mb_cbgtaveo (#3)

*2025-6-15 13:58*

6666

## 回复 by mb_ldbucrik (#4)

*2025-6-15 18:15*

感谢分享

## 回复 by SomeMx (#5)

*2025-6-15 19:15*

过来瞧瞧

## 回复 by onlythis (#6)

*2025-6-16 09:02*

感谢分享

## 回复 by Imxz (#7)

*2025-6-16 09:13*

666

## 回复 by GEKEZYX (#8)

*2025-6-16 09:37*

666

## 回复 by mb_vanjeoof (#9)

*2025-6-16 09:48*

666

## 回复 by xifgg (#10)

*2025-6-16 10:04*

666

## 回复 by Azhan_ (#11)

*2025-6-16 17:09*

666

## 回复 by zylyy (#12)

*2025-6-16 19:50*

666

## 回复 by Andy_877594 (#13)

*2025-6-17 11:05*

学习

## 回复 by koflfy (#14)

*2025-6-17 11:54*

mark

## 回复 by 文西哥 (#15)

*2025-6-17 12:14*

学习mark

## 回复 by wx_piracy (#16)

*2025-6-17 16:38*

mark

## 回复 by iBa0 (#17)

*2025-6-17 19:21*

666

## 回复 by mb_vvpefhit (#18)

*2025-6-17 19:47*

666

## 回复 by jdong (#19)

*2025-6-18 09:31*

6666

## 回复 by 晨曦遇晓 (#20)

*2025-6-18 17:05*

6666

## 回复 by mb_kgsesxqm (#21)

*2025-6-18 21:29*

暗示冒泡

## 回复 by 从现在开始 (#22)

*2025-6-19 09:24*

看一下

## 回复 by qqizai (#23)

*2025-6-19 09:28*

6666

## 回复 by mb_amstadtm (#24)

*2025-6-19 23:22*

看一下，谢谢

## 回复 by uni7corn (#25)

*2025-6-20 00:22*

学习学习

## 回复 by mb_fidppcok (#26)

*2025-6-20 08:46*

看看大佬的作品

## 回复 by wx_插曲 (#27)

*2025-6-20 11:22*

666

## 回复 by mb_mrjjcxgk (#28)

*2025-6-21 10:22*

666

## 回复 by lonkil (#29)

*2025-6-21 11:42*

动态注册的导出JNI方法，是如何处理的呢？

## 回复 by kkte (#30)

*2025-6-21 13:29*

mark

## 回复 by mb_jmkwanzm (#31)

*2025-6-22 11:50*

666

## 回复 by mb_mrgbywba (#32)

*2025-6-25 23:37*

学习学习

## 回复 by ONewTach (#33)

*2025-6-26 08:46*

666

## 回复 by mb_egmgknxr (#34)

*2025-6-26 09:50*

看看

## 回复 by 生命练习生 (#35)

*2025-7-7 10:04*

666

## 回复 by wx_嗯哼正在输入··· (#36)

*2025-7-7 11:52*

学习学习

## 回复 by 4Chan (#37)

*2025-7-7 12:02*

学习一下

## 回复 by mb_ddgrnawd (#38)

*2025-7-8 13:33*

学习学习

## 回复 by lidongyooo (#39)

*2025-7-8 22:40*

666

## 回复 by Gryffindoss (#40)

*2025-7-9 08:23*

666

## 回复 by Yangser (#41)

*2025-7-9 14:30*

>
> [lonkil](https://bbs.kanxue.com/user-40719.htm)
>
>  动态注册的导出JNI方法，是如何处理的呢？
>
>

解决了吗，没解决可以反编译我上传的apk看看，里面写了

## 回复 by 丶咖啡猫丶 (#42)

*2025-7-10 10:02*

666

## 回复 by asm_zhang (#43)

*2025-7-11 15:17*

666

## 回复 by xx_dd_y (#44)

*2025-7-14 13:46*

66666

## 回复 by xdcs100 (#45)

*2025-7-15 10:00*

学习

## 回复 by 月清晖 (#46)

*2025-7-16 22:15*

感谢楼主分享

## 回复 by Ms135 (#47)

*2025-7-19 09:11*

666

## 回复 by mb_jeplbefy (#48)

*2025-7-24 01:50*

学习学习

## 回复 by 我是小奥 (#49)

*2025-7-26 21:53*

学习学习

## 回复 by mb_kqntebgh (#50)

*2025-7-30 13:25*

学习一下

## 回复 by mb_sqhqbwmj (#51)

*2025-7-30 21:06*

学一下，谢谢

## 回复 by 无视红绿灯 (#52)

*2025-7-31 10:22*

学习学习

## 回复 by mb_ndmoqzht (#53)

*2025-7-31 21:37*

学习

## 回复 by αβγδεξπ (#54)

*2025-8-2 09:13*

tql

## 回复 by mb_lzotvdxv (#55)

*2025-8-4 02:34*

6666

## 回复 by mb_rbptjrta (#56)

*2025-8-4 14:08*

谢谢老哥，把你的源码看了一遍，结合ai当老师，解决了困扰我的一些问题。

## 回复 by 秃顶 (#57)

*2025-8-4 20:18*

6666

## 回复 by mb_tmbvnlxt (#58)

*2025-8-7 20:38*

666

## 回复 by mb_tnkubkna (#59)

*2025-8-11 10:44*

111

## 回复 by 鞠婧祎 (#60)

*2025-8-12 00:12*

1111

## 回复 by wx_kx31902 (#61)

*2025-8-12 04:59*

kk

## 回复 by 我不是卷王 (#62)

*2025-8-12 11:47*

666

## 回复 by Yangser (#63)

*2025-8-12 15:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rbptjrta](https://bbs.kanxue.com/user-1044999.htm)
>
>  谢谢老哥，把你的源码看了一遍，结合ai当老师，解决了困扰我的一些问题。
>
>

有帮助就好

## 回复 by 山竹笠 (#64)

*2025-8-15 14:21*

mark

## 回复 by mb_irhdtnzm (#65)

*2025-8-15 20:38*

1

## 回复 by 飆汗吉米 (#66)

*2025-8-17 04:03*

6666

## 回复 by 寻梦之璐 (#67)

*2025-8-18 20:28*

6666

## 回复 by mb_paeqogwt (#68)

*2025-8-19 01:01*

学习学习

## 回复 by czins (#69)

*2025-8-23 21:52*

厉害

## 回复 by 夫人十八岁 (#70)

*2025-8-25 20:08*

DDDD

## 回复 by czins (#71)

*2025-8-26 18:56*

佬，我看 soinfo 是新创建的，而 ng1ok-linker 是来自壳 so，静态jni函数，比如：Java_com_xxx，系统是如何找到的，这两种方式有啥区别

## 回复 by Arsylk (#72)

*2025-8-27 12:20*

666

## 回复 by rainb0w (#73)

*2025-9-9 15:30*

1

## 回复 by wx_coddvccwyh (#74)

*2025-9-13 18:05*

66666

## 回复 by XCicada (#75)

*2025-9-13 18:22*

学习

## 回复 by mb_ekhqutmo (#76)

*2025-9-15 11:49*

6666

## 回复 by fei3ei (#77)

*2025-9-17 17:01*

学习

## 回复 by mb_qqlojqnm (#78)

*2025-9-22 05:07*

111

## 回复 by 酋knave (#79)

*2025-9-22 16:05*

666

## 回复 by mb_fhpfcoqp (#80)

*2025-9-30 14:30*

学习学习

## 回复 by mb_dmryhnwz (#81)

*2025-10-4 19:38*

学习

## 回复 by 日暮归途 (#82)

*2025-10-4 22:02*

学习学习

## 回复 by 威兹曼 (#83)

*2025-10-13 08:39*

666

## 回复 by 倾心Deep (#84)

*2025-10-17 08:23*

666

## 回复 by 雪风完美 (#85)

*2025-10-18 23:50*

学习学习

## 回复 by mb_zphlpmxp (#86)

*2025-10-19 22:17*

very good.

## 回复 by mb_ldufamty (#87)

*2025-10-20 09:43*

学习

## 回复 by Roc.li (#88)

*2025-10-20 09:44*

学习

## 回复 by xautzbl (#89)

*2025-10-20 13:42*

1

## 回复 by guijingwen (#90)

*2025-10-20 14:23*

66

## 回复 by jjcat (#91)

*2025-10-21 22:05*

学习学习

## 回复 by 小辣鸡的id (#92)

*2025-10-24 16:58*

666

## 回复 by wx_sj_644 (#93)

*2025-10-24 17:37*

学习了

## 回复 by onwyc123 (#94)

*2025-10-26 12:05*

学习

## 回复 by cpannn (#95)

*2025-10-27 12:45*

冒个泡

## 回复 by mb_jnmxfjku (#96)

*2025-10-28 16:38*

666

## 回复 by mb_xyatmibc (#97)

*2025-11-6 02:57*

11

## 回复 by FindCall (#98)

*2025-11-13 17:18*

66

## 回复 by 踏水流 (#99)

*2025-11-20 14:13*

1111

## 回复 by Circ1e (#100)

*2025-11-21 16:28*

666

## 回复 by 智取棋 (#101)

*2025-11-24 08:57*

学习

## 回复 by 刘建龙 (#102)

*2025-11-25 10:42*

感谢你的贡献，论坛因你而更加精彩！

## 回复 by git_71735namngsec-netizen (#103)

*2025-11-25 11:43*

666

## 回复 by 眩晕症 (#104)

*2025-11-27 19:08*

学习

## 回复 by baitongling (#105)

*2025-12-2 19:27*

6666

## 回复 by mb_jxiwhkvq (#106)

*2025-12-6 10:47*

学习学习

## 回复 by Heiyiren123 (#107)

*2025-12-8 13:01*

顶一下，感谢分享！

## 回复 by cobe (#108)

*2025-12-19 10:01*

666

## 回复 by dsr000 (#109)

*2026-1-9 16:20*

666

## 回复 by ovo_帮我不c (#110)

*2026-1-9 17:11*

1

## 回复 by mb_zdcoxmwv (#111)

*2026-1-11 23:10*

学习

## 回复 by 灬哈密瓜 (#112)

*2026-1-12 13:44*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  czins](https://bbs.kanxue.com/user-869918.htm)
>
>  佬，我看 soinfo 是新创建的，而 ng1ok-linker 是来自壳 so，静态jni函数，比如：Java_com_xxx，系统是如何找到的，这两种方式有啥区别
>
>

不修复soinfo, 能找到个沟八符号. 此方案用于学习的而已

## 回复 by mb_vjpiriil (#113)

*2026-1-19 17:01*

大佬sixsixsix

## 回复 by yyyyy——— (#114)

*2026-1-19 17:02*

6666

## 回复 by 钱钱钱￥ (#115)

*2026-1-26 14:22*

学习

## 回复 by Majh (#116)

*2026-2-1 07:11*

![image](https://bbs.kanxue.com/view/img/face/019.gif)

## 回复 by mb_wtskxwnr (#117)

*2026-2-15 18:22*

566

## 回复 by mb_ysikfhxt (#118)

*2026-2-16 12:19*

111

## 回复 by 非凡人平常心 (#119)

*2026-2-16 14:07*

学习![image](https://bbs.kanxue.com/view/img/face/057.gif)

## 回复 by mb_jxhmajfh (#120)

*2026-2-16 14:54*

666666666

## 回复 by 櫬木汐 (#121)

*2026-2-26 14:39*

学习学习

## 回复 by 街道办事处 (#122)

*2026-2-26 14:56*

111

## 回复 by xeiyu (#123)

*2026-3-4 02:16*

66

## 回复 by mb_ttdxmirg (#124)

*2026-3-17 20:18*

学习学习

## 回复 by Sigil (#125)

*2026-3-27 19:09*

1

## 回复 by 晴空万里丶 (#126)

*2026-3-27 20:24*

学习下！

## 回复 by 小迷糊ddd (#127)

*2026-4-5 21:20*

感谢分享，认真学习。

## 回复 by 小尘0000 (#128)

*2026-4-8 14:45*

666

## 回复 by mb_koixqizd (#129)

*2026-4-8 22:18*

学习

## 回复 by 毛毛毛毛虫 (#130)

*2026-4-9 20:03*

学习

## 回复 by cx52038 (#131)

*2026-4-19 22:20*

666

## 回复 by mb_fqndstzl (#132)

*2026-4-20 10:48*

66666666

## 回复 by mb_ykavguun (#133)

*2026-4-20 20:20*

666

## 回复 by A0x01 (#134)

*2026-4-21 07:57*

666

## 回复 by 徐天意 (#135)

*2026-4-29 11:05*

支持

## 回复 by 徐天意 (#136)

*2026-4-29 11:06*

支持支持

## 回复 by 徐天意 (#137)

*2026-4-29 11:06*

支持支持

## 回复 by 徐天意 (#138)

*2026-4-29 11:06*

支持支持![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_uzmffdbw (#139)

*2026-4-29 11:37*

666

## 回复 by mb_qimctavn (#140)

*2026-4-29 12:34*

6

## 回复 by git_86585flowclouds (#141)

*2026-4-30 14:19*

学习学习

## 回复 by Ankeys (#142)

*2026-5-3 13:39*

点赞

## 回复 by ClPrada (#143)

*2026-5-4 17:23*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 宛枫 (#144)

*2026-5-16 00:34*

感谢分享

## 回复 by wx_张健_921 (#145)

*2026-5-21 17:01*

6666

## 回复 by 心在o (#146)

*2026-5-21 23:21*

学习学习

## 回复 by 叶晓枫A (#147)

*2026-6-4 10:57*

技术又更新了么,又白学了么

## 回复 by mb_sqetvntx (#148)

*2026-6-9 16:26*

学习

## 回复 by mb_rbixrkdo (#149)

*2026-6-12 10:01*

66666666学习谢谢了

## 回复 by wx_小友 (#150)

*2026-7-7 19:14*

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by 破执. (#151)

*2026-7-9 01:54*

学习

## 回复 by mb_fafswnif (#152)

*2026-7-14 17:45*

感谢分享

## 回复 by blackr0ck (#153)

*2026-7-15 16:25*

666
