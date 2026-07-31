---
title: '[原创] 初探安卓隐藏Bootloader锁'
url: https://bbs.kanxue.com/thread-278445.htm
tid: 278445
author: cslime
date: '2023-08-17'
tags: [Android安全, 原创, 程序开发, HOOK注入, 系统相关]
crawled_at: '2026-07-31T14:39:13+08:00'
replies: 35
---

# 初探安卓隐藏Bootloader锁

做完硬件断点记录器后就开始研究如何隐藏Android的Bootloader锁了,当然最近没啥兴趣继续研究了,把目前为止的思路发出来

首先想到的一个方向是要先spoof安卓Setting里的oemlock status

## 收集所需信息

在aoxpxref网站上搜索

`bootloader unlocked`

看到一个可疑的文件

`/frameworks/base/core/java/android/service/oemlock/OemLockManager.java`

xref 找到

`/frameworks/base/services/core/java/com/android/server/oemlock/OemLockService.java`

看到函数

| 12345678910111213 | `private` `static` `final` `String FLASH_LOCK_PROP =` `"ro.boot.flash.locked"``;``private` `static` `final` `String FLASH_LOCK_UNLOCKED =` `"0"` `public` `boolean` `isDeviceOemUnlocked() {``enforceOemUnlockReadPermission();``String locked = SystemProperties.get(FLASH_LOCK_PROP);``switch` `(locked) {``case` `FLASH_LOCK_UNLOCKED:``return` `true``;``default``:``return` `false``;``}``}` |
|-|-|

可以看到Setting检测的是系统属性 `ro.boot.flash.locked` 来判断Bootloader是否解锁

AOSP搜索`ro.boot.flash.locked`,发现`/system/core/init/init.cpp` 有初始化该属性值的代码

| 12345678 | `static` `void` `export_oem_lock_status() {``if` `(!android::base::GetBoolProperty(``"ro.oem_unlock_supported"``,` `false``)) {``return``;``}``SetProperty(``"ro.boot.flash.locked"``,``android::base::GetProperty(``"ro.boot.verifiedbootstate"``,` `""``) ==` `"orange"` `?` `"0"` `:` `"1"``);``}` |
|-|-|

`ro.boot.flash.locked` 的值是受到 `ro.boot.verifiedbootstate` 的值影响

google搜了一下后面的这个属性,发现这个属性可能的值有red,orange,yellow,green

看到一个隐藏bl锁的github项目

<https://github.com/topjohnwu/Magisk/blob/3c04dab47274e9bbbfb3ddd1fcf71c929c8ed0c0/native/jni/magiskhide/hide_policy.cpp#L12>

看到替换表

| 12345678910111213 | `static` `const` `char` `*prop_key[] =``{` `"ro.boot.vbmeta.device_state"``,` `"ro.boot.verifiedbootstate"``,` `"ro.boot.flash.locked"``,``"ro.boot.veritymode"``,` `"ro.boot.warranty_bit"``,` `"ro.warranty_bit"``,``"ro.debuggable"``,` `"ro.secure"``,` `"ro.build.type"``,` `"ro.build.tags"``,``"ro.vendor.boot.warranty_bit"``,` `"ro.vendor.warranty_bit"``,``"vendor.boot.vbmeta.device_state"``, nullptr };` `static` `const` `char` `*prop_val[] =``{` `"locked"``,` `"green"``,` `"1"``,``"enforcing"``,` `"0"``,` `"0"``,``"0"``,` `"1"``,` `"user"``,` `"release-keys"``,``"0"``,` `"0"``,``"locked"``, nullptr };` |
|-|-|

可以确定green是bl未解锁,还有一个 `ro.boot.vbmeta.device_state` 要改成locked状态,实机看这个属性解锁bl状态下是unlocked,除了前三个之外其他属性解bl之后没变

还有 googleplay service 的验证

<https://developer.android.com/training/safetynet/attestation>

<https://developer.android.com/google/play/integrity/overview>

对应的解决方案是

<https://github.com/kdrag0n/safetynet-fix>

这个问题不大,国内又不用googleplay service

## 总结需要修改的信息

按照上述总结一下,隐藏bl锁需要修改以下属性

| Property | Value |
|-|-|
| ro.boot.flash.locked | 1 |
| ro.boot.verifiedbootstate | green |
| ro.boot.vbmeta.device_state | locked |

## 寻找修改Property的方法

Java层最终会调用`native_get`方法获取Property的值

顺着`native_get` 找到函数`__system_property_find` 这个是用户层标准的获取property值的函数,来自libc.so,往下翻就是android property系统的实现了,可以看这篇文章

<https://bbs.kanxue.com/thread-274100.htm>

进用户层初始化property service的地方

`/system/core/init/property_service.cpp`

找到函数 `PropertyInit` 从名字猜测这是init进程初始化系统基本property值的地方,`ProcessBootconfig`和`ProcessKernelCmdline`最后是通过读取`/proc/bootconfig`和`/proc/cmdline`调用`_system_property_add`来设置`ro.boot.verifiedbootstate`和`ro.boot.vbmeta.device_state`的值

cat一下这两个设备文件,确实有相关信息

| 12345678910111213141516171819202122232425262728 | `adb shell su` `-``c cat` `/``proc``/``bootconfig``androidboot.hardware` `=` `"qcom"``androidboot.memcg` `=` `"1"``androidboot.usbcontroller` `=` `"a600000.dwc3"``androidboot.bootdevice` `=` `"1d84000.ufshc"``androidboot.boot_devices` `=` `"soc/1d84000.ufshc"``androidboot.prjname` `=` `"22803"``androidboot.startupmode` `=` `"pwrkey"``androidboot.mode` `=` `"normal"``androidboot.product.hardware.sku` `=` `"0"``androidboot.hw_region_id` `=` `"1"``androidboot.serialno` `=` `"xxxxxxx"``androidboot.baseband` `=` `"msm"``androidboot.dtbo_idx` `=` `"12"``androidboot.dtb_idx` `=` `"1"``androidboot.force_normal_boot` `=` `"0"``androidboot.fstab_suffix` `=` `"default"``androidboot.verifiedbootstate` `=` `"orange"``androidboot.keymaster` `=` `"1"``androidboot.vbmeta.device` `=` `"PARTUUID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"``androidboot.vbmeta.avb_version` `=` `"1.0"``androidboot.vbmeta.device_state` `=` `"unlocked"``androidboot.vbmeta.hash_alg` `=` `"sha256"``androidboot.vbmeta.size` `=` `"23232"``androidboot.vbmeta.digest` `=` `"xxxxx"``androidboot.vbmeta.invalidate_on_error` `=` `"yes"``androidboot.veritymode` `=` `"enforcing"``androidboot.slot_suffix` `=` `"_a"` |
|-|-|

我想到了三个思路

1. 在内核层修改/proc/bootconfig和/proc/cmdline的内容
2. 对_system_property_add下硬件断点,回调里修改value的参数
3. 修改/dev/**properties**/u:object_r:bootloader_prop:s0里的信息

## 第一个思路

kernel版本 5.10.168 路径`/common/fs/proc/bootconfig.c` 中的`proc_boot_config_init` 函数初始化了`/proc/bootconfig`的输出,顺着全局变量 `xbc_data` 找到系统获取bootconfig的地方`/common/init/main.c -> setup_bootconfig` , 可以看到bootconfig是从initrd里拿的

 ![image](https://bbs.kanxue.com/upload/attach/202308/844784_ACGYEBG974DBN95.png)

将返回的data copy进全局变量,然后由驱动打印出来看到数据

| 12 | `www1@www1s``-``Mac``-``mini ~` `%` `adb shell su` `-``c dmesg \| grep` `"\[+"``[` `0.278576``] [``+``] androidboot.hardware``=``qcom\x0aandroidboot.memcg``=``1``\x0aandroidboot.usbcontroller``=``a600000.dwc3\x0a\x0aandroidboot.bootdevice``=``1d84000``.ufshc\x0aandroidboot.boot_devices``=``soc``/``1d84000``.ufshc\x0aandroidboot.prjname``=``22803``\x0aandroidboot.startupmode``=``hard_reset\x0aandroidboot.mode``=``normal\x0aandroidboot.product.hardware.sku``=``0``\x0aandroidboot.hw_region_id``=``1``\x0aandroidboot.serialno``=``xxxxxxxx\x0aandroidboot.baseband``=``msm\x0aandroidboot.dtbo_idx``=``12``\x0aandroidboot.dtb_idx``=``1``\x0aandroidboot.force_normal_boot``=``0``\x0aandroidboot.fstab_suffix``=``default\x0a\x0aandroidboot.verifiedbootstate``=``orange\x0aandroidboot.keymaster``=``1``\x0aandroidboot.vbmeta.device``=``PARTUUID``=``xxxxxxxx``-``xxxx``-``xxxx``-``xxxx``-``xxxxxxxxxxxx\x0aandroidboot.vbmeta.avb_version``=``1.0``\x0aandroidboot.vbmeta.device_state``=``unlocked\x0aandroidboot.vbmeta.hash_alg``=``sha256\x0aandroidboot.vbmeta.size``=``23232``\x0aandroidboot.vbmeta.digest``=``xxxxxxxxxxxxx\x0aandroidboot.vbmeta.invalidate_on_error``=``yes\x0aandroidboot.veritymode``=``enforcing\x0aandroidboot.slot_suffix``=``_a\x0a\x0d` |
|-|-|

尝试文本替换

| 12345678910111213141516171819 | `void` `regen_bootcfg(``char``* buffer)``{``char` `* pos;``pos =` `strstr``(buffer,` `"verifiedbootstate=orange"``);``if``(pos)``{``memcpy``(pos,``"verifiedbootstate=green\n"``,24);``}``pos =` `strstr``(buffer,` `"vbmeta.device_state=unlocked"``);``if``(pos)``{``memcpy``(pos,``"vbmeta.device_state=locked\n\n"``,28);``}``pos =` `strstr``(buffer,` `"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"``);``if``(pos)``{``memcpy``(pos,``"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx1"``,36);``}``}` |
|-|-|

实验发现替换 uuid 和 vbmeta.device_state 系统正常启动,一旦修改 verifiedbootstate 系统就无法启动了,第一个思路就结束在这里了

## 第二个思路

先说结果: **成功了!!!!!!**

安卓的linker使用的是mmap映射的elf文件,hook do_mmap的返回处,判断pgoff和filepath就能拦截到init进程加载libc.so,在这个时机里对_system_property_add函数下execute hook,

| 1234567891011121314 | `void` `rwhandler_hidebl_mmap_callback(unsigned` `long` `addr,``struct` `file *file)``{``char` `fullpath[1024];``char` `*path = d_path(&file->f_path, fullpath, 1024);``if``(``path &&``!``strcmp``(path,``"/system/lib64/bootstrap/libc.so"``) &&` `current->pid == 1)``{``rwhandler_start_debug();``rwhandler_set_hbp(1,addr+0x90430,4,HW_BREAKPOINT_X);``printk(``"task = %s file = %s addr = %llX\r\n"``,current->comm,path,addr);``}``}` |
|-|-|

hook回调里对参数进行简单处理

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354 | `static` `const` `char` `*hide_props[]={``"ro.boot.verifiedbootstate"``,``"ro.boot.vbmeta.device_state"``,NULL};``static` `char` `*hide_value[]={``"green"``,``"locked"``,NULL};` `static` `bool` `hidebl_hbpcallback(``struct` `perf_event *bp,``struct` `perf_sample_data *data,``struct` `pt_regs *regs)``{``if``(current->pid == 1)``{``char` `key[100];``unsigned` `long` `keyaddr = regs->regs[0];``unsigned` `long` `varaddr = regs->regs[2];``memset``(key, 0, 100);``printk(``"[+] init hit pc = %llX x0 = %llX x1 = %llX\r\n"``,``regs->pc,regs->regs[0],regs->regs[1]);` `keyaddr &= 0xFFFFFFFFFFFFFF;``varaddr &= 0xFFFFFFFFFFFFFF;``if``(rwhandler_read_memory(``1,` `(unsigned` `long``)keyaddr,` `key, 99)>0)``{``char` `value[100];``memset``(value, 0, 100);``printk(``"[+] value = %llX\r\n"``,*(uint64_t*)key);``printk(``"[+] init key = %s\r\n"``,key);` `if``(rwhandler_read_memory(``1,` `(unsigned` `long``)varaddr,` `value, 99)>0)``{``int` `idx = 0;``printk(``"[+] init value = %s\r\n"``,value);``while``(hide_props[idx])``{``if``(!``strcmp``(key,hide_props[idx]))``{` `if``(rwhandler_do_ptrace_write(1, varaddr, hide_value[idx],` `strlen``(hide_value[idx])+1))``{``regs->regs[3]=``strlen``(hide_value[idx]);``}``break``;``}``idx++;``}``}``}``return` `true``;``}``return` `false``;``};` |
|-|-|

修改成功

 ![image](https://bbs.kanxue.com/upload/attach/202308/844784_BKVA9CRF3N9FJNX.png)

成功 Spoof Setting

 ![image](https://bbs.kanxue.com/upload/attach/202308/844784_7EZE3XXJWHBBQMU.png)

## 结尾

第三个方法暂时没试过,感兴趣的可以试试看

有空就把第二个思路用kprobe来实现hook,包装成驱动连带硬件断点记录器分别开源到github上

刚入坑安卓,如有不对的地方或者有其他方法检测bl锁请大佬们在评论区指出!!!

---

# 回复

## 回复 by hhhaiai (#2)

*2023-8-17 13:02*

占坑，赞

## 回复 by Ylarod (#4)

*2023-8-17 15:07*

密钥认证了解一下
https://github.com/vvb2060/KeyAttestation

## 回复 by cslime (#5)

*2023-8-17 15:27*

>
> [Ylarod](https://bbs.kanxue.com/user-892096.htm)
>
>  密钥认证了解一下
> https://github.com/vvb2060/KeyAttestation
>
>

这个确实难过的,TEE chip里的key很难拿出来

## 回复 by cmputer (#6)

*2023-8-17 15:39*

mark

## 回复 by StriveMario (#7)

*2023-8-17 20:49*

>
> [Ylarod](https://bbs.kanxue.com/user-892096.htm)
>
>  密钥认证了解一下
> https://github.com/vvb2060/KeyAttestation
>
>

https://github.com/PaperStrike/safetynet-fix

## 回复 by 秋狝 (#8)

*2023-8-18 09:23*

感谢分享

## 回复 by shinratensei (#9)

*2023-8-18 09:44*

tql

## 回复 by 小黄鸭爱学习 (#10)

*2023-8-18 11:45*

>
> [StriveMario](https://bbs.kanxue.com/user-773600.htm)
>
>  https://github.com/PaperStrike/safetynet-fix
>
>

这是通过改成不支持认证的方式来绕过的

## 回复 by cslime (#11)

*2023-8-18 12:01*

>
> [Ylarod](https://bbs.kanxue.com/user-892096.htm)
>
>  密钥认证了解一下
> https://github.com/vvb2060/KeyAttestation

删除

## 回复 by Ylarod (#12)

*2023-8-18 16:23*

>
> [cslime](https://bbs.kanxue.com/user-844784.htm)
>
>
>
>
>
>
>
>  Ylarod
>
>  密钥认证了解一下
> https://github.com/vvb2060/KeyAttestation 昨天在听歌的时候想到了一个 ...
>
>

绕不过的，会生成一对密钥，私钥保存在TEE里面拿不到

## 回复 by cslime (#13)

*2023-8-18 16:31*

>
> [Ylarod](https://bbs.kanxue.com/user-892096.htm)
>
>  绕不过的，会生成一对密钥，私钥保存在TEE里面拿不到

删除

## 回复 by cslime (#14)

*2023-8-18 16:52*

删除

## 回复 by StriveMario (#15)

*2023-8-18 18:23*

>
> [小黄鸭爱学习](https://bbs.kanxue.com/user-832784.htm)
>
>  这是通过改成不支持认证的方式来绕过的
>
>

雀实....

## 回复 by cslime (#16)

*2023-8-21 00:26*

>
> [Ylarod](https://bbs.kanxue.com/user-892096.htm)
>
>  绕不过的，会生成一对密钥，私钥保存在TEE里面拿不到

或许可以这样?

App层用Hook劫持密钥认证的传输层,利用重放请求来绕过设备密钥认证,密钥认证返回的请求者APP数字签名信息是来自software层,root设备可以修改software层获取到的请求者数字签名绕过防重放,这样就可以利用通过一个CVE-2022-20409提权上去的设备来做重放请求的设备

但是TEE会返回kernel的patch版本,还是会产生一些检测方向,不太理想

最理想的是受害app出现了一个代码执行漏洞,在未解BL的设备上复现受害APP的代码执行漏洞来进行请求的重放

![image](https://bbs.kanxue.com/upload/attach/202308/844784_CWFX235622K5HWK.jpg)

## 回复 by 珍惜Any (#17)

*2023-8-21 14:04*

现在都在用秘钥验证 。很少用你说的这些了 。

## 回复 by cslime (#18)

*2023-8-21 14:19*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  现在都在用秘钥验证 。很少用你说的这些了 。
>
>

重放攻击了解一下,root后的设备可以控app执行密钥认证时机的传输层,再给你另外一台未解BL的设备上重放一次
看楼上

## 回复 by 月落之汀 (#19)

*2023-8-21 14:53*

bootconfig里面的state这个试着通过在内核里面hook进行修改, 结论是有些机器是可以正常开机的, 有些会panic, 有可能是vendor的驱动搞鬼? 没细究, 不过KeyAttestation确实挺麻烦的, 不对症下药不知道有什么靠谱的办法

## 回复 by 珍惜Any (#20)

*2023-8-21 15:41*

>
> [cslime](https://bbs.kanxue.com/user-844784.htm)
>
>  重放攻击了解一下,root后的设备可以控app执行密钥认证时机的传输层,再给你另外一台未解BL的设备上重放一次
> 看楼上
>
>

太复杂了 哈哈哈哈  ，我现在就是不知道怎么检测shamiko

## 回复 by TrumpWY (#21)

*2023-8-22 09:31*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  太复杂了 哈哈哈哈 ，我现在就是不知道怎么检测shamiko
>
>

哈哈哈哈哈哈哈哈哈     偷偷截屏ocr分析，手机launcher有shamiko就是有

## 回复 by 珍惜Any (#22)

*2023-8-22 09:55*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  TrumpWY](https://bbs.kanxue.com/user-957821.htm)
>
>  哈哈哈哈哈哈哈哈哈 偷偷截屏ocr分析，手机launcher有shamiko就是有
>
>

这是高手

## 回复 by Ylarod (#23)

*2023-8-22 10:39*

bl解锁 + 没找到ksu + 没找到root = shamiko，启动！

## 回复 by 江渚 (#24)

*2023-9-14 13:06*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  TrumpWY](https://bbs.kanxue.com/user-957821.htm)
>
>  哈哈哈哈哈哈哈哈哈 偷偷截屏ocr分析，手机launcher有shamiko就是有
>
>

有没有一种可能 shamiko没有launcher

## 回复 by 龙之叶 (#25)

*2023-9-14 14:59*

感谢楼主的分享

## 回复 by mb_ggnlrzcs (#26)

*2023-9-22 23:46*

楼主的代码能发出来学习一下么？

## 回复 by 浅笑不语 (#27)

*2023-9-24 20:09*

感谢分享

## 回复 by 珍惜Any (#28)

*2023-10-28 20:58*

https://github.com/chiteroman/BootloaderSpoofer 看看这个过tee检测的

## 回复 by pareto (#29)

*2023-11-23 16:08*

>
> [小黄鸭爱学习](https://bbs.kanxue.com/user-832784.htm)
>
>  这是通过改成不支持认证的方式来绕过的
>
>

 thow new UnsupportedOperationException

## 回复 by lvcoffee (#30)

*2024-4-29 20:29*

https://github.com/Displax/safetynet-fix  这个试了很久都没成功，还有能过谷歌完整性检测的方法吗？

## 回复 by hacker521 (#31)

*2024-5-7 13:43*

这个也过不了 Google的safety Net 检测

## 回复 by 轻装前行 (#32)

*2024-5-7 20:50*

研究一下海外市场泄露的xiaomikey解锁bl啊，一个100美刀呢

## 回复 by wx_林林林林林 (#33)

*2025-4-16 15:23*

这个是内核态的下隐藏的frida hook么？

## 回复 by feng504x (#34)

*2025-9-9 14:38*

楼主啥时候把硬件断点hook分享一下，想学！！

## 回复 by mb_hrwhbuad (#35)

*2025-9-10 00:36*

>
> [cslime](https://bbs.kanxue.com/user-844784.htm)
>
>  重放攻击了解一下,root后的设备可以控app执行密钥认证时机的传输层,再给你另外一台未解BL的设备上重放一次
> 看楼上
>
>

1.流程通常包含Nonce（随机数） 机制来防止重放攻击。当Victim APP请求证明时，它会生成一个Nonce并发送到Keymaster/TEE。TEE会将这个Nonce包含在证书链中并进行签名。服务器验证时，会检查Nonce是否匹配。如果你只是简单地重放之前捕获的证书链，其中的Nonce与当前请求的Nonce不一致，服务器会立即拒绝验证。
2. 你提到“root设备可以修改software层获取到的请求者数字签名”，这理论上可以绕过本地的Nonce检查，但服务器端的验证是独立的，修改本地数据无法影响服务器。
3.即使你通过Hook修改了某些软件层的数据，证书链的数字签名是基于原始设备状态生成的，任何修改都会导致签名失效。服务器验证签名时，会检测到篡改

## 回复 by mb_zuzhlnnf (#36)

*2025-9-23 04:00*

第三个思路我试过修改那个之后在查询属性就什么都没有了可能是损坏了吧

## 回复 by mb_itwvwlom (#37)

*2026-3-8 21:04*

为什么我在do_mmap的返回处加了hook，但是这个hook里面却不能执行如d_path和printk等函数？如果用这些函数，就会卡在log界面，然后重启
