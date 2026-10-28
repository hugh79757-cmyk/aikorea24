#!/usr/bin/env python3
"""aikorea24 데일리 파이프라인 (Blog Pipeline)

뉴스 → 브리핑 → 썸네일 → 이메일 → 배포:
1. 뉴스 선정 (auto_news_selector)
2. 브리핑 생성 (auto_briefing)
3. 썸네일 생성
4. 이메일 발송
5. 빌드 + 배포

Usage:
    python3 scripts/run_pipeline.py [--collect] [--skip-news] [--skip-briefing]
    python3 scripts/run_pipeline.py [--skip-email] [--skip-thumbnails] [--skip-deploy]
    python3 scripts/run_pipeline.py [--date YYYY-MM-DD] [--dry-run]
"""
import argparse
import html
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure scripts/ is importable
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
sys.path.insert(0, str(_SCRIPTS_DIR))
# 프로젝트 루트도 import 가능하게 한다 (pipeline.infra.telegram 등 공용 헬퍼 사용).
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


KST = timezone(timedelta(hours=9))


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


class _StdoutTee:
    """표준출력을 그대로 화면에 흘려보내면서 문자열로 모은다.

    왜 필요한가 (AIK24-PIPE-ALERT-01): auto_briefing 은 브리핑을 못 만든 사유를
    로그 문자열로만 남긴다("이미 오늘 브리핑 발행됨" 등). 파이프라인이 그 사유를
    알아야 "왜 0건"을 보고할 수 있다. 출력을 삼키지 않고 그대로 보여준다
    (launchd 로그가 달라지지 않는다).
    """

    def __init__(self, orig):
        self._orig = orig
        self._parts = []

    def write(self, s):
        self._parts.append(s)
        self._orig.write(s)
        return len(s)

    def flush(self):
        try:
            self._orig.flush()
        except Exception:  # noqa: BLE001 — flush 실패로 파이프라인을 죽이지 않는다
            pass

    def getvalue(self):
        return "".join(self._parts)

    def __getattr__(self, name):
        # isatty/encoding/fileno 등 나머지는 원본 stdout 으로 위임한다.
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._orig, name)


def step_news_selection():
    """Step 1: 뉴스 선정"""
    import auto_news_selector

    log("═══ Step 1: 뉴스 선정 ═══")
    selected = auto_news_selector.main()
    if not selected:
        log("선정된 뉴스가 없습니다.")
        return []
    return selected


def step_briefing(articles):
    """Step 2: 브리핑 생성 (articles 전달 시 해당 기사로 생성). briefing_id 반환."""
    import auto_briefing

    log("═══ Step 2: 브리핑 생성 ═══")
    if articles:
        return auto_briefing.main(articles)
    elif articles is None:
        return auto_briefing.main()
    else:
        log("  선정된 기사가 없어 브리핑을 건너뜁니다.")
        return None


def step_briefing_with_log(articles):
    """Step 2 래퍼 — (briefing_id, auto_briefing 로그) 반환.

    원래 stdout 을 그대로 흘려보내므로 화면·launchd 로그는 그대로고, 로그 문자열만
    추가로 얻는다 (AIK24-PIPE-ALERT-01).
    """
    orig = sys.stdout
    tee = _StdoutTee(orig)
    sys.stdout = tee
    try:
        result = step_briefing(articles)
    finally:
        sys.stdout = orig
    return result, tee.getvalue()


def briefing_cause_of(briefing_log, selected_count):
    """브리핑 0건 원인 추정 (best effort) — auto_briefing 로그 문자열 기준."""
    log_text = briefing_log or ""
    if "이미 오늘 브리핑 발행됨" in log_text or "이미 오늘 브리핑이 published 입니다" in log_text:
        return "오늘 브리핑이 이미 발행됨(하루 1회 정책) — 신규 0건"
    if "빈 브리핑 저장 없음" in log_text:
        # AIK24-PIPE-12: 폴백(일반 뉴스) 후에도 3건 미만이면 저장하지 않고 중단한다.
        return "선정 부족(폴백·재충원 후보 없음) — 빈 브리핑 미저장"
    if "선정된 기사 없음" in log_text or "수집된 뉴스 없음" in log_text:
        return "선정된 기사 0건"
    if "브리핑 생성 실패" in log_text or "D1 실행 오류" in log_text:
        return "D1 저장 실패"
    if not selected_count:
        return "선정된 뉴스 0건"
    return "브리핑 id 미반환 (저장 실패 또는 이미 발행됨)"


# ---------------------------------------------------------------------------
# AIK24-PIPE-08 — B-1 수집 상태 확인 / B-2 후보 풀 깊이 조기 경보
#
# 2026-10-21 07:00 사고: D1 읽기 가드(82.1%)가 05:30 수집을 죽여 후보 풀이 전날
# 잔여분으로 고정 → 선정 3건이 Phase 2 dedup 에서 3/3 탈락 → 브리핑 0건 →
# 그런데도 exit 0 + "✅ 에러 없음" + 텔레그램 "Briefing published"(가짜 성공).
#
# ALERT-01(커밋 31a32e19)이 0건을 exit 1 로 만들었고, 여기(B-2)는 **한 단계 앞**에서
# 알려준다 — LLM 채점을 돌리기 전에 신선 후보 수를 세어 MAX_COUNT 미만이면 조기 경보 1회.
#
# **게이트가 아니라 경보다.** 브리핑 생성을 막지 않는다. 후보가 진짜 없으면 빈 슬롯을
# 유지하고 알림으로 알린다 (AIK24-PIPE-04 "강제 충전 금지" 원칙 유지).
# 경고는 summary['warnings'] 에만 담는다 → summary['errors'] 와 분리되어 exit 코드에
# 영향이 없다. (0건 자체는 ALERT-01 이 exit 1 로 만든다.)
# ---------------------------------------------------------------------------

# 수집기 상태 파일 (AIK24-PIPE-08 B-1) — 수집기가 쓰고, 파이프라인은 읽기만 한다.
COLLECTOR_STATE_FILENAME = ".collector_state.json"
COLLECTOR_STATE_PATH = _SCRIPTS_DIR / COLLECTOR_STATE_FILENAME
# 상태 파일의 'at' 이 이 시간보다 오래면 "이전 실행"으로 본다 (05:30 수집 → 07:00 파이프라인
# = 1.5시간 차이. 6시간 여유를 두어 수동 실행(오후)도 오늘 파일로 판정되게 한다).
COLLECTOR_STATE_MAX_AGE_HOURS = 6
# auto_news_selector.MAX_COUNT 폴백 (scripts/auto_news_selector.py:39 = 3)
MAX_COUNT_FALLBACK = 3

# 조기 경보 1회 보장 (런 안에서 여러 번 검사해도 1회만 발송)
_EARLY_ALERT_STATE = {"sent": False}


def reset_early_alert_state():
    """조기 경보 1회 발송 상태 초기화 (테스트용)."""
    _EARLY_ALERT_STATE["sent"] = False


def resolve_max_count():
    """auto_news_selector.MAX_COUNT 를 읽는다 (헬퍼 없으면 기본 3)."""
    try:
        import auto_news_selector
        return int(getattr(auto_news_selector, "MAX_COUNT", MAX_COUNT_FALLBACK))
    except Exception:  # noqa: BLE001 — import 실패해도 파이프라인은 계속
        return MAX_COUNT_FALLBACK


def count_fresh_candidates(d1_query_func=None):
    """신선 후보 수 — auto_news_selector.count_fresh_candidates 래퍼 (AIK24-PIPE-08 B-2).

    헬퍼는 "최종 dedup 기준(D1 이력 + local 이력)까지 통과했을 후보 수"를 돌려준다
    (side effect 없음). 헬퍼가 아직 없거나 예외가 나면 **None** 을 돌려준다 —
    fail soft: 파이프라인을 죽이지 않고 조기 경보만 건너뛴다.
    """
    try:
        import auto_news_selector
    except Exception as e:  # noqa: BLE001
        log(f"  ⚠️ auto_news_selector import 실패(무시): {type(e).__name__}: {e}")
        return None
    fn = getattr(auto_news_selector, "count_fresh_candidates", None)
    if fn is None:
        log("  ⚠️ auto_news_selector.count_fresh_candidates 없음 — 후보 깊이 판정 생략")
        return None
    query = d1_query_func
    if query is None:
        try:
            from pipeline.infra.d1_client import d1_query
            query = d1_query
        except Exception as e:  # noqa: BLE001
            log(f"  ⚠️ d1_query import 실패(무시): {type(e).__name__}: {e}")
            return None
    try:
        return int(fn(query))
    except Exception as e:  # noqa: BLE001
        log(f"  ⚠️ 신선 후보 수 계산 실패(무시): {type(e).__name__}: {e}")
        return None


def _parse_iso(text):
    """ISO8601 문자열 → datetime. 파싱 실패/빈 값이면 None. naive 는 KST 로 간주."""
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt


def _local_date(dt):
    """datetime → 로컬 달력일. naive 는 이미 로컬 시각으로 간주한다."""
    if dt.tzinfo is None:
        return dt.date()
    return dt.astimezone().date()


def _is_fresh(at_dt, now_dt):
    """상태 파일이 '오늘 수집 결과'인지 판정.

    규칙: ① 로컬 달력일이 같으면 오늘 것  ② 또는 now - at 이 6시간 이내면 오늘 것
    ③ 그 외는 이전 실행 → stale.
    """
    if _local_date(at_dt) == _local_date(now_dt):
        return True
    now_aware = now_dt.astimezone() if now_dt.tzinfo is None else now_dt
    age_hours = (now_aware - at_dt).total_seconds() / 3600.0
    return 0 <= age_hours <= COLLECTOR_STATE_MAX_AGE_HOURS


def read_collector_state(path=None, now=None):
    """수집기 상태 파일 읽기 (AIK24-PIPE-08 B-1) — **읽기 전용**.

    기대 스키마:
      {"status": "aborted"|"reduced"|"ok"|"error",
       "reason": "<사유>", "at": "<ISO8601 KST>", "collected": <int>}

    반환 dict:
      status     : 파일의 status (파일이 없으면 "missing", 깨졌으면 "invalid")
      reason/at/collected : 원본 값
      freshness  : "fresh"(오늘) | "stale"(이전 실행) | "unknown"(판정 불가)
                    | "missing"(파일 없음) | "invalid"(읽기 실패)
    """
    p = Path(path) if path else COLLECTOR_STATE_PATH
    now_dt = now or datetime.now()
    result = {
        "status": "missing",
        "reason": "",
        "at": "",
        "collected": 0,
        "freshness": "missing",
        "path": str(p),
    }
    if not p.exists():
        return result
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as e:
        result["status"] = "invalid"
        result["reason"] = f"파일 읽기 실패: {type(e).__name__}"
        result["freshness"] = "invalid"
        return result
    try:
        data = json.loads(raw)
    except ValueError:
        result["status"] = "invalid"
        result["reason"] = "JSON 파싱 실패"
        result["freshness"] = "invalid"
        return result
    if not isinstance(data, dict):
        result["status"] = "invalid"
        result["reason"] = "JSON 형식 아님"
        result["freshness"] = "invalid"
        return result

    result["status"] = str(data.get("status") or "unknown")
    result["reason"] = str(data.get("reason") or "")
    result["at"] = str(data.get("at") or "")
    try:
        result["collected"] = int(data.get("collected") or 0)
    except (TypeError, ValueError):
        result["collected"] = 0

    at_dt = _parse_iso(result["at"])
    if at_dt is None:
        result["freshness"] = "unknown"
    elif _is_fresh(at_dt, now_dt):
        result["freshness"] = "fresh"
    else:
        result["freshness"] = "stale"
    return result


def collector_state_warning(state, fresh_count=None, max_count=MAX_COUNT_FALLBACK):
    """수집 상태 → 요약 경고 문구 (경고가 없으면 None).

    판정표 (AIK24-PIPE-08 B-1):
      · status=='ok' + 오늘 파일            → 경고 없음
      · status!='ok' + 오늘 파일            → "수집 단계 이상: ..." (강한 문구)
      · 이전 실행의 파일(stale)              → "수집 상태 오래됨: ..." (약한 문구)
      · 파일 없음/깨짐                       → "알 수 없음" — 단독으로는 경고 아님.
        후보 풀도 부족할 때만 함께 적는다.
    """
    state = state or {}
    status = state.get("status") or "unknown"
    freshness = state.get("freshness") or "unknown"
    reason = state.get("reason") or "사유 미상"
    at = state.get("at") or "시간 미상"

    if status == "ok":
        if freshness == "fresh":
            return None
        return f"수집 상태 확인 안 됨: {status} ({at}) — 오늘 수집 결과 확인 안 됨"

    if status in ("missing", "invalid"):
        if fresh_count is not None and fresh_count < max_count:
            return "수집 상태 알 수 없음 (파일 없음 또는 읽기 실패) — 후보 풀이 전날 잔여분일 수 있음"
        return None

    # aborted / reduced / error / unknown
    if freshness == "fresh":
        return f"수집 단계 이상: {status} ({reason}) — 후보 풀이 전날 잔여분일 수 있음"
    if freshness == "stale":
        return f"수집 상태 오래됨: {status} ({reason}, {at}) — 오늘 수집 결과 확인 안 됨"
    if fresh_count is not None and fresh_count < max_count:
        return (f"수집 단계 이상: {status} ({reason}) — 시간 정보 불명 — "
                "후보 풀이 전날 잔여분일 수 있음")
    return None


def _default_notifier(message):
    """조기 경보 알림 채널 — Telegram (파이프라인 알림 채널과 동일).

    실패해도 파이프라인은 계속된다 (경보일 뿐이다).
    """
    try:
        from pipeline.infra.telegram import send_telegram
        return bool(send_telegram(message))
    except Exception as e:  # noqa: BLE001
        log(f"  ⚠️ 텔레그램 조기 경보 전송 실패(무시): {type(e).__name__}: {e}")
        return False


def send_early_alert(fresh, max_count, collector=None, notify=None):
    """후보 풀 부족 조기 경보 **1회** 발송 (AIK24-PIPE-08 B-2).

    - 브리핑 생성을 막지 않는다 (경보 전용).
    - 한 런에서 최대 1회만 발송한다 (_EARLY_ALERT_STATE).
    """
    if _EARLY_ALERT_STATE["sent"]:
        return False
    _EARLY_ALERT_STATE["sent"] = True
    sender = notify or _default_notifier
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "⚠️ <b>aikorea24 파이프라인 조기 경보</b>",
        f"⏰ {now}",
        "",
        f"후보 풀 부족: 신선 후보 {fresh}건 (최소 {max_count}건 필요)",
        f"브리핑 슬롯 {max_count}개를 채울 후보가 부족합니다. 파이프라인은 계속 진행합니다.",
    ]
    note = collector_state_warning(collector, fresh_count=fresh, max_count=max_count)
    if note:
        lines.append(html.escape(note))
    try:
        ok = bool(sender("\n".join(lines)))
    except Exception as e:  # noqa: BLE001
        log(f"  ⚠️ 조기 경보 전송 실패(무시): {type(e).__name__}: {e}")
        ok = False
    log(f"  ⚠️ 조기 경보 발송({'성공' if ok else '실패'}) — "
        f"신선 후보 {fresh}건 < 최소 {max_count}건")
    return ok


def check_candidate_depth(query_func=None, state_path=None, now=None, notify=None):
    """후보 풀 깊이 검사 + 수집 상태 확인 (AIK24-PIPE-08 B-1/B-2).

    반환: {"fresh": int|None, "max_count": int, "warnings": [str],
           "collector": dict, "alert_sent": bool}
    """
    max_count = resolve_max_count()
    fresh = count_fresh_candidates(query_func)
    state = read_collector_state(path=state_path, now=now)

    warnings = []
    if fresh is not None and fresh < max_count:
        warnings.append(f"후보 풀 부족: 신선 후보 {fresh}건 (최소 {max_count}건 필요)")
    collector_warning = collector_state_warning(state, fresh_count=fresh, max_count=max_count)
    if collector_warning:
        warnings.append(collector_warning)

    alert_sent = False
    if fresh is not None and fresh < max_count:
        alert_sent = send_early_alert(fresh, max_count, collector=state, notify=notify)

    return {
        "fresh": fresh,
        "max_count": max_count,
        "warnings": warnings,
        "collector": state,
        "alert_sent": alert_sent,
    }


def apply_depth_warnings(summary, query_func=None, state_path=None, now=None, notify=None):
    """depth 검사 결과를 summary['warnings'] 에만 담는다 (errors 는 건드리지 않는다).

    → 경고는 요약·알림에만 남고 exit 코드에는 영향이 없다 (조기 경보 = advisory).
    """
    depth = check_candidate_depth(query_func=query_func, state_path=state_path,
                                  now=now, notify=notify)
    summary.setdefault("warnings", []).extend(depth["warnings"])
    summary["fresh_candidates"] = depth["fresh"]
    summary["max_count"] = depth["max_count"]
    summary["collector_state"] = depth["collector"]
    return depth


def step_blog_link():
    """Step 1.5: AIK24-PIPE-05 — 무료 모델 news 행 ↔ AIK24 블로그 글 매칭.

    무료 모델의 AIK24 블로그 글(blog_link)을 채운다. **"원문 보기"에는 더 이상
    쓰지 않는다** — AIK24-PIPE-07 부터 원문 보기는 제공사 모델 페이지
    (COALESCE(n.origin_link, n.link))로 연결한다. blog_link 는 심층 분석·역링크
    등 후속 기능의 참조용으로 유지한다.
    """
    import blog_link_resolver

    log("═══ Step 1.5: 무료 모델 → 블로그 링크 매칭 ═══")
    try:
        stats = blog_link_resolver.resolve()
    except Exception as e:
        log(f"  ⚠️ blog_link 매칭 실패 (브리핑은 계속): {type(e).__name__}: {str(e)[:160]}")
        return None
    log(f"  모델 {stats['models']}개 중 매칭 {stats['matched_models']}개 · "
        f"연결 {stats['linked_rows']}행 · 글 필요 큐 {stats['queued_models']}개")
    return stats


def step_thumbnails(articles):
    """Step 4: 썸네일 생성"""
    import auto_thumbnail

    log("═══ Step 3: 썸네일 생성 ═══")
    import re as re_mod

    results = []
    for i, art in enumerate(articles, 1):
        title = art.get("title", "")
        url = art.get("link", "")
        slug = re_mod.sub(r"[^a-z0-9가-힣]+", "-", title.lower())[:60].strip("-")
        log(f"  [{i}/{len(articles)}] {title[:60]}")

        if not url:
            log("    URL 없음, 스킵")
            continue

        try:
            rel_path = auto_thumbnail.process_thumbnail(url, slug, title=title, description=art.get("description", ""))
            if rel_path:
                log(f"    ✅ {rel_path}")
                results.append({"title": title, "thumbnail": rel_path})
            else:
                log("    ❌ 썸네일 생성 실패")
        except Exception as e:
            log(f"    ❌ 에러: {e}")

    return results


def step_email():
    """Step 4: 이메일 발송"""
    import auto_email_sender

    log("═══ Step 4: 이메일 발송 ═══")
    auto_email_sender.main()


def step_deploy():
    """Step 5: 빌드 + Cloudflare Pages 배포"""
    log("═══ Step 5: 빌드 + 배포 ═══")
    deploy_script = str(Path(__file__).resolve().parent / "deploy.sh")
    if not Path(deploy_script).exists():
        log("  deploy.sh 없음, 건너뜀")
        return

    result = subprocess.run(
        ["/bin/bash", deploy_script],
        capture_output=True, text=True, timeout=300, cwd=str(Path(__file__).resolve().parent.parent)
    )
    for line in result.stdout.splitlines():
        log(f"  {line}")
    if result.returncode != 0:
        log(f"  ❌ 배포 실패 (rc={result.returncode})")
        if result.stderr:
            for line in result.stderr.splitlines()[-5:]:
                log(f"  ⚠ {line}")
        raise RuntimeError(f"배포 실패 (rc={result.returncode})")
    else:
        log("  ✅ 배포 완료")


def main():
    parser = argparse.ArgumentParser(
        description="aikorea24 데일리 파이프라인",
        epilog="전체 워크플로우: 뉴스선정 → 브리핑 → 썸네일 → 이메일 → 빌드/배포",
    )
    parser.add_argument("--collect", action="store_true",
                        help="Step 0 v2 소스 수집 실행 (기본: 05:30 수집기에 이관되어 스킵)")
    parser.add_argument("--skip-news", action="store_true", help="뉴스 선정 단계 건너뜀")
    parser.add_argument("--skip-briefing", action="store_true", help="브리핑 생성 단계 건너뜀")
    parser.add_argument("--skip-blog-link", action="store_true",
                        help="무료 모델 → 블로그 링크 매칭 단계 건너뜀 (AIK24-PIPE-05)")
    parser.add_argument("--skip-thumbnails", action="store_true", help="썸네일 생성 단계 건너뜀")
    parser.add_argument("--skip-email", action="store_true", help="이메일 발송 단계 건너뜀")
    parser.add_argument("--no-email", action="store_true",
                        help="이메일 발송 안 함 (수동 실행용, --skip-email과 동일. 자동 스케줄 실행에는 사용 금지)")
    parser.add_argument("--skip-deploy", action="store_true", help="빌드/배포 단계 건너뜀")
    parser.add_argument("--date", help="날짜 지정 (YYYY-MM-DD 형식, 기본값: 오늘)")
    parser.add_argument("--dry-run", action="store_true", help="실행하지 않고 계획만 출력")
    args = parser.parse_args()

    log("╔══════════════════════════════════════╗")
    log("║  aikorea24 데일리 파이프라인 시작    ║")
    log("╚══════════════════════════════════════╝")
    log("")

    start_time = datetime.now()
    summary = {
        "news": [],
        # AIK24-PIPE-ALERT-01: 실제 저장된 브리핑 수 (선정 건수와 반드시 분리한다)
        "briefings": 0,
        "thumbnails": [],
        "errors": [],
        # AIK24-PIPE-08 B-1/B-2: 조기 경보 사유 (errors 와 분리 — exit 코드에 영향 없음)
        "warnings": [],
    }

    if args.dry_run:
        log("DRY RUN 모드 - 실행하지 않음")
        steps = []
        if not args.skip_news:
            steps.append("1. 뉴스 선정")
        if not args.skip_blog_link:
            steps.append("1.5. 무료 모델 → 블로그 링크 매칭")
        if not args.skip_briefing:
            steps.append("2. 브리핑 생성")
        if not args.skip_thumbnails:
            steps.append("3. 썸네일 생성")
        if not args.skip_email and not args.no_email:
            steps.append("4. 이메일 발송")
        if not args.skip_deploy:
            steps.append("5. 빌드/배포")
        for s in steps:
            log(f"  → {s}")
        return

    # Step 0: v2 소스 수집 (AIK24-PIPE-02 Step 2/4)
    # AIK24-EFFICIENCY-02: 05:30 launchd 수집기(kr.aikorea24.news-unified)가 같은 소스를
    # 수집한다. Step 0 은 205건 중 신규 2건(99% 중복)에 228초를 썼다.
    # → 기본 스킵. 수집기 실패 시 `run_pipeline.py --collect` 로 수동 복구한다.
    #   (호출부와 수집기 코드는 지시서 §4-2 에 따라 남겨둔다)
    if not args.collect:
        log("⏭ Step 0 수집 스킵 (05:30 수집기에 이관) — 수동 실행 시 --collect")
    else:
        try:
            log("Step 0: v2 소스 수집 (OpenRouter free / HF trending / 공식 RSS)")
            r = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parent / "news_collector_v2.py")],
                capture_output=True, text=True, timeout=300,
            )
            for line in (r.stdout or "").splitlines()[-4:]:
                log(f"  {line}")
            if r.returncode != 0:
                log(f"  v2 수집기 실패 rc={r.returncode}: {(r.stderr or '')[:200]}")
        except Exception as e:
            log(f"v2 수집 에러(무시하고 계속): {e}")

    # AIK24-PIPE-08 B-2/B-1: 후보 풀 깊이 조기 경보 + 수집 단계 상태 요약.
    # LLM 채점(Step 1) **전에** 신선 후보 수를 세고, MAX_COUNT 미만이면 조기 경보를
    # 1회 발송한다. 브리핑 생성은 막지 않는다 (조기 경보 = advisory).
    # --skip-news 는 LLM 채점을 돌지 않으므로 검사도 건너뛴다.
    if not args.skip_news:
        depth = apply_depth_warnings(summary)
        for w in depth["warnings"]:
            log(f"  ⚠️ {w}")
    else:
        log("ⓘ 뉴스 선정 건너뜀 — 후보 깊이 조기 경보 생략")

    # Step 1: 뉴스 선정
    articles = []
    if not args.skip_news:
        try:
            articles = step_news_selection()
            summary["news"] = [a.get("title", "") for a in articles]
        except Exception as e:
            log(f"뉴스 선정 에러: {e}")
            traceback.print_exc()
            summary["errors"].append(f"뉴스 선정: {e}")
    else:
        log("⏭ 뉴스 선정 건너뜀")

    log("")

    # Step 2: 브리핑 생성 (step 1의 기사 목록 전달)
    briefing_id = None
    briefing_count = 0
    briefing_cause = ""
    briefing_exc = False
    if not args.skip_briefing:
        try:
            briefing_id, briefing_log = step_briefing_with_log(articles)
            # AIK24-PIPE-ALERT-01: "생성 브리핑" 은 실제 저장된 건수만 센다.
            # auto_briefing.save_briefing() 이 D1 INSERT 후 새 row id 를 돌려주고,
            # auto_briefing.main() 은 그 id 를 그대로 반환한다(없으면 None = 저장 실패/건너뜀).
            briefing_count = 1 if briefing_id else 0
            if not briefing_count:
                briefing_cause = briefing_cause_of(briefing_log, len(articles))
                log(f"  ⚠️ 브리핑 0건 — {briefing_cause}")
        except Exception as e:
            briefing_exc = True
            log(f"브리핑 생성 에러: {e}")
            traceback.print_exc()
            summary["errors"].append(f"브리핑 생성: {e}")
    else:
        log("⏭ 브리핑 생성 건너뜀")
        briefing_cause = "단계 건너뜀(--skip-briefing)"
    summary["briefings"] = briefing_count

    # AIK24-PIPE-ALERT-01: 브리핑 0건 = 실패 (가짜 성공 알림 방지).
    # 2026-10-21 실측: 뉴스 3건 선정 → 브리핑 0건 저장인데도 errors 가 비어 있어
    # "✅ 에러 없음"(exit 0)으로 끝나고, 텔레그램은 "Briefing published" 를 알렸다.
    # 선정 건수와 실제 저장 건수를 분리해, 0건이면 같은 errors 구조에 넣는다.
    # 제외: --skip-briefing / --skip-news 는 단계 자체를 돌지 않은 의도된 실행이다
    # (문서화된 "이메일만 단독 실행" 워크플로의 exit 0 을 깨지 않기 위해).
    if (not args.skip_briefing and not args.skip_news
            and briefing_count == 0 and not briefing_exc):
        summary["errors"].append(f"브리핑 미생성: {briefing_cause or '사유 미상'}")

    log("")

    # Step 1.5: 무료 모델 → 블로그 링크 매칭 (AIK24-PIPE-05)
    # 브리핑 생성 전에 blog_link 를 채운다. "원문 보기"는 AIK24-PIPE-07 부터
    # 렌더링 시점에 COALESCE(n.origin_link, n.link) — 제공사 모델 페이지 — 로 연결된다.
    if not args.skip_blog_link:
        try:
            step_blog_link()
        except Exception as e:
            log(f"blog_link 매칭 단계 오류(무시하고 계속): {e}")
            traceback.print_exc()
            summary["errors"].append(f"blog_link 매칭: {e}")
    else:
        log("⏭ Step 1.5 blog_link 매칭 건너뜀")

    log("")

    log("")

    # Step 4: 썸네일 생성
    if not args.skip_thumbnails:
        try:
            if not articles:
                log("선정된 뉴스가 없어 썸네일을 건너뜁니다.")
            else:
                thumb_results = step_thumbnails(articles)
                summary["thumbnails"] = [r["thumbnail"] for r in thumb_results]
        except Exception as e:
            log(f"썸네일 생성 에러: {e}")
            traceback.print_exc()
            summary["errors"].append(f"썸네일 생성: {e}")
    else:
        log("⏭ 썸네일 생성 건너뜀")

    log("")

    # Step 5: 이메일 발송 (--no-email이면 절대 발송 금지: 수동 실행용)
    if args.no_email:
        log("[pipeline] --no-email: 이메일 발송 건너뜀")
    elif not args.skip_email:
        if not briefing_id:
            # 2026-10-16: 새 브리핑이 없으면(이미 오늘 발행됨/후보 없음) 이메일도 보내지 않는다.
            # 종전에는 브리핑 생성과 무관하게 발송해, 같은 날 재실행마다 같은 브리핑이
            # 중복 발송됐다 (실측: 10-16 브리핑 2건 → 이메일 2회).
            log("⏭ 새 브리핑이 없어 이메일 발송 건너뜀 (중복 발송 방지)")
        else:
            try:
                step_email()
            except Exception as e:
                log(f"이메일 발송 에러: {e}")
                traceback.print_exc()
                summary["errors"].append(f"이메일 발송: {e}")
    else:
        log("⏭ 이메일 발송 건너뜀")

    log("")

    # Step 6: 빌드 + 배포
    if not args.skip_deploy:
        try:
            step_deploy()
        except Exception as e:
            log(f"배포 에러: {e}")
            traceback.print_exc()
            summary["errors"].append(f"배포: {e}")
    else:
        log("⏭ 빌드/배포 건너뜀")

    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    log("")
    log("╔══════════════════════════════════════╗")
    log("║  파이프라인 완료                      ║")
    log("╚══════════════════════════════════════╝")
    log(f"  소요 시간: {elapsed:.1f}초")
    log(f"  선정 뉴스: {len(summary['news'])}건")
    log(f"  생성 브리핑: {summary['briefings']}건")
    log(f"  썸네일:   {len(summary['thumbnails'])}건")
    if summary.get("fresh_candidates") is not None:
        log(f"  신선 후보: {summary['fresh_candidates']}건 "
            f"(최소 {summary.get('max_count')}건 필요)")

    # AIK24-PIPE-08: 경고는 요약에만 남는다 (errors 가 아니므로 exit 코드에 영향 없음).
    if summary.get("warnings"):
        log(f"  ⚠️  경고: {len(summary['warnings'])}건")
        for warn in summary["warnings"]:
            log(f"    - {warn}")

    if summary["errors"]:
        log(f"  ⚠️  에러: {len(summary['errors'])}건")
        for err in summary["errors"]:
            log(f"    - {err}")
        sys.exit(1)
    else:
        log("  ✅ 에러 없음")


if __name__ == "__main__":
    main()
