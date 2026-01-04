# 기술 상세 문서

## 1. Skill 핸들러 흐름 (api/skill.py)

```
사용자 메시지 → 카카오 서버 → /skill 엔드포인트
                                    ↓
                            classify_intent() (AI 분류)
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
              handle_save()   handle_summary()  handle_stats() ...
                    ↓               ↓               ↓
                    └───────────────┼───────────────┘
                                    ↓
                            JSON 응답 반환
```

## 2. 핵심 함수 위치

### skill.py 주요 함수
- `skill_handler()` - 메인 라우터 (line ~160)
- `handle_save()` - 메모 저장 (line ~80)
- `handle_summary()` - 정리/요약 (line ~100)
- `handle_stats()` - 통계 (line ~120)
- `get_default_quick_replies()` - 기본 버튼 7개 (line ~30)

### classifier.py 주요 함수
- `classify_intent()` - AI 의도 분류 (line ~104)
- `analyze_memo()` - 메모 카테고리 분류 (line ~211)

### memo_service.py 주요 함수
- `save_memo()` - 메모 저장
- `get_summary()` - 정리 조회
- `search_memos()` - 검색
- `delete_memos()` - 삭제

## 3. Redis 데이터 구조 (Upstash)

```
키 형식: memo:{user_id}:{memo_id}

값 (JSON):
{
    "id": "uuid",
    "user_id": "kakao_user_id",
    "content": "메모 내용 또는 URL",
    "category": "영상|맛집|...",
    "tags": ["태그1", "태그2"],
    "summary": "한줄 요약",
    "metadata": {
        "type": "youtube|instagram|...",
        "title": "OG 제목",
        "description": "설명",
        "image": "썸네일 URL",
        "site_name": "YouTube"
    },
    "created_at": "ISO 날짜",
    "reminder_at": "리마인더 날짜 (옵션)"
}
```

## 4. 카카오 Skill 요청 형식

```json
{
    "intent": {"id": "...", "name": "블록명"},
    "userRequest": {
        "timezone": "Asia/Seoul",
        "utterance": "사용자 발화",
        "user": {
            "id": "카카오 유저 ID",
            "type": "accountId"
        }
    },
    "bot": {"id": "봇 ID", "name": "챗노트"}
}
```

## 5. 자주 수정하는 부분

### QuickReplies 변경
```python
# skill.py - get_default_quick_replies()
def get_default_quick_replies() -> list:
    return [
        {"label": "📅 오늘", "action": "message", "messageText": "오늘 정리"},
        # ... 여기에 추가/수정
    ]
```

### 의도 분류 규칙 변경
```python
# classifier.py - INTENT_PROMPT
# Few-shot 예시 추가/수정으로 분류 정확도 개선
```

### 새 의도 추가
1. `classifier.py`의 `INTENT_PROMPT`에 새 의도 추가
2. `skill.py`에 `handle_새의도()` 함수 추가
3. `skill_handler()`에서 라우팅 추가

## 6. 디버깅 명령어

```bash
# Vercel 로그 실시간 확인
vercel logs memomate-mcp.vercel.app --follow

# Skill 직접 테스트
curl -X POST https://memomate-mcp.vercel.app/skill \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"userRequest":{"user":{"id":"test"},"utterance":"통계"}}'

# MCP 테스트
curl -X POST https://memomate-mcp.vercel.app/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## 7. 주의사항

1. **인코딩**: 카카오 요청은 UTF-8이 아닐 수 있음 → `errors='replace'` 필수
2. **타임아웃**: 카카오 스킬은 5초 타임아웃 → AI 호출 최적화 필요
3. **user_id**: 카카오 user_id는 봇마다 다름 (같은 사용자도 다른 ID)
4. **배포 순서**: Vercel 먼저 → 카카오 챗봇 빌더 배포

## 8. 파일별 의존성

```
skill.py
├── classifier.py (의도 분류)
├── memo_service.py (비즈니스 로직)
│   ├── storage.py (Redis)
│   ├── metadata.py (URL 파싱)
│   └── classifier.py (메모 분류)
└── datetime_parser.py (날짜 파싱)

mcp_server.py
├── memo_service.py
└── storage.py
```
