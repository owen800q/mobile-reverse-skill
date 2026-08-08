---
title: '[原创]抖音抓包LSPosed插件多版本可用的技术刨析'
url: https://bbs.kanxue.com/thread-291805.htm
tid: 291805
author: 太岁又沐风
date: '2026-06-29'
tags: [Android安全, 原创]
crawled_at: '2026-08-08T10:05:26+00:00'
replies: 126
---

# 抖音抓包LSPosed插件多版本可用的技术刨析

**如果只需要插件，不想看技术实现，可以关注公众号，发送“抖音插件”，获取编译好的插件**
 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/957122_YMXSQSRQQNVJ6SV.webp)

## 1. 落点选 `custom_verify`

`libsscronet.so` 会引用 BoringSSL 的 SSL API，比如 `SSL_CTX_set_custom_verify` 和 `SSL_do_handshake`；真实实现位于 `libttboringssl.so`。所以这里 hook 的不是 Cronet 的导入符号，而是 BoringSSL 里的 `custom_verify` setter。

直接 hook Cronet 的 `CertVerify` 语义上最直观，但稳定性不如 BoringSSL setter。

Cronet 的证书校验不只是一个 bool。它还会填充证书链、host、OCSP、SCT、verify flags、SSLInfo 等状态。高层粗暴截断，很容易让后续逻辑拿到不完整状态。

`custom_verify` setter 更干净：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/957122_AMCEYUMW569D5CQ.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/957122_VMHAV83V8Y34JD9.webp)

这两个函数的特点很适合 hook：

\```
函数体短
没有 paciasp
x2 就是 verify callback
语义稳定，和上层业务混淆关系不大
\```

---

## 2. 注册阶段：保存原 callback，再替换

\```
Cronet:
  SSL_CTX_set_custom_verify(ctx, mode, cronet_cb)
Detour:
  保存 cronet_cb
  调原 setter，把 MyVerifyCb 写入 BoringSSL
TLS handshake:
  BoringSSL 调 MyVerifyCb
  MyVerifyCb 再调 cronet_cb
  MyVerifyCb 覆盖最终结果
\```

核心 detour：

```cpp
using VerifyCb = int (*)(void *ssl, uint8_t *out_alert);
using SetVerifyFn = void (*)(void *obj, int mode, VerifyCb cb);
void CtxSetVerifyDetour(void *ctx, int mode, VerifyCb cb) {
    if (cb && cb != MyVerifyCb) {
        std::lock_guard<std::mutex> lk(g_mtx);
        g_ctx_cb[ctx] = cb;
    }
    g_orig_ctx_set(ctx, mode, MyVerifyCb);
}
\```

BoringSSL 的 verify callback 有 per-CTX 和 per-SSL 两种注册粒度。抖音 Cronet 的主流量都通过 `SSL_CTX_set_custom_verify` 在 CTX 级注册，所以只 hook 这一个 setter 就能覆盖。

不要丢掉原始 callback。原 callback 后面还要被调用，用来维持 Cronet / BoringSSL 内部状态。

---

## 3. 为什么要 per-CTX 保存

不能只用一个全局变量保存“最后一次看到的 callback”。

同一个进程里可能有多套 TLS 使用者：

\```
主 Cronet
媒体下载
PCDN / ODL
WebView / sandbox
其他 native 网络组件
\```

它们各自创建自己的 `SSL_CTX`，注册各自的 verify callback。如果只保存一个全局 callback，后注册的组件会覆盖前面的组件。结果就是：

\```
SSL 对象 A（属于 CTX a）
  -> 被喂给组件 B 的 callback
  -> callback 按 B 的上下文解析 A
  -> 状态错乱或崩溃
\```

所以要按 CTX 对象保存：

```cpp
std::unordered_map<void *, VerifyCb> g_ctx_cb;  // SSL_CTX* -> 这个 CTX 自己的原始 callback
\```

但握手时 BoringSSL 交给回调的是 `SSL*`，不是 `SSL_CTX*`。要回到这张表，还得先从 `SSL*` 反查出它的 `SSL_CTX*`——这就是下一节的事。

---

## 4. 从 `SSL*` 找回 `SSL_CTX*`

主流量通常走 `SSL_CTX_set_custom_verify`。注册时我们保存的是 `ctx -> callback`，但握手时 `MyVerifyCb` 收到的是 `SSL* ssl`，所以需要从 `ssl` 反查 `ctx`。

`SSL_get_SSL_CTX` 很短：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/957122_D2NRZKDMKRWC3AH.webp)

代码里直接按偏移读取：

```cpp
constexpr uintptr_t kSslCtxOff = 0x68;
void *ctx = *reinterpret_cast<void *const *>(
    reinterpret_cast<const char *>(ssl) + kSslCtxOff);
\```

然后用这个 `ctx` 去 `g_ctx_cb` 里找原始 callback，这个值目前看到抖音39.1.0-39.3.0目前最新版本没变化，其余版本我就不一一测试了，需要自行测试。

---

## 5. 握手阶段：`MyVerifyCb`

`MyVerifyCb` 做三件事：

\```
1. 从 SSL* 反查 SSL_CTX*，再到 g_ctx_cb 找回 Cronet 原始 callback
2. 调用原始 callback，让原始校验链路继续执行
3. 根据返回值语义决定是否覆盖
\```

核心逻辑：

```cpp
int MyVerifyCb(void *ssl, uint8_t *out_alert) {
    VerifyCb orig = nullptr;
    {
        std::lock_guard<std::mutex> lk(g_mtx);
        void *ctx = *reinterpret_cast<void *const *>(
                        reinterpret_cast<const char *>(ssl) + kSslCtxOff);
        auto it = g_ctx_cb.find(ctx);
        if (it != g_ctx_cb.end()) orig = it->second;
    }
    int r = orig ? orig(ssl, out_alert) : kSslVerifyOk;
    return r == kSslVerifyRetry ? kSslVerifyRetry : kSslVerifyOk;
}
\```

查找路径只有一条：`ssl -> ctx`（按 §4 的偏移）`-> g_ctx_cb`。如果没找到（`orig == nullptr`），通常意味着 hook 晚于 CTX 创建，或偏移变了；这种情况应当打诊断暴露出来，而不是悄悄放行。

这一步的重点是先调原 callback。它会继续执行 Cronet 的证书校验逻辑，填充后续还会使用的状态。我们只是在它返回之后改最终结果。

custom verify callback 的返回值不是普通 bool：

\```
0 = ssl_verify_ok
1 = ssl_verify_invalid
2 = ssl_verify_retry
\```

同步失败可以覆盖：

\```
origret=1 -> 0
\```

但异步校验不能提前放行：

\```
origret=2 -> 2
\```

`retry(2)` 表示证书校验还在异步流程里。这个时候如果直接改成 `ok(0)`，握手会被提前推进，但 Cronet 内部状态还没准备好，后面很容易触发断言或状态不一致。

---

## 6. 为什么还要 hook `SSL_get_verify_result`

只 hook custom verify setter，可以处理同步失败；但更严格的异步路径里，最终错误码还会被后续读取。

所以补一层：

```cpp
using GetVerifyResultFn = long (*)(void *ssl);
long GetVerifyResultDetour(void *ssl) {
    // 仍调原函数让内部状态走完，只把最终错误码覆盖成 0
    if (g_orig_get_verify_result) g_orig_get_verify_result(ssl);
    return 0;
}
\```

这层的作用是把覆盖动作放到更晚的位置：

\```
custom_verify 阶段：
  尊重 retry，不提前推进握手
verify_result 读取阶段：
  把最终错误码覆盖成 0
\```

这也是整套方案稳定的关键：握手状态按真实流程走，最终结果在读取点再改。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/957122_T7H2DQW37CWE2D4.webp)

---

## 7. 总结

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/957122_TKX8DPY78ZMFPDQ.webp)

这套方案的核心不是直接改 Cronet 的证书校验结果，而是接管 BoringSSL 的 `custom_verify` callback 注册点。最终只剩两个 hook 点、一张 map：

\```
注册阶段：
  Cronet 调 SSL_CTX_set_custom_verify 注册 verify callback
  hook 这个 setter，把原 callback 存进 g_ctx_cb[ctx]
  把真正写入 BoringSSL 的 callback 换成 MyVerifyCb
握手阶段：
  BoringSSL 调 MyVerifyCb
  MyVerifyCb 用 ssl->ctx 偏移反查 g_ctx_cb，找回并调用 Cronet 原 callback
  retry(2) 原样返回
  同步失败(1) 覆盖为 ok(0)
结果读取阶段：
  SSL_get_verify_result 覆盖为 0
\```

>
> 不要跳过原始校验流程；让它把状态喂完整，再在返回值边界上做最小改动。
>
>
>

---

# 回复

## 回复 by mb_4nrpVMxJ (#2)

*2026-6-29 09:01*

666

## 回复 by huangjw (#3)

*2026-6-29 09:13*

看看先666

## 回复 by 夜惜风雨 (#4)

*2026-6-29 09:35*

66666666666

## 回复 by 小尘0000 (#5)

*2026-6-29 09:43*

666

## 回复 by git_31575Neigb (#6)

*2026-6-29 09:49*

66666666666

## 回复 by YoungBai (#7)

*2026-6-29 09:53*

666

## 回复 by nuomida (#8)

*2026-6-29 10:03*

感谢分享

## 回复 by jyotidwi (#9)

*2026-6-29 10:21*

666

## 回复 by 4Chan (#10)

*2026-6-29 10:28*

学习一下

## 回复 by 长短短 (#11)

*2026-6-29 10:33*

133123223

## 回复 by MaYil (#12)

*2026-6-29 10:35*

感谢分享

## 回复 by 星落黎明 (#13)

*2026-6-29 10:41*

感谢分享

## 回复 by mb_dwxaumtm (#14)

*2026-6-29 11:06*

1

## 回复 by 熊猫吃鱼 (#15)

*2026-6-29 11:19*

666

## 回复 by mb_mlyojneh (#16)

*2026-6-29 11:33*

making

## 回复 by Snowman_Liam (#17)

*2026-6-29 12:03*

6666

## 回复 by mb_paopxhtx (#18)

*2026-6-29 12:17*

6666

## 回复 by linglonger (#19)

*2026-6-29 12:42*

66666666

## 回复 by wx_插曲 (#20)

*2026-6-29 13:28*

666666666666666

## 回复 by 我就是小熊猫 (#21)

*2026-6-29 14:26*

6666

## 回复 by Imxz (#22)

*2026-6-29 14:40*

tql

## 回复 by ovo_帮我不c (#23)

*2026-6-29 14:52*

1

## 回复 by 街道办事处 (#24)

*2026-6-29 14:53*

1

## 回复 by mb_lfwgtxdb (#25)

*2026-6-29 14:58*

感谢分享

## 回复 by 寻梦之璐 (#26)

*2026-6-29 16:03*

666

## 回复 by 黑屏 (#27)

*2026-6-29 16:32*

666

## 回复 by 086Love (#28)

*2026-6-29 16:41*

学习

## 回复 by dsr000 (#29)

*2026-6-29 16:44*

1

## 回复 by fjqisba (#30)

*2026-6-29 16:51*

这么多人研究dy吗

## 回复 by chionyuna (#31)

*2026-6-29 16:52*

666

## 回复 by mb_kiwccpyo (#32)

*2026-6-29 17:52*

厉害

## 回复 by mb_jhohnbzu (#33)

*2026-6-29 18:10*

1

## 回复 by mb_pesxllvn (#34)

*2026-6-29 18:24*

666

## 回复 by aue (#35)

*2026-6-29 19:15*

感谢分享

## 回复 by puppet_w (#36)

*2026-6-29 20:07*

牛哇

## 回复 by SandKing (#37)

*2026-6-30 10:04*

666

## 回复 by mb_qimctavn (#38)

*2026-6-30 11:12*

6

## 回复 by 钱钱钱￥ (#39)

*2026-6-30 11:17*

学习

## 回复 by git_71735namngsec-netizen (#40)

*2026-6-30 11:17*

666

## 回复 by 红皮西瓜 (#41)

*2026-6-30 11:44*

666

## 回复 by mb_uvyukvot (#42)

*2026-6-30 16:03*

666

## 回复 by younghare (#43)

*2026-6-30 16:19*

学习一下

## 回复 by mb_ykavguun (#44)

*2026-6-30 19:42*

1

## 回复 by 文西哥 (#45)

*2026-6-30 19:54*

感谢分享

## 回复 by Gryffindoss (#46)

*2026-7-1 10:01*

6666

## 回复 by luckbbs (#47)

*2026-7-1 10:18*

感谢分享

## 回复 by 学计算机睡觉 (#48)

*2026-7-1 11:03*

666

## 回复 by wx-小萌新 (#49)

*2026-7-1 11:20*

1

## 回复 by 简单的简单 (#50)

*2026-7-1 11:42*

666

## 回复 by A00乐淘 (#51)

*2026-7-1 14:30*

支持下

## 回复 by 补丁布丁 (#52)

*2026-7-1 14:41*

支持一下

## 回复 by 补丁布丁 (#53)

*2026-7-1 14:42*

感谢分享 支持以下

## 回复 by mb_hiqvmjsd (#54)

*2026-7-1 15:43*

666

## 回复 by mb_cbgtaveo (#55)

*2026-7-1 16:52*

66666666666

## 回复 by mb_qanhjohb (#56)

*2026-7-1 17:39*

感谢分享

## 回复 by iBa0 (#57)

*2026-7-1 21:14*

1

## 回复 by 带壳的蜗牛 (#58)

*2026-7-2 08:10*

666

## 回复 by mb_fidppcok (#59)

*2026-7-2 08:28*

感谢分享

## 回复 by wx_啊啊啊啊 (#60)

*2026-7-2 15:28*

学习学习

## 回复 by 荷蒉丈人 (#61)

*2026-7-2 17:02*

1

## 回复 by 看snowadfad (#62)

*2026-7-2 17:27*

6666

## 回复 by mb_beayjoxd (#63)

*2026-7-2 18:51*

感谢分享

## 回复 by mb_euhyowpw (#64)

*2026-7-2 20:12*

666

## 回复 by FMNS (#65)

*2026-7-3 04:28*

6666

## 回复 by JuZi420 (#66)

*2026-7-3 09:23*

感谢分享

## 回复 by GeeKc (#67)

*2026-7-3 10:28*

111

## 回复 by YANG、 (#68)

*2026-7-3 11:07*

感谢分享

## 回复 by 上官兮唐 (#69)

*2026-7-3 11:32*

感谢分享，学习

## 回复 by 黄文静 (#70)

*2026-7-3 18:00*

感谢分享

## 回复 by x1a0f3n9 (#71)

*2026-7-4 05:37*

感谢分享，这思路真好

## 回复 by mb_owfvtagq (#72)

*2026-7-4 07:29*

非常支持你的观点！

## 回复 by 安稳_ (#73)

*2026-7-4 18:29*

感谢大佬 么么哒..正发愁怎么跳过呢

## 回复 by mb_kqoewvav (#74)

*2026-7-4 20:13*

感谢分享

## 回复 by 流星沦落 (#75)

*2026-7-4 23:49*

6666666

## 回复 by wx_白鸟之诗 (#76)

*2026-7-5 09:01*

1

## 回复 by 奋斗der小鸟 (#77)

*2026-7-5 15:25*

![image](https://bbs.kanxue.com/view/img/face/057.gif)

## 回复 by mb_vujvqmjj (#78)

*2026-7-5 21:18*

666

## 回复 by SilentXC (#79)

*2026-7-6 13:51*

1

## 回复 by 大河马_579155 (#80)

*2026-7-6 21:03*

感谢分享

## 回复 by 大脚板忍者 (#81)

*2026-7-6 21:22*

感谢分享

## 回复 by mb_ekszwdeo (#82)

*2026-7-6 21:26*

感谢分享

## 回复 by git_84461osscv (#83)

*2026-7-7 00:38*

牛逼，找到了哈哈总算，欸
看了那么多文章今天

## 回复 by woaiziyou (#84)

*2026-7-7 09:28*

感谢分享

## 回复 by 学着学逆向 (#85)

*2026-7-7 17:38*

look look

## 回复 by 云觞 (#86)

*2026-7-7 17:57*

感谢分享

## 回复 by Orange88 (#87)

*2026-7-8 10:53*

感谢分享

## 回复 by wx_kx92911 (#88)

*2026-7-9 09:52*

感谢分析

## 回复 by B.M.K (#89)

*2026-7-9 10:21*

1

## 回复 by 巡夜人 (#90)

*2026-7-14 04:56*

感谢你的贡献，论坛因你而更加精彩！

## 回复 by cjja爱之恋 (#91)

*2026-7-15 03:08*

支持，，，

## 回复 by mb_kxdmjbxj (#92)

*2026-7-15 15:55*

666

## 回复 by 桐人dx (#93)

*2026-7-15 15:59*

666

## 回复 by lhnr0pe (#94)

*2026-7-15 17:06*

666666

## 回复 by mb_cezdpjbw (#95)

*2026-7-16 13:45*

1

## 回复 by sjshb57 (#96)

*2026-7-16 18:41*

好厉害

## 回复 by 阿福哦哦 (#97)

*2026-7-17 05:34*

666

## 回复 by kris_574089 (#98)

*2026-7-17 10:17*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_ynvaddwg (#99)

*2026-7-17 12:49*

感谢分享

## 回复 by uni7corn (#100)

*2026-7-20 17:59*

感谢分享

## 回复 by 老衲很年轻 (#101)

*2026-7-21 15:53*

特别棒，点赞收藏了

## 回复 by 错过 (#102)

*2026-7-21 16:07*

666

## 回复 by mb_cdcczvtr (#103)

*2026-7-22 00:16*

11

## 回复 by huluxia (#104)

*2026-7-22 14:10*

牛逼

## 回复 by mb_wcezgawj (#105)

*2026-7-23 02:16*

学习一下

## 回复 by kingking888 (#106)

*2026-7-23 11:02*

666

## 回复 by ReverseApp (#107)

*2026-7-25 09:49*

感谢分享

## 回复 by xtyuns (#108)

*2026-7-25 10:44*

666

## 回复 by git_38916onekb (#109)

*2026-7-25 11:06*

感谢分享

## 回复 by mb_bmpurgym (#110)

*2026-7-25 11:26*

111

## 回复 by wx_相逢 (#111)

*2026-7-27 15:01*

666

## 回复 by Lpangs (#112)

*2026-7-30 11:51*

感谢分享

## 回复 by mb_jhwzigll (#113)

*2026-7-31 16:36*

1111111111

## 回复 by 伊苏尔德 (#114)

1

## 回复 by E_Obj (#115)

感谢分享

## 回复 by mb_hqppvdoa (#116)

看一下，感谢分享

## 回复 by mb_sucdkadh (#117)

看看思路

## 回复 by mb_jwvcvtfi (#118)

thanks

## 回复 by mb_tewbhakr (#119)

看看

## 回复 by J1rrY (#120)

![image](https://bbs.kanxue.com/view/img/face/022.gif)

## 回复 by git_72642juancv-code (#121)

感谢分享

## 回复 by wx_pyroxenite (#122)

感谢分享

## 回复 by mb_ooaxqkvk (#123)

感谢分享

## 回复 by mb_irhdtnzm (#124)

1

## 回复 by mb_xmedaecc (#125)

1

## 回复 by wx_Huber Barrientos (#126)

666

## 回复 by mb_axpeuqgo (#127)

赞
