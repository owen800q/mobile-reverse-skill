---
title: '[原创] 分享一个 Android / iOS 逆向 Skill：让 Claude Code、Codex 按证据推进分析'
url: https://bbs.kanxue.com/thread-293328.htm
tid: 293328
author: Wika
date: '2026-10-26'
tags: [Android安全, 原创, 逆向分析, 协议分析, 工具脚本]
crawled_at: '2026-10-26T09:02:08+00:00'
replies: 24
---

```html
# 分享一个 Android / iOS 逆向 Skill：让 Claude Code、Codex 按证据推进分析

大家好，最近整理并持续维护了一个移动端逆向项目 **mobile-reverse-skill**，想分享给看雪的朋友交流。

项目地址：<https://github.com/owen800q/mobile-reverse-skill>

平时使用 AI 辅助逆向，经常遇到几个问题：分析步骤比较零散，静态代码和运行时数据对不上；分析到一半换个会话，又需要重新交代上下文；有时模型看到几个常量，就过早判断用了某种加密算法。

这个项目尝试把分析过程整理成一套可复用的 Skill，让 Claude Code 和 Codex 按阶段调用工具、记录证据，并验证分析结果。适合移动端 CTF、逆向学习，以及授权范围内的应用安全研究。

## 主要功能

- **Android 分析：**结合 jadx、apktool 和 ASC，检查 APK、定位接口及请求构造代码，并进一步追踪 Java / JNI / native 调用链。
- **运行时观察：**结合 Frida，以及设备和内核条件允许时的 ecapture、stackplz，把实际运行数据与静态代码对应起来。
- **Native 与算法分析：**支持 IDA Pro 的 MCP 或 headless 分析路径，结合常量、指令特征和样本验证，辅助还原签名及加密逻辑。
- **iOS 分析：**提供基于 Apple Silicon Mac + PlayCover 的分析流程，覆盖 IPA 检查、ObjC / Swift 信息和本地 Frida 观察等。
- **分析记录与交接：**使用统一的 `findings.json` 保存发现、证据和待验证假设，方便后续会话接着分析。

## 比较重视的一点：结论需要验证

项目会区分“观察到的事实”“推测”和“已验证结论”。

例如，看到一个疑似加密常量，并不足以确认算法；还原签名后，也需要用实际样本重新计算、比对，并通过修改输入的对照测试验证。

工具没有成功运行、分析受阻或证据不足时，也应该如实记录。

## 安装与使用

先克隆仓库：

\```
git clone https://github.com/owen800q/mobile-reverse-skill.git
cd mobile-reverse-skill
\```

安装到 Claude Code：

\```
./install.sh
\```

安装到 Codex：

\```
./install.sh --agent codex
\```

两边共用当前仓库中的 Skill，方便持续更新：

\```
./install.sh --agent both --link
\```

Claude Code 中可通过 `/reverse-skill` 指定目标和分析任务；Codex 中使用 `$reverse-skill`。

例如：

\```
/reverse-skill 分析本地 CTF APK，定位 flag 校验函数，梳理 Java 到 JNI 的调用链，并验证还原出的算法。
\```

Skill 本身不会自动配好逆向环境，具体能力取决于本机工具、设备及权限。例如，Android 的 eBPF 分析需要满足对应的设备和内核条件。

## 来源与交流

项目整合并改编了多个社区逆向 Skill 和工具的思路，上游来源在 README 的 Credits 中列出，也感谢原作者们的分享。

目前仍在迭代，欢迎大家拿 CTF 样本或自己有权分析的测试应用试用。如果遇到工具兼容问题、流程不合理，或者分析结论缺少证据，欢迎提 Issue、PR，也欢迎在楼里交流具体案例。

觉得有用的话，欢迎 Star 支持。

GitHub：<https://github.com/owen800q/mobile-reverse-skill>

\```

---

# 回复

## 回复 by hackbs (#2)

66666666666

## 回复 by 怜音 (#3)

6666

## 回复 by jccforever (#4)

66666666666

## 回复 by method (#5)

1

## 回复 by mb_elqwyvnm (#6)

1111

## 回复 by 熊猫吃鱼 (#7)

6666

## 回复 by Xx_gg (#8)

666

## 回复 by System's (#9)

66666

## 回复 by mb_dovfssxz (#10)

666666

## 回复 by mb_ykavguun (#11)

看看

## 回复 by guijingwen (#12)

66

## 回复 by mb_vxufgfcw (#13)

666

## 回复 by xingbing (#14)

看看

## 回复 by 九黎 (#15)

666

## 回复 by dextoart (#16)

6666

## 回复 by git_82460xiadeshu (#17)

666

## 回复 by mb_rdhblxpy (#18)

111

## 回复 by cnhuaWu (#19)

66666

## 回复 by fjqisba (#20)

777

## 回复 by xianhuimin (#21)

看看

## 回复 by kzx0808 (#22)

6

## 回复 by breakM (#23)

66666

## 回复 by breakM (#24)

66666

## 回复 by GEKEZYX (#25)

666
