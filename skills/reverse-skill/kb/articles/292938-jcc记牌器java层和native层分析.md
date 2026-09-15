---
title: '[原创]jcc记牌器java层和native层分析'
url: https://bbs.kanxue.com/thread-292938.htm
tid: 292938
author: Ann945
date: '2026-09-14'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-09-15T08:48:59+00:00'
replies: 13
attachments:
- {filename: libdemo.so, aid: '405105', path: ../attachments/292938/libdemo.so, url: 'https://bbs.kanxue.com/attach-download-405105-5dd435de523a1adcece550dc25c8c801@LX+Epf18O+hy/Zb5fAucEQ==.htm', size: 5.33MB，12次下载, downloaded: false}
---

| 项 | 值 |
|-|-|
| 样本 | `jcc记牌器.apk` |
| SHA-256 | `0df71b48c2daf299f2fb82e78cd8adb63dfcc88d43d854b1d561bb34a38e70d0` |
| 包名 | `com.android.support`（伪装） |
| versionName / Code | `632` / `67` |
| 目标应用 | `com.脱敏.jkchess`（） |
| 分析工具 | JADX-GUI + jadx-ai-mcp（Java 层）、IDA Pro + ida-pro-mcp（native 层）、strings/nm/readelf |
| 分析日期 | 2026-09-13 |

---

## 目录

- 零、样本总览与整体架构
	- 0.1 样本信息
	- 0.2 双进程架构
	- 0.3 功能清单（作者自述）
	- 0.4 代码模块清单
	- 0.5 技术栈与混淆情况
- 一、Root 提权与 So 注入链路
	- 1.0 端到端链路总览
	- 1.1 找 su：路径候选与 `adoptSuPrefix` 逻辑
	- 1.2 SELinux 处理
	- 1.3 Mount namespace：`GameDataLocation$Decision`、`applyRootMountNamespace`
	- 1.4 注入：文件落位、命令行、目标定位、成功判定
	- 1.5 守护与保活
	- 1.6 环境检测（模拟器）
- 二、Java 与注入 Native 的 IPC 协议
	- 2.0 一句话结论
	- 2.1 通道总览
	- 2.2 分帧与信封格式
	- 2.3 命令清单（App → native）
	- 2.4 推送清单（native → App）
	- 2.5 连接、握手、心跳、重连、超时
	- 2.6 诊断共享内存页（`DiagnosticSharedMemoryBridge`）
	- 2.7 游戏状态数据是怎么流回 App 的
	- 2.8 值得注意的实现细节
- 三、阵容推荐与羁绊计算
	- 3.0 一句话结论
	- 3.1 阵容数据从哪来
	- 3.2 羁绊计算 `TraitCalculator`（核心）
	- 3.3 阵容评分算法 `LineupRecommender`（核心）
	- 3.4 英雄 ID 体系 `HeroIdMapper`
	- 3.5 `OwnedHeroTracker`：场上英雄追踪
	- 3.6 `AutoLineupApplier`：自动应用阵容
	- 3.7 棋盘位置与 slot 表示
	- 3.8 商店预测 / 海克斯预测 / 对手预测：**Java 侧没有算法**
	- 3.9 其它相关资产文件
- 四、授权信任链与诊断上报
	- 4.1 一句话结论
	- 4.2 授权流程完整时序
	- 4.3 密码学归属：native 里有什么、Java 里有什么
	- 4.4 `nativeLicenseHeader` 生成的请求头，以及 `TrustTransport` 怎么用它
	- 4.5 `WigVerify` 的 native 方法：防伪 / 防篡改，还是别的？
	- 4.6 诊断上报体系
	- 4.7 反调试 / 反注入 / 完整性自校验
	- 4.8 本节要点小结
- 五、悬浮窗 UI、无障碍与配置体系
	- 5.1 悬浮窗服务是绝对主体
	- 5.2 防截屏 / 防录屏：反射调用隐藏 API
	- 5.3 无障碍服务：只用来吃按键
	- 5.4 配置持久化：双轨制
	- 5.5 语音播报链路
	- 5.6 其余 Java 侧子系统（一句话职责）
- 六、Native 层：四个 so 的分工与算法归属
	- 5.1 结论先行
	- 5.2 `libinject.so`：注入器
	- 5.3 `libdemo.so`：注入的游戏内运行时
	- 5.4 待确认的疑点
	- 6.7 IDA 静态分析补充（`libdemo.so`，IDB 已加载）
- 七、对手预测（下一场次对手）的实现
	- 7.0 一句话结论
	- 7.1 三个数据来源与优先级
	- 7.2 主力来源：每帧轮询 `preMatchData`
	- 7.3 兜底来源：钩 `SelectHighScore` 但不改行为
	- 7.4 IPC 载荷格式
	- 7.5 Java 侧只做选择，不做推算
	- 7.6 整体链路
	- 7.7 四个疑点的复查结果
- 八、是否存在「修改概率」的方法
	- 8.0 结论
	- 8.1 逐个核对：概率相关钩子的返回值
	- 8.2 观察容器机制：`byte_564A44` 标志位
	- 8.3 全库唯一的写内存路径
	- 8.4 那「指定海克斯 / 指定重铸」是怎么实现的

---

## 零、样本总览与整体架构

### 0.1 样本信息

| 项 | 值 |
|-|-|
| 文件 | `jcc记牌器.apk` |
|  |  |
| 大小 | 20,966,526 字节（约 20 MB） |
| SHA-256 | `0df71b48c2daf299f2fb82e78cd8adb63dfcc88d43d854b1d561bb34a38e70d0` |
| 包名 | `com.android.support`（伪装的系统支持库名） |
| versionName / versionCode | `632` / `67` |
| minSdk / targetSdk / compileSdk | 28 / 37 / 37 |
| 类总数 | 7815 |
| 自研类 | 2280（均在 `com.android.support.*`） |
|  |  |

包名 `com.android.support` 是刻意选择的伪装：真 AndroidX/Support 库的包名是 `android.support.*` 和 `androidx.*`，而本样本自研代码全部放在 `com.android.support.*` 下，在进程列表和包列表里看起来像系统组件。`AndroidManifest.xml` 里 `<queries>` 只声明了一个包：`com.脱敏.jkchess`（《金铲铲之战》）。

### 0.2 双进程架构

这是整个样本最核心的结构判断：**它不是单一进程的应用，而是「悬浮窗 App + 注入游戏进程的 native 运行时」的双端结构。**

```python
┌─────────────────────────────────────────┐
│  App 进程  com.android.support          │
│  （MainActivity / FloatingWindowService）│
│                                         │
│  · 悬浮窗 UI、所有设置面板               │
│  · root 工具链（su / mount namespace）   │
│  · 授权与网关通信（Java 侧）             │
│  · 诊断上报                              │
└──────────────┬──────────────────────────┘
               │
               │  ① 注入：libinject.so -pkg com.脱敏.jkchess
               │     -lib libdemo.so -pid N -dl_memfd
               │     （经 su，setenforce 0，memfd 无文件注入）
               ▼
┌─────────────────────────────────────────┐
│  游戏进程  com.脱敏.jkchess          │
│  （Unity + IL2CPP，libil2cpp.so）        │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │ libdemo.so（注入的运行时载荷）     │  │
│  │ · IL2CPP 方法 hook（FRandom 等）   │  │
│  │ · 商店/海克斯/重铸 预测算法        │  │
│  │ · 对手数据读取（PlayerListItem）   │  │
│  │ · 棋盘操作（拿牌/卖牌/换位）       │  │
│  │ · 信任链密码学实现                 │  │
│  └───────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │
               │  ② 通信：IPC v2（共享内存 + LocalSocket）
               │
               └──────────► 回到 App 进程（IPC v2：抽象 Unix socket + LocalSocket，JSON 帧）
\```

两端的分工决定了后面所有分析：

- **Java 侧不做算法**。Java 侧负责 UI、配置、root、授权、诊断，以及把用户操作序列化成 IPC 命令发出去。
- **真正的游戏读取/预测/操作全在 `libdemo.so` 里**。它被注入到游戏进程后，直接 hook IL2CPP 方法读写游戏内存。
- 这也是为什么「关键算法在哪个 so」的答案明确落在 `libdemo.so`（详见第五节）。

### 0.3 功能清单（作者自述）

`com.android.support.IntroFeatureCatalog` 是作者写在引导页里的功能介绍，等于一份官方功能表。按原文章节整理如下。

**自动拿牌**

| 功能 | 说明 |
|-|-|
| 一键激活 | 进对局后点一次，自动拿牌、海克斯预测、牌库等全部就绪 |
| 自动拿牌 | 商店刷出目标英雄自动购买，可按 1~5 费勾选 |
| 智能卡牌 | 盯住对手追的三星，自动买同名卡限制其成型，可设触发张数与保留金币 |
| 购买五费天选 | 刷出二星五费天选自动拿下，可指定只拿哪几张五费 |
| 追 3★ | 棋盘上有 2 星英雄时自动拿同名卡，按张数阈值触发 |
| 天选拿取 | 按阈值自动拿天选英雄，可一键全费天选 |
| 海克斯预测 | 提前知道本局三次海克斯的品质（银/金/彩）与具体选项 |
| 自动刷新商店 | 按节奏自动 D 牌，可设保底间隔与保留金币 |
| 一键卖牌 | 一键卖备战席 / 卖场上，快速清仓换经济 |
| 一键换位 | 左右/上下/中心对称镜像换位，也可自定义多对棋子互换 |
| 一键梭哈 | 自动追三星：拿牌、卖多余棋子、刷新一条龙，达成即停 |
| 阵容管理 | 保存/加载/切换多套阵容，A→B 一键换阵 |

**牌库与商店**

| 功能 | 说明 |
|-|-|
| 牌库余量 | 实时显示每张牌在牌库还剩几张 |
| 棋子脚下牌库 | 在每个棋子头顶显示头像、我方张数与牌库余量 |
| 商店剩余显示 | 把牌库余量画进商店金币旁 |
| 自动选中已有英雄 | 牌库自动高亮你已拥有的英雄 |

**指定功能**

| 功能 | 说明 |
|-|-|
| 指定海克斯 | 勾选想要的海克斯（最多 12 个），预测命中时提示对应卡位 |
| 指定重铸 | 指定一件装备，用重铸器锤出它时自动出手并提示 |

**玩家与预警**

| 功能 | 说明 |
|-|-|
| 玩家数据 | 实时列出八家等级、经济、血量与阵容 |
| 对手预测 | 提前显示你下一轮可能遇到的对手，并给出攻击准星标记 |
| 三星预警 | 有对手快三星时弹横幅 + 语音播报，可按费用筛选 |
| 游戏内显示经济 | 把玩家名改成冰块等级 + 琥珀金币，两套颜色区分 |
| 同行识别 | 同一对局双方都开启时，在玩家列表互标★同行 |

**语音播报**：云端模型女声（`CloudTtsClient`）、本地音效（语速/音量/音调滑块）、三星预警语音播报。

**热键与快捷**：模拟器快捷键（F1 显隐悬浮窗、F2 自动拿牌、F3 屏幕牌库，支持 F1~~F12 与 A~~Z 自定义，经无障碍服务绑定）、屏幕常驻快捷按钮。

**单机工具**

| 功能 | 说明 |
|-|-|
| 属性修改 | 单机模式下修改金币 / 血量 / 等级 / 人口上限 |
| 英雄装备生成 | 生成指定星级英雄与成装，数量可选 ×1~×100 |
| 拦截弹窗 | 屏蔽游戏内弹窗 |
| iOS 转区 | 模拟 iOS 区服标识 |
| 退出对局 | 一键退出当前对局 |
| 网页共享 | 生成房间号，电脑与手机浏览器同步查看战况 |
| 防录屏/防截屏 | 开启后截图与录屏里看不到辅助界面 |
| 界面自定义 | 覆盖层透明度、HUD 配色、方框位置大小全部可调 |
| 配置管理 | 保存/加载/导出/导入整套配置 |
| 远程诊断 | 生成识别码给客服，授权后远程定位问题 |

### 0.4 代码模块清单

2280 个自研类，按包分布（前 20）：

| 类数 | 包 | 职责 |
|-|-|-|
| 1429 | `com.android.support`（根） | 主逻辑：悬浮窗、各功能面板、控制绑定器 |
| 122 | `lineup` | 阵容仓库、元数据更新、推荐、修订策略 |
| 99 | `diagnostics` | 诊断协调器、事件存储、上报 |
| 97 | `FloatingWindowService$*` | 悬浮窗服务内部类 |
| 61 | `trust` | 授权信任链（native 桥 + 传输） |
| 17 | `MainActivity$*` | root / 注入流程内部类 |
| 13 | `SharedMemManager$*` | 历史遗留类名：实际已桩化，`readSharedMemoryOnce()` 直接返回 `new byte[0]`，数据全部改由 native 主动推 JSON。详见第二节 |
| 12 | `LocalSocketIPC$*` | LocalSocket IPC |
| 12 | `OpponentPredictionControlBinder$*` | 对手预测 |
| 11 | `CloudTtsClient$*` | 云端语音合成 |
| 10 | `RankWarningControlBinder$*` | 三星预警 |

几个体量突出的文件：`FloatingWindowService.java` 1.52 MB（近乎单文件承载了整个 UI 与业务编排）、`MainActivity.java` 251 KB（root/注入）、`WigVerify.java` 166 KB、`SharedMemManager.java` 143 KB、`NativeTrustBridge.java` 113 KB。

### 0.5 技术栈与混淆情况

- **语言**：Java（AndroidX + 大量 Kotlin stdlib/coroutines 依赖，说明原生工程含 Kotlin 代码，但自研逻辑反编译后呈现为 Java）。
- **网络**：OkHttp3 + Glide（图片）。
- **混淆**：字符串**未加密但大量采用 Unicode 转义**（如 `\u8fdb\u5bf9\u5c40`），JADX 中可直接还原；类名/方法名基本保留语义（`applyRootMountNamespace`、`OwnedHeroTracker` 等），**没有做名称混淆**。这大幅降低了分析难度。
- **native 侧**：静态链接 libc++（`_ZNSt6__ndk1...`），JSON 用 nlohmann/json 3.11.3，注入器基于 KittyMemory（`KittyCmdln` 符号）改写的 ptrace 注入器。
- **加固**：无第三方加固壳痕迹（无 `libjiagu`、`libDexHelper` 等），DEX 未加密；但 native 侧有明显的字符串/日志混淆（大量随机字节字符串）。

---

## 一、Root 提权与 So 注入链路

---

### 1.0 端到端链路总览

入口是 `MainActivity.startInjection()`（`MainActivity.java:1249`），它起一个名为 `Jcc-Injection` 的线程执行 `runInjectionScript(attempt, lease)`（`MainActivity.java:2505`），流程为：

1. `checkRootPermission()` → `su -c id` 里含 `uid=0`（`MainActivity.java:3141`）。
2. 写系统属性 `persist.inject.java_pid` / `persist.inject.mount_dir`，真机路径下顺带 `setenforce 0`（`MainActivity.java:2690`）。
3. `getGameStatus()` 拿游戏 pid / `libil2cpp.so` 是否加载 / 是否已注入（`MainActivity.java:1839`）；已注入则走 `handleReconnect`。
4. `launchGame()` + `waitForGameReady(180000, 稳定窗口)` 等游戏就绪。
5. `prepareInjectionFiles(...)`（`MainActivity.java:2454`）→ `resolveGameDataDir(pid)`（`MainActivity.java:2365`）探到游戏 data dir，做 mount namespace 处理，再把 `libdemo.so` / `libinject.so` 拷进游戏 data dir 并套 SELinux context。
6. `performRootInject(pid, dataDir, libdemoPath)`（`MainActivity.java:1999`）→ 用 `su` 前缀 + `libinject.so` 对目标 pid 做 ptrace 注入。
7. 注入是否成功最终以 **IPC v2 是否 READY**（`SharedMemManager.isCppConnected()`）为准，而不是只看注入器退出码（`MainActivity.java:2188-2230`）。

所有 shell 命令统一走 `execCommand(str)` → `execCommandDetailed(str, timeout)` → `execCommandWithPrefix(getSuPrefix(), str, timeout)`（`MainActivity.java:3224-3291`）。默认超时 35s（`MainActivity.java:3259`），注入那一调用是 120s（`MainActivity.java:2077`）。

---

### 1.1 找 su：路径候选与 `adoptSuPrefix` 逻辑

**候选路径**由 `SuBinaryPathPolicy`（`SuBinaryPathPolicy.java`）集中定义：

```java
static final String DEFAULT_BINARY = "su";
private static final List<String> AUTO_VERSION_PROBES =
        Collections.unmodifiableList(Arrays.asList("/system/xbin/su", "/system/bin/su", DEFAULT_BINARY));
\```

- 自动模式（配置为空，`AUTO = ""`）时，`versionProbeCandidates()` 返回上面三个候选，逐个试；用户显式配置时只用该值（`SuBinaryPathPolicy.java:93-95`）。
- 配置项 key 是 `su_binary_path`，存在 `APP_SETTINGS` 命名空间的 SharedPreferences（`SuBinaryPathPolicy.java:13`；读取见 `MainActivity.java:956-957`）。UI 在 `setupSuBinaryPath()`（`MainActivity.java:920`）、落盘在 `applySuBinaryPath()`（`MainActivity.java:965-1023`）。
- 校验规则 `validate()`（`SuBinaryPathPolicy.java:37-61`）：长度 ≤255、不含 `..`、不能以 `/` 结尾、绝对路径必须匹配 `^(/[A-Za-z0-9._][A-Za-z0-9._+-]*)+$`，否则必须是匹配 `^[A-Za-z0-9._][A-Za-z0-9._+-]{0,63}$` 的裸名字（如 `su`）。不合法则 `sanitize()` 返回空串 → 退回自动模式。

**探测与提权**分三步：

- `checkRoot()`（`MainActivity.java:1349`）：对每个候选执行 `<su> -v`，`exitValue() == 0` 即认为 root 可用。
- `requestRoot()`（`MainActivity.java:1380`）：用 `SuBinaryPathPolicy.pipeCommand()`（即 `new String[]{"su"}`）启动 su，从 stdin 写入 `id\n` + `exit\n`，读回输出，含 `uid=0` 才算成功。走的是"管道模式"。
- `checkRootPermission()`（`MainActivity.java:3141`）：真正注入前再执行一次 `id`，含 `uid=0` 才继续。

**su 前缀（命令拼装方式）**`getSuPrefix()`（`MainActivity.java:3156-3181`）：按顺序试三组 mount-master 前缀，再试普通前缀，都不行则返回 `null`（管道模式）：

```java
static List<String[]> mountMasterPrefixes(String str) {
    String binary = binary(str);
    ArrayList arrayList = new ArrayList(3);
    arrayList.add(new String[]{binary, "-mm", "-c"});
    arrayList.add(new String[]{binary, "-M", "-c"});
    arrayList.add(new String[]{binary, "--mount-master", "-c"});
    return arrayList;
}

static String[] plainPrefix(String str) { return new String[]{binary(str), "-c"}; }
\```

判定方式是 `suPrefixWorks()`（`MainActivity.java:3184-3214`）：把前缀拼上 `echo ok` 执行，5 秒内读回 `ok` 就算通。

`adoptSuPrefix(String[])`（`MainActivity.java:3216-3222`）从两处被调用，作用是**把探测成功的那组前缀固化**：

- `probeGameDataLocationWithMountMaster()`（`MainActivity.java:2407-2426`）：当默认前缀看不到游戏 data dir（`namespace_isolated` 或 `dir_not_found`）时，遍历另外几组 mount-master 前缀重试探测；某组成功就 `adoptSuPrefix(strArr)` 并记一条 `runtimeRecord("INJECT", "SU_PREFIX", "OK", ...)`。
- `getSuPrefix()` 自身探测成功时也会写 `cachedSuPrefix`。

`FloatingWindowService.onCreate()`（`FloatingWindowService.java:1637`）会把同一份配置同步给 `ShellExec`：

```java
ShellExec.setSuBinary(SuBinaryPathPolicy.binary(SuBinaryPathPolicy.sanitize(
        getSharedPreferences(ConfigPreferenceNamespaces.APP_SETTINGS.preferencesName, 0)
                .getString("su_binary_path", ""))));
\```

---

### 1.2 SELinux 处理

代码里有三层，只有第二层是"硬要求"：

**第一层：全局关 SELinux（尽力而为）。** 真机注入命令里前后各夹一次 `setenforce 0`，模拟器分支不做（`MainActivity.java:2077`）：

```java
"cd '" + str + "' && setenforce 0 2>/dev/null; " + str8 + " & INJ_PID=$!; ..."
...
"  else echo '__TARGET_IDENTITY_MISMATCH__:'$CUR_START; fi; setenforce 0 2>/dev/null || true; echo '__INJECT_RC__:'$INJ_RC; exit $INJ_RC"
\```

`runInjectionScript` 的环境准备 lambda 里，非模拟器还会把 `setenforce 0` 和 `setprop` 串在一起执行（`MainActivity.java:2688-2694`）。注意全部带 `2>/dev/null` / `|| true`，**失败不阻断**——很多设备上 `setenforce` 已被 SELinux 策略或 Magisk 拦住。

**第二层：把 so 的 SELinux context 改成目标目录的 context（真正依赖的机制）。** `applyTargetDataContext(dataDir, libdemoPath, libinjectPath)`（`MainActivity.java:2482-2492`）生成一段 shell：

```python
set -eu; context=$(ls -Zd <dataDir> | awk '{print $1}');
case "$context" in u:object_r:*) ;; *) echo __TARGET_BAD_CONTEXT__:$context; exit 1;; esac;
chcon "$context" <so1>; targetContext=$(ls -Zd <so1> | awk '{print $1}'); [ "$targetContext" = "$context" ];
chcon "$context" <so2>; ... ; echo __TARGET_CONTEXT_READY__
\```

要求 context 形如 `u:object_r:...`，逐个 `chcon` 后**回读校验**，不一致就整体失败。`prepareInjectionFiles` 靠这个返回值决定是否 `showErrorAndExit`（`MainActivity.java:2474-2477`）。

**第三层：IPC 引导文件也走同一套。** `stageInjectionBootstrap()`（`MainActivity.java:2333-2337`）：

```java
"set -eu; owner=$(stat -c '%u:%g' " + shellQuote(str) + "); context=$(ls -Zd " + shellQuote(str) + " | awk '{print $1}'); case \"$context\" in u:object_r:*) ;; *) echo __IPC_BOOTSTRAP_BAD_CONTEXT__:$context; exit 1;; esac; rm -f " + shellQuote(str3) + "; cp -f " + shellQuote(file.getAbsolutePath()) + " " + shellQuote(str3) + "; chown \"$owner\" " + shellQuote(str3) + "; chmod 600 " + shellQuote(str3) + "; chcon \"$context\" " + shellQuote(str3) + "; mv -f " + shellQuote(str3) + " " + shellQuote(str2) + "; [ \"$(stat -c '%a' ...)\" = \"600\" ]; [ \"$(stat -c '%u:%g' ...)\" = \"$owner\" ]; ..."
\```

即 `cp` 到 `.tmp.<mypid>` → `chown` 成目标目录 owner → `chmod 600` → `chcon` → 原子 `mv`，最后校验权限/属主/context 全部一致，输出 `__IPC_BOOTSTRAP_READY__`。

---

### 1.3 Mount namespace：`GameDataLocation$Decision`、`applyRootMountNamespace`

**问题背景**：Magisk/KernelSU 的 `su` 默认在自己的 mount namespace 里，root shell `ls /data/data/com.脱敏.jkchess` 会看不到（namespace 隔离）。代码用「探测 + 逃逸」两步解决。

**探测**：`GameDataLocation.buildProbeCommand(pid, pkg, selfDataDir, nativeLibDir)`（`GameDataLocation.java:77-85`）拼出一条很长的 shell，逻辑是：

1. 用 `stat -c %u /proc/PID`（失败退到 `/proc/PID/status` 的 `Uid:` 字段）拿游戏 uid，`GUSER = uid / 100000` 得到 Android userId。
2. 候选目录：`/data/user/$GUSER/$PKG`、`/data/user_de/$GUSER/$PKG`，`GUSER==0` 时追加 `/data/data/$PKG`；另外还会 glob `/mnt/expand/*/user/$GUSER/$PKG`（对应 `EXPANDED_DIR_PATTERN`，`GameDataLocation.java:28`）。
3. 对 **三个视图** 各扫一遍：

| view | BASE（根） | NSF（namespace 文件） |
|-|-|-|
| `direct` | 空（当前进程视角） | 空 |
| `init` | `/proc/1/root` | `/proc/1/ns/mnt` |
| `target` | `/proc/PID/root` | `/proc/PID/ns/mnt` |
4. 每个视图输出 `dir=`（命中的候选目录）、`self=`（能否看到本应用 dataDir）、`lib=`（能否看到本应用 nativeLibraryDir）、`hop=`（用 `nsenter --mount=$NSF -- sh -c 'echo hopok'` 实测能否进入该 namespace，输出 `ok`/`fail`/`na`）。

**决策**：`GameDataLocation.decide(result, pkg)`（`GameDataLocation.java:312-333`）优先级为

1. `direct` 视图 `found()` → `Escape.NONE`，code = `ok_direct`；
2. 否则 `init` 视图必须同时满足 `stageable()`（`found && selfVisible && libraryVisible`）**且** `hoppable()`（`hop == "ok"`）→ `Escape.INIT_NAMESPACE`（`mountNamespaceFile = "/proc/1/ns/mnt"`），code = `ok_init_ns`；
3. 两者都不成立时，如果 init 或 target 视图"找到了目录但不可用"→ `namespace_isolated`；否则 `dir_not_found`。

`validated()`（`GameDataLocation.java:335-343`）会额外把不属于本包候选目录的 `dir` 清成 null，防止跨包误判。

**应用**：`applyRootMountNamespace(decision)`（`MainActivity.java:2428-2444`）：

```java
String mountNamespaceFile = decision.escape().mountNamespaceFile();
if (mountNamespaceFile == null) { this.rootMountNamespaceFile = null; return true; }
this.rootMountNamespaceFile = mountNamespaceFile;
CommandResult execCommandDetailed = execCommandDetailed("[ -d " + shellQuote(decision.dataDir()) + " ] && echo __GAME_DATA_DIR_EXISTS__", 5000L);
if (... 不通过 ...) { this.rootMountNamespaceFile = null; return false; }
\```

也就是：只有 `Escape.INIT_NAMESPACE` 才设 `rootMountNamespaceFile`，并**再验证一次**套用后确实能看到 dataDir，看不到就回退。回退时 `resolveGameDataDir` 会把 decision 换成 `GameDataLocation.escapeRejected(...)`（`MainActivity.java:2377-2379`），code = `escape_rejected`，给用户的文案是：

>
> 已拿到高级权限，但权限会话看不到游戏数据目录（挂载空间被隔离）。请在 Magisk/KernelSU/APatch 里给记牌器开启"全局挂载命名空间(Mount Master)"，或把 su 改回默认路径后重试。
>
>
>

**落地到每条命令**：`wrapWithRootMountNamespace(str)`（`MainActivity.java:3266-3269`）：

```java
String str2 = this.rootMountNamespaceFile;
return str2 == null ? str : "nsenter --mount=" + shellQuote(str2) + " -- sh -c " + shellQuote(str);
\```

`execCommandWithPrefix()` 在拼命令前先调它（`MainActivity.java:3300`），所以一旦逃逸成功，后续**所有** su 命令都自动套上 `nsenter --mount=/proc/1/ns/mnt`。

**为什么要这么做**：注入需要把 `libdemo.so` / `libinject.so` 写进游戏 data dir（私有目录，只有 root 能写），而能不能看到这个目录直接取决于 root shell 所在的 mount namespace。`/data/user/0/...` 与 `/data/data/...` 是同一个 inode 的不同挂载视图，namespace 错了就"看得见路径、看不见内容"或干脆不存在——这正是 `self`/`lib`/`hop` 三个布尔要区分的东西。

---

### 1.4 注入：文件落位、命令行、目标定位、成功判定

#### 常量与源文件

```java
private static final String INJECT_NAME = "libinject.so";
private static final String INJECT_NAME_X86_64 = "libinject_x86_64.so";
private static final String LIB_NAME = "libdemo.so";
private static final String LIB_NAME_COMPAT = "libdemo_compat.so";
\```

（`MainActivity.java:91-94`）运行时库由 `NativeLibrarySelector` 选择：主 ABI 含 `x86` 或用户勾了兼容模式 → `libdemo_compat.so`，否则 `libdemo.so`（`NativeLibrarySelector.java:13-30`）。注入器同理：模拟器用 `libinject_x86_64.so`（`MainActivity.java:2584`）。

#### 拷到哪里（`prepareInjectionFiles`，`MainActivity.java:2454-2480`）

```java
String resolveGameDataDir = resolveGameDataDir(i);      // 例如 /data/user/0/com.脱敏.jkchess
...
String str5 = resolveGameDataDir + "/libdemo.so";        // payload 落点
String str6 = resolveGameDataDir + "/libinject.so";      // 注入器落点
execCommand("rm -f " + shellQuote(str5) + " " + shellQuote(resolveGameDataDir + "/libdemo_compat.so") + " " + shellQuote(str6) + " 2>/dev/null");
// cp 自身 nativeLibraryDir 下的 libdemo*.so  -> 游戏 data dir/libdemo.so，chmod 555
// cp 自身 nativeLibraryDir 下的 libinject*.so -> 游戏 data dir/libinject.so，chmod 555
// 然后 applyTargetDataContext(resolveGameDataDir, str5, str6)
\```

要点：

- **两个 so 都落到游戏的 `dataDir` 根下**，而不是自己的目录、也不是 `/data/local/tmp`。权限位固定 `555`（`Android17CompatibilityPolicy.stagedNativeArtifactMode()` 返回字符串 `"555"`，`Android17CompatibilityPolicy.java:6,21-23`），灌入前还会 `stat -c '%a'` 校验必须是 `555`，否则也算失败（`MainActivity.java:2033-2039`）。
- 落点选游戏 data dir 的原因从代码可推断：`applyTargetDataContext` 把两个文件 `chcon` 成**游戏 data dir 的 SELinux context**，且注入器以 `cd '<dataDir>'` 为工作目录启动。这样注入器进程的 domain/context 与被注入的游戏进程同源，ptrace 与 `dlopen` 路径可见性都更容易过。
- 三个 so 文件名都会先 `rm -f` 清掉，避免残留旧版本。

#### 用什么命令行执行（`performRootInject`，`MainActivity.java:2072-2077`）

```java
String str8 = "'" + str6 + "' -pkg com.脱敏.jkchess -lib '" + str2 + "' -pid " + i + " -dl_memfd";
if (isEmulator) { str8 = str8 + " -delay 3000000"; }
\```

即最终形态为：

```python
cd '<游戏dataDir>' && setenforce 0 2>/dev/null; \
'<游戏dataDir>/libinject.so' -pkg com.脱敏.jkchess -lib '<游戏dataDir>/libdemo.so' -pid <PID> -dl_memfd & \
INJ_PID=$!; ... wait $INJ_PID ...
\```

模拟器分支则是 `-delay 3000000`（微秒 = 3 秒，对应常量 `EMULATOR_NATIVE_BRIDGE_DELAY_MICROS = 3000000`，`MainActivity.java:80`），并且不 `setenforce`，改用 30 秒 `kill -0` 轮询 + 超时 `kill -9`。

真机分支在 `wait` 之后还会做目标身份校验并恢复目标进程：

```java
CUR_START=$(awk '{print $22}' /proc/<PID>/stat 2>/dev/null);
if [ "<j>" -le 0 ] || [ "$CUR_START" = "<j>" ]; then
  echo '__TARGET_IDENTITY_OK__:'$CUR_START; kill -CONT <PID> 2>/dev/null || true; echo '__TARGET_RESUME__:'<PID>;
else echo '__TARGET_IDENTITY_MISMATCH__:'$CUR_START; fi
\```

`libinject.so` 的身份，从 strings 可以确认是 **AndKittyInjector**：

```python
Usage: ./path/to/AndKittyInjector [-h] [-pkg] [-pid] [-lib] [ options ]
-hide_maps      Try to hide lib segments from /proc/[pid]/maps.
-hide_solist
-watch          Monitor process launch then inject, ...
-dl_memfd       Use memfd_create & dlopen_ext to inject library, useful to bypass path restrictions.
-delay          Set a delay in microseconds before injecting.
E: PTRACE_ATTACH failed for pid %d. error="%s".
I: nativeInject: memfd_rand(%d) = %s.
I: Injection succeeded. / E: Injection failed.
\```

即实现是：`PTRACE_ATTACH` → 远程 `memfd_create` + `dlopen_ext` 载入 payload → 调 `JNI_OnLoad` → 验证 `TracerPid` 归零后 `PTRACE_DETACH`（`inject_lib: Detach verified (TracerPid stable at zero).`）。`libinject_x86_64.so` 多了一条 NativeBridge 路径（`emuInject: Using NativeBridge namespace`、`NativeBridgeGetTrampoline`、`libnativebridge.so`），用于 x86 模拟器上把 arm64 payload 通过 NativeBridge 塞进去。**注意**：Java 侧只传 `-pkg/-lib/-pid/-dl_memfd/-delay`，`-hide_maps` / `-hide_solist` **没有被使用**（`MainActivity.java` 全文无匹配）。

#### 目标进程怎么定位

- `getGamePid()`（`MainActivity.java:1481-1502`）：`pidof com.脱敏.jkchess` 逐行取，并用 `cat /proc/$p/cmdline` 过滤掉含 `:` 的子进程（`:xg` 之类），取第一个。
- `getGameStatus()`（`MainActivity.java:1839-1854`）：一条 shell 同时做三件事——用 `/proc/$p/cmdline` 第一段严格等于 `com.脱敏.jkchess` 选出主进程；`grep -q 'libil2cpp\.so' /proc/$PID/maps` 判断核心库是否加载；`grep -q 'libdemo\.so' ... || grep -qx 'IPC-V2-Recv' /proc/$PID/task/*/comm` 判断是否已注入。返回 `[pid, libsLoaded, injected]`。
- **进程身份指纹**：`readGameProcessIdentity(pid)`（`MainActivity.java:1706-1715`）取 `/proc/PID/stat` 第 22 个字段（starttime），拼成 `"<pid>:<starttime>"` 存进 `injection_runtime_state` / `target_process_identity`（`MainActivity.java:1698-1704`）。注入前后都用它比对，防 PID 复用。`hasExistingRuntimeReconnectHint()`（`MainActivity.java:1589`）就是读回这个值比对。
- **注入前等待**：`waitForGameReady(180000, 3000|6000)`；以及 `waitForInteractiveInjectionTarget(pid, 12000)`（`MainActivity.java:1769`）——先 `launchGame()` 把游戏切回前台、`am unfreeze com.脱敏.jkchess`，然后以 100ms 间隔读 `readInjectionTargetSnapshot()`（`MainActivity.java:1756`，读 `/proc/PID/status` 的 `State/TracerPid/SigPnd/ShdPnd`、`/proc/PID/stat` 的 starttime、cgroup `cgroup.freeze`、`/proc/PID/wchan`），交给 `InjectionTargetReadiness.rejectionReason()`（`InjectionTargetReadiness.java`）判断是否处于冻结/被 trace/不可用状态；被系统冻结或被别的工具占用就安全取消并提示「关闭其他辅助/加速工具」。
- 另外还有 `isGameInputReady()`（`MainActivity.java:1741`）看 `wchan` 是否落在 `hrtimer_nanosleep|nanosleep|do_nanosleep`（游戏主线程还在启动休眠 → 延后注入）。

#### 怎么判断注入成功

多层交叉验证，任一环节失败都会 `failInject(消息)`（`MainActivity.java:2307-2310`）并写 `runtimeRecord`：

1. **注入器文本**：输出含 `Injection succeeded` / `Injection failed`（`MainActivity.java:2101-2102`）。
2. **退出码**：从输出里解析 `__INJECT_RC__:<rc>`（`MainActivity.java:2083-2100`）。模拟器分支额外要求 `__TARGET_IDENTITY_OK__` 且 `__TARGET_RESUME__:<pid>`。
3. **memfd 精确匹配**：`extractInjectedMemfdName()`（`MainActivity.java:2312-2321`）用正则 `memfd_rand\(\d+\)\s*=\s*([A-Za-z0-9._-]{5,64})\.` 从注入器日志抓 memfd 名字（"I: nativeInject: memfd_rand(N) = NAME."），再 `hasExactInjectedMemfdMapping(pid, name)`（`MainActivity.java:2323-2331`）执行 `grep -F "/memfd:NAME" /proc/PID/maps`。
4. **真机目标恢复**：注入后重新读一次 target snapshot，要求 pid / startTicks 与注入前一致、`TracerPid <= 0`、`State != 'T'`（`MainActivity.java:2113-2168`）。
5. **最终判定 = IPC v2 握手**（`MainActivity.java:2188-2230`）：注入器报告成功后，`initSharedMemory()` 并轮询 `shmManager.isCppConnected()`，每 250ms 一次、最多 30s；成功即 `rememberInjectedRuntime(pid)` + `return true`；超时则 `failInject("已注入游戏但握手未完成…")`。**这正是"注入成功但辅助没生效"这一类问题的判据。**

与此对应的"已注入"快速通道是 `isAlreadyInjected(pid)`（`MainActivity.java:1504-1530`）：`grep -qE 'libdemo\.so' /proc/PID/maps` + `libil2cpp.so` 已加载 + `SharedMemManager.isCppConnected()` + 重连提示，由 `InjectionReconnectPolicy` 的四个布尔策略函数决定是复用/等待认证/阻断重复注入（`InjectionReconnectPolicy.java:5-32`）。判定"payload 线程活着"用的是 `hasLiveIpcPayloadThreads()`（`MainActivity.java:1581-1587`）：`grep -qx 'IPC-V2-Recv' /proc/PID/task/*/comm`。

**失败诊断**`logInjectFailureDiagnostics()`（`MainActivity.java:3499` 起）会在注入失败时收集：`id; getenforce; /proc/sys/kernel/yama/ptrace_scope`、`/proc/PID/status`（含 `Seccomp`/`NoNewPrivs`/`TracerPid`）、`/proc/PID/attr/current`、`getprop`（`ro.product.cpu.abi`/`abilist`、`ro.dalvik.vm.native.bridge`、`ro.kernel.qemu`）、`/proc/PID/cmdline`+`readlink exe`、maps 里 `libhoudini|libndk_translation|libnativebridge|libil2cpp|libunity|libdemo|libinject|/memfd:`、同包所有 pid 的 State/TracerPid、`ls -lZ` 两个 so 的 SELinux label、以及 `dmesg | grep -i -E 'avc:|denied|ptrace|xptrace' | tail -n 20`。

---

### 1.5 守护与保活

#### 唯一的 BroadcastReceiver：`FloatingWindowWatchdog`

`FloatingWindowWatchdog.java` 全文就是一个 AlarmManager 自唤醒看门狗：

- 常量：`ACTION_TICK = "com.android.support.WATCHDOG_TICK"`、`INTERVAL_MS = 45000`、`FAST_INTERVAL_MS = 2500`、`PI_REQUEST_CODE = 987297`（第 13-16 行）。
- `scheduleAt()` 用 `alarmManager.setAndAllowWhileIdle(0, now + delay, pendingIntent)`（第 70 行），PendingIntent 是发给自己的 broadcast（`buildPendingIntent`，第 100-105 行，`FLAG_IMMUTABLE`）。
- `onReceive()`（第 19-45 行）的 tick 逻辑三步：

```java
scheduleNext(context);                                        // 先续期，保证链不断
boolean wasRunning = FloatingServiceState.wasRunning(context);
boolean isServiceReady = FloatingWindowService.isServiceReady();
if (!wasRunning) { return; }                                  // 用户主动退出过 → 不拉起
if (isServiceReady) { return; }                               // 服务还在 → 不拉起
FloatingWindowService.sIntentionalStart = true;
FloatingWindowService.sReconnectMode = true;
context.startForegroundService(new Intent(context, FloatingWindowService.class));
\```

关键点是它**不会盲目复活**：只有 `FloatingServiceState.wasRunning == true`（SharedPreferences `FloatingWindowConfig/service_was_running`，`FloatingServiceState.java`）时才拉起。用户主动退出时会 `clearServiceWasRunning()` + `FloatingWindowWatchdog.cancel()`（`FloatingWindowService.java:4546-4551`，强制更新退出路径）。

#### 加速复活的三个触发点

- `FloatingWindowService.onDestroy()`（`FloatingWindowService.java:22649`，判定在 `22782`）：

```java
if (ServiceDestroyWatchdogPolicy.shouldAccelerateResurrect(FloatingServiceState.wasRunning(this))) {
    Log.w(TAG, "★ onDestroy 但 service_was_running=true，触发看门狗加速复活");
    FloatingWindowWatchdog.scheduleFast(getApplicationContext());
}
\```

`ServiceDestroyWatchdogPolicy.shouldAccelerateResurrect(boolean)` 就是 `return z;`（`ServiceDestroyWatchdogPolicy.java:5-7`），即等价于"服务本该在跑"。

- `onTrimMemory(i)`，`i >= 80` 时 `scheduleFast`（`FloatingWindowService.java:22503-22515`）。
- `onLowMemory()` 无条件 `scheduleFast`（`FloatingWindowService.java:22518-22528`）。

#### 服务自身的"半死"防护

`FloatingWindowService.onCreate()`（`FloatingWindowService.java:1621`）开头：

```java
if (FloatingServiceState.wasRunning(this) && !sIntentionalStart) { sReconnectMode = true; ... }
if (!sIntentionalStart && !sReconnectMode) {
    Dbg.m70d(TAG, "onCreate: sIntentionalStart=false, sReconnectMode=false (Android auto-restart), stopping immediately");
    startForegroundNotification(); stopSelf(); return;
}
\```

即：系统自动重建（既非主动启动、也没有"上次在跑"的记录）时立刻自杀，避免出现无 IPC 连接的空壳服务。`onCreate` 成功后才 `markServiceWasRunning(this)`（`FloatingWindowService.java:1660`、`1881`、`1994`、`2209` 四处）并启动看门狗 `FloatingWindowWatchdog.scheduleNext(this)`（`FloatingWindowService.java:1891`、`2004`、`2220`）；`onCreate` 异常则 `clearServiceWasRunning` + `Watchdog.cancel` + `stopSelf`（`FloatingWindowService.java:2227-2236`）。

#### Root 侧独立探针进程 `RootHelperManager`

`RootHelperManager`（`RootHelperManager.java`）在服务 `onCreate` 成功后被启动（`FloatingWindowService.java:1884-1893`）。`startInternal()` 做四件事：

```java
new ProcessBuilder("su", "-c", "pkill -f jcc_helper").redirectErrorStream(true).start();   // 清旧的
File extractHelper = extractHelper();                                                       // 从 assets 解出
this.bridge = new RootHelperBridge(socketNameFor, listener); this.bridge.start();           // LocalServerSocket
String str = extractHelper.getAbsolutePath() + " --sock " + socketNameFor;                  // [--cso <hex>]
this.helperProcess = new ProcessBuilder("su", "-c", str).redirectErrorStream(true).start();
\```

- `extractHelper()`（第 143-180 行）按 `Build.SUPPORTED_ABIS[0]` 选 `arm64` 或 `x86_64`，把 `assets/helper/<abi>/jcc_helper` 解到 `files/helper/<abi>/jcc_helper` 并 `setExecutable(true, true)`。
- socket 名 `RootHelperProtocol.socketNameFor(pkg)` = `"jcc_helper_" + 包名`（`RootHelperProtocol.java:7,14-16`）。
- 通信是**行分隔 JSON**：helper 往 socket 写，`RootHelperBridge.dispatch()`（`RootHelperBridge.java:94-106`）识别 `helper_ready` 或 `game_probe`；`parseGameProbe()`（`RootHelperProtocol.java:18-27`）解析 `pid` / `cpu_ticks` / `rss_kb` / `libil2cpp` / `libdemo_injected` → `RootHelperGameState`。`FloatingWindowService` 侧只做日志与去重（`FloatingWindowService.java:2431-2436`）。
- `restartWithCso(long)`（第 46-52 行）会 stop 再 `startInternal(listener, cso)`，把 `--cso <Long.toHexString(j)>` 追加到 helper 命令行。**`--cso` 的具体语义在 Java 侧读不出来**（只有 `cso()` getter 和 `restartWithCso`），需要看 `jcc_helper` 二进制。

#### 被杀后的恢复：`attemptAutomaticRuntimeRecovery` / `abandonAutomaticRuntimeRecovery`

调用点在 `updateRootStatus(true)` 里（`MainActivity.java:1436`），即每次确认 root 授权后触发一次；`AtomicBoolean automaticRecoveryStarted` 保证只跑一次（`MainActivity.java:1601-1612`）。

`attemptAutomaticRuntimeRecovery` 线程体（`MainActivity.java:1614-1643`）：

```java
int gamePid = getGamePid();
if (!InjectionReconnectPolicy.shouldAutoRecoverRuntime(gamePid, isGameLibsLoaded(gamePid), hasExistingRuntimeReconnectHint(gamePid))) {
    log("启动恢复：没有可复用的同进程运行时"); return;
}
if (this.isInjecting) { log("启动恢复：已有注入/恢复流程进行中"); return; }
this.isInjecting = true;
// ... UI 切 CONNECTING ...
if (!isCurrentInjection(j) || !stageExistingRuntimeReconnectBootstrap(gamePid)) {
    abandonAutomaticRuntimeRecovery("启动恢复：无法安全重放当前 IPC 认证材料，静默放弃");
} else if (isAlreadyInjected(gamePid)) {
    handleReconnect(gamePid, j);
} else {
    abandonAutomaticRuntimeRecovery("启动恢复：旧运行时未在安全窗口内完成认证，禁止自动二次注入，静默放弃");
}
\```

`shouldAutoRecoverRuntime(pid, libsLoaded, reconnectHint)` = `pid > 0 && libsLoaded && reconnectHint`（`InjectionReconnectPolicy.java:5-7`）——必须"同一个进程（starttime 指纹一致）+ 核心库已加载 + 之前注入过"三条同时成立。

`abandonAutomaticRuntimeRecovery`（`MainActivity.java:1657-1675`）只是 `isInjecting = false` + 把 UI 阶段退回 `READY`，**不报错、不弹窗**，这是刻意的静默降级。

与之配套的"禁止二次注入"闸门在 `runInjectionScript` 里（`MainActivity.java:2566-2577`）：`shouldBlockDuplicateInjection(pid, coreLoaded, cppConnected, reconnectHint)` 为真时提示用户完全关闭并重启《金铲铲之战》，理由是「同一局内重复注入无法重挂 hook」。

`handleReconnect(pid, attempt)`（`MainActivity.java:2819`）走的是纯 IPC 重连路径（`initSharedMemory` + 起悬浮窗 + 验证），不再调注入器。

---

### 1.6 环境检测（模拟器）

唯一实现是 `MainActivity.isEmulator()`（`MainActivity.java:1444-1479`），结果缓存在 `cachedIsEmulator`，四重判据依次短路：

1. **ABI**：`Build.SUPPORTED_ABIS[0]` 含 `"x86"` → 模拟器。
2. **`Build.HARDWARE`** 含 `ranchu` / `goldfish` / `vbox` / `nox` / `nemu` / `mumu` / `android_x86`。
3. **11 个特征文件**逐个 `File.exists()`：

```java
String[] strArr = {"/dev/qemu_pipe", "/dev/goldfish_pipe", "/dev/vboxguest",
    "/system/lib/libmumuvm.so", "/system/lib64/libmumuvm.so",
    "/system/lib/libnemu.so", "/system/lib64/libnemu.so",
    "/system/lib/libldinput.so", "/system/lib64/libldinput.so",
    "/system/bin/nox", "/system/bin/microvirt"};
\```

4. **`Build.MANUFACTURER`** 小写含 `genymotion` / `netease` / `nemu` / `mumu`。

**检测到之后做什么**（都是"走另一条更保守的分支"，不是拒绝运行）：

| 处 | 行为 | 位置 |
|-|-|-|
| 运行时库 | `NativeLibrarySelector.shouldUseCompat()` → 用 `libdemo_compat.so` | `NativeLibrarySelector.java:13-26` |
| 注入器 | `INJECT_NAME_X86_64 = libinject_x86_64.so` | `MainActivity.java:2584` |
| 注入命令 | 追加 `-delay 3000000`（3s，等 NativeBridge 起来） | `MainActivity.java:2074-2076` |
| 注入 shell | 不走 `setenforce`，改用 30s 轮询 + 超时 `kill -9` | `MainActivity.java:2077` |
| 目标就绪判定 | 跳过 `readInjectionTargetSnapshot` 那一套（`if (!isEmulator)` 才做） | `MainActivity.java:2113-2114` |
| 稳定窗口 | `GAME_STABLE_WINDOW_MS_EMULATOR = 6000`（真机 3000） | `MainActivity.java:87-88` |
| 系统属性 | 模拟器分支不执行 `setenforce 0` | `MainActivity.java:2688-2693` |
| 快捷键 | 额外提供 `EmulatorShortcutService`（无障碍服务，F1-F12 等映射到自动拿牌/牌库/窗口开关），因为模拟器映射不出音量键 | `EmulatorShortcutService.java` |

另外 `libdemo.so` 的 strings 里也出现了 `/dev/socket/qemu`，说明 **native payload 自己也做了一套模拟器判定**（Java 侧只读到了路径字符串，具体分支未反编译）。

---

## 二、Java 与注入 Native 的 IPC 协议

### 2.0 一句话结论

App 与注入 native 之间**只有一条真正承载业务的通道**：一条名为 `xf_game_control_v2` 的 **Linux 抽象命名空间 Unix domain socket**（Android `LocalServerSocket`），协议代号 **IPC v2**，全部消息是 **UTF-8 JSON**，用 **4 字节大端长度前缀**分帧。会话建立时用 HMAC-SHA256 挑战/应答做双向鉴权，Token 通过**文件引导通道**（把 `ipc_v2_bootstrap.json` 写进游戏进程的数据目录）交接。另有一条**独立的诊断共享内存页**（262144 字节），通过 **SCM_RIGHTS fd 传递**挂到游戏进程，是唯一真实的共享内存。旧版 `SharedMemManager` 的共享内存数据面已被**废弃并桩化**（`readSharedMemoryOnce()` 返回 `byte[0]`）。

---

### 2.1 通道总览

| 通道 | 类型 | 方向 | 载体 | 用途 | 代码位置 |
|-|-|-|-|-|-|
| **IPC v2 抽象 socket** | Unix domain socket（abstract namespace） | 双向 | `LocalServerSocket("xf_game_control_v2")` | 全部业务：命令、状态推送、配置同步、心跳、诊断控制 | `LocalSocketIPC.java` |
| **IPC v2 TCP 回退** | TCP `127.0.0.1:39816..39820` | 双向 | `ServerSocket` | 抽象 socket 不可用时的备用传输（同一套协议） | `LocalSocketIPC.startServer()` `LocalSocketIPC.java:428` |
| **诊断共享内存页** | 匿名共享内存 + fd 传递 | native → App（App 侧轮询） | 262144 B page，`ParcelFileDescriptor` | native 侧 trace/事件/健康度/崩溃槽位 | `diagnostics/DiagnosticSharedMemoryBridge.java` |
| **Bootstrap Token 文件** | 文件交换 | App → native（单向投递） | 游戏数据目录下 `.xfjcc_ipc_v2_bootstrap` | 把 IPC v2 首次鉴权用 token 交给注入模块 | `IpcV2TokenStore.java`、`MainActivity.java:2043` |
| 旧共享内存数据面 | —— | —— | 已废弃 | `readSharedMemoryOnce()` 返回 `SENTINEL_DATA`（空数组） | `SharedMemManager.java:51, 1616` |
| PeerSync / 云端 | HTTP 网关（`JccGatewayClient`） | App ↔ 服务器 | —— | 跨设备旁路同步，**不属于**本机 native IPC | `PeerSync.java` |

>
> 命名空间判定依据：`new LocalServerSocket(SOCKET_NAME)`（`LocalSocketIPC.java:417`），`SOCKET_NAME` = `"xf_game_control_v2"`，不以 `/` 开头，因此是抽象命名空间（`\0xf_game_control_v2`）。`LocalSocketIPC.logStatus()` 也把它打印成 `Socket: @xf_game_control_v2`。
>
>
>

**Socket 名与端口按发行版分流**（`JccDistributionProfile.java` + `BuildConfig.java:16-27`）：

| 发行版 | applicationId | socket 名 | TCP 起始端口 | bootstrap 文件名 |
|-|-|-|-|-|
| FORMAL（正式） | `com.android.support` | `xf_game_control_v2` | 39816（~39820） | `.xfjcc_ipc_v2_bootstrap` |
| CANDIDATE | `com.android.support.candidate` | `xf_game_control_v2_candidate` | 39821 | `.xfjcc_ipc_v2_candidate_bootstrap` |
| TEST | `com.android.support.test` | `xf_game_control_v2_test` | 39826 | `.xfjcc_ipc_v2_test_bootstrap` |

App 侧启动的服务端线程名 `IPC-v2-IO` / `IPC-v2-Maintenance`（`LocalSocketIPC.java:288,297`）；游戏进程侧 native 的连接线程命名为 **`IPC-V2-Recv`**，App 正是靠读 `/proc/<pid>/task/*/comm` 里的 `IPC-V2-Recv` 来判断"注入是否存活"（`MainActivity.java:1585`、`MainActivity.java:1842`）。**因此 native 是 client，App 是 server。**

---

### 2.2 分帧与信封格式

#### 2.2.1 分帧（`IpcV2FrameCodec.java`）

\```
+---------------------+---------------------------+
| 4 bytes, big-endian | N bytes                   |
| N = payload length  | UTF-8 JSON text           |
+---------------------+---------------------------+
\```

| 约束 | 值 | 出处 |
|-|-|-|
| 长度前缀 | 4 字节，大端，`(b[0]<<24) | (b[1]<<16) |
| 单帧上限 | `MAX_FRAME_BYTES = 1048576`（1 MiB），超限抛 `FRAME_TOO_LARGE` | `IpcV2Protocol.java:16`、`IpcV2FrameCodec.java:50` |
| 空载荷 | 非法（`INVALID_LENGTH`） | `IpcV2FrameCodec.java:47, 70` |
| 编码 | 严格 UTF-8，非法序列抛 `INVALID_UTF8`（`CodingErrorAction.REPORT`） | `IpcV2FrameCodec.java:56, 67` |
| 无帧内校验和 | 没有任何 checksum / CRC 字段 | 通读 `IpcV2FrameCodec` 全文 |

#### 2.2.2 业务信封（`LocalSocketIPC.validateEnvelope()` `LocalSocketIPC.java:1111-1129`）

发方组包在 `writerLoop()`（`LocalSocketIPC.java:638`）：

```java
new JSONObject().put("v", 2)
               .put("type", take.type)
               .put("sessionId", session.sessionId())
               .put("id", take.id)
               .put("seq", incrementAndGet)
               .put("method", take.method)
               .put(bodyKey, take.body);   // bodyKey ∈ {"params", "result"}
\```

| 字段 | 类型 | 含义 / 校验 |
|-|-|-|
| `v` | int | 协议版本，必须 `== 2`（`IpcV2Protocol.VERSION = 2`），否则 `bad version` |
| `type` | string | 必须是 `state` / `response` / `event` / `ping` / `pong` / `error` 之一 |
| `sessionId` | string(base64url,16B) | 必须与服务端当前 session 完全相等，否则 `session mismatch` |
| `id` | string(base64url,16B) | 请求关联 id；收方用 `decodeBase64Url(id, 16)` 校验长度 |
| `seq` | int64 | **严格递增 1**（`IpcV2Sequence.accept()` `IpcV2Sequence.java:18-25`），违反则 `sequence violation` 断链 |
| `method` | string | 正则 `[A-Za-z0-9_.]+$`，长度 ≤ 96（`validMethod()` `LocalSocketIPC.java:1153`） |
| `params` | object | 入站业务/事件体的键名 |
| `result` | object | 出站响应的键名；`error` 帧用 `error` 键 |

**示例：App → native 的一条动作帧**（`chess.sell`）

```json
{"v":2,"type":"request","sessionId":"<22字符base64url>","id":"<22字符base64url>",
 "seq":17,"method":"chess.sell",
 "params":{"mode":2,"costMask":31,"keepHeroIds":[101,102],"keepCardingTargets":0,
           "matchGeneration":"<22字符>","createdBootMs":812345,"ttlMs":5000}}
\```

**示例：native → App 的响应帧**

```json
{"v":2,"type":"response","sessionId":"...","id":"(回显请求id)","seq":9,
 "method":"chess.sell","result":{"status":"completed"}}
\```

**示例：native → App 的错误帧**

```json
{"v":2,"type":"error","sessionId":"...","id":"...","seq":10,
 "method":"chess.sell","error":{"code":"invalid_request"}}
\```

（`handleInbound()` `LocalSocketIPC.java:706-708`，缺 `code` 时默认 `invalid_request`。）

**示例：native → App 的状态推送帧**

```json
{"v":2,"type":"state","sessionId":"...","id":"...","seq":31,
 "method":"updatePlayers",
 "params":{"dualPlay":false,"turnState":3,
   "players":[{"id":0,"hp":100,"level":7,"gold":42,"rank":1,"isMe":true,
               "name":"我","enemy":3,"avatarId":101,"isBot":false,"botKnown":true}]}}
\```

#### 2.2.3 握手专用信封

握手用同一分帧，但 `seq` 固定 `0`、`type` 固定 `request`/`response`（`writeHandshake()` `LocalSocketIPC.java:1131-1133`）：

**① App(native 视角的 server) → native：`handshake.challenge`**

```json
{"v":2,"type":"request","id":"<challengeId>","seq":0,"method":"handshake.challenge",
 "params":{"challengeId":"<16B base64url>","serverNonce":"<32B base64url>",
           "connectionId":<positive long>,"serverGeneration":<long>,
           "transport":0,"deadlineBootMs":<elapsedRealtime+3000>}}
\```

（`authenticateAndPromote()` `LocalSocketIPC.java:555`；`transport` 0=abstract，1=tcp）

**② native → App：`handshake.challenge` 的 response**

```json
{"v":2,"type":"response","id":"<challengeId>","seq":0,"method":"handshake.challenge",
 "result":{"version":2,"tokenEpoch":<long>,"clientNonce":"<32B base64url>",
           "clientProof":"<32B base64url>"}}
\```

**③ App → native：`handshake.welcome`**

```json
{"v":2,"type":"request","id":"<randomId>","seq":0,"method":"handshake.welcome",
 "params":{"sessionId":"<16B base64url>","serverProof":"<32B base64url>"}}
\```

**④ native → App：`handshake.welcome` 的 response**

```json
{"v":2,"type":"response","id":"<randomId>","seq":0,"method":"handshake.welcome",
 "result":{"ready":true}}
\```

#### 2.2.4 鉴权算法（`IpcV2Protocol.java`）

- `transcript = BE32(2) ‖ u64 serverGeneration ‖ u64 connectionId ‖ u64 tokenEpoch ‖ challengeId(16) ‖ serverNonce(32) ‖ clientNonce(32) ‖ byte transport`（`transcript()` `IpcV2Protocol.java:26-37`）
- `clientProof = HMAC-SHA256(token, "xfjcc-ipc-v2/client\0" ‖ transcript)`（`clientProof()` `IpcV2Protocol.java:39-42`，域分隔符带尾部 `\0`，见 `domain()` `IpcV2Protocol.java:97-102`）
- `serverProof = HMAC-SHA256(token, "xfjcc-ipc-v2/server\0" ‖ transcript ‖ sessionId(16))`（`serverProof()` `IpcV2Protocol.java:44-48`）
- 比较用 `MessageDigest.isEqual` 做常量时间比较（`proofEquals()` `IpcV2Protocol.java:50-52`）
- `token` 是 32 字节随机数，base64url（无填充）编码成 43 字符

#### 2.2.5 Bootstrap Token 文件格式（`IpcV2TokenStore.java`）

严格正则（`IpcV2TokenStore.java:28`）：

\```
\{"v":2,"tokenEpoch":<正整数>,"token":"<43字符base64url>"\}
\```

三份文件（同名目录 `context.getDir("ipc_v2", 0)`，权限 owner-only 0600，原子写入 + `fsync`）：

| 文件名 | 角色 |
|-|-|
| `ipc_v2_pending_token.json` | 本次注入新生成的待用 token |
| `ipc_v2_current_token.json` | 已鉴权通过的当前 token |
| `ipc_v2_bootstrap.json` | 投递给 native 的引导文件 |

注入流程：`beginInjection()` 生成 epoch = max(current, pending)+1 的随机 token 写入 pending → `writeBootstrap()` 写 bootstrap 文件 → `MainActivity.stageInjectionBootstrap(...)` 把它拷到游戏数据目录并命名为 `.xfjcc_ipc_v2_bootstrap`（`MainActivity.java:2043-2046`）→ 注入模块读它完成握手 → 成功后 `promoteAuthenticated(epoch)` 把 pending 提升为 current 并**删除** bootstrap 文件（`IpcV2TokenStore.java:115-129`）；失败则 `abortPending(epoch)` 回滚（`MainActivity.java:2341`）。重连时用 `prepareReconnectBootstrap()` / `writeActiveBootstrap()` 复用已有 token（`MainActivity.java:1684`）。

---

### 2.3 命令清单（App → native）

#### 2.3.1 业务动作 `request` 帧（经 `IpcActionSender`，自动注入 `matchGeneration` / `createdBootMs` / `ttlMs`）

`IpcActionSender.sendWithTerminal()`（`IpcActionSender.java:71-94`）会在每个动作上追加：

| 附加字段 | 值 | 说明 |
|-|-|-|
| `matchGeneration` | 当前对局的 22 字符 generation | 无对局时本地直接拒绝，返回 `no_active_match_generation` |
| `createdBootMs` | `SystemClock.elapsedRealtime()` | 创建时刻 |
| `ttlMs` | `ACTION_TTL_MS = 5000` | native 侧过期丢弃 |
| 请求超时 | `REQUEST_TIMEOUT_MS = 6000` | 客户端侧回调超时 |

完整常量表见 `IpcV2ActionMethods.java:10-31`。

| 方法名 | 语义 | 关键 params 字段 | 代码位置 |
|-|-|-|-|
| `game.modifyGold` | 改金币 | `value`, `targetMask`, `targetSelf` | `SharedMemManager.modifyGold()` `:847` |
| `game.modifyHp` | 改血量 | `value`, `targetMask`, `targetSelf` | `:857` |
| `game.modifyLevel` | 改等级 | `value`, `targetMask`, `targetSelf` | `:867` |
| `game.modifyPopulation` | 改人口 | `delta`, `targetMask`, `targetSelf` | `:1132` |
| `game.exit` | 退出对局 | 无 | `:1141` |
| `drop.generateHeroes` | 凭空生成英雄 | `heroIds[]`, `starLevel`, `targetMask`, `targetSelf` | `:876` |
| `drop.generateEquipment` | 凭空生成装备 | `equipIds[]`, `targetMask`, `targetSelf` | `:889` |
| `chess.sell` | 一键卖英雄 | `mode`(1备战席/2场上/3全部), `costMask`(≤31), `keepHeroIds[]`(≤64), `keepCardingTargets` | `:920-999` |
| `chess.mirror` | 一键镜像换位 | `axis`(0水平/1垂直/2中心对称) | `:1039` |
| `chess.customSwap` | 自定义换位 | `pairs[]`（JSONArray） | `:1054` |
| `chess.allIn.start` | 一键梭哈启动 | `maxTargets`(1-9), `reserveGold`(0-50), `blockedAction`(0/1), `keepLineup`(0/1), `ackTimeoutMs`(2000-6000), `costMask`(8/16/24), `priorityHeroIds[]`(≤64) | `:1072-1100` |
| `chess.allIn.stop` | 一键梭哈停止 | 无 | `:1107` |
| `cancelChessOp` | 取消所有 ChessOp 任务（走 `sendCommand`，**不带** `matchGeneration`） | 无 | `:1111-1113` |
| `lineup.apply` | 把 App 侧阵容反向注入游戏 | `heroes[]`, `title`, …（整个 JSON 由调用方给） | `:1263-1270` |
| `lineup.clear` | 清除 App 注入的阵容 | 无 | `:1325-1331` |
| `lineup.syncToSlot` | 同步阵容到指定槽位 | `title`, `shareCode`, `deckIndex` | `:1339-1346` |
| `hex.query` | 查询海克斯强化等级（广播式，见 2.5） | 无 | `:403`、`HexQueryBroker` |
| `hex.specify` | 指定海克斯 | `targetHexIds[]`(1-12 个), `stage`(1-3), `matchGeneration` | `:1499-1528` |
| `hex.cancel` | 取消指定海克斯 | `matchGeneration` | `:1535-1541` |
| `recast.specify` | 指定重铸目标 | `targetEquipId`(1-1000000), `targetTier`(0-1000), `matchGeneration` | `:1548-1563` |
| `recast.cancel` | 取消重铸指定 | `matchGeneration` | `:1570-1576` |
| `diagnostics.uiApplied` | 诊断 UI 发布回执 | `DiagnosticUiPublication.receipt(status)` | `:2548-2554` |

#### 2.3.2 `state` 帧（App → native，可合并的"最新值语义"）

| 方法名 | 语义 | params | 代码位置 |
|-|-|-|-|
| `config.replace` | **全量配置下发**（核心配置面） | `revision` + 全部配置键，见下表 | `LocalSocketIPC.enqueueLatestConfig()` `:864-910` |
| `hudStyle.replace` | HUD 配色下发 | `revision`, `levelRgb`, `goldRgb`, `shopRgb`, `selfRgb`, `fightRgb` | `:970-1013`、`HudAppearance.toIpcParams()` `HudAppearance.java:126-137` |

`config.replace` 的键（`IpcV2ConfigState.java:13-78`），标量键：

`autoPick`, `autoPlay`, `autoPick5CostChosen`, `autoPickAllChosen`, `autoPickCostMask`, `chase3StarThreshold`, `chase3StarChosenThreshold`, `autoRefreshShop`, `autoRefreshFallbackMs`, `autoRefreshReserveGold`, `auxiliaryMode`, `blockDialogs`, `boardEntityPreview`, `boardHeroHeadOverlay`, `chessOpIntervalFrames`, `iosFake`, `lineupStateKnown`, `nativeAttackIconEnabled`, `nativeAttackIconOffsetX`, `nativeAttackIconOffsetY`, `nativeAttackIconSizePercent`, `nativePlayerEconName`, `opponentBoardPerspective`, `opponentCardingEnabled`, `opponentCardingCostMask`, `opponentCardingMaxOwnedCopies`, `opponentCardingReserveGold`, `opponentCardingStrategy`, `opponentCardingThreshold`, `opponentPredictStyle`, `sessionActive`, `shopNativeLabel`, `showDebugWindow`, `specifiedShop`, `specifiedShopAffordOnly`, `specifiedShopCostMask`, `specifiedShopReserveGold`, `specifiedShopUseLineup`, `uiSurfaceDisableMask`, `uiSurfaceEnableMask`, `uiSurfaceHideMask`, `uiSurfaceShowMask`

集合/数组键（`REQUIRED_COLLECTION_KEYS` `IpcV2ConfigState.java:78`）：

`customAutoPickHeroIds`, `excludedHeroIds`, `lineupAppliedHeroIds`, `lineupAppliedStarTargets`, `auxiliaryAutoPickHeroIds`, `chosen5CostFilterIds`, `chosenAllCostFilterIds`, `starTargets`, `auxiliaryStarTargets`, `battlePanelLineups`

其中 `starTargets` / `auxiliaryStarTargets` / `lineupAppliedStarTargets` 序列化为 `[{"heroId":N,"star":1..4}]`（`IpcConfigSync.isStarTargetKey()` `:121`、`starTargetsToJson()` `:133-144`）。

#### 2.3.3 其余 `request` 帧（走裸 `sendRequest`/`sendCommand`，**不带** `matchGeneration`）

| 方法名 | 语义 | params | 超时 | 代码位置 |
|-|-|-|-|-|
| `diagnostics.trace.attach` | 把诊断共享内存页 fd 挂到游戏进程 | `{generation, mode(2=DEEP, 否则 1), expiresMonoNs, featureMask[]}` **+ 附带 fd** | 5000 ms | `LocalSocketIPC.sendDiagnosticTraceAttach()` `:813-842`；参数见 `DiagnosticSharedMemoryBridge.attachParams()` `:218-232` |
| `diagnostics.trace.disable` | 撤销诊断页挂载 | `{generation}` | 5000 ms | `FloatingWindowService.java:4811-4825`（`DiagnosticCoordinator.IPC_TIMEOUT_MS = 5000`） |
| `debug.pointers` | 取调试指针 | `{}` | 5000 ms | `SharedMemManager.requestDebugPointers()` `:1583-1587` |
| `acceptTrustLease` | 信任租约下发 | `{trust_generation, lease[], device, server_time_offset}` | 3000 ms | `trust/NativeTrustBridge.java:1880, 2193-2205` |
| `activateWigSession` | 激活 WIG 会话 | `{trust_generation, expiry, token, payloadKind, device, binding, server_time_offset}` | 3000 ms | `NativeTrustBridge.java:1928, 2151-2162` |
| `acceptFeatureCatalog` | 下发功能目录 | `{trust_generation, words}` | 3000 ms | `NativeTrustBridge.java:2008, 2108-2114` |
| `clearTrustLease` | 清除信任租约（`sendCommand`） | `{trust_generation}` | 3000 ms | `NativeTrustBridge.java:2217-2218, 2208-2215` |

#### 2.3.4 控制帧

| 类型 / 方法 | 方向 | 说明 | 代码位置 |
|-|-|-|-|
| `type=ping`, `method=heartbeat.ping` | App → native | App 每 5 s 发一次，`params` 为空 | `LocalSocketIPC.maintain()` `:767` |
| `type=pong`, `method=heartbeat.pong` | App → native | 收到 native 的 `ping` 后回敬，`id` 回显 | `handleInbound()` `:711` |
| `type=ping` | native → App | native 也会主动 ping | `:710` |
| `type=pong` | native → App | 收到即刷新 `lastReceivedBootMs`，不做别的事 | `:714-716` |

>
> 注意方向：`ping`/`pong` 双方都会发；`heartbeat.ping`/`heartbeat.pong` 这两个 method 名只出现在 App 出站帧里。
>
>
>

---

### 2.4 推送清单（native → App）

全部走 `type=state` 或 `type=event` 帧（`handleInbound()` `LocalSocketIPC.java:720-722`；`state` 静默、`event` 会自动回一条 `{"status":"completed"}` 的 `response` 帧，见 `:725, 746-748`）。方法名常量集中在 `IpcV2PushMethods.java:10-34`，分发在 `SharedMemManager.createPushDispatcher()` `:1880-2058`，未注册的方法只打一行 `[MSG] 未知方法: X` 日志（`handleCppMessage()` `:1869-1878`）。

| 方法名 | 语义 | 关键字段 | 处理函数 |
|-|-|-|-|
| `match.started` | 对局开始 | `matchGeneration`(**必须 22 字符**), `sessionGeneration`(>0) | `parseStarted()` `IpcMatchLifecycleParser.java:20-30`；`SharedMemManager.handleMatchStarted()` `:2066` |
| `match.ended` | 对局结束 | `matchGeneration` | `parseEnded()` `IpcMatchLifecycleParser.java:32-34`；`:2087` |
| `connected` | native 侧"我连上了/断了" | `value` (bool) | `handleConnected()` `:2097-2103` |
| `updatePlayers` | 8 名玩家状态（英雄、经济、对手） | `players[{id,hp,level,gold,rank,isMe,name,enemy,avatarUrl,avatarId,isBot,botKnown}]`, `dualPlay`, `turnState`, `profileProbe` | `IpcPlayersParser.parse()`；`:2330-2351` |
| `updateHeroPool` | 牌库剩余 | `pool[].heroes[{heroID,cost,currentCount,totalCount}]`, `locked[{heroId,cost,leftCount,totalCount}]` | `IpcHeroPoolParser.parse()`；`:2378` |
| `updateBoardPositions` | 各玩家棋盘/备战席 | `positions[{playerId,isMe,boardMask,benchMask,boardCount,benchCount,boardHeroes[≤28],benchHeroes[≤9]}]` | `IpcBoardPositionsParser.parse()`；`:2394` |
| `updateMyOwnedHeroes` | 自己拥有的英雄与张数 | `heroes[]`, `pieceCount` | `IpcMyOwnedHeroesParser.parse()`；`:2416` |
| `updateOpponentCardingStatus` | 卡对手牌状态 | `state`, `summary`, `targets[{playerId,name,heroId,copies,threshold,purchaseEligible,reason,ownedCopies,maxOwnedCopies,neededCopies}]` | `IpcOpponentCardingParser.parse()`；`:2250` |
| `toast` | native 让 App 弹提示 | `text` | `handleNativeToast()` `:2106-2112` |
| `updateAllInStatus` | 一键梭哈运行状态 | `active`, `reason` | `IpcAllInStatus.parse()`；`:2061-2062` |
| `updateBoardHeroAnchors` | 棋子头顶锚点（屏幕坐标） | `sequence`, `planning`, `anchors[]` | `IpcBoardHeroAnchorsParser.parse()`；`:2432` |
| `updateHexPrediction` | **海克斯等级查询结果**（`hex.query` 的回程） | `matchGeneration`, `available`, `levels[4]`, `livePool[]`, `livePoolWeights[]`, `livePoolTotalWeight`, `drawsPerStage`, `reason` | `IpcHexLevelsParser.parse()`；`parseHexData()` `:2443-2470` |
| `hex.specified.status` | 指定海克斯执行状态 | （见 `parseSpecifiedHexStatus`） | `:2206` |
| `updateMatchup` | 对手预测配对 | `myId`, `opponentId`, `matchId`, `source`, `pairs[{p1,p2,ghost}]` | `IpcMatchupEnvelopeParser`/`IpcMatchupPairsParser`；`:2474-2492` |
| `updateOpponentDiagnostics` | 对手预测诊断 | `{...}` | `parseOpponentDiagnostics()` `:170` |
| `updateShopAutomationDiagnostics` | 商店自动化诊断 | `{...}` | `:174` |
| `updateSpecifiedShopStatus` | 指定商店状态 | `armed, ready, targets, roster, unaffordable, reachable, predictions, refreshed, landed` | `parseSpecifiedShopStatus()` `:2557-2561` |
| `updateGameRecommendUiDiagnostics` | 阵容推荐 UI 诊断 | `{...}` | `:166` |
| `updateGameRecommendHookDiagnostics` | 阵容推荐 hook 诊断 | `{...}` | `:162` |
| `updateRankAnchors` | 排行 HUD 锚点 | `anchors[]` | `IpcRankAnchorsParser.parse()`；`:2652` |
| `updateShopSlots` | **商店 5 个槽位的英雄** | `slots[{index,heroId}]` | `IpcShopSlotsParser.parse()`（含 FNV 指纹 `FINGERPRINT_SEED = -3750763034362895579`）；`:2705` |
| `updateGameRecommendTeam` | 阵容推荐队伍 | `{...}` | `IpcGameRecommendParser`；`:2612` |
| `updateGameRecommendActive` | 阵容推荐激活目标 | `active`, `heroIds[]` | `:2602-2609` |
| `recast.specified.status` | 指定重铸运行状态 | `RecastRunStatus` JSON | `:2143` |
| `recast.pool.catalog` | 重铸候选池目录 | `RecastLivePoolCatalog` JSON | `:2173` |

>
> `trace` 诊断发布附加字段：部分推送（`updateMatchup`、`updateBoardPositions`、`updateRankAnchors`、`updateGameRecommend*`）可携带 `DiagnosticUiPublication.METADATA_KEY` 元数据，App 按 `publicationRevision`（`Long.compareUnsigned`）做去重，并把 `REJECTED_STALE_REVISION` / `REJECTED_STALE_GENERATION` / `REJECTED_PARSE` / `CACHED_NOT_VISIBLE` / `APPLIED` 等状态通过 `diagnostics.uiApplied` 回执给 native（`parseDiagnosticUiPublication()` `:2494-2532`，`completeDiagnosticUiPublication()` `:2534-2546`）。
>
>
>

---

### 2.5 连接、握手、心跳、重连、超时

#### 连接生命周期

\```
App: startServer()  → LocalServerSocket(@xf_game_control_v2) + ServerSocket(127.0.0.1:39816..)
                   ↓ accept
抽象 socket: 校验 peer（acceptAbstractPeer，要求 uid%100000 与目标 uid%100000 相同，且 pid != 自己）
                   ↓
candidate（最多 8 个并发候选，MAX_CANDIDATES，ipcV2RuntimeState.Candidate）
                   ↓ handshake.challenge / welcome 双向 HMAC 校验（HANDSHAKE_TIMEOUT_MS = 3000）
                   ↓ promoteAuthenticated → Session（带 serverGeneration）
READY 之前：App 先推 config.replace，等 ack 对得上 revision 才 ready
                   ↓ ready=true → notifyConnected → cppConnectedFlag = true
\```

- `IpcV2RuntimeState` 有 `generation` 计数器：`stopServer()`/`startServer()` 每次自增，旧 generation 的连接一律判为 stale（`LocalSocketIPC.isCurrent()` `:1157-1159`）。
- `expectedPeerUid` 由 `configure(dir, uid)` 传入，取的是 `com.脱敏.jkchess` 的 uid（找不到包则 `-1`）（`SharedMemManager.java:341-343`）。
- TCP 回退通道**不校验 uid/pid**（`dispatchCandidate` 里 peerPid/-1, peerUid/-1, transport=1），但**仍要求 token 握手**。TCP 不是可选项而是并行监听：`startServer()` 同时起抽象 socket 和 TCP 两个 accept 循环。

#### 心跳与超时

| 常量 | 值 | 用途 | 出处 |
|-|-|-|-|
| `ACCEPT_TIMEOUT_MS` | 3000 | accept/握手读超时 | `LocalSocketIPC.java:49` |
| `HANDSHAKE_TIMEOUT_MS` | 3000 | 握手阶段 `setReadTimeout` | `:53` |
| `FRAME_TIMEOUT_MS` | 5000 | 握手完成后的读超时（每 5 s 无帧即醒一次去检查心跳） | `:52` |
| `HEARTBEAT_INTERVAL_MS` | 5000 | App 主动 ping 间隔 | `:54` |
| `HEARTBEAT_TIMEOUT_MS` | 30000 | **30 s 没收到任何帧即判定断线** | `:55` |
| `REQUEST_TIMEOUT_MS` | 3000 | `sendCommand()` 默认请求超时 | `:60` |
| `ACTION_TTL_MS` | 5000 | 业务动作 `ttlMs` | `IpcActionSender.java:10` |
| `REQUEST_TIMEOUT_MS`（动作） | 6000 | 业务动作请求超时 | `IpcActionSender.java:11` |
| `CONFIG_SYNC_TIMEOUT_MS` | 30000 | 配置/配色同步等的 pending 超时 | `:50` |
| `MAX_CONFIG_SYNC_RETRIES` | 5 | 配置同步最大重试 | `:58` |
| `HEX_QUERY_TIMEOUT_MS` | 4000 | 海克斯查询整体超时 | `SharedMemManager.java:49` |
| `MATCHUP_SNAPSHOT_MAX_AGE_MS` | 6500 | 对手快照保鲜期 | `SharedMemManager.java:50` |
| `pending` 队列容量 | 128 | 未决请求上限，满则 `busy` | `LocalSocketIPC.java:74`；`IpcV2PendingRequests` |
| 出站队列容量 | control 64 / request 128 / state 64（唯一键）/ event 16 | 满则 `BUSY` | `LocalSocketIPC.java:245`；`IpcV2OutboundQueue` |

**心跳检测点有两处**：`readerLoop()` 在每次读超时（`InterruptedIOException`）时检查 `elapsedRealtime() - lastReceivedBootMs > 30000` → `disconnectIfCurrent(session, "heartbeat timeout")`（`:684-687`）；`maintain()` 每秒定时也做同样检查（`:760-761`）。`maintain()` 同时负责 `pending.expire(...)`：未写出的 pending 以 `request_timeout_before_write` 收尾，已写出的以 `response_timeout` 收尾（`:759`）。

#### 断线与重连

- 断线原因字符串（`disconnectIfCurrent(session, reason)` 的 reason）：`"heartbeat timeout"`、`"reader failure"`、`"writer failure"`、`"config sync failed"`、`"forced reconnect"`（`:664, 686, 691, 950, 1062`）。
- 断线时 `pending.failSession(sessionId)` 把所有未决请求分别以 `session_replaced`（未写出）或 `peer_disconnected_after_write`（已写出）终结（`closeConnection()` `:1083-1086`）。
- **宽限期**：UI 侧 `CONNECTION_LOST_GRACE_MS = 2500`（`FloatingWindowService.java:290, 22455`）——掉线后 2.5 s 才把状态灯变红；`MainActivity` 侧 `EXISTING_RUNTIME_RECONNECT_GRACE_MS = 35000`（`MainActivity.java:81`）用于判断"已有进程还需不需要重注入"。
- **重连策略**：App 不主动重连，靠 native 侧重连（`needsReconnect`/`forceDisconnectStale()` `:1058-1063`）；重连前 App 用 `prepareReconnectBootstrap()` 把当前 token 重新写成 bootstrap 文件（`MainActivity.java:1684`）。
- 配置同步失败时指数退避重试：`min(8000, (1 << min(n-1,4)) * 500)` ms，即 500/1000/2000/4000/8000 ms，超过 5 次直接断线（`scheduleConfigRetry()` `:942-961`）。

#### `isCppConnected` 的真实语义

```java
// SharedMemManager.java:1590-1592
public boolean isCppConnected() {
    return this.socketIPC.isClientConnected() && this.cppConnectedFlag;
}
\```

- `socketIPC.isClientConnected()` = 存在 active session 且 `ready == true` 且未关闭（`LocalSocketIPC.isClientConnected()` `:1037-1040`）。
- `cppConnectedFlag` 是两个来源的或：连接建立并配置同步完成后置 true（`SharedMemManager.init()` 的 `ConnectionListener.onClientConnected()` `:430-435`），以及 native 推送 `connected{value}`（`handleConnected()` `:2097-2103`）。
- **`ready` 的达成条件比较苛刻**：握手成功 ≠ ready。必须 App 下发 `config.replace` → native 回 ack 且 `ack.revision == 发送的 revision` → App 再下发 `hudStyle.replace` → 才 `ready.compareAndSet(false,true)`（`handleConfigAck()` `:917-940`）。在此之前 native 发的业务帧会被直接拒（`business frame received before ready`，`:717-718`）。
- App 侧 `getDiagnostics()` 会把状态显示成 `STOPPED` / `LISTENING` / `SYNCING` / `READY` 四态（`LocalSocketIPC.getDiagnostics()` `:1042-1056`）。

---

### 2.6 诊断共享内存页（`DiagnosticSharedMemoryBridge`）

这是**唯一的真实共享内存**。生命周期：

\```
App: DiagnosticSharedMemoryBridge.create(generation)   → nativeCreateReader(generation)
     （App 进程内加载 libdemo.so，见 NativeLibraryLoader → NativeLibrarySelector，PRIMARY_RUNTIME = "demo"）
     duplicateForSend() → nativeDuplicateReaderFd(generation) → ParcelFileDescriptor
     ↓ 经 LocalSocket 的 SCM_RIGHTS 随 diagnostics.trace.attach 帧发给游戏进程
native(游戏进程): mmap 同一页，按 featureMask 往里写事件
App: 轮询 nativeDrain / nativeReadHeader / nativeReadThreadStacks / nativeReadFeatureHealth / nativeReadCrashSlot
\```

**8 个 native 方法**（`DiagnosticSharedMemoryBridge.java:27-41`）：
`nativeCloseReader(long)`、`nativeCreateReader(long)`、`nativeDrain(long,long,int) → long[]`、`nativeDuplicateReaderFd(long) → int`、`nativeReadCrashSlot(long) → long[]`、`nativeReadFeatureHealth(long) → long[]`、`nativeReadHeader(long) → long[]`、`nativeReadThreadStacks(long) → long[]`。

**页大小**：`PAGE_BYTES = 262144`（256 KiB）。native 的 attach 应答必须回 `{generation == 请求值, schema == 1, mappedSize == 262144}`，三者缺一 App 就判失败（`FloatingWindowService.java:4798`）。`TraceCatalog.SCHEMA = 1`。

**Header 布局**（9 个 u64，`HeaderSnapshot` `DiagnosticSharedMemoryBridge.java:43-65`）：

| 下标 | 字段 | 含义 |
|-|-|-|
| 0 | `generation` | 页代数（与 attach 请求一致） |
| 1 | `mode` | 1 / 2（DEEP），来自 `DiagnosticGrant.Mode` |
| 2 | `writeTicket` | **写票据 / 生产者写指针** |
| 3 | `droppedEvents` | 丢弃事件累计 |
| 4 | `gameFrameHeartbeatNs` | 游戏帧心跳 |
| 5 | `nativeWorkerHeartbeatNs` | native worker 心跳 |
| 6 | `matchEpoch` | 对局纪元 |
| 7 | `flags` | 位标志 |
| 8 | `attached` | != 0 表示已挂载 |

>
> 该头部**没有 magic 常量**，也没有显式版本字段；页的识别与版本靠 `generation` + attach 应答里的 `schema` 字段。
>
>
>

**事件环形缓冲**：`nativeDrain(generation, fromTicket, maxCount)`，`maxCount ∈ (0, 2048]`，返回
`long[3 + count*14]` = `[0]=nextTicket, [1]=droppedEvents, [2]=count, 之后 count 条 14×u64 记录`（`drain()` `:241-259`，`FIELDS_PER_EVENT = 14`）。每条事件 14 个 u64：

`seq, monoNs, opId, matchEpoch, threadId, featureId, stepId, phase, result, reason, arg0, arg1, durationUs, flags`

**线程栈**：返回 `long[1 + n*43]`，`[0]=n`（n ≤ 16），每个线程 43 个格：`threadId, frameDepth(≤8), flags, 然后最多 8 帧 × {opId, enterMonoNs, featureId, stepId, flags}`（`FIELDS_PER_THREAD = 43`，`FIELDS_PER_FRAME = 5`，`MAX_STACK_DEPTH = 8`，`MAX_THREAD_STACKS = 16`）。

**功能健康度**：`long[1 + n*10]`，`[0]=n`（n ≤ 64），每条 10 格：`featureId, lastSuccessMonoNs, lastFailureMonoNs, lastInputRevision, consecutiveFailures, lastReason, enabledConfig, capabilityState, hookState, recoveryCount`。

**崩溃槽位**：固定 `long[10]`：`sequence, monoNs, opId, threadId, moduleRelativeRva, signalNumber, moduleId, featureId, stepId, flags`。有效性判据是 **seqlock 风格**：`sequence > 0 && (sequence & 1) == 0`（`parseCrashSlot()` `:339-347`）。

**Feature ID 目录**（`TraceCatalog.Feature`）：`TRUST_RUNTIME_LIFECYCLE=100`、`IPC_CONFIG_SYNC=110`、`AUTO_PICK=200`、`AUTO_REFRESH_SHOP_LOCK=210`、`SELL_ALL_IN=220`、`SPECIFIED_HEX=230`、`OPPONENT_PREDICTION=240`、`GAME_RECOMMENDATION=250`、`BOARD_HUD=300`、`RANK_HUD=310`、`SHOP_HUD=320`。Step ID：`RECEIVE_INTENT=10, CHECK_CONFIG=20, CHECK_MATCH_STATE=30, CHECK_CAPABILITY=40, READ_INPUT_SNAPSHOT=50, MAKE_DECISION=60, CHECK_SHOP_LOCK=65, RESOLVE_ENTITY=66, DISPATCH_ACTION=70, WAIT_ACK=80, VERIFY_EFFECT=90, COMPLETE_OPERATION=100`。每个 feature 最多 5 个诊断 UI 槽位（`diagnosticUiPublications = new DiagnosticUiPublication[5]`，`SharedMemManager.java:80`）。

诊断的**开启/关闭**由远程授权驱动：`DiagnosticCoordinator` 从控制服务取 `DiagnosticGrant`（EC P-256 签名，公钥 `BuildConfig.JCC_DIAGNOSTIC_GRANT_PUBLIC_KEY_SPKI_BASE64URL`，key id `jcc-v480-production-diag-b8acc9063be36518`），校验通过后在 `ACTIVE_MATCH` 状态才 attach 页面；校验上下文里 `maxBytesCap = 20971520`（20 MiB）、`maxMatchesCap = 3`（`DiagnosticGrantVerifier.Context` `:45-66`、`DiagnosticCoordinator.verifierContext()` `:519-521`），`ACTIVE_RECOVERY_GRACE_MS = 30000`。

---

### 2.7 游戏状态数据是怎么流回 App 的

**结论：不是 App 主动读游戏内存，而是 native 主动推。** App 侧完全没有内存扫描代码，`SharedMemManager` 里所有 `*FromData(byte[])` 方法都已退化成只读缓存（例如 `readPlayersInfoFromData(byte[])` 直接 `return this.snapshot.cachedPlayers;`，`SharedMemManager.java:1674-1676`），`readSharedMemoryOnce()` 返回 `SENTINEL_DATA`（空 `byte[0]`，`:51, 1616-1618`）。

数据流：

\```
游戏进程 libdemo.so
   ├─ 读游戏内存 / hook il2cpp
   ├─ 组装 JSON，按帧率推 type=state 帧：
   │    updatePlayers / updateHeroPool / updateBoardPositions / updateMyOwnedHeroes /
   │    updateShopSlots / updateHexPrediction / updateMatchup / updateRankAnchors / ...
   └─ 对局边界推 match.started / match.ended
        ↓ socket
App: LocalSocketIPC.readerLoop → validateEnvelope(seq 严格 +1) → handleInbound
        ↓ MessageListener
App: SharedMemManager.handleCppMessage(method, params) → IpcPushDispatcher
        ↓ 各 parseXxx()
App: GameSnapshotStore 缓存 + 时间戳（cachedPlayers / cachedPlayersReceivedAtMs / cachedPlayerTimestamp++ 等）
        ↓ mainHandler.post / listener
App: FloatingWindowService 悬浮窗渲染
\```

各类数据的关键字段（来自各 parser，均为 JSON）：

- **玩家/经济/对手**（`updatePlayers`）：`id, hp, level, gold, rank, isMe, name, enemy, avatarUrl, avatarId, isBot, botKnown`，外加顶层 `dualPlay` 与 `turnState`（`IpcPlayersParser.java:24-52`，`SharedMemManager.parsePlayersData()` `:2330-2351`）。
- **商店**（`updateShopSlots`）：`slots[{index, heroId}]`，另有 FNV-1a 指纹用于判断是否变化（`IpcShopSlotsParser.java:38-50`）。
- **牌库**（`updateHeroPool`）：分 `pool`（分组 heroes，字段 `heroID/cost/currentCount/totalCount`）与 `locked`（`heroId/cost/leftCount/totalCount`）。
- **棋盘**（`updateBoardPositions`）：位掩码 `boardMask/benchMask` + 英雄 id 数组（`boardHeroes` 最多 28、`benchHeroes` 最多 9），英雄 id 用十进制位数编码星级（`twoStarCount()` 通过反复 `/10` 取首位判 2 星，`IpcBoardPositionsParser.java:45-68`）。
- **海克斯**（`updateHexPrediction`）：4 个阶段等级 + 实时卡池 id/权重/总权重 + 每阶段抽数；`matchGeneration` 长度必须 22，否则整帧丢弃（`IpcHexLevelsParser.java:44-47`）。
- **对手预测**（`updateMatchup`）：`myId/opponentId/matchId/source` + `pairs[{p1,p2,ghost}]`；`source` 不同优先级 + `MATCHUP_SNAPSHOT_MAX_AGE_MS = 6500` 保鲜，低优先级来源会被丢弃（`MatchupSnapshot.shouldAccept()`，`SharedMemManager.java:2480`）。
- **是否有活跃对局**：由 `GameHudSessionPolicy.isReady(...)` 综合判定 —— 需要 `cppConnectedFlag` + `sessionActive` + `isMatchActive` + 拿到本地玩家 + 棋盘证据（`localPlayerId ∈ [0,8)`，棋盘证据要求 `hasLocalBoard || 不同玩家数 >= 4`）以及各时间戳新鲜度（`GameHudSessionPolicy.java:7-13`、`SharedMemManager.hasFreshActiveGameSession()` `:1754-1757`）。

---

### 2.8 值得注意的实现细节

- **所有入站帧的 `seq` 必须严格 +1**。这是主动防御：`IpcV2Sequence.accept()` 只接受 `lastAccepted + 1`，乱序/重放/丢帧都会直接断链（`LocalSocketIPC.validateEnvelope()` `:1118`，`IpcV2Sequence.java:18-25`）。
- **fd 传递只在抽象 socket 上允许**：`writerLoop()` 里若 `transport != 0` 或 socket 不是 `LocalSocket`，带着 fd 的帧直接抛 `fd transport requires authenticated LocalSocket`（`LocalSocketIPC.java:642-646`）。所以诊断共享内存页在 TCP 回退通道上不可用。
- **state 队列是"按方法名去重"的**：`IpcV2OutboundQueue.offerStateReplacing(method, frame)` 用 `LinkedHashMap<String,T>`，同一 method 只保留最新一帧，旧帧对应的 pending 会被 `pending.cancel()`（`IpcV2OutboundQueue.java:79-95`，`enqueueLatestConfig()` `:892-897`）。出队优先级：control > request > state > event（`:104-116`）。
- **配置同步用单调递增 revision + 持久化高水位**：`ipc_v2_config_revision` SharedPreferences 存 `high_watermark`，保证 App 重装/重启后 revision 不回退（`IpcConfigSync.java:14-15, 60-61`、`IpcV2ConfigRevisionPolicy`）。native 必须回显同一个 revision，否则视为失败并重试（`:925-928`）。
- **`hex.query` 是"广播 + 多等待者"模式**：`HexQueryBroker` 单飞（`inFlight`）——多个调用方挂在 `waiters` 上，只发一次 `hex.query`，收到 `updateHexPrediction` 或 4000 ms 超时后统一回调（`HexQueryBroker.java`、`SharedMemManager.java:1467-1485, 2468`）。
- **兼容性回退**：`chess.sell` 若收到 `invalid_request` / `unknown_method`，会自动降级重发"只有 `mode`"的旧格式（`SharedMemManager.java:1004-1016`）。说明 native 版本可用性检测靠错误码完成。
- **native 版本可由字段有无探测**：`updatePlayers` 里 App 会用 `has("avatarUrl")` 判断"跑的是不是旧包"（`SharedMemManager.java:2305`）。
- **App 自己也加载了同一份 native 库**：`NativeLibrarySelector` 选 `libdemo.so`（x86 ABI 走 `libdemo_compat.so`），App 进程用它创建诊断页（`nativeCreateReader`）和做信任校验（`NativeTrustBridge` 的 20 个 native 方法），游戏进程用同一份库做被注入端。
- **App 侧线程名**：`IPC-v2-IO-<nanoTime>`、`IPC-v2-Maintenance-<nanoTime>`，均为 daemon（`LocalSocketIPC.daemonThread()` `:1251-1256`）。

---

## 三、阵容推荐与羁绊计算

### 3.0 一句话结论

阵容数据是**「内置 assets 兜底 + 远端签名下发覆盖」**的双层结构：APK 里打包一套 `assets/lineup/<setId>/*.json`，运行时优先使用从 `jcc.zhuzhufaka.cn` 下载、经 **ES256(P-256) 签名 + SHA-256 内容寻址**校验后落盘的「bundle」（`filesDir/lineup_data_v2/`），旧的 `filesDir/lineup_data/` 作为 legacy 兼容层。

**真正的算法只有两个**，都在 Java 侧：

1. **羁绊计算 `TraitCalculator`** —— 不是加权打分，而是「按 paint 去重计数 → 查阈值表得到 tier」。每个英雄的 `speciesId` 与 `classId` 各计一次，羁绊等级 = 阈值表中不超过当前计数的最大档位。
2. **阵容评分 `LineupRecommender`** —— 唯一带权重的公式：玩家已拥有英雄的 paint 集合与每套阵容的 early/mid/late 三段做交集计数，加权求和后减惩罚、加品质奖励，排序取 Top-N。

商店预测、海克斯预测、对手预测在 Java 侧**完全没有算法**，全部由注入 native 算好后通过 IPC push 回传；Java 只做解析、缓存、以及一处展示层的 `1-(1-p)^n` 换算。

---

### 3.1 阵容数据从哪来

#### 3.1.1 三级数据源解析顺序

`LineupDataSource.resolveDataset(Context, setId)`（`LineupDataSource.java:86`）按固定优先级回退：

| 优先级 | 来源 | 目录 / 载体 | `DatasetSnapshot.override` | `generation` 值 |
|-|-|-|-|-|
| 1 | v2 Bundle Store | `filesDir/lineup_data_v2/sets/<setId>/versions/<gen>/` | `true` | `CURRENT` 指针里的 64 位十六进制 generation |
| 2 | Legacy Override | `filesDir/lineup_data/<setId>/`（单文件平铺） | `true` | `"legacy:" + SHA-256(...)` |
| 3 | APK 内置 assets | `assets/lineup/<setId>/` | `false` | `"asset:lineup/<setId>"` |

三处都要求同一组**四个必需文件**（`LineupDataSource.REQUIRED_FILES`）：`lineup_meta.json`、`chess_meta.json`、`race.json`、`job.json`。`setId` 为空串时统一规范化为目录名 `_default`（`LineupBundleStore.DEFAULT_SET`）。

`setId` 校验在 `LineupBundleStore.canonicalSetId(String)`：长度 ≤ 32、只允许 `[A-Za-z0-9._-]`、禁止 `..`。这同时是路径遍历防线。

#### 3.1.2 数据格式（字段名逐项来自解析代码）

**`lineup_meta.json`** —— 顶层 `version`（字符串，用于版本比较）、`setId`、`lineups`（数组）。每个阵容对象由 `LineupRepo.loadLineups`（`LineupRepo.java:716`）解析：

| JSON 字段 | 映射到 `Lineup` 字段 | 说明 |
|-|-|-|
| `id` | `f89id` | 阵容唯一 id |
| `name` / `author` | `name` / `author` |  |
| `quality` | `quality` | 品质，评分时用：`"S"` 加 1.0 分，`"N"` 加 0.5 分 |
| `feature` | `featureMapId` | 海克斯/地区特性 id |
| `share_code` | `shareCode` | 游戏内分享码，`lineup.syncToSlot` 必需 |
| `early_info` / `d_time` | `earlyInfo` / `dTime` |  |
| `equip` | `equipOrder` | 逗号分隔的装备优先级列表 |
| `hex_recomm` / `hex_replace` | `hexRecomm` / `hexReplace` | 推荐/可替换海克斯 |
| `early_heroes` / `mid_heroes` / `late_heroes` | `earlyHeroes` / `midHeroes` / `lateHeroes` | 字符串数组；也兼容写成单个字符串（`readMaybeArray`） |
| `final_level` | `finalLevel` |  |
| `final_units` | `finalUnits` | 对象数组，见下 |

`final_units[]` 每项由 `LineupRepo.loadLineups` 构造为 `LineupUnit(heroId, location, carry, equip, type)`：

| JSON 字段 | 含义 |
|-|-|
| `hero_id` | 英雄 id 字符串 |
| `loc` | 棋盘坐标，格式见 3.7.2 |
| `carry` | 是否主 C |
| `equip` | 该英雄的装备 id 列表（逗号分隔） |
| `type` | 默认 `"hero"`；`LineupUnit.isHero()` = `"hero".equals(type) |

**`chess_meta.json`** —— 顶层 `heroes` 是一个以 id 字符串为 key 的对象。`LineupRepo.loadHeroes`（`LineupRepo.java:648`）逐项读：`id`、`name`（中文名）、`cost`、`species`（种族，字符串转 int）、`class`（职业，字符串转 int）、`paint`（**去重键**）。

`paint` 是这套系统的核心抽象：它把「同一个英雄的不同星级/不同形态 id」归一到同一个字符串。羁绊计数、阵容匹配全部以 paint 为单位，因此**同名英雄在场上出现多次只算一次**。

**`race.json` / `job.json`** —— 结构完全相同，都以 `"traits"` 为顶层 key，`LineupRepo.loadTraits(..., "race.json", false)` 与 `(..., "job.json", true)` 的唯一区别是 `isJob` 标志。每项字段：`id`、`name`、`numList`、`picture`。

`numList` 是**用 `|` 分隔的激活阈值**，由 `LineupRepo.parseThresholds` 解析成 `int[]`。例如 `"2|4|6"` 表示该羁绊在 2/4/6 个英雄时分别达到 1/2/3 级。

#### 3.1.3 远端下发与签名校验

**入口**：`LineupMetaUpdater.checkAndUpdate(Context, setId, Callback)`（`LineupMetaUpdater.java:112`），单线程 daemon executor 串行执行，结果回主线程。

默认 URL（`LineupMetaUpdater.DEFAULT_URL`）：

```python
https://jcc.zhuzhufaka.cn/v2/api/lineup/manifest?setId={setId}
\```

可在 SharedPreferences `lineup_cdn` 的 `url` 键里覆盖（`getUrl`/`setUrl`），但**覆盖后仍受主机白名单约束**。

**签名信封**：服务端返回一个 JSON 信封，字段由 `requireExactFields` 强制为 **恰好四个**：`algorithm`、`key_id`、`payload`、`signature`。

`LineupManifestPolicy.verifyEnvelope`（`LineupManifestPolicy.java:81`）的判定条件写死为：

- `algorithm` 必须精确等于字符串 `"ES256-P1363"`（ECDSA P-256，签名用 P1363 原始 r||s 格式而非 DER）；
- `key_id` 必须等于 `JccReleaseConfig.VERSION_POLICY_KEY_ID`；
- `payload` 解码后非空且 ≤ 65536 字节；
- `JccVersionPolicy.verify(payload, signature, publicKey)` 验签通过。公钥由 `loadReleasePublicKey()` 从 `JccReleaseConfig.VERSION_POLICY_PUBLIC_KEY_SPKI_BASE64URL` 解码 SPKI，并**强制校验是 256 位曲线**（非 P-256 直接抛错）。

若 `VERSION_POLICY_KEY_ID` 或 `VERSION_POLICY_PUBLIC_KEY_SPKI_BASE64URL` 为空，直接返回「阵容发布公钥尚未配置」，**不做任何降级放行**。

**Manifest 结构**（`LineupMetaUpdater.parseManifest` + `LineupManifestPolicy.Manifest`）：顶层字段 `schema`、`set_id`、`revision`、`version_name`、`bundle_sha256`、`data_schema`、`published_at`、`files`；`files` 恰好四项，每项 `{path, size, sha256}`。

**`LineupManifestPolicy.validate(manifest, setId, nowEpochSeconds)`** 的完整校验清单：

| 校验项 | 规则 | 失败 Code |
|-|-|-|
| schema / dataSchema | 必须都 == 1 | `SCHEMA_INVALID` |
| revision | > 0 | `SCHEMA_INVALID` |
| 发布时间 | `published_at` > 0 且 ≤ now + **300 秒**时钟偏移 | `SCHEMA_INVALID` |
| versionName | 非空、UTF-8 ≤ 128 字节、无控制字符 | `SCHEMA_INVALID` |
| bundleSha256 | 必须是小写十六进制、长度 64 | `SCHEMA_INVALID` |
| set_id | 与请求的 setId 精确相等（双方都先 canonical 化） | `SET_ID_MISMATCH` |
| 文件数 | 必须恰好 4 个，且不能有未知文件名 | `INCOMPLETE_BUNDLE` |
| 单文件大小 | `0 < size ≤ 8388608`（8 MiB），累计 ≤ 16777216（16 MiB） | `TOO_LARGE` |
| 文件路径 | 必须 `startsWith("files/")`，长度 ≤ 512，禁止 `/` 开头、禁止 `\ ? # %`，每段必须非空且非 `.`/`..`，字符集限 `[A-Za-z0-9._-]`，且**最后一段必须等于文件名本身** | `PATH_INVALID` |
| bundle 摘要 | 重算 `computeBundleDigest` 必须等于 `bundle_sha256` | `HASH_MISMATCH` |

**Bundle 摘要算法**（`LineupManifestPolicy.computeBundleDigest`，`LineupManifestPolicy.java:135`）——这是 generation id 的来源，也是本地落盘的目录名：

```python
SHA-256(
  for f in ["lineup_meta.json","chess_meta.json","race.json","job.json"]:   # 固定顺序
      len_be32(f.name) || f.name
      len_be32(32)     || raw_bytes(f.sha256)      # 注意：喂的是原始 32 字节，不是 hex 字符串
  len_be32(|setId|) || setId
  be64(revision)
).hex()
\```

固定文件顺序 + 长度前缀 + 把 revision 也纳入摘要，使得 generation 同时绑定了内容、赛季和版本号。

**下载校验**：每个文件用 `resolveFileUrl` 基于 manifest URL 解析，并再次过白名单；下载后 `LineupManifestPolicy.verifyFile` 要求**字节数完全等于 manifest 的 size** 且 SHA-256 完全匹配（`HASH_MISMATCH`）。

**URL 白名单**（`LineupMetaUpdater.isAllowedUrl`，`LineupMetaUpdater.java:603`）——两条规则：

- manifest 请求：必须是 `https`、host 精确等于 `jcc.zhuzhufaka.cn`、无 userInfo、无 fragment、端口为 -1 或 443、路径精确等于 `/v2/api/lineup/manifest`、query 必须匹配正则 `setId=[A-Za-z0-9._-]{0,32}`；
- 文件请求：同 host/protocol 约束，路径必须以 `/v2/api/lineup/files/` 开头且**不允许有 query**。

`getJson` 另外做了：禁止重定向（`setInstanceFollowRedirects(false)`，遇 3xx 直接抛 `redirect rejected`）、强制 `Content-Type` 以 `application/json` 开头、`Accept-Encoding: identity`、`User-Agent: XFjcc/LineupMetaUpdater-v2`、连接超时 5s / 读超时 10s、响应体长度必须与 manifest 声明一致、manifest 信封上限 98304 字节。

#### 3.1.4 版本与降级策略

`LineupRevisionPolicy.evaluate(installedRevision, installedVersion, hasBundle, manifestRevision, manifestVersion)`（`LineupRevisionPolicy.java:26`）返回 `Code`：

- `INVALID` —— 本地 revision < 0，或远端 versionName 为空；bundle 路径下远端 revision < 0 也算；
- `DOWNGRADE_REJECTED` —— 远端 revision < 本地（bundle 路径），或版本号比较结果 < 0（非 bundle 路径）；
- `NO_UPDATE` —— 版本号字符串相等且非 bundle 路径；
- `CHECK_BUNDLE` —— 其余情况，`commitRevision` 返回 `localRevision + 1`（非 bundle 路径）或直接用 manifest revision。

版本比较 `compareVersion` 走 `.` 分段：逐段优先按数值比较，若任一段含非数字字符则退化为字符串 `compareTo`。**注意它是有符号解析（`Long.parseLong`），与 `LineupDataSource.compareVersion` 的 int 版本是两份独立实现。**

#### 3.1.5 落盘：内容寻址 + 原子切换 + 崩溃回滚

`LineupBundleStore.commit(Bundle)`（`LineupBundleStore.java:170`）是本项目里工程质量最高的一段：

1. `prepare(bundle)` 重新计算与 manifest 完全相同的 digest 作为 **generation**，同时校验四个文件非空、大小限制、文件名集合精确匹配。这一步意味着**目录名本身就是内容的校验和**。
2. 目录布局：`<root>/sets/<setId>/versions/<generation>/`，内含四个 JSON + 一个 `manifest.meta`（key=value 文本，含 `schema=1`、`setId`、`revision`、`versionName`（Base64URL 编码）、`generation`、以及每个文件的 `size.X` / `sha256.X`）。
3. 写入 staging 目录 `.staging-<UUID>`，每个文件 `writeSynced`（write + flush + **FileDescriptor.sync**），再 `syncDirectory`（对目录 fd 做 `force(true)`）。
4. `atomicMove`（`Files.move` + `ATOMIC_MOVE`）把 staging 一次性改名成 generation 目录——不支持原子移动则直接失败，不做非原子降级。
5. `writePointer` 原子更新 `CURRENT` 文件（key=value：`schema` / `setId` / `current` / `previous` / `revision`），保留 `previous` 指针。
6. 读取时 `loadSnapshot` **逐文件重新计算 SHA-256 并与 manifest.meta 核对**；任何不匹配都会触发 `recoverLocked`，自动回退到 `previous` generation 并重写 `CURRENT`。

并发用 `ConcurrentHashMap<String,Object> LOCKS` 以「root 绝对路径 + `\n` + setId」为 key 做进程内互斥。

`commit` 的返回值 `Code` 区分 `UPDATED` / `NO_UPDATE`（revision 相同且 generation 相同）/ `VERSION_CONFLICT`（revision 相同但 generation 不同 —— 说明服务端在同一 revision 上换了内容，会被拒绝）/ `DOWNGRADE_REJECTED` / `STAGE_IO_FAILED`。

#### 3.1.6 赛季自动切换

`LineupRepo.bindAutoSync(Context)`（`LineupRepo.java:421`）订阅 `GameSeasonBus`：当游戏内赛季 id 变化且与当前 `targetSetId` 不同时，起一个名为 `lineup-autosync` 的线程调用 `reload(context, newSetId)`，实现「换赛季自动换整套阵容数据」。`reload` 走 `buildCandidate` → `activateCandidate` 的**先构建后切换**模式，构建失败则保留旧 state 并打日志。

---

### 3.2 羁绊计算 `TraitCalculator`（核心）

#### 3.2.1 数据结构

`TraitCalculator.compute(Set<String> paints, LineupRepo repo)`（`lineup/TraitCalculator.java:55`）：

```java
HashMap<Integer,Integer> counts = new HashMap<>();
for (String paint : paints) {
    HeroMeta h = repo.getHeroByPaint(paint);
    if (h == null) continue;
    if (h.speciesId > 0) inc(counts, h.speciesId);   // 种族
    if (h.classId   > 0) inc(counts, h.classId);     // 职业
}
// 每个非零 id → TraitDef → ActiveTrait(def, count)
Collections.sort(list, COMP_ACTIVE_DESC);
\```

**关键点**：一个英雄同时给它的 `speciesId` 和 `classId` 各 +1（例如某英雄是「龙族 + 法师」，则龙族 +1、法师 +1）。计数单位是 **paint 而不是英雄 id**，所以同一英雄的 1/2/3 星在场上只贡献 1 点——这正是记牌器「不重复计数」的实现方式。

#### 3.2.2 等级与激活判定

`TraitDef.getActivatedTier(int count)`（`LineupRepo.java:89`）：

```java
int tier = 0;
for (int i = 0; i < thresholds.length; i++)
    if (count >= thresholds[i]) tier = i + 1;
return tier;
\```

即**线性扫描阈值表，取满足条件的最大下标 +1**。阈值来自 `race.json`/`job.json` 的 `numList`（`|` 分隔）。例如 `numList="2|4|6"`、count=5 → tier = 2。

`ActiveTrait` 构造函数（`lineup/TraitCalculator.java:29`）：

- `count` = 命中该羁绊的 paint 数
- `tier` = 上面算出的档位
- `activated` = `tier > 0`

**没有权重、没有系数、没有溢出收益**——超过最高档的部分不产生额外收益，也不会被裁剪。

#### 3.2.3 排序

`COMP_ACTIVE_DESC`（`lineup/TraitCalculator.java:15`）四级比较，决定 UI 里羁绊的展示顺序：

1. `activated` 降序（已激活的排前面）
2. `tier` 降序（档位高的靠前）
3. `count` 降序（同档位下数量多的靠前）
4. `def.id` 升序（同数量按 id 稳定排序）

#### 3.2.4 辅助方法

- `computeActivated` —— 过滤出 `activated == true` 的子集。
- `computeForLineup(List<String> heroIds, repo)` —— 先 `repo.stringIdsToPaints(heroIds)` 转 paint，再调 `computeActivated`。**这是评分流程复用的入口**（`LineupRecommender.java:134`）。
- `ActiveTrait.distanceToNextTier()` —— 遍历阈值返回第一个 `count < threshold` 的差值，即「还差几个到下一档」；已满级返回 0，无阈值返回 `Integer.MAX_VALUE`。
- `isJob()` —— 透传 `def.isJob`，区分「职业」（job.json）与「种族」（race.json）。

UI 侧的雷达图 `TraitRadarView.ratio(ActiveTrait)` 用 `count / thresholds[last]` 归一化到 `[0.05, 1.0]` 作为顶点半径——**这是纯展示，不回流到推荐算法**。

---

### 3.3 阵容评分算法 `LineupRecommender`（核心）

#### 3.3.1 权重常量

```java
EARLY_HOLD_THRESHOLD = 8;      // 判断「前期」的 paint 数量阈值（名字写的是 hold，实际判的是 paints.size() < 8）
W_EARLY  = 3.0;                // 前期英雄命中权重
W_MID    = 2.0;                // 中期英雄命中权重
W_LATE   = 1.0;                // 后期/终局英雄命中权重
W_PENALTY = 0.05;              // 每个「无用英雄」的惩罚
PREF_BONUS = 30.0;             // 命中用户指定羁绊的巨额奖励
\```

#### 3.3.2 入口

`recommend(Set<Integer> ownedIds, Integer preferredTraitId, int limit, LineupRepo repo)`（`LineupRecommender.java:69`）：

1. repo 未 ready 直接返回空列表；
2. `limit <= 0` 时默认取 **5**；
3. `repo.normalizeToPaints(ownedIds)` 把玩家拥有的英雄 id 归一成 `Set<String> paints`（这套归一非常宽容，见 3.4.3 的 `resolveHero` 多级回退）；
4. `boolean earlyPhase = paints.size() < 8`；
5. 对**全部阵容**逐个 `score(...)`，按 `COMP_SCORE_DESC` 排序，截断到 `limit`。

`scoreOne(lineup, ownedIds, preferredTraitId, repo)` 是对单套阵容的公开版本，复用同一个 `score`。

#### 3.3.3 评分公式

`LineupRecommender.score(...)`（`LineupRecommender.java:95`）逐步展开：

**第一步：阵容侧三套 paint 集合**

```python
earlySet = repo.stringIdsToPaints(lineup.earlyHeroes)
midSet   = repo.stringIdsToPaints(lineup.midHeroes)
lateSet  = paintsFromUnits(lineup.finalUnits)          // final_units 里 hero 的 paint
           ?? repo.stringIdsToPaints(lineup.lateHeroes) // final_units 为空时回退
\```

**第二步：三个交集计数** —— `intersectCount(a, b)` 是手写的迭代计数（遍历较小集合，检查是否在较大集合中），得到 `earlyHits`、`midHits`、`lateHits`。

**第三步：无用英雄惩罚**

```python
all = earlySet ∪ midSet ∪ lateSet
extraHeroes = |{ p ∈ ownedPaints : p ∉ all }|
\```

**第四步：主评分**

```python
earlyWeight = earlyPhase ? 4.5 : W_EARLY          // 开局阶段前期命中权重从 3.0 提到 4.5
score = earlyHits * earlyWeight
      + midHits   * 2.0
      + lateHits  * 1.0
      - extraHeroes * 0.05
\```

**第五步：品质奖励**

```java
if ("S".equalsIgnoreCase(lineup.quality))      score += W_LATE;   // +1.0
else if ("N".equalsIgnoreCase(lineup.quality)) score += 0.5;
\```

（源码里写成 `ExifInterface.LATITUDE_SOUTH`（值 `"S"`）与 `ExifInterface.GPS_MEASUREMENT_IN_PROGRESS`（值 `"N"`）——借用 EXIF 常量做字符串常量，属于混淆残留。）

**第六步：指定羁绊奖励**

```java
List<ActiveTrait> projected = TraitCalculator.computeForLineup(finalUnits 里的 heroId, repo);
if (preferredTraitId != null && preferredTraitId > 0
    && projected 中存在 def.id == preferredTraitId 的 ActiveTrait)
    score += 30.0;   // PREF_BONUS
\```

注意只检查**已激活**的羁绊（`computeForLineup` 内部走 `computeActivated`）。**30.0 远大于其它所有项之和的量级**，一旦命中基本锁定第一名。

**第七步：排序**

`COMP_SCORE_DESC`（`LineupRecommender.java:16`）三级稳定排序：

1. `score` 降序（`Double.compare`）
2. `earlyHits` 降序
3. `lineup.id` 字符串升序

**结果对象 `Recommendation`** 携带：`lineup`、`score`、`earlyHits` / `midHits` / `lateHits` / `extraHeroes`、`projectedTraits`、`preferredHit`，并提供 `missingPaints(owned, repo)` / `matchedPaints(owned, repo)` 两个差集工具（基于 `lineupAllPaints` = early ∪ mid ∪ finalUnits）。

#### 3.3.4 实际调用情况

全仓 grep `LineupRecommender.` 只有**一处生产调用**：

```java
// AutoLineupApplier.java:270
List<Recommendation> rec = LineupRecommender.recommend(linkedHashSet, null, 5, lineupRepo);
\```

即**自动模式永远传 `preferredTraitId = null`**，`PREF_BONUS` 分支在自动链路里从不触发；`limit` 固定 5。`scoreOne` 在 Java 侧没有调用点，应该是留给阵容面板 UI（WebView / 动态插件）走的公开 API。

---

### 3.4 英雄 ID 体系 `HeroIdMapper`

#### 3.4.1 五位十进制编号

英雄 id 是五位十进制数，**前两位 = 费用档位 + 10**，后三位是英雄序号：

| 前两位 | 费用 cost |
|-|-|
| 11 | 1 费 |
| 12 | 2 费 |
| 13 | 3 费 |
| 14 | 4 费 |
| 15 | 5 费 |

`HeroIdMapper.HeroInfo` 构造函数的实现就是这个编码的直接体现（`HeroIdMapper.java:965`）：

```java
HeroInfo(int id, String cn, String en) {
    int i = id;
    while (i >= 100) i /= 10;   // 11112 → 1111 → 111 → 11
    this.cost = i % 10;         // 11 % 10 = 1
}
\```

`getHeroesByCost(cost, setIdx)`（`HeroIdMapper.java:1042`）反过来用 `i3 = cost + 10` 做同样降位后匹配；`get5CostHeroes` 等价于 `cost == 5`（降位后 == 15）。

#### 3.4.2 按赛季分组的表

`HeroIdMapper` 静态初始化 6 个赛季的数据集，通过 `setIdx` 索引选择：

| setIdx | 赛季代号 | 地图/常量名 | 当前示例 |
|-|-|-|-|
| 0 | FUX | `FUX_ID_TO_CN_NAME` / `FUX_CN_TO_EN_NAME` | 复刻/福星 |
| 1 | S10 | `S10_*` |  |
| 2 | S16 | `S16_*` |  |
| 3 | S17 | `S17_*` + `S17_FORM_TO_BASE` |  |
| 4 | S8 | `S8_*` + `S8_FORM_TO_BASE` |  |
| 5 | S18 | `S18_*` + `S18_FORM_TO_BASE` |  |

每个赛季维护两张表：

- `Map<Integer,String> ID_TO_CN_NAME` —— id → 中文名；
- `Map<String,String> CN_TO_EN_NAME` —— 中文名 → 英文名（英文名同时是**资源文件名**）。

`getHeroAvatarPath(id, setIdx)`（`HeroIdMapper.java:988`）拼出 `heroes/<SET>/<englishName>.png`，其中 `<SET>` 取 `FUX`/`S10`/`S16`/`S17`/`S8`/`S18`。查不到的 id 统一返回中文名 `"未知英雄"`，`getHeroInfo` 遇到「未知英雄」返回 `null`。

#### 3.4.3 形态（form）映射

S17/S8/S18 有「同英雄的不同形态 id」（例如终极形态、变身后），用 `FORM_TO_BASE: Map<Integer,Integer>` 把形态 id 折回基础 id：

- `s17CanonicalBaseId(id)` / `s18CanonicalBaseId(id)` —— 若 id 本身在基础表里返回自身，否则查 `FORM_TO_BASE`，再否则返回原 id；
- `s17IsKnownHeroId(id)` / `s18IsKnownHeroId(id)` —— 基础表或形态表任一命中即为已知。

**没有为 FUX/S10/S16 提供对应的 form 映射**，这三个赛季只有单层表。

`getHeroIdsByChineseName(cn)` 会遍历全部 6 个赛季的基础表 + 形态表，收集所有同名 id（去重），用于「按名字查所有可能 id」。

#### 3.4.4 星级表示

**星级编码在 id 的十进制最高位**，由 `HeroStarId`（`lineup/HeroStarId.java`）处理：

```java
starOf(int id)  // 循环 /10 直到 <10，若结果在 [1,4] 则返回它作为星级，否则 0
baseOf(int id)  // 去掉最高位星数：id -= (lead - 1) * 10^k；再过一次 HeroIdMapper.s17CanonicalBaseId
\```

举例：`11112` → star 1（也即基础 id）；`21112` → 2 星；`31112` → 3 星；`41112` → 4 星。`starOf` 接受 1..4，与金铲铲支持 4 星 1 费单位的设定一致。

`LineupRepo.normalizeStarPrefix(int)`（`LineupRepo.java:900`）是同一套逻辑的第二份实现（去掉星位），仅当首位在 `[2,4]` 时才做减法。

**副本数与星级的换算**（`HeroStarId`）：

| 星级 | 需要副本数 |
|-|-|
| 1 | 1 |
| 2 | 3 |
| 3 | 9 |

`copiesForStar(star)` 与 `starForCopies(copies)` 是一对互逆函数，阈值分别是 1/3/9。

`HeroStarId.targetFor(Map<Integer,Integer> targets, int id)`：先按精确 id 查目标星级；查不到则用 `baseOf` 找到所有同基础英雄的条目取 `Math.max`。这是「目标星级」的解析规则。

#### 3.4.5 `LineupRepo` 侧的 id 归一化（非常宽容）

`LineupRepo.resolveHero(state, id)`（`LineupRepo.java:800`）对任意输入的 id 做**六到七级回退**，这是「游戏内 id 与数据表 id 对不上」的主要容错点：

1. `heroById.get(id)` —— 精确命中；
2. `heroById.get(normalizeStarPrefix(id))` —— 去掉星位后命中；
3. `heroByAlias.get(id)` —— 别名命中（别名在加载时批量注册）；
4. `heroByAlias.get(normalizeStarPrefix(id))`；
5. `heroByAlias.get(id % 10000)` —— 砍掉最高位（应对 5 位/4 位混用）；
6. `heroByAlias.get(normalizeStarPrefix(id) % 10000)`；
7. `resolveByMappedName(state, id)` —— 调 `HeroIdMapper.getChineseName(id, k)` 与 `getEnglishNameById(id, k)`，按 `k ∈ {0, 3, 2, 1, 4}` 的顺序（当前赛季优先）在各 setName 表里找，名字 key 经 `normalizeHeroNameKey` 归一（小写、去 `· . _ - 空格`，「未知英雄」视为空）；
8. 最后对 `normalizeStarPrefix(id)` 再重复一次第 7 步。

**别名注册**（`registerHeroAliases`，`LineupRepo.java:856`）——每个英雄在加载 `chess_meta.json` 时注册四个别名键：`id`、`normalizeStarPrefix(id)`、`id % 10000`、`normalizeStarPrefix(id) % 10000`。如果两个不同 paint 的英雄抢同一个别名键，该键会被**移除并加入 `ambiguousHeroAliases` 黑名单**，之后再也不会被注册（`registerHeroAlias`，`LineupRepo.java:864`）。同时 `name` 与 `paint` 也作为名字别名注册进 `heroByNameKey`，**先到先得**（`registerHeroNameAlias` 用 `containsKey` 判重）。

运行时还有两个便捷入口：`getCurrentRuntimeHero(id)` 先精确查、失败再去掉星位查；`getRuntimeIdsByPaint(paint)` 返回该 paint 下所有 id 并保证包含 `heroByPaint` 里那个主 id。

---

### 3.5 `OwnedHeroTracker`：场上英雄追踪

**数据来源是 IPC，不是本地文件。** 完整链路：

```python
native 推送 updateMyOwnedHeroes
  → SharedMemManager.parseMyOwnedHeroesData(JSONObject)   // SharedMemManager.java:2416
  → IpcMyOwnedHeroesParser.parse(...)
      JSON: { "heroes": [ {"heroId": int, "copies": int}, ... ], "pieceCount": int }
      → OwnedHeroCopies（heroId → copies 的不可变 LinkedHashMap）
  → 缓存进 snapshot
\```

`OwnedHeroTracker` 通过 `SharedMemManager.getMyOwnedTimestamp()`（一个**变更计数器**，`SharedMemManager.java:1694`）和 `getMyOwnedHeroIds()`（`SharedMemManager.java:1686`）读取。

**轮询机制**（`OwnedHeroTracker.tick`，`OwnedHeroTracker.java:160`）：

- 单例 + 独立 `HandlerThread`（线程名 `OwnedHeroTracker`），**1 秒轮询一次**（`POLL_INTERVAL_MS = 1000`），循环用 `postDelayed` 自重排；
- 只有当 `timestamp != lastTimestamp` 时才处理，避免重复回调；
- 每次变更回调 `OwnedChangeListener.onOwnedChanged(Set<Integer>)`（传当次快照的副本）；
- 新出现的 id 累加进 `everOwnedThisGame`（`LinkedHashSet`，本局累计拥有过的英雄并集），并对每个**新增** id 逐个回调 `NewHeroListener.onNewHeroOwned(int)`；
- **自动重置**：当 `myOwnedHeroIds` 连续为空超过 `RESET_AFTER_EMPTY_MS = 60000`（60 秒）时，清空 `everOwnedThisGame`——用于识别「新的一局已经开始」（卖光/清场超过一分钟）。另有公开 `resetForNewGame()` 供显式重置。

`stop()` 会 `removeCallbacksAndMessages(null)` + `quitSafely()` 并清空状态。

**注意**：`OwnedHeroTracker` 拿到的 id 是原生运行时 id（可能带星位），因此消费方（`AutoLineupApplier`）交给 `LineupRecommender` 后，是靠 `normalizeToPaints` 的多级回退去匹配的。

---

### 3.6 `AutoLineupApplier`：自动应用阵容

#### 3.6.1 开关与触发

- 开关存 SharedPreferences `lineup_auto_apply` 的 `enabled` 键，**默认 false**（`isEnabled`，`AutoLineupApplier.java:172`）；`setEnabled(true)` 会立刻触发一次 `tryRecommendAndApply("toggleOn")`，`setEnabled(false)` 会清空 battle panel 并调 `LineupActiveBus.clearIfAutoApplied()`。
- 独立 `HandlerThread`（线程名 `AutoLineupApplier`）+ `Handler`。

**四种触发源**：

| 触发源 | 代码位置 | 说明 |
|-|-|-|
| 定时轮询 | `periodicTick` | 每 `PERIODIC_RECHECK_MS = 5000` 毫秒一次 |
| 新英雄入手 | `OwnedHeroTracker.NewHeroListener` → `tryRecommendAndApply("newHero=" + id)` | 每买入一个新英雄立即重算 |
| 阵容库就绪 | `LineupRepo.OnReadyListener` → `tryRecommendAndApply("repoReady=" + setId)` | 数据加载/热更新完成后 |
| 手动 | `poke(String)` | 供 UI/测试主动触发 |

**节流**：`MIN_INTERVAL_MS = 2000`，距上次成功应用不足 2 秒直接返回。

#### 3.6.2 决策流程（`tryRecommendAndApply`，`AutoLineupApplier.java:245`）

1. 输入集合 = `OwnedHeroTracker.getEverOwned()` ∪ `SharedMemManager.peekInstance().getMyOwnedHeroIds()`（**两个来源求并集**，前者含历史、后者是瞬时的）；
2. 集合为空 → `syncBattlePanelLineups(null)` 清空、标记 `battlePanelCleared = true`、并**直接返回，不调 `LineupActiveBus.clear()`**（在下一次为空时才会走 `clearIfAutoApplied`，避免反复清空）；
3. `LineupRecommender.recommend(owned, null, 5, repo)`；
4. `buildSignature(rec)` —— 把 Top-5 阵容 id 用 `|` 拼接成签名字符串；
5. 若签名与 `lastAutoAppliedId` 相同 → **直接返回，不做任何 IPC**（这是最重要的去重：只有推荐结果变了才推游戏）；
6. 否则记录 `lastAutoAppliedId` / `lastApplyAt`，执行两个动作：

```java
syncBattlePanelLineups(rec);              // 推 Top-5 到游戏内阵容面板
syncDefaultNativeTarget(rec.get(0).lineup); // 把第一名设为"当前应用阵容"
\```

- `syncBattlePanelLineups` 把 Top-5 逐个 `LineupActiveBus.buildNativeLineupPayload(lineup, index)`（index = 0..4），组成 `JSONArray` 交给 `SharedMemManager.syncBattlePanelLineups(...)`；
- `syncDefaultNativeTarget` 调 `LineupActiveBus.get().applyByAuto(lineup)`。

#### 3.6.3 它到底做了什么？——**真的操作游戏，不只是改 UI**

`applyByAuto` 最终走 `LineupActiveBus.applyInternal`（`LineupActiveBus.java:265`），做三件事：

| # | 方法 | IPC 命令 / 通道 | 载荷 |
|-|-|-|-|
| 1 | `pushHeroIdsToNative` | **config-sync 通道** | `SharedMemManager.writeLineupAppliedHeroIds(int[])` → 写 config 键 `lineupAppliedHeroIds`（另有 `lineupAppliedStarTargets`），然后 `IpcConfigSync.requestSync()` 全量同步——这是「自动拿牌清单」 |
| 2 | `pushAppLineupToNative` | action **`lineup.apply`** | `buildNativeLineupPayload(lineup, 0)` |
| 3 | `pushSyncLineupToGameSlot` | action **`lineup.syncToSlot`** | `{shareCode, title, deckIndex:-1}`；**仅当 `lineup.shareCode` 非空才发**，否则日志记「v1 不支持无 shareCode（v2 计划用 ReplaceLineUpWithIndex 直接构造）」 |

清空路径对应 `pushHeroIdsToNative(空)` + `writeLineupAppliedTargets(new int[0], emptyMap)` + action **`lineup.clear`**。

三条 action 常量定义在 `IpcV2ActionMethods`：`LINEUP_APPLY = "lineup.apply"`、`LINEUP_CLEAR = "lineup.clear"`、`LINEUP_SYNC_TO_SLOT = "lineup.syncToSlot"`；发送点全部在 `SharedMemManager`（`applyAppLineupToGame` / `clearAppLineupFromGame` / `syncLineupToGameSlot`）。**Java 侧没有接收方**——这些是发给注入进游戏进程的 native 库（`libdemo.so` / `libinject.so`）去执行的。

可靠性上，`LineupActiveBus` 每个 push 都带**签名去重**（`lastPushAppLineupSig` 等）和**重试队列**（`pendingAppLineupPayload` / `pendingClearStarTargets` / `pendingGameSlotPayload`），失败时 `scheduleNativeRetry()`，最多 `MAX_NATIVE_RETRY_ATTEMPTS = 120` 次、每次间隔 `NATIVE_RETRY_DELAY_MS = 100` 毫秒（即最长约 12 秒），并严格按生成号 `nativePushGeneration` 保证旧载荷不覆盖新载荷。

#### 3.6.4 `lineup.apply` 的完整载荷结构

由 `LineupActiveBus.buildNativeLineupPayload(Lineup, int index)`（`LineupActiveBus.java:459`）构造：

```json
{
  "title": "<阵容名>",
  "index": 0,
  "preferEquipments": [ <equipOrder 逗号解析出的装备 id> ],
  "heroes": [
    {
      "heroId": 11112,
      "row": 0,
      "col": 3,
      "core": true,
      "equips": [ { "targetID": 11112, "item1": 3, "item2": 7 } ]
    }
  ]
}
\```

细节：

- `heroes` 取自 `payloadUnits(lineup)`：优先 `finalUnits`，为空则按 `lateHeroes → midHeroes → earlyHeroes` 取第一个非空列表，并构造无坐标的 `LineupUnit`（`location=""`）；
- 坐标由 `BoardLoc.parse(location)` 得到，解析失败或 **slot 重复**（`row*7+col` 已出现过）则 `row = col = -1`，表示「只要求上阵不要求站位」；
- 装备用 `EquipRecipeMapper.getRecipe(itemId)` 展开成合成件：命中配方取 `recipe.part1` / `recipe.part2`，否则 `item1 = 原始 id, item2 = 0`。配方表来自 asset `equipment_table.txt`，字段为 `productId` / `part1` / `part2`；
- 当 `index = 0` 时该载荷就是 `lineup.apply` 的主题；`index ≥ 1` 用于 battle panel 的第 2..5 套阵容。

#### 3.6.5 反方向：游戏内阵容回灌 App

native 推送 `updateGameRecommendTeam` → `SharedMemManager` 分发 → `GameLineupBridge.onGameRecommendReceived(JSONObject)`：

- 顶层字段 `stages`（必选，缺省视为「游戏清空了阵容」）、`title`（默认 `"游戏内已应用"`）、`applied`、`snapshotKind`（等于 `"appliedDeck"` 时视为已应用）、`coordinateTransform`（`flipX`/`flipY`/`flipXY`）、`precedenceEquips`；
- `stages` 的 key 是 `"0"` / `"1"` / `"2"`（对应 early/mid/late），每阶段含 `heroes[]`（每项 `heroId` / `row` / `col` / `equips`）与 `coreHeroId`；`GameAppliedLineupFactory.fromTeamJson` 取**英雄数最多的阶段**作为 `finalUnits`，并按 `coordinateTransform` 翻转坐标（`flipY` → `row = 3-row`，`flipX` → `col = 6-col`），`carry = (heroId == coreHeroId)`，location 写成 `"0:row,col"`；
- 生成的 `Lineup`：`id = "game_applied_" + fingerprint`、`author = "游戏内应用"`、`quality = "S"`；
- 另有 `mergeGameDataWithMetadata` 把仓库元数据（id/name/author/quality/feature/shareCode/earlyInfo/dTime）与游戏数据（equipOrder/earlyHeroes/midHeroes/lateHeroes/finalLevel/finalUnits）合并；
- `GameLineupBridge` 的返回值枚举 `PublicationResult { APPLIED, UNCHANGED, REJECTED_PARSE, REJECTED_STALE }` 用于去重与拒绝过期帧；
- **当 `autoApply == true` 时，解析成功后会反过来调 `LineupActiveBus.get().applyByAuto(lineup)`**（`GameLineupBridge.java:326`），即「游戏里已经用的阵容」会被回灌成 App 的当前应用阵容——这形成了一条自我强化的闭环，需要注意会与 3.6.3 的自动推荐互相覆盖。

另一条 push `updateGameRecommendActive`（字段 `active`(0/1) + `heroIds[]`，最多 32 个）走 `GameLineupBridge.onGameRecommendActiveTargets`，由 `GameAppliedLineupFactory.fromActiveHeroIds(int[])` 构造一个「只关心拿哪些英雄、不关心站位」的临时 `Lineup`。

---

### 3.7 棋盘位置与 slot 表示

#### 3.7.1 尺寸

`BoardLoc`（`lineup/BoardLoc.java`）：`ROWS = 4`、`COLS = 7`，`inBounds(row, col)` = `0 <= row < 4 && 0 <= col < 7`。

**slot 索引 = `row * 7 + col`**（0..27）。这个值在 `LineupActiveBus.buildNativeLineupPayload` 用于站位去重、在 `PickBoardModel`/`GameAppliedLineupFactory` 用于定位，是棋盘格子的唯一整数表示。

#### 3.7.2 坐标字符串格式

`BoardLoc.parse(String)` 同时接受两种写法：

| 格式 | 说明 |
|-|-|
| `"0:row,col"` | 前缀 `0:` 表示已是 0-based，直接解析 |
| `"row,col"` | 无前缀时按 1-based 解析（`1..4` / `1..7`），内部各减 1 |

解析成功返回 `int[]{row, col}`（0-based），越界或格式错误返回 `null`。**App 内部统一用 `"0:row,col"` 写出**（`GameAppliedLineupFactory` 的 location 字段），1-based 形式是为兼容数据源里手写的坐标。

#### 3.7.3 `PickBoardModel`

`PickBoardModel` 是「一套阵容怎么摆到棋盘上」的视图模型，不参与评分。

- 枚举 `Source { NONE, GAME, APP }`；`PickBoardSourcePolicy.resolve(pref, hasApp, hasGame)` 决定取哪一路：`PREF_APP = 2` 锁定 App 阵容、`PREF_GAME = 1` 锁定游戏阵容、`PREF_AUTO = 0` 自动（优先 GAME）。
- 字段：`cells`（有坐标的格子，按 row/col 排序）、`unpositioned`（`final_units` 里没有 `loc` 的英雄）、`title`、`source`、`reachedCount`、`visualFingerprint`（用于判断是否需要重绘）。
- `Cell` 字段：`row`、`col`、`rawHeroId`、`baseHeroId`、`name`、`paint`、`cost`、`targetStar`、`targetCopies`、`ownedCopies`、`currentStar`、`carry`、`equipIds`。
- `build(Source, Lineup, StarResolver, Map<Integer,Integer> ownedCopies)`（`PickBoardModel.java:202`）：遍历 `finalUnits`，`BoardLoc.parse` 有效且 slot 未重复的进 `cells`，其余进 `unpositioned`。
- **目标星级的两套解析规则**：
	- `gameStarResolver()` —— 优先 `HeroStarId.starOf(rawHeroId)`（游戏内 id 自带星位），否则查 `GameLineupBridge.targetStarForBase(baseId)`；
	- `appStarResolver(ownedCopies, lineup)` —— `ownedCopies` 有值用 `HeroStarId.targetFor`；否则按阵容分段给默认值：**carry 或属于 `lateHeroes` → 3 星，属于 `midHeroes` → 2 星，其余 → 1 星**。
- `Entry`（`cell` / `count` / `targetCopies`）与 `allEntriesForList()` 按 `baseHeroId` 聚合，用于「同名英雄需要几张」的合成清单。

---

### 3.8 商店预测 / 海克斯预测 / 对手预测：**Java 侧没有算法**

#### 3.8.1 海克斯（Hex / 强化符文）

**Java 侧的本地数据只有两张静态表**：

- `SpecifiedHexCatalog` 读 asset `hex_catalog.json`（海克斯名录）；
- `SpecifiedHexOfferTable`（`SpecifiedHexOfferTable.java`）读 asset `hex_offer_table.json`，schema 为 `"jcc-hex-offer/v2"`，并要求 `"runtimePoolOnly": true`。其 `Row` **只有四个字段**：`id`、`mode`、`quality`（强制 `1..4`）、`stagesMask`（1-3 阶段的位掩码）。`Row.allowsStage(stage)` = `(stagesMask & (1 << (stage-1))) != 0`；查表用 `Arrays.binarySearch` 按 id 二分。

**这张表是「能不能刷出」的布尔表，不是概率表。** 没有任何「等级 1-10 → 各费用出现概率」的数字硬编码在 Java 里。

**运行时数据全部来自 native**，IPC 命令与载荷：

| 方向 | 命令 / push 名 | 用途 | 关键字段 |
|-|-|-|-|
| App → native | `hex.query` | 查询本局各阶段品质等级 + 实时可刷池 | 请求体为 `{}` |
| App → native | `hex.specify` | 指定目标海克斯 | `{targetHexIds, stage, matchGeneration}` |
| App → native | `hex.cancel` | 取消指定 |  |
| native → App | `updateHexPrediction` | 回传预测数据 | `matchGeneration`、`levels[]`、`available`、`livePool[]`、`livePoolWeights[]`、`livePoolTotalWeight`、`drawsPerStage` |
| native → App | `hex.specified.status` | 指定结果状态 | `phase`、`targetHexId`、`code`、`stage`、`sessionGeneration`、`matchGeneration`、`targetRevision` |

`SpecifiedHexPanel`（2268 行，TAG `"HexPredict"`）是**纯 UI**：Grid 选择器 + 已选目标列表，图标从 `file:///android_asset/hex_icons/...` 加载，不可刷出的格子透明度降到 0.35，品质着色由 `HexAugmentMapper`（asset `hex_augment_table.txt`，字段 id/name/tier/description，颜色常量 `COL_SILVER` / `COL_GOLD` / `COL_PRISM` / `COL_UNKNOWN`）提供。

**Java 侧唯一一处真正的概率计算**在 `SpecifiedHexHitRate`，而且它是**建立在 native 给回的权重之上**的：

```java
FALLBACK_DRAWS_PER_STAGE = 65;

weightOf(id, ids[], weights[])      // 线性查找 ids[i] == id，取 max(0, weights[i])
totalWeight(weights[], total)       // total > 0 用 total，否则累加正权重
perRefresh(...) = min(1.0, weightOf / totalWeight)          // 单次刷新命中概率
perRound(p, n)  = 1 - (1 - p)^n                             // n 次抽取至少中一次
roundChance(...) = perRound(perRefresh(...), draws)         // draws 缺省回退 65
roundChanceForAny(...) = perRound(min(1.0, Σ权重 / total), draws)   // 多目标去重后求和
\```

展示文案 `chanceLabel`：`本阶段不会出` / `本阶段可出` / `本阶段几乎不出`（<1%）/ `本阶段稳出`（≥99%）/ `本阶段 X%`。

`HexQueryBroker` 是一个**单飞（single-flight）请求合并器**：`request(callback)` 把回调放入 `waiters`，若已有请求在飞则只排队，否则置 `inFlight = true` 并排一个超时任务；`complete(int[])` 清空 waiters、取消超时、给每个 waiter 一份**克隆的** `int[]`；超时（`SharedMemManager.HEX_QUERY_TIMEOUT_MS = 4000` 毫秒）与 `cancelPending()` 都以 `complete(null)` 收尾。缓存落在 `SharedMemManager.snapshot` 的 `cachedHexLevels` / `cachedHexLivePool` / `cachedHexLivePoolWeights` / `cachedHexLivePoolTotalWeight` / `cachedHexDrawsPerStage`。

#### 3.8.2 商店 / 英雄池

- 原生推送 `updateHeroPool`（`pool[].heroes[]{heroID, cost, currentCount, totalCount}` + `locked[]{heroId, cost, leftCount, totalCount}`）由 `IpcHeroPoolParser` **纯解析**。
- `updateShopSlots`（`slots:[{index, heroId}]`）由 `IpcShopSlotsParser` 解析，`IpcShopSlotState.apply` 用 fingerprint 判断有无变化。**无概率计算**。
- `updateSpecifiedShopStatus` 的字段 `armed`/`ready`/`targets`/`roster`/`unaffordable`/`reachable`/`predictions`/`refreshed`/`landed` **全部由 native 算好**，Java 侧 `SpecifiedShopControlBinder.applyRuntime` 只把它们翻译成中文文案（如「已预测 ×N」「已出手 N 次 · 拿到目标 N 次」）。
- Java 侧仅有的「数学」是 `HeroPoolCountTier.of(count, total)`：`count <= 0` → `SOLD_OUT`；`count <= total * 0.3` → `SCARCE`；否则 `PLENTIFUL`。这是**余量分级，不是概率**。`HeroPoolMerge` 只做按 `heroId` 去重合并，`HeroPoolKnownCensus` 只做计数。
- 佐证：全仓 grep `ShopPredict` 只命中 `ContinuousLogCapture` 里的一份**日志抓取关键词列表**，Java 侧不存在这个类。

#### 3.8.3 对手预测

`OpponentPredictionControlBinder` 是**纯 UI 绑定**——5 个 Switch、若干 SeekBar（对手文本框位置/大小、攻击图标偏移/大小、native 攻击图标）、预设按钮（TL/LM/TR/RM/拖拽模式）以及位置百分比文案格式化，**没有任何「血量/等级 → 阵容」的推断代码**。

`OpponentPredictSourcePolicy` 只有三个来源常量：`SOURCE_OFF = 0` / `SOURCE_IMAGE = 1` / `SOURCE_NATIVE = 2`，`imageOverlayEnabled(...)` 决定用图像覆盖层还是 native 覆盖层。

真正的对手数据由 native 的 `updateMatchup` 推送：`IpcMatchupEnvelopeParser` 解析 `myId` / `opponentId` / `matchId` / `source` / `pairs`；`IpcMatchupPairsParser` 解析 `pairs: [{p1, p2, ghost}]` 到 `MatchupPairData{player1Id, player2Id, ghostSourcePlayer}`；`MatchupSnapshot.shouldAccept` 做优先级仲裁。**配对是 native 算好的。**

#### 3.8.4 汇总：本地 vs native

| 归属 | 内容 |
|-|-|
| **Java 本地算法** | `TraitCalculator.compute/getActivatedTier`（计数 + 阈值档位）、`LineupRecommender.score`（唯一带权重的评分公式）、`SpecifiedHexHitRate.perRefresh/perRound/roundChanceForAny`（加权比例 + `1-(1-p)^n`）、`SpecifiedHexOfferTable.get/allowsStage`（布尔查表）、`HeroPoolCountTier.of`（0.3 阈值分级）、`HeroPoolMerge`/`HeroPoolKnownCensus`（去重计数） |
| **native 计算、IPC 回传** | 商店刷新预测（`updateShopSlots` / `updateSpecifiedShopStatus` 的 `predictions`/`reachable` 等）、海克斯可刷池与权重（`updateHexPrediction` 的 `levels` / `livePoolWeights` / `drawsPerStage`）、英雄池余量（`updateHeroPool`）、对手配对（`updateMatchup` 的 `pairs`） |

一句话：**Java 只负责「算羁绊、算阵容匹配度、把 native 给的概率数字换算成百分比文案」，所有与游戏内随机性相关的推断都在 native。**

---

### 3.9 其它相关资产文件

| asset 文件 | 加载类 | 内容 |
|-|-|-|
| `lineup/<setId>/lineup_meta.json` | `LineupRepo.loadLineups` | 阵容库主文件 |
| `lineup/<setId>/chess_meta.json` | `LineupRepo.loadHeroes` | 英雄 cost / species / class / paint |
| `lineup/<setId>/race.json`、`job.json` | `LineupRepo.loadTraits` | 羁绊定义与激活阈值 `numList` |
| `hex_catalog.json` | `SpecifiedHexCatalog` | 海克斯名录 |
| `hex_offer_table.json` | `SpecifiedHexOfferTable` | 海克斯可刷性布尔表（mode / quality / stagesMask） |
| `hex_augment_table.txt` | `HexAugmentMapper` | 海克斯 id → 名称 / tier / 描述 |
| `equipment_table.txt` | `EquipRecipeMapper` | 装备合成配方 `productId` → `part1` + `part2` |

本地持久化（SharedPreferences）：`lineup_auto_apply`（自动应用开关）、`lineup_cdn`（更新 URL 覆盖）、`lineup_favorites`（收藏阵容 id，逗号分隔字符串，`LineupFavorites`）。

---

## 四、授权信任链与诊断上报

### 4.1 一句话结论

本样本的授权体系是**两层、且信任根完全下沉到 `libdemo.so`** 的结构：Java 层只做"搬运工 + 形状校验"，所有密钥、签名、验签、环境判定都在 native 里；Java 侧唯一真正持钥的三处（诊断上报 HMAC、诊断授权令验签、版本策略验签）用的都是**服务端下发或硬编码的公钥**，没有对称密钥。

两层授权：

| 层 | 触发 | 载体 | 谁校验 | 结果 |
|-|-|-|-|-|
| **WIG 登录层** | 用户输入授权码（卡密） | `POST /v2/api/wig/login/<appid>/<...>` | 服务端 + native 验签 | 返回 `expiryEpochSeconds`，写入 `wigExpiryEpochSeconds` |
| **Trust 租约层** | WIG 登录成功后自动 | `POST /v2/challenge` → `POST /v2/lease` | native 验签 + 服务端 | 返回 320 字节 signed lease，写入 `signedLease` |

两层都通过后 `nativeIsAuthorized()` 才为真，功能才开放。此外还有一条**下发通道**：Java 拿到 lease 后通过本地 `LocalSocketIPC`（socket `xf_game_control_v2`）把 lease / WIG session / feature catalog **转发给注入在游戏进程里的 native 运行时**，游戏进程侧再自行校验一次。

---

### 4.2 授权流程完整时序

#### 4.2.1 文字时序图

```python
[App 进程 com.android.support]                     [服务器 jcc.zhuzhufaka.cn]        [游戏进程内的 libdemo.so]

(1) 预热阶段
 NativeTrustBridge.warmPreLogin()
   └─ nativeWarmPreLogin()            ─────────►  (无网络)  native 侧预热：内部状态/密钥表/环境自检
      (线程 jcc-prelogin-start / jcc-prelogin-rewarm)
   └─ prefetchFeatureCatalogAsync()
        └─ nativeLoadFeatureCatalog() + nativeExportFeatureCatalog()  → cachedCatalogWords

(2) WIG 登录阶段（授权码验证）—— WigVerify.login(card, imei)
 NativeTrustBridge.prepareLicense(card)
   └─ nativePrepareLicense(card)      ─────────►  native 本地校验授权码格式 + 生成内部登录态，返回 boolean
 NativeTrustBridge.buildGatewayLoginRequest(card, imei)
   └─ nativeBuildWigLoginRequest()    ─────────►  返回 byte[]：首行是完整 URL，其后是 form body
 TrustTransport.postWig(byte[])
   ├─ Java 强校验：scheme=https、host=jcc.zhuzhufaka.cn、port=-1、路径前缀 /v2/api/wig/login/<数字>/<安全串>、
   │   body 必须严格匹配 "card=<enc>&imei=<enc>"（isFixedWigPath / isFixedWigForm）
   └─ POST ─────────────────────────────────────► 服务端校验授权码、设备绑定、封禁状态
        ◄──────────────────────────────────────  响应体（≤64KiB）
 nativeAcceptWigLoginResponse(resp, deviceId) ──► native 验证响应并落库，返回 long expiryEpochSeconds
   └─ 判定：expiry > 0 且 expiry > 当前服务器校正时间  → 否则按 failureCode() 失败
   └─ 写 lastWigLoginCode / lastWigLoginError / wigExpiryEpochSeconds

(3) Trust 租约阶段 —— NativeTrustBridge.acquirePrepared() → exchange(generation, false)
 (3a) nativeLicenseHeader()            ─────────►  生成长期许可证凭据字节串（见 4.4）
 (3b) nativeBeginChallenge()           ─────────►  生成 challenge 请求体 byte[]
 (3c) TrustTransport.postChallenge()  ─────────►  POST /v2/challenge   （注意：此请求【不】带 license header）
        ◄──────────────────────────────────────  challenge 响应（服务端签名）
 (3d) nativeAcceptChallenge(resp)      ─────────►  native 验签 + 校验，返回 int TrustError code
 (3e) nativeBuildLeaseRequest(challengeResp, deviceId)  ──►  生成 lease 请求体（含设备绑定）
 (3f) TrustTransport.postLease(body, nativeLicenseHeader)
        └─ 请求头 X-JCC-License: <nativeLicenseHeader>        POST /v2/lease
        ◄──────────────────────────────────────  320 字节 signed lease
 (3g) nativeAcceptLease(resp)          ─────────►  native 验签 + 校验租约结构/有效期/绑定，返回 int TrustError
 (3h) 成功 → this.signedLease = resp.clone()
             lastError = OK, nativeVerdictReacquireCount = 0
             startLeaseRelayLocked / startCatalogRelayLocked
             executor.schedule(exchange(j, true), 60s)   ← 续租（/v2/renew）
             schedulePresenceLocked(j)                    ← 心跳（/v2/presence）

(4) 授权判定与下发
 NativeTrustBridge.isAuthorized()
   ├─ nativeIsAuthorized()             ─────────►  native 最终裁决
   └─ hasCompleteAuthorization(): lastError==OK && native==true
                                  && signedLease != null && wigExpiry > now
      或 hasLiveWigSession(): 仅 WIG session 有效
 relay（LocalSocketIPC，socket xf_game_control_v2）：
   "acceptTrustLease"      ← {lease:[int...], device, server_time_offset, trust_generation}
   "activateWigSession"    ← {expiry, token, payloadKind, device, binding(b64url), server_time_offset, trust_generation}
   "acceptFeatureCatalog"  ← {words(b64url), trust_generation}
   "clearTrustLease"       ← {trust_generation}   （登出/撤销时 sendCommand，无回调）
 回包校验：accepted==true 且 trust_generation == 当前 generation，否则 2s 后重试，最多 20 次
\```

#### 4.2.2 每一步"谁校验谁"

| 步骤 | 校验方 | 校验内容 | 失败表现 |
|-|-|-|-|
| `nativePrepareLicense` | **native** | 授权码格式、内部状态 | 返回 false → `acquire()` 直接 `onFailed(CANCELED)` |
| `TrustTransport.postWig` | **Java** | URL/表单的**形状**白名单（防 patch 改地址、防注入额外字段） | 抛 `Failure("WIG_PARSE")`，**不发包** |
| `nativeAcceptWigLoginResponse` | **native** | 服务端响应真实性、有效期 | 返回 0 → 映射 `INTEGRITY` 或 `failureCode()` |
| `nativeAcceptChallenge` | **native** | 服务端 challenge 签名 | 返回 `BAD_SIGNATURE(2)` 等 → `fail()` |
| `nativeAcceptLease` | **native** | 服务端 lease 签名、租约内部结构、时钟 | 返回 `BAD_SIGNATURE/MALFORMED_LEASE/CLOCK_OVERFLOW/LEASE_EXPIRED/REVOKED/VM_REJECTED/VM_PROGRAM_INVALID/MANIFEST_INVALID` |
| `TrustControlResponse.parse` | **native**（经 `nativeVerifyControlPolicy`） | `/v2/client-policy`、`/v2/presence` 响应的 `signature` 字段 | 抛 IOException `"trust policy signature invalid"` → 走 transport 重试 |
| 注入侧 `libdemo.so` | **native（游戏进程内）** | 自己再验一遍 lease / WIG session / catalog | 回包 `accepted=false` 或 `trust_generation` 不匹配 → Java 侧重试 20 次 |

关键点：**Java 层从不验证服务端响应的密码学签名**。`nativeAcceptChallenge` / `nativeAcceptLease` / `nativeVerifyControlPolicy` / `nativeIsAuthorized` 这四个方法是 Java 与信任根之间唯一的"判决接口"，全部返回 `int`/`boolean`，具体算法实现在 `libdemo.so` 内，Java 侧不可见。

`TrustError` 枚举（`trust/TrustError.java`）把 native 判决码翻译成语义：

```python
OK(0)  WRONG_LENGTH(1)  BAD_SIGNATURE(2)  MALFORMED_LEASE(3)  CLOCK_OVERFLOW(4)
VM_REJECTED(5)  VM_PROGRAM_INVALID(6)  MANIFEST_INVALID(7)  REVOKED(8)  LEASE_EXPIRED(9)
TRANSPORT(-1)  NATIVE_UNAVAILABLE(-2)  CANCELED(-3)  BUILD_NOT_REGISTERED(-4)  UNKNOWN(MIN)
\```

其中 `VM_REJECTED` / `VM_PROGRAM_INVALID` / `MANIFEST_INVALID` 这组命名强烈暗示 native 内部有一个**解释器/虚拟机式的租约校验程序**（租约里可能带一段被签名保护的"校验程序"，由 native VM 执行）。**实现在 `libdemo.so` 内，Java 侧不可见。**

`isDefinitiveRejection()` 只把 `REVOKED` 和 `BUILD_NOT_REGISTERED` 当作不可重试的终局拒绝，其余失败一律走重试（初始 acquire 指数退避；续租固定 10s）。

---

### 4.3 密码学归属：native 里有什么、Java 里有什么

#### 4.3.1 全部在 libdemo.so 内（Java 侧不可见）

`trust/NativeTrustBridge.java:141-185` 声明 20 个 native 方法，其中与信任根直接相关的：

| native 方法 | Java 看到的样子 | 推断职责 |
|-|-|-|
| `nativeWarmPreLogin()` | `boolean` | 预热：装载密钥表 / 内部状态 / 环境自检 |
| `nativePrepareLicense(String)` | `boolean` | 授权码本地校验与登录态准备 |
| `nativeBuildWigLoginRequest(card, imei)` | `byte[]` | 构造 WIG 登录请求（含 URL 首行） |
| `nativeAcceptWigLoginResponse(resp, device)` | `long` expiry | 验证登录响应，返回授权到期时间 |
| `nativeLicenseHeader()` | `byte[]` | 生成长期许可证凭据（→ `X-JCC-License`） |
| `nativeBeginChallenge()` | `byte[]` | 生成 challenge 请求体 |
| `nativeAcceptChallenge(resp)` | `int` TrustError | **验 challenge 响应签名** |
| `nativeBuildLeaseRequest(challengeResp, device)` | `byte[]` | 构造租约请求（含设备绑定） |
| `nativeAcceptLease(resp)` | `int` TrustError | **验租约签名 + 租约结构 + 时钟 + 撤销状态** |
| `nativeIsAuthorized()` | `boolean` | 最终授权裁决 |
| `nativeGetTrustError()` | `int` | 读取当前信任错误码 |
| `nativeVerifyControlPolicy(payload, sigHex)` | `boolean` | **验证服务端控制策略签名**（`/v2/client-policy`、`/v2/presence`） |
| `nativeGetWigLoginCode()` / `nativeGetWigLoginError()` | `String` | 读取 native 侧失败码（`ADB_DEBUG`/`INTEGRITY`/`ENVIRONMENT`/`INJECT_PENDING`/`LOCAL_CHECK_*`/`DEVICE_BINDING_MISMATCH`） |
| `nativeExportWigRelay()` / `nativeExportFeatureCatalog()` / `nativeLoadFeatureCatalog()` | `byte[]`/`boolean` | 导出可下发给注入侧的 WIG session 快照 / 功能目录 |
| `nativeSetServerTimeOffset(long)` | `void` | 把服务器时间偏移喂给 native 时钟 |
| `nativeClearTrust()` | `void` | 清空 native 信任状态 |

**结论：信任根密钥（用于验服务端签名的公钥，或对称密钥）在 `libdemo.so` 内，Java 侧完全不可见。** Java 侧硬编码的常量里没有任何可以替代它。

#### 4.3.2 Java 侧真正持钥的四+一处

| 类 | 算法 | 密钥来源 | 位置 |
|-|-|-|-|
| `diagnostics/DiagnosticRequestSigner` | **HMAC-SHA256**，上下文串 `"JCC-DIAG-HMAC-V2"` | 服务端注册时下发的 32 字节 `installation_secret`，**非硬编码**；用后 `Arrays.fill(...,0)` 销毁 | `DiagnosticRequestSigner.java:18,23,129-140,200-208` |
| `diagnostics/DiagnosticGrantVerifier` | **SHA256withECDSA / P-256**，签名对象 `kid + "." + payload` | **硬编码公钥**（见下） | `DiagnosticGrantVerifier.java:108-116` |
| `JccReleaseConfig` + `JccVersionPolicy` | **ES256-P1363** 验签 `/v2/api/version` 响应 | **硬编码公钥**（见下） | `JccReleaseConfig.java:5-8` |
| `JccDeviceIdentity` | **SHA256withECDSA / secp256r1**，对服务端 challenge 的 `message` 签名 | **AndroidKeyStore 生成，私钥不出 TEE/Keystore**，别名 `jcc_gateway_device_p256_v1` | `JccDeviceIdentity.java:14,34-38` |
| `diagnostics/SupportIdentity.AndroidSecretProtector` | **AES/GCM/NoPadding**，AAD `"JCC-DIAG-IDENTITY-V1"` | AndroidKeyStore，别名 `jcc_diagnostic_identity_aes_v1` | `SupportIdentity.java:19-25,204-227` |

#### 4.3.3 硬编码常量与密钥清单（逐字）

**授权令（Diagnostic Grant）验签公钥** —— `src/com/android/support/BuildConfig.java:13-14`：

```java
JCC_DIAGNOSTIC_GRANT_KEY_ID = "jcc-v480-production-diag-b8acc9063be36518"
JCC_DIAGNOSTIC_GRANT_PUBLIC_KEY_SPKI_BASE64URL =
  "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEeUBkawzbBfPg03FkK52CJKrnuFz8JjHZAHqnSmD6vkyIItB3LAUfdJu0cN67DXDe6SJcCrFAnziDLXvu97c3og"
\```

**版本策略验签公钥** —— `src/com/android/support/JccReleaseConfig.java:5-8`：

```java
FORMAL_VERSION_POLICY_KEY_ID = "jcchd-gateway-cb8ee942cf24c927"
FORMAL_VERSION_POLICY_PUBLIC_KEY_SPKI_BASE64URL =
  "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE637s12oBFraL45Htz1ALaEEboI4JA840_pPb0jZc4dutb21Ng7cdlUXIsW3VCPd3B1OLMOH_RiQsMsYlQijE6w"
\```

**服务端源** —— `src/com/android/support/JccNetworkPolicy.java:12`：`ORIGIN = "https://jcc.zhuzhufaka.cn"`；`JccGatewayClient.java:38`：`ORIGIN_FALLBACK_ADDRESS = "43.226.61.21"`（DNS 兜底直连 IP）。

**官方频道常量** —— `src/com/android/support/WigVerify.java:28-39`：

```java
APPROVED_CHANNEL_CHECKSUM = -202905437;
APPROVED_GROUP_CHECKSUM   = -2012013098;
APPROVED_SUPPORT_CHECKSUM = -162038091;
APPROVED_TEXT_CHECKSUM    = 1412097564;
OFFICIAL_CHANNEL_URL_DEFAULT = "https://t.me/XFchart";
OFFICIAL_GROUP_URL_DEFAULT   = "https://t.me/XFchart1";
OFFICIAL_HANDLE_DEFAULT      = "@XFchart";
OFFICIAL_PREFIX_DEFAULT      = "XF官方频道 ";   // 原文 "XF官方频道 "，末尾一个空格
OFFICIAL_SUPPORT_URL_DEFAULT = "https://t.me/XFzong";
\```

这些都是 **Telegram** 链接，与"官方 QQ 群"无关。

**Java 侧没有任何对称密钥**：全部 `grep` 下来，`SecretKeySpec`、`HmacSHA256` 的密钥都是运行时构造（服务端下发或 Keystore 生成），没有硬编码的 AES key、HMAC key、RSA 私钥或 ECDSA 私钥。这是有意设计——Java 层只放公钥。

**唯一的完整性校验算法在 Java**：`OfficialBrandContract.fnv1aUtf8`（`src/com/android/support/OfficialBrandContract.java:21-30`），FNV-1a 32 位、UTF-8 字节、offset basis `-2128831035`、prime `16777619`。

---

### 4.4 `nativeLicenseHeader` 生成的请求头，以及 `TrustTransport` 怎么用它

`nativeLicenseHeader()`（`trust/NativeTrustBridge.java:172`）返回 `byte[]`，在 `exchange()` 的第一个 native 步骤（`lambda$exchange$0`，第 1472-1475 行）与 `nativeBeginChallenge()` 一起取出：

```java
atomicReference.set(nativeLicenseHeader());   // → bArr  (license header)
atomicReference2.set(nativeBeginChallenge()); // → bArr2 (challenge 请求体)
\```

**它被放到 HTTP 头 `X-JCC-License` 里**（`trust/TrustTransport.java:349`、`:385`）：

```java
method.header("X-JCC-License", new String(bArr2, StandardCharsets.US_ASCII));
\```

**精确的使用位置**（重要，容易搞错）：

```java
final byte[] postChallenge = this.transport.postChallenge(bArr2);   // 只带 challenge，license header = null
...
postLease = trustTransport.postLease(bArr3, bArr);   // body=lease请求, licenseHeader=bArr  ← 带
postRenew = trustTransport.postRenew(bArr3, bArr);   // 续租同样带
\```

即：`/v2/challenge` **不带** `X-JCC-License`；`/v2/lease` 与 `/v2/renew` **带**。设计意图可读为：先拿 challenge 证明请求是新鲜的，再用 license header 证明请求来自合法客户端，两者一起换取租约。

**Java 对 header 内容的校验（`validateLicenseHeader`，`TrustTransport.java:423-436`）**：只做形状约束，不解码、不验签。

- 长度必须 `1..342` 字节
- 每个字节必须落在 `[A-Za-z0-9_-]`，即 **Base64URL 字母表（无填充）**

这正是一个"native 生成的、不透明的不定长凭据"的特征。**header 的内部结构、生成算法、是否签名、绑定什么，全部实现在 `libdemo.so` 内，Java 侧不可见。**

同一个 `TrustTransport` 还对 `postWig` 做了更严格的白名单（`isFixedWigPath` / `isFixedWigForm` / `isEncodedComponent`，`TrustTransport.java:242-317`）：URL 必须是 `https://jcc.zhuzhufaka.cn/v2/api/wig/login/<≤20位数字>/<安全串>`，body 必须严格是 `card=<enc>&imei=<enc>` 且只有这两个字段。这是**防 Java 层被 patch 后改地址或加字段**。

---

### 4.5 `WigVerify` 的 native 方法：防伪 / 防篡改，还是别的？

#### 4.5.1 澄清数量

**`WigVerify.java` 里实际是 12 个 native 方法，不是 13 个**（第 80-102 行，穷尽 `grep`）：

`nativeGetChannelUrl`、`nativeGetOfficialChannelUrl`、`nativeGetOfficialChannelChecksum`、`nativeGetOfficialGroupUrl`、`nativeGetOfficialGroupChecksum`、`nativeGetOfficialHandle`、`nativeGetOfficialPrefix`、`nativeGetOfficialSupportUrl`、`nativeGetOfficialSupportChecksum`、`nativeGetOfficialTextChecksum`、`nativeGetVersionCode`、`nativeGetVersionName`。

（信任侧的 20 个 native 方法在 `NativeTrustBridge`，诊断侧的 8 个在 `DiagnosticSharedMemoryBridge`。）

#### 4.5.2 作用：官方品牌信息的防伪，不是完整性自校验

这 12 个方法的共同模式是「**native 提供值 + native 提供校验和，Java 侧用硬编码的批准值双向核对**」：

```java
// OfficialBrandContract.java:32-34
static String validatedValue(String str, int i, String str2, int i2) {
    return (str != null && i == i2 && fnv1aUtf8(str) == i2) ? str : str2;
}
\```

即三个条件**全部**成立才采用 native 的值：

1. native 返回的校验和 `i` == Java 硬编码的批准校验和 `i2`
2. `FNV-1a(native 返回的字符串)` == 同一个批准值
3. 字符串非 null

**防的是什么**：防止有人 patch `libdemo.so` 把官方频道/客服链接替换成仿冒的 Telegram 群或充值钓鱼页。因为校验和是硬编码在 Java dex 里的一个魔数，攻击者改 native 字符串就必须同时改 dex 里的校验和。

**校验失败会怎样**：**静默回退到明文默认常量**（`WigVerify.java:114-160`，`try { ... } catch (Throwable unused) {}` 后 `return OFFICIAL_*_DEFAULT`）。不抛异常、不崩溃、不禁用功能。

因此必须诚实指出：**这是一层弱防伪**。默认常量本身就是明文正确的 URL，所以攻击者可以直接 patch Java 层或直接读默认常量绕过，代价很低。它的真实作用是防止"改 native 而不改 dex"这类粗糙篡改，而不是保护授权。

`nativeGetVersionName` / `nativeGetVersionCode` 在 native 不可用时回退到 `PackageManager`（`WigVerify.java:1958`）或硬编码 `"1.0"`（`:1960`）/ `1`（`:1966,1971`）。

`purchaseUrl()`（`WigVerify.java:162-175`）对 `nativeGetChannelUrl()` **只检查 `startsWith("https://")`，不做校验和**——这是 12 个里唯一没有校验和保护的一个。

#### 4.5.3 `VerifyOverlayAuth` 在做什么

**它不是权限校验，也不做任何密码学操作。** 读完全文（565 行）可以确认它是一个**登录 UI 状态机 + 重试策略**：

- `bindLogin`（:73-90）/ `lambda$bindLogin$0`（:92-145）：读输入框 → 启动 60s 超时 → 调 `host.wigVerify().login(card, callback)`
- 成功 → `host.markVerifiedAndEnter()`（:225），文案 `"✓ 验证成功 "`
- 失败 → 用 `GatewayFailurePolicy.allowsSilentRetry` 判断能否静默重试（最多 2 次），否则 `showActionableFailure`（:403-417）
- `WIG_AUTHORIZATION_EXPIRED` / `WIG_AUTHORIZATION_DENIED` 时清空已保存授权码并重新聚焦输入框（:312-318）
- 后台自动重试 `scheduleBackgroundRetry`（:335-361）：最多 20 次、间隔 15s（`BACKGROUND_RETRY_DELAY_MS = 15000`）
- `startVersionCheck`（:430-438）→ `host.wigVerify().checkVersionAndNotice(...)`；强制更新时 `cancelPendingLogin()` + `showForceUpdate(...)`（:514-516），仅提示更新时仍可继续（:517-520）；**版本检查失败是软失败**（:551-562，提示"版本检查未完成，不影响验证"）

`TAG = "FloatingWindowService"`（:27）——它是 `FloatingWindowService` 的内部逻辑类，不是独立组件。

---

### 4.6 诊断上报体系

#### 4.6.1 上报什么

**注册阶段**（`diagnostics/DiagnosticControlClient.java:178-187`，`POST /diag/v1/installations/register`）：`schema`、`lease`（320 字节信任租约的 Base64URL）、`version_name`。
服务端返回并落盘为"身份"（`Registration`，`:49-79`）：`support_subject_id`、`installation_id`、`support_code`、`installation_secret`（32 字节，后续所有请求的 HMAC 密钥）、`build_id_hash`、`server_time`。

**会话期**（`DiagnosticEventStore.eventLine`，`DiagnosticEventStore.java:639-644`）：每事件一行 JSONL，**14 个全数字字段，没有任何字符串**：

```python
{"seq":..,"mono_ns":..,"op_id":..,"match_epoch":..,"thread_id":..,"feature_id":..,
 "step_id":..,"phase":..,"result":..,"reason":..,"arg0":..,"arg1":..,"duration_us":..,"flags":..}
\```

字段取值全部来自 `TraceCatalog.java` 的枚举表：`feature_id`（`TRUST_RUNTIME_LIFECYCLE=100`、`IPC_CONFIG_SYNC=110`、`AUTO_PICK=200`、`AUTO_REFRESH_SHOP_LOCK=210`、`SELL_ALL_IN=220`、`SPECIFIED_HEX=230`、`OPPONENT_PREDICTION=240`、`GAME_RECOMMENDATION=250`、`BOARD_HUD=300`、`RANK_HUD=310`、`SHOP_HUD=320`），以及 step / phase / result / reason 码表（`reason` 含 `HOOK_NOT_INSTALLED=3`、`HOOK_STALE=4`、`OFFSET_INVALID=5`、`MEMORY_READ_FAILED=6`、`GRANT_EXPIRED=20`、`TRACE_QUOTA_EXHAUSTED=21` 等）。

**事故（incident）**（`DiagnosticIncidentSampler.java:86-96`，`POST /diag/v1/sessions/{id}/incidents`）：`incident_id`、`match_epoch`、`incident_type`、`feature_id`、`step_id`、`op_id`、`result`、`reason`、`confidence`、`evidence`。类型有 `FEATURE_NO_EFFECT`、`CRASH`（evidence 含 `signal_number`、`module_id`、**模块相对 RVA**）、`FREEZE`（游戏帧心跳停滞 ≥10s）、`FEATURE_DEGRADED`、`FEATURE_RECOVERED`。`incident_id = "incident_" + Base64URL(SHA-256(sessionId ‖ 0x00 ‖ dedupKey)[:16])`（`:251-261`）。

**支持码** `SupportCode.generate`（`SupportCode.java:15-25`）：`"JCC"` + 16 位 `"23456789ABCDEFGHJKMNPQRSTUVWXYZ"` + 1 位校验（`i = (i*17+idx) % 32`，初值 19），格式 `JCC-XXXX-XXXX-XXXX-XXXX-C`。

**不上报的内容**（值得强调）：没有原始调用栈、没有函数名、没有符号、没有绝对地址、没有包名、没有设备标识明文。设备身份只在 HTTP 头里。这是一个刻意设计的**低信息量、高可统计性**的数字遥测。

#### 4.6.2 上报到哪里

单一固定源：`https://jcc.zhuzhufaka.cn`（`JccNetworkPolicy.java:12`），路径前缀 `/diag/v1/`。

| 方法 | 路径 | 位置 |
|-|-|-|
| POST | `/diag/v1/installations/register` | `DiagnosticControlClient.java:186` |
| GET | `/diag/v1/control` | `:190` |
| POST | `/diag/v1/sessions` | `:199` |
| POST | `/diag/v1/sessions/{id}/incidents` | `:203` |
| PUT | `/diag/v1/sessions/{id}/chunks/{seq}` | `:217` |
| POST | `/diag/v1/sessions/{id}/complete` | `:210` |

传输用 OkHttp，connect 8s / read 20s / write 20s / call 30s，**禁用重定向**（`followRedirects(false)`）。`JccNetworkPolicy.requireFixedDiagnosticUrl`（`:106-117`）强制 `https` + host 必须等于 `jcc.zhuzhufaka.cn` + 端口 -1/443 + 无 userinfo/query/fragment。

另有**本地通道**（不是上传通道）：`FloatingWindowService.java:4787-4798` 通过 `LocalSocketIPC.sendDiagnosticTraceAttach(pfd, json, ...)`（请求名 `"diagnostics.trace.attach"`）把 **262144 字节共享内存页的 fd** 传给注入到游戏进程的 native，native 侧往这页里写 trace。attach 回包必须是 `{schema:1, generation:<匹配>, mappedSize:262144}`。

#### 4.6.3 有没有签名：有，HMAC-SHA256

`diagnostics/DiagnosticRequestSigner.java`：

- 算法 **HmacSHA256**（`:200-208`），上下文串 `"JCC-DIAG-HMAC-V2"`（`:18`）
- 密钥 32 字节（`SECRET_BYTES=32`，`:23`），来自**服务端注册时下发的 `installation_secret`**，不是硬编码、不是来自 native；`signer()` 每次从 `SupportIdentity` 取副本，用完 `Arrays.fill(secret, 0)` 销毁（`DiagnosticControlClient.java:253-262`、`DiagnosticRequestSigner.java:142-144`）
- 规范串（`:129-140`）：

```python
"JCC-DIAG-HMAC-V2\n" + METHOD + '\n' + PATH + '\n' + timestamp + '\n' + nonce
  + '\n' + hex(sha256(body)) + '\n' + hex(sha256(chunkMetadata.canonicalBytes))
\```

- nonce：16 字节随机，Base64URL 无填充（`:22,107-109`）
- 输出请求头（`SignedHeaders.asMap()`，`:85-94`）：`X-Diag-Installation`、`X-Diag-Timestamp`、`X-Diag-Nonce`、`X-Diag-Body-SHA256`、`X-Diag-Signature`
- 分块上传附加头（`ChunkMetadata.headers()`，`:54-65`）：`Content-Type: application/gzip`、`X-Diag-Chunk-SHA256`、`X-Diag-Previous-SHA256`、`X-Diag-First-Event-Seq`、`X-Diag-Last-Event-Seq`、`X-Diag-Compressed-Bytes`、`X-Diag-Raw-Bytes`、`X-Diag-Event-Count`
- 路径约束（`requirePath`，`:164-169`）：必须以 `/diag/v1/` 开头，禁止 `..`、`%`、`?`、`#`

**载荷本身不加密**：事件块只做 **gzip 压缩**（`DiagnosticEventStore.sealActive`，`GZIPOutputStream`，`:237`）+ 链式 SHA-256（`previousHash`/`sha256`，`:256-257,268-270`）。incident 是明文 JSON。

#### 4.6.4 采集授权令（Grant）：ECDSA P-256

采集不是无条件的——它需要服务端下发一张**签名的授权令**：

1. 客户端轮询 `GET /diag/v1/control`（`DiagnosticCoordinator.pollControl`，`:455-470`），服务端返回 `Control`：`status(NONE/GRANT/REVOKED)`、`revision`、`grant_id`、`grant_envelope`（≤32KiB）
2. `grant_envelope` 交给 `DiagnosticGrantVerifier.verify`（`DiagnosticCoordinator.applyControl`，`:493-506`）
3. `DiagnosticGrantStateMachine.install`（`:32-48`）：`OFF → ARMED`（STANDARD），或 `OFF → WAITING_LOCAL_CONFIRMATION →(用户确认) ARMED`（DEEP 深度采集，`DiagnosticGrant.Mode`，`:40-43`）
4. `ARMED` + IPC 已连 + 对局进行中 → 建会话、attach 共享内存、开始采集（`maybeStartMatch`，`:523-595`）
5. 配额：`max_matches(1..100)`、`max_bytes(1..1GiB)`，`consumeBytes` 消耗完 → `QUOTA_EXHAUSTED`

验签算法（`DiagnosticGrantVerifier.java:108-116`）：**`SHA256withECDSA`，P-256（secp256r1）**，签名对象 `kid + "." + payload`（US-ASCII），强制 `ECPublicKey` 且 `getField().getFieldSize() == 256`；信封 JSON `{kid, payload, signature}`，signature 为 DER ECDSA（64..80 字节）。密钥解析见 `DiagnosticGrantKeyResolver.fromBuildConfig()`（`:21-32`），只接受 kid == `JCC_DIAGNOSTIC_GRANT_KEY_ID`。

校验项（`DiagnosticGrant.parse`，`:64-100`）：`expires_at`、`not_before`、`revision`（防回放）、`allowed_build_id_hashes`、`min/max_version_name`、`installation_scope`、`feature_mask`。错误码含 `REVISION_REPLAY`、`QUOTA_EXCEEDED`、`UNSUPPORTED_FEATURE` 等（`Code`，`:22-39`）。

持久化在 `noBackupFilesDir/diagnostics/control/`：`grant-envelope.json` + `grant-state.json`（`DiagnosticGrantRepository.java:16-23`）。

#### 4.6.5 `DiagnosticSharedMemoryBridge` 从 native 读什么

8 个 native 方法（`DiagnosticSharedMemoryBridge.java:27-41`）：`nativeCloseReader`、`nativeCreateReader`、`nativeDrain`、`nativeDuplicateReaderFd`、`nativeReadHeader`、`nativeReadThreadStacks`、`nativeReadFeatureHealth`、`nativeReadCrashSlot`。**这些实现在 `libdemo.so` / `libdemo_compat.so` 内，Java 不可见；Java 侧只负责按固定字段数把返回的 `long[]` 切分。**

布局常量（`:17-23`）：`PAGE_BYTES = 262144`、`FIELDS_PER_EVENT = 14`、`FIELDS_PER_FRAME = 5`、`FIELDS_PER_HEALTH = 10`、`FIELDS_PER_THREAD = 43`、`MAX_STACK_DEPTH = 8`、`MAX_THREAD_STACKS = 16`。

| 槽位 | 字段（Java 侧切分） |
|-|-|
| Header（9 long） | `generation, mode, writeTicket, droppedEvents, gameFrameHeartbeatNs, nativeWorkerHeartbeatNs, matchEpoch, flags, attached` |
| Event（14 long） | `seq, monoNs, opId, matchEpoch, threadId, featureId, stepId, phase, result, reason, arg0, arg1, durationUs, flags` |
| Crash（10 long） | `sequence, monoNs, opId, threadId, moduleRelativeRva, signalNumber, moduleId, featureId, stepId, flags`；仅当 `sequence` 为偶数才有效（槽位轮转去重，`:342`） |
| 线程栈（每线程 43 long） | `[threadId, depth, flags, 8×5 帧]`，帧 = `opId, enterMonoNs, featureId, stepId, flags` |
| FeatureHealth（每功能 10 long） | `featureId, lastSuccessMonoNs, lastFailureMonoNs, lastInputRevision, consecutiveFailures, lastReason, enabledConfig, capabilityState, hookState, recoveryCount` |

用途：`create(generation)`（`:197-206`，generation 是 63 位随机数，`DiagnosticCoordinator.positiveRandomLong`，`:974-980`）→ `duplicateForSend()` 复制 fd → `LocalSocketIPC` 把 fd 与 `{generation, mode, expiresMonoNs, featureMask}` 一起交给游戏进程的 native → Java 侧周期 `drain(ticket, 2048)` 拉取。**共享内存内是否有额外魔数/校验，无法从 Java 确认。**

#### 4.6.6 `DiagnosticRedactor`：白名单清洗器（**但未接入**）

`DiagnosticRedactor.java` 是严格白名单：事件只允许那 14 个 `Number` 字段，incident 文本字段只允许 `incident_type`、`confidence` 且须匹配 `[A-Z_]{1,32}`，越界直接抛 `IllegalArgumentException`（`:36-38`）。

**但全仓 `grep` 确认 `DiagnosticRedactor` / `sanitizeEvent` / `sanitizeIncident` 除自身定义外没有任何调用点——是死代码。** 隐私边界实际上靠"采集时就只写数字 id"（见 4.6.1）来保证，而不是上传前清洗。

---

### 4.7 反调试 / 反注入 / 完整性自校验

#### 4.7.1 Java 层：几乎没有

`WigVerify`、`VerifyOverlayAuth`、`OfficialBrandContract` 中**没有**任何 `MessageDigest` 自校验、`GET_SIGNATURES` APK 签名比对、`ro.debuggable` 读取、`ptrace`/`frida`/`xposed` 检测。`getPackageInfo(..., 0)`（`WigVerify.java:1958`）flags 为 0，只是读版本名。

Java 层仅有：

- `WigVerify.getOrCreateImei()`（`:274-344`）执行 `su -mm -c getprop ro.serialno`（`:282`）探测设备序列号，回退 `Build.SERIAL` → `Settings.Secure` 的 `android_id` → 随机 16 位小写字母（`:346-353`）。这是**设备指纹/绑定素材**，不是反篡改；但它反证了该 App 依赖 root
- `MainActivity.checkRoot()`（`:1349-1375`）逐个执行 `su -v` 看退出码；`requestRoot()` 用 `id` 命令看 `uid=0`
- `MainActivity` 的诊断命令里有 `cat /proc/sys/kernel/yama/ptrace_scope`、`dmesg | grep -i -E 'avc:|denied|ptrace|xptrace'`（`:3511,3539`）——但这是**给用户看的排障工具**（诊断面板），不是自我保护
- `JccNetworkPolicy.requireFixedApiUrl` / `TrustTransport.isFixedWigPath` 等 URL/表单白名单，属于**抗 patch 的网络层约束**

#### 4.7.2 native 层：真正做检查的地方（证据来自 `strings libdemo.so`）

`libdemo.so` 内确实存在下列字符串，与 Java 侧只做"错误码翻译"的行为互相印证：

| 字符串 | 含义 |
|-|-|
| `ADB_DEBUG` | ADB 调试检测（Java 侧映射为"检测到设备调试功能已开启"） |
| `ENVIRONMENT` | 运行环境安全校验（Java 侧映射为"运行环境安全校验未通过"） |
| `INTEGRITY` | 完整性校验（Java 侧映射为"程序完整性校验未通过"） |
| `INJECT_PENDING` | 注入未完成 |
| `LOCAL_CHECK_BUSY` / `LOCAL_CHECK_TIMEOUT` / `LOCAL_CHECK_UNKNOWN` | 本机安全自检的状态机（有超时/忙/未完成三态） |
| `/proc/self/maps` | 模块枚举 —— 用于检测被注入的第三方 so |
| `/proc/self/cmdline` | 进程身份确认 |
| `/proc/self/task/`、`/proc/self/task` | 线程遍历（与 `MAX_THREAD_STACKS = 16` 对应） |
| `/proc/self/statu`（dump 中显示为截断形态） | 疑似 `/proc/self/status`，即经典 `TracerPid` 反调试读取 |
| `dl_iterate_phdr` | 遍历已加载模块表 |
| `libhoudini.so`、`libndk_translation.so` | x86 翻译层检测（对应 `NativeLibrarySelector` 的 `demo_compat` 分支，即模拟器/PC 场景） |
| `libil2cpp.so`、`libunity.so` | 目标游戏模块（Unity/IL2CPP） |
| `libart.so`、`libc.so`、`libdl.so` | 常见于反调试/内存扫描的枚举目标 |
| `&JCCLV2` | 信任租约魔数（与 Java 侧 `DiagnosticCoordinator.java:1033-1050` 校验的 12 字节头 `"JCCLV2" + 00 00 00 02 01 00` 一致，build hash 位于偏移 116、长 32 字节） |

**Java 侧还留有 native 会返回这些码的旁证**：`VerificationUserMessage.fromInternal`（`:157-168`）把 `MANIFEST` / `INTEGRITY` / **`SELFCRC`** / **`CODE_MISMATCH`** 一律映射为 `INTEGRITY`，把 **`ENV`** / **`TRACER`** / **`HOOK`** / **`ROOT`** 一律映射为 `ENVIRONMENT`。也就是说 native 会产出 **自 CRC 校验失败（SELFCRC）**、**代码段不匹配（CODE_MISMATCH）**、**调试器（TRACER）**、**Hook（HOOK）**、**ROOT** 这几类码——Java 侧只是把它们收敛成两个用户可见文案。

**诚实边界**：

- 未在 `libdemo.so` 中检出 `frida` / `xposed` / `magisk` / `ptrace` / `TracerPid` / `libsubstrate` / `dobby` / `SandHook` / `zygisk` 等**明文字面量**。这不代表没有检测——很可能用了混淆字符串、内联比较，或纯靠 `/proc/self/maps` + `dl_iterate_phdr` 扫描实现（这种方式本来就不需要这些名字）。
- 上述检测的**具体算法、触发阈值、绕过难度，全部实现在 `libdemo.so` 内，Java 侧不可见**，本节只能给出字符串级证据与 Java 侧的行为印证。

#### 4.7.3 失败后的后果

**不崩溃、不硬退出，一律是"拦截功能 + 提示重试"**：

- WIG 登录期失败 → `WigVerify` 调 `verificationTrace.event(INTEGRITY, "INTEGRITY", 0)`、`runtimeRecord("WIG","AUTH_STATE","FAIL","authorized=0")`、`clearSessionLocked()`、`onFailed(...)`（`WigVerify.java:1145-1148`），UI 显示 `"✗ " + 错误信息` 并允许重试（`VerifyOverlayAuth.java:403-417`）
- 服务器撤销授权 → `NativeTrustBridge.ControlListener.onTrustRevoked` → `WigVerify.forceLogout` + 向 `FloatingWindowService` 发 `ACTION_TRUST_REVOKED` 前台服务（`WigVerify.java:240-253`）
- 版本强制更新 → `cancelPendingLogin()` + 只显示强制更新界面，阻断进入（`VerifyOverlayAuth.java:514-516`）

---

### 4.8 本节要点小结

1. **信任根 100% 在 `libdemo.so`**。Java 与信任根之间只有 4 个判决接口：`nativeAcceptChallenge` / `nativeAcceptLease` / `nativeVerifyControlPolicy` / `nativeIsAuthorized`，全部返回 `int`/`boolean`。
2. **Java 层只放公钥**：诊断上报 HMAC 密钥是服务端下发的 32 字节；授权令和版本策略验签是硬编码 P-256 公钥（`BuildConfig.java:13-14`、`JccReleaseConfig.java:5-8`）；设备身份私钥在 AndroidKeyStore。**Java 侧不存在任何可替代 native 信任根的硬编码对称密钥。**
3. **`nativeLicenseHeader` 是 native 生成的不透明 Base64URL 凭据**，只出现在 `X-JCC-License` 头，只在 `/v2/lease` 和 `/v2/renew` 上发送；Java 只校验长度为 `1..342` 且字符属于 `[A-Za-z0-9_-]`。
4. **`WigVerify` 的 12 个 native 方法是官方品牌信息防伪**（FNV-1a 校验和双向核对），不是完整性自校验；校验失败**静默回退到明文默认常量**，属弱保护。`purchaseUrl` 甚至没有校验和保护。
5. **诊断上报是"低信息量数字遥测 + 强签名"**：14 个纯数字字段/事件、无字符串无地址无包名；HMAC-SHA256 签名、gzip 压缩、不加密；采集需服务端下发 ECDSA P-256 签名的授权令，且有配额与用户确认（DEEP 模式）。
6. **反调试/反注入/反 root 在 native**（`/proc/self/maps`、`dl_iterate_phdr`、`/proc/self/status`、自 CRC、代码段比对、翻译层检测），Java 只做错误码到中文文案的翻译；失败后果是拦截功能并允许重试，不崩溃。

---

## 五、悬浮窗 UI、无障碍与配置体系

这一节覆盖 Java 侧除「注入」与「IPC」之外的其余逻辑：窗口体系、按键注入、配置持久化、语音与诊断外壳。

### 5.1 悬浮窗服务是绝对主体

`com.android.support.FloatingWindowService` 是 `Service`，但它的源码单文件 **1.52 MB / 28679 行**，外加 97 个内部类。整个 App 的 UI 编排、状态机、功能开关、面板生命周期几乎都塞在这一个类里，是典型的「巨类」结构。`MainActivity` 只负责启动时的 root/注入引导，注入完成后把控制权交给它。

悬浮窗不是单个窗口，而是一组**分层窗口**：

| 窗口 | 对应实现 | 用途 |
|-|-|-|
| 主面板 | 内嵌各功能页 View | 功能/牌库/指定/玩家/语音/模式/热键/设置/关于 九个 tab |
| 悬浮球 | `BallDraggingControlBinder` | 收起态，可拖拽 |
| 面板头拖动条 | `OverlayHeaderDragBinder` | 面板拖动 |
| 窗口拖动 | `WindowDraggingControlBinder`、`SelectedHeroWindowPositionControlBinder` | 各子窗口位置 |
| 棋盘标记层 | `BoardHeroOverlayController` + `BoardHeroOverlayView` + `.MarkerWindow` | 棋子头顶的牌库/星级标记 |
| 全屏提示层 | `AllInAlertOverlay`、`RankWarningView`、`CelebrationOverlay` | 梭哈提示、三星预警横幅、庆祝动画 |
| 快捷按钮条 | `FloatingActionChipLayer` | 常驻一排快捷键（卖牌/换位/镜像/刷新/梭哈） |
| 语音横幅 | `VoiceAlertBannerOverlay` | 语音播报同步文字条 |
| 同伴面板 | `CompanionDock`、`CompanionPanelLayoutMath` | 伴侣面板停靠 |

窗口类型：`TrustedVisualOverlayWindowManager` 里用 `createWindowContext(2038, null)` 创建 **2038 = `TYPE_APPLICATION_OVERLAY`** 的窗口上下文（另一处复制布局参数时用了 `type = 2032`）。用 `createWindowContext` 而非 `getApplicationContext` 是 Android 12+ 悬浮窗的正确姿势，可避免隐式依赖 Activity 上下文。

### 5.2 防截屏 / 防录屏：反射调用隐藏 API

`ScreenSecureController` 是这一类里技术含量最高的部分。它**没有**用常规的 `WindowManager.LayoutParams.FLAG_SECURE`（全代码库搜不到 `FLAG_SECURE`），而是反射调用 AOSP 未公开接口：

```java
mGetViewRootImpl  = View.class.getMethod("getViewRootImpl", new Class[0]);
mGetSurfaceControl = Class.forName("android.view.ViewRootImpl").getMethod("getSurfaceControl", new Class[0]);
mSetSkipScreenshot = SurfaceControl.Transaction.class.getMethod(
        "setSkipScreenshot", SurfaceControl.class, Boolean.TYPE);
\```

拿到 `ViewRootImpl.getSurfaceControl()` 后，用 `SurfaceControl.Transaction.setSkipScreenshot(surfaceControl, true)` 把某个 View 的 Surface 标记为「跳过截屏」。更狠的一点是它规避了 Android 9+ 的隐藏 API 黑名单——第一句 `getMethod` 失败时会走 fallback，用 `Class.getDeclaredMethod("getMethod", ...)` 反射出 `Method` 对象再 invoke：

```java
Method declaredMethod = Class.class.getDeclaredMethod("getMethod", String.class, Class[].class);
this.mGetViewRootImpl = (Method) declaredMethod.invoke(View.class, "getViewRootImpl", new Class[0]);
\```

这是绕 `HiddenApiRestriction` 的经典手法。要求 `SDK_INT >= 29`，低于此版本 `isReady()` 返回 false，功能静默失效。

效果是「截图与录屏里看不到辅助界面」——比 `FLAG_SECURE` 更精准，因为它只作用于工具自己的覆盖层，不会让整个游戏画面变黑（用 `FLAG_SECURE` 的话录屏会全黑，反而暴露）。

### 5.3 无障碍服务：只用来吃按键

`EmulatorShortcutService` 继承 `AccessibilityService`，但它的能力被压到最小：

- 只重写了 `onKeyEvent` 和 `onAccessibilityEvent`（后者基本是空实现或仅做状态维护）
- **没有** `getRootInActiveWindow()` 调用——即不读别的应用的 UI 树
- 三个自定义动作：`SHORTCUT_TOGGLE_AUTOPICK`（F2 自动拿牌）、`SHORTCUT_TOGGLE_CARDPOOL`（F3 屏幕牌库）、`SHORTCUT_TOGGLE_WINDOW`（F1 显隐悬浮窗）
- 受 `com.android.support.permission.INTERNAL_SHORTCUT`（`signature` 级）保护，只有自己签名的组件能发

也就是说，无障碍权限在这里的唯一用途是**在模拟器里接收 F1~~F12 / A~~Z 的物理按键**（模拟器环境下悬浮窗拿不到按键焦点，必须借无障碍）。它不涉及读取其他 App 内容，这是它比一般游戏外挂「温和」的地方。

### 5.4 配置持久化：双轨制

配置分两层存储：

1. **SharedPreferences + 快照对象**。`AllConfigPersistence.Snapshot` 是一个扁平的 POJO，把几十个开关/数值一次性读写（`editor.putBoolean(KEY_NATIVE_ATTACK_ICON_ENABLED, ...)`、`putInt(KEY_NATIVE_ATTACK_ICON_OFFSET_X, ...)` 等）。UI 上的每个控件都对应一个 `*ControlBinder` 类（`AutoPickCostFilterControlBinder`、`ShopDisplaySettingsControlBinder`、`BoardOverlayTransformControlBinder`……），把 View 与 Snapshot 字段双向绑定。
2. **原子 JSON 文件**。`AtomicJsonFileStore` 用 `FILE_LOCK` 同步 + 临时文件替换的方式写 JSON，用于阵容、配置档案这类结构化数据。外层还有 `GameDataRefreshWorker`、`GameDataRefreshCoordinator` 走 `WorkManager`/后台线程做数据刷新与自动备份（对应 `CONFIG_AUTO_BACKUP_DELAY_MS`、`EXTERNAL_AUTO_BACKUP_FILE`）。

**一个值得注意的设计**：`ConfigPreferenceNamespaces` 定义了一组**被排除在「配置导出/导入」之外的命名空间**：

```java
new ExcludedNamespace("wig_verify_prefs",        "credential_and_device_identity"),
new ExcludedNamespace("jcc_presence_prefs",      "presence_generation"),
new ExcludedNamespace("ipc_v2_config_revision",  "transport_revision"),
new ExcludedNamespace("injection_runtime_state", "injection_runtime"),
new ExcludedNamespace("main_announcement",       "announcement_seen_state"),
new ExcludedNamespace(UiSurfaceControl.PREFERENCES_NAME, "server_ui_surface_policy"),
\```

即：**凭证/设备身份、在线状态代际、IPC 修订号、注入运行时状态、公告已读、服务端下发的 UI 策略**这六类不随配置迁移。前两类是安全考虑（防止导出配置时泄漏凭证或让别人冒用设备身份），后几类是「机器本地状态」，跟着配置走会导致 IPC 版本错配（呼应第二节的 `REJECTED_STALE_REVISION`）。

### 5.5 语音播报链路

三段式：

- `CloudTtsClient` / `CloudTtsWire`（11 + 3 个类）——云端 TTS，负责文本合成音频，功能表里写的「云端模型女声」。
- `VoiceAlertQueue` + `VoiceAlertBannerOverlay` + `VoiceAlertBannerLifecycle`——播报队列与同步文字横幅，可调位置。
- `VoiceAlertPlayer`——本地兜底播放，功能表里的「本地音效：语速/音量/音调本地滑块即调即听」。

事件驱动的播报（三星预警报名、梭哈达成等）由 IPC 事件触发，走 `LineupActiveBus` 之类的总线分发。

### 5.6 其余 Java 侧子系统（一句话职责）

| 子系统 | 类 | 职责 |
|-|-|-|
| 网关客户端 | `JccGatewayClient`（7 类） | 与服务端通信的 HTTP 客户端，承载授权、公告、阵容元数据下发 |
| 在线人数 | `XfOnlineCountClient` | 拉取当前在线用户数 |
| 自助解绑 | `SelfServiceUnbindClient` | 用户自助解绑设备（配合设备指纹绑定） |
| 公告 | `MainAnnouncementState` | 服务端公告的已读状态 |
| 认证恢复 | `AuthenticationRecoveryController`、`ProcessAuthRecoveryGate`、`AuthUiDisplayPolicy` | 授权失效后的静默重认证与 UI 呈现策略 |
| 荣誉/排名预警 | `RankWarningControlBinder`、`RankWarningView` | 三星预警的 UI 与语音联动 |
| 对手预测 | `OpponentPredictionControlBinder`、`OpponentCardingSettingsPanel` | 下一轮对手预测与「智能卡牌」设置 |
| 换位 | `CustomSwapPairingPolicy`、`CustomSwapMirrorSubmit`、`CustomSwapTapApply` | 自定义多对棋子互换、镜像换位 |
| 梭哈 | `AllInPriorityGrid`、`AllInPriorityStore`、`AllInRuleText` | 梭哈优先级排序与规则文案 |
| 棋盘几何 | `BoardOverlayMath`、`BoardHeroOverlayMath`、`CompanionPanelLayoutMath` | 把游戏内坐标换算成覆盖层像素坐标 |
| 头像缓存 | `BoardHeroAvatarCache` | 棋子头顶头像的加载缓存 |
| 日志 | `ContinuousLogCapture`、`DiagnosticLogController` | 持续抓 logcat 并按白名单过滤（含 `libdemo.so`、`HexPredict`、`ShopPredict`、`RecastObserve` 等关键字） |
| 进程探针 | `BoundedProcessProbe` | 有界耗时的 `/proc` 探测，用于判断游戏进程状态 |

「浏览器同步查看战况」的网页共享（`switchWebShare`、`ACTION_SET_WEB_SHARE`）在 Java 侧只看到一个开关和服务端交互，实际网页渲染大概率在服务端，本地不实现——Java 侧找不到 WebView 或本地 HTTP server 的实现。

---

## 六、Native 层：四个 so 的分工与算法归属

### 5.1 结论先行

**关键算法全部在 `libdemo.so` 里，不在 `libinject.so`。**

| 库 | 大小 | 角色 | 是否含业务算法 |
|-|-|-|-|
| `libdemo.so` | 5,589,360 B | **注入到游戏进程的运行时载荷**，全部业务逻辑与算法 | **是，全部** |
| `libdemo_compat.so` | 5,585,280 B | `libdemo.so` 的 x86 翻译兼容版，逻辑相同 | 是，同 `libdemo.so` |
| `libinject.so` | 523,320 B | 注入器（独立可执行），把 `libdemo.so` 塞进游戏进程 | 否，纯加载器 |
| `libinject_x86_64.so` | 528,344 B | x86_64 版注入器 | 否 |

`libdemo_compat.so` 与 `libdemo.so` 只差约 4 KB，是同一份代码针对 x86（模拟器/houdini 翻译层）的构建变体。Java 侧选择逻辑在 `NativeLibrarySelector`：`Build.SUPPORTED_ABIS[0]` 含 `"x86"` 就用 `demo_compat`，否则用 `demo`。

四个库都只有 **arm64-v8a** 一个 ABI 目录，x86_64 版本也是放在 `lib/arm64-v8a/` 下由注入器显式按需选取（`INJECT_NAME_X86_64 = "libinject_x86_64.so"`），不走系统 ABI 分发。

### 5.2 `libinject.so`：注入器

它是 **PIE 可执行文件**（`readelf -h` 显示 `Type: DYN`，但有 `.interp` 段），由 root shell 直接执行，而不是被 `System.loadLibrary` 加载。字符串表里的 Usage 暴露了出身：

```python
Usage: ./path/to/AndKittyInjector [-h] [-pkg] [-pid] [-lib] [ options ]
\```

即基于开源项目 **AndKittyInjector**（内部用 KittyMemory，符号 `KittyCmdln::addFlag` / `addScanf` 可证）。

**它做三件事：**

1. **定位目标进程**：`-pkg com.脱敏.jkchess` / `-pid N`。还支持 `-watch` 模式——用 `inotify_add_watch` 监听 `/proc` 目录，配合 `android_event_am_proc_start` 结构体识别 AMS 的进程启动事件，等游戏进程一起来就注入（字符串 `watch_proc_inject`、`E: -watch is used but the target process is already alive.`）。本样本实际走的是 `-pid` 路径。
2. **无文件注入**：`-dl_memfd` 开关。字符串 `E: nativeInject: memfd_create failed`、`I: nativeInject: memfd_rand(%d) = %s.` 表明它把待注入的 `.so` 读进匿名内存（memfd），再用 `dlopen("/memfd:随机名")` 加载，磁盘上不落地文件。memfd 名带随机后缀，Java 侧用正则 `memfd_rand\(\d+\)\s*=\s*([A-Za-z0-9._-]{5,64})\.` 从注入器输出里把这个随机名抠出来，再去 `/proc/<pid>/maps` 里核对是否真的映射成功。
3. **隐藏痕迹**（可选）：`-hide_maps`（重新映射段以从 `/proc/pid/maps` 消失，`hideSegments`）、`-hide_solist`（从 linker 的 soinfo 链表里摘除，`SoInfoPatch`）。字符串：

```python
I: SoInfoPatch: Removed soinfo(%p) elf(%p) from solist.
E: SoInfoPatch: elf(%p) is not in solist or was loaded before sohead.
I: hideSegments: Hiding segment %p - %p
I: Hide lib from maps: %d
\```

有两条注入路径：`nativeInject`（普通进程，ptrace）和 `emuInject`（模拟器/翻译层进程，失败会回退到传统 dlopen：`I: emuInject: memfd failed, falling back to legacy dlopen.`）。这解释了为什么需要单独的 `libinject_x86_64.so`。

**注意一个细节**：Java 侧实际拼出的命令行（`MainActivity.java:2072`）只传了 `-dl_memfd`，**没有显式传 `-hide_maps` / `-hide_solist`**。这两个开关是否默认开启，需要反汇编 `KittyCmdln::addFlag` 的默认值才能确定；仅凭字符串无法判断。从 `MainActivity` 会在 `/proc/<pid>/maps` 里主动搜 `/memfd:` 前缀来看，memfd 映射**是可见的**，至少 maps 这一层没有隐藏。

### 5.3 `libdemo.so`：注入的游戏内运行时

这是全样本真正的核心。5.5 MB，静态链接 libc++，内嵌 nlohmann/json 3.11.3。

#### 5.3.1 JNI 入口与动态注册

`libdemo.so` 只导出了两个符号：

```python
JNI_OnLoad
Java_com_tdatamaster_tdm_system_FileUtils_FileUtilsInit
\```

`Java_com_android_support_*` 一个都没有——说明所有 native 方法都是在 `JNI_OnLoad` 里用 `RegisterNatives` **动态注册**的。字符串表里能找到完整的注册用方法名与签名：

```python
nativePrepareLicense, nativeBeginChallenge, nativeAcceptChallenge,
nativeBuildLeaseRequest, nativeAcceptLease, nativeIsAuthorized, ...
(Ljava/lang/String;)Z        ([B)I        ([BLjava/lang/String;)[B
([B[B)Z                      (JJI)[J      (J)[J
\```

后者（`(JJI)[J`、`(J)[J`）对应 `DiagnosticSharedMemoryBridge` 里 `nativeDrain(long, long, int)` 返回 `long[]`、`nativeReadHeader(long)` 返回 `long[]` 这类共享内存读取接口。

`Java_com_tdatamaster_tdm_system_FileUtils_FileUtilsInit` 是**腾讯 DataMaster SDK 的 JNI 符号**（`com.tdatamaster.tdm` 是腾讯的数据采集 SDK）。样本里既没有 `com.tdatamaster` 的 Java 类，也没找到调用它的地方。可能是作者拿含该 SDK 的工程当模板留下的残留，也可能是刻意放的干扰项——**未能确认，标为疑点**。

#### 5.3.2 IL2CPP Hook 目标清单

`libdemo.so` 字符串表里出现了一批「类名_方法名」形式的标识符，全部指向游戏《金铲铲之战》的 IL2CPP 方法（游戏用 Unity IL2CPP，Java 侧会检测 `/proc/<pid>/maps` 里的 `libil2cpp.so`）。这些是它 hook 或调用的落点：

| 目标方法 | 推断用途 |
|-|-|
| `FRandom_InternalSample` | Unity/游戏 RNG 底层采样 |
| `FRandom_RandomIntMax` | 随机整数 |
| `FRandUtils_RandWeightsListIndex` | **按权重取列表下标**——商店发牌、海克斯随机都走这里 |
| `RandomEquipmentByQuality_WithJCC` | 按品质随机装备。方法名带 `_WithJCC` 后缀，是本工具改写过的版本 |
| `TAC_GenerateHeroListFromHeroPool` | **从英雄池生成商店英雄列表**——商店预测/自动拿牌的核心 |
| `BaseHexCard_SetData` / `HackHexCard_SetData` | 海克斯卡数据写入（`Hack` 前缀对应被改写的那条路径） |
| `HexStoreItem_SetData` | 海克斯商店条目 |
| `HeroRoot_SetData` / `HeroRoot_Update` / `HeroRoot_ctor` | 场上英雄节点，用于脚下牌库、星级标记 |
| `BuyHeroView_AnimateIn` | 商店购买动画——自动拿牌触发点 |
| `PlayerListItem_SetData` / `_SetMoney` / `_SetBloodValue` / `_SetPlayerLevel` / `_SetPercentValue` | **八家玩家列表**（等级/经济/血量）——「玩家数据」与「游戏内显示经济」的数据源 |
| `TeamRecommend_InitData` / `TeamRecommend_ctor` | 阵容推荐面板（游戏内自带的推荐阵容） |
| `RookieDeckView_Start` / `_SetHeroData` / `_OnDestroy` | 新手阵容视图 |
| `CSoGame_FrameTimeTick` | 游戏主循环帧回调——用于按帧驱动覆盖层与状态刷新 |

外加一个 C++ 命名空间 `NativePlayerListDecor::PostRefreshAll`（`ZN21NativePlayerListDecor12_GLOBAL__N_114PostRefreshAllEv`），是工具自己写的玩家列表装饰器。

**这批 hook 点直接解释了所有「预测」类功能为什么可能：**

- **商店/海克斯预测**——不是「推算概率」，而是 hook 掉了 `FRandUtils_RandWeightsListIndex` / `FRandom_InternalSample` 这些随机源。随机数在游戏客户端本地生成，hook 住随机源就能在结果展示给玩家之前拿到（甚至改写）结果。所以「提前知道本局三次海克斯的品质与具体选项」在技术上是**读取而非预测**。
- **`_WithJCC` 后缀的方法**则是把随机结果直接改掉（`RandomEquipmentByQuality_WithJCC`），对应「指定重铸」——用重铸器锤出指定装备。
- **自动拿牌/一键梭哈**——hook `BuyHeroView_AnimateIn` 与商店列表生成，检测到目标英雄出现即以程序化方式触发购买。

一个佐证：`libdemo.so` 内嵌 `hex_refresh_predictor` 命名空间与 `PredictionSnapshot` 结构（`hex_refresh_predictor::PredictionSnapshot`、`OnSpecifiedHexPredictionPublished`），即「海克斯刷新预测器」是 native 里一个独立模块，预测快照算好后通过 IPC 推给 Java 侧。所谓「预测」是在这个模块里，基于被 hook 的 RNG 状态做的。

#### 5.3.3 Native 侧实现的 IPC 命令

`libdemo.so` 里出现的点号分隔命令名，是 IPC v2 协议的另一端。它与 Java 侧 `SharedMemManager` / `LocalSocketIPC` 共同构成通信层（详见第二节）：

```python
hex.query              hex.specify            hex.cancel
hex.specified.status
lineup.apply           lineup.clear
chess.cancel           chess.mirror           chess.sell
recast.specify         recast.cancel          recast.pool.catalog
recast.specified.status
config.replace         debug.pointers         game.exit
match.started          match.ended
diagnostics.trace.attach                   diagnostics.trace.disable
\```

配套的错误/拒绝码：

```python
REJECTED_NO_CONSUMER   REJECTED_PARSE
REJECTED_STALE_GENERATION                   REJECTED_STALE_REVISION
INJECT_PENDING         INPUT_INVALID        CACHED_NOT_VISIBLE
GATEWAY_LOGIN_LICENSE_MISSING               GATEWAY_NONCE_UNAVAILABLE
GATEWAY_BUILD_MANIFEST_INVALID              GATEWAY_LOGIN_INPUT_INVALID
LOCAL_CHECK_BUSY       LOCAL_CHECK_TIMEOUT  LOCAL_CHECK_UNKNOWN
WIG_PARSE              WIG_REJECT
\```

`REJECTED_STALE_GENERATION` / `REJECTED_STALE_REVISION` 说明协议带**代际号（generation）与修订号（revision）校验**，防止 App 与 native 版本错配后继续发命令。

native 内部还有自己的 IPC 实现命名空间 `ipc_v2`（`N6ipc_v27WriteIoE`、`N6ipc_v28FdCloserE`），即 IPC v2 的收发逻辑在 native 侧有一份独立实现。

#### 5.3.4 其他 native 能力

- **压缩/载荷**：内嵌 XZ 解压器（`XzUnpacker_Construct` / `_Code` / `_IsStreamWasFinished`），用于解压内置的压缩数据（如阵容库、英雄元数据）。
- **设备指纹**：读取 `ro.product.model` / `ro.product.brand` / `ro.boot.serialno` / `ro.serialno` / `ro.build.version.sdk` / `ro.arch`，并检查 `ADB_DEBUG`。授权绑定设备时用。
- **反调试迹象**：`ADB_DEBUG` 常量、`/proc/self/task/` 路径、以及一批**随机字节字符串**（看似加密的日志/配置）。日志与提示文案在 native 侧被混淆，与 Java 侧「全用 Unicode 转义但语义可读」形成对比——native 侧是有意做过处理的。

### 5.4 待确认的疑点

以下问题仅靠 `strings` + 反汇编无法定论，需要 IDA 介入：

1. `-hide_maps` / `-hide_solist` 的默认值，以及本样本的 memfd 映射是否真的对游戏的反作弊可见。
2. `libdemo.so` 是如何在 IL2CPP 里定位到 `TAC_GenerateHeroListFromHeroPool` 等方法的（扫元数据、特征码匹配、还是 `il2cpp_api` 符号解析）——这决定它对游戏版本的鲁棒性。
3. `hex_refresh_predictor` 的完整算法：`PredictionSnapshot` 的字段构成与预测推导过程。
4. `com.tdatamaster` JNI 符号的真实用途（残留 or 干扰）。
5. native 侧反调试的具体强度（是否检测 Frida/Xposed、是否做完整性自校验）。

---

---

### 6.7 IDA 静态分析补充（`libdemo.so`，IDB 已加载）

以下结论来自 IDA Pro 对 `libdemo.so` 的静态分析（镜像 base `0x0`，实际大小 `0x554970`，7060 个函数，符号表已 strip，仅 `JNI_OnLoad` 与一个腾讯 SDK 导出保留名字）。

#### 6.7.1 JNI 注册结构（已完整还原）

`JNI_OnLoad`（`0x2958D8`）的结构是：

```c
jint JNI_OnLoad(JavaVM *vm, void *reserved)
{
  if ( !vm ) return -1;
  if ( (sub_295704(vm, reserved) & 1) != 0 )          // 缓存 JavaVM 引用
  {
    if ( (unsigned int)sub_2959C4() ) return 65542;
    else return -1;
  }
  ...
  v6 = sub_3B3D9C(v8[0]);   // RegisterNatives: NativeTrustBridge
  v7 = sub_353D64(v8[0]);   // RegisterNatives: WigVerify
  if ( (int)(v6 | v7 | sub_34074C(v8[0])) < 0 )        // RegisterNatives: DiagnosticSharedMemoryBridge
    return -1;
  return 65542;
}
\```

三个注册函数结构同构（各 `0x104` 字节），都是 `FindClass` → `RegisterNatives` → `DeleteLocalRef`。表地址与条目数：

| Java 类 | JNINativeMethod 表 | 条目数 |
|-|-|-|
| `com.android.support.trust.NativeTrustBridge` | `0x5415C0` | 20 |
| `com.android.support.diagnostics.DiagnosticSharedMemoryBridge` | `0x541200` | 8 |
| `com.android.support.WigVerify` | `0x541310` | 12 |

**`NativeTrustBridge`（20 个，含函数地址）**——授权信任链的全部 native 接口：

| 方法 | 签名 | 地址 |
|-|-|-|
| `nativeBeginChallenge` | `()[B` | `0x3B3EA0` |
| `nativePrepareLicense` | `(Ljava/lang/String;)Z` | `0x3B40D0` |
| `nativeBuildGatewayLoginRequest` | `(Ljava/lang/String;Ljava/lang/String;)[B` | `0x3B4298` |
| `nativeBuildWigLoginRequest` | `(Ljava/lang/String;Ljava/lang/String;)[B` | `0x3B4E24` |
| `nativeAcceptWigLoginResponse` | `([BLjava/lang/String;)J` | `0x3B53B0` |
| `nativeGetWigLoginCode` | `()Ljava/lang/String;` | `0x3B5844` |
| `nativeGetWigLoginError` | `()Ljava/lang/String;` | `0x3B5A58` |
| `nativeLicenseHeader` | `()[B` | `0x3B5B70` |
| `nativeAcceptChallenge` | `([B)I` | `0x3B5C8C` |
| `nativeBuildLeaseRequest` | `([BLjava/lang/String;)[B` | `0x3B5E50` |
| `nativeAcceptLease` | `([B)I` | `0x3B61B0` |
| `nativeGetTrustError` | `()I` | `0x3B6378` |
| `nativeIsAuthorized` | `()Z` | `0x3B6398` |
| `nativeWarmPreLogin` | `()Z` | `0x3B63D0` |
| `nativeClearTrust` | `()V` | `0x3B63F0` |
| `nativeVerifyControlPolicy` | `([B[B)Z` | `0x3B65C8` |
| `nativeSetServerTimeOffset` | `(J)V` | `0x3B6764` |
| `nativeExportWigRelay` | `()[B` | `0x3B6770` |
| `nativeLoadFeatureCatalog` | `()Z` | `0x3B6AEC` |
| `nativeExportFeatureCatalog` | `()[B` | `0x3B6B40` |

**`DiagnosticSharedMemoryBridge`（8 个）**：`nativeCreateReader(J)Z` `0x340854`、`nativeDuplicateReaderFd(J)I` `0x340A2C`、`nativeCloseReader(J)V` `0x340ACC`、`nativeReadHeader(J)[J` `0x340B60`、`nativeDrain(JJI)[J` `0x340CF0`、`nativeReadThreadStacks(J)[J` `0x340FF8`、`nativeReadFeatureHealth(J)[J` `0x34194C`、`nativeReadCrashSlot(J)[J` `0x341BE0`。全部围绕「从 native 侧共享内存读诊断快照」，`(J)[J` 说明每次返回一组 `long`（定长槽位）。

**`WigVerify`（12 个）**：`nativeGetVersionCode` `0x353E6C`、`nativeGetVersionName` `0x353E78`、`nativeGetChannelUrl` `0x353F44`、`nativeGetOfficialPrefix` `0x354034`、`nativeGetOfficialHandle` `0x354138`、`nativeGetOfficialChannelUrl` `0x35420C`、`nativeGetOfficialSupportUrl` `0x3542FC`、`nativeGetOfficialGroupUrl` `0x3543F0`、`nativeGetOfficialTextChecksum` `0x3544E0`、`nativeGetOfficialChannelChecksum` `0x3544F0`、`nativeGetOfficialSupportChecksum` `0x354500`、`nativeGetOfficialGroupChecksum` `0x354510`。

注意这 12 个方法是**纯 getter**：返回版本号、官方频道 URL 和对应 checksum。checksum 由 native 侧算出期望值，Java 侧 `WigVerify` 拿到后再校验——即「官方频道防伪」，防的是二次打包者替换成自己的推广链接。**这里没有密码学，只有完整性校验。**

从字符串表推断出的 `nativeAttackIconEnabled` / `nativeAttackIconOffsetX/Y` / `nativeAttackIconSizePercent` / `nativePlayerEconName` 这 5 个名字**不在以上任何注册表中**——它们只是 `AllConfigPersistence` 里的 SharedPreferences 键名撞了 `native` 前缀，不是真正的 JNI 方法。这是纯字符串检索容易踩的坑，在此更正。

#### 6.7.2 IL2CPP 定位方式：硬编码偏移表

hook 安装点在 `sub_293304`（`0x293304`，6952 字节，native 侧初始化主函数）。它内部对每个 hook 目标重复同一段模式：

```asm
0x2943c0  ADRL  X0, aLibil2cppSo        ; "libil2cpp.so"
0x2943c8  BL    sub_2F7FE4              ; 解析 so 基址 → X21
0x2943e0  ADRL  X8, xmmword_566DD0
0x2943e8  LDR   X8, [X8, #(qword_566E68 - 0x566DD0)]   ; 从偏移表取偏移
0x2943f0  ADD   X0, X8, X21             ; 目标地址 = 基址 + 偏移
0x2943f8  ADR   X1, sub_2F8DBC          ; 替换函数
0x2943fc  ADRL  X2, off_564F18          ; 原始函数保存位置
0x294404  ADRL  X3, aTacGenerateher     ; "TAC_GenerateHeroListFromHeroPool"（仅用于日志）
0x29440c  BL    sub_38A764              ; 装钩
\```

结论：**它不用 IL2CPP 的 `il2cpp_class_get_method_from_name` 之类 API 按名字解析方法，而是把每个目标函数在 `libil2cpp.so` 里的偏移硬编码在一张表（`0x566DD0`）里，运行时用「基址 + 偏移」直接算出地址。** 表里同时存了 `libil2cpp.so` 和 `libunity.so` 两套偏移（字符串 `libil2cpp.so` 与 `libunity.so` 都出现在这里）。

这解释了工具的版本依赖：**游戏每更新一次，只要 IL2CPP 生成代码布局变了，这张偏移表就得跟着改。** 612 / 632 这类版本号差异很可能就对应不同的偏移表。

#### 6.7.3 装钩引擎是自研的

`sub_38A764`（384 字节）做地址校验：

```c
v3 = 0xFFFFFFFF00000000;
if ( a1 < 0x10000 ) goto INVALID;
if ( a1 == 0xDEADBEEF || a1 == 0xCCCCCCCC || a1 == 0xFEE1DEAD || a1 == 0xBADC0DE )
    goto ALREADY_HANDLED;                       // 毒值（未初始化内存）检测
...
v8 = getpid();
if ( syscall(270, v8, v14, 1, v13, 1, 0) == 4 && (v12 - 1) <= 0xFFFFFFFD )
    return sub_4435E4(a1, a2, a3);              // 校验通过 → 真正装钩
\```

`syscall(270)` 在 arm64 上是 **`process_vm_readv`**。它对自己进程（`getpid()`）调用 `process_vm_readv` 读取目标地址的 4 个字节——**这是安全的内存可读性探测**：地址非法时 `process_vm_readv` 返回 `EFAULT` 而不是触发 `SIGSEGV`，于是可以在不崩溃的前提下判断「这个偏移算出来的地址到底是不是有效代码」。读到 `0xDEADBEEF` / `0xCCCCCCCC` 这类毒值也判为无效。

真正装钩的是 `sub_4435E4`。在 `libdemo.so` 整个字符串表里搜索 `dobby` / `shadowhook` / `xhook` / `substrate` / `And64InlineHook` 等常见 inline hook 框架标识，**一条都没有**——所以这是**自研的 inline hook 引擎**（自写指令重定位 + trampoline）。

#### 6.7.4 完整 hook 目标清单

`sub_293304` 内引用的全部字符串（53 条去重）如下，去掉路径与格式串后即为 hook 目标全表。

**渲染与主循环**

| 目标 | 作用 |
|-|-|
| `eglSwapBuffers` | 在游戏 GL 交换缓冲的时机绘制自己的覆盖层 |
| `CSoGame_FrameTimeTick` | 游戏帧回调，驱动状态刷新 |

`eglSwapBuffers` 这个 hook 是理解「游戏内显示经济」「棋子脚下牌库」「攻击准星」的关键：这些**不是** Android WindowManager 悬浮窗，而是 hook 了游戏的 GL 交换点，把内容**直接画进游戏自己的 GL 表面**。所以它们能严丝合缝跟着棋盘走，配合 `ScreenSecureController` 的反截屏处理（见第五节）在截图时隐藏。

**商店与英雄**

| 目标 | 作用 |
|-|-|
| `TAC_GenerateHeroListFromHeroPool` | 从英雄池生成商店列表 |
| `UpdateRefreshBuyList2UI` | 刷新商店 UI |
| `SelectHeroVectorByUserLevel` | 按玩家等级决定英雄池概率 |
| `GetBadLuckProtectionV2` | 保底（bad-luck protection）机制 |
| `FRandUtils_RandWeightsListIndex` | 按权重取下标 |
| `FRandom_InternalSample` | 随机采样 |
| `FRandom_RandomIntMax` | 随机整数 |
| `BuyHeroView_AnimateIn` | 购买动画（自动拿牌触发点） |
| `OnBuyHeroInfoChange` | 购买信息变更 |
| `GetHeroKu` | 英雄库（牌库余量数据源） |
| `HeroRoot_SetData` / `_ctor` / `_Update` | 场上英雄节点 |

`SelectHeroVectorByUserLevel` + `GetBadLuckProtectionV2` + 三个 `FRandom*` 合在一起，就是「商店还剩什么、下一刷会出什么」的完整信息链——**预测能力来自 hook 住整条随机链路，而不是概率推算。**

**海克斯**

| 目标 | 作用 |
|-|-|
| `GetRandomHACfgForSingle` | 随机海克斯配置（HA = Hex Augment） |
| `FilterValidConfigs` | 过滤合法配置 |
| `HexStoreItem_SetData` | 海克斯商店条目 |
| `BaseHexCard_SetData` / `HackHexCard_SetData` | 海克斯卡数据（`Hack` 为改写路径） |

**装备与重铸**

| 目标 | 作用 |
|-|-|
| `RandomEquipmentByQuality` / `RandomEquipmentByQuality_WithJCC` | 按品质随机装备（`_WithJCC` 为改写版） |
| `GetTargetLevelEquipmentPool` | 目标等级装备池 |
| `RecastingHeroEquipments` | 英雄装备重铸 |
| `OnEquipmentRecasting` | 重铸事件回调 |

**玩家与对手**

| 目标 | 作用 |
|-|-|
| `GetMyPlayerModel` | 本方玩家数据 |
| `OpponentPrediction.SelectHighScore` | 对手预测的评分选择函数 |
| `PlayerListItem_SetData` / `_SetMoney` / `_SetPlayerLevel` / `_SetBloodValue` / `_SetPercentValue` | 八家列表数据 |

`OpponentPrediction.SelectHighScore` 被直接 hook，说明「下一轮可能遇到谁」是在游戏自己的匹配/评分函数上取数，同样属于**读取**而非推算。

**推荐与面板**

| 目标 | 作用 |
|-|-|
| `TeamRecommend_InitData` / `_ctor` / `TeamRecommendItemCallback0~3` | 游戏内阵容推荐面板 |
| `RecListPanelBattle_InitData` | 推荐列表面板 |
| `SetRookieDeckData` / `GetRecommendData` | 新手阵容数据 |
| `RookieDeckView_Start` / `_SetHeroData` / `_OnDestroy` | 新手阵容视图 |
| `AddPopPanel` / `RemovePopPanel` | 弹窗加入/移除（对应「拦截弹窗」） |

**输入与其他**

| 目标 | 作用 |
|-|-|
| `WriteInput(byte[])` / `WriteInput(List<byte>)` | 游戏输入写入函数 |
| `GetLoginPlatType` | 登录平台类型（对应「iOS 转区」） |

`WriteInput` 被 hook 是「自动拿牌 / 一键卖牌 / 一键换位 / 自动刷新商店 / 一键梭哈」的实现基础：工具构造游戏自己的输入结构体再调用被 hook 的 `WriteInput`，**在游戏引擎看来这就是玩家操作**，不经过 Android 触摸注入，因此不受 `FLAG_NOT_TOUCHABLE` 影响，也不需要无障碍的点击能力。

#### 6.7.5 字符串混淆

`sub_293304` 里能看到加密字符串的解密内联展开：

```c
v4 = *(int8x16_t *)v3;
v5 = *(_BYTE *)(v3 + 16);
*(_BYTE *)(v3 + 17) = 0;
*(_BYTE *)(v3 + 16) = v5 ^ 0x15;                             // 逐字节 XOR 0x15
*(int8x16_t *)v3 = veorq_s8(v4, (int8x16_t)xmmword_16F60);   // 16 字节向量 XOR
\```

即 native 侧字符串用**一次性惰性解密**（首次访问时 XOR 还原并原地写回，`+17` 是「已解密」标志位）。密钥是 `xmmword_16F60` 与单字节 `0x15`。这解释了为什么 `strings` 只能捞到一部分明文——hook 目标名与协议命令名是明文，系统属性名和日志文案是加密的。

#### 6.7.6 由 IDA 更正/补充的结论

| 项 | 原（仅 strings）判断 | IDA 核实结果 |
|-|-|-|
| `nativeAttackIcon*` / `nativePlayerEconName` | 疑似 JNI 方法 | **不是**，仅是 SharedPreferences 键名 |
| IL2CPP 方法定位方式 | 未确定 | **硬编码偏移表**（`0x566DD0`），非 API 按名解析 |
| 装钩引擎 | 未确定 | **自研 inline hook**（`sub_4435E4`），非 Dobby/ShadowHook |
| `WigVerify` 方法数 | 13 | **12** |
| 覆盖层渲染路径 | 疑似 WindowManager | **`eglSwapBuffers` hook，画进游戏 GL 表面** |
| 输入注入路径 | 疑似无障碍/触摸 | **hook `WriteInput`，构造游戏原生输入** |
| 地址有效性防御 | 未知 | `process_vm_readv` 自读探测 + 毒值检测 |

#### 6.7.7 仍需动态分析才能回答的问题

1. `hex_refresh_predictor` 的具体预测推导逻辑。字符串表里没有该命名空间的函数名，符号已 strip，需要在 `sub_293304` 之后按交叉引用手工定位并重建结构体。
2. 偏移表 `0x566DD0` 的完整条目数与对应的 632 版游戏构建号。
3. `sub_4435E4` 自研 hook 引擎的指令重定位实现细节与稳定性。
4. `NativeTrustBridge` 20 个方法内部的密码学原语（是否有硬编码密钥、是否用 ECDH/Ed25519）。
5. 反调试强度：目前只看到 `ADB_DEBUG` 常量与信号处理安装，未见 Frida / Xposed 主动检测特征串。

---

## 七、对手预测（下一场次对手）的实现

### 7.0 一句话结论

**它不是预测，是三种来源的读取，按优先级择优采用。** 主力来源是把 `preMatchData` 的读取挂在游戏主循环帧回调 `CSoGame_FrameTimeTick` 上，**每帧轮询游戏自己的赛前配对数据结构**；兜底来源是钩住游戏自己的对手选择函数 `OpponentPrediction.SelectHighScore` 抄结果。Java 侧只做「挑一个可用 id 显示」，没有任何推算。

### 7.1 三个数据来源与优先级

`MatchupSnapshot.sourcePriority()` 明确了三条来源及其优先级：

| `source` 取值 | 优先级 | 含义 |
|-|-|-|
| `preMatchData` / `preMatchData-empty` | 3（最高） | 直接读游戏的赛前配对数据结构 |
| `preMatch` | 2 | 赛前配对的另一条读取路径 |
| `selectHighScore` | 1（兜底） | 钩住游戏对手选择函数的返回值 |

裁定规则在 `MatchupSnapshot.shouldAccept()`：快照过期就直接接受；`matchId` 更大就接受、更小就丢弃；`matchId` 相同则比较 `sourcePriority`，高者胜。即**同一局内高优先级来源可以覆盖低优先级来源，但反过来不行**。

>
> 补充（详见 7.7.1）：native 侧 `source` 实际是**数字 id**（1=`selectHighScore`、2=`preMatch`、3=`preMatchData`），由 `libdemo.so` 内一张相对偏移表映射成字符串。表中**只有这 3 项**。
>
>
>

### 7.2 主力来源：每帧轮询 `preMatchData`

在第六节 6.7.4 列出的 hook 表里，`CSoGame_FrameTimeTick` 的处理器就是 `sub_28EB48`（8092 字节）。装钩现场（`0x293b64`–`0x293b8c`）：

```asm
0x293b64  LDR   X8, [qword_55BF40]      ; 目标函数指针
0x293b70  LDR   X0, [X8]                ; = CSoGame_FrameTimeTick
0x293b7c  ADR   X1, sub_28EB48          ; 处理器 = 配对数据读取器
0x293b80  ADRL  X2, off_55D260          ; 原函数保存位
0x293b88  ADRL  X3, aCsogameFrameti     ; "CSoGame_FrameTimeTick"
0x293b8c  BL    sub_38A764              ; 装钩
\```

所以**游戏每渲染一帧，它就重新读一次赛前配对数据**。这就是该功能看起来「实时、不滞后」的原因——数据一直在刷新，而不是在回合开始时算一次。

读取地址来自运行时解混淆的全局量（`sub_27E3D4`）：

```c
qword_564AF0 = qword_5516A0 ^ 0x93AC5E71D0FE2537LL;
qword_564AF8 = qword_5516A0 ^ 0x93AC5E71D0FE26D7LL;   // 配对数据基址
qword_564B00 = qword_5516A0 ^ 0x93AC5E71D0FE24A7LL;
qword_564B08 = qword_5516A0 ^ 0x93AC5E71D0FE24ABLL;
qword_564B10 = qword_5516A0 ^ 0x93AC5E71D0FE24E7LL;
\```

`qword_5516A0` 是模块基址，右侧常量是 XOR 掩码——**与 6.7.2 的硬编码偏移表是同一套设计**，只是这里多了一层掩码混淆。实际读取的是 `qword_564AF8 + a1`。

#### 安全读取与结果分类

读取前先做地址合法性校验，然后用 `process_vm_readv` 自读 8 字节：

```c
v63 = qword_564AF8 + a1;
if ( v63 < 0x10000 ) goto UNAVAILABLE;
if ( v63 == 0xDEADBEEF || v63 == 0xCCCCCCCC ||
     v63 == 0xFEE1DEAD || v63 == 0xBADC0DE ) goto UNAVAILABLE;   // 毒值检测
...
v74 = getpid();                                  // 读自己
if ( syscall(270, v74, &src, 1, &v158, 1, 0) != 8 )  // process_vm_readv
    goto UNAVAILABLE;
\```

`syscall(270)` = `process_vm_readv`，对**自身进程**调用——地址非法时返回 `EFAULT` 而不是触发 `SIGSEGV`，于是能在不崩溃的前提下验证「这个偏移算出来的地址到底有没有东西」。这与 6.7.3 里 `sub_38A764` 用的是同一个技巧。

校验通过后按结构体内容分类，失败路径各自带一个诊断标签：

| 标签 | 触发条件 |
|-|-|
| `preMatchData-unavailable` | 地址非法、是毒值、或读取失败 |
| `preMatchData-invalid-array` | 读到了，但数组结构不合法 |
| `preMatchData-empty` | 结构合法但为空（未进入配对阶段） |
| `preMatchData-unrecognized` | 结构合法但版本不匹配，字段布局对不上 |
| `preMatchData-resolved` | 成功解析 |

这些标签既用于日志，也直接决定 `source` 字段的取值（`preMatchData-empty` 会作为独立 source 上报，Java 侧识别为「显式空」）。`preMatchData-unrecognized` 的存在说明**它对游戏结构体布局有版本假设**，与 6.7.2 的偏移表问题同源。

### 7.3 兜底来源：钩 `SelectHighScore` 但不改行为

处理器 `sub_28C6F4`（152 字节）短得出乎意料：

```c
__int64 sub_28C6F4(__int64 a1)          // a1 = 游戏对象的 this 指针
{
  if ( !off_55D288 ) return 0;
  v2 = off_55D288();                    // 先调用原函数
  if ( (sub_3D55F8() & 1) != 0 )        // 开关
  {
    qword_564E38 = a1;                  // 抄下参数
    qword_564E40 = v2;                  // 抄下返回值
    qword_564E48 = sub_4F2174();        // 抄下附加上下文
    atomic_store(1u, byte_564A1C);      // 置位「有新数据」
    sub_5339F0(1LL, &byte_564A1C[4]);   // 唤醒等待线程
  }
  return v2;                            // 原值返回，不修改
}
\```

三点值得强调：

1. **`return v2` 是原函数的返回值，没有被改动。** 这个钩子是纯观察器，游戏的对手选择逻辑完全不受影响。这和商店/装备那类「改写型」钩子（如 `RandomEquipmentByQuality_WithJCC`）性质完全不同——对手预测只读不写。
2. 它抄下来的是**游戏自己算出来的对手**，所以「预测」的准确性等同于游戏本身的决策，不存在猜错的问题。
3. 数据通过 `atomic_store` + `sub_5339F0`（条件变量唤醒）交给消费者线程，由 `sub_29FAA8` 取出这三个全局量并组装推送。

### 7.4 IPC 载荷格式

发布路径为 `sub_28EB48` / `sub_2C0524` → `sub_2D6880`（JSON 组装，426 行）。字段从反编译中逐个确认：

```json
{
  "matchId":    <int>,          // 第几局/轮次，用于新旧裁定
  "myId":       <int>,          // 我的座位号
  "opponentId": <int>,          // 我的对手座位号，-1 表示无
  "source":     "preMatchData" | "preMatch" | "selectHighScore" | "...-empty",
  "pairs": [
    { "p1": <int>, "p2": <int>, "ghost": <int> }
  ]
}
\```

**`pairs` 是整张配对表，不是只有我这一对**——游戏这一轮谁打谁全部在里面。这是理解该功能能力边界的关键：它拿到的是全局配对结果，因此可以标出「攻击准星」、预告别人的对局，而不只是自己那一场。

`ghost` 字段（`-1` 表示无，否则为被复制的玩家座位号）对应游戏里的**幽灵对局**：你打的不是本人，而是某个玩家阵容的快照。Java 侧对此有专门处理——`OpponentSelectionPolicy.resolveFromPairs()` 里，当 `ghostSourcePlayer != -1` 时返回的是**幽灵的源玩家**，也就是「你实际面对的是谁的阵容」。玩家座位号有效范围是 `0..7`（八家）。

### 7.5 Java 侧只做选择，不做推算

数据到达后由三件小事决定显示什么：

**`MatchupSnapshot`** 负责接收裁定：来源优先级、`matchId` 新旧比较、新鲜度（`isFresh` 带时间窗）。

**`OpponentSelectionPolicy.resolve()`**（140 行）是三级回退：

```java
static int resolve(int i, int i2, List<MatchupPairData> list, List<PlayerInfo> list2) {
    int my = resolveMyPlayerId(i2, list2);
    if (isSelectableOpponent(i, my, list2))  return i;        // ① 直接用推来的 opponentId
    int fromPairs = resolveFromPairs(my, list);
    if (isSelectableOpponent(fromPairs, my, list2)) return fromPairs;  // ② 从整张配对表里找我这行
    PlayerInfo me = findLocalPlayer(my, list2);
    if (me == null || !isSelectableOpponent(me.enemyId, my, list2)) return -1;
    return me.enemyId;                                        // ③ 退回本地玩家模型的 enemyId
}
\```

`isSelectableOpponent()` 会排除自己，并检查该座位玩家 `hp != 0`（已淘汰的不能当对手）。

**`retainDuringActiveMatch()`** 做防抖：对局进行中，只要推来的对手**还活着**（`hp != 0`）就保持显示不清空，避免每帧刷新时界面闪断。这个函数也解释了为什么 `OpponentMatchupRefreshPolicy.Resolved` 里会同时保留 `opponentId` 和 `retainedPlanningOpponentId` 两个字段。

### 7.6 整体链路

```python
游戏主循环每帧
   └─ CSoGame_FrameTimeTick  ──[hook]──►  sub_28EB48
                                           ├─ 读 qword_564AF8 + off（赛前配对结构）
                                           ├─ process_vm_readv 自读校验（防 SIGSEGV）
                                           ├─ 分类：resolved / empty / unavailable / ...
                                           └─ sub_2D6880 组装 JSON
                                                 └─► push "updateMatchup"
                                                       { matchId, myId, opponentId, source, pairs[] }

游戏选对手时（兜底）
   └─ OpponentPrediction.SelectHighScore ──[hook]──► sub_28C6F4
                                           ├─ 调原函数，原值返回（不改游戏行为）
                                           └─ 抄 a1 / 返回值 / 上下文 → 置位 + 唤醒
                                                 └─► sub_29FAA8 取出 → 同样组装 JSON 推送

Java 侧
   IpcMatchupEnvelopeParser / IpcMatchupPairsParser  →  MatchupSnapshot（按 source 优先级 + matchId 裁定）
   →  OpponentSelectionPolicy.resolve（三级回退，排除自己与已淘汰）
   →  retainDuringActiveMatch（对局中防抖）
   →  显示「下一轮对手」与攻击准星
\```

### 7.7 四个疑点的复查结果

初稿留下的四个疑点已逐个查清，其中第 2 条推翻了初稿的判断。

#### 7.7.1 `source` 字段的实现：数字 id + 相对偏移表（推翻初稿）

初稿说 `preMatch` / `selectHighScore` 是「无交叉引用的孤立字符串」。**这个判断是错的。**

真正的机制在 JSON 构建器 `sub_2D6880` 里（第 113 行）：

```c
v53 = (char *)dword_212BA8 + dword_212BA8[a4 - 1];
\```

`a4` 是**数字 source id**（1 基），`dword_212BA8` 是表自身地址，表项是**相对自身的负数偏移**。因为存的是计算出来的偏移而不是重定位指针，IDA 无法把它识别成交叉引用——这正是初稿搜不到 xref 的原因。

表在 `0x212BA8`，实测**只有 3 项**：

| id | 地址 | 字符串 |
|-|-|-|
| 1 | `0x1B683` | `selectHighScore` |
| 2 | `0x1C322` | `preMatch` |
| 3 | `0x1BA7B` | `preMatchData` |

验算 id=3：`0x212BA8 + (int32)0xFFE08ED3 = 0x212BA8 - 0x1F712D = 0x1BA7B`，正是 `preMatchData`。

**由此得到一条重要结论：native 侧能发出的 `source` 只有这 3 个值。** `preMatchData-empty` / `-unavailable` / `-invalid-array` / `-unrecognized` 这几个标签走的是 `sub_2F7250`（1412 字节的**诊断事件发射器**，写入结构化诊断流），**不进入 matchup 信封的 `source` 字段**。也就是说 Java 侧 `MatchupSnapshot.sourcePriority()` 里对 `"preMatchData-empty"` 的处理、以及 `isExplicitEmpty()` 依赖的 `source.endsWith("empty")` 判断，在当前 native 构建下**永远不会命中**——属于防御性/遗留代码。

#### 7.7.2 `preMatch`（优先级 2）的来源路径（已查清）

它由**同一个帧回调处理器** `sub_28EB48` 发出，不是另一条独立链路。该函数有**两个发出点**：

| 发出点 | source id | 函数 | 目标 |
|-|-|-|-|
| `0x290910` | **3** (`preMatchData`) | `sub_2D6880`（直接组装） | 高优先级 |
| `0x2907C4` | **2** (`preMatch`) | `sub_2C0524`（共享构建器） | 次优先级 |

调用点现场（`0x2907b8`）：`MOV W2, #2` → 即传入 sourceId=2。

语义上这是 `preMatchData` **解析失败后的降级路径**——同一帧内先用直读结构体尝试，不成再走次一级读取。两者共用同一个触发时机（每帧），所以「优先级」在时间上几乎没有差异，`shouldAccept` 的优先级比较更多是防止乱序覆盖。

#### 7.7.3 `sub_2C0524` 的角色（已查清）

它**不是** `preMatch` 专有路径，而是一个**共享的快照构建器**：

```c
sub_2C0524(out, capturedCtx, sourceId)   // sourceId 透传给 sub_2D6880
\```

两个调用者分别传不同的 id：

| 调用点 | 调用者 | sourceId | 对应 source |
|-|-|-|-|
| `0x2907C4` | `sub_28EB48`（帧回调） | `W2 = #2` | `preMatch` |
| `0x2A2508` | `sub_29FAA8`（SelectHighScore 消费者） | `W2 = #1` | `selectHighScore` |

即两条来源共用同一个组装与下发实现，只是 sourceId 不同。这也解释了为什么初稿会误判它「对应 preMatch」——它其实两个都发。

#### 7.7.4 `sub_3D55F8()` 的语义（已查清，不是鉴权）

它是**特性开关 + 节流闸门**，不是「是否进对局」或「是否已授权」的判定。展开四条子调用：

| 子调用 | 行为 | 判定 |
|-|-|-|
| `sub_3D4B78(3)` | 查特性开关表（`a1 <= 5` 的小枚举，走 `unk_56B670` 与 `sub_3D48C0`） | 「特性 3 是否启用」 |
| `sub_3D53F4()` | `clock_gettime(CLOCK_MONOTONIC=7)` 与 `unk_56B7C0` 记录的时间戳比较，窗口 `0x59682F01` ns | **约 1.5 秒**内是否有过事件 |
| `sub_3D548C(3)` | `clock_gettime` 与 `unk_56B790` 比较，窗口 `0x5F5E100` ns = 0.1 秒；不匹配时用 `sub_3CEC38` 回写时间戳 | **0.1 秒冷却** |
| `sub_3D5370()` | 读 `unk_56B738` 后调 `sub_3D030C(_, 2)` | 辅助计数/状态 |

组合逻辑（`sub_3D55F8` 本身只有 76 字节）：

```c
if ( sub_3D4B78(3) & 1 )  return 1;              // 特性已启用
if ( sub_3D53F4()  & 1 )  return sub_3D5370();   // 1.5s 窗口内
return sub_3D548C(3);                            // 否则走 0.1s 冷却判断
\```

所以它的作用是**给兜底钩子限流**：只有当特性启用、或处于 1.5 秒活跃窗口、或通过 0.1 秒冷却时，才把 `SelectHighScore` 的结果抄下来并发 IPC。这是必要的——`SelectHighScore` 在游戏里调用频繁，每帧都推会打爆 IPC。

#### 7.7.5 `preMatchData` 结构体布局（部分查清）

比初稿推进了一步，但仍未拿到逐字段语义：

- 首读是对 `qword_564AF8 + a1` 的安全读取，读到的 `s` 是 **IL2CPP 数组对象**——检查 `s + 24 < 0x19`，即在偏移 **+24** 处读长度字段并要求 ≥1，符合 IL2CPP `Il2CppArray` 头部（0x20 字节头 + 元素区）的布局。
- 真正的解析交给 `sub_3D73A0(src, count, out)`，它只是个 88 字节的薄包装，转发给**通用的 schema 驱动反序列化器**：

```c
sub_3D8334(&unk_21EFF0, 1520, args, 3, off_542ED0, 4, 160, 88)
//        schema描述符   大小       入参  字段表       字段数     元素记录大小
\```

即字段布局**不是硬编码偏移**，而是由描述符 `unk_21EFF0`（1520 字节）加字段回调表 `off_542ED0`（4 个字段）在运行时解释。字段回调本身是极薄的包装：

```c
sub_3D75B8(a1) { return sub_3D7380(*a1) & 1; }   // 取首字段并校验
sub_3D75E8(a1) { sub_3D73F8(*a1); return 0; }    // 取首字段
sub_3D7600 / sub_3D7624                           // 另两个字段
\```

元素记录大小 **88 字节 / 4 字段**，与解析输出缓冲区（`v144`，120 字节）量级吻合。
- 结果分类逻辑（`sub_28EB48`）：解析返回 `v128 > 0` 即 `preMatchData-resolved`；`v128 <= 0` 时，若长度 < 1 判 `empty`，否则扫描缓冲区是否为全 `-1`——全 `-1` 判 `empty`，出现非 `-1` 判 `unrecognized`。

**要拿到座位号与幽灵字段的确切偏移，需要读 `unk_21EFF0` 描述符表的字段偏移条目**，这比逐函数反编译更高效，留作后续。

#### 7.7.6 复查后仍然未定的部分

1. **`preMatchData` 描述符 `unk_21EFF0`（1520 字节）里 4 个字段的具体偏移与语义**——布局由 schema 表控制，未逐条展开。
2. **`GetMyPlayerModel` / `sub_2D76EC` 的角色**。在 resolved 分支里出现 `v131 = sub_2D76EC(atomic_load(&qword_564E38))`，即**帧回调路径也会去读 SelectHighScore 钩子捕获的那个对象**（`qword_564E38`）。这说明两条来源并非完全独立，preMatchData 路径会用捕获对象补充信息。具体补什么未展开。
3. **`sub_3D4B78` 里 `a1 <= 5` 那 6 个特性编号各自对应什么功能**——只知道 3 号控制 matchup 采集。

---

## 八、是否存在「修改概率」的方法

### 8.0 结论

**没有。所有与随机/概率相关的钩子都是只读观察器——照原参数调用原函数，照原值返回，不篡改任何一个随机结果。**

这可能会出乎意料，因为工具里确实有「指定海克斯」「指定重铸」这类看起来像在操控概率的功能。它们的实现方式是**检测 + 行动**，而不是改概率（见 8.4）。

### 8.1 逐个核对：概率相关钩子的返回值

对 `libdemo.so` 中全部 7 个与随机/概率有关的钩子处理器做了逐个反编译核对：

| 目标函数 | 处理器地址 | 大小 | 处理方式 | 是否改结果 |
|-|-|-|-|-|
| `FRandom_RandomIntMax` | `0x2F8BB0` | 92 B | `v4 = off_564F08(); return v4;` | **否** |
| `FRandom_InternalSample` | `0x2F8C0C` | 428 B | `v5 = off_564F10(a1,a2); return v5;` | **否** |
| `FRandUtils_RandWeightsListIndex` | `0x2FBC8C` | 204 B | `v2 = off_564F38(a1); return v2;` | **否** |
| `TAC_GenerateHeroListFromHeroPool` | `0x2F8DBC` | 3124 B | 单出口 `return v23 & 1;`，`v23` 为原函数返回值 | **否** |
| `SelectHeroVectorByUserLevel` | `0x2FA554` | 4416 B | 单出口尾调 `off_564F28(...)`，参数为原参数的副本 | **否** |
| `GetBadLuckProtectionV2`（保底） | `0x2FB6A8` | 1492 B | `v2 = off_564F30(a1); return v2;` | **否** |
| `RandomEquipmentByQuality` | `0x2FBF64` | 336 B | 原值返回 | **否** |
| `RandomEquipmentByQuality_WithJCC` | `0x2FC0B4` | 352 B | `v19 = off_564F48(...); return v19;` | **否** |

几个值得单独说明的细节：

**`FRandom_RandomIntMax`**（最短的一个，92 字节）最能说明设计意图：

```c
v4 = off_564F08();                        // 调原函数
v5 = sub_532F58(&unk_551B30);
if ( a3 && (*v5 & 1) == 0 )
    atomic_store(a3, &qword_561FD0);      // 只把上限 a3 缓存下来
return v4;                                // 原值返回
\```

它连返回值都不碰，只把「随机上限」参数存进自己的全局量，供预测逻辑参考。

**`SelectHeroVectorByUserLevel`**（等级概率表，最大的一个）起初让我怀疑：它的尾调用传的是 `v92, v31` 而不是 `a1, a2`。追进去发现 `v92 = a1`（`0x2fa65c`）、`v31 = a2`（`0x2fa8b0` 等三处），全是原参数的副本，只是借了局部变量传递。函数只有一个出口（第 977 行），且原样返回原函数结果。

**`_WithJCC` 后缀不代表改写。** `RandomEquipmentByQuality_WithJCC` 与 `RandomEquipmentByQuality` 是两个**不同的游戏方法**（各自有独立的 hook 点和原始函数保存槽 `off_564F48` / `off_564F40`），工具的处理器对两者一视同仁——都是调用后原值返回。后缀是游戏侧的命名差异，不是「被工具改过」。

### 8.2 观察容器机制：`byte_564A44` 标志位

工具确实下了不少功夫，但方向是**提高读取精度**而非改写。`TAC_GenerateHeroListFromHeroPool` 的处理器里：

```c
atomic_store(1u, &byte_564A44);     // 进入商店生成
v23 = off_564F18(...);              // 调原函数
atomic_store(0, &byte_564A44);      // 离开商店生成
\```

而 `FRandUtils_RandWeightsListIndex` 的处理器里正好检查这个标志：

```c
v2 = off_564F38(a1);
if ( (byte_564A44 & 1) == 0 )
    return v2;                       // 不在商店生成期 → 直接返回，不记录
// 在商店生成期 → 快照权重供预测
\```

`_WithJCC` 装备钩子里也有对称的一对 `atomic_store` 与 `v17`（「本次是工具发起的重铸」）标志。

这套设计的含义很清楚：**用一个跨钩子的共享标志位界定「现在是哪段业务」，只在该业务窗口内采集数据**，其余时刻直接放行。这是采集器的做法，不是改写器的做法——改写器不需要知道「现在处于哪个业务阶段」。

### 8.3 全库唯一的写内存路径

为排除「处理器原值返回、但在别处偷偷改状态」的可能，我把 `libdemo.so` 里所有原始 `syscall` 调用点枚举了一遍：

| syscall | 编号 | 次数 | 用途 |
|-|-|-|-|
| `process_vm_readv` | 270 (0x10E) | 249 | 安全内存可读性探测（不是真的读数据） |
| `gettid` | 178 (0xB2) | 6 | 线程标识 |
| `clock_gettime` | 113 (0x71) | 4 | 计时 |
| `openat` / `read` / `close` / `write` | 56/63/57/61 | 多处 | 文件与 IPC |
| **`process_vm_writev`** | **271 (0x10F)** | **1** | **唯一的直接内存写入** |

只有一处 `process_vm_writev`，在 `sub_3703DC`：

```c
unsigned __int64 sub_3703DC(result, a2, a3)   // 目标地址, 源数据, 长度
{
  if ( result >> 58 < 0x2D ) {                 // 普通地址
      v8 = -sysconf(40);
      mprotect(result & v8, ..., 7);           // 改成 RWX
      return memcpy(result, a2, a3);           // 直接写
  }
  // 高地址 → 走进程内存写入
  v5 = dword_55D328 ?: getpid();               // 注意：目标是 getpid()，即自身
  return syscall(271, v5, v13, 1, v12, 1, 0);
}
\```

两条分支的目标都是 **`getpid()`，即自身进程**。这是一个通用的「安全写入」原语（先 `mprotect` 再写），不是跨进程注入。

它的调用链只有两条：

1. **装钩引擎**——inline hook 需要改写被钩函数的机器码，这是必然的写入。
2. **`HeroRoot_Update` → `sub_284CB0` → `sub_36B954`**——而 `sub_36B954` 是**卖牌 / 换位执行引擎**，其日志字符串暴露了身份：

```python
sell (%d,%d,a%d) submitted          sell done submitted=%d confirmed=%d skipped=%d
sell (%d,%d,a%d) skipped by game rule
selective sell rejected: hero identity changed
swap (%d,%d)->(%d,%d) ret=%d        swap skip: no move primitive
\```

即写内存的第二个用途是**棋盘操作**（一键卖牌、一键换位），对应第七节之外的 `chess.sell` / `chess.mirror` 类命令。

**结论：全库有写内存的能力，但写入目标是代码段（装钩）与棋盘状态（卖牌/换位），没有一处指向随机数生成器或概率表。**

### 8.4 那「指定海克斯 / 指定重铸」是怎么实现的

答案是**检测 + 行动**，而不是操控结果：

1. 随机源钩子（`FRandUtils_RandWeightsListIndex`、`FRandom_InternalSample`、`RandomEquipmentByQuality_WithJCC` 等）在游戏生成结果时**读走结果**；
2. 工具把它与你勾选的「指定」项比对；
3. 命中后，通过被钩的 `WriteInput` 或 `sub_36B954` 的卖牌/换位原语，**下发一次合法的游戏操作**，并弹提示。

这与作者自己的功能描述完全吻合——原文写的是「指定一件装备，**用重铸器锤出它时**自动出手并提示」（命中即出手），而不是「锤出你指定的装备」。海克斯那条的措辞同样是「**预测命中时**提示对应卡位」。

顺带说明一个容易混淆的边界：**工具确实会修改游戏状态**（卖牌、换位、拿牌、刷新、重铸都是真操作），只是走的是游戏自己的操作接口，在引擎视角与玩家操作无异。这与「修改概率」是两回事——前者是操作，后者是篡改随机源，本样本做的是前者。

## 附件

- [libdemo.so](../attachments/292938/libdemo.so) — 5.33MB，12次下载

---

# 回复

## 回复 by mb_ldbucrik (#2)

感谢分享

## 回复 by Imxz (#3)

tql

## 回复 by iBa0 (#4)

666

## 回复 by xingbing (#5)

感谢分享

## 回复 by mb_jnmxfjku (#6)

666

## 回复 by mb_dmryhnwz (#7)

666

## 回复 by 啊你好哇123 (#8)

学习学习

## 回复 by 馨禧 (#9)

666

## 回复 by 卑鄙兔 (#10)

6

## 回复 by mb_vymbqugn (#11)

sadas

## 回复 by Gryffindoss (#12)

123123

## 回复 by 珍惜Any (#13)

kk

## 回复 by mb_rztmbvgb (#14)

666
