# Android Concept Atlas Evidence App

Concept Atlas 글의 가상 환경 실측 화면을 만드는 읽기 전용 앱입니다. 앱 프로세스 안에서 공개된 시스템 속성과 `/proc` 항목을 읽어 화면에 표시합니다. 공격 코드, 루팅, 우회 기능은 포함하지 않습니다.

```powershell
./build.ps1
adb -s emulator-5580 install -r ./build/atlas-evidence.apk
adb -s emulator-5580 shell am start -n com.example.atlasreport/.MainActivity --es section sandbox
```

지원 섹션은 `environment`, `sandbox`, `kernel`, `boot`, `runtime`, `storage`, `binder`, `network`, `keystore`, `biometric`, `jni`, `package`, `parcel`, `identity`, `uri`입니다. `jni`는 NDK로 빌드한 x86_64 공유 라이브러리를 실제로 로드해 Java→JNI→native→Java 왕복을 검증합니다. 결과는 API 33 Google APIs x86_64 전용 AVD에서 확인합니다.
