"""
카카오 API 모듈
나에게 보내기, OAuth
"""
import os
import json
import httpx
from typing import Optional

KAKAO_MEMO_API = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
KAKAO_TOKEN_API = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_API = "https://kapi.kakao.com/v2/user/me"

KAKAO_CLIENT_ID = os.environ.get("KAKAO_CLIENT_ID", "")
KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "")
KAKAO_REDIRECT_URI = os.environ.get("KAKAO_REDIRECT_URI", "")


async def send_to_me(access_token: str, message: str, link_url: str = None) -> dict:
    """나에게 보내기 - 텍스트"""

    if not access_token:
        return {"error": "No access token"}

    template = {
        "object_type": "text",
        "text": message,
        "link": {
            "web_url": link_url or "https://playmcp.kakao.com",
            "mobile_web_url": link_url or "https://playmcp.kakao.com"
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                KAKAO_MEMO_API,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "template_object": json.dumps(template, ensure_ascii=False)
                },
                timeout=10.0
            )

            return response.json()

    except Exception as e:
        print(f"Send to me error: {e}")
        return {"error": str(e)}


async def send_memo_card(access_token: str, memo: dict) -> dict:
    """나에게 보내기 - 피드 카드"""

    if not access_token:
        return {"error": "No access token"}

    emoji = get_category_emoji(memo.get("category", "기타"))
    metadata = memo.get("metadata", {})

    template = {
        "object_type": "feed",
        "content": {
            "title": f"{emoji} {memo.get('category', '메모')}",
            "description": memo.get("summary", ""),
            "image_url": metadata.get("image", ""),
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

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                KAKAO_MEMO_API,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "template_object": json.dumps(template, ensure_ascii=False)
                },
                timeout=10.0
            )

            return response.json()

    except Exception as e:
        print(f"Send card error: {e}")
        return {"error": str(e)}


async def exchange_code_for_token(code: str) -> dict:
    """인가 코드를 토큰으로 교환"""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                KAKAO_TOKEN_API,
                data={
                    "grant_type": "authorization_code",
                    "client_id": KAKAO_CLIENT_ID,
                    "client_secret": KAKAO_CLIENT_SECRET,
                    "redirect_uri": KAKAO_REDIRECT_URI,
                    "code": code
                },
                timeout=10.0
            )

            return response.json()

    except Exception as e:
        print(f"Token exchange error: {e}")
        return {"error": str(e)}


async def refresh_token(refresh_token: str) -> dict:
    """토큰 갱신"""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                KAKAO_TOKEN_API,
                data={
                    "grant_type": "refresh_token",
                    "client_id": KAKAO_CLIENT_ID,
                    "client_secret": KAKAO_CLIENT_SECRET,
                    "refresh_token": refresh_token
                },
                timeout=10.0
            )

            return response.json()

    except Exception as e:
        print(f"Token refresh error: {e}")
        return {"error": str(e)}


async def get_user_info(access_token: str) -> dict:
    """사용자 정보 조회"""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                KAKAO_USER_API,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0
            )

            return response.json()

    except Exception as e:
        print(f"User info error: {e}")
        return {"error": str(e)}


def get_category_emoji(category: str) -> str:
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


def format_memo_message(analysis: dict) -> str:
    """정리된 메모 메시지 포맷"""
    emoji = get_category_emoji(analysis.get("category", "기타"))
    tags = " ".join([f"#{tag}" for tag in analysis.get("tags", [])])

    return f"""
{emoji} 메모 저장 완료!

📂 카테고리: {analysis.get("category", "기타")}
🏷️ 태그: {tags}
📝 요약: {analysis.get("summary", "")}
""".strip()
