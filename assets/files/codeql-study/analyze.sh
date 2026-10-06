#!/bin/bash
# 사용: analyze.sh DB 쿼리.ql [소스루트] -> 경로 문제 결과를 한 줄씩 요약
export PATH=~/tools/codeql:$PATH
out=/tmp/$(basename "$2" .ql).sarif
codeql database analyze "$1" "$2" --format=sarif-latest -o "$out" >/tmp/analyze.log 2>&1 || { tail -5 /tmp/analyze.log; exit 1; }
python3 /mnt/c/Users/yejun/codeql-study/sarif_summary.py "$out" ${3:-}
