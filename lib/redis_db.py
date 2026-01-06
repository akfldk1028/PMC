"""
Upstash Redis 기반 데이터베이스 모듈
서버리스 호환, 유저별 메모 관리
"""
import os
import json
import uuid
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import List, Optional

# Upstash Redis 설정
UPSTASH_REDIS_REST_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_REDIS_REST_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")


async def redis_command(*args) -> any:
    """Upstash Redis REST API 호출"""
    if not UPSTASH_REDIS_REST_URL or not UPSTASH_REDIS_REST_TOKEN:
        raise Exception("Redis 환경변수가 설정되지 않았습니다")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            UPSTASH_REDIS_REST_URL,
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"},
            json=list(args)
        )
        result = response.json()
        if "error" in result:
            raise Exception(result["error"])
        return result.get("result")


# ============ 저장 함수 ============

async def save_memo(
    user_id: str,
    content: str,
    memo_type: str,
    category: str,
    tags: List[str],
    summary: str,
    metadata: dict = None,
    reminder_at: datetime = None
) -> str:
    """메모 저장"""
    memo_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    memo = {
        "id": memo_id,
        "user_id": user_id,
        "content": content,
        "memo_type": memo_type,
        "category": category,
        "tags": tags,
        "summary": summary,
        "url": metadata.get("url") if metadata else None,
        "metadata": metadata or {},
        "created_at": now,
        "reminder_at": reminder_at.isoformat() if reminder_at else None,
        "reminder_sent": False
    }

    # 메모 저장 (Hash)
    memo_key = f"memo:{user_id}:{memo_id}"
    await redis_command("SET", memo_key, json.dumps(memo, ensure_ascii=False))

    # 유저 메모 목록에 추가 (최신순 정렬을 위해 score = timestamp)
    timestamp = datetime.now().timestamp()
    await redis_command("ZADD", f"user:{user_id}:memos", timestamp, memo_id)

    # 카테고리 인덱스에 추가
    await redis_command("SADD", f"user:{user_id}:category:{category}", memo_id)

    # 리마인더 인덱스에 추가 (있는 경우)
    if reminder_at:
        reminder_timestamp = reminder_at.timestamp()
        await redis_command("ZADD", "reminders:pending", reminder_timestamp, f"{user_id}:{memo_id}")

    return memo_id


# ============ 검색 함수 ============

async def search_memos(
    user_id: str,
    query: str,
    category: Optional[str] = None,
    limit: int = 5
) -> List[dict]:
    """메모 검색 (content, summary, tags에서 검색) - 배치 최적화"""

    # 카테고리 필터가 있으면 해당 카테고리 메모만 검색 (범위 축소)
    if category:
        memo_ids = await redis_command("SMEMBERS", f"user:{user_id}:category:{category}")
    else:
        # 최근 100개만 검색 (전체 검색 방지)
        memo_ids = await redis_command("ZREVRANGE", f"user:{user_id}:memos", 0, 99)

    if not memo_ids:
        return []

    results = []
    query_lower = query.lower()

    # 배치로 메모 조회 (한 번에 최대 20개씩)
    batch_size = 20
    for i in range(0, len(memo_ids), batch_size):
        if len(results) >= limit:
            break

        batch_ids = memo_ids[i:i + batch_size]
        batch_keys = [f"memo:{user_id}:{mid}" for mid in batch_ids]

        # MGET으로 배치 조회 (N번 호출 -> 1번 호출)
        batch_data = await redis_command("MGET", *batch_keys)

        if not batch_data:
            continue

        for memo_data in batch_data:
            if not memo_data:
                continue

            memo = json.loads(memo_data)

            # 검색어 매칭 (content, summary, tags)
            searchable = f"{memo.get('content', '')} {memo.get('summary', '')} {' '.join(memo.get('tags', []))}".lower()

            if query_lower in searchable:
                results.append(memo)
                if len(results) >= limit:
                    break

    # 카테고리 필터 사용 시 최신순 정렬
    if category:
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return results[:limit]


async def get_memos_by_category(
    user_id: str,
    category: str,
    limit: int = 10
) -> List[dict]:
    """카테고리별 메모 조회 - MGET 배치 최적화"""
    # 카테고리 인덱스에서 메모 ID 가져오기
    memo_ids = await redis_command("SMEMBERS", f"user:{user_id}:category:{category}")

    if not memo_ids:
        return []

    # MGET으로 한 번에 조회
    memo_keys = [f"memo:{user_id}:{mid}" for mid in memo_ids]
    batch_data = await redis_command("MGET", *memo_keys)

    results = []
    if batch_data:
        for memo_data in batch_data:
            if memo_data:
                results.append(json.loads(memo_data))

    # 최신순 정렬
    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return results[:limit]


async def get_memos_by_period(
    user_id: str,
    period: str
) -> List[dict]:
    """기간별 메모 조회 (확장) - MGET 배치 최적화"""
    now = datetime.now()
    end_timestamp = None  # 기본: 현재까지

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "yesterday":
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_timestamp = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    elif period == "week":
        start = now - timedelta(days=7)
    elif period == "last_week":
        start = now - timedelta(days=14)
        end_timestamp = (now - timedelta(days=7)).timestamp()
    elif period == "month":
        start = now - timedelta(days=30)
    elif period == "last_month":
        start = now - timedelta(days=60)
        end_timestamp = (now - timedelta(days=30)).timestamp()
    elif period == "all":
        start = now - timedelta(days=365)  # 1년치
    else:
        start = now - timedelta(days=7)

    start_timestamp = start.timestamp()
    max_score = end_timestamp if end_timestamp else "+inf"

    # 기간 내 메모 ID 가져오기
    memo_ids = await redis_command("ZREVRANGEBYSCORE", f"user:{user_id}:memos", max_score, start_timestamp)

    if not memo_ids:
        return []

    # MGET으로 한 번에 조회
    memo_keys = [f"memo:{user_id}:{mid}" for mid in memo_ids]
    batch_data = await redis_command("MGET", *memo_keys)

    results = []
    if batch_data:
        for memo_data in batch_data:
            if memo_data:
                results.append(json.loads(memo_data))

    return results


async def get_user_stats(user_id: str) -> dict:
    """유저 통계 조회 (병렬 처리 최적화)"""
    from .constants import CATEGORIES
    now = datetime.now()

    # 기간별 timestamp 계산
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    week_start = (now - timedelta(days=7)).timestamp()
    month_start = (now - timedelta(days=30)).timestamp()
    now_timestamp = now.timestamp()

    memos_key = f"user:{user_id}:memos"

    # ========== 모든 Redis 호출을 병렬로 실행 ==========
    # 기존: 15개 순차 호출 (~1.5초) → 병렬: 1번에 (~0.2초)

    tasks = [
        # 기본 통계 (4개)
        redis_command("ZCARD", memos_key),
        redis_command("ZCOUNT", memos_key, str(int(today_start)), str(int(now_timestamp))),
        redis_command("ZCOUNT", memos_key, str(int(week_start)), str(int(now_timestamp))),
        redis_command("ZCOUNT", memos_key, str(int(month_start)), str(int(now_timestamp))),
    ]

    # 카테고리별 SCARD (11개)
    for cat in CATEGORIES:
        tasks.append(redis_command("SCARD", f"user:{user_id}:category:{cat}"))

    # 병렬 실행
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 결과 파싱
    total = results[0] if not isinstance(results[0], Exception) else 0
    today_count = results[1] if not isinstance(results[1], Exception) else 0
    week_count = results[2] if not isinstance(results[2], Exception) else 0
    month_count = results[3] if not isinstance(results[3], Exception) else 0

    # 카테고리별 통계 파싱
    by_category = {}
    for i, cat in enumerate(CATEGORIES):
        count = results[4 + i]
        if not isinstance(count, Exception) and count and count > 0:
            by_category[cat] = count

    return {
        "total": total or 0,
        "today": today_count or 0,
        "week": week_count or 0,
        "month": month_count or 0,
        "by_category": by_category
    }


async def get_recent_memos(
    user_id: str,
    limit: int = 5
) -> List[dict]:
    """최근 메모 조회 - MGET 배치 최적화"""
    # 최신순으로 limit개 가져오기
    memo_ids = await redis_command("ZREVRANGE", f"user:{user_id}:memos", 0, limit - 1)

    if not memo_ids:
        return []

    # MGET으로 한 번에 조회
    memo_keys = [f"memo:{user_id}:{mid}" for mid in memo_ids]
    batch_data = await redis_command("MGET", *memo_keys)

    results = []
    if batch_data:
        for memo_data in batch_data:
            if memo_data:
                results.append(json.loads(memo_data))

    return results


# ============ 삭제/수정 함수 ============

async def delete_memo(user_id: str, memo_id: str) -> bool:
    """메모 삭제"""
    # 메모 데이터 조회 (카테고리 확인용)
    memo_key = f"memo:{user_id}:{memo_id}"
    memo_data = await redis_command("GET", memo_key)

    if not memo_data:
        return False

    memo = json.loads(memo_data)
    category = memo.get("category", "기타")

    # 1. 메모 데이터 삭제
    await redis_command("DEL", memo_key)

    # 2. 유저 메모 목록에서 제거
    await redis_command("ZREM", f"user:{user_id}:memos", memo_id)

    # 3. 카테고리 인덱스에서 제거
    await redis_command("SREM", f"user:{user_id}:category:{category}", memo_id)

    return True


async def update_memo(
    user_id: str,
    memo_id: str,
    summary: str = None,
    category: str = None,
    tags: List[str] = None
) -> dict:
    """메모 수정 (summary, category, tags)"""
    memo_key = f"memo:{user_id}:{memo_id}"
    memo_data = await redis_command("GET", memo_key)

    if not memo_data:
        return None

    memo = json.loads(memo_data)
    old_category = memo.get("category", "기타")

    # 필드 업데이트
    if summary is not None:
        memo["summary"] = summary
    if tags is not None:
        memo["tags"] = tags
    if category is not None and category != old_category:
        # 카테고리 변경 시 인덱스 업데이트
        await redis_command("SREM", f"user:{user_id}:category:{old_category}", memo_id)
        await redis_command("SADD", f"user:{user_id}:category:{category}", memo_id)
        memo["category"] = category

    memo["updated_at"] = datetime.now().isoformat()

    # 저장
    await redis_command("SET", memo_key, json.dumps(memo, ensure_ascii=False))

    return memo


async def get_memo_by_id(user_id: str, memo_id: str) -> dict:
    """메모 ID로 조회"""
    memo_key = f"memo:{user_id}:{memo_id}"
    memo_data = await redis_command("GET", memo_key)

    if not memo_data:
        return None

    return json.loads(memo_data)


async def get_memo_by_short_id(user_id: str, short_id: str) -> dict:
    """짧은 ID (8자리)로 메모 조회 - UUID prefix 매칭"""
    if not short_id or len(short_id) < 4:
        return None

    short_id_lower = short_id.lower()

    # 최근 메모 100개에서 검색 (prefix 매칭)
    memo_ids = await redis_command("ZREVRANGE", f"user:{user_id}:memos", 0, 99)

    if not memo_ids:
        return None

    # prefix가 일치하는 메모 찾기
    for memo_id in memo_ids:
        if memo_id.lower().startswith(short_id_lower):
            return await get_memo_by_id(user_id, memo_id)

    return None


# ============ 사용자 함수 ============

async def get_or_create_user(kakao_id: str) -> dict:
    """사용자 조회 또는 생성"""
    user_key = f"user:{kakao_id}"
    user_data = await redis_command("GET", user_key)

    if user_data:
        return json.loads(user_data)

    # 새 사용자 생성
    user_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    user = {
        "id": user_id,
        "kakao_id": kakao_id,
        "created_at": now,
        "updated_at": now
    }

    await redis_command("SET", user_key, json.dumps(user, ensure_ascii=False))
    return user


# ============ 리마인더 함수 ============

async def get_pending_reminders() -> List[dict]:
    """
    현재 시간 이전의 미발송 리마인더 조회
    Returns: [{"user_id": str, "memo_id": str, "memo": dict}, ...]
    """
    now_timestamp = datetime.now().timestamp()

    # 현재 시간까지의 리마인더 가져오기 (score = reminder_at timestamp)
    pending = await redis_command("ZRANGEBYSCORE", "reminders:pending", 0, now_timestamp)

    if not pending:
        return []

    results = []
    for item in pending:
        # item = "user_id:memo_id"
        parts = item.split(":", 1)
        if len(parts) != 2:
            continue

        user_id, memo_id = parts
        memo = await get_memo_by_id(user_id, memo_id)

        if memo and not memo.get("reminder_sent", False):
            results.append({
                "user_id": user_id,
                "memo_id": memo_id,
                "memo": memo
            })

    return results


async def mark_reminder_sent(user_id: str, memo_id: str) -> bool:
    """리마인더 발송 완료 처리"""
    memo_key = f"memo:{user_id}:{memo_id}"
    memo_data = await redis_command("GET", memo_key)

    if not memo_data:
        return False

    memo = json.loads(memo_data)
    memo["reminder_sent"] = True
    memo["reminder_sent_at"] = datetime.now().isoformat()

    # 메모 업데이트
    await redis_command("SET", memo_key, json.dumps(memo, ensure_ascii=False))

    # pending 목록에서 제거
    await redis_command("ZREM", "reminders:pending", f"{user_id}:{memo_id}")

    return True


async def get_user_reminders(user_id: str, include_sent: bool = False) -> List[dict]:
    """유저의 리마인더 목록 조회"""
    # 할일 카테고리에서 리마인더가 있는 메모 조회
    memos = await get_memos_by_category(user_id, "할일", limit=50)

    reminders = []
    for memo in memos:
        if memo.get("reminder_at"):
            if include_sent or not memo.get("reminder_sent", False):
                reminders.append(memo)

    # 리마인더 시간순 정렬
    reminders.sort(key=lambda x: x.get("reminder_at", ""))
    return reminders


# ============ 시드 데이터 ============

async def seed_demo_data(user_id: str = "demo_user") -> int:
    """테스트 데이터 시드"""
    test_memos = [
        # 영상
        {"content": "https://youtube.com/watch?v=abc123", "memo_type": "link", "category": "영상",
         "tags": ["파이썬", "FastAPI"], "summary": "FastAPI 강좌 - REST API 만들기"},
        {"content": "https://youtube.com/watch?v=def456", "memo_type": "link", "category": "영상",
         "tags": ["리액트", "프론트엔드"], "summary": "React 18 새로운 기능 총정리"},
        {"content": "https://youtube.com/watch?v=ghi789", "memo_type": "link", "category": "영상",
         "tags": ["AI", "ChatGPT"], "summary": "ChatGPT API 활용법 완벽 가이드"},
        {"content": "https://youtube.com/watch?v=mcp001", "memo_type": "link", "category": "영상",
         "tags": ["MCP", "클로드"], "summary": "MCP 서버 만들기 튜토리얼"},

        # 맛집
        {"content": "강남역 맛집", "memo_type": "text", "category": "맛집",
         "tags": ["강남", "골뱅이"], "summary": "을지로골뱅이 강남점 - 골뱅이무침 맛있음"},
        {"content": "홍대 맛집", "memo_type": "text", "category": "맛집",
         "tags": ["홍대", "라멘"], "summary": "멘야하나비 - 마제소바 강추"},
        {"content": "판교 점심", "memo_type": "text", "category": "맛집",
         "tags": ["판교", "점심"], "summary": "봇나무집 - 돼지갈비 정식 12000원"},

        # 쇼핑
        {"content": "로지텍 MX Keys", "memo_type": "text", "category": "쇼핑",
         "tags": ["키보드", "로지텍"], "summary": "로지텍 MX Keys 무선 키보드 - 쿠팡 139000원"},
        {"content": "에어팟 맥스", "memo_type": "text", "category": "쇼핑",
         "tags": ["애플", "헤드폰"], "summary": "에어팟 맥스 실버 - 769000원"},

        # 할일
        {"content": "프로젝트 문서 작성", "memo_type": "text", "category": "할일",
         "tags": ["업무", "문서"], "summary": "이번 주 프로젝트 문서 작성 및 코드 리뷰"},
        {"content": "치과 예약", "memo_type": "text", "category": "할일",
         "tags": ["병원", "예약"], "summary": "목요일 오후 3시 치과 예약하기"},

        # 아이디어
        {"content": "MCP 챗봇 연동", "memo_type": "text", "category": "아이디어",
         "tags": ["MCP", "카카오톡"], "summary": "카카오톡 챗봇 + MCP 서버 연동 아이디어"},
        {"content": "사이드 프로젝트", "memo_type": "text", "category": "아이디어",
         "tags": ["창업", "앱"], "summary": "동네 커피숍 리뷰 앱 만들어볼까?"},

        # 읽을거리
        {"content": "https://velog.io/@teo/MCP", "memo_type": "link", "category": "읽을거리",
         "tags": ["MCP", "기술블로그"], "summary": "MCP 프로토콜 심층 분석 글"},
        {"content": "https://medium.com/ai-trends", "memo_type": "link", "category": "읽을거리",
         "tags": ["AI", "트렌드"], "summary": "2025년 AI 트렌드 예측"},
    ]

    count = 0
    for memo in test_memos:
        await save_memo(
            user_id=user_id,
            content=memo["content"],
            memo_type=memo["memo_type"],
            category=memo["category"],
            tags=memo["tags"],
            summary=memo["summary"],
            metadata={"url": memo["content"]} if memo["memo_type"] == "link" else {}
        )
        count += 1

    return count
