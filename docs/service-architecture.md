# MemoMate 서비스 아키텍처

## 개요
카카오톡 기반 AI 메모 앱 - PlayMCP 경진대회 출품작

## 배포 현황
| 서비스 | URL | 상태 |
|--------|-----|------|
| Vercel | memomate-mcp.vercel.app | 운영 중 |
| Upstash Redis | workable-bengal-37069.upstash.io | 운영 중 |
| 카카오 채널 | 챗노트 | 운영 중 |

## 핵심 변경사항 (2026-01-05)

### 저장 로직 변경: "있는 그대로 저장"
- **기본 저장**: AI 개입 없이 원본 그대로 저장
- **AI 분류 저장**: `AI:` 접두사 사용 시에만 AI 분류

```
# 기본 저장 (원본 그대로)
"야야" → title: "야야", category: "기타"

# AI 분류 저장 (사용자 명시적 요청)
"AI: 맛있는 파스타집 발견" → title: "맛있는 파스타집", category: "맛집"
```

### 변경된 파일
1. `lib/memo_service.py` - `use_ai` 파라미터 추가
2. `lib/classifier.py` - `AI:` 접두사 패턴 인식
3. `api/skill.py` - `save_with_ai` intent 핸들링

---

## MCP vs Bot 개념

| 구분 | Bot (skill.py) | MCP (mcp_server.py) |
|------|----------------|---------------------|
| 대상 | 인간 (카카오톡) | AI 에이전트 (PlayMCP) |
| 입력 | 자연어 | JSON-RPC 2.0 |
| 처리 | 의도분류 → 실행 | 직접 도구 호출 |
| 응답 | BasicCard, ListCard | JSON 데이터 |

---

## 서비스화 체크리스트

### DB 분리 (확인됨)
- `memo:{user_id}:{memo_id}` 키 구조
- 유저 간 데이터 완전 격리

### 용량 분석
- 1개 메모 = 약 1-2KB
- 무료 티어 256MB = 약 12만 메모 한계
- 서비스화 시 Pro 전환 필요

### Phase 1 (런칭 전 필수)
- [ ] Upstash Pro 전환
- [ ] Rate Limit 추가
- [ ] 유저당 메모 제한 (100개)
- [ ] Sentry 에러 모니터링

### Phase 2 (사용자 증가 시)
- [ ] 데이터 아카이빙
- [ ] Redis → PostgreSQL 하이브리드
- [ ] CDN 캐싱

### Phase 3 (수익화)
- [ ] 프리미엄 플랜
- [ ] API 사용량 과금

---

## 명령어 목록

### 저장
- 아무 텍스트 → 원본 그대로 저장
- `AI: 내용` → AI 분류 저장

### 조회
- `오늘 정리`, `이번주 정리` → 기간별 조회
- `영상 정리`, `맛집 정리` → 카테고리별 조회
- `검색 키워드` → 메모 검색

### 기타
- `통계` → 저장 현황
- `리마인더` → 예정된 알림
- `도움말` → 사용법
