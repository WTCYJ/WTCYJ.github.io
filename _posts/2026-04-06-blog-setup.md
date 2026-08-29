---
layout: post
title: "블로그 개설 및 Jekyll 환경 구축 기록"
date: 2026-04-06
category: 블로그/기술
author: yejunkim2000
excerpt: "GitHub Pages와 Jekyll을 이용해 개발 블로그를 구축한 과정을 정리합니다."
---

## 개요

GitHub Pages와 Jekyll을 이용해 개인 기술 블로그를 구축했습니다.  
이 글에서는 전체 설정 과정과 커스터마이징 방법을 정리합니다.

## 왜 Jekyll인가?

- GitHub Pages에서 공식 지원
- Markdown으로 글 작성 가능
- 정적 사이트라 빠르고 무료 호스팅 가능
- 다양한 테마와 플러그인 생태계

## 디렉토리 구조

```
yejunkim2000.github.io/
├── _layouts/
│   ├── default.html
│   └── post.html
├── _posts/
├── assets/
│   └── css/
│       └── main.css
├── _config.yml
├── index.md
├── about.md
└── posts.md
```

## 카테고리 구성

총 6개 카테고리로 글을 분류합니다.

- **개발** - 프로그래밍, 도구 개발
- **CTF/Wargame** - 문제풀이 및 기법 정리
- **Bug Bounty** - 취약점 발굴 기록
- **블로그/기술문서** - 블로그 운영, 기술 정리
- **논문/컨퍼런스** - 논문 리뷰, 컨퍼런스 후기
- **공모전/자격증** - 대회 참가 및 자격증 취득 기록

## 앞으로 계획

꾸준히 보안과 개발 관련 내용을 기록할 예정입니다.
