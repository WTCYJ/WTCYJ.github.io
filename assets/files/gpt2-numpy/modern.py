"""2019년 GPT-2 와 2025~2026년 공개 모델 비교: 한국어 토큰 수, config 로 본 구조 차이.
토크나이저·config.json 파일만 받는다(가중치 없음). 결과는 out/modern.json, out/fig/10_tokenizers_2026.png"""
import json
import numpy as np
import tiktoken
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from huggingface_hub import hf_hub_download, model_info
from transformers import AutoTokenizer

plt.rcParams["font.family"] = ["DejaVu Sans", "Malgun Gothic"]  # 숫자·기호는 DejaVu, 한글은 맑은 고딕으로 대체
plt.rcParams["text.hinting"] = "no_hinting"  # 맑은 고딕 힌팅이 켜져 있으면 "같" 의 받침이 어긋나 그려진다

PAIRS = [  # experiments.py 와 같은 문장 쌍
    ("Hello, how are you today?", "안녕하세요, 오늘 어떻게 지내세요?"),
    ("The weather is really nice today.", "오늘 날씨가 정말 좋네요."),
    ("I am a student studying computer security.", "저는 컴퓨터 보안을 공부하는 학생입니다."),
    ("Large language models predict the next token.", "대규모 언어 모델은 다음 토큰을 예측한다."),
    ("Please call me when you arrive at the station.", "역에 도착하면 전화해 주세요."),
    ("The cat is sleeping on the sofa.", "고양이가 소파 위에서 자고 있다."),
    ("I would like to order a cup of coffee.", "커피 한 잔 주문하고 싶어요."),
    ("Artificial intelligence is changing the world.", "인공지능이 세상을 바꾸고 있다."),
]

# (표시 이름, 출처) — 출처가 tiktoken:이름 이면 tiktoken, 아니면 HF 저장소
TOKENIZERS = [
    ("GPT-2 (2019)", "tiktoken:gpt2"),
    ("GPT-4 cl100k (2023)", "tiktoken:cl100k_base"),
    ("gpt-oss o200k (2025)", "openai/gpt-oss-20b"),
    ("Mistral Medium 3.5", "mistralai/Mistral-Medium-3.5-128B"),
    ("DeepSeek-V4.1-Flash", "deepseek-ai/DeepSeek-V4.1-Flash"),
    ("Qwen3.8-27B", "Qwen/Qwen3.8-27B"),
    ("HyperCLOVA X SEED Think", "naver-hyperclovax/HyperCLOVAX-SEED-Think-32B"),
    ("Kanana-2 3B", "kakaocorp/kanana-2-3b-instruct"),
    ("K-EXAONE 2.0", "LGAI-EXAONE/K-EXAONE-2.0-750B-A37B"),
    ("Solar Pro 4", "upstage/solar-pro4-tokenizer"),
]


def encoder(src):
    if src.startswith("tiktoken:"):
        e = tiktoken.get_encoding(src.split(":")[1])
        return e.encode, e.n_vocab
    t = AutoTokenizer.from_pretrained(src, trust_remote_code=False)
    return (lambda s: t.encode(s, add_special_tokens=False)), len(t)


out = {"tokenizers": []}
for name, src in TOKENIZERS:
    enc, vocab = encoder(src)
    en = sum(len(enc(e)) for e, _ in PAIRS)
    ko = sum(len(enc(k)) for _, k in PAIRS)
    created = None if src.startswith("tiktoken:") else str(model_info(src).created_at)[:10]
    out["tokenizers"].append(dict(name=name, src=src, created=created, vocab=vocab, en=en, ko=ko,
                                  ratio=ko / en, ko_chars_per_token=sum(len(k) for _, k in PAIRS) / ko,
                                  hello=[enc("안녕하세요")]))
    print(out["tokenizers"][-1])

# 구조 비교: config.json 에서 그대로 읽은 값
CONFIGS = ["openai/gpt-oss-20b", "kakaocorp/kanana-2-3b-instruct", "Qwen/Qwen3.8-27B",
           "LGAI-EXAONE/K-EXAONE-2.0-750B-A37B", "deepseek-ai/DeepSeek-V4.1-Flash"]
KEYS = ["model_type", "hidden_size", "num_hidden_layers", "num_attention_heads", "num_key_value_heads",
        "head_dim", "intermediate_size", "moe_intermediate_size", "num_local_experts", "num_experts",
        "n_routed_experts", "num_experts_per_tok", "vocab_size", "max_position_embeddings", "rope_theta",
        "rope_scaling", "rope_parameters", "hidden_act", "rms_norm_eps", "tie_word_embeddings",
        "sliding_window", "layer_types", "full_attention_interval"]
out["configs"] = {}
for r in CONFIGS:
    c = json.load(open(hf_hub_download(r, "config.json"), encoding="utf-8"))
    c = c.get("text_config", c)
    d = {k: c[k] for k in KEYS if k in c}
    if "layer_types" in d:
        d["layer_types"] = {t: d["layer_types"].count(t) for t in set(d["layer_types"])}
    out["configs"][r] = d
    print(r, d)

json.dump(out, open("out/modern.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

T = out["tokenizers"]
fig, ax = plt.subplots(figsize=(10, 4.8))
y = np.arange(len(T))[::-1]
ax.barh(y + 0.2, [t["en"] for t in T], 0.4, label="영어 8문장")
ax.barh(y - 0.2, [t["ko"] for t in T], 0.4, label="같은 뜻의 한국어 8문장")
for yy, t in zip(y, T):
    ax.text(t["ko"] + 3, yy - 0.2, f"×{t['ratio']:.2f}", va="center", fontsize=9)
ax.set_yticks(y, [f"{t['name']}  ({t['vocab']:,})" for t in T])
ax.set_xlabel("토큰 수")
ax.set_title("같은 뜻, 다른 토큰 수 — 괄호는 어휘 크기")
ax.legend(loc="lower right")
plt.tight_layout(pad=1.2)
plt.savefig("out/fig/10_tokenizers_2026.png", dpi=150, bbox_inches="tight", pad_inches=0.15)

# GRPO 의 '그룹 상대 이득'을 GPT-2 로: 같은 질문에 답 8개를 뽑아 정답 여부(검증 가능한 보상)로 점수를 매긴다
from gpt2_numpy import BPETokenizer, load_weights, generate
tok, w = BPETokenizer(), load_weights()
TASKS = [("Q: What is 7 + 5?\nA:", "12"),                                   # GPT-2 에게 어려운 문제
         ("Q: What is the capital of France?\nA: The capital of France is", "Paris")]  # 쉬운 문제
out["grpo"] = []
for q, answer in TASKS:
    group = []
    for seed in range(8):
        ids = tok.encode(q)
        ans = tok.decode(generate(ids, w, 6, seed=seed, temperature=1.0)[len(ids):])
        group.append(dict(answer=ans, reward=float(answer in ans.split("\n")[0])))
    r = np.array([g["reward"] for g in group])
    adv = (r - r.mean()) / (r.std() + 1e-6)                                # 그룹 평균·표준편차로 정규화
    for g, a in zip(group, adv):
        g["advantage"] = float(a)
        print(repr(g["answer"]), g["reward"], round(float(a), 2))
    out["grpo"].append(dict(prompt=q, group=group))
json.dump(out, open("out/modern.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
