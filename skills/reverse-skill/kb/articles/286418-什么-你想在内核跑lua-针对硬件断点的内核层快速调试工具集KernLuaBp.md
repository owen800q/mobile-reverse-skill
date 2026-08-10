---
title: '[原创]什么,你想在内核跑lua?针对硬件断点的内核层快速调试工具集KernLuaBp'
url: https://bbs.kanxue.com/thread-286418.htm
tid: 286418
author: dadadasda
date: '2025-04-10'
tags: [Android安全, 原创, 工具脚本, 源码框架, 逆向分析, 系统相关, HOOK注入]
crawled_at: '2026-08-10T05:00:19+00:00'
replies: 21
---

## 开发动机

目前主流的调试工具依赖于ptrace接口，需要2个进程通过信号来互相唤醒处理调试事件。简单考察一次单点命中，目标tracee+trace线程至少需要 **3次** 用户/内核上下文切换：

{**tracee执行直到命中hwbp_trap**}
-[上下文切换，同步处理]->
（储存信号，唤醒tracer睡眠）
-[上下文切换+异步进程调度]->
{**tracer被唤醒处理，重新执行tracee程序**}
-[上下文切换+异步进程调度]->
{**tracee重新开始运行**}

符号标志意义为：[上下文开销] {**用户态执行内容**} (内核态执行内容)

可以看到上下文开销中直接由硬件异常导致的上下文切换是同步的，耗时较少，但是睡眠和唤醒tracer、tracee是一个不小的开销，并且tracer的处理函数需要反复使用ptrace调用陷入内核态以获取tracee的内存+寄存器信息,实际的运行开销比这里只考虑做ptrace_cont的场景更大。但是呢，为了能够在tracer线程里灵活执行可修改的调试操作，好像又是只能依赖这一套反复唤醒和切换的流程。对...对吗？

也并不一定，如果内核硬件调试异常的handler中直接把这个异常给处理完了，然后直接返回用户态，

{**tracee执行直到命中hwbp_trap**}
-[上下文切换，同步处理]->
（丢弃信号，内核内处理异常，硬件断点更新，直接返回用户态）
-[上下文切换，同步处理]->
{**tracee重新开始运行**}

这样的切换开销最多只是**2次同步上下文切换**，相比之下就是飞速。那么怎么实现可修改的异常处理功能呢？不妨把lua脚本植入进内核。查了下git，果然在内核层跑解释器语言这种烂点子已经有人想过。

## 技术要求

- 有可完整编译的kernel源码
- 编写内核模块的makefile与kconfig选项
- 检查下发现lunatik对于调用lua的写法强烈依赖loadFile也即从内核态直接去读取文件，这是个傻x行为
- 移入文档
	- 移入文档
	-
	-
	-
	-
- 改写特定的系统调用，用于向内核传入lua脚本字符串，以配置对应的hwbp_trap_handler中实现的功能
	- 例如劫持socket/ioctl/sendto/recvfrom
	- 仿apatch直接定义新syscallno
- 将硬件调试中断的处理导入通用lua处理函数，然后立即清除线程异常状态返回用户态

# 20250814更新-适用于内核模块的lua源码

截取自lunatik，目前只包含标准库和dostring功能（string直接从用户空间拷贝）
源码集合附上，放入待编译的内核子模块`path/to/your/module/`以子目录为`lua-core`为例

## MakeFile填写

| 12345678910111213141516 | `obj``-``$(CONFIG_YOUR_MODULE)` `+``=` `yourmoduleall.o` `ccflags``-``y` `+``=`  `-``D_LUNATIK` `-``D_KERNEL` `-``DLUA_USE_C89` `-``I${PWD}``/``lua``-``core`  `# 假设yourmodule.c为你的内核子模块所有功能集成源码文件` `yourmoduleall``-``y` `+``=`  `yourmodule.o \``lua``-``core``/``lapi.o lua``-``core``/``lcode.o lua``-``core``/``lctype.o lua``-``core``/``ldebug.o lua``-``core``/``ldo.o \``lua``-``core``/``ldump.o lua``-``core``/``lfunc.o lua``-``core``/``lgc.o lua``-``core``/``llex.o lua``-``core``/``lmem.o \``lua``-``core``/``lobject.o lua``-``core``/``lopcodes.o lua``-``core``/``lparser.o lua``-``core``/``lstate.o \``lua``-``core``/``lstring.o lua``-``core``/``ltable.o lua``-``core``/``ltm.o \``lua``-``core``/``lundump.o lua``-``core``/``lvm.o lua``-``core``/``lzio.o \``lua``-``core``/``lauxlib.o lua``-``core``/``lbaselib.o \``lua``-``core``/``lcorolib.o lua``-``core``/``ldblib.o lua``-``core``/``lstrlib.o \``lua``-``core``/``ltablib.o lua``-``core``/``lutf8lib.o lua``-``core``/``lmathlib.o lua``-``core``/``linit.o \``lua``-``core``/``loadlib.o lua``-``core``/``arm64``/``setjmp.o` |
|-|-|

## 头文件引用

| 12345678910111213141516171819202122232425262728293031323334353637 | `#include "lua-core/lua.h"``#include "lua-core/lauxlib.h"``#include "lua-core/lualib.h"` `/``/``取消lunatik中loadfile的功能``int` `lunatik_loadfile(lua_State` `*``L, const char` `*``filename, const char` `*``mode){``return` `1``;``}` `/``/``内核环境测试代码`   `int` `call_lua(char``*` `simple_cmd){` `int` `result;``lua_State` `*``L` `=` `luaL_newstate();` `/``*` `create state` `*``/``if` `(L` `=``=` `NULL) {``printk(KERN_ALERT` `"Lua-cannot create state: not enough memory\n"``);``return` `1``;``}``lua_gc(L, LUA_GCSTOP);` `/``*` `stop GC` `while` `building state` `*``/``/``/``lua基础库``luaL_openlibs(L);` `/``/` `/``/``load kernLuaBpLibs``/``/` `luaL_openKernBplibs(L);``result``=``luaL_dostring(L,simple_cmd);``lua_close(L);``return` `0``;``}` `/``/``用来搞笑的测试代码``/``/``放入模块_init中测试``int` `test_lua(void){``return` `call_lua(``"print('hello motherfucker')"``);``}` |
|-|-|

## 测试结果

这样就算验证完了内核的lua执行环境
![image](https://bbs.kanxue.com/upload/attach/202508/1006186_4EMQ7M3QEYHYK85.webp)

# 20250814更新-目前部分发布Lua接口文档

## 用户态核心接口-函数形式

劫持系统调用实现

- `public static native void installLua(String name,String lua_script)` 为内核中指定名字`name`的Luastate解释器挂载脚本。
- `public static native String execLuaInkernel(String lua_script)` 单次解释器执行脚本返回结果数据，Luastate立即销毁。

## 内核态接口Lua模块KernLuaBp

在lua代码中已安装实现的接口,可直接在lua代码中调用

### Luastate相关

- `KernLuaBp.preInit(tid)`为线程提取准备好luaState,减少线程重入lua环境新建Luastate带来的overhead
- `KernLuaBp.Load(tid,script)`为线程LuaState预先加载函数定义
- `KernLuaBp.delState(tid)`清除tid上的Luastate
- `KernLuaBp.delAllState()`清除所有缓存的Luastate

### 线程上下文相关

- `KernLuaBp.tid()`
- `KernLuaBp.uid()`
- `KernLuaBp.getRegContext()`获取寄存器状态`RegContext`
- `KernLuaBp.hangup(name)`强制睡眠当前线程，并为此线程标记命名
- `KernLuaBp.wake(name)` 唤醒name命名的线程

#### 寄存器context

- `RegContext.get(abbr)` 获取当前线程寄存器值,abbr为寄存器缩写，包括特殊寄存器lr,pc,sp一般整形寄存器xn以及浮点寄存器dn
- `RegContext.Set(abbr,val)` 写入当前线程寄存器值，例如 "x0",0x8000

#### 线程内存访问

- `KernLuaBp.accessMem(storeKey,tid,addr,len,mod)`保存addr/len的用户态内存到全局表的storeKey变量中, 读取`mode=0`，写入`mode=1`,保存与待写入内容准备为base64格式。

### 进程权限接口

- `KernLuaBp.setUid(uid)`切换进程用户id
- `KernLuaBp.setGroups(groups[])`切换进程groups

### 用户态内存分配

- `KernLuaBp.userMap(pages)` 映射pages页面数的匿名内存，返回起始地址
- `KernLuaBp.userUnMap(addr)` 清除映射

### 同步硬件断点安装

- `KernLuaBp.installBp(addr,type,index,enable,callbackName)`为current线程安装bp,指令断点`type=0`,读断点`type=1`,写断点`type=2`。`callbackName`为线程踩断点后同步调用的Luastate镜像名称，将在此Luastate上调用`bpHit()函数`。`callbackName`设置为nil则默认为当前线程缓存的Luastate执行用户定义的`bpHit()函数`。
- `KernLuaBp.installBpTid(tid,addr,type,index,enable)`为其他线程安装，会先暂停线程，再进行安装
- `KernLuaBp.singleStep()`设置当前进程为单步模式
- `KernLuaBp.isSingleSteped()`判定当前进程是否处在单步暂停中
- `KernLuaBp.clearBp(tid)`清除线程上安装的所有bp

### 封装功能接口

- `KernLuaBp.utils_installFuncHook(addr,callback_in,callback_out,max_retdistance=1024)`
	- `callback_in`与`callback_out`类似frida interceptor接口`onEnter()`与`onLeave()`，无调用参数，需要通过KernLuaBp接口获得context参数。如果是无尾函数,或者在max_retdistance范围内没有ret指令，则onLeave不生效
- `KernLuaBp.utils_mapsItem()`获取当前线程映射表
- `KernLuaBp.utils.mapsItemSearch(desc,index)` 获取满足匹配的第index个映射表项，效率比整体dump更快

### 日志

- `KernLuaBp.log(tag,info)`写入专属logbuf
- `KernLuaBp.readLog(maxcnt)`读取并清除专属logbuf

## 实践用例

未完待续...后续可以给大家演示一下常见的几个骚操作,包括

- JumpKing.lua，命中断点后跳转进入任意位置代码继续执行
- hookEnter.lua 函数入口hook
- hookRet.lua 函数返回hook
- DepthTracer.lua 有限制调用栈的函数trace
- v_vdso.lua 仿vdso用户空间映射动态可执行库
...

上传的附件：
- lua-core.zip

（312.34kb，40次下载）

---

# 回复

## 回复 by dadadasda (#2)

*2025-8-14 14:12*

追加了可编译的lua-core源码,与当前开发完毕的内核lua接口

## 回复 by 暴强 (#3)

*2025-8-17 08:57*

你真猛！

## 回复 by mb_ndttieme (#4)

*2025-8-17 09:04*

谢谢你的细致分析，受益匪浅！

## 回复 by mb_nkjfyhkg (#5)

*2025-9-3 02:15*

mark

## 回复 by TeamAR (#6)

*2025-9-3 03:17*

like!

## 回复 by mb_akowpmjs (#7)

*2025-9-10 19:57*

6666

## 回复 by bullyxy (#8)

*2025-9-22 13:28*

gooooood

## 回复 by Ara (#9)

*2025-9-28 21:04*

good

## 回复 by mb_euhyowpw (#10)

*2025-9-28 21:09*

1

## 回复 by Obuchi (#11)

*2025-9-30 19:10*

看看

## 回复 by asuralove (#12)

*2025-10-10 10:03*

666

## 回复 by mb_irhdtnzm (#13)

*2025-10-14 15:18*

1

## 回复 by 大萨达 (#14)

*2025-11-9 11:40*

666

## 回复 by mb_qimctavn (#15)

*2025-11-9 12:33*

6

## 回复 by Heiyiren123 (#16)

*2025-12-8 16:40*

感谢分享技术干货！

## 回复 by wx_白鸟之诗 (#17)

*2026-3-19 11:22*

感谢分享

## 回复 by 星辰北天 (#18)

*2026-3-29 19:49*

666

## 回复 by wx_Dispa1r (#19)

*2026-3-29 23:34*

1

## 回复 by mb_paopxhtx (#20)

*2026-6-22 22:32*

厉害就两个字

## 回复 by 温泉划水鱼 (#21)

*2026-6-22 22:49*

good

## 回复 by Yuuuual (#22)

*2026-7-23 13:38*

学习记录，感谢分享
