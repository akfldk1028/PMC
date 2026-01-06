# 카카오 멀티봇 통합 관리 시스템

## 개요
카카오톡 봇 수십 개를 효율적으로 관리하는 **하이브리드 아키텍처** 가이드

> 이 문서는 PlayMCP 경진대회 및 카카오 챗봇 개발자를 위한 실전 가이드입니다.

---

## TL;DR (요약)

```
스킬서버 (Vercel/Railway) = 빠른 응답 (5초 제한)
     ↓ (비동기 이벤트)
n8n (Railway) = 로깅, 알림, 리마인더, AI 분석
     ↓
Redis + Slack + OpenAI
```

**왜 하이브리드?**
- n8n에 OpenAI 넣으면 됨 → 맞음, 근데 콜드스타트 + 단일장애점
- 스킬서버만 쓰면? → 비동기 처리, 알림, 스케줄 직접 구현해야 함
- **하이브리드** = 각자 잘하는 거 하기

---

## 아키텍처 비교

### Option A: n8n 올인 (소규모)
```
카카오 → n8n Webhook → OpenAI 노드 → Redis → 응답
```
- ✅ 간편, 노코드
- ❌ 콜드스타트 (Railway 무료: 5-10초)
- ❌ n8n 죽으면 전체 죽음
- **추천: 봇 1-3개, 트래픽 적음**

### Option B: 스킬서버 올인 (직접 구현)
```
카카오 → Vercel 스킬서버 → OpenAI → Redis → 응답
                      └→ 직접 구현: 로깅, 알림, 스케줄...
```
- ✅ 빠름, 안정적
- ❌ 모든 것 직접 구현
- **추천: 개발자 리소스 충분할 때**

### Option C: 하이브리드 ✅ 권장
```
카카오 → 스킬서버 (빠른 응답)
              ↓ (비동기)
            n8n (로깅, 알림, AI 분석, 스케줄)
```
- ✅ 빠른 응답 + 풍부한 기능
- ✅ 각 도구의 장점 활용
- ✅ 장애 격리
- **추천: 봇 5개+, 프로덕션**

---

## 하이브리드 아키텍처 상세

```
┌─────────────────────────────────────────────────────────────────┐
│                        카카오톡 사용자                            │
└───────────┬─────────────────┬─────────────────┬─────────────────┘
            │                 │                 │
       ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
       │ 메모봇  │       │ 일정봇  │       │ 검색봇  │
       │ 채널    │       │ 채널    │       │ 채널    │
       └────┬────┘       └────┬────┘       └────┬────┘
            │                 │                 │
            └─────────────────┼─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    통합 스킬서버 (Vercel/Railway)                 │
│                                                                  │
│   POST /skill/memo      ───┐                                    │
│   POST /skill/schedule  ───┼──→ Router → BotHandler → 응답      │
│   POST /skill/search    ───┘         │                          │
│                                      │                          │
│                              ┌───────▼───────┐                  │
│                              │ Shared Layer  │                  │
│                              │ - OpenAI      │                  │
│                              │ - Redis       │                  │
│                              │ - Classifier  │                  │
│                              └───────┬───────┘                  │
│                                      │                          │
│                              (비동기 HTTP POST)                  │
└──────────────────────────────────────┼──────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                         n8n (Railway)                            │
│                                                                  │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│   │   Webhook   │    │  Schedule   │    │   Error     │        │
│   │   (로깅)    │    │  (리마인더) │    │  (알림)     │        │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘        │
│          │                  │                  │                │
│          ▼                  ▼                  ▼                │
│   ┌─────────────────────────────────────────────────┐          │
│   │                  공통 처리                       │          │
│   │  - Redis 저장    - OpenAI 분석                  │          │
│   │  - Slack 알림    - 리포트 생성                  │          │
│   └─────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step 구축 가이드

### Step 1: 스킬서버 구축 (Vercel)

#### 1.1 프로젝트 구조
```
kakao-bots/
├── api/
│   └── skill.py              # 통합 엔드포인트
├── bots/
│   ├── __init__.py
│   ├── base.py               # 베이스 클래스
│   ├── registry.py           # 봇 등록
│   ├── memo/
│   │   └── handler.py
│   └── schedule/
│       └── handler.py
├── lib/
│   ├── ai/
│   │   └── openai_client.py
│   ├── db/
│   │   └── redis_client.py
│   └── kakao/
│       └── responses.py
├── requirements.txt
└── vercel.json
```

#### 1.2 통합 라우터 (api/skill.py)
```python
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

# 봇 핸들러 레지스트리
from bots.registry import get_handler

# n8n 웹훅 URL
N8N_WEBHOOK_URL = "https://your-n8n.railway.app/webhook/kakao-log"

@app.post("/skill/{bot_id}")
async def skill(bot_id: str, request: Request, background: BackgroundTasks):
    body = await request.json()

    # 1. 봇 핸들러로 빠른 응답
    handler = get_handler(bot_id)
    if not handler:
        return JSONResponse({"error": f"Unknown bot: {bot_id}"})

    response = await handler.process(body)

    # 2. n8n에 비동기 로깅 (응답 후 실행)
    background.add_task(send_to_n8n, bot_id, body, response)

    return JSONResponse(response)

async def send_to_n8n(bot_id: str, request: dict, response: dict):
    """n8n에 비동기로 로그 전송"""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(N8N_WEBHOOK_URL, json={
                "bot_id": bot_id,
                "user_id": request["userRequest"]["user"]["id"],
                "utterance": request["userRequest"]["utterance"],
                "response": response,
                "timestamp": datetime.now().isoformat()
            }, timeout=5.0)
    except Exception as e:
        print(f"n8n 전송 실패: {e}")  # 실패해도 응답에 영향 없음
```

#### 1.3 베이스 핸들러 (bots/base.py)
```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseBotHandler(ABC):
    """모든 봇 핸들러가 상속받는 베이스 클래스"""

    @property
    @abstractmethod
    def bot_id(self) -> str:
        """봇 고유 ID"""
        pass

    @property
    @abstractmethod
    def bot_name(self) -> str:
        """봇 표시 이름"""
        pass

    @abstractmethod
    async def process(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """카카오 요청 처리 → 응답 반환"""
        pass

    def create_text_response(self, text: str) -> Dict:
        """간단한 텍스트 응답"""
        return {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": text}}]
            }
        }

    def create_card_response(self, title: str, desc: str) -> Dict:
        """카드 응답"""
        return {
            "version": "2.0",
            "template": {
                "outputs": [{
                    "textCard": {
                        "title": title[:40],
                        "description": desc[:76]
                    }
                }]
            }
        }
```

#### 1.4 봇 레지스트리 (bots/registry.py)
```python
from typing import Dict, Optional
from bots.base import BaseBotHandler
from bots.memo.handler import MemoHandler
from bots.schedule.handler import ScheduleHandler

# 봇 등록
_HANDLERS: Dict[str, BaseBotHandler] = {}

def register_bot(handler: BaseBotHandler):
    """봇 핸들러 등록"""
    _HANDLERS[handler.bot_id] = handler

def get_handler(bot_id: str) -> Optional[BaseBotHandler]:
    """봇 핸들러 조회"""
    return _HANDLERS.get(bot_id)

def list_bots() -> list:
    """등록된 봇 목록"""
    return [{"id": h.bot_id, "name": h.bot_name} for h in _HANDLERS.values()]

# 봇 등록 실행
register_bot(MemoHandler())
register_bot(ScheduleHandler())
```

---

### Step 2: n8n 구축 (Railway)

#### 2.1 Railway 배포
```bash
# 1. Railway 가입 (https://railway.app)
# 2. New Project → Deploy from GitHub
# 3. n8n-io/n8n 선택

# 4. 환경변수 설정:
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=your-password
WEBHOOK_URL=https://your-n8n.railway.app
GENERIC_TIMEZONE=Asia/Seoul
```

#### 2.2 필수 워크플로우

##### 워크플로우 1: 로깅 수집
```
[Webhook: /kakao-log]
    ↓
[Set: 데이터 정리]
    ↓
[Redis: 저장]
    ↓
[IF: 에러 발생?]
    ├─ Yes → [Slack: 에러 알림]
    └─ No → [End]
```

##### 워크플로우 2: 리마인더 발송
```
[Schedule: 매 10분]
    ↓
[Redis: 리마인더 조회]
    ↓
[IF: 발송할 리마인더?]
    ├─ Yes → [HTTP: 카카오 알림톡 API]
    └─ No → [End]
```

##### 워크플로우 3: 일일 리포트
```
[Schedule: 매일 09:00]
    ↓
[Redis: 어제 통계 조회]
    ↓
[OpenAI: 요약 생성]
    ↓
[Slack: 리포트 전송]
```

#### 2.3 n8n 노드 가이드

| 카테고리 | 노드 | 용도 |
|----------|------|------|
| **트리거** | Webhook | 스킬서버에서 이벤트 수신 |
| **트리거** | Schedule Trigger | 정기 작업 |
| **조건** | IF | 조건 분기 |
| **조건** | Switch | 다중 분기 (봇별 라우팅) |
| **데이터** | Redis | 로그 저장/조회 |
| **데이터** | Set | 데이터 변환 |
| **AI** | OpenAI | GPT 분석/요약 |
| **알림** | Slack | 팀 알림 |
| **알림** | Discord | 팀 알림 |
| **HTTP** | HTTP Request | 카카오 API 호출 |
| **유틸** | Code | JavaScript 커스텀 |

---

### Step 3: 연동 및 테스트

#### 3.1 카카오 오픈빌더 설정
```
스킬 URL 설정:
- 메모봇: https://your-app.vercel.app/skill/memo
- 일정봇: https://your-app.vercel.app/skill/schedule
- 검색봇: https://your-app.vercel.app/skill/search
```

#### 3.2 테스트 체크리스트
```
[ ] 스킬서버 응답 확인 (5초 이내)
[ ] n8n 웹훅 수신 확인
[ ] Redis 로그 저장 확인
[ ] Slack 알림 수신 확인
[ ] 리마인더 발송 테스트
```

---

## n8n에서 OpenAI 사용하기

### 왜 n8n에서 OpenAI?
- 실시간 응답 = 스킬서버에서 직접
- **비동기 분석** = n8n에서 OpenAI
  - 대화 요약
  - 사용 패턴 분석
  - 리포트 생성

### 설정 방법
```
1. n8n → Credentials → OpenAI API
2. API Key 입력
3. 워크플로우에서 OpenAI 노드 사용
```

### 예시: 일일 대화 요약
```
[Schedule: 09:00]
    ↓
[Redis: 어제 대화 조회]
    ↓
[OpenAI: Chat Model]
    - Model: gpt-4o-mini
    - Prompt: "다음 대화 내역을 요약해줘: {{대화목록}}"
    ↓
[Slack: 요약 전송]
```

### 레이턴시 고려
```
n8n OpenAI 호출: ~2-5초
→ 실시간 응답에는 부적합
→ 비동기 분석에만 사용
```

---

## 비용 분석

### 봇 10개 기준

| 서비스 | 무료 티어 | Pro |
|--------|----------|-----|
| Vercel | $0 | $20/mo |
| Railway (n8n) | $5/mo | $10/mo |
| Upstash Redis | $0 | $10/mo |
| OpenAI | ~$5/mo | ~$20/mo |
| Sentry | $0 | $0 |
| **합계** | **~$10/mo** | **~$60/mo** |

### 봇 50개 기준

| 서비스 | 예상 비용 |
|--------|----------|
| Railway (API) | $20/mo |
| Railway (n8n) | $15/mo |
| Upstash Pro | $25/mo |
| OpenAI | ~$50/mo |
| **합계** | **~$110/mo** |

---

## 트러블슈팅

### 문제: 카카오 5초 타임아웃
```
원인: 스킬서버 응답 느림
해결:
1. n8n 비동기 처리로 분리
2. OpenAI 호출 최적화 (gpt-4o-mini)
3. Redis 캐싱 활용
```

### 문제: n8n 콜드스타트
```
원인: Railway 무료 티어 휴면
해결:
1. Railway Pro ($5/mo) - 항상 실행
2. 또는 UptimeRobot으로 5분마다 핑
```

### 문제: 봇 간 데이터 공유 안됨
```
원인: 각 봇이 별도 Redis 키 사용
해결:
1. 공통 키 구조: user:{user_id}:*
2. n8n에서 데이터 동기화 워크플로우
```

---

## 프로젝트 구조 (전체)

```
kakao-bots/
├── api/
│   ├── skill.py              # 통합 스킬 엔드포인트
│   └── health.py             # 헬스체크
│
├── bots/
│   ├── __init__.py
│   ├── base.py               # BaseBotHandler
│   ├── registry.py           # 봇 레지스트리
│   │
│   ├── memo/                 # 메모 봇
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── intents.py
│   │   └── config.yaml
│   │
│   ├── schedule/             # 일정 봇
│   │   └── ...
│   │
│   └── search/               # 검색 봇
│       └── ...
│
├── lib/
│   ├── ai/
│   │   ├── openai_client.py  # OpenAI 래퍼
│   │   └── classifier.py     # 의도 분류
│   │
│   ├── db/
│   │   ├── redis_client.py   # Redis 래퍼
│   │   └── models.py         # 데이터 모델
│   │
│   ├── kakao/
│   │   ├── responses.py      # 응답 포맷
│   │   └── cards.py          # 카드 생성
│   │
│   └── utils/
│       ├── logger.py         # 로깅
│       └── helpers.py        # 유틸
│
├── config/
│   ├── settings.py           # 환경변수
│   └── bots.yaml             # 봇 설정
│
├── n8n/                      # n8n 워크플로우 백업
│   ├── logging.json
│   ├── reminder.json
│   └── daily-report.json
│
├── tests/
│   └── ...
│
├── requirements.txt
├── vercel.json
└── README.md
```

---

## 체크리스트

### Phase 1: 기본 구축
- [ ] GitHub 레포 생성
- [ ] 프로젝트 구조 설정
- [ ] BaseBotHandler 구현
- [ ] 첫 번째 봇 마이그레이션
- [ ] 통합 라우터 구현
- [ ] Vercel 배포
- [ ] 카카오 오픈빌더 연결

### Phase 2: n8n 연동
- [ ] Railway에 n8n 배포
- [ ] 로깅 워크플로우 생성
- [ ] 스킬서버 → n8n 연동
- [ ] Slack 알림 설정
- [ ] 리마인더 워크플로우

### Phase 3: 확장
- [ ] 추가 봇 등록
- [ ] 대시보드 구축 (Retool)
- [ ] 모니터링 강화 (Sentry)
- [ ] 성능 최적화

---

## 결론

### 하이브리드가 정답인 이유
```
스킬서버 = 빠른 응답 (카카오 5초 제한)
n8n = 풍부한 기능 (로깅, 알림, 분석)

둘 다 쓰면 = 빠르면서 + 기능도 풍부
```

### 핵심 원칙
1. **응답은 스킬서버에서** - 5초 제한 준수
2. **나머지는 n8n에서** - 비동기 처리
3. **공통 Redis 사용** - 데이터 공유
4. **점진적 확장** - 봇 추가 쉽게

### 시작하기
```bash
# 1. 레포 클론
git clone https://github.com/your/kakao-bots

# 2. 환경변수 설정
cp .env.example .env

# 3. 로컬 테스트
uvicorn api.skill:app --reload

# 4. Vercel 배포
vercel deploy

# 5. n8n 배포 (Railway)
# → Railway 대시보드에서 설정
```

---

## 참고 자료

- [카카오 오픈빌더 가이드](https://kakaobusiness.gitbook.io)
- [n8n 공식 문서](https://docs.n8n.io)
- [Railway 가이드](https://docs.railway.app)
- [Vercel 가이드](https://vercel.com/docs)
- [Upstash Redis](https://upstash.com/docs/redis)
