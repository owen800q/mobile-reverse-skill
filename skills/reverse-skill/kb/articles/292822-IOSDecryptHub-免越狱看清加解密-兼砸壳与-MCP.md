---
title: '[原创]IOSDecryptHub：免越狱看清加解密，兼砸壳与 MCP'
url: https://bbs.kanxue.com/thread-292822.htm
tid: 292822
author: 太岁又沐风
date: ''
tags: [Android安全, 原创, 逆向分析, 程序开发, HOOK注入, 工具脚本, 其他]
crawled_at: '2026-09-02T01:39:39+00:00'
replies: 4
---

# IOSDecryptHub：免越狱看清加解密，兼砸壳与 MCP

>
> 一个只需注入 dylib、无须越狱的 iOS 运行时分析助手：**加解密捕获 + 抓包 + 砸壳 + 文件/Keychain/行为分析 + MCP**。
>
>
>

---

github: <https://github.com/decrypthub/IOSDecryptHub>

网站(兼越狱源)：<https://ios.decrypthub.com>

# 一、设计思路、能力边界与兼容性

## 设计思路

这个工具适用于密码学算法逆向、iOS 砸壳，还有抓包（hook 实现，无须代理），还有 iOS 应用文件、Keychain、App 行为分析。

AI 时代，效率非常重要，做这个的意义就是把重复低级的工作交给 AI 完成，把时间花在有价值的事情（刷抖音）上面。

把流程简化，逆向 App 协议的步骤现在应该是——打开 IOSDecryptHub，手动登录一次 App，然后对 Agent 说：

>
>
>
> ```python
> 调用 IOSDecryptHub MCP，帮我分析 xxxx 的登录请求和它的加密算法，并用 Python 实现协议登录。
> ```
>
>
>

当然这是比较理想化的任务，不过一般来说，其实对于大部分 App 都可以做到。

## 能力边界

我们实现了大量**不需要越狱、只需要注入 dylib** 就能实现的功能！

iOS 有两个相互咬合的内核级机制，是整套设计的根本约束（这里不谈越狱哈）：

>
> **① 强制代码签名（AMFI / AppleMobileFileIntegrity）**
> 每一个要执行的内存页都必须有有效签名，由内核配合 trust cache 校验。没签名的代码页，内核直接拒绝执行。
>
>
> **② W^X（Write XOR Execute）内存策略**
> 一块内存要么可写、要么可执行，不能兼得。想把一块可写内存改成可执行（`mprotect` 加执行权限、`mmap` 带 `MAP_JIT`），需要一个叫 `dynamic-codesigning` 的 entitlement——而这个 entitlement 只发给系统里极少数进程（比如 WebKit 的 JavaScriptCore 做 JIT）。普通侧载 App 拿不到。
>
>
>

方便以后为越狱开发更为强大的功能，比如 inline hook / trampoline / DBI（Frida Stalker、QBDI）这种。（先画饼再说哈哈哈哈）

## 兼容性

这就是为啥用 **fishhook + swizzle**。

不过没关系，这样的牺牲是有价值的，并且是刻意做的取舍，因为获得了兼容性——

>
> 打包了：**巨魔、roothide、rootless** 环境都可以使用的通用助手！
>
>
>

至于为什么不做 rootful，太老了 bro，现在越狱工具都不更新了，也就不想花时间维护这玩意，而且老 iOS 系统已经很多 App 跑不起来了。

>
> 推荐使用**多巴胺**环境～
>
>
>

---

# 二、能给你帮啥忙？解决什么逆向

在注入 dylib 的能力边界上，基本能堆的配置都上了一遍，有些是 AI 查到的，不过没关系，够你用了。

## 加解密

>
> **核心中的核心。** 不追具体算法实现，只掐住密码学库的 API 咽喉。
>
>
>

看表：

| 路线 | 库 | Hook 手段 | “咽喉”符号 |
|-|-|-|-|
| CommonCrypto | libSystem | fishhook | `CCCrypt` / `CCCryptorCreate*` / `CCHmac*` / `CC_SHA*` / `CCKeyDerivationPBKDF` |
| SecKey（非对称） | Security.framework | fishhook | `SecKeyCreateSignature` / `SecKeyCreateDecryptedData` 等 |
| OpenSSL | 自带的 libcrypto | fishhook | `EVP_*Init_ex` / `EVP_*Update` / `EVP_*Final` |

**这些都是 C 导出符号，用 fishhook 改 GOT 就行。**

对称加密里，`CCCrypt` 是一次性调用，直接在 hook 里拿到 `(key, iv, in, out)` 六元组落库；而 `CCCryptorCreate → Update → Final` 是流式的，单次 hook 拿不到全貌，所以它用 `cryptorRef` 指针**当 key**，把每次 `Update` 的输入输出累积起来，到 `Final` 才落一条完整日志（累积上限 4MB 防 OOM）。HMAC 同理，用 ctx 指针在 `NSMutableDictionary` 里跟踪 key 和累积输入。

## 网络请求

>
> **双层布点：** 上层抓结构化请求，下层抓 TLS 明文字节流。
>
>
>

### 上层：NSURLSession 用 ObjC swizzle

绝大多数 App 走 `NSURLSession`，而它是 ObjC，所以用 swizzle 而不是 fishhook。难点是任务有好几种发起方式：

- **completion 型**：`dataTaskWithRequest:completionHandler:`
- **delegate 型**：`dataTaskWithRequest:`（结果回调走 delegate，不在这个方法里）
- **上传型**：`uploadTaskWithRequest:fromData:`
- **body 单独设置**：`NSMutableURLRequest setHTTPBody:`

**在 `NSURLSessionTask resume` 上做兜底。** 因为不管你用哪种方式创建任务，最后都得 `resume` 才会真正发出去。在 `resume` 时把 method / url / headers / body 合并成一条日志。

### 下层：SSL_write / SSL_read 用 fishhook

`SSL_write` / `SSL_read` 抓的是**进 TLS 之前 / 出 TLS 之后的明文字节流**——这是抓 TLS 加密流量明文的经典点位，之前 r0capture 也在这里 hook 过。

## App 沙盒文件

水一个段落吧，这个没啥好写的，不就是读文件吗，hook 一下 libc 的文件系统调用，可以观察简单的越狱检测。

## Keychain

>
> **看似小角色其实有大用。**
>
>
>

Keychain 是 Security.framework 的 C 符号，hook 点是 `SecItem` 那四个 CRUD：

| 符号 | 操作 |
|-|-|
| `SecItemCopyMatching` | 读 |
| `SecItemAdd` | 写 |
| `SecItemUpdate` | 改 |
| `SecItemDelete` | 删 |

很多 App 会把用户凭据、设备 id 和一些敏感数据放在里面，其实在 AI 追踪的时候很方便，因为有些数据它能分辨出是持久化存储的，还是协议里面的数据。

## 系统行为

**观测** —— `hook_env.m` 和 `hook_system.m` 里的符号：

- `dlopen` / `dlsym`：记录 App 运行时加载了哪些库、动态解析了哪些符号（`dlsym` 还要顺便返回 hook wrapper，前面讲过）
- `sysctl` / `sysctlbyname` / `uname` / `getenv`：观测 App 在探测什么环境信息

**改写** —— 拦截和改写系统调用（`ptrace`、`csops`、`sysctl`）和应用层 API（`dladdr`、`canOpenURL` 等），让 App 无法感知调试器的存在和越狱环境的证迹，从而绕过开发者设置的反调试锁定、代码签名验证、进程追踪、越狱路径暴露和动态库注入。

>
> 懂的都懂，不展开说，隐藏强度也有限。
>
>
>

## Dump（砸壳）

浏览器打开 **Web UI**，可以像下载文件一样下载砸壳的 **IPA**，或者下载某个单独的镜像，非常方便，用了就知道。

---

# 三、MCP

最开始的设想很简单，就是用 HTTP 的 MCP，但由于每个 iOS 设备 IP 地址不一样，所以写了个 **CLI 工具**，可以直接安装使用：

```bash
pip install ios-decrypt-hub
idh --help
\```

等于是一个网关的作用，也有部分原因是部分 AI 工具（Claude Desktop）甚至不支持 HTTP 的 MCP，很傻 x 还以为自己老屌了。用 CLI 又方便配置，兼容性也强，用起来也简便。

如果仅仅是工具调用，其实也没啥，但是我把 **Capstone** 编进去了，这就有了一些扩展性，AI 可以自己反汇编，虽然没有 idapro-mcp 那样强大的能力，但做一些简单的分析和定位也很方便。

>
> 效果很棒
>
>
>

---

# 结语

AI的帮助无疑是巨大的，工具大部分功能，都是依靠AI搜索查询，边学习边做的，不过感觉大脑有点被AI夺舍了，什么都想让AI搞，自己变得懒惰许多

>
> 淘汰从不喧哗。它只是某天你打开工具，发现机器已经替你走完了你引以为傲的全部步骤，只在真正需要判断的岔路口停下，等一个它给不出的答案。而如果那个答案你也给不出——那么这个行业，已经不再需要你了。
>
>
>

---

# 回复

## 回复 by 墨穹呢 (#2)

感谢分享

## 回复 by git_20231158183478491 (#3)

111

## 回复 by 拍拖 (#4)

感谢分享

## 回复 by sorely (#5)

666
