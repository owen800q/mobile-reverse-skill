---
title: '[原创]飞车手游Java层分析到Xposed模块实战'
url: https://bbs.kanxue.com/thread-288692.htm
tid: 288692
author: JSnow
date: '2025-10-06'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-08T10:43:03+00:00'
replies: 22
---

# 祝大家中秋国庆快乐！

上一篇帖子：[飞车手游分析 & 加速，秒通关实现](https://bbs.kanxue.com/thread-287859.htm)

大家对我上次的使用修改器修改游戏的帖子似乎比较感兴趣，本帖将带大家深入分析这个飞车小游戏并且编写快捷易用的Xposed模块

上一篇帖子我们简单使用修改器修改了这个游戏，但是碰到了切屏就失效，搜索数据浪费时间等问题，这篇帖子我们使用Xposed模块来解决这些问题，成品放在附件里面了

最终效果：速度锁400，积分赛66666分

https://b23.tv/iZuCg8a

## 初步思路

上一期我们找到了这个游戏的速度地址，但是每一局都要重新搜索，修改，有时候一局可能还需要搜索修改多次，会显得很麻烦。

~~本期的受害者依旧是 ↓↓↓~~

**AmazingGame！！！**

 ![image](https://bbs.kanxue.com/upload/attach/202510/1033854_NQB2MTXVCGNFX6F.webp)

我们提到过一个想法就是Hook撞墙的代码来获取对象数据，但是这里的主要撞墙逻辑并不是传入实例后调方法的形式，所以想Hook方法参数，就只能hook玩家之间的碰撞了

在Java层我们是无法像Native层一样下访问断点追踪的，因为Java为了安全性避免了直接的内存操作，而且是运行环境也是ART虚拟机，即使下断点，访问点也都是在Code System段，所以很难通过地址定位类信息，而且搜了几天几乎没找到任何相关的追踪手段，根据我的思考和探索，有以下初步的思路

- 直接分析Java层代码
	- 优点：能够应对各种奇奇怪怪的问题
	- 缺点：时间成本高，在大型游戏中难度大
- 使用Android Studio附带SDK tools提供的monitor工具分析函数调用，来找到撞墙逻辑代码分析
	- 优点：分析速度快，能够快速定位关键方法
	- 缺点：如果撞墙不是一个方法来实现的，那就会被误导到一大堆乱七八糟的方法里面去
- Frida通过遍历前后地址，尝试解析类，或者枚举所有实例信息后进行地址比对
	- 优点：快，便捷
	- 缺点：~~我不会~~
- **Java Heap Dump + GGlua**
	- 优点：相比其他方法优点非常明显，速度快，便捷（算是frida想法手动实现）

各位师傅有更好的办法浇浇我

## 从对象字段到类的寻找

### Java层逆向分析

没有进行Java层的混淆，比较适合萌新体质（）

我们首先尝试搜索`wall`，`speed`，`player`等关键信息，这里我选择从`KeyEvent`入手

在Android开发中`android.view.KeyEvent`为玩家操作游戏提供了支持，也会为我们提供一些关键信息

我们在这里的回调函数中很轻松的找到了对我们对象状态的判断，很明显我们的游戏对局对象是`inGame`，其中存储着我们在这局游戏中的状态等信息

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_Y8NMC3NW9AHJ8KZ.webp)

还发现了可爱的flag（？）

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_BRP3DDMJFYR62MD.webp)

另一个方法也印证了这一点

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_NRXBSP6AGRNXSVJ.webp)

我们可以进入到`InGame`这个类看看，发现了我们上次对内存中状态码的初步判断是正确的

发现了`public static Vaisseau player = new Vaisseau();`，结合后面的代码，说明玩家是一个`Vaisseau`类的实例

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_4BHXU7BJ84XTU8J.webp)

我们的目标是获取速度信息，我们在类里面搜索speed找到了对应的信息，这似乎是一个列表，这里设置了敌人的`defaultParams`（默认参数）我们修改之后发现敌人不能动了，不过这不是我们分析的重点

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_V26FW34J8W58GQ6.webp)

结合游戏玩法，很明显这是根据敌人选择不同的基础速率，而且float类型也符合我们对速度的判断

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_6ST6JQGENJ9J9W9.webp)

但是这并不是我们想要的数据，我们继续分析，来到了这里，发现这里是我们游戏角色运动的逻辑，都在`doPhysics`方法中

玩家加速逻辑（这里可以看出来`player.param[3]`是角色速度上限）

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_JV726JNRRNY8PYN.webp)

玩家之间碰撞的逻辑检测，其中是在扣除`vzb`这个变量数据，所以我们合理认为`vzb`是速度信息

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_HHRBRB7XEVVVGT9.webp)

所以接下来我们来到角色类(`Vaisseau`类)实例中，通过查找速度的交叉引用寻找到了碰撞逻辑

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_KAHPUKU5YT7KKTW.webp)

第二关和第五关也找到判断玩家是否在赛道上的逻辑了

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_TTCZNCTZH5BZEEJ.webp)

这里是玩家的速度变化逻辑

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_C6427J9SF8JA8D9.webp)

这里分析了一下游戏的`vxb`,`vyb`,`vzb`，三者是xyz三个方向的速度

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_G8S9VXXG2PJD8QK.webp)

到这里其实我们关于游戏的基本信息都分析出来了，这是最直接最暴力的方法，虽然在大型，有混淆的游戏中花费的时间成本会大幅提高，但能应对各种乱七八糟的情况

### monitor工具分析函数调用（不可行）

其实到这里我们发现我们使用monitor并不可行，因为这里的撞墙并不是通过调用一个方法实现的，而是直接进行if判断后加减，我们如果尝试这种方法，很有可能会被误导到各种角度坐标计算方法中去，从而无法自拔，所以这只能作为一种技巧使用

### Frida搜索类实例（未实现）

#### 获取所有类实例的地址比对

实现不了的关键点在于无法获取类实例的地址，也没有找到相关的api

来来回回研究了半天，不会获取类实例的地址，寄了，半成品脚本放在这里，师傅们有建议的话可以提一下，谢谢喵

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687 | `function` `find_obj(){``Java.perform(``function``() {``// 我们使用修改器获得到的Java实例中速度字段的地址``var` `targetAddress = ptr(``"0x1390013c"``);``console.log(``"目标地址: "` `+ targetAddress);` `// 获取当前加载的所有类``console.log(``"开始搜索类实例..."``);` `var` `processedClasses =` `new` `Set();` `// 使用Java.enumerateLoadedClasses获取所有已加载类``Java.enumerateLoadedClasses({``onMatch:` `function``(className) {``// 只搜索App内的类，避免系统类``if` `(!className.startsWith(``"net.osaris"``) \|\|``!className.startsWith(``"com.pangbai."``) \|\|``!className.startsWith(``"adrt"``)``) {``return``;``}` `try` `{``if` `(processedClasses.has(className))` `return``;``processedClasses.add(className);` `var` `javaClass = Java.use(className);` `// 搜索该类的所有实例``Java.choose(className, {``onMatch:` `function``(instance) {``try` `{``console.log(``"检查实例: "` `+ instance);``console.log(``"addr: "` `+ instance.$handle);``// 卡在这里了``// 获取实例的地址（这里读不出来，抛出异常）``var` `instanceAddr = ptr(instance.$handle);``console.log(``"实例地址: "` `+ instanceAddr);` `var` `maxObjectSize = 1024;``var` `minAddr = instanceAddr;``var` `maxAddr = instanceAddr.add(maxObjectSize);` `// 检查目标地址是否在该范围内``if` `(targetAddress.compare(minAddr) >= 0 &&` `targetAddress.compare(maxAddr) <= 0) {``console.log(``"找到可能匹配的对象!"``);``console.log(``"类名: "` `+ className);``console.log(``"实例地址: "` `+ instanceAddr);``console.log(``"字段可能偏移量: "` `+ targetAddress.sub(instanceAddr));` `// 尝试打印对象详情``console.log(``"对象信息: "` `+ instance.toString());` `// 尝试列出字段``var` `clazz = instance.getClass();``var` `fields = clazz.getDeclaredFields();``console.log(``"类字段数量: "` `+ fields.length);``for` `(``var` `i = 0; i < fields.length; i++) {``fields[i].setAccessible(``true``);``console.log(``"字段: "` `+ fields[i].getName() +` `", 类型: "` `+ fields[i].getType());``}``}``}` `catch` `(e) {``console.error(``"实例检查错误: "` `+ e);``}``return` `"continue"``;``},``onComplete:` `function``() {` `}``});``}` `catch` `(e) {``console.error(``"类处理错误: "` `+ e);``}``},``onComplete:` `function``() {``console.log(``"所有类搜索完成"``);``}``});` `console.log(``"搜索已启动，等待结果..."``);``});``}` `setTimeout(find_obj, 1000);` |
|-|-|

#### 尝试在附近解析类

注入就崩了，可能是解析方法错了？~~也中道崩殂了~~

| 12345678910111213141516171819202122232425262728293031323334353637383940414243 | `function` `find_obj()``{``Java.perform(``function``() {` `var` `fieldAddress = ptr(``"0x134EB318"``);` `console.log(``"已知字段地址: "` `+ fieldAddress);` `var` `searchRange = 256;` `// 搜索范围` `// 从字段地址向前搜索``for` `(``var` `offset = 0; offset < searchRange; offset += 8) {``var` `potentialHeaderAddr = ptr(fieldAddress).sub(offset);` `try` `{``var` `value = Memory.readPointer(potentialHeaderAddr);``console.log(potentialHeaderAddr +` `" -> "` `+ value);` `// 尝试将读取的值作为类引用``try` `{``// 尝试将该值作为对象或类信息的引用``var` `possibleClass = Java.cast(value, Java.use(``"java.lang.Class"``));``console.log(``"可能的类引用: "` `+ potentialHeaderAddr +` `" -> "` `+ possibleClass.getName());``console.log(``"找到可能的对象头部，距离字段偏移: "` `+ offset +` `" 字节"``);``}` `catch``(e) {``// 尝试作为对象引用``try` `{``var` `possibleObj = Java.cast(value, Java.use(``"java.lang.Object"``));``console.log(``"可能的对象引用: "` `+ potentialHeaderAddr +` `" -> "` `+ possibleObj.getClass().getName());``}` `catch``(e2) {``console.log(potentialHeaderAddr +` `" -> [无法转换为对象或类]"``);``}``}``}` `catch``(e) {``console.log(potentialHeaderAddr +` `" -> [无法读取]"``);``}``}`  `});``}` `setTimeout(find_obj, 1000);` |
|-|-|

### Java Heap Dump + GGlua定位

Java虚拟机如果创建了这些类，肯定是需要一个标识用于管理他们的，但是单纯的使用Java Heap Dump的话我们很难确定实例的头部究竟在哪里，但是GGlua脚本就为我们很好的解决了这个问题

我们使用Android Studio的Profiler这个工具来dump堆信息

[官方文档](https://developer.android.google.cn/studio/profile?hl=zh-cn)

首先根据上一篇帖子，我们知道了这个值在Java Heap中的地址

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_6SNBXC5BYQJBQBM.webp)

#### GGlua脚本寻找信息

首先我们要思考一个Java Heap上的对象，系统是如何判断它属于哪个类呢？其实就是根据对象头部的指针

就像身份证上的“籍贯”，告诉JVM这个对象是哪个类的实例

[Java的对象头：原理与源码详解](https://blog.csdn.net/goTsHgo/article/details/147784540)

所以我们在这里可以看到类实例头部，会有一个指针，这个指针是指向`J`内存的

**J (JIT Memory)**

- **描述**: JIT（Just-In-Time）编译生成的内存区域，通常用于动态编译和执行代码。
- **用途**: 存储动态生成的可执行代码，特别是Java或Android应用的JIT编译结果。
- **特点**: 可执行代码，可能是读写混合属性。

所以我们可以借助这一点来使用GGlua来为我们自动确定类的头部信息

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_3XUHAVUHV3G4HQ3.webp)

我们使用GG修改器执行如下GGlua脚本

\```
function main()
    local m={
    'Find ClassAddr with address',
    'Exit Script'
    }
    local g=gg.choice(m,nil,'Find ClassAddr Script')
    if g==1 then F1() end
    if g==2 then os.exit() end
    xgck=-1
end

function F1()
    local input = gg.prompt({"请输入十六进制地址（无需输入0x）:"},{""},{"text"})
    if input == nil then return end  -- 结束脚本
    local base_addr = tonumber(input[1], 16)
    if base_addr == nil then
        gg.toast("无效地址，请输入有效的十六进制地址")
        return
    end

    gg.toast(string.format("Base Address: 0x%X", base_addr))

    --每次减少4个字节，依次向上寻找，并检查指针是否指向Java内存区域
    local found = false
    -- 这里设置0x200一般够用了，可以根据需求修改这里
    for i=0,0x200,4 do
        --读取该地址处的值
        local curr_addr = base_addr - i
        local result = gg.getValues({{address = curr_addr, flags = gg.TYPE_QWORD}})
        local pointer = result[1].value

        --检查指针是否在Java内存区域内
        local inJavaRegion = false

        -- 创建一个包含 pointer 地址的表
        local pointerInfo = {{address = pointer, flags = gg.TYPE_DWORD}}
        -- 获取内存区域
        local valueRange = gg.getValuesRange(pointerInfo)
        if valueRange ~= nil then
            -- 检查是否为Java区域
            if valueRange[1] == "J" then
                gg.toast(string.format("找到Java Class! Java Heap地址: 0x%X 指向: 0x%X", curr_addr, pointer))
                gg.sleep(1000)
                -- 将得到的curr_addr写入到/storage/emulated/0/JSnow_FindClass.txt文件中
                local file = io.open("/storage/emulated/0/JSnow_FindClass.txt", "a")
                if file then
                    file:write(string.format("0x%X\n", curr_addr))
                    file:close()
                    gg.toast("地址已保存到 /storage/emulated/0/JSnow_FindClass.txt")
                    gg.sleep(1000)
                else
                    gg.toast("无法打开文件进行写入")
                    gg.sleep(1000)
                end

                found = true
                inJavaRegion = true
            else
                gg.toast(string.format("指针在非Java区域 (%s)", valueRange[1]))
            end
        end
    end

    if not found then
        gg.toast("未找到指向Java区域的指针")
    end
end

--主循环
xgck = -1
while true do
    if gg.isVisible(true) then
        xgck=1
        --gg.setVisible(false)  -- 隐藏界面游戏会持续运行，不方便我们提取数据
    end
    if xgck==1 then
        main()
        xgck = -1
    end
    gg.sleep(100)
end
\```

我们在`/storage/emulated/0/JSnow_FindClass.txt`中可以得到类实例头部的地址

#### Java Heap Dump

然后我们使用Android Studio自带的Profiler功能将此时的Java Heap整个Dump下来

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_MAWV9K3TE3C4DD5.webp)

根据官方文档，我们需要使用SDK工具将 `.hprof` 文件从 Android 格式转换为 Java SE `.hprof` 文件格式

\```
hprof-conv .\memory-20250920T100450.hprof dest.hprof
\```

接下来使用MAT（MemoryAnalyzer）工具分析我们输出的堆转储文件

我们根据GGlua脚本输出得到的地址搜索，很快就在找到了这个类，然后我们就可以直接快速定位关键类进行Java层分析了，相比我们在Java层分析下来这种方法的效率明显更高

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_JQY2F2DR3KQBER3.webp)

## Frida Hook测试

所以我们可以简单使用frida写出一个作弊脚本，这里只是简单试一下效果，所以没有优化

如果`-UF`指定顶层会导致hook的是修改器

\```
frida -U -l ./hook.js -n AmazingGame
\```

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950 | `function` `hook(rounds, modules)``{``var` `i = 0``while` `(i < rounds) {``i += 1``Java.perform(``function` `() {``var` `classes = Java.enumerateLoadedClassesSync();``var` `targets = classes.filter(``function` `(cls) {``// 过滤出我们的游戏角色实例类``return` `cls.startsWith(``"net.osaris.turbofly.models.Vaisseau"``)``});` `console.log(``"匹配到的类及其实例："``);``targets.forEach(``function` `(clsName) {``try` `{``Java.choose(clsName, {``// 每找到一个实例就会调用这个回调函数，修改所有的实例的 vzb 字段值``onMatch:` `function` `(instance) {``console.log(``"找到实例: "` `+ instance.toString());``if` `(modules == 1) {``instance.vzb.value = 20;` `// 修改 vzb 字段的值``console.log(``"vzb 值: "` `+ instance.vzb.value);``}``else` `if` `(modules == 2) {``instance.vyb.value = 20;``console.log(``"vyb 值: "` `+ instance.vyb.value);``}``else` `if` `(modules == 3) {``instance.vzb.value = 20;``instance.vyb.value = 20;``console.log(``"vzb 值: "` `+ instance.vzb.value);``console.log(``"vyb 值: "` `+ instance.vyb.value);``}``},``onComplete:` `function` `() {``console.log(clsName +` `" 实例枚举完成"``);``}``});``}` `catch` `(e) {``console.log(``"无法处理类: "` `+ clsName +` `"，原因: "` `+ e);``}``});``});``}``}` `// 参数填写我们想hook的次数``// 因为游戏中这个实例的速度会被不断修改，而while(true)会导致hook无法退出``// 1是加速，2是飞天，3是两者都有``setTimeout(hook(10, 1), 1000);` |
|-|-|

hook发现的确有效，说明我们寻找的是正确的，但是我们要寻找合适的Hook点，因为这种方法会导致**所有赛车**都加速，达不到获胜的目的

但是我们不可能每次打开游戏都启动frida，连接usb，会显得比较麻烦，~~而且连着个电脑打游戏总会不得劲~~（但是听说有一个叫算法助手的app可以便捷启动frida脚本）

## 编写Xposed模块

我们新建项目之后，需要新建lib目录**（不是libs）**下加入我们的Xposed的jar包，为我们提供代码补全，方便我们调用api，然后在main目录下新建assets目录，新建`xposed_init`文件，这里用于声明Xposed的入口点，我这里是`com.JSnow.cheatmodule.XposedCheatModule`，所以就向其中添加`com.JSnow.cheatmodule.XposedCheatModule`这一串内容就可以了

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_WQADHGZRUWBRTKZ.webp)

为了减小app体积，我们需要在`build.gradle`文件中添加`compileOnly`，让jar包不被打包到我们的app中

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_ZBXW92FTC55NMEB.webp)

然后我们就可以在我们指定的入口点开始写Hook了

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/1033854_MAHESG3ZHEY96Z7.webp)

分析了一圈，尝试了不少Hook点，感觉还是绘制的方法Hook起来体验最好，而且player对象是没有看到作为参数传递到某个方法中的，所以就只能利用反射获取这个实例了

现在大家都喜欢用Lsposed模块，Lsposed模块是兼容了Xposed模块的，**加载后记得勾选游戏和系统框架**
因为xposed的原理是替换系统的`app_process`文件，所以不重启是无法生效的

核心代码：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849 | `package` `com.JSnow.cheatmodule;`  `import` `de.robv.android.xposed.IXposedHookLoadPackage;``import` `de.robv.android.xposed.XC_MethodHook;``import` `de.robv.android.xposed.XposedBridge;``import` `de.robv.android.xposed.XposedHelpers;``import` `de.robv.android.xposed.callbacks.XC_LoadPackage;` `public` `class` `XposedCheatModule` `implements` `IXposedHookLoadPackage {``static` `int` `state;``static` `Object player;``@Override``public` `void` `handleLoadPackage(XC_LoadPackage.LoadPackageParam loadPackageParam)` `throws` `Throwable {``if``(loadPackageParam.packageName.equals(``"com.pangbai.projectm"``)){` `XposedHelpers.findAndHookMethod(``"net.osaris.turbofly.InGame"``, loadPackageParam.classLoader,` `"drawFrame"``,` `new` `XC_MethodHook() {``@Override``protected` `void` `afterHookedMethod(MethodHookParam param)` `throws` `Throwable {``super``.afterHookedMethod(param);``// 通过反射获取InGame对象的字段``player = XposedHelpers.getObjectField(param.thisObject,` `"player"``);``XposedBridge.log(``"player："` `+ player);``XposedBridge.log(``"player vzb："` `+ XposedHelpers.getObjectField(player,` `"vzb"``));``// 修改分数和速度字段的值``// 这里本来是打算加状态判断的，但是会影响切屏后的生效，所以就不加了``XposedHelpers.setObjectField(player,` `"vzb"``,` `2``.0f);``XposedHelpers.setObjectField(param.thisObject,` `"scoreInfini"``, (``int``)``666666``);``// log信息``XposedBridge.log(``"player vzb："` `+ XposedHelpers.getObjectField(player,` `"vzb"``));``}``});` `XposedHelpers.findAndHookMethod(``"net.osaris.turbofly.InGame"``, loadPackageParam.classLoader,` `"getState"``,` `new` `XC_MethodHook() {``@Override``protected` `void` `afterHookedMethod(MethodHookParam param)` `throws` `Throwable {``super``.afterHookedMethod(param);``// 监听游戏状态``if``(state != (``int``)param.getResult() && state <=` `3``) {``state = (``int``) param.getResult();``XposedBridge.log(``"State："` `+ state);``}``}``});``}`  `}``}` |
|-|-|

最终效果：https://b23.tv/iZuCg8a
(~~其它地方都不能点击即看，最后还是b站收留了我的视频~~)

成品和源码都打包了一份，感兴趣的师傅可以拿来玩玩，游戏本体下载：

https://github.com/CTF-Archives/2024-newstar/releases/download/v1.0.0/ns24_misc.zip

上传的附件：
- app-debug.apk

（3.56MB，19次下载）
- CheatModule.zip

（127.18kb，18次下载）

---

# 回复

## 回复 by SomeMx (#2)

*2025-10-6 21:25*

过来瞧瞧

## 回复 by mb_dmryhnwz (#3)

*2025-10-6 23:32*

666

## 回复 by Imxz (#4)

*2025-10-7 08:56*

tql

## 回复 by mb_xflcgdik (#5)

*2025-10-7 09:02*

66

## 回复 by mb_nhphjyjb (#6)

*2025-10-7 15:28*

666

## 回复 by 希梦☆奈何 (#7)

*2025-10-7 22:10*

路过学习

## 回复 by 9494 (#8)

*2025-10-7 22:31*

666

## 回复 by mb_qimctavn (#9)

*2025-10-9 10:12*

6

## 回复 by Qc101 (#10)

*2025-10-10 08:35*

666

## 回复 by Met三二 (#11)

*2025-10-10 09:09*

6

## 回复 by mb_xjdhrmck (#12)

*2025-10-10 10:23*

6666

## 回复 by 智取棋 (#13)

*2025-10-10 11:48*

666

## 回复 by wx_插曲 (#14)

*2025-10-10 12:48*

666

## 回复 by wx_归期_856 (#15)

*2025-10-10 13:58*

666

## 回复 by 超级卡卡罗特 (#16)

*2025-10-10 15:23*

3+3

## 回复 by fangliangz (#17)

*2025-10-13 09:54*

666

## 回复 by Ms135 (#18)

*2025-10-13 17:33*

666

## 回复 by mb_lghhumnu (#19)

*2025-10-13 18:22*

谢谢分享

## 回复 by 我是小奥 (#20)

*2025-11-17 23:17*

谢谢分享

## 回复 by kuku8888 (#21)

*2025-11-18 09:09*

666学习了

## 回复 by mb_pxpmsjtj (#22)

*2025-11-18 09:59*

666

## 回复 by 小迷糊ddd (#23)

*2026-4-7 09:18*

感谢分享，学习一下。
