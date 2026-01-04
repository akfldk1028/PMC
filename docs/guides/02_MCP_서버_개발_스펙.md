# MCP 서버 개발 스펙 (PlayMCP용)

## 1. PlayMCP 기술 요구사항

### 지원 프로토콜
| 프로토콜 | PlayMCP 지원 | 설명 |
|----------|-------------|------|
| **Streamable HTTP** | ✅ 지원 | **유일하게 지원** |
| stdio | ❌ 미지원 | 로컬 전용 |
| SSE (Server-Sent Events) | ❌ 미지원 | - |

### MCP 프로토콜 버전
- 권장: `2024-11-05` 또는 최신
- JSON-RPC 2.0 기반

---

## 2. Streamable HTTP 구조

### 엔드포인트
```
POST https://your-domain.com/mcp
Content-Type: application/json
```

### 통신 방식
- 클라이언트 → 서버: HTTP POST 요청
- 서버 → 클라이언트: JSON 응답
- 모든 요청/응답은 **JSON-RPC 2.0** 형식

---

## 3. 필수 메서드

### 3.1 initialize
서버 초기화 및 프로토콜 버전 협상

**요청:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "PlayMCP",
      "version": "1.0.0"
    }
  }
}
```

**응답:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "My MCP Server",
      "version": "1.0.0"
    }
  }
}
```

### 3.2 tools/list
사용 가능한 도구 목록 반환

**요청:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

**응답:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "send_message",
        "description": "카카오톡 나와의 채팅방에 메시지를 전송합니다",
        "inputSchema": {
          "type": "object",
          "properties": {
            "message": {
              "type": "string",
              "description": "전송할 메시지 내용"
            }
          },
          "required": ["message"]
        }
      }
    ]
  }
}
```

### 3.3 tools/call
도구 실행

**요청:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "send_message",
    "arguments": {
      "message": "안녕하세요! 테스트 메시지입니다."
    }
  }
}
```

**응답 (성공):**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "메시지가 성공적으로 전송되었습니다."
      }
    ]
  }
}
```

**응답 (에러):**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32000,
    "message": "메시지 전송에 실패했습니다."
  }
}
```

---

## 4. Python 서버 예제 (FastAPI)

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

# MCP 서버 정보
SERVER_INFO = {
    "name": "MyMCP",
    "version": "1.0.0"
}

# 도구 정의
TOOLS = [
    {
        "name": "send_message",
        "description": "카카오톡 나와의 채팅방에 메시지를 전송합니다",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "전송할 메시지 내용"
                }
            },
            "required": ["message"]
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

        if tool_name == "send_message":
            message = arguments.get("message")
            # 여기서 실제 카카오 API 호출
            result = f"메시지 전송 완료: {message}"

            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": result}]
                }
            })

        # 알 수 없는 도구
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
        })

    # 알 수 없는 메서드
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"}
    })

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 5. Node.js 서버 예제 (Express)

```javascript
const express = require('express');
const app = express();

app.use(express.json());

const SERVER_INFO = {
  name: "MyMCP",
  version: "1.0.0"
};

const TOOLS = [
  {
    name: "send_message",
    description: "카카오톡 나와의 채팅방에 메시지를 전송합니다",
    inputSchema: {
      type: "object",
      properties: {
        message: {
          type: "string",
          description: "전송할 메시지 내용"
        }
      },
      required: ["message"]
    }
  }
];

app.post('/mcp', (req, res) => {
  const { method, params = {}, id } = req.body;

  // initialize
  if (method === 'initialize') {
    return res.json({
      jsonrpc: "2.0",
      id,
      result: {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: SERVER_INFO
      }
    });
  }

  // tools/list
  if (method === 'tools/list') {
    return res.json({
      jsonrpc: "2.0",
      id,
      result: { tools: TOOLS }
    });
  }

  // tools/call
  if (method === 'tools/call') {
    const { name, arguments: args = {} } = params;

    if (name === 'send_message') {
      const { message } = args;
      // 여기서 실제 카카오 API 호출

      return res.json({
        jsonrpc: "2.0",
        id,
        result: {
          content: [{ type: "text", text: `메시지 전송 완료: ${message}` }]
        }
      });
    }

    return res.json({
      jsonrpc: "2.0",
      id,
      error: { code: -32601, message: `Unknown tool: ${name}` }
    });
  }

  // Unknown method
  res.json({
    jsonrpc: "2.0",
    id,
    error: { code: -32601, message: `Unknown method: ${method}` }
  });
});

app.listen(8000, () => console.log('MCP Server running on port 8000'));
```

---

## 6. PlayMCP 특화 설정

### 6.1 MCP 식별자 (Prefix)
- PlayMCP에서 도구 이름 앞에 붙는 접두사
- LLM이 중복 도구를 구분하는 데 사용
- 개발자 콘솔에서 설정 가능

### 6.2 인증 방식

**방식 1: Key/Token (간단)**
```
Authorization: Bearer <your-token>
```

**방식 2: OAuth (PlayMCP Gateway 연동)**
- PlayMCP Gateway 통해 사용자 인증
- 사용자의 카카오 계정 데이터 접근 가능

### 6.3 에러 코드
| 코드 | 의미 |
|------|------|
| -32700 | Parse error |
| -32600 | Invalid Request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error |
| -32000 ~ -32099 | Server error (커스텀) |

---

## 7. 공모전 1등 팁

### 서비스 안정성
- 모든 예외 상황 처리
- 타임아웃 설정 (30초 이내 응답)
- 재시도 로직 구현
- 헬스체크 엔드포인트 추가

### 편의성
- 도구 이름: 직관적이고 명확하게
- description: 한글로 상세히
- inputSchema: 모든 파라미터 설명 포함
- 에러 메시지: 사용자 친화적으로

### 창의성
- 기존에 없는 새로운 기능
- 카카오 생태계 시너지
- 실용적인 활용 가치

---

## 8. 다음 단계

- [03_호스팅_및_배포.md](./03_호스팅_및_배포.md) - 서버 배포 방법
