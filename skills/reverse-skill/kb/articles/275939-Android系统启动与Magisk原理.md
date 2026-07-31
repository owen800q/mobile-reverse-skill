---
title: '[原创]  Android系统启动与Magisk原理'
url: https://bbs.kanxue.com/thread-275939.htm
tid: 275939
author: 飞翔的猫咪
date: '2023-02-01'
tags: [Android安全, 原创, 系统相关, 源码框架]
crawled_at: '2026-07-31T14:53:55+08:00'
replies: 38
---

Android系统启动是个相当复杂的过程,牵扯的技术点很多,如果想实现Android虚拟化云手机技术或者专注于刷机刷系统,理解启动的整个过程更是必需的。

Magisk和Android系统的启动更是息息相关,本文会在系统启动的角度描述一下Magisk的原理。

本文包含如下内容:
一. 磁盘分区表mbr,gpt的概念
二. ramdisk,initrd,ramfs,tmpfs,initramfs,rootfs,根文件系统名词的澄清
三. Linux内核启动init进程的五种不同情况
四. 安卓系统启动的三种不同方式
五. Magisk原理

## 一. 磁盘分区表mbr,gpt

以下描述中磁盘、硬盘都是通用概念，代表着非易失的存储设备。
说到系统启动，和分区是息息相关的,对磁盘进行分区必然有分区表这样的一个结构，它存放在磁盘当中，分区表所面临的抽象仍然是将整个磁盘视为一个大的字节数组，只不过它通常以扇区为单元，扇区一般为512字节。
老式的磁盘分区方法叫MBR,新式的磁盘分区方法叫GPT。

**MBR：**
MBR的全称为Master Boot Record,它指的是指定开机指定启动硬盘的第一个扇区，通常为512字节，为什么说分区方法也叫MBR呢，因为这个扇区包括了两部分内容: bootstrap code area和partition table

1. bootstrap code area占据446个字节，包含了启动相关的代码
2. partition table分区表占据了64个字节，包含了四个分区表的内容，每个分区表占据16个字节
3. 446+64 = 510,还剩下最后两个字节的内容为0x55aa,这是MBR的标志
所以MBR这个名词不仅仅指磁盘的第一个扇区，它还暗指了上面的这种布局以及分区格式

**读写磁盘逻辑地址:**
C/H/S (Cylinder / Head / Sector) 柱面/磁头/扇区是以前用于读写磁盘的基本逻辑地址结构，比如0/0/1(Cylinder=0,Head=0,Sector=1)就代表MBR。
MBR中的分区表格式就用到了C/H/S的表示方法。
C/H/S是一种老式的逻辑地址方式，它的存在有一定的历史原因，早期磁盘的结构就是柱面，磁头和扇区这些，后面磁盘的物理结构就不一定再是这些了，CHS也就不再对应于磁盘物理上的结构，对于CHS转换到实际磁盘的地址则是磁盘控制器的工作。
新式的逻辑地址表示方法为LBA:Logical Block Addressing,它的想法很简单，就是将磁盘视为一个大的字节数组，LBA从0开始: LBA0,LBA1,..... 每一块LBA的大小通常为512字节(也有以1024字节为块大小的固态硬盘，和4096字节为块大小的flash存储设备)。

**C/H/S到LBA有一个转换公式:**
`A = (c ⋅ Nheads + h) ⋅ Nsectors + (s − 1)`
A为LBA地址，Nheads为磁盘上的heads个数，Nsectors是每个track里边的最大扇区个数
理解这个公式可以简单的认为磁盘是这样构成的:

1. 扇区是一块扇形区域，像一块切好的比萨
2. 多个扇区最终组成一个圆，好比组成一个完整的比萨，这块比萨可以分割成多少个扇区由Nsectors表示
3. 磁盘由多个完整的比萨组成(串在一起)，数量共为Nheads个

MBR每个分区表占据16个字节，比如:
`80 01 01 00 0B FE BF FC 3F 00 00 00 7E 86 BB 00`
含义如下:
80    --> 1字节，分区状态: 00 --> 非活动分区，80 --> 活动分区
01  01  00  --> 3字节, 共同表示分区起始C/H/S(但是并不指C=1,H=1,S=0)
0B  --> 文件系统标志位 : "0B"表示分区的系统类型是FAT32，其他比较常用的有04（FAT16）、07（NTFS）
FE BF FC   --> 共同表示分区结束C/H/S
3F 00 00 00  --> 分区起始相对扇区号
7E 86 BB 00  --> 分区总的扇区数

由于MBR格式的分区表只能识别四个分区(这些分区叫主分区)，如果想分四个以上的分区，必须创建一个分区，该分区用于存放更多的分区表，这样的分区叫做扩展分区，扩展分区只能有一个: 分区方式为4个主分区或者3个主分区加上一个扩展分区。
由于MBR使用4个字节表示分区总的扇区数,因此它可以表示的最大分区大小为2199023255552字节，约为2T，这也是MBR的一个限制。
由于各种限制，MBR已经成为老式的分区方式，新式的分区方式为GPT。

**GPT:**
GUID Partition Table

GPT采用LBA的地址格式，为了向后兼容以及用来防止不支持GPT的硬盘管理工具错误识别并破坏硬盘中的数据，LBA0仍然给MBR使用,不过MBR里边只有一块分区，分区类型为0xEE,这种MBR又叫"Protective MBR"。

GPT的格式维基百科中有详细描述，它还有一块区域用来备份分区表，在磁盘的末尾部分:
 ![image](https://bbs.kanxue.com/upload/attach/202302/607812_DSEHNYV9QAXD75E.png)

按照GPT的格式，磁盘真正的分区数据部分从LBA34开始，但分区软件一般将GPT分区边界对齐，比如对齐到2048扇区处:1,048,576 MB，所以一般分区的数据从LBA2048开始，因此从LBA34到LBA2048有一块大约1MB的间隙。

**查看分区表内容:**

安装python的gpt包:
`python3 -m pip install gpt`
以pixel3Xl手机为例,因为pixel3xl用的是高通的scsi总线的ufs存储设备，所以它的设备名称以"sd"开头(内核`drivers/scsi/sd.c的sd_format_disk_name()`函数),查看所有的sd设备:

| 1234567 | `ls` `-``l` `/``sys``/``block``/``sd``*``lrwxrwxrwx` `1` `root root` `0` `2023``-``01``-``11` `03``:``56` `/``sys``/``block``/``sda` `-``> ..``/``devices``/``platform``/``soc``/``1d84000``.ufshc``/``host0``/``target0:``0``:``0``/``0``:``0``:``0``:``0``/``block``/``sda``lrwxrwxrwx` `1` `root root` `0` `2023``-``01``-``11` `10``:``36` `/``sys``/``block``/``sdb` `-``> ..``/``devices``/``platform``/``soc``/``1d84000``.ufshc``/``host0``/``target0:``0``:``0``/``0``:``0``:``0``:``1``/``block``/``sdb``lrwxrwxrwx` `1` `root root` `0` `2023``-``01``-``11` `10``:``36` `/``sys``/``block``/``sdc` `-``> ..``/``devices``/``platform``/``soc``/``1d84000``.ufshc``/``host0``/``target0:``0``:``0``/``0``:``0``:``0``:``2``/``block``/``sdc``lrwxrwxrwx` `1` `root root` `0` `2023``-``01``-``11` `10``:``36` `/``sys``/``block``/``sdd` `-``> ..``/``devices``/``platform``/``soc``/``1d84000``.ufshc``/``host0``/``target0:``0``:``0``/``0``:``0``:``0``:``3``/``block``/``sdd``lrwxrwxrwx` `1` `root root` `0` `2023``-``01``-``11` `10``:``36` `/``sys``/``block``/``sde` `-``> ..``/``devices``/``platform``/``soc``/``1d84000``.ufshc``/``host0``/``target0:``0``:``0``/``0``:``0``:``0``:``4``/``block``/``sde``lrwxrwxrwx` `1` `root root` `0` `2023``-``01``-``11` `10``:``36` `/``sys``/``block``/``sdf` `-``> ..``/``devices``/``platform``/``soc``/``1d84000``.ufshc``/``host0``/``target0:``0``:``0``/``0``:``0``:``0``:``5``/``block``/``sdf` |
|-|-|

ufshc的含义为:`ufs host controller`,可以看到有6个sd设备,从a到f,并不代表着6个物理ufs设备,而是一块ufs物理设备分出来的逻辑设备,称之为LU(Logical Unit)。
它们的逻辑地址空间是独立的，都是从LBA 0开始，因此都有各自的分区表结构。
先来看一下sda的分区表信息,对应的/dev下面的块设备文件为/dev/block/sda,看一下sda设备的块逻辑大小(`内核include/linux/blkdev.h文件的bdev_logical_block_size()函数`):

| 12 | `cat` `/``sys``/``block``/``sda``/``queue``/``logical_block_size``4096` |
|-|-|

因此LBA的大小为4096字节。
安卓存储设备采用的是gpt分区,LBA0仍然给MBR使用，叫做"Protective MBR",dump它的内容查看分区表:
在手机中运行命令:

| 1 | `dd` `if``=``/``dev``/``block``/``sda bs``=``4096` `count``=``1`  `>` `/``data``/``local``/``tmp``/``lba0` |
|-|-|

在pc运行命令adb pull把/data/local/tmp/lba0文件拉取到pc
在pc运行命令

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344 | `cat lba0 \| print_mbr``Warning: Using only the first` `512` `bytes of` `input``<<< MBR >>>``BootCode:` `0x0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000``UniqueMBRDiskSignature:` `0x00000000``Unknown:` `0x0000``PartitionRecord:` `0x00000200ee00000001000000ffffffff000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000``Signature:` `0xAA55``<<< MBR Partition` `#0 >>>``#0.BootIndicator:                                                      0x0``#0.Is Bootable? (syn):                                                  No``#0.StartingCHS:                                                    0, 0, 2``#0.OSType:                                                            0xEE``#0.OSType (syn):                                            GPT Protective``#0.EndingCHS:                                                      0, 0, 0``#0.StartingLBA:                                                          1``#0.SizeInLBA:                                                   4294967295``<<< MBR Partition` `#1 >>>``#1.BootIndicator:                                                      0x0``#1.Is Bootable? (syn):                                                  No``#1.StartingCHS:                                                    0, 0, 0``#1.OSType:                                                             0x0``#1.OSType (syn):                                                     Empty``#1.EndingCHS:                                                      0, 0, 0``#1.StartingLBA:                                                          0``#1.SizeInLBA:                                                            0``<<< MBR Partition` `#2 >>>``#2.BootIndicator:                                                      0x0``#2.Is Bootable? (syn):                                                  No``#2.StartingCHS:                                                    0, 0, 0``#2.OSType:                                                             0x0``#2.OSType (syn):                                                     Empty``#2.EndingCHS:                                                      0, 0, 0``#2.StartingLBA:                                                          0``#2.SizeInLBA:                                                            0``<<< MBR Partition` `#3 >>>``#3.BootIndicator:                                                      0x0``#3.Is Bootable? (syn):                                                  No``#3.StartingCHS:                                                    0, 0, 0``#3.OSType:                                                             0x0``#3.OSType (syn):                                                     Empty``#3.EndingCHS:                                                      0, 0, 0``#3.StartingLBA:                                                          0``#3.SizeInLBA:                                                            0` |
|-|-|

可以看到它的bootcode全是0,且OSType为`GPT Protective`。

根据gpt的格式,LBA1为"Primary GPT Header", LBA2-LBA33为分区表，先看一下LBA1：

在手机中运行命令:

| 1 | `dd` `if``=``/``dev``/``block``/``sda bs``=``4096` `count``=``1` `skip``=``1` `>` `/``data``/``local``/``tmp``/``lba1` |
|-|-|

在pc运行命令adb pull把/data/local/tmp/lba1文件拉取到pc
在pc运行命令

| 1234567891011121314151617 | `cat lba1 \| print_gpt_header``Warning: Using only the first` `92` `bytes of` `input``<<< GPT Header >>>``Signature:` `0x4546492050415254``Revision:` `0x00000100``HeaderSize:` `92``HeaderCRC32:` `0x1d3ca154``HeaderCRC32 (calculated):` `0x1d3ca154``Reserved:` `0x00000000``MyLBA:` `1``AlternateLBA:` `15589375``FirstUsableLBA:` `6``LastUsableLBA:` `15589370``PartitionEntryLBA:` `2``NumberOfPartitionEntries:` `21``SizeOfPartitionEntry:` `128``PartitionEntryArrayCRC32:` `0xd171d8a9` |
|-|-|

再来看一下LBA2-LBA33:
在手机中运行命令:

| 1 | `dd` `if``=``/``dev``/``block``/``sda bs``=``4096` `count``=``32` `skip``=``2` `>` `/``data``/``local``/``tmp``/``lba2``-``33` |
|-|-|

在pc运行命令adb pull把/data/local/tmp/lba2-33文件拉取到pc
在pc运行命令

| 1 | `cat lba2``-``33``\| print_gpt_partition_entry_array` |
|-|-|

即可打印出所有分区表的信息。比如entry4和entry5为system_a,system_b分区:

| 123456789101112131415161718192021222324 | `<<< GPT Partition Entry` `#4 >>>``#4.PartitionTypeGUID:                   0x11b0d797da543548b3c4917ad6e73d74``#4.PartitionTypeGUID (syn):           97d7b011-54da-4835-b3c4-917ad6e73d74``#4.PartitionType (syn):                                                  ?``#4.UniquePartitionGUID:                 0xdbfff6623331984e9b30f325067783f0``#4.UniquePartitionGUID (syn):         62f6ffdb-3133-4e98-9b30-f325067783f0``#4.StartingLBA:                                                        520``#4.EndingLBA:                                                       721415``#4.Attributes:                                            0x5f000000000000``#4.Attributes (syn):                                                    []``#4.PartitionName: 0x730079007300740065006d005f0061000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000``#4.PartitionName (syn):                                           system_a``<<< GPT Partition Entry` `#5 >>>``#5.PartitionTypeGUID:                   0xd46c0377d503bb428ed137e5a88baa34``#5.PartitionTypeGUID (syn):           77036cd4-03d5-42bb-8ed1-37e5a88baa34``#5.PartitionType (syn):                                                  ?``#5.UniquePartitionGUID:                 0x75465b2326a94d4e9c32e9acf66da87d``#5.UniquePartitionGUID (syn):         235b4675-a926-4e4d-9c32-e9acf66da87d``#5.StartingLBA:                                                     721416``#5.EndingLBA:                                                      1442311``#5.Attributes:                                                         0x0``#5.Attributes (syn):                                                    []``#5.PartitionName: 0x730079007300740065006d005f0062000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000``#5.PartitionName (syn):                                           system_b` |
|-|-|

这些分区和安卓系统相关的有`system,vendor,data,odm,oem,misc,product`等(越老的安卓版本相关的分区越少)，其他的分区都是厂商相关的分区，这里的相关是指安卓代码中会直接有代码关联着分区挂载后的路径，等于是安卓版本的FHS(Filesystem Hierarchy Standard文件系统层次结构标准)。有的分区数据是raw数据，没有格式化为具体的文件系统，比如misc分区。
system_a,system_b是A/B分区的概念。对于高版本的安卓来说，上面的分区表里是没有recovery分区的。
bootloader会分析gpt分区表结构，当执行`fastboot flash system_a system.img`命令的时候bootloader才知道要刷写的分区位置。
Linux内核也会扫描gpt分区表，生成gendisk的分区表相关的数据结构，以高通的ufs为例，它的调用过程为:

| 1234567 | `drivers``/``scsi``/``sd.c:sd_probe()``sd_probe_async()``block``/``genhd.c:device_add_disk()``register_disk()``fs``/``block_dev.c:blkdev_get()``__blkdev_get()``block``/``partition``-``generic.c:rescan_partitions()` |
|-|-|

当系统检测到sda,sdb这样的设备时会在sysfs中创建目录分别为`/sys/block/sda,/sys/block/sdb`,而在每个设备中检测到分区以后就会创建出各自的目录(利用kobject机制)表示分区:
/sys/block/sda/sda1,/sys/block/sda/sda2,/sys/block/sda/sda3 ...
而init进程会重新触发uevent消息在/dev目录下创建出对应块设备文件:/dev/block/sda,/dev/block/sda1,/dev/block/sda2 ...
同时/dev下的如下目录也能反映出分区和块设备的关联性:

| 12345678910 | `ls` `-``l` `/``dev``/``block``/``platform``/``soc``/``1d84000``.ufshc``/``by``-``name` `lrwxrwxrwx` `1` `root root` `15` `1970``-``08``-``22` `11``:``05` `ALIGN_TO_128K_1` `-``>` `/``dev``/``block``/``sdd1``lrwxrwxrwx` `1` `root root` `15` `1970``-``08``-``22` `11``:``05` `ALIGN_TO_128K_2` `-``>` `/``dev``/``block``/``sdf1``lrwxrwxrwx` `1` `root root` `16` `1970``-``08``-``22` `11``:``05` `ImageFv` `-``>` `/``dev``/``block``/``sdf14``lrwxrwxrwx` `1` `root root` `15` `1970``-``08``-``22` `11``:``05` `abl_a` `-``>` `/``dev``/``block``/``sde4``lrwxrwxrwx` `1` `root root` `16` `1970``-``08``-``22` `11``:``05` `abl_b` `-``>` `/``dev``/``block``/``sde16``lrwxrwxrwx` `1` `root root` `15` `1970``-``08``-``22` `11``:``05` `aop_a` `-``>` `/``dev``/``block``/``sde1``lrwxrwxrwx` `1` `root root` `16` `1970``-``08``-``22` `11``:``05` `aop_b` `-``>` `/``dev``/``block``/``sde13``lrwxrwxrwx` `1` `root root` `16` `1970``-``08``-``22` `11``:``05` `apdp_a` `-``>` `/``dev``/``block``/``sda15``lrwxrwxrwx` `1` `root root` `16` `1970``-``08``-``22` `11``:``05` `apdp_b` `-``>` `/``dev``/``block``/``sda16` |
|-|-|

## 二.ramdisk,initrd,ramfs,tmpfs,initramfs,rootfs,根文件系统名词的澄清

我一开始接触到init进程启动的时候，遇到上面的这些名词，总是感觉模模糊糊，不知道它们具体的作用和含义，在这里对这些名词进行一下澄清，它们和init进程的启动有很大的关系。

**Ramdisk:**首先是ramdisk,它是个古老的东西，在1979/80就出现了。ramdisk简单来说就是RAM模拟为硬盘的技术。由于读取写入都在内存中，所以RAMDISK速度非常快。它在各种操作系统上都有实现，在linux中的实现为`drivers/block/brd.c`。
虽然安卓的boot.img里边也有个文件叫ramdisk,但是其实它用的技术本质上却并不是ramdisk，后面会有详细描述。
开启ramdisk功能需要配置`CONFIG_BLK_DEV_RAM=y`,同时关联的配置为`CONFIG_BLK_DEV_RAM_COUNT`默认为16,表示ramdisk设备的个数,`CONFIG_BLK_DEV_RAM_SIZE`默认为8192,以1kb为单位的ramdisk设备的字节数大小。
当ramdisk功能开启以后会有如下的设备文件:/dev/ram0,/dev/ram1,/dev/ram2 ... /dev/ram15,由于每一块模拟的都是硬盘，因此可以直接格式化为指定文件系统并挂载:

| 12 | `sudo mkfs.ext4` `/``dev``/``ram0``sudo mount` `/``dev``/``ram0 mount_dir` |
|-|-|

ramdisk的缺点在于它是固定大小的，文件系统挂载在上面也是固定的大小，那么必然会有无法扩展和空间浪费的问题。而且由于linux内核会缓存块设备中的文件(page cache)和目录(dentry cache)，会导致对ramdisk中的文件内容做不必要的缓存，一份数据可能在ramdisk中占了一份内容，同时在page cache中也有一个副本。而且ramdisk还需要专门去格式化然后使用。

**根文件系统:** 这里指的linux系统启动以后最终/目录所在的那个文件系统。

ramfs,tmpfs,rootfs，这三个都是文件系统:

| 1234 | `cat` `/``proc``/``filesystems``nodev ramfs``nodev tmpfs``nodev rootfs` |
|-|-|

nodev装载标志表示装载的文件系统是虚拟的，没有物理后端设备。

因为ramdisk有着一些缺点，Linus Torvalds创建出了ramfs文件系统，它将linux的缓存机制(page cache和dentry cache)用做动态的可扩展的基于ram的文件系统。在ramfs的基础上其他内核开发者又创建了一个改善版本叫做tmpfs,tmpfs可以将数据写入交换分区，并且可以限制挂载点的大小。而initramfs其实就是ramfs的一个实例。
rootfs虽然它直译过来是"根文件系统"的意思，但这里指的是内核中的一个文件系统，它和用户空间的"根文件系统"并不是一个东西：

| 12345 | `struct file_system_type rootfs_fs_type` `=` `{``.name` `=` `"rootfs"``,``.init_fs_context` `=` `rootfs_init_fs_context,``.kill_sb` `=` `kill_litter_super,``};` |
|-|-|

因此综上,ramdisk和ramfs,tmpfs,rootfs这三个有本质的区别，ramdisk模拟的是块设备，而其他三个是文件系统可以直接挂载。

initrd直译过来就是"init ramdisk"的意思，那是不是initramfs就是将ramfs挂载为根文件系统,而initrd就是将ramdisk格式化并挂载为根文件系统呢？事实却并不是这样，因为历史的一些原因,initrd的含义也发生了变化，它其实成了主流的启动方式，而它的含义也并不一定和ramdisk技术有关，下面的示例会详细说明这一点。

下面用具体的示例来解释这些名词的真正含义。

## 三. Linux内核启动init进程的五种不同情况:

我的操作系统是ubuntu 22.04,内核版本5.15.0-58-generic,那么就下载一个linux-5.15.89的内核吧:

| 1234567 | `wget https:``/``/``cdn.kernel.org``/``pub``/``linux``/``kernel``/``v5.x``/``linux``-``5.15``.``89.tar``.xz``tar xvf linux``-``5.15``.``89.tar``.xz``cd linux``-``5.15``.``89``#默认配置就为x86_64的配置``make defconfig` `#编译出x86_64的内核镜像``make bzImage` |
|-|-|

编译成功以后`arch/x86/boot/bzImage`文件就可以做为内核文件调用qemu启动了:

| 1 | `qemu``-``system``-``x86_64` `-``kernel arch``/``x86_64``/``boot``/``bzImage` |
|-|-|

为了看清楚启动过程的日志，可以加-nographic参数，此模式下退出qemu用快捷键"ctl+a x"

| 1 | `qemu``-``system``-``x86_64` `-``kernel arch``/``x86_64``/``boot``/``bzImage` `-``-``append` `"console=ttyS0"` `-``nographic` |
|-|-|

由于只启动了内核没有指定根文件系统，所以启动后会报:
`Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)`

接下来创建一个简单的根文件系统让内核去启动,总结起来大致分为如下五种启动方式。

### 启动方式1:

首先是最原始的启动方式直接指定内核启动参数root为一个块设备。

| 12 | `mkdir` `-``p my_rootfs``/``root_disk``cd my_rootfs``/``root_disk` |
|-|-|

创建一个文件init.c内容为:

| 12345678 | `#include <stdio.h>``#include <unistd.h>` `int` `main() {``printf(``"Hello, Linux!!!\n"``);``sleep(``999999``);``return` `0``;``}` |
|-|-|

编译这个文件:

| 1 | `gcc` `-``static init.c` `-``o init` |
|-|-|

创建一个10M大小的镜像文件:

| 1 | `dd` `if``=``/``dev``/``zero of``=``disk.img bs``=``10M` `count``=``1` |
|-|-|

格式化为ext4文件系统:

| 1 | `sudo mkfs.ext4 disk.img` |
|-|-|

挂载这个文件系统:

| 12 | `mkdir mount_dir``sudo mount disk.img mount_dir` |
|-|-|

将init程序拷贝到mount_dir中:

| 1 | `sudo cp init mount_dir` |
|-|-|

卸载文件系统:

| 1 | `sudo umount mount_dir` |
|-|-|

这样等于用于启动的硬盘就创建好了，用qemu去启动它:

| 1 | `qemu``-``system``-``x86_64` `-``kernel arch``/``x86_64``/``boot``/``bzImage` `-``hda my_rootfs``/``root_disk``/``disk.img` `-``-``append` `"root=/dev/sda init=/init console=ttyS0"` `-``nographic` |
|-|-|

会打印出`"Hello, Linux!!!"`,由于执行了sleep(999999),init进程短时间内就不会退出,init进程退出以后内核会panic。

-hda用于指定硬盘镜像，--append后面的参数用于传递给内核做为命令行参数，root指定了根文件系统所在的设备/dev/sda,正常情况下/dev目录是由init进程创建出来的，而此时init进程自己还没运行,哪来的/dev/sda?事实上/dev在内核代码中会被截掉，内核只认sda，/dev/sda只是习惯上的表示而已。init=/init指定了根文件系统中/init程序做为内核执行程序。

以上的启动方式是最早时期内核启动init进程的方式，安卓的Legacy System-as-root其实也算是这种方式。
这种启动方式有什么缺点呢？旧时期这种方式足以启动满足要求，但是随着时代的发展，硬件变的越来越复杂，根文件系统可能处于各种scsi,sata,flash设备上，甚至RAID阵列,可插拔的usb设备中。根文件系统还可能被压缩和加密，那么如何解压缩，如何解密则成了问题。如果根文件系统处于网络文件系统NFS中，那么内核就必须执行DHCP,DNS网络请求然后登录到目标机器中然后才能挂载根文件系统。这些功能如果让内核去一一实现等于是用汇编语言来写web应用程序，而且完成这些工作还需要在内核中集成各种所需驱动，有的驱动却并不会用到，这增加了配置的难度。

那么总体解决方案是不论最终的根文件系统在哪，内核先挂载一个初始根文件系统，这个初始根文件系统负责加载合适的驱动并寻找最终根文件系统并挂载，内核挂载完初始根文件系统以后接下来的事情它就不管了。而挂载初始化根文件系统本身是很简单的，可以基于ramdisk,ramfs,tmpfs,rootfs这些技术。下面的另外四种启动方式和第一种方式的不同点就在于多了处理初始根文件系统的步骤。

先来看一下基于古老的ramdisk的技术，这种技术后面不会再使用了(代码中描述:`using deprecated initrd support, will be removed in 2021`)，但描述它才能澄清initrd的一些概念。

### 启动方式2:

开启CONFIG_BLK_DEV_RAM配置:

| 1 | `make menuconfig` |
|-|-|

输入/CONFIG_BLK_DEV_RAM,按1将`"RAM block device support"`置为y选中状态。
选中以后.config增加的配置项为:

| 123 | `CONFIG_BLK_DEV_RAM``=``y``CONFIG_BLK_DEV_RAM_COUNT``=``16``CONFIG_BLK_DEV_RAM_SIZE``=``4096` |
|-|-|

接着创建启动用的镜像文件:

| 12 | `mkdir` `-``p my_rootfs``/``old_ramdisk``cd my_rootfs``/``old_ramdisk` |
|-|-|

创建一个文件linuxrc.c内容为:

| 1234567 | `#include <stdio.h>``#include <unistd.h>``int` `main() {` `printf(``"From linuxrc : Hello, Linux!!\n"``);``return` `0``;``}` |
|-|-|

编译这个文件:

| 1 | `gcc` `-``static linuxrc.c` `-``o linuxrc` |
|-|-|

创建一个2M大小的镜像文件:

| 1 | `dd` `if``=``/``dev``/``zero of``=``ramdisk.img bs``=``2M` `count``=``1` |
|-|-|

格式化为ext2文件系统:

| 1 | `sudo mkfs.ext2 ramdisk.img` |
|-|-|

挂载这个文件系统:

| 12 | `mkdir mount_dir``sudo mount ramdisk.img mount_dir` |
|-|-|

将linuxrc程序拷贝到mount_dir中:

| 1 | `sudo cp linuxrc mount_dir` |
|-|-|

创建/dev/console设备节点不然不会有日志输出:

| 1234 | `cd mount_dir``sudo mkdir dev``cd dev``sudo mknod console c` `5` `1` |
|-|-|

退出目录并卸载文件系统:

| 1 | `sudo umount mount_dir` |
|-|-|

这样一个ramdisk就创建好了，用它来启动:

| 1 | `qemu``-``system``-``x86_64` `-``kernel  arch``/``x86_64``/``boot``/``bzImage` `-``hda my_rootfs``/``root_disk``/``disk.img` `-``initrd my_rootfs``/``old_ramdisk``/``ramdisk.img` `-``-``append` `"root=/dev/sda init=/init console=ttyS0"` `-``nographic` |
|-|-|

和第一种启动方式的区别在于这里多指定了`-initrd my_rootfs/old_ramdisk/ramdisk.img。`
会先打印出`"From linuxrc : Hello, Linux!!"`
接着打印出`"Hello, Linux!!!"`

第一种启动方式中内核执行完/init进程以后就不回头了，init进程如果退出内核会panic。

而第二种启动方式内核会利用ramdisk在上挂载ramdisk.img并执行/linuxrc程序(写死的),并且等待这个程序的返回，然后内核再去挂载并执行位于/dev/sda中的init程序。linuxrc执行的任务一般是加载下一阶段init程序所需要的模块。

### 启动方式3:

| 12 | `mkdir` `-``p my_rootfs``/``initrd``cd my_rootfs``/``initrd` |
|-|-|

创建一个文件init.c内容为:

| 12345678 | `#include <stdio.h>``#include <unistd.h>` `int` `main() {``printf(``"Hello, Linux!!!\n"``);``sleep(``999999``);``return` `0``;``}` |
|-|-|

编译这个文件:

| 1 | `gcc` `-``static init.c` `-``o init` |
|-|-|

创建一个2M大小的镜像文件:

| 1 | `dd` `if``=``/``dev``/``zero of``=``disk.img bs``=``2M` `count``=``1` |
|-|-|

格式化为ext2文件系统:

| 1 | `sudo mkfs.ext2 disk.img` |
|-|-|

挂载这个文件系统:

| 12 | `mkdir mount_dir``sudo mount disk.img mount_dir` |
|-|-|

将init程序拷贝到mount_dir中:

| 1 | `sudo cp init mount_dir` |
|-|-|

创建/dev/console设备节点不然不会有日志输出:

| 1234 | `cd mount_dir``sudo mkdir dev``cd dev``sudo mknod console c` `5` `1` |
|-|-|

退出目录并卸载文件系统:

| 1 | `sudo umount mount_dir` |
|-|-|

用它来启动:

| 1 | `qemu``-``system``-``x86_64` `-``kernel  arch``/``x86_64``/``boot``/``bzImage` `-``initrd my_rootfs``/``initrd``/``disk.img` `-``-``append` `"root=/dev/ram0 init=/init console=ttyS0"` `-``nographic` |
|-|-|

会打印出`"Hello, Linux!!!"`

这种启动方式不再需要指定-hda参数，只指定了一个-initrd参数，且root修改为/dev/ram0。

### 启动方式4:

| 12 | `mkdir` `-``p my_rootfs``/``initrd_cpio``/``out``cd my_rootfs``/``initrd_cpio` |
|-|-|

创建一个文件init.c内容为:

| 12345678 | `#include <stdio.h>``#include <unistd.h>` `int` `main() {``printf(``"Hello, Linux!!!\n"``);``sleep(``999999``);``return` `0``;``}` |
|-|-|

编译这个文件:

| 1234 | `gcc` `-``static init.c` `-``o init``cp init out``/``cd out``find . \| cpio` `-``o` `-``H newc \| gzip > ..``/``simple_initrd.cpio.gz` |
|-|-|

接着使用创建出来的文件启动:

| 1 | `qemu``-``system``-``x86_64` `-``kernel  arch``/``x86_64``/``boot``/``bzImage` `-``initrd my_rootfs``/``initrd_cpio``/``simple_initrd.cpio.gz` `-``-``append` `"init=/init console=ttyS0"` `-``nographic` |
|-|-|

会打印出`"Hello, Linux!!!"`
上面的过程是不需要root权限的，这也是这种启动方式的一个小优点。
安卓boot.img中的ramdisk启动算是此类启动方式。

### 启动方式5:

| 12 | `mkdir my_rootfs``/``initramfs``/``out``cd my_rootfs``/``initramfs` |
|-|-|

创建一个文件init.c内容为:

| 12345678 | `#include <stdio.h>``#include <unistd.h>` `int` `main() {``printf(``"Hello, Linux!!!\n"``);``sleep(``999999``);``return` `0``;``}` |
|-|-|

编译这个文件:

| 123 | `gcc` `-``static init.c` `-``o init``cp init out``/``cd out` |
|-|-|

创建/dev/console设备节点不然不会有日志输出:

| 123456 | `mkdir dev``cd dev``sudo mknod console c` `5` `1``cd ..` `find . \| cpio` `-``o` `-``H newc \| gzip > ..``/``initramfs_data.cpio.gz` |
|-|-|

修改内核配置:

| 1 | `make menuconfig` |
|-|-|

按/并输入CONFIG_INITRAMFS_SOURCE,按回车,然后输入
`my_rootfs/initramfs/initramfs_data.cpio.gz`
这样.config文件就多了一项:
`CONFIG_INITRAMFS_SOURCE="my_rootfs/initramfs/initramfs_data.cpio.gz"`
重新编译:

| 1 | `make bzImage` |
|-|-|

直接启动:

| 1 | `qemu``-``system``-``x86_64` `-``kernel  arch``/``x86_64``/``boot``/``bzImage` `-``-``append` `"init=/init console=ttyS0"` `-``nographic` |
|-|-|

会打印出`"Hello, Linux!!!"`

这种启动方式就是initramfs。它是将initramfs_data.cpio.gz文件和内核编译在了一起，因此启动的时候什么额外的参数都不需要指定。

如果不指定`CONFIG_INITRAMFS_SOURCE`配置,默认也会有个initramfs,位于内核源码目录`usr/initramfs_data.cpio`,它里边除了/dev/console文件以外没有其他任何的文件。因此不管怎么样都会有个initramfs打包进内核一起启动。

### 源码分析:

上面的五种方式体现了内核在启动这块的复杂性，下面从代码层次来分析这个过程。内核版本为5.15.89:
内核的c语言函数入口为start_kernel:

| 123456789101112131415161718192021222324252627282930 | `start_kernel()``vfs_caches_init()``mnt_init()``init_rootfs()``init_mount_tree()``vfs_kern_mount(&rootfs_fs_type,` `0``,` `"rootfs"``, NULL)` `arch_call_rest_init()``rest_init()``kernel_thread(kernel_init, NULL, CLONE_FS)``kernel_init_freeable()``do_basic_setup()``do_initcalls()` `-``-``> rootfs_initcall(populate_rootfs)``do_populate_rootfs()``unpack_to_rootfs()` `#ifdef CONFIG_BLK_DEV_RAM``populate_initrd_image(err);` `console_on_rootfs()``if` `(init_eaccess(ramdisk_execute_command) !``=` `0``) prepare_namespace()``initrd_load()``mount_root()``create_dev(``"/dev/root"``, ROOT_DEV)``mount_block_root(``"/dev/root"``, root_mountflags)``devtmpfs_mount();``init_mount(``"."``,` `"/"``, NULL, MS_MOVE, NULL);``init_chroot(``"."``);` `try_to_run_init_process()` |
|-|-|

不论对于上面的哪种启动方式,都会走到`init_mount_tree()`函数调用`vfs_kern_mount(&rootfs_fs_type, 0, "rootfs", NULL)`,并且设置current的pwd与root:

| 12 | `set_fs_pwd(current``-``>fs, &root);``set_fs_root(current``-``>fs, &root);` |
|-|-|

这里的current是0号进程,它是所有其他进程的祖先，也称作idle进程或swapper进程。因此不论是哪种启动方式都有一个rootfs挂载起来以供使用。这个rootfs实现方式可以是ramfs也可以是tmpfs,可以灵活配置:

| 123456 | `void __init init_rootfs(void)``{``if` `(IS_ENABLED(CONFIG_TMPFS) && !saved_root_name[``0``] &&``(!root_fs_names \|\| strstr(root_fs_names,` `"tmpfs"``)))``is_tmpfs` `=` `true;``}` |
|-|-|

接下来会在rest_init()函数中调用`kernel_thread(kernel_init, NULL, CLONE_FS)`创建出1号进程，由于指定了CLONE_FS,因此1号进程也会继承0号进程的文件系统信息，即挂载的rootfs。
接下来的流程会经由`do_basic_setup()`初始化驱动以后调用到`populate_rootfs()`函数，从而调用到`do_populate_rootfs()`函数，在这个函数首先会调用`unpack_to_rootfs(__initramfs_start, __initramfs_size)`将initramfs的内容解压至rootfs,以上的过程对所有启动过程都是相同的，接下来针对上面的不同启动方式进行分析:

**启动方式1:**

| 1 | `qemu``-``system``-``x86_64` `-``kernel arch``/``x86_64``/``boot``/``bzImage` `-``hda my_rootfs``/``root_disk``/``disk.img` `-``-``append` `"root=/dev/sda init=/init console=ttyS0"` `-``nographic` |
|-|-|

由于默认的initramfs并没有内容，而且这种启动方式没有指定initrd选项,initrd_start变量为0,`do_populate_rootfs()`函数就返回了。
回到`kernel_init_freeable()`函数中进行到如下的判断:

| 1234 | `if` `(init_eaccess(ramdisk_execute_command) !``=` `0``) {``ramdisk_execute_command` `=` `NULL;``prepare_namespace();``}` |
|-|-|

如果没有设置内核命令行参数"rdinit=",ramdisk_execute_command就为/init,此时检查rootfs中有没有/init，由于initramfs中只有一个/dev/console文件,所以init_eaccess()函数的返回非0，进入到`prepare_namespace()`函数。
在`prepare_namespace()`函数中`root_device_name`的值为/dev/sda,首先会获取/dev/sda的主设备和次设备号表示dev_t ROOT_DEV,接着将root_device_name从/dev/sda截取为sda,然后调用initrd_load()函数加载/initrd.image文件，由于rootfs中没有/initrd.image因此initrd_load除了创建了设备节点/dev/ram并不会做什么事情。
接下执行:

| 123456789 | `/``/``创建ROOT_DEV对应的设备节点``/``dev``/``root,如果没有指定rootfstype命令行参数就尝试遍历文件系统类型对``/``dev``/``root进行挂载，挂载点为``/``root,并且调用init_chdir(``"/root"``)将工作目录切换到``/``root目录下` `mount_root();` `/``/``将当前工作目录(``/``root)移动挂载至``/``目录下``init_mount(``"."``,` `"/"``, NULL, MS_MOVE, NULL);` `/``/``切换当前进程的根目录至当前目录``init_chroot(``"."``);` |
|-|-|

启动分为两个过程:`rootfs --> sda`

根文件系统挂载完毕以后就可以调用`run_init_process("/init")`执行根文件系统上的init程序了,1号进程就切换到了用户空间去执行。

这种启动方式是二阶段启动，一阶段为rootfs,启动完了以后rootfs还是存在的，只不过挂载点被占用了，它无法被卸载，由于tmpfs占据的空间极少，所以并不是什么问题。

**启动方式2:**

| 1 | `qemu``-``system``-``x86_64` `-``kernel  arch``/``x86_64``/``boot``/``bzImage` `-``hda my_rootfs``/``root_disk``/``disk.img` `-``initrd my_rootfs``/``old_ramdisk``/``ramdisk.img` `-``-``append` `"root=/dev/sda init=/init console=ttyS0"` `-``nographic` |
|-|-|

先来看`do_populate_rootfs`函数, 由于指定了-initrd参数，所以initrd_start不为0，会执行`unpack_to_rootfs((char *)initrd_start, initrd_end - initrd_start)`将-initrd选项指定的ramdisk.img内容解压至rootfs,
但由于ramdisk.img的格式并不是cpio,而是ext2镜像，`unpack_to_rootfs()`函数会失败:`"rootfs image is not initramfs (invalid magic at start of compressed archive); looks like an initrd"`,并进入到`populate_initrd_image()`函数。

`populate_initrd_image()`函数会在rootfs中创建/initrd.image文件，并将-initrd选项指定的ramdisk.img内容写入/initrd.image文件。
回到`kernel_init_freeable()`函数仍然会进入到prepare_namespace函数并且调用initrd_load函数:

| 12345 | `if` `(rd_load_image(``"/initrd.image"``) && ROOT_DEV !``=` `Root_RAM0) {``init_unlink(``"/initrd.image"``);``handle_initrd();``return` `true;``}` |
|-|-|

`rd_load_image("/initrd.image"):`
rd_load_image的逻辑是先尝试识别出/initrd.image文件的格式，由于ramdisk.img的格式是ext2,因此会打印出`"RAMDISK: ext2 filesystem found at block 0"`表示识别出是ext2的文件格式。接下来将/initrd.image文件拷贝至ramdisk设备文件/dev/ram中。

由于这种启动方式ROOT_DEV为/dev/sda,`ROOT_DEV != Root_RAM0`判断就为true,从而进入到`handle_initrd`函数:
这个函数总体逻辑是创建表示Root_RAM0的/dev/root.old设备并挂载然后执行其上的/linuxrc程序并等待其返回，接着调用mount_root继续/dev/sda的挂载。

回到`prepare_namespace`函数,从该函数返回:

| 12 | `if` `(initrd_load())``goto out;` |
|-|-|

继续执行`run_init_process("/init")`函数启动位于sda设备上的init进程。

从上面的流程可以看出，启动分为三个过程:`rootfs --> ramdisk initrd --> sda。`

如果创建出来的ramdisk镜像大于CONFIG_BLK_DEV_RAM_SIZE的配置将无法加载镜像至/dev/ram，这种方式内核还需要等待/linuxrc程序返回然后接着挂载sda。

上面也提到过，这种方式是被废弃的老的ramdisk启动方式。

**启动方式3:**

| 1 | `qemu``-``system``-``x86_64` `-``kernel  arch``/``x86_64``/``boot``/``bzImage` `-``initrd my_rootfs``/``initrd``/``disk.img` `-``-``append` `"root=/dev/ram0 init=/init console=ttyS0"` `-``nographic` |
|-|-|

由于initrd指定的disk.img格式仍然为ext2镜像，所以这种启动方式和启动方式2的区别在于判断:

| 12345 | `if` `(rd_load_image(``"/initrd.image"``) && ROOT_DEV !``=` `Root_RAM0) {``init_unlink(``"/initrd.image"``);``handle_initrd();``return` `true;``}` |
|-|-|

`ROOT_DEV == Root_RAM0`,因此就不会走到`handle_initrd()`函数，而是将/dev/ram直接用做最终的根文件系统执行其上的/init进程。
启动分为两个过程:`rootfs --> ramdisk initrd`, 它本质上也是ramdisk技术的应用。

**启动方式4:**

| 1 | `qemu``-``system``-``x86_64` `-``kernel  arch``/``x86_64``/``boot``/``bzImage` `-``initrd my_rootfs``/``initrd_cpio``/``simple_initrd.cpio.gz` `-``-``append` `"init=/init console=ttyS0"` `-``nographic` |
|-|-|

先来看`do_populate_rootfs`函数, 由于指定了-initrd参数，所以initrd_start不为0，会执行`unpack_to_rootfs((char *)initrd_start, initrd_end - initrd_start)`将-initrd选项指定的simple_initrd.cpio.gz内容解压至rootfs,
由于simple_initrd.cpio.gz的格式为cpio gzip压缩格式,所以`unpack_to_rootfs`就会成功就不会进入ramdisk逻辑相关的`populate_initrd_image()`函数中了，并且释放掉initrd占据的物理内存。

回到判断:

| 1234 | `if` `(init_eaccess(ramdisk_execute_command) !``=` `0``) {``ramdisk_execute_command` `=` `NULL;``prepare_namespace();``}` |
|-|-|

由于rootfs中有/init文件这个判断就不会进入。从而直接执行`run_init_process("/init")`执行init程序。

启动过程步骤:`rootfs --> cpio initrd`。

cpio的格式非常简单，内核的解压代码也非常少。这种启动方式虽然也叫initrd,但是用的是cpio格式的initrd,和上面ramdisk格式的initrd区别很大，为主流的启动方式，init进程启动以后可以再执行额外查找并挂载文件系统的操作，只不过这些都是用户空间的事了。

**启动方式5:**

| 1 | `qemu``-``system``-``x86_64` `-``kernel arch``/``x86_64``/``boot``/``bzImage` `-``-``append` `"init=/init console=ttyS0"` `-``nographic` |
|-|-|

有点类似于启动方式4,在`do_populate_rootfs`函数中的`unpack_to_rootfs(__initramfs_start, __initramfs_size)`以后do_populate_rootfs函数就返回了,并且`prepare_namespace函数`也不会走到。
这种启动是将cpio压缩包和内核编译在了一起,启动过程步骤:`rootfs --> initramfs。`

综上所述这五种启动方式都会有可用的rootfs,initrd分为ramdisk initrd和cpio initrd,安卓文档中甚至把initrd也叫做initramfs,因此initrd并不单单指的是ramdisk技术，android boot.img中解压出来的ramdisk文件本质上cpio格式,用的并不是ramdisk initrd技术而是cpio initrd。这些名词概念极容易产生误导，理解了上面启动的代码流程才是最重要的。

## 四.安卓系统启动的三种不同方式

来看一下安卓系统是如何启动的
可以先参考一下magisk的文档:
<https://topjohnwu.github.io/Magisk/boot.html>
安卓的启动流程相当复杂并且一直在演进，演进的是最终目标都是为了提升用户体验、解决碎片化问题并且提升安全性。magisk把安卓启动方式归为三类:

| 1234 | `Method  Initial rootdir  Final rootdir``A        rootfs           rootfs``B        system           system``C        rootfs           system` |
|-|-|

Method A为老设备的rootfs,两阶段都是rootfs。
Method B为system-as-root,两阶段都是system。
Method C为一阶段为rootfs,二阶段为system。

### Method A:

拿运行android 4.4的nexus5设备来说， 它的代号为hammerhead，下载factory包解压以后，可以看到只有这几个文件:

boot.img　--> 刷入boot分区
cache.img --> 刷入cache分区
recovery.img --> 刷入recovery分区
system.img --> 刷入system分区
userdata.img --> 刷入userdata分区，最终挂载为/data
radio-hammerhead-m8974a-2.0.50.1.16.img --> 刷入radio分区
bootloader-hammerhead-hhz11k.img　--> 刷入bootloader分区

旧设备安卓的分区是相当少的，此时甚至没有单独的vendor分区，vendor目录在/system/vendor下，recovery此时有单独的分区。

我们来看boot.img里边有什么内容：
android不仅需要bootloader遵循arm/arm64平台上linux的boot协议:
<https://www.kernel.org/doc/Documentation/arm/Booting>
<https://www.kernel.org/doc/Documentation/arm64/booting.txt>

而且它还定义了自己的boot image格式:
<https://source.android.com/docs/core/architecture/bootloader/boot-image-header?hl=zh-cn>

由boot-image-header结构描述它的格式，到目前为止的Android 13一共有5个版本的boot image header,对于android 4.4来说它用的是版本0:

| 123456789101112131415161718192021 | `struct boot_img_hdr``{``uint8_t magic[BOOT_MAGIC_SIZE];``uint32_t kernel_size;` `/``*` `size` `in` `bytes` `*``/``uint32_t kernel_addr;` `/``*` `physical load addr` `*``/` `uint32_t ramdisk_size;` `/``*` `size` `in` `bytes` `*``/``uint32_t ramdisk_addr;` `/``*` `physical load addr` `*``/` `uint32_t second_size;` `/``*` `size` `in` `bytes` `*``/``uint32_t second_addr;` `/``*` `physical load addr` `*``/` `uint32_t tags_addr;` `/``*` `physical addr` `for` `kernel tags` `*``/``uint32_t page_size;` `/``*` `flash page size we assume` `*``/``uint32_t unused;``uint32_t os_version;``uint8_t name[BOOT_NAME_SIZE];` `/``*` `asciiz product name` `*``/``uint8_t cmdline[BOOT_ARGS_SIZE];``uint32_t` `id``[``8``];` `/``*` `timestamp` `/` `checksum` `/` `sha1` `/` `etc` `*``/``uint8_t extra_cmdline[BOOT_EXTRA_ARGS_SIZE];``};` |
|-|-|

bootloader需要识别boot_img_hdr格式的boot.img,这也是安卓系统对bootloader程序的要求，而正常linux系统下的bootloader只要遵循arm/arm64平台上linux内核的boot协议即可。

随着安卓版本的升级，安卓一些新特性对bootloader提出了越来越多的要求，如Reboot reason,A/B分区，DTBO,用户空间的fastboot,AVB 2.0,bootconfig,vendor_boot分区等等。这些新特性都使Android平台上的bootloader与普通Linux系统的bootloader有很大的区别。

可以在aosp源码根目录执行

| 1 | `make unpack_bootimg` |
|-|-|

，编译出来的out/host/linux-x86/bin/unpack_bootimg可以用于解包boot.img:

| 1 | `out``/``host``/``linux``-``x86``/``bin``/``unpack_bootimg` `-``-``boot_img boot.img` `-``-``out boot_out` |
|-|-|

nexus5的boot.img解包出来只有两个文件kernel和ramdisk。

版本0 boot image中并没有给dtb image留有位置，内核和dtb是打包在一起的，叫zImage-dtb,打包到boot.img时会重命名为kernel。
通过aosp编译hammerhead的boot.img时，zImage-dtb的来源为`device/lge/hammerhead-kernel/zImage-dtb`，当然也可以自己编译内核，替换掉`device/lge/hammerhead-kernel/zImage-dtb`再编译boot.img。

ramdisk的格式为gzip cpio, 解压方式如下:

| 12345 | `mv ramdisk ramdisk.img.gz``gunzip ramdisk.img.gz``mkdir ramdisk_dir``cd ramdisk_dir``cpio` `-``i` `-``F ..``/``ramdisk.img` |
|-|-|

可以看到解压后的目录有init程序以及init.rc等配置文件。
由于ramdisk的格式为gzip cpio,所以对于android 4.4的nexus5来说，所使用的启动方式正是上面描述的启动方式4,对于qemu来说直接指定-initrd参数即可,那么nexus5的bootloader是通过什么方式将initrd传递给内核的呢?

答案是采用的fdt扁平设备树,由上面的<https://www.kernel.org/doc/Documentation/arm/Booting>可知,bootloader可以通过kernel tagged list或者设置设备树的方式向内核传递配置信息,配置信息的物理内存地址存放在寄存器r2中。

bootloader在物理内存中加载完ramdisk以后会修改fdt，设置/chosen节点的`"linux,initrd-start"和"linux,initrd-end"`属性为加载的ramdisk的物理起始地址与物理结束地址。内核拿到配置信息以后会进行如下处理:

| 1234567 | `start_kernel:``setup_arch()``setup_machine_fdt()``of_scan_flat_dt(early_init_dt_scan_chosen, boot_command_line);``early_init_dt_scan_chosen()``early_init_dt_check_for_initrd()``early_init_dt_setup_initrd_arch()` |
|-|-|

从而将ramdisk加载的物理内存起始地址赋值给phys_initrd_start变量，物理内存占据空间赋值给phys_initrd_size变量。最终ramdisk将会被解压至rootfs中。这种启动方式rootfs挂载点并没有被其他挂载点占据，所以系统启动以后仍然可以看到rootfs:

| 1 | `rootfs` `/` `rootfs ro,relatime` `0` `0` |
|-|-|

init进程启动以后会加载`init.hammerhead.rc`配置，在init.hammerhead.rc配置中会执行`mount_all ./fstab.hammerhead`动作，进一步挂载system分区,userdata等其他分区。

对于recovery分区，烧写进去的recovery.img格式也是boot image格式，里边的kernel文件和boot.img中的是一个文件，只是ramdisk不同(因此有一部分的冗余)，bootloader会决定加载boot分区的镜像从而进入正常的系统还是加载recovery分区的镜像从而进入到recovery模式。

### Method B:

`Legacy System-as-root`
谷歌一推出pixel手机系列就开始官方支持A/B分区实现无缝系统更新功能，很多分区现在都有了后缀如system_a,system_b，vendor_a,vendor_b。无缝更新的目标确保在无线下载 (OTA) 更新期间在磁盘上保留一个可正常启动和使用的系统。

A/B分区是为了用户体验而推出的功能，android还有个长久的Project Treble计划用于解决安卓系统更新困难的问题，Project Treble将安卓部分和厂商部分分开,并且定义两者之间稳定的接口从而实现解耦。随后的很多新功能包括system-as-root,hidl,用户空间fastbootd,单独的vendor分区，product分区和ODM分区等都是这种想法的体现。

system-as-root是较早出现的新功能，它的想法是将init程序编译进system镜像，并且将system镜像挂载为/(而不是ramdisk),这样做的原因是想将rootdir和安卓平台绑定，而不是让rootdir和厂商相关部分绑定。

android 6.0开始增加了一个新的编译配置变量`BOARD_BUILD_SYSTEM_ROOT_IMAGE`,当它为true时会指示编译系统将根文件系统合并到system.img中,此时system-as-root是可选的功能。
既然boot.img中已经不需要ramdisk了,那何不去掉recovery分区把recovery的ramdisk放在boot中?
android 7引入了一个新的编译配置变量`BOARD_USES_RECOVERY_AS_BOOT`,当它为true时会指示编译系统将编译出来的ramdisk-recovery.img放在boot.img中替换掉原来的ramdisk。

不过这样就需要添加额外的代码来指示bootloader如何启动recovery模式。这也是pixel手机没有recovery分区的原因(节省空间),不过有的手机从老版本升级到新版本recovery分区还是保留的。

为了说明system-as-root过程，以运行android 7.1.2的pixel1举例：
下载aosp 7.1.2和pixel1厂商相关包编译后`out/target/product/sailfish`下会有ramdisk-`recovery.img,boot.img`文件，解压boot.img以后查看里边的ramdisk确实是和ramdisk-recovery.img是相同的文件。该目录下同时还有system.img文件，它的格式为:

| 12 | `file` `system.img``system.img: Android sparse image, version:` `1.0``, Total of` `524288` `4096``-``byte output blocks` `in` `4409` `input` `chunks.` |
|-|-|

Android sparse image没办法直接挂载，需要使用simg2img工具进行处理:

| 12 | `out``/``host``/``linux``-``x86``/``bin``/``simg2img system.img system_ext4.img``sudo mount system_ext4.img system_mount` |
|-|-|

挂载目录system_mount下可以看到init程序,以及原来出现在rootdir(out/target/product/sailfish/root目录)的其他程序，BOARD_BUILD_SYSTEM_ROOT_IMAGE变量指示编译系统将rootdir和system合在了一起。

进入到pixel1的终端里查看命令行参数/proc/cmdline可以发现如下内容:

| 1 | `root``=``/``dev``/``dm``-``0` `dm``=``"system none ro,0 1 android-verity /dev/sda34"` `rootwait skip_initramfs init``=``/``init` |
|-|-|

skip_initramfs是android在内核中添加的新命令行参数选项:

| 12345678910 | `static` `int` `__initdata do_skip_initramfs;` `static` `int` `__init skip_initramfs_param(char` `*``str``)``{``if` `(``*``str``)``return` `0``;``do_skip_initramfs` `=` `1``;``return` `1``;``}``__setup(``"skip_initramfs"``, skip_initramfs_param);` |
|-|-|

在populate_rootfs()函数中如果do_skip_initramfs为true,则populate_rootfs会提前返回:

| 12345 | `if` `(do_skip_initramfs) {``if` `(initrd_start)``free_initrd();``return` `default_rootfs();``}` |
|-|-|

提前返回就不会解压initramfs和initrd到rootfs,而是直接调用default_rootfs()在rootfs中创建出/dev/console文件,除此之外没有其他文件。

因此接下来的流程和启动方式1一样会进入到`prepare_namespace()`函数，只不过由于设置了"dm="命令行参数会进入到`dm_setup`函数，以及调用后边的`dm_run_setup()`函数。接下来的流程会利用device mapper机制创建出虚拟块设备dm-0,将这个虚拟块设备文件做为根文件系统挂载，除此之外启动流程和上面所述的linux启动方式1是差不多的。

查看`/sys/block/dm-0/slaves`目录就可以看到它所对应的设备文件:

| 12 | `ls` `-``l` `/``sys``/``block``/``dm``-``0``/``slaves``lrwxrwxrwx` `1` `root root` `0` `2017``-``01``-``13` `09``:``40` `sda34` `-``> ..``/``..``/``..``/``..``/``soc``/``624000.ufshc``/``host0``/``target0:``0``:``0``/``0``:``0``:``0``:``0``/``block``/``sda``/``sda34` |
|-|-|

如果内核命令行参数中没有设置skip_initramfs，那么boot.img中的ramdisk会被解压到rootfs中，就不会走到`prepare_namespace()`函数，而是直接跳到ramdisk中执行，也就是进入到recovery模式。

那么在system-as-root的情况下如何重新挂载system目录所在的分区呢?
具体的逻辑在`system/core/adb/remount_service.cpp`的`remount_partition()`函数中，由于现在/proc/mounts无法体现出/所在设备情况:

| 123 | `sailfish:``/` `# cat /proc/mounts``rootfs` `/` `rootfs rw,seclabel` `0` `0``/``dev``/``root` `/` `ext4 ro,seclabel,relatime,data``=``ordered` `0` `0` |
|-|-|

需要进一步分析厂商的fstab文件才能得到/目录所在的设备，这里就是/fstab.sailfish文件：

| 12 | `#<src>                                  <mnt_point>       <type>  <mnt_flags and options>                     <fs_mgr_flags>``/``dev``/``block``/``bootdevice``/``by``-``name``/``system` `/`           `ext4    ro,barrier``=``1``,discard                                wait,slotselect,verify` |
|-|-|

知道/对应的设备以后执行重新挂载就可以了。

### Method C:

这种启动方式bootloader仍然会传递initrd给内核，这样initrd就会解压至rootfs中做为初始的根文件系统，并在上执行/init进程，而/init进程负责挂载system分区并且把它做为新的rootdir,并且进一步执行/system/bin/init程序完成系统启动的剩余步骤。

这种方式又被magisk作者称为两阶段的``ramdisk system-as-root`。在谷歌的角度只有Method B才被称为system-as-root,对于Method C它虽然也是将"system挂载为(as)root",但是从启动的角度来说和Method B有本质的区别。所以在谷歌的官方文档中如果看到这样的描述,里边的system-as-root指的就是启动方式Method B:
"搭载 Android 10 的设备不得使用 system-as-root。"

从Method B进化到Method C，有部分原因是因为动态分区这一新特性的引入:
Android 10引入了动态分区的概念，因为A/B分区的存在，导致可用分区空间减少了很多，如果system,vendor,product等分区大小没有规划好，很有可能会影响到后边系统的升级。而动态分区会分配出super逻辑分区将system,vendor,product分区纳入其中，子分区可动态调整大小,各个分区映像不再需要为将来的 OTA 预留空间。

动态分区是通过Linux内核device-mapper框架的dm-linear插件实现的，bootloader和Linux内核无法解读super分区，因此无法自行装载system本身。所以Method B启动方式不再适用，需要新的启动方式就是Method C。

由于bootloader无法理解动态分区，因此无法对其进行刷写，安卓引入了另外一个新的功能:用户空间fastbootd，原来由闭源bootloader实现的功能，现在放在了recovery模式下的fastbootd实现，阅读fastbootd的代码还可以学习到fastboot协议实现的细节，fastbootd可以通过hal接口调用厂商特有的功能，用户空间fastbootd也算是Project Treble目标的一种体现。

以运行android 10的pixel 3xl举例，下载厂商二进制包放在android 10源码中编译以后,会生成boot.img和ramdisk-recovery.img,其中boot.img中的ramdisk正是ramdisk-recovery.img文件，新的内核可以在/proc文件系统中查看设备树的信息:

| 12345 | `cat` `/``proc``/``device``-``tree``/``chosen``/``linux,initrd``-``start \| xxd``00000000``:` `0000` `0000` `8470` `0000`                      `.....p..` `cat` `/``proc``/``device``-``tree``/``chosen``/``linux,initrd``-``end \| xxd` `00000000``:` `0000` `0000` `8515` `3be9` |
|-|-|

0x85153be9 - 0x84700000 = 10828777
而编译出来的ramdisk-recovery.img大小也正是10828777字节。

ramdisk-recovery.img中也有个init程序，它里边的init程序和编译到system.img中的init程序有什么区别？

ramdisk-recovery.img中的init是个指向/system/bin/init的软链接，system/core/init/Android.bp文件中有如下语句:

| 12345678910111213141516171819202122 | `cc_binary {``name:` `"init_second_stage"``,``recovery_available: true,``stem:` `"init"``,``defaults: [``"init_defaults"``],``static_libs: [``"libinit"``],``required: [``"e2fsdroid"``,``"mke2fs"``,``"sload_f2fs"``,``"make_f2fs"``,``],``srcs: [``"main.cpp"``],``symlinks: [``"ueventd"``],``target: {``recovery: {``cflags: [``"-DRECOVERY"``],``exclude_shared_libs: [``"libbinder"``,` `"libutils"``],``},``},``ldflags: [``"-Wl,--rpath,/system/${LIB}/bootstrap"``],``}` |
|-|-|

注意上面的Android.bp中声明了recovery_available: true。只要声明了recovery_available: true或者recovery: true的都会编译到recovery目录最终打包成ramdisk-recovery.img镜像:

| 123456 | `Shared library support` `in` `recovery mode``In Android` `10``, shared libraries are available` `in` `the recovery partition, which eliminates the need` `for` `all` `recovery mode executables to be static. The shared libraries are located under the` `/``system``/``lib (``or` `/``system``/``lib64` `for` `64``-``bit devices) directory` `in` `the partition.` `To add a new shared library to the recovery partition, add recovery_available: true` `or` `recovery: true to Android.bp of the shared library. The former installs the library to both the system` `and` `recovery partitions,` `while` `the latter installs it only to the recovery partition.` `Shared library support can``'t be built with Android'``s make``-``based build system. To convert an existing static executable` `for` `the recovery mode to a dynamic one, remove LOCAL_FORCE_STATIC_EXECUTABLE :``=` `true` `in` `Android.mk` `or` `static_executable: true (``in` `Android.bp ).` |
|-|-|

由于指定了stem属性，所以生成的目标产物名称为init，而且recovery目录的system/bin/init程序它指定了exclude_shared_libs从而排除了libbinder和libutils库，因为不需要这两个库。

和启动方式2不同的地方是现在必须从initrd启动，所以之前用于指示是否进入recovery模式的do_skip_initramfs内核命令行参数不再使用，android 10引入了新的androidboot.force_normal_boot参数，它的值为1时表示进入正常的系统，否则才会进入recovery模式。和init第一阶段挂载相关还有新的内核命令行参数`androidboot.boot_devices`。

看一下启动流程,ramdisk-recovery.img会被解压到rootfs中并且执行/init，根据上面的描述/init的代码仍然编译自system/core/init目录,因此执行函数从system/core/init/main.cpp的main函数开始:

| 123456789101112131415161718192021 | `FirstStageMain(){``....``if` `(ForceNormalBoot()) {``mkdir(``"/first_stage_ramdisk"``,` `0755``);``/``/` `SwitchRoot() must be called with a mount point as the target, so we bind mount the``/``/` `target directory to itself here.``if` `(mount(``"/first_stage_ramdisk"``,` `"/first_stage_ramdisk"``, nullptr, MS_BIND, nullptr) !``=` `0``) {``LOG(FATAL) <<` `"Could not bind mount /first_stage_ramdisk to itself"``;``}``SwitchRoot(``"/first_stage_ramdisk"``);``}``....``if` `(!DoFirstStageMount()) {``LOG(FATAL) <<` `"Failed to mount required partitions early ..."``;``}``...``const char``*` `path` `=` `"/system/bin/init"``;``const char``*` `args[]` `=` `{path,` `"selinux_setup"``, nullptr};``execv(path, const_cast<char``*``*``>(args));``...` `}` |
|-|-|

`ForceNormalBoot`用于判断是不是正常启动系统:

| 12345 | `bool` `ForceNormalBoot() {``std::string cmdline;``android::base::ReadFileToString(``"/proc/cmdline"``, &cmdline);``return` `cmdline.find(``"androidboot.force_normal_boot=1"``) !``=` `std::string::npos;``}` |
|-|-|

如果是正常启动系统则将根切换到/first_stage_ramdisk目录:
SwitchRoot是通过move bind和chroot来实现切换根操作的。
/first_stage_ramdisk目录有如下文件:

| 12 | `drwxrwxr``-``x` `4096` `7``月` `18`  `2022` `avb``-``rw``-``rw``-``r``-``-` `2015` `7``月` `18`  `2022` `fstab.sdm845` |
|-|-|

avb目录下存放着验证启动相关的公钥文件,是通过源码`system/core/rootdir/avb/`生成出来的。

fstab.sdm845是厂商相关的文件系统挂载表,由`device/google/crosshatch/device.mk`文件拷贝生成:

| 12 | `PRODUCT_COPY_FILES` `+``=` `\``device``/``google``/``crosshatch``/``fstab.hardware:$(TARGET_COPY_OUT_RECOVERY)``/``root``/``first_stage_ramdisk``/``fstab.$(PRODUCT_PLATFORM)` |
|-|-|

接下来执行`DoFirstStageMount()`函数进行第一阶段挂载，如果是recovery模式则跳过此阶段。

第一阶段挂载执行完以后就执行/system/bin/init程序，跳到下一阶段selinux_setup。此时的/system/bin/init已经不再是ramdisk-recovery.img中的/system/bin/init,实际上它执行的是system.img中的/system/bin/init程序。

看一下`DoFirstStageMount`到底做了什么:
首先寻找挂载所需fstab文件，文件内容可以通过设备树传递，对于pixel3xl来说对应的路径为`/first_stage_ramdisk/fstab.sdm845`,只有标记为`first_stage_mount`的挂载点才会在这一阶段处理,以下是具有`first_stage_mount`标记的项:

| 1234567 | `# Android fstab file.` `#<src>                                              <mnt_point>        <type>      <mnt_flags and options>                               <fs_mgr_flags>``system` `/``system            ext4        ro,barrier``=``1`                                          `wait,slotselect,avb``=``vbmeta,logical,first_stage_mount``vendor` `/``vendor            ext4        ro,barrier``=``1`                                          `wait,slotselect,avb,logical,first_stage_mount``product` `/``product           ext4        ro,barrier``=``1`                                          `wait,slotselect,avb,logical,first_stage_mount``/``dev``/``block``/``by``-``name``/``metadata` `/``metadata          ext4        noatime,nosuid,nodev,discard,sync                     wait,formattable,first_stage_mount` |
|-|-|

第一阶段装载的目标就是挂载/system,/vendor,/product和/metadata。

然后进入`FirstStageMount::DoFirstStageMount`逻辑:

| 123456789101112131415 | `bool` `FirstStageMount::DoFirstStageMount() {``if` `(!IsDmLinearEnabled() && fstab_.empty()) {``/``/` `Nothing to mount.``LOG(INFO) <<` `"First stage mount skipped (missing/incompatible/empty fstab in device tree)"``;``return` `true;``}` `if` `(!InitDevices())` `return` `false;` `if` `(!CreateLogicalPartitions())` `return` `false;` `if` `(!MountPartitions())` `return` `false;` `return` `true;``}` |
|-|-|

InitDevices()主要做的事情是初始化一些数据结构，创建出/dev/device-mapper设备节点以及触发uevent事件创建出subsystem为block的设备节点。
触发uevent事件的逻辑是遍历/sys/class,/sys/block,/sys/devices目录下的uevent文件，向其中写入"add\n",并且利用netlink机制获取内核传递过来的uevent消息。

这个过程处理完就会在/dev/block下创建出设备及分区的设备节点，以及一些符号链接，比如system_a分区的设备名为sda5,那么就会创建出/dev/block/sda5及如下符号链接:

| 123 | `/``dev``/``block``/``platform``/``soc``/``1d84000``.ufshc``/``by``-``name``/``system_a` `-``>` `/``dev``/``block``/``sda5``/``dev``/``block``/``by``-``name``/``system_a` `-``>` `/``dev``/``block``/``sda5``/``dev``/``block``/``platform``/``soc``/``1d84000``.ufshc``/``sda5` `-``>` `/``dev``/``block``/``sda5` |
|-|-|

`CreateLogicalPartitions()`会从动态分区元数据所在分区中读取出动态分区数据，这个分区并不一定是super分区，像pixel3xl这种上市的时候是android 9,它是没有super分区的，升级到android 10需要使用动态分区功能需要进行如下的配置:
`BOARD_SUPER_PARTITION_METADATA_DEVICE := system`

这个配置会生成内核命令行参数: `"androidboot.super_partition=system"`, 表示system分区是容纳其他分区的"super"分区。通过dd命令将/dev/block/sda5分区数据dump出来，跳转到0x1000处就可以看到魔数:`LP_METADATA_GEOMETRY_MAGIC 0x616c4467`。

`CreateLogicalPartitions`函数会调用device mapper的接口创建出表示各个分区的dm设备:

| 123 | `[` `1.108482``] init: [libfs_mgr]Created logical partition system_a on device` `/``dev``/``block``/``dm``-``0``[` `1.109118``] init: [libfs_mgr]Created logical partition vendor_a on device` `/``dev``/``block``/``dm``-``1``[` `1.109711``] init: [libfs_mgr]Created logical partition product_a on device` `/``dev``/``block``/``dm``-``2` |
|-|-|

这三个设备的物理分区都是system_a分区:

| 12345678 | `ls` `-``l` `/``sys``/``block``/``dm``-``0``/``slaves``/``sda5` `-``> ..``/``..``/``..``/``..``/``platform``/``soc``/``1d84000``.ufshc``/``host0``/``target0:``0``:``0``/``0``:``0``:``0``:``0``/``block``/``sda``/``sda5` `ls` `-``l` `/``sys``/``block``/``dm``-``1``/``slaves``/``sda5` `-``> ..``/``..``/``..``/``..``/``platform``/``soc``/``1d84000``.ufshc``/``host0``/``target0:``0``:``0``/``0``:``0``:``0``:``0``/``block``/``sda``/``sda5` `ls` `-``l` `/``sys``/``block``/``dm``-``2``/``slaves``/``sda5` `-``> ..``/``..``/``..``/``..``/``platform``/``soc``/``1d84000``.ufshc``/``host0``/``target0:``0``:``0``/``0``:``0``:``0``:``0``/``block``/``sda``/``sda5` |
|-|-|

接着调用`MountPartitions()`函数,在这个函数中会创建出额外的逻辑块设备用于单独挂载system,vendor与product镜像:

| 123 | `init: [libfs_mgr]__mount(source``=``/``dev``/``block``/``dm``-``3``,target``=``/``system,``type``=``ext4)``=``0``: Success``init: [libfs_mgr]__mount(source``=``/``dev``/``block``/``dm``-``4``,target``=``/``vendor,``type``=``ext4)``=``0``: Success``init: [libfs_mgr]__mount(source``=``/``dev``/``block``/``dm``-``5``,target``=``/``product,``type``=``ext4)``=``0``: Success` |
|-|-|

挂载完system镜像以后,调用`SwitchRoot("/system")`执行切换根操作,从此init进程的根目录(初始挂载命名空间)就切换到了system镜像中，下一阶段执行的selinux_setup就已经不再是原来的init文件了,随后的事情将由system.img中的/system/bin/init程序接管。

动态分区会对system分区的重挂载为读写产生影响,adb remount需要做相应的调整，实现方式是利用overlayfs在只读文件系统上加上读写层，详细内容参考链接:
<https://android.googlesource.com/platform/system/core/+/a9a3b73163fda5abf237cc0f0cee97ff33e6254d/fs_mgr/README.overlayfs.md>

随着安卓系统的升级,Method C已经成了必须的支持选项,这不仅包括新出厂的设备还包括升级到更新版本安卓的旧设备。
可以看到安卓系统的启动比起linux的启动复杂了很多,它对bootloader有很多的要求，不过一旦满足了安卓的启动要求，后续的系统升级将会越来越简单。

## 五. magisk原理:

安卓启动方式的不同对magisk的影响很大，magisk文档中描述最糟糕的设备类型是2018-2019年出现的非A/B分区的设备，这种设备在boot.img中没有ramdisk存在，这种设备需要每次启动至recovery模式才能让magisk正常工作。比如samsung的galaxy s10 5G(如果这款设备刷了lineageos就会发现boot.img当中有ramdisk了)，先从代码层次了解一下magisk的原理吧。

magisk的根本原理是修改设备原始的boot.img的内容替换掉一阶段init，由于不会影响到system分区的内容，所以叫systemless。init进程刚启动的时候拥有最大的权限,此时selinux策略还没有加载,magisk的init进程可以做任何它想做的事情。

1.首先magisk app会执行`manager.sh`脚本判断当前的设备是否拥有ramdisk:

| 123456789 | `app_init() {``mount_partitions``RAMDISKEXIST``=``false``check_boot_ramdisk && RAMDISKEXIST``=``true``get_flags``run_migrations``SHA1``=``$(grep_prop SHA1 $MAGISKTMP``/``config)``check_encryption``}` |
|-|-|

上面曾提到过站在谷歌的角度只有Method B才是System-as-root设备，而在Magisk作者的角度Method B和Method C都是System-as-root(SAR)。Magisk作者称谷歌角度的System-as-root为Legacy System-as-root。

check_boot_ramdisk函数的逻辑如果是A/B设备(是否为A/B设备是通过ro.build.ab_update和ro.boot.slot_suffix属性获得的)肯定会有ramdisk。

如果不是A/B设备,但是又是`Legacy system-as-root`(Method B启动方式),那么就会定为没有ramdisk,这种设备recovery分区还在,所以recovery-ramdisk.img没有存放在boot.img中，换句话说就是没有设置`BOARD_USES_RECOVERY_AS_BOOT`编译变量。

是否是Method B启动由如下命令来判断:

| 1 | `grep` `' / '` `/``proc``/``mounts \| grep` `-``q` `'/dev/root'` |
|-|-|

因为根据上面的代码分析只有Method B启动才会创建出ROOT_DEV的设备节点/dev/root并挂载。

有ramdisk的设备magisk可以执行程序patch原始的boot.img中的ramdisk,而没有ramdisk的设备magisk只能去修改recovery分区的内容了。

看一下magisk的patch流程:

| 1234567891011121314151617 | `patch执行的脚本为boot_patch.sh,解压完boot.img以后提取出里边的ramdisk文件做如下处理:``.``/``magiskboot cpio ramdisk.cpio \``"add 0750 $INIT magiskinit"` `\` `#将编译出来的magiskinit替换掉里边的init程序``"mkdir 0750 overlay.d"` `\` `#创建出overlay.d目录``"mkdir 0750 overlay.d/sbin"` `\``#创建出overlay.d/sbin目录``"$SKIP32 add 0644 overlay.d/sbin/magisk32.xz magisk32.xz"` `\` `#将magisk32守护进程执行文件压缩包拷贝至overlay.d/sbin目录``"$SKIP64 add 0644 overlay.d/sbin/magisk64.xz magisk64.xz"` `\` `#将magisk64守护进程执行文件压缩包拷贝至overlay.d/sbin目录``"add 0644 overlay.d/sbin/stub.xz stub.xz"` `#stub.xz文件添加至overlay.d/sbin,stub.xz是stub.apk的压缩包用于隐藏magisk app的功能``"patch"` `\``#如果不需要保留验证启动的功能则将fstab中dm-verity相关项(如verifyatboot)去掉，如果不需要保留分区加密功能则将fstab中分区加密相关项(如forceencrypt)去掉``"backup ramdisk.cpio.orig"` `\``#主要备份的是init程序``"mkdir 000 .backup"` `\``"add 000 .backup/.magisk config"``#将配置项保存在.backup/.magisk文件中，里边的内容如下示:``KEEPVERITY``=``true``KEEPFORCEENCRYPT``=``true``PATCHVBMETAFLAG``=``false``RECOVERYMODE``=``false``SHA1``=``ea36c0b1d697814f99d38984d720875274bb1764` |
|-|-|

接下来patch dtb中的内容,因为挂载参数和内核命令行参数可能来自dtb,需要替换掉dtb内核命令行参数中的`skip_initramfs`，修改为`want_initramfs`,回想一下如果设置了`skip_initramfs`代表着Method B启动方式中进入到正常系统而不是recovery，不会从boot.img中的ramdisk启动，magisk也就无法启动了，修改为`want_initramfs`屏蔽掉`skip_initramfs`让系统可以从ramdisk中启动。

**注:**
**谢"残页"提醒，patch dtb其实是因为三星手机的特殊行为: **<https://github.com/topjohnwu/Magisk/pull/4788>

如果dtb中有指定挂载标志fsmgr_flags,且不需要保留验证启动的功能，和上面修改fstab一样，直接移除掉fsmgr_flags中和dm-verity相关字符串。

接下来patch内核,这块逻辑对三星的手机有额外的处理:

| 12345678910 | `#Remove Samwqsung RKP``.``/``magiskboot hexpatch kernel \``49010054011440B93FA00F71E9000054010840B93FA00F7189000054001840B91FA00F7188010054` `\``A1020054011440B93FA00F7140020054010840B93FA00F71E0010054001840B91FA00F7181010054` `# Remove Samsung defex``# Before: [mov w2, #-221]   (-__NR_execve)``# After:  [mov w2, #-32768]` `.``/``magiskboot hexpatch kernel` `821B8012` `E2FF8F12` |
|-|-|

然后直接将内核中`skip_initramfs`字节表示替换为`want_initramfs`的字节表示，原先的`skip_initramfs`配置变更为`want_initramfs`配置,那么do_skip_initramfs变量的值永远为0。skip和want都是四字节，所以不会对内核长度有影响:

| 123 | `.``/``magiskboot hexpatch kernel \``736B69705F696E697472616D667300` `\``77616E745F696E697472616D667300` |
|-|-|

bootloader仍然按原来的方式传递skip_initramfs参数给内核,只不过配置不会生效，magisk可以读取skip_initramfs参数判断出启动的真正意图。

patch过程结束,拿到boot.img重新烧写启动就会导致magiskinit接管init进程。

magisk init启动流程,`native/src/init/init.cpp`的main函数:
不同的启动流程如下:

| 12345678910111213 | `/``/` `This will also mount` `/``sys` `and` `/``proc``load_kernel_info(&config);` `if` `(config.skip_initramfs)``init` `=` `new LegacySARInit(argv, &config);``else` `if` `(config.force_normal_boot)``init` `=` `new FirstStageInit(argv, &config);``else` `if` `(access(``"/sbin/recovery"``, F_OK)` `=``=` `0` `\|\| access(``"/system/bin/recovery"``, F_OK)` `=``=` `0``)``init` `=` `new RecoveryInit(argv, &config);``else` `if` `(check_two_stage())``init` `=` `new FirstStageInit(argv, &config);``else``init` `=` `new RootFSInit(argv, &config);` |
|-|-|

以下是magisk需要区分的四种不同的场景。()
 ![image](https://bbs.kanxue.com/upload/attach/202302/607812_SEKPGQHPE9YZ8WB.png)

### Type I:

1.如果要启动的是正常系统,那么会归入最后一种情况进入到`init = new RootFSInit(argv, &config);`
2.如果要启动的是recovery模式，由于recovery分区并未被magisk修改,直接从recovery分区启动即可

### Type II:

1.如果要启动的是正常系统,由于存在命令行参数skip_initramfs,会进入到`init = new LegacySARInit(argv, &config);`
2.如果要启动的是recovery模式,不会存在skip_initramfs参数,但由于boot.img中的ramdisk是ramdisk-recovery.img,所以会有/sbin/recovery或者/system/bin/recovery文件，进入到`init = new RecoveryInit(argv, &config);`

### Type III:

此种情况magisk patch的是recovery分区的ramdisk。
1.如果要启动的是正常系统,直接进入无magisk的原始系统。
2.如果要启动的是recovery模式,会导致magisk init执行，magisk init读取/.backup/.magisk配置文件得到`RECOVERYMODE=true`知道它自己是在recovery分区启动,它会调用check_key_combo()判断是否长按音量键上,如果长按则进入magisk系统,否则进入到原来的recovery系统。进入magisk系统仍然进入到`init = new LegacySARInit(argv, &config);`进入recovery模式会进入`init = new RecoveryInit(argv, &config);`

### Type IV:

1.如果要启动的是正常系统,由于有很多新的配置是随着Method C出现的,如force_normal_boot,/apex目录,所以会通过判断进入到`init = new FirstStageInit(argv, &config)`
2.如果要启动的是recovery模式,由于存在/system/bin/init文件。仍然会进入到`init = new FirstStageInit(argv, &config)`

接下来依次看每个函数做的事情:

`RecoveryInit`函数最简单,需要进入recovery模式,此时/.backup/init就是原先recovery模式的执行程序,将它替换掉/init然后执行它就可以了。

对于其他启动的情况,magisk需要完成它对系统的修改以后才能调用原始/.backup/init程序继续启动。

magisk对系统的修改需要对最终的根文件系统做出修改，根据启动方式的不同，此时根文件系统为可写状态或者为只读状态，可写状态调用的函数为`patch_rw_root()`,只读状态调用的函数为`patch_ro_root()`。

比如对于Method C,它是两阶段启动，一阶段位于rootfs,二阶段位于system，想要对真正的根文件系统做修改，magisk需要等待一阶段的`DoFirstStageMount`结束,magisk将一阶段/init文件中的/system/bin/init替换为/data/magiskinit(因为直接替换的elf文件，两个路径长度要一样都为16),然后执行原始的/.backup/init文件,一阶段DoFirstStageMount结束后挂载system分区切换根操作然后执行的是/data/magiskinit(路径被替换了),传递的命令行参数为`selinux_setup`,此时magisk init继续执行，进入分支`init = new SecondStageInit(argv);` 此时magisk init所处的环境就是根文件系统为只读挂载。

而对于Method A，magisk init所处环境就是根文件系统为可写挂载,执行完前期操作以后,再由init.rc中重新挂载为只读:

| 12 | `# once everything is setup, no need to modify /``mount rootfs rootfs` `/` `ro remount` |
|-|-|

`patch_ro_root()`是依靠bind mount来实现对只读根文件系统做出修改的,它的做法是在可读写的其他分区(/sbin存在就是/sbin,否则就是/dev)创建出临时目录.magisk/rootdir，所有对根文件系统做出的修改都写入此临时目录,接着调用`magic_mount(ROOTOVL)`利用bind mount将临时目录下所有文件映射到/目录下对应的文件。本质上并没有修改只读的根文件系统，bind mount是个可以实现不少黑科技的技术,比如结合命名空间可以实现文件重定向。

对于`Legacy System-as-root`来说,magisk init是从ramdisk中启动的，最终的根文件系统会以dm虚拟块设备的方式挂载，因此magisk init需要查找根文件设备挂载它以后才能对根文件系统做出修改,具体的逻辑在LegacySARInit类的mount_system_root函数中,这里就不详细描述了。这种情况下system分区被magisk挂载为只读:

| 1 | `if` `(xmount(``"/dev/root"``,` `"/system_root"``,` `"ext4"``, MS_RDONLY, nullptr))` |
|-|-|

修改根文件系统仍然是`patch_ro_root函数`，总体来说还是实现了magisk的"systemless"的目标....

magisk面对的设备种类很多,有些设备还有它自己独特的行为,magisk需要一一处理。

**修改系统:**
magisk对系统的修改主要是为了能启动magisk root管理守护进程,这需要修改init.rc文件，加入magisk的service,添加的片段见文件`native/src/init/magiskrc.inc`。由于selinux的存在,还需要修改selinux的策略。

selinux刚出现的时候selinuxfs是会被内核挂载并且加入sysfs中的,不过android8和android 9的selinuxfs由init进程来挂载,magisk init启动的时候`/sys/fs/selinux`还不存在,magisk init必须启动原始的init文件挂载完selinuxfs以后才能对selinux策略进行patch，这也是bool MagiskInit::hijack_sepolicy()函数比较复杂的一个原因。magisk对selinux策略做出的一些修改可以参照`void sepolicy::magisk_rules()`函数。

由上面可知,magisk还是相当复杂的,限于篇幅还有很多功能没有描述,不过理解了安卓启动以后,magisk整体工作原理就清楚了,后边如果再想知道它某一个细节的实现,找出代码和理解它的原理就不再是难事了。

理解上述的启动过程不仅对整个系统的理解会更有帮助，对于实现虚拟化技术如安卓模拟器、容器化云手机也是必备的技能。
安卓启动还有很多功能如avb,磁盘加密等这里没有提及,且随着安卓系统的演进会有更多新的技术加入进来，不过总体的原理是一样的。

---

# 回复

## 回复 by huangjw (#2)

*2023-2-2 09:38*

优秀文章，学习下

## 回复 by shinratensei (#3)

*2023-2-2 10:03*

tql

## 回复 by TUGOhost (#4)

*2023-2-2 10:34*

tql

## 回复 by Ylarod (#5)

*2023-2-2 10:53*

tql

## 回复 by 你瞒我瞒 (#6)

*2023-2-2 11:05*

![image](https://bbs.kanxue.com/view/img/face/1.gif)期待着大佬把面具直接移植到AOSP中

## 回复 by luoyesiqiu (#7)

*2023-2-2 12:09*

tql

## 回复 by 胡一米 (#8)

*2023-2-2 12:31*

tql

## 回复 by mudebug (#9)

*2023-2-2 12:51*

tql

## 回复 by 爱吃菠菜 (#10)

*2023-2-2 13:59*

内容十分hardcore ,没几个月我是真的学不会. ![image](https://bbs.kanxue.com/view/img/face/56.gif)

## 回复 by 飞翔的猫咪 (#11)

*2023-2-2 14:28*

>
> [爱吃菠菜](https://bbs.kanxue.com/user-760871.htm)
>
>  内容十分hardcore ,没几个月我是真的学不会. [em_56]
>
>

其实就是里边牵扯的内容比较多,深度倒不是太深![image](https://bbs.kanxue.com/view/img/face/85.gif)

## 回复 by saloyun (#12)

*2023-2-2 17:23*

tql

## 回复 by fengyunabc (#13)

*2023-2-2 18:15*

感谢分享！

## 回复 by Amun (#14)

*2023-2-2 18:16*

真棒。刚好有台 ARM 服务器在吃灰，我看看怎么把 magisk 塞进 cuttlefish 云手机镜像里。

## 回复 by DirtyAngle (#15)

*2023-2-3 10:58*

大佬司还招人,吗

## 回复 by 残页 (#16)

*2023-2-3 11:35*

Patch DTB 部分 “回想一下如果设置了skip_initramfs代表着Method B启动方式中进入到正常系统而不是recovery，不会从boot.img中的ramdisk启动，magisk也就无法启动了”
这句话不对，加这个 patch 的原因是三星部分机型不支持 SAR 但是 cmdline 里却有这个参数，正常启动的时候内核会直接忽略，但是 Magisk 会因为有这个参数而判断这台设备是 Legacy SAR，进入 Legacy SAR 流程导致手机无法启动。这里 Patch 的本质是『不让 magisk 自己看到错误的参数』，而不是『阻止设备挂载 /system 到 /』。参见 https://github.com/topjohnwu/Magisk/pull/4788

## 回复 by 残页 (#17)

*2023-2-3 11:48*

“selinux刚出现的时候selinuxfs是会被内核挂载并且加入sysfs中的,不过android8和android 9的selinuxfs由init进程来挂载”
这句话我也觉得有问题，我印象里所有设备的 selinuxfs 都由 init 挂载，但是老的设备只支持单个 sepolicy，直接 patch /sepolicy 就行；新一点的设备开始支持 split policy，sepolicy 由多个 cil 文件组成，这种情况才需要 hijack_sepolicy
代码里专门注释说这里是 android 8-9 only的原因在于：老设备不走这个逻辑；10+ 以上 init 一定是 Two Stage，selinuxfs 在 init first stage 挂载，magisk 等 first stage 跑完之后再去 hijack 所以不会遇到问题；而 Android 8-9 可能是 rootfs 也可能是 Single Stage Init 的 SAR，这两种情况 hijack_sepolicy 会比 init 先跑，init 没机会 mount selinuxfs。

## 回复 by 飞翔的猫咪 (#18)

*2023-2-3 13:32*

>
> [残页](https://bbs.kanxue.com/user-764835.htm)
>
>  Patch DTB 部分 “回想一下如果设置了skip_initramfs代表着Method B启动方式中进入到正常系统而不是recovery，不会从boot.img中的ramdisk启动，magis ...
>
>

patch dtb的部分你说的对，看来和patch kernel还不是一个目的，这种手机太少了,例外情况本来不打算说太多的

## 回复 by 飞翔的猫咪 (#19)

*2023-2-3 13:42*

>
> [残页](https://bbs.kanxue.com/user-764835.htm)
>
>  “selinux刚出现的时候selinuxfs是会被内核挂载并且加入sysfs中的,不过android8和android 9的selinuxfs由init进程来挂载”
> 这句话我也觉得有问题，我印象里 ...
>
>

android 7.1.2的selinuxfs挂载竟然隐藏在selinux_android_load_policy()里，老哥靠谱![image](https://bbs.kanxue.com/view/img/face/19.gif)，有空我改一下

## 回复 by 残页 (#20)

*2023-2-3 14:48*

嗯，另外“如果长按则进入magisk系统,否则进入到原来的recovery系统” 这里写反了，长按进原来的 recovery 否则进入带 magisk 的系统 才对
另外不是所有 Type 3 设备都只能修补 recovery，我记得小米全部 Type 3 手机都能直接修补 boot.img

## 回复 by nevinhappy (#21)

*2023-2-3 15:37*

tql，码上后面学习。

## 回复 by Ssssone (#22)

*2023-2-3 19:23*

学习，膜拜

## 回复 by seeeseee (#23)

*2023-2-4 13:58*

学习，膜拜

## 回复 by lvcoffee (#24)

*2023-2-4 18:06*

这深度，广度，叹为观止，膜拜

## 回复 by vigiles (#25)

*2023-2-4 21:32*

太干，难啃![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by koflfy (#26)

*2023-2-6 11:26*

mark

## 回复 by 万里星河 (#27)

*2023-2-6 17:12*

牛逼克拉斯

## 回复 by guijingwen (#28)

*2023-2-6 21:29*

好像没看懂，尴尬

## 回复 by ChengQing (#29)

*2023-2-7 09:25*

虽然不知道在说什么但感觉好厉害的样子

## 回复 by xxRea (#30)

*2023-2-8 11:07*

优秀文章，学习下

## 回复 by Grav1ty (#31)

*2023-2-10 20:25*

膜拜 最近看到magisk获取鸿蒙root权限，这就尴尬了

## 回复 by lxcoder (#32)

*2023-5-4 00:46*

666![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by caocaofff (#33)

*2023-5-4 10:10*

good job

## 回复 by log2 (#34)

*2023-8-4 21:14*

多写点文章求求你了

## 回复 by 哇哈哈919 (#35)

*2023-11-7 09:54*

谢谢大佬的详细解读，膜拜大佬。最近在学习Xposed的原理，就不得不学习一些android系统的加载流程。

## 回复 by Jecelyin (#36)

*2023-12-5 11:36*

好久没看过如此好文了

## 回复 by 万里星河 (#37)

*2025-8-8 18:16*

重温经典

## 回复 by 阳光宝贝 (#38)

*2025-8-14 00:40*

感谢分享

## 回复 by 万里星河 (#39)

*2026-3-10 13:23*

重温^2经典
