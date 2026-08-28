# Host-side build, runtime, and protocol verification

Captured: 2026-08-29 02:13:49 +09:00

이 문서는 전용 API 33 AVD와 로컬 빌드 도구에서 다시 실행한 결과만 기록한다. 물리 기기, TEE, StrongBox, 실제 AVB 퓨즈와 Play 백엔드는 검증 범위가 아니다.

## APK signature verification

명령: `apksigner verify --verbose --print-certs atlas-evidence.apk`

```text
WARNING: A restricted method in java.lang.System has been called
WARNING: java.lang.System::loadLibrary has been called by org.conscrypt.NativeLibraryUtil in an unnamed module (file:/C:/Users/yejun/AppData/Local/Android/Sdk/build-tools/36.0.0/lib/apksigner.jar)
WARNING: Use --enable-native-access=ALL-UNNAMED to avoid a warning for callers in this module
WARNING: Restricted methods will be blocked in a future release unless native access is enabled

Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v3.1 scheme (APK Signature Scheme v3.1): false
Verified using v4 scheme (APK Signature Scheme v4): false
Verified for SourceStamp: false
Number of signers: 1
Signer #1 certificate DN: C=US, O=Android, CN=Android Debug
Signer #1 certificate SHA-256 digest: 766e4a4ce2ecb9bfce171ec829100591aa9f0bbd3fa1a497ad909ee5b9d2feb1
Signer #1 certificate SHA-1 digest: 0679ec7bdf576e4552e0ccd8354faeb2e89c2735
Signer #1 certificate MD5 digest: 92815a7f2913c239a33045c80b9efd1f
Signer #1 key algorithm: RSA
Signer #1 key size (bits): 2048
Signer #1 public key SHA-256 digest: 891a6ba886864b63285675bc48f8419d24ea5fc16a0e06c3a4add53cd1ada4fd
Signer #1 public key SHA-1 digest: 7b98718763372d04f6d18b49a547b62794f0aa6b
Signer #1 public key MD5 digest: 94c8247de9cd5c07d7ddef923088cdb4
[exit=0]
```

## APK manifest and package metadata

명령: `aapt dump badging atlas-evidence.apk`

```text
package: name='com.example.atlasreport' versionCode='' versionName='' platformBuildVersionName='14' platformBuildVersionCode='34' compileSdkVersion='34' compileSdkVersionCodename='14'
sdkVersion:'26'
targetSdkVersion:'33'
uses-permission: name='android.permission.USE_BIOMETRIC'
uses-permission: name='android.permission.USE_FINGERPRINT'
application: label='' icon=''
launchable-activity: name='com.example.atlasreport.MainActivity'  label='' icon=''
feature-group: label=''
  uses-feature: name='android.hardware.faketouch'
  uses-implied-feature: name='android.hardware.faketouch' reason='default feature for all apps'
main
supports-screens: 'small' 'normal' 'large' 'xlarge'
supports-any-density: 'true'
locales:
densities:
native-code: 'x86_64'
[exit=0]
```

## APK file table

명령: `apkanalyzer files list atlas-evidence.apk`

```text
/
/META-INF/
/META-INF/MANIFEST.MF
/META-INF/ANDROIDD.RSA
/META-INF/ANDROIDD.SF
/lib/
/lib/x86_64/
/lib/x86_64/libatlasevidence.so
/classes.dex
/AndroidManifest.xml
[exit=0]
```

## Manifest application id

명령: `apkanalyzer manifest application-id atlas-evidence.apk`

```text
com.example.atlasreport
[exit=0]
```

## DEX package summary

명령: `apkanalyzer dex packages atlas-evidence.apk (Atlas rows)`

```text
P d 15	127	5605	<TOTAL>
P d 15	21	4685	com.example
P d 15	21	4685	com.example.atlasreport
C d 14	20	4552	com.example.atlasreport.MainActivity
M d 1	1	656	com.example.atlasreport.MainActivity <clinit>()
M d 1	1	38	com.example.atlasreport.MainActivity <init>()
M d 1	1	260	com.example.atlasreport.MainActivity java.lang.String biometricReport()
M d 1	1	518	com.example.atlasreport.MainActivity android.widget.TextView commandView(java.lang.String)
M d 1	1	235	com.example.atlasreport.MainActivity java.lang.String identityReport()
M d 1	1	505	com.example.atlasreport.MainActivity java.lang.String keystoreReport()
M d 1	1	12	com.example.atlasreport.MainActivity java.lang.String nativeEvidence()
M d 1	1	501	com.example.atlasreport.MainActivity java.lang.String packageReport()
M d 1	1	307	com.example.atlasreport.MainActivity java.lang.String parcelReport()
M d 1	1	368	com.example.atlasreport.MainActivity java.lang.String run(java.lang.String)
M d 1	1	240	com.example.atlasreport.MainActivity java.lang.String securityLevel(int)
M d 1	1	78	com.example.atlasreport.MainActivity android.widget.TextView text(java.lang.String,int,int,int)
M d 1	1	274	com.example.atlasreport.MainActivity java.lang.String uriReport()
M d 1	1	428	com.example.atlasreport.MainActivity void onCreate(android.os.Bundle)
M r 0	1	8	com.example.atlasreport.MainActivity android.content.pm.ApplicationInfo getApplicationInfo()
M r 0	1	8	com.example.atlasreport.MainActivity android.content.Intent getIntent()
M r 0	1	8	com.example.atlasreport.MainActivity android.content.pm.PackageManager getPackageManager()
M r 0	1	8	com.example.atlasreport.MainActivity java.lang.String getPackageName()
M r 0	1	8	com.example.atlasreport.MainActivity java.lang.Object getSystemService(java.lang.String)
M r 0	1	8	com.example.atlasreport.MainActivity void setContentView(android.view.View)
F d 0	0	18	com.example.atlasreport.MainActivity java.util.Map COMMANDS
F d 0	0	10	com.example.atlasreport.MainActivity int CYAN
C d 1	1	133	com.example.atlasreport.MainActivity$$ExternalSyntheticBackport0
M d 1	1	93	com.example.atlasreport.MainActivity$$ExternalSyntheticBackport0 void m(java.lang.Throwable,java.lang.Throwable)
[exit=0]
```

## JNI ELF hardening metadata

명령: `llvm-readelf -h -l -d -n libatlasevidence.so`

```text
ELF Header:
  Magic:   7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00
  Class:                             ELF64
  Data:                              2's complement, little endian
  Version:                           1 (current)
  OS/ABI:                            UNIX - System V
  ABI Version:                       0
  Type:                              DYN (Shared object file)
  Machine:                           Advanced Micro Devices X86-64
  Version:                           0x1
  Entry point address:               0x0
  Start of program headers:          64 (bytes into file)
  Start of section headers:          3816 (bytes into file)
  Flags:                             0x0
  Size of this header:               64 (bytes)
  Size of program headers:           56 (bytes)
  Number of program headers:         9
  Size of section headers:           64 (bytes)
  Number of section headers:         23
  Section header string table index: 21

Elf file type is DYN (Shared object file)
Entry point 0x0
There are 9 program headers, starting at offset 64

Program Headers:
  Type           Offset   VirtAddr           PhysAddr           FileSiz  MemSiz   Flg Align
  PHDR           0x000040 0x0000000000000040 0x0000000000000040 0x0001f8 0x0001f8 R   0x8
  LOAD           0x000000 0x0000000000000000 0x0000000000000000 0x00062c 0x00062c R   0x1000
  LOAD           0x000630 0x0000000000001630 0x0000000000001630 0x000110 0x000110 R E 0x1000
  LOAD           0x000740 0x0000000000002740 0x0000000000002740 0x0001c0 0x0008c0 RW  0x1000
  DYNAMIC        0x000758 0x0000000000002758 0x0000000000002758 0x000170 0x000170 RW  0x8
  GNU_RELRO      0x000740 0x0000000000002740 0x0000000000002740 0x0001c0 0x0008c0 R   0x1
  GNU_EH_FRAME   0x000528 0x0000000000000528 0x0000000000000528 0x000044 0x000044 R   0x4
  GNU_STACK      0x000000 0x0000000000000000 0x0000000000000000 0x000000 0x000000 RW  0x0
  NOTE           0x000238 0x0000000000000238 0x0000000000000238 0x000098 0x000098 R   0x4

 Section to Segment mapping:
  Segment Sections...
   00
   01     .note.android.ident .dynsym .gnu.version .gnu.version_r .gnu.hash .dynstr .rela.dyn .rela.plt .rodata .eh_frame_hdr .eh_frame
   02     .text .plt
   03     .data.rel.ro .fini_array .dynamic .got.plt .relro_padding
   04     .dynamic
   05     .data.rel.ro .fini_array .dynamic .got.plt .relro_padding
   06     .eh_frame_hdr
   07
   08     .note.android.ident
   None   .comment .symtab .shstrtab .strtab
Dynamic section at offset 0x758 contains 23 entries:
  Tag                Type           Name/Value
  0x0000000000000001 (NEEDED)       Shared library: [libdl.so]
  0x0000000000000001 (NEEDED)       Shared library: [libc.so]
  0x000000000000001e (FLAGS)        BIND_NOW
  0x000000006ffffffb (FLAGS_1)      NOW
  0x0000000000000007 (RELA)         0x438
  0x0000000000000008 (RELASZ)       72 (bytes)
  0x0000000000000009 (RELAENT)      24 (bytes)
  0x000000006ffffff9 (RELACOUNT)    3
  0x0000000000000017 (JMPREL)       0x480
  0x0000000000000002 (PLTRELSZ)     96 (bytes)
  0x0000000000000003 (PLTGOT)       0x28c8
  0x0000000000000014 (PLTREL)       RELA
  0x0000000000000006 (SYMTAB)       0x2d0
  0x000000000000000b (SYMENT)       24 (bytes)
  0x0000000000000005 (STRTAB)       0x3b0
  0x000000000000000a (STRSZ)        135 (bytes)
  0x000000006ffffef5 (GNU_HASH)     0x390
  0x000000000000001a (FINI_ARRAY)   0x2748
  0x000000000000001c (FINI_ARRAYSZ) 16 (bytes)
  0x000000006ffffff0 (VERSYM)       0x360
  0x000000006ffffffe (VERNEED)      0x36c
  0x000000006fffffff (VERNEEDNUM)   1
  0x0000000000000000 (NULL)         0x0
Displaying notes found in: .note.android.ident
  Owner                Data size 	Description
  Android              0x00000084	NT_ANDROID_TYPE_IDENT
   description data: 1a 00 00 00 72 32 37 64 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 31 33 37 35 30 37 32 34 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
[exit=0]
```

## AVD APK installation

명령: `adb -s emulator-5580 install -r atlas-evidence.apk`

```text
Performing Incremental Install
Performing Streamed Install
Success
[exit=0]
```

## 15-section AVD activity sweep

명령: `am start -W ... --es section <name>; logcat -b crash`

```text
environment : Status=ok
sandbox : Status=ok
kernel : Status=ok
boot : Status=ok
runtime : Status=ok
storage : Status=ok
binder : Status=ok
network : Status=ok
keystore : Status=ok
biometric : Status=ok
jni : Status=ok
package : Status=ok
parcel : Status=ok
identity : Status=ok
uri : Status=ok
crash-buffer : PASS (no FATAL EXCEPTION)
[exit=0]
```

## TLS 1.3 request to developer.android.com

명령: `curl -I --tlsv1.3 https://developer.android.com`

```text
HTTP/1.1 200 OK
last-modified: Thu, 27 Aug 2026 13:29:38 GMT
content-type: text/html; charset=utf-8
vary: Cookie
content-security-policy: base-uri 'self'; object-src 'none'; script-src 'strict-dynamic' 'unsafe-inline' https: http: 'nonce-aUnJmr7akEZLKG4Jx0PpnU21jjhAas' 'unsafe-eval'; frame-ancestors 'self' https://developers.google.com/_d/analytics-iframe; report-uri https://csp.withgoogle.com/csp/devsite/v2
strict-transport-security: max-age=63072000; includeSubdomains; preload
x-xss-protection: 0
x-content-type-options: nosniff
cache-control: no-cache, must-revalidate
expires: 0
pragma: no-cache
x-cloud-trace-context: 96580dabd131409c0a6d643af32fb439
[exit=0]
```

## UBSan safe/overflow control

명령: `build-and-run-ubsan.ps1`

```text
C:\Users\yejun\Documents\Codex\2026-08-22\so\blog-source\labs\android-concept-atlas-evidence-app\build\ubsan\ubsan_probe: 1 file pushed, 0 skipped. 18.4 MB/s (7776 bytes in 0.000s)
C:\Users\yejun\AppData\Local\Android\Sdk\ndk\27.3.13750724\toolchains\llvm\prebuilt\windows-x86_64\lib\clang\18\lib\linux\libclang_rt.ubsan_standalone-x86_64-android.so: 1 file pushed, 0 skipped. 176.5 MB/s (870032 bytes in 0.005s)
[safe exit=0]
safe-result=42
[overflow exit=134]
C:\Users\yejun\Documents\Codex\2026-08-22\so\blog-source\labs\android-concept-atlas-evidence-app\jni\ubsan_probe.c:13:46: runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior C:\Users\yejun\Documents\Codex\2026-08-22\so\blog-source\labs\android-concept-atlas-evidence-app\jni\ubsan_probe.c:13:46 in
Aborted
ubsan-verification=PASS
[exit=0]
```

## Patch-before/after matrix

명령: `run-matrix.ps1`

```text
## normal
before exit=0
before offset=10 length=20 total=100 end=30 decision=ACCEPT
after exit=0
after offset=10 length=20 total=100 decision=ACCEPT
## boundary
before exit=0
before offset=80 length=20 total=100 end=100 decision=ACCEPT
after exit=0
after offset=80 length=20 total=100 decision=ACCEPT
## range-error
before exit=1
before offset=90 length=20 total=100 end=110 decision=REJECT
after exit=1
after offset=90 length=20 total=100 decision=REJECT
## overflow
before exit=134
C:\Users\yejun\Documents\Codex\2026-08-22\so\blog-source\labs\android-concept-atlas-research-method\length_check_before.c:10:26: runtime error: signed integer overflow: 2147483640 + 16 cannot be represented in type 'int32_t' (aka 'int')
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior C:\Users\yejun\Documents\Codex\2026-08-22\so\blog-source\labs\android-concept-atlas-research-method\length_check_before.c:10:26 in
Aborted
after exit=1
after offset=2147483640 length=16 total=4096 decision=REJECT

patch-diff-matrix=PASS
[exit=0]
```

## Jekyll production build

명령: `bundle exec jekyll build`

```text
Configuration file: C:/Users/yejun/Documents/Codex/2026-08-22/so/blog-source/_config.yml
            Source: C:/Users/yejun/Documents/Codex/2026-08-22/so/blog-source
       Destination: C:/Users/yejun/Documents/Codex/2026-08-22/so/blog-source/_site
 Incremental build: disabled. Enable with --incremental
      Generating...
       Jekyll Feed: Generating feed for posts
                    done in 4.751 seconds.
 Auto-regeneration: disabled. Use --watch to enable.
[exit=0]
```

## Final verdict

- `PASS`: APK v2/v3 서명, APK/DEX/ELF 구조, 설치, 15개 화면 실행, crash scan, TLS 1.3, UBSan 대조군, patch-before/after 행렬, Jekyll 빌드.
- `EXPECTED DENY`: 앱 샌드박스가 막은 보호 파일·속성 접근은 격리 통제가 작동한 결과다.
- `LIMIT`: AVD에 없는 TEE·StrongBox·Weaver·하드웨어 AVB/rollback fuse·Play Integrity 프로덕션 verdict는 성공으로 표시하지 않는다.
