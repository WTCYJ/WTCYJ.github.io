---
layout: post
title: "[BugBounty] Semgrep으로 워드프레스 플러그인 취약점 스캐너 만들기"
date: 2026-10-06 00:00:00 +0900
category: 개발
author: SeiKa
tags: [Semgrep, 정적분석, taint, 워드프레스, 플러그인, 버그바운티, SAST, Patchstack, 트리아지, 디핑]
excerpt: "wp.org에서 플러그인을 긁어 와 직접 짠 Semgrep 룰로 훑는 스캐너를 만들었다. 정적 스캔으로는 유효한 취약점이 나오지 않았고, 로컬에 워드프레스를 세워 동적으로 옮겨 간 뒤에야 비인증 결함 하나를 찾았다. 스캐너가 주는 건 후보일 뿐 판정은 사람이 한다는 걸, 오탐을 하나씩 걷어 내며 배운 기록이다."
---

> 룰을 돌리면 630건이 빨갛게 뜬다. 그중 진짜는 몇 개일까. 답은 영(0)이었고, 그 영에 도달하기까지가 이 글의 전부다.

버그바운티 과제로 "Semgrep을 이용한 정규표현식 스캐너를 만들고 실제 취약점을 찾아라"를 받았다. 참고 링크로 받은 [영상](https://www.youtube.com/watch?v=RvKLn2ofMAo)이 가리키는 방향은 분명했다. 공개된 플러그인을 대량으로 받아서 패턴 매칭으로 훑는, 흔히 "플러그인 농사"라고 부르는 방식이다. 워드프레스 플러그인 생태계는 수만 개가 공개 저장소에 올라와 있고 소스가 그대로 열려 있으니, 정적 분석기를 들이대기에 이보다 좋은 사냥터는 없어 보인다.

만들고 돌리는 것까지는 하루면 됐다. 문제는 그 다음이었다. 빨갛게 뜬 경고를 한 줄씩 들여다보는 일, 그게 진짜 작업이었다.

---

## 무엇을 만들었나

구조는 단순하다. 공개 저장소에서 플러그인을 받아 압축을 풀고, 직접 짠 룰로 Semgrep을 돌린 다음, 결과를 "누가 이 코드에 도달할 수 있는가" 기준으로 줄 세운다.

<svg class="sgw-fig" viewBox="0 0 760 150" role="img" aria-label="스캐너 파이프라인: wp.org API에서 슬러그를 받아 다운로드와 압축 해제를 거쳐 Semgrep으로 스캔하고 도달성 기준으로 트리아지해 결과를 낸다">
  <style>
    .sgw-fig { font-family: var(--sans); }
    .sgw-box { fill: var(--surface); stroke: var(--rule); stroke-width: 1.5; }
    .sgw-t { fill: var(--ink); font-size: 15px; font-weight: 600; }
    .sgw-s { fill: var(--ink-faint); font-size: 11.5px; font-family: var(--mono); }
    .sgw-arr { stroke: var(--ink-soft); stroke-width: 1.6; fill: none; }
    .sgw-hd { fill: var(--ink-soft); }
  </style>
  <defs>
    <marker id="sgwA" markerWidth="9" markerHeight="9" refX="7" refY="4" orient="auto">
      <path d="M0,0 L8,4 L0,8 z" class="sgw-hd"/>
    </marker>
  </defs>
  <g>
    <rect class="sgw-box" x="8" y="40" width="130" height="62" rx="7"/>
    <text class="sgw-t" x="73" y="66" text-anchor="middle">수집</text>
    <text class="sgw-s" x="73" y="86" text-anchor="middle">wp.org API</text>
    <rect class="sgw-box" x="170" y="40" width="130" height="62" rx="7"/>
    <text class="sgw-t" x="235" y="66" text-anchor="middle">다운로드·해제</text>
    <text class="sgw-s" x="235" y="86" text-anchor="middle">zip → 소스</text>
    <rect class="sgw-box" x="332" y="40" width="130" height="62" rx="7"/>
    <text class="sgw-t" x="397" y="66" text-anchor="middle">Semgrep</text>
    <text class="sgw-s" x="397" y="86" text-anchor="middle">taint + regex</text>
    <rect class="sgw-box" x="494" y="40" width="130" height="62" rx="7"/>
    <text class="sgw-t" x="559" y="62" text-anchor="middle">도달성</text>
    <text class="sgw-s" x="559" y="82" text-anchor="middle">트리아지</text>
    <rect class="sgw-box" x="656" y="40" width="96" height="62" rx="7"/>
    <text class="sgw-t" x="704" y="66" text-anchor="middle">후보</text>
    <text class="sgw-s" x="704" y="86" text-anchor="middle">json·csv</text>
    <line class="sgw-arr" x1="138" y1="71" x2="168" y2="71" marker-end="url(#sgwA)"/>
    <line class="sgw-arr" x1="300" y1="71" x2="330" y2="71" marker-end="url(#sgwA)"/>
    <line class="sgw-arr" x1="462" y1="71" x2="492" y2="71" marker-end="url(#sgwA)"/>
    <line class="sgw-arr" x1="624" y1="71" x2="654" y2="71" marker-end="url(#sgwA)"/>
  </g>
</svg>

코드는 파이썬 한 파일과 룰 YAML 하나, 그리고 트리아지용 보조 스크립트 몇 개다. 외부 의존성 없이 표준 라이브러리로 플러그인을 받고(`urllib`, `zipfile`), Semgrep은 하위 프로세스로 부른다. 받은 압축 파일은 믿을 수 없는 남의 코드이므로 풀기 전에 zip-slip(압축 안에 `../`가 들어가 작업 폴더 바깥으로 파일이 튀어나오는 수법)을 막는 검사를 넣었다. 받은 코드는 오직 Semgrep이 읽기만 할 뿐 실행하지 않는다.

## 엔진을 고르다

사소해 보였지만 첫 벽은 실행 환경이었다. 윈도우에 설치된 Semgrep으로 샘플 PHP 하나를 긁었더니 결과가 0건이었다. 룰이 틀렸나 한참 들여다봤는데, 범인은 "Ran 1 rule on 0 files"였다. 네이티브 윈도우 빌드가 파일을 아예 집어 들지 못하고 있었다. 같은 룰을 WSL의 Semgrep으로 돌리니 멀쩡히 잡혔다.

그래서 파이프라인 전체를 WSL 안에서 돌리기로 했다. 다만 플러그인 소스를 윈도우 파일시스템(`/mnt/c`)에 두고 긁으면 경계를 넘나드는 입출력 때문에 한 배치가 2분 제한을 넘겨 버렸다. 받은 플러그인은 WSL 네이티브 파일시스템에 풀고, 레포와 결과물만 윈도우 쪽에 두니 속도가 제자리를 찾았다.

![룰 셀프 체크. 의도적으로 취약하게 짠 vuln.php에서 룰 열두 개가 모두 발동하고, 방어가 된 safe.php에서는 한 건도 뜨지 않는다](/assets/img/semgrep-wp/01-selfcheck.png)

## 왜 grep이 아니라 taint인가

`$wpdb->query(` 를 grep으로 찾으면 수백 줄이 쏟아진다. 그런데 그 대부분은 안전하다. `prepare()`로 감쌌거나, 정수로 캐스팅했거나, 애초에 사용자 입력이 닿지 않는 쿼리다. 패턴 매칭만으로는 "위험한 함수를 호출한 곳"과 "위험하게 호출한 곳"을 구분하지 못한다.

그래서 룰의 중심을 Semgrep의 [taint 모드](https://semgrep.dev/docs/writing-rules/data-flow/taint-mode)에 뒀다. 소스를 요청 전역변수(`$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE`)로, 싱크를 위험한 API로 두고, 그 사이에 실제 데이터 흐름이 있을 때만 경고한다. 중간에 `prepare()`나 `esc_html()`, 정수 캐스팅 같은 정화 함수를 지나면 흐름이 끊겨 경고가 사라진다.

과제 제목이 "정규표현식 스캐너"였으니 `pattern-regex` 룰도 두 개 넣었다. 하나는 `preg_replace`의 `/e` 수정자(치환 결과를 PHP 코드로 실행해 버리는 고전적 RCE)를, 다른 하나는 `wp_ajax_nopriv_` 등록(비인증으로 열린 AJAX 표면)을 잡는다. 앞의 것은 taint로는 보이지 않는 모양이고, 뒤의 것은 그 자체로 취약점은 아니지만 "누가 도달할 수 있나"를 판단할 때 요긴한 힌트다.

SQL 인젝션, 반사·저장형 XSS, 명령 실행, 코드 실행, 파일 포함, 파일 읽기·쓰기, 객체 주입, SSRF, 오픈 리다이렉트까지 열 몇 개의 룰을 짰다. 소스 목록처럼 여러 룰이 공유하는 부분은 YAML 앵커(`&`/`*`)로 한 곳에서 관리했다. 다만 YAML 앵커로 시퀀스를 "합치는" 건 안 되고 통째로 재사용만 되는 점, 그리고 `header("Location: ...")` 처럼 값에 콜론이 든 패턴은 따옴표로 감싸지 않으면 YAML이 매핑으로 오해해 룰 파일 전체가 죽는 점에서 각각 한 번씩 막혔다.

룰이 쓸 만한지 확인하려고 일부러 취약하게 짠 `vuln.php`와 그걸 정화한 `safe.php`를 두고, 전자에서는 모든 룰이 뜨고 후자에서는 한 건도 안 뜨는지를 검사하는 셀프 체크를 붙였다. 이게 통과해야 룰을 믿고 수백 개에 들이댈 수 있다.

## 첫 스캔, 그리고 오탐의 벽

최근 갱신된 플러그인 예순 개로 첫 스캔을 돌렸다. 경고가 백 건 넘게, 그중 심각도 ERROR가 쉰 건 넘게 떴다. 설치 수가 가장 많은 플러그인부터 위로 올라오게 줄을 세우고, 위에서부터 코드를 열었다.

설치 수가 수백만인 마이그레이션 플러그인의 "코드 실행"들은 전부 플러그인이 미리 정해 둔 콜백을 부르는 디스패처였다. 소셜 공유 플러그인의 SQL 인젝션 경고가 걸린 자리에는 이런 코드가 있었다.

```php
$include = isset($_POST['b2s-re-post-tags-state']) && (int) $_POST['b2s-re-post-tags-state'] === 1;
// ...
$limit = intval($limit);
$where .= (!B2S_PLUGIN_ADMIN) ? (" AND posts.post_author =" . (int) B2S_PLUGIN_BLOG_USER_ID) : '';
$sql = "SELECT ID FROM $wpdb->posts ... WHERE ... " . $where . " LIMIT " . $limit;
$result = $wpdb->get_results($sql);
```

사용자 입력이 쿼리에 닿기는 한다. 그래서 taint가 흐름을 본 것이다. 그런데 닿는 값은 전부 정수 캐스팅을 거쳤고, 개발자는 "No unescaped User input in statement"라는 주석까지 달아 두었다. taint는 데이터가 흐른다는 사실은 알지만, 그 데이터가 `(int)`를 지나며 무해해졌다는 건 모른다. 오탐이다.

그 플러그인의 객체 주입 경고도 비슷했다. `unserialize()`에 들어가는 값이 사용자 입력이 아니라 플러그인이 예전에 직렬화해 DB에 넣어 둔 자기 데이터였다. 열어 본 상위 후보가 하나같이 이런 식이었다. 요즘 플러그인은 `phpcs:ignore` 주석마다 "왜 이게 안전한지"를 적어 둘 만큼 감사받은 코드였다.

![네 피드에서 긁어온 434개 플러그인을 한 번에 스캔. ERROR만 630건이 떴지만, 그 숫자 자체는 아무 의미가 없었다](/assets/img/semgrep-wp/02-scan.png)

## 도달성으로 다시 줄 세우기

오탐을 손으로 거르는 데 지쳐서, 트리아지를 자동화하기로 했다. taint가 "흐름이 있다"까지 말해 준다면, 남은 질문은 "공격자가 그 함수를 실제로 부를 수 있나"다. 그래서 각 경고의 싱크를 감싼 함수를 찾아, 그 함수가 어떻게 세상에 노출되는지로 네 통에 나눴다.

<svg class="sgw-fig" viewBox="0 0 720 196" role="img" aria-label="도달성 네 단계: 비인증, 저권한(논스만 있고 권한 체크 없음), 가드 없음, 권한 게이트됨. 위로 갈수록 공격자가 도달하기 쉽다">
  <style>
    .sgw2-t { fill: var(--ink); font-size: 14px; font-weight: 600; font-family: var(--sans); }
    .sgw2-s { fill: var(--ink-faint); font-size: 12px; font-family: var(--mono); }
    .sgw2-bar { stroke: var(--rule); stroke-width: 1.2; }
    .sgw2-red { fill: var(--red); }
    .sgw2-amber { fill: var(--amber); }
    .sgw2-soft { fill: var(--ink-soft); }
    .sgw2-green { fill: var(--forest); }
    .sgw2-n { fill: var(--surface); font-size: 13px; font-weight: 700; font-family: var(--mono); }
  </style>
  <g>
    <rect class="sgw2-red sgw2-bar" x="8" y="12" width="200" height="34" rx="5" opacity="0.82"/>
    <text class="sgw2-n" x="22" y="34">UNAUTH</text>
    <text class="sgw2-t" x="222" y="28">비인증 훅에 걸림 — 누구나 도달</text>
    <text class="sgw2-s" x="222" y="42">nopriv AJAX · init · template_redirect</text>
    <rect class="sgw2-amber sgw2-bar" x="8" y="58" width="200" height="34" rx="5" opacity="0.82"/>
    <text class="sgw2-n" x="22" y="80">LOWPRIV</text>
    <text class="sgw2-t" x="222" y="74">논스만 있고 권한 체크 없음 — 로그인만 하면</text>
    <text class="sgw2-s" x="222" y="88">nonce ≠ capability</text>
    <rect class="sgw2-soft sgw2-bar" x="8" y="104" width="200" height="34" rx="5" opacity="0.82"/>
    <text class="sgw2-n" x="22" y="126">NOGUARD</text>
    <text class="sgw2-t" x="222" y="120">가드가 안 보임 — 손으로 확인 필요</text>
    <rect class="sgw2-green sgw2-bar" x="8" y="150" width="200" height="34" rx="5" opacity="0.82"/>
    <text class="sgw2-n" x="22" y="172">GUARDED</text>
    <text class="sgw2-t" x="222" y="166">권한 게이트 있음 — 관리자만</text>
    <text class="sgw2-s" x="222" y="180">current_user_can(...)</text>
  </g>
</svg>

여기서 중요한 구분이 하나 있다. 논스(nonce)는 "이 요청이 우리 사이트에서 나왔다"를 증명할 뿐, "이 사용자가 그럴 권한이 있다"를 증명하지 않는다. `check_ajax_referer`만 있고 `current_user_can`이 없는 AJAX 핸들러는, 구독자 등급으로 가입만 하면 누구나 부를 수 있다. 실제로 [Patchstack](https://patchstack.com)에 올라오는 유효 제보의 상당수가 이 "논스는 있는데 권한 체크가 빠진" 저권한 버그다. 그래서 이 통을 따로 뒀다.

통을 나눠 놓으니 비인증으로 열린 ERROR가 금세 좁혀졌다. 한 폼 플러그인의 비인증 AJAX 핸들러에 코드 실행 경고가 둘이나 걸려 있었다. RCE라면 대박이다. 열어 봤다.

```php
if ( is_callable( $this->tags[$tag]['validation'] ) ) {
    $result = call_user_func( $this->tags[$tag]['validation'], $tagOptions, $v, $messages );
}
```

부르는 함수가 사용자 입력이 아니라 `$this->tags`라는, 플러그인이 등록해 둔 핸들러 표에서 나온다. `$tag`는 폼 정의에서 뽑히고, 호출되는 콜백은 언제나 그 표 안의 값이다. 사용자가 함수 이름을 고를 수 없으니 임의 코드 실행이 아니다. 이 "배열 키로 화이트리스트에서 꺼내 부르기" 모양은 이후에도 지겹도록 다시 만났다. taint는 키가 사용자 손에 있는 걸 보고 흐름이라 판단하지만, 꺼내지는 값은 개발자가 미리 박아 둔 것이다.

![도달성 트리아지. 비인증 ERROR는 금세 한 줌으로 줄지만, 하나씩 열어 보면 전부 오탐이었다](/assets/img/semgrep-wp/03-triage.png)

## 더 키워도 숫자만 커졌다

예순 개로 안 나오면 더 많이 보면 되지 않을까. 네 피드(인기·신규·갱신·고평점)에서 사백 개 넘게, 다시 신규만 육백 개를 받아 돌렸다. ERROR는 수백 건으로 불었지만, 비인증 ERROR와 "방어가 안 보이는" SQL 인젝션·파일 쓰기만 추려 손으로 확인하는 결론은 늘 같았다.

가장 그럴듯해 보였던 한 건은 폼 플러그인의 관리 목록 테이블이었다. `ORDER BY` 절에 `$_GET['orderby']`가 `html_escape()`만 거친 채 들어가고 있었다.

```php
$orderby = !empty($_GET['orderby']) ? $this->html_escape($_GET['orderby']) : 'ASC';
$query .= ' ORDER BY '.$orderby.' '.$order;
$totalitems = $wpdb->query($query);
```

`html_escape`는 `htmlspecialchars`다. 꺾쇠와 따옴표를 HTML 실체로 바꿀 뿐, SQL에는 아무 효력이 없다. `ORDER BY`에는 따옴표가 필요 없으니 공백도 괄호도 쉼표도 그대로 통과한다. 진짜 SQL 인젝션처럼 보였다. 그런데 이 리스트 테이블 클래스는 플러그인 어디에서도 생성되지 않았다. `new`로 인스턴스화하는 곳도, `prepare_items()`를 부르는 곳도 없는 죽은 코드였다. 도달하지 못하는 싱크는 취약점이 아니다.

나머지도 비슷하게 하나씩 떨어져 나갔다. 어떤 "파일 쓰기"는 `php://memory`나 `php://output` 스트림이라 디스크에 닿지 않았고, 어떤 "SSRF"는 목적지 호스트가 플러그인에 박힌 고정 URL이라 공격자가 돌릴 수 없었으며, 어떤 오픈 리다이렉트는 `wp_safe_redirect`(같은 호스트만 허용하는 안전판)를 쓰거나 서버가 저장해 둔 값으로만 이동했다. 저권한 통에 떨어진 SQL 인젝션들조차 식별자까지 `%i`로 바인딩하는 최신 `prepare()` 문법을 쓰고 있었다.

## 접근을 바꾸다 — 디핑

랜덤 스캔으로는 안 된다는 게 분명해졌다. 쉬운 버그는 이미 Wordfence와 Patchstack의 상시 스캔이 올라온 지 며칠 안에 걷어 간다. 그래서 방향을 틀었다. 무작위로 긁는 대신, 최근에 보안 패치를 한 플러그인을 골라 그 패치가 완전한지를 보기로 했다. 패치가 지적받은 한 곳만 고치고 같은 모양의 형제 호출을 놓쳤다면, 거기가 아직 열린 구멍이다.

검색에 기대지 않고 타깃을 골랐다. 이미 받아 둔 플러그인들의 `readme.txt` 변경 이력에서 "security", "XSS", "sanitize" 같은 단어가 최근 항목에 보이는 것들을 뽑으면, 그게 곧 "취약한 버전이 아직 저장소에 남아 있는" 디핑 후보다. 그다음 취약 버전과 패치 버전을 나란히 받아 보안과 관련된 변경만 추렸다.

한 이미지 교체 플러그인이 "표시 이름을 통한 저장형 XSS"를 고친 걸 찾았다. 패치는 깔끔했다.

![보안 패치 디핑. 이스케이프가 빠졌던 자리에 esc_html이 들어갔고, 패치본에 남은 echo를 전수로 확인했지만 형제 버그는 없었다](/assets/img/semgrep-wp/04-diff.png)

패치본에서 이스케이프 없이 출력하는 다른 자리를 전부 찾아봤지만, 남은 것들은 첨부 파일의 URL이나 이미지 크기 문자열처럼 사용자가 건드리기 어려운 값뿐이었다. 완전한 패치였다. 니치한 플러그인이면 허술하지 않을까 싶어 "설정 초기화를 아무 로그인 사용자나 부를 수 있던" 문제를 고친 다른 플러그인도 봤다. 패치는 지적받은 핸들러만이 아니라 그 플러그인의 AJAX 핸들러 전부에 논스와 권한 체크를, 심지어 글 단위 권한(`current_user_can('edit_post', $id)`)까지 달아 두었다. 형제 버그를 노렸는데, 개발자가 이미 한 번에 쓸어 담은 뒤였다.

## 싱크 없는 구멍 — 접근제어

taint 룰은 위험한 싱크가 있어야 경고한다. 그런데 워드프레스에서 가장 흔한 유효 제보는 싱크가 아니라 "권한 확인이 빠진 상태 변경"이다. 파일을 지우거나 옵션을 바꾸는 코드 자체는 위험 함수가 아니어서 taint에는 안 걸리지만, 그걸 아무나 부를 수 있으면 취약점이다. 그래서 플러그인의 모든 AJAX·admin-post 핸들러를 뽑아 각각 논스와 권한을 확인하는지 표로 만드는 감사기를 따로 짰다. 논스만 있고 권한 체크가 없으면 구독자 등급으로 도달하고, 비인증 훅에 걸려 있으면 로그인조차 필요 없다.

받아 둔 플러그인 전부에 돌리니 "권한 확인 없이 상태를 바꾸는" 핸들러가 수백 건 플래그됐다. 위에서부터 열었다. 비인증 파일 업로드가 여럿 걸렸는데, 하나는 `finfo`로 실제 MIME을 확인하고 이미지 세 종만 허용했고, 다른 하나는 `wp_check_filetype_and_ext`와 `wp_handle_upload`를 거쳤다. 웹셸은 못 올린다. 비인증 백업 복원처럼 섬뜩한 이름도 열어 봤지만, 복원 세션마다 발급되는 비밀 키를 맞춰야만 동작했다.

![접근제어 감사기. 논스도 권한도 없는 비인증 상태 변경이 여럿 플래그됐지만, 열어 보면 저마다 표준 함수 바깥의 방어가 있었다](/assets/img/semgrep-wp/05-audit.png)

가장 그럴듯했던 건 비인증으로 페이월을 여는 플러그인이었다. 논스도 권한도 없이 이메일과 코드만 받아 접근 쿠키를 내주고, 코드가 네 자리 숫자라 무차별 대입이 바로 떠올랐다.

```php
function veo_pa_login_is_locked( $email ) {
    if ( $email !== '' && veo_pa_bucket_count( 'veo_pa_fe_' . md5( $email ) ) >= 5 ) {
        return true;
    }
    return veo_pa_bucket_count( 'veo_pa_fi_' . md5( veo_pa_client_ip() ) ) >= 20;
}
```

그런데 실패를 이메일당 다섯 번, IP당 스무 번으로 묶고 15분 잠갔다. IP는 `REMOTE_ADDR`로 잡으니 헤더로 위조할 수 없고, 이메일 없이 쓰는 여덟 자리 레거시 코드는 난수 영숫자였다. 개발자는 "여덟 자리는 IP 제한만 걸린다"는 주석까지 달아 두었다. 또 막혔다.

내 감사기가 이것들을 플래그한 이유는 하나였다. 권한 확인을 `current_user_can`이 아니라 자체 토큰 검증이나 실패 횟수 제한, 파일 타입 화이트리스트로 하고 있었기 때문이다. 도구는 표준 권한 함수를 찾지만, 방어는 그 바깥에도 산다. 플래그는 오탐을 줄여 줄 뿐, 판정은 역시 사람 몫이었다.

## 정적의 끝, 동적의 시작

접근제어까지 뒤졌지만 정적으로는 끝내 손에 잡히는 게 없었다. 열어 본 수십 개가 전부 자체 토큰, 소유권 확인, 실패 횟수 제한으로 막혀 있었다. 정적 분석이 "코드가 무엇을 하는가"는 보여줘도 "실제 요청에 서버가 어떻게 답하는가"는 못 본다는 한계에 부딪힌 것이다.

그래서 로컬에 워드프레스를 세웠다. php 내장 서버와 SQLite로 가볍게 띄우고, 구독자 계정과 의심스러운 플러그인 몇 개를 올린 뒤, 정적으로 애매했던 자리에 실제 요청을 보냈다.

여기서 하나가 걸렸다. 한 예약 플러그인이 "예약 가능한 시간"을 돌려주는 엔드포인트와 "예약을 생성하는" 엔드포인트를 따로 두었는데, 앞의 것은 영업시간만 돌려주지만 뒤의 것은 시간의 형식(`숫자 두 자리 콜론 숫자 두 자리`)만 확인하고 그 범위를 다시 검사하지 않았다. 클라이언트 자바스크립트가 고른 시간을 서버가 그대로 믿은 것이다. 로그인하지 않은 채 공개 페이지에서 토큰을 주운 다음, 영업시간 밖의 새벽 세 시로 예약을 만들어 봤더니 그대로 통과했다. 날짜 상한도 없어 수십 년 뒤로도, 횟수 제한도 없어 얼마든지 만들 수 있었다.

정적으로 두 엔드포인트의 검증이 다르다는 건 읽을 수 있었지만, "서버가 정말 그걸 막지 않는지"는 실제로 요청을 보내 본 뒤에야 확신이 섰다. 이 건은 지금 책임 있는 공개 절차를 밟고 있다. 벤더와 Patchstack에 먼저 알리고, 패치가 나오면 플러그인 이름과 재현 과정을 이 글에 더한다.

## 남은 것

정적 스캔만으로는 유효한 취약점이 나오지 않았고, 동적 테스트로 옮겨 간 뒤에야 하나를 찾았다. 그 과정에서 분명해진 사실이 있다.

2026년의 공개 워드프레스 플러그인 생태계는 무작위 정적 스캔에 꽤 단단하다. 저장소가 Plugin Check를 의무화했고, Patchstack과 Wordfence가 상시로 긁어 가며, 개발자들은 `prepare()`, `esc_*`, 논스와 권한 체크, 화이트리스트 디스패치, 직접 짠 경로 검증기를 일상적으로 쓴다. 지적을 받으면 그 주변을 통째로 점검한다. "Semgrep 돌려서 0-day 줍기"가 통하던 시절은 적어도 인기·신규 피드에서는 지난 것 같다.

그래서 이 과제가 남긴 진짜 교훈은 도구가 아니라 작업의 성격이다. taint 스캐너는 취약점을 찾아 주지 않는다. 사람이 봐야 할 후보의 목록을 줄여 줄 뿐이고, 630건을 0건으로 깎는 트리아지가 실제 일의 전부다. 그 트리아지를 자동화한 도달성 분류와 디핑 선별기가, 돌이켜 보면 이 스캐너에서 가장 쓸모 있는 부분이었다.

다음에 이 사냥터로 돌아온다면 무작위 스캔은 접고, 패치 디핑을 니치한 플러그인으로 넓히거나 같은 개발자가 여러 플러그인에 복사해 둔 코드를 쫓는 쪽으로 갈 것이다. 이긴 적 있는 패턴은 무작위가 아니라 "남이 안 본 틈"과 "불완전한 패치"였으니까.

스캐너와 룰, 트리아지 스크립트는 레포로 정리해 두었다. 책임 있는 공개 원칙상, 뭔가를 찾으면 공개 전에 로컬에 해당 버전을 설치해 재현하고 개발자나 Patchstack·Wordfence에 먼저 알려야 한다. 이번에 찾은 한 건은 바로 그 절차를 밟는 중이고, 재현까지 끝냈으니 패치가 나오는 대로 이 글에 상세를 더한다.

---

<p class="sgw-note" style="color: var(--ink-faint); font-size: 0.9em;">스캐너 저장소: <code>github.com/wtcyj/semgrep-plugin-scanner</code> · 받은 플러그인 소스는 저장소에 포함하지 않는다(남의 코드이자 용량 문제). 룰과 수집기, 트리아지 도구만 들어 있다.</p>
