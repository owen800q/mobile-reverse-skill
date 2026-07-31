---
title: '[原创] X-Apple-ActionSignature分析'
url: https://bbs.kanxue.com/thread-291582.htm
tid: 291582
author: 九天666
date: '2026-06-13'
tags: [Android安全, 原创, 逆向分析, 协议分析, 脱壳反混淆]
crawled_at: '2026-07-31T15:03:07+08:00'
replies: 57
---

分析对象: apple music
Android端

## 概述

这里面的算法还是比较复杂的,混淆都是BR间接跳转混淆,使得分析人员无法静态分析,然后再搭配MBA混淆及平坦化,让逆向门槛更上一步,堆栈内存地址也是加密处理了的,用到的时候会通过算法运算解密出来,再取数据。

如果只看trace去解决算法的话,会耗费大量时间，因为里面算法大量用到了白盒加密,基于查表的方法达到一个加密目的,这是其一,其二是会用一些魔改算法,比如这里频繁用到了梅森旋转算法(MT19937)，每次更新MT表数据都会迭代624轮,光初始化都执行了128次，别说后面的一些切页操作。

这里我用的是trace再配合idapyhton去混淆就可以很好的分析了，在效率是有很大提升。

[GumTrace](https://github.com/lidongyooo/GumTrace.git): 真机trace工具

[trace-ui](https://github.com/imj01y/trace-ui.git): trace日志分析工具

这两个工具对于算法分析,大大提升了分析效率,很棒!感谢两位大佬的无私奉献！具体使用就去Github上查看。

## 环境

手机: pixel 6 os: 15

Frida: 17.8.2

## 分析

### 去br间接跳转混淆

为了能方便分析代码逻辑，去混淆是不可缺少的步骤。

先对目标函数进行trace,然后提取里面所有BR地址和跳转的目标地址。

格式:

```plain
{'0x228620': {'0x228624'}, '0x228664': {'0x228684'}, '0x1d7724': {'0x1d772c'}, '0x1d773c': {'0x1d7770', '0x1d77e8', '0x1d78d8'}, '0x1fda60': {'0x1fda68'}, '0x1fda8c': {'0x1fdad4', '0x1fdaf4', '0x1fda90'}, '0x1d7988': {'0x1d798c'}, '0x1d79c0': {'0x1d82d4'}, '0x1d8308': {'0x1d8310'}, '0x20858c': {'0x208594'}, '0x2085b0': {'0x2085b4'}, '0x208668': {'0x20866c'}, '0x2086a8': {'0x208ad4'}, '0x208b00': {'0x208c68'}, '0x208c98': {'0x2086e8'}, '0x208704': {'0x20870c'}, '0x208750': {'0x208b3c'}, '0x208b78': {'0x20911c'}, '0x209158': {'0x209414'}, '0x20944c': {'0x2097cc'}, '0x209804': {'0x209808'}, '0x209838': {'0x209d90'}, '0x209da8': {'0x209dac'}, '0x1d83c4': {'0x1d83cc'}, '0x1d83f8': {'0x1d8a14'}, '0x200678': {'0x200680'}, '0x200694': {'0x200704', '0x2007cc'}, '0x227264': {'0x22726c'}, '0x1e0264': {'0x1e0268'}, '0x200814': {'0x200818'}, '0x200858': {'0x20085c'}, '0x200880': {'0x200884'}, '0x2008b8': {'0x200a50', '0x2008c0'}, '0x200a80': {'0x200ab8'}, '0x2008f0': {'0x200b10'}, '0x200b24': {'0x200b2c'}, '0x20091c': {'0x200b4c'}, '0x200ab4': {'0x200b10', '0x200b4c'}, '0x200ae8': {'0x200af0', '0x200b10'}, '0x200b48': {'0x200b4c'}, '0x200b60': {'0x200b68'}, '0x200b0c': {'0x200b4c'}, '0x1fdad0': {'0x1fdaf4'}, '0x1e02f0': {'0x1e02f4', '0x1eeec4'}, '0x227300': {'0x227dac'}, '0x2007c8': {'0x200b68'}, '0x1dc1c0': {'0x1dd374'}, '0x1d77c4': {'0x1d77c8'}, '0x1d77e0': {'0x1d8a14'}, '0x1fdaf0': {'0x1fdaf4'}, '0x1e03f4': {'0x1e03f8'}, '0x1e048c': {'0x1e0494'}, '0x21a0e8': {'0x21a0f0'}, '0x21a12c': {'0x21a648'}, '0x21a67c': {'0x21a85c', '0x21a680'}, '0x21a880': {'0x21a8ac'}, '0x1e04e4': {'0x1e04e8'}, '0x21a6d0': {'0x21a85c'}, '0x1e0528': {'0x1e052c', '0x1e05cc'}, '0x21a724': {'0x21a85c'}, '0x1e061c': {'0x1eee44'}, '0x21a778': {'0x21a85c'}, '0x21a7c8': {'0x21a85c'}, '0x21a81c': {'0x21a85c', '0x21a820'}, '0x21a854': {'0x21a85c'}, '0x1d783c': {'0x1d8260'}, '0x1d8278': {'0x1d8a14'}, '0x1eeec0': {'0x1eeec4'}, '0x1e057c': {'0x1e0580'}}
```

提取出来的大致会有两种

```plain
def patch_br(datas):
    for br_addr, targets in datas.items():
        if len(targets) == 1:
            target = list(targets)[0]
            encoding, count = ks.asm(f'B {int(target, 16)}', int(br_addr, 16))
            for i in range(4):
                idc.patch_byte(int(br_addr, 16) + i, encoding[i])

        else:
            print(f"{br_addr}-->{targets}")
```

先用这个脚本去执行，目标跳转地址=1的会直接被patch。下面print输出的都是目标地址>1的。这里>1的把它细分成=2的和>2的。

#### =2的情况:

这种更多的是带条件跳转特征的,例如eq,cc,ne等等。

##### 情况①

以0x3069a8这个地址为例,有两个目标地址[0x319740,0x3069ac]

为真时跳转到0x319740，为假时跳转到0x3069ac
![image](https://bbs.kanxue.com/upload/attach/202606/947335_93HZ8A4G9E5X5WK.png)

>
> CINC W20, W6, EQ
>
>
>

这个指令的意思是上面X26与x24作比较,如果相等,w20=w6+1，否则w20=w6。

在0x306984~0x3069A8之间的指令都有用到,所以不能随便patch，像以前的惯性思维都是在基本快的最后两条指令作patch，在这里如果这样做了,会导致F5出来的代码不全。

这里我们可以看到0x3069a8 br地址的下一条地址是0x3069ac，而0x3069ac又在这个br的目标地址里。所以我们只需要patch一处即可,可以直接在br地址出patch成 **b.eq 0x319740 **,然后不满足条件时,它自己就会顺序走到0x3069ac地址处。

##### 情况②

以0x308b4c这个地址为例,有两个目标地址[0x3110c4,0x308904]

为真时跳转到0x3110c4，假时跳转到0x308904![image](https://bbs.kanxue.com/upload/attach/202606/947335_MNW4JBMVR33EM35.png)

这里可以看到br的下一条指令地址是 0x308B50,这个时候就不在br的目标地址里了，前面也是说到了br到cinc指令之前的所有指令操作都有用到,我们不能随意patch，那这里应该怎么做呢?细看0x308B50这个地址的指令,它其实是个垃圾指令,在整个程序里并不会被执行到。所以我们可以在

0x308b4c地址处patch成**b.eq 0x3110c4**,

0x308B50地址处patch成 **b 0x308904。**

如果还有不知道为什么能一眼看出0x308B50这里的地址是垃圾指令,那你可以直接在trace日志里搜索这个地址,看是否被用到,如果没被用到你就放心大胆的patch。

脚本:

```plain
def patch_bytes(src_ea,bytes):
    for i in range(4):
        origin_byte = idc.get_bytes(src_ea+i, 1)
        # print(f"origin_byte:{hex(origin_byte[0])},bytes:{hex(bytes[i])}")
        if origin_byte[0] == bytes[i]:
            continue
        patch_status = idc.patch_byte(src_ea + i, bytes[i])
        if patch_status is False:
            print(f"patch地址失败:{hex(src_ea)}")
            break
def patch_condition_br(condition,br_ea,dst_condition_ea,dst_b_ea):
    # print(f"patch_condition_br_ea ==> {hex(br_ea)}")
    encoding, count = ks.asm(f'B.{condition} {dst_condition_ea}', br_ea)
    patch_bytes(br_ea,encoding)

    # b_ea = idc.next_head(br_ea)
    b_ea = br_ea+4
    if dst_b_ea != b_ea:
        encoding, count = ks.asm(f'B {dst_b_ea}', b_ea)
        patch_bytes(b_ea,encoding)

patch_condition_br("eq",0x3069a8,0x319740,0x3069ac)
patch_condition_br("eq",0x308b4c,0x3110c4,0x308904)
```

#### >2的情况

就去找一块没有被执行到的块,然后在br地址处patch到这个块作为跳板,再patch到每个目标地址即可。

```plain
def patch_ins(src_ea,ins_text):
    encoding, count = ks.asm(f'{ins_text}', src_ea)
    patch_bytes(src_ea,encoding)

patch_ins(0x5b3af8,'b 0x5B3A28')# 跳板处理
patch_ins(0x5B3A28+0*4,'cmp X11,0xcfc')
patch_ins(0x5B3A28+1*4,'b.eq 0x5b3cfc')
patch_ins(0x5B3A28+2*4,'cmp X11, 0xbf8')
patch_ins(0x5B3A28+3*4,'b.eq 0x5b3bf8')
# patch_ins(0x5B3A28+4*4,'cmp X11, 0xafc')
patch_ins(0x5B3A28+4*4,'b 0x5b3afc')
```

完成以上步骤,那么br混淆的去除已经完成了,接下来就是分析代码了。

### 加密数据构成分析

![image](https://bbs.kanxue.com/upload/attach/202606/947335_36D3KJHTC8KA83B.png)
这是登录的时候抓包数据。

整体数据大小有501个字节。
![image](https://bbs.kanxue.com/upload/attach/202606/947335_QPS9YZ395CVJ5EP.png)

>
> 02
>
>
>

固定字节

>
> F5 74 3E 5E 32 A1 91 79 93 76 B1 A0 25 EC F0 3F
>
>
> 14 25 2E 26 3E 8A 08 0F B3 12 96 58 9E E4 E7 3F
>
>
>

共32字节,前16字节是从 libCoreFP.so 里的text段取数据计算出来的。后16字节由请求body和证书交换加密出来的。

>
> 00 00 01 D0 03 00 00 00 42 00 00 01 00
>
>
>

头部魔数,

`00 00 01 D0`:后面有0x1d0个数据大小,固定大小

`03` :固定

`00 00 00 42`:固定

`00 00 01 00`:固定,0x100个数据

>
> AB CD EF AB CD EF AB CD EF AB CD EF AB CD EF AB
>
>
> CD EF AB CD EF AB CD EF AB CD EF AB CD EF AB CD
>
>
> EF AB CD EF AB CD EF AB CD EF AB CD EF AB CD EF
>
>
> AB CD EF AB CD EF AB CD EF AB CD EF AB CD EF AB
>
>
> CD EF AB CD EF AB CD EF AB CD EF AB CD EF AB CD
>
>
> EF AB CD EF AB CD EF AB CD EF AB CD EF AB CD EF
>
>
> AB CD EF AB CD EF AB CD EF AB CD EF AB CD EF AB
>
>
> CD EF AB CD EF AB CD EF AB CD EF AB CD EF AB CD
>
>
> EF AB CD EF AB CD EF AB CD EF AB CD EF AB CD EF
>
>
> AB CD EF AB CD EF AB CD EF AB CD EF AB CD EF AB
>
>
> CD EF AB CD EF AB CD EF AB CD EF AB CD EF AB CD
>
>
> EF AB CD EF AB CD EF AB CD EF AB CD EF AB CD EF
>
>
> AB CD EF AB CD EF AB CD EF AB CD EF AB CD EF AB
>
>
> CD EF AB CD EF AB CD EF AB CD EF AB CD EF AB CD
>
>
> EF AB CD EF AB CD EF AB CD EF AB CD EF AB CD EF
>
>
> AB CD EF AB CD EF AB CD EF AB CD EF AB CD EF AB
>
>
>

这里就是0x100个数据,运算出来的固定数据。

>
> 00 00 00 1A 67 35 BC CF 5D 5C 15 32 C9 A8 4F 0A 58 A5 95 95
>
>
> 0F 51 56 D8 17 A9 A6 BC 8D 22
>
>
>

`00 00 00 1A` 这个大小是前面计算出来的，这里的大小范围是0-32,剩下的数据会在加密数据后面填充0。后面0x1a个数据内容,也是从text段取数据计算出来的，

>
> 00 00 00 9F 01 C9 C9 38 20 2B EF 7B 6A F1 80 19
>
>
> C4 4C 85 6A 46 74 9D 19 14 00 00 00 86 00 01 30
>
>
> FE 41 0B 34 75 E9 2B CB D0 59 F0 27 B2 89 B8 6A
>
>
> 15 51 10 ED 4E 02 4B B6 71 9C FE 48 A3 82 28 54
>
>
> 84 68 52 4D 32 F6 32 C6 23 71 82 6C 50 BD 80 FD
>
>
> 47 06 EB 02 46 C0 F0 24 AF 3F F8 19 4C A3 C3 0B
>
>
> 44 86 BF 62 19 CD D7 FE 6F 50 93 D5 43 8B FD CC
>
>
> 24 88 91 D6 5A AC E2 5A 61 16 1F E4 70 9A D4 28
>
>
> 00 47 B2 CE 99 8B 9A EB D3 AC AE 16 A9 0E 1F 2A
>
>
> E8 A0 E0 10 C2 77 39 5C 88 0D DB EC 3D BE 11 0D
>
>
> A0 20 8F
>
>
>

`00 00 00 9F`固定长度大小,从signSapSetup请求的响应里取最后的0x9f个数据

>
> 00 00 00 00 00 00
>
>
>

填充补0

### 初始化

上面说到从text段里获取的数据,从哪个地方获取,text基址模板都是在初始化就决定好了的。

看看里面做了什么
![image](https://bbs.kanxue.com/upload/attach/202606/947335_R89WUJR8YZ2FQGE.png)

首先会调用arc4random()生成一个4字节随机数,用作MT19973算法的种子初始化,这里MT表里的624个4字节数据就初始化完成了。

还原后代码

```plain
enum {
    N = 624
};

typedef struct {
    uint32_t data[N];
    uint32_t idx;
} MT19937_t;

void mt_init(MT19937_t *mt) {
    for (uint32_t i = 1; i < N; i++) {
        uint32_t x = mt->data[i - 1] ^(mt->data[i - 1] >> 30);
        mt->data[i] = (uint32_t) (0x6c078965u * x + i);
    }
}
```

接着继续调用arc4random()和gettimeofday()方法 生成一个16字节的表

>
> scratch[0]: arc4random
>
>
> scratch[1]: tv.tv_usec 微秒
>
>
> scratch[2]: tv.tv_sec 秒
>
>
> scratch[3]: arc4random
>
>
>

这里面的数据还会经过一轮运算才是最终的

```plain
uint32_t generate_four(uint32_t w0) {
    uint32_t w20 = 0x204bc6d6;
    uint32_t w22 = 0x1025e36b;
    uint32_t w9 = (w0 + w22) - (w20 & (w0 << 1));
    return w9;
}
```

下面就是开始做旋转操作
![image](https://bbs.kanxue.com/upload/attach/202606/947335_CWCPCVSSVGQXSE7.png)

dword_7D1074就是MT表，不断更新里面的数据
![image](https://bbs.kanxue.com/upload/attach/202606/947335_WHXQGH3QZPWXCK3.png)

因为伪代码较长,这是我还原后的代码。

qword_7D1A38:512字节的random表,是由MT表计算得来的,后续这个表里的数据是不会变的。

dword_7D1074:624个4字节表,这个表在做每一步切页操作,例如进入首页,我的等这些步骤,这里面的数据都会被旋转更新。

qword_7D1A70: text段的某个偏移处,最终写入int64的数据，和dword_7D1074、text段大小有关

qword_7D1A78：text段大小

### 从text段获取字节

![image](https://bbs.kanxue.com/upload/attach/202606/947335_R8CFGKMQA4PMW94.png)
v35和v36就是从代码段里获取两个相邻的字节再经过后面的运算得到最终的16字节

>
> F5 74 3E 5E 32 A1 91 79 93 76 B1 A0 25 EC F0 3F
>
>
>

>
> 1A 67 35 BC CF 5D 5C 15 32 C9 A8 4F 0A 58 A5 95
>
>
> 95 0F 51 56 D8 17 A9 A6 BC 8D 22
>
>
>

这段数据也是,只不过原来的前16字节会额外再与另一个16字节的text数据在经过一个白盒加密得到结果`1A 67 35 BC CF 5D 5C 15 32 C9 A8 4F 0A 58 A5 95`

还原后:

```plain
uint8_t *
extract_text_bytes(int len) {
    uint32_t v28;

    uint8_t *out = (uint8_t *) malloc(len);
    uint32_t v1 = (uint32_t) (uintptr_t) out;

    int v3 = 1;

    LABEL_3:
    uint64_t v36 = 0x9908B0DF00000000LL;
    uint32_t v12 = dword_7D1074[0];
    for (int i = 0;; ++i) {
        uint32_t v14 = v12 & 0x80000000;
        v12 = dword_7D1074[i + 1];
        dword_7D1074[i] = *((uint32_t *) &v36 + (v12 & 1)) ^ dword_7D1074[i + 397] ^ ((v12 & 0x7FFFFFFE | v14) >> 1);
        if (i == 226)
            break;
    }

    int dword_7D1400 = dword_7D1074[227];
    int v15 = dword_7D1400;
    int v11 = v3;

    for (int j = 0; j != 396; v11 += (j == 396) | (8 * (j == 396))) {
        uint32_t *v17 = &dword_7D1074[j];
        uint32_t v18 = v15 & 0x80000000;
        v15 = v17[228];
        ++j;
        v17[227] = *((uint32_t *) &v36 + (v15 & 1)) ^ *v17 ^ ((v15 & 0x7FFFFFFE | v18) >> 1);
    }
    int dword_7D16A4 = dword_7D1074[396];

    dword_7D1074[623] = *((uint32_t *) &v36 + (dword_7D1074[0] & 1))
                        ^ dword_7D16A4
                        ^ ((dword_7D1074[0] & 0x7FFFFFFE | dword_7D1074[623] & 0x80000000) >> 1);

    dword_7D1048 = dword_7D1048 % 624 + 1;

    uint32_t v38 = dword_7D1048;

    int64_t v20 = v38;
    uint32_t v23 = dword_7D1074[v20];
    uint32_t v24 = ((v23 ^ (v23 >> 11)) << 7) & 0x9D2C5680 ^v23 ^(v23 >> 11);
    uint32_t v25 = (v24 << 15) & 0xEFC60000 ^v24;
    int v9 = 0;
    uint32_t v27 = v25 ^(v25 >> 18);

    while (1) {
        v28 = v1 + (unsigned int) (len - 1);

        uint8_t v29 = *(uint8_t *) ((qword_7D1A70 ^ 0x706EF8FBC44DB258LL)
                                    + ((unsigned int) (
                *(uint32_t *) (qword_7D1A38 + (dword_7D1070 & 0xD77E0F74))
                + (uint32_t) v28
                - 679604361) & (qword_7D1A78 ^ 0x924170E1LL)));

        uint8_t v30 = *(uint8_t *) ((qword_7D1A70 ^ 0x706EF8FBC44DB258LL)
                                    + ((unsigned int) (
                *(uint32_t *) (qword_7D1A38 + (dword_7D1070 & 0xD77E0F74))
                + (uint32_t) v28
                - 679604359) & (qword_7D1A78 ^ 0x924170E1LL)));

        len--;
        out[len] = (-4 * (uint8_t) v28) ^ (v27 >> v9) ^ v29 ^ v30 ^ 0x8B;

        if (!len) {
            break;
        }
        v9 += 8;
        if (v9 == 32) {
//            printf("取代码段字节输出\n");
            goto LABEL_3;
        }
    }

    return out;
}
```

### 0x100数据的生成

还原后，就是从v4300内存里依次取数据后运算得到

```plain
uint8_t *part_0x1d0_1 = (uint8_t *) malloc(0x100);
unsigned char v4300[3] = {
        0xC5, 0xE7, 0x09
};
for (int i = 921166456;; ++i) {
    part_0x1d0_1[i - 921166456] = *(v4300 + ((i - 921166456) % 3uLL)) - 26;
    if (i == 921166711)
        break;
}
```

### 最复杂的加密运算简述

最复杂的是`14 25 2E 26 3E 8A 08 0F B3 12 96 58 9E E4 E7 3F`数据的生成。

这里大概说下,首先把**0x1d0的数据**和**body明文**拼接进行**sha1**签名,然后把这个结果与前16字节`F5 74 3E 5E 32 A1 91 79 93 76 B1 A0 25 EC F0 3F`进行运算更新,并注入白盒加密运算，此外还有有前面证书交换的操作,会生成一张576字节的表,这个作为初始表,后面会生成n多张表都是基于这张表计算得来的,然后再从这些表里进行查表操作再逐步运算得到最终的16字节加密结果。最后拼接上前面所有的运算即可得到最终的X-Apple-ActionSignature,没整理将就看=-=

证书交换的网络请求可以看文章 [破解iTunes 登陆 PC授权 设备授权 购买安装协议](https://bbs.kanxue.com/thread-203641-1.htm)
![image](https://bbs.kanxue.com/upload/attach/202606/947335_7QMWY72WRGNQ27X.png)

---

纯算实现的话,因为前面证书交换那里还得需要花费更多时间,所以这里就用unidbg实现了。
![image](https://bbs.kanxue.com/upload/attach/202606/947335_X2B4K559PJJQPKV.png)
![image](https://bbs.kanxue.com/upload/attach/202606/947335_BH7CFW42CWPRFGR.png)

这个东西研究下还是能学到很多东西的,和DroidGuard在很多方面都有相似处,短时间的还原还是推荐unidbg的模拟调用,不然纯算可太耗时间了。

---

# 回复

## 回复 by kingking888 (#2)

*2026-6-14 18:04*

666

## 回复 by MaYil (#3)

*2026-6-14 18:12*

感谢分享

## 回复 by wx_插曲 (#4)

*2026-6-14 18:49*

666

## 回复 by dob_C (#5)

*2026-6-15 14:10*

感谢分享

## 回复 by 大魔头 (#6)

*2026-6-15 14:18*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by 小调调 (#7)

*2026-6-15 14:50*

我尝试过直接模拟还原出一个释放算法，跑了20分钟直接把Token烧没了，还没跑完![image](https://bbs.kanxue.com/view/img/face/031.gif)

## 回复 by xingbing (#8)

*2026-6-15 15:00*

感谢分享

## 回复 by swkl (#9)

*2026-6-15 15:25*

感谢分享

## 回复 by 墨穹呢 (#10)

*2026-6-15 18:46*

感谢分享

## 回复 by ppbb (#11)

*2026-6-16 02:05*

必须得点赞啊

## 回复 by ppbb (#12)

*2026-6-16 02:09*

交换的信息中有一些是表，有一些是aes 加密数据。 平坦化部分难度还是大。 点个赞。

## 回复 by 啦啦啦哈哈 (#13)

*2026-6-16 10:26*

感谢分享

## 回复 by mb_cezterwx (#14)

*2026-6-16 11:03*

感谢分享

## 回复 by mb_ouvcyahy (#15)

*2026-6-16 16:01*

????

## 回复 by FMNS (#16)

*2026-6-16 16:22*

66

## 回复 by gluttony (#17)

*2026-6-16 17:16*

![image](https://bbs.kanxue.com/view/img/face/015.gif)

## 回复 by mb_ysikfhxt (#18)

*2026-6-17 09:03*

111

## 回复 by mb_depeeceu (#19)

*2026-6-17 11:20*

nb 666

## 回复 by 熊猫吃鱼 (#20)

*2026-6-17 13:53*

666666

## 回复 by 机车王子 (#21)

*2026-6-17 15:37*

谢谢你的细致分析，受益匪浅！

## 回复 by 4Chan (#22)

*2026-6-17 19:43*

学习一下思路

## 回复 by mb_euhyowpw (#23)

*2026-6-18 11:29*

666

## 回复 by mb_qimctavn (#24)

*2026-6-18 17:08*

6

## 回复 by mb_kbagkani (#25)

*2026-6-18 17:15*

大佬牛哇

## 回复 by xifgg (#26)

*2026-6-18 17:31*

666

## 回复 by mb_uzmffdbw (#27)

*2026-6-18 17:48*

666

## 回复 by jw8888 (#28)

*2026-6-19 07:38*

66666666666666

## 回复 by mb_ttrbbnkv (#29)

*2026-6-19 10:04*

6

## 回复 by hiergou (#30)

*2026-6-20 16:58*

学习 一下 不知道有没有最新的算法

## 回复 by hiergou (#31)

*2026-6-20 22:33*

有没有老哥有算法成品啊

## 回复 by mb_paeqogwt (#32)

*2026-6-22 16:00*

看看

## 回复 by dsr000 (#33)

*2026-6-24 14:15*

666

## 回复 by mb_wcxanmeu (#34)

*2026-6-26 19:49*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by caolinkai (#35)

*2026-6-28 03:05*

看看

## 回复 by didiid (#36)

*2026-6-29 17:22*

666

## 回复 by mb_osxdmntv (#37)

*2026-7-2 18:35*

666

## 回复 by mb_bsaiedcd (#38)

*2026-7-2 18:42*

666

## 回复 by git_86745anasmahmoudmonssif1 (#39)

*2026-7-3 06:36*

asd

## 回复 by syagen (#40)

*2026-7-5 06:16*

666

## 回复 by iBa0 (#41)

*2026-7-6 20:29*

123

## 回复 by wx_kx92911 (#42)

*2026-7-9 09:53*

感谢分析

## 回复 by hanjiefang (#43)

*2026-7-10 18:18*

666

## 回复 by kbsync (#44)

*2026-7-16 13:02*

1

## 回复 by mb_yvuzbfvo (#45)

*2026-7-17 22:46*

看看

## 回复 by 小叶叶_let (#46)

*2026-7-19 04:06*

牛

## 回复 by mb_hnwotbvj (#47)

*2026-7-19 21:56*

学习一下

## 回复 by totaldark (#48)

*2026-7-20 00:29*

Nice, thanks for sharing!

## 回复 by zhujieqaq (#49)

*2026-7-21 01:18*

大佬666

## 回复 by git_20668ternary88 (#50)

*2026-7-21 10:40*

11

## 回复 by tt8369 (#51)

*2026-7-21 11:22*

6666666

## 回复 by ugui (#52)

*2026-7-21 19:48*

![image](https://bbs.kanxue.com/view/img/face/050.gif)

## 回复 by mb_nbwjjtth (#53)

*2026-7-22 15:01*

6

## 回复 by Rain fog (#54)

*2026-7-24 10:29*

66666

## 回复 by wf021325 (#55)

*2026-7-24 12:57*

666,之前研究过windows的itunes这个参数，现在竟然研究安卓的了

## 回复 by wx_阿伦_109 (#56)

牛大佬厉害 不像我混吃等死

## 回复 by GeQ1an (#57)

666

## 回复 by mb_aplfzyec (#58)

厉害，学习一下！
