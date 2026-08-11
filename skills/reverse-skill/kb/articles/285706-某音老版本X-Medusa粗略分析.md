---
title: '[原创]某音老版本X-Medusa粗略分析'
url: https://bbs.kanxue.com/thread-285706.htm
tid: 285706
author: Tubbs
date: '2025-02-22'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-11T08:39:51+00:00'
replies: 15
---

# X-Mdeusa 参数分析

抖音25.0.0六神参数X-Medusa算法还原。首先使用unidbg完成对六神参数的模拟，后面的分析全部基于unidbg模拟执行。

## 详细分析过程

通过unidbg生成一份指令trace日志，所有分析都是为了还原日志中的结果。下面是需要还原的结果：

| 1 | `z7umZ``/``vXMwv4yfz8KW``+``7AgUD30Fyg``/``hdkGDmOvdJAfclrEAFiV``+``HFZIusnoMRcL8Z2tAqqheflnmgn52Voe8r3n7sCdF``/``Lb91FGLuei3wPeId2x9cosbAUOEEH285TnGqDZ9LbYK``+``1GlHr0v0uSlh4N2bSLFvK2ZOrizOGQngjUhr76h``/``0sBDFytAsgOvHWhs2umwyBgbE``/``HavK9dhdzqDmL6lQI4mPvSlYGEkDWIROp6MCPKOCgT``/``jpMaeMDOXaKLC2FR1OzfYJCzw6LG5MZPjpLq1KozOBkSbNASFUKa330``+``zrrigt95EeI7IVqB0c2GB33crIoOV2uZDeOTek7EWtZvdRh5LvZjwb9rwCyYM3SnJrT5NqJMQv3fzaCkZTH``/``gmnSWAoISUW``/``N3CHhD``/``QWNm6AshwT``/``Hvw``/``AUY``+``UFlIk8iz9Uk``=` |
|-|-|

从最后的结果可以看出是一个base64字符串，利用ida插件获取到base64相关函数，然后使用unidbg断点hook base64输入数据和base64结果来判定是否是标准的base64算法。

| 1234567891011121314151617181920212223242526272829 | `// base64 分析``// base64 入参分析``debugger.addBreakPoint(module.base +` `0xbfbf4``,` `new` `BreakPointCallback() {``int` `count =` `0``;``@Override``public` `boolean` `onHit(Emulator<?> emulator,` `long` `address) {``System.out.println(``"call base64 bfbf4 count = "` `+ ++count);``Backend backend = emulator.getBackend();``long` `msgAddr = backend.reg_read(Arm64Const.UC_ARM64_REG_X3).longValue();``long` `msgLen = backend.reg_read(Arm64Const.UC_ARM64_REG_X4).longValue();``byte``[] message = backend.mem_read(msgAddr, msgLen);``System.out.println(``"addr 0x"` `+ Long.toHexString(msgAddr) +` `", length "` `+ msgLen +` `"\n"` `+ bytesToHexString(message));``return` `true``;``}``});``// base64 结果？``debugger.addBreakPoint(module.base +` `0xbfd44``,` `new` `BreakPointCallback() {``int` `count =` `0``;``@Override``public` `boolean` `onHit(Emulator<?> emulator,` `long` `address) {``System.out.println(``"call base64 bfd44 count = "` `+ ++count);``Backend backend = emulator.getBackend();``long` `resAddr = backend.reg_read(Arm64Const.UC_ARM64_REG_X0).longValue();``long` `resLen = backend.reg_read(Arm64Const.UC_ARM64_REG_X1).longValue();``byte``[] result = backend.mem_read(resAddr, resLen);``System.out.println(``new` `String(result));``return` `true``;``}``});` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_BKFC6G52KGHVQEC.webp)

利用上面hook结果验证base64是标准的，并且得到了base64之前medusa结果存储的内存地址，方便后面traceWrite分析。将medusa解base64的到如下字节：

| 1 | `cf bb a6` `67` `fb d7` `33` `0b` `f8 c9 fc fc` `29` `6f` `bb` `02` `05` `03` `df` `41` `72` `83` `f8` `5d` `90` `60` `e6` `3a` `f7` `49` `01` `f7` `25` `ac` `40` `05` `89` `5f` `87` `15` `92` `2e` `b2` `7a` `0c` `45` `c2 fc` `67` `6b` `40` `aa a8` `5e` `7e` `59` `e6` `82` `7e` `76` `56` `87` `bc af` `79` `fb b0` `27` `45` `fc b6 fd d4` `51` `8b` `b9 e8 b7 c0 f7` `88` `77` `6c` `7d` `72` `8b` `1b` `01` `43` `84` `10` `7d` `bc e5` `39` `c6 a8` `36` `7d` `2d` `b6` `0a` `fb` `51` `a5` `1e` `bd` `2f` `d2 e4 a5` `87` `83` `76` `6d` `22` `c5 bc ad` `99` `3a` `b8 b3` `38` `64` `27` `82` `35` `21` `af be a1 ff` `4b` `01` `0c` `5c` `ad` `02` `c8` `0e` `bc` `75` `a1 b3` `6b` `a6 c3` `20` `60` `6c` `4f` `c7` `6a` `f2 bd` `76` `17` `73` `a8` `39` `8b` `ea` `54` `08` `e2` `63` `ef` `4a` `56` `06` `12` `40` `d6` `21` `13` `a9 e8 c0` `8f` `28` `e0 a0` `4f` `f8 e9` `31` `a7` `8c` `0c` `e5 da` `28` `b0 b6` `15` `1d` `4e` `cd f6` `09` `0b` `3c` `3a` `2c` `6e` `4c` `64` `f8 e9` `2e` `ad` `4a` `a3` `33` `81` `91` `26` `cd` `01` `21` `54` `29` `ad f7 d3 ec eb ae` `28` `2d` `f7` `91` `1e` `23` `b2` `15` `a8` `1d` `1c` `d8` `60` `77` `dd ca c8 a0 e5` `76` `b9` `90` `de` `39` `37` `a4 ec` `45` `ad` `66` `f7` `51` `87` `92` `ef` `66` `3c` `1b` `f6 bc` `02` `c9` `83` `37` `4a` `72` `6b` `4f` `93` `6a` `24` `c4` `2f` `dd fc da` `0a` `46` `53` `1f` `f8` `26` `9d` `25` `80` `a0` `84` `94` `5b` `f3` `77` `08` `78` `43` `fd` `05` `8d` `9b` `a0` `2c` `87` `04` `ff` `1e` `fc` `3f` `01` `46` `3e` `50` `59` `48` `93` `c8 b3 f5` `49` |
|-|-|

接下来则需要分析上面字节的来源，通过之前的线索直接traceWrite内存区域得到如下结果：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_NV64PCS9AM5TZWS.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_TC6X5URXSCP8TU7.webp)

从上图中可以看出trace内存指示的位置和LR都不是直接写内存的地方，之前没遇到过这种情况，不知道这里是unidbg的缺陷还是app的什么策略，不过问题不大，既然trace不到具体的写内存过程，那就写hook函数时刻判断内存找到内存变化的瞬间，然后利用unidbg单步调试，数据绝对不会凭空出现在内存里。

| 1234567891011121314151617181920212223 | `emulator.getBackend().hook_add_new(``new` `CodeHook() {``@Override``public` `void` `hook(Backend backend,` `long` `address,` `int` `size, Object user) {``long` `memAddr = 0x4069a000L;``byte``[] buf = backend.mem_read(memAddr,` `8``);``String hexStr = bytesToHexString(buf);``System.out.println(``"[0x"` `+ Long.toHexString(address) +` `"] "` `+ hexStr);``if` `(buf[``0``] !=` `0``) {``System.exit(``0``);``}` `}` `@Override``public` `void` `onAttach(UnHook unHook) {` `}` `@Override``public` `void` `detach() {` `}``}, module.base, module.base + module.size,` `null``);` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_VK8JYAQZNBNPGVV.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_UQJQCYJWJGQ5GGM.webp)

trace之后确认不是unidbg的问题，traceWrite结果是准确的，并且从上面的trace结果可以可以看出从pc地址有个变化，接着内存数据就发生了变化，在trace 日志中也能找到证明，接下来则是想办法让unidbg在这里断下

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_7X7MYX7QNU3TQTY.webp)

很简单保持前面的代码不动，计数调用次数断下即可：

| 123456789101112 | `// base64 输入数据内存变化定位``debugger.addBreakPoint(module.base +` `0x0d19d8``,` `new` `BreakPointCallback() {``int` `count =` `0``;``@Override``public` `boolean` `onHit(Emulator<?> emulator,` `long` `address) {``System.out.println(``"call 0x0d19d8 count "` `+ ++count);``if` `(count ==` `159``) {``return` `false``;``}``return` `true``;``}``});` |
|-|-|

断下之后开始单步调试

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_D5AWUY66PJDVSVU.webp)

从上图中可以看出先拷贝进去了20字节并且来源的地址也都知道了，其实将之前的trace长度更改到全长326 或者是大于22字节也同样能看出medusa base64输入参数的分布。**medusa base64输入是三部分拷贝进来的，第一部分是20字节，第二部分是2字节，第三部分则是剩下的所有。** 具体分析方式也是重复上面的步骤而已。

| 12345 | `cf bb a6` `67` `fb d7` `33` `0b` `f8 c9 fc fc` `29` `6f` `bb` `02` `05` `03` `df` `41` `72` `83` `f8` `5d` `90` `60` `e6` `3a` `f7` `49` `01` `f7` `25` `ac` `40` `05` `89` `5f` `87` `15` `92` `2e` `b2` `7a` `0c` `45` `c2 fc` `67` `6b` `40` `aa a8` `5e` `7e` `59` `e6` `82` `7e` `76` `56` `87` `bc af` `79` `fb b0` `27` `45` `fc b6 fd d4` `51` `8b` `b9 e8 b7 c0 f7` `88` `77` `6c` `7d` `72` `8b` `1b` `01` `43` `84` `10` `7d` `bc e5` `39` `c6 a8` `36` `7d` `2d` `b6` `0a` `fb` `51` `a5` `1e` `bd` `2f` `d2 e4 a5` `87` `83` `76` `6d` `22` `c5 bc ad` `99` `3a` `b8 b3` `38` `64` `27` `82` `35` `21` `af be a1 ff` `4b` `01` `0c` `5c` `ad` `02` `c8` `0e` `bc` `75` `a1 b3` `6b` `a6 c3` `20` `60` `6c` `4f` `c7` `6a` `f2 bd` `76` `17` `73` `a8` `39` `8b` `ea` `54` `08` `e2` `63` `ef` `4a` `56` `06` `12` `40` `d6` `21` `13` `a9 e8 c0` `8f` `28` `e0 a0` `4f` `f8 e9` `31` `a7` `8c` `0c` `e5 da` `28` `b0 b6` `15` `1d` `4e` `cd f6` `09` `0b` `3c` `3a` `2c` `6e` `4c` `64` `f8 e9` `2e` `ad` `4a` `a3` `33` `81` `91` `26` `cd` `01` `21` `54` `29` `ad f7 d3 ec eb ae` `28` `2d` `f7` `91` `1e` `23` `b2` `15` `a8` `1d` `1c` `d8` `60` `77` `dd ca c8 a0 e5` `76` `b9` `90` `de` `39` `37` `a4 ec` `45` `ad` `66` `f7` `51` `87` `92` `ef` `66` `3c` `1b` `f6 bc` `02` `c9` `83` `37` `4a` `72` `6b` `4f` `93` `6a` `24` `c4` `2f` `dd fc da` `0a` `46` `53` `1f` `f8` `26` `9d` `25` `80` `a0` `84` `94` `5b` `f3` `77` `08` `78` `43` `fd` `05` `8d` `9b` `a0` `2c` `87` `04` `ff` `1e` `fc` `3f` `01` `46` `3e` `50` `59` `48` `93` `c8 b3 f5` `49` |
|-|-|

将上面的部分按照前面分析完成分割，接下来先追主体数据来源，将之前的trace中内存首字节变化程序退出的语句注释掉，并将前面`count == 159` 的条件更改为`count >= 159` 那么接下来的第三个X1对应的地址就是主体部分的来源`0x40695280`。接下来开始分析此处内存数据的来源, 还是traceWrite得到如下结果：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_T4FFJ6C4G7RDYG9.webp)

对应的是libc中的函数，通过LR地址发现是memcpy系统调用，这里直接偷懒到日志文件中搜索，如果有足够耐心前面也可以不调试，单个字节在trace日志里搜索。这里直接搜索对应内存地址：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_7K7KW8BABHNX8HZ.webp)

从上面可以看出只有127个结果，倒着看在上图位置发现首字节，搜索那句pc值：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_23BJN6SH6658DY5.webp)

查看这句附近的汇编指令能发现下面规律：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_3HUYFTCBYP39ZT6.webp)

第三部分的数据是通过异或得到的：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_JDUAAVJBWSUCKHB.webp)

将搜索结果拿出来部分进行分析

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950 | `0x84` `^` `0x7c` `=` `0xf8``0xe7` `^` `0xba` `=` `0x5d``0x5`  `^` `0x95` `=` `0x90``0xc7` `^` `0xa7` `=` `0x60``0x95` `^` `0x73` `=` `0xe6``0x58` `^` `0x62` `=` `0x3a``0x26` `^` `0xd1` `=` `0xf7``0xa3` `^` `0xea` `=` `0x49``0x16` `^` `0x17` `=` `0x1``0xc6` `^` `0x31` `=` `0xf7``0x4c` `^` `0x69` `=` `0x25``0x11` `^` `0xbd` `=` `0xac``0x69` `^` `0x29` `=` `0x40``0x53` `^` `0x56` `=` `0x5``0xe5` `^` `0x6c` `=` `0x89``0xce` `^` `0x91` `=` `0x5f` `0x84` `^` `0x3`  `=` `0x87``0xe7` `^` `0xf2` `=` `0x15``0x5`  `^` `0x97` `=` `0x92``0xc7` `^` `0xe9` `=` `0x2e``0x95` `^` `0x27` `=` `0xb2``0x58` `^` `0x22` `=` `0x7a``0x26` `^` `0x2a` `=` `0xc``0xa3` `^` `0xe6` `=` `0x45``0x16` `^` `0xd4` `=` `0xc2``0xc6` `^` `0x3a` `=` `0xfc``0x4c` `^` `0x2b` `=` `0x67``0x11` `^` `0x7a` `=` `0x6b``0x69` `^` `0x29` `=` `0x40``0x53` `^` `0xf9` `=` `0xaa``0xe5` `^` `0x4d` `=` `0xa8``0xce` `^` `0x90` `=` `0x5e` `0x84` `^` `0xfa` `=` `0x7e``0xe7` `^` `0xbe` `=` `0x59``0x5`  `^` `0xe3` `=` `0xe6``0xc7` `^` `0x45` `=` `0x82``0x95` `^` `0xeb` `=` `0x7e``0x58` `^` `0x2e` `=` `0x76``0x26` `^` `0x70` `=` `0x56``0xa3` `^` `0x24` `=` `0x87``0x16` `^` `0xaa` `=` `0xbc``0xc6` `^` `0x69` `=` `0xaf``0x4c` `^` `0x35` `=` `0x79``0x11` `^` `0xea` `=` `0xfb``0x69` `^` `0xd9` `=` `0xb0``0x53` `^` `0x74` `=` `0x27``0xe5` `^` `0xa0` `=` `0x45``0xce` `^` `0x32` `=` `0xfc` |
|-|-|

从上面可以看出呈现出一定的规律，都是同一个16字节数组异或后得到最后结果，先分析每组变化的字节来源。直接在附近搜索0x7c:

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_A9Q29W3F2DBKACY.webp)

在临近位置发现上图所示的计算过程，继续向下翻能发现会出现和上图所示差不多的模式，都是每四个字节一组的计算，这里可能是有个循环或是是什么规律，根据之前traceWrite第三部分地址得到的数据往前一层开始大致确定带有上面模式的开始，然后拿出来单独分析。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_RPG3HFRUKC8BFV9.webp)

| 123456789101112 | `大致就是从上面截图这部分开始，取``16``字节顺着日志分析数据变化，总结出下面的变化` `4c` `9d` `94` `f4` `66` `ec` `1c` `26` `d5 b2` `52` `46` `bd bb d4` `30` `接着与``0xbffbb40` `开始的数据异或，前``16``字节` `ea` `2b` `04` `5b` `11` `bf` `23` `64` `83` `9e` `6a` `b2` `7f` `95` `a9 df` `异或之后得到``a6 b6` `90` `af` `77` `53` `3f` `42` `56` `2c` `38` `f4 c2` `2e` `7d` `ef` `这部分变化也能从第三部分的内存变化中看出来` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_FR2NVP2ET7QR45E.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_MMRA7MMU8X8J2HK.webp)

| 1234567891011121314151617 | `a6 b6` `90` `af` `77` `53` `3f` `42` `56` `2c` `38` `f4 c2` `2e` `7d` `ef` `将上面异或结果转成` `4` `*` `4` `的矩阵` `a6 b6` `90` `af``77` `53` `3f` `42``56` `2c` `38` `f4``c2` `2e` `7d` `ef` `按照上面的列查表` `0xdfed0` `38` `5f` `fb` `9e` `a0 e4 c0` `44` `50` `b3` `64` `e7` `75` `b7` `89` `7b` `38` `5f` `fb` `9e``a0 e4 c0` `44``50` `b3` `64` `e7``75` `b7` `89` `7b` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_6MPNBQD58EZG9G3.webp)

| 1234567891011 | `按照上图所示的变化重新排序数据``00` `b3` `89` `44` `00` `b7 fb e7` `00` `5f` `c0` `7b` `00` `e4` `64` `9e` `38` `b3` `89` `44` `a0 b7 fb e7` `50` `5f` `c0` `7b` `75` `e4` `64` `9e` `38` `b3` `89` `44``a0 b7 fb e7` `50` `5f` `c0` `7b``75` `e4` `64` `9e` `明显看着就是行变化，已经看着非常像是aes算法了` |
|-|-|

通过上面的日志分析，这部分已经看着非常像是的aes了，但是字节代换部分表是固定的，更可能是个aes算法的变种魔改。如果是aes的魔改那么行变换之后就是列混淆部分了。下面部分日志通过脚本筛选出读取内存和一些数学运算：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_HN73WKSQKMTV8WX.webp)

上面只是部分被筛选出来的日志，选择其中一部分进行分析：

| 1234567891011121314151617181920212223242526272829303132333435 | `接着上面行变换之后的矩阵` `38` `b3` `89` `44``a0 b7 fb e7` `50` `5f` `c0` `7b``75` `e4` `64` `9e` `将日志中出现的计算总结如下``第``1``列第``1``字节计算总结``0x38` `<<` `1` `=` `0x70``0x70` `^` `0` `=` `0x70` `第``1``列第``2``字节计算总结``0xa0` `^` `0` `=` `0xa0``0xa0` `<<` `1` `=` `0x140` `&` `0xff` `=` `0x40``0x40` `^` `0x1b` `=` `0x5b``0x5b` `^` `0xa0` `=` `0xfb` `第``1``列第``3``字节计算总结``0x50` `^` `0x0` `=` `0x50``0x50` `<<` `1` `=` `0xa0` `第``1``列第``4``字节计算总结``0x75` `^` `0x0` `=` `0x75``0x75` `<<` `1` `=` `0xea` `总计算``0x70` `^` `0xfb` `=` `0x8b``0x50` `^` `0x8b` `=` `0xdb``0xdb` `^` `0x75` `=` `0xae` `将上面的计算可以汇总成一句计算``lsl_one_bit(col[``0``] ^` `0x0``) ^ lsl_one_bit(col[``1``] ^` `0x0``) ^ col[``1``] ^ col[``2``] ^ col[``3``]` `这个计算逻辑出来之后就非常熟悉了` |
|-|-|

根据上面的计算分析，多分析几组日志中的数据就更能确定是aes中列混淆的计算了。直接上网或者是利用大模型搞个列混淆代码，连着之前的逻辑一起写个python代码测试：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576777879808182838485868788899091929394 | `message` `=` `bytes.fromhex(``"4c9d94f466ec1c26d5b25246bdbbd430"``)``fixed_bytes_1` `=` `bytes.fromhex(``"ea2b045b11bf2364839e6ab27f95a9df84e705c7955826a316c64c116953e5ce62028a3df75aac9ee19ce08f88cf0541"``)` `# 这里应该是异或初始向量``state` `=` `bytes([a ^ b` `for` `a, b` `in` `zip``(message, cycle(fixed_bytes_1))])``print``(``"异或初始化向量: "` `+` `state.``hex``())` `# 这个是计算后需要查的表，直接从ida中复制出来的``# 这部分应该是对应着查表， 字节代换的过程``dfed0_table` `=` `[``0x2E``,` `0x5C``,` `0x55``,` `0xED``,` `0x1B``,` `0xDA``,` `0xA``,` `0x79``,` `0x28``,``0x69``,` `0x57``,` `0xFE``,` `0x68``,` `0x3A``,` `0xDE``,` `0xAC``,` `0x90``,` `0xF9``,``0xC1``,` `0xE1``,` `0xC3``,` `0x8B``,` `0x7F``,` `0x59``,` `0x26``,` `0xCA``,` `0x13``,``0xBB``,` `0x11``,` `0x37``,` `0x39``,` `0x21``,` `0xEB``,` `0x9A``,` `0xFF``,` `0x5E``,``0x42``,` `0x33``,` `0xBE``,` `0x51``,` `0x8D``,` `0x40``,` `0x1E``,` `0x91``,` `0xB3``,``0x85``,` `0xB7``,` `0xCD``,` `0xDC``,` `0x27``,` `0x92``,` `0x83``,` `0x87``,` `0x3F``,``0xE6``,` `0x4A``,` `0x64``,` `0x56``,` `0x8C``,` `0xA1``,` `0x76``,` `0xD2``,` `0xFD``,``0xC0``,` `0x63``,` `0x18``,` `0x44``,` `0x1A``,` `0x9F``,` `0x61``,` `0xCB``,` `0x6E``,``0x67``,` `0x29``,` `0xAF``,` `0xB8``,` `0x54``,` `0x60``,` `0xDB``,` `0x97``,` `0xE8``,``0xA3``,` `0xC9``,` `0xE4``,` `0``,` `0xEC``,` `0x50``,` `0x17``,` `0xBD``,` `0x2A``,``0xB6``,` `0x8E``,` `0x3B``,` `0x46``,` `0x65``,` `0xA6``,` `0x7A``,` `0x96``,` `0xD3``,``0x72``,` `0x12``,` `0xBC``,` `0x20``,` `0x4D``,` `0x7C``,` `0xFA``,` `0x15``,` `0xC``,``0x41``,` `0x9B``,` `0xAA``,` `9``,` `0xF8``,` `0xF0``,` `0x5D``,` `0x84``,` `0xFC``,``0xE``,` `0xD6``,` `0xA0``,` `0xF2``,` `0xEF``,` `0x4E``,` `0x10``,` `0xBF``,` `0x89``,``0x6D``,` `0x9C``,` `0x98``,` `6``,` `0xC2``,` `0xC7``,` `0x5A``,` `0xF1``,` `0xB1``,``0xA5``,` `0xF4``,` `0xB9``,` `0xA2``,` `0xF5``,` `0x78``,` `0xAE``,` `0x3D``,` `0x24``,``0xFB``,` `0x30``,` `0x9D``,` `0xD8``,` `0xA4``,` `0x6F``,` `0x1F``,` `0x49``,` `0xD0``,``0x95``,` `0x3C``,` `0x99``,` `0xBA``,` `0x23``,` `0xEA``,` `0x53``,` `0x14``,` `0x2B``,``0xE0``,` `0xD``,` `0x5B``,` `0x94``,` `0x38``,` `0x4B``,` `0x1C``,` `0xCC``,` `0x4C``,``0x88``,` `0x2C``,` `0x81``,` `0xF3``,` `0x9E``,` `0x70``,` `0xF6``,` `0x58``,` `0x45``,``0xB0``,` `0x35``,` `0x5F``,` `0x6A``,` `0x8A``,` `0x32``,` `0x19``,` `0x34``,` `0xDD``,``0x4F``,` `0x7D``,` `0x36``,` `0xEE``,` `0xAB``,` `0x75``,` `0x71``,` `0xF``,` `0x25``,``0xB5``,` `0xE9``,` `0x47``,` `0xF7``,` `0xCF``,` `0x43``,` `0x6C``,` `0xC6``,` `0x8F``,``0x31``,` `0xB2``,` `0x2F``,` `0xD9``,` `0x1D``,` `0xC4``,` `0xA8``,` `0xD4``,` `0x93``,``0x73``,` `0xA7``,` `0x82``,` `0x77``,` `0x66``,` `8``,` `0x6B``,` `1``,` `0xA9``,` `0xE3``,``0xD5``,` `0xAD``,` `0xD7``,` `0xE5``,` `0x62``,` `0x86``,` `3``,` `0x22``,` `0xB4``,``0x2D``,` `0xD1``,` `0xDF``,` `0x3E``,` `0x7B``,` `0x52``,` `0xE2``,` `0x7E``,` `0x48``,``0xE7``,` `0xB``,` `4``,` `0xC8``,` `0x16``,` `0xC5``,` `2``,` `0xCE``,` `7``,` `0x74``,` `0x80``,``5``,` `0x8D``,` `1``,` `2``,` `4``,` `8``,` `0x10``,` `0x20``,` `0x40``,` `0x80``,` `0x1B``,``0x36``,` `0``,` `0``,` `0``,` `0``,` `0``,``]` `state_1` `=` `[dfed0_table[a]` `for` `a` `in` `state]``print``(``"查表结果: "` `+` `bytes(state_1).``hex``())`  `# 修改行变换到和日志中的结果一致``def` `shift_rows(s):``s[``0``][``1``], s[``1``][``1``], s[``2``][``1``], s[``3``][``1``]` `=` `s[``2``][``1``], s[``3``][``1``], s[``0``][``1``], s[``1``][``1``]``s[``0``][``2``], s[``1``][``2``], s[``2``][``2``], s[``3``][``2``]` `=` `s[``3``][``2``], s[``0``][``2``], s[``1``][``2``], s[``2``][``2``]``s[``0``][``3``], s[``1``][``3``], s[``2``][``3``], s[``3``][``3``]` `=` `s[``1``][``3``], s[``2``][``3``], s[``3``][``3``], s[``0``][``3``]` `def` `print_matrix_hex(matrix):``for` `row` `in` `matrix:``print``(``' '``.join([``'{:02x}'``.``format``(x)` `for` `x` `in` `row]))` `state_1` `=` `np.asarray(state_1).reshape(``4``,` `4``)``print_matrix_hex(state_1)``shift_rows(state_1)``print``(``"移位结果: "``)``print_matrix_hex(state_1)` `# 下面则需要进行列混淆``def` `gf_multiply(a, b):``p` `=` `0``counter` `=` `0``while` `b:``if` `b &` `1``:``p ^``=` `a``a <<``=` `1``if` `a &` `0x100``:``a ^``=` `0x11B``b >>``=` `1``counter` `+``=` `1``return` `p`  `def` `mix_columns(state):``new_state` `=` `[[``0` `for` `_` `in` `range``(``4``)]` `for` `_` `in` `range``(``4``)]``mix_matrix` `=` `[``[``0x02``,` `0x03``,` `0x01``,` `0x01``],``[``0x01``,` `0x02``,` `0x03``,` `0x01``],``[``0x01``,` `0x01``,` `0x02``,` `0x03``],``[``0x03``,` `0x01``,` `0x01``,` `0x02``]``]``for` `col` `in` `range``(``4``):``for` `row` `in` `range``(``4``):``for` `k` `in` `range``(``4``):``new_state[row][col] ^``=` `gf_multiply(mix_matrix[row][k], state[k][col])``return` `new_state` `state_1` `=` `mix_columns(state_1)``print``(``"列混淆结果: "``)``print_matrix_hex(state_1)` |
|-|-|

验证之后更加确定是aes魔改的算法了，后面的日志都可以带入aes计算逻辑了，而且发现只是计算的轮数被减少了，只保留了3轮计算，并且加密使用的密钥和iv是固定的，并且是固定字节的md5的结果这里和X-Argus AES部分类似，而且和海外版也保持一致所以还原算法时，轮钥和初始化向量可以固定。下面给出随手还原验证代码, 是分析过程脚本，部分注释不准确：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156 | `# 此字节数组前16字节看成是iv，中间16字节看成是轮钥，最后16字节看成是固定字节``fixed_bytes` `=` `fixed_bytes_1` `=` `bytes.fromhex(``"ea2b045b11bf2364839e6ab27f95a9df84e705c7955826a316c64c116953e5ce62028a3df75aac9ee19ce08f88cf0541"``)` `# 这里显然还是有填充的``# a6859ef7500129091896b693bda37a64``message_hex_str` `=` `"a6859ef7500129091896b693bda37a6484bc760816db6c7c7ee4d68af2b5327acb93cbaa1068e3970264df8a0437c4cebda4a78aa358a5c3c79b532abeba15788f80dd7af08eebb976deb674ed5a014a4d4bee0be3e8bf4a71d8bc3fee832aa16c6315c8abad40a1163ff89caccf44197018cd7de9dcac8b49864f0f97adfc4eea9da3f4b93497badb9b51403b2f7d34df872cc79aed512673e6335feee72db6b512885638b4e2a28668e185e3016d7f76aa10084c26c095e995d990c91e93895faccdfe79b609354bda5fdd4588715a0e07f53bea3536a940935dccf3bf9889608bc6d951554d7ea1ac333cb2ac95e7f1fbe572c3f750f6af3804d650f372dfc9635c649dfa9ea9901b257976cad8ab8393070aea4288a30cf2fd77e6fffd77e6ff514a0c0c0c0c0c0c0c0c0c0c0c0c"``message` `=` `bytes.fromhex(message_hex_str)` `print``(message[:``-``12``].``hex``())``# TODO: 后买再研究padding问题``# message_paded = pad(message, 16)``# print(message_paded.hex())`   `def` `print_matrix_hex(matrix):``for` `row` `in` `matrix:``print``(``' '``.join([``'{:02x}'``.``format``(x)` `for` `x` `in` `row]))`  `# 下面是aes魔改的加密算法` `# 这个是计算后需要查的表，直接从ida中复制出来的``# 这部分应该是对应着查表， 字节代换的过程``dfed0_table` `=` `[``0x2E``,` `0x5C``,` `0x55``,` `0xED``,` `0x1B``,` `0xDA``,` `0xA``,` `0x79``,` `0x28``,``0x69``,` `0x57``,` `0xFE``,` `0x68``,` `0x3A``,` `0xDE``,` `0xAC``,` `0x90``,` `0xF9``,``0xC1``,` `0xE1``,` `0xC3``,` `0x8B``,` `0x7F``,` `0x59``,` `0x26``,` `0xCA``,` `0x13``,``0xBB``,` `0x11``,` `0x37``,` `0x39``,` `0x21``,` `0xEB``,` `0x9A``,` `0xFF``,` `0x5E``,``0x42``,` `0x33``,` `0xBE``,` `0x51``,` `0x8D``,` `0x40``,` `0x1E``,` `0x91``,` `0xB3``,``0x85``,` `0xB7``,` `0xCD``,` `0xDC``,` `0x27``,` `0x92``,` `0x83``,` `0x87``,` `0x3F``,``0xE6``,` `0x4A``,` `0x64``,` `0x56``,` `0x8C``,` `0xA1``,` `0x76``,` `0xD2``,` `0xFD``,``0xC0``,` `0x63``,` `0x18``,` `0x44``,` `0x1A``,` `0x9F``,` `0x61``,` `0xCB``,` `0x6E``,``0x67``,` `0x29``,` `0xAF``,` `0xB8``,` `0x54``,` `0x60``,` `0xDB``,` `0x97``,` `0xE8``,``0xA3``,` `0xC9``,` `0xE4``,` `0``,` `0xEC``,` `0x50``,` `0x17``,` `0xBD``,` `0x2A``,``0xB6``,` `0x8E``,` `0x3B``,` `0x46``,` `0x65``,` `0xA6``,` `0x7A``,` `0x96``,` `0xD3``,``0x72``,` `0x12``,` `0xBC``,` `0x20``,` `0x4D``,` `0x7C``,` `0xFA``,` `0x15``,` `0xC``,``0x41``,` `0x9B``,` `0xAA``,` `9``,` `0xF8``,` `0xF0``,` `0x5D``,` `0x84``,` `0xFC``,``0xE``,` `0xD6``,` `0xA0``,` `0xF2``,` `0xEF``,` `0x4E``,` `0x10``,` `0xBF``,` `0x89``,``0x6D``,` `0x9C``,` `0x98``,` `6``,` `0xC2``,` `0xC7``,` `0x5A``,` `0xF1``,` `0xB1``,``0xA5``,` `0xF4``,` `0xB9``,` `0xA2``,` `0xF5``,` `0x78``,` `0xAE``,` `0x3D``,` `0x24``,``0xFB``,` `0x30``,` `0x9D``,` `0xD8``,` `0xA4``,` `0x6F``,` `0x1F``,` `0x49``,` `0xD0``,``0x95``,` `0x3C``,` `0x99``,` `0xBA``,` `0x23``,` `0xEA``,` `0x53``,` `0x14``,` `0x2B``,``0xE0``,` `0xD``,` `0x5B``,` `0x94``,` `0x38``,` `0x4B``,` `0x1C``,` `0xCC``,` `0x4C``,``0x88``,` `0x2C``,` `0x81``,` `0xF3``,` `0x9E``,` `0x70``,` `0xF6``,` `0x58``,` `0x45``,``0xB0``,` `0x35``,` `0x5F``,` `0x6A``,` `0x8A``,` `0x32``,` `0x19``,` `0x34``,` `0xDD``,``0x4F``,` `0x7D``,` `0x36``,` `0xEE``,` `0xAB``,` `0x75``,` `0x71``,` `0xF``,` `0x25``,``0xB5``,` `0xE9``,` `0x47``,` `0xF7``,` `0xCF``,` `0x43``,` `0x6C``,` `0xC6``,` `0x8F``,``0x31``,` `0xB2``,` `0x2F``,` `0xD9``,` `0x1D``,` `0xC4``,` `0xA8``,` `0xD4``,` `0x93``,``0x73``,` `0xA7``,` `0x82``,` `0x77``,` `0x66``,` `8``,` `0x6B``,` `1``,` `0xA9``,` `0xE3``,``0xD5``,` `0xAD``,` `0xD7``,` `0xE5``,` `0x62``,` `0x86``,` `3``,` `0x22``,` `0xB4``,``0x2D``,` `0xD1``,` `0xDF``,` `0x3E``,` `0x7B``,` `0x52``,` `0xE2``,` `0x7E``,` `0x48``,``0xE7``,` `0xB``,` `4``,` `0xC8``,` `0x16``,` `0xC5``,` `2``,` `0xCE``,` `7``,` `0x74``,` `0x80``,``5``,` `0x8D``,` `1``,` `2``,` `4``,` `8``,` `0x10``,` `0x20``,` `0x40``,` `0x80``,` `0x1B``,``0x36``,` `0``,` `0``,` `0``,` `0``,` `0``,``]`  `# 修改行变换到和日志中的结果一致``def` `shift_rows(s):``s[``0``][``1``], s[``1``][``1``], s[``2``][``1``], s[``3``][``1``]` `=` `s[``2``][``1``], s[``3``][``1``], s[``0``][``1``], s[``1``][``1``]``s[``0``][``2``], s[``1``][``2``], s[``2``][``2``], s[``3``][``2``]` `=` `s[``3``][``2``], s[``0``][``2``], s[``1``][``2``], s[``2``][``2``]``s[``0``][``3``], s[``1``][``3``], s[``2``][``3``], s[``3``][``3``]` `=` `s[``1``][``3``], s[``2``][``3``], s[``3``][``3``], s[``0``][``3``]` `# 下面则需要进行列混淆``def` `gf_multiply(a, b):``p` `=` `0``counter` `=` `0``while` `b:``if` `b &` `1``:``p ^``=` `a``a <<``=` `1``if` `a &` `0x100``:``a ^``=` `0x11B``b >>``=` `1``counter` `+``=` `1``return` `p`  `def` `mix_columns(state):``new_state` `=` `[[``0` `for` `_` `in` `range``(``4``)]` `for` `_` `in` `range``(``4``)]``mix_matrix` `=` `[``[``0x02``,` `0x03``,` `0x01``,` `0x01``],``[``0x01``,` `0x02``,` `0x03``,` `0x01``],``[``0x01``,` `0x01``,` `0x02``,` `0x03``],``[``0x03``,` `0x01``,` `0x01``,` `0x02``]``]``for` `col` `in` `range``(``4``):``for` `row` `in` `range``(``4``):``for` `k` `in` `range``(``4``):``new_state[row][col] ^``=` `gf_multiply(mix_matrix[row][k], state[k][col])``return` `new_state` `def` `add_round_key(matrix, round_key):``# round_key = fixed_bytes[16:32]``for` `i` `in` `range``(``4``):``for` `j` `in` `range``(``4``):``matrix[i][j] ^``=` `round_key[i` `*` `4` `+` `j]` `def` `round_encrypt(block_bytes: bytes):``# 1. 异或iv``iv` `=` `fixed_bytes[:``16``]``state` `=` `bytes([a ^ b` `for` `a, b` `in` `zip``(block_bytes, iv)])``logger.debug(f``"异或初始化向量: {state.hex()}"``)``# 2. 字节代换``state` `=` `[dfed0_table[a]` `for` `a` `in` `state]``logger.debug(f``"查表结果: {bytes(state).hex()}"``)``# 3. 行变换``state` `=` `np.asarray(state).reshape((``4``,` `4``))``shift_rows(state)``logger.debug(f``"行变换结果:"``)``print_matrix_hex(state)``# 4. 列混淆``state` `=` `mix_columns(state)``logger.debug(f``"列混淆结果:"``)``print_matrix_hex(state)``# 5. 异或轮钥``add_round_key(state, fixed_bytes[``16``:``32``])``logger.debug(f``"轮钥结果:"``)``print_matrix_hex(state)``# 6. 第二轮字节代换``state` `=` `[dfed0_table[a]` `for` `a` `in` `np.asarray(state).flatten()]``logger.debug(f``"第二轮查表结果: {bytes(state).hex()}"``)``# 7. 第二轮行变换``state` `=` `np.asarray(state).reshape((``4``,` `4``))``shift_rows(state)``logger.debug(f``"第二轮行变换结果:"``)``print_matrix_hex(state)``# 8. 第二轮异或轮钥``add_round_key(state, fixed_bytes[``32``:])``logger.debug(f``"第二轮轮钥结果:"``)``print_matrix_hex(state)``# 9. 最后再异或key``add_round_key(state, fixed_bytes[``16``:``32``])``logger.debug(f``"最后结果:"``)``print_matrix_hex(state)``return` `bytes(state.flatten().astype(np.uint8))` `def` `aes_encrypt(message: bytes):``assert` `len``(message)` `%` `16` `=``=` `0``,` `'Message must be padded for AES block size!'``encrypted_msg` `=` `b''``iv` `=` `bytes.fromhex(``"ea180a0336ed352fcd24e4d50018ae54"``)``for` `i` `in` `range``(``0``,` `len``(message),` `16``):``msg` `=` `message[i:i``+``16``]` `if` `iv` `is` `None` `else` `bytes([a ^ b` `for` `a, b` `in` `zip``(message[i:i``+``16``], iv)])``iv` `=` `round_encrypt(msg)``print``(message[i:i``+``16``].``hex``())``print``(iv.``hex``())``encrypted_msg` `+``=` `iv``return` `encrypted_msg`   `if` `__name__` `=``=` `'__main__'``:``res` `=` `aes_encrypt(message)``print``(f``"Encrypted Message: {res.hex()}"``)``print``(``'\n'``.join(wrap(res.``hex``(),` `32``)))` |
|-|-|

到此关于aes部分相关还原完成，接下来则是继续向上看，aes相关输入数据来源，并且这部分也能从前面的traceWrite中看出蛛丝马迹。下面是整理出来的需要继续追踪的数据：

| 1234567891011121314151617181920212223242526 | `a6` `85` `9e` `f7` `50` `01` `29` `09` `18` `96` `b6` `93` `bd a3` `7a` `64``84` `bc` `76` `08` `16` `db` `6c` `7c` `7e` `e4 d6` `8a` `f2 b5` `32` `7a``cb` `93` `cb aa` `10` `68` `e3` `97` `02` `64` `df` `8a` `04` `37` `c4 ce` `bd a4 a7` `8a` `a3` `58` `a5 c3 c7` `9b` `53` `2a` `be ba` `15` `78``8f` `80` `dd` `7a` `f0` `8e` `eb b9` `76` `de b6` `74` `ed` `5a` `01` `4a``4d` `4b` `ee` `0b` `e3 e8 bf` `4a` `71` `d8 bc` `3f` `ee` `83` `2a` `a1` `6c` `63` `15` `c8 ab ad` `40` `a1` `16` `3f` `f8` `9c` `ac cf` `44` `19``70` `18` `cd` `7d` `e9 dc ac` `8b` `49` `86` `4f` `0f` `97` `ad fc` `4e``ea` `9d` `a3 f4 b9` `34` `97` `ba db` `9b` `51` `40` `3b` `2f` `7d` `34``df` `87` `2c` `c7` `9a` `ed` `51` `26` `73` `e6` `33` `5f` `ee e7` `2d` `b6` `b5` `12` `88` `56` `38` `b4 e2 a2` `86` `68` `e1` `85` `e3` `01` `6d` `7f``76` `aa` `10` `08` `4c` `26` `c0` `95` `e9` `95` `d9` `90` `c9` `1e` `93` `89``5f` `ac cd fe` `79` `b6` `09` `35` `4b` `da` `5f` `dd` `45` `88` `71` `5a``0e` `07` `f5` `3b` `ea` `35` `36` `a9` `40` `93` `5d` `cc f3 bf` `98` `89``60` `8b` `c6 d9` `51` `55` `4d` `7e` `a1 ac` `33` `3c` `b2 ac` `95` `e7` `f1 fb e5` `72` `c3 f7` `50` `f6 af` `38` `04` `d6` `50` `f3` `72` `df` `c9` `63` `5c` `64` `9d` `fa` `9e` `a9` `90` `1b` `25` `79` `76` `ca d8 ab` `83` `93` `07` `0a` `ea` `42` `88` `a3` `0c` `f2 fd` `77` `e6 ff fd` `77``e6 ff` `51` `4a` `0c` `0c` `0c` `0c` `0c` `0c` `0c` `0c` `0c` `0c` `0c` `0c` `至于为什么要这么分割如果有四神分析经验就感觉这里非常的像X``-``Argus的部分逻辑了` |
|-|-|

从上面的数据，可以继续使用前面介绍的利用unidbg调试和定位内存变换定位，也可以直接去trace日志中搜索字节找线索，也可以利用经验从末尾开始看起，除去填充字节0c和忽略末尾两个字节，尾部 `fd 77 e6 ff fd 77 e6 ff` 这几个字节实在是太有规律了。同时这里的数据在本文中也只分析主体部分。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_HVKSTZXNPRYGD2H.webp)

从上图可以看出这部分的计算规律了，接着是这四字节简单计算分析如下：

| 123456789101112131415161718192021222324252627282930 | `第一个随机数` `0x4a518372` `[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d188``] [``08f17dd3``]` `0x4002d188``:` `"lsl x8, x8, #3"` `x8``=``0x5` `=``> x8``=``0x28``[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d18c``] [``486968b8``]` `0x4002d18c``:` `"ldr w8, [x10, x8]"` `x10``=``0xbfffbe20` `x8``=``0x28` `=``> w8``=``0x51``[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d190``] [``0825cf1a``]` `0x4002d190``:` `"lsr w8, w8, w15"` `w8``=``0x51` `w15``=``0x5` `=``> w8``=``0x2` `0x51` `>>` `0x5` `=` `0x2`  `[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d0ec``] [``6a596af8``]` `0x4002d0ec``:` `"ldr x10, [x11, w10, uxtw #3]"` `x11``=``0xbfffbe20` `w10``=``0x1` `=``> x10``=``0x2884a``[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d0f0``] [``685968f8``]` `0x4002d0f0``:` `"ldr x8, [x11, w8, uxtw #3]"` `x11``=``0xbfffbe20` `w8``=``0x7` `=``> x8``=``0x2``[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d0f4``] [``08010aca``]` `0x4002d0f4``:` `"eor x8, x8, x10"` `x8``=``0x2` `x10``=``0x2884a` `=``> x8``=``0x28848``这里` `0x2884a` `来源确实在unidbg trace日志中没有体验，这里也是直接套用了四神参数的经验，当然如果去调试肯定也是能找到线索的。` `0x2` `^` `0x2884a` `=` `0x28848`  `[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d0ec``] [``6a596af8``]` `0x4002d0ec``:` `"ldr x10, [x11, w10, uxtw #3]"` `x11``=``0xbfffbe20` `w10``=``0x1` `=``> x10``=``0x28848``[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d0f0``] [``685968f8``]` `0x4002d0f0``:` `"ldr x8, [x11, w8, uxtw #3]"` `x11``=``0xbfffbe20` `w8``=``0x5` `=``> x8``=``0x51``[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d0f4``] [``08010aca``]` `0x4002d0f4``:` `"eor x8, x8, x10"` `x8``=``0x51` `x10``=``0x28848` `=``> x8``=``0x28819` `0x28848` `^` `0x51` `=` `0x28819`  `[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d104``] [``6a596af8``]` `0x4002d104``:` `"ldr x10, [x11, w10, uxtw #3]"` `x11``=``0xbfffbe20` `w10``=``0x1` `=``> x10``=``0x28819``[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d108``] [``685968f8``]` `0x4002d108``:` `"ldr x8, [x11, w8, uxtw #3]"` `x11``=``0xbfffbe20` `w8``=``0x0` `=``> x8``=``0x0``[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d10c``] [``08010aaa``]` `0x4002d10c``:` `"orr x8, x8, x10"` `x8``=``0x0` `x10``=``0x28819` `=``> x8``=``0x28819``[``10``:``05``:``08` `869``][libmetasec_ml.so` `0x02d110``] [e80328aa]` `0x4002d110``:` `"mvn x8, x8"` `x8``=``0x28819` `=``> x8``=``0xfffffffffffd77e6` `~``0x28819` `&` `0xffffffff` `=` `0xffffd77e5` |
|-|-|

上面对四字节生成日志做了初步的分析，接下来则是查找异或之前的数据来源，还是重复的trace内存定位重复操作。

| 123456789101112131415161718 | `69` `4b` `e4` `5b` `5c` `87` `13` `62` `43` `8b` `7f` `f0` `24` `91` `0b` `98``1b` `2b` `fd` `14` `4a` `cf` `0d` `2d` `6c` `36` `dd f6` `97` `1e` `e0 e4` `9b` `22` `fd e2 c8` `39` `b9` `5b` `5b` `5a` `fd` `45` `a7` `58` `b4` `21``64` `ae` `5d` `58` `45` `e8` `0f` `69` `7f` `20` `0d` `16` `71` `16` `ce` `90``21` `4b` `03` `0b` `a5 fc` `3d` `ab b4` `13` `7c` `05` `17` `42` `3d` `97``27` `41` `48` `08` `7c` `d7 d6` `8a` `9c` `e8 bf` `4d` `52` `bd d6 f0` `c0` `05` `eb` `4a` `30` `b9` `6e` `96` `e7` `30` `0a` `0f` `23` `51` `fc af` `79` `b2` `78` `71` `52` `01` `39` `0c` `62` `5e` `83` `5f` `cb` `6a` `cd` `3d``64` `ac` `37` `dd d0` `80` `43` `39` `78` `d1 b0` `7c` `12` `ac` `51` `95``19` `ce` `28` `08` `18` `d0 c1` `53` `ed` `75` `21` `de` `4b` `1f` `d5` `60``97` `1c` `f2` `05` `fe` `90` `08` `90` `55` `ed` `7f` `aa d9` `3d` `e2` `0f``6a` `24` `e7` `2f` `e1` `6e` `fe b9` `53` `30` `89` `9f` `49` `f4` `42` `ad` `25` `a2 aa a3` `77` `8c` `2d` `e8 f8` `08` `4c` `0c` `ca cb de a6` `6c` `a0 bb` `15` `40` `65` `fe` `86` `74` `3b` `ae b7 aa b0` `09` `47``53` `ce` `4b` `54` `53` `68` `90` `17` `04` `18` `05` `25` `08` `ad` `81` `49``c7 f9 a1 b6` `0c` `8f` `a8` `2f` `9c` `a1` `13` `7b` `05` `63` `de` `76``e4 d8` `0e` `90` `35` `25` `dc` `65` `6c` `fa` `7d` `0c` `bd` `75` `d4 ea` `0d` `00` `00` `00` `00` `00` `00` `00` `00` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_RDAU57TF9VVXEY8.webp)

当然这还不是最初生成的位置，继续查找：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_V7BJRFG2R2E5E44.webp)

发现是逆序的，并且相关计算都是在函数`0x89824` 中完成，这里是处理最初输入数据的函数，并且混淆也不是很严重只需要照着静态代码还原即可。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_U3J8MAQ2XQUY5NZ.webp)

通过调试获取输入数据是protobuf

| 123456789101112131415161718 | `0a` `10` `36` `6c` `95` `6c` `35` `72` `5a` `9b` `e4 d4` `1d` `65` `c8 b8` `79` `26` `10` `04` `18` `f4 fd ae` `9b` `0f` `22` `04` `33` `30` `31` `39``32` `0a` `31` `36` `31` `31` `39` `32` `31` `37` `36` `34` `3a` `06` `32` `35``2e` `30` `2e` `30` `42` `14` `76` `30` `34` `2e` `30` `34` `2e` `30` `35` `2d``6d` `6c` `2d` `61` `6e` `64` `72` `6f` `69` `64` `48` `80` `94` `a0` `40` `52``08` `00` `00` `00` `00` `00` `00` `00` `00` `60` `9a` `ef b5 fa` `0c` `6a``14` `a9` `91` `86` `04` `d7` `79` `bd` `1b` `90` `8b` `ea` `84` `5e` `31` `34``6b` `13` `6b` `e5 f0` `72` `06` `24` `17` `68` `83` `2a` `1c` `7a` `0e` `08``02` `10` `be e1` `54` `18` `be e1` `54` `20` `be e1` `54` `a2` `01` `04``6e` `6f` `6e` `65` `a8` `01` `e2` `05` `ba` `01` `09` `08` `e6` `8d` `e1 f9` `0c` `38` `ac` `71` `c2` `01` `6a` `7b` `0a` `09` `22` `63` `6d` `72` `22` `3a``09` `31` `36` `37` `37` `37` `32` `31` `36` `2c` `0a` `09` `22` `63` `6d` `72``32` `22` `3a` `09` `31` `36` `37` `37` `37` `32` `31` `36` `2c` `0a` `09` `22``75` `6e` `5f` `68` `22` `3a` `09` `30` `2c` `0a` `09` `22` `6b` `64` `22` `3a``09` `36` `39` `34` `33` `36` `37` `2c` `0a` `09` `22` `66` `6b` `64` `22` `3a``09` `31` `39` `39` `38` `30` `31` `38` `32` `30` `34` `2c` `0a` `09` `22` `70``64` `22` `3a` `09` `2d` `31` `30` `34` `33` `30` `39` `30` `30` `38` `35` `0a``7d` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_BSW8HFDAYZWQVW2.webp)

到这里X-Medusa算法的主体部分就都完成了，下面给出简单的整体粗略验证代码：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240 | `# -*- coding: utf-8 -*-` `'''``正向验证前面的分析，尝试完整还原日志中的计算流程。`  `'''` `import` `numpy as np``from` `loguru` `import` `logger``from` `gmssl` `import` `sm3, func``from` `itertools` `import` `cycle``from` `Crypto.Util.Padding` `import` `pad` `sign_key_bytes` `=` `bytes.fromhex(``"ac1adaae95a7af94a5114ab3b3a97dd80050aa0a39314c40528caec95256c28c"``)``rand_num` `=` `bytes.fromhex(``"7283514a"``)` `# 随机数` `# 和protocbuf 初步处理相关的数据``protobuf_mixed_bytes` `=` `sm3.sm3_hash(func.bytes_to_list(sign_key_bytes` `+` `rand_num` `+` `sign_key_bytes))``logger.debug(protobuf_mixed_bytes)` `# 待加密的设备信息protobuf``device_protobuf` `=` `bytes.fromhex(``"0a10366c956c35725a9be4d41d65c8b87926100418f4fdae9b0f220433303139320a313631313932313736343a0632352e302e3042147630342e30342e30352d6d6c2d616e64726f6964488094a04052080000000000000000609aefb5fa0c6a14a9918604d779bd1b908bea845e31346b136be5f07206241768832a1c7a0e080210bee15418bee15420bee154a201046e6f6e65a801e205ba010908e68de1f90c38ac71c2016a7b0a0922636d72223a0931363737373231362c0a0922636d7232223a0931363737373231362c0a0922756e5f68223a09302c0a09226b64223a093639343336372c0a0922666b64223a09313939383031383230342c0a09227064223a092d313034333039303038350a7d"``)`  `# 下面则是还原最开始的处理``def` `c_bitwise_not(num):``# 假设模拟 32 位 int 类型``bit_size` `=` `32``# 创建一个 32 位的掩码，所有位都为 1``mask` `=` `(``1` `<< bit_size)` `-` `1``# 对输入的数进行按位取非操作，并与掩码进行按位与操作``result` `=` `~num & mask``# 检查结果是否为负数（最高位为 1）``if` `result & (``1` `<< (bit_size` `-` `1``)):``# 如果是负数，将其转换为 Python 的负数表示``result` `-``=` `(``1` `<< bit_size)``return` `result`  `def` `bfxill(w21, w8):``# 提取 w8 中从第 3 位开始、宽度为 5 位的位域``extracted_bits` `=` `(w8 >>` `3``) &` `0b11111``# 清除 w21 的最低 5 位``w21` `=` `w21 & ~``0b11111``# 将提取的位域插入到 w21 的最低 5 位``w21` `=` `w21 \| extracted_bits``return` `w21`  `def` `medusa_protobuf_mixed(protobuf_bytes: bytes, mix_param_bytes: bytes):``result` `=` `[]``for` `i, b` `in` `enumerate``(protobuf_bytes):``idx` `=` `(``4` `*` `i)` `%` `len``(mix_param_bytes)``tmp` `=` `(b >>` `2``) &` `0xffffc03f` `\| (b <<` `6``)``tmp` `+``=` `mix_param_bytes[idx]``eon_val` `=` `(tmp ^ c_bitwise_not(mix_param_bytes[idx` `+` `1``])) &` `0xffffffff``tmp` `=` `bfxill((``32` `*` `eon_val &` `0xffffffff``), eon_val)` `+` `mix_param_bytes[idx` `+` `1``]``tmp` `=` `(mix_param_bytes[idx] ^ c_bitwise_not(tmp)) &` `0xffffffff``result.append(``int``.to_bytes(tmp,` `4``, byteorder``=``'little'``)[``0``])``# 开始第二步处理``mixed_param` `=`  `list``(``reversed``(result))` `# 逆转``# 处理前两个字节``mixed_param[``0``]` `=` `(((c_bitwise_not(mixed_param[``-``2``]) ^ mixed_param[``-``1``]) &` `0xffffffff``)` `+` `mixed_param[``0``]) &` `0xffffffff``mixed_param[``1``]` `=` `(mixed_param[``0``] ^ mixed_param[``-``1``] ^` `0xfe``)` `+` `mixed_param[``1``] &` `0xffffffff``# print(f"Mixed parameter [0]: {hex(mixed_param[0])}, {hex(mixed_param[1])}")``for` `i` `in` `range``(``2``,` `len``(mixed_param)` `-` `1``):``mixed_param[i]` `+``=` `mixed_param[i``-``2``] ^ (((mixed_param[i``-``1``] &` `0x80` `!``=` `0``)) \| (``2` `*` `mixed_param[i``-``1``])) ^ (c_bitwise_not(i) &` `0xffffffff``)``mixed_param[i]` `=` `int``.to_bytes(mixed_param[i],` `8``, byteorder``=``'little'``)[``0``]``# 最后一个字节特殊处理``mixed_param[``-``1``] ^``=` `mixed_param[``-``2``]``return` `bytes(mixed_param[``1``:])` `protobuf_processed` `=` `medusa_protobuf_mixed(device_protobuf, bytes.fromhex(protobuf_mixed_bytes))``logger.debug(protobuf_processed.``hex``())`  `# xor 计算` `# NOTE: 注意输入随机数的序列。统一使用大端模式``def` `get_xor_key(random_bytes: bytes):``a, b` `=` `random_bytes[``-``2``], random_bytes[``-``1``]``res` `=` `a ^ (a >>` `0x5``) ^ ((a <<` `0xb` `\| b))``res` `=` `(~res) &` `0xffffffff``return` `res` `logger.debug(f``"xor key calculated {hex(get_xor_key(rand_num))}"``)``xor_key` `=` `bytes.fromhex(``'fffd77e6'``)` `# TODO: 这个数字的生成需要单独追``# NOTE: 注意这里需要反转初步计算的protobuf数据, 并且填充0, 还有0d的顺序``# TODO: 这里可能还是数据填充的问题，``pad_bytes` `=` `bytes.fromhex(``'00000000000000000d'``)``xor_result` `=` `bytearray([a ^ b` `for` `a, b` `in` `zip``(``reversed``(pad_bytes` `+` `protobuf_processed), cycle(xor_key))])` `logger.debug(f``"xor result: {xor_result.hex()}"` `)`  `# 头尾拼接字节准备aes简化加密``prefix_bytes` `=` `bytes.fromhex(``'a6'``)` `# 首字节固定``prefix_bytes` `+``=` `bytes.fromhex(``"859ef750"``)` `# 这四字节是随机数``prefix_bytes` `+``=` `bytes.fromhex(``"01290918"``)` `# 这四字节除了第二字节可变其他字节固定` `aes_lite_in_bytes` `=` `prefix_bytes` `+` `xor_result` `+` `rand_num[``2``:]` `# aes 数据填充``# logger.debug(f"aes lite input: {aes_lite_in_bytes.hex()}")``aes_lite_in_bytes` `=` `pad(aes_lite_in_bytes,` `16``)``logger.debug(f``"aes lite input: {aes_lite_in_bytes.hex()}"``)`  `# aes简化算法` `# 此字节数组前16字节看成是iv，中间16字节看成是轮钥，最后16字节看成第二轮轮钥``'''``ea2b045b11bf2364839e6ab27f95a9df 84e705c7955826a316c64c116953e5ce 62028a3df75aac9ee19ce08f88cf0541``'''``round_key` `=` `bytes.fromhex(``"ea2b045b11bf2364839e6ab27f95a9df84e705c7955826a316c64c116953e5ce62028a3df75aac9ee19ce08f88cf0541"``)`  `# 下面是aes魔改的加密算法` `# 这个是计算后需要查的表，直接从ida中复制出来的``# 这部分应该是对应着查表， 字节代换的过程``dfed0_table` `=` `[``0x2E``,` `0x5C``,` `0x55``,` `0xED``,` `0x1B``,` `0xDA``,` `0xA``,` `0x79``,` `0x28``,``0x69``,` `0x57``,` `0xFE``,` `0x68``,` `0x3A``,` `0xDE``,` `0xAC``,` `0x90``,` `0xF9``,``0xC1``,` `0xE1``,` `0xC3``,` `0x8B``,` `0x7F``,` `0x59``,` `0x26``,` `0xCA``,` `0x13``,``0xBB``,` `0x11``,` `0x37``,` `0x39``,` `0x21``,` `0xEB``,` `0x9A``,` `0xFF``,` `0x5E``,``0x42``,` `0x33``,` `0xBE``,` `0x51``,` `0x8D``,` `0x40``,` `0x1E``,` `0x91``,` `0xB3``,``0x85``,` `0xB7``,` `0xCD``,` `0xDC``,` `0x27``,` `0x92``,` `0x83``,` `0x87``,` `0x3F``,``0xE6``,` `0x4A``,` `0x64``,` `0x56``,` `0x8C``,` `0xA1``,` `0x76``,` `0xD2``,` `0xFD``,``0xC0``,` `0x63``,` `0x18``,` `0x44``,` `0x1A``,` `0x9F``,` `0x61``,` `0xCB``,` `0x6E``,``0x67``,` `0x29``,` `0xAF``,` `0xB8``,` `0x54``,` `0x60``,` `0xDB``,` `0x97``,` `0xE8``,``0xA3``,` `0xC9``,` `0xE4``,` `0``,` `0xEC``,` `0x50``,` `0x17``,` `0xBD``,` `0x2A``,``0xB6``,` `0x8E``,` `0x3B``,` `0x46``,` `0x65``,` `0xA6``,` `0x7A``,` `0x96``,` `0xD3``,``0x72``,` `0x12``,` `0xBC``,` `0x20``,` `0x4D``,` `0x7C``,` `0xFA``,` `0x15``,` `0xC``,``0x41``,` `0x9B``,` `0xAA``,` `9``,` `0xF8``,` `0xF0``,` `0x5D``,` `0x84``,` `0xFC``,``0xE``,` `0xD6``,` `0xA0``,` `0xF2``,` `0xEF``,` `0x4E``,` `0x10``,` `0xBF``,` `0x89``,``0x6D``,` `0x9C``,` `0x98``,` `6``,` `0xC2``,` `0xC7``,` `0x5A``,` `0xF1``,` `0xB1``,``0xA5``,` `0xF4``,` `0xB9``,` `0xA2``,` `0xF5``,` `0x78``,` `0xAE``,` `0x3D``,` `0x24``,``0xFB``,` `0x30``,` `0x9D``,` `0xD8``,` `0xA4``,` `0x6F``,` `0x1F``,` `0x49``,` `0xD0``,``0x95``,` `0x3C``,` `0x99``,` `0xBA``,` `0x23``,` `0xEA``,` `0x53``,` `0x14``,` `0x2B``,``0xE0``,` `0xD``,` `0x5B``,` `0x94``,` `0x38``,` `0x4B``,` `0x1C``,` `0xCC``,` `0x4C``,``0x88``,` `0x2C``,` `0x81``,` `0xF3``,` `0x9E``,` `0x70``,` `0xF6``,` `0x58``,` `0x45``,``0xB0``,` `0x35``,` `0x5F``,` `0x6A``,` `0x8A``,` `0x32``,` `0x19``,` `0x34``,` `0xDD``,``0x4F``,` `0x7D``,` `0x36``,` `0xEE``,` `0xAB``,` `0x75``,` `0x71``,` `0xF``,` `0x25``,``0xB5``,` `0xE9``,` `0x47``,` `0xF7``,` `0xCF``,` `0x43``,` `0x6C``,` `0xC6``,` `0x8F``,``0x31``,` `0xB2``,` `0x2F``,` `0xD9``,` `0x1D``,` `0xC4``,` `0xA8``,` `0xD4``,` `0x93``,``0x73``,` `0xA7``,` `0x82``,` `0x77``,` `0x66``,` `8``,` `0x6B``,` `1``,` `0xA9``,` `0xE3``,``0xD5``,` `0xAD``,` `0xD7``,` `0xE5``,` `0x62``,` `0x86``,` `3``,` `0x22``,` `0xB4``,``0x2D``,` `0xD1``,` `0xDF``,` `0x3E``,` `0x7B``,` `0x52``,` `0xE2``,` `0x7E``,` `0x48``,``0xE7``,` `0xB``,` `4``,` `0xC8``,` `0x16``,` `0xC5``,` `2``,` `0xCE``,` `7``,` `0x74``,` `0x80``,``5``,` `0x8D``,` `1``,` `2``,` `4``,` `8``,` `0x10``,` `0x20``,` `0x40``,` `0x80``,` `0x1B``,``0x36``,` `0``,` `0``,` `0``,` `0``,` `0``,``]`  `# 修改行变换到和日志中的结果一致``def` `shift_rows(s):``s[``0``][``1``], s[``1``][``1``], s[``2``][``1``], s[``3``][``1``]` `=` `s[``2``][``1``], s[``3``][``1``], s[``0``][``1``], s[``1``][``1``]``s[``0``][``2``], s[``1``][``2``], s[``2``][``2``], s[``3``][``2``]` `=` `s[``3``][``2``], s[``0``][``2``], s[``1``][``2``], s[``2``][``2``]``s[``0``][``3``], s[``1``][``3``], s[``2``][``3``], s[``3``][``3``]` `=` `s[``1``][``3``], s[``2``][``3``], s[``3``][``3``], s[``0``][``3``]` `# 下面则需要进行列混淆``def` `gf_multiply(a, b):``p` `=` `0``counter` `=` `0``while` `b:``if` `b &` `1``:``p ^``=` `a``a <<``=` `1``if` `a &` `0x100``:``a ^``=` `0x11B``b >>``=` `1``counter` `+``=` `1``return` `p`  `def` `mix_columns(state):``new_state` `=` `[[``0` `for` `_` `in` `range``(``4``)]` `for` `_` `in` `range``(``4``)]``mix_matrix` `=` `[``[``0x02``,` `0x03``,` `0x01``,` `0x01``],``[``0x01``,` `0x02``,` `0x03``,` `0x01``],``[``0x01``,` `0x01``,` `0x02``,` `0x03``],``[``0x03``,` `0x01``,` `0x01``,` `0x02``]``]``for` `col` `in` `range``(``4``):``for` `row` `in` `range``(``4``):``for` `k` `in` `range``(``4``):``new_state[row][col] ^``=` `gf_multiply(mix_matrix[row][k], state[k][col])``return` `new_state` `def` `add_round_key(matrix, round_key):``# round_key = round_key[16:32]``for` `i` `in` `range``(``4``):``for` `j` `in` `range``(``4``):``matrix[i][j] ^``=` `round_key[i` `*` `4` `+` `j]` `def` `round_encrypt(block_bytes: bytes):``# 1. 异或iv``iv` `=` `round_key[:``16``]``state` `=` `bytes([a ^ b` `for` `a, b` `in` `zip``(block_bytes, iv)])``# logger.debug(f"异或初始化向量: {state.hex()}")``# 2. 字节代换``state` `=` `[dfed0_table[a]` `for` `a` `in` `state]``# logger.debug(f"查表结果: {bytes(state).hex()}")``# 3. 行变换``state` `=` `np.asarray(state).reshape((``4``,` `4``))``shift_rows(state)``# 4. 列混淆``state` `=` `mix_columns(state)``# 5. 异或轮钥``add_round_key(state, round_key[``16``:``32``])``# 6. 第二轮字节代换``state` `=` `[dfed0_table[a]` `for` `a` `in` `np.asarray(state).flatten()]``# logger.debug(f"第二轮查表结果: {bytes(state).hex()}")``# 7. 第二轮行变换``state` `=` `np.asarray(state).reshape((``4``,` `4``))``shift_rows(state)``# 8. 第二轮异或轮钥``add_round_key(state, round_key[``32``:])``# 9. 最后再异或key``add_round_key(state, round_key[``16``:``32``])``return` `bytes(state.flatten().astype(np.uint8))` `def` `aes_encrypt(message: bytes):``assert` `len``(message)` `%` `16` `=``=` `0``,` `'Message must be padded for AES block size!'``encrypted_msg` `=` `b''``# NOTE: 这里的iv是signkey的后16字节取md5和argus保持一致``iv` `=` `bytes.fromhex(``"ea180a0336ed352fcd24e4d50018ae54"``)``for` `i` `in` `range``(``0``,` `len``(message),` `16``):``msg` `=` `message[i:i``+``16``]` `if` `iv` `is` `None` `else` `bytes([a ^ b` `for` `a, b` `in` `zip``(message[i:i``+``16``], iv)])``iv` `=` `round_encrypt(msg)``# print(message[i:i+16].hex())``# print(iv.hex())``encrypted_msg` `+``=` `iv``return` `encrypted_msg`  `aes_result` `=` `aes_encrypt(aes_lite_in_bytes)``logger.debug(f``"aes lite result: {aes_result.hex()}"``)` |
|-|-|

## 部分补充

base64输入参数中的第一部分是一个时间戳也是X-Khronos与protobuf编号1对应字节的异或：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/951135_B9427MTQWY2MU6R.webp)

中间的两个字节留意出现的随机字节。

## 总结

1. 上面只记录了主体加密部分，部分细节缺失，但是不需要那么高还原度也可以通过接口校验。
2. 除了部分魔改之后，大部分算法细节和X-Argus流程几乎一致，protobuf输入数据都打部分相似。
3. 使用unidbg0.9.8发现调用过程中总是缺失部分关键信息，但是由于之前分析过太多次了，就没有详细分析原因。
4. 本文只是粗略的分析练手学习，部分算法细节也不够精确。

上传的附件：
- GodParameter25.java

（35.07kb，260次下载）

---

# 回复

## 回复 by kreedz (#2)

*2025-2-22 18:05*

666 强 大佬

## 回复 by 墨穹呢 (#3)

*2025-2-22 18:18*

火钳刘明 今年好多分析字节的文章

## 回复 by Tubbs (#4)

*2025-2-22 18:31*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  墨穹呢](https://bbs.kanxue.com/user-886838.htm)
>
>  火钳刘明 今年好多分析字节的文章
>
>

闲着也是闲着，练个手，也是有段时间没看了

## 回复 by 陈可牛 (#5)

*2025-2-22 20:10*

里面还有魔改的md5，那个也蛮有意思的![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by Imxz (#6)

*2025-2-23 12:09*

66666666

## 回复 by MsScotch (#7)

*2025-2-25 20:09*

tql

## 回复 by huxianwei (#8)

*2025-3-19 02:14*

可是看了半天还是 屁用没有   东拉西扯，遮遮掩掩

## 回复 by Tubbs (#9)

*2025-3-19 14:13*

>
> [huxianwei](https://bbs.kanxue.com/user-718334.htm)
>
>  可是看了半天还是 屁用没有 东拉西扯，遮遮掩掩
>
>

我也是第一次分析这个参数，是有点问题，只是交流而已，缺失的部分还是要你自己补齐。

## 回复 by mb_uigwndnf (#10)

*2025-3-19 14:22*

>
> [huxianwei](https://bbs.kanxue.com/user-718334.htm)
>
>  可是看了半天还是 屁用没有 东拉西扯，遮遮掩掩
>
>

站着把饭要了![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by 龙哥在不在 (#11)

*2025-3-31 21:21*

每个app的哥哥算法的key iv 还有各种盐不同，是写死在代码里的还是动态生成的啊

## 回复 by mb_xeodfvew (#12)

*2025-4-2 09:45*

能公开到这种程度也不错了

## 回复 by mb_ggxkozau (#13)

*2025-5-6 16:06*

里面还有一个比较重要的bodyHash算法![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_axnyspcg (#14)

*2025-8-1 18:02*

大佬大佬，你的so是特殊处理过吗，我的版本和你一样，函数地址也一样，但是因为vmp的原因，搜到的指令结果都是大几千起步

## 回复 by 我一无所知 (#15)

*2025-10-8 22:07*

>
> [Tubbs](https://bbs.kanxue.com/user-951135.htm)
>
>  我也是第一次分析这个参数，是有点问题，只是交流而已，缺失的部分还是要你自己补齐。
>
>

用unidbg以后ac1adaae95a7af94a5114ab3b3a97dd80050aa0a39314c40528caec95256c28c不对，有解决办法吗？

## 回复 by 陈世已忘 (#16)

*2025-10-21 18:39*

6666
