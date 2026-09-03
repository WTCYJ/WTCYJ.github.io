---
layout: post
title: "[KOI] 그래프 균형 맞추기"
date: 2026-09-03 10:00:00 +0900
category: 개발
author: WTCY
tags: [KOI, 정보올림피아드, 그래프, BFS, 이분그래프, 중앙값, C++, PS, 알고리즘]
excerpt: "간선마다 두 정점 값의 합이 정해진 그래프에서 절댓값 합을 최소로 만드는 문제. 정점 하나를 정하면 나머지가 전부 따라오고, 남는 자유도 하나를 홀수 사이클이 있느냐 없느냐로 갈라 처리한다."
---

> 간선마다 양 끝 정점 값의 합이 못 박혀 있다. 정점 하나를 정하면 나머지가 도미노처럼 전부 결정되고, 남는 것은 그 하나를 어디에 두느냐뿐이다.

정올 4799번, 2021년 KOI 2차 대회 문제다. 언뜻 선형 연립방정식처럼 보이는데 실제로 풀어야 할 미지수는 딱 하나다. 그 하나를 그래프가 강제로 못 박아 버리는 경우와 끝까지 자유롭게 남겨 두는 경우가 갈리고, 자유롭게 남았을 때 최적점을 고르는 방법이 이 문제의 알맹이다.

---

## 1. 문제

$N$개의 정점과 $M$개의 간선으로 이루어진 무방향 단순 연결 그래프가 주어진다. $j$번 간선은 정점 $a_j$와 $b_j$를 잇고 정수 가중치 $c_j$를 가진다.

모든 정점에 정수 가중치 $x_i$를 부여하되, 균형 조건을 지켜야 한다.

$$x_{a_j} + x_{b_j} = c_j \quad (1 \le j \le M)$$

총 비용은 부여한 가중치의 절댓값 합 $\sum_{i=1}^{N} \lvert x_i \rvert$ 이고, 균형을 맞추는 것이 가능한지 판정한 뒤 가능하다면 총 비용이 최소인 배정을 하나 출력한다. 불가능하면 `No`를 출력한다.

제약은 $2 \le N \le 100\,000$, $1 \le M \le 200\,000$, $\lvert c_j \rvert \le 1\,000\,000$ 이다. 자기 자신을 잇는 간선도, 같은 정점 쌍을 두 번 잇는 간선도 없고, 그래프는 연결되어 있다. 시간 제한 2초, 메모리 1024MB.

문제에 실린 예제 그림을 다시 그리면 이렇다.

<figure style="margin: 0 0 1.6rem">
<svg viewBox="0 0 700 300" role="img" aria-label="예제 2의 그래프. 왼쪽은 정점 번호와 간선 가중치, 오른쪽은 총 비용 17을 만드는 정점 가중치">
  <style>
    .gb1-l { stroke: var(--rule-dark); stroke-width: 2; }
    .gb1-c { fill: var(--surface); stroke: var(--ink-soft); stroke-width: 1.7; }
    .gb1-c2 { fill: var(--surface); stroke: var(--forest); stroke-width: 2.3; }
    .gb1-n { fill: var(--ink); font-family: var(--mono); font-size: 15px; font-weight: 500; text-anchor: middle; dominant-baseline: central; }
    .gb1-w { fill: var(--forest); font-family: var(--mono); font-size: 13px; font-weight: 500; text-anchor: middle; }
    .gb1-h { fill: var(--ink-soft); font-family: var(--sans); font-size: 13px; text-anchor: middle; }
    .gb1-d { stroke: var(--rule); stroke-width: 1; stroke-dasharray: 5 5; }
  </style>
  <text class="gb1-h" x="170" y="26">정점 번호와 간선 가중치</text>
  <text class="gb1-h" x="520" y="26">비용이 최소인 정점 가중치</text>
  <line class="gb1-d" x1="345" y1="45" x2="345" y2="282" />

  <line class="gb1-l" x1="81"  y1="90"  x2="149" y2="90" />
  <line class="gb1-l" x1="191" y1="90"  x2="259" y2="90" />
  <line class="gb1-l" x1="170" y1="111" x2="170" y2="154" />
  <line class="gb1-l" x1="170" y1="196" x2="170" y2="237" />
  <text class="gb1-w" x="115" y="80">5</text>
  <text class="gb1-w" x="225" y="80">3</text>
  <text class="gb1-w" x="192" y="137">-4</text>
  <text class="gb1-w" x="195" y="220">-12</text>
  <circle class="gb1-c" cx="60"  cy="90"  r="21" />
  <circle class="gb1-c" cx="170" cy="90"  r="21" />
  <circle class="gb1-c" cx="280" cy="90"  r="21" />
  <circle class="gb1-c" cx="170" cy="175" r="21" />
  <circle class="gb1-c" cx="170" cy="258" r="21" />
  <text class="gb1-n" x="60"  y="90">1</text>
  <text class="gb1-n" x="170" y="90">3</text>
  <text class="gb1-n" x="280" y="90">5</text>
  <text class="gb1-n" x="170" y="175">2</text>
  <text class="gb1-n" x="170" y="258">4</text>

  <line class="gb1-l" x1="431" y1="90"  x2="499" y2="90" />
  <line class="gb1-l" x1="541" y1="90"  x2="609" y2="90" />
  <line class="gb1-l" x1="520" y1="111" x2="520" y2="154" />
  <line class="gb1-l" x1="520" y1="196" x2="520" y2="237" />
  <text class="gb1-w" x="465" y="80">5</text>
  <text class="gb1-w" x="575" y="80">3</text>
  <text class="gb1-w" x="542" y="137">-4</text>
  <text class="gb1-w" x="545" y="220">-12</text>
  <circle class="gb1-c2" cx="410" cy="90"  r="21" />
  <circle class="gb1-c2" cx="520" cy="90"  r="21" />
  <circle class="gb1-c2" cx="630" cy="90"  r="21" />
  <circle class="gb1-c2" cx="520" cy="175" r="21" />
  <circle class="gb1-c2" cx="520" cy="258" r="21" />
  <text class="gb1-n" x="410" y="90">2</text>
  <text class="gb1-n" x="520" y="90">3</text>
  <text class="gb1-n" x="630" y="90">0</text>
  <text class="gb1-n" x="520" y="175">-7</text>
  <text class="gb1-n" x="520" y="258">-5</text>

  <text class="gb1-h" x="170" y="294">간선 위 숫자는 두 정점 값의 합이어야 한다</text>
  <text class="gb1-h" x="520" y="294">총 비용 2 + 7 + 3 + 5 + 0 = 17</text>
</svg>
</figure>

오른쪽 배정에서 정점 3과 정점 2의 값을 더하면 $3 + (-7) = -4$ 로 그 사이 간선의 가중치와 같다. 나머지 간선도 마찬가지고, 이때 총 비용 17보다 작게 만드는 방법은 없다.

---

## 2. 자유도는 하나뿐

간선 조건 $x_u + x_v = c$ 는 $x_v = c - x_u$ 로 바꿔 쓸 수 있다. 한쪽을 알면 반대쪽이 즉시 정해진다는 뜻이다. 그래프가 연결되어 있으니 정점 1의 값 하나만 잡으면 BFS로 온 그래프를 훑으며 나머지 값이 전부 따라온다.

정점 1에 부여할 값을 $x$ 라 두고 각 정점의 값을 $x$ 에 대한 식으로 적어 보자. BFS 트리를 한 칸 내려갈 때마다 부호가 뒤집히므로 모든 정점의 값은

$$x_v = s_v \cdot x + k_v, \qquad s_v \in \{+1, -1\}$$

꼴이 된다. 시작 정점은 $s = +1$, $k = 0$ 이고, 값이 $s\,x + k$ 인 정점에서 가중치 $c$ 인 간선을 타고 넘어가면 상대 정점은 $c - (s\,x + k) = (-s)\,x + (c - k)$ 가 된다. 부호는 뒤집히고 상수항은 $c$ 에서 빼진다.

예제 2에 그대로 적용하면 다음과 같다.

<figure style="margin: 0 0 1.6rem">
<svg viewBox="0 0 700 300" role="img" aria-label="각 정점의 값을 시작 정점 값 x에 대한 일차식으로 표현한 그림">
  <style>
    .gb2-l { stroke: var(--rule-dark); stroke-width: 2; }
    .gb2-a { fill: var(--surface); stroke: var(--blue); stroke-width: 2.3; }
    .gb2-b { fill: var(--surface); stroke: var(--red); stroke-width: 2.3; }
    .gb2-ta { fill: var(--blue); font-family: var(--mono); font-size: 14px; font-weight: 500; text-anchor: middle; dominant-baseline: central; }
    .gb2-tb { fill: var(--red); font-family: var(--mono); font-size: 14px; font-weight: 500; text-anchor: middle; dominant-baseline: central; }
    .gb2-w { fill: var(--forest); font-family: var(--mono); font-size: 13px; font-weight: 500; text-anchor: middle; }
    .gb2-id { fill: var(--ink-faint); font-family: var(--sans); font-size: 11px; text-anchor: middle; }
    .gb2-h { fill: var(--ink-soft); font-family: var(--sans); font-size: 13px; text-anchor: middle; }
  </style>
  <line class="gb2-l" x1="127" y1="80"  x2="258" y2="80" />
  <line class="gb2-l" x1="342" y1="80"  x2="503" y2="80" />
  <line class="gb2-l" x1="300" y1="102" x2="300" y2="143" />
  <line class="gb2-l" x1="300" y1="187" x2="300" y2="228" />
  <text class="gb2-w" x="192" y="70">5</text>
  <text class="gb2-w" x="422" y="70">3</text>
  <text class="gb2-w" x="324" y="126">-4</text>
  <text class="gb2-w" x="327" y="211">-12</text>

  <ellipse class="gb2-a" cx="85"  cy="80"  rx="42" ry="22" />
  <ellipse class="gb2-b" cx="300" cy="80"  rx="42" ry="22" />
  <ellipse class="gb2-a" cx="545" cy="80"  rx="42" ry="22" />
  <ellipse class="gb2-a" cx="300" cy="165" rx="42" ry="22" />
  <ellipse class="gb2-b" cx="300" cy="250" rx="42" ry="22" />
  <text class="gb2-ta" x="85"  y="80">x</text>
  <text class="gb2-tb" x="300" y="80">-x+5</text>
  <text class="gb2-ta" x="545" y="80">x-2</text>
  <text class="gb2-ta" x="300" y="165">x-9</text>
  <text class="gb2-tb" x="300" y="250">-x-3</text>
  <text class="gb2-id" x="85"  y="44">1번</text>
  <text class="gb2-id" x="300" y="44">3번</text>
  <text class="gb2-id" x="545" y="44">5번</text>
  <text class="gb2-id" x="372" y="169">2번</text>
  <text class="gb2-id" x="372" y="254">4번</text>

  <text class="gb2-h" x="350" y="292">파란 테두리는 x의 계수가 +1, 빨간 테두리는 -1. 간선으로 이어진 두 정점은 반드시 반대 부호가 된다.</text>
</svg>
</figure>

여기까지는 트리 간선만 쓴 이야기다. BFS 트리에 포함되지 않은 간선이 등장하는 순간 이야기가 두 갈래로 갈린다. 그런 간선은 양 끝 정점의 $s$ 값이 같거나 다르거나 둘 중 하나인데, 그 차이가 곧 사이클 길이의 홀짝이다.

부호가 다르다면 $(s\,x + k_u) + (-s\,x + k_v) = k_u + k_v$ 라서 $x$ 가 통째로 사라진다. 이 간선은 $x$ 를 제약하지 못하고, 대신 $k_u + k_v = c$ 인지만 확인하면 된다. 어긋나면 어떤 $x$ 를 넣어도 안 되니 `No`다.

---

## 3. 홀수 사이클은 x를 못 박는다

부호가 같은 경우가 재미있다. $(s\,x + k_u) + (s\,x + k_v) = c$ 이므로 $x$ 항이 살아남는다.

$$2\,s\,x = c - k_u - k_v \quad \Longrightarrow \quad x = \frac{s\,(c - k_u - k_v)}{2}$$

자유도가 사라지고 $x$ 가 한 값으로 못 박힌다. 예제 1의 삼각형이 정확히 이 경우다.

<figure style="margin: 0 0 1.6rem">
<svg viewBox="0 0 620 300" role="img" aria-label="삼각형 그래프에서 부호가 같은 두 정점을 잇는 간선이 x 값을 하나로 고정하는 그림">
  <style>
    .gb3-l { stroke: var(--rule-dark); stroke-width: 2; }
    .gb3-hi { stroke: var(--red); stroke-width: 2.6; stroke-dasharray: 7 5; }
    .gb3-a { fill: var(--surface); stroke: var(--blue); stroke-width: 2.3; }
    .gb3-b { fill: var(--surface); stroke: var(--red); stroke-width: 2.3; }
    .gb3-ta { fill: var(--blue); font-family: var(--mono); font-size: 14px; font-weight: 500; text-anchor: middle; dominant-baseline: central; }
    .gb3-tb { fill: var(--red); font-family: var(--mono); font-size: 14px; font-weight: 500; text-anchor: middle; dominant-baseline: central; }
    .gb3-w { fill: var(--forest); font-family: var(--mono); font-size: 13px; font-weight: 500; text-anchor: middle; }
    .gb3-id { fill: var(--ink-faint); font-family: var(--sans); font-size: 11px; text-anchor: middle; }
    .gb3-h { fill: var(--ink-soft); font-family: var(--sans); font-size: 13px; text-anchor: middle; }
    .gb3-eq { fill: var(--ink); font-family: var(--mono); font-size: 14px; font-weight: 500; text-anchor: middle; }
  </style>
  <line class="gb3-l"  x1="310" y1="70"  x2="170" y2="215" />
  <line class="gb3-l"  x1="310" y1="70"  x2="450" y2="215" />
  <line class="gb3-hi" x1="170" y1="215" x2="450" y2="215" />
  <text class="gb3-w" x="205" y="140">5</text>
  <text class="gb3-w" x="415" y="140">3</text>
  <text class="gb3-w" x="310" y="204">4</text>

  <ellipse class="gb3-a" cx="310" cy="70"  rx="44" ry="22" />
  <ellipse class="gb3-b" cx="170" cy="215" rx="44" ry="22" />
  <ellipse class="gb3-b" cx="450" cy="215" rx="44" ry="22" />
  <text class="gb3-ta" x="310" y="70">x</text>
  <text class="gb3-tb" x="170" y="215">-x+5</text>
  <text class="gb3-tb" x="450" y="215">-x+3</text>
  <text class="gb3-id" x="310" y="36">1번</text>
  <text class="gb3-id" x="100" y="219">2번</text>
  <text class="gb3-id" x="520" y="219">3번</text>

  <text class="gb3-h"  x="310" y="256">점선 간선은 부호가 같은 두 정점을 잇는다</text>
  <text class="gb3-eq" x="310" y="286">(-x+5) + (-x+3) = 4  →  x = 2</text>
</svg>
</figure>

여기서 걸러야 할 것이 하나 더 있다. $c - k_u - k_v$ 가 홀수면 $x$ 가 정수가 아니다. 문제는 정수 가중치를 요구하므로 이때는 `No`다. 세 간선의 가중치가 모두 1인 삼각형이 딱 그 예다. 세 조건을 다 더하면 $2(x_1 + x_2 + x_3) = 3$ 이 되어 좌변은 짝수, 우변은 홀수라 답이 없다.

홀수 사이클이 하나라도 있으면 최소 비용을 고민할 여지 자체가 사라진다. 답이 존재한다면 그 배정이 유일하기 때문이다. 남은 일은 그 유일한 후보가 모든 간선을 실제로 만족하는지 확인하는 것뿐이다.

---

## 4. 이분 그래프면 중앙값

홀수 사이클이 없다면, 즉 그래프가 이분 그래프라면 $x$ 는 끝까지 자유롭다. 이제 총 비용을 $x$ 의 함수로 써 보자. $s_v$ 가 $+1$ 아니면 $-1$ 이므로

$$\lvert x_v \rvert = \lvert s_v x + k_v \rvert = \lvert x + s_v k_v \rvert = \lvert x - p_v \rvert, \qquad p_v = -s_v k_v$$

가 된다. 절댓값 안의 부호를 통째로 뒤집어도 값이 같다는 성질 하나로, 계수가 $-1$ 인 정점까지 전부 "수직선 위의 한 점 $p_v$ 로부터의 거리"로 통일된다. 그러면 총 비용은

$$\sum_{v} \lvert x - p_v \rvert$$

이고, 이것은 수직선 위 $N$개의 점까지 거리 합을 최소로 만드는 지점을 찾는 고전 문제다. 답은 $p$ 들의 중앙값이다. $p$ 가 모두 정수이니 중앙값도 정수라 정수 조건까지 저절로 지켜진다.

예제 2의 $p$ 값을 뽑아 수직선에 올리면 이렇다.

<figure style="margin: 0 0 1.6rem">
<svg viewBox="0 0 700 215" role="img" aria-label="예제 2의 다섯 개 기준점을 수직선에 올리고 중앙값 2를 고른 그림">
  <style>
    .gb4-ax { stroke: var(--ink-soft); stroke-width: 1.6; }
    .gb4-tk { stroke: var(--rule-dark); stroke-width: 1.2; }
    .gb4-pt { fill: var(--forest); }
    .gb4-md { stroke: var(--banana); stroke-width: 2.4; }
    .gb4-v  { fill: var(--ink); font-family: var(--mono); font-size: 13px; font-weight: 500; text-anchor: middle; }
    .gb4-id { fill: var(--ink-faint); font-family: var(--sans); font-size: 11px; text-anchor: middle; }
    .gb4-h  { fill: var(--ink-soft); font-family: var(--sans); font-size: 13px; text-anchor: middle; }
    .gb4-mt { fill: var(--amber); font-family: var(--mono); font-size: 14px; font-weight: 500; text-anchor: middle; }
  </style>
  <line class="gb4-ax" x1="55" y1="120" x2="665" y2="120" />
  <line class="gb4-tk" x1="100" y1="114" x2="100" y2="126" />
  <line class="gb4-tk" x1="180" y1="114" x2="180" y2="126" />
  <line class="gb4-tk" x1="220" y1="114" x2="220" y2="126" />
  <line class="gb4-tk" x1="300" y1="114" x2="300" y2="126" />
  <line class="gb4-tk" x1="380" y1="114" x2="380" y2="126" />
  <line class="gb4-tk" x1="420" y1="114" x2="420" y2="126" />
  <line class="gb4-tk" x1="500" y1="114" x2="500" y2="126" />
  <line class="gb4-tk" x1="540" y1="114" x2="540" y2="126" />
  <line class="gb4-tk" x1="580" y1="114" x2="580" y2="126" />
  <line class="gb4-md" x1="340" y1="62" x2="340" y2="152" />

  <circle class="gb4-pt" cx="140" cy="120" r="6" />
  <circle class="gb4-pt" cx="260" cy="120" r="6" />
  <circle class="gb4-pt" cx="340" cy="120" r="6" />
  <circle class="gb4-pt" cx="460" cy="120" r="6" />
  <circle class="gb4-pt" cx="620" cy="120" r="6" />

  <text class="gb4-id" x="140" y="98">4번</text>
  <text class="gb4-id" x="260" y="98">1번</text>
  <text class="gb4-id" x="340" y="98">5번</text>
  <text class="gb4-id" x="460" y="98">3번</text>
  <text class="gb4-id" x="620" y="98">2번</text>
  <text class="gb4-v" x="140" y="145">-3</text>
  <text class="gb4-v" x="260" y="145">0</text>
  <text class="gb4-v" x="340" y="145">2</text>
  <text class="gb4-v" x="460" y="145">5</text>
  <text class="gb4-v" x="620" y="145">9</text>

  <text class="gb4-mt" x="340" y="52">x = 2</text>
  <text class="gb4-h" x="350" y="180">다섯 점까지의 거리 합 5 + 2 + 0 + 3 + 7 = 17 이 곧 총 비용이다</text>
  <text class="gb4-h" x="350" y="202">중앙값을 벗어나면 어느 쪽으로 움직여도 합이 늘어난다</text>
</svg>
</figure>

$x = 2$ 를 각 정점 식에 넣으면 $[2, -7, 3, -5, 0]$ 이 나온다. 문제 본문이 최적이라고 밝힌 그 배정이다.

---

## 5. 코드

```cpp
#include <iostream>
#include <vector>
#include <queue>
#include <algorithm>
using namespace std;
int N, M;
vector<pair<int, int>> adj[100000];
void calc(long long num) {
  vector<long long> ans(N);
  vector<bool> visit(N, false);
  visit[0] = true; ans[0] = num;
  queue<int> q; q.push(0);
  while(!q.empty()) {
    int here = q.front(); q.pop();
    for(int i=0;i<adj[here].size();++i) {
      int there = adj[here][i].first, cost = adj[here][i].second;
      if(visit[there] && ans[here] + ans[there] != cost) { cout<<"NO\n"; return ; }
      else if(!visit[there]) {
        visit[there] = true;
        ans[there] = cost - ans[here];
        q.push(there);
      }
    }
  }
  cout<<"YES\n";
  for(int i=0;i<N;++i)
    cout<<ans[i]<<" ";
}

bool getNum(long long& ret) {
  vector<pair<int, long long>> visit(N, make_pair(0, 0));
  vector<long long> resA(1, 0);
  visit[0] = make_pair(1, 0);
  queue<int> q; q.push(0);
  while(!q.empty()) {
    int here = q.front(); q.pop();
    int sign = visit[here].first; long long coef = visit[here].second;
    for(int i=0;i<adj[here].size();++i) {
      int there = adj[here][i].first, cost = adj[here][i].second;
      int ts = visit[there].first; long long tc = visit[there].second;
      if(ts == 0) {
        visit[there] = make_pair(-sign, cost - coef);
        q.push(there);
        resA.push_back((cost - coef) * sign);
      } else if(sign == ts) {
        long long res = (sign) * (cost - coef - tc);
        if((res<0?-res:res) % 2) return false;
        ret = res / 2;
        return true;
      } else if(tc + coef != cost) return false;
    }
  }
  sort(resA.begin(), resA.end());
  ret = resA[resA.size() / 2];
  return true;
}
int main() {
  ios::sync_with_stdio(false); cin.tie(0);
  cin>>N>>M;
  for(int i=0;i<M;++i) {
    int a, b, c; cin>>a>>b>>c;
    --a; --b;
    adj[a].push_back(make_pair(b, c));
    adj[b].push_back(make_pair(a, c));
  }
  long long res;
  if(!getNum(res)) cout<<"NO\n";
  else calc(res);
  return 0;
}
```

---

## 6. 코드 뜯어보기

### 6.1 getNum, 정점마다 부호와 상수 한 쌍

`visit[v]`는 방문 표시와 계수를 겸한다. `first`가 $s_v$, `second`가 $k_v$ 이고, `first == 0`이 곧 미방문 표시다. 부호가 $+1$ 아니면 $-1$ 뿐이라 0이 남아돌아서 가능한 절약이다.

```cpp
visit[there] = make_pair(-sign, cost - coef);
```

2절에서 유도한 전이를 그대로 옮긴 줄이다. 부호는 뒤집고 상수항은 간선 가중치에서 빼면 끝이다. BFS 트리를 한 칸 내려갈 때마다 부호가 뒤집히므로, 이후 만나는 간선의 양 끝 부호를 비교하는 것만으로 사이클 길이의 홀짝을 알 수 있다. 이분 판정을 위한 별도의 색칠 배열이 필요 없다.

이미 방문한 정점을 만났을 때 갈리는 두 갈래가 각각 3절과 2절 끝의 이야기다. `sign == ts`면 홀수 사이클이라 $x$ 가 결정되고, 다르면 $x$ 가 소거되어 `tc + coef != cost` 검사만 남는다.

부모로 되돌아가는 간선이 오탐을 일으키지 않을까 싶지만 그렇지 않다. 부모와 자식은 항상 부호가 반대라 두 번째 갈래로 들어가고, 그때 `tc + coef`는 $k_{parent} + (c - k_{parent})$ 라서 언제나 $c$ 와 같다.

### 6.2 resA에 담기는 값

```cpp
resA.push_back((cost - coef) * sign);
```

새로 방문한 정점의 계수는 $s' = -s$, $k' = c - k$ 이므로 4절의 기준점은 $p' = -s'k' = s\,(c-k)$ 다. 위 한 줄이 정확히 그 값이다. 시작 정점 몫인 $p = 0$ 은 `resA(1, 0)` 생성자에서 미리 넣어 두었다.

정렬 후 `resA[resA.size() / 2]`를 고르는데, 원소 수가 짝수일 때는 가운데 두 값 중 큰 쪽이 잡힌다. 거리 합을 최소로 만드는 지점은 가운데 두 값 사이 구간 전체라 어느 쪽 끝을 잡아도 최적이다. 실제로 경로 `1-2-3-4`에 가중치 `4 4 100`을 준 입력을 넣으면 `4 0 4 96`이 나오는데, 작은 쪽 중앙값을 골랐을 때 나오는 `0 4 0 100`과 비용이 104로 같다.

### 6.3 calc, 두 번째 BFS가 필요한 이유

`getNum`이 홀수 사이클을 찾으면 $x$ 를 계산하고 그 자리에서 반환한다. 나머지 간선은 쳐다보지도 않는다. 검증이 끝나지 않았는데 값을 확정해도 되는 이유는 그 뒤를 `calc`가 책임지기 때문이다.

`calc`는 확정된 $x$ 로 값을 실제로 채워 넣으면서 모든 간선을 다시 확인한다. 트리 간선은 구성상 자동으로 만족하고, 나머지 간선은 양쪽이 채워진 뒤 `ans[here] + ans[there] != cost`로 검사된다. 어긋나면 `NO`를 출력하고 빠져나온다. 홀수 사이클이 여럿이라 서로 다른 $x$ 를 요구하는 입력이 여기서 걸린다.

이분 그래프 쪽에서는 `getNum`이 이미 모든 간선을 확인했으므로 `calc`의 검사가 중복이다. 그래도 출력 경로를 한 갈래로 유지하는 값으로는 싼 편이다.

### 6.4 출력 대소문자

문제는 `Yes`와 `No`를 요구하는데 코드는 `YES`와 `NO`를 찍는다. 출력이 대소문자를 구분하지 않는다고 명시되어 있어 문제없다.

---

## 7. 채점 결과와 실측

정올에 제출한 결과는 100점이고 서브태스크 일곱 개가 전부 정답이다. 가장 오래 걸린 것은 추가 제약이 없는 마지막 서브태스크로 126ms에 11.0MB를 썼는데, 제한 2초의 십분의 일도 쓰지 않았다. 이 문제의 평균 런타임 290.1ms에 견주면 절반 아래, 평균 메모리 18.4MB에 견주면 6할쯤이다.

상수가 작은 이유는 단순하다. BFS 두 번과 정렬 한 번이 전부고, $N$과 $M$이 커진다고 새로 만드는 자료구조가 없다. 채점 화면은 글 끝에 붙여 두었다.

글에 싣기 전 로컬 검증은 WSL의 g++ 13.3에서 `-O2`로 했다. 두 예제는 문제에 실린 출력과 문자열까지 똑같이 나왔다.

정확성은 무작위 대조로 확인했다. 정점 12개 이하, 간선 가중치 절댓값 15 이하의 연결 그래프를 만들고, 시작 정점 값을 $-400$ 부터 $400$ 까지 전부 대입해 보는 완전 탐색과 비교했다. 판정이 다르거나, 출력한 배정이 간선 조건을 어기거나, 비용이 완전 탐색의 최솟값보다 크면 실패로 잡도록 했다. 8000개 입력에서 불일치는 없었고 `No` 판정이 나온 입력도 2000개 넘게 섞여 있어 실패 경로까지 함께 훑였다.

손으로 만든 반례도 몇 개 넣어 봤다. 가중치가 모두 1인 삼각형은 홀짝 검사에 걸려 `No`, 가중치가 `0 0 0 1`인 사각형은 $x$ 가 소거된 뒤 상수항이 어긋나 `No`, 삼각형 두 개가 서로 다른 $x$ 를 요구하도록 붙인 그래프는 `calc`의 재검사에서 `No`가 나왔다.

최대 크기 입력의 실행 시간과 메모리는 이렇다.

| 입력 | 크기 | 시간 | 메모리 | 최대 절댓값 |
|---|---|---|---|---|
| 부호가 교대하는 경로 | $N = 100\,000$, 가중치 $\pm 10^6$ | 0.11s | 11MB | $5 \times 10^{10}$ |
| 무작위 연결 그래프 | $N = 100\,000$, $M = 200\,000$ | 0.23s | 13MB | 499992 |
| 별 모양 | $N = 100\,000$, 잎마다 무작위 가중치 | 0.08s | 12MB | 1001231 |

두 번의 BFS가 $O(N + M)$, 중앙값을 위한 정렬이 $O(N \log N)$ 이라 예상대로다.

마지막 열에서 눈여겨볼 값은 첫 줄의 $5 \times 10^{10}$ 이다. 가중치가 $+10^6$ 과 $-10^6$ 을 번갈아 나오는 경로에서는 상수항 $k$ 가 한 칸마다 $10^6$ 씩 누적되어, 정점 10만 개를 지나면 $10^{11}$ 규모까지 자란다. 32비트 정수 한계의 20배가 넘는 값이다.

---

## 8. 구현 리스크

| 항목 | 상태 |
|---|---|
| 오버플로 | 계수와 정점 값 모두 `long long`. 위 실측대로 `int`로는 확실히 넘친다 |
| 홀짝 검사 | `(res<0?-res:res) % 2`로 음수까지 안전하고, 통과한 값만 `res / 2`로 나누므로 절단 문제가 없다 |
| 연결성 가정 | 두 BFS 모두 0번 정점 성분만 훑는다. 연결 그래프 보장에 기대는 부분이라 다른 문제에 옮겨 쓸 때 주의 |
| 배열 크기 | `adj[100000]`이 $N$ 상한과 정확히 같다 |
| 재귀 | 없다. BFS라 정점 10만 개짜리 경로 입력에서도 스택 걱정이 없다 |
| 출력 끝 | 마지막 값 뒤에 공백이 붙고 개행이 없다. 보통 채점기는 무시한다 |

---

## 9. 마치며

$x_v = s_v x + k_v$ 라는 한 줄이 문제 전체를 끌고 간다. 부호를 붙여 두면 이분 판정과 사이클 홀짝 판정이 따로 필요 없어지고, 절댓값 안에서 부호를 뽑아내는 순간 서로 다르게 생긴 $N$개의 항이 전부 같은 수직선 위의 거리로 바뀐다. 남는 것은 중앙값이라는 익숙한 결론이다.

가중 유니온 파인드로 각 정점의 부호와 상수를 들고 다녀도 같은 풀이가 나온다. 사이클을 만나는 시점이 다를 뿐 결국 확인하는 것은 똑같이 부호의 일치 여부와 상수항의 정합성이다. 그래도 이 문제에서는 BFS 쪽이 기준점을 그대로 모을 수 있어 더 편하다.

---

제출 화면은 이렇다.

![정올 4799 제출 결과. 서브태스크 일곱 개가 모두 정답이고 126ms / 11.0MB로 통과했다](/assets/img/koi/koi-graph-balance-verdict.png)
