---
title: '[原创] libmsaoaidsec.so 过检测'
url: https://bbs.kanxue.com/thread-287058.htm
tid: 287058
author: wx_小友
date: '2025-06-02'
tags: [Android安全, 原创, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:09:24+08:00'
replies: 22
---

在逆向某视频APP时，发现有对frida和hook java 层的检测，对于frida 的过检测，我使用了魔改后的frida 。
在hook native层的时候，没什么问题，但是只要我去hook java层，就会退出，即使hook java层时，什么都不写，只要有

Java.perform(); 就直接退出。
开始我是想看看程序是在哪里退出的，通过strace，发现app对/proc/self/status 和 /proc/self/task/<tid>/status 、/proc/self/map 等都有检测。

当我对/proc/self/status和/proc/self/task/<tid>/status 进行模拟。脚本如下：

```
const FAKE_STATUS = "TracerPid:\t0\nUid:\t10086\nGid:\t10086\n";

// Hook open + read 组合拳
const openPtr = Module.findExportByName(null, 'open');
const readPtr = Module.findExportByName(null, 'read');
const closePtr = Module.findExportByName(null, 'close');

const fdMap = new Map();

Interceptor.attach(openPtr, {
    onEnter: function(args) {
        const path = args[0].readCString();
        if (path && path.match(/\/proc\/\d+\/status/)) {
            console.log(`[!] 拦截到 status 打开: ${path}`);
            this.shouldHook = true;
        }
    },
    onLeave: function(retval) {
        if (this.shouldHook) {
            const fd = retval.toInt32();
            fdMap.set(fd, true);
        }
    }
});

Interceptor.attach(readPtr, {
    onEnter: function(args) {
        this.fd = args[0].toInt32();
        if (fdMap.has(this.fd)) {
            this.buf = args[1];
            this.size = args[2].toInt32();
        }
    },
    onLeave: function(retval) {
        if (fdMap.has(this.fd)) {
            // 写入伪造数据
            const fakeData = Memory.allocUtf8String(FAKE_STATUS);
            Memory.writeByteArray(this.buf, fakeData.readByteArray(FAKE_STATUS.length));
            retval.replace(FAKE_STATUS.length);
            fdMap.delete(this.fd);
        }
    }
});
```

这个时候还是会被检测，我想是模拟的文件不够真实，然后选择直接对目标文件复制，修改 TracerPid: 0 ，脚本如下：

```
function fakeStatus() {
  var fdMap = new Map();
  var openatAddr = Module.findExportByName(null, "openat");

  if (!openatAddr) {
    throw new Error("openat function not found in libc.so");
  }
  const syscallOpen = Module.findExportByName(null, "open");

  var firstOpenat = false;

  Interceptor.attach(openatAddr, {
    onEnter: function (args) {
      var path = ptr(args[1]).readCString();
      this.path = path;
      // 检测目标文件路径
      if (
        this.path &&
        this.path.startsWith("/proc/") &&
        this.path.includes("/status")
      ) {
        console.log(`openat [+] Intercepted access to: ${this.path}`);
        this.shouldHook = true;
        this.fd = fakeFile(this.path);
      }

      if (!firstOpenat) {
        firstOpenat = true;
        var log = Thread.backtrace(this.context, Backtracer.ACCURATE).map(DebugSymbol.fromAddress).join("\n");
        console.log("log: ", log);
      }
    },
    onLeave: function (retval) {
      if (this.shouldHook) {
        fdMap.set(this.fd, retval.toInt32());
        this.shouldHook = false;
        console.log(
          `[+] Intercepted openat for: ${
            this.path
          }, originFd: ${retval.toInt32()}, fd: ${this.fd}`
        );
        retval.replace(this.fd); // 替换返回值为伪造的文件描述符
      }
    },
  });

  Interceptor.attach(syscallOpen, {
    onEnter: function (args) {
      const path = args[0].readCString();
      this.path = path;
      if (path && path.startsWith("/proc/") && path.includes("/status")) {
        console.log(`open [+] Intercepted access to: ${this.path}`);
        this.shouldFilter = true;
        this.fd = fakeFile(this.path);
      }
    },
    onLeave: function (retval) {
      if (this.shouldFilter) {
        this.shouldFilter = false;
        fdMap.set(this.fd, retval.toInt32());
        console.log(
          `[+] Intercepted open for: ${
            this.path
          }, originFd: ${retval.toInt32()}, fd: ${this.fd}`
        );
        retval.replace(this.fd); // 替换返回值为伪造的文件描述符
      }
    },
  });

  function fakeFile(path) {
    try {
      var content = File.readAllText(path);
      let lines = content.split("\n");
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].startsWith("TracerPid:")) {
          lines[i] = "TracerPid:\t0"; // 伪造 TracerPid
        } else if (lines[i].startsWith("Name:")) {
          console.log("Name: ", lines[i]);
        }
      }

      content = lines.join("\n");
      // 使用 memfd_create 创建匿名内存文件
      const memfd_create = new NativeFunction(
        Module.findExportByName(null, "memfd_create"),
        "int",
        ["pointer", "int"]
      );

      // 创建内存文件
      const namePtr = Memory.allocUtf8String(path.replace("/", "_"));
      const fd = memfd_create(namePtr, 0);

      if (fd < 0) {
        console.error("Failed to create memory file descriptor");
        return -1;
      }
      // 写入伪造内容到内存文件
      const write = new NativeFunction(
        Module.findExportByName(null, "write"),
        "int",
        ["int", "pointer", "int"]
      );
      const contentPtr = Memory.allocUtf8String(content);
      write(fd, contentPtr, content.length);
        console.log(`[+] Virtual file created at fd: ${fd}`);

      return fd;
    } catch (e) {
      console.error("Failed to read/write status file:", e);
    }
    return -1;
  }

  const syscallClose = Module.findExportByName(null, "close");
  const closeFunc = new NativeFunction(syscallClose, "int", ["int"]);
  Interceptor.attach(syscallClose, {
    onEnter: function (args) {
      this.fd = args[0].toInt32();
      if (fdMap.has(this.fd)) {
        var originFd = fdMap.get(this.fd);
        closeFunc(originFd);
        // console.log(`[+] Intercepted close for originFd: ${originFd} fd: ${this.fd}`);
        fdMap.delete(this.fd); // 删除伪造的文件描述符
      }
    },
  });
}
fakeStatus();
```

此时，可以执行strace 指令了，   但是每次只能持续5-10秒钟，app就会被强制退出。原因不详，此时还是无法 hook java层，我怀疑是对/proc/self/maps的检测才导致的java hook 失败。

这时，我对maps 的文件进行copy ，放到/sdcard/download 目录下，然后慢慢比较有什么差别，但是没看出来。
还有种可能，是对/proc/self/task/tid/status 中的Name有检测，可能会有线程名有问题，所以我有打印出了每个task的Name ，没有任何发现，里面的名字没有什么问题，和正常情况下的名字差不多，没有frida 和其他异常的名称。

此时思路完全卡死，没有别的办法了。
然后我在网上找过这个SO的方法，比如在pthread 中nop掉线程，或者直接nop掉调用这些pthread 的方法。这些方法都会造成app 假死。 app 打开后就卡死在首页了。（找到的方法：0x1C544      0x1B8D4     0x26E5C）三个方法。

我只能在pthread中使用Stalker.follow 看看有哪些指令，看看有什么问题。

```
0x7a0a7557e4:mov x1, x21
0x7a0a7557e8:bl #0x7a0a755c04
0x7a0a755c04:sub sp, sp, #0x60
0x7a0a755c08:stp x29, x30, [sp, #0x30]
0x7a0a755c0c:str x21, [sp, #0x40]
0x7a0a755c10:stp x20, x19, [sp, #0x50]
0x7a0a755c14:add x29, sp, #0x30
0x7a0a755c18:mrs x20, tpidr_el0
0x7a0a755c1c:ldr x8, [x20, #0x28]
0x7a0a755c20:mov x19, x1
0x7a0a755c24:cmp x1, #0x7f
0x7a0a755c28:stur x8, [x29, #-8]
0x7a0a755c2c:b.hi #0x7a0a755c3c
0x7a0a755c30:add x8, x0, x19, lsl #3
0x7a0a755c34:add x0, x8, #8
0x7a0a755c38:b #0x7a0a755c60
0x7a0a755c60:ldr x8, [x20, #0x28]
0x7a0a755c64:ldur x9, [x29, #-8]
0x7a0a755c68:cmp x8, x9
0x7a0a755c6c:b.ne #0x7a0a755d28
0x7a0a755c70:ldp x20, x19, [sp, #0x50]
0x7a0a755c74:ldr x21, [sp, #0x40]
0x7a0a755c78:ldp x29, x30, [sp, #0x30]
0x7a0a755c7c:add sp, sp, #0x60
0x7a0a755c80:ret
0x7a0a7557ec:cbz x0, #0x7a0a755804
0x7a0a7557f0:ldaxr x21, [x0]
0x7a0a7557f4:cmp x21, x20
0x7a0a7557f8:b.ne #0x7a0a755814
0x7a0a7557fc:stlxr w8, x22, [x0]
0x7a0a755800:cbnz w8, #0x7a0a7557f0
0x7a0a7557fc:stlxr w8, x22, [x0]
0x7a0a755800:cbnz w8, #0x7a0a7557f0
0x7a0a7557f0:ldaxr x21, [x0]
0x7a0a7557f4:cmp x21, x20
0x7a0a7557f8:b.ne #0x7a0a755814
0x7a0a755804:ldp x20, x19, [sp, #0x20]
0x7a0a755808:ldp x22, x21, [sp, #0x10]
0x7a0a75580c:ldp x29, x30, [sp], #0x30
0x7a0a755810:ret
0x7a0a75393c:add x0, x19, #0x18
0x7a0a753940:mov x1, xzr
0x7a0a753944:str xzr, [x19, #0x10a8]
0x7a0a753948:stp xzr, xzr, [x19, #8]
0x7a0a75394c:bl #0x7a0a7b7200
0x7a0a7b7200:adrp x16, #0x7a0a7bb000
0x7a0a7b7204:ldr x17, [x16, #0xf38]
0x7a0a7b7208:add x16, x16, #0xf38
0x7a0a7b720c:br x17
0x7a0a7b374c:movi v0.2d, #0000000000000000
0x7a0a7b3750:str xzr, [x0, #0x20]
0x7a0a7b3754:stp q0, q0, [x0]
0x7a0a7b3758:cbnz x1, #0x7a0a7b3768
0x7a0a7b375c:strh wzr, [x0]
0x7a0a7b3760:mov w0, wzr
0x7a0a7b3764:ret
0x7a0a753950:b #0x7a0a753958
0x7a0a753958:mov x0, x19
0x7a0a75395c:ldp x20, x19, [sp, #0x10]
0x7a0a753960:ldp x29, x30, [sp], #0x20
0x7a0a753964:ret
0x76f70aefe4:cbz x0, #0x76f70af11c
0x76f70aefe8:mov x19, x0
0x76f70aefec:bl #0x76f709b170
0x76f709b170:adrp x16, #0x76f70da000
0x76f709b174:ldr x17, [x16, #0xd58]
0x76f709b178:add x16, x16, #0xd58
0x76f709b17c:br x17
0x7a0a753968:stp x29, x30, [sp, #-0x30]!
0x7a0a75396c:str x21, [sp, #0x10]
0x7a0a753970:stp x20, x19, [sp, #0x20]
0x7a0a753974:mov x29, sp
0x7a0a753978:cbz x0, #0x7a0a753a20
0x7a0a75397c:add x19, x0, #0x18
0x7a0a753980:mov x20, x0
0x7a0a753984:mov x0, x19
0x7a0a753988:bl #0x7a0a7b6c20
0x7a0a7b6c20:adrp x16, #0x7a0a7bb000
0x7a0a7b6c24:ldr x17, [x16, #0xc48]
0x7a0a7b6c28:add x16, x16, #0xc48
0x7a0a7b6c2c:br x17
0x7a0a7b37dc:stp x29, x30, [sp, #-0x10]!
0x7a0a7b37e0:mov x29, sp
0x7a0a7b37e4:ldrh w8, [x0]
0x7a0a7b37e8:ubfx w9, w8, #0xe, #2
0x7a0a7b37ec:and x8, x8, #0xffff
0x7a0a7b37f0:cbnz w9, #0x7a0a7b3830
0x7a0a7b37f4:and x8, x8, #0x2000
0x7a0a7b37f8:orr x9, x8, #1
0x7a0a7b37fc:ldaxrh w10, [x0]
0x7a0a7b3800:cmp w10, w8
0x7a0a7b3804:b.ne #0x7a0a7b381c
0x7a0a7b3808:stxrh w10, w9, [x0]
0x7a0a7b380c:cbnz w10, #0x7a0a7b37fc
0x7a0a7b3808:stxrh w10, w9, [x0]
0x7a0a7b380c:cbnz w10, #0x7a0a7b37fc
0x7a0a7b37fc:ldaxrh w10, [x0]
0x7a0a7b3800:cmp w10, w8
0x7a0a7b3804:b.ne #0x7a0a7b381c
0x7a0a7b3810:mov w0, wzr
0x7a0a7b3814:ldp x29, x30, [sp], #0x10
0x7a0a7b3818:ret
0x7a0a75398c:ldr x8, [x20, #8]
0x7a0a753990:cbz x8, #0x7a0a7539bc
0x7a0a7539bc:add x21, x20, #0x40
0x7a0a7539c0:ldr w0, [x20]
0x7a0a7539c4:mov w2, #0x1068
0x7a0a7539c8:mov x1, x21
0x7a0a7539cc:bl #0x7a0a79e1b0
0x7a0a79e1b0:mov x8, #0x3d
0x7a0a79e1b4:svc #0
0x7a0a79e1b8:cmn x0, #1, lsl #12
0x7a0a79e1bc:cneg x0, x0, hi
0x7a0a79e1c0:b.hi #0x7a0a79d820
0x7a0a79e1c4:ret
0x7a0a7539d0:cmn w0, #1
0x7a0a7539d4:b.ne #0x7a0a7539ec
0x7a0a7539ec:cmp w0, #1
0x7a0a7539f0:b.lt #0x7a0a753a00
0x7a0a7539f4:mov w8, w0
0x7a0a7539f8:stp x8, x21, [x20, #8]
0x7a0a7539fc:b #0x7a0a753998
0x7a0a753998:ldrh w9, [x21, #0x10]
0x7a0a75399c:add x9, x21, x9
0x7a0a7539a0:str x9, [x20, #0x10]
0x7a0a7539a4:ldrh w9, [x21, #0x10]
0x7a0a7539a8:sub x8, x8, x9
0x7a0a7539ac:str x8, [x20, #8]
0x7a0a7539b0:ldr x8, [x21, #8]
0x7a0a7539b4:str x8, [x20, #0x10a8]
0x7a0a7539b8:b #0x7a0a753a04
0x7a0a753a04:mov x0, x19
0x7a0a753a08:bl #0x7a0a7b6c60
0x7a0a7b6c60:adrp x16, #0x7a0a7bb000
0x7a0a7b6c64:ldr x17, [x16, #0xc68]
0x7a0a7b6c68:add x16, x16, #0xc68
0x7a0a7b6c6c:br x17
0x7a0a7b3ce0:stp x29, x30, [sp, #-0x30]!
0x7a0a7b3ce4:stp x22, x21, [sp, #0x10]
0x7a0a7b3ce8:stp x20, x19, [sp, #0x20]
0x7a0a7b3cec:mov x29, sp
0x7a0a7b3cf0:ldrh w9, [x0]
0x7a0a7b3cf4:mov x19, x0
0x7a0a7b3cf8:ubfx w10, w9, #0xe, #2
0x7a0a7b3cfc:and x8, x9, #0x2000
0x7a0a7b3d00:cbnz w10, #0x7a0a7b3d6c
0x7a0a7b3d04:orr w9, w8, #2
0x7a0a7b3d08:ldxrh w10, [x19]
0x7a0a7b3d0c:stlxrh w11, w8, [x19]
0x7a0a7b3d10:cbnz w11, #0x7a0a7b3d08
0x7a0a7b3d04:orr w9, w8, #2
0x7a0a7b3d08:ldxrh w10, [x19]
0x7a0a7b3d0c:stlxrh w11, w8, [x19]
0x7a0a7b3d10:cbnz w11, #0x7a0a7b3d08
0x7a0a7b3d14:cmp w10, w9
0x7a0a7b3d18:b.ne #0x7a0a7b3e08
0x7a0a7b3e08:mov w0, wzr
0x7a0a7b3e0c:ldp x20, x19, [sp, #0x20]
0x7a0a7b3e10:ldp x22, x21, [sp, #0x10]
0x7a0a7b3e14:ldp x29, x30, [sp], #0x30
0x7a0a7b3e18:ret
0x7a0a753a0c:mov x0, x21
0x7a0a753a10:ldp x20, x19, [sp, #0x20]
0x7a0a753a14:ldr x21, [sp, #0x10]
0x7a0a753a18:ldp x29, x30, [sp], #0x30
0x7a0a753a1c:ret
0x76f70aeff0:cbz x0, #0x76f70af114
0x76f70aeff4:adrp x20, #0x76f70c3000
0x76f70aeff8:adrp x21, #0x76f70c3000
0x76f70aeffc:adrp x22, #0x76f70dc000
0x76f70af000:adrp x23, #0x76f70dc000
0x76f70af004:adrp x24, #0x76f70dc000
0x76f70af008:mov x25, x0
0x76f70af00c:add x20, x20, #0x5e5
0x76f70af010:add x21, x21, #0x5e4
0x76f70af014:add x22, x22, #0x30
0x76f70af018:add x28, sp, #0x18
0x76f70af01c:add x23, x23, #0x4a
0x76f70af020:add x24, x24, #0x56
0x76f70af024:add x0, sp, #0x218
0x76f70af028:mov w2, #0x200
0x76f70af02c:mov w1, wzr
0x76f70af030:bl #0x76f709aea0
0x76f709aea0:adrp x16, #0x76f70da000
0x76f709aea4:ldr x17, [x16, #0xbf0]
0x76f709aea8:add x16, x16, #0xbf0
0x76f709aeac:br x17
0x7a0a74d380:dup v0.16b, w1
0x7a0a74d384:add x4, x0, x2
0x7a0a74d388:cmp x2, #0x60
0x7a0a74d38c:b.hi #0x7a0a74d404
0x7a0a74d404:and w1, w1, #0xff
0x7a0a74d408:and x3, x0, #0xfffffffffffffff0
0x7a0a74d40c:str q0, [x0]
0x7a0a74d410:cmp x2, #0x100
0x7a0a74d414:ccmp w1, #0, #0, hs
0x7a0a74d418:b.eq #0x7a0a74d448
0x7a0a74d448:mrs x5, dczid_el0
0x7a0a74d44c:tbnz w5, #4, #0x7a0a74d41c
0x7a0a74d450:and w5, w5, #0xf
0x7a0a74d454:cmp w5, #4
0x7a0a74d458:b.ne #0x7a0a74d4a8
0x7a0a74d45c:str q0, [x3, #0x10]
0x7a0a74d460:stp q0, q0, [x3, #0x20]
0x7a0a74d464:and x3, x3, #0xffffffffffffffc0
0x7a0a74d468:stp q0, q0, [x3, #0x40]
0x7a0a74d46c:stp q0, q0, [x3, #0x60]
0x7a0a74d470:sub x2, x4, x3
0x7a0a74d474:sub x2, x2, #0x100
0x7a0a74d478:add x3, x3, #0x80
0x7a0a74d47c:nop
0x7a0a74d480:dc zva, x3
0x7a0a74d484:add x3, x3, #0x40
0x7a0a74d488:subs x2, x2, #0x40
0x7a0a74d48c:b.hi #0x7a0a74d480
0x7a0a74d480:dc zva, x3
0x7a0a74d484:add x3, x3, #0x40
0x7a0a74d488:subs x2, x2, #0x40
0x7a0a74d48c:b.hi #0x7a0a74d480
0x7a0a74d490:stp q0, q0, [x3]
0x7a0a74d494:stp q0, q0, [x3, #0x20]
0x7a0a74d498:stp q0, q0, [x4, #-0x40]
0x7a0a74d49c:stp q0, q0, [x4, #-0x20]
0x7a0a74d4a0:ret
0x76f70af034:add x25, x25, #0x13
0x76f70af038:mov x0, x25
0x76f70af03c:mov x1, x20
0x76f70af040:bl #0x76f709aab0
0x76f709aab0:adrp x16, #0x76f70da000
0x76f709aab4:ldr x17, [x16, #0x9f8]
0x76f709aab8:add x16, x16, #0x9f8
0x76f709aabc:br x17
0x7a0a74da40:eor x7, x0, x1
0x7a0a74da44:mov x10, #0x101010101010101
0x7a0a74da48:tst x7, #7
0x7a0a74da4c:b.ne #0x7a0a74dac8
0x7a0a74dac8:tst x0, #7
0x7a0a74dacc:b.eq #0x7a0a74daec
0x7a0a74dad0:ldrb w2, [x0], #1
0x7a0a74dad4:ldrb w3, [x1], #1
0x7a0a74dad8:cmp w2, #1
0x7a0a74dadc:ccmp w2, w3, #0, hs
0x7a0a74dae0:b.ne #0x7a0a74db1c
0x7a0a74dae4:tst x0, #7
0x7a0a74dae8:b.ne #0x7a0a74dad0
0x7a0a74db1c:sub x0, x2, x3
0x7a0a74db20:ret
0x76f70af044:cbz w0, #0x76f70af104
0x76f70af104:mov x0, x19
0x76f70af108:bl #0x76f709b170
0x7a0a7b37f4:and x8, x8, #0x2000
0x7a0a7b37f8:orr x9, x8, #1
0x7a0a7b37fc:ldaxrh w10, [x0]
0x7a0a7b3800:cmp w10, w8
0x7a0a7b3804:b.ne #0x7a0a7b381c
0x7a0a753994:ldr x21, [x20, #0x10]
0x7a0a753998:ldrh w9, [x21, #0x10]
0x7a0a75399c:add x9, x21, x9
0x7a0a7539a0:str x9, [x20, #0x10]
0x7a0a7539a4:ldrh w9, [x21, #0x10]
0x7a0a7539a8:sub x8, x8, x9
0x7a0a7539ac:str x8, [x20, #8]
0x7a0a7539b0:ldr x8, [x21, #8]
0x7a0a7539b4:str x8, [x20, #0x10a8]
0x7a0a7539b8:b #0x7a0a753a04
0x7a0a7539b8:b #0x7a0a753a04
0x7a0a7539b8:b #0x7a0a753a04
0x76f70af10c:mov x25, x0
0x76f70af110:cbnz x0, #0x76f70af024
0x76f70af024:add x0, sp, #0x218
0x76f70af028:mov w2, #0x200
0x76f70af02c:mov w1, wzr
0x76f70af030:bl #0x76f709aea0
```

经过指令和IDA中的对应方法对比，在IDA中有存在
![image](https://bbs.kanxue.com/upload/attach/202506/783296_SKDKN4NNE4BAD7U.webp)

__stack_chk_fail 的方法，在使用java hook后，会调用这个方法。
现在总结一下我之前做过的事情：
1、模拟/proc/self/status、/rpoc/self/task/<tid>/status     可以 strace 和 debug， 但是 只能运行不到一分钟。
2、模拟 /proc/self/maps  ， 这个事情上面没说，是因为我将正常运行的app的 maps 复制了好多份，然后再hook app，替换maps 的内容，app会直接死掉。
3、 pthread_create 时 nop 对应的方法， app 会卡死掉。
4、找到IDA中的 BL __stack_chk_fail   将之nop掉，会出现卡死。我怀疑是循环无法正常退出，导致死循环。

现在我应该找到前面提到的三个方法(**0x1C544      0x1B8D4     0x26E5C**)
对这三个方法查看调用方，并nop 掉 BL XXXX   ，但是还是卡死。

无奈，只好用 继续理第4点，查看这三个方法 哪些地方可能会死循环，将流程中不想被执行的地方都用NOP 替换。

最后从上述三个方法中的几个关键点NOP 后，程序正常运行了，不管是java层还是native层都可以hook了。

完整脚本如下。

```
function hookDlopen() {
  // 1. 获取链接器模块
  let linkerModule =
    Process.findModuleByName("linker64") || Process.findModuleByName("linker");
  if (!linkerModule) {
    console.error("[-] 链接器模块未加载");
    return;
  }
  console.log(`[+] 链接器模块基地址: ${linkerModule.base}`);

  // 2. 动态查找符号
  let android_dlopen_ext = null;
  let exports = linkerModule.enumerateExports();
  for (let exp of exports) {
    if (
      exp.name.includes("do_dlopen") ||
      exp.name.includes("android_dlopen_ext") ||
      exp.name.includes("__dl__Z9do_dlopen")
    ) {
      // 匹配修饰名
      android_dlopen_ext = exp.address;
      console.log(`[+] 匹配到符号: ${exp.name} -> ${android_dlopen_ext}`);
      break;
    }
  }

  // 3. 备选方案：手动偏移
  if (!android_dlopen_ext) {
    const OFFSET = 0x3ba00; // 需根据设备调整
    android_dlopen_ext = linkerModule.base.add(OFFSET);
    console.log(`[!] 使用手动偏移地址: ${android_dlopen_ext}`);
  }

  const sleep = new NativeFunction(
    Module.findExportByName("libc.so", "sleep"),
    "int",
    ["int"]
  );

  // 4. 挂钩函数
  if (android_dlopen_ext) {
    Interceptor.attach(android_dlopen_ext, {
      onEnter: async function (args) {
        let path = args[0].readCString();
        console.log(`[dlopen] 加载库: ${path}`);
        this.path = path;
        if (path != null && path.indexOf("libmsaoaidsec.so") >= 0) {
          console.log("onEnter [+] 目标库已加载，开始Hook...");
          setTimeout(() => {
            var secmodule = Process.findModuleByName("libmsaoaidsec.so");
            if (secmodule) {
                console.log("setImmediate [+] 目标库已加载，开始Hook...");
             // hook_sub_1b924(secmodule);
            } else {
              console.error("[-] 未找到目标库 libmsaoaidsec.so");
            }
          }, 1000);

        }
      },
      onLeave: function (retval) {
        if (this.path && this.path.includes("libmsaoaidsec.so")) {
          console.log("onLeave [+] 目标库已加载，开始Hook...");
          // hook_library_init();
        }
      },
    });
  } else {
    console.error("[-] 无法定位do_dlopen函数");
  }
}

function hook_native_addr(secmodule, addr) {
    // let secmodule = Process.findModuleByName("libmsaoaidsec.so");
    if (!secmodule) {
        console.error("[-] libmsaoaidsec.so module not found");
        return;
    }
    var point = secmodule.base.add(addr);
    Interceptor.attach(point,{
        onEnter:function (args){
            Stalker.follow(Process.getCurrentThreadId(), {
                transform: function (iterator) {
                    var instruction = iterator.next();
                    do{
                        console.log(instruction.address + ":" + instruction);
                        iterator.keep();
                    }  while ((instruction = iterator.next()) !== null);
                }
            });

        },
        onLeave:function(retval){

        }
    });
}

function hook_pthread_create(){
    console.log("libmsaoaidsec.so --- " + Process.findModuleByName("libmsaoaidsec.so").base)
    console.log("libmsaoaidauth.so --- " + Process.findModuleByName("libmsaoaidauth.so").base)

    Interceptor.attach(Module.findExportByName("libc.so", "pthread_create"),{
        onEnter(args){
            let func_addr = args[2]
            console.log("The thread function address is " + func_addr)
        }
    })
}

function hook_dlopen(soName = '') {
    Interceptor.attach(Module.findExportByName(null, "android_dlopen_ext"),
        {
            onEnter: function (args) {
                var pathptr = args[0];
                if (pathptr !== undefined && pathptr != null) {
                    var path = ptr(pathptr).readCString();
                    if (path.indexOf(soName) >= 0) {
                        locate_init()
                    }
                }
            }
        }
    );
}

function locate_init() {
    let secmodule = null
    Interceptor.attach(Module.findExportByName(null, "__system_property_get"),
        {
            // _system_property_get("ro.build.version.sdk", v1);
            onEnter: function (args) {
                secmodule = Process.findModuleByName("libmsaoaidsec.so")
                var name = args[0];
                if (name !== undefined && name != null) {
                    name = ptr(name).readCString();
                    if (name.indexOf("ro.build.version.sdk") >= 0) {
                        // 这是.init_proc刚开始执行的地方，是一个比较早的时机点
                        // do something
                        // bypass()
                        // hook_pthread_create()
                        console.log("libmsaoaidsec.so --- " + Process.findModuleByName("libmsaoaidsec.so").base);
                        // console.log("libmsaoaidsec.so --- " + Process.findModuleByName("libmsaoaiauth.so").base);
                        // hook_native_addr(secmodule, 0x26E5C);
                        // hook_native_addr(secmodule, 0x1B8D4);
                        // hook_native_addr(secmodule, 0x1C544);
                        bypass(secmodule.base.add(0xC95C));
                        bypass(secmodule.base.add(0x26744));
                        bypass(secmodule.base.add(0x1B630));
                        bypass(secmodule.base.add(0x26424));
                        // bypass(secmodule.base.add(0x11FD4));

                        /* bypass(secmodule.base.add(0x1B8AC));
                        bypass(secmodule.base.add(0x17C60));
                        bypass(secmodule.base.add(0x1B8F8)); */
                        /* bypass(secmodule.base.add(0x876C));
                        bypass(secmodule.base.add(0x8718));
                        bypass(secmodule.base.add(0x8C80));
                        bypass(secmodule.base.add(0x9124));
                        bypass(secmodule.base.add(0x95A0));
                        bypass(secmodule.base.add(0xA938));
                        bypass(secmodule.base.add(0xA998));
                        bypass(secmodule.base.add(0xA9F4));
                        bypass(secmodule.base.add(0xAA48));
                        bypass(secmodule.base.add(0xAAD4));
                        bypass(secmodule.base.add(0xADF4));
                        bypass(secmodule.base.add(0xB094));
                        bypass(secmodule.base.add(0xB210));
                        bypass(secmodule.base.add(0xB4A8));
                        bypass(secmodule.base.add(0xB840));
                        bypass(secmodule.base.add(0xBBEC));
                        bypass(secmodule.base.add(0xBC70));
                        bypass(secmodule.base.add(0xBCEC));
                        bypass(secmodule.base.add(0xBE24));
                        bypass(secmodule.base.add(0xBE40));
                        bypass(secmodule.base.add(0xBFF0));
                        bypass(secmodule.base.add(0xC11C));
                        bypass(secmodule.base.add(0xC150));
                        bypass(secmodule.base.add(0xC1D8));
                        bypass(secmodule.base.add(0xC1FC));
                        bypass(secmodule.base.add(0xC3B4));
                        bypass(secmodule.base.add(0xC5D4));
                        bypass(secmodule.base.add(0xC63C));
                        bypass(secmodule.base.add(0xC6D8));
                        bypass(secmodule.base.add(0xC72C));
                        bypass(secmodule.base.add(0xC7DC));
                        bypass(secmodule.base.add(0xC814)); */
                    }
                }
            }
        }
    );
}

function nop(addr) {
    Memory.patchCode(ptr(addr), 4, code => {
        const cw = new Arm64Writer(code, { pc: ptr(addr) });
        cw.putNop();
        // cw.putNop();
        cw.flush();
    });
}

function bypass(addr){
    // let module = Process.findModuleByName("libmsaoaidsec.so")
    // nop(module.base.add(0x1C544))
    // nop(module.base.add(0x1B8D4))
    // nop(module.base.add(0x26E5C))
    nop(addr)
}

setImmediate(hook_dlopen, "libmsaoaidsec.so")

// hookDlopen();
```

菜鸟一枚，如果有大神可以指导下，是怎么检测的java hook 的。  看不明白他的逻辑.

---

# 回复

## 回复 by calleng (#2)

*2025-6-2 23:53*

能够写的这么详细, 确实 花了不少时间, 我估计遇到问题 , 4个小时, 写成文章 4个小时, 特别折腾人. 楼主的 如此的执着精神令小生佩服...![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by hacker521 (#3)

*2025-6-3 00:49*

你这不如在内核隐藏frida的痕迹啊？

## 回复 by mb_elqwyvnm (#4)

*2025-6-3 10:04*

感谢分析，新手学习

## 回复 by falconnnn (#5)

*2025-6-3 14:33*

app是哪个版本的？

## 回复 by calleng (#6)

*2025-6-4 02:34*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  你这不如在内核隐藏frida的痕迹啊？
>
>

我也想要学习, 但是ebpf 课程中, r0yuse 佬, 提到过, ksu 逻辑 和  apatch 中的内核模块实现. 想要青椒高手, 探讨,能加wchat ,么?

## 回复 by wx_小友 (#7)

*2025-6-7 13:12*

>
> [calleng](https://bbs.kanxue.com/user-304186.htm)
>
>  能够写的这么详细, 确实 花了不少时间, 我估计遇到问题 , 4个小时, 写成文章 4个小时, 特别折腾人. 楼主的 如此的执着精神令小生佩服...[em_003]
>
>

这个我弄了好多天，菜鸟一枚，想学习逆向的东西。

## 回复 by wx_小友 (#8)

*2025-6-7 13:13*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  你这不如在内核隐藏frida的痕迹啊？
>
>

不知道怎么弄，有什么切入点吗？  或者知识点是什么？ 我找找。 谢谢

## 回复 by wx_小友 (#9)

*2025-6-7 13:14*

>
> [falconnnn](https://bbs.kanxue.com/user-803962.htm)
>
>  app是哪个版本的？
>
>

V16.4.7  你能看出这个APP是哪个？

## 回复 by wx_小友 (#10)

*2025-6-7 13:17*

>
> [calleng](https://bbs.kanxue.com/user-304186.htm)
>
>  我也想要学习, 但是ebpf 课程中, r0yuse 佬, 提到过, ksu 逻辑 和 apatch 中的内核模块实现. 想要青椒高手, 探讨,能加wchat ,么?
>
>
>

电报  @lpy0001

## 回复 by wx_小友 (#11)

*2025-6-7 13:21*

>
> [深圳PD Labs](https://bbs.kanxue.com/user-1034449.htm)
>
>  这贴思路清晰、实战痕迹很重，`Java.perform()`被秒退的问题基本摸到了关键点：`/proc/self/status` 和 `maps` 的检测只是外围，核心还是 `libmsaoaidse ...
>
>

感谢告知，等我学习好，在找相关工作吧， 现在是个菜鸟，完成不了任何APP的逆向，  想想就可悲，已经学习了近半年了， 还是菜鸟水平。

## 回复 by wx_小友 (#12)

*2025-6-7 13:32*

>
> [深圳PD Labs](https://bbs.kanxue.com/user-1034449.htm)
>
>  这贴思路清晰、实战痕迹很重，`Java.perform()`被秒退的问题基本摸到了关键点：`/proc/self/status` 和 `maps` 的检测只是外围，核心还是 `libmsaoaidse ...
>
>

```
function hook_native_addr(secmodule, addr) {
    if (!secmodule) {
        console.error("[-] libmsaoaidsec.so module not found");
        return;
    }
    var point = secmodule.base.add(addr);
    var startAddr = secmodule.base;
    var endAddr = secmodule.base.add(secmodule.size);

    Interceptor.attach(point,{
        onEnter:function (args){
            Stalker.follow(Process.getCurrentThreadId(), {
                transform: function (iterator) {
                    var instruction = iterator.next();
                    do{
                        if (instruction === null || instruction.address === null) {
                            continue;
                        }
                        if (instruction.address >= startAddr && instruction.address < endAddr) {
                            console.log(instruction.address.sub(secmodule.base) + ":" + instruction);
                        }
                        iterator.keep();
                    }  while ((instruction = iterator.next()) !== null);
                }
            });

        },
        onLeave:function(retval){

        }
    });
}

var firstHandle = false;
function locate_init() {
    let secmodule = null
    Interceptor.attach(Module.findExportByName(null, "__system_property_get"),
        {
            // _system_property_get("ro.build.version.sdk", v1);
            onEnter: function (args) {
                secmodule = Process.findModuleByName("libmsaoaidsec.so")
                var name = args[0];
                if (name !== undefined && name != null) {
                    name = ptr(name).readCString();
                    if (name.indexOf("ro.build.version.sdk") >= 0) {
                        console.log("locate_init [+] 目标库已加载，开始Hook... secmodule base: " + secmodule.base);
                        if (!firstHandle) {
                            hook_native_addr(secmodule, 0x26334);
                            firstHandle = true;
                        }
                    }
                }
            }
        }
    );
}
```

发现一个更不知道的方法， 只要在里面加入Stalker.follow 就可以过java hook ,好奇怪。  使用 frida -H xxxxxx  -l xxxx.js -f xxxx  启动后，等会app会被杀死，但是可以手动在手机上打开app, 此时app 就可以被 java hook了。  但是10%的概率会卡死。  原因不明。  我在过广告的过程中发现的，弄了2周了，还是过不了广告，发现应该是在native层加入的广告。 但是没找到JNI的调用，理论上，从界面上点击后，应该会有JNI的调用，在View层将广告的视频流写入到同一个SurfaceView, 但是没找到对应的入口。好多次想放弃了，还是坚持下来了， 不过还是没达到目的。 再研究研究吧~  给自己加油-小菜鸟。

## 回复 by null0bj (#13)

*2025-6-7 18:54*

respect!!!

我之前也研究过这个库，当时只专注于native层对frida注入的检测，得出结论如下：

1、当主线程对libmsaoaidsec.so库完成链接、重定位后，在constructor函数会通过dlsym查找pthread_create创建子线程进行间歇性检查。
2、libmsaoaidsec库实现了字符串特征进行检测（如下图）包括、线程名称、文件fd、文件名称（/data/local/tmp）、TracerPid、等等。
我以为所有的检测工作都是在子线程中进行的，但是当我通过spawn方式进行注入魔改版的frida（基本去除了所有的字符串特征），libmsaoaidsec会在主线程中触发崩溃机制，libmsaoaidsec在不断进化，我测试的版本已经不能仅仅通过hook pthread_create进行绕过了，主线程也会检测frida。
此外，java层的hook检测我也没搞清是怎么回事，不只是Java.perform，当我使用Java.use也会被检测到，不知道是什么检测方法，看了许多帖子，并没有找到相关的研究，问了AI也没头绪，就暂时搁置了。
楼主加油，看好你！

![image](https://bbs.kanxue.com/upload/attach/202506/890495_JCQDGPXM6TP3M58.webp)

## 回复 by null0bj (#14)

*2025-6-7 20:33*

我刚刚测试了一下，当使用Java层的hook，libart.so的PrettyMethod会被frida-agent hook，因为inline hook就是将目标函数入口的指令替换成了跳转到自定义代码的跳转指令（arm64下为BLR），所以，通过检测PrettyMethod入口的字节码就知道是否使用了Java Hook。

楼主可以试试执shell命令

```
readelf /apex/com.android.art/lib64/libart.so -s | grep PrettyMethod
```

记录一下PrettyMethod函数在**原始libart.so文件中**，入口的指令。
再注入frida，然后随意使用一个Java Hook，再查看**内存中libart.so库**的PrettyMethod函数的入口指令。

## 回复 by wx_小友 (#15)

*2025-6-9 15:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  null0bj](https://bbs.kanxue.com/user-890495.htm)
>
>  我刚刚测试了一下，当使用Java层的hook，libart.so的PrettyMethod会被frida-agent hook，因为inline hook就是将目标函数入口的指令替换成了跳转到自定义代 ...
>
>

好的，我尝试一下看看，  感谢提供的思路。 看来还得学习一下inline hook的原理

## 回复 by wx_小友 (#16)

*2025-6-9 15:25*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  null0bj](https://bbs.kanxue.com/user-890495.htm)
>
>  respect!!!我之前也研究过这个库，当时只专注于native层对frida注入的检测，得出结论如下：1、当主线程对libmsaoaidsec.so库完成链接、重定位后，在constructor函 ...
>
>

一起加油吧

## 回复 by 酒仙桥之虎 (#17)

*2025-6-9 18:10*

写的很好很细 切实可行 学习下

## 回复 by bluegatar (#18)

*2025-6-10 00:53*

很好的分析啊

## 回复 by mb_pnlabahd (#19)

*2025-6-12 01:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  null0bj](https://bbs.kanxue.com/user-890495.htm)
>
>  我刚刚测试了一下，当使用Java层的hook，libart.so的PrettyMethod会被frida-agent hook，因为inline hook就是将目标函数入口的指令替换成了跳转到自定义代 ...
>
>

怎么过这个检测

## 回复 by null0bj (#20)

*2025-6-12 12:27*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_pnlabahd](https://bbs.kanxue.com/user-975939.htm)
>
>  怎么过这个检测
>
>

对PrettyMethod的检测一般利用子线程轮询检测。所以，在主线程使用pthread_create clone子线程的时候可以知道子线程所执行的偏移地址，将该偏移地址放一条ret指令即可。

## 回复 by Da_ (#21)

*2025-6-19 11:19*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 我不是卷王 (#22)

*2025-8-8 14:51*

可以提供一下对应的so文件吗 版本有很多

## 回复 by wx_小友 (#23)

*2025-8-8 15:54*

>
> [我不是卷王](https://bbs.kanxue.com/user-1030887.htm)
>
>  可以提供一下对应的so文件吗 版本有很多
>
>

.....      你直接下载个aiqiyi 之类的app都可以吧， 主要那个地址需要直接找下， 还有你android版本，linker 文件初始化so的函数地址。
我试了几个app  都可以。

你看我这个文章，  https://bbs.kanxue.com/thread-287913.htm
当前这个文章问题太多了。
