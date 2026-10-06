"""SARIF 결과를 '싱크 위치 <- 소스 위치' 한 줄씩 요약한다.

사용: sarif_summary.py 결과.sarif [소스루트]
소스루트를 주면 각 위치를 감싸는 함수 이름을 같이 찍는다.
"""
import json, re, sys

root = sys.argv[2] if len(sys.argv) > 2 else None
FUNC = re.compile(r"^[A-Za-z_].*?\b(\w+)\s*\(")


def where(uri, line):
    if not root:
        return f"{uri}:{line}"
    with open(f"{root}/{uri}", errors="replace") as f:
        lines = f.readlines()[:line]
    # ponytail: 열 0에서 시작하는 '이름(' 줄을 함수 정의로 본다. K&R 스타일이나 매크로 정의는 틀릴 수 있다.
    name = next((m.group(1) for l in reversed(lines) if (m := FUNC.match(l))), "?")
    return f"{uri}:{line} {name}()"


rows = []
for run in json.load(open(sys.argv[1]))["runs"]:
    for r in run["results"]:
        p = r["locations"][0]["physicalLocation"]
        sink = where(p["artifactLocation"]["uri"], p["region"]["startLine"])
        s = r["relatedLocations"][0]["physicalLocation"]
        src = where(s["artifactLocation"]["uri"], s["region"]["startLine"])
        rows.append((sink, src))
w = max((len(a) for a, _ in rows), default=0)
for sink, src in sorted(rows):
    print(f"{sink:{w}}  <-  {src}")
print(f"({len(rows)}건)")
