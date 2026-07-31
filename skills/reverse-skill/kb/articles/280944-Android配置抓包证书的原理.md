---
title: Android配置抓包证书的原理
url: https://bbs.kanxue.com/thread-280944.htm
tid: 280944
author: Onlyxiu
date: '2024-03-18'
tags: [Android安全, 其他, 系统相关, 程序开发, 基础理论]
crawled_at: '2026-07-31T14:30:08+08:00'
replies: 2
---

## 一、数字证书的常见格式

数字证书有多种格式，其中一些常见的格式包括：

1. **X.509证书**：
- X.509是最常见的数字证书标准，它定义了公钥证书的格式和相关的验证流程。X.509证书**通常使用DER编码或PEM编码**。
1. **DER (Distinguished Encoding Rules)**：
- DER是**一种二进制编码规则**，通常用于表示X.509证书的二进制形式。
1. **PEM (Privacy Enhanced Mail)**：
- PEM是一种基于文本的编码格式，通常用于在文本协议中传输X.509证书。**PEM格式可以包含DER编码或Base64编码的数据**。
1. **PKCS#12 / PFX (Personal Information Exchange)**：
- PKCS#12是一种文件格式，用于存储和传输私钥、公钥和证书链等信息。PFX是PKCS#12的一种常见扩展名。
1. **PKCS#7 / P7B**：
- PKCS#7是一种数字签名标准，它通常用于签署和验证数据的完整性。P7B是PKCS#7的一种常见扩展名，通常用于存储证书链。
1. **JKS (Java KeyStore)**：
- JKS是Java中用于管理密钥和证书的密钥存储库格式。
1. **JCEKS (Java Cryptography Extension KeyStore)**：
- JCEKS是Java Cryptography Extension中的一种密钥存储库格式，提供了对更高级加密算法的支持。
1. **AC (Attribute Certificate)**：
- AC是一种X.509证书的扩展，用于在X.509证书中包含附加属性信息。

## 二、CER格式数字证书与PEM格式数字证书的转换

### (一) 从PEM到CER的转换：

1. 获取PEM证书文件：首先，你需要有一个PEM格式的数字证书文件。
2. 将PEM证书转换为CER格式：
- 使用合适的工具或者编程语言，读取PEM证书文件中除了 -----BEGIN CERTIFICATE----- 和 -----END CERTIFICATE----- 标记之外的部分。
- 将这段Base64编码的数据解码为二进制数据。
- 将得到的二进制数据保存为一个以.cer为扩展名的文件，这样就得到了CER格式的证书。

> `openssl x509 -outform der -in demo.pem -out demo.cer`
>
>

- openssl x509：使用OpenSSL工具中的x509子命令，用于操作X.509证书。
- -outform der：指定输出格式为DER编码格式。
- -in demo.pem：指定输入文件为demo.pem，即PEM格式的证书文件。
- -out demo.cer：指定输出文件为demo.cer，即DER格式的证书文件。

| 123456789101112131415161718192021222324252627282930 | `-----BEGIN CERTIFICATE-----``MIIFPDCCBCSgAwIBAgIGAYyvnmk8MA0GCSqGSIb3DQEBCwUAMIGiMTMwMQYDVQQD``DCpDaGFybGVzIFByb3h5IENBICgyOCBEZWMgMjAyMywgT05MWVhJVS1QQykxJTAj``BgNVBAsMHGh0dHBzOi8vY2hhcmxlc3Byb3h5LmNvbS9zc2wxETAPBgNVBAoMCFhL``NzIgTHRkMREwDwYDVQQHDAhBdWNrbGFuZDERMA8GA1UECAwIQXVja2xhbmQxCzAJ``BgNVBAYTAk5aMB4XDTIzMTIyNzA4NTA0M1oXDTI0MTIyNjA4NTA0M1owgaIxMzAx``BgNVBAMMKkNoYXJsZXMgUHJveHkgQ0EgKDI4IERlYyAyMDIzLCBPTkxZWElVLVBD``KTElMCMGA1UECwwcaHR0cHM6Ly9jaGFybGVzcHJveHkuY29tL3NzbDERMA8GA1UE``CgwIWEs3MiBMdGQxETAPBgNVBAcMCEF1Y2tsYW5kMREwDwYDVQQIDAhBdWNrbGFu``ZDELMAkGA1UEBhMCTlowggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCJ``TK1VSeT/k60mk8XIXLd/wSvl9XQpb6n2ouoybMj/vGSnr49reuzdZLAX2L4wR4E5``pIzCGGnYOKM0HgY8REiMPGRdPQujxkqlqlMj69/mQiUM6DNuP6QEIMaFqBD64pjd``Jv2X00FR/WTn+hulwA/iQyo43E9/lZ75yIa4eldEJKjLoteZAKrw6FAAEXec7Dfw``mGYvrVUBKBeQsHpSNo547hw1WStmfw7RbFgrOA2HPZb+3nbqAJb/zV2f9xfqRQZr``+H7GEzDv2jDvPGTKEYEe5BAy3xSxWiKsFGfmbJhebfQob08dh5PjJilB/ZZ8Phwe``3SYxpjZorgVmrKSPmdBnAgMBAAGjggF0MIIBcDAPBgNVHRMBAf8EBTADAQH/MIIB``LAYJYIZIAYb4QgENBIIBHROCARlUaGlzIFJvb3QgY2VydGlmaWNhdGUgd2FzIGdl``bmVyYXRlZCBieSBDaGFybGVzIFByb3h5IGZvciBTU0wgUHJveHlpbmcuIElmIHRo``aXMgY2VydGlmaWNhdGUgaXMgcGFydCBvZiBhIGNlcnRpZmljYXRlIGNoYWluLCB0``aGlzIG1lYW5zIHRoYXQgeW91J3JlIGJyb3dzaW5nIHRocm91Z2ggQ2hhcmxlcyBQ``cm94eSB3aXRoIFNTTCBQcm94eWluZyBlbmFibGVkIGZvciB0aGlzIHdlYnNpdGUu``IFBsZWFzZSBzZWUgaHR0cDovL2NoYXJsZXNwcm94eS5jb20vc3NsIGZvciBtb3Jl``IGluZm9ybWF0aW9uLjAOBgNVHQ8BAf8EBAMCAgQwHQYDVR0OBBYEFFMQZywS+KKZ``6b7kqWVDwcw/YbvWMA0GCSqGSIb3DQEBCwUAA4IBAQB9YIDwLnBTHYT8E7cZ1DCd``1scQRak/iZwbTbcmxPLT/Mi/FTKDRNFXvA/3JO/SOZZMGmRU1TGiU1IfMyIIf5YT``yz7iuv1MTs5G8jlJ2iguIsAu4keBda3y9gOyDjGfdya1IXI1BxJV9zjw+uKqQS7k``zP7PEeCsJN41OPy1mgNuCxsLC1EvvilvTH7Q4fJGTtu/ImIgdeyIThuEc6m/hswv``DjAfGw9LNBJJNgQqiKid/lBp68HEDVTrsjEtRc9wnfiqlKXQlZnnt17vV8I8Bxdp``+ihpOt44gfR79Z9qPuScDejMYb3vCySsbOApPlS327ty4Abf1dlxFBVsjWbmQoV0``-----END CERTIFICATE-----` |
|-|-|

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162 | `#define _CRT_SECURE_NO_WARNINGS` `#include <iostream>``#include <fstream>``#include <openssl/pem.h>``#include <openssl/x509.h>``#include <openssl/bio.h>``#include <openssl/applink.c>``int` `main() {``// 打开PEM格式证书文件``FILE``* pem_file =``fopen``(``"demo.pem"``,``"r"``);``if` `(!pem_file) {``std::cerr <<``"Failed to open PEM file."` `<< std::endl;``return` `1;``}` `// 创建BIO对象``BIO* pem_bio = BIO_new_fp(pem_file, BIO_CLOSE);``if` `(!pem_bio) {``std::cerr <<``"Failed to create BIO for PEM file."` `<< std::endl;``fclose``(pem_file);``return` `1;``}` `// 读取PEM格式证书``X509* cert = PEM_read_bio_X509(pem_bio, nullptr, nullptr, nullptr);``if` `(!cert) {``std::cerr <<``"Failed to read PEM certificate."` `<< std::endl;``BIO_free(pem_bio);``fclose``(pem_file);``return` `1;``}` `// 创建DER格式证书文件``FILE``* der_file =``fopen``(``"demo.cer"``,``"wb"``);``if` `(!der_file) {``std::cerr <<``"Failed to create DER file."` `<< std::endl;``BIO_free(pem_bio);``fclose``(pem_file);``X509_free(cert);``return` `1;``}` `// 将X509证书编码为DER格式并写入文件``if` `(i2d_X509_fp(der_file, cert) == 0) {``std::cerr <<``"Failed to write DER certificate."` `<< std::endl;``fclose``(der_file);``BIO_free(pem_bio);``fclose``(pem_file);``X509_free(cert);``return` `1;``}` `// 释放资源``fclose``(der_file);``BIO_free(pem_bio);``fclose``(pem_file);``X509_free(cert);` `std::cout <<``"Conversion completed successfully."` `<< std::endl;``return` `0;``}` |
|-|-|

转换得到的cer格式数字证书与从Charles导出的cer格式数字证书一致

![image](https://bbs.kanxue.com/upload/attach/202403/957322_BWQGFWAFSPYK46P.jpg)

### (二) 从CER到PEM的转换：

1. 获取CER证书文件：首先，你需要有一个CER格式的数字证书文件。
2. 将CER证书转换为PEM格式：
- 使用合适的工具或者编程语言，读取CER证书的二进制数据。
- 将二进制数据进行Base64编码。
- 在编码后的数据前添加 -----BEGIN CERTIFICATE----- 标记，并在后面添加 -----END CERTIFICATE----- 标记。
- 保存这个带有标记的数据为一个以.pem为扩展名的文件，这样就得到了PEM格式的证书。

> `openssl x509 -inform der -in demo.cer -out demo.pem`
>
>

转换得到的pem格式数字证书与从Charles导出的pem格式数字证书一致

![image](https://bbs.kanxue.com/upload/attach/202403/957322_P2XQH385R9TDBUE.jpg)

## 三、计算数字证书的hash值

在移动设备上安装证书时，可能会导致证书文件名发生变化的原因有几个可能：

1. 系统生成的哈希值命名：在某些情况下，移动设备会对安装的证书文件进行哈希计算，并将生成的哈希值作为文件名。这个哈希值通常是证书内容的哈希，用于唯一标识该证书。
2. 系统要求的特定文件名格式：某些移动设备可能对证书文件名有特定的要求，需要符合一定的命名格式。例如，在 Android 系统中，系统会要求证书文件名为 <hash>.0 的格式，其中 <hash> 是证书内容的哈希值。

所以我们可以进行手机更改文件名的,将原文件名修改为<hash>.0

对于.pem证书

```cpp
mv cacert.pem `openssl x509 -inform PEM -subject_hash_old -in cacert.pem  |head -1`'.0'
```

对于.cer证书

```cpp
mv cacert.cer `openssl x509 -inform DER -subject_hash_old -in cacert.cer |head -1`'.0'
```

## 四、证书的加载流程和原理

在 Android 系统中，证书的管理和解析是由 Android 的安全框架和 Keystore 系统来完成的。Android 系统中的证书管理主要涉及以下几个方面：

1. **安全框架（Security Framework）**：Android 的安全框架提供了一组 API 和服务，用于实现各种安全功能，包括证书的管理和使用。这些功能包括 SSL/TLS 连接、数字签名、证书验证等。安全框架中的组件负责解析和处理证书文件，包括 PEM 和 DER 格式的证书。
2. **Keystore 系统**：Android 的 Keystore 是一个安全的存储库，用于存储密钥、证书和其他敏感信息。Keystore 提供了一种安全的方式来存储和管理证书，以防止证书的私钥被恶意应用程序或攻击者访问。Keystore 通过系统级别的安全保护来保护证书的私钥，例如硬件支持的安全元素（如 Trusted Execution Environment）或安全软件容器（如 StrongBox）。
3. **系统证书存储（System Certificate Store）**：Android 系统还提供了一个系统级别的证书存储，用于存储系统信任的根证书和其他受信任的证书。这些证书通常用于验证 SSL/TLS 连接或数字签名。Android 系统会在启动时加载系统证书存储，并将其中的证书用于系统级别的安全功能。

在 Android 系统中，证书的解析和使用通常涉及以下步骤：

1. **证书加载**：Android 系统会在启动时加载系统证书存储中的根证书和其他受信任的证书。这些证书被存储在系统的证书存储中，并由系统的安全框架和 Keystore 系统来管理。
- **KeyStore.getInstance()**：获取 KeyStore 实例，用于加载和管理证书和密钥。
- **KeyStore.load()**：从文件或输入流中加载证书和密钥到 KeyStore 中。
- **CertificateFactory.getInstance()**：获取 CertificateFactory 实例，用于解析证书。
- **CertificateFactory.generateCertificate()**：从输入流中生成证书对象。
- **Resources.openRawResource()**：在 Android 应用程序中加载资源文件，如证书文件。
1. **证书解析**：当应用程序需要使用证书时，系统会调用安全框架中的证书解析组件来解析证书文件。这些组件能够识别证书的格式，并提取其中的公钥、颁发者信息、有效期等关键信息。
- **X509Certificate** 类：表示 X.509 标准的证书对象，提供了获取证书信息的方法，如获取公钥、颁发者信息、有效期等。
- **CertificateFactory.generateCertificate()**：从输入流中生成证书对象，可用于解析证书。
1. **证书验证**：在建立安全连接或者验证数字签名时，系统会使用证书解析得到的信息来验证证书的有效性。这包括验证证书链、检查证书的有效期、验证颁发者的签名等步骤。
- **TrustManagerFactory.getInstance()**：获取 TrustManagerFactory 实例，用于创建 TrustManager 实例，用于验证服务器端证书。
- **KeyStore.getInstance()**：获取 KeyStore 实例，用于获取系统和应用程序信任的根证书。
- **SSLContext.getInstance()**：获取 SSLContext 实例，用于创建 SSL/TLS 连接。
- **SSLContext.init()**：使用 TrustManager 和 KeyManager 初始化 SSLContext。
- **SSLSocketFactory.setHostnameVerifier()**：设置主机名验证器，用于验证服务器主机名。
1. **证书存储**：对于应用程序生成的证书或密钥，系统会使用 Keystore 系统来安全地存储和管理。Keystore 会将这些证书和密钥存储在安全的硬件或软件容器中，以防止它们被未经授权的应用程序或攻击者访问。

总的来说，在 Android 系统中，证书的管理和使用是由安全框架、Keystore 系统和系统证书存储共同实现的。这些组件能够保障证书的安全性和可靠性，并在系统级别上提供安全的证书管理和使用功能。因此，当你将 .pem 格式的证书文件放入系统证书目录时，系统会自动将其转换为二进制格式的 .cer 格式的证书文件，以便系统能够更方便地处理和使用。这种转换通常是由系统的证书管理工具或者证书存储服务自动完成的，用户无需手动操作。

## 五、配置代理实操

### (一) 使用手机程序安装pem证书

#### 1. 选择cacert.pem数字证书进行安装

![image](https://bbs.kanxue.com/upload/attach/202403/957322_WTN7UHTG8B6S66G.jpg)

![image](https://bbs.kanxue.com/upload/attach/202403/957322_TX4AN4EYP3VBPQ3.jpg)

![image](https://bbs.kanxue.com/upload/attach/202403/957322_ZPZNPAFYFZ3JYBG.jpg)

#### 2. 命名为pem

![image](https://bbs.kanxue.com/upload/attach/202403/957322_HFFM7X9MJSWXE9N.jpg)

![image](https://bbs.kanxue.com/upload/attach/202403/957322_WWVBBUY2UX8KYT9.jpg)

#### 3. 查看证书

![image](https://bbs.kanxue.com/upload/attach/202403/957322_NTZNFN66YD7PWMB.jpg)

就会发现该文件已转换为cer二进制文件的数字证书

#### 4. 导出该文件进行原cer数字证书对比

![image](https://bbs.kanxue.com/upload/attach/202403/957322_DT5AC75VB5BT8U7.jpg)

结果发现pem格式数字证书的安装，经过系统的证书安装程序,会将pem格式数字证书转化为cer格式数字证书。

### (二) 用户证书抓包测试

抓包效果：

![image](https://bbs.kanxue.com/upload/attach/202403/957322_BFMC2RFVTWC6KX4.jpg)

### (三) 用户证书目录转存储系统系统证书目录

通过Move_Certificates-v1.9模块将用户证书目录下的证书转存到系统证书目录中去。

![image](https://bbs.kanxue.com/upload/attach/202403/957322_S2PSGS2XHJACRZR.jpg)

![image](https://bbs.kanxue.com/upload/attach/202403/957322_9SUC33D6MW2ZFQB.jpg)

### (四) 系统证书抓包测试

SSL证书报错,相对与用户证书抓包效果好了很多。

![image](https://bbs.kanxue.com/upload/attach/202403/957322_6TDEE8PGG8EYY6X.jpg)

### (五) 手动推送pem证书到系统目录下

#### 1. 将pem证书推动到系统目录下

将证书推送到Move_Certificates模块目录下

![image](https://bbs.kanxue.com/upload/attach/202403/957322_GPQADM42SZ6EG4G.jpg)

#### 2. 并修改权限为644

![image](https://bbs.kanxue.com/upload/attach/202403/957322_98TWST77K5GJPMA.jpg)

#### 3. 重启手机,等待Move_Certificates插件将证书重定向到系统目录证书下

![image](https://bbs.kanxue.com/upload/attach/202403/957322_A4AS8WY2T6VSAJQ.jpg)

#### 4. 抓包效果

![image](https://bbs.kanxue.com/upload/attach/202403/957322_83GN7RMKS8Z2RJJ.jpg)

### (六) 制作与原系统证书一致的pem格式数字证书

#### 1. 源系统证书处理pem格式数字证书除了base64,还有签名等信息

```cpp
platina:/system/etc/security/cacerts # cat 7892ad52.0
-----BEGIN CERTIFICATE-----
MIIClDCCAhqgAwIBAgIILCmcWxbtBZUwCgYIKoZIzj0EAwIwfzELMAkGA1UEBhMC
VVMxDjAMBgNVBAgMBVRleGFzMRAwDgYDVQQHDAdIb3VzdG9uMRgwFgYDVQQKDA9T
U0wgQ29ycG9yYXRpb24xNDAyBgNVBAMMK1NTTC5jb20gRVYgUm9vdCBDZXJ0aWZp
Y2F0aW9uIEF1dGhvcml0eSBFQ0MwHhcNMTYwMjEyMTgxNTIzWhcNNDEwMjEyMTgx
NTIzWjB/MQswCQYDVQQGEwJVUzEOMAwGA1UECAwFVGV4YXMxEDAOBgNVBAcMB0hv
dXN0b24xGDAWBgNVBAoMD1NTTCBDb3Jwb3JhdGlvbjE0MDIGA1UEAwwrU1NMLmNv
bSBFViBSb290IENlcnRpZmljYXRpb24gQXV0aG9yaXR5IEVDQzB2MBAGByqGSM49
AgEGBSuBBAAiA2IABKoSR5CYG/vvw0AHgyBO8TCCogbR8pKGYfL2IWjKAMTH6kMA
VIbc/R/fALhBYlzccBYy3h+Z1MzFB8gIH2EWB1E9fVwHU+M1OIzfzZ/ZLg1Kthku
WnBaBu2+8KGwytAJKaNjMGEwHQYDVR0OBBYEFFvKXuXe0oGqzagtZFG22XKbl+ZP
MA8GA1UdEwEB/wQFMAMBAf8wHwYDVR0jBBgwFoAUW8pe5d7SgarNqC1kUbbZcpuX
5k8wDgYDVR0PAQH/BAQDAgGGMAoGCCqGSM49BAMCA2gAMGUCMQCK5kCJN+vp1RPZ
ytRrJPOwPYdGWBrssd9v+1a6cGvHOMzosYxPD/fxZ3YOg9AeUY8CMD32IygmTMZg
h5Mmm7I1HrrW9zzRHM76JTymGoEVW/MSD2zuZYrJh6j5B+BimoxcSg==
-----END CERTIFICATE-----
Certificate:
    Data:
        Version: 3 (0x2)
        Serial Number: 3182246526754555285 (0x2c299c5b16ed0595)
    Signature Algorithm: ecdsa-with-SHA256
        Issuer: C=US, ST=Texas, L=Houston, O=SSL Corporation, CN=SSL.com EV Root Certification Authority ECC
        Validity
            Not Before: Feb 12 18:15:23 2016 GMT
            Not After : Feb 12 18:15:23 2041 GMT
        Subject: C=US, ST=Texas, L=Houston, O=SSL Corporation, CN=SSL.com EV Root Certification Authority ECC
        Subject Public Key Info:
            Public Key Algorithm: id-ecPublicKey
                Public-Key: (384 bit)
                pub:
                    04:aa:12:47:90:98:1b:fb:ef:c3:40:07:83:20:4e:
                    f1:30:82:a2:06:d1:f2:92:86:61:f2:f6:21:68:ca:
                    00:c4:c7:ea:43:00:54:86:dc:fd:1f:df:00:b8:41:
                    62:5c:dc:70:16:32:de:1f:99:d4:cc:c5:07:c8:08:
                    1f:61:16:07:51:3d:7d:5c:07:53:e3:35:38:8c:df:
                    cd:9f:d9:2e:0d:4a:b6:19:2e:5a:70:5a:06:ed:be:
                    f0:a1:b0:ca:d0:09:29
                ASN1 OID: secp384r1
                NIST CURVE: P-384
        X509v3 extensions:
            X509v3 Subject Key Identifier:
                5B:CA:5E:E5:DE:D2:81:AA:CD:A8:2D:64:51:B6:D9:72:9B:97:E6:4F
            X509v3 Basic Constraints: critical
                CA:TRUE
            X509v3 Authority Key Identifier:
                keyid:5B:CA:5E:E5:DE:D2:81:AA:CD:A8:2D:64:51:B6:D9:72:9B:97:E6:4F

            X509v3 Key Usage: critical
                Digital Signature, Certificate Sign, CRL Sign
    Signature Algorithm: ecdsa-with-SHA256
         30:65:02:31:00:8a:e6:40:89:37:eb:e9:d5:13:d9:ca:d4:6b:
         24:f3:b0:3d:87:46:58:1a:ec:b1:df:6f:fb:56:ba:70:6b:c7:
         38:cc:e8:b1:8c:4f:0f:f7:f1:67:76:0e:83:d0:1e:51:8f:02:
         30:3d:f6:23:28:26:4c:c6:60:87:93:26:9b:b2:35:1e:ba:d6:
         f7:3c:d1:1c:ce:fa:25:3c:a6:1a:81:15:5b:f3:12:0f:6c:ee:
         65:8a:c9:87:a8:f9:07:e0:62:9a:8c:5c:4a
SHA1 Fingerprint=4C:DD:51:A3:D1:F5:20:32:14:B0:C6:C5:32:23:03:91:C7:46:42:6D
platina:/system/etc/security/cacerts #
```

#### 2. 生成系统系统预设格式证书文件

对于.pem证书

```cpp
openssl x509 -inform PEM -text -in cacert.pem > 7591945e.0
```

对于.cer证书

```cpp
openssl x509 -inform DER -text -in cacert.cer > 7591945e.0
```

#### 3. 编辑生成的文件

把 -----BEGIN CERTIFICATE----- 到最后的这部分移动到开头

```cpp
-----BEGIN CERTIFICATE-----
MIIFPDCCBCSgAwIBAgIGAYyvnmk8MA0GCSqGSIb3DQEBCwUAMIGiMTMwMQYDVQQD
DCpDaGFybGVzIFByb3h5IENBICgyOCBEZWMgMjAyMywgT05MWVhJVS1QQykxJTAj
BgNVBAsMHGh0dHBzOi8vY2hhcmxlc3Byb3h5LmNvbS9zc2wxETAPBgNVBAoMCFhL
NzIgTHRkMREwDwYDVQQHDAhBdWNrbGFuZDERMA8GA1UECAwIQXVja2xhbmQxCzAJ
BgNVBAYTAk5aMB4XDTIzMTIyNzA4NTA0M1oXDTI0MTIyNjA4NTA0M1owgaIxMzAx
BgNVBAMMKkNoYXJsZXMgUHJveHkgQ0EgKDI4IERlYyAyMDIzLCBPTkxZWElVLVBD
KTElMCMGA1UECwwcaHR0cHM6Ly9jaGFybGVzcHJveHkuY29tL3NzbDERMA8GA1UE
CgwIWEs3MiBMdGQxETAPBgNVBAcMCEF1Y2tsYW5kMREwDwYDVQQIDAhBdWNrbGFu
ZDELMAkGA1UEBhMCTlowggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCJ
TK1VSeT/k60mk8XIXLd/wSvl9XQpb6n2ouoybMj/vGSnr49reuzdZLAX2L4wR4E5
pIzCGGnYOKM0HgY8REiMPGRdPQujxkqlqlMj69/mQiUM6DNuP6QEIMaFqBD64pjd
Jv2X00FR/WTn+hulwA/iQyo43E9/lZ75yIa4eldEJKjLoteZAKrw6FAAEXec7Dfw
mGYvrVUBKBeQsHpSNo547hw1WStmfw7RbFgrOA2HPZb+3nbqAJb/zV2f9xfqRQZr
+H7GEzDv2jDvPGTKEYEe5BAy3xSxWiKsFGfmbJhebfQob08dh5PjJilB/ZZ8Phwe
3SYxpjZorgVmrKSPmdBnAgMBAAGjggF0MIIBcDAPBgNVHRMBAf8EBTADAQH/MIIB
LAYJYIZIAYb4QgENBIIBHROCARlUaGlzIFJvb3QgY2VydGlmaWNhdGUgd2FzIGdl
bmVyYXRlZCBieSBDaGFybGVzIFByb3h5IGZvciBTU0wgUHJveHlpbmcuIElmIHRo
aXMgY2VydGlmaWNhdGUgaXMgcGFydCBvZiBhIGNlcnRpZmljYXRlIGNoYWluLCB0
aGlzIG1lYW5zIHRoYXQgeW91J3JlIGJyb3dzaW5nIHRocm91Z2ggQ2hhcmxlcyBQ
cm94eSB3aXRoIFNTTCBQcm94eWluZyBlbmFibGVkIGZvciB0aGlzIHdlYnNpdGUu
IFBsZWFzZSBzZWUgaHR0cDovL2NoYXJsZXNwcm94eS5jb20vc3NsIGZvciBtb3Jl
IGluZm9ybWF0aW9uLjAOBgNVHQ8BAf8EBAMCAgQwHQYDVR0OBBYEFFMQZywS+KKZ
6b7kqWVDwcw/YbvWMA0GCSqGSIb3DQEBCwUAA4IBAQB9YIDwLnBTHYT8E7cZ1DCd
1scQRak/iZwbTbcmxPLT/Mi/FTKDRNFXvA/3JO/SOZZMGmRU1TGiU1IfMyIIf5YT
yz7iuv1MTs5G8jlJ2iguIsAu4keBda3y9gOyDjGfdya1IXI1BxJV9zjw+uKqQS7k
zP7PEeCsJN41OPy1mgNuCxsLC1EvvilvTH7Q4fJGTtu/ImIgdeyIThuEc6m/hswv
DjAfGw9LNBJJNgQqiKid/lBp68HEDVTrsjEtRc9wnfiqlKXQlZnnt17vV8I8Bxdp
+ihpOt44gfR79Z9qPuScDejMYb3vCySsbOApPlS327ty4Abf1dlxFBVsjWbmQoV0
-----END CERTIFICATE-----
Certificate:
    Data:
        Version: 3 (0x2)
        Serial Number: 1703753443644 (0x18caf9e693c)
        Signature Algorithm: sha256WithRSAEncryption
        Issuer: CN = "Charles Proxy CA (28 Dec 2023, ONLYXIU-PC)", OU = https://charlesproxy.com/ssl, O = XK72 Ltd, L = Auckland, ST = Auckland, C = NZ
        Validity
            Not Before: Dec 27 08:50:43 2023 GMT
            Not After : Dec 26 08:50:43 2024 GMT
        Subject: CN = "Charles Proxy CA (28 Dec 2023, ONLYXIU-PC)", OU = https://charlesproxy.com/ssl, O = XK72 Ltd, L = Auckland, ST = Auckland, C = NZ
        Subject Public Key Info:
            Public Key Algorithm: rsaEncryption
                Public-Key: (2048 bit)
                Modulus:
                    00:89:4c:ad:55:49:e4:ff:93:ad:26:93:c5:c8:5c:
                    b7:7f:c1:2b:e5:f5:74:29:6f:a9:f6:a2:ea:32:6c:
                    c8:ff:bc:64:a7:af:8f:6b:7a:ec:dd:64:b0:17:d8:
                    be:30:47:81:39:a4:8c:c2:18:69:d8:38:a3:34:1e:
                    06:3c:44:48:8c:3c:64:5d:3d:0b:a3:c6:4a:a5:aa:
                    53:23:eb:df:e6:42:25:0c:e8:33:6e:3f:a4:04:20:
                    c6:85:a8:10:fa:e2:98:dd:26:fd:97:d3:41:51:fd:
                    64:e7:fa:1b:a5:c0:0f:e2:43:2a:38:dc:4f:7f:95:
                    9e:f9:c8:86:b8:7a:57:44:24:a8:cb:a2:d7:99:00:
                    aa:f0:e8:50:00:11:77:9c:ec:37:f0:98:66:2f:ad:
                    55:01:28:17:90:b0:7a:52:36:8e:78:ee:1c:35:59:
                    2b:66:7f:0e:d1:6c:58:2b:38:0d:87:3d:96:fe:de:
                    76:ea:00:96:ff:cd:5d:9f:f7:17:ea:45:06:6b:f8:
                    7e:c6:13:30:ef:da:30:ef:3c:64:ca:11:81:1e:e4:
                    10:32:df:14:b1:5a:22:ac:14:67:e6:6c:98:5e:6d:
                    f4:28:6f:4f:1d:87:93:e3:26:29:41:fd:96:7c:3e:
                    1c:1e:dd:26:31:a6:36:68:ae:05:66:ac:a4:8f:99:
                    d0:67
                Exponent: 65537 (0x10001)
        X509v3 extensions:
            X509v3 Basic Constraints: critical
                CA:TRUE
            Netscape Comment:
                ....This Root certificate was generated by Charles Proxy for SSL Proxying. If this certificate is part of a certificate chain, this means that you're browsing through Charles Proxy with SSL Proxying enabled for this website. Please see http://charlesproxy.com/ssl for more information.
            X509v3 Key Usage: critical
                Certificate Sign
            X509v3 Subject Key Identifier:
                53:10:67:2C:12:F8:A2:99:E9:BE:E4:A9:65:43:C1:CC:3F:61:BB:D6
    Signature Algorithm: sha256WithRSAEncryption
    Signature Value:
        7d:60:80:f0:2e:70:53:1d:84:fc:13:b7:19:d4:30:9d:d6:c7:
        10:45:a9:3f:89:9c:1b:4d:b7:26:c4:f2:d3:fc:c8:bf:15:32:
        83:44:d1:57:bc:0f:f7:24:ef:d2:39:96:4c:1a:64:54:d5:31:
        a2:53:52:1f:33:22:08:7f:96:13:cb:3e:e2:ba:fd:4c:4e:ce:
        46:f2:39:49:da:28:2e:22:c0:2e:e2:47:81:75:ad:f2:f6:03:
        b2:0e:31:9f:77:26:b5:21:72:35:07:12:55:f7:38:f0:fa:e2:
        aa:41:2e:e4:cc:fe:cf:11:e0:ac:24:de:35:38:fc:b5:9a:03:
        6e:0b:1b:0b:0b:51:2f:be:29:6f:4c:7e:d0:e1:f2:46:4e:db:
        bf:22:62:20:75:ec:88:4e:1b:84:73:a9:bf:86:cc:2f:0e:30:
        1f:1b:0f:4b:34:12:49:36:04:2a:88:a8:9d:fe:50:69:eb:c1:
        c4:0d:54:eb:b2:31:2d:45:cf:70:9d:f8:aa:94:a5:d0:95:99:
        e7:b7:5e:ef:57:c2:3c:07:17:69:fa:28:69:3a:de:38:81:f4:
        7b:f5:9f:6a:3e:e4:9c:0d:e8:cc:61:bd:ef:0b:24:ac:6c:e0:
        29:3e:54:b7:db:bb:72:e0:06:df:d5:d9:71:14:15:6c:8d:66:
        e6:42:85:74
```

![image](https://bbs.kanxue.com/upload/attach/202403/957322_4M8DKJA6WXHVV8X.jpg)

#### 4. 抓包效果

![image](https://bbs.kanxue.com/upload/attach/202403/957322_R5EGXT66HSBSX3F.jpg)

## 六、总结

在 Android 系统中，证书的管理和使用是由安全框架、Keystore 系统和系统证书存储共同实现的。这些组件能够保障证书的安全性和可靠性，并在系统级别上提供安全的证书管理和使用功能。因此，当你将 .pem 格式的证书文件放入系统证书目录时，系统会自动将其转换为二进制格式的 .cer 格式的证书文件，以便系统能够更方便地处理和使用。这种转换通常是由系统的证书管理工具或者证书存储服务自动完成的，用户无需手动操作。因此，使用上述方式所配置的证书代理，抓包效果是差不多的。

---

# 回复

## 回复 by 秋狝 (#2)

*2024-3-19 11:25*

感谢分享

## 回复 by tigris (#3)

*2024-3-30 22:50*

感谢分享
