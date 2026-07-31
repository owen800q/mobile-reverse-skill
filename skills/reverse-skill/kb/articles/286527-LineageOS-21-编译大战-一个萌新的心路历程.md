---
title: '[原创] LineageOS-21 编译大战！—— 一个萌新的心路历程 ☆'
url: https://bbs.kanxue.com/thread-286527.htm
tid: 286527
author: OrionisLi
date: '2025-04-18'
tags: [Android安全, 原创, 系统相关]
crawled_at: '2026-07-31T14:11:18+08:00'
replies: 11
---

# LineageOS-21 编译大战！—— 一个萌新的心路历程 ☆

*kira~☆ 本文将同步闪耀于 CSDN & 看雪论坛，请多指教！*

## 0x01 碎碎念 Time~

最近闲得快要长蘑菇了，于是淘来一台二手 *LG G8 ThinQ* (代号是 `alphaplus` 哦~)，打算让它成为我的新玩具... 啊不，是备用机！然后捏，一个大胆的想法突然降临：何不亲手为它打造一套 LineageOS 呢？
说干就干，冒险的帷幕，就此拉开！(•̀ㅂ•́)و✧

## 0x02 冒险前的物资准备！

1. **大量的时间 & 钢铁般的耐心** (非常重要！说三遍！后面还会再说！)
2. **Linux 大陆通行证** (强烈推荐物理机，跑起来才够劲！虚拟机什么的... 稍稍有点勉强啦。WSL2 也要小心，特别是 WSL1，那是万万不可的哟~‍♀️)
3. **畅通无阻的网络** (我们需要从 GitHub 召唤 **Vendor Blobs** 和 **Kernel** 这些神秘力量！后面会细说。可怜我的校园网只有 7Mb/s，光是拉源码就花了一整天... ！)
4. **一个足够大的磁盘空间** (咱的口袋是 391.8GB，编译完成后还剩大约 67.1GB，给小伙伴们参考一下~ 至少需要 400GB 才稳妥哦！)
5. **强力的 CPU 核心** (我用的是 i7-9750H... 没错，就是那台服役 6 年的老伙计笔记本！编译过程大概跑了一整天... 核心越多越好，像八爪鱼那样！)
6. **至少 32GB 的内存** (不开 swap 会直接宕机！亲身经历 T_T... 建议设置 12GB 的 swap 结界，不然真的会死得很惨...)
7. **再次强调：大量的时间 & 钢铁般的耐心！** (这是成为魔法师... 啊呸，编译大师的必备素质！)

## 0x03 羁绊的开始！Let's Go!

### Step 1: 搭建我们的秘密基地 (环境准备)

首先，得把我们的 Linux 小窝打造成适合编译魔法的环境。需要安装一些神秘的咒语。

**本教程基于 Archlinux 魅魔，Ubuntu 小姐姐部分如果有误，请温柔地指出，我会立刻修正哒~ (没有特别标注的话，就是两个系统通用的咒语哦！)**

**！！！注意注意！！！编译的时候千万不要用 root 大人的权限，会引来不必要的麻烦哦！Σ( ° △ °|||)**

**For Archlinux 小伙伴:**

| 1234567 | `# 先来个全身心的大扫除和升级！``sudo` `pacman -Syyu``# 然后召唤我们需要的工具伙伴们！``sudo` `pacman -S --needed base-devel git jdk17-openjdk python python-pip ccache \``libxml2 ncurses zlib openssl pngcrush schedtool imagemagick \``bc` `android-tools` `rsync` `wget unzip zip p7zip curl \``libxslt lz4 patchelf coreutils findutils` `gawk` `grep` `sed` `git git-lfs` |
|-|-|

**For Ubuntu 小伙伴:**

| 1234 | `# 同样，先给系统梳梳毛，升升级~``sudo` `apt update &&` `sudo` `apt upgrade``# 召唤 Ubuntu 平台的工具伙伴们！``sudo` `apt` `install` `bc` `bison build-essential ccache curl flex g++-multilib gcc-multilib git git-lfs gnupg gperf imagemagick lib32readline-dev lib32z1-dev libdw-dev libelf-dev liblz4-tool lz4 libsdl1.2-dev libssl-dev libxml2 libxml2-utils lzop pngcrush` `rsync` `schedtool squashfs-tools xsltproc zip zlib1g-dev libwxgtk3.0-dev lib32ncurses5-dev libncurses5 libncurses5-dev` |
|-|-|

### Step 1.5: 召唤 Ccache 酱，开启高速模式！✨

诶嘿嘿~ 想要让之后的编译快到飞起吗？那就快来召唤 **Ccache 酱** 这位时间魔法师吧！她能记住你编译过的东西，下次再编译同样的内容时，就能瞬间完成，大大缩短等待时间哦！(ﾉ´ヮ´)ﾉ*:･ﾟ✧

要召唤 Ccache 酱，你需要咏唱以下咒语：

| 12 | `export` `USE_CCACHE=1``export` `CCACHE_EXEC=``/usr/bin/ccache` |
|-|-|

然后，记得把这两行神秘代码也添加到你的 `~/.bashrc` (或者 `~/.zshrc`，看你用哪个 Shell 啦) 文件里，这样每次打开终端，Ccache 酱就会自动准备好为你加速啦！

接下来，要告诉 Ccache 酱她能使用多少硬盘空间来存放她的编译产物。念这个咒语：

| 12 | `# 这里以分配 30GB 为例，可以根据自己的硬盘大小调整哦``ccache -M 30G` |
|-|-|

这里的 `30G` 就代表 Ccache 酱可以征用 30GB 的硬盘空间哦。这个咒语只需要成功咏唱 **一次** 就好~

**Ccache 酱需要多大空间呢？**

- 一般来说，给她分配 **25GB 到 100GB** 的空间，就能让编译速度发生翻天覆地的变化！(举个栗子，原本 1 小时的漫长等待，可能咻的一下就缩短到 20 分钟！)
- 如果你只打算为一个老婆… 啊不，一台设备编译 ROM，那么 **25GB-50GB** 就足够 Ccache 酱施展拳脚啦。
- 但如果你是个“后宫王”体质，要为好几位内核源码不同的设备后宫编译，那最好给她准备 **75GB-100GB** 的大 house！
- **不过要注意！** 这部分空间会被 Ccache 酱 **永久占据** (除非你手动清理或卸载她)，所以在决定大小前要好好掂量一下自己的硬盘容量，别不小心撑爆了哟！

**还有个小秘技！Ccache 酱的压缩魔法！**

你可以选择开启 Ccache 酱的压缩模式！虽然这可能会让她的编译速度稍微慢一丢丢，但好处是能在同样的空间里塞下更多的缓存文件！更省空间了耶！

要开启压缩模式，就念这个咒语 (同样，只需一次)：

| 1 | `ccache -o compression=``true` |
|-|-|

 **小贴士：** 如果开启了压缩模式，之前设定的缓存大小就可以适当调小一点啦 (比如只为一个设备编译的话，大概 **20GB** 可能就够用了~)

好啦！有了 Ccache 酱的加持，我们的编译大业就能更加顺畅啦！继续前进！➡️

### Step 2: 开辟源码的圣域 (创建源码目录)

就在咱的用户目录下建一个新家吧~

| 1 | `mkdir` `~``/LineageOS` |
|-|-|

然后，瞬移进去！

| 1 | `cd` `LineageOS` |
|-|-|

### Step 3: 获取 repo 酱这个传送门管理员 (设置 repo)

| 12345678 | `mkdir` `~``/bin``# 温馨提示：这条命令是把 ~/bin 目录暂时加入到当前 Shell 的寻路列表 (PATH) 里，``# 新开终端或者重启电脑后就失效啦。想让它一直有效？把它加到 ~/.bashrc 或 ~/.zshrc 文件里吧！``PATH=~``/bin``:$PATH``# 从清华大学的神秘宝库里请来 repo 酱！``curl https:``//mirrors``.tuna.tsinghua.edu.cn``/git/git-repo` `-o ~``/bin/repo``# 赋予 repo 酱执行魔法的力量！``chmod` `a+x ~``/bin/repo` |
|-|-|

### Step 4: 设定传送目标 (配置仓库)

我们选择清华大学的镜像作为主要传送点。(当然 BFSU 镜像在 LineageOS-21.0 时也能成功抵达终点，但 LineageOS-22.1 遇到了 VNDK33 无法召唤的问题，22.2 又遇到了奇怪的编译错误... 可能是版本更新太快，同步还没跟上？)

**简单对比一下两大传送门 (截至我上次观察时... 诶～我上次观察是啥时候来着？)：**

- **清华源 (TUNA):** 同步范围超广，但有时感觉拉取速度像是在爬... (不知道现在有没有变快？)
	- ![image](https://bbs.kanxue.com/upload/attach/202504/1033399_DR74PAA2FKADEAJ.webp) -> 清华酱的 AOSP 代码同步状态展示图 (看起来很大很全！)
	- ![image](https://bbs.kanxue.com/upload/attach/202504/1033399_NDJ28UV7V52PJQT.webp) -> 清华酱的 LineageOS 代码同步状态展示图 (感觉也不错！)
- **北外源 (BFSU):** 速度飞快！但可能因为同步有延迟，偶尔会找不到最新的零件。
	- ![image](https://bbs.kanxue.com/upload/attach/202504/1033399_NSUAQMQ2DZCYWAX.webp) -> BFSU 酱的 AOSP 代码同步状态展示图 (明显小很多)
	- ![image](https://bbs.kanxue.com/upload/attach/202504/1033399_4TN6HCRARBNPW9T.webp) -> BFSU 酱的 LineageOS 代码同步状态展示图 (同样，可能不是最新鲜的)

**结论：** 清华更稳妥全面，但可能慢；BFSU 快但可能有坑。大家可以根据自己的网络情况和追求选择信仰！(当然，直连官方 GitHub/GoogleSource 的都是真·勇士！这件事实在是泰裤辣！)

这里以 BFSU 源为例 (因为它在我的 LineageOS-21 冒险中成功了嘛)：

| 1234 | `# 赋予 repo 酱执行魔法的力量 (如果前面做了就不用重复啦)``# chmod a+x ~/bin/repo``# 初始化我们的冒险地图！指定 BFSU 为传送起点，目标是 lineage-21.0 分支，并开启 LFS 支持！``repo init -u https:``//mirrors``.bfsu.edu.cn``/git/lineageOS/LineageOS/android``.git -b lineage-21.0 --git-lfs` |
|-|-|

**小小解说：**

- `-u`: 指定那个记录着所有宝藏地点 (manifest 仓库) 的 URL。
- `-b`: 我们要探索哪个版本的世界线 (分支)。
- `--git-lfs`: 开启对“大件行李”(Git Large File Storage) 的支持，有些宝藏需要这个才能搬运哦 (具体是哪些嘛... 咱也不知道，咱也不敢问)。

### Step 5: 向 Git 大神登记身份 (配置 Git)

第一次进行大规模召唤 (拉取操作) 前，需要先跟 Git 大神报上名号：

| 12 | `git config --global user.name` `"<你的昵称或者名字啦，记得去掉尖括号哦>"``git config --global user.email` `"<你的邮箱地址，也去掉尖括号哈>"` |
|-|-|

### Step 6: 开始伟大的召唤仪式！(拉取源码)

**先悄悄修改一下传送契约 `.repo/manifests/default.xml`：**

把这段：

| 123456789101112131415 | `<``remote`  `name``=``"github"``fetch``=``"https://github.com/"` `/>` `<``remote`  `name``=``"private"``fetch``=``"ssh://git@github.com"` `/>` `<``remote`  `name``=``"aosp"``fetch``=``"https://mirrors.bfsu.edu.cn/git/AOSP"``review``=``"android-review.googlesource.com"``revision``=``"refs/tags/android-14.0.0_r67"` `/>` `<``default` `revision``=``"refs/heads/lineage-21.0"``remote``=``"github"``sync-c``=``"true"``sync-j``=``"4"` `/>` |
|-|-|

改成这样 (具体修改可以参考镜像站点的帮助文档)：

| 1234567891011121314151617 | `<``remote`  `name``=``"github"``fetch``=``"https://github.com/"` `/>``<!-- 新增一个指向 LineageOS 镜像的 remote -->``<``remote`  `name``=``"lineage"``fetch``=``"https://mirrors.bfsu.edu.cn/git/lineageOS/"``review``=``"review.lineageos.org"` `/>``<!-- ... 其他 remote ... -->``<``remote`  `name``=``"aosp"``fetch``=``"https://mirrors.bfsu.edu.cn/git/AOSP"``review``=``"android-review.googlesource.com"``revision``=``"refs/tags/android-14.0.0_r67"` `/>` `<!-- 把 default 的 remote 指向我们新增的 'lineage'，并可以调大 sync-j 的值（比如12）来加速召唤 -->``<``default` `revision``=``"refs/heads/lineage-21.0"``remote``=``"lineage"``sync-c``=``"true"``sync-j``=``"12"` `/>` |
|-|-|

**然后，启动召唤法阵！**

| 1 | `repo` `sync` `--no-clone-bundle` |
|-|-|

加 `--no-clone-bundle` 这个小咒语是为了防止某些调皮的仓库 (比如 `Lineage_framework_base`) 在同步时闹别扭，出现 *bundle* 错误。

**召唤途中可能会遇到小波折**，不要慌！按下 `Ctrl + C` 中断仪式，然后重新念咒：

| 1 | `repo` `sync` `--no-clone-bundle` |
|-|-|

**如果还不行，试试更强硬的姿态：**

| 1 | `repo` `sync` `--fail-fast` |
|-|-|

**但有时，会遇到极其可怕的恶性错误：**

| 12345678 | `出现错误：Fetching:  0% (7``/1471``) 0:05 \| 14 jobs \| 0:04 LineageOS``/android_bionic` `@ bionic``致命错误：不是 git 仓库：``'/mnt/swapdisk/Android/LineageOS/.repo/projects/dalvik.git'``platform``/dalvik``:``致命错误：不是 git 仓库：``'/mnt/swapdisk/Android/LineageOS/.repo/projects/dalvik.git'``platform``/dalvik``: sleeping 4.0 seconds before retrying``致命错误：不是 git 仓库：``'/mnt/swapdisk/Android/LineageOS/.repo/projects/dalvik.git'``error: Cannot fetch platform``/dalvik` `from https:``//mirrors``.bfsu.edu.cn``/git/AOSP/platform/dalvik``... (更多类似的报错) ...` |
|-|-|

这是我在尝试召唤 LineageOS-22.1 时遇到的噩梦...

遇到这种级别的错误，基本就是绝境了... (偷偷用 `git clone` 塞东西到 `.repo/project` 里面？想都别想！`repo` 酱会用小皮鞭严厉惩罚每一个不听话的宝宝；中途更换代码源到 `googlesource` 或 `github`？她同样会惩罚那些三心二意的宝宝，必须对选择的源保持忠贞不渝！)

**实在没办法了，可以试试这些最后的挣扎：**

1. **强制对问题仓库进行灵魂同步：**

| 12 | `# 比如 dalvik 仓库出错了``repo` `sync` `--force-``sync` `platform``/dalvik` |
|-|-|
2. **物理超度损坏的仓库，然后重新召唤：**

| 1234 | `# 先删除本地缓存的问题仓库``rm` `-rf .repo``/projects/platform/dalvik``.git` `# 注意路径需要根据实际错误调整(在这里使用的是相对路径)``# 再单独召唤它``repo` `sync` `platform``/dalvik` |
|-|-|
3. **如果以上都不行... 终极奥义：删库重来！**

| 1 | `rm` `-rf .repo` |
|-|-|

然后回到 **Step 4**，重新配置仓库 (`repo init`)。这次... 也许该考虑放弃国内镜像，直接拥抱官方源了 (虽然可能要经历漫长的等待... 大约 200GB 的数据量呢)。

| 1 | `repo init -u https:``//github``.com``/LineageOS/android``.git -b lineage-21.0 --git-lfs` |
|-|-|

之后，就是... 泡杯茶，看几集番，或者睡一觉吧... 等待法阵完成它的工作... 直到所有星辰归位... ✨

### Step 7: 召唤特定设备的神秘力量 (准备 Vendor Blobs 等)

**请务必查清你家设备的代号！可以去官方文档或者XDA这样的论坛找找看。**

在 `.repo` 目录下创建一个叫做 `local_manifests` 的小文件夹。在里面新建一个文件，名字可以叫 `<你的手机厂商>_manifest.xml` (比如 `lge_manifest.xml`)。然后，参考下面的模板抄写咒语：

| 123456789101112131415161718192021222324 | `<?``xml` `version``=``"1.0"` `encoding``=``"UTF-8"``?>``<``manifest``>``<!-- 先定义好远程的神秘力量来源地，方便后面召唤 -->``<!-- 注释的代码可以用来参考 -->``<!-- <remote name="lge-qcom-dev" fetch="https://github.com/lge-qcom-dev" revision="lineage-21" /> -->``<``remote` `name="<随便取个名字，比如 a_cool_repo>" fetch="<仓库地址，一定要对哦！>" revision="<仓库里对应的分支名，比如 lineage-21>" />` `<!-- 设备专属的 Vendor 力量 -->``<!-- <project path="vendor/lge/alphaplus" name="proprietary_vendor_lge_alphaplus" remote="lge-qcom-dev" /> -->``<``project` `path="vendor/<手机厂商>/<设备代号>" name="proprietary_vendor_<手机厂商>_<设备代号>" remote="<上面定义的名字>" />` `<!-- 设备专属的 Device Tree (设备树) -->``<!-- <project path="device/lge/alphaplus" name="android_device_lge_alphaplus" remote="lge-qcom-dev" /> -->``<``project` `path="device/<手机厂商>/<设备代号>" name="android_device_<手机厂商>_<设备代号>" remote="<上面定义的名字>" />` `<!-- 同芯片平台的通用 Vendor 力量 (如果你的设备有的话) -->``<!-- <project path="vendor/lge/sm8150-common" name="proprietary_vendor_lge_sm8150-common" remote="lge-qcom-dev" /> -->``<``project` `path="vendor/<手机厂商>/<处理器代号>-common" name="proprietary_vendor_<手机厂商>_<处理器代号>-common" remote="<上面定义的名字>" />` `<!-- 同芯片平台的通用 Device Tree (如果你的设备有的话) -->``<!-- <project path="device/lge/sm8150-common" name="android_device_lge_sm8150-common" remote="lge-qcom-dev" /> -->``<``project` `path="device/<手机厂商>/<处理器代号>-common" name="android_device_<手机厂商>_<处理器代号>-common" remote="<上面定义的名字>" />`  `</``manifest``>` |
|-|-|

**那么，这些神秘力量的地址在哪里找呢？**

很简单！去 GitHub 这个大宝库里搜索关键词，比如：

- `proprietary_vendor <手机厂商> <设备代号>`
- `android_device <手机厂商> <设备代号>`
- `proprietary_vendor <手机厂商> <处理器代号> common` (建议有)
- `android_device <手机厂商> <处理器代号> common` (建议有)

很多机型的这些宝贝都可以在 `TheMuppets` (木偶大佬！) 的 GitHub 仓库下找到 (但不一定是最新的哦)。想要最新鲜的？直接在 GitHub 搜索框里搜，像这样：

 ![image](https://bbs.kanxue.com/upload/attach/202504/1033399_PFBY8838DMXFEEA.webp)

点进搜索结果，找到看起来最靠谱的仓库(数量不多的话也可以依次查看，顺便看看作者有没有其他的库)，然后去看看它的 `Branches` (分支) 页面：

 ![image](https://bbs.kanxue.com/upload/attach/202504/1033399_ZS9WCFTUVFNU9R3.webp)

选择与你的 LineageOS 版本 (比如 `lineage-21`) 相对应的那个分支，把仓库地址和分支名填到我们刚才的 `.xml` 文件里。

**保存好 `.xml` 文件后，再次执行召唤仪式！**

| 1 | `repo` `sync` `--no-clone-bundle` |
|-|-|

### Step 8: 与 Android 酱共进早餐 (最终准备与编译)

现在呢...

*呐~ 你吃早餐了吗？要不要和可爱的 Android 酱共进早餐呢？*

*诶？同意了嘛？那... 把你手机的代号作为用餐券交给 Android 酱吧~*

*欸嘿，别忘了问 Android 酱的联系方式哦~ (虽然她可能不会直接告诉你)*

| 12 | `# 问一下 Android 酱的联系方式``source` `build``/envsetup``.sh` |
|-|-|

嗯... 果然，傲娇的 Android 酱没有直接回应... 但没关系，我们可以用刚才的“用餐券”来正式邀请她共进早餐啦！

| 12 | `# 使用你的设备代号作为“用餐券”``breakfast <你的设备代号>` |
|-|-|

如果是第一次约 Android 酱吃早餐，她可能会需要从 GitHub 上拉取一些专属于你设备的材料 (device, hardware, kernel 等)。**这时候可能需要你的魔法上网工具助力！如果开了代理(全局)还是卡住不动，就按 `Ctrl + C` 强制取消，然后重新邀请她吃早餐 (多试几次可能就好了)。**

 ![image](https://bbs.kanxue.com/upload/attach/202504/1033399_MA766YH8VMHVCFH.webp)

早餐过后，就是激动人心的早午餐 (Brunch) 时间！这才是正餐！

| 12 | `# 和 Android 酱享用早午餐 (开始编译！)``brunch <你的设备代号>` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202504/1033399_G46HK7D5B5XTYWY.webp)

接下来，就是漫长而又悲壮的炼成时间... 期间你可能会经历：

- 出现奇怪的编译错误
- 仿佛永无止境的编译时间...
- CPU 君发出的痛苦咆哮
- 内存酱被 Buffer/Cache 填满到几乎窒息
- Swap 结界被无情地挤占
- 硬盘空间以肉眼可见的速度消失 (尤其最后 10%-15%，请务必留足至少 50GB 的空间！)
- 甚至... 电脑直接累晕过去

不过不用太担心！即使编译中途电脑不幸牺牲，直接强制重启后，回到源码目录，重新执行 `source build/envsetup.sh` 和 `brunch <你的设备代号>`，编译大法师会从上次中断的地方继续施法 (有点像断点续传，超神奇！)。

 ![image](https://bbs.kanxue.com/upload/attach/202504/1033399_RM7YD7J5SEUESQJ.webp)

**坚持住！胜利的 BGM 终将奏响！—— 编译成功！**

 ![image](https://bbs.kanxue.com/upload/attach/202504/1033399_P9TJM7Y3DXCSG68.webp)
我们亲手炼成的 ROM 包就静静地躺在 `./out/target/product/<你的设备代号>/` 这个目录下。

 ![image](https://bbs.kanxue.com/upload/attach/202504/1033399_KAFKARCWJA726NS.webp)
好啦！快去把这份带着你心血和汗水的 ROM 刷入你的爱机吧！享受这份亲手创造的喜悦！(≧∇≦)

---

# 回复

## 回复 by mb_wpitiize (#2)

*2025-4-21 10:29*

神人

## 回复 by MsScotch (#3)

*2025-4-21 22:47*

这风格。。。 好BT，好喜欢

## 回复 by chengdrgon (#4)

*2025-4-22 10:36*

感谢分享，收藏备用

## 回复 by 呼吸24K纯氧 (#5)

*2025-4-23 09:46*

这风格。。。 好BT，好喜欢

## 回复 by C0rax (#6)

*2025-4-23 12:25*

牛笔

## 回复 by wx_A$001101000011000000110100 (#7)

*2025-4-23 19:12*

非常好风格

## 回复 by mb_tkijjroi (#8)

*2025-5-5 00:26*

这种风格真的很好，看着很棒

## 回复 by 自称宅男 (#9)

*2025-5-6 20:17*

这种风格真的很好，看着很棒

## 回复 by 清风QingFeng (#10)

*2025-6-26 11:49*

pixel 5 编译了一整天lineageOS 21都没有成功
[100% 1/1] analyzing Android.bp files and generating ninja file at out/soong/build.lineage_redfin.ninja
FAILED: out/soong/build.lineage_redfin.ninja
cd "$(dirname "out/host/linux-x86/bin/soong_build")" && BUILDER="$PWD/$(basename "out/host/linux-x86/bin/soong_build")" && cd / && env -i  "$BUILDER"     --top "$TOP"     --soong_out "out/soong"     --out "out"     --soong_variables out/soong/soong.lineage_redfin.variables -o out/soong/build.lineage_redfin.ninja --globListDir lineage_redfin --globFile out/soong/globs-lineage_redfin.ninja -l out/.module_paths/Android.bp.list --available_env out/soong/soong.environment.available --used_env out/soong/soong.environment.used.lineage_redfin.build Android.bp
error: prebuilts/clang/host/linux-x86/Android.bp:39:1: unrecognized module type "llvm_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:48:1: unrecognized module type "llvm_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:69:1: unrecognized module type "libclang_rt_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:84:1: unrecognized module type "libclang_rt_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:118:1: unrecognized module type "libclang_rt_prebuilt_library_shared"
error: prebuilts/clang/host/linux-x86/Android.bp:130:1: unrecognized module type "libclang_rt_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:140:1: unrecognized module type "libclang_rt_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:150:1: unrecognized module type "libclang_rt_prebuilt_library_shared"
error: prebuilts/clang/host/linux-x86/Android.bp:167:1: unrecognized module type "libclang_rt_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:182:1: unrecognized module type "libclang_rt_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:195:1: unrecognized module type "libclang_rt_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:214:1: unrecognized module type "libclang_rt_prebuilt_library_shared"
error: prebuilts/clang/host/linux-x86/Android.bp:233:1: unrecognized module type "libclang_rt_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:245:1: unrecognized module type "libclang_rt_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:261:1: unrecognized module type "libclang_rt_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:275:1: unrecognized module type "libclang_rt_prebuilt_object"
error: prebuilts/clang/host/linux-x86/Android.bp:281:1: unrecognized module type "libclang_rt_prebuilt_object"
error: prebuilts/rust/Android.bp:40:1: unrecognized module type "rust_stdlib_prebuilt_host"
error: prebuilts/clang/host/linux-x86/Android.bp:309:1: unrecognized module type "llvm_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:319:1: unrecognized module type "llvm_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:332:1: unrecognized module type "llvm_prebuilt_library_static"
error: prebuilts/clang/host/linux-x86/Android.bp:356:1: unrecognized module type "llvm_host_defaults"
error: prebuilts/clang/host/linux-x86/Android.bp:361:1: unrecognized module type "llvm_host_prebuilt_library_shared"
error: prebuilts/clang/host/linux-x86/Android.bp:378:1: unrecognized module type "llvm_host_prebuilt_library_shared"
error: prebuilts/clang/host/linux-x86/Android.bp:392:1: unrecognized module type "llvm_host_prebuilt_library_shared"
error: prebuilts/clang/host/linux-x86/Android.bp:400:1: unrecognized module type "clang_builtin_headers"
error: prebuilts/clang/host/linux-x86/Android.bp:408:1: unrecognized module type "llvm_tools_filegroup"
error: prebuilts/clang/host/linux-x86/Android.bp:415:1: unrecognized module type "llvm_prebuilt_build_tool"
error: prebuilts/clang/host/linux-x86/Android.bp:419:1: unrecognized module type "llvm_prebuilt_build_tool"
error: prebuilts/rust/Android.bp:486:1: unrecognized module type "rust_stdlib_prebuilt_filegroup_host"
fatal errors encountered
11:46:57 soong bootstrap failed with: exit status 1

#### failed to build some targets (4 seconds) ####

## 回复 by X66iaM (#11)

*2025-8-11 23:09*

![image](https://bbs.kanxue.com/view/img/face/064.gif)读着心里毛毛的

## 回复 by dadadasda (#12)

*2025-8-12 03:31*

以前第一次编译lineage时候甚至某机器的内核源码都找不着，得拿着成品内核自己写东拉西凑一些驱动用dtb。手机的相机不能用，得自己写视频推流驱动来实现假画面。现在lineage的编译已经非常方便了，不涉及修改基本上拉下来选完编译类型直接就能make dist
