"""Public X material collection using pinned x-tweet-fetcher; screenshots use host tools."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit

VENDOR = Path(__file__).resolve().parents[1] / 'references/vendor/x-tweet-fetcher'
sys.path.insert(0, str(VENDOR / 'src'))
from xtf import http
from xtf.backends.fxtwitter import API, normalize_tweet_json
from xtf.exceptions import NotFound, RateLimited, UpstreamDown, XtfError


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def tweet_url(value):
    parsed = urlsplit(value.strip())
    if parsed.scheme not in ('http', 'https') or parsed.netloc.lower() not in ('x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'):
        raise ValueError('Expected a public x.com or twitter.com tweet URL')
    match = re.fullmatch(r'/([A-Za-z0-9_]{1,15})/status/(\d{1,25})(?:/(?:photo|video)/\d+)?/?', parsed.path)
    if not match:
        raise ValueError('Expected /USERNAME/status/ID; standalone X Articles use the host browser')
    user, ident = match.groups()
    return f'https://x.com/{user}/status/{ident}', user, ident


def published_at(raw):
    timestamp = raw.get('created_timestamp')
    try:
        if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
            return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
        value = parsedate_to_datetime(raw.get('created_at', ''))
        if value.tzinfo is None:
            return None
        return value.isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def validate_payload(payload, ident):
    if not isinstance(payload, dict):
        raise UpstreamDown('Invalid public API response')
    code = payload.get('code')
    if code == 404:
        raise NotFound('Public tweet not found')
    if code in (403, 429):
        raise RateLimited('Public tweet service rate limited')
    if code != 200 or not isinstance(payload.get('tweet'), dict):
        raise UpstreamDown('Public tweet service returned no tweet')
    raw = payload['tweet']
    if raw.get('id') is not None and str(raw['id']) != ident:
        raise UpstreamDown('Returned tweet ID differs from requested ID')
    if not isinstance(raw.get('author'), dict) or not isinstance(raw.get('text', ''), str):
        raise UpstreamDown('Returned tweet has an invalid author or text shape')
    author = raw['author'].get('screen_name', '')
    if not re.fullmatch(r'[A-Za-z0-9_]{1,15}', author):
        raise UpstreamDown('Returned tweet has no valid author handle')
    return raw


def fetch_one(url, run, cache_dir=None, max_age=1800, refresh=False, timeout=15):
    start = time.perf_counter()
    public_url, user, ident = tweet_url(url)
    run = Path(run).resolve()
    cache_path = Path(cache_dir) / f'{ident}.json' if cache_dir else None
    payload, fetched_at, cache_hit = None, None, False
    if cache_path and cache_path.is_file() and not refresh:
        try:
            cached = json.loads(cache_path.read_text(encoding='utf-8'))
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached['fetched_at'])).total_seconds()
            if 0 <= age <= max_age:
                validate_payload(cached['payload'], ident)
                payload, fetched_at, cache_hit = cached['payload'], cached['fetched_at'], True
        except (OSError, ValueError, KeyError, TypeError, XtfError):
            pass
    endpoint = f'{API}/{user}/status/{ident}'
    if payload is None:
        # One bounded public request. No browser import, credential reads or retry backoff.
        payload = http.get_json(endpoint, timeout=timeout, retries=0)
        raw = validate_payload(payload, ident)
        fetched_at = now()
    raw = validate_payload(payload, ident)
    tweet = normalize_tweet_json(raw)
    article = tweet.get('article', {})
    if not tweet.get('text', '').strip() and not article.get('full_text', '').strip():
        raise UpstreamDown('No readable tweet or attached article text was returned')
    if cache_path and not cache_hit:
        save(cache_path, {'fetched_at': fetched_at, 'payload': payload})
    public_url = f"https://x.com/{raw['author']['screen_name']}/status/{ident}"
    partial_article = bool(raw.get('article')) and (
        bool(raw['article'].get('is_partial')) or not article.get('full_text', '').strip())
    access = 'author_caption' if partial_article else 'full_text'
    parts = [f'Public URL: {public_url}', f"Author: {tweet['author']} (@{tweet['screen_name']})",
             f"Published: {tweet.get('created_at', '')}", '\nTweet text\n', tweet.get('text', '')]
    if tweet.get('quote'):
        quote = tweet['quote']
        parts += ['\nQuoted tweet (separate author)\n', f"@{quote['screen_name']}", quote.get('text', '')]
    if article:
        parts += ['\nAttached article\n', article.get('title', ''),
                  article.get('full_text') or article.get('preview_text', '')]
    if raw.get('community_note'):
        parts += ['\nCommunity note (as returned by proxy)\n', json.dumps(raw['community_note'], ensure_ascii=False)]
    folder = run / 'readings/x' / ident
    raw_file, reading = folder / 'raw.json', folder / 'reading.txt'
    save(raw_file, payload)
    reading.write_text('\n'.join(parts) + '\n', encoding='utf-8')
    record = {'status': 'readable_material', 'tweet_id': ident, 'url': public_url,
              'backend': 'x-tweet-fetcher/fxtwitter', 'transport': 'third_party_public_proxy',
              'api_url': endpoint, 'fetched_at': fetched_at, 'reused_at': now() if cache_hit else None,
              'cache_hit': cache_hit, 'published_at': published_at(raw),
              'metrics': {key: raw.get(key) for key in ('likes', 'retweets', 'views', 'bookmarks', 'replies')},
              'metrics_note': 'Proxy snapshot, potentially cached; verify important counts on the visible source page.',
              'article_partial': partial_article, 'tweet': tweet,
              'raw_path': raw_file.relative_to(run).as_posix(), 'raw_sha256': sha(raw_file),
              'read_record': {'access': access, 'artifact_path': reading.relative_to(run).as_posix(),
                              'artifact_sha256': sha(reading)},
              'seconds': round(time.perf_counter()-start, 4)}
    save(folder / 'record.json', record)
    return record


def collect(urls, run, cache_dir=None, max_age=1800, refresh=False, timeout=15):
    unique = {}
    for url in urls:
        canonical, _, ident = tweet_url(url)
        unique.setdefault(ident, canonical)
    if not unique or len(unique) > 12:
        raise ValueError('Provide 1–12 unique public tweet URLs per bounded batch')
    run = Path(run).resolve()
    def task(url):
        try:
            return fetch_one(url, run, cache_dir, max_age, refresh, timeout)
        except (XtfError, ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
            return {'url': url, 'status': 'failed', 'error_code': getattr(exc, 'code', 'invalid_response'),
                    'error': str(exc), 'next': 'Use host search/browser; do not report no results or retry in a loop.'}
    with ThreadPoolExecutor(max_workers=min(3, len(unique))) as pool:
        records = list(pool.map(task, unique.values()))
    candidates, screenshots = [], []
    for record in records:
        if record['status'] != 'readable_material':
            continue
        tweet = record['tweet']
        candidates.append({'id': f"X-{record['tweet_id']}", 'title': f"@{tweet['screen_name']}: {tweet.get('text', '')[:90]}",
                           'url': record['url'], 'published_at': record['published_at'],
                           'retrieved_at': record['fetched_at'], 'kind': 'lead', 'verified': False,
                           'independence_group': tweet['screen_name'].lower(), 'summary': '',
                           'verification_note': 'Host must read this material, classify its origin and verify relevant claims.',
                           'read_record': record['read_record'], 'transport': record['transport']})
        screenshots.append({'source_url': record['url'], 'tweet_id': record['tweet_id'],
                            'capture_state': 'not_captured', 'capture_backend': 'host_browser',
                            'focus_text': tweet.get('text', '')[:500], 'media_candidates': tweet.get('media', {}),
                            'purpose': 'Choose the useful case, result or operation before capturing a real viewport.'})
    save(run / 'readings/x/source-candidates.json', candidates)
    save(run / 'readings/x/screenshot-candidates.json', screenshots)
    result = {'status': 'ok' if len(candidates) == len(records) else 'partial' if candidates else 'failed',
              'records': records, 'scope': 'Public text and media URLs only; no screenshot or factual verification implied.'}
    save(run / 'readings/x/fetch-results.json', result)
    return result


def nitter_settings(workspace=None):
    path = Path(workspace or Path.cwd()).resolve() / '.wechat-tools/x-nitter.json'
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('instances'), list):
            raise ValueError('invalid schema')
        if not all(isinstance(item, str) for item in data['instances']):
            raise ValueError('invalid instances')
        return data
    except (ValueError, OSError):
        raise ValueError('Invalid local Nitter configuration; use nitter_setup.py configure to repair it') from None


def nitter_config(value=None, workspace=None):
    raw = value or os.environ.get('XTF_NITTER') or os.environ.get('NITTER_URL')
    if not raw:
        raw = ','.join(nitter_settings(workspace).get('instances', []))
    if not raw:
        return []
    instances = []
    for candidate in raw.split(','):
        candidate = candidate.strip().rstrip('/')
        if not candidate:
            continue
        if '://' not in candidate:
            candidate = 'https://' + candidate
        parsed = urlsplit(candidate)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Nitter base URL must not contain credentials, query parameters or fragments')
        instances.append(candidate)
    if len(instances) > 2:
        raise ValueError('Use at most two Nitter instances for a bounded query')
    return instances


def nitter_query(command, run, query=None, user=None, url=None, nitter=None, limit=10, workspace=None):
    start = time.perf_counter()
    instances = nitter_config(nitter, workspace)
    if not instances:
        return {'status': 'unconfigured', 'error_code': 'backend_unavailable', 'seconds': round(time.perf_counter()-start, 4),
                'next': 'Use host web/X browser search to locate tweet URLs, then fetch; do not probe default localhost or claim no results.'}
    flags = ['--backend', 'nitter', '--nitter', ','.join(instances), '--limit', str(min(20, max(1, limit)))]
    if command == 'search':
        if not query:
            raise ValueError('--query required')
        flags += ['--search', query]
    elif command == 'timeline':
        if not user or not re.fullmatch(r'[A-Za-z0-9_]{1,15}', user.lstrip('@')):
            raise ValueError('Valid --user required')
        # The upstream timeline maps to search anyway; avoid automatic per-tweet view supplementation.
        flags += ['--search', 'from:' + user.lstrip('@')]
    else:
        canonical, _, _ = tweet_url(url or '')
        flags += ['--url', canonical, '--replies']
    try:
        process = subprocess.run([sys.executable, str(VENDOR / 'scripts/fetch_tweet.py'), *flags],
                                 capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=25,
                                 env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        payload = json.loads(process.stdout)
        items = payload.get('replies' if command == 'replies' else 'tweets', [])
        state = 'failed' if payload.get('error') or process.returncode else 'leads' if items else 'empty_unverified'
        result = {'status': state,
                  'backend': 'x-tweet-fetcher/nitter', 'method': 'public_http', 'command': command,
                  'observed_at': now(), 'seconds': round(time.perf_counter()-start, 4), 'result': payload,
                  'scope': 'Proxy leads only. Fetch selected tweet URLs for original dates and complete material before verification.'}
        if state == 'empty_unverified':
            result['next'] = 'No tweet content returned. Verify the original page or use host search; a challenge/error page may look like an empty list.'
    except subprocess.TimeoutExpired:
        result = {'status': 'failed', 'error_code': 'timeout', 'next': '25-second bound reached; use host search/browser.'}
    except json.JSONDecodeError:
        result = {'status': 'failed', 'error_code': 'invalid_response', 'next': 'Upstream returned no structured result; use host search/browser.'}
    key = hashlib.sha256(json.dumps([command, query, user, url], ensure_ascii=False).encode()).hexdigest()[:12]
    save(Path(run) / 'readings/x' / f'nitter-{command}-{key}.json', result)
    return result


def doctor(workspace=None):
    provenance = json.loads((VENDOR / 'provenance.json').read_text(encoding='utf-8'))
    instances = nitter_config(workspace=workspace)
    local = nitter_settings(workspace) if not (os.environ.get('XTF_NITTER') or os.environ.get('NITTER_URL')) else {}
    return {'installed': True, 'version': provenance['version'], 'commit': provenance['commit'],
            'single_tweet': 'available_not_probed', 'configured_nitter_instances': len(instances),
            'search_timeline_replies': 'configured_not_probed' if instances else 'unconfigured',
            'last_local_validation': local.get('validation'),
            'screenshot': 'host_browser_required', 'article': 'embedded_article_when_returned; standalone_article_host_browser',
            'note': 'Installation and configuration do not prove current connectivity.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['doctor', 'fetch', 'search', 'timeline', 'replies'])
    parser.add_argument('--run', type=Path)
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--url', action='append', default=[])
    parser.add_argument('--query'); parser.add_argument('--user'); parser.add_argument('--nitter')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--max-age', type=int, default=1800)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'doctor':
            result = doctor(args.workspace)
        else:
            if not args.run:
                raise ValueError('--run required')
            if args.max_age < 0:
                raise ValueError('--max-age must be nonnegative')
            if args.command == 'fetch':
                cache = args.workspace.resolve() / '.wechat-tools/x-cache' if args.workspace else args.run / 'readings/x/cache'
                result = collect(args.url, args.run, cache, args.max_age, args.refresh)
            else:
                if args.command == 'replies' and len(args.url) != 1:
                    raise ValueError('replies requires exactly one --url')
                result = nitter_query(args.command, args.run, args.query, args.user, args.url[0] if args.url else None, args.nitter, args.limit, args.workspace)
    except (ValueError, OSError) as exc:
        result = {'status': 'failed', 'error_code': 'invalid_input', 'error': str(exc)}
    if args.command == 'fetch' and 'records' in result:
        compact = {**result, 'records': [{k: v for k, v in item.items() if k != 'tweet'} for item in result['records']]}
        print(json.dumps(compact, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get('status') in ('failed', 'partial', 'unconfigured', 'empty_unverified') else 0


if __name__ == '__main__':
    raise SystemExit(main())
