---
title: '[原创] 还原shc编译的shell脚本'
url: https://bbs.kanxue.com/thread-287439.htm
tid: 287439
author: LeoW丨
date: '2025-07-01'
tags: [Android安全, 原创, 逆向分析, 混淆加固]
crawled_at: '2026-07-31T14:08:08+08:00'
replies: 0
---

最近在逆向一款android上的改机工具，发现它使用到了shc，将核心的改机逻辑隐藏了起来，没有搜索到相关的教程，分享一下“解密”的过程

## 介绍shc

[shc](https://github.com/neurobin/shc) 一款开源的工具，可以借助c语言将shell编译为可执行程序

逻辑

![image](https://bbs.kanxue.com/upload/attach/202507/889798_WDVZW7YJ6VTR9E4.webp)

shc处理后的逻辑会通过execvp两次执行可执行文件，**在第二次中，才会解密为原始的shell字符串**，再执行此shell

## 提取shell

既然知道了在execvp执行后，第二次可以获取到第一次设置的环境变量后，才会解密，那么就可以直接在第二次的`memcpy()`位置下断点，打印出原始的shell文本，具体如下：

1. 使用lldb或者gdb，对shc编译后的executable进行动态调试，我是使用ndk提供的lldb调试的

| 12 | `$ adb push ndk/...``/aarch64/lldb-server` `/data/local/tmp``$ adb forward tcp:1234 tcp:1234` |
|-|-|

android:

| 1 | `$ .``/lldb-server` `platform  --listen``"*:1234"` `--server` |
|-|-|

mac:

| 1 | `$ adb forward tcp:1234 tcp:1234` |
|-|-|

mac:

| 1234567 | `$ lldb``$ platform``select` `remote-android``$ platform connect connect:``//localhost``:1234``$``file` `shced_executable``$ b main``$ b memcpy``$ r` |
|-|-|

因为execvp会将目标的进程替换为现在运行的进程，执行execvp后保持相同的pid，因此无论是否是第一次执行，调试器都可以调试到

对main函数和ida显示调用memcpy处下端点，ida中显示的可能不是`memcpy()`，可能像下面的函数调用：

((void (__fastcall *)(const char *, void *, signed __int64))qword_4002B0[0])(v3 + 4096, &unk_4A0255, 1930LL);  // `memcpy()`需要定位一下，在 `memcmp()` 下一段，就是了

2. 内存读取字符串

调试时，调试器会多次自动断点，保险起见，每次断点都在memcpy处下断点

打印`memcpy()`的第二个参数，读取内存即可获取到内存hex

```
memory read ${x1} --count ${x2} -f y --force --outfile ${output_file}
```

3. 处理output_file

读取出的output_file是字符串，将其中的字节拼接，使用utf-8编码，即获取到原始的shell脚本，使用以下的py脚本可以实现这个转换

| 12345678910111213141516171819202122232425 | `def` `read_and_decode_file():``# 读取文件``with``open``(``'yyuj_shell.txt'``,``'r'``) as``file``:``s``=` `file``.read()` `s_arr``=` `s.split(``' '``)` `# 拼接字节``byte_list``=` `[]``for` `b``in` `s_arr:``if` `not` `b:``# skip empty strings``continue``hex_str``=` `'0x'` `+` `b``byte``=` `int``(hex_str,``16``)``byte_list.append(byte)` `# 转换为bytes对象``data3``=` `bytes(byte_list)` `# 使用utf-8解码``try``:``s3``=` `data3.decode(``'utf-8'``)``print``(s3)``except` `UnicodeDecodeError as e:``print``(f``"Error decoding UTF-8: {e}"``)` |
|-|-|
