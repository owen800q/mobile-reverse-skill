---
title: '[原创]libmsaoaidsec.so 检测体系分析'
url: https://bbs.kanxue.com/thread-291377.htm
tid: 291377
author: xiusi
date: '2026-05-28'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T15:05:15+08:00'
replies: 128
---

# libmsaoaidsec.so Native 检测体系分析：线程调度、签名校验与代码 CRC

## 前言：样本定位与阅读方式

`libmsaoaidsec.so` 是一个 Android Native 层共享库，文件格式为 **ELF64 AArch64**。从初始化入口、线程创建逻辑和大量 `/proc`、系统属性、APK/ZIP 访问行为来看，该库主要承担运行环境检测、反调试、反注入、签名校验和代码完整性校验等职责。

本文以 IDA 静态分析结果为基础，将该库的检测逻辑整理为三条主线：

1. **线程调度主线**：`.init_proc -> sub_1BEC4 -> sub_1B924`，负责创建 `sub_1C544`、`sub_1B8D4`、`sub_19E0C` 等检测线程。
2. **APK/签名校验主线**：`.init_proc -> sub_13728 -> sub_2701C -> sub_26E5C -> sub_1678C`，负责定位 APK、读取签名文件并做白名单校验。
3. **代码 CRC 主线**：`.init_proc -> sub_13728` 执行初始化期 CRC，`.init_proc -> sub_9150 -> sub_8CAC` 执行周期性 CRC。

---

## 总体调用关系：从 .init_proc 展开的三条主线

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/1036360_7BHBZ7G6RZKK5W7.webp)

整体检测面可以概括为：

| 主线 | 入口链路 | 核心目标 | 代表函数 |
|-|-|-|-|
| **线程调度主线** | `.init_proc -> sub_1BEC4 -> sub_1B924` | 创建周期性检测线程，检查 Frida、调试器、ADB/USB 环境 | `sub_1C544`、`sub_1B8D4`、`sub_19E0C` |
| **APK/签名校验主线** | `.init_proc -> sub_13728 -> sub_2701C -> sub_26E5C -> sub_1678C` | 检查 APK 路径、签名文件和签名公钥 CRC 白名单 | `sub_26E5C`、`sub_1678C`、`sub_12050` |
| **代码 CRC 主线** | `.init_proc -> sub_13728`，`.init_proc -> sub_9150 -> sub_8CAC` | 检查内存中的 Native 代码片段是否被 patch/hook | `sub_13728`、`sub_8CAC`、`sub_16720` |

---

## 保护特征概览

该库不是单一反调试函数，而是一组组合式检测。几个明显特征如下。

| 特征 | 表现 | 分析意义 |
|-|-|-|
| **字符串运行时解密** | 大量字符串在栈上构造后进行循环 XOR 解密，常见模式为 3 字节循环 key | 静态字符串搜索难以直接定位检测点 |
| **控制流扁平化 / BCF** | 多个函数被 IDA 标记为 `The function seems has been flattened` | 伪代码中出现大量状态变量和跳转噪声，需要抽象语义 |
| **动态 API 解析** | 通过 `dlopen("libc.so")`、`dlsym("pthread_create")` 创建线程 | 弱化导入表特征，增加静态追踪难度 |
| **动态生成退出代码** | `mmap` RWX 内存，写入 AArch64 syscall stub，再执行 `exit_group(0)` | 避免所有退出路径都直接暴露为 `_exit` / `exit_group` 符号 |
| **多线程轮询检测** | Frida、反调试、ADB/USB、代码 CRC 均有独立线程或初始化旁路 | 绕过某一个检测点并不等于绕过整套保护 |
| **签名白名单校验** | 从 APK v1 签名文件中提取 RSA 公钥片段并计算 CRC32 | 检查当前安装包签名是否符合内置白名单 |
| **早期反检测检测** | `sub_23B18` 在初始栈附近搜索 `MAGISKTMP` | 命中后使 `.init_proc` 后续 native 检测初始化短路，更像风险打标/降级入口 |

字符串解密的核心模式可以抽象为。不同函数的局部 key 表达可能存在差异，但整体都是“密文栈上构造 -> 循环 XOR -> 运行时得到明文”的模式：

```c
for (i = 0; i < len; i++) {
    buf[i] ^= key[i % 3];
}
```

解密出的关键字符串包括 `/proc/self/task`、`/proc/self/maps`、`gum-js-loop`、`gmain`、`frida-agent`、`sys.usb.config`、`META-INF/CERT.RSA`、`META-INF/ANDROID.RSA` 等。这些字符串基本覆盖了后文的检测逻辑。

---

## 早期反检测检测：`sub_23B18` 与 `MAGISKTMP`

在进入线程调度、APK 签名校验和代码 CRC 之前，`.init_proc` 会先调用 `sub_25A48()`。该函数受全局开关 `dword_48850` 控制，当 `sub_CC64()` 返回 `218` 时才进入 `sub_23B18()`：

```c
__int64 sub_25A48()
{
    int n218 = sub_CC64();      // 返回 dword_48850

    if (n218 == 218)
        return sub_23B18() & 1;

    return 0;
}
```

`.init_proc` 对返回值的使用方式比较关键：

```c
result = sub_25A48();

if ((result & 1) == 0) {
    sub_1BEC4();    // 线程调度与运行环境检测
    sub_13728();    // 初始化期 CRC 与 APK/签名校验链
    sub_23AD4();    // 模块信息初始化与辅助校验
    sub_9150();     // 周期性代码 CRC 线程
}

return result;
```

也就是说，`sub_23B18()` 返回 `1` 时并不是直接 `exit_group(0)`，而是让 `.init_proc` **跳过后续 native 检测初始化**。这一点决定了它更像“反检测检测/风险打标/降级入口”，而不是最终风控拦截点。

### `sub_23B18` 的核心检测目标

`sub_23B18()` 运行时解密出三个关键字符串：

| 解密结果 | 用途 |
|-|-|
| `/proc/self/maps` | 扫描当前进程内存映射 |
| `%lx-%lx %s %lx %s %ld %s` | 解析 maps 行 |
| `MAGISKTMP` | 检测 Magisk 临时环境变量残留 |

函数语义可以概括为：

```c
bool sub_23B18_semantic()
{
    cmdline = read("/proc/<pid>/cmdline");

    if (strchr(cmdline, ':') != NULL)
        return false;                       // 只检测主进程

    maps = fopen("/proc/self/maps", "r");
    stack_range = find_mapping_containing_local_stack_addr(maps);

    if (!stack_range.found)
        return false;

    return scan_c_strings_near_stack_top(stack_range.end - 0x200,
                                         stack_range.end,
                                         "MAGISKTMP");
}
```

它没有直接调用 `getenv("MAGISKTMP")`，而是通过 `/proc/self/maps` 找到当前栈映射，再扫描栈顶附近的原始字符串区域。Android/Linux 进程启动时，`argv`、`envp`、`auxv` 等数据会放在初始栈上。即使后续通过 `unsetenv()` 或修改 `environ` 隐藏环境变量，原始字符串仍可能残留在栈映射中。

### 为什么命中后反而跳过后续检测

从常规防护直觉看，检测到 Magisk/root 痕迹后应该更严格。但这里的代码行为是：`MAGISKTMP` 命中后 `sub_23B18()` 返回 `1`，再由 `.init_proc` 跳过 `sub_1BEC4`、`sub_13728`、`sub_23AD4`、`sub_9150` 等后续初始化。

更合理的解释是：**这不是最终风控决策，而是“反检测检测”或高风险环境标记**。在 Magisk/Zygisk 环境下，maps、linker、ART、线程和属性读取结果都可能被改写，继续启动大量本地检测线程既容易暴露检测逻辑，也可能产生不稳定结果。因此样本选择在本地 native 层短路后续检测，把这个高风险状态交给其他链路处理，例如 Java 层、服务端风控、功能降级或静默打标。

```
sub_23B18 是受配置控制的 Magisk 环境痕迹探测函数。
命中 MAGISKTMP 后，它返回 1，使 .init_proc 跳过后续 native 检测初始化。
该行为更像反检测检测、兼容降级或风险打标入口，而非直接拦截入口。
```

---

## 主线一：线程调度与运行环境检测

线程调度主线从 `.init_proc` 开始。初始化函数会读取 `/proc/<pid>/cmdline`，只有当进程名不包含 `:` 时才进入 `sub_1BEC4()`。在 Android 应用中，`com.xxx:push`、`com.xxx:remote` 这类进程名通常表示子进程或带后缀进程。该库选择在主进程中创建主要检测线程，避免在多进程场景下重复执行重检测逻辑。

### `sub_1BEC4`：保存主进程 PID 并进入线程调度器

**部分恢复伪代码：**

```c
void sub_1BEC4()
{
  ...
  main_process = getpid();                      // 主进程 PID
  sub_1B924();                                  // 线程调度与运行环境检测
}
```

`sub_1BEC4()` 的语义很简洁：

```
sub_1BEC4()
  ├─ pid = getpid()
  ├─ 保存到全局 pid
  └─ sub_1B924()
```

这个全局 pid 后续会被 `sub_1B8D4` 使用，尤其是在 `sub_1AB54()` 中用于判断 `TracerPid` 的父进程是否为主进程。换句话说，它不仅是记录当前进程 ID，还参与了后续的 **self-debugger 白名单判断**。

### `sub_1B924`：主检测线程调度器

**部分恢复伪代码：**

```c
void __fastcall sub_1B924()
{
  ...
  handle = dlopen(libc_so, RTLD_NOW);
  if ( handle )
  {
    pthread_create = dlsym(handle, pthread_create_str);
    if ( sub_CAA8() == 248 && !sub_12D9C() )
      sub_1CEF8(pthread_create);                // Frida/注入痕迹检测
    if ( sub_CAE8() == 249 )
      (pthread_create)(&unk_49650, 0LL, sub_1B8D4, 0LL);// 反调试、TracerPid、线程状态检测
    else
      sub_1B380(handle, pthread_create);
    if ( sub_CA28() == 167 )
      (pthread_create)(&unk_49658, 0LL, sub_19E0C, 0LL);// ADB/USB 调试环境检测
    dlclose(handle);
  }
}
```

`sub_1B924()` 是一个经过控制流扁平化处理的调度函数。剥离状态机后，它的核心工作是：

1. 使用循环 XOR 解密字符串 `libc.so` 和 `pthread_create`。
2. 调用 `dlopen("libc.so", RTLD_NOW)`。
3. 调用 `dlsym(handle, "pthread_create")`。
4. 按全局配置开关决定是否创建检测线程。

```python
__int64 __fastcall sub_CAA8()
{
  _ReadStatusReg(ARM64_SYSREG(3, 3, 13, 0, 2));
  return dword_48810;
}
bool sub_12D9C()
{
  ...
  _system_property_get("ro.product.model", haystack);
  return strstr(haystack, "Firefly-RK3399") != 0LL;
}
```

```python
__int64 __fastcall sub_CAE8()
{
  _ReadStatusReg(ARM64_SYSREG(3, 3, 13, 0, 2));
  return dword_48814;
}
```

```python
__int64 __fastcall sub_CA28()
{
  _ReadStatusReg(ARM64_SYSREG(3, 3, 13, 0, 2));
  return dword_48394;
}
```

关键线程创建条件如下：

| 条件 | 创建的线程 | 线程职责 |
|-|-|-|
| `sub_CAA8() == 248` 且设备型号不是 `Firefly-RK3399` | `sub_1C544` | Frida/注入痕迹检测 |
| `sub_CAE8() == 249` | `sub_1B8D4` | 反调试、TracerPid、线程状态检测 |
| `sub_CA28() == 167` | `sub_19E0C` | ADB/USB 调试环境检测 |

这种设计说明检测功能并非全部固定开启，而是受全局配置值控制。全局配置可能由静态数据、初始化逻辑或上层参数共同决定。

### `sub_1C544`：Frida 与注入痕迹检测线程

`sub_1C544()` 由 `sub_1CEF8()` 创建。`sub_1CEF8()` 会解析 `libart.so` 中与 `PrettyMethod` 相关的函数入口，并将该入口地址作为参数传给 `sub_1C544()`。因此 `sub_1C544()` 不只检查进程环境，也会检查 ART 函数入口是否出现可疑 prologue。

该线程的主循环可以概括为：

```
while true:
    sub_1BFAC()       // 线程名检测
    sub_1C158()       // fd 链接检测
    sub_1C26C()       // maps / agent 检测
    sub_26334(arg)    // ART 入口指令检测
    sleep(4)
```

#### `sub_1BFAC`：线程名检测

**部分恢复伪代码：**

```c
void sub_1BFAC()
{
  ...
  dir = opendir(proc_self_task);
  if ( dir )
  {
    dir_1 = dir;
    v2 = readdir(dir);
    if ( v2 )
    {
      v3 = v2;
      do                                        // 遍历所有线程
      {
        memset(&status, 0, 0x200uLL);
        d_name = v3->d_name;
        if ( strcmp(d_name, ".") )              // 过滤"."
        {
          if ( strcmp(d_name, "..") )           // 过滤".."
          {
            _snprintf_chk(
              &status,                          // 拼接得到实际/proc/self/task/%s/status
              512LL,
              0LL,
              512LL,
              proc_self_task_s_status,
              d_name);
            fd_1 = openat(-100, &status, O_CLOEXEC, 0LL);
            if ( fd_1 )
            {
              fd = fd_1;
              memset(name, 0, sizeof(name));
              for ( i = 0LL; i < 0x1FF; ++i )
              {
                if ( _read_chk(fd, s, 1LL, 1LL) != 1 )
                  break;
                if ( s[0] == '\n' )             // 只读一行
                  break;
                name[i] = s[0];                 // 读取的内容
              }
              if ( strstr(name, gum_js_loop) || strstr(name, gmain) )
                exit(0);                        // 命中 "gum-js-loop" / "gmain" 后退出
              close(fd);
            }
          }
        }
        v3 = readdir(dir_1);
      }
      while ( v3 );
    }
    closedir(dir_1);
  }
}
```

`sub_1BFAC()` 遍历 `/proc/self/task`，逐个读取线程状态文件：

```
/proc/self/task/<tid>/status
```

它重点搜索线程名中是否出现：

| 明文字符串 | 含义 |
|-|-|
| `gum-js-loop` | Frida Gum JavaScript runtime 常见线程名 |
| `gmain` | GLib main loop 线程名，Frida 环境中常见 |

命中后会调用 `exit(0)` 退出进程。这里的检测思路非常直接：**Frida 注入后通常会带来较稳定的线程名特征**，因此扫描 `/proc/self/task` 可以在无需 ptrace 的情况下发现运行时注入痕迹。

#### `sub_1C158`：fd 符号链接注入痕迹检测

**部分恢复伪代码：**

```c
void sub_1C158()
{
  ...
  dir = opendir(proc_self_fd);
  if ( dir )
  {
    dir_1 = dir;
    v2 = readdir(dir);
    if ( v2 )
    {
      v3 = v2;
      do                                        // 遍历所有fd
      {
        memset(s, 0, sizeof(s));
        memset(s_1, 0, sizeof(s_1));
        _snprintf_chk(s_1, 512LL, 0LL, 512LL, "/proc/self/fd/%s", v3->d_name);
        lstat(s_1, &buf);
        if ( (buf.st_mode & 0xF000) == 0xA000 ) // 判断是否为符号链接
        {
          readlink(s_1, s, 0x200uLL);           // 获取符号链接真实路径
          if ( strstr(s, linjector) )
            exit(0);                            // 命中 linjector 后退出
        }
        v3 = readdir(dir_1);
      }
      while ( v3 );
    }
    closedir(dir_1);
  }
}
```

`sub_1C158()` 遍历 `/proc/self/fd`，通过 `lstat` 和 `readlink` 读取文件描述符指向的真实路径。它重点搜索：

```
linjector
```

如果 fd 链接中出现该关键字，说明当前进程可能存在注入器相关文件或匿名映射痕迹，函数会直接触发退出。

#### `sub_1C26C`：maps / agent 检测

`sub_1C26C()` 的检测分为两层：第一层扫描 `/proc/self/maps`，筛选可疑映射路径；第二层打开这些映射文件，解析文件内容并搜索 Frida agent 特征。这样即使 agent 文件名被修改，只要文件内部仍保留 `_AGENT_1.0` 或 `frida-agent` 等特征，也可能被检测到。

**部分恢复伪代码：**

```c
while (1) {
    parser = operator new(0x158);
    init_parser_fields_to_zero(parser);

    filename = current_map_node->path;

    if ((sub_18774(parser, filename) & 1) == 0 ||
        (sub_18240(parser + 3, *parser) & 1) == 0) {
        break;                                  // 打开或解析文件失败
    }

    if ((sub_1806C(parser + 3, AGENT_1_0, frida_agent) & 1) != 0) {
        exit(0);                                // 命中 "_AGENT_1.0" / "frida-agent"
    }

    sub_18F0C(parser);
    operator delete(parser);
    current_map_node = sub_27B04(current_map_node);
}
```

`sub_1C26C()` 打开 `/proc/self/maps`，关注可执行映射及可疑路径。重点字符串包括：

| 字符串 | 检测意义 |
|-|-|
| `/data/local/tmp` | Android 调试、注入工具常见落点 |
| `_AGENT_1.0` | agent 标识 |
| `frida-agent` | Frida agent 典型关键词 |

这段循环中的几个辅助函数可以按下表理解：

| 函数/变量 | 语义化理解 | 说明 |
|-|-|-|
| `operator new(0x158)` | 创建文件解析上下文 | `0x158` 字节对象用于保存 fd、映射地址、ELF 解析状态等字段 |
| `sub_18774(parser, filename)` | 打开或映射目标文件 | 目标文件来自 maps 中筛出的可疑路径 |
| `sub_18240(parser + 3, *parser)` | 初始化 ELF/文件内容解析结构 | 成功后才继续搜索 agent 特征 |
| `sub_1806C(parser + 3, AGENT_1_0, frida_agent)` | 搜索 Frida agent 特征字符串 | 命中 `_AGENT_1.0` 或 `frida-agent` 后返回成功 |
| `sub_18F0C(parser)` | 清理解析上下文 | 释放 fd、mmap、缓冲区等内部资源 |
| `sub_27B04(current_map_node)` | 取下一个 maps 节点 | 类似链表/容器迭代器的 next 操作 |

因此，该函数不仅简单搜索 maps 字符串，还会结合映射文件内容检查 agent 特征。其目标是发现放在 `/data/local/tmp` 等位置的注入组件，尤其是 Frida agent 一类动态加载对象。

#### `sub_26334`：ART 函数入口 prologue 检测

**部分恢复伪代码：**

```c
void __fastcall sub_26334(_DWORD *a1)
{
  ...
  if ( a1 && (*a1 == 0x58000050 || *a1 == 0x58000051) )
    v7 = linux_eabi_syscall(__NR_exit_group, 0LL, v1, v2, v3, v4, v5, v6);
}
```

`sub_26334(a1)` 检查传入地址处的 4 字节指令。如果入口指令为以下值之一，会触发动态 `exit_group(0)`：

```
0x58000050
0x58000051
```

这类指令常见于 AArch64 上的字面量加载跳板形态，可用于识别某些 inline hook 或 trampoline。结合 `sub_1CEF8()` 传入的 ART 函数入口来看，该检测用于判断 `libart` 中关键函数是否被改写。

### `sub_1B8D4`：反调试、父进程和线程状态检测

`sub_1B8D4()` 是一个周期性反调试线程。默认轮询间隔约为 `2000000 us`，即 2 秒；如果 `sub_CB28()` 返回值大于等于 100，则使用该返回值作为轮询间隔。

**部分恢复伪代码：**

```
void __noreturn sub_1B8D4()
{
  ...
  n0x64 = sub_CB28();
  if ( n0x64 >= 100 )
    sleep_time = n0x64;
  else
    sleep_time = 2000000;
  while ( 1 )
  {
    TracerPid = sub_1AE48();                    // 读取TracerPid
    if ( TracerPid == -1 || TracerPid && (sub_1AB54(TracerPid) & 1) == 0 || sub_1B730() == 777 )
      exit_group();
    usleep(sleep_time);
  }
}
```

#### `sub_1AE48`：读取 `TracerPid`

**部分恢复伪代码：**

```c
__int64 sub_1AE48()
{
  ...
  _sprintf_chk(s, 0LL, 1024LL, proc_d_status, main_process);
  stream = fopen(s, "r");
  if ( stream )
  {
    ...
    while ( fgets(haystack, 1024, stream) )
    {
      v23 = strstr(haystack, &TracerPid);
      if ( v23 )
      {
        v24 = atoi(v23 + 10);
        if ( v24 )
        {
          v14 = v24;
          fclose(stream);
          return v14;
        }
        break;
      }
    }
    fclose(stream);
    return 0;
  }
  else
  {
    return -1;
  }
}
```

`sub_1AE48()` 打开：

```
/proc/<pid>/status
```

逐行搜索：

```
TracerPid:
```

返回语义如下：

| 返回值 | 含义 |
|-|-|
| `0` | 当前进程未被 ptrace |
| `> 0` | 当前进程正在被指定 pid ptrace |
| `-1` | status 文件打开失败，视为异常 |

`TracerPid` 是 Linux/Android 反调试中最常见的检测点之一。调试器、部分注入器或 ptrace 型保护工具都会改变该字段。

#### `sub_1AB54`：校验 `TracerPid` 的 `PPid`

**部分恢复伪代码：**

```c
int __fastcall sub_1AB54(unsigned int TracerPid)
{
  ...
  _sprintf_chk(s, 0LL, 1024LL, proc_d_status, TracerPid);
  stream_1 = fopen(s, "r");
  if ( stream_1 )
  {
    ...
      if ( !fgets(haystack, 1024, stream) )
        goto LABEL_22;
      __TracerPid_PPid = strstr(haystack, PPid);// 获取TracerPid的PPid
    }
    while ( !__TracerPid_PPid );
    if ( atoi(__TracerPid_PPid + 5) == main_process )
    {
      fclose(stream);
      LODWORD(stream_1) = 1;
      return stream_1;
    }
    fclose(stream);
    ...
  }
  return stream_1;
}
```

`sub_1AB54(tracer_pid)` 会继续读取：

```
/proc/<tracer_pid>/status
```

并搜索：

```
PPid:
```

随后将 tracer 进程的父进程 pid 与 `sub_1BEC4()` 保存的主进程 pid 比较：

| 判断 | 含义 |
|-|-|
| `PPid == 主进程 pid` | 可能是应用自身 fork 出来的 self-debugger，允许 |
| `PPid != 主进程 pid` | 更可能是外部调试器或注入器，退出 |

这个逻辑不是简单地禁止所有 `TracerPid != 0`，而是保留了 **自调试保护** 的可能性。若 tracer 是由当前主进程派生出来的子进程，函数会返回通过；否则认为调试来源异常。

#### `sub_1B730`：线程 `stat` 状态检测

**部分恢复伪代码：**

```c
__int64 sub_1B730()
{
  ...
  pid = getpid();
  _sprintf_chk(name, 0LL, 1024LL, "/proc/%d/task", pid);
  dirp = opendir(name);
  if ( !dirp )
    return 0xFFFFFFFFLL;
  dirp_1 = dirp;
  v3 = readdir(dirp);
  if ( v3 )
  {
    while ( 1 )
    {
      d_name = v3->d_name;
      v4 = v3->d_name[0];
      if ( v4 )
      {
        v6 = &v3->d_name[1];
        while ( v4 - 48 > 9 )
        {
          v7 = *v6++;
          v4 = v7;
          if ( !v7 )
            goto LABEL_14;
        }
        pid_1 = getpid();
        _sprintf_chk(s, 0LL, 512LL, "/proc/%d/task/%s/stat", pid_1, d_name);
        fd = open(s, O_RDONLY);
        if ( fd == -1 )
          return fd;
        fd_1 = fd;
        fd = _read_chk(fd, s_1, 1024LL, 1024LL);
        if ( fd == -1 )
          return fd;
        v11 = 0LL;
        do
          n41 = s_1[v11++];
        while ( n41 != ')' );
        close(fd_1);
        if ( (s_1[(v11 + 1)] | ' ') == 't' && s_1[(v11 + 2)] == ' ' )
          return 777LL;
      }
LABEL_14:
      v3 = readdir(dirp_1);
      if ( !v3 )
        goto LABEL_15;
    }
  }
  else
  {
LABEL_15:
    closedir(dirp_1);
    return 0LL;
  }
}
```

`sub_1B730()` 遍历：

```
/proc/<pid>/task/<tid>/stat
```

读取每个线程的 stat 内容，找到线程名右括号 `)` 后面的状态字段。如果状态字符为 `t` 或 `T`，返回 `777`。

在 Linux `/proc/<pid>/task/<tid>/stat` 中，`T/t` 常用于 stopped、tracing stop 等状态。该检测可用于发现线程被调试器暂停、单步或 trace 造成的异常状态。

### `sub_19E0C`：ADB/USB 调试环境检测

**部分恢复伪代码：**

```c
void __noreturn sub_19E0C()
{
  ...

  while ( 1 )
  {
    memset(&v9[1], 0, 112);
    v9[0] = *"sys.usb.config";
    ...
    _system_property_get(v9, haystack);
    if ( strstr(haystack, "adb") )
    {
      v0 = sub_17C8C();                         // 获取当前可用的 JNIEnv *
      if ( sub_19A58(v0) )                      // 通过 Android Framework API 查询 BATTERY_CHANGED sticky broadcast
        exit_group_1();
    }
    sleep(3u);
  }
}
```

`sub_19E0C()` 由 `sub_1B924()` 创建，创建条件为：

```
sub_CA28() == 167
```

线程每 3 秒读取一次系统属性：

```
__system_property_get("sys.usb.config", buf)
```

若属性值中包含 `adb`，例如：

```
adb
mtp,adb
ptp,adb
rndis,adb
```

则继续通过 JNI 判断设备是否处于插电/连接状态。

辅助函数关系如下：

| 函数 | 作用 |
|-|-|
| `sub_17C8C()` | 动态解析 `JNI_GetCreatedJavaVMs`，获取当前可用的 `JNIEnv *` |
| `sub_19A58(JNIEnv *)` | 通过 Android Framework API 查询 `BATTERY_CHANGED` sticky broadcast |

`sub_19A58()` 的 Java 层语义可以概括为：

```
ActivityThread.currentActivityThread()
  -> getApplication()
  -> registerReceiver(null, IntentFilter("android.intent.action.BATTERY_CHANGED"))
  -> Intent.getIntExtra("plugged", -1)
```

当 `plugged != 0` 时，通常表示设备正在通过 AC、USB 或无线方式供电。结合 `sys.usb.config` 中包含 `adb`，该线程试图识别 **开启 ADB 且设备正处于连接/供电状态的调试环境**。

---

## 主线二：APK 路径与签名白名单校验

APK/签名校验主线不是从 `sub_1B924()` 创建，而是从 `sub_13728()` 进入 `sub_2701C()`，再创建 `sub_26E5C()`。这条链路更偏向一次性完整性校验，而不是长期轮询。

### `sub_13728 -> sub_2701C`：签名校验线程创建入口

`sub_13728()` 中会调用 `sub_2701C()`。`sub_2701C()` 与前面的主线程调度逻辑类似，也会读取：

```
/proc/<pid>/cmdline
```

如果 cmdline 中包含冒号 `:`，说明当前可能是 `com.xxx:push`、`com.xxx:remote` 一类子进程，此时跳过 `sub_26E5C()` 创建。如果没有冒号，则动态解析 `pthread_create` 并创建：

```
pthread_create(&tid, 0, sub_26E5C, 0)
```

这样做的目的很明确：**APK 路径和签名校验只在主进程执行**，避免多进程环境中重复打开 APK、解析 ZIP 和读取签名文件。

### `sub_26E5C`：一次性 APK/签名完整性校验线程

`sub_26E5C()` 不是死循环，而是后台执行的一次性校验任务。其核心判断为：

```
n = sub_C930()

if (n < 13 && n != 0 && (sub_1678C() & 1) == 0) {
    sub_269AC(0)        // 最终执行 exit_group(0)
}
```

其中：

| 函数 | 含义 |
|-|-|
| `sub_C930()` | 返回全局白名单数量 `dword_48130` |
| `sub_1678C()` | 执行 APK 路径定位、签名文件读取、RSA 公钥 CRC 白名单校验 |
| `sub_269AC(0)` | 动态生成 syscall stub 并执行 `exit_group(0)` |

触发退出需要同时满足三个条件：

1. `sub_C930()` 返回值不为 `0`。
2. `sub_C930()` 返回值小于 `13`。
3. `sub_1678C()` 返回值 bit0 为 `0`，表示签名校验未通过。

这说明 `sub_C930()` 不只是白名单数量，也承担了签名校验开关的作用。当白名单数量为 0 时，该线程不会触发签名失败退出。

### `sub_12050`：从 cmdline 提取主包名

`sub_1678C()` 依赖 `sub_12050()` 获取当前应用主包名。`sub_12050()` 的语义如下：

```
读取 /proc/<pid>/cmdline
如果进程名包含 ":"，截断冒号后的后缀
返回主包名
```

例如：

| 原始 cmdline | `sub_12050()` 结果 |
|-|-|
| `com.xingin.xhs` | `com.xingin.xhs` |
| `com.xingin.xhs:push` | `com.xingin.xhs` |
| `com.xingin.xhs:remote` | `com.xingin.xhs` |

这个处理非常关键。APK 安装目录通常基于主包名，而 Android 子进程名会带冒号后缀。如果不截断，后续拼接 `/data/app/<package>-N/base.apk` 时会得到错误路径。

### `sub_1678C`：APK 定位、签名读取与 CRC 白名单比较

`sub_1678C()` 是 APK/签名校验链的核心函数。它并不是简单检查 APK 文件是否存在，而是执行一套较完整的签名白名单验证：

1. 获取主包名。
2. 尝试定位当前应用 APK。
3. 打开 APK/ZIP 容器。
4. 查找 v1 签名文件。
5. 读取签名文件内容。
6. 将签名文件字节转为十六进制文本。
7. 在十六进制文本中定位 RSA DER 公钥结构头。
8. 从命中位置开始取 300 字节计算 CRC32。
9. 与内置 CRC 白名单比较。

#### APK 路径定位策略

该函数先尝试旧版和常见安装路径：

```
/data/app/<package>-1.apk
/data/app/<package>-2.apk
...
/data/app/<package>-10.apk

/data/app/<package>-1/base.apk
/data/app/<package>-2/base.apk
...
/data/app/<package>-10/base.apk

/data/app/<package>-1
/data/app/<package>-2
...
/data/app/<package>-10
```

如果这些路径找不到，并且 SDK 版本大于等于 26，则扫描 `/proc/self/maps` 兜底。扫描时关注以下信息：

| 字符串 | 用途 |
|-|-|
| `/data/app/` | APK 安装路径前缀 |
| 当前包名 | 确认映射路径属于当前应用 |
| `libmsaoaidsec.so` | 从当前 so 映射路径反推 APK 所在目录 |
| `/base.apk` | 主 APK |
| `/split_config.arm64_v8a.apk` | arm64 split APK |
| `/lib` | 从 native lib 路径回退到 APK 路径时使用 |

这种兜底方式可以适配 Android 新版安装目录、split APK 和不同设备上的路径差异。

#### 签名文件与 RSA 公钥定位

APK 打开后，函数关注 v1 签名目录：

```
META-INF/
```

常见目标 entry 包括：

```
META-INF/CERT.RSA
META-INF/ANDROID.RSA
```

读取签名文件后，函数将每个字节格式化为：

```
%02x
```

也就是带空格分隔的十六进制文本。随后搜索 RSA 公钥 DER 结构头：

| DER 头十六进制文本 | 对应含义 |
|-|-|
| `30 81 89 02 81 81 00` | 常见 1024-bit RSA 公钥结构头 |
| `30 82 01 0a 02 82 01 01 00` | 常见 2048-bit RSA 公钥结构头 |
| `30 82 02 0a 02 82 02 01 00` | 常见 4096-bit RSA 公钥结构头 |

命中后执行：

```
crc = sub_16720(match_ptr, 300)
```

这里的 `match_ptr` 指向十六进制文本中的 DER 头位置，而不是原始二进制签名字节。因此 CRC 计算对象是 **签名内容的十六进制文本片段**，长度固定为 300 字节。

#### 白名单比较

白名单由两个函数提供：

| 函数 | 作用 |
|-|-|
| `sub_C930()` | 返回白名单数量 |
| `sub_C970()` | 返回白名单 CRC 数组地址 |

比较逻辑为：

```
for i in range(sub_C930()):
    if whitelist[i] == crc:
        return 1

return failure
```

因此，`sub_1678C()` 的本质不是验证整个 APK 哈希，也不是验证整个证书链，而是验证 **签名文件中 RSA 公钥附近固定片段的 CRC32 是否命中内置白名单**。这是一种轻量级签名绑定方式：只要重打包后签名公钥发生变化，CRC 大概率会变化，从而触发失败。

#### 语义化伪代码

```c
bool sub_1678C_semantic(void)
{
    for each candidate in strtok(sub_CBA8(), delim) {
        package = sub_12050();                      // /proc/<pid>/cmdline，去掉 :xxx 后缀
        apk = try_open_common_apk_paths(package);

        if (!apk && get_sdk() >= 26) {
            apk = find_apk_from_proc_self_maps(package, "libmsaoaidsec.so");
        }

        if (!apk) {
            if (get_sdk() < 19)
                return true;                        // 低版本兼容分支
            continue;
        }

        entry_name = "META-INF/" + candidate;
        if (!zip_find_entry(apk, entry_name)) {
            close_apk(apk);
            if (get_sdk() < 19)
                return true;
            continue;
        }

        raw = zip_read_entry_all(apk);
        hex = bytes_to_hex_with_space(raw);          // 每字节转为 "%02x "

        p = strstr(hex, "30 81 89 02 81 81 00");
        if (!p) p = strstr(hex, "30 82 01 0a 02 82 01 01 00");
        if (!p) p = strstr(hex, "30 82 02 0a 02 82 02 01 00");

        if (!p) {
            status = (sub_CCA4() == 217) ? -1 : 0;
        } else {
            crc = sub_16720(p, 300);
            status = crc_in_whitelist(crc, sub_C970(), sub_C930()) ? 1 : -1;
        }

        close_apk(apk);

        if (status != 0)
            return status == 1;

        if (get_sdk() < 19)
            return true;
    }

    return false;
}
```

#### 返回值语义

| 返回值语义 | 含义 | `sub_26E5C` 中的结果 |
|-|-|-|
| bit0 为 `1` | 签名 CRC 命中白名单，或低版本兼容分支放行 | 不退出 |
| bit0 为 `0` | APK 未找到、签名文件未找到、DER 头未找到、CRC 不在白名单等 | 满足开关条件时 `exit_group(0)` |

---

## 主线三：代码 CRC 完整性校验

代码 CRC 主线用于发现 Native 代码被静态 patch、运行时 inline hook 或内存改写。该主线包含两个层次：

1. **初始化期 CRC**：在 `sub_13728()` 中执行，加载早期即可发现代码段异常。
2. **周期性 CRC**：由 `sub_9150()` 创建 `sub_8CAC()` 线程，每隔约 3 秒重复校验。

### `sub_16720`：标准 CRC32 的查表实现

`sub_16720(buf, len)` 是标准 CRC32/IEEE 的查表实现。反编译语义如下：

```c
uint32_t sub_16720(uint8_t *buf, int len)
{
    uint32_t crc;

    if (!len)
        return 0;

    crc = 0xFFFFFFFF;
    while (len--) {
        crc = dword_2FAEC[(uint8_t)(crc ^ *buf++)] ^ (crc >> 8);
    }
    return ~crc;
}
```

它与常见逐 bit 写法看起来不同，是因为这里使用了 **预计算 CRC 表 `dword_2FAEC`**。两者本质一致：

```c
uint32_t crc32_bitwise(const uint8_t *data, size_t len)
{
    uint32_t crc = 0xFFFFFFFF;

    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int j = 0; j < 8; j++) {
            if (crc & 1)
                crc = (crc >> 1) ^ 0xEDB88320;
            else
                crc >>= 1;
        }
    }

    return crc ^ 0xFFFFFFFF;
}
```

区别在于：

| 实现方式 | 特点 |
|-|-|
| 逐 bit 实现 | 每个字节循环 8 次，逻辑直观 |
| 查表实现 | 每个字节查一次 256 项表，速度更快 |

`dword_2FAEC` 对应的就是由多项式 `0xEDB88320` 推导出的查表结果。因此，`sub_16720()` 可以视为标准 CRC32，而不是自定义哈希。

### `sub_13728`：初始化期代码 CRC 校验

`sub_13728()` 由 `.init_proc` 调用，是初始化期完整性链的核心函数之一。其主要动作包括：

1. 在配置满足时执行代码 CRC。
2. 调用 `sub_2701C()` 创建 `sub_26E5C()`。
3. 调用 `sub_198D8()`、`sub_25964()` 等辅助检测或初始化路径。
4. 初始化与 `libmsaoaidsec.so` 模块信息相关的数据。

初始化期 CRC 的核心条件为：

```
if (sub_CEE4() == 203) {
    crc = sub_16720(base + sub_CE24(), sub_CE64())
    if (crc != sub_CEA4())
        sub_2676C(0)
}
```

结合当前样本中的常量，可整理为：

| 项 | 值 | 说明 |
|-|-|-|
| 起始偏移 | `0x83F0` | `sub_CE24()` 返回的目标区域起始偏移 |
| 校验长度 | `0x26A04` | `dword_48840` / `sub_CE64()` 返回的长度 |
| 校验结束位置 | `0x2EDF4` | `0x83F0 + 0x26A04` |
| 期望 CRC | `0x536953F0` | `sub_CEA4()` 返回的预期值 |

关于 `LOAD:0000000000048840 dword_48840 DCD 0x26A04` 中的 `0x26A04`，它不是 CRC32 算法要求的固定长度，也不是某种通用 magic number。更合理的解释是：**该值是样本作者为当前版本选定的代码保护区间长度**。

从边界看：

```
start = 0x83F0
len   = 0x26A04
end   = 0x2EDF4
```

该范围覆盖了库内主要可执行代码区域的一大段，并在进入大量只读数据、字符串或其他不适合校验的区域前结束。这样做有几个目的：

1. **覆盖关键检测逻辑**：如果反调试、反注入或退出逻辑被 patch，CRC 很容易变化。
2. **避免易变区域**：只校验相对稳定的代码区域，减少重定位、数据段变化带来的误报。
3. **降低计算成本**：CRC32 计算较快，但固定范围仍能控制启动期开销。
4. **版本绑定**：每个 so 版本的代码布局不同，偏移、长度和期望 CRC 可以随版本更新。

因此，`0x26A04` 的原因应理解为 **代码完整性保护配置的一部分**，不是标准 CRC32 的特性。

### `sub_9150 / sub_8CAC`：周期性代码 CRC 检测线程

`sub_9150()` 负责创建周期性 CRC 线程。它同样会解密 `libc.so` 和 `pthread_create`，再通过 `dlopen` / `dlsym` 动态解析线程创建函数。

创建条件为：

```
if (sub_CDE4() == 204 || sub_CEE4() == 203) {
    pthread_create(&tid, 0, sub_8CAC, 0)
}
```

`sub_8CAC()` 的核心逻辑可以概括为：

```
while true:
    lock(module_mutex)
    module = find_module("libmsaoaidsec.so")

    if sub_CDE4() == 204:
        start = module_base + sub_CD24()
        len = sub_CD64()
        expected = sub_CDA4()
        if sub_16720(start, len) != expected:
            sub_260B0(0)

    if sub_CEE4() == 203:
        start = calculated_base + sub_CE24()
        len = sub_CE64()
        expected = sub_CEA4()
        if sub_16720(start, len) != expected:
            sub_269AC(0)

    unlock(module_mutex)
    usleep(0x2DC6C0)   // 3000000 us，约 3 秒
```

这条线程和 `sub_13728()` 的区别在于：

| 维度 | `sub_13728` | `sub_8CAC` |
|-|-|-|
| 执行时机 | 初始化期执行一次 | 后台线程周期执行 |
| 主要目的 | 尽早发现已被 patch 的代码 | 持续发现运行时 inline hook / memory patch |
| 失败处理 | `sub_2676C(0)` | `sub_260B0(0)` 或 `sub_269AC(0)` |
| CRC 函数 | `sub_16720()` | `sub_16720()` |

这说明该库同时关注 **加载时完整性** 和 **运行时完整性**。即使某些 patch 在初始化后才写入内存，也可能被 `sub_8CAC()` 后续轮询发现。

---

## 统一退出机制

该库存在多种退出路径，但最终目标基本一致：**让整个进程退出**。

| 退出路径 | 触发来源 | 退出方式 |
|-|-|-|
| `exit(0)` | `sub_1BFAC`、`sub_1C158`、`sub_1C26C` | 直接调用 libc `exit` |
| `sub_11FA4()` | `sub_1B8D4`、`sub_19E0C` | 做辅助处理后进入 `sub_234E0(0)` |
| `sub_234E0(0)` | ART hook 检测、反调试检测等 | 动态 syscall stub -> `exit_group(0)` |
| `sub_2676C(0)` | `sub_13728` 初始化期 CRC 失败 | 动态 syscall stub -> `exit_group(0)` |
| `sub_269AC(0)` | `sub_26E5C` 签名失败、`sub_8CAC` CRC 失败 | 动态 syscall stub -> `exit_group(0)` |
| `sub_260B0(0)` | `sub_8CAC` 周期 CRC 失败 | 动态 syscall stub -> `exit_group(0)` |

动态 syscall stub 的共同结构为：

```
mmap(NULL, 0x1c, PROT_READ|PROT_WRITE|PROT_EXEC, MAP_PRIVATE|MAP_ANON, -1, 0)
写入解密后的 AArch64 指令
__clear_cache()
调用该内存地址
munmap()
```

核心指令语义为：

```
mov x8, #94
svc #0
ret
```

在 ARM64 Linux/Android 上，系统调用号 `94` 对应 `exit_group`。当 `x0` 为 0 时，实际效果是：

```
exit_group(0)
```

这种写法的意义在于：退出调用不完全依赖导入表符号，也不会在所有路径上直接出现 `_exit` 或 `exit_group` 明文调用。对静态分析而言，需要把这些动态 stub 也纳入退出点统计。

---

## 检测点汇总

下表按检测对象汇总主要函数和命中结果。

| 类别 | 函数 | 检测对象 | 关键文件/API | 命中结果 |
|-|-|-|-|-|
| Frida 线程名 | `sub_1BFAC` | `gum-js-loop`、`gmain` | `/proc/self/task/<tid>/status` | `exit(0)` |
| fd 注入痕迹 | `sub_1C158` | fd 符号链接中的 `linjector` | `/proc/self/fd`、`lstat`、`readlink` | `exit(0)` |
| maps / agent | `sub_1C26C` | `/data/local/tmp`、`_AGENT_1.0`、`frida-agent` | `/proc/self/maps` | `exit(0)` |
| ART hook | `sub_26334` | 函数入口指令 `0x58000050/0x58000051` | `libart` PrettyMethod 相关入口 | `exit_group(0)` |
| TracerPid | `sub_1AE48`、`sub_1B8D4` | 当前进程是否被 ptrace | `/proc/<pid>/status` | `exit_group(0)` |
| tracer 父进程 | `sub_1AB54` | `TracerPid` 的 `PPid` 是否为主进程 | `/proc/<tracer_pid>/status` | 不匹配则退出 |
| 线程 trace 状态 | `sub_1B730` | 线程状态是否为 `t/T` | `/proc/<pid>/task/<tid>/stat` | 返回 `777` 后退出 |
| ADB/USB | `sub_19E0C`、`sub_17C8C`、`sub_19A58` | `adb` + `plugged != 0` | `sys.usb.config`、JNI、`BATTERY_CHANGED` | `exit_group(0)` |
| Magisk 环境残留 | `sub_25A48`、`sub_23B18` | 初始栈附近是否残留 `MAGISKTMP` | `/proc/self/maps`、栈顶原始字符串 | 命中后短路后续 native 检测初始化 |
| APK 签名 | `sub_26E5C`、`sub_1678C` | RSA 公钥片段 CRC 是否命中白名单 | APK/ZIP、`META-INF/*.RSA`、CRC32 | 失败则退出 |
| 初始化期代码 CRC | `sub_13728` | `base+0x83F0` 起始的 `0x26A04` 字节 | `sub_16720()` | CRC 不一致则退出 |
| 周期性代码 CRC | `sub_9150`、`sub_8CAC` | 内存中目标代码片段 | 模块基址、偏移、长度、CRC32 | CRC 不一致则退出 |

从检测覆盖面看，`libmsaoaidsec.so` 同时检查：

1. **环境痕迹**：Frida 线程名、fd、maps、agent 文件。
2. **调试状态**：`TracerPid`、tracer 父进程、线程 `t/T` 状态。
3. **反检测环境**：初始栈中是否残留 `MAGISKTMP` 等 Magisk 环境痕迹。
4. **设备连接状态**：ADB 属性和电池 plugged 状态。
5. **安装包可信度**：APK 路径、v1 签名文件、公钥 CRC 白名单。
6. **Native 代码完整性**：初始化期和周期性代码 CRC。

---

## 结论

`libmsaoaidsec.so` 的检测体系可以理解为一套分层 Native 防护：

1. **入口层**通过 `.init_proc(0x14400)` 在 Java 层业务逻辑运行前启动检测，而真实 `JNI_OnLoad(0x13A4C)` 并不是主要检测线程的直接创建点。
2. **早期反检测检测层**由 `sub_25A48 -> sub_23B18` 完成，命中 `MAGISKTMP` 后更像风险打标或降级入口，会使 `.init_proc` 短路后续 native 检测初始化，而不是直接退出。
3. **线程调度层**由 `sub_1BEC4 -> sub_1B924` 创建多个后台检测线程，分别覆盖 Frida/注入、ptrace 调试、线程异常状态和 ADB/USB 调试环境。
4. **签名校验层**由 `sub_13728 -> sub_2701C -> sub_26E5C -> sub_1678C` 完成，核心是对 APK v1 签名文件中的 RSA 公钥片段计算 CRC32，并与内置白名单比较。
5. **代码完整性层**由 `sub_13728` 和 `sub_8CAC` 共同完成，前者做初始化期 CRC，后者做周期性 CRC，用于发现静态 patch 和运行时内存改写。
6. **退出层**通过直接 `exit(0)` 和动态生成 `exit_group(0)` syscall stub 两类方式终止进程，检测失败通常不会向上层返回可恢复错误。

---

# 回复

## 回复 by jyotidwi (#2)

*2026-5-28 22:40*

tql

## 回复 by mb_sysjgaug (#3)

*2026-5-28 22:43*

11

## 回复 by mb_osxdmntv (#4)

*2026-5-28 23:10*

666

## 回复 by Imxz (#5)

*2026-5-29 09:06*

tql

## 回复 by huangjw (#6)

*2026-5-29 09:44*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by 钱钱钱￥ (#7)

*2026-5-29 09:53*

666

## 回复 by 4Chan (#8)

*2026-5-29 09:57*

学习一下

## 回复 by tonykros (#9)

*2026-5-29 10:08*

666

## 回复 by Zepp7289 (#10)

*2026-5-29 10:33*

tql

## 回复 by fjqisba (#11)

*2026-5-29 10:33*

777

## 回复 by mb_xjdhrmck (#12)

*2026-5-29 10:37*

88888

## 回复 by XiaozaYa (#13)

*2026-5-29 10:46*

1

## 回复 by guijingwen (#14)

*2026-5-29 11:21*

66

## 回复 by 海带 (#15)

*2026-5-29 12:30*

6666

## 回复 by 墨穹呢 (#16)

*2026-5-29 12:57*

有样本吗？

## 回复 by wx_wyx (#17)

*2026-5-29 13:44*

66666

## 回复 by 芃杉 (#18)

*2026-5-29 14:13*

666

## 回复 by wangzehua (#19)

*2026-5-29 14:42*

只有magisk? 没kernelSu那些吗？

## 回复 by xingbing (#20)

*2026-5-29 16:07*

学习一下

## 回复 by yangshuang (#21)

*2026-5-29 16:58*

学习一下

## 回复 by 爬下全世界 (#22)

*2026-5-29 17:07*

daniu

## 回复 by LuisY (#23)

*2026-5-29 17:09*

那如何绕过libmsao 有系统性的文章讲解吗 ？

## 回复 by mb_jhohnbzu (#24)

*2026-5-29 17:32*

666

## 回复 by XCicada (#25)

*2026-5-29 18:02*

tql

## 回复 by niceday (#26)

*2026-5-29 18:10*

感谢分享

## 回复 by kingking888 (#27)

*2026-5-29 23:01*

666

## 回复 by xianhuimin (#28)

*2026-5-30 02:47*

666

## 回复 by 奋斗的小趴菜 (#29)

*2026-5-30 10:30*

1

## 回复 by xiusi (#30)

*2026-5-30 13:07*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  墨穹呢](https://bbs.kanxue.com/user-886838.htm)
>  有样本吗？
>

某红薯的lib里就有

## 回复 by xiusi (#31)

*2026-5-30 15:46*

>
> [LuisY](https://bbs.kanxue.com/user-1000037.htm)
>  那如何绕过libmsao 有系统性的文章讲解吗 ？
>

https://bbs.kanxue.com/thread-291403.htm

## 回复 by mb_euhyowpw (#32)

*2026-5-30 16:16*

111

## 回复 by mb_uoktlvrn (#33)

*2026-6-1 08:59*

tql

## 回复 by pan_634488 (#34)

*2026-6-1 09:19*

666

## 回复 by iBa0 (#35)

*2026-6-1 16:53*

123

## 回复 by MaYil (#36)

*2026-6-1 19:46*

感谢分享

## 回复 by mb_elqwyvnm (#37)

*2026-6-1 23:20*

不错的

## 回复 by tigericon (#38)

*2026-6-2 14:13*

66

## 回复 by 086Love (#39)

*2026-6-2 17:15*

学习一下

## 回复 by 随风而行aa (#40)

*2026-6-2 17:50*

看看

## 回复 by mb_uvyukvot (#41)

*2026-6-2 18:36*

666

## 回复 by mb_vrkpxsoe (#42)

*2026-6-2 19:16*

66

## 回复 by x0rrrrr (#43)

*2026-6-3 11:15*

他的这个crc的检测真的有调用吗，我hook了crc这个函数但是没见有调用![image](https://bbs.kanxue.com/view/img/face/029.gif)

## 回复 by PPTV (#44)

*2026-6-3 12:42*

libmsaoaidsec.so 检测体系分析

## 回复 by Mr.He (#45)

*2026-6-3 14:29*

666

## 回复 by mb_lfwgtxdb (#46)

*2026-6-4 12:44*

666

## 回复 by mb_elytixax (#47)

*2026-6-4 14:03*

学习

## 回复 by snowflake911 (#48)

*2026-6-4 15:24*

![image](https://bbs.kanxue.com/view/img/face/038.gif)

## 回复 by Rocky虞 (#49)

*2026-6-4 18:22*

666

## 回复 by xiusi (#50)

*2026-6-5 00:03*

>
> [x0rrrrr](https://bbs.kanxue.com/user-999665.htm)
>  他的这个crc的检测真的有调用吗，我hook了crc这个函数但是没见有调用[em_029]
>

https://bbs.kanxue.com/thread-291403.htm
有的，没调用那只是厂商没启用这个检测而已

## 回复 by GEKEZYX (#51)

*2026-6-5 00:18*

666

## 回复 by mb_pcnicgfm (#52)

*2026-6-5 10:48*

666

## 回复 by x0rrrrr (#53)

*2026-6-5 14:13*

>
> [xiusi](https://bbs.kanxue.com/user-1036360.htm)
>  https://bbs.kanxue.com/thread-291403.htm
> 有的，没调用那只是厂商没启用这个检测而已
>

原来是这样吗![image](https://bbs.kanxue.com/view/img/face/063.gif)

## 回复 by ugui (#54)

*2026-6-5 22:51*

0.0

## 回复 by bedaway (#55)

*2026-6-6 00:36*

666

## 回复 by mb_nggigxxl (#56)

*2026-6-6 01:37*

666

## 回复 by 简单的简单 (#57)

*2026-6-6 03:19*

666

## 回复 by Mr.ChenX (#58)

*2026-6-6 11:07*

666

## 回复 by AK1988DA (#59)

*2026-6-6 17:24*

999

## 回复 by issio (#60)

*2026-6-6 19:56*

帖子还活着, 看来

## 回复 by FloatGuy (#61)

*2026-6-6 20:44*

666

## 回复 by Little_Z (#62)

*2026-6-6 23:47*

666

## 回复 by mb_dcjxxhsk (#63)

*2026-6-7 08:53*

666

## 回复 by Snark (#64)

*2026-6-7 14:08*

111

## 回复 by git_87237minhdanhsc (#65)

*2026-6-8 00:04*

1

## 回复 by gzzchh (#66)

*2026-6-8 02:41*

为你点赞！

## 回复 by mb_bhmtpskk (#67)

*2026-6-8 09:44*

6666学习一下

## 回复 by Da_ (#68)

*2026-6-8 11:31*

tql

## 回复 by mb_czqyztmr (#69)

*2026-6-8 15:38*

666

## 回复 by mb_kbagkani (#70)

*2026-6-9 14:36*

学习一下

## 回复 by Kevin_ZZZ (#71)

*2026-6-10 17:42*

感谢分享

## 回复 by mb_dtcxfgwm (#72)

*2026-6-10 19:22*

感谢分享

## 回复 by win柠初 (#73)

*2026-6-10 19:41*

666

## 回复 by 五彩斑斓的黑 (#74)

*2026-6-11 00:36*

tql

## 回复 by hyz111 (#75)

*2026-6-11 11:52*

tqp

## 回复 by mb_lhxrckiu (#76)

*2026-6-11 15:22*

看看

## 回复 by mb_dcxmjpuj (#77)

*2026-6-16 12:06*

1

## 回复 by ldehua (#78)

*2026-6-17 10:09*

感谢你分享这么好的资源

## 回复 by gannicusliu (#79)

*2026-6-17 11:44*

这个够详细

## 回复 by secflag (#80)

*2026-6-17 12:16*

学习一下

## 回复 by git_27068Lych1e1 (#81)

*2026-6-18 01:40*

666

## 回复 by Zireael (#82)

*2026-6-18 02:22*

666

## 回复 by cpannn (#83)

*2026-6-18 19:35*

牛人

## 回复 by 我不是卷王 (#84)

*2026-6-18 21:33*

6

## 回复 by 飆汗吉米 (#85)

*2026-6-18 23:14*

666

## 回复 by 4ak5ra (#86)

*2026-6-21 15:41*

学习一下

## 回复 by zzhone (#87)

*2026-6-21 20:35*

666

## 回复 by mb_ajxntfzc (#88)

*2026-6-22 02:44*

6666

## 回复 by git_56402Syy040316 (#89)

*2026-6-22 14:06*

666

## 回复 by ulong9527 (#90)

*2026-6-26 09:42*

感谢分享，学习一下

## 回复 by 信心风暴 (#91)

*2026-6-27 06:55*

Mark

## 回复 by mb_qimctavn (#92)

*2026-6-27 07:06*

6

## 回复 by 孤独的小木虫 (#93)

*2026-6-30 14:07*

tql

## 回复 by mb_zfnetraa (#94)

*2026-6-30 19:53*

学习一下

## 回复 by wx_筟鈈疋 (#95)

*2026-7-1 17:10*

666

## 回复 by mb_paopxhtx (#96)

*2026-7-1 20:04*

666

## 回复 by mb_fuiuugpi (#97)

*2026-7-3 02:39*

000

## 回复 by wx_飞_847 (#98)

*2026-7-4 18:21*

666

## 回复 by hyperchem (#99)

*2026-7-4 20:19*

感谢

## 回复 by hyperchem (#100)

*2026-7-4 20:21*

能给一份样本不

## 回复 by mb_cbgtaveo (#101)

*2026-7-5 00:07*

666666666666

## 回复 by 奋斗der小鸟 (#102)

*2026-7-5 15:32*

![image](https://bbs.kanxue.com/view/img/face/057.gif)

## 回复 by mJqalJqN (#103)

*2026-7-5 21:04*

1

## 回复 by mJqalJqN (#104)

*2026-7-5 21:04*

1

## 回复 by mb_kgneopde (#105)

*2026-7-6 15:21*

666

## 回复 by mb_ulozvsrv (#106)

*2026-7-6 17:56*

666666

## 回复 by sffool (#107)

*2026-7-7 10:55*

666nb

## 回复 by mb_ysikfhxt (#108)

*2026-7-7 11:07*

111

## 回复 by wx_Riham、 (#109)

*2026-7-8 18:23*

666

## 回复 by mb_hktfsykj (#110)

*2026-7-8 21:10*

99

## 回复 by wx_kx92911 (#111)

*2026-7-9 10:04*

感谢分析

## 回复 by mb_ugnawvja (#112)

*2026-7-9 11:18*

tql

## 回复 by SomeMx (#113)

*2026-7-9 11:53*

学习

## 回复 by lotus* (#114)

*2026-7-10 14:03*

66666

## 回复 by mb_wjytplsl (#115)

*2026-7-14 11:05*

666

## 回复 by 3cly (#116)

*2026-7-14 14:40*

1

## 回复 by mb_degalzhb (#117)

*2026-7-15 14:34*

666

## 回复 by mb_ohctzvjg (#118)

*2026-7-16 10:35*

tql

## 回复 by wx_杨杰_424 (#119)

*2026-7-17 08:09*

tql

## 回复 by mb_nkjfyhkg (#120)

*2026-7-20 03:14*

mark

## 回复 by totaldark (#121)

*2026-7-20 07:50*

666

## 回复 by 学计算机睡觉 (#122)

*2026-7-21 16:37*

tql

## 回复 by mb_rxgpbdxs (#123)

*2026-7-21 22:15*

1

## 回复 by hanjiefang (#124)

*2026-7-22 13:33*

666

## 回复 by mb_qztkkwxt (#125)

*2026-7-23 09:33*

666

## 回复 by Yuuuual (#126)

*2026-7-23 13:39*

学习记录，感谢分享

## 回复 by mb_akzdpbgl (#127)

666666

## 回复 by scllqk (#128)

学习

## 回复 by mb_irhdtnzm (#129)

1
