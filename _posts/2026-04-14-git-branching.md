---
layout: post
title: "Learn Git Branching 완전 정복 — 명령어 총정리"
date: 2026-04-14
category: 개발
author: WTCY
tags: [git, branch, rebase, cherry-pick, remote]
---

> [learngitbranching.js.org](https://learngitbranching.js.org/)를 풀면서 배운 Git 명령어를 정리했습니다.

---


## 목차

1. [커밋과 히스토리](#1-커밋과-히스토리)
2. [브랜치](#2-브랜치)
3. [병합 — merge](#3-병합--merge)
4. [리베이스 — rebase](#4-리베이스--rebase)
5. [HEAD와 상대 참조](#5-head와-상대-참조)
6. [히스토리 수정 — reset, revert, cherry-pick](#6-히스토리-수정--reset-revert-cherry-pick)
7. [원격 저장소](#7-원격-저장소)
8. [고급 명령어](#8-고급-명령어)

---

## 1. 커밋과 히스토리

Git의 가장 기본 단위는 **커밋(commit)**입니다. 커밋은 프로젝트의 스냅샷을 저장하며, 각 커밋은 고유한 해시값(SHA-1)을 가집니다. 커밋은 이전 커밋을 가리키는 포인터를 포함하고, 이 연결이 쌓여 히스토리 트리가 만들어집니다.

```bash
# 변경사항을 스테이징하고 커밋
git add .
git commit -m "메시지"

# add와 commit을 한 번에 (이미 추적 중인 파일만)
git commit -am "메시지"
```

---

## 2. 브랜치

브랜치는 특정 커밋을 가리키는 **가벼운 포인터**입니다. 새 브랜치를 만들어도 실제 파일이 복사되지 않기 때문에 생성 비용이 거의 없습니다.

| 명령어 | 설명 |
|---|---|
| `git branch 이름` | 새 브랜치 생성 |
| `git switch 이름` | 브랜치 이동 (최신 문법) |
| `git checkout -b 이름` | 생성 + 이동을 한 번에 |
| `git branch -d 이름` | 브랜치 삭제 |

```bash
# 현재 브랜치 목록 확인
git branch

# 생성과 동시에 이동
git switch -c feature/login
```

---

## 3. 병합 — merge

두 브랜치의 작업을 합칩니다. `merge`는 두 브랜치의 공통 조상을 기준으로 새로운 **병합 커밋**을 만듭니다.

```bash
# main 브랜치에서 feature를 병합
git switch main
git merge feature/login
```

**Fast-forward란?** feature 브랜치가 main보다 앞에 있고 main에 새 커밋이 없다면, 포인터만 앞으로 이동합니다. 이 경우 별도의 병합 커밋이 생기지 않습니다.

---

## 4. 리베이스 — rebase

`rebase`는 커밋들을 다른 브랜치 위로 **재배치**합니다. merge와 달리 히스토리가 일직선으로 정리됩니다.

```bash
# feature 브랜치를 main 위로 이동
git switch feature/login
git rebase main
```

> **주의:** 이미 원격에 푸시한 커밋은 rebase하지 마세요. 커밋 해시가 바뀌어 협업자와 충돌이 발생합니다.

---

## 5. HEAD와 상대 참조

HEAD는 현재 체크아웃된 위치를 가리키는 포인터입니다. 보통 브랜치를 가리키고, 브랜치는 커밋을 가리킵니다.

| 표현 | 의미 |
|---|---|
| `HEAD~1` | 한 단계 이전 커밋 |
| `HEAD~3` | 세 단계 이전 커밋 |
| `HEAD^` | 첫 번째 부모 커밋 |
| `HEAD^2` | 두 번째 부모 (병합 커밋의 경우) |

```bash
# 특정 커밋으로 HEAD만 이동 (detached HEAD 상태)
git checkout abc1234

# 두 단계 뒤로
git checkout HEAD~2
```

---

## 6. 히스토리 수정 — reset, revert, cherry-pick

### git reset

브랜치 포인터를 과거로 되돌립니다. 로컬 작업에서만 사용하는 것이 안전합니다.

```bash
git reset HEAD~1          # 커밋 취소, 변경사항은 유지 (--mixed, 기본값)
git reset --hard HEAD~1   # 커밋 + 변경사항 모두 삭제 (주의!)
git reset --soft HEAD~1   # 커밋만 취소, 스테이징 유지
```

### git revert

특정 커밋의 변경사항을 되돌리는 **새 커밋**을 만듭니다. 공유 브랜치에서도 안전하게 사용할 수 있습니다.

```bash
git revert HEAD         # 마지막 커밋을 되돌리는 커밋 생성
git revert abc1234      # 특정 커밋을 되돌리기
```

### git cherry-pick

다른 브랜치의 특정 커밋만 골라 현재 브랜치에 적용합니다.

```bash
# 특정 커밋 하나 가져오기
git cherry-pick abc1234

# 여러 커밋 한 번에
git cherry-pick abc1234 def5678
```

---

## 7. 원격 저장소

원격 저장소(remote)는 GitHub 같은 서버에 있는 저장소입니다.

| 명령어 | 설명 |
|---|---|
| `git clone URL` | 원격 저장소를 로컬로 복사 |
| `git fetch` | 원격 변경사항 가져오기 (병합 안 함) |
| `git pull` | fetch + merge를 한 번에 |
| `git push` | 로컬 커밋을 원격에 업로드 |

```bash
# 원격 브랜치 추적하며 push
git push -u origin main

# fetch 후 로그 확인, 그 다음 merge
git fetch origin
git log origin/main
git merge origin/main

# pull --rebase: merge 커밋 없이 깔끔하게
git pull --rebase
```

`origin/main`은 원격 브랜치의 로컬 복사본입니다. `fetch`를 해야 최신 상태로 갱신됩니다.

---

## 8. 고급 명령어

### git rebase -i (인터랙티브 리베이스)

여러 커밋을 한꺼번에 수정, 합치기, 순서 변경할 수 있는 강력한 도구입니다.

```bash
# 최근 3개 커밋을 편집 모드로 열기
git rebase -i HEAD~3
```

편집 화면에서 사용하는 키워드:

| 키워드 | 동작 |
|---|---|
| `pick` | 커밋 그대로 유지 |
| `reword` | 커밋 메시지만 수정 |
| `squash` | 이전 커밋에 합치기 |
| `drop` | 커밋 삭제 |

### git tag

특정 커밋에 버전 번호 같은 영구적인 이름을 붙입니다.

```bash
git tag v1.0.0              # 현재 커밋에 태그
git tag v1.0.0 abc1234      # 특정 커밋에 태그
git push origin --tags      # 태그를 원격에 push
```

### git describe

가장 가까운 태그를 기준으로 현재 위치를 사람이 읽기 좋은 형태로 보여줍니다.

```bash
git describe HEAD
# 출력 예: v1.0.0-3-gabc1234
# v1.0.0 태그에서 3커밋 위, 해시 abc1234
```

### git stash

커밋하지 않은 변경사항을 임시로 저장합니다. 브랜치를 급하게 바꿔야 할 때 유용합니다.

```bash
git stash          # 현재 작업 임시 저장
git stash pop      # 저장한 작업 복원
git stash list     # 저장 목록 확인
```

<img width="1581" height="1253" alt="image" src="https://github.com/user-attachments/assets/6ae39df0-6d90-49fb-9804-d1d1f495e564" />
<img width="1448" height="760" alt="스크린샷 2026-04-14 224814" src="https://github.com/user-attachments/assets/daf34eac-f591-4311-b807-f600b1bfe9cc" />
