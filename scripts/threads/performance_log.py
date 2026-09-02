#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""performance_log.py — Threads 발행 성과 측정 (Phase 38 자가개선 루프)

[1] 측정: record_publish() — 발행 성공 시 메타 기록 (API 0 call)
[2] 수집: collect_insights() — 일 1회 views/likes/replies/reposts/quotes 수집 + net_replies 보정
[3] 분석: analyze() — 30일 집계 → insights_report.json (≥30 posts 시만)

파일:
  - logs/performance_log.json  (posts 배열 append-only)
  - logs/insights_report.json  (analyze 산출물)

stdlib only. 토큰은 publisher.load_env() (EnvConfig) 경로만 사용.
"""
import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

THREADS_DIR = os.path.join(_project_root, 'scripts', 'threads')
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

PERF_LOG = os.path.join(LOGS_DIR, 'performance_log.json')
REPORT = os.path.join(LOGS_DIR, 'insights_report.json')

INSIGHTS_METRICS = ['views', 'likes', 'replies', 'reposts', 'quotes']
THREADS_API_HOST = 'graph.threads.net'
SELF_USERNAME = 'aikorea24'  # 자기 링크 답글 식별용


def _log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] [perf] {msg}')


def _load():
    if os.path.exists(PERF_LOG):
        try:
            with open(PERF_LOG, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get('posts'), list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {'posts': []}


def _atomic_save(data):
    tmp = PERF_LOG + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PERF_LOG)


# ---------- [1] 측정 ----------

def record_publish(root_id, posted_at, fmt, article_id, title, source, topic_tags=None):
    """발행 성공 직후 호출. 실패해도 발행 흐름에 영향 없음(호출부에서 try/except)."""
    data = _load()
    data['posts'].append({
        'root_id': str(root_id),
        'posted_at': posted_at or datetime.now().isoformat(),
        'format': fmt or 'D',
        'article_id': str(article_id) if article_id is not None else '',
        'title': (title or '')[:120],
        'source': source or '',
        'topic_tags': topic_tags,
        'metrics': None,  # collect_insights가 채움
    })
    _atomic_save(data)
    return True


# ---------- [2] 수집 ----------

def _get(url, token, timeout=30, retries=1):
    """GET with Bearer-style token param. 실패 시 예외 (호출부가 error 기록)."""
    sep = '&' if '?' in url else '?'
    full = f'{url}{sep}access_token={urllib.parse.quote(token)}'
    last = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(full, headers={'User-Agent': 'aikorea24-perf/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:  # noqa: BLE001 — error 문자열로 기록 후 계속
            last = e
    raise last


def _fetch_insights(root_id, token):
    """GET /{id}/insights?metric=views,likes,replies,reposts,quotes → {metric: value}"""
    qs = urllib.parse.urlencode({'metric': ','.join(INSIGHTS_METRICS)})
    data = _get(f'https://{THREADS_API_HOST}/v1.0/{root_id}/insights?{qs}', token)
    out = {}
    for item in data.get('data', []):
        name = item.get('name', '')
        vals = item.get('values', [])
        if name == 'thread_replies':
            name = 'replies'
        if vals and name in INSIGHTS_METRICS:
            try:
                out[name] = int(vals[0].get('value', 0))
            except (TypeError, ValueError):
                pass
    return out


def _external_reply_count(root_id, token):
    """root 직접 답글 중 외부(자기 아님) 답글 개수. 실패 시 -1.

    주의: insights의 `replies`(thread_replies)는 스레드 전체 답글 수로
    자기 카드 체인(카드2~5)과 🔗 링크 답글까지 포함됨 (라이브 검증:
    2026-09-01 18:00 포스트 replies=5 = 자기 답글 전부, 외부 0).
    따라서 net_replies는 차감이 아니라 root 직접 답글의 외부 개수로 직접 산출.
    """
    qs = urllib.parse.urlencode({'fields': 'id,text,username', 'limit': 50})
    data = _get(f'https://{THREADS_API_HOST}/v1.0/{root_id}/replies?{qs}', token)
    count = 0
    for r in data.get('data', []):
        username = (r.get('username') or '').strip().lower()
        if username and username != SELF_USERNAME:
            count += 1
            continue
        # username 누락 시 🔗 링크 답글은 자기 답글로 간주 (우리 파이프 형식)
        text = r.get('text') or ''
        if not text.startswith('🔗') and username != SELF_USERNAME:
            pass  # username 없고 🔗 아님 — 불명확, 미카운트 (과다계상 방지)
    return count


def collect_insights(days=2):
    """metrics==None이고 posted_at이 days일 내인 포스트만 수집·갱신."""
    from publisher import load_env
    envs = load_env()
    token = envs.get('THREADS_ACCESS_TOKEN', '')
    if not token:
        _log('❌ 토큰 없음 — 수집 중단')
        return 0

    data = _load()
    cutoff = datetime.now() - timedelta(days=days)
    updated = 0
    for post in data['posts']:
        if post.get('metrics') is not None:
            continue
        try:
            posted_dt = datetime.fromisoformat((post.get('posted_at') or '').split('.')[0])
        except ValueError:
            posted_dt = None
        if posted_dt and posted_dt < cutoff:
            continue

        root_id = post.get('root_id', '')
        if not root_id:
            post['metrics'] = {'error': 'no root_id'}
            updated += 1
            continue

        try:
            metrics = _fetch_insights(root_id, token)
            replies = metrics.get('replies', 0)
            if replies > 0:
                external = _external_reply_count(root_id, token)
                # replies edge 실패(-1) 시: 자기 링크 답글 1개 가정 fallback.
                # 외부 답글이 남는지 검증 불가 상황 → 보수적으로 replies-1.
                metrics['net_replies'] = max(0, replies - 1) if external < 0 else external
            else:
                metrics['net_replies'] = 0
            post['metrics'] = metrics
            updated += 1
            _log(f'수집 {root_id}: views={metrics.get("views")} net_replies={metrics.get("net_replies")}')
        except Exception as e:  # noqa: BLE001 — error 기록 후 계속
            post['metrics'] = {'error': str(e)[:200]}
            updated += 1
            _log(f'⚠️ {root_id} 수집 실패 (error 기록 후 계속): {e}')

    if updated:
        _atomic_save(data)
    _log(f'수집 완료: {updated}건 갱신 (전체 {len(data["posts"])}건)')
    return updated


# ---------- [3] 분석 ----------

def _avg(values):
    return round(sum(values) / len(values), 2) if values else 0


def analyze(window_days=30, min_posts=30):
    """최근 window_days일 metrics 완비 포스트 ≥ min_posts일 때만 report 생성."""
    data = _load()
    cutoff = datetime.now() - timedelta(days=window_days)
    posts = []
    for p in data['posts']:
        m = p.get('metrics') or {}
        if not isinstance(m, dict) or 'views' not in m or m.get('error'):
            continue
        try:
            dt = datetime.fromisoformat((p.get('posted_at') or '').split('.')[0])
        except ValueError:
            continue
        if dt >= cutoff:
            posts.append(p)

    if len(posts) < min_posts:
        _log(f'분석 스킵: {len(posts)}/{min_posts}건 — 부트스트랩 기간')
        return None

    def group_stats(key_fn):
        groups = {}
        for p in posts:
            k = key_fn(p)
            if not k:
                continue
            groups.setdefault(k, []).append(p)
        return {
            k: {
                'n': len(v),
                'avg_views': _avg([p['metrics']['views'] for p in v]),
                'avg_likes': _avg([p['metrics'].get('likes', 0) for p in v]),
                'avg_net_replies': _avg([p['metrics'].get('net_replies', 0) for p in v]),
                'engagement_rate': _avg([
                    (p['metrics'].get('likes', 0) + p['metrics'].get('net_replies', 0))
                    / p['metrics']['views'] if p['metrics']['views'] else 0
                    for p in v
                ]),
            }
            for k, v in groups.items()
        }

    by_format = group_stats(lambda p: p.get('format') or 'D')
    by_topic = group_stats(lambda p: (p.get('topic_tags') or [None])[0] if p.get('topic_tags') else None)
    by_source = group_stats(lambda p: p.get('source') or None)

    def slot_of(p):
        try:
            return datetime.fromisoformat((p.get('posted_at') or '').split('.')[0]).strftime('%H:00')
        except ValueError:
            return None
    by_slot = group_stats(slot_of)

    # 상위 토픽 3개 (topic_tags 없으면 source 기준 fallback)
    topic_pool = by_topic if by_topic else by_source
    top_topics = sorted(
        [(k, v['avg_views']) for k, v in topic_pool.items() if k],
        key=lambda x: -x[1],
    )[:3]

    report = {
        'generated_at': datetime.now().isoformat(),
        'window_days': window_days,
        'n_posts': len(posts),
        'by_format': by_format,
        'by_topic': by_topic,
        'by_source': by_source,
        'by_slot': by_slot,
        'top_topics': [{'topic': t, 'avg_views': v} for t, v in top_topics],
    }
    tmp = REPORT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    os.replace(tmp, REPORT)
    _log(f'리포트 생성: {REPORT} ({len(posts)}건, top_topics={[t for t, _ in top_topics]})')
    return report


if __name__ == '__main__':
    collect_insights()
    analyze()
