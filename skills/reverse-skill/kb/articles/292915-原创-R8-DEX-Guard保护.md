---
title: '[分享][原创]R8 DEX Guard保护'
url: https://bbs.kanxue.com/thread-292915.htm
tid: 292915
author: mb_xpdephnu
date: '2026-09-11'
tags: [Android安全, 分享, 程序开发]
crawled_at: '2026-09-14T09:02:30+00:00'
replies: 14
---

DEX Guard2.0

核心混淆（独立生效）

![image](https://bbs.kanxue.com/upload/attach/202609/1090061_B74KGB4WYV575KP.webp)

选项 强度 说明

控制流平坦化 ★★★★★ 打乱控制流结构，显著提升逆向难度

符号混淆 ★★★★★ 重命名类、方法、字段，去除可读性

逻辑混淆 ★★★★☆ 插入等价逻辑变换

全局状态耦合 ★★★☆☆ 将方法状态耦合至全局，增加分析成本

需配合 DEX 优化生效

· 花指令（优化时）

· 扁平化 2.0（优化时）

· 数字混淆（优化时）

· 指令替换（优化时）

基础选项

· 去除调试信息

· 加密资源 ID

· 只读取规则内类

· 不处理接口类

· 字符串加密

· DEX 优化

隐身保护

· 隐身保护（合并开关）★★★★★

· 插入虚假分支

· 字符串多层加密

[**R8 DEX Guard**](https://github.com/cvbzzz/R8-DEX-Guard/releases)

---

# 回复

## 回复 by mb_kflrccfl (#2)

404

## 回复 by mb_xpdephnu (#3)

>
> [mb_kflrccfl](https://bbs.kanxue.com/user-944800.htm)
>  404
>

已修复

## 回复 by 風輕澐淡 (#4)

感谢分享！

## 回复 by 夜惜风雨 (#5)

66666666666

## 回复 by mb_4nrpVMxJ (#6)

6666

## 回复 by 万神fake (#7)

谢谢楼主分享

## 回复 by guardia (#8)

看看

## 回复 by iBa0 (#9)

111

## 回复 by qmqsyz (#10)

感谢分享

## 回复 by k4y0z (#11)

666

## 回复 by Gryffindoss (#12)

123

## 回复 by TeamAR (#13)

666

## 回复 by mb_vwdfywtj (#14)

123

## 回复 by mb_jwvcvtfi (#15)

66666
