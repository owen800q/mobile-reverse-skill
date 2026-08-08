---
title: '[原创]某卷轴App flutter md5 aes'
url: https://bbs.kanxue.com/thread-291091.htm
tid: 291091
author: Cure.
date: '2026-05-04'
tags: [Android安全, 原创]
crawled_at: '2026-08-08T10:09:25+00:00'
replies: 53
---

demo地址: atob('aHR0cHM6Ly9kd3ouY24vSkR4WjJzMHU=')

在逛项目网的时候发现一个卷轴，想写个注册机玩玩，结果发现有加密，通过blutter处理后，在ida中打开libapp.so后加载字符串还原脚本，在方法名称搜索md5、aes、encrypt、decrypt一无所获，最后搜索pp.txt中的文本定位到了

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_EAG269REQCKMY6X.webp)

通过分析，主要需要解决sign和请求体

\```
sign: b4e50fdf583dee13d6f434b556be17ef  //32位,猜测是md5
\```

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_E4UE7FBHRAXUHZH.webp)

\```
请求体: loprmMq5XUsW0Xot2uMM1ZgYzfF3WvRjQjK9gLtc5gZFH1lkdUVkzTJUyB/SWAak  //解码后字节长度96,是16的倍数猜测是aes
\```

通过addNames.py还原部分方法名称

搜索猜测的算法

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_7GPJC4R7699CVUN.webp)![image](https://bbs.kanxue.com/upload/attach/202605/1022596_TGUUWGWZPBTWA2V.webp)

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_GAMPQP4WTY2GM3R.webp)![image](https://bbs.kanxue.com/upload/attach/202605/1022596_ATVVE4A7EFT4UNH.webp)

什么都搜索不到

在pp.txt( 对象池中的所有 Dart 对象)搜索相关常量字符串如"sign"、"nonce"等，最后搜索到下方相关内容

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_P22GJTA46VN487R.webp)

直接跳转到0x754d30分析

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_ZRR2XYCXT4Z2DWN.webp)

根据pp.txt面搜索出来的数据可以知道它是一个 Dart 匿名闭包函数，所以这是一个 Dart 匿名闭包函数的调用入口，用来取出闭包保存的数据，再转调真正的业务函数 sub_754D70,sub_754D70的参数是Dart 类实例对象无法直接打印，所以直接看754D70内部方法

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_TGQPS9XUHPWM5PM.webp)

直接通过方法名称看不出来任何东西，直接用最笨的方法一个一个hook(这里方法少可以这样试试)，以下是测试结果

\```
sub_755708: nonce
sub_755040: sign
sub_754954: 解密
sub_4BC6E0: 加密
\```

hook 755040

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_KPCUUGDNJSUUH67.webp)

结果是sign但是参数没什么用，进入755040

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_Y3527DXDUYCYTWS.webp)

只有这两个地方返回了，且是同一个方法，直接hook，把打印出来的参数丢到加密工具里面，测试发现是md5，sign解决

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_KV2Y9JPDAHF8JJQ.webp)

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_D5HS6KK4XWDZGGD.webp)

经过一层一层追踪hook解密函数 754954 但是还是没hook的key iv之类的，然后尝试hook加密函数4BC6E0

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_R9N5CGGPNZRR3UR.webp)

hook到了明文和一串32位的字符串，可能是key，没hook到其字符串了，最开始我把b06f8916bdba044d当成key，9ca1be6c64c1fa4v当成iv

加密算法当成aes/cbc/pkcs7 128位去测试的，没测试通过，然后换成aes/ecb/pkcs7 256位测试才成功的

![image](https://bbs.kanxue.com/upload/attach/202605/1022596_4PEPF9KCPUA4HXK.webp)
frida 脚本，自行替换偏移即可

\```
let base = Module.findBaseAddress("libapp.so");

Interceptor.attach(base.add(0x4BC6E0), {
    onEnter(args) {
        this.a1 = this.context.x1;
        this.a2 = this.context.x2;
        this.a3 = this.context.x3;
        try {
            console.log("x1 =",hexdump(this.a1,{ ansi:true}));
            console.log("x2 =",readDartString(this.a2));
            console.log("x3 =",readDartString(this.a3));
            // console.log("x1 =",hexdump(this.a1,{ ansi:true}));
            // console.log("x2 =",hexdump(this.a2,{ ansi:true}));
            // console.log("x3 =",hexdump(this.a3,{ ansi:true}));

        } catch (e) { }
    },

    onLeave(ret) {
        // console.log("ret =", hexdump(ret,{ ansi:true}));
        console.log("ret string =", readDartString(ret));
    }
});

function readDartString(p) {
    let real = p.sub(1);
    let s = real.add(0x10)
    let type = detectStringType(s);
    console.log(type);

    if (type === "utf16") {
        return s.readUtf16String();
    }
    if (type === "utf8") {
        return s.readUtf8String();
    }
    return "";
}

function detectStringType(ptr) {
    let utf16Score = 0;
    let asciiScore = 0;
    for (let i = 0; i < 16; i++) {
        let b = ptr.add(i).readU8();
        if (i % 2 === 1 && b === 0)
            utf16Score++;
        if (b >= 0x20 && b <= 0x7e)
            asciiScore++;
    }
    if (utf16Score >= 6) {
        return "utf16";
    }
    if (asciiScore >= 6) {
        return "utf8";
    }
    return "unknown";
}
\```

感谢Chatgpt的援助，哈哈

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2026-5-4 12:26*

感谢分享

## 回复 by 上官兮唐 (#3)

*2026-5-4 13:03*

看看

## 回复 by 啥也不会2 (#4)

*2026-5-4 13:12*

看看

## 回复 by jyotidwi (#5)

*2026-5-4 13:44*

看看

## 回复 by 过我眼即我有 (#6)

*2026-5-4 14:12*

看看

## 回复 by Zepp7289 (#7)

*2026-5-5 11:03*

tql

## 回复 by ldehua (#8)

*2026-5-5 15:02*

看看

## 回复 by mb_llrygall (#9)

*2026-5-5 16:34*

看看

## 回复 by 黑色心跳 (#10)

*2026-5-5 19:32*

看看

## 回复 by 苦瓜tim (#11)

*2026-5-5 21:05*

666666666

## 回复 by 需要渗透高手 (#12)

*2026-5-5 21:10*

6666666

## 回复 by mb_qblzkzce (#13)

*2026-5-6 00:17*

学习

## 回复 by mb_yyvcbkli (#14)

*2026-5-6 09:58*

学习一下，先进经验

## 回复 by x1a0f3n9 (#15)

*2026-5-6 10:35*

感谢分享

## 回复 by 4Chan (#16)

*2026-5-6 10:37*

学习一下

## 回复 by mb_fywmigrm (#17)

*2026-5-6 11:20*

1

## 回复 by Mengz3 (#18)

*2026-5-6 11:20*

学习学习

## 回复 by mb_rirvdrlh (#19)

*2026-5-6 12:11*

66666666666666666666

## 回复 by 不具名的悲伤 (#20)

*2026-5-6 13:51*

6

## 回复 by mb_uzmffdbw (#21)

*2026-5-6 14:05*

666

## 回复 by iBa0 (#22)

*2026-5-6 15:12*

6666

## 回复 by mb_cbgtaveo (#23)

*2026-5-6 15:23*

6666

## 回复 by xeiyu (#24)

*2026-5-6 15:31*

666

## 回复 by lance_357335 (#25)

*2026-5-6 15:34*

666

## 回复 by 简简单单看看 (#26)

*2026-5-6 15:47*

6666

## 回复 by dsr000 (#27)

*2026-5-6 15:54*

666

## 回复 by logeye (#28)

*2026-5-6 17:15*

666

## 回复 by mb_pvsntfdw (#29)

*2026-5-7 14:15*

学习

## 回复 by 小木马 (#30)

*2026-5-7 14:30*

66

## 回复 by mb_qimctavn (#31)

*2026-5-7 18:59*

6

## 回复 by 我真的很菜 (#32)

*2026-5-7 23:43*

666

## 回复 by Imxz (#33)

*2026-5-8 10:57*

kkb

## 回复 by Cure. (#34)

*2026-5-8 10:58*

>
> [Imxz](https://bbs.kanxue.com/user-656334.htm)
>  kkb
>

没有

## 回复 by Imxz (#35)

*2026-5-8 11:06*

>
> [Cure.](https://bbs.kanxue.com/user-1022596.htm)
>  没有
>

6 哥们

## 回复 by wugenb (#36)

*2026-5-8 17:13*

1

## 回复 by kingking888 (#37)

*2026-5-9 10:53*

666

## 回复 by uni7corn (#38)

*2026-5-9 13:57*

666

## 回复 by nhtr (#39)

*2026-5-10 17:45*

66

## 回复 by B.M.K (#40)

*2026-5-10 20:47*

1

## 回复 by mb_ezphxtar (#41)

*2026-5-10 23:44*

66666

## 回复 by huazai华仔 (#42)

*2026-5-13 23:48*

666

## 回复 by mb_jvgnqejw (#43)

*2026-5-30 06:07*

888

## 回复 by mb_zoyhhbnr (#44)

*2026-6-8 13:12*

![image](https://bbs.kanxue.com/view/img/face/038.gif)666

## 回复 by wantwill (#45)

*2026-6-8 16:30*

66666

## 回复 by 蒲公英v (#46)

*2026-6-28 19:27*

66666

## 回复 by mb_yyvcbkli (#47)

*2026-7-2 10:39*

学习一下先进的

## 回复 by wx_kx92911 (#48)

*2026-7-15 09:55*

感谢分析

## 回复 by MikotoDev (#49)

*2026-7-20 16:02*

看看

## 回复 by ugui (#50)

*2026-7-26 09:30*

![image](https://bbs.kanxue.com/view/img/face/026.gif)

## 回复 by mb_gjhmacqd (#51)

*2026-7-26 09:32*

666

## 回复 by mb_wfqcntgg (#52)

*2026-8-1 00:38*

666

## 回复 by Viseris (#53)

6666

## 回复 by git_78819sinyu1012 (#54)

666
