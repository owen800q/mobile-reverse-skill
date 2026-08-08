---
title: '[原创]AI辅助逆向某flutter应用'
url: https://bbs.kanxue.com/thread-290688.htm
tid: 290688
author: Evan_422
date: '2026-04-07'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-08T10:11:39+00:00'
replies: 85
---

### AI辅助逆向某flutter应用

---

引言：最近买了点基金，然后我对象基本过半个小时就提醒我看看基金情况，工位不太好不好摸鱼，所以就想着搞下这个app接口，
然后开发一个桌面应用挂在这里定时轮询，正好最近也想尝试一下jadx的mcp，AI分析到最后告诉我这是flutter开发的，
之前没有接触过flutter逆向，所以搞一下填补一下空白，下面开始正篇。

---

样本&&工具&&环境：

- 样本：5YW75Z+65a6d
- ubuntu_22.04.5
- jadx-mcp插件
- IDA 9.2
- frida 16.1.5
- reqable

---

1.分析接口嘛，肯定先抓个包试试

- 抓包这里有个坑点，flutter自带SSL校验，这个问了下AI，github上有佬开源的通杀flutter SSL校验，感兴趣的可以去看一下代码实现 https://github.com/NVISOsecurity/disable-flutter-tls-verification
- 定位到目标接口，头部有一个签名，看长度初步判断是md5 ![image](https://bbs.kanxue.com/upload/attach/202604/1016671_Z4U728C4SNGWQFK.webp)

1. 算法逆向

- flutter开发的应用核心代码打包后都在libapp.so里面 ![image](https://bbs.kanxue.com/upload/attach/202604/1016671_46BPJ59RAX383AT.webp)
- 先在IDA里面搜索一下字符串 request-sign ![image](https://bbs.kanxue.com/upload/attach/202604/1016671_XQPK2PXS79BP9BD.webp)
- 这里我本来想看交叉引用的，发现没效果，问了下AI，告诉我如下原因和解决方案 ![image](https://bbs.kanxue.com/upload/attach/202604/1016671_MD7DYSCNZE9QC94.webp)
- 按blutter官方文档执行以下命令，执行完之后会在你的输出目录生成以下内容

```shell
  python3 blutter.py path/to/app/lib/arm64-v8a out_dir
\```

- 输出文件 ![image](https://bbs.kanxue.com/upload/attach/202604/1016671_9R3BVX6A5RSRF98.webp)
- 其实到这里如果只是为了搞算法的话就已经可以将输出的asm里面的dio_request.dart导出文件丢给ai去分析就行了，针对这个app因为我已经知道它是一个加盐其未魔改的md5了，所以找盐这种事丢给ai完全可以胜任的 ![image](https://bbs.kanxue.com/upload/attach/202604/1016671_V88DHWRB5TRX2HY.webp)
- 但是为了体验flutter逆向全流程和熟悉IDA，我还是按网上教程，在IDA中导入了blutter生成的还原字符的脚本 ![image](https://bbs.kanxue.com/upload/attach/202604/1016671_63GJB3AQM7G466M.webp)
- 定位到_onRequest函数 ![image](https://bbs.kanxue.com/upload/attach/202604/1016671_FNT9PVHUUVAS9XM.webp)
- hook盐值，在ida里我们看到了generateMD5函数的起始地址是0x70A264，所以我们只需要hook函数的入参和返回值，就能看到盐值了

```javascript
function readDartStringExact(ptr) {
    if (ptr.isNull()) return "null";

    try {
        // 1. 读取长度：位于指针偏移 +7 的位置，占用 4 个字节
        // 读取出来的 Smi 编码值需要右移 1 位才是真实长度
        let lengthSmi = ptr.add(7).readU32();
        let length = lengthSmi >> 1;

        if (length === 0) return "";
        if (length > 10240) return "[String suspiciously long: " + length + " bytes]";

        // 2. 读取字符串数据：位于指针偏移 +15 (0x0F) 的位置
        let strDataPtr = ptr.add(15);

        // 按照真实长度读取完整的 UTF-8 字符串
        let str = strDataPtr.readUtf8String(length);
        return str;
    } catch (e) {
        return "[Error reading string at " + ptr + ": " + e.message + "]";
    }
}

function hookMD5() {
    let moduleName = "libapp.so";
    let libapp = Process.getModuleByName(moduleName);
    let targetOffset = 0x70A264;
    let targetAddress = libapp.base.add(targetOffset);

    console.log("[*] Hooking generateMD5 at: " + targetAddress);
    console.log("[*] Waiting for network requests...\n");

    Interceptor.attach(targetAddress, {
        onEnter: function(args) {
            // 我们已经确认 args[0] 就是我们要的明文字符串指针
            this.inputStringPtr = args[0];

            console.log("=========================================");
            console.log("[+] MD5 Signature Triggered!");

            // 使用精准解析函数读取完整明文
            let plaintext = readDartStringExact(this.inputStringPtr);

            console.log("[->] Full Plaintext Input:");
            console.log("-----------------------------------------");
            console.log(plaintext);
            console.log("-----------------------------------------");
            console.log("[i] Plaintext Length: " + plaintext.length + " characters");
        },
        onLeave: function(retval) {
            // 返回值同样是 Dart 字符串，包含 32 位的 MD5 Hex
            let md5Result = readDartStringExact(retval);

            console.log("[<-] MD5 Output Hash : " + md5Result);
            console.log("=========================================\n");
        }
    });
}

setTimeout(function() {
    hookMD5();
}, 1000);
\```

 ![image](https://bbs.kanxue.com/upload/attach/202604/1016671_C7Y6WEMYKYFR76H.webp)

1. 总结

- 本次样本逆向全程基本都是由ai完成的，包括思路和分析，我只是给它提供需要的信息，虽然不复杂，不过也是学到一些新东西的，包括怎么去逆flutter，怎么过flutter的SSL校验，基于地址hook so函数等，写的比较水勿喷，只是为了记录一下flutter逆向的流程。感谢AI— ~hhhha

---

# 回复

## 回复 by mb_gluymaeh (#2)

*2026-4-8 11:21*

感谢你分享这么好的资源！

## 回复 by Imxz (#3)

*2026-4-8 11:37*

rbq

## 回复 by AyonA333 (#4)

*2026-4-8 18:24*

学习

## 回复 by mb_uktygsmq (#5)

*2026-4-9 17:27*

65666

## 回复 by 孤梦拾遗 (#6)

*2026-4-9 19:05*

blutter

## 回复 by guijingwen (#7)

*2026-4-9 19:43*

66

## 回复 by 4Chan (#8)

*2026-4-10 10:20*

66

## 回复 by 随风而行aa (#9)

*2026-4-10 10:27*

看看

## 回复 by 小木马 (#10)

*2026-4-10 11:25*

看看

## 回复 by 啥也不会2 (#11)

*2026-4-10 14:58*

看看

## 回复 by Unsped (#12)

*2026-4-10 23:04*

学习一下

## 回复 by 需要渗透高手 (#13)

*2026-4-10 23:18*

看看

## 回复 by lackone (#14)

*2026-4-10 23:59*

666666

## 回复 by mb_zxamxsfc (#15)

*2026-4-11 00:16*

66

## 回复 by mb_ujlbfnqz (#16)

*2026-4-12 15:32*

6666 感谢大佬

## 回复 by Zy143L (#17)

*2026-4-13 03:39*

APP也没加固什么的么..之前想让AI逆一个APP ida的mcp和jadx的mcp 以及 frida都给他提供好了
然后他就在那里死磕ollvm切到frida 因为有注入检测 spwn启动就崩溃 ai自己搁那改 改了几十个版本了..
烧了我300M的token 最终还是不了了之

## 回复 by mb_iqcojgcb (#18)

*2026-4-13 07:08*

学习学习

## 回复 by uni7corn (#19)

*2026-4-13 12:26*

感谢分享。

## 回复 by mb_qimctavn (#20)

*2026-4-13 12:52*

6

## 回复 by iBa0 (#21)

*2026-4-14 13:50*

123

## 回复 by 网安小白long (#22)

*2026-4-16 00:52*

6666

## 回复 by 魔童 (#23)

*2026-4-21 19:41*

感谢大佬

## 回复 by mb_vhgkbxus (#24)

*2026-4-22 09:34*

正在学flutter逆向。感谢！

## 回复 by 丁真 (#25)

*2026-4-25 13:43*

刚好在搞flutter

## 回复 by console_ (#26)

*2026-4-25 15:34*

学习

## 回复 by kingking888 (#27)

*2026-4-25 18:11*

666

## 回复 by apxar (#28)

*2026-4-26 11:08*

。

## 回复 by pingsky (#29)

*2026-4-27 10:04*

感谢分享

## 回复 by mb_ktasfpbp (#30)

*2026-4-27 14:21*

666

## 回复 by mb_yyvcbkli (#31)

*2026-4-27 14:27*

学习一下先进经验

## 回复 by mb_dwksysag (#32)

*2026-4-27 14:57*

可以的

## 回复 by pan_634488 (#33)

*2026-4-27 16:42*

感谢大佬

## 回复 by oscar99999 (#34)

*2026-4-27 21:56*

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by 菜鸟逆向 (#35)

*2026-4-28 11:59*

学习下![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by 菜鸟逆向 (#36)

*2026-4-28 11:59*

学习下666666![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by 菜鸟逆向 (#37)

*2026-4-28 11:59*

学习下666666![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by 菜鸟逆向 (#38)

*2026-4-28 12:00*

学习下666666

## 回复 by 菜鸟逆向 (#39)

*2026-4-28 12:00*

正在学flutter逆向。感谢！

## 回复 by mb_gynasaoe (#40)

*2026-4-29 20:26*

好东西值得学习

## 回复 by mb_gynasaoe (#41)

*2026-4-29 20:26*

好东西值得学习![image](https://bbs.kanxue.com/view/img/face/007.gif)

## 回复 by 末日大哥 (#42)

*2026-4-29 20:54*

666

## 回复 by 末日大哥 (#43)

*2026-4-29 21:00*

感谢大佬

## 回复 by 末日大哥 (#44)

*2026-4-29 21:00*

感谢大佬

## 回复 by Cure. (#45)

*2026-5-3 11:51*

1

## 回复 by git_48163heylam (#46)

*2026-5-13 18:18*

学习下，感谢大佬

## 回复 by huazai华仔 (#47)

*2026-5-15 08:28*

666

## 回复 by cpluse (#48)

*2026-5-16 20:19*

感谢分享

## 回复 by 086Love (#49)

*2026-5-18 11:26*

学习

## 回复 by mb_yyvcbkli (#50)

*2026-5-18 14:27*

学习一下先进经验

## 回复 by 行者有三 (#51)

*2026-5-22 19:53*

感谢分享

## 回复 by 行者有三 (#52)

*2026-5-22 19:53*

感谢分享

## 回复 by 行者有三 (#53)

*2026-5-22 19:53*

感谢分享

## 回复 by mb_rnbyretn (#54)

*2026-5-25 23:50*

刚好在搞flutter

## 回复 by mb_ofgyxagz (#55)

*2026-5-28 03:57*

看看

## 回复 by byhk (#56)

*2026-5-28 08:37*

谢谢分享

## 回复 by 勒LI (#57)

*2026-5-28 09:26*

6666

## 回复 by litianp (#58)

*2026-5-28 09:46*

学习了，刚需

## 回复 by 安东尼Studio (#59)

*2026-5-29 16:17*

![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by Savoor (#60)

*2026-5-31 20:02*

学习学习

## 回复 by mb_xwntdpxy (#61)

*2026-6-1 21:06*

666

## 回复 by mb_itwvwlom (#62)

*2026-6-2 13:04*

学习

## 回复 by hanjiefang (#63)

*2026-6-5 15:38*

1

## 回复 by MaYil (#64)

*2026-6-5 16:10*

感谢分享

## 回复 by mb_zoyhhbnr (#65)

*2026-6-14 17:11*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by GEKEZYX (#66)

*2026-6-15 00:30*

666

## 回复 by yuanyouran (#67)

*2026-6-22 10:29*

感谢分享

## 回复 by ugui (#68)

*2026-6-24 20:45*

![image](https://bbs.kanxue.com/view/img/face/059.gif)

## 回复 by wx_逸_143 (#69)

*2026-6-26 01:43*

感谢分享

## 回复 by wx_插曲 (#70)

*2026-6-26 08:09*

6666

## 回复 by wx_插曲 (#71)

*2026-6-26 08:09*

66666

## 回复 by 蒲公英v (#72)

*2026-6-28 19:16*

学习

## 回复 by 嘉心糖 (#73)

*2026-6-28 21:58*

看看隐藏

## 回复 by mb_dlljjfcf (#74)

*2026-6-28 22:46*

6666

## 回复 by 揰掵佲 (#75)

*2026-6-29 03:25*

感谢分享............

## 回复 by jyotidwi (#76)

*2026-6-30 11:45*

tql

## 回复 by dsr000 (#77)

*2026-7-2 15:46*

666

## 回复 by 吾苏同在 (#78)

*2026-7-9 07:20*

感谢分享

## 回复 by git_54107yeweilin666 (#79)

*2026-7-11 20:52*

1

## 回复 by mb_wfqcntgg (#80)

*2026-7-30 16:08*

学习

## 回复 by 漂流的鱼 (#81)

666

## 回复 by whe (#82)

66666

## 回复 by 飆汗吉米 (#83)

666

## 回复 by mb_gkbxtfri (#84)

666

## 回复 by git_78819sinyu1012 (#85)

666

## 回复 by mb_jdkigsoz (#86)

正在学flutter逆向，学习大佬的教程
