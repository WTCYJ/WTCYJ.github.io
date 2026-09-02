# WTCY's DevLog

[![Website](https://img.shields.io/badge/website-live-0f766e)](https://wtcyj.github.io/)
[![GitHub stars](https://img.shields.io/github/stars/WTCYJ/WTCYJ.github.io?style=flat)](https://github.com/WTCYJ/WTCYJ.github.io/stargazers)
[![GitHub last commit](https://img.shields.io/github/last-commit/WTCYJ/WTCYJ.github.io)](https://github.com/WTCYJ/WTCYJ.github.io/commits/main)
[![Jekyll](https://img.shields.io/badge/Jekyll-4.3-cc0000)](https://jekyllrb.com/)

보안과 개발을 공부하며 얻은 결과를 재현 가능한 형태로 정리하는 공개 기술
블로그입니다. CTF와 Wargame 문제 풀이, 취약점 분석, Bug Bounty, 보안 도구,
알고리즘, 시스템 개발 기록을 한국어로 공유합니다.

- Website: [https://wtcyj.github.io](https://wtcyj.github.io/)
- Posts: [전체 글 보기](https://wtcyj.github.io/posts/)
- Maintainer: [@WTCYJ](https://github.com/WTCYJ)

## 프로젝트 소개

이 저장소는 Jekyll과 GitHub Pages로 배포되는 기술 지식 저장소의 전체 소스를
포함합니다. 단순한 학습 메모보다는 다른 학습자가 같은 환경을 구성하고 결과를
검증할 수 있도록 다음 내용을 중심으로 문서를 작성합니다.

- 실행 환경, 도구 버전, 명령어와 코드 예제
- 취약점의 원인, 재현 과정과 분석 결과
- 시행착오와 해결 과정
- 추가 학습에 활용할 수 있는 개념과 참고 자료

## 프로젝트 현황

2026년 6월 README 개편 시점을 기준으로 다음 자료를 공개하고 있습니다.

| 항목 | 현황 |
| --- | ---: |
| 공개 기술 글 | 79개 |
| 콘텐츠 분야 | 6개 |
| 저장소 커밋 | 109개 |
| 운영 형태 | 단독 메인테이너 |
| 배포 방식 | GitHub Pages |

### 콘텐츠 분야

| 분야 | 글 수 | 주요 내용 |
| --- | ---: | --- |
| 개발 | 60 | 알고리즘, 시스템, 웹, 프로그래밍 실습 |
| 블로그/기술문서 | 7 | 보안 개념, 도구와 운영 지식 |
| CTF/Wargame | 4 | 문제 풀이, 퍼징, 바이너리 분석 |
| Bug Bounty | 4 | 웹 취약점 분석과 실전 접근법 |
| 논문/컨퍼런스 | 2 | 연구 및 발표 내용 정리 |
| 공모전/자격증 | 2 | 준비 과정과 학습 기록 |

## 대표 콘텐츠

- [WebAssembly를 직접 뜯어보며 배운 것들](https://wtcyj.github.io/posts/webassembly/)
  - WAT 작성, JavaScript 연동, LEB128과 Wasm 바이너리 구조 분석
- [AFL++ 실습 상세 Write-up](https://wtcyj.github.io/posts/fuzzing101-writeup-v2/)
  - Xpdf, libexif, tcpdump 퍼징과 CVE 크래시 재현
- [침입 탐지 및 방지 시스템(IDS/IPS) 완전 정복](https://wtcyj.github.io/posts/ids-ips-complete-guide/)
  - IDS/IPS 구조, 탐지 방식, 오픈소스 도구와 운영 전략

## 기술 스택

- Jekyll 4.3
- GitHub Pages
- Liquid
- Markdown and Kramdown
- HTML and CSS
- Rouge syntax highlighting
- `jekyll-seo-tag`, `jekyll-sitemap`, `jekyll-feed`

## 로컬 실행

Ruby와 Bundler가 설치된 환경에서 다음 명령을 실행합니다.

```bash
git clone https://github.com/WTCYJ/WTCYJ.github.io.git
cd WTCYJ.github.io
bundle install
bundle exec jekyll serve
```

브라우저에서 [http://localhost:4000](http://localhost:4000)에 접속하면 로컬
사이트를 확인할 수 있습니다.

## 저장소 구조

```text
.
|-- _layouts/       # 공통 페이지와 게시물 레이아웃
|-- _posts/         # Markdown 기반 기술 문서
|-- assets/css/     # 사이트 스타일
|-- category/       # 분야별 목록 페이지
|-- _config.yml     # Jekyll 및 사이트 설정
|-- index.html      # 홈 화면
|-- posts.md        # 전체 게시물 목록
`-- about.md        # 메인테이너 소개
```

## 유지관리

메인테이너는 다음 작업을 직접 수행합니다.

- 기술 문서 작성과 기존 문서 보완
- 코드, 명령어, 도구 버전과 링크 검토
- CVE 및 취약점 재현 결과의 정확성 확인
- 카테고리, 태그, front matter 일관성 관리
- Jekyll 빌드와 GitHub Pages 배포 상태 확인

### 개선 계획

- Markdown front matter와 내부 링크 자동 검사
- 코드 블록 및 명령어 예제의 오류 탐지
- 오래된 보안 도구와 CVE 정보의 갱신 후보 생성
- 민감정보 노출 여부와 문서 품질 검사
- 반복 점검 작업을 CI에서 실행할 수 있는 공개 도구 개발
- 기여 가이드, 이슈 템플릿과 라이선스 정책 정비

## 기여 방법

오탈자, 깨진 링크, 재현되지 않는 명령어, 잘못된 기술 내용이나 새로운 주제에
대한 제안은 [Issue](https://github.com/WTCYJ/WTCYJ.github.io/issues)
또는 Pull Request로 남겨 주세요.

Pull Request에는 변경 목적, 검증한 환경과 결과를 함께 작성해 주시면 검토에
도움이 됩니다. 보안 취약점 관련 내용은 허가된 환경에서 재현 가능한 자료만
제안해 주세요.

## 라이선스

현재 저장소에는 별도의 라이선스가 지정되어 있지 않습니다. 라이선스 정책이
확정되기 전까지 코드와 콘텐츠의 재배포 또는 상업적 이용은 메인테이너에게
먼저 문의해 주세요.
