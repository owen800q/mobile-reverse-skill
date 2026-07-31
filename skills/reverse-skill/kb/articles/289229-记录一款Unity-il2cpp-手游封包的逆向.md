---
title: '[原创]记录一款Unity il2cpp 手游封包的逆向'
url: https://bbs.kanxue.com/thread-289229.htm
tid: 289229
author: mb_vhwdzyqo
date: '2025-11-27'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T15:25:48+08:00'
replies: 190
---

游戏名称:5ZWG6YGT6auY5omL

学了那么久逆向了 也是准备进军手游逆向 对于发送包的逻辑我大致上是了解了很多 但是对于接收包的逆向 我感觉还是缺了点经验  这一篇文章对我逆向这款游戏就当一次记录 游戏并没有检测以及保护 所有还是比较适合我这样的小菜的 如果一个游戏看到了易盾 tprt 那我应该直接放弃了 逆向时间一共三天 那么废话不多说 直接开干

前置知识以及工具 root的手机(建议pixel4) frida ida suuny抓包工具 frida-il2cpp-bridge 没了~~~ 至于frida-il2cpp-bridge github下载即可~~~

# 1.分析游戏引擎

额 可能是我的知识储备有限 不知道该怎么称呼 也可以说这游戏是啥开发吧 我一般来说比较喜欢看so文件 ，用mt管理器把游戏安装包提取出来 /lib/arm64-v8a/这个路径下就是so文件（一顿乱点）

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_2JVDQNE7HHU223W.webp)

哟西 这不是我们的老朋友il2cpp.so还会libunity吗 嘿嘿 那就知道了这个是unity开发的 至于lua 应该没有 ，先打开il2cpp.so查看他的16进制

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_B3XXTGY7FVGNZJA.webp)

感谢天感谢地 文件并没有被加密 熵值没有那么高 头部也没问题 是正常的elf文件 7F 45 4C 46     接下来 在/assets/bin/Data/Managed/Metadata/拿到我们的global-meta文件

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_MZRBGKUS4D5NTEB.webp)

AF 1B B1 FA也是正常的魔术头 那我们就不需要在内存里dump了(庆幸)

那行 拿出我们的frida-il2cpp-bridge直接把游戏逻辑给dump出来吧 我刚开始学unity逆向的时候也是这么懵逼的 为啥还要dump出来 不能直接在il2cpp.so看吗 后来我才知道 il2cpp的都是subxxx开头的方法 和真实的名字匹配不上~~~(愚蠢) 扯远了 直接dump吧

#

# 2.dump游戏逻辑

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_Z699TB3MXJXQH3B.webp)

双击我框出来的exe文件 第一个选择il2cpp.so 第二个选中global-metadata 然后dump完毕后直接回车    ok 你会看到一个dump.cs  我图上有是因为我之前dump过了 其中dump.cs里面都是游戏的逻辑 但不能说的那么绝对 因为一些游戏的逻辑会在lua里面

# 3.分析游戏逻辑

不好意思 忘记抓包了 先抓个包吧(笑哭) 哈哈 如果dump失败了我绝对先去抓包了 这不影响我们操作 来吧 打开suny抓包工具 sunny会提供一个sunnynet的软件

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_CEXHQPC224JXNR5.webp)

在里面填入地址即可 这个地址填写自己的 每个人都不一样 然后呢保存电脑和手机同一个网络 在电脑也打开抓包工具 至于这些不会的 可以看sunny的文档或者去联系下开发人员 在Bilibilli这些地方都能找到

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_5HZ3A7UUWG5HAAY.webp)

好简单介绍了下游戏 我们要准备抓包了 这个游戏没有vpn检测 如果有的话 直接把他hook掉即可 因为 没有 我这里就不贴图了

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_W42NMVW8B59MUXR.webp)

这个就是tcp包 以后发的包都会在这里 因为方便调试 我们拿这个游戏的喊话来介绍 喊话内容123 ps:等级没到是发不出去的 但是会发送包 这点大家不用担心

这是第一次发包

BC9988AA2D0032E64D5E16BBA23BAD1EBC1B1020D02DA01FBA481925847BF54EE04E1F758E76A61DE2421C768620F11CBE457014F046C82FC9

这是第二次发包

BC9988AA2D0032E673602885A23BAD1E821B1020D02DA01F84481925847BF54EDE4E1F758E76A61DDC421C768620F11C80457014F046C82FF7

这俩包完全是不一样的 但是我们明明发的同一个内容啊?还是说有随机值?于是我又重新发送了一遍

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_RAG4AZTZBHV9B2H.webp)

发现并没有效果 这很正常 游戏防你重发包(没给我掉线已经是很大的仁慈了 嘻嘻)  来吧 分析游戏的发包逻辑了

因为他是tcp游戏 我们打开dump.cs之后可以搜索关键词 send net client encrypt 等等 其实我认为大部分都是靠猜

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_ZH3XP7CYG422JDW.webp)

我搜索的是send 一共302个结果 其中public void SendData(byte[] oriData, int index, int count) { }这个我感觉就是发包的逻辑(剧透下 走狗屎运了 一猜就猜到了) 为啥感觉是他 一个是因为他是个方法 其次他的class是在![image](https://bbs.kanxue.com/upload/attach/202512/1023363_K6Z9DCB538BTMD6.webp)

这个netclient之下(就算不在我也会尝试 嘻嘻)

好找到方法之后 拿出frida 开始构造函数了 一顿乱找发现assembly在Utility里面(可以自己动手找一下 图就不贴了 因为代码找不到了)

frida-il2cpp-bridge的具体用法可以查看bilibilli

我把hook代码先贴出来

```
import "frida-il2cpp-bridge";

Il2Cpp.perform(() => {
    const Assembly = Il2Cpp.domain.assembly("Utility").image;
    const NetClient = Assembly.class("Net.NetClient");
    const EncTdrBuffMethod = NetClient.method("SendData", 3);
    EncTdrBuffMethod.implementation = function (a, b, c) {
        console.log("SendData:", a, b, c);
        const result = this.method("SendData", 3).invoke(a, b, c);
        console.log("SendData结果:", a,b,c);
        return result;
    };
});
```

发现senddata的结果就是我们想要的 可见senddata这个方法就是发送数据的方法 当然肯定是加密了之后的

至于我为啥要重新输出入参 因为有些返回值他会以入参的形式返回 这个记住就行

然后直接trace utility这个assembly 看看有谁在调用

```
import "frida-il2cpp-bridge";

Il2Cpp.perform(() => {
    Il2Cpp.trace(true)
        .verbose(false)
        .assemblies(Il2Cpp.domain.assembly("Utility"))
        .and()
        .attach();
});
```

看trace结果

il2cpp:

0x00b8af00 ┌─Utility.HttpHelper::Update

0x00b8b194 │ ┌─Utility.HttpSession::get_IsDone

0x00b85290 │ │ ┌─Net.LuaConnect::Send

0x00b84d6c │ │ │ ┌─Net.GameConnect::allocGamePacket

0x00b889b0 │ │ │ │ ┌─Net.SendDataPacket::Clear

0x00b889b0 │ │ │ │ └─Net.SendDataPacket::Clear

0x00b8495c │ │ │ │ ┌─Net.SendDataPacket::SetMessage

0x00b8495c │ │ │ │ └─Net.SendDataPacket::SetMessage

0x00b84d6c │ │ │ └─Net.GameConnect::allocGamePacket

0x00b85364 │ │ │ ┌─Net.SendDataPacket::WriteBuffer

0x00b8211c │ │ │ │ ┌─Net.DataPacket::Reverse

0x00b8211c │ │ │ │ └─Net.DataPacket::Reverse

0x00b85364 │ │ │ └─Net.SendDataPacket::WriteBuffer

0x00b8232c │ │ │ ┌─Net.GameConnect::get_Instance

0x00b8232c │ │ │ └─Net.GameConnect::get_Instance

0x00b84f14 │ │ │ ┌─Net.GameConnect::flushPacket

0x00b83994 │ │ │ │ ┌─Net.GameConnect::getPacketIndex

0x00b83994 │ │ │ │ └─Net.GameConnect::getPacketIndex

0x00b84b84 │ │ │ │ ┌─Net.SendDataPacket::completePacket

0x00b88728 │ │ │ │ │ ┌─Net.NetProtocol::calcPacketDataVerify

0x00b88728 │ │ │ │ │ └─Net.NetProtocol::calcPacketDataVerify

0x00b887f0 │ │ │ │ │ ┌─Net.NetProtocol::encryptClientPacket

0x00b887f0 │ │ │ │ │ └─Net.NetProtocol::encryptClientPacket

0x00b84b84 │ │ │ │ └─Net.SendDataPacket::completePacket

0x00b84fa4 │ │ │ │ ┌─Net.NetClient::SendData

0x00b8293c │ │ │ │ │ ┌─Net.GameConnect::IsConnected

0x00b8293c │ │ │ │ │ └─Net.GameConnect::IsConnected

0x00b84fa4 │ │ │ │ └─Net.NetClient::SendData

0x00b84f14 │ │ │ └─Net.GameConnect::flushPacket

0x00b85290 │ │ └─Net.LuaConnect::Send

0x00b8bfe8 │ │ ┌─Utility.HttpSession::Dispose

0x00b8bfe8 │ │ └─Utility.HttpSession::Dispose

0x00b8b194 │ └─Utility.HttpSession::get_IsDone

0x00b8af00 └─Utility.HttpHelper::Update

这一段就非常适合研究

我们仔细看 就知道流程了

completePacket组包->calcPacketDataVerify获取验证码->encryptClientPacket加密->completePacket完成组包->发送

因为明文是completePacket所以我只看了这么点 到后面会有点瑕疵 ~~~(懒了)

```
import "frida-il2cpp-bridge";

Il2Cpp.perform(() => {
    const Assembly = Il2Cpp.domain.assembly("Utility").image;
    const NetClient = Assembly.class("Net.NetProtocol");
    const NetClient1 = Assembly.class("Net.NetProtocol");
    const NetClient2 = Assembly.class("Net.SendDataPacket");
    const EncTdrBuffMethod = NetClient.method("calcPacketDataVerify", 4);
    const EncTdrBuffMethod1 = NetClient1.method("encryptClientPacket", 4);
    const EncTdrBuffMethod2 = NetClient2.method("completePacket", 2);
    EncTdrBuffMethod.implementation = function (tdrBuff, tdrBuffLen, encBuff,a) {
        console.log("calcPacketDataVerify:", tdrBuff, tdrBuffLen, encBuff,a);
        const result = this.method("calcPacketDataVerify", 4).invoke(tdrBuff, tdrBuffLen, encBuff,a);
        console.log("calcPacketDataVerify结果:", tdrBuff, tdrBuffLen, encBuff,a);
        return result;
    };
    EncTdrBuffMethod1.implementation = function (tdrBuff, tdrBuffLen, encBuff,a) {
        console.log("encryptClientPacket:", tdrBuff, tdrBuffLen, encBuff,a);
        const result = this.method("encryptClientPacket", 4).invoke(tdrBuff, tdrBuffLen, encBuff,a);
        console.log("encryptClientPacket结果:", tdrBuff, tdrBuffLen, encBuff,a);
        return result;
    };
    EncTdrBuffMethod2.implementation = function (tdrBuff, tdrBuffLen) {
        console.log("completePacket:", tdrBuff, tdrBuffLen);
        const result = this.method("completePacket", 2).invoke(tdrBuff, tdrBuffLen);
        console.log("completePacket结果:", tdrBuff, tdrBuffLen);
        return result;
    };

});
```

这个是完整的hook代码

查看hook结果

![image](https://bbs.kanxue.com/upload/attach/202512/1023363_EXUVJVCKRU6Q8S6.webp)

我们发现complete有两个值的传入 一个值是固定的 还有一个值每次都会随机加1-2 但是固定的值每次上游戏都会变 还有一个值的初始值因为懒我还没找到在哪里初始化的(这就是瑕疵 给我多点时间我一定会找出来)

在calcPacketDataVerify里 我们看到了明文49,50,51,  对应ascll码1 2 3 其实看到这里就很明白了

至于分析算法 我们先进入completePacket 对应地址0xB84B84

__int64 __fastcall completePacket(__int64 a1, __int64 a2, int a3)

{

  unsigned __int16 v4; // w20

  __int64 v6; // x8

  __int64 *v7; // x21

  __int64 v8; // x24

  __int64 v9; // x0

  int v10; // w22

  __int64 v11; // x0

  int v12; // w8

  __int64 result; // x0

  unsigned int v14; // w8

  v4 = a2;

  if ( (byte_1C25190 & 1) == 0 )

  {

    sub_66D538(15359LL);

    byte_1C25190 = 1;

  }

  v7 = (a1 + 16);

  v6 = *(a1 + 16);

  if ( !v6 || !*(v6 + 24) || (v8 = v6 + 32, v6 == -32) )

    sub_6979A4(0LL);

  v9 = qword_1BF15F0;

  if ( (*(qword_1BF15F0 + 295) & 2) != 0 && !*(qword_1BF15F0 + 216) )

  {

    il2cpp_runtime_class_init_0(qword_1BF15F0, a2);

    v9 = qword_1BF15F0;

  }

  *v8 = *(*(v9 + 184) + 8LL);

  v10 = *(a1 + 28);

  v11 = qword_1BF15C8;

  if ( (*(qword_1BF15C8 + 295) & 2) != 0 && !*(qword_1BF15C8 + 216) )

  {

    il2cpp_runtime_class_init_0(qword_1BF15C8, a2);

    v11 = qword_1BF15C8;

  }

  v12 = v10 - **(v11 + 184);

  *(v8 + 4) = v10 - **(v11 + 184);

  *(v8 + 6) = calcPacketDataVerify(*v7, **(qword_1BF15C8 + 184), v12, v4);

  result = encryptClientPacket(v7, **(qword_1BF15C8 + 184), *(v8 + 4), a3);

  v14 = a3 ^ (v4 | (*(v8 + 4) << 16)) ^ 0xFFFF0000;

  *(v8 + 8) = (v14 & 0xFF000000 ^ (v14 << 24)) & 0xFFFFFF00 | v14 | (v14 ^ (v14 << 8)) & 0xFF00 | (v14 ^ (v14 << 16)) & 0xFF0000;

  return result;

}

额 让AI辅助分析吧

```
def encryptClientPacket(buf, index, dwSize, uKey):
    result = bytearray(buf)
    start_idx = index
    if dwSize >= 5:
        v7 = (dwSize - 5) & 0xFFFFFFFC
        v8 = dwSize ^ uKey ^ 0x1E9D3AE4
        v9 = start_idx + v7
        i = dwSize
        current_idx = start_idx
        while i > 4:
            data = int.from_bytes(result[current_idx:current_idx + 4], 'little', signed=False)
            v8 ^= uKey ^ data
            v8 &= 0xFFFFFFFF
            result[current_idx:current_idx + 4] = v8.to_bytes(4, 'little', signed=False)
            current_idx += 4
            i -= 4
        dwSize = dwSize - 4 - v7
        current_idx = v9 + 4
    else:
        current_idx = start_idx
    remaining = dwSize
    while remaining > 0:
        result[current_idx] ^= (uKey & 0xFF) ^ 0xA6
        current_idx += 1
        remaining -= 1
    return bytes(result)

def calcPacketDataVerify(buf, idx, dwSize, uKey):
    if dwSize < 1:
        v7 = 0xCE
        v6 = 0x9B
    else:
        v5 = dwSize + 1
        v6 = 0x9B
        v7 = 0xCE
        current_idx = idx

        while v5 > 1:
            v9 = buf[current_idx]
            v5 -= 1
            current_idx += 1
            v7 ^= v9
            v6 ^= v7
    result = (v7 | (v6 << 8)) ^ (~uKey & 0xFFFF)
    return result & 0xFFFF

def calculate_final_value(packet_index, verify_key, data_size):
    v14 = packet_index ^ (verify_key | (data_size << 16)) ^ 0xFFFF0000
    v14 &= 0xFFFFFFFF
    part1 = (v14 & 0xFF000000) ^ ((v14 << 24) & 0xFF000000)
    part1 = part1 & 0xFFFFFF00
    part2 = v14 & 0x000000FF
    part3 = (v14 ^ (v14 << 8)) & 0x0000FF00
    part4 = (v14 ^ (v14 << 16)) & 0x00FF0000
    final_value = part1 | part2 | part3 | part4
    return final_value & 0xFFFFFFFF

验证码 = 0#这个验证码发的一个包都是0
递增数 = 177340530#暂时还不知道这个seq的来源
buf = [188,153,136,170,45,0,0,0,0,0,0,0,107,1,8,1,18,3,49,49,51,48,0,66,32,102,48,57,53,101,51,101,49,52,97,52,102,55,52,57,99,52,52,54,51,56,56,48,101,53,100,101,99,57,52,100,99,0,0,0,0,0,0,0]#喊话123
buf = [188,153,136,170,7,0,0,0,0,0,0,0,0,0,69,78,67,82,0,0,0,0,0,0,0,0,0,0,0,0,0,0]#登录的第一个包
buf = [188,153,136,170,7,0,0,0,0,0,0,0,0,0,69,78,67,82,0,0,0,0,0,0,0,0,0,0,0,0,0,0]#登录第一个包
verify_code = calcPacketDataVerify(buf, 12, buf[4], 验证码)
buf_with_verify = bytearray(buf)
buf_with_verify[6] = verify_code & 0xFF        # 0xB2
buf_with_verify[7] = (verify_code >> 8) & 0xFF # 0x3B
index = 12#w忘了
dwSize = buf[4]
uKey = 递增数
tmp1 = encryptClientPacket(buf_with_verify, index, dwSize, uKey)
final_value = calculate_final_value(uKey, 验证码, dwSize)
final_bytes = final_value.to_bytes(4, 'little')
tmp1_final = bytearray(tmp1)
tmp1_final[8:12] = final_bytes
final_result = bytes(tmp1_final)
print("result:", ''.join(f'{b:02X}' for b in final_result))
```

大致的算法如上 其实最主要的还是那3个函数

看到递增数了吗 这个数每次发包都会+ 1或者2 你自己hook的话是可以看出来的 所以你想要重发包必须得对应上这个计数器 暂时称之为seq吧  但是你重发包的话游戏会断开连接 因为seq是存储在系统里面 你的seq更新了 游戏里的seq可没有更新 自然而然游戏重新连接了

如果想要自己搭建一套客户端 那是非常耗时间的 我现在因为时间不够还得去解密接收逻辑 还得去找固定的值 自己平常课也多 也没那么多时间来研究 争取这个星期给他搞定吧

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2025-11-27 23:34*

感谢分享

## 回复 by mb_mmlkqxal (#3)

*2025-11-28 11:43*

111111111111

## 回复 by 夜惜风雨 (#4)

*2025-11-28 14:28*

666666

## 回复 by azd放 (#5)

*2025-11-28 15:11*

感谢分享

## 回复 by KerryS (#6)

*2025-11-28 15:29*

感谢分享

## 回复 by 哟哟哟哟 (#7)

*2025-11-28 16:33*

thx

## 回复 by icey233 (#8)

*2025-11-28 16:52*

感谢分享

## 回复 by method (#9)

*2025-11-28 17:52*

1

## 回复 by GEKEZYX (#10)

*2025-11-28 18:03*

666

## 回复 by aqingadmin (#11)

*2025-11-29 00:21*

666

## 回复 by 龙龙pyl (#12)

*2025-11-29 02:35*

感谢分享

## 回复 by wx_Huber Barrientos (#13)

*2025-11-29 03:31*

感谢分享

## 回复 by huangjw (#14)

*2025-11-29 10:09*

好文章

## 回复 by mb_jxhmajfh (#15)

*2025-11-29 11:50*

66666

## 回复 by mb_qimctavn (#16)

*2025-11-29 12:52*

6

## 回复 by hacker521 (#17)

*2025-11-29 13:49*

666

## 回复 by MaYil (#18)

*2025-11-29 14:31*

感谢分享

## 回复 by mb_aryaikny (#19)

*2025-11-29 15:12*

![image](https://bbs.kanxue.com/view/img/face/001.gif) 牛批啊 感谢分享

## 回复 by mb_udytusff (#20)

*2025-11-29 20:40*

...................

## 回复 by mb_nkjfyhkg (#21)

*2025-11-30 02:21*

Mark

## 回复 by 啊你好哇123 (#22)

*2025-11-30 17:10*

学习学习

## 回复 by mb_irhdtnzm (#23)

*2025-11-30 19:28*

1

## 回复 by mb_xodigovh (#24)

*2025-11-30 21:22*

11

## 回复 by Freway (#25)

*2025-11-30 22:51*

666

## 回复 by mb_ehujhmht (#26)

*2025-12-1 08:16*

6

## 回复 by wx_范迪塞尔 (#27)

*2025-12-1 10:14*

6666

## 回复 by lanliqiang (#28)

*2025-12-1 13:59*

666

## 回复 by zzw_xjx (#29)

*2025-12-2 11:25*

666

## 回复 by mb_lmjlnzrh (#30)

*2025-12-3 11:47*

666

## 回复 by 瓜皮逆向 (#31)

*2025-12-3 13:28*

思路清晰

## 回复 by mb_xjdhrmck (#32)

*2025-12-3 13:45*

66666

## 回复 by mb_awbfnjrt (#33)

*2025-12-3 18:13*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by Dlnn (#34)

*2025-12-3 21:08*

666

## 回复 by yzlmars (#35)

*2025-12-4 09:27*

66666

## 回复 by mb_yynjwyzd (#36)

*2025-12-4 10:02*

康康

## 回复 by mb_itzrixny (#37)

*2025-12-4 15:47*

1

## 回复 by C兔 (#38)

*2025-12-4 16:43*

Dd

## 回复 by kissbai (#39)

*2025-12-5 07:06*

感谢分享

## 回复 by xifgg (#40)

*2025-12-5 10:03*

6

## 回复 by mb_phbudlqp (#41)

*2025-12-5 10:38*

很棒

## 回复 by CheRevir (#42)

*2025-12-5 17:56*

666

## 回复 by Our_OT (#43)

*2025-12-5 21:52*

学习

## 回复 by wx_老夫_473 (#44)

*2025-12-6 10:06*

1

## 回复 by wx_随波逐流、 (#45)

*2025-12-7 21:01*

66666666666666666

## 回复 by xinhu (#46)

*2025-12-8 09:49*

666

## 回复 by wuligam (#47)

*2025-12-8 14:01*

看看型结构

## 回复 by wx_白泽 (#48)

*2025-12-8 14:22*

666

## 回复 by zylyy (#49)

*2025-12-8 14:29*

666

## 回复 by wx-LL- (#50)

*2025-12-8 15:08*

666

## 回复 by 勒LI (#51)

*2025-12-8 17:25*

666

## 回复 by mb_ddbuxnvh (#52)

*2025-12-9 10:58*

6666

## 回复 by mb_milinwyn (#53)

*2025-12-9 17:55*

1

## 回复 by mb_mqojhpdd (#54)

*2025-12-9 21:50*

哈哈哈哈

## 回复 by mb_nfhxghsg (#55)

*2025-12-10 02:04*

111111111111

## 回复 by mb_haorlggm (#56)

*2025-12-10 02:04*

111

## 回复 by mb_szqldxer (#57)

*2025-12-10 11:19*

看看

## 回复 by mb_jvgnqejw (#58)

*2025-12-10 16:21*

666

## 回复 by mb_rbaigqfb (#59)

*2025-12-11 10:40*

学习下

## 回复 by mb_devnoxep (#60)

*2025-12-11 11:50*

牛????

## 回复 by mb_uodtmdzg (#61)

*2025-12-11 16:52*

666

## 回复 by 错过 (#62)

*2025-12-11 17:13*

66666

## 回复 by mb_vuoalrrx (#63)

*2025-12-12 11:48*

666

## 回复 by mb_optpmxoa (#64)

*2025-12-12 14:47*

赞

## 回复 by cobe (#65)

*2025-12-16 16:12*

666

## 回复 by chenwitch (#66)

*2025-12-16 17:44*

666

## 回复 by wx_宇克鴻 (#67)

*2025-12-18 12:41*

牛批

## 回复 by vcdemon (#68)

*2025-12-18 13:38*

1111

## 回复 by mb_nbakwvoe (#69)

*2025-12-18 13:42*

666

## 回复 by mb_dynjaspl (#70)

*2025-12-18 18:12*

666

## 回复 by uniking (#71)

*2025-12-18 18:32*

mark

## 回复 by AiGame (#72)

*2025-12-18 23:49*

666

## 回复 by TinM! (#73)

*2025-12-19 14:35*

666

## 回复 by mb_oskoghri (#74)

*2025-12-20 01:04*

![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by stayupup (#75)

*2025-12-22 09:53*

学习学习

## 回复 by mb_rtxtnuec (#76)

*2025-12-25 06:13*

感谢分享

## 回复 by 希梦☆奈何 (#77)

*2025-12-25 11:10*

路过看看

## 回复 by console_ (#78)

*2025-12-25 22:26*

学习

## 回复 by 哥倫布 (#79)

*2025-12-27 12:06*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by wdnynmp (#80)

*2025-12-27 12:43*

666

## 回复 by 3zureus (#81)

*2025-12-27 17:39*

感谢分享

## 回复 by CCTV9 (#82)

*2025-12-27 18:43*

6666

## 回复 by 他姓何i (#83)

*2025-12-28 09:33*

谢谢分享

## 回复 by kuteng01 (#84)

*2025-12-29 13:35*

666

## 回复 by tjytjy (#85)

*2025-12-30 15:31*

666

## 回复 by gaoyanggnay (#86)

*2025-12-30 18:35*

666666

## 回复 by 魔童 (#87)

*2025-12-30 18:56*

6666666

## 回复 by xiongbl (#88)

*2025-12-30 19:46*

666

## 回复 by 小李08 (#89)

*2025-12-31 16:24*

6666

## 回复 by mb_kjujrhnv (#90)

*2025-12-31 17:31*

666

## 回复 by win柠初 (#91)

*2026-1-1 17:34*

666

## 回复 by zhenzhentx (#92)

*2026-1-3 18:24*

你的帖子非常有用，感谢分享！

## 回复 by wx_[          ] (#93)

*2026-1-3 21:41*

666

## 回复 by TeamAR (#94)

*2026-1-4 09:05*

666

## 回复 by mb_ujgvshnw (#95)

*2026-1-4 21:03*

66666666666666666666

## 回复 by 街道办事处 (#96)

*2026-1-6 16:33*

1

## 回复 by samosxin (#97)

*2026-1-7 08:31*

1

## 回复 by mb_cazrktqg (#98)

*2026-1-9 00:46*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by wx_123_100 (#99)

*2026-1-13 22:17*

感谢大佬分享

## 回复 by mb_ppryzjtf (#100)

*2026-1-15 12:54*

666

## 回复 by mb_hymnmxvw (#101)

*2026-1-15 13:38*

7

## 回复 by 0cc0 (#102)

*2026-1-20 23:15*

学习

## 回复 by mb_lpbalxud (#103)

*2026-1-22 22:03*

6666

## 回复 by wx_豪_522545 (#104)

*2026-1-22 23:58*

666

## 回复 by xiaoxuya (#105)

*2026-1-23 13:53*

学习看看

## 回复 by 章节三 (#106)

*2026-1-23 16:08*

![image](https://bbs.kanxue.com/view/img/face/002.gif)nice

## 回复 by 大安心 (#107)

*2026-1-24 00:13*

![image](https://bbs.kanxue.com/view/img/face/062.gif)

## 回复 by 樊辉 (#108)

*2026-1-25 11:35*

666

## 回复 by xlaa (#109)

*2026-1-25 14:30*

3

## 回复 by wx_西门浪 (#110)

*2026-1-25 15:51*

666

## 回复 by wx_ln (#111)

*2026-1-26 19:24*

7n

## 回复 by 我是小奥 (#112)

*2026-1-26 23:02*

666

## 回复 by mb_niapwogb (#113)

*2026-1-30 10:02*

学习了

## 回复 by mb_vxguvtyr (#114)

*2026-1-30 11:11*

感谢作者分享经验

## 回复 by xinyii (#115)

*2026-2-1 10:18*

感谢分享

## 回复 by 吾苏同在 (#116)

*2026-2-1 11:03*

1111

## 回复 by Python小艾 (#117)

*2026-2-1 12:42*

易学习

## 回复 by mb_wngyylvq (#118)

*2026-2-2 01:00*

牛逼的

## 回复 by mb_uruwpimj (#119)

*2026-2-6 01:28*

学习

## 回复 by mb_rmwvchlr (#120)

*2026-2-6 16:34*

666

## 回复 by mb_lgbrcvmf (#121)

*2026-2-7 00:10*

666

## 回复 by mb_utxzckcq (#122)

*2026-2-7 04:36*

66666

## 回复 by 外交 (#123)

*2026-2-7 14:36*

11

## 回复 by mb_nggigxxl (#124)

*2026-2-7 20:54*

666

## 回复 by git_11829lalueandliuliu (#125)

*2026-2-8 02:23*

66666666

## 回复 by git_44735Windy1337 (#126)

*2026-2-16 21:27*

666

## 回复 by superoldman (#127)

*2026-2-19 19:04*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_etgbvvic (#128)

*2026-2-20 00:24*

666666

## 回复 by mb_yalauklc (#129)

*2026-2-20 13:19*

在666

## 回复 by mb_owfvtagq (#130)

*2026-2-21 22:51*

学习学习

## 回复 by wx_qsrl (#131)

*2026-2-24 17:24*

111

## 回复 by mb_eywdngzs (#132)

*2026-2-25 23:14*

666

## 回复 by 禾夕夕 (#133)

*2026-2-26 00:31*

666

## 回复 by wx_-_127 (#134)

*2026-2-26 05:07*

姐姐姐姐姐姐

## 回复 by mb_axuhckkh (#135)

*2026-2-27 17:38*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_iywmjqjc (#136)

*2026-3-3 14:35*

666

## 回复 by mb_efeveydv (#137)

*2026-3-4 12:33*

牛啊！

## 回复 by k4y0z (#138)

*2026-3-4 14:30*

666

## 回复 by wx_lll_652 (#139)

*2026-3-7 00:51*

学习学习

## 回复 by wx_coddvccwyh (#140)

*2026-3-7 21:04*

666666

## 回复 by 大白_460230 (#141)

*2026-3-7 21:14*

666

## 回复 by wx_何少_366 (#142)

*2026-3-9 16:16*

牛

## 回复 by hekes (#143)

*2026-3-9 16:19*

看一看

## 回复 by git_843361313113 (#144)

*2026-3-9 23:16*

学习

## 回复 by git_107370xcmore (#145)

*2026-3-16 13:57*

666

## 回复 by mb_xiammaav (#146)

*2026-3-20 03:58*

666

## 回复 by 白毅 (#147)

*2026-3-25 18:50*

看不懂但是点赞了

## 回复 by mb_gbpycqur (#148)

*2026-3-26 21:07*

6

## 回复 by Matchman33 (#149)

*2026-3-27 09:30*

666

## 回复 by mb_gatolgsc (#150)

*2026-3-27 14:02*

支持

## 回复 by 彭彭丁满 (#151)

*2026-3-27 17:46*

666

## 回复 by lackone (#152)

*2026-3-28 12:00*

666

## 回复 by mafengko (#153)

*2026-3-29 08:09*

66666666

## 回复 by mb_ecyhqrqd (#154)

*2026-3-30 02:59*

感谢分享

## 回复 by mb_yresqgiz (#155)

*2026-3-31 18:59*

感谢分享

## 回复 by 小迷糊ddd (#156)

*2026-4-6 22:32*

感谢分享，受教了。

## 回复 by mb_qmpoczzi (#157)

*2026-4-11 11:32*

666

## 回复 by x_power (#158)

*2026-4-11 11:45*

111

## 回复 by mb_ujlbfnqz (#159)

*2026-4-12 15:30*

6666 超级感谢

## 回复 by 毛毛毛毛虫 (#160)

*2026-4-12 19:11*

看看

## 回复 by B.M.K (#161)

*2026-4-12 19:37*

1

## 回复 by mb_eubpihhp (#162)

*2026-5-1 01:54*

大佬666

## 回复 by mb_rcckfzub (#163)

*2026-5-11 10:40*

11

## 回复 by 小童net (#164)

*2026-5-12 03:42*

![image](https://bbs.kanxue.com/view/img/face/022.gif)

## 回复 by Crack999 (#165)

*2026-5-12 14:20*

6666

## 回复 by mb_xbgppumd (#166)

*2026-5-12 17:52*

学习

## 回复 by mb_cjjbbtgt (#167)

*2026-5-13 02:33*

666

## 回复 by admin5 (#168)

*2026-5-13 03:11*

xue 西

## 回复 by mb_lhxrckiu (#169)

*2026-5-17 23:34*

看看

## 回复 by 086Love (#170)

*2026-5-18 11:16*

感谢分享

## 回复 by mb_ccsairor (#171)

*2026-5-18 14:24*

666

## 回复 by mb_vhbswbct (#172)

*2026-5-26 17:41*

666

## 回复 by mb_lgtsulbs (#173)

*2026-5-31 19:54*

6

## 回复 by mb_tecrmqmn (#174)

*2026-5-31 20:20*

1

## 回复 by mb_fogbfnnb (#175)

*2026-6-6 14:56*

666

## 回复 by mb_vvsdmmfc (#176)

*2026-6-13 14:40*

66666666

## 回复 by CROOOW (#177)

*2026-6-18 16:17*

666

## 回复 by wx_小人物有大梦想 (#178)

*2026-6-19 23:11*

111

## 回复 by mb_uekrtlsh (#179)

*2026-6-20 17:34*

666

## 回复 by 闲闲 (#180)

*2026-6-21 12:19*

感谢分享  学习...感谢分享  学习...

## 回复 by mb_vdakxenl (#181)

*2026-7-6 15:32*

感谢分享

## 回复 by 肆意残沙 (#182)

*2026-7-9 21:05*

6

## 回复 by 3cly (#183)

*2026-7-14 14:55*

9

## 回复 by mb_zmitfows (#184)

*2026-7-14 16:05*

466

## 回复 by mb_qdutazbj (#185)

*2026-7-15 04:18*

666

## 回复 by mb_aimiyfrp (#186)

*2026-7-15 08:12*

666

## 回复 by permanent011 (#187)

1

## 回复 by 阿文hx (#188)

666

## 回复 by Towartz (#189)

+1

## 回复 by mb_iucxpcvn (#190)

666新手学这个正好

## 回复 by wx_放心我很好 (#191)

111
