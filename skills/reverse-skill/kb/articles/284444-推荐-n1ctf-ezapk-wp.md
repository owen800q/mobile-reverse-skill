---
title: '[原创][推荐]n1ctf ezapk wp'
url: https://bbs.kanxue.com/thread-284444.htm
tid: 284444
author: SleepAlone
date: '2024-11-16'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:18:43+08:00'
replies: 14
---

# n1ctf ezapk wp

## 0x01 写在前面

又是一个周五晚上，就在刚才搜集到这道题的关键“证据”，到这里这道题算是完全”破解“成功（开心）。所以就写一篇文章，总结下我的心路历程吧，包括但不限于：

1. ezapk的解体思路
2. 环境问题搭建tips
3. 完整的脚本（避免缺头少尾，让新手看了懵逼）

总之，完全是新手向的文章，遇到的坑，一步步怎么做，我都会说清楚，即使你是新手也没关系。
看完这篇文章你讲学到：

- 安卓逆向基本思路
	- dex反编译
	- frida hook
	- CE 找出是谁在暗中修改函数
- 深入JNI机制
- frida 环境搭建以及基本使用
- CE 使用 以及 CE server 构建

## 0x02 题目背景

![image.png](https://bbs.kanxue.com/upload/attach/202411/950548_BVZWWDJDAQS3B8Y.png)

题目非常简单，输入n1ctf{flag}, 点击check检查，很正规的安卓题

## 0x03 开门见山-dex反编译

放入jadx-gui查看一下主逻辑：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243 | `public` `class` `MainActivity` `extends` `AppCompatActivity {``private` `ActivityMainBinding binding;` `public` `native` `String enc(String str);` `public` `native` `String stringFromJNI();` `/* JADX INFO: Access modifiers changed from: protected */``@Override // androidx.fragment.app.FragmentActivity, androidx.activity.ComponentActivity, androidx.core.app.ComponentActivity, android.app.Activity``public void onCreate(Bundle bundle) {``super.onCreate(bundle);``ActivityMainBinding inflate = ActivityMainBinding.inflate(getLayoutInflater());``this.binding = inflate;``setContentView(inflate.getRoot());``this.binding.CheckButton.setOnClickListener(new View.OnClickListener() { // from class: com.n1ctf2024.ezapk.MainActivity$$ExternalSyntheticLambda0``@Override // android.view.View.OnClickListener``public final void onClick(View view) {``MainActivity.this.m157lambda$onCreate$0$comn1ctf2024ezapkMainActivity(view);``}``});``}` `/* JADX INFO: Access modifiers changed from: package-private */``/* renamed from: lambda$onCreate$0$com-n1ctf2024-ezapk-MainActivity, reason: not valid java name */``public /* synthetic */` `void` `m157lambda$onCreate$``0``$comn1ctf2024ezapkMainActivity(View view) {``String obj =` `this``.binding.flagText.getText().toString();``if` `(obj.startsWith(``"n1ctf{"``) && obj.endsWith(``"}"``)) {``if` `(enc(obj.substring(``6``, obj.length() -` `1``)).equals(``"iRrL63tve+H72wjr/HHiwlVu5RZU9XDcI7A="``)) {``Toast.makeText(``this``,` `"Congratulations!"``,` `1``).show();``return``;``}` `else` `{``Toast.makeText(``this``,` `"Try again."``,` `0``).show();``return``;``}``}``Toast.makeText(``this``,` `"Try again."``,` `0``).show();``}` `static` `{``System.loadLibrary(``"native2"``);``System.loadLibrary(``"native1"``);``}``}` |
|-|-|

可以看到主要逻辑在enc中，enc 属于native 函数，通过JNI调用，enc位于通过System.loadLibrary()的两个so中

## 0x03 迷雾重重-JNI逆向

ida 打开libnative.so反编译会发现有大量的类似指针数组的调用，其实这是JNI调用

`关于JNI调用可以看：[https://docs.oracle.com/javase/7/docs/technotes/guides/jni/spec/jniTOC.html](https://docs.oracle.com/javase/7/docs/technotes/guides/jni/spec/jniTOC.html)`

native code 想要访问java VM的特性就需要调用JNI函数，调用JNI函数需要JNI interface pointer

并且JNI interface pointer是native函数的第一个参数，如下：

| 123456789 | `package` `pkg;`  `class` `Cls {`  `native` `double` `f(``int` `i, String s);`  `...`  `}` |
|-|-|

这里 double 会经过名称混淆变为Java_pkg_Cls_f_ILjava_lang_String_2

| 1234567891011121314151617 | `jdouble Java_pkg_Cls_f__ILjava_lang_String_2 (``JNIEnv *env,` `/* interface pointer */``jobject obj,` `/* "this" pointer */``jint i,` `/* argument #1 */``jstring s)` `/* argument #2 */``{``/* Obtain a C-copy of the Java string */``const` `char` `*str = (*env)->GetStringUTFChars(env, s, 0);` `/* process the string */``...` `/* Now we are done with str */``(*env)->ReleaseStringUTFChars(env, s, str);` `return` `...``}` |
|-|-|

JNI interface pointer是一个pointer to pointer，具体来说就是一个指针数组，这个数组保存着JNI函数的地址，包括：

| 123456789101112131415161718 | `const` `struct` `JNINativeInterface ... = {` `NULL,``NULL,``NULL,``NULL,``GetVersion,` `DefineClass,``//... 太长省略` `GetJavaVM,` `GetStringRegion,``GetStringUTFRegion,``//...``GetObjectRefType``};` |
|-|-|

但是ida中并没有JNIEnv等等结构体，一个个倒入自动识别太麻烦，手动计算又太蠢

该怎么办呢？

## 0x04 拨云见日-frida hook

### 定位enc

其实真正常用的JNI 函数就那几个，可以看到enc中传入了字符串，所以native函数想要获取这个字符串，会调用关于String的JNI调用 一般为GetStringUTFChars

`关于环境：我的pc是mac m1,手头也没有安卓设备，最后选择mu mu pro模拟器（啥都好，就是要花钱）`

在mu mu pro模拟器中安装好 frida server后，运行frida server后就可以hook了

```
Java.perform(() => {
    const MainActivity = Java.use("com.n1ctf2024.ezapk.MainActivity");

    MainActivity.enc.implementation = function(input) {
        console.log("enc called with input:", input);
        const result = this.enc(input);
        startHook();
        // startHooklib();
        console.log("enc returned:", result);

        return result;
    };
});

function startHook(){
    const lib_art = Process.findModuleByName('libart.so');
    const symbols = lib_art.enumerateSymbols();
    for (let symbol of symbols) {
        var name = symbol.name;
        if (name.indexOf("art") >= 0) {
            if ((name.indexOf("CheckJNI") == -1) && (name.indexOf("JNI") >= 0)) {
                if (name.indexOf("GetStringUTFChars") >= 0) {
                    console.log('start hook', symbol.name);
                    Interceptor.attach(symbol.address, {
                        onEnter: function (arg) {
                            console.log('GetStringUTFChars called from:\n' + Thread.backtrace(this.context, Backtracer.ACCURATE).map(DebugSymbol.fromAddress).join('\n') + '\n');
                        },
                        onLeave: function (retval) {
                            console.log('onLeave GetStringUTFChars:', ptr(retval).readCString())
                        }
                    })
                }
            }
        }
    }
}
```

运行结果

```
// frida -U -f com.n1ctf2024.ezapk -l hook.js
GetStringUTFChars called from:
0x6d55c7117c libnative1.so!0x1b17c
//没有 多点几次 hook和输出在一起 所有你需要hook了 再点几次
```

这里就知道sub_1b148是enc了

### stacktrace

接下来，定位enc调用了哪些函数，还是hook

```
ava.perform(() => {
    const MainActivity = Java.use("com.n1ctf2024.ezapk.MainActivity");

    MainActivity.enc.implementation = function(input) {
        console.log("enc called with input:", input);
        const result = this.enc(input);
        //startHook();
        startHooklib();
        console.log("enc returned:", result);

        return result;
    };
});

function startHooklib(){

    var functions_lib1 = Module.enumerateExports("libnative1.so");
    functions_lib1 = []
    var functions_lib2 = Module.enumerateExports("libnative2.so");

    functions_lib1 = functions_lib1.map(item => {
        return { ...item, module: "libnative1.so" };
    })

    functions_lib2 = functions_lib2.map(item => {
        return { ...item, module: "libnative2.so" };
    })

    var functions = [...functions_lib1,...functions_lib2];

    // {
    //     "address": "0x6d56602ca8",
    //     "name": "aE7KMLpKuUbB",
    //     "type": "function"
    // }

    functions.forEach(function(func) {
        var moduleBase_lib1 = Module.findBaseAddress(func.module);
        var moduleBase_lib2 = Module.findBaseAddress(func.module);
        if ( moduleBase_lib1 && moduleBase_lib2) {
            var address = func.address
            // console.log("Attaching to function at " + func.module + "!" + func.addr);
            Interceptor.attach(address, {
                onEnter: function(args) {
                    console.log(func.module + " function called at "  + func.address + " " + func.name);
                },
                onLeave: function(retval) {
                    console.log(func.module + " function returned at "+ func.address + " " + func.name);
                }
            });
        } else {
            console.log("Module " + func.module + " not found!");
        }
    });
}
```

运行结果

```
libnative2.so function called at 0x6d55c0306c iusp9aVAyoMI
libnative2.so function returned at 0x6d55c0306c iusp9aVAyoMI
libnative2.so function called at 0x6d55c032c0 SZ3pMtlDTA7Q
libnative2.so function returned at 0x6d55c032c0 SZ3pMtlDTA7Q
libnative2.so function called at 0x6d55c03ab0 UqhYy0F049n5
libnative2.so function returned at 0x6d55c03ab0 UqhYy0F049n5
```

这就获取了调用顺序，在ida里看一下，一眼丁真，分别是EOR，rc4，base64

## 0x05 九九八十难-谁改了我的rand()

| 12345678910111213141516171819202122 | `_BYTE *__fastcall iusp9aVAyoMI(``__int64` `a1,` `size_t` `a2)``{``size_t` `i;` `// [xsp+0h] [xbp-40h]``_BYTE *v4;` `// [xsp+8h] [xbp-38h]` `v4 =` `malloc``(a2);``__memcpy_chk(v4, a1, a2, -1LL);``for` `( i = 0LL; i < a2; ++i )``v4[i] ^=` `rand``();``return` `v4;``}``_BYTE *__fastcall SZ3pMtlDTA7Q(``__int64` `a1,` `int` `a2)``{``v20[2] = *(_QWORD *)(_ReadStatusReg(ARM64_SYSREG(3, 3, 13, 0, 2)) + 40);``v16 =` `malloc``(a2);``__memcpy_chk(v16, a1, a2, -1LL);``v20[1] = 0LL;``v20[0] = 0LL;``for` `( i = 0; i < 16; ++i )``*((_BYTE *)v20 + i) =` `rand``();``// ....` `}` |
|-|-|

可以看到EOR和rc4的密钥都是rand()获取的，libnative2.so中的.init.array中有个init函数，初始化了随机种子

| 1234 | `void` `init()``{``srand``(0x134DAD5u);``}` |
|-|-|

真正解密会发现解密失败，实际上这里rand被修改了，如法炮制，在libnative1.so的.init.array中有三个函数

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758 | `__int64` `sub_1B540()``{``FILE` `*v0;` `// x20``char` `*v1;` `// x0``unsigned` `__int64` `v2;` `// x19``__int64` `v3;` `// x24``__int64` `v4;` `// x22``__int64` `v5;` `// x23``__int64` `v6;` `// x25``__int64` `v7;` `// x8``__int64` `(**v8)();` `// x19``__int64` `result;` `// x0``char` `filename[4096];` `// [xsp+8h] [xbp-1008h] BYREF``__int64` `v11;` `// [xsp+1008h] [xbp-8h]` `v11 = *(_QWORD *)(_ReadStatusReg(ARM64_SYSREG(3, 3, 13, 0, 2)) + 40);``sub_1B6C4(filename);``v0 =` `fopen``(filename,` `"r"``);``if` `( v0 )``{``while` `(` `fgets``(filename, 4096, v0) )``{``if` `(` `strstr``(filename,` `"libnative2.so"``) )``{``v1 =` `strtok``(filename,` `"-"``);``v2 = strtoull(v1, 0LL, 16);``goto` `LABEL_6;``}``}``}``v2 = 0LL;``LABEL_6:``fclose``(v0);``sub_1B000(v2, &qword_40F70);``if` `( (``int``)(qword_40FC8 / 0x18uLL) < 1 )``{``LABEL_10:``v7 = 0LL;``}``else``{``v3 = (unsigned` `int``)(qword_40FC8 / 0x18uLL);``v4 = qword_40F78;``v5 = unk_40F80;``v6 = qword_40FC0 + 8;``while` `(` `strcmp``((``const` `char` `*)(v5 + *(unsigned` `int` `*)(v4 + 24LL * *(unsigned` `int` `*)(v6 + 4))),` `"rand"``) )``{``v6 += 24LL;``if` `( !--v3 )``goto` `LABEL_10;``}``v7 = *(_QWORD *)(v6 - 8);``}``v8 = (``__int64` `(**)())(v7 + v2);``result = mprotect(v8, 8uLL, 3);``*v8 = sub_1B140;``return` `result;``}` |
|-|-|

这里可以很明显的是一个rand的替换操作，rand替换为了sub_1B140，这个函数恒定返回233，就是真正的密钥了。

## 0x06 on more thing-我的思考

如果这个修改rand got表的操作不在.init.got表中，如何找到他呢？

### 方案一 CE + CE server + frida hook（小坑+小坑+大坑）

tips：

- `官网只给了mac版本的7.5.2 CE 但是给的CE server是7.5，所以连接的时候会报错，最后只能自己编译，编译的时候ndk版本别太高，不然一堆报错（血的教训）`
- `如果主机和模拟器不能ping通 那连接ce server时 使用127.0.0.1的话 记得 adb forwar tcp:52736 tcp:52736`

要看so 在哪被修改了，CE 扫描的时机很重要，要在native2加载的时候扫描一次，然后native1加载后或者再往后的一个时机扫描改变的字节

所以要hook System.loadLibrary()

`这里真是大坑了，查看github issues 才知道System.loadLibrary()是不可以hook的函数之一，因为你在Java.perfrom()里使用，但它会修改classloadrer，导致报错`

所以最根本的方法就是hook dlopen 或者 android_dlopen_ext

这里我选择 hook android_dlopen_ext，在 native1加载的时候暂停一会，方便CE 扫描

| 1234567891011121314151617 | `Interceptor.attach(Module.findExportByName(``'libc.so'``,` `'android_dlopen_ext'``), {``onEnter:` `function``(args) {``var` `libraryPath = Memory.readUtf8String(args[0]);` `// 第一个参数是库路径``console.log(``'android_dlopen_ext called to load library: '` `+ libraryPath);``if` `(libraryPath.indexOf(``'native1.so'``) !== -1) {``console.log(``'Pausing for 10 seconds before loading native1.so...'``);``// 暂停 10 秒``var` `sleep_string = Module.findExportByName(``'libc.so'``,` `'sleep'``);``var` `sleep_address = parseInt(sleep_string, 16);``new` `NativeFunction(ptr(sleep_address),` `'void'``, [``'int'``])(20);``}``},``onLeave:` `function``(retval) {``// 你可以在此修改返回值，或输出其他信息``console.log(``'android_dlopen_ext returned: '` `+ retval);``}``});` |
|-|-|

![image.png](https://bbs.kanxue.com/upload/attach/202411/950548_GDU7PHZ5ENW26QB.png)

### 方案二 frida hook （推荐）

hook mprotect的调用，关注地址在so地址范围的地址

| 12345678910111213141516171819202122232425262728 | `hook_mprotect()``var module = Process.findModuleByName(``'libnative2.so'``);``console.``log``(``'libnative2.so loaded at: '` `+ module.base);` `function hook_mprotect(){``// 使用 Frida 钩取 mprotect 函数``Interceptor.attach(Module.findExportByName(``"libc.so"``,` `'mprotect'``), {``onEnter: function(args) {``// 获取函数参数``this``.addr = args[0];` `// addr 参数：指向内存区域的指针``this``.len = args[1];` `// len 参数：内存区域的长度``this``.prot = args[2];` `// prot 参数：内存保护标志` `// console.log(this.len.toString());` `// if(this.len.toString() === '0x8'){``console.``log``(``'mprotect called'``);``console.``log``(``'Address: '` `+` `this``.addr,``'Length: '` `+` `this``.len +` `'Protection: '` `+` `this``.prot);``// }` `},``onLeave: function(retval) {``// 你可以在此修改函数的返回值，或者在返回时打印一些信息``// console.log('mprotect return value: ' + retval);``}``});` `}` |
|-|-|

运行结果

| 12 | `mprotect called``Address: 0x6d55c3c3f8 Length: 0x8Protection: 0x3` |
|-|-|

计算偏移 正好是0x43f8 也就是 rand_ptr的位置

CE 查看修改后的内容

![image.png](https://bbs.kanxue.com/upload/attach/202411/950548_GVMZYFEE4NZM758.png)

正好是 native1 中 sub_1B140

## 0x07 总结

整体 难度不大 但是很有趣 这个过程中探索了各种工具的使用 各种环境的搭建 还是学到了很多，感谢你看到了这里 祝你玩的开心。

上传的附件：
- ezapk.apk

（9.82MB，29次下载）

---

# 回复

## 回复 by iBa0 (#2)

*2024-11-26 10:43*

mac m1可以使用genymotion模拟器也挺好用的，写的很详细![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by SleepAlone (#3)

*2024-11-27 21:06*

>
> [WMBa0](https://bbs.kanxue.com/user-971547.htm)
>
>  mac m1可以使用genymotion模拟器也挺好用的，写的很详细[em_003]
>
>

好的佬 我试试，感谢夸奖

## 回复 by mb_vntjoaqu (#4)

*2024-11-28 19:52*

你好，请问题目在哪下载

## 回复 by SleepAlone (#5)

*2024-11-28 20:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_vntjoaqu](https://bbs.kanxue.com/user-986688.htm)
>
>  你好，请问题目在哪下载
>
>

我更新下附件

## 回复 by 软件君子 (#6)

*2024-11-30 17:55*

开发者还有这么骚的操作 哈哈

## 回复 by 吃饭去2 (#7)

*2024-12-4 11:49*

我用的雷电模拟器，使用这个脚本都用不了，是什么情况

## 回复 by SleepAlone (#8)

*2024-12-4 14:56*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  吃饭去2](https://bbs.kanxue.com/user-884348.htm)
>
>  我用的雷电模拟器，使用这个脚本都用不了，是什么情况
>
>

frida server安装好了吗 给root权限了吗

## 回复 by 吃饭去2 (#9)

*2024-12-4 21:42*

>
> [SleepAlone](https://bbs.kanxue.com/user-950548.htm)
>
>  frida server安装好了吗 给root权限了吗
>
>
>

雷电用的fridaserver-android-x86-64，有装面具，脚本运行后出来的是libhoudini.so，并且偏移不一样

## 回复 by SleepAlone (#10)

*2024-12-5 13:24*

libhoudini.so 是专门用于 ARM-on-x86 的仿真, 题目中的两个so都是arm的，你模拟器又是x86的所以会这样，现在安卓不都是arm架构吗，你的为啥是x86 很奇怪

## 回复 by 吃饭去2 (#11)

*2024-12-5 14:45*

>
> [SleepAlone](https://bbs.kanxue.com/user-950548.htm)
>
>  libhoudini.so 是专门用于 ARM-on-x86 的仿真, 题目中的两个so都是arm的，你模拟器又是x86的所以会这样，现在安卓不都是arm架构吗，你的为啥是x86 很奇怪
>
>

我用的是mumu模拟器，Process.findModuleByName('libnative1.so');Module.findBaseAddress("libnative1.so")，这两个返回都是null。估计要用真机来做

## 回复 by 吃饭去2 (#12)

*2024-12-5 14:57*

你的是苹果。。。就是arm架构所以使用模拟器没问题

## 回复 by SleepAlone (#13)

*2024-12-5 20:25*

确实 你的x86跑arm的模拟器 可能会遇到一些问题 真的话 应该就没啥问题

## 回复 by SleepAlone (#14)

*2024-12-5 20:26*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  吃饭去2](https://bbs.kanxue.com/user-884348.htm)
>
>  你的是苹果。。。就是arm架构所以使用模拟器没问题
>
>

确实 你的x86跑arm的模拟器 可能会遇到一些问题 真的话 应该就没啥问题

## 回复 by SleepAlone (#15)

*2024-12-5 20:27*

>
> [SleepAlone](https://bbs.kanxue.com/user-950548.htm)
>
>  确实 你的x86跑arm的模拟器 可能会遇到一些问题 真的话 应该就没啥问题
>
>

真机的话
