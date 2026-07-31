---
title: jadx二次开发- 实现对类的所有字段和方法生成hook脚本
url: https://bbs.kanxue.com/thread-276973.htm
tid: 276973
author: iyue_t
date: '2023-04-24'
tags: [Android安全, 逆向分析, 协议分析, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T14:49:49+08:00'
replies: 15
---

# jadx二次开发

## 前言

| 1234 | `-` `最近需要分析Android Java层混淆后的代码,看的欲仙欲死.``-` `jadx 目前支持对单个字段或方法生成frida hook脚本.``-` `在实际工作中,往往连蒙带猜的去分析,通过frida,xposed,objection等工具去验证猜测.``-` `实在是有点麻了,在使用时发现只能一个方法生成脚本很不方便,而objection对类进行watch时又不能看到参数返回值,也没有扩展性,从而产生了今天这篇文章以及修改` |
|-|-|

- jadx的项目不管是架构还是代码风格看的是那么的赏心悦目.

## 上代码

- 其实代码很简单主要是jadx的代码封装的太好了,几句代码就实现了.
- 通过修改生成类的hook脚本,遍历所有方法和字段调用封装好的直接生成拼接完事儿,原本只有一句use class

| 12345678910111213 | `private String generateFridaSnippet(JNode node) {``if` `(node instanceof JMethod) {``return` `generateMethodSnippet((JMethod) node,false);``}``/``/` `主要修改生成``class``类的hook``if` `(node instanceof JClass) {``return` `generateClassSnippet((JClass) node,true);``}``if` `(node instanceof JField) {``return` `generateFieldSnippet((JField) node,false);``}``throw new JadxRuntimeException(``"Unsupported node type: "` `+` `(node !``=` `null ? node.getClass() :` `"null"``));``}` |
|-|-|

| 1234567891011 | `private String generateClassSnippet(JClass jc,boolean isAll) {``JavaClass javaClass` `=` `jc.getCls();``String classSnippet` `=` `generateClassSnippet(jc);``for` `(JavaField field : javaClass.getFields()) {``classSnippet``+``=``"\n"``+``generateFieldSnippet(new JField(field,jc),true);``}``for` `(JavaMethod method : javaClass.getMethods()) {``classSnippet``+``=``"\n"``+``generateMethodSnippet(new JMethod(method,jc),true);``}``return` `classSnippet;``}` |
|-|-|

## 看一下效果

 ![生成的脚本](https://bbs.kanxue.com/upload/attach/202304/853140_YA5P292J5DN6T2B.png)

- github地址 [jadx for iyue](https://github.com/ys1231/jadx/releases/latest)文件有点大就不上传了.
- 附件有patch可参考自行修改

上传的附件：
- 0001-feat-FridaAction-fire-Class-hook.patch

（6.34kb，14次下载）

---

# 回复

## 回复 by 秋狝 (#2)

*2023-4-24 09:16*

感谢分享

## 回复 by Skyart (#3)

*2023-4-24 09:30*

mark

## 回复 by shinratensei (#4)

*2023-4-24 09:44*

tql

## 回复 by clz3216 (#5)

*2023-4-24 11:50*

好东西好东西

## 回复 by vay (#6)

*2023-4-24 12:18*

谢谢分享，![image](https://bbs.kanxue.com/view/img/face/78.gif)你发布的Release版本能否兼容一下jdk8呢？

## 回复 by iyue_t (#7)

*2023-4-27 22:11*

>
> [vay](https://bbs.kanxue.com/user-916888.htm)
>
>  谢谢分享，[em_78]你发布的Release版本能否兼容一下jdk8呢？
>
>

你要不要下载下来自己编译一下,不需要任何额外的配置.

## 回复 by vay (#8)

*2023-4-30 07:19*

>
> [iyue_t](https://bbs.kanxue.com/user-853140.htm)
>
>  你要不要下载下来自己编译一下,不需要任何额外的配置.
>
>

功能可以的![image](https://bbs.kanxue.com/view/img/face/63.gif)，已经在用了

## 回复 by wx_倾尽天下 (#9)

*2023-5-2 10:46*

感谢分享~![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 手酸哥 (#10)

*2023-5-5 11:29*

感谢分享~

## 回复 by 万里星河 (#11)

*2023-5-7 00:22*

不太明白hook字段是什么意思 能看到程序在什么时间什么地点引用了哪个类的哪个字段吗？![image](https://bbs.kanxue.com/view/img/face/14.gif)

## 回复 by iyue_t (#12)

*2023-5-8 23:47*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  不太明白hook字段是什么意思 能看到程序在什么时间什么地点引用了哪个类的哪个字段吗？[em_14]
>
>

就是获取字段值,有些类有执行线程,而线程可能执行不同任务,这些任务是通过这个类的某一个字段控制的,此时获取字段值就有用了.

## 回复 by IX221 (#13)

*2023-6-1 23:15*

mark

## 回复 by qqsunqiang (#14)

*2024-3-26 07:58*

./jadx-gui/src/main/java/jadx/gui/ui/codearea/FridaAction.java
import jadx.api.JavaMethod;
generateClassSnippet((JClass) node);多加个参数true
在添加一个方法:如下
private String generateClassSnippet(JClass jc, boolean isAll) {
        JavaClass javaClass = jc.getCls();
        String classSnippet = generateClassSnippet(jc);
        for (JavaField field : javaClass.getFields()) {
            classSnippet = classSnippet + "\n" + generateFieldSnippet(new JField(field, jc));
        }
        for (JavaMethod method : javaClass.getMethods()) {
            classSnippet = classSnippet + "\n" + generateMethodSnippet(new JMethod(method, jc));
        }
        return classSnippet;
    }
对这一个文件修改，传个FridaAction.class ,对官方版替换就可以了。

## 回复 by xdnice (#15)

*2024-3-26 08:42*

谢谢分享

## 回复 by calleng (#16)

*2024-7-3 00:22*

jadx , 和r0yuse 魔改媲美。 虽然没用过。
