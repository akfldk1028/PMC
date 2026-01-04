"""
MCP 서버 - PlayMCP용
Streamable HTTP 프로토콜 (JSON-RPC 2.0)
"""
import sys
import os

# lib 모듈 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from typing import Optional
import json

from lib.redis_db import (
    search_memos,
    get_memos_by_category,
    get_memos_by_period,
    get_recent_memos,
    save_memo,
    delete_memo,
    update_memo,
    get_memo_by_id,
    seed_demo_data,
    get_user_stats
)
from lib.classifier import get_category_emoji
from lib.metadata import extract_metadata, extract_urls

# FastAPI 앱
app = FastAPI(title="챗노트 MCP Server")

# MCP 서버 정보
SERVER_INFO = {
    "name": "챗노트",
    "version": "1.0.0"
}

# 공통 user_id 속성 정의
USER_ID_PROP = {"type": "string", "description": "사용자 고유 ID (PlayMCP에서 자동 전달)", "default": "anonymous"}

# MCP 도구 정의
TOOLS = [
    {
        "name": "search_memo",
        "description": "저장된 메모를 검색합니다. 키워드, 카테고리로 검색할 수 있습니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": USER_ID_PROP,
                "query": {"type": "string", "description": "검색어 (예: 맛집, 유튜브, 개발)"},
                "category": {"type": "string", "description": "카테고리 필터 (영상/맛집/쇼핑/할일/아이디어/읽을거리/기타)"},
                "limit": {"type": "integer", "description": "결과 개수 (기본: 5)", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "list_by_category",
        "description": "특정 카테고리의 메모 목록을 조회합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": USER_ID_PROP,
                "category": {"type": "string", "description": "조회할 카테고리 (영상/맛집/쇼핑/할일/아이디어/읽을거리/기타)"},
                "limit": {"type": "integer", "description": "결과 개수 (기본: 10)", "default": 10}
            },
            "required": ["category"]
        }
    },
    {
        "name": "get_summary",
        "description": "특정 기간 또는 카테고리의 메모를 요약합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": USER_ID_PROP,
                "period": {"type": "string", "description": "요약 기간 (today/yesterday/week/last_week/month/last_month/all)", "default": "today"},
                "category": {"type": "string", "description": "특정 카테고리만 조회 (영상/음악/맛집/쇼핑/여행/할일/아이디어/학습/건강/읽을거리/기타)"}
            }
        }
    },
    {
        "name": "get_stats",
        "description": "메모 통계를 조회합니다. 전체 개수, 오늘/이번주/이번달 개수, 카테고리별 개수를 확인할 수 있습니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": USER_ID_PROP
            }
        }
    },
    {
        "name": "get_recent",
        "description": "최근에 저장한 메모를 조회합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": USER_ID_PROP,
                "limit": {"type": "integer", "description": "조회 개수 (기본: 5)", "default": 5}
            }
        }
    },
    {
        "name": "add_memo",
        "description": "**중요: 사용자가 URL, 텍스트, 정보를 보내면 확인하지 말고 바로 저장하세요!** 저장할지 물어보지 마세요. 질문(?로 끝나는 문장)이 아니면 전부 메모입니다. 자동 분류: 유튜브='영상', 맛집='맛집', 상품='쇼핑', 할일='할일', 아이디어='아이디어', 기사='읽을거리'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": USER_ID_PROP,
                "content": {"type": "string", "description": "저장할 내용 (URL, 텍스트 등)"},
                "category": {"type": "string", "description": "카테고리 (영상/맛집/쇼핑/할일/아이디어/읽을거리/기타)", "default": "기타"},
                "summary": {"type": "string", "description": "메모 요약 (한 줄 설명)"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "태그 목록", "default": []}
            },
            "required": ["content", "summary"]
        }
    },
    {
        "name": "delete_memo",
        "description": "저장된 메모를 삭제합니다. 메모 ID를 지정하여 삭제할 수 있습니다. 먼저 search_memo나 get_recent로 메모 ID를 확인하세요.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": USER_ID_PROP,
                "memo_id": {"type": "string", "description": "삭제할 메모의 ID (UUID 형식)"}
            },
            "required": ["memo_id"]
        }
    },
    {
        "name": "update_memo",
        "description": "저장된 메모를 수정합니다. 요약, 카테고리, 태그를 변경할 수 있습니다. 먼저 search_memo나 get_recent로 메모 ID를 확인하세요.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": USER_ID_PROP,
                "memo_id": {"type": "string", "description": "수정할 메모의 ID (UUID 형식)"},
                "summary": {"type": "string", "description": "새로운 요약 (한 줄 설명)"},
                "category": {"type": "string", "description": "새로운 카테고리 (영상/맛집/쇼핑/할일/아이디어/읽을거리/기타)"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "새로운 태그 목록"}
            },
            "required": ["memo_id"]
        }
    }
]


# ============ 도구 함수 ============

async def tool_search_memo(args: dict) -> str:
    """메모 검색"""
    user_id = args.get("user_id", "anonymous")
    query = args.get("query", "")
    category = args.get("category")
    limit = args.get("limit", 5)

    memos = await search_memos(user_id, query, category, limit)

    if not memos:
        return f"📭 '{query}' 관련 메모가 없습니다.\n\n💡 다른 키워드로 검색해보세요!"

    lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    lines.append(f"🔍 검색: '{query}' | {len(memos)}건 발견")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    for i, memo in enumerate(memos, 1):
        cat = memo.get("category", "기타")
        emoji = get_category_emoji(cat)
        summary = memo.get('summary', '')
        created = memo.get("created_at", "")[:10] if memo.get("created_at") else ""
        memo_id = memo.get("id", "")

        lines.append(f"┌─ {emoji} {cat}")
        lines.append(f"│  {summary}")

        tags = memo.get("tags", [])
        if tags:
            tag_str = " ".join([f"#{t}" for t in tags[:4]])
            lines.append(f"│  🏷 {tag_str}")

        if memo.get("url"):
            lines.append(f"│  🔗 {memo['url']}")

        lines.append(f"│  📅 {created}")
        lines.append(f"└─ 🆔 {memo_id}")
        lines.append("")

    return "\n".join(lines)


async def tool_list_by_category(args: dict) -> str:
    """카테고리별 메모 조회"""
    user_id = args.get("user_id", "anonymous")
    category = args.get("category", "기타")
    limit = args.get("limit", 10)

    memos = await get_memos_by_category(user_id, category, limit)
    emoji = get_category_emoji(category)

    if not memos:
        return f"📭 {emoji} {category} 카테고리가 비어있습니다.\n\n💡 메모를 저장해보세요!"

    lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    lines.append(f"{emoji} {category} | {len(memos)}건")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    for i, memo in enumerate(memos, 1):
        summary = memo.get('summary', '')
        created = memo.get("created_at", "")[:10] if memo.get("created_at") else ""
        tags = memo.get("tags", [])

        lines.append(f"  {i}. {summary}")
        if tags:
            tag_str = " ".join([f"#{t}" for t in tags[:3]])
            lines.append(f"     🏷 {tag_str}")
        if created:
            lines.append(f"     📅 {created}")
        lines.append("")

    return "\n".join(lines)


async def tool_get_summary(args: dict) -> str:
    """기간별/카테고리별 요약"""
    user_id = args.get("user_id", "anonymous")
    period = args.get("period", "today")
    category = args.get("category")

    # 카테고리별 조회
    if category:
        memos = await get_memos_by_category(user_id, category, limit=10)
        label = f"{category} 카테고리"
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
        label = period_names.get(period, period)

    if not memos:
        return f"📭 {label} 저장된 메모가 없습니다.\n\n💡 메모를 저장해보세요!"

    by_category = {}
    for memo in memos:
        cat = memo.get("category", "기타")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(memo)

    lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    lines.append(f"📊 {label} 요약 | 총 {len(memos)}건")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    # 카테고리별 개수 표시
    summary_line = " | ".join([f"{get_category_emoji(c)}{len(items)}" for c, items in by_category.items()])
    lines.append(f"📈 {summary_line}\n")

    for cat, items in by_category.items():
        emoji = get_category_emoji(cat)
        lines.append(f"┌─ {emoji} {cat} ({len(items)}건)")
        for item in items[:3]:
            lines.append(f"│  • {item.get('summary', '')}")
        if len(items) > 3:
            lines.append(f"│  + {len(items)-3}건 더...")
        lines.append("└─")
        lines.append("")

    return "\n".join(lines)


async def tool_get_stats(args: dict) -> str:
    """통계 조회"""
    user_id = args.get("user_id", "anonymous")

    stats = await get_user_stats(user_id)

    total = stats.get("total", 0)
    today = stats.get("today", 0)
    week = stats.get("week", 0)
    month = stats.get("month", 0)
    by_category = stats.get("by_category", {})

    lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    lines.append(f"📊 메모 통계")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    lines.append(f"📈 전체: {total}개")
    lines.append(f"📅 오늘: {today}개")
    lines.append(f"📆 이번 주: {week}개")
    lines.append(f"🗓️ 이번 달: {month}개")
    lines.append("")

    if by_category:
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("📂 카테고리별")
        for cat, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
            emoji = get_category_emoji(cat)
            lines.append(f"  {emoji} {cat}: {count}개")
    else:
        lines.append("📭 아직 저장된 메모가 없습니다.")

    return "\n".join(lines)


async def tool_get_recent(args: dict) -> str:
    """최근 메모 조회"""
    user_id = args.get("user_id", "anonymous")
    limit = args.get("limit", 5)

    memos = await get_recent_memos(user_id, limit)

    if not memos:
        return "📭 저장된 메모가 없습니다.\n\n💡 '메모해줘'라고 말해보세요!"

    lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    lines.append(f"📋 최근 메모 | {len(memos)}건")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    for i, memo in enumerate(memos, 1):
        cat = memo.get("category", "기타")
        emoji = get_category_emoji(cat)
        summary = memo.get('summary', '')
        created = memo.get("created_at", "")[:10] if memo.get("created_at") else ""
        tags = memo.get("tags", [])
        memo_id = memo.get("id", "")

        lines.append(f"┌─ {emoji} {cat}")
        lines.append(f"│  {summary}")
        if tags:
            tag_str = " ".join([f"#{t}" for t in tags[:3]])
            lines.append(f"│  🏷 {tag_str}")
        if memo.get("url"):
            lines.append(f"│  🔗 {memo['url']}")
        lines.append(f"│  📅 {created}")
        lines.append(f"└─ 🆔 {memo_id}")
        lines.append("")

    return "\n".join(lines)


async def tool_add_memo(args: dict) -> str:
    """메모 저장"""
    user_id = args.get("user_id", "anonymous")
    content = args.get("content", "")
    category = args.get("category", "기타")
    summary = args.get("summary", content[:50])
    tags = args.get("tags", [])

    # URL 추출 및 메타데이터 가져오기
    urls = extract_urls(content)
    memo_type = "link" if urls else "text"
    metadata = {}

    if urls:
        url = urls[0]
        metadata = await extract_metadata(url)
        metadata["url"] = url
        # 메타데이터에서 더 좋은 제목이 있으면 사용
        if metadata.get("title") and len(metadata["title"]) > len(summary):
            summary = metadata["title"][:80]

    memo_id = await save_memo(
        user_id=user_id,
        content=content,
        memo_type=memo_type,
        category=category,
        tags=tags,
        summary=summary,
        metadata=metadata
    )

    emoji = get_category_emoji(category)
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "✅ 메모 저장 완료!",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"┌─ {emoji} {category}",
        f"│  {summary}",
    ]
    if tags:
        tag_str = " ".join([f"#{t}" for t in tags])
        lines.append(f"│  🏷 {tag_str}")
    if memo_type == "link":
        site_name = metadata.get("site_name", "")
        if site_name:
            lines.append(f"│  📍 {site_name}")
        lines.append(f"│  🔗 {metadata.get('url', content)}")
        if metadata.get("image"):
            lines.append(f"│  🖼 썸네일 저장됨")
    lines.append("└─")
    lines.append("")
    lines.append("💡 '최근 메모', '메모 검색' 등으로 확인하세요!")

    return "\n".join(lines)


async def tool_delete_memo(args: dict) -> str:
    """메모 삭제"""
    user_id = args.get("user_id", "anonymous")
    memo_id = args.get("memo_id", "")

    if not memo_id:
        return "❌ 삭제할 메모 ID를 입력해주세요."

    # 메모 존재 확인
    memo = await get_memo_by_id(user_id, memo_id)
    if not memo:
        return f"❌ 메모를 찾을 수 없습니다.\n\nID: {memo_id}\n\n💡 'search_memo'나 'get_recent'로 메모 ID를 확인하세요."

    # 삭제 실행
    success = await delete_memo(user_id, memo_id)

    if success:
        emoji = get_category_emoji(memo.get("category", "기타"))
        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "🗑️ 메모 삭제 완료!",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"삭제된 메모:",
            f"  {emoji} {memo.get('summary', '')}",
            f"  카테고리: {memo.get('category', '기타')}",
            "",
            "💡 '최근 메모'로 확인하세요!"
        ]
        return "\n".join(lines)
    else:
        return "❌ 메모 삭제에 실패했습니다."


async def tool_update_memo(args: dict) -> str:
    """메모 수정"""
    user_id = args.get("user_id", "anonymous")
    memo_id = args.get("memo_id", "")
    new_summary = args.get("summary")
    new_category = args.get("category")
    new_tags = args.get("tags")

    if not memo_id:
        return "❌ 수정할 메모 ID를 입력해주세요."

    # 메모 존재 확인
    old_memo = await get_memo_by_id(user_id, memo_id)
    if not old_memo:
        return f"❌ 메모를 찾을 수 없습니다.\n\nID: {memo_id}\n\n💡 'search_memo'나 'get_recent'로 메모 ID를 확인하세요."

    # 수정할 내용 확인
    if not any([new_summary, new_category, new_tags]):
        return "❌ 수정할 내용을 입력해주세요. (summary, category, tags 중 하나 이상)"

    # 수정 실행
    updated_memo = await update_memo(user_id, memo_id, new_summary, new_category, new_tags)

    if updated_memo:
        emoji = get_category_emoji(updated_memo.get("category", "기타"))
        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "✏️ 메모 수정 완료!",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "변경 내용:"
        ]

        if new_summary:
            lines.append(f"  📝 요약: {old_memo.get('summary', '')} → {updated_memo.get('summary', '')}")
        if new_category:
            old_emoji = get_category_emoji(old_memo.get("category", "기타"))
            lines.append(f"  📁 카테고리: {old_emoji}{old_memo.get('category', '기타')} → {emoji}{updated_memo.get('category', '기타')}")
        if new_tags:
            old_tags = " ".join([f"#{t}" for t in old_memo.get('tags', [])])
            new_tags_str = " ".join([f"#{t}" for t in updated_memo.get('tags', [])])
            lines.append(f"  🏷️ 태그: {old_tags or '없음'} → {new_tags_str or '없음'}")

        lines.append("")
        lines.append("💡 '최근 메모'로 확인하세요!")
        return "\n".join(lines)
    else:
        return "❌ 메모 수정에 실패했습니다."


# 도구 핸들러 매핑
TOOL_HANDLERS = {
    "search_memo": tool_search_memo,
    "list_by_category": tool_list_by_category,
    "get_summary": tool_get_summary,
    "get_stats": tool_get_stats,
    "get_recent": tool_get_recent,
    "add_memo": tool_add_memo,
    "delete_memo": tool_delete_memo,
    "update_memo": tool_update_memo,
}


# ============ MCP JSON-RPC 핸들러 ============

@app.post("/")
@app.post("/mcp")
async def mcp_handler(request: Request):
    """MCP JSON-RPC 2.0 핸들러"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "Parse error"},
            "id": None
        })

    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")

    # initialize
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": SERVER_INFO
            },
            "id": req_id
        })

    # notifications/initialized
    if method == "notifications/initialized":
        return JSONResponse({"jsonrpc": "2.0", "result": {}, "id": req_id})

    # tools/list
    if method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": {"tools": TOOLS},
            "id": req_id
        })

    # tools/call
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
                "id": req_id
            })

        try:
            result = await handler(tool_args)
            return JSONResponse({
                "jsonrpc": "2.0",
                "result": {
                    "content": [{"type": "text", "text": result}]
                },
                "id": req_id
            })
        except Exception as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": req_id
            })

    # Unknown method
    return JSONResponse({
        "jsonrpc": "2.0",
        "error": {"code": -32601, "message": f"Method not found: {method}"},
        "id": req_id
    })


@app.get("/")
async def health():
    """헬스 체크"""
    return {"status": "ok", "server": SERVER_INFO}


@app.get("/seed")
@app.post("/seed")
async def seed_data():
    """테스트 데이터 시드 (Redis)"""
    try:
        count = await seed_demo_data("demo_user")
        return {"status": "ok", "message": f"{count}개 테스트 메모 추가됨 (Redis)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# 로컬 실행용
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
