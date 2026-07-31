---
title: '[原创] Android 加固技术回忆录(0x1) 一代TX加固完整分析'
url: https://bbs.kanxue.com/thread-288890.htm
tid: 288890
author: SharkFall
date: '2025-10-23'
tags: [Android安全, 原创, 逆向分析, 脱壳反混淆]
crawled_at: '2026-07-31T15:28:19+08:00'
replies: 68
---

小白逆向记录, 有错误的地方还请各位大佬指正

内容涉及到结构体还原, 自实现linker脱壳修复, dex解密和dump分析, 以及加固技术原理

# 逆向环境

- lg g5 android 4.4.4
- ida 9.1
- 010editor
- 记事本, 记录一些重要信息, 哈哈
- 一双小手, 大手也没事, 按的准键盘就可以

# Java 层简单分析

拿到Apk后先简单分析一下Application, 没有发现骚操作, 确定直接加载lib中so后, 直接进入Native分析

![image](https://bbs.kanxue.com/upload/attach/202510/954363_RH2A7VSD4A2XYZH.webp)

# 调试/分析壳子ELF

ida打开so后发现导入是空的, 看来了壳子也做了保护, 分析一下

![image](https://bbs.kanxue.com/upload/attach/202510/954363_S855TUX9ZSDMZFP.webp)

这里shdr有一些问题, 查看段表找不到 .init.array, 那就直接动态调试抓把

![image](https://bbs.kanxue.com/upload/attach/202510/954363_MGGF2PFUG65RG5D.webp)

## 断点.init / .init.array

挂上调试, 直接断在linker的callFunction, br .init / .init.array 的位置

会先加载Bugly.so, 可以直接跳过, 直到libshella.so加载后再f7跟进去即可

![image](https://bbs.kanxue.com/upload/attach/202510/954363_MXPNZGZV46V396P.webp)

AUV, 您猜怎么着, 断住了!

(其实这里已经分析下去了, 忘了截图, 后补的图)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_MQK9RMKHZFFKR5U.webp)

调试发现只调用了一次 callFunction, 说明只有一个 .init.array

ida静态跳到0x944, 开始分析, 乍一看没有看出什么, 卒

![image](https://bbs.kanxue.com/upload/attach/202510/954363_B3A7ZZ55XDMEJFF.webp)

动态分析一下, 一行一行跟着汇编看

补了一下, 发现这里先取了so在内存中的起始地址给elfStart

initArray01 & 0xFFFFF000 取函数页起始地址, *elfStart != 0x464C457F 判断elf magic, 每次向下减一页大小, 直到找到elf magic

(还发现遍历了一下phdr, 但是没有引用, 暂不知道用途)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_QU6XBX9SP2RJQJN.webp)

## 修复壳子ELF

调试时, 发现这一块在读elfStart+idx的字节, 再各种异或后存回原处, 直接猜测是解密

![image](https://bbs.kanxue.com/upload/attach/202510/954363_AU7TXYAM4UZ8R6W.webp)

结合动态调试和静态修补, 以及接下来的函数调用中其中一个函数代码乱码状态, 最终可以确定是动态解密

![image](https://bbs.kanxue.com/upload/attach/202510/954363_6STWF9BA7VPBDC7.webp)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_M3DSTG39J2AJ547.webp)

elfStart_backup这个是一个拼接的int, 前一个字(short)代表需要解密的起始idx, 后一个字(short)代表需要解密的结束idx

起名elfStart_backup是因为, 取完解密的idx以后就赋值为elfStart地址被后面引用了

![image](https://bbs.kanxue.com/upload/attach/202510/954363_3BSWUMGTAXZEY86.webp)

那就run to解密完成的地方, 直接dump这一小块, 填进idb中 (偷个懒, 不用重新打开so分析)

mprotect是恢复内存属性为read exec, 断在这里dump即可

![image](https://bbs.kanxue.com/upload/attach/202510/954363_J2EZQTVTSGNSE8W.webp)

```
auto i, fp, start, end;
fp = fopen("d:\\dump_split.so","wb");
start = 0x766AF000; // elfStart + startIdx
end = 0x766B0AB4; // elfStart + endIdx

for (i = start; i <= end; i++) {
fputc(Byte(i),fp);
}

fclose(fp);
```

dump后再使用idapy填回idb即可开始分析

```
import idc

def set_arm_code_range(start_ea, end_ea):
"""
将指定范围设置为 ARM 代码
"""
current = start_ea
while current < end_ea:
idc.split_sreg_range(current, "T", 0)
current += 4

print(f"Converted range 0x{start_ea:X} - 0x{end_ea:X} to ARM code")

# 使用示例
set_arm_code_range(0x16c3, 0x24b4)import ida_bytes
import os

def patch_elf_from_file(offset, file_path, size=None):
"""
从文件读取内容并修补到ELF的指定偏移
:param offset: ELF文件中的偏移地址
:param file_path: 包含修补数据的文件路径
:param size: 要修补的字节数（如果为None，则使用文件大小）
"""
if not os.path.exists(file_path):
print("Error: File not found - %s" % file_path)
return False

with open(file_path, "rb") as f:
file_data = f.read()

if size is not None:
file_data = file_data[:size]

# 修补数据
for i, byte in enumerate(file_data):
ida_bytes.patch_byte(offset + i, byte)

print("Successfully patched %d bytes from %s at offset 0x%X" %
(len(file_data), file_path, offset))
return True

# 使用示例
if __name__ == "__main__":
# 将patch.bin文件的内容写入到ELF的0x1000偏移处
patch_elf_from_file(0x1000, "dump_elf_dec_0x1000_0x2ab4")
```

ai大法好, 哈哈, 效率+++

接下来在恢复完内存权限后, 做了cache刷新, 避免cup指令缓存没有更新

![image](https://bbs.kanxue.com/upload/attach/202510/954363_WUEYUBBGRGH5B67.webp)

等一下 syscall 983042 ??

![image](https://bbs.kanxue.com/upload/attach/202510/954363_WPGKNRBXFUEK4HJ.webp)

孤陋寡闻了, arm中 syscall调用号983042是cacheflush

![image](https://bbs.kanxue.com/upload/attach/202510/954363_SUBS37UDDYYWE84.webp)

接下来就走到了较为核心的逻辑, sub_766B074C是JNI_OnLoad函数, 先下断点

但是这里没有调用, 因为getnenv("DEX_PATH")没有取到东西

![image](https://bbs.kanxue.com/upload/attach/202510/954363_9QE3FWSC3V5UA7K.webp)

然后继续往下走, .init.array就返回来了, 回到了linker

直接f9, 我们就到了JNI_OnLoad函数, 之前断过, 这里是走到了libdvm call JNI_OnLoad

![image](https://bbs.kanxue.com/upload/attach/202510/954363_5GZYN3E6GKUEJ32.webp)

readOffset是0x6dc0, 命名为buildSdkVersion是因为这个值用完以后就被赋值buildSdkVersion了

记住这里的0x6dc0, 下面会考

![image](https://bbs.kanxue.com/upload/attach/202510/954363_EENZENB55N792BE.webp)

跟进sub_766B05B4看一下

根据elf开始地址, 在内存中寻找so的完整路径, 然后写入a1, 结束返回上一层

![image](https://bbs.kanxue.com/upload/attach/202510/954363_FP6V9XMRBGFNCBP.webp)

现在jniOnLoad 长这个样子, 跟进sub_766AF63C

![image](https://bbs.kanxue.com/upload/attach/202510/954363_W2ECFCQMVTNK9BJ.webp)

## 修补自实现linker加载so的info结构体

这里的info不是linker的soinfo, 而是elf的结构信息 !

这里的info不是linker的soinfo, 而是elf的结构信息 !

这里的info不是linker的soinfo, 而是elf的结构信息 !

重要的事情说三遍

sub_766AF63C 也是有一点难以阅读, 不过大概总览了一下, 猜测是自实现linker加载elf

有了这个方向, 下面的分析就事半功倍了

![image](https://bbs.kanxue.com/upload/attach/202510/954363_SN4VXF5J3ZTQJD9.webp)

这里就是用完0x6dc0后写成buildSdkVerison的地方

![image](https://bbs.kanxue.com/upload/attach/202510/954363_56QKK2JJGPWFMG7.webp)

先打开soFd, 在读取壳子so+0x6dc0的位置

那么为什么是0x6dc0呢, 这有什么特殊呢, 为什么不读取内存中这个位置呢 ???

小小的脑袋有大大的问号 ???

![image](https://bbs.kanxue.com/upload/attach/202510/954363_HDRYSKTF7XYUYGE.webp)

看了一下内存中libshella.so的内存占用, 计算了一下大小只有33kb

但是so静态大小是98kb, 那很明显了, 后半部分就是藏着的真实elf

![image](https://bbs.kanxue.com/upload/attach/202510/954363_MQS7SP759JAK6NW.webp)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_ZEJUD9AEQ6E7K9U.webp)

继续跟着分析, 发现一个无根之木, size 从哪里来 ???

这里就要开始补全结构体了, 先设置minVAddr为char[88]

![image](https://bbs.kanxue.com/upload/attach/202510/954363_DAG7TCHP985BADG.webp)

然后就很明了了, 从0x6dc0读取的0x58字节, 必然是一个结构体

开始逆向分析结构体中每一个字段代表什么

![image](https://bbs.kanxue.com/upload/attach/202510/954363_2UP9HKV8ZGS8M64.webp)

根据log直接得知第一个int和第二个int分别是minvaddr和size

![image](https://bbs.kanxue.com/upload/attach/202510/954363_6BM9SURKCN4BQ6P.webp)

**直接开补 !!!**

**这里注意, 没有定义的地方也需要保留, 不然结构体大小对不上, 就会飘红, 干扰正常分析**

![image](https://bbs.kanxue.com/upload/attach/202510/954363_8JKSTTYA2MHHDUT.webp)

这里对着变量 y 一下, 直接设置刚刚声明的结构体类型

![image](https://bbs.kanxue.com/upload/attach/202510/954363_C498CE5JAMGCBY5.webp)

接着就柳暗花明了, 继续猛猛补全即可

看到这里mmap已经可以完全确定了, 这是一个自实现linker加载真实elf, 那么下面就可以更大胆的猜测了

![image](https://bbs.kanxue.com/upload/attach/202510/954363_D526JHYTKNQEWF6.webp)

补全过程比较枯燥, 就不一个一个字段展示流程了, 展示一下大的点的分析基本就很明了了

通过这里可以推断这是另一个结构体, 占据24字节, 再结合 [再mmap] 推测应该是segment信息

那么another中第一个short就是segmentInfo结构体存储对应的偏移, 第二个short是segment的数量

(short类型根据汇编LDRH确定)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_X9NZWZTNNA683G7.webp)

再往下根据log再结合猜测就可以再补齐很多字段

![image](https://bbs.kanxue.com/upload/attach/202510/954363_UP8PUZ49QU5YVSP.webp)

再记录一下segmentInfo的补全

v48是从v50做页对齐来的, 那么v50就是loadBias+minVAddr了, 那也就是segmentInfo的第一个int就是起始虚拟地址, 后面用来re-map

v46是page end对齐减去(v50 + segmentInfos[1]), 那么segmentInfo的第二个int就是**segmentMemSize**

![image](https://bbs.kanxue.com/upload/attach/202510/954363_BDE9BQEJ8XYAS7J.webp)

猜测是segmentInfo的第二个int是memSize而不是fileSize的原因在下面

这里的从文件读取才是fileSize, 又确定了fileSize和segOffset字段

![image](https://bbs.kanxue.com/upload/attach/202510/954363_UY7ERKJA68W693X.webp)

这里还像是做了一个解密的样子

![image](https://bbs.kanxue.com/upload/attach/202510/954363_T9F5RFJP426QXM6.webp)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_7FKUWAYDJ5GN3HX.webp)

一路进来, 是不是很眼熟

![image](https://bbs.kanxue.com/upload/attach/202510/954363_XNJG9U2GFM7WVS6.webp)

让我们google一下, 原来是tea算法, 如果想静态解密可以写脚本试试了

![image](https://bbs.kanxue.com/upload/attach/202510/954363_2PFMP78FXBAM72S.webp)

那么segmentInfo[5]自然就是解密的数据大小, 单位应该是bit

![image](https://bbs.kanxue.com/upload/attach/202510/954363_U8YFMAK9BDKMM75.webp)

加密以后又做了一个xz解压, 这里zStream的结构体直接导入就可以

![image](https://bbs.kanxue.com/upload/attach/202510/954363_THCH66D9H7GGC85.webp)

## 修补结构体完成

最后, 经过了七七四十九天的修补, realElfInfo, segmentInfo, zStream全部补全的差不多以后就非常明了了

![image](https://bbs.kanxue.com/upload/attach/202510/954363_CGU2AXZ94PWD5YA.webp)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_F95UVMZ4Q4X47NV.webp)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_9SBWYT6BNNBR387.webp)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_KJNFCXH7PW6ZBGP.webp)

```
struct realElfInfo
{
    int minVAddr;
    int totalSize;
    __int16 segmentInfoOffset;
    __int16 segmentCount;
    char notUsed[4];
    int strtabOffset;
    int symtabOffset;
    int initFuncOffset;
    int initArrayFuncsOffset;
    char notUsed_1[8];
    bool unusedBool;
    __int16 initArrayFuncCount;
    __int16 neededLibCount;
    __int16 short6;
    int neededLibNameIdxArrOffset;
    int bucketNum1;
    int bucketNum2;
    int bucketOffset;
    int relaOffset;
    int realSymCount;
    int pltSymCount;
    int pltOffset;
    __int16 short2;
    __int16 short3;
    __int16 short4;
    __int16 short5;
};

struct segmentInfo
{
    int minVAddr;
    int memSize;
    int segmentOffset;
    int segFileSize;
    int flags;
    int segDecryptBits;
};

struct z_stream
{
    char *next_in;
    unsigned int avail_in;
    unsigned int total_in;
    char *next_out;
    unsigned int avail_out;
    unsigned int total_out;
    char *msg;
    void *state;
    void *zalloc;
    void *zfree;
    void *opaque;
    int data_type;
    unsigned int adler;
    unsigned int reserved;
};
```

##

# 手搓字节码修复真实So

补完结构体仅仅是可以看清楚逻辑, 真实elf到现在还没有修复出来, 目测是只能手搓字节码回填了

## 找真实So字段信息

这里可以静态解析所有字段, 不过我选择动态一把梭, 直接拿数据, 哈哈哈

![image](https://bbs.kanxue.com/upload/attach/202510/954363_URMWWSZ8AGRHR69.webp)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_G6RZJ46JX9Y38XK.webp)

都解密完了以后, 就要dlopen neededLib 再重定位函数了

![image](https://bbs.kanxue.com/upload/attach/202510/954363_KYSNKSAXNCNF8VX.webp)

这是几个neededLibName的下标数组, copy一下

![image](https://bbs.kanxue.com/upload/attach/202510/954363_FZ7E4TQBHUSJNVM.webp)

再跟进去就是重定位函数, 一眼顶针

这几个地址在前面预先计算好了, 修复的时候就要手动填进dynamic节

![image](https://bbs.kanxue.com/upload/attach/202510/954363_GBBWGAWW7NQTDX8.webp)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_7Y6RSV4K53J7UE6.webp)

## 巧妙的壳子So符号覆盖操作

再往下做了一个很好玩的操作, 把真实so的符号表, 字符串表 覆盖 到壳子so的符号表和字符串表, **这里先记一下**

![image](https://bbs.kanxue.com/upload/attach/202510/954363_SDM8P54WD997BFV.webp)

再恢复segment的flag

![image](https://bbs.kanxue.com/upload/attach/202510/954363_6WNZM8EGEKC4SRG.webp)

再call .init / .init.array就结束了

![image](https://bbs.kanxue.com/upload/attach/202510/954363_F846DKNU8UAJDMA.webp)

## 修复真实ELF

这里根据上面的消息, 尝试修复真实elf

把dump出的整块内存丢进010ediotr, 再把ehdr, phdr, dynamic都手打字节码拼一下, 再使用SoFixer32修复一下即可

![image](https://bbs.kanxue.com/upload/attach/202510/954363_43X5YMVV3U4H53C.webp)

## 修复完成

丢进ida直接分析, 完美不报错,, 就是导入函数没有, 但是影响不大, 一边调试, 一边命名 -- 静态分析青春版

还请各位大佬指点一下, 这种导入函数看不到是不是plt, rela没修好的原因 ?

![image](https://bbs.kanxue.com/upload/attach/202510/954363_BCH7KXFRMJJBRRU.webp)

正常f5, 但是因为没有import函数, 很多需要函数调用需要手动重命名

![image](https://bbs.kanxue.com/upload/attach/202510/954363_2ETVD5A7DUF4AWC.webp)

截至这里, 真实so就修复好了

# 调试/分析真实so逻辑

## 分析.init.array函数

linker加载完so就到了.init.array函数, 这里分析一下.init.array先

到了真实elf以后就全都是thumb指令集了, getEnv还是没取到东西, 直接返回

![image](https://bbs.kanxue.com/upload/attach/202510/954363_DR78P6UCBYJKGRM.webp)

剩下几个.init.array都长这样, 暂且跳过分析

![image](https://bbs.kanxue.com/upload/attach/202510/954363_NT9FUJYPX9VGNGH.webp)

## 分析JNI_OnLoad函数

前面sub_765B163C的函数call完.init.arry, 出来后就到了调用了真实elf的JNI_OnLoad

![image](https://bbs.kanxue.com/upload/attach/202510/3NA48MGGA3FKUK9.jpg)

## 壳子So符号覆盖答案揭晓

但是为什么还是dlsym 找JNI_OnLoad呢 ? 明明是自实现linker加载的elf, 怎么可能通过dlsym找到非linker加载的elf的函数呢 ?

![image](https://bbs.kanxue.com/upload/attach/202510/954363_PCK93CCPHZ4Y357.webp)

答案揭晓, 这里的memcpy符号表, 让linker在壳子so找JNI_OnLoad符号的时候, 返回已经修改后的JNI_OnLoad函数

此时, 壳子so的符号表中的JNI_OnLoad已经指向了真实elf的JNI_OnLoad

![image](https://bbs.kanxue.com/upload/attach/202510/954363_J2QMZVBYMQYZD5R.webp)

跟入分析, 进去后发现就是thumb指令集了, 大概还原了一下

![image](https://bbs.kanxue.com/upload/attach/202510/954363_MU7JG23HQYEH6EB.webp)

初始化了很多字符串

![image](https://bbs.kanxue.com/upload/attach/202510/954363_8XWKHBJNSXZFPEV.webp)

再注册了native函数, 然后就等待java调用了

![image](https://bbs.kanxue.com/upload/attach/202510/954363_9NA82UFNYCG4B6D.webp)

全部打上断点, 等待调用

![image](https://bbs.kanxue.com/upload/attach/202510/954363_PWAUXBS5JQ6PS73.webp)

## 分析 load函数

第一个跑到了load函数, 分析一下

![image](https://bbs.kanxue.com/upload/attach/202510/954363_G6YSUXKEGZ8HRU3.webp)

跟入 sub_7660B16C, 非常明显了, 进入下一个

![image](https://bbs.kanxue.com/upload/attach/202510/954363_QRRRS8ZAZUU7HZR.webp)

跟入 sub_7660C91C, 呜呜呜, 调试一半手滑点错了, 程序死了, 还好一边调试, 一遍改idb

判断jvm版本是不是2.开头

![image](https://bbs.kanxue.com/upload/attach/202510/954363_JC8XQJDQ3JKNN2S.webp)

跟入 sub_76717470, 注册receiver

![image](https://bbs.kanxue.com/upload/attach/202510/954363_EJUDQ6SZEUJ6G2H.webp)

跟入 sub_76725AF4, 注册了txShell的loadClass函数

![image](https://bbs.kanxue.com/upload/attach/202510/954363_YUZUR9YSP4YSUN4.webp)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_ZJ33XT9UKH2XMV8.webp)

这里先不着急看, 先跟着调试看看对于 java.vm.version 的版本的不同分支做了什么

![image](https://bbs.kanxue.com/upload/attach/202510/954363_SA5RJU7KED7XZAX.webp)

现在的 load 函数长这样, 大概流程:

1. 取buildSdkInt
2. 注册recevier
3. 判断jvm版本, 进入不同分支加载dex
4. 注册**MeShell的loadClass函数
5. 定位了artInterpreterToInterpreterBridge和art_quick_to_interpreter_bridge函数

![image](https://bbs.kanxue.com/upload/attach/202510/954363_8GHQKMKUC35EUGE.webp)

跟入看看这个 sub_CFC4(env, context, 0) 分支, 先从java层取几个值

![image](https://bbs.kanxue.com/upload/attach/202510/954363_XH8HS7PU6RREG4S.webp)

### 内存解密 Dex

然后寻找apk对应的DexFile, 找到以后在maps中取/data/dalvik-cache/data@app@com.xxxxxx.apk@classes.dex的起始地址

![image](https://bbs.kanxue.com/upload/attach/202510/954363_YMWN2EX8PSSUN6Z.webp)

找到classes.dex在内存中的位置以后:

1. 解析dex, 取到dex中data_size+data_off的偏移, 也就是data之后的位置, 这里应该是原始dex的位置
2. 修改clasess.dex内存区域权限为读写
3. 找到原始dex的内存地址以后使用tea算法解密dexHeader
4. 如果直接修改classes.dex内存区域的权限为读写失败就使用保底方案, 读取原始dex的大小, 并mmap出一片内存, 将原始dex move到mmap出来的内存区域

![image](https://bbs.kanxue.com/upload/attach/202510/954363_GRTCA2BSADBRHZA.webp)

这里取原始dex地址的时候做了一个页对齐的操作, 向后对齐

![image](https://bbs.kanxue.com/upload/attach/202510/954363_3D77ENZ4HNHVZEY.webp)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_97PM4AK3DPXFZHW.webp)

解密dexHeader以后就可以尝试dump出来并且还原原始dex了

![image](https://bbs.kanxue.com/upload/attach/202510/954363_EG47KEUCMTVSTW7.webp)

010editor去掉没用的头部, 粘贴原始dexheader以后丢进jdax发现就可以正常解析了

![image](https://bbs.kanxue.com/upload/attach/202510/954363_MA6EUZJDMPH2T5H.webp)

发现还是有注入data到dex中, 说明不止一个dex, 后面应该还有别的dex, 暂且先不管, 继续跟着跑

![image](https://bbs.kanxue.com/upload/attach/202510/954363_XYGJK865Y5Y5AH5.webp)

### 加载 Dex

拼接了mixSoPath和mixDexPath以后就开始解密并加载所有dex了

![image](https://bbs.kanxue.com/upload/attach/202510/954363_JEA39YD7MBSZ3H7.webp)

先加载mix.dex (空壳dex, 只有类), 然后取了mix.dex的DexFile的mCookie去内存解析, 一路找到DvmDex结构体指针

![image](https://bbs.kanxue.com/upload/attach/202510/954363_7Q39EAUH5PFYDBV.webp)

然后解析了原始dex header, 重新pack了结构体

![image](https://bbs.kanxue.com/upload/attach/202510/954363_KN5DDVUGBXBC6GR.webp)

```
struct dexHeader
{
int unused;
int memAddr;
int strIdxTab;
int typeIdxTab;
int fieldIdxTab;
int methodIdxTab;
int protoIdxTab;
int clsDefIdxTab;
int linkData;
char unused3[8];
int memAddr3_Normal;
char unused2[44];
int memAddr2_Android2;
};
```

dexCreateClassLookup, 创建类查找表

![image](https://bbs.kanxue.com/upload/attach/202510/954363_ZTNMY627G2MHPSP.webp)

填充DvmDex结构体,

![image](https://bbs.kanxue.com/upload/attach/202510/954363_K85A7GXY2WYHRGY.webp)

将所有DexFile放进elements数组以后, 替换原dexElements数组

![image](https://bbs.kanxue.com/upload/attach/202510/954363_BNAK9AM76TF5JYC.webp)

然后函数就return退出了, 回到了load函数最后一个部分

![image](https://bbs.kanxue.com/upload/attach/202510/954363_ZEQF2JMVURNAB9F.webp)

没什么太麻烦的点, 直接上图, **实际上这里是没有跑到的, 我的样本reg native返回0, 然后就退出了**

![image](https://bbs.kanxue.com/upload/attach/202510/954363_QRNBRRPYM5E949S.webp)

这里还check了是不是yunos, android 4.4 时代的yunos, 我搜了搜貌似是阿里做的定制版系统, 可惜没有见过

![image](https://bbs.kanxue.com/upload/attach/202510/954363_UBZSFFFDYKUMJMV.webp)

定位了artInterpreterToInterpreterBridge和art_quick_to_interpreter_bridge函数

![image](https://bbs.kanxue.com/upload/attach/202510/954363_6MK86VZ3PUKWSY6.webp)

## 分析 changeEnv函数

load函数结束以后, 直接f9就来到了changeEnv函数

函数逻辑比较简单, remove了mAllApplications中的mInitialApplication, 也就是加固自身的application

![image](https://bbs.kanxue.com/upload/attach/202510/954363_NC5K58EDV4T334A.webp)

再替换原始application

1. 修改mApplicationInfo的clsName为原始application name
2. 通过loadedApk.makeApplication构造原始application
3. 替换activityThread的mInitialApplication为原始application

![image](https://bbs.kanxue.com/upload/attach/202510/954363_E84MCXTJMAJ9E2A.webp)

## 分析 runCreate函数

非常简单, 调用了原始application的onCreate就结束了

![image](https://bbs.kanxue.com/upload/attach/202510/954363_FDWPCGFR5DVGWKX.webp)

还有两个函数, 分别是receiver和txEntries, 没有调用到, 函数体也比较简单, 贴个反汇编把

![image](https://bbs.kanxue.com/upload/attach/202510/954363_A6SWVU8SS4P3Y7D.webp)

![image](https://bbs.kanxue.com/upload/attach/202510/954363_5KTW32VNC3768TC.webp)

接着f9几下, 程序就正常进入了

# 小结

一路调下来感觉最惊艳我的还是自实现linker加载真实elf, 真是麻雀虽小,五脏俱全, 只用了大概一两百行就做出了完整加载实现, 受益匪浅.

还有解密壳子so的操作, 通过地址页边界对齐, 再逐次减去页大小向下寻找elf头, 真是非常骚的操作

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2025-10-23 12:50*

感谢分享

## 回复 by 陈可牛 (#3)

*2025-10-23 12:58*

在dex中有些图片缺失了麻烦补一下谢谢，还有就是楼主方便提供样本学习吗？谢谢

## 回复 by SharkFall (#4)

*2025-10-23 13:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  在dex中有些图片缺失了麻烦补一下谢谢，还有就是楼主方便提供样本学习吗？谢谢
>
>

好的，一会儿我补上

## 回复 by Steve2280 (#5)

*2025-10-23 13:28*

感谢分享

## 回复 by 逆天而行 (#6)

*2025-10-23 13:50*

详细，好文章！![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by xifgg (#7)

*2025-10-23 14:07*

66

## 回复 by KanXue_NG (#8)

*2025-10-23 15:21*

学习学习

## 回复 by HappyKL (#9)

*2025-10-23 15:28*

666

## 回复 by NshIdE (#10)

*2025-10-23 15:40*

学习

## 回复 by wx_插曲 (#11)

*2025-10-23 15:45*

学习

## 回复 by azd放 (#12)

*2025-10-23 16:21*

学习

## 回复 by mb_hcqpswwu (#13)

*2025-10-23 16:47*

学习

## 回复 by mb_hcqpswwu (#14)

*2025-10-23 16:49*

有样本学习一下吗

## 回复 by wx_huhu_859 (#15)

*2025-10-23 16:55*

11

## 回复 by 夫人十八岁 (#16)

*2025-10-23 23:07*

感谢分享

## 回复 by SharkFall (#17)

*2025-10-23 23:58*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_hcqpswwu](https://bbs.kanxue.com/user-1037289.htm)
>
>  有样本学习一下吗
>
>

稍后我补上

## 回复 by mb_fywsujzf (#18)

*2025-10-24 01:22*

111

## 回复 by SomeMx (#19)

*2025-10-24 01:28*

下期分析一下数字壳![image](https://bbs.kanxue.com/view/img/face/056.gif)

## 回复 by huangjw (#20)

*2025-10-24 09:15*

牛逼

## 回复 by Imxz (#21)

*2025-10-24 23:12*

tql

## 回复 by 嘎嘎真的很棒 (#22)

*2025-10-25 15:48*

感谢你分享这么好的资源！

## 回复 by 猫子 (#23)

*2025-10-25 16:55*

感谢分享

## 回复 by mb_hcqpswwu (#24)

*2025-10-25 17:13*

大佬计算器可以分享一下吗

## 回复 by Arsylk (#25)

*2025-10-25 17:56*

1

## 回复 by 毛毛毛毛虫 (#26)

*2025-10-25 17:58*

学习一下

## 回复 by mb_dmryhnwz (#27)

*2025-10-25 18:28*

1

## 回复 by kingking888 (#28)

*2025-10-26 17:39*

666

## 回复 by fangliangz (#29)

*2025-10-28 09:45*

学习学习

## 回复 by SharkFall (#30)

*2025-10-28 17:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_hcqpswwu](https://bbs.kanxue.com/user-1037289.htm)
>
>  大佬计算器可以分享一下吗
>
>

计算器是啥, 佬

## 回复 by mb_tewbhakr (#31)

*2025-10-28 19:22*

看看

## 回复 by fei3ei (#32)

*2025-10-29 09:52*

学习学习

## 回复 by mb_xjdhrmck (#33)

*2025-10-31 09:59*

6666

## 回复 by 正己 (#34)

*2025-10-31 10:22*

sf佬牛逼，带带弟弟

## 回复 by wx_收纸箱的咸鱼王 (#35)

*2025-10-31 11:32*

111

## 回复 by 倾心Deep (#36)

*2025-10-31 17:35*

666

## 回复 by mb_pfsyahdt (#37)

*2025-11-1 00:02*

带派

## 回复 by mb_uktygsmq (#38)

*2025-11-1 09:02*

学习学习

## 回复 by 东方玻璃 (#39)

*2025-11-1 18:15*

好文

## 回复 by ikunnn (#40)

*2025-11-1 19:52*

111111

## 回复 by Circ1e (#41)

*2025-11-3 15:58*

111

## 回复 by mb_cbgtaveo (#42)

*2025-11-3 17:30*

66666666

## 回复 by 黄石 (#43)

*2025-11-5 10:50*

感谢分享

## 回复 by uni7corn (#46)

*2025-11-11 14:20*

感谢分享

## 回复 by guage (#47)

*2025-11-12 11:29*

11

## 回复 by mb_uvyukvot (#48)

*2025-11-12 13:18*

学习

## 回复 by mb_lakweznz (#49)

*2025-11-12 21:29*

2

## 回复 by Whoami默 (#50)

*2025-11-13 18:48*

1

## 回复 by guijingwen (#51)

*2025-11-13 19:55*

66

## 回复 by wx_Kj (#52)

*2025-11-13 21:40*

1

## 回复 by nevinhappy (#53)

*2025-11-13 22:25*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by xinhu (#54)

*2025-11-16 15:36*

666

## 回复 by GEKEZYX (#55)

*2025-11-21 13:56*

666

## 回复 by git_71735namngsec-netizen (#56)

*2025-11-22 15:04*

666

## 回复 by 智取棋 (#57)

*2025-11-24 09:22*

666

## 回复 by 莱茵 (#58)

*2025-12-25 17:23*

厉害

## 回复 by mb_advzsyem (#59)

*2026-1-9 10:47*

感谢分享

## 回复 by Zepp7289 (#60)

*2026-1-16 10:39*

学习

## 回复 by mb_ysikfhxt (#61)

*2026-2-16 20:35*

1

## 回复 by devil_1 (#62)

*2026-3-21 19:51*

666

## 回复 by 小迷糊ddd (#63)

*2026-4-5 21:18*

感谢分享，受教了。

## 回复 by iBa0 (#64)

*2026-4-6 14:44*

123

## 回复 by mb_mddfhmcj (#65)

*2026-5-8 09:39*

看看

## 回复 by Nijika (#66)

*2026-7-21 10:17*

666

## 回复 by mb_qimctavn (#67)

*2026-7-21 10:47*

6

## 回复 by ShadowSsdt (#68)

*2026-7-21 20:35*

大佬，可以提供一下样本么，想实操一下

## 回复 by ShadowSsdt (#69)

*2026-7-22 10:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_hcqpswwu](https://bbs.kanxue.com/user-1037289.htm)
>  有样本学习一下吗
>

大佬与样本么，可以分享一下么

## 回复 by mb_kgneopde (#70)

66666

## 回复 by mb_irhdtnzm (#71)

1
