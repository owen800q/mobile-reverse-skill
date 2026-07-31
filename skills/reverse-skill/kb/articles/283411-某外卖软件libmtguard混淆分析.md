---
title: '[原创]某外卖软件libmtguard混淆分析'
url: https://bbs.kanxue.com/thread-283411.htm
tid: 283411
author: k423
date: '2024-09-12'
tags: [Android安全, 原创, 逆向分析, NDK分析, 脱壳反混淆]
crawled_at: '2026-07-31T14:20:39+08:00'
replies: 3
---

# 字符串加密

sub_25CDC这个函数就是字符串解密函数，byte_218F01是标记有没有解密的
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_B3M6ZDJQXFPHXTX.webp)
字符串解密函数就是一个异或，参数第一个存放解密后字符串，第二个是加密的字符串，第三个是密钥，第四个是长度
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_UGPN3D5TQ5ETC8N.webp)

字符串还是挺多的，需要批量处理一下
![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_3K5BE6QC7RSDRP4.webp)
解密算法已经知道了，直接从解密函数调用前的10个指令开始模拟执行到解密函数，得到解密函数的4个参数
找解密函数调用处的前10个指令时，需要判断一下是不是bxx之类的分支指令，是的话就不往前找了，避免模拟执行跑飞
然后根据参数解密出字符串，patch到第一个参数的地址

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081 | `import` `flare_emu``from` `idc` `import` `*``from` `idaapi` `import` `*``import` `idaapi``import` `ida_allins``from` `ida_ida` `import` `*``from` `idautils` `import` `*``import` `unicorn``from` `keystone` `import` `*` `from` `unicorn` `import` `arm64_const` `my_EH` `=` `flare_emu.EmuHelper()` `def` `emu_last_x_insn(ea, insn_cnt``=``10``, skip_ea``=``True``, stop_in_brach``=``True``, reg_info``=``{}):``count` `=` `0``curr_addr` `=` `ea``while` `count < insn_cnt:``curr_addr` `=` `prev_head(curr_addr,` `0``)``insn` `=` `idaapi.insn_t()``length` `=` `idaapi.decode_insn(insn, curr_addr)``if` `stop_in_brach:``if` `(insn.get_canon_feature() & CF_JUMP) !``=` `0` `or` `(insn.get_canon_feature() & CF_CALL) !``=` `0` `or` `insn.itype` `in` `[``ARM_b, ARM_bl, ARM_br, ARM_bx, ARM_blx1, ARM_blx2, ARM_cbz, ARM_cbnz, ARM_blr,` `ARM_tbz, ARM_tbnz, ARM_ldrpc, ARM_ret] :``curr_addr` `=` `next_head(curr_addr, BADADDR)``break``count` `+``=` `1``start_addr` `=` `curr_addr``end_addr` `=` `ea``my_EH.emulateRange(start_addr, end_addr, registers``=``reg_info, count``=``insn_cnt)``return` `my_EH.uc`  `def` `is_valid_address(addr, segment_name` `=` `".data"``):``seg` `=` `get_segm_by_name(segment_name)``return` `addr >``=` `seg.start_ea` `and` `addr <``=` `seg.end_ea` `def` `is_valid_string(string):``for` `c` `in` `string:``if` `c` `not` `in` `string.printable:``return` `False``return` `True` `def` `dec_str():``func_addr` `=` `0x25CDC``all_used_addr` `=` `list``(CodeRefsTo(func_addr,` `False``))``error_process_addr` `=` `[]``for` `used_addr` `in` `all_used_addr:``try``:``uc_stata` `=` `emu_last_x_insn(used_addr, reg_info``=``{``"X0"``:` `0``,` `"X1"``:` `0``,` `"X2"``:` `0``,` `"X3"``:` `0``})``x0` `=` `uc_stata.reg_read(arm64_const.UC_ARM64_REG_X0)``x1` `=` `uc_stata.reg_read(arm64_const.UC_ARM64_REG_X1)``x2` `=` `uc_stata.reg_read(arm64_const.UC_ARM64_REG_X2)``x3` `=` `uc_stata.reg_read(arm64_const.UC_ARM64_REG_X3)` `out_addr, enc_addr, key, lens` `=` `x0, x1, x2, x3``if` `is_valid_address(enc_addr):``curr_str_bytes` `=` `[]``for` `i` `in` `range``(lens):``curr_char` `=` `get_wide_byte(enc_addr` `+` `i)``curr_char ^``=` `key``key` `+``=` `3``key` `%``=` `256``curr_str_bytes.append(curr_char)``curr_str` `=` `bytearray(curr_str_bytes).decode(``'utf-8'``)``if` `is_valid_address(out_addr):``for` `k` `in` `range``(lens):``patch_byte(out_addr` `+` `k, curr_str_bytes[k])``create_strlit(out_addr,``0``,STRTYPE_C)``print``(f``"patched {hex(out_addr)} with   {curr_str}"``)``else``:``error_process_addr.append(used_addr)``else``:``error_process_addr.append(used_addr)``except` `Exception as e:``error_process_addr.append(used_addr)``print``()` `for` `addr` `in` `error_process_addr:``print``(``hex``(addr),end``=``' '``)` |
|-|-|

最后会有十几个字符串参数识别有问题，手动处理一下就可以
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_QFXACEFDU73MQ86.webp)
如果是把字符串解密函数直接内联到使用字符串的函数代码中可能混淆效果好一些

# 控制流混淆

直接看JNI_Onload，先是给W0赋了个值
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_K8D969SME8VX8FN.webp)
然后来到0x24980调用sub_25d0c
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_35TN2ZRY8HKX3SS.webp)
函数从x30加上w0<<2的内存位置取了一个dword，然后加到x30
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_APXFK7BARGBMC88.webp)
函数调用时会把返回地址放到link register(x30)，所以取数据的位置就是0x24980下面
上面是取了[0x24984 + 2<<2]，也就是0x78
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_YR84QEN992PWDD4.webp)
加到x30之后ret来到0x0249FC
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_K8BWHPHR9SX5VXP.webp)
查看0x24980的地方发现还有另外几个，并且sub_25D0C也不止有0x24980调用
可以猜测是每个函数都有有类似0x24980这种类似分发器的东西，通过上面的运算分发到函数内的基本块上
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_SAKJERZYV9UC66Y.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_8CT7EAMHHD3HU3P.webp)
还是要用脚本批量处理一下
找到BL sub_25d0c的所有调用处，然后每个调用处向前找3条指令开始模拟执行，找到取数据时的下标，取出对应的偏移加回去得到正确的跳转位置，然后用keystone汇编一下指令，再patch回BL sub_25d0c的调用处
当然也不一定非要去模拟执行，这个so中BL sub_25d0c的所有调用处的前一条指令刚好都是赋值下标的指令，也就是LDR W0, xxx ，所以直接匹配也是可以
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_G2JVNHXSBM2KM7S.webp)

| 1234567891011121314151617181920212223242526272829303132 | `def` `jump_deobfuscator():``sp_modify_func` `=` `0x25D0C``all_used_addr` `=` `list``(CodeRefsTo(sp_modify_func,` `False``))``error_process_addr` `=` `[]``for` `used_addr` `in` `all_used_addr:``data_addr` `=` `used_addr` `+` `4``for` `xref_addr` `in` `list``(CodeRefsTo(used_addr,` `False``)):` `insn` `=` `idaapi.insn_t()``length` `=` `idaapi.decode_insn(insn, xref_addr)``assert``(insn.itype` `=``=` `ARM_b)``try``:``uc_stata` `=` `emu_last_x_insn(xref_addr, insn_cnt``=``2``, reg_info``=``{``"X0"``:` `0xffffffff``,` `"X1"``:` `0``,` `"X2"``:` `0``,` `"X3"``:` `0``})``x0` `=` `uc_stata.reg_read(arm64_const.UC_ARM64_REG_X0)``data_offset` `=` `x0``if` `(data_offset` `=``=` `0xffffffff``):``error_process_addr.append([used_addr, xref_addr])``continue``jump_addr` `=` `get_wide_dword(data_addr` `+` `(data_offset` `*` `4``))` `+` `data_addr``if` `(``not` `is_valid_address(jump_addr,` `".text"``)):``error_process_addr.append([used_addr, xref_addr])``continue``ks` `=` `Ks(KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN)``assembly_code` `=` `f``"b {hex(jump_addr)}"``encoding, count` `=` `ks.asm(assembly_code, as_bytes``=``True``, addr``=``xref_addr)``for` `k` `in` `range``(``4``):``patch_byte(xref_addr` `+` `k, encoding[k])``except` `Exception as e:``error_process_addr.append([used_addr,` `0``])``print``()` `for` `addr` `in` `error_process_addr:``print``(f``"{hex(addr[0])} {hex(addr[1])}"``)` |
|-|-|

patch完成之后，应用到so文件，重新用ida打开就可以看到函数都可以正常分析了
 ![反混淆前](https://bbs.kanxue.com/upload/attach/202409/866908_BP5PEBXYJV7PY5N.webp)
 ![反混淆后](https://bbs.kanxue.com/upload/attach/202409/866908_K2D5XQ5GMCSP3FV.webp)

# JNINativeInterface重映射

看JNI_Onload
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_GZGHVVFS6W932QB.webp)
sub_24A74里分配了一些空间，然后调用sub_24D20
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_6RB9NBDPGKJSU5D.webp)
sub_24D20中对JNINativeInterface里的函数全部重新映射了一遍，我们直接建个新的struct映射一下就好
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_CZNZASKGU3ZJ58A.webp)
最后映射完会发现4个reserve没有映射，所以出现了部分方法出现2次，这里直接把其中一个方法加个前缀保留
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_TZ8HGFBJSECR7FH.webp)
导入
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_AT5G8GSMBJ8A4HE.webp)
修改类型重新反编译
 ![图片描述](https://bbs.kanxue.com/upload/attach/202409/866908_253YKHCRA3VBJNN.webp)

---

# 回复

## 回复 by mb_fssslkzs (#2)

*2024-9-14 20:15*

标准 indbr 混淆 很好patch

## 回复 by frozenrain (#3)

*2025-2-11 15:10*

分析的很好。JNI interface remap 楼主可以把新的结构定义贴出来？

## 回复 by 软件君子 (#4)

*2025-2-11 16:20*

好帖 不过我懒 直接选择trace
