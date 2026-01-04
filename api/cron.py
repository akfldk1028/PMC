"""
리마인더 체크 Cron API
Vercel Cron에서 1분마다 호출하여 알림 발송
"""
import sys
import os

# lib 모듈 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from lib.redis_db import get_pending_reminders, mark_reminder_sent, get_memo_by_id
from lib.datetime_parser import format_reminder_time
from datetime import datetime

app = FastAPI()


@app.get("/api/cron/reminders")
async def check_reminders(request: Request):
    """
    리마인더 체크 - Vercel Cron에서 호출
    1분마다 실행되어 현재 시간 이전의 리마인더 발송
    """
    try:
        # 대기 중인 리마인더 조회
        pending = await get_pending_reminders()

        if not pending:
            return JSONResponse({
                "ok": True,
                "message": "No pending reminders",
                "count": 0
            })

        sent_count = 0
        errors = []

        for item in pending:
            user_id = item["user_id"]
            memo_id = item["memo_id"]
            memo = item["memo"]

            try:
                # 카카오톡 알림 발송 (나에게 보내기)
                # TODO: 실제 카카오 알림 API 연동
                reminder_time = memo.get("reminder_at", "")
                summary = memo.get("summary", memo.get("content", "")[:50])

                notification_text = f"⏰ 리마인더\n\n{summary}\n\n예정: {reminder_time[:16] if reminder_time else '시간 미지정'}"

                print(f"[REMINDER] Sending to {user_id}: {summary}")

                # 발송 완료 처리
                await mark_reminder_sent(user_id, memo_id)
                sent_count += 1

            except Exception as e:
                error_msg = f"Failed to send reminder {memo_id}: {str(e)}"
                print(f"[REMINDER ERROR] {error_msg}")
                errors.append(error_msg)

        return JSONResponse({
            "ok": True,
            "message": f"Processed {len(pending)} reminders",
            "sent": sent_count,
            "errors": errors if errors else None
        })

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[CRON ERROR] {e}\n{error_detail}")
        return JSONResponse({
            "ok": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/cron/health")
async def health_check():
    """헬스 체크"""
    return JSONResponse({
        "ok": True,
        "service": "reminder-cron",
        "timestamp": datetime.now().isoformat()
    })


# 로컬 실행용
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
