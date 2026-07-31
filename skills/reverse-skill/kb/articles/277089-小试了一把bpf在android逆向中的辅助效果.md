---
title: '[原创]小试了一把bpf在android逆向中的辅助效果'
url: https://bbs.kanxue.com/thread-277089.htm
tid: 277089
author: lxcoder
date: '2023-05-04'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:48:48+08:00'
replies: 6
---

### 起因

其实，这是一篇水文，没什么技术含量，都是些基础东西。样本是某比较流行的app，之前听说它有frida检测，正好有空就搂出来看看了。

### 初试(完结)

frida检测常规的手段一般都是

| 123456 | `1.frida_server``名字检测``2.``端口号检测``3.D``-``Bus检测``4.maps``检测``5.``线程检测``6.``内存特征检测` |
|-|-|

而1、2、3都有个特征，那就是在frida_server运行的时候才存在，不论是否附加进程，因为这个app是在附加时退出，所以直接就排除了这几个。
然后就从所有检测的共同点入手了，所有检测的共同点就是字符串检测，而字符串匹配最常见的就是strstr函数
 ![image](https://bbs.kanxue.com/upload/attach/202305/719948_WH9NNJWQPQUEE5T.png)
然后就hook掉修改返回值，之后就尴尬了。。。
 ![image](https://bbs.kanxue.com/upload/attach/202305/719948_9MC98GBEJRZ5FUN.png)
当然还有一些其它的检测，比如里面还对.dex进行了比较，不过目的是处理frida挂不上去的问题，所以就没有细看比较这东西是干嘛的，盲猜可能是检测dex注入的。
上面的几个检测点直接用frida进行hook就行了

| 123456789101112131415161718192021222324 | `var ph` `=` `Module.findExportByName(null,` `"strstr"``);``Interceptor.attach(ptr(ph), {``onEnter: function (args) {``this.filename` `=` `args[``0``]``this.checkname` `=` `args[``1``]``/``/` `console.log(this.filename.readCString(), ptr(args[``1``]).readCString())``}, onLeave: function (retval) {` `var s` `=` `ptr(this.filename).readCString()``if` `(s.indexOf(``"gmain"``) >``=` `0``){``console.log(``"gmain anti."``)``retval.replace(``0``)``}``else` `if``(s.indexOf(``"gum-js-loop"``) >``=` `0``){``console.log(``"gum-js-loop anti."``)``retval.replace(``0``)``}``else` `if``(s.indexOf(``"linjector"``) >``=` `0``){``console.log(``"linjector anti."``)``retval.replace(``0``)``}``else` `if``(s.indexOf(``"/data/local/tmp"``) >``=` `0``){``console.log(``"/data/local/tmp anti."``)``retval.replace(``0``)``}``}``})` |
|-|-|

### 定位检测代码位置

定位检测代码的位置还是简单的采用了打印栈的方式

| 1 | `console.log(Thread.backtrace(this.context, Backtracer.FUZZY).``map``(DebugSymbol.fromAddress).join(``"\n"``));` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202305/719948_5XHCD9DGUG69HHK.png)
结合maps文件就直接定位到libmsaoaidsec.so里面的0x1AEE4方法了，里面一堆的字符串解密函数不用管
 ![image](https://bbs.kanxue.com/upload/attach/202305/719948_HRNSWEKFYKE8GVE.png)
想看每一个代码段都是什么字符串的话可以跑一下脚本自解密即可，或者直接动态打印，不过这里没有必要。
排除这些解密字符串的代码直接找到里面的函数调用的地方：
 ![image](https://bbs.kanxue.com/upload/attach/202305/719948_2FCCAVXM3JJARH4.png)
字符串解密后死循环每隔4秒检测一次，初略看了一下，大概是这么个情况，因为没有验证所以仅供参考

| 1234 | `sub_1A940 线程名检测``sub_1AAEC 通过``/``proc``/``self``/``fd文件的实际路径检测是否存在匹配的文件``sub_1AC00 maps检测``sub_23804 xxx内容有点大，需要具体分析` |
|-|-|

sub_23804初看貌似是对libart的某些函数的hook检测，有兴趣的可以分析看看，代码不适合直接stalker进行处理，因为里面像这种指令会导致死循环需要特殊处理，在系统的库代码里面这种原子指令到处都是
 ![image](https://bbs.kanxue.com/upload/attach/202305/719948_29RCT7ENBKAXRGD.png)
再则，里面好像用到了这个玩意

| 123456789101112131415161718 | `v2` `=` `dlopen(``"libart.so"``,` `0``);``if` `( !v2 )``goto LABEL_23;``v3` `=` `v2;` `...` `off_47728[``0``]` `=` `(``int` `*``)dlsym(v3, (const char` `*``)&v38);``dlclose(v3);``goto LABEL_23;` `...` `LABEL_23:``v0` `=` `off_47728[``0``];``if` `( off_47728[``0``] )``return` `(unsigned` `int``)``*``v0 >>` `1` `=``=` `0x2C000028``;``return` `0LL``;` |
|-|-|

参考
 ![image](https://bbs.kanxue.com/upload/attach/202305/719948_82DQGQ8P4TY4S7W.png)

### 尝试bpf定位

接下来假设前面的检测手段都被修正了，那么前面的都得失效，比如：

| 123 | `strstr函数自定义``相应的方法采用svc的方式调用``...` |
|-|-|

这时候使用bpf检直就是降维打击，主要用到了bcc里面的opensnoop及trace.py脚本

| 12 | `python3 opensnoop` `-``u` `10094``python3 trace.py` `-``-``uid` `10094` `'do_sys_openat2 "%s", arg2@user'` `-``U` `-``-``address` `-``v` `-``f maps` |
|-|-|

opensnoop观察访问的文件日志 ，trace查看堆栈
比如，这里是对这个app进行进行文件追踪的日志
 ![image](https://bbs.kanxue.com/upload/attach/202305/719948_R83MF9AE2JHGU37.png)
你会频繁的看到这类日志，而循环读取这类文件的，那最有可能就是检测点了
既然找到了切入点，那自然是通过trace的栈信息来定位了，trace的用户栈信息有几个问题，一个是栈信息不全，其次就是总是显示unknow的问题，这个有兴趣研究的可以参考大佬的文章 https://bbs.kanxue.com/thread-274546.htm
而我采用的是最笨最简单的一种方式，就是直接解析maps，将文件偏移与文件名关联起来直接替换trace脚本中的相关内容就行了，虽然没有解决特殊情况下栈不全的问题，但也勉强能用了，毕竟我的要求不高

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111 | `# 定义``class` `MapsItem:``def` `__init__(``self``, startAddr, endAddr, fOffset, path):``self``.startAddr` `=` `int``(startAddr,` `16``)``self``.endAddr` `=` `int``(endAddr,` `16``)``self``.fileOffset` `=` `int``(fOffset,` `16``)``self``.path` `=` `path` `def` `update(``self``, startAddr``=``None``, endAddr``=``None``, path``=``None``):``if` `startAddr` `is` `not` `None``:``self``.startAddr` `=` `startAddr``if` `endAddr` `is` `not` `None``:``self``.endAddr` `=` `endAddr``if` `path` `is` `not` `None``:``self``.path` `=` `path` `def` `__str__(``self``):``return` `"MapsItem{%s-%s %s %s}"` `%` `(``hex``(``self``.startAddr),` `hex``(``self``.endAddr),` `hex``(``self``.fileOffset),` `self``.path)` `class` `PidItem(``object``):``pid` `=` `0``lst_segments` `=` `[]` `# MapsItem` `def` `__init__(``self``, pid):``self``.pid` `=` `pid` `def` `printLst(``self``):``for` `item` `in` `self``.lst_segments:``print``(``"%s"` `%` `(item))` `class` `KKStackCache:``pidmap` `=` `{}` `def` `__init__(``self``, pid):``if` `pid` `in` `KKStackCache.pidmap:``pass``else``:``KKStackCache.parserMaps(pid)` `@staticmethod``def` `parserMaps(pid):``try``:``fname` `=` `"/proc/%d/maps"` `%` `(pid)``# fname = "maps"``# print("open %s" % fname)``f` `=` `open``(fname)``pattern` `=` `re.``compile``(r``'([\w]+)-([\w]+)\s+([\w\-]+)\s+([\w\-]+)\s+([\w\:]+)\s+([\d]+)\s+(\S+(?:\s+\S+)*?)*\s*$'``)` `KKStackCache.pidmap[pid]` `=` `PidItem(pid)` `mapsdata` `=` `[]``lines` `=` `f.readlines()``for` `line` `in` `lines:``match` `=` `re.match(pattern, line)``if` `match:``mapsItem` `=` `MapsItem(match.group(``1``), match.group(``2``), match.group(``4``), match.group(``7``))``mapsdata.append(mapsItem)` `else``:``print``(``"No match:"` `+` `line)` `KKStackCache.pidmap[pid].lst_segments` `=` `sorted``(mapsdata, key``=``lambda` `x: x.startAddr)` `f.close()``except``:``pass` `print``(``"parser %d over."` `%` `pid)` `@staticmethod``def` `addrInfo(pid, addr):``pidmap` `=` `KKStackCache.pidmap.get(pid)``if` `pidmap` `is` `not` `None``:``lst` `=` `pidmap.lst_segments` `bg` `=` `0``;``end` `=` `len``(lst)` `-` `1` `while` `bg <``=` `end:``mid` `=` `int``((bg` `+` `end` `+` `1``)` `/` `2``)``# print("mid %d: %s %s, addr:%s" % (mid, hex(lst[mid].startAddr), hex(lst[mid].endAddr), hex(addr)))``if` `addr < lst[mid].startAddr:``end` `=` `mid` `-` `1``elif` `addr >``=` `lst[mid].endAddr:``bg` `=` `mid` `+` `1``else``:``itm` `=` `lst[mid]``path` `=` `itm.path``offset` `=` `itm.fileOffset` `+` `(addr` `-` `itm.startAddr)``return` `True``, addr, offset, path``return` `False``,` `None``,` `None``,` `None` `@staticmethod``def` `printLst(pid):``pidmap` `=` `KKStackCache.pidmap.get(pid)``if` `pidmap` `is` `not` `None``:``pidmap.printLst()``# 使用``# 给_stack_to_string函数增加一个pid参数 def _stack_to_string(self, bpf, stack_id, tgid, pid):``# 在处理栈信息的地方加上下面的代码``if` `pid >` `0``:``name, offset, module` `=` `BPF._sym_cache(tgid).resolve(addr,` `False``)``if` `name` `is` `None``:``KKStackCache(pid)``isExist, baseAddr, offset, path` `=` `KKStackCache.addrInfo(pid, addr)``if` `not` `isExist:``KKStackCache.parserMaps(pid)``isExist, baseAddr, offset, path` `=` `KKStackCache.addrInfo(pid, addr)``if` `isExist:``if` `path` `is` `not` `None``:``symstr` `=` `"%s %s"` `%` `(``hex``(offset), path)` |
|-|-|

效果如下：
 ![image](https://bbs.kanxue.com/upload/attach/202305/719948_R48SGZZ47XN259C.png)
然后定位的0x1ac50是哪呢，正好是我们前面分析的0x1AC00函数内部，结合我们前面看过的逻辑，不难看出来这栈信息是不全的，不过其实也无所位了，定位到了一个点，其它的也就不远了，比如就像我们之前的操作，直接hook打印堆栈信息等，或者按大佬的方式去处理也可以。
至于那个libtiny.so的栈信息，我就打开简单看了下：
 ![image](https://bbs.kanxue.com/upload/attach/202305/719948_X2DM4Y3JBQFD7EA.png)
上下翻了翻，能大致看到有读取maps并手动解析的操作，其它略过~（ps:因为不调试细节看不懂，还有就是懒！）

 然后试了一下通过bpf修改open函数的返回值，基于opensnoop.py做的尝试性修改

| 1234 | `/``/``在trace_return里面增加代码``if``(my_strnstr((const char``*``)data.name,` `"maps"``,` `256``,` `5``) !``=` `NULL){``bpf_override_return(ctx,` `-``1``);``}` |
|-|-|

其中my_strnstr是自定义实现的strstr函数，因为标准的strstr函数貌似会因为循环问题而过不了验证，所以实现了一个有限循环的strstr，再则，使用bpf_override_return需要内核开启CONFIG_BPF_KPROBE_OVERRIDE选项
开启和关闭效果如下：
 ![image](https://bbs.kanxue.com/upload/attach/202305/719948_WDR9Q2UH856TNT2.png)

### ps

bpf很好很强大，强大到颠覆性的改变，可以类比frida对安全行业的影响，而且是完全是高维打击，目前已经发现有很多大佬在搞这方面的研究了，有兴趣的可以报虫佬的课程系统的学一学，个人觉得很值得学

---

# 回复

## 回复 by 万里星河 (#2)

*2023-5-7 11:11*

支持一下

## 回复 by bluegatar (#3)

*2023-5-9 01:00*

不错，非常有借鉴意义

## 回复 by 司徒废人 (#4)

*2023-5-10 15:47*

然后试了一下通过bpf修改open函数的返回值，基于opensnoop.py做的尝试性修改

| 1 2 3 4 | `/``/``在trace_return里面增加代码` `if``(my_strnstr((const char``*``)data.name,``"maps"``,``256``,``5``) !``=` `NULL){` `bpf_override_return(ctx,``-``1``);` `}` |
|-|-|

上面这部分能再稍微详细的贴下代码吗

## 回复 by lxcoder (#5)

*2023-5-11 05:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  司徒废人](https://bbs.kanxue.com/user-641235.htm)
>
>  然后试了一下通过bpf修改open函数的返回值，基于opensnoop.py做的尝试性修改1234//在trace_return里面增加代码&nbsp;if(my_strnstr((const ...
>
>

这个随便处理都可以，目的只是将原strstr里面的无限循环变成有限循环即可，比如我这里后面两个参数的作用就是对前面两个字符串比较的长度进行了限定

## 回复 by 秋狝 (#6)

*2023-5-11 09:08*

感谢分享

## 回复 by mb_cmrpibxs (#8)

*2024-5-21 16:08*

大佬，能加下qq，请教下技术问题吗
