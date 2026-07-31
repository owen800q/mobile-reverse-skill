---
title: '[原创]okhttp 证书绑定流程 ssl pinning分析'
url: https://bbs.kanxue.com/thread-285064.htm
tid: 285064
author: 绿豆粥
date: '2024-12-31'
tags: [Android安全, 原创, 基础理论, 逆向分析, 协议分析]
crawled_at: '2026-07-31T14:15:20+08:00'
replies: 9
---

# 前言

https 相比 http 更加安全的其中一个原因就是增加了证书功能，用于对数据传输双方进行身份的验证和加密传输数据。之前直接使用 charles 或者 fiddler 等中间人抓包的方式，就无法获取到明文数据，或者无法与服务器建立连接。从而导致安全分析被卡在了第一步。虽然 app 使用了 https 方式对抗抓包，但是依然会有解决方案。本篇文章主要就是记录了我学习对抗https 过程中知识点的梳理。

# Okhttp 建立 https 的方式

要想反制https抓包，首先就得知道正向是如何开发的。okhttp 使用 https 有几种方式，第一种信任所有证书，第二种只信任系统证书，第三种只信任指定证书。

## 信任所有证书

HostnameVerifier 中不验证主机域名，TrustAllCerts 也不做任何处理。这样就是默认信任所有证书

```
private static class TrustAllCerts implements X509TrustManager {
    public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
    }

    public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {

    }

    public X509Certificate[] getAcceptedIssuers() {
        // //返回长度为0的数组，相当于return null
        return new X509Certificate[0];
    }
}

// 信任所有的域名
HostnameVerifier hostnameVerifierTrustAllHoust = new HostnameVerifier() {
    @Override
    public boolean verify(String s, SSLSession sslSession) {
        //信任所有域名
        return true;
    }
};

public void httpsTrustAll() {
    /**
     * 信任所有证书
     */
    new Thread(new Runnable() {
        @RequiresApi(api = Build.VERSION_CODES.N)
        @Override
        public void run() {
            SSLSocketFactory sSLSocketFactory = null;
            try {
                SSLContext sc = SSLContext.getInstance("TLS");
                sc.init(null, new TrustManager[]{new TrustAllCerts()}, new SecureRandom());

                sSLSocketFactory = sc.getSocketFactory();

                OkHttpClient mClient = new OkHttpClient().newBuilder()
                        .sslSocketFactory(sSLSocketFactory, new TrustAllCerts())
                        .hostnameVerifier(hostnameVerifierTrustAllHoust)
                        .build();

                Request request = new Request.Builder()
                        .url("https://www.baidu.com")
                        .build();
                String msg = "";
                try (Response response = mClient.newCall(request).execute()) {
                    msg = "HTTPS 忽略所有证书，连接成功";
                } catch (IOException e) {
                    msg = "HTTPS 忽略所有证书，连接失败";
                    e.printStackTrace();
                }
                mHandler.obtainMessage(2, msg).sendToTarget();

            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }).start();
}
```

## 信任系统证书

okhttp 如果不做任何配置，默认就是信任系统的证书

```
public void httpsTrustSystemca() {
    /**
     * 信任系统证书
     */
    new Thread(new Runnable() {
        @Override
        public void run() {
            // OkHttp 链接使用 HTTPS 时，默认自动验证系统的证书。不需要额外配置
            Request request = new Request.Builder()
                    .url("https://www.baidu.com/?q=defaultCerts")
                    .build();
            String msg = "";
            try (Response response = new OkHttpClient().newCall(request).execute()) {
                msg = "HTTPS 验证系统证书，连接成功";
            } catch (IOException e) {
                msg = "HTTPS 验证系统证书，连接失败";
                e.printStackTrace();
            }
            mHandler.obtainMessage(2, msg).sendToTarget();
        }
    }).start();
}
```

![image001](https://bbs.kanxue.com/upload/attach/202412/791353_WRKUZPFJ44WFPKQ.png)

## 只信任指定证书

更加专业的说法叫做 ssl pinning ，主要是将服务器的公钥或证书直接嵌入到客户端应用中，确保客户端只与特定的服务器建立安全连接。验证也有几种说法，单项验证和双向验证。双向验证是 app 验证服务端证书，同时服务器也验证 app证书。单项验证分两种情况，第一种客户端校验服务端证书，服务端不校验 app 证书，这是比较常见的。第二种，服务验证 app 证书，app 不校验服务端证书，这种就少见了。代码实现方式，第一种是通过 okhttp自带的 CertificatePinner 进行证书的绑定服务端证书，第二种就是前面验证系统证书时，使用的继承 X509TrustManager 的方式。

### 单项校验

1. #### CertificatePinner 证书绑定

这里使用了百度的证书，把证书从网站上保存下来之后，手动生成 hash，再进行 base64编码。通过下面的命令就可以搞定

```
openssl x509 -in baidu.crt -pubkey -noout | openssl rsa -pubin -outform der | openssl dgst -sha256 -binary | openssl base64
```

![image002](https://bbs.kanxue.com/upload/attach/202412/791353_BYH798P28GFWAGA.png)

通过 .certificatePinner(certificatePinner) 把 CertificatePinner 添加的百度证书绑定上去。在 okhttp 源码中，会自动进行证书的判断（后面的源码分析会有讲解），当证书不匹配就抛出异常。注意 CertificatePinner 只能绑定服务器证书进行验证，如果想要把 app 证书传入服务器，需要另外的代码。具体看后面的双向认证。

```
    private void appCheckServerCertificatePinner() {
        try {

            CertificatePinner certificatePinner = new CertificatePinner.Builder()
                    .add("http://www.baidu.com", "sha256/cGuxAXyFXFkWm61cF4HPWX8S0srS9j0aSqN0k4AP+4A=") // 替换为实际的公钥指纹
                    .build();
            HttpLoggingInterceptor loggingInterceptor = new HttpLoggingInterceptor();
            zInterceptor interceptor = new zInterceptor();
            // 配置 OkHttpClient
            OkHttpClient okHttpClient = new OkHttpClient.Builder()
                    .certificatePinner(certificatePinner)
                    .addInterceptor(new StackTraceInterceptor())
                    .addInterceptor(interceptor)
                    .build();

            // 发起请求
            Request request = new Request.Builder()
                    .url("https://www.baidu.com/")
                    .build();
            // 异步请求
            okHttpClient.newCall(request).enqueue(new Callback() {
                @Override
                public void onFailure(Call call, IOException e) {
                    Log.e(TAG, "app 百度证书 CertificatePinner " + e.toString());
                    mHandler.obtainMessage(336, "").sendToTarget();
                }

                @Override
                public void onResponse(Call call, Response response) throws IOException {
                    Log.i(TAG, "app 百度证书 CertificatePinner " + response.body().string());
                    mHandler.obtainMessage(333, "").sendToTarget();
                }
            });
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
```

![image003](https://bbs.kanxue.com/upload/attach/202412/791353_XVTDXBVQ6EQ4ZFT.png)

使用 charles 进行抓包。尽管 charles 的证书已经导入到系统中了。依然无法抓包。通过提示就可以知道，需要让 app 信任 Charles 的证书，才能抓包。具体的对抗方式在之后有介绍。

![image004](https://bbs.kanxue.com/upload/attach/202412/791353_F75C3GREB58GXK7.png)

![image005](https://bbs.kanxue.com/upload/attach/202412/791353_749MKSH8FJN9GVB.png)

1. #### X509TrustManager 证书绑定

X509TrustManager 自定义证书绑定。通过构造方法传入服务端的证书，在 checkServerTrusted 进行证书的校验。

使用 X509Certificate 的 equals 来判断两个证书是否相同，不相同直接抛出异常

```
// ====== app 验证 serverca ==== 单向验证 ===
private static class TrustServerCerts implements X509TrustManager {
    private final X509Certificate trustedCertificate;//传入信任的证书

    public TrustServerCerts(X509Certificate trustedCertificate) {
        this.trustedCertificate = trustedCertificate;
    }

    @Override
    public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
    }

    @Override
    public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
        // 服务器证书验证逻辑
        if (chain == null || chain.length == 0) {
            throw new CertificateException("No server certificates provided.");
        }

        // 验证服务器证书是否与受信任的证书匹配
        X509Certificate serverCertificate = chain[0];
        // Certificate 的 equal 方法
        if (!serverCertificate.equals(trustedCertificate)) {
            throw new CertificateException("Server certificate does not match the trusted certificate.");
        } else {
            Log.d(TAG, "https 验证服务器证书成功");
        }
    }

    @Override
    public X509Certificate[] getAcceptedIssuers() {
        // 返回受信任的证书颁发机构（CA）列表
        return new X509Certificate[]{trustedCertificate};
    }
}
```

我们把服务端证书证书放到 app 中的 assert 目录，然后通过代码读取证书设置到 X509Certificate ，在 SSLContext 初始化时，使用 TrustManager 加载 X509Certificate 。当app 发起请求时，系统会自动调用我们写的 TrustServerCerts 类中的 checkServerTrusted 校验证书。

注意这里还有一个主机校验，因为我们自己写了证书校验，那么主机校验，也需要进行我们进行操作。

通过 .hostnameVerifier((hostname, session) -> true) 校验。true 是不验证主机，这里我就偷个懒了。不做这么多操作了。

>
> 这里我使用本地服务器做了一个 https的服务器端做测试
>
>
>

```
private void appCheckServerCA_V3() {
    /**
     *  检测服务器证书 v2 ,使用 TrustServerCerts implements X509TrustManager
     *  从目录中加载证 crt证书
     */
    new Thread(() -> {
        try {
            // 加载受信任的服务器证书
            InputStream serverCertInputStream = getAssets().open("server.crt"); // 确保是 .crt 或 .pem 文件
            CertificateFactory certificateFactory = CertificateFactory.getInstance("X.509");
            X509Certificate serverCertificate = (X509Certificate) certificateFactory.generateCertificate(serverCertInputStream);

            // 创建 SSLContext
            SSLContext sslContext = SSLContext.getInstance("TLS");
            sslContext.init(null, new TrustManager[]{new TrustServerCerts(serverCertificate)}, new SecureRandom());

            // 配置 OkHttpClient
            HttpLoggingInterceptor loggingInterceptor = new HttpLoggingInterceptor();

            loggingInterceptor.setLevel(HttpLoggingInterceptor.Level.BODY);

            // 配置 OkHttpClient
            OkHttpClient okHttpClient = new OkHttpClient.Builder()
                    .sslSocketFactory(sslContext.getSocketFactory(), new TrustServerCerts(serverCertificate))
                    .hostnameVerifier((hostname, session) -> true) // 不验证域名
                    .addInterceptor(loggingInterceptor)
                    .build();

            // 发起请求
            Request request = new Request.Builder()
                    .url("https://xx.xx.xx.xx:8443/insecure") // 替换为你的服务器地址
                    .build();

            try (Response response = okHttpClient.newCall(request).execute()) {
                Log.i(TAG, "app 检测本地服务器证书 " + response.body().string());
                mHandler.obtainMessage(33, "").sendToTarget();
            } catch (Exception e) {
                Log.e(TAG, "app 检测本地服务器证书 " + e.toString());
                mHandler.obtainMessage(336, "").sendToTarget();
            }
        } catch (Exception e) {
            Log.e(TAG, "app 检测本地服务器证书 " + e.toString());
            mHandler.obtainMessage(336, "").sendToTarget();
        }
    }).start();
}
```

![image006](https://bbs.kanxue.com/upload/attach/202412/791353_E2T4ABXWAZ9W4AP.png)

### 双向校验

双向验证就是多了服务器校验客户端证书，请求的使用需要把 app 证书携带上。注意 app 端的证书需要时 bks 或者 jks 格式的。因为这两个证书中包含了秘钥和证书两个信息。android系统加载证书时需要这两个信息。使用 KeyStore 加载 bks 证书，传入证书秘钥，再使用 KeyManagerFactory 存放证书。关键点在 sslContext.init 初始话的时候，把 KeyManagerFactory 加载的 app 证书作为第一个参数传入，这样在发送请求时，会自动携带此证书。

同样 hostnameVerifier 也要做处理。

```
    private void SSLPinningV2() {
        /**
         * 使用本地的服务器验证 https
         *
         * 1. ca 字符串
         * 2. assert 下的文件
         */
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    // 加载客户端证书和私钥
                    KeyStore clientCA = KeyStore.getInstance("BKS");
                    InputStream keyStoreInputStream = getAssets().open("client.bks");
                    clientCA.load(keyStoreInputStream, "123456".toCharArray());

                    // 初始化 KeyManagerFactory
                    KeyManagerFactory keyManagerFactory = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
                    keyManagerFactory.init(clientCA, "123456".toCharArray());

                    InputStream serverCertInputStream = getAssets().open("server.crt"); // 确保是 .crt 或 .pem 文件
                    CertificateFactory certificateFactory = CertificateFactory.getInstance("X.509");
                    X509Certificate serverCertificate = (X509Certificate) certificateFactory.generateCertificate(serverCertInputStream);

                    // 创建 SSLContext
                    SSLContext sslContext = SSLContext.getInstance("TLS");
                    sslContext.init(keyManagerFactory.getKeyManagers(), new TrustManager[]{new TrustServerCerts(serverCertificate)}, new SecureRandom());

                    // 配置 OkHttpClient
                    OkHttpClient okHttpClient = new OkHttpClient.Builder()
                            // 通过 KeyManagerFactory 加载 app 的证书
                            //  trustManagerFactory 加载并验证服务端证书
                            .sslSocketFactory(sslContext.getSocketFactory(), (X509TrustManager) new TrustServerCerts(serverCertificate))
                            .hostnameVerifier((hostname, session) -> true) // 不验证域名
                            .build();

                    Request request = new Request.Builder().url("https://xx.xx.xx.xx:8443/secure").build();
                    try (Response response = okHttpClient.newCall(request).execute()) {
                        Log.i(TAG, "app 检测本地服务器证书 \n" + response.body().string());
                        mHandler.obtainMessage(33, "").sendToTarget();
                    } catch (Exception e) {
                        Log.e(TAG, "app 检测本地服务器证书 " + e.toString());
                        mHandler.obtainMessage(336, "").sendToTarget();
                    }
                } catch (CertificateException e) {
                    throw new RuntimeException(e);
                } catch (NoSuchAlgorithmException e) {
                    throw new RuntimeException(e);
                } catch (KeyManagementException e) {
                    throw new RuntimeException(e);
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }
        }).start();
    }
```

![image007](https://bbs.kanxue.com/upload/attach/202412/791353_29UAGEN2CEAA4EH.png)

此时开启抓包。假设 app 验证服务器的证书，你已经绕过成功了。但是没有把 app 的证书携带给服务器，因为 charles 抓 https 的包，默认是把 charles 自己的证书传给目标服务器。目标服务器开启了 app 证书校验，那一定是不会通过的，就会直接关闭这个链接请求。具体表现形式。

第一种，我自己写的 https 服务器直接返回 403 。

![image008](https://bbs.kanxue.com/upload/attach/202412/791353_D6UWEBH298N7Q59.png)

![image009](https://bbs.kanxue.com/upload/attach/202412/791353_7WYJJ5KZYEDZ5RW.png)

第二种，就是某app返回的 ，远程 ssl 服务器拒接请求。

![image010](https://bbs.kanxue.com/upload/attach/202412/791353_3T5WG63WKR5AU6N.png)

具体解决方案，请看下文！！

这里还有一个要注意的点。证书在app中的存放方式，可以是保存成文件例如保存成 crt bks jks 等文件直接和app一起打包。也可以把证书变成一个字符串，存放在代码中如下图所示。

![image011](https://bbs.kanxue.com/upload/attach/202412/791353_PGKAZ6D7BACRBRR.png)

最终都是要把证书转成 InputStream 进行加载。

![image012](https://bbs.kanxue.com/upload/attach/202412/791353_VKS8PT8SFETWT64.png)

![image013](https://bbs.kanxue.com/upload/attach/202412/791353_6TH4ACAQCDPE6A2.png)

# Okhttp 证书绑定源码分析

从 okhttp 开始发起请求跟踪，这里我用的 okhttp 版本是 3.10 这个版本代码还是使用 java 写的。先进入 execute

![image014](https://bbs.kanxue.com/upload/attach/202412/791353_CEPS6N7GAC752ZF.png)

 ![image](https://bbs.kanxue.com/upload/attach/202501/791353_CE3W6RMPB87ZAEX.webp)

没有被实现，点击左边的绿色图标跳转到实现的地方。

![image015](https://bbs.kanxue.com/upload/attach/202412/791353_MQX2YR3EMAYTUUY.png)

关键点就是 getResponseWithInterceptorChain，从这个地方得到了 Response 。

![image016](https://bbs.kanxue.com/upload/attach/202412/791353_8RR4263Q2EPE427.png)

okhttp 的关键就是有很多的拦截器，不同的拦截器做了不同的时候。默认先加载我们自定义的拦截器 client.interceptors()。然后加载了 4 个固定拦截器 。

- retryAndFollowUpInterceptor——失败和重定向拦截器
- BridgeInterceptor——封装request和response拦截器
- CacheInterceptor——缓存相关的过滤器，负责读取缓存直接返回、更新缓存
- ConnectInterceptor——连接服务，负责和服务器建立连接 这里才是真正的请求网络
- CallServerInterceptor——执行流操作(写出请求体、获得响应数据) 负责向服务器发送请求数

这里我们的重点是 ConnectInterceptor ，因为这个拦截器在建立连接的时候同时进行了证书校验。

![image016](https://bbs.kanxue.com/upload/attach/202412/791353_PXP29KSX3CBK9X5.png)

入口在 newStream

![image018](https://bbs.kanxue.com/upload/attach/202412/791353_QSZSDB77UE5JVBA.png)

findHealthyConnection 这是关键入口 ，里面做了各种检测。

![image019](https://bbs.kanxue.com/upload/attach/202412/791353_SJFCTTPP2467Y3Y.png)

在这个方法的下面一点有建立连接的代码

![image020](https://bbs.kanxue.com/upload/attach/202412/791353_8ZZ37D6XCRBXB3F.png)

![image021](https://bbs.kanxue.com/upload/attach/202412/791353_XXUW336FZSSZ3H7.png)

进入 establishProtocol

![image022](https://bbs.kanxue.com/upload/attach/202412/791353_GNWPDJ4VUHK9XMQ.png)

再跟进 connectTls 这就是最关键的地方，里面开始与服务器握手，握手之后进行证书的验证。

![image022](https://bbs.kanxue.com/upload/attach/202412/791353_49BFG9XKEQBNNWA.png)

通过代码里可以看到先进行了“握手”，然后验证主机域名，再验证 CertificatePinner 绑定的服务端证书。问题来了，这里没有看到验证 X509TrustManager 里面加载的服务器证书，是在哪里验证的呢？其实 X509TrustManager 是系统自带的证书验证，CertificatePinner 是 okhttp 的证书绑定认证。所以 X509TrustManager 是先执行的。在 sslSocket.startHandshake() 里面链接完成之后就调用了 X509TrustManager 进行验证。

进入 startHandshake 查看一下

![image022](https://bbs.kanxue.com/upload/attach/202412/791353_A7KDZQQYYYFZ97U.png)

到这里已经进入android源码了，不好继续跟踪。但是我们可以在 X509TrustManager 里面增加一个堆栈输出。看看是调用了哪个类，在源码网站去继续跟进分析。

![image025](https://bbs.kanxue.com/upload/attach/202412/791353_ATURK439BTY7MGH.png)

![image026](https://bbs.kanxue.com/upload/attach/202412/791353_VHZGFZTG4JMSJA4.png)

![image027](https://bbs.kanxue.com/upload/attach/202412/791353_U2B35NUFSUDNNRQ.png)

![image028](https://bbs.kanxue.com/upload/attach/202412/791353_W8VDU2GD5SRFPDW.png)

直接进入到最近的调用看看

![image029](https://bbs.kanxue.com/upload/attach/202412/791353_NA23FHPVFX8PBJ9.png)

## certificatePinner 校验逻辑

到这里基本可以确定是调用了 X509TrustManager 进行证书校验。X509TrustManager 的校验逻辑是我们自己写的。所以这里就继续分析一下 certificatePinner 校验逻辑。check方法传入了 host 和服务器返回的所有证书。跟进check 方法。

![image030](https://bbs.kanxue.com/upload/attach/202412/791353_3WH8BGGSKTAZ85A.png)

发现这个函数返回的是 void 。且第一步进行 host 判断

![image031](https://bbs.kanxue.com/upload/attach/202412/791353_QPSRDW2NUNR7EC9.png)

host是直接判断主机名是否相同，如果主机名都不相同，就直接退出 certificatePinner 校验。

![image032](https://bbs.kanxue.com/upload/attach/202412/791353_6XRQ3ZE9NBHP72E.png)

证书的校验逻辑

![image033](https://bbs.kanxue.com/upload/attach/202412/791353_VQARXYGM4E28NNP.png)

通过观察可以发现，如果证书校验通过是直接返回空的，如果校验失败就直接抛出了异常。所以如果打开了 charles 发现无法抓包，可以在 logcat 中看看是否有报错。这也是一种确定是否是 ssl pinning 的一种方式。

okhttp 校验证书的整体流程我们大概清楚了。app端的证书使用 KeyStore 加载，服务端证书通过CertificateFactory 加载。在 sslContext.init 是把两个证书作为参数传入。okhttp 发起请求时，在RealConnnection 中调用系统的 startHandshake 开始与服务器进行握手。当握手成功，系统主动调用 X509TrustManager 校验证书，之后是 okhttp 的主机验证，主机验证完成再到 CertificatePinner 绑定的证书校验。

# 反制方法

既然整体的证书绑定和校验方式我们都知道了，那么反制的方式也不会太难了。因为存在双向验证的方式，两种验证所在的地方都不同，我们能控制的仅在 app 端。服务器端的我们无法控制。针对不同的地方校验证书，我们就是用不同的方案。

## 服务端验证客户端证书

服务器端验证逻辑是，拿着客户端发送过来的证书去验证。当我们使用 charles 抓 https 包时，charles 默认是使用 charles 证书去发起请求。只要把 charles 发起请求携带的证书设置成 app 的证书即可。那么对于不是自己开发的app证书我们如何获取呢？charles 如何导入 app证书呢？

### Charles 导入 app 证书

首先解决简单的。假设我们已经获取到 app 证书了。

![image](https://bbs.kanxue.com/upload/attach/202412/791353_87VY9UDPPVXTW59.png)

![image035](https://bbs.kanxue.com/upload/attach/202412/791353_9YHPKCF9HKEHCJD.png)

然后填写目标主机的域名和https端口，默认https端口是 443

![image036](https://bbs.kanxue.com/upload/attach/202412/791353_S9XS7XY2HSMTE7A.png)

然后选择 import p12

![image036](https://bbs.kanxue.com/upload/attach/202412/791353_KBZSMAD7KXU5WSX.png)

再输入证书密码，即可导入成功

### 获取 app 中的证书

第一种解压 app ，然后搜索各种证书的结尾 .bks .p12 .pem .csr 等。然后通过逆向手段在代码中寻找证书的秘钥。具体如何寻找，不是本篇文章的目的了（狗头保命）。

第二种使用工具。肉丝大佬开源的 r0capture 有dump 证书的功能，且能无视证书校验抓取明文的包。

第三种hook方式。前面的分析我们可以知道 app 的证书是会作为第一个参数传入 sslContext.init ，且证书是通过 KeyManagerFactory加载出来的。这里就有两个 hook点了。

![image038](https://bbs.kanxue.com/upload/attach/202412/791353_VRR96R4VT28EVVS.png)

应该还有其他的寻找证书的方式，大佬可以在评论区分享交流一下哈！

## 客户端验证服务端证书

主要的方式都是使用 hook 。hook各种框架的验证证书逻辑。这部分已经有很多大佬造过轮子了。我们开箱即用就好。xposed有 justtrustmeplus 。frida 也有很多的bypass代码，具体逻辑是就 hook 上面源码分析过程中的具体类，修改返回值，或者自己new 一个类替换掉原先的类。

## 混淆过后的 okhttp 定位证书绑定的代码

混淆过的代码我们无法通过直接搜索找到证书绑定的位置。混淆有个特点的就是无法混淆系统类。所以我们主要找到一个关键的系统类的调用，然后输出堆栈，即可知道是在混淆代码中是哪里调用了这个绑定证书的位置。根据前面的分析可以发现 startHandshake 是一个很好的点。

![image039](https://bbs.kanxue.com/upload/attach/202412/791353_XE4BCG27FSB8H7W.png)

![image040](https://bbs.kanxue.com/upload/attach/202412/791353_M6SZ8TE597H53HJ.png)

进入就是 android 系统的 SSLSocker 系统代码，无法被混淆。但是这个是没有被实现的方法。我们从之前的堆栈找到是谁实现了它。

![image041](https://bbs.kanxue.com/upload/attach/202412/791353_34JNDQ3N7ZFQP96.png)

是 ConscryptEngineSocket （注意，在不同版本的系统，实现的类可能不同，我这里用的是 android13）

![image042](https://bbs.kanxue.com/upload/attach/202412/791353_KSZGYA3S9XNQCCB.png)

```
function hookssl(){

    Java.perform(function(){
        var  SSLSocket  = Java.use("com.android.org.conscrypt.ConscryptEngineSocket");
        console.log("SSLSocket ",SSLSocket);
        SSLSocket.startHandshake.implementation = function () {
            console.log("startHandshake");
            //java层的堆栈信息
            console.log(Java.use("android.util.Log").getStackTraceString(Java.use("java.lang.Exception").$new()))

            return this.startHandshake();
        }

    });
}
```

![image043](https://bbs.kanxue.com/upload/attach/202412/791353_4P7VWQTDM7SVH42.png)

可以看到的确输出了我们的调用栈。如果是被混淆了，也是会定位到大概位置。然后根据 okhttp 源码向下分析基本能够确定校验证书的地方

## 另一种 Okhttp 抓包方式

因为 okhttp 使用了拦截器的概念，我们可以自己使用 frida 构建一个拦截器，然后加入到 intercepter 链中。这总就是比较复杂了。能用上面hook绕过方式就用 hook吧。这种就作为一个备选方案，了解一下先。网上也有相应代码。

# 总结

本次通过代码实现了 https 证书绑定也就是 ssl pinning 。分析了 okhttp 的证书校验逻辑，其中 startHandshake 是一个hook点。在这时刻往下就是app中的证书校验逻辑 。文章后半部分给出了证书校验的绕过逻辑，总体来说在 app 端的证书校验，使用 hook手段绕过。服务端的证书校验，是把 app 端的证书导入抓包工具解决，其中app端的证书定位与证书密码获取也是通过hook进行定位。

文章很难面面俱到，如果有更多想要交流的可以来深入探讨一下哈 lvdouzhou_。多谢各位大佬的时间！

---

# 回复

## 回复 by huangjw (#2)

*2025-1-2 09:56*

爽文，加强了连接ssl方面的学习

## 回复 by mb_elqwyvnm (#3)

*2025-1-5 23:47*

很简单使用

## 回复 by 老皮一號 (#4)

*2025-1-6 08:40*

知識滿滿啊

## 回复 by Editor (#5)

*2025-1-6 09:51*

有个图片挂了

## 回复 by 七星舞月 (#6)

*2025-1-6 10:17*

感谢分享

## 回复 by 荧光之夏 (#7)

*2025-1-6 12:03*

666

## 回复 by yinsel (#8)

*2025-1-13 21:51*

可以分享一下这个demo程序吗

## 回复 by 绿豆粥 (#9)

*2025-1-14 10:14*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  yinsel](https://bbs.kanxue.com/user-978953.htm)
>
>  可以分享一下这个demo程序吗
>
>

暂时不分享哈![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_fhpfcoqp (#10)

*2025-12-1 11:36*

666
