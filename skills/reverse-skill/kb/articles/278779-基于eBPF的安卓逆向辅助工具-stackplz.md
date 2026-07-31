---
title: '[原创] 基于eBPF的安卓逆向辅助工具——stackplz'
url: https://bbs.kanxue.com/thread-278779.htm
tid: 278779
author: seeeseee
date: '2023-09-08'
tags: [Android安全, 原创, 逆向分析, 程序开发, HOOK注入, 系统相关, 工具脚本]
crawled_at: '2026-07-31T14:38:14+08:00'
replies: 16
---

# 前言

[stackplz](https://github.com/SeeFlowerX/stackplz)是一款基于eBPF技术实现的追踪工具，目的是辅助安卓native逆向，仅支持64位进程，主要功能如下：

- **hardware breakpoint** 基于`pref_event`实现的硬件断点功能，在断点处可读取寄存器信息，**不会被用户态探测到**
	- 前提是需要内核启用`CONFIG_HAVE_HW_BREAKPOINT`，5.10+内核默认开启
- **uprobe hook** 即在**用户态**对动态库下断点，在断点处可读取寄存器等上下文信息
- **trace syscall** 即在**内核态**对syscall进行追踪，输出syscall信息，**无视任何反调试**
- 自动追踪fork产生的进程，可按`pid/uid/tid/package`等组合进行过滤
- 在命中hook的时候可发送信号，例如发送`SIGSTOP`可挂起进程（硬件断点暂未实现发送信号
	- 几乎无视反调试，并且此时可以使用lldb等调试器附加到进程，获取上下文内容
	- 如果进程已经处于相互ptrace的状态，则调试器不可附加，但此时还是可以通过dd等手段获取上下文内容
- 使用上述功能时，均可回溯堆栈

使用要求：**内核 5.10+**（开发板+ReDroid也是可以的，当前支持rock5b），该限制主要来自于需要使用`bpf_probe_read_user`接口

stackplz最初是受到[定制bcc/ebpf在android平台上实现基于dwarf的用户态栈回溯](https://bbs.kanxue.com/thread-274546.htm)启发，加上自己对eBPF技术略有一点研究，然后决定开发这样一款工具

当时核心目的是寻求一种门槛低、不依赖额外环境、能实际落地的方案开发eBPF程序

受限于当时高版本内核安卓设备的普及程度，只实现了寄存器获取与堆栈回溯，限制是内核要求4.14+

经过一年左右的发展，GKI 2.0设备多了起来，各类eBPF相关的内容不断涌现 ~~，加上之前自己立了flag~~

于是最近几个月把之前给stackplz立的flag给陆续落地，加上了许多功能，以期能真正将eBPF技术投入实际的安卓逆向分析中

另外KernelSU近期也发布了新的计划：

- su 使用日志；通过在内核中跟踪 fork, execve 等系统调用，给出调用 su 的进程调用的日志，如时间，命令行参数等。
- 集成支持硬件断点并提供用户空间接口，为开发和调试提供便利。
- 在 kernel 中集成 Lua 解释器并为用户空间提供接口；这样可以让内核运行 lua 脚本，等同于无限制的 eBPF，成为 tracing 好帮手。

**什么，无限制的eBPF？那真的是太好了！** 所以本文再不出，stackplz就要凉啦(>_<)

再次说明要求与限制：**内核 5.10+**，仅支持64位进程

请前往[Releases](https://github.com/SeeFlowerX/stackplz/releases)或者[Actions](https://github.com/SeeFlowerX/stackplz/actions)下载使用

| 123 | `adb push stackplz` `/data/local/tmp``chmod` `+x` `/data/local/tmp/stackplz``cd` `/data/local/tmp` `&& .``/stackplz` `--prepare` |
|-|-|

注意：每次更新版本请手动执行一次`./stackplz --prepare`

# 功能演示

本文演示过程中没有任何APP受到伤害！

写原理太枯燥你们可能就划走了，下次再写，还是先看看实际效果吧~

### **1. 硬件断点**

硬件断点支持四种类型，即`r,w,x,rw`，断点长度为4字节

命令中必须提供pid，`断点绝对地址`或者`断点偏移+动态库名`，下面是两个示例效果：

| 1 | `.``/stackplz` `-p 37919 --brk 0xf3a4:x --brk-lib libnative-lib.so --stack` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202309/941366_6E6RPQE5TVZ57BX.png)

| 1 | `.``/stackplz` `-p 37919 --brk 0x763e6103a4:x --regs --stack --stack-size 4096` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202309/941366_HGJ9P5D4DUJVKMB.png)

说明：

- `--regs` 输出寄存器信息
- `--stack` 默认获取用户态8192字节的栈上数据用于回溯堆栈
- `--stack-size` 可以用于指定要获取的栈上数据大小，必须是8的倍数

如果要给内核空间的地址下硬件断点，可以使用pid+绝对地址的方式，pid给定一个存在的进程即可（不过目前没有回溯内核堆栈的功能，所以给内核空间地址下硬件断点聊胜于无

### **2. uprobe hook**

其原理是替换目标位置动态库的指令为brk指令，执行到目标位置的时候会陷入内核，执行eBPF虚拟机中的代码

美中不足的是，这个brk指令是可以被扫描出来的，但优势也是只有这一个brk指令，没有inlinehook那么多特征

如果确实担心被扫描，那么可以采用硬件断点先检查下^_^

基于该能力，stackplz可以在断点位置读取上下文的内容，在逆向时以最小的侵入力度获取想要的内容，尽可能避开检测

下面是具体效果：

| 1 | `.``/stackplz` `-n com.sfx.ebpf --point strstr[str,str] --getoff --stack` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202309/941366_9Z6MXFUDEQAUBEQ.png)

| 1 | `.``/stackplz` `-n com.sfx.ebpf -l libnative-lib.so -w _Z5func4i[int] --regs` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202309/941366_732Q7M8RWDFZWBF.png)

| 123 | `.``/stackplz` `-n com.sfx.ebpf -w open64[str,int] -f w:``/data``.``/stackplz` `-n com.sfx.ebpf -w open64[str.f0,int] -f w:``/data``.``/stackplz` `-n com.sfx.ebpf -w open64[str.f0.f1.f2,int] -f w:``/data` `-f b:``/sys` `-f w:``/proc` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202309/941366_ZPDPANFN342Z637.png)

说明：

- `--getoff` 计算LR与PC的偏移情况，方便快速定位调用位置
- `-l/--lib` 指定动态库路径，默认为libc.so
	- 大多数情况下使用库名即可，如果遇到同名不同路径，或者找不到的情况，可手动指定为`/proc/{pid}/maps`中的完整路径
- `-w/--point` 意为观测点，配合动态库指定符号或者偏移，可设置多个，**上限6个**
	- 语法是{符号/基址偏移}{+偏移}{[参数类型{寄存器/读取地址},参数类型{.f{规则索引}}]}
	- **一个观测点下最多读取10个参数**
	- **一个参数下最多应用6个过滤规则**
	- 下面是一些使用组合示例，目前支持的类型：`int,uint,int64,uint64,str,ptr,buf`
	- -w _Z5func1v
	- -w 0x9542c[str,str]
	- -w strstr+0x4[str,str]
	- -w strstr[str,str] -w open[str,int]
	- -w 0xA94E8[int:x1,ptr:sp+0x30-0x2c]
		- **默认按寄存器顺序读取，也可以参考本示例，在第一个位置读取x1为int，在第二个位置读取sp+0x30-0x2c为指针**
		- 没错，可以进行简单的计算，这样能够灵活读取栈上的内容
	- -w write[int,buf:x2,int]
	- -w write[int,buf:32,int]
	- -w write[int,buf:0x10,int]
		- buf较为特殊，规则如下：
		- 如果`:`后面是寄存器表明以该寄存器大小为长度读取数据
		- 如果`:`后面是十进制或十六进制字符串，则表明以这个数的大小为长度读取数据
	- -w write[buf:x2:x1,int,int]
		- 这里的规则表示，读取第一个参数时，读的是x1寄存器，长度为x2，即`:`后的第一个内容表示长度，末尾的才是要读取的寄存器
- `-f/--filter` 字符串过滤规则，有三种，分别是`w/white b/black r/replace`，示例如下
	- 规则位于参数的末尾，多个规则以`.`作为分隔符
	- 替换规则涉及两个字符串，以`:::`作为分隔符
	- 示例如下，依次为白名单规则、黑名单规则、替换规则：
		- -f w:/data
		- -f b:/sys
		- -f r:/system/bin/su:::/system/bin/zz
	- -w openat[int,str.f0.f1] 意为对符号`openat`的第二个参数，应用**规则0**和**规则1**
	- -s openat:f0 这是syscall，先在这里说了，意为对openat系统调用的第一个字符串参数应用**规则0**，注意分隔符为`:`

### **3. trace syscall**

原理是将eBPF程序挂载到`raw_tracepoint/sys_enter`和`raw_tracepoint/sys_exit`，然后根据预设配置解析参数

追踪syscall的时候自然也是能输出堆栈的，不过限于篇幅，下面的例子中就不演示了，加`--stack`即可

下面是具体效果：

| 1 | `.``/stackplz` `-n com.sfx.ebpf -s openat,socket,connect` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202309/941366_NTVXM26H5FVVA83.png)

| 1 | `.``/stackplz` `-n com.sfx.ebpf -s %``file``,%net --no-syscall openat,recvfrom` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202309/941366_CE4UCMTM2RCUP3G.png)

| 1 | `.``/stackplz` `-n ???.???.??? -s openat:f0.f1.f2 -f w:``/system` `-f w:``/dev` `-f b:``/system/lib64` `-o tmp.log` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202309/941366_TA24UWU6Q5V7FZ3.png)

说明：

- `-s/--syscall` 一般情况，追踪多个syscall要用`,`作为分隔符
	- 还可以使用下面的内容进行分组追踪，避免手打大量syscall名
		- `all %attr %file %exec %clone %process %net %signal %kill %stat`
	- 对syscall中的参数进行过滤，示例如下，使用`:`作为起始分隔符，使用`.`作为多个规则的分隔符
		- `-s openat:f0.f1.f2`
	- **syscall的参数过滤仅支持syscall的首个字符串参数**

### **4. 进阶使用**

下面将演示如何过root检查，虽然对于eBPF来说做这个事情比较鸡肋，但是还是值得演示一下

核心原理就是通过`bpf_probe_write_user`方法修改内存数据，这里过root检查就是简单替换下相关的字符串

再次说明：本文演示过程中没有任何APP受到伤害！

这里请一位不愿透露姓名的APP做演示，过程如下：

1. 首先执行第一个命令，该命令意为追踪`execve`和`openat`两个系统调用
2. 打开APP，很快啊，APP就崩溃了；这个时候已经采集到syscall的调用情况了，从日志中检查调用的参数，发现有su相关的访问
3. 还是执行第一个命令，然后另开一个shell，执行第二个命令，将有关su的访问替换为其他字符串
4. 打开APP，很快啊，APP还是崩溃了，不过可以发现APP执行得更久一点...
5. 配合使用`--stack`、`--mstack`和`--getoff`，进行更准确的分析
6. 以此往复，最终发现APP还会执行`mount`和`which su`等命令，而且是走的libc.so，于是再开一个shell执行第三个命令

| 123 | `.``/stackplz` `-n ???.???.???,iso -s execve,openat -o tmp_s.log``.``/stackplz` `-n ???.???.???,iso -s execve:f3,openat:f0.f1.f2 -f r:``/sbin/su``:::``/xx` `-f r:``/system/bin/su``:::``/xx` `-f r:``/system/xbin/su``:::``/xx` `-f r:``/system/bin/getprop``:::``/xx``.``/stackplz` `-n ???.???.???,iso -w popen[str.f0.f1] -f r:``mount``:::mounx -f` `"r:which su:::which zz"` `--stack` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202309/941366_XQ2JJ3Z7Q7YEM57.png)

![image](https://bbs.kanxue.com/upload/attach/202309/941366_Q7NQZXRG6UKGVUD.png)

使用`--mstack`，该选项意为手工解析堆栈，因为某些情况下默认的方案可能无法给出详细的堆栈（全是unknown

![image](https://bbs.kanxue.com/upload/attach/202309/941366_AQ49UPX52T9MYS7.png)

在后面两个命令同时使用的情况下，最终能走到APP的启动页面：

![image](https://bbs.kanxue.com/upload/attach/202309/941366_ZAETMUQXSVW3S4D.png)

不过使用eBPF过这个检查实在是麻烦...所以stackplz的定位是辅助分析，这里仅仅演示一下eBPF修改内存的能力

对了，APP怎么老是退出，想个办法让它不要退出好不好哇（

| 1 | `.``/stackplz` `-n ???.???.???,iso -s` `exit` `--``kill` `SIGSTOP --stack` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202309/941366_HGCZX8MF2UYBBFS.png)

这样每次调用exit的时候，都会发送`SIGSTOP`信号，可以把整个进程挂起

每次挂起后如果要恢复进程运行，那么执行`kill -SIGCONT {pid}`这样的命令即可

不过有一个需要注意的问题，那就是发信号的时候，syscall还是会执行，也就是说如果在exit这个系统调用处发信号，进程有可能还是没办法挂起

那么可以配合使用`--stack`、`--mstack`和`--getoff`来判断从用户态的什么地方调用，从上面的结果来看，是libc.so的`__exit`

那么使用下面的命令进行追踪，这样就可以真正在执行到`__exit`的时候挂起，上下文也会保持在`__exit`的状态

| 1 | `.``/stackplz` `-n ???.???.???,iso -w __exit --``kill` `SIGSTOP --stack` |
|-|-|

这是lldb附加上去的效果：

![image](https://bbs.kanxue.com/upload/attach/202309/941366_DUYSV9H2SFH33GF.png)

这里的`iso`指追踪`isolated`进程，`-n/--name`选项可以给定进程分组，目前的分组是`root system shell app iso`

### **5. 其他补充**

如果单条命令hook无法一次性实现想要的追踪内容，那么多开stackplz即可，以及同一个位置多次下hook都是支持的

具有黑白名单的选项：

| 白名单 | 黑名单 |
|-|-|
| -u/--uid | --no-uid |
| -p/--pid | --no-pid |
| -t/--tid | --no-tid |
| --tname | --no-tname |
| -s/--syscall | --no-syscall |

在某些情况下，stackplz无法解析到偏移、堆栈，可以设置debug和输出日志到文件，然后根据日志中的各类事件信息进行分析

- `--debug -o tmp.log`

仅将日志输出到文件，不输出到终端，这对于进行大量追踪的时候，有助于减少数据丢失

- `-q/--quiet`

默认情况下，buf类型的数据打印为`ASCII + hex`，使用下面的选项将打印为`hexdump`

- `--dumphex`

追踪一些特别频繁的调用时，可能会出现部分数据丢失的情况，这个时候请适当增加eBPF的数据缓冲区大小

- `-b/--buffer` 默认8M，一般不建议超过32M

更多命令，请执行`./stackplz --help`查看

### **6. Q & A**

Q: 不能修改寄存器吗
A: 是的，eBPF中无法修改寄存器，只能修改给定地址处的内存数据

Q: 运行不了
A: 首先请使用`5.10+`内核的设备，如果确实不行请反馈至issue

Q: 技术架构等
A: 语言：`Golang + C`
A: 三方库：`ebpf + ebpfmanager + libbpf`
A: 预编译：`BTFHubForAndroid + unwinddaemon`
A: 其他：`ndk clang + Makefile`

# Ref

- [stackplz](https://github.com/SeeFlowerX/stackplz)
- [BTFHubForAndroid](https://github.com/SeeFlowerX/BTFHubForAndroid)
- [unwinddaemon](https://github.com/SeeFlowerX/unwinddaemon)
- [eCapture(旁观者)](https://github.com/ehids/ecapture)
- [定制bcc/ebpf在android平台上实现基于dwarf的用户态栈回溯](https://bbs.kanxue.com/thread-274546.htm)
- [Simpleperf](https://android.googlesource.com/platform/system/extras/+/master/simpleperf/doc/README.md)
- [Tracee](https://github.com/aquasecurity/tracee)
- [bpftrace](https://github.com/iovisor/bpftrace)
- [ebpf](https://github.com/cilium/ebpf)
- [ebpfmanager](https://github.com/gojue/ebpfmanager)
- [eStrace](https://github.com/ri-char/eStrace)

---

# 回复

## 回复 by Ylarod (#2)

*2023-9-8 21:45*

好用，爱用，牛逼！

## 回复 by _ZeroOne (#3)

*2023-9-8 22:02*

我没看，但是我先来评论，脸哥牛的

## 回复 by qxpy_ (#4)

*2023-9-8 22:12*

牛逼

## 回复 by 爱吃菠菜 (#5)

*2023-9-9 01:33*

![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 你瞒我瞒 (#6)

*2023-9-9 09:01*

太强了![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by wx_晚风_407 (#7)

*2023-9-9 18:44*

![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 秋狝 (#8)

*2023-9-9 18:58*

感谢分享

## 回复 by tfflowers (#9)

*2023-9-9 20:34*

脸哥牛逼 ![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 智取棋 (#10)

*2023-9-12 09:25*

牛逼

## 回复 by shinratensei (#11)

*2023-9-12 09:34*

tql

## 回复 by seeeseee (#12)

*2023-9-18 09:31*

谢谢各位支持，最新版加入了以下内容：

- 加入了`--dumpret`选项，可以输出含有给定符号关键词的RET指令偏移，符号本身偏移信息，拿到这些偏移信息后，可以对函数返回值进行快速追踪

- 修复`--reg`选项未按预期工作的情况，该选项可用于计算给定寄存器的偏移情况

- 修复hexdump含有`%`时出现格式化异常的情况

- 修正了指针类型参数的读取，现在可以通过指示`*int`对特定位置进行读取

- 添加了`%dup`和`%epoll`两组快速追踪

- 支持IOVEC类型数据详细解析，即可以详细输出`readv/writev/preadv/pwritev/process_vm_readv/process_vm_writev`的内容了

![image](https://bbs.kanxue.com/upload/attach/202309/941366_E45Q9VK43JAN8FG.jpg)

详细效果请移步[Releases](https://github.com/SeeFlowerX/stackplz/releases/tag/v2.1.3)查看，最新版请在[Actions](https://github.com/SeeFlowerX/stackplz/actions)下载

## 回复 by seeeseee (#13)

*2023-9-18 09:31*

>
> [Ylarod](https://bbs.kanxue.com/user-892096.htm)
>
>  好用，爱用，牛逼！
>
>

![image](https://bbs.kanxue.com/view/img/face/71.gif)![image](https://bbs.kanxue.com/view/img/face/71.gif)![image](https://bbs.kanxue.com/view/img/face/71.gif)

## 回复 by footsome (#14)

*2023-9-18 19:22*

牛

## 回复 by jasonzhou (#15)

*2023-9-21 17:58*

终于有人用到perf了，可以进一步看看kernel里的perf开关

## 回复 by 万里星河 (#16)

*2023-10-31 18:10*

6

## 回复 by 万里星河 (#17)

*2026-4-11 01:09*

重温经典
