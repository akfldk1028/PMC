"""
메모 서비스 - 핵심 비즈니스 로직
skill.py와 mcp_server.py 모두 이 모듈을 사용
"""
from typing import Optional, List

# 상대 경로 import (lib 폴더 내부이므로)
from .redis_db import (
    search_memos,
    get_memos_by_category,
    get_memos_by_period,
    get_recent_memos,
    save_memo,
    delete_memo as db_delete_memo,
    update_memo as db_update_memo,
    get_memo_by_id,
    get_user_reminders,
    get_user_stats,
    get_or_create_user as db_get_or_create_user
)
from .classifier import get_category_emoji, analyze_memo, classify_intent
from .metadata import extract_metadata, extract_urls
from .datetime_parser import extract_reminder_info, format_reminder_time


async def service_search(user_id: str, query: str, category: str = None, limit: int = 5) -> dict:
    """메모 검색 서비스"""
    memos = await search_memos(user_id, query, category, limit)

    return {
        "success": True,
        "query": query,
        "count": len(memos),
        "memos": memos
    }


async def service_get_summary(user_id: str, period: str = "today", category: str = None) -> dict:
    """기간별/카테고리별 요약 서비스"""

    # 카테고리 지정 시 카테고리별 조회 (전체 표시)
    if category:
        memos = await get_memos_by_category(user_id, category, limit=100)
        period_name = f"{category}"
    else:
        memos = await get_memos_by_period(user_id, period)
        period_names = {
            "today": "오늘",
            "yesterday": "어제",
            "week": "이번 주",
            "last_week": "지난 주",
            "month": "이번 달",
            "last_month": "지난 달",
            "all": "전체"
        }
        period_name = period_names.get(period, period)

    # 카테고리별 분류
    by_category = {}
    for memo in memos:
        cat = memo.get("category", "기타")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(memo)

    return {
        "success": True,
        "period": period,
        "period_name": period_name,
        "category": category,
        "count": len(memos),
        "memos": memos,
        "by_category": by_category
    }


async def service_get_stats(user_id: str) -> dict:
    """통계 서비스"""
    stats = await get_user_stats(user_id)

    return {
        "success": True,
        "stats": stats
    }


async def get_user_top_categories(user_id: str, limit: int = 2) -> list:
    """사용자 상위 N개 카테고리 반환 (개인화된 QuickReplies용)"""
    stats = await get_user_stats(user_id)
    by_category = stats.get("by_category", {})

    if not by_category:
        # 데이터 없으면 기본값 반환
        return ["영상", "맛집"][:limit]

    # 빈도순 정렬
    sorted_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    top_cats = [cat for cat, count in sorted_cats[:limit]]

    # limit 개수 못 채우면 기본 카테고리로 보충
    defaults = ["영상", "맛집", "쇼핑", "학습"]
    while len(top_cats) < limit:
        for d in defaults:
            if d not in top_cats:
                top_cats.append(d)
                break
        if len(top_cats) >= limit:
            break

    return top_cats[:limit]


async def service_get_recent(user_id: str, limit: int = 5) -> dict:
    """최근 메모 조회 서비스"""
    memos = await get_recent_memos(user_id, limit)

    return {
        "success": True,
        "count": len(memos),
        "memos": memos
    }


async def service_save_memo(
    user_id: str,
    content: str,
    category: str = None,
    summary: str = None,
    tags: List[str] = None
) -> dict:
    """메모 저장 서비스 (AI 분류 포함)"""

    # URL 추출
    urls = extract_urls(content)
    memo_type = "url" if urls else "text"

    # 메타데이터 추출
    metadata = {}
    if urls:
        metadata = await extract_metadata(urls[0])
        metadata["url"] = urls[0]

    # AI 분류 (카테고리/태그/요약이 없으면)
    if not category or not summary:
        analysis = await analyze_memo(content, metadata)
        if not category:
            category = analysis.get("category", "기타")
        if not summary:
            summary = analysis.get("summary", content[:30])
        if not tags:
            tags = analysis.get("tags", [])

    # 할일 카테고리면 리마인더 정보 추출
    reminder_at = None
    if category == "할일":
        reminder_info = extract_reminder_info(content)
        reminder_at = reminder_info.get("reminder_at")

        if reminder_at:
            time_str = format_reminder_time(reminder_at)
            clean_text = reminder_info.get("reminder_text", content[:30])
            summary = f"{clean_text} ({time_str})"

    # 저장
    memo_id = await save_memo(
        user_id=user_id,
        content=content,
        memo_type=memo_type,
        category=category,
        tags=tags or [],
        summary=summary,
        metadata=metadata if metadata else None,
        reminder_at=reminder_at
    )

    return {
        "success": True,
        "memo_id": memo_id,
        "category": category,
        "summary": summary,
        "tags": tags or [],
        "memo_type": memo_type,
        "url": urls[0] if urls else None,
        "reminder_at": str(reminder_at) if reminder_at else None,
        "metadata": metadata if metadata else {}
    }


async def service_delete_memo(user_id: str, memo_id: str = None, keyword: str = None) -> dict:
    """메모 삭제 서비스"""

    # 키워드로 검색해서 삭제
    if keyword and not memo_id:
        memos = await search_memos(user_id, keyword, limit=1)
        if not memos:
            return {"success": False, "error": f"'{keyword}' 관련 메모가 없습니다."}
        memo = memos[0]
        memo_id = memo.get("id")
    else:
        memo = await get_memo_by_id(user_id, memo_id)
        if not memo:
            return {"success": False, "error": "메모를 찾을 수 없습니다."}

    success = await db_delete_memo(user_id, memo_id)

    if success:
        return {
            "success": True,
            "deleted_memo": memo
        }
    else:
        return {"success": False, "error": "삭제 실패"}


async def service_get_reminders(user_id: str, include_sent: bool = False) -> dict:
    """리마인더 목록 서비스"""
    reminders = await get_user_reminders(user_id, include_sent=include_sent)

    return {
        "success": True,
        "count": len(reminders),
        "reminders": reminders
    }


async def service_classify_intent(message: str) -> dict:
    """사용자 메시지 의도 분류 서비스"""
    return await classify_intent(message)


async def service_get_or_create_user(kakao_id: str) -> dict:
    """사용자 조회/생성 서비스 (레이어 규칙 준수)"""
    return await db_get_or_create_user(kakao_id)


# 포맷팅 유틸리티
def format_memo_list(memos: list, title: str = "메모 목록") -> str:
    """메모 목록을 텍스트로 포맷팅"""
    if not memos:
        return f"📭 {title}: 없음"

    lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    lines.append(f"📋 {title} | {len(memos)}건")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    for memo in memos[:5]:
        cat = memo.get("category", "기타")
        emoji = get_category_emoji(cat)
        summary = memo.get('summary', '')
        created = memo.get("created_at", "")[:10] if memo.get("created_at") else ""

        lines.append(f"┌─ {emoji} {cat}")
        lines.append(f"│  {summary}")
        if memo.get("url"):
            lines.append(f"│  🔗 {memo['url']}")
        lines.append(f"│  📅 {created}")
        lines.append(f"└─ 🆔 {memo.get('id', '')}")
        lines.append("")

    return "\n".join(lines)
