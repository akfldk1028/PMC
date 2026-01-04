"""
AI 주도 의도 분류 모듈 (비즈니스용)
- OpenAI API 필수 (없으면 사용자에게 안내)
- 신뢰도 기반 응답
- Few-shot 프롬프트로 정확도 향상
"""
import os
import json
import httpx
from typing import Optional

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# ============ 의도 분류 (AI 주도) ============

INTENT_PROMPT = """당신은 메모 앱의 의도 분류 AI입니다.
사용자 메시지를 분석하여 의도를 정확히 분류하세요.

## 의도 종류
1. **summary**: 저장된 메모 정리/요약 요청 (기간별/카테고리별)
2. **search**: 메모 검색 요청
3. **delete**: 메모 삭제 요청
4. **reminder**: 리마인더/알림 목록 조회
5. **stats**: 통계 조회 (몇 개 저장했는지 등)
6. **help**: 사용법/도움말 요청
7. **save**: 메모로 저장할 내용 (기본값)

## 분류 규칙 (중요!)
- 명확한 **명령어 형태**만 해당 의도로 분류
- 일반 문장/정보는 **save**로 분류 (메모 저장)
- 의심스러우면 **save**로 분류 (저장이 기본)

## 핵심 예시 (반드시 참고)

### summary (정리/요약) - 명확한 명령어만
기간별:
- "오늘 정리" → summary (period: today)
- "어제 정리" → summary (period: yesterday)
- "이번주 정리" → summary (period: week)
- "지난주 정리" → summary (period: last_week)
- "이번달 정리" → summary (period: month)
- "지난달 정리" → summary (period: last_month)
- "전체 보여줘" → summary (period: all)

카테고리별:
- "영상 정리" → summary (category: 영상)
- "맛집 정리" → summary (category: 맛집)
- "할일 정리" → summary (category: 할일)
- "쇼핑 정리" → summary (category: 쇼핑)
- "여행 정리" → summary (category: 여행)

### search (검색) - "검색/찾아" 단어 포함
- "맛집 검색" → search (keyword: 맛집)
- "유튜브 찾아줘" → search (keyword: 유튜브)
- "검색 개발" → search (keyword: 개발)

### delete (삭제) - "삭제/지워" 단어 포함
- "삭제 유튜브" → delete (keyword: 유튜브)
- "맛집 지워줘" → delete (keyword: 맛집)

### reminder (리마인더)
- "리마인더" → reminder
- "알림 목록" → reminder
- "예정된 일정" → reminder

### stats (통계)
- "통계" → stats
- "몇 개 저장했어?" → stats
- "이번주 몇 개?" → stats
- "카테고리별 통계" → stats

### help (도움말)
- "도움말" → help
- "사용법" → help
- "어떻게 써?" → help
- "?" → help
- "뭘 할 수 있어?" → help

### save (저장) - 그 외 모든 것!
- "오늘메모를마지막에ai가정리" → save (문장이므로 저장)
- "내일 3시 회의" → save (할일 메모)
- "https://youtube.com/..." → save (URL 저장)
- "맛있는 파스타집 발견" → save (정보 저장)
- "아이디어: 앱 만들기" → save
- "오늘 날씨 좋다" → save

## 응답 형식 (JSON)
{{
    "intent": "의도",
    "confidence": 0.0~1.0,
    "keyword": "검색어/삭제대상 (search/delete만)",
    "period": "today/yesterday/week/last_week/month/last_month/all (summary만)",
    "category": "영상/음악/맛집/쇼핑/여행/할일/아이디어/학습/건강/읽을거리 (summary 카테고리별만)",
    "reasoning": "판단 근거 한줄"
}}

---
사용자 메시지: {message}
---

JSON으로만 응답하세요:"""


# ============ 빠른 규칙 기반 분류 (AI 호출 없이 즉시 응답) ============

def fast_rule_classify(message: str) -> dict | None:
    """
    빠른 규칙 기반 의도 분류 (AI 호출 없이 ~0ms)
    명확한 명령어만 처리, 애매하면 None 반환하여 AI로 위임
    """
    msg = message.strip()
    msg_lower = msg.lower()

    # 정확 매칭 (가장 빠름)
    EXACT_MATCHES = {
        # 리마인더
        "리마인더": {"intent": "reminder", "confidence": 1.0},
        "알림": {"intent": "reminder", "confidence": 1.0},
        "알림 목록": {"intent": "reminder", "confidence": 1.0},
        # 통계
        "통계": {"intent": "stats", "confidence": 1.0},
        # 도움말/홈
        "도움말": {"intent": "help", "confidence": 1.0},
        "홈": {"intent": "help", "confidence": 1.0},
        "사용법": {"intent": "help", "confidence": 1.0},
        "?": {"intent": "help", "confidence": 1.0},
        # 기간별 정리
        "오늘 정리": {"intent": "summary", "confidence": 1.0, "period": "today"},
        "오늘정리": {"intent": "summary", "confidence": 1.0, "period": "today"},
        "어제 정리": {"intent": "summary", "confidence": 1.0, "period": "yesterday"},
        "이번주 정리": {"intent": "summary", "confidence": 1.0, "period": "week"},
        "이번 주 정리": {"intent": "summary", "confidence": 1.0, "period": "week"},
        "지난주 정리": {"intent": "summary", "confidence": 1.0, "period": "last_week"},
        "지난 주 정리": {"intent": "summary", "confidence": 1.0, "period": "last_week"},
        "이번달 정리": {"intent": "summary", "confidence": 1.0, "period": "month"},
        "이번 달 정리": {"intent": "summary", "confidence": 1.0, "period": "month"},
        "지난달 정리": {"intent": "summary", "confidence": 1.0, "period": "last_month"},
        "전체 보여줘": {"intent": "summary", "confidence": 1.0, "period": "all"},
        "전체보여줘": {"intent": "summary", "confidence": 1.0, "period": "all"},
        # 카테고리별 정리
        "영상 정리": {"intent": "summary", "confidence": 1.0, "category": "영상"},
        "음악 정리": {"intent": "summary", "confidence": 1.0, "category": "음악"},
        "맛집 정리": {"intent": "summary", "confidence": 1.0, "category": "맛집"},
        "쇼핑 정리": {"intent": "summary", "confidence": 1.0, "category": "쇼핑"},
        "여행 정리": {"intent": "summary", "confidence": 1.0, "category": "여행"},
        "할일 정리": {"intent": "summary", "confidence": 1.0, "category": "할일"},
        "아이디어 정리": {"intent": "summary", "confidence": 1.0, "category": "아이디어"},
        "학습 정리": {"intent": "summary", "confidence": 1.0, "category": "학습"},
        "건강 정리": {"intent": "summary", "confidence": 1.0, "category": "건강"},
        "읽을거리 정리": {"intent": "summary", "confidence": 1.0, "category": "읽을거리"},
        "기타 정리": {"intent": "summary", "confidence": 1.0, "category": "기타"},
        # 전체보기 (show_all=True)
        "전체보기 today": {"intent": "summary", "confidence": 1.0, "period": "today", "show_all": True},
        "전체보기 yesterday": {"intent": "summary", "confidence": 1.0, "period": "yesterday", "show_all": True},
        "전체보기 week": {"intent": "summary", "confidence": 1.0, "period": "week", "show_all": True},
        "전체보기 last_week": {"intent": "summary", "confidence": 1.0, "period": "last_week", "show_all": True},
        "전체보기 month": {"intent": "summary", "confidence": 1.0, "period": "month", "show_all": True},
        "전체보기 all": {"intent": "summary", "confidence": 1.0, "period": "all", "show_all": True},
        "전체보기 영상": {"intent": "summary", "confidence": 1.0, "category": "영상", "show_all": True},
        "전체보기 음악": {"intent": "summary", "confidence": 1.0, "category": "음악", "show_all": True},
        "전체보기 맛집": {"intent": "summary", "confidence": 1.0, "category": "맛집", "show_all": True},
        "전체보기 쇼핑": {"intent": "summary", "confidence": 1.0, "category": "쇼핑", "show_all": True},
        "전체보기 여행": {"intent": "summary", "confidence": 1.0, "category": "여행", "show_all": True},
        "전체보기 할일": {"intent": "summary", "confidence": 1.0, "category": "할일", "show_all": True},
        "전체보기 아이디어": {"intent": "summary", "confidence": 1.0, "category": "아이디어", "show_all": True},
        "전체보기 학습": {"intent": "summary", "confidence": 1.0, "category": "학습", "show_all": True},
        "전체보기 건강": {"intent": "summary", "confidence": 1.0, "category": "건강", "show_all": True},
        "전체보기 읽을거리": {"intent": "summary", "confidence": 1.0, "category": "읽을거리", "show_all": True},
        "전체보기 기타": {"intent": "summary", "confidence": 1.0, "category": "기타", "show_all": True},
    }

    if msg in EXACT_MATCHES:
        return EXACT_MATCHES[msg]

    # 패턴 매칭 (검색/삭제)
    # "검색 XXX" 또는 "XXX 검색"
    if msg.startswith("검색 "):
        keyword = msg[3:].strip()
        if keyword:
            return {"intent": "search", "confidence": 1.0, "keyword": keyword}
    if msg.endswith(" 검색"):
        keyword = msg[:-3].strip()
        if keyword:
            return {"intent": "search", "confidence": 1.0, "keyword": keyword}
    if "찾아줘" in msg:
        keyword = msg.replace("찾아줘", "").strip()
        if keyword:
            return {"intent": "search", "confidence": 0.9, "keyword": keyword}

    # "삭제 XXX" 또는 "XXX 삭제" 또는 "XXX 지워"
    if msg.startswith("삭제 "):
        keyword = msg[3:].strip()
        if keyword:
            return {"intent": "delete", "confidence": 1.0, "keyword": keyword}
    if msg.endswith(" 삭제"):
        keyword = msg[:-3].strip()
        if keyword:
            return {"intent": "delete", "confidence": 1.0, "keyword": keyword}
    if "지워줘" in msg or "지워" in msg:
        keyword = msg.replace("지워줘", "").replace("지워", "").strip()
        if keyword:
            return {"intent": "delete", "confidence": 0.9, "keyword": keyword}

    # URL은 무조건 저장 (AI 호출 불필요)
    if msg_lower.startswith(("http://", "https://", "www.")):
        return {"intent": "save", "confidence": 1.0, "reasoning": "URL 감지"}

    # 그 외는 None 반환 → AI로 위임
    return None


async def classify_intent(message: str) -> dict:
    """의도 분류 (규칙 기반 우선 → AI 폴백)"""

    # 1. 빠른 규칙 기반 분류 먼저 시도 (~0ms)
    fast_result = fast_rule_classify(message)
    if fast_result:
        print(f"[Classifier] Fast rule: {fast_result.get('intent')}")
        return fast_result

    # 2. OpenAI API 키 필수 (규칙으로 분류 안 된 경우)
    if not OPENAI_API_KEY:
        # API 키 없으면 기본 저장으로 처리 (에러 안 냄)
        return {
            "intent": "save",
            "confidence": 0.5,
            "reasoning": "API 키 없음, 기본 저장 처리"
        }

    # 3. AI 분류 시도
    try:
        result = await openai_intent_classification(message)
        if result:
            return result
    except Exception as e:
        print(f"[Classifier] AI Error: {e}")

    # AI 실패 시 - 저장으로 안전하게 처리
    return {
        "intent": "save",
        "confidence": 0.5,
        "reasoning": "AI 분류 실패, 안전하게 저장 처리"
    }


async def openai_intent_classification(message: str) -> Optional[dict]:
    """OpenAI API로 의도 분류"""

    prompt = INTENT_PROMPT.format(message=message)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "의도 분류 AI입니다. JSON으로만 응답합니다."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,  # 일관성 최대화
                    "max_tokens": 200,
                    "response_format": {"type": "json_object"}  # JSON 강제
                },
                timeout=10.0
            )

            if response.status_code != 200:
                print(f"[Classifier] API Error: {response.status_code}")
                return None

            result = response.json()
            answer = result["choices"][0]["message"]["content"]

            parsed = json.loads(answer)

            # 필수 필드 검증
            if "intent" not in parsed:
                parsed["intent"] = "save"
            if "confidence" not in parsed:
                parsed["confidence"] = 0.7

            print(f"[Classifier] AI Result: {parsed}")
            return parsed

    except json.JSONDecodeError as e:
        print(f"[Classifier] JSON Parse Error: {e}")
    except Exception as e:
        print(f"[Classifier] Request Error: {e}")

    return None


# ============ 메모 분류 (카테고리/태그/요약) ============

CLASSIFICATION_PROMPT = """다음 메모를 분석해서 JSON으로 반환해줘.

메모: {content}
{metadata_info}

응답 형식:
{{
    "category": "영상/음악/맛집/쇼핑/여행/할일/아이디어/학습/건강/읽을거리/기타 중 하나",
    "tags": ["태그1", "태그2"],
    "summary": "한줄 요약 (30자 이내)"
}}

카테고리 기준:
- 영상: 유튜브, 동영상, 릴스, 틱톡, 넷플릭스
- 음악: 스포티파이, 멜론, 애플뮤직, 플레이리스트, 노래
- 맛집: 음식점, 카페, 맛집, 레스토랑
- 쇼핑: 상품, 구매, 쇼핑몰, 가격비교
- 여행: 여행지, 호텔, 항공, 관광, 숙소
- 할일: 해야 할 일, 일정, 예약, 약속, 시간 포함 메모
- 아이디어: 아이디어, 기획, 영감
- 학습: 강의, 튜토리얼, 교육, 코딩, 공부
- 건강: 운동, 헬스, 다이어트, 건강관리
- 읽을거리: 블로그, 뉴스, 기사, 아티클
- 기타: 위에 해당 안 되는 것"""


async def analyze_memo(content: str, metadata: Optional[dict] = None) -> dict:
    """메모 분석 (분류 + 태그 + 요약)"""

    # OpenAI API 키가 있으면 AI 분류
    if OPENAI_API_KEY:
        result = await openai_classification(content, metadata)
        if result:
            return result

    # 폴백: 기본 분류
    return rule_based_classification(content, metadata)


async def openai_classification(content: str, metadata: Optional[dict] = None) -> Optional[dict]:
    """OpenAI API로 메모 분류"""

    metadata_info = ""
    if metadata:
        metadata_info = f"메타데이터: {json.dumps(metadata, ensure_ascii=False)}"

    prompt = CLASSIFICATION_PROMPT.format(
        content=content,
        metadata_info=metadata_info
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 200,
                    "response_format": {"type": "json_object"}
                },
                timeout=10.0
            )

            if response.status_code != 200:
                print(f"[Classifier] Memo API Error: {response.status_code}")
                return None

            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            return json.loads(answer)

    except Exception as e:
        print(f"[Classifier] Memo Classification Error: {e}")

    return None


def rule_based_classification(content: str, metadata: dict = None) -> dict:
    """규칙 기반 분류 (폴백용)"""
    content_lower = content.lower()

    # URL 기반 분류
    if metadata and metadata.get("type"):
        url_type = metadata["type"]
        title = metadata.get("title", content[:30])[:30]

        type_to_category = {
            "youtube": "영상", "instagram": "영상", "tiktok": "영상", "netflix": "영상",
            "spotify": "음악", "melon": "음악", "apple_music": "음악",
            "airbnb": "여행", "booking": "여행", "yanolja": "여행",
            "kakao_map": "맛집", "naver_map": "맛집", "mango_plate": "맛집",
            "coupang": "쇼핑", "musinsa": "쇼핑", "zigzag": "쇼핑",
            "inflearn": "학습", "udemy": "학습", "coursera": "학습",
            "naver_blog": "읽을거리", "tistory": "읽을거리", "velog": "읽을거리"
        }

        if url_type in type_to_category:
            return {"category": type_to_category[url_type], "tags": [url_type], "summary": title}

    # 키워드 기반
    keywords = {
        "영상": ["youtube", "youtu.be", "영상", "동영상", "넷플릭스"],
        "음악": ["spotify", "멜론", "음악", "노래", "플레이리스트"],
        "맛집": ["맛집", "음식", "카페", "식당", "레스토랑"],
        "쇼핑": ["쇼핑", "구매", "상품", "쿠팡", "할인"],
        "여행": ["여행", "호텔", "항공", "숙소", "관광"],
        "할일": ["해야", "할일", "예약", "약속", "회의", "내일", "오전", "오후"],
        "학습": ["강의", "공부", "코딩", "tutorial", "교육"],
        "건강": ["운동", "헬스", "다이어트", "건강"],
        "읽을거리": ["블로그", "뉴스", "기사", "글"]
    }

    for category, kws in keywords.items():
        if any(kw in content_lower for kw in kws):
            return {"category": category, "tags": [category], "summary": content[:30]}

    return {"category": "기타", "tags": [], "summary": content[:30]}


# get_category_emoji는 constants.py에서 import하여 재export
from .constants import get_category_emoji, CATEGORY_EMOJIS, CATEGORIES
