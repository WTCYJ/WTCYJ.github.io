---
layout: post
title: "Allsafe iOS - 맥 없이, 배포 IPA와 소스로 뜯어본 취약한 iOS 앱"
date: 2026-08-31 21:00:00 +0900
category: iOS
author: SeiKa
tags: [iOS, iOSSecurity, 모바일보안, Allsafe, Frida, objection, 정적분석, IPA, Mach-O, 리버싱, 취약점분석, 학습기록]
excerpt: "안드로이드 Allsafe를 풀고 나서 같은 저자의 iOS판이 있는 걸 보고 흥미가 생겨 시작했습니다. 그런데 제 PC는 Windows라 iOS를 아예 못 돌립니다. 그래서 이번엔 기기에 올려 Frida로 찌르는 대신, 배포된 IPA 바이너리와 소스를 Windows에서 정적으로 뜯었습니다. plist 하나에서 관리자 비밀번호와 Stripe 라이브 키가 평문으로 쏟아지고, 컴파일된 바이너리에서 열세 개 챌린지의 플래그가 그대로 strings로 나오는 걸 하나씩 확인한 기록입니다. 되는 것과, 기기가 없어 못 한 것, 그리고 배포본이 소스보다 오래돼 아예 존재하지 않던 취약점까지 그대로 적었습니다."
---

> 대상: [t0thkr1s/allsafe-ios](https://github.com/t0thkr1s/allsafe-ios) — 교육용으로 만들어진 의도적 취약 iOS 앱 (release v1.0)
> 환경: Windows 11. iOS 기기·시뮬레이터 없음. 배포 IPA 정적 분석(unzip / plistlib / strings / IDA) + 소스 리뷰

안드로이드 Allsafe를 끝까지 풀고 나서, 같은 저자 t0thkr1s의 깃허브를 구경하다가 iOS판이
따로 있는 걸 봤습니다. 안드로이드판이 워낙 재밌었어서 iOS는 어떻게 문제를 냈을까 궁금해서
바로 받아봤습니다.

그런데 시작하자마자 벽에 부딪혔습니다. 제 작업 PC는 Windows인데, iOS 앱은 Windows에서
아예 못 돌립니다. 안드로이드 때처럼 에뮬레이터에 올려서 Frida로 찌르고 화면을 캡처하는
흐름이 iOS에선 성립하지 않습니다. 빌드하려면 Xcode(맥)가 필요하고, 시뮬레이터도 맥 위에서
돌고, Frida 동적 분석은 탈옥한 실기기가 있어야 합니다. 저는 맥도 아이폰도 없습니다. 찾아보다
".NET MAUI용 Windows 원격 iOS 시뮬레이터" 같은 것도 결국 네트워크에 맥이 한 대 있어야
그 화면을 원격으로 띄워주는 뷰어라, 맥 없이 되는 우회로는 아니었습니다.

그래서 이번 글은 성격이 다릅니다. "기기에 올려서 실제로 터뜨렸다"가 아니라, 앱을 실행하지
않고 **배포된 IPA 바이너리와 소스만으로 어디까지 드러나는가**를 본 정적 분석 기록입니다.
결론부터 말하면 생각보다 훨씬 많이 드러납니다. 열네 개 챌린지 중 상당수는 앱을 한 번도
실행하지 않고 파일과 문자열만으로 정답(플래그)과 시크릿이 그대로 나왔습니다. 반대로,
생체 인증 우회나 탈옥 탐지 우회처럼 "실제로 Frida를 걸어 판정을 뒤집는" 부분은 기기가
없으면 시연이 안 되니, 그건 방법만 정확히 적고 실행은 못 했다고 그대로 남겼습니다.

정리는 안드로이드 때처럼 성격별로 묶었습니다.

---

## 0. 먼저 정한 것 — 무엇을 "실측"이라 부를지

정적 분석이라고 하면 자칫 "소스 읽고 추측했다"로 흐르기 쉬워서, 시작 전에 선을 하나 그었습니다.
이 글에서 실측이라고 부르는 것은 **실제로 배포되는 IPA 바이너리에서 확인된 것**입니다.
소스는 저자가 올린 오픈소스지만, 소스에 있다고 실제 배포물에 그대로 있으리란 법은 없습니다
(이건 뒤에서 실제로 어긋나는 챌린지가 하나 나옵니다). 그래서 소스로 취약 지점을 짚되,
가능한 건 전부 컴파일된 바이너리에서 다시 확인했습니다.

준비물부터 실제로 만들었습니다. 릴리스에 올라온 IPA를 받아 풀면 이렇게 생겼습니다.

```console
$ curl -sL -o allsafe-ios.ipa https://github.com/t0thkr1s/allsafe-ios/releases/download/v1.0/allsafe-ios.ipa
$ unzip -q allsafe-ios.ipa && find Payload/Allsafe.app -maxdepth 1 -type f
Payload/Allsafe.app/Allsafe              # 메인 실행파일 (Mach-O)
Payload/Allsafe.app/APIConfig.plist      # ← 이게 첫 번째 챌린지다
Payload/Allsafe.app/Info.plist
Payload/Allsafe.app/embedded.mobileprovision
Payload/Allsafe.app/_CodeSignature/
```

메인 실행파일이 어떤 물건인지부터 봤습니다.

```console
$ file Payload/Allsafe.app/Allsafe
Allsafe: Mach-O 64-bit arm64 executable, flags:<NOUNDEFS|DYLDLINK|TWOLEVEL|PIE>
```

arm64 기기 빌드입니다. 이 점이 뒤에서 계속 발목을 잡습니다 — 시뮬레이터는 x86_64/arm64
시뮬레이터 슬라이스를 요구하는데 이건 순수 기기 빌드라, 설령 맥이 있어도 이 IPA를
시뮬레이터에 그냥 올릴 순 없습니다. 그래서 "실행"은 처음부터 선택지가 아니었고, 대신
바이너리 안을 들여다보는 쪽으로 갔습니다.

Windows엔 `strings`가 기본으로 없어서, 파이썬으로 인쇄 가능한 바이트열만 뽑는 간단한
추출기를 썼습니다. 이 덤프가 이 글 전체의 근거가 됩니다.

```console
$ python -c "import re,sys; d=open('Payload/Allsafe.app/Allsafe','rb').read(); \
             print('\n'.join(m.decode() for m in re.findall(rb'[\x20-\x7e]{5,}', d)))" > strings.txt
$ grep -oE 'FLAG\{[^}]*\}' strings.txt | sort -u | wc -l
12
```

앱을 켜지도 않았는데 컴파일된 바이너리에서 플래그가 열두 개 나옵니다(하나는 plist에 따로
들어 있어서 실제로는 열세 개). 이게 이 앱의 성격을 그대로 보여줍니다 — 비밀이 전부
클라이언트 안에 있습니다.

---

## 1. 저장소 — 기기 안은 비밀이 아니다

가장 큰 덩어리입니다. iOS 앱은 값을 어디에 두든(plist, UserDefaults, Keychain, SQLite, 캐시)
결국 기기 파일시스템에 남고, 그 파일시스템은 앱 프로세스 밖에서 읽힙니다. 저장 위치를 잘못
고르면 암호화 없이 그대로 노출됩니다.

### 1-1. Plist에 쏟아진 시크릿 (property_lists)

첫 챌린지는 힌트가 아예 대놓고 `APIConfig.plist`를 가리킵니다. 이건 앱 번들에 딸려 오는
설정 파일인데, 번들 리소스는 코드 서명으로 무결성만 보장될 뿐 암호화가 아닙니다. IPA는
그냥 zip이라 풀기만 하면 됩니다. 바이너리 plist라 파이썬 `plistlib`으로 디코드했습니다.

```console
$ python -c "import plistlib; d=plistlib.load(open('Payload/Allsafe.app/APIConfig.plist','rb')); \
             import json; print(json.dumps(d, indent=1, ensure_ascii=False))"
{
 "AdminCredentials":   { "Username": "root_admin", "Password": "AllSafe2024!Admin", "AccessLevel": "SuperUser" },
 "DatabaseCredentials":{ "DBHost": "db.allsafe-internal.com", "DBPassword": "P@ssw0rd123_DB", "DBUser": "admin_service" },
 "APIKeys":            { "ProductionKey": "ak_prod_4f8b2c1e9d3a5b7f8e9c2d1a4b6e8f3c", ... },
 "EncryptionKeys":     { "AESKey": "2b7e151628aed2a6abf7158809cf4f3c", "RSAPrivateKey": "-----BEGIN RSA PRIVATE KEY-----\n..." },
 "ThirdPartyServices": { "AWSSecretKey": "wJalrXUtnFEMI/...", "StripeAPIKey": "sk_live_51H8..." },
 "SecretFlag":         "FLAG{property_lists_expose_secrets_p4432}"
}
```

플래그 하나 찾는 문제인 줄 알았는데, 같은 파일에 관리자 비밀번호, DB 자격증명, 프로덕션
API 키, AES 키, RSA 개인키, 그리고 Stripe 라이브 시크릿 키(`sk_live_...`)까지 전부 평문으로
들어 있습니다. 실제 앱이었다면 이 파일 하나 유출이 백엔드 전체 장악으로 이어집니다.
플래그는 `FLAG{property_lists_expose_secrets_p4432}`. 앱을 실행하지도, 기기에 올리지도
않았습니다 — IPA를 푼 게 전부입니다.

### 1-2. UserDefaults (userdefaults_are_not_secure)

UserDefaults는 편의용 설정 저장소인데, 값을 앱 샌드박스 안의 평문 plist
(`Library/Preferences/infosecadventures.allsafe.plist`)로 직렬화합니다. 암호화가 없습니다.
소스를 보면 화면을 열기만 해도(onAppear) 플래그가 심어집니다.

```swift
// UserDefaultsVulnerabilityView.swift
private func setupVulnerabilityData() {
    UserDefaults.standard.set("FLAG{userdefaults_are_not_secure_m8934}", forKey: "hidden_flag")
    UserDefaults.standard.set("admin_backup_key_2024", forKey: "api_secret")
}
// 사용자가 [STORE CREDENTIALS]로 저장하면 이것도 평문:
UserDefaults.standard.set(username, forKey: "stored_username")
UserDefaults.standard.set(password, forKey: "stored_password")
```

플래그와 키 문자열은 컴파일된 바이너리에도 그대로 있습니다.

```console
$ grep -E 'hidden_flag|userdefaults_are_not_secure|admin_backup_key' strings.txt
hidden_flag
FLAG{userdefaults_are_not_secure_m8934}
admin_backup_key_2024
```

기기가 있었다면 `objection -g infosecadventures.allsafe explore` 후
`ios plist cat Library/Preferences/infosecadventures.allsafe.plist` 한 줄로 뽑는 값입니다.
그 objection 명령 자체는 실기기가 필요해 돌려보지 못했지만, 값은 바이너리에서 이미 확정됩니다.

### 1-3. Keychain 접근성 (keychain_accessibility)

Keychain은 iOS에서 그나마 제대로 된 비밀 저장소인데, `kSecAttrAccessible` 접근성 클래스를
어떻게 고르느냐가 핵심입니다. 이 챌린지는 가장 관대한 축을 골랐습니다.

```swift
// KeychainVulnerabilityView.swift  (.onAppear 에서 저장)
let query: [String: Any] = [
    kSecClass as String:        kSecClassGenericPassword,
    kSecAttrAccount as String:  "ctf_flag",
    kSecValueData as String:    "FLAG{keychain_accessibility_matters_k7821}".data(using: .utf8)!,
    kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock   // ← 약한 접근성
]
SecItemAdd(query as CFDictionary, nil)
```

`AfterFirstUnlock`은 부팅 후 한 번만 잠금해제하면 그 뒤로는 기기가 다시 잠겨도 항목이
읽힙니다. `ThisDeviceOnly` 변형이 아니라 암호화 백업에도 딸려 나가고, 생체/패스코드 접근
게이트(`SecAccessControl`)도 없습니다. 고가치 비밀이라면
`kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly` + 생체 ACL이 맞습니다. 소스 전체에서
`ThisDeviceOnly`, `SecAccessControl`, `biometry` 를 grep해도 0건입니다.

그런데 이 플래그도 굳이 Keychain을 열 필요가 없습니다. 바이너리 문자열에 그대로 있습니다.

```console
$ grep -E 'keychain_accessibility|_kSecAttrAccessibleAfterFirstUnlock' strings.txt
FLAG{keychain_accessibility_matters_k7821}
_kSecAttrAccessibleAfterFirstUnlock
```

### 1-4. 암호화 없는 SQLite (sqlite_without_encryption)

이 챌린지는 `import SQLite3`로 플랫폼 libsqlite3을 그대로 쓰고, `sqlite3_open()`으로 평문 DB를
만듭니다. SQLCipher도, `PRAGMA key`도, Keychain 파생 키도 없습니다. 그리고 그 DB에 온갖 걸
시드합니다.

```console
$ grep -E 'allsafe_secrets|CREATE TABLE|master_key|jwt_signing|ctf_flag|AKIA' strings.txt
allsafe_secrets.db
CREATE TABLE IF NOT EXISTS users ...
CREATE TABLE IF NOT EXISTS secrets ...
CREATE TABLE IF NOT EXISTS sessions ...
mk_4f8b2c1e9d3a5b7f8e9c2d1a4b6e8f3c            # database_master_key
HS256_super_secret_key_do_not_share            # jwt_signing_key
FLAG{sqlite_without_encryption_s9876}          # secrets 테이블 id=4, secret_key='ctf_flag'
AKIA4SQLITEEXAMPLE123                           # aws_access_key
```

암호화 API가 정말 없는지도 역으로 확인했습니다.

```console
$ grep -Ei 'sqlcipher|PRAGMA key|sqlite3_key|sqlite3_rekey' strings.txt
(없음)
```

DB 파일은 `.../Documents/allsafe_secrets.db`에 그대로 남으니, 기기에서라면
`objection`의 `sqlite connect`나 `file download` 후
`SELECT secret_value FROM secrets WHERE secret_key='ctf_flag';` 로 끝납니다. 미암호화라
복호 키도 필요 없습니다.

### 1-5. URLSession 디스크 캐시 (nsurlsession_cache)

이건 조금 더 미묘합니다. 인증 응답을 디스크 캐시에 강제로 남기고, 심지어 플래그를 요청
URL의 쿼리스트링에 실었습니다.

```swift
// NSURLSessionCacheVulnerabilityView.swift
config.requestCachePolicy = .returnCacheDataElseLoad
let urlString = "https://api.allsafe-corp.com/login?flag=FLAG{nsurlsession_cache_exposes_secrets_c4ch3}"
...
let cachedResponse = CachedURLResponse(response: httpResponse, data: responseData, storagePolicy: .allowed)
URLCache.shared.storeCachedResponse(cachedResponse, for: request)   // 디스크로
```

캐시된 응답 본문에는 관리자 계정까지 들어 있습니다. 전부 바이너리에 평문으로 컴파일돼
있었습니다.

```console
$ grep -E 'nsurlsession_cache|AllSafe2024!Admin|ak_live_|storeCachedResponse' strings.txt
https://api.allsafe-corp.com/login?flag=FLAG{nsurlsession_cache_exposes_secrets_c4ch3}
FLAG{nsurlsession_cache_exposes_secrets_c4ch3}
"password": "AllSafe2024!Admin"
"api_key": "ak_live_4f8b2c1e9d3a5b7f8e9c2d1a4b6e8f3c"
storeCachedResponse:forRequest:
```

민감 응답은 애초에 `.notAllowed`나 `URLSessionConfiguration.ephemeral`로 디스크에 안 남겨야
하고, 비밀을 URL 파라미터에 싣는 것도 캐시 키(`request_key`)에 그대로 박히니 이중으로
나쁩니다. 기기에서라면 `Library/Caches/.../Cache.db`를 뽑아
`SELECT request_key FROM cfurl_cache_response;` 하면 URL의 플래그가 그대로 나옵니다.

### 1-6. 파일 공유 — 그리고 소스에 있다고 배포본에 있는 건 아니다

여기서 이 글에서 개인적으로 제일 재밌었던 순간이 나옵니다. 이 챌린지는 `Info.plist`에
`UIFileSharingEnabled`와 `LSSupportsOpeningDocumentsInPlace`를 켜서 앱 Documents를
Finder/파일 앱에 노출하고, 거기에 플래그 CSV를 떨구는 구성 취약입니다. 소스에는 분명히
있습니다.

```swift
// InsecureFileSharing.swift  (.onAppear)
let flagContent = "FLAG{itunes_file_sharing_exposed}"
try flagContent.data(using: .utf8)?.write(to: documentsDirectory
        .appendingPathComponent("itunes_export_share_flag.csv"), options: .atomic)
```

```xml
<!-- Info.plist (소스) -->
<key>UIFileSharingEnabled</key><true/>
```

그런데 제가 받은 배포 IPA의 실제 `Info.plist`를 디코드해 보니, 이 두 키가 아예 없었습니다.

```console
$ python -c "import plistlib; d=plistlib.load(open('Payload/Allsafe.app/Info.plist','rb')); \
             print('UIFileSharingEnabled' in d, 'LSSupportsOpeningDocumentsInPlace' in d)"
False False
$ grep -Ei 'itunes_file_sharing|itunes_export_share|file_sharing' strings.txt
(없음)
```

바이너리에도 이 챌린지의 플래그가 없습니다. 즉 제가 가진 릴리스 v1.0 IPA는 이 챌린지가
소스에 추가되기 전에 빌드된 물건입니다. 취약점은 소스에 있지만 이 배포본에는 존재하지
않습니다. 안드로이드판을 풀 때도 계속 마주쳤던 교훈이 여기서도 그대로 나왔습니다 —
코드에 있다는 것과 지금 이 배포물에서 진짜 터진다는 것은 다릅니다. 그래서 이 챌린지는
"소스 기준으로는 이렇게 노출되고, 방법은 house_arrest AFC(`pymobiledevice3 apps afc ...`)나
Finder 파일 탭이지만, 내 손의 IPA로는 재현되지 않는다"까지만 정직하게 적어 둡니다.

---

## 2. 암호화 — 열쇠를 자물쇠 옆에 두면

### 2-1. 하드코딩된 AES 키 (hardcoded_keys)

암호화를 하긴 하는데, 키와 IV를 소스에 그대로 박아 뒀습니다.

```swift
// HardcodedSecrets.swift
let key = "MyS3cr3tK3y2024!"     // 16 bytes -> AES-128
let iv  = "InitVector123456"
...
CCCrypt(CCOperation(kCCEncrypt), CCAlgorithm(kCCAlgorithmAES),
        CCOptions(kCCOptionPKCS7Padding),
        keyBytes.baseAddress, kCCKeySizeAES128, ivBytes.baseAddress, ...)
```

배포 바이너리는 공격자 소유 기기에서 완전히 읽히니, 소스/바이너리에 박힌 키는 전부 노출
자산입니다. 키(`MyS3cr3tK3y2024!`)와 IV를 회수하면 이 앱이 만든 산출물
(`Documents/encrypted_secrets_*.dat`)을 오프라인에서 복호할 수 있습니다.

```console
# 파일을 뽑았다면 (AES-128-CBC/PKCS7):
$ openssl enc -d -aes-128-cbc \
    -K 4d795333637233744b33793230323421 \   # utf8("MyS3cr3tK3y2024!")
    -iv 496e6974566563746f72313233343536 \   # utf8("InitVector123456")
    -in ciphertext.bin
```

여기서 이 앱이 파 놓은 함정을 하나 발견했습니다. 플래그가 다른 챌린지들과 달리 바이너리에
평문으로 안 나옵니다.

```console
$ grep -E 'hardcoded_keys_extracted|hardcoded' strings.txt
(없음)
```

소스를 보면 이유가 있습니다. 플래그 접미사를 런타임에 해시로 만듭니다.

```swift
private func generateFlagFromSecrets() -> String {
    let combined = key + iv
    let hash = abs(combined.hashValue)
    let flagSuffix = String(hash).suffix(4)
    return "FLAG{hardcoded_keys_extracted_\(flagSuffix)}"
}
```

`String.hashValue`는 Swift 4.2(SE-0206)부터 **프로세스마다 무작위 SipHash 시드로 시딩**됩니다.
즉 이 4자리 접미사는 앱을 켤 때마다 달라집니다. 그러니 프리픽스
`FLAG{hardcoded_keys_extracted_XXXX}`까지는 정적으로 확정되지만, XXXX는 정적으로 확정이
불가능합니다 — 이건 제가 기기가 없어서 못 한 게 아니라, 애초에 런타임 값이라 지어낼 수
없는 부분입니다. 실제 값을 얻으려면 기기에서 CCCrypt를 후킹해 암호화 직전 평문을 덤프하는
게 정석입니다.

```javascript
// 기기에서 실행할 후킹 (여기선 미실행 — 방법만)
Interceptor.attach(Module.findExportByName(null, 'CCCrypt'), {
  onEnter(a) {
    if (a[0].toInt32() === 0) {           // kCCEncrypt
      console.log('PT', Memory.readUtf8String(a[6], a[7].toInt32()));  // 완성된 flag
    }
  }
});
```

---

## 3. 클라이언트 측 판정 — 단말이 심판이면

여기서부터는 "비밀이 새는" 문제가 아니라 "판정을 클라이언트가 한다"는 문제입니다. 정답도,
검증 로직도 전부 공격자가 통제하는 단말 안에 있으니 경계 자체가 성립하지 않습니다.

### 3-1. 라이선스 키 (license_key_bypass)

서버 왕복도 서명도 없이, 하드코딩된 두 문자열과 단순 비교합니다.

```swift
// LicenseKeyVulnerabilityView.swift
private func validateLicense() -> Bool {
    let validKeys = ["VALID-ALLSAFE-LICENSE-2024", "DEMO-KEY-12345"]
    return validKeys.contains(licenseKey)
}
// 성공 시 뜨는 alert 본문에 플래그가 그대로:
Text("FLAG{license_key_bypass_success_f1ag}")
```

정답 키도, 플래그도 전부 바이너리에 있습니다. "우회"라고 부르기도 민망하게, 정답 키를 읽어
그대로 입력하면 됩니다.

```console
$ grep -E 'VALID-ALLSAFE-LICENSE|DEMO-KEY-12345|license_key_bypass' strings.txt
VALID-ALLSAFE-LICENSE-2024
DEMO-KEY-12345
FLAG{license_key_bypass_success_f1ag}
```

기기에서 굳이 후킹한다면 `validateLicense()`의 Bool 반환을 true로 뒤집는 건데, private
Swift 메서드라 심볼이 export되지 않아 모듈 베이스+오프셋으로 잡아야 합니다. 그 오프셋은
정적 덤프만으론 확정이 안 돼서, 이 경로는 방법까지만 적어 둡니다. 어차피 정답 키가 그냥
보이니 실전에선 그게 제일 빠릅니다.

### 3-2. PIN 브루트포스 (pin_brute_force)

"6자리 PIN 볼트"인데, 정답이 소스에 상수로 박혀 있고 평문 `==` 비교입니다.

```swift
// PinBruteforceVulnerabilityView.swift
let pin = "029728"                       // Keychain(secure_vault/vault_pin)에 저장도 함
...
let storedPin = "029728"
if enteredPin == storedPin { showFlagPopup = true }
```

게다가 시도 횟수 제한이 없습니다. `attempts += 1`로 세기만 하고, 10회를 넘겨도 화면 숫자가
빨개질 뿐 차단하지 않습니다. 그러니 10^6 완전탐색이 지연 없이 가능하고 — 사실 그럴 필요도
없이 PIN과 플래그가 둘 다 바이너리에 있습니다.

```console
$ grep -E '029728|secure_vault|vault_pin|pin_brute_force' strings.txt
029728
secure_vault
vault_pin
FLAG{pin_brute_force_keychain_bypass_m8934}
```

### 3-3. 생체 인증 우회 (biometric) — 시저 암호에 걸린 함정

이 챌린지가 정적 분석으로 제일 풀 맛이 났습니다. 인증 판정은 `LAContext.evaluatePolicy`의
성공 콜백(불리언) 하나에만 의존합니다. 이 콜백은 앱과 같은 주소공간에서 돌기 때문에,
기기에서라면 `objection`의 `ios ui biometrics_bypass` 한 줄이나 Frida로 콜백을 위조하면
뚫립니다(이건 기기가 필요해 미실행).

```swift
// BiometricBypass.swift
context.evaluatePolicy(policy, localizedReason: "...") { success, error in
    if success { self.handleSuccessfulAuthentication() }   // → decryptFlag()
}
```

그런데 정작 플래그는 인증과 무관하게, 소스에 난독화된 리터럴로 박혀 있습니다. 복호 함수가
그냥 각 문자 ASCII -1(시저)입니다.

```swift
private let obfuscatedFlag = "GMBH|c21n4us2d_5bvui_czq5tt4e_x2ui_gs2e5~"
private func decryptFlag() -> String {
    return String(obfuscatedFlag.compactMap {
        Character(UnicodeScalar($0.asciiValue! - 1))   // -1 Caesar
    })
}
```

인증을 한 번도 통과하지 않고 오프라인에서 그대로 디코드했습니다.

```console
$ python -c "print(''.join(chr(ord(c)-1) for c in 'GMBH|c21n4us2d_5bvui_czq5tt4e_x2ui_gs2e5~'))"
FLAG{b10m3tr1c^4auth^byp4ss3d^w1th^fr1d4}
```

여기서 재밌는 함정이 하나 있습니다. 구분자가 `_`가 아니라 `^`로 나옵니다. 개발자가 난독화
리터럴에 문자 그대로 `_`(0x5F)를 넣었는데, -1을 하면 `^`(0x5E)가 되기 때문입니다. 원래
`_`를 얻으려면 리터럴에 backtick(0x60)이 들어갔어야 합니다. 그러니 앱이 실제로 복사해 주는
값은 `^` 버전이 맞고(채점은 런타임 값 기준일 테니), 개발자 의도값은
`FLAG{b10m3tr1c_4auth_byp4ss3d_w1th_fr1d4}`로 보입니다. 둘 다 적어 둡니다. 참고로 미션
설명엔 "anti-debugging, encrypted flag storage"라고 써 있지만 소스엔 디버거 탐지도, 진짜
암호화도 없었습니다 — 시저 난독화가 전부입니다.

### 3-4. 탈옥 탐지 우회 (jailbreak_detection)

탈옥 탐지를 클라이언트가 로컬 신호(설치 앱 URL 스킴, 파일 존재, 루트 쓰기 시도)만으로
합니다. 검사 대상 경로가 전부 바이너리에 문자열로 박혀 있어서, 무엇을 검사하는지가 그대로
드러납니다.

```console
$ grep -E 'cydia://|Cydia.app|/bin/bash|/etc/apt|/usr/sbin/sshd|jailbreak_detection' strings.txt
cydia://
/Applications/Cydia.app
/bin/bash
/etc/apt
/usr/sbin/sshd
FLAG{jailbreak_detection_bypassed_j4il}
```

```swift
// JailbreakDetectionView.swift
private func isJailbroken() -> Bool {
    return checkSuspiciousApps() || checkSuspiciousPaths()
        || checkSuspiciousSchemes() || checkWriteAccess()
}
// isJailbroken() == false 일 때만 성공 다이얼로그 → 플래그
```

기기에서라면 `objection`의 `ios jailbreak disable`이 `-[NSFileManager fileExistsAtPath:]`,
`-[UIApplication canOpenURL:]` 등을 일괄 후킹해 네 검사를 무력화하고, 파일 쓰기까지 확실히
죽이려면 판정 함수나 그 ObjC 브리지를 직접 후킹합니다(미실행, 방법만). 다만 플래그 값 자체는
바이너리에 평문이라, "값을 아는 것"과 "앱에서 성공 다이얼로그를 띄우는 것"은 별개입니다 —
후자만 기기가 필요합니다.

---

## 4. 안티탬퍼링이 사실은 없던 것 (ssl_pinning)

SSL 피닝 챌린지는 이름과 달리, 실제 TLS 검증이 아니라 하드코딩된 불리언 게이트였습니다.
소스를 보면 진짜 인증서를 비교하는 게 아니라 가짜 핀 해시를 흉내만 내고 무조건 false를
반환합니다.

```swift
// SSLPinningBypassView.swift
let pinnedCertificateHashes = [
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",   // Fake pinned cert hash
    "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB="
]
return false                                          // 항상 false
```

그리고 성공 분기의 플래그는 응답 JSON 문자열에 통째로 박혀 있습니다.

```console
$ grep -E 'ssl_pinning_bypass|AAAAAAAA.*=|SSL Pinning Bypassed' strings.txt
FLAG{ssl_pinning_bypass_success_h4ck}
{'flag':'FLAG{ssl_pinning_bypass_success_h4ck}','user':'admin','token':'abc123'}
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
SSL Pinning Bypassed!
```

즉 이 화면은 실제 HTTPS 요청을 보내지 않습니다. 그래서 Burp/mitmproxy로 트래픽을 가로채는
전형적 피닝 우회를 걸어도 관측할 트래픽이 없습니다. 기기에서 성공 UI를 띄우려면
`isSSLPinningBypassed()`/`validateCertificatePinning()`의 Bool 반환을 Frida로 뒤집어야
하는데(미실행), 플래그 값은 이미 바이너리에서 나옵니다. 한 가지 정정: 힌트에 나오는
`https://api.allsafe-corp.com/login`은 사실 이 화면이 아니라 앞의 URLSession 캐시 챌린지의
문자열입니다 — 이 SSL 화면은 네트워크를 아예 안 탑니다.

---

## 5. 주입 — WebView XSS (webview_xss)

`WKWebView`에 사용자 입력을 이스케이프 없이 HTML로 붙이고 JS를 켜 둔, 교과서적 XSS입니다.

```swift
// WebViewXSSView.swift  (generateMinimalHTML)
"</script>" + input + "</body></html>"          // ← 문자열 연결, 이스케이프 없음
...
preferences.allowsContentJavaScript = true
webView.loadHTMLString(minimalHTML, baseURL: nil)
```

입력이 데이터가 아니라 마크업으로 해석되니 `<img src=x onerror=alert(1)>` 같은 페이로드가
그대로 실행됩니다. 심지어 성공 판정 로직 자체도 허술해서, 탐지가
`document.getElementsByTagName('script').length > 1`인데 템플릿에 이미 `<script>`가 하나
있어 `<script>1</script>`만 넣어도 성립합니다. 이 HTML 템플릿과 탐지 로직, 플래그가 전부
바이너리에 그대로 있었습니다.

```console
$ grep -E 'webview_xss|XSSDetector|getElementsByTagName' strings.txt
FLAG{webview_xss_injection_successful_w3b}
XSSDetector
document.getElementsByTagName('script').length > 1
```

실제로 페이로드를 넣어 성공 다이얼로그를 띄우는 건 기기(또는 최소한 앱 실행)가 필요해서
못 했지만, 취약 경로와 플래그는 정적으로 전부 확인됩니다.

---

## 6. 로깅 — 디버그 흔적이 비밀을 흘린다 (insecure_logging)

마지막은 로깅입니다. 민감값을 네 가지 로그 싱크에 그대로 흘립니다.

```swift
// LoggingVulnerabilityView.swift
let logger = Logger(subsystem: "com.allsafe.ios", category: "data")
logger.info("Processing sensitive data with flag: FLAG{insecure_logging_exposes_secrets_l0g5}")
print("DEBUG: Flag verification - FLAG{insecure_logging_exposes_secrets_l0g5}")
NSLog("ALLSAFE: Data processing complete - FLAG{insecure_logging_exposes_secrets_l0g5}")
os_log("Sensitive operation completed: FLAG{insecure_logging_exposes_secrets_l0g5}", type: .info)
```

포맷 문자열이 그대로라 `os_log`/`Logger`의 `%{private}` 리댁션도 안 걸립니다(리댁션은 보간
인자에만 걸리는데 여기선 플래그가 상수 문자열의 일부입니다). 네 문장 모두 바이너리에 있습니다.

```console
$ grep -E 'insecure_logging|Processing sensitive data|ALLSAFE: Data' strings.txt
Processing sensitive data with flag: FLAG{insecure_logging_exposes_secrets_l0g5}
ALLSAFE: Data processing complete - FLAG{insecure_logging_exposes_secrets_l0g5}
FLAG{insecure_logging_exposes_secrets_l0g5}
```

하나 짚어둘 게 있습니다. 이 네 싱크가 다 같지 않습니다. `NSLog`/`os_log`/`Logger`는 통합
로그(unified log)에 남아서 `idevicesyslog`나 macOS Console/`log stream`으로 수집됩니다. 반면
`print`는 stdout으로 나가 통합 로그엔 안 남고 Xcode 디버거 콘솔에서만 보입니다. 그래서
"기기 연결만으로 새는" 건 앞의 세 개고, `print`는 결이 다릅니다 — 처음엔 저도 넷을 뭉뚱그려
봤다가 이 부분을 갈라 적었습니다. 어느 쪽이든 디버그용 로그가 앱 샌드박스라는 경계를 넘어
비밀을 흘린다는 결론은 같습니다.

바이너리 문자열 테이블을 보다가 `FLAG{vulnerable_vault_exposed_l0g5}`라는, 소스 어디에도
grep되지 않는 플래그도 하나 발견했습니다. 현재 소스 트리가 만들지 않는 잔존/중복 정답
상수로 보입니다. 확실히 소스가 생성하는 값은 위의 `insecure_logging_exposes_secrets` 쪽이라,
이건 "바이너리에 이런 것도 남아 있더라"까지만 적어 둡니다.

---

## 마치며

열네 개를 다 보고 나니 한 문장이 남습니다. iOS 앱이라고 특별히 안전한 게 아니라, 비밀을
어디에 두느냐의 문제라는 겁니다. plist·UserDefaults·SQLite·캐시·바이너리 문자열은 전부
암호화 없이 드러났고, 클라이언트가 내리는 판정(라이선스·PIN·생체·탈옥·피닝)은 정답과 로직이
같이 단말에 있어서 애초에 심판을 공격자에게 맡긴 꼴이었습니다. 방어는 결국 안드로이드 때와
똑같습니다 — 비밀은 Keychain(그것도 제대로 된 접근성 클래스로)이나 서버로, 판정은 서버로,
민감 데이터는 로그·캐시·번들에 남기지 않기.

그런데 이번에 저한테 제일 많이 남은 건 "환경이 방법을 정한다"였습니다. 안드로이드는 Windows
에뮬레이터로 실제로 터뜨려 볼 수 있었는데, iOS는 기기가 없으니 같은 걸 못 합니다. 그래서
처음엔 "이거 반쪽짜리 아닌가" 싶었는데, 막상 배포 IPA를 뜯어 보니 정적 분석만으로도 열세
개 플래그가 그냥 나왔습니다. 대신 생체 콜백 위조나 탈옥 판정 뒤집기처럼 진짜로 실행 흐름을
바꿔야 하는 건 기기 없이는 시연이 안 되니, 그건 방법만 적고 "못 했다"고 그대로 남겼습니다.
파일 공유 챌린지가 배포본엔 아예 없던 것도, 하드코딩 플래그 접미사가 런타임 해시라 정적으론
확정 불가였던 것도 마찬가지로 감추지 않았습니다. 되는 것과 안 되는 것의 경계를 정직하게
긋는 게, 결국 안드로이드판이 저한테 남긴 그 습관이었습니다.

iOS 쪽은 이번에 처음 제대로 들여다봤는데, 정적 분석만으로도 이렇게 많은 게 보인다는 게
신기했고, 나중에 맥이나 탈옥 기기를 구하면 이 글에서 "방법만 적고 못 한" 동적 우회들을
실제로 돌려 보고 싶어졌습니다. 긴 글 여기까지 읽어 주셔서 감사합니다.
