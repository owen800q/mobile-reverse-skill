---
title: '[原创]SSL-Pinning-Bybass——一键式解决SSL证书锁定'
url: https://bbs.kanxue.com/thread-292049.htm
tid: 292049
author: ODcat
date: '2026-07-17'
tags: [Android安全, 原创, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T13:30:57+08:00'
replies: 7
---

# 使用指南

`SSL-Pinning-Bybass` 是一个用于 Android App 动态调试的 Frida 脚本，目标是在授权测试场景下绕过或识别常见 SSL Pinning / 证书校验逻辑。

脚本覆盖两层：

1. Java 层
包括 OkHttp、`SSLContext`、`TrustManagerImpl`、`TrustManagerFactory`、`HttpsURLConnection`、TrustKit、Cronet、WebView、Flutter 相关类识别。
2. Native 层
包括 BoringSSL / Cronet / OpenSSL 派生库中的 `SSL_CTX_set_custom_verify`、`SSL_set_custom_verify` 等验证回调入口。
脚本默认是“稳定模式”：只启用相对安全、低侵入的 Hook，避免启动后白屏、卡死或主线程阻塞。深度扫描和高风险 Hook 都保留在配置里，但默认关闭。

**主要能力**

- 绕过 OkHttp `CertificatePinner.check/check$okhttp`
- 替换 OkHttp `OkHttpClient.Builder.certificatePinner()`
- 替换 OkHttp `hostnameVerifier()`
- 替换 `SSLContext.init()` 中的 `TrustManager[]`
- 覆盖 Android Conscrypt `TrustManagerImpl`
- 覆盖 `TrustManagerFactory.getTrustManagers()`
- 覆盖 `HttpsURLConnection` 的 HostnameVerifier
- 支持 TrustKit 常见 Pinning 类
- 支持 Cronet public key pinning 相关 Builder 方法
- 识别 Flutter / Dart Native 模块和 Java 类
- Hook `dlopen/android_dlopen_ext`，在相关 so 加载后自动重扫
- Native 层绕过 BoringSSL/Cronet custom verify 回调

**默认稳定配置**

文件顶部的 `CONFIG` 是主要配置区：

```python
enableMultiClassLoaderScan: false,
enableAutoDiscovery: false,
printNativeBacktrace: false,
enableCronetQuicDowngrade: false,
enableWebViewSslErrorProceed: false,
enableNativeReturnOverrideHooks: false,
hookSslCtxSetVerify: false,
```

这些默认关闭是为了稳定。
如何HOOK时App 白屏、黑屏、闪退或卡死时，优先保持这些选项关闭。

**推荐调试流程**

1. 先用默认配置运行脚本。
2. 如果 App 正常启动，再观察日志中是否出现：
	- `OkHttp CertificatePinner`
	- `SSLContext.init`
	- `SSL_CTX_set_custom_verify`
	- `libsscronet.so`
	- `libttboringssl.so`
3. 如果仍抓不到 HTTPS 流量，再逐步打开增强功能，不要一次性全开。
4. 如果 App 白屏、黑屏、闪退或卡死，先关闭：
	- `enableModuleLoadHooks`
	- `enableNativeCustomVerifyHooks`
	- `enableOkHttpSocketFactoryBypass`
	- `enableCronetQuicDowngrade`

**增强功能开关**

需要分析混淆、插件化或加固 App 时，可打开：

```python
enableMultiClassLoaderScan: true,
enableAutoDiscovery: true,
```

作用：

- 枚举多个 ClassLoader
- 搜索可疑 SSL / Pinning 类
- 输出候选方法，例如 `checkServerTrusted`、`verify`、`certificatePinner`

如果要分析 Native 调用链，可打开：

```python
printNativeBacktrace: true,
```

但这个会明显增加日志和性能开销，不建议默认开启。

如果目标使用 Cronet/QUIC，想尝试让流量回落到 TLS/TCP：

```python
enableCronetQuicDowngrade: true,
```

如果要强制 WebView 遇到 SSL 错误后继续加载：

```python
enableWebViewSslErrorProceed: true,
```

这个选项比较激进，默认关闭。

**白屏、黑屏、闪退或卡死时排查**

如果注入后 App 白屏、黑屏、闪退或卡死，按这个顺序降级：

1.关闭模块加载 Hook：

```python
enableModuleLoadHooks: false,
```

2.关闭 Native custom verify：

```python
enableNativeCustomVerifyHooks: false,
```

3.保持这些高风险选项关闭：

```python
enableAutoDiscovery: false,
enableMultiClassLoaderScan: false,
printNativeBacktrace: false,
enableNativeReturnOverrideHooks: false,
enableCronetQuicDowngrade: false,
```

4.如果仍白屏，只保留 Java 层 OkHttp / TrustManager，再逐项打开 Native 功能。

**注意事项**
部分 App 使用自研 Native TLS、加固、反 Frida、证书透明度、QUIC 或动态下发网络库，可能需要针对目标 App 单独补 Hook。

# SSL-Pinning-Bybass

```python
const CONFIG = {
    moduleWaitTimeoutMs: 15000,
    modulePollIntervalMs: 100,
    nativeRescanDelayMs: 300,
    javaRescanDelayMs: 1200,
    startupJavaHookDelayMs: 300,
    startupNativeHookDelayMs: 300,
    printNativeBacktrace: false,

    // 默认使用稳定模式。需要分析混淆/加固/插件时，再手动打开深度扫描。
    enableMultiClassLoaderScan: false,
    enableAutoDiscovery: false,
    enableModuleLoadHooks: true,
    enableJavaRescanOnNativeLoad: false,
    enableNativeRescanOnNativeLoad: true,
    enableCronetQuicDowngrade: false,
    enableWebViewSslErrorProceed: false,

    enableOkHttpSocketFactoryBypass: false,
    enableHttpsUrlConnectionSocketFactoryBypass: false,
    enableNativeCustomVerifyHooks: true,
    enableNativeSetVerifyHooks: false,
    enableNativeCertVerifyCallbackHook: false,
    enableNativeReturnOverrideHooks: false,
    hookSslCtxSetVerify: false,

    maxClassLoadersToScan: 8,
    maxDiscoveryMatches: 40,
    maxNativeReturnLogsPerSymbol: 5,

    customVerifyModules: [
        { name: "libttboringssl.so", note: "抖音系 BoringSSL" },
        { name: "libsscronet.so", note: "TikTok/Cronet" },
        { name: "libflutter.so", note: "Flutter/Dart 网络栈识别" },
        { name: "libssl.so", note: "OpenSSL/系统 SSL" },
        { name: "libcrypto.so", note: "OpenSSL/系统 Crypto" },
        { name: "libboringssl.so", note: "BoringSSL" },
        { name: "libconscrypt_jni.so", note: "Android Conscrypt JNI" },
    ],

    nativeModuleNameHints: [
        "ssl",
        "crypto",
        "cronet",
        "boring",
        "conscrypt",
        "flutter",
        "quic",
        "ttboring",
    ],

    discoveryClassKeywords: [
        "certificatepinner",
        "hostnameverifier",
        "trustmanager",
        "pinning",
        "trustkit",
        "cronet",
        "webviewclient",
        "flutter",
        "ssl",
        "tls",
    ],

    discoveryMethodKeywords: [
        "checkServerTrusted",
        "checkClientTrusted",
        "verify",
        "shouldEnforcePinning",
        "onReceivedSslError",
        "addPublicKeyPins",
        "enableQuic",
        "setQuicOptions",
        "certificatePinner",
        "hostnameVerifier",
        "sslSocketFactory",
    ],

    discoveryMethodQueries: [
        "*CertificatePinner*!*",
        "*Pinning*!*",
        "*Trust*!checkServerTrusted",
        "*Trust*!checkClientTrusted",
        "*HostnameVerifier*!verify",
        "*Cronet*!*",
        "*WebViewClient*!onReceivedSslError",
        "*Flutter*!*",
    ],
};

const hookedJavaOverloads = Object.create(null);
const hookedNativeFunctions = Object.create(null);
const hookedNativeCallbacks = Object.create(null);
const nativeFakeCallbacks = Object.create(null);
const nativeCallbackRefs = [];
const discoveredJavaCandidates = Object.create(null);
const discoveredMethodQueries = Object.create(null);
const hostnameVerifierInstances = Object.create(null);

let dynamicClassCounter = 0;
let javaRescanTimer = null;
let nativeRescanTimer = null;
let cachedTrustManagers = null;

function logInfo(message) {
    console.log(`[SSL绕过] ${message}`);
}

function logWarn(message) {
    console.warn(`[SSL绕过] ${message}`);
}

function logError(message) {
    console.error(`[SSL绕过] ${message}`);
}

function safeToString(value) {
    try {
        return String(value);
    } catch (e) {
        return "<无法转为字符串>";
    }
}

function safeLower(value) {
    return safeToString(value).toLowerCase();
}

function basename(path) {
    if (!path) {
        return "";
    }

    const normalized = safeToString(path).replace(/\\/g, "/");
    const index = normalized.lastIndexOf("/");
    return index >= 0 ? normalized.substring(index + 1) : normalized;
}

function typeName(type) {
    if (!type) {
        return "未知类型";
    }

    return type.className || type.name || safeToString(type);
}

function describeOverload(overload) {
    const returnType = typeName(overload.returnType);
    const argumentTypes = overload.argumentTypes
        .map(function (argumentType) {
            return typeName(argumentType);
        })
        .join(", ");

    return `${returnType} (${argumentTypes})`;
}

function callOriginal(overload, thisObject, argsLike) {
    const args = [];

    for (let i = 0; i < argsLike.length; i += 1) {
        args.push(argsLike[i]);
    }

    return overload.call.apply(overload, [thisObject].concat(args));
}

function pointerIsNull(ptr) {
    return ptr === null || ptr === undefined || (typeof ptr.isNull === "function" && ptr.isNull());
}

function getLoaderLabel(loader) {
    if (!loader) {
        return "默认 ClassLoader";
    }

    try {
        return loader.toString();
    } catch (e) {
        return `ClassLoader#${safeToString(loader)}`;
    }
}

function getLoaderKey(loader, fallback) {
    return fallback || getLoaderLabel(loader);
}

function withJavaClassLoader(loader, callback) {
    const previousLoader = Java.classFactory.loader;

    try {
        if (loader) {
            Java.classFactory.loader = loader;
        }

        return callback();
    } finally {
        if (loader) {
            Java.classFactory.loader = previousLoader;
        }
    }
}

function tryUseClass(className) {
    try {
        return Java.use(className);
    } catch (e) {
        return null;
    }
}

function classExists(className) {
    return tryUseClass(className) !== null;
}

function hookAllOverloads(targetClass, className, methodName, implementationFactory, ownerKey) {
    const method = targetClass[methodName];

    if (!method || !method.overloads) {
        return 0;
    }

    let hookedCount = 0;

    method.overloads.forEach(function (overload) {
        const signature = describeOverload(overload);
        const hookKey = `${ownerKey || "默认"}|${className}|${methodName}|${signature}`;

        if (hookedJavaOverloads[hookKey]) {
            return;
        }

        try {
            overload.implementation = implementationFactory(signature, overload);
            hookedJavaOverloads[hookKey] = true;
            hookedCount += 1;
            logInfo(`[+] 已挂钩 ${className}.${methodName} ${signature}`);
        } catch (e) {
            logWarn(`[-] 挂钩 ${className}.${methodName} ${signature} 失败：${e}`);
        }
    });

    return hookedCount;
}

function successfulReturn(overload, argsLike, options) {
    const opts = options || {};
    const returnType = typeName(overload.returnType);

    if (returnType === "void") {
        return;
    }

    if (returnType === "boolean") {
        return opts.booleanValue !== undefined ? opts.booleanValue : true;
    }

    if (returnType === "int" || returnType === "short" || returnType === "byte") {
        return opts.numberValue !== undefined ? opts.numberValue : 0;
    }

    if (returnType === "long") {
        return opts.numberValue !== undefined ? opts.numberValue : 0;
    }

    if (returnType.indexOf("java.util.List") >= 0) {
        if (opts.objectValue !== undefined) {
            return opts.objectValue;
        }

        if (argsLike.length > 0 && argsLike[0]) {
            return argsLike[0];
        }

        const ArrayList = tryUseClass("java.util.ArrayList");
        return ArrayList ? ArrayList.$new() : null;
    }

    if (returnType.indexOf("java.security.cert.X509Certificate") >= 0 && returnType.charAt(0) === "[") {
        return argsLike.length > 0 ? argsLike[0] : Java.array("java.security.cert.X509Certificate", []);
    }

    return opts.objectValue !== undefined ? opts.objectValue : null;
}

function getTrustAllManagers() {
    if (cachedTrustManagers) {
        return cachedTrustManagers;
    }

    const X509TrustManager = Java.use("javax.net.ssl.X509TrustManager");
    const trustManagerClassName = `com.abc.ssl.pinning.TrustManager${Date.now()}${dynamicClassCounter++}`;

    const TrustManager = Java.registerClass({
        name: trustManagerClassName,
        implements: [X509TrustManager],
        methods: {
            checkClientTrusted: [{
                returnType: "void",
                argumentTypes: ["[Ljava.security.cert.X509Certificate;", "java.lang.String"],
                implementation: function (chain, authType) {
                },
            }],
            checkServerTrusted: [{
                returnType: "void",
                argumentTypes: ["[Ljava.security.cert.X509Certificate;", "java.lang.String"],
                implementation: function (chain, authType) {
                },
            }],
            getAcceptedIssuers: [{
                returnType: "[Ljava.security.cert.X509Certificate;",
                argumentTypes: [],
                implementation: function () {
                    return Java.array("java.security.cert.X509Certificate", []);
                },
            }],
        },
    });

    cachedTrustManagers = Java.array("javax.net.ssl.TrustManager", [TrustManager.$new()]);
    logInfo(`[+] 已注册全信任 TrustManager：${trustManagerClassName}`);
    return cachedTrustManagers;
}

function getTrustAllHostnameVerifier(ownerKey) {
    const key = ownerKey || "默认";

    if (hostnameVerifierInstances[key]) {
        return hostnameVerifierInstances[key];
    }

    const HostnameVerifier = Java.use("javax.net.ssl.HostnameVerifier");
    const className = `com.abc.ssl.pinning.HostnameVerifier${Date.now()}${dynamicClassCounter++}`;

    const Verifier = Java.registerClass({
        name: className,
        implements: [HostnameVerifier],
        methods: {
            verify: [{
                returnType: "boolean",
                argumentTypes: ["java.lang.String", "javax.net.ssl.SSLSession"],
                implementation: function (hostname, session) {
                    logInfo(`[绕过] HostnameVerifier.verify 已放行：${hostname}`);
                    return true;
                },
            }],
        },
    });

    hostnameVerifierInstances[key] = Verifier.$new();
    logInfo(`[+] 已注册全放行 HostnameVerifier：${className}`);
    return hostnameVerifierInstances[key];
}

function createEmptyCertificatePinner() {
    const CertificatePinner = tryUseClass("okhttp3.CertificatePinner");
    const CertificatePinnerBuilder = tryUseClass("okhttp3.CertificatePinner$Builder");

    if (CertificatePinnerBuilder) {
        try {
            return CertificatePinnerBuilder.$new().build();
        } catch (e) {
            logWarn(`[-] 创建空 CertificatePinner$Builder 失败：${e}`);
        }
    }

    if (CertificatePinner) {
        try {
            if (CertificatePinner.DEFAULT) {
                return CertificatePinner.DEFAULT.value;
            }
        } catch (e) {
            logWarn(`[-] 读取 CertificatePinner.DEFAULT 失败：${e}`);
        }
    }

    return null;
}

// 绕过 OkHttp 3/4/5 的 CertificatePinner。
function bypassCertificatePinner(ownerKey, loaderLabel) {
    const className = "okhttp3.CertificatePinner";
    const CertificatePinner = tryUseClass(className);

    if (!CertificatePinner) {
        return;
    }

    hookAllOverloads(CertificatePinner, className, "check", function (signature) {
        return function () {
            const hostname = arguments.length > 0 ? arguments[0] : "<未知>";
            logInfo(`[绕过] OkHttp CertificatePinner.check ${signature} -> ${hostname} | ${loaderLabel}`);
            return;
        };
    }, ownerKey);

    hookAllOverloads(CertificatePinner, className, "check$okhttp", function (signature) {
        return function () {
            const hostname = arguments.length > 0 ? arguments[0] : "<未知>";
            logInfo(`[绕过] OkHttp CertificatePinner.check$okhttp ${signature} -> ${hostname} | ${loaderLabel}`);
            return;
        };
    }, ownerKey);
}

function bypassOkHttpBuilder(ownerKey, loaderLabel) {
    const className = "okhttp3.OkHttpClient$Builder";
    const Builder = tryUseClass(className);

    if (!Builder) {
        return;
    }

    hookAllOverloads(Builder, className, "certificatePinner", function (signature, overload) {
        return function () {
            const emptyPinner = createEmptyCertificatePinner();
            logInfo(`[绕过] OkHttpClient.Builder.certificatePinner 已替换为空 Pinning 策略 | ${loaderLabel}`);

            if (emptyPinner) {
                try {
                    return overload.call(this, emptyPinner);
                } catch (e) {
                    logWarn(`[-] 调用原始 certificatePinner(empty) 失败，直接返回 Builder：${e}`);
                }
            }

            return this;
        };
    }, ownerKey);

    hookAllOverloads(Builder, className, "hostnameVerifier", function (signature, overload) {
        return function () {
            const verifier = getTrustAllHostnameVerifier(ownerKey);
            logInfo(`[绕过] OkHttpClient.Builder.hostnameVerifier 已替换为全放行校验器 | ${loaderLabel}`);

            try {
                return overload.call(this, verifier);
            } catch (e) {
                logWarn(`[-] 调用原始 hostnameVerifier(verifier) 失败，直接返回 Builder：${e}`);
                return this;
            }
        };
    }, ownerKey);

    if (CONFIG.enableOkHttpSocketFactoryBypass) {
        hookAllOverloads(Builder, className, "sslSocketFactory", function (signature) {
            return function () {
                logInfo(`[绕过] OkHttpClient.Builder.sslSocketFactory 已拦截，跳过自定义 SSLSocketFactory | ${loaderLabel}`);
                return this;
            };
        }, ownerKey);
    } else {
        hookAllOverloads(Builder, className, "sslSocketFactory", function (signature, overload) {
            return function () {
                logInfo(`[识别] OkHttpClient.Builder.sslSocketFactory 已调用，稳定模式下保持原始逻辑 | ${loaderLabel}`);
                return callOriginal(overload, this, arguments);
            };
        }, ownerKey);
    }
}

function shouldRunSystemHooks(ownerKey) {
    return ownerKey === "默认";
}

function shouldHandleNativeLoadPath(path) {
    const lowerName = safeLower(basename(path));

    return CONFIG.nativeModuleNameHints.some(function (hint) {
        return lowerName.indexOf(hint) >= 0;
    });
}

function shouldRunDiscoveryForOwner(ownerKey) {
    return ownerKey === "默认";
}

function shouldScanAdditionalClassLoader(loaderLabel) {
    const lowerLabel = safeLower(loaderLabel);

    return lowerLabel.indexOf("pathclassloader") >= 0 ||
        lowerLabel.indexOf("dexclassloader") >= 0 ||
        lowerLabel.indexOf("delegate_last") >= 0 ||
        lowerLabel.indexOf("inmemorydexclassloader") >= 0;
}

function isNativeSpecEnabled(spec) {
    if (spec.group === "customVerify") {
        return CONFIG.enableNativeCustomVerifyHooks;
    }

    if (spec.group === "setVerify") {
        return CONFIG.enableNativeSetVerifyHooks;
    }

    if (spec.group === "certVerifyCallback") {
        return CONFIG.enableNativeCertVerifyCallbackHook;
    }

    if (spec.group === "returnOverride") {
        return CONFIG.enableNativeReturnOverrideHooks;
    }

    return true;
}

// 替换 Java TrustManager 验证逻辑。
function bypassTrustManager(ownerKey, loaderLabel) {
    const ArrayList = tryUseClass("java.util.ArrayList");
    const TrustManagerImpl = tryUseClass("com.android.org.conscrypt.TrustManagerImpl");

    if (TrustManagerImpl && ArrayList && shouldRunSystemHooks(ownerKey)) {
        hookAllOverloads(TrustManagerImpl, "com.android.org.conscrypt.TrustManagerImpl", "checkTrustedRecursive", function (signature) {
            return function () {
                logInfo(`[绕过] TrustManagerImpl.checkTrustedRecursive ${signature} | ${loaderLabel}`);
                return ArrayList.$new();
            };
        }, ownerKey);

        hookAllOverloads(TrustManagerImpl, "com.android.org.conscrypt.TrustManagerImpl", "verifyChain", function (signature, overload) {
            return function () {
                logInfo(`[绕过] TrustManagerImpl.verifyChain ${signature} | ${loaderLabel}`);
                return successfulReturn(overload, arguments, { objectValue: arguments.length > 0 ? arguments[0] : ArrayList.$new() });
            };
        }, ownerKey);
    }

    const SSLContext = tryUseClass("javax.net.ssl.SSLContext");
    if (SSLContext && shouldRunSystemHooks(ownerKey)) {
        hookAllOverloads(SSLContext, "javax.net.ssl.SSLContext", "init", function (signature, overload) {
            return function (keyManager, trustManager, secureRandom) {
                logInfo(`[绕过] SSLContext.init 已替换 TrustManager[] | ${loaderLabel}`);
                return overload.call(this, keyManager, getTrustAllManagers(), secureRandom);
            };
        }, ownerKey);
    }

    const TrustManagerFactory = tryUseClass("javax.net.ssl.TrustManagerFactory");
    if (TrustManagerFactory && shouldRunSystemHooks(ownerKey)) {
        hookAllOverloads(TrustManagerFactory, "javax.net.ssl.TrustManagerFactory", "getTrustManagers", function (signature) {
            return function () {
                logInfo(`[绕过] TrustManagerFactory.getTrustManagers 已返回全信任 TrustManager[] | ${loaderLabel}`);
                return getTrustAllManagers();
            };
        }, ownerKey);
    }
}

function bypassHttpsURLConnection(ownerKey, loaderLabel) {
    if (!shouldRunSystemHooks(ownerKey)) {
        return;
    }

    const className = "javax.net.ssl.HttpsURLConnection";
    const HttpsURLConnection = tryUseClass(className);

    if (!HttpsURLConnection) {
        return;
    }

    hookAllOverloads(HttpsURLConnection, className, "setDefaultHostnameVerifier", function (signature, overload) {
        return function () {
            logInfo(`[绕过] HttpsURLConnection.setDefaultHostnameVerifier 已替换为全放行校验器 | ${loaderLabel}`);
            return overload.call(this, getTrustAllHostnameVerifier(ownerKey));
        };
    }, ownerKey);

    hookAllOverloads(HttpsURLConnection, className, "setHostnameVerifier", function (signature, overload) {
        return function () {
            logInfo(`[绕过] HttpsURLConnection.setHostnameVerifier 已替换为全放行校验器 | ${loaderLabel}`);
            return overload.call(this, getTrustAllHostnameVerifier(ownerKey));
        };
    }, ownerKey);

    if (CONFIG.enableHttpsUrlConnectionSocketFactoryBypass) {
        hookAllOverloads(HttpsURLConnection, className, "setSSLSocketFactory", function () {
            return function () {
                logInfo(`[绕过] HttpsURLConnection.setSSLSocketFactory 已拦截，跳过自定义 SSLSocketFactory | ${loaderLabel}`);
                return;
            };
        }, ownerKey);
    }
}

function bypassTrustKit(ownerKey, loaderLabel) {
    const targets = [
        {
            className: "com.datatheorem.android.trustkit.pinning.PinningTrustManager",
            methods: [
                { name: "checkServerTrusted", booleanValue: true },
                { name: "checkClientTrusted", booleanValue: true },
                { name: "shouldEnforcePinning", booleanValue: false },
            ],
        },
        {
            className: "com.datatheorem.android.trustkit.pinning.OkHostnameVerifier",
            methods: [
                { name: "verify", booleanValue: true },
            ],
        },
    ];

    targets.forEach(function (target) {
        const klass = tryUseClass(target.className);
        if (!klass) {
            return;
        }

        target.methods.forEach(function (method) {
            hookAllOverloads(klass, target.className, method.name, function (signature, overload) {
                return function () {
                    logInfo(`[绕过] TrustKit ${target.className}.${method.name} ${signature} | ${loaderLabel}`);
                    return successfulReturn(overload, arguments, { booleanValue: method.booleanValue });
                };
            }, ownerKey);
        });
    });
}

function bypassCronet(ownerKey, loaderLabel) {
    const cronetBuilders = [
        "org.chromium.net.CronetEngine$Builder",
        "org.chromium.net.ExperimentalCronetEngine$Builder",
        "org.chromium.net.impl.CronetEngineBuilderImpl",
        "org.chromium.net.impl.NativeCronetEngineBuilderImpl",
    ];

    cronetBuilders.forEach(function (className) {
        const Builder = tryUseClass(className);
        if (!Builder) {
            return;
        }

        hookAllOverloads(Builder, className, "addPublicKeyPins", function () {
            return function () {
                const host = arguments.length > 0 ? arguments[0] : "<未知主机>";
                logInfo(`[绕过] Cronet addPublicKeyPins 已忽略：${host} | ${loaderLabel}`);
                return this;
            };
        }, ownerKey);

        hookAllOverloads(Builder, className, "enablePublicKeyPinningBypassForLocalTrustAnchors", function (signature, overload) {
            return function () {
                logInfo(`[绕过] Cronet 已强制启用本地信任锚 Pinning 绕过 | ${loaderLabel}`);

                try {
                    return overload.call(this, true);
                } catch (e) {
                    return this;
                }
            };
        }, ownerKey);

        hookAllOverloads(Builder, className, "enableQuic", function (signature, overload) {
            return function () {
                if (!CONFIG.enableCronetQuicDowngrade) {
                    return callOriginal(overload, this, arguments);
                }

                logInfo(`[绕过] Cronet enableQuic 已强制关闭，便于回落到 TLS/TCP | ${loaderLabel}`);

                try {
                    return overload.call(this, false);
                } catch (e) {
                    return this;
                }
            };
        }, ownerKey);

        hookAllOverloads(Builder, className, "setQuicOptions", function (signature, overload) {
            return function () {
                if (CONFIG.enableCronetQuicDowngrade) {
                    logInfo(`[绕过] Cronet setQuicOptions 已忽略 | ${loaderLabel}`);
                    return this;
                }

                return callOriginal(overload, this, arguments);
            };
        }, ownerKey);

        hookAllOverloads(Builder, className, "setLibraryLoader", function (signature, overload) {
            return function () {
                const loader = arguments.length > 0 ? arguments[0] : null;
                logInfo(`[识别] Cronet setLibraryLoader：${safeToString(loader)} | ${loaderLabel}`);
                return callOriginal(overload, this, arguments);
            };
        }, ownerKey);

        hookAllOverloads(Builder, className, "build", function (signature, overload) {
            return function () {
                logInfo(`[识别] Cronet Engine 正在 build，Native 库加载 Hook 会继续跟踪 | ${loaderLabel}`);
                return callOriginal(overload, this, arguments);
            };
        }, ownerKey);
    });
}

function bypassWebView(ownerKey, loaderLabel) {
    if (!shouldRunSystemHooks(ownerKey)) {
        return;
    }

    const className = "android.webkit.WebViewClient";
    const WebViewClient = tryUseClass(className);

    if (!WebViewClient) {
        return;
    }

    hookAllOverloads(WebViewClient, className, "onReceivedSslError", function () {
        return function () {
            const handler = arguments.length > 1 ? arguments[1] : null;
            logInfo(`[绕过] WebViewClient.onReceivedSslError 已命中 | ${loaderLabel}`);

            if (CONFIG.enableWebViewSslErrorProceed && handler) {
                try {
                    handler.proceed();
                    logInfo("[绕过] WebView SSL 错误已调用 proceed()");
                } catch (e) {
                    logWarn(`[-] WebView SSL 错误 proceed() 失败：${e}`);
                }
            }

            return;
        };
    }, ownerKey);
}

function identifyFlutter(ownerKey, loaderLabel) {
    const flutterClasses = [
        "io.flutter.embedding.engine.FlutterEngine",
        "io.flutter.plugin.common.MethodChannel",
        "io.flutter.embedding.engine.dart.DartExecutor",
    ];

    flutterClasses.forEach(function (className) {
        if (classExists(className)) {
            logInfo(`[识别] 发现 Flutter Java 类：${className} | ${loaderLabel}`);
        }
    });
}

function hookSystemLoaders(ownerKey, loaderLabel) {
    if (!CONFIG.enableModuleLoadHooks || !shouldRunSystemHooks(ownerKey)) {
        return;
    }

    const SystemClass = tryUseClass("java.lang.System");

    if (!SystemClass) {
        return;
    }

    ["load", "loadLibrary"].forEach(function (methodName) {
        hookAllOverloads(SystemClass, "java.lang.System", methodName, function (signature, overload) {
            return function () {
                const target = arguments.length > 0 ? arguments[0] : "<未知>";
                logInfo(`[加载] System.${methodName}(${target}) 已调用 | ${loaderLabel}`);

                try {
                    return callOriginal(overload, this, arguments);
                } finally {
                    scheduleNativeRescan(`System.${methodName}(${target})`);
                    scheduleJavaRescan(`System.${methodName}(${target})`);
                }
            };
        }, ownerKey);
    });
}

function classNameMatchesDiscovery(className) {
    const lowerName = safeLower(className);

    return CONFIG.discoveryClassKeywords.some(function (keyword) {
        return lowerName.indexOf(keyword.toLowerCase()) >= 0;
    });
}

function methodTextMatchesDiscovery(methodText) {
    return CONFIG.discoveryMethodKeywords.some(function (keyword) {
        return methodText.indexOf(keyword) >= 0;
    });
}

function inspectDiscoveryClass(className, ownerKey, loaderLabel) {
    const key = `${ownerKey}|${className}`;

    if (discoveredJavaCandidates[key]) {
        return false;
    }

    discoveredJavaCandidates[key] = true;

    try {
        const klass = Java.use(className);
        const methods = klass.class.getDeclaredMethods();
        const matches = [];

        for (let i = 0; i < methods.length; i += 1) {
            const text = safeToString(methods[i]);

            if (methodTextMatchesDiscovery(text)) {
                matches.push(text);
            }

            if (matches.length >= 8) {
                break;
            }
        }

        if (matches.length > 0) {
            logInfo(`[发现] 候选 SSL/Pinning 类：${className} | ${loaderLabel}`);
            matches.forEach(function (method) {
                logInfo(`[发现]   方法：${method}`);
            });
            return true;
        }
    } catch (e) {
        logWarn(`[-] 检查候选类 ${className} 失败：${e}`);
    }

    return false;
}

function runLoadedClassDiscovery(ownerKey, loaderLabel) {
    if (!CONFIG.enableAutoDiscovery || !Java.enumerateLoadedClasses) {
        return;
    }

    let matchCount = 0;

    Java.enumerateLoadedClasses({
        onMatch: function (className) {
            if (matchCount >= CONFIG.maxDiscoveryMatches) {
                return;
            }

            if (!classNameMatchesDiscovery(className)) {
                return;
            }

            if (inspectDiscoveryClass(className, ownerKey, loaderLabel)) {
                matchCount += 1;
            }
        },
        onComplete: function () {
            logInfo(`[发现] 已完成加载类扫描 | ${loaderLabel} | 新候选数量：${matchCount}`);
        },
    });
}

function runMethodQueryDiscovery(reason) {
    if (!CONFIG.enableAutoDiscovery || !Java.enumerateMethods) {
        return;
    }

    CONFIG.discoveryMethodQueries.forEach(function (query) {
        const key = `${reason}|${query}`;

        if (discoveredMethodQueries[key]) {
            return;
        }

        discoveredMethodQueries[key] = true;

        try {
            const groups = Java.enumerateMethods(`${query}/s`);
            let count = 0;

            groups.forEach(function (group) {
                if (count >= CONFIG.maxDiscoveryMatches) {
                    return;
                }

                if (group.classes) {
                    group.classes.forEach(function (klass) {
                        if (count >= CONFIG.maxDiscoveryMatches) {
                            return;
                        }

                        logInfo(`[发现] 方法查询 ${query} 命中类：${klass.name || "<未知类>"}`);

                        if (klass.methods) {
                            klass.methods.slice(0, 8).forEach(function (method) {
                                logInfo(`[发现]   ${method}`);
                            });
                        }

                        count += 1;
                    });
                    return;
                }

                logInfo(`[发现] 方法查询 ${query} 命中类：${group.className || group.name || "<未知类>"}`);

                if (group.methods) {
                    group.methods.slice(0, 8).forEach(function (method) {
                        logInfo(`[发现]   ${method}`);
                    });
                }

                count += 1;
            });
        } catch (e) {
            logWarn(`[-] Java.enumerateMethods 查询 ${query} 失败：${e}`);
        }
    });
}

function runJavaHookSuite(loader, loaderLabel, ownerKey, reason) {
    withJavaClassLoader(loader, function () {
        try {
            bypassCertificatePinner(ownerKey, loaderLabel);
            bypassOkHttpBuilder(ownerKey, loaderLabel);
            bypassTrustManager(ownerKey, loaderLabel);
            bypassHttpsURLConnection(ownerKey, loaderLabel);
            bypassTrustKit(ownerKey, loaderLabel);
            bypassCronet(ownerKey, loaderLabel);
            bypassWebView(ownerKey, loaderLabel);
            identifyFlutter(ownerKey, loaderLabel);
            hookSystemLoaders(ownerKey, loaderLabel);

            if (shouldRunDiscoveryForOwner(ownerKey)) {
                runLoadedClassDiscovery(ownerKey, loaderLabel);
            }
        } catch (e) {
            logWarn(`[-] Java 挂钩套件执行失败 | ${loaderLabel} | ${reason}：${e}`);
        }
    });
}

function scanJavaClassLoaders(reason) {
    if (typeof Java === "undefined" || !Java.available) {
        logWarn("[-] 当前进程不可用 Java 运行时，跳过 Java 层挂钩");
        return;
    }

    Java.perform(function () {
        logInfo(`[+] 开始 Java 层扫描：${reason}`);
        runJavaHookSuite(null, "默认 ClassLoader", "默认", reason);

        if (CONFIG.enableMultiClassLoaderScan && Java.enumerateClassLoaders) {
            let scannedClassLoaderCount = 0;

            Java.enumerateClassLoaders({
                onMatch: function (loader) {
                    if (scannedClassLoaderCount >= CONFIG.maxClassLoadersToScan) {
                        return;
                    }

                    const loaderLabel = getLoaderLabel(loader);

                    if (!shouldScanAdditionalClassLoader(loaderLabel)) {
                        return;
                    }

                    const ownerKey = getLoaderKey(loader, loaderLabel);
                    scannedClassLoaderCount += 1;
                    runJavaHookSuite(loader, loaderLabel, ownerKey, reason);
                },
                onComplete: function () {
                    logInfo(`[+] 多 ClassLoader 扫描完成：${reason} | 已扫描 ${scannedClassLoaderCount} 个`);
                },
            });
        } else {
            logInfo("[!] 当前 Frida 环境不支持 Java.enumerateClassLoaders 或配置已关闭");
        }

        runMethodQueryDiscovery(reason);
    });
}

function scheduleJavaRescan(reason) {
    if (javaRescanTimer !== null) {
        clearTimeout(javaRescanTimer);
    }

    javaRescanTimer = setTimeout(function () {
        javaRescanTimer = null;
        scanJavaClassLoaders(`延迟重扫：${reason}`);
    }, CONFIG.javaRescanDelayMs);
}

// 等待模块加载，避免目标 so 延迟加载导致 Native Hook 过早失败。
function waitForModule(moduleName, timeoutMs, intervalMs) {
    const effectiveTimeoutMs = timeoutMs || CONFIG.moduleWaitTimeoutMs;
    const effectiveIntervalMs = intervalMs || CONFIG.modulePollIntervalMs;

    return new Promise(function (resolve, reject) {
        const existing = Process.findModuleByName(moduleName);
        if (existing !== null) {
            resolve(existing);
            return;
        }

        const startedAt = Date.now();
        const interval = setInterval(function () {
            const module = Process.findModuleByName(moduleName);

            if (module !== null) {
                clearInterval(interval);
                resolve(module);
                return;
            }

            if (Date.now() - startedAt >= effectiveTimeoutMs) {
                clearInterval(interval);
                reject(new Error(`等待 ${moduleName} 超时，已等待 ${effectiveTimeoutMs}ms`));
            }
        }, effectiveIntervalMs);
    });
}

const NATIVE_VERIFY_SPECS = [
    {
        name: "SSL_CTX_set_custom_verify",
        group: "customVerify",
        kind: "callbackSetter",
        callbackArgIndex: 2,
        callbackReturnValue: 0,
        callbackArgTypes: ["pointer", "pointer"],
        successLabel: "SSL_VERIFY_OK",
    },
    {
        name: "SSL_set_custom_verify",
        group: "customVerify",
        kind: "callbackSetter",
        callbackArgIndex: 2,
        callbackReturnValue: 0,
        callbackArgTypes: ["pointer", "pointer"],
        successLabel: "SSL_VERIFY_OK",
    },
    {
        name: "SSL_CTX_set_cert_verify_callback",
        group: "certVerifyCallback",
        kind: "callbackSetter",
        callbackArgIndex: 1,
        callbackReturnValue: 1,
        callbackArgTypes: ["pointer", "pointer"],
        successLabel: "验证成功",
    },
    {
        name: "SSL_CTX_set_verify",
        group: "setVerify",
        kind: "callbackSetter",
        callbackArgIndex: 2,
        callbackReturnValue: 1,
        callbackArgTypes: ["int", "pointer"],
        successLabel: "验证成功",
        enabled: function () {
            return CONFIG.hookSslCtxSetVerify;
        },
    },
    {
        name: "SSL_set_verify",
        group: "setVerify",
        kind: "callbackSetter",
        callbackArgIndex: 2,
        callbackReturnValue: 1,
        callbackArgTypes: ["int", "pointer"],
        successLabel: "验证成功",
    },
    {
        name: "SSL_get_verify_result",
        group: "returnOverride",
        kind: "returnOverride",
        returnValue: 0,
        successLabel: "X509_V_OK",
    },
    {
        name: "X509_verify_cert",
        group: "returnOverride",
        kind: "returnOverride",
        returnValue: 1,
        successLabel: "验证成功",
    },
];

function shouldEnableNativeSpec(spec) {
    return isNativeSpecEnabled(spec) && (!spec.enabled || spec.enabled());
}

function getFakeNativeCallback(spec) {
    const key = `${spec.name}|${spec.callbackReturnValue}|${spec.callbackArgTypes.join(",")}`;

    if (nativeFakeCallbacks[key]) {
        return nativeFakeCallbacks[key];
    }

    const fakeCallback = new NativeCallback(function () {
        logInfo(`[绕过] ${spec.name} 回调已强制返回 ${spec.callbackReturnValue}（${spec.successLabel}）`);
        return spec.callbackReturnValue;
    }, "int", spec.callbackArgTypes);

    nativeFakeCallbacks[key] = fakeCallback;
    nativeCallbackRefs.push(fakeCallback);
    return fakeCallback;
}

function hookNativeCallbackSetter(moduleName, addr, spec) {
    Interceptor.attach(addr, {
        onEnter: function (args) {
            const originalCb = args[spec.callbackArgIndex];

            if (pointerIsNull(originalCb)) {
                logInfo(`[命中] ${moduleName}!${spec.name} | 跳过：原始回调为空`);
                return;
            }

            const cbKey = `${spec.name}|${originalCb}`;
            if (!hookedNativeCallbacks[cbKey]) {
                hookedNativeCallbacks[cbKey] = moduleName;
                logInfo(`[绕过] ${moduleName}!${spec.name} 原始回调 ${originalCb} 已替换为伪造回调`);
            }

            args[spec.callbackArgIndex] = getFakeNativeCallback(spec);

            if (CONFIG.printNativeBacktrace) {
                try {
                    const bt = Thread.backtrace(this.context, Backtracer.ACCURATE)
                        .map(DebugSymbol.fromAddress)
                        .join("\n");
                    logInfo(`[调用栈] ${moduleName}!${spec.name}\n${bt}`);
                } catch (e) {
                    logWarn(`[-] 打印 ${moduleName}!${spec.name} 调用栈失败：${e}`);
                }
            }
        },
    });
}

function hookNativeReturnOverride(moduleName, addr, spec) {
    const logKey = `${moduleName}!${spec.name}`;
    let logCount = 0;

    Interceptor.attach(addr, {
        onLeave: function (retval) {
            retval.replace(spec.returnValue);

            if (logCount < CONFIG.maxNativeReturnLogsPerSymbol) {
                logCount += 1;
                logInfo(`[绕过] ${logKey} 返回值已强制改为 ${spec.returnValue}（${spec.successLabel}）`);
            }
        },
    });
}

function hookNativeSymbolInModule(module, spec) {
    if (!shouldEnableNativeSpec(spec)) {
        return false;
    }

    const addr = Module.findExportByName(module.name, spec.name);
    if (!addr) {
        return false;
    }

    const hookKey = `${module.name}|${spec.name}|${addr}`;
    if (hookedNativeFunctions[hookKey]) {
        return false;
    }

    try {
        if (spec.kind === "callbackSetter") {
            hookNativeCallbackSetter(module.name, addr, spec);
        } else if (spec.kind === "returnOverride") {
            hookNativeReturnOverride(module.name, addr, spec);
        }

        hookedNativeFunctions[hookKey] = true;
        logInfo(`[+] 已挂钩 Native 符号 ${module.name}!${spec.name} @ ${addr}`);
        return true;
    } catch (e) {
        logWarn(`[-] 挂钩 Native 符号 ${module.name}!${spec.name} 失败：${e}`);
        return false;
    }
}

function shouldScanNativeModule(module) {
    const lowerName = safeLower(module.name);

    return CONFIG.nativeModuleNameHints.some(function (hint) {
        return lowerName.indexOf(hint) >= 0;
    });
}

function identifyNativeModule(module, reason) {
    const lowerName = safeLower(module.name);

    if (lowerName.indexOf("flutter") >= 0) {
        logInfo(`[识别] 发现 Flutter/Dart Native 模块：${module.name} | ${module.path} | ${reason}`);
    }

    if (lowerName.indexOf("cronet") >= 0 || lowerName.indexOf("quic") >= 0) {
        logInfo(`[识别] 发现 Cronet/QUIC Native 模块：${module.name} | ${module.path} | ${reason}`);
    }
}

function hookNativeModule(module, reason) {
    identifyNativeModule(module, reason);

    if (!shouldScanNativeModule(module)) {
        return 0;
    }

    let count = 0;

    NATIVE_VERIFY_SPECS.forEach(function (spec) {
        if (hookNativeSymbolInModule(module, spec)) {
            count += 1;
        }
    });

    if (count > 0) {
        logInfo(`[+] Native 模块扫描完成：${module.name} | 新增挂钩 ${count} 个 | ${reason}`);
    }

    return count;
}

function hookAllLoadedNativeModules(reason) {
    const modules = Process.enumerateModules();
    let count = 0;

    modules.forEach(function (module) {
        count += hookNativeModule(module, reason);
    });

    logInfo(`[+] Native 已加载模块扫描完成：${reason} | 新增挂钩 ${count} 个`);
}

function scheduleNativeRescan(reason) {
    if (nativeRescanTimer !== null) {
        clearTimeout(nativeRescanTimer);
    }

    nativeRescanTimer = setTimeout(function () {
        nativeRescanTimer = null;
        hookAllLoadedNativeModules(`延迟重扫：${reason}`);
    }, CONFIG.nativeRescanDelayMs);
}

function onNativeLibraryLoaded(path, source) {
    const name = basename(path);

    if (!shouldHandleNativeLoadPath(name)) {
        return;
    }

    logInfo(`[加载] ${source} 已加载 Native 库：${path}`);

    const module = name ? Process.findModuleByName(name) : null;
    if (module) {
        hookNativeModule(module, `${source} 触发`);
    }

    if (CONFIG.enableNativeRescanOnNativeLoad) {
        scheduleNativeRescan(`${source}:${path}`);
    }

    if (CONFIG.enableJavaRescanOnNativeLoad) {
        scheduleJavaRescan(`${source}:${path}`);
    }
}

function hookNativeLoaders() {
    if (!CONFIG.enableModuleLoadHooks) {
        return;
    }

    ["dlopen", "android_dlopen_ext"].forEach(function (symbolName) {
        const addr = Module.findExportByName(null, symbolName);
        if (!addr) {
            logInfo(`[!] 未找到 Native 加载函数 ${symbolName}`);
            return;
        }

        const hookKey = `native-loader|${symbolName}|${addr}`;
        if (hookedNativeFunctions[hookKey]) {
            return;
        }

        try {
            Interceptor.attach(addr, {
                onEnter: function (args) {
                    this.libraryPath = pointerIsNull(args[0]) ? "" : Memory.readCString(args[0]);
                },
                onLeave: function (retval) {
                    if (!pointerIsNull(retval) && this.libraryPath) {
                        onNativeLibraryLoaded(this.libraryPath, symbolName);
                    }
                },
            });

            hookedNativeFunctions[hookKey] = true;
            logInfo(`[+] 已挂钩 Native 加载函数 ${symbolName} @ ${addr}`);
        } catch (e) {
            logWarn(`[-] 挂钩 Native 加载函数 ${symbolName} 失败：${e}`);
        }
    });
}

function waitForConfiguredNativeModules() {
    CONFIG.customVerifyModules.forEach(function (target) {
        logInfo(`[+] 正在等待加载 ${target.name}（${target.note}）`);

        waitForModule(target.name)
            .then(function (module) {
                hookNativeModule(module, `配置等待：${target.note}`);
            })
            .catch(function (e) {
                logWarn(`[-] ${e.message}`);
            });
    });
}

setImmediate(function () {
    setTimeout(function () {
        scanJavaClassLoaders("脚本启动");
    }, CONFIG.startupJavaHookDelayMs);

    setTimeout(function () {
        hookNativeLoaders();
        hookAllLoadedNativeModules("脚本启动");
        waitForConfiguredNativeModules();
    }, CONFIG.startupNativeHookDelayMs);
});
```

上传的附件：
- SSL-Pinning-Bybass.js

（41.74kb，87次下载）

---

# 回复

## 回复 by bluegatar (#2)

*2026-7-17 11:53*

非常棒，解决了不少实际问题

## 回复 by iBa0 (#3)

*2026-7-18 22:10*

666

## 回复 by Imxz (#4)

*2026-7-20 09:16*

tql

## 回复 by uni7corn (#5)

*2026-7-20 15:31*

感谢分享。

## 回复 by mb_zsmeyemp (#6)

*2026-7-21 09:47*

66666

## 回复 by mb_owfvtagq (#7)

*2026-7-21 10:01*

非常棒，解决了不少实际问题。

## 回复 by PPTV (#8)

SSL-Pinning-Bybass
