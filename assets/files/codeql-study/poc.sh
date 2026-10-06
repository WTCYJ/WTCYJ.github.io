#!/bin/sh
# 각 처리기에 길이 필드만 큰 패킷을 보낸다. 실제 데이터는 몇 바이트뿐이다.
B=${1:-/tmp/pktd-asan}
echo "[E] ntohl 길이 0x1000";  printf "E\000\000\020\000AAAAAAAA" | $B 2>&1 | grep -m1 "SUMMARY" || echo "  정상 종료"
echo "[N] ntohs 길이 0x1000";  printf "N\020\000AAAAAAAA"         | $B 2>&1 | grep -m1 "SUMMARY" || echo "  정상 종료"
echo "[D] ntohs 길이 2 (2-4 언더플로)"; printf "DXX\000\002AAAAAAAA" | $B 2>&1 | grep -m1 "SUMMARY" || echo "  정상 종료"
