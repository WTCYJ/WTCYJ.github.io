"""표준 쿼리 묶음 SARIF: 규칙별 개수와, 네트워크 코드에서 나온 결과만 따로 본다."""
import json, sys
from collections import Counter

rs = json.load(open(sys.argv[1]))["runs"][0]["results"]
print(f"전체 {len(rs)}건, 규칙 상위 8개:")
for k, v in Counter(r["ruleId"] for r in rs).most_common(8):
    print(f"  {v:3} {k}")
print("net/, drivers/net/ 에서 나온 결과:")
for r in rs:
    l = r["locations"][0]["physicalLocation"]
    u = l["artifactLocation"]["uri"]
    if u.startswith(("net/", "drivers/net/")):
        print(f"  {r['ruleId']:42} {u}:{l['region']['startLine']}")
