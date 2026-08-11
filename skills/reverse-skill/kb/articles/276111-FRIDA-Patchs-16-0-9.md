---
title: '[原创]FRIDA Patchs 16.0.9'
url: https://bbs.kanxue.com/thread-276111.htm
tid: 276111
author: .KK
date: '2023-02-15'
tags: [Android安全, 原创, 基础理论, 系统相关, 源码框架, 工具脚本]
crawled_at: '2026-08-11T08:48:52+00:00'
replies: 27
---

# FRIDA Patchs 16.0.9

---

# # 其他版本需要修改编译版本号及对应 NDK 版本，还有代理地址

| 12 | `# 14.2.17``sudo apt``-``get update && sudo apt``-``get install` `-``y build``-``essential curl git lib32stdc``+``+``-``9``-``dev libc6``-``dev``-``i386 nodejs npm python3``-``dev python3``-``pip && git config` `-``-``global` `http.proxy` `"http://192.168.1.6:7890"` `&& git config` `-``-``global` `https.proxy` `"https://192.168.1.6:7890"` `&& git clone` `-``b` `14.2``.``17` `-``-``recurse``-``submodules https:``/``/``github.com``/``frida``/``frida.git && wget https:``/``/``dl.google.com``/``android``/``repository``/``android``-``ndk``-``r22b``-``linux``-``x86_64.``zip` `&& unzip android``-``ndk``-``r22b``-``linux``-``x86_64 && export ANDROID_NDK_ROOT``=``/``home``/``k``/``Desktop``/``android``-``ndk``-``r22b && export PATH``=``$ANDROID_NDK_ROOT:$PATH && source ~``/``.bashrc && cd frida && make && python3 releng``/``generate``-``version``-``header.py` `"build/frida-version.h"` `&& make core``-``android``-``arm64 && ls` `-``alith build``/``frida``-``android``-``arm64``/``bin``/` |
|-|-|

| 12 | `# 最版本编译（16.0.9）``sudo apt``-``get update && sudo apt``-``get install` `-``y build``-``essential curl git lib32stdc``+``+``-``9``-``dev libc6``-``dev``-``i386 nodejs npm python3``-``dev python3``-``pip && git config` `-``-``global` `http.proxy` `"http://192.168.1.6:7890"` `&& git config` `-``-``global` `https.proxy` `"https://192.168.1.6:7890"` `&& git clone` `-``-``recurse``-``submodules https:``/``/``github.com``/``frida``/``frida.git && wget https:``/``/``dl.google.com``/``android``/``repository``/``android``-``ndk``-``r25c``-``linux.``zip` `&& unzip android``-``ndk``-``r25c``-``linux.``zip` `&& export ANDROID_NDK_ROOT``=``/``home``/``k``/``Desktop``/``android``-``ndk``-``r25c && export PATH``=``$ANDROID_NDK_ROOT:$PATH && cd frida && make core``-``android``-``arm64` |
|-|-|

 ![代理](https://bbs.kanxue.com/upload/tmp/918604_RMNR69YBBR7KR3D.png)

 16.0.9 需要代理才能一遍过，在编译过程中会访问一个链接

# 安装 vscode

| 1 | `sudo snap install code` `-``-``classic && cd ~``/``Desktop``/``frida && code .` |
|-|-|

| 12 | `sudo snap install code` `-``-``classic` `# vscode 安装``code .` `# vscode 打开当前目录` |
|-|-|

# huluwa Patch 姿势

这里修改的主要目录是 `frida/frida-core` 中的相关文件
https://github.com/hluwa/Patchs huluwa Patchs 似乎最新能支持15.1.25

| 1234567891011121314 | `# 如果你编译的版本与之 Patch 支持版本相符 则可以使用该命令进行一键 Patch` `git config` `-``-``global` `user.email` `"you@example.com"`  `# 配置 git 信息``git config` `-``-``global` `user.name` `"Your Name"` `cd ~``/``Desktop``git clone https:``/``/``github.com``/``AAAA``-``Project``/``Patchs.git` `# 克隆 huluwa Patch``cd frida``/``frida``-``core``/`                                  `# 进入 FRIDA 源码目录``git am ..``/``..``/``Patchs``/``strongR``-``frida``/``frida``-``core``/``*``.patch` `# 合并所有 Patch``cd ..` `# 回到 FRIDA 根目录``mark core``-``android``-``arm64` `# 开始编译` `# 一键使用``git config` `-``-``global` `user.email` `"you@example.com"` `&& git config` `-``-``global` `user.name` `"Your Name"` `&& cd ~``/``Desktop && git clone https:``/``/``github.com``/``AAAA``-``Project``/``Patchs.git && cd frida``/``frida``-``core``/` `&& git am ..``/``..``/``Patchs``/``strongR``-``frida``/``frida``-``core``/``*``.patch && cd .. && mark core``-``android``-``arm64` |
|-|-|

# huluwa Patch 解析

GLib 源码下载：<http://ftp.gnome.org/pub/gnome/sources/glib/>

 GLib 帮助文档：<https://docs.gtk.org/glib/func.base64_decode.html>

## 字符串 frida:rpc

| 12345 | `-`    `.add_string_value (``"frida:rpc"``)``+`    `.add_string_value ((string) GLib.Base64.decode(``"ZnJpZGE6cnBj="``))` `-`    `if` `(json.index_of (``"\"frida:rpc\""``)` `=``=` `-``1``)``+`    `if` `(json.index_of ((string) GLib.Base64.decode(``"ImZyaWRhOnJwYyI="``))` `=``=` `-``1``)` |
|-|-|

## 字符串 linjector

| 12 | `-`  `self``-``>fifo_path` `=` `g_strdup_printf (``"%s/linjector-%u"``,` `self``-``>temp_path,` `self``-``>``id``);``+`  `self``-``>fifo_path` `=` `g_strdup_printf (``"%s/%p%u"``,` `self``-``>temp_path,` `self` `,``self``-``>``id``);` |
|-|-|

## 字符串 frida-agent

| 1234567891011 | `-`            `agent` `=` `new AgentDescriptor (PathTemplate (``"frida-agent-<arch>.so"``),``+`            `var random_prefix` `=` `GLib.Uuid.string_random();` `/``/` `随机前缀``+`            `agent` `=` `new AgentDescriptor (PathTemplate (random_prefix` `+` `"-<arch>.so"``),``new Bytes.static (blob32.data),``new Bytes.static (blob64.data),``new AgentResource[] {``-`                    `new AgentResource (``"frida-agent-arm.so"``, new Bytes.static (emulated_arm.data), tempdir),``-`                    `new AgentResource (``"frida-agent-arm64.so"``, new Bytes.static (emulated_arm64.data), tempdir),``+`                    `new AgentResource (random_prefix` `+` `"-arm.so"``, new Bytes.static (emulated_arm.data), tempdir),` `/``/` `去除frida``-``agent特征``+`                    `new AgentResource (random_prefix` `+` `"-arm64.so"``, new Bytes.static (emulated_arm64.data), tempdir),``},` |
|-|-|

## 字符串 frida_agent_main

| 12345678910111213141516171819202122232425262728293031323334353637383940 | `/``/` `修改所有` `"frida_agent_main"` `字符串为` `"main"``-`            `var main_func_found` `=` `container.module.symbol (``"frida_agent_main"``, out main_func_symbol);``+`            `var main_func_found` `=` `container.module.symbol (``"main"``, out main_func_symbol);` `-`            `unowned string entrypoint` `=` `"frida_agent_main"``;``+`            `unowned string entrypoint` `=` `"main"``;` `+` `custom_script``=``"$output_dir/../../../../frida-core/src/anti-anti-frida.py"`  `/``/` `读取文件目录``priv_dir``=``"$output_dir/frida-agent@emb"` `else``touch` `"$embedded_agent"``fi``+`  `if` `[` `-``f` `"$custom_script"` `]; then``+`    `python3` `"$custom_script"` `"$embedded_agent"``+`  `fi``embedded_agents``+``=``(``"$embedded_agent"``)``}` `exit` `1``fi``+`    `if` `[` `-``f` `"$custom_script"` `]; then``+`      `python3` `"$custom_script"` `"$embedded_agent"``+`    `fi``exec` `"$resource_compiler"` `-``-``toolchain``=``gnu` `-``c` `"$resource_config"` `-``o` `"$output_dir/frida-data-agent"` `"$embedded_agent"` `-`            `string entrypoint` `=` `"frida_agent_main"``;``+`            `string entrypoint` `=` `"main"``;` `-`            `var` `id` `=` `yield` `qinjector.inject_library_resource (pid, agent_desc,` `"frida_agent_main"``,``+`            `var` `id` `=` `yield` `qinjector.inject_library_resource (pid, agent_desc,` `"main"``,` `-`            `var` `id` `=` `yield` `winjector.inject_library_resource (pid, agent,` `"frida_agent_main"``,``+`            `var` `id` `=` `yield` `winjector.inject_library_resource (pid, agent,` `"main"``,` `-`            `var main_func_found` `=` `module.symbol (``"frida_agent_main"``, out main_func_symbol);``+`            `var main_func_found` `=` `module.symbol (``"main"``, out main_func_symbol);` `-`                `yield` `injector.inject_library_file (process.``id``, path,` `"frida_agent_main"``, data);``+`                `yield` `injector.inject_library_file (process.``id``, path,` `"main"``, data);` |
|-|-|

| 123456789101112131415161718192021222324252627282930313233 | `# anti-anti-frida.py``import` `lief``import` `sys``import` `random``import` `os` `if` `__name__` `=``=` `"__main__"``:``input_file` `=` `sys.argv[``1``]``print``(f``"[*] Patch frida-agent: {input_file}"``)``random_name` `=` `"``".join(random.sample("``ABCDEFGHIJKLMNO",` `5``))``print``(f``"[*] Patch `frida` to `{random_name}``"``)` `binary` `=` `lief.parse(input_file)` `if` `not` `binary:``exit()` `for` `symbol` `in` `binary.symbols:``if` `symbol.name` `=``=` `"frida_agent_main"``:``symbol.name` `=` `"main"` `if` `"frida"` `in` `symbol.name:``symbol.name` `=` `symbol.name.replace(``"frida"``, random_name)` `if` `"FRIDA"` `in` `symbol.name:``symbol.name` `=` `symbol.name.replace(``"FRIDA"``, random_name)` `binary.write(input_file)` `# gum-js-loop thread``random_name` `=` `"``".join(random.sample("``abcdefghijklmn",` `11``))``print``(f``"[*] Patch `gum-js-loop` to `{random_name}`"``)``os.system(f``"sed -b -i s/gum-js-loop/{random_name}/g {input_file}"``)` |
|-|-|

## 字符串 `gum-js-loop` `gmain` 进程名

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051 | `# 在上面新建的 Python 文件修改为如下代码``# anti-anti-frida.py``import` `lief``import` `sys``import` `random``import` `os` `if` `__name__` `=``=` `"__main__"``:``input_file` `=` `sys.argv[``1``]``print``(f``"[*] Patch frida-agent: {input_file}"``)``random_name` `=` `"``".join(random.sample("``ABCDEFGHIJKLMNO",` `5``))``print``(f``"[*] Patch `frida` to `{random_name}``"``)` `binary` `=` `lief.parse(input_file)` `if` `not` `binary:``exit()` `for` `symbol` `in` `binary.symbols:``if` `symbol.name` `=``=` `"frida_agent_main"``:``symbol.name` `=` `"main"` `if` `"frida"` `in` `symbol.name:``symbol.name` `=` `symbol.name.replace(``"frida"``, random_name)` `if` `"FRIDA"` `in` `symbol.name:``symbol.name` `=` `symbol.name.replace(``"FRIDA"``, random_name)` `all_patch_string` `=` `[``"FridaScriptEngine"``,` `"GLib-GIO"``,` `"GDBusProxy"``,` `"GumScript"``]` `# 字符串特征修改 尽量与源字符一样``for` `section` `in` `binary.sections:``# print(section.name)``if` `section.name !``=` `".rodata"``:``continue``for` `patch_str` `in` `all_patch_string:``addr_all` `=` `section.search_all(patch_str)``for` `addr` `in` `addr_all:``print``(``"current section name="` `+` `section.name,` `"offset="``,` `hex``(section.file_offset` `+` `addr))``patch` `=` `[``ord``(n)` `for` `n` `in` `list``(patch_str)[::``-``1``]]``binary.patch_address(section.file_offset` `+` `addr, patch)` `binary.write(input_file)` `# gum-js-loop thread``random_name` `=` `"``".join(random.sample("``abcdefghijklmn",` `11``))``print``(f``"[*] Patch `gum-js-loop` to `{random_name}`"``)``os.system(f``"sed -b -i s/gum-js-loop/{random_name}/g {input_file}"``)` `# gmain thread``random_name` `=` `"``".join(random.sample("``abcdefghijklmn",` `5``))``print``(f``"[*] Patch `gmain` to `{random_name}`"``)``os.system(f``"sed -b -i s/gmain/{random_name}/g {input_file}"``)` |
|-|-|

## 目录 re.frida.server

| 12345 | `-`    `private const string DEFAULT_DIRECTORY` `=` `"re.frida.server"``;``+`    `private static string DEFAULT_DIRECTORY` `=` `null;` `private static` `int` `main (string[] args) {``+`        `DEFAULT_DIRECTORY` `=` `GLib.Uuid.string_random();` `/``/` `随机字符串作为目录名` |
|-|-|

## Unexpected command

这个不知道具体作用是什么

| 123456 | `namespace Frida.Droidy {``case` `"OPEN"``:``case` `"CLSE"``:``case` `"WRTE"``:``-`                            `throw new Error.PROTOCOL (``"Unexpected command"``);``+`                            `break``;` `/``/` `throw new Error.PROTOCOL (``"Unexpected command"``);` |
|-|-|

# 手动 Patchs | 16.0.9

- 修改目录 `frida/frida-core` ，`tests` 目录下的文件不用去做修改
- 因为该 https://github.com/hluwa/Patchs 仅支持 15 的版本，所以 14 或 16 的版本可能需要手动进行修改，无法使用 `git am` 一键 Patch
- 建议 Paths 前完整编译一次，编译完成后备份源文件进行 Patch，避免被玩坏了又得重头再来
- 为了方便测试，在 Ubuntu 安装环境

| 12345678910111213141516171819202122 | `# FRIDA 环境``sudo pip3 install frida``-``tools lief` `# adb 安装``sudo apt install` `-``y android``-``tools``-``adb` `# 编译并推送到手机运行``adb root``cd ~``/``Desktop``/``frida``/` `&& make core``-``android``-``arm64` `# 编译64位!``adb push ~``/``Desktop``/``frida``/``build``/``frida``-``android``-``arm64``/``bin``/``frida``-``server` `/``system``/``lib64``adb shell chmod` `777` `/``system``/``lib64``/``fs``adb shell .``/``system``/``lib64``/``fs` `-``l` `0.0``.``0.0``:``9527` `# 查看手机IP``adb shell ifconfig \|grep Bcast` `# 查看端口监听``sagit:``/` `# netstat -tunlp` `Active Internet connections (only servers)``Proto Recv``-``Q Send``-``Q Local Address           Foreign Address         State       PID``/``Program Name``tcp` `0`      `0` `127.0``.``0.1``:``27042`         `0.0``.``0.0``:``*`               `LISTEN` `20043``/``fs` `# frida 标准端口监听``tcp` `0`      `0` `127.0``.``0.1``:``9527`          `0.0``.``0.0``:``*`               `LISTEN` `20238``/``fs` `# frida 非标准端口监听 \| 非标准端口也无需端口转发 老版本的 FRIDA 才需要转发` |
|-|-|

| 12345 | `# 环境配置``sudo pip3 install frida``-``tools lief && sudo apt install` `-``y android``-``tools``-``adb` `# 一键命令(新建 build.sh 写入以下命令运行比较方便)``adb root && cd ~``/``Desktop``/``frida``/` `&& make core``-``android``-``arm64 && adb push ~``/``Desktop``/``frida``/``build``/``frida``-``android``-``arm64``/``bin``/``frida``-``server` `/``system``/``lib64``/``fs && adb shell chmod` `777` `/``system``/``lib64``/``fs && adb shell .``/``system``/``lib64``/``fs` `-``l` `0.0``.``0.0``:``9527` |
|-|-|

## Build.sh

| 1 | `adb root && export ANDROID_NDK_ROOT``=``/``home``/``k``/``Desktop``/``android``-``ndk``-``r25c && export PATH``=``$ANDROID_NDK_ROOT:$PATH && source ~``/``.bashrc && cd ~``/``Desktop``/``frida``/` `&& make core``-``android``-``arm64 && adb push build``/``frida``-``android``-``arm64``/``bin``/``frida``-``server` `/``system``/``lib64``/``fs && adb shell chmod` `777` `/``system``/``lib64``/``fs && adb shell .``/``system``/``lib64``/``fs` `-``l` `0.0``.``0.0``:``9527` |
|-|-|

##

- ![image](https://bbs.kanxue.com/upload/attach/202302/918604_Y3E56Q2ZX9RZW8C.png)

全局搜索执行修改

## 目录名修改 re.frida.server

>
> `re.frida.server` 目录会生成很多文件，frida 就是把其中的 `frida-agent-<32/64>.so` 注入到进程
>
>
>

| 12345678910111213141516 | `/``/` `frida``/``frida``-``core``/``server``/``server.vala``-`    `private const string DEFAULT_DIRECTORY` `=` `"re.frida.server"``;``+` `private static string DEFAULT_DIRECTORY` `=` `null;``private static` `int` `main (string[] args) {``+`        `DEFAULT_DIRECTORY` `=` `GLib.Uuid.string_random();` `/``/` `随机目录名` `/``/` `frida``/``frida``-``core``/``server``/``server.vala``-`    `private const string DEFAULT_DIRECTORY` `=` `"re.frida.server"``;``+`    `private const string DEFAULT_DIRECTORY` `=` `"IOserver"``;` `/``/` `建议修改为固定目录名⭐` `/``/` `在 frida``-``server 运行时才会存在目录 __``sagit:``/` `# ls -alit /data/local/tmp/` `2105359` `drwxr``-``xr``-``x` `2` `root   root` `4096` `2023``-``02``-``12` `21``:``32` `IOserver` `/``/` `这个目录一般来说 frida``-``server 退出会删除, 但是也可能异常退出就不会被删除; 意味着如果是随机目录名就可能会随地` `"大小便"` `不进行处理``2097154` `drwxrwxrwx` `3` `system system` `4096` `2023``-``02``-``12` `21``:``32` `.``2097200` `-``rwxrwxrwx` `1` `shell  shell` `41391568` `2023``-``02``-``12` `21``:``24` `fs``2097153` `drwxr``-``x``-``-``x` `6` `root   root` `4096` `2023``-``02``-``12` `17``:``46` `..` |
|-|-|

## 目录存放修改 re.frida.server

| 12345678 | `/``/` `frida``/``frida``-``core``/``src``/``linux``/``system``-``linux.c``if` `(getuid ()` `=``=` `0``)``-`  `return` `g_strdup (``"/data/local/tmp"``);``+`  `return` `g_strdup (``"/system/lib64"``);` `/``/` `以后就会在目录` `/``system``/``lib64 生成所需文件，其他目录尝试会出权限问题``/``/` `Unable to get frontmost application on MI` `6``: error creating directory` `/``system``/``9527``: Read``-``only` `file` `system``/``/` `frida.PermissionDeniedError: error creating directory` `/``bin``/``9527``: Read``-``only` `file` `system` |
|-|-|

## 字符串修改

### linjector

| 123 | `/``/` `frida``/``frida``-``core``/``src``/``linux``/``frida``-``helper``-``backend``-``glue.c``-`  `self``-``>fifo_path` `=` `g_strdup_printf (``"%s/linjector-%u"``,` `self``-``>temp_path,` `self``-``>``id``);``+`  `self``-``>fifo_path` `=` `g_strdup_printf (``"%s/%p%u"``,` `self``-``>temp_path,` `self` `,``self``-``>``id``);` |
|-|-|

### frida-agent

这个是 `re.frida.server` 目录下的注入文件

| 1234567891011 | `-`            `agent` `=` `new AgentDescriptor (PathTemplate (``"frida-agent-<arch>.so"``),``+`            `var random_prefix` `=` `GLib.Uuid.string_random();` `/``/` `随机前缀``+`            `agent` `=` `new AgentDescriptor (PathTemplate (random_prefix` `+` `"-<arch>.so"``),``new Bytes.static (blob32.data),``new Bytes.static (blob64.data),``new AgentResource[] {``-`                    `new AgentResource (``"frida-agent-arm.so"``, new Bytes.static (emulated_arm.data), tempdir),``-`                    `new AgentResource (``"frida-agent-arm64.so"``, new Bytes.static (emulated_arm64.data), tempdir),``+`                    `new AgentResource (random_prefix` `+` `"-arm.so"``, new Bytes.static (emulated_arm.data), tempdir),` `/``/` `去除frida``-``agent特征 修改为随机前缀``+`                    `new AgentResource (random_prefix` `+` `"-arm64.so"``, new Bytes.static (emulated_arm64.data), tempdir),` `/``/` `去除frida``-``agent特征 修改为随机前缀``},` |
|-|-|

| 1234567891011121314151617181920212223242526 | `sagit:``/` `# ls -alitr /system/lib64/62881400-731e-43cd-a359-6e795717188d/` `total` `36588``4481689` `srw``-``rw``-``rw``-` `1` `root root` `0` `2023``-``02``-``12` `22``:``27` `pipe``-``a9d2e03a7b2ae5826b9333aba83438bd``5736713` `srw``-``rw``-``rw``-` `1` `root root` `0` `2023``-``02``-``12` `22``:``27` `pipe``-``384b91416c99237ee13372f8d87b31db``4481694` `prw``-``rw``-``rw``-` `1` `root root` `0` `2023``-``02``-``12` `22``:``27` `linjector``-``1``4481692` `-``rwx``-``-``-``-``-``-` `1` `root root` `2624112` `2023``-``02``-``12` `22``:``27` `frida``-``helper``-``32``4481691` `-``rwxr``-``xr``-``x` `1` `root root` `20142336` `2023``-``02``-``12` `22``:``27` `7a9f4666``-``5fa6``-``4ec8``-``b030``-``3f019e05b68e``-``64.so`  `/``/` `随机名字``4481690` `-``rwxr``-``xr``-``x` `1` `root root` `14693860` `2023``-``02``-``12` `22``:``27` `7a9f4666``-``5fa6``-``4ec8``-``b030``-``3f019e05b68e``-``32.so``23345` `drwxr``-``xr``-``x` `8` `root root` `13540` `2023``-``02``-``12` `22``:``27` `..``4970580` `srw``-``rw``-``rw``-` `1` `root root` `0` `2023``-``02``-``12` `22``:``27` `pipe``-``5fe63df60d778fafde6fc5559736357b``4492937` `prw``-``rw``-``rw``-` `1` `root root` `0` `2023``-``02``-``12` `22``:``27` `linjector``-``3``4492936` `prw``-``rw``-``rw``-` `1` `root root` `0` `2023``-``02``-``12` `22``:``27` `linjector``-``2``4481687` `drwxr``-``xr``-``x` `2` `root root` `220` `2023``-``02``-``12` `22``:``27` `.` `sagit:``/` `# ls -alitr /data/local/tmp_back/re.frida.server/` `total` `36620``2097833` `srw``-``rw``-``rw``-` `1` `root   root` `0` `2023``-``02``-``12` `17``:``46` `pipe``-``f47ac5882f95a69873c4ecae495ef7f4``2097814` `srw``-``rw``-``rw``-` `1` `root   root` `0` `2023``-``02``-``12` `17``:``46` `pipe``-``b9e6c386ba48b51d881e4c066c01417f``2097818` `srw``-``rw``-``rw``-` `1` `root   root` `0` `2023``-``02``-``12` `17``:``46` `pipe``-``40bf4f01603822d132ad3e68d66f9dbd``2097816` `prw``-``rw``-``rw``-` `1` `root   root` `0` `2023``-``02``-``12` `17``:``46` `linjector``-``2``2097819` `prw``-``rw``-``rw``-` `1` `root   root` `0` `2023``-``02``-``12` `17``:``46` `linjector``-``1``2097835` `-``rwx``-``-``-``-``-``-` `1` `root   root` `2623956` `2023``-``02``-``12` `17``:``46` `frida``-``helper``-``32``2097831` `-``rwxr``-``xr``-``x` `1` `root   root` `20138088` `2023``-``02``-``12` `17``:``46` `frida``-``agent``-``64.so`    `/``/` `原本的名字``2097837` `-``rwxr``-``xr``-``x` `1` `root   root` `14693704` `2023``-``02``-``12` `17``:``46` `frida``-``agent``-``32.so``2105402` `drwxrwxrwx` `9` `system system` `4096` `2023``-``02``-``12` `17``:``46` `..``2105421` `drwxr``-``xr``-``x` `2` `root   root` `4096` `2023``-``02``-``12` `17``:``46` `.` |
|-|-|

### frida:rpc

>
> FRIDA 14.2.17 修改此项不成功，利用 `lief` 进行全局 Patch 会出问题，总之 14 版本 frida:rpc 字符串修改不了（反正我没成功过，可以尝试使用 010Editor 或 ida 进行 Patch
>
>
>

 如果修改为其他值还需要改动 PC 端的文件

| 123456789101112131415161718192021222324252627282930 | `/``/` `这种修改不用对 PC 端进行改动``/``/` `frida``/``frida``-``core``/``lib``/``interfaces``/``rpc.vala \|` `16.0``.``9` `是 rpc.vala``-`    `.add_string_value (``"frida:rpc"``)` `/``/` `这个要改动两处``+`    `.add_string_value ((string) GLib.Base64.decode(``"ZnJpZGE6cnBj="``))` `-`    `if` `(json.index_of (``"\"frida:rpc\""``)` `=``=` `-``1``)``+`    `if` `(json.index_of ((string) GLib.Base64.decode(``"ImZyaWRhOnJwYyI="``))` `=``=` `-``1``)` `/``/` `这种改动需要对 PC 端进行修改``"frida:rpc"` `-``>` `"fuck"` `/``/` `windows 改动``〉which core.py``├───┼───────┼─────────────────────────────────────────┼──────────┤``│` `0` `│ frida │ D:\B_Tool\Python3.``8.5``\Scripts\frida.exe │ false    │``╰───┴───────┴─────────────────────────────────────────┴──────────╯``〉``open`  `D:\B_Tool\Python3.``8.5``\Lib\site``-``packages\frida\core.py \|findstr` `"frida:rpc"``message` `=` `[``'frida:rpc'``, request_id]``elif` `mtype` `=``=` `'send'` `and` `isinstance``(payload,` `list``)` `and` `len``(payload) >` `0` `and` `payload[``0``]` `=``=` `'frida:rpc'``:` `/``/` `linux 改动``cat` `/``usr``/``local``/``lib``/``python3.``10``/``dist``-``packages``/``frida``/``core.py \|grep` `"frida:rpc"``message` `=` `[``'frida:rpc'``, request_id]``elif` `mtype` `=``=` `'send'` `and` `isinstance``(payload,` `list``)` `and` `len``(payload) >` `0` `and` `payload[``0``]` `=``=` `'frida:rpc'``:` `sudo sed` `-``i` `'s/frida:rpc/fuck/g'` `/``usr``/``local``/``lib``/``python3.``10``/``dist``-``packages``/``frida``/``core.py` `/``/` `命令行修改文本` `cat` `/``usr``/``local``/``lib``/``python3.``10``/``dist``-``packages``/``frida``/``core.py \|grep` `"fuck"``message` `=` `[``'fuck'``, request_id]``elif` `mtype` `=``=` `'send'` `and` `isinstance``(payload,` `list``)` `and` `len``(payload) >` `0` `and` `payload[``0``]` `=``=` `'fuck'``:` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202302/918604_EGTFKZRARD84W5W.png)

### frida_agent_main

| 1234567891011121314151617181920 | `/``/` `这里是` `14.2``.``17` `的替换``/``/` `frida``/``frida``-``core``/``src``/``agent``-``container.vala``-`  `var main_func_found` `=` `container.module.symbol (``"frida_agent_main"``, out main_func_symbol);``+`  `var main_func_found` `=` `container.module.symbol (``"main"``, out main_func_symbol);` `/``/` `frida``/``frida``-``core``/``src``/``darwin``/``darwin``-``host``-``session.vala``-`  `unowned string entrypoint` `=` `"frida_agent_main"``;``+`  `unowned string entrypoint` `=` `"main"``;` `/``/` `frida``/``frida``-``core``/``src``/``linux``/``linux``-``host``-``session.vala``-`  `string entrypoint` `=` `"frida_agent_main"``;``+`  `string entrypoint` `=` `"main"``;` `/``/` `frida``/``frida``-``core``/``src``/``qnx``/``qnx``-``host``-``session.vala``-`  `var` `id` `=` `yield` `qinjector.inject_library_resource (pid, agent_desc,` `"frida_agent_main"``, t.remote_address,``+`  `var` `id` `=` `yield` `qinjector.inject_library_resource (pid, agent_desc,` `"main"``, t.remote_address,` `/``/` `frida``/``frida``-``core``/``src``/``windows``/``windows``-``host``-``session.vala``-`  `var` `id` `=` `yield` `winjector.inject_library_resource (pid, agent,` `"frida_agent_main"``, t.remote_address, cancellable);``+`  `var` `id` `=` `yield` `winjector.inject_library_resource (pid, agent,` `"main"``, t.remote_address, cancellable);` |
|-|-|

### `gum-js-loop` `gmain` `gdbus` 进程名

| 1234567891011121314151617 | `# frida/frida-core/src/embed-agent.sh``+`  `custom_script``=``"$output_dir/../../../../frida-core/src/anti-frida.py"``priv_dir``=``"$output_dir/frida-agent@emb"` `+`  `if` `[` `-``f` `"$custom_script"` `]; then``+`    `python3` `"$custom_script"` `"$embedded_agent"``+`  `fi``embedded_agents``+``=``(``"$embedded_agent"``)` `echo` `"An agent must be provided"``exit` `1``fi``+`   `if` `[` `-``f` `"$custom_script"` `]; then``+`     `python3` `"$custom_script"` `"$embedded_agent"``+`   `fi` `exec` `"$resource_compiler"` `-``-``toolchain``=``gnu` `-``c` `"$resource_config"` `-``o` `"$output_dir/frida-data-agent"` `"$embedded_agent"` |
|-|-|

Tips：记得安装依赖 `sudo pip3 install lief`

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758 | `# frida/frida-core/src/anti-frida.py 新建 Python Script 命名为 anti-frida.py``import` `lief``import` `sys``import` `random``import` `os` `def` `log_color(msg):``print``(f``"\033[1;31;40m{msg}\033[0m"``)` `if` `__name__` `=``=` `"__main__"``:``input_file` `=` `sys.argv[``1``]``log_color(f``"[*] Patch frida-agent: {input_file}"``)``random_name` `=` `"``".join(random.sample("``ABCDEFGHIJKLMNO``", 5)) # generate random "``frida``-``agent``-``arm``/``64.so``" name``log_color(f``"[*] Patch `frida` to `{random_name}``"``)` `binary` `=` `lief.parse(input_file)` `if` `not` `binary:``exit()` `for` `symbol` `in` `binary.symbols:` `# 修改符号名``if` `symbol.name` `=``=` `"frida_agent_main"``:``symbol.name` `=` `"main"` `if` `"frida"` `in` `symbol.name:``symbol.name` `=` `symbol.name.replace(``"frida"``, random_name)` `if` `"FRIDA"` `in` `symbol.name:``symbol.name` `=` `symbol.name.replace(``"FRIDA"``, random_name)` `all_patch_string` `=` `[``"FridaScriptEngine"``,` `"GLib-GIO"``,` `"GDBusProxy"``,` `"GumScript"``]` `# 字符串特征修改 尽量与源字符一样``for` `section` `in` `binary.sections:``log_color(section.name)``if` `section.name !``=` `".rodata"``:``continue``for` `patch_str` `in` `all_patch_string:``addr_all` `=` `section.search_all(patch_str)` `# Patch 内存字符串``for` `addr` `in` `addr_all:``patch` `=` `[``ord``(n)` `for` `n` `in` `list``(patch_str)[::``-``1``]]``log_color(f``"current section name={section.name} offset={hex(section.file_offset + addr)} {patch_str}-{"``".join(list(patch_str)[::-1])}"``)``binary.patch_address(section.file_offset` `+` `addr, patch)` `binary.write(input_file)` `# thread_gum_js_loop``random_name` `=` `"``".join(random.sample("``abcdefghijklmn",` `11``))``log_color(f``"[*] Patch `gum-js-loop` to `{random_name}`"``)``os.system(f``"sed -b -i s/gum-js-loop/{random_name}/g {input_file}"``)` `# thread_gmain``random_name` `=` `"``".join(random.sample("``abcdefghijklmn",` `5``))``log_color(f``"[*] Patch `gmain` to `{random_name}`"``)``os.system(f``"sed -b -i s/gmain/{random_name}/g {input_file}"``)` `# thread_gdbus``random_name` `=` `"``".join(random.sample("``abcdefghijklmn",` `5``))``log_color(f``"[*] Patch `gdbus` to `{random_name}`"``)``os.system(f``"sed -b -i s/gdbus/{random_name}/g {input_file}"``)` |
|-|-|

# 一个检测案例

具体检测方法就留给你们自己去研究了~

  ![image](https://bbs.kanxue.com/upload/attach/202302/918604_23RHW3GQYNMZWQE.png)

# ANTI FRID ARTICLE

- 推荐一些不错的 FRIDA 相关文章
- [从 inlinehook 角度检测 frida-Android](https://bbs.kanxue.com/thread-269862.htm)
- [从 Frida源码学习ArtHook（一） · wuhx/AppInspect Wiki](https://github.com/wuhx/AppInspect/wiki/%E4%BB%8EFrida%E6%BA%90%E7%A0%81%E5%AD%A6%E4%B9%A0ArtHook%EF%BC%88%E4%B8%80%EF%BC%89)
- [从 Frida源码学习ArtHook（二） · wuhx/AppInspect Wiki](https://github.com/wuhx/AppInspect/wiki/%E4%BB%8EFrida%E6%BA%90%E7%A0%81%E5%AD%A6%E4%B9%A0ArtHook%EF%BC%88%E4%BA%8C%EF%BC%89)
- [Frida Internal - Part 1: 架构、Gum 与 V8](https://mp.weixin.qq.com/s/P6WGhDL3b4qB-edyc4hpXg)
- [Frida Internal - Part 2: 核心组件 frida-core](https://mp.weixin.qq.com/s/TJkGsm9UaSkC4AFXj9fGHw)
- [Frida Internal - Part 3: Java Bridge 与 ART hook](https://mp.weixin.qq.com/s/aFtQt6_js1DuJvJp6Jgj2Q)
- [Frida 源码分析 | m4bln](https://mabin004.github.io/2018/07/31/Mac%E4%B8%8A%E7%BC%96%E8%AF%91Frida/)
- [frida 源代码分析--进程注入和 server dbus 通讯架构分析](https://bbs.kanxue.com/thread-270305.htm)
- [LIEF 官方文档](https://lief-project.github.io//doc/latest/tutorials/09_frida_lief.html)
- [多种姿势花样使用 Frida注入 | AshenOne](https://ashenone66.cn/2021/09/20/duo-chong-zi-shi-hua-yang-shi-yong-frida-zhu-ru/)
- [关于frida检测的一个新思路](https://bbs.kanxue.com/thread-268586.htm)
- https://github.com/qtfreet00/AntiFrida

# 总结

- 其实还有很多字符串特征，想要 Patch 完全的话工作量可能有点大而且我觉得不太现实（我猜大胡子能做到！！

| 12 | `1``\|sagit:``/` `$ ps` `-``A \|grep frida` `root` `8920`     `1`   `11504`   `2280` `0`                   `0` `S frida``-``helper``-``32` |
|-|-|
- 建议把编译好的 frida 放在 `/system/lib64` 使用
- 一入对抗深似海~ 卷死我了都
- 这里还做了一个 16.0.9 的 Patchs 文件，暂时能过掉文章的检测案例，其他检测需要根据实际的对抗场景进行优化

| 12345678 | `# 最版本编译（16.0.9）` `# 1.把 Patchs.zip 放在桌面``# 2.Pathch后编译推送到手机执行 frida-server，期间把手机链接到虚拟机``cd ~``/``Desktop && unzip Patchs.``zip` `&& sudo apt``-``get update && sudo apt``-``get install` `-``y build``-``essential curl git lib32stdc``+``+``-``9``-``dev libc6``-``dev``-``i386 nodejs npm python3``-``dev python3``-``pip android``-``tools``-``adb && sudo pip3 install frida``-``tools lief && git config` `-``-``global` `http.proxy` `"http://192.168.1.6:7890"` `&& git config` `-``-``global` `https.proxy` `"https://192.168.1.6:7890"` `&& git config` `-``-``global` `user.email` `"you@example.com"` `&& git config` `-``-``global` `user.name` `"Your Name"` `&& git clone` `-``-``recurse``-``submodules https:``/``/``github.com``/``frida``/``frida.git && wget https:``/``/``dl.google.com``/``android``/``repository``/``android``-``ndk``-``r25c``-``linux.``zip` `&& unzip android``-``ndk``-``r25c``-``linux.``zip` `&& export ANDROID_NDK_ROOT``=``/``home``/``k``/``Desktop``/``android``-``ndk``-``r25c && export PATH``=``$ANDROID_NDK_ROOT:$PATH && cd frida``/``frida``-``core && git am ..``/``..``/``Patchs``/``*``.patch && cd ..``/` `&& make core``-``android``-``arm64 && adb root && adb push build``/``frida``-``android``-``arm64``/``bin``/``frida``-``server` `/``system``/``lib64``/``fs && adb shell chmod` `777` `/``system``/``lib64``/``fs && adb shell .``/``system``/``lib64``/``fs` `-``l` `0.0``.``0.0``:``9527` `# build.sh``adb root && export ANDROID_NDK_ROOT``=``/``home``/``k``/``Desktop``/``android``-``ndk``-``r25c && export PATH``=``$ANDROID_NDK_ROOT:$PATH && source ~``/``.bashrc && cd ~``/``Desktop``/``frida``/` `&& make core``-``android``-``arm64 && adb push build``/``frida``-``android``-``arm64``/``bin``/``frida``-``server` `/``system``/``lib64``/``fs && adb shell chmod` `777` `/``system``/``lib64``/``fs && adb shell .``/``system``/``lib64``/``fs` `-``l` `0.0``.``0.0``:``9527` |
|-|-|
- patch 生成与合并（一些栗子

| 12345678910 | `git config` `-``-``global` `user.email` `"you@example.com"` `&& git config` `-``-``global` `user.name` `"Your Name"``git commit` `-``a` `-``m` `"io_re_frida_server"` `&& git` `format``-``patch HEAD^``git reset` `-``-``soft HEAD^` `# 撤销` `git add <文件>            更新要提交的内容``git restore <文件>        丢弃工作区的改动``git commit` `-``m` `"提交说明"``git commit` `-``a` `-``m` `"提交说明"` `$ git` `format``-``patch HEAD^^^^` `# 生成最近的4次commit的patch` |
|-|-|
- 那些一大堆的脚本是打开 Ubuntu 终端输入自动运行编译的代码，傻瓜式编译~

上传的附件：
- Frida_check.apk

（4.14MB，466次下载）
- Patchs.zip

（9.39kb，270次下载）

---

# 回复

## 回复 by hzzheyang (#2)

*2023-2-15 11:54*

我用了会报错
Failed to spawn: error creating directory /system/lib64/IOserver: Read-only file system

## 回复 by 司徒废人 (#3)

*2023-2-15 16:02*

正常编译16.0.9普通版本可以运行，用patch后，运行会导致系统不断重启

## 回复 by 司徒废人 (#4)

*2023-2-15 16:34*

找到问题了 ；
释放到/sytem/lib64一样有权限问题，不开启系统分区写权限时，无法创建目录；
开启写入权限，则系统重启；
更换目录后，可以正常spawn，但是check程序，显示线程检测通过不了。

## 回复 by .KK (#5)

*2023-2-15 16:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  司徒废人](https://bbs.kanxue.com/user-641235.htm)
>
>  找到问题了 ；
> 释放到/sytem/lib64一样有权限问题，不开启系统分区写权限时，无法创建目录；
> 开启写入权限，则系统重启；
> 更换目录后，可以正常spawn，但是check程序，显示线程检测 ...
>
>

也许我以前修改过这个目录权限吧 自己也可以测试放在其他目录 或者默认目录也一样 特征基本都修改了

## 回复 by .KK (#6)

*2023-2-15 17:01*

>
> [hzzheyang](https://bbs.kanxue.com/user-860121.htm)
>
>  我用了会报错
> Failed to spawn: error creating directory /system/lib64/IOserver: Read-only file system
>
>

有问题可以不修改目录的生成位置

## 回复 by 司徒废人 (#7)

*2023-2-16 09:01*

我hook了 线程检测，有线程名为pool-frida；
  threadCheck ret value is found pool-frida thread: Name:        pool-frida；
然后脚本中加了下面这句，还是不行
 # thread_pool-frida
    random_name = "".join(random.sample("abcdefghijklmn", 10))
    log_color(f"[*] Patch `pool-frida` to `{random_name}`")
    os.system(f"sed -b -i s/pool-frida/{random_name}/g {input_file}")

## 回复 by bluegatar (#8)

*2023-2-16 12:22*

还有一些小毛病吧，修改一下

## 回复 by mb_wpitiize (#9)

*2023-2-17 18:09*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  司徒废人](https://bbs.kanxue.com/user-641235.htm)
>
>  我hook了 线程检测，有线程名为pool-frida；
>  threadCheck ret value is found pool-frida thread: Name: pool-frida；
>  ...
>
>

老哥找到解决办法了吗

## 回复 by lamorm (#10)

*2023-2-28 08:59*

老哥解决了嘛

## 回复 by 司徒废人 (#11)

*2023-2-28 10:22*

还没找到这个字符串创建的位置，等大佬指点

## 回复 by .KK (#12)

*2023-3-1 20:42*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  司徒废人](https://bbs.kanxue.com/user-641235.htm)
>
>  还没找到这个字符串创建的位置，等大佬指点
>
>

pool-frida 我也修改不成功 我的想法就是 patch 大部分特征+anti的脚本去进行对抗 单纯指望一次性修改掉所有特征我觉得不太现实

## 回复 by Avenue-le (#13)

*2023-3-23 10:30*

![image](https://bbs.kanxue.com/upload/attach/202303/935618_EBN8Q5MVHMPFSYT.jpg)

这个什么错误啊

## 回复 by wx_嗨 (#14)

*2023-4-8 00:28*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  司徒废人](https://bbs.kanxue.com/user-641235.htm)
>
>  找到问题了 ；
> 释放到/sytem/lib64一样有权限问题，不开启系统分区写权限时，无法创建目录；
> 开启写入权限，则系统重启；
> 更换目录后，可以正常spawn，但是check程序，显示线程检测 ...
>
>

老哥解决了吗？一样的问题，启动服务直接重启

## 回复 by wx_嗨 (#15)

*2023-4-8 01:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  司徒废人](https://bbs.kanxue.com/user-641235.htm)
>
>  我hook了 线程检测，有线程名为pool-frida；
>  threadCheck ret value is found pool-frida thread: Name: pool-frida；
>  ...
>
>

好像是system目录的问题，我挂载了能正常写入也是会重启，我把路径改到/data/local/tmp/目录下重新编译就正常了，不过楼主发的线程检测、map记录检测和fd检测都检测到了，应该特征就是这个路径![image](https://bbs.kanxue.com/view/img/face/5.gif)

## 回复 by .KK (#16)

*2023-4-8 01:06*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_嗨](https://bbs.kanxue.com/user-953698.htm)
>
>  好像是system目录的问题，我挂载了能正常写入也是会重启，我把路径改到/data/local/tmp/目录下重新编译就正常了，不过楼主发的线程检测、map记录检测和fd检测都检测到了，应该特征就是这 ...
>
>

这个检测不全是这个原因，你可以把检测的so用ida分析一下检测逻辑就明白检测了哪些点

## 回复 by Yuusha (#17)

*2023-5-17 14:23*

pool-frida在frida注入十来秒后就没了,自己写个app用frida启用等十来秒后加载libmsaoaidsec.so也不会闪退,就是不知道在哪里改这个字符串特征

## 回复 by ivy1 (#18)

*2023-5-19 15:12*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  司徒废人](https://bbs.kanxue.com/user-641235.htm)
>
>  我hook了 线程检测，有线程名为pool-frida；
>  threadCheck ret value is found pool-frida thread: Name: pool-frida；
>  ...
>
>

在内核中修改
--- a/kernel/sys.c
+++ b/kernel/sys.c
@@ -2298,6 +2298,10 @@ SYSCALL_DEFINE5(prctl, int, option, unsigned long, arg2, unsigned long, arg3,
                if (strncpy_from_user(comm, (char __user *)arg2,
                                      sizeof(me->comm) - 1) < 0)
                        return -EFAULT;
+        if (!strcmp(comm, "pool-frida")) {
+            memcpy(comm, "pool-works", strlen(comm));
+            pr_info("prctl rename from %d\n", me->pid);
+        }

## 回复 by 万里星河 (#19)

*2023-5-19 23:35*

mark

## 回复 by Yuusha (#20)

*2023-5-23 18:39*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  ivy1](https://bbs.kanxue.com/user-972238.htm)
>
>  在内核中修改
> --- a/kernel/sys.c
> +++ b/kernel/sys.c
> @@ -2298,6 +2298,10 @@ SYSCALL_DEFINE5(prctl, int, o ...
>
>

我是4.10内核 改了kernel/sys.c 这个位置确实可以了,忘了从内核下手
case PR_SET_NAME:
                comm[sizeof(me->comm) - 1] = 0;
                if (strncpy_from_user(comm, (char __user *)arg2,
                                      sizeof(me->comm) - 1) < 0)
                        return -EFAULT;
                if (!strcmp(comm, "pool-frida")) {
                            memcpy(comm, "pool-works", strlen(comm));
                            pr_info("prctl rename from %d\n", me->pid);
                }
                set_task_comm(me, comm);
                proc_comm_connector(me);
                break;

## 回复 by Yuusha (#21)

*2023-5-24 14:14*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Yuusha](https://bbs.kanxue.com/user-951896.htm)
>
>  我是4.10内核 改了kernel/sys.c 这个位置确实可以了,忘了从内核下手
> case PR_SET_NAME:
>  comm[sizeof(me->comm) - 1] = 0;
>  ...
>
>

补一个简单过PrettyMethod的检测方法,把手机的libart.so拖出来看PrettyMethod函数头原来的几个字节进行修改,这样改应该会对frida部分功能造成影响
function fridaInlineHookCheckPass(){
    //PrettyMethod

    //获取libart模块
    var libart = Process.findModuleByName("libart.so")
    console.log("libart base: " + libart.base);

    //打印原函数头字节
    var PrettyMethod = libart.base.add(0x175475);
    console.log(myhexdump(Memory.readByteArray(PrettyMethod, 16)))

    //修改函数头字节
    Memory.protect(PrettyMethod, 16, "rwx");
    var p_fun = new NativePointer(PrettyMethod)
    p_fun.writeByteArray([0xF0, 0xB5, 0x85, 0xBD, 0x04, 0x46, 0x3E, 0x48, 0x0D, 0x46])

    //修改代码段属性
    Memory.protect(PrettyMethod, 16, "rx");

    //再次打印函数头查看是否修改成功
    console.log(myhexdump(Memory.readByteArray(PrettyMethod, 16)))
}

## 回复 by mb_nyocdonk (#22)

*2023-6-12 01:46*

pool-%s  对应pool-frida

## 回复 by 微微T52G25 (#23)

*2023-6-13 15:37*

太复杂了看不懂

## 回复 by VinceLi (#24)

*2023-9-13 10:53*

hluwa的Patch中的 0003-string_frida_rpc.patch文件

| 12 | `-`  `.add_string_value (``"frida:rpc"``)``+`  `.add_string_value ((string) GLib.Base64.decode(``"ZnJpZGE6cnBj="``))` |
|-|-|

这个替换，"ZnJpZGE6cnBj=" base64解码后还是 "frida:rpc" ，那这个替换的意义在哪？

## 回复 by ldzspace (#25)

*2024-1-8 15:22*

>
> [VinceLi](https://bbs.kanxue.com/user-966848.htm)
>
>  hluwa的Patch中的 0003-string_frida_rpc.patch文件-&nbsp;&nbsp;.add_string_value&nbsp;(&quo ...

防止内存扫描吧

## 回复 by ninebell (#26)

*2024-1-8 15:51*

这玩意 能编译个中文版的出来么？
英文都认识，就是虾米小字看得太累眼。
另外还需要加点学习笔记和心得到各地。

## 回复 by ty1937 (#27)

*2024-12-18 11:25*

楼主，你是怎么过  线程检测（"SigBlk:\tffffffe0fffbfaff）？

## 回复 by 思睿 (#28)

*2024-12-18 15:03*

frida-core目录：
diff --git a/src/frida-glue.c b/src/frida-glue.c
old mode 100644
new mode 100755
index 13429703..768c8677
--- a/src/frida-glue.c
+++ b/src/frida-glue.c
@@ -40,7 +40,7 @@ frida_init_with_runtime (FridaRuntime rt)
     g_io_module_openssl_register ();
 #endif

-    g_set_prgname ("frida");
+    g_set_prgname ("niubi");

     if (runtime == FRIDA_RUNTIME_OTHER)
     {

frida-gum目录：
diff --git a/gum/gum.c b/gum/gum.c
old mode 100644
new mode 100755
index b07c0fe1..8de05108
--- a/gum/gum.c
+++ b/gum/gum.c
@@ -304,7 +304,7 @@ gum_init_embedded (void)
   g_log_set_default_handler (gum_on_log_message, NULL);
   gum_do_init ();

-  g_set_prgname ("frida");
+  g_set_prgname ("niubi");

 #if defined (HAVE_LINUX) && defined (HAVE_GLIBC)
   gum_libdl_prevent_unload ();
