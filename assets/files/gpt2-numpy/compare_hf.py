"""내 NumPy 구현을 Hugging Face GPT-2, tiktoken 과 맞대어 본다. 결과는 out/compare.json"""
import json, os, time
import numpy as np
import tiktoken
import torch
from transformers import GPT2LMHeadModel, GPT2TokenizerFast
from gpt2_numpy import BPETokenizer, load_weights, forward, generate

os.makedirs("out", exist_ok=True)
tok, w = BPETokenizer(), load_weights()
enc = tiktoken.get_encoding("gpt2")
hf_tok = GPT2TokenizerFast.from_pretrained("gpt2")
hf = GPT2LMHeadModel.from_pretrained("gpt2", attn_implementation="eager").eval()

# 1) 토크나이저: 내 BPE == tiktoken == HF
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
    open(__file__, encoding="utf-8").read(),   # 이 파일 전체
]
tok_report = []
for t in texts:
    a, b, c = tok.encode(t), enc.encode(t), hf_tok.encode(t)
    assert a == b == c, t[:40]
    assert tok.decode(a) == t
    tok_report.append(dict(text=t[:40], n=len(a)))
print("tokenizer: all", len(texts), "texts identical to tiktoken and HF")

# 2) logits
prompts = [
    "Hello, my name is",
    "The capital of France is",
    "안녕하세요. 오늘 날씨가",
    "In a shocking finding, scientists discovered a herd of unicorns living in a remote, "
    "previously unexplored valley in the Andes Mountains. Even more surprising to the "
    "researchers was the fact that the unicorns spoke perfect English." * 4,
]
rows = []
for p in prompts:
    ids = tok.encode(p)
    t0 = time.perf_counter()
    mine = forward(ids, w)
    t_np = time.perf_counter() - t0
    with torch.no_grad():
        ref = hf(torch.tensor([ids])).logits[0].numpy()
    diff = np.abs(mine - ref)
    rows.append(dict(
        prompt=p[:30], tokens=len(ids),
        max_abs=float(diff.max()), mean_abs=float(diff.mean()),
        max_rel=float(diff.max() / np.abs(ref).max()),
        argmax_agree=float((mine.argmax(-1) == ref.argmax(-1)).mean()),
        top1_np=tok.decode([int(mine[-1].argmax())]), top1_hf=tok.decode([int(ref[-1].argmax())]),
        numpy_sec=round(t_np, 3),
    ))
    print(rows[-1])

# 3) greedy 생성 결과가 토큰 단위로 같은가
gen = []
for p in ["The meaning of life is", "Alan Turing theorized that computers would one day become"]:
    ids = tok.encode(p)
    mine = generate(ids, w, 30, temperature=0)
    with torch.no_grad():
        ref = hf.generate(torch.tensor([ids]), max_new_tokens=30, do_sample=False,
                          pad_token_id=50256)[0].tolist()
    gen.append(dict(prompt=p, same=mine == ref[:len(mine)], text=tok.decode(mine)))
    print(gen[-1])

# 4) 오차가 구현 차이인지 float32 반올림인지: 양쪽을 float64 로 올려 다시 잰다
w64 = {k: v.astype(np.float64) for k, v in w.items()}
hf64 = hf.double()
fp64 = []
for p in prompts:
    ids = tok.encode(p)
    with torch.no_grad():
        ref = hf64(torch.tensor([ids])).logits[0].numpy()
    fp64.append(dict(prompt=p[:30], tokens=len(ids), max_abs=float(np.abs(forward(ids, w64) - ref).max())))
    print("float64", fp64[-1])

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = ["DejaVu Sans", "Malgun Gothic"]  # 숫자·기호는 DejaVu, 한글은 맑은 고딕으로 대체
plt.rcParams["text.hinting"] = "no_hinting"  # 맑은 고딕 힌팅이 켜져 있으면 "같" 의 받침이 어긋나 그려진다
ids = tok.encode(prompts[0])
mine = forward(ids, w)[-1]
hf32 = GPT2LMHeadModel.from_pretrained("gpt2", attn_implementation="eager").eval()  # hf 는 위에서 double() 로 바뀌었다
with torch.no_grad():
    ref = hf32(torch.tensor([ids])).logits[0, -1].numpy()
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
axes[0].scatter(ref, mine, s=1, alpha=0.3)
axes[0].plot([ref.min(), ref.max()], [ref.min(), ref.max()], "r--", lw=0.8)
axes[0].set_xlabel("Hugging Face logits"); axes[0].set_ylabel("내 NumPy 구현 logits")
axes[0].set_title(f'"{prompts[0]}" 다음 토큰 50,257개의 logits')
x = np.arange(len(rows))
axes[1].bar(x - 0.2, [r["max_abs"] for r in rows], 0.4, label="float32")
axes[1].bar(x + 0.2, [r["max_abs"] for r in fp64], 0.4, label="float64")
axes[1].set_yscale("log")
axes[1].set_xticks(x, [f'{r["prompt"][:14]}…\n({r["tokens"]} 토큰)' for r in rows], fontsize=8)
axes[1].set_ylabel("최대 절대 오차 (로그)")
axes[1].set_title("HF 와의 logits 최대 오차")
axes[1].legend()
plt.tight_layout(pad=1.2)
plt.savefig("out/fig/00_hf_compare.png", dpi=150, bbox_inches="tight", pad_inches=0.15)

json.dump(dict(tokenizer=tok_report, logits=rows, greedy=gen, float64=fp64), open("out/compare.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
assert all(r["max_abs"] < 1e-2 and r["argmax_agree"] == 1.0 for r in rows)
assert all(g["same"] for g in gen)
print("OK")
