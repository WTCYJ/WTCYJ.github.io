"""codeql generate log-summary 결과에서 재귀 술어가 고정점까지 몇 번 돌았는지 뽑는다."""
import json, sys

txt = open(sys.argv[1]).read()
dec, i, rows = json.JSONDecoder(), 0, []
while i < len(txt):
    while i < len(txt) and txt[i].isspace():
        i += 1
    if i < len(txt):
        o, i = dec.raw_decode(txt, i)
        rows.append(o)

key = sys.argv[2] if len(sys.argv) > 2 else "NtohFlow"
print(f"{'predicate':60} {'tuples':>9} {'iter':>5} {'ms':>6}")
for r in rows:
    n = r.get("predicateName", "")
    if r.get("evaluationStrategy") == "COMPUTE_RECURSIVE" and key in n and ("fwdFlow" in n or "revFlow" in n):
        short = n.split("NtohFlow::", 1)[1].split("#")[0]
        print(f"{short:60} {r['resultSize']:>9,} {len(r['pipelineRuns']):>5} {r['millis']:>6}")
