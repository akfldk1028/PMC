"""
메타데이터 추출 모듈
URL에서 OG 태그, 제목 등 추출
"""
import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Optional

# 플랫폼별 도메인 (확장)
PLATFORM_DOMAINS = {
    # 영상
    "youtube": ["youtube.com", "youtu.be"],
    "instagram": ["instagram.com"],
    "tiktok": ["tiktok.com"],
    "netflix": ["netflix.com"],
    "twitch": ["twitch.tv"],
    "vimeo": ["vimeo.com"],
    # 음악
    "spotify": ["spotify.com", "open.spotify.com"],
    "melon": ["melon.com"],
    "apple_music": ["music.apple.com"],
    "soundcloud": ["soundcloud.com"],
    "bugs": ["bugs.co.kr"],
    # 블로그/읽을거리
    "naver_blog": ["blog.naver.com", "m.blog.naver.com"],
    "tistory": ["tistory.com"],
    "velog": ["velog.io"],
    "brunch": ["brunch.co.kr"],
    "medium": ["medium.com"],
    "substack": ["substack.com"],
    # 쇼핑
    "coupang": ["coupang.com"],
    "musinsa": ["musinsa.com"],
    "zigzag": ["zigzag.kr", "croquis.com"],
    "gmarket": ["gmarket.co.kr"],
    "11st": ["11st.co.kr"],
    "amazon": ["amazon.com", "amazon.co.kr"],
    "aliexpress": ["aliexpress.com"],
    # 여행
    "airbnb": ["airbnb.com", "airbnb.co.kr"],
    "booking": ["booking.com"],
    "yanolja": ["yanolja.com"],
    "goodchoice": ["goodchoice.kr"],
    "agoda": ["agoda.com"],
    "expedia": ["expedia.com", "expedia.co.kr"],
    # 맛집
    "kakao_map": ["map.kakao.com", "place.map.kakao.com"],
    "naver_map": ["map.naver.com", "naver.me"],
    "mango_plate": ["mangoplate.com"],
    "diningcode": ["diningcode.com"],
    # 학습/개발
    "inflearn": ["inflearn.com"],
    "udemy": ["udemy.com"],
    "coursera": ["coursera.org"],
    "class101": ["class101.net"],
    "github": ["github.com", "githubusercontent.com"],
    "gitlab": ["gitlab.com"],
    "stackoverflow": ["stackoverflow.com"],
    "notion": ["notion.so", "notion.site"],
    "figma": ["figma.com"],
    "codepen": ["codepen.io"],
    "codesandbox": ["codesandbox.io"],
    "replit": ["replit.com"],
    "huggingface": ["huggingface.co"],
    "kaggle": ["kaggle.com"],
    # 문서/협업
    "google_docs": ["docs.google.com", "drive.google.com", "sheets.google.com"],
    "dropbox": ["dropbox.com"],
    "slack": ["slack.com"],
    "discord": ["discord.com", "discord.gg"],
    "trello": ["trello.com"],
    "jira": ["atlassian.net"],
    # 기타
    "naver": ["naver.com"],
    "kakao": ["kakao.com"],
    "twitter": ["twitter.com", "x.com"],
    "facebook": ["facebook.com", "fb.com"],
    "linkedin": ["linkedin.com"],
    "reddit": ["reddit.com"],
    "wikipedia": ["wikipedia.org"],
    # 정부/공공
    "gov": ["go.kr", "korea.kr"],
    "hometax": ["hometax.go.kr"],
    "wetax": ["wetax.go.kr"],
    "gov24": ["gov.kr"],
    # 금융
    "bank": ["kbstar.com", "shinhan.com", "wooribank.com", "hanabank.com", "ibk.co.kr"],
    "card": ["card.kbcard.com", "shinhancard.com", "wooricard.com"],
    # 뉴스
    "news": ["news.naver.com", "news.daum.net", "chosun.com", "donga.com", "joins.com", "hani.co.kr", "khan.co.kr"],
}

# URL 패턴 (더 정교한 패턴)
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


def extract_youtube_id(url: str) -> Optional[str]:
    """YouTube URL에서 video_id 추출"""
    if "youtu.be" in url:
        path = url.split("youtu.be/")[-1]
        return path.split("?")[0].split("/")[0]
    elif "youtube.com" in url:
        # /watch?v=xxx 형식
        match = re.search(r"v=([^&]+)", url)
        if match:
            return match.group(1)
        # /embed/xxx 또는 /v/xxx 형식
        match = re.search(r"(?:embed|v)/([^/?]+)", url)
        if match:
            return match.group(1)
    return None


def normalize_image_url(image_url: str, base_url: str) -> Optional[str]:
    """이미지 URL 정규화 (상대경로 → 절대경로)"""
    if not image_url:
        return None

    # 이미 절대 경로면 그대로 반환
    if image_url.startswith(('http://', 'https://')):
        return image_url

    # 프로토콜 없이 //로 시작하는 경우
    if image_url.startswith('//'):
        return 'https:' + image_url

    # 상대 경로 → 절대 경로 변환
    from urllib.parse import urljoin
    return urljoin(base_url, image_url)


def get_favicon_url(url: str) -> str:
    """사이트 favicon URL 생성 (Google Favicon API 사용)"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        # Google Favicon API - 안정적이고 대부분 사이트 지원
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    except Exception:
        return ""


def get_default_thumbnail(platform: str) -> Optional[str]:
    """플랫폼별 기본 썸네일 URL (공개 아이콘)"""
    # 플랫폼별 기본 이미지 (CDN에서 가져옴)
    DEFAULT_THUMBNAILS = {
        "youtube": "https://www.youtube.com/img/desktop/yt_1200.png",
        "instagram": "https://www.instagram.com/static/images/ico/favicon-192.png/68d99ba29cc8.png",
        "github": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
        "naver_blog": "https://ssl.pstatic.net/static/blog/favicon/blog_favicon_192.png",
        "velog": "https://velog.velcdn.com/images/velog/velog.png",
        "notion": "https://www.notion.so/images/logo-ios.png",
        "spotify": "https://open.spotifycdn.com/cdn/images/favicon32.8e66b099.png",
    }
    return DEFAULT_THUMBNAILS.get(platform)


def get_domain_name(url: str) -> str:
    """URL에서 깔끔한 도메인명 추출 (www 제거, 대문자화)"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # www. 제거
        if domain.startswith("www."):
            domain = domain[4:]
        # 첫 글자 대문자화 (hometax.go.kr → Hometax.go.kr)
        parts = domain.split(".")
        if parts:
            parts[0] = parts[0].capitalize()
        return ".".join(parts)
    except Exception:
        return ""


def extract_urls(text: str) -> list:
    """텍스트에서 URL 추출 (끝에 붙은 특수문자 정리)"""
    urls = URL_PATTERN.findall(text)
    cleaned = []
    for url in urls:
        # URL 끝의 한글, 문장부호 제거
        url = url.rstrip('.,;:!?)"\'』」, 。、')
        # 괄호 균형 맞추기
        if url.count('(') < url.count(')'):
            url = url.rstrip(')')
        if url:
            cleaned.append(url)
    return cleaned


def has_url(text: str) -> bool:
    """URL 포함 여부"""
    return bool(URL_PATTERN.search(text))


async def extract_metadata(url: str) -> dict:
    """URL에서 메타데이터 추출 (모든 사이트 지원, 영상 썸네일 개선)"""

    platform = detect_platform(url)

    # YouTube 특수 처리 - 직접 썸네일 URL 생성 (더 안정적)
    youtube_thumbnail = None
    youtube_id = None
    if platform == "youtube":
        youtube_id = extract_youtube_id(url)
        if youtube_id:
            # hqdefault는 항상 존재 (maxresdefault는 없을 수 있음)
            youtube_thumbnail = f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg"

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(
                url,
                timeout=10.0,  # 느린 사이트 대응
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
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

            # 이미지 URL 정규화 (상대 경로 → 절대 경로)
            raw_image = _get_content(og_image)
            image_url = normalize_image_url(raw_image, url)

            # YouTube일 때 og:image가 없거나 이상하면 직접 생성한 썸네일 사용
            if platform == "youtube" and youtube_thumbnail:
                if not image_url or "ytimg.com" not in image_url:
                    image_url = youtube_thumbnail

            # 이미지가 없으면 폴백: 플랫폼 기본 → favicon
            final_image = image_url
            if not final_image:
                final_image = get_default_thumbnail(platform)
            if not final_image:
                final_image = get_favicon_url(url)

            # 제목 폴백: OG → title 태그 → 도메인명
            title = _get_content(og_title) or _get_text(title_tag)
            if not title:
                title = get_domain_name(url)

            # 사이트명 폴백: OG → 도메인명
            site_name = _get_content(og_site_name)
            if not site_name:
                site_name = get_domain_name(url)

            # 결과 구성
            result = {
                "title": title or "",
                "description": _get_content(og_description) or _get_content(desc_tag) or "",
                "image": final_image or "",
                "thumbnail": final_image or "",  # 호환성: image와 thumbnail 둘 다
                "site_name": site_name or "",
                "url": url,
                "type": platform
            }

            # YouTube video_id 추가 (필요시 활용)
            if youtube_id:
                result["video_id"] = youtube_id

            return result

    except Exception as e:
        print(f"Metadata extraction error: {e}")
        # 실패해도 썸네일은 최대한 보장
        fallback_image = None
        if youtube_thumbnail:
            fallback_image = youtube_thumbnail
        elif platform:
            fallback_image = get_default_thumbnail(platform)
        if not fallback_image:
            fallback_image = get_favicon_url(url)

        result = {
            "url": url,
            "type": platform,
            "image": fallback_image or "",
            "thumbnail": fallback_image or ""
        }
        if youtube_id:
            result["video_id"] = youtube_id
        return result


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
