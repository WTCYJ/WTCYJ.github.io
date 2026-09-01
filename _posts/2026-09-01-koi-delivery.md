---
layout: post
title: "[KOI] 맛집 배달"
date: 2026-09-01 21:00:00 +0900
category: 개발
author: WTCY
tags: [KOI, 정보올림피아드, 트리, DP, 트리DP, C++, PS, 알고리즘]
---

> 서로 겹치지 않는 배달 범위를 골라 선호도 합을 최대로. 트리 위에서 "겹치지 않는 공 집합"의 가중 최대 선택 문제로 떨어진다.

트리 위에 반지름이 제각각인 공을 여러 개 놓고, 서로 겹치지 않게 고르면서 가치 합을 최대로 만드는 문제다. 얼핏 상태가 복잡해 보이는데, 결국 서브트리 하나가 바깥에 노출하는 정보가 **정수 하나**로 접힌다는 게 이 풀이의 전부다. 그 정수 하나를 어떻게 잡고, 형제 서브트리를 어떻게 합치는지가 이야기의 중심이다.

---

## 1. 문제

KOI나라에는 $N$개의 도시가 있고, 도시를 정점, 길을 간선으로 보면 트리가 된다. 맛집은 $M$개다. $i$번 맛집은 $c_i$번 도시에 있고, 배달 가능 거리 $d_i$, 선호도 $g_i$를 가진다. $i$번 맛집이 배달 가능한 도시 집합은

$$R_i = \{\, j : d(c_i, j) \le d_i \,\}$$

이다. 여기서 $d(a,b)$는 두 도시 사이 최단 경로의 길이(거쳐야 하는 최소 길 수)다. 한 도시에 맛집이 없을 수도, 여러 개 있을 수도 있다.

배달 앱 운영자로서, 서비스 중복을 피하려고 맛집 집합 $S$를 고른다. 조건은 **어떤 도시도 $S$의 두 맛집 이상에게 동시에 배달받지 않는다** — 즉 $S$의 서로 다른 두 맛집 $i, j$에 대해 $R_i \cap R_j = \varnothing$. 이 조건을 만족하는 $S$ 중 선호도 합 $\sum_{i \in S} g_i$를 최대로 만든다.

### 1.1 겹침 조건을 거리로 바꾸기

집합 $R_i$를 직접 다룰 필요는 없다. 트리는 두 정점 사이 경로가 유일하므로, 반지름 $d_i$·$d_j$짜리 두 공이 겹치는지는 중심 사이 거리 하나로 판정된다.

```
R_i ∩ R_j ≠ ∅   ⟺   dist(c_i, c_j) ≤ d_i + d_j
따라서 서로소 조건은:  dist(c_i, c_j) ≥ d_i + d_j + 1
```

그러면 문제는 **트리 위 가중 최대 서로소 공 집합**(maximum weight disjoint balls on a tree)으로 정확히 환원된다. 이후로는 코드 표기에 맞춰 반지름을 $r$, 가치를 $c$로 쓴다.

---

## 2. 핵심 관찰 — 상태를 정수 하나로

루트를 잡고 $\text{depth}(x)$를 루트로부터의 거리라 하자. 한 서브트리 안에서는 항상 $\text{dist}(u, x) = \text{depth}(x) - \text{depth}(u)$가 성립한다. 이 단순한 성질이 모든 걸 접는다.

깊이 $d$인 정점 $u$의 서브트리 안에 이미 유효한 선택 $T$가 있다고 하자. 이때 다음 값 하나가 바깥과의 모든 상호작용을 결정한다.

$$h(T) = \min_{i \in T} \bigl(\text{depth}(c_i) - r_i\bigr)$$

왜 이 값 하나로 충분한지 세 경우로 확인한다.

**(a) 바깥 공이 위에서 내려오는 경우.** 중심 $c_j$가 서브트리 밖이면 $c_j \to c_i$ 경로는 반드시 $u$를 지난다. 그래서 $\text{dist}(c_j, c_i) = \text{dist}(c_j, u) + \text{depth}(c_i) - d$이고, 서로소 조건을 정리하면

```
dist(c_j, c_i) ≥ r_j + r_i + 1
⟺ depth(c_i) − r_i ≥ d + (r_j − dist(c_j, u)) + 1
```

우변의 $\rho = r_j - \text{dist}(c_j, u)$는 그 바깥 공이 $u$ 아래로 파고드는 깊이다. 즉 **모든 $i$에 대한 조건이 $h \ge d + \rho + 1$ 하나로 묶인다.** 서브트리 안 개별 맛집을 일일이 알 필요가 없다 — 최솟값 $h$만 있으면 된다.

**(b) $u$에 새 맛집(반지름 $r$)을 놓는 경우.** 위 식에서 $\text{dist} = 0$, $\rho = r$이므로 놓을 수 있는 조건은 $h \ge d + r + 1$, 놓고 난 새 상태는 $\min(d - r,\ h) = d - r$.

**(c) 두 형제 서브트리 $A$, $B$를 $u$ 밑에서 합치는 경우.** $i \in A$, $j \in B$면 경로가 $u$를 지나므로 $\text{dist}(c_i, c_j) = (\text{depth}(c_i) - d) + (\text{depth}(c_j) - d)$이고,

```
(depth(c_i) − r_i) + (depth(c_j) − r_j) ≥ 2d + 1
⟺ h_A + h_B ≥ 2d + 1        (합친 상태 = min(h_A, h_B))
```

호환 조건이 부모 깊이 $d$를 축으로 한 대칭식 $h_A + h_B \ge 2d + 1$로 깔끔하게 떨어진다. 코드의 `inv(h) = 2*d - h + 1`이 바로 이 식이다 — 짝이 만족해야 할 최소 $h$.

### 2.1 같은 $h$의 두 얼굴

| 범위 | 의미 |
|---|---|
| $h \le d$ | $h$를 달성한 공이 $u$를 덮으며 **위로 깊이 $h$까지** 뻗어 있다 (그런 공은 최대 1개 — 둘이면 $u$에서 겹친다) |
| $h > d$ | $u$를 덮는 공이 없고, 서브트리가 **깊이 $h-1$까지 비어 있다** → 바깥 공이 $\rho \le h - d - 1$만큼 내려와도 안전 |

"위로 얼마나 침범했나"와 "아래로 얼마나 비어 있나"는 전혀 다른 정보처럼 보이지만, $\min(\text{depth}(c) - r)$ 이라는 **하나의 식**에서 자동으로 갈라진다. 이 통합이 핵심이다.

---

## 3. DP 설계

```
dp[u] : h ↦ (그 상태를 만족하는 선택 중 최대 가치)
```

$h$가 클수록 바깥에 관대하지만(자유롭지만) 그만큼 자기가 덜 골랐으므로 가치는 작다. 즉 이 함수는 **키가 커지면 값이 작아지는 계단함수**라, 지배당하지 않는 점들만 남긴 **파레토 경계**로 유지하면 된다.

전이는 세 가지다.

| 전이 | 식 | 코드 |
|---|---|---|
| 공집합 기저 | $(d,\ 0)$ | `dp[u].upd(d, 0)` |
| 맛집 선택 | $h' = d - r$, 값 $= c + dp[u][d+r+1]$ | `dp[u].upd(d-ball.r, ball.c + dp[u][d+ball.r+1])` |
| 형제 병합 | $h_A + h_B \ge 2d+1$, $h = \min(h_A, h_B)$ | `merge(d, child, dp[u])` |

병합의 기하학적 그림은 이렇다.

```
       깊이 h  ┄┄┄┄●┄┄┄  ← A쪽 공이 덮는 최상단
                   │  (d−h)
       깊이 d      u          ← 두 자식이 만나는 정점
                 ╱   ╲
              A       B
                   │  (d−h) 만큼 B로도 내려온다
     깊이 2d−h  ┄┄┄●┄┄┄  ← B에서 덮이는 최하단
  ⇒ B는 2d−h+1 = inv(h) 부터 비어 있어야 한다
```

$\text{inv}$는 결국 **부모 깊이 $d$를 축으로 한 거울 반사**다. $A$가 위로 $h$까지 밀고 들어왔으면, $B$는 아래로 그만큼 비워 줘야 둘이 안 겹친다.

---

## 4. 코드

```cpp
#include <cstdio>
#include <vector>
#include <algorithm>
#include <map>
const int N_ = 100005;
struct Ball { int r, c; };
std::vector<Ball> balls[N_ + 3];

struct State : std::map<int, long long> {
    State() { emplace(-1, (long long)1e18); }
    int depth() { return std::max(0, rbegin()->first); }
    void upd(int x, long long v) {
        auto it = lower_bound(x);
        if (it != end() && it->second >= v) return;
        if (it != end() && it->first == x) it->second = v;
        else it = emplace(x, v).first;
        it--;
        while (it->first >= 0) {
            if (it->second > v) break;
            auto pit = std::prev(it);
            erase(it);
            it = pit;
        }
    }
    long long operator[] (int x) {
        return depth() < x ? 0 : lower_bound(x)->second;
    }
};

void merge (int d, State &from, State &to) {
    if (from.depth() > to.depth()) from.swap(to);
    if (from.depth() == to.depth() && from.size() > to.size()) from.swap(to);
    #define inv(h) (2*d - (h) + 1)
    const int from_depth = from.depth();
    for (auto &[h, _] : from) {
        if (h >= inv(from_depth)) break;
        to.upd(h, from[h] + to[inv(h)]);
    }
    for (int h = std::max(inv(from_depth), 0); h <= d; h++) {
        to.upd(h, std::max(from[h] + to[inv(h)], from[inv(h)] + to[h]));
    }
    for (int h = d+1; h <= from_depth; h++) {
        to.upd(h, to[h] + from[h]);
    }
    from.clear();
}

int N, M;
std::vector<int> gph[N_ + 3];
State dp[N_];
State& dfs (int u, int p, int d) {
    for (int v : gph[u]) if (v != p) merge(d, dfs(v, u, d+1), dp[u]);
    dp[u].upd(d, 0);
    for (const Ball &ball : balls[u])
        dp[u].upd(d - ball.r, ball.c + dp[u][d + ball.r + 1]);
    return dp[u];
}
int main() {
    scanf("%d%d", &N, &M);
    for (int i = 0; i < N-1; i++) {
        int u, v; scanf("%d%d", &u, &v);
        gph[u].push_back(v); gph[v].push_back(u);
    }
    for (int j = 0; j < M; j++) {
        int u, r, c; scanf("%d%d%d", &u, &r, &c);
        balls[u].push_back({ r, c });
    }
    printf("%lld\n", dfs(1, -1, N)[0]);
    return 0;
}
```

---

## 5. 코드 뜯어보기

### 5.1 `struct State` — 파레토 계단함수

`std::map<int, long long>`을 상속해서, 키 = $h$, 값 = 그 상태에서의 최대 가치로 쓴다. 핵심 불변식은 **키가 커지면 값이 작아진다**는 것이고, `upd`가 이 불변식을 유지한다.

- `lower_bound(x)`의 값이 이미 $v$ 이상이면, 더 자유로운 상태에 더 큰 값이 이미 있다는 뜻이라 새 점은 **지배당함 → 무시**.
- 삽입한 뒤에는 왼쪽(더 작은 키 = 더 나쁜 상태)으로 가며 값이 $v$ 이하인 항목을 **삭제**한다. 새로 들어온 점이 그것들을 지배하기 때문.

`operator[](x)`는 "상태가 $x$ 이상인 선택 중 최대 가치"다. 값이 감소 함수라 `lower_bound` 한 번이면 끝난다. $x$가 현재 최대 키를 넘으면 `0`을 돌려주는데, 이게 **공집합(가치 0, 무한히 자유로움)** 을 자연스럽게 인코딩한다.

센티넬 `(-1, 1e18)`은 생성자에서 미리 넣어 두는데, 역할이 셋이다. ① 맵이 비어도 `rbegin()`이 안전 ② `lower_bound`가 `end()`를 반환하지 않게 ③ `upd`의 왼쪽 삭제 루프를 `it->first >= 0`에서 멈추게 하는 보초 — 값이 `1e18`이라 절대 삭제되지 않는다.

한 가지 영리한 점은 상속받은 `std::map::operator[]`(삽입형)를 **의도적으로 가린다**는 것이다. 실수로 조회만 했는데 항목이 생겨 버리는 사고를 막는 장치다.

그리고 `upd(d, 0)` — "아무것도 안 고름"을 낮은 값으로 등록해 두는 기저. 이게 없으면 `dp[u][x]`가 센티넬 `1e18`을 흘릴 수 있다. 상태를 실제보다 **작게(더 겸손하게) 신고하는 건 언제나 안전**하다. 자유도를 과장하지만 않으면 되니까.

### 5.2 `merge` — 세 구간으로 나눠 담당

```cpp
if (from.depth() > to.depth()) from.swap(to);                     // ① 얕은 쪽을 from 으로
if (from.depth() == to.depth() && from.size() > to.size()) ...    // ② 동률이면 작은 쪽
```

먼저 얕은(또는 작은) 쪽을 `from`으로 맞춘다 — small-to-large의 밑작업이다. `from_depth = from.depth()`라 할 때 세 루프가 나눠 맡는 구간은 이렇다.

| 루프 | 범위 | 하는 일 | 이유 |
|---|---|---|---|
| 1 | `from`의 키 중 $h < \text{inv}(from\_depth)$ | `to.upd(h, from[h] + to[inv(h)])` | 이 구간은 $\text{inv}(h) > from\_depth$라 **`from`이 자유측을 맡을 수 없다** → 한 방향만 |
| 2 | $h = \max(\text{inv}(from\_depth), 0) \ldots d$ | 두 방향 `max` | 양쪽 다 자유측이 될 수 있는 겹침 창 |
| 3 | $h = d+1 \ldots from\_depth$ | `to[h] + from[h]` | 둘 다 $h > d$면 합이 $\ge 2d+2$라 **조건 자동 충족** → 단순 덧셈 |

$h \le d$ 구간에서는 $h \le \text{inv}(h)$라 병합 결과 $\min(\cdot)$이 항상 $h$가 되어 키가 그대로 맞는다. `to`에 남은 $from\_depth$ 초과 키들은 손대지 않는데, 그건 "`from`에서 아무것도 안 고른 경우"라 그대로 옳다.

첫 자식을 병합할 때 `to`는 센티넬뿐($\text{depth}()=0$)이라 ①의 swap 한 번으로 **$O(1)$ 흡수**되고, 루프 2·3 범위는 공집합이 된다. 끝의 `from.clear()`와 맞물려 **자식 맵을 재활용**하므로, 10만 개 맵이 동시에 메모리에 살아 있지 않다. 메모리 설계상 반드시 필요한 장치다.

### 5.3 `dfs` / `main`

```cpp
for (int v : gph[u]) if (v != p) merge(d, dfs(v, u, d+1), dp[u]);
dp[u].upd(d, 0);
for (const Ball &ball : balls[u])
    dp[u].upd(d - ball.r, ball.c + dp[u][d + ball.r + 1]);
```

**자식 전부 병합 → 기저 등록 → 자기 맛집 처리** 순서다. 맛집 전이가 `dp[u]`를 읽어야 하므로 이 순서가 강제된다.

눈에 띄는 건 루트 깊이를 `0`이 아니라 `N`으로 시작한다는 점이다(`dfs(1, -1, N)`). `d - r`이 음수로 내려가지 않게 하는 좌표 평행이동인데($r \le N \le d$가 보장된다), 덤으로 5.5의 안전성까지 딸려 온다. 정답은 `dp[root][0]` — 제약 없는(가장 자유로운) 상태의 최대값이고, 실제 키가 모두 $\ge 0$이라 `[0]`이 전체 최댓값이 된다.

### 5.4 한 도시에 맛집이 여러 개면?

같은 도시의 두 맛집은 거리 0이라 동시에 고를 수 없는데, 코드엔 별도 처리가 없다. **필요 없어서**다. 먼저 처리된 맛집 1이 만든 상태 키는 $d - r_1$인데, 맛집 2가 자기를 놓으려고 읽는 조건은 $h \ge d + r_2 + 1$이다. $d - r_1 \ge d + r_2 + 1$은 $r \ge 0$에서 성립할 수 없으니, **전이식 자체가 자기 배제를 품고 있다.**

### 5.5 센티넬이 루프 1에 끌려 들어가는 문제

루프 1의 range-for는 키 `-1`(센티넬)부터 순회한다. 그래서 `to.upd(-1, 1e18 + to[2d+2])`가 호출되는데, `to[2d+2]`가 0이면 `to`의 센티넬(`1e18 ≥ v`)에 걸려 **즉시 return하는 무해한 no-op**이다. 그리고 그 값이 0임이 보장된다 — 어떤 상태의 최대 키는 그 서브트리 최대 정점 깊이 $\le d + (N-1)$인데, $d \ge N$이라 $d + N - 1 < 2d + 2$다. 5.3의 깊이 오프셋이 여기서도 안전판이 된다. (오프셋이 없었다면 `--begin()` 같은 UB 경로가 열린다.)

---

## 6. 복잡도

- **루프 2·3**: 길이가 $2(from\_depth - d)$ = 얕은 쪽 자식 서브트리 높이의 2배. 병합할 때마다 $\min(\text{높이})$가 더해지는데, 이 총합은 long-path 논증으로 $O(N)$.
- **루프 1**: 작은 쪽 맵의 낮은 키 구간만 훑는 small-to-large 성격의 항. 창의 상한 $\text{inv}(from\_depth) = 2d - from\_depth + 1$은 서브트리가 깊어질수록 레벨당 2씩 좁아져, 위로 갈수록 급격히 싸진다.
- 항목 삽입·조회는 `std::map`의 로그.

정리하면 **실질 $O((N + M)\log N)$**, 메모리는 살아 있는 맵 총합 $O(N + M)$. (루프 1의 최악 상한은 위 창 축소 논증에 기대는 부분이라, 여기서 엄밀 증명까지는 생략한다.)

이론상 로그 인수만 붙는데, 실측으로도 잘 나왔다. 같은 정답 제출들이 대부분 1초 안팎인데 이 코드는 **266ms로 제출 목록 최상단**이고, 메모리도 30.4MB로 정답 중 가장 적다.

![BOJ 제출 목록(시간 정렬) 상단 — 이 풀이(266ms, 30.4MB, C++20)가 정답 제출 중 가장 빠르다](/assets/img/koi/koi-delivery-rank.png)

---

## 7. 구현 리스크

| 항목 | 상태 |
|---|---|
| 오버플로 | 가치 합은 `long long`, 센티넬 덧셈도 `1e18 + 0`으로 안전 |
| 배열 크기 | `dp[N_]`, `gph/balls[N_+3]` — 정점 $1 \ldots N \le 100000$ |
| 재귀 깊이 | `dfs`가 재귀 — 경로 그래프면 프레임 10만 개. 스택 여유 없는 채점 환경이면 주의 |
| `%lld` | 구버전 MinGW에서 주의(BOJ는 무관) |
| 음수 가치 | $g < 0$이어도 공집합 하한 0 덕에 정상 동작 |

---

## 8. 한 줄 정리

서브트리가 노출하는 정보를 $h = \min(\text{depth}(c) - r)$ 하나로 접고, 형제 간 호환 조건을 부모 깊이 기준 반사 $h_A + h_B \ge 2d + 1$로 쓴 뒤, 각 정점에서 $h \mapsto \text{최대가치}$를 **단조 계단함수(파레토 경계)** 로만 들고 얕은 쪽부터 병합하는 트리 DP.

상태를 정수 하나로 접는 그 관찰 한 줄이 문제 전체를 끌고 간다. 이런 류의 "서브트리가 바깥에 노출하는 최소 정보가 무엇인가"를 묻는 트리 DP는 볼 때마다 배우는 게 있다.
