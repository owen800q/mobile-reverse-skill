---
title: '[原创]解决Il2cppapi混淆，通杀DumpUnityCs文件'
url: https://bbs.kanxue.com/thread-289623.htm
tid: 289623
author: rettozero
date: '2025-12-30'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T15:16:26+08:00'
replies: 110
---

# 解决Il2cppapi混淆，DumpUnityCs文件

## 0x0 前言

没想到上一篇文章有这么多师傅观看，因此有了这一篇。

上一篇讲解了纯静态解决global-metadata.dat的各类问题，并且提到了利用il2cpp_api（未混淆）动态dump CS文件这一方法。

也就是下方这个项目。

https://github.com/Perfare/Zygisk-Il2CppDumper

所以这一篇就分享一下我解决il2cpp_api混淆的解决方法。

## 0x1 了解Dumper原理

通过源码了解Zygisk-Il2CppDumper做了什么，因代码过长，所以后续仍旧截取片段。

打开il2cpp_dump.cpp，找到il2cpp_dump函数。

我们可以看到几个由il2cpp命名的函数，il2cpp_domain_get il2cpp_domain_get_assemblies il2cpp_assembly_get_image等等。

| 12345678910 | `void il2cpp_dump(const char` `*``outDir) {``LOGI(``"dumping..."``);``size_t size;``auto domain` `=` `il2cpp_domain_get();``auto assemblies` `=` `il2cpp_domain_get_assemblies(domain, &size);``std::stringstream imageOutput;``for` `(``int` `i` `=` `0``; i < size;` `+``+``i) {``auto image` `=` `il2cpp_assembly_get_image(assemblies[i]);``imageOutput <<` `"// Image "` `<< i <<` `": "` `<< il2cpp_image_get_name(image) <<` `"\n"``;``}` |
|-|-|

索引il2cpp_domain_get查看它的实现，会来到il2cpp-api-functions.h。

会发现整个头文件是一个规范由DO_API宏定义的函数。

| 1234 | `/``/` `domain``DO_API(Il2CppDomain``*``, il2cpp_domain_get, ());``DO_API(const Il2CppAssembly``*``, il2cpp_domain_assembly_open, (Il2CppDomain` `*` `domain, const char``*` `name));``DO_API(const Il2CppAssembly``*``*``, il2cpp_domain_get_assemblies, (const Il2CppDomain` `*` `domain, size_t` `*` `size));` |
|-|-|

跳转到DO_API看看它都做了什么。

r：返回的类型

n：函数的名字

p：指针地址

| 1234567891011121314151617181920 | `#define DO_API(r, n, p) r (*n) p` `#include "il2cpp-api-functions.h"` `#undef DO_API` `static uint64_t il2cpp_base` `=` `0``;` `void init_il2cpp_api(void` `*``handle) {``#define DO_API(r, n, p) {                      \``n` `=` `(r (``*``) p)xdl_sym(handle,` `#n, nullptr); \``if``(!n) {                                   \``LOGW(``"api not found %s"``,` `#n);          \``}                                          \``}` `#include "il2cpp-api-functions.h"` `#undef DO_API``}` |
|-|-|

通过xdl_sym去获取符号名n的地址并定义成返回类型为r的函数。

DO_API宏遍历了所有的API声明，并为每个API解析函数地址。

既然如此，我们打开任意一个il2cpp.so来查看一下。
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_RD2DX9X6BH9GWKE.webp)
打开导出表，搜索il2cpp_，可以看见大量的函数名。

而这些函数有什么作用呢？

我们截取dump_method，cs文件中的方法是怎么导出的。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162 | `std::string dump_method(Il2CppClass` `*``klass) {``std::stringstream outPut;``outPut <<` `"\n\t// Methods\n"``;``void` `*``iter` `=` `nullptr;``while` `(auto method` `=` `il2cpp_class_get_methods(klass, &``iter``)) {``/``/``TODO attribute``if` `(method``-``>methodPointer) {``outPut <<` `"\t// RVA: 0x"``;``outPut << std::``hex` `<< (uint64_t) method``-``>methodPointer` `-` `il2cpp_base;``outPut <<` `" VA: 0x"``;``outPut << std::``hex` `<< (uint64_t) method``-``>methodPointer;``}` `else` `{``outPut <<` `"\t// RVA: 0x VA: 0x0"``;``}``/``*``if` `(method``-``>slot !``=` `65535``) {``outPut <<` `" Slot: "` `<< std::dec << method``-``>slot;``}``*``/``outPut <<` `"\n\t"``;``uint32_t iflags` `=` `0``;``auto flags` `=` `il2cpp_method_get_flags(method, &iflags);``outPut << get_method_modifier(flags);``/``/``TODO genericContainerIndex``auto return_type` `=` `il2cpp_method_get_return_type(method);``if` `(_il2cpp_type_is_byref(return_type)) {``outPut <<` `"ref "``;``}``auto return_class` `=` `il2cpp_class_from_type(return_type);``outPut << il2cpp_class_get_name(return_class) <<` `" "` `<< il2cpp_method_get_name(method)``<<` `"("``;``auto param_count` `=` `il2cpp_method_get_param_count(method);``for` `(``int` `i` `=` `0``; i < param_count;` `+``+``i) {``auto param` `=` `il2cpp_method_get_param(method, i);``auto attrs` `=` `param``-``>attrs;``if` `(_il2cpp_type_is_byref(param)) {``if` `(attrs & PARAM_ATTRIBUTE_OUT && !(attrs & PARAM_ATTRIBUTE_IN)) {``outPut <<` `"out "``;``}` `else` `if` `(attrs & PARAM_ATTRIBUTE_IN && !(attrs & PARAM_ATTRIBUTE_OUT)) {``outPut <<` `"in "``;``}` `else` `{``outPut <<` `"ref "``;``}``}` `else` `{``if` `(attrs & PARAM_ATTRIBUTE_IN) {``outPut <<` `"[In] "``;``}``if` `(attrs & PARAM_ATTRIBUTE_OUT) {``outPut <<` `"[Out] "``;``}``}``auto parameter_class` `=` `il2cpp_class_from_type(param);``outPut << il2cpp_class_get_name(parameter_class) <<` `" "``<< il2cpp_method_get_param_name(method, i);``outPut <<` `", "``;``}``if` `(param_count >` `0``) {``outPut.seekp(``-``2``, outPut.cur);``}``outPut <<` `") { }\n"``;``/``/``TODO GenericInstMethod``}``return` `outPut.``str``();``}` |
|-|-|

所以我们可以知道unity底层就是通过这些api去获取各类class field等。

因此我们也可以通过这些api去获取。

## 0x2 il2cpp_api混淆例子

拿出例子，观看混淆后的样子。
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_N4R35ZN59F836WQ.webp)

我们去导出表搜索il2cpp字符串没有一个相对应的api函数，函数名被混淆为长度11的乱序字符。

## 0x3 解决思路发散

1.特征码。

2.api的顺序是否规律。

3.找到游戏上个未混淆的版本，进行对比。

这是作者最先想到，并且尝试的方法，先说第一种。

| 1234567891011121314 | `.text:``00000000019047F8``.text:``00000000019047F8``.text:``00000000019047F8`                 `EXPORT YMqyW_Qt_Ld``.text:``00000000019047F8` `YMqyW_Qt_Ld                             ; DATA XREF: LOAD:``0000000000007578``↑o``.text:``00000000019047F8` `; __unwind {``.text:``00000000019047F8`                 `RET``.text:``00000000019047F8` `; }` `/``/` `starts at` `19047F8``.text:``00000000019047F8` `; End of function YMqyW_Qt_Ld``.text:``00000000019047F8``.text:``00000000019047FC`                 `EXPORT yG_WSutBToN``.text:``00000000019047FC` `yG_WSutBToN                             ; DATA XREF: LOAD:``0000000000003B88``↑o``.text:``00000000019047FC` `; __unwind {``.text:``00000000019047FC`                 `RET``.text:``00000000019047FC` `; }` `/``/` `starts at` `19047FC` |
|-|-|

看到以上两个函数，它们仅仅只有ret，除了这两个还有其余许多汇编一摸一样的函数。因此特征码是不行的。

第二种api的顺序是否规律。

这里作者直接给出答案，大致是规律的。例如，如果你确认某个混淆函数是il2cpp_property_get_name，那么它的下一个混淆函数大概率就是il2cpp_property_get_get_method，以此类推。

| 1234567891011121314151617181920212223 | `.text:``0000000001279314`                 `EXPORT il2cpp_property_get_name``.text:``0000000001279314` `il2cpp_property_get_name                ; DATA XREF: LOAD:``00000000000048F0``↑o``.text:``0000000001279314` `; __unwind {``.text:``0000000001279314`                 `B               il2cpp_field_get_type_0``.text:``0000000001279318``.text:``0000000001279318`                 `EXPORT il2cpp_property_get_get_method``.text:``0000000001279318` `il2cpp_property_get_get_method          ; DATA XREF: LOAD:``0000000000005178``↑o``.text:``0000000001279318` `; __unwind {``.text:``0000000001279318`                 `B               il2cpp_class_get_name_0``.text:``000000000127931C`                 `EXPORT il2cpp_property_get_set_method``.text:``000000000127931C` `il2cpp_property_get_set_method          ; DATA XREF: LOAD:``000000000000A788``↑o``.text:``000000000127931C` `; __unwind {``.text:``000000000127931C`                 `B               il2cpp_class_get_namespace_0``.text:``0000000001279320``.text:``0000000001279320`                 `EXPORT il2cpp_property_get_parent``.text:``0000000001279320` `il2cpp_property_get_parent              ; DATA XREF: LOAD:``000000000000E0E8``↑o``.text:``0000000001279320` `; __unwind {``.text:``0000000001279320`                 `B               il2cpp_assembly_get_image_0``.text:``0000000001279320` `; }` `/``/` `starts at` `1279320``.text:``0000000001279328`                 `EXPORT il2cpp_object_get_class``.text:``0000000001279328` `il2cpp_object_get_class                 ; DATA XREF: LOAD:``000000000000B928``↑o``.text:``0000000001279328` `; __unwind {``.text:``0000000001279328`                 `B               il2cpp_assembly_get_image_0` |
|-|-|

这个方法的隐患就是如果有变动了，你也不确定，当某个重要api地址错误时，程序会崩溃。

第三个方法找到游戏上个未混淆的版本，进行对比。

这个方法当版本更新越接近越好用。

所以将以上三个方法一起搭配使用，应该是最美味的。

## 0x4 利用libunity.so

不知道你否注意到过这个so呢？

任意将这个libunity.so名字丢入ai，说明它的作用。

它应该都会给你诸如此类的回答。

| 12345678 | `1.` `引擎运行时核心``包含 Unity 游戏引擎的核心功能代码` `处理游戏循环、内存管理、渲染管线等基础系统` `提供 Unity C``# 脚本与底层原生代码之间的桥梁` `包含游戏的核心逻辑（特别是使用 IL2CPP 时）` |
|-|-|

我们可以特别注意到这两行回答。

提供 Unity C# 脚本与底层原生代码之间的桥梁和包含游戏的核心逻辑（特别是使用 IL2CPP 时）。

我们任意打开一个未混淆il2cpp_api包的libunity.so，发现导出表也没有跟il2cpp相关的函数啊？

那试试字符串呢？
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_4NTRYMEB3HRVFH7.webp)

我们赶紧索引字符串，看看谁在调用它们。

| 123456789101112131415161718192021222324252627282930313233 | `result` `=` `sub_2931EC(a1,` `0``);``qword_122FDC0` `=` `result;``if` `( result )``{``off_122F698` `=` `sub_2933C8(result,` `"il2cpp_init"``,` `0``);``if` `( off_122F698 )``{``v2` `=` `1``;``}``else``{``sub_819C78(``"il2cpp: function il2cpp_init not found\n"``);``v2` `=` `0``;``}``qword_122F6A0` `=` `sub_2933C8(qword_122FDC0,` `"il2cpp_init_utf16"``,` `0``);``if` `( !qword_122F6A0 )``{``sub_819C78(``"il2cpp: function il2cpp_init_utf16 not found\n"``);``v2` `=` `0``;``}``off_122F6A8` `=` `sub_2933C8(qword_122FDC0,` `"il2cpp_shutdown"``,` `0``);``if` `( !off_122F6A8 )``{``sub_819C78(``"il2cpp: function il2cpp_shutdown not found\n"``);``v2` `=` `0``;``}``off_122F6B0` `=` `sub_2933C8(qword_122FDC0,` `"il2cpp_set_config_dir"``,` `0``);``if` `( !off_122F6B0 )``{``sub_819C78(``"il2cpp: function il2cpp_set_config_dir not found\n"``);``v2` `=` `0``;``}``off_122F6B8` `=` `sub_2933C8(qword_122FDC0,` `"il2cpp_set_data_dir"``,` `0``);` |
|-|-|

可以发现所有的il2cpp_api相关的字符串都只索引了这一个函数，并且观察规律，这些api是按照一定顺序进行初始化的。

按照这个思路，马萨卡？难道说？赶紧打开混淆的libunity.so

| 12345678910111213141516171819202122232425262728 | `if` `( result )``{``v2` `=` `sub_557770(result,` `"GdnPlVZEdxf"``,` `0``);``qword_119E3E8` `=` `v2;``if` `( !v2 )``sub_B5BB5C(&unk_144CDD);``v3` `=` `v2 !``=` `0``;``qword_119E3F0` `=` `sub_557770(qword_119EB38,` `"xeESwBbuab_"``,` `0``);``if` `( !qword_119E3F0 )``{``sub_B5BB5C(&unk_FA8EA);``v3` `=` `0``;``}``off_119E3F8` `=` `sub_557770(qword_119EB38,` `"nKyghkcwxJe"``,` `0``);``if` `( !off_119E3F8 )``{``sub_B5BB5C(&unk_1372DB);``v3` `=` `0``;``}``qword_119E400` `=` `sub_557770(qword_119EB38,` `"XiKOzOdJsYE"``,` `0``);``if` `( !qword_119E400 )``{``sub_B5BB5C(&unk_FF214);``v3` `=` `0``;``}``qword_119E408` `=` `sub_557770(qword_119EB38,` `"AbJEjDq_zgF"``,` `0``);``if` `( !qword_119E408 )``{` |
|-|-|

ohhhhhhhhhh,通过比较我们可以知道GdnPlVZEdxf对应的就是il2cpp_init，接着往下的函数都是一样。

## 0x5 懒狗出世（编写脚本，快速映射）

众所周知，我是一个懒狗。

既然有这么好用的映照函数，当然是赶紧编写一些idapython脚本做一套映射表。

1.获取il2cpp_api对照表

| 1234 | `ADRL            X1, aGdnplvzedxf ;` `"GdnPlVZEdxf"``ADRP            X1,` `#aXeeswbbuab@PAGE ; "xeESwBbuab_"``ADRL            X1, aNkyghkcwxje ;` `"nKyghkcwxJe"``ADRL            X1, aXikozodjsye ;` `"XiKOzOdJsYE"` |
|-|-|

通过汇编观察规律，字符串不是在ADRL就是ADRP语句上。

众所周知，我是一个懒狗，懒狗就要有懒狗的样子！

我都发现这个规律了，凭什么还要写脚本？派出AI大将。
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_UVKDXPJHM8JQG95.webp)

一通批评ai后，哐当！我们得到一个ida插件（顺便让它帮忙写了一个ui，不然每次都要点加载脚本，累死哥们了），运行一下DumpIl2cppFuction.py

| 12345678910111213141516171819202122 | `il2cpp_functions` `=` `[``'il2cpp_init'``,``'il2cpp_init_utf16'``,``'il2cpp_shutdown'``,``'il2cpp_set_config_dir'``,``'il2cpp_set_data_dir'``,``'il2cpp_set_temp_dir'``,``'il2cpp_set_commandline_arguments'``,``'il2cpp_set_commandline_arguments_utf16'``,``'il2cpp_set_config_utf16'``,``'il2cpp_set_config'``,``'il2cpp_set_memory_callbacks'``,``'il2cpp_get_corlib'``,``'il2cpp_add_internal_call'``,``'il2cpp_resolve_icall'``,``'il2cpp_alloc'``,``'il2cpp_free'``,``'il2cpp_array_class_get'``,``'il2cpp_array_length'``,``'il2cpp_array_get_byte_length'``,``'il2cpp_array_new'``,``'il2cpp_array_new_specific'``,` |
|-|-|

得到了一个按照正确顺序的il2cpp函数表。注意unity的版本不同，这里的函数表也不一样，大家做游戏的时候，可以收集一下各个版本的il2cpp_functions表，其实也没几个版本差距特别大，也就4-5个。

| 12345678910111213 | `function_addresses` `=` `{``'inbBTWllAfE'``:` `0x019048A8``,``'moZkrEOxnod'``:` `0x01904948``,``'UgeTybrtfli'``:` `0x01903FE0``,``'bETTzCiChhf'``:` `0x01904800``,``'dNQnXjbmJKE'``:` `0x0190473C``,``'vkWLZpdNfvo'``:` `0x01903FF4``,``'lQyvUscAGEB'``:` `0x01904010``,``'rpORpEUDUUG'``:` `0x0190496C``,``'DDuIaqSaJPb'``:` `0x01904940``,``'SCpPaWMGYuU'``:` `0x019046D4``,``'JerpDnxOVno'``:` `0x01903F68``,``'iL_PocEDOUL'``:` `0x019046F4``,` |
|-|-|

顺手再dump一个混淆的表。

| 12345678910111213141516171819202122232425 | `il2cpp函数映射表``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``分析函数:` `0x59D26C` `-` `0x59FEA0``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=` `1.` `il2cpp_init` `-``> GdnPlVZEdxf     (``0x01903EAC``)``2.` `il2cpp_init_utf16` `-``> nKyghkcwxJe     (``0x01903F5C``)``3.` `il2cpp_shutdown` `-``> XiKOzOdJsYE     (``0x01903F60``)``4.` `il2cpp_set_config_dir` `-``> AbJEjDq_zgF     (``0x01903F64``)``5.` `il2cpp_set_data_dir` `-``> JerpDnxOVno     (``0x01903F68``)``6.` `il2cpp_set_temp_dir` `-``> NkyFkhKjXDP     (``0x01903F6C``)``7.` `il2cpp_set_commandline_arguments` `-``> UfNXctJaZQO     (``0x01903F7C``)``8.` `il2cpp_set_commandline_arguments_utf16` `-``> MJdRIVcUmWY     (``0x01903F8C``)``9.` `il2cpp_set_config_utf16` `-``> igjWeppGXcn     (``0x01903F90``)``10.` `il2cpp_set_config` `-``> NPuDEZOXejP     (``0x01903F94``)``11.` `il2cpp_set_memory_callbacks` `-``> EAFNJ_FIJYK     (``0x01903F98``)``12.` `il2cpp_memory_pool_set_region_size` `-``> gdwVBiglIWC     (``0x01903F9C``)``13.` `il2cpp_memory_pool_get_region_size` `-``> NGbgctWOdID     (``0x01903FA0``)``14.` `il2cpp_get_corlib` `-``> kdoNiyv_Qhd     (``0x01903FA4``)``15.` `il2cpp_add_internal_call` `-``> UWZdnspJd_I     (``0x01903FA8``)``16.` `il2cpp_resolve_icall` `-``> KaCKWSaBPCP     (``0x01903FAC``)``17.` `il2cpp_alloc` `-``> PRfrmVSTTrU     (``0x01903FB0``)``18.` `il2cpp_free` `-``> LAiuXZUDdNh     (``0x01903FB4``)``19.` `il2cpp_array_class_get` `-``> QRIjzueyGZT     (``0x01903FB8``)``20.` `il2cpp_array_length` `-``> jzmYhGGuWvJ     (``0x01903FBC``)` |
|-|-|

最后再映射成一个表。

## 0x6 修改Zygisk-Il2CppDump项目

怎么将我们的混淆函数名和代码中的函数名映射上呢？

你问我？我怎么知道？

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556 | `/``/` `简单版混淆API映射` `-` `最小修改版本` `/``/` `1.` `在文件顶部添加映射表``static std::unordered_map<std::string, std::string> g_apiNameMapping` `=` `{``{``"il2cpp_init"``,` `"EEHqqEpNwom"``},``{``"il2cpp_init_utf16"``,` `"RZsQLagwTlx"``},``{``"il2cpp_shutdown"``,` `"FPBuKAnxJnW"``},``{``"il2cpp_set_config_dir"``,` `"gvRjOOFEQoD"``},``{``"il2cpp_class_get_methods"``,` `"yYjgwGcrPwX"``},``{``"il2cpp_class_get_field_from_name"``,` `"AXSPXatQQDi"``},``{``"il2cpp_class_from_name"``,` `"FYAdRLtSOwT"``},``{``"il2cpp_domain_get"``,` `"olpitYGBqDf"``},``{``"il2cpp_object_new"``,` `"rmxDRModSbB"``},``{``"il2cpp_runtime_invoke"``,` `"GMAl_ZIdVoF"``},``{``"il2cpp_string_new"``,` `"MzuQxUkMQUQ"``},``{``"il2cpp_type_get_name"``,` `"mZIXSsmWGNY"``},``{``"il2cpp_method_get_name"``,` `"UwPOCbVQdna"``}``/``/` `根据需要添加更多映射...``};` `/``/` `获取混淆后的API名称``const char``*` `get_obfuscated_name(const char``*` `original_name) {``auto it` `=` `g_apiNameMapping.find(original_name);``return` `(it !``=` `g_apiNameMapping.end()) ? it``-``>second.c_str() : original_name;``}` `/``/` `2.` `修改你的 init_il2cpp_api 函数``void init_il2cpp_api(void` `*``handle) {``#define DO_API(r, n, p) {                                          \``const char``*` `symbol_name` `=` `get_obfuscated_name(``#n);             \``n` `=` `(r (``*``) p)xdl_sym(handle, symbol_name, nullptr);            \``if``(!n) {                                                       \``LOGW(``"api not found %s (tried: %s)"``,` `#n, symbol_name);     \``/``*` `回退到原始名称` `*``/`                                       `\``n` `=` `(r (``*``) p)xdl_sym(handle,` `#n, nullptr);                 \``if``(!n) {                                                   \``LOGE(``"api not found %s"``,` `#n);                          \``}                                                          \``}                                                              \``}` `#include "il2cpp-api-functions.h"` `#undef DO_API``}` `/``*``使用方法：``1.` `将这个代码片段复制到你现有的文件中``2.` `确保包含了必要的头文件：``-` `#include <unordered_map>``-` `#include <string>``3.` `编译测试即可` `这样最小的修改就能让Dumper支持混淆API了！``*``/` |
|-|-|

肯定是继续让ai写啊！

后续可以让dump脚本映射成{"il2cpp_init", "EEHqqEpNwom"},的样式。但是我太懒了，连让ai修改一下的动力都没有了...

最后在game.h填上你最爱的游戏包名，编译导入手机面具加载模块即可。

| 1 | `#define GamePackageName "com.game.packagename"` |
|-|-|

## 0x7 总结

额...看了一眼上一篇文章，有师傅在底下问我问题，然后我记得我好像扣了几百字回复了，然后就...发现竟然没有发出！！！

然后就不管了...一想到要重新扣那么多字就心累~

因此，我在这里留一个球球好了，OTYyNTY0ODM5。

如果添加第一时间没通过...本人虽然真得很懒，但那一定是在睡觉。

还有如果没有帮助到师傅你完成通杀的话...我是个标题党哈哈哈哈

最后，临近元旦，祝师傅们一定要多笑，苹果肌尽量不要保持扁平，我知道这很困难！但这是命令！

毕竟，搞技术身体最重要！

嗯@-@

---

# 回复

## 回复 by 签个到 (#2)

*2025-12-30 23:49*

666

## 回复 by wx_Huber Barrientos (#3)

*2025-12-31 08:57*

为你点赞！

## 回复 by huangjw (#4)

*2025-12-31 09:21*

火钳刘明

## 回复 by New对象处 (#5)

*2025-12-31 10:01*

好文

## 回复 by mb_ldbucrik (#6)

*2025-12-31 10:53*

yyds

## 回复 by vmoveq (#7)

*2025-12-31 10:53*

qword_122F6A0 = sub_2933C8(qword_122FDC0, "il2cpp_init_utf16", 0);
   if ( !qword_122F6A0 )
   {
     sub_819C78("il2cpp: function il2cpp_init_utf16 not found\n");
     v2 = 0;
   }
何必这么麻烦，直接调用这个sub_2933C8不就拿到api了？

## 回复 by kingking888 (#8)

*2025-12-31 13:40*

666

## 回复 by 5h3r10(l{ (#9)

*2025-12-31 17:12*

666

## 回复 by mb_uvyukvot (#10)

*2025-12-31 17:50*

666

## 回复 by mb_rqlksylg (#11)

*2025-12-31 20:44*

非常好

## 回复 by wx_宇克鴻 (#12)

*2026-1-1 01:10*

66666

## 回复 by SomeMx (#13)

*2026-1-1 02:44*

过来瞧瞧

## 回复 by 空处 (#14)

*2026-1-1 09:17*

学习了

## 回复 by mb_dmryhnwz (#15)

*2026-1-1 12:23*

7676

## 回复 by mb_qimctavn (#16)

*2026-1-1 12:47*

6

## 回复 by wx_1_659 (#17)

*2026-1-1 16:04*

666

## 回复 by zylyy (#18)

*2026-1-2 11:45*

666

## 回复 by supyuan (#19)

*2026-1-2 12:33*

666

## 回复 by foryrrrr (#20)

*2026-1-2 13:42*

666

## 回复 by mb_wtskxwnr (#21)

*2026-1-2 14:45*

666

## 回复 by wx_荣仔 (#22)

*2026-1-2 15:28*

好东西。学习了。

## 回复 by 希梦☆奈何 (#23)

*2026-1-2 16:06*

666

## 回复 by XCicada (#24)

*2026-1-2 19:21*

666

## 回复 by mb_urzqsoer (#25)

*2026-1-3 04:25*

666666666666666666666

## 回复 by Imxz (#26)

*2026-1-3 09:02*

tql

## 回复 by Imxz (#27)

*2026-1-3 09:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  vmoveq](https://bbs.kanxue.com/user-785870.htm)
>
>  qword_122F6A0 = sub_2933C8(qword_122FDC0, "il2cpp_init_utf16", 0);
>  if ( !qword_122F6A ...
>
>

记得 这个函数 sub_2933C8 里不是 调用 dlsym 获取嘛? 本身导出函数名被混淆了, 调用这个没用吧?

## 回复 by mb_nggigxxl (#28)

*2026-1-3 11:19*

6666

## 回复 by mb_4nrpVMxJ (#29)

*2026-1-3 13:47*

6666

## 回复 by wx_ ╰☆L玄V0心E☆╮ (#30)

*2026-1-3 21:57*

666666666

## 回复 by vmoveq (#31)

*2026-1-3 21:58*

>
> [Imxz](https://bbs.kanxue.com/user-656334.htm)
>
>  记得 这个函数 sub_2933C8 里不是 调用 dlsym 获取嘛? 本身导出函数名被混淆了, 调用这个没用吧?
>
>

导出函数名被混淆  关  字符串 什么事，f5铁一样的事实，调用它就行

## 回复 by GEKEZYX (#32)

*2026-1-4 10:40*

666

## 回复 by xinhu (#33)

*2026-1-4 14:09*

333333

## 回复 by wx_范迪塞尔 (#34)

*2026-1-4 14:25*

666666666666666

## 回复 by 4Chan (#35)

*2026-1-4 16:20*

666666666666666666666

## 回复 by Imxz (#36)

*2026-1-5 09:09*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  vmoveq](https://bbs.kanxue.com/user-785870.htm)
>
>  导出函数名被混淆 关 字符串 什么事，f5铁一样的事实，调用它就行
>
>

有没有可能 F5 看到的 导出函数 在 libunity.so 中 对应的 字符串 也是混淆的?

## 回复 by Imxz (#37)

*2026-1-5 09:12*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  vmoveq](https://bbs.kanxue.com/user-785870.htm)
>
>  导出函数名被混淆 关 字符串 什么事，f5铁一样的事实，调用它就行
>
>

qword_122F6A0 = sub_2933C8(qword_122FDC0, "il2cpp_init_utf16", 0);
if ( !qword_122F6A0 )
{
        sub_819C78("il2cpp: function il2cpp_init_utf16 not found\n");
        v2 = 0;
}
你F5看到的是这个
混淆处理后 变成了
qword_122F6A0 = sub_2933C8(qword_122FDC0, "RZsQLagwTlx", 0);
if ( !qword_122F6A0 )
{
        sub_819C78("il2cpp: function RZsQLagwTlx not found\n");
        v2 = 0;
}
这个你hook sub_2933C8 这个函数 依旧是混淆的
连sub_819C78 这个函数里的都是混淆的

## 回复 by vmoveq (#38)

*2026-1-5 10:35*

>
> [Imxz](https://bbs.kanxue.com/user-656334.htm)
>
>  qword_122F6A0 = sub_2933C8(qword_122FDC0, "il2cpp_init_utf16", 0);
> if ( !qword_122F6A0 )
>  ...
>
>

有没有可能这只是你的妄想

## 回复 by 零_721409 (#39)

*2026-1-5 14:39*

666

## 回复 by RayTracing (#40)

*2026-1-5 15:02*

666

## 回复 by mb_mesldbiy (#41)

*2026-1-6 11:15*

666666

## 回复 by flyingx (#42)

*2026-1-6 13:47*

学习了

## 回复 by Imxz (#43)

*2026-1-6 14:19*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  vmoveq](https://bbs.kanxue.com/user-785870.htm)
>
>  有没有可能这只是你的妄想
>
>

算了 你说是就是吧 懒得挣了

## 回复 by mb_euhyowpw (#44)

*2026-1-6 18:55*

66

## 回复 by wx_123_100 (#45)

*2026-1-13 21:57*

感谢老师傅分享！！！

## 回复 by mb_dtdhdols (#46)

*2026-1-14 04:35*

这是真牛

## 回复 by mb_vgbsclvi (#47)

*2026-1-17 01:41*

666

## 回复 by 猫毛茂 (#48)

*2026-1-18 15:28*

666

## 回复 by mb_xiycxveg (#49)

*2026-1-18 23:01*

666

## 回复 by 哆啦H梦 (#50)

*2026-1-19 00:10*

看看

## 回复 by 恋一世的爱 (#51)

*2026-1-22 23:04*

楼主，我遇到一个问题，使用Zygisk-Il2CppDumper在内存中dump，也dump不出来，提示
il2cpp_handle: 0x6df39c8c30
api not found il2cpp_init
api not found il2cpp_init_utf16
api not found il2cpp_shutdown
api not found il2cpp_set_config_dir
...
api not found il2cpp_set_data_dir
api not found il2cpp_set_default_thread_affinity
Failed to initialize il2cpp api.
这种情况，该如何解决

## 回复 by wx_豪_522545 (#52)

*2026-1-23 00:04*

6666

## 回复 by mb_yvhnqhmk (#53)

*2026-1-23 01:02*

6666

## 回复 by 恋一世的爱 (#54)

*2026-1-23 05:34*

在混淆的unity.so里面怎么能快速定位到这个这个函数块
if ( result )
  {
    v2 = sub_557770(result, "GdnPlVZEdxf", 0);
    qword_119E3E8 = v2;
    if ( !v2 )
      sub_B5BB5C(&unk_144CDD);
    v3 = v2 != 0;
    qword_119E3F0 = sub_557770(qword_119EB38, "xeESwBbuab_", 0);
    if ( !qword_119E3F0 )
    {
      sub_B5BB5C(&unk_FA8EA);
      v3 = 0;
    }
    off_119E3F8 = sub_557770(qword_119EB38, "nKyghkcwxJe", 0);
    if ( !off_119E3F8 )
    {
      sub_B5BB5C(&unk_1372DB);
      v3 = 0;
    }
    qword_119E400 = sub_557770(qword_119EB38, "XiKOzOdJsYE", 0);
    if ( !qword_119E400 )
    {
      sub_B5BB5C(&unk_FF214);
      v3 = 0;
    }
    qword_119E408 = sub_557770(qword_119EB38, "AbJEjDq_zgF", 0);
    if ( !qword_119E408 )
    {

## 回复 by uni7corn (#55)

*2026-1-26 17:48*

感谢分享

## 回复 by wx_友情 (#56)

*2026-1-27 00:32*

[原创]解决Il2cppapi混淆，通杀DumpUnityCs文件-Android安全-看雪安全社区｜专业技术交流与安全研究论坛

## 回复 by yikuaiyingbi (#57)

*2026-1-28 11:54*

11

## 回复 by 我是小奥 (#58)

*2026-1-29 22:33*

666

## 回复 by 夜惜风雨 (#59)

*2026-1-30 09:51*

6666666666666666666

## 回复 by mb_kxnxllvw (#60)

*2026-1-31 18:19*

感谢大佬分享

## 回复 by 哥倫布 (#61)

*2026-2-1 09:07*

666

## 回复 by mb_uruwpimj (#62)

*2026-2-6 01:10*

学习学习

## 回复 by hekes (#63)

*2026-2-7 09:37*

666666666

## 回复 by S_602205 (#64)

*2026-2-24 16:54*

666

## 回复 by Zepp7289 (#65)

*2026-2-24 16:57*

tql

## 回复 by 努力8点 (#66)

*2026-2-28 10:56*

好东西。学习了。

## 回复 by mb_ntpqnzrm (#67)

*2026-2-28 11:46*

6666

## 回复 by mb_irhdtnzm (#68)

*2026-3-2 09:46*

1

## 回复 by xifgg (#69)

*2026-3-5 12:09*

111

## 回复 by 漆黑火焰魔法使 (#70)

*2026-3-5 12:33*

感谢分享，学习了。

## 回复 by mb_zdoxkucm (#71)

*2026-3-5 15:24*

看看隐藏

## 回复 by k4y0z (#72)

*2026-3-5 15:24*

666

## 回复 by 小尘0000 (#73)

*2026-3-6 18:24*

666

## 回复 by mb_jzyasacd (#74)

*2026-3-8 08:28*

666

## 回复 by git_107370xcmore (#75)

*2026-3-16 14:05*

666

## 回复 by xxRea (#76)

*2026-3-16 19:13*

都是老师傅

## 回复 by 大白_460230 (#77)

*2026-3-21 22:40*

66666666666666666666

## 回复 by mb_vfhjrcqv (#78)

*2026-3-21 22:50*

66666666666666

## 回复 by mb_ohekqrwa (#79)

*2026-3-24 19:12*

666

## 回复 by qqqiu (#80)

*2026-3-24 19:17*

1

## 回复 by mb_miylylso (#81)

*2026-3-26 18:38*

555

## 回复 by mb_izusevbx (#82)

*2026-3-31 00:12*

1

## 回复 by 小迷糊ddd (#83)

*2026-4-6 22:36*

感谢分享，认真学习。

## 回复 by win柠初 (#84)

*2026-4-7 15:24*

66666

## 回复 by mb_uktygsmq (#85)

*2026-4-9 17:37*

666

## 回复 by mb_lkdeiaju (#86)

*2026-4-16 00:13*

666

## 回复 by netwolfer (#87)

*2026-4-16 10:19*

赞一个。ai用的不错

## 回复 by fffgggfg (#88)

*2026-4-17 14:22*

66666666666666666

## 回复 by mb_zcfhleoj (#89)

*2026-4-22 16:38*

感谢分享

## 回复 by nqminhquan (#90)

*2026-4-22 23:36*

6666666

## 回复 by TeamAR (#91)

*2026-4-23 05:05*

666

## 回复 by mb_cbxyhpeu (#92)

*2026-4-28 16:22*

6666

## 回复 by mb_cbxyhpeu (#93)

*2026-4-28 16:22*

6666

## 回复 by mb_cbxyhpeu (#94)

*2026-4-28 16:22*

学习学习

## 回复 by mb_kpzkkmql (#95)

*2026-4-30 08:44*

1231

## 回复 by mb_kpzkkmql (#96)

*2026-4-30 08:44*

666666666666666666666

## 回复 by mb_kpzkkmql (#97)

*2026-4-30 08:44*

666666666666666666666![image](https://bbs.kanxue.com/view/img/face/009.gif)

## 回复 by mb_kpzkkmql (#98)

*2026-4-30 08:45*

感谢分享

## 回复 by iAndroid_223207 (#99)

*2026-5-27 15:06*

666

## 回复 by mb_vrrlkian (#100)

*2026-5-27 22:06*

666

## 回复 by 简单的简单 (#101)

*2026-5-27 22:39*

666

## 回复 by B.M.K (#102)

*2026-5-27 23:01*

666

## 回复 by gfxvggbwic (#103)

*2026-6-3 16:59*

666

## 回复 by mb_eumnbkwy (#104)

*2026-6-28 14:05*

看看

## 回复 by mb_rosvaogy (#105)

*2026-7-9 00:46*

11

## 回复 by mb_cedxuhcp (#106)

*2026-7-9 03:58*

过来看看

## 回复 by mb_iiumogmn (#107)

*2026-7-12 22:58*

感谢分享，深入学习

## 回复 by wx_Riham、 (#108)

*2026-7-12 23:09*

666啊

## 回复 by wx_Dispa1r (#109)

*2026-7-15 00:55*

1

## 回复 by mb_vsvwurwv (#110)

666

## 回复 by mb_wpgxvewy (#111)

666
