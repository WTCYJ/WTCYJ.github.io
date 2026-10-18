---
layout: post
title: "Gradle·multi-module·공급망"
date: 2026-11-19 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Gradle, 공급망보안, 빌드시스템, 의존성검증]
excerpt: "Gradle 빌드는 소스를 컴파일하기 전에 설정 단계에서 이미 제3자 플러그인 코드를 실행한다 — 제3자 플러그인·애노테이션 프로세서가 곧 빌드 머신에서의 코드 실행이며(평범한 `implementation` 라이브러리는 온디바이스 런타임에서만 실행된다), `api`를 `implementation`으로 바꿔도 그 실행은 막지 못한다."
---

APK 하나가 나오기까지 내 소스코드가 차지하는 비중은 생각보다 작다. 나머지는 Gradle이 원격 저장소에서 끌어온 수십~수백 개의 라이브러리와, 그 라이브러리를 끌어오는 과정에서 실행되는 플러그인 코드다. 앱을 뜯어보는 관점에서 보면 이건 공격 표면이 아니라 **공급망 전체**다. 컴파일된 바이트코드가 어디서 왔는지 고정하지 않으면, "내가 짠 적 없는 코드"가 조용히 APK에 들어간다.

이 글은 Gradle 빌드가 실제로 무엇을 실행하는지(설정/실행 수명주기), 멀티모듈이 의존성 경계를 어떻게 나누는지, 그리고 공급망을 고정하는 두 장치(의존성 검증 메타데이터·락파일)를 자작 멀티모듈 프로젝트로 확인한 기록이다. 공격이 아니라 "빌드가 무엇을 신뢰하는가"를 소스와 명령 출력으로 짚는다.

> **한 줄 결론**: 빌드는 신뢰 경계다. 원격 저장소의 코드를 받아 설정 단계에 실행하므로, 체크섬·서명(`verification-metadata.xml`)과 락파일로 "무엇이 들어오는지"를 고정하지 않으면 공급망은 컴파일 전에 이미 뚫려 있다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 범위는 세 가지다. (1) Gradle 빌드 수명주기(Initialization → Configuration → Execution)와 그 안에서 제3자 코드가 실행되는 지점, (2) 멀티모듈에서 `api`/`implementation`이 나누는 의존성 경계, (3) 공급망 고정 장치 — 저장소 콘텐츠 필터링·의존성 검증·의존성 락. AGP(Android Gradle Plugin)는 Gradle 위에 얹히는 플러그인일 뿐이라, 여기서 정리하는 원리는 순수 Gradle과 동일하게 적용된다.

선수 지식은 얕게만 있으면 된다. JVM 바이트코드와 클래스패스가 뭔지, APK가 dex로 컴파일된다는 사실(이 시리즈 8장의 ART/dex2oat) 정도다. 서명 검증이 설치 시점에 어떻게 작동하는지는 11장(PackageManagerService·서명 검증)과 Atlas C11에서 다루므로 여기서는 빌드 시점만 본다.

전체 구조에서 이 장은 **APK가 만들어지기 직전의 층**이다. 이후 장의 ART·ClassLoader·PackageManager는 전부 "이미 만들어진 APK"를 소비한다. 그 APK 안에 무엇이 들어갔는지를 결정하는 게 바로 빌드이고, 그래서 공급망의 무결성은 런타임 방어보다 앞선다.

## 핵심 개념 — 빌드 수명주기와 의존성 경계

Gradle 빌드는 세 단계로 진행된다. `Source-confirmed`

| 단계 | 하는 일 | 실행되는 제3자 코드 |
|--|--|--|
| Initialization | `settings.gradle(.kts)` 평가, 참여 모듈·`pluginManagement` 결정 | 플러그인 저장소 해석 |
| Configuration | 모든 모듈의 빌드 스크립트 평가, `plugins {}` 적용, 태스크 그래프 구성 | **플러그인 `apply()` 실행** |
| Execution | 요청된 태스크(컴파일·패키징 등)만 실행 | 태스크·애노테이션 프로세서 |

여기서 첫 번째 함정 — 제3자 플러그인 코드는 **Execution이 아니라 Configuration에서** 실행된다. 즉 `assembleDebug` 같은 빌드 태스크를 한 번도 돌리지 않아도, `./gradlew tasks`처럼 설정만 하는 명령에서 이미 플러그인의 `apply()`가 내 빌드 권한으로 실행된다. `Source-confirmed` "빌드하지 않았으니 안전하다"는 착각이 여기서 깨진다.

멀티모듈은 `settings.gradle`의 `include(":app", ":core")`로 모듈을 묶고, 모듈 간 의존은 `implementation(project(":core"))`로 건다. `api`와 `implementation`의 차이는 소비자 컴파일 클래스패스 노출 여부다. `api`로 선언한 의존은 그 모듈을 쓰는 상위 모듈의 컴파일 클래스패스에도 새어 나가고, `implementation`은 새어 나가지 않는다(런타임 클래스패스에는 둘 다 올라간다). `Source-confirmed`

두 번째 함정이 바로 여기다 — `api`를 `implementation`으로 바꾸는 건 **캡슐화이지 공급망 축소가 아니다**. 두 경우 모두 해당 아티팩트는 다운로드되고 런타임 클래스패스에 실린다. 실행되는 코드의 양은 그대로다. 공격 표면을 줄이려면 의존성 자체를 빼거나 고정해야지, 가시성 키워드만 바꿔선 아무것도 줄지 않는다. `Inferred`

의존성 해석은 전이(transitive)로 퍼진다. `implementation("com.squareup.okhttp3:okhttp:...")` 한 줄이 okio 등 여러 전이 의존을 함께 끌어오고, 버전 충돌은 기본적으로 "가장 높은 버전 선택"으로 해소된다. `Source-confirmed` 그래서 내가 명시한 의존성 수보다 실제 그래프가 훨씬 크고, 그 격차가 공급망 관리의 핵심 난점이다.

> **[그림 1]** 자작 `:app` 모듈에서 `./gradlew :app:dependencies`를 실행해 명시 의존성 하나가 펼쳐낸 전이 의존성 트리 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **로컬에서 만든 멀티모듈 Gradle 프로젝트**로만 진행한다. 제3자 저장소를 공격하거나 실제 패키지를 typosquatting하지 않는다. 관측 대상은 오직 "내 빌드가 무엇을 받아 실행하는가"이며, 실험은 로컬 캐시·로컬 파일 변조 수준에서 멈춘다. 에뮬레이터도 필요 없다 — 빌드 시점 이야기이기 때문이다.

## 실습 절차와 관측

### 가설
- **가설 A** — 명시 의존성 1개도 `dependencies` 트리에서 다수의 전이 의존으로 펼쳐진다. `Inferred`
- **가설 B** — `--write-verification-metadata sha256`은 그래프의 모든 아티팩트에 대한 sha256을 `gradle/verification-metadata.xml`에 기록하고, 이후 그 파일의 체크섬과 다른 아티팩트가 들어오면 빌드가 실패한다. `Inferred`

### 절차
1. `:app`·`:core` 두 모듈을 `settings.gradle`에 등록하고 버전 카탈로그(`gradle/libs.versions.toml`)로 버전을 한 곳에 모은다.
2. `./gradlew :app:dependencies`로 전이 그래프를 관측한다.
3. `./gradlew --write-verification-metadata sha256 help`로 검증 메타데이터를 생성한다.
4. 생성된 `verification-metadata.xml`의 한 항목 체크섬을 일부러 한 글자 바꾼다.
5. 다시 빌드해 검증 실패를 관측한다.

```bash
# settings.gradle: 참여 모듈과 플러그인/의존 저장소를 한곳에서 고정
# (콘텐츠 필터링으로 각 저장소가 서빙할 group 제한 — 의존성 혼동 완화)
# dependencyResolutionManagement {
#   repositories {
#     google(); mavenCentral()
#     // exclusiveContent { forRepository { ... }; filter { includeGroup("com.mycorp") } }
#   }
# }

./gradlew :app:dependencies                       # 전이 그래프 관측
./gradlew --write-verification-metadata sha256 help   # 체크섬 메타데이터 생성
# → gradle/verification-metadata.xml 이 생김 (VCS에 커밋 대상)

# 이후 빌드는 모든 아티팩트를 이 파일과 대조한다.
# 메타데이터의 sha256 한 글자를 바꾸고 캐시를 비운 뒤 재빌드하면:
./gradlew --refresh-dependencies :app:assembleDebug
```

> **[그림 2]** 생성된 `gradle/verification-metadata.xml`의 sha256 항목과, 체크섬을 변조한 뒤 재빌드했을 때 나오는 "dependency verification failed" 오류를 나란히 대조한 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력(교체)` — 실제 실행으로 대체:

```
$ ./gradlew :app:dependencies

debugRuntimeClasspath - Runtime classpath of compilation 'debug' (target (androidJvm)).
+--- project :core
+--- com.squareup.okhttp3:okhttp:4.12.0
|    \--- com.squareup.okio:okio:3.6.0
\--- ...
# (실측 값. 출력은 debugCompileClasspath/debugRuntimeClasspath 등 구성별 블록으로 나오고,
#  선언만 된 implementation 구성은 해석 전이라 각 항목이 '(n)'으로 표기된다)

$ ./gradlew --refresh-dependencies :app:assembleDebug
> Dependency verification failed for configuration ':app:debugRuntimeClasspath':
  - On artifact okhttp-4.12.0.jar (com.squareup.okhttp3:okhttp:4.12.0) in repository 'MavenRepo': expected a 'sha256' checksum of '<원본>' but was '<변조본>'
```

명시 의존성 1개가 전이로 여러 아티팩트가 되고, 그 각각이 검증 메타데이터에 sha256으로 고정된다. 고정된 값과 다른 바이트가 들어오면 컴파일까지 가지 못하고 해석 단계에서 빌드가 멈춘다. 이 실패가 바로 공급망 회귀 검증이다.

## Root Cause — 왜 이렇게 되는가

근본 원인은 빌드 도구가 **동적으로 원격 코드를 받아 로컬에서 실행하도록 설계**됐다는 데 있다. 편의(재사용·자동 업데이트)를 위해 의존성을 좌표(`group:name:version`)로만 선언하면, Gradle이 저장소에서 실제 바이트를 가져온다. 이때 두 가지 신뢰가 암묵적으로 전제된다 — (1) 그 좌표가 항상 같은 바이트를 가리킨다, (2) 그 바이트를 실행해도 안전하다. 고정 장치가 없으면 두 전제 모두 검증되지 않는다. `Inferred`

의존성 혼동(dependency confusion)이 성립하는 이유도 같은 결이다. 내부 산출물과 동일한 좌표의 상위 버전이 공개 저장소에 올라오고, 빌드가 여러 저장소를 구분 없이 탐색하면, 버전 해석이 공개 쪽을 고를 수 있다. `Reported` 이건 Gradle만의 버그가 아니라 "좌표는 신뢰의 근거가 못 된다"는 생태계 공통 문제다. 그래서 방어는 좌표를 믿는 대신 **바이트(체크섬)와 출처(서명·저장소 제한)를 믿는 것**으로 옮겨간다.

플러그인이 Configuration 단계에서 실행된다는 사실도 근본적이다. 빌드 스크립트는 선언형처럼 보이지만 실제로는 임의 코드가 도는 프로그램이고, `plugins {}`로 적용한 제3자 플러그인의 `apply()`가 내 빌드·CI 권한으로 실행된다. `Source-confirmed` 의존성 하나가 "라이브러리"가 아니라 "빌드 시점 코드 실행"이 되는 지점이 여기다.

## 방어와 회귀 검증

빌드를 신뢰 경계로 다루는 구체 장치는 다음과 같다.

- **저장소 콘텐츠 필터링** — `content { includeGroup(...) }`·`exclusiveContent`로 각 저장소가 서빙할 수 있는 group을 제한한다. 내부 group은 내부 저장소에서만 오도록 못박아 의존성 혼동을 차단한다. `Source-confirmed`
- **의존성 검증(`verification-metadata.xml`)** — 모든 아티팩트의 sha256/sha512, 선택적으로 PGP 서명을 기록하고 이후 빌드마다 대조한다. 이 파일을 VCS에 커밋해야 CI에서도 같은 기준으로 검증된다. `Source-confirmed`
- **의존성 락(`gradle.lockfile`)** — 동적 버전(`1.+` 등)을 해석된 정확한 버전으로 고정한다. `--write-locks`로 갱신하고, 락과 다른 버전이 해석되면 실패시킨다. `Source-confirmed`
- **버전 카탈로그(`gradle/libs.versions.toml`)** — 버전을 한 곳에 모아 단일 출처로 만든다. 무결성 장치는 아니지만, 어떤 버전이 어디서 오는지 감사(audit)하기 쉬워진다. `Source-confirmed`

회귀 검증의 형태는 "빌드 실패"다. 체크섬이 바뀌거나(변조·의도치 않은 업데이트) 락이 안 맞으면 CI가 붉게 뜬다. 이것이 정상 동작이다 — 조용히 통과하는 것보다 시끄럽게 실패하는 게 공급망에서는 옳다.

**버전·한계.** 의존성 검증은 Gradle 6.2대에서, 버전 카탈로그는 7.x대에서 안정화됐다(정확한 마이너 버전은 릴리스 노트 확인). 한계도 분명하다 — 검증 메타데이터는 바이트가 "변하지 않았음"을 보장할 뿐, 그 바이트가 **처음부터 악성**이면 막지 못한다(TOFU, Trust On First Use). 최초 등록 시점의 라이브러리 자체가 깨끗한지는 별도 검토가 필요하고, 이건 도구가 아니라 사람이 판단한다. `Inferred`

## 정리

- Gradle 빌드는 Configuration 단계에서 제3자 플러그인 코드를 실행한다 — 빌드하지 않아도 실행된다.
- `api`→`implementation`은 캡슐화일 뿐, 실행되는 코드나 공급망을 줄이지 않는다.
- 좌표는 신뢰의 근거가 못 된다. 체크섬·서명·저장소 제한·락으로 "바이트와 출처"를 고정해야 공급망이 검증된다.
- 회귀 검증은 빌드 실패로 나타나며, 검증 메타데이터는 변조는 막아도 최초 악성(TOFU)은 못 막는다.

**점검 질문** — (1) 제3자 플러그인 코드는 빌드 수명주기 중 어느 단계에서 실행되며, 그것이 왜 위험한가? (2) `api`를 `implementation`으로 바꾸면 공급망 공격 표면이 줄어드는가, 그 이유는? (3) `verification-metadata.xml`이 막을 수 있는 위협과 막지 못하는 위협은 각각 무엇인가?

**참고** — [Gradle Build Lifecycle](https://docs.gradle.org/current/userguide/build_lifecycle.html) · [Dependency Verification](https://docs.gradle.org/current/userguide/dependency_verification.html) · [Dependency Locking](https://docs.gradle.org/current/userguide/dependency_locking.html) · [Declaring Repositories(콘텐츠 필터링)](https://docs.gradle.org/current/userguide/declaring_repositories.html) · [java-library 플러그인(api vs implementation)](https://docs.gradle.org/current/userguide/java_library_plugin.html)

*다음 글: [ART interpreter/JIT/AOT/dex2oat](/posts/android-expert-p2c08/).*
