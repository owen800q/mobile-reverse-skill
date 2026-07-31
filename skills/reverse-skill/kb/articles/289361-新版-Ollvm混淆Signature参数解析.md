---
title: '[原创]新版****Ollvm混淆Signature参数解析'
url: https://bbs.kanxue.com/thread-289361.htm
tid: 289361
author: A0tem
date: '2025-12-08'
tags: [Android安全, 原创, 逆向分析, 协议分析]
crawled_at: '2026-07-31T15:22:20+08:00'
replies: 136
---

案例为最新版某马拉雅,可在豌豆夹下载(技术交流可加A0tem_  备注看雪)

# 抓包

## 发送验证码

```
POST /mobile/sms/v3/send HTTP/2
host: passport.ximalaya.com
cookie: 1&_device=android&d13a02e8-8efe-3427-80d8-e9347afe3e63&9.4.21;channel=and-f5;impl=com.ximalaya.ting.android;osversion=29;fp=009527657x2222q22264v0500700000000000000000000000000000000000;device_model=Pixel+2+XL;XIM=;c-oper=%E6%9C%AA%E7%9F%A5;net-mode=WIFI;res=1440%2C2712;AID=YTBiNTZmNjE1NTc2ODcyYQ==;manufacturer=Google;XD=SwmCBcM0DUJdkboCzp7x4FOk8Sp6aAtdSin4EsgNbx7+LoTgvWvpnD0fJ9tPskX9e1UXnLxL3Bn06ANSvQ+LCerM3eC5cDACyylaE7O3AW2dCDBfUBXa7UlnA6pbyIEe;xm_grade=0;specialModeStatus=0;
cookie2: $version=1
accept: */*
user-agent: ting_9.4.21(Pixel+2+XL,Android29)
x-tk: TACaS_-ndE6AuiO_jQngNjpNHr-PmPYLLD6cS5y7RNafhjt4EGQcET4NNoJs_RgxpBcO8_6aq6Dos-dtDmhvp9dYDhJKt9jb20ueGltYWxheWEudGluZy5hbmRyb2lkITEuMy4yNyE5LjQuMjEuMyFiPXBhc3Nwb3J0JnM9bG9naW4mdT0w
http_dns_address: old,d_s=false;d_g=true;d_f=true;d_i=false;p=false;h=false
content-type: application/json; charset=utf-8
content-length: 1165
accept-encoding: gzip
{"fdsOtp":"{}",
"biz":"1",
"signature":"e4cf26b5e716127762507811a4c747cf8e127a6f",
"mobile":"",
"sendType":"1",
"nonce":"0-224742D9E414bf681cef6aa5dfb1440934eba4d3a13a82532c3cbca33a3d8a"}
```

我们主要分析signature参数，signature长度为40，大概率为SHA1

# 逆向分析

## 发送验证码参数signature

首先搜索请求体字段中的fdsOtp定位关键代码

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_WUBW9D7FMD787S9.webp)

总共有三个，分别对应不同的登录形式，我们只关注验证码登录即可

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_R8HWR3XN5XDW5GR.webp)

```
                private void b(String str2) {
                    HashMap map = new HashMap();
                    if (AnonymousClass11.this.f72593c != null) {
                        if (AnonymousClass11.this.f72593c.containsKey("mobile")) {
                            map.put("mobile", (String) AnonymousClass11.this.f72593c.get("mobile"));
                        }
                        map.put("sendType", (String) AnonymousClass11.this.f72593c.get("sendType"));
                    }
                    map.put("nonce", str);
                    if (!TextUtils.isEmpty(str2)) {
                        map.put("fdsOtp", str2);
                    }
                    map.put(com.alipay.sdk.app.statistic.c.f5786b, AnonymousClass11.this.f72592b + "");
                    map.put("signature", LoginRequest.b(AnonymousClass11.this.f72594d, map));
                    LoginRequest.f72585b = System.currentTimeMillis();
                    LoginRequest.a(AnonymousClass11.this.f72594d, k.a().j(), map, AnonymousClass11.this.f72591a, new com.ximalaya.ting.android.loginservice.b.a<BaseResponse>() { // from class: com.ximalaya.ting.android.loginservice.LoginRequest.11.1.2
                        @Override // com.ximalaya.ting.android.loginservice.b.a
                        /* renamed from: a, reason: merged with bridge method [inline-methods] */
                        public BaseResponse b(String str3) throws Exception {
                            return (BaseResponse) new Gson().fromJson(str3, BaseResponse.class);
                        }
                    });
                }
```

可以发现signature参数的生成与代码

```
map.put("signature", LoginRequest.b(AnonymousClass11.this.f72594d, map));
```

有关，追踪，最终定位到

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_H7F4398F2X8RGY8.webp)

最终定位到此处代码，发现需要分析so层实现内容(login_encrypt)，为了更清楚的分析，我们需要先了解进入so层前传入的参数是什么形式，

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_JQZCJRWSWQF5ZZB.webp)

打印传入的参数，内容为:

```
z    = false
str  = biz=1&fdsOtp={"captcha_id":"3723312ce42a04b5c0b40e605a882037","lot_number":"b48afede55594f09ba5c82b9593b7402","pass_token":"a6d1832f7fe4a37776e5b5d610b2c45f42dd2d00007f061f3c4e20613a67f22a","gen_time":"1764764163","captcha_output":"2Z76G2CapbcJxb3z0NRv6M3hvdvpPpJiZYrOHqnYCvDSbFN1VW0MwSEZ3bzVLqngdIUnBFLqkqeiuyHwBeNxxkik34W9dQ5VNZm9JK-HSYpcxrp0NAOilcOY2Hvd1fNbL1gaiSbmgIg2vkSkBKcNidZdAs6JYmiWSCWjxwaE_iQXvm1gZABlsGsilYp-owYg05gxV5FZ70aYkw5cjkllOPITxWc_B7js3HAoApNEamZuLa0mKyHoTKcpRf41IXVgauvjOHYhM2nXeiif08NADj8Ho4NaELWsS2qZD01zZNtT0AWOZuE_z85Kgy3XHDHKm6hNryiY_0XtMaVPUWHalIbmumT1UetSWnZmhOnaxiQfob3m4-9gSby6csz3TM_EgSoRlWbM_cA7aDcQ8uapUlDXi3caucce-a7rHF31LnJOdVcWw-0OS13zo-xh-cD0qkilsQ3wPKe94ESLrSFxR2W8Avfuin5zYpWW49U6cllffSicGk4B7fKO0mkVZMrHl9E5KxX0n4zG4-cED9B4kasrOrbirl8rWEQjFgVwUog="}&mobile=epMimImhTRIy8xX0F3mQa5ccuLd7UtpUEwpkLKp6KYE87t/GhiVYaGzhkFvctWeBhYP8xqpKEzwo
co/J+Zl6fOlaSRCa/3VGkQswp+W0eaZw9JXTSpFTj7yX6sB17qgQIecCwT4z1WpcK85lwyY6iSvE
8Ml8sVmq/VHvc6FI7fQ=
&nonce=0-3E044F385FFB3fa71dad20ad2190576fdf24e4d639e8b3a3b76fbbc3ba03ec&sendType=1&
```

发现so层代码将近2500行，存在Ollvm混淆

我们从头开始分析代码

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_27W95JPPDEQZ3BA.webp)

修正函数头之后，先分析前几行代码

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_G6S6ZZ49NP2ZYHV.webp)

```
int *__fastcall sub_10F8(int a1, int a2)
{
  int i; // r0
  int v4; // r4
  int v5; // r9
  unsigned int v6; // r0
  int v7; // r2
  bool v8; // zf
  int v9; // r2
  int *v12; // [sp+4h] [bp-34h]
  bool v13; // [sp+12h] [bp-26h]
  bool v14; // [sp+13h] [bp-25h]
  int v15; // [sp+14h] [bp-24h]
  bool v16; // [sp+1Bh] [bp-1Dh]
  v13 = (((x_149 * (x_149 - 1)) ^ 0xFFFFFFFE) & (x_149 * (x_149 - 1))) == 0;
  v14 = y_150 < 10;
  v12 = &y_150;
  for ( i = 642638909; ; i = 1890200666 )
  {
LABEL_14:
    while ( i <= 642638908 )
    {
      i = 1448165231;
      if ( v16 )
        i = -1518418466;
      if ( i <= -64863450 )
      {
        while ( 1 )
        {
LABEL_3:
          while ( i == -2015175878 )
          {
            v4 = (*(int (__fastcall **)(int, void *))(*(_DWORD *)a1 + 24))(a1, &unk_1B010);
            (*(void (__fastcall **)(int, int, char *, char *))(*(_DWORD *)a1 + 132))(a1, v4, &byte_1B02F, &byte_1B040);
            (*(void (__fastcall **)(int, int))(*(_DWORD *)a1 + 92))(a1, v4);
            i = -957104787;
          }
          if ( i != -957104787 )
            break;
          v5 = (*(int (__fastcall **)(int, void *))(*(_DWORD *)a1 + 24))(a1, &unk_1B010);
          v15 = (*(int (__fastcall **)(int, int, char *, char *))(*(_DWORD *)a1 + 132))(
                  a1,
                  v5,
                  &byte_1B02F,
                  &byte_1B040);
          v16 = v15 == 0;
          (*(void (__fastcall **)(int, int))(*(_DWORD *)a1 + 92))(a1, v5);
          v6 = (~(x_149 * (x_149 - 1)) | 0xFFFFFFFE) + 1;
          v7 = -2015175878;
          if ( y_150 < 10 != (v6 == 0) )
            v7 = -64863449;
          v8 = v6 == 0;
          i = v7;
          if ( v8 )
            i = -64863449;
          if ( y_150 >= 10 )
            i = v7;
          if ( i > -64863450 )
            goto LABEL_14;
        }
        i = 1890200666;
        v12 = (int *)&unk_19B64;
      }
    }
    if ( i == 642638909 )
    {
      v9 = -2015175878;
      if ( (v13 ^ v14) << 31 )
        v9 = -957104787;
      i = v9;
      if ( v14 )
        i = -957104787;
      if ( !v13 )
        i = v9;
      goto LABEL_3;
    }
    if ( i != 1448165231 )
      break;
    v12 = (int *)(*(int (__fastcall **)(int, int, int))(*(_DWORD *)a1 + 136))(a1, a2, v15);
  }
  return v12;
}
```

可以看到存在一定程度的混淆，去除控制流垃圾

```
// case i == -2015175878:
v4 = (*(int (__fastcall **)(int, void *))(*(_DWORD *)a1 + 24))(a1, &unk_1B010);
(*(void (__fastcall **)(int, int, char *, char *))(*(_DWORD *)a1 + 132))(a1, v4, &byte_1B02F, &byte_1B040);
(*(void (__fastcall **)(int, int))(*(_DWORD *)a1 + 92))(a1, v4);
i = -957104787;
// case i == -957104787:
v5 = (*(int (__fastcall **)(int, void *))(*(_DWORD *)a1 + 24))(a1, &unk_1B010);
v15 = (*(int (__fastcall **)(int, int, char *, char *))(*(_DWORD *)a1 + 132))(
          a1,
          v5,
          &byte_1B02F,
          &byte_1B040);
v16 = v15 == 0;
(*(void (__fastcall **)(int, int))(*(_DWORD *)a1 + 92))(a1, v5);
```

按照JNI模式解析，大概率为

```
jclass clazz = (*env)->FindClass(env, "xxx");                  // &unk_1B010
jmethodID mid = (*env)->GetMethodID(env, clazz, "name", "sig"); // &byte_1B02F, &byte_1B040
(*env)->DeleteLocalRef(env, clazz);
v16 = (mid == 0);
```

查看一下对应的内存地址，是否为类名

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_AYMEDX7YFGEQSF3.webp)

可以看到字符串被混淆了，根据交叉引用寻找

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_ABR8KMZK74JM3YY.webp)

发现存在解密代码

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_DPM9DN2JGAVFJ6A.webp)

```
# asc_1B010 原始密文字节
ida_chars = [
    0xFC, 0xF3, 0xF9, 0xEF, 0xF2, 0xF4, 0xF9, 0xB2, 0xFE, 0xF2,
    0xF3, 0xE9, 0xF8, 0xF3, 0xE9, 0xB2, 0xDE, 0xF2, 0xF3, 0xE9,
    0xF8, 0xE5, 0xE9, 0xCA, 0xEF, 0xFC, 0xED, 0xED, 0xF8, 0xEF,
    0x9D,
]
def decode(data):
    out = []
    for b in data:
        # 按 C 里的写法： dst = ~( (b & 0x9D) | (~b & 0x62) );
        # 再按 unsigned char 截断到 8 位
        v = ~((b & 0x9D) | (~b & 0x62)) & 0xFF
        out.append(v)
    return bytes(out)
plain = decode(ida_chars)
print("hex :", plain.hex())
try:
    print("ascii:", plain.decode("ascii"))
except UnicodeDecodeError:
    print("ascii decode failed")
#android/content/ContextWrapper
```

其他解密也是相同的，这样我们就知道了这个函数其实就是获取包名，脚本写为Idapython脚本更方便

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_5SCFF4A6M2GKWF8.webp)

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_YGTV8WDD8Q96A8F.webp)

发现都是进行比较，我们解密另一个参数即可，还是按照刚才的方法

```
byte_1B310-byte_1B32A 为
com.ximalaya.android.sleep
aJfdQDhehphfzYh 为
com.ximalayaos.pad[00]
byte_1BA00
com.ximalaya.huibenguan.android[00]
byte_1B330
com.ximalaya.android.sleep.dev\x00
```

可以看到所有的strcmp就是和硬编码的包名比较，所以我们需要找到对应的包名

最终是在一千一百多行发现

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_YC7KFP3BT6JTH3B.webp)

发现比较成功之后，会设置v13=1825021717，这个v13就是状态机，觉得下一步会执行什么代码，因此我们追踪if(v13==1825021717)的代码即可

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_JEKTRJ9ZB7TATZB.webp)

这两个地址解密的数据为:

```
byte_1B510   解密后为;MOBIL-V1-PRODUCT-1
   aD7dgkjj1K1g5Gk                   解密后为:7D74899B338B4F348E2383970CC09991E8E8D8F2BC744EF0BEE94D76D718C0894
```

![image](https://bbs.kanxue.com/upload/attach/202512/1060705_472AAC2XSFHZHNX.webp)

可以发现设置v13的状态为2590219376，继续跟进发现没有搜到，这时候可以切换为十六进制形式0x9A639C70发现找到了对应代码

```
else if ( v13 <= -1520500360 )
{
  if ( v13 == 0x9A639C70 )      // = -1704747920
  {
    v261 = v228;                // 保存 key 字符串
    v262 = v230;                // 保存标志位
    v260 = v5;                  // 保存 "MOBIL-V1-PRODUCT-1" 之类
    v239 = (char *)(*v231)->GetStringUTFChars(v231, str, 0);  // jstring str -> char*
    v13 = 923489355;
    v14 = v15;
    if ( !v230 )
      v13 = 816144671;          // v230==0 时，状态改成 816144671
  }
}
```

所以我们继续跟进新的状态

```
if ( v13 == 816144671 )         // 这里
{
v13 = 3581685779;
if ( (~(x_153 * (x_153 - 1)) | 0xFFFFFFFE) == 0xFFFFFFFF )
v13 = 909332025;
v97 = 0;
if ( y_154 < 10 )
v97 = 1;
else
v13 = 3581685779;
if ( v97 != ((~(x_153 * (x_153 - 1)) | 0xFFFFFFFE) == -1) )
v13 = 909332025;
}
```

寻找有没有等于3581685779和909332025的

```
 else if ( v13 == 909332025 )
              {
                v53 = strlen(v260);             // 这个值为MOBIL-V1-PRODUCT-1
                v54 = (char *)malloc(v53);
                qmemcpy(v54, v260, strlen(v260) - 1);
                v54[-(1 - strlen(v260))] = 0;   // 复制的时候去除最后一位
                v55 = strlen(v261);             // 这个值为7D74899B338B4F348E2383970CC09991E8E8D8F2BC744EF0BEE94D76D718C0894
                v56 = (char *)malloc(v55);
                qmemcpy(v56, v261, strlen(v261) - 1);// 复制的时候去除最后一位
                v56[strlen(v261) - 1] = 0;

                v57 = strlen(c_str) - 123099768;
                v58 = strlen(v54);
                v59 = strlen(v56) + v58 + v57 + 123099769;// v59等于三段字符串总长度加\0
                v60 = malloc(v59);
                memset(v60, 0, v59);

                strcat((char *)v60, c_str);     // 拼接待签名原始数据
                strcat((char *)v60, v54);       // 拼接版本标识
                strcat((char *)v60, v56);       // 拼接key字符串
                v240 = (int)(*v231)->NewStringUTF(v231, (const char *)v60);
                free(v54);
                v61 = v56;
                v12 = 1215952980;
                free(v61);
                free(v60);
                v13 = -713281517;
                if ( (~(x_153 * (x_153 - 1)) | 0xFFFFFFFE) == 0xFFFFFFFF )
                  v13 = -1769657914;
                v62 = 0;
                if ( y_154 < 10 )
                  v62 = 1;
                else
                  v13 = -713281517;
                v14 = v15;
                if ( v62 != ((~(x_153 * (x_153 - 1)) | 0xFFFFFFFE) == -1) )
                  v13 = -1769657914;
              }
```

所以我们现在需要追踪v240

```
  else if ( v13 > -1771541319 )
            {
              if ( v13 != -1771541318 )
              {
                v45 = v240;
LABEL_360:
                v13 = 493313113;
                v223 = (char *)v45;
                v14 = v15;
                continue;
              }
              v208 = v231;
              (*v231)->DeleteLocalRef(v231, (jobject)v254);
              (*v208)->DeleteLocalRef(v208, (jobject)v242);
              v257 = (int)(*v208)->CallObjectMethod(v208, (jobject)v246, (jmethodID)v245);
              v209 = ((int (__fastcall *)(JNIEnv *))(*v208)->ExceptionCheck)(v208);
              v13 = -1805937577;
              v21 = v209 == 0;
              v14 = v15;
              if ( !v21 )
                v13 = 1741960892;
            }
```

状态转移：v240 存进 v223，状态 v13 = 493313113

```
if ( v13 == 493313113 )
{
  v263 = v223;                         // ① 保存前面构造好的 jstring 指针
  v189 = (~(x_153 * (x_153 - 1)) | 0xFFFFFFFE) + 1;
  v190 = -1326811784;
  if ( y_154 < 10 != (v189 == 0) )
    v190 = -925493942;
  v21 = v189 == 0;
  v13 = v190;
  v14 = v15;
  if ( v21 )
    v13 = -925493942;
  if ( y_154 >= 10 )
    v13 = v190;
}
```

这两个新状态都可以找到，一个是加密后检查，一个是加密，我贴上加密的

```
  else if ( v13 == -1326811784 )
              {
                v226 = v14;
                v69 = v231;
                v70 = (int)(*v231)->FindClass(v231, &byte_1BCA0);
                v71 = (int)(*v69)->GetMethodID(v69, (jclass)v70, &byte_1BCB1, &byte_1B040);
                v72 = (int)(*v69)->CallObjectMethod(v69, v263, (jmethodID)v71);
                v73 = (int)(*v69)->GetMethodID(v69, (jclass)v70, &byte_1B29F, &byte_1B2B0);
                CallObjectMethod = (*v231)->CallObjectMethod;
                v75 = (int)(*v69)->NewStringUTF(v69, &byte_1BCBD);
                CallObjectMethod(v231, (jobject)v72, (jmethodID)v73, v75);
                v76 = (int)(*v69)->FindClass(v69, &byte_1BCD0);
                v77 = (int)(*v69)->GetMethodID(v69, (jclass)v76, &byte_1B126, &byte_1B27E);
                (*v69)->GetMethodID(v69, (jclass)v76, aJ, byte_1BCF0);
                (*v69)->GetMethodID(v69, (jclass)v76, &byte_1BD1E, &byte_1B040);
                (*v69)->NewObject(v69, (jclass)v76, (jmethodID)v77);
                v12 = 1215952980;
                (*v69)->GetMethodID(v69, (jclass)v76, aJ, &byte_1BD30);
                v78 = (int)(*v69)->FindClass(v69, &byte_1BD50);
                v79 = (int)(*v69)->GetStaticMethodID(v69, (jclass)v78, &byte_1B079, byte_1BD70);
                v80 = (int)(*v69)->NewStringUTF(v69, &byte_1BDA2);
                (*v69)->CallStaticObjectMethod(v69, (jclass)v78, (jmethodID)v79, v80);
                (*v69)->ExceptionCheck(v69);
                v13 = -925493942;
                v14 = v226;
              }
```

全部解密

```
  else if ( v13 == -1326811784 )
              {
                v226 = v14;
                v69 = v231;
                v70 = (int)(*v231)->FindClass(v231, &byte_1BCA0);// java/lang/String
                v71 = (int)(*v69)->GetMethodID(v69, (jclass)v70, &toUpperCase, &byte_1B040);// ()Ljava/lang/String;
                v72 = (int)(*v69)->CallObjectMethod(v69, v263, (jmethodID)v71);
                v73 = (int)(*v69)->GetMethodID(v69, (jclass)v70, &getBytes, &byte_1B2B0);// (Ljava/lang/String;)[B
                CallObjectMethod = (*v231)->CallObjectMethod;
                v75 = (int)(*v69)->NewStringUTF(v69, &byte_1BCBD);// utf-8

                CallObjectMethod(v231, (jobject)v72, (jmethodID)v73, v75);
                v76 = (int)(*v69)->FindClass(v69, &byte_1BCD0);// java/lang/StringBuilder
                v77 = (int)(*v69)->GetMethodID(v69, (jclass)v76, &byte_1B126, &byte_1B27E);// 第三个参数为：<init>\x00([B)V\x00generatePublic\x00   第四个参数()V\x00write\x00toByteArrayÿ([B\x00close\x00getBytes\x00
                (*v69)->GetMethodID(v69, (jclass)v76, append, byte_1BCF0);// (Ljava/lang/String;)Ljava/lang/StringBuilder;
                (*v69)->GetMethodID(v69, (jclass)v76, &toString, &byte_1B040);// ()Ljava/lang/String;RSA
                (*v69)->NewObject(v69, (jclass)v76, (jmethodID)v77);
                v12 = 1215952980;

                (*v69)->GetMethodID(v69, (jclass)v76, append, &byte_1BD30);// (I)Ljava/lang/StringBuilder;
                v78 = (int)(*v69)->FindClass(v69, &byte_1BD50);// java/security/MessageDigest
                v79 = (int)(*v69)->GetStaticMethodID(v69, (jclass)v78, &getInstance, byte_1BD70);// (Ljava/lang/String;)Ljava/security/MessageDigest;
                v80 = (int)(*v69)->NewStringUTF(v69, &byte_1BDA2);// SHA-1updatedigest
                (*v69)->CallStaticObjectMethod(v69, (jclass)v78, (jmethodID)v79, v80);
                (*v69)->ExceptionCheck(v69);
                v13 = -925493942;
                v14 = v226;
              }
```

可以看到进行了SHA1，现在我们需要搞清楚的就是

喂给 update 的 byte[] 是谁，digest 出来的 byte[] 是如何变成最终 sign

所以这时候重新考虑Hook

上面我们已经知道调用了java层的这么多方法，因此可以每个方法都试试，我这里选择的是hook toUpperCase

下面是输出

```
========== [toUpperCase] ==========
输入: biz=1&fdsOtp={"captcha_id":"3723312ce42a04b5c0b40e605a882037","lot_number":"43d0fb9d6ceb4d34b77f6998203fb7c3","pass_token":"cd28f0a8e166dd870f589c36bc43986fde88ceef418c92b6b3e8dfa1097ce027","gen_time":"1764831091","captcha_output":"2Z76G2CapbcJxb3z0NRv6M3hvdvpPpJiZYrOHqnYCvDSbFN1VW0MwSEZ3bzVLqngN4RJMRn1V6Uvj9gAHrgeznYrystLCzuDzpheGrXmtoInaTm_JIaayivXrDqJd1xrqxIqbMWmFj8RSFvxBFc2R1M8Ape_b6WdHTrf1BeQtjEN_sdWrJTbi48cbT6ayPbqPDU8vDchMd1tgXZDBKZhoFm3ANOcDQs_SP2GqsZANRo3sZR_X2sZQhGD2EgaJvrnlfLOTcZ8kDIPGOSQyoSEyNF6R1NuWtETfRTicTxTsj8b55gDWy72e16ItCupfEoQDye8zYIaHQ1UIg4TnXxFK1aTtqGFi551e-zcyIuQnTHqMAdNtIrac0khlYn8tfPFmpkkhJCa69hR-gcGFI_qvHCeFa4ab0xjeGbRNVosEfhxp3yBbv8tbPbZ-ObfR0LN3qYS8y1JPmB3EvamKHSmU7h76fVjRfZEyM-8UhIyzz5VJit0xT970VxEGgEqJ_ZE-7FBeXmrmFycDqjAN32aZYLKfE6y9WDHtwgu2D9vbbY="}&mobile=H+FK2BFDCnb7eyJ+5Y6MZ3Du/2lwuHI3wK9RnyE+g4VKStBxb/EyvBP4mudzGTeKKZFD1PZoJarJ
OoK9xq9LPSaQ+tialKCMq++5PmJLiiEkU6kqVdtqQVs0w9BKiakZKh+HH60bCpDVGTqFbhn4i/Sf
4W+bADoG3LzJGco9Vy4=
&nonce=0-4EE56BEBDE87cdb8b25529f4c7b2f9c8158d18e3ef90b13cff9725b5d652c4&sendType=1&MOBILE-V1-PRODUCT-7D74899B338B4F348E2383970CC09991E8E8D8F2BC744EF0BEE94D76D718C089
====================================
```

此时Signature参数的生成也很清晰了

```
输入 = 参数按字母排序拼接 + "MOBILE-V1-PRODUCT-" + "7D74899B338B4F348E2383970CC09991E8E8D8F2BC744EF0BEE94D76D718C089"
signature = SHA1(输入.toUpperCase().getBytes("UTF-8"))
```

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2025-12-8 23:52*

感谢分享

## 回复 by 星落黎明 (#3)

*2025-12-9 00:17*

感谢分享

## 回复 by hacker521 (#4)

*2025-12-9 00:28*

看大佬手撕VMP

## 回复 by buluo533 (#5)

*2025-12-9 07:47*

感谢分享

## 回复 by Heiyiren123 (#6)

*2025-12-9 08:31*

感谢分享，支持！

## 回复 by wx_插曲 (#7)

*2025-12-9 09:04*

6666

## 回复 by wx-LL- (#8)

*2025-12-9 09:05*

感谢分享

## 回复 by 逍遥无极天 (#9)

*2025-12-9 09:15*

6666

## 回复 by KanXue_NG (#10)

*2025-12-9 09:32*

666

## 回复 by mb_xjdhrmck (#11)

*2025-12-9 09:42*

666

## 回复 by mb_cbgtaveo (#12)

*2025-12-9 09:58*

666666666

## 回复 by LQ6H (#13)

*2025-12-9 10:04*

666

## 回复 by guijingwen (#14)

*2025-12-9 10:14*

66

## 回复 by Ace_Heng (#15)

*2025-12-9 10:19*

看看

## 回复 by git_94730eaydwshawke-gif (#16)

*2025-12-9 10:29*

666

## 回复 by Imxz (#17)

*2025-12-9 10:48*

tql

## 回复 by mb_uvyukvot (#18)

*2025-12-9 11:05*

感谢分享

## 回复 by 不具名的悲伤 (#19)

*2025-12-9 11:15*

6

## 回复 by kxblah (#20)

*2025-12-9 11:26*

666

## 回复 by mb_euhyowpw (#21)

*2025-12-9 11:41*

11

## 回复 by mb_roiscepd (#22)

*2025-12-9 16:38*

666

## 回复 by 丶咖啡猫丶 (#23)

*2025-12-9 18:20*

666

## 回复 by jack.Chen (#24)

*2025-12-9 19:31*

666

## 回复 by 机车王子 (#25)

*2025-12-9 22:48*

你的帖子非常有用，感谢分享！

## 回复 by Friday_risa (#26)

*2025-12-9 23:23*

6666

## 回复 by 哈哈田 (#27)

*2025-12-10 08:27*

![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by 红皮西瓜 (#28)

*2025-12-10 11:45*

666

## 回复 by 29o (#29)

*2025-12-10 15:36*

111

## 回复 by everhu (#30)

*2025-12-10 15:44*

666

## 回复 by 酒仙桥之虎 (#31)

*2025-12-10 17:05*

666

## 回复 by piaoyi01 (#32)

*2025-12-11 00:35*

厉害，看看

## 回复 by myios (#33)

*2025-12-11 09:10*

666

## 回复 by mb_bhsrdtqf (#34)

*2025-12-11 09:45*

66666

## 回复 by 飞飞非反 (#35)

*2025-12-11 09:48*

66

## 回复 by MaYil (#36)

*2025-12-11 10:41*

感谢分享

## 回复 by asuralove (#37)

*2025-12-11 11:05*

666

## 回复 by 伊苏尔德 (#38)

*2025-12-11 14:55*

666666666666666666

## 回复 by mb_uzmffdbw (#39)

*2025-12-11 16:09*

666

## 回复 by Xx_gg (#40)

*2025-12-11 17:20*

6666

## 回复 by 乐活 (#41)

*2025-12-11 18:19*

66

## 回复 by 自称宅男 (#42)

*2025-12-11 19:14*

1

## 回复 by SomeMx (#43)

*2025-12-11 19:44*

666

## 回复 by 我不是卷王 (#44)

*2025-12-11 20:18*

666

## 回复 by Kill_Log (#45)

*2025-12-12 16:22*

66666666666

## 回复 by Viseris (#46)

*2025-12-12 16:23*

谢谢分享

## 回复 by kingking888 (#47)

*2025-12-12 23:35*

666

## 回复 by jdong (#48)

*2025-12-13 09:51*

你的帖子非常有用，感谢分享！

## 回复 by mb_tewbhakr (#49)

*2025-12-13 12:17*

看看

## 回复 by AK1988DA (#50)

*2025-12-13 12:50*

22

## 回复 by 小尘0000 (#51)

*2025-12-13 17:26*

666

## 回复 by Oo风之恋oO (#52)

*2025-12-13 19:47*

谢谢楼主分享

## 回复 by tubecityman (#53)

*2025-12-13 19:52*

6666

## 回复 by 上官兮唐 (#54)

*2025-12-14 14:43*

看看

## 回复 by 夫人十八岁 (#55)

*2025-12-14 17:41*

感谢分享

## 回复 by iBa0 (#56)

*2025-12-15 13:39*

x

## 回复 by 五彩斑斓的黑 (#57)

*2025-12-15 20:30*

tql

## 回复 by maomaolk (#58)

*2025-12-16 11:46*

666

## 回复 by kelb (#59)

*2025-12-16 13:05*

你的帖子非常有用，感谢分享！

## 回复 by peterchen (#60)

*2025-12-16 17:47*

多谢分享！

## 回复 by ldehua (#61)

*2025-12-17 09:03*

你的帖子非常有用，感谢分享！

## 回复 by 夜惜风雨 (#62)

*2025-12-17 09:50*

66666666666666

## 回复 by guijian (#63)

*2025-12-17 09:57*

6666

## 回复 by mb_saeucvtv (#64)

*2025-12-17 15:37*

666

## 回复 by mb_rrwegvyc (#65)

*2025-12-17 16:47*

你的帖子非常有用，感谢分享！

## 回复 by Kk一刀 (#66)

*2025-12-18 19:50*

11

## 回复 by mb_ykavguun (#67)

*2025-12-19 12:31*

1

## 回复 by 上善若水No (#68)

*2025-12-19 14:43*

1

## 回复 by mb_ynpgeaep (#69)

*2025-12-19 16:23*

1

## 回复 by mb_dagesnbs (#70)

*2025-12-20 00:03*

666

## 回复 by 温泉划水鱼 (#71)

*2025-12-21 02:02*

66

## 回复 by mb_tofujngy (#72)

*2025-12-21 13:35*

这个我刷了几千万金币，后面直接检测设备过了又封提现，最后也是过了然后直接封活动权限再也进不去金币活动了

## 回复 by mb_mgmaxnuw (#73)

*2025-12-21 14:38*

1111111111

## 回复 by mb_abajbief (#74)

*2025-12-21 18:49*

6

## 回复 by Splite_1130 (#75)

*2025-12-23 14:53*

666666

## 回复 by 毕索 (#76)

*2025-12-24 12:05*

666

## 回复 by mr2222 (#77)

*2025-12-24 17:12*

66666

## 回复 by mb_jnmxfjku (#78)

*2025-12-25 16:26*

111

## 回复 by Thehepta (#79)

*2025-12-26 13:35*

1

## 回复 by apxar (#80)

*2025-12-26 17:53*

1

## 回复 by 飆汗吉米 (#81)

*2026-1-1 15:00*

6666

## 回复 by wx_知行_889 (#82)

*2026-1-12 17:50*

555

## 回复 by xuhe123 (#83)

*2026-1-22 13:49*

6666666

## 回复 by 墨点 (#84)

*2026-1-23 05:30*

666

## 回复 by mb_cabwymdh (#85)

*2026-1-23 11:48*

888

## 回复 by GEKEZYX (#86)

*2026-1-23 13:22*

666

## 回复 by 0x530c (#87)

*2026-1-23 18:35*

6666

## 回复 by ID蝴蝶 (#88)

*2026-1-30 19:55*

666

## 回复 by huangbof (#89)

*2026-1-31 01:56*

666

## 回复 by mb_fwrpuosr (#90)

*2026-2-1 14:09*

牛的

## 回复 by mr2222 (#91)

*2026-2-1 16:00*

前段时间做了下载音频,这玩意的so 函数有些按f5会崩溃,最后还是unidbg trace![image](https://bbs.kanxue.com/view/img/face/051.gif)

## 回复 by 带篮子 (#92)

*2026-2-7 22:29*

你的帖子非常有用，感谢分享！
你的帖子非常有用，感谢分享！

## 回复 by git_11829lalueandliuliu (#93)

*2026-2-8 02:21*

666666

## 回复 by xx_dd_y (#94)

*2026-2-9 17:51*

66666

## 回复 by mb_ysikfhxt (#95)

*2026-2-10 15:57*

111

## 回复 by _MasterYoda (#96)

*2026-2-10 19:00*

666

## 回复 by spdfdfer (#97)

*2026-2-11 11:15*

666

## 回复 by mb_ghebfkzn (#98)

*2026-2-18 14:05*

。

## 回复 by git_107370xcmore (#99)

*2026-2-18 14:14*

666

## 回复 by 逆向爱好者 (#100)

*2026-2-19 13:12*

牛逼牛逼

## 回复 by lingyi223 (#101)

*2026-2-19 18:18*

666

## 回复 by kccp (#102)

*2026-2-19 18:49*

666

## 回复 by mb_fglogyec (#103)

*2026-2-24 22:08*

6666

## 回复 by wx_Y_786749 (#104)

*2026-2-28 10:44*

nice

## 回复 by 怜音 (#105)

*2026-3-6 14:20*

666

## 回复 by x0rrrrr (#106)

*2026-3-8 17:25*

1

## 回复 by mb_ygfwwoty (#107)

*2026-3-11 12:10*

666

## 回复 by 临江仙_ (#108)

*2026-3-13 03:09*

666

## 回复 by Mr.He (#109)

*2026-3-13 11:55*

666

## 回复 by mb_ifjlatem (#110)

*2026-3-13 14:22*

看大佬手撕VMP

## 回复 by mykobi (#111)

*2026-3-13 16:03*

1111

## 回复 by mb_mihutdve (#112)

*2026-3-15 17:32*

666

## 回复 by αβγδεξπ (#113)

*2026-3-17 11:17*

学习学习

## 回复 by git_14248bibinocode (#114)

*2026-3-22 18:22*

你的帖子非常有用，感谢分享！

## 回复 by 特洛伊Troye (#115)

*2026-3-24 19:18*

为你点赞！

## 回复 by Noguess9 (#116)

*2026-3-25 17:19*

66

## 回复 by mb_hfjfruhl (#117)

*2026-3-27 10:54*

666

## 回复 by ak8888 (#118)

*2026-3-28 19:35*

高手

## 回复 by 小迷糊ddd (#119)

*2026-4-7 09:16*

感谢分享，学习一下。

## 回复 by cpannn (#120)

*2026-4-23 20:32*

xuexi le

## 回复 by ADR66 (#121)

*2026-4-29 16:14*

6666666666

## 回复 by ADR66 (#122)

*2026-4-29 16:14*

66666666

## 回复 by ADR66 (#123)

*2026-4-29 16:15*

666

## 回复 by ADR66 (#124)

*2026-4-29 16:15*

666

## 回复 by ADR66 (#125)

*2026-4-29 16:15*

666

## 回复 by ADR66 (#126)

*2026-4-29 16:15*

666

## 回复 by ADR66 (#127)

*2026-4-29 16:15*

666

## 回复 by 4Chan (#128)

*2026-4-29 16:49*

学习一下

## 回复 by 4Chan (#129)

*2026-4-29 16:49*

学习一下

## 回复 by 4Chan (#130)

*2026-4-29 16:49*

学习一下

## 回复 by 4Chan (#131)

*2026-4-29 16:49*

学习一下

## 回复 by 4Chan (#132)

*2026-4-29 16:49*

666

## 回复 by qq戚导 (#133)

*2026-5-27 17:25*

感谢分享

## 回复 by 简单的简单 (#134)

*2026-5-27 22:41*

666

## 回复 by 章康 (#135)

*2026-6-14 21:45*

666

## 回复 by mb_ojftpwtm (#136)

*2026-7-17 13:59*

666

## 回复 by hanjiefang (#137)

*2026-7-21 09:20*

666
