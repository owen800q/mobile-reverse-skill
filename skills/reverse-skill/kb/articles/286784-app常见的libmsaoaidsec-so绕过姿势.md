---
title: '[分享]app常见的libmsaoaidsec.so绕过姿势'
url: https://bbs.kanxue.com/thread-286784.htm
tid: 286784
author: 櫬木汐
date: '2025-05-09'
tags: [Android安全, 分享, HOOK注入, 逆向分析]
crawled_at: '2026-07-31T14:10:23+08:00'
replies: 4
---

最近在学习安卓逆向的时候遇到了libmsaoaidsec.so导致无法frida注入，这里自己收集了一些绕过的方法，如有错误的地方还请各位大佬指正

# hook pthread_create

[[原创]【安卓逆向】libmsaoaidsec.so反调试及算法逆向案例(爱库存)-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-284816.htm)

用frida先注入一下，在输出hello之后直接被杀掉![图片](https://bbs.kanxue.com/upload/attach/202505/UP7YB8XDTBPM6SC.jpg)

![image](https://bbs.kanxue.com/upload/attach/202505/991035_Y9WCWDU6JWJNEKN.webp)

看看是加载了哪个so之后退出

```
function hook_dlopen() {    Interceptor.attach(Module.findExportByName(null, "android_dlopen_ext"),        {            onEnter: function (args) {                var pathptr = args[0];                if (pathptr !== undefined && pathptr != null) {                    var path = ptr(pathptr).readCString();                    console.log("load " + path);                }            }        }    );}
```

可以猜测是libmsaoaidsec.so这个so存在反frida注入![image-20250509163624287](https://bbs.kanxue.com/upload/attach/202505/UP7YB8XDTBPM6SC.jpg)![image](https://bbs.kanxue.com/upload/attach/202505/991035_HAAU4BRG9U2R2CH.webp)

关于绕过的方法网上很多，大多就是Hook pthread_create函数，然后nop掉他的创建的线程函数

```
function replace(addr) {    Interceptor.replace(addr, new NativeCallback(function () {        console.log(`replace ${addr}`)    }, 'void', []));}function nop_64(addr) {    Memory.protect(addr, 4 , 'rwx');    var w = new Arm64Writer(addr);    w.putRet();    w.flush();    w.dispose();}function hook_pthread_create(soname) {    let replaces = [];  // 用来记录已经替换的函数偏移    // int pthread_create(pthread_t *thread, const pthread_attr_t *attr, void *(*start_routine)(void*), void *arg);    let pthread_create = Module.findExportByName(null, "pthread_create");    if (!pthread_create) {        console.log("pthread_create not found in libc.so");        return;    }        Interceptor.attach(pthread_create, {        onEnter: function (args) {            //console.log("hooking pthread_create ", pthread_create)            let start_routine = args[2];            //console.log(start_routine)            let libmsaoaidsec = Process.findModuleByAddress(start_routine);            if (libmsaoaidsec && libmsaoaidsec.name === soname) {                if (!replaces.includes(start_routine.toString())) {                    let libmsaoaidsec_addr = libmsaoaidsec.base;                    let func_offset = start_routine.sub(libmsaoaidsec_addr);                    console.log("The thread function offset address in libmsaoaidsec.so(" + libmsaoaidsec_addr + ") is " + func_offset);                    console.log("replace: " + func_offset);                    //replaces.push(start_routine.toString());                    //nop_64(start_routine)                }            }        }    });}setImmediate(hook_pthread_create, "libmsaoaidsec.so")
```

成功命中了，但是nop掉这三处之后app不知道为什么就卡死了![image-20250509170859269](https://bbs.kanxue.com/upload/attach/202505/UP7YB8XDTBPM6SC.jpg)![image](https://bbs.kanxue.com/upload/attach/202505/991035_22C7AV9RAPP2QCZ.webp)

# hook clone

这里我又找到了更底层的clone函数创建线程检测方法

[[分享]某邦企业壳frida检测绕过-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-285932.htm)

![img](https://bbs.kanxue.com/upload/attach/202505/UP7YB8XDTBPM6SC.jpg)![image](https://bbs.kanxue.com/upload/attach/202505/991035_EENRRRMDFC6FSDN.webp)

```
function hook_clone(soname){    var clone = Module.findExportByName('libc.so', 'clone');    Interceptor.attach(clone, {        onEnter: function(args) {            // args[3] 子线程的栈地址。如果这个值为 0，可能意味着没有指定栈地址            if(args[3] != 0){                var addr = args[3].add(96).readPointer()                var so_name = Process.findModuleByAddress(addr).name;                var so_base = Module.getBaseAddress(so_name);                var offset = (addr - so_base);                console.log("===============>", so_name, addr,offset, offset.toString(16));            }        },        onLeave: function(retval) {             }    });     }setImmediate(hook_clone, "libmsaoaidsec.so")
```

这样也能成功获取到线程函数的地址

![image-20250509165630393](https://bbs.kanxue.com/upload/attach/202505/UP7YB8XDTBPM6SC.jpg)

![image](https://bbs.kanxue.com/upload/attach/202505/991035_CNPTPJK2KW34689.webp)

# hook strstr

[[原创] frida常用检测点及其原理--一把梭方案-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-278145-1.htm#msg_header_h2_6)

我们不妨进入这几个线程函数，来看看到底做了些什么

![image-20250509174257945](https://bbs.kanxue.com/upload/attach/202505/UP7YB8XDTBPM6SC.jpg)![image](https://bbs.kanxue.com/upload/attach/202505/991035_3CU8K2NUBP4V6MR.webp)

![image](https://bbs.kanxue.com/upload/attach/202505/991035_UC4SWW3G3TAJBMH.webp)

可以推测，就是open了一些系统文件，然后fgets获取其信息，再进行ststsr的关键点检测

```
function hook_pthread_create(soname) {    var pt_strstr = Module.findExportByName("libc.so", 'strstr');    var pt_strcmp = Module.findExportByName("libc.so", 'strcmp');     Interceptor.attach(pt_strstr, {        onEnter: function (args) {            var str1 = args[0].readCString();            var str2 = args[1].readCString();            if (                str2.indexOf("REJECT") !== -1 ||                str2.indexOf("tmp") !== -1 ||                str2.indexOf("frida") !== -1 ||                str2.indexOf("gum-js-loop") !== -1 ||                str2.indexOf("gmain") !== -1 ||                str2.indexOf("linjector") !== -1            ) {                //console.log("strstr-->", str1, str2);                this.hook = true;            }        }, onLeave: function (retval) {            if (this.hook) {                retval.replace(0);            }        }    });     Interceptor.attach(pt_strcmp, {        onEnter: function (args) {            var str1 = args[0].readCString();            var str2 = args[1].readCString();            if (                str2.indexOf("REJECT") !== -1 ||                str2.indexOf("tmp") !== -1 ||                str2.indexOf("frida") !== -1 ||                str2.indexOf("gum-js-loop") !== -1 ||                str2.indexOf("gmain") !== -1 ||                str2.indexOf("linjector") !== -1            ) {                //console.log("strcmp-->", str1, str2);                this.hook = true;            }        }, onLeave: function (retval) {            if (this.hook) {                retval.replace(0);            }        }    })}setImmediate(hook_pthread_create, "libmsaoaidsec.so")
```

直接对这些检测点的结果返回false, 同样可以绕过![image-20250509174520356](https://bbs.kanxue.com/upload/attach/202505/UP7YB8XDTBPM6SC.jpg)![image](https://bbs.kanxue.com/upload/attach/202505/991035_ZN2RBHZX7EUVBVD.webp)

# 魔改Frida -> rusda

[[原创]frida16.2.1 编译patch全过程-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-284739.htm)

frida和frida-tools使用官方源即可，然后在手机上使用release的rusda-server-android-arm64，无需手动编译

使用rusda后发现居然直接绕过了

![image-20250509171817811](https://bbs.kanxue.com/upload/attach/202505/UP7YB8XDTBPM6SC.jpg)![image](https://bbs.kanxue.com/upload/attach/202505/991035_B87AJSRGXNWRCA8.webp)

---

# 回复

## 回复 by inkeyy (#2)

*2025-5-9 19:15*

洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害洋参好厉害

## 回复 by huangjw (#3)

*2025-5-12 09:51*

good job

## 回复 by @=llfly (#4)

*2025-5-12 16:49*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by iBa0 (#5)

*2025-5-15 17:50*

libmsaoaidsec.so 不是专门用来检测frida的其实。大厂有自己的so来检测
