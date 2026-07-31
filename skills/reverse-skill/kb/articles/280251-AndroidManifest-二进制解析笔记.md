---
title: '[原创]AndroidManifest 二进制解析笔记'
url: https://bbs.kanxue.com/thread-280251.htm
tid: 280251
author: 简单的简单
date: '2024-01-18'
tags: [Android安全, 原创, 基础理论, 工具脚本]
crawled_at: '2026-07-31T14:33:20+08:00'
replies: 7
---

# AndroidManifest解析笔记

## 前言

自笔者开始学习Android逆向的第一天起就一直被一个问题所困扰，那就是 AndroidManifest 的编码总是会有问题，相信大家在使用 apktool 的时候如果直接 `java -jar apktool.jar d HelloWorld.apk` 那么在回编译的时候大概率会出现报错，这是因为 apktool 的资源的解析是有问题的，添加参数 -r 可以屏蔽资源的解析，但这样一来 AndroidManifest 就无法解析，而在逆向的过程中很常见的需求就是修改 AndroidManifest，例如修改启动类又或者添加debug标志，所以很容易想到的方法就是 apktool.jar 屏蔽资源解析，然后使用针对 AndroidManifest 修改的工具，这其中有许多大佬开源了自己的 AndroidManifest 修改工具，但在笔者的使用过程中总是会有这样那样的问题，正好最近有个需求是修改 AndroidManifest，所以在这里记录下 AndroidManifest.xml 二进制文件格式分析。

## 格式总览

首先按照惯例先贴上这张神图，可以说总结的非常全面，但此图也有自己的问题，那就是难以让读者在心中对整个 AndroidManifest 格式有一个大概的雏形。

![image-20240118115059789](https://bbs.kanxue.com/upload/attach/202401/950902_YAJ6SDC6MNAM9TH.jpg)

在这张图中我们需要明白整个 AndroidManifest 格式分为六大区域，七种 Chunk 类型，依次分别为 AndroidManifestHead、StringChunk、ResourceChunk、StartNamespaceChunk、StartTagChunk&EndTagChunk、EndNameSpaceChunk，其中多数情况 ResourceChunk为空，不太需要处理。

![image-20240118120250532](https://bbs.kanxue.com/upload/attach/202401/950902_AQQZXXNE6CDAS8A.jpg)

## AndroidManifestHead

AndroidManifestHead 占据 AndroidManifest 的起始8个字节，magic 标志着这个文件是 AndroidManifest 格式，file_size 记录 AndroidManifest.xml 文件的大小，这种文件头可以说是异常简单了。

| 1234 | `struct sAndroidManifestHead {``int` `magic;` `/``/` `标志着这个文件是 AndroidManifest 格式``int` `file_size;` `/``/` `记录 AndroidManifest.xml  文件的大小``};` |
|-|-|

## Chunk

笔者在分析完 AndroidManifest 后总结出 StringChunk、ResourceChunk、StartNamespaceChunk、StartTagChunk、EndTagChunk、EndNameSpaceChunk 这六种块的前 8 个字节是一样的

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950 | `class` `Chunk {``public``:``struct` `sChunk {``int` `cSignature;` `// 块类型标识``// cSignature = 0x001c0001  stringChunk``// cSignature = 0x00080180  resourceChunk``// cSignature = 0x00100100  startNameSpaceChunk``// cSignature = 0x00100102  startTagChunk``// cSignature = 0x00100103  endTagChunk``// cSignature = 0x00100101  EndNameSpaceChunk``int` `cSize;` `// 块的大小``};` `char``* addr;``int` `cSignature;``int` `cSize;``std::string type;` `Chunk(``char``* chunk_addr) {``addr = chunk_addr;``sChunk* mChunk = (sChunk*)chunk_addr;` `if` `(mChunk->cSignature == 0x001c0001) {``type =` `"StringChunk"``;``}``else` `if` `(mChunk->cSignature == 0x00080180) {``type =` `"ResourceChunk"``;``}``else` `if` `(mChunk->cSignature == 0x00100100) {``type =` `"StartNameSpaceChunk"``;``}``else` `if` `(mChunk->cSignature == 0x00100102) {``type =` `"StartTagChunk"``;``}``else` `if` `(mChunk->cSignature == 0x00100103) {``type =` `"EndTagChunk"``;``}``else` `if` `(mChunk->cSignature == 0x00100101) {``type =` `"EndNameSpaceChunk"``;``}``else` `{``type =` `"Unknown"``;``}``cSize = mChunk->cSize;``};` `Chunk* NextChunk() {``return` `new` `Chunk((addr + cSize));``}``};` |
|-|-|

由此我们可以先对 AndroidManifest 进行一个大致的遍历

| 12345678910111213141516171819 | `int` `main() {``const` `char``* AndroidManifestPath =` `"C:\\Users\\lxz\\source\\repos\\AndroidManifestEditor\\AndroidManifest.xml"``;``char``* mAndroidManifestData = read_file(AndroidManifestPath);``sAndroidManifestHead* mAndroidManifestHead = (sAndroidManifestHead*)mAndroidManifestData;` `std::vector<Chunk*> chunkList;` `Chunk* chunk =` `new` `Chunk(((``char``*)mAndroidManifestHead +` `sizeof``(sAndroidManifestHead)));``while` `(chunk->type !=` `"Unknown"``) {``chunkList.push_back(chunk);``chunk = chunk->NextChunk();``}` `for` `(Chunk* chunk : chunkList) {``printf``(``"%s\n\n"``, chunk->type.c_str());``delete` `chunk;``}``chunkList.clear();``}` |
|-|-|

输出的结果大致为这样，可以完美对应上方的结构图

| 123456789101112131415161718192021 | `stringChunk` `resourceChunk` `startNameSpaceChunk` `startTagChunk` `startTagChunk` `endTagChunk` `startTagChunk` `......` `endTagChunk` `endTagChunk` `EndNameSpaceChunk` |
|-|-|

## StringChunk

StringChunk 的格式就略显复杂了，首先我们先看下 StringChunk 的头部，这部分共计 7 * 4 = 28 个字节的大小

| 123456789 | `struct sStringChunk {``int` `scSignature;` `/``/` `块类型标识``int` `scSize;` `/``/` `块大小``int` `scStringCount;` `/``/` `字符串数量``int` `scStyleCount;` `/``/` `未知``int` `scUNKNOWN;` `/``/` `未知``int` `scStringPoolOffset;` `/``/` `字符串集合的偏移``int` `scStylePoolOffset;` `/``/` `未知``};` |
|-|-|

StringChunk 的头部后面跟着的就是 StringOffsets，这部分区域是的大小为 scStringCount *4，其中每4个字节记录了对应 StringItem 在文件中的的偏移，这里画了一个图可以直观理解一下。

![image-20240118150033561](https://bbs.kanxue.com/upload/attach/202401/950902_YMH2BMZJKB896XF.jpg)

根据上述的分析，故此我们可以定义如下两个类 StringItem、StringChunk

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273 | `class` `StringItem {``public``:``std::wstring wstr;``char``* raw;``int` `size;``StringItem(``char``* addr) {``size = 2 + (*(``wchar_t``*)addr) * 2 + 2;``wstr = std::wstring((``wchar_t``*)(addr + 2));``raw = addr;``}``StringItem(std::wstring v_wstr) {``wstr = v_wstr;``size = 2 + wstr.length() * 2 + 2;``raw = (``char``*)``malloc``(size);``memset``(raw, 0, size);``*(``int``*)raw = wstr.length();``memcpy``(raw + 2, wstr.c_str(), wstr.length() * 2);``}``};` `class` `StringChunk {``public``:``struct` `sStringChunk {``int` `scSignature;` `// 块类型标识``int` `scSize;` `// 块大小``int` `scStringCount;` `// 字符串数量``int` `scStyleCount;` `// 未知``int` `scUNKNOWN;` `// 未知``int` `scStringPoolOffset;` `// 字符串集合的偏移``int` `scStylePoolOffset;` `// 未知``};` `char``* addr;``int` `scSignature;``int` `scSize;``int` `scStringCount;` `int` `scStyleCount;``int` `scUNKNOWN;``int` `scStringPoolOffset;``int` `scStylePoolOffset;``int``* scStringOffsets;` `std::vector<``int``> StringOffset_list;``std::vector<StringItem*> StringItem_list;` `StringChunk(``char``* chunk_addr) {``addr = chunk_addr;` `scSignature = ((sStringChunk*)chunk_addr)->scSignature;``scSize = ((sStringChunk*)chunk_addr)->scSize;``scStringCount = ((sStringChunk*)chunk_addr)->scStringCount;``scStyleCount = ((sStringChunk*)chunk_addr)->scStyleCount;``scUNKNOWN = ((sStringChunk*)chunk_addr)->scUNKNOWN;``scStringPoolOffset = ((sStringChunk*)chunk_addr)->scStringPoolOffset;``scStylePoolOffset = ((sStringChunk*)chunk_addr)->scStylePoolOffset;` `scStringOffsets = (``int``*)(chunk_addr +` `sizeof``(sStringChunk));``for` `(``int` `i = 0; i < scStringCount; i++) {``StringOffset_list.push_back(*(scStringOffsets + i));``StringItem_list.push_back(``new` `StringItem(addr + scStringPoolOffset + *(scStringOffsets + i)));``}``};` `std::wstring get_string(``int` `id) {``return` `(``wchar_t``*)(addr + scStringPoolOffset + *(scStringOffsets + id) + 2);``}` `void` `show_all_string() {``for``(``int` `i = 0; i < scStringCount; i++) {``printf``(``"%S \n"``, get_string(i).c_str());``}``}``};` |
|-|-|

## StartNamespaceChunk

StartNamespaceChunk 中主要的字段为 sncPrefix，可以轻易解析通过 StringChunk 解析

| 1234567891011121314151617181920212223242526272829303132333435 | `class` `StartNamespaceChunk {``public``:``struct` `sStartNamespaceChunk {``int` `scSignature;` `// 块类型标识``int` `scSize;` `// 块大小``int` `sncLineNumber;` `// 该属性在明文中的行数``int` `sncUNKNOWN;` `// 未知``int` `sncPrefix;` `// 字符串索引``int` `sncUri;` `// 字符串 Uri 索引``};` `char``* addr;``int` `scSignature;``int` `scSize;``int` `sncLineNumber;``int` `sncUNKNOWN;``int` `sncPrefix;``int` `sncUri;` `StringChunk*& mStringChunk;` `StartNamespaceChunk(``char``* chunk_addr, StringChunk** vStringChunk):mStringChunk(*vStringChunk) {``addr = chunk_addr;``scSignature = ((sStartNamespaceChunk*)addr)->scSignature;``scSize = ((sStartNamespaceChunk*)addr)->scSize;``sncLineNumber = ((sStartNamespaceChunk*)addr)->sncLineNumber;``sncUNKNOWN = ((sStartNamespaceChunk*)addr)->sncUNKNOWN;``sncPrefix = ((sStartNamespaceChunk*)addr)->sncPrefix;``sncUri = ((sStartNamespaceChunk*)addr)->sncUri;``};` `std::wstring get_string() {``return` `mStringChunk->get_string(sncPrefix);``}``};` |
|-|-|

## EndNameSpaceChunk

和 StartNamespaceChunk 不能说一模一样，只能说完全相同

| 1234567891011121314151617181920212223242526272829303132333435 | `class` `EndNameSpaceChunk {``public``:``struct` `sEndTagChunk {``int` `encSignature;``int` `encSize;``int` `encLineNumber;``int` `encUNKNOWN;``int` `encPrefix;``int` `encUri;``};` `char``* addr;``int` `encSignature;``int` `encSize;``int` `encLineNumber;``int` `encUNKNOWN;``int` `encPrefix;``int` `encUri;` `StringChunk*& mStringChunk;` `EndNameSpaceChunk(``char``* chunk_addr, StringChunk** vStringChunk): mStringChunk(*vStringChunk) {``addr = chunk_addr;``encSignature = ((sEndTagChunk*)addr)->encSignature;``encSize = ((sEndTagChunk*)addr)->encSize;``encLineNumber = ((sEndTagChunk*)addr)->encLineNumber;``encUNKNOWN = ((sEndTagChunk*)addr)->encUNKNOWN;``encPrefix = ((sEndTagChunk*)addr)->encPrefix;``encUri = ((sEndTagChunk*)addr)->encUri;``};` `std::wstring get_string() {``return` `mStringChunk->get_string(encPrefix);``}``};` |
|-|-|

## StartTagChunk

StartTagChunk 也是稍显复杂的一个结构，因为其中包含了另一个结构 AttributeChunk，这里同样给出一个关系结构图

![image-20240118152802749](https://bbs.kanxue.com/upload/attach/202401/950902_UWY5522YZXVJXRS.jpg)

由此我们可以定义如下两个类 AttributeChunk、StartTagChunk

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148 | `class` `AttributeChunk {``public``:``struct` `sAttributeChunk {``int` `acNamespaceUri;` `// 命名空间 Uri 索引``int` `acName;` `// 属性名称(key)的索引``int` `acValueStr;` `// 属性内容(value)的索引（当前类型为字符串时使用该属性）``int` `acType;` `// 属性内容(value)的类型（String、Int、Bool ...）``int` `acData;` `// 属性内容(value)的索引``};` `int` `acNamespaceUri;` `int` `acName;` `int` `acValueStr;` `int` `acType;` `int` `acData;`  `char``* addr;``StringChunk*& mStringChunk;``StartNamespaceChunk*& mStartNamespaceChunk;` `AttributeChunk(``char``* chunk_addr, StringChunk** vStringChunk, StartNamespaceChunk** vStartNamespaceChunk):mStringChunk(*vStringChunk), mStartNamespaceChunk(*vStartNamespaceChunk) {``addr = chunk_addr;``acNamespaceUri = ((sAttributeChunk*)addr)->acNamespaceUri;``acName = ((sAttributeChunk*)addr)->acName;``acValueStr = ((sAttributeChunk*)addr)->acValueStr;``acType = ((sAttributeChunk*)addr)->acType;``acData = ((sAttributeChunk*)addr)->acData;``}` `std::wstring get_srting() {``std::wstring resData = L``""``;``// 当 acNamespaceUri 为 -1 时，命名空间为空``if` `(acNamespaceUri != -1 && acNamespaceUri == mStartNamespaceChunk->sncUri) {``resData = mStartNamespaceChunk->get_string() + L``":"``;``}` `// 属性名称``resData += mStringChunk->get_string(acName);``resData += L``"="``;` `// 属性值的数据类型``if` `((acType >> 24) == 0x10) {``// 整数``resData += L``"\""``;``resData += std::to_wstring(acData);``resData += L``"\""``;``}``else` `if` `((acType >> 24) == 0x3) {``// 字符串``resData += L``"\""``;``resData += mStringChunk->get_string(acValueStr);``resData += L``"\""``;``}``else` `if` `((acType >> 24) == 0x12) {``// 布尔值``if` `(acData == -1) {``resData += L``"\"true\""``;``}``else` `if` `(acData == 0) {``resData += L``"\"false\""``;``}``}``else` `if` `((acType >> 24) == 0x1) {``// 资源ID``std::wstringstream wss;``wss << std::hex << acData;``std::wstring hexString = wss.str();``resData += L``"\"@"``;``resData += std::wstring(wss.str());``resData += L``"\""``;``}``else` `{``// 未识别格式``std::wstringstream wss;``wss << std::hex << acData;``std::wstring hexString = wss.str();``resData += L``"\"[Error]"``;``resData += std::wstring(wss.str());``resData += L``"\""``;``}``return` `resData;``}` `void` `change_value(``int` `value) {``((sAttributeChunk*)addr)->acValueStr = value;``acValueStr = value;``}``};`  `class` `StartTagChunk {``public``:``struct` `sStartTagChunk {``int` `stcSignature;` `// 块类型标识` `int` `stcSize;` `// 块大小``int` `stcLineNumber;` `// 该属性在明文中的行数``int` `stcUNKNOWN;` `// 未知``int` `stcNamespaceUri;` `// 字符串 Uri 索引``int` `stcName;` `// Tag 名称字符串索引``int` `stcFlags;` `// 未知``int` `stcAttributeCount;` `// AttributeChunk 的数量``int` `stcClassAttribute;` `// 未知``};` `char``* addr;``int` `stcSignature;``int` `stcSize;``int` `stcLineNumber;``int` `stcUNKNOWN;``int` `stcNamespaceUri;``int` `stcName;``int` `stcFlags;``int` `stcAttributeCount;``int` `stcClassAttribute;` `EndTagChunk* mEndTagChunk;``StringChunk*& mStringChunk;``StartNamespaceChunk*& mStartNamespaceChunk;``std::vector<AttributeChunk*> mAttributeChunkList;` `StartTagChunk(``char``* chunk_addr, StringChunk** vStringChunk, StartNamespaceChunk** vStartNamespaceChunk)``: mStringChunk(*vStringChunk), mStartNamespaceChunk(*vStartNamespaceChunk){``addr = chunk_addr;``stcSignature = ((sStartTagChunk*)addr)->stcSignature;``stcSize = ((sStartTagChunk*)addr)->stcSize;``stcLineNumber = ((sStartTagChunk*)addr)->stcLineNumber;``stcUNKNOWN = ((sStartTagChunk*)addr)->stcUNKNOWN;``stcName = ((sStartTagChunk*)addr)->stcName;``stcFlags = ((sStartTagChunk*)addr)->stcFlags;``stcAttributeCount = ((sStartTagChunk*)addr)->stcAttributeCount;``stcClassAttribute = ((sStartTagChunk*)addr)->stcClassAttribute;` `for` `(``int` `i = 0; i < stcAttributeCount; i++) {``AttributeChunk* mAttributeChunk =` `new` `AttributeChunk(addr +` `sizeof``(sStartTagChunk) + 20 * i, &mStringChunk, &mStartNamespaceChunk);``mAttributeChunkList.push_back(mAttributeChunk);``}``};` `std::wstring get_string() {``std::wstring resData = L``""``;``for` `(``int` `i = 0; i < mAttributeChunkList.size(); i++) {``resData += mAttributeChunkList[i]->get_srting();``resData += L``"\n"``;``}``return` `resData;``}``};` |
|-|-|

## EndTagChunk

EndTagChunk 的结构就没 StartTagChunk 那么复杂了，可以说简单的很

| 12345678910111213141516171819202122232425262728293031323334 | `class` `EndTagChunk {``public``:``struct` `sEndTagChunk {``int` `etcSignature;` `// 块类型标识``int` `etcSize;` `// 块大小``int` `etcLineNumber;` `// 该属性在明文中的行数``int` `etcUNKNOWN;` `// 未知``int` `etcNamespaceUri;` `// 字符串 Uri 索引``int` `etcName;` `// Tag 名称字符串索引``};` `char``* addr;` `int` `etcSignature;``int` `etcSize;``int` `etcLineNumber;``int` `etcUNKNOWN;``int` `etcNamespaceUri;``int` `etcName;` `StringChunk*& mStringChunk;` `EndTagChunk(``char``* chunk_addr, StringChunk** vStringChunk):mStringChunk(*vStringChunk) {``addr = chunk_addr;``etcSignature = ((sEndTagChunk*)addr)->etcSignature;``etcSize = ((sEndTagChunk*)addr)->etcSize;``etcLineNumber = ((sEndTagChunk*)addr)->etcLineNumber;``etcUNKNOWN = ((sEndTagChunk*)addr)->etcUNKNOWN;``etcName = ((sEndTagChunk*)addr)->etcName;``};` `std::wstring get_string() {``return` `mStringChunk->get_string(etcName);``}``};` |
|-|-|

## 解析小结

自此我们在为借助其他第三方模块的完成了绝大部分 Chunk 的解析，AndroidManifest 也变得不再神秘，那么就简单的 show 一下吧

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374757677787980818283848586878889 | `class` `AndroidManifestEditor {``public``:``struct` `sAndroidManifestHead {``int` `magic;``int` `file_size;``};` `char``* mAndroidManifestData;``sAndroidManifestHead* mAndroidManifestHead;``StringChunk* mStringChunk;``StartNamespaceChunk* mStartNamespaceChunk;``EndNameSpaceChunk* mEndNameSpaceChunk;` `std::vector<Chunk*> chunk_list;``std::vector<StartTagChunk*> mStartTagChunkList;``std::vector<EndTagChunk*> mEndTagChunkList;``std::vector<StartTagChunk*> tStartTagChunkList;` `// 临时列表，用来处理 StartTagChunk 和 EndTagChunk 的对应关系` `AndroidManifestEditor(``const` `char``* AndroidManifestPath) {``mAndroidManifestData = read_file(AndroidManifestPath);``mAndroidManifestHead = (sAndroidManifestHead*)mAndroidManifestData;` `Chunk* chunk =` `new` `Chunk(((``char``*)mAndroidManifestHead +` `sizeof``(sAndroidManifestHead)));``while` `(chunk->type !=` `"Unknown"``) {``if` `(chunk->type ==` `"StartNameSpaceChunk"``) {``mStartNamespaceChunk =` `new` `StartNamespaceChunk(chunk->addr, &mStringChunk);``}``else` `if` `(chunk->type ==` `"StringChunk"``) {``mStringChunk =` `new` `StringChunk(chunk->addr);``}``else` `if` `(chunk->type ==` `"StartTagChunk"``) {``StartTagChunk* mStartTagChunk =` `new` `StartTagChunk(chunk->addr, &mStringChunk, &mStartNamespaceChunk);``mStartTagChunkList.push_back(mStartTagChunk);``tStartTagChunkList.push_back(mStartTagChunk);``}``else` `if` `(chunk->type ==` `"EndTagChunk"``) {``EndTagChunk* mEndTagChunk =` `new` `EndTagChunk(chunk->addr, &mStringChunk);``mEndTagChunkList.push_back(mEndTagChunk);``tStartTagChunkList.back()->mEndTagChunk = mEndTagChunk;``tStartTagChunkList.pop_back();``}``else` `if` `(chunk->type ==` `"EndNameSpaceChunk"``) {``mEndNameSpaceChunk =` `new` `EndNameSpaceChunk(chunk->addr, &mStringChunk);``}``chunk_list.push_back(chunk);``chunk = chunk->NextChunk();``}``}` `void` `show() {``printf``(``"AndroidManifest 魔数\t\t\t\t0x%x\n"``, mAndroidManifestHead->magic);``printf``(``"AndroidManifest 文件大小\t\t\t0x%x\n"``, mAndroidManifestHead->file_size);` `int` `start_tag_id = 0;``int` `end_tag_id = 0;` `for` `(``int` `i = 0; i < chunk_list.size(); i++) {``Chunk* chunk = chunk_list[i];``printf``(``"[%s] \n"``, chunk->type.c_str());``if` `(chunk->type ==` `"StringChunk"``) {``printf``(``"\n"``);``}``else` `if` `(chunk->type ==` `"ResourceChunk"``) {``printf``(``"\n"``);``}``else` `if` `(chunk->type ==` `"StartNameSpaceChunk"``) {``std::wstring wstr = mStartNamespaceChunk->get_string();``printf``(``"%S\n\n"``, wstr.c_str());``}``else` `if` `(chunk->type ==` `"StartTagChunk"``) {``StartTagChunk* mStartTagChunk = mStartTagChunkList[start_tag_id];``printf``(``"%S\n"``, mStartTagChunk->mEndTagChunk->get_string().c_str());``printf``(``"%S\n\n"``, mStartTagChunk->get_string().c_str());``start_tag_id++;``}``else` `if` `(chunk->type ==` `"EndTagChunk"``) {``EndTagChunk* mEndTagChunk = mEndTagChunkList[end_tag_id];``std::wstring wstr = mEndTagChunk->get_string();``end_tag_id++;``printf``(``"%S\n\n"``, wstr.c_str());``}``else` `if` `(chunk->type ==` `"EndNameSpaceChunk"``) {``std::wstring wstr = mEndNameSpaceChunk->get_string();``printf``(``"%S\n\n"``, wstr.c_str());``break``;``}``}``}``};` |
|-|-|

## 添加字符串

现在 AndroidManifest 已经可以任由我们搓扁揉圆了，重新组装 StringChunk 一下，就可以向其中添加任意的字符串

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172 | `class` `StringChunk {``char``* build_raw() {``int` `raw_size =` `sizeof``(sStringChunk);``for` `(``int` `i = 0; i < StringOffset_list.size(); i++) {``raw_size += 4;``}``for` `(``int` `i = 0; i < StringItem_list.size(); i++) {``raw_size += StringItem_list[i]->size;``}` `// 4字节对齐``if` `(raw_size % 4 != 0) {``raw_size += 2;``}` `char``* new_raw = (``char``*)``malloc``(raw_size);``memset``(new_raw, 0, raw_size);``char``* cp_point = new_raw;` `((sStringChunk*)cp_point)->scSignature = scSignature;``((sStringChunk*)cp_point)->scSize = raw_size;``((sStringChunk*)cp_point)->scStringCount = StringItem_list.size();``((sStringChunk*)cp_point)->scStyleCount = scStyleCount;``((sStringChunk*)cp_point)->scUNKNOWN = scUNKNOWN;``((sStringChunk*)cp_point)->scStringPoolOffset = scStringPoolOffset + 4;``((sStringChunk*)cp_point)->scStylePoolOffset = scStylePoolOffset;``cp_point +=` `sizeof``(sStringChunk);` `for` `(``int` `i = 0; i < StringOffset_list.size(); i++) {``*(``int``*)cp_point = StringOffset_list[i];``cp_point += 4;``}` `for` `(``int` `i = 0; i < StringItem_list.size(); i++) {``memcpy``(cp_point, StringItem_list[i]->raw, StringItem_list[i]->size);``cp_point += StringItem_list[i]->size;``}` `return` `new_raw;``}` `StringChunk* add_string(std::wstring wstr) {` `StringItem* mStringItem =` `new` `StringItem(wstr);` `int` `new_StringOffset = StringOffset_list[scStringCount - 1] + StringItem_list[scStringCount - 1]->size;` `StringOffset_list.push_back(new_StringOffset);` `StringItem_list.push_back(mStringItem);` `char``* new_raw = build_raw();` `return` `new` `StringChunk(new_raw);``}` `};` `class` `AndroidManifestEditor {``void` `add_string(std::wstring wstr) {``for` `(``int` `i = 0; i < chunk_list.size(); i++) {``if` `(chunk_list[i]->type ==` `"StringChunk"``) {``StringChunk* newStringChunk = mStringChunk->add_string(wstr);``mAndroidManifestHead->file_size += (newStringChunk->scSize - mStringChunk->scSize);``delete` `mStringChunk;``mStringChunk = newStringChunk;``delete` `chunk_list[i];``chunk_list[i] =` `new` `Chunk(newStringChunk->addr);``}``}``}``};` |
|-|-|

## 修改启动项

当 AndroidManifest 中已存在 ApplicationName 时直接修改其字符串偏移即可

| 1234567891011121314151617181920 | `class` `AndroidManifestEditor {``void` `change_application_name(std::wstring application_name) {``int` `id = mStringChunk->get_id(application_name);``if` `(id == -1) {``add_string(application_name);``id = mStringChunk->get_id(application_name);``}``for` `(``int` `i = 0; i < mStartTagChunkList.size(); i++) {``if` `(mStartTagChunkList[i]->mEndTagChunk->get_string() == L``"application"``) {``std::vector<AttributeChunk*> tAttributeChunkList =` `mStartTagChunkList[i]->mAttributeChunkList;``for` `(``int` `i = 0; i < tAttributeChunkList.size(); i++) {``if` `(tAttributeChunkList[i]->get_srting().find(L``"android:name="``) != std::wstring::npos) {``tAttributeChunkList[i]->change_value(id);``}``}``}``}``}``};` |
|-|-|

## 总结

AndroidManifest 的数据结构总体来讲不算过于复杂，和PE/ELF比算是小巫见大巫了，不过由于搞得不是很精细，后续还需要多做一些测试

## 参考资料

[Android逆向之旅—解析编译之后的AndroidManifest文件格式](http://www.520monkey.com/archives/575)

[AndroidManifest二进制文件格式分析](https://bbs.kanxue.com/thread-194206.htm)

[Android逆向笔记 —— AndroidManifest.xml 文件格式解析](https://zhuanlan.zhihu.com/p/66800574?utm_id=0)

---

# 回复

## 回复 by 你瞒我瞒 (#2)

*2024-1-19 10:34*

太细了

## 回复 by 秋狝 (#3)

*2024-1-19 11:19*

感谢分享

## 回复 by 简单的简单 (#4)

*2024-1-19 11:20*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  太细了
>
>

因为我真的在试图教会你 ![image](https://bbs.kanxue.com/view/img/face/51.gif)

## 回复 by Amun (#5)

*2024-1-19 12:14*

看得出来这是逆向出来，没有细看 AOSP 的相关源码，有一些情况没有覆盖到，还有改进空间。

## 回复 by 你瞒我瞒 (#6)

*2024-1-23 09:21*

>
> [简单的简单](https://bbs.kanxue.com/user-950902.htm)
>
>  因为我真的在试图教会你 [em_51]
>
>

现在有部分app试图在破坏某个部分但是不影响app安装，影响文件的解析来规避上架检测，或者让反编译工具反编译失效![image](https://bbs.kanxue.com/view/img/face/2.gif)

## 回复 by palkiver (#7)

*2024-1-24 10:51*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  现在有部分app试图在破坏某个部分但是不影响app安装，影响文件的解析来规避上架检测，或者让反编译工具反编译失效[em_2]
>
>

现在的APP为了切支付也是煞费苦心

## 回复 by 阿耿 (#8)

*2025-5-6 17:52*

解析这个文件最主要的就是变长和对齐，这些坑都趟过，其他没啥
