---
title: '[原创]AI逆向新突破！-业内首个完全使用AI，不写一行代码完成JAVA层和SO层的全流程分析'
url: https://bbs.kanxue.com/thread-288260.htm
tid: 288260
author: 执着的猫
date: '2025-08-28'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-08T10:48:33+00:00'
replies: 22
---

接上文
https://bbs.kanxue.com/thread-288219.htm

上文我们提到使用ADB-MCP和FRIDA-MCP,让AI有了动态调试的能力，不止局限于单纯的静态分析。同时也提到IDA-MCP拥有了能够分析SO层的能力，那么就完成了最后一块拼图的搭建，这次我们就尝试使用AI,进行较高难度的APP的分析，包括java层和so层。

我们的分析思路是尽可能静态分析到无法分析的程度，使用frida进行hook得到缺失数据

这次分析的app是x品会，整体上属于一个中等难度的app，不算难，我们来看ai能做到什么程度

首先第一步还是抓包

\```
Python
import requests

headers = {
    "User-Agent": "okhttp/4.9.1",
    "Accept-Encoding": "gzip",
    "authorization": "OAuth api_sign=6322da63bf94fc2d5d06dedad1175285d88c0429"
}
url = "https://mp.appvipshop.com/apns/device_reg"
params = {
    "app_name": "achievo_ad",
    "app_version": "9.40.7",
    "device_token": "e75d2bed-a3cf-3dbf-b2b7-18861af5fef7",
    "status": "3",
    "warehouse": "VIP_NH",
    "manufacturer": "Google",
    "device": "Pixel 4 XL",
    "os_version": "33",
    "channel": "rjx5hknt:::",
    "vipruid": "",
    "regPlat": "0",
    "regid": "null",
    "rom": "Dalvik/2.1.0 (Linux; U; Android 13; Pixel 4 XL Build/TP1A.221005.002.B2)",
    "skey": "6692c461c3810ab150c9a980d0c275ec"
}
response = requests.get(url, headers=headers, params=params)

print(response.text)
print(response)
\```

这是一个设备注册的请求，请求头中的字段是我们需要分析的对象

首先还是第一步，使用apklab进行apk包的反编译，第二步，使用adb-mcp安装apk包

![image](https://bbs.kanxue.com/upload/attach/202508/1001962_CTHEABVVM34YRQF.webp)![image](https://bbs.kanxue.com/upload/attach/202508/1001962_3CNRDCXD7J58VA5.webp)

第三步，找到入口，我们来看是怎么做的，这里需要注意的是，提示词很重要，并且你应该指导AI怎么做，而不是AI牵着你的鼻子走

![image](https://bbs.kanxue.com/upload/attach/202508/1001962_H4JE4WX7PTC3S9D.webp)![image](https://bbs.kanxue.com/upload/attach/202508/1001962_2GM28E98BMH5D2C.webp)

这里AI给出了一大堆的分析结果，感觉人都晕了，但是感觉又说得很对，别慌，抓住主线，AI提示我们可以使用frida进行hook，但是别忘了，我们的思路是静态分析到无法分析的程度，java层分析了，还有so层没去分析呢，别全部都听AI的

![image](https://bbs.kanxue.com/upload/attach/202508/1001962_GX878HAQPNUW3HT.webp)

可以看到这里AI调用了IDA-MCP来去分析我们提到的so层函数，不需要我们自己找，只需要打开IDA使用这个MCP

![image](https://bbs.kanxue.com/upload/attach/202508/1001962_99J2A59M93JUVAP.webp)![image](https://bbs.kanxue.com/upload/attach/202508/1001962_TJZDGVK95MCXDP4.webp)

看似好像是给出了结果，但是我们需要注意的是，AI给到的结果可能有问题，不能全部相信，所有继续来问AI,你完全确定的信息是什么？哪些信息不完全确定？答案如下

![image](https://bbs.kanxue.com/upload/attach/202508/1001962_QAVWD8GYTYJMVXQ.webp)

这时候其实已经大体上知道加密逻辑了，下一步可能要做的就是HOOK确定关键信息，但是我必须要提到的是，使用多个AI交叉验证，不能相信一个AI，先把分析结果保存到文档，然后我们切换到CLAUDE CODE交叉验证

![image](https://bbs.kanxue.com/upload/attach/202508/1001962_6KKCC5HFGXQA969.webp)![image](https://bbs.kanxue.com/upload/attach/202508/1001962_779RTCDVYNE6S7W.webp)

这时候提到有三个问题，我们需要知道，哪些是静态分析能分析出来的，哪些是必须要动态分析的

![image](https://bbs.kanxue.com/upload/attach/202508/1001962_6NDYT9WJREQWD4H.webp)![image](https://bbs.kanxue.com/upload/attach/202508/1001962_4RRSWQ6T49FPCP3.webp)

分析到这一步，已经是静态分析的极限了，现在开始动态调试，AI自动进行hook,并写脚本分析结果是否正确

![image](https://bbs.kanxue.com/upload/attach/202508/1001962_6HP9CJCES3KQZR8.webp)![image](https://bbs.kanxue.com/upload/attach/202508/1001962_4M9FA982E5D4RDX.webp)![image](https://bbs.kanxue.com/upload/attach/202508/1001962_MJ9EMSVD97B5QM4.webp)

还是有不清楚的地方，提到的原因部分，我们觉得可能还是需要静态分析，因为URL参与签名的格式不应该不明确，所以继续静态分析

![image](https://bbs.kanxue.com/upload/attach/202508/1001962_5AZ56BZVXH7TA7B.webp)![image](https://bbs.kanxue.com/upload/attach/202508/1001962_62WCPGXR536XBQJ.webp)

AI有进行了一些frida的HOOK,最终得到了正确结果

到这一步已经完成了，我们让AI复现请求

![image](https://bbs.kanxue.com/upload/attach/202508/1001962_TT8Z6SYJBUATGDN.webp)

最后把AI复现的脚本放上

\```
Python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
唯品会 API Sign 生成器
Version: 1.0
Date: 2024-12-27
Author: Security Research Team

已成功破解唯品会9.40.7版本的api_sign算法
"""

import hashlib
import requests
from typing import Dict, Optional

class VipshopApiSigner:
    """唯品会API签名生成器"""

    # 固定的盐前缀（从native层提取）
    SALT_PREFIX = "aee4c425dbb2288b80c71347cc37d04b"

    @staticmethod
    def generate_api_sign(params: Dict[str, str]) -> str:
        """
        生成api_sign签名

        算法公式：
        api_sign = SHA1(salt_prefix + SHA1(salt_prefix + params_str))

        Args:
            params: 请求参数字典

        Returns:
            40位小写hex格式的api_sign
        """
        # 1. 参数按字典序排序
        sorted_params = sorted(params.items())

        # 2. 拼接参数串
        params_str = '&'.join([f"{k}={v}" for k, v in sorted_params])

        # 3. 第一次SHA1: 对(盐前缀 + 参数串)进行SHA1
        first_input = VipshopApiSigner.SALT_PREFIX + params_str
        first_hash = hashlib.sha1(first_input.encode('utf-8')).hexdigest()

        # 4. 第二次SHA1: 对(盐前缀 + 第一次SHA1结果)进行SHA1
        second_input = VipshopApiSigner.SALT_PREFIX + first_hash
        api_sign = hashlib.sha1(second_input.encode('utf-8')).hexdigest()

        return api_sign

    @staticmethod
    def send_device_reg_request(params: Optional[Dict] = None) -> requests.Response:
        """
        发送device_reg请求示例

        Args:
            params: 自定义参数，如果为None则使用默认参数

        Returns:
            requests.Response对象
        """
        # 默认参数
        if params is None:
            params = {
                "app_name": "achievo_ad",
                "app_version": "9.40.7",
                "device_token": "e75d2bed-a3cf-3dbf-b2b7-18861af5fef7",
                "status": "3",
                "warehouse": "VIP_NH",
                "manufacturer": "Google",
                "device": "Pixel 4 XL",
                "os_version": "33",
                "channel": "rjx5hknt:::",
                "vipruid": "",
                "regPlat": "0",
                "regid": "null",
                "rom": "Dalvik/2.1.0 (Linux; U; Android 13; Pixel 4 XL Build/TP1A.221005.002.B2)",
                "skey": "6692c461c3810ab150c9a980d0c275ec"
            }

        # 生成签名
        api_sign = VipshopApiSigner.generate_api_sign(params)

        # 构造请求
        headers = {
            "User-Agent": "okhttp/4.9.1",
            "Accept-Encoding": "gzip",
            "Authorization": f"OAuth api_sign={api_sign}"
        }

        url = "https://mp.appvipshop.com/apns/device_reg"

        # 发送请求
        response = requests.get(url, headers=headers, params=params)
        return response

def test_api_sign():
    """测试api_sign生成"""
    print("=== 唯品会 API Sign 生成器测试 ===\n")

    # 测试参数
    test_params = {
        "app_name": "achievo_ad",
        "app_version": "9.40.7",
        "device_token": "e75d2bed-a3cf-3dbf-b2b7-18861af5fef7",
        "status": "3",
        "warehouse": "VIP_NH",
        "manufacturer": "Google",
        "device": "Pixel 4 XL",
        "os_version": "33",
        "channel": "rjx5hknt:::",
        "vipruid": "",
        "regPlat": "0",
        "regid": "null",
        "rom": "Dalvik/2.1.0 (Linux; U; Android 13; Pixel 4 XL Build/TP1A.221005.002.B2)",
        "skey": "6692c461c3810ab150c9a980d0c275ec"
    }

    # 生成签名
    signer = VipshopApiSigner()
    api_sign = signer.generate_api_sign(test_params)

    print(f"生成的 api_sign: {api_sign}")
    print(f"期望的 api_sign: 6322da63bf94fc2d5d06dedad1175285d88c0429")
    print(f"验证结果: {'[MATCHED]' if api_sign == '6322da63bf94fc2d5d06dedad1175285d88c0429' else '[NOT MATCHED]'}")

    print("\n参数详情：")
    sorted_params = sorted(test_params.items())
    for key, value in sorted_params:
        print(f"  {key}: {value}")

def demonstrate_usage():
    """演示如何使用API签名器"""
    print("\n=== 使用示例 ===\n")

    # 创建签名器实例
    signer = VipshopApiSigner()

    # 自定义参数
    my_params = {
        "app_name": "test_app",
        "app_version": "1.0.0",
        "device": "Test Device",
        "skey": "test_key_12345"
    }

    # 生成签名
    api_sign = signer.generate_api_sign(my_params)
    print(f"自定义参数的签名: {api_sign}")

    # 可以直接发送请求（需要真实参数）
    response = signer.send_device_reg_request()
    print(f"响应状态: {response.status_code}")

    print(f"响应值: {response.text}")

if __name__ == "__main__":
    # 运行测试
    test_api_sign()

    # 演示用法
    demonstrate_usage()

    print("\n[SUCCESS] API signature algorithm fully cracked and working!")
\```

总结：再打通了静态分析与动态调试之后，AI已经完全从一个辅助者，变成了一个合格的逆向工程师，这次的AI使用经历重塑了我的认知，原来一行代码都不用写，也不需要懂JAVA或者汇编代码，就可以完成全流程的静态分析与动态调试，AI现在的能力已经可以替代我们人类了。

但是需要注意的是，使用AI我们从一个执行者变成一个指挥者，我们一定不能被AI牵着鼻子走，这是完成全流程的关键

目前存在的问题：
1.AI找入口依赖于搜素关键字，如果关键字不是明文，就需要我们人类给到AI提示，比如hook hashmap,hook base64等等

2.AI对于强混淆的SO层代码，解析能力较弱，需要我们人类帮助，后续我会写一个专门去混淆的MCP,来完成这个过程，ollvm-mcp，vmp-mcp都不是不可能

下一步的改进：

1. 构建辅助AI分析的先验知识库，帮助AI更准确的生成脚本，以及做出判断
2. 开发去控制流混淆的MCP,分析控制流混淆的SO

看到这里的话，可以关注我，本人有逆向背景和人工智能背景，在业内某互联网公司就职，可能是业内首个成功打通AI逆向全流程的人，后续会在AI逆向，AI风控方面深耕，我相信AI会改变整个逆向和风控，需要我们共同努力

---

# 回复

## 回复 by iBa0 (#2)

*2025-8-28 09:55*

![image](https://bbs.kanxue.com/view/img/face/049.gif)

## 回复 by l1nn (#3)

*2025-8-28 10:06*

>
> [WMBa0](https://bbs.kanxue.com/user-971547.htm)
>
>  [em_049]
>
>

![image](https://bbs.kanxue.com/view/img/face/057.gif)

## 回复 by 西瓜帅 (#4)

*2025-8-28 10:58*

站在巨人的jb上学ai逆向

## 回复 by DirtyAngle (#5)

*2025-8-28 11:28*

坐在巨人的jb上学ai逆向

## 回复 by kkte (#6)

*2025-8-28 12:37*

躺在巨人的jb上学ai逆向

## 回复 by tDasm (#7)

*2025-8-28 13:21*

AI哪里逆向分析了？做一些辅助功能而已。AI目前还没有这种能力

## 回复 by 执着的猫 (#8)

*2025-8-28 14:18*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  tDasm](https://bbs.kanxue.com/user-382.htm)
>
>  AI哪里逆向分析了？做一些辅助功能而已。AI目前还没有这种能力
>
>

全程只是跟AI交互，就把协议逆向出来了

## 回复 by XCicada (#9)

*2025-8-28 16:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  tDasm](https://bbs.kanxue.com/user-382.htm)
>
>  AI哪里逆向分析了？做一些辅助功能而已。AI目前还没有这种能力
>
>

可以的之前我随便试了一下，我说请你研究这个字符串解密，然后我跑去做别的了，回来一看他弄完了，aes的什么iv那些全部解出来了，还写了个脚本

## 回复 by 一只笨猫 (#10)

*2025-8-29 14:13*

>
> [a'ゞCicada](https://bbs.kanxue.com/user-927003.htm)
>
>  可以的之前我随便试了一下，我说请你研究这个字符串解密，然后我跑去做别的了，回来一看他弄完了，aes的什么iv那些全部解出来了，还写了个脚本
>
>

native还是太吃力了

## 回复 by 一只笨猫 (#11)

*2025-8-29 14:56*

need help
![image](https://bbs.kanxue.com/upload/attach/202508/890609_W5NKNW8CW9H9VB2.webp)

## 回复 by 执着的猫 (#12)

*2025-8-29 22:37*

>
> [一只笨猫](https://bbs.kanxue.com/user-890609.htm)
>
>  need help
>
>

应该是frida配置的问题，frida需要配置下config.js,跟机型也有关系，我关注你了，你私信我

## 回复 by 酒仙桥之虎 (#13)

*2025-8-30 00:21*

感觉做一个unidbg-mcp也会有实战价值

## 回复 by 初学者有毅力 (#14)

*2025-8-30 10:33*

以后都是AI逆向了,,逆向没什么门槛了 以前都要累计几年的经验才算出入门,,现在好了 没有门槛了 学个简单的知识配合AI 谁都是逆向大神

## 回复 by 一只笨猫 (#15)

*2025-8-30 15:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  初学者有毅力](https://bbs.kanxue.com/user-641633.htm)
>
>  以后都是AI逆向了,,逆向没什么门槛了 以前都要累计几年的经验才算出入门,,现在好了 没有门槛了 学个简单的知识配合AI 谁都是逆向大神
>
>

理想是好的

## 回复 by MikotoDev (#16)

*2025-8-31 22:17*

躺在巨人的jb上学ai逆向![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by 熊猫吃鱼 (#17)

*2025-8-31 22:50*

躺在巨人的jb上学ai逆向

## 回复 by lichaolich (#18)

*2025-9-2 09:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  初学者有毅力](https://bbs.kanxue.com/user-641633.htm)
>
>  以后都是AI逆向了,,逆向没什么门槛了 以前都要累计几年的经验才算出入门,,现在好了 没有门槛了 学个简单的知识配合AI 谁都是逆向大神
>
>

逆向的门槛并不在经验，而在于智商，因为这个不是跟别人学来的都是自己研究。所以出来新技术，高手比你更会玩；假设所有人都立马成为逆向专家了，那么软件厂商也会增强，最终平衡点还是少数人能搞定。

## 回复 by zhuzhu_biu (#19)

*2025-9-2 14:05*

对native来说, 算法还原只是体力活,有llm加持,24小时持续分析,vmp算法还原也不再是难事,有兴趣我们可以加个好友![image](https://bbs.kanxue.com/view/img/face/071.gif)

## 回复 by 过江龙V (#20)

*2025-9-12 14:14*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by ikunnn (#21)

*2025-10-3 22:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zhuzhu_biu](https://bbs.kanxue.com/user-878476.htm)
>
>  对native来说, 算法还原只是体力活,有llm加持,24小时持续分析,vmp算法还原也不再是难事,有兴趣我们可以加个好友[em_071]
>
>

兄弟你可以给我发信息吗，我有兴趣，也有相关知识基础，因为我是临时用户加不了你谢谢啦

## 回复 by ikunnn (#22)

*2025-10-4 13:50*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zhuzhu_biu](https://bbs.kanxue.com/user-878476.htm)
>
>  对native来说, 算法还原只是体力活,有llm加持,24小时持续分析,vmp算法还原也不再是难事,有兴趣我们可以加个好友[em_071]
>
>

不行啊大佬，你发的vx二维码打不开，实在抱歉，能不能发wx号也行

## 回复 by mb_zzzklvpa (#23)

*2026-3-11 10:42*

666
