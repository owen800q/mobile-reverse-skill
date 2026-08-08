---
title: '[原创]自定义Linker SO修复'
url: https://bbs.kanxue.com/thread-291861.htm
tid: 291861
author: 九天666
date: '2026-07-02'
tags: [Android安全, 原创, 基础理论, 逆向分析, 协议分析, 混淆加固, HOOK注入, 工具脚本]
crawled_at: '2026-08-08T10:04:46+00:00'
replies: 34
---

看之前最好是对linker相关的知识有一定了解，这里推荐文章[Android从ELF-Loader到自定义Linker的实现及原理](https://bbs.kanxue.com/thread-290643.htm#msg_header_h2_36)，该文章写的很详细，很好。

## 概述

因为这是一个壳so(Shell SO)内嵌一个so(Payload SO)。system.loadlibray加载壳so，遵循linker加载so的流程。内嵌so是由壳so通过自定义Linker去加载。

本文目的主要针对壳so和内嵌so的修复，方便IDA等工具分析。

## 壳so修复

ida加载so，主要可以看到这里，大部分节区信息都被抹掉，导致ida无法正常识别。因为ida是静态分析的,所以依赖section节区。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_DCYB2Y7K5P4T9TQ.png)

这里的sub_2A30和sub_2A50很明显分别是**dlopen**和**dlsym**，但是这里也没有识别出来。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_Y82SG2P7DDR3PEU.png)

所以后面需要把壳入口.init_array和系统函数进行修复还原。

### 1 .init_array

这里会优先执行.init_array节区里的函数，所以先找到这个节区里有哪些函数。

PT_DYNAMIC:动态链接信息节

Program里 PT_DYNAMIC(.dynamic) 找 DT_INIT_ARRAY（d_tag: 0x19）和 DT_INIT_ARRAYSZ (d_tag: 0x1b)

![image](https://bbs.kanxue.com/upload/attach/202607/947335_632R7TVTE3WJNKZ.png)

.dynamic里每个表项数据有16字节,相关结构如下。

>
> typedef struct {
>
>
>  Elf64_Sxword d_tag;
>
>
>  union {
>
>
>
>
> ```python
> Elf64_Xword d_val;
>
> Elf64_Addr d_ptr;
> ```
>
>
>  } d_un;
>
>
> } Elf64_Dyn;
>
>
>

.dynamic表数据：

```plain
01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00
01 00 00 00 00 00 00 00 09 00 00 00 00 00 00 00
01 00 00 00 00 00 00 00 17 00 00 00 00 00 00 00
01 00 00 00 00 00 00 00 21 00 00 00 00 00 00 00
01 00 00 00 00 00 00 00 2E 00 00 00 00 00 00 00
01 00 00 00 00 00 00 00 36 00 00 00 00 00 00 00
01 00 00 00 00 00 00 00 3E 00 00 00 00 00 00 00
0E 00 00 00 00 00 00 00 62 08 00 00 00 00 00 00
10 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
19 00 00 00 00 00 00 00 08 4D 01 00 00 00 00 00
1B 00 00 00 00 00 00 00 10 00 00 00 00 00 00 00
1A 00 00 00 00 00 00 00 18 4D 01 00 00 00 00 00
1C 00 00 00 00 00 00 00 10 00 00 00 00 00 00 00
04 00 00 00 00 00 00 00 00 C0 16 00 00 00 00 00
05 00 00 00 00 00 00 00 00 B0 16 00 00 00 00 00
06 00 00 00 00 00 00 00 00 90 16 00 00 00 00 00
0A 00 00 00 00 00 00 00 77 08 00 00 00 00 00 00
0B 00 00 00 00 00 00 00 18 00 00 00 00 00 00 00
03 00 00 00 00 00 00 00 18 4F 01 00 00 00 00 00
02 00 00 00 00 00 00 00 40 02 00 00 00 00 00 00
14 00 00 00 00 00 00 00 07 00 00 00 00 00 00 00
17 00 00 00 00 00 00 00 30 27 00 00 00 00 00 00
07 00 00 00 00 00 00 00 E8 26 00 00 00 00 00 00
08 00 00 00 00 00 00 00 48 00 00 00 00 00 00 00
09 00 00 00 00 00 00 00 18 00 00 00 00 00 00 00
18 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
FB FF FF 6F 00 00 00 00 01 00 00 00 00 00 00 00
F9 FF FF 6F 00 00 00 00 02 00 00 00 00 00 00 00
\```

>
> 19 00 00 00 00 00 00 00 08 4D 01 00 00 00 00 00
>
>
>

DT_INIT_ARRAY：0x14D08

>
> 1B 00 00 00 00 00 00 00 10 00 00 00 00 00 00 00
>
>
>

DT_INIT_ARRAYSZ: 0x10

这里可以看到，.init_array节区起始是0x14D08，大小为0x10个字节,每8个字节为1个函数槽,也就是有两个函数槽在里面。

进入ida查看,这里的地址0x14D08里面怎么没有对应存储的函数呢，接下来就要去.rela.dyn里去找0x14D08地址存储的函数。因为这里是变量赋值,所以要去重定位表.rela.dyn里查看。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_7P678WEP4YSWCE7.png)

![image](https://bbs.kanxue.com/upload/attach/202607/947335_UG552JYMFQXFYKP.png)

这里在节表里没有发现.rela.dyn,看来也是抹除了，所以需要再去.dynamic里找到.rela.dyn并修复。

#### 1） 修复.rela.dyn

.dynamic表获取对应数据

>
> 07 00 00 00 00 00 00 00 E8 26 00 00 00 00 00 00
>
>
>

DT_RELA : 0x26e8

>
> 08 00 00 00 00 00 00 00 48 00 00 00 00 00 00 00
>
>
>

DT_RELASZ: 0x48

然后点开节表所有的SHN_UNDEF，找里面的s_type为SHT_RELA的节，这里找到两个重定位表,那么用哪一个呢？因为.rela.dyn的s_info为0，所以这里我们就选s_info为0的节。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_QA8XNFGSMNTNNAS.png)

把上面获取的0x26e8和0x48对应填入。然后s_name的偏移也要在.shstrtab里找到.rela.dyn的字符串偏移。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_8XP978CX4GUG5Z4.png)

![image](https://bbs.kanxue.com/upload/attach/202607/947335_4396G49NDAS8ZCK.png)

然后F5刷新下修改的文件。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_95H4YTGXK7Z6PAF.png)

ida打开，在ida里可以看到,有需要被修复的地址就自动填充进去了，这里只有一个函数槽需要被修复。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_SCUUYX99YCRVECG.png)

#### 2） 修复.init_array

但是这样感觉还不得劲,想让它的.init_array节区显示出来,继续去SHN_UNDEF找s_type为SHT_INIT_ARRAY

![image](https://bbs.kanxue.com/upload/attach/202607/947335_6A8YPVTPUDTVWN6.png)

修复后：

![image](https://bbs.kanxue.com/upload/attach/202607/947335_5RS4P9KBWGGTJP2.png)

这里的s_offset可以不填。我们只保证虚拟内存地址(s_addr)是正确的就行了。

进入ida可以看到.init_array已经被修复了。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_FDCBVU6X6AEEFVM.png)

### 2. 修复系统函数显示

进入0x4780系统函数,明显看出sub_2A30是**dlopen**函数，sub_2A50是**dlsym**函数，但是这里都是以函数偏移显示的，没有正常的符号名。那么接下来就要修复这类符号名显示问题。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_52M3S7WWDAPBDBH.png)

看.dynsym是否正常显示

![image](https://bbs.kanxue.com/upload/attach/202607/947335_9TXZD5X8P9ERDBK.png)

看来.dynsym里的所有数据也是被抹除了。

#### 1） 修复.dynsym

>
> 06 00 00 00 00 00 00 00 00 90 16 00 00 00 00 00
>
>
>

DT_SYMTAB: 0x169000

原始的是0x2268，所以这里是假的.dynsym。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_W6QXBFQ4BGBW8RV.png)

修复后：

![image](https://bbs.kanxue.com/upload/attach/202607/947335_9CHQESP3G59H5JG.png)

---

**为什么这里s_offset是0x129000？**

![image](https://bbs.kanxue.com/upload/attach/202607/947335_VMSEBJEDKA7N3SC.png)

这里有个小细节，一个程序头表是由多个节表组成，程序头表里，p_offset和p_vaddr的差值是多少，那么应用在对应的节表里时，s_offset和s_addr也应该是这个差值。ida这里工具解析ELF文件时，会以内存的模式去加载，这里就会去把物理文件的偏移s_offset的数据复制到虚拟内存的偏移s_addr处。

因为0x169000刚好处在segment `0x47000~(0x47000+0x1256d0)` 这个范围里。p_vaddr是在p_offset的基础上增加了0x40000。所以这里文件偏移应该是`0x169000-0x40000=0x129000`。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_X9SBUVJWXYRUM3S.png)

函数在010Editor里已经能正常显示了，这里就好了吗？不是，还需要去修复.rela.plt 函数重定位表。

#### 2） 修复.rela.plt

>
> 17 00 00 00 00 00 00 00 30 27 00 00 00 00 00 00
>
>
>

DT_JMPREL：0x2730

>
> 02 00 00 00 00 00 00 00 40 02 00 00 00 00 00 00
>
>
>

DT_PLTRELSZ：0x240

![image](https://bbs.kanxue.com/upload/attach/202607/947335_HFTAGTEBG22EMR3.png)

修复后：

![image](https://bbs.kanxue.com/upload/attach/202607/947335_3NGRMQN7A3XWD6J.png)

s_flags: 这里需要的模式是ALLOC|INFO_LINK，也就是0x42。

s_link: 链接的节.dynsym，在节表的索引。

s_info: 这是got/.got.plt表在节表的索引。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_ZHZT89WV8QZKXY4.png)

由上可知，s_info我们还不清楚是多少，并且节表字符串里有.got，这里我们要去修复.got表。

#### 3） 修复.got

**怎么选?**

只要s_type为SHT_PROGBITS ，s_flags为SF64_Alloc_Exec ，都可以作为.got表。这里就选节表索引14作为.got表。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_8RTB4VZA2UNQHGH.png)

查询.dynamic

>
> 03 00 00 00 00 00 00 00 18 4F 01 00 00 00 00 00
>
>
>

DT_PLTGOT: 0x14f18

.got表的大小需要自己计算，上面已知DT_PLTRELSZ大小为0x240，因为.rela.plt的每项大小为24字节，这里就有0x240/24=24 个函数，并且.got表的前3个槽位是填充，每个槽位大小为8字节，这里.got size则为(24+3)*8=0xd8

修复后：

![image](https://bbs.kanxue.com/upload/attach/202607/947335_K2FC56EU4NJ5P6J.png)

这里.got表也修复了，接着就可以补全上面.rela.plt的s_info信息,也就是got表在节表的索引为0xE

![image](https://bbs.kanxue.com/upload/attach/202607/947335_MMCGWUC7XU55B4X.png)

### 3. 壳SO修复成果

ida查看,这里函数符号也都能正常显示了

![image](https://bbs.kanxue.com/upload/attach/202607/947335_M363C9YEE2TY7VC.png)

![image](https://bbs.kanxue.com/upload/attach/202607/947335_YX37YWYMYJ7U84Z.png)

### 4.分析壳so的运作

##### 1.初始化分析

这里是在init_array里进行内嵌so的解密操作，并用自定义linker去加载内嵌so

init_array的运作函数sub_4780

![image](https://bbs.kanxue.com/upload/attach/202607/947335_YTF4GPEHH9HNGV5.png)

这些地址处的数据比较重要

>
>  dword_15040 = dword_15008;
>
>
>  dword_15064 = dword_1500C;
>
>
>  dword_15078 = dword_15010;
>
>
>  dword_15030 = dword_15014;
>
>
>  dword_15088 = dword_15018;
>
>
>  dword_15084 = dword_1501C;
>
>
>  dword_1507C = dword_15020;
>
>
>

![image](https://bbs.kanxue.com/upload/attach/202607/947335_CTN5G87DTYZ9BXX.png)

dword_15040：内嵌so在壳so的起始地址

dword_15064：壳.dynsym节区的大小

dword_15078：壳.dynstr节区的大小

dword_15030：壳.dynsym节区在内存里的地址(s_addr)

dword_15088：壳.dynstr节区在内存里的地址(s_addr)

dword_15084：壳.hash节区在内存里的地址(s_addr)

dword_1507C：解密内嵌so的密钥偏移地址

垃圾代码，主要是干扰静态分析的，不用理会

![image](https://bbs.kanxue.com/upload/attach/202607/947335_UC7KKHAMTTZ92FU.png)

##### 2.获取解密密钥

读取**dword_1507C**地址**0x14**个字节的内容到**qword_15050**处，前16个字节是rc4解密的密钥，后4个字节是异或解密的密钥(这里值是单字节)。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_WW2EZWHC6GPX3W3.png)

![image](https://bbs.kanxue.com/upload/attach/202607/947335_RJJ9H9PFUZH6H9C.png)

010Editor查看可知

>
> rc4密钥:2F CE A7 38 12 73 AC 59 57 7E 56 B5 5F 59 C9 85
>
>
> xor密钥字节：0x95
>
>
>

##### 3.解密函数

sub_3184：rc4解密函数

- a1: 加密输入\解密输出

![image](https://bbs.kanxue.com/upload/attach/202607/947335_ZT52TB56BPSPUVY.png)

sub_2B1C：xor异或解密函数

- a1: 加密输入\解密输出
- a2: 起始偏移
- a3: 需要解密的长度

![image](https://bbs.kanxue.com/upload/attach/202607/947335_AQNX9D622U2B3YD.png)

##### 4.rc4解密内嵌so ELF头数据(0x40字节)

![image](https://bbs.kanxue.com/upload/attach/202607/947335_4QU9RWE8THEXX3S.png)

##### 5.xor解密

这里解密内嵌so前0x1000字节内容，主要解密出程序头表的内容。用于后续装载PT_Load段数据，和重定位修复。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_F4Q4BWZ9YB5CGEC.png)

解密PT_Load

这里是解密第二个PT_Load段

![image](https://bbs.kanxue.com/upload/attach/202607/947335_CZD4PTUDMP8YNSD.png)

从内嵌so偏移64字节开始解密，这里是解密第一个PT_Load段

![image](https://bbs.kanxue.com/upload/attach/202607/947335_RBJ3XCB3DDJAEH6.png)

##### 6.计算PT_Load段需要的空间

计算PT_Load段在内存里占用的空间大小，也就是so运行需要的空间大小。用mmap申请一段匿名空间，供后面从文件里装载数据到这段匿名空间。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_FUSJAUXWDSMJK73.png)

装载数据

![image](https://bbs.kanxue.com/upload/attach/202607/947335_CCDXRBN9SK75BWX.png)

##### 7.解析Dynamic段

里面包含节区的偏移数据内容和大小

![image](https://bbs.kanxue.com/upload/attach/202607/947335_2TASE9X76MW9V3G.png)

##### 8.修复重定位表

sub_2CD0

![image](https://bbs.kanxue.com/upload/attach/202607/947335_GSXQBEH6S72SSSD.png)

##### 9.内嵌so初始化函数调用

init\init_array函数调用

![image](https://bbs.kanxue.com/upload/attach/202607/947335_4TAZWUBU529M35J.png)

sub_303C：JNI_OnLoad函数符号地址解析

##### 10.回填数据

把内嵌so的**.hash**、**.dynsym**、**.dynstr **这三个节表的数据回填进壳so的对应地址。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_ND64UJ63DBDPMRB.png)

## 内嵌so修复

这里以两种方案来解决内嵌so的修复

1）因为内嵌so是加密了的，通过解密运算得到so

2）从内存dump得到解密后的so

### 方案① 解密得到内嵌so

从壳so的运作流程分析可以知道，

- 内嵌so的起始地址在壳so偏移0x8000地址处。
- 内嵌so的header(前0x40字节)数据，是用rc4解密得到。
- 内嵌so从0x40偏移处开始都是异或解密

整体解密流程知道了，下面用python进行还原出整个内嵌so。

#### 1.引用库

>
> import lief
>
>
> import hexdump
>
>
> import struct
>
>
> from Crypto.Cipher import ARC4
>
>
>

>
> pip install lief==0.17.6
>
>
> pip install hexdump==3.3
>
>
> pip install pycryptodome==3.23.0
>
>
>

- lief: 用于解析二进制文件格式
- hexdump: 以内存形式打印数据，方便查看
- pycryptodome: 加密库，这里需要rc4

#### 2.包装壳so

so名字脱敏处理了

这里通过SoFixer构造一个实例,init初始化主要做了对so的解析

```python
path = "shell.so"
key_offset = 0x1281DD
shell_so = SoFixer(path)
\```

```python
class SoFixer:
    def __init__(self, path):
        self.path = path
        self.binary = lief.ELF.parse(path)
        if isinstance(path, str):
            self.so_base = memoryview(bytearray(open_so(path)))  # str形式传入
        else:
            self.so_base = memoryview(bytearray(path))  # bytes形式传入

        self.Ehdr = self.so_base[0:64]

        # 解析Program
        self.e_phoff = self.binary.header.program_header_offset
        self.e_phentsize = self.binary.header.program_header_size
        self.e_phnum = self.binary.header.numberof_segments
        self.Phdr = self.so_base[self.e_phoff:]

        # 解析Section
        self.e_shoff = self.binary.header.section_header_offset
        self.e_shentsize = self.binary.header.section_header_size
        self.e_shnum = self.binary.header.numberof_sections
        self.e_shtrndx = self.binary.header.section_name_table_idx
        self.Shdr = self.so_base[self.e_shoff:]
\```

#### 3.定位内嵌so

```python
payload_so = shell_so.so_base[0x8000:]
\```

#### 4.定位解密密钥

```python
key = shell_so.so_base[key_offset:(key_offset + 20)]
\```

#### 5.获取到rc4和xor的密钥key

```python
rc4_key = key[:16]
xor_key = read_u32(key[16:20], 0)
\```

#### 6.解密内嵌SO的ELF Header

```python
payload_so_ehdr = rc4(payload_so[:64], rc4_key)
# hexdump_bytes(payload_so,64)
memcpy(payload_so, payload_so_ehdr, 64)
print("Payload SO Header解密完成")
\```

#### 7.包装内嵌SO

```python
payload_so = SoFixer(bytes(payload_so))
\```

#### 8.计算内嵌SO的大小

从so文件格式可以知道，Section Header Table是在整个so的尾部，所以我们只需要知道节头表的起始地址，和整个表的大小，就可以得到so文件的大小。

通过上面rc4解密，拿到ELF Header数据后，我们就可以拿到**e_shoff、e_shnum、e_shentsize**数据，通过这些就可以计算出节头表的结束地址，这个也就是整个so的文件大小。

```python
payload_so_size = payload_so.e_shoff + payload_so.e_shnum * payload_so.e_shentsize
\```

#### 9.异或解密出整个SO里除ELF Header以外的所有数据

```python
xor_decrypt(payload_so.so_base, payload_so.e_phoff, payload_so_size-payload_so.e_phoff, xor_key)
\```

#### 10.保存内嵌so

```python
payload_so.save("payload_so.so", payload_so.so_base[:payload_so_size])
\```

#### 11.内嵌so解密成果展示

##### 010Editor

所有节表正常显示

![image](https://bbs.kanxue.com/upload/attach/202607/947335_R3HXDGYZ36ACQSW.png)

函数符号也可以显示

![image](https://bbs.kanxue.com/upload/attach/202607/947335_FA8R2SMK4F3P2BW.png)

##### IDA

![image](https://bbs.kanxue.com/upload/attach/202607/947335_FSXWUWCMWY956KW.png)

### 方案② 内存dump得到内嵌so

这里面字符串都是加密了的，需要在代码运行后，这个时候字符串是解密的了，从内存里dump数据，就能清晰的知道代码里做了什么。

根据linker的执行流程，在so加载完后会先经过init、init_array初始化，再去解析JNI_OnLoad函数，有就执行。因为壳本身是没有JNI_OnLoad函数的，而内嵌so是有JNI_OnLoad函数，所有检测和dex释放都是在这里面进行的，壳so把内嵌so的三个节表给回填进了壳的数据空间，此时壳里就会有内嵌so的JNI_OnLoad函数了,linker就会去执行JNI_OnLoad函数。

所以直接在JNI_OnLoad函数执行完后去dump数据,这里不演示了,只讲so的修复，dump的so会提供。

#### 1.现象

查看dump下来的so数据，ELF Header和Program Header Table都是解密后的数据，就后面的Section Header Table的信息没有，这是因为linker加载so，是可以不需要Section Header Table信息的，这个只是给类似IDA这类工具分析所需要的。这里我们就去修复节信息。

![image](https://bbs.kanxue.com/upload/attach/202607/947335_CMXY76F7XPT6KD6.png)

![image](https://bbs.kanxue.com/upload/attach/202607/947335_CTSH4X8YCEKXVRU.png)

#### 2.包装dump so

```python
path = "dump.so"
fixer = SoFixer(path)
\```

#### 3.收集PT_Load段

一个段是由多个节组成，节表的addr和offset修复需要参考所属段的addr和offset的差值。供后续节表修复作准备。

```python
fixer.collect_load_segments()
\```

>
> def collect_load_segments(self):
>  segments = self.binary.segments
>  self.load_segments = list()
>
>
>

```python
for i in range(self.e_phnum):
    segment = segments[i]
    if segment.type == 1:
        pls = self.PT_Load_Segment(segment.virtual_address,
                                   segment.virtual_address + segment.virtual_size,
                                   segment.file_offset,
                                   segment.physical_size,
                                   segment.virtual_size)
        self.load_segments.append(pls)
\```

>
>

#### 4.修复所有段的地址和大小

因为是内存dump下来的so，物理地址和大小已经没有意义了，这里就把所有物理地址和大小全部替换为内存地址和大小。

```python
fixer.fix_segment()
\```

>
> def fix_segment(self):
>  segments = self.binary.segments
>  for i in range(self.e_phnum):
>  segment = segments[i]
>  pt = self.Phdr[i * self.e_phentsize:]
>
>
>

```python
    if segment.file_offset != segment.virtual_address:
        write_u64(pt, 0x8, segment.virtual_address)  # 修改p_offset为p_vaddr
    if segment.physical_size != segment.virtual_size:
        write_u64(pt, 0x20, segment.virtual_size)  # 修改p_filesz为pmemsz
\```

>
>

#### 5.清零所有节头表

dump so里节表里的信息全是无用的大数据，这里直接全部清0处理，免得拖入ida时会提示报错信息。

```python
fixer.clean_section()
\```

>
> def clean_section(self):
>  for i in range(self.e_shnum):
>  st = self.Shdr[i * self.e_shentsize:]
>  memset(st, 0, self.e_shentsize)
>
>
>

#### 6.修复节名字符串表

既然要修复节表，肯定要有所有的节名，这里直接引用的壳so里的节名字符串表。位置就放置在Section Header Table的前面。

为什么要这样放? 根据标准ELF 文件格式来的，节名字符串表(.shstrtab)在所有节表里的最后一个。

```python
fixer.fix_shstrtab()
\```

>
> def fix_shstrtab(self):
>  # 准备节头字符串表的数据内容，从壳so里获取的数据
>  shstrtabl_hex_str = """
>  00 2E 65 68 5F 66 72 61 6D 65 5F 68 64 72 00 2E
>  66 69 6E 69 5F 61 72 72 61 79 00 2E 69 6E 69 74
>  5F 61 72 72 61 79 00 2E 73 68 73 74 72 74 61 62
>  00 2E 65 68 5F 66 72 61 6D 65 00 2E 72 65 6C 61
>  2E 70 6C 74 00 2E 72 65 6C 61 2E 64 79 6E 00 2E
>  63 6F 6D 6D 65 6E 74 00 2E 64 79 6E 61 6D 69 63
>  00 2E 72 6F 64 61 74 61 00 2E 64 79 6E 73 74 72
>  00 2E 64 79 6E 73 79 6D 00 2E 64 61 74 61 00 2E
>  74 65 78 74 00 2E 68 61 73 68 00 2E 62 73 73 00
>  2E 67 6F 74 00
>  """
>  shstrtabl_data = bytes.fromhex(shstrtabl_hex_str.replace("\n", " ").strip())
>
>
>

```python
# 定位节头字符串表里数据内容的s_offset
"""
标准ELF，节名字符串表的数据内容就在Section Table的上方紧挨着。
"""
## 向上8字节对齐
align_shstrtab_data_len = align_up(len(shstrtabl_data))

# 复制数据
## 标准ELF的节头字符串表都是在节头表的上方
shstrtab_s_offset = self.e_shoff - align_shstrtab_data_len
# print_format("shstrtab_s_offset", hex(shstrtab_s_offset))
memcpy(self.so_base[shstrtab_s_offset:], shstrtabl_data, len(shstrtabl_data))
# hexdump_bytes(self.so_base[shstrtab_s_offset:],len(shstrtabl_data))

# 修复
shstrtab_item = self.Shdr[self.e_shtrndx * self.e_shentsize:]
shstrtab_section = SoFixer.Section(shstrtab_item)
shstrtab_section.set_name(0x27)
shstrtab_section.set_type(lief.ELF.Section.TYPE.STRTAB.value)
shstrtab_section.set_flags(lief.ELF.Section.FLAGS.NONE.value)
shstrtab_section.set_addr(0)
shstrtab_section.set_offset(shstrtab_s_offset)
shstrtab_section.set_size(len(shstrtabl_data))
shstrtab_section.set_link(0)
shstrtab_section.set_info(0)
shstrtab_section.set_addralign(1)
shstrtab_section.set_entsize(0)
\```

>
>

#### 7.解析Dynamic Segment

通过解析Dynamic Segment去获取到需要的节表信息，后面就是要修复这些。

>
> .dynstr
>
>
> .hash (这里只用来计算.dynsym的大小)
>
>
> .dynsym
>
>
> .rela_dyn
>
>
> .got
>
>
> .rela_plt
>
>
> .init_array （可选）
>
>
>

这里1，是采用内存模式去解析,默认是文件模式。

```python
fixer.parse_dynamic(1)
\```

>
> def parse_dynamic(self, mode=0):
>  self.dynstr = None
>  self.dynstr_size = None
>  self.hash = None
>  self.dynsym = None
>  self.rela_dyn = None
>  self.rela_dyn_size = None
>  self.got = None
>  self.rela_plt = None
>  self.rela_plt_size = None
>  self.init_array = None
>  self.init_array_size = None
>
>
>

```python
dynamic_off = None
dynamic_sz = None
for seg in self.binary.segments:
    if seg.type == 2:  # 找到Dynamic Segment
        if mode == 1:
            dynamic_off = seg.virtual_address
            dynamic_sz = seg.virtual_size
        else:
            dynamic_off = seg.file_offset
            dynamic_sz = seg.physical_size
        break
dynamic_size = dynamic_sz // 16  # 每项是16字节,获取dynamic的表项数

dynamic = self.so_base[dynamic_off:]

for i in range(dynamic_size):
    dyn = dynamic[i * 16:]  # 每项dyn的起始
    tag = read_u64(dyn, 0)  # dyn类型
    val = read_u64(dyn, 8)  # dyn数值(offset/num)

    if tag == lief.ELF.DynamicEntry.TAG.STRTAB:
        self.dynstr = val
    elif tag == lief.ELF.DynamicEntry.TAG.STRSZ:
        self.dynstr_size = val
    elif tag == lief.ELF.DynamicEntry.TAG.HASH:
        self.hash = val
    elif tag == lief.ELF.DynamicEntry.TAG.SYMTAB:
        self.dynsym = val
    elif tag == lief.ELF.DynamicEntry.TAG.RELA:
        self.rela_dyn = val
    elif tag == lief.ELF.DynamicEntry.TAG.RELASZ:
        self.rela_dyn_size = val
    elif tag == lief.ELF.DynamicEntry.TAG.PLTGOT:
        self.got = val
    elif tag == lief.ELF.DynamicEntry.TAG.JMPREL:
        self.rela_plt = val
    elif tag == lief.ELF.DynamicEntry.TAG.PLTRELSZ:
        self.rela_plt_size = val
    elif tag == lief.ELF.DynamicEntry.TAG.INIT_ARRAY:
        self.init_array = val
    elif tag == lief.ELF.DynamicEntry.TAG.INIT_ARRAYSZ:
        self.init_array_size = val
\```

>
>

#### 8.解析.hash节表

```python
fixer.parse_hash()
\```

>
> def parse_hash(self):
>  if self.hash is not None:
>  diff = self.calcula_diff(self.hash)
>  self.hash_table = self.so_base[self.hash - diff:]
>
>
>

```python
    self.nbucket = read_u32(self.hash_table, 0)
    self.nchain = read_u32(self.hash_table, 4)
    print_format("nbucket", hex(self.nbucket))
    print_format("nchain", hex(self.nchain))
else:
    raise ValueError("not find DT_HASH")
\```

>
>

#### 9.节表修复

这里面功能大致一样的，内容重复，代码会放后面。

```python
# 修复动态符号字符串表
fixer.fix_dynstr()
# 修复动态符号表
fixer.fix_dynsym()
# 修复数据重定位表
fixer.fix_rela_dyn()
# 修复got表
fixer.fix_got()
# 修复函数重定位表
fixer.fix_rela_plt()
# 修复.init_array表
fixer.fix_init_array()
\```

#### 10.运行

```python
def fix_dump_so_main():
    path = "dump.so"
    # 包装so
    fixer = SoFixer(path)

    # 收集PT_Load段
    fixer.collect_load_segments()

    # 修复所有段的地址和大小
    fixer.fix_segment()

    # dump下来的节头表数据全是被抹除了，这里直接清零所有节头表
    fixer.clean_section()

    # 修复节名字符串表
    fixer.fix_shstrtab()

    # 解析Dynamic Segment
    fixer.parse_dynamic(1)

    # 解析.hash节表
    fixer.parse_hash()

    # 修复动态符号字符串表
    fixer.fix_dynstr()
    # 修复动态符号表
    fixer.fix_dynsym()
    # 修复数据重定位表
    fixer.fix_rela_dyn()
    # 修复got表
    fixer.fix_got()
    # 修复函数重定位表
    fixer.fix_rela_plt()
    # 修复.init_array表
    fixer.fix_init_array()

    # 获取JNI_OnLoad函数地址
    fixer.find_symbol("JNI_OnLoad")

    fixer.save("dump_fix.so")
    print("Dump SO 修复完成")
\```

#### 11.修复结果展示

进入0x1AD84函数

##### dump 修复

![image](https://bbs.kanxue.com/upload/attach/202607/947335_NSV4B5UDGW76Z89.png)

##### 解密内嵌so修复

![image](https://bbs.kanxue.com/upload/attach/202607/947335_EX29TNH3CDY7KC3.png)

对比这两个就能明显看出，dump修复里面字符串是解密后的了，这里在做对libc.so的crc检测。

GitHub仓库下载: <https://github.com/jiutian666/fix_so_script.git>

---

# 回复

## 回复 by MaYil (#2)

*2026-7-2 17:14*

感谢分享

## 回复 by mb_sqetvntx (#3)

*2026-7-2 17:24*

学习

## 回复 by 北袅 (#4)

*2026-7-2 17:25*

学到了

## 回复 by iBa0 (#5)

*2026-7-2 20:17*

666

## 回复 by SomeMx (#6)

*2026-7-2 21:39*

学习一下

## 回复 by wx_Huber Barrientos (#7)

*2026-7-2 23:25*

666

## 回复 by mb_ldbucrik (#8)

*2026-7-3 08:40*

向大佬学习

## 回复 by huangjw (#9)

*2026-7-3 09:36*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by Zepp7289 (#10)

*2026-7-3 09:50*

tql

## 回复 by x1a0f3n9 (#11)

*2026-7-4 05:32*

牛逼，感谢分享，看完了，学到了很多

## 回复 by mb_qimctavn (#12)

*2026-7-4 13:51*

6

## 回复 by ldehua (#13)

*2026-7-4 14:00*

感谢分享

## 回复 by 上官兮唐 (#14)

*2026-7-4 14:20*

感谢分享，学习

## 回复 by koflfy (#15)

*2026-7-4 15:05*

第一步那里，直接在elf头里把节偏移地址清0，再用ida打开，init_array就正常了。

## 回复 by 一栋奥特曼 (#16)

*2026-7-4 15:12*

感谢分享，学习

## 回复 by GEKEZYX (#17)

*2026-7-4 20:07*

666

## 回复 by 墨穹呢 (#18)

*2026-7-4 20:36*

感谢分享

## 回复 by wx_北极星_493 (#19)

*2026-7-7 03:14*

66

## 回复 by buluo533 (#20)

*2026-7-7 09:57*

学习了

## 回复 by Imxz (#21)

*2026-7-7 16:09*

tql

## 回复 by B.M.K (#22)

*2026-7-7 18:31*

666

## 回复 by 灬哈密瓜 (#23)

*2026-7-8 09:29*

终于看到有好文章了. 而不是AI文.

## 回复 by wx_kx92911 (#24)

*2026-7-9 09:52*

感谢分析

## 回复 by hanjiefang (#25)

*2026-7-10 17:40*

666

## 回复 by Sigil (#26)

*2026-7-14 15:55*

1

## 回复 by SamPoson (#27)

*2026-7-14 17:49*

111

## 回复 by cobe (#28)

*2026-7-14 18:38*

666

## 回复 by 章康 (#29)

*2026-7-16 22:49*

66

## 回复 by wx_插曲 (#30)

*2026-7-21 13:41*

6666

## 回复 by GeQ1an (#31)

*2026-7-26 19:54*

66666666

## 回复 by scllqk (#32)

学习

## 回复 by wx_coddvccwyh (#33)

6666

## 回复 by wx_宇克鴻 (#34)

66666

## 回复 by mb_ysikfhxt (#35)

111
