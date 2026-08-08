---
title: '[原创]unidbg还原pangle(TikTok 旗下)算法'
url: https://bbs.kanxue.com/thread-288714.htm
tid: 288714
author: tuosen
date: '2025-10-09'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-08T10:42:13+00:00'
replies: 134
---

# 主要工具

## ida9.1

静态分析

## unidgb

动态调试: debug不用多说

trace read: 跟踪内存的读取

trace write: 跟踪内存写入

trace code: trace 执行的汇编日志

## 010

方便分析trace后的汇编, 根据汇编还原具体的算法

# 目标函数

\```
Java_com_bytedance_sdk_component_pglcrypt_PglCryptUtils_bc(
        JNIEnv *JNIEnv,
        __int64 a2,
        int n1011,
        void *a4)
\```

# 固定随机数

`RandomFileIO`

\```
  public static String toHex(byte[] bytes) {
        StringBuilder hexString = new StringBuilder();
        for(byte b: bytes) {
            hexString.append(String.format("%02x ", b));
        }
        return hexString.toString().trim();
    }
    @Override
    public int read(Backend backend, Pointer buffer, int count) {
        int total = 0;
        byte[] buf = new byte[Math.min(0x1000, count)];
        randBytes(buf);
        System.out.println("固定随机数:" + toHex(buf));
        Pointer pointer = buffer;
        while (total < count) {
            int read = Math.min(buf.length, count - total);
            pointer.write(0, buf, 0, read);
            total += read;
            pointer = pointer.share(read);
        }
        return total;
    }

    protected void randBytes(byte[] bytes) {
//        ThreadLocalRandom.current().nextBytes(bytes);
        Arrays.fill(bytes, (byte) 1);
    }
\```

# 固定时间戳

`UnixSyscallHandler`

\```
 protected long currentTimeMillis() {
//        return System.currentTimeMillis();
        System.out.println("固定时间戳:"+ 1744706898936L);
        return  1744706898936L;
    }
\```

# 构造主动调用

\```
public void call() {
        List<Object> list = new ArrayList<>(4);
        list.add(vm.getJNIEnv());
        list.add(0);
        list.add(1010);

        String inputHex = "04369e6fbcb4";
        System.out.println("输入:" + inputHex);
        byte[] byteArray = hexStringToByteArray(inputHex);

        ByteArray arr1 = new ByteArray(vm,byteArray);
        list.add(vm.addLocalObject(arr1));

        Number number = module.callFunction(emulator, 0x0350C, list.toArray());

        byte [] result = (byte[]) vm.getObject(number.intValue()).getValue();

        String resultHex = bytesToHexString(result);
        System.out.println("输出:" + resultHex);
        System.out.println(Arrays.toString(result));
    }
\```

# 输入输出

\```
输入: 04369e6fbcb4  //为了还原算法方便, 先搞个短的
时间戳:1744941231020
固定随机数:01 01 01 01 01 01 01 01
pathname: /dev/urandom
固定随机数:01 01 01 01 01 01 01 01
pathname: /dev/urandom
固定随机数:01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01
固定时间戳:1744706898936
随机数: 6c158b50
随机数: 7d07d5e7
随机数: 8dd1b04
随机数: 7bc9fbeb
随机数: 22d9f739
随机数: 7d25804f
随机数: 50c7c469
随机数: 77d8cc98
随机数: 4fef7840
随机数: 5b45fe10
随机数: 6891d51e
随机数: 56b91f98
输出: 041e5599061da19c89851f755619894e620007040b0901090800000e08107292182baff4ac107292162baff4ac10729216
\```

\```
JNIEnv->SetByteArrayRegion([B@0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000, 0, 49, RW@0x12358000) was called from RX@0x1200c984[libpglarmor.so]0xc984
\```

\```
 emulator.attach().addBreakPoint(module.base + 0xc984, new BreakPointCallback() {
            @Override
            public boolean onHit(Emulator<?> emulator, long address) {
                RegisterContext context = emulator.getContext();
                int len = context.getIntArg(3); // 获取长度（日志中为 49）

                long bufPtr = context.getLongArg(4);
                System.out.println("Buffer address: " + Long.toHexString(bufPtr));
                byte[] bufData = emulator.getBackend().mem_read(bufPtr, len);
                System.out.println("Buffer content (len=" + len + "): " + Arrays.toString(bufData));
                System.out.println("Buffer hex: " + toHex(bufData));
                return true;
            }
        });
\```

\```
Buffer address: 12358000
Buffer content (len=49): [4, 59, 5, -111, 118, 112, 6, 35, 20, -36, -84, 111, 56, -3, -100, -18, -96, 0, 7, 4, 11, 9, 0, 9, 8, 0, 0, 14, 8, 17, 115, -109, 24, 42, -82, -11, -83, 17, 115, -109, 23, 42, -82, -11, -83, 17, 115, -109, 23]
Buffer hex: 04 3b 05 91 76 70 06 23 14 dc ac 6f 38 fd 9c ee a0 00 07 04 0b 09 00 09 08 00 00 0e 08 11 73 93 18 2a ae f5 ad 11 73 93 17 2a ae f5 ad 11 73 93 17
确认这个12358000就是返回值的地址
\```

# traceWrite跟踪内存写入(根据结果反推)

\```
      emulator.traceWrite(0x12358000, 12358000 + 0x49);
\```

\```
[18:20:48 893] Memory WRITE at 0x12358028, data size = 1, data value = 0x17, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358027, data size = 1, data value = 0x93, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358026, data size = 1, data value = 0x73, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358025, data size = 1, data value = 0x11, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358024, data size = 1, data value = 0xad, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358023, data size = 1, data value = 0xf5, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358022, data size = 1, data value = 0xae, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358021, data size = 1, data value = 0x2a, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358020, data size = 1, data value = 0x18, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x1235801f, data size = 1, data value = 0x93, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x1235801e, data size = 1, data value = 0x73, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x1235801d, data size = 1, data value = 0x11, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x1235801c, data size = 1, data value = 0x08, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x1235801b, data size = 1, data value = 0x0e, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x1235801a, data size = 1, data value = 0x00, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358019, data size = 1, data value = 0x00, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358018, data size = 1, data value = 0x08, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358017, data size = 1, data value = 0x09, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358016, data size = 1, data value = 0x00, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358015, data size = 1, data value = 0x09, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358014, data size = 1, data value = 0x0b, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358013, data size = 1, data value = 0x04, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358012, data size = 1, data value = 0x07, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358011, data size = 1, data value = 0x00, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x12358010, data size = 1, data value = 0xa0, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x1235800f, data size = 1, data value = 0xee, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 893] Memory WRITE at 0x1235800e, data size = 1, data value = 0x9c, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x1235800d, data size = 1, data value = 0xfd, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x1235800c, data size = 1, data value = 0x38, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x1235800b, data size = 1, data value = 0x6f, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x1235800a, data size = 1, data value = 0xac, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x12358009, data size = 1, data value = 0xdc, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x12358008, data size = 1, data value = 0x14, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x12358007, data size = 1, data value = 0x23, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x12358006, data size = 1, data value = 0x06, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x12358005, data size = 1, data value = 0x70, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x12358004, data size = 1, data value = 0x76, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x12358003, data size = 1, data value = 0x91, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x12358002, data size = 1, data value = 0x05, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x12358001, data size = 1, data value = 0x3b, PC=RX@0x12003440[libpglarmor.so]0x3440, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[18:20:48 894] Memory WRITE at 0x12358000, data size = 1, data value = 0x04, PC=RX@0x12009590[libpglarmor.so]0x9590, LR=unidbg@0xe4fff648
\```

这个案例我们改用正推更简单, 从参数入手

# 正推入口

按y 修改为JNIenv*

按n重命名下

\```
jbyteArray __fastcall Java_com_bytedance_sdk_component_pglcrypt_PglCryptUtils_bc(
        JNIEnv *JNIEnv,
        __int64 a2,
        int n1011,
        void *a4)
{
  if ( n1011 == 1011 )
    return (jbyteArray)sub_C9F4(JNIEnv, a4);
  if ( n1011 == 1010 )
    return sub_C8D0(JNIEnv, a4);
  return 0LL;
}
\```

看下n1011的值, 这种直接通过trace code, w2 = 0x3f2

\```
[18:17:14 739][libpglarmor.so 0x0350c] [fd7bbfa9] 0x1200350c: "stp x29, x30, [sp, #-0x10]!" x29=0x0 x30=0x7ffff0000 sp=0xe4fff710 => x29=0x0 x30=0x7ffff0000 sp=0xe4fff700
[18:17:14 743][libpglarmor.so 0x03510] [fd030091] 0x12003510: "mov x29, sp" sp=0xe4fff700 => x29=0xe4fff700
[18:17:14 745][libpglarmor.so 0x03514] [5fcc0f71] 0x12003514: "cmp w2, #0x3f3" => nzcv: N=1, Z=0, C=0, V=0 w2=0x3f2
[18:17:14 748][libpglarmor.so 0x03518] [e0000054] 0x12003518: "b.eq #0x12003534" nzcv: N=1, Z=0, C=0, V=0
[18:17:14 749][libpglarmor.so 0x0351c] [5fc80f71] 0x1200351c: "cmp w2, #0x3f2" => nzcv: N=0, Z=1, C=1, V=0 w2=0x3f2
[18:17:14 750][libpglarmor.so 0x03520] [21010054] 0x12003520: "b.ne #0x12003544" nzcv: N=0, Z=1, C=1, V=0
\```

0x3f2的10进制就是1010,

那么走的sub_C8D0

\```
jbyteArray __fastcall sub_C8D0(JNIEnv *JNIEnv, void *a2)
{
  int array_len; // w22
  JNIEnv *byte_array; // x0
  jbyte *byte_array_1; // x21
  jbyte *ptr; // x23
  jbyteArray v8; // x22
  unsigned int v10; // [xsp+4h] [xbp-Ch] BYREF
  __int64 v11; // [xsp+8h] [xbp-8h]

  v11 = *(_QWORD *)(_ReadStatusReg(ARM64_SYSREG(3, 3, 13, 0, 2)) + 40);
  if ( !a2 )
    return 0LL;
  array_len = ((__int64 (__fastcall *)(JNIEnv *))(*JNIEnv)->GetArrayLength)(JNIEnv);
  byte_array = (JNIEnv *)(*JNIEnv)->GetByteArrayElements(JNIEnv, a2, 0LL);
  if ( !byte_array )
    return 0LL;
  byte_array_1 = (jbyte *)byte_array;
  v10 = 0;
  ptr = (jbyte *)sub_3550(byte_array, array_len, (__int64)&v10, 4);
  if ( ptr )
  {
    v8 = (*JNIEnv)->NewByteArray(JNIEnv, v10);
    (*JNIEnv)->SetByteArrayRegion(JNIEnv, v8, 0LL, v10, ptr);
  }
  else
  {
    v8 = 0LL;
  }
  (*JNIEnv)->ReleaseByteArrayElements(JNIEnv, a2, byte_array_1, 0LL);
  free(ptr);
  return v8;
}
\```

看下3550函数, 无法f5, 按p

byte_array和len被传入sub_3550

\```
__int64 __fastcall sub_3550(JNIEnv *JNIEnv, int array_len, __int64 a3, int n4)
{
  __int64 v4; // x30
  unsigned __int64 v5; // x12
  __int64 v7[2]; // [xsp-480h] [xbp-490h] BYREF
  __int64 v8; // [xsp-470h] [xbp-480h]
  __int64 v9; // [xsp-38h] [xbp-48h] BYREF
  JNIEnv *JNIEnv_1; // [xsp-30h] [xbp-40h] BYREF
  int array_len_1; // [xsp-28h] [xbp-38h]
  __int64 v12; // [xsp-20h] [xbp-30h]
  int n4_1; // [xsp-18h] [xbp-28h]
  __int64 v14; // [xsp-10h] [xbp-20h]
  int n640; // [xsp+4h] [xbp-Ch]
  __int64 v16; // [xsp+8h] [xbp-8h]

  v16 = *(_QWORD *)(_ReadStatusReg(ARM64_SYSREG(3, 3, 13, 0, 2)) + 40);
  n640 = 640;
  v5 = (((~(unsigned __int64)sub_3550 & 0x10400040400LL | 0xA060400A021040LL)
       + ((unsigned __int64)sub_3550 & 0x10400040400LL)) | 0x1010104) ^ 0xFF5F9EBBF49C6B5CLL;
  JNIEnv_1 = JNIEnv;
  array_len_1 = array_len;
  v12 = a3;
  n4_1 = n4;
  v7[0] = (__int64)sub_43FC;
  v7[1] = (__int64)&v9;
  v8 = v4;
  sub_4408((char *)off_16600 + v5, (__int64)&JNIEnv_1, (__int64)off_16608 + v5, (__int64)off_16610 + v5, v7);
  return v14;
}
\```

打印下入参看对不对

\```
 emulator.attach().addBreakPoint(module.base + 0x3550, new BreakPointCallback() {
            @Override
            public boolean onHit(Emulator<?> emulator, long address) {
                RegisterContext context = emulator.getContext();
                int len = context.getIntArg(1); // 获取长度（日志中为 49）

                long bufPtr = context.getLongArg(0);
                System.out.println("Buffer address 0x3550: " + Long.toHexString(bufPtr));
                byte[] bufData = emulator.getBackend().mem_read(bufPtr, len);
                System.out.println("Buffer content 0x3550(len=" + len + "): " + Arrays.toString(bufData));
                System.out.println("Buffer hex 0x3550: " + toHex(bufData));
                return false;
            }
        });
\```

\```
Buffer address 0x3550: 12019000
Buffer content 0x3550(len=6): [4, 54, -98, 111, -68, -76]
Buffer hex 0x3550: 04 36 9e 6f bc b4
\```

也可以断点后通过mx0查看

![image](https://bbs.kanxue.com/upload/attach/202510/846973_73HPNHQYKJDV9ZM.webp)

trace read一下看下谁读取了, 因为ida查看有混淆无法知道进入哪个函数了

\```
emulator.traceRead(0x12019000, 0x12019000 + 0x6);
\```

\```
[12:12:29 875] Memory READ at 0x12019000, data size = 1, data value = 0x04, PC=RX@0x1200333c[libpglarmor.so]0x333c, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[12:12:29 876] Memory READ at 0x12019001, data size = 1, data value = 0x36, PC=RX@0x1200333c[libpglarmor.so]0x333c, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[12:12:29 876] Memory READ at 0x12019002, data size = 1, data value = 0x9e, PC=RX@0x1200333c[libpglarmor.so]0x333c, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[12:12:29 876] Memory READ at 0x12019003, data size = 1, data value = 0x6f, PC=RX@0x1200333c[libpglarmor.so]0x333c, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[12:12:29 876] Memory READ at 0x12019004, data size = 1, data value = 0xbc, PC=RX@0x1200333c[libpglarmor.so]0x333c, LR=RX@0x120043a0[libpglarmor.so]0x43a0
[12:12:29 877] Memory READ at 0x12019005, data size = 1, data value = 0xb4, PC=RX@0x1200333c[libpglarmor.so]0x333c, LR=RX@0x120043a0[libpglarmor.so]0x43a0
\```

ida 查看下 0x333c, 在函数sub_330C中,这个函数就是内存copy,  交叉引用下sub_36C8

看下sub_36C8, 断点查看入参mx1

\```
020004369e6fbcb40c00010101010101
\```

参数1:0x10 长度

参数2:0x12359000 我们的参数

参数3:0x12359000 返回值

tracewrite 0x12359000  看看他是怎么被写入的

0x385C 开始写入

![image](https://bbs.kanxue.com/upload/attach/202510/846973_97HPQKZT9AADQP3.webp)

ida查看代码

\```
input_1 = "020004369e6fbcb40c"
v42 = "00000000a3e1eaf4"
  n255_1 = len;
  myresult_1 = myresult;
  v11 = 4 * (v8 % 5) + 16;
  do
  {
    v12 = BYTE1(v42);
    *myresult_1 = v42 ^ *input_1;
    v13 = v12 ^ input_1[1];
    v14 = BYTE2(v42);
    myresult_1[1] = v13;
    v15 = v14 ^ input_1[2];
    v16 = BYTE3(v42);
    myresult_1[2] = v15;
    v17 = v16 ^ input_1[3];
    v18 = BYTE4(v42);
    myresult_1[3] = v17;
    v19 = v18 ^ input_1[4];
    v20 = BYTE5(v42);
    myresult_1[4] = v19;
    v21 = v20 ^ input_1[5];
    v22 = BYTE6(v42);
    myresult_1[5] = v21;
    v23 = v22 ^ input_1[6];
    v24 = HIBYTE(v42);
    myresult_1[6] = v23;
    myresult_1[7] = v24 ^ input_1[7];
    (loc_4010)(s, myresult_1, myresult_1, v11);   //第二个算法
    sub_330C(&v42, myresult_1, 8uLL);
    v25 = (n255_1 | 0xFFFFFFF7) + (n255_1 & 0xFFFFFFF7);
    myresult_1 += 8;
    n255_1 = v25 + 1;
    input_1 += 8;
  }
  while ( v25 != -1 );
\```

看下v42 的值是多少

\```
hex(0xe4ffefd0 + 0x18)
'0xe4ffefe8'
\```

![image](https://bbs.kanxue.com/upload/attach/202510/846973_FFNYBBEKHR65FN5.webp)

v42 = 01010101a3e1eaf4  因为长度是unsigned int  4字节

根据ida的伪代码和trace code 还原第一个算法

\```
[18:17:15 606][libpglarmor.so 0x03854] [2801084a] 0x12003854: "eor w8, w9, w8" w9=0x0 w8=0x2 => w8=0x2
[18:17:15 606][libpglarmor.so 0x03858] [e9674039] 0x12003858: "ldrb w9, [sp, #0x19]" sp=0xe4ffefd0 => w9=0x0
\```

# 第一个算法(异或):

\```
input_hex = "020004369e6fbcb40c00010101010101"  # 输入：9 字节
v42_hex = "01010101a3e1eaf4"    # v42：8 字节

input_data =  bytes.fromhex(input_hex)
#[0x02, 0x00, 0x04, 0x36, 0x9e, 0x6f, 0xbc, 0xb4]  # x22=0x12358000处的数据
v42_data =  bytes.fromhex(v42_hex)
#[0x00, 0x00, 0x00, 0xa3, 0xe1, 0xea, 0xf4, 0x00]
# 存储结果的数组（模拟x19=0x12358000的内存）
result_1 = [0] * 8

# 模拟汇编代码的逻辑
for i in range(8):
    # ldrb w8, [x22, #i] => 读取x22 + i的数据到w8
    w8 = input_data[i]

    # ldrb w9, [sp, #0x19 + i] => 读取sp + 0x19 + i的数据到w9
    w9 = v42_data[i]

    # eor w8, w9, w8 => w8 = w9 ^ w8
    w8 = w9 ^ w8

    # strb w8, [x19, #i] => 将w8存储到x19 + i
    result_1[i] = w8

# 输出结果 030105373d8e5640
print("result_1:", ''.join([format(byte, '02x') for byte in result_1]))
\```

\```
v11 = 4 * (v42_int % 5) + 16
print("v11:",v11)
v11 = 20
\```

# 第二个算法sub_4010

\```
void __fastcall sub_4010(__int64 rand, unsigned int *param, _BYTE *result, unsigned int flag)
{
  unsigned int v4; // w9
  unsigned int v5; // w8
  unsigned int v6; // w10
  unsigned int i; // w12
  int v8; // w14
  int v9; // w17
  int v10; // w14

  v4 = bswap32(*param);
  v5 = bswap32(param[1]);
  if ( flag )
  {
    v6 = 0;
    for ( i = 0; i < flag; i = (i ^ 0xFFFFFFFE) + ((2 * i) | 2) + 1 )
    {
      v8 = *(rand + 4LL * (v6 & 3));
      v9 = v8 ^ v6;
      v10 = v8 | v6;
      v6 = ((2 * v6) & 0x3C6EF372) + (v6 ^ 0x9E3779B9);
      v4 += (2 * v10 - v9) ^ (((v5 >> 5) ^ (16 * v5)) + v5);
      v5 += (((16 * v4) ^ (v4 >> 5)) + v4) ^ (*(rand + 4LL * ((v6 >> 11) & 3)) + v6);
    }
  }
  result[3] = v4;
  result[7] = v5;
  *result = HIBYTE(v4);
  result[1] = BYTE2(v4);
  result[2] = BYTE1(v4);
  result[4] = HIBYTE(v5);
  result[5] = BYTE2(v5);
  result[6] = BYTE1(v5);
}
\```

参数:

030105373d8e5640 8个字节

返回值:

\```
1edc84501dc383890c00010101010101
\```

debug断点查看入参:

\```
x0=0xe4fff028(-452988888) x1=0x12359000 x2=0x12359000 x3=0x10
\```

参数1: s 就是随机数 01010101010101010101010101010101

\```
01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01
\```

x1 = 是第一个算法的结果: 030105373d8e5640

x2 是返回值

x3 是一个v11 判断是否等于0走不同的逻辑

\```
[libpglarmor.so 0x0400c] [ed260094] 0x1200400c: "bl #0x1200dbc0"
    // 跳转并链接到地址 0x1200dbc0，调用函数（返回地址存入 x30）

[libpglarmor.so 0x04010] [ff4300d1] 0x12004010: "sub sp, sp, #0x10"
    // 栈指针减去 16，为局部变量腾出空间（入栈）

[libpglarmor.so 0x04014] [28284029] 0x12004014: "ldp w8, w10, [x1]"
    // 从 x1 指向的地址一次性加载两个 32 位数据到 w8 和 w10（结构体读取？）

[libpglarmor.so 0x04018] [0909c05a] 0x12004018: "rev w9, w8"
    // 将 w8 的字节顺序翻转，结果放入 w9（大小端转换）
    w9 = int.from_bytes(reg["w8"].to_bytes(4, 'little'), 'big')

[libpglarmor.so 0x0401c] [4809c05a] 0x1200401c: "rev w8, w10"
    // 将 w10 的字节顺序翻转，结果放入 w8
    w8 = int.from_bytes(reg["w10"].to_bytes(4, 'little'), 'big')

[libpglarmor.so 0x04020] [83040034] 0x12004020: "cbz w3, #0x120040b0"
    // 如果 w3 == 0，则跳转到 0x120040b0（可能是 if 判断）

[libpglarmor.so 0x04024] [2b378f52] 0x12004024: "movz w11, #0x79b9"
    // 把 16 位立即数 0x79B9 写入 w11（movz 清高位）

[libpglarmor.so 0x04028] [4d6e9e52] 0x12004028: "movz w13, #0xf372"
    // 把 16 位立即数 0xF372 写入 w13（movz 清高位）

[libpglarmor.so 0x0402c] [ea031f2a] 0x1200402c: "mov w10, wzr"
    // 把零寄存器（wzr）写入 w10，即 w10 = 0

[libpglarmor.so 0x04030] [ec031f2a] 0x12004030: "mov w12, wzr"
    // 把零寄存器写入 w12，即 w12 = 0

[libpglarmor.so 0x04034] [ebc6b372] 0x12004034: "movk w11, #0x9e37, lsl #16"
    // 把 w11 的高 16 位替换为 0x9E37，低 16 位保持不变（构造 32 位立即数）

[libpglarmor.so 0x04038] [cd8da772] 0x12004038: "movk w13, #0x3c6e, lsl #16"
    // 把 w13 的高 16 位替换为 0x3C6E，低 16 位保持不变

[libpglarmor.so 0x0403c] [4e050012] 0x1200403c: "and w14, w10, #3"
    // w14 = w10 & 0x3，取最低两位（通常用于模 4 运算）

[libpglarmor.so 0x04040] [4f010b4a] 0x12004040: "eor w15, w10, w11"
    // w15 = w10 异或 w11

[libpglarmor.so 0x04044] [b0050a0a] 0x12004044: "and w16, w13, w10, lsl #1"
    // w16 = w13 & (w10 << 1)，对 w10 左移后与 w13 进行按位与

[libpglarmor.so 0x04048] [0e586eb8] 0x12004048: "ldr w14, [x0, w14, uxtw #2]"
    // 从地址 x0 + (w14 无符号扩展并左移 2 位) 读取 4 字节，存到 w14
    // 通常是访问一个整型数组：4 字节对齐

[libpglarmor.so 0x0404c] [d1010a4a] 0x1200404c: "eor w17, w14, w10"
    // w17 = w14 异或 w10
\```

python还原

rand hex = 01010101010101010101010101010101

param hex = 030105373d8e5640

flag= 0x20

返回result

\```
; FUNCTION CHUNK AT .text:0000000000004130 SIZE 00000040 BYTES
.text:0000000000004010
.text:0000000000004010 ; __unwind {
.text:0000000000004010                 SUB             SP, SP, #0x10
.text:0000000000004014                 LDP             W8, W10, [X1]
.text:0000000000004018                 REV             W9, W8
.text:000000000000401C                 REV             W8, W10
.text:0000000000004020                 CBZ             W3, loc_40B0
.text:0000000000004024                 MOV             W11, #0x79B9
.text:0000000000004028                 MOV             W13, #0xF372
.text:000000000000402C                 MOV             W10, WZR
.text:0000000000004030                 MOV             W12, WZR
.text:0000000000004034                 MOVK            W11, #0x9E37,LSL#16
.text:0000000000004038                 MOVK            W13, #0x3C6E,LSL#16
.text:000000000000403C
.text:000000000000403C loc_403C                                ; CODE XREF: sub_4010+9C↓j
.text:000000000000403C                 AND             W14, W10, #3
.text:0000000000004040                 EOR             W15, W10, W11
.text:0000000000004044                 AND             W16, W13, W10,LSL#1
.text:0000000000004048                 LDR             W14, [X0,W14,UXTW#2]
.text:000000000000404C                 EOR             W17, W14, W10
.text:0000000000004050                 ORR             W14, W14, W10
.text:0000000000004054                 ADD             W10, W16, W15
.text:0000000000004058                 LSR             W15, W8, #5
.text:000000000000405C                 UBFX            W16, W10, #0xB, #2
.text:0000000000004060                 EOR             W15, W15, W8,LSL#4
.text:0000000000004064                 LSL             W14, W14, #1
.text:0000000000004068                 ADD             W15, W15, W8
.text:000000000000406C                 SUB             W14, W14, W17
.text:0000000000004070                 EOR             W14, W14, W15
.text:0000000000004074                 LDR             W15, [X0,W16,UXTW#2]
.text:0000000000004078                 ADD             W9, W14, W9
.text:000000000000407C                 LSL             W16, W12, #1
.text:0000000000004080                 LSL             W14, W9, #4
.text:0000000000004084                 EOR             W12, W12, #0xFFFFFFFE
.text:0000000000004088                 EOR             W14, W14, W9,LSR#5
.text:000000000000408C                 ORR             W16, W16, #2
.text:0000000000004090                 ADD             W14, W14, W9
.text:0000000000004094                 ADD             W15, W15, W10
.text:0000000000004098                 EOR             W14, W14, W15
.text:000000000000409C                 ADD             W12, W12, W16
.text:00000000000040A0                 ADD             W8, W14, W8
.text:00000000000040A4                 ADD             W12, W12, #1
.text:00000000000040A8                 CMP             W12, W3
.text:00000000000040AC                 B.CC            loc_403C
.text:00000000000040B0
.text:00000000000040B0 loc_40B0                                ; CODE XREF: sub_4010+10↑j
.text:00000000000040B0                 MOV             W10, #0x177
.text:00000000000040B4                 MOV             W11, #0x29 ; ')'
.text:00000000000040B8                 MOV             W12, #1
.text:00000000000040BC                 STR             W10, [SP,#0x10+var_4]
.text:00000000000040C0                 STR             W11, [SP,#0x10+var_8]
.text:00000000000040C4                 LDR             W10, [SP,#0x10+var_4]
.text:00000000000040C8                 LDR             W11, [SP,#0x10+var_8]
.text:00000000000040CC                 MADD            W10, W10, W10, W12
.text:00000000000040D0                 MUL             W11, W11, W11
.text:00000000000040D4                 LSL             W12, W11, #3
.text:00000000000040D8                 SUB             W11, W12, W11
.text:00000000000040DC                 CMP             W10, W11
.text:00000000000040E0                 B.NE            loc_4130
.text:00000000000040E0 ; End of function sub_4010
.text:00000000000040E0
.text:00000000000040E0 ; ---------------------------------------------------------------------------
.text:00000000000040E4                 DCD 0x46EB4EBF
.text:00000000000040E8                 DCQ 0xC5DD8AB06014E91B, 0x912E03FFA34C8745, 0xA54FAF3261D1C8CC
.text:0000000000004100                 DCQ 0x44F15B6CE3AF8A5B, 0xA27337EDE178E012, 0xA36AEEA400FBEFF9
.text:0000000000004118                 DCQ 0x66FF9CF182E0EB4F, 0xC05773E5E5F4E4AA, 0x64EA24F966AF5C2A
.text:0000000000004130 ; ---------------------------------------------------------------------------
.text:0000000000004130 ; START OF FUNCTION CHUNK FOR sub_4010
.text:0000000000004130
.text:0000000000004130 loc_4130                                ; CODE XREF: sub_4010+D0↑j
.text:0000000000004130                 LSR             W10, W9, #0x18
.text:0000000000004134                 LSR             W11, W9, #0x10
.text:0000000000004138                 LSR             W12, W9, #8
.text:000000000000413C                 STRB            W9, [X2,#3]
.text:0000000000004140                 LSR             W9, W8, #8
.text:0000000000004144                 STRB            W8, [X2,#7]
.text:0000000000004148                 STRB            W10, [X2]
.text:000000000000414C                 LSR             W10, W8, #0x18
.text:0000000000004150                 STRB            W11, [X2,#1]
.text:0000000000004154                 LSR             W11, W8, #0x10
.text:0000000000004158                 STRB            W12, [X2,#2]
.text:000000000000415C                 STRB            W10, [X2,#4]
.text:0000000000004160                 STRB            W11, [X2,#5]
.text:0000000000004164                 STRB            W9, [X2,#6]
.text:0000000000004168                 ADD             SP, SP, #0x10
.text:000000000000416C                 RET
.text:000000000000416C ; } // starts at 4010
.text:000000000000416C ; END OF FUNCTION CHUNK FOR sub_4010
\```

\```
stp x29, x30, [sp, #-0x10]!" x29=0x0 x30=0x7ffff0000 sp=0xe4fff710 => x29=0x0 x30=0x7ffff0000 sp=0xe4fff700
[09:58:33 335][libpglarmor.so 0x03510] [fd030091] 0x12003510: "mov x29, sp" sp=0xe4fff700 => x29=0xe4fff700
[09:58:33 337][libpglarmor.so 0x03514] [5fcc0f71] 0x12003514: "cmp w2, #0x3f3" => nzcv: N=1, Z=0, C=0, V=0 w2=0x3f2
[09:58:33 339][libpglarmor.so 0x03518] [e0000054] 0x12003518: "b.eq #0x12003534" nzcv: N=1, Z=0, C=0, V=0
[09:58:33 340][libpglarmor.so 0x0351c] [5fc80f71] 0x1200351c: "cmp w2, #0x3f2" => nzcv: N=0, Z=1, C=1, V=0 w2=0x3f2
[09:58:33 341][libpglarmor.so 0x03520] [21010054] 0x12003520: "b.ne #0x12003544" nzcv: N=0, Z=1, C=1, V=0
[09:58:33 344][libpglarmor.so 0x03524] [e10303aa] 0x12003524: "mov x1, x3" x3=0x67e2d983 => x1=0x67e2d983
[09:58:33 345][libpglarmor.so 0x03528] [ea240094] 0x12003528: "bl #0x1200c8d0"
\```

# 监控result内存变化

我们现在知道每次result的地址都是:

`0x12359000`

\```
long result_addr = hexToLong(0x12359000);
        emulator.attach().addBreakPoint(module.base + 0x38E8, new BreakPointCallback() {
            @Override
            public boolean onHit(Emulator<?> emulator, long address) {
                long bufPtr = result_addr;
                byte[] bufData = emulator.getBackend().mem_read(bufPtr, 8);
                System.out.println("执行完4010和330c后, result变化: " + toHex(bufData));
//                emulator.attach().addBreakPoint(context.getLR(), new BreakPointCallback() {
//                    @Override
//                    public boolean onHit(Emulator<?> emulator, long address) {
//                        return false;
//                    }
//                });
                return false;
            }
        });
\```

在循环中断点这样子就可以知道我们的输入每轮的变化

# 监控sub4010 的参数和返回值

\```
emulator.attach().addBreakPoint(module.base + 0x4010, new BreakPointCallback() {
            @Override
            public boolean onHit(Emulator<?> emulator, long address) {
                RegisterContext context = emulator.getContext();
                UnidbgPointer pointer1 = context.getPointerArg(1);
                Inspector.inspect(pointer1.getByteArray(0, 8), "0x4010参数: "+pointer1);
                emulator.attach().addBreakPoint(context.getLR(), new BreakPointCallback() {
                    final RegisterContext context2 = emulator.getContext();
                    @Override
                    public boolean onHit(Emulator<?> emulator, long address) {

                        UnidbgPointer pointer2 = context2.getPointerArg(2);

                        Inspector.inspect(pointer2.getByteArray(0, 8), "0x4010结果: " + pointer2);
                        return false;
                    }
                });
                return true;
            }
        });
\```

第一轮

\```
[17:11:09 171]0x4010参数: RW@0x12359000, md5=06420b16f638d85415c490a9b15e7e69, hex=030105373d8e5640
size: 8
0000: 03 01 05 37 3D 8E 56 40                            ...7=.V@
^-----------------------------------------------------------------------------^

>-----------------------------------------------------------------------------<
[17:11:09 173]0x4010结果: RW@0x12359000, md5=2f18be93cbca895a282f55da20eee7f6, hex=1edc84501dc38389
size: 8
0000: 1E DC 84 50 1D C3 83 89
\```

第二轮

\```
[17:12:52 748]0x4010参数: RW@0x12359008, md5=54f823d244849701ae5e8a1f5f0ef7fa, hex=12dc85511cc28288
size: 8
0000: 12 DC 85 51 1C C2 82 88                            ...Q....
^-----------------------------------------------------------------------------^

>-----------------------------------------------------------------------------<
[17:12:52 749]0x4010结果: RW@0x12359008, md5=aacfaeaaf85df28193fb91e07e63109f, hex=851f3b5607004e62
size: 8
0000: 85 1F 3B 56 07 00 4E 62
\```

查看tracecode更快

![image](https://bbs.kanxue.com/upload/attach/202510/846973_P69JSR5U8KPXZF4.webp)

第一轮是:01010101a3e1eaf4 ^ 020004369e6fbcb4 = 030105373d8e5640

第二轮是:1edc84501dc38389 ^ 0c00010101010101 = 12dc85511cc28288

020004369e6fbcb4 是输入的前8个字节

0c00010101010101 是输入的后8个字节

第一次4010的参数是030105373d8e5640(第一次异或的结果)

第一次4010的结果: 1edc84501dc38389

第二次4010的参数是12dc85511cc28288(第二次异或的结果)

第一次4010的结果: 851f3b5607004e62

# python代码还原算法

\```
import struct
import binascii

def convert_function(input_hex, v42_hex, len, rand_hex):
    print("参数:",input_hex)
    if len:
        i = 4 * ((2749491956 & 0xFFFFFFFF) % 5) + 16
        # print("i:",i)
        w25 = len
        c = 0
        # 2轮计算, 第一轮8字节0x12359000   020004369e6fbcb4
        # 第二轮8字节0x12359008  0c00010101010101
        while True:

            if c == 0:
                _input = "020004369e6fbcb4"
            else:
                _input = "0c00010101010101"
            result_1 = sub_one(_input, v42_hex)  # 异或结果
            print("本次处理input:",_input)

            print("异或结果:",result_1)
            v42_hex = sub_4010(rand_hex, result_1, 0x20)
            # print("第",c,"轮输入:",_input)
            # print("第",c,"轮输出:",  binascii.hexlify(result_1).decode('utf-8'))
            # v42 = sub_330C(myresult_1, 8)

            w8 = w25 & 0xfffffff7
            w9 = w25 | 0xfffffff7
            w8 = (w9 + w8) & 0xFFFFFFFF  # 模拟32位溢出
            w25 = (w8 + 1) & 0xFFFFFFFF  # 模拟32位溢出并设置条件标志
            # print("v25:",v25)
            # result_1 = result_1[2:]
            # print("_len:",_len)

            # if v25 <= 0:
            #     break
            # print("w25:",w25)
            c=c+1
            if w25 <= 0:
                break

def sub_one(input_hex, v42_hex):
    # 模拟内存数据
  # sp=0xe4ffefd0 + 0x19到0x1f的数据
    # input_hex = "020004369e6fbcb40c00010101010101"  # 输入：9 字节
    # v42_hex = "01010101a3e1eaf4"      # v42：8 字节

    input_data = bytes.fromhex(input_hex)
    v42_data = bytes.fromhex(v42_hex)

    # 把 v42_data 转换为整数，按大端字节序
    v42_int = int.from_bytes(v42_data, byteorder='big')

    v11 = 4 * (v42_int % 5) + 16
    print("v11:",v11)

    #[0x00, 0x00, 0x00, 0xa3, 0xe1, 0xea, 0xf4, 0x00]
    # 存储结果的数组（模拟x19=0x12358000的内存）
    result_1 = [0] * 8

    # 模拟汇编代码的逻辑
    for i in range(8):
        # ldrb w8, [x22, #i] => 读取x22 + i的数据到w8
        w8 = input_data[i]

        # ldrb w9, [sp, #0x19 + i] => 读取sp + 0x19 + i的数据到w9
        w9 = v42_data[i]

        # eor w8, w9, w8 => w8 = w9 ^ w8
        w8 = w9 ^ w8

        # strb w8, [x19, #i] => 将w8存储到x19 + i
        result_1[i] = w8

    # 输出结果
    result_hex = ''.join([format(byte, '02x') for byte in result_1])
    print("小算法1:", result_hex)
    return result_hex

def sub_4010(rand_hex, param_hex, flag):
    # print("rand_hex:",rand_hex)
    print("sub4010参数:",param_hex)
    # print("flag:",flag)
    rand_bytes = bytes.fromhex(rand_hex)
    param_bytes = bytes.fromhex(param_hex)
    rand = []
    for i in range(0, len(rand_bytes), 4):
        rand.append(int.from_bytes(rand_bytes[i:i+4], byteorder='little'))

    w8, w10 = struct.unpack("<II", param_bytes)

    w9 = ((w8 & 0xFF) << 24) | ((w8 & 0xFF00) << 8) | ((w8 & 0xFF0000) >> 8) | ((w8 & 0xFF000000) >> 24)
    w8 = ((w10 & 0xFF) << 24) | ((w10 & 0xFF00) << 8) | ((w10 & 0xFF0000) >> 8) | ((w10 & 0xFF000000) >> 24)

    if flag != 0:
        w11 = 0x9E3779B9  # MOV W11, #0x79B9 + MOVK W11, #0x9E37,LSL#16
        w13 = 0x3C6EF372  # MOV W13, #0xF372 + MOVK W13, #0x3C6E,LSL#16
        w10 = 0           # MOV W10, WZR
        w12 = 0           # MOV W12, WZR

        while w12 < flag:
            # AND W14, W10, #3
            w14 = w10 & 3

            # EOR W15, W10, W11
            w15 = w10 ^ w11

            # AND W16, W13, W10,LSL#1
            w16 = w13 & ((w10 << 1) & 0xFFFFFFFF)

            # LDR W14, [X0,W14,UXTW#2]
            w14 = rand[w14]

            # EOR W17, W14, W10
            w17 = w14 ^ w10

            # ORR W14, W14, W10
            w14 = w14 | w10

            # ADD W10, W16, W15
            w10 = (w16 + w15) & 0xFFFFFFFF

            # LSR W15, W8, #5
            w15 = w8 >> 5

            # UBFX W16, W10, #0xB, #2
            w16 = (w10 >> 11) & 3

            # EOR W15, W15, W8,LSL#4
            w15 = w15 ^ ((w8 << 4) & 0xFFFFFFFF)

            # LSL W14, W14, #1
            w14 = (w14 << 1) & 0xFFFFFFFF

            # ADD W15, W15, W8
            w15 = (w15 + w8) & 0xFFFFFFFF

            # SUB W14, W14, W17
            w14 = (w14 - w17) & 0xFFFFFFFF

            # EOR W14, W14, W15
            w14 = w14 ^ w15

            # LDR W15, [X0,W16,UXTW#2]
            w15 = rand[w16]

            # ADD W9, W14, W9
            w9 = (w14 + w9) & 0xFFFFFFFF

            # LSL W16, W12, #1
            w16 = (w12 << 1) & 0xFFFFFFFF

            # LSL W14, W9, #4
            w14 = (w9 << 4) & 0xFFFFFFFF

            # EOR W12, W12, #0xFFFFFFFE
            w12 = w12 ^ 0xFFFFFFFE

            # EOR W14, W14, W9,LSR#5
            w14 = w14 ^ (w9 >> 5)

            # ORR W16, W16, #2
            w16 = w16 | 2

            # ADD W14, W14, W9
            w14 = (w14 + w9) & 0xFFFFFFFF

            # ADD W15, W15, W10
            w15 = (w15 + w10) & 0xFFFFFFFF

            # EOR W14, W14, W15
            w14 = w14 ^ w15

            # ADD W12, W12, W16
            w12 = (w12 + w16) & 0xFFFFFFFF

            # ADD W8, W14, W8
            w8 = (w14 + w8) & 0xFFFFFFFF

            # ADD W12, W12, #1
            w12 = (w12 + 1) & 0xFFFFFFFF

    result = bytearray(8)

    result[0] = (w9 >> 24) & 0xFF  # LSR W10, W9, #0x18 + STRB W10, [X2]
    result[1] = (w9 >> 16) & 0xFF  # LSR W11, W9, #0x10 + STRB W11, [X2,#1]
    result[2] = (w9 >> 8) & 0xFF   # LSR W12, W9, #8 + STRB W12, [X2,#2]
    result[3] = w9 & 0xFF          # STRB W9, [X2,#3]
    result[4] = (w8 >> 24) & 0xFF  # LSR W10, W8, #0x18 + STRB W10, [X2,#4]
    result[5] = (w8 >> 16) & 0xFF  # LSR W11, W8, #0x10 + STRB W11, [X2,#5]
    result[6] = (w8 >> 8) & 0xFF   # LSR W9, W8, #8 + STRB W9, [X2,#6]
    result[7] = w8 & 0xFF          # STRB W8, [X2,#7]

    result_hex = binascii.hexlify(result).decode('utf-8')
    print(f"sub4010 返回值: {result_hex}")
    return result_hex

def sub_330C(data, size):
    return 0

if __name__ == "__main__":
    input_hex = "020004369e6fbcb40c00010101010101"
    v42_hex = "01010101a3e1eaf4"
    rand_hex = "01010101010101010101010101010101"
    convert_function(input_hex,v42_hex, 0x10, rand_hex)
\```

输出结果与我们上面分析的能对上, 打完收工~

\```
参数: 020004369e6fbcb40c00010101010101
v11: 16
小算法1: 030105373d8e5640
本次处理input: 020004369e6fbcb4
异或结果: 030105373d8e5640
sub4010参数: 030105373d8e5640
sub4010 返回值: 1edc84501dc38389
v11: 32
小算法1: 12dc85511cc28288
本次处理input: 0c00010101010101
异或结果: 12dc85511cc28288
sub4010参数: 12dc85511cc28288
sub4010 返回值: 851f3b5607004e62
\```

# 整体思路

1.根据ida来梳理代码的调用流程和大体算法

2.unidbg来动态调试和trace 出汇编代码, trace read跟踪参数, trace write跟踪结果, debug断点用来查看寄存器和参数等等, trace code用来查看汇编

3.根据汇编代码来还原小算法(因为ida的伪代码直接扣会出错, 浪费时间)

欢迎有做mt, ct, qunar的各位佬 一起多交流:)
![image](https://bbs.kanxue.com/upload/attach/202510/846973_UR4PWE6NDHFGBQ4.webp)

---

# 回复

## 回复 by Wh1tebird (#2)

*2025-10-9 16:41*

学习

## 回复 by 寻梦之璐 (#3)

*2025-10-9 17:51*

1

## 回复 by mb_uvyukvot (#4)

*2025-10-9 18:36*

666

## 回复 by k4y0z (#5)

*2025-10-9 18:39*

666

## 回复 by mb_asiwnxyv (#6)

*2025-10-9 19:12*

666

## 回复 by 铭天星 (#7)

*2025-10-9 21:01*

tql

## 回复 by 9494 (#8)

*2025-10-9 21:38*

为你点赞！

## 回复 by wx_huhu_859 (#9)

*2025-10-9 21:56*

11

## 回复 by wx_插曲 (#10)

*2025-10-9 22:51*

大佬牛逼

## 回复 by mb_clkpejqc (#11)

*2025-10-9 23:25*

![image](https://bbs.kanxue.com/view/img/face/002.gif)

## 回复 by kingking888 (#12)

*2025-10-9 23:48*

666

## 回复 by mb_ldbucrik (#13)

*2025-10-9 23:52*

感谢分享

## 回复 by tubecityman (#14)

*2025-10-10 00:24*

学习下。

## 回复 by mb_lchjcnyn (#15)

*2025-10-10 00:50*

>
> [tubecityman](https://bbs.kanxue.com/user-967800.htm)
>
>  学习下。
>
>

学会了记得教我哈

## 回复 by bisoso (#16)

*2025-10-10 03:17*

学习下。

## 回复 by 星落黎明 (#17)

*2025-10-10 05:45*

感谢分享

## 回复 by mb_ykavguun (#18)

*2025-10-10 08:01*

12111

## 回复 by matrump (#19)

*2025-10-10 09:36*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by xifgg (#20)

*2025-10-10 09:59*

66

## 回复 by mb_xjdhrmck (#21)

*2025-10-10 10:19*

6666

## 回复 by mb_pmgifpme (#22)

*2025-10-10 10:46*

1

## 回复 by 黑屏 (#23)

*2025-10-10 11:01*

666

## 回复 by iBa0 (#24)

*2025-10-10 11:38*

111

## 回复 by KanXue_NG (#25)

*2025-10-10 15:31*

666

## 回复 by Imxz (#26)

*2025-10-10 16:58*

牛蛙

## 回复 by hacker521 (#27)

*2025-10-10 17:20*

想看下风控参数

## 回复 by mb_cbgtaveo (#28)

*2025-10-10 17:39*

6666666

## 回复 by 夫人十八岁 (#29)

*2025-10-10 19:46*

感谢分享

## 回复 by 青椒土豆 (#30)

*2025-10-10 20:20*

666

## 回复 by 祝枝山 (#31)

*2025-10-11 13:53*

678

## 回复 by mb_mrjjcxgk (#32)

*2025-10-11 14:57*

666

## 回复 by A冷忆 (#33)

*2025-10-11 16:56*

学习

## 回复 by 黄石 (#34)

*2025-10-11 17:19*

666

## 回复 by 嘎嘎真的很棒 (#35)

*2025-10-11 23:36*

感谢你分享这么好的资源！

## 回复 by wx_Huber Barrientos (#36)

*2025-10-11 23:54*

为你点赞！

## 回复 by 暴强 (#37)

*2025-10-12 16:51*

学习下！！！

## 回复 by muskccc (#38)

*2025-10-13 11:33*

1

## 回复 by AHook (#39)

*2025-10-13 12:02*

666

## 回复 by yangshuang (#40)

*2025-10-13 19:42*

111

## 回复 by MsScotch (#41)

*2025-10-13 20:17*

mark

## 回复 by YAR (#42)

*2025-10-13 20:48*

666

## 回复 by 哈。 (#43)

*2025-10-14 00:42*

9999999

## 回复 by 不具名的悲伤 (#44)

*2025-10-14 10:53*

6

## 回复 by mb_cizqyhuh (#45)

*2025-10-14 15:45*

分析得很透彻！unidbg调试和算法还原的步骤讲解通俗易懂，对逆向很有帮助！我把关键点整理成了[思维导图](https://www.anygraphanywhere.com/automap/mindmap.html?link=1760428929777-1760428929777)，方便查阅！

![image](https://bbs.kanxue.com/upload/attach/202510/1040915_B87ZC7R4VTB6NT7.webp)

## 回复 by mb_fidppcok (#46)

*2025-10-14 20:40*

学习

## 回复 by 小扒菜 (#47)

*2025-10-14 20:41*

666

## 回复 by edisonhu (#48)

*2025-10-14 21:42*

66

## 回复 by mb_oxelgdar (#49)

*2025-10-15 10:55*

太牛了吧

## 回复 by System's (#50)

*2025-10-15 11:04*

66666

## 回复 by mb_oxchypds (#51)

*2025-10-15 11:40*

1

## 回复 by mb_lakweznz (#52)

*2025-10-17 18:55*

9999

## 回复 by luckbbs (#53)

*2025-10-18 08:27*

666

## 回复 by TopDbg (#54)

*2025-10-18 13:21*

111

## 回复 by mb_xxeouezk (#55)

*2025-10-20 15:33*

666

## 回复 by wx_好饿想吃肉 (#56)

*2025-10-20 18:12*

666

## 回复 by 呼吸24K纯氧 (#57)

*2025-10-21 10:53*

666

## 回复 by Ace_Heng (#58)

*2025-10-21 21:05*

66666

## 回复 by Hawcett (#59)

*2025-10-23 16:30*

6666，论坛有你更精彩

## 回复 by 4Chan (#60)

*2025-10-24 14:33*

666

## 回复 by 蟑螂一号 (#61)

*2025-10-24 14:59*

666

## 回复 by 梨树生果 (#62)

*2025-10-24 18:14*

666

## 回复 by huangjw (#63)

*2025-10-24 18:55*

牛逼

## 回复 by MaYil (#64)

*2025-10-24 19:16*

感谢分享

## 回复 by mb_frspcrqz (#65)

*2025-10-25 12:15*

666

## 回复 by xeiyu (#66)

*2025-10-26 04:10*

666

## 回复 by mb_cqcrdwgm (#67)

*2025-10-27 16:25*

666

## 回复 by mb_mrjjcxgk (#68)

*2025-10-27 17:11*

666

## 回复 by sklww (#69)

*2025-10-27 17:35*

1

## 回复 by mb_yqgamfux (#70)

*2025-10-28 10:02*

![image](https://bbs.kanxue.com/view/img/face/003.gif)666

## 回复 by mb_ssnabqqf (#71)

*2025-10-28 10:16*

66666

## 回复 by Mr.He (#72)

*2025-10-28 10:34*

6666

## 回复 by cnhuaWu (#73)

*2025-11-1 14:13*

66666

## 回复 by hmlyn (#74)

*2025-11-2 15:24*

666666

## 回复 by fenfei331 (#75)

*2025-11-2 16:06*

666

## 回复 by 秦小海 (#76)

*2025-11-13 14:53*

11

## 回复 by _Tomorrow (#77)

*2025-11-13 23:19*

666

## 回复 by uni7corn (#78)

*2025-11-14 00:03*

6666

## 回复 by wx_听书人 (#79)

*2025-11-15 19:40*

666

## 回复 by 暗香沉浮 (#80)

*2025-11-15 21:51*

1

## 回复 by kekao (#81)

*2025-11-24 12:22*

感谢分享

## 回复 by LuciferArmy (#82)

*2025-11-26 15:55*

111

## 回复 by AK1988DA (#83)

*2025-11-27 15:28*

2

## 回复 by rebeksh (#84)

*2025-11-28 12:25*

666

## 回复 by fenfei331 (#85)

*2025-12-2 16:36*

666

## 回复 by mb_ffsfxcfz (#86)

*2025-12-6 01:57*

111

## 回复 by git_34874ucupucup8991-lgtm (#87)

*2025-12-21 11:02*

great

## 回复 by xianhuimin (#88)

*2025-12-22 20:08*

感谢分享

## 回复 by goongoon (#89)

*2026-1-5 17:27*

6666

## 回复 by mb_nggigxxl (#90)

*2026-1-6 08:25*

![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by mb_klyhhlcc (#91)

*2026-1-16 17:47*

1

## 回复 by mb_gcjwsflo (#92)

*2026-1-16 17:52*

666

## 回复 by mb_qimctavn (#93)

*2026-1-16 18:25*

6

## 回复 by CheRevir (#94)

*2026-1-16 19:18*

6666

## 回复 by Diana111 (#95)

*2026-1-19 23:29*

有大佬想合作的吗？一起去变现

## 回复 by SInnon (#96)

*2026-1-24 06:28*

666666

## 回复 by mb_uzmffdbw (#97)

*2026-2-3 14:34*

666

## 回复 by mb_fglogyec (#98)

*2026-2-7 13:18*

6666

## 回复 by Superoot (#99)

*2026-2-8 14:27*

感谢分享

## 回复 by 小今朝 (#100)

*2026-2-9 17:28*

666

## 回复 by mb_ysikfhxt (#101)

*2026-2-9 22:21*

1

## 回复 by git_41224nguyentruong190 (#102)

*2026-2-11 02:05*

66666

## 回复 by mb_npsajqlx (#103)

*2026-2-11 11:24*

6

## 回复 by mb_lgbrcvmf (#104)

*2026-2-12 14:08*

666

## 回复 by kccp (#105)

*2026-2-12 14:34*

6

## 回复 by mb_hwxdqfhi (#106)

*2026-2-13 20:05*

666

## 回复 by git_79771lunchaohe (#107)

*2026-2-23 03:46*

666

## 回复 by Crack999 (#108)

*2026-3-2 10:58*

666

## 回复 by fengvmu (#109)

*2026-3-4 10:15*

666

## 回复 by tjytjy (#110)

*2026-3-4 14:46*

666

## 回复 by wx_lll_652 (#111)

*2026-3-4 15:24*

6666666

## 回复 by hekes (#112)

*2026-3-4 15:30*

看看

## 回复 by 小尘0000 (#113)

*2026-3-4 18:01*

666

## 回复 by YooHaa (#114)

*2026-3-4 18:52*

666

## 回复 by 3倍アイスクリーム! (#115)

*2026-3-4 20:23*

前来学习

## 回复 by mb_peeqldfc (#116)

*2026-3-6 14:57*

666

## 回复 by lizhenzhe (#117)

*2026-3-6 15:23*

111

## 回复 by 水瓶 (#118)

*2026-3-6 19:02*

6666666666666

## 回复 by 水瓶 (#119)

*2026-3-6 19:12*

这个是穿山甲的请求体加密算法吧，其实就里面的流程复杂一点，移位和异或和排序等，里面就只有一个魔改了轮数的xxtea算法

## 回复 by kelvin_IDA (#120)

*2026-3-10 04:01*

6666

## 回复 by mb_ybvqgbkl (#121)

*2026-3-10 15:44*

6666

## 回复 by GEKEZYX (#122)

*2026-3-10 16:55*

666

## 回复 by didiid (#123)

*2026-3-10 17:46*

666

## 回复 by mb_mlyojneh (#124)

*2026-3-10 17:51*

感谢分享

## 回复 by Thehepta (#125)

*2026-3-11 12:16*

1

## 回复 by SamPoson (#126)

*2026-3-21 14:41*

111

## 回复 by mb_ocblkbwi (#127)

*2026-4-2 10:04*

666

## 回复 by wx_丁丁丁 (#128)

*2026-4-13 23:53*

6666

## 回复 by kevin0_0 (#129)

*2026-4-27 18:24*

666

## 回复 by niama (#130)

*2026-5-6 11:25*

666

## 回复 by mb_qztkkwxt (#131)

*2026-5-9 10:36*

感谢分享

## 回复 by mb_yprlutlv (#132)

*2026-5-13 11:43*

1

## 回复 by sorry呀 (#133)

*2026-5-21 07:17*

666

## 回复 by hanjiefang (#134)

*2026-6-5 16:42*

1

## 回复 by git_69678tuantmtb (#135)

*2026-7-29 11:46*

666
