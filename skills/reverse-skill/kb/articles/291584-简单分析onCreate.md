---
title: '[原创]简单分析onCreate'
url: https://bbs.kanxue.com/thread-291584.htm
tid: 291584
author: lingyi223
date: '2026-06-13'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T15:02:53+08:00'
replies: 18
---

dex vmp简单分析onCreate

前言

本人小白一枚，学习其他大佬的教程，发现还是太吃力了，觉得vmp是无法逾越的宏沟，然后也尝试看过一些大佬的文章，有的没样本，有的反调过不了没法复现，于是有了这篇文章，不过样本有点老了，不过学个基本流程感觉还行，刷到这篇[教程]([[原创/]某企业加固dex vmp简单分析-Android安全-看雪安全社区｜专业技术交流与安全研究论坛](https://bbs.kanxue.com/thread-291492.htm)),马上大4了，找工作感觉迷茫，。

贴个带时间的图证明一下不是抄的

![image-20260612195144947](https://bbs.kanxue.com/upload/attach/202606/1043807_CVXD5VXZMF4RD87.png)

##### onCreate入口

脱完壳看一下onCreate发现被A.V代理了，其实说白了就是一个vmp入口，0xab000000应该对应的就是vmp需要解释执行的函数，简单介绍vmp，其实就是一个解释器而已，解释自定义的字节码，和你正常写的程序差不多，然后虚拟化寄存器和堆栈(简单理解就是申请一块内存然后放对应寄存器的值而已，这个样本应该没有虚拟栈(毕竟都是通过jni解释执行的)，原理感觉很简单，但是还是感觉有点难

```java
public class MainActivity extends AppCompatActivity {
    public static final String logTag = "xposed_log";

    public static native String[] parseClassNames(byte[] bArr);

    public native String stringFromJNI();

    static {
        System.loadLibrary("native-lib");
    }

    protected void onCreate(Bundle bundle) {
        A.V((int) 0xab000000, this, new Object[]{bundle});
    }
}
```

然后看看V函数是个啥,那么多跳板函数，感觉是根据返回值定义的，这就不说了，现在主要找一下V函数绑定在哪里的

```java
public class A {
    public static final String BAIDUPROTECT_TAG = "baiduprotect5.0.1";

    public static native byte B(int i, Object obj, Object... objArr);

    public static native char C(int i, Object obj, Object... objArr);

    public static native double D(int i, Object obj, Object... objArr);

    public static native float F(int i, Object obj, Object... objArr);

    public static native int I(int i, Object obj, Object... objArr);

    public static native long J(int i, Object obj, Object... objArr);

    public static native Object L(int i, Object obj, Object... objArr);

    public static native short S(int i, Object obj, Object... objArr);

    public static native void V(int i, Object obj, Object... objArr);

    public static native boolean Z(int i, Object obj, Object... objArr);

    public static native void n001(String str, String str2, String str3, String str4, int i, boolean z);

    public static native void n002(Context context);

    public static native void n003();
}
```

跑一下脚本,脚本附件应该会提供

```python
name: V, signature: (ILjava/lang/Object;[Ljava/lang/Object;)V, fnPtr: 0x7958f5d598, modulename: libbaiduprotect.so -> base: 0x7958f1b000, offset: 0x42598
```

然后就看到这个函数大概的样子,很明显 ((dword_C0118 * (dword_C0118 - 1)) & 1) != 0 && dword_C0120 >= 10这个表达式是一个不透明谓词，可以装hrtng去除。后面那个是装了的样子

```
__int64 __fastcall sub_42598(__int64 a1, __int64 a2, int a3)
{
  __int64 result; // x0

  while ( ((dword_C0118 * (dword_C0118 - 1)) & 1) != 0 && dword_C0120 >= 10 )
    ;
  while ( 1 )
  {
    result = sub_4A458(qword_BED18[(a3 & 0xFF0000u) >> 16], 0, 0, 0, 0);
    if ( ((dword_C0118 * (dword_C0118 - 1)) & 1) == 0 || dword_C0120 < 10 )
      break;
    sub_4A458(qword_BED18[(a3 & 0xFF0000u) >> 16], 0, 0, 0, 0);
  }
  while ( ((dword_C0118 * (dword_C0118 - 1)) & 1) != 0 && dword_C0120 >= 10 )
    ;
  return result;
}
```

装了的样子，这个函数应该是ida反编译的错误导致的，因为正常应该是5个参数，前两个固定，后3个是传入的，不懂建议问ai，第一个参数是根据传入的索引0xab000000在对应的地址取出来的，就叫vmState(后面分析出来的，存储对应onCreate方法的一些信息)，至于后面那几个后面看trace日志确定的

```
__int64 __fastcall sub_42598(__int64 a1, __int64 a2, int a3)
{
  return sub_4A458(qword_BED18[(a3 & 0xFF0000u) >> 16], 0, 0, 0, 0);// vmState,0,env,this,args
}
```

然后进入函数看看看见这个函数*(a1 + 56)，前面说了a1是一个vmState的结构体，但是结构体有什么东西我们并不知道，我猜的是一个方法表method_table[a2]这样取一个对应方法的基本信息，这个是后面分析出来的，简单看一下

```python
v10 = sub_5CB98(*a1, a2);

__int64 __fastcall sub_5CB98(__int64 a1, int a2)
{
  return *(*(a1 + 56) + 8LL * a2);
}
```

然后看到这个函数，被加密了，可以自己跑一遍模拟执行啥的，或者frida自己hook一下就能发现是一个malloc，不是重点就不讲了,

这里用到了v10就是上面取的method结构体，8LL * *(v10 + 18)申请了这么大的空间，可以得出v12可能就是我们需要找的虚拟寄存器，照着源码，看基本能实锤，并且*(v10 + 18)是7，而这个方法正好使用了那么多的寄存器

```
  v12 = off_BE260(8LL * *(v10 + 18));

  name_5 = sub_261D4("2D5E4DE7FD827D7E");
  off_BE260 = dlsym(handle, name_5);
```

![image-20260612205053937](https://bbs.kanxue.com/upload/attach/202606/1043807_VZMJ32SN4HSVVKJ.png)

寄存器的初始化,一样的不说了，__memset_aarch64寄存器清0

```
   off_BE270(v12, 0, 8LL * *(v10 + 18));
```

然后发现这个函数，看见switch 以为是个vmp解释器，半天找不到虚拟字节码啥的，也不知道用来做啥的，就没管了，不过好像art虚拟机也有一个类似的前置操作，感兴趣可以自己去找一下，这就不说了

```python
sub_45EBC(vmState, method, a3, obj_this, args, vmRegisters, v11);
```

```
__int64 __fastcall sub_45EBC(_QWORD *a1, __int64 a2, __int64 a3, __int64 a4, __int64 a5, __int64 a6, __int64 a7)
{
  int v7; // w0
  _QWORD *v8; // x15
  _QWORD *v9; // x19
  _BYTE *v10; // x11
  __int64 v12; // [xsp-A0h] [xbp-130h]
  unsigned int v13; // [xsp-90h] [xbp-120h]
  int v14; // [xsp-80h] [xbp-110h]
  _BYTE *v15; // [xsp-70h] [xbp-100h]
  __int64 v16; // [xsp-60h] [xbp-F0h]
  _QWORD v19[2]; // [xsp-30h] [xbp-C0h] BYREF
  __int64 v20; // [xsp-20h] [xbp-B0h]
  _QWORD *v21; // [xsp-10h] [xbp-A0h]
  _QWORD *v22; // [xsp+0h] [xbp-90h]
  _QWORD *v23; // [xsp+8h] [xbp-88h]
  __int64 v24; // [xsp+10h] [xbp-80h]
  __int64 v25; // [xsp+18h] [xbp-78h]
  __int64 v26; // [xsp+20h] [xbp-70h]
  __int64 v27; // [xsp+28h] [xbp-68h]
  __int64 v28; // [xsp+30h] [xbp-60h]
  __int64 v29; // [xsp+38h] [xbp-58h]

  v24 = a2;
  v25 = a3;
  v26 = a4;
  v29 = a5;
  v27 = a6;
  v28 = a7;
  v23 = v19;
  v22 = v19;
  v21 = a1;
  v20 = a2;
  v19[0] = a5;
  v16 = sub_4590C(*a1, *(a2 + 20));
  v14 = *(v20 + 14);
  v7 = sub_4A3E4(*(v20 + 8));
  v8 = v23;
  if ( !v7 )
  {
    *(a6 + 8LL * (v14 - 1)) = *v22;
    *(a7 + v14 - 1) = 76;
  }
  v9 = v8;
  v15 = v16;
  v13 = 0;
  while ( *v15 )
  {
    v12 = sub_4A3EC(*v9, v19[0], v13);
    v10 = v15++;
    if ( *v10 > 0x59u )
    {
      if ( *v10 == 90 )
      {
        *(a6 + 8LL * v14) = sub_4A44C(*v9, v12, qword_BF580, qword_BF620, 0);
        *(a7 + v14) = 73;
      }
    }
    else
    {
      switch ( *v10 )
      {
        case 'B':
          *(a6 + 8LL * v14) = sub_4A440(*v9, v12, qword_BF588, qword_BF628, 0);
          *(a7 + v14) = 73;
          break;
        case 'C':
          *(a6 + 8LL * v14) = sub_4A434(*v9, v12, qword_BF590, qword_BF630, 0);
          *(a7 + v14) = 73;
          break;
        case 'D':
          *(a6 + 8LL * v14) = sub_4A3F8(*v9, v12, qword_BF5B8, qword_BF658, 0);
          *(a7 + v14++) = 73;
          break;
        case 'F':
          *(a6 + 8LL * v14) = sub_4A410(*v9, v12, qword_BF5B0, qword_BF650, 0);
          *(a7 + v14) = 73;
          break;
        case 'I':
          *(a6 + 8LL * v14) = sub_4A41C(*v9, v12, qword_BF5A0, qword_BF640, 0);
          *(a7 + v14) = 73;
          break;
        case 'J':
          *(a6 + 8LL * v14) = sub_4A404(*v9, v12, qword_BF5A8, qword_BF648, 0);
          *(a7 + v14++) = 73;
          break;
        case 'L':
          *(a6 + 8LL * v14) = v12;
          *(a7 + v14) = 76;
          break;
        case 'S':
          *(a6 + 8LL * v14) = sub_4A428(*v9, v12, qword_BF598, qword_BF638, 0);
          *(a7 + v14) = 73;
          break;
        default:
          break;
      }
    }
    ++v14;
    ++v13;
  }
  return 1;
}
```

这个才是真正的入口

```python
*v9 = sub_4CC20(a1, a3, v10, v12, v11);
下面这个是分析后命名的，不一定对，主要关注一下vmRegisters的使用就行了，method是错的，这就不改了，后面改
sub_45EBC(vmState, method, a3, obj_this, args, vmRegisters的使用就行了, v11);
```

进入函数看看

```
void __fastcall sub_4CC20(__int64 a1, __int64 a2, __int64 a3)
{
  __int64 v5; // x16
  __int64 v6; // x26
  char v7; // w0
  __int128 v8; // [xsp+128h] [xbp-F8h] BYREF
  __int64 v9; // [xsp+138h] [xbp-E8h]
  __int64 v10; // [xsp+140h] [xbp-E0h]
  int n1065353216; // [xsp+148h] [xbp-D8h]
  __int128 v12; // [xsp+150h] [xbp-D0h] BYREF
  __int64 v13; // [xsp+160h] [xbp-C0h]
  __int64 v14; // [xsp+168h] [xbp-B8h]
  __int128 v15; // [xsp+170h] [xbp-B0h]
  __int64 v16; // [xsp+180h] [xbp-A0h]
  __int128 v17; // [xsp+188h] [xbp-98h]
  __int64 v18; // [xsp+198h] [xbp-88h]
  __int64 v19; // [xsp+1A8h] [xbp-78h]
  __int64 v20; // [xsp+1B0h] [xbp-70h]
  __int64 v21; // [xsp+1B8h] [xbp-68h]
  __int64 v22; // [xsp+1C0h] [xbp-60h]
  __int64 v23; // [xsp+1C8h] [xbp-58h] BYREF

  v21 = 0;
  v22 = 0;
  v19 = 0;
  v20 = 0;
  v12 = 0u;
  v13 = 0;
  v14 = 0;
  v15 = 0u;
  v16 = 0;
  v17 = 0u;
  v18 = 0;
  sub_5556C(&v12, 0);
  v8 = 0u;
  v9 = 0;
  v10 = 0;
  n1065353216 = 1065353216;
  sub_45A84(&v8, 8);
  v23 = 0;
  sub_45BC8(&v8, 8, &v23);
  v5 = a1;
  v6 = *(a3 + 24);
  if ( !*(a1 + 2056) )
  {
    v7 = sub_5AE5C(*a1, off_BD040, a1 + 8);
    v5 = a1;
    *(a1 + 2056) = v7 & 1;
  }
  __asm { BR              X8 }
}
```

off_BD040,发现了很多函数，基本有256个吧，好像官方opcode也是那么多，不过不重要

```python
.data:00000000000BD040 off_BD040       DCQ sub_4CD58           ; DATA XREF: sub_4CC20+C4↑o
.data:00000000000BD048                 DCQ sub_4CD8C
.data:00000000000BD050                 DCQ sub_4CDE0
.data:00000000000BD058                 DCQ sub_4CE34
.data:00000000000BD060                 DCQ sub_4CE84
.data:00000000000BD068                 DCQ sub_4CED4
.data:00000000000BD070                 DCQ sub_4CF24
.data:00000000000BD078                 DCQ sub_4CF70
.data:00000000000BD080                 DCQ sub_4CFC0
.data:00000000000BD088                 DCQ sub_4D010
.data:00000000000BD090                 DCQ sub_4D05C
.data:00000000000BD098                 DCQ sub_4D0C0
.data:00000000000BD0A0                 DCQ sub_4D12C
.data:00000000000BD0A8                 DCQ sub_4D198
.data:00000000000BD0B0                 DCQ loc_546DC
```

接下来看 __asm { BR X8 }是这么实现跳转的和x2有关，x2是前面取的method，上面好像命名错了，不管了，最开始猜测了一下x8哪里应该是一个switch跳转，所以尝试用ida自带的识别了一下，不过用处不大，他跳转的地方也有br跳转,不过还是贴一下，所以根据这个跳转可以合理推测x26就是我们的虚拟字节码，可以自己写个frida dump下来看看

```python
vm_run(__int64 vmstate, JNIEnv *a2, VmMethod *a3, registerS *a4, __int64 a5)
.text:000000000004CC48                 MOV             X20, X2
.text:000000000004CCD0                 LDR             X26, [X20,#0x18]
.text:000000000004CD00                 LDRH            W22, [X26]
.text:000000000004CD04                 ADD             X8, X16, W22,UXTB#3
.text:000000000004CD08                 ADD             X8, X8, #8
.text:000000000004CD0C                 LDR             X8, [X8]
.text:000000000004CD54                 BR              X8      ; switch jump
```

![image-20260612211521756](https://bbs.kanxue.com/upload/attach/202606/1043807_NHBSE9RADTY8VCH.png)

然后基本就水到这里了，上trace文件看看，trace工具是乐子人大佬的 ，第一条虚拟指令w26应该算是pc指针了，然后根据取出的指令码又进行了一次跳转，

###### 0xf9

```python
[libbaiduprotect.so] 0x7277e85d00!0x4cd00 ldrh w22, [x26]; w22=0x4081c620 x26=0x753510a161 mem_r=0x753510a161 -> w22=0xf9
[libbaiduprotect.so] 0x7277e85d04!0x4cd04 add x8, x16, w22, uxtb #3; x8=0x1 x16=0x744081c620 w22=0xf9 -> x8=0x744081cde8
[libbaiduprotect.so] 0x7277e85d08!0x4cd08 add x8, x8, #8; x8=0x744081cde8 x8=0x744081cde8 -> x8=0x744081cdf0
[libbaiduprotect.so] 0x7277e85d0c!0x4cd0c ldr x8, [x8]; x8=0x744081cdf0 x8=0x744081cdf0 mem_r=0x744081cdf0 -> x8=0x7277e864cc
[libbaiduprotect.so] 0x7277e85d10!0x4cd10 mov w9, wzr; w9=0x1 -> w9=0x0
[libbaiduprotect.so] 0x7277e85d14!0x4cd14 stp xzr, x9, [sp, #0x48]; x9=0x0 sp=0x7ff37e70d0 mem_w=0x7ff37e7118
[libbaiduprotect.so] 0x7277e85d18!0x4cd18 str xzr, [sp, #0x10]; sp=0x7ff37e70d0 mem_w=0x7ff37e70e0
[libbaiduprotect.so] 0x7277e85d1c!0x4cd1c mov w17, wzr; w17=0x0 -> w17=0x0
[libbaiduprotect.so] 0x7277e85d20!0x4cd20 mov w25, wzr; w25=0xf37e7310 -> w25=0x0
[libbaiduprotect.so] 0x7277e85d24!0x4cd24 mov w24, wzr; w24=0xf37e71f8 -> w24=0x0
[libbaiduprotect.so] 0x7277e85d28!0x4cd28 mov w28, wzr; w28=0xf37e75bc -> w28=0x0
[libbaiduprotect.so] 0x7277e85d2c!0x4cd2c mov w20, wzr; w20=0x60840d50 -> w20=0x0
[libbaiduprotect.so] 0x7277e85d30!0x4cd30 mov w23, wzr; w23=0x4081c620 -> w23=0x0
[libbaiduprotect.so] 0x7277e85d34!0x4cd34 mov w27, wzr; w27=0x4081c620 -> w27=0x0
[libbaiduprotect.so] 0x7277e85d38!0x4cd38 mov w19, wzr; w19=0x4081c620 -> w19=0x0
[libbaiduprotect.so] 0x7277e85d3c!0x4cd3c str x9, [sp, #0x30]; x9=0x0 sp=0x7ff37e70d0 mem_w=0x7ff37e7100
[libbaiduprotect.so] 0x7277e85d40!0x4cd40 str x9, [sp, #0x40]; x9=0x0 sp=0x7ff37e70d0 mem_w=0x7ff37e7110
[libbaiduprotect.so] 0x7277e85d44!0x4cd44 str x9, [sp, #0x38]; x9=0x0 sp=0x7ff37e70d0 mem_w=0x7ff37e7108
[libbaiduprotect.so] 0x7277e85d48!0x4cd48 str x9, [sp, #0x28]; x9=0x0 sp=0x7ff37e70d0 mem_w=0x7ff37e70f8
[libbaiduprotect.so] 0x7277e85d4c!0x4cd4c ldr x14, [sp, #0x68]; x14=0x1 sp=0x7ff37e70d0 mem_r=0x7ff37e7138 -> x14=0x72e0898080
[libbaiduprotect.so] 0x7277e85d50!0x4cd50 ldr x15, [sp, #0x58]; x15=0x1 sp=0x7ff37e70d0 mem_r=0x7ff37e7128 -> x15=0x72d083ddd0
[libbaiduprotect.so] 0x7277e85d54!0x4cd54 br x8; x8=0x7277e864cc
```

可以在自己文本工具吧这个地址用颜色标出来，后面可以直接看

![image-20260612212430951](https://bbs.kanxue.com/upload/attach/202606/1043807_USGXZR4C5YCRDKX.png)

然后又取了2字节，并且取了高8位

![image-20260612213238667](https://bbs.kanxue.com/upload/attach/202606/1043807_7FNYTXV94XJZUXE.png)

然后写了个x0到对应的地址，w19是索引，是不是可以合理推测一下，x14就是虚拟寄存器的基地址，所以标出来，然后x0是什么？

发现是是NewGlobalRef的返回结果

![image-20260612213901117](https://bbs.kanxue.com/upload/attach/202606/1043807_NHZ4S89JDKWGTNK.png)

![image-20260612220525497](https://bbs.kanxue.com/upload/attach/202606/1043807_WHG7YYYWGVPW7GB.png)

0x5d580这个地址跳过去看看,a2这个偏移大概率是env了

```
  v13 = (*(v11 + 88) + *(*(v11 + 16) + 4LL * a3));
  do
    v14 = *v13++;
  while ( v14 < 0 );
  v15 = (*(*a2 + 1336LL))(a2, v13);
  v16 = sub_12058(a2, v15, qword_BF618);
  (*(*a2 + 184LL))(a2, v15);
  v10 = (*(*a2 + 168LL))(a2, v16);
  (*(*a2 + 184LL))(a2, v16);
  *sub_5D5D0(v12, &v18) = v10;

    v13 = (*(v11 + 88) + *(*(v11 + 16) + 4LL * a3));
  do
    v14 = *v13++;
  while ( v14 < 0 );
  v15 = (*a2)->NewStringUTF(a2, v13);
  v16 = sub_12058(a2, v15, qword_BF618);
  (*a2)->DeleteLocalRef(a2, v15);
  v10 = (*a2)->NewGlobalRef(a2, v16);
  (*a2)->DeleteLocalRef(a2, v16);
  *sub_5D5D0(v12, &v18) = v10;
```

然后日志有这个，v13这么来的，合理猜测一下来自于字符串常量池里面的

```python
call jni func: NewStringUTF(0xb40000728080f370, 0x753510035f)
args1: xposed_log
```

这里好像也能对上，0x97a前面取的指令，不知道这个猜测对不对，开始我直接拿着索引去dex文件里面找了，并且也印证了猜测

```python
[libbaiduprotect.so] 0x7277e96514!0x5d514 ldr w8, [x10, x8, lsl #2]; w8=0x97a x10=0x75350e8070 x8=0x97a mem_r=0x75350ea658 -> w8=0x1835e
[libbaiduprotect.so] 0x7277e96518!0x5d518 add x21, x21, #0x900; x21=0x744081c620 x21=0x744081c620 -> x21=0x744081cf20
[libbaiduprotect.so] 0x7277e9651c!0x5d51c add x1, x9, x8; x1=0xb40000728080f370 x9=0x75350e8000 x8=0x1835e -> x1=0x753510035e
```

![image-20260612221635745](https://bbs.kanxue.com/upload/attach/202606/1043807_7KNCE63SDUAHSST.png)

然后这个我也不知道这么印证，我猜测可能是一个tostring方法，有方法的话求告知

```python
  v16 = CallObjectMethodV(a2, v15, methodIds);
```

然后整理一下

```python
0x4cd00 ldrh w22, [x26]; w22=0x4081c620 x26=0x753510a161 mem_r=0x753510a161 -> w22=0xf9
0x4d4cc ldrh w2, [x26, #2]; w2=0x4081c628 x26=0x753510a161 mem_r=0x753510a163 -> w2=0x97a
然后创建了一个全局的java对象(字符串)，写入了0寄存器，就是v0
0x4d508 str x0, [x14, w19, uxtw #3]; x0=0x32a2 x14=0x72e0898080 w19=0x0 mem_w=0x72e0898080
```

这是没加壳的

```python
00117c40: 1a00 d243               0000: const-string        v0, "xposed_log" # string@43d2
```

###### 0x6e

```python
0x4d514 ldrh w22, [x26, #4]!; w22=0xd083ddd0 x26=0x753510a161 mem_r=0x753510a165 -> w22=0x206e
0x537d0 ldrh w19, [x26, #4]; w19=0x0 x26=0x753510a165 mem_r=0x753510a169 -> w19=0x65
0x537e0 ldr x21, [x14, x8, lsl #3]; x21=0xb40000728080f370 x14=0x72e0898080 x8=0x5 mem_r=0x72e08980a8 -> x21=0x7ff37e75bc
```

这里0x65应该是寄存器索引，跟一下自己就能出来，这里取了一个5的索引，因为trace要闪退我就单独对入口trace了一份，x3就是这个寄存器的值 A.V((int) 0xab000000, this, new Object[]{r5}); 这个的this，然后有个知识点就是，这个onCreate总共使用了，7个寄存器，有一个参数，所以0-6,6就是参数寄存器，5就是this指针p0,0-4就是通用寄存器(如果有误请纠正)

```python
0x7277e7f5b4!0x425b4 mov x20, x3; x20=0x0 x3=0x7ff37e75bc -> x20=0x7ff37e75bc
```

然后有取了2字节

```python
0x7277e8c7e8!0x537e8 ldrh w2, [x26, #2]; w2=0xf37e7040 x26=0x753510a165 mem_r=0x753510a167 -> w2=0x7
```

主要跟一下对字节码和虚拟寄存器和jni就行了，所以后面一大坨就不看了然后找到这里有个字符串，看着有点像方法签名

```python
call func: __strlen_aarch64(0x75350f5895)
args0: Landroid/os/Bundle;
ret: 0x13

call func: __strlen_aarch64(0x75350f8ae9)
args0: V
ret: 0x1

call func: __strlen_aarch64(0x75350f5895)
args0: Landroid/os/Bundle;
ret: 0x13

call func: strdup(0x7ff37e6f60)
args0: (Landroid/os/Bundle;)V
ret: 0x742084c680

call jni func: GetMethodID(0xb40000728080f370, 0x32c6, 0x75350fef2f, 0x742084c680)
args2: onCreate
args3: (Landroid/os/Bundle;)V
ret: 0x4a063838

[libbaiduprotect.so] 0x7277e8caec!0x53aec ldr x8, [x2, x8, lsl #3]; x8=0x6 x2=0x72e0898080 x8=0x6 mem_r=0x72e08980b0 -> x8=0x0

[libbaiduprotect.so] 0x7277e8caf8!0x53af8 ldr x8, [x2, x8, lsl #3]; x8=0x5 x2=0x72e0898080 x8=0x5 mem_r=0x72e08980a8 -> x8=0x7ff37e75bc

call jni func: CallNonvirtualVoidMethodA()
ret: 0x0
```

CallNonvirtualVoidMethodA 调用父类的一个方法，然后没有返回值，所以就不会操作虚拟寄存器，所以这个方法是什么好难猜啊，上面有些东西懒得找了又臭又长，上面一些操作应该是拼接这个方法签名，然后进行调用，然后5，6两个参数寄存器，5是this指针会隐式传入，前面指令流取的0x7是啥，方法索引呗

```python
args2: onCreate
args3: (Landroid/os/Bundle;)V
```

![image-20260612230455773](https://bbs.kanxue.com/upload/attach/202606/1043807_PF6W4PDN89WBZMY.png)

整理一下

```python
0x206e 6e 操作码 ，0x20 应该是两个参数
0x65   5，6寄存器
0x7    方法索引
00117c44: 6f20 e80d 6500          0002: invoke-super        {p0, v6}, Landroidx/appcompat/app/AppCompatActivity;->onCreate(Landroid/os/Bundle;)V # method@0de8
```

###### 0xc8

这个就是给v6寄存器赋值

![image-20260612231337352](https://bbs.kanxue.com/upload/attach/202606/1043807_6TJTTTGB29N8FSF.png)

```python
0x6c8 c8操作码 06目标寄存器
00117c4a: 1406 1c00 0a7f          0005: const               v6, 0x7f0a001c
```

###### 0x98

```python
0x4d2f4 ldrh w22, [x26, #6]!; w22=0x6c8 x26=0x753510a16b mem_r=0x753510a171 -> w22=0x2098 x26=0x753510a171
0x53780 ldrh w19, [x26, #4]; w19=0x0 x26=0x753510a171 mem_r=0x753510a175 -> w19=0x65
ldrh w2, [x26, #2]; w2=0xd084b310 x26=0x753510a171 mem_r=0x753510a173 -> w2=0x25
```

结构太像了 不太想看了

```python
call jni func: GetMethodID(0xb40000728080f370, 0x32e6, 0x75350ff694, 0x72d084b310)
args2: setContentView
args3: (I)V
ret: 0x4a063af8

call jni func: CallVoidMethodA()
jmethod: setContentView
ret: 0x0
```

CallVoidMethodA 方法调用也没有返回值

![image-20260613120613279](https://bbs.kanxue.com/upload/attach/202606/1043807_4FZ9CN2C4R4CN7K.png)

整理一下

```python
0x2098 0x98操作码 0x20 两个寄存器
0x65    5，6寄存器
0x25    方法索引
00117c50: 6e20 683b 6500          0008: invoke-virtual      {p0, v6}, Lcom/example/test/MainActivity;->setContentView(I)V # method@3b68
```

###### 0x73

```python
0x54680 ldrh w22, [x26, #6]!; w22=0xd083ddd0 x26=0x753510a17d mem_r=0x753510a183 -> w22=0x673 x26=0x753510a183

0x4d160 str x11, [x14, w8, uxtw #3]; x11=0x7547067021 x14=0x72e0898080 w8=0x6 mem_w=0x72e08980b0

这是上一个函数的调用结果，6e指令，一样就跳过了
call jni func: CallObjectMethodA()
jmethod: findViewById
ret: 0x7547067021
```

这两条指令是成对出现的，函数调用有返回值就会用move-result-object v6进行接收

```python
00117c5c: 6e20 643b 6500          000e: invoke-virtual      {p0, v6}, Lcom/example/test/MainActivity;->findViewById(I)Landroid/view/View; # method@3b64
    00117c62: 0c06                    0011: move-result-object  v6
```

整理一下

```python
0x673  0x73操作码   0x6目标寄存器
00117c62: 0c06                    0011: move-result-object  v6
```

###### 0x70

```python
0x4d168 ldrh w22, [x26, #2]!; w22=0x673 x26=0x753510a183 mem_r=0x753510a185 -> w22=0x670 x26=0x753510a185
0x4d72c ldr x25, [x14, w8, uxtw #3]; x25=0x0 x14=0x72e0898080 w8=0x6 mem_r=0x72e08980b0 -> x25=0x7547067021
0x4d734 ldrh w2, [x26, #2]; w2=0xf37e7090 x26=0x753510a185 mem_r=0x753510a187 -> w2=0xe
```

类名拼接

```python
call func: __strlen_aarch64(0x75350f58d3)
args0: Landroid/widget/TextView;
```

类型转换

```python
call jni func: IsInstanceOf()
ret: 0x1
```

![image-20260613161244813](https://bbs.kanxue.com/upload/attach/202606/1043807_7EN5PTQ4QJ8CPHK.png)

整理一下

```python
0x670 0x70操作码 0x6目标寄存器
0x0e  类型索引
00117c64: 1f06 0002               0012: check-cast          v6, Landroid/widget/TextView; # type@0200
```

###### 0x3a

这条简单 就是加载2字节到对应寄存器，这也可以很清晰的看到中间一坨寄存器清0操作，明显的字节码分割线

![image-20260613163426290](https://bbs.kanxue.com/upload/attach/202606/1043807_58F7B255729W3GH.png)

```python
0x3ca  0xca操作码 0x3索引寄存器
x9=0x40 加载数
1303 4000               0021: const/16            v3, 0x40
```

###### 0x4e

```python
0x4d168 ldrh w22, [x26, #2]!; w22=0x673 x26=0x753510a1ad mem_r=0x753510a1af -> w22=0x664e x26=0x753510a1af
0x4f638 ldr x25, [x14, w8, uxtw #3]; x25=0x0 x14=0x72e0898080 w8=0x6 mem_r=0x72e08980b0 -> x25=0x754706702d
ldrh w2, [x26, #2]; w2=0xf37e7090 x26=0x753510a1af mem_r=0x753510a1b1 -> w2=0x0

call func: __strlen_aarch64(0x75350f57e9)
args0: Landroid/content/pm/PackageInfo;
ret: 0x20

call jni func: GetFieldID()
ret: 0x70a2dc50

call jni func: GetObjectField()
ret: 0x7547067031

0x4f764 str x25, [x14, x19, lsl #3]; x25=0x7547067031 x14=0x72e0898080 x19=0x6 mem_w=0x72e08980b0
```

写个frida 可以看看拿的是什么字段

```python
    var module = Process.getModuleByName("libbaiduprotect.so").base
    Interceptor.attach(module.add(0x5CEEC), {
        onEnter: function (args) {
            console.log(Java.cast(args[1], Java.use("java.lang.Object")))
            console.log(args[3].readCString())
        },
        onLeave: function (retval) {

        }
    })
class android.content.pm.PackageInfo
[Landroid/content/pm/Signature;
```

整理一下

```python
0x664e  0x4e操作码 0x6 0x6 这两个是寄存器索引读取那个，写入那个懒得看了
0x0     猜一下吧类型索引，上面frida也能佐证
```

![image-20260613170750705](https://bbs.kanxue.com/upload/attach/202606/1043807_DM5XGK4NTZ2EN9G.png)

###### 0xbc

很明显了，就是获取一个对象的长度，而对象就是上一步的v6对象

```python
0x4f770 ldrh w22, [x26, #4]!; w22=0xd083ddd0 x26=0x753510a1af mem_r=0x753510a1b3 -> w22=0x62bc x26=0x753510a1b3
0x4d870 ldr x1, [x14, w8, uxtw #3]; x1=0x10 x14=0x72e0898080 w8=0x6 mem_r=0x72e08980b0 -> x1=0x7547067031
call jni func: GetArrayLength()
ret: 0x1
str x8, [x14, x19, lsl #3]; x8=0x1 x14=0x72e0898080 x19=0x2 mem_w=0x72e0898090
```

整理一下

```python
0x62bc 0xbc操作码 0x2 目标寄存器 0x6 目标对象
00117c92: 2162                    0029: array-length        v2, v6
```

###### 0xde

```python
0x4d8ac ldrh w22, [x26, #2]!; w22=0x62bc x26=0x753510a1b3 mem_r=0x753510a1b5 -> w22=0x3de x26=0x753510a1b5
0x4d240 ubfx w10, w8, #8, #4; w10=0x5c000000 w8=0x3de -> w10=0x3
0x4d244 sbfx w8, w8, #0xc, #4; w8=0x3de w8=0x3de -> w8=0x0
str x8, [x14, w10, uxtw #3]; x8=0x0 x14=0x72e0898080 w10=0x3 mem_w=0x72e0898098
```

整理一下

```python
0x03de 0xde 操作码 0x3 目标寄存器 0x0 imm
1203                    002a: const/4             v3, 0
```

###### 0xa6

取了两个寄存器然后进行对比，然后跳转，看一条跳转的地方做了什么

```python
0x4d250 ldrh w22, [x26, #2]!; w22=0x3de x26=0x753510a1b5 mem_r=0x753510a1b7 -> w22=0x23a6 x26=0x753510a1b7
[libbaiduprotect.so] 0x7277e87394!0x4e394 and w8, w22, #0xffff; w8=0x77e87394 w22=0x23a6 -> w8=0x23a6
[libbaiduprotect.so] 0x7277e87398!0x4e398 ubfx x9, x8, #8, #4; x9=0x49 x8=0x23a6 -> x9=0x3
[libbaiduprotect.so] 0x7277e8739c!0x4e39c lsr w8, w8, #0xc; w8=0x23a6 w8=0x23a6 -> w8=0x2
[libbaiduprotect.so] 0x7277e873a0!0x4e3a0 lsl x9, x9, #3; x9=0x3 x9=0x3 -> x9=0x18
[libbaiduprotect.so] 0x7277e873a4!0x4e3a4 lsl x8, x8, #3; x8=0x2 x8=0x2 -> x8=0x10
[libbaiduprotect.so] 0x7277e873a8!0x4e3a8 ldr w9, [x14, x9]; w9=0x18 x14=0x72e0898080 x9=0x18 mem_r=0x72e0898098 -> w9=0x0
[libbaiduprotect.so] 0x7277e873ac!0x4e3ac ldr w8, [x14, x8]; w8=0x10 x14=0x72e0898080 x8=0x10 mem_r=0x72e0898090 -> w8=0x1
[libbaiduprotect.so] 0x7277e873b0!0x4e3b0 cmp w9, w8; w9=0x0 w8=0x1 -> w9=0x0
[libbaiduprotect.so] 0x7277e873b4!0x4e3b4 b.ge #0x7277e873ec;
```

x26是pc寄存器，然后取了2字节x8，pc = pc+X8, LDRH W22, [X26] 然后取指令开始执行

```python
4E3B4                 B.GE            loc_4E3EC
.text:000000000004E3EC                 MOV             W17, WZR
.text:000000000004E3F0                 LDRSH           X8, [X26,#2]
.text:000000000004E3F4                 ADD             X26, X26, X8,LSL#1
.text:000000000004E3F8                 LDRH            W22, [X26]
.text:000000000004E3FC                 ADD             X8, X16, W22,UXTB#3
.text:000000000004E400                 ADD             X8, X8, #8
.text:000000000004E404                 LDR             X8, [X8]
.text:000000000004E408                 MOV             W25, WZR
.text:000000000004E40C                 MOV             W24, WZR
.text:000000000004E410                 MOV             W28, WZR
.text:000000000004E414                 MOV             W20, WZR
.text:000000000004E418                 MOV             W23, WZR
.text:000000000004E41C                 MOV             W27, WZR
.text:000000000004E420                 MOV             W19, WZR
.text:000000000004E424                 BR              X8
```

很明显就是一条和跳转指令相关的，然后有b.ge很明显了

```python
    00117c96: 3523 1700               002b: if-ge               v3, v2, :cond_0042
```

###### 0x8f

根据根据索引获取对应数组对象的内容

```python
0x4e3bc ldrh w22, [x26, #4]!; w22=0x23a6 x26=0x753510a1b7 mem_r=0x753510a1bb -> w22=0x48f x26=0x753510a1bb
0x4eaa4 ldrh w8, [x26, #2]; w8=0x77e87aa4 x26=0x753510a1bb mem_r=0x753510a1bd -> w8=0x306
0x4eaac ldr x25, [x14, x9, lsl #3]; x25=0x0 x14=0x72e0898080 x9=0x6 mem_r=0x72e08980b0 -> x25=0x7547067031
0x4ead0 lsl x8, x19, #3; x8=0xd20bb5f4e22c9bb5 x19=0x3 -> x8=0x18
call jni func: GetArrayLength()
ret: 0x1
0x4ead4 ldr w8, [x20, x8]; w8=0x18 x20=0x72e0898080 x8=0x18 mem_r=0x72e0898098 -> w8=0x0
call jni func: GetObjectArrayElement()
ret: 0x7547067035
0x4ebf0 str x25, [x14, w19, uxtw #3]; x25=0x7547067035 x14=0x72e0898080 w19=0x4 mem_w=0x72e08980a0
```

```python
0x48f 0x8f 操作码 0x4 目标寄存器
0x306 0x6 目标对象 0x3 index
00117c9a: 4604 0603               002d: aget-object         v4, v6, v3
```

##### 结语

其他的自己看看吧都差不多，本人小白一枚，有误勿喷。

参考链接

[[[原创]Dalvik解释器源码到VMP分析-Android安全-看雪安全社区｜专业技术交流与安全研究论坛](https://bbs.kanxue.com/thread-226214-1.htm)](https://bbs.kanxue.com/thread-226214-1.htm)

<https://bbs.kanxue.com/thread-281427-1.htm>

[样本来源](https://bbs.kanxue.com/thread-257926-1.htm)

<https://bbs.kanxue.com/thread-270799.htm>

上传的附件：
- baidu.zip

（1.24MB，23次下载）

---

# 回复

## 回复 by SomeMx (#2)

*2026-6-14 08:12*

看看

## 回复 by wx_插曲 (#3)

*2026-6-14 21:27*

看看

## 回复 by 我就是小熊猫 (#4)

*2026-6-15 16:33*

6666

## 回复 by fjqisba (#5)

*2026-6-15 16:37*

vmp有意思

## 回复 by fcguo (#6)

*2026-6-16 09:38*

非常不错的分析，感谢分享。

## 回复 by jyotidwi (#7)

*2026-6-16 17:02*

感谢分享

## 回复 by mb_lfwgtxdb (#8)

*2026-6-16 17:35*

感谢分享

## 回复 by mb_xjdhrmck (#9)

*2026-6-16 23:29*

6666

## 回复 by mb_qimctavn (#10)

*2026-6-17 07:02*

6

## 回复 by secflag (#11)

*2026-6-17 12:11*

感谢分享

## 回复 by 七星舞月 (#12)

*2026-6-17 13:31*

感谢分享

## 回复 by 章康 (#13)

*2026-6-20 21:40*

666

## 回复 by mb_ebihoycp (#14)

*2026-6-25 17:46*

感谢分享

## 回复 by ikunnn (#15)

*2026-7-5 16:19*

mark

## 回复 by iBa0 (#16)

*2026-7-6 08:10*

，66

## 回复 by mb_rfeucrmf (#17)

*2026-7-8 16:42*

66

## 回复 by wx_kx92911 (#18)

*2026-7-8 18:22*

感谢分析

## 回复 by git_51684xuexijiaoben (#19)

感谢分享![image](https://bbs.kanxue.com/view/img/face/003.gif)
