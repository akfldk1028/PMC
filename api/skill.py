"""
챗노트 (ChatNote) 스킬서버 - 카카오 챗봇용
AI 의도 분류 + memo_service 연동

* 채널 URL: http://pf.kakao.com/_IHxegn
* 봇 ID: 6957875684dcee6380090caa
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
from lib.redis_db import get_memo_by_id, get_memo_by_short_id
from lib.datetime_parser import format_reminder_time
from lib.kakao import send_to_me

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
    """BasicCard 응답 (thumbnail 필수!)"""
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


def create_text_card(title: str, description: str, buttons: list = None, quick_replies: list = None) -> dict:
    """TextCard 응답 (이미지 없이 깔끔한 카드)"""
    card = {"title": title[:40], "description": description[:76]}
    if buttons:
        card["buttons"] = buttons

    response = {
        "version": "2.0",
        "template": {"outputs": [{"textCard": card}]}
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
        {"label": "삭제", "action": "message", "messageText": "메모 삭제"},
        {"label": "통계", "action": "message", "messageText": "통계"},
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
        {"label": "삭제", "action": "message", "messageText": "메모 삭제"},
        {"label": "통계", "action": "message", "messageText": "통계"},
        {"label": "도움말", "action": "message", "messageText": "도움말"}
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


def get_delete_quick_replies() -> list:
    """삭제 옵션 QuickReplies - 기간별/카테고리별 삭제"""
    return [
        {"label": "← 홈", "action": "message", "messageText": "홈"},
        {"label": "오늘 삭제", "action": "message", "messageText": "오늘 메모 삭제"},
        {"label": "영상 삭제", "action": "message", "messageText": "영상 삭제"},
        {"label": "맛집 삭제", "action": "message", "messageText": "맛집 삭제"},
        {"label": "전체 삭제", "action": "message", "messageText": "전체 메모 삭제"}
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
            memo_id = intent_result.get("memo_id", "")
            return await handle_delete(user["id"], keyword, memo_id)

        elif intent == "reminder":
            step = "handle_reminders"
            return await handle_reminders(user["id"])

        elif intent == "detail":
            step = "handle_detail"
            memo_id = intent_result.get("memo_id", "")
            short_id = intent_result.get("short_id", "")
            return await handle_detail(user["id"], memo_id, short_id)

        elif intent == "help" or utterance in ["도움말", "사용법", "?"]:
            step = "handle_help"
            return handle_help()

        elif intent == "save_with_ai":
            # AI 분류 저장 ("AI: 내용" 형식)
            step = "handle_save_with_ai"
            content = intent_result.get("content", utterance)
            return await handle_save(user["id"], user.get("access_token"), content, use_ai=True)

        else:
            # 기본: 메모 저장 (원본 그대로, AI 없음)
            step = "handle_save"
            return await handle_save(user["id"], user.get("access_token"), utterance)

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[Skill Error] at {step}: {e}\n{error_detail}")
        return JSONResponse(create_simple_response("오류가 발생했습니다. 다시 시도해주세요."))


# ============ 의도별 핸들러 ============

async def handle_summary(user_id: str, period: str, category: str = None, show_all: bool = False):
    """정리/요약 처리 - 모든 메모를 카드 형식으로 모던하게 표시"""
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

    # 처음에는 10개만 (Carousel/ListCard 제한 고려)
    display_memos = memos if show_all else memos[:10]

    # 10개 이상이고 전체보기 아닐 때 → "전체보기" 버튼 추가
    if total_count > 10 and not show_all:
        if category:
            view_all_btn = {"label": f"전체 {total_count}건 보기", "action": "message", "messageText": f"전체보기 {category}"}
        else:
            view_all_btn = {"label": f"전체 {total_count}건 보기", "action": "message", "messageText": f"전체보기 {period}"}
        quick_replies = quick_replies + [view_all_btn]

    # URL 메모와 텍스트 메모 분리
    url_memos = [m for m in display_memos if m.get("url")]
    text_memos = [m for m in display_memos if not m.get("url")]

    outputs = []

    # URL 메모 → Carousel BasicCard (썸네일 있음)
    if url_memos:
        carousel_items = []
        for memo in url_memos[:10]:
            metadata = memo.get("metadata", {}) or {}
            thumbnail = metadata.get("image") or metadata.get("thumbnail")
            title = metadata.get("title") or memo.get("summary", "")[:40]
            url = memo.get("url", "")
            cat = memo.get("category", "기타")
            time_str = format_relative_time(memo.get("created_at", ""))

            item = {
                "title": (title[:40] if title else "메모"),
                "description": f"{cat} | {time_str}" if time_str else cat,
                "buttons": [{"action": "webLink", "label": "바로가기", "webLinkUrl": url}]
            }
            if thumbnail:
                item["thumbnail"] = {"imageUrl": thumbnail, "fixedRatio": True}
            carousel_items.append(item)

        outputs.append({
            "carousel": {
                "type": "basicCard",
                "items": carousel_items
            }
        })

    # 텍스트 메모 → ListCard (깔끔한 리스트)
    if text_memos:
        # 헤더 타이틀
        if category:
            header_title = f"{category} | {len(text_memos)}건"
        else:
            header_title = f"{period_name} 메모 | {len(text_memos)}건"

        list_items = []
        for memo in text_memos[:5]:  # ListCard 최대 5개
            cat = memo.get("category", "기타")
            summary = memo.get("summary", "")[:35]
            time_str = format_relative_time(memo.get("created_at", ""))
            memo_id = memo.get("id", "")
            short_id = memo_id[:8] if memo_id else ""  # 짧은 ID (UX 개선)

            list_items.append({
                "title": f"[{cat}] {summary}",
                "description": time_str if time_str else "",
                "action": "message",
                "messageText": f"#{short_id}"  # "상세 uuid" → "#a448275d"
            })

        outputs.append({
            "listCard": {
                "header": {"title": header_title},
                "items": list_items
            }
        })

    # outputs가 비어있으면 (예외 상황)
    if not outputs:
        return JSONResponse(create_simple_response("메모가 없습니다.", quick_replies=quick_replies))

    # 응답 생성
    response = {
        "version": "2.0",
        "template": {
            "outputs": outputs
        }
    }
    if quick_replies:
        response["template"]["quickReplies"] = quick_replies

    return JSONResponse(response)


async def handle_search(user_id: str, keyword: str):
    """검색 처리 - 카드 형식으로 모던하게 표시"""
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

    # URL 메모와 텍스트 메모 분리
    url_memos = [m for m in memos if m.get("url")]
    text_memos = [m for m in memos if not m.get("url")]

    outputs = []

    # URL 메모 → Carousel
    if url_memos:
        carousel_items = []
        for memo in url_memos[:10]:
            metadata = memo.get("metadata", {}) or {}
            thumbnail = metadata.get("image") or metadata.get("thumbnail")
            title = metadata.get("title") or memo.get("summary", "")[:40]
            url = memo.get("url", "")
            cat = memo.get("category", "기타")
            time_str = format_relative_time(memo.get("created_at", ""))

            item = {
                "title": (title[:40] if title else "메모"),
                "description": f"{cat} | {time_str}" if time_str else cat,
                "buttons": [{"action": "webLink", "label": "바로가기", "webLinkUrl": url}]
            }
            if thumbnail:
                item["thumbnail"] = {"imageUrl": thumbnail, "fixedRatio": True}
            carousel_items.append(item)

        outputs.append({
            "carousel": {
                "type": "basicCard",
                "items": carousel_items
            }
        })

    # 텍스트 메모 → ListCard (클릭 시 상세보기)
    if text_memos:
        list_items = []
        for memo in text_memos[:5]:
            cat = memo.get("category", "기타")
            summary = memo.get("summary", "")[:35]
            time_str = format_relative_time(memo.get("created_at", ""))
            memo_id = memo.get("id", "")
            short_id = memo_id[:8] if memo_id else ""

            list_items.append({
                "title": f"[{cat}] {summary}",
                "description": time_str if time_str else "",
                "action": "message",
                "messageText": f"#{short_id}"
            })

        outputs.append({
            "listCard": {
                "header": {"title": f"검색 '{keyword}' | {len(text_memos)}건"},
                "items": list_items
            }
        })

    # 응답 생성
    response = {
        "version": "2.0",
        "template": {
            "outputs": outputs
        }
    }
    if sub_qr:
        response["template"]["quickReplies"] = sub_qr

    return JSONResponse(response)


async def handle_delete(user_id: str, keyword: str = "", memo_id: str = ""):
    """삭제 처리 - BasicCard로 모던하게"""
    sub_qr = get_sub_page_quick_replies()
    delete_qr = get_delete_quick_replies()

    if not keyword and not memo_id:
        return JSONResponse(create_simple_response(
            "어떤 메모를 삭제할까요?",
            quick_replies=delete_qr
        ))

    # memo_id가 있으면 직접 삭제, 없으면 키워드 검색
    if memo_id:
        result = await service_delete_memo(user_id, memo_id=memo_id)
    else:
        result = await service_delete_memo(user_id, keyword=keyword)

    if not result.get("success"):
        return JSONResponse(create_simple_response(
            result.get("error", "삭제 실패"),
            quick_replies=sub_qr
        ))

    memo = result.get("deleted_memo", {})
    cat = memo.get("category", "기타")
    summary = memo.get("summary", "")[:40]

    # TextCard - 이미지 없이 깔끔하게
    return JSONResponse(create_text_card(
        title="삭제 완료",
        description=f"[{cat}] {summary}",
        quick_replies=sub_qr
    ))


async def handle_reminders(user_id: str):
    """리마인더 목록 처리 - ListCard로 모던하게"""
    sub_qr = get_sub_page_quick_replies()

    result = await service_get_reminders(user_id)
    reminders = result.get("reminders", [])

    if not reminders:
        return JSONResponse(create_simple_response(
            "예정된 리마인더가 없습니다.\n\n할일 예시\n- 내일 3시 병원 예약\n- 다음주 금요일 회의",
            quick_replies=sub_qr
        ))

    from datetime import datetime

    list_items = []
    for memo in reminders[:5]:  # ListCard 최대 5개
        reminder_at = memo.get("reminder_at", "")
        summary = memo.get("summary", memo.get("content", "")[:30])
        memo_id = memo.get("id", "")

        try:
            if reminder_at:
                dt = datetime.fromisoformat(reminder_at)
                time_str = format_reminder_time(dt)
            else:
                time_str = "시간 미지정"
        except Exception:
            time_str = "시간 미지정"

        short_id = memo_id[:8] if memo_id else ""
        list_items.append({
            "title": summary[:35],
            "description": time_str,
            "action": "message",
            "messageText": f"#{short_id}"
        })

    response = {
        "version": "2.0",
        "template": {
            "outputs": [{
                "listCard": {
                    "header": {"title": f"리마인더 | {len(reminders)}건"},
                    "items": list_items
                }
            }]
        }
    }
    if sub_qr:
        response["template"]["quickReplies"] = sub_qr

    return JSONResponse(response)


async def handle_detail(user_id: str, memo_id: str = "", short_id: str = ""):
    """메모 상세 보기 - BasicCard로 전체 정보 표시"""
    sub_qr = get_sub_page_quick_replies()

    if not memo_id and not short_id:
        return JSONResponse(create_simple_response(
            "메모를 찾을 수 없습니다.",
            quick_replies=sub_qr
        ))

    # short_id가 있으면 prefix 매칭으로 검색
    if short_id:
        memo = await get_memo_by_short_id(user_id, short_id)
        if memo:
            memo_id = memo.get("id", "")  # 삭제 버튼용 full ID
    else:
        memo = await get_memo_by_id(user_id, memo_id)

    if not memo:
        return JSONResponse(create_simple_response(
            "메모를 찾을 수 없습니다.",
            quick_replies=sub_qr
        ))

    # 메모 정보 추출
    cat = memo.get("category", "기타")
    summary = memo.get("summary", "")
    content = memo.get("content", "")
    created_at = memo.get("created_at", "")
    url = memo.get("url")
    tags = memo.get("tags", [])
    reminder_at = memo.get("reminder_at")
    metadata = memo.get("metadata", {}) or {}
    thumbnail = metadata.get("image") or metadata.get("thumbnail")

    # 날짜 포맷팅
    from datetime import datetime
    date_str = ""
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y.%m.%d %H:%M")
        except Exception:
            date_str = created_at[:16] if len(created_at) > 16 else created_at

    # 설명 구성 (상세 정보)
    desc_lines = []
    desc_lines.append(f"[{cat}]")
    if date_str:
        desc_lines.append(f"저장: {date_str}")
    if tags:
        desc_lines.append(f"태그: {', '.join(tags[:3])}")
    if reminder_at:
        try:
            r_dt = datetime.fromisoformat(reminder_at)
            desc_lines.append(f"리마인더: {format_reminder_time(r_dt)}")
        except Exception:
            pass

    description = " | ".join(desc_lines)

    # 버튼 구성
    buttons = []
    if url:
        buttons.append({"action": "webLink", "label": "바로가기", "webLinkUrl": url})
    buttons.append({"action": "message", "label": "삭제", "messageText": f"삭제 {memo_id}"})

    return JSONResponse(create_basic_card(
        title=summary[:40] if summary else content[:40],
        description=description[:76],
        thumbnail_url=thumbnail,
        buttons=buttons if buttons else None,
        quick_replies=sub_qr
    ))


async def handle_stats(user_id: str):
    """통계 처리 - ListCard로 모던하게"""
    result = await service_get_stats(user_id)
    stats = result.get("stats", {})

    total = stats.get("total", 0)
    today = stats.get("today", 0)
    week = stats.get("week", 0)
    month = stats.get("month", 0)
    by_category = stats.get("by_category", {})

    # 카테고리별 통계를 ListCard 아이템으로
    list_items = []

    # 기간별 요약을 첫 번째 아이템으로
    list_items.append({
        "title": f"전체 {total}건",
        "description": f"오늘 {today} | 이번주 {week} | 이번달 {month}"
    })

    # 카테고리별 상위 4개 (ListCard 최대 5개이므로)
    sorted_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:4]
    for cat, count in sorted_cats:
        percentage = round(count / total * 100) if total > 0 else 0
        list_items.append({
            "title": cat,
            "description": f"{count}건 ({percentage}%)"
        })

    response = {
        "version": "2.0",
        "template": {
            "outputs": [{
                "listCard": {
                    "header": {"title": "통계"},
                    "items": list_items
                }
            }]
        }
    }
    response["template"]["quickReplies"] = get_category_quick_replies()

    return JSONResponse(response)


def handle_help():
    """도움말 처리"""
    help_text = """챗노트 사용법
────────────────────

메모 저장
· 첫 단어 = 카테고리! (테니스 연습 → 테니스)
· URL → 플랫폼별 자동 분류 (유튜브→영상)
· "내일 3시 회의" → 리마인더 설정

메모 정리
오늘 정리 / 이번주 정리
영상 정리 / 맛집 정리

검색·삭제
검색 유튜브 / 삭제 유튜브

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


async def handle_save(user_id: str, access_token: str, content: str, use_ai: bool = False):
    """메모 저장 처리 - 모던 스타일

    use_ai=False (기본): 원본 그대로 저장
    use_ai=True: AI 분류/요약 사용
    """
    personalized_qr = await get_personalized_quick_replies(user_id)

    result = await service_save_memo(user_id, content, use_ai=use_ai)

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
        # 텍스트 메모 - TextCard (이미지 없이 깔끔하게)
        desc = f"[{category}] 저장 완료"
        if reminder_at:
            desc += " | 리마인더 설정됨"
        return JSONResponse(create_text_card(
            title=summary[:40],
            description=desc,
            quick_replies=personalized_qr
        ))


# 로컬 실행용
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
