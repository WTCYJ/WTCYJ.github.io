# 내 구현이랑 hf gpt2, tiktoken 결과 비교함. 결과는 out/compare.json
import json, os
import numpy as np
import tiktoken
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from transformers import GPT2LMHeadModel, GPT2TokenizerFast
from gpt2_numpy import BPE, load, fwd, gen

plt.rcParams["font.family"] = ["DejaVu Sans", "Malgun Gothic"]  # 숫자/기호는 dejavu, 한글은 맑은고딕
plt.rcParams["text.hinting"] = "no_hinting"  # 힌팅 켜져 있으면 "같" 받침 깨짐

os.makedirs("out/fig", exist_ok=True)
tok, w = BPE(), load()
tt = tiktoken.get_encoding("gpt2")
htok = GPT2TokenizerFast.from_pretrained("gpt2")
hf = GPT2LMHeadModel.from_pretrained("gpt2", attn_implementation="eager").eval()

# 1. 토크나이저: 내 bpe == tiktoken == hf 인지 확인
texts = [
    "Hello, world!",
    "The quick brown fox jumps over the lazy dog.",
    "I've been waiting for 1,234,567 years... isn't it?",
    "  leading spaces and\ttabs\nnewlines\n\n",
    "안녕하세요. 오늘 날씨가 정말 좋네요!",
    "대규모 언어 모델은 다음 토큰을 예측한다.",
    "日本語のテキストも試してみる。",
    "emoji 🤖🔥 and ünïcödé",
    "def f(x):\n    return x**2  # comment",
    open(__file__, encoding="utf-8").read(),  # 이 파일 통째로
]
tk = []
for s in texts:
    a, b, c = tok.encode(s), tt.encode(s), htok.encode(s)
    assert a == b == c, s[:40]
    assert tok.decode(a) == s
    tk.append(dict(text=s[:40], n=len(a)))
print("tokenizer ok:", [x["n"] for x in tk])

# 2. logits
ps = [
    "Hello, my name is",
    "The capital of France is",
    "안녕하세요. 오늘 날씨가",
    "In a shocking finding, scientists discovered a herd of unicorns living in a remote, "
    "previously unexplored valley in the Andes Mountains. Even more surprising to the "
    "researchers was the fact that the unicorns spoke perfect English." * 4,
]
rows = []
for p in ps:
    ids = tok.encode(p)
    me = fwd(ids, w)
    with torch.no_grad():
        ref = hf(torch.tensor([ids])).logits[0].numpy()
    d = np.abs(me - ref)
    rows.append(dict(prompt=p[:30], tokens=len(ids), max_abs=float(d.max()), mean_abs=float(d.mean()),
                     max_rel=float(d.max() / np.abs(ref).max()),
                     argmax_agree=float((me.argmax(-1) == ref.argmax(-1)).mean())))
    print(rows[-1])

# 3. greedy 생성 결과 토큰 단위로 같은지
gs = []
for p in ["The meaning of life is", "Alan Turing theorized that computers would one day become"]:
    ids = tok.encode(p)
    me = gen(ids, w, 30, t=0)
    with torch.no_grad():
        ref = hf.generate(torch.tensor([ids]), max_new_tokens=30, do_sample=False, pad_token_id=50256)[0].tolist()
    gs.append(dict(prompt=p, same=me == ref[:len(me)], text=tok.decode(me)))
    print(gs[-1])

# 4. 오차가 구현 차이인지 float32 반올림인지 보려고 둘 다 float64로 다시 잼
w64 = {k: v.astype(np.float64) for k, v in w.items()}
hf64 = GPT2LMHeadModel.from_pretrained("gpt2", attn_implementation="eager", torch_dtype=torch.float64).eval()
f64 = []
for p in ps:
    ids = tok.encode(p)
    with torch.no_grad():
        ref = hf64(torch.tensor([ids])).logits[0].numpy()
    f64.append(dict(prompt=p[:30], tokens=len(ids), max_abs=float(np.abs(fwd(ids, w64) - ref).max())))
    print("float64", f64[-1])

# 그림
ids = tok.encode(ps[0])
me = fwd(ids, w)[-1]
with torch.no_grad():
    ref = hf(torch.tensor([ids])).logits[0, -1].numpy()
fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
ax[0].scatter(ref, me, s=1, alpha=0.3)
ax[0].plot([ref.min(), ref.max()], [ref.min(), ref.max()], "r--", lw=0.8)
ax[0].set_xlabel("Hugging Face logits"); ax[0].set_ylabel("내 NumPy 구현 logits")
ax[0].set_title(f'"{ps[0]}" 다음 토큰 50,257개의 logits')
x = np.arange(len(rows))
ax[1].bar(x - 0.2, [r["max_abs"] for r in rows], 0.4, label="float32")
ax[1].bar(x + 0.2, [r["max_abs"] for r in f64], 0.4, label="float64")
ax[1].set_yscale("log")
ax[1].set_xticks(x, [f'{r["prompt"][:14]}…\n({r["tokens"]} 토큰)' for r in rows], fontsize=8)
ax[1].set_ylabel("최대 절대 오차 (로그)")
ax[1].set_title("HF 와의 logits 최대 오차")
ax[1].legend()
plt.tight_layout(pad=1.2)
plt.savefig("out/fig/00_hf_compare.png", dpi=150, bbox_inches="tight", pad_inches=0.15)

json.dump(dict(tokenizer=tk, logits=rows, greedy=gs, float64=f64), open("out/compare.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
assert all(r["max_abs"] < 1e-2 and r["argmax_agree"] == 1.0 for r in rows)
assert all(g["same"] for g in gs)
print("OK")
