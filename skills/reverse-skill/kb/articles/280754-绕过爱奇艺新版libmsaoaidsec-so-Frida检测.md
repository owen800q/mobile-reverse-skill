---
title: '[原创]绕过爱奇艺新版libmsaoaidsec.so Frida检测'
url: https://bbs.kanxue.com/thread-280754.htm
tid: 280754
author: yyy123
date: '2024-03-03'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:31:02+08:00'
replies: 71
---

# 1、环境：

手机：Google Pixel 6，Aosp android13
cpu架构：Arm64
Frida：16.1.10
爱奇艺：15.2.5

# 2、问题

这段时间在研究爱奇艺的一些功能，当用Frida调试时发现有反Frida检测，现象是执行`frida -l index.js -U -f com.qiyi.video`时进程重启，下面是对Frida检测的一些分析，并通过hook绕过Frida检测。

# 3、分析

用Frida hook do_dlopen函数看加载哪个so时崩溃的，hook之前先获取do_dlopen在linker64中的相对偏移
 ![image](https://bbs.kanxue.com/upload/attach/202403/956681_M8YT5HFFQYW8P5S.webp)

## hook 脚本如下：

| 1234567891011121314151617 | `function hookDlopen() {``let linker64_base_addr` `=` `Module.getBaseAddress(``'linker64'``)``let offset` `=` `0x3ba00` `/``/` `__dl__Z9do_dlopenPKciPK17android_dlextinfoPKv``let android_dlopen_ext` `=` `linker64_base_addr.add(offset)``Interceptor.attach(android_dlopen_ext, {``onEnter: function(args){``this.name` `=` `args[``0``].readCString()``Log.log(`dlopen onEnter ${this.name}`)``}, onLeave: function(retval){``Log.log(`dlopen onLeave name: ${this.name}`)``if` `(this.name !``=` `null && this.name.indexOf(``'libmsaoaidsec.so'``) >``=` `0``) {``let JNI_OnLoad` `=` `Module.getExportByName(this.name,` `'JNI_OnLoad'``)``Log.log(`dlopen onLeave JNI_OnLoad: ${JNI_OnLoad}`)``}``}``})``}` |
|-|-|

## 执行`frida -l index.js -U -f com.qiyi.video`

 ![image](https://bbs.kanxue.com/upload/attach/202403/956681_6FZRKEWB3SK9J5X.webp)
从结果可以看出加载的最后一个so是：libmsaoaidsec.so，并且没有调用onLeave，由此可断定崩溃点在libmsaoaidsec.so中，并且在JNI_OnLoad之前检测的，检测点应该是在init_array初始化函数中。
<br/>
既然挂上Frida后进程就退出，那么我们就来分析是调用哪个系统调用退出的，可以通过strace查看系统调用，但在执行strace时需要在dlopen加载libmsaoaidsec.so之前让线程sleep 10秒，以便留出strace执行时机。

| 123456789101112131415161718 | `function hookDlopen() {``/``/` `获取libc中的sleep函数``let sleep: Function` `=` `new NativeFunction(Module.getExportByName(``'libc.so'``,` `'sleep'``),` `'uint'``, [``'uint'``])``let linker64_base_addr` `=` `Module.getBaseAddress(``'linker64'``)``let offset` `=` `0x3ba00` `/``/` `__dl__Z9do_dlopenPKciPK17android_dlextinfoPKv``let android_dlopen_ext` `=` `linker64_base_addr.add(offset)``Interceptor.attach(android_dlopen_ext, {``onEnter: function(args){``this.name` `=` `args[``0``].readCString()``Log.log(`dlopen onEnter ${this.name}`)``if` `(this.name !``=` `null && this.name.indexOf(``'libmsaoaidsec.so'``) >``=` `0``) {``sleep(``10``)` `/``/` `sleep10秒留出strace执行时机``}``}, onLeave: function(retval){``Log.log(`dlopen onLeave name: ${this.name}`)``}``})``}` |
|-|-|

## 下面重新执行`frida -l index.js -U -f com.qiyi.video`

 ![image](https://bbs.kanxue.com/upload/attach/202403/956681_327JNERN9DYECMW.webp)

## 然后得到pid立即执行strace -e trace=process -i -f -p 15534 等待10秒后结果：

 ![image](https://bbs.kanxue.com/upload/attach/202403/956681_TPDWPJV3V6B3CYY.webp)
我们看这一行`[pid 15576] [000000751926c008] exit_group(0 <unfinished ...>`，显示15576线程是在0x751926c008地址处调用exit_group退出的，通过proc/15534/maps查看libc.so的地址范围是0x7509b9c000 - 0x7509c70000，很明显0x751926c008不是libc.so的地址，由此可以断定exit_group的代码是动态释放的。
<br/>
动态释放代码一定是要操作内存的，接下来我们用前面相同的逻辑，用strace查看调用了哪些和内存相关的系统调用
<br/>
`strace -e trace=process,memory -i -f -p 25947`
 ![image](https://bbs.kanxue.com/upload/attach/202403/956681_AJDYG9RMXV9257X.webp)
注意这行：[pid 25990] [0000007509c48ab8] mmap(NULL, 28, PROT_READ|PROT_WRITE|PROT_EXEC, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0) = 0x751926c000
<br/>
上面这行mmap申请的内存返回的地址是：0x751926c000，正好匹配后面exit_group前面的地址：000000751926c008
<br/>
由mmap的地址可以看出mmap是libc.so中的函数，于是我们可以hook mmap打印一下调用栈

| 12345678910111213141516171819202122232425262728293031 | `function hook_mmap() {``const mmap` `=` `Module.getExportByName(``"libc.so"``,` `"mmap"``);``Interceptor.attach(mmap, {``onEnter: function (args) {``let length` `=` `args[``1``].toString(``16``)``if` `(parseInt(length,` `16``)` `=``=` `28``) {``Log.log(``'backtrace:\n'` `+` `Thread.backtrace(this.context, Backtracer.ACCURATE)``.``map``(DebugSymbol.fromAddress).join(``'\n'``)` `+` `'\n'``);``}``}``})``}` `function hookDlopen() {``let sleep: Function` `=` `new NativeFunction(Module.getExportByName(``'libc.so'``,` `'sleep'``),` `'uint'``, [``'uint'``])``let linker64_base_addr` `=` `Module.getBaseAddress(``'linker64'``)``let offset` `=` `0x3ba00` `/``/` `__dl__Z9do_dlopenPKciPK17android_dlextinfoPKv``let android_dlopen_ext` `=` `linker64_base_addr.add(offset)``Interceptor.attach(android_dlopen_ext, {``onEnter: function(args){``this.name` `=` `args[``0``].readCString()``Log.log(`dlopen onEnter ${this.name}`)``if` `(this.name !``=` `null && this.name.indexOf(``'libmsaoaidsec.so'``) >``=` `0``) {``/``/` `sleep(``10``)``hook_mmap()``}``}, onLeave: function(retval) {``Log.log(`dlopen onLeave name: ${this.name}`)``}``})``}` |
|-|-|

## 调用栈如下：

 ![image](https://bbs.kanxue.com/upload/attach/202403/956681_VGC94QD3PNWEDYC.webp)

## 下面用IDA打开libmsaoaidsec.so，看0x2358c地址处对应的函数

 ![image](https://bbs.kanxue.com/upload/attach/202403/956681_UVHAUG3SJ5VEEMJ.webp)

## 下面看C语言伪码，的确是在释放代码并且执行：

 ![image](https://bbs.kanxue.com/upload/attach/202403/956681_HEWBB69AM2F9M8H.webp)

## 经过IDA分析0x1bdcc地址对应的函数：`void sub_1B924()`是检测逻辑所在，具体检测逻辑就不在这赘述了，大家有兴趣可以自行研究

 ![image](https://bbs.kanxue.com/upload/attach/202403/956681_S4YX3ED9AVUNGA4.webp)

# 4、解决方案

解决方案就是replace掉这个无返回值的函数 `void sub_1B924()`
<br/>
由于这个检测逻辑在.init_函数中，所以得先找到hook时机，查看Aosp代码发现linker执行init_array类的函数是call_constructors：

| 12345678910111213141516171819202122 | `void soinfo::call_constructors() {``if` `(constructors_called) {``return``;``}``constructors_called` `=` `true;` `if` `(!is_main_executable() && preinit_array_ !``=` `nullptr) {``/``/` `The GNU dynamic linker silently ignores these, but we warn the developer.``PRINT``(``"\"%s\": ignoring %zd-entry DT_PREINIT_ARRAY in shared library!"``,``get_realpath(), preinit_array_count_);``}` `get_children().for_each([] (soinfo``*` `si) {``si``-``>call_constructors();``});` `TRACE(``"\"%s\": calling constructors"``, get_realpath());` `/``/` `DT_INIT should be called before DT_INIT_ARRAY` `if` `both are present.``call_function(``"DT_INIT"``, init_func_);``call_array(``"DT_INIT_ARRAY"``, init_array_, init_array_count_, false);``}` |
|-|-|

所以直接hook call_constructors函数，在onEnter中replace掉sub_1b924
<br/>
查看call_constructors在linker64中的偏移
 ![image](https://bbs.kanxue.com/upload/attach/202403/956681_USE5ZNV8TMW8T5J.webp)

# 5、最终代码

| 12345678910111213141516171819202122232425262728293031323334353637383940414243 | `function hookDlopen() {``let linker64_base_addr` `=` `Module.getBaseAddress(``'linker64'``)``let offset` `=` `0x3ba00` `/``/` `__dl__Z9do_dlopenPKciPK17android_dlextinfoPKv``let android_dlopen_ext` `=` `linker64_base_addr.add(offset)``if` `(android_dlopen_ext !``=` `null) {``Interceptor.attach(android_dlopen_ext, {``onEnter: function(args){``this.name` `=` `args[``0``].readCString()``if` `(this.name !``=` `null && this.name.indexOf(``'libmsaoaidsec.so'``) >``=` `0``) {``hook_linker_call_constructors()``}``}, onLeave: function(retval){``Log.log(`dlopen onLeave name: ${this.name}`)``if` `(this.name !``=` `null && this.name.indexOf(``'libmsaoaidsec.so'``) >``=` `0``) {``let JNI_OnLoad` `=` `Module.getExportByName(this.name,` `'JNI_OnLoad'``)``Log.log(`dlopen onLeave JNI_OnLoad: ${JNI_OnLoad}`)``}``}``})``}``}` `function hook_linker_call_constructors() {``let linker64_base_addr` `=` `Module.getBaseAddress(``'linker64'``)``let offset` `=` `0x521f0` `/``/` `__dl__ZN6soinfo17call_constructorsEv``let call_constructors` `=` `linker64_base_addr.add(offset)``let listener` `=` `Interceptor.attach(call_constructors, {``onEnter: function (args) {``Log.log(``'hook_linker_call_constructors onEnter'``)``let secmodule` `=` `Process.findModuleByName(``"libmsaoaidsec.so"``)``if` `(secmodule !``=` `null) {``hook_sub_1b924(secmodule)``listener.detach()``}``}``})``}` `function hook_sub_1b924(secmodule) {``Interceptor.replace(secmodule.base.add(``0x1b924``), new NativeCallback(function () {``Log.log(`hook_sub_1b924 >>>>>>>>>>>>>>>>> replace`)``},` `'void'``, []));``}` |
|-|-|

上传的附件：
- strace_android10

（786.68kb，153次下载）
- strace_android12

（794.04kb，110次下载）
- strace_android13

（801.84kb，137次下载）
- strace_android14

（822.27kb，122次下载）
- libmsaoaidsec.so

（676.00kb，120次下载）

---

# 回复

## 回复 by 秋狝 (#2)

*2024-3-3 23:00*

感谢分享

## 回复 by 苦瓜tim (#3)

*2024-3-4 09:46*

牛逼

## 回复 by shinratensei (#4)

*2024-3-4 09:54*

tql

## 回复 by 你瞒我瞒 (#5)

*2024-3-4 10:06*

大佬能附带个样本，去下载一个同版本的app，里面是arm版本so，在ida中搜索函数1b924没有的

## 回复 by 你瞒我瞒 (#6)

*2024-3-4 10:13*

疑问1【显示15576线程是在0x751926c008地址处调用exit_group退出的，通过proc/15534/maps查看libc.so的地址范围是0x7509b9c000 - 0x7509c70000，很明显0x751926c008不是libc.so的地址，由此可以断定exit_group的代码是动态释放的】

这个查看libc.so的地址范围的时机是什么时候呢，如果注入frida后app重启了，这个地址会变化？如果变化了这个时候exit的那个地址范围就和重启后的libc.so地址对不上了吧。这个查libc.so的地址是在sleep的时候做的吗？

strace是自己编译的，还是可以在网上下到呢，在Android12上面没有这个工具。

## 回复 by fishod (#7)

*2024-3-4 10:23*

感谢分享精彩文章，附加是64位so

上传的附件：
- libmsaoaidsec.so

（676.00kb，47次下载）

## 回复 by koflfy (#8)

*2024-3-4 11:22*

mark

## 回复 by yyy123 (#9)

*2024-3-4 11:34*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  大佬能附带个样本，去下载一个同版本的app，里面是arm版本so，在ida中搜索函数1b924没有的
>
>

要64位的，应用宝下载即可

## 回复 by yyy123 (#10)

*2024-3-4 11:40*

1、是调用的sleep获取maps文件，另外linux的fork机制原因，libc.so映射地址一般都和zygote进程一样

2、通过Aoso编译的镜像是自带strace的

稍等我在文章后面附加指定版本的strace

## 回复 by yyy123 (#11)

*2024-3-4 11:41*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  疑问1【显示15576线程是在0x751926c008地址处调用exit_group退出的，通过proc/15534/maps查看libc.so的地址范围是0x7509b9c000 - 0x7509c ...
>
>

1、是调用的sleep获取maps文件，另外linux的fork机制原因，libc.so映射地址一般都和zygote进程一样

2、通过Aoso编译的镜像是自带strace的

稍等我在文章后面附加指定版本的strace

## 回复 by 你瞒我瞒 (#12)

*2024-3-4 14:13*

>
> [yyy123](https://bbs.kanxue.com/user-956681.htm)
>
>  1、是调用的sleep获取maps文件，另外linux的fork机制原因，libc.so映射地址一般都和zygote进程一样
>
> 2、通过Aoso编译的镜像是自带strace的
>
> 稍等我在文章 ...
>
>

感谢![image](https://bbs.kanxue.com/view/img/face/75.gif)

## 回复 by 青眼白龙 (#13)

*2024-3-4 19:24*

![image](https://bbs.kanxue.com/view/img/face/63.gif)学习一下

## 回复 by anenn (#14)

*2024-3-5 11:29*

学习了![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by neo10 (#15)

*2024-3-5 14:12*

学习了![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by linkin5epk (#16)

*2024-3-6 11:58*

复现不了...下载的爱奇艺版本也会Process terminated,但是没有没有到libmsaoaidsec.so 这个文件...

## 回复 by yyy123 (#17)

*2024-3-6 14:07*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  linkin5epk](https://bbs.kanxue.com/user-984485.htm)
>
>  复现不了...下载的爱奇艺版本也会Process terminated,但是没有没有到libmsaoaidsec.so 这个文件...
>
>

版本一致吗？我在应用宝下载的

## 回复 by linkin5epk (#18)

*2024-3-6 19:54*

>
> [yyy123](https://bbs.kanxue.com/user-956681.htm)
>
>  版本一致吗？我在应用宝下载的
>
>

有可能是因为我使用的是模拟器，我没试过真机，我换真机试试![image](https://bbs.kanxue.com/view/img/face/51.gif)

## 回复 by yyy123 (#19)

*2024-3-6 19:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  linkin5epk](https://bbs.kanxue.com/user-984485.htm)
>
>  有可能是因为我使用的是模拟器，我没试过真机，我换真机试试[em_51]
>
>

现在有点规模的app都有反作弊检测的，首先检测的就是模拟器

## 回复 by axyzyz (#20)

*2024-3-6 22:38*

66666

## 回复 by linkin5epk (#21)

*2024-3-7 00:09*

>
> [yyy123](https://bbs.kanxue.com/user-956681.htm)
>
>  现在有点规模的app都有反作弊检测的，首先检测的就是模拟器
>
>

谢嘞大哥，换真机成功嘞![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by jueqingqiai (#22)

*2024-3-7 16:36*

学习了，谢谢分享

## 回复 by jueqingqiai (#23)

*2024-3-7 21:52*

Log 如何打印的  id 和 ThreadId？

## 回复 by linkin5epk (#24)

*2024-3-8 00:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  jueqingqiai](https://bbs.kanxue.com/user-735199.htm)
>
>  Log 如何打印的 id 和 ThreadId？
>
>
>

同问

## 回复 by linkin5epk (#25)

*2024-3-8 01:01*

我们看这一行[pid 15576] [000000751926c008] exit_group(0 <unfinished ...>，显示15576线程是在0x751926c008地址处调用exit_group退出的，通过proc/15534/maps查看libc.so的地址范围是0x7509b9c000 - 0x7509c70000，很明显0x751926c008不是libc.so的地址，由此可以断定exit_group的代码是动态释放的。

我太菜了,能请问一下这个动态释放是什么意思?(我可以认为是在exit前会执行动态释放内存的操作吗?)

上面这行mmap申请的内存返回的地址是：0x751926c000，正好匹配后面exit_group前面的地址：000000751926c008(这段话有什么含义么?不是很理解...这和上面的动态释放连着的吗?)
![image](https://bbs.kanxue.com/view/img/face/47.gif)

## 回复 by koflfy (#26)

*2024-3-8 10:28*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  linkin5epk](https://bbs.kanxue.com/user-984485.htm)
>
>  我们看这一行[pid 15576] [000000751926c008] exit_group(0 ，显示15576线程是在0x751926c008地址处调用exit_group退出的，通过proc/ ...
>
>

他的意思是exit退出这个函数并不在libc.so的地址范围内，说明这个exit的代码很可能是动态申请的，所以才会关注后面的mmap动态申请内存的函数，而这个mmap申请的返回值基址是0x751926c000，正好0x751926c008在这里面，说明exit退出这个函数代码就是在这段动态申请的地址里。

## 回复 by yyy123 (#27)

*2024-3-8 12:57*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  linkin5epk](https://bbs.kanxue.com/user-984485.htm)
>
>  我们看这一行[pid 15576] [000000751926c008] exit_group(0 ，显示15576线程是在0x751926c008地址处调用exit_group退出的，通过proc/ ...
>
>

动态释放代码：通过mmap申请内存，把exit_group系统调用的汇编指令写到这段内存中，然后执行。此时如果用strace查看exit_group系统调用的地址就在前面mmap申请内存的空间范围里。

## 回复 by yyy123 (#28)

*2024-3-8 12:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  jueqingqiai](https://bbs.kanxue.com/user-735199.htm)
>
>  Log 如何打印的 id 和 ThreadId？
>
>
>

  static log(msg: string) {
      let pid = Process.id
      let tid = Process.getCurrentThreadId()
      msg = pid + '-' + tid + ' ' + msg
      console.log(`${msg}`)
    }
  }

## 回复 by linkin5epk (#29)

*2024-3-8 14:43*

>
> [yyy123](https://bbs.kanxue.com/user-956681.htm)
>
>  动态释放代码：通过mmap申请内存，把exit_group系统调用的汇编指令写到这段内存中，然后执行。此时如果用strace查看exit_group系统调用的地址就在前面mmap申请内存的空间范围里。
>
>

大佬太强啦![image](https://bbs.kanxue.com/view/img/face/51.gif)懂了懂了...我一开始理解成动态释放内存了....现在我的理解是系统调用的汇编代码是动态释放执行的吧...所以安卓系统调用只能通过libc库实现?或者直接执行汇编?exit_group的执行地址不在libc.so中,所以是动态释放的汇编代码来执行?(但是我ida查看libc.so也没有exit_group的导出函数?这是为什么呢?)

## 回复 by linkin5epk (#30)

*2024-3-8 14:56*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  koflfy](https://bbs.kanxue.com/user-111569.htm)
>
>  他的意思是exit退出这个函数并不在libc.so的地址范围内，说明这个exit的代码很可能是动态申请的，所以才会关注后面的mmap动态申请内存的函数，而这个mmap申请的返回值基址是0x751926 ...
>
>

嗯嗯嗯,思路转过来了....我的我的,太辣了我![image](https://bbs.kanxue.com/view/img/face/5.gif)![image](https://bbs.kanxue.com/view/img/face/5.gif)![image](https://bbs.kanxue.com/view/img/face/5.gif)

## 回复 by Damn7Kx (#31)

*2024-3-8 15:53*

我是把这个文件删掉![image](https://bbs.kanxue.com/view/img/face/86.gif)

## 回复 by 曹无咎 (#32)

*2024-3-14 11:12*

牛逼，学习了

## 回复 by AunCss (#33)

*2024-3-14 14:06*

学习了，新的思路

## 回复 by artake (#34)

*2024-3-14 16:00*

请教一下：
[pid 15576] [000000751926c008] exit_group(0 <unfinished ...>  这行前面还有一个exit(0)，怎么忽略了呢？感觉这个exit(0)也很重要啊，exit_group是svc退出吗？strace能够监控svc退出吗？

## 回复 by mb_xsfdfkko (#35)

*2024-3-14 23:19*

用的确实是arm64的包，15.2.5版本，

目前百度手机助手还是没有更新，[爱奇艺 百度手机助手 15.2.5版本，ARM64位的](https://mobile.baidu.com/item?docid=5008384204&f0=search_searchContent%400_appBaseNormal%400&advitem=source%2Bnatural%40pos%2B1%40bid%2B0%40ctr%2B0.000000%40trans%2B%40keyword%2B%E7%88%B1%E5%A5%87%E8%89%BA%40app_rcv%2B)

< hook mmap打印一下调用栈 if(parseInt(length, 16) == 28)  >

为啥我这里这个判断一直进不去呀？进去之后一直获取不到 前线程的回溯 和符号（函数名、类名),并且程序视乎被暂停了

## 回复 by yyy123 (#36)

*2024-3-15 14:51*

>
> [Damn7Kx](https://bbs.kanxue.com/user-869843.htm)
>
>  我是把这个文件删掉[em_86]
>
>

牛逼，这个好使![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by linkin5epk (#37)

*2024-3-15 19:20*

>
> [mb_xsfdfkko](https://bbs.kanxue.com/user-941451.htm)
>
>  用的确实是arm64的包，15.2.5版本，目前百度手机助手还是没有更新，爱奇艺 百度手机助手 15.2.5版本，ARM64位的&lt;&nbsp;hook&nbsp;mmap ...
>
>

确实,我复现的时候也是进不去![image](https://bbs.kanxue.com/view/img/face/5.gif)

## 回复 by nianchu (#38)

*2024-3-23 14:19*

牛逼

## 回复 by gr4v8l. (#39)

*2024-4-4 10:06*

不知道是什么原因，复现失败了，strace中可以观察到同样的mmap 28参数调用，但frida却无法hook到该条28参数的mmap，有哪位大佬能推测下可能是什么原因导致的嘛？![image](https://bbs.kanxue.com/view/img/face/67.gif)

## 回复 by Analysts1981 (#40)

*2024-4-5 19:41*

????????????????????????????

## 回复 by 苦瓜tim (#41)

*2024-4-8 23:41*

大佬，附件的strace如何使用啊，谢谢。

## 回复 by aizhiqun (#42)

*2024-4-10 15:21*

牛逼![image](https://bbs.kanxue.com/view/img/face/63.gif)，感谢大佬分享，我好好学习学习

## 回复 by 青蓝梦 (#43)

*2024-4-11 14:58*

strace 可以跟踪到svc么大佬

## 回复 by zx_994305 (#44)

*2024-4-11 16:25*

666

## 回复 by ymswx (#45)

*2024-4-15 13:08*

好像这个方案被公布后，人家修改了检测逻辑，后边的人又要等新的方案了。函数换成了munmap，应该是版本更新了

## 回复 by WangONC (#46)

*2024-4-15 15:32*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  linkin5epk](https://bbs.kanxue.com/user-984485.htm)
>
>  我们看这一行[pid 15576] [000000751926c008] exit_group(0 ，显示15576线程是在0x751926c008地址处调用exit_group退出的，通过proc/ ...
>
>

代码不是静态的，是通过解密或者什么方式，动态下发释放到内存中，然后执行，你看一下那块代码就知道了，exit__group不是libc调的

下面那个问题，mmap申请了一块内存，exit_group在申请等得那块内存附近执行，说明是先申请内存，后执行代码，把代码释放到了申请的内存中然后执行的

## 回复 by onwyc123 (#47)

*2024-4-27 11:04*

strace -e trace=process,memory -i -f -p 25947

## 回复 by onwyc123 (#48)

*2024-4-27 11:05*

strace -e trace=process,memory -i -f -p 25947
请问这个 pid是从哪来的呢,这个搜索的是什么应用的pid呢?

## 回复 by falconnnn (#49)

*2024-4-27 21:05*

学习了，谢谢分享

## 回复 by 梦_魇 (#50)

*2024-7-4 14:28*

楼主 请教下strace这个工具怎么编译不同安卓版本的啊   我看文章都是编译aarch64的

## 回复 by Jave (#51)

*2024-7-4 15:26*

先赞后读！![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by zkbutt (#52)

*2024-7-16 19:52*

strace -e trace=process -i -f -p 14181  这个是什么工具呀，运行不了

## 回复 by 华达州 (#53)

*2024-7-19 11:10*

佬您好，这块是不是有问题“从结果可以看出加载的最后一个so是：libmsaoaidsec.so，并且没有调用onLeave，由此可断定崩溃点在libmsaoaidsec.so中，并且在JNI_OnLoad之前检测的，检测点应该是在init_array初始化函数中。”
因为既然都没有走到onLeave，那么后面的if判断必然也没有执行，所以没办法根据这个来判断是否是在JNI_OnLoad之前检测的

## 回复 by graywolf (#54)

*2024-7-31 17:22*

【由mmap的地址可以看出mmap是libc.so中的函数，于是我们可以hook mmap打印一下调用栈】这里打印调用栈好像有检测，打印不出来，有办法解决吗。

## 回复 by zx_994305 (#55)

*2024-8-7 17:45*

libmsaoaidsec.so 是哪个厂商的加固？ 好多App都在用

## 回复 by 从黎明到衰落 (#56)

*2024-8-10 19:08*

不知道为什么打印不出来调用栈，打印了mmap的长度没有28的![image](https://bbs.kanxue.com/upload/attach/202408/758985_MHGGNZ5HKSGTEZH.webp)

## 回复 by 从黎明到衰落 (#57)

*2024-8-11 23:15*

>
> [从黎明到衰落](https://bbs.kanxue.com/user-758985.htm)
>
>  不知道为什么打印不出来调用栈，打印了mmap的长度没有28的
>
>

将脚本包裹在perform里面，并且加了一行log打印context。
现在栈回溯可以打印出来了。
不过还是不太明白，hook的都是本地层函数。为什么还是要加perform才能把栈回溯打印出来

![image](https://bbs.kanxue.com/upload/attach/202408/758985_GRWD93ZQK7D4KP3.webp)

## 回复 by im菜鸡 (#58)

*2024-8-15 14:31*

想问一下佬，strace不是能只能跟踪系统调用吗，那么mmap这个系统调用你是怎么判断是libc中的mmap发起的呢，有没有可能是malloc函数发起的mmap系统调用？

## 回复 by 一颗小草 (#59)

*2024-8-17 11:54*

尝试了一下最新版本的，不知道是我的机器问题还是其他问题，在Log('backtrace:\n' + Thread.backtrace(this.context, Backtracer.ACCURATE).map(DebugSymbol.fromAddress).join('\n') + '\n');，这一行日志的时候，会让app整个进程卡死，无法打印详细的内存堆栈信息

## 回复 by 乐子人 (#60)

*2024-8-17 12:17*

libmsaoaidsec.so这个是移动安全联盟的sdk，跟爱奇艺没啥关系，很多app都有用的

## 回复 by 一颗小草 (#61)

*2024-8-17 13:49*

>
> [从黎明到衰落](https://bbs.kanxue.com/user-758985.htm)
>
>
>
>
>
>
>
>  从黎明到衰落
>
>
>
>  不知道为什么打印不出来调用栈，打印了mmap的长度没有28的
>
>  将脚本包裹在perform里面，并且加了一行log打 ...
>
>

我也是相同的问题，我是打印回溯就会卡死，我换了一个其他的app，打印mmap的回溯，是正常的，试了你的这个放到Java.perform中后，确实正常打印了

## 回复 by jfztaq (#62)

*2024-8-20 15:29*

大神，能不能加下i国网这个app，怎么过检测的呢

## 回复 by 教教我吧~ (#63)

*2024-10-1 14:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  linkin5epk](https://bbs.kanxue.com/user-984485.htm)
>
>  我们看这一行[pid 15576] [000000751926c008] exit_group(0 ，显示15576线程是在0x751926c008地址处调用exit_group退出的，通过proc/ ...
>
>

意思就是不是libc.so执行的exit程序，而是程序员自己写的代码强制退出程序的，此处就是反调地方

## 回复 by kccp (#64)

*2024-11-9 11:23*

1

## 回复 by 梦幻雪月 (#65)

*2024-12-5 23:31*

strace  下载 过期了  这个还可以在哪里下载

## 回复 by 梦幻雪月 (#66)

*2024-12-6 17:56*

下载凭证已过期，请刷新页面重新尝试下载。  能给一个strace嘛

## 回复 by mb_lyqehpis (#67)

*2024-12-11 16:55*

大佬，15.11.6，为什么跑不了，第一个hook脚本检测frida直接就寄了

## 回复 by 荧光之夏 (#68)

*2025-1-6 12:30*

tql

## 回复 by wx_小友 (#69)

*2025-5-17 22:00*

strace 可以通过termux下载，放到/system/bin/    目录下就可以了。
这帖子NB了，Get到新技能

## 回复 by wx_范迪塞尔 (#70)

*2025-5-19 12:00*

现在都替换了也不行了，不知道哪里下套了

## 回复 by mb_vnpvoszd (#71)

*2025-7-4 15:06*

>
> [wx_范迪塞尔](https://bbs.kanxue.com/user-880532.htm)
>
>  现在都替换了也不行了，不知道哪里下套了
>
>

相同版本也不行么

## 回复 by Himly (#72)

*2026-5-24 15:55*

牛逼
