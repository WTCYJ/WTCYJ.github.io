# GPT-2 small numpy 구현
# hf에서는 가중치랑 vocab/merges 파일만 받음. 토크나이저, 순전파, 샘플링은 직접 짬
import json
import numpy as np
import regex  # \p{L} 쓰려고 re 대신 씀
from huggingface_hub import hf_hub_download
from safetensors.numpy import load_file

REPO = "gpt2"
NH = 12  # 헤드 수


# ---------------- 토크나이저 ----------------
def b2u_table():
    # 바이트 0~255 -> 눈에 보이는 글자 256개로 1:1 매핑함 (gpt2 원본이랑 같은 표임)
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return dict(zip(bs, map(chr, cs)))


class BPE:
    # 먼저 단어 단위로 자름: 축약형 / 공백+글자 / 공백+숫자 / 공백+기호 / 공백
    PAT = regex.compile(r"""'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+""")

    def __init__(self):
        self.enc = json.load(open(hf_hub_download(REPO, "vocab.json"), encoding="utf-8"))
        self.dec = {v: k for k, v in self.enc.items()}
        ms = open(hf_hub_download(REPO, "merges.txt"), encoding="utf-8").read().split("\n")[1:-1]
        self.rank = {tuple(m.split()): i for i, m in enumerate(ms)}  # 위에 있을수록 먼저 합침
        self.b2u = b2u_table()
        self.u2b = {v: k for k, v in self.b2u.items()}

    def bpe(self, w, tr=None):
        # 한 글자씩 쪼갠 다음 rank 제일 낮은 쌍부터 계속 합침
        p = list(w)
        while len(p) > 1:
            r, i = min((self.rank.get(x, 1e18), i) for i, x in enumerate(zip(p, p[1:])))
            if r == 1e18:  # 더 합칠 쌍 없음
                break
            a, b = p[i], p[i + 1]
            out, j = [], 0
            while j < len(p):  # 같은 쌍 여러 개면 왼쪽부터 다 합침
                if j < len(p) - 1 and p[j] == a and p[j + 1] == b:
                    out.append(a + b)
                    j += 2
                else:
                    out.append(p[j])
                    j += 1
            p = out
            if tr is not None:
                tr.append((int(r), (a, b), p[:]))
        return p

    def encode(self, s):
        ids = []
        for x in self.PAT.findall(s):
            w = "".join(self.b2u[b] for b in x.encode("utf-8"))
            ids += [self.enc[t] for t in self.bpe(w)]
        return ids

    def decode(self, ids):
        bs = bytes(self.u2b[c] for c in "".join(self.dec[i] for i in ids))
        return bs.decode("utf-8", errors="replace")

    def tbytes(self, i):
        return bytes(self.u2b[c] for c in self.dec[i])


# ---------------- 모델 ----------------
def load():
    # hf gpt2는 Conv1D라 weight가 (in, out) 모양임 -> x @ W 로 바로 씀
    return load_file(hf_hub_download(REPO, "model.safetensors"))


def ln(x, g, b, eps=1e-5):
    mu = x.mean(-1, keepdims=True)
    var = x.var(-1, keepdims=True)  # n으로 나누는 분산임 (torch LayerNorm이랑 같음)
    return (x - mu) / np.sqrt(var + eps) * g + b


def gelu(x):
    # gpt2는 tanh 근사식(gelu_new) 씀
    return 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3)))


def softmax(x, ax=-1):
    x = x - x.max(ax, keepdims=True)  # exp 터지는 거 막음
    e = np.exp(x)
    return e / e.sum(ax, keepdims=True)


def attn(x, w, p, causal=True, scale=True, keep=None):
    T, C = x.shape
    d = C // NH  # 64
    qkv = x @ w[p + "c_attn.weight"] + w[p + "c_attn.bias"]  # (T, 3C)
    q, k, v = np.split(qkv, 3, axis=-1)
    q, k, v = (a.reshape(T, NH, d).transpose(1, 0, 2) for a in (q, k, v))  # (H, T, d)
    s = q @ k.transpose(0, 2, 1)  # (H, T, T)
    if scale:
        s = s / np.sqrt(d)
    if causal:
        fut = np.triu(np.ones((T, T), dtype=bool), k=1)  # j > i 칸 = 미래
        s = np.where(fut, -1e10, s)
    a = softmax(s)
    if keep is not None:
        keep.append(dict(q=q, k=k, att=a))
    o = (a @ v).transpose(1, 0, 2).reshape(T, C)  # 헤드 다시 이어붙임
    return o @ w[p + "c_proj.weight"] + w[p + "c_proj.bias"]


def mlp(x, w, p):
    h = gelu(x @ w[p + "c_fc.weight"] + w[p + "c_fc.bias"])  # 768 -> 3072
    return h @ w[p + "c_proj.weight"] + w[p + "c_proj.bias"]  # 3072 -> 768


def fwd(ids, w, causal=True, scale=True, res=True, keep=None):
    # ids -> logits (T, 50257). causal/scale/res 끄면 그 장치 뺀 모델 됨 (실험용)
    ids = np.asarray(ids)
    x = w["wte.weight"][ids] + w["wpe.weight"][np.arange(len(ids))]  # 토큰 임베딩 + 위치 임베딩
    for i in range(12):
        p = f"h.{i}."
        a = attn(ln(x, w[p + "ln_1.weight"], w[p + "ln_1.bias"]), w, p + "attn.", causal, scale, keep)
        x = x + a if res else a
        m = mlp(ln(x, w[p + "ln_2.weight"], w[p + "ln_2.bias"]), w, p + "mlp.")
        x = x + m if res else m
    x = ln(x, w["ln_f.weight"], w["ln_f.bias"])
    return x @ w["wte.weight"].T  # 출력층 따로 없음. 입력 임베딩 재사용함 (weight tying)


# ---------------- 샘플링 ----------------
def sample(lg, rng, t=1.0, k=None, p=None):
    if t == 0:  # greedy
        return int(np.argmax(lg))
    z = lg / t
    if k is not None:  # 상위 k개만 남김
        kth = np.sort(z)[-k]
        z = np.where(z < kth, -np.inf, z)
    pr = softmax(z)
    if p is not None:  # 누적확률 p 넘은 다음 토큰부터 버림
        o = np.argsort(-pr)
        cum = np.cumsum(pr[o])
        pr[o[cum - pr[o] >= p]] = 0
        pr /= pr.sum()
    return int(rng.choice(len(pr), p=pr))


def gen(ids, w, n, seed=0, **kw):
    # kv캐시 없이 매번 전체 다시 계산함. 50토큰 정도면 충분히 빠름
    rng = np.random.default_rng(seed)
    ids = list(ids)
    for _ in range(n):
        t = sample(fwd(ids, w)[-1], rng, **kw)
        ids.append(t)
        if t == 50256:  # <|endoftext|>
            break
    return ids


if __name__ == "__main__":
    tok, w = BPE(), load()
    ids = tok.encode("Alan Turing theorized that computers would one day become")
    print(tok.decode(gen(ids, w, 12, t=0)))
    assert tok.decode(tok.encode("안녕하세요, GPT-2!")) == "안녕하세요, GPT-2!"
