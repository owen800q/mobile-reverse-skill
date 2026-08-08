---
title: '[原创]美团大众点评降级抓包LSPosed插件-反混淆通用思路'
url: https://bbs.kanxue.com/thread-291926.htm
tid: 291926
author: 太岁又沐风
date: '2026-07-08'
tags: [Android安全, 原创]
crawled_at: '2026-08-08T10:03:59+00:00'
replies: 50
---

# 美团大众点评降级抓包LSPosed插件-反混淆通用

如果只需要插件，不想看技术实现，可以关注公众号，发送“美团插件”
![image](https://bbs.kanxue.com/upload/attach/202607/957122_6FKSHMMUZHFSA8J.png)
美团系的APP都可以用，因为虽然类名和方法名不一样，但是做了方法搜寻对抗混淆，所以通用

## 1. 先定位网络配置

---

先搜：

\```
nt.defaulttunnel
\```

![image](https://bbs.kanxue.com/upload/attach/202607/957122_AXAURTTPNUQXEXR.png)
其中 `nt.defaulttunnel` 很关键。它决定默认通道，比如 `cip`、`http`。
![image](https://bbs.kanxue.com/upload/attach/202607/957122_6B5GVDHYBTXAWDR.png)
然后找到引用
一个方法读取这个字段，返回 `2` 或 `3`，返回3走的就是http，把这个hook掉返回3就可以了，走的就是http

```java
return (!"cip".equals(this.xxx) && "http".equals(this.xxx)) ? 3 : 2;
\```

![image](https://bbs.kanxue.com/upload/attach/202607/957122_3A8EDE5K53GPFH5.png)

模块里自动定位的流程就是：

\```
搜 "nt.defaulttunnel"
找到被赋值的成员字段
找读取这个字段的 int 无参方法
方法里包含 "cip"、"http"、返回 2/3
hook 这个方法，直接返回3
\```

## 2. 实现反混淆hook

---

用 dexlib2 静态扫 dex，不依赖类名、方法名、字段名、Robust。

### 依赖

```gradle
implementation "org.smali:dexlib2:2.5.2"
implementation "de.robv.android.xposed:api:82"
compileOnly "de.robv.android.xposed:api:82"
\```

基于dexlib2库，通过对DEX字节码进行模式匹配

### 1. 找字段（定位 nt.defaulttunnel 配置）

要找的字节码模式是：optString 读配置 -> move-result-object 拿结果 -> iput-object 存进成员变量。

```java
// 1. 先看有没有 "nt.defaulttunnel" 和 "cip" 两个常量
if (!hasKey || !hasCip) continue;

// 2. 找到 invoke-virtual 调用 optString 的地方
if (isInvokeOptString(insn)) {
    // 3. 看下一条是不是 move-result-object，拿返回值寄存器
    Integer moveResultReg = nextMoveResultObjectRegister(insns, i);
    if (moveResultReg == null) continue;

    // 4. 在后面几条指令里找 iput-object，且寄存器对上号
    FieldReference field = findNextIputObjectSameRegister(insns, i + 1, moveResultReg);
    if (field != null && "Ljava/lang/String;".equals(field.getType())) {
        return new FieldSig(field.getDefiningClass(), field.getName(), field.getType());
    }
}
\```

### 2. 找方法（定位返回 int 的选择器）

不硬匹配，方法特征。
在同一个类中，找那个无参且返回int、读取了那个“nt.defaulttunnel”字段（这个是关键，几乎百发百中）、同时引用了"cip"/"http"两个字符串和2/3两个数字常量，并调用了String.equals比较的方法。

### 3. 转反射（拿到可调用的 Method）

定位到签名后，把 Dex 格式的类型描述符（Lcom/xxx;）转成 Java 类名（com.xxx），然后直接反射拿方法。

```java
// 把 "Lcom/example/MyClass;" 变成 "com.example.MyClass"
String className = dexTypeToJava(sig.owner);
Class<?> clazz = Class.forName(className, false, cl);

// 参数类型同样转一遍
Class<?>[] params = new Class<?>[sig.params.size()];
for (int i = 0; i < sig.params.size(); i++) {
    params[i] = dexTypeToClass(sig.params.get(i), cl);
}

// 反射获取并爆破
Method m = clazz.getDeclaredMethod(sig.name, params);
m.setAccessible(true);
return m;
\```

## 3. 成果展示

轻松抓到团价格，大众点评同理
![image](https://bbs.kanxue.com/upload/attach/202607/957122_QQFFNBM7DSUBC33.png)

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2026-7-8 23:46*

感谢分享

## 回复 by 九黎 (#3)

*2026-7-9 08:44*

tql

## 回复 by mb_wqvhhpxn (#4)

*2026-7-9 09:45*

学习

## 回复 by wx_kx92911 (#5)

*2026-7-9 09:51*

感谢分析

## 回复 by huangjw (#6)

*2026-7-9 09:53*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by B.M.K (#7)

*2026-7-9 10:04*

1

## 回复 by xets007 (#8)

*2026-7-9 10:28*

1

## 回复 by mb_vghyvbhn (#9)

*2026-7-9 11:15*

1

## 回复 by 海带 (#10)

*2026-7-9 11:35*

1

## 回复 by mb_mildqryr (#11)

*2026-7-9 15:33*

1

## 回复 by 窗外的荡秋千 (#12)

*2026-7-9 15:38*

1

## 回复 by Da_ (#13)

*2026-7-9 15:51*

666

## 回复 by mb_pmgifpme (#14)

*2026-7-10 13:39*

1

## 回复 by 南上加蓝 (#15)

*2026-7-10 13:40*

1

## 回复 by hanjiefang (#16)

*2026-7-10 15:14*

1

## 回复 by YooHaa (#17)

*2026-7-10 16:13*

666

## 回复 by hacker521 (#18)

*2026-7-10 16:14*

1

## 回复 by mb_sqetvntx (#19)

*2026-7-10 17:31*

学习

## 回复 by git_84461osscv (#20)

*2026-7-11 02:28*

牛逼啊，谢谢分享

## 回复 by shuaiaimei (#21)

*2026-7-11 17:21*

学习了。

## 回复 by linglonger (#22)

*2026-7-11 18:52*

111111111111

## 回复 by System's (#23)

*2026-7-11 19:06*

看看

## 回复 by 咸鱼…… (#24)

*2026-7-12 09:54*

666

## 回复 by iBa0 (#25)

*2026-7-12 15:43*

123

## 回复 by TheLuckyOne (#26)

*2026-7-12 16:37*

tql

## 回复 by kingking888 (#27)

*2026-7-12 16:45*

666

## 回复 by waddle (#28)

*2026-7-12 18:21*

666

## 回复 by mb_iiumogmn (#29)

*2026-7-12 22:59*

感谢分享

## 回复 by mb_auylfslb (#30)

*2026-7-13 10:48*

6

## 回复 by Arsylk (#31)

*2026-7-13 13:49*

11

## 回复 by mb_koixqizd (#32)

*2026-7-13 16:32*

学习

## 回复 by mb_bgqsbxew (#33)

*2026-7-13 18:28*

666

## 回复 by mb_xqpwqark (#34)

*2026-7-14 10:31*

1

## 回复 by mb_uulqeyon (#35)

*2026-7-14 10:45*

1

## 回复 by yyyyy——— (#36)

*2026-7-14 17:17*

11

## 回复 by saf3d0s (#37)

*2026-7-15 14:19*

666

## 回复 by eup0r1e (#38)

*2026-7-15 14:52*

1

## 回复 by 无忧序列号 (#39)

*2026-7-15 16:03*

1

## 回复 by 云觞 (#40)

*2026-7-15 16:48*

666

## 回复 by mb_ngvbatem (#42)

*2026-7-17 11:54*

1111

## 回复 by 喜欢就去抢啊 (#43)

*2026-7-21 12:53*

感谢分享

## 回复 by FMNS (#44)

*2026-7-21 13:46*

123

## 回复 by 无视红绿灯 (#45)

*2026-7-23 11:57*

1111

## 回复 by 机车王子 (#46)

*2026-7-23 17:09*

这个讨论对我很有帮助，谢谢！

## 回复 by ALCFree (#47)

*2026-7-23 20:46*

牛啊

## 回复 by ldzhjn (#48)

*2026-7-23 20:51*

666

## 回复 by mb_ooaxqkvk (#49)

123

## 回复 by mb_pklvtpgn (#50)

看看

## 回复 by 天道happy (#51)

666

## 回复 by mb_ugsctkiu (#52)

666
