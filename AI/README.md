# 챗노트 (ChatNote) - AI 핸드오프 문서

> 📌 채널 URL: http://pf.kakao.com/_IHxegn
> 봇 ID: 6957875684dcee6380090caa

## 즉시 이해해야 할 핵심 정보

### 프로젝트 개요
**카카오톡 AI 메모 앱** - 사용자가 카카오톡으로 메모를 저장/검색/정리하는 서비스

### 채널 정보
| 항목 | 값 |
|------|-----|
| 채널명 | 챗노트 |
| 검색용 아이디 | 챗노트 |
| 채널 URL | http://pf.kakao.com/_IHxegn |
| 채팅 URL | http://pf.kakao.com/_IHxegn/chat |

### 배포 URL
| 엔드포인트 | URL |
|------------|-----|
| **Skill** | `https://memomate-mcp.vercel.app/skill` |
| **MCP** | `https://memomate-mcp.vercel.app/mcp` |
| **Health** | `https://memomate-mcp.vercel.app/` |

### 테스트/관리 링크
| 용도 | URL |
|------|-----|
| 카카오톡 채팅 테스트 | http://pf.kakao.com/_IHxegn/chat |
| 챗봇 관리자센터 | https://chatbot.kakao.com/ |
| PlayMCP (MCP 테스트) | https://playmcp.kakao.com |
| Vercel 대시보드 | https://vercel.com/dashboard |

---

## 환경 변수 (Vercel에 설정됨)
```
OPENAI_API_KEY=sk-xxx (AI 분류용)
UPSTASH_REDIS_REST_URL=https://workable-bengal-37069.upstash.io
UPSTASH_REDIS_REST_TOKEN=xxx
```

---

## 핵심 파일 구조
```
api/
├── skill.py          # 카카오 스킬 핸들러 (메인 진입점)
├── mcp_server.py     # MCP 프로토콜 서버
└── cron.py           # 리마인더 크론

lib/
├── classifier.py     # AI 의도 분류 (OpenAI)
├── memo_service.py   # 메모 비즈니스 로직
├── metadata.py       # URL 메타데이터 추출 (OG 태그)
├── storage.py        # Upstash Redis 저장소
└── datetime_parser.py # 날짜/시간 파싱
```

---

## 의도 분류 (classifier.py)
| 의도 | 트리거 예시 | 처리 함수 |
|------|-------------|-----------|
| `save` | 일반 텍스트, URL | `handle_save()` |
| `summary` | "오늘 정리", "영상 정리" | `handle_summary()` |
| `search` | "맛집 검색" | `handle_search()` |
| `delete` | "삭제 유튜브" | `handle_delete()` |
| `stats` | "통계" | `handle_stats()` |
| `reminder` | "리마인더" | `handle_reminder()` |
| `help` | "도움말" | `handle_help()` |

---

## 카카오 Skill 응답 형식
```python
{
    "version": "2.0",
    "template": {
        "outputs": [
            {"simpleText": {"text": "응답 메시지"}}
            # 또는 {"basicCard": {...}}
        ],
        "quickReplies": [
            {"label": "버튼명", "action": "message", "messageText": "발화"}
        ]
    }
}
```

---

## 현재 QuickReplies (7개)
1. 📅 오늘 → "오늘 정리"
2. 📆 이번주 → "이번주 정리"
3. 📺 영상 → "영상 정리"
4. 🍽️ 맛집 → "맛집 정리"
5. 📊 통계 → "통계"
6. ⏰ 리마인더 → "리마인더"
7. ❓ 도움말 → "도움말"

---

## 알려진 이슈
1. **Cold Start 타임아웃**: Vercel 서버리스 특성상 첫 요청시 5초+ 걸림 → 카카오 타임아웃 발생 가능
2. **UTF-8 인코딩**: 카카오에서 오는 요청 인코딩 문제 → `request.body().decode('utf-8', errors='replace')` 사용

---

## 배포 명령어
```bash
# Vercel 배포
cd D:/Data/23_PMC
vercel --prod --yes

# 카카오 챗봇 재배포
# https://chatbot.kakao.com/bot/6957875684dcee6380090caa/publish 에서 수동 배포
```

---

## MCP 도구 (8개)
| 도구 | 설명 |
|------|------|
| `add_memo` | 메모 저장 (URL 메타데이터 자동 추출) |
| `list_memos` | 메모 목록 조회 |
| `search_memos` | 키워드 검색 |
| `delete_memo` | 메모 삭제 |
| `get_summary` | 기간별/카테고리별 정리 |
| `get_stats` | 통계 조회 |
| `get_reminders` | 리마인더 목록 |
| `get_categories` | 카테고리 목록 |

---

## 카테고리 목록
영상, 음악, 맛집, 쇼핑, 여행, 할일, 아이디어, 학습, 건강, 읽을거리, 기타

---

## 다음 작업 제안
1. Cold Start 해결: Edge Function 또는 Keep-alive 설정
2. 카카오톡 카드 응답: BasicCard로 썸네일 표시
3. 리마인더 푸시 알림: 카카오 알림톡 연동
