"""
날짜/시간 파싱 모듈
한국어 자연어에서 날짜와 시간 추출
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple


def parse_datetime(text: str) -> Optional[datetime]:
    """
    텍스트에서 날짜/시간 추출

    지원하는 표현:
    - 날짜: 오늘, 내일, 모레, 글피, 이번주 X요일, 다음주 X요일
    - 시간: X시, 오전/오후 X시, X시 반, X시 X분
    - 복합: 내일 3시, 다음주 월요일 오후 2시

    Returns:
        datetime 객체 또는 None
    """
    text = text.lower().strip()

    # 날짜 파싱
    date = parse_date(text)

    # 시간 파싱
    time = parse_time(text)

    if date is None and time is None:
        return None

    # 날짜만 있으면 오전 9시 기본값
    if date and time is None:
        return date.replace(hour=9, minute=0, second=0, microsecond=0)

    # 시간만 있으면 오늘 또는 내일
    if time and date is None:
        now = datetime.now()
        hour, minute = time
        result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # 이미 지난 시간이면 내일로
        if result <= now:
            result += timedelta(days=1)
        return result

    # 둘 다 있으면 합치기
    if date and time:
        hour, minute = time
        return date.replace(hour=hour, minute=minute, second=0, microsecond=0)

    return None


def parse_date(text: str) -> Optional[datetime]:
    """날짜 파싱"""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 오늘/내일/모레/글피
    if "오늘" in text:
        return today
    if "내일" in text:
        return today + timedelta(days=1)
    if "모레" in text:
        return today + timedelta(days=2)
    if "글피" in text:
        return today + timedelta(days=3)

    # 요일 처리
    weekdays = {
        "월요일": 0, "월": 0,
        "화요일": 1, "화": 1,
        "수요일": 2, "수": 2,
        "목요일": 3, "목": 3,
        "금요일": 4, "금": 4,
        "토요일": 5, "토": 5,
        "일요일": 6, "일": 6,
    }

    for day_name, day_num in weekdays.items():
        if day_name in text:
            # 다음주 X요일
            if "다음주" in text or "다음 주" in text:
                days_ahead = day_num - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                days_ahead += 7  # 다음주니까 +7
                return today + timedelta(days=days_ahead)

            # 이번주 X요일 또는 그냥 X요일
            days_ahead = day_num - today.weekday()
            if days_ahead < 0:  # 이미 지난 요일이면 다음주
                days_ahead += 7
            elif days_ahead == 0:  # 오늘이면 오늘
                pass
            return today + timedelta(days=days_ahead)

    # 이번주/다음주/이번달/다음달
    if "이번주" in text or "이번 주" in text:
        # 이번주 일요일 (주의 마지막)
        days_ahead = 6 - today.weekday()
        return today + timedelta(days=days_ahead)

    if "다음주" in text or "다음 주" in text:
        # 다음주 월요일
        days_ahead = 7 - today.weekday()
        return today + timedelta(days=days_ahead)

    if "이번달" in text or "이번 달" in text:
        # 이번달 말일
        next_month = today.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        return last_day

    if "다음달" in text or "다음 달" in text:
        # 다음달 1일
        if today.month == 12:
            return today.replace(year=today.year + 1, month=1, day=1)
        return today.replace(month=today.month + 1, day=1)

    # 특정 날짜 패턴: X월 X일, X/X, X-X
    date_patterns = [
        r'(\d{1,2})월\s*(\d{1,2})일',  # 1월 15일
        r'(\d{1,2})/(\d{1,2})',  # 1/15
        r'(\d{1,2})-(\d{1,2})',  # 1-15
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            try:
                result = today.replace(month=month, day=day)
                # 이미 지난 날짜면 내년
                if result < today:
                    result = result.replace(year=result.year + 1)
                return result
            except ValueError:
                pass

    return None


def parse_time(text: str) -> Optional[Tuple[int, int]]:
    """시간 파싱 -> (hour, minute) 튜플"""

    # 오전/오후 처리
    is_pm = "오후" in text or "저녁" in text or "밤" in text
    is_am = "오전" in text or "아침" in text

    # 시간 패턴들
    patterns = [
        r'(\d{1,2})시\s*(\d{1,2})분',  # 3시 30분
        r'(\d{1,2})시\s*반',  # 3시 반
        r'(\d{1,2})시',  # 3시
        r'(\d{1,2}):(\d{2})',  # 15:30
    ]

    for i, pattern in enumerate(patterns):
        match = re.search(pattern, text)
        if match:
            hour = int(match.group(1))

            if i == 0:  # X시 X분
                minute = int(match.group(2))
            elif i == 1:  # X시 반
                minute = 30
            elif i == 2:  # X시
                minute = 0
            elif i == 3:  # HH:MM
                minute = int(match.group(2))
            else:
                minute = 0

            # 오전/오후 변환
            if is_pm and hour < 12:
                hour += 12
            elif is_am and hour == 12:
                hour = 0
            # 애매한 경우 (오전/오후 명시 안됨)
            elif not is_am and not is_pm:
                # 1~6시는 오후로 추정 (낮 시간대)
                if 1 <= hour <= 6:
                    hour += 12

            return (hour, minute)

    return None


def extract_reminder_info(text: str) -> dict:
    """
    텍스트에서 리마인더 정보 추출

    Returns:
        {
            "reminder_at": datetime or None,
            "reminder_text": str (시간 표현 제거된 텍스트),
            "has_time": bool
        }
    """
    reminder_at = parse_datetime(text)

    # 시간 관련 키워드 제거하여 핵심 내용 추출
    time_keywords = [
        r'\d{1,2}월\s*\d{1,2}일',
        r'\d{1,2}/\d{1,2}',
        r'\d{1,2}-\d{1,2}',
        r'오전|오후|아침|저녁|밤',
        r'\d{1,2}시\s*\d{0,2}분?',
        r'\d{1,2}시\s*반',
        r'\d{1,2}:\d{2}',
        r'오늘|내일|모레|글피',
        r'이번\s*주|다음\s*주|이번주|다음주',
        r'이번\s*달|다음\s*달|이번달|다음달',
        r'월요일|화요일|수요일|목요일|금요일|토요일|일요일',
        r'까지|전에|마감',
    ]

    cleaned_text = text
    for pattern in time_keywords:
        cleaned_text = re.sub(pattern, '', cleaned_text)

    # 공백 정리
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    return {
        "reminder_at": reminder_at,
        "reminder_text": cleaned_text if cleaned_text else text,
        "has_time": reminder_at is not None
    }


def format_reminder_time(dt: datetime) -> str:
    """리마인더 시간을 읽기 좋게 포맷"""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    target_day = dt.replace(hour=0, minute=0, second=0, microsecond=0)

    diff_days = (target_day - today).days

    # 날짜 부분
    if diff_days == 0:
        date_str = "오늘"
    elif diff_days == 1:
        date_str = "내일"
    elif diff_days == 2:
        date_str = "모레"
    elif diff_days < 7:
        weekdays = ["월", "화", "수", "목", "금", "토", "일"]
        date_str = f"{weekdays[dt.weekday()]}요일"
    else:
        date_str = f"{dt.month}월 {dt.day}일"

    # 시간 부분
    hour = dt.hour
    minute = dt.minute

    if hour < 12:
        time_str = f"오전 {hour}시"
    elif hour == 12:
        time_str = "낮 12시"
    else:
        time_str = f"오후 {hour - 12}시"

    if minute > 0:
        time_str += f" {minute}분"

    return f"{date_str} {time_str}"


# 테스트
if __name__ == "__main__":
    test_cases = [
        "내일 병원 3시 예약",
        "다음주 금요일 회의",
        "모레 오후 2시 30분 미팅",
        "12월 25일 크리스마스",
        "이번주 토요일 약속",
        "3시까지 보고서 제출",
        "아침 9시 운동",
        "저녁 7시 저녁약속",
    ]

    for text in test_cases:
        result = extract_reminder_info(text)
        print(f"\n입력: {text}")
        print(f"  시간: {result['reminder_at']}")
        if result['reminder_at']:
            print(f"  포맷: {format_reminder_time(result['reminder_at'])}")
        print(f"  내용: {result['reminder_text']}")
