---
title: '[原创]Radare2 AI Bridge 安卓应用'
url: https://bbs.kanxue.com/thread-289945.htm
tid: 289945
author: 财神爷999
date: '2026-02-04'
tags: [Android安全, 原创, 逆向分析, NDK分析, 混淆加固, 脱壳反混淆, 漏洞相关, 程序开发, HOOK注入, 工具脚本]
crawled_at: '2026-08-08T10:26:21+00:00'
replies: 27
---

##本项目完全使用AI控制开发
 ![image](https://bbs.kanxue.com/upload/attach/202602/881104_NSWAYJMWN9GFM89.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202602/881104_9BP7DWR58FPUXMB.webp)

##  核心特性

- ✅ **命令行集成**: 通过 JNI 包装 Radare2 CLI（避免复杂的头文件依赖）
- ✅ **前台服务**: 后台运行 Ktor HTTP 服务器 (端口 5050)
- ✅ **MCP 协议**: JSON-RPC 2.0 实现，20 个 Radare2 + OS 工具
- ✅ **并发管理**: 16 桶锁机制，支持多客户端
- ✅ **Material 3 UI**: Jetpack Compose 现代界面
- ✅ **零头文件依赖**: 简化的 CMake 配置

## 技术栈

- **Kotlin 1.9.22** - 主要编程语言
- **Jetpack Compose** - UI 框架
- **Ktor 3.0** - HTTP 服务器
- **Kotlinx Serialization** - JSON 序列化
- **JNI** - C++/Kotlin 桥接
- **CMake** - 原生代码构建
- **Radare2** - 逆向引擎

## MCP 工具列表

服务器在 `0.0.0.0:5050` 端点暴露以下 28 个 MCP 工具：

### 1. r2_open_file

打开文件并执行基础分析 (默认 a 基础分析)。

**参数:**

- `file_path` (string) - 要分析的文件路径
- `auto_analyze` (boolean, optional) - 是否自动执行基础分析 (默认 true)

**返回:**

- 会话 ID 和文件基本信息

### 2. r2_analyze_file

执行深度分析 (aaa, 耗时较长)。

**参数:**

- `file_path` (string) - 要分析的文件路径

**返回:**

- 分析结果和文件信息

### 3. r2_analyze_target

智能分析策略 (精准下刀)。

**策略说明:**

- `basic` (aa): 基础分析，识别符号和入口点
- `blocks` (aab): 分析基本块结构，修复函数截断问题
- `calls` (aac): 递归分析函数调用，发现未识别的子函数
- `refs` (aar): 分析数据引用，识别字符串引用和全局变量
- `pointers` (aad): 分析数据段指针，用于C++虚表和跳转表恢复
- `full` (aaa): 全量深度分析（耗时极长，仅在小文件或必要时使用）

**参数:**

- `strategy` (string) - 分析策略模式
- `address` (string, optional) - 指定分析的起始地址或符号

**返回:**

- 分析结果和状态反馈

### 4. r2_run_command

执行 R2 命令 (通用)。

**参数:**

- `session_id` (string) - 会话 ID
- `command` (string) - Radare2 命令

**返回:**

- 命令执行结果

### 5. r2_config_manager

配置管理 (动态调整分析参数)。

**参数:**

- `session_id` (string) - 会话 ID
- `configs` (object) - 配置参数键值对

**返回:**

- 配置更新结果

### 6. r2_analysis_hints

分析提示 (手动修正分析错误)。

**参数:**

- `session_id` (string) - 会话 ID
- `hint_type` (string) - 提示类型
- `address` (string) - 目标地址
- `data` (string, optional) - 提示数据

**返回:**

- 提示应用结果

### 7. r2_list_functions

列出函数列表。

**参数:**

- `session_id` (string) - 会话 ID
- `filter` (string, optional) - 函数名过滤器
- `limit` (integer, optional) - 最大返回数量 (默认 500)

**返回:**

- 函数列表

### 8. r2_list_strings

列出字符串 (逆向第一步)。

**参数:**

- `session_id` (string) - 会话 ID
- `mode` (string, optional) - 搜索模式 ('data' 或 'all')
- `min_length` (integer, optional) - 最小字符串长度 (默认 5)

**返回:**

- 字符串列表

### 9. r2_get_xrefs

获取交叉引用 (逻辑追踪)。

**参数:**

- `session_id` (string) - 会话 ID
- `address` (string) - 目标地址或函数名
- `direction` (string, optional) - 引用方向 ('to' 或 'from')
- `limit` (integer, optional) - 最大返回数量 (默认 50)

**返回:**

- 交叉引用列表

### 10. r2_manage_xrefs

管理交叉引用 (手动修复)。

**参数:**

- `session_id` (string) - 会话 ID
- `action` (string) - 操作类型 ('add' 或 'remove')
- `from` (string) - 源地址
- `to` (string) - 目标地址

**返回:**

- 操作结果

### 11. r2_get_info

获取文件详细信息。

**参数:**

- `session_id` (string) - 会话 ID
- `detailed` (boolean, optional) - 是否显示详细信息 (默认 false)

**返回:**

- 文件信息

### 12. r2_decompile_function

反编译函数。

**参数:**

- `session_id` (string) - 会话 ID
- `address` (string) - 函数地址

**返回:**

- 反编译代码

### 13. r2_disassemble

反汇编代码。

**参数:**

- `session_id` (string) - 会话 ID
- `address` (string) - 起始地址 (十六进制)
- `lines` (integer, optional) - 反汇编行数 (默认 10)

**返回:**

- 反汇编输出

### 14. r2_test

测试 R2 库状态 (诊断)。

**参数:**

- 无

**返回:**

- 测试结果

### 15. r2_close_session

关闭会话。

**参数:**

- `session_id` (string) - 会话 ID

**返回:**

- 关闭确认

### 16. os_list_dir

列出目录内容 (支持 Root)。

**参数:**

- `path` (string) - 目标文件夹的绝对路径

**返回:**

- 目录内容列表，包含文件类型和大小

### 17. os_read_file

读取文件内容 (支持 Root)。

**参数:**

- `path` (string) - 目标文件的绝对路径

**返回:**

- 文件内容（自动截断大文件以防 OOM）

### 18. termux_command

Termux 环境命令 (AI 沙盒)。

**参数:**

- `command` (string) - 要执行的命令

**返回:**

- 命令执行结果

### 19. termux_save_script

保存代码 (赋权/所有者)。

**参数:**

- `script` (string) - 脚本内容
- `path` (string) - 保存路径

**返回:**

- 保存结果

### 20. sqlite_query

SQL 查询 (读取私有数据库)。

**参数:**

- `db_path` (string) - 数据库文件路径
- `query` (string) - SQL 查询语句

**返回:**

- 查询结果

### 21. read_logcat

读取 Android 系统日志 (Logcat)。

**参数:**

- `filter` (string, optional) - 日志过滤器
- `lines` (integer, optional) - 读取行数 (默认 100)

**返回:**

- 日志内容

### 22. rename_function

智能重命名函数 (语义理解)。

**参数:**

- `session_id` (string) - 会话 ID
- `address` (string) - 函数地址
- `new_name` (string) - 新函数名

**返回:**

- 重命名结果

### 23. simulate_execution

模拟执行 (ESIL 沙盒)。

**参数:**

- `session_id` (string) - 会话 ID
- `address` (string) - 起始地址
- `steps` (integer, optional) - 执行步数 (默认 100)

**返回:**

- 执行结果和状态

### 24. add_knowledge_note

持久化知识库 (记录重要发现)。

**参数:**

- `note` (string) - 知识库笔记内容
- `category` (string, optional) - 分类标签

**返回:**

- 保存结果

### 25. batch_decrypt_strings

批量解密字符串对抗混淆。

**参数:**

- `session_id` (string) - 会话 ID
- `method` (string) - 解密方法
- `params` (object, optional) - 解密参数

**返回:**

- 解密结果

### 26. scan_crypto_signatures

扫描加密签名识别算法。

**参数:**

- `session_id` (string) - 会话 ID
- `address` (string, optional) - 扫描起始地址

**返回:**

- 加密算法识别结果

### 27. apply_hex_patch

对指定地址应用二进制 Patch。

**参数:**

- `session_id` (string) - 会话 ID
- `address` (string) - 目标地址
- `patch` (string) - 十六进制补丁数据

**返回:**

- 补丁应用结果

### 28. find_jni_methods

列出所有的 JNI 接口函数。

**参数:**

- `session_id` (string) - 会话 ID

**返回:**

- JNI 方法列表

## API 端点

### POST /mcp

MCP JSON-RPC 2.0 端点

**请求示例 - 列出工具:**

\```
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}
\```

**请求示例 - 调用工具:**

\```
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "r2_analyze_file",
    "arguments": {
      "file_path": "/sdcard/binary.elf"
    }
  }
}
\```

### GET /health

健康检查端点，返回 "R2 MCP Server Running"

[详情访问GITHUB](https://github.com/muort521/R2AIBridge)

---

# 回复

## 回复 by 随风而行aa (#2)

*2026-2-5 15:48*

看看

## 回复 by mb_ztqcemce (#3)

*2026-2-6 09:40*

看看检查

## 回复 by CheRevir (#4)

*2026-2-6 10:56*

666

## 回复 by wx_Huber Barrientos (#5)

*2026-2-6 23:14*

666

## 回复 by csy999 (#6)

*2026-2-7 00:16*

66666

## 回复 by maarek (#7)

*2026-2-8 00:06*

wow nice

## 回复 by mb_qimctavn (#8)

*2026-2-9 12:58*

6

## 回复 by mb_ijumdife (#9)

*2026-2-10 08:50*

666

## 回复 by qig (#10)

*2026-2-11 18:23*

看看

## 回复 by uni7corn (#11)

*2026-2-12 11:47*

看看

## 回复 by Ankeys (#12)

*2026-2-13 17:29*

还以为是原本DeepSeek app支持mcp了...

## 回复 by MaYil (#13)

*2026-2-13 18:00*

感谢分享

## 回复 by rikthhpgf (#14)

*2026-2-13 19:31*

感谢分享

## 回复 by mb_sdvjpqrb (#15)

*2026-2-23 20:10*

谢谢分享

## 回复 by Kill_Log (#16)

*2026-3-4 20:33*

6666

## 回复 by mb_ghcouuzx (#17)

*2026-3-9 19:13*

看看

## 回复 by mb_hcqpswwu (#18)

*2026-3-14 02:33*

看看

## 回复 by 小迷糊ddd (#19)

*2026-4-7 09:15*

感谢分享，受教了。

## 回复 by mb_avxnjzyi (#20)

*2026-4-8 01:49*

感谢，很有用

## 回复 by mb_uktygsmq (#21)

*2026-4-8 02:51*

666

## 回复 by tjytjy (#22)

*2026-4-10 16:05*

66

## 回复 by k4y0z (#23)

*2026-4-10 16:22*

666

## 回复 by 勒LI (#24)

*2026-4-11 09:52*

6666

## 回复 by vdaoren (#25)

*2026-4-12 11:11*

![image](https://bbs.kanxue.com/view/img/face/039.gif)

## 回复 by mb_ggnlrzcs (#26)

*2026-4-12 12:00*

双击6666

## 回复 by mb_suajmqsa (#27)

*2026-6-29 11:07*

66666

## 回复 by Snowman_Liam (#28)

*2026-6-29 12:05*

6666
