---
title: '[原创][萌新学逆向]某漫画Status接口分析 （Java层）'
url: https://bbs.kanxue.com/thread-290056.htm
tid: 290056
author: 小Tzzz
date: '2026-02-19'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-08T10:24:01+00:00'
replies: 15
---

小米商城 3.6亿下载量, 阅读榜第10. 比较有意思的是它使用了 Retrofit用于接口的开发 (Retrofit 是 Square 公司开发的一个 类型安全 的 HTTP 客户端库，专为 Android 和 Java 设计。它本质上是 对 OkHttp 的高级封装，通过 接口注解 将 HTTP API 转换为可调用的 Java/Kotlin 接口，极大简化了网络请求的代码。)

原文链接: <https://www.yuque.com/again-719bb/pfhi8f/oee7ugfig95w4kw5>

# 0x01 登录Status接口流程

分析这个接口, 主要原因是加密字段比较多

#### 判断是否注册账号

输入手机号后, 会向`/v2/passport/phone/status`接口查询状态

![image](https://bbs.kanxue.com/upload/attach/202602/MYDUHVSRN8Y7N8Y.jpg)![image](https://bbs.kanxue.com/upload/attach/202602/FTH28MURQSX5BTS.jpg)

#### status接口请求

收集接口关键信息

```http
POST /v2/passport/phone/status HTTP/2
host: api.kkmh.com
cookie: Expires=Thu, 12-Feb-2026 13:12:24 GMT;Max-Age=86400;kk_s_t=1771394824955;Domain=.kkmh.com;Path=/
x-device: A:62a16f76968f9b5f
user-agent: Kuaikan/8.9.0/809000(Android;11;Redmi Note 8;kuaikan26;WIFI;2216*1080)
muid: cfcd208495d565ef66e7dff9f98764da
kkdid: A20260208193740873080333461684308
package-id: com.kuaikan.comic
lower-flow: No
kkflowtype: NotFree
cipher-key: Vc61Y3oqD0YGunURzUE3rIk_cxEKtSayeTKkaVwiQ_xuGn2U_YaOqsHri7ZXBEeLXXRPbuE3YbHt7opaTLcmLmSfbZ2Ao7oDsEOkeYkQYqBSw1Kwh3zObGwg3W9c6PQmjLQx4JdZIqAFmccOxeKmtqEXdu0u9MjhmkqlZmuycU8
content-type: application/x-www-form-urlencoded
content-length: 28
accept-encoding: gzip
app-info: eyJLS0RJRCI6IkEyMDI2MDIwODE5Mzc0MDg3MzA4MDMzMzQ2MTY4NDMwOCIsImFlZ2lzX2FwcF9pZCI6IjEwMDAwMDE3NzYiLCJhbmRyb2lkX2lkIjoiNjJhMTZmNzY5NjhmOWI1ZiIsImFwcF9zZWNyZXRfc2lnbiI6IjJiNmZlNTJmODM2Zjk4MThiY2ZkOTAwYTMwNzJkYTc3IiwiYmQiOiJYaWFvbWkiLCJjYSI6MCwiY3QiOjIwLCJkZXZ0IjoxLCJkcGkiOjQ0MCwiZ2VuZGVyIjowLCJoZWlnaHQiOjIyMTYsImltZWkiOiIwIiwia2tfY190IjoxNzcxMzk0ODI2NjI5LCJra19zX3QiOjE3NzEzOTQ4MjQ5NTUsIm1hYyI6IiIsIm1vZGVsIjoiUmVkbWkgTm90ZSA4Iiwib2FpZCI6ImRiMmI0ZmI1ZDFjMTEyMTYiLCJvdiI6IjExIiwicmVjX2ZvcmJpZCI6ZmFsc2UsInVzZXJfZ3JvdXAiOiJub3JtYWwiLCJ2aXNpdG9yX3NpZ24iOiJmZDVhNGM2YmMyNTIyN2EyNDQwN2MyODFmMmU5NTI4YyIsIndpZHRoIjoxMDgwfQ==

phone=sa7dfta_RpRCzVRPWo8uAQ
\```

- `v2`第二版本接口, 说明存在v1版本接口 可能加密会相对简单
- `x-device`貌似是设备相关信息
- `user-agent`由操作系统/设置信息多个参数封装
- `muid`未知
- `kkdid`未知
- `cipher-key`暂时固定
- `package-id`固定参数
- `app-info`看起来像base64
- `phone`加密数据

#### status接口响应参数

```http
HTTP/2 200
 Wed, 18 Feb 2026 06:07:05 GMT
content-type: application/json;charset=UTF-8
server: openresty
vary: Accept-Encoding
set-cookie: kk_s_t=1771394825761; Domain=.kkmh.com; Expires=Thu, 19 Feb 2026 06:07:05 GMT; Path=/
x-envoy-upstream-service-time: 11
x-request-id: 41546995-5709-4bbf-bdfd-7d007d4cfa37
content-encoding: gzip

{"code":200,"data":"nFrTAvDXUkm3X7OIqtT35Up6a2b6A5QzG2ewGnY4UUBlXscHoxYB_5pg8ScnqDauQai2hDxEaG8qaPMSU07lYg","message":"ok"}
\```

- `code`200 ok, 和http code一致, 一般我是喜欢写0的
- `data`具体信息, 被加密
- `message`code对应的解释

# 0x02 x-device参数

#### 数据格式

特征: A : [0-9a-z]{16}

```java
x-device: A:62a16f76968f9b5f
\```

#### 搜索

发现可能是A + AndroidID的拼接 `builder.a("X-Device", "A:" + k.this.sAndroidId.get());`

![image](https://bbs.kanxue.com/upload/attach/202602/YY2E4FDZEWA457H.jpg)

#### 尝试获取AndroidID

我们知道每个app的AndroidID都是不一样的, 所以尝试运行app后使用fridahook获取一下

```javascript
function getAndroidId() {
    var currentActivity = Java.use('android.app.ActivityThread').currentActivityThread().getApplication();
    var androidId = Java.use("android.provider.Settings$Secure").getString(
        currentActivity.getContentResolver(),
        "android_id"
    );

    return androidId
}

function main() {
    Java.perform(function () {
        setTimeout(function () {
            console.log("[*] Android ID: " + getAndroidId());
        }, 3000);
    });
}

setImmediate(main);
\```

控制台打印, 那基本上就做实了 `x-device: A:62a16f76968f9b5f`就是一个简单的拼接

```powershell
[*] Android ID: 62a16f76968f9b5f
\```

# 0x03 muid参数分析

#### 数据格式

特征: [0-9a-z]{32}, 看起来像 hash摘要

```java
muid: cfcd208495d565ef66e7dff9f98764da
\```

#### 定位

看起来像这个, 跟网络有关, 包括下面的 intercept也是调用同样的方法

![image](https://bbs.kanxue.com/upload/attach/202602/6KG85WXYZM539BR.jpg)

getMuid是被我rename过了, 之前叫m

```java
@NonNull
/* renamed from: m */
public static String getMuid() {
    return muid.get();
}
\```

#### 入口点确认

在函数名上按 `F`, 复制到脚本中

![image](https://bbs.kanxue.com/upload/attach/202602/2UP3E9UX33JK3ZC.jpg)

可以确定就是这个m方法获取的

```java
var Client = Java.use("com.kuaikan.app.Client");
Client["m"].implementation = function () {
    console.log(`Client.getMuid is called`);
    let result = this["m"]();
    console.log(`Client.getMuid result=${result}`);
    return result;
};
\```

![image](https://bbs.kanxue.com/upload/attach/202602/R35FNP6B4VM5D6S.jpg)

#### 分析初始化位置

继续分析它是怎么设置的, 查询引用 发现在init阶段初始化了这个类, 但是没有任何地方 set

![image](https://bbs.kanxue.com/upload/attach/202602/65ZYGPU9PHW8WXQ.jpg)

![image](https://bbs.kanxue.com/upload/attach/202602/74ZWTX8Q8KZ3GK5.jpg)

分析k类, 发现是个内部类, jadx有bug 无法正常跳转 (会显示空白)

```java
public class k extends com.kuaikan.library.base.utils.l0<String> {
    @Override // com.kuaikan.library.base.utils.l0
    /* renamed from: onInit, reason: avoid collision after fix types in other method */
    public String mo1057onInit() {
        return encryptUtil.g(Client.f38029x.get());
    }
}
\```

#### 算法还原

我们看一下 `encryptUtil.g`方法, 发现其实是个md5, 那和我们一开始分析的32位对应上了

```java
@Nullable
/* renamed from: g */
public static final String md5(String str) throws NoSuchAlgorithmException {
    if (TextUtils.isEmpty(str)) {
        return null;
    }
    try {
        MessageDigest messageDigest = MessageDigest.getInstance("MD5");
        messageDigest.update(str.getBytes());
        return a(messageDigest.digest());
    } catch (NoSuchAlgorithmException e11) {
        e11.printStackTrace();
        return null;
    }
}
\```

尝试Hook一下, 发现Hook不到, 那这就奇怪了

```java
var encryptUtil = Java.use("r40.c");
encryptUtil["g"].implementation = function (str) {
    console.log(`encryptUtil.md5 is called: str=${str}`);
    let result = this["g"](str);
    console.log(`encryptUtil.md5 result=${result}`);
    return result;
};
\```

(.... 补充:spawn启动 第一时间没Hook到, 重新保存后就正常了)

Hook下内部类$K, 发现onInit调用了 并且成功返回了值. 但是`encryptUtil.g`这个md5没反应 你这不扯犊子呢?

![image](https://bbs.kanxue.com/upload/attach/202602/97J44SVQ4EU4Q4Q.jpg)

OK虽然没成功Hook到md5(可能是bug 或者 被劫持了), 但是可以确定密文是一致的, 而明文是从`Client.f38029x.get()`获取. 我的思路是 在 onInit的时候再调用一次 get 看看明文数据

```java
/* renamed from: x */
public static com.kuaikan.library.base.utils.l0<String> f38029x;
\```

x是个静态方法, 我们直接调用即可, 需要注意的是 有另一个方法叫x, 所以需要在x前面加下划线

```java
Java.perform(function () {

    var encryptUtil = Java.use("r40.c");
    encryptUtil["g"].implementation = function (str) {
        console.log(`encryptUtil.md5 is called: str=${str}`);
        let result = this["g"](str);
        console.log(`encryptUtil.md5 result=${result}`);
        return result;
    };

    var k = Java.use("com.kuaikan.app.Client$k");
    k["onInit"].overload().implementation = function () {
        console.log(`k.onInit is called`);

        var Client = Java.use("com.kuaikan.app.Client");
        var f38024x = Client._x.value;
        console.log("[*] f38024x value: " + f38024x.get());

        let result = this["onInit"]();
        console.log(`k.onInit result=${result}`);
        return result;
    };
});
\```

![image](https://bbs.kanxue.com/upload/attach/202602/KCENPTB2WU9W4H4.jpg)

发现结果是个0, 需要验证一下, 那可以确定`muid`在未登录状态下 md5(0) , 暂时固定

![image](https://bbs.kanxue.com/upload/attach/202602/ETRX68JK2H5HJQZ.jpg)

# 0x04 app-info分析

#### 数据格式

特征: 与base64相似

```plain
app-info: eyJLS0RJRCI6IkEyMDI2MDIwODE5Mzc0MDg3MzA4MDMzMzQ2MTY4NDMwOCIsImFlZ2lzX2FwcF9pZCI6IjEwMDAwMDE3NzYiLCJhbmRyb2lkX2lkIjoiNjJhMTZmNzY5NjhmOWI1ZiIsImFwcF9zZWNyZXRfc2lnbiI6IjJiNmZlNTJmODM2Zjk4MThiY2ZkOTAwYTMwNzJkYTc3IiwiYmQiOiJYaWFvbWkiLCJjYSI6MCwiY3QiOjIwLCJkZXZ0IjoxLCJkcGkiOjQ0MCwiZ2VuZGVyIjowLCJoZWlnaHQiOjIyMTYsImltZWkiOiIwIiwia2tfY190IjoxNzcxMzk0ODI2NjI5LCJra19zX3QiOjE3NzEzOTQ4MjQ5NTUsIm1hYyI6IiIsIm1vZGVsIjoiUmVkbWkgTm90ZSA4Iiwib2FpZCI6ImRiMmI0ZmI1ZDFjMTEyMTYiLCJvdiI6IjExIiwicmVjX2ZvcmJpZCI6ZmFsc2UsInVzZXJfZ3JvdXAiOiJub3JtYWwiLCJ2aXNpdG9yX3NpZ24iOiJmZDVhNGM2YmMyNTIyN2EyNDQwN2MyODFmMmU5NTI4YyIsIndpZHRoIjoxMDgwfQ==
\```

#### 尝试base64

```json
{
	"KKDID": "A20260208193740873080333461684308",
	"aegis_app_id": "1000001776",
	"android_id": "62a16f76968f9b5f",
	"app_secret_sign": "2b6fe52f836f9818bcfd900a3072da77",
	"bd": "Xiaomi",
	"ca": 0,
	"ct": 20,
	"devt": 1,
	"dpi": 440,
	"gender": 0,
	"height": 2216,
	"imei": "0",
	"kk_c_t": 1771394826629,
	"kk_s_t": 1771394824955,
	"mac": "",
	"model": "Redmi Note 8",
	"oaid": "db2b4fb5d1c11216",
	"ov": "11",
	"rec_forbid": false,
	"user_group": "normal",
	"visitor_sign": "fd5a4c6bc25227a24407c281f2e9528c",
	"width": 1080
}
\```

### 0x05 Phone参数分析

#### 数据格式

看起来不像base64, 因为常规base64没下划线

```java
phone=sa7dfta_RpRCzVRPWo8uAQ
\```

#### 定位

直接搜索`/v2/passport/phone/status`看看有没有组装流程

![image](https://bbs.kanxue.com/upload/attach/202602/Z7G282TCHG8B4QR.jpg)

只搜索到一个关键信息, 而且还是一个接口?

```java
public interface AccountInterface {
    @NotNull
    @FormUrlEncoded
    @Encryption
    @POST("/v2/passport/phone/status")
    s90.g<StatusResponse> getSignInStatusSafe(@Field(LastSignIn.PHONE) @Nullable String phone);
}
\```

#### 注解信息(Retrofit)

这些注解看上去有点子说法的, 把整个 interface 丢给GPT

```java
@NotNull
@FormUrlEncoded
@Encryption
@POST("/v2/passport/phone/status")
\```

GPT说这个是用于 Retrofit的一个[RESTFul接口](https://www.yuque.com/again-719bb/pfhi8f/qk7zz5aoa2gpw3ce)注册, 用于动态生成

```java
Retrofit retrofit = new Retrofit.Builder()
        .baseUrl(serverApi)
        .build();

AccountInterface api = retrofit.create(AccountInterface.class);
\```

#### @Encryption注解

那么`@Encryption`这个注解就很可疑了! 跳过去发现就是一个空的接口, 而且有点怪异 使用的是 `@interface`

```java
@Target({ElementType.METHOD, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
/* loaded from: classes15.dex */
public @interface Encryption {
}
\```

那就找一下相关的引用吧. 发现只有一个地方使用, 其他都是声明.

![image](https://bbs.kanxue.com/upload/attach/202602/CRC37MEYZNZF565.jpg)

这啥玩意. 遇事不决可问AI, AI不语就砸键盘 :)

AI说这是一个 `运行时注解处理器 (implements IAnnotationProcessor)`

其作用是把注解转换成内部参数 Map `@Encryption => _internal_encryption=1`

```java
public final class a implements IAnnotationProcessor {
    @Override // com.kuaikan.library.net.annotation.IAnnotationProcessor
    @Nullable
    public Map<String, String> a(@NotNull List<? extends Annotation> annotation) {
        Intrinsics.checkNotNullParameter(annotation, "annotation");
        LinkedHashMap linkedHashMap = new LinkedHashMap();
        for (Annotation annotation2 : annotation) {
            if (annotation2 instanceof Encryption) {
                linkedHashMap.put("_internal_encryption", "1");
            }
            if (annotation2 instanceof UnEncryption) {
                linkedHashMap.put("_internal_un_encryption", "1");
            }
        }
        return linkedHashMap;
    }
}
\```

那就搜一下`_internal_encryption`看看有没有具体实现喽

![image](https://bbs.kanxue.com/upload/attach/202602/ZMKPR54NBYPQ6ED.jpg)

最终定位`implements okhttp3.Interceptor`

```java
import okhttp3.Interceptor;

public final class d implements Interceptor {

    @Override // okhttp3.Interceptor
    @NotNull
    public okhttp3.Response intercept(@NotNull Interceptor.Chain chain) throws IOException {
        Intrinsics.checkNotNullParameter(chain, "chain");
        Request request = chain.request();
        sa0.e eVar = sa0.e.f106281a;
        String str = (String) eVar.d(request, "_internal_encryption");
        if (!TextUtils.isEmpty((String) eVar.d(request, "_internal_un_encryption"))) {
            return chain.proceed(request);
        }
        if (!TextUtils.isEmpty(str) || this.aesEncryptionALl) {
            request = l(request);
        }
        okhttp3.Response responseProceed = chain.proceed(request);
        return (responseProceed.isSuccessful() && (!TextUtils.isEmpty(str) || this.aesEncryptionALl)) ? e(responseProceed) : responseProceed;
    }
}
\```

可以看到`(String) eVar.d(request, "_internal_encryption");`貌似是取值 (可能就是上面put的值)

`!TextUtils.isEmpty(str) || this.aesEncryptionALl`这个应该就是判断了

使用frida Hook一下验证是否正确

```javascript
Java.perform(function () {

  //public okhttp3.Response intercept(@NotNull Interceptor.Chain chain)
  var d = Java.use("ia0.d");
  d["intercept"].implementation = function (chain) {
      var Request = chain.request();
      var url = Request.url();
      console.log(`d.intercept is called: chain.url=${url}`);
      let result = this["intercept"](chain);
      console.log(`d.intercept result=${result}`);
      return result;
  };

  //eVar.d(request, "_internal_encryption")
  var e = Java.use("sa0.e");
  e["d"].implementation = function (request, key) {
      console.log(`e.d is called: request=${request}, key=${key}`);
      let result = this["d"](request, key);
      console.log(`e.d result=${result}`);
      return result;
  };
});
\```

可以看到 `e.d result`第一次进入是1

```java
d.intercept is called: chain.url=https://api.kkmh.com/v2/passport/phone/status
e.d is called: request=Request{method=POST, url=https://api.kkmh.com/v2/passport/phone/status, headers=[kk_net_inner_call_id:208, Cookie:Expires=Thu, 12-Feb-2026 13:12:24 GMT;Max-Age=86400;kk_s_t=1771435823281;Domain=.kkmh.com;Path=/, X-Device:A:62a16f76968f9b5f, User-Agent:Kuaikan/8.9.0/809000(Android;11;Redmi Note 8;kuaikan26;WIFI;2216*1080), Muid:cfcd208495d565ef66e7dff9f98764da, KKDID:A20260208193740873080333461684308, Package-Id:com.kuaikan.comic, Lower-Flow:No, kkFlowType:NotFree]}, key=_internal_encryption
e.d result=1
e.d is called: request=Request{method=POST, url=https://api.kkmh.com/v2/passport/phone/status, headers=[kk_net_inner_call_id:208, Cookie:Expires=Thu, 12-Feb-2026 13:12:24 GMT;Max-Age=86400;kk_s_t=1771435823281;Domain=.kkmh.com;Path=/, X-Device:A:62a16f76968f9b5f, User-Agent:Kuaikan/8.9.0/809000(Android;11;Redmi Note 8;kuaikan26;WIFI;2216*1080), Muid:cfcd208495d565ef66e7dff9f98764da, KKDID:A20260208193740873080333461684308, Package-Id:com.kuaikan.comic, Lower-Flow:No, kkFlowType:NotFree]}, key=_internal_un_encryption
e.d result=null
e.d is called: request=Request{method=POST, url=https://api.kkmh.com/v2/passport/phone/status, headers=[kk_net_inner_call_id:208, Cookie:Expires=Thu, 12-Feb-2026 13:12:24 GMT;Max-Age=86400;kk_s_t=1771435823281;Domain=.kkmh.com;Path=/, X-Device:A:62a16f76968f9b5f, User-Agent:Kuaikan/8.9.0/809000(Android;11;Redmi Note 8;kuaikan26;WIFI;2216*1080), Muid:cfcd208495d565ef66e7dff9f98764da, KKDID:A20260208193740873080333461684308, Package-Id:com.kuaikan.comic, Lower-Flow:No, kkFlowType:NotFree, CIPHER-KEY:EeMyZKUJNuM5nlVgTM2hNhgwBiBChXTlXdzMGLwYVC4k1pT3Q4RQXTgMdSNXoVdzDCWaa4Fp9MlPNYhsuiflDImjD752DGc9DvJFldC-ctn9yDZDMoWCZWtoy_qcCCcDOkd5FE6ZBldWHXmrNjlVeftBhEPUXVA4hq3sKrzBv9c, Content-Type:application/x-www-form-urlencoded, Content-Length:28, Host:api.kkmh.com, Connection:Keep-Alive, Accept-Encoding:gzip]}, key=App-Info
e.d result=null
d.intercept result=Response{protocol=h2, code=200, message=, url=https://api.kkmh.com/v2/passport/phone/status}
\```

#### 请求链路分析

那现在基本可以确定加密逻辑在`l(request);`中, 我们来分析一下 l获取 Request.Method 然后调用不同的逻辑分支. 如果是get调用h, 否则调用j

```java
public final class d implements Interceptor {

    public final Request l(Request request) {
        String lowerCase = request.method().toLowerCase();
        Intrinsics.checkNotNullExpressionValue(lowerCase, "toLowerCase(...)");
        return Intrinsics.areEqual(lowerCase, "get") ? h(request) : j(request);
    }

    public final Request h(Request request) {
        Set<String> setQueryParameterNames = request.url().queryParameterNames();
        Request.Builder builderNewBuilder = request.newBuilder();
        HttpUrl.Builder builderNewBuilder2 = request.url().newBuilder();
        for (String str : setQueryParameterNames) {
            builderNewBuilder2.removeAllQueryParameters(str);
            String strQueryParameter = request.url().queryParameter(str);
            if (strQueryParameter == null) {
                strQueryParameter = "";
            }
            builderNewBuilder2.addQueryParameter(str, f(strQueryParameter));
        }
        return builderNewBuilder.url(builderNewBuilder2.build()).addHeader("CIPHER-KEY", n()).removeHeader("_internal_encryption").build();
    }

    public final Request j(Request request) {
        RequestBody requestBodyBody = request.body();
        if (requestBodyBody == null) {
            return request;
        }
        return request.newBuilder().method(request.method(), requestBodyBody instanceof FormBody ? g((FormBody) requestBodyBody) : requestBodyBody instanceof MultipartBody ? i((MultipartBody) requestBodyBody) : k(requestBodyBody)).addHeader("CIPHER-KEY", n()).removeHeader("_internal_encryption").build();
    }
}
\```

那我们是这个POST, 所以直接看j就好了. 让AI帮我们格式化一下

```java
public final Request j(Request request) {
    RequestBody requestBodyBody = request.body();

    // 如果 RequestBody 为 null，直接返回原 Request
    if (requestBodyBody == null) {
        return request;
    }

    // 构建新 Request 对象
    return request.newBuilder()
        .method(
            request.method(),
            // 根据 Body 类型选择不同的处理方法
            requestBodyBody instanceof FormBody
                ? g((FormBody) requestBodyBody)
                : requestBodyBody instanceof MultipartBody
                    ? i((MultipartBody) requestBodyBody)
                    : k(requestBodyBody)
        )
        .addHeader("CIPHER-KEY", n())      // 添加新 Header
        .removeHeader("_internal_encryption")  // 移除指定 Header
        .build();
}
\```

那我们content-type => `application/x-www-form-urlencoded`(FormBody) 走 g方法

```java
cipher-key: Vc61Y3oqD0YGunURzUE3rIk_cxEKtSayeTKkaVwiQ_xuGn2U_YaOqsHri7ZXBEeLXXRPbuE3YbHt7opaTLcmLmSfbZ2Ao7oDsEOkeYkQYqBSw1Kwh3zObGwg3W9c6PQmjLQx4JdZIqAFmccOxeKmtqEXdu0u9MjhmkqlZmuycU8
content-type: application/x-www-form-urlencoded
\```

g方法就是获取http body 中的value进行处理后赋值回去, 然后重新生成一个新的RequestBody

```java
public final RequestBody g(FormBody formBody) {
    int size = formBody.size();
    if (size <= 0) {
        return null;
    }
    FormBody.Builder builder = new FormBody.Builder(null, 1, null);
    for (int i11 = 0; i11 < size; i11++) {
        String strF = f(formBody.value(i11));
        if (strF == null || strF.length() == 0) {
            builder.addEncoded(formBody.name(i11), formBody.value(i11));
        } else {
            builder.addEncoded(formBody.name(i11), strF);
        }
    }
    return builder.build();
}
\```

再来看一下f方法

```java
public final String f(String data) {
    if (!TextUtils.isEmpty(data)) {
        try {
            com.kuaikan.library.base.utils.e eVar = com.kuaikan.library.base.utils.e.f59696a;
            Charset charset = Charsets.UTF_8;
            byte[] bytes = data.getBytes(charset);
            Intrinsics.checkNotNullExpressionValue(bytes, "getBytes(...)");
            byte[] bytes2 = m().getBytes(charset);
            Intrinsics.checkNotNullExpressionValue(bytes2, "getBytes(...)");
            return eVar.h(q.aes(bytes, bytes2), 11);
        } catch (Exception e11) {
            if (n0.sDebugBuild) {
                n0.f("EncryptionInterceptor", e11, e11.getMessage());
            }
        }
    }
    return data;
}
\```

#### aes加密

发现`q.aes`就是aes加密

```java
public final class q {

    /* renamed from: d, reason: from kotlin metadata */
    @NotNull
    public static final IvParameterSpec AES_IV;

    static {
        byte[] bytes = "0102030405060708".getBytes(Charsets.UTF_8);
        Intrinsics.checkNotNullExpressionValue(bytes, "getBytes(...)");
        AES_IV = new IvParameterSpec(bytes);
        XOR_KEY = "D0ICClxQD1UCXA4QUV4RUV1eUFg";
    }

    @Nullable
    @JvmStatic
    @org.jetbrains.annotations.Nullable
    /* renamed from: e */
    public static final byte[] aes(@org.jetbrains.annotations.Nullable byte[] data, @org.jetbrains.annotations.Nullable byte[] key) throws NoSuchPaddingException, NoSuchAlgorithmException, InvalidKeyException, InvalidAlgorithmParameterException {
        if (data == null || data.length == 0) {
            return null;
        }
        SecretKeySpec secretKeySpec = new SecretKeySpec(key, "AES/CBC/PKCS5Padding");
        Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
        cipher.init(1, secretKeySpec, AES_IV);
        return cipher.doFinal(data);
    }
}
\```

使用Hook的方式获取aes的初始数据. data/key都是byte数组 需要转换一下

```java
Java.perform(function () {

    var StringCls = Java.use("java.lang.String");
    function bytesToString(bytes) {
        return StringCls.$new(bytes, "UTF-8");
    }

    var q = Java.use("com.kuaikan.library.base.utils.q");
    q["e"].overload('[B', '[B').implementation = function (data, key) {
        console.log(`q.aes is called: data=${bytesToString(data)}, key=${bytesToString(key)}`);
        let result = this["e"](data, key);
        console.log(`q.aes result=${result}`);
        return result;
    };
});
\```

打印结果, 我们发现key是非固定值每次重新启动就动态生成, 而data也被拼接了 +86 的国际区号

data/key/padding都有了 IV初始化向量就是static块中的明文`0102030405060708`我们来验证一下

```java
q.aes is called: data=+86-18511111111, key=fElKNAjHippHDDKt
q.aes result=56,108,-12,54,-53,-95,125,57,40,48,60,30,-68,-112,-41,99

//第二次启动app
q.aes is called: data=+86-18511111111, key=rbwfNCIIhiqwknbz
\```

因为重启了app, 需要重新发包phone参数验证

```java
POST /v2/passport/phone/status HTTP/2
host: api.kkmh.com
cookie: Expires=Thu, 12-Feb-2026 13:12:24 GMT;Max-Age=86400;kk_s_t=1771480597356;Domain=.kkmh.com;Path=/
x-device: A:62a16f76968f9b5f
user-agent: Kuaikan/8.9.0/809000(Android;11;Redmi Note 8;kuaikan26;WIFI;2216*1080)
muid: cfcd208495d565ef66e7dff9f98764da
kkdid: A20260208193740873080333461684308
package-id: com.kuaikan.comic
lower-flow: No
kkflowtype: NotFree
cipher-key: ES42iEuWu4-nWlRHonw05L4PfLmMM5w4Ymmliz1nkgb39ayBDvwmpQX46wzwZBunz6lB-78eVblcJRWqJnZtu0FUM_1Lnd_BXUINhPhvMMrBw11of-YLMlEpK6Z0S_y20HCJ0dS3bJIg1NY5hW4JmRt4bx8qtT22sTvZRg81h2U
content-type: application/x-www-form-urlencoded
content-length: 28
accept-encoding: gzip
app-info: eyJLS0RJRCI6IkEyMDI2MDIwODE5Mzc0MDg3MzA4MDMzMzQ2MTY4NDMwOCIsImFlZ2lzX2FwcF9pZCI6IjEwMDAwMDE3NzYiLCJhbmRyb2lkX2lkIjoiNjJhMTZmNzY5NjhmOWI1ZiIsImFwcF9zZWNyZXRfc2lnbiI6ImQ5NDc1MTM4OWNmNWIyMzE3MDQ1YjFlZjIyOTJjODgzIiwiYmQiOiJYaWFvbWkiLCJjYSI6MCwiY3QiOjIwLCJkZXZ0IjoxLCJkcGkiOjQ0MCwiZ2VuZGVyIjowLCJoZWlnaHQiOjIyMTYsImltZWkiOiIwIiwia2tfY190IjoxNzcxNDgwNjAwMDQwLCJra19zX3QiOjE3NzE0ODA1OTczNTYsIm1hYyI6IiIsIm1vZGVsIjoiUmVkbWkgTm90ZSA4Iiwib2FpZCI6ImRiMmI0ZmI1ZDFjMTEyMTYiLCJvdiI6IjExIiwicmVjX2ZvcmJpZCI6ZmFsc2UsInVzZXJfZ3JvdXAiOiJub3JtYWwiLCJ2aXNpdG9yX3NpZ24iOiJmZDVhNGM2YmMyNTIyN2EyNDQwN2MyODFmMmU5NTI4YyIsIndpZHRoIjoxMDgwfQ==

phone=nsWCS-7gH2gfEzaRC4k_vA
\```

#### base64_safe

而 `eVar.h`则是flag为11的base64

```java
@NonNull
@NotNull
public final String h(@Nullable byte[] bytes, int flag) {
    if (bytes == null || bytes.length == 0) {
        return "";
    }
    byte[] bArrEncode = Base64.encode(bytes, flag);
    Intrinsics.checkNotNullExpressionValue(bArrEncode, "encode(...)");
    return new String(bArrEncode, Charsets.UTF_8);
}
\```

问一下ai Base64.encode flag. 11 那不就是 8 + 2 + 1

![image](https://bbs.kanxue.com/upload/attach/202602/UNBXAZ6UTZCAXCX.jpg)

#### 加密流程逻辑梳理与信息收集

```java
okhttp3.Response intercept
└── 获取 Request.header._internal_un_encryption
    └── 如果存在 则直接正常发起请求
└── 获取 Request.header._internal_encryption
    └── 如果存在 则重新生成新的加密 RequestBody
        └── 判断Request.Method
            └── aes加密value
            └── base64 flag 11编码 value
\```

参数收集

```java
phone=nsWCS-7gH2gfEzaRC4k_vA
key=rbwfNCIIhiqwknbz			//非固定参数, 每次app启动会变化
data=+86-18511111111
iv=0102030405060708
\```

#### py脚本编写

```java
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64

def aes_cbc_pkcs5_encrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    if data is None or len(data) == 0:
        return None

    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(data, AES.block_size))
    return encrypted

def aes_cbc_pkcs5_decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    if not data:
        return b""

    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(data)

    return unpad(decrypted, AES.block_size)

def base64encode_urlsafe_no_padding(data: bytes) -> str:
    if not data:
        return ""

    b64 = base64.urlsafe_b64encode(data).decode()
    return b64.rstrip("=")

# binascii.Error: Incorrect padding
def base64decode_urlsafe_no_padding(b64_text: str) -> bytes:
    if not b64_text:
        return b""

    padding = 4 - (len(b64_text) % 4)
    if padding != 4:
        b64_text += "=" * padding

    return base64.urlsafe_b64decode(b64_text)

def encrypt_hbody_map_values(data_map: dict, key: bytes, iv: bytes) -> dict:
    """
    对字典中的所有value值进行加密操作

    Args:
        data_map (dict): 包含待加密数据的字典
        key (bytes): AES加密密钥
        iv (bytes): AES加密初始向量

    Returns:
        dict: 包含加密后数据的字典
    """
    if not data_map:
        return {}

    encrypted_map = {}

    for key_name, value in data_map.items():
        if isinstance(value, str):
            # 将字符串转换为bytes
            value_bytes = value.encode('utf-8')
        elif isinstance(value, bytes):
            value_bytes = value
        else:
            # 其他类型转换为字符串再处理
            value_bytes = str(value).encode('utf-8')

        # 执行加密步骤
        step1 = aes_cbc_pkcs5_encrypt(value_bytes, key, iv)
        if step1 is not None:
            step2 = base64encode_urlsafe_no_padding(step1)
            encrypted_map[key_name] = step2
        else:
            encrypted_map[key_name] = None

    return encrypted_map

if __name__ == "__main__":

    data_map = {
        "phone": "+86-18511111111",
    }
    key = b"rbwfNCIIhiqwknbz"
    iv = b"0102030405060708"
    encrypted_map = encrypt_hbody_map_values(data_map, key, iv)
    print(encrypted_map)
\```

![image](https://bbs.kanxue.com/upload/attach/202602/M9KQ5B8URHM8FCT.jpg)

# 0x06 kkdid参数分析

#### 数据格式

33位, 有点像 前缀的A + 个32位的时间格式?

```java
kkdid: A20260208193740873080333461684308
\```

#### 定位

![image](https://bbs.kanxue.com/upload/attach/202602/HPFYJE2S8NVKXSQ.jpg)

找了一圈, 发现这个RequestInterceptor 最可疑

```java
public final class RequestInterceptor implements ICommonHeaderInterceptor, INetFilter {
    @Override // com.kuaikan.library.net.interceptor.INetFilter
    @Nullable
    public a a() {
        return a.INSTANCE.a().b(true).a(DomainConfig.INSTANCE.a());
    }

    @Override // com.kuaikan.library.net.interceptor.INetInterceptor
    @Nullable
    public NetResponse b(@NotNull IChain chain) throws IOException {
        Intrinsics.checkNotNullParameter(chain, "chain");
        pa0.a builder = chain.getRequestInfo().getBuilder();
        c(chain, builder);
        d(builder);
        if (!TextUtils.isEmpty(Client.getDevice())) {
            builder.j("X-Device", Client.getDevice());
        }
        if (!TextUtils.isEmpty(Client.getUserAgent())) {
            builder.j("User-Agent", Client.getUserAgent());
        }
        if (!TextUtils.isEmpty(Client.getMuid())) {
            builder.j("Muid", Client.getMuid());
        }
        String strB = com.kuaikan.user.kkdid.a.b();
        if (!TextUtils.isEmpty(strB)) {
            builder.j(KKCollectTrack.PARAM_KKDID, strB);
        }
        if (d.a() != null) {
            builder.j("Package-Id", d.e());
        }
        if (e.e()) {
            builder.j(KKCollectTrack.PARAM_IS_GRAY, "1");
        }
        builder.j("Lower-Flow", tx.a.a().f() ? "Yes" : "No");
        builder.j("kkFlowType", b.f103827e.e());
        return chain.a(builder.c());
    }

}
\```

找下strB的生成

```java
package com.kuaikan.user.kkdid;
public final class a implements Handler.Callback, ActivityRecordMgr.AppVisibleChangeListener {
    public static final String b() {
        String strB = ur0.a.f109522a.b();
        return strB == null ? "" : strB;
    }
}

package ur0;
public final class a {
    /* renamed from: a, reason: collision with root package name */
    @NotNull
    public static final a f109522a = new a();

    @Nullable
    public final String b() {
        return kvOperation.getString("key_kkdid", "");
    }
}
\```

看了下 ur0.a这个类很多 key/value的 getset操作. 感觉是做持久化的, 那就麻烦了 那这个kkdid是什么时候设置的呢?

```java
package ur0;

import android.content.Context;
import android.text.TextUtils;
import com.kuaikan.library.kv.api.IKvOperation;
import com.kuaikan.library.kv.api.KvMode;
import com.kuaikan.library.tracker.util.PreferenceStorageUtil;
import com.kuaishou.weapon.p0.t;
import com.kwad.components.offline.api.tk.model.report.TKDownloadReason;
import com.kwad.sdk.core.response.model.SdkConfigData;
import com.umeng.analytics.pro.bm;
import com.umeng.analytics.pro.f;
import h80.b;
import java.util.List;
import kotlin.Metadata;
import kotlin.jvm.JvmStatic;
import kotlin.jvm.internal.SourceDebugExtension;
import kotlin.text.r;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;
import r40.d;

/* compiled from: ClientInfoPreferenceUtils.kt */
@Metadata(d1 = {"\u0000@\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\u0002\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u000f\n\u0002\u0010\t\n\u0002\b\u0013\n\u0002\u0018\u0002\n\u0002\b\u0005\bÆ\u0002\u0018\u00002\u00020\u0001B\t\b\u0002¢\u0006\u0004\b\u0002\u0010\u0003J\u0019\u0010\u0007\u001a\u00020\u00062\b\u0010\u0005\u001a\u0004\u0018\u00010\u0004H\u0007¢\u0006\u0004\b\u0007\u0010\bJ\u0015\u0010\u000b\u001a\u00020\u00062\u0006\u0010\n\u001a\u00020\t¢\u0006\u0004\b\u000b\u0010\fJ\r\u0010\r\u001a\u00020\t¢\u0006\u0004\b\r\u0010\u000eJ\u001f\u0010\u0013\u001a\u00020\u00062\b\u0010\u0010\u001a\u0004\u0018\u00010\u000f2\u0006\u0010\u0012\u001a\u00020\u0011¢\u0006\u0004\b\u0013\u0010\u0014J\u0017\u0010\u0015\u001a\u00020\u00112\b\u0010\u0010\u001a\u0004\u0018\u00010\u000f¢\u0006\u0004\b\u0015\u0010\u0016J\u0017\u0010\u0018\u001a\u00020\u00062\b\u0010\u0017\u001a\u0004\u0018\u00010\u0004¢\u0006\u0004\b\u0018\u0010\bJ\u000f\u0010\u0019\u001a\u0004\u0018\u00010\u0004¢\u0006\u0004\b\u0019\u0010\u001aJ\r\u0010\u001b\u001a\u00020\u0004¢\u0006\u0004\b\u001b\u0010\u001aJ\u0019\u0010\u001c\u001a\u0004\u0018\u00010\u00042\b\u0010\u0010\u001a\u0004\u0018\u00010\u000f¢\u0006\u0004\b\u001c\u0010\u001dJ!\u0010\u001f\u001a\u00020\u00062\b\u0010\u0010\u001a\u0004\u0018\u00010\u000f2\b\u0010\u001e\u001a\u0004\u0018\u00010\u0004¢\u0006\u0004\b\u001f\u0010 J\u0017\u0010\"\u001a\u00020!2\b\u0010\u0010\u001a\u0004\u0018\u00010\u000f¢\u0006\u0004\b\"\u0010#J\u0015\u0010%\u001a\u00020\u00062\u0006\u0010$\u001a\u00020\t¢\u0006\u0004\b%\u0010\fJ\r\u0010&\u001a\u00020\t¢\u0006\u0004\b&\u0010\u000eJ\u001f\u0010(\u001a\u00020\u00062\b\u0010\u0010\u001a\u0004\u0018\u00010\u000f2\u0006\u0010'\u001a\u00020!¢\u0006\u0004\b(\u0010)J\u000f\u0010*\u001a\u0004\u0018\u00010\u0004¢\u0006\u0004\b*\u0010\u001aJ\u0017\u0010,\u001a\u00020\u00062\b\u0010+\u001a\u0004\u0018\u00010\u0004¢\u0006\u0004\b,\u0010\bJ\u0015\u0010-\u001a\u00020\u00112\u0006\u0010\u001e\u001a\u00020!¢\u0006\u0004\b-\u0010.J\r\u0010/\u001a\u00020\u0006¢\u0006\u0004\b/\u0010\u0003R\"\u00101\u001a\u00020\u00118\u0006@\u0006X\u0086\u000e¢\u0006\u0012\n\u0004\b*\u00100\u001a\u0004\b1\u00102\"\u0004\b3\u00104R\u0017\u00109\u001a\u0002058\u0006¢\u0006\f\n\u0004\b6\u00107\u001a\u0004\b6\u00108¨\u0006:"}, d2 = {"Lur0/a;", "", "<init>", "()V", "", TKDownloadReason.KSAD_TK_MD5, "", t.f70917a, "(Ljava/lang/String;)V", "", "pollingInterval", "o", "(I)V", "f", "()I", "Landroid/content/Context;", f.X, "", "enable", "p", "(Landroid/content/Context;Z)V", "j", "(Landroid/content/Context;)Z", "str", "r", bm.aM, "()Ljava/lang/String;", "a", "e", "(Landroid/content/Context;)Ljava/lang/String;", "time", t.f70920d, "(Landroid/content/Context;Ljava/lang/String;)V", "", t.f70936t, "(Landroid/content/Context;)J", "state", "q", "g", "reportTime", t.f70924h, "(Landroid/content/Context;J)V", t.f70928l, "id", t.f70929m, "i", "(J)Z", "s", "Z", "isTodayFirstOpenApp", "()Z", "setTodayFirstOpenApp", "(Z)V", "Lcom/kuaikan/library/kv/api/IKvOperation;", "c", "Lcom/kuaikan/library/kv/api/IKvOperation;", "()Lcom/kuaikan/library/kv/api/IKvOperation;", "kvOperation", "LibraryClientInfo_release"}, k = 1, mv = {1, 9, 0}, xi = 48)
@SourceDebugExtension
/* loaded from: classes20.dex */
public final class a {

    /* renamed from: b, reason: collision with root package name and from kotlin metadata */
    public static boolean isTodayFirstOpenApp;

    /* renamed from: a, reason: collision with root package name */
    @NotNull
    public static final a f109522a = new a();

    /* renamed from: c, reason: collision with root package name and from kotlin metadata */
    @NotNull
    public static final IKvOperation kvOperation = b.f88628a.a(PreferenceStorageUtil.PREFERENCES_NAME, KvMode.SINGLE_PROCESS_MODE);

    @JvmStatic
    public static final void k(@Nullable String md5) {
        kvOperation.putString("key_kkmh_apk_md5", md5).apply();
    }

    @NotNull
    public final String a() {
        List listSplit$default;
        String string = kvOperation.getString("key_kkmh_apk_md5", "");
        if (TextUtils.isEmpty(string)) {
            return "";
        }
        String[] strArr = (string == null || (listSplit$default = r.split$default((CharSequence) string, new String[]{","}, false, 0, 6, (Object) null)) == null) ? null : (String[]) listSplit$default.toArray(new String[0]);
        return (strArr == null || strArr.length <= 0) ? "" : strArr[0];
    }

    @Nullable
    public final String b() {
        return kvOperation.getString("key_kkdid", "");
    }

    @NotNull
    public final IKvOperation c() {
        return kvOperation;
    }

    public final long d(@Nullable Context context) {
        if (context == null) {
            return 0L;
        }
        return kvOperation.getLong("key_last_dau_tracker_time", 0L);
    }

    @Nullable
    public final String e(@Nullable Context context) {
        return context == null ? "" : kvOperation.getString("key_last_failure_dau_tracker_time", "");
    }

    public final int f() {
        return kvOperation.getInt("polling_interval", SdkConfigData.DEFAULT_REQUEST_INTERVAL) * 1000;
    }

    public final int g() {
        return kvOperation.getInt("key_notification_state", -1);
    }

    @Nullable
    public final String h() {
        return kvOperation.getString("key_webview_useragent", "");
    }

    public final boolean i(long time) {
        IKvOperation iKvOperation = kvOperation;
        long j11 = iKvOperation.getLong("KEY_FIRST_START_APP_DAY", -1L);
        if (j11 != -1) {
            return d.M(time, j11);
        }
        iKvOperation.putLong("KEY_FIRST_START_APP_DAY", System.currentTimeMillis());
        return true;
    }

    public final boolean j(@Nullable Context context) {
        if (context == null) {
            return false;
        }
        return kvOperation.getBoolean("key_enable_net_accelerate", true);
    }

    public final void l(@Nullable Context context, @Nullable String time) {
        if (context == null) {
            return;
        }
        IKvOperation iKvOperation = kvOperation;
        iKvOperation.putString("key_last_failure_dau_tracker_time", time);
        iKvOperation.apply();
    }

    public final void m(@Nullable String id2) {
        kvOperation.putString("key_kkdid", id2).apply();
    }

    public final void n(@Nullable Context context, long reportTime) {
        if (context == null) {
            return;
        }
        IKvOperation iKvOperation = kvOperation;
        iKvOperation.putLong("key_last_dau_tracker_time", reportTime);
        iKvOperation.apply();
    }

    public final void o(int pollingInterval) {
        IKvOperation iKvOperation = kvOperation;
        iKvOperation.putInt("polling_interval", pollingInterval);
        iKvOperation.apply();
    }

    public final void p(@Nullable Context context, boolean enable) {
        if (context == null) {
            return;
        }
        IKvOperation iKvOperation = kvOperation;
        iKvOperation.putBoolean("key_enable_net_accelerate", enable);
        iKvOperation.apply();
    }

    public final void q(int state) {
        kvOperation.putInt("key_notification_state", state).apply();
    }

    public final void r(@Nullable String str) {
        kvOperation.putString("key_webview_useragent", str).apply();
    }

    public final void s() {
        b bVar = b.f88628a;
        if (bVar.e().getLong("KEY_OPEN_APP_TIME", -1L) != -1) {
            isTodayFirstOpenApp = !d.M(System.currentTimeMillis(), r5);
            bVar.e().putLong("KEY_OPEN_APP_TIME", System.currentTimeMillis());
        } else {
            isTodayFirstOpenApp = true;
            bVar.e().putLong("KEY_OPEN_APP_TIME", System.currentTimeMillis());
        }
    }
}
\```

搜一下这个 key 对应的put操作, 再找下m的引用 没找到...

![image](https://bbs.kanxue.com/upload/attach/202602/QM2QF9NX2H2TCBS.jpg)

![image](https://bbs.kanxue.com/upload/attach/202602/FYVCSJ899JS9N44.jpg)

Hook下这个m方法, 发现还报错了... 头疼 很明显Java.use 触发了它的 classLoad中 `<cinit>`代码的调用, 这里面有环境依赖, 如果延时Hook的话估计不一定能Hook到.

```javascript
Java.perform(function () {

  var a = Java.use("ur0.a");
  a["m"].implementation = function (id2) {
    console.log(`a.m is called: id2=${id2}`);
    this["m"](id2);
  };
});
\```

```javascript
Process crashed: java.lang.NullPointerException: Attempt to invoke virtual method 'void android.app.Application.registerActivityLifecycleCallbacks(android.app.Application$ActivityLifecycleCallbacks)' on a null object reference

***
FATAL EXCEPTION: main
Process: com.kuaikan.comic, PID: 8116
java.lang.ExceptionInInitializerError
        at com.kuaikan.library.base.manager.ActivityRecordMgr.w(ActivityRecordMgr.java:1)
        at com.kuaikan.library.base.BaseApplication.<init>(BaseApplication.java:6)
        at com.kuaikan.KKMHApp.<init>(KKMHApp.java:1)
        at java.lang.Class.newInstance(Native Method)
        at android.app.AppComponentFactory.instantiateApplication(AppComponentFactory.java:76)
        at androidx.core.app.CoreComponentFactory.instantiateApplication(CoreComponentFactory.java:1)
        at android.app.Instrumentation.newApplication(Instrumentation.java:1159)
        at android.app.LoadedApk.makeApplication(LoadedApk.java:1240)
        at android.app.ActivityThread.handleBindApplication(ActivityThread.java:6957)
        at android.app.ActivityThread.handleBindApplication(Native Method)
        at android.app.ActivityThread.access$1600(ActivityThread.java:257)
        at android.app.ActivityThread$H.handleMessage(ActivityThread.java:1993)
        at android.os.Handler.dispatchMessage(Handler.java:106)
        at android.os.Looper.loop(Looper.java:236)
        at android.app.ActivityThread.main(ActivityThread.java:8057)
        at java.lang.reflect.Method.invoke(Native Method)
        at com.android.internal.os.RuntimeInit$MethodAndArgsCaller.run(RuntimeInit.java:656)
        at com.android.internal.os.ZygoteInit.main(ZygoteInit.java:967)
Caused by: java.lang.NullPointerException: Attempt to invoke virtual method 'void android.app.Application.registerActivityLifecy.registerActivityLifecycleCallbacks(android.app.Application$ActivityLifecycleCallbacks)' on a null object reference
        at com.kuaikan.library.base.manager.ActivityRecordMgr.<init>(ActivityRecordMgr.java:11)
        at com.kuaikan.library.base.manager.ActivityRecordMgr.<init>(ActivityRecordMgr.java:1)
        at com.kuaikan.library.base.manager.ActivityRecordMgr$c.<clinit>(ActivityRecordMgr.java:4)
        ... 18 more
\```

只能找找其他方案, 定位a类的引用看看有没有线索.

![image](https://bbs.kanxue.com/upload/attach/202602/MRKERXHEUTG96G8.jpg)

这就奇了怪了 m明明有调用, 能正常跳过去. 但是反向 m 找就找不到, bug都让我碰到了???

![image](https://bbs.kanxue.com/upload/attach/202602/9GGPD4FMNTVEQ3Y.jpg)

后续我又分析了一下, 难道说这种单例模式 不能直接通过x反向找? 直接对 `f109522a`按x就能找到 (说白了 字符串匹配呗?)

```javascript
public final class a {

    /* renamed from: b, reason: collision with root package name and from kotlin metadata */
    public static boolean isTodayFirstOpenApp;

    /* renamed from: a, reason: collision with root package name */
    @NotNull
    public static final a f109522a = new a();

    public final void m(@Nullable String id2) {
        kvOperation.putString("key_kkdid", id2).apply();
    }

}
\```

![image](https://bbs.kanxue.com/upload/attach/202602/E7SAWCUHNKM6GXR.jpg)

#### KkdidResponse

KkdidResponse可能是来自网络, 先Hook这个内部类看下对不对

```java
public static final class C0957a implements Callback<KkdidResponse> {
    @Override // com.kuaikan.library.net.callback.NetBaseCallback
    /* renamed from: a, reason: merged with bridge method [inline-methods] */
    public void onSuccessful(@NotNull KkdidResponse kkdidRes) {
        Intrinsics.checkNotNullParameter(kkdidRes, "kkdidRes");
        ur0.a.f109522a.m(kkdidRes.getKkdid());
    }

    @Override // com.kuaikan.library.net.callback.NetBaseCallback
    public void onFailure(@NotNull e e11) {
        Intrinsics.checkNotNullParameter(e11, "e");
    }
}
\```

Hook onSuccessful 并且获取 kkdid, 提示报错重载的格式不匹配, 那我们换成 Object的重载

```javascript
Java.perform(function () {

  var C0957a = Java.use("com.kuaikan.user.kkdid.a$a");
  C0957a["onSuccessful"].overload('com.kuaikan.user.kkdid.KkdidResponse').implementation = function (v) {
    console.log(`C0957a.onSuccessful is called`);
    console.log(v.getKkdid());

    this["onSuccessful"](v);
  };
});
\```

![image](https://bbs.kanxue.com/upload/attach/202602/9QG4BCN9ZEESXUW.jpg)

因为使用了 Object, 需要使用 Java.cast转化一下

```javascript
Java.perform(function () {
  var KkdidResponse = Java.use("com.kuaikan.user.kkdid.KkdidResponse");

  var C0957a = Java.use("com.kuaikan.user.kkdid.a$a");
  C0957a["onSuccessful"].overload('java.lang.Object').implementation = function (v) {
    console.log(`C0957a.onSuccessful is called`);
    var nv = Java.cast(v, KkdidResponse)
    console.log(nv.getKkdid());
    this["onSuccessful"](v);
  };
});
\```

![image](https://bbs.kanxue.com/upload/attach/202602/239DAVH533URRZE.jpg)

#### 远端接口?

那基本上可以确定来自远端, 搜一下Http Response body中存在的关键字 发现搜不到.

![image](https://bbs.kanxue.com/upload/attach/202602/ZXYM9FWMHNPN7DF.jpg)

只能继续分析代码, 查看下 KkdidResponse的引用, 定位到 `v1/device/did/create`接口上. 从接口上不难分析出 kkdid 应该就是 kk device id的缩写了

![image](https://bbs.kanxue.com/upload/attach/202602/KK9WX2J9FHB6JVQ.jpg)

```java
@NotNull
@FormUrlEncoded
@Encryption
@POST("v1/device/did/create")
s90.g<KkdidResponse> getKkdid(@Field(RemoteMessageConst.MessageBody.PARAM) @Nullable String param);
\```

小黄鸟搜一下这个接口, 发现接口数据被加密 (好好好, 看漫画我只用快看漫画) =>  [data数据解密](https://www.yuque.com/again-719bb/pfhi8f/oee7ugfig95w4kw5#Tjmry)

![image](https://bbs.kanxue.com/upload/attach/202602/7Z5PQDHXA3S67TR.jpg)

# 0x07 响应数据data分析

#### 数据格式

拿kkid分析时返回的数据, 这个data看上去又像是 base64

```json
{
	"code": 200,
	"message": "ok",
	"data": "lorC3FaOgAoQCDG68mwCjRLaIZ0aKhG5RMPqoF0eHAWxYgFDNQ7mKlLweMfDOY5M",
	"request_id": "289d37c47b6e47a7bed4440e455fffaf.137.17714936015646673"
}
\```

#### 定位

搜下`"data"`1800+... 太多了 这不纯纯折磨

![image](https://bbs.kanxue.com/upload/attach/202602/2GVAWKEYVDVSQEA.jpg)

这个时候我们需要发散逆向思维, 拿到数据通常需要 String => JSON Object, 那我们在关键链路上拦截试试

```javascript
Java.perform(function () {
  const Gson = Java.use('com.google.gson.Gson');
  Gson.fromJson.overload('java.lang.String', 'java.lang.Class').implementation = function (jsonStr, clazz) {
    console.log(`\n==== Gson.fromJson()被调用 ====`);

    if (jsonStr.indexOf(`"data":`) >= 0){
      //打印java堆栈
      var traces = Java.use("android.util.Log").getStackTraceString(Java.use("java.lang.Exception").$new())
      console.log(traces);
      console.log(`JSON hit: ${jsonStr}`);
    }

    const result = this.fromJson(jsonStr, clazz);
    return result;
  };

  const JsonParser = Java.use('com.google.gson.JsonParser');
  JsonParser['parseString'].overload('java.lang.String').implementation = function(json) {
    console.log(`\n==== JsonParser.parseString()被调用 ====`);
    if (json.indexOf(`"data":`) >= 0){
      //打印java堆栈
      var traces = Java.use("android.util.Log").getStackTraceString(Java.use("java.lang.Exception").$new())
      console.log(traces);
      console.log(`JSON hit: ${json}`);
    }
    return this['parseString'](json);
  };
});
\```

```java
==== JsonParser.parseString()被调用 ====
java.lang.Exception
        at com.google.gson.JsonParser.parseString(Native Method)
        at com.google.gson.JsonParser.parse(JsonParser.java:1)
        at ia0.d.e(EncryptionInterceptor.kt:47)
        at ia0.d.intercept(EncryptionInterceptor.kt:76)
        at pz0.f.proceed(RealInterceptorChain.kt:167)
        at ia0.j.intercept(NetDebugInterceptor.kt:25)
        at pz0.f.proceed(RealInterceptorChain.kt:167)
        at ia0.n.intercept(NetStatusInterceptor.kt:26)
        at pz0.f.proceed(RealInterceptorChain.kt:167)
        at ia0.o.a(INetChain.kt:35)
        at com.kuaikan.video.player.antichain.net.interceptor.ResponseHeaderInterceptor.b(ResponseHeaderInterceptor.kt:10)
        at ia0.e.b(FilterNetInterceptor.kt:55)
        at ia0.o.a(INetChain.kt:57)
        at com.kuaikan.net.intercept.CookieInterceptor.b(CookieInterceptor.kt:10)
        at ia0.e.b(FilterNetInterceptor.kt:55)
        at ia0.o.a(INetChain.kt:57)
        at com.kuaikan.net.FakePushInterceptor.b(FakePushInterceptor.kt:127)
        at ia0.e.b(FilterNetInterceptor.kt:55)
        at ia0.o.a(INetChain.kt:57)
        at com.kuaikan.teenager.TeenagerInterceptor.b(TeenagerInterceptor.kt:20)
        at ia0.e.b(FilterNetInterceptor.kt:55)
        at ia0.o.a(INetChain.kt:57)
        at com.kuaikan.app.accelertor.ecdn.ECdnNetInterceptor.b(ECdnNetInterceptor.kt:25)
        at ia0.e.b(FilterNetInterceptor.kt:55)
        at ia0.o.a(INetChain.kt:57)
        at com.kuaikan.net.intercept.RequestInterceptor.b(RequestInterceptor.kt:155)
        at ia0.e.b(FilterNetInterceptor.kt:55)
        at ia0.o.a(INetChain.kt:57)
        at w90.e$a$a.intercept(OkInterceptorSwitcher.kt:67)
        at pz0.f.proceed(RealInterceptorChain.kt:167)
        at ia0.g.intercept(LoadingIssueInterceptor.kt:130)
        at pz0.f.proceed(RealInterceptorChain.kt:167)
        at ia0.k.intercept(NetFirstInterceptor.kt:37)
        at pz0.f.proceed(RealInterceptorChain.kt:167)
        at oz0.e.q(RealCall.kt:117)
        at oz0.e$a.run(RealCall.kt:52)
        at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1167)
        at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:641)
        at java.lang.Thread.run(Thread.java:923)

JSON hit: {"code":200,"message":"ok","data":"FSlybBqXEWx6T3Dka70SOCVEPHq4v6in9lM_2DWQ4YADdeWeFCGx6iX-uXZOFYqz","request_id":"289d37c47b6e47a7bed4440e455fffaf.151.17714912998249019"}
\```

定位到ia0.d.e看看

```java
public final okhttp3.Response e(okhttp3.Response response) throws IOException {
    JsonElement jsonElement;
    ResponseBody responseBodyPeekBody = response.peekBody(Long.MAX_VALUE);
    MediaType mediaType = responseBodyPeekBody.get$contentType();
    if (mediaType == null || !Intrinsics.areEqual(FastJsonJsonView.DEFAULT_CONTENT_TYPE, mediaType.getMediaType())) {
        return response;
    }
    String strString = responseBodyPeekBody.string();
    if (TextUtils.isEmpty(strString)) {
        return response;
    }
    try {
        JsonElement jsonElement2 = new JsonParser().parse(strString);
        JsonElement jsonElement3 = null;
        JsonObject asJsonObject = (jsonElement2 == null || !jsonElement2.isJsonObject()) ? null : jsonElement2.getAsJsonObject();
        if (asJsonObject == null || !asJsonObject.has("code")) {
            return response;
        }
        JsonElement jsonElement4 = asJsonObject.get("code");
        if (!jsonElement4.isJsonPrimitive()) {
            return response;
        }
        JsonPrimitive asJsonPrimitive = jsonElement4.getAsJsonPrimitive();
        if (!s.Y(asJsonPrimitive != null ? Boolean.valueOf(asJsonPrimitive.isNumber()) : null) || jsonElement4.getAsInt() != 200 || !asJsonObject.has("data")) {
            return response;
        }
        String asString = (asJsonObject == null || (jsonElement = asJsonObject.get("data")) == null) ? null : jsonElement.getAsString();
        if (asString == null) {
            return response;
        }
        String strD = d(asString);
        if (strD != null) {
            try {
                jsonElement3 = new JsonParser().parse(strD);
            } catch (Exception e11) {
                n0.f("EncryptionInterceptor", e11, e11.getLocalizedMessage());
            }
        }
        if (strD == null || jsonElement3 == null) {
            n0.f("EncryptionInterceptor", new UnknownError("ResponseBody is unavailable!"), "解密失败");
        }
        if (jsonElement3 == null && asJsonObject != null) {
            asJsonObject.addProperty("code", (Number) 200);
        }
        if (asJsonObject != null) {
            asJsonObject.add("data", jsonElement3);
        }
        return response.newBuilder().body(ResponseBody.INSTANCE.create(responseBodyPeekBody.get$contentType(), String.valueOf(asJsonObject))).build();
    } catch (JsonSyntaxException unused) {
        return response;
    }
}
\```

#### data解密流程

`get("data")`应该就是获取Response.body中的data加密数据了

```java
String asString = (asJsonObject == null || (jsonElement = asJsonObject.get("data")) == null) ? null : jsonElement.getAsString();
if (asString == null) {
    return response;
}
String strD = d(asString);
\```

看下d方法

```java
public final String d(@NotNull String data) {
    Intrinsics.checkNotNullParameter(data, "data");
    if (!TextUtils.isEmpty(data)) {
        try {
            byte[] bArrD = com.kuaikan.library.base.utils.e.f59696a.d(data, 8);
            byte[] bytes = m().getBytes(Charsets.UTF_8);
            Intrinsics.checkNotNullExpressionValue(bytes, "getBytes(...)");
            return q.b(bArrD, bytes);
        } catch (Exception e11) {
            if (n0.sDebugBuild) {
                n0.f("EncryptionInterceptor", e11, e11.getMessage());
            }
        }
    }
    return data;
}
\```

`com.kuaikan.library.base.utils.e.f59696a.d(data, 8);`也是base64, 只不过flag变成了8

```java
public final byte[] d(@Nullable String str, int flag) {
    if (str == null || str.length() == 0) {
        return null;
    }
    return Base64.decode(str, flag);
}
\```

q.b最终会跳转到 q.a上

```java
public static final byte[] a(@org.jetbrains.annotations.Nullable byte[] data, @org.jetbrains.annotations.Nullable byte[] key) throws NoSuchPaddingException, NoSuchAlgorithmException, InvalidKeyException, InvalidAlgorithmParameterException {
    if (data == null || data.length == 0) {
        return null;
    }
    SecretKeySpec secretKeySpec = new SecretKeySpec(key, "AES/CBC/PKCS5Padding");
    Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
    cipher.init(2, secretKeySpec, AES_IV);
    return cipher.doFinal(data);
}

public static final String b(@org.jetbrains.annotations.Nullable byte[] data, @org.jetbrains.annotations.Nullable byte[] key) throws NoSuchPaddingException, NoSuchAlgorithmException, InvalidKeyException, InvalidAlgorithmParameterException {
    byte[] bArrA = a(data, key);
    return bArrA == null ? "" : new String(bArrA, Charsets.UTF_8);
}
\```

hook一下q.a看看参数

```javascript
Java.perform(function () {
     var StringCls = Java.use("java.lang.String");
    function bytesToString(bytes) {
        return StringCls.$new(bytes, "UTF-8");
    }

    var q = Java.use("com.kuaikan.library.base.utils.q");
    q["a"].implementation = function (data, key) {
        console.log(`q.a is called: data=${bytesToString(data)}, key=${bytesToString(key)}`);
        let result = this["a"](data, key);
        // console.log(`q.a result=${result}`);
        return result;
    };
});
\```

拿到输出结果, 直接拿去解密

```javascript
q.a is called: data=乱码省略...., key=zGexheDzpxMcuIGu
\```

![image](https://bbs.kanxue.com/upload/attach/202602/A4X8HVWMN5GASF8.jpg)

---

# 回复

## 回复 by mb_srmwcgoy (#2)

*2026-2-19 18:21*

taiqiangl

## 回复 by kccp (#3)

*2026-2-19 18:46*

666

## 回复 by 我不是卷王 (#4)

*2026-2-22 09:42*

6

## 回复 by wx_插曲 (#5)

*2026-2-24 12:51*

6

## 回复 by 丶咖啡猫丶 (#6)

*2026-2-24 17:56*

666

## 回复 by mb_roiscepd (#7)

*2026-2-24 17:56*

666

## 回复 by mb_fglogyec (#8)

*2026-2-24 20:34*

6666

## 回复 by ikunnn (#9)

*2026-2-27 17:52*

221

## 回复 by uni7corn (#10)

*2026-2-28 01:47*

666

## 回复 by AK1988DA (#11)

*2026-3-1 19:11*

8

## 回复 by mb_srmwcgoy (#12)

*2026-3-4 18:44*

有frida检测呀

## 回复 by 零_721409 (#13)

*2026-3-4 20:46*

66666666666

## 回复 by 小迷糊ddd (#14)

*2026-4-7 09:14*

感谢分享，受教了。

## 回复 by mb_vkopqebt (#15)

*2026-5-29 21:13*

谢谢

## 回复 by 希梦☆奈何 (#16)

*2026-6-2 11:55*

666
