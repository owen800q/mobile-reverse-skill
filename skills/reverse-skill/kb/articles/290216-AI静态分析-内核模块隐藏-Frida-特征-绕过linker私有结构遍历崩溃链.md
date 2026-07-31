---
title: '[原创]AI静态分析 内核模块隐藏 Frida 特征 绕过linker私有结构遍历崩溃链'
url: https://bbs.kanxue.com/thread-290216.htm
tid: 290216
author: nuoen
date: '2026-03-08'
tags: [Android安全, 原创, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T13:57:01+08:00'
replies: 26
---

# 某sec.so反调试分析：AI静态分析+内核模块隐藏 Frida 特征+绕过linker私有结构遍历崩溃链

## 1. 背景介绍

跟随feicong大佬学习后，对某sec.so进行了反调试分析，发现其反调试手段主要集中在：

- 用 `/proc/<pid>/status` 检查 `TracerPid`
- 用 `/proc/<pid>/task/<tid>/status` / `stat` 检查线程状态和线程名
- 用 `/proc/self/maps`、`/proc/self/fd` 检查 Frida 注入痕迹
- 再辅以 linker 私有结构遍历，做更底层的模块探测

从已有分析可以确认，这个 so 在初始化阶段会拉起多条保护链，其中与 Frida 最直接相关的一条是：

- 扫描线程列表
- 检查线程状态
- 匹配 Frida 常见线程名

典型命中目标包括：

- `gum-js-loop`
- `gmain`
- `frida`

一旦命中，样本要么直接触发退出，要么进入更激进的异常路径，最终导致进程崩溃。

本文的重点

- 在内核里拦截 `/proc` 相关输出
- 在目标进程读取 `/proc/<pid>/task/<tid>/status` 时临时改写 `task_struct->comm`
- 从源头隐藏 Frida 线程名

可以先用一张总览图把本文涉及的检测面放在一起：
 ![image](https://bbs.kanxue.com/upload/attach/202603/856625_46H3K59T4HTUSR9.webp)

---

## 2. 反调试机制分析

详细静态分析是利用agent工具 codex + tenrec（ida的mcp）进行的，不得不感叹AI正在彻底颠覆行业。

完整的反调试机制可以先用一张图概括：
 ![image](https://bbs.kanxue.com/upload/attach/202603/856625_J82HX7KQXD93YP8.webp)

### 2.1 两条主检测链

目前最准确的整理方式是：

- `init_proc -> sub_1BEC4 -> sub_1B924` 是共同初始化/分发入口
- 真正进入持续检测并最终触发退出的，是 `sub_1B8D4` 和 `sub_1C544`

其中：

1. `sub_1B8D4`

- 负责 `TracerPid`、`PPid`、线程 trace-stop 状态检测
- 命中后走 `sub_11FA4 -> sub_234E0 -> exit_group`

1. `sub_1C544`

- 负责反 Frida 扫描
- 会周期性扫描：
	- `/proc/self/task`
	- `/proc/self/fd`
	- `/proc/self/maps`
- 命中后触发 `_exit/exit`

### 2.2 与 Frida 线程名直接相关的检测点

`sub_1C544` 的主循环里至少包含三个检测点：

1. `sub_1BFAC`

- 遍历 `/proc/self/task/<tid>/status`
- 匹配线程名 `gum-js-loop`、`gmain`

1. `sub_1C158`

- 遍历 `/proc/self/fd/*`
- `readlink` 后匹配注入痕迹字符串

1. `sub_1C26C`

- 遍历 `/proc/self/maps`
- 匹配 `/data/local/tmp`、`frida-agent`、`_AGENT_1.0`

其中和本文最直接相关的是 `sub_1BFAC`。

可以把它还原成下面这种可读伪代码：

| 1234567891011121314151617181920212223 | `void` `scan_task_status_for_frida_threads(``void``) {``DIR *dir = opendir(``"/proc/self/task"``);``if` `(!dir)``return``;` `while` `((de = readdir(dir)) != NULL) {``if` `(!is_digits(de->d_name))``continue``;` `char` `path[0x100];``snprintf(path,` `sizeof``(path),` `"/proc/self/task/%s/status"``, de->d_name);` `char` `buf[0x400] = {0};``if` `(!read_text_file(path, buf,` `sizeof``(buf)))``continue``;` `if` `(``strstr``(buf,` `"gum-js-loop"``) \|\|` `strstr``(buf,` `"gmain"``)) {``_exit(0);` `// 或 exit(0)``}``}` `closedir(dir);``}` |
|-|-|

用户态检测流程可以概括成：

1. 枚举 `/proc/self/task`
2. 拿到每个线程的 `tid`
3. 读取 `/proc/self/task/<tid>/status`
4. 在文本中查找 Frida 特征线程名

这意味着，**只要用户态看到的 `status` 内容被改写，检测就会失效。**

## 对应的用户态线程名检测流程如下： ![image](https://bbs.kanxue.com/upload/attach/202603/856625_ZDDVJ64HCPSCTWA.webp)

## 3. Frida 特征产生原因

很多人第一次分析这类检测时，会把 `gum-js-loop`、`gmain` 当成“样本自己创建的线程”。
其实不是，这些线程名来自 Frida 运行时自身。

### 3.1 `gum-js-loop`

Frida 的脚本执行、消息循环、调度逻辑依赖 Gum。
在目标进程里注入 agent 后，Gum 会创建自己的事件循环线程，典型线程名就是：

- `gum-js-loop`

这个线程基本可以视作“Frida JavaScript runtime 正在进程内运行”的直接信号。

### 3.2 `gmain`

Frida 底层依赖 GLib/GIO 事件循环。
一旦使用消息通信、异步 IO 或内部调度，GLib 相关线程也会出现，典型名就是：

- `gmain`

### 3.3 为什么样本喜欢扫线程名

原因很简单：

1. 成本低

- 不需要复杂反汇编、也不需要解析 linker 私有结构

1. 命中率高

- Frida 默认行为下，这几个线程名非常稳定

1. 输出简单

- `/proc/<pid>/task/<tid>/status` 本身就是纯文本
- 一个 `strstr` 就能完成判定

换句话说，线程名检测是最典型、也最容易落地的 Frida 识别手段之一。

---

## 4. 利用内核模块绕过检测

既然样本依赖的是 `/proc` 输出，那最直接的思路就是：

- 不在用户态和它拼输出
- 直接在内核里改它能看到的 `/proc` 内容

本文使用的模块就是：

>
> https://github.com/nuoen/kernel_modules
>
>
>

### 4.1 总体思路

`hookmodule` 主要做了三类事：

1. hook `proc_pid_status`

- 在生成 `/proc/<pid>/task/<tid>/status` 文本前，临时修改 `task_struct`

1. hook `proc_task_name`

- 在某些 `/proc` 名称输出路径上，直接改写线程名显示

1. hook `show_map_vma`

- 隐藏 `/proc/<pid>/maps` 里的目标库路径

这三类 hook 对应三条不同检测面：

| 检测面 | 目标路径 | 模块对应处理 |
|-|-|-|
| 线程名 | `/proc/<pid>/task/<tid>/status` | `proc_pid_status` kretprobe |
| 任务名显示 | `/proc/.../task/...` 相关 seq 输出 | `proc_task_name` ftrace |
| 映射路径 | `/proc/<pid>/maps` | `show_map_vma` ftrace |

从实现层面看，`hookmodule` 的核心思路是把“用户态读取 `/proc` 的结果”前移到内核里处理：
 ![image](https://bbs.kanxue.com/upload/attach/202603/856625_FQTD7Q2HEYGYF4F.webp)

### 4.2 关键参数

模块支持的关键参数有：

| 1234 | `static` `int` `target_pid = 0;``static` `int` `target_uid = -1;``static` `char` `*hide_so[MAX_NAMES];``static` `int` `hide_so_cnt;` |
|-|-|

示例加载方式：

| 1 | `insmod hookmodule.ko hide_so=``"frida,gum,gmain,AGENT"` `debug=``true` |
|-|-|

这里的 `hide_so` 并不只是“隐藏 so 名字”，更准确地说是：

- 作为一组统一关键字
- 同时用于线程名、maps 路径、状态输出中的字符串过滤

---

## 5. 针对每一类检测的绕过实现

### 5.1 绕过 `/proc/self/task/<tid>/status` 线程名检测

这是本文最核心的一部分。

用户态样本读取的 `status` 文本最终来自内核的 `proc_pid_status()`。
因此最稳的方式不是去改用户态 `fopen/read/fgets`，而是直接在内核里拦 `proc_pid_status`。

#### 5.1.1 核心 hook 点

模块里使用了 kretprobe：

| 12345678 | `static` `struct` `kretprobe_wrap my_kretprobes[] = {``KRETPROBEHOOK(``kretprobe_ret_handler_porc_pid_status,``kretprobe_entry_handler_proc_pid_status,``sizeof``(``struct` `kretprobe_data),``"proc_pid_status"``,``true``),``};` |
|-|-|

进入 `proc_pid_status` 时：

| 1234567 | `task = (``struct` `task_struct *)regs->regs[3];``get_task_struct(task);``task_lock(task);``data->task = task;``data->original_ptrace = task->ptrace;``strscpy(data->original_comm, task->comm, TASK_COMM_LEN);``data->original_state = READ_ONCE(task->__state);` |
|-|-|

如果线程名命中隐藏关键字，就临时改写：

| 123456 | `for` `(``int` `i = 0; i < hide_so_cnt; i++) {``if` `(``strstr``(data->original_comm, hide_so[i])) {``strscpy(task->comm, REPLAE_COMM, TASK_COMM_LEN);``}``}``task->ptrace = 0;` |
|-|-|

返回 `proc_pid_status` 后再恢复：

| 1234567 | `task_lock(task);``task->ptrace = data->original_ptrace;``if` `(``strcmp``(task->comm, REPLAE_COMM) == 0) {``memcpy``(task->comm, data->original_comm, TASK_COMM_LEN);``}``task_unlock(task);``put_task_struct(task);` |
|-|-|

#### 5.1.2 为什么这能绕过

因为用户态样本最终看到的是：

| 1 | `/proc/self/task/<tid>/status` |
|-|-|

而 `status` 文件中的线程名字段，本质上就是内核按 `task_struct->comm` 生成的文本。
我们在文本生成前把 `task->comm` 临时改成替身值，样本读到的就不再是：

- `gum-js-loop`
- `gmain`
- `frida`

而是：

- `replace_comm`

等到文本生成完成，再恢复原值。
这样既能骗过检测，又不会永久破坏线程本身。

这条关键绕过链可以用时序图来表示：
 ![image](https://bbs.kanxue.com/upload/attach/202603/856625_NAH5EW8J538VVME.webp)

#### 5.1.3 这和用户态 hook 的差别

用户态 hook 的问题在于：

1. 容易被对方先发现
2. 需要拦多个 libc 调用点
3. 很容易和目标样本互相对抗

而内核里拦 `proc_pid_status` 的优点是：

1. 只改最终输出源头
2. 对上层 `fopen/fgets/read` 全透明
3. 对样本来说，看到的是“正常 `/proc` 结果”

---

### 5.2 绕过 `proc_task_name` 路径上的线程名显示

除了 `status`，模块还用 ftrace hook 了 `proc_task_name`：

| 123 | `static` `struct` `ftrace_hook my_hooks[] = {``FTRACEHOOK(``"proc_task_name"``, fh_proc_task_name, &real_proc_task_name,` `true``)``};` |
|-|-|

关键实现：

| 1234567891011121314151617 | `static` `asmlinkage` `void` `fh_proc_task_name(``struct` `seq_file *m,``struct` `task_struct *p,``bool` `escape) {``if` `(!escape) {``char` `tcomm[64];``__get_task_comm(tcomm,` `sizeof``(tcomm), p);``for` `(``int` `i = 0; i < hide_so_cnt; i++) {``if` `(``strstr``(tcomm, hide_so[i])) {``const` `char` `*hide_str =` `"hidding"``;``strscpy(tcomm, hide_str, 64);``seq_printf(m,` `"%.64s"``, tcomm);``return``;``}``}``}``real_proc_task_name(m, p, escape);``}` |
|-|-|

#### 5.2.1 作用

这个 hook 并不替代 `proc_pid_status`，而是补位：

- 某些 `/proc` 输出路径不会直接走 `status`
- 但仍会走基于 `seq_file` 的任务名格式化逻辑

对这些路径，`fh_proc_task_name` 可以直接把线程名输出改成：

- `hidding`

#### 5.2.2 为什么需要这一层

因为有些样本并不只读 `status`，还会：

- 枚举 task 目录
- 走其他 proc 文本生成路径
- 直接读取任务名相关输出

这时只拦 `proc_pid_status` 不一定够，`proc_task_name` 相当于多了一层兜底。

它和 `proc_pid_status` 的分工关系如下：
 ![image](https://bbs.kanxue.com/upload/attach/202603/856625_A794VT26MRC55VG.webp)

---

### 5.3 绕过 `/proc/self/maps` 中的 Frida 模块痕迹

`sub_1C26C` 这类检测会扫 `/proc/self/maps`。
模块里对应的处理是 hook `show_map_vma`：

| 123 | `static` `struct` `ftrace_hook my_hooks[] = {``FTRACEHOOK(``"show_map_vma"``, fh_show_map_vma, &real_show_map_vma,` `true``)``};` |
|-|-|

关键逻辑：

| 1234567 | `pathname = d_path(&vma->vm_file->f_path, path_buf,` `sizeof``(path_buf));``for` `(``int` `i = 0; i < hide_so_cnt; i++) {``if` `(``strstr``(pathname, hide_so[i])) {``return``;` `// 不输出这个 maps 条目``}``}``real_show_map_vma(m, vma);` |
|-|-|

#### 5.3.1 为什么能绕过

因为 `/proc/<pid>/maps` 的每一行最终都是内核把 `vma` 格式化成文本。
我们在输出层直接跳过匹配项，用户态样本看到的 maps 就不会包含：

- `frida`
- `gum`
- `AGENT`

#### 5.3.2 但这不是万能的

这点需要说清楚。

`show_map_vma` 只能隐藏：

- `/proc/maps` 文本视图

它**不能隐藏**：

- linker 私有 `solist`
- 已经实际加载进进程的 `soinfo`

所以它能绕过 `sub_1C26C` 这类 `/proc/maps` 检测，
但无法直接解决 `sub_20BDC` 那种 linker 私有结构遍历。

---

### 5.4 对 `TracerPid` 与 TASK_TRACED 的处理

模块还在 `proc_pid_status` kretprobe 里顺手做了两件事：

| 12345 | `if` `(data->original_state == TASK_TRACED) {``WRITE_ONCE(task->__state, TASK_RUNNING);``}` `task->ptrace = 0;` |
|-|-|

#### 5.4.1 作用

这可以绕过另一类典型用户态反调试：

1. 读取 `TracerPid`
2. 检查线程是否处于 `T/t`（trace stop）

这正对应 `so` 另一条链路里的：

- `sub_1AE48`
- `sub_1B730`

---

## 6. 实验结果

| 1234567891011121314151617181920212223242526272829303132333435 | `[` `7621.344945``] hookmodule: Modified TracerPid` `for` `process` `2055` `to` `0``[` `7621.345031``] hookmodule: [SEQ:``358``] KRETPROBE HANDLER :proc_pid_status` `return` `(entry was SEQ:``357``)``[` `7621.345050``] hookmodule: [SEQ:``358``] Restored TracerPid` `for` `process` `2055` `to` `0``[` `7621.346354``] hookmodule: orig getdents64 address` `is` `00000000191697cc``[` `7621.346528``] hookmodule: orig getdents64 address` `is` `00000000191697cc``[` `7623.020180``] hookmodule: [SEQ:``359``] KREPROBE ENTRY_HANDLER:proc_pid_status entry``[` `7623.020255``] hookmodule: Modified TracerPid` `for` `process` `13612` `to` `0``[` `7623.020571``] hookmodule: [SEQ:``360``] KRETPROBE HANDLER :proc_pid_status` `return` `(entry was SEQ:``359``)``[` `7623.020614``] hookmodule: [SEQ:``360``] Restored TracerPid` `for` `process` `13612` `to` `0``[` `7623.020859``] hookmodule: orig getdents64 address` `is` `00000000191697cc``[` `7623.030068``] hookmodule: orig getdents64 address` `is` `00000000191697cc``[` `7624.322863``] hookmodule: orig getdents64 address` `is` `00000000191697cc``[` `7624.323171``] hookmodule: orig getdents64 address` `is` `00000000191697cc``[` `7624.342313``] hookmodule: Hiding target library frida form PID` `13646` `maps``[` `7624.342400``] hookmodule: Hiding target library frida form PID` `13646` `maps``[` `7624.342441``] hookmodule: Hiding target library frida form PID` `13646` `maps``[` `7624.342486``] hookmodule: Hiding target library frida form PID` `13646` `maps``[` `7624.420313``] hookmodule: Hiding target library frida form PID` `13646` `maps``[` `7624.420355``] hookmodule: Hiding target library frida form PID` `13646` `maps``[` `7624.420376``] hookmodule: Hiding target library frida form PID` `13646` `maps``[` `7624.420396``] hookmodule: Hiding target library frida form PID` `13646` `maps``[` `7625.677320``] hookmodule: orig getdents64 address` `is` `00000000191697cc``[` `7625.694435``] hookmodule: orig getdents64 address` `is` `00000000191697cc``[` `7629.417787``] hookmodule: [SEQ:``361``] KREPROBE ENTRY_HANDLER:proc_pid_status entry``[` `7629.417859``] hookmodule: Modified TracerPid` `for` `process` `4725` `to` `0``[` `7629.418097``] hookmodule: [SEQ:``362``] KREPROBE ENTRY_HANDLER:proc_pid_status entry``[` `7629.418108``] hookmodule: [SEQ:``363``] KRETPROBE HANDLER :proc_pid_status` `return` `(entry was SEQ:``361``)``[` `7629.418160``] hookmodule: [SEQ:``363``] Restored TracerPid` `for` `process` `4725` `to` `0``[` `7629.418190``] hookmodule: Modified TracerPid` `for` `process` `4725` `to` `0``[` `7629.418328``] hookmodule: [SEQ:``364``] KRETPROBE HANDLER :proc_pid_status` `return` `(entry was SEQ:``362``)``[` `7629.418367``] hookmodule: [SEQ:``364``] Restored TracerPid` `for` `process` `4725` `to` `0``[` `7629.422463``] hookmodule: [SEQ:``365``] KREPROBE ENTRY_HANDLER:proc_pid_status entry``[` `7629.422506``] hookmodule: Modified TracerPid` `for` `process` `4725` `to` `0``[` `7629.422785``] hookmodule: [SEQ:``366``] KRETPROBE HANDLER :proc_pid_status` `return` `(entry was SEQ:``365``)``[` `7629.422818``] hookmodule: [SEQ:``366``] Restored TracerPid` `for` `process` `4725` `to` `0` |
|-|-|

---

## 7. `sub_20BDC` linker私有结构遍历崩溃链的原理分析

### 7.1 `sub_20BDC` 的作用

`sub_20BDC` 本质上不是 `/proc` 检测函数，而是：

- 从 linker 私有结构中拿到 `solist` 头指针
- 遍历已加载模块链表
- 按名字查找目标模块

可以把它理解成一个私有版：

| 1 | `void` `*find_loaded_module_by_name_via_solist(``const` `char` `*name);` |
|-|-|

### 7.2 `sub_20BDC` 的伪代码

根据 tenrec 分析后结果，可以整理成：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869 | `void` `*find_loaded_module_by_name_via_solist(``const` `char` `*name) {``if` `(!guard_initialized)``solist_head = get_linker_solist_head();` `// sub_2082C()` `cur = solist_head;``if` `(!cur)``return` `0;` `found = 0;``sdk = *off_47FB8;` `if` `(sdk <= 22) {``do` `{``if` `(``strlen``((``char` `*)cur) <= 0x7F &&` `strstr``((``char` `*)cur, name))``found = cur;``cur = *(``void` `**)(cur + 176);``}` `while` `(cur);``return` `found;``}` `if` `(sdk <= 25) {``do` `{``soname = *(``const` `char` `**)(cur + 416);``if` `(soname &&` `strstr``(soname, name))``found = cur;``cur = *(``void` `**)(cur + 48);``}` `while` `(cur);``return` `found;``}` `if` `(sdk == 31) {``while` `(cur) {``if` `((*(uint8_t *)(cur + 408) & 1) != 0)``soname = *(``const` `char` `**)(cur + 424);``else``soname = (``const` `char` `*)(cur + 409);` `if` `(soname &&` `strstr``(soname, name))``found = cur;` `cur = *(``void` `**)(cur + 40);``}``return` `found;``}` `if` `(sdk > 31) {``while` `(cur) {``if` `((*(uint8_t *)(cur + 392) & 1) != 0)``soname = *(``const` `char` `**)(cur + 408);``else``soname = (``const` `char` `*)(cur + 393);` `if` `(soname &&` `strstr``(soname, name))``found = cur;` `cur = *(``void` `**)(cur + 40);``}``return` `found;``}` `do` `{``soname = *(``const` `char` `**)(cur + 408);``if` `(soname &&` `strstr``(soname, name))``found = cur;``cur = *(``void` `**)(cur + 40);``}` `while` `(cur);` `return` `found;``}` |
|-|-|

### 7.3 检测逻辑使用frida后，sub_20BDC必崩

`sub_20BDC` 的危险点有两个：

1. 它依赖 linker 私有结构偏移
2. 它命中目标模块后不会立即返回，而是继续遍历整个 `solist`

这意味着：

- 即使它已经找到了目标模块
- 只要后续节点里存在一个它用错偏移无法正确处理的节点
- 它仍然会在继续遍历时把自己扫崩

这也解释了为什么：

- 不挂 Frida 时通常不崩
- 挂 Frida 后更容易崩

根因不是“Frida 改坏了 linker 偏移”，而是：

- Frida 注入后，`solist` 中节点更多、更复杂
- `sub_20BDC` 在命中目标后继续遍历
- 最终扫到一个不兼容节点

这条“正常环境通常不崩、Frida 环境更容易崩”的差异，可以用下面这张图概括：
 ![image](https://bbs.kanxue.com/upload/attach/202603/856625_93EW4YSWRTJWP8H.webp)

### 7.4 调用流程

从当前分析可以确认，`sub_20BDC` 至少有两条从初始化阶段可达的路径。

#### 路径一：长链

| 1234567 | `.init_proc``-> sub_13728``-> sub_8784``-> sub_DF74``-> sub_FD08``-> sub_148F0``-> sub_20BDC` |
|-|-|

#### 路径二：短链

| 1234 | `.init_proc``-> sub_95C8``-> sub_11F38``-> sub_20BDC` |
|-|-|

结合动态日志，当前更直接的崩溃短链是：

| 12345 | `sub_95C8``-> sub_11F38``-> sub_C7F4 => "**sec.so"``-> sub_20BDC``-> SIGSEGV / Process terminated` |
|-|-|

可以把这条崩溃链画成：
 ![image](https://bbs.kanxue.com/upload/attach/202603/856625_R2Q499PQ95GHEBW.webp)

### 7.5 这条链路我采用frida绕过而不是内核模块

原因很简单：

- `sub_1BFAC / sub_1C158 / sub_1C26C` 依赖的是 `/proc`
- `sub_20BDC` 依赖的是 linker 进程内存里的私有 `solist`

也就是说：

- `show_map_vma` 能骗 `/proc/maps`
- `proc_pid_status` 能骗 `/proc/task/.../status`
- 但都骗不了 linker 私有模块链

因此，从对抗角度看：

1. 内核模块适合解决 `/proc` 检测链
2. `sub_20BDC` 这类 linker 私有遍历链，仍需要用户态来做

| 123456789101112131415 | `function` `patch_sub_20BDC(secmodule) {``const addr = secmodule.base.add(0x20BDC);``Interceptor.replace(addr,` `new` `NativeCallback(``function` `(namePtr) {``let name =` `'<null>'``;``try` `{``if` `(!namePtr.isNull()) {``name = namePtr.readCString();``}``}` `catch` `(_) {}` `console.log(``'[+] patch sub_20BDC @ '` `+ addr +` `' =====> return NULL for name='` `+ name);``return` `ptr(0);``},` `'pointer'``, [``'pointer'``]));``console.log(``'[+] semantic patch installed sub_20BDC @ '` `+ addr);``}` |
|-|-|

---

## 8. 总结

`**sec.so` 的反调试并不是单点检测，而是一组层次化的保护：

1. `/proc/status`、`TracerPid`、线程 trace-stop
2. `/proc/task/<tid>/status` 里的线程名
3. `/proc/self/maps` 与 `/proc/self/fd`
4. linker 私有 `solist` 遍历

本文给出的内核模块方案，核心价值在于：

- 不和用户态 libc/stdio 对抗
- 直接改写 `/proc` 最终输出源头
- 对 `gum-js-loop`、`gmain`、`frida` 这类线程名检测非常有效

这使得：

- `sub_1BFAC` 这类基于 `/proc/task/.../status` 的反 Frida 检测可以被稳定绕过
- `TracerPid` / `TASK_TRACED` 相关检测也可以顺手处理
- `/proc/maps` 里的显式 Frida 痕迹也能被隐藏

但同样需要明确边界：

- 内核模块能骗 `/proc`
- 不能直接骗 linker 私有结构

因此在实战中，更合理的策略不是“只用一种手段”，而是分层处理：

1. 用内核模块压住 `/proc` 检测链
2. 用用户态 patch 或 uprobe 处理 `sub_20BDC` 这类 linker 私有遍历链

这才是对抗 `**sec.so` 这类综合型反调试模块的更稳妥方案。

最后用一张总图收敛本文结论：
 ![image](https://bbs.kanxue.com/upload/attach/202603/856625_PKMJU5MNE473G9K.webp)

---

# 回复

## 回复 by 我不是卷王 (#2)

*2026-3-8 07:19*

学到了

## 回复 by didiid (#3)

*2026-3-8 11:10*

写的很好

## 回复 by mb_ldbucrik (#4)

*2026-3-8 13:22*

感谢分享

## 回复 by fei3ei (#5)

*2026-3-9 09:48*

学习

## 回复 by 寻梦之璐 (#6)

*2026-3-9 10:18*

6666

## 回复 by k4y0z (#7)

*2026-3-9 10:31*

666

## 回复 by Imxz (#8)

*2026-3-9 15:02*

tql

## 回复 by huangjw (#9)

*2026-3-11 14:02*

好文章，干货

## 回复 by mb_jhohnbzu (#10)

*2026-3-12 10:47*

666

## 回复 by 中文fjja (#11)

*2026-3-15 15:29*

学习学习

## 回复 by 天地一逆旅 (#12)

*2026-3-17 09:46*

get_linker_solist_head();   // sub_2082C()有对应微代码吗？想了解一下怎么获取solist head

## 回复 by nuoen (#13)

*2026-3-19 01:44*

>
> [mb_cqcnvzkn](https://bbs.kanxue.com/user-1070930.htm)
>  get_linker_solist_head(); // sub_2082C()有对应微代码吗？想了解一下怎么获取solist head
>

void * get_linker_solist_head()
{
    long linker_base = 0;
    FILE *fp = NULL;
    unsigned char *buf = NULL;
    size_t size = 0;

    unsigned char *symtab = NULL;
    unsigned char *strtab = NULL;
    int sym_count = 0;

    linker_base = sub_20B04("/system/bin/linker64");
    if (!linker_base)
        linker_base = sub_20B04("/bionic/bin/linker64");
    if (!linker_base)
        linker_base = sub_20B04("/apex/com.android.runtime/bin/linker64");
    if (!linker_base)
        return NULL;

    fp = fopen("/system/bin/linker64", "rb");
    if (!fp)
        return NULL;

    fseek(fp, 0, SEEK_END);
    size = ftell(fp);
    fseek(fp, 0, SEEK_SET);

    buf = (unsigned char *)malloc(size);
    if (!buf) {
        fclose(fp);
        return NULL;
    }

    memset(buf, 0, size);
    fread(buf, 1, size, fp);
    fclose(fp);

    // 这里应该是 ELF header / section header 解析
    // 反编译结果把 buf 当成 FILE* 访问，实际不是 FILE
    parse_elf_find_symtab_and_strtab(buf, &symtab, &strtab, &sym_count);

    if (!symtab || !strtab || sym_count <= 0) {
        free(buf);
        return NULL;
    }

    for (int i = 0; i < sym_count; i++) {
        Elf64_Sym *sym = (Elf64_Sym *)(symtab + i * sizeof(Elf64_Sym));
        const char *name = (const char *)(strtab + sym->st_name);

        if (!strstr(name, "solist"))
            continue;

        if ((sym->st_info & 0xF) != 1)   // STT_OBJECT
            continue;

        if (*off_47FB8 == 27 && strlen(name) >= 0x28)
            continue;

        uint64_t st_value = sym->st_value;
        free(buf);

        if (!st_value)
            return NULL;

        return *(void **)(linker_base + st_value);
    }

    free(buf);
    return NULL;
}

## 回复 by 天地一逆旅 (#14)

*2026-3-19 09:57*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  nuoen](https://bbs.kanxue.com/user-856625.htm)
>  void * get_linker_solist_head()
> {
>  long linker_base = 0;
>  FILE *fp = NULL;
>  unsigned ch ...
>

# readelf -s linker64 |grep solist
  4818: 000000000012b218     8 OBJECT  LOCAL  DEFAULT   19 __dl__ZL6solist
  4860: 00000000000b2d30    20 FUNC    LOCAL  HIDDEN    11 __dl__Z17solist_[...]
  4861: 00000000000b2e0c    12 FUNC    LOCAL  HIDDEN    11 __dl__Z15solist_[...]
  4862: 00000000000b2e18    12 FUNC    LOCAL  HIDDEN    11 __dl__Z17solist_[...]
  4864: 00000000000b2e24    12 FUNC    LOCAL  HIDDEN    11 __dl__Z15solist_[...]
  4865: 00000000000b2d44   200 FUNC    LOCAL  HIDDEN    11 __dl__Z20solist_[...]
原来是通过符号表去找solist的地址。![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by git_55111Empycity (#15)

*2026-4-5 23:51*

666

## 回复 by breakM (#16)

*2026-4-8 19:09*

感谢分享

## 回复 by git_14248bibinocode (#17)

*2026-4-11 23:50*

66666

## 回复 by mb_ggnlrzcs (#18)

*2026-4-12 12:18*

666

## 回复 by 曰你 (#19)

*2026-4-17 11:11*

可以将so文件发出来下吗

## 回复 by mb_zcfhleoj (#20)

*2026-4-22 16:37*

感谢分享

## 回复 by AYHMO (#21)

*2026-4-23 09:54*

6666

## 回复 by uni7corn (#22)

*2026-4-27 12:26*

感谢分享

## 回复 by mb_lzotvdxv (#23)

*2026-5-10 06:25*

请在 Telegram 上联系我，有个重要的 2000 美元任务。
 Telegram：@dlopenext

## 回复 by 天涯共何时 (#24)

*2026-5-13 16:27*

666

## 回复 by 天涯共何时 (#25)

*2026-5-14 10:48*

学废了～

## 回复 by 天涯共何时 (#26)

*2026-5-14 10:57*

博主可以私发下so吗 文章写的真好我想学习实操一下

## 回复 by mb_osxdmntv (#27)

*2026-5-14 11:03*

666
