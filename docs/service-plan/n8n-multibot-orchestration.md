# n8n 멀티봇 오케스트레이션 가이드

## 개요
카카오톡 봇 여러 개를 n8n으로 관리하는 전략

---

## 핵심 결론

### n8n의 역할
```
n8n = "봇의 뇌"가 아닌 "봇의 신경계"
```

| 역할 | 담당 |
|------|------|
| **실시간 응답** | 각 스킬서버 (Vercel/Railway) |
| **비동기 처리** | n8n (로깅, 분석, 알림) |

**이유:** 카카오 오픈빌더 5초 제한 → n8n 거치면 레이턴시 증가

---

## 권장 아키텍처

```
┌─────────────────────────────────────────────────┐
│                카카오톡 사용자                    │
└───────┬───────────────┬───────────────┬─────────┘
        │               │               │
   ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
   │ 봇A     │    │ 봇B     │    │ 봇C     │
   │(메모)   │    │(일정)   │    │(검색)   │
   └────┬────┘    └────┬────┘    └────┬────┘
        │               │               │
   ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
   │스킬서버A│    │스킬서버B│    │스킬서버C│
   │(Vercel) │    │(Railway)│    │(Vercel) │
   └────┬────┘    └────┬────┘    └────┬────┘
        │               │               │
        └───────────────┼───────────────┘
                        │ (비동기 이벤트)
                   ┌────▼────┐
                   │   n8n   │ ← 오케스트레이터
                   └────┬────┘
                        │
      ┌─────────────────┼─────────────────┐
      │                 │                 │
 ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
 │ Redis   │      │ OpenAI  │      │ Slack   │
 │(공유DB) │      │(AI분석) │      │(알림)   │
 └─────────┘      └─────────┘      └─────────┘
```

---

## n8n 노드 가이드

### 필수 노드

| 카테고리 | 노드 | 용도 |
|----------|------|------|
| **트리거** | Webhook | 스킬서버에서 이벤트 수신 |
| **트리거** | Schedule Trigger | 정기 작업 (리마인더, 리포트) |
| **라우팅** | Switch | 봇별/이벤트별 분기 |
| **라우팅** | If | 조건부 처리 |
| **외부 연동** | HTTP Request | 카카오 API, 스킬서버 호출 |
| **AI** | OpenAI | GPT 분류/요약 |
| **AI** | Anthropic (Claude) | Claude 분류 |
| **데이터** | Redis | 공유 데이터 저장 |
| **데이터** | Postgres/Supabase | 장기 데이터 |
| **알림** | Slack/Discord | 관리자 알림 |
| **처리** | Code | JavaScript 커스텀 로직 |
| **처리** | Set | 데이터 변환 |

### 유용한 노드

| 노드 | 용도 |
|------|------|
| Respond to Webhook | 즉시 응답 후 비동기 처리 |
| Wait | 딜레이 (리마인더) |
| Merge | 여러 데이터 합치기 |
| Split In Batches | 대량 처리 |
| Error Trigger | 에러 발생 시 알림 |

---

## n8n 활용 시나리오

### 1. 중앙 로깅 시스템
```
스킬서버 → n8n Webhook → Redis/Postgres 저장 → Slack 알림
```

### 2. 크로스봇 데이터 공유
```
봇A 메모 저장 → n8n → Redis 저장
봇B 검색 요청 → n8n → Redis 조회 → 응답
```

### 3. 일일 요약 리포트
```
Schedule (매일 9시) → Redis 조회 → GPT 요약 → Slack 전송
```

### 4. 리마인더 발송
```
Schedule (매 1시간) → Redis 조회 (reminder_at) → 카카오 API 발송
```

### 5. 에러 모니터링
```
Error Trigger → Slack 알림 → 로그 저장
```

---

## n8n vs 직접 구현

| 기준 | n8n 사용 | 직접 구현 |
|------|----------|----------|
| **개발 속도** | 빠름 (노코드) | 느림 |
| **유연성** | 제한적 | 무한 |
| **유지보수** | 쉬움 (비주얼) | 코드 관리 필요 |
| **비용** | $5-20/mo | 개발자 시간 |
| **레이턴시** | +200-500ms | 없음 |

### 언제 n8n?
- ✅ 봇 5개 이상
- ✅ 비동기 처리 많음
- ✅ 빠른 프로토타이핑
- ✅ 비개발자 관리 필요

### 언제 직접 구현?
- ✅ 실시간 응답 필수
- ✅ 복잡한 비즈니스 로직
- ✅ 비용 최적화 필요

---

## n8n 배포 옵션

| 플랫폼 | 비용 | 특징 |
|--------|------|------|
| **Railway** | $5/mo | 가장 간편, 권장 |
| **Render** | $7/mo | 안정적 |
| **DigitalOcean** | $5/mo | VPS, 커스텀 가능 |
| **n8n Cloud** | $20/mo | 공식, 관리형 |

### Railway 배포 (권장)
```bash
# 1. Railway 가입
# 2. New Project → Deploy from GitHub
# 3. n8n-io/n8n 선택
# 4. 환경변수 설정:
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=비밀번호
WEBHOOK_URL=https://your-app.railway.app
```

---

## 카카오 연동 워크플로우 예시

### 기본 구조
```
[Webhook] → [Switch: 봇 구분] → [HTTP Request: 스킬서버] → [Respond to Webhook]
                                        ↓
                              [비동기: 로깅/분석]
```

### 샘플 워크플로우 (JSON)
```json
{
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "kakao-bot",
        "httpMethod": "POST"
      }
    },
    {
      "name": "Switch Bot",
      "type": "n8n-nodes-base.switch",
      "parameters": {
        "dataPropertyName": "body.bot_id",
        "rules": [
          { "value": "memo_bot" },
          { "value": "schedule_bot" }
        ]
      }
    },
    {
      "name": "Log to Redis",
      "type": "n8n-nodes-base.redis",
      "parameters": {
        "operation": "set",
        "key": "log:{{ $json.timestamp }}",
        "value": "{{ JSON.stringify($json) }}"
      }
    }
  ]
}
```

---

## 결론

### MemoMate 권장 전략

| 단계 | 봇 수 | 전략 |
|------|-------|------|
| **현재** | 1개 | Vercel만 (n8n 불필요) |
| **확장** | 3-5개 | n8n 도입 (로깅/알림) |
| **대규모** | 10개+ | n8n 필수 (중앙 관리) |

### n8n이 해결하는 문제
1. **봇 간 데이터 공유** - Redis 중앙화
2. **통합 모니터링** - 에러/사용량 한눈에
3. **스케줄 작업** - 리마인더, 리포트
4. **빠른 실험** - 새 기능 노코드 테스트

### 주의사항
- 카카오 응답은 스킬서버가 직접 (n8n 거치지 않음)
- n8n은 비동기 처리 전용
- 셀프호스팅 시 HTTPS 필수 (Webhook용)
