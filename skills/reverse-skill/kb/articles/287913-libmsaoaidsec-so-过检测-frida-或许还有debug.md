---
title: '[原创] libmsaoaidsec.so 过检测 frida（或许还有debug）'
url: https://bbs.kanxue.com/thread-287913.htm
tid: 287913
author: wx_小友
date: '2025-08-06'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-08T10:50:55+00:00'
replies: 27
---

之前写了一篇，但是那种办法不稳定，而且并没有普遍性，今天在弄一个体育类的APP时，发现还是会不时被检测，所以有找到一种新的hook方式，可以过掉frida的检测。没有测试debug是否也一起过了，  应该是一起过了的。

先说下步骤。

1、打印下so的加载，看哪个so检测的。

2、测试是在哪里被检测的，（.init_proc或jni_load）。

3、替换对应的方法。

上代码。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263 | `function` `my_hook_dlopen(soName) {``var` `name = Module.findExportByName(``null``,``"android_dlopen_ext"``);``console.log(name);``Interceptor.attach(name, {``onEnter:``function` `(args) {``var` `pathptr = args[0];``if` `(pathptr !== undefined && pathptr !=``null``) {``var` `path = ptr(pathptr).readCString();``console.log(path);` `if` `(path.indexOf(soName) != -1) {``hook_call_constructors()``}``}``},``onLeave:``function` `(retval) {``if` `(``this``.is_can_hook) {``dump_so(soName);``}``},``});``}` `var` `first =``false``;``function` `hook_call_constructors() {``var` `linker = Process.findModuleByName(``"linker64"``);``Interceptor.attach(linker.base.add(0x4A174), {``onEnter:``function` `() {``var` `module = Process.findModuleByName(``"libmsaoaidsec.so"``);``if` `(module && !first) {``first =``true``;``Interceptor.replace(``module.base.add(0x14400),``new` `NativeCallback(``function` `() {``console.log(``"Bypassed sub_14400"``);``},``"void"``,``[]``)``);` `Interceptor.replace(module.base.add(0x13A4C),``new` `NativeCallback(``function` `(vm, reserved) {``console.log(``"[+] Fake JNI_OnLoad called!"``);` `// 原始功能（可选调用原函数）``// const old_ret = old_jni_onload(vm, reserved);` `// 返回版本号（通常0x10004 for JNI 1.4）``return` `0x10006;``// JNI 1.6``},``"int"``, [``"pointer"``,``"pointer"``]``))``}``},``});``}` `function` `main() {``my_hook_dlopen(``"libmsaoaidsec.so"``);``}``setImmediate(main);` |
|-|-|

解释一下里面用到的地址。

linker.base.add(0x4A174)

这个对应的是linker64的 __dl__ZN6soinfo17call_constructorsEv  在android 11中没有被导出，所以直接拿到这个文件IDA查找到了这个地址。

module.base.add(0x14400)

这个是对应的 libmsaoaidesc.so的 .init_proc 方法。

module.base.add(0x13A4C)

这个是 JNI_LOAD 方法。

没有更多内容了，  简单吧。。   哈哈哈。

---

# 回复

## 回复 by ty1937 (#2)

*2025-8-11 09:25*

我把我手机的__dl__ZN6soinfo17call_constructorsEv  改了，我的目标测试app,.init_proc 和JNI_LOAD  地址和你的是一样的，但是 -U -f 启附加了脚本，依旧会退出，
Bypassed sub_14400
[+] Fake JNI_OnLoad called!
........
Process terminated

## 回复 by wx_小友 (#3)

*2025-8-11 13:53*

>
> [ty1937](https://bbs.kanxue.com/user-857508.htm)
>
>  我把我手机的__dl__ZN6soinfo17call_constructorsEv 改了，我的目标测试app,.init_proc 和JNI_LOAD 地址和你的是一样的，但是 -U -f 启附 ...
>
>

方便告知下app吗？ 共同学习下

## 回复 by ty1937 (#4)

*2025-8-11 16:43*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_小友](https://bbs.kanxue.com/user-783296.htm)
>
>  方便告知下app吗？ 共同学习下
>
>

私你了

## 回复 by 陈可牛 (#5)

*2025-8-11 16:55*

其实有个更简单的方法，那就是删除so，或者阻止so的加载，，，

## 回复 by aq88 (#6)

*2025-8-11 23:13*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  其实有个更简单的方法，那就是删除so，或者阻止so的加载，，，
>
>

大佬能具体说下么？有个app怎么也过不了，好像还有爱加密的壳，里面也有libmsaoaidsec.so

## 回复 by aq88 (#7)

*2025-8-11 23:14*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_小友](https://bbs.kanxue.com/user-783296.htm)
>
>  方便告知下app吗？ 共同学习下
>
>

同求，学习，自己测试几个有libmsaoaidsec.so 怎么也过不去，抓狂

## 回复 by 陈可牛 (#8)

*2025-8-12 11:47*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_hojnmyba](https://bbs.kanxue.com/user-1046428.htm)
>
>  大佬能具体说下么？有个app怎么也过不了，好像还有爱加密的壳，里面也有libmsaoaidsec.so
>
>

发apk，我瞅瞅

## 回复 by aq88 (#9)

*2025-8-12 19:41*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  发apk，我瞅瞅
>
>

https://www.123684.com/s/o5Wajv-oi5cv?pwd=TgHE 私信不了，发这里不知道是否违规

## 回复 by 陈可牛 (#10)

*2025-8-12 21:22*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  aq88](https://bbs.kanxue.com/user-1046428.htm)
>
>  https://www.123684.com/s/o5Wajv-oi5cv?pwd=TgHE 私信不了，发这里不知道是否违规
>
>

![image](https://bbs.kanxue.com/upload/attach/202508/794149_FRQERX2QBT7ESPY.webp)

啥问题都没

## 回复 by mb_vzsnpfhs (#11)

*2025-8-13 14:50*

直接删了也可以

## 回复 by aq88 (#12)

*2025-8-15 11:48*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>
>
>
>
>
>
>  aq88
>
>
>
>  https://www.123684.com/s/o5Wajv-oi5cv?pwd=TgHE 私信不了，发这里不知道是否违规
>  ...
>
>

大佬，我这里就是不行啊，frida换成和你一样的版本也不行

0x768c0c20f8

里面地址，脚本里面的地址是怎么计算的？需要修改么？方便留个联系方式请教

![image](https://bbs.kanxue.com/upload/attach/202508/1046428_YJ44RKQCUS9GYAY.png)

上传的附件：
- 微信图片_20250815114617.png

（65.50kb，4次下载）

## 回复 by aq88 (#13)

*2025-8-15 12:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_vzsnpfhs](https://bbs.kanxue.com/user-927389.htm)
>
>  直接删了也可以
>
>

不能直接删除，有签名校验，删掉重新签名安装，打开闪退。

## 回复 by mb_vzsnpfhs (#14)

*2025-8-18 09:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  aq88](https://bbs.kanxue.com/user-1046428.htm)
>
>  不能直接删除，有签名校验，删掉重新签名安装，打开闪退。
>
>

先安装，再删除。写个py脚本删

## 回复 by mb_jkykcuwo (#15)

*2025-8-18 20:38*

大佬！！！ 不知道发生了什么 但是好像发生了很多！！！

## 回复 by aq88 (#16)

*2025-8-23 15:34*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>
>
>
>
>
>
>  aq88
>
>
>
>  https://www.123684.com/s/o5Wajv-oi5cv?pwd=TgHE 私信不了，发这里不知道是否违规
>  ...
>
>

大佬能分享下你的脚本么？是地址需要修改还是啥？

## 回复 by 陈可牛 (#17)

*2025-8-23 22:17*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  aq88](https://bbs.kanxue.com/user-1046428.htm)
>
>  大佬能分享下你的脚本么？是地址需要修改还是啥？
>
>

你这个是爱加密，跟帖子两码事。爱加密的样本也可以发出来，我简单瞅瞅

## 回复 by aq88 (#18)

*2025-9-4 09:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  你这个是爱加密，跟帖子两码事。爱加密的样本也可以发出来，我简单瞅瞅
>
>

我看你的截图hook成功了啊，样本就是之前发网盘发过的，就是能否分享一下你hook成功的脚本，小弟学习一下

## 回复 by mb_pkmnczqg (#19)

*2025-9-25 08:51*

怎么联系想买个

## 回复 by aq88 (#20)

*2025-9-29 09:21*

>
> [mb_pkmnczqg](https://bbs.kanxue.com/user-1002588.htm)
>
>  怎么联系想买个
>
>

兄弟，你要买啥？

## 回复 by Joyboy_L (#21)

*2025-10-13 17:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  发apk，我瞅瞅
>
>

大佬，我这种有啥思路吗？![image](https://bbs.kanxue.com/upload/attach/202510/1031807_MMWSJV8HGFTQ55E.webp)

## 回复 by mb_pkmnczqg (#22)

*2025-11-26 08:43*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  aq88](https://bbs.kanxue.com/user-1046428.htm)
>
>  兄弟，你要买啥？
>
>

买你的unidbg

## 回复 by mb_cxjxrwqb (#23)

*2025-12-5 21:53*

膜拜大佬，学习新思路了

## 回复 by onwyc123 (#24)

*2026-1-31 15:10*

![image](https://bbs.kanxue.com/upload/attach/202601/976340_FQ2XHARNWW7578F.webp)

我在逆向一个 Android App，遇到一种比较奇怪的反 Frida 检测现象，想请教下有没有人遇到过。

**现象描述：**

- 只要 **frida-server 在当前开机周期中启动过一次**
- 即使 **没有 attach / spawn / hook 这个 App**
- 之后 **只要手机不重启，该 App 每次启动都会立刻闪退**
- 闪退时有 crash，但 **logcat / tombstone 看不到明确是哪个 so 导致的问题**
- **重启手机后恢复正常**，在不启动 frida-server 的情况下 App 可以正常运行

**环境：**

- Android 8.1（Pixel ）
- frida-server 16.1.8

而且闪退不是那种process terminate 那种现象, 是出现图中的报错这种

## 回复 by wx_小友 (#25)

*2026-1-31 19:44*

>
> [onwyc123](https://bbs.kanxue.com/user-976340.htm)
>
>  我在逆向一个 Android App，遇到一种比较奇怪的反 Frida 检测现象，想请教下有没有人遇到过。现象描述：只要 frida-server 在当前开机周期中启动过一次即使 没有 attach ...
>
>

有apk吗，学习下，没遇到过

## 回复 by onwyc123 (#26)

*2026-1-31 21:26*

链接: https://pan.baidu.com/s/1_aVbUoU0cyZtC3y9ubyT5w 提取码: scgf

## 回复 by onwyc123 (#27)

*2026-1-31 21:27*

5Y675LiK572RKOWOu+WTkik= 应用商店可以搜到

## 回复 by 柳哈辣子 (#28)

*2026-3-6 16:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_小友](https://bbs.kanxue.com/user-783296.htm)
>
>  有apk吗，学习下，没遇到过
>
>

1
