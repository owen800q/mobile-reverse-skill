---
title: '[原创]最新版dy抓包&RPC&Unidbg模拟执行生成7神'
url: https://bbs.kanxue.com/thread-290392.htm
tid: 290392
author: Rocky虞
date: '2026-03-19'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-08T10:18:29+00:00'
replies: 279
---

### 声明

本文章中所有内容仅供学习交流使用，不用于其他任何目的，严禁用于商业用途和非法用途，否则由此产生的一切后果均与作者无关！若有侵权，请联系删除。

### 前言

unidbg模拟执行以出值为目的补环境，未进行unidbg指纹进行去除和风控对抗，所以最终结果并不可用于实际请求，只能作为算法分析使用；抓包方案采用的frida hook libsscronet.so的SSL_CTX_set_custom_verify的方式；undibg版本0.9.8，dy版本v38.0.0(搞的时候这还是最新，然后写文章时最新版变成了38.1.0……)。

### 抓包

参考大佬们分享的脚本，hook libsscronet.so的SSL_CTX_set_custom_verify方法。

\```
function hook_dlopen(module_name, fun) {    var android_dlopen_ext = Module.findExportByName(null, "android_dlopen_ext");    if (android_dlopen_ext) {        Interceptor.attach(android_dlopen_ext, {            onEnter: function (args) {                var pathptr = args[0];                if (pathptr) {                    this.path = (pathptr).readCString();                    if (this.path.indexOf(module_name) >= 0) {                        this.canhook = true;                    }                }            },            onLeave: function (retval) {                if (this.canhook) {                    let verifyadd = Module.getExportByName("libsscronet.so","SSL_CTX_set_custom_verify");                    Interceptor.attach(verifyadd,{                        onEnter(args){                            Interceptor.attach(args[2],{                                onLeave(retval){                                    retval.replace(0x0);                                }                            })                        }                    })                }            }        });    }}
\```

评论列表、用户详情这些接口可以找到明文，作品列表不知道是没抓到还是返回的压缩或者密文。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_EURC6R957HFDQCU.webp)

### RPC

参考大佬们的文章，直接在libsscronet.so中搜索http_request_headers。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_DEBWVTKZB6PMCWR.webp)

在sub_37ED64内，那么hook地址应该就是 0x37ED64。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_R979ANBX7WUNK75.webp)

hook他。

\```
function hookSetHeaders(lib) {    // 38.0.0    var SetHeaders = lib.add(0x37ED64);    console.log("Hooking SetHeaders at: " + SetHeaders);    Java.perform(function () {        Interceptor.attach(SetHeaders, {                onEnter: function (args) {                    var key = args[1].readPointer().readUtf8String();                      var val = args[2].readPointer().readUtf8String();                    if (key.indexOf("X-Gorgon") !== -1) {                        console.log(key + " : " + val);                        console.log('SetHeaders called from:\n' + Thread.backtrace(this.context, Backtracer.ACCURATE).map(DebugSymbol.fromAddress).join('\n') + '\n');                        console.log("---------------------------end----------------------------------");                    }                },                onLeave: function (retval) {                    // console.log("retval is :", retval)                }            }        )    })}
\```

可以发现有两处调用。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_ZDV6YRFSD593RYU.webp)先选第一处看看，0x47abc8，在sub_47A31C内。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_YRJAN56Q39Z9RS4.webp)

然后看v76(忘记为啥是看这个了……)，v76 = (char *)v73(v74, v75)，然后看v73，也就是x23。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_PWT3E7SSHQKMGV6.webp)

x23对应的地址为0x47AAEC。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_KKK3B46WU85D2PJ.webp)

在hookSetHeaders方法中添加对x23的hook，然后attach进去。

\```
var test = lib.add(0x47AAEC);Interceptor.attach(test, {    onEnter: function (args) {        console.log(args[0].readUtf8String());        console.log(args[1].readUtf8String());        console.log("X23：" + this.context.x23);    },    onLeave: function (retval) {    }});
\```

可以看到此时x23的地址为0x709bb39e38。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_QD8Y8EQ2DEWHYRR.webp)计算以下在so中的偏移地址，看一下dy的maps，可以发现x23的地址在libmetasec_ml.so中。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_4CWFMYWSA7GM4BY.webp)计算偏移为0x2A6E38，跳转到对应位置。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_2MC6AX8CWCRVRK7.webp)

然后hook他。

\```
function hookmetasec_ml(lib) {    var get_sig = lib.add(0x2A6E38);    console.log("baseAddr from hook", lib);    Interceptor.attach(get_sig, {        onEnter: function (args) {            // console.log("onEnter 0x88ee0");            var arg0 = args[0].readUtf8String();            var arg1 = args[1].readUtf8String();            console.log("arg0：" + arg0);            console.log("arg1：" + arg1);        },        onLeave: function (retval) {            console.log("retval ptr: " + retval);            console.log("retval: " + retval.readUtf8String());        }    });}
\```

可以看到入参和7神了。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_F97U397QNAPSJ43.webp)然后就是封装rpc调用(ps:生成的7神没有测试是否真实可用)。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_284TVF4XA3E5BPC.webp)

### unidbg模拟执行

先搭个基础框架。

\```
package com.bytedance.mobsec;import com.github.unidbg.AndroidEmulator;import com.github.unidbg.Emulator;import com.github.unidbg.Module;import com.github.unidbg.arm.backend.DynarmicFactory;import com.github.unidbg.arm.backend.Unicorn2Factory;import com.github.unidbg.file.FileResult;import com.github.unidbg.file.IOResolver;import com.github.unidbg.linux.android.AndroidEmulatorBuilder;import com.github.unidbg.linux.android.AndroidResolver;import com.github.unidbg.linux.android.dvm.AbstractJni;import com.github.unidbg.linux.android.dvm.DalvikModule;import com.github.unidbg.linux.android.dvm.VM;import com.github.unidbg.memory.Memory;import com.github.unidbg.virtualmodule.android.AndroidModule;import java.io.File;public class MetaSec380001 extends AbstractJni implements IOResolver {    private final AndroidEmulator emulator;    private final VM vm;    private final Module module;    MetaSec380001() {        // 加载so的方式启动        emulator = AndroidEmulatorBuilder.for64Bit()                .setProcessName("com.ss.android.ugc.aweme")                .addBackendFactory(new Unicorn2Factory(true))                .build();        final Memory memory = emulator.getMemory(); // 模拟器的内存操作接口        memory.setLibraryResolver(new AndroidResolver(23)); // 设置系统类库解析        vm = emulator.createDalvikVM(); // 创建Android虚拟机        vm.setVerbose(true); // 设置是否打印Jni调用细节        vm.setJni(this);        DalvikModule dm = vm.loadLibrary(new File("unidbg-android/src/test/resources/dy_380001/libmetasec_ml.so"), false);        module = dm.getModule();        dm.callJNI_OnLoad(emulator);    }    public static void main(String[] args) {        new MetaSec380001();    }    @Override    public FileResult resolve(Emulator emulator, String pathname, int oflags) {        return null;    }}
\```

运行一下，出现报错：libmetasec_ml.so load dependency libandroid.so failed。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_HE72UYZ5GDAZNFT.webp)

有两个方案：1.Patch/Hook 这个不支持的SO所使用的函数，2.使用unidbg VirtualModule，这里选择第2个方案。

\```
new AndroidModule(emulator, vm).register(memory);     // 虚拟libandroid.so
\```

继续运行出现了checkVersion相关的报错。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_JMCAUEKUGQMTQY6.webp)那就使用骚操作把checkVersion注释掉吧(不确定这样做会有什么后果)。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_SS5NCC6QGCPTR9C.webp)继续，可以看到查找了com/bytedance/mobsec/metasec/ml/MS这个类。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_XQN8YBMVUNJAD4F.webp)jadx中看一下这个类。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_676KU9MMBF5X38G.webp)

补。

\```
MS = vm.resolveClass("com/bytedance/mobsec/metasec/ml/MS",        vm.resolveClass("ms/bd/c/i2",                vm.resolveClass("ms/bd/c/y2")));
\```

继续，出现了callStaticObjectMethodV相关的报错。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_NPVW33C5Y85XY7Y.webp)看一下java层对应的方法。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_Y27QEVQP7E3W2VK.webp)

那我们打印一下入参，再做处理。

\```
    @Override    public DvmObject<?> callStaticObjectMethodV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {        switch (signature) {            case "com/bytedance/mobsec/metasec/ml/MS->b(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;":                int i = vaList.getIntArg(0);                System.out.println("MS->b arg0: " + i);        }        throw new UnsupportedOperationException(signature);    }}
\```

执行了268435470这个分支。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_6M2HR2W7JPXNYA3.webp)补。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_B6N4EUC9TKF9VYN.webp)继续，出现了callLongMethodV报错。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_WG364SU8CVRMNM8.webp)

补。

\```
@Overridepublic long callLongMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {    switch (signature) {        case "java/lang/Long->longValue()J":            if (dvmObject.getValue() instanceof Long) {                return (Long) dvmObject.getValue();            }    }    throw new UnsupportedOperationException(signature);}
\```

然后就运行结束了。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_U722A596VFKNJS4.webp)

接下来开始主动调用。

\```
    public void call_seven_god() {        String url = "https://api5-core-hj.amemv.com/aweme/v2/feed/?……";        String header = "cookie……";        Number number = module.callFunction(emulator, 0x2A6E38, url, header);        UnidbgPointer pointer = memory.pointer(number.intValue() & 0xffffffffL);        String result = pointer.getString(0);        System.out.println(">>> result: " + result);    }
\```

又回到了补环境的环节，连续3个报错的补环境方式跟之前的268435470处理方式一样，java方法返回什么，我们就返回什么。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_5DEUDVW6B4ARDDZ.webp)继续，还是callStaticObjectMethodV。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_ZBSGCXS5KE5B9FV.webp)

补。

\```
case "java/lang/Thread->currentThread()Ljava/lang/Thread;":    return vm.resolveClass("java/lang/Thread").newObject(Thread.currentThread());
\```

然后是callObjectMethodV。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_W6H4ZZY8RBK279A.webp)

补。

\```
@Overridepublic DvmObject<?> callObjectMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {    switch (signature) {        case "java/lang/Thread->getStackTrace()[Ljava/lang/StackTraceElement;":            StackTraceElement[] elements = Thread.currentThread().getStackTrace();            DvmObject[] objs = new DvmObject[elements.length];            for (int i = 0; i < elements.length; i++) {                objs[i] = vm.resolveClass("java/lang/StackTraceElement").newObject(elements[i]);            }            return new ArrayObject(objs);    }    throw new UnsupportedOperationException(signature);}
\```

连续几个都是callObjectMethodV，就不一一展示了。

\```
case "java/lang/String->getBytes(Ljava/lang/String;)[B":    String arg0 = (String) vaList.getObjectArg(0).getValue();    System.out.println("java/lang/String->getBytes arg0: " + arg0);    return new ByteArray(vm, arg0.getBytes(StandardCharsets.UTF_8));case "java/lang/StackTraceElement->getClassName()Ljava/lang/String;":    StackTraceElement element = (StackTraceElement) dvmObject.getValue();    return new StringObject(vm, element.getClassName());case "java/lang/StackTraceElement->getMethodName()Ljava/lang/String;":    element = (StackTraceElement) dvmObject.getValue();    return new StringObject(vm, element.getMethodName());
\```

然后就是一个要注意的地方了，这里需要补16777233的返回值和处理"java/lang/Thread->getBytes(Ljava/lang/String;)[B"。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_YENW9JHCZ99AN6G.webp)

补。

\```
case "java/lang/Thread->getBytes(Ljava/lang/String;)[B":    arg0 = (String) vaList.getObjectArg(0).getValue();    System.out.println("java/lang/Thread->getBytes arg0: " + arg0);    return new ByteArray(vm, arg0.getBytes(StandardCharsets.UTF_8));
\```

补完就可以看到7神出来了(没进行指纹处理，应该是没法用于实际请求的)。
![image](https://bbs.kanxue.com/upload/attach/202603/865419_YVVSHF7TW76FZTC.webp)

---

# 回复

## 回复 by mb_4nrpVMxJ (#2)

*2026-3-19 09:51*

学习

## 回复 by 天地一逆旅 (#3)

*2026-3-19 10:13*

图片内容看不到

## 回复 by Gryffindoss (#4)

*2026-3-19 10:22*

6666

## 回复 by mb_asiwnxyv (#5)

*2026-3-19 10:23*

感谢分享

## 回复 by wx_无法回头的伪装 (#6)

*2026-3-19 10:26*

6666

## 回复 by mb_qimctavn (#7)

*2026-3-19 10:26*

6

## 回复 by iBa0 (#8)

*2026-3-19 10:34*

图挂完了

## 回复 by Rocky虞 (#9)

*2026-3-19 10:53*

>
> [mb_cqcnvzkn](https://bbs.kanxue.com/user-1070930.htm)
>  图片内容看不到
>

抱歉，用的公众号图床

## 回复 by Rocky虞 (#10)

*2026-3-19 10:53*

>
> [iBa0](https://bbs.kanxue.com/user-971547.htm)
>  图挂完了
>

抱歉，用的公众号图床

## 回复 by 77H (#11)

*2026-3-19 10:55*

公众号发一下啊

## 回复 by mb_homnvxow (#12)

*2026-3-19 11:13*

没图了

## 回复 by 上善若水No (#13)

*2026-3-19 11:15*

11

## 回复 by 上官兮唐 (#14)

*2026-3-19 11:41*

看看

## 回复 by mb_tjsboqui (#15)

*2026-3-19 12:01*

666

## 回复 by 嘎嘎真的很棒 (#16)

*2026-3-19 12:14*

mark

## 回复 by 悟 (#17)

*2026-3-19 12:16*

11111

## 回复 by 五彩斑斓的黑 (#18)

*2026-3-19 13:47*

666

## 回复 by wx_插曲 (#19)

*2026-3-19 13:59*

666

## 回复 by mb_pmgifpme (#20)

*2026-3-19 14:37*

1

## 回复 by mb_jnmxfjku (#21)

*2026-3-19 15:19*

666

## 回复 by nevinhappy (#22)

*2026-3-19 15:36*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_fidppcok (#23)

*2026-3-19 15:44*

6666

## 回复 by tubecityman (#24)

*2026-3-19 16:12*

66666

## 回复 by wx_7788 (#25)

*2026-3-19 16:18*

666666

## 回复 by XCicada (#26)

*2026-3-19 16:27*

666666

## 回复 by xianhuimin (#27)

*2026-3-19 16:51*

看看

## 回复 by mb_ykavguun (#28)

*2026-3-19 17:01*

1

## 回复 by 墨穹呢 (#29)

*2026-3-19 17:08*

感谢分享

## 回复 by method (#30)

*2026-3-19 18:16*

1

## 回复 by 小手冰凉_ (#31)

*2026-3-19 18:38*

1

## 回复 by mb_zqrczqwa (#32)

*2026-3-19 20:28*

看看

## 回复 by guijingwen (#33)

*2026-3-19 21:20*

66

## 回复 by A00乐淘 (#34)

*2026-3-19 22:03*

666666

## 回复 by linclsky (#35)

*2026-3-19 22:07*

6666

## 回复 by 1sfans (#36)

*2026-3-19 23:00*

666

## 回复 by 小明的爱 (#37)

*2026-3-20 09:11*

感谢分享

## 回复 by Imxz (#38)

*2026-3-20 09:28*

tql

## 回复 by mb_npsajqlx (#39)

*2026-3-20 09:51*

666

## 回复 by wx_Yu_799 (#40)

*2026-3-20 09:57*

66666

## 回复 by YoungBai (#41)

*2026-3-20 10:15*

666

## 回复 by mb_ugnawvja (#42)

*2026-3-20 11:17*

感谢分享

## 回复 by wx_啊啊啊啊 (#43)

*2026-3-20 14:00*

感谢分享

## 回复 by s1nec-1o (#44)

*2026-3-20 14:09*

看看

## 回复 by wx_。。。。_455 (#45)

*2026-3-20 14:09*

666

## 回复 by 小木马 (#46)

*2026-3-20 14:14*

666666666

## 回复 by mb_uvyukvot (#47)

*2026-3-20 15:19*

666

## 回复 by 破客 (#48)

*2026-3-20 15:27*

66666

## 回复 by mb_cbgtaveo (#49)

*2026-3-20 15:55*

666666666666

## 回复 by dob_C (#50)

*2026-3-20 15:59*

感谢分享

## 回复 by 4Chan (#51)

*2026-3-20 16:17*

666

## 回复 by SInnon (#52)

*2026-3-20 18:29*

666666666666

## 回复 by widy二八 (#53)

*2026-3-20 18:44*

666666

## 回复 by mb_wdhhagbo (#54)

*2026-3-20 22:05*

666666

## 回复 by wuchonghua (#55)

*2026-3-21 02:36*

666,7神大神

## 回复 by huangjw (#56)

*2026-3-21 09:49*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by asuralove (#57)

*2026-3-21 10:11*

666

## 回复 by xwysj (#58)

*2026-3-21 16:33*

666666

## 回复 by mb_srmwcgoy (#59)

*2026-3-21 22:16*

666666666666

## 回复 by mb_euhyowpw (#60)

*2026-3-22 10:43*

666

## 回复 by 温泉划水鱼 (#61)

*2026-3-22 15:14*

xuexi

## 回复 by flyocean (#62)

*2026-3-22 15:48*

666

## 回复 by Youlor (#63)

*2026-3-22 16:01*

666

## 回复 by 我不是卷王 (#64)

*2026-3-22 16:05*

666

## 回复 by LQ6H (#65)

*2026-3-22 16:23*

666

## 回复 by 夯大力 (#66)

*2026-3-22 20:48*

精品

## 回复 by 学计算机睡觉 (#67)

*2026-3-22 22:02*

666

## 回复 by wx_故事与酒 (#68)

*2026-3-22 23:15*

66666666666666666666

## 回复 by wx_35 (#69)

*2026-3-23 07:50*

11

## 回复 by mb_abajbief (#70)

*2026-3-23 08:39*

6

## 回复 by huangjw (#71)

*2026-3-23 09:04*

火钳刘明

## 回复 by mb_ktasfpbp (#72)

*2026-3-23 11:32*

666666

## 回复 by wx_暗影异童 (#73)

*2026-3-23 11:49*

6666

## 回复 by qqqiu (#74)

*2026-3-23 11:58*

6

## 回复 by mb_nntqdxvc (#75)

*2026-3-23 14:27*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by 0x530c (#76)

*2026-3-23 18:55*

6666

## 回复 by mb_ffutjsbk (#77)

*2026-3-23 19:04*

66666

## 回复 by XJ。 (#78)

*2026-3-23 19:16*

666

## 回复 by hacker521 (#79)

*2026-3-23 20:18*

不错哦~

## 回复 by mb_ekhqutmo (#80)

*2026-3-23 20:19*

看看

## 回复 by fengvmu (#81)

*2026-3-23 20:31*

6666

## 回复 by huluxia (#82)

*2026-3-23 22:50*

66666666

## 回复 by mb_uktygsmq (#83)

*2026-3-24 00:37*

6666666666

## 回复 by linix (#84)

*2026-3-24 09:26*

感谢分享，散花

## 回复 by GEKEZYX (#85)

*2026-3-24 09:47*

666

## 回复 by mb_jhohnbzu (#86)

*2026-3-24 10:12*

66

## 回复 by 错过 (#87)

*2026-3-24 10:18*

666

## 回复 by 土豆爱学习 (#88)

*2026-3-24 16:28*

666

## 回复 by 机车王子 (#89)

*2026-3-24 16:48*

这个讨论对我很有帮助，谢谢！

## 回复 by git_39829Makseeee (#90)

*2026-3-24 18:26*

6666

## 回复 by byhk (#91)

*2026-3-24 18:29*

谢谢分享

## 回复 by 29o (#92)

*2026-3-24 20:36*

11

## 回复 by MaYil (#93)

*2026-3-24 21:16*

感谢分享

## 回复 by OJ-BK (#94)

*2026-3-24 21:44*

666666

## 回复 by mb_gpgmubgh (#95)

*2026-3-24 21:50*

666

## 回复 by 一只鸭子 (#96)

*2026-3-24 23:17*

大佬，Orz

## 回复 by mb_mgmaxnuw (#97)

*2026-3-25 00:23*

6666666

## 回复 by 非凡人平常心 (#98)

*2026-3-25 00:31*

66

## 回复 by mb_sqetvntx (#99)

*2026-3-25 09:00*

xx

## 回复 by mb_vxufgfcw (#100)

*2026-3-25 10:10*

6666666

## 回复 by mb_fywmigrm (#101)

*2026-3-25 11:07*

1

## 回复 by kingking888 (#102)

*2026-3-25 11:08*

666

## 回复 by Matchman33 (#103)

*2026-3-25 11:49*

太强了

## 回复 by 会飞的锅 (#104)

*2026-3-25 14:31*

666666

## 回复 by maxcl (#105)

*2026-3-25 14:37*

6666

## 回复 by mb_gxuunnxx (#106)

*2026-3-25 15:22*

666

## 回复 by nirvanawoody (#107)

*2026-3-25 16:35*

牛，给你点赞

## 回复 by Xx_gg (#108)

*2026-3-25 18:01*

66666

## 回复 by 丶咖啡猫丶 (#109)

*2026-3-26 09:45*

666

## 回复 by 伊苏尔德 (#110)

*2026-3-26 09:59*

666

## 回复 by zouzhiqiang (#111)

*2026-3-26 09:59*

66666

## 回复 by chionyuna (#112)

*2026-3-26 10:34*

66666

## 回复 by fancy繁星 (#113)

*2026-3-26 18:54*

666

## 回复 by artake (#114)

*2026-3-27 06:41*

666

## 回复 by freakish (#115)

*2026-3-27 14:12*

1

## 回复 by mb_pbowocpw (#116)

*2026-3-27 14:18*

666666

## 回复 by didiid (#117)

*2026-3-27 14:27*

66666

## 回复 by mb_mlyojneh (#118)

*2026-3-27 15:12*

感谢分享

## 回复 by 我就是小熊猫 (#119)

*2026-3-27 15:34*

6666

## 回复 by 24LX (#120)

*2026-3-27 15:57*

学习

## 回复 by Sherry77 (#121)

*2026-3-27 16:39*

学习一下

## 回复 by 心有万象 (#122)

*2026-3-27 22:20*

666

## 回复 by git_843361313113 (#123)

*2026-3-28 03:02*

学学

## 回复 by Wolfxyb (#124)

*2026-3-28 10:24*

6666666666

## 回复 by PangBai (#125)

*2026-3-29 12:32*

1

## 回复 by 军哥i (#126)

*2026-3-31 10:16*

看看

## 回复 by 杀老师 (#127)

*2026-3-31 10:37*

666

## 回复 by 军哥i (#128)

*2026-3-31 10:51*

为什么我环境补完以后，调用返回值的结果返回的是null

## 回复 by s1nec-1o (#129)

*2026-3-31 14:47*

可以的

## 回复 by mb_bpqjsuuu (#130)

*2026-3-31 16:38*

1

## 回复 by wx_L_ (#131)

*2026-3-31 16:43*

666666

## 回复 by mb_yaeaedrh (#132)

*2026-3-31 17:21*

6666

## 回复 by mb_uzmffdbw (#133)

*2026-3-31 17:28*

666

## 回复 by hanjiefang (#134)

*2026-3-31 19:21*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by jaefern (#135)

*2026-4-1 11:20*

666

## 回复 by mb_tjqabdvq (#136)

*2026-4-3 11:01*

6666666

## 回复 by mb_hfbquwgl (#137)

*2026-4-3 14:42*

大佬威武

## 回复 by mb_qfjnvedi (#138)

*2026-4-4 06:43*

66666

## 回复 by mb_ybvqgbkl (#139)

*2026-4-4 16:30*

66666666

## 回复 by maomaolk (#140)

*2026-4-4 16:55*

666666

## 回复 by lizhenzhe (#141)

*2026-4-4 20:33*

666666

## 回复 by 小迷糊ddd (#142)

*2026-4-6 22:49*

感谢分享，学习一下。

## 回复 by mb_rzyawund (#143)

*2026-4-7 11:14*

666

## 回复 by YANG、 (#144)

*2026-4-7 12:58*

666666

## 回复 by mb_ggxkozau (#145)

*2026-4-9 11:03*

666666

## 回复 by Kk一刀 (#146)

*2026-4-10 11:08*

666

## 回复 by mb_xlviyutx (#147)

*2026-4-10 14:33*

666666

## 回复 by tjytjy (#148)

*2026-4-10 15:27*

666

## 回复 by r0k (#149)

*2026-4-15 14:29*

谢谢分享

## 回复 by 信仰666 (#150)

*2026-4-15 15:41*

学习一下，太强了

## 回复 by Freax (#151)

*2026-4-15 17:53*

666

## 回复 by johnwas (#152)

*2026-4-15 19:01*

666

## 回复 by sakmacc (#153)

*2026-4-16 19:43*

666

## 回复 by sir678 (#154)

*2026-4-17 17:24*

666

## 回复 by git_23977jackmama12138 (#155)

*2026-4-17 21:06*

66666666

## 回复 by mb_ckwbzclg (#156)

*2026-4-18 16:23*

感谢大佬

## 回复 by 勒LI (#157)

*2026-4-18 16:47*

666

## 回复 by 龙哥在不在 (#158)

*2026-4-18 20:42*

6666

## 回复 by mb_paopxhtx (#159)

*2026-4-19 14:27*

这么厉害的吗

## 回复 by xwtwho (#160)

*2026-4-19 15:16*

1

## 回复 by mb_ermtvtqr (#161)

*2026-4-20 17:37*

666

## 回复 by jw8888 (#162)

*2026-4-20 21:23*

66666666666666666

## 回复 by nrllh (#163)

*2026-4-22 19:58*

666

## 回复 by xiyewuqiu (#164)

*2026-4-22 23:52*

大佬太强了，已经开始学习了

## 回复 by ReverseApp (#165)

*2026-4-23 00:08*

666666

## 回复 by 9494 (#166)

*2026-4-23 21:11*

66666

## 回复 by 呼吸24K纯氧 (#167)

*2026-4-24 11:47*

666666

## 回复 by mb_ffsfxcfz (#168)

*2026-4-25 16:35*

666666

## 回复 by vip隐刺 (#169)

*2026-4-26 00:33*

学到就是赚到，看到就是经验！

## 回复 by Xnxin (#170)

*2026-4-26 06:08*

很强啊，学习一下

## 回复 by mb_odjbvqwf (#171)

*2026-4-27 19:51*

666

## 回复 by mb_rfeucrmf (#172)

*2026-4-28 12:08*

666

## 回复 by mb_rfeucrmf (#173)

*2026-4-28 12:08*

666

## 回复 by 街道办事处 (#174)

*2026-4-28 13:40*

111

## 回复 by Zzzr (#175)

*2026-4-28 14:34*

学习。

## 回复 by mJqalJqN (#176)

*2026-4-28 15:12*

1

## 回复 by pan_634488 (#177)

*2026-4-28 16:31*

6666

## 回复 by pan_634488 (#178)

*2026-4-28 16:31*

6666

## 回复 by pan_634488 (#179)

*2026-4-28 16:31*

6666

## 回复 by pan_634488 (#180)

*2026-4-28 16:31*

666

## 回复 by pan_634488 (#181)

*2026-4-28 16:31*

感谢分享

## 回复 by bisoso (#182)

*2026-4-29 08:07*

6666

## 回复 by console_ (#183)

*2026-4-29 10:33*

33333

## 回复 by console_ (#184)

*2026-4-29 10:33*

33333

## 回复 by console_ (#185)

*2026-4-29 10:33*

33333

## 回复 by console_ (#186)

*2026-4-29 10:33*

33333

## 回复 by console_ (#187)

*2026-4-29 10:34*

33333

## 回复 by console_ (#188)

*2026-4-29 10:34*

33333

## 回复 by console_ (#189)

*2026-4-29 10:34*

111

## 回复 by console_ (#190)

*2026-4-29 10:34*

1

## 回复 by br0nze (#191)

*2026-4-29 16:52*

six

## 回复 by br0nze (#192)

*2026-4-29 16:53*

6

## 回复 by mb_iiulbilc (#193)

*2026-4-30 09:13*

111

## 回复 by mb_iiulbilc (#194)

*2026-4-30 09:13*

11166666

## 回复 by mb_iiulbilc (#195)

*2026-4-30 09:14*

6666666

## 回复 by mb_iiulbilc (#196)

*2026-4-30 09:14*

6666666

## 回复 by mb_iiulbilc (#197)

*2026-4-30 09:37*

3333

## 回复 by mb_iiulbilc (#198)

*2026-4-30 09:37*

3333

## 回复 by mb_iiulbilc (#199)

*2026-4-30 09:41*

3333

## 回复 by 星落黎明 (#200)

*2026-4-30 12:54*

感谢分享

## 回复 by hygzs (#201)

*2026-4-30 13:45*

![image](https://bbs.kanxue.com/view/img/face/092.gif)

## 回复 by mb_rooofjxx (#202)

*2026-4-30 15:38*

666666666

## 回复 by mb_jkuospdr (#203)

*2026-5-6 14:36*

666

## 回复 by 陈天浩 (#204)

*2026-5-8 16:18*

6666

## 回复 by njxxdx (#205)

*2026-5-11 16:39*

感谢

## 回复 by hex_290388 (#206)

*2026-5-12 15:33*

kankan

## 回复 by iamxiaoq (#207)

*2026-5-13 16:22*

66666

## 回复 by 小若渴jh (#208)

*2026-5-13 16:27*

6666666666666666

## 回复 by chuyuan178 (#209)

*2026-5-13 18:29*

666

## 回复 by mb_ocigfxyo (#210)

*2026-5-13 20:26*

牛逼

## 回复 by 黄石 (#211)

*2026-5-15 11:21*

666666

## 回复 by mb_ysikfhxt (#212)

*2026-5-15 22:49*

111

## 回复 by 086Love (#213)

*2026-5-16 09:46*

学习

## 回复 by mb_frspcrqz (#214)

*2026-5-17 13:01*

666

## 回复 by mb_sajaoega (#215)

*2026-5-18 21:37*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 信心风暴 (#216)

*2026-5-21 12:12*

感谢分享

## 回复 by mb_rztmbvgb (#217)

*2026-5-21 13:36*

666

## 回复 by shuyangzjg (#218)

*2026-5-21 13:44*

看看，学习下

## 回复 by Ro0kie (#219)

*2026-5-22 20:51*

666

## 回复 by wx_北极星_493 (#220)

*2026-5-24 19:01*

看看

## 回复 by 简单的简单 (#221)

*2026-5-24 22:36*

1

## 回复 by gtathinkphp (#222)

*2026-5-25 08:58*

6666666666666666

## 回复 by ovo_帮我不c (#223)

*2026-5-25 12:19*

111

## 回复 by r0reborn (#224)

*2026-5-26 15:09*

6666

## 回复 by wx_技术Liu (#225)

*2026-5-28 14:33*

6666

## 回复 by mb_xnazhfyu (#226)

*2026-5-28 14:56*

大佬

## 回复 by 果冻大砍刀 (#227)

*2026-5-29 18:24*

学一学

## 回复 by 晴空万里丶 (#228)

*2026-5-31 18:19*

学习下

## 回复 by mb_sucnifie (#229)

*2026-6-1 15:13*

666

## 回复 by 小李08 (#230)

*2026-6-1 15:30*

666666

## 回复 by 这样的我 (#231)

*2026-6-2 11:46*

1

## 回复 by mb_qcshhquy (#232)

*2026-6-6 15:34*

666

## 回复 by issio (#233)

*2026-6-6 20:02*

感谢分享

## 回复 by mb_fvscuabi (#234)

*2026-6-6 20:39*

谢谢分享

## 回复 by mb_avjobzgi (#235)

*2026-6-7 12:54*

6666

## 回复 by Midsw (#236)

*2026-6-7 14:42*

nb。

## 回复 by git_14004xiabinhan2004 (#237)

*2026-6-13 13:52*

666

## 回复 by mb_xzwzvabc (#238)

*2026-6-18 07:24*

666666

## 回复 by mb_lurftzqi (#239)

*2026-6-18 16:38*

6666

## 回复 by mb_osxdmntv (#240)

*2026-6-19 18:20*

77777

## 回复 by git_98579rabbits0209 (#241)

*2026-6-20 15:46*

,66666

## 回复 by mb_leghawkh (#242)

*2026-6-22 00:01*

666

## 回复 by mb_paeqogwt (#243)

*2026-6-22 11:38*

学习

## 回复 by Timele (#244)

*2026-6-23 15:21*

66666

## 回复 by mb_pesxllvn (#245)

*2026-6-23 15:57*

1

## 回复 by Class___ (#246)

*2026-6-24 16:53*

666666

## 回复 by 田木果呦 (#247)

*2026-6-25 04:23*

6666
6666

## 回复 by mb_gcjwsflo (#248)

*2026-6-30 11:32*

666

## 回复 by Am1re (#249)

*2026-6-30 17:40*

666

## 回复 by curtainzzzz (#250)

*2026-6-30 22:30*

666666666666

## 回复 by mb_dcrbszvg (#251)

*2026-7-2 13:26*

6666

## 回复 by mb_txbqztiu (#252)

*2026-7-2 14:03*

6666

## 回复 by mb_audxeeaj (#253)

*2026-7-2 14:45*

66666

## 回复 by mb_gpxzdoej (#254)

*2026-7-5 11:10*

大佬nb

## 回复 by mb_zazihpbz (#255)

*2026-7-7 10:06*

666

## 回复 by hansa (#256)

*2026-7-8 10:35*

666666

## 回复 by git_71281rich168 (#257)

*2026-7-15 17:16*

111

## 回复 by 小尘0000 (#258)

*2026-7-17 14:50*

666

## 回复 by mb_wcezgawj (#259)

*2026-7-23 02:26*

学习一下

## 回复 by mb_ocfanoyj (#260)

*2026-7-23 13:24*

感谢你

## 回复 by jianxcao (#261)

*2026-7-23 14:18*

666666

## 回复 by 独一无二_370133 (#262)

*2026-7-27 11:30*

123456

## 回复 by mb_ifkqwpjq (#263)

*2026-7-27 13:48*

6666666666666

## 回复 by 随风而行aa (#264)

*2026-7-27 13:49*

看看

## 回复 by git_69678tuantmtb (#265)

*2026-7-29 11:32*

666

## 回复 by tt8369 (#266)

*2026-7-29 13:53*

学习了

## 回复 by onejane (#267)

*2026-7-29 14:20*

6

## 回复 by mb_pjvujuri (#268)

*2026-7-30 11:29*

8888

## 回复 by Lpangs (#269)

*2026-7-30 11:57*

学习

## 回复 by Zireael (#270)

*2026-8-1 01:03*

6666

## 回复 by 学习的小秦 (#271)

*2026-8-1 01:36*

6666666

## 回复 by 爱学习的小明 (#272)

*2026-8-1 02:14*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by junbo (#273)

111

## 回复 by 漂流的鱼 (#274)

666

## 回复 by mb_varcurxz (#275)

厉害啊

## 回复 by E_Obj (#276)

学习一下

## 回复 by 带壳的蜗牛 (#277)

666

## 回复 by wx_　　　　　　　　_126478 (#278)

666

## 回复 by git_40631tt123-web (#279)

66

## 回复 by jianxcao (#280)

6666
