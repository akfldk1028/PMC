# 외부 API 연동

## 1. 개요

챗노트가 사용하는 외부 API 목록:

| API | 용도 | 필수 |
|-----|------|------|
| Kanana API | AI 분류/요약 | O |
| 카카오 OAuth | 사용자 인증 | O |
| 나에게 보내기 | 결과 전송 | O |
| OG 태그 추출 | URL 메타데이터 | O |

---

## 2. Kanana API

### 2.1 개요

카카오의 LLM API. 메모 분류 및 요약에 사용.

| 항목 | 값 |
|------|-----|
| 엔드포인트 | `https://api.kakao.com/v1/kanana/chat` |
| 인증 | Bearer Token |
| 모델 | `kanana-2-30b` |

### 2.2 요청 형식

```bash
curl -X POST https://api.kakao.com/v1/kanana/chat \
  -H "Authorization: Bearer {KANANA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kanana-2-30b",
    "messages": [
      {"role": "user", "content": "..."}
    ]
  }'
```

### 2.3 응답 형식

```json
{
    "id": "chatcmpl-xxx",
    "object": "chat.completion",
    "created": 1234567890,
    "model": "kanana-2-30b",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "{\"category\": \"영상\", \"tags\": [...], \"summary\": \"...\"}"
            },
            "finish_reason": "stop"
        }
    ]
}
```

### 2.4 구현 코드

```python
# lib/kanana.py
import httpx
import os
import json
from typing import Optional

KANANA_API_URL = "https://api.kakao.com/v1/kanana/chat"
KANANA_API_KEY = os.environ.get("KANANA_API_KEY")

# 분류 프롬프트
CLASSIFICATION_PROMPT = """다음 메모를 분석해서 JSON으로 반환해줘.

메모: {content}
{metadata_info}

응답 형식 (JSON만 반환):
{{
    "category": "영상/맛집/쇼핑/할일/아이디어/읽을거리/기타 중 하나",
    "tags": ["태그1", "태그2", "태그3"],
    "summary": "한줄 요약 (30자 이내)"
}}

카테고리 기준:
- 영상: 유튜브, 동영상 콘텐츠
- 맛집: 음식점, 카페, 맛집 정보
- 쇼핑: 상품, 구매, 쇼핑몰
- 할일: 해야 할 일, 일정, 약속
- 아이디어: 아이디어, 생각, 기획
- 읽을거리: 블로그, 뉴스, 기사
- 기타: 위에 해당 안 되는 것"""


async def analyze_memo(content: str, metadata: Optional[dict] = None) -> dict:
    """메모 분석 (분류 + 태그 + 요약)"""

    # 메타데이터 정보 구성
    metadata_info = ""
    if metadata:
        metadata_info = f"메타데이터: {json.dumps(metadata, ensure_ascii=False)}"

    prompt = CLASSIFICATION_PROMPT.format(
        content=content,
        metadata_info=metadata_info
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            KANANA_API_URL,
            headers={
                "Authorization": f"Bearer {KANANA_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "kanana-2-30b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,  # 일관된 분류를 위해 낮게
                "max_tokens": 200
            },
            timeout=10.0
        )

        result = response.json()

        # 응답 파싱
        answer = result["choices"][0]["message"]["content"]

        # JSON 추출 (응답에 부가 텍스트가 있을 수 있음)
        try:
            # JSON 부분만 추출
            json_start = answer.find("{")
            json_end = answer.rfind("}") + 1
            json_str = answer[json_start:json_end]
            return json.loads(json_str)
        except:
            # 파싱 실패 시 기본값
            return {
                "category": "기타",
                "tags": [],
                "summary": content[:30]
            }


async def generate_summary(memos: list) -> str:
    """여러 메모 요약 생성"""

    memo_list = "\n".join([f"- {m['summary']}" for m in memos])

    prompt = f"""다음 메모들을 카테고리별로 정리해서 요약해줘.

메모 목록:
{memo_list}

간결하게 정리해줘."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            KANANA_API_URL,
            headers={
                "Authorization": f"Bearer {KANANA_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "kanana-2-30b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 500
            },
            timeout=15.0
        )

        result = response.json()
        return result["choices"][0]["message"]["content"]
```

### 2.5 에러 처리

```python
class KananaAPIError(Exception):
    pass

async def analyze_memo_safe(content: str, metadata: dict = None) -> dict:
    """에러 처리 포함 분석"""
    try:
        return await analyze_memo(content, metadata)
    except httpx.TimeoutException:
        # 타임아웃 시 기본 분류
        return fallback_classification(content, metadata)
    except Exception as e:
        print(f"Kanana API Error: {e}")
        return fallback_classification(content, metadata)


def fallback_classification(content: str, metadata: dict = None) -> dict:
    """API 실패 시 규칙 기반 분류"""
    content_lower = content.lower()

    # URL 기반 분류
    if metadata and metadata.get("type"):
        url_type = metadata["type"]
        if url_type == "youtube":
            return {"category": "영상", "tags": ["유튜브"], "summary": metadata.get("title", content[:30])}
        elif url_type == "instagram":
            return {"category": "영상", "tags": ["인스타그램"], "summary": "인스타그램 콘텐츠"}

    # 키워드 기반 분류
    if any(kw in content_lower for kw in ["youtube", "youtu.be", "영상", "동영상"]):
        return {"category": "영상", "tags": ["영상"], "summary": content[:30]}
    elif any(kw in content_lower for kw in ["맛집", "음식", "카페", "식당"]):
        return {"category": "맛집", "tags": ["맛집"], "summary": content[:30]}
    elif any(kw in content_lower for kw in ["쇼핑", "구매", "상품", "쿠팡"]):
        return {"category": "쇼핑", "tags": ["쇼핑"], "summary": content[:30]}
    elif any(kw in content_lower for kw in ["해야", "할일", "TODO", "예약"]):
        return {"category": "할일", "tags": ["할일"], "summary": content[:30]}

    return {"category": "기타", "tags": [], "summary": content[:30]}
```

---

## 3. 카카오 OAuth

### 3.1 개요

PlayMCP에서 사용자 인증 시 카카오 OAuth 사용.

| 항목 | 값 |
|------|-----|
| 인가 URL | `https://kauth.kakao.com/oauth/authorize` |
| 토큰 URL | `https://kauth.kakao.com/oauth/token` |
| 사용자 정보 | `https://kapi.kakao.com/v2/user/me` |

### 3.2 OAuth 플로우

```
[1] 사용자가 PlayMCP에서 MCP 사용 시작
         ↓
[2] PlayMCP Gateway가 OAuth 인가 요청
    GET /oauth/authorize?client_id=...&redirect_uri=...&scope=talk_message
         ↓
[3] 사용자 동의 후 Authorization Code 발급
         ↓
[4] MCP 서버가 Access Token 교환
    POST /oauth/token
         ↓
[5] Access Token으로 API 호출 가능
```

### 3.3 필요 Scope

| Scope | 용도 |
|-------|------|
| `talk_message` | 나에게 보내기 API 사용 |
| `profile_nickname` | 사용자 이름 표시 (선택) |

### 3.4 토큰 관리

```python
# lib/oauth.py
import httpx
import os
from datetime import datetime, timedelta

KAKAO_CLIENT_ID = os.environ.get("KAKAO_CLIENT_ID")
KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET")
KAKAO_REDIRECT_URI = os.environ.get("KAKAO_REDIRECT_URI")

async def exchange_code_for_token(code: str) -> dict:
    """인가 코드를 토큰으로 교환"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://kauth.kakao.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": KAKAO_CLIENT_ID,
                "client_secret": KAKAO_CLIENT_SECRET,
                "redirect_uri": KAKAO_REDIRECT_URI,
                "code": code
            }
        )

        return response.json()
        # {
        #     "access_token": "...",
        #     "token_type": "bearer",
        #     "refresh_token": "...",
        #     "expires_in": 21599,
        #     "scope": "talk_message",
        #     "refresh_token_expires_in": 5183999
        # }


async def refresh_token(refresh_token: str) -> dict:
    """토큰 갱신"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://kauth.kakao.com/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": KAKAO_CLIENT_ID,
                "client_secret": KAKAO_CLIENT_SECRET,
                "refresh_token": refresh_token
            }
        )

        return response.json()


async def get_user_info(access_token: str) -> dict:
    """사용자 정보 조회"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        return response.json()
        # {
        #     "id": 1234567890,
        #     "properties": {"nickname": "홍길동"},
        #     ...
        # }
```

---

## 4. 나에게 보내기 API

### 4.1 개요

사용자의 "나와의 채팅방"에 메시지 전송.

| 항목 | 값 |
|------|-----|
| 엔드포인트 | `POST https://kapi.kakao.com/v2/api/talk/memo/default/send` |
| 인증 | Bearer {access_token} |
| Content-Type | `application/x-www-form-urlencoded` |

### 4.2 템플릿 종류

| 타입 | 설명 |
|------|------|
| text | 텍스트 메시지 |
| feed | 피드형 카드 |
| list | 리스트형 카드 |
| commerce | 상품형 카드 |

### 4.3 구현 코드

```python
# lib/kakao.py
import httpx
import json

KAKAO_MEMO_API = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

async def send_to_me(access_token: str, message: str, link_url: str = None) -> dict:
    """나에게 보내기 - 텍스트"""

    template = {
        "object_type": "text",
        "text": message,
        "link": {
            "web_url": link_url or "https://playmcp.kakao.com",
            "mobile_web_url": link_url or "https://playmcp.kakao.com"
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            KAKAO_MEMO_API,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "template_object": json.dumps(template, ensure_ascii=False)
            }
        )

        return response.json()


async def send_memo_card(access_token: str, memo: dict) -> dict:
    """나에게 보내기 - 피드 카드"""

    template = {
        "object_type": "feed",
        "content": {
            "title": f"{get_emoji(memo['category'])} {memo['category']}",
            "description": memo["summary"],
            "image_url": memo.get("metadata", {}).get("image", ""),
            "link": {
                "web_url": memo.get("url", "https://playmcp.kakao.com"),
                "mobile_web_url": memo.get("url", "https://playmcp.kakao.com")
            }
        },
        "buttons": [
            {
                "title": "원본 보기",
                "link": {
                    "web_url": memo.get("url", "https://playmcp.kakao.com"),
                    "mobile_web_url": memo.get("url", "https://playmcp.kakao.com")
                }
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            KAKAO_MEMO_API,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "template_object": json.dumps(template, ensure_ascii=False)
            }
        )

        return response.json()


def get_emoji(category: str) -> str:
    """카테고리 이모지"""
    emojis = {
        "영상": "📺",
        "맛집": "🍽️",
        "쇼핑": "🛒",
        "할일": "📅",
        "아이디어": "💡",
        "읽을거리": "📰",
        "기타": "📌"
    }
    return emojis.get(category, "📌")
```

### 4.4 응답

성공 시:
```json
{"result_code": 0}
```

실패 시:
```json
{
    "msg": "error message",
    "code": -401  // 토큰 만료 등
}
```

---

## 5. OG 태그 추출

### 5.1 개요

URL에서 Open Graph 메타데이터 추출.

### 5.2 구현 코드

```python
# lib/metadata.py
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re

# 플랫폼별 도메인
PLATFORM_DOMAINS = {
    "youtube": ["youtube.com", "youtu.be"],
    "instagram": ["instagram.com"],
    "naver": ["naver.com", "blog.naver.com", "m.blog.naver.com"],
    "tistory": ["tistory.com"],
    "velog": ["velog.io"],
    "brunch": ["brunch.co.kr"],
    "coupang": ["coupang.com"],
}

async def extract_metadata(url: str) -> dict:
    """URL에서 메타데이터 추출"""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(
                url,
                timeout=5.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; ChatNoteBot/1.0)"
                }
            )

            soup = BeautifulSoup(response.text, 'html.parser')

            # OG 태그 추출
            og_title = soup.find("meta", property="og:title")
            og_description = soup.find("meta", property="og:description")
            og_image = soup.find("meta", property="og:image")
            og_site_name = soup.find("meta", property="og:site_name")

            # 일반 title, description
            title_tag = soup.find("title")
            desc_tag = soup.find("meta", attrs={"name": "description"})

            # 결과 구성
            return {
                "title": (og_title["content"] if og_title else
                         (title_tag.text.strip() if title_tag else "")),
                "description": (og_description["content"] if og_description else
                               (desc_tag["content"] if desc_tag else "")),
                "image": og_image["content"] if og_image else "",
                "site_name": og_site_name["content"] if og_site_name else "",
                "url": url,
                "type": detect_platform(url)
            }

    except Exception as e:
        print(f"Metadata extraction error: {e}")
        return {
            "url": url,
            "type": detect_platform(url)
        }


def detect_platform(url: str) -> str:
    """URL 플랫폼 감지"""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    for platform, domains in PLATFORM_DOMAINS.items():
        if any(d in domain for d in domains):
            return platform

    return "link"


async def extract_youtube_info(url: str) -> dict:
    """유튜브 추가 정보 추출"""
    # video_id 추출
    video_id = None
    if "youtu.be" in url:
        video_id = url.split("/")[-1].split("?")[0]
    elif "youtube.com" in url:
        match = re.search(r"v=([^&]+)", url)
        if match:
            video_id = match.group(1)

    metadata = await extract_metadata(url)
    metadata["video_id"] = video_id

    return metadata
```

---

## 6. 에러 코드

### 카카오 API 공통

| 코드 | 설명 | 대응 |
|------|------|------|
| -1 | 서버 오류 | 재시도 |
| -2 | 잘못된 요청 | 파라미터 확인 |
| -401 | 토큰 만료 | 토큰 갱신 |
| -402 | 접근 불가 | 권한 확인 |

### 에러 핸들링

```python
class KakaoAPIError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")

async def call_kakao_api_safe(func, *args, **kwargs):
    """공통 에러 핸들링"""
    try:
        result = await func(*args, **kwargs)

        if isinstance(result, dict) and result.get("code"):
            code = result["code"]

            if code == -401:
                # 토큰 갱신 시도
                # await refresh_and_retry(...)
                raise KakaoAPIError(code, "토큰 만료")

            raise KakaoAPIError(code, result.get("msg", "Unknown error"))

        return result

    except httpx.TimeoutException:
        raise KakaoAPIError(-1, "API 타임아웃")
    except Exception as e:
        raise KakaoAPIError(-1, str(e))
```

---

## 7. 환경 변수

```bash
# .env

# Kanana API
KANANA_API_KEY=your_kanana_api_key

# 카카오 OAuth
KAKAO_CLIENT_ID=your_rest_api_key
KAKAO_CLIENT_SECRET=your_client_secret
KAKAO_REDIRECT_URI=https://memomate.vercel.app/oauth/callback

# Database
DATABASE_URL=sqlite:///data/memomate.db
# 또는 Supabase
# DATABASE_URL=postgresql://...
```

---

## 8. 다음 단계

- 실제 코드 구현
- Vercel 배포
- 카카오 채널 및 챗봇 설정
- PlayMCP 등록
