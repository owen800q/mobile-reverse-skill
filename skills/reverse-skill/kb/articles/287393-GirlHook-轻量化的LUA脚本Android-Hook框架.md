---
title: '[原创]GirlHook 轻量化的LUA脚本Android Hook框架'
url: https://bbs.kanxue.com/thread-287393.htm
tid: 287393
author: Lynnette
date: '2025-06-28'
tags: [Android安全, 原创, 基础理论, 系统相关, 源码框架, 工具脚本]
crawled_at: '2026-08-09T04:46:56+00:00'
replies: 213
---

如果这个项目对你有用，还请在GitHub为我留下一颗star。非常感谢。目前已支持java方法hook和dump所有已加载dex

项目地址位于最下方

    本意是写一个Hook框架来平替一下总是被检测的frida，所以花费一些时间写了这个Hook框架。另一方面也是想研究一下ART的Hook原理，借着这个机会研究明白也写出来了。目前运行的还不是很完美，对象会直接打印出地址，也就是localref，不能递归解析(对象嵌套对象)，只能解析对象中的基础类型。被嵌套的对象需要手动再调用函数解析一次。

基础场景下算是够用了，功力不够深，大佬轻喷。以后会逐步完善这套框架。

    目前只支持AArch64(因为参数传递比较麻烦，用了不少内联汇编)。探测结构偏移用的是Android15的，因为我目前手机上只有Android15的机器，在Android11/15/16手机上测试通过，理论上api30+的手机都能使用。使用文件传递参数，所以最好使用真机和api33之后的模拟器。如果需要在低版本使用，可以修改一下FindClass里面定义的偏移；这个使用的是类似frida的做法，找到固定字段作为锚点，往上往下加减固定偏移来找指定字段。这些小偏移如果不想自己找，也可以抄frida-java-bridge的内容。

    核心是一个so，注入后就可以进行hook，通过文件与loader通信，loader再与client通信。注入器这块我没有写，使用的是tinjector。这个注入器也是十分的强大，强烈推荐。

测试用例包含在Github，另外也拿其他软件测试了一下

一个简单的演示视频：<https://www.bilibili.com/video/BV1s9KmzVE1i/>

贴一张图：

![image-20250628213902887](https://bbs.kanxue.com/upload/attach/202506/1000748_K9U97WW7YQSATWM.jpg)

### Girl的功能：

- 自动探测art结构，计算出需要使用的结构的offset。(仅在Android15 16进行测试)
- 展示全部类名，筛选指定类。展示类全部方法名，筛选指定方法，进行Hook
- 遍历全部的ClassLoader，遍历全部已加载的类，遍历某类的全部方法(应对加壳软件)
- 全自动的shorty等参数生成
- Hook Java函数，显示参数内容，修改参数内容，并应用修改。
- 支持处理自定义结构、数组、List等内容。提供多个api来转换结构至lua table，并提供api从lua table应用修改。

Hook的原理比较繁杂，我放在我的个人博客上，如果感兴趣可以看一下。

[https://note.lynnette.uk/article/girlHook](https://note.lynnette.uk/article/girlHook#21ab7eadde8180cca10bef723cc005ec)

至于遍历所有classloader和所有类，主要用的是ClassLinker的方法，博客里没有提到，这里简单贴一点代码。主要是注意这里拿到的classloader是mirror object，必须用newlocalref创建一个引用，才能像jni里面找到的classloader一样用。不然参数不对会崩溃。同样，用jni找到的classloader是引用，读出来的指针和这里拿到的mirror object是一样的，也验证了正确性。

\```
void* realVisit(void* thiz, void* classloader){
    LOGI("Called realVisit ClassLoader:%p", classloader);
    auto currentSize = VectorStore<ClassLoaderPtr>::Instance().Size();
    VectorStore<ClassLoaderPtr>::Instance().Add((ClassLoaderPtr)classloader,currentSize);
    return classloader;
}
bool MyVisitClassImpl(void* thiz, void* kclass) {
    if (kclass == nullptr) return true;
    std::string dest = ArtInternals::PrettyDescriptorFn(kclass);
    size_t pos = dest.find('$');
    if (pos != std::string::npos) {
        dest = dest.substr(0, pos);  // 截取 $ 之前的部分
    }
    pos = dest.find('[');
    if (pos != std::string::npos) {
        dest = dest.substr(0, pos);  // 截取 [ 之前的部分
    }
    for (char& ch : dest) {
        if (ch == '.') {
            ch = '/';
        }
    }
    UnorderedStore<CLASSNAMETYPE>::Instance().Add(dest);
    return true;
}
namespace Class_Method_Finder {
    void Store_all_classLoaders(){
        // 构造 vtable
        void* vtable[3] = {};
        vtable[2] = (void*)+[](void* thiz, void* loader) -> bool {
            return realVisit(thiz, loader);
        };
        // 构造 fake visitor 实例
        void* visitorBuf[1] = {};
        visitorBuf[0] = vtable;
        // 调用 VisitClassLoaders
        VectorStore<ClassLoaderPtr>::Instance().Clear();
        void* classLinker = *(void**)(ArtInternals::RuntimeInstance + ArtInternals::RunTimeSpec.classLinker);
        ArtInternals::VisitClassLoadersFn(classLinker, visitorBuf);
    }
    void iterate_all_classes(){
        // 构造 vtable，只有一个函数，在 operator() 的虚函数槽位
        UnorderedStore<CLASSNAMETYPE>::Instance().Clear();
        void* vtable[3] = {};
        vtable[2] = (void*)+[](void* thiz, void* klass, void* arg) -> bool {
            return MyVisitClassImpl(thiz, klass);
        };
        // 构造 fake visitor 实例，第一项就是 vtable 指针
        void* visitorBuf[1] = {};
        visitorBuf[0] = vtable;
        // 调用 VisitClassLoaders
        void* classLinker = *(void**)(ArtInternals::RuntimeInstance + ArtInternals::RunTimeSpec.classLinker);
        ArtInternals::VisitClassesFn(classLinker, visitorBuf);
    }
}
\```

项目地址：<https://github.com/Lynnette177/GirlHook>

---

# 回复

## 回复 by wx_插曲 (#2)

*2025-6-29 01:08*

6666

## 回复 by wx_ln (#3)

*2025-6-29 02:05*

6666666666

## 回复 by mb_ldbucrik (#4)

*2025-6-29 06:49*

感谢分享

## 回复 by lyghost (#5)

*2025-6-29 07:52*

感谢分享

## 回复 by 安卓逆向test (#6)

*2025-6-29 08:51*

牛的

## 回复 by zhengyuqin (#7)

*2025-6-29 08:51*

66

## 回复 by mb_ijijcnje (#8)

*2025-6-29 09:10*

666

## 回复 by mb_pobqzscg (#9)

*2025-6-29 09:11*

666

## 回复 by 一只笨猫 (#10)

*2025-6-29 13:41*

1

## 回复 by wjwujian (#11)

*2025-6-29 17:08*

支持一下吧

## 回复 by MaYil (#12)

*2025-6-29 17:08*

感谢分享

## 回复 by SomeMx (#13)

*2025-6-29 18:47*

过来瞧瞧

## 回复 by mb_kznyrusy (#14)

*2025-6-29 19:24*

学习学习

## 回复 by mb_qimctavn (#15)

*2025-6-29 19:29*

感谢分享

## 回复 by tonykros (#16)

*2025-6-29 20:54*

Thanks for sharing

## 回复 by 毛毛毛毛虫 (#17)

*2025-6-29 21:53*

学习一下

## 回复 by mb_pesxllvn (#18)

*2025-6-29 22:04*

666

## 回复 by xianhuimin (#19)

*2025-6-30 00:18*

轮子造的好

## 回复 by darknight007 (#20)

*2025-6-30 02:08*

6666

## 回复 by onlythis (#21)

*2025-6-30 09:07*

6666

## 回复 by jdong (#22)

*2025-6-30 09:32*

6666

## 回复 by GEKEZYX (#23)

*2025-6-30 09:37*

6666

## 回复 by fangliangz (#24)

*2025-6-30 09:40*

666

## 回复 by 西瓜帅 (#25)

*2025-6-30 09:54*

6666

## 回复 by 酒仙桥之虎 (#26)

*2025-6-30 10:16*

666

## 回复 by matrump (#27)

*2025-6-30 10:24*

666

## 回复 by 文西哥 (#28)

*2025-6-30 10:30*

6666

## 回复 by ccc9329 (#29)

*2025-6-30 10:43*

6666666666666666

## 回复 by litianp (#30)

*2025-6-30 11:12*

牛批了，学习一下

## 回复 by heckerstone (#31)

*2025-6-30 11:21*

666

## 回复 by Ankeys (#32)

*2025-6-30 11:23*

666

## 回复 by sk97 (#33)

*2025-6-30 11:51*

相当牛逼啊

## 回复 by mb_patxjnad (#34)

*2025-6-30 13:38*

66

## 回复 by K4NG (#35)

*2025-6-30 14:02*

回复看帖 666666666

## 回复 by mb_dhaylnrk (#36)

*2025-6-30 14:15*

666

## 回复 by Dem0li (#37)

*2025-6-30 14:18*

666

## 回复 by 晨曦遇晓 (#38)

*2025-6-30 14:24*

666

## 回复 by YooHaa (#39)

*2025-6-30 14:38*

666

## 回复 by mb_4nrpVMxJ (#40)

*2025-6-30 15:01*

看看

## 回复 by 夜惜风雨 (#41)

*2025-6-30 15:04*

666

## 回复 by 万物有属 (#42)

*2025-6-30 15:12*

66666

## 回复 by 肉蚌葱鸡 (#43)

*2025-6-30 15:58*

66666666

## 回复 by mb_kbkqyusp (#44)

*2025-6-30 16:00*

666666666666

## 回复 by mb_peeqldfc (#45)

*2025-6-30 16:01*

牛逼

## 回复 by wgetlaidu (#46)

*2025-6-30 16:07*

666

## 回复 by 丶咖啡猫丶 (#47)

*2025-6-30 16:37*

666666

## 回复 by mb_xjdhrmck (#48)

*2025-6-30 16:58*

66666

## 回复 by 蓝色橘子 (#49)

*2025-6-30 17:00*

这个... 男的能用吗？

## 回复 by mb_estrypsw (#50)

*2025-7-1 03:48*

666

## 回复 by wx_Huber Barrientos (#51)

*2025-7-1 04:02*

感谢分享

## 回复 by 日暮归途 (#52)

*2025-7-1 09:11*

学习学习

## 回复 by wx_范迪塞尔 (#53)

*2025-7-1 09:39*

试试看

## 回复 by 光年AI (#54)

*2025-7-1 09:52*

真希望能遇到你这么厉害的工程师，一起同行共事

## 回复 by 星落黎明 (#55)

*2025-7-1 09:53*

感谢分享

## 回复 by huangjw (#56)

*2025-7-1 10:06*

用lua写frida hook脚本吗

## 回复 by mb_mzwrvupz (#57)

*2025-7-1 10:41*

666

## 回复 by 菜菜Zn (#58)

*2025-7-1 11:09*

牛的

## 回复 by 看雪高研 (#59)

*2025-7-1 13:34*

1

## 回复 by MsScotch (#60)

*2025-7-1 14:18*

mark

## 回复 by wx_荼风 (#61)

*2025-7-1 15:18*

6666

## 回复 by txs_app (#62)

*2025-7-1 16:36*

666

## 回复 by zylyy (#63)

*2025-7-1 16:40*

66666

## 回复 by Papaya. (#64)

*2025-7-1 16:46*

开始在技术社区打拳了？

## 回复 by Papaya. (#65)

*2025-7-1 16:47*

>
> [蓝色橘子](https://bbs.kanxue.com/user-432185.htm)
>
>  这个... 男的能用吗？
>
>

用一次，jj短1cm![image](https://bbs.kanxue.com/view/img/face/044.gif)

## 回复 by 撒空间zz (#66)

*2025-7-1 17:01*

66

## 回复 by awayawell (#67)

*2025-7-1 17:40*

6666

## 回复 by 火雪非薛 (#68)

*2025-7-1 17:41*

真希望能遇到你这么厉害的工程师，一起同行共事

## 回复 by mb_cfzkocqj (#69)

*2025-7-2 10:15*

感谢分享

## 回复 by 淡定小胖子 (#70)

*2025-7-2 10:19*

看看学习

## 回复 by mb_cbgtaveo (#71)

*2025-7-2 10:30*

6666666

## 回复 by mb_wiuwknnh (#72)

*2025-7-2 11:53*

666666

## 回复 by mb_zvaghcal (#73)

*2025-7-3 01:17*

666

## 回复 by Lynnette (#74)

*2025-7-3 12:34*

>
> [Papaya.](https://bbs.kanxue.com/user-843975.htm)
>
>  开始在技术社区打拳了？
>
>

看这个名字就知道恰恰相反![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by tongling bai (#75)

*2025-7-3 16:16*

666

## 回复 by Imxz (#76)

*2025-7-3 16:31*

牛逼

## 回复 by jpacg (#77)

*2025-7-3 18:33*

赞一个

## 回复 by lackone (#78)

*2025-7-3 22:16*

666666

## 回复 by 孤独的街 (#79)

*2025-7-4 00:02*

感谢分享

## 回复 by 呼吸24K纯氧 (#80)

*2025-7-4 09:55*

![image](https://bbs.kanxue.com/view/img/face/014.gif) 感谢分享

## 回复 by l1nn (#81)

*2025-7-4 10:18*

666

## 回复 by lookaside (#82)

*2025-7-4 10:25*

1

## 回复 by mb_kfexwtvm (#83)

*2025-7-4 11:29*

6666

## 回复 by cpannn (#84)

*2025-7-4 12:54*

感谢分享

## 回复 by 一直会笑的猫 (#85)

*2025-7-4 15:11*

6666

## 回复 by mb_basgiwmq (#86)

*2025-7-4 15:17*

66666666666666

## 回复 by cobe (#87)

*2025-7-4 17:58*

6666

## 回复 by mb_btjndvgh (#88)

*2025-7-5 00:25*

有一头无数

## 回复 by mb_tnkubkna (#89)

*2025-7-5 09:23*

666

## 回复 by mb_evqfuijb (#90)

*2025-7-5 13:00*

6666

## 回复 by wx_紫风⁸³⁸³²⁴⁶ (#91)

*2025-7-5 17:31*

![image](https://bbs.kanxue.com/view/img/face/038.gif)

## 回复 by wx_huhu_859 (#92)

*2025-7-6 19:20*

11

## 回复 by wen55444 (#93)

*2025-7-8 02:07*

感谢分享

## 回复 by 李啊啊 (#94)

*2025-7-8 09:20*

666

## 回复 by 蓝色橘子 (#95)

*2025-7-11 16:28*

>
> [Papaya.](https://bbs.kanxue.com/user-843975.htm)
>
>  用一次，jj短1cm[em_044]
>
>

那还行，我可以用20次![image](https://bbs.kanxue.com/view/img/face/044.gif)

## 回复 by Arsylk (#96)

*2025-7-13 14:37*

6

## 回复 by 我靠三二一 (#97)

*2025-7-14 11:40*

感谢分享

## 回复 by Snowman_Liam (#98)

*2025-7-14 13:25*

666666

## 回复 by Sherry77 (#99)

*2025-7-15 09:49*

66

## 回复 by 周旋久 (#100)

*2025-7-15 10:30*

牛逼挂哥

## 回复 by manyuegong33 (#101)

*2025-7-17 08:46*

666

## 回复 by 末日大哥 (#102)

*2025-7-17 08:53*

666学习一下

## 回复 by 会飞的锅 (#103)

*2025-7-17 09:25*

强者

## 回复 by 猫毛茂 (#104)

*2025-7-17 19:26*

6666

## 回复 by mb_jadbsvwe (#105)

*2025-7-17 21:16*

感谢分享

## 回复 by shawn996 (#106)

*2025-7-18 04:48*

感谢

## 回复 by 宛枫 (#107)

*2025-7-18 08:38*

感谢分享，学习一下

## 回复 by baichisi (#108)

*2025-7-24 10:17*

6666

## 回复 by 希梦☆奈何 (#109)

*2025-7-24 10:22*

路过看看

## 回复 by quanIngo (#110)

*2025-7-24 10:36*

看看内容

## 回复 by mb_gqiqtgge (#111)

*2025-7-24 19:09*

66666

## 回复 by mb_nsmgrdtd (#112)

*2025-7-24 20:20*

66666

## 回复 by wx_听书人 (#113)

*2025-7-24 20:35*

1111

## 回复 by mb_iyfuxmht (#114)

*2025-7-25 00:06*

6666666

## 回复 by mb_mumzrqcs (#115)

*2025-7-25 05:51*

666666

## 回复 by 海带 (#116)

*2025-7-25 10:31*

3212121

## 回复 by chiikawa_gui (#117)

*2025-7-29 11:26*

支持native层hook么？

## 回复 by mb_xwseruzz (#118)

*2025-7-31 00:15*

6666

## 回复 by aizhiqun (#119)

*2025-8-1 13:00*

感谢分享

## 回复 by 4Chan (#120)

*2025-8-1 14:24*

666

## 回复 by 王炸接小三 (#121)

*2025-8-1 15:03*

666

## 回复 by mb_nsxzyazh (#122)

*2025-8-6 15:06*

看看

## 回复 by mb_vknsuayu (#123)

*2025-8-6 15:41*

666

## 回复 by wx_赛特 (#124)

*2025-8-6 16:28*

666

## 回复 by Imxz (#125)

*2025-8-8 10:49*

666

## 回复 by mb_donutrph (#126)

*2025-8-8 11:01*

666

## 回复 by yml2213 (#127)

*2025-8-8 11:38*

6666

## 回复 by Freax (#128)

*2025-8-8 13:55*

6

## 回复 by baitongling (#129)

*2025-8-8 16:13*

6666

## 回复 by 下雨天sana (#130)

*2025-8-8 16:14*

666

## 回复 by SharkFall (#131)

*2025-8-8 16:18*

6666

## 回复 by wx_平头哥 (#132)

*2025-8-8 16:27*

666

## 回复 by Light紫星 (#133)

*2025-8-8 16:32*

大佬太厉害了，学习学习

## 回复 by wuxin159 (#134)

*2025-8-11 15:37*

6666

## 回复 by aq88 (#135)

*2025-8-11 23:33*

学习，frida老被检测，不会搞

## 回复 by dreameriii (#136)

*2025-8-12 11:44*

优秀！

## 回复 by mb_tkijjroi (#137)

*2025-8-19 01:16*

6666

## 回复 by NL不分 (#138)

*2025-8-19 20:43*

66

## 回复 by zz胡 (#139)

*2025-8-19 20:46*

可以看看

## 回复 by 金钱蒲 (#140)

*2025-8-20 09:41*

好好学习天天向上

## 回复 by p1s1lver (#141)

*2025-8-21 10:36*

666

## 回复 by 前来打酱油的 (#142)

*2025-8-22 17:04*

围观

## 回复 by jw8888 (#143)

*2025-8-23 13:17*

666666666666666

## 回复 by mb_ehupwxyu (#144)

*2025-8-26 16:59*

666

## 回复 by mb_hfpmtthz (#145)

*2025-8-29 16:32*

6666

## 回复 by wx_马 (#146)

*2025-8-30 17:02*

6666

## 回复 by mb_ebiwunmj (#147)

*2025-8-31 00:50*

666

## 回复 by mb_ebiwunmj (#148)

*2025-8-31 00:58*

真牛皮啊

## 回复 by 苏幻墨 (#149)

*2025-8-31 10:12*

GirlHook 轻量化的LUA脚本Android Hook框架

## 回复 by Viseris (#150)

*2025-8-31 11:58*

6666

## 回复 by 街道办事处 (#151)

*2025-9-11 14:12*

666

## 回复 by 星辰北天 (#152)

*2025-9-11 15:28*

感谢分享

## 回复 by bedaway (#153)

*2025-9-11 20:42*

6666

## 回复 by 星辰北天 (#154)

*2025-9-12 10:26*

大佬666

## 回复 by 温泉划水鱼 (#155)

*2025-9-12 12:45*

好

## 回复 by Sharp_Wang (#156)

*2025-9-15 13:56*

666

## 回复 by mb_alksjkud (#157)

*2025-9-17 09:38*

学习

## 回复 by wx_郑泽科 (#158)

*2025-9-17 10:04*

666

## 回复 by XCicada (#159)

*2025-9-17 10:17*

看看

## 回复 by 飆汗吉米 (#160)

*2025-9-18 21:04*

666

## 回复 by jjjo (#161)

*2025-9-19 11:16*

666

## 回复 by lbunknow (#162)

*2025-9-19 13:58*

777

## 回复 by wx_a_856361 (#163)

*2025-9-20 01:04*

666

## 回复 by wx_！_336 (#164)

*2025-9-20 09:48*

6666

## 回复 by Gryffindoss (#165)

*2025-10-14 11:04*

666

## 回复 by mb_cbhhrcqt (#166)

*2025-10-17 07:16*

111111111111

## 回复 by fujing (#167)

*2025-10-17 07:33*

感谢你的积极参与，期待更多精彩内容！

## 回复 by KanXue_NG (#168)

*2025-10-19 11:45*

6666

## 回复 by jjcat (#169)

*2025-10-26 12:43*

mark

## 回复 by Ace_Heng (#170)

*2025-10-26 15:13*

111111

## 回复 by 荧光之夏 (#171)

*2025-10-27 12:06*

666

## 回复 by mb_zbqbqzlp (#172)

*2025-11-10 10:36*

666

## 回复 by mb_fqndstzl (#173)

*2025-11-10 11:00*

6666

## 回复 by logeye (#174)

*2025-11-10 16:04*

8888

## 回复 by mb_xflcgdik (#175)

*2025-11-14 16:19*

6

## 回复 by 勒LI (#176)

*2025-11-14 17:17*

66

## 回复 by mb_jofnsvty (#177)

*2025-11-20 16:51*

666

## 回复 by jyotidwi (#178)

*2025-11-21 12:58*

66666

## 回复 by mb_pmgifpme (#179)

*2025-11-24 11:42*

1

## 回复 by AndroidDev (#180)

*2025-11-26 21:32*

666

## 回复 by zylyy (#181)

*2025-11-26 22:20*

6666666

## 回复 by wx_随波逐流、 (#182)

*2025-11-27 07:52*

计算机为经济危机王俊凯

## 回复 by mb_pmwkabcl (#183)

*2025-12-2 03:42*

1

## 回复 by mb_awbfnjrt (#184)

*2025-12-3 18:52*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by x_power (#185)

*2025-12-3 20:39*

666

## 回复 by 带篮子 (#186)

*2025-12-4 03:39*

6666

## 回复 by Heiyiren123 (#187)

*2025-12-9 20:58*

一直在找这个，谢谢！

## 回复 by mb_jqqxasya (#188)

*2025-12-9 21:43*

666

## 回复 by kuteng01 (#189)

*2025-12-11 09:41*

学习一下

## 回复 by mb_jvgnqejw (#190)

*2025-12-12 00:38*

ooo

## 回复 by mb_ztqcemce (#191)

*2025-12-16 13:50*

1看看教程

## 回复 by Hasaone (#192)

*2025-12-16 13:59*

非常666

## 回复 by mb_myeogrox (#193)

*2025-12-16 16:57*

666

## 回复 by cjja爱之恋 (#194)

*2025-12-18 02:24*

支持，，，

## 回复 by Sybbbcy (#195)

*2025-12-18 12:15*

牛掰

## 回复 by git_71735namngsec-netizen (#196)

*2025-12-18 12:32*

666

## 回复 by 人九 (#197)

*2025-12-18 20:21*

66666666666

## 回复 by wx_故事与酒 (#198)

*2025-12-23 17:34*

6666666666666666666666

## 回复 by mb_jzcwgtoc (#199)

*2026-1-20 11:49*

感谢分享。

## 回复 by mb_bvwbboty (#200)

*2026-1-26 16:46*

666

## 回复 by mb_kynpgjqo (#201)

*2026-1-26 16:49*

6666

## 回复 by AYHMO (#202)

*2026-1-29 15:31*

66666

## 回复 by mb_ampejxbk (#203)

*2026-2-10 21:55*

6666

## 回复 by kccp (#204)

*2026-2-10 22:34*

666

## 回复 by 毕索 (#205)

*2026-2-22 23:52*

666

## 回复 by git_91090armpro666-tech (#206)

*2026-2-23 11:58*

看起来很强大

## 回复 by mJqalJqN (#207)

*2026-2-23 14:32*

1

## 回复 by mb_evlxbmwv (#208)

*2026-2-25 17:17*

66666

## 回复 by 小尘0000 (#209)

*2026-3-16 11:31*

6666

## 回复 by ClPrada (#210)

*2026-3-16 11:45*

研究研究

## 回复 by mb_wuevwbec (#211)

*2026-3-18 09:43*

a

## 回复 by 零_721409 (#212)

*2026-3-18 10:43*

666

## 回复 by 孤梦拾遗 (#213)

*2026-3-18 10:48*

6666

## 回复 by mb_kgkbontt (#214)

*2026-4-30 17:51*

666
