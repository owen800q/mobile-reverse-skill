# HA Go — Username/Password Login API (static analysis)

> **Scope & authorization.** Defensive/research documentation of how the *client*
> (the HA Go React Native app) builds its own username+password login request,
> produced with `reverse-skill` in **pure static analysis** mode (jadx + Hermes
> bytecode decompilation only — no device, no traffic capture, no live request
> against HA servers). It documents a client-side scheme so it can be understood
> and verified; it is not a tool for accessing accounts. Use only against
> apps/accounts you are authorized to test.

## Target

| | |
|-|-|
| App | **HA Go** (Hong Kong Hospital Authority patient app) |
| Package | `hk.org.ha.hago` |
| Version | 2.42.0 (versionCode 262), targetSdk 36 |
| Stack | **React Native + Hermes** (`assets/index.android.bundle` = Hermes bytecode HBC v96; `libhermesvm.so`, `libreactnative.so`) |
| Method | jadx (APK survey) + `hbc-decompiler` (hermes-dec) on `index.android.bundle` (8.4 MB). The login logic is in the JS bundle, not DEX. |
| API gateway | `https://hago-corp-cloudgw-prd.hago.ha.org.hk/hago/gw/2/` (resolved by `getAppPath()` from runtime config `https://hago-corp-resources-prd.hago.ha.org.hk/hago-app-config/config.json`) |
| Prior art | KB verdict `NONE` — original analysis |

> **Note on the earlier commit.** An earlier revision of this branch analysed
> `com.yy.hiyo` ("Hago", a YY social/gaming app) — that was a misread of "HA Go".
> The correct target is the Hospital Authority's **HA Go** (`hk.org.ha.hago`),
> analysed here; the wrong-app file has been removed.

## TL;DR

Username/password login is a **two-layer** scheme:

1. **Inner field:** the raw password is RSA-encrypted with a *static, embedded*
   2048-bit public key → sent as the JSON field `password` (a.k.a. `secured_password`).
2. **Transport envelope:** the whole JSON body is then AES-256-CBC encrypted with a
   fresh random key, and that key is RSA-wrapped with a *dynamic* public key, and
   POSTed as multipart form-data.

```
POST https://hago-corp-cloudgw-prd.hago.ha.org.hk/hago/gw/2/api/user/v2/login
Authorization: Bearer <app-level access_token>        (from api/app/token)
Content-Type: multipart/form-data

form fields:
  content = Base64( AES-256-CBC( JSON.stringify(INNER_BODY), aesKey, iv ) )   # PKCS7
  en_key  = JSEncrypt( JSON.stringify({ aesKey, iv }) )   # RSA-PKCS1v1.5, dynamic key
  lang    = <ui language>

INNER_BODY = {
  username,
  challenge,            # nonce from api/user/v2/accesschallenge (pre-login)
  password,             # = hex( RSA-PKCS1v1.5( rawPassword, STATIC embedded 2048-bit pubkey ) )
  device_info,
  request_credential,
  timestamp,            # corrected unix seconds: floor(Date.now()/1000) - timestampError
  api_version,
  is_captcha_verified   # 'Y' | 'N'
}
```

Two **different** RSA keys are involved: a **static embedded** key protects the
password; a **dynamic** key (`rsa_public_key`, fetched into local storage) wraps the
per-request AES key. Everything is standard JS crypto (jsrsasign + CryptoJS +
JSEncrypt) in the Hermes bundle — none of it is in native code.

## Call path (Hermes bytecode, decompiled)

```
LoginPage submit
  → EncryptPassword(rawPassword)                     # index_decomp.txt:262083
       KEYUTIL.getKey(<embedded PEM>); KJUR.crypto.Cipher.encrypt(pwd, key, 'RSA')
  → setSecuredPassword(cipher)                        # stored as 'secured_password'
  → login action (fun8831)                            # index_decomp.txt:315235
       body = { username, challenge, password:getSecuredPassword(), device_info,
                request_credential, timestamp, api_version, is_captcha_verified }
       url  = getAppPath() + API_NAME_LOGIN_V2        # 'api/user/v2/login'
       payload = parametersFromData(JSON.stringify(body))   # passthrough
       SubmitRequest(url, payload, 'POST', true)      # index_decomp.txt:293398
  → SubmitRequest
       aesKey = aes_generation()   # 32 random bytes -> 32-char string (crypto.getRandomValues)
       iv     = iv_generation()    # 16 random bytes -> 16-char string
       form   = parametersFromData_with_key(payload, aesKey, iv)   # {content, en_key, lang}
       fetch(url, { method:'POST', headers:{ Authorization:'Bearer '+token, ... }, body:form })
```

## Layer 1 — password field (`secured_password`)

`EncryptPassword` (verbatim, `index_decomp.txt:262083`):

```js
function EncryptPassword(pwd) {
    var key = KEYUTIL.getKey(
      '-----BEGIN PUBLIC KEY-----\n' +
      'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEApgUWNOMjbZplkH4O8j4w\n' +
      'hhjIrwaTpSGUcBv8iUj5cTh+ibiWQYA9ew2Feg7oPC5isbRqdxBcjoIuGhsno4sh\n' +
      'Fh3ZfU05ssR9zo3PN+8xHHrL9GQUkNq2VBf4uAOwLrhYTDNPhtIglbe/FFkUtWiZ\n' +
      'P1NKQGh+UNlkk52ARLCA/L6OCPmZJ7MxBzv+xfXB6i4kwmWWmQXcJa45jWjCkLc6\n' +
      'hxk0mUT2/cRyEKvd5SdAz1lFOwjvXPJ1Z77LwJRi2mKQyVZ6f9aZlXq9R0LgzAee\n' +
      'BYNprIgvYOMt/B3dEM5GBM4PxZxkOxyviCSG3GTWg7qpiy2nxPifP6xavQ2ojxsZ\n' +
      'xwIDAQAB\n-----END PUBLIC KEY-----\n');
    return KJUR.crypto.Cipher.encrypt(pwd, key, 'RSA');   // jsrsasign
}
```

- jsrsasign `KJUR.crypto.Cipher.encrypt(msg, key, 'RSA')` ⇒ **RSAES-PKCS1-v1_5**,
  **hex** output.
- Key is a **static 2048-bit RSA public key baked into the bundle** (same for every
  install/session). Modulus begins `A6 05 16 34 E3 23 6D 9A 65 90 …`.
- The cipher is stored locally as `secured_password` (also reused for biometric
  re-login via `setSecuredPassword`/`getSecuredPassword`), and placed in the inner
  body's `password` field.

## Layer 2 — transport envelope (all requests)

`aesEncrypt_with_key` (CryptoJS, `index_decomp.txt:295821`):

```js
function aesEncrypt_with_key(data, key, iv) {
  return CryptoJS.enc.Base64.stringify(
    CryptoJS.AES.encrypt(
      data,
      CryptoJS.enc.Utf8.parse(key),
      { mode: CryptoJS.mode.CBC, padding: CryptoJS.pad.Pkcs7, iv: CryptoJS.enc.Utf8.parse(iv) }
    ).ciphertext);
}
```

`RSAJSEncrypt_with_key` (JSEncrypt, `index_decomp.txt:295904`):

```js
function RSAJSEncrypt_with_key(aesKey, iv) {
  var pub = localStorage.getItem('rsa_public_key');   // DYNAMIC key (from server config/handshake)
  var e = new JSEncrypt(); e.setPublicKey(pub);
  return e.encrypt(JSON.stringify({ aesKey: aesKey, iv: iv }));   // RSA-PKCS1v1.5, base64
}
```

`parametersFromData_with_key` (`index_decomp.txt:296100`) assembles the wire form:

```js
form = new FormData();
form.append('content', aesEncrypt_with_key(body, key, iv));   // AES-256-CBC/PKCS7 -> Base64
form.append('en_key',  RSAJSEncrypt_with_key(key, iv));       // RSA(JSON{aesKey,iv}) -> base64
form.append('lang',    info.lang);
```

- `aes_generation()` / `iv_generation()` build the key/iv from
  `crypto.getRandomValues` over a 32-byte / 16-byte `Uint8Array`, mapped char-by-char
  into a fixed alphabet ⇒ a **32-char AES-256 key** and **16-char (128-bit) IV**,
  both used as their **UTF-8 bytes**.
- `SubmitRequest` adds `Authorization: Bearer <app access_token>` (the app-level
  token from `api/app/token` / `api/app/refreshtoken`).

## Related endpoints (from the API-name registry, `index_decomp.txt:719xxx`)

| Constant | Path |
|-|-|
| `API_NAME_LOGIN_V2` | `api/user/v2/login` |
| `API_NAME_ACCESS_CHALLENGE_V2` | `api/user/v2/accesschallenge` (pre-login nonce → `challenge`) |
| `API_NAME_RELOGIN_V2` | `api/user/v2/relogin` (biometric re-login) |
| `API_NAME_PASSWORD_CHANGE_V2` | `api/user/v2/password/change` |
| `API_NAME_FORGOT_PASSWORD_RESET_V2` | `api/user/v2/password/forgot/reset` |
| `API_NAME_EHEALTH_LOGIN_V2` | `api/user/ehrss/v2/login` (醫健通 eHealth SSO) |
| `API_NAME_IAMSMART_LOGIN_V2` | `api/user/iamsmart/v2/login` (智方便 / iAM Smart) |
| biometric login | `api/user/biometric/login` |
| app token | `api/app/token`, `api/app/refreshtoken`, `api/app/getCurrentTimestamp` |

The 醫健通 eHealth and 智方便 buttons on the login screen route to the
`ehrss`/`iamsmart` endpoints (OAuth-style external identity), not to
`api/user/v2/login`; only the username+password form uses `api/user/v2/login`.

## Reference reconstruction (documentation only — not executed against any server)

```python
import json, time, base64, hashlib
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5, AES
from Crypto.Util.Padding import pad
from Crypto.Random import get_random_bytes

STATIC_PUB = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEApgUWNOMjbZplkH4O8j4w
hhjIrwaTpSGUcBv8iUj5cTh+ibiWQYA9ew2Feg7oPC5isbRqdxBcjoIuGhsno4sh
Fh3ZfU05ssR9zo3PN+8xHHrL9GQUkNq2VBf4uAOwLrhYTDNPhtIglbe/FFkUtWiZ
P1NKQGh+UNlkk52ARLCA/L6OCPmZJ7MxBzv+xfXB6i4kwmWWmQXcJa45jWjCkLc6
hxk0mUT2/cRyEKvd5SdAz1lFOwjvXPJ1Z77LwJRi2mKQyVZ6f9aZlXq9R0LgzAee
BYNprIgvYOMt/B3dEM5GBM4PxZxkOxyviCSG3GTWg7qpiy2nxPifP6xavQ2ojxsZ
xwIDAQAB
-----END PUBLIC KEY-----"""

_ALPHABET = "...app charset from slot21 (recover exactly if byte-accuracy needed)..."

def secure_password(raw_pwd: str) -> str:                      # EncryptPassword
    c = PKCS1_v1_5.new(RSA.import_key(STATIC_PUB))
    return c.encrypt(raw_pwd.encode()).hex()                   # jsrsasign returns hex

def inner_body(username, challenge, raw_pwd, device_info, request_credential,
               api_version, captcha=False, ts_error=0):
    return {
        "username": username,
        "challenge": challenge,                                 # from accesschallenge
        "password": secure_password(raw_pwd),
        "device_info": device_info,
        "request_credential": request_credential,
        "timestamp": int(time.time()) - ts_error,
        "api_version": api_version,
        "is_captcha_verified": "Y" if captcha else "N",
    }

def envelope(body_json: str, dynamic_pub_pem: str):            # SubmitRequest
    key = get_random_bytes(32); iv = get_random_bytes(16)      # (app maps to 32/16-char strings)
    ae = AES.new(key, AES.MODE_CBC, iv)
    content = base64.b64encode(ae.encrypt(pad(body_json.encode(), 16))).decode()
    rc = PKCS1_v1_5.new(RSA.import_key(dynamic_pub_pem))
    en_key = base64.b64encode(rc.encrypt(json.dumps({"aesKey": key.decode('latin1'),
                                                     "iv": iv.decode('latin1')}).encode())).decode()
    return {"content": content, "en_key": en_key, "lang": "en"}   # multipart form fields
# POST multipart to <appPath>/api/user/v2/login with Authorization: Bearer <app token>
```

*(The app derives its 32/16-char key/iv from a fixed alphabet rather than raw
bytes; recover `slot21`'s alphabet from the bundle for byte-exact reproduction.)*

## Verification status

Pure static analysis. Every claim is traced to a verbatim decompiled line (ledger
rung **REACHABLE**); the three crypto primitives are **high**-confidence, each
resting on an unambiguous literal library call (`KJUR.crypto.Cipher.encrypt(...,'RSA')`,
`CryptoJS.AES.encrypt(...,{mode:CBC,padding:Pkcs7})`, `JSEncrypt().encrypt(...)`).
The scheme was **not** replayed against HA servers — that would exercise a real
account and is out of scope. Reaching `VERIFIED` would require capturing one real
`api/user/v2/login` request and confirming the reconstruction reproduces `content`
and `en_key` (the outer envelope is per-request-random, so verify by decrypting the
capture with the recovered scheme rather than by byte-matching).

## Security observations (defensive)

- **Static embedded RSA key for the password.** The password-protecting key is the
  same for every install and never rotates; anyone with the app can encrypt a
  password to it. It provides confidentiality against passive on-wire capture (on
  top of TLS) but is not a per-session secret.
- **Encrypted password persisted for biometric re-login.** `secured_password` (the
  RSA ciphertext) is stored in native storage and replayed by `api/user/v2/relogin`
  — i.e. a reusable password-equivalent lives on the device; its protection reduces
  to the OS keystore / biometric gate.
- **Layered app-level crypto is defense-in-depth over TLS**, not a replacement:
  `challenge` (nonce) + `timestamp` give anti-replay on the login call.
```
