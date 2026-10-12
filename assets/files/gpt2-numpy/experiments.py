# 탐구 질문용 실험. 그림은 out/fig/, 숫자는 out/results.json
import json, os
import numpy as np
import tiktoken
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from gpt2_numpy import BPE, load, fwd, gen, softmax

plt.rcParams["font.family"] = ["DejaVu Sans", "Malgun Gothic"]  # 숫자/기호는 dejavu, 한글은 맑은고딕
plt.rcParams["text.hinting"] = "no_hinting"  # 힌팅 켜져 있으면 "같" 받침 깨짐
os.makedirs("out/fig", exist_ok=True)
tok, w = BPE(), load()
R = {}


def save(nm):
    plt.tight_layout(pad=1.2)
    plt.savefig(f"out/fig/{nm}.png", dpi=150, bbox_inches="tight", pad_inches=0.15)
    plt.close()


def nlp(ids, **kw):
    # 각 위치에서 실제 다음 토큰에 준 log 확률 (길이 T-1)
    lg = fwd(ids, w, **kw)[:-1]
    lg = lg - lg.max(-1, keepdims=True)
    lp = lg - np.log(np.exp(lg).sum(-1, keepdims=True))
    return lp[np.arange(len(ids) - 1), ids[1:]]


def ent(p, ax=-1):
    return -(p * np.log(p + 1e-30)).sum(ax)


# ======== 1. 토크나이저 ========
pairs = [
    ("Hello, how are you today?", "안녕하세요, 오늘 어떻게 지내세요?"),
    ("The weather is really nice today.", "오늘 날씨가 정말 좋네요."),
    ("I am a student studying computer security.", "저는 컴퓨터 보안을 공부하는 학생입니다."),
    ("Large language models predict the next token.", "대규모 언어 모델은 다음 토큰을 예측한다."),
    ("Please call me when you arrive at the station.", "역에 도착하면 전화해 주세요."),
    ("The cat is sleeping on the sofa.", "고양이가 소파 위에서 자고 있다."),
    ("I would like to order a cup of coffee.", "커피 한 잔 주문하고 싶어요."),
    ("Artificial intelligence is changing the world.", "인공지능이 세상을 바꾸고 있다."),
]
encs = {n: tiktoken.get_encoding(n) for n in ["gpt2", "cl100k_base", "o200k_base"]}
rows = []
for en, ko in pairs:
    r = dict(en=en, ko=ko, en_chars=len(en), ko_chars=len(ko), en_bytes=len(en.encode()), ko_bytes=len(ko.encode()))
    for n, e in encs.items():
        r[f"en_{n}"], r[f"ko_{n}"] = len(e.encode(en)), len(e.encode(ko))
    rows.append(r)
tot = {k: sum(r[k] for r in rows) for k in rows[0] if k not in ("en", "ko")}
ratio = {n: tot[f"ko_{n}"] / tot[f"en_{n}"] for n in encs}
R["tokens"] = dict(rows=rows, total=tot, ratio=ratio)
print("ko/en", ratio, "bytes", tot["ko_bytes"] / tot["en_bytes"])

# 병합 과정 찍어봄
for s in [" tokenization", " 안녕하세요"]:
    tr = []
    bs = "".join(tok.b2u[b] for b in s.encode())
    tok.bpe(bs, tr)
    R.setdefault("bpe_trace", {})[s] = dict(start=list(bs), steps=[(r, list(p), x) for r, p, x in tr])
    print(s, "->", len(tr), "merges", tr[-1][2] if tr else list(bs))
R["ko_split"] = [(i, tok.tbytes(i).hex(" ")) for i in tok.encode("안녕하세요")]
print("안녕하세요 ->", R["ko_split"])
# vocab에 온전한 한글 음절 들어간 토큰 몇 개인지 셈
hg = [i for i in range(50257) if any("가" <= c <= "힣" for c in tok.tbytes(i).decode("utf-8", "ignore"))]
R["vocab_hangul_tokens"] = [tok.tbytes(i).decode() for i in hg]
print("hangul tokens:", len(hg))


# ======== 2. 임베딩 ========
wpe = w["wpe.weight"]
n = wpe[:256] / np.linalg.norm(wpe[:256], axis=1, keepdims=True)
fig, ax = plt.subplots(figsize=(5.6, 4.6))
im = ax.imshow(n @ n.T, cmap="RdBu_r", vmin=-1, vmax=1)
ax.set_title("위치 임베딩 코사인 유사도 (0~255)")
ax.set_xlabel("위치 j"); ax.set_ylabel("위치 i")
plt.colorbar(im, ax=ax)
save("02_wpe_similarity")
ids = tok.encode("The cat sat on the mat")
R["embedding_norms"] = dict(tokens=[tok.decode([i]) for i in ids],
                            wte=np.linalg.norm(w["wte.weight"][ids], axis=1).round(2).tolist(),
                            wpe=np.linalg.norm(wpe[:len(ids)], axis=1).round(2).tolist())
print("emb norm", R["embedding_norms"])

# ======== 3. 어텐션 맵 ========
sent = "The animal didn't cross the street because it was too tired."
ids = tok.encode(sent)
lab = [tok.decode([i]) for i in ids]
keep = []
fwd(ids, w, keep=keep)
att = np.stack([k["att"] for k in keep])  # (층, 헤드, T, T)
it, an = lab.index(" it"), lab.index(" animal")
L, H = np.unravel_index(att[:, :, it, an].argmax(), (12, 12))  # it -> animal 제일 센 헤드
prev = np.array([[np.mean([att[l, h, i, i - 1] for i in range(1, len(ids))]) for h in range(12)] for l in range(12)])
pl, ph = np.unravel_index(prev.argmax(), (12, 12))  # 바로 앞 토큰 제일 잘 보는 헤드
R["attention"] = dict(it_to_animal_best=(int(L), int(H), float(att[L, H, it, an])),
                      prev_token_best=(int(pl), int(ph), float(prev[pl, ph])),
                      first_token_mass=float(att[:, :, 1:, 0].mean()))
print("attn", R["attention"])

fig, axs = plt.subplots(12, 12, figsize=(12, 12))
for l in range(12):
    for h in range(12):
        axs[l, h].imshow(att[l, h], cmap="viridis", vmin=0, vmax=1)
        axs[l, h].set_xticks([]); axs[l, h].set_yticks([])
        if h == 0: axs[l, h].set_ylabel(f"L{l}", fontsize=8)
        if l == 0: axs[l, h].set_title(f"H{h}", fontsize=8)
fig.suptitle(f'"{sent}" 의 어텐션 맵 144개 (행=층, 열=헤드)')
save("03_attention_all")

fig, axs = plt.subplots(1, 3, figsize=(15, 5))
for ax, (l, h, ttl) in zip(axs, [(0, 0, "층 0 헤드 0"),
                                 (pl, ph, f"층 {pl} 헤드 {ph}: 바로 앞 토큰"),
                                 (L, H, f"층 {L} 헤드 {H}: ' it' → ' animal'")]):
    ax.imshow(att[l, h], cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(len(lab)), lab, rotation=90, fontsize=8)
    ax.set_yticks(range(len(lab)), lab, fontsize=8)
    ax.set_xlabel("보는 토큰 (key)"); ax.set_ylabel("질의 토큰 (query)")
    ax.set_title(ttl)
save("04_attention_heads")

# induction head: 랜덤 토큰 50개 두 번 반복해서 넣음
rng = np.random.default_rng(0)
seq = rng.integers(1000, 20000, 50).tolist()
ids = [50256] + seq + seq
keep = []
fwd(ids, w, keep=keep)
att = np.stack([k["att"] for k in keep])
q = np.arange(51, 101)  # 두 번째 반복 구간
ind = att[:, :, q, q - 49].mean(-1)  # 지난번 등장 위치 '바로 다음' 토큰 보는 정도
lp = nlp(np.array(ids))
R["induction"] = dict(top=[(int(a), int(b), float(ind[a, b])) for a, b in
                           zip(*np.unravel_index(np.argsort(-ind, axis=None)[:5], (12, 12)))],
                      loss_first=float(-lp[:50].mean()), loss_second=float(-lp[51:].mean()))
print("induction", R["induction"])
fig, ax = plt.subplots(figsize=(5.5, 4.5))
im = ax.imshow(ind, cmap="magma")
ax.set_xlabel("헤드"); ax.set_ylabel("층", rotation=0, labelpad=12); ax.set_xticks(range(12)); ax.set_yticks(range(12))
ax.set_title("induction 점수 (반복 구간에서 '지난번 다음 토큰'에 준 어텐션)")
plt.colorbar(im, ax=ax)
save("05_induction")

# ======== 4. sqrt(d_k) ========
d = 64
rng = np.random.default_rng(1)
qr, kr = rng.standard_normal((1000, d)), rng.standard_normal((20, d))
dots = qr @ kr.T
R["sqrt_dk_random"] = dict(var_raw=float(dots.var()), var_scaled=float((dots / 8).var()),
                           maxp_raw=float(softmax(dots).max(-1).mean()),
                           maxp_scaled=float(softmax(dots / 8).max(-1).mean()))
# 실제 gpt2에서 나누기 빼면 같은 점수에 8배 곱한 거랑 같음
text = ("Alice was beginning to get very tired of sitting by her sister on the bank, and of having "
        "nothing to do: once or twice she had peeped into the book her sister was reading, but it had "
        "no pictures or conversations in it.")
tids = np.array(tok.encode(text))
keep = []
fwd(tids, w, keep=keep)
es, eu = [], []
T = len(tids)
mask = np.triu(np.ones((T, T), bool), 1)
for k in keep:
    s = k["q"] @ k["k"].transpose(0, 2, 1)
    for sc in (True, False):
        a = softmax(np.where(mask, -1e10, s / 8 if sc else s))
        (es if sc else eu).append(float(ent(a)[:, 10:].mean()))


def onehot(div):
    # 한 토큰에 0.99 넘게 몰아준 행 비율
    return float(np.mean([(softmax(np.where(mask, -1e10, k["q"] @ k["k"].transpose(0, 2, 1) / div)).max(-1) > 0.99).mean()
                          for k in keep]))


R["sqrt_dk_gpt2"] = dict(entropy_scaled=es, entropy_unscaled=eu,
                         onehot_frac_unscaled=onehot(1), onehot_frac_scaled=onehot(8),
                         loss_scaled=float(-nlp(tids).mean()), loss_unscaled=float(-nlp(tids, scale=False).mean()))
print("sqrt_dk", R["sqrt_dk_random"], {k: v for k, v in R["sqrt_dk_gpt2"].items() if "entropy" not in k})

# 평균적인 행 하나 고름 (안 나눴을 때 최대확률이 평균이랑 제일 가까운 거)
row = dots[np.argmin(np.abs(softmax(dots).max(-1) - R["sqrt_dk_random"]["maxp_raw"]))]
fig, axs = plt.subplots(1, 2, figsize=(10, 3.5))
for ax, (z, ttl) in zip(axs, [(row / 8, "√d_k 로 나눔"), (row, "나누지 않음")]):
    p = softmax(z)
    ax.bar(range(20), p)
    ax.set_ylim(0, 1)
    ax.set_title(f"{ttl}: 최대 확률 {p.max():.2f}, 엔트로피 {ent(p):.2f}")
    ax.set_xlabel("key 번호"); ax.set_ylabel("어텐션 가중치")
    ax.set_xticks(range(0, 20, 2))
save("06_sqrt_dk")


# softmax 야코비안 diag(p) - pp^T. 원핫에 가까울수록 0에 가까워짐
def jn(z):
    p = softmax(z)
    return np.linalg.norm(np.diag(p) - np.outer(p, p))


R["sqrt_dk_random"]["softmax_jacobian_norm_scaled"] = float(np.mean([jn(r / 8) for r in dots[:200]]))
R["sqrt_dk_random"]["softmax_jacobian_norm_raw"] = float(np.mean([jn(r) for r in dots[:200]]))

# ======== 5. causal mask ========
pre = tok.encode("The capital of France is")
full = pre + tok.encode(" Paris, and the capital of Germany is Berlin.")
R["causal"] = {}
for c in (True, False):
    a = fwd(pre, w, causal=c)
    b = fwd(full, w, causal=c)[:len(pre)]
    R["causal"][f"prefix_change_causal={c}"] = float(np.abs(a - b).max())
R["causal"]["loss_with_mask"] = float(-nlp(tids).mean())
R["causal"]["loss_without_mask"] = float(-nlp(tids, causal=False).mean())
# 마스크 없으면 i가 정답(i+1)을 볼 수 있음 -> 바로 다음 토큰으로 가는 어텐션 양 잼
keep = []
fwd(tids, w, causal=False, keep=keep)
R["causal"]["attention_to_answer_no_mask"] = float(np.mean([k["att"][:, np.arange(T - 1), np.arange(1, T)].mean() for k in keep]))
print("causal", R["causal"])


# ======== 6. 잔차 연결 ========
def gnorm(D, res, g0, d=256, seed=0):
    # x <- x + W tanh(x) (잔차 없으면 W tanh(x)), W ~ N(0, g0^2/d)
    # 출력 쪽에 크기 1 기울기 넣고 입력까지 역전파한 크기 기록함. [0]이 입력 쪽
    rng = np.random.default_rng(seed)
    Ws = [rng.standard_normal((d, d)) * g0 / np.sqrt(d) for _ in range(D)]
    xs = [rng.standard_normal(d)]
    for W in Ws:
        f = W @ np.tanh(xs[-1])
        xs.append(xs[-1] + f if res else f)
    g = rng.standard_normal(d); g /= np.linalg.norm(g)
    ns = [1.0]
    for W, x in zip(reversed(Ws), reversed(xs[:-1])):
        gf = (W.T @ g) * (1 - np.tanh(x) ** 2)  # f 거쳐가는 길
        g = g + gf if res else gf  # 잔차 있으면 그대로 지나가는 길이 하나 더 있음
        ns.append(float(np.linalg.norm(g)))
    return ns[::-1]


D = 48
gs = [0.1, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0]
# 잔차 쪽은 gpt2 논문처럼 블록 출력 가중치를 1/sqrt(N)으로 줄여서 초기화함
R["residual_toy"] = {g: dict(plain=gnorm(D, False, g)[0], residual=gnorm(D, True, g / np.sqrt(D))[0]) for g in gs}
fig, axs = plt.subplots(1, 2, figsize=(12, 4))
axs[0].semilogy(gnorm(D, False, 0.5), "o-", ms=3, label="잔차 없음  x ← f(x)")
axs[0].semilogy(gnorm(D, True, 0.5 / np.sqrt(D)), "o-", ms=3, label="잔차 있음  x ← x + f(x)")
axs[0].set_xlabel("층 번호 (0 = 입력 쪽)"); axs[0].set_ylabel("기울기 크기 (로그)")
axs[0].set_title("48층, gain 0.5: 출력의 기울기가 입력까지 오는 동안")
axs[0].legend()
axs[1].loglog(gs, [R["residual_toy"][g]["plain"] for g in gs], "o-", label="잔차 없음")
axs[1].loglog(gs, [R["residual_toy"][g]["residual"] for g in gs], "o-", label="잔차 있음")
axs[1].axhline(1, color="gray", lw=0.8, ls="--")
axs[1].set_xticks(gs, [str(g) for g in gs]); axs[1].minorticks_off()
axs[1].set_xlabel("가중치 초기화 크기 gain"); axs[1].set_ylabel("입력층 기울기 크기 (로그)")
axs[1].set_title("48층, 초기화 크기에 따른 입력층 기울기")
axs[1].legend()
save("07_residual_grad")
R["residual_gpt2"] = dict(loss_with=float(-nlp(tids).mean()), loss_without=float(-nlp(tids, res=False).mean()))
print("res", R["residual_toy"], R["residual_gpt2"])

# ======== 7. 샘플링 ========
prompt = "Once upon a time, in a small village by the sea,"
pids = tok.encode(prompt)
cfgs = [("greedy", dict(t=0)), ("T=0.1", dict(t=0.1)), ("T=1.0", dict(t=1.0)), ("T=2.0", dict(t=2.0)),
        ("top-k=40", dict(t=1.0, k=40)), ("top-p=0.9", dict(t=1.0, p=0.9))]
outs = {}
for nm, kw in cfgs:
    outs[nm] = []
    for sd in (range(1) if nm == "greedy" else range(3)):
        o = gen(pids, w, 40, seed=sd, **kw)
        outs[nm].append(tok.decode(o[len(pids):]))
        print(nm, sd, repr(outs[nm][-1]))
R["sampling"] = dict(prompt=prompt, gens=outs)

lg = fwd(pids, w)[-1]
R["sampling"]["dist"] = {}
fig, axs = plt.subplots(1, 3, figsize=(14, 3.8), sharey=True)
top = np.argsort(-lg)[:15]
for ax, tp in zip(axs, (0.1, 1.0, 2.0)):
    p = softmax(lg / tp)
    n90 = int(np.searchsorted(np.cumsum(np.sort(p)[::-1]), 0.9) + 1)  # 확률 90% 덮는 데 필요한 토큰 수
    R["sampling"]["dist"][tp] = dict(entropy=float(ent(p)), top1=float(p.max()), n_for_90pct=n90)
    ax.bar(range(15), p[top])
    ax.set_xticks(range(15), [repr(tok.decode([i]))[1:-1] for i in top], rotation=70, fontsize=8)
    ax.set_title(f"T={tp}: 1등 {p.max():.3g}, 90%를 덮는 데 {n90:,}개")
axs[0].set_ylabel("다음 토큰 확률")
save("08_temperature")
p = softmax(lg)
R["sampling"]["top_p_0.9_kept"] = int(np.searchsorted(np.cumsum(np.sort(p)[::-1]), 0.9) + 1)
print("dist", R["sampling"]["dist"], "top-p kept", R["sampling"]["top_p_0.9_kept"])

# ======== 8. 학습/정렬 ========
# 사전학습 손실 = 다음 토큰 cross-entropy
for nm, s in [("en", text), ("ko", "앨리스는 언니 옆 강둑에 앉아 아무것도 하지 않는 것에 몹시 지루해지기 시작했다.")]:
    lp = nlp(np.array(tok.encode(s)))
    R.setdefault("pretrain_loss", {})[nm] = dict(tokens=len(lp) + 1, loss=float(-lp.mean()), ppl=float(np.exp(-lp.mean())),
                                                  bits_per_byte=float(-lp.sum() / np.log(2) / len(s.encode())))
print("pretrain", R["pretrain_loss"])

# 사전학습만 된 모델한테 질문 넣어봄
R["chat"] = {}
for s in ["Q: What is the capital of France?\nA:",
          "User: Can you recommend a good book for learning Python?\nAssistant:",
          "Translate to Korean: I love you.\n"]:
    o = gen(tok.encode(s), w, 40, t=0)
    R["chat"][s] = tok.decode(o)[len(s):]
    print(repr(s), "->", repr(R["chat"][s]))

# SFT: 손실은 같은 ce인데 응답 토큰에만 걸음
inst = "### Instruction:\nWhat is the capital of France?\n\n### Response:\n"
a, b = tok.encode(inst), tok.encode("The capital of France is Paris.") + [50256]
lp = nlp(np.array(a + b))
R["sft"] = dict(prompt_tokens=len(a), response_tokens=len(b),
                loss_all=float(-lp.mean()), loss_response_only=float(-lp[len(a) - 1:].mean()),
                per_token=[(tok.decode([t]), float(-l)) for t, l in zip(b, lp[len(a) - 1:])])
print("sft", R["sft"])
fig, ax = plt.subplots(figsize=(8, 3.5))
xl = [repr(x)[1:-1] for x, _ in R["sft"]["per_token"]]
ax.bar(range(len(xl)), [l for _, l in R["sft"]["per_token"]])
ax.set_xticks(range(len(xl)), xl, rotation=30)
ax.set_ylabel("−log p (nats)")
ax.set_title("SFT 손실이 걸리는 응답 토큰별 손실 (사전학습만 된 GPT-2)")
save("09_sft_loss")

# DPO: 정책 = 참조 = gpt2 인 시작 시점
qq = "Q: Is it safe to look directly at the sun?\nA:"
yw, yl = " No. Looking at the sun can permanently damage your eyes.", " Yes, it is totally fine."


def seq_lp(pr, rs):
    a = tok.encode(pr)
    return float(nlp(np.array(a + tok.encode(rs)))[len(a) - 1:].sum())


lc, lr = seq_lp(qq, yw), seq_lp(qq, yl)
beta = 0.1


def dpo(pc, pr, rc=lc, rr=lr):
    m = beta * ((pc - rc) - (pr - rr))
    return float(np.log1p(np.exp(-m)))


R["dpo"] = dict(logp_chosen=lc, logp_rejected=lr, loss_at_init=dpo(lc, lr),
                loss_if_chosen_up_5=dpo(lc + 5, lr), loss_if_rejected_down_5=dpo(lc, lr - 5),
                loss_if_both_10=dpo(lc + 10, lr - 10))
print("dpo", R["dpo"])

json.dump(R, open("out/results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
assert R["causal"]["prefix_change_causal=True"] < 1e-3 < R["causal"]["prefix_change_causal=False"]
assert abs(R["dpo"]["loss_at_init"] - np.log(2)) < 1e-9
print("done")
