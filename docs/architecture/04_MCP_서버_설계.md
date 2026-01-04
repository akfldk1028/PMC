# MCP 서버 설계 (PlayMCP용)

## 1. 개요

PlayMCP에 등록할 MCP 서버입니다. 사용자가 AI와 대화하면서 저장된 메모를 검색/조회할 수 있습니다.

```
PlayMCP 사용자 → "저번에 저장한 맛집 뭐였지?"
      ↓
PlayMCP → MCP 서버 (tools/call: search_memo)
      ↓
MCP 서버 → DB 검색 → 결과 반환
```

---

## 2. 프로토콜 스펙

| 항목 | 값 |
|------|-----|
| 프로토콜 | Streamable HTTP |
| 형식 | JSON-RPC 2.0 |
| 버전 | 2024-11-05 |
| 엔드포인트 | POST /mcp |

---

## 3. 도구(Tools) 정의

### 3.1 search_memo
메모 검색

```json
{
  "name": "search_memo",
  "description": "저장된 메모를 검색합니다. 키워드, 카테고리, 태그로 검색할 수 있습니다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "검색어 (예: 맛집, 유튜브, 개발)"
      },
      "category": {
        "type": "string",
        "description": "카테고리 필터 (영상/맛집/쇼핑/할일/아이디어/읽을거리)",
        "enum": ["영상", "맛집", "쇼핑", "할일", "아이디어", "읽을거리", "기타"]
      },
      "limit": {
        "type": "integer",
        "description": "결과 개수 (기본: 5)",
        "default": 5
      }
    },
    "required": ["query"]
  }
}
```

### 3.2 list_by_category
카테고리별 메모 목록

```json
{
  "name": "list_by_category",
  "description": "특정 카테고리의 메모 목록을 조회합니다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "category": {
        "type": "string",
        "description": "조회할 카테고리",
        "enum": ["영상", "맛집", "쇼핑", "할일", "아이디어", "읽을거리", "기타"]
      },
      "limit": {
        "type": "integer",
        "description": "결과 개수 (기본: 10)",
        "default": 10
      }
    },
    "required": ["category"]
  }
}
```

### 3.3 get_summary
기간별 메모 요약

```json
{
  "name": "get_summary",
  "description": "특정 기간의 메모를 카테고리별로 요약합니다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "period": {
        "type": "string",
        "description": "요약 기간",
        "enum": ["today", "week", "month"],
        "default": "week"
      }
    }
  }
}
```

### 3.4 get_recent
최근 메모 조회

```json
{
  "name": "get_recent",
  "description": "최근에 저장한 메모를 조회합니다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "limit": {
        "type": "integer",
        "description": "조회 개수 (기본: 5)",
        "default": 5
      }
    }
  }
}
```

---

## 4. 코드 구현

### 4.1 메인 MCP 서버

```python
# api/mcp.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from lib.db import search_memos, get_memos_by_category, get_memos_by_period, get_recent_memos

app = FastAPI()

# 서버 정보
SERVER_INFO = {
    "name": "챗노트",
    "version": "1.0.0"
}

# 도구 정의
TOOLS = [
    {
        "name": "search_memo",
        "description": "저장된 메모를 검색합니다. 키워드, 카테고리, 태그로 검색할 수 있습니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색어"},
                "category": {"type": "string", "description": "카테고리 필터"},
                "limit": {"type": "integer", "default": 5}
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
                "category": {
                    "type": "string",
                    "enum": ["영상", "맛집", "쇼핑", "할일", "아이디어", "읽을거리", "기타"]
                },
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["category"]
        }
    },
    {
        "name": "get_summary",
        "description": "특정 기간의 메모를 카테고리별로 요약합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month"],
                    "default": "week"
                }
            }
        }
    },
    {
        "name": "get_recent",
        "description": "최근에 저장한 메모를 조회합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 5}
            }
        }
    }
]


@app.post("/mcp")
async def mcp_handler(request: Request):
    body = await request.json()

    method = body.get("method")
    params = body.get("params", {})
    request_id = body.get("id")

    # initialize
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO
            }
        })

    # tools/list
    elif method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": TOOLS}
        })

    # tools/call
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        # 사용자 ID 추출 (PlayMCP Gateway에서 제공)
        user_id = get_user_id_from_request(request)

        result = await handle_tool_call(tool_name, arguments, user_id)

        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": result}]
            }
        })

    # Unknown method
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"}
    })
```

### 4.2 도구 호출 핸들러

```python
async def handle_tool_call(tool_name: str, arguments: dict, user_id: str) -> str:
    """도구 호출 처리"""

    if tool_name == "search_memo":
        query = arguments.get("query")
        category = arguments.get("category")
        limit = arguments.get("limit", 5)

        memos = await search_memos(user_id, query, category, limit)
        return format_search_result(memos, query)

    elif tool_name == "list_by_category":
        category = arguments.get("category")
        limit = arguments.get("limit", 10)

        memos = await get_memos_by_category(user_id, category, limit)
        return format_category_list(memos, category)

    elif tool_name == "get_summary":
        period = arguments.get("period", "week")

        memos = await get_memos_by_period(user_id, period)
        return format_summary(memos, period)

    elif tool_name == "get_recent":
        limit = arguments.get("limit", 5)

        memos = await get_recent_memos(user_id, limit)
        return format_recent_list(memos)

    else:
        return f"알 수 없는 도구입니다: {tool_name}"
```

### 4.3 결과 포맷터

```python
def format_search_result(memos: list, query: str) -> str:
    """검색 결과 포맷"""
    if not memos:
        return f"'{query}' 관련 메모가 없습니다."

    lines = [f"🔍 '{query}' 검색 결과 ({len(memos)}건)\n"]

    for i, memo in enumerate(memos, 1):
        emoji = get_category_emoji(memo["category"])
        lines.append(f"{i}. {emoji} {memo['summary']}")
        lines.append(f"   🏷️ {' '.join(['#'+t for t in memo['tags']])}")
        if memo.get("url"):
            lines.append(f"   🔗 {memo['url']}")
        lines.append("")

    return "\n".join(lines)


def format_category_list(memos: list, category: str) -> str:
    """카테고리별 목록 포맷"""
    emoji = get_category_emoji(category)

    if not memos:
        return f"{emoji} {category} 카테고리에 저장된 메모가 없습니다."

    lines = [f"{emoji} {category} 메모 ({len(memos)}건)\n"]

    for i, memo in enumerate(memos, 1):
        lines.append(f"{i}. {memo['summary']}")
        lines.append(f"   📅 {memo['created_at'][:10]}")
        lines.append("")

    return "\n".join(lines)


def format_summary(memos: list, period: str) -> str:
    """기간별 요약 포맷"""
    period_name = {"today": "오늘", "week": "이번 주", "month": "이번 달"}

    if not memos:
        return f"{period_name[period]} 저장된 메모가 없습니다."

    # 카테고리별 그룹핑
    by_category = {}
    for memo in memos:
        cat = memo["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(memo)

    lines = [f"📊 {period_name[period]} 메모 요약 (총 {len(memos)}건)\n"]

    for category, items in by_category.items():
        emoji = get_category_emoji(category)
        lines.append(f"{emoji} {category} ({len(items)}건)")
        for item in items[:3]:  # 최대 3개만 표시
            lines.append(f"  • {item['summary']}")
        if len(items) > 3:
            lines.append(f"  • ... 외 {len(items)-3}건")
        lines.append("")

    return "\n".join(lines)


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
```

---

## 5. PlayMCP 등록 정보

### 서버 정보
| 항목 | 값 |
|------|-----|
| 서버 이름 | 챗노트 (ChatNote) |
| 설명 | 카카오톡에 던진 메모를 AI가 자동 정리하고, 언제든 검색할 수 있게 해주는 스마트 메모 비서 |
| 엔드포인트 | https://memomate.vercel.app/mcp |
| 인증 방식 | OAuth (PlayMCP Gateway) |

### MCP 식별자 (Prefix)
- 추천: `memo` 또는 `memomate`
- 도구 호출 시: `memo_search_memo`, `memo_get_summary` 등

---

## 6. Vercel 배포

### vercel.json 추가

```json
{
  "version": 2,
  "builds": [
    {"src": "api/skill.py", "use": "@vercel/python"},
    {"src": "api/mcp.py", "use": "@vercel/python"}
  ],
  "routes": [
    {"src": "/skill", "dest": "/api/skill.py"},
    {"src": "/mcp", "dest": "/api/mcp.py"}
  ]
}
```

---

## 7. 테스트

### curl로 테스트

```bash
# initialize
curl -X POST https://memomate.vercel.app/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'

# tools/list
curl -X POST https://memomate.vercel.app/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# tools/call
curl -X POST https://memomate.vercel.app/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_memo","arguments":{"query":"맛집"}}}'
```

---

## 8. 다음 문서

- [05_데이터_모델.md](./05_데이터_모델.md) - DB 스키마
- [06_API_연동.md](./06_API_연동.md) - 외부 API 상세
