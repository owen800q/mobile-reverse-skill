---
title: '[原创]redroid镜像编译及预埋 adb_key认证'
url: https://bbs.kanxue.com/thread-287127.htm
tid: 287127
author: CCTV果冻爽
date: '2025-06-06'
tags: [Android安全, 原创, 系统相关, 其他]
crawled_at: '2026-07-31T15:50:33+08:00'
replies: 111
---

这里使用香橙派5 max适配的 redroid，拉取源码并编译 ,并且修改 adb_key的认证方式，使用预埋证书完成认证。

源码版本是 Android12，并且使用user模式编译。

香橙派5max的板子是这样的（实际测试不能这样裸着，必须加上散热和风扇，否则同时跑多个实例cpu热到死机）：

![image](https://bbs.kanxue.com/upload/attach/202506/770147_WEZ5Y23E2WUFW3Z.webp)

香橙派安装 Ubuntu参考 ： [香橙派刷入Ubuntu系统](https://mp.weixin.qq.com/s/G4nspVMFR14vYRipFD1_-w)

1、拉取源码

```
mkdir ~/redroid && cd ~/redroid

# 拉取源码
apt install repo git-lfs -y

echo "y" | repo init -u https://github.com/redroid-rockchip/platform_manifests.git -b redroid-12.0.0 --depth=1
cp /root/redroid/.repo/repo/repo /usr/bin/repo
repo sync -j4
repo forall -g lfs -c git lfs pull
```

2、修改源码

1）编译增加user模式

修改device文件 device/redroid/AndroidProducts.mk ，新增 redroid_arm64-user

```
COMMON_LUNCH_CHOICES := \
    redroid_x86_64-userdebug \
    redroid_x86_64_only-userdebug \
    redroid_arm64-user \
    redroid_arm64-userdebug \
    redroid_arm64_only-user \
    redroid_arm64_only-userdebug \
```

2）新增adb_keys文件和shell文件：

![image](https://bbs.kanxue.com/upload/attach/202506/770147_42XS4BENPAME4SW.webp)

adb_keys主要用于存放adb认证用的公钥，preinstall用于在系统第一次启动时，拷贝相关文件。

preinstall.sh文件内容如下，目的在系统启动时将 adb_keys文件拷贝到 data/system目录下：

```
#!/system/bin/sh

CUSTOMIZED_APK=/system/usr/app
DATA_APK=/data/app

echo "CUSTOMIZED_APK=${CUSTOMIZED_APK}"
#获取是否已经预安装过标记位
PREINSTALL_RESULT=`getprop persist.sys.preinstall.value`
echo "PREINSTALL_RESULT=${PREINSTALL_RESULT}"
apk_files=""
#判断标记位是否为空，为空则没有预装过。然后将所有apk均copy到data/app下面。

if [ -z "${PREINSTALL_RESULT}" ]; then

cd ${CUSTOMIZED_APK}

apk_files=$(ls *.apk )

echo "apks files = ${apk_files}"

for apkfile in $apk_files

do

echo " apkfiles = ${apkfile} "

cp -vf ${CUSTOMIZED_APK}/${apkfile} ${DATA_APK}/${apkfile}

echo "start copy "

chmod 777 ${DATA_APK}/${apkfile}

done

#设置标记位
setprop persist.sys.preinstall.value 1

# 拷贝 设备改机文件
cp /system/etc/device.json /data/system/device.json
chmod 666 /data/system/device.json
# 拷贝adb公钥
cp /system/etc/adb_keys /data/system/adb_keys
chown -R shell:shell /data/system/adb_keys
chmod 666 /data/system/adb_keys

cd ../..

fi
```

3） 打包时拷贝相关文件

修改 build/target/product/base_product.mk，增加内容：

```
# 拷贝APP
PRODUCT_COPY_FILES += $(call find-copy-subdir-files,*,/data1/rom/android/redroid12/apps/apps,/system/usr/app)
# 拷贝shell
PRODUCT_COPY_FILES += $(call find-copy-subdir-files,*,/data1/rom/android/redroid12/apps/shell,/system/bin)
# 拷贝改机文件及adb公钥
PRODUCT_COPY_FILES += $(call find-copy-subdir-files,*,/data1/rom/android/redroid12/apps/devices,/system/etc)
```

4）系统启动时运行preinstall.sh

修改 system/core/rootdir/init.rc ，在 on_boot 最后新增：

```
on boot
    start preinstall
```

修改 system/sepolicy/private/file_contexts 以及 system/sepolicy/prebuilts/api/31.0/private/file_contexts，新增：

```
/system/bin/preinstall.sh  u:object_r:preinstall_exec:s0
```

新增文件 system/sepolicy/private/preinstall.te 以及 system/sepolicy/prebuilts/api/31.0/private/preinstall.te ，内容如下：

```
type preinstall, domain, coredomain;
type preinstall_exec, exec_type, file_type, system_file_type;

# init_daemon_domain(preinstall)
#全部默认允许
permissive preinstall;
```

修改 system/sepolicy/private/init.te 以及 system/sepolicy/prebuilts/api/31.0/private/init.te，新增：

```
domain_trans(init, preinstall_exec, preinstall)
allow init preinstall_exec:file {read open getattr execute};
```

编译时如果还有其他selinux问题，自行看提示解决。因为我也忘了还修改了哪些。

5) 修改adb认证

修改 frameworks/native/libs/adbd_auth/adbd_auth.cpp，路径中新增 /data/system/adb_keys

```
static constexpr const char* key_paths[] = {"/adb_keys", "/data/misc/adb/adb_keys", "/data/system/adb_keys"};
void IteratePublicKeys(bool (*callback)(void*, const char*, size_t), void* opaque) {
    for (const auto& path : key_paths) {
        if (access(path, R_OK) == 0) {
            LOG(INFO) << "adbd_auth: loading keys from " << path;
            std::string content;
            if (!android::base::ReadFileToString(path, &content)) {
                PLOG(ERROR) << "adbd_auth: couldn't read " << path;
                continue;
            }
            for (const auto& line : android::base::Split(content, "\n")) {
                if (!callback(opaque, line.data(), line.size())) {
                    return;
                }
            }
        }
    }
}
```

修改 frameworks/base/services/core/java/com/android/server/adb/AdbDebuggingManager.java

```
//第一处，指向我们自己预埋的adb_keys
private static final String SYSTEM_KEY_FILE = "/data/system/adb_keys";

//第二处，系统adb_keys也增加过期时间
public void setLastConnectionTime(String key, long connectionTime, boolean force) {
    // Do not set the connection time to a value that is earlier than what was previously
    // stored as the last connection time unless force is set.
    if (mKeyMap.containsKey(key) && mKeyMap.get(key) >= connectionTime && !force) {
        return;
    }
    // System keys are always allowed so there's no need to keep track of their connection
    // time.
    // if (mSystemKeys.contains(key)) {
    //     return;
    // }
    // if this is the first time the key is being added then write it to the key file as
    // well.
    if (!mKeyMap.containsKey(key)) {
        writeKey(key);
    }
    mKeyMap.put(key, connectionTime);
}

//第三处，如果是预埋的key，直接允许并返回
case MESSAGE_ADB_CONFIRM: {
    String key = (String) msg.obj;

    String fingerprints = getFingerprints(key);
    Slog.d(TAG, "confirm: " + key);
    Slog.d(TAG, "fingerprints: " + fingerprints);
    if(mAdbKeyStore.isKeyAuthorized(key)) {
        Slog.d(TAG, "confirm in system key");
        mFingerprints = fingerprints;
        allowDebugging(true, key);
        return;
    }
```

6）开机时启动adb服务

修改 frameworks/base/services/core/java/com/android/server/adb/AdbService.java

```
/**
 * Callend in response to {@code SystemService.PHASE_BOOT_COMPLETED} from {@code SystemServer}.
 */
public void bootCompleted() {
    if (DEBUG) Slog.d(TAG, "boot completed");
    if (mDebuggingManager != null) {
        mDebuggingManager.setAdbEnabled(true, AdbTransportType.USB);  //mIsAdbUsbEnabled
        mDebuggingManager.setAdbEnabled(true, AdbTransportType.WIFI);  //mIsAdbWifiEnabled
    }
}
```

修改 system/core/rootdir/init.usb.rc

```
on boot && property:persist.sys.usb.config=*
    # setprop sys.usb.config ${persist.sys.usb.config}
    start adbd
```

7）修改adb连接过期时间

修改 frameworks/base/core/java/android/provider/Settings.java

```
/**
 * The default time in ms within which a subsequent connection from an always allowed system
 * is allowed to reconnect without user interaction.
 *
 * @hide
 */
public static final long DEFAULT_ADB_ALLOWED_CONNECTION_TIME = 604800000 * 365;
```

8）保持adb root 权限

修改 packages/modules/adb/daemon/main.cpp ， should_drop_privileges函数返回false

```
static bool should_drop_privileges() {
    // The properties that affect `adb root` and `adb unroot` are ro.secure and
    // ro.debuggable. In this context the names don't make the expected behavior
    // particularly obvious.
    //
    // ro.debuggable:
    //   Allowed to become root, but not necessarily the default. Set to 1 on
    //   eng and userdebug builds.
    //
    // ro.secure:
    //   Drop privileges by default. Set to 1 on userdebug and user builds.
    bool ro_secure = android::base::GetBoolProperty("ro.secure", true);
    bool ro_debuggable = __android_log_is_debuggable();

    // Drop privileges if ro.secure is set...
    bool drop = ro_secure;

    // ... except "adb root" lets you keep privileges in a debuggable build.
    std::string prop = android::base::GetProperty("service.adb.root", "");
    bool adb_root = (prop == "1");
    bool adb_unroot = (prop == "0");
    if (ro_debuggable && adb_root) {
        drop = false;
    }
    // ... and "adb unroot" lets you explicitly drop privileges.
    if (adb_unroot) {
        drop = true;
    }

    return false;
}
```

9）其它可能需要修改

修改 system/sepolicy/public/domain.te 及 system/sepolicy/prebuilts/api/31.0/public/domain.te，注释内容：

```
# neverallowxperm * *:{ dir notdevfile_class_set socket_class_set blk_file } ioctl { 0 };
```

修改 hardware/rockchip/librkvpu/omx_get_gralloc_private/Android.bp， 在 cc_library_shared的 include_dirs 新增 "hardware/rockchip/libgralloc/utgard

```
include_dirs: [
    "hardware/libhardware/include/",
    "system/core/libcutils/include",
    "hardware/rockchip/libgralloc/utgard",
    "hardware/libhardware/modules/gralloc",
    "system/core/libsystem/include",
    "system/memory/libion/original-kernel-headers",
],
```

修改system/sepolicy/Android.mk，注释下面代码，允许user模式下使用permissive

```
$(hide) if [ "$(TARGET_BUILD_VARIANT)" = "user" -a -s $@.permissivedomains ]; then \
echo "==========" 1>&2; \
echo "warning: permissive domains not allowed in user builds" 1>&2; \
echo "List of invalid domains:" 1>&2; \
cat $@.permissivedomains 1>&2; \
fi
```

3、编译

```
# 编译
cd ~/redroid
source build/envsetup.sh
lunch redroid_arm64-user
export TARGET_BOARD_PLATFORM_GPU=mali-G52
export TARGET_RK_GRALLOC_VERSION=4
m
```

4、导入docker

```
# 编译产物目录
cd ~/redroid/out/target/product/redroid_arm64

# 挂载并导入到 docker
mount system.img system -o ro
mount vendor.img vendor -o ro
tar --xattrs -c vendor -C system --exclude="./vendor" . | DOCKER_DEFAULT_PLATFORM=linux/arm64 docker import -c 'ENTRYPOINT ["/init", "androidboot.hardware=redroid"]' - redroid12_user
umount system vendor

# 或者打包成tar文件
tar --xattrs -cf redroid12_user.tar vendor -C system --exclude="./vendor" . && \
# 并从tar文件导入到docker
DOCKER_DEFAULT_PLATFORM=linux/arm64 docker import -c 'ENTRYPOINT ["/init", "androidboot.hardware=redroid"]' redroid12_user.tar redroid12_user
```

导入成功后，可以看到名为 redroid12_user的镜像

![image](https://bbs.kanxue.com/upload/attach/202506/770147_V9XU7T2X7UGT2VD.webp)

5、启动镜像

```
docker run -d --restart=always --privileged \
    -p 5001:5555 \
    -v ~/redroid-data1:/data \
    -v /dev/net/tun:/dev/tun \
    -v /dev/mali0:/dev/mali0 \
   --name redroid1 \
   redroid12_user androidboot.redroid_height=1280 androidboot.redroid_width=720 androidboot.redroid_magisk=1  androidboot.redroid_virt_wifi=1 androidboot.redroid_gpu_mode=mali
```

6、查看运行中的镜像

![image](https://bbs.kanxue.com/upload/attach/202506/770147_VK9QRNMWM3KEYJU.webp)

同时运行6个实例效果图

![image](https://bbs.kanxue.com/upload/attach/202506/770147_RFKG6WKJ9ACQFXW.webp)

最后，附上一张真机长时间运行的开裂图：

![image](https://bbs.kanxue.com/upload/attach/202506/770147_RGGJ2RBDX4UK2U6.webp)

**总结：**还是云手机香

---

# 回复

## 回复 by ONewTach (#2)

*2025-6-6 16:56*

666

## 回复 by kkte (#3)

*2025-6-6 19:42*

zc

## 回复 by mb_ldbucrik (#4)

*2025-6-6 20:41*

感谢分享

## 回复 by wangzehua (#5)

*2025-6-6 20:51*

最后一张图真实了，我这边好几台也是这样，尤其是xiaomi的

## 回复 by mb_qimctavn (#6)

*2025-6-6 20:53*

感谢分享

## 回复 by huluxia (#7)

*2025-6-7 06:52*

牛逼

## 回复 by fujing (#8)

*2025-6-7 06:54*

感谢分享

## 回复 by niceday (#9)

*2025-6-7 08:25*

感谢分享

## 回复 by 智取琪 (#10)

*2025-6-7 08:58*

感谢(*^_^*)

## 回复 by mb_kyexnjsx (#11)

*2025-6-7 11:25*

感谢分享

## 回复 by mb_mzwrvupz (#12)

*2025-6-7 17:43*

感谢分享

## 回复 by method (#13)

*2025-6-7 19:13*

1

## 回复 by 青丝梦 (#14)

*2025-6-8 20:30*

kan

## 回复 by uncle flower (#15)

*2025-6-8 20:45*

感谢分享

## 回复 by zgm1210006 (#16)

*2025-6-8 20:58*

感谢分享，学习一下

## 回复 by 蜡笔晓辉 (#17)

*2025-6-8 22:51*

厉害了

## 回复 by Imxz (#18)

*2025-6-9 08:58*

66666666666

## 回复 by huangjw (#19)

*2025-6-9 09:28*

niu b plus

## 回复 by GEKEZYX (#20)

*2025-6-9 09:35*

6666

## 回复 by guijingwen (#21)

*2025-6-9 10:06*

666

## 回复 by 菜鸟也想飞 (#22)

*2025-6-9 10:44*

6

## 回复 by creek_ (#23)

*2025-6-9 12:00*

6666

## 回复 by 浮事青云 (#24)

*2025-6-9 13:19*

666

## 回复 by mb_cbgtaveo (#25)

*2025-6-9 14:12*

nb

## 回复 by mb_fidppcok (#26)

*2025-6-9 14:23*

感谢你的积极参与，期待更多精彩内容！

## 回复 by xiaotuo (#27)

*2025-6-9 14:27*

66

## 回复 by xiaotuo (#28)

*2025-6-9 14:27*

66

## 回复 by 4Chan (#29)

*2025-6-9 14:31*

666

## 回复 by JackHunter (#31)

*2025-6-9 17:08*

666666

## 回复 by forpubtest (#32)

*2025-6-10 10:40*

感谢分享

## 回复 by fishod (#33)

*2025-6-11 11:43*

鼓包了我的哥

## 回复 by lookaside (#34)

*2025-6-11 14:24*

666

## 回复 by KenLi (#35)

*2025-6-11 17:41*

看看

## 回复 by mb_cirblqqg (#36)

*2025-6-11 21:33*

有大佬可以帮忙找回被骗的钱吗，现在实在坚持不住了

## 回复 by mb_cirblqqg (#37)

*2025-6-11 21:40*

有大佬可以找回被骗的钱吗，现在实在坚持不住了

## 回复 by kingking888 (#38)

*2025-6-11 21:47*

666

## 回复 by Elice (#39)

*2025-6-13 09:54*

6666

## 回复 by hhhaiai (#40)

*2025-6-13 14:54*

6666

## 回复 by mb_yaeaedrh (#41)

*2025-6-13 16:57*

感谢分享，学习一下

## 回复 by Snark (#42)

*2025-6-13 18:43*

666

## 回复 by Thehepta (#43)

*2025-6-17 17:40*

kk

## 回复 by Thehepta (#44)

*2025-6-17 17:46*

我有问题，为什么不使用原本的逻辑，将adb证书内置进去，直接完成认证，而是要重改一边，目的是什么，为什么要这么做

## 回复 by hy6ran (#45)

*2025-6-18 23:08*

厉害了

## 回复 by git_56701jackt88 (#46)

*2025-6-19 00:20*

6666

## 回复 by uni7corn (#47)

*2025-6-23 10:56*

11111

## 回复 by 咸鱼…… (#48)

*2025-6-23 14:08*

强！！！！

## 回复 by KingSelyF (#49)

*2025-6-23 15:03*

太强了

## 回复 by adnin (#50)

*2025-6-23 15:08*

看看

## 回复 by bedaway (#51)

*2025-6-23 15:11*

666

## 回复 by tjytjy (#52)

*2025-6-24 18:26*

666

## 回复 by wx_Long_583904 (#53)

*2025-6-25 09:35*

nb

## 回复 by mb_ocqiotcu (#54)

*2025-6-26 18:38*

666

## 回复 by dfJerry (#55)

*2025-6-26 18:40*

6666

## 回复 by YooHaa (#56)

*2025-6-27 18:23*

6

## 回复 by wx_不愿入赘老板郎 (#57)

*2025-6-27 19:19*

1

## 回复 by git_87237minhdanhsc (#58)

*2025-6-29 08:26*

666

## 回复 by maxcl (#59)

*2025-6-29 22:21*

66666

## 回复 by MaYil (#60)

*2025-6-29 22:25*

感谢分享

## 回复 by breakM (#61)

*2025-6-30 00:08*

感谢分享

## 回复 by mb_pmgifpme (#62)

*2025-6-30 14:05*

6

## 回复 by iacky (#63)

*2025-7-4 10:20*

666～

## 回复 by 海带 (#64)

*2025-7-10 18:54*

66666

## 回复 by wx_Haluk (#65)

*2025-7-11 11:03*

666

## 回复 by 3cly (#66)

*2025-7-15 14:31*

12

## 回复 by baichisi (#67)

*2025-7-15 17:33*

66666

## 回复 by mb_fbxgiqnb (#68)

*2025-7-30 17:11*

怎么联系

## 回复 by 呼吸24K纯氧 (#69)

*2025-7-30 19:26*

感谢分享

## 回复 by jaefern (#70)

*2025-8-2 18:35*

666

## 回复 by moher (#71)

*2025-8-11 10:06*

感谢分享

## 回复 by l1nn (#72)

*2025-8-11 10:54*

66

## 回复 by mb_bsawqapm (#73)

*2025-8-14 18:31*

66

## 回复 by 山竹笠 (#74)

*2025-8-15 10:44*

厉害

## 回复 by Heiyiren123 (#75)

*2025-8-15 11:57*

666

## 回复 by 万里星河 (#76)

*2025-8-16 02:22*

666

## 回复 by AndroidDev (#77)

*2025-8-17 10:09*

感谢分享

## 回复 by 野狼 (#78)

*2025-8-17 16:36*

666666

## 回复 by omuitk (#79)

*2025-8-18 09:23*

666

## 回复 by mb_egsjciof (#80)

*2025-8-18 10:52*

666

## 回复 by 千谦 (#81)

*2025-8-19 23:50*

666

## 回复 by 废人one (#82)

*2025-8-30 17:25*

111

## 回复 by xxjj678 (#83)

*2025-9-12 22:52*

666

## 回复 by m0y1 (#84)

*2025-9-21 10:19*

666

## 回复 by mb_pnyyaazf (#85)

*2025-9-21 16:51*

感谢分享

## 回复 by XCicada (#86)

*2025-9-21 17:25*

学习

## 回复 by xysds (#87)

*2025-10-26 14:56*

nb

## 回复 by mb_hrqmnpac (#88)

*2025-10-30 02:36*

666

## 回复 by 9527vv7 (#89)

*2025-10-31 11:04*

66

## 回复 by 黄药师pp (#90)

*2025-11-11 18:10*

nb

## 回复 by 大魔头 (#91)

*2025-11-11 18:20*

![image](https://bbs.kanxue.com/view/img/face/027.gif)

## 回复 by axpol (#92)

*2025-11-17 16:49*

666

## 回复 by MeeSii (#93)

*2025-11-19 12:40*

666

## 回复 by ReverseApp (#94)

*2025-11-28 11:45*

1

## 回复 by pxyss (#95)

*2025-12-1 12:08*

![image](https://bbs.kanxue.com/view/img/face/005.gif)666

## 回复 by mb_ropjefke (#96)

*2025-12-9 11:03*

nb学习

## 回复 by PoisonBCat (#97)

*2025-12-16 16:52*

学习学习，感谢

## 回复 by mb_eskdmxqf (#98)

*2025-12-25 23:00*

666

## 回复 by Hacker_0 (#99)

*2026-1-4 11:49*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by javac_kylin (#100)

*2026-2-10 15:33*

6666

## 回复 by mb_zhnwjvhx (#101)

*2026-2-11 03:09*

想解决magisk面具安装完模块 adb连不了 验证不了 不知咋解决

## 回复 by Zepp7289 (#102)

*2026-2-12 17:18*

感谢分享

## 回复 by 智取棋 (#103)

*2026-3-4 09:53*

nb

## 回复 by mb_kaprdfsx (#104)

*2026-4-9 15:00*

111

## 回复 by wx_k74001 (#105)

*2026-4-10 10:07*

555

## 回复 by AyonA333 (#106)

*2026-4-17 09:12*

666

## 回复 by tmi (#107)

*2026-4-17 10:33*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by nuomida (#108)

*2026-4-20 15:48*

树莓派可以吗

## 回复 by 靴子 (#109)

*2026-4-24 09:24*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by uuhc (#110)

*2026-5-9 23:22*

nb

## 回复 by mb_irrqcmsq (#111)

*2026-5-15 09:44*

nb

## 回复 by 口艾口牙女马口牙 (#112)

*2026-6-4 16:32*

6666

## 回复 by CheRevir (#113)

*2026-6-4 17:15*

666
