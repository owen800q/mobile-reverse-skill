---
title: '[讨论]我发布的hookui xposed插件 用ai mcp hook的文章咋没引起轰动啊这是为啥'
url: https://bbs.kanxue.com/thread-288839.htm
tid: 288839
author: 情迁
date: '2025-10-17'
tags: [Android安全, 讨论, 逆向分析, 混淆加固, HOOK注入, 工具脚本]
crawled_at: '2026-08-08T10:39:45+00:00'
replies: 14
---

[hookui xposed插件 支持mcp能力后逆向分析不要太简单 - 简书](https://www.jianshu.com/p/2e51acfc1a12)

https://www.jianshu.com/p/2e51acfc1a12

[[下载]xposed插件 HOOKUI 2.1已发布支持 直接mcp调用 ai控制 本地内存搜索-Android安全-看雪论坛-安全社区|非营利性质技术交流社区](https://bbs.kanxue.com/thread-288827.htm)

而且这个 只需要 手机和  ai 软件 或者 任意能连sse mcp的都行啊. 都不需要专业的能力甚至能无需脱壳,因为是动态分析的. 不需要解包代码了都

提一嘴,效果不好,不是mcp不行,而是 ai 比如cherry studio我试过完全和claude code没法比,甚至还让我提供是啥应用,实际上 是不需要的,

![image](https://bbs.kanxue.com/upload/attach/202510/769855_8ASZG8TTFYDNFE7.webp)

都能直接滤清整个逻辑了, ,注意,是不需要用 任何提取apk的工具纯运行后直接分析的.

![image](https://bbs.kanxue.com/upload/attach/202510/769855_ZH7TQ7NU26Q2XV2.webp)

---

# 回复

## 回复 by k4y0z (#2)

*2025-10-17 18:19*

666

## 回复 by 简单的简单 (#3)

*2025-10-18 00:36*

岂不知天下英雄如过江之鲫????

## 回复 by mb_rjdrqvpa (#4)

*2025-10-18 00:48*

使用未混淆的测试demo，没什么价值，人工分析也能得出结论，实在不行，复制给ai分析也是一样的
你找个top app，演示分析难的算法，实战帖一出，大家都能看到价值

## 回复 by 情迁 (#5)

*2025-10-18 10:47*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rjdrqvpa](https://bbs.kanxue.com/user-932635.htm)
>
>  使用未混淆的测试demo，没什么价值，人工分析也能得出结论，实在不行，复制给ai分析也是一样的
> 你找个top app，演示分析难的算法，实战帖一出，大家都能看到价值
>
>

首先,这是给不会写代码的人用的,以及不想解包的人快速使用的,至于价值 是挖掘的.  主要的价值在于ai 快速提取数据,你复制ai一样的,那  网页版ai写代码和 claude code写代码是一样吗?后者不需要打开开发工具不需要粘贴,能一样吗?我不认同你的观点 ,

## 回复 by 情迁 (#6)

*2025-10-18 10:51*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rjdrqvpa](https://bbs.kanxue.com/user-932635.htm)
>
>  使用未混淆的测试demo，没什么价值，人工分析也能得出结论，实在不行，复制给ai分析也是一样的
> 你找个top app，演示分析难的算法，实战帖一出，大家都能看到价值
>
>

现在是初级阶段,已经能快速的分析当前界面的逻辑了, 并控制 js了,后续 能直接该逻辑直接重启 ,这第一步ai控制完成了后面遐想无限哈  另外也内置了frida 这样的东西,后续直接载入sandbox的 frida 脚本也是可以的.

## 回复 by 你瞒我瞒 (#7)

*2025-10-21 09:23*

1、如何使用。
2、有什么特别厉害的功能。
3、达到了什么效果。

## 回复 by k4y0z (#8)

*2025-10-21 10:11*

666

## 回复 by 情迁 (#9)

*2025-10-21 16:58*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  1、如何使用。
> 2、有什么特别厉害的功能。
> 3、达到了什么效果。
>
>

能用ai控制 被hook的应用,动态hook, 和动态分析 动态执行js全是ai完成的, 如何使用可以网上搜索  ai接入mcp, cherry studio和 claude code都可以支持mcp   ,是sse协议哈

## 回复 by zzzzz1 (#10)

*2025-10-21 21:02*

大佬，我也在做类似的工作，现在遇到了一些瓶颈，能交流下吗，我的账号私信不了

## 回复 by 情迁 (#11)

*2025-10-22 14:40*

>
> [zzzzz1](https://bbs.kanxue.com/user-1028333.htm)
>
>  大佬，我也在做类似的工作，现在遇到了一些瓶颈，能交流下吗，我的账号私信不了
>
>

类似的工作是啥意思?是想抄作业么

## 回复 by wx_妳还是不懂 (#12)

*2025-10-22 18:57*

建议你要做就做关于futter系列的，目前这些已经很少人用了

## 回复 by 情迁 (#13)

*2025-10-24 16:10*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_妳还是不懂](https://bbs.kanxue.com/user-913925.htm)
>
>  建议你要做就做关于futter系列的，目前这些已经很少人用了
>
>

![image](https://bbs.kanxue.com/view/img/face/002.gif)那需要抄作业了 把别人的功能缝合到我这个mcp里面去

## 回复 by chenxchun (#14)

*2025-12-24 12:41*

过于超前！

## 回复 by tDasm (#15)

*2026-1-29 11:51*

个人觉得还可以更好？既然是ui，就应该直接在界面上操作。还是没有跳出frida？
1、hook java类，就在界面上输入类名和对应方法名，然后在log框输出参数和结果
2、hook so地址，就在界面上输入so名和函数名或偏移地址，然后在log框输出各寄存器值，如果该寄存器是地址就显示该地址的数据。
3、内存搜索及查看
你也说能AI了？那为什么还要别人写几乎同样的js？不需要编程傻瓜式操作才是更好。
