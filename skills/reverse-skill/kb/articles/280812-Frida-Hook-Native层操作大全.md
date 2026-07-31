---
title: '[原创]Frida-Hook-Native层操作大全'
url: https://bbs.kanxue.com/thread-280812.htm
tid: 280812
author: Shangwendada
date: '2024-03-07'
tags: [Android安全, 原创, HOOK注入, 逆向分析, 工具脚本]
crawled_at: '2026-07-31T14:30:28+08:00'
replies: 13
---

## 前期准备

- 使用 jadx 进行逆向工程的基础知识。
- 能够理解 Java 代码。
- 能够编写简短的 JavaScript 代码片段。
- 熟悉 adb。
- 已 root 的设备。
- 对 x86/ARM64 汇编和逆向工程有基础了解。

## 1、Hook Native层中调用的函数并且读取传入的参数

对于Native层的函数Hook，我们使用如下模板

| 12345678910 | `Interceptor.attach(targetAddress, {``onEnter:` `function` `(args) {``console.log(``'Entering '` `+ functionName);``// Modify or log arguments if needed``},``onLeave:` `function` `(retval) {``console.log(``'Leaving '` `+ functionName);``// Modify or log return value if needed``}``});` |
|-|-|

- `Interceptor.attach`：将回调函数附加到指定的函数地址。`targetAddress` 应该是我们想要挂钩的本地函数的地址。
- `onEnter`：当挂钩的函数被调用时，调用此回调。它提供对函数参数 (`args`) 的访问。
- `onLeave`：当挂钩的函数即将退出时，调用此回调。它提供对返回值 (`retval`) 的访问。
需要获取targetAddress我们可以方便的使用如下API

1. `Module.enumerateExports()`
通过调用 Module.enumerateExports()，我们可以获取到导出函数的名称、地址以及其他相关信息。这些信息对于进行函数挂钩、函数跟踪或者调用其他函数都非常有用。
2. `Module.getExportByName()`
当我们知道要查找的导出项的名称但不知道其地址时，可以使用 Module.getExportByName()。通过提供导出项的名称作为参数，这个函数会返回与该名称对应的导出项的地址。
3. `Module.findExportByName()`
这与 Module.getExportByName() 是一样的。唯一的区别在于，如果未找到导出项，Module.getExportByName() 会引发异常，而 Module.findExportByName() 如果未找到导出项则返回 `null`。让我们看一个示例。
4. `Module.getBaseAddress()`
通过调用 Module.getBaseAddress() 函数，我们可以获取指定模块的基址地址，然后可以基于这个基址地址进行偏移计算，以定位模块内部的特定函数、变量或者数据结构
5. `Module.enumerateImports()`
通过调用 Module.enumerateImports() 函数，我们可以获取到指定模块导入的外部函数或变量的名称、地址以及其他相关信息。

### 例题 Frida-Labs 0x8

#### MainActivity

![file](https://bbs.kanxue.com/upload/attach/202403/979679_7ERN84625EDTGHU.jpg)
可以发现，程序从EditText控件中获取到了用户的输入，然后调用了native层中的cmpstr函数进行比较。

#### Navtive层逻辑

![file](https://bbs.kanxue.com/upload/attach/202403/979679_BH8PQCUN8R5W3D7.jpg)
程序在cmpstr中使用了strcmp函数，那么我们只需要拿到strcmp函数的传入参数就可以知道程序的正确输入了

#### Hook begin

首先我们使用Module.enumerateImports("libfrida0x8.so")查看导入表
![file](https://bbs.kanxue.com/upload/attach/202403/979679_HXZ7QJ6H7U4X6KY.jpg)
可以发现strcmp来自于libc.so，那么我们就可以使用Module.findExportByName("libc.so","strcmp");来获取strcmp的地址了
![file](https://bbs.kanxue.com/upload/attach/202403/979679_C7C5Q6RWU32M2CG.jpg)

获取了strcmp的地址就可以使用之前给的模板进行Hook了

| 12345678910111213141516171819202122 | `function` `hook(){` `var` `targetAddress = Module.findExportByName(``"libc.so"``,``"strcmp"``);``console.log(``"Strcmp Address: "``,targetAddress.toString(16));` `Interceptor.attach(targetAddress,{``onEnter:``function` `(args){` `},onLeave:``function``(retval){` `}``})``console.log(``"success!"``);``}`  `function` `main(){``Java.perform(``function` `(){``hook();``})``}``setImmediate(main);` |
|-|-|

但是我们需要注意的是strcmp可能不止调用一次，因此我们需要判断strcmp的第一个参数是否为0我们才进行操作，不然hook可能会一直循环输出
![file](https://bbs.kanxue.com/upload/attach/202403/979679_Z2MVWBT4SNTBNHY.jpg)
因此我们可以使用Memory.readUtf8String(args[0]);来获取我们的输入字符串，平且使用 if (input.includes("111"))来判断

### hook代码

| 1234567891011121314151617181920212223242526 | `function` `hook(){` `var` `targetAddress = Module.findExportByName(``"libc.so"``,``"strcmp"``);``console.log(``"Strcmp Address: "``,targetAddress.toString(16));` `Interceptor.attach(targetAddress,{``onEnter:``function` `(args){``var` `input = Memory.readUtf8String(args[0]);``if` `(input.includes(``"111"``)){``console.log(Memory.readUtf8String(args[1]));``}` `},onLeave:``function``(retval){` `}``})``console.log(``"success!"``);``}`  `function` `main(){``Java.perform(``function` `(){``hook();``})``}``setImmediate(main);` |
|-|-|

![file](https://bbs.kanxue.com/upload/attach/202403/979679_RUPEFUFA7SG7DTQ.jpg)

## 2、Hook修改native层程序返回值

首先还是给出hook的模板如下：

| 12345678 | `Interceptor.attach(functionaddr, {``onEnter:` `function` `(args) {` `},``onLeave:` `function` `(retval) {` `}``});` |
|-|-|

可以看到在onLeave中有一个参数retval，这个retval，就是我们hook上的程序的返回值，我们可以使用retval.replace(val)来修改返回值。

### 例题 Frida-labs 0x9

#### MainActivity

![file](https://bbs.kanxue.com/upload/attach/202403/979679_6CTE2Q9DXGEQC5T.jpg)
可以发现程序根据native层的check_flag 方法的返回值

#### check_flag

![file](https://bbs.kanxue.com/upload/attach/202403/979679_YUWA3KUKDV2NZ3C.jpg)
只是简简单单的返回了一个1

#### hookbegin

首先使用Module.enumerateExports("liba0x9.so")，查看导出表，看看check_flag方法的偏移地址
![file](https://bbs.kanxue.com/upload/attach/202403/979679_JH9JUFK33JZA5ZA.jpg)
然后就可以使用模板一把梭了

#### hook代码

| 123456789101112131415161718 | `function` `hook(){``var` `check_flag = Module.enumerateExports(``"liba0x9.so"``)[0][``"address"``];``console.log(``"Func address = "``,check_flag);``Interceptor.attach(check_flag,{``onEnter:``function` `(args){` `},onLeave:``function` `(retval){``console.log(``"Origin retval : "``,retval);``retval.replace(1337);``}``})``}``function` `main(){``Java.perform(``function` `(){``hook();``})``}``setImmediate(hook);` |
|-|-|

![file](https://bbs.kanxue.com/upload/attach/202403/979679_SU54WWPKETXWTT7.jpg)

## 3、调用native层中未被调用的方法

让我提供一个模板。

| 123 | `var` `native_adr =` `new` `NativePointer(<address_of_the_native_function>);``const native_function =` `new` `NativeFunction(native_adr,` `'<return type>'``, [``'argument_data_type'``]);``native_function(<arguments>);` |
|-|-|

让我逐行解释。

| 1 | `var` `native_adr =` `new` `NativePointer(<address_of_the_native_function>);` |
|-|-|

要在 Frida 中调用一个本地函数，我们需要一个 `NativePointer` 对象。我们应该将要调用的本地函数的地址传递给 `NativePointer` 构造函数。接下来，我们将创建 `NativeFunction` 对象，它表示我们想要调用的实际本地函数。它在本地函数周围创建一个 JavaScript 包装器，允许我们从 Frida 调用该本地函数。

| 1 | `const native_function =` `new` `NativeFunction(native_adr,` `'<return type>'``, [``'argument_data_type'``]);` |
|-|-|

第一个参数应该是 `NativePointer` 对象，第二个参数是本地函数的返回类型，第三个参数是要传递给本地函数的参数的数据类型列表。现在我们可以像在 Java 空间中那样调用该方法了。

| 1 | `native_function(<arguments>);` |
|-|-|

好的，我们明白了。让我们来看看例题。

### 例题Frida-labs 0xA

#### MainActivity

![file](https://bbs.kanxue.com/upload/attach/202403/979679_5RUYY7RXQTT68U4.jpg)
发现就是在主函数中加载了stringFromJNI

#### native

![file](https://bbs.kanxue.com/upload/attach/202403/979679_TB36MTWACDWB86E.jpg)
没有关于flag的信息，但是有未被调用的flag函数，我们直接使用hook调用它输出log
![file](https://bbs.kanxue.com/upload/attach/202403/979679_QPVUWYSEUUAPMWD.jpg)

#### hook代码

| 1234567891011121314151617181920212223242526272829 | `function` `hook(){``var` `a = Module.findBaseAddress(``"libfrida0xa.so"``);``var` `b = Module.enumerateExports(``"libfrida0xa.so"``);``var` `get_flagaddress =` `null``;``var` `mvaddress =` `null``;``for``(``var` `i = 0 ; b[i]!=` `null` `; i ++ ){``// console.log(b[i]["name"])``if``(b[i][``"name"``] ==` `"_Z8get_flagii"``){``console.log(``"function get_flag : "``,b[i][``"address"``]);``console.log((b[i][``"address"``] - a).toString(16));``//       mvaddress = b[i]["address"] - a;``get_flagaddress = b[i][``"address"``];``}``}``console.log(ptr.toString(16));` `var` `get_flag_ptr =` `new` `NativePointer(get_flagaddress);``const get_flag =` `new` `NativeFunction(get_flag_ptr,``'char'``,[``'int'``,``'int'``]);``var` `flag = get_flag(1,2);``console.log(flag)``//console.log(b);``}` `function` `main(){``Java.perform(``function` `(){``hook();``})``}``setImmediate(main)` |
|-|-|

![file](https://bbs.kanxue.com/upload/attach/202403/979679_PWAF44KUQZEUY9K.jpg)

## 4、更改Native层方法的汇编指令

首先我们先看来自x86指令集的frida使用模板

| 12345678910 | `var` `writer =` `new` `X86Writer(opcodeaddr);``Memory.protect(opcodeaddr, 0x1000,` `"rwx"``);``try` `{` `writer.flush();` `} finally {` `writer.dispose();``}` |
|-|-|

**`X86Writer`的实例化：**

- `var writer = new X86Writer(<指令的地址>);`
- 这将创建一个`X86Writer`类的实例，并指定我们要修改的指令的地址。这设置了写入器以操作指定的内存位置。

**插入指令 **

- `try { /* 在此处插入指令 */ }`
- 在`try`块内，我们可以插入要修改/添加的x86指令。`X86Writer`实例提供了各种方法来插入各种x86指令。我们可以查阅文档以了解详情。

**刷新更改：**

- `writer.flush();`
- 插入指令后，调用`flush`方法将更改应用到内存中。这确保修改后的指令被写入内存位置。

**清理：**

- `finally { /* 释放X86Writer以释放资源 */ writer.dispose(); }`
- `finally`块用于确保`X86Writer`资源得到适当清理。调用`dispose`方法释放与`X86Writer`实例关联的资源。

**解除段只读权限**
`Memory.protect` 。我们可以使用这个函数来修改内存区域的保护属性。`Memory.protect` 函数的语法如下：

| 1 | `Memory.protect(地址, 大小, 保护属性);` |
|-|-|

- `地址`：要更改保护的内存区域的起始地址。
- `大小`：内存区域的大小，以字节为单位。
- `保护属性`：内存区域的保护属性。

那么如何使用进行覆写呢
对于x86系统而言我们首先需要查看官方文档中的使用方法
<https://frida.re/docs/javascript-api/#x86writer>

![file](https://bbs.kanxue.com/upload/attach/202403/979679_TNMKTACGGURKN98.jpg)
对与arm64系统而言，我们使用如下api
<https://frida.re/docs/javascript-api/#arm64writer>

![file](https://bbs.kanxue.com/upload/attach/202403/979679_S3PF4D68H3739VJ.jpg)
接下来让我用一个用例程序来讲一下这个指令的用法，我们示范的内容为arm64架构

### 例题Frida-labs 0xB

#### MainActivity

首先我们看到MainActivity函数内容
![file](https://bbs.kanxue.com/upload/attach/202403/979679_U7CAKDKWMUP47N9.jpg)
发现MainActivity就是在用户点击按钮后调用了getflag方法，但是正常点击getflag方法并不会返回flag值。

#### Native层内容

![file](https://bbs.kanxue.com/upload/attach/202403/979679_P2HKZNEMUW8ZWFZ.jpg)
惊讶的发现MainActivity中什么都没有，显然这是不存在的。接下来我们到控制流窗口中查看。
![file](https://bbs.kanxue.com/upload/attach/202403/979679_UNCEPTUBWVVGVW9.jpg)
查看控制流发现程序出现了永假条件跳转。导致导致ida识别不到输出flag的功能。那么我们可以把这个B.NE给Nop掉即可
首先我们需要计算B.NE的偏移地址
![file](https://bbs.kanxue.com/upload/attach/202403/979679_S5XNR4C4HA7X7NF.jpg)
可以发现就是基地址增加15248，然后我们覆写为Nop就可以了

#### Hook代码

| 12345678910111213141516171819202122 | `function` `hook(){``var` `Base =  Module.getBaseAddress(``"libfrida0xb.so"``);``console.log(``"Base address : "``,Base);``var` `BNE = Base.add(0x15248);``Memory.protect(Base,0x1000,``"rwx"``);``var` `writer =` `new` `Arm64Writer(BNE);``try``{``writer.putNop();``writer.flush();``console.log(``"Success!!"``);``}finally {``writer.dispose();``}``}` `function` `main(){``Java.perform(``function` `(){``hook();``})``}` `setTimeout(main,1000);` |
|-|-|

![file](https://bbs.kanxue.com/upload/attach/202403/979679_ZA3NWJCEBUK5DRY.jpg)

---

# 回复

## 回复 by 秋狝 (#2)

*2024-3-8 11:17*

感谢分享

## 回复 by 浮虚千年 (#3)

*2024-4-25 00:54*

写的真多啊![image](https://bbs.kanxue.com/view/img/face/8.gif)

## 回复 by qig (#4)

*2024-5-17 18:50*

刚开始学这个工具的我，跟完了全部题目，感觉这些题目难度刚刚好，可以快速熟悉API,不过有一些写法在最新Frida版本编译不了,提示找不到方法.比如Module.enumerateImports("libfrida0x8.so")，readUtf8String方法等等. 不知道是不是Frida版本不同的原因.  还有从0xA题目开始，Android9里面运行不了apk,一运行就崩溃. 换到了Android13做. native的题目，我发现可以直接hook 那个 native api,不用管so文件，直接就能hook出来.

## 回复 by Shangwendada (#5)

*2024-5-27 09:41*

>
> [qig](https://bbs.kanxue.com/user-416209.htm)
>
>  刚开始学这个工具的我，跟完了全部题目，感觉这些题目难度刚刚好，可以快速熟悉API,不过有一些写法在最新Frida版本编译不了,提示找不到方法.比如Module.enumerateImports(&qu ...
>
>

尽量避免模拟器

## 回复 by F1nGY3 (#6)

*2024-6-4 16:32*

>
> [Shangwendada](https://bbs.kanxue.com/user-979679.htm)
>
>  尽量避免模拟器
>
>

我用的实机，frida14.1.18版本的，这些函数也用不了![image](https://bbs.kanxue.com/view/img/face/5.gif)

## 回复 by Shangwendada (#7)

*2024-6-5 10:18*

>
> [F1nGY3](https://bbs.kanxue.com/user-997909.htm)
>
>  我用的实机，frida14.1.18版本的，这些函数也用不了[em_5]
>
>

现在都到16.2.5啦怎么还在用14

## 回复 by 北袅 (#8)

*2024-6-27 22:32*

大佬例题可以分享一下吗

## 回复 by mb_lqssbocc (#9)

*2024-6-30 09:29*

感谢大佬分享

## 回复 by Shangwendada (#10)

*2024-7-3 00:58*

>
> [北袅](https://bbs.kanxue.com/user-951483.htm)
>
>  大佬例题可以分享一下吗
>
>
>

上一篇帖子给出了

## 回复 by passself (#11)

*2024-7-11 15:06*

0x8这个，不知道为啥我替换了返回值，还是没有出flag
var input = ""
   Interceptor.attach(targetAddress,{
        onEnter:function(args){
            //console.log("args ");
            input = Memory.readUtf8String(args[0]);
            //console.log(Memory.readUtf8String(args[0]));
            if(input.includes("111")){
                console.log("---"+Memory.readUtf8String(args[0]));
                console.log("---"+Memory.readUtf8String(args[1]));
            }
        },onLeave:function(retval){
            if(input.includes("111")){
                console.log("retval is:"+retval);
                //retval = 1;

                retval.replace(1)
                console.log("after retval is:"+retval);
            }
            //retval = 1;
        }
   })
}

## 回复 by Shangwendada (#12)

*2024-7-12 18:44*

>
> [passself](https://bbs.kanxue.com/user-858989.htm)
>
>  0x8这个，不知道为啥我替换了返回值，还是没有出flag
> var input = ""
>  Interceptor.attach(targetAddress,{
>  ...
>
>

在logcat中查看

## 回复 by 北袅 (#13)

*2024-11-10 13:47*

佬你IDApro啥版本

## 回复 by Shangwendada (#14)

*2024-11-10 18:43*

>
> [北袅](https://bbs.kanxue.com/user-951483.htm)
>
>  佬你IDApro啥版本
>
>

7.7
