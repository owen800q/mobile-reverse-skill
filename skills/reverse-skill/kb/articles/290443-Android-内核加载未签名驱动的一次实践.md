---
title: '[原创] Android 内核加载未签名驱动的一次实践'
url: https://bbs.kanxue.com/thread-290443.htm
tid: 290443
author: 拉不利多
date: '2026-03-21'
tags: [Android安全, 原创, 基础理论, 逆向分析, 系统相关]
crawled_at: '2026-07-31T13:55:54+08:00'
replies: 4
---

# 前言

测试机型是 `Honor 50 SE` 内核版本是 `4.14.186` 已解锁 BootLoader 通过 Magisk 27 管理 root

前段时间需要测试 4 系内核的一个外设驱动,打算用这台机器,编译好了驱动才发现有签名校验.网上一搜几乎都是小米和一加的教程,大意就是,先用 `find_load_module.exe` 在内核中搜索 `load_module` 函数位置,然后用 ida 修补了其中的几行汇编就搞定了.无奈我手中的的二进制看上去和教程中的完全不一样,压根无从改起,只好自己动手,这才有了这篇文档

# 一 提取内核文件

1. 查看当前系统使用的槽位,我的是 `b`

```bash
getprop ro.boot.slot_suffix
```
2. 找到内核文件所在分区,在我这里 `boot_b` 对应的是 `/dev/block/sdc64`

```bash
ls -al /dev/block/by-name/ | grep boot
```
3. 复制分区镜像到当前目录下

```bash
dd if=/dev/block/sdc64 of=./boot.img
```
4. 在系统里找到 `magiskboot` 文件用于解包 `boot.img`, 我的是在 `/data/adb/magisk/magiskboot`, 如果是 `apk` 文件就从中提取 `libmagiskboot.so`

```bash
./magiskboot unpack ./boot.img
# 或
./libmagiskboot.so unpack ./boot.img
```
5. 得到的 `kernel` 文件就是本篇的主角

# 二 对照内核源代码修补

1. 从[官网](https://www.honor.com/global/opensource/)搜索对应的机型下载源码,解压后进到 `Code_Opensource/kernel` 找到 `kernel/module.c`, `load_module` 函数的相关代码基本上都在这里,下面贴一小段主要逻辑

```c
static int load_module(struct load_info *info, const char __user *uargs,
                       int flags)
{
        struct module *mod;
        long err;
        char *after_dashes;

        err = module_sig_check(info, flags);
        if (err)
                goto free_copy;

        err = elf_header_check(info);
        if (err)
                goto free_copy;

        /* Figure out module layout, and allocate all the memory. */
        mod = layout_and_allocate(info, flags);
        if (IS_ERR(mod)) {
                err = PTR_ERR(mod);
                goto free_copy;
        }

        audit_log_kern_module(mod->name);

        /* Reserve our place in the list. */
        err = add_unformed_module(mod);
        if (err)
                goto free_module;

#ifdef CONFIG_MODULE_SIG
        mod->sig_ok = info->sig_ok;
        if (!mod->sig_ok) {
                pr_notice_once("%s: module verification failed: signature "
                               "and/or required key missing - tainting "
                               "kernel\n", mod->name);
                add_taint_module(mod, TAINT_UNSIGNED_MODULE, LOCKDEP_STILL_OK);
        }
#endif

        ... 以下省略 ...
}
```

```c
static int module_sig_check(struct load_info *info, int flags)
{
        int err = -ENOKEY;
        const unsigned long markerlen = sizeof(MODULE_SIG_STRING) - 1;
        const void *mod = info->hdr;

        /*
         * Require flags == 0, as a module with version information
         * removed is no longer the module that was signed
         */
        if (flags == 0 &&
            info->len > markerlen &&
            memcmp(mod + info->len - markerlen, MODULE_SIG_STRING, markerlen) == 0) {
                /* We truncate the module to discard the signature */
                info->len -= markerlen;
                err = mod_verify_sig(mod, &info->len);
        }

        if (!err) {
                info->sig_ok = true;
                return 0;
        }

#ifdef CONFIG_HUAWEI_PROC_CHECK_ROOT
        saudit_log(MOD_SIGN, STP_RISK, 0, "result=%d,", err);
#endif

        /* Not having a signature is only an error if we're strict. */
        if (err == -ENOKEY && !sig_enforce)
                err = 0;

        return err;
}
```

 可以看到签名校验部分都在 `module_sig_check` 中,我一看这还不手拿把掐嘛, `nop` 掉一个 `bl` 指令就能收工啦
2. 打开 ida 后尝试搜索了几个字符串,很快就定为到了 `load_module`, 部分反汇编代码如下

```c
  v6 = a1;
  v575 = &off_0;
  v8 = (const char *)(a1 + 8);
  v7 = *(_QWORD *)(a1 + 8);
  if ( a3
    || (v10 = (const char **)(v6 + 16), v9 = *(_QWORD *)(v6 + 16), v9 < 0x1D)
    || *(_QWORD *)(v7 + v9 - 28) ^ 0x20656C75646F4D7ELL
     | *(_QWORD *)(v7 + v9 - 20) ^ 0x727574616E676973LL
     | *(_QWORD *)(v7 + v9 - 12) ^ 0x646E657070612065LL
     | *(unsigned int *)(v7 + v9 - 4) ^ 0xA7E6465LL )
  {
    v11 = -126;
LABEL_5:
    sub_68939C(10, 1, 0, "result=%d,", v11);
    v12 = v11;
    goto LABEL_6;
  }
  v4 = a2;
  v3 = v5;
  *v10 = (const char *)(v9 - 28);
  v11 = sub_2B82E0();
  if ( v11 )
    goto LABEL_5;
  v15 = *(_QWORD *)(v6 + 16);
  *(_BYTE *)(v6 + 76) = 1;
  if ( v15 < 0x40
    || (v16 = *(_DWORD **)v8, **(_DWORD **)v8 != 1179403647)
    || *((_WORD *)v16 + 8) != 1
    || *((_WORD *)v16 + 9) != 183
    || *((_WORD *)v16 + 29) != 64
    || (v17 = *((_QWORD *)v16 + 5), v18 = v15 > v17, v19 = v15 - v17, !v18)
    || v19 < (unsigned __int64)*((unsigned __int16 *)v16 + 30) << 6 )
  {
    v12 = -8;
    goto LABEL_6;
  }
```

 emm...这种情况怎么说呢,算不上好但也不是无解,我尝试了直接跳转当然是失败了哈哈.编译内核时 `module_sig_check` 甚至 `mod_verify_sig` 都被内联进了 `load_module`, 没有函数调用就没有弹栈寄存器恢复现场,所以只好手动分析汇编,看看哪些寄存器会被后面的代码用到
3. 机器码如下

 ![image](https://bbs.kanxue.com/upload/attach/202603/1066062_D2VNZDKQ5XDPUAR.webp)

 好在编译器没给我更上强度,在一番试错后也是终于顺利进入系统,只需做如下修改

| 文件偏移 | 原指令 | 原机器码 | 新指令 | 新机器码 | 作用 |
|-|-|-|-|-|-|
| 0x2B267C | CBNZ W2,loc_2B26FC | 02 04 00 35 | NOP | 1F 20 03 D5 | 绕过 flags 校验 |
| 0x2B2688 | CMP X8,#0x1D | 1F 75 00 F1 | MOV X22,X1 | F6 03 01 AA | 保存必要寄存器值 |
| 0x2B268C | B.CC loc_2B26FC | 83 03 00 54 | MOV X20,X30 | F4 03 1E AA | 同上 |
| 0x2B2690 | ADD X9,X0,X8 | 09 00 08 8B | B 0x2B2780 | 3C 00 00 14 | 跳过验证函数 |

# 三 回刷内核

1. 保持 `kernel` 文件名不变放回原来的位置打包

```bash
./magiskboot repack ./boot.img
```
2. 得到 `new-boot.img` 后写入原分区

```bash
dd if=./new-boot.img of=/dev/block/sdc64
```
3. 重启手机,如果失败了进不去系统,那就得用 `fastboot` 刷回原镜像

```bash
fastboot flash boot boot.img
```

# 四 编译内核驱动

这部分和其他的 4 系内核差不多,简单说明一下,除了上面用到的内核源代码,还得下载 gcc 和 clang 工具链,地址如下

- gcc: https://github.com/LineageOS/android_prebuilts_gcc_linux-x86_aarch64_aarch64-linux-android-4.9
- clang: https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+archive/refs/heads/android12-release/clang-r383902.tar.gz

编译时最好是用 `Ubuntu 20.04 x64` 系统,我没有用机器自带的 `/proc/config.gz` 也成功了,只编译内核模块的话应该没那么多讲究

```bash
MAKE_ARGS='ARCH=arm64 SUBARCH=arm64 CLANG_TRIPLE=aarch64-linux-gnu- CC=clang LD=ld.lld CROSS_COMPILE=aarch64-linux-android- O=out'
export PATH="/home/ubuntu/clang/bin:/home/ubuntu/gcc/bin:$PATH"
cd Code_Opensource/kernel/
make $MAKE_ARGS merge_full_k6877v1_64_defconfig
make $MAKE_ARGS modules_prepare
```

上面的脚本 `PATH` 和 `defconfig` 按需修改就行,测试代码如下

`Makefile`

```makefile
obj-m += hello.o
KDIR := /home/ubuntu/Code_Opensource/kernel/out
MAKE_ARGS := ARCH=arm64 CC=clang LD=ld.lld CLANG_TRIPLE=aarch64-linux-gnu- CROSS_COMPILE=aarch64-linux-android-

all:
    $(MAKE) -C $(KDIR) M=$(PWD) $(MAKE_ARGS) modules

clean:
    $(MAKE) -C $(KDIR) M=$(PWD) $(MAKE_ARGS) clean
```

`hello.c`

```c
#include &lt;linux/module.h&gt;
static int __init hello_init(void) {
    pr_info("Test: Hello, world!\n");
    return 0;
}
static void __exit hello_exit(void) {
    pr_info("Test: Goodbye, world!\n");
}
module_init(hello_init);
module_exit(hello_exit);
MODULE_LICENSE("GPL");
```

`KDIR` 是编译好的头文件目录,如果是新开的终端要重新添加 `PATH`, 将以上两个文件放到同一个目录下 `make` 即可

完事收工!

---

# 回复

## 回复 by iBa0 (#2)

*2026-3-22 10:31*

学到了哈哈

## 回复 by huangjw (#3)

*2026-3-26 09:22*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by mb_zcfhleoj (#4)

*2026-4-22 16:31*

感谢分享

## 回复 by djog (#5)

*2026-6-30 00:20*

好东西..学习了..
