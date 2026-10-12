# 2019 gpt2 vs 2025~26 공개 모델 비교: 한국어 토큰 수, config로 본 구조 차이
# 토크나이저랑 config.json만 받음 (가중치 x). 결과는 out/modern.json, out/fig/10_tokenizers_2026.png
import json
import numpy as np
import tiktoken
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from huggingface_hub import hf_hub_download, model_info
from transformers import AutoTokenizer
from gpt2_numpy import BPE, load, gen

plt.rcParams["font.family"] = ["DejaVu Sans", "Malgun Gothic"]  # 숫자/기호는 dejavu, 한글은 맑은고딕
plt.rcParams["text.hinting"] = "no_hinting"  # 힌팅 켜져 있으면 "같" 받침 깨짐

PAIRS = [  # experiments.py랑 같은 문장 쌍임
    ("Hello, how are you today?", "안녕하세요, 오늘 어떻게 지내세요?"),
    ("The weather is really nice today.", "오늘 날씨가 정말 좋네요."),
    ("I am a student studying computer security.", "저는 컴퓨터 보안을 공부하는 학생입니다."),
    ("Large language models predict the next token.", "대규모 언어 모델은 다음 토큰을 예측한다."),
    ("Please call me when you arrive at the station.", "역에 도착하면 전화해 주세요."),
    ("The cat is sleeping on the sofa.", "고양이가 소파 위에서 자고 있다."),
    ("I would like to order a cup of coffee.", "커피 한 잔 주문하고 싶어요."),
    ("Artificial intelligence is changing the world.", "인공지능이 세상을 바꾸고 있다."),
]

# (표시 이름, 출처). tiktoken:이름 이면 tiktoken, 아니면 hf 저장소
TOKS = [
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


def get_enc(src):
    if src.startswith("tiktoken:"):
        e = tiktoken.get_encoding(src.split(":")[1])
        return e.encode, e.n_vocab
    t = AutoTokenizer.from_pretrained(src, trust_remote_code=False)
    return (lambda s: t.encode(s, add_special_tokens=False)), len(t)


out = {"tokenizers": []}
for nm, src in TOKS:
    enc, nv = get_enc(src)
    en = sum(len(enc(e)) for e, _ in PAIRS)
    ko = sum(len(enc(k)) for _, k in PAIRS)
    dt = None if src.startswith("tiktoken:") else str(model_info(src).created_at)[:10]  # hf 등록일
    out["tokenizers"].append(dict(name=nm, src=src, created=dt, vocab=nv, en=en, ko=ko, ratio=ko / en,
                                  ko_chars_per_token=sum(len(k) for _, k in PAIRS) / ko, hello=[enc("안녕하세요")]))
    print(out["tokenizers"][-1])

# 구조 비교. config.json에 적힌 값 그대로 뽑음
CFGS = ["openai/gpt-oss-20b", "kakaocorp/kanana-2-3b-instruct", "Qwen/Qwen3.8-27B",
        "LGAI-EXAONE/K-EXAONE-2.0-750B-A37B", "deepseek-ai/DeepSeek-V4.1-Flash"]
KEYS = ["model_type", "hidden_size", "num_hidden_layers", "num_attention_heads", "num_key_value_heads",
        "head_dim", "intermediate_size", "moe_intermediate_size", "num_local_experts", "num_experts",
        "n_routed_experts", "num_experts_per_tok", "vocab_size", "max_position_embeddings", "rope_theta",
        "rope_scaling", "rope_parameters", "hidden_act", "rms_norm_eps", "tie_word_embeddings",
        "sliding_window", "layer_types", "full_attention_interval"]
out["configs"] = {}
for r in CFGS:
    c = json.load(open(hf_hub_download(r, "config.json"), encoding="utf-8"))
    c = c.get("text_config", c)
    d = {k: c[k] for k in KEYS if k in c}
    if "layer_types" in d:  # 층 종류별 개수로 줄임
        d["layer_types"] = {t: d["layer_types"].count(t) for t in set(d["layer_types"])}
    out["configs"][r] = d
    print(r, d)

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

# GRPO 그룹 이득을 gpt2로 계산해봄: 같은 질문에 답 8개 뽑고 정답이면 보상 1
tok, w = BPE(), load()
TASKS = [("Q: What is 7 + 5?\nA:", "12"),  # gpt2한테 어려운 문제
         ("Q: What is the capital of France?\nA: The capital of France is", "Paris")]  # 쉬운 문제
out["grpo"] = []
for q, ans in TASKS:
    grp = []
    for sd in range(8):
        ids = tok.encode(q)
        a = tok.decode(gen(ids, w, 6, seed=sd, t=1.0)[len(ids):])
        grp.append(dict(answer=a, reward=float(ans in a.split("\n")[0])))
    r = np.array([g["reward"] for g in grp])
    adv = (r - r.mean()) / (r.std() + 1e-6)  # 그룹 평균/표준편차로 정규화함
    for g, v in zip(grp, adv):
        g["advantage"] = float(v)
        print(repr(g["answer"]), g["reward"], round(float(v), 2))
    out["grpo"].append(dict(prompt=q, group=grp))
json.dump(out, open("out/modern.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
