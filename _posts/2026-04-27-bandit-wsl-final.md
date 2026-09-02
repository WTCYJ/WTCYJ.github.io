---
layout: post
title: "[Wargame] OverTheWire Bandit LV0 → LV25 상세 풀이"
date: 2026-04-27
category: 시스템
author: WTCY
tags: [OverTheWire, Bandit, Wargame, Linux, SSH]
---

> **플랫폼:** [OverTheWire — Bandit](https://overthewire.org/wargames/bandit/)
> **목적:** Linux 기초 명령어 / 파일 시스템 / 네트워크 / 권한 상승

---

## LV0 → LV1

### 목표
home 디렉토리의 readme 파일에서 비밀번호 찾기

### SSH 접속
```bash
ssh bandit0@bandit.labs.overthewire.org -p 2220
# 비밀번호: bandit0
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ ls
yejun@yejunhc:/mnt/c/windows/system32$ cat readme
```

### 학습 개념
- `ls` : 현재 디렉토리의 파일 목록 출력
- `cat` : 파일 내용 출력

### 획득 비밀번호
```
ZjLjTmM6FvvyRnrb2rfNWOZOTa6ip5If
```

---

## LV1 → LV2

### 목표
파일명이 `-`(대시)인 파일 읽기

### SSH 접속
```bash
ssh bandit1@bandit.labs.overthewire.org -p 2220
# 비밀번호: ZjLjTmM6FvvyRnrb2rfNWOZOTa6ip5If
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ ls
yejun@yejunhc:/mnt/c/windows/system32$ cat ./-
```

### 학습 개념
- `-`는 리눅스에서 **stdin(표준입력)** 으로 인식됨
- `cat -`만 치면 파일을 읽지 못하고 입력 대기 상태에 빠짐
- `./`를 앞에 붙여 **경로로 명시**해야 파일로 인식

### 획득 비밀번호
```
263JGJPfgU6LtdEvgfWU1XP5yac29mFx
```

---

## LV2 → LV3

### 목표
파일명에 공백이 포함된 파일 읽기

### SSH 접속
```bash
ssh bandit2@bandit.labs.overthewire.org -p 2220
# 비밀번호: 263JGJPfgU6LtdEvgfWU1XP5yac29mFx
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ ls
yejun@yejunhc:/mnt/c/windows/system32$ cat ./*
# 또는
yejun@yejunhc:/mnt/c/windows/system32$ cat "spaces in this filename"
```

### 학습 개념
- 리눅스 쉘은 **공백을 인자 구분자**로 처리
- 공백이 포함된 파일명은 **따옴표로 감싸거나** 와일드카드(`*`) 사용

### 획득 비밀번호
```
MNk8KNH3Usiio41PRUEoDFPqfxLPlSmx
```

---

## LV3 → LV4

### 목표
`inhere/` 디렉토리 안의 숨김 파일 읽기

### SSH 접속
```bash
ssh bandit3@bandit.labs.overthewire.org -p 2220
# 비밀번호: MNk8KNH3Usiio41PRUEoDFPqfxLPlSmx
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ ls
yejun@yejunhc:/mnt/c/windows/system32$ ls -la inhere/
yejun@yejunhc:/mnt/c/windows/system32$ cat inhere/...Hiding-From-You
```

### 학습 개념
- 리눅스에서 `.`으로 시작하는 파일은 **숨김 파일**
- `ls`만 치면 보이지 않음
- `ls -la` 옵션으로 숨김 파일까지 확인 가능

### 획득 비밀번호
```
2WmrDFRmJIq3IPxneAaMGhap0pFhF3NJ
```

---

## LV4 → LV5

### 목표
`inhere/` 안 10개 파일 중 사람이 읽을 수 있는(ASCII) 파일만 찾기

### SSH 접속
```bash
ssh bandit4@bandit.labs.overthewire.org -p 2220
# 비밀번호: 2WmrDFRmJIq3IPxneAaMGhap0pFhF3NJ
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ file inhere/./*
yejun@yejunhc:/mnt/c/windows/system32$ cat inhere/./-file07
```

### 학습 개념
- `file` 명령어로 파일의 실제 형식 확인
- **ASCII text** 라고 뜨는 파일이 사람이 읽을 수 있는 파일

### 획득 비밀번호
```
4oQYVPkxZOOEOO5pTW81FB8j8lxXGUQw
```

---

## LV5 → LV6

### 목표
아래 조건을 모두 만족하는 파일 찾기
- 사람이 읽을 수 있음
- 크기: 1033 bytes
- 실행 불가능

### SSH 접속
```bash
ssh bandit5@bandit.labs.overthewire.org -p 2220
# 비밀번호: 4oQYVPkxZOOEOO5pTW81FB8j8lxXGUQw
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ find inhere -type f -size 1033c ! -executable
yejun@yejunhc:/mnt/c/windows/system32$ cat inhere/maybehere07/.file2
```

### 학습 개념

| 옵션 | 설명 |
|------|------|
| `-type f` | 파일만 탐색 |
| `-size 1033c` | 크기 1033 bytes (`c` = bytes) |
| `! -executable` | 실행 불가 파일 |

### 획득 비밀번호
```
HWasnPhtq9AVKe0dmk45nxy20cvUa6EG
```

---

## LV6 → LV7

### 목표
서버 어딘가에 있는 파일 탐색 (조건 3가지)
- 소유자: bandit7
- 그룹: bandit6
- 크기: 33 bytes

### SSH 접속
```bash
ssh bandit6@bandit.labs.overthewire.org -p 2220
# 비밀번호: HWasnPhtq9AVKe0dmk45nxy20cvUa6EG
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ find / -user bandit7 -group bandit6 -size 33c 2>/dev/null
```

### 학습 개념
- `find /` : 루트(/)부터 전체 서버 탐색
- `2>/dev/null` : **에러 메시지를 버림** → 권한 없는 디렉토리 에러 숨기기
- `-user`, `-group` 옵션으로 소유자/그룹 지정

### 획득 비밀번호
```
morbNTDkSW6jIlUc0ymOdMaLnOlFVAaj
```

---

## LV7 → LV8

### 목표
`data.txt`에서 `millionth` 단어 옆에 있는 비밀번호 찾기

### SSH 접속
```bash
ssh bandit7@bandit.labs.overthewire.org -p 2220
# 비밀번호: morbNTDkSW6jIlUc0ymOdMaLnOlFVAaj
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ grep millionth data.txt
```

### 학습 개념
- `grep` : 파일에서 **특정 패턴이 포함된 줄**을 검색해서 출력
- 수십만 줄 파일에서도 즉시 원하는 줄을 찾아냄

### 획득 비밀번호
```
dfwvzFQi4mU0wfNbFOe9RoWskMLg7eEc
```

---

## LV8 → LV9

### 목표
`data.txt`에서 딱 한 번만 등장하는 줄 찾기

### SSH 접속
```bash
ssh bandit8@bandit.labs.overthewire.org -p 2220
# 비밀번호: dfwvzFQi4mU0wfNbFOe9RoWskMLg7eEc
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ sort data.txt | uniq -u
```

### 학습 개념
- `sort` : 줄을 알파벳순으로 정렬
- `uniq -u` : **인접한 중복 줄 제거** 후 유일한 줄만 출력
- `uniq`는 인접한 줄끼리만 비교하므로 반드시 **sort 후 사용**

### 획득 비밀번호
```
4CKMh1JI91bUIZZPXDqGanal4xvAg0JM
```

---

## LV9 → LV10

### 목표
`data.txt`(바이너리)에서 `=`로 시작하는 사람이 읽을 수 있는 문자열 찾기

### SSH 접속
```bash
ssh bandit9@bandit.labs.overthewire.org -p 2220
# 비밀번호: 4CKMh1JI91bUIZZPXDqGanal4xvAg0JM
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ strings data.txt | grep ==
```

### 학습 개념
- `strings` : **바이너리 파일에서 사람이 읽을 수 있는 문자열만 추출**
- 바이너리 분석의 첫 번째 단계로 자주 사용
- `grep ==` 으로 `=`이 포함된 줄만 필터링

### 획득 비밀번호
```
FGUW5ilLVJrxX9kMYMmlN4MgbpfMiqey
```

---

## LV10 → LV11

### 목표
`data.txt`는 base64로 인코딩된 파일 → 디코딩

### SSH 접속
```bash
ssh bandit10@bandit.labs.overthewire.org -p 2220
# 비밀번호: FGUW5ilLVJrxX9kMYMmlN4MgbpfMiqey
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ cat data.txt
yejun@yejunhc:/mnt/c/windows/system32$ base64 -d data.txt
```

### 학습 개념
- **base64** : 바이너리 데이터를 ASCII 문자로 표현하는 인코딩 방식
- 암호화가 아니라 **인코딩** → `-d` 옵션 하나로 바로 원문 복원 가능

### 획득 비밀번호
```
dtR173fZKb0RRsDFSGsg2RWnpNVj3qRr
```

---

## LV11 → LV12

### 목표
`data.txt`는 ROT13으로 인코딩 → 알파벳을 13자리 이동하여 디코딩

### SSH 접속
```bash
ssh bandit11@bandit.labs.overthewire.org -p 2220
# 비밀번호: dtR173fZKb0RRsDFSGsg2RWnpNVj3qRr
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ cat data.txt
yejun@yejunhc:/mnt/c/windows/system32$ cat data.txt | tr 'a-zA-Z' 'n-za-mN-ZA-M'
```

### 학습 개념
- **ROT13** : 알파벳을 13칸 밀어서 치환하는 단순 암호
- `tr` 명령어 : **문자를 다른 문자로 치환**
- `tr 'a-zA-Z' 'n-za-mN-ZA-M'` → a는 n으로, b는 o로 ... 13칸씩 이동

### 획득 비밀번호
```
7x16WNeHIi5YkIhWsfFIqoognUTyj9Q4
```

---

## LV12 → LV13

### 목표
`data.txt`는 hexdump 파일 → 바이너리 변환 후 반복 압축 해제

### SSH 접속
```bash
ssh bandit12@bandit.labs.overthewire.org -p 2220
# 비밀번호: 7x16WNeHIi5YkIhWsfFIqoognUTyj9Q4
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ mkdir /tmp/mywork
yejun@yejunhc:/mnt/c/windows/system32$ cp data.txt /tmp/mywork/
yejun@yejunhc:/mnt/c/windows/system32$ cd /tmp/mywork
yejun@yejunhc:/mnt/c/windows/system32$ xxd -r data.txt > d0       # hexdump → 바이너리 변환
yejun@yejunhc:/mnt/c/windows/system32$ file d0                    # 파일 형식 확인 후 반복

# gzip인 경우
mv d0 d0.gz && gzip -d d0.gz

# bzip2인 경우
mv d0 d0.bz2 && bzip2 -d d0.bz2

# tar인 경우
tar -xf d0

# ASCII text 나올 때까지 반복
yejun@yejunhc:/mnt/c/windows/system32$ cat 최종파일
```

### 압축 해제 명령어 정리

| 형식 | 명령어 |
|------|--------|
| gzip | `gzip -d 파일.gz` |
| bzip2 | `bzip2 -d 파일.bz2` |
| tar | `tar -xf 파일` |

### 학습 개념
- `xxd -r` : **hexdump를 바이너리 파일로 역변환**
- `file` : 파일의 실제 형식 확인 (확장자 무관)
- 여러 겹으로 압축된 파일을 단계별로 해제하는 패턴

### 획득 비밀번호
```
FO5dwFsc0cbaIiH0h8J2eUks2vdTDwAn
```

---

## LV13 → LV14

### 목표
비밀번호 대신 SSH 개인키(`sshkey.private`)로 다음 레벨 접속

### SSH 접속
```bash
ssh bandit13@bandit.labs.overthewire.org -p 2220
# 비밀번호: FO5dwFsc0cbaIiH0h8J2eUks2vdTDwAn
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ ls
yejun@yejunhc:/mnt/c/windows/system32$ ssh -i sshkey.private bandit14@localhost -p 2220
yejun@yejunhc:/mnt/c/windows/system32$ cat /etc/bandit_pass/bandit14
```

### 학습 개념
- SSH는 비밀번호 외에 **개인키 파일로도 인증** 가능
- `-i` 옵션 : identity file(개인키 파일) 지정
- 공개키/개인키 쌍으로 인증하는 방식 → 실제 서버 접속에서도 자주 사용

### 획득 비밀번호
```
MU4VWeTyJk8ROof1qqmcBPaLh7lDCPvS
```

---

## LV14 → LV15

### 목표
localhost의 port 30000에 현재 레벨 비밀번호를 전송하면 다음 비밀번호 수신

### SSH 접속
```bash
ssh bandit14@bandit.labs.overthewire.org -p 2220
# 비밀번호: MU4VWeTyJk8ROof1qqmcBPaLh7lDCPvS
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ echo MU4VWeTyJk8ROof1qqmcBPaLh7lDCPvS | nc localhost 30000
```

### 학습 개념
- `nc(netcat)` : **TCP/UDP 연결을 간단하게 테스트**하는 네트워크 도구
- 특정 포트에 데이터를 보내거나 받을 때 사용
- CTF 네트워크 문제의 기본 도구

### 획득 비밀번호
```
8xCjnmgoKbGLhHFAZlGE5Tmu4M2tKJQo
```

---

## LV15 → LV16

### 목표
SSL/TLS 암호화 통신으로 port 30001에 비밀번호 전송

### SSH 접속
```bash
ssh bandit15@bandit.labs.overthewire.org -p 2220
# 비밀번호: 8xCjnmgoKbGLhHFAZlGE5Tmu4M2tKJQo
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ echo 8xCjnmgoKbGLhHFAZlGE5Tmu4M2tKJQo | openssl s_client -connect localhost:30001 -ign_eof
```

### 학습 개념
- `openssl s_client` : **SSL/TLS 암호화 채널**로 서버에 연결하는 도구
- `nc`는 평문 통신, `openssl s_client`는 **암호화 통신**
- HTTPS가 동작하는 원리와 같은 방식

### 획득 비밀번호
```
kSkvUpMQ7lBYyCM4GBPvCvT1BfWRy0Dx
```

---

## LV16 → LV17

### 목표
31000~32000 포트 중 SSL을 사용하는 포트 찾기 → 비밀번호 전송 → RSA 개인키 획득

### SSH 접속
```bash
ssh bandit16@bandit.labs.overthewire.org -p 2220
# 비밀번호: kSkvUpMQ7lBYyCM4GBPvCvT1BfWRy0Dx
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ nmap localhost -p 31000-32000          # 열린 포트 스캔
# → 31790 포트가 정답

yejun@yejunhc:/mnt/c/windows/system32$ echo kSkvUpMQ7lBYyCM4GBPvCvT1BfWRy0Dx | openssl s_client -connect localhost:31790 -ign_eof
# RSA PRIVATE KEY 출력됨

yejun@yejunhc:/mnt/c/windows/system32$ mkdir /tmp/mykey
yejun@yejunhc:/mnt/c/windows/system32$ cat > /tmp/mykey/sshkey.pem            # RSA키 붙여넣기 후 Ctrl+D
yejun@yejunhc:/mnt/c/windows/system32$ chmod 600 /tmp/mykey/sshkey.pem
yejun@yejunhc:/mnt/c/windows/system32$ ssh -i /tmp/mykey/sshkey.pem bandit17@localhost -p 2220
```

### 학습 개념
- `nmap` : **포트 스캐너** → 열린 포트 및 서비스 확인
- RSA 개인키 저장 후 `chmod 600` 필수 (권한이 너무 넓으면 SSH가 키 사용 거부)
- **포트 스캔 → 올바른 포트 파악 → SSH 키 획득** 흐름

### 획득 비밀번호
```
EReVavePLFHtFlFsjn3hyzMlvSuSAcRD
```

---

## LV17 → LV18

### 목표
`passwords.new`와 `passwords.old` 두 파일의 차이점에서 비밀번호 찾기

### SSH 접속
```bash
ssh bandit17@bandit.labs.overthewire.org -p 2220
# 비밀번호: EReVavePLFHtFlFsjn3hyzMlvSuSAcRD
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ ls
yejun@yejunhc:/mnt/c/windows/system32$ diff passwords.new passwords.old
# '<' 로 표시된 줄 = passwords.new에만 있는 줄 = 비밀번호
```

### 학습 개념
- `diff` : **두 파일의 차이**를 출력
- `<` : 첫 번째 파일(passwords.new)에만 있는 줄
- `>` : 두 번째 파일(passwords.old)에만 있는 줄

### 획득 비밀번호
```
x2gLTTjFwMOhQ8oWNbMN362QKxfRqGlO
```

---

## LV18 → LV19

### 목표
`.bashrc`가 로그인 시 자동으로 로그아웃시킴 → SSH에서 직접 명령 실행

### SSH 접속 (일반 로그인 불가)
```bash
ssh bandit18@bandit.labs.overthewire.org -p 2220 'cat readme'
# 비밀번호: x2gLTTjFwMOhQ8oWNbMN362QKxfRqGlO
```

### 학습 개념
- `.bashrc` : bash 로그인 시 **자동으로 실행되는 설정 파일**
- 여기에 `exit`가 심어져 있으면 로그인 즉시 로그아웃
- SSH 명령어를 인자로 뒤에 붙이면 **쉘을 열지 않고 해당 명령만 실행**
- `.bashrc` 우회뿐 아니라 자동화에도 자주 쓰이는 패턴

### 획득 비밀번호
```
cGWpMaKXVwDUNgPAVJbWYuGHVn9zl3j8
```

---

## LV19 → LV20

### 목표
setuid 바이너리(`bandit20-do`)를 이용해 bandit20 권한으로 명령 실행

### SSH 접속
```bash
ssh bandit19@bandit.labs.overthewire.org -p 2220
# 비밀번호: cGWpMaKXVwDUNgPAVJbWYuGHVn9zl3j8
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ ls -la
# -rwsr-x--- bandit20-do  (s = setuid 비트)
yejun@yejunhc:/mnt/c/windows/system32$ ./bandit20-do id
yejun@yejunhc:/mnt/c/windows/system32$ ./bandit20-do cat /etc/bandit_pass/bandit20
```

### 학습 개념
- **setuid 비트(s)** : 해당 파일을 실행할 때 **파일 소유자의 권한**으로 동작
- `ls -la`에서 권한에 `s`가 표시되면 setuid 설정된 것
- 실제 Pwnable/권한 상승 문제에서 핵심 개념

### 획득 비밀번호
```
0qXahG8ZjOVMN9Ghs7iOWsCfZyXOUbYO
```

---

## LV20 → LV21

### 목표
`suconnect` 바이너리: 지정한 포트에서 현재 레벨 비밀번호를 받으면 다음 레벨 비밀번호 전송

### SSH 접속
```bash
ssh bandit20@bandit.labs.overthewire.org -p 2220
# 비밀번호: 0qXahG8ZjOVMN9Ghs7iOWsCfZyXOUbYO
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ echo 0qXahG8ZjOVMN9Ghs7iOWsCfZyXOUbYO | nc -l -p 5555 &
yejun@yejunhc:/mnt/c/windows/system32$ ./suconnect 5555
```

### 학습 개념
- `nc -l -p` : **리스너 모드** → 지정 포트에서 연결 대기
- `&` : 명령어를 **백그라운드에서 실행**
- 두 프로세스가 소켓으로 통신하는 구조 이해

### 획득 비밀번호
```
EeoULMCra2q0dSkYj561DX7s1CpBuOBt
```

---

## LV21 → LV22

### 목표
cron이 주기적으로 실행하는 스크립트를 분석하여 비밀번호 획득

### SSH 접속
```bash
ssh bandit21@bandit.labs.overthewire.org -p 2220
# 비밀번호: EeoULMCra2q0dSkYj561DX7s1CpBuOBt
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ ls /etc/cron.d/
yejun@yejunhc:/mnt/c/windows/system32$ cat /etc/cron.d/cronjob_bandit22
yejun@yejunhc:/mnt/c/windows/system32$ cat /usr/bin/cronjob_bandit22.sh
# 스크립트 분석: /tmp/t7O6lds9S0RqQh9aMcz6ShpAoZKF7fgv 에 비밀번호 저장
yejun@yejunhc:/mnt/c/windows/system32$ cat /tmp/t7O6lds9S0RqQh9aMcz6ShpAoZKF7fgv
```

### 학습 개념
- **cron** : 리눅스 예약 작업 스케줄러
- `/etc/cron.d/` : cron 설정 파일 위치
- cron 스크립트를 역추적해 비밀번호가 저장된 파일 경로 파악

### 획득 비밀번호
```
tRae0UfB9v0UzbCdn9cY0gQnds9GF58Q
```

---

## LV22 → LV23

### 목표
cron 스크립트가 username의 md5 해시로 `/tmp` 파일명을 만들어 비밀번호 저장

### SSH 접속
```bash
ssh bandit22@bandit.labs.overthewire.org -p 2220
# 비밀번호: tRae0UfB9v0UzbCdn9cY0gQnds9GF58Q
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ cat /usr/bin/cronjob_bandit23.sh
# 스크립트 분석: mytarget=$(echo I am user $myname | md5sum | cut -d ' ' -f 1)

yejun@yejunhc:/mnt/c/windows/system32$ echo I am user bandit23 | md5sum | cut -d ' ' -f 1
# → 8ca319486bfbbc3663ea0fbe81326349

yejun@yejunhc:/mnt/c/windows/system32$ cat /tmp/8ca319486bfbbc3663ea0fbe81326349
```

### 학습 개념
- `md5sum` : **MD5 해시 함수** → 입력값을 고정 길이 해시로 변환
- `cut -d ' ' -f 1` : 공백으로 구분된 첫 번째 필드만 추출
- 스크립트 로직을 그대로 분석해 파일명을 직접 계산

### 획득 비밀번호
```
0Zf11ioIjMVN551jX3CmStKLYqjk54Ga
```

---

## LV23 → LV24

### 목표
cron이 `/var/spool/bandit24/foo` 디렉토리의 스크립트를 1분마다 실행 후 삭제
→ 내 스크립트를 넣어서 비밀번호 추출

### SSH 접속
```bash
ssh bandit23@bandit.labs.overthewire.org -p 2220
# 비밀번호: 0Zf11ioIjMVN551jX3CmStKLYqjk54Ga
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ cat /usr/bin/cronjob_bandit24.sh       # 동작 확인

yejun@yejunhc:/mnt/c/windows/system32$ mkdir -p /tmp/mydir24
yejun@yejunhc:/mnt/c/windows/system32$ chmod 777 /tmp/mydir24

yejun@yejunhc:/mnt/c/windows/system32$ cat > /var/spool/bandit24/foo/myscript.sh << 'EOF'
#!/bin/bash
cat /etc/bandit_pass/bandit24 > /tmp/mydir24/pass.txt
chmod 644 /tmp/mydir24/pass.txt
EOF

yejun@yejunhc:/mnt/c/windows/system32$ chmod 755 /var/spool/bandit24/foo/myscript.sh

# 약 1분 대기 후
yejun@yejunhc:/mnt/c/windows/system32$ cat /tmp/mydir24/pass.txt
```

### 학습 개념
- cron의 **자동 실행 디렉토리**에 스크립트를 삽입해 높은 권한 프로세스가 실행하도록 유도
- `chmod 777` : 모든 사용자가 읽기/쓰기/실행 가능
- `chmod 755` : 소유자는 모두 가능, 나머지는 읽기/실행만
- `chmod 644` : 소유자 읽기/쓰기, 나머지 읽기만
- 실제 리눅스 **권한 상승(Privilege Escalation)** 기법과 연결

### 획득 비밀번호
```
gb8KRRCsshuZXI0tUuR6ypOFjiZbf3G8
```

---

## LV24 → LV25

### 목표
port 30002에 비밀번호 + 4자리 PIN을 전송
0000~9999 중 올바른 PIN을 브루트포스로 찾기

### SSH 접속
```bash
ssh bandit24@bandit.labs.overthewire.org -p 2220
# 비밀번호: gb8KRRCsshuZXI0tUuR6ypOFjiZbf3G8
```

### 풀이
```bash
yejun@yejunhc:/mnt/c/windows/system32$ for i in $(seq -w 0000 9999); do
    echo "gb8KRRCsshuZXI0tUuR6ypOFjiZbf3G8 $i"
  done | nc localhost 30002 | grep -v Wrong
```

### 학습 개념
- **브루트포스(Brute Force)** : 가능한 모든 경우의 수를 시도하는 방식
- `seq -w 0000 9999` : 0000부터 9999까지 **앞에 0을 붙여** 생성 (`-w` 옵션)
- `grep -v Wrong` : "Wrong"이 포함된 줄 제외 → 성공한 줄만 출력
- 파이프라인(`|`)으로 10000개 조합을 한 번에 전송

### 획득 비밀번호
```
iCi86ttT4KSNe1armKiwbQNmB3YJP3q4
```

---

## 전체 레벨 요약

| 레벨 | 핵심 기술 |
|------|-----------|
| LV0~3 | `ls`, `cat`, 특수문자 파일명, 숨김 파일 |
| LV4~6 | `file`, `find` 조건부 탐색 |
| LV7~9 | `grep`, `sort \| uniq`, `strings` |
| LV10~11 | `base64`, `tr` (ROT13) |
| LV12 | `xxd`, gzip/bzip2/tar 압축 해제 |
| LV13~14 | SSH 키 기반 인증 (`-i`) |
| LV14~16 | `nc`, `openssl s_client` 네트워크 통신 |
| LV16~17 | `nmap` 포트 스캔, `diff` 파일 비교 |
| LV18 | `.bashrc` 우회, SSH 명령 직접 실행 |
| LV19~20 | setuid, `nc -l` 소켓 통신 |
| LV21~23 | cron 스크립트 분석, `md5sum` |
| LV23~24 | cron 자동 실행 악용, 브루트포스 자동화 |
