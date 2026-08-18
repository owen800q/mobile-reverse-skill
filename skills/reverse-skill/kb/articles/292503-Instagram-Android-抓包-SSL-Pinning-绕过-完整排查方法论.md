---
title: '[原创]Instagram Android 抓包 / SSL Pinning 绕过 —— 完整排查方法论'
url: https://bbs.kanxue.com/thread-292503.htm
tid: 292503
author: wx_小友
date: ''
tags: [Android安全, 原创]
crawled_at: '2026-08-18T06:06:13+00:00'
replies: 5
---

# Instagram Android 抓包 / SSL Pinning 绕过 —— 完整排查方法论

> 目的:记录这次从"代理连不上"到"找到真正的 pinning 检查函数"的完整排查思路,

> 方便 App 更新后(函数地址会变),照着同一套方法重新定位,不用从头摸索。

>

> 结论先说:Instagram 用的是 Meta 自家的 **Tigon 网络栈**(Fizz TLS1.3 + 私有编译的

> BoringSSL + folly + proxygen),完全不走 Android 系统的网络 API / 系统证书库,

> 所以市面上通用的"改系统证书""hook OkHttp/TrustManager"的方法对它全部无效。

> 真正卡住抓包的,是一个独立的、跟标准 TLS 校验完全分开的 **SPKI 证书锁定检查函数**。

---

## 0. 前置知识:为什么常规方法没用

- Instagram 的网络请求不走标准 Android `HttpsURLConnection` / `OkHttp` / 系统 `libssl.so`。

- 它用的是 Meta 私有的 **Tigon** 网络栈,内部代号 **MNS**(Mobile Network Stack)。

- TLS 握手用的是 Facebook 开源的 **Fizz**(TLS 1.3 实现),配合**私有编译进

  `libstartup.so` 的 BoringSSL**(不是系统 `/system/lib64/libssl.so`,是 App 自己

  编译打包的一份,函数名相同但是完全独立的二进制)。

- 所以:

  - 改 `/apex/com.android.conscrypt/cacerts` 或系统 CA store 没用(它压根不查系统信任库)。

  - hook 系统 `libssl.so` 的 `SSL_CTX_set_custom_verify` 等标准函数没用(调用次数为 0,

    验证过一遍就知道:这些 hook 全都不会被触发)。

  - hook OkHttp 的 `CertificatePinner` 没用(Instagram 走的不是 OkHttp)。

- App 的原生库是用 Meta 自研的 **Superpack** 压缩格式打包在 `assets/lib/libs.spo`

  里的,运行时解压到 `/data/data/com.instagram.android/lib-compressed/`,

  **必须从这个运行时目录里 pull 出来分析,APK 里直接解出来的 .so 是无法直接用的压缩格式**。

---

## 1. 环境准备

### 1.1 需要的工具

- 已 root 的测试机(Magisk)

- Frida 17.x + `frida-server`(改名规避检测,见下方)

- IDA Pro(带 Hex-Rays ARM64 反编译器)

- mitmproxy 或 Burp Suite(建议用 mitmproxy,启动更快,而且能重放/查看更方便)

### 1.2 拉取运行时的 App 原生库

先正常启动一次 App(让它把 Superpack 压缩包解压好),然后:

```bash

adb shell run-as com.instagram.android ls lib-compressed/

adb shell run-as com.instagram.android cat lib-compressed/libstartup.so > libstartup.so

\```

`libstartup.so` 就是本次真正要分析的目标 —— 里面塞了 Fizz + proxygen + folly +

私有 BoringSSL + 证书锁定逻辑,是个几十 MB 的巨型 C++ 库,stripped(没有符号表)。

> 如果更新版本后文件名变了(比如换成别的 lib 名),用同样的方法从

> `lib-compressed/` 目录里把所有 .so 都 pull 出来,再用 `nm -D` 或者 IDA 打开看

> 里面 export 的符号(搜 `fizz::`、`folly::`、`proxygen::`、`MNSTCP` 这些关键字)

> 找到对应的库。

### 1.3 配置代理 + 设备网络

```bash

adb shell settings put global http_proxy <代理机IP>:<端口>

\```

或者在 WiFi 设置里手动填代理(部分场景 `settings put global` 不生效,需要在

系统 WiFi 详情页手动配置静态代理)。

装好 mitmproxy/Burp 的 CA 证书到用户证书目录即可,**不需要**折腾系统级证书注入

(NVISO 的 `AlwaysTrustUserCerts` 那一套对 Tigon 完全没用,是走了弯路才发现的,

Tigon 根本不查系统信任库)。

---

## 2. 快速定位法(推荐,优先试这个)

这是这次绕了一大圈之后,事后复盘发现**最快、最该优先做**的方法:

**直接在 IDA 里全局搜索证书校验相关的错误字符串**,不用去猜 vtable、猜调用栈。

### 2.1 操作步骤

1. 用 IDA 打开 `libstartup.so`,等自动分析跑完。

2. 打开 `Strings` 窗口:菜单 `View > Open subviews > Strings`,或快捷键 `Shift+F12`。

3. 在字符串窗口里按 `Ctrl+F` 搜索以下关键词(**任意一个命中就有戏**):

   - `pinning`

   - `pinned root`

   - `SPKI`

   - `Certificate chain verification failed`

   - `Failed to parse proxy response`

   - `certificate_unknown`

4. 这次实测命中的是:

   ```

   "Certificate pinning validation failed. Peer certificate chain does not

   contain pinned root, peer SPKIs={}"

   ```

5. 双击这条字符串跳转过去,然后按 `X`(交叉引用)看谁引用了它 —— 会跳到唯一一个

   函数(本次是 `sub_58E8C4`)。

6. 反编译这个函数(`F5`),确认函数特征符合:

   - 入参里有证书链(数组/count)

   - 内部会解析 DER 证书、算 SPKI

   - 返回值是"错误对象指针"或者 bool/int(0/1 表示成功失败)

   - 里面能看到多条类似的错误信息拼接(chain verification failed、

     cert expired、parse DER 失败 等等),因为这类函数通常是"一个大的证书校验

     流程,每种失败原因返回不同错误"

### 2.2 为什么这个方法更好、更抗版本更新

- 函数地址(`sub_XXXXXX`)每次编译都会变,**不能**硬编码地址长期使用。

- 但**错误提示字符串**是产品文案,除非 Meta 主动改文案或者加字符串混淆/加密,

  否则**版本升级后大概率还在**,搜索它比"猜哪个 vtable 槽位""追 close() 调用栈"

  快得多、稳得多。

- 如果这几个字符串本身也搜不到了(比如新版本对字符串做了混淆/加密),再退回

  第 3 节的笨办法。

---

## 3. 笨办法(字符串搜索失效时的兜底流程)

如果字符串搜索这条路走不通(比如版本更新后错误文案被混淆了),按下面顺序来,

这是这次实际踩出来的路径,**顺序很重要**,能少走弯路:

### 3.1 先确认代理层面到底卡在哪一步

写一个 Frida 脚本 hook `connect()` / `write()` / `send()` / `close()`(参考本

仓库 `frida/tls_progress.js`),观察:

- **连 CONNECT 请求都没发出去** → 问题在 TCP 连接建立阶段,不是证书问题。

- **发了 CONNECT,代理响应也解析成功,ClientHello 也发出去了,但之后连接很快

  被 close()** → 说明走到了 TLS 层,大概率是证书 / pinning 问题。

  这次的现象就是这一种:每次都是固定发 2 次 write(CONNECT 行 + ClientHello)

  后连接被杀。

> **踩坑提醒**:filter 连接时不要用 `dest.port === 443` 来判断"是不是要追踪的

> 代理连接"——**客户端连的是代理自己的端口(比如 mitmproxy 的 8888),不是

> 443**,443 只有在没走代理、直连的时候才对。这次因为这个过滤条件写错,浪费了

> 好几轮测试都拿到空结果。

### 3.2 通过 `close()` 调用栈反查是谁杀的连接

```js

Interceptor.attach(libc.findExportByName("close"), {

    onEnter: function (args) {

        var frames = Thread.backtrace(this.context, Backtracer.FUZZY);

        // Backtracer.ACCURATE 在这个 App 里会直接把网络线程搞崩,别用

        ...

    }

});

\```

参考 `frida/catch_close.js`。拿到的调用栈里,找到 `libstartup.so` 内的地址,

在 IDA 里定位是哪个函数在调 `close()` 或者调统一的"拆连接"辅助函数

(这次是 `sub_404B7C`)。

### 3.3 顺着"拆连接"函数往上找触发源

在 IDA 里对这个"拆连接"函数按 `Ctrl+X` 看交叉引用,会列出所有调用它的地方

(这次找到 7 个调用点)。这些调用点里可能混杂了:

- 真正的证书/pinning 校验失败路径(我们要找的)

- 各种超时定时器回调(TCP connect 超时、代理 CONNECT 响应超时等)

- 正常的 socket 错误处理(read()==0、EOF 等)

**不要一上来就猜是超时**——这次一开始怀疑是连接超时(1.0s 定时器),

patch 了以后现象没变,浪费了一轮排查。正确经验是:**这些调用点要一个一个

反编译确认语义,不要只看函数名字长得像就猜**。

### 3.4 判断依据:看函数里有没有"证书/SPKI/pinning"相关的字样或逻辑

反编译每个候选函数,重点看:

- 有没有解析证书链(DER 解析、SPKI 计算、base64 编码指纹的循环)

- 有没有"域名是否在 pinning 名单里"这种查表逻辑

- 有没有明显的错误信息拼接(哪怕字符串本身乱码/加密了,`fmt::v9::vformat` 这种

  格式化调用 + 后面跟一堆 "xxx failed" 结构,也是强烈信号)

真正的 pinning 校验函数长这样(简化后的特征,供下次比对):

```c

// 伪代码特征,不是真实反编译结果,仅供识别用

xxx_error_t* check_pinning(cert_chain_t chain) {

    if (chain.count == 0) return error("empty chain");

    for each cert in chain: parse_der(cert);       // 解析证书

    verify_chain(chain);                             // 标准链校验(过期/签名等)

    if (hostname not in pinned_domains) return NULL;  // 没配置 pinning 的域名直接放行

    for each cert in chain:

        if spki_hash(cert) in pinned_roots: return NULL; // 命中 pinned root,通过

    return error("pinning validation failed, SPKIs=...");  // 都没命中,失败

}

\```

---

## 4. 确认候选函数:用"最小化验证法"

找到候选函数后,**不要一次性把所有猜测都 patch 上**,一个一个单独测,

才能确认到底是不是它、以及是不是唯一需要的点。这次的教训是一开始同时

patch 了 3 个点(Fizz `verify()` + 连接超时 + SPKI pinning),流量通了,

但根本不知道哪个是真正起作用的,后来专门做了一轮"减法测试"才搞清楚

**其实只有 SPKI pinning 这一个 patch 是必需的**,另外两个都是无效的弯路。

### 4.1 Frida patch 模板

```js

(function () {

var TARGET_OFFSET = 0x58E8C4; // 改成新版本里找到的地址

function hookModule(mod) {

    var addr = mod.base.add(TARGET_OFFSET);

    Interceptor.replace(addr, new NativeCallback(function (a1) {

        console.log("[pin-bypass] called -> forcing NULL (pass)");

        return ptr(0); // 返回 NULL/0 表示"没有错误,校验通过"

    }, "pointer", ["pointer"]));

    console.log("[pin-bypass] PATCHED @ " + addr);

}

var mod = Process.findModuleByName("libstartup.so");

if (mod) hookModule(mod);

else Process.attachModuleObserver({

    onAdded: function (m) {

        if (m.name === "libstartup.so") setTimeout(function () { hookModule(m); }, 300);

    }

});

})();

\```

> 返回值类型要看反编译出来的函数签名:如果是返回 `void` 且靠"抛异常"表示失败

> (比如 Fizz 的 vtable `verify()`),patch 成"什么都不做的空函数"即可,不需要

> return 值;如果是返回错误指针/错误码,patch 成返回 `0`/`NULL`。

### 4.2 验证脚本:确认连接真的活过了 TLS 握手

用 `frida/tls_progress.js` 这类脚本,track 走代理的连接(按 4.3 节的方式过滤),

记录每条连接的 write 次数和是否被提前 `close()`:

- **失败特征**:固定 2 次 write(CONNECT 行 + ClientHello)后就 close。

- **成功特征**:write 次数能持续增长到 7~8 次以上,且中间出现明显变大的

  数据包(几百到几千字节,是真实的应用层数据),长时间不 close。

```js

var PROXY_IP = "<代理机IP>";

Interceptor.attach(libc.findExportByName("connect"), {

    onEnter: function (args) {

        var dest = describeSockaddr(args[1]); // 解析 sockaddr

        if (!dest || dest.ip !== PROXY_IP) return; // 按代理 IP 过滤,不要按 443 端口过滤!

        trackedFds[args[0].toInt32()] = { writes: 0, ip: dest.ip };

    }

});

\```

### 4.3 测试流程(每个候选点重复一遍)

1. `adb shell am force-stop com.instagram.android` —— 保证每次都是干净的进程状态。

2. `frida -H 127.0.0.1:1234 -f com.instagram.android -l <只加这一个候选补丁>.js -l tls_progress.js`

3. 手动操作 App(刷 Feed、点开几个主页)15~20 秒 —— **冷启动本身不一定会触发

   走代理的请求,必须要有实际的 GraphQL 类接口调用才会看到代理连接**。

4. 看日志:有没有 `CLOSED after 2 writes` 这种提前断连,还是能持续 write 下去。

5. 一个点测完,`taskkill /F /IM frida.exe`(或者关掉当前 frida session),

   `am force-stop` 干净后再测下一个候选点。

这次实测结果:只挂 `spki_pin_bypass.js` 一个补丁,15 条走代理的连接全部正常

持续到 write #7/#8(1700~2400+ 字节的真实数据),0 条提前断连 —— 证明

**这一个点就是全部答案**,不需要叠加其他补丁。

---

## 5. Hook 的两种使用方式

找到目标函数之后,有两种落地方式:**动态 Frida hook**(每次启动都要跑脚本,

但灵活、可随时改)和**静态改二进制**(改一次,理论上不用每次都跑 Frida,但

有失效风险,见下方说明)。两种方式patch 的目标是同一个东西:让

`sub_58E8C4`(或新版本里重新定位到的同类函数)不管传进去什么证书,永远

"返回校验通过"。

### 5.1 方式一:Frida 动态 hook(每次启动都要执行,推荐日常使用)

**优点**:不改设备上的任何文件,App 更新后只要改个地址数字就行,出问题随时

`Ctrl+C` 就能撤销,没有"改坏了变砖"的风险。

**缺点**:每次要抓包都得重新跑一遍命令,App 不能脱离 Frida 独立运行。

#### 前置条件

- 设备已 root,`frida-server` 在跑(实测环境里是改名后的

  `ajeossida-server-17.13.0-android-arm64`,放在 `/data/local/tmp/`,

  用 `su -c` 启动:

  ```bash

  adb shell "su -c '/data/local/tmp/ajeossida-server-17.13.0-android-arm64 -l 0.0.0.0:1234 &'"

  ```

- 本机(分析机)执行过 `adb forward tcp:1234 tcp:1234`,或者直接用

  `-H <设备IP>:1234` 远程连(前提是设备和分析机在同一局域网)。

- 本机装了跟设备端版本匹配的 `frida-tools`(这次全程用的 17.13.0,

  两端版本不一致的话协议握手会失败)。

#### 使用步骤

```bash

# 1. 保证是干净的进程状态(避免旧 patch/旧连接状态残留干扰判断)

adb shell am force-stop com.instagram.android

# 2. spawn 模式启动并注入(-f 会自动拉起 App,不需要额外 monkey/launch)

cd frida

frida -H 127.0.0.1:1234 -f com.instagram.android -l spki_pin_bypass.js

\```

看到下面这行说明 patch 成功挂上了:

\```

[spki-pin] PATCHED SPKI pinning check @ 0x7a5c2e38c4

\```

之后每次证书校验函数被调用,还会打一行:

\```

[spki-pin] sub_58E8C4 called -> forcing NULL (pinning passed)

\```

**没看到这行也不代表没生效** —— 这个函数只有在真正发起走代理的 HTTPS 连接时

才会被调用,冷启动界面不动的话可能一直不触发,去刷一下 Feed / 点开个人主页

就会看到了。

打开 mitmproxy(或 Burp)的 Flows/Events 面板,确认能看到解密后的

`i.instagram.com` / `graph.instagram.com` 请求即可。

> 想同时验证有没有连接被提前断开,可以再加一个 `-l tls_progress.js`

> 一起挂上,具体看第 4.2 节。

#### 常见问题

- **命令卡住不动 / 一直在 "Spawning..."**:先确认 `frida-server` 在设备上

  是不是真的在跑(`adb shell su -c 'ps -A | grep <改名后的进程名>'`),

  没跑的话重新起一个。

- **`Failed to attach: unable to perform ptrace pokedata`**:这是 attach

  模式(`-p <pid>`)被反调试拦了,改用 spawn 模式(`-f`)就行,别对一个

  已经在跑的进程做 attach。

- **改了脚本没生效**:如果是跟别的脚本一起用 `-l a.js -l b.js` 加载,

  确认每个脚本都把整体代码包在 `(function () { ... })();` 里 —— Frida

  多个 `-l` 脚本是共享同一个 JS 全局作用域的,顶层同名变量/函数会互相

  覆盖,不包 IIFE 的话经常出现"单独跑正常、一起跑其中一个就没反应"的诡异现象。

### 5.2 方式二:直接改 `.so` 文件(改一次,免 Frida 启动,但有失效风险)

**优点**:不用每次都开一个 Frida 会话,App 可以完全脱离电脑独立运行抓包,

实测比每次跑 Frida 快很多。

**缺点**:

- App 更新后地址会变,补丁失效,需要重新定位、重新改、重新推送。

- 权限/属主/SELinux context 四项但凡有一项没对齐,App 直接读不到这个文件,

  轻则那部分功能失效,重则整个 App 起不来。

> **已验证**:这次实测确认,当前这个版本下 Superpack **不会每次冷启动都

> 重新解压覆盖**改过的文件——替换后多次重启 App,代理流量依然能正常解密,

> 补丁是持久生效的,不需要每次都重新 push。不过这是"当前这个版本的行为",

> 不代表以后每个版本都一定这样,换新版本后建议还是先按第 5.2 节末尾的

> 「验证」步骤重新确认一遍稳定性,而不是默认它一定持久有效。

#### 用 IDA 手动改(Keypatch)

1. 跳转到目标地址(比如 `0x58E8C4`)

2. `Edit > Patch program > Assemble`,依次写入:

   ```

   MOV X0, #0

   RET

   ```

   对应机器码(小端序,8 字节):`00 00 80 D2 C0 03 5F D6`

3. `Edit > Patch program > Apply patches to input file...`,导出一份改过的

   `libstartup.so`

#### 或者用命令行脚本批量改(`ida/patch_so.py`)

不想开 IDA GUI 手动点的话,可以直接用脚本改(会正确按 ELF program header

把"模块内偏移"换算成"文件偏移",不是简单假设两者相等):

```bash

python ida/patch_so.py frida/libstartup.so frida/libstartup.patched.so 0x58E8C4

\```

支持一次传多个地址,一起打多个点:

```bash

python ida/patch_so.py libstartup.so libstartup.patched.so 0x58E8C4 0x8F24E4

\```

#### 推送到设备,替换掉运行时的库

**先记录原文件的权限信息**(每台设备的 uid 可能不一样,不要直接照抄下面的

`u0_a223`,一定要自己现查一遍):

```bash

adb shell "su -c 'ls -laZ /data/data/com.instagram.android/lib-compressed/libstartup.so'"

\```

拿到 owner(比如 `u0_a223:u0_a223`)、权限(比如 `r--------` / `400`)、

SELinux context(比如 `u:object_r:app_data_file:s0:c223,c256,c512,c768`)

这四项之后:

```bash

# adb push/shell 传绝对路径时,Windows 上的 Git Bash 有时会把 "/xxx" 自动转译

# 成本机 Windows 路径导致失败,报 "remote secure_mkdirs() failed" 之类的错误。

# 遇到这种情况就在路径前面加一个多余的 "/" 绕过 MSYS 的自动转换,

# 或者设置 MSYS_NO_PATHCONV=1 再执行。

adb push frida/libstartup.patched.so /data/local/tmp/libstartup.so

adb shell su -c "cp /data/local/tmp/libstartup.so /data/data/com.instagram.android/lib-compressed/libstartup.so"

adb shell su -c "chown u0_a223:u0_a223 /data/data/com.instagram.android/lib-compressed/libstartup.so"

adb shell su -c "chmod 400 /data/data/com.instagram.android/lib-compressed/libstartup.so"

adb shell su -c "chcon u:object_r:app_data_file:s0:c223,c256,c512,c768 /data/data/com.instagram.android/lib-compressed/libstartup.so"

adb shell am force-stop com.instagram.android

\```

#### 验证

不带 Frida,直接手动打开 App、刷 Feed,看 mitmproxy 能不能正常解密流量:

- **正常解密 + App 不闪退** → 补丁生效,且这次冷启动没有被 Superpack

  重新解压覆盖。多重启几次 App 确认稳定性(这次实测多次重启后依然生效)。

- **App 直接闪退 / 打不开** → 大概率是第 4 步权限/属主/context 四项没对齐,

  重新 `ls -laZ` 核对。

- **又能打开,但流量还是握手失败** → 大概率是被重新解压覆盖回原文件了,

  说明这个方法在当前 App 版本下不稳定,老老实实用 5.1 的 Frida 方式。

---

## 6. 版本更新后的操作清单(Checklist)

App 更新后,函数地址肯定会变,按这个顺序走一遍即可:

- [ ] 重新从 `lib-compressed/` 目录 pull 最新的 `libstartup.so`(或者新版本

      改名后的对应库,用 `nm -D` / IDA 搜 `fizz::`/`MNSTCP` 关键字确认是哪个)

- [ ] IDA 打开,`Shift+F12` 搜字符串:`pinning` / `pinned root` / `SPKI` /

      `Certificate chain verification failed`

- [ ] 命中后 `X` 看交叉引用,定位到函数,反编译确认是"证书链 + SPKI 校验"

      的函数特征(第 3.4 节的伪代码结构)

- [ ] 记下新的偏移地址(相对模块基址的 offset,不是绝对地址),改到

      `spki_pin_bypass.js` 的 `SPKI_PIN_CHECK_OFFSET`(或建一个新脚本)

- [ ] 单独测试这一个补丁(按第 4 节流程),确认走代理的连接能正常持续

      write、不提前 close

- [ ] 如果字符串搜索这次失效了(被混淆/加密),回到第 3 节的笨办法:

      抓 `close()` 调用栈 → 找拆连接公共函数 → 看它的调用者列表 →

      逐个反编译排查证书校验特征

---

## 7. 本次涉及的关键文件对照表

| 文件 | 作用 |

|---|---|

| `frida/spki_pin_bypass.js` | **最终生效、唯一必需**的补丁,patch `sub_58E8C4`(SPKI pinning 检查) |

| `frida/tls_progress.js` | 验证用:track 走代理连接的 write 次数和 close 情况 |

| `frida/catch_close.js` | 排查用:抓 `close()` 调用栈,定位是谁杀的连接 |

| `frida/retina_bypass_final.js` | 排查过程中的产物,**实测非必需**,patch 的是 Fizz 底层 `verify()` 和 `X509_verify_cert`,和真正的 SPKI pinning 是两条独立路径 |

| `frida/disable_timeout.js` | 排查过程中的产物,**实测非必需**,一开始怀疑是连接超时导致断连,后来证明是误诊 |

| `ida/find_timer_setters.py` | 排查过程中写的辅助脚本(全二进制扫描定时器偏移),这次没用上就已经找到答案,仅作参考 |

| `ida/patch_so.py` | 静态改二进制用的命令行小工具,按 ELF program header 把模块内偏移换算成文件偏移后直接改字节,配合第 5.2 节使用 |

---

## 8. 核心经验教训(避免下次重复踩坑)

1. **先搜错误字符串,再考虑虚表/调用栈这些笨办法** —— 字符串是产品文案,

   信息密度最高,能直接告诉你函数的语义,比逆向猜结构快得多。

2. **过滤代理连接要按代理自己的 IP,不要按目标端口(443)判断** —— 客户端

   连的是代理的端口,不是最终目标的 443。

3. **不要一次性叠多个补丁然后就当作"解决了"** —— 一定要做减法测试,

   确认真正必需的最小集合,否则以后维护的时候根本不知道该改哪个地址。

4. **怀疑超时/性能问题之前,先证明"多等一会儿"确实有用** —— 这次一开始

   怀疑是代理证书生成慢、连接超时杀连接,但即使 patch 掉超时定时器现象

   也没变,说明从一开始就该怀疑是"证书校验主动拒绝",而不是"时间不够"。

5. **冷启动不代表会触发所有网络请求** —— 测试的时候一定要真的操作 App

   (刷 Feed、切页面),否则可能压根没有触发到需要验证的那条代码路径,

   会误判"补丁没生效"。

---

# 回复

## 回复 by 尤瑟努 (#2)

6666666

## 回复 by Cure. (#3)

instagram lite有分析过吗

## 回复 by bluegatar (#4)

好像没有上传附件，格式有些奇怪

## 回复 by wx_小友 (#5)

>
> [Cure.](https://bbs.kanxue.com/user-1022596.htm)
>  instagram lite有分析过吗
>

没有看到有lite版本，fb倒是有。

## 回复 by wx_小友 (#6)

>
> [bluegatar](https://bbs.kanxue.com/user-352825.htm)
>  好像没有上传附件，格式有些奇怪
>
>

具体的脚本没给，不太好给，只给了最后的答案，格式是md的
