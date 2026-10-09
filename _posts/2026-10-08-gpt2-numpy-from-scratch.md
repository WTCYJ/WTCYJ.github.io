---
layout: post
title: "NumPy로 구현한 GPT-2"
date: 2026-10-08 00:30:00 +0900
category: 개발
author: WTCY
tags: [LLM, GPT-2, Transformer, NumPy, Self-attention, BPE, 샘플링, SFT, RLHF, DPO, GRPO, RoPE, MoE]
excerpt: "GPT-2 small을 NumPy 행렬 연산만으로 구현하고 공개 가중치를 올려 Hugging Face와 logits를 비교했다. float32 최대 오차 2.8e-3, float64로 올리면 1.1e-11. 그 위에서 토크나이저, 어텐션 맵, √d_k, causal mask, 잔차 연결, temperature, SFT·DPO·GRPO를 숫자로 확인하고, 2026년에 공개된 모델들의 토크나이저와 config.json을 받아 무엇이 달라졌는지 비교했다."
---

ChatGPT나 Claude에 문장을 넣으면 답이 한 토큰씩 나온다. 그 토큰 하나가 나오기까지 안에서 어떤 계산이 오가는지는 그동안 그림으로만 봤다. 그래서 이번에는 GPT-2 small(파라미터 1억 2,441만 개)을 라이브러리 없이 NumPy로 직접 짜고, OpenAI가 공개한 가중치를 올려 Hugging Face 구현과 같은 숫자가 나오는지 확인했다. 숫자가 맞고 나면 부품을 마음대로 빼거나 바꿔 볼 수 있다. 글의 절반은 그렇게 해 본 실험이다.

GPT-2는 2019년 모델이다. 그래도 지금 공개되는 모델들의 뼈대는 거의 그대로다. 글 뒷부분에서는 2025~2026년에 Hugging Face에 올라온 모델들(gpt-oss, Qwen3.8, DeepSeek-V4.1, K-EXAONE 2.0, Kanana-2 등)의 토크나이저와 `config.json`을 직접 받아, GPT-2와 무엇이 같고 무엇이 바뀌었는지 비교했다.

코드는 역할별로 나눴다. 모델과 토크나이저는 [gpt2_numpy.py](/assets/files/gpt2-numpy/gpt2_numpy.py), Hugging Face·tiktoken과의 비교는 [compare_hf.py](/assets/files/gpt2-numpy/compare_hf.py), GPT-2 실험은 [experiments.py](/assets/files/gpt2-numpy/experiments.py), 최신 모델과의 비교는 [modern.py](/assets/files/gpt2-numpy/modern.py)에 있다. 실행 환경은 Windows 11, Python 3.11, NumPy 2.4.6이고, 비교용으로 transformers 5.19.0, tiktoken 0.14.0, PyTorch 2.14.1(CPU)을 썼다. Hugging Face에서는 `model.safetensors`, `vocab.json`, `merges.txt` 파일만 받았고, 모델 계산과 BPE는 직접 구현했다.

## 전체 구조

먼저 큰 그림부터 보자. 문장은 토큰 ID의 열이 되고, ID 하나하나는 768차원 벡터가 된다. 이 벡터 열이 똑같이 생긴 트랜스포머 블록 12개를 차례로 통과한 뒤, 어휘 50,257개 각각에 매긴 점수(logits)로 바뀐다. 마지막 위치의 점수에서 토큰 하나를 고르면 그게 다음 토큰이다. 그 토큰을 뒤에 붙이고 같은 계산을 처음부터 다시 한다. 생성이란 이 반복이 전부다.

<svg viewBox="0 0 720 330" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GPT-2 순전파 구조. 문장이 BPE 토크나이저를 거쳐 토큰 ID가 되고, 토큰 임베딩과 위치 임베딩을 더한 뒤 블록 12개를 지나 logits가 되며, 샘플링한 토큰을 다시 입력에 붙인다. 아래에는 블록 하나의 내부(LayerNorm, self-attention, 잔차 덧셈, LayerNorm, MLP, 잔차 덧셈)가 펼쳐져 있다.">
<style>
.g2-box{fill:var(--surface);stroke:var(--rule-dark);stroke-width:1.2}
.g2-hl{fill:var(--surface);stroke:var(--blue);stroke-width:1.6}
.g2-t{fill:var(--ink);font-family:var(--sans);font-size:13px;text-anchor:middle}
.g2-s{fill:var(--ink-soft);font-family:var(--mono);font-size:10.5px;text-anchor:middle}
.g2-a{stroke:var(--ink-soft);stroke-width:1.3;fill:none;marker-end:url(#g2-arr)}
.g2-r{stroke:var(--forest);stroke-width:1.5;fill:none;marker-end:url(#g2-arrg)}
.g2-d{stroke:var(--blue);stroke-width:1;fill:none;stroke-dasharray:4 3}
.g2-lab{fill:var(--forest);font-family:var(--sans);font-size:11px;text-anchor:middle}
.g2-lab2{fill:var(--ink-soft);font-family:var(--sans);font-size:11px;text-anchor:middle}
.g2-arrh{fill:var(--ink-soft)}
.g2-arrhg{fill:var(--forest)}
</style>
<defs>
<marker id="g2-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="g2-arrh" d="M0,0 L10,5 L0,10 z"/></marker>
<marker id="g2-arrg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="g2-arrhg" d="M0,0 L10,5 L0,10 z"/></marker>
</defs>
<rect class="g2-box" x="6" y="20" width="104" height="54" rx="6"/><text class="g2-t" x="58" y="43">문장</text><text class="g2-s" x="58" y="61">"The cat sat"</text>
<rect class="g2-box" x="124" y="20" width="110" height="54" rx="6"/><text class="g2-t" x="179" y="43">BPE 토크나이저</text><text class="g2-s" x="179" y="61">[464,3797,3332]</text>
<rect class="g2-box" x="248" y="20" width="110" height="54" rx="6"/><text class="g2-t" x="303" y="43">임베딩</text><text class="g2-s" x="303" y="61">wte[id]+wpe[pos]</text>
<rect class="g2-hl" x="372" y="20" width="104" height="54" rx="6"/><text class="g2-t" x="424" y="43">블록 × 12</text><text class="g2-s" x="424" y="61">(T, 768) 유지</text>
<rect class="g2-box" x="490" y="20" width="110" height="54" rx="6"/><text class="g2-t" x="545" y="43">ln_f · wteᵀ</text><text class="g2-s" x="545" y="61">logits (T,50257)</text>
<rect class="g2-box" x="614" y="20" width="100" height="54" rx="6"/><text class="g2-t" x="664" y="43">샘플링</text><text class="g2-s" x="664" y="61">다음 토큰 1개</text>
<path class="g2-a" d="M110,47 L122,47"/><path class="g2-a" d="M234,47 L246,47"/><path class="g2-a" d="M358,47 L370,47"/><path class="g2-a" d="M476,47 L488,47"/><path class="g2-a" d="M600,47 L612,47"/>
<path class="g2-a" d="M664,74 L664,100 L179,100 L179,77"/>
<text class="g2-lab2" x="420" y="116">고른 토큰을 뒤에 붙여 처음부터 다시 계산</text>
<path class="g2-d" d="M372,74 L20,160"/><path class="g2-d" d="M476,74 L704,160"/>
<rect class="g2-d" x="12" y="160" width="696" height="160" rx="8"/>
<text class="g2-s" x="44" y="232">x</text>
<rect class="g2-box" x="66" y="210" width="84" height="38" rx="5"/><text class="g2-t" x="108" y="234">LayerNorm</text>
<rect class="g2-hl" x="166" y="202" width="136" height="54" rx="5"/><text class="g2-t" x="234" y="224">Self-attention</text><text class="g2-s" x="234" y="242">12 heads, causal</text>
<circle class="g2-box" cx="330" cy="229" r="12"/><text class="g2-t" x="330" y="234">+</text>
<rect class="g2-box" x="364" y="210" width="84" height="38" rx="5"/><text class="g2-t" x="406" y="234">LayerNorm</text>
<rect class="g2-hl" x="464" y="202" width="150" height="54" rx="5"/><text class="g2-t" x="539" y="224">MLP (GELU)</text><text class="g2-s" x="539" y="242">768 → 3072 → 768</text>
<circle class="g2-box" cx="642" cy="229" r="12"/><text class="g2-t" x="642" y="234">+</text>
<path class="g2-a" d="M52,229 L64,229"/><path class="g2-a" d="M150,229 L164,229"/><path class="g2-a" d="M302,229 L316,229"/><path class="g2-a" d="M342,229 L362,229"/><path class="g2-a" d="M448,229 L462,229"/><path class="g2-a" d="M614,229 L628,229"/><path class="g2-a" d="M654,229 L694,229"/>
<path class="g2-r" d="M56,229 L56,184 L330,184 L330,215"/>
<path class="g2-r" d="M352,229 L352,184 L642,184 L642,215"/>
<text class="g2-lab" x="193" y="178">잔차 연결: 입력을 그대로 더한다</text>
<text class="g2-lab" x="497" y="178">잔차 연결</text>
<text class="g2-lab2" x="360" y="300">블록 하나 = x + Attn(LN(x)), 그 결과 + MLP(LN(·)). 모양은 들어올 때와 나갈 때 모두 (T, 768)</text>
</svg>

가중치 이름도 그림과 그대로 맞아떨어진다. `wte`(50257×768)가 토큰 임베딩, `wpe`(1024×768)가 위치 임베딩이다. 블록마다 `ln_1`, `attn.c_attn`(Q·K·V를 한 번에 만드는 768×2304 행렬), `attn.c_proj`, `ln_2`, `mlp.c_fc`, `mlp.c_proj`가 들어 있다. 처음엔 마지막 `ln_f` 뒤에 출력층이 따로 없어서 의아했는데, GPT-2는 입력 임베딩 행렬 `wte`를 전치해서 출력층으로 다시 쓴다. 가중치를 이렇게 공유하면 "이 토큰의 뜻"과 "다음에 이 토큰이 나올 만한 상태"가 768차원 공간에서 같은 방향을 쓰게 된다.

## 토크나이저: 문장이 숫자가 되기까지

GPT-2의 토크나이저는 바이트 단위 BPE다. 문장을 UTF-8 바이트로 바꾼 뒤 바이트 하나를 토큰 하나로 놓고 시작해서, 학습 때 정해 둔 순서대로 붙어 있는 두 조각을 합쳐 나간다. 그 순서가 `merges.txt`에 50,000줄로 적혀 있고, 위에 있는 줄일수록 먼저 학습된 병합이라 우선순위가 높다. 원리는 [Sennrich 등의 BPE 논문](https://arxiv.org/abs/1508.07909)에서 왔다.

병합에 앞서 정규식으로 문장을 대략 단어 단위로 자른다. 영어 축약형(`'s`, `'ll`), 앞에 공백 하나가 붙은 글자 묶음, 숫자 묶음, 기호 묶음, 공백 순으로 잘라서, 단어 앞 공백은 단어 토큰 쪽에 붙는다. vocab에서 `Ġ`로 보이는 글자가 바로 그 공백이다. 바이트 0x20을 그대로 두면 JSON에 저장하기가 곤란해서, GPT-2는 바이트 256개를 눈에 보이는 유니코드 글자 256개에 하나씩 대응시켜 놓았다. `bytes_to_unicode()`가 그 표를 만든다.

병합 부분은 이렇게 짰다.

```python
def bpe(self, word, trace=None):
    parts = list(word)
    while len(parts) > 1:
        pairs = [(self.ranks.get(p, 1e18), i) for i, p in enumerate(zip(parts, parts[1:]))]
        rank, i = min(pairs)
        if rank == 1e18:          # 더 합칠 쌍이 vocab에 없음
            break
        pair = (parts[i], parts[i + 1])
        out, j = [], 0
        while j < len(parts):     # 같은 쌍이 여러 번 있으면 왼쪽부터 전부 합친다
            if j < len(parts) - 1 and (parts[j], parts[j + 1]) == pair:
                out.append(parts[j] + parts[j + 1]); j += 2
            else:
                out.append(parts[j]); j += 1
        parts = out
    return parts
```

문장 중간에 나오는 단어 tokenization을 예로 들어 보자. 앞에 공백이 붙어 있으니 실제 입력은 공백 1바이트와 글자 12바이트, 합쳐서 13바이트다. 병합 과정을 하나씩 찍어 보면 다음과 같다.

| 병합 순위 | 합친 쌍 | 결과 |
|---|---|---|
| 0 | `Ġ` + `t` | `Ġt o k e n i z a t i o n` |
| 5 | `o` + `n` | `Ġt o k e n i z a t i on` |
| 9 | `a` + `t` | `Ġt o k e n i z at i on` |
| 12 | `e` + `n` | `Ġt o k en i z at i on` |
| 28 | `Ġt` + `o` | `Ġto k en i z at i on` |
| 39 | `i` + `on` | `Ġto k en i z at ion` |
| 85 | `at` + `ion` | `Ġto k en i z ation` |
| 272 | `i` + `z` | `Ġto k en iz ation` |
| 1378 | `iz` + `ation` | `Ġto k en ization` |
| 3208 | `k` + `en` | `Ġto ken ization` |
| 10985 | `Ġto` + `ken` | `Ġtoken ization` |

13바이트가 토큰 2개로 줄었다. 영어에서 자주 나오는 조각일수록 순위가 높아 먼저 붙는다.

구현이 맞는지는 tiktoken의 `gpt2` 인코딩, Hugging Face `GPT2TokenizerFast`와 비교해서 확인했다. 영어, 한국어, 일본어, 이모지, 탭과 연속 개행, 파이썬 코드에 `compare_hf.py` 파일 자체(1,514토큰)까지 넣어 봤는데, 세 쪽의 토큰 ID가 모두 같았고 디코딩하면 원문이 그대로 돌아왔다.

### 탐구 질문 1. 한국어는 토큰이 몇 배 나오나

뜻이 같은 영어·한국어 문장 여덟 쌍을 준비했다. "Hello, how are you today?"와 "안녕하세요, 오늘 어떻게 지내세요?", "I would like to order a cup of coffee."와 "커피 한 잔 주문하고 싶어요." 같은 짧은 일상 문장들이다. 이 문장들을 GPT-2부터 2026년 9월에 공개된 토크나이저까지 넣고 토큰 수를 셌다. 최신 모델은 Hugging Face에서 토크나이저 파일만 받았고, 괄호 안 날짜는 Hugging Face 저장소 등록일이다.

![같은 뜻의 영어 8문장과 한국어 8문장의 토큰 수를 토크나이저 10종에서 비교한 가로 막대그래프. 한국어가 영어의 몇 배인지가 GPT-2 4.74배, GPT-4 cl100k 2.24배, gpt-oss o200k 1.29배, Mistral Medium 3.5 1.24배, DeepSeek-V4.1-Flash 1.55배, Qwen3.8-27B 1.18배, HyperCLOVA X SEED Think 1.03배, Kanana-2 0.86배, K-EXAONE 2.0 1.04배, Solar Pro 4 0.85배로 표시돼 있다](/assets/img/gpt2-numpy/10_tokenizers_2026.png)

| 토크나이저 (등록일) | 어휘 수 | 영어 | 한국어 | 한/영 | `안녕하세요` |
|---|---|---|---|---|---|
| GPT-2 (2019) | 50,257 | 66 | 313 | 4.74 | 14 |
| GPT-4 cl100k_base (2023) | 100,277 | 66 | 148 | 2.24 | 5 |
| gpt-oss-20b, o200k (2025-08) | 200,019 | 65 | 84 | 1.29 | 2 |
| Mistral Medium 3.5 (2026-03) | 131,072 | 66 | 82 | 1.24 | 4 |
| DeepSeek-V4.1-Flash (2026-09) | 129,280 | 65 | 101 | 1.55 | 5 |
| Qwen3.8-27B (2026-08) | 248,077 | 66 | 78 | 1.18 | 3 |
| HyperCLOVA X SEED Think 32B (2025-12) | 128,256 | 66 | 68 | 1.03 | 2 |
| K-EXAONE 2.0 (2026-07) | 153,600 | 53 | 55 | 1.04 | 1 |
| Kanana-2 3B (2026-07) | 128,256 | 65 | 56 | 0.86 | 1 |
| Solar Pro 4 (2026-09) | 196,608 | 65 | 55 | 0.85 | 1 |

GPT-2에서 한국어는 영어의 4.74배였다. 그런데 같은 뜻을 담는 데 드는 바이트는 한국어 359바이트, 영어 307바이트로 1.17배밖에 차이 나지 않는다. 한글 한 음절은 UTF-8로 3바이트라 글자당 바이트가 많지만, 같은 뜻을 더 적은 글자(145자 대 307자)로 쓰기 때문에 총량은 비슷해진다. 그러니 4.74배의 대부분은 문자 체계가 아니라 어휘표에서 나온다.

실제로 GPT-2 어휘 50,257개를 전부 뒤져 봤더니, 온전한 한글 음절이 하나라도 들어 있는 토큰이 0개였다. GPT-2는 레딧에서 링크된 웹 문서(WebText)로 BPE를 학습했는데, 그 안에 한국어가 워낙 적어서 한글 바이트 조합이 병합 순위 5만 위 안에 하나도 들지 못했다. 그래서 `안녕하세요`(15바이트)는 이렇게 쪼개진다.

```
ec | 95 | 88 | eb | 85 | 95 | ed 95 | 98 | ec | 84 | b8 | ec | 9a | 94
```

토큰 14개 가운데 병합된 건 `ed 95` 하나뿐이고 나머지는 바이트 하나가 그대로 토큰 하나다. 모델 입장에서는 "안"이라는 글자 하나를 알아보려면 토큰 세 개를 조합해야 하고, 생성할 때도 세 번 연달아 맞게 골라야 한다.

최신 토크나이저로 오면 이야기가 완전히 달라진다. 어휘가 12만~25만 개로 커지고 다국어 데이터로 다시 학습되면서, 한국어 음절과 자주 쓰는 어절이 통째로 토큰이 됐다. 글로벌 모델 가운데서는 Qwen3.8이 1.18배로 가장 낮았고, o200k와 Mistral이 1.2~1.3배였다. DeepSeek-V4.1은 1.55배로 상대적으로 높았다. 더 눈에 띄는 건 국내 모델들이다. Kanana-2와 Solar Pro 4는 한국어가 영어보다 오히려 토큰이 적었고(0.86배, 0.85배), K-EXAONE 2.0과 HyperCLOVA X도 거의 같은 수준이었다. 이 네 모델은 `안녕하세요`를 토큰 한두 개로 처리한다. 한국어 토큰 하나에 담기는 글자 수로 보면 GPT-2가 0.46자, K-EXAONE 2.0과 Solar Pro 4가 2.64자로 다섯 배 넘게 차이 난다.

토큰 수는 곧 API 비용이고 문맥 창에 들어가는 분량이다. GPT-2 시절이었다면 한국어 사용자는 같은 내용을 쓰면서 다섯 배 가까운 값을 치르고 문맥은 그만큼 짧게 썼을 것이다. 지금도 같은 한국어 여덟 문장이 모델에 따라 55토큰에서 101토큰까지 1.8배 차이가 나니, 한국어 서비스를 만든다면 모델을 고를 때 토크나이저도 함께 봐야 한다.

## 임베딩: 토큰 ID가 벡터가 되는 순간

토크나이저가 내놓은 토큰 ID는 그냥 번호다. 앞에 공백이 붙은 Paris가 6342번, dog가 3290번이라는 건 어휘표에 실린 순서일 뿐, 6342가 3290보다 크다는 데에는 아무 뜻이 없다. 이 번호를 그대로 신경망에 넣으면 모델은 숫자의 크기에서 엉뚱한 관계를 읽게 된다. 그래서 토큰마다 숫자 여러 개로 이루어진 벡터를 하나씩 배정하고, 그 벡터를 모델의 입력으로 쓴다. 이 벡터가 임베딩이다. GPT-2 small에서는 토큰 하나가 숫자 768개짜리 벡터가 된다.

이 768개 숫자는 사람이 정한 값이 아니다. 처음에는 무작위로 시작해서, 다음 토큰을 잘 맞히도록 다른 가중치와 함께 학습된다. 그러다 보면 문맥에서 비슷하게 쓰이는 토큰끼리 벡터가 비슷한 방향을 향하게 된다. 학습된 GPT-2의 `wte`에서 몇몇 토큰과 코사인 유사도가 가장 높은 이웃을 찾아보면 그게 그대로 보인다.

| 토큰 | 가장 가까운 이웃 (코사인 유사도) |
|---|---|
| Paris | Paris(공백 없음) 0.83, France 0.63, French 0.58, London 0.58, Copenhagen 0.57 |
| dog | dogs 0.80, Dog 0.73, canine 0.65, Dogs 0.64 |
| Monday | Tuesday 0.89, Thursday 0.85, Wednesday 0.84, Friday 0.82, Sunday 0.81 |
| happy | Happy 0.69, happier 0.67, unhappy 0.66, pleased 0.63 |
| 7 | 6 0.85, 8 0.85, 5 0.81, 9 0.78, 4 0.74 |

요일은 요일끼리, 숫자는 숫자끼리, 도시는 다른 도시와 그 나라 이름 곁에 모였다. Paris와 dog처럼 관계없는 토큰끼리는 0.21에 그친다. happy 바로 옆에 unhappy가 있는 것도 재미있다. 뜻은 반대지만 문장에서 들어가는 자리가 같으니 비슷한 벡터를 갖게 된 것이다. 임베딩이 담는 건 사전적인 의미라기보다 "어떤 문맥에 등장하는가"에 가깝다.

구현 쪽에서 보면 임베딩은 행렬에서 행 하나를 꺼내는 일이다. 토큰 ID가 464면 `wte`의 464번째 행(숫자 768개)을 꺼내고, 그 토큰이 문장의 0번째 자리에 있으면 `wpe`의 0번째 행을 꺼내 더한다.

```python
x = w["wte.weight"][ids] + w["wpe.weight"][np.arange(len(ids))]   # (T, 768)
```

어텐션은 그 자체로는 순서를 모르는 연산이다. 토큰 순서를 뒤섞어도 같은 집합이면 같은 결과가 나온다. 그래서 위치 정보를 벡터에 직접 더해 줘야 "The cat"과 "cat The"를 구별할 수 있다. GPT-2의 위치 임베딩은 원래 트랜스포머처럼 사인·코사인 공식으로 만든 값이 아니라 학습으로 얻은 값이다. 위치끼리 코사인 유사도를 그려 보면, 아무도 알려 주지 않았는데 가까운 위치끼리 닮아 가는 구조가 학습만으로 생겼다.

![GPT-2 위치 임베딩 0~255번의 코사인 유사도 행렬. 대각선을 따라 진한 빨간 띠가 있어 가까운 위치끼리 비슷하고, 대각선에서 멀어질수록 0 근처로 옅어진다](/assets/img/gpt2-numpy/02_wpe_similarity.png)

"The cat sat on the mat"으로 벡터 크기를 재 보면 토큰 임베딩은 2.5~3.5 정도인데, 위치 임베딩은 0번 자리만 9.88이고 나머지는 4~5다. 방향도 남다르다. 100번 자리는 바로 옆 101번 자리와 코사인 유사도가 0.999인데, 0번 자리는 1번 자리와도 0.52밖에 안 된다. 첫 자리 벡터가 유난히 크고 이웃과 닮지 않았다는 이 특징은 뒤에서 볼 어텐션 맵과도 이어진다.

GPT-2는 위치 임베딩 행이 1,024개뿐이라 그보다 긴 문장은 아예 넣을 수 없다. 지금 모델들이 이 방식을 버리고 RoPE로 옮겨 간 이유 중 하나인데, 이 부분은 글 끝에서 다시 다룬다.

## Self-attention

블록 안에서 토큰끼리 정보를 주고받는 곳은 어텐션 하나뿐이다. 각 위치의 벡터 $x_i$에서 벡터 세 개를 만든다. 질의 $q_i$는 "나는 어떤 정보를 찾는가", 키 $k_j$는 "나는 어떤 정보를 갖고 있다고 내세우는가", 값 $v_j$는 "실제로 건네줄 내용"이다. 위치 $i$는 모든 $j$와 $q_i \cdot k_j$로 점수를 매기고, softmax로 확률처럼 바꾼 다음, 그 비율대로 $v_j$를 섞어서 가져간다.

$$
\mathrm{Attention}(Q,K,V) = \mathrm{softmax}\!\left(\frac{QK^\top}{\sqrt{d_k}} + M\right)V
$$

$M$은 causal mask다. $j > i$인 칸, 즉 미래 위치에 $-\infty$를 넣어서 softmax를 거친 뒤 0이 되게 만든다. GPT-2 small은 768차원을 64차원짜리 헤드 12개로 나눠 이 계산을 각각 한 다음 다시 이어 붙인다. 헤드마다 서로 다른 관계를 보라는 뜻이다. NumPy에서는 reshape와 transpose로 헤드 축을 앞으로 빼 두면 행렬곱 한 번에 12개 헤드가 동시에 계산된다.

```python
def attention(x, w, p, causal=True, scale=True, keep=None):
    T, C = x.shape
    d = C // N_HEAD                                                     # 64
    qkv = x @ w[p + "c_attn.weight"] + w[p + "c_attn.bias"]           # (T, 3C)
    q, k, v = np.split(qkv, 3, axis=-1)
    q, k, v = (a.reshape(T, N_HEAD, d).transpose(1, 0, 2) for a in (q, k, v))  # (H, T, d)
    scores = q @ k.transpose(0, 2, 1)                                   # (H, T, T)
    if scale:
        scores = scores / np.sqrt(d)
    if causal:
        future = np.triu(np.ones((T, T), dtype=bool), k=1)              # j > i 인 칸 = 미래
        scores = np.where(future, -1e10, scores)
    att = softmax(scores)
    out = (att @ v).transpose(1, 0, 2).reshape(T, C)                    # 헤드를 다시 이어 붙임
    return out @ w[p + "c_proj.weight"] + w[p + "c_proj.bias"]
```

`causal`과 `scale` 인자는 뒤의 실험에서 이 장치들을 끄려고 넣었다. 기본값으로 두면 GPT-2와 똑같이 동작한다.

### 어텐션 맵

"The animal didn't cross the street because it was too tired."를 넣고 헤드 144개(12층 × 12헤드)의 어텐션 행렬을 모두 그렸다. 칸 하나는 "행의 토큰이 열의 토큰을 얼마나 보는가"를 뜻하고, 위쪽 삼각형이 비어 있는 건 causal mask 때문이다.

![12층 12헤드 어텐션 맵 144개를 격자로 배치한 그림. 대부분의 헤드가 첫 열(첫 토큰 The)에 밝은 세로줄을 갖고 있고, 몇몇은 대각선 바로 아래 한 칸만 밝은 패턴이다](/assets/img/gpt2-numpy/03_attention_all.png)

가장 먼저 보이는 건 첫 토큰 열에 세로로 밝게 선 줄이다. 헤드와 위치 전체를 평균하면 어텐션의 64%가 첫 토큰으로 갔다. 첫 토큰이 정말 중요해서라기보다는, softmax는 합이 1이라 딱히 볼 게 없을 때도 가중치를 어딘가에 내려놓아야 하고 그 자리로 첫 토큰을 쓰는 것으로 알려져 있다([StreamingLLM 논문의 attention sink](https://arxiv.org/abs/2309.17453)). 위치 임베딩 0번이 유독 컸던 것도 같은 맥락으로 보인다.

![헤드 세 개를 토큰 라벨과 함께 확대한 그림. 층 0 헤드 0은 첫 토큰과 자기 주변에 퍼져 있고, 층 4 헤드 11은 각 행에서 바로 앞 토큰 한 칸만 노랗게 밝다. 층 4 헤드 3에서는 it 행이 animal 열을 강하게 본다](/assets/img/gpt2-numpy/04_attention_heads.png)

층 4 헤드 11은 거의 완벽하게 바로 앞 토큰만 본다(평균 0.999). 층 4 헤드 3에서는 `it`이 `animal`에 0.85를 줬다. 이 문장 하나만으로 모델이 대명사가 가리키는 대상을 사람처럼 풀었다고 말할 수는 없다. 다만 헤드 144개 중 `it` → `animal` 값이 가장 큰 헤드를 골랐을 때 0.85까지 나온다는 것까지는 확인했다.

패턴이 더 분명하게 드러나는 건 반복이다. 무작위 토큰 50개를 두 번 이어 붙여 넣고, 두 번째 반복 구간의 각 위치가 "지난번에 같은 토큰이 나왔던 자리의 바로 다음 토큰"을 얼마나 보는지 헤드마다 쟀다.

![층×헤드 12×12 induction 점수 히트맵. 층 5 헤드 5와 헤드 1, 층 6 헤드 9, 층 7 헤드 10과 헤드 2가 0.8~0.94로 가장 밝고 대부분의 헤드는 0에 가깝다](/assets/img/gpt2-numpy/05_induction.png)

층.헤드로 적으면 5.5(0.94), 6.9(0.92), 5.1(0.91), 7.10(0.89), 7.2(0.80)가 두드러졌고 나머지는 대부분 0 근처였다. 이처럼 앞에서 본 패턴을 이어 가는 헤드를 [Olsson 등](https://transformer-circuits.pub/2022/in-context-learning-and-induction-heads/index.html)은 induction head라고 불렀다. 효과는 손실에서 바로 보인다. 첫 번째 50토큰은 무작위라 토큰당 손실이 12.97로, 어휘 전체에서 아무거나 찍을 때의 $\ln 50257 = 10.82$보다도 나빴다. 그런데 두 번째 반복 구간에서는 0.14까지 떨어졌다. 앞에서 A 다음에 B가 왔으면 이번에도 A 다음에 B를 내놓는 일을 이 헤드들이 하고 있다는 뜻이다. 그 연구는 프롬프트 속 예시를 따라 하는 능력이 이런 회로 위에서 생긴다고 주장한다.

## 트랜스포머 블록과 전체 순전파

블록의 나머지 부품은 간단하다. LayerNorm은 벡터 하나의 768개 값을 평균 0, 분산 1로 맞춘 다음 학습된 배율 `g`와 이동값 `b`를 적용한다. MLP는 768차원을 3072로 넓혔다가 GELU를 거쳐 다시 768로 줄인다. 어텐션이 위치 사이로 정보를 옮긴다면, MLP는 위치마다 따로 그 벡터 안에서 계산한다.

```python
def layer_norm(x, g, b, eps=1e-5):
    mu = x.mean(-1, keepdims=True)
    var = x.var(-1, keepdims=True)
    return (x - mu) / np.sqrt(var + eps) * g + b

def gelu(x):   # GPT-2 의 gelu_new: tanh 근사식
    return 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3)))

def forward(ids, w, causal=True, scale=True, residual=True, keep=None):
    ids = np.asarray(ids)
    x = w["wte.weight"][ids] + w["wpe.weight"][np.arange(len(ids))]
    for i in range(12):
        p = f"h.{i}."
        a = attention(layer_norm(x, w[p + "ln_1.weight"], w[p + "ln_1.bias"]), w, p + "attn.", causal, scale, keep)
        x = x + a if residual else a
        m = mlp(layer_norm(x, w[p + "ln_2.weight"], w[p + "ln_2.bias"]), w, p + "mlp.")
        x = x + m if residual else m
    x = layer_norm(x, w["ln_f.weight"], w["ln_f.bias"])
    return x @ w["wte.weight"].T
```

LayerNorm이 어텐션과 MLP 앞에 놓인 구조(pre-LN)가 원래 트랜스포머와 다른 점이다. [GPT-2 논문](https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf)이 정규화를 이 자리로 옮기고 마지막 블록 뒤에 `ln_f`를 하나 더 붙였다. 이렇게 하면 `x`가 지나가는 큰길(잔차 스트림)에는 정규화가 끼어들지 않고 덧셈만 쌓인다. [Xiong 등](https://arxiv.org/abs/2002.04745)은 이 배치가 학습을 훨씬 안정적으로 만든다는 것을 분석했다.

처음 짤 때 실수한 곳은 가중치 모양이었다. Hugging Face의 GPT-2는 `nn.Linear` 대신 OpenAI 원본을 따른 `Conv1D`를 써서 가중치를 (입력, 출력) 모양으로 저장한다. 그러니 `x @ W`로 바로 곱하면 된다. 습관처럼 `W.T`를 붙이면 768×2304 행렬은 어디에도 곱할 수 없어 바로 에러가 나지만, 정사각형인 `c_proj`(768×768)는 전치해도 에러 없이 숫자만 틀어진다. 이쪽이 훨씬 위험하다.

## Hugging Face와 logits 비교

같은 토큰을 내 구현과 `GPT2LMHeadModel`에 넣고, 모든 위치의 logits(토큰 수 × 50,257)를 비교했다.

![왼쪽은 Hello, my name is 다음 토큰 50,257개에 대해 Hugging Face logits를 가로축, 내 NumPy 구현 logits를 세로축에 찍은 산점도로 모든 점이 대각선 위에 있다. 오른쪽은 프롬프트 네 개에서 float32와 float64의 최대 절대 오차를 로그 축 막대로 비교한 그림으로, float32는 1e-4에서 3e-3, float64는 1e-12 수준이다](/assets/img/gpt2-numpy/00_hf_compare.png)

| 프롬프트 | 토큰 수 | 최대 절대 오차 (float32) | 평균 절대 오차 | 최대 오차 (float64) | argmax 일치 |
|---|---|---|---|---|---|
| Hello, my name is | 5 | 1.42e-4 | 2.7e-5 | 4.4e-13 | 100% |
| The capital of France is | 5 | 1.21e-4 | 1.7e-5 | 6.6e-13 | 100% |
| 안녕하세요. 오늘 날씨가 | 30 | 9.18e-5 | 1.4e-5 | 5.4e-13 | 100% |
| In a shocking finding, ... (×4) | 176 | 2.77e-3 | 7.8e-5 | 1.09e-11 | 100% |

마지막 프롬프트는 logits 절댓값이 최대 317까지 가기 때문에, 2.77e-3도 상대 오차로 따지면 9e-6이다. 그래도 이 차이가 구현이 미세하게 다른 탓인지 단순한 반올림 탓인지는 가려야 했다. 그래서 양쪽을 모두 float64로 올려 다시 쟀더니 오차가 1e-11 아래로 떨어졌다. 계산 순서가 서로 다른 두 구현이 float32에서 각자 반올림하며 쌓은 차이였던 것이다. 176토큰짜리 오차가 큰 것도 행렬곱에서 더하는 항이 길어졌기 때문이다.

greedy 생성도 비교했다. "The meaning of life is"와 "Alan Turing theorized that computers would one day become" 뒤로 각각 30토큰씩 생성했는데, 두 구현의 결과가 토큰 하나까지 같았다. 앞의 것은 `not the same as the meaning of death.`를 되풀이했고, 뒤의 것은 `the most powerful machines on the planet.`으로 이어졌다.

## 탐구 질문 2. √d_k로 나누지 않으면

$q$와 $k$의 각 성분이 평균 0, 분산 1이고 서로 독립이라면, 내적 $q\cdot k = \sum_{i=1}^{d_k} q_i k_i$의 분산은 $d_k$가 된다. 헤드 차원이 64면 표준편차가 8이다. 난수로 재 보니 내적의 분산이 67.8이었고, $\sqrt{64}=8$로 나누자 1.06이 됐다.

softmax는 입력 차이에 지수적으로 반응한다. 점수의 표준편차가 8쯤 되면 가장 큰 점수가 그다음 점수보다 몇씩 앞서는 일이 흔하고, 그 차이는 softmax를 거치며 $e^{\text{차이}}$배로 벌어진다.

![같은 query와 key 20개의 점수를 softmax 한 결과. 왼쪽 √d_k로 나눈 경우는 최대 확률 0.20, 엔트로피 2.50으로 여러 key에 가중치가 퍼져 있고, 오른쪽 나누지 않은 경우는 key 하나가 0.84를 가져가고 엔트로피가 0.60으로 떨어진다](/assets/img/gpt2-numpy/06_sqrt_dk.png)

key 20개를 놓고 보면, 가장 큰 가중치의 평균이 나눴을 때 0.23, 나누지 않았을 때 0.84였다. 실제 GPT-2의 각 층에서 Q와 K를 꺼내 같은 비교를 하면 더 극단적이다. 나누지 않으면 어텐션 행의 77%가 토큰 하나에 0.99 이상을 몰아줬고(나눴을 때는 5%), 층별 엔트로피는 1.0~2.6에서 0.02~0.5로 떨어졌다. 학습된 가중치는 나누는 것을 전제로 맞춰져 있으므로, 나누기만 빼도 앨리스 문단의 토큰당 손실이 3.33에서 5.78로 나빠졌다.

학습에서는 기울기가 문제가 된다. softmax의 야코비안은 $\mathrm{diag}(p) - pp^\top$이고, $p$가 원-핫에 가까울수록 이 행렬은 0에 가까워진다. key 하나가 가중치를 다 가져간 상태에서는 다른 key의 점수를 조금 바꿔도 출력이 거의 변하지 않으니 기울기가 흐르지 않는다. 학습 초기에 어텐션이 무작위로 한 곳에 꽂혀 버리면 거기서 빠져나올 신호도 약하다. $\sqrt{d_k}$로 나누는 것은 차원과 상관없이 점수의 분산을 1 근처로 맞춰서, softmax를 기울기가 잘 흐르는 구간에 붙잡아 두려는 장치다([Attention Is All You Need](https://arxiv.org/abs/1706.03762) 3.2.1절의 설명과 같다).

## 탐구 질문 3. causal mask를 빼면

"The capital of France is"를 넣었을 때의 logits와, 같은 문장 뒤에 " Paris, and the capital of Germany is Berlin."을 덧붙여 넣었을 때 앞 5개 위치의 logits를 비교했다. 마스크가 있으면 두 결과의 최대 차이는 9e-8로 반올림 수준이다. 뒤에 무엇이 오든 앞 위치의 계산은 바뀌지 않는다. 마스크를 빼면 최대 차이가 99.5까지 벌어졌다. 앞 위치가 뒤 토큰을 보기 시작했기 때문이다.

가장 크게 망가지는 건 학습이다. 언어 모델은 문장 하나로 모든 위치의 "다음 토큰 맞히기"를 한꺼번에 학습한다. 위치 $i$의 정답은 $i+1$번째 토큰인데, 마스크가 없으면 위치 $i$의 어텐션이 그 정답을 직접 볼 수 있다. 그러면 모델은 언어를 배울 필요 없이 "오른쪽 옆 칸을 베껴라"만 익혀도 손실을 0 가까이 떨어뜨린다. 사전학습된 GPT-2에서 마스크만 빼고 돌려 보면 정답 자리로 가는 어텐션은 평균 1.7%에 그쳤다. 미래를 보는 법을 배운 적이 없으니 베끼지는 못하고, 처음 보는 입력 분포 탓에 손실만 3.33에서 4.43으로 나빠졌다. 처음부터 마스크 없이 학습시켰다면 그 1.7%를 1 가까이 끌어올리는 쪽으로 학습이 흘러갔을 것이다.

생성도 앞뒤가 맞지 않게 된다. 생성 시점에는 미래 토큰이 아직 없다. 학습 때는 미래를 보며 계산하던 모델이 생성 때는 그럴 수 없으니 학습과 추론의 조건이 어긋난다. 게다가 실제 서비스는 앞 위치의 K와 V를 저장해 두고(KV 캐시) 새 토큰 하나만 계산하는데, 앞 위치 값이 뒤 토큰에 따라 바뀐다면 캐시가 매번 무효가 되어 문장 전체를 다시 계산해야 한다. 이 KV 캐시를 얼마나 작게 만드느냐가 지금 모델 구조를 바꾸는 큰 동력이라는 점도 글 끝에서 다시 보게 된다.

## 탐구 질문 4. 잔차 연결이 없으면

$x_{l+1} = f(x_l)$로만 쌓으면, 출력에서 입력까지 오는 기울기는 각 층 야코비안의 곱이 된다.

$$
\frac{\partial L}{\partial x_0} = J_0^\top J_1^\top \cdots J_{L-1}^\top \frac{\partial L}{\partial x_L}
$$

행렬 48개를 곱하면, 크기가 1보다 조금만 작아도 0으로, 조금만 커도 무한대로 달아난다. 잔차를 넣어 $x_{l+1} = x_l + f(x_l)$로 만들면 각 층의 야코비안이 $I + J_l$이 된다. 이 곱을 전개하면 $I$만 골라 곱한 항, 즉 기울기가 아무 변형 없이 입력까지 지나가는 길이 늘 하나 남는다.

GPT-2를 직접 역전파하는 대신, 256차원 벡터를 $f(x) = W\tanh(x)$에 48번 통과시키는 작은 망을 NumPy로 만들어 확인했다. 출력 쪽에 크기 1인 기울기를 넣고 입력까지 얼마가 남는지를, 가중치 초기화 크기(gain)를 바꿔 가며 쟀다. 잔차가 있는 쪽은 GPT-2 논문처럼 블록 출력 가중치를 $1/\sqrt{N}$로 줄여 초기화했다.

![왼쪽은 48층에서 gain 0.5일 때 층별 기울기 크기로, 잔차가 없으면 입력 쪽으로 갈수록 로그 축에서 직선으로 떨어져 1e-15 근처까지 내려가고 잔차가 있으면 1 근처에 머문다. 오른쪽은 gain을 0.1에서 3까지 바꿨을 때 입력층 기울기로, 잔차 없음은 1e-49에서 1e6까지 요동치고 잔차 있음은 1에서 2.8 사이에 있다](/assets/img/gpt2-numpy/07_residual_grad.png)

| gain | 0.1 | 0.3 | 0.5 | 0.8 | 1.0 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|---|---|---|---|
| 잔차 없음 | 8.3e-49 | 6.4e-26 | 2.6e-15 | 1.2e-5 | 0.15 | 10.8 | 1.4e3 | 1.8e6 |
| 잔차 있음 | 1.00 | 1.02 | 1.05 | 1.14 | 1.23 | 1.50 | 1.88 | 2.84 |

잔차가 없으면 gain이 1 근처의 좁은 구간을 벗어나는 순간 기울기가 사라지거나 폭발한다. 1e-15 같은 기울기를 받는 앞쪽 층은 사실상 학습이 멈춘다. 학습 도중 가중치 크기가 조금만 바뀌어도 그 좁은 구간에서 밀려날 수 있으니, 깊은 망을 그냥 쌓으면 초기화를 아무리 잘 맞춰도 아슬아슬하다. 잔차가 있으면 gain을 30배 바꿔도 1~3 사이를 지킨다. [ResNet 논문](https://arxiv.org/abs/1512.03385)이 50층, 152층 망을 학습시킬 수 있었던 비결이 이것이고, 트랜스포머는 이 구조를 그대로 물려받았다. 2026년 모델들이 64층, 78층까지 쌓을 수 있는 것도 마찬가지다.

학습이 끝난 GPT-2에서 덧셈만 빼 보면 또 다른 면이 보인다. 앨리스 문단의 손실이 3.33에서 9.23으로 올라 무작위로 찍는 수준(10.82)에 가까워졌다. 각 블록은 처음부터 입력을 대체할 값이 아니라 잔차 스트림에 더할 수정분을 내도록 학습됐다. 블록들은 이 공용 스트림에 쓰고 읽으며 정보를 주고받는다. 앞에서 본 induction head가 5층의 어텐션과 그 앞 층들의 결과를 엮어 동작할 수 있는 것도 이 덧셈 덕분이다.

## 탐구 질문 5. temperature와 샘플링

마지막 위치의 logits $z$에서 다음 토큰을 고르는 방법은 여러 가지다.

```python
def next_token(logits, rng, temperature=1.0, top_k=None, top_p=None):
    if temperature == 0:                                   # greedy
        return int(np.argmax(logits))
    z = logits / temperature
    if top_k is not None:                                  # 상위 k개만 남김
        kth = np.sort(z)[-top_k]
        z = np.where(z < kth, -np.inf, z)
    probs = softmax(z)
    if top_p is not None:                                  # 누적확률 p까지만 남김
        order = np.argsort(-probs)
        cum = np.cumsum(probs[order])
        cut = order[cum - probs[order] >= top_p]
        probs[cut] = 0
        probs /= probs.sum()
    return int(rng.choice(len(probs), p=probs))
```

logits를 temperature $T$로 나누면 확률은 $p_i \propto e^{z_i/T}$가 된다. $T<1$이면 큰 값과 작은 값의 격차가 벌어져 분포가 뾰족해지고, $T>1$이면 평평해진다. "Once upon a time, in a small village by the sea," 다음에 올 토큰의 분포로 확인했다.

![같은 프롬프트의 다음 토큰 상위 15개 확률을 temperature 0.1, 1.0, 2.0에서 비교한 막대그래프. 0.1에서는 1등이 0.788, 상위 2개가 90%를 덮는다. 1.0에서는 1등이 0.128이고 90%를 덮는 데 1,841개가 필요하다. 2.0에서는 1등이 0.00539로 막대가 거의 보이지 않고 20,650개가 필요하다](/assets/img/gpt2-numpy/08_temperature.png)

| T | 1등 확률 | 엔트로피 (nats) | 확률 90%를 덮는 토큰 수 |
|---|---|---|---|
| 0.1 | 0.79 | 0.55 | 2 |
| 1.0 | 0.13 | 5.45 | 1,841 |
| 2.0 | 0.005 | 9.76 | 20,650 |

T=2.0에서는 확률 90%를 덮는 데 어휘의 40%가 필요하다. 이 상태로 뽑으면 거의 아무 토큰이나 튀어나온다. 실제로 40토큰씩 생성해 봤다(시드 0, 1, 2로 세 번씩).

| 방식 | 생성 결과 (시드 0) |
|---|---|
| greedy | a man named Tzal, who had been a member of the royal family, had been sent to the city of Tzal, where he had been sent to meet the king of the people |
| T=0.1 | a man named Tzitza was a young man, and he was a man of great wealth. He was a man of great wealth, and he was a man of great wealth. He was |
| T=1.0 | no one for a hundred miles got away and scattered those a sleeping-bird-eye from the tree, and those four alone had entangled Wright with their flew; ... |
| T=2.0 | drilling paper's on liquidity tweaked ma solicitalogcomponent envisioned, extravagaccomplish ordained scholar Ma Oceanis met Princeton linguakiologist ... |
| top-k=40 | as the first-born son of the king's royal-daughter, his mother saw this world in a way that she never could forget—for there was no one less beautiful in his soul than he |
| top-p=0.9 | there was a jaguar game which could draw almost a thousand of its own birds. The players, with one bird or no birds at all, played for a short time. There were eggs of |

T=0.1은 시드를 바꿔도 세 번 모두 "a man named Tz…"나 "a young man named Tz…"로 시작해 greedy와 거의 같았고, "a man of great wealth"를 되풀이하는 고리에 빠졌다. 매번 가장 그럴듯한 토큰만 고르면 방금 쓴 구절이 다시 가장 그럴듯해지기 때문이다. T=1.0은 모델이 배운 분포 그대로 뽑으니 다양하긴 한데, 확률 낮은 토큰이 가끔 섞여 들어 "entangled Wright with their flew"처럼 문법이 무너진다. T=2.0은 단어도 아닌 조각이 줄줄이 이어진다.

top-k와 top-p는 T=1.0의 다양성은 살리고 꼬리만 잘라 낸다. top-k=40은 언제나 후보를 40개만 남기고, top-p=0.9는 분포 모양에 맞춰 남길 개수를 정한다. 이 프롬프트에서 top-p=0.9가 남긴 후보는 1,841개였지만, 분포가 뾰족한 위치에서는 몇 개만 남는다. 확률 낮은 꼬리 토큰을 아예 뽑을 수 없게 막으니 T=1.0보다 문장이 훨씬 멀쩡하다. 꼬리를 자르는 편이 temperature를 낮추는 것보다 반복 없이 자연스러운 글을 낸다는 게 [nucleus sampling 논문](https://arxiv.org/abs/1904.09751)의 결론이었는데, 여기서도 같은 경향이 나왔다.

## 학습과 정렬

지금까지는 이미 학습된 가중치로 순전파만 했다. 그 가중치가 어떻게 만들어지는지는 손실 함수로 정리할 수 있고, 손실값은 내 구현으로 직접 계산해 볼 수 있다.

### 사전학습: 다음 토큰 예측

토큰열 $x_1,\dots,x_T$가 있으면, 모든 위치에서 실제 다음 토큰의 log 확률을 높이도록 학습한다.

$$
\mathcal{L}_{\text{pretrain}} = -\frac{1}{T-1}\sum_{t=1}^{T-1} \log p_\theta(x_{t+1} \mid x_{\le t})
$$

causal mask 덕분에 문장 하나로 $T-1$개 문제를 한꺼번에 푼다. 앨리스 문단(49토큰)에서 GPT-2의 손실은 3.33, perplexity로는 27.9였다. 토큰마다 평균 28개쯤 되는 후보 사이에서 망설이는 정도라는 뜻이다.

앨리스 문단의 첫 문장을 한국어로 옮긴 문장(99토큰)은 토큰당 손실이 2.06으로 오히려 낮게 나왔다. 바이트 단위로 쪼개진 한글은 한 글자의 둘째·셋째 바이트가 거의 정해져 있어서 맞히기 쉬운 토큰이 많기 때문이다. 원문 1바이트당 정보량(bits per byte)으로 바꾸면 영어 1.06, 한국어 2.63으로 순서가 뒤집힌다. 두 문장의 길이와 내용이 완전히 같지는 않으니 정밀한 비교는 아니지만, 방향은 분명하다. 토크나이저가 다르면 토큰당 손실은 서로 비교할 수 없는 숫자다.

이 손실 하나만으로 문법과 사실 지식, 앞에서 본 induction head까지 생겨난다. 모두 다음 토큰을 잘 맞히는 데 도움이 되기 때문이다. 다만 이 목표는 "인터넷 문서의 다음 부분을 그럴듯하게 이어 쓰기"이지 "질문에 답하기"가 아니다.

### 탐구 질문 6. 사전학습만 된 모델과 대화형 모델

사전학습만 된 GPT-2에 질문 형식의 입력을 넣고 greedy로 이어 쓰게 했다.

| 입력 | GPT-2의 이어 쓰기 |
|---|---|
| `Q: What is the capital of France?\nA:` | The capital of France is Paris.\nQ: What is the capital of France?\nA: The capital of France is Paris.\nQ: ... |
| `User: Can you recommend a good book for learning Python?\nAssistant:` | I'm a Python developer and I've been working on Python for a while now. I've been working on Python for a while now and ... |
| `Translate to Korean: I love you.\n` | \nI love you.\n\nI love you.\n\nI love you.\n\n... |

첫 번째는 답은 맞혔지만 멈추지 않고 Q/A 문서의 다음 줄을 계속 만들어 낸다. 질문을 받았다기보다 Q/A 목록 문서를 이어 쓰고 있다고 보는 게 맞다. 두 번째는 Assistant 자리에 자기소개 글을 쓴다. 인터넷에 그런 글이 흔했을 것이다. 세 번째는 번역하는 대신 영어 문장을 되풀이한다. 지식은 있는데, 그것을 요청에 답하는 형태로 꺼내는 법도, 언제 멈춰야 하는지도 모른다.

대화형 모델은 같은 구조, 같은 사전학습에서 출발해 아래 단계들을 더 거친 모델이다.

### SFT: 손실은 같고, 데이터와 마스크가 다르다

지도 미세조정(SFT)은 사람이 쓴 (지시, 응답) 쌍으로 학습한다. 손실은 사전학습과 같은 cross-entropy인데, 지시문 토큰에는 손실을 걸지 않고 응답 토큰에만 건다.

$$
\mathcal{L}_{\text{SFT}} = -\sum_{t \in \text{응답}} \log p_\theta(y_t \mid \text{지시}, y_{<t})
$$

`### Instruction:\nWhat is the capital of France?\n\n### Response:\n` 뒤에 `The capital of France is Paris.<|endoftext|>`를 붙이고, 사전학습된 GPT-2가 응답 토큰마다 받는 손실을 계산했다.

![응답 토큰 8개별 손실 막대그래프. The가 14.3으로 가장 높고, capital, of, France, is는 0.6 이하로 낮다. Paris는 2.8, 마침표는 0.7, endoftext는 5.7이다](/assets/img/gpt2-numpy/09_sft_loss.png)

응답 전체 평균은 3.10이지만 토큰마다 사정이 다르다. `capital of France is`는 질문에서 베껴 오면 되니 0.1~0.6으로 이미 쉽다. `Paris`는 2.83으로, 지식은 어느 정도 갖고 있다. 손실이 큰 쪽은 형식이다. 응답 첫 토큰 `The`의 손실이 14.3이었는데, 확인해 보니 GPT-2는 이 자리에 개행 문자가 올 확률을 0.9997로 보고 있었다. 위에서 `?` 뒤에 빈 줄이 하나 있었으니 `Response:` 뒤에도 빈 줄이 하나 더 올 거라고 패턴을 따라간 것이다. 응답을 끝내는 `<|endoftext|>`도 5.7이다.

SFT가 바꾸는 건 주로 이런 부분이다. 새 지식을 넣는다기보다, 지시가 끝나면 바로 답을 시작하고 답이 끝나면 멈추는 형식과 답하는 말투를 확률 분포에 새긴다. 지시문에도 손실을 걸면(이 예에서는 전체 평균 4.22) 모델이 사용자 질문을 생성하는 법까지 배우느라 학습 신호가 흐려진다.

### RLHF: 무엇이 좋은 답인지 사람의 선호로 배운다

SFT는 정답 응답 하나를 흉내 내게 할 뿐, 같은 질문에 대한 두 답 중 어느 쪽이 나은지는 가르치지 못한다. [InstructGPT](https://arxiv.org/abs/2203.02155)가 정리한 RLHF는 이 빈자리를 두 단계로 채운다.

먼저 같은 프롬프트에 대한 응답 두 개를 사람에게 보여 주고 더 나은 쪽을 고르게 한 다음, 그 데이터로 보상 모델 $r_\phi$를 학습한다. 보상 모델은 보통 같은 트랜스포머에서 출력층만 스칼라 하나로 바꾼 것이고, 손실은 선택된 답 $y_w$의 점수가 거절된 답 $y_l$보다 높게 나오도록 만든다.

$$
\mathcal{L}_{\text{RM}} = -\log \sigma\big(r_\phi(x, y_w) - r_\phi(x, y_l)\big)
$$

그다음 언어 모델(정책 $\pi_\theta$)이 응답을 생성하면 보상 모델이 점수를 매기고, 그 점수가 높아지는 쪽으로 [PPO](https://arxiv.org/abs/1707.06347)를 써서 정책을 업데이트한다. 이때 SFT 모델($\pi_{\text{ref}}$)에서 너무 멀어지지 않도록 KL 벌점을 함께 건다.

$$
\max_\theta \; \mathbb{E}_{y \sim \pi_\theta}\big[r_\phi(x,y)\big] - \beta\, \mathrm{KL}\big(\pi_\theta(\cdot \mid x)\,\big\Vert\,\pi_{\text{ref}}(\cdot \mid x)\big)
$$

KL 항이 없으면 정책은 보상 모델의 허점을 파고든다. 보상 모델도 결국 학습된 함수일 뿐이라, 사람은 좋아하지 않는데 점수만 높게 나오는 이상한 문장이 존재한다. 정책이 그런 문장을 찾아내면 점수는 오르는데 실제 품질은 떨어진다.

### DPO: 보상 모델 없이 선호 데이터로 바로

[DPO](https://arxiv.org/abs/2305.18290)는 위 KL 제약 문제의 최적해가 $\pi^*(y\mid x) \propto \pi_{\text{ref}}(y\mid x)\, e^{r(x,y)/\beta}$ 꼴이라는 점을 이용해, 보상을 정책과 참조 모델의 log 확률 비로 바꿔 쓴다. 그러면 보상 모델도 강화학습도 없이, 선호 쌍에 대한 분류 손실 하나로 정책을 바로 학습할 수 있다.

$$
\mathcal{L}_{\text{DPO}} = -\log \sigma\!\left(\beta \left[\log\frac{\pi_\theta(y_w\mid x)}{\pi_{\text{ref}}(y_w\mid x)} - \log\frac{\pi_\theta(y_l\mid x)}{\pi_{\text{ref}}(y_l\mid x)}\right]\right)
$$

`Q: Is it safe to look directly at the sun?\nA:`에 선택 답 "No. Looking at the sun can permanently damage your eyes."와 거절 답 "Yes, it is totally fine."을 두고(둘 다 앞에 공백 하나를 붙여 이어 썼다), GPT-2로 응답 전체의 log 확률을 계산했다. 선택 답이 -29.5, 거절 답이 -15.7이었다. 사전학습 모델은 짧고 틀린 답에 훨씬 높은 확률을 준다. 토큰이 적을수록 곱해지는 확률도 적다는 영향이 크다.

학습이 시작되는 시점에는 정책과 참조가 같으므로 괄호 안이 0이고 손실은 정확히 $\ln 2 = 0.693$이다. $\beta=0.1$일 때 정책이 선택 답의 log 확률을 참조보다 5 올리거나 거절 답을 5 내리면 손실은 0.474로, 양쪽을 10씩 벌리면 0.127로 줄어든다. 이 손실이 보는 건 절대 확률이 아니라 참조 모델에 비해 얼마나 움직였느냐다. 그래서 원래 -29.5로 낮았던 선택 답도 상대적으로만 올리면 된다. 참조 대비 비율을 쓰는 것 자체가 RLHF의 KL 벌점과 같은 역할을 한다.

### 2026년의 후처리 학습: 검증 가능한 보상과 GRPO

여기까지가 ChatGPT가 처음 나왔을 무렵의 정석이었다. 2025년 이후로는 한 단계가 더 붙었다. 수학 답이나 코드 테스트처럼 정답 여부를 기계가 바로 판정할 수 있는 문제에서는 사람의 선호 대신 "맞았는가"를 보상으로 쓰는 강화학습(RLVR, reinforcement learning with verifiable rewards)을 돌린다. 이 방식을 널리 알린 [DeepSeek-R1](https://arxiv.org/abs/2501.12948)은 SFT 없이 이 강화학습만 돌린 R1-Zero 실험에서 모델이 긴 풀이 과정을 스스로 쓰기 시작한다는 것을 보였다. 지금 Hugging Face에 `HyperCLOVAX-SEED-Think-32B`나 `kanana-2-30b-a3b-thinking`처럼 이름에 Think가 붙은 모델이 흔한 것도 이 흐름에서 나왔다. 그렇다고 선호 학습이 사라진 건 아니다. 말투나 친절함처럼 정답이 없는 부분은 여전히 사람이나 AI의 선호로 맞춰야 하니, 두 방식이 함께 쓰인다. 전체 흐름은 2026년 5월에 개정된 [RL 후처리 학습 서베이](https://arxiv.org/abs/2407.16216)에 정리돼 있다.

이때 주로 쓰는 알고리즘이 [DeepSeekMath](https://arxiv.org/abs/2402.03300)에서 나온 GRPO다. PPO는 각 상태의 가치를 추정하는 가치 모델(critic)을 보통 정책과 비슷한 크기로 하나 더 학습해야 한다. GRPO는 이걸 없앴다. 같은 질문에 답을 $G$개 뽑고, 각 답의 보상을 그 그룹의 평균과 표준편차로 정규화해서 이득(advantage)으로 쓴다.

$$
\hat{A}_i = \frac{r_i - \mathrm{mean}(r_1,\dots,r_G)}{\mathrm{std}(r_1,\dots,r_G)}
$$

평균보다 잘한 답은 확률을 올리고 못한 답은 내린다. 이 계산을 GPT-2로 직접 해 봤다. 질문은 GPT-2에게 어려운 `Q: What is 7 + 5?` 하나와, 답의 앞부분을 `The capital of France is`까지 깔아 둔 쉬운 질문 하나다. 각각 temperature 1.0으로 답을 8개씩(6토큰) 뽑고, 정답 문자열(12, Paris)이 첫 줄에 있으면 보상 1, 없으면 0을 줬다.

| 질문 | GPT-2의 답 (일부) | 보상 | 이득 |
|---|---|---|---|
| 7 + 5 | `No, the "changing planets`, `8 = 6. Symbolism`, `That means 6 is an oct` 등 8개 | 모두 0 | 모두 0 |
| 프랑스 수도 | `Paris when I walked out of`, `Paris. The capital cannot be` 등 4개 | 1 | +1 |
| 프랑스 수도 | `Normandy. Quote: From D`, `Roumania. I have no` 등 4개 | 0 | −1 |

쉬운 질문에서는 8개 중 4개가 Paris를 맞혀서 맞힌 답은 +1, 틀린 답은 −1을 받았다. 사람이 좋고 나쁨을 하나하나 매기지 않아도 정답 판정기만 있으면 학습 신호가 나온다. 반대로 GPT-2에게 덧셈은 너무 어려워서 8개가 모두 틀렸고, 보상이 전부 같으니 이득도 전부 0이 되어 배울 게 하나도 없었다. RLVR이 어느 정도 실력을 갖춘 모델에서 출발하는 이유가 이것이다. [DAPO](https://arxiv.org/abs/2503.14476)처럼 모두 맞히거나 모두 틀린 그룹을 걸러 내고 다시 뽑는 개선안이 나온 것도 같은 문제 때문이다.

정리하면 사전학습은 언어와 지식을, SFT는 지시에 답하는 형식과 멈출 때를, RLHF와 DPO는 여러 가능한 답 가운데 사람이 더 낫다고 보는 쪽을, RLVR은 정답에 이르는 풀이를 확률적으로 밀어 올린다. 모델 구조는 처음부터 끝까지 이 글에서 짠 `forward` 그대로이고, 바뀌는 건 가중치 숫자뿐이다.

## 2026년 모델은 GPT-2에서 무엇이 바뀌었나

그렇다면 구조 자체는 7년 동안 얼마나 바뀌었을까. 2025~2026년에 공개된 모델 다섯 개의 `config.json`을 Hugging Face에서 받아 GPT-2와 나란히 놓았다. 가중치는 받지 않았고, 아래 값은 모두 각 config 파일에 적힌 그대로다.

| 항목 | GPT-2 small (2019) | gpt-oss-20b (2025-08) | Kanana-2 3B (2026-07) | Qwen3.8-27B (2026-08) | K-EXAONE 2.0 (2026-07) | DeepSeek-V4.1-Flash (2026-09) |
|---|---|---|---|---|---|---|
| 층 수 | 12 | 24 | 32 | 64 | 78 | 40 |
| hidden 크기 | 768 | 2,880 | 2,560 | 5,120 | 6,144 | 5,120 |
| 질의 / KV 헤드 | 12 / 12 | 64 / 8 | 32 / 8 | 24 / 4 | 64 / 8 | 64 / 1 |
| 위치 정보 | 학습한 표 1,024개 | RoPE + YaRN | RoPE + YaRN | RoPE (차원의 25%) | RoPE | RoPE + YaRN |
| 최대 문맥 | 1,024 | 131,072 | 32,768 | 262,144 | 262,144 | 1,048,576 |
| 정규화 | LayerNorm | RMSNorm | RMSNorm | RMSNorm | RMSNorm | RMSNorm |
| FFN | GELU | SiLU 게이트, MoE 32개 중 4개 | SiLU 게이트 | SiLU 게이트 | SiLU 게이트, MoE 256개 중 8개 | SiLU 게이트, MoE 384개 중 6개 |
| 어텐션 층 구성 | 전체 12 | 전체 12 + 슬라이딩 12 | 전체 32 | 선형 48 + 전체 16 | 슬라이딩 58 + 전체 20 | 슬라이딩 창 128 등 |
| 어휘 (config) | 50,257 | 201,088 | 128,256 | 248,320 | 153,600 | 129,280 |
| 입출력 임베딩 공유 | 예 | 아니오 | 예 | 아니오 | 아니오 | 아니오 |

잔차 스트림 위에 어텐션과 FFN을 번갈아 쌓고, causal mask를 건 채 다음 토큰을 예측한다는 뼈대는 그대로다. 바뀐 부품들은 이 글에서 직접 본 GPT-2의 한계와 하나씩 맞물린다.

위치 정보가 가장 크게 달라졌다. GPT-2는 위치마다 벡터를 하나씩 학습해 더했기 때문에 1,024번째 이후 위치는 아예 표현할 수 없었다. 지금 모델들은 모두 [RoPE](https://arxiv.org/abs/2104.09864)를 쓴다. 위치를 더하는 대신 $q$와 $k$를 위치에 비례한 각도만큼 회전시켜서, 내적 $q_i \cdot k_j$가 두 위치의 차이 $i-j$에만 의존하게 만든다. 학습 때보다 긴 문맥은 [YaRN](https://arxiv.org/abs/2309.00071) 같은 방법으로 회전 주파수를 늘려 처리한다. DeepSeek-V4.1-Flash의 config에는 65,536 길이를 16배 늘려 1,048,576 토큰까지 받는다고 적혀 있다.

KV 헤드 수도 눈에 띈다. GPT-2는 질의 헤드와 KV 헤드가 12개로 같지만, 최신 모델들은 KV 헤드를 질의 헤드의 1/4~1/64로 줄였다([GQA](https://arxiv.org/abs/2305.13245)). 질의 헤드 여러 개가 K와 V 한 벌을 나눠 쓰는 방식이다. 탐구 질문 3에서 본 KV 캐시가 그만큼 줄어든다. 문맥이 수십만 토큰이 되면 가중치보다 KV 캐시가 메모리를 더 차지하기 때문에, 이 숫자가 곧 서비스 비용이다. 같은 이유로 어텐션 층 일부를 최근 128토큰만 보는 슬라이딩 창으로 바꾸거나(gpt-oss, K-EXAONE), 4층 중 3층을 상태 크기가 고정된 선형 어텐션으로 바꾸기도 한다(Qwen3.8). 앞에서 그린 T×T 어텐션 맵이 문맥 길이의 제곱으로 커지는 문제를 피하려는 선택이다.

FFN은 GELU에서 SiLU 게이트를 쓰는 SwiGLU([Shazeer](https://arxiv.org/abs/2002.05202))로 바뀌었고, 큰 모델일수록 전문가 혼합(MoE)을 쓴다. FFN을 여러 개 두고 토큰마다 일부만 골라 계산하는 구조다. K-EXAONE 2.0은 이름의 750B-A37B가 뜻하듯 전체 파라미터 7,500억 개 중 토큰당 370억 개만 계산하고, DeepSeek-V4.1-Flash는 전문가 384개 중 6개만 쓴다. LayerNorm은 평균을 빼는 단계와 bias를 생략한 [RMSNorm](https://arxiv.org/abs/1910.07467)으로 바뀌었다. 입력과 출력 임베딩을 공유하는 GPT-2 방식은 작은 모델인 Kanana-2 3B에만 남아 있다. 모델이 커지면 임베딩이 차지하는 비중이 작아져서 굳이 아낄 이유가 줄어든다.

결국 바뀐 것은 길이(RoPE, 슬라이딩·선형 어텐션), 메모리(GQA), 계산량(MoE) 쪽이고, 토큰 하나를 만드는 원리는 GPT-2 그대로다. 이 글의 NumPy 코드에서 `wpe`를 RoPE로, `layer_norm`을 RMSNorm으로, `gelu` MLP를 게이트 MLP로 바꾸고 KV 헤드를 나눠 쓰게 하면 구조적으로는 지금 모델과 거의 같아진다.

## 정리

직접 짜 보니 GPT-2의 순전파는 생각보다 짧았다. 토크나이저와 샘플링까지 합쳐도 빈 줄을 빼면 150줄이 안 되고, 정답 확인용 라이브러리와 float64 기준으로 1e-11까지 맞았다. 대신 숫자 하나를 맞추려면 부품 하나하나가 정확해야 했다. LayerNorm의 분산이 편향 추정인지, GELU가 정확식인지 tanh 근사인지, 가중치가 (입력, 출력) 모양인지 가운데 하나만 틀려도 logits가 어긋났다.

부품을 하나씩 빼 본 결과도 분명했다. $\sqrt{d_k}$를 빼면 어텐션의 77%가 한 토큰에 꽂히고 손실이 3.33에서 5.78이 된다. causal mask를 빼면 뒤에 붙인 문장 때문에 앞 위치 logits가 99.5까지 바뀐다. 잔차 연결을 빼면 학습된 모델은 무작위에 가까워지고, 학습 전의 깊은 망은 기울기가 1e-49에서 1e6 사이를 오간다. temperature는 같은 분포를 뾰족하게도 평평하게도 만들어서, 0.1에서는 반복에, 2.0에서는 의미 없는 조각에 빠진다.

한국어 토큰 문제는 7년 사이에 가장 극적으로 나아진 부분이었다. GPT-2에서 4.74배였던 한국어 토큰 수가 2026년 국내 모델 토크나이저에서는 영어보다 적어졌다. 대화형 모델과 사전학습 모델의 차이는 구조가 아니라 무엇을 목표로 학습했느냐에 있었다. 같은 `forward` 위에서 손실을 어디에 거느냐, 무엇과 비교하느냐, 보상을 누가 매기느냐가 달라질 뿐이다.

다음에는 이 구현에 역전파를 붙여 작은 데이터로 SFT를 직접 돌려 보고 싶다. 응답 첫 토큰의 손실 14.3이 몇 스텝 만에 내려가는지, 그리고 7 + 5에서 한 번도 보상을 받지 못한 GPT-2가 쉬운 문제부터 GRPO로 학습하면 어디까지 올라오는지가 궁금하다.

## 참고 자료

- Radford et al., [Language Models are Unsupervised Multitask Learners](https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf) (GPT-2 논문)
- Vaswani et al., [Attention Is All You Need](https://arxiv.org/abs/1706.03762)
- Sennrich et al., [Neural Machine Translation of Rare Words with Subword Units](https://arxiv.org/abs/1508.07909) (BPE)
- He et al., [Deep Residual Learning for Image Recognition](https://arxiv.org/abs/1512.03385)
- Xiong et al., [On Layer Normalization in the Transformer Architecture](https://arxiv.org/abs/2002.04745)
- Olsson et al., [In-context Learning and Induction Heads](https://transformer-circuits.pub/2022/in-context-learning-and-induction-heads/index.html)
- Xiao et al., [Efficient Streaming Language Models with Attention Sinks](https://arxiv.org/abs/2309.17453)
- Holtzman et al., [The Curious Case of Neural Text Degeneration](https://arxiv.org/abs/1904.09751) (top-p)
- Ouyang et al., [Training language models to follow instructions with human feedback](https://arxiv.org/abs/2203.02155) (InstructGPT, RLHF)
- Schulman et al., [Proximal Policy Optimization Algorithms](https://arxiv.org/abs/1707.06347)
- Rafailov et al., [Direct Preference Optimization](https://arxiv.org/abs/2305.18290)
- Shao et al., [DeepSeekMath](https://arxiv.org/abs/2402.03300) (GRPO)
- DeepSeek-AI, [DeepSeek-R1](https://arxiv.org/abs/2501.12948)
- Yu et al., [DAPO](https://arxiv.org/abs/2503.14476)
- [Reinforcement Learning for LLM Post-Training: A Survey](https://arxiv.org/abs/2407.16216)
- Su et al., [RoFormer](https://arxiv.org/abs/2104.09864) (RoPE), Peng et al., [YaRN](https://arxiv.org/abs/2309.00071)
- Ainslie et al., [GQA](https://arxiv.org/abs/2305.13245), Shazeer, [GLU Variants Improve Transformer](https://arxiv.org/abs/2002.05202), Zhang & Sennrich, [RMSNorm](https://arxiv.org/abs/1910.07467)
- 비교에 쓴 Hugging Face 저장소: [openai/gpt-oss-20b](https://huggingface.co/openai/gpt-oss-20b), [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B), [deepseek-ai/DeepSeek-V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash), [LGAI-EXAONE/K-EXAONE-2.0-750B-A37B](https://huggingface.co/LGAI-EXAONE/K-EXAONE-2.0-750B-A37B), [kakaocorp/kanana-2-3b-instruct](https://huggingface.co/kakaocorp/kanana-2-3b-instruct), [naver-hyperclovax/HyperCLOVAX-SEED-Think-32B](https://huggingface.co/naver-hyperclovax/HyperCLOVAX-SEED-Think-32B), [upstage/solar-pro4-tokenizer](https://huggingface.co/upstage/solar-pro4-tokenizer), [mistralai/Mistral-Medium-3.5-128B](https://huggingface.co/mistralai/Mistral-Medium-3.5-128B)
- [openai/tiktoken](https://github.com/openai/tiktoken), [Hugging Face openai-community/gpt2](https://huggingface.co/openai-community/gpt2)
