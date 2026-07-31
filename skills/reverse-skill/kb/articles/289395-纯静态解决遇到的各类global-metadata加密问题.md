---
title: '[原创]纯静态解决遇到的各类global-metadata加密问题'
url: https://bbs.kanxue.com/thread-289395.htm
tid: 289395
author: rettozero
date: '2025-12-10'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T15:21:57+08:00'
replies: 50
---

# 纯静态解决遇到的各类global-metadata加密问题

## 0x0 前言

在通过Il2cppdumper工具尝试dump unity游戏的sdk时，经常会碰到一些加密的global-metadata.dat，导致无法成功dump。

搜索网上的文章或工具个人感觉最好用两种分别是。

1.动态dump解密后的metadata。

2.利用il2cpp_api（未混淆）动态dump CS文件。

本文总共4个例子，有能用以上办法解决的，也有不能用以上方法解决的，全都是纯静态解决，按照从易到难的顺序。

## 0x1 找不到解密逻辑，观察规律编写解密脚本

既然要解密，肯定要先了解加密的位置在哪里。

通过github能下载到2020年的unity源码，找到MetadataCache.cpp中的il2cpp::vm::MetadataCache::Initialize函数，而这里也是大多数metadata解密的位置。

因考虑篇幅问题，一部分的代码都只会截取一部分。

| 123456789 | `bool` `il2cpp::vm::MetadataCache::Initialize()``{``s_GlobalMetadata = vm::MetadataLoader::LoadMetadataFile(``"global-metadata.dat"``);``if` `(!s_GlobalMetadata)``return` `false``;` `s_GlobalMetadataHeader = (``const` `Il2CppGlobalMetadataHeader*)s_GlobalMetadata;``IL2CPP_ASSERT(s_GlobalMetadataHeader->sanity == 0xFAB11BAF);``IL2CPP_ASSERT(s_GlobalMetadataHeader->version == 24);` |
|-|-|

| 12345 | `void``*` `il2cpp::vm::MetadataLoader::LoadMetadataFile(const char``*` `fileName)``{``std::string resourcesDirectory` `=` `utils::PathUtils::Combine(utils::Runtime::GetDataDir(), utils::StringView<char>(``"Metadata"``));` `std::string resourceFilePath` `=` `utils::PathUtils::Combine(resourcesDirectory, utils::StringView<char>(fileName, strlen(fileName)));` |
|-|-|

观看源码可以知道，我们可以利用global-metadata.dat或Metadata字符串去索引到具体的函数实现。而大多数的加密操作一般都在这两个函数。

让我们正式开始第一个案例吧！

先通过Metadata字符串索引到LoadMetadataFile函数。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657 | `__int64 __fastcall sub_35FC404(``sub_361107C(&a11);``a9` `=` `"Metadata"``;``a10` `=` `8``;``v19` `=` `a11 >>` `1``;``if` `( (a11 &` `1``) !``=` `0` `)``v20` `=` `a13;``else``v20` `=` `&a11` `+` `1``;``if` `( (a11 &` `1``) !``=` `0` `)``v19` `=` `a12;``a17` `=` `v20;``a18` `=` `v19;``sub_35A26B0(&a14, &a17, &a9);``if` `( (a11 &` `1``) !``=` `0` `)``operator delete(a13);``v21` `=` `strlen(a1);``if` `( (a14 &` `1``) !``=` `0` `)``v22` `=` `a16;``else``v22` `=` `&a14` `+` `1``;``if` `( (a14 &` `1``) !``=` `0` `)``v23` `=` `a15;``else``v23` `=` `a14 >>` `1``;``a9` `=` `a1;``a10` `=` `v21;``a17` `=` `v22;``a18` `=` `v23;``sub_35A26B0(&a11, &a17, &a9);``LODWORD(a17)` `=` `0``;``v24` `=` `sub_35B18B0(&a11,` `3``,` `1``,` `1``,` `0``, &a17);``if` `( a17 )``{``if` `( (a11 &` `1``) !``=` `0` `)``v25` `=` `a13;``else``v25` `=` `&a11` `+` `1``;``sub_35B31F4(``"ERROR: Could not open %s"``, v25);``}``else``{``v26` `=` `v24;``v27` `=` `sub_35B3380();``sub_35B1AF0(v26, &a17);``if` `( !a17 )``goto LABEL_22;``sub_35B3390(v27);``}``v27` `=` `0``;``LABEL_22:``if` `( (a11 &` `1``) !``=` `0` `)``operator delete(a13);``if` `( (a14 &` `1``) !``=` `0` `)``operator delete(a16);``return` `v27;``}` |
|-|-|

如果是十分熟悉这两个函数的师傅，一眼就可以知道这个函数里没有进行解密操作，接着索引到Initialize函数

| 12345678910111213141516 | `bool` `__fastcall sub_35D25D8(_DWORD` `*``a1,` `int` `*``a2)``v4` `=` `(sub_35FC404)(``"global-metadata.dat"``);``v5` `=` `v4;``unk_873B968` `=` `v4;``if` `( v4 )``{``unk_873B970` `=` `v4;``v6` `=` `*``(v4` `+` `172``);``*``a1` `=` `v6` `/` `0x28``;``unk_873B978` `=` `v6` `/` `0x28``;``*``a2` `=` `*``(v4` `+` `180``) >>` `6``;``unk_873B980` `=` `(sub_35B3354)((v6` `/` `0x28``),` `24``);``unk_873B988` `=` `(sub_35B3354)(``*``(unk_873B960` `+` `48LL``),` `8``);``unk_873B990` `=` `(sub_35B3354)(``*``(unk_873B970` `+` `164LL``)` `/` `0x58uLL``,` `8``);``unk_873B950` `=` `(sub_35B3354)(``*``(unk_873B970` `+` `52LL``)` `/` `0x24uLL``,` `8``);``}` |
|-|-|

if ( v4 )后的伪代码已经是将metadata的结构头和一些值填入到内存中了，按理说应该在sub_35FC404读取metadata后进行解密操作。

既然没找到，那就查看一下metadata的数据。
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_CTDN8J9VUWTM972.webp)

如果有观察了解过metadata结构头，或是对数字比较敏感的师傅，一眼就能看出来，这个metadata的加密十分规律。
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_NWAWCQV9R39AHVR.webp)

拿一个正常的结构头，会更加直观，因为metadata存储的多是各个参数的偏移和数量，因此很少有数据大于0xffffff（小端序）

因此通过观察03 07 0b 0f等偏移，可以观察出一定的加减规律。

再细致可以观察出这个规律是呈16一轮，这是我们在观察0x100这个偏移，这里存储的是关于windows相关的数据，apk是用不到的，因此多是不变的。

因此我们只需要提取0x100的十六个字节，并且对偏移0x8的数据异或0x1，即可得到一个异或表。

| 12345678910111213141516171819202122232425 | `def` `decrypt_metadata(encrypted_file_path, output_file_path):``with` `open``(encrypted_file_path,` `'rb'``) as f:``encrypted_data` `=` `f.read()` `# 初始化密钥表``key_table` `=` `[``0x70``,``0x2c``,``0xe8``,``0xa4``,``0x60``,``0x1c``,``0xd8``,``0x94``,``0x51``,``0x0c``,``0xc8``,``0x84``,``0x40``,``0xfc``,``0xb8``,``0x74``]``key_table[``8``] ^``=``0x1``decrypted_data` `=` `bytearray()` `for` `i` `in` `range``(``len``(encrypted_data)):``# 使用当前密钥表位置进行异或``key_index` `=` `i` `%` `16``temp` `=` `encrypted_data[i] ^ key_table[key_index]` `# 重要：将解密后的数据写回密钥表``key_table[key_index]` `=` `(key_table[key_index]` `-` `0x40``) &` `0xFF` `decrypted_data.append(temp)` `with` `open``(output_file_path,` `'wb'``) as f:``f.write(decrypted_data)`  `# 使用示例``decrypt_metadata(``'global-metadata.dat'``,` `'global-metadata-decrypted.dat'``)` |
|-|-|

随便找一个ai写一个脚本即可
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_KMU2HDKSSGX6KVM.webp)

可以看到我们得到了一个很干净的metadata，只需要把头部修复一下即可。

## 0x2 metadata改名且加密

第二个案例，我在so中无法搜索到metadata相关的字符串,查看assets资源文件，发现文件路径名和文件名都被修改成无意义命名。

但好在LoadMetadataFile函数中还有一个ERROR: Could not open %s 字符串

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758 | `__int64 __fastcall sub_12C6E34(const char` `*``a1)``{``sub_12E2F9C(v14);``v12` `=` `"gloxinia"``;``v13` `=` `8``;``v2` `=` `LOBYTE(v14[``0``]) >>` `1``;``if` `( (v14[``0``] &` `1``) !``=` `0` `)``v3` `=` `v15;``else``v3` `=` `v14` `+` `1``;``if` `( (v14[``0``] &` `1``) !``=` `0` `)``v2` `=` `v14[``1``];``v18` `=` `v3;``v19` `=` `v2;``sub_122C950(v16, &v18, &v12);``if` `( (v14[``0``] &` `1``) !``=` `0` `)``operator delete(v15);``v4` `=` `strlen(a1);``if` `( (v16[``0``] &` `1``) !``=` `0` `)``v5` `=` `v17;``else``v5` `=` `v16` `+` `1``;``if` `( (v16[``0``] &` `1``) !``=` `0` `)``v6` `=` `v16[``1``];``else``v6` `=` `LOBYTE(v16[``0``]) >>` `1``;``v12` `=` `a1;``v13` `=` `v4;``v18` `=` `v5;``v19` `=` `v6;``sub_122C950(v14, &v18, &v12);``LODWORD(v18)` `=` `0``;``v7` `=` `sub_12E1F00(v14,` `3``,` `1``,` `1``,` `0``, &v18);``if` `( v18 )``{``if` `( (v14[``0``] &` `1``) !``=` `0` `)``v8` `=` `v15;``else``v8` `=` `v14` `+` `1``;``sub_12F631C(``"ERROR: Could not open %s"``, v8);``}``else``{``v9` `=` `v7;``v10` `=` `sub_12F64F4();``sub_12E2140(v9, &v18);``if` `( !v18 )``goto LABEL_22;``sub_12F6504(v10);``}``v10` `=` `0``;``LABEL_22:``if` `( (v14[``0``] &` `1``) !``=` `0` `)``operator delete(v15);``if` `( (v16[``0``] &` `1``) !``=` `0` `)``operator delete(v17);``return` `v10;``}` |
|-|-|

找到函数后，发现路径名字被改为gloxinia，再向上索引，发现解密函数操作

| 1234567891011121314151617181920212223242526272829 | `__int64 __fastcall sub_12C6D60(const char` `*``a1)``{``result` `=` `sub_12C6E34(a1);``if` `( result )``{``v2` `=` `result;``v3` `=` `sub_12F64A0();``v4` `=` `sub_12F647C(``1``, v3);``v7` `=` `v4;``if` `( v4 )``{``memcpy(v4, v2, v3);``v8` `=` `&v7;``*``(sub_1277C3C(&qword_2CE6568, &v7, &unk_A414F3, &v8, &v6)` `+` `40``)` `=` `v2;``LODWORD(v8)` `=` `0``;``v5` `=` `0``;``v6` `=` `0``;``sub_12C6FDC(v7,` `256``, &v8, &v6, &v5);``sub_12C6FDC(v7, (v7[``63``]` `+` `v7[``62``]), &v8, &v6, &v5);``return` `v7;``}``else``{``sub_12F631C(``"ERROR: Could not malloc %ld"``, v3);``return` `0``;``}``}``return` `result;``}` |
|-|-|

我们再向上索引，成功找到我们的Initialize函数，我的metadata名字叫做feast_plaint_knight

| 123456789101112131415161718 | `bool` `__fastcall sub_12645CC(_DWORD` `*``a1,` `int` `*``a2)``{``v4` `=` `sub_12C6D60(``"feast_plaint_knight"``);``v5` `=` `v4;``qword_2CE58C0` `=` `v4;``if` `( v4 )``{``qword_2CE58C8` `=` `v4;``v6` `=` `*``(v4` `+` `172``);``*``a1` `=` `v6` `/` `0x28``;``dword_2CE58D0` `=` `v6` `/` `0x28``;``*``a2` `=` `*``(v4` `+` `180``) >>` `6``;``qword_2CE58D8` `=` `sub_12F647C((v6` `/` `0x28``),` `24``);``qword_2CE58E0` `=` `sub_12F647C(``*``(qword_2CE58B8` `+` `48``),` `8``);``qword_2CE58E8` `=` `sub_12F647C(``*``(qword_2CE58C8` `+` `164``)` `/` `0x58uLL``,` `8``);``qword_2CE58A8` `=` `sub_12F647C(``*``(qword_2CE58C8` `+` `52``)` `/` `0x24uLL``,` `8``);``v7` `=` `sub_12F647C(``*``(qword_2CE58B8` `+` `64``),` `8``);``}` |
|-|-|

拉进010查看，这个metadata初看大概也是一个循环异或的规律。
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_KJ83RW2QXM7ERKZ.webp)

但老是写解密脚本显然不是我这种懒狗的思路。这里当然要使用出我们的顶级解密工具Unidbg！

动态dump的原理除了识别metadata特征就是hook读取metadata返回的指针。

通过把unidbg模拟执行，不用传入任何参数，只需要配置一下globla-metadata.dat的路径读取问题即可。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445 | `public` `class` `Decryptor extends AbstractJni {` `private final AndroidEmulator emulator;``private final VM vm;``private final Module module;` `public Decryptor() {``/``/` `创建模拟器``emulator` `=` `AndroidEmulatorBuilder.for64Bit().build();``Memory memory` `=` `emulator.getMemory();` `memory.setLibraryResolver(new AndroidResolver(``23``));` `/``/` `Android` `8.0` `/``/` `创建虚拟机``vm` `=` `emulator.createDalvikVM();``vm.setJni(this);``vm.setVerbose(true);` `/``/` `加载目标so文件``File` `lib` `=` `new` `File``(``"unidbg-android/src/test/resources/libil2cpp.so"``);` `/``/` `替换为实际路径``module` `=` `vm.loadLibrary(lib, false).getModule();``}` `public void decryptGlobalMetadata() {``try` `{``/``/` `获取目标函数地址``long` `funcAddr` `=` `0x12645CC``;``System.out.println(``"目标函数地址: 0x"` `+` `Long``.toHexString(funcAddr));` `emulator.attach().addBreakPoint(module,` `0x``, new BreakPointCallback() {``@Override``public boolean onHit(Emulator<?> emulator,` `long` `address) {``try` `{``/``/` `读取后的地址添加一个断点,dump出来即可,可让ai直接写``return` `true;``}``});``Number result` `=` `module.callFunction(emulator, funcAddr);``System.out.println(``"函数执行结果: "` `+` `result);` `} catch (Exception e) {``e.printStackTrace();` `}``}` |
|-|-|

## 0x3 metadata加密且结构头顺序打乱

来到第三个案例,查看metadata
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_JQ478TZGHFGGK7Y.webp)

加快节奏,直接来到so中观察加密函数

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596 | `_DWORD` `*``__fastcall sub_654BC4(_DWORD` `*``a1,` `int` `*``a2)``{``v42` `=` `*``(_ReadStatusReg(TPIDR_EL0)` `+` `40``);``v41` `=` `0x11646E6A``;``v40` `=` `xmmword_1ABF1B9;``BYTE4(v40)` `=` `99``;``v4` `=` `1``;``LOBYTE(v40)` `=` `103``;``do``{``*``(&v40` `+` `v4) ^``=` `v4` `-` `2``;``+``+``v4;``}``while` `( v4 !``=` `20` `);``result` `=` `sub_673A98(&v40);` `/``/``读取metadata``qword_227D250` `=` `result;``if` `( result )``{``v35` `=` `a1;``v36` `=` `a2;``v6` `=` `result` `+` `1``;``v7` `=` `*``(result` `-` `*``result` `-` `192947``)` `+` `401871``;``v8` `=` `malloc(v7);``memcpy(v8, v6, v7);``v9` `=` `1``;``v38` `=` `xmmword_1ABF1CD;``*``v39` `=` `xmmword_1ABF1DD;``v39[``8``]` `=` `78``;``*``&v39[``13``]` `=` `*``(&xmmword_1ABF1DD` `+` `13``);``LOBYTE(v38)` `=` `57``;``do``{``v39[v9` `-` `16``] ^``=` `v9` `+` `98``;``+``+``v9;``}``while` `( v9 !``=` `45` `);``v10` `=` `sub_654FF8(v8, v7, &v38, &v37);``v11` `=` `*``(v37` `+` `v10` `-` `1``);``*``(v37` `+` `v10` `-` `1``)` `=` `*``v10;``*``v10` `=` `v11;``free(v8);``v12` `=` `*``(v10` `+` `5``);``v13` `=` `*``(v10` `+` `320``);``*``(v10` `+` `9``) ^``=` `0x27u``;``*``(v10` `+` `5``)` `=` `v12 ^` `0x59``;``qword_227D258` `=` `v10;``v14` `=` `malloc(v13);``v15` `=` `*``(v10` `+` `220``);``v16` `=` `v14;``qword_227D1D0` `=` `v14;``v17` `=` `malloc(v15);``v18` `=` `qword_227D250;``v19` `=` `v17;``v20` `=` `*``(v10` `+` `52``)` `+` `484``;``qword_227D1D8` `=` `v17;``memcpy(v16, (qword_227D250` `+` `v20), v13);``memcpy(v19, (v18` `+` `*``(v10` `+` `208``)` `+` `484``), v15);``if` `( v13 >``=` `1` `)``{``v21` `=` `*``(v10` `+` `320``);``*``v16 ^``=` `0xDu``;``if` `( v21 >``=` `2` `)``{``v22` `=` `1``;``do``{``*``(qword_227D1D0` `+` `v22) ^``=` `13` `-` `v22;``+``+``v22;``}``while` `( v22 <` `*``(v10` `+` `320``) );``}``v15` `=` `*``(v10` `+` `220``);``}``if` `( v15 >``=` `1` `)``{``v23` `=` `0``;``do``{``*``(qword_227D1D8` `+` `v23) ^``=` `v23` `+` `95``;``+``+``v23;``}``while` `( v23 <` `*``(v10` `+` `220``) );``}``v24` `=` `*``(v10` `+` `100``);``*``v35` `=` `v24` `/` `0x28``;``v25` `=` `*``(v10` `+` `616``);``dword_227D260` `=` `v24` `/` `0x28``;``*``v36` `=` `v25 >>` `6``;``qword_227D268` `=` `sub_6B3F18((v24` `/` `0x28``),` `56``);``qword_227D270` `=` `sub_6B3F18(``*``(qword_227D248` `+` `48``),` `8``);``qword_227D278` `=` `sub_6B3F18(``*``(qword_227D258` `+` `248``)` `/` `0x58uLL``,` `8``);``qword_227D238` `=` `sub_6B3F18(``*``(qword_227D258` `+` `192``) >>` `5``,` `8``);``v26` `=` `sub_6B3F18(``*``(qword_227D248` `+` `64``),` `8``);``v27` `=` `qword_227D248;``qword_227D280` `=` `v26;``}` |
|-|-|

可以看到函数把global-metadata.dat字符串解密后，读取再解密的过程。

其实就是加密了结构头和两个metadata的区段,stringLiteralDataOffset和stringOffset。

通过unidbg，这次我们断在v24 = *(v10 + 100);解密完后将两个区段dump出来,这里就不详细讲诉了，一样的操作

我们来观察dump下来的结构头。
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_X8NQ93RV9MYKCBC.webp)

惊奇的发现，不仅顺序被打乱，还被塞入很多无用数据。

| 1234567891011121314151617181920 | `s_TypeInfoTable` `=` `(Il2CppClass``*``*``)IL2CPP_CALLOC(s_Il2CppMetadataRegistration``-``>typesCount, sizeof(Il2CppClass``*``));``s_TypeInfoDefinitionTable` `=` `(Il2CppClass``*``*``)IL2CPP_CALLOC(s_GlobalMetadataHeader``-``>typeDefinitionsCount` `/` `sizeof(Il2CppTypeDefinition), sizeof(Il2CppClass``*``));``s_MethodInfoDefinitionTable` `=` `(const MethodInfo``*``*``)IL2CPP_CALLOC(s_GlobalMetadataHeader``-``>methodsCount` `/` `sizeof(Il2CppMethodDefinition), sizeof(MethodInfo``*``));``s_GenericMethodTable` `=` `(const Il2CppGenericMethod``*``*``)IL2CPP_CALLOC(s_Il2CppMetadataRegistration``-``>methodSpecsCount, sizeof(Il2CppGenericMethod``*``));``s_ImagesCount` `=` `s_GlobalMetadataHeader``-``>imagesCount` `/` `sizeof(Il2CppImageDefinition);``s_ImagesTable` `=` `(Il2CppImage``*``)IL2CPP_CALLOC(s_ImagesCount, sizeof(Il2CppImage));``s_AssembliesCount` `=` `s_GlobalMetadataHeader``-``>assembliesCount` `/` `sizeof(Il2CppAssemblyDefinition);``s_AssembliesTable` `=` `(Il2CppAssembly``*``)IL2CPP_CALLOC(s_AssembliesCount, sizeof(Il2CppAssembly));`  `-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``v24` `=` `*``(v10` `+` `100``);``*``v35` `=` `v24` `/` `0x28``;``v25` `=` `*``(v10` `+` `616``);``dword_227D260` `=` `v24` `/` `0x28``;``*``v36` `=` `v25 >>` `6``;``qword_227D268` `=` `sub_6B3F18((v24` `/` `0x28``),` `56``);``qword_227D270` `=` `sub_6B3F18(``*``(qword_227D248` `+` `0x30``),` `8``);``qword_227D278` `=` `sub_6B3F18(``*``(s_GlobalMetadataHeader` `+` `0xF8``)` `/` `0x58uLL``,` `8``);``qword_227D238` `=` `sub_6B3F18(``*``(s_GlobalMetadataHeader` `+` `0xC0``) >>` `5``,` `8``);``v26` `=` `sub_6B3F18(``*``(qword_227D248` `+` `64``),` `8``);` |
|-|-|

读过源码可以知道，这里填入的有s_GlobalMetadataHeader的一些结构头数据，但是观察偏移0xf8 0xc0明显是不对的，它映照的是打乱顺序后的结构头。

因此我们无法通过解密后的metadata进行sdkdump，还需要修复s_GlobalMetadataHeader。

哪如何快速的修复我们的s_GlobalMetadataHeader呢，我想到的第一个方法是通过拿一份同版本的未魔改的so文件，再索引进行比较。
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_SSCJ62GK65GEZQU.webp)

我们通过010模板拿到我们的结构头
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_WXRDFGDUS4TAJS2.webp)

在ida中对s_GlobalMetadataHeader进行填入
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_P3ZUMRUFQN6Z9PN.webp)

这里我未详细修改，将后面的字符串删除即可。

但是我们身为一个懒狗，将近60个数据，一个个去寻找，并且可能还有遗漏，显然不是我们的风格。
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_G3ED4B8RHQAKG8H.webp)

我们拿案例1解密后的metadata来观看，可以发现除了头部特征字节和末尾没用的字节，其余字节都是紧凑相连的。

例如

stringLiteralOffset+stringLiteralCount==stringLiteralDataOffset

0x100+0x39458==0x39558

我们只需要开头stringLiteralOffset和stringLiteralCount的数据就可以推算出全部的数据。

因为我们拥有所有正确的结构头，通过遍历stringLiteralDataOffset+打乱结构头数组[i]==打乱结构头数组[j]以此类推。

最后这个例子还有一个小坑

| 123 | `v49` `=` `unk_227D250` `+` `*``(s_GlobalMetadataHeader` `+` `0x20LL``)` `+` `0x1E4` `+` `88` `*` `v48;` `v49` `=` `unk_227D250` `+` `*``(s_GlobalMetadataHeader` `+` `0x1D8LL``)` `+` `0x1E4` `+` `16` `*` `v50;` |
|-|-|

在读取后还需要加0x1e4才是真正的数值

修复后：
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_2X6BFA9MJAA4U2V.webp)

## 0x4 metadata加密且结构头顺序打乱且加减数值不一

直接查看so

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153 | `bool` `__fastcall sub_11481E4()``{``v60` `=` `*``(_ReadStatusReg(TPIDR_EL0)` `+` `40``);``LODWORD(v59)` `=` `-``943937362``;``s_` `=` `::s_;``BYTE9(s_)` `=` `-``91``;``BYTE4(s_)` `=` `-``73``;``BYTE12(s_)` `=` `-``81``;``BYTE14(s_)` `=` `-``83``;``n20` `=` `1``;``LOBYTE(s_)` `=` `103``;``*``(&s_` `+` `1``)` `=` `-``18507``;``do``{``*``(&s_` `+` `n20) ^``=` `-``38` `-` `n20;``+``+``n20;``}``while` `( n20 !``=` `20` `);``src` `=` `sub_116475C(&s_, a2, a3, a4, a5, a6, a7, a8, s_,` `*``(&s_` `+` `1``), v59, v60, v61, v62, v63, v64, v65, v66);` `/``/``读metadata``::src` `=` `src;``if` `( src )``{``dest` `=` `malloc(``0x150u``);``dest_0` `=` `dest;``memcpy(dest, src,` `0x150u``);``v13` `=` `xmmword_706520;``n84` `=` `0``;``v15.n128_u64[``0``]` `=` `0x9494949494949494LL``;``v15.n128_u64[``1``]` `=` `0x9494949494949494LL``;``v16.n128_u64[``0``]` `=` `0x1010101010101010LL``;``v16.n128_u64[``1``]` `=` `0x1010101010101010LL``;``do``{``v17` `=` `vaddq_s8(v13, v15);``v13` `=` `vaddq_s8(v13, v16);``*``&dest[n84]` `=` `veorq_s8(``*``&dest[n84], v17);``n84` `+``=` `4``;``}``while` `( n84 !``=` `84` `);``size` `=` `dest[``64``];``::dest` `=` `dest;``dest_1` `=` `malloc(size);``v20` `=` `dest[``4``]` `+` `0x28``;``::dest_1` `=` `dest_1;``memcpy(dest_1, &src[v20], size);``if` `( size )``{``for` `( i` `=` `0``; i < size;` `+``+``i )``*``(dest_1` `+` `i) ^``=` `v20` `+` `i` `-` `72``;``}``size_1` `=` `dest[``16``];``dest_2` `=` `malloc(size_1);``v24` `=` `dest[``74``]` `+` `24``;``::dest_2` `=` `dest_2;``memcpy(dest_2, &src[v24], size_1);``if` `( size_1 )``{``for` `( j` `=` `0``; j < size_1;` `+``+``j )``*``(dest_2` `+` `j) ^``=` `-``v24` `+` `j` `+` `72``;``}``size_2` `=` `dest[``18``];``dest_3` `=` `malloc(size_2);``v28` `=` `dest[``55``]` `+` `40``;``::dest_3` `=` `dest_3;``memcpy(dest_3, &src[v28], size_2);``if` `( size_2 )``{``for` `( k` `=` `0``; k < size_2;` `+``+``k )``*``(dest_3` `+` `k) ^``=` `-``v28` `+` `k` `+` `72``;``}``size_3` `=` `dest[``33``];``dest_4` `=` `malloc(size_3);``v32` `=` `dest[``63``]` `+` `44``;``::dest_4` `=` `dest_4;``memcpy(dest_4, &src[v32], size_3);``if` `( size_3 )``{``for` `( m` `=` `0``; m < size_3;` `+``+``m )``*``(dest_4` `+` `m) ^``=` `-``v32` `+` `m` `+` `72``;``}``size_4` `=` `dest[``3``];``dest_5` `=` `malloc(size_4);``v36` `=` `dest[``73``];``::dest_5` `=` `dest_5;``dest_8` `=` `dest_5;``memcpy(dest_5, &src[v36` `-` `24``], size_4);``if` `( size_4 )``{``for` `( n` `=` `0``; n < size_4;` `+``+``n )``dest_8[n] ^``=` `v36` `-` `24` `+` `n` `-` `72``;``}``size_5` `=` `dest[``11``];``dest_6` `=` `malloc(size_5);``v41` `=` `dest[``80``]` `+` `28``;``::dest_6` `=` `dest_6;``memcpy(dest_6, &src[v41], size_5);``if` `( size_5 )``{``for` `( ii` `=` `0``; ii < size_5;` `+``+``ii )``*``(dest_6` `+` `ii) ^``=` `v41` `+` `ii` `-` `72``;``}``size_6` `=` `dest[``27``];``dest_7` `=` `malloc(size_6);``v45` `=` `dest[``34``]` `+` `20``;``::dest_7` `=` `dest_7;``memcpy(dest_7, &src[v45], size_6);``if` `( size_6 )``{``for` `( jj` `=` `0``; jj < size_6;` `+``+``jj )``*``(dest_7` `+` `jj) ^``=` `v45` `+` `jj` `-` `72``;``}``v47` `=` `dest[``79``]` `/` `0x28uLL``;``*``a1` `=` `v47;``dword_2D5CA40` `=` `v47;``*``a2` `=` `size_4 >>` `6``;``qword_2D5CA48` `=` `sub_10FC34C(v47,` `24``);``qword_2D5CA50` `=` `sub_10FC34C(``*``(qword_2D5C9E8` `+` `48``),` `8``);``qword_2D5CA58` `=` `sub_10FC34C(``*``(::dest` `+` `0x7C``)` `/` `0x58uLL``,` `8``);``qword_2D5C9D8` `=` `sub_10FC34C(``*``(::dest` `+` `0x100``)` `/` `0x24uLL``,` `8``);``v48` `=` `sub_10FC34C(``*``(qword_2D5C9E8` `+` `64``),` `8``);``v49` `=` `qword_2D5C9E8;``qword_2D5CA60` `=` `v48;``if` `(` `*``(qword_2D5C9E8` `+` `48``) >``=` `1` `)``{``for` `( kk` `=` `0``; kk <` `*``(qword_2D5C9E8` `+` `48``);` `+``+``kk )``{``v51` `=` `*``(``*``(v49` `+` `56``)` `+` `8` `*` `kk);``n0x1E` `=` `*``(v51` `+` `10``);``if` `( n0x1E <``=` `0x1E` `)``{``v53` `=` `1` `<< n0x1E;``if` `( (v53 &` `0x13467FFE``) !``=` `0` `)``{``v54` `=` `*``v51;``if` `( v54 !``=` `-``1` `)``{``v55` `=` `::src` `+` `*``(::dest` `+` `0xE8``)` `+` `0x1C` `+` `88` `*` `v54;``LABEL_37:``*``v51` `=` `v55;``goto LABEL_38;``}``goto LABEL_36;``}``if` `( (v53 &` `0x40080000``) !``=` `0` `)``{``v56` `=` `*``v51;``if` `( v56 !``=` `-``1` `)``{``v55` `=` `::src` `+` `*``(::dest` `+` `56``)` `-` `0x40` `+` `16` `*` `v56;``goto LABEL_37;``}` `}` |
|-|-|

最后一个例子就是加强版的3号例子，加密了7个区块，且观察这两行代码，dest指向的就是metadata指针。

| 12 | `v55` `=` `::src` `+` `*``(::dest` `+` `0xE8``)` `+` `0x1C` `+` `88` `*` `v54;``v55` `=` `::src` `+` `*``(::dest` `+` `56``)` `-` `0x40` `+` `16` `*` `v56;` |
|-|-|

3号例子是统一的0x1e4，而这个例子，是不同的加减数，让我们无法利用上面那个方法计算。

但是通过观察发现，这个加减数大多都在0x50以内。

因此我们可以添加一个区间值

stringLiteralOffset+stringLiteralCount ±0x50 ≈≈stringLiteralDataOffset

但这样有一个隐患，可能出现两个或多个值，这里我使用的方法是了解每个结构体中各个值的意义，这样把每个值都添加一边跳转过去查看。

修复后：
 ![image](https://bbs.kanxue.com/upload/attach/202512/931883_CWGZAV4HV8P4AYH.webp)

## 0x5 总结

如果写得不好，请轻喷，代码基本让ai都能编写出来，就没贴出来了。如果师傅们有更好的方法请多多分享让我学习一下！！！

---

# 回复

## 回复 by mb_lakweznz (#2)

*2025-12-11 02:28*

不错

## 回复 by mb_ldbucrik (#3)

*2025-12-11 10:51*

感谢分享

## 回复 by New对象处 (#4)

*2025-12-11 11:18*

案例3像以前解决的一款海外游戏，对峙2

## 回复 by 流霜瞳 (#5)

*2025-12-11 11:29*

学习

## 回复 by Imxz (#6)

*2025-12-11 14:51*

tql

## 回复 by 梧桐生 (#7)

*2025-12-11 23:33*

tql

## 回复 by 独爱电脑 (#8)

*2025-12-13 21:27*

tql

## 回复 by xianhuimin (#9)

*2025-12-15 14:41*

感谢分享

## 回复 by mb_vhwdzyqo (#10)

*2025-12-15 19:04*

哥 四个样本分别是啥 我想动手试试

## 回复 by mb_vhwdzyqo (#11)

*2025-12-15 19:24*

哥 我真的好想学 你看到了能发下样本的名字吗

## 回复 by mb_vhwdzyqo (#12)

*2025-12-15 22:09*

大佬们 这个游戏是bao ke meng da ji jie是tprt加固

然后

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_EY5EPVK97CD3WX2.webp)

我去hook这俩地址 用的是大佬的unidbg代码

下方是我的代码

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_X99MA4SZF8KTHZC.webp)

打印结果是

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_JYMHNCH78DGS4ZH.webp)

然后我查看了这个地址的值

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_6V49C3UT95TU8UR.webp)

为啥会这样

我很蒙 看不懂

求帮助 我想知道具体是怎么打印这个

大佬的0x我是改过的 发现0x它报错 希望大佬能讲讲

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_JQJTUMA3VD67F72.webp)

球球大佬了

## 回复 by mb_vhwdzyqo (#13)

*2025-12-15 23:03*

public boolean onHit(Emulator<?> emulator, long address) {
                    try {
                    // 读取后的地址添加一个断点,dump出来即可,可让ai直接写
                    return true;
                }
          });哥 这里的代码能发过来吗

## 回复 by icey233 (#14)

*2025-12-19 00:16*

感谢分享

## 回复 by mb_vhwdzyqo (#15)

*2025-12-23 14:49*

哥 你还在吗球球了

## 回复 by 啊你好哇123 (#16)

*2025-12-23 22:05*

学习

## 回复 by bfloat16 (#17)

*2025-12-25 10:25*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_vhwdzyqo](https://bbs.kanxue.com/user-1023363.htm)
>
>  大佬们 这个游戏是bao ke meng da ji jie是tprt加固然后我去hook这俩地址 用的是大佬的unidbg代码下方是我的代码打印结果是然后我查看了这个地址的值为啥会这样我很蒙 看不懂 ...
>
>

用frida + 物理机去dump，直接就是解密后的文件

## 回复 by mb_wsvngnua (#18)

*2025-12-25 16:32*

感谢大佬分享

## 回复 by mb_eizetlni (#19)

*2025-12-26 07:12*

666

## 回复 by cobe (#20)

*2025-12-26 10:12*

666

## 回复 by iamshy (#21)

*2025-12-29 13:47*

感谢大佬分享

## 回复 by tjytjy (#22)

*2025-12-30 14:44*

666

## 回复 by xinhu (#23)

*2025-12-31 17:06*

5555

## 回复 by wx_荣仔 (#24)

*2026-1-2 15:09*

一直没有解决的问题。看看这里能不能学到。

## 回复 by 3zureus (#25)

*2026-1-5 14:15*

感谢分享

## 回复 by GEKEZYX (#26)

*2026-1-9 16:43*

666

## 回复 by mb_tjehxaqu (#27)

*2026-1-9 17:24*

感谢分享

## 回复 by mb_dtdhdols (#28)

*2026-1-14 04:15*

感谢分享

## 回复 by mb_uruwpimj (#29)

*2026-2-6 01:14*

学习学习

## 回复 by mb_fglogyec (#30)

*2026-2-8 11:52*

666

## 回复 by mb_irhdtnzm (#31)

*2026-2-9 18:48*

666

## 回复 by mb_jxhmajfh (#32)

*2026-2-10 22:37*

感谢感谢

## 回复 by 小尘0000 (#33)

*2026-3-3 17:27*

6

## 回复 by xifgg (#34)

*2026-3-5 11:55*

666

## 回复 by mb_qimctavn (#35)

*2026-3-5 12:20*

6

## 回复 by 漆黑火焰魔法使 (#36)

*2026-3-5 12:33*

感谢分享，学习了。

## 回复 by 外交 (#37)

*2026-3-30 16:42*

666

## 回复 by 小迷糊ddd (#38)

*2026-4-6 22:33*

感谢分享，记录学习。

## 回复 by mb_uktygsmq (#39)

*2026-4-9 17:42*

666

## 回复 by cxxxx (#40)

*2026-4-15 22:58*

感谢分享

## 回复 by fffgggfg (#41)

*2026-4-17 14:07*

非常感谢。

## 回复 by FMNS (#42)

*2026-4-20 06:06*

感谢分享

## 回复 by 看这是什么 (#43)

*2026-4-22 16:19*

感谢分享

## 回复 by nqminhquan (#44)

*2026-4-30 19:36*

66666

## 回复 by zhonghuayi (#45)

*2026-5-26 00:56*

感谢分享

## 回复 by B.M.K (#46)

*2026-5-27 23:10*

666

## 回复 by 简单的简单 (#47)

*2026-5-31 14:10*

666

## 回复 by mb_jegknedl (#48)

*2026-6-3 16:25*

学习学习

## 回复 by wlmf (#49)

*2026-6-16 15:35*

mark

## 回复 by 櫬木汐 (#50)

*2026-6-16 16:31*

666

## 回复 by 听闻 (#51)

*2026-7-15 12:27*

感谢分享
