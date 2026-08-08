---
title: '[原创]挑战 Android 墓碑机制：揭秘某头部社交 APP 永生背后的保活术'
url: https://bbs.kanxue.com/thread-290821.htm
tid: 290821
author: 易之生生
date: '2026-04-14'
tags: [Android安全, 原创, 基础理论, 逆向分析]
crawled_at: '2026-08-08T10:11:20+00:00'
replies: 123
---

# 挑战 Android 墓碑机制：揭秘某头部社交 APP 永生背后的保活术

随着 Android 系统的不断迭代，系统对后台进程的管控越来越严格（如 PhantomProcessKiller、FGS 限制等）。到了 Android 16（API 36），传统的后台保活手段几乎全军覆没，“墓碑机制”更是让大量应用在后台乖乖休眠。

然而，在逆向分析某头部社交 APP 时，发现它依然能够在严苛的系统限制下实现“永生”。本文将深入剥析其保活链路，看看大厂是如何利用 Android 系统机制的白名单与底层特性，构建出一条完整的“冷启动 -> 提权 -> 死亡监听无限复活”的保活链的。

## 冷启动入口：Account SyncAdapter

要实现保活，第一步是必须能在应用被强杀后重新唤醒。该 APP 巧妙地利用了 Android 的账户同步机制（Account SyncAdapter）。

APP 在 AndroidManifest 中注册了帐号认证与同步服务。即使应用被强杀且未设置自启动，系统也会为了执行定期的同步任务而主动冷启动应用进程。

![Account SyncAdapter](https://bbs.kanxue.com/upload/attach/202604/920134_5TPXTZW83VG8238.webp)

通过逆向分析，发现 AuthenticationService 调用了 Authenticator 的 addAccount 来静默添加系统同步账户。

![Account SyncAdapter](https://bbs.kanxue.com/upload/attach/202604/920134_TT6Z4JA3N73QV6E.webp)

随后，GuardSyncService 调用了 GuardSyncAdapter 的 onPerformSync 来执行系统同步任务，最后试图调用 startService 来启动 PushServiceProxy。

![Account SyncAdapter](https://bbs.kanxue.com/upload/attach/202604/920134_DNTYYESGWUTSCZ9.webp)

但是这里出现了一个核心问题：在 API 36 中，后台直接使用 startService 来启动 Service 已经被系统严格限制并判定为无效。那么，APP 究竟是如何成功拉起 Service 的呢？

![Account SyncAdapter](https://bbs.kanxue.com/upload/attach/202604/920134_6JMY3ES63URMCUV.webp)

![Account SyncAdapter](https://bbs.kanxue.com/upload/attach/202604/920134_UHFNM9F55USNGRE.webp)

通过 adb 确认系统的 account 与同步定时任务信息。账户确实已经成功注册：:

```python
adb shell dumpsys account
User UserInfo{0:机主:4c13}:
  Accounts: 4
    Account {name=易知生生, type=com.sina.weibo.account}

  RegisteredServicesCache: 9 services
    ServiceInfo: AuthenticatorDescription {type=com.sina.weibo.account}, ComponentInfo{com.sina.weibo/com.sina.weibo.sync.AuthenticationService}, uid 10236, lastUpdateTime 1774425903394
\```

查看系统的运行信息，发现定时任务运行极为频繁（每小时都在稳定触发）：

```python
adb shell dumpsys content
Periodic Syncs: 16
JobId=1 易知生生/com.sina.weibo.account u0 [com.sina.weibo.sync.authority] PERIODIC Reason=Periodic (period=1h00m00s flex=2m24s) Owner={u0a236 com.sina.weibo [10]}

Sync Status
Account 易知生生 u0 com.sina.weibo.account
=======================================================================
Authority                      Syncable  Enabled  Stats  Loc  Poll  Per   Feed  User  Othr  Tot   Fail  Can  Time    Last Sync            Backoff
-------------------------------------------------------------------------------------------------------------------------------------------------
com.sina.weibo.sync.authority  1         true     Total  0    0     6295  0     0     1     6296  5     46   12m58s  PERIODIC SUCCESS
                                                  Today             8                       8                0s      2026-04-14 11:36:31
                                                  Yestr             21                      21               1s

Recent Sync History
(SERVER is now split up to FEED and OTHER)
  #2  : 2026-04-14 11:36:30 PERIODIC    0.1s            易知生生/com.sina.weibo.account u0             com.sina.weibo.sync.authority           Periodic
  #11 : 2026-04-14 10:34:27 PERIODIC    0.1s  01:02:03  易知生生/com.sina.weibo.account u0             com.sina.weibo.sync.authority           Periodic
  #25 : 2026-04-14 09:34:45 PERIODIC    0.0s     59:42  易知生生/com.sina.weibo.account u0             com.sina.weibo.sync.authority           Periodic
  #30 : 2026-04-14 08:59:07 PERIODIC    0.0s     35:38  易知生生/com.sina.weibo.account u0             com.sina.weibo.sync.authority           Periodic
  #38 : 2026-04-14 05:18:42 PERIODIC    0.0s  03:40:25  易知生生/com.sina.weibo.account u0             com.sina.weibo.sync.authority           Periodic
  #44 : 2026-04-14 03:12:42 PERIODIC    0.0s  02:06:00  易知生生/com.sina.weibo.account u0             com.sina.weibo.sync.authority           Periodic
  #53 : 2026-04-14 01:33:06 PERIODIC    0.0s  01:39:35  易知生生/com.sina.weibo.account u0             com.sina.weibo.sync.authority           Periodic
  #61 : 2026-04-14 00:35:11 PERIODIC    0.1s     57:54  易知生生/com.sina.weibo.account u0             com.sina.weibo.sync.authority           Periodic

Per Adapter History
(SERVER is now split up to FEED and OTHER)
  易知生生/com.sina.weibo.account u0 [com.sina.weibo.sync.authority]
    Per source last syncs:
         OTHER  Success: 2025-05-17 23:55:44  Failure: N/A
         LOCAL  Success: N/A  Failure: N/A
          POLL  Success: N/A  Failure: N/A
          USER  Success: N/A  Failure: N/A
      PERIODIC  Success: 2026-04-14 11:36:31  Failure: 2026-03-07 17:49:56
          FEED  Success: N/A  Failure: N/A
    Last syncs:
      2026-04-14 11:36:31 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 10:34:27 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 09:34:45 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 08:59:07 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 05:18:42 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 03:12:42 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 01:33:06 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 00:35:11 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-13 23:34:25 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-13 22:37:00 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]

Sync adapters for UserInfo{0:机主:4c13}:
  ServiceInfo: SyncAdapterType {name=com.sina.weibo.sync.authority, type=com.sina.weibo.account, userVisible=false, supportsUploading=false, isAlwaysSyncable=true, allowParallelSyncs=false, settingsActivity=null, packageName=com.sina.weibo}, ComponentInfo{com.sina.weibo/com.sina.weibo.sync.guard.GuardSyncService}, uid 10236, lastUpdateTime 1774425903394
\```

通过这一步，APP 成功拿到了第一张“免死金牌”，确保了进程有规律地被系统主动拉起。

## 拉活 Service：绕过限制的 bindService 策略

既然 startService 在高版本失效，APP 必须寻找替代方案。

通过查看 APP 的 Service 运行信息，验证了猜想：PushServiceProxy 确实没有运行成功（被系统拦截）。但是，另一个名为 HotEventService 的服务却运行正常，并且其核心特征是 isBindService=true。

```python
adb shell dumpsys activity services com.sina.weibo
ACTIVITY MANAGER SERVICES (dumpsys activity services)
  User 0 active services:
  * ServiceRecord{183e79a u0 com.sina.weibo/.push.PushServiceProxy c:com.sina.weibo}
    intent={cmp=com.sina.weibo/.push.PushServiceProxy}
    packageName=com.sina.weibo
    processName=com.sina.weibo
    targetSdkVersion=35
    baseDir=/data/app/~~uoXjceB90I0js6XTG6nCMA==/com.sina.weibo-aKsMmrU5f9_N2Ayd8_aKlA==/base.apk
    dataDir=/data/user/0/com.sina.weibo
    app=null
    useNewWiuLogic_forCapabilities()=true
    useNewWiuLogic_forStart()=true
    useNewBfslLogic()=true
    mAllowWiu_noBinding=DENIED
    mAllowWiu_inBindService=DENIED
    mAllowWiu_byBindings=DENIED
    getFgsAllowWiu_legacy=DENIED
    getFgsAllowWiu_new=DENIED
    getFgsAllowWiu_forStart=DENIED
    getFgsAllowWiu_forCapabilities=DENIED
    allowUiJobScheduling=false
    recentCallingPackage=com.sina.weibo
    recentCallingUid=10236
    mAllowStart_noBinding=DENIED
    mAllowStart_inBindService=DENIED
    mAllowStart_byBindings=DENIED
    getFgsAllowStart_legacy=DENIED
    getFgsAllowStart_new=DENIED
    getFgsAllowStart=DENIED
    startForegroundCount=0
    infoAllowStartForeground=[callingPackage: com.sina.weibo; callingUid: 10236; uidState: TRNB; uidBFSL: n/a; intent: Intent { xflg=0x4 cmp=com.sina.weibo/.push.PushServiceProxy (has extras) }; code:DENIED; tempAllowListReason:&lt;null&gt;; allowWiu:-1; targetSdkVersion:35; callerTargetSdkVersion:35; startForegroundCount:0; bindFromPackage:null: isBindService:false]
    createTime=-2h12m1s559ms startingBgTimeout=--
    lastActivity=-2h12m1s559ms restartTime=-- createdFromFg=true

  * ServiceRecord{62edefe u0 com.sina.weibo/com.xiaomi.push.service.XMPushService c:com.sina.weibo}
    intent={cmp=com.sina.weibo/com.xiaomi.push.service.XMPushService}
    packageName=com.sina.weibo
    processName=com.sina.weibo:pushservice
    targetSdkVersion=35
    baseDir=/data/app/~~uoXjceB90I0js6XTG6nCMA==/com.sina.weibo-aKsMmrU5f9_N2Ayd8_aKlA==/base.apk
    dataDir=/data/user/0/com.sina.weibo
    app=ProcessRecord{c301933 29799:com.sina.weibo:pushservice/u0a236}
    useNewWiuLogic_forCapabilities()=true
    useNewWiuLogic_forStart()=true
    useNewBfslLogic()=true
    mAllowWiu_noBinding=DENIED
    mAllowWiu_inBindService=PROC_STATE_TOP
    mAllowWiu_byBindings=DENIED
    getFgsAllowWiu_legacy=PROC_STATE_TOP
    getFgsAllowWiu_new=DENIED
    getFgsAllowWiu_forStart=DENIED
    getFgsAllowWiu_forCapabilities=DENIED
    allowUiJobScheduling=false
    recentCallingPackage=com.sina.weibo
    recentCallingUid=10236
    mAllowStart_noBinding=DENIED
    mAllowStart_inBindService=PROC_STATE_TOP
    mAllowStart_byBindings=DENIED
    getFgsAllowStart_legacy=PROC_STATE_TOP
    getFgsAllowStart_new=DENIED
    getFgsAllowStart=DENIED
    startForegroundCount=0
    infoAllowStartForeground=[callingPackage: com.sina.weibo; callingUid: 10236; uidState: TOP ; uidBFSL: [BFSL]; intent: Intent { xflg=0x4 cmp=com.sina.weibo/com.xiaomi.push.service.XMPushService (has extras) }; code:PROC_STATE_TOP; tempAllowListReason:&lt;null&gt;; allowWiu:12; targetSdkVersion:35; callerTargetSdkVersion:35; startForegroundCount:0; bindFromPackage:null: isBindService:true]
    createTime=-5d1h44m9s681ms startingBgTimeout=--
    lastActivity=-2h12m1s602ms restartTime=-2h12m51s695ms createdFromFg=false
    restartCount=1 restartDelay=-4d3h39m14s11ms nextRestartTime=-2h12m51s952ms crashCount=0
    Bindings:
    * IntentBindRecord{f38ef44 CREATE}:
      intent={xflg=0x4 cmp=com.sina.weibo/com.xiaomi.push.service.XMPushService}
      binder=android.os.BinderProxy@d6b8cb
      requested=true received=true hasBound=true doRebind=false
      * Client AppBindRecord{fbcb8a8 ProcessRecord{20b3e81 29971:com.sina.weibo:remote/u0a236}}
        Per-process Connections:
          ConnectionRecord{54514d1 u0 CR com.sina.weibo/com.xiaomi.push.service.XMPushService:@3ddb7f8 flags=0x1}
      * Client AppBindRecord{d8dffc1 ProcessRecord{c301933 29799:com.sina.weibo:pushservice/u0a236}}
        Per-process Connections:
          ConnectionRecord{c1b3095 u0 CR com.sina.weibo/com.xiaomi.push.service.XMPushService:@a77984c flags=0x1}
      * Client AppBindRecord{9a8e366 ProcessRecord{fae235a 29967:com.sina.weibo/u0a236}}
        Per-process Connections:
          ConnectionRecord{f6c54c2 u0 CR com.sina.weibo/com.xiaomi.push.service.XMPushService:@352d0d flags=0x1}
    All Connections:
      ConnectionRecord{f6c54c2 u0 CR com.sina.weibo/com.xiaomi.push.service.XMPushService:@352d0d flags=0x1}
      ConnectionRecord{54514d1 u0 CR com.sina.weibo/com.xiaomi.push.service.XMPushService:@3ddb7f8 flags=0x1}
      ConnectionRecord{c1b3095 u0 CR com.sina.weibo/com.xiaomi.push.service.XMPushService:@a77984c flags=0x1}

  * ServiceRecord{567dec5 u0 com.sina.weibo/.HotEventService c:com.sina.weibo}
    intent={cmp=com.sina.weibo/.HotEventService}
    packageName=com.sina.weibo
    processName=com.sina.weibo:remote
    targetSdkVersion=35
    baseDir=/data/app/~~uoXjceB90I0js6XTG6nCMA==/com.sina.weibo-aKsMmrU5f9_N2Ayd8_aKlA==/base.apk
    dataDir=/data/user/0/com.sina.weibo
    app=ProcessRecord{20b3e81 29971:com.sina.weibo:remote/u0a236}
    useNewWiuLogic_forCapabilities()=true
    useNewWiuLogic_forStart()=true
    useNewBfslLogic()=true
    mAllowWiu_noBinding=DENIED
    mAllowWiu_inBindService=PROC_STATE_TOP
    mAllowWiu_byBindings=DENIED
    getFgsAllowWiu_legacy=PROC_STATE_TOP
    getFgsAllowWiu_new=DENIED
    getFgsAllowWiu_forStart=DENIED
    getFgsAllowWiu_forCapabilities=DENIED
    allowUiJobScheduling=false
    recentCallingPackage=com.sina.weibo
    recentCallingUid=10236
    mAllowStart_noBinding=DENIED
    mAllowStart_inBindService=PROC_STATE_TOP
    mAllowStart_byBindings=DENIED
    getFgsAllowStart_legacy=PROC_STATE_TOP
    getFgsAllowStart_new=DENIED
    getFgsAllowStart=DENIED
    startForegroundCount=0
    infoAllowStartForeground=[callingPackage: com.sina.weibo; callingUid: 10236; uidState: TOP ; uidBFSL: [BFSL]; intent: Intent { xflg=0x4 cmp=com.sina.weibo/.HotEventService }; code:PROC_STATE_TOP; tempAllowListReason:&lt;null&gt;; allowWiu:12; targetSdkVersion:35; callerTargetSdkVersion:35; startForegroundCount:0; bindFromPackage:null: isBindService:true]
    createTime=-5d1h44m9s521ms startingBgTimeout=--
    lastActivity=-2h12m1s522ms restartTime=-2h12m1s568ms createdFromFg=false
    restartCount=1 restartDelay=-4d3h39m23s971ms nextRestartTime=-2h12m1s847ms crashCount=0
    Bindings:
    * IntentBindRecord{74aba29 CREATE}:
      intent={xflg=0x4 cmp=com.sina.weibo/.HotEventService}
      binder=android.os.BinderProxy@91616a7
      requested=true received=true hasBound=true doRebind=false
      * Client AppBindRecord{578b754 ProcessRecord{c301933 29799:com.sina.weibo:pushservice/u0a236}}
        Per-process Connections:
          ConnectionRecord{88b4db2 u0 CR BALF com.sina.weibo/.HotEventService:@d61b3bd flags=0x201}
      * Client AppBindRecord{b39d6fd ProcessRecord{fae235a 29967:com.sina.weibo/u0a236}}
        Per-process Connections:
          ConnectionRecord{878e5ff u0 CR BALF com.sina.weibo/.HotEventService:@692791e flags=0x201}
    All Connections:
      ConnectionRecord{878e5ff u0 CR BALF com.sina.weibo/.HotEventService:@692791e flags=0x201}
      ConnectionRecord{88b4db2 u0 CR BALF com.sina.weibo/.HotEventService:@d61b3bd flags=0x201}

  Connection bindings to services:
  * ConnectionRecord{f6c54c2 u0 CR com.sina.weibo/com.xiaomi.push.service.XMPushService:@352d0d flags=0x1}
    binding=AppBindRecord{9a8e366 com.sina.weibo/com.xiaomi.push.service.XMPushService:com.sina.weibo}
    conn=android.os.BinderProxy@352d0d flags=0x1
    ongoingCalls=false
  * ConnectionRecord{54514d1 u0 CR com.sina.weibo/com.xiaomi.push.service.XMPushService:@3ddb7f8 flags=0x1}
    binding=AppBindRecord{fbcb8a8 com.sina.weibo/com.xiaomi.push.service.XMPushService:com.sina.weibo:remote}
    conn=android.os.BinderProxy@3ddb7f8 flags=0x1
    ongoingCalls=false
  * ConnectionRecord{878e5ff u0 CR BALF com.sina.weibo/.HotEventService:@692791e flags=0x201}
    binding=AppBindRecord{b39d6fd com.sina.weibo/.HotEventService:com.sina.weibo}
    conn=android.os.BinderProxy@692791e flags=0x201
    ongoingCalls=false
  * ConnectionRecord{c1b3095 u0 CR com.sina.weibo/com.xiaomi.push.service.XMPushService:@a77984c flags=0x1}
    binding=AppBindRecord{d8dffc1 com.sina.weibo/com.xiaomi.push.service.XMPushService:com.sina.weibo:pushservice}
    conn=android.os.BinderProxy@a77984c flags=0x1
    ongoingCalls=false
  * ConnectionRecord{88b4db2 u0 CR BALF com.sina.weibo/.HotEventService:@d61b3bd flags=0x201}
    binding=AppBindRecord{578b754 com.sina.weibo/.HotEventService:com.sina.weibo:pushservice}
    conn=android.os.BinderProxy@d61b3bd flags=0x201
    ongoingCalls=false
\```

查看 HotEventService 的底层代码逻辑，发现它放弃了直接 start，而是巧妙地通过跨进程的 bindService 机制启动。只要 Client 端发起 Bind，系统就会拉起目标 Service 所在的进程。

![HotEventService BindService](https://bbs.kanxue.com/upload/attach/202604/920134_RJFDN34EKZ4WYP2.webp)

![HotEventService BindService](https://bbs.kanxue.com/upload/attach/202604/920134_H8HR7YDW3YNRES7.webp)

## 进程拉活监控：ContentProvider + Binder 死亡传输的无限循环

至此，进程已经可以启动并在后台驻留。但如果用户手动划掉卡片，或者系统强杀进程怎么办？APP 祭出了最后的大招：底层 Binder 死亡监听 + ContentProvider 唤醒。

使用 FRIDA 对 APP 进行了注入调试，手动 KILL 掉目标进程后，发现进程几乎是瞬间自动重启。

追踪其调用链发现，在 AMBinderHolder 类中，APP 调用了底层的 linkToDeath 注册了 DeathRecipient（死亡通知接收器）。这是一种极其底层的 IPC 监控手段。

![ContentProvider Binder](https://bbs.kanxue.com/upload/attach/202604/920134_SH9HC9PAQXAATT5.webp)

![ContentProvider Binder](https://bbs.kanxue.com/upload/attach/202604/920134_27P7KQVWW43S7WY.webp)

当进程还在存活时，守护类 GroundStateMonitorImpl 会对 com.sina.weibo.appmonitor.provider 这个 ContentProvider 发起查询操作，以此获取到目标进程的 Binder 代理对象。

![ContentProvider Binder](https://bbs.kanxue.com/upload/attach/202604/920134_UNDQHHYA3H2DS8K.webp)

AppMonitorProvider 返回的实际上是一个自定义的 IAppMonitorBinder。

![ContentProvider Binder](https://bbs.kanxue.com/upload/attach/202604/920134_EVQH9DCYWZYY5EE.webp)

核心复活逻辑：当内核发现目标进程（主进程或推送进程）消失时，Binder 驱动会立即向注册了 linkToDeath 的端回调 binderDied 方法。这个回调会瞬间触发 GroundStateMonitorImpl 再次发起对 Provider 的查询 (query)。而查询一个未启动的 ContentProvider，系统会主动拉起该 Provider 所在的进程。

这就形成了一个完美的死循环：进程被杀 -> 触发 binderDied -> 守护进程查询 Provider -> 系统拉起被杀进程 -> 重新绑定 linkToDeath -> 再次等待被杀。

## 链路还原

AndroidManifest.xml

```python
<?xml version="1.0" encoding="utf-8"?>
&lt;manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools"&gt;

    &lt;uses-permission android:name="android.permission.GET_ACCOUNTS" /&gt;
    &lt;uses-permission android:name="android.permission.MANAGE_ACCOUNTS" /&gt;
    &lt;uses-permission android:name="android.permission.AUTHENTICATE_ACCOUNTS" /&gt;
    &lt;uses-permission android:name="android.permission.READ_SYNC_SETTINGS" /&gt;
    &lt;uses-permission android:name="android.permission.WRITE_SYNC_SETTINGS" /&gt;

    &lt;application
        android:allowBackup="true"
        android:dataExtractionRules="@xml/data_extraction_rules"
        android:fullBackupContent="@xml/backup_rules"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.KA"&gt;

        &lt;activity
            android:name=".MainActivity"
            android:exported="true"&gt;
            &lt;intent-filter&gt;
                &lt;action android:name="android.intent.action.MAIN" /&gt;
                &lt;category android:name="android.intent.category.LAUNCHER" /&gt;
            &lt;/intent-filter&gt;
        &lt;/activity&gt;

        &lt;provider
            android:name=".StubProvider"
            android:authorities="com.test.ka.sync.authority"
            android:exported="true"
            android:process=":remote"
            /&gt;
        &lt;service
            android:name=".GuardSyncService"
            android:exported="true"&gt;
            &lt;intent-filter&gt;
                &lt;action android:name="android.content.SyncAdapter" /&gt;
            &lt;/intent-filter&gt;
            &lt;meta-data
                android:name="android.content.SyncAdapter"
                android:resource="@xml/sync_adapter" /&gt;
        &lt;/service&gt;
        &lt;service
            android:name=".AuthService"
            android:exported="true"&gt;
            &lt;intent-filter&gt;
                &lt;action android:name="android.accounts.AccountAuthenticator" /&gt;
            &lt;/intent-filter&gt;
            &lt;meta-data
                android:name="android.accounts.AccountAuthenticator"
                android:resource="@xml/authenticator" /&gt;
        &lt;/service&gt;

        &lt;service
            android:name=".PushService"
            android:persistent="true"
            android:exported="true"
            android:process=":push"&gt;
            &lt;intent-filter&gt;
                &lt;action android:name="com.test.ka.push.service"/&gt;
                &lt;category android:name="android.category.DEFAULT"/&gt;
            &lt;/intent-filter&gt;
        &lt;/service&gt;

    &lt;/application&gt;

&lt;/manifest&gt;
\```

sync_adapter.xml

```python
<?xml version ="1.0" encoding="utf-8"?>
&lt;sync-adapter xmlns:android="http://schemas.android.com/apk/res/android"
    android:contentAuthority="com.test.ka.sync.authority"
    android:accountType="com.test.ka.account"
    android:isAlwaysSyncable="true" /&gt;
\```

authenticator.xml

```python
<?xml version ="1.0" encoding="utf-8"?>
&lt;account-authenticator xmlns:android="http://schemas.android.com/apk/res/android"
    android:accountType="com.test.ka.account"
    android:icon="@mipmap/ic_launcher"
    android:label="@string/app_name"
    android:smallIcon="@mipmap/ic_launcher" /&gt;
\```

AuthService.java

```python
package com.test.ka;

import android.accounts.AbstractAccountAuthenticator;
import android.accounts.Account;
import android.accounts.AccountAuthenticatorResponse;
import android.accounts.AccountManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.IBinder;
import android.util.Log;

public class AuthService extends Service {

    private Authenticator mAuthenticator;

    @Override
    public void onCreate() {
        super.onCreate();
        mAuthenticator = new Authenticator(this);
    }

    @Override
    public IBinder onBind(Intent intent) {
        return mAuthenticator.getIBinder();
    }

    /**
     * 账户认证器实现
     * 只需提供最基本的空实现，因为本 Demo 不需要真正的账户登录界面
     */
    private static class Authenticator extends AbstractAccountAuthenticator {

        public Authenticator(Context context) {
            super(context);
        }

        @Override
        public Bundle editProperties(AccountAuthenticatorResponse response, String accountType) {
            return Bundle.EMPTY;
        }

        @Override
        public Bundle addAccount(AccountAuthenticatorResponse response, String accountType,
                                 String authTokenType, String[] requiredFeatures, Bundle options) {
            Bundle result = new Bundle();
            result.putString(AccountManager.KEY_ACCOUNT_NAME, "keep_alive_account");
            result.putString(AccountManager.KEY_ACCOUNT_TYPE, accountType);
            return result;
        }

        @Override
        public Bundle confirmCredentials(AccountAuthenticatorResponse response, Account account,
                                         Bundle options) {
            return Bundle.EMPTY;
        }

        @Override
        public Bundle getAuthToken(AccountAuthenticatorResponse response, Account account,
                                   String authTokenType, Bundle options) {
            return Bundle.EMPTY;
        }

        @Override
        public String getAuthTokenLabel(String authTokenType) {
            return null;
        }

        @Override
        public Bundle updateCredentials(AccountAuthenticatorResponse response, Account account,
                                        String authTokenType, Bundle options) {
            return Bundle.EMPTY;
        }

        @Override
        public Bundle hasFeatures(AccountAuthenticatorResponse response, Account account,
                                  String[] features) {
            return Bundle.EMPTY;
        }
    }
}
\```

GuardSyncService.java

```python
package com.test.ka;

import android.accounts.Account;
import android.app.Service;
import android.content.AbstractThreadedSyncAdapter;
import android.content.ContentProviderClient;
import android.content.Context;
import android.content.Intent;
import android.content.SyncResult;
import android.os.Bundle;
import android.os.IBinder;

public class GuardSyncService extends Service {
    private static SyncAdapter mAdapter = null;

    @Override
    public void onCreate() {
        if (mAdapter == null) mAdapter = new SyncAdapter(getApplicationContext(), true);
    }

    @Override
    public IBinder onBind(Intent intent) {
        return mAdapter.getSyncAdapterBinder();
    }

    private class SyncAdapter extends AbstractThreadedSyncAdapter {
        public SyncAdapter(Context context, boolean autoInit) {
            super(context, autoInit);
        }

        @Override
        public void onPerformSync(Account account, Bundle extras, String auth,
                                  ContentProviderClient provider, SyncResult result) {
            // 系统唤醒后，第一时间触发 MonitorManager 的拉活逻辑
            MonitorManager.rebirth(getContext());
        }
    }
}
\```

MonitorManager.java

```python
package com.test.ka;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.IBinder;
import android.os.RemoteException;
import android.util.Log;

public class MonitorManager {
    private static final String TAG = "MonitorManager";
    private static final String PROVIDER_URI = "content://com.test.ka.sync.authority";

    // 【关键】必须持有强引用，防止被 GC 回收
    private static IBinder.DeathRecipient sDeathRecipient;
    private static IBinder sBinder; // 建议同时持有 Binder 引用

    public static void bindDeathRecipient(Context context, IBinder binder) {
        if (binder == null) return;

        sBinder = binder;

        // 创建并保存到静态变量中
        sDeathRecipient = new IBinder.DeathRecipient() {
            @Override
            public void binderDied() {
                Log.e(TAG, "!!! 检测到进程死亡，执行同步拉活逻辑 !!!");

                // 死亡后移除旧的监听
                if (sBinder != null) {
                    sBinder.unlinkToDeath(sDeathRecipient, 0);
                }
                // 执行拉活
                rebirth(context);
            }
        };

        try {
            binder.linkToDeath(sDeathRecipient, 0);
            Log.d(TAG, "linkToDeath 闭环注册成功");
        } catch (RemoteException e) {
            Log.e(TAG, "注册失败，进程可能已经挂了，立即拉活");
            rebirth(context);
        }
    }

    public static void rebirth(Context context) {
        // 建议在子线程操作，防止主线程卡顿
        new Thread(() -> {
            try {
                Log.d(TAG, "开始查询 Provider 进行拉活...");
                Cursor cursor = context.getContentResolver().query(
                        Uri.parse(PROVIDER_URI), null, null, null, null);

                if (cursor != null) {
                    IBinder binder = cursor.getExtras().getBinder("_appmonitor_|_binder_");
                    cursor.close(); // 拿到 Binder 后可以关闭 Cursor

                    if (binder != null) {
                        bindDeathRecipient(context, binder);
                        Log.d(TAG, "进程拉活成功，新 Binder 已就绪");
                    }
                } else {
                    Log.e(TAG, "rebirth cursor is null");
                }
            } catch (Exception e) {
                Log.e(TAG, "拉活异常: " + e.getMessage());
            }
        }).start();
    }
}
\```

StubProvider.java

```python
package com.test.ka;

import android.content.ComponentName;
import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.IBinder;
import android.util.Log;

public class StubProvider extends ContentProvider {

    // private static IBinder serviceBinder;

    @Override
    public boolean onCreate() {
        Intent intent = new Intent(getContext(), PushService.class);
        getContext().bindService(intent, new ServiceConnection() {
            @Override
            public void onServiceConnected(ComponentName name, IBinder service) {
                // serviceBinder = service;
            }
            @Override
            public void onServiceDisconnected(ComponentName name) {
                // serviceBinder = null;
            }
        }, Context.BIND_AUTO_CREATE);
        return true;
    }

    @Override
    public Cursor query(Uri uri, String[] p, String s, String[] sa, String so) {
        MatrixCursor cursor = new MatrixCursor(new String[]{"col"});
        Bundle bundle = new Bundle();
        bundle.putBinder("_appmonitor_|_binder_", new IKeepAliveInterface.Stub() {
            @Override
            public void ping() {
                Log.e("IKeepAliveInterface", "time:" + System.currentTimeMillis());
            }
        }.asBinder());
        cursor.setExtras(bundle);
        return cursor;
    }

    @Override public String getType(Uri uri) { return null; }
    @Override public Uri insert(Uri uri, ContentValues v) { return null; }
    @Override public int delete(Uri uri, String s, String[] sa) { return 0; }
    @Override public int update(Uri uri, ContentValues v, String s, String[] sa) { return 0; }
}
\```

PushService.java

```python
package com.test.ka;

import static java.lang.Thread.sleep;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Binder;
import android.os.IBinder;
import android.util.Log;

public class PushService extends Service {

    public class LocalBinder extends Binder {
        PushService getService() {
            return PushService.this;
        }
    }

    private final IBinder binder = new LocalBinder();

    @Override
    public IBinder onBind(Intent intent) {
        Log.e("PushService","PushService onBind: " + "time:" + System.currentTimeMillis());
        return binder;
    }

    @Override
    public void onCreate() {
        Log.e("PushService","PushService onCreate: " + "time:" + System.currentTimeMillis());
        run();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.e("PushService","PushService onStartCommand: " + "time:" + System.currentTimeMillis());
        return START_NOT_STICKY;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
    }

    public void run(){
        Thread mthread = new Thread(new Runnable() {
            @Override
            public void run() {
                while (true){
                    Log.e("PushService","PushService run: " + "time:" + System.currentTimeMillis());
                    try {
                        sleep(1000);
                    } catch (InterruptedException e) {
                        throw new RuntimeException(e);
                    }
                }
            };
        });
        mthread.start();
    }

}
\```

IKeepAliveInterface.aidl

```python
// IKeepAliveInterface.aidl
package com.test.ka;

// Declare any non-default types here with import statements

interface IKeepAliveInterface {
    /**
     * Demonstrates some basic types that you can use as parameters
     * and return values in AIDL.
     */
    void ping();
}
\```

MainActivity.java

```python
package com.test.ka;

import androidx.appcompat.app.AppCompatActivity;
import android.accounts.Account;
import android.accounts.AccountManager;
import android.content.ContentResolver;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.TextView;

import com.test.ka.databinding.ActivityMainBinding;

public class MainActivity extends AppCompatActivity {

    private ActivityMainBinding binding;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        binding = ActivityMainBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());

        // Example of a call to a native method
        TextView tv = binding.sampleText;
        tv.setText("点击登录");
        tv.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                addAccount();
            }
        });
    }

    private void addAccount() {
        AccountManager am = AccountManager.get(this);
        Account account = new Account("keep_alive_account", "com.test.ka.account");
        boolean success = am.addAccountExplicitly(account, null, null);
        if (success) {
            Log.e("AUTH", "账号添加成功");
        } else {
            Log.e("AUTH", "账号添加失败，可能账号已存在或类型定义错误");
        }
        if (success) {
            // 设置同步自动开启
            ContentResolver.setIsSyncable(account, "com.test.ka.sync.authority", 1);
            ContentResolver.setSyncAutomatically(account, "com.test.ka.sync.authority", true);
            ContentResolver.addPeriodicSync(account, "com.test.ka.sync.authority", new Bundle(), 900);
        }
    }

}
\```

查看账户信息:

```python
adb shell dumpsys account
User UserInfo{0:机主:4c13}:
  Accounts: 4
    Account {name=keep_alive_account, type=com.test.ka.account}

  RegisteredServicesCache: 9 services
    ServiceInfo: AuthenticatorDescription {type=com.test.ka.account}, ComponentInfo{com.test.ka/com.test.ka.AuthService}, uid 10048, lastUpdateTime 1776149776942
\```

查看已注册JobId=298的定时任务。

```python
adb shell dumpsys content

JobId=298 keep_alive_account/com.test.ka.account u0 [com.test.ka.sync.authority] PERIODIC Reason=Periodic (period=15m00s flex=36s) Owner={u0a48 com.test.ka [10]}

Account keep_alive_account u0 com.test.ka.account
=======================================================================
Authority                   Syncable  Enabled  Stats  Loc  Poll  Per  Feed  User  Othr  Tot  Fail  Can  Time  Last Sync            Backoff
------------------------------------------------------------------------------------------------------------------------------------------
com.test.ka.sync.authority  1         true     Total  0    0     160  0     0     1     161  0     0    33s   PERIODIC SUCCESS
                                               Today             69                     69              21s   2026-04-14 16:16:41
                                               Yestr             64                     64              9s

Recent Sync History
(SERVER is now split up to FEED and OTHER)
  #2  : 2026-04-14 16:16:40 PERIODIC    0.7s            keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #3  : 2026-04-14 16:13:48 PERIODIC    0.7s     02:52  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #8  : 2026-04-14 15:52:56 PERIODIC    0.8s     20:52  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #9  : 2026-04-14 15:50:33 PERIODIC    0.8s     02:22  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #10 : 2026-04-14 15:48:02 PERIODIC    0.7s     02:30  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #11 : 2026-04-14 15:41:01 PERIODIC    0.8s     07:01  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #12 : 2026-04-14 15:39:55 PERIODIC    0.7s     01:06  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #13 : 2026-04-14 15:35:47 PERIODIC    0.7s     04:08  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #14 : 2026-04-14 15:34:14 PERIODIC    0.8s     01:32  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #15 : 2026-04-14 15:32:56 PERIODIC    0.0s     01:18  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #16 : 2026-04-14 15:32:55 PERIODIC    0.8s         0  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #18 : 2026-04-14 15:30:30 PERIODIC    0.8s     02:25  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #19 : 2026-04-14 15:28:36 PERIODIC    0.4s     01:53  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #20 : 2026-04-14 15:27:59 PERIODIC    0.4s        37  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #21 : 2026-04-14 15:25:02 PERIODIC    0.7s     02:56  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #22 : 2026-04-14 15:11:58 PERIODIC    0.4s     13:04  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic
  #23 : 2026-04-14 15:10:59 PERIODIC    0.7s        58  keep_alive_account/com.test.ka.account u0  com.test.ka.sync.authority            Periodic

Per Adapter History
(SERVER is now split up to FEED and OTHER)
  keep_alive_account/com.test.ka.account u0 [com.test.ka.sync.authority]
    Per source last syncs:
         OTHER  Success: 2026-04-12 17:09:24  Failure: N/A
         LOCAL  Success: N/A  Failure: N/A
          POLL  Success: N/A  Failure: N/A
          USER  Success: N/A  Failure: N/A
      PERIODIC  Success: 2026-04-14 16:16:41  Failure: N/A
          FEED  Success: N/A  Failure: N/A
    Last syncs:
      2026-04-14 16:16:41 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 16:13:49 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 15:52:57 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 15:50:34 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 15:48:03 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 15:41:02 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 15:39:56 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 15:35:47 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 15:34:15 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]
      2026-04-14 15:32:56 success Source=PERIODIC Elapsed=0s Reason=Periodic Extras=[]

Sync adapters for UserInfo{0:机主:4c13}:
  ServiceInfo: SyncAdapterType {name=com.test.ka.sync.authority, type=com.test.ka.account, userVisible=true, supportsUploading=true, isAlwaysSyncable=true, allowParallelSyncs=false, settingsActivity=null, packageName=com.test.ka}, ComponentInfo{com.test.ka/com.test.ka.GuardSyncService}, uid 10048, lastUpdateTime 1776149776942
\```

手动运行定时任务 adb shell cmd jobscheduler run -n SyncManager -u 0 -f android 298 查看 SERVICES 运行信息:

```python
adb shell dumpsys activity services com.test.ka
ACTIVITY MANAGER SERVICES (dumpsys activity services)
  User 0 active services:
  * ServiceRecord{265a6a u0 com.test.ka/.PushService c:com.test.ka}
    intent={cmp=com.test.ka/.PushService}
    packageName=com.test.ka
    processName=com.test.ka:push
    targetSdkVersion=36
    baseDir=/data/app/~~gHOofbefUmqembSX1t9wyQ==/com.test.ka-slpaBq1J0GeUE_-CoumVLg==/base.apk
    dataDir=/data/user/0/com.test.ka
    app=ProcessRecord{7dcfb5b 27520:com.test.ka:push/u0a48}
    useNewWiuLogic_forCapabilities()=true
    useNewWiuLogic_forStart()=true
    useNewBfslLogic()=true
    mAllowWiu_noBinding=DENIED
    mAllowWiu_inBindService=DENIED
    mAllowWiu_byBindings=DENIED
    getFgsAllowWiu_legacy=DENIED
    getFgsAllowWiu_new=DENIED
    getFgsAllowWiu_forStart=DENIED
    getFgsAllowWiu_forCapabilities=DENIED
    allowUiJobScheduling=false
    recentCallingPackage=com.test.ka
    recentCallingUid=10048
    mAllowStart_noBinding=DENIED
    mAllowStart_inBindService=DENIED
    mAllowStart_byBindings=DENIED
    getFgsAllowStart_legacy=DENIED
    getFgsAllowStart_new=DENIED
    getFgsAllowStart=DENIED
    startForegroundCount=0
    infoAllowStartForeground=[callingPackage: com.test.ka; callingUid: 10048; uidState: TRNB; uidBFSL: n/a; intent: Intent { xflg=0x4 cmp=com.test.ka/.PushService }; code:DENIED; tempAllowListReason:&lt;null&gt;; allowWiu:-1; targetSdkVersion:36; callerTargetSdkVersion:36; startForegroundCount:0; bindFromPackage:null: isBindService:true]
    createTime=-44s144ms startingBgTimeout=--
    lastActivity=-43s781ms restartTime=-43s781ms createdFromFg=true
    Bindings:
    * IntentBindRecord{60add4 CREATE}:
      intent={xflg=0x4 cmp=com.test.ka/.PushService}
      binder=android.os.BinderProxy@418cb7d
      requested=true received=true hasBound=true doRebind=false
      * Client AppBindRecord{c3cea72 ProcessRecord{f1212e3 27491:com.test.ka:remote/u0a48}}
        Per-process Connections:
          ConnectionRecord{332a055 u0 CR com.test.ka/.PushService:@c0bef0c flags=0x1}
    All Connections:
      ConnectionRecord{332a055 u0 CR com.test.ka/.PushService:@c0bef0c flags=0x1}

  Connection bindings to services:
  * ConnectionRecord{332a055 u0 CR com.test.ka/.PushService:@c0bef0c flags=0x1}
    binding=AppBindRecord{c3cea72 com.test.ka/.PushService:com.test.ka:remote}
    conn=android.os.BinderProxy@c0bef0c flags=0x1
    ongoingCalls=false
\```

*（注：仅在 PIXEL 6 + ANDROID API 36 下测试）*

## 总结

这款头部 APP 的保活链条极其清晰且环环相扣，几乎榨干了 Android 系统为了兼容性和功能性留下的所有后门：

突破休眠机制： 利用 Account SyncAdapter 周期性唤醒进程，确保有一个“种子”存活。

突破启动限制： 放弃早已禁用的 startService，改用 bindService 拉起常驻进程。

突破强杀机制： 利用底层的 linkToDeath + ContentProvider 的系统特性，实现微秒级的进程被杀复活。

从逆向对抗的角度来看，这套组合拳非常精妙；但从用户体验和系统初衷来看，这也是导致 Android 手机后台耗电、性能下降的罪魁祸首之一。

---

# 回复

## 回复 by LQ6H (#2)

*2026-4-14 18:45*

666

## 回复 by 毛毛毛毛虫 (#3)

*2026-4-14 19:12*

学习一下

## 回复 by kagayaki (#4)

*2026-4-14 19:15*

666

## 回复 by mb_gjmllnia (#5)

*2026-4-14 19:34*

6666

## 回复 by linclsky (#6)

*2026-4-14 23:14*

666

## 回复 by mb_vghyvbhn (#7)

*2026-4-15 09:36*

666

## 回复 by Zepp7289 (#8)

*2026-4-15 09:40*

tql

## 回复 by wangzehua (#9)

*2026-4-15 10:06*

66666

## 回复 by k4y0z (#10)

*2026-4-15 10:08*

666

## 回复 by git_86302JokerXsh (#11)

*2026-4-15 10:08*

6666

## 回复 by iBa0 (#12)

*2026-4-15 10:23*

13

## 回复 by 随风而行aa (#13)

*2026-4-15 10:41*

11

## 回复 by FMNS (#14)

*2026-4-15 11:13*

6666

## 回复 by mb_fidppcok (#15)

*2026-4-15 11:14*

学习一下

## 回复 by space_std (#16)

*2026-4-15 11:47*

1

## 回复 by Imxz (#17)

*2026-4-15 11:58*

tql

## 回复 by 丶咖啡猫丶 (#18)

*2026-4-15 16:07*

666

## 回复 by guijingwen (#19)

*2026-4-15 16:58*

66

## 回复 by 驱动玩家 (#20)

*2026-4-16 00:00*

666

## 回复 by HELLC (#21)

*2026-4-16 01:53*

666

## 回复 by netwolfer (#22)

*2026-4-16 10:00*

棒，测试机型是？

## 回复 by babyrjw (#23)

*2026-4-16 10:07*

学习一下

## 回复 by 努力8点 (#24)

*2026-4-16 10:52*

6+666

## 回复 by mb_hpnnkjnq (#25)

*2026-4-16 12:41*

666

## 回复 by 秃顶 (#26)

*2026-4-16 16:34*

666

## 回复 by fangliangz (#27)

*2026-4-16 16:39*

666

## 回复 by 不具名的悲伤 (#28)

*2026-4-16 17:37*

6

## 回复 by 4Chan (#29)

*2026-4-16 20:02*

666

## 回复 by wx_听书人 (#30)

*2026-4-17 00:52*

66666

## 回复 by alds (#31)

*2026-4-17 07:57*

6

## 回复 by pan_634488 (#32)

*2026-4-17 09:56*

666

## 回复 by 4Chan (#33)

*2026-4-17 11:01*

666

## 回复 by wohowo (#34)

*2026-4-17 11:06*

11111111

## 回复 by wohowo (#35)

*2026-4-17 11:08*

一看就是腾讯的，只有狗马化腾才这么狗

## 回复 by mb_jnmxfjku (#36)

*2026-4-17 11:10*

666

## 回复 by veluboii (#37)

*2026-4-18 01:00*

666

## 回复 by zxc (#38)

*2026-4-18 08:08*

666

## 回复 by jdong (#39)

*2026-4-18 10:03*

666666

## 回复 by PPTV (#40)

*2026-4-18 10:44*

666

## 回复 by 温泉划水鱼 (#41)

*2026-4-18 12:12*

全网最尊重某大厂的佬

## 回复 by asm_zhang (#42)

*2026-4-20 09:32*

666

## 回复 by anywhere杨 (#43)

*2026-4-20 15:05*

999

## 回复 by tjytjy (#44)

*2026-4-20 16:46*

666

## 回复 by A0tem (#45)

*2026-4-20 16:55*

看看

## 回复 by mb_yvylrygw (#46)

*2026-4-20 17:26*

666

## 回复 by mb_ktasfpbp (#47)

*2026-4-20 18:52*

6666

## 回复 by wx_段利军 (#48)

*2026-4-20 20:17*

666

## 回复 by mb_elqwyvnm (#49)

*2026-4-21 04:50*

努力8点
  24 楼
6+666

## 回复 by LoginUser (#50)

*2026-4-21 09:25*

感谢分享

## 回复 by mb_qimctavn (#51)

*2026-4-21 12:40*

6

## 回复 by mb_dwksysag (#52)

*2026-4-21 12:48*

很厉害

## 回复 by mb_tcheuwvg (#53)

*2026-4-21 14:29*

666

## 回复 by mb_euhyowpw (#54)

*2026-4-21 17:23*

666

## 回复 by Ankeys (#55)

*2026-4-22 09:18*

666

## 回复 by Elenia (#56)

*2026-4-22 10:08*

感谢分享

## 回复 by mJqalJqN (#57)

*2026-4-24 14:33*

1

## 回复 by wx_kx97684 (#58)

*2026-4-24 19:38*

666

## 回复 by mb_ggnlrzcs (#59)

*2026-4-24 23:56*

双击666

## 回复 by mb_jfpnwwjp (#60)

*2026-4-26 11:25*

学习一下

## 回复 by mb_qqihqaoo (#61)

*2026-4-26 12:50*

6666666

## 回复 by 汤猿猿 (#62)

*2026-4-26 14:31*

6666666

## 回复 by wx_huhu_859 (#63)

*2026-4-26 15:26*

11

## 回复 by mb_jhnzmdhn (#64)

*2026-4-27 12:23*

666

## 回复 by mb_juxkxhua (#65)

*2026-4-27 22:59*

666

## 回复 by bbpk (#66)

*2026-4-27 23:12*

666

## 回复 by jerrychoi (#67)

*2026-4-28 14:49*

666+666

## 回复 by jerrychoi (#68)

*2026-4-28 14:49*

大佬V5

## 回复 by jerrychoi (#69)

*2026-4-28 14:52*

大佬V5，学习中

## 回复 by wx_岁月真好_475628 (#70)

*2026-4-28 17:09*

6666666

## 回复 by wx_岁月真好_475628 (#71)

*2026-4-28 17:10*

6666666

## 回复 by wx_岁月真好_475628 (#72)

*2026-4-28 17:10*

6666666

## 回复 by wx_岁月真好_475628 (#73)

*2026-4-28 17:12*

6666666

## 回复 by wx_岁月真好_475628 (#74)

*2026-4-28 17:15*

6666666

## 回复 by xiaofo (#75)

*2026-4-28 17:53*

666

## 回复 by xiaofo (#76)

*2026-4-28 17:54*

666好

## 回复 by javac_kylin (#77)

*2026-4-30 11:33*

感谢分享

## 回复 by mb_ohbogvqs (#78)

*2026-5-5 11:01*

666

## 回复 by mb_ohbogvqs (#79)

*2026-5-5 11:01*

666

## 回复 by mb_ohbogvqs (#80)

*2026-5-5 11:03*

牛逼啊

## 回复 by mb_ecoknywz (#81)

*2026-5-5 20:36*

太厉害了阿

## 回复 by mb_colgshpu (#82)

*2026-5-7 16:38*

666

## 回复 by mb_vwnqcfsr (#83)

*2026-5-8 09:37*

666

## 回复 by 墨穹呢 (#84)

*2026-5-8 23:27*

感谢分享

## 回复 by wx_三生三世 (#85)

*2026-5-11 19:33*

学习

## 回复 by wx_Oh.漏 (#86)

*2026-5-11 19:56*

6666

## 回复 by mb_iikvttwp (#87)

*2026-5-11 20:06*

666

## 回复 by spygg (#88)

*2026-5-11 20:58*

还真是学习到了

## 回复 by 0xCodeMaster (#89)

*2026-5-12 19:41*

adwad

## 回复 by 0xCodeMaster (#90)

*2026-5-12 19:44*

真的牛皮，大佬的思路与众不同

## 回复 by kingkongk (#91)

*2026-5-12 20:32*

666

## 回复 by 青枫留念 (#92)

*2026-5-13 11:38*

3

## 回复 by mb_gyfyvpbi (#93)

*2026-5-13 17:12*

学习一下

## 回复 by 有的是钱啊 (#94)

*2026-5-13 18:51*

1111

## 回复 by stayupup (#95)

*2026-5-13 19:01*

学习一下

## 回复 by kxnight (#96)

*2026-5-14 10:33*

学习一下

## 回复 by HexGadget (#97)

*2026-5-14 10:45*

666

## 回复 by 末日大哥 (#98)

*2026-5-14 10:53*

666学习一下

## 回复 by 哥倫布 (#99)

*2026-5-23 06:13*

666

## 回复 by mb_qzxqnktk (#100)

*2026-5-31 23:08*

666

## 回复 by 简单的简单 (#101)

*2026-5-31 23:20*

666

## 回复 by zzzzz1 (#102)

*2026-6-2 13:11*

6

## 回复 by mb_xgoaxxei (#103)

*2026-6-2 18:48*

6666666666

## 回复 by tigericon (#104)

*2026-6-3 09:50*

66

## 回复 by 三点水的湫 (#105)

*2026-6-3 11:03*

666

## 回复 by mb_4nrpVMxJ (#106)

*2026-6-3 13:06*

666

## 回复 by liqianjie (#107)

*2026-6-3 18:21*

666

## 回复 by zizzy.zhao (#108)

*2026-6-5 14:42*

666

## 回复 by liowmark (#109)

*2026-6-5 15:28*

666

## 回复 by hanjiefang (#110)

*2026-6-5 15:37*

1

## 回复 by CheRevir (#111)

*2026-6-5 16:05*

6666

## 回复 by mb_xyoslnox (#112)

*2026-6-5 16:44*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by Tanuyoki0 (#113)

*2026-6-6 22:37*

学习一下

## 回复 by Freax (#114)

*2026-6-16 15:58*

6

## 回复 by 哥倫布 (#115)

*2026-6-22 15:46*

666

## 回复 by JoshuaC (#116)

*2026-6-22 18:45*

666666666

## 回复 by 张恒_884729 (#117)

*2026-6-25 21:30*

666666

## 回复 by git_50054gnemyg7221 (#118)

*2026-6-26 11:44*

太强了

## 回复 by mb_dlljjfcf (#119)

*2026-6-27 08:17*

6666谢了

## 回复 by mb_bdfwnwgm (#120)

*2026-7-21 11:33*

666

## 回复 by tt8369 (#121)

*2026-7-21 13:40*

学习了

## 回复 by jonloong (#122)

*2026-7-21 19:27*

666

## 回复 by simpleness (#123)

6

## 回复 by git_78819sinyu1012 (#124)

667688
