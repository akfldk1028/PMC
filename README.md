# 챗노트 (ChatNote)

카카오톡 챗봇 기반 메모 관리 서비스. URL/텍스트를 자동 분류하고, 리마인더 알림을 지원합니다.

## 주요 기능

- **자동 분류**: URL/텍스트 입력 시 AI가 카테고리 자동 분류 (영상/음악/맛집/쇼핑/여행/할일/아이디어/학습/건강/읽을거리)
- **리마인더**: 한국어 자연어로 리마인더 설정 ("내일 3시 병원 예약", "다음주 금요일 회의")
- **MCP 서버**: PlayMCP 연동 지원 (Claude AI에서 메모 검색/관리)
- **리치 응답**: 카카오 챗봇 BasicCard, ListCard 지원

## 기술 스택

- **Backend**: FastAPI (Python 3.12)
- **Database**: Upstash Redis
- **Hosting**: Vercel Serverless
- **AI**: OpenAI API (선택, 없으면 규칙 기반 분류)

## 프로젝트 구조

```
23_PMC/
├── api/                    # Vercel Serverless Functions
│   ├── cron.py            # 리마인더 체크 (Cron Job)
│   ├── mcp_server.py      # MCP JSON-RPC 서버 (PlayMCP용)
│   └── skill.py           # 카카오 챗봇 스킬 서버
├── lib/                    # 공용 라이브러리
│   ├── classifier.py      # 메모 분류 (AI/규칙 기반)
│   ├── datetime_parser.py # 한국어 날짜/시간 파싱
│   ├── kakao.py           # 카카오 API (나에게 보내기)
│   ├── metadata.py        # URL 메타데이터 추출
│   └── redis_db.py        # Upstash Redis DB
├── docs/                   # 문서
│   ├── architecture/      # 아키텍처 설계 문서
│   └── guides/            # 설정/배포 가이드
├── tests/                  # 테스트
├── requirements.txt        # Python 의존성
└── vercel.json            # Vercel 설정
```

## 환경 변수

```bash
# Upstash Redis
UPSTASH_REDIS_REST_URL=https://xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=xxx

# OpenAI (선택)
OPENAI_API_KEY=sk-xxx

# 카카오 (나에게 보내기용)
KAKAO_CLIENT_ID=xxx
KAKAO_CLIENT_SECRET=xxx
KAKAO_REDIRECT_URI=https://xxx/callback
```

## API 엔드포인트

| 경로 | 설명 |
|------|------|
| `/skill` | 카카오 챗봇 스킬 서버 |
| `/mcp` | MCP JSON-RPC 서버 |
| `/seed` | 테스트 데이터 시드 |
| `/api/cron/reminders` | 리마인더 체크 (Cron) |
| `/api/cron/health` | 헬스 체크 |

## 로컬 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 스킬 서버 실행 (포트 8001)
python api/skill.py

# MCP 서버 실행 (포트 8000)
python api/mcp_server.py
```

## 배포

```bash
vercel deploy --prod
```

## 카카오 챗봇 명령어

| 명령 | 예시 | 설명 |
|------|------|------|
| 메모 저장 | URL 또는 텍스트 입력 | 자동 분류 후 저장 |
| 정리/요약 | "오늘 정리", "이번주 요약" | 기간별 메모 조회 |
| 검색 | "검색 맛집" | 키워드로 메모 검색 |
| 삭제 | "삭제 AI트렌드" | 키워드로 메모 삭제 |
| 리마인더 | "리마인더" | 예정된 리마인더 목록 |

## 리마인더 예시

```
내일 3시 병원 예약
다음주 금요일 회의
모레 오후 2시 미팅
12월 25일 크리스마스 파티
```

## TODO

- [ ] 카카오 알림톡 연동 (푸시 알림)
- [ ] OAuth 로그인 연동
- [ ] 메모 공유 기능

## 라이선스

MIT License
