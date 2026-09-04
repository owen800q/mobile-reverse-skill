# Hago — Username/Password Login API (static analysis)

> **Scope & authorization.** Defensive/research documentation of how the *client*
> builds its own login request, produced with `reverse-skill` in **pure static
> analysis** mode (jadx decompilation only — no device, no traffic capture, no
> live request against Hago servers). It documents a client-side scheme so it can
> be understood and verified; it is not a tool for accessing third-party accounts.
> Use only against apps/accounts you are authorized to test.

## Target

| | |
|-|-|
| App | **Hago** |
| Package | `com.yy.hiyo` |
| Version | 5.54.0 (versionCode 52428), targetSdk 35 |
| Source | XAPK (base `com.yy.hiyo.apk` + arm64/armeabi splits) |
| Feature | Login by **phone number + password** (Hago has no separate "username"; the account identifier for password login is the phone number). Internal login type name: `PhonePwdLogin` (mode 1) |
| Method | jadx 1.5.0 on `classes10.dex` (login module) and `classes6.dex` (base utils / `UriProvider`) |
| Prior art | KB search verdict `NONE` — original analysis |

## TL;DR

```
POST https://i.ihago.net/uaas/login/passwordAuth
Content-Type: application/x-www-form-urlencoded   (okhttp POST + param map)

mobile         = <countryCode><phoneNumber>          e.g. 5511987654321
country_code   = <countryCode>                        e.g. 55
password       = SHA256(rawPassword)                  lowercase hex (64 chars)
set_password   = 1
timestamp      = <System.currentTimeMillis()>         ms, as string
ts             = Base64( 3DES-CBC-encrypt(timestamp) ) see "ts signature" below
device_id      = <hdid>                               q.b()
dev_type       = 11
appId          = ikxd
app            = hago
sim_country, sys_country, network_country, sys_lang, vpn   (locale/env, from LoginUtil.b)
[guest_s_t, guest_c_auth]  only when a guest session already exists
```

There is **no request-signing header** (no `X-Sign`/HMAC header). The only
credential material is in the body: the password is **SHA-256 hashed**, and the
`ts` field is a **3DES-encrypted timestamp** keyed by a value derived from the
password. All crypto is standard JCE in Java (`com.yy.base.utils`) — none of it
is in native code.

## Call path (UI → network)

```
PhoneLoginWindow.getGoActionParam()            // com/yy/hiyo/login/phone/windows/PhoneLoginWindow.java
   mode==1: gVar.m(passwordItem.getPasswordText())   // password -> h00.g.confirmPassword
            gVar.n/o(country/countryCode); gVar.r(phoneNumFormat)
   -> h.onGoAction(gVar) -> h.bO(gVar)          // com/yy/hiyo/login/phone/h.java:610
        this.a.QK().Y(phone, countryCode, null, gVar.getConfirmPassword(), null, cb)
   -> LoginRequestManager.Y(...)                // com/yy/hiyo/login/request/LoginRequestManager.java:1713
        v.q(new q(cb, phone, null, password, null, countryCode))
   -> q.run()                                   // LoginRequestManager.java:948
        u uVar; uVar.e=phone; uVar.h=password; uVar.j=1; uVar.c=UriProvider.F (=passwordAuth)
        uVar.f=countryCode
   -> LoginRequestManager.S(uVar)               // LoginRequestManager.java:1476
        Map body = K(uVar); okhttp g.I(url, body, headers).method(POST)
   -> LoginRequestManager.K(uVar)               // LoginRequestManager.java:1258  <-- body built here
```

`q.run()` (LoginRequestManager.java:966-990) also selects the endpoint: when no
SMS code is present it uses `UriProvider.F` (`passwordAuth`) with `uVar.j = 1`;
the SMS-code path uses `UriProvider.v` instead.

## Endpoint resolution

`com/yy/appbase/envsetting/uriprovider/UriProvider.java`:

```java
a = "https://i.ihago.net/uaas";          // line 161  (production uaas gateway)
F = a + "/login/passwordAuth";           // line 190
```

⇒ **`https://i.ihago.net/uaas/login/passwordAuth`**

(Hard-coded test peers also exist in the same class: `O =
http://47.75.242.132/uaas/login/passwordAuth`, `P =
http://47.52.230.226/uaas/login/passwordAuth`; and a `str2`-templated debug form
`"http://" + str2 + "/uaas/login/passwordAuth"`. Production is `i.ihago.net`.)

## Body construction — `LoginRequestManager.K(u)` (lines 1258-1327)

Verbatim (key lines):

```java
String valueOf = String.valueOf(System.currentTimeMillis());   // timestamp
String str2   = uVar.f + uVar.e;                               // country_code + phone
String k2     = k();                                           // device_id (q.b() hdid)
String str3   = uVar.h;                                        // raw password (pwd login)
String str4   = uVar.i;                                        // null for pwd login
if (q1.G(str4) && q1.H(str3)) {          // str4 blank && password non-blank
    str4 = a1.g(str3);                   // str4 = SHA256(rawPassword)
    uVar.i = str4;
}
if (q1.H(str4)) {
    hashMap.put("password", str4);       // password = SHA256(rawPassword)
    hashMap.put("set_password", "1");
    str = a1.g(str4);                    // secret = SHA256(SHA256(rawPassword))
}
...
hashMap.put("mobile", str2);
hashMap.put("country_code", uVar.f);
hashMap.put("device_id", k2);
hashMap.put("dev_type", "11");
hashMap.put("timestamp", valueOf);
b2 = com.yy.base.utils.k.b(valueOf, str); // ts = 3DES(timestamp, key=secret)
hashMap.put("ts", b2);
hashMap.put("appId", "ikxd");
hashMap.put("app", "hago");
com.yy.hiyo.loginrequest.l.b(hashMap);    // + sim_country/sys_country/network_country/sys_lang/vpn
```

(`q1.G` = is-blank, `q1.H` = is-not-blank — verified in `com/yy/base/utils/q1.java`.)

`LoginUtil.b` (`com/yy/hiyo/loginrequest/l.java:36`) appends: `sim_country`,
`sys_country`, `network_country` (from `SystemUtils.m/i/l`), `sys_lang`, and
`vpn` (`"1"`/`"0"` from `SystemUtils.v()`).

The request is dispatched as **POST** with the map as the form body
(`com/yy/base/okhttp/g.java` `I()` → `RequestMethod.POST`, `.method(POST, map)`).
The per-request hook `d.g()` only sets a retry strategy + `BizScenc.NORMAL_LOGIN`
group; `LoginRequestManager.O()` returns the header map unchanged — **no signing
header is added.**

## Cryptographic primitives (fingerprinted)

### 1. Password hash — SHA-256  (`com/yy/base/utils/a1.java`)

```java
public static String g(String str) { return d(str, "SHA-256"); }

private static String d(String str, String algo) {
    MessageDigest md = MessageDigest.getInstance(algo);   // "SHA-256"
    md.update(str.getBytes("UTF-8"));
    return c(md.digest());                                 // lowercase hex
}
private static String c(byte[] b) {   // Integer.toHexString(x & 255), zero-padded
    ... }
```

- **`password` field** = `SHA256(rawPassword)` UTF-8, lowercase hex, 64 chars.
- **`secret`** (used as the 3DES key for `ts`) = `SHA256(SHA256(rawPassword))`
  = `a1.g` applied twice.

Fingerprint: literal `MessageDigest.getInstance("SHA-256")` + manual lowercase-hex
encoder. Confidence **high** (unambiguous JCE API string).

### 2. `ts` signature — 3DES (DESede/CBC/PKCS5Padding)  (`com/yy/base/utils/k.java`)

```java
public static String b(String data, String key) throws Exception {   // data=timestamp, key=secret
    SecretKey sk = SecretKeyFactory.getInstance("desede")
                       .generateSecret(new DESedeKeySpec(key.getBytes()));
    Cipher c = Cipher.getInstance("desede/CBC/PKCS5Padding");
    c.init(Cipher.ENCRYPT_MODE, sk, new IvParameterSpec("01234567".getBytes()));
    return b.f(c.doFinal(data.getBytes("utf-8")), 2);      // Base64.encode(..., 2) = NO_WRAP
}
```

- **`ts`** = `Base64_NO_WRAP( 3DES-CBC-encrypt( data = timestampString,
  key = DESedeKeySpec(secret.getBytes())  // first 24 ASCII bytes of the 64-char hex secret,
  iv = ASCII "01234567" ) )`.
- `b.f(x, 2)` → `Base64.encode(x, 2)` (`android.util.Base64`, flag `NO_WRAP`),
  confirmed in `com/yy/base/utils/b.java`.

Fingerprint: literal `Cipher.getInstance("desede/CBC/PKCS5Padding")` +
`SecretKeyFactory.getInstance("desede")` + `DESedeKeySpec` + fixed IV `01234567`.
Confidence **high**.

**Why `ts` exists (interpretation):** the server stores the password as its
SHA-256 hash, so it can recompute `secret = SHA256(password_hash)`, 3DES-decrypt
`ts`, and check the recovered timestamp against the `timestamp` field. This binds
the request to *both* the password and a fresh timestamp (anti-replay / integrity)
without ever sending the raw password. It is an application-layer check on top of
TLS, not a substitute for it.

## Reference reconstruction (documentation only — not executed against any server)

```python
import hashlib, base64, time
from Crypto.Cipher import DES3            # pip install pycryptodome
from Crypto.Util.Padding import pad

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()      # a1.g

def ts_field(timestamp: str, secret_hex: str) -> str:         # k.b
    key = secret_hex.encode("ascii")[:24]                     # DESedeKeySpec -> first 24 bytes
    cipher = DES3.new(key, DES3.MODE_CBC, iv=b"01234567")
    ct = cipher.encrypt(pad(timestamp.encode("utf-8"), 8))    # PKCS5 == PKCS7 for 8-byte block
    return base64.b64encode(ct).decode()                      # NO_WRAP

def build_password_login_body(phone, country_code, raw_password, device_id):
    pwd_hash = sha256_hex(raw_password)                       # password field
    secret   = sha256_hex(pwd_hash)                           # SHA256(SHA256(pwd))
    timestamp = str(int(time.time() * 1000))
    return {
        "mobile":       f"{country_code}{phone}",
        "country_code": country_code,
        "password":     pwd_hash,
        "set_password": "1",
        "timestamp":    timestamp,
        "ts":           ts_field(timestamp, secret),
        "device_id":    device_id,
        "dev_type":     "11",
        "appId":        "ikxd",
        "app":          "hago",
        # + sim_country / sys_country / network_country / sys_lang / vpn (device locale/env)
    }
# POST as application/x-www-form-urlencoded to https://i.ihago.net/uaas/login/passwordAuth
```

## Verification status

Pure static analysis: every claim above is traced to a verbatim decompiled line
(logged in the `reverse-skill` ledger at rung **REACHABLE**; crypto primitives are
**high**-confidence hypotheses backed by literal JCE fingerprints). The scheme was
**not** replayed against Hago's servers — doing so would exercise a real account
and is out of scope for an authorized static-analysis exercise. To reach the
`VERIFIED` rung, one would capture one real `passwordAuth` request (P2) and confirm
the reconstruction reproduces its `password`/`ts` byte-for-byte.

## Incidental observations

- **Local password storage.** `com/yy/hiyo/login/account/m.java` persists the
  phone record — including the *raw* password — to shared-prefs
  (`e1.y("key_last_login_password" + uid, pVar.getPassword())`, line 527) and logs
  it (`AccountModel ... password: %s`). Sensitive-data-at-rest / log-hygiene note.
- **SHA-256 without salt or KDF.** `password = SHA256(rawPassword)` is an
  unsalted fast hash; server-side storage strength is unknown from the client.
- Native libs present (`libyyruntime.so`, `libnms.so`, `libpglarmor.so`,
  `libyyshellv2.so`) are **not** on the password-login path — the whole scheme is
  pure Java/JCE.
