"""
ChatNote 스킬서버 - 카카오 챗봇용
AI 의도 분류 + memo_service 연동
"""
import sys
import os
import json

# lib 모듈 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from lib.memo_service import (
    service_search,
    service_get_summary,
    service_get_stats,
    service_save_memo,
    service_delete_memo,
    service_get_reminders,
    service_classify_intent,
    get_user_top_categories,
    service_get_or_create_user
)
from lib.constants import get_category_emoji, CATEGORY_EMOJIS
from lib.datetime_parser import format_reminder_time
from lib.kakao import send_to_me, format_memo_message

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 카카오 응답 생성 함수 ============

def create_simple_response(text: str, quick_replies: list = None) -> dict:
    """SimpleText 응답"""
    response = {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}]
        }
    }
    if quick_replies:
        response["template"]["quickReplies"] = quick_replies
    return response


def create_list_card(header_title: str, items: list, buttons: list = None, quick_replies: list = None) -> dict:
    """ListCard 응답"""
    list_card = {
        "header": {"title": header_title},
        "items": items[:5]
    }
    if buttons:
        list_card["buttons"] = buttons

    response = {
        "version": "2.0",
        "template": {"outputs": [{"listCard": list_card}]}
    }
    if quick_replies:
        response["template"]["quickReplies"] = quick_replies
    return response


def create_basic_card(title: str, description: str, thumbnail_url: str = None, buttons: list = None, quick_replies: list = None) -> dict:
    """BasicCard 응답"""
    card = {"title": title[:40], "description": description[:76]}
    if thumbnail_url:
        card["thumbnail"] = {"imageUrl": thumbnail_url, "fixedRatio": True}
    if buttons:
        card["buttons"] = buttons

    response = {
        "version": "2.0",
        "template": {"outputs": [{"basicCard": card}]}
    }
    if quick_replies:
        response["template"]["quickReplies"] = quick_replies
    return response


def create_carousel(cards: list, quick_replies: list = None) -> dict:
    """Carousel 응답 - 영상/이미지 메모에 적합"""
    carousel_items = []
    for card in cards[:10]:  # 최대 10개
        item = {
            "title": card.get("title", "")[:40],
            "description": card.get("description", "")[:76]
        }
        if card.get("thumbnail"):
            item["thumbnail"] = {"imageUrl": card["thumbnail"], "fixedRatio": True}
        if card.get("buttons"):
            item["buttons"] = card["buttons"]
        carousel_items.append(item)

    response = {
        "version": "2.0",
        "template": {
            "outputs": [{
                "carousel": {
                    "type": "basicCard",
                    "items": carousel_items
                }
            }]
        }
    }
    if quick_replies:
        response["template"]["quickReplies"] = quick_replies
    return response


def get_default_quick_replies() -> list:
    """기본 QuickReplies - 홈 화면용"""
    return [
        {"label": "오늘", "action": "message", "messageText": "오늘 정리"},
        {"label": "이번주", "action": "message", "messageText": "이번주 정리"},
        {"label": "영상", "action": "message", "messageText": "영상 정리"},
        {"label": "맛집", "action": "message", "messageText": "맛집 정리"},
        {"label": "통계", "action": "message", "messageText": "통계"},
        {"label": "리마인더", "action": "message", "messageText": "리마인더"},
        {"label": "도움말", "action": "message", "messageText": "도움말"}
    ]


async def get_personalized_quick_replies(user_id: str) -> list:
    """개인화된 QuickReplies - 사용자 상위 2개 카테고리 동적 반영 (← 홈 포함)"""
    # 사용자 상위 2개 카테고리 가져오기
    top_cats = await get_user_top_categories(user_id, limit=2)

    # 동적 카테고리 버튼 생성 (이모지 없이 깔끔하게)
    dynamic_buttons = []
    for cat in top_cats:
        dynamic_buttons.append({
            "label": cat,
            "action": "message",
            "messageText": f"{cat} 정리"
        })

    # 모든 화면에서 ← 홈 버튼 포함 (일관된 UX)
    return [
        {"label": "← 홈", "action": "message", "messageText": "홈"},
        {"label": "오늘", "action": "message", "messageText": "오늘 정리"},
        {"label": "이번주", "action": "message", "messageText": "이번주 정리"},
    ] + dynamic_buttons + [
        {"label": "통계", "action": "message", "messageText": "통계"},
        {"label": "리마인더", "action": "message", "messageText": "리마인더"}
    ]


def get_category_quick_replies() -> list:
    """카테고리별 QuickReplies (뒤로가기 포함)"""
    return [
        {"label": "← 홈", "action": "message", "messageText": "홈"},
        {"label": "영상", "action": "message", "messageText": "영상 정리"},
        {"label": "맛집", "action": "message", "messageText": "맛집 정리"},
        {"label": "쇼핑", "action": "message", "messageText": "쇼핑 정리"},
        {"label": "학습", "action": "message", "messageText": "학습 정리"},
        {"label": "할일", "action": "message", "messageText": "할일 정리"},
        {"label": "기타", "action": "message", "messageText": "기타 정리"}
    ]


def get_period_quick_replies() -> list:
    """기간별 QuickReplies (뒤로가기 포함)"""
    return [
        {"label": "← 홈", "action": "message", "messageText": "홈"},
        {"label": "오늘", "action": "message", "messageText": "오늘 정리"},
        {"label": "어제", "action": "message", "messageText": "어제 정리"},
        {"label": "이번주", "action": "message", "messageText": "이번주 정리"},
        {"label": "지난주", "action": "message", "messageText": "지난주 정리"},
        {"label": "이번달", "action": "message", "messageText": "이번달 정리"},
        {"label": "전체", "action": "message", "messageText": "전체 보여줘"}
    ]


def get_sub_page_quick_replies() -> list:
    """서브 페이지용 QuickReplies (뒤로가기 포함) - 검색/삭제/리마인더용"""
    return [
        {"label": "← 홈", "action": "message", "messageText": "홈"},
        {"label": "오늘", "action": "message", "messageText": "오늘 정리"},
        {"label": "이번주", "action": "message", "messageText": "이번주 정리"},
        {"label": "통계", "action": "message", "messageText": "통계"},
        {"label": "리마인더", "action": "message", "messageText": "리마인더"}
    ]


def format_relative_time(iso_time: str) -> str:
    """상대 시간 포맷"""
    if not iso_time:
        return ""
    try:
        from datetime import datetime
        created = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        now = datetime.now(created.tzinfo) if created.tzinfo else datetime.now()
        diff = now - created

        if diff.days == 0:
            hours = diff.seconds // 3600
            return "방금" if hours == 0 else f"{hours}시간 전"
        elif diff.days == 1:
            return "어제"
        elif diff.days < 7:
            return f"{diff.days}일 전"
        else:
            return f"{diff.days // 7}주 전"
    except Exception:
        return ""


# ============ 스킬 핸들러 ============

@app.post("/skill")
async def skill_handler(request: Request):
    """카카오 챗봇 스킬 핸들러 (AI 주도 의도 분류)"""
    step = "init"
    try:
        step = "json_parse"
        # 인코딩 에러 방지: raw body를 먼저 받아서 처리
        body_bytes = await request.body()
        try:
            body_text = body_bytes.decode('utf-8')
        except UnicodeDecodeError:
            # Windows/한글 인코딩 폴백
            body_text = body_bytes.decode('cp949', errors='replace')
        body = json.loads(body_text)

        step = "extract_user"
        user_request = body.get("userRequest", {})
        user_info = user_request.get("user", {})
        user_id = user_info.get("id", "unknown")
        utterance = user_request.get("utterance", "").strip()

        step = "get_user"
        user = await service_get_or_create_user(user_id)

        # AI 의도 분류 (신뢰도 포함)
        step = "classify_intent"
        intent_result = await service_classify_intent(utterance)
        intent = intent_result.get("intent", "save")
        confidence = intent_result.get("confidence", 0.5)

        print(f"[Skill] user={user_id[:8]}... utterance='{utterance}' intent={intent} conf={confidence}")

        # API 키 없음 에러 처리
        if intent == "error":
            sub_qr = get_sub_page_quick_replies()
            return JSONResponse(create_simple_response(
                intent_result.get("message", "설정 오류가 발생했습니다."),
                quick_replies=sub_qr
            ))

        # 낮은 신뢰도 처리 (0.6 미만)
        if confidence < 0.6 and intent != "save":
            # 불확실하면 사용자에게 확인 (뒤로가기 포함)
            return JSONResponse(create_simple_response(
                f"'{utterance}'를 어떻게 처리할까요?",
                quick_replies=[
                    {"label": "← 홈", "action": "message", "messageText": "홈"},
                    {"label": "메모 저장", "action": "message", "messageText": utterance},
                    {"label": "오늘", "action": "message", "messageText": "오늘 정리"},
                    {"label": "검색", "action": "message", "messageText": f"검색 {utterance}"}
                ]
            ))

        # 의도에 따라 처리
        if intent == "summary":
            step = "handle_summary"
            period = intent_result.get("period", "today")
            category = intent_result.get("category")
            show_all = intent_result.get("show_all", False)
            return await handle_summary(user["id"], period, category, show_all)

        elif intent == "stats":
            step = "handle_stats"
            return await handle_stats(user["id"])

        elif intent == "search":
            step = "handle_search"
            keyword = intent_result.get("keyword", "")
            return await handle_search(user["id"], keyword)

        elif intent == "delete":
            step = "handle_delete"
            keyword = intent_result.get("keyword", "")
            return await handle_delete(user["id"], keyword)

        elif intent == "reminder":
            step = "handle_reminders"
            return await handle_reminders(user["id"])

        elif intent == "help" or utterance in ["도움말", "사용법", "?"]:
            step = "handle_help"
            return handle_help()

        else:
            # 기본: 메모 저장
            step = "handle_save"
            return await handle_save(user["id"], user.get("access_token"), utterance)

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[Skill Error] at {step}: {e}\n{error_detail}")
        return JSONResponse(create_simple_response("오류가 발생했습니다. 다시 시도해주세요."))


# ============ 의도별 핸들러 ============

async def handle_summary(user_id: str, period: str, category: str = None, show_all: bool = False):
    """정리/요약 처리 (기간별/카테고리별) - 처음 10개, 전체보기시 전부"""
    result = await service_get_summary(user_id, period, category)
    memos = result.get("memos", [])
    period_name = result.get("period_name", "오늘")
    total_count = len(memos)

    # QuickReplies 선택
    if category:
        quick_replies = get_category_quick_replies()
    else:
        quick_replies = get_period_quick_replies()

    if not memos:
        if category:
            msg = f"{category} 카테고리에 저장된 메모가 없습니다."
        else:
            msg = f"{period_name} 저장된 메모가 없습니다."
        return JSONResponse(create_simple_response(msg, quick_replies=quick_replies))

    # 처음에는 10개만, 전체보기면 전부
    display_limit = None if show_all else 10
    display_memos = memos if show_all else memos[:10]

    # 모던한 헤더
    if category:
        header = f"{category} · {len(display_memos)}/{total_count}"
    else:
        header = f"{period_name} · {len(display_memos)}/{total_count}"

    lines = [header, "─" * 20, ""]

    for memo in display_memos:
        summary = memo.get("summary", "")[:45]
        time_str = format_relative_time(memo.get("created_at", ""))
        url = memo.get("url", "")

        lines.append(summary)
        if url:
            lines.append(url)
        if time_str:
            lines.append(f"└ {time_str}")
        lines.append("")

    text = "\n".join(lines)

    # 카카오 메시지 최대 길이 제한 (1000자)
    if len(text) > 950:
        text = text[:950] + "\n\n... (메시지 길이 제한)"

    # 10개 이상이고 전체보기 아닐 때 → "전체보기" 버튼 추가
    if total_count > 10 and not show_all:
        # 전체보기 버튼을 QuickReplies 맨 뒤에 추가
        if category:
            view_all_btn = {"label": f"▼ 전체 {total_count}건", "action": "message", "messageText": f"전체보기 {category}"}
        else:
            view_all_btn = {"label": f"▼ 전체 {total_count}건", "action": "message", "messageText": f"전체보기 {period}"}
        quick_replies = quick_replies + [view_all_btn]

    return JSONResponse(create_simple_response(text, quick_replies=quick_replies))


async def handle_search(user_id: str, keyword: str):
    """검색 처리"""
    # 서브페이지용 QuickReplies (뒤로가기 포함)
    sub_qr = get_sub_page_quick_replies()

    if not keyword:
        return JSONResponse(create_simple_response(
            "검색어를 입력해주세요.\n예: 검색 맛집",
            quick_replies=sub_qr
        ))

    # 날짜 키워드 처리
    date_keywords = {"오늘": "today", "어제": "yesterday", "이번주": "week", "이번 주": "week", "이번달": "month"}
    if keyword in date_keywords:
        return await handle_summary(user_id, date_keywords[keyword])

    result = await service_search(user_id, keyword)
    memos = result.get("memos", [])

    if not memos:
        return JSONResponse(create_simple_response(
            f"'{keyword}' 관련 메모가 없습니다.",
            quick_replies=sub_qr
        ))

    # 모던한 검색 결과
    lines = [f"검색 '{keyword}' · {len(memos)}건", "─" * 20, ""]

    for memo in memos:
        summary = memo.get("summary", "")[:40]
        url = memo.get("url", "")

        lines.append(summary)
        if url:
            lines.append(url)
        lines.append("")

    text = "\n".join(lines)
    if len(text) > 950:
        text = text[:950] + "\n\n..."

    return JSONResponse(create_simple_response(text, quick_replies=sub_qr))


async def handle_delete(user_id: str, keyword: str):
    """삭제 처리"""
    # 서브페이지용 QuickReplies (뒤로가기 포함)
    sub_qr = get_sub_page_quick_replies()

    if not keyword:
        return JSONResponse(create_simple_response(
            "삭제할 메모를 검색어로 알려주세요.\n예: 삭제 유튜브",
            quick_replies=sub_qr
        ))

    result = await service_delete_memo(user_id, keyword=keyword)

    if not result.get("success"):
        return JSONResponse(create_simple_response(
            result.get("error", "삭제 실패"),
            quick_replies=sub_qr
        ))

    memo = result.get("deleted_memo", {})

    return JSONResponse(create_simple_response(
        f"삭제 완료\n─────────────────\n{memo.get('summary', '')[:40]}",
        quick_replies=sub_qr
    ))


async def handle_reminders(user_id: str):
    """리마인더 목록 처리"""
    sub_qr = get_sub_page_quick_replies()

    result = await service_get_reminders(user_id)
    reminders = result.get("reminders", [])

    if not reminders:
        return JSONResponse(create_simple_response(
            "리마인더 · 0건\n────────────────────\n\n예정된 리마인더가 없습니다.\n\n할일 예시\n내일 3시 병원 예약\n다음주 금요일 회의",
            quick_replies=sub_qr
        ))

    from datetime import datetime
    lines = [f"리마인더 · {len(reminders)}건", "─" * 20, ""]

    for memo in reminders:
        reminder_at = memo.get("reminder_at", "")
        summary = memo.get("summary", memo.get("content", "")[:30])

        try:
            if reminder_at:
                dt = datetime.fromisoformat(reminder_at)
                time_str = format_reminder_time(dt)
            else:
                time_str = "시간 미지정"
        except Exception:
            time_str = "시간 미지정"

        lines.append(summary[:35])
        lines.append(f"└ {time_str}")
        lines.append("")

    text = "\n".join(lines)
    if len(text) > 950:
        text = text[:950] + "\n\n..."

    return JSONResponse(create_simple_response(text, quick_replies=sub_qr))


async def handle_stats(user_id: str):
    """통계 처리"""
    result = await service_get_stats(user_id)
    stats = result.get("stats", {})

    total = stats.get("total", 0)
    today = stats.get("today", 0)
    week = stats.get("week", 0)
    month = stats.get("month", 0)
    by_category = stats.get("by_category", {})

    # 카테고리별 통계 (이모지 없이)
    cat_lines = []
    for cat, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
        cat_lines.append(f"{cat} {count}")

    cat_text = " · ".join(cat_lines) if cat_lines else "데이터 없음"

    text = f"""통계 · 전체 {total}건
────────────────────

오늘 {today} · 이번주 {week} · 이번달 {month}

카테고리별
{cat_text}"""

    return JSONResponse(create_simple_response(
        text,
        quick_replies=get_category_quick_replies()
    ))


def handle_help():
    """도움말 처리"""
    help_text = """챗노트 사용법
────────────────────

메모 저장
아무 텍스트나 URL을 보내면 자동 저장
"내일 3시 회의" 형식으로 리마인더 설정

메모 정리
오늘 정리 / 이번주 정리
영상 정리 / 맛집 정리

검색·삭제
검색 유튜브
삭제 유튜브

기타
통계 / 리마인더"""

    return JSONResponse(create_simple_response(
        help_text,
        quick_replies=[
            {"label": "오늘", "action": "message", "messageText": "오늘 정리"},
            {"label": "이번주", "action": "message", "messageText": "이번주 정리"},
            {"label": "영상", "action": "message", "messageText": "영상 정리"},
            {"label": "맛집", "action": "message", "messageText": "맛집 정리"},
            {"label": "통계", "action": "message", "messageText": "통계"},
            {"label": "리마인더", "action": "message", "messageText": "리마인더"}
        ]
    ))


async def handle_save(user_id: str, access_token: str, content: str):
    """메모 저장 처리 - 모던 스타일"""
    personalized_qr = await get_personalized_quick_replies(user_id)

    result = await service_save_memo(user_id, content)

    if not result.get("success"):
        return JSONResponse(create_simple_response(
            "저장 실패\n다시 시도해주세요.",
            quick_replies=personalized_qr
        ))

    category = result.get("category", "기타")
    summary = result.get("summary", content[:30])
    url = result.get("url")
    reminder_at = result.get("reminder_at")
    metadata = result.get("metadata", {})
    thumbnail = metadata.get("image") or metadata.get("thumbnail") if metadata else None
    site_name = metadata.get("site_name", "") if metadata else ""
    og_title = metadata.get("title", "") if metadata else ""

    # 리마인더가 있으면 표시
    extra_info = ""
    if reminder_at:
        extra_info = "\n└ 리마인더 설정됨"

    # 카카오 나에게 보내기 (선택)
    if access_token:
        from lib.kakao import send_to_me
        message = f"{category}: {summary}"
        await send_to_me(access_token, message)

    if url:
        # URL 메모 - BasicCard
        display_title = og_title[:35] if og_title else summary[:35]

        # 간결한 설명
        desc_parts = [category]
        if site_name:
            desc_parts.append(site_name)
        description = " · ".join(desc_parts)

        return JSONResponse(create_basic_card(
            title=display_title,
            description=description[:76],
            thumbnail_url=thumbnail,
            buttons=[{"action": "webLink", "label": "바로가기", "webLinkUrl": url}],
            quick_replies=personalized_qr
        ))
    else:
        # 텍스트 메모 - SimpleText
        return JSONResponse(create_simple_response(
            f"저장 완료 · {category}\n────────────────────\n{summary}{extra_info}",
            quick_replies=personalized_qr
        ))


# 로컬 실행용
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
