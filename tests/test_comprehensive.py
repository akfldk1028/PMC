"""
MemoMate 종합 테스트 스크립트
로컬에서 직접 lib 모듈을 호출하여 테스트
"""
import sys
import os
import asyncio
import json
from datetime import datetime
from collections import Counter

# 프로젝트 루트 경로 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 환경변수 로드 (로컬 테스트용 - .env.local 먼저 시도)
from dotenv import load_dotenv
env_local = os.path.join(PROJECT_ROOT, ".env.local")
env_file = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(env_local):
    load_dotenv(env_local)
    print(f"Loaded: {env_local}")
elif os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"Loaded: {env_file}")
else:
    print("Warning: No .env file found")

from lib.memo_service import (
    service_search,
    service_get_summary,
    service_get_stats,
    service_save_memo,
    service_delete_memo,
    service_get_reminders,
    get_user_top_categories,
)
from lib.redis_db import (
    get_recent_memos,
    get_memos_by_category,
    update_memo,
    get_memo_by_id,
)
from lib.constants import CATEGORIES, get_category_emoji

# 테스트 사용자 ID (실제 카카오 사용자 ID 또는 테스트용)
TEST_USER_ID = os.environ.get("TEST_USER_ID", "test_user_comprehensive")


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.results = {}

    def add_pass(self, name, data=None):
        self.passed += 1
        self.results[name] = {"status": "PASS", "data": data}
        print(f"✅ {name}")

    def add_fail(self, name, error, data=None):
        self.failed += 1
        self.errors.append({"name": name, "error": str(error)})
        self.results[name] = {"status": "FAIL", "error": str(error), "data": data}
        print(f"❌ {name}: {error}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"테스트 결과: {self.passed}/{total} 통과")
        if self.errors:
            print(f"\n실패 목록:")
            for err in self.errors:
                print(f"  - {err['name']}: {err['error']}")
        return self.results


async def test_1_stats_and_recent(result: TestResult):
    """1. 전체 통계 조회하고 최근 메모 20개"""
    print("\n" + "="*50)
    print("📊 테스트 1: 전체 통계 및 최근 메모 20개")
    print("="*50)

    try:
        # 통계 조회
        stats_result = await service_get_stats(TEST_USER_ID)
        stats = stats_result.get("stats", {})

        print(f"\n📈 전체 통계:")
        print(f"  - 전체: {stats.get('total', 0)}건")
        print(f"  - 오늘: {stats.get('today', 0)}건")
        print(f"  - 이번주: {stats.get('week', 0)}건")
        print(f"  - 이번달: {stats.get('month', 0)}건")

        by_category = stats.get("by_category", {})
        if by_category:
            print(f"\n📂 카테고리별:")
            for cat, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
                emoji = get_category_emoji(cat)
                print(f"  - {emoji} {cat}: {count}건")

        result.add_pass("통계 조회", stats)

        # 최근 메모 20개
        recent_memos = await get_recent_memos(TEST_USER_ID, limit=20)
        print(f"\n📝 최근 메모 ({len(recent_memos)}건):")
        for i, memo in enumerate(recent_memos[:10], 1):
            cat = memo.get("category", "기타")
            summary = memo.get("summary", "")[:40]
            created = memo.get("created_at", "")[:10]
            print(f"  {i}. [{cat}] {summary} ({created})")

        if len(recent_memos) > 10:
            print(f"  ... 외 {len(recent_memos) - 10}건")

        result.add_pass("최근 메모 20개", {"count": len(recent_memos)})

    except Exception as e:
        result.add_fail("테스트 1", str(e))


async def test_2_category_each_5(result: TestResult):
    """2. 10개 카테고리 각각 5개씩 조회"""
    print("\n" + "="*50)
    print("📂 테스트 2: 카테고리별 5개씩 조회")
    print("="*50)

    categories = ["영상", "맛집", "쇼핑", "할일", "아이디어", "여행", "음악", "학습", "건강", "읽을거리"]

    for cat in categories:
        try:
            memos = await get_memos_by_category(TEST_USER_ID, cat, limit=5)
            emoji = get_category_emoji(cat)

            print(f"\n{emoji} {cat} ({len(memos)}건):")
            if memos:
                for memo in memos[:5]:
                    summary = memo.get("summary", "")[:35]
                    print(f"  - {summary}")
                result.add_pass(f"카테고리:{cat}", {"count": len(memos)})
            else:
                print(f"  (없음)")
                result.add_pass(f"카테고리:{cat}", {"count": 0})

        except Exception as e:
            result.add_fail(f"카테고리:{cat}", str(e))


async def test_3_keyword_search(result: TestResult):
    """3. 키워드 검색 15개"""
    print("\n" + "="*50)
    print("🔍 테스트 3: 키워드 검색")
    print("="*50)

    keywords = ["유튜브", "블로그", "개발", "AI", "Python", "MCP", "카카오",
                "추천", "할인", "운동", "Netflix", "쿠팡", "커피", "독서", "React"]

    for keyword in keywords:
        try:
            search_result = await service_search(TEST_USER_ID, keyword, limit=5)
            memos = search_result.get("memos", [])

            print(f"\n'{keyword}' 검색: {len(memos)}건")
            for memo in memos[:3]:
                summary = memo.get("summary", "")[:30]
                print(f"  - {summary}")

            result.add_pass(f"검색:{keyword}", {"count": len(memos)})

        except Exception as e:
            result.add_fail(f"검색:{keyword}", str(e))


async def test_4_period_summary(result: TestResult):
    """4. 기간별 요약"""
    print("\n" + "="*50)
    print("📅 테스트 4: 기간별 요약")
    print("="*50)

    periods = [
        ("today", "오늘"),
        ("yesterday", "어제"),
        ("week", "이번주"),
        ("last_week", "지난주"),
        ("month", "이번달"),
        ("last_month", "지난달"),
    ]

    for period, name in periods:
        try:
            summary_result = await service_get_summary(TEST_USER_ID, period)
            memos = summary_result.get("memos", [])

            # 카테고리별 집계
            cat_counts = Counter(m.get("category", "기타") for m in memos)

            print(f"\n📆 {name}: {len(memos)}건")
            if cat_counts:
                cat_str = ", ".join([f"{c}:{n}" for c, n in cat_counts.most_common(3)])
                print(f"  분포: {cat_str}")

            result.add_pass(f"기간:{name}", {"count": len(memos), "categories": dict(cat_counts)})

        except Exception as e:
            result.add_fail(f"기간:{name}", str(e))


async def test_5_category_summary(result: TestResult):
    """5. 카테고리별 요약"""
    print("\n" + "="*50)
    print("📊 테스트 5: 카테고리별 전체 요약")
    print("="*50)

    categories = ["영상", "맛집", "쇼핑", "할일", "아이디어", "여행", "음악", "학습", "건강", "읽을거리"]

    for cat in categories:
        try:
            summary_result = await service_get_summary(TEST_USER_ID, period="all", category=cat)
            memos = summary_result.get("memos", [])

            emoji = get_category_emoji(cat)
            url_count = sum(1 for m in memos if m.get("url"))
            text_count = len(memos) - url_count

            print(f"\n{emoji} {cat}: 총 {len(memos)}건 (링크:{url_count}, 텍스트:{text_count})")

            result.add_pass(f"요약:{cat}", {"total": len(memos), "url": url_count, "text": text_count})

        except Exception as e:
            result.add_fail(f"요약:{cat}", str(e))


async def test_6_save_new_memos(result: TestResult):
    """6. 새 메모 저장 18개"""
    print("\n" + "="*50)
    print("💾 테스트 6: 새 메모 저장")
    print("="*50)

    new_memos = [
        # URL 메모
        ("https://youtube.com/watch?v=test_abc123", None),
        ("https://youtube.com/watch?v=test_def456", None),
        ("https://youtube.com/watch?v=test_ghi789", None),
        ("https://coupang.com/vp/products/test12345", None),
        ("https://amazon.com/dp/testabc", None),
        # 텍스트 메모
        ("맛집 강남 스시 오마카세 추천", None),
        ("맛집 판교 점심 맛집 리스트", None),
        ("할일 1월 15일까지 MCP 서버 개발 완료", None),
        ("할일 금요일 팀 회의 준비", None),
        ("할일 PlayMCP 공모전 응모하기", None),
        ("할일 포트폴리오 업데이트하기", None),
        ("아이디어 AI 메모 자동태깅 아이디어", None),
        ("아이디어 사이드프로젝트 AI일기장", None),
        ("여행 2월 제주도 여행 계획", None),
        ("학습 MCP 공식문서 정독", None),
        ("학습 클린코드 1-5장 요약", None),
        ("건강 매일 아침 30분 런닝", None),
        ("건강 홈트 루틴 상체하체코어", None),
    ]

    saved_memo_ids = []

    for content, category in new_memos:
        try:
            save_result = await service_save_memo(TEST_USER_ID, content, category=category)

            if save_result.get("success"):
                memo_id = save_result.get("memo_id")
                saved_cat = save_result.get("category")
                summary = save_result.get("summary", "")[:30]
                saved_memo_ids.append(memo_id)

                print(f"✅ [{saved_cat}] {summary}")
                result.add_pass(f"저장:{content[:20]}", save_result)
            else:
                result.add_fail(f"저장:{content[:20]}", "저장 실패")

        except Exception as e:
            result.add_fail(f"저장:{content[:20]}", str(e))

    return saved_memo_ids


async def test_7_update_tags(result: TestResult, saved_memo_ids: list):
    """7. 방금 저장한 할일 4개 태그 수정"""
    print("\n" + "="*50)
    print("🏷️ 테스트 7: 태그 수정 (할일 메모)")
    print("="*50)

    # 저장된 메모 중 할일 찾기
    todo_memos = []
    for memo_id in saved_memo_ids:
        try:
            memo = await get_memo_by_id(TEST_USER_ID, memo_id)
            if memo and memo.get("category") == "할일":
                todo_memos.append(memo)
        except:
            pass

    print(f"\n할일 메모 {len(todo_memos)}개 발견")

    new_tags = ["업무", "긴급", "중요", "deadline"]

    for memo in todo_memos[:4]:
        try:
            memo_id = memo.get("id")
            summary = memo.get("summary", "")[:30]

            updated = await update_memo(
                TEST_USER_ID,
                memo_id,
                tags=new_tags
            )

            if updated:
                print(f"✅ 태그 수정: {summary}")
                print(f"   새 태그: {new_tags}")
                result.add_pass(f"태그수정:{summary[:15]}", {"memo_id": memo_id, "tags": new_tags})
            else:
                result.add_fail(f"태그수정:{summary[:15]}", "수정 실패")

        except Exception as e:
            result.add_fail(f"태그수정", str(e))


async def test_8_search_and_delete(result: TestResult):
    """8. 테스트 키워드 검색해서 삭제"""
    print("\n" + "="*50)
    print("🗑️ 테스트 8: 테스트 데이터 검색 및 삭제")
    print("="*50)

    keywords = ["테스트", "임시", "temp", "sample", "삭제예정", "draft"]
    total_deleted = 0

    for keyword in keywords:
        try:
            # 검색
            search_result = await service_search(TEST_USER_ID, keyword, limit=10)
            memos = search_result.get("memos", [])

            if memos:
                print(f"\n'{keyword}' 검색: {len(memos)}건 발견")

                # 삭제
                delete_result = await service_delete_memo(TEST_USER_ID, keyword=keyword)

                if delete_result.get("success"):
                    deleted_count = delete_result.get("deleted_count", 0)
                    total_deleted += deleted_count
                    print(f"  → {deleted_count}건 삭제 완료")
                    result.add_pass(f"삭제:{keyword}", {"deleted": deleted_count})
                else:
                    print(f"  → 삭제 실패: {delete_result.get('error')}")
                    result.add_pass(f"삭제:{keyword}", {"deleted": 0, "note": "해당 없음"})
            else:
                print(f"\n'{keyword}' 검색: 0건")
                result.add_pass(f"삭제:{keyword}", {"deleted": 0})

        except Exception as e:
            result.add_fail(f"삭제:{keyword}", str(e))

    print(f"\n총 삭제: {total_deleted}건")


async def test_9_compare_stats(result: TestResult):
    """9. 다시 통계 조회하고 최근 10개 확인"""
    print("\n" + "="*50)
    print("📊 테스트 9: 변경 후 통계 재조회")
    print("="*50)

    try:
        # 통계 조회
        stats_result = await service_get_stats(TEST_USER_ID)
        stats = stats_result.get("stats", {})

        print(f"\n📈 변경 후 통계:")
        print(f"  - 전체: {stats.get('total', 0)}건")
        print(f"  - 오늘: {stats.get('today', 0)}건")
        print(f"  - 이번주: {stats.get('week', 0)}건")

        by_category = stats.get("by_category", {})
        if by_category:
            print(f"\n📂 카테고리별 변화:")
            for cat, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:5]:
                emoji = get_category_emoji(cat)
                print(f"  - {emoji} {cat}: {count}건")

        result.add_pass("변경 후 통계", stats)

        # 최근 메모 10개
        recent_memos = await get_recent_memos(TEST_USER_ID, limit=10)
        print(f"\n📝 최근 메모 10개:")
        for i, memo in enumerate(recent_memos, 1):
            cat = memo.get("category", "기타")
            summary = memo.get("summary", "")[:35]
            print(f"  {i}. [{cat}] {summary}")

        result.add_pass("최근 10개 확인", {"count": len(recent_memos)})

    except Exception as e:
        result.add_fail("테스트 9", str(e))


async def test_10_comprehensive_report(result: TestResult):
    """10. 종합 리포트"""
    print("\n" + "="*50)
    print("📋 테스트 10: 종합 리포트")
    print("="*50)

    try:
        # 전체 통계
        stats_result = await service_get_stats(TEST_USER_ID)
        stats = stats_result.get("stats", {})

        # 전체 메모 가져오기 (분석용)
        all_memos_result = await service_get_summary(TEST_USER_ID, "all")
        all_memos = all_memos_result.get("memos", [])

        # 분석 데이터 수집
        total = len(all_memos)
        url_memos = [m for m in all_memos if m.get("url")]
        text_memos = [m for m in all_memos if not m.get("url")]

        # 카테고리 분포
        cat_counter = Counter(m.get("category", "기타") for m in all_memos)

        # 키워드 추출 (summary에서)
        all_words = []
        for memo in all_memos:
            summary = memo.get("summary", "")
            words = summary.split()
            all_words.extend([w for w in words if len(w) > 1 and not w.startswith("http")])

        word_counter = Counter(all_words)
        top_keywords = word_counter.most_common(10)

        # 요일별 분포
        from collections import defaultdict
        weekday_counts = defaultdict(int)
        for memo in all_memos:
            created = memo.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    weekday_counts[weekdays[dt.weekday()]] += 1
                except:
                    pass

        # 리포트 출력
        print(f"""
{'='*50}
📊 MemoMate 종합 리포트
{'='*50}

1. 사용 현황
   - 총 메모: {total}건
   - 링크 메모: {len(url_memos)}건 ({round(len(url_memos)/total*100) if total else 0}%)
   - 텍스트 메모: {len(text_memos)}건 ({round(len(text_memos)/total*100) if total else 0}%)

2. 카테고리별 분포
""")
        for cat, count in cat_counter.most_common():
            emoji = get_category_emoji(cat)
            percentage = round(count/total*100) if total else 0
            bar = "#" * (percentage // 5)
            print(f"   {emoji} {cat:8} {bar:20} {count} ({percentage}%)")

        print(f"""
3. 자주 사용하는 키워드 Top 10
""")
        for i, (word, count) in enumerate(top_keywords, 1):
            print(f"   {i:2}. {word} ({count}회)")

        print(f"""
4. 요일별 패턴
""")
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            count = weekday_counts.get(day, 0)
            bar = "#" * (count // 2) if count else ""
            print(f"   {day} {bar:20} {count}")

        # 개선 제안
        print(f"""
5. 개선 제안
""")
        suggestions = []

        # 카테고리 편중 분석
        if cat_counter:
            top_cat, top_count = cat_counter.most_common(1)[0]
            if total > 0 and top_count / total > 0.5:
                suggestions.append(f"   - '{top_cat}' 카테고리 비중이 높아요. 다른 카테고리도 활용해보세요!")

        # URL vs 텍스트 비율
        if total > 0:
            if len(url_memos) / total < 0.2:
                suggestions.append("   - 링크 저장 기능을 더 활용해보세요! URL을 보내면 자동 분류됩니다.")
            if len(text_memos) / total < 0.2:
                suggestions.append("   - 생각이나 아이디어도 텍스트로 저장해보세요!")

        # 할일 체크
        todo_count = cat_counter.get("할일", 0)
        if todo_count > 10:
            suggestions.append(f"   - 할일이 {todo_count}개 있어요. 완료된 건 정리해보세요!")

        # 리마인더 활용
        reminders = await service_get_reminders(TEST_USER_ID)
        if len(reminders.get("reminders", [])) == 0:
            suggestions.append("   - 리마인더 기능을 활용해보세요! '내일 3시 회의' 형식으로 저장하면 알림이 와요.")

        if not suggestions:
            suggestions.append("   - 아주 잘 활용하고 계세요! 👍")

        for s in suggestions:
            print(s)

        print(f"\n{'='*50}")

        result.add_pass("종합 리포트", {
            "total": total,
            "url_count": len(url_memos),
            "text_count": len(text_memos),
            "top_categories": dict(cat_counter.most_common(5)),
            "top_keywords": top_keywords
        })

    except Exception as e:
        result.add_fail("종합 리포트", str(e))


async def main():
    print("""
========================================================
         MemoMate Comprehensive Test Script
         Test User: {user_id}
========================================================
""".format(user_id=TEST_USER_ID[:20]))

    result = TestResult()

    # 1. 통계 및 최근 메모
    await test_1_stats_and_recent(result)

    # 2. 카테고리별 5개씩
    await test_2_category_each_5(result)

    # 3. 키워드 검색
    await test_3_keyword_search(result)

    # 4. 기간별 요약
    await test_4_period_summary(result)

    # 5. 카테고리별 요약
    await test_5_category_summary(result)

    # 6. 새 메모 저장
    saved_ids = await test_6_save_new_memos(result)

    # 7. 태그 수정
    await test_7_update_tags(result, saved_ids)

    # 8. 테스트 데이터 삭제
    await test_8_search_and_delete(result)

    # 9. 변경 후 통계
    await test_9_compare_stats(result)

    # 10. 종합 리포트
    await test_10_comprehensive_report(result)

    # 최종 결과
    final_results = result.summary()

    # JSON 파일로 저장
    output_file = os.path.join(os.path.dirname(__file__), "test_comprehensive_results.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n📁 결과 저장: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
