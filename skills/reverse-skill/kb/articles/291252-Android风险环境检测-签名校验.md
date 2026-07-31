---
title: '[原创]Android风险环境检测 —— 签名校验'
url: https://bbs.kanxue.com/thread-291252.htm
tid: 291252
author: mb_wckjnnha
date: '2026-05-18'
tags: [Android安全, 原创, HOOK注入, 其他]
crawled_at: '2026-07-31T15:06:08+08:00'
replies: 150
---

## 前言

最近在阅读《Android设备指纹攻防与风险环境检测》时，发现光靠阅读书中的思路和代码片段不能很好的理解，所以打算自己写一个app，实践一下

## java层签名检测

java层通常使用`PackageManager`进行签名校验

在Android9以上，签名可以通过PackageInfo -> signingInfo -> signatures获得，以下则是通过PackageInfo -> signatures

无论是哪种，获取PackageInfo都会使用`getPackageInfo`这个api

```java
package com.example.mysecurityapp;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.os.Build;
import android.os.Message;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

public class SignatureVerificationUtils {

    public static final String expected_signature_hash = "74:0F:46:6F:D4:7E:F5:2A:38:10:CE:AB:92:F0:46:45:B9:4D:94:65:DF:F2:DC:D6:99:51:B5:86:7A:F6:10:E1";

    public static String getAppSignatureHash(Context context, String packageName) {
        try {
            PackageManager pm = context.getPackageManager();
            Signature[] signatures;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                // PackageInfo用来储存package中的一些信息
                PackageInfo packageInfo = pm.getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES);
                if (packageInfo == null || packageInfo.signingInfo == null) {
                    return null;
                }
                // 是否有多个签名者
                if (packageInfo.signingInfo.hasMultipleSigners()) {
                    // 当前签名
                    signatures = packageInfo.signingInfo.getApkContentsSigners();
                } else {
                    // 历史签名
                    signatures = packageInfo.signingInfo.getSigningCertificateHistory();
                }
            } else {
                PackageInfo packageInfo = pm.getPackageInfo(packageName, PackageManager.GET_SIGNATURES);
                if (packageInfo == null || packageInfo.signatures == null) {
                    return null;
                }
                signatures = packageInfo.signatures;
            }
            if (signatures != null && signatures.length > 0) {
                return getSHA256(signatures[0].toByteArray());
            }
        } catch (PackageManager.NameNotFoundException e) {
            e.printStackTrace();
        }
        return null;
    }

    private static String getSHA256(byte[] signatureBytes) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            md.update(signatureBytes);
            byte[] digest = md.digest();
            return bytesToHex(digest);
        } catch (NoSuchAlgorithmException e) {
            e.printStackTrace();
        }
        return null;
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder hexString = new StringBuilder();
        for (int i = 0; i < bytes.length; i++) {
            String hex = Integer.toHexString(0xFF & bytes[i]);
            if (hex.length() == 1) {
                hexString.append('0');
            }
            hexString.append(hex.toUpperCase());
            if (i < bytes.length - 1) {
                hexString.append(":");
            }
        }
        return hexString.toString();
    }

    public static boolean verifySignature(Context context) {
        String signature = getAppSignatureHash(context, context.getPackageName());
        return expected_signature_hash.equals(signature);
    }
}
```

在Android9引入了密钥轮换机制，因此废弃了`GET_SIGNATURES`，转而推荐使用`GET_SIGNING_CERTIFICATES`获取证书

但是单纯java层检测并不安全：PackageManager的getPackageInfo可能会被hook、用来比对的签名值也可能被篡改

### 伪造PackageInfo

在MainActivity调用这个方法

```java
@Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        Button button = findViewById(R.id.signature_java);
        button.setOnClickListener(this);
        textView = findViewById(R.id.signature_text);
    }

    @Override
    public void onClick(View v) {
        boolean verify_res = SignatureVerificationUtils.verifySignature(this);
        if(verify_res == false)
        {
            textView.setText("签名校验失败");
        }
        else
        {
            textView.setText("签名校验成功");
        }
    }
```

并对应用重新签名

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_7MQ97JBVKSDH6AT.png)

此时签名校验失败，尝试通过hook PackageManger返回正确校验值

```js
function fakeSignatures()
{
  var signature = Java.use("android.content.pm.Signature");
  var mySignative = "308202e4308201cc020101300d06092a864886f70d01010b050030373116301406035504030c0d416e64726f69642044656275673110300e060355040a0c07416e64726f6964310b30090603550406130255533020170d3234313131363134343832385a180f32303534313130393134343832385a30373116301406035504030c0d416e64726f69642044656275673110300e060355040a0c07416e64726f6964310b300906035504061302555330820122300d06092a864886f70d01010105000382010f003082010a02820101009042f3b7fbe3164cac331f89ca5eefa713b17a3bc7385f7c740646feb823099717b5c83f4d466415e09cdc0aa1f195419b8b485c69c5da7c2a77b4252527188df70e99f842729e7e6aa6ed3b93e021035c740d53b2f8e65157b6994e4d054091b984c48a0b5161e63e7104e858e995117c884dfb8337e129b8b65af7ddbbca501261cd043c9b6105956b569f50d58c2b2fba2c81c30fbb022c30043f9ca13230d437b5d304cc6e4be6fa9e7ca85b8b4945093c5bdb13df5f1936ac25ad3c3a102b18aaaf118d8dc9e93fe8637ba37b09b232d3923eb257d451c7bb9da68a8ae189766a917f76ae0a864669656ee6f6c869553555d96e05b519e899d04a8b121d0203010001300d06092a864886f70d01010b050003820101002042005e9bdb007e94c01a6dc74bf56f16ddcd7a85b5407bdd8a20494c8949cbecff0ebf213e415fff05a8141c84273a79ce14387487ca1e449f1a18a50c38dd254dc3e8f29f987a0ba550e78572afa9bad0eabeac03609f74d6575456444fd3f5d35a94abf167b96ed3a774a12d0cebbfb7c9b6a7821e3c11ad940eed2c63647e9b7570e5aa609dbec0678d7ebba8acd4213c28dc5a01dfe6a1f438c5ee8c94ef573acd565334fe9287d74c94a934bc3959a9e7d69e7ac1074f8667a58b8f3e51e29564b164854610a983a4fdcc516b9b48726e6feee74247deb407e335ba411af80c5216d59815b689f398e13d4aa900f589960df72dd73e565d0b592480a0";
  var fakeSignature = signature.$new(mySignative);
  return Java.array('android.content.pm.Signature',[fakeSignature]);
}

function fakeSigningInfo()
{
  var SigningDetails = Java.use("android.content.pm.SigningDetails");
  var SigningInfo = Java.use("android.content.pm.SigningInfo");
  var ArraySet = Java.use("android.util.ArraySet");
  var fakeDetails = SigningDetails.$new(fakeSignatures(), 3, ArraySet.$new(), fakeSignatures());
  return SigningInfo.$new(fakeDetails);
}

function patchPackageInfo(packageInfo)
{
  if (packageInfo.signatures.value != null) {
    packageInfo.signatures.value = fakeSignatures();
  }
  if (packageInfo.signingInfo.value != null) {
    packageInfo.signingInfo.value = fakeSigningInfo();
  }
  return packageInfo;
}

function hookSignative()
{
  var PackageManager = Java.use("android.app.ApplicationPackageManager");
  var MessageDigest = Java.use("java.security.MessageDigest");

  var getPackageInfoInt = PackageManager.getPackageInfo.overload('java.lang.String', 'int');
  getPackageInfoInt.implementation = function(packageName, flags)
  {
    var packageInfo = getPackageInfoInt.call(this, packageName, flags);
    patchPackageInfo(packageInfo);
    console.log("getPackageInfo hooked: " + packageName + ", flags=" + flags + ", signingInfo=" + (packageInfo.signingInfo.value != null));
    return packageInfo;
  }

  try {
    var getPackageInfoFlags = PackageManager.getPackageInfo.overload('java.lang.String', 'android.content.pm.PackageManager$PackageInfoFlags');
    getPackageInfoFlags.implementation = function(packageName, flags)
    {
      var packageInfo = getPackageInfoFlags.call(this, packageName, flags);
      patchPackageInfo(packageInfo);
      console.log("getPackageInfo hooked: " + packageName + ", flags=" + flags + ", signingInfo=" + (packageInfo.signingInfo.value != null));
      return packageInfo;
    }
  } catch (e) {
  }

}

function main()
{
  Java.perform(function(){
    console.log("hook start");
    hookSignative();
  });
}

setImmediate(main);
```

脚本hook了getPackageInfo方法，返回了伪造的PackageInfo -> SigningInfo -> SigningDetails值

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_JAMC76Z4PWXQM4P.png)

此时签名校验失败。

如何防止这种方式hook getPackageInfo呢

### 构造IPC请求向系统服务获取应用签名

最直接的思路就是不使用getPackageInfo，可以通过反射获取Binder对象，直接和系统服务进行通信

```java
public static String IPCGetSignatureHash(Context context)
    {
        // 从对象池中获取两个 Parcel 对象
        // Parcel 是 Android 中用于在不同组件之间传递数据的容器，它可以包含基本数据类型、对象引用以及实现了 Parcelable 接口的对象
        // Parcel 的主要用途是进行进程间通信（IPC），特别是在使用 Binder 机制时
        // _data 用于存放发送给系统服务的数据
        // _reply 用于接收系统服务返回的数据结果
        Parcel _data = Parcel.obtain();
        Parcel _reply = Parcel.obtain();
        try{
            // 通过反射获取底层 IBinder 对象
            // 获取 PackageManager 对象（ApplicationPackageManager 实例）
            PackageManager packageManager = context.getPackageManager();
            // 反射获取 ApplicationPackageManager 内部隐藏的 mPM 变量
            // 获取 mPM 字段对象
            Field mPMFile = packageManager.getClass().getDeclaredField("mPM");
            mPMFile.setAccessible(true);
            // get packageManager 中的 mPM
            Object mPM = mPMFile.get(packageManager);
            // mPM 是 IPackageManager 的 Proxy，直接通过 asBinder 获取 IBinder
            IBinder mRemote = ((IInterface) mPM).asBinder();
            if(mRemote == null)
            {
                Log.e("YvY_security","获取IBinder失败");
                return null;
            }
            // 写入接口 Token，告诉系统调用的接口
            _data.writeInterfaceToken("android.content.pm.IPackageManager");
            // a1 : 包名
            _data.writeString(context.getPackageName());
            // Android 13 之前使用 writeInt，Android 13 及以上 flags 参数类型为 long
            // a2 : 获取信息标志位
            long flags = (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P)?134217728L:64L;
            if(Build.VERSION.SDK_INT >= 33)
            {
                _data.writeLong(flags);
            }
            else
            {
                _data.writeInt((int)flags);
            }
            // a3 : userId
            int userId = 0;
            if(Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN_MR1)
            {
                userId = android.os.Process.myUid() / 100000;
            }
            _data.writeInt(userId);

            int transactCode = getTransactionCode();
            // 调用 transact 触发底层 Binder 驱动通信
            boolean _status = mRemote.transact(transactCode,_data,_reply,0);
            if(!_status)
            {
                return null;
            }
            _reply.readException();
            PackageInfo packageInfo = null;
            if(_reply.readInt() != 0)
            {
                // 从数据包里还原出 PackageInfo 实例
                packageInfo = PackageInfo.CREATOR.createFromParcel(_reply);
            }
            if(packageInfo != null)
            {
                byte[] signatureBytes = null;
                // Android 9 以上
                if(Build.VERSION.SDK_INT >= Build.VERSION_CODES.P && packageInfo.signingInfo != null)
                {
                    // 如果是多重签名
                    if(packageInfo.signingInfo.hasMultipleSigners())
                    {
                        // 当前签名者的首个签名
                        signatureBytes = packageInfo.signingInfo.getApkContentsSigners()[0].toByteArray();
                    }
                    // 单一签名
                    else
                    {
                        // 历史证书
                        signatureBytes = packageInfo.signingInfo.getSigningCertificateHistory()[0].toByteArray();
                    }
                }
                else
                {
                    // Android 9 以下使用 signatures 数组获取签名
                    signatureBytes = packageInfo.signatures[0].toByteArray();
                }
                if(signatureBytes != null)
                {
                    return getSHA256(signatureBytes);
                }
            }

        }catch (Throwable e)
        {
            Log.e("YvY_security","IPC signature check error", e);
        }
        finally {
            _data.recycle();
            _reply.recycle();
        }
        return null;
    }

    // Android 13 及以上无法通过反射获取隐藏 API，只能硬编码或使用第三方库解除限制
    private static int getTransactionCode() {
        int TRANSACTION_getPackageInfo = 0;
        if(Build.VERSION.SDK_INT >= 33)
        {
            switch (Build.VERSION.SDK_INT)
            {
                case 33:
                    TRANSACTION_getPackageInfo = 3;
                    break;
                // 添加自己的安卓版本
            }
        }
        else
        {
            try {
                Class<?> pkmIPCClazz = Class.forName("android.content.pm.IPackageManager$Stub");
                Field field = pkmIPCClazz.getDeclaredField("TRANSACTION_getPackageInfo");
                field.setAccessible(true);
                TRANSACTION_getPackageInfo = field.getInt(null);
            } catch (Throwable e) {
                e.printStackTrace();
            }
        }
        return TRANSACTION_getPackageInfo;
    }

    public static boolean verifySignature_IPC(Context context) {
        String signature = IPCGetSignatureHash(context);
        return expected_signature_hash.equals(signature);
    }
```

不使用getPackageInfo，减少hook点。运行应用观察，发现此方法的签名校验失败

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_PQ7EC5E6VKG4WR9.png)

但这种方法同样有缺点

### 替换PackageInfo.CREATOR

上面这段代码中

```java
if(_reply.readInt() != 0)
{
    // 从数据包里还原出 PackageInfo 实例
    packageInfo = PackageInfo.CREATOR.createFromParcel(_reply);
}
```

解析PackageInfo.CREATOR为PackageInfo对象，所以可以通过反射替换此静态变量，伪造签名信息

hook方法如下

```
var TARGET_PACKAGE = "com.example.mysecurityapp";

function fakeSignatures() {
  var mySignative = "...";
  var Signature = Java.use("android.content.pm.Signature");
  return Java.array("android.content.pm.Signature", [
    Signature.$new(mySignative)
  ]);
}

function isFromIPCGetSignatureHash() {
  var Exception = Java.use("java.lang.Exception");
  var Log = Java.use("android.util.Log");
  var stack = Log.getStackTraceString(Exception.$new());
  return stack.indexOf("com.example.mysecurityapp.SignatureVerificationUtils.IPCGetSignatureHash") !== -1;
}

function patchPackageInfoForIpc(packageInfo) {
  if (packageInfo == null) {
    return packageInfo;
  }

  var packageName = packageInfo.packageName.value;
  if (packageName !== TARGET_PACKAGE) {
    return packageInfo;
  }

  packageInfo.signatures.value = fakeSignatures();
  if (packageInfo.signingInfo !== undefined) {
    packageInfo.signingInfo.value = null;
  }

  return packageInfo;
}

function hookSignativeIPC() {
  var PackageInfo = Java.use("android.content.pm.PackageInfo");
  var ParcelableCreator = Java.use("android.os.Parcelable$Creator");
  var originalCreator = PackageInfo.CREATOR.value;

  var className = "com.example.mysecurityapp.PackageInfoCreatorProxy" + Date.now();
  var ProxiedCreator = Java.registerClass({
    name: className,
    implements: [ParcelableCreator],
    methods: {
      createFromParcel: [{
        returnType: "java.lang.Object",
        argumentTypes: ["android.os.Parcel"],
        implementation: function(source) {
          var packageInfo = Java.cast(
            originalCreator.createFromParcel(source),
            PackageInfo
          );

          if (isFromIPCGetSignatureHash()) {
            return patchPackageInfoForIpc(packageInfo);
          }

          return packageInfo;
        }
      }],
      newArray: [{
        returnType: "[Ljava.lang.Object;",
        argumentTypes: ["int"],
        implementation: function(size) {
          return originalCreator.newArray(size);
        }
      }]
    }
  });

  PackageInfo.CREATOR.value = ProxiedCreator.$new();
}

function main() {
  Java.perform(function() {
    console.log("hook start");
    hookSignativeIPC();
  });
}

setImmediate(main);
```

`CREATOR`里包含两个方法

1.createFromParcel(Parcel source) 从二进制字节流里读取数据 拼装还原出一个完整的Java对象

2.newArray(int size) 用来创建该对象的数组

```
  var packageInfo = Java.cast(
    originalCreator.createFromParcel(source),
    PackageInfo
  );

  if (isFromIPCGetSignatureHash()) {
    return patchPackageInfoForIpc(packageInfo);
  }

  return packageInfo;
```

在我们自己创建的CREATOR中，截取到数据之后将PackageInfo替换即可成功替换

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_UCPUD9QJ24CC6HJ.png)

在Java代码中新建一个方法检测PackageInfo.CREATOR是否被替换

```java
    // 检测替换PackageInfo.CREATOR
    public static boolean checkIsPackageInfoReplace()
    {
        try{
            Field creatorField = PackageInfo.class.getField("CREATOR");
            creatorField.setAccessible(true);
            // 反射获取creator对象
            Object creator = creatorField.get(null);
            if(creator != null)
            {
                // 系统默认的CREATOR加载器为BootClassLoader 但是替换后的通常不是
                ClassLoader creatorClassloader = creator.getClass().getClassLoader();
                // 获取PackageInfo的加载器 此加载器为BootClassLoader
                ClassLoader sysClassloader = PackageInfo.class.getClassLoader();
                if(creatorClassloader == null || sysClassloader == null)
                {
                    return false;
                }
                // 比较地址 同一个类加载器加载的类 地址是唯一的
                if(sysClassloader != creatorClassloader)
                {
                    return true;
                }
            }
        }
        catch (Throwable e)
        {
            e.printStackTrace();
        }
        return false;
    }
```

现在运行完整脚本，发现此方法被检测到

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_YTUSBFPFE5HCXPZ.png)

## native层检测

先来写一个简单的native检测

native-lib.cpp

```
#include <jni.h>
#include <string>
#include <sstream>
#include <iomanip>
#include "Utils.h"
#include "android/log.h"
#define LOG_TAG "YvY_Security"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, LOG_TAG, __VA_ARGS__)

extern "C" JNIEXPORT jstring JNICALL
Java_com_example_mysecurityapp_MainActivity_stringFromJNI(
        JNIEnv* env,
        jobject /* this */) {
    std::string hello = "Hello from C++";
    return env->NewStringUTF(hello.c_str());
}

std::string expected_signature = "308202e4308201cc020101300d06092a864886f70d01010b050030373116301406035504030c0d416e64726f69642044656275673110300e060355040a0c07416e64726f6964310b30090603550406130255533020170d3234313131363134343832385a180f32303534313130393134343832385a30373116301406035504030c0d416e64726f69642044656275673110300e060355040a0c07416e64726f6964310b300906035504061302555330820122300d06092a864886f70d01010105000382010f003082010a02820101009042f3b7fbe3164cac331f89ca5eefa713b17a3bc7385f7c740646feb823099717b5c83f4d466415e09cdc0aa1f195419b8b485c69c5da7c2a77b4252527188df70e99f842729e7e6aa6ed3b93e021035c740d53b2f8e65157b6994e4d054091b984c48a0b5161e63e7104e858e995117c884dfb8337e129b8b65af7ddbbca501261cd043c9b6105956b569f50d58c2b2fba2c81c30fbb022c30043f9ca13230d437b5d304cc6e4be6fa9e7ca85b8b4945093c5bdb13df5f1936ac25ad3c3a102b18aaaf118d8dc9e93fe8637ba37b09b232d3923eb257d451c7bb9da68a8ae189766a917f76ae0a864669656ee6f6c869553555d96e05b519e899d04a8b121d0203010001300d06092a864886f70d01010b050003820101002042005e9bdb007e94c01a6dc74bf56f16ddcd7a85b5407bdd8a20494c8949cbecff0ebf213e415fff05a8141c84273a79ce14387487ca1e449f1a18a50c38dd254dc3e8f29f987a0ba550e78572afa9bad0eabeac03609f74d6575456444fd3f5d35a94abf167b96ed3a774a12d0cebbfb7c9b6a7821e3c11ad940eed2c63647e9b7570e5aa609dbec0678d7ebba8acd4213c28dc5a01dfe6a1f438c5ee8c94ef573acd565334fe9287d74c94a934bc3959a9e7d69e7ac1074f8667a58b8f3e51e29564b164854610a983a4fdcc516b9b48726e6feee74247deb407e335ba411af80c5216d59815b689f398e13d4aa900f589960df72dd73e565d0b592480a0";

extern "C"
JNIEXPORT jboolean JNICALL
Java_com_example_mysecurityapp_MainActivity_SignatureVerificationNative(JNIEnv *env, jclass clazz) {
    const std::string path = Utils::getBaseApkPath();
    if(path.empty())
    {
        LOGE("APK签名验证失败 原因: getBaseApkPath fail");
        return JNI_FALSE;
    }

    int fd = open(path.c_str(),O_RDONLY | O_CLOEXEC);
    if(fd < 0)
    {
        LOGE("APK签名验证失败 原因: open fd fail");
        return JNI_FALSE;
    }
    std::vector<unsigned char> cert_stream = Utils::read_certificate(fd);
    if(cert_stream.empty())
    {
        LOGE("APK签名验证失败 原因: read_certificate fail");
        close(fd);
        return JNI_FALSE;
    }
    std::stringstream stream;
    stream << std::hex << std::setfill('0');
    for(unsigned char byte : cert_stream)
    {
        stream << std::setw(2) << static_cast<int>(byte);
    }
    std::string APK_sign = stream.str();
    jboolean is_valid = JNI_FALSE;
    if(APK_sign == expected_signature)
    {
        is_valid = JNI_TRUE;
    }
    else
    {
        is_valid = JNI_FALSE;
    }
    close(fd);
    return is_valid;
}
```

（有些工具类函数，比如解析v2 v3签名的函数，使用ai辅助生成）

### libc函数重定向

在上面这个例子中，完全可以hook open函数，将参数一的地址替换成原始apk，这样签名校验一定会成功

hook脚本如下：

```js
const original_apk = "/data/user/0/com.example.mysecurityapp/files/app-debug.apk";
const target_so = "libmysecurityapp.so";

const original_apk_ptr = Memory.allocUtf8String(original_apk);

function isTargetFile(path)
{
  if(!path) return false;
  return (path.indexOf("base.apk") !== -1) && path != original_apk;
}

function isTargerCaller(context)
{
  const caller = DebugSymbol.fromAddress(context.lr);
  if(caller.moduleName.indexOf(target_so) !== -1)
  {
    return true;
  }
  return false;
}

function attachOpenLike(name,argsIndex)
{
  const addr = Module.findExportByName("libc.so",name);
  Interceptor.attach(addr,{
    onEnter(args)
    {
      const pathPtr = args[argsIndex];
      const path = Memory.readUtf8String(pathPtr);
      if(isTargetFile(path) && isTargerCaller(this.context))
      {
        args[argsIndex] = original_apk_ptr;
        console.log(name + "重定向成功");
      }
    }
  });
}

function hookOpen() {
  attachOpenLike("open", 0);
  attachOpenLike("open64", 0);
  attachOpenLike("__open_2", 0);
  attachOpenLike("openat", 1);
  attachOpenLike("openat64", 1);
}

function main() {
  console.log("hook start");
  hookOpen();
}

setImmediate(main);
```

编译保护将open函数自动替换为__open_2，所以这里不能只hook open函数，效果如下

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_8ZDQT7JGWNWTJN6.png)

为了防止对libc函数进行hook，可以考虑使用SVC指令进行代替

>
> 在ARM架构中，SVC指令用于从用户态切换到内核态，执行系统调用。
>
>
>

使用SVC指令比普通函数更加安全

```
#include <jni.h>
#include <string>
#include <sstream>
#include <iomanip>
#include <cerrno>
#include "Utils.h"
#include "android/log.h"
#define LOG_TAG "YvY_Security"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, LOG_TAG, __VA_ARGS__)

namespace {

// 相对目录
constexpr int SVC_AT_FDCWD = -100;
// openat的系统调用号
constexpr int SVC_OPENAT_ARM64 = 56;
constexpr int SVC_OPENAT_ARM = 322;

int svc_openat(const char *path, int flags, int mode)
{
// arm64
#if defined(__aarch64__)
    register long x0 asm("x0") = SVC_AT_FDCWD; // a1 : 目录文件描述符
    register long x1 asm("x1") = reinterpret_cast<long>(path); // a2 : 文件路径的指针
    register long x2 asm("x2") = flags; // a3 : 标志
    register long x3 asm("x3") = mode; // a4 : 权限模式
    register long x8 asm("x8") = SVC_OPENAT_ARM64; // x8寄存器存放系统调用号

    asm volatile(
            "svc #0"
            : "+r"(x0)
            : "r"(x1), "r"(x2), "r"(x3), "r"(x8)
            : "memory");
    return static_cast<int>(x0); // 将返回值转为int返回
#elif defined(__arm__)
    register long r0 asm("r0") = SVC_AT_FDCWD;
    register long r1 asm("r1") = reinterpret_cast<long>(path);
    register long r2 asm("r2") = flags;
    register long r3 asm("r3") = mode;

    asm volatile(
            "push {r7}\n"
            "mov r7, %4\n"
            "svc #0\n"
            "pop {r7}"
            : "+r"(r0)
            : "r"(r1), "r"(r2), "r"(r3), "r"(SVC_OPENAT_ARM)
            : "memory");
    return static_cast<int>(r0);
#else
    return open(path, flags, mode);
#endif
}

int open_apk_by_svc(const char *path, int flags)
{
    int fd = svc_openat(path, flags, 0);
    if (fd < 0) {
        errno = -fd;
        return -1;
    }
    return fd;
}

} // namespace

}
```

### fd替换

此时再去hook open函数难度较高，但可以使用fd替换的方式来绕过签名校验，重打包后的应用fd指向bask.apk，将指向的文件改为原始apk即可

```js
const original_apk = "/data/user/0/com.example.mysecurityapp/files/app-debug.apk";
const target_so = "libmysecurityapp.so";
const target_symbol = "_ZN5Utils16read_certificateEi";
const O_RDONLY = 0;
const O_CLOEXEC = 0x80000;

const openPtr = Module.findExportByName("libc.so","open");
const dup2Ptr = Module.findExportByName("libc.so","dup2");
const closePtr = Module.findExportByName("libc.so","close");

const openFn = new SystemFunction(openPtr,"int",["pointer","int"]);
const dup2Fn = new SystemFunction(dup2Ptr,"int",["int","int"]);
const closeFn = new NativeFunction(closePtr,"int",["int"]);

const originalApkPtr = Memory.allocUtf8String(original_apk);

function hookFd()
{
  const targetModule = Process.findModuleByName(target_so);
  if(targetModule === null) return;

  const target = targetModule.findExportByName(target_symbol);
  Interceptor.attach(target,{
    onEnter(args)
    {
      const realFd = args[0].toInt32();
      // open函数打开原始apk 获得fakefd
      const openResult = openFn(originalApkPtr,O_RDONLY | O_CLOEXEC);
      const fakeFd = openResult.value;
      // 使用dup2函数复制fakefd
      const dup2Result = dup2Fn(fakeFd,realFd);
      if(dup2Result.value < 0)
      {
        closeFn(fakeFd);
        return;
      }
      this.shadowFd = fakeFd;
    },
    onLeave()
    {
      if(this.shadowFd >= 0)
      {
        closeFn(this.shadowFd);
        console.log("替换成功");
      }
    }
  });

}

function main() {
  console.log("hook start");
  // 轮询查找目标so文件
  var isHooked = false;
  var timer = setInterval(function(){
    var module = Process.findModuleByName(target_so);
    if(module !== null && !isHooked)
    {
      hookFd();
      clearInterval(timer);
    }
  },10);
}

setImmediate(main);
```

这里使用dup2函数替换了原始的fd，这时fd指向的不再是当前应用的base.apk，而是我们早就准备好的原始apk，所以校验一定会成功。

运行脚本，同样可以成功绕过

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_MKABW3NFQ3QU4KS.png)

当然这种方法也有对应的保护措施

可以新建一个函数，用来判断fd是否被替换。

```
// native-lib.cpp
if (!Utils::isExpectedFdPath(fd, path)) {
        LOGE("APK签名验证失败 原因: fd path mismatch");
        close(fd);
        return 2;
    }
// Utils.cpp
bool Utils::isExpectedFdPath(int fd, const std::string& expected_path)
{
    if (fd < 0 || expected_path.empty()) {
        return false;
    }

    char fd_link[64] = {};
    std::snprintf(fd_link, sizeof(fd_link), "/proc/self/fd/%d", fd);

    char resolved_path[PATH_MAX] = {};
    ssize_t len = readlink(fd_link, resolved_path, sizeof(resolved_path) - 1);
    if (len <= 0) {
        return false;
    }

    resolved_path[len] = '\0';
    return expected_path == resolved_path;
}
```

假如fd指向的不再是原始文件，证明被重定向

这里修改了一下函数类型，如果是被替换则返回2，MainActivity调用

```java
case "signature_native_button":
    native_res = SignatureVerificationNative();
    if(native_res == 1)
    {
        native_textView.setText("签名校验成功");
    }
    else
    {
        native_textView.setText("签名校验失败");
    }
    if(native_res == 2)
    {
        native_textView.setText("检测到fd被替换");
    }
```

再次hook，观察日志

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_7MBME62MYN2VD27.png)

### 对比Inode值

除了上面检测fd路径的方法，还可以对比Inode的值

Inode就像每个文件的身份证，里面不存储具体数据，而是存文件的元数据。每个文件都有一个唯一的Inode值。

```
bool Utils::isExpectedFdInode(int fd, const std::string& expected_path)
{
    if(fd < 0 || expected_path.empty()) return false;
    // stat64结构体储存文件系统元数据
    struct stat64 fd_stat;
    // 获取文件系统元数据
    if(fstat64(fd,&fd_stat) != 0) return false;
    // Linux 特殊的虚拟文件/proc/self/maps记录了当前 App 进程加载到内存里的所有模块和文件
    std::ifstream  maps_files("/proc/self/maps");
    std::string  line,dummy,path;
    unsigned long long maps_inode;
    // 逐行读取maps内容
    while (std::getline(maps_files,line))
    {
        if(line.find(expected_path) == std::string ::npos) continue;
        std::istringstream iss(line);
        // maps格式通常为 : 地址 权限 偏移 设备号 Inode 路径
        // 这里将line按流解析 直接获得第五个Inode
        if(iss >> dummy >> dummy >> dummy >> dummy >> maps_inode >> path)
        {
            if(path == expected_path)
            {
                // 将当前fd的Inode与原始apk的Inode值进行比较
                return maps_inode == static_cast<unsigned long long>(fd_stat.st_ino);
            }
        }
    }
    return false;
}
```

注释掉刚才的fd检测，新加上这个检测Inode值的函数，运行

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_SKS9K8GX4W2AKDE.png)

成功检测到。fd检测可以通过magisk挂载等方式解决，比对Inode号的检测方法更加直接

## 最后

本人是安卓蒟蒻一枚~因为只是想作为练习，所以这个apk写的也不是很完善，还有很多可以hook的地方。在此附上apk，如果apk或文中出现的代码有任何问题，希望各位大佬指正，如果有其他看法也欢迎和我交流，感谢大家阅读

上传的附件：
- app-debug.apk

（9.71MB，52次下载）

---

# 回复

## 回复 by Liv_T (#2)

*2026-5-18 00:19*

学习学习

## 回复 by PangBai (#3)

*2026-5-18 00:35*

沙发

## 回复 by fu11p7r (#4)

*2026-5-18 00:42*

学习

## 回复 by SomeMx (#5)

*2026-5-18 07:13*

过来瞧瞧

## 回复 by mb_rirvdrlh (#6)

*2026-5-18 07:48*

666666666666

## 回复 by mb_rndpmawh (#7)

*2026-5-18 08:04*

学习

## 回复 by huangjw (#8)

*2026-5-18 09:13*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by 086Love (#9)

*2026-5-18 09:18*

学习

## 回复 by mb_ldbucrik (#10)

*2026-5-18 12:04*

感谢分享

## 回复 by CheRevir (#11)

*2026-5-18 13:58*

666

## 回复 by taeyeon_ss (#12)

*2026-5-18 14:09*

233333

## 回复 by xingbing (#13)

*2026-5-18 15:52*

学习学习

## 回复 by mb_bfghjvta (#14)

*2026-5-18 16:28*

学习学习

## 回复 by 温泉划水鱼 (#15)

*2026-5-18 17:57*

学习

## 回复 by xput (#16)

*2026-5-18 19:09*

感谢分享

## 回复 by 无视红绿灯 (#17)

*2026-5-18 19:12*

111

## 回复 by 三点水的湫 (#18)

*2026-5-18 19:37*

ooo

## 回复 by 恋一世的爱 (#19)

*2026-5-18 19:39*

看看，感觉应该早就过掉了

## 回复 by wx_coddvccwyh (#20)

*2026-5-18 21:22*

66666

## 回复 by ROM2639 (#21)

*2026-5-18 22:00*

学习学习

## 回复 by 院士 (#22)

*2026-5-18 22:01*

来学习了。

## 回复 by mb_xjdhrmck (#23)

*2026-5-19 00:45*

666

## 回复 by mb_ofgyxagz (#24)

*2026-5-19 01:58*

看看

## 回复 by 夜惜风雨 (#25)

*2026-5-19 09:32*

66666666

## 回复 by mb_eqttlgdj (#26)

*2026-5-19 09:49*

6666666

## 回复 by 窗外的荡秋千 (#27)

*2026-5-19 15:50*

666

## 回复 by shuaiaimei (#28)

*2026-5-19 16:55*

看看

## 回复 by xianhuimin (#29)

*2026-5-19 17:43*

666

## 回复 by Da_ (#30)

*2026-5-19 20:08*

666

## 回复 by mb_zuqeschf (#31)

*2026-5-20 08:26*

111

## 回复 by YoungBai (#32)

*2026-5-20 09:45*

666

## 回复 by 学计算机睡觉 (#33)

*2026-5-20 11:14*

6666

## 回复 by jyotidwi (#34)

*2026-5-20 12:38*

66666

## 回复 by mb_ahyhoece (#35)

*2026-5-20 17:30*

666

## 回复 by mb_euhyowpw (#36)

*2026-5-20 17:31*

1231

## 回复 by 魔童 (#37)

*2026-5-20 19:45*

66666

## 回复 by XJ。 (#38)

*2026-5-20 19:58*

看看

## 回复 by mb_wtskxwnr (#39)

*2026-5-20 20:45*

666

## 回复 by wx_北极星_493 (#40)

*2026-5-20 22:17*

看看

## 回复 by lixianhuei (#41)

*2026-5-21 10:38*

666

## 回复 by XCicada (#42)

*2026-5-21 11:57*

学习

## 回复 by mb_tewbhakr (#43)

*2026-5-21 14:55*

66666666666

## 回复 by wx_Dispa1r (#44)

*2026-5-21 15:17*

1

## 回复 by 一栋奥特曼 (#45)

*2026-5-21 16:05*

6666

## 回复 by B.M.K (#46)

*2026-5-21 16:28*

66

## 回复 by FMNS (#47)

*2026-5-21 16:32*

666

## 回复 by pan_634488 (#48)

*2026-5-21 16:47*

66666666

## 回复 by RookieApe (#49)

*2026-5-22 09:52*

学习学习

## 回复 by C1ever (#50)

*2026-5-22 10:22*

66666

## 回复 by iBa0 (#51)

*2026-5-22 15:51*

123

## 回复 by chionyuna (#52)

*2026-5-22 16:54*

1111

## 回复 by 钱钱钱￥ (#53)

*2026-5-22 17:23*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_zwojibcx (#54)

*2026-5-22 18:53*

![image](https://bbs.kanxue.com/view/img/face/002.gif)

## 回复 by mb_fdskejlh (#55)

*2026-5-22 20:16*

牛啊牛啊

## 回复 by mb_rtxtnuec (#56)

*2026-5-22 23:04*

感谢分享

## 回复 by 寻梦之璐 (#57)

*2026-5-22 23:17*

666

## 回复 by kingking888 (#58)

*2026-5-23 12:06*

666

## 回复 by 呆萌的小白 (#59)

*2026-5-23 16:14*

很需要,因为某平台软件,经过重定向处理后不能用,看日志还看不出来什么

## 回复 by guijingwen (#60)

*2026-5-23 18:13*

66

## 回复 by mb_4nrpVMxJ (#61)

*2026-5-23 18:26*

666

## 回复 by mJqalJqN (#62)

*2026-5-24 00:06*

1

## 回复 by mb_isbmbfet (#63)

*2026-5-24 11:53*

666

## 回复 by 咸鱼…… (#64)

*2026-5-24 13:00*

666

## 回复 by 简单的简单 (#65)

*2026-5-24 22:38*

1

## 回复 by mb_qqamgdce (#66)

*2026-5-25 09:08*

>
> [taeyeon_ss](https://bbs.kanxue.com/user-996488.htm)
>  233333
>

大佬，看你绕过了某App反调试和分析斗地主的帖子，技术很扎实。我自研了一套国密SM2/SM3/SM4+防逆向安全基座，想请你帮忙验验成色。源码已埋水印，你方便时拆一下？拆不穿帮我指条变现的路。QQ：1404716956

## 回复 by wx_技术Liu (#67)

*2026-5-25 11:08*

66

## 回复 by mb_mxsesokv (#68)

*2026-5-25 14:06*

学习

## 回复 by mb_ywyqvlni (#69)

*2026-5-25 14:39*

666

## 回复 by mb_zdoxkucm (#70)

*2026-5-25 15:18*

kkyv

## 回复 by mb_hcadvceu (#71)

*2026-5-25 18:16*

路过看看

## 回复 by mb_uvyukvot (#72)

*2026-5-26 10:53*

666

## 回复 by 逆道而行 (#73)

*2026-5-26 12:28*

666

## 回复 by uni7corn (#74)

*2026-5-27 12:15*

666

## 回复 by 毛毛毛毛虫 (#75)

*2026-5-27 15:33*

学习一下

## 回复 by mb_osxdmntv (#76)

*2026-5-27 18:45*

666

## 回复 by 沫水. (#77)

*2026-5-28 08:44*

111

## 回复 by popsky_ok (#78)

*2026-5-29 03:18*

看看在SO中如何实现

## 回复 by git_94327axixa518 (#79)

*2026-5-29 19:16*

5555

## 回复 by mb_ecyhqrqd (#80)

*2026-5-29 23:21*

太有实力了

## 回复 by TeamAR (#81)

*2026-5-30 00:38*

看看

## 回复 by huangbof (#82)

*2026-5-30 01:49*

将open函数自动替换为__open_2，所以这里不能只ho

## 回复 by 偶尔.c (#83)

*2026-5-31 00:05*

看看隐藏，感谢分享

## 回复 by buluo533 (#84)

*2026-5-31 09:24*

学习了，大佬

## 回复 by 珍惜Any (#85)

*2026-6-1 16:05*

点赞点赞，写的很好~

## 回复 by 随风而行aa (#86)

*2026-6-1 22:47*

看看

## 回复 by 啊哈_623438 (#87)

*2026-6-2 13:26*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by 伊苏尔德 (#88)

*2026-6-2 18:45*

6

## 回复 by mb_fnxpmwzu (#89)

*2026-6-2 22:49*

666

## 回复 by blx2024 (#90)

*2026-6-3 10:21*

看看

## 回复 by Viseris (#91)

*2026-6-4 09:48*

66666

## 回复 by 珍惜Any (#92)

*2026-6-4 17:36*

点赞~![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by ROSE0 (#93)

*2026-6-4 17:57*

666666

## 回复 by mb_xyoslnox (#94)

*2026-6-4 19:59*

学习学习

## 回复 by mb_nggigxxl (#95)

*2026-6-5 23:19*

66666

## 回复 by Mr.ChenX (#96)

*2026-6-6 11:16*

666

## 回复 by AK1988DA (#97)

*2026-6-6 17:40*

444

## 回复 by mb_gkbxtfri (#98)

*2026-6-6 17:55*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_wckjnnha (#99)

*2026-6-6 18:02*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>  点赞~[em_014]
>

膜拜珍惜大神！书写的非常不错

## 回复 by 那么一下下 (#100)

*2026-6-7 11:05*

6666666

## 回复 by mb_ykqbcfdu (#101)

*2026-6-7 11:37*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by git_87237minhdanhsc (#102)

*2026-6-7 16:04*

111

## 回复 by apxar (#103)

*2026-6-7 16:08*

1

## 回复 by mb_agxdcibq (#104)

*2026-6-7 16:41*

666

## 回复 by 烬奇小云 (#105)

*2026-6-7 17:59*

666

## 回复 by koftnt (#106)

*2026-6-7 20:23*

学习

## 回复 by mb_ehfqhzdm (#107)

*2026-6-10 10:33*

666666666666

## 回复 by Sadmin (#108)

*2026-6-11 15:46*

66666666

## 回复 by mb_kgneopde (#109)

*2026-6-12 18:08*

666

## 回复 by shuangmou (#110)

*2026-6-12 22:51*

感谢分享

## 回复 by mb_yfxezfnn (#111)

*2026-6-14 06:39*

666

## 回复 by xiaoc996 (#112)

*2026-6-14 10:39*

66

## 回复 by mb_orouaapx (#113)

*2026-6-15 02:12*

看看

## 回复 by 一四得肆 (#114)

*2026-6-15 15:09*

学习

## 回复 by veluboii (#115)

*2026-6-15 23:02*

666

## 回复 by 飆汗吉米 (#116)

*2026-6-17 01:21*

666

## 回复 by mb_lfvhycml (#117)

*2026-6-17 13:06*

1

## 回复 by 恋一世的爱 (#118)

*2026-6-19 01:19*

你这个原版，测试也会不通过

## 回复 by 白毅 (#119)

*2026-6-19 02:06*

猛攻…….

## 回复 by mb_ntpggcsm (#121)

*2026-6-20 03:26*

好

## 回复 by mb_ajkljcfj (#122)

*2026-6-22 15:07*

6666

## 回复 by wx_Dr.strange (#123)

*2026-6-23 16:57*

66666666

## 回复 by mb_ajqftfbv (#124)

*2026-6-24 03:42*

66666666

## 回复 by git_34548yef2779-bit (#125)

*2026-6-24 08:42*

学习学习

## 回复 by dob_C (#126)

*2026-6-24 10:39*

感谢分享

## 回复 by 张恒_884729 (#127)

*2026-6-25 17:25*

66666666666

## 回复 by ClPrada (#128)

*2026-6-25 18:01*

![image](https://bbs.kanxue.com/view/img/face/056.gif)

## 回复 by ulong9527 (#129)

*2026-6-26 09:43*

感谢分享，学习一下

## 回复 by 无情铁手 (#130)

*2026-6-26 13:53*

66

## 回复 by zengaven (#131)

*2026-6-26 17:52*

6666666666666666

## 回复 by wx_靛芒 (#132)

*2026-6-28 01:09*

看看

## 回复 by 千谦 (#133)

*2026-6-28 01:10*

66

## 回复 by Ankeys (#134)

*2026-6-28 22:15*

看看

## 回复 by 4Chan (#135)

*2026-6-29 15:21*

学习下

## 回复 by mb_ugfkvowp (#136)

*2026-7-7 11:04*

666

## 回复 by taeyeon_ss (#137)

*2026-7-7 17:24*

文章写的不错，但是被csdn的一个憨批抄过去了。链接：https://blog.csdn.net/2503_90751789/article/details/161751210?spm=1001.2014.3001.5502
我写的帖子也被爬了，而且这货还把文章里的看雪图片水印给裁剪了![image](https://bbs.kanxue.com/view/img/face/019.gif)

## 回复 by cx52038 (#138)

*2026-7-7 20:07*

666

## 回复 by mb_mpebdgbn (#139)

*2026-7-7 20:13*

为你点赞！

## 回复 by wx_kx92911 (#140)

*2026-7-9 10:05*

感谢分析

## 回复 by Crack999 (#141)

*2026-7-9 10:07*

感谢分享

## 回复 by 独狼自我修养 (#142)

*2026-7-17 03:50*

666

## 回复 by 钟白 (#143)

*2026-7-19 02:48*

666

## 回复 by aii9917 (#144)

*2026-7-20 20:49*

66

## 回复 by aii9917 (#145)

*2026-7-20 20:49*

666

## 回复 by git_78406ACmodel (#146)

666

## 回复 by didiid (#147)

6666

## 回复 by zkbutt (#148)

学习

## 回复 by mb_cbgtaveo (#149)

66666666

## 回复 by mb_cjbkfrpc (#150)

学习

## 回复 by mb_akzdpbgl (#151)

看看

## 回复 by mb_irhdtnzm (#152)

6
