"""GPT-2 small, NumPy only.

가중치와 토크나이저 파일(vocab.json, merges.txt)만 Hugging Face Hub에서 받고,
토크나이저(BPE)와 순전파·생성은 전부 여기서 직접 계산한다.
"""
import json
import numpy as np
import regex  # \p{L} 같은 유니코드 클래스 때문에 표준 re 대신 씀 (GPT-2 원본 코드와 같은 패턴)
from huggingface_hub import hf_hub_download
from safetensors.numpy import load_file

REPO = "gpt2"
N_HEAD = 12


# ---------------------------------------------------------------- 토크나이저
def bytes_to_unicode():
    """바이트 0~255 를 '눈에 보이는' 유니코드 글자 256개에 1:1 대응시킨다.
    공백·제어문자를 그대로 쓰면 vocab.json 에 문자열로 저장하기 곤란해서 GPT-2가 만든 표."""
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return dict(zip(bs, map(chr, cs)))


class BPETokenizer:
    # 문장을 먼저 '단어 조각'으로 자른다. 영어 축약형, 글자 묶음, 숫자 묶음, 기호 묶음, 공백.
    PAT = regex.compile(r"""'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+""")

    def __init__(self):
        self.encoder = json.load(open(hf_hub_download(REPO, "vocab.json"), encoding="utf-8"))
        self.decoder = {v: k for k, v in self.encoder.items()}
        merges = open(hf_hub_download(REPO, "merges.txt"), encoding="utf-8").read().split("\n")[1:-1]
        self.ranks = {tuple(m.split()): i for i, m in enumerate(merges)}  # 먼저 학습된 병합일수록 rank 가 작다
        self.b2u = bytes_to_unicode()
        self.u2b = {v: k for k, v in self.b2u.items()}

    def bpe(self, word, trace=None):
        """word(바이트를 글자로 바꾼 문자열)를 한 글자씩 쪼갠 뒤, rank 가 가장 낮은 인접 쌍부터 계속 합친다."""
        parts = list(word)
        while len(parts) > 1:
            pairs = [(self.ranks.get(p, 1e18), i) for i, p in enumerate(zip(parts, parts[1:]))]
            rank, i = min(pairs)
            if rank == 1e18:
                break
            pair = (parts[i], parts[i + 1])
            # 같은 쌍이 여러 번 나오면 왼쪽부터 전부 합친다
            out, j = [], 0
            while j < len(parts):
                if j < len(parts) - 1 and (parts[j], parts[j + 1]) == pair:
                    out.append(parts[j] + parts[j + 1])
                    j += 2
                else:
                    out.append(parts[j])
                    j += 1
            parts = out
            if trace is not None:
                trace.append((int(rank), pair, parts[:]))
        return parts

    def encode(self, text):
        ids = []
        for piece in self.PAT.findall(text):
            word = "".join(self.b2u[b] for b in piece.encode("utf-8"))
            ids += [self.encoder[t] for t in self.bpe(word)]
        return ids

    def decode(self, ids):
        data = bytes(self.u2b[c] for c in "".join(self.decoder[i] for i in ids))
        return data.decode("utf-8", errors="replace")

    def token_bytes(self, i):
        return bytes(self.u2b[c] for c in self.decoder[i])


# ---------------------------------------------------------------- 모델
def load_weights():
    """safetensors 를 NumPy 배열 dict 로. HF GPT-2 는 Conv1D 라서 weight 가 (in, out) 모양이다 → x @ W 로 바로 쓴다."""
    return load_file(hf_hub_download(REPO, "model.safetensors"))


def layer_norm(x, g, b, eps=1e-5):
    mu = x.mean(-1, keepdims=True)
    var = x.var(-1, keepdims=True)  # 분모 n (편향 분산) — PyTorch LayerNorm 과 같다
    return (x - mu) / np.sqrt(var + eps) * g + b


def gelu(x):
    # GPT-2 의 gelu_new: tanh 근사식
    return 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3)))


def softmax(x, axis=-1):
    x = x - x.max(axis, keepdims=True)  # 큰 값이 exp 에서 넘치지 않게
    e = np.exp(x)
    return e / e.sum(axis, keepdims=True)


def attention(x, w, p, causal=True, scale=True, keep=None):
    T, C = x.shape
    d = C // N_HEAD
    qkv = x @ w[p + "c_attn.weight"] + w[p + "c_attn.bias"]           # (T, 3C)
    q, k, v = np.split(qkv, 3, axis=-1)                                 # 각 (T, C)
    q, k, v = (a.reshape(T, N_HEAD, d).transpose(1, 0, 2) for a in (q, k, v))  # (H, T, d)
    scores = q @ k.transpose(0, 2, 1)                                   # (H, T, T)
    if scale:
        scores = scores / np.sqrt(d)
    if causal:
        future = np.triu(np.ones((T, T), dtype=bool), k=1)              # j > i 인 칸 = 미래
        scores = np.where(future, -1e10, scores)
    att = softmax(scores)
    if keep is not None:
        keep.append(dict(q=q, k=k, att=att))
    out = (att @ v).transpose(1, 0, 2).reshape(T, C)                    # 헤드들을 다시 이어 붙임
    return out @ w[p + "c_proj.weight"] + w[p + "c_proj.bias"]


def mlp(x, w, p):
    h = gelu(x @ w[p + "c_fc.weight"] + w[p + "c_fc.bias"])            # 768 → 3072
    return h @ w[p + "c_proj.weight"] + w[p + "c_proj.bias"]           # 3072 → 768


def forward(ids, w, causal=True, scale=True, residual=True, keep=None):
    """ids: 토큰 ID 리스트 → logits (T, 50257).
    causal/scale/residual 을 끄면 각 장치를 뺀 모델이 된다 (실험용)."""
    ids = np.asarray(ids)
    x = w["wte.weight"][ids] + w["wpe.weight"][np.arange(len(ids))]    # 토큰 임베딩 + 위치 임베딩
    for i in range(12):
        p = f"h.{i}."
        a = attention(layer_norm(x, w[p + "ln_1.weight"], w[p + "ln_1.bias"]), w, p + "attn.", causal, scale, keep)
        x = x + a if residual else a
        m = mlp(layer_norm(x, w[p + "ln_2.weight"], w[p + "ln_2.bias"]), w, p + "mlp.")
        x = x + m if residual else m
    x = layer_norm(x, w["ln_f.weight"], w["ln_f.bias"])
    return x @ w["wte.weight"].T                                        # 출력층은 입력 임베딩 행렬을 그대로 재사용(weight tying)


# ---------------------------------------------------------------- 샘플링
def next_token(logits, rng, temperature=1.0, top_k=None, top_p=None):
    if temperature == 0:                                                # greedy
        return int(np.argmax(logits))
    z = logits / temperature
    if top_k is not None:
        kth = np.sort(z)[-top_k]
        z = np.where(z < kth, -np.inf, z)
    probs = softmax(z)
    if top_p is not None:
        order = np.argsort(-probs)
        cum = np.cumsum(probs[order])
        cut = order[cum - probs[order] >= top_p]                        # 누적확률이 p 를 넘은 '다음' 토큰부터 버림
        probs[cut] = 0
        probs /= probs.sum()
    return int(rng.choice(len(probs), p=probs))


def generate(ids, w, n, seed=0, **kw):
    # ponytail: KV 캐시 없이 매번 전체를 다시 계산. 50토큰 남짓이면 충분히 빠르다
    rng = np.random.default_rng(seed)
    ids = list(ids)
    for _ in range(n):
        t = next_token(forward(ids, w)[-1], rng, **kw)
        ids.append(t)
        if t == 50256:  # <|endoftext|>
            break
    return ids


if __name__ == "__main__":
    tok, w = BPETokenizer(), load_weights()
    ids = tok.encode("Alan Turing theorized that computers would one day become")
    out = generate(ids, w, 12, temperature=0)
    print(tok.decode(out))
    assert tok.decode(tok.encode("안녕하세요, GPT-2!")) == "안녕하세요, GPT-2!"
