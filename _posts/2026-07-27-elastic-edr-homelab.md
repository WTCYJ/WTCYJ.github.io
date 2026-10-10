---
layout: post
title: "Elastic EDR 홈랩 직접 구축기 — Docker 스택부터 Elastic Defend 탐지 분석까지"
date: 2026-07-27
category: 블로그/기술문서
author: SeiKa
tags: [Elastic, EDR, ElasticDefend, Fleet, Elasticsearch, Kibana, ElasticAgent, DetectionEngineering, MITRE, ATT&CK, Windows, Docker, 홈랩, BlueTeam]
excerpt: "Elasticsearch·Kibana·Fleet Server를 Docker로 올리고 Windows 호스트에 Elastic Agent + Elastic Defend를 붙여 EDR 홈랩을 구축한 뒤, 비파괴 공격 시뮬레이션으로 탐지 동작을 실측하고 '무엇이 잡히고 무엇이 안 잡혔는지'까지 분석한 기록."
---

> **Elastic Stack**으로 EDR 환경을 처음부터 직접 구축하고, 내 Windows PC를 엔드포인트로 등록한 뒤
> 비파괴 공격 기법을 실행해 **실제로 어떤 이벤트가 수집되고 어떤 룰이 발화하는지**를 측정한 기록입니다.
>
> 구축 매뉴얼을 따라가는 글이 아니라, **막힌 지점과 그걸 어떻게 풀었는지**, 그리고
> **탐지되지 않은 것들이 왜 탐지되지 않았는지**에 무게를 뒀습니다.
>
> **환경**: Elastic Stack 9.4.4 · Elastic Defend(endpoint) 9.4.1 · Docker 29.2.1 / Compose v5.0.2 · Windows 11 (26200)

---

## 1. 왜 EDR을 직접 구축하는가

EDR을 "쓰는" 것과 "이해하는" 것은 다릅니다. 상용 제품의 콘솔은 이미 잘 정제된 알림만 보여주기 때문에,
그 알림이 **어떤 원시 이벤트로부터, 어떤 룰을 거쳐, 왜 저 심각도로** 만들어졌는지는 보이지 않습니다.

Elastic Security는 그 파이프라인 전체가 열려 있습니다.

- **Elastic Defend**가 커널 드라이버로 프로세스·파일·레지스트리·네트워크·DLL 로드·API 호출을 수집하고
- **Elastic Agent**가 그걸 **Fleet Server**를 거쳐 **Elasticsearch**로 밀어넣고
- **Detection Engine**이 그 위에서 룰을 주기적으로 돌려 알림을 만들고
- **Kibana Security**가 그걸 ATT&CK 기준으로 보여줍니다

각 단을 직접 세워보면 "EDR이 못 보는 것"이 어디서 생기는지가 손에 잡힙니다. 이 글의 후반부(6~7장)가 사실상 그 얘기입니다.

### 구성도

```
┌─────────────────────────── Windows 11 호스트 (엔드포인트 겸 도커 호스트) ───────────────────────────┐
│                                                                                                    │
│   Elastic Agent (서비스)                              Docker Desktop (WSL2)                        │
│     ├─ ElasticEndpoint 서비스                          ┌──────────────────────────────────────┐    │
│     │   └─ elastic-endpoint-driver.sys  ← 커널         │  ecp-elasticsearch  :9200 (TLS)      │    │
│     │      ElasticElam.sys              ← ELAM         │  ecp-kibana         :5601 (TLS)      │    │
│     ├─ winlog (Security/System/App)                    │  ecp-fleet-server   :8220 (TLS)      │    │
│     └─ system/metrics                                  └──────────────────────────────────────┘    │
│            │                                                        ▲                              │
│            └──── enroll: https://localhost:8220 ────────────────────┘                              │
│            └──── ship  : https://localhost:9200 ────────────────────┘                              │
└────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

엔드포인트와 스택이 같은 물리 머신에 있는 구성입니다. 실무에서는 절대 이렇게 두지 않지만
(공격자가 호스트를 잡으면 로그 저장소까지 같이 잡힙니다), 홈랩에서는 네트워크 변수가 사라져서
**문제가 생겼을 때 원인이 한 곳으로 좁혀지는** 장점이 있습니다.

---

## 2. 스택 구축 — elastic-container 프로젝트

Elastic이 공식 소개하는 [The Elastic Container Project](https://www.elastic.co/security-labs/the-elastic-container-project)
(`peasead/elastic-container`)를 베이스로 잡았습니다. 자체 CA를 만들어 ES·Kibana·Fleet Server용 인증서를
발급하고, 전 구간 TLS로 묶어주는 compose 세트입니다.

`.env`에서 실질적으로 손대야 하는 값들:

```bash
STACK_VERSION=9.4.4
ELASTIC_PASSWORD=<changeme 아님>
KIBANA_PASSWORD=<changeme 아님>
LICENSE=trial          # basic이면 Defend의 예방 기능 상당수가 잠김
WindowsDR=1            # Windows 태그 프리빌트 룰 일괄 활성화
MEM_LIMIT=4294967296   # 기본 2GB는 룰 2천 개 돌리기엔 빠듯
```

`LICENSE`를 `trial`로 둔 이유가 큽니다. `basic`에서는 Elastic Defend가 **텔레메트리 수집기**에 가깝고,
악성코드·랜섬웨어·메모리 보호 같은 EDR다운 기능은 Platinum 이상에서 열립니다. 30일 트라이얼이면
Enterprise 상당 기능을 다 볼 수 있어서, 학습 목적에는 이쪽이 맞습니다.

### 삽질 ①: Docker 데몬이 아예 안 뜸

시작부터 막혔습니다. Docker Desktop을 실행하면 백엔드가 조용히 죽고 데몬 파이프가 안 생깁니다.
`com.docker.backend.exe.log`를 열어보니 원인이 명확했습니다.

```
backend crashed: starting services: initializing Inference manager:
  listening on unix://<HOME>\AppData\Local\Docker\run\dockerInference:
  remove ...\dockerInference: The file cannot be accessed by the system.
```

이전에 Docker가 비정상 종료되면서 남긴 **AF_UNIX 소켓 reparse point가 유령 파일**이 된 상태입니다.
`ls`에는 보이는데 열 수도, 지울 수도 없습니다. 개별 파일 삭제가 안 되니 **상위 디렉터리를 통째로 rename**하면
풀립니다 — 디렉터리 리네임은 자식 핸들이 필요 없기 때문입니다.

```powershell
Get-Process *ocker* | Stop-Process -Force
Rename-Item "$env:LOCALAPPDATA\Docker\run" "run.bak"
Rename-Item "$env:LOCALAPPDATA\docker-secrets-engine" "docker-secrets-engine.bak"
# 폴더는 Docker가 재시작하며 자동으로 다시 만듭니다
```

### 삽질 ②: `elastic-container.sh`는 Windows에서 안 돕니다

이 프로젝트의 구동 스크립트는 bash 전용이고, Git Bash에서 돌려도 두 군데서 걸립니다.

**첫째, `jq` 의존.** `check_required_apps()`가 `jq`와 `curl`을 요구하는데 Git Bash에는 `jq`가 없습니다.

**둘째, 호스트 IP 판별.**

```bash
get_host_ip() {
  os=$(uname -s)
  if [ "${os}" == "Linux" ]; then   ipvar=$(hostname -I | awk '{print $1}')
  elif [ "${os}" == "Darwin" ]; then ipvar=$(ifconfig en0 | awk '$1=="inet" {print $2}')
  fi
}
```

Git Bash의 `uname -s`는 `MINGW64_NT-10.0-26200`을 반환합니다. 두 분기 모두 안 타므로 `ipvar`가
초기값 `0.0.0.0`으로 남고, 결과적으로 Fleet 서버 주소와 ES 출력이 `https://0.0.0.0:8220`,
`https://0.0.0.0:9200`으로 등록됩니다. 에이전트는 여기에 붙을 수 없습니다.

`jq`를 새로 깔고 스크립트를 패치하는 대신, **스택 기동 이후의 설정 단계를 PowerShell로 다시 구현**했습니다.
PowerShell 5.1의 `Invoke-RestMethod`에는 `-SkipCertificateCheck`가 없어서 자체 서명 CA를 만나면 곤란한데,
`curl.exe -k`로 요청하고 `ConvertFrom-Json`으로 파싱하면 깔끔하게 우회됩니다.

```powershell
function Invoke-Kbn {
    param([string]$Method='GET', [string]$Path, $Body)
    $args = @('-sk','-X',$Method,'-u',"${USER}:${PASS}",
              '-H','kbn-xsrf: kibana','-H','Content-Type: application/json')
    if ($Body) {
        $tmp = [IO.Path]::GetTempFileName()
        [IO.File]::WriteAllText($tmp, ($Body|ConvertTo-Json -Depth 20 -Compress),
                                (New-Object Text.UTF8Encoding($false)))   # BOM 없는 UTF-8 필수
        $args += @('--data-binary', "@$tmp")
    }
    ((& curl.exe @args "$KBN$Path") -join "`n") | ConvertFrom-Json
}
```

`UTF8Encoding($false)`가 포인트입니다. PowerShell의 기본 UTF-8 출력은 BOM을 붙이는데,
BOM이 앞에 붙은 JSON을 Kibana API에 던지면 파싱 에러가 납니다.

이 스크립트로 탐지 엔진 초기화 → 프리빌트 룰 설치 → Windows 룰 일괄 활성화까지 자동화했습니다.
9.4.4 기준 프리빌트 룰은 **2,026개**가 설치되고, 그중 Windows 태그가 붙은 **628개**가 켜집니다.

---

## 3. Fleet 설정 — 컨테이너와 호스트가 같은 주소를 볼 수 없다는 문제

여기서 이 랩 구성 특유의 함정이 나옵니다.

Fleet의 기본 ES 출력을 `https://localhost:9200`으로 잡으면 **Windows 호스트의 에이전트**는 잘 붙습니다.
컨테이너가 9200을 호스트로 publish 하고 있고, 인증서 SAN에도 `localhost`와 `127.0.0.1`이 들어 있으니까요.

그런데 **fleet-server 컨테이너 자신도 같은 기본 출력을 씁니다.** 컨테이너 안에서 `localhost:9200`은
자기 자신이므로 연결이 거부됩니다.

```
Recoverable: Elasticsearch request failed: dial tcp 127.0.0.1:9200: connect: connection refused
```

Fleet에서 에이전트가 `degraded`로 뜨고, 컴포넌트를 까보면 `fleet-server` 본체는 HEALTHY인데
자기 모니터링용 `filestream-monitoring`, `beat/metrics-monitoring`만 죽어 있습니다.

원본 스크립트는 호스트의 LAN IP를 써서 이 문제를 피합니다(컨테이너에서도 도커 브리지를 통해 LAN IP로
호스트 publish 포트에 닿습니다). 다만 인증서 SAN에 LAN IP가 없어서 `ssl.verification_mode: certificate`로
호스트명 검증을 꺼야 하는 트레이드오프가 붙습니다.

저는 대신 **정책별 출력 분리**로 풀었습니다. 트라이얼(Enterprise 상당)에서는 정책마다 다른 출력을 지정할 수 있습니다.

```powershell
# 컨테이너 전용 출력: 도커 내부 DNS 이름 사용
POST /api/fleet/outputs
{ "id":"internal-docker-output", "type":"elasticsearch",
  "hosts":["https://ecp-elasticsearch:9200"],
  "ca_trusted_fingerprint":"<CA sha256>",
  "config_yaml":"ssl.verification_mode: certificate" }

# fleet-server 정책만 이 출력을 쓰도록
PUT /api/fleet/agent_policies/fleet-server-policy
{ "data_output_id":"internal-docker-output",
  "monitoring_output_id":"internal-docker-output" }
```

기본 출력(`https://localhost:9200`)은 Windows 엔드포인트가 그대로 쓰고, 컨테이너만 내부 DNS로 보냅니다.
적용 직후 fleet-server 에이전트가 `online`으로 돌아옵니다.

`ca_trusted_fingerprint`는 CA 인증서 **DER의 SHA-256**입니다. openssl 없이 PowerShell로 뽑을 수 있습니다.

```powershell
docker cp ecp-elasticsearch:/usr/share/elasticsearch/config/certs/ca/ca.crt .\ca.crt
$cert = New-Object Security.Cryptography.X509Certificates.X509Certificate2 .\ca.crt
(([Security.Cryptography.SHA256]::Create().ComputeHash($cert.RawData)) |
    ForEach-Object { $_.ToString('x2') }) -join ''
```

---

## 4. Elastic Defend 통합 — `prevent`를 `detect`로 내린 이유

에이전트 정책에 Elastic Defend를 붙일 때 `EDRComplete` 프리셋을 썼습니다. 그런데 이 프리셋의 기본값을
확인해 보면 보호 기능이 전부 **차단 모드**입니다.

```
malware            mode=prevent
ransomware         mode=prevent
memory_protection  mode=prevent
behavior_protection mode=prevent
```

이 랩의 엔드포인트는 제 주력 PC입니다. `prevent`는 탐지에서 끝나지 않고 **프로세스를 죽이고 파일을
격리**합니다. 오탐 한 번이 작업 중이던 프로그램을 날릴 수 있고, 무엇보다 공격 시뮬레이션이 중간에
차단되면 "이 기법이 어떤 텔레메트리를 남기는가"를 관찰할 수 없습니다.

그래서 네 항목을 전부 `detect`로 내렸습니다. **텔레메트리와 알림은 그대로 받고 차단만 하지 않는** 구성입니다.

패키지 정책 PUT에서 한 번 걸렸는데, `inputs[0].config`에서 `policy.value`만 보내면 거부됩니다.

```
Invalid Elastic Defend security policy.
'inputs[0].config.policy.value' and 'inputs[0].config.artifact_manifest.value' are required.
```

`artifact_manifest`(전역 예외·신뢰 목록의 매니페스트)까지 같이 보내야 하므로, GET으로 받은 `config`
블록을 통째로 유지하고 그 안의 `policy.value`만 수정해서 되돌려주는 방식으로 처리했습니다.

---

## 5. 에이전트 설치와 등록 — 조용히 실패하는 enroll

```powershell
elastic-agent.exe install --non-interactive `
  --url=https://localhost:8220 `
  --enrollment-token=<token> `
  --certificate-authorities=C:\...\ca.crt
```

`--certificate-authorities`로 자체 CA를 명시했습니다. `--insecure`로 검증을 통째로 끄는 것보다
"자체 CA를 신뢰하되 검증은 한다"가 실제 사내 배포와 가까운 형태입니다.

설치는 성공했습니다. 서비스가 올라오고 `.installed`, `fleet.enc`, `vault\`가 생성됩니다.
그런데 **Fleet에는 이 호스트가 나타나지 않았습니다.** 설치 로그는 `Waiting For Enroll...`에서 멈춰 있고,
fleet-server 컨테이너 로그를 뒤져도 이 호스트발 enrollment 요청 자체가 없습니다.

여기서 진단이 한 번 더 막힙니다. `elastic-agent status`도, 에이전트 로그 디렉터리도 **Administrators로
ACL이 걸려 있어** 일반 권한으로는 못 읽습니다.

```
Error: failed to communicate with Elastic Agent daemon:
  open \\.\pipe\elastic-agent-system: Access is denied.
```

그래서 관리자 권한으로 ① `status --output json` ② 로그 tail ③ 미등록이면 `enroll --force -v` 재시도를
**전부 파일로 덤프**하는 진단 스크립트를 따로 만들어 돌렸습니다(승격된 콘솔은 순식간에 닫혀서 화면으로는
읽을 수가 없습니다). 결과:

```json
{"message":"Starting enrollment to URL: https://localhost:8220/"}
{"message":"Restarting agent daemon, attempt 0"}
Successfully enrolled the Elastic Agent.
exit=0
```

**재시도는 2초 만에 성공했습니다.** 즉 주소·토큰·CA는 처음부터 전부 맞았고, `install`이 서비스를 띄운
직후 진행하는 최초 enroll의 타이밍 문제였습니다. Fleet Server가 방금 정책 변경(출력 재지정)을 받아
재적용하는 중이었을 가능성이 큽니다.

> **교훈**: `elastic-agent install`이 `Waiting For Enroll...`에서 굳었다면 설치를 되돌릴 필요 없습니다.
> 서비스는 이미 정상이므로 **`elastic-agent enroll --force`만 다시** 때리면 됩니다.

#### 곁다리: `curl --cacert`가 실패해서 잠깐 헤맨 것

중간에 호스트에서 `curl --cacert ca.crt https://localhost:8220/api/status`가 exit 60(인증서 검증 실패)로
떨어져서 CA 발급이 잘못됐나 의심했습니다. 인증서를 까보니 SAN은 멀쩡했습니다.

```
Subject Alternative Name:
  DNS Name = ecp-fleet-server
  DNS Name = localhost
  IP Address = 127.0.0.1
```

원인은 **Windows에 내장된 curl이 Schannel 백엔드**라는 점이었습니다. Schannel은 `--cacert`로 넘긴
CA를 임시 신뢰 앵커로 잡아주지 않아서, Windows 인증서 저장소에 없는 사설 CA는 검증에 실패합니다.
`-k`를 붙이면 200이 정상적으로 옵니다. Go로 작성된 Elastic Agent는 자체 TLS 스택을 쓰므로 이 제약과
무관합니다. **호스트 curl의 검증 실패를 에이전트의 문제로 오해하면 안 됩니다.**

설치가 끝나면 커널 컴포넌트가 실제로 배치된 것을 확인할 수 있습니다.

```
Elastic Agent      Running   Automatic
ElasticEndpoint    Running   Automatic

C:\Windows\System32\drivers\elastic-endpoint-driver.sys   207,696 bytes
C:\Windows\System32\drivers\ElasticElam.sys                17,888 bytes
```

`ElasticElam.sys`는 ELAM(Early Launch Anti-Malware) 드라이버로, 부팅 초기에 로드되어
부트킷류가 EDR보다 먼저 자리 잡는 것을 막는 역할입니다.

---

## 6. 공격 시뮬레이션 — 무엇을, 왜 그것만 실행했나

시뮬레이션 원칙을 먼저 정했습니다. **되돌릴 수 없는 것과 보안을 낮추는 것은 넣지 않는다.**

그래서 EDR 테스트에 흔히 등장하는 아래 항목들은 의도적으로 제외했습니다.

| 흔한 테스트 | 제외 이유 |
|---|---|
| `vssadmin delete shadows` | 섀도 카피는 복구 수단입니다. 되돌릴 수 없음 |
| `wevtutil cl Security` | 이벤트 로그 삭제 = 증적 파괴 |
| Defender 실시간 보호 해제 / 예외 추가 | 실제로 방어를 약화시킴 |
| 실제 악성 샘플 | 주력 PC에서 실행할 이유가 없음 |

실행한 것은 다음과 같습니다. 레지스트리 값·예약 작업·임시 파일은 스크립트 끝에서 전부 되돌립니다.

| 기법 | ATT&CK | 내용 |
|---|---|---|
| 정찰 버스트 | T1087.001 / T1082 / T1016 / T1057 | `whoami /priv`·`net user`·`net localgroup administrators`·`systeminfo`·`arp -a`·`tasklist /svc` 연속 실행 |
| 인코딩 PowerShell | T1059.001 / T1027 | `-WindowStyle Hidden -EncodedCommand <base64>` |
| 다운로드 크래들 | T1105 | `(New-Object Net.WebClient).DownloadString(...)` |
| Run 키 지속성 | T1547.001 | `HKCU\...\CurrentVersion\Run`에 값 추가 |
| 리네임 LOLBin | T1036.003 | `cmd.exe`를 `%TEMP%\svchost.exe`로 복사 후 실행 |
| WMI 프로세스 생성 | T1047 | `Win32_Process.Create` |
| EICAR | T1204.002 | 안티멀웨어 테스트 문자열 파일 생성 |

### 삽질 ③: 시뮬레이션 스크립트를 AMSI가 먼저 막았다

스크립트를 실행하자 **파일이 파싱조차 되지 않았습니다.**

```
This script contains malicious content and has been blocked by your antivirus software.
    + FullyQualifiedErrorId : ScriptContainedMaliciousContent
```

AMSI가 `.ps1` **내용**을 스캔해서 거부한 것입니다. 원인은 파일 안에 그대로 박혀 있던 문자열들이었습니다.

- EICAR 테스트 문자열 (파일에 리터럴로 존재하는 순간 그 파일이 곧 시그니처 매치)
- `rundll32 javascript:"\..\mshtml,RunHTMLApplication ...` (알려진 프록시 실행 패턴)
- `comsvcs.dll, MiniDump` (LSASS 덤프 패턴)
- `New-Object Net.WebClient).DownloadString`

문자열을 런타임에 조립하도록 바꾸니 통과했습니다.

```powershell
# 파일에 리터럴로 두면 이 스크립트 자체가 시그니처 매치가 됩니다
$s = ('X5O!P%@AP[4\PZX54(P^)7CC)7}$EI','CAR-STANDARD-ANTIVIRUS-TE','ST-FILE!$H+H*') -join ''
```

이건 우회 기법 자랑이 아니라 **AMSI가 실제로 어느 레이어에서 동작하는지**를 보여주는 사례입니다.
AMSI는 스크립트를 실행 엔진에 넘기기 전에 원문을 본다 — 즉 **디스크의 문자열**을 보는 것이지
행위를 보는 게 아닙니다. 그래서 리터럴만 쪼개도 통과합니다. 반대로 말하면,
**실제 행위를 보는 EDR 레이어(Elastic Defend)는 이 조립 트릭에 전혀 영향받지 않았습니다.**
뒤에서 보듯 조립된 페이로드가 실행되는 순간 그대로 잡힙니다.

---

## 7. 탐지 결과 분석

측정 창에서 Detection Engine이 만든 알림은 **19개 룰에서 36건**, 그중 Elastic Defend의
행위 기반 엔진(`logs-endpoint.alerts`)이 직접 올린 것이 **4건(전부 critical / risk 99)** 입니다.

### 7-1. 가장 잘 잡힌 것 — 리네임된 서명 바이너리

`cmd.exe`를 `%TEMP%\svchost.exe`로 복사해서 실행한 것 하나에 **독립된 룰 3개가 동시에** 걸렸습니다.

```
rule     : Potential Masquerading as SVCHOST
exe      : C:\Users\yejun\AppData\Local\Temp\edrlab\svchost.exe
cmdline  : "...\edrlab\svchost.exe /c "whoami & echo EDRLAB masquerade"
sha256   : 65ec268add3973b6dca64222985da47caeaee44a340b0ec1466782914fd743d9
signature: subject=Microsoft Windows  trusted=True  status=trusted
parent   : C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe
```

여기가 이 실습에서 가장 흥미로운 지점입니다. **이 바이너리는 서명이 유효합니다.**
진짜 Microsoft가 서명한 진짜 `cmd.exe`이므로 `trusted=True`가 정직하게 찍혀 있습니다.
서명만 보는 방어라면 100% 통과합니다.

Elastic Defend가 잡아낸 건 서명이 아니라 **맥락의 불일치**입니다.

1. `svchost.exe`라는 이름인데 해시가 진짜 `svchost.exe`가 아니다 → *Potential Masquerading as SVCHOST*
2. 서명된 시스템 바이너리가 원래 경로가 아닌 `%TEMP%`에서 실행됐다 → *Binary Masquerading via Untrusted Path*
3. 서명된 바이너리가 이름만 바꿔 프록시 실행에 쓰였다 → *Execution via Renamed Signed Binary Proxy*

같은 사건을 세 각도에서 독립적으로 본 것이고, 하나를 우회해도 나머지가 남습니다.
**"서명 = 신뢰"가 아니라 "이름 + 경로 + 해시 + 부모 프로세스의 조합"이 판단 근거**라는 걸
실제 알림 문서로 확인한 셈입니다.

### 7-2. 저심각도의 누적 — 정찰 버스트

개별로는 `low / risk 21`짜리 알림들이지만, 짧은 시간에 겹쳐서 발화합니다.

```
Windows Account or Group Discovery              (whoami /priv, whoami /groups, net user, net localgroup administrators)
Enumeration of Administrator Accounts           (net localgroup administrators)
Enumeration of Privileged Local Groups Membership  [medium]
Windows System Information Discovery            (systeminfo)
Windows System Network Connections Discovery    (net user)
Remote System Discovery Commands                (arp -a)
Process Discovery Using Built-in Tools          (tasklist /svc)
Unusual Discovery Signal Alert with Unusual Process Command Line
```

여기서 눈여겨볼 룰이 `Unusual Discovery Signal Alert...`입니다. 개별 명령이 아니라
**"짧은 구간에 정찰 계열 알림이 비정상적으로 몰렸다"는 사실 자체**를 입력으로 삼는 상위 룰입니다.
`whoami` 한 번은 정상이지만 `whoami; net user; net localgroup; systeminfo; arp -a`가
30초 안에 연달아 나오는 건 사람의 작업 패턴이 아닙니다. 개별 low 알림을 하나씩 보면 전부 노이즈로
치우게 되지만, 상관 룰이 그 위에 한 겹 있으면 묶여서 올라옵니다.

### 7-3. 탐지되지 않은 것들 — 이쪽이 더 중요합니다

**Run 키 지속성(T1547.001)은 알림이 발화하지 않았고, 원시 텔레메트리에도 남지 않았습니다.**

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Run 관련 registry 이벤트 : 0건
```

같은 시간대에 레지스트리 이벤트 자체는 수집되고 있습니다(측정 창에서 192건, `event.action`은
`modification` 180 / `query` 8). `reg.exe` 프로세스 실행 이벤트도 정상적으로 남아 있습니다.
즉 **레지스트리 채널은 켜져 있는데 이 키의 쓰기가 이벤트로 올라오지 않았습니다.**

수집된 레지스트리 이벤트의 발생 프로세스를 보면 `svchost.exe` 158건, `explorer.exe` 13건 식으로
시스템 프로세스에 몰려 있습니다. Elastic Defend는 볼륨 폭발을 막기 위해 레지스트리 이벤트를
**기본적으로 상당히 좁게 필터링**하는데, 이 구성에서는 `HKCU`의 Run 키 쓰기가 그 필터를 통과하지
못한 것으로 보입니다.

무엇을 뜻하느냐 — **"EDR을 깔았으니 다 보인다"가 틀렸다**는 겁니다.
가장 고전적인 지속성 기법 하나가, 기본 설정에서 알림은커녕 원시 이벤트로도 남지 않았습니다.
실무라면 여기서 Sysmon(Event ID 13)을 병행 수집하거나, Defend의 이벤트 필터를 명시적으로
넓히는 선택을 해야 합니다. **탐지 커버리지는 제품을 설치한 시점이 아니라 이런 검증을 한 뒤에야 알 수 있습니다.**

**EICAR도 악성코드 알림을 만들지 않았습니다.** 파일은 디스크에 그대로 남았습니다
(Windows Defender 실시간 보호도 켜져 있는 상태였습니다). Elastic Defend의 malware 보호는
PE 파일에 대한 ML 모델 기반이라, 68바이트짜리 비-PE 텍스트 파일인 EICAR은 애초에 채점 대상이
아닙니다. **EICAR이 안 잡힌다고 EDR이 고장난 게 아니라, EICAR이 EDR의 테스트 도구가 아닌 것입니다.**
AV 시그니처 엔진 테스트용 문자열을 EDR 행위 엔진 검증에 쓰면 안 됩니다.

### 7-4. 랩 자신이 남긴 알림 — 덤으로 얻은 교훈 둘

**하나. 자격증명이 EDR 텔레메트리에 그대로 박힙니다.**

```
rule    : Potential File Transfer via Curl for Windows
process : curl.exe  (parent=powershell.exe)
cmdline : "C:\windows\system32\curl.exe -sk -u elastic:<비밀번호가 여기 그대로> https://localhost:5601/api/...
```

스택을 설정하느라 제가 돌린 `curl -u user:pass` 명령들이 전부 탐지되었고,
**명령줄에 넣은 비밀번호가 Elasticsearch에 평문으로 색인**되었습니다. EDR을 붙인다는 건
"명령줄에 비밀 정보를 넣는 모든 습관이 중앙 로그에 영구 기록된다"는 뜻입니다.
운영 환경이라면 이것만으로 사고가 됩니다. 자격증명은 환경변수나 파일로 넘기고,
`.env`·`lab-info.json` 같은 산출물은 공개 저장소에 올리기 전에 반드시 걸러야 합니다.

**둘. AI 코딩 도구도 탐지 대상입니다.**

```
rule: GenAI CLI Started with Unsafe Permission Bypass   [medium / risk 47]
```

권한 확인을 생략하는 옵션으로 기동된 GenAI CLI를 잡는 프리빌트 룰이 이미 존재하고,
실제로 발화했습니다. 개발 편의로 켜는 옵션이 블루팀 관점에서는 이미 탐지 대상이 되어 있다는 뜻입니다.

### 7-5. 수집량

| 데이터 스트림 | 문서 수 |
|---|---:|
| `logs-system.security` | 34,466 |
| `logs-endpoint.events.file` | 10,471 |
| `logs-endpoint.events.process` | 2,771 |
| `logs-system.system` | 2,538 |
| `logs-endpoint.events.library` | 1,607 |
| `logs-endpoint.events.network` | 1,405 |
| `logs-system.application` | 1,045 |
| `logs-endpoint.events.registry` | 192 |
| `logs-endpoint.events.api` | 74 |
| `logs-endpoint.events.security` | 36 |
| `logs-endpoint.alerts` | 4 |

엔드포인트 1대, 약 한 시간입니다. 파일 이벤트가 프로세스 이벤트의 4배가 조금 안 되고,
레지스트리는 192건에 불과합니다. 이 비대칭이 앞서 본 Run 키 미탐지와 정확히 같은 얘기입니다 —
**볼륨 관리를 위해 레지스트리 채널이 강하게 눌려 있습니다.** 엔드포인트가 수백 대로 늘었을 때
어떤 채널을 살리고 어떤 채널을 포기할지가 곧 탐지 설계라는 게 숫자로 보입니다.

---

## 8. 정리

구축 자체보다 **막힌 지점을 뚫는 과정**에서 배운 게 많았습니다.

- Docker 유령 소켓은 **상위 디렉터리 rename**으로 푼다 (개별 파일 삭제 불가)
- Windows에서 `elastic-container.sh`는 그대로 안 돈다 — `jq` 의존과 `uname -s` 분기 때문.
  스택 기동만 compose에 맡기고 **설정 단계는 PowerShell + `curl.exe -k`로 재구현**하는 게 빠르다
- 컨테이너와 호스트가 같은 스택을 볼 때는 **정책별 출력 분리**가 깔끔하다
- `install`의 최초 enroll이 굳으면 **`enroll --force`만 다시** — 재설치 불필요
- Windows 내장 curl은 **Schannel**이라 `--cacert`가 기대대로 동작하지 않는다. 도구의 한계를
  대상 시스템의 문제로 오해하지 말 것
- 주력 PC를 엔드포인트로 쓸 땐 **`prevent` → `detect`** 로 내려야 관찰이 가능하다

탐지 쪽에서 남은 결론은 하나입니다.
**EDR을 설치하는 것과 EDR이 그 기법을 본다는 것은 별개입니다.**
리네임된 서명 바이너리는 세 개 룰이 동시에 잡아냈지만, 가장 고전적인 Run 키 지속성은 알림은 물론
원시 이벤트조차 남지 않았습니다. 어느 쪽도 문서를 읽어서는 알 수 없고, 직접 기법을 실행하고
인덱스를 조회해봐야만 알 수 있습니다. 홈랩을 세우는 진짜 이유가 여기에 있다고 생각합니다.

### 남은 것

certutil 다운로더(T1105), 예약 작업 지속성(T1053.005), mshta/rundll32 프록시 실행(T1218)은
자동화 환경 제약으로 이번 측정에 포함하지 못했습니다. 특히 예약 작업은 Windows 보안 이벤트
4698과 Defend 프로세스 이벤트 양쪽에 남아야 정상이므로, Run 키와 비교해 **어떤 지속성 기법이
기본 설정에서 실제로 보이는지** 확인하기 좋은 대상입니다. 이어서 측정해 볼 계획입니다.

---

## 참고

- [The Elastic Container Project](https://www.elastic.co/security-labs/the-elastic-container-project) — Elastic Security Labs
- [peasead/elastic-container](https://github.com/peasead/elastic-container) — 구축에 사용한 compose 세트
- [Elastic Defend 문서](https://www.elastic.co/docs/solutions/security/configure-elastic-defend)
- [Elastic 프리빌트 탐지 룰 저장소](https://github.com/elastic/detection-rules)
