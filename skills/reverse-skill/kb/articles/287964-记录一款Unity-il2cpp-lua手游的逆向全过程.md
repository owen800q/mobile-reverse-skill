---
title: '[原创]记录一款Unity il2cpp lua手游的逆向全过程'
url: https://bbs.kanxue.com/thread-287964.htm
tid: 287964
author: G33k3r
date: '2025-08-10'
tags: [Android安全, 原创, 逆向分析, 混淆加固, 脱壳反混淆, HOOK注入]
crawled_at: '2026-07-31T14:05:40+08:00'
replies: 54
---

## 前言

**补充声明：请勿用于非法用途，未经本人许可不能转载。**

最近在某音刷到了一款叫XX冬日的手游，大致套路要升级建筑、升级英雄、做各种任务积攒资源从而提升实力，参与各种实力排行，下载之后玩了两天，各种任务小红点点到停不下来，属实上头。游戏中大多数操作都是无脑点击，于是想着通过逆向工程来看看能不能自动做任务。

主要想达成两个目的：第一分析下这个客户端apk和服务端的通信协议，看看能不能实现封包改包，如果服务端少了校验，甚至可以在pk时一键秒杀对方；第二看看游戏逻辑能否实现任务自动化，实现脱机养号。

于是有了此文，一方面记录一下一些apk逆向的惯用套路方便之后查阅，二来这些年在看雪、52破解等论坛混迹多年，常常感概于各路大神的骚操作，也常常觉得自己“曹操媳妇进菜园——甄姬拔菜”。

## 抓包

首先通过`Reqable`抓包，这个工具以前叫`httpcanary`，也叫小黄鸟，是安卓上一款抓包神器，现在可以配合PC端来使用，手机端抓到的包，可以直接在电脑上查看，还可以对`url`进行下断点改包，针对一些`http/https`交互的`apk`，还是比较好使的。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_N49ZDFG6HKSRBSP.webp)

进入游戏后，点击一下领取资源、做任务的按钮，观察数据包，发现抓包面板没有响应，游戏也没有出现网络无连接的现象，根据以往的逆向经验，交互逻辑没有采用常规的`http/https`协议，可能是`rpc`或者自定义报文格式的`tcp/udp`协议。
如果`apk`是在`java`层面实现的通信协议，那么常规的思路就是从`Activity`出发，至于`Activity`的定位，可以通过MT管理器来查看定位，结合UI通过`Frida`来进行hook，手动抛出异常并打印调用栈，结合`jadx`反编译`class.dex`进而追溯到网络协议请求相关的代码逻辑。这里给出一种思路，本文未使用此法。

| 123456789101112131415161718192021222324252627282930313233 | `Java.perform(``function` `() {``// 定义目标类和方法``var` `targetClass =` `"com.example.TargetClass"``;``var` `targetMethod =` `"methodToHook"``;` `// 获取目标类引用``var` `cls = Java.use(targetClass);` `// Hook目标方法（处理重载方法）``var` `overloads = cls[targetMethod].overloads;``for` `(``var` `i = 0; i < overloads.length; i++) {``overloads[i].implementation =` `function` `() {``try` `{``// 1. 打印方法调用信息``console.log(`\n[+] Called ${targetClass}.${targetMethod}`);``console.log(``"Arguments:"``, JSON.stringify(arguments));` `// 2. 创建异常对象获取调用栈``var` `Exception = Java.use(``"java.lang.Exception"``);``var` `e = Exception.$``new``(``"Frida Hook Stack Trace"``);``console.log(``"Call Stack:"``);``console.log(Java.use(``"android.util.Log"``).getStackTraceString(e));` `// 3. 主动抛出异常``throw` `e;` `// 中断方法执行` `}` `catch` `(err) {``console.error(``"Hook Error:"``, err);``}``};``}``console.log(`[+] Hooked ${targetClass}.${targetMethod}`);``});` |
|-|-|

如果通信协议是`rpc`或者自定义格式的`tcp/udp`协议，通过`socket`层面的发送和接收来进行抓包，脚本如下

| 1234567891011 | `function` `hook_sendto() {``const sendto = Module.findExportByName(``'libc.so'``,` `'sendto'``);``Interceptor.attach(sendto, {``onEnter(args) {``this``.buf = args[1];` `// 数据缓冲区``this``.size = args[2];``this``.data = ptr(``this``.buf).readByteArray(``this``.size.toInt32());``console.log(``'Sendto:'``, hexdump(``this``.data));``}``});``}` |
|-|-|

不过这游戏有反调试，需要先过掉。

## Frida动态分析

### Frida反调试

配置好`Frida`的基础环境，电脑上需要通过`python`安装`frida-tools`和`frida`，`frida-tools`就是让我们可以在命令行里使用`frida -U -f com.target.app -l hook.js --no-pause`这样的命令，`frida`则是`python`的`package`，可以在`python`脚本中去引入使用。手机上则需要安装对应版本和CPU架构的`frida-server`，配置好基础环境之后附加到进程启动，启动之后游戏还没加载完就退出了，有针对`frida`的反调试。

### Frida反反调试

将`.apk`拖到电脑上，后缀改名`.zip`之后，直接解压，查看`lib`目录下有如下`.so`文件

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_U4EY9F75ZYJM5NQ.webp)

拿着`.so`名称做为关键字搜索反调试，找到了一篇文章，[无壳app的libmsaoaidsec.so frida反调试绕过姿势 (qq.com)](https://mp.weixin.qq.com/s?__biz=MjM5NTc2MDYxMw==&amp;mid=2458590751&amp;idx=1&amp;sn=3a5f5b3c1d41a36914abf745b355f9dc&amp;chksm=b096b8c8ef74479a0a5bbc80e8814d95979a266fc0b120f69076d8402ee5c801be68ed41794b&amp;scene=27)，文章中已经详细说明了原理并给出了过反调试的脚本，直接拿过来使用。笑嘻嘻的复制完脚本，启动之后，过了一会儿还是退出了，搜索了几篇文章之后，猜测大概率是因为有一些`frida`的特征检测，针对此类特征码的检测，看到有文章通过hook诸如`strcmp`这类的字符串操作类函数来规避特征检测，不过也比较麻烦，没有去深究，我这里采用魔改`frida`的方式来规避。

### Frida魔改版本rusda

下载地址，[Release rusda16.2.1 · taisuii/rusda (github.com)](https://github.com/taisuii/rusda/releases/tag/release)，仓库中有教程怎么修改编译，完全抹除了`frida`的字符串特征，作者也给出了编译好的版本。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_Z7AM37GWTWYWGTY.webp)

模拟器选择`x86`，我是`红米K40`真机，架构是`arm64`，因此下载

[rusda-server-android-arm64](https://github.com/taisuii/rusda/releases/download/release/rusda-server-android-arm64)，不知道`cpu`架构可以通过如下命令查看

| 1 | `adb shell getprop ro.product.cpu.abi` |
|-|-|

输出`arm64-v8a`

将魔改Frida推送到手机上并且启动监听

| 123456789101112 | `adb push rusda-server-android-arm64` `/data/local/tmp/``adb shell``su``chmod` `+x rusda-server-android-arm64``.``/rusda-server-android-arm64` `-l 0.0.0.0:54321 -D` `#这里自定义端口号，防止反Frida检测特征端口 -l指定监听地址 -D表示后台运行``ps` `-A \|` `grep` `rusda` `#查看后台进程` `# 输出如下``haydn:``/data/local/tmp` `# ps -A \| grep rusda``root           5469      1 2237164  50516 do_sys_poll         0 S rusda-server-android-arm64` `kill` `-9 5469` `#杀死进程` |
|-|-|

以上，手机端配置完成，接下来windows上需要安装对应版本的也就是`16.2.1`的`frida`，我的python版本为`3.13.3`，通过如下命令安装`frida 16.2.1`，对应`frida-tools`为`12.3.0`，由于我的电脑上之前安装的没有魔改的`frida`版本和这个`android_server`不对应，得先卸载掉，或者新建一套虚拟环境配置也行。

| 1234567891011 | `pip uninstall frida frida-tools` `#卸载其它版本` `#安装和手机端对应的版本``pip` `install` `frida==16.2.1``pip` `install` `frida-tools=12.3.0` `#验证安装，控制台输入``frida --version` `#输出``16.2.1` |
|-|-|

以上便完成了基础的环境搭建，尝试通过电脑端`frida`连接手机端，结合脚本如下直接就绕过了，笑容又回来了！

| 1 | `frida -H 192.168.0.101:54321 -f com.example.package -l anti_frida.js` `#-H指定远程Host的ip和端口 因为我是无线调式 usb调试的用-U -f指定包名` |
|-|-|

`anti_frida.js`脚本如下，来源于[无壳app的libmsaoaidsec.so frida反调试绕过姿势 (qq.com)](https://mp.weixin.qq.com/s?__biz=MjM5NTc2MDYxMw==&amp;mid=2458590751&amp;idx=1&amp;sn=3a5f5b3c1d41a36914abf745b355f9dc&amp;chksm=b096b8c8ef74479a0a5bbc80e8814d95979a266fc0b120f69076d8402ee5c801be68ed41794b&amp;scene=27)

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162 | `function` `hook_dlopen(){``const android_dlopen_ext = Module.findExportByName(``null``,` `"android_dlopen_ext"``);``if``(android_dlopen_ext) {``Interceptor.attach(android_dlopen_ext, {``onEnter:` `function``(args) {``const pathptr = args[0];``if``(pathptr !=` `null` `&& pathptr != undefined) {``const path = ptr(pathptr).readCString();``if``(path !=` `null` `&& path.indexOf(``"libmsaoaidsec.so"``) != -1){``console.log(`android_dlopen_ext >>> load ${path}`);``hook_call_constructors_libmsaoaidsec();``}``}``},``onLeave:` `function``() {` `}``});``}` `}` `function` `hook_call_constructors_libmsaoaidsec() {``let linker =` `null``;` `if` `(Process.pointerSize === 4) {``linker = Process.findModuleByName(``"linker"``);``}` `else` `{``linker = Process.findModuleByName(``"linker64"``);``}``let call_constructors_addr, get_soname``let symbols = linker.enumerateSymbols();``for` `(let index = 0; index < symbols.length; index++) {``let symbol = symbols[index];``if` `(symbol.name ===` `"__dl__ZN6soinfo17call_constructorsEv"``) {``call_constructors_addr = symbol.address;``}` `else` `if` `(symbol.name ===` `"__dl__ZNK6soinfo10get_sonameEv"``) {``get_soname =` `new` `NativeFunction(symbol.address,` `"pointer"``, [``"pointer"``]);``}``}``// console.log(call_constructors_addr)``var` `listener = Interceptor.attach(call_constructors_addr, {``onEnter:` `function` `(args) {``var` `module = Process.findModuleByName(``"libmsaoaidsec.so"``)``if` `(module !=` `null``) {``Interceptor.replace(module.base.add(0x1c544),` `new` `NativeCallback(``function` `() {``console.log(``"0x1c544:替换成功"``)``},` `"void"``, []))``Interceptor.replace(module.base.add(0x1b8d4),` `new` `NativeCallback(``function` `() {``console.log(``"0x1b8d4:替换成功"``)``},` `"void"``, []))``Interceptor.replace(module.base.add(0x26e5c),` `new` `NativeCallback(``function` `() {``console.log(``"0x26e5c:替换成功"``)``},` `"void"``, []))``listener.detach();``}``},``onLeave:` `function``(retvel) {` `}``})``}` |
|-|-|

接下来便可以的开心的进行hook了，我进入游戏之后，通过MT管理器，查到页面的`Activity`是`com.unity3d.player.DDUnityLaunchActivity`，切换了下面的几个页签之后，这个`Activity`都没有变，因此UI资源和游戏逻辑不在java层面，那么反编译`class.dex`就没必要了。只能知道是一个`unity`游戏。

## Unity游戏开发套路

结合`Activity`名称，`lib`目录下的`.so`文件，例如`libunity.so`和`libil2cpp.so`，以及`\assets\bin\Data\Managed\Metadata\global-metadata.dat`这些特征，也搜索到了几篇比较好的文章，如下

[[原创]什么？IL2CPP APP分析这一篇就够啦！-茶余饭后-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-282821.htm)

[针对魔改unity引擎的il2cpp dump方案il2cpp_class_dumper-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-282653.htm)

[[原创]IL2CPP 逆向初探-软件逆向-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-278275.htm)

[global-metadata.dat,libil2cpp.so解密修复](https://bbs.kanxue.com/thread-273503.htm)

这几篇文章都值得细细品味，根据文章中的思路，首先尝试通过`Prefare`大佬的[github.com/Perfare/Il2CppDumper](https://github.com/Perfare/Il2CppDumper)，根据`libil2cpp.so`和`global-metadata.dat`去反编译得到`C#符号表`，当然是失败了的。根据文章中的思路，`.so`和`global-metadata.data`大概率经过了混淆和魔改，那么我们就需要尝试从内存中dump出来这两个文件，脚本如下，记得配合之前过反调试使用，进入游戏后，`frida`没有被异常终止之后在`frida`控制台中输入`dump_so("libil2cpp.so")`来使用

| 12345678910111213141516171819 | `function dump_so(so_name) {``Java.perform(function () {``var libso` `=` `Process.getModuleByName(so_name);``console.log(``"[name]:"``, libso.name);``console.log(``"[base]:"``, libso.base);``console.log(``"[size]:"``, ptr(libso.size));``console.log(``"[path]:"``, libso.path);``var file_path` `=` `"/sdcard/Download/"` `+` `libso.name` `+` `"_"` `+` `libso.base` `+` `"_"` `+` `ptr(libso.size)` `+` `".so"``;``var file_handle` `=` `new` `File``(file_path,` `"wb"``);``if` `(file_handle && file_handle !``=` `null) {``Memory.protect(ptr(libso.base), libso.size,` `'r--'``);``var libso_buffer` `=` `ptr(libso.base).readByteArray(libso.size);``file_handle.write(libso_buffer);``file_handle.flush();``file_handle.close();``console.log(``"[dump]:"``, file_path);``}``});``}` |
|-|-|

这样我们就把`libil2cpp.so`导出到了手机`Download`目录下了。

接下来是针对`global-metadata.dat`的导出，其中一种方式通过魔术头来漫游内存进行dump，这种方式后来发现其实dump出来的文件不对，所以我后面采用的是另一种方式来进行dump。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374757677787980818283 | `function` `get_self_process_name()``{``var` `openPtr = Module.getExportByName(``'libc.so'``,` `'open'``);``var` `open =` `new` `NativeFunction(openPtr,` `'int'``, [``'pointer'``,` `'int'``]);` `var` `readPtr = Module.getExportByName(``"libc.so"``,` `"read"``);``var` `read =` `new` `NativeFunction(readPtr,` `"int"``, [``"int"``,` `"pointer"``,` `"int"``]);` `var` `closePtr = Module.getExportByName(``'libc.so'``,` `'close'``);``var` `close =` `new` `NativeFunction(closePtr,` `'int'``, [``'int'``]);` `var` `path = Memory.allocUtf8String(``"/proc/self/cmdline"``);``var` `fd = open(path, 0);``if` `(fd != -1)``{``var` `buffer = Memory.alloc(0x1000);` `var` `result = read(fd, buffer, 0x1000);``close(fd);``result = ptr(buffer).readCString();``return` `result;``}` `return` `"-1"``;``}` `function` `frida_Memory()``{``Java.perform(``function` `()``{``var` `pattern =` `"AF 1B B1 FA 18"``;``//global-metadata.dat头部特征``console.log(``"头部标识:"` `+ pattern);``var` `addrArray = Process.enumerateRanges(``"r--"``);``for` `(``var` `i = 0; i < addrArray.length; i++)``{``var` `addr = addrArray[i];``Memory.scan(addr.base, addr.size, pattern,``{``onMatch:` `function` `(address, size)``{``console.log(``'搜索到 '` `+ pattern +` `" 地址是:"` `+ address.toString());``console.log(hexdump(address,``{``offset: 0,``length: 0x110,``header:` `true``,``ansi:` `true``}``));``//0x108，0x10C如果不行，换 0x100，0x104``var` `DefinitionsOffset = parseInt(address, 16) + 0x108;``var` `DefinitionsOffset_size = Memory.readInt(ptr(DefinitionsOffset));` `var` `DefinitionsCount = parseInt(address, 16) + 0x10C;``var` `DefinitionsCount_size = Memory.readInt(ptr(DefinitionsCount));``if` `(DefinitionsCount_size < 10)``{``DefinitionsOffset = parseInt(address, 16) + 0x100;``DefinitionsOffset_size = Memory.readInt(ptr(DefinitionsOffset));` `DefinitionsCount = parseInt(address, 16) + 0x104;``DefinitionsCount_size = Memory.readInt(ptr(DefinitionsCount));``}``//根据两个偏移得出global-metadata大小``var` `global_metadata_size = DefinitionsOffset_size + DefinitionsCount_size``console.log(``"大小："``, global_metadata_size);``var` `file =` `new` `File(``"/data/data/"` `+ get_self_process_name() +` `"/global-metadata.dat"``,` `"wb"``);``file.write(Memory.readByteArray(address, global_metadata_size));``file.flush();``file.close();``console.log(``'路径：'` `+` `"/data/data/"` `+ get_self_process_name() +` `"/global-metadata.dat"``);``console.log(``'导出完毕...'``);``},``onComplete:` `function` `()``{``//console.log("搜索完毕")``}``}``);``}``}``);``}` |
|-|-|

之后将这两个文件送入`Il2CppDumper`，报错`“[VerifyElfHeader:145]"libil2cpp.so_0x7a4a345000_0x5c9e000.so" has bad ELF magic”`。

通过`010Editor`打开文件`libil2cpp.so_0x7a4a345000_0x5c9e000.so`，尝试运行`ELF`模板也没有成功，查看字节如下

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_7QY6AN5JAZN9BPA.webp)

## ELF格式(so)修复

魔术头不是`7F 45 4C 46`，对比正常的`ELF`文件，通过`010Editor`模板解析之后应该如下

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_HZYA22SQWBSXCEN.webp)

关于ELF文件头格式的解析，有这些文章参考

[[原创] ELF文件结构浅析-解析器和加载器实现-软件逆向-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-284556.htm)

[[原创] SoFixer导入表问题修复及ELF解析简记-软件逆向-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-282221.htm)

正常的`so`的`elf_header`大小为`0x40`，例如我们观察`lib`目录下的`libil2cpp.so`的头部如下

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_TZNYZYFC7VUXYP8.webp)

我这里dump出来的`so`的前面`0x40`字节被替换了，这样做一是可以阻止一些根据`ELF`魔术头进行的dump脚本，二是可以阻断我们dump出`so`之后直接拖入`IDA`进行反编译。

当然这里我们也能确定一些固定的信息，例如`0x10`大小的`e_ident`固定为`7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00`，`e_type`固定为`3`，`e_machine`固定为`183`，`e_version`固定为`1`，程序入口`entry`暂时不能确定，`e_phoff`固定为`64`，也就是`0x40`，因为`elf_program_header_table`是紧跟着`elf_header`的，而`elf_header`的大小固定为`0x40`，所以程序头表`elf_program_header_table`的偏移也是固定的，至于节头表`section_header_table`相关信息我们现在没法确定，根据这些固定的信息，通过脚本替换前面`0x40`的`elf_header`。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374757677787980 | `import` `struct` `def` `fix_elf_header(input_file, output_file):``#` `e_ident` `=` `bytes.fromhex(``'7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00'``)``e_type` `=` `3`          `# ET_DYN (共享对象文件)``e_machine` `=` `183`     `# EM_AARCH64 (arm64)``e_version` `=` `1``e_entry` `=` `0`         `# 程序入口``e_phoff` `=` `64`        `# 程序头表起始位置``e_shoff` `=` `0`         `# 节头表起始位置``e_flags` `=` `0``e_ehsize` `=` `64`       `# ELF头大小``e_phentsize` `=` `0`    `# 程序头大小``e_phnum` `=` `7`        `# 程序头数量``e_shentsize` `=` `0`    `# 节头大小``e_shnum` `=` `0`        `# 节头数量``e_shstrndx` `=` `0`     `# 节头字符串表索引` `# 构建ELF头结构 (小端序)``elf_header` `=` `struct.pack(``'<16s'`    `# e_ident``'H'`        `# e_type``'H'`        `# e_machine``'I'`        `# e_version``'Q'`        `# e_entry``'Q'`        `# e_phoff``'Q'`        `# e_shoff``'I'`        `# e_flags``'H'`        `# e_ehsize``'H'`        `# e_phentsize``'H'`        `# e_phnum``'H'`        `# e_shentsize``'H'`        `# e_shnum``'H'`        `# e_shstrndx``,` `e_ident,``e_type,``e_machine,``e_version,``e_entry,``e_phoff,``e_shoff,``e_flags,``e_ehsize,``e_phentsize,``e_phnum,``e_shentsize,``e_shnum,``e_shstrndx``)` `# 读取原始dump文件``with` `open``(input_file,` `'rb'``) as f:``data` `=` `f.read()` `# 检查文件长度是否足够``if` `len``(data) < e_ehsize:``raise` `ValueError(``"File is smaller than ELF header size"``)` `# 将新ELF头与原始内容组合 (替换前64字节)``new_data` `=` `elf_header` `+` `data[e_ehsize:]` `# 写入修复后的文件``with` `open``(output_file,` `'wb'``) as f:``f.write(new_data)` `if` `__name__` `=``=` `"__main__"``:``import` `sys` `if` `len``(sys.argv) !``=` `3``:``print``(``"Usage: python fix_elf_header.py <input_dump.so> <output_fixed.so>"``)``sys.exit(``1``)` `input_file` `=` `sys.argv[``1``]``output_file` `=` `sys.argv[``2``]` `fix_elf_header(input_file, output_file)``print``(f``"ELF header repaired. Output saved to {output_file}"``)` |
|-|-|

替换后对比结果如下，其实也就是前面`0x14`字节有差异。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_2UWKN2KJ6D4CCF5.webp)

好了，`elf_header`修复之后用[Releases · F8LEFT/SoFixer (github.com)](https://github.com/F8LEFT/SoFixer/releases)进行修复。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_R68J46VGPZ6EJJ3.webp)

修复之后的再拖到`010Editor`观察，运行`ELF`模板后如下

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_AKMATC45AXQHKBA.webp)

可以看到，`SoFixer`帮我们恢复了程序头表和节头表，但是还是少了一个动态符号表`dynamic_symbol_table`，我们仔细观察`elf_header`发现里面的

`Elf64_Half e_ehsize_ELF_HEADER_SIZE`固定的`64`

`Elf64_Half e_phentsize_PROGRAM_HEADER_ENTRY_SIZE_IN_FILE`对比原版`so`是`56`

`Elf64_Half e_shentsize_SECTION_HEADER_ENTRY_SIZE`固定为`64`

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_2SXK4VHY6BV8CCP.webp)

手动编辑一下相关字节之后，重新运行`ELF.bt`，底部多出来了动态符号表`dynamic_symbol_table`了

其实我回头看的时候，发现我们添加头部的脚本里面还可以确定上面手动改的3个参数，调整后如下，这样填充完头部之后，通过`SoFixer`可以一步到位。

| 12345678910111213141516 | `def` `fix_elf_header(input_file, output_file):``#` `e_ident` `=` `bytes.fromhex(``'7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00'``)``e_type` `=` `3`          `# ET_DYN (共享对象文件)``e_machine` `=` `183`     `# EM_AARCH64 (arm64)``e_version` `=` `1``e_entry` `=` `0`         `# 程序入口``e_phoff` `=` `64`        `# 程序头表起始位置``e_shoff` `=` `0`         `# 节头表起始位置``e_flags` `=` `0``e_ehsize` `=` `64`       `# ELF头大小``e_phentsize` `=` `56`    `# 程序头大小``e_phnum` `=` `7`        `# 程序头数量``e_shentsize` `=` `64`    `# 节头大小``e_shnum` `=` `0`        `# 节头数量``e_shstrndx` `=` `0`     `# 节头字符串表索引` |
|-|-|

再次尝试通过`Il2CppDumper`去反编译，尝试得到`dump.cs`，还是失败，心灰意冷。

不过修复之后，拖入`IDA`之后可以反编译。至此，我们终于踏出了艰难的一步，拿到了修复之后的`libil2cpp.so`，由于文件比较大，重建符号表时间比较长。遗留：修复之后的`so`有`92.6M`多，`apk`目录下的原版`so`仅有`53.4M`，里面填充了很多空字节，不过不影响`IDA`反编译。

## il2cpp导出函数定位

既然静态dump不行，于是我又尝试去试了一下[针对魔改unity引擎的il2cpp dump方案il2cpp_class_dumper-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-282653.htm)这篇文章里的，通过`Zygisk-Il2CppDumper`来直接从内存里面导出`dump.cs`，启动目标`apk`之后，程序崩溃，没有成功导出`dump.cs`，我查看日志之后也没有运行到导出的位置。
其实到了这里，根据上面那篇文章的提示，大概率猜到了隐藏了`il2cpp`的部分导出函数，进而让`Zygisk-Il2CppDumper`这样的工具没办法找到函数偏移。

于是我又去尝试如下工具：

[AndroidReverser-Test/frida-find-il2cpp-api: 使用frida spawn启动目标il2cpp手游注入脚本获得需要的il2cpp api的所在偏移 (github.com)](https://github.com/AndroidReverser-Test/frida-find-il2cpp-api)

[AndroidReverser-Test/il2cpp_class_dumper: 一个用于动态dump 魔改il2cpp框架的unity游戏符号的frida脚本 (github.com)](https://github.com/AndroidReverser-Test/il2cpp_class_dumper)

这两个工具的原理差不多，既然你混淆了`il2cpp`的导出函数名，就通过汇编特征码去定位，根据已经给的字符串特征码交叉引用，只找到了一个函数，`il2cpp_class_get_methods`。在导出表中名字如下，好家伙，混淆成了`HTPcDxoiHnMqKZdyUYO9uXzP`

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_WHYZX3HF3JQC3UB.webp)

所以我猜测其它几个关键API的字符串特征码也被抹除了。

到了这里，由于这两个工具需要的`API`不是很多，我的思路是去找一个原版没有混淆的版本来对比汇编代码，看看能不能再找出几个来，所以我又去下载了`Unity Editor`，由于`Unity Editor`版本较多，这里一定要下载对应版本的，至于下载什么版本，一种方式是查看`\assets\data\`下的`.unity3d`，可以看到版本号为`2022.3.52f1`

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_G5V2GCE5C9QSFTC.webp)

另一种方式，通过[SamboyCoding/Cpp2IL: Work-in-progress tool to reverse unity's IL2CPP toolchain. (github.com)](https://github.com/SamboyCoding/Cpp2IL)这个工具也能拿到，这个工具应该是整合了很多功能，可以直接对没有魔改的`Unity`游戏进行反编译，不过这里也没有去深究它了，拿到版本号和上面一致。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_GJUUD8P3TPH4DP5.webp)

一顿下载操作现学`Unity Editor`开发安卓apk，最后编译打包得到了一个没有混淆的`libil2cpp.so`，并且在`Unity\Hub\Editor\2022.3.52f1\Editor\Data\il2cpp\libil2cpp`下面有源码，这样对比起来看其实就没那么困难了。此时我们一个`IDA`打开没有混淆的so，另一个打开被混淆的so，之后在未混淆的里面搜索`il2cpp_method_get_name`这些函数，再通过汇编特征码去对比定位，这里由于读汇编代码一个个去匹配实在太慢了，写了个脚本来进行汇编特征码匹配。

大致思路就是，在未混淆的so里面搜索函数，将函数名和汇编特征码和常量引用存到`E:\python_project\il2cpp-project\original_signatures.json`，这个脚本需要在`IDA`里通过`ALT+F7`来加载运行。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374757677787980818283848586878889909192 | `# -*- coding: utf-8 -*-``import` `idautils``import` `idc``import` `json``import` `binascii` `# 目标函数列表``TARGET_FUNCTIONS` `=` `[``"il2cpp_method_get_name"``,``"il2cpp_class_get_name"``,``"il2cpp_class_get_type"``,``"il2cpp_class_get_namespace"``,``"il2cpp_method_get_param"``,``"il2cpp_method_get_param_count"``,``"il2cpp_class_from_type"``]` `def` `extract_function_signature(func_ea):``"""提取函数的特征签名"""``signature` `=` `[]``func_end` `=` `idc.get_func_attr(func_ea, idc.FUNCATTR_END)` `# 遍历函数前20条指令``ea` `=` `func_ea``for` `_` `in` `range``(``20``):``# 获取指令字节``insn_bytes` `=` `idc.get_bytes(ea, idc.get_item_size(ea))` `# 使用 binascii 将字节串转换为十六进制字符串``hex_bytes` `=` `binascii.hexlify(insn_bytes).decode(``'utf-8'``).upper()``hex_bytes` `=` `" "``.join(hex_bytes[i:i``+``2``]` `for` `i` `in` `range``(``0``,` `len``(hex_bytes),` `2``))` `# 添加到签名``signature.append(hex_bytes)` `# 移动到下一条指令``ea` `=` `idc.next_head(ea, func_end)``if` `ea` `=``=` `idc.BADADDR:``break` `return` `signature` `def` `extract_constant_references(func_ea):``"""提取函数引用的常量"""``constants` `=` `set``()` `# 遍历函数中的常量引用``for` `ref` `in` `idautils.CodeRefsTo(func_ea,` `0``):``# 获取引用处的指令``for` `head` `in` `idautils.Heads(ref, ref` `+` `16``):``if` `idc.print_insn_mnem(head)` `=``=` `"LDR"``:``op` `=` `idc.get_operand_value(head,` `1``)``if` `op !``=` `idc.BADADDR:``constant` `=` `idc.get_strlit_contents(op)``if` `constant:``constants.add(constant.decode(``'utf-8'``, errors``=``'ignore'``))` `return` `list``(constants)` `def` `main():``signatures` `=` `{}` `for` `func_name` `in` `TARGET_FUNCTIONS:``func_ea` `=` `idc.get_name_ea_simple(func_name)``if` `func_ea` `=``=` `idc.BADADDR:``print``(``"[-] Function not found: {}"``.``format``(func_name))``continue` `print``(``"[*] Processing {} at {}"``.``format``(func_name,` `hex``(func_ea)))` `# 提取特征``signature` `=` `extract_function_signature(func_ea)``constants` `=` `extract_constant_references(func_ea)` `# 添加到结果``signatures[func_name]` `=` `{``"address"``:` `hex``(func_ea),``"signature"``: signature,``"constants"``: constants,``"min_length"``:` `len``(signature)``}` `# 保存结果``output_path` `=` `"E:\python_project\il2cpp-project\original_signatures.json"` `with` `open``(output_path,` `"w"``) as f:` `# Removed encoding parameter``json.dump(signatures, f, ensure_ascii``=``False``, indent``=``2``)` `print``(``"[+] Saved signatures for {} functions to {}"``.``format``(``len``(signatures), output_path))` `if` `__name__` `=``=` `"__main__"``:``main()` |
|-|-|

得到的结果如下

```
{
  "il2cpp_class_get_namespace": {
    "min_length": 1,
    "signature": [
      "00 0C 40 F9"
    ],
    "constants": [],
    "address": "0xc192d8L"
  },
  "il2cpp_method_get_name": {
    "min_length": 1,
    "signature": [
      "E8 85 00 14"
    ],
    "constants": [],
    "address": "0xc19ae4L"
  },
  "il2cpp_class_from_type": {
    "min_length": 2,
    "signature": [
      "21 00 80 52",
      "29 85 00 14"
    ],
    "constants": [
      "T\b"
    ],
    "address": "0xc1934cL"
  },
  "il2cpp_method_get_param": {
    "min_length": 1,
    "signature": [
      "00 59 61 F8"
    ],
    "constants": [],
    "address": "0xc19af8L"
  },
  "il2cpp_class_get_type": {
    "min_length": 2,
    "signature": [
      "00 80 00 91",
      "C0 03 5F D6"
    ],
    "constants": [],
    "address": "0xc19354L"
  },
  "il2cpp_method_get_param_count": {
    "min_length": 1,
    "signature": [
      "E3 35 01 14"
    ],
    "constants": [],
    "address": "0xc19af4L"
  },
  "il2cpp_class_get_name": {
    "min_length": 1,
    "signature": [
      "B1 0C FF 17"
    ],
    "constants": [],
    "address": "0xc192d4L"
  }
}
```

之后再去混淆函数名的`IDA`里去根据汇编特征码和字符串引用来匹配定位函数

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899 | `# -*- coding: utf-8 -*-``import` `idautils``import` `idc``import` `json``import` `re``import` `binascii` `def` `match_signature(func_ea, signature):``"""检查函数是否匹配特征签名"""``ea` `=` `func_ea` `# 检查每条指令``for` `i, expected_bytes` `in` `enumerate``(signature):``# 获取当前指令字节``insn_size` `=` `idc.get_item_size(ea)``if` `insn_size <``=` `0``:``return` `False` `insn_bytes` `=` `idc.get_bytes(ea, insn_size)``hex_bytes` `=` `binascii.hexlify(insn_bytes).decode(``'utf-8'``).upper()``hex_bytes` `=` `" "``.join(hex_bytes[i:i``+``2``]` `for` `i` `in` `range``(``0``,` `len``(hex_bytes),` `2``))` `# 比较指令字节``if` `hex_bytes !``=` `expected_bytes:``return` `False` `# 移动到下一条指令``ea` `=` `idc.next_head(ea, idc.BADADDR)``if` `ea` `=``=` `idc.BADADDR:``return` `False` `return` `True` `def` `match_constants(func_ea, constants):``"""检查函数是否引用了特定常量"""``if` `not` `constants:``return` `True` `for` `ref` `in` `idautils.CodeRefsTo(func_ea,` `0``):``for` `head` `in` `idautils.Heads(ref, ref` `+` `16``):``if` `idc.print_insn_mnem(head)` `=``=` `"LDR"``:``op` `=` `idc.get_operand_value(head,` `1``)``if` `op !``=` `idc.BADADDR:``constant` `=` `idc.get_strlit_contents(op)``if` `constant` `and` `constant` `in` `constants:``return` `True``return` `False` `def` `main():``# 加载特征库``sig_path` `=` `"E:\python_project\il2cpp-project\original_signatures.json"` `try``:``with` `open``(sig_path,` `"r"``) as f:``signatures` `=` `json.load(f)``except` `Exception as e:``print``(``"[-] Error loading signatures: {}"``.``format``(``str``(e)))``return` `# 准备结果``results` `=` `{}` `# 遍历所有函数``for` `func_ea` `in` `idautils.Functions():``func_name` `=` `idc.get_func_name(func_ea)` `# 检查每个目标特征``for` `orig_name, sig_data` `in` `signatures.items():``# 跳过已识别的函数``if` `orig_name` `in` `results:``continue` `# 检查指令签名``if` `not` `match_signature(func_ea, sig_data[``"signature"``]):``continue` `# 检查常量引用``if` `not` `match_constants(func_ea, sig_data[``"constants"``]):``continue` `# 找到匹配``print``(``"[+] Match found: {} -> {}"``.``format``(func_name, orig_name))``results[orig_name]` `=` `{``"obfuscated_name"``: func_name,``"address"``:` `hex``(func_ea),``"original_address"``: sig_data[``"address"``]``}``break` `# 保存结果``output_path` `=` `"E:\python_project\il2cpp-project\matched.json"` `with` `open``(output_path,` `"w"``) as f:``json.dump(results, f, indent``=``2``)` `print``(``"[+] Saved matching results for {} functions"``.``format``(``len``(results)))` `if` `__name__` `=``=` `"__main__"``:``main()` |
|-|-|

最后输出的结果类似如下

```
{
  "il2cpp_class_get_namespace": {
    "original_address": "0xc192d8L",
    "address": "0x1246ba0L",
    "obfuscated_name": "mono_method_full_name"
  },
  "il2cpp_class_get_type": {
    "original_address": "0xc19354L",
    "address": "0x123dd28L",
    "obfuscated_name": "sub_123DD28"
  }
}
```

拿着结果去手动对比验证了一下结果，发现不太准，取特征码和匹配的方式也有点讲究，大家感兴趣可以改下脚本，这个脚本还是有点呆了。

函数少，硬着头皮手动去对比吧，最后结合源码，未混淆的so，混淆的so，得到了如下对应关系，这里纯是体力活，给我看得两眼冒金星，差点原地飞升。

| 12345678910 | `var` `il2cpp_api = {``"il2cpp_class_get_methods"``:0x1245B64,` `// HTPcDxoiHnMqKZdyUYO9uXzP``"il2cpp_method_get_name"``:0x124637C,` `//  HTP4BzjkLc0Ep8KqUM7Hgb il2cpp_class_get_namespace_0 HTP9VACoiunt2ayxTsWY03qPB4_0``"il2cpp_class_get_name"``:0x1245b6c,` `// HTPJfogkGmTA2qHjBLMEQ il2cpp_class_get_name_0 HTPJfogkGmTA2qHjBLMEQ_0``"il2cpp_class_get_type"``:0x1245BEC,` `// HTPn5HAetfvRrFuLaiykb 0000000001245BEC` `"il2cpp_class_get_namespace"``:0x1245b70,` `// HTP9VACoiunt2ayxTsWY03qPB4 il2cpp_class_get_namespace_0 HTP9VACoiunt2ayxTsWY03qPB4_0``"il2cpp_method_get_param"``:0x1246390,` `// HTPf0Gubletcrw75UNLIdAQ 1246390 il2cpp_method_get_param_0 HTPf0Gubletcrw75UNLIdAQ_0``"il2cpp_method_get_param_count"``:0x124638C,` `// HTPUE8G6mnVTpIZ5frhRXklNgu3HL 124638C il2cpp_method_get_param_count_0 HTPUE8G6mnVTpIZ5frhRXklNgu3HL_0``"il2cpp_class_from_type"``:0x1245BE4,` `// HTPKT2qrLb4HBUcxzypYsP+4 1245BE4``};` |
|-|-|

观察了一下，这里的函数名和混淆后的名称长度是一致的，而且前面都是HTP开头，后面的不知道采用了啥加密方式，其实有种思路就是去hook这个混淆的函数偏移，然后打印调用栈，看看会不会有符号解密的地方，然后看看能不能还原它的加密方式，这样我通过未混淆的API经过加密函数不就拿到了混淆的函数了。

| 1234567891011121314151617181920212223242526272829303132333435363738394041 | `// hook调用栈``function` `printStackTrace() {``console.log(``"调用栈:"``);``Thread.backtrace(``this``.context, Backtracer.FUZZY)``.map(DebugSymbol.fromAddress)``.forEach(sym => {``console.log(`  ${sym.name} [${sym.address}]`);``});``}` `// 带符号``function` `detailedStackTrace() {``const backtrace = Thread.backtrace(``this``.context, Backtracer.ACCURATE);``console.log(``"详细调用栈:"``);` `backtrace.forEach((address, i) => {``const symbol = DebugSymbol.fromAddress(address);``const module = Process.findModuleByAddress(address);``if``(module.name ==` `"libil2cpp.so"``) {``console.log(```#${i} ${symbol.name \|\| '???'}`);``console.log(`  地址: ${address}`);``console.log(`  模块: ${module ? module.name :` `'未知模块'``}`);``console.log(`  文件: ${symbol.fileName}:${symbol.lineNumber}`);``console.log(`  偏移: ${address.sub(module.base)}`);``}``});``}` `// 函数反追调用栈``function` `hook_call_stack() {``var` `module = Process.findModuleByName(``"libil2cpp.so"``)``const il2cpp_method_get_name_addr = module.base.add(0x124637C);``var` `l3 = Interceptor.attach(il2cpp_method_get_name_addr, {``onEnter:``function``(args){``detailedStackTrace.call(``this``);``},``onLeave:` `function``(retval) {` `}``})``}` |
|-|-|

**备注：文章发表后，@`breaklink`和@`安卓逆向test`两位大佬在评论区中提示，`il2cpp`的导出函数最终都会被`libunity.so`调用，这里大家可以`dump`出来`libunity.so`，和上面同样的思路进行修复，对比自己编译的`libunity.so`，导出函数的对应关系便一目了然了。**

到了这里其实已经可以用上面提到的`find_il2cpp_api2.js`这个脚本去结合`frida-il2cpp-bridge`来使用了，不过我实操之后发现这两脚本能导出东西，但是打开一看，毛也没有，差点当场吐血。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_F4DRS9CRYNARXZ9.webp)

## global-metadata.dat解密导出

这时候我又想起来前面导出的`glabal-metadata.dat`比原本的小了很多，所以我怀疑dump出来的不完整甚至不对，导致`Il2CppDumper`解析不出来`dump.cs`。兜兜转转又给我干会原地。

我又回去看原本的`glabal-metadata.dat`，是这样的。也是`HTP`开头，和混淆函数名的开头一致，可能一样算法，也可能是加固厂商特有标识。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_J5D3MFFX2QPMUCQ.webp)

头部信息不是标准的`AF 1B B1 FA`。大概率魔改了结构或者加密了。

根据`il2cpp`的源码可以知道，最终会根据`LoadMetaDataFile`这个函数去加载`glabal-metadata.dat`。核心的逻辑如下，

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_H354X9VNNCCTCKZ.webp)

拿着这个关键字`global-metadata.dat`直接去混淆后的so里来搜索字符串，IDA可以通过`Shift+F12`生成字符串表，进而查看这个字符串的交叉引用，很容易就找到了这个加载的位置，其实这里如果对抗的话可以把这个`global-metadata.dat`隐藏加密一下，这样定位起来就又只能通过汇编特征码了。

![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_X39VN99QWHWM3PH.webp)

这段就是加载`global-metadata.dat`的逻辑了

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_PGR4VR9SDMREMUA.webp)

其实到了这里，只需要去hook函数`sub_1238164`，就可以拿到加载之后的文件了，而且经过判断，后续直接对文件头进行解析了，也没有看到可疑的解密操作。所以可以确定这里的`global-metadata.dat`即使被加密了，也是解密过后的，否则无法进行函数头的解析。脚本如下，

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166 | `function` `dump_global_metadata() {``let` `var` `module = Process.findModuleByName(``"libil2cpp.so"``);``const LOAD_METADATA_ADDR_BIAS = 0x1238164;``const LOAD_METADATA_ADDR = module.base.add(LOAD_METADATA_ADDR_BIAS);``console.log(`>>>>>>>>>>>>>>>>>>>>>> attach LOAD_METADATA: ${LOAD_METADATA_ADDR} >>>>>>>>>>>>>>>>>>>>>>>>>`);``Interceptor.attach(LOAD_METADATA_ADDR, {``onEnter:``function``(args){``this``.loaded =` `true``},``onLeave:` `function``(retval) {``// 这个retval其实就是文件句柄指针``if``(``this``.loaded) {``const header = parseMetadataHeader(retval, Il2CppGlobalMetadataHeader);``const fileSize = calculateMetadataSize(header);``const buffer = retval.readByteArray(fileSize);` `const path =` `"/sdcard/Download/global-metadata-decrypted.dat"``;` `new` `File(path,` `"wb"``).write(buffer);``console.log(`数据已保存: ${path}`);``}``}``})``}` `function` `parseMetadataHeader(address) {``let header = {};``let offset = 0;``for` `(const [field, type] of Object.entries(Il2CppGlobalMetadataHeader)) {``if` `(type ===` `'int32'``) {``header[field] = address.add(offset).readS32();``}` `else` `{``// 如果有其他类型，需要扩展``console.error(`Unsupported type: ${type}` `for` `field ${field}`);``header[field] = 0;``}``offset += 4;``}``return` `header;``}` `function` `calculateMetadataSize(header) {``let maxEnd = 0;` `// 检查所有数据段``const segments = [``[header.stringLiteralOffset, header.stringLiteralSize],``[header.stringLiteralDataOffset, header.stringLiteralDataSize],``[header.stringOffset, header.stringSize],``[header.eventsOffset, header.eventsSize],``[header.propertiesOffset, header.propertiesSize],``[header.methodsOffset, header.methodsSize],``[header.parameterDefaultValuesOffset, header.parameterDefaultValuesSize],``[header.fieldDefaultValuesOffset, header.fieldDefaultValuesSize],``[header.fieldAndParameterDefaultValueDataOffset, header.fieldAndParameterDefaultValueDataSize],``[header.fieldMarshaledSizesOffset, header.fieldMarshaledSizesSize],``[header.parametersOffset, header.parametersSize],``[header.fieldsOffset, header.fieldsSize],``[header.genericParametersOffset, header.genericParametersSize],``[header.genericParameterConstraintsOffset, header.genericParameterConstraintsSize],``[header.genericContainersOffset, header.genericContainersSize],``[header.nestedTypesOffset, header.nestedTypesSize],``[header.interfacesOffset, header.interfacesSize],``[header.vtableMethodsOffset, header.vtableMethodsSize],``[header.interfaceOffsetsOffset, header.interfaceOffsetsSize],``[header.typeDefinitionsOffset, header.typeDefinitionsSize],``[header.imagesOffset, header.imagesSize],``[header.assembliesOffset, header.assembliesSize],``[header.fieldRefsOffset, header.fieldRefsSize],``[header.referencedAssembliesOffset, header.referencedAssembliesSize],``[header.attributeDataOffset, header.attributeDataSize],``[header.attributeDataRangeOffset, header.attributeDataRangeSize],``[header.unresolvedIndirectCallParameterTypesOffset, header.unresolvedIndirectCallParameterTypesSize],``[header.unresolvedIndirectCallParameterRangesOffset, header.unresolvedIndirectCallParameterRangesSize],``[header.windowsRuntimeTypeNamesOffset, header.windowsRuntimeTypeNamesSize],``[header.windowsRuntimeStringsOffset, header.windowsRuntimeStringsSize],``[header.exportedTypeDefinitionsOffset, header.exportedTypeDefinitionsSize]``];` `for` `(const [offset, size] of segments) {``// 跳过无效段``if` `(offset === 0 \|\| size === 0)` `continue``;` `const end = offset + size;``if` `(end > maxEnd) maxEnd = end;``}` `// 确保最小大小``if` `(maxEnd < HEADER_SIZE) {``console.log(`[!] 警告: 计算大小(${maxEnd})小于头部大小(${HEADER_SIZE})`);``maxEnd = HEADER_SIZE;``}` `// 向上对齐到4KB 这个可选 我发现不补齐的话和原版的大小是一样的``// const alignedSize = (maxEnd + 0xFFF) & ~0xFFF;``// console.log(`[+] 计算大小: ${maxEnd} 字节 (对齐到 ${alignedSize} 字节)`);` `return` `maxEnd;``}` `const Il2CppGlobalMetadataHeader = {``sanity:` `'int32'``,``version:` `'int32'``,``stringLiteralOffset:` `'int32'``,``stringLiteralSize:` `'int32'``,``stringLiteralDataOffset:` `'int32'``,``stringLiteralDataSize:` `'int32'``,``stringOffset:` `'int32'``,``stringSize:` `'int32'``,``eventsOffset:` `'int32'``,``eventsSize:` `'int32'``,``propertiesOffset:` `'int32'``,``propertiesSize:` `'int32'``,``methodsOffset:` `'int32'``,``methodsSize:` `'int32'``,``parameterDefaultValuesOffset:` `'int32'``,``parameterDefaultValuesSize:` `'int32'``,``fieldDefaultValuesOffset:` `'int32'``,``fieldDefaultValuesSize:` `'int32'``,``fieldAndParameterDefaultValueDataOffset:` `'int32'``,``fieldAndParameterDefaultValueDataSize:` `'int32'``,``fieldMarshaledSizesOffset:` `'int32'``,``fieldMarshaledSizesSize:` `'int32'``,``parametersOffset:` `'int32'``,``parametersSize:` `'int32'``,``fieldsOffset:` `'int32'``,``fieldsSize:` `'int32'``,``genericParametersOffset:` `'int32'``,``genericParametersSize:` `'int32'``,``genericParameterConstraintsOffset:` `'int32'``,``genericParameterConstraintsSize:` `'int32'``,``genericContainersOffset:` `'int32'``,``genericContainersSize:` `'int32'``,``nestedTypesOffset:` `'int32'``,``nestedTypesSize:` `'int32'``,``interfacesOffset:` `'int32'``,``interfacesSize:` `'int32'``,``vtableMethodsOffset:` `'int32'``,``vtableMethodsSize:` `'int32'``,``interfaceOffsetsOffset:` `'int32'``,``interfaceOffsetsSize:` `'int32'``,``typeDefinitionsOffset:` `'int32'``,``typeDefinitionsSize:` `'int32'``,``imagesOffset:` `'int32'``,``imagesSize:` `'int32'``,``assembliesOffset:` `'int32'``,``assembliesSize:` `'int32'``,``fieldRefsOffset:` `'int32'``,``fieldRefsSize:` `'int32'``,``referencedAssembliesOffset:` `'int32'``,``referencedAssembliesSize:` `'int32'``,``attributeDataOffset:` `'int32'``,``attributeDataSize:` `'int32'``,``attributeDataRangeOffset:` `'int32'``,``attributeDataRangeSize:` `'int32'``,``unresolvedIndirectCallParameterTypesOffset:` `'int32'``,``unresolvedIndirectCallParameterTypesSize:` `'int32'``,``unresolvedIndirectCallParameterRangesOffset:` `'int32'``,``unresolvedIndirectCallParameterRangesSize:` `'int32'``,``windowsRuntimeTypeNamesOffset:` `'int32'``,``windowsRuntimeTypeNamesSize:` `'int32'``,``windowsRuntimeStringsOffset:` `'int32'``,``windowsRuntimeStringsSize:` `'int32'``,``exportedTypeDefinitionsOffset:` `'int32'``,``exportedTypeDefinitionsSize:` `'int32'``};` |
|-|-|

这里`Il2CppGlobalMetadataHeader`我是看源码下定义的，如果遇到了头部被魔改的情况，那可能需要进一步跟踪`sub_1238164`的解析函数头部分，我对比了一下原版so和混淆的so之后，发现解析部分是没有差异的，所以确定头部没有被魔改。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_GX68WG5S7KYTYD4.webp)

之后就是拿到了导出之后的`global-metadata-decrypted.dat`文件了，和源文件对比如下。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_MFVB7BDA96QKD7Y.webp)

此时，拿到了修复之后的`.so`和`global-metadata.dat`，送入`Il2CppDumper`，弯弯绕绕还是拿到了导出符号表，如下。`stringliteral.json`和`script.json`这个可以结合`Il2CppDumper-win-v6.7.46`目录下的`ida.py`和`ida_with_struct.py`来帮助`IDA`进行符号解析。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_VY2YH5V7SJP8RXZ.webp)

去`dump.cs`里面翻一下，尝试搜索一些`hero`，`attack`，这类可能的关键字，又是毛也没有，怀疑人生，游戏逻辑藏哪去了？至于`DummyDll`目录下的就是`Csharp`写的了，可以通过`dnSpy`这类工具去反编译，不过游戏逻辑不在里面，就没去看了。

## Lua加载逻辑定位

### tolua_loadbuffer

`lib`目录下还有一个`so`是`libtolua.so`，之前一直没关注它，后来我去搜了一下`Unity`游戏开发，尝试从开发者的视角来看，找到了文章如下：[[讨论][原创]安卓lua解密——opcode修改后dump反编译-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-282259.htm)

原来如此，网游为了方便实现热更，游戏逻辑写到了`Lua`里面。这套娃给我套得已经一愣一愣的，那就是又要去dump这个`lua`脚本呗，通过上面的文章知道`lual_loadbuffer`用来加载`lua`的脚本，那直接hook它就可以了。到这里其实上面反编译`Csharp`的`dump.cs`也起到了作用，我们在`dump.cs`里面去搜索`lual_loadbuffer`，找到了两个函数。这个可能在IDA里面也能搜到，因为我是把反编译之后的字符串通过`ida.py`和`ida_with_struct.py`重建过后去搜的，不知道如果不重建能不能搜到。

| 12345 | `// RVA: 0x1C88B0C Offset: 0x1C88B0C VA: 0x7A4BFCDB0C``public` `static` `extern` `int` `tolua_loadbuffer(IntPtr luaState,` `byte``[] buff,` `int` `size,` `string` `name) { }` `// RVA: 0x1C88A90 Offset: 0x1C88A90 VA: 0x7A4BFCDA90``public` `static` `int` `luaL_loadbuffer(IntPtr luaState,` `byte``[] buff,` `int` `size,` `string` `name) { }` |
|-|-|

根据这个偏移去IDA里面按`G`跳转到指定偏移位置，`tolua_loadbuffer`如下，第一个参数是`lua`虚拟机句柄，第二个参数是文件字节流，第三个参数是文件大小，第四个参数是文件名，第五个参数是方法名。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_PGR7X7DPBUFEGBF.webp)

`luaL_loadbuffer`如下，参数和`tolua_loadbuffer`一致。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_3XN4NB8K94AXETK.webp)

### Lua脚本dump

这里hook函数`tolua_loadbuffer`和`luaL_loadbuffer`都行

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051 | `function` `hook_tolua_loadbuffer() {``const libil2cpp = Module.getBaseAddress(``'libil2cpp.so'``);``const tolua_loadbuffer_offset = 0x1C88B0C;``const tolua_loadbuffer_addr = libil2cpp.add(tolua_loadbuffer_offset);` `Interceptor.attach(tolua_loadbuffer_addr, {``onEnter:` `function``(args) {``this``.buff = args[1];``this``.size = args[2].toInt32();``this``.name = args[3];``this``.method = args[4];``},``onLeave:` `function``(retval) {``if``(``this``.size > 0 &&` `this``.buff &&` `this``.name) {``const decrypted_name = decrypt_name(``this``.name);``const dataStart =` `this``.buff.add(0x20);``const rawData = dataStart.readByteArray(``this``.size);` `const sdcard =` `'/sdcard/Download/lua_dump/'``const filename = decrypted_name.replace(/^@/,` `''``);``const fullPath = sdcard + filename;``const dirPath = fullPath.substring(0, fullPath.lastIndexOf(``'/'``));``mkdirs(dirPath);` `console.log(`${``this``.buff} >> dumping  ${decrypted_name} to ${fullPath}, size: ${``this``.size}`);` `const f =` `new` `File(fullPath,` `'wb'``);``f.write(rawData);``f.close();``}``}``});``}` `const mkdirs = (path) => {``Java.perform(() => {``const File = Java.use(``'java.io.File'``);``const dir = File.$``new``(path);``if` `(!dir.exists()) dir.mkdirs();``});``};` `function` `decrypt_name(encrypted) {``const libil2cpp = Module.getBaseAddress(``'libil2cpp.so'``);``const decrypt_func_offset = 0x123BE38;``const decrypt_func_offset_addr = libil2cpp.add(decrypt_func_offset);` `var` `my_decrypt =` `new` `NativeFunction(decrypt_func_offset_addr,` `'pointer'``, [``'pointer'``]);` `return` `my_decrypt(encrypted).readCString();``}` |
|-|-|

这里留意第一个点，`dataStart`读取的位置偏移了`0x20`，如果不进行偏移，会发现dump出来头部多了`0x20`字节，会影响后面的`lua`反编译。对应如下

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_74CSBUBEDPWSM9V.webp)

另外`name`是加密过的，解密逻辑是下面框起来的函数

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_Z65MHGEKW5DPMC2.webp)

`v5`是name，之后通过`sub_123BE38`处理得到`v10`，然后调用`qword_3153C60`，这里`qword_3153C60`其实是通过上面那个`__fastcall`来延迟加载的一个函数指针。也懒得去研究它怎么解密的了，直接根据这个函数签名自己构建一个`NativeFunction`函数在`js`里主动调用解密。也就是`decrypt_name`的逻辑。

到这里，其实所有的`lua`字节码已经拿到了，大致如下

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_FNAR9WSE9JBFVZA.webp)

不过到了这里还是没有结束，这玩意儿也是编译之后的`bytecode`，送入`lua`虚拟机后可以直接执行，但是你直接看肯定看不懂，这里还是看一下这个字节码的结构。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_FJ9P4JMYKTGKF9S.webp)

这里`1B 4C 4A`开头的是`LuaJit`编译的特征码

![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_VHFHM79EN4VRWVQ.webp)

另外还有一个`Luac`编译器编译后的字节码是这样的，魔术为`1B 4C 75 61`

 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_TBEF9UWZ7DJ2RVC.webp)

### Lua反编译

如果是`Luajit`的字节码，需要通过[marsinator358/luajit-decompiler-v2: LuaJIT bytecode decompiler (github.com)](https://github.com/marsinator358/luajit-decompiler-v2)进行反编译，如果是`Luac`的通过`unluac_2023_12_24.jar`反编译。我这里用的`luajit-decompiler-v2`。这玩意没法批量反编译，搞个脚本反编译，保持原有目录结构。这里如果是魔改的字节码，那么可以参照这篇文章：[[原创]对一手游的自定义 luajit 字节码的研究-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-280217-1.htm)。

`libtolua.so`相关资料

[unity tolua_mob64ca14173efa的技术博客_51CTO博客](https://blog.51cto.com/u_16213712/12539202)

[topameng/tolua_runtime: tolua runtime library (github.com)](https://github.com/topameng/tolua_runtime)

[unity3d中交互对话系统 unity游戏交互_mob64ca1401464d的技术博客_51CTO博客](https://blog.51cto.com/u_16213620/10182376)

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576777879808182 | `import` `os``import` `subprocess``import` `argparse``import` `shutil` `def` `decompile_lua_files(source_dir, decompiler_path, output_root):``"""``递归反编译目录中的所有Lua文件，保持目录结构``:param source_dir: 包含.lua文件的源目录``:param decompiler_path: luajit-decompiler-v2.exe的完整路径``:param output_root: 最终输出根目录``"""``decompiler_dir` `=` `os.path.dirname(decompiler_path)` `# 遍历源目录``for` `root, _, files` `in` `os.walk(source_dir):``for` `file` `in` `files:``source_file` `=` `os.path.join(root,` `file``)` `# 计算相对路径和输出路径``rel_path` `=` `os.path.relpath(root, source_dir)``output_dir` `=` `os.path.join(output_root, rel_path)``final_output` `=` `os.path.join(output_dir,` `file``)` `# 确保输出目录存在``os.makedirs(output_dir, exist_ok``=``True``)` `print``(f``"Decompiling: {source_file} -> {final_output}"``)` `# 构建反编译命令（添加 -s 和 -f 参数）``command` `=` `[``decompiler_path,``source_file,``"-s"``,` `# 静默模式，禁用断言错误弹窗``"-f"``,` `# 强制覆盖现有文件``"-o"``, output_dir` `# 直接输出到目标目录``]` `# 运行反编译器``try``:``subprocess.run(command, check``=``True``)``print``(f``"  √ Successfully decompiled"``)``except` `subprocess.CalledProcessError as e:``print``(f``"  × Error decompiling: {e}"``)``except` `Exception as e:``print``(f``"  × Unexpected error: {e}"``)`  `def` `main():``parser` `=` `argparse.ArgumentParser(description``=``'批量反编译LuaJIT文件'``)``parser.add_argument(``'source_dir'``,` `help``=``'包含.lua文件的源目录'``)``parser.add_argument(``'--decompiler'``, default``=``'luajit-decompiler-v2.exe'``,` `help``=``'反编译器路径 (默认: luajit-decompiler-v2.exe)'``)``parser.add_argument(``'--output'``, default``=``'decompiled_output'``,``help``=``'最终输出目录 (默认: ./decompiled_output)'``)` `args` `=` `parser.parse_args()` `# 获取绝对路径``source_dir` `=` `os.path.abspath(args.source_dir)``decompiler_path` `=` `os.path.abspath(args.decompiler)``output_root` `=` `os.path.abspath(args.output)` `# 检查反编译器是否存在``if` `not` `os.path.isfile(decompiler_path):``print``(f``"Error: Decompiler not found at {decompiler_path}"``)``return` `print``(f``"Source directory: {source_dir}"``)``print``(f``"Using decompiler: {decompiler_path}"``)``print``(f``"Output directory: {output_root}"``)``print``(f``"Using flags: -s (silent assertions) and -f (force overwrite)"``)` `# 创建输出目录``os.makedirs(output_root, exist_ok``=``True``)` `# 执行反编译``decompile_lua_files(source_dir, decompiler_path, output_root)``print``(``"\nDecompilation completed!"``)` `if` `__name__` `=``=` `"__main__"``:``main()` |
|-|-|

最后拿到`Lua`源码如下

![图片描述](https://bbs.kanxue.com/upload/attach/202508/1046559_8NZV6VBFAJRMTEW.webp)

## 分析协议

其实已经能够看到`sproto_crypt`就是这游戏的数据协议加解密了，翻一翻这个目录，通过`sproto`这类关键字，搜索得到 [cloudwu/sproto: Yet another protocol library like google protocol buffers , but simple and fast. (github.com)](https://github.com/cloudwu/sproto)，本质就是将`rpc`传输的数据进行序列化和反序列化。结合文章开头的hook网络`sendto`函数，不难解析出游戏协议，感兴趣的可以往下研究。

到了这里已经耗费了一周时间，至于`一刀999`，目前大部分网游都是服务器端数据为准，改了本地意义也不大。至于脱机，可以说是外挂的终极形态，相当于用其它语言自己实现一套客户端，然后根据资源数量或者事件做一些自动化的决策来和服务端通信，整体的复杂度和自己开发一套端游差不多了，肝疼。

## 总结

本文主要介绍了当前`Unity+Il2cpp+Lua`实现热更新游戏的逆向思路，包含`Frida`反调试绕过，`so`的dump和修复，`global-metadata.dat`的dump和修复，`Lua`脚本的dump和反编译。逆向和安全的对抗始终是魔高一尺，道高一丈，文中很多思路和工具都是站在巨人的肩膀上，长路漫漫，还需上下求索。

---

# 回复

## 回复 by breaklink (#2)

*2025-8-10 18:34*

导出函数最终都会被unity调用来着，所以直接找一个原版的unity对照字符串看一下就知道了

当然我也只遇到过一次，用这种方法可以解决

![image](https://bbs.kanxue.com/upload/attach/202508/756531_SBEYJWUFJYJ5PAJ.webp)

## 回复 by 安卓逆向test (#3)

*2025-8-10 19:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  breaklink](https://bbs.kanxue.com/user-756531.htm)
>
>  导出函数最终都会被unity调用来着，所以直接找一个原版的unity对照字符串看一下就知道了当然我也只遇到过一次，用这种方法可以解决
>
>

没错，我去看了下这个游戏，将libunity.so dump下并修复找到sub_6D3494函数就能看到所有的il2cpp api

![image](https://bbs.kanxue.com/upload/attach/202508/973348_7T4GXTXURDWKQYE.webp)

## 回复 by G33k3r (#4)

*2025-8-10 21:26*

>
> [安卓逆向test](https://bbs.kanxue.com/user-973348.htm)
>
>
>
>
>
>
>
>  breaklink
>
>
>
>  导出函数最终都会被unity调用来着，所以直接找一个原版的unity对照字符串看一下就知道了当然我也只遇到过一次，用这 ...
>
>

大佬来了 荣幸 回去看了一下确实 如果顺序和原版一致的话 直接就对上了 想起来一个个找就肝疼

## 回复 by zZhouQing (#5)

*2025-8-10 21:53*

signature 应该还需要再处理一下重定位的问题才有机会匹配成功。

> 拿着结果去手动对比验证了一下结果，发现不太准，取特征码和匹配的方式也有点讲究，大家感兴趣可以改下脚本，这个脚本还是有点呆了。
>
>
>

关于 sproto 协议的设计部分：

> # [云风的 BLOG](https://blog.codingnow.com/)
>
> 设计一种简化的 protocol buffer 协议
> https://blog.codingnow.com/2014/07/ejoyproto.html
>
>
>

## 回复 by Zepp7289 (#6)

*2025-8-10 23:07*

哈哈，lua他没自定义字节码，不然你至少还得整三天，顺便告诉你LuaJIT Decompiler v2可以直接拖文件夹到exe就行，自动批量跑

## 回复 by zylyy (#7)

*2025-8-10 23:10*

666666666

## 回复 by G33k3r (#8)

*2025-8-11 01:10*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Zepp7289](https://bbs.kanxue.com/user-993285.htm)
>
>  哈哈，lua他没自定义字节码，不然你至少还得整三天，顺便告诉你LuaJIT Decompiler v2可以直接拖文件夹到exe就行，自动批量跑
>
>

哈哈 原来如此 我以为他工具不支持嘞

## 回复 by wx_Huber Barrientos (#9)

*2025-8-11 05:46*

66666

## 回复 by 快乐的小跳蛙 (#10)

*2025-8-11 09:45*

tql，学习一下

## 回复 by kkte (#11)

*2025-8-11 09:56*

mark

## 回复 by jilay (#12)

*2025-8-11 10:12*

mark

## 回复 by 2beNo2 (#13)

*2025-8-11 11:14*

tql，学习一下

## 回复 by G33k3r (#14)

*2025-8-11 12:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  2beNo2](https://bbs.kanxue.com/user-893279.htm)
>
>  tql，学习一下
>
>

看了佬的文章也很强啊

## 回复 by qj111111 (#15)

*2025-8-11 19:16*

用lua dump还原打乱的opcode是一种方法,有些网游如果不提供lua dump函数接口,可以用triton识别出lua opcode
大概原理是
https://github.com/archercreat/titan
这种,过一阵我写篇文章来详细说明

## 回复 by G33k3r (#16)

*2025-8-11 20:51*

>
> [qj111111](https://bbs.kanxue.com/user-822471.htm)
>
>  用lua dump还原打乱的opcode是一种方法,有些网游如果不提供lua dump函数接口,可以用triton识别出lua opcode
> 大概原理是
> https://github.com/ar ...
>
>

期待你的文章 到时候@我 学习一下

## 回复 by fanfall (#17)

*2025-8-11 22:41*

>
> [qj111111](https://bbs.kanxue.com/user-822471.htm)
>
>  用lua dump还原打乱的opcode是一种方法,有些网游如果不提供lua dump函数接口,可以用triton识别出lua opcode
> 大概原理是
> https://github.com/ar ...
>
>

同期待，更新求踢

## 回复 by 胡家二少 (#18)

*2025-8-12 11:00*

无尽冬日这个游戏可以换个方式，从微信小程序入手，解密wasm然后提取dll。再修复下偏移，拿到完整的解密。

## 回复 by 阿杨` (#19)

*2025-8-12 13:36*

看爽了

## 回复 by Light紫星 (#20)

*2025-8-12 16:56*

大佬太厉害了

## 回复 by G33k3r (#21)

*2025-8-12 18:39*

>
> [Light紫星](https://bbs.kanxue.com/user-676827.htm)
>
>  大佬太厉害了
>
>

谦卑求学

## 回复 by G33k3r (#22)

*2025-8-12 18:39*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  阿杨`](https://bbs.kanxue.com/user-982558.htm)
>
>  看爽了
>
>

你能看得懂也不简单

## 回复 by G33k3r (#23)

*2025-8-12 18:40*

>
> [胡家二少](https://bbs.kanxue.com/user-668329.htm)
>
>  无尽冬日这个游戏可以换个方式，从微信小程序入手，解密wasm然后提取dll。再修复下偏移，拿到完整的解密。
>
>

有空研究下

## 回复 by Imxz (#24)

*2025-8-13 13:37*

6666

## 回复 by 阿杨` (#25)

*2025-8-14 12:44*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  G33k3r](https://bbs.kanxue.com/user-1046559.htm)
>
>  你能看得懂也不简单
>
>

看得懂，不会写。拿来用的话没啥问题。哈哈哈哈  之前接了个单子，都没接触过，找帖子，拼在一块，硬生生是把lua解密出来，然后自己修改一份符合要求的lua，然后替换资源，实现的功能![image](https://bbs.kanxue.com/view/img/face/011.gif) 大佬确实np

## 回复 by G33k3r (#26)

*2025-8-14 18:19*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  阿杨`](https://bbs.kanxue.com/user-982558.htm)
>
>  看得懂，不会写。拿来用的话没啥问题。哈哈哈哈 之前接了个单子，都没接触过，找帖子，拼在一块，硬生生是把lua解密出来，然后自己修改一份符合要求的lua，然后替换资源，实现的功能[em_011] 大佬 ...
>
>

学习能力很强 我也是到处搜 哈哈哈 有时候看雪上还是有不少思路的 奈何大佬们有时候一句话我要研究半天

## 回复 by mb_lhxrckiu (#27)

*2025-8-28 00:50*

大牛接着入手呗～

## 回复 by mb_lhxrckiu (#28)

*2025-8-28 00:51*

想合作下可以吗

## 回复 by huangjw (#29)

*2025-8-28 10:47*

niub plus

## 回复 by G33k3r (#30)

*2025-8-28 12:13*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_lhxrckiu](https://bbs.kanxue.com/user-1048958.htm)
>
>  大牛接着入手呗～
>
>

私

## 回复 by mb_lhxrckiu (#31)

*2025-8-28 13:14*

大佬，能接着弄吗

## 回复 by mb_lhxrckiu (#32)

*2025-8-28 13:14*

>
> [胡家二少](https://bbs.kanxue.com/user-668329.htm)
>
>  无尽冬日这个游戏可以换个方式，从微信小程序入手，解密wasm然后提取dll。再修复下偏移，拿到完整的解密。
>
>

哈喽大佬能搞吗

## 回复 by mb_lhxrckiu (#33)

*2025-8-28 13:17*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  G33k3r](https://bbs.kanxue.com/user-1046559.htm)
>
>  私
>
>

WJ686810
大牛我不能发消息给你，上面泡泡

## 回复 by 日暮归途 (#34)

*2025-8-29 23:32*

大佬，你怎么知道global-metadata.dat的魔术头是要替换前8字节，而不是在前面拼接AF 1B B1 FA 1F 00 00 00 ?怎么看出来这个游戏版本号是1F(31)的

## 回复 by G33k3r (#35)

*2025-8-31 10:09*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  日暮归途](https://bbs.kanxue.com/user-1000607.htm)
>
>  大佬，你怎么知道global-metadata.dat的魔术头是要替换前8字节，而不是在前面拼接AF 1B B1 FA 1F 00 00 00 ?怎么看出来这个游戏版本号是1F(31)的
>
>

网易盾的惯用套路，内存中头部做手脚，其实不影响正常解析

## 回复 by KuCha128 (#36)

*2025-9-6 20:53*

甄姬是曹丕的媳妇吧![image](https://bbs.kanxue.com/view/img/face/060.gif)

## 回复 by mryoufx (#37)

*2025-9-8 11:11*

>
> [胡家二少](https://bbs.kanxue.com/user-668329.htm)
>
>  无尽冬日这个游戏可以换个方式，从微信小程序入手，解密wasm然后提取dll。再修复下偏移，拿到完整的解密。
>
>

大佬，请问wasm的解密有学习材料推荐么

## 回复 by mryoufx (#38)

*2025-9-8 11:12*

>
> [胡家二少](https://bbs.kanxue.com/user-668329.htm)
>
>  无尽冬日这个游戏可以换个方式，从微信小程序入手，解密wasm然后提取dll。再修复下偏移，拿到完整的解密。
>
>

## 回复 by 街道办事处 (#39)

*2025-9-11 11:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  G33k3r](https://bbs.kanxue.com/user-1046559.htm)
>
>  学习能力很强 我也是到处搜 哈哈哈 有时候看雪上还是有不少思路的 奈何大佬们有时候一句话我要研究半天
>
>

说实话，我很纠结这到底是以什么一种方式在解决问题。总感觉是知其然，不知其所以然。我也总是东拼西凑的实验，解决问题。大佬一句话，甚至可以玩三五天的。但到最后感觉基础底子太差了，有点方向上的迷茫。

## 回复 by 外交 (#40)

*2025-9-28 20:37*

这个游戏是不是检查谷歌手机？我一个谷歌手机上面安装了面具和MT，其他的还没安装。就没法进游戏。想跟着帖子尝试呢，结果游戏都进不去。

## 回复 by mb_nmqxkune (#41)

*2025-9-29 15:51*

>
> [阿杨`](https://bbs.kanxue.com/user-982558.htm)
>
>  看得懂，不会写。拿来用的话没啥问题。哈哈哈哈 之前接了个单子，都没接触过，找帖子，拼在一块，硬生生是把lua解密出来，然后自己修改一份符合要求的lua，然后替换资源，实现的功能[em_011] 大佬 ...
>
>

有没有大佬最近不忙，来接点活，忙不过来了~

## 回复 by zkbutt (#42)

*2025-11-18 23:40*

太强了这个文章，感谢分享

## 回复 by 掀起你的头盖骨 (#43)

*2025-12-4 18:27*

https://luadec.metaworm.site/这个网站可以直接解lua，但是有些是有加密（我也不确定，可能是自定义解析）这种目前没找到什么好办法

## 回复 by G33k3r (#44)

*2025-12-4 22:14*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  掀起你的头盖骨](https://bbs.kanxue.com/user-850198.htm)
>
>  https://luadec.metaworm.site/这个网站可以直接解lua，但是有些是有加密（我也不确定，可能是自定义解析）这种目前没找到什么好办法
>
>
>

自定义字节码有通杀方法

## 回复 by G33k3r (#45)

*2025-12-4 22:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  街道办事处](https://bbs.kanxue.com/user-1024212.htm)
>
>  说实话，我很纠结这到底是以什么一种方式在解决问题。总感觉是知其然，不知其所以然。我也总是东拼西凑的实验，解决问题。大佬一句话，甚至可以玩三五天的。但到最后感觉基础底子太差了，有点方向上的迷茫。
>
>

我个人理解 这玩意儿一方面比较吃经验 大佬写工具 我们会用会改就行了 二一个也吃理解学习能力 到了底层逃不开操作系统 站在巨人的jb上搞逆向

## 回复 by G33k3r (#46)

*2025-12-4 22:22*

>
> [KuCha128](https://bbs.kanxue.com/user-866562.htm)
>
>  甄姬是曹丕的媳妇吧[em_060]
>
>

不知道谁的媳妇 瞎jb乱套 哈哈哈

## 回复 by xifgg (#47)

*2025-12-5 15:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  G33k3r](https://bbs.kanxue.com/user-1046559.htm)
>
>  自定义字节码有通杀方法
>
>

自定义字节码有通杀方法, 大佬能细说吗？

## 回复 by G33k3r (#48)

*2025-12-7 08:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  xifgg](https://bbs.kanxue.com/user-864403.htm)
>
>  自定义字节码有通杀方法, 大佬能细说吗？
>
>

回头整理分享出来

## 回复 by mb_ggnpkuap (#49)

*2026-1-24 04:08*

大佬，想问问你在dump出global_metadata那步，是在哪个时机进行hook的？我尝试了刚加载il2cpp.so的时候和加载完成后两个时机都不行，不知道为什么没有触发![image](https://bbs.kanxue.com/view/img/face/006.gif)

## 回复 by mb_ggnpkuap (#50)

*2026-1-24 13:31*

大佬，想问问您在dump global_metadata的时机是什么？就是注入之后随便一个时机直接dump吗？我在新版本直接dump好像是不会触发函数的，so里面多了一个某盾的防护，不知道大佬这个版本有没有

## 回复 by git_94730eaydwshawke-gif (#51)

*2026-1-24 19:00*

666

## 回复 by mb_xiammaav (#52)

*2026-3-20 04:07*

大佬能合作吗

## 回复 by 沐仁浴义 (#53)

*2026-4-14 03:22*

也常常觉得自己“曹操媳妇进菜园——甄姬拔菜”。 无敌了。

## 回复 by xxRea (#54)

*2026-4-15 09:15*

真的是太强了，哥![image](https://bbs.kanxue.com/view/img/face/047.gif)

## 回复 by mb_keqtuquo (#55)

*2026-4-15 16:45*

大佬，能不能把逆向出来的lua存个盘，想学习学习
