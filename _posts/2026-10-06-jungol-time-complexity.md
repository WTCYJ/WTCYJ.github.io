---
layout: post
title: "[알고리즘] 정올 문제로 익히는 시간 복잡도 줄이기"
date: 2026-10-06 00:00:00 +0900
category: 개발
author: SeiKa
tags: [시간복잡도, 누적합, 투포인터, 단조스택, LIS, 이분탐색, 펜윅트리, 분할상환분석, 정올, KOI, C++, 알고리즘]
excerpt: "O(N²) 풀이로는 시간 제한을 넘는 정올 문제들을 골라 누적 합, 투 포인터, 단조 스택, 이분 탐색, 펜윅 트리로 복잡도를 줄인다. 문제마다 단순한 풀이와 개선한 풀이를 정올에 직접 제출해 결과를 비교한다."
---

> 같은 답을 내는 두 코드가 있다. 한쪽은 시간 초과로 절반도 못 받고, 다른 쪽은 수십 밀리초 만에 만점을 받는다. 차이는 컴퓨터가 아니라 같은 계산을 몇 번 반복하느냐에서 나온다.

[앞의 글](/posts/ioi-2007-flood/)에서 시간 복잡도의 정의와 계산법을 정리했다. 이번 글은 그 연습편이다. 단순하게 풀면 $O(N^2)$ 이상이 나와 시간 제한을 넘는 정올 문제를 골라, 문제마다 무엇이 반복되는지 찾고 그 반복을 없애서 복잡도를 줄인다.

문제마다 같은 순서로 정리했다. 입력 제한으로 허용 복잡도를 먼저 어림하고, 단순한 풀이의 복잡도를 계산한다. 그다음 개선한 풀이가 왜 더 적은 연산으로 같은 답을 내는지 연산 횟수로 설명하고, 두 풀이를 정올에 실제로 제출한 결과를 나란히 붙였다.

---

## 확인 방법

두 풀이 모두 정올에 C++20으로 제출했다. 결과 화면의 점수, 실행 시간, 메모리가 이 글에서 말하는 정올 수치다. 단순한 풀이는 모두 시간 초과로 일부 점수만 받았고, 개선한 풀이는 모두 100점을 받았다.

정올은 시간 제한을 넘으면 그 테스트를 끊어 버리므로 단순한 풀이가 실제로 얼마나 걸리는지는 알 수 없다. 그래서 로컬에서도 따로 쟀다. WSL의 g++ `-O2`로 빌드하고 문제마다 제한의 최댓값으로, 단순한 풀이에 가장 불리한 모양의 입력을 만들었다. 단순한 풀이가 20초를 넘으면 끊고, 입력을 줄여 잰 시간에 복잡도 비율을 곱해 최대 크기의 시간을 추정했다. 추정값에는 "약"을 붙였다.

제출 전에는 문제에 실린 예제와, 작은 무작위 입력 1,500개씩을 두 풀이끼리 대조해 답이 같은지 확인했다.

---

## 1. 구간의 합 구하기 (1D), 정올 3135

[문제](https://jungol.co.kr/problem/3135)는 길이 $N$인 배열에 대해 "$s$번째부터 $e$번째까지의 합"을 묻는 질의 $Q$개에 답하는 것이다. $N, Q \le 10^6$이고 시간 제한은 2초다.

질의마다 $s$부터 $e$까지 직접 더하면 질의 하나에 최대 $N$번, 전체 $O(NQ)$다. 최악이면 $10^{12}$번이다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    vector<long long> a(n + 1);
    for (int i = 1; i <= n; i++) scanf("%lld", &a[i]);
    int q;
    scanf("%d", &q);
    while (q--) {
        int s, e;
        scanf("%d %d", &s, &e);
        long long t = 0;
        for (int i = s; i <= e; i++) t += a[i];
        printf("%lld\n", t);
    }
}
```

![정올 3135 단순한 풀이 제출 결과. 시간 초과 45점, 2,000ms, 9,344KB](/assets/img/jungol-tc/3135-naive.jpg)

반복되는 일은 겹치는 구간을 매번 처음부터 다시 더하는 것이다. 앞에서부터의 합을 한 번만 구해 두면 된다.

$$P_i = A_1 + A_2 + \cdots + A_i, \qquad P_0 = 0$$

그러면 어떤 구간의 합도 뺄셈 한 번이다.

$$A_s + A_{s+1} + \cdots + A_e = P_e - P_{s-1}$$

$P$를 만드는 데 $O(N)$, 질의마다 $O(1)$이라 전체 $O(N + Q)$다. 합이 최대 $10^6 \times 10^6 = 10^{12}$라 `long long`이 필요하다. 입력과 출력이 각각 수백만 개라 `scanf`와 `printf`도 무시할 수 없어서, 입력은 `fread`로 한 번에 읽고 출력은 문자열에 모았다가 한 번에 쓴다.

```cpp
#include <bits/stdc++.h>
using namespace std;

static char b[1 << 25];
int l, k;
long long r() {
    while (k < l && b[k] != '-' && (b[k] < '0' || b[k] > '9')) k++;
    bool g = b[k] == '-';
    if (g) k++;
    long long x = 0;
    while (k < l && b[k] >= '0' && b[k] <= '9') x = x * 10 + b[k++] - '0';
    return g ? -x : x;
}

int main() {
    l = fread(b, 1, sizeof(b), stdin);
    int n = r();
    vector<long long> p(n + 1, 0);
    for (int i = 1; i <= n; i++) p[i] = p[i - 1] + r();
    int q = r();
    string o;
    o.reserve(q * 14);
    while (q--) {
        int s = r(), e = r();
        o += to_string(p[e] - p[s - 1]);
        o += '\n';
    }
    fwrite(o.data(), 1, o.size(), stdout);
}
```

![정올 3135 개선한 풀이 제출 결과. 정답 100점](/assets/img/jungol-tc/3135-fast.jpg)

정올에서 단순한 풀이는 시간 초과 45점, 누적 합 풀이는 299ms에 100점이었다. 로컬 최대 입력으로는 단순한 풀이가 약 209초, 누적 합 풀이가 37ms였다.

---

## 2. 연속부분합 찾기, 정올 1836

[문제](https://jungol.co.kr/problem/1836)는 배열에서 연속한 구간의 합 중 최댓값을 구하는 것이다. 아무것도 고르지 않는 경우(합 0)도 허용된다. $N \le 10^5$이다.

이 문제는 부분 점수가 복잡도대로 나뉘어 있어서 연습에 특히 좋다. $N \le 10^3$인 38점짜리는 $O(N^2)$로 충분하고, $N \le 10^5$인 51점까지 받으려면 더 빨라야 한다.

시작점을 고정하고 끝점을 늘려 가며 더하면 $O(N^2)$이다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    vector<long long> a(n);
    for (auto& x : a) scanf("%lld", &x);
    long long m = 0;
    for (int i = 0; i < n; i++) {
        long long s = 0;
        for (int j = i; j < n; j++) {
            s += a[j];
            m = max(m, s);
        }
    }
    printf("%lld\n", m);
}
```

![정올 1836 단순한 풀이 제출 결과. 시간 초과 38점, 부분문제 2번만 정답](/assets/img/jungol-tc/1836-naive.jpg)

결과가 정확히 38점이다. $N \le 10^3$인 부분문제만 통과하고 나머지는 시간 초과가 났다. 복잡도가 점수로 그대로 찍힌 셈이다.

$i$번째에서 끝나는 구간의 최대 합을 $c_i$라 하자. $i$번째에서 끝나는 구간은 $i-1$번째에서 끝나는 구간에 $A_i$를 붙이거나, $A_i$부터 새로 시작하거나, 아무것도 고르지 않는 셋 중 하나다. 그래서

$$c_i = \max(0,\; c_{i-1} + A_i)$$

이고, 답은 모든 $c_i$ 중 최댓값이다. 앞의 결과를 그대로 다시 쓰므로 원소마다 상수 번 연산이고 전체 $O(N)$이다. 카데인 알고리즘이라 부르는 방법이다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    long long c = 0, m = 0;
    for (int i = 0; i < n; i++) {
        long long x;
        scanf("%lld", &x);
        c = max(0LL, c + x);
        m = max(m, c);
    }
    printf("%lld\n", m);
}
```

![정올 1836 개선한 풀이 제출 결과. 정답 100점](/assets/img/jungol-tc/1836-fast.jpg)

정올에서 12ms에 100점이었다. 1절의 누적 합으로도 풀린다. 구간 합이 $P_e - P_{s-1}$이니 $e$마다 그 앞의 가장 작은 $P$를 기억해 두면 된다. 두 방법 모두 "앞에서 이미 계산한 값을 버리지 않는다"는 점이 같다.

---

## 3. 두 용액, 정올 2306

[문제](https://jungol.co.kr/problem/2306)는 서로 다른 정수 $N$개 중 두 개를 골라 합이 0에 가장 가까운 쌍을 찾는 것이다. $N \le 10^5$, KOI 2010 2차 중등부 문제다.

모든 쌍을 보면 $N(N-1)/2 \approx 5 \times 10^9$번이다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    vector<long long> a(n);
    for (auto& x : a) scanf("%lld", &x);
    int p = 0, q = 1;
    for (int i = 0; i < n; i++)
        for (int j = i + 1; j < n; j++)
            if (llabs(a[i] + a[j]) < llabs(a[p] + a[q])) p = i, q = j;
    printf("%lld %lld\n", min(a[p], a[q]), max(a[p], a[q]));
}
```

![정올 2306 단순한 풀이 제출 결과. 시간 초과 40점](/assets/img/jungol-tc/2306-naive.jpg)

먼저 정렬한다. 그다음 양 끝에 포인터 $l$, $r$을 두고 합 $a_l + a_r$을 본다.

- 합이 음수면 $l$을 오른쪽으로 옮긴다. $a_l$과 짝지을 수 있는 남은 수는 모두 $a_r$ 이하라서 합이 더 작아지기만 하고 0에서 멀어진다. $a_l$은 더 볼 필요가 없다.
- 합이 양수면 같은 이유로 $r$을 왼쪽으로 옮긴다.
- 0이면 더 좋은 답이 없으니 멈춘다.

한 번 움직일 때마다 후보 하나가 영원히 빠지므로 포인터는 합쳐서 $N-1$번 이하로 움직인다. 정렬 $O(N \log N)$에 훑기 $O(N)$이 더해져 $O(N \log N)$이다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    vector<long long> a(n);
    for (auto& x : a) scanf("%lld", &x);
    sort(a.begin(), a.end());
    int l = 0, r = n - 1, p = 0, q = n - 1;
    while (l < r) {
        long long s = a[l] + a[r];
        if (llabs(s) <= llabs(a[p] + a[q])) p = l, q = r;
        if (s < 0) l++;
        else if (s > 0) r--;
        else break;
    }
    printf("%lld %lld\n", a[p], a[q]);
}
```

![정올 2306 개선한 풀이 제출 결과. 정답 100점](/assets/img/jungol-tc/2306-fast.jpg)

정올에서 19ms에 100점이었다. 비교에 `<=`를 쓴 데는 이유가 있다. 예제 2는 $(-100, 103)$과 $(-2, -1)$의 합이 각각 3과 $-3$으로 0과의 거리가 같은데, 예제 출력은 나중에 만나는 $(-2, -1)$이다. 문제는 아무 답이나 된다고 했지만 예제와 같은 쪽을 고르도록 맞췄다.

---

## 4. 탑, 정올 1809

[문제](https://jungol.co.kr/problem/1809)는 높이가 모두 다른 탑 $N$개가 일렬로 서 있을 때, 각 탑에서 왼쪽으로 쏜 신호를 처음 받는 더 높은 탑의 번호를 구하는 것이다. $N \le 5 \times 10^5$, 메모리 32MB다.

탑마다 왼쪽으로 한 칸씩 보며 자기보다 높은 탑을 찾으면 최악에 $O(N^2)$다. 높이가 계속 커지는 입력이면 매번 맨 앞까지 가야 한다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    vector<int> h(n + 1);
    for (int i = 1; i <= n; i++) scanf("%d", &h[i]);
    for (int i = 1; i <= n; i++) {
        int r = 0;
        for (int j = i - 1; j >= 1; j--) {
            if (h[j] > h[i]) {
                r = j;
                break;
            }
        }
        printf("%d%c", r, i == n ? '\n' : ' ');
    }
}
```

![정올 1809 단순한 풀이 제출 결과. 시간 초과 50점](/assets/img/jungol-tc/1809-naive.jpg)

핵심은 "앞으로 신호를 받을 가능성이 있는 탑"만 남기는 것이다. 새 탑 $i$보다 낮은 탑은 $i$에 가려져 $i$ 오른쪽의 어떤 탑의 신호도 받지 못한다. 그러니 스택에 탑 번호를 쌓되, 새 탑보다 낮은 탑은 꺼내 버린다. 꺼내고 나서 스택 맨 위에 남은 탑이 곧 답이다. 스택 안의 탑은 아래에서 위로 갈수록 낮아지는 순서를 유지하므로 단조 스택이라 부른다.

<figure style="margin: 0 0 1.6rem">
<svg viewBox="0 0 700 360" role="img" aria-label="탑 예제 6 9 5 7 4에서 각 탑의 신호가 왼쪽의 어느 탑에 닿는지와, 탑을 하나씩 처리할 때마다 스택에 남는 탑 번호">
  <style>
    .st-b { fill: var(--surface); stroke: var(--ink-soft); stroke-width: 1.6; }
    .st-n { fill: var(--ink); font-family: var(--mono); font-size: 14px; text-anchor: middle; dominant-baseline: central; }
    .st-i { fill: var(--ink-faint); font-family: var(--sans); font-size: 12px; text-anchor: middle; }
    .st-ar { stroke: var(--amber); stroke-width: 1.8; fill: none; }
    .st-hd { fill: var(--amber); }
    .st-sk { fill: var(--surface); stroke: var(--blue); stroke-width: 1.6; }
    .st-sn { fill: var(--blue); font-family: var(--mono); font-size: 13px; text-anchor: middle; dominant-baseline: central; }
    .st-h { fill: var(--ink-soft); font-family: var(--sans); font-size: 13px; }
    .st-a { fill: var(--amber); font-family: var(--mono); font-size: 13px; text-anchor: middle; }
    .st-gl { stroke: var(--rule-dark); stroke-width: 1.4; }
  </style>
  <defs><marker id="st-head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="st-hd" d="M0 0 L10 5 L0 10 z" /></marker></defs>
  <line class="st-gl" x1="100" y1="200" x2="650" y2="200" />
  <rect class="st-b" x="128" y="104" width="44" height="96" rx="2" />
  <text class="st-n" x="150" y="152">6</text>
  <text class="st-i" x="150" y="218">1번</text>
  <text class="st-a" x="150" y="238">답 0</text>
  <rect class="st-b" x="238" y="56" width="44" height="144" rx="2" />
  <text class="st-n" x="260" y="128">9</text>
  <text class="st-i" x="260" y="218">2번</text>
  <text class="st-a" x="260" y="238">답 0</text>
  <rect class="st-b" x="348" y="120" width="44" height="80" rx="2" />
  <text class="st-n" x="370" y="160">5</text>
  <text class="st-i" x="370" y="218">3번</text>
  <line class="st-ar" x1="346" y1="122" x2="284" y2="122" marker-end="url(#st-head)" />
  <text class="st-a" x="370" y="238">답 2</text>
  <rect class="st-b" x="458" y="88" width="44" height="112" rx="2" />
  <text class="st-n" x="480" y="144">7</text>
  <text class="st-i" x="480" y="218">4번</text>
  <line class="st-ar" x1="456" y1="90" x2="284" y2="90" marker-end="url(#st-head)" />
  <text class="st-a" x="480" y="238">답 2</text>
  <rect class="st-b" x="568" y="136" width="44" height="64" rx="2" />
  <text class="st-n" x="590" y="168">4</text>
  <text class="st-i" x="590" y="218">5번</text>
  <line class="st-ar" x1="566" y1="138" x2="504" y2="138" marker-end="url(#st-head)" />
  <text class="st-a" x="590" y="238">답 4</text>
  <text class="st-h" x="20" y="282">스택</text>
  <rect class="st-sk" x="133" y="314" width="34" height="22" rx="3" />
  <text class="st-sn" x="150" y="325">1</text>
  <rect class="st-sk" x="243" y="314" width="34" height="22" rx="3" />
  <text class="st-sn" x="260" y="325">2</text>
  <rect class="st-sk" x="353" y="314" width="34" height="22" rx="3" />
  <text class="st-sn" x="370" y="325">2</text>
  <rect class="st-sk" x="353" y="288" width="34" height="22" rx="3" />
  <text class="st-sn" x="370" y="299">3</text>
  <rect class="st-sk" x="463" y="314" width="34" height="22" rx="3" />
  <text class="st-sn" x="480" y="325">2</text>
  <rect class="st-sk" x="463" y="288" width="34" height="22" rx="3" />
  <text class="st-sn" x="480" y="299">4</text>
  <rect class="st-sk" x="573" y="314" width="34" height="22" rx="3" />
  <text class="st-sn" x="590" y="325">2</text>
  <rect class="st-sk" x="573" y="288" width="34" height="22" rx="3" />
  <text class="st-sn" x="590" y="299">4</text>
  <rect class="st-sk" x="573" y="262" width="34" height="22" rx="3" />
  <text class="st-sn" x="590" y="273">5</text>
  <text class="st-h" x="20" y="308">(아래가 바닥)</text>
</svg>
</figure>

반복문 안에 `while`이 있어 $O(N^2)$처럼 보이지만 그렇지 않다. 탑 하나는 스택에 한 번 들어가고 많아야 한 번 나온다. 그래서 `while`이 도는 횟수를 프로그램 전체에서 다 더해도 $N$을 넘지 않는다. 앞의 글 6절에서 다룬 분할 상환 분석이 그대로 적용되는 예다. 전체 $O(N)$이다.

```cpp
#include <bits/stdc++.h>
using namespace std;

static char b[1 << 23];
int l, k;
int r() {
    while (k < l && (b[k] < '0' || b[k] > '9')) k++;
    int x = 0;
    while (k < l && b[k] >= '0' && b[k] <= '9') x = x * 10 + b[k++] - '0';
    return x;
}

int main() {
    l = fread(b, 1, sizeof(b), stdin);
    int n = r();
    vector<int> h(n + 1), s;
    s.reserve(n);
    string o;
    o.reserve(n * 7);
    for (int i = 1; i <= n; i++) {
        h[i] = r();
        while (!s.empty() && h[s.back()] < h[i]) s.pop_back();
        o += to_string(s.empty() ? 0 : s.back());
        o += i == n ? '\n' : ' ';
        s.push_back(i);
    }
    fwrite(o.data(), 1, o.size(), stdout);
}
```

![정올 1809 개선한 풀이 제출 결과. 정답 100점](/assets/img/jungol-tc/1809-fast.jpg)

정올에서 10ms, 5.1MB로 100점이었다. 메모리 제한이 32MB라 입력 버퍼와 출력 문자열 크기도 따져 두었다. 단순한 풀이는 처음 제출했을 때 60점, 다시 냈을 때 50점이 나왔다. 시간 제한 언저리에서 통과하던 테스트가 채점마다 갈렸기 때문으로 보인다.

---

## 5. 히스토그램, 정올 1214

[문제](https://jungol.co.kr/problem/1214)는 너비 1인 막대 $n$개로 된 히스토그램 안에 들어가는 가장 큰 직사각형의 넓이를 구하는 것이다. $n \le 10^5$, 높이는 $10^9$까지다.

<figure style="margin: 0 0 1.6rem">
<svg viewBox="0 0 700 280" role="img" aria-label="히스토그램 예제 2 1 4 5 1 3 3에서 가장 큰 직사각형은 세 번째와 네 번째 막대에 걸친 높이 4, 너비 2의 넓이 8">
  <style>
    .hg-b { fill: var(--surface); stroke: var(--ink-soft); stroke-width: 1.6; }
    .hg-m { fill: var(--forest); fill-opacity: .28; stroke: var(--forest); stroke-width: 2.4; }
    .hg-n { fill: var(--ink); font-family: var(--mono); font-size: 14px; text-anchor: middle; }
    .hg-i { fill: var(--ink-faint); font-family: var(--sans); font-size: 12px; text-anchor: middle; }
    .hg-h { fill: var(--forest); font-family: var(--sans); font-size: 13px; }
    .hg-gl { stroke: var(--rule-dark); stroke-width: 1.4; }
  </style>
  <line class="hg-gl" x1="140" y1="220" x2="530" y2="220" />
  <rect class="hg-b" x="160" y="152" width="50" height="68" />
  <text class="hg-n" x="185" y="144">2</text>
  <text class="hg-i" x="185" y="238">1</text>
  <rect class="hg-b" x="210" y="186" width="50" height="34" />
  <text class="hg-n" x="235" y="178">1</text>
  <text class="hg-i" x="235" y="238">2</text>
  <rect class="hg-b" x="260" y="84" width="50" height="136" />
  <text class="hg-n" x="285" y="76">4</text>
  <text class="hg-i" x="285" y="238">3</text>
  <rect class="hg-b" x="310" y="50" width="50" height="170" />
  <text class="hg-n" x="335" y="42">5</text>
  <text class="hg-i" x="335" y="238">4</text>
  <rect class="hg-b" x="360" y="186" width="50" height="34" />
  <text class="hg-n" x="385" y="178">1</text>
  <text class="hg-i" x="385" y="238">5</text>
  <rect class="hg-b" x="410" y="118" width="50" height="102" />
  <text class="hg-n" x="435" y="110">3</text>
  <text class="hg-i" x="435" y="238">6</text>
  <rect class="hg-b" x="460" y="118" width="50" height="102" />
  <text class="hg-n" x="485" y="110">3</text>
  <text class="hg-i" x="485" y="238">7</text>
  <rect class="hg-m" x="260" y="84" width="100" height="136" />
  <text class="hg-h" x="545" y="152">높이 4 × 너비 2 = 8</text>
  <text class="hg-i" x="350" y="266">막대 아래 숫자는 위치, 위 숫자는 높이</text>
</svg>
</figure>

시작 막대를 정하고 오른쪽으로 늘려 가며 최소 높이를 유지하면 모든 구간을 $O(n^2)$에 볼 수 있다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    while (scanf("%d", &n) == 1 && n > 0) {
        vector<long long> h(n);
        for (auto& x : h) scanf("%lld", &x);
        long long m = 0;
        for (int i = 0; i < n; i++) {
            long long t = LLONG_MAX;
            for (int j = i; j < n; j++) {
                t = min(t, h[j]);
                m = max(m, t * (j - i + 1));
            }
        }
        printf("%lld\n", m);
    }
}
```

![정올 1214 단순한 풀이 제출 결과. 시간 초과 72.2점](/assets/img/jungol-tc/1214-naive.jpg)

가장 큰 직사각형은 반드시 어떤 막대 하나의 높이를 그대로 쓴다. 그 막대를 기준으로 양쪽으로, 자기보다 낮은 막대를 만나기 직전까지 넓힐 수 있다. 결국 막대마다 "왼쪽과 오른쪽에서 처음 만나는 더 낮은 막대"를 알면 되고, 이것은 4절 탑 문제와 같은 모양이다.

높이가 증가하는 순서로 스택을 유지하다가, 더 낮은 막대 $i$가 오면 스택에서 꺼내는 막대마다 넓이를 계산한다. 꺼내는 순간 그 막대의 오른쪽 경계는 $i$이고 왼쪽 경계는 스택에서 바로 아래 있던 막대 $l$이다. 넓이는 $t \times (i - l - 1)$이다. 끝에 높이 0짜리 막대를 하나 더 두면 남은 막대도 전부 꺼내진다. 탑 문제와 같은 이유로 $O(n)$이다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    while (scanf("%d", &n) == 1 && n > 0) {
        vector<long long> h(n + 1, 0);
        for (int i = 0; i < n; i++) scanf("%lld", &h[i]);
        vector<int> s;
        long long m = 0;
        for (int i = 0; i <= n; i++) {
            while (!s.empty() && h[s.back()] >= h[i]) {
                long long t = h[s.back()];
                s.pop_back();
                int l = s.empty() ? -1 : s.back();
                m = max(m, t * (i - l - 1));
            }
            s.push_back(i);
        }
        printf("%lld\n", m);
    }
}
```

![정올 1214 개선한 풀이 제출 결과. 정답 100점](/assets/img/jungol-tc/1214-fast.jpg)

정올에서 12ms에 100점이었다. 넓이는 최대 $10^9 \times 10^5 = 10^{14}$라 `long long`이 필요하다.

---

## 6. 최장 증가 부분 수열, 정올 4529

[문제](https://jungol.co.kr/problem/4529)는 수열에서 순서를 지키며 고른 증가 수열 가운데 가장 긴 것의 길이(LIS)를 구하는 것이다. $N \le 5 \times 10^5$이고, 같은 값은 증가로 치지 않는다.

교과서 풀이는 $d_i$를 "$i$번째로 끝나는 LIS의 길이"로 두고 앞의 모든 $j$를 보는 것이다.

$$d_i = 1 + \max_{j < i,\ a_j < a_i} d_j$$

$O(N^2)$이다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    vector<int> a(n), d(n, 1);
    for (auto& x : a) scanf("%d", &x);
    int m = 0;
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < i; j++)
            if (a[j] < a[i]) d[i] = max(d[i], d[j] + 1);
        m = max(m, d[i]);
    }
    printf("%d\n", m);
}
```

![정올 4529 단순한 풀이 제출 결과. 시간 초과 50점](/assets/img/jungol-tc/4529-naive.jpg)

빨라지는 열쇠는 앞의 모든 $j$를 볼 필요가 없다는 관찰이다. 길이가 같은 증가 수열이 여럿이면 마지막 값이 가장 작은 것만 기억하면 된다. 뒤에 붙일 수 있는 수가 가장 많기 때문이다. 그래서 $T_k$를 "길이 $k+1$인 증가 수열들의 마지막 값 중 최솟값"으로 둔다. 코드에서는 배열 `t`다.

$T$는 항상 증가하는 배열이다. 길이 $k+1$인 수열에서 마지막 하나를 빼면 길이 $k$인 수열이 되고, 그 마지막 값은 원래 마지막 값보다 작기 때문이다. 정렬된 배열이니 새 수 $x$가 들어갈 자리는 이분 탐색으로 찾는다. $x$ 이상인 첫 칸을 $x$로 바꾸고, 그런 칸이 없으면 맨 뒤에 붙인다. 원소마다 $O(\log N)$, 전체 $O(N \log N)$이다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    vector<int> t;
    for (int i = 0; i < n; i++) {
        int x;
        scanf("%d", &x);
        auto p = lower_bound(t.begin(), t.end(), x);
        if (p == t.end()) t.push_back(x);
        else *p = x;
    }
    printf("%d\n", (int)t.size());
}
```

![정올 4529 개선한 풀이 제출 결과. 정답 100점](/assets/img/jungol-tc/4529-fast.jpg)

정올에서 85ms에 100점이었다. `lower_bound`를 쓴 것이 "같은 값은 증가가 아니다"를 지키는 부분이다. `upper_bound`를 쓰면 같은 값이 이어지는 것을 허용하게 되어 예제 2의 `2 2 3 3 4`에서 3 대신 5가 나온다. 이 문제 본문은 세그먼트 트리로도 풀어 보라고 권하는데, 값을 좌표 압축한 뒤 "값이 $x$ 미만인 것 중 최대 $d$"를 트리로 구하면 역시 $O(N \log N)$이다.

---

## 7. 전깃줄(중), 정올 1257

[문제](https://jungol.co.kr/problem/1257)는 두 전봇대 사이의 전깃줄 중 최소 몇 개를 없애야 남은 것들이 서로 교차하지 않는지 구하고, 없앨 전깃줄의 A쪽 위치를 오름차순으로 출력하는 것이다. 전깃줄은 $10^5$개 이하, KOI 2007 중등부 문제다.

전깃줄을 A쪽 위치로 정렬하면, 교차하지 않는 전깃줄 집합은 B쪽 위치도 증가하는 집합이다. 그러니 남길 수 있는 최대 개수가 B 위치 수열의 LIS 길이고, 답은 전체에서 그것을 뺀 값이다. 6절과 같은 문제가 모양만 바꿔 나온 셈이다. 다른 점은 무엇을 없앨지까지 출력해야 한다는 것이다. $O(N^2)$ DP로 역추적하면 이렇다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    vector<pair<int, int>> w(n);
    for (auto& [a, b] : w) scanf("%d %d", &a, &b);
    sort(w.begin(), w.end());
    vector<int> d(n, 1), p(n, -1);
    int m = 0;
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < i; j++)
            if (w[j].second < w[i].second && d[j] + 1 > d[i]) d[i] = d[j] + 1, p[i] = j;
        if (d[i] > d[m]) m = i;
    }
    vector<char> c(n, 0);
    for (int i = m; i != -1; i = p[i]) c[i] = 1;
    printf("%d\n", n - d[m]);
    for (int i = 0; i < n; i++)
        if (!c[i]) printf("%d\n", w[i].first);
}
```

![정올 1257 단순한 풀이 제출 결과. 시간 초과 42.9점](/assets/img/jungol-tc/1257-naive.jpg)

개선한 풀이는 뒤에서부터 LIS를 구해 $s_i$, 즉 "$i$번 전깃줄에서 시작하는 가장 긴 증가 수열의 길이"를 원소마다 $O(\log N)$에 얻는다. B 위치에 부호를 바꿔 붙이면 뒤에서부터 보는 증가 수열이 앞에서부터 보는 LIS와 같은 모양이 된다. 그다음 앞에서부터 훑으며 $s_i$가 지금 필요한 길이와 같고 B 위치가 직전에 고른 것보다 큰 전깃줄을 남긴다. 전체 $O(N \log N)$이다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    vector<pair<int, int>> w(n);
    for (auto& [a, b] : w) scanf("%d %d", &a, &b);
    sort(w.begin(), w.end());

    vector<int> s(n), t;
    for (int i = n - 1; i >= 0; i--) {
        int v = -w[i].second;
        int k = lower_bound(t.begin(), t.end(), v) - t.begin();
        s[i] = k + 1;
        if (k == (int)t.size()) t.push_back(v);
        else t[k] = v;
    }

    int m = t.size(), d = m, p = 0;
    vector<char> c(n, 0);
    for (int i = 0; i < n && d > 0; i++)
        if (s[i] == d && w[i].second > p) c[i] = 1, p = w[i].second, d--;

    printf("%d\n", n - m);
    for (int i = 0; i < n; i++)
        if (!c[i]) printf("%d\n", w[i].first);
}
```

![정올 1257 개선한 풀이 제출 결과. 정답 100점](/assets/img/jungol-tc/1257-fast.jpg)

정올에서 38ms에 100점이었다. 처음에는 앞에서부터 LIS를 구하고 뒤에서부터 역추적했다. 없애는 개수는 맞았지만 예제와 다른 조합(1, 2, 3)이 나왔다. 예제는 1, 3, 4를 없앤다. 문제는 답이 여러 개면 아무것이나 된다고 했지만, 채점기가 출력을 글자 그대로 비교할 가능성에 대비해 예제와 같은 조합이 나오도록 "앞에서부터 가능한 한 일찍 고르는" 방식으로 바꿨다.

---

## 8. 구간의 합(PURQ) 1, 정올 3297

[문제](https://jungol.co.kr/problem/3297)는 1절과 같은 구간 합 질의에 값 변경 명령이 섞인 것이다. $N \le 10^6$, 명령 $M \le 3 \times 10^5$이다.

1절의 누적 합은 여기서 통하지 않는다. 값 하나가 바뀌면 그 뒤의 $P$를 전부 고쳐야 해서 변경이 $O(N)$이 된다. 반대로 배열만 두면 변경은 $O(1)$이지만 질의가 $O(N)$이다. 어느 쪽이든 최악에 $O(NM) = 3 \times 10^{11}$이다.

```cpp
#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    scanf("%d", &n);
    vector<long long> a(n + 1);
    for (int i = 1; i <= n; i++) scanf("%lld", &a[i]);
    int m;
    scanf("%d", &m);
    while (m--) {
        int t;
        long long x, y;
        scanf("%d %lld %lld", &t, &x, &y);
        if (t == 1) {
            a[x] = y;
        } else {
            if (x > y) swap(x, y);
            long long s = 0;
            for (long long i = x; i <= y; i++) s += a[i];
            printf("%lld\n", s);
        }
    }
}
```

![정올 3297 단순한 풀이 제출 결과. 시간 초과 30점, 2,000ms](/assets/img/jungol-tc/3297-naive.jpg)

펜윅 트리(이진 인덱스 트리)는 두 연산을 모두 $O(\log N)$으로 맞춘다. $i$의 이진수에서 가장 낮은 1비트를 $\mathrm{low}(i) = i \mathbin{\&} (-i)$라 하면, 칸 $i$에는 다음 구간의 합을 저장한다.

$$F_i = A_{i - \mathrm{low}(i) + 1} + \cdots + A_i$$

앞에서부터 $i$까지의 합은 $i$에서 $\mathrm{low}(i)$를 계속 빼 가며 $F$를 더하면 된다(코드의 `q`). 값을 바꿀 때는 $i$에 $\mathrm{low}(i)$를 계속 더해 가며 그 칸을 포함하는 $F$만 고친다(코드의 `u`). 어느 쪽이든 한 번 움직일 때마다 가장 낮은 1비트가 하나씩 지워지거나 위로 올라가므로 많아야 $\log_2 N + 1$번, $N = 10^6$이면 20번 남짓이다.

처음 배열로 트리를 만들 때도 $N$번 `u`를 부르면 $O(N \log N)$이지만, 칸마다 자기 값을 바로 위 칸 $i + \mathrm{low}(i)$에 한 번씩 넘겨 주면 $O(N)$에 만들 수 있다. 전체 $O(N + M \log N)$이다.

```cpp
#include <bits/stdc++.h>
using namespace std;

static char b[1 << 25];
int l, k;
long long r() {
    while (k < l && b[k] != '-' && (b[k] < '0' || b[k] > '9')) k++;
    bool g = b[k] == '-';
    if (g) k++;
    long long x = 0;
    while (k < l && b[k] >= '0' && b[k] <= '9') x = x * 10 + b[k++] - '0';
    return g ? -x : x;
}

int n;
vector<long long> f, a;

void u(int i, long long d) {
    for (; i <= n; i += i & -i) f[i] += d;
}
long long q(int i) {
    long long s = 0;
    for (; i > 0; i -= i & -i) s += f[i];
    return s;
}

int main() {
    l = fread(b, 1, sizeof(b), stdin);
    n = r();
    a.assign(n + 1, 0);
    f.assign(n + 1, 0);
    for (int i = 1; i <= n; i++) {
        a[i] = r();
        f[i] += a[i];
        int j = i + (i & -i);
        if (j <= n) f[j] += f[i];
    }
    int m = r();
    string o;
    while (m--) {
        int t = r();
        long long x = r(), y = r();
        if (t == 1) {
            u(x, y - a[x]);
            a[x] = y;
        } else {
            if (x > y) swap(x, y);
            o += to_string(q(y) - q(x - 1));
            o += '\n';
        }
    }
    fwrite(o.data(), 1, o.size(), stdout);
}
```

![정올 3297 개선한 풀이 제출 결과. 정답 100점](/assets/img/jungol-tc/3297-fast.jpg)

정올에서 153ms에 100점이었다.

---

## 정리

정올 제출 결과를 한 표에 모았다.

| 문제 | 단순한 풀이 | 정올 결과 | 개선한 풀이 | 정올 결과 | 줄인 방법 |
|---|---|---|---|---|---|
| 3135 구간의 합 | $O(NQ)$ | 시간 초과 45점 | $O(N + Q)$ | 100점, 299ms | 누적 합 |
| 1836 연속부분합 | $O(N^2)$ | 시간 초과 38점 | $O(N)$ | 100점, 12ms | 카데인 알고리즘 |
| 2306 두 용액 | $O(N^2)$ | 시간 초과 40점 | $O(N \log N)$ | 100점, 19ms | 정렬 + 투 포인터 |
| 1809 탑 | $O(N^2)$ | 시간 초과 50점 | $O(N)$ | 100점, 10ms | 단조 스택 |
| 1214 히스토그램 | $O(N^2)$ | 시간 초과 72.2점 | $O(N)$ | 100점, 12ms | 단조 스택 |
| 4529 LIS | $O(N^2)$ | 시간 초과 50점 | $O(N \log N)$ | 100점, 85ms | 이분 탐색 |
| 1257 전깃줄 | $O(N^2)$ | 시간 초과 42.9점 | $O(N \log N)$ | 100점, 38ms | LIS + 역추적 |
| 3297 구간 합 갱신 | $O(NM)$ | 시간 초과 30점 | $O(N + M \log N)$ | 100점, 153ms | 펜윅 트리 |

단순한 풀이가 받은 점수는 대부분 입력이 작은 테스트에서 나왔다. 정올은 시간 제한을 넘는 순간 끊어 버리므로 단순한 풀이가 실제로 얼마나 오래 걸리는지는 로컬에서 따로 쟀다. 최대 입력에서 잰 두 풀이의 시간을 한 그림에 모으면 이렇다.

<figure style="margin: 0 0 1.6rem">
<svg viewBox="0 0 700 462" role="img" aria-label="여덟 문제의 단순한 풀이와 개선한 풀이의 최대 입력 실행 시간 비교. 단순한 풀이는 2초에서 229초, 개선한 풀이는 모두 43ms 이하">
  <style>
    .jb-g { stroke: var(--rule); stroke-width: 1; }
    .jb-lim { stroke: var(--ink-faint); stroke-width: 1.3; stroke-dasharray: 6 5; }
    .jb-tk { fill: var(--ink-soft); font-family: var(--mono); font-size: 12px; text-anchor: middle; }
    .jb-rl { fill: var(--ink); font-family: var(--sans); font-size: 13px; text-anchor: end; dominant-baseline: central; }
    .jb-v { fill: var(--ink-soft); font-family: var(--mono); font-size: 11.5px; dominant-baseline: central; }
    .jb-nv { fill: var(--red); }
    .jb-nve { fill: var(--red); fill-opacity: .35; stroke: var(--red); stroke-width: 1.4; stroke-dasharray: 4 3; }
    .jb-op { fill: var(--blue); }
    .jb-lg { fill: var(--ink-soft); font-family: var(--sans); font-size: 13px; dominant-baseline: central; }
    .jb-nt { fill: var(--ink-faint); font-family: var(--sans); font-size: 12px; text-anchor: middle; }
  </style>
  <line class="jb-g" x1="150.0" y1="66" x2="150.0" y2="392" />
  <text class="jb-tk" x="150.0" y="410">1ms</text>
  <line class="jb-g" x1="235.0" y1="66" x2="235.0" y2="392" />
  <text class="jb-tk" x="235.0" y="410">10ms</text>
  <line class="jb-g" x1="320.0" y1="66" x2="320.0" y2="392" />
  <text class="jb-tk" x="320.0" y="410">100ms</text>
  <line class="jb-g" x1="405.0" y1="66" x2="405.0" y2="392" />
  <text class="jb-tk" x="405.0" y="410">1초</text>
  <line class="jb-g" x1="490.0" y1="66" x2="490.0" y2="392" />
  <text class="jb-tk" x="490.0" y="410">10초</text>
  <line class="jb-g" x1="575.0" y1="66" x2="575.0" y2="392" />
  <text class="jb-tk" x="575.0" y="410">100초</text>
  <line class="jb-g" x1="660.0" y1="66" x2="660.0" y2="392" />
  <text class="jb-tk" x="660.0" y="410">1000초</text>
  <line class="jb-lim" x1="405.0" y1="60" x2="405.0" y2="392" />
  <text class="jb-nt" x="405.0" y="54">시간 제한 1초</text>
  <rect class="jb-nv" x="150" y="14" width="12" height="12" rx="2" /><text class="jb-lg" x="168" y="20">단순한 풀이</text>
  <rect class="jb-nve" x="260" y="14" width="12" height="12" rx="2" /><text class="jb-lg" x="278" y="20">단순한 풀이 (20초 초과, 추정)</text>
  <rect class="jb-op" x="480" y="14" width="12" height="12" rx="2" /><text class="jb-lg" x="498" y="20">개선한 풀이</text>
  <text class="jb-rl" x="140" y="92.0">3135 구간의 합</text>
  <rect class="jb-nve" x="150" y="77.0" width="452.2" height="13" rx="2"><title>3135 구간의 합 단순한 풀이: 209초 (추정)</title></rect>
  <text class="jb-v" x="608.2" y="83.5">약 209초</text>
  <rect class="jb-op" x="150" y="92.0" width="133.6" height="13" rx="2"><title>3135 구간의 합 개선한 풀이: 37.3ms</title></rect>
  <text class="jb-v" x="289.6" y="98.5">37.3ms</text>
  <text class="jb-rl" x="140" y="132.0">1836 연속부분합</text>
  <rect class="jb-nv" x="150" y="117.0" width="297.2" height="13" rx="2"><title>1836 연속부분합 단순한 풀이: 3.1초</title></rect>
  <text class="jb-v" x="453.2" y="123.5">3.1초</text>
  <rect class="jb-op" x="150" y="132.0" width="55.5" height="13" rx="2"><title>1836 연속부분합 개선한 풀이: 4.5ms</title></rect>
  <text class="jb-v" x="211.5" y="138.5">4.5ms</text>
  <text class="jb-rl" x="140" y="172.0">2306 두 용액</text>
  <rect class="jb-nv" x="150" y="157.0" width="308.1" height="13" rx="2"><title>2306 두 용액 단순한 풀이: 4.2초</title></rect>
  <text class="jb-v" x="464.1" y="163.5">4.2초</text>
  <rect class="jb-op" x="150" y="172.0" width="86.4" height="13" rx="2"><title>2306 두 용액 개선한 풀이: 10.4ms</title></rect>
  <text class="jb-v" x="242.4" y="178.5">10.4ms</text>
  <text class="jb-rl" x="140" y="212.0">1809 탑</text>
  <rect class="jb-nve" x="150" y="197.0" width="377.3" height="13" rx="2"><title>1809 탑 단순한 풀이: 27초 (추정)</title></rect>
  <text class="jb-v" x="533.3" y="203.5">약 27초</text>
  <rect class="jb-op" x="150" y="212.0" width="82.7" height="13" rx="2"><title>1809 탑 개선한 풀이: 9.4ms</title></rect>
  <text class="jb-v" x="238.7" y="218.5">9.4ms</text>
  <text class="jb-rl" x="140" y="252.0">1214 히스토그램</text>
  <rect class="jb-nv" x="150" y="237.0" width="287.6" height="13" rx="2"><title>1214 히스토그램 단순한 풀이: 2.4초</title></rect>
  <text class="jb-v" x="443.6" y="243.5">2.4초</text>
  <rect class="jb-op" x="150" y="252.0" width="67.4" height="13" rx="2"><title>1214 히스토그램 개선한 풀이: 6.2ms</title></rect>
  <text class="jb-v" x="223.4" y="258.5">6.2ms</text>
  <text class="jb-rl" x="140" y="292.0">4529 LIS</text>
  <rect class="jb-nve" x="150" y="277.0" width="455.5" height="13" rx="2"><title>4529 LIS 단순한 풀이: 229초 (추정)</title></rect>
  <text class="jb-v" x="611.5" y="283.5">약 229초</text>
  <rect class="jb-op" x="150" y="292.0" width="130.2" height="13" rx="2"><title>4529 LIS 개선한 풀이: 34ms</title></rect>
  <text class="jb-v" x="286.2" y="298.5">34ms</text>
  <text class="jb-rl" x="140" y="332.0">1257 전깃줄</text>
  <rect class="jb-nv" x="150" y="317.0" width="338.7" height="13" rx="2"><title>1257 전깃줄 단순한 풀이: 9.7초</title></rect>
  <text class="jb-v" x="494.7" y="323.5">9.7초</text>
  <rect class="jb-op" x="150" y="332.0" width="106.3" height="13" rx="2"><title>1257 전깃줄 개선한 풀이: 17.8ms</title></rect>
  <text class="jb-v" x="262.3" y="338.5">17.8ms</text>
  <text class="jb-rl" x="140" y="372.0">3297 구간의 합 갱신</text>
  <rect class="jb-nve" x="150" y="357.0" width="384.7" height="13" rx="2"><title>3297 구간의 합 갱신 단순한 풀이: 34초 (추정)</title></rect>
  <text class="jb-v" x="540.7" y="363.5">약 34초</text>
  <rect class="jb-op" x="150" y="372.0" width="138.4" height="13" rx="2"><title>3297 구간의 합 갱신 개선한 풀이: 42.5ms</title></rect>
  <text class="jb-v" x="294.4" y="378.5">42.5ms</text>
  <text class="jb-nt" x="350" y="436">가로축은 로그 눈금이다. 3135와 3297의 실제 제한은 2초, 나머지는 1초</text>
</svg>
</figure>

방법은 다섯 가지지만 줄인 원리는 몇 갈래로 모인다.

이미 계산한 것을 다시 쓰는 경우가 있다. 누적 합과 카데인 알고리즘이 여기 속한다. 겹치는 구간을 매번 처음부터 더하는 대신 앞의 결과에 하나만 더한다.

다시 볼 필요가 없는 후보를 영원히 버리는 경우도 있다. 투 포인터와 단조 스택이 그렇다. 정렬이나 높이 순서 같은 단조성 덕분에 한 번 버린 후보가 다시 답이 될 수 없다는 것이 보장된다. 그래서 반복문이 두 겹이어도 전체 이동 횟수가 $N$에 묶인다.

정렬된 구조 위에서 찾기도 한다. LIS의 $T$ 배열은 늘 정렬되어 있어서 "어디에 넣을지"를 $N$번이 아니라 $\log N$번 만에 찾는다.

마지막은 구간을 $\log N$개 조각으로 나눠 저장하는 방법이다. 펜윅 트리는 변경과 질의 중 한쪽만 싸게 만드는 대신 둘 다 $\log N$으로 맞췄다.

---

## 마치며

여덟 문제 모두 단순한 풀이를 먼저 짜고 그 복잡도를 계산한 다음, 그 풀이에서 같은 일을 되풀이하는 곳을 찾는 데서 개선이 시작됐다. 입력 제한을 보고 목표 복잡도를 정해 두면 어느 정도까지 줄여야 하는지가 분명해진다. $N = 10^5$에 1초면 $O(N^2)$은 안 되고 $O(N \log N)$이면 넉넉하다는 식이다.

채점 결과가 그 판단을 그대로 확인해 줬다. 단순한 풀이는 여덟 문제 모두 시간 초과였고, 1836처럼 부분 점수가 입력 크기로 나뉜 문제에서는 $O(N^2)$이 허용되는 구간의 점수만 정확히 받았다. 로컬에서 재 보면 탑과 LIS의 단순한 풀이는 $N$이 두 배가 될 때 각각 3.9배, 4.1배 느려져 $O(N^2)$이 예측하는 네 배와 거의 같았다.
