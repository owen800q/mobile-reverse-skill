---
title: '[原创]（萌新总结）Android渗透测试指引（一）：总述②'
url: https://bbs.kanxue.com/thread-277639.htm
tid: 277639
author: mb_rdzyrhpc
date: '2023-06-15'
tags: [Android安全, 原创, 基础理论]
crawled_at: '2026-07-31T14:44:30+08:00'
replies: 1
---

第二部分 由于帖子超长只能分段发了

还是那句话，萌新总结，如有错误请轻喷，我受不了网络暴力~_~

# 6 使用Frida

由于lamda中自带了frida，本节分为使用lamda与不使用lamda两种方式讲解（可惜不能兼容真机模拟器，不然是想默认使用lamda讲解的）

## 6.1 安装

Frida与Drozer一样，也是基于python的分布式框架。分为服务端与客户端两个。客户端（本机）使用pip安装：

pip install frida

pip install frida-tools

pip install objection

服务端（安装过lamda的手机**不需要**安装，也就是可以跳过下面的内容直接到使用部分）访问github页面选择下载：[https://github.com/frida/frida/](https://github.com/frida/frida/releases)

服务端和客户端的版本要一致，由于pip安装时会自动选择版本，我们这里以客户端版本为准。

使用

pip list | findstr frida

查看frida的版本，adb命令行中使用

getprop ro.product.cpu.abi

获取架构，然后选择对应的frida-server，如：

![image](https://bbs.kanxue.com/upload/attach/202306/JMX6CWJ4ST53M7F.jpg)

![image](https://bbs.kanxue.com/upload/attach/202306/VNWV8W29KBZ2PV4.jpg)

![image](https://bbs.kanxue.com/upload/attach/202402/93_ZE2G7AFGQD3DWFR.webp)

解压文件，adb push到/data/local/tmp，对frida-server-xxx文件chmod 777然后执行即可。

### 6.1.1 lamda使用frida的适配

以当前最新的lamda版本（3.150）为例。首先，需要运行命令：

pip3 install -U --force-reinstall lamda[full]

然后，确定frida版本为15.X，frida-tools为12.1.X。

否则将会出现frida命令执行反复横跳，一会成功一会提示版本不匹配的问题。

## 6.2 基础使用

使用lamda中的frida与普通情况相似，但是需要在每一条frida命令下添加参数：-H 192.168.0.2:65000（ip请改成手机ip），而原生frida需要让adb转发frida端口出来：

adb forward tcp:27043 tcp:27043

adb forward tcp:27042 tcp:27042

在已经连接adb的情况下，cmd使用：

frida-ps -U

来进行一个热身。这个命令显示的是手机进程列表。

![image](https://bbs.kanxue.com/upload/attach/202402/93_WWHUMA3MSXE757M.webp)

使用命令（如果程序太多，考虑使用frida-ps -Ua，它只会显示运行中APK）

frida-ps -Uai

获取当前运行所有APK的包名：

![image](https://bbs.kanxue.com/upload/attach/202402/93_5T5PRUHHFNG34RC.webp)

进入frida-shell：

frida -H 192.168.3.61:65000 -f com.busuu.android.enc

![image](https://bbs.kanxue.com/upload/attach/202402/93_5EMTS7XRF26MK9B.webp)

### 6.2.1 lamda中frida的另一种使用方式

即在python脚本中进行。我给一个示例代码：

```
import lamda
from lamda.client import *
device=Device("192.168.3.61")
fridar=device.frida
#以下使用frida命令
fridar.enumerate_processes() #一个示例，枚举进程
```

# 7 使用Jadx进行反编译

这个东西很容易安装，就不讲了。

安装后直接将要反编译的apk文件拖进程序即可：

![image](https://bbs.kanxue.com/upload/attach/202402/93_Y7RJFFGCB43M6HA.webp)

不过根据使用经验，还有一些额外的设置推荐赠送：

·         首选项里打开反混淆，方便追踪方法

·         如果要搜索被混淆过的、被编码的，反正很长的文件，最好复制出来在第三方编辑器中查找，不然很容易卡死

## 7.1 先谈谈APK本身

安卓应用说来说去其实就是基于google android框架下的一类代码打包成的可运行包。与web应用不同，这些包一般都经过了编译才能在目标平台运行（想象一下jar包，里面的代码就是从.java文件编译成了.class字节码，APK可以看做大号带资源的jar包），我们是没办法直接看到源代码的。

用解压缩文件打开一个apk包可以看到其结构如下：

![image](https://bbs.kanxue.com/upload/attach/202402/93_2TYRFUQF53KZMPX.webp)

如果读者做过android开发，可以发现apk的结构和它作为源代码的结构基本类似，只是明文代码变成了编译后的文件。

我拿一个android工程的目录做例子，进行对比：

![image](https://bbs.kanxue.com/upload/attach/202402/93_77AH4N8FWAYPXYN.webp)

assets文件、res文件、AndroidManifest.xml保持不变，java文件夹中的源代码包被放在主目录，META-INF文件夹为签名。多出来的文件为.dex文件与.arsc文件。前者为Android原生的可执行文件（当作安卓上的exe），后者为资源映射文件。

## 7.2. Jadx+Frida 进行Hook

最新版本中，可以右键选择函数，然后复制为frida片段（在反混淆开启时此选项生成的代码是**错误**的）：

![image](https://bbs.kanxue.com/upload/attach/202402/93_EM3G5JYHYNSQZWS.webp)

不过我更推荐自己写。

我们以函数getLevels为例（获取用户等级）：

![image](https://bbs.kanxue.com/upload/attach/202402/93_MDDCFJ63WTFAZE4.webp)

先找到其类名和函数名。然后对照原函数写原始Hook：

```
Java.perform(function(){ //当作主函数
    var Course=Java.use('com.busuu.android.api.course.model.ApiCourse'); //这句获取类
    Course.getLevels.implementation=function(){ //这里开始是Hook函数，前面的getLevels为要Hook的函数名
        console.log("Hook start");
        var level=this.getLevels(); //获取下返回值
        console.log(level.toString());
        return level; //返回函数执行结果，否则这就不是一个纯正的Hook了
    }
})
```

然后我们再写一个python脚本，使frida挂上Hook：

```
import frida,sys

appPacknName = "com.busuu.android.enc" #请填写对应要调试APK的包名
scriptFile = "1.js" #JS文件名
HOST="192.168.3.61:65000" #frida 位置

# 输出日志的回调方法
def on_message(message, data):
    if message['type'] == 'send':
        print("[*] {0}".format(message['payload']))
    else:
        print(message)

manager = frida.get_device_manager()
device = manager.add_remote_device(HOST)
# spawn模式,找到目标包名并重启,在启动前注入脚本
pid = device.spawn([appPacknName])
session = device.attach(pid)
device.resume(pid) #以上两行的顺序不能错

with open(scriptFile, encoding='UTF-8') as f :
    script = session.create_script(f.read())

script.on("message", on_message)
script.load()   #把js代码注入到目标应用中
#设置一直监听
sys.stdin.read()
```

运行此脚本，frida会自动重启APK并挂上Hook。执行效果如下：

![image](https://bbs.kanxue.com/upload/attach/202402/93_FGSKH98NH3UC3P2.webp)

---

# 回复

## 回复 by 秋狝 (#2)

*2023-6-16 09:12*

感谢分享
