---
title: '[原创] ida脚本开发环境配置idapython&idacpp三端环境(win,mac,linux)'
url: https://bbs.kanxue.com/thread-279793.htm
tid: 279793
author: 初恒
date: '2023-12-07'
tags: [Android安全, 原创, 工具脚本]
crawled_at: '2026-07-31T14:36:14+08:00'
replies: 21
---

写ida脚本也有一段时间了,一直有个痛点是找不到比较好的方法热重载脚本来实时改动生效,导致开发效率老慢了。固总结下比较友好的环境搭配

# ida脚本开发,使用ida热加载插件让你开发脚本更高效

### github地址: <https://github.com/0xeb/ida-qscripts>, 这位老外是个知名视频网站小博主,挺多小妙招的

## 1.下载源码:

| 1234567 | `/``/``1.``下载 ida``-``cmake` `cd` `/``path``/``to``/``ida``/``idasdk``/``plugins && git clone  https:``/``/``github.com``/``0xeb``/``ida``-``cmake` `/``/``2.``下载 ida``-``qscripts``cd` `/``path``/``to``/``ida``/``idasdk``/``plugins && git clone https:``/``/``github.com``/``0xeb``/``ida``-``qscripts` `/``/``3.``下载idax``cd` `/``path``/``to``/``ida``/``idasdk``/``plugins``/``ida``-``qscripts &&``git clone https:``/``/``github.com``/``0xeb``/``idax` |
|-|-|

## 2.编译:

- mac or linux 环境

| 123456 | `/``/``1.``环境变量添加 IDASDK``/``/``mac` `or` `linux``export IDASDK``=``/``path``/``to``/``ida``/``idasdk``/``/``2.clion` `直接打开 ida``-``qscripts``/``/``3.clion` `-``-` `settings` `-``-` `build,execution,deployment 中 新增配置,并设置 cmake ida插件变量(``64``位的需要)``/``/``4.``将编译出来的 qscripts.dylib qscripts64.dylib` `or` `qscripts.so qscripts.so 手动复制到` `/``path``/``to``/``ida``/``plugins 中,重启ida即生效` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_29BUE2NJTYS6UVR.webp)
- windows 环境

| 1234 | `/``/``1.``设置环境变量``setx IDASDK` `/``path``/``to``/``ida``/``idasdk``/``/``2.``使用visual studio打开,测试环境为vs2022,打开后在cmakefile中看情况设置` `/``/``3.vs` `点击 项目``-``-``> qscripts的 CMake设置，在下面设置才能编译``64``位的dll` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_8C4QH4RGB7RGFYN.webp)

| 1 | `/``/``4.``将 qscripts.dll qscripts64.dll 复制到` `/``path``/``to``/``ida``/``plugins` |
|-|-|

## 3.运行图:

- ida 运行图
	- mac or linux
		- ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_SBZQURM4JGWCPDV.webp)
	- windows
		- ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_J4ZAXAR4JW9XHYN.webp)

## 4.pycharm 配置 idapython开发环境

- 代码提示配置
	- 打开pycharm的setting --> python interpreter --> showall
		- ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_D8MMHXM5BPQ26GZ.webp)
	- 点击这个图标
		- ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_NWB8FAMEAUYSDCR.webp)
	- 添加ida目录下的python3
		- ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_3UPWMARHMUAU3A7.webp)
	- 验证
		- ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_55TSSNBMDX5MY4P.webp)
- 动态调试
	- pycharm 新增一个remote debug
		- ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_7ZFUBVRWNPWRGJS.webp)
	- 点击pycharm debug按钮,此时pycharm会循环监听目标端口
	- ida打开qscripts进行加载和监听
		- ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_4ZWPWYZR9GHHFS8.webp)
	- 命中断点
		- ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_88CKH4ZV697PD5N.webp)
- 热加载
	- ida-qscripts勾选指定idapython脚本后,当修改脚本后,会触发插件reload实现重新载入脚本，自动更新上去了

## 5.clion 配置 idacpp开发环境(这里三个端一样)

>
> 选择cpp插件的原因肯定是性能了,毕竟开发起来麻烦,但是c++默认比py快20倍,在某些场景很难不用吧,比如一个混淆代码的块有上千个,测试用python的d810跑这种大型函数+单规则处理,耗时5分多钟,电脑cpu i9了
>
>
>

- 代码提示配置
	- camkefile中添加ida目录
		- ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_B9T253EFNADCEKY.webp)
		- 这边导入就不报错了
			- ![图片描述](https://bbs.kanxue.com/upload/attach/202312/788622_CQWAXFV3NW6Z34Q.webp)
- 简单的插件模板

| 12345678910111213141516171819202122232425262728293031323334 | `#include <ida.hpp>``#include <idp.hpp>``#include <loader.hpp>``#include <kernwin.hpp>` `plugmod_t *idaapi init(``void``)``{``msg(``"Plugin initialized!\n"``);``return` `PLUGIN_OK;``}` `void` `idaapi term(``void``)``{``msg(``"Plugin term()\n"``);``}` `bool` `idaapi run(``size_t` `arg)``{``msg(``"Plugin run()\n"``);``return` `true``;``}` `plugin_t PLUGIN =``{``IDP_INTERFACE_VERSION,``PLUGIN_UNL,` `//需要这个标记,否则不触发qscripts``init,``term,``run,``""``,``""``,``"Sample plugin"``,``""``};` |
|-|-|

| 1234567891011121314151617 | `/``/``cmakefile 配置``cmake_minimum_required(VERSION` `3.26``)``project(ByeObf)``set``(CMAKE_CXX_STANDARD` `20``)``#set(CMAKE_RUNTIME_OUTPUT_DIRECTORY /Applications/IDAPro8.3/ida.app/Contents/MacOS/plugins)` `include_directories(``/``Applications``/``IDAPro``/``ida.app``/``Contents``/``MacOS``/``plugins``/``hexrays_sdk``/``include``/``)``include_directories(``/``Applications``/``IDAPro``/``ida.app``/``Contents``/``MacOS``/``idasdk_pro``/``include``/``)`  `#导入idaapi的目录``set``(PLUGIN_NAME byeobf)``set``(PLUGIN_SOURCES library.h library.cpp)``set``(PLUGIN_OUTPUT_NAME ${PLUGIN_NAME})``set``(PLUGIN_RUN_ARGS` `"-t"``)` `include($ENV{IDASDK}``/``ida``-``cmake``/``addons.cmake)` |
|-|-|

| 1 | `编译64位插件定义EA64即可` |
|-|-|

- 修改ida-cmake的addons.cmake改编译后的插件生成目录
	- 修改 LIBRARY_OUTPUT_DIRECTORY 、RUNTIME_OUTPUT_DIRECTORY_${cfg} 属性,改为/path/to/ida/plugins
- 热重载
	- 1.模板定义了插件名byeobf,需要创建两个文件 byeobf.py 和 byeobf.py.deps.qscripts,确保**插件名**要一样
	- 2.byeobf.py内容

	| 12345678910111213 | `import` `time``import` `idaapi` `# Give the linker time to finish flushing the binary``time.sleep(``1``)` `# Optionally clear the screen:``#idaapi.msg_clear()` `# Load your plugin and pass any arg value you want``idaapi.load_and_run_plugin(``'byeobf'``,` `0``)` `# Optionally, do post work, etc.` |
	|-|-|
	- 3.deps.qscripts内容
		- 改为你要触发的插件绝对路径

	| 1 | `/triggerfile /keep /Applications/IDAPro/ida.app/Contents/MacOS/plugins/byeobf64.dylib` |
	|-|-|
	- 4.将byeobf.py 和 byeobf.py.deps.qscripts 放到 /path/to/ida/plugins
	- 5.重启ida打开qscripts,导入并双击 byeobf.py,此时你每次重新编译idacpp改动都会被自动载入到ida中了
	- 6.效果图请看 ida-qscripts项目
- 搭配热重载动态调试
	- 1.clion --> run --> Attach to Process --> 选择你的ida进程号, 后续这个附加**不用关闭**
	- 2.设置断点
	- 3.触发等待命中,开始愉快的带着debug环境开发吧！

## 6.vs 配置 idacpp开发环境 idapython环境

| 1 | `-` `这里大差不差都参考上述改动即可` |
|-|-|

ida-win 7.7下载: <https://bbs.kanxue.com/thread-276531.htm>

---

# 回复

## 回复 by 初恒 (#2)

*2023-12-7 14:51*

这敏感词到底是哪个噢

## 回复 by xxRea (#3)

*2023-12-12 20:56*

感谢分享

## 回复 by 八岛 (#4)

*2024-1-30 17:24*

感谢，非常有用

## 回复 by 秋狝 (#5)

*2024-1-31 09:35*

感谢分享

## 回复 by st0ne (#6)

*2024-1-31 09:48*

感谢分享

## 回复 by bullyxy (#7)

*2024-2-27 16:09*

用 pycharm 来调试 ida 脚本，在代码中插入下面代码连接 pycharm

```

```
if DEBUG:
    import pydevd_pycharm
    pydevd_pycharm.settrace('localhost', port=2222, stdoutToServer=True, stderrToServer=True)
```

```

就会显示这个

![image](https://bbs.kanxue.com/upload/attach/202402/790572_NNV7JK9BHYNNAQN.webp)

我明明是同一个文件，为啥会这样呢？

## 回复 by bullyxy (#8)

*2024-2-27 16:11*

配置也是一样的

## 回复 by 初恒 (#9)

*2024-2-27 16:37*

这个是python弹了异常，但是pycharm调试的时候跳不到源码那里吧，就弹这个错。 自己调试的时候记住触发这个错的那一行，不让他触发就好了。

## 回复 by 疯火戏猪猴 (#10)

*2024-9-15 09:57*

谢谢大佬分享 真棒![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by bluegatar (#11)

*2024-9-18 00:11*

开发脚本的是大牛啊

## 回复 by calleng (#12)

*2024-10-31 11:46*

这个发帖，我的天呀，真是极度精简， ida9.0 的适配， 在 Linux 下， 在 macOS 下， 基本跑通点点， 技术是专注练习出来的。
作者想说的话，只是够自己用， 或者懂开发的老手，一遍过，就知道怎么回事，经验丰富，

作为菜鸡， 想一想， 系统2天， 搞明白 2天， IDA 基础 2个月。 ---》 后续官方 cpp sdk 用多了，看外国人的教程多了就明白怎么回事了。
看了，Qscript 的 作者的原帖， 视频。结合 作者的文章， 真的漏了太多，太多。 满不在意，不过脑，就是笨。自学的路上多么的痛苦，但是有了自己解决和排错的能力，非常重要， 也得感谢现在的AI这么强，辅助学习。
所以， 老手说，我看了不下10遍， 每一遍都是一次收获。！！

## 回复 by calleng (#13)

*2024-10-31 22:10*

Native Plugins 开发看得老明白了。
Python Plugins 开发，真愣了3天。![image](https://bbs.kanxue.com/view/img/face/3.gif)
为啥，巨佬一句话，小白要看3次，每次分别是一天， pycharm 调试 IDA 那么牛逼的功能，code自动补全， 调试py的变量下断监控修改，自动热重载，含糊其辞。作者太省略了，小白难懂啊。｜

## 回复 by 初恒 (#14)

*2024-11-1 22:17*

>
> [calleng](https://bbs.kanxue.com/user-304186.htm)
>
>  Native Plugins 开发看得老明白了。
> Python Plugins 开发，真愣了3天。[em_3]
> 为啥，巨佬一句话，小白要看3次，每次分别是一天， pycharm 调试 IDA 那么 ...
>
>

![image](https://bbs.kanxue.com/view/img/face/52.gif)行吧我表达欠缺,考虑不周了

## 回复 by 养只猫不好么 (#15)

*2024-11-4 10:55*

感谢分享

## 回复 by 墨穹呢 (#16)

*2024-11-4 11:45*

mac使用clion编译不出来，提示报错：
make[3]: *** No rule to make target `idasdk90/lib/x64_mac_clang_64/libida.dylib', needed by `idasdk90/bin/plugins/mysample.dylib'.  Stop.
make[3]: *** Waiting for unfinished jobs....

## 回复 by 初恒 (#17)

*2024-11-4 18:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  墨穹呢](https://bbs.kanxue.com/user-886838.htm)
>
>  mac使用clion编译不出来，提示报错：
> make[3]: *** No rule to make target `idasdk90/lib/x64_mac_clang_64/libida.dyl ...
>
>

使用ida 之前泄露的sdk进行编译试试，不要用正式版的泄露，看起来文件缺失了。

## 回复 by calleng (#18)

*2024-11-5 10:35*

>
> [初恒](https://bbs.kanxue.com/user-788622.htm)
>
>  [em_52]行吧我表达欠缺,考虑不周了
>
>

没有那个意思，你是话中有话， 都写得明明白白的在截图里面躺着的。
就看有心人，能不明白作者的意图了。
对于只看文字的表述的人，走点，拖点，自以为是的人，就是这样，让他看不懂。
我就是被你降服之前的那个自以为是的那个YING。![image](https://bbs.kanxue.com/view/img/face/86.gif)

## 回复 by 初恒 (#19)

*2024-11-5 14:14*

>
> [calleng](https://bbs.kanxue.com/user-304186.htm)
>
>  没有那个意思，你是话中有话， 都写得明明白白的在截图里面躺着的。
> 就看有心人，能不明白作者的意图了。
> 对于只看文字的表述的人，走点，拖点，自以为是的人，就是这样，让他看不懂。
> 我就是被你降服之前 ...
>
>

哈哈，给你点个赞![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 墨穹呢 (#20)

*2024-11-5 14:24*

>
> [初恒](https://bbs.kanxue.com/user-788622.htm)
>
>  使用ida 之前泄露的sdk进行编译试试，不要用正式版的泄露，看起来文件缺失了。
>
>

用的就是泄露版里边的sdk，似乎是对mac的支持有限

## 回复 by calleng (#21)

*2024-11-5 20:42*

看了那个老外的视屏，莫说了。基本是IDA砖家级别，果断订阅。
然后， 他的 Qscript的视屏看了10遍， Native 插件没想到先搞定了。
py插件，花了2天才看明白。
初恒是看雪的砖家级别了，如果花点心思，估计就是真砖家了。![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by kingking888 (#22)

*2024-11-27 11:48*

麻烦出一篇IDAPRO 9.0
