# AI 비용 분석 및 최적화 전략

## 현재 사용 모델
- **GPT-4o-mini**: $0.15 입력 / $0.60 출력 (per 1M tokens)

## 대안 모델 비교 (2025년 기준)

| 모델 | 입력 | 출력 | 비고 |
|------|------|------|------|
| **GPT-4o-mini** | $0.15 | $0.60 | 현재 사용 중, 한국어 우수 |
| Grok 4 Fast | $0.20 | $0.50 | 출력 17% 저렴 |
| Gemini 2.5 Flash | ~$0.15-0.30 | $0.60-$3.50 | 1M 토큰 컨텍스트 |
| DeepSeek V3.2 | ~$0.28 | ~$0.84 | 중국 기반 |
| Claude 3.5 Haiku | - | - | Anthropic 저가 모델 |

## 현재 아키텍처 (이미 최적화됨)

### AI가 사용되는 곳
1. **의도 분류** (`classify_intent`)
   - 파일: `lib/classifier.py:274-323`
   - 조건: 규칙 기반(`fast_rule_classify`)으로 처리 안 될 때만
   - 실제 호출: **매우 드묾** (대부분 규칙으로 처리)

2. **메모 분류** (`analyze_memo`)
   - 파일: `lib/classifier.py:354-408`
   - 조건: `use_ai=True`일 때만 (사용자가 "AI:" 접두사 사용 시)
   - 실제 호출: **사용자 선택 시에만**

### AI 호출 흐름
```
사용자 입력
    ↓
fast_rule_classify() ← 규칙 기반 (AI 없음)
    ↓ (규칙 매칭 실패 시)
openai_intent_classification() ← AI 호출 (드묾)
    ↓
저장 시:
  use_ai=False → 원본 그대로 (AI 없음)
  use_ai=True  → openai_classification() (사용자 요청 시만)
```

## 결론

### GPT-4o-mini 유지 추천
1. **한국어 지원 우수**
2. **가격 대비 성능 최고** ("shockingly strong for the price" 평가)
3. **안정적인 API**

### 추가 최적화 방안
1. 분류 결과 캐싱 (Redis)
2. 야간 배치 분류 처리
3. 서비스 확장 시 Gemini Flash / Claude Haiku 병행

## Sources
- [LLM API Pricing Comparison 2025](https://intuitionlabs.ai/articles/llm-api-pricing-comparison-2025)
- [Low-Cost LLM Comparison](https://intuitionlabs.ai/articles/low-cost-llm-comparison)
- [Top 11 LLM API Providers 2025](https://futureagi.com/blogs/top-11-llm-api-providers-2025)
