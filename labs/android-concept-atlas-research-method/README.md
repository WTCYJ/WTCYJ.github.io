# Android Concept Atlas research-method harness

실제 제품 취약점이나 공격 코드를 사용하지 않고, 정수 길이 검사의 패치 전·후 차이를 전용 Android Emulator에서 검증하는 교육용 하네스입니다.

- `length_check_before.c`: `offset + length`가 먼저 계산되어 signed overflow가 가능한 대조군
- `length_check_after.c`: `length <= total - offset` 순서로 바꿔 overflow 없이 범위를 검사하는 수정본
- `run-matrix.ps1`: 정상·경계·범위초과·오버플로 입력을 두 바이너리에 동일하게 투입

성공 기준은 취약 대조군에서 UBSan이 오버플로를 탐지하고, 수정본이 같은 입력을 정상적으로 `REJECT`하는 것입니다.
