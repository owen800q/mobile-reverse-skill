---
title: '[原创]ART环境下dex加载流程分析及frida dump dex方案'
url: https://bbs.kanxue.com/thread-277771.htm
tid: 277771
author: 行简
date: '2023-06-26'
tags: [Android安全, 原创, 逆向分析, HOOK注入, 源码框架, 工具脚本]
crawled_at: '2026-07-31T14:42:44+08:00'
replies: 6
---

# 0x01 前言

其实有台fart的脱壳机挺好的，很多时候就没有这么多麻烦，你说是吧。。。
手上有两台设备一个Android 7 一个Android 8，没脱壳需求的时候还没发现它两脱壳点完全不一样，为此有了今天的研究。
源码在线：<http://aospxref.com/>

# 0x02 源码解析

源码阅读是一件痛苦的事情，我相信不止我这么觉得，所以我会在不影响大家理解的情况下，以最简单的方式，以最少的源码量让大家读懂理解源码。

## 2.1 dex_file

从Android 5.0（Lollipop）开始，ART取代了之前的Dalvik虚拟机作为Android的主要运行时环境。
在/art/runtime/dex_file.cc中提供了对DEX文件的解析和访问功能，dex_file.cc的主要作用如下：
1、DEX文件解析：dex_file.cc提供了解析DEX文件的功能，可以读取DEX文件的结构和内容。它能够解析DEX文件的头部信息、字符串表、类定义、方法定义等，将这些信息转化为可供程序使用的数据结构。
2、类加载：dex_file.cc可以根据DEX文件中的类定义加载指定的类。它能够根据类的全限定名查找并获取类的相关信息，如父类、接口、字段、方法等。
3、方法调用和执行：通过dex_file.cc，可以获取DEX文件中方法的字节码指令，以及方法的参数和返回值类型等信息。这使得程序能够调用和执行DEX文件中定义的方法。
4、字符串处理：dex_file.cc还提供了对DEX文件中字符串表的操作。它可以读取DEX文件中的字符串，比如类名、方法名、字段名等，并提供相关的字符串处理功能。
5、资源访问：在DEX文件中，可能包含一些资源文件（如图片、音频等），dex_file.cc可以读取这些资源文件，以便程序进行相应的操作和使用。
dex_file.h中提供了两个重要的函数：

| 1234567 | `const uint8_t``*` `Begin() const {``return` `begin_;``}` `size_t Size() const {``return` `size_;``}` |
|-|-|

Begin()获取了dex在内存中的相对位置，Size()获取了dex的大小。

## 2.2 dex 格式规范

Dex文件的版本号标识着Dex文件的格式和兼容性。
每个Dex文件版本都对应着不同的Android系统版本，并且随着时间的推移，新的Dex文件版本会随着新版本的Android系统发布而引入。
打开源码网站找到对应版本源码，在File Path中输入dex_file.cc后点搜索，即可跳转到/art/runtime/dex_file.cc源码界面。
在Android 7.1.2 源码界面首先会发现这么一段代码：

| 12345678 | `namespace art {``const uint8_t DexFile::kDexMagic[]` `=` `{` `'d'``,` `'e'``,` `'x'``,` `'\n'` `};``const uint8_t DexFile::kDexMagicVersions[DexFile::kNumDexVersions][DexFile::kDexVersionLen]` `=` `{``{``'0'``,` `'3'``,` `'5'``,` `'\0'``},``/``/` `Dex version` `036` `skipped because of an old dalvik bug on some versions of android where dex``/``/` `files with that version number would erroneously be accepted` `and` `run.``{``'0'``,` `'3'``,` `'7'``,` `'\0'``}``};` |
|-|-|

其中明确规定了dex唯一允许的值是 035 和 037，Android 8.0 中为 038。注释中声明：
由于旧版 Android 中存在 Dalvik 错误，Dex 版本 036 已被跳过。Dex 036 版不适用于任何版本的 Android，而且永远不会。
Android 8.0 中：

| 123456789 | `const uint8_t DexFile::kDexMagic[]` `=` `{` `'d'``,` `'e'``,` `'x'``,` `'\n'` `};``const uint8_t DexFile::kDexMagicVersions[DexFile::kNumDexVersions][DexFile::kDexVersionLen]` `=` `{``{``'0'``,` `'3'``,` `'5'``,` `'\0'``},``/``/` `Dex version` `036` `skipped because of an old dalvik bug on some versions of android where dex``/``/` `files with that version number would erroneously be accepted` `and` `run.``{``'0'``,` `'3'``,` `'7'``,` `'\0'``},``/``/` `Dex version` `038``: Android` `"O"` `and` `beyond.``{``'0'``,` `'3'``,` `'8'``,` `'\0'``}``};` |
|-|-|

037 和 038 属于较新的格式规范，并未被广泛应用。

## 2.3 Android 7.1.2

### 2.3.1 DexFile::Open

首先看dex_file.cc中第一处 DexFile::Open 函数，通过OatFile取得DexFile走这个。
感兴趣的可以从/art/runtime/oat_file_manager.cc中OatFileManager::OpenDexFilesFromOat往下看：

| 1234567891011121314151617181920212223 | `std::unique_ptr<const DexFile> DexFile::``Open``(const uint8_t``*` `base, size_t size,``const std::string& location,``uint32_t location_checksum,``const OatDexFile``*` `oat_dex_file,``bool` `verify,``std::string``*` `error_msg) {``ScopedTrace trace(std::string(``"Open dex file from RAM "``)` `+` `location);``std::unique_ptr<const DexFile> dex_file` `=` `OpenMemory(base,``size,``location,``location_checksum,``nullptr,``oat_dex_file,``error_msg);``if` `(verify && !DexFileVerifier::Verify(dex_file.get(),``dex_file``-``>Begin(),``dex_file``-``>Size(),``location.c_str(),``error_msg)) {``return` `nullptr;``}``return` `dex_file;``}` |
|-|-|

解析：
1、参数列表

>
> const uint8_t* base 是一个指向 uint8_t 类型的指针，表示Dex文件的内存基地址。
> size_t size 是一个无符号整数，表示Dex文件的大小。
> const std::string& location 是一个常量引用，表示Dex文件的位置。
> uint32_t location_checksum 是一个无符号 32 位整数，表示Dex文件位置的校验和。
> const OatDexFile* oat_dex_file 是一个指向 OatDexFile 类对象的指针，用于关联Dex与Oat文件。
> bool verify 是一个布尔值，表示是否要验证Dex文件的有效性。
> std::string* error_msg 是一个指向 std::string 类对象的指针，用于存储错误消息（如果有）。
>
>
>

2、函数体

>
> 调用另一个成员函数 OpenMemory，传递了相同的参数，并返回其结果作为函数的返回值。
> 在调用中，mem_map->Begin() 返回内存映射的起始地址，mem_map->Size() 返回映射区域的大小，然后将它们以及其他参数传递给 OpenMemory 函数。
>
>
>

看第二处 DexFile::Open 函数，通过OatFile取得DexFile失败走这个，从Zip存档中打开Dex文件。
可从/art/runtime/oat_file_manager.cc中OatFileManager::OpenDexFilesFromOat函数中DexFile::Open入参参数判断出：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445 | `std::unique_ptr<const DexFile> DexFile::``Open``(const ZipArchive& zip_archive, const char``*` `entry_name,``const std::string& location, std::string``*` `error_msg,``ZipOpenErrorCode``*` `error_code) {``ScopedTrace trace(``"Dex file open from Zip Archive "` `+` `std::string(location));``CHECK(!location.empty());``std::unique_ptr<ZipEntry> zip_entry(zip_archive.Find(entry_name, error_msg));``if` `(zip_entry.get()` `=``=` `nullptr) {``*``error_code` `=` `ZipOpenErrorCode::kEntryNotFound;``return` `nullptr;``}``std::unique_ptr<MemMap>` `map``(zip_entry``-``>ExtractToMemMap(location.c_str(), entry_name, error_msg));``if` `(``map``.get()` `=``=` `nullptr) {``*``error_msg` `=` `StringPrintf(``"Failed to extract '%s' from '%s': %s"``, entry_name, location.c_str(),``error_msg``-``>c_str());``*``error_code` `=` `ZipOpenErrorCode::kExtractToMemoryError;``return` `nullptr;``}``std::unique_ptr<const DexFile> dex_file(OpenMemory(location, zip_entry``-``>GetCrc32(),` `map``.release(),``error_msg));``if` `(dex_file.get()` `=``=` `nullptr) {``*``error_msg` `=` `StringPrintf(``"Failed to open dex file '%s' from memory: %s"``, location.c_str(),``error_msg``-``>c_str());``*``error_code` `=` `ZipOpenErrorCode::kDexFileError;``return` `nullptr;``}``if` `(!dex_file``-``>DisableWrite()) {``*``error_msg` `=` `StringPrintf(``"Failed to make dex file '%s' read only"``, location.c_str());``*``error_code` `=` `ZipOpenErrorCode::kMakeReadOnlyError;``return` `nullptr;``}``CHECK(dex_file``-``>IsReadOnly()) << location;``if` `(!DexFileVerifier::Verify(dex_file.get(), dex_file``-``>Begin(), dex_file``-``>Size(),``location.c_str(), error_msg)) {``*``error_code` `=` `ZipOpenErrorCode::kVerifyError;``return` `nullptr;``}``*``error_code` `=` `ZipOpenErrorCode::kNoError;``return` `dex_file;``}` `/``/` `Technically we do` `not` `have a limitation with respect to the number of dex files that can be` `in` `a``/``/` `multidex APK. However, it's bad practice, as each dex` `file` `requires its own tables` `for` `symbols``/``/` `(types, classes, methods, ...)` `and` `dex caches. So warn the user that we` `open` `a` `zip` `with what``/``/` `seems an excessive number.``static constexpr size_t kWarnOnManyDexFilesThreshold` `=` `100``;` |
|-|-|

解析：
1、参数列表

>
> const ZipArchive& zip_archive 是一个常量引用，表示包含Dex文件的Zip存档对象。
> const char* entry_name 是一个指向字符的指针，表示Dex文件在Zip存档中的入口名称。
> const std::string& location 是一个常量引用，表示Dex文件的位置。
> std::string* error_msg 是一个指向 std::string 类对象的指针，用于存储错误消息（如果有）。
> ZipOpenErrorCode* error_code 是一个指向 ZipOpenErrorCode 枚举类型对象的指针，用于存储错误码。
>
>
>

2、函数体

>
> ScopedTrace 类的实例化，初始化了一个 ScopedTrace 对象，用于跟踪函数执行过程。同时，构造函数会生成一条与Zip存档位置相关的跟踪信息。
> 使用 CHECK 宏检查 location 是否为空，如果为空则触发断言。
> 调用 zip_archive 对象的 Find 函数查找指定名称的Zip文件条目，并使用 std::unique_ptr 管理返回的 ZipEntry 对象。
> 如果找不到Zip文件条目，则将错误码设置为 ZipOpenErrorCode::kEntryNotFound，并返回空指针。
> 调用 zip_entry 对象的 ExtractToMemMap 函数，将Zip文件条目提取到内存映射对象 MemMap 中，并使用 std::unique_ptr 管理返回的 MemMap 对象。
> 如果提取失败，则根据错误消息生成详细错误信息，并将错误码设置为 ZipOpenErrorCode::kExtractToMemoryError，然后返回空指针。
> 调用另一个成员函数 OpenMemory，传递了相同的参数，并返回一个指向 const DexFile 对象的智能指针。
> 如果打开Dex文件失败，则根据错误消息生成详细错误信息，并将错误码设置为 ZipOpenErrorCode::kDexFileError，然后返回空指针。
> 调用 DisableWrite 函数将Dex文件设置为只读模式。如果设置失败，则根据错误消息生成详细错误信息，并将错误码设置为 ZipOpenErrorCode::kMakeReadOnlyError，然后返回空指针。
> 使用 CHECK 宏检查Dex文件是否已被设置为只读模式，如果未设置则触发断言。
> 调用 DexFileVerifier 类的静态成员函数 Verify 验证Dex文件的有效性。如果验证失败，则将错误码设置为 ZipOpenErrorCode::kVerifyError，然后返回空指针。
> 如果所有步骤执行成功，将错误码设置为 ZipOpenErrorCode::kNoError，并返回包含Dex文件的智能指针。
> 此外，还定义了一个常量 kWarnOnManyDexFilesThreshold，用于设置在多dex APK中存在过多Dex文件时发出警告的阈值。
>
>
>

这两个open函数，只要成功都走了成员函数 OpenMemory 只是其入参不同：
第一处入参：

| 1 | `std::unique_ptr<const DexFile> dex_file` `=` `OpenMemory(base, size, location, location_checksum, nullptr, oat_dex_file, error_msg);` |
|-|-|

第二处入参：

| 1 | `std::unique_ptr<const DexFile> dex_file(OpenMemory(location, zip_entry``-``>GetCrc32(),` `map``.release(),error_msg));` |
|-|-|

### 2.3.2 DexFile::OpenMemory

查看两个重载的OpenMemory成员函数：
第一处：

| 123456789101112131415 | `std::unique_ptr<const DexFile> DexFile::OpenMemory(const uint8_t``*` `base,``size_t size,``const std::string& location,``uint32_t location_checksum,``MemMap``*` `mem_map,``const OatDexFile``*` `oat_dex_file,``std::string``*` `error_msg) {``CHECK_ALIGNED(base,` `4``);` `/``/` `various dex` `file` `structures must be word aligned``std::unique_ptr<DexFile> dex_file(``new DexFile(base, size, location, location_checksum, mem_map, oat_dex_file));``if` `(!dex_file``-``>Init(error_msg)) {``dex_file.reset();``}``return` `std::unique_ptr<const DexFile>(dex_file.release());``}` |
|-|-|

第二处：

| 123456789101112 | `std::unique_ptr<const DexFile> DexFile::OpenMemory(const std::string& location,``uint32_t location_checksum,``MemMap``*` `mem_map,``std::string``*` `error_msg) {``return` `OpenMemory(mem_map``-``>Begin(),``mem_map``-``>Size(),``location,``location_checksum,``mem_map,``nullptr,``error_msg);``}` |
|-|-|

不难发现第二处最后还是走了第一个OpenMemory函数，殊途同归了。

### 2.3.3 脱壳点分析

经过上面的分析，可得DexFile::Open后只要打开了dex文件，最终都是走OpenMemory函数，其重要意义不必多说，dddd，这也是其作为常用脱壳点的原因！
参数解析：

>
> const uint8_t* base 是一个指向 uint8_t 类型的指针，表示Dex文件在内存中的基地址。
> size_t size 表示Dex文件的大小。
> const std::string& location 是一个常量引用，表示Dex文件的位置。
> uint32_t location_checksum 表示Dex文件位置的校验和。
> MemMap* mem_map 是一个指向 MemMap 类对象的指针，表示内存映射对象。
> const OatDexFile* oat_dex_file 是一个指向 OatDexFile 类对象的常量指针。
> std::string* error_msg 是一个指向 std::string 类对象的指针，用于存储错误消息（如果有）。
>
>
>

函数体：

>
> 用 CHECK_ALIGNED 宏检查 base 是否按字对齐，因为Dex文件的结构必须按字对齐。
> 使用 std::unique_ptr 创建一个指向 DexFile 对象的智能指针 dex_file。DexFile 的构造函数接收多个参数，用于初始化 DexFile 对象。
> 如果 dex_file->Init(error_msg) 返回 false，表示初始化失败，将 dex_file 重置为 nullptr。
> 返回一个指向 dex_file 的常量 std::unique_ptr<const DexFile> 对象。
>
>
>

前两个参数分别是dex的起始地址和大小，想dumpdex直接hook该函数，在加上libart.so的基址即可完整脱下dex。
注意这里的base需加上固定偏移parseInt(base,16) + 0x20。

## 2.4 Android 8.1.0

其实和Android 7.1.2的分析流程并无太多区别，甚至可以说大差不差，只是最后的脱壳函数变成了OpenCommon函数。

### 2.4.1 DexFile::Open

看dex_file.cc中第一处 DexFile::Open 函数，通过OatFile取得DexFile走这个。
感兴趣的可以从/art/runtime/oat_file_manager.cc中OatFileManager::OpenDexFilesFromOat往下看：

| 123456789101112131415161718 | `std::unique_ptr<const DexFile> DexFile::``Open``(const uint8_t``*` `base,``size_t size,``const std::string& location,``uint32_t location_checksum,``const OatDexFile``*` `oat_dex_file,``bool` `verify,``bool` `verify_checksum,``std::string``*` `error_msg) {``ScopedTrace trace(std::string(``"Open dex file from RAM "``)` `+` `location);``return` `OpenCommon(base,``size,``location,``location_checksum,``oat_dex_file,``verify,``verify_checksum,``error_msg);``}` |
|-|-|

解析：
1、参数列表

>
> const uint8_t* base 是一个指向 uint8_t 类型的指针，表示Dex文件在内存中的基地址。
> size_t size 表示Dex文件的大小。
> const std::string& location 是一个常量引用，表示Dex文件的位置。
> uint32_t location_checksum 表示Dex文件位置的校验和。
> const OatDexFile* oat_dex_file 是一个指向 OatDexFile 类对象的常量指针。
> bool verify 表示是否进行验证。
> bool verify_checksum 表示是否验证校验和。
> std::string* error_msg 是一个指向 std::string 类对象的指针，用于存储错误消息（如果有）。
>
>
>

2、函数体

>
> 创建一个 ScopedTrace 对象 trace，并将信息字符串与 location 相连接，用于跟踪和记录Dex文件的打开操作。
> 调用 OpenCommon 函数，将参数传递给 OpenCommon，并返回其返回值。
>
>
>

看第二处 DexFile::Open 函数，通过OatFile取得DexFile失败走这个，从Zip存档中打开Dex文件。
可从/art/runtime/oat_file_manager.cc中OatFileManager::OpenDexFilesFromOat函数中DexFile::Open入参参数判断出：

| 12345678910111213141516171819202122232425262728 | `std::unique_ptr<const DexFile> DexFile::``Open``(const std::string& location,``uint32_t location_checksum,``std::unique_ptr<MemMap>` `map``,``bool` `verify,``bool` `verify_checksum,``std::string``*` `error_msg) {``ScopedTrace trace(std::string(``"Open dex file from mapped-memory "``)` `+` `location);``CHECK(``map``.get() !``=` `nullptr);` `if` `(``map``-``>Size() < sizeof(DexFile::Header)) {``*``error_msg` `=` `StringPrintf(``"DexFile: failed to open dex file '%s' that is too short to have a header"``,``location.c_str());``return` `nullptr;``}``std::unique_ptr<DexFile> dex_file` `=` `OpenCommon(``map``-``>Begin(),``map``-``>Size(),``location,``location_checksum,``kNoOatDexFile,``verify,``verify_checksum,``error_msg);``if` `(dex_file !``=` `nullptr) {``dex_file``-``>mem_map_` `=` `std::move(``map``);``}``return` `dex_file;``}` |
|-|-|

解析：
1、参数列表

>
> const std::string& location 是一个常量引用，表示Dex文件的位置。
> uint32_t location_checksum 表示Dex文件位置的校验和。
> std::unique_ptr<MemMap> map 是一个指向 MemMap 类对象的独占指针，表示内存映射区域。
> bool verify 表示是否进行验证。
> bool verify_checksum 表示是否验证校验和。
> std::string* error_msg 是一个指向 std::string 类对象的指针，用于存储错误消息（如果有）。
>
>
>

2、函数体

>
> 创建一个 ScopedTrace 对象 trace，并将信息字符串与 location 相连接，用于跟踪和记录Dex文件的打开操作。
> 使用 CHECK 宏检查 map 是否为非空指针。如果为空指针，则产生一个断言失败并终止程序的错误。
> 如果内存映射区域的大小小于 DexFile::Header 的大小，说明Dex文件太短而无法包含头部信息，将错误消息赋值给 error_msg，然后返回空指针。
> 调用 OpenCommon 函数，将内存映射区域的起始地址、大小、位置、校验和等参数传递给 OpenCommon 函数，并将返回值赋给 dex_file。
> 如果 dex_file 不为空指针，将内存映射区域的所有权转移给 dex_file 的 mem_map_ 成员变量。
> 返回 dex_file。
>
>
>

这两个open函数，只要成功都走了成员函数 OpenCommon ，且该函数并无重载。

### 2.4.2 DexFile::OpenCommon

查看其函数：

| 123456789101112131415161718192021222324252627282930313233343536373839404142 | `std::unique_ptr<DexFile> DexFile::OpenCommon(const uint8_t``*` `base,``size_t size,``const std::string& location,``uint32_t location_checksum,``const OatDexFile``*` `oat_dex_file,``bool` `verify,``bool` `verify_checksum,``std::string``*` `error_msg,``VerifyResult``*` `verify_result) {``if` `(verify_result !``=` `nullptr) {``*``verify_result` `=` `VerifyResult::kVerifyNotAttempted;``}``std::unique_ptr<DexFile> dex_file(new DexFile(base,``size,``location,``location_checksum,``oat_dex_file));``if` `(dex_file` `=``=` `nullptr) {``*``error_msg` `=` `StringPrintf(``"Failed to open dex file '%s' from memory: %s"``, location.c_str(),``error_msg``-``>c_str());``return` `nullptr;``}``if` `(!dex_file``-``>Init(error_msg)) {``dex_file.reset();``return` `nullptr;``}``if` `(verify && !DexFileVerifier::Verify(dex_file.get(),``dex_file``-``>Begin(),``dex_file``-``>Size(),``location.c_str(),``verify_checksum,``error_msg)) {``if` `(verify_result !``=` `nullptr) {``*``verify_result` `=` `VerifyResult::kVerifyFailed;``}``return` `nullptr;``}``if` `(verify_result !``=` `nullptr) {``*``verify_result` `=` `VerifyResult::kVerifySucceeded;``}``return` `dex_file;``}` |
|-|-|

解析：
1、参数列表

>
> size_t size 表示Dex文件的大小。
> const std::string& location 是一个常量引用，表示Dex文件的位置。
> uint32_t location_checksum 表示Dex文件位置的校验和。
> const OatDexFile* oat_dex_file 是一个指向 OatDexFile 对象的常量指针。
> bool verify 表示是否进行验证。
> bool verify_checksum 表示是否验证校验和。
> std::string* error_msg 是一个指向 std::string 对象的指针，用于存储错误消息（如果有）。
> VerifyResult* verify_result 是一个指向 VerifyResult 枚举类型对象的指针，用于存储验证结果（如果有）。
>
>
>

2、函数体

>
> 如果 verify_result 不为空指针，则将其值设置为 VerifyResult::kVerifyNotAttempted，表示验证尚未尝试。
> 使用 new 运算符创建一个 DexFile 对象，并将参数传递给构造函数，然后将返回的指针赋给 dex_file。
> 如果 dex_file 为空指针，则将错误消息设置为无法打开Dex文件的错误信息，并返回空指针。
> 调用 Init 函数初始化 dex_file，如果初始化失败，则将 dex_file 重置为空指针，并返回空指针。
> 如果需要进行验证而且验证失败，则将验证结果设置为 VerifyResult::kVerifyFailed，表示验证失败，并返回空指针。
> 如果 verify_result 不为空指针，则将其值设置为 VerifyResult::kVerifySucceeded，表示验证成功。
> 返回 dex_file。
>
>
>

和上个版本一样，前两个参数分别是dex的起始地址和大小，想dumpdex直接hook该函数，在加上libart.so的基址即可完整脱下dex。
注意这里的base需加上固定偏移parseInt(base,16) + 0x20。

## 2.5 总结

总结来看在art模式下，无论哪个Android版本下其dex的加载流程总是类似的，都可以从/art/runtime/oat_file_manager.cc源代码中找出往下的流程，其hook点也并非是一成不变的。
在Android 9版本后从原来的/art/runtime/dex_file.cc变成了/art/libdexfile/dex/dex_file_loader.cc文件中查找hook函数，一样可以从/art/runtime/oat_file_manager.cc代码中得出结论。

# 0x03 frida dump dex方案

## 3.1 hook 函数获取

需要hook的so文件为：libart.so
需要hook的函数为：OpenCommon、OpenMemory
但在C++编译过程中函数名会进行名称修饰，用以支持函数重载和命名空间。这种修饰将函数名转换为一串带有类型信息的字符串，以便在链接和调用过程中进行区分。
所以想直接通过给定OpenCommon、OpenMemory函数名进行hook是行不通的。
那总不能，每换一个设备就需要去找对应的so文件查看其对应的特征函数名吧？
frida enumerateExportsSync() 函数很好的解决了这个问题，可用于枚举给定模块（或进程）中的导出函数。
具体来说，它的作用如下：
接收一个模块名或进程名作为参数，可以是字符串形式的名称或整数形式的进程ID。
枚举出指定模块（或进程）中所有的导出函数。
返回一个包含导出函数信息的数组，每个元素都包含函数名及其对应的内存地址。
那么就通过该函数进行hook函数获取：

| 1234567891011121314151617 | `function find_hook_fun() {``var fun_Name` `=` `"";` `/``/` `声明一个变量用于存储函数名``var libart` `=` `Module.findBaseAddress(``'libart.so'``);` `/``/` `查找 libart.so 的基地址``var exports` `=` `Module.enumerateExportsSync(``"libart.so"``);` `/``/` `枚举 libart.so 导出函数``for` `(var i` `=` `0``; i < exports.length; i``+``+``) {``if` `(exports[i].name.indexOf(``"OpenMemory"``) !``=``=` `-``1``) {` `/``/` `如果导出函数名包含` `"OpenMemory"``fun_Name` `=` `exports[i].name;` `/``/` `将函数名赋值给 fun_Name``console.log(``"导出模块名: "` `+` `exports[i].name` `+` `"\t\t偏移地址: "` `+` `(exports[i].address` `-` `libart` `-` `1``));` `/``/` `打印导出函数名和偏移地址``break``;` `/``/` `跳出循环``}` `else` `if` `(exports[i].name.indexOf(``"OpenCommon"``) !``=``=` `-``1``) {` `/``/` `如果导出函数名包含` `"OpenCommon"``fun_Name` `=` `exports[i].name;` `/``/` `将函数名赋值给 fun_Name``console.log(``"导出模块名: "` `+` `exports[i].name` `+` `"\t\t偏移地址: "` `+` `(exports[i].address` `-` `libart` `-` `1``));` `/``/` `打印导出函数名和偏移地址``break``;` `/``/` `跳出循环``}``}``return` `fun_Name;` `/``/` `返回找到的函数名``}` |
|-|-|

## 3.2 DEX 校验

但根据DEX格式的官方规范，唯一允许的值是035和037，Android 8.0中为038。
根据其给定的规则，可编写如下代码进行DEX文件校验：

| 123456789101112131415 | `function DexFileVerifier(Verify) {``var magic_03x` `=` `true;` `/``/` `声明一个变量用于标识是否符合特定条件，默认为 true``var magic_Hex` `=` `[``0x64``,` `0x65``,` `0x78``,` `0x0a``,` `0x30``,` `0x33``,` `0x35``,` `0x00``];` `/``/` `给定最常见dex魔数序列``for` `(var i` `=` `0``; i <` `8``; i``+``+``) {` `/``/` `遍历魔数序列的每个字节``if` `(Memory.readU8(ptr(Verify).add(i)) !``=``=` `magic_Hex[i]) {` `/``/` `判断 Verify 内存地址偏移 i 处的字节是否与魔数序列相等``if` `(Memory.readU8(ptr(Verify).add(i))` `=``=``=` `0x37` `\|\|` `0x38``) {` `/``/` `如果当前字节等于` `0x37` `或者` `0x38` `新版本的dex``console.log(``'new dex'``);` `/``/` `打印输出` `'new dex'``}` `else` `{``magic_03x` `=` `false;` `/``/` `将 magic_03x 置为 false``break``;` `/``/` `跳出循环``}``}``}``return` `magic_03x;` `/``/` `返回 magic_03x 的值，表示是否符合特定条件``}` |
|-|-|

## 3.3 dump dex

前面已经把要将的都讲了，直接上代码吧，注释也很详细：

| 12345678910111213141516171819202122232425262728293031323334353637 | `function dump_Dex(fun_Name, apk_Name) {``if` `(fun_Name !``=``=` `'') {` `/``/` `判断传入的参数 fun_Name 是否为空字符串``var hook_fun` `=` `Module.findExportByName(``"libart.so"``, fun_Name);` `/``/` `在 libart.so 动态库中查找指定的导出函数地址``Interceptor.attach(hook_fun, {` `/``/` `使用 Interceptor 对导出函数进行挂钩``onEnter: function (args) {` `/``/` `进入函数之前的回调函数``var begin` `=` `0``;` `/``/` `初始化一个变量用于保存 Dex 文件的起始地址``var dex_flag` `=` `false;` `/``/` `初始化一个标志位，表示是否符合 Dex 文件的魔数``dex_flag` `=` `DexFileVerifier(args[``0``]);` `/``/` `调用 DexFileVerifier 函数对传入的第一个参数进行验证``if` `(dex_flag` `=``=``=` `true) {` `/``/` `如果验证通过``begin` `=` `args[``0``];` `/``/` `保存 Dex 文件的起始地址``}``if` `(begin` `=``=``=` `0``) {` `/``/` `如果起始地址为` `0``dex_flag` `=` `DexFileVerifier(args[``1``]);` `/``/` `再次调用 DexFileVerifier 函数对传入的第二个参数进行验证``if` `(dex_flag` `=``=``=` `true) {` `/``/` `如果验证通过``begin` `=` `args[``1``];` `/``/` `保存 Dex 文件的起始地址``}``}``if` `(dex_flag` `=``=``=` `true) {` `/``/` `如果验证通过``console.log(``"magic : "` `+` `Memory.readUtf8String(begin));` `/``/` `打印输出 Dex 文件的魔数``var address` `=` `parseInt(begin,``16``)` `+` `0x20``;` `/``/` `计算 Dex 文件大小字段的地址``var dex_size` `=` `Memory.readInt(ptr(address));` `/``/` `读取 Dex 文件大小``console.log(``"dex_size :"` `+` `dex_size);` `/``/` `打印输出 Dex 文件的大小``var dex_path` `=` `"/data/data/"` `+` `apk_Name` `+` `"/"` `+` `dex_size` `+` `".dex"``;` `/``/` `构建 Dex 文件保存路径``var dex_file` `=` `new` `File``(dex_path,` `"wb"``);` `/``/` `创建一个文件对象用于写入 Dex 文件``dex_file.write(Memory.readByteArray(begin, dex_size));` `/``/` `将 Dex 文件内容写入文件``dex_file.flush();` `/``/` `刷新文件缓冲区``dex_file.close();` `/``/` `关闭文件``}``},``onLeave: function (retval) {` `/``/` `函数返回之后的回调函数` `}``});``}` `else` `{``console.log(``"Error: no hook function."``);` `/``/` `如果传入的参数 fun_Name 为空字符串，则打印错误消息``}``}` |
|-|-|

## 3.4 调用方法

| 12345 | `var fun_Name` `=` `find_hook_fun();``var apk_Name` `=` `'com.xxx.xxx'` `/``/` `给定要hook的apk` `dump_Dex(fun_Name, apk_Name);``/``/` `frida` `-``U` `-``f com.xxx.xxx` `-``l dumpdex.js` `-``-``no``-``pause` |
|-|-|

在手机上启动 fs 执行 frida -U -f com.xxx.xxx -l dumpdex.js --no-pause 脱壳后的dex保存在/data/data/应用包名/目录下

# 0x04 结论

缺点：普通加固可以脱壳,对于类抽取等加固脱出的只是个空壳，需要做指令Dump以及Patch到脱出的Dex文件中，后续如有遇到该类型apk再给大家做对应的分享。
无论是工具脱壳，还是自行脱壳，最根本的思想还是在dex加载流程中进行dump，整个流程中可脱壳时机有很多，但脱壳的时机不同，效果也会不同，我无非是站在前人的肩膀上快速的定位了较好的脱壳点。

---

# 回复

## 回复 by 秋狝 (#2)

*2023-6-27 09:05*

感谢分享

## 回复 by vay (#3)

*2023-6-27 13:12*

![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by vrolife (#4)

*2023-7-4 08:29*

“大相径庭”这个成语是不是用错了？这样直接存参数给定的内存区域，如果遇到越界的dex咋办？

## 回复 by 行简 (#5)

*2023-7-4 09:38*

>
> [vrolife](https://bbs.kanxue.com/user-978503.htm)
>
>  “大相径庭”这个成语是不是用错了？这样直接存参数给定的内存区域，如果遇到越界的dex咋办？
>
>

确实使用错误，感谢纠错，已更正！越界dex你说的是方法数超过65536会进行分包操作？这种情况的话不用担心，只要是一代壳都能dump。

## 回复 by vrolife (#6)

*2023-7-5 15:43*

>
> [行简](https://bbs.kanxue.com/user-945390.htm)
>
>  确实使用错误，感谢纠错，已更正！越界dex你说的是方法数超过65536会进行分包操作？这种情况的话不用担心，只要是一代壳都能dump。
>
>

我指的是OpenMemory/OpenCommon的size参数比实际dex内容小的情况。

## 回复 by chaego (#8)

*2024-1-27 10:48*

楼主蛋粗，很不错的文章
