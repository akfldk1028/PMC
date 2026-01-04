"""
메타데이터 추출 모듈
URL에서 OG 태그, 제목 등 추출
"""
import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Optional

# 플랫폼별 도메인
PLATFORM_DOMAINS = {
    # 영상
    "youtube": ["youtube.com", "youtu.be"],
    "instagram": ["instagram.com"],
    "tiktok": ["tiktok.com"],
    "netflix": ["netflix.com"],
    # 음악
    "spotify": ["spotify.com", "open.spotify.com"],
    "melon": ["melon.com"],
    "apple_music": ["music.apple.com"],
    "soundcloud": ["soundcloud.com"],
    # 블로그/읽을거리
    "naver_blog": ["blog.naver.com", "m.blog.naver.com"],
    "tistory": ["tistory.com"],
    "velog": ["velog.io"],
    "brunch": ["brunch.co.kr"],
    "medium": ["medium.com"],
    # 쇼핑
    "coupang": ["coupang.com"],
    "musinsa": ["musinsa.com"],
    "zigzag": ["zigzag.kr", "croquis.com"],
    # 여행
    "airbnb": ["airbnb.com", "airbnb.co.kr"],
    "booking": ["booking.com"],
    "yanolja": ["yanolja.com"],
    "goodchoice": ["goodchoice.kr"],  # 여기어때
    # 맛집
    "kakao_map": ["map.kakao.com", "place.map.kakao.com"],
    "naver_map": ["map.naver.com", "naver.me"],
    "mango_plate": ["mangoplate.com"],
    # 학습
    "inflearn": ["inflearn.com"],
    "udemy": ["udemy.com"],
    "coursera": ["coursera.org"],
    "class101": ["class101.net"],
    # 기타
    "naver": ["naver.com"],
    "kakao": ["kakao.com"],
}

# URL 패턴
URL_PATTERN = re.compile(r'https?://[^\s]+')


def extract_urls(text: str) -> list:
    """텍스트에서 URL 추출"""
    return URL_PATTERN.findall(text)


def has_url(text: str) -> bool:
    """URL 포함 여부"""
    return bool(URL_PATTERN.search(text))


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
                "title": _get_content(og_title) or _get_text(title_tag) or "",
                "description": _get_content(og_description) or _get_content(desc_tag) or "",
                "image": _get_content(og_image) or "",
                "site_name": _get_content(og_site_name) or "",
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
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        for platform, domains in PLATFORM_DOMAINS.items():
            if any(d in domain for d in domains):
                return platform

    except Exception:
        pass

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


def _get_content(tag) -> Optional[str]:
    """meta 태그에서 content 추출"""
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def _get_text(tag) -> Optional[str]:
    """태그에서 텍스트 추출"""
    if tag and tag.text:
        return tag.text.strip()
    return None
