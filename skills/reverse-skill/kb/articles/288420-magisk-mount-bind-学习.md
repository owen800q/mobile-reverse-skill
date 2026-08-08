---
title: '[原创]magisk mount bind 学习'
url: https://bbs.kanxue.com/thread-288420.htm
tid: 288420
author: Thehepta
date: '2025-09-09'
tags: [Android安全, 原创, 基础理论]
crawled_at: '2026-08-08T10:47:15+00:00'
replies: 11
---

在很多年以前,我我第一次接触magisk的时候,我觉得这个东西很神奇,然后我试图搜索他的原理,只有一种关于systemless的说法,后来在一些学习以后,我知道mount bind,并且写了 https://bbs.kanxue.com/thread-276652.htm 这个博客,但是总是觉得一直半解,有很多东西没有非常清晰.而这一篇主要来详细讲解magisk所谓文件替换的这个概念.

## mount bind 挂载技术讲解

### 挂载回顾

我们都知道mount 是挂载,挂载是将一个设备挂载到一个目录上,然后就可以通过这个挂载目录访问这个设备中的数据了,但是被挂载的目录原来的内容,会被挂载的设备的内容覆盖,导致完全不可见.

### mount bind目录挂载

mount bind 提供了一种目录挂载,就是将一个目录挂载到另一个目录的位置,这其实是一种非常浅显的解释,但是很多人只能通过这种方式才能理解和使用他的功能

| 12345 | `/``data``/``a``/``└── file_a.txt` `/``data``/``b``/``└── file_b.txt` |
|-|-|

现在我们执行一个 mount --bind命令：

| 1 | `mount` `-``-``bind` `/``data``/``a` `/``data``/``b` |
|-|-|

结果

| 12 | `/``data``/``b``/`  `（实际上是` `/``data``/``a 的“镜像”）``└── file_a.txt    ← 看到的是` `/``data``/``a 的文件` |
|-|-|

mout bind 的这个功能可以实现目录内容的替换

### mount bind 文件挂载

mount bind 不仅有一种目录的替换,他还具备单体文件的替换:

假设原始系统文件：

| 12 | `/``system``/``build.prop``└── (原始内容，包含 ro.product.model``=``PhoneA)` |
|-|-|

我们把修改后的文件放在 /data/local/tmp/build.prop：

| 12 | `/``data``/``local``/``tmp``/``build.prop``└── (修改后内容，ro.product.model``=``PhoneB)` |
|-|-|

执行 mount --bind 替换

| 1 | `mount` `-``-``bind` `/``data``/``local``/``tmp``/``build.prop` `/``system``/``build.prop` |
|-|-|

这个时候 /system/build.prop 中的文件内容已经被替换为了 /data/local/tmp/build.prop 中的内容.

### 底层核心原理和文件节点视图

#### 视图问题

我在很长时间内不能理解这个问题,导致不能自如的运用这个技术,我们在看这个技术的时候,要把目光往下移,所谓文件和目录,他只是文件系统中的一个节点,而我们通过使用节点去访问底层的真正的文件数据,所以节点,只是一个通往真正数据的入口,而入口后面才是真正的数据,所以数据是什么,在于入口通往哪个数据.

### 通过挂载点替换文件节点

我们大部分使用挂载都是将设备挂载到目录上,文件和目录其实都一样,都是文件节点inode,都可以进行节点的挂载,从而改变了这个节点通往的位置,而提供这个功能就是mount bind,这是mount bind 可以进行文件挂载的核心原理

## mount bind 实现 overlayfs 目录合并

### 代码讲解

根据我们前面讲的原理, mount bind 只有文件节点的替换功能,好像不具备添加文件的功能啊,而overlayfs 天生就具备两个目录合并,并且可以修改读写属性的功能,可谓天生高贵

mount bind 代码overlayfs实现

| 12345678910111213141516171819202122232425262728293031323334353637 | `int` `main(``int` `argc, char` `*``*``argv) {` `char` `*``src``=``"/apex/com.android.art/bin"``;` `char` `*` `merge``=``"/apex/com.android.abc/bin"``;`  `auto src_dp` `=` `opendir(src);` `int` `src_fd` `=` `open``(src, O_RDONLY \| O_DIRECTORY);` `if` `(src_fd` `=``=` `-``1``) {` `perror(``"open faile, is not dir"``);` `return` `0``;` `}` `char buf[``4096``];` `char path[``4096``];` `for` `(dirent` `*``entry; (entry` `=` `readdir(src_dp));) {` `if` `(strcmp(entry``-``>d_name,` `"."``)` `=``=` `0` `\|\| strcmp(entry``-``>d_name,` `".."``)` `=``=` `0``) {` `continue``;` `}` `sprintf(path,``"%s/%s"``,merge,entry``-``>d_name);` `struct stat st;` `fstatat(src_fd, entry``-``>d_name, &st, AT_SYMLINK_NOFOLLOW);` `if` `(S_ISLNK(st.st_mode)) {` `readlinkat(src_fd, entry``-``>d_name, buf, sizeof(buf));` `symlink(buf, path);` `}` `else``{` `sprintf(buf,` `"%s/%s"``, src, entry``-``>d_name);` `auto mode` `=` `st.st_mode &` `0777``;` `if` `(S_ISDIR(st.st_mode))` `mkdir(path, mode);` `else` `close(``open``(path, O_CREAT \| O_WRONLY \| O_CLOEXEC, mode));`  `mount(buf, path, nullptr, MS_BIND, nullptr);` `}`  `}` `mount(merge,src, nullptr, MS_BIND\|MS_REC, nullptr);` `return` `0``;` `}` |
|-|-|

这段代码的思路：

- 遍历 /apex/com.android.art/bin 中所有的文件
- 根据 /apex/com.android.art/bin 中的文件在 /apex/com.android.abc/bin 目录创建对应的文件或者目录
- 将 /apex/com.android.art/bin 这个目录中的所以子节点挂载到 /apex/com.android.abc/bin 中
- 第二步，/apex/com.android.abc/bin 中创建了对应的名字的文件,现在将文件节点全部挂载过来完成替换
- 将 /apex/com.android.abc/bin 目录,挂载到 /apex/com.android.art/bin 中,
- 将/apex/com.android.abc/bin中挂载的节点通过递归挂载的方式,挂载到 /apex/com.android.art/bin 中,实现了/apex/com.android.art/bin 中的文件添加

### 挂载视图

| 123456789101112131415161718192021222324 | `tmpfs on` `/``apex``/``com.android.abc` `type` `tmpfs (rw,seclabel,relatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.abc``/``bin``/``dex2oat64` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.abc``/``bin``/``dalvikvm32` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.abc``/``bin``/``artd` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.abc``/``bin``/``dexlist` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.abc``/``bin``/``dex2oat32` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.abc``/``bin``/``dexoptanalyzer` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.abc``/``bin``/``odrefresh` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.abc``/``bin``/``dalvikvm64` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.abc``/``bin``/``profman` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.abc``/``bin``/``dexdump` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.abc``/``bin``/``oatdump` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``tmpfs on` `/``apex``/``com.android.art``/``bin` `type` `tmpfs (rw,seclabel,relatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.art``/``bin``/``dex2oat64` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.art``/``bin``/``dalvikvm32` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.art``/``bin``/``artd` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.art``/``bin``/``dexlist` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.art``/``bin``/``dex2oat32` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.art``/``bin``/``dexoptanalyzer` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.art``/``bin``/``odrefresh` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.art``/``bin``/``dalvikvm64` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.art``/``bin``/``profman` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.art``/``bin``/``dexdump` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)``/``dev``/``block``/``dm``-``26` `on` `/``apex``/``com.android.art``/``bin``/``oatdump` `type` `ext4 (ro,dirsync,seclabel,nodev,noatime)` |
|-|-|

#### 二次挂载实现原始文件不修改

/apex/com.android.art/bin/dex2oat64 -> 挂载到 /apex/com.android.abc/bin/dex2oat64 -> 挂载到 /apex/com.android.art/bin/dex2oat64

#### 递归挂载

当我们将/apex/com.android.art/bin 中所有的文件挂载到 /apex/com.android.abc/bin/ 目录下以后,如果直接将 /apex/com.android.abc/bin/ 挂载到 /apex/com.android.art/bin ,这个时候你会发现,挂载过去以后,/apex/com.android.art/bin/dex2oat64 这种art原始文件,是0,是个空文件,这是因为普通挂载是只会显示挂载的这个节点的数据的,而dex2oat64 是别的地方挂载过来的,不是他的原始文件,所以无法显示,这个时候,我们需要使用递归挂载

| 1 | `mount(merge,src, nullptr, MS_BIND\|MS_REC, nullptr);` |
|-|-|

这个递归挂载,其实就是我们手动,将/apex/com.android.abc/bin/ 的节点,在一个一个挂载到/apex/com.android.art/bin目录下
android 命令行好像不支持递归挂载

## magisk root 检测和隐藏

### magisk root的实现

我们已经讲过了 如何通过mount bind 实现overlayfs ,所以想实现root 往/system/bin这个目录中添加文件也是轻而易举的事情,我们看下mount的 挂载关于root实现的/system/bin 目录的挂载

| 12345678910111213141516171819 | `/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``abb` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``abx` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``abx2xml` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``am` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``apexd` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``app_process32` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``app_process64` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``appops` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``appwidget` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``atrace` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``audioserver` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``auditctl` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``awk` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``badblocks` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``bc` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``bcc` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``blank_screen` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``blkid` `type` `ext4 (ro,seclabel,relatime)``/``dev``/``block``/``dm``-``5` `on` `/``system``/``bin``/``bmgr` `type` `ext4 (ro,seclabel,relatime)` |
|-|-|

我们可以看到,他有很多的/system/bin 目录子节点的挂载,这跟我们前面说的实现文件目录文件添加的方法是一样的

### root的检测

关于root的检测有很多,我们没必要花大篇幅挨个讲,因为很多都是可以解决的,并且magisk已经解决过的.我们只说关于PATH 路径su命令所在文件的检测

#### 为什么要进行su路径检测

这其实算是一个约定俗称的使用方式导致的检测方法,作为一款root工具,肯定要提供su功能,而很多使用root的工具,他们都默认使用su命令来获取和执行root,这种大趋势下,一个提供root的项目,必然要提供一个命令中可以直接调用的su,你确实也可以改成kp,但是很多使用的app,因为完全无法使用,对于开发者来说没影响,但是对于广大使用root权限的人来说,者影响很大,因为使用,所以检测.

### magisk 隐藏root的方式

这个其实很简单,将特定进程的命名挂载空间/system/bin 所有子节点挂载卸载,然后卸载掉 system/bin 目录的挂载,这样root就不可见了,我说的可能有点狭隘,可以卸载magisk 所有相关的命名挂载,将他恢复到原来的样子,这个magisk已经实现了,可以完美隐藏root

### magisk 针对于app开启的权限和root套接字的隐藏

 magisk 是通过 服务实现的root权限,我们执行su,会通过套接字去请求服务,而android 处于selinux 强制模式下,所以,如果没有权限,app根本无法通过 selinux访问到root权限的套接字,所以magisk其实为所有的app开启了套接字权限

| 12 | `/``/` `Allow these processes to access MagiskSU` `and` `output logs``allow([``"zygote"``,` `"shell"``,` `"platform_app"``,``"system_app"``,` `"priv_app"``,` `"untrusted_app"``,` `"untrusted_app_all"``],[proc], [``"unix_stream_socket"``], [``"connectto"``,` `"getopt"``]);` |
|-|-|

而这个unix_stream_socket 有两种,命名套接字 和 匿名套接字,而magisk使用的是 命名套接字 ,这是一种需要路径的套接字,我开始的时候认为这很low,因为这需要一个位置来存放,后来发现这是故意为了隐藏root对于套接字的检测设计的,当需要隐藏root的时候,将套接字所在的路径一并卸载,这样根本访问不到套接字,即使有权限其实也无所谓了.
但是这告诉我们另一个问题,如果你开发一个magisk模块的开源项目,一定要注入,如果你使用 匿名套接字 ,会被检测工具通过connectto 检测到.

## mount bind 的懒卸载导致的注入缺陷

任何东西都是不完美的
现在有很多的检测工具去检测root,如果只是隐藏root来说mount bind 方案是足够的,但是有很多需要进行目录so文件添加,但是又要隐藏关于mount bind的挂载,这对于mount bind 来说,真的很难评

### 懒卸载技术

mount bind 挂载隐藏全靠懒卸载技术,当这个挂载节点中有被进程使用的时候,我们可以通过懒卸载将挂载信息从命名空间中删除 ,但是这个挂载的文件却不会立即卸载,而是当这个这个挂载的节点的使用者全部使用完毕以后才会卸载他.这个技术可以完美隐藏我们使用挂载进行文件替换,但是挂载节点中存在挂载信息的问题

### 注入目录未使用文件的检测尴尬

这个懒卸载技术,只能针对于正在使用的文件所在的节点,而对于没有使用文件的节点,是不会被懒卸载的,而是会被直接卸载,如果像su这种情况,我们需要完全的卸载su相关的所有内容,卸载以后,目录恢复原始的样子,这种情况下,根本用不到懒卸载技术,而是完全卸载节点规避检测.
但是如果我们需要注入,需要往系统库中插入so,然后通过dlopen直接寻找他,这样还可以防止外来路径的so检测,memfd检测等等,但是这就需要将so所在的目录的全部文件进行节点映射,但是却并不是所有的so文件都会使用,但我们注入的这个so一定会被使用,比如magisk的zygisk ,我们注入的libzygisk 一定会被使用,但是libzygisk注入到/system/lib64 中并不是所有的文件都正在都会被使用,尤其是,在我们进行卸载隐藏的使用,正在使用,这就导致了,如果我们要隐藏这个挂载节点,就需要将 libzygisk 所在目录的映射过来的子节点全部懒卸载,最好的情况是,这个目录下的所有文件都真正被使用,这个时候,全部都是懒卸载,但是如果,有一个映射过来的文件没有被使用,他就被直接卸载掉了,变成我们替换目录的空文件了,而这个时候,因为 libzygisk这个挂载目录的文件是被使用的,所有目录不会被卸载,但是他其中不被使用的映射的子节点全被卸载了,这个时候,检测下so空文件,或者在后续又要使用别的被卸载的so,libzygisk又一直在使用,无法触发卸载,那这个使用被卸载的这个so,就一直是空文件.

## mount bind 的优势和注入缺陷的解决

这个注入的缺陷,其实就是递归挂载子节点导致的,因为我们想要隐藏mount的挂载节点,就必须把所有文件挂载信息全部清楚掉,想要解决这个注入挂载的缺陷其实很简单,我们只需要不惜成本的把我们所要替换目录的全部内容全部直接复制过来,然后是使用替换的目录挂载到被替换的目录上,这样我们就可以用进行子节点的递归挂载了,而我们注入的库正在使用,这个目录节点就会触发懒卸载,而其中的文件都是真正的文件.但是这会造成磁盘使用空间X2,而mount bind 这个方案,可以在微乎其微的空间增加上完美的修改只读文件系统,向其中添加文件,所以只谈技术不谈使用场景完全是耍流氓.

- 通过 mount bind 微量增加文件节点实现只读文件系统的修改,没法完成对抗
- 通过文件目录子文件,然后使用mount bind, 可以配合懒卸载完成隐藏,但是空间最少膨胀两倍

### magisk 文件替换测试未果

有点懒,最后没试过magisk的文件替换,只是测试了当进程强制禁绝以后,libzygisk和模块都不会被使用,我估计magisk 这个文件添加功能,应该是具备我上面说的问题的,这个其实这东西单拿出来自己开发随便玩的,但是想要自动化,还想要隐藏完成对抗,估计不太行

## 最后

吹一波magisk
当我看明白了maigsk，才明白magisk的强大，虽然后续有apatch 和ksu 这样强劲的后来者，但是magisk在当下依然毫不逊色，只不过很多人不懂他的思想，又急于求成，反而落了下成

就到这里把,累了,一天码了1w多字

---

# 回复

## 回复 by Thehepta (#2)

*2025-9-9 11:52*

先占个楼

## 回复 by mb_iesvmzqc (#3)

*2025-9-9 13:23*

nb

## 回复 by iBa0 (#4)

*2025-9-9 17:18*

哟西 刚看了mounts的沙箱

## 回复 by wangzehua (#5)

*2025-9-9 19:36*

不明觉厉

## 回复 by 珍惜Any (#6)

*2025-9-9 19:54*

我那个四两拨千斤用的就是这种方式，还可以直接在内核里面直接全量IO重定向也行。这种方式会在mount有痕迹，需要mount文件隐藏 。这部分需要隐藏的数据在末尾，还好。但是你这文章还有一些点没写，比如你在挂载的时候文件正在使用，这种情况都需要考虑。

## 回复 by 随风而行aa (#7)

*2025-9-9 21:21*

不错不错

## 回复 by mb_ldbucrik (#8)

*2025-9-9 22:18*

感谢分享

## 回复 by Thehepta (#9)

*2025-9-10 14:14*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  我那个四两拨千斤用的就是这种方式，还可以直接在内核里面直接全量IO重定向也行。这种方式会在mount有痕迹，需要mount文件隐藏 。这部分需要隐藏的数据在末尾，还好。但是你这文章还有一些点没写，比如 ...
>
>

没必要隐藏在末位太low，mounts有mount的隐藏方式，既然决定挂载就要自己掌握使用时机，正在使用发生挂载这是使用的问题，不是挂载的问题，内核搞没啥问题，而且比较简单，但是我喜欢非内核方案

## 回复 by younghare (#10)

*2025-9-10 16:55*

你的分享对大家帮助很大，非常感谢！

## 回复 by 龙飞雪 (#11)

*2025-9-11 11:31*

学习了，感谢分享。

## 回复 by mb_cizqyhuh (#12)

*2025-11-14 16:10*

讲得很透彻，让我对Magisk的mount bind原理有了更清晰的认识。文件节点映射和二次挂载的方法确实很巧妙，虽然空间占用和懒卸载问题需要注意，但整体是个很实用的技术方案。我把相关知识点整理成了[思维导图](https://www.anygraphanywhere.com/automap/mindmap.html?link=1751446034783-1763107613529)，有兴趣可以参考。

![image](https://bbs.kanxue.com/upload/attach/202511/1040915_EVRT4JR3W4EBYD3.webp)
