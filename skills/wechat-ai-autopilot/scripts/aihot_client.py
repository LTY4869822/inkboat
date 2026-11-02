"""Anonymous official AIhot transport; execution permissions belong to the host."""
import datetime as dt
import email.utils
import errno
import hashlib
import json
import os
from pathlib import Path
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request


class AIhotError(RuntimeError):
    def __init__(self, detail):
        self.detail = detail
        super().__init__(f"AIhot {detail['code']}: {detail['message']}")


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def transport_detail(exc):
    reason = getattr(exc, 'reason', exc)
    number = getattr(reason, 'winerror', None) or getattr(reason, 'errno', None)
    if isinstance(reason, OSError) and getattr(reason, 'filename', None):
        return {'code': 'local_filesystem_error', 'message': type(reason).__name__, 'errno': number,
                'http_status': None, 'retryable': False, 'action': 'check-workspace-access'}
    if isinstance(reason, ConnectionRefusedError) or number in (errno.ECONNREFUSED, 10061):
        code, retry = 'transport_connection_refused', False
    elif isinstance(reason, socket.gaierror):
        code, retry = 'transport_dns_failure', False
    elif isinstance(reason, ssl.SSLError):
        code, retry = 'transport_tls_failure', False
    elif isinstance(reason, (TimeoutError, socket.timeout)):
        code, retry = 'transport_timeout', True
    else:
        code, retry = 'transport_unavailable', True
    # Never expose exception URLs, proxy credentials, or arbitrary response bodies.
    return {'code': code, 'message': type(reason).__name__, 'errno': number,
            'http_status': None, 'retryable': retry,
            'action': 'check-host-approved-network' if not retry else 'bounded-retry-or-host-search'}


def retry_seconds(value):
    if str(value).isdigit():
        return int(value)
    try:
        moment = email.utils.parsedate_to_datetime(value)
        return max(0, int((moment - dt.datetime.now(dt.timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError, OverflowError):
        return 60


def fetch_json(url, cache_dir, opener=None, sleeper=time.sleep, trace=None):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'aihot.virxact.com' or not parts.path.startswith('/api/v1/'):
        raise ValueError('AIhot fetch requires anonymous official v1 endpoint')
    opener = opener or urllib.request.urlopen
    trace = trace if trace is not None else {}
    trace.update(url=url, checked_at=stamp(), attempts=0, cache_hit=False)
    cache_path = Path(cache_dir) / (hashlib.sha256(url.encode()).hexdigest() + '.json')
    cache = json.loads(cache_path.read_text(encoding='utf-8-sig')) if cache_path.is_file() else {}
    headers = {'User-Agent': 'wechat-ai-autopilot/2.0 (+https://aihot.virxact.com/aihot-skill/)',
               'Accept': 'application/json'}
    if cache.get('url') == url and cache.get('etag'):
        headers['If-None-Match'] = cache['etag']
    for attempt in range(3):
        trace['attempts'] = attempt + 1
        try:
            with opener(urllib.request.Request(url, headers=headers), timeout=12) as response:
                raw = response.read(4_000_001)
                if len(raw) > 4_000_000:
                    raise ValueError('AIhot response exceeded 4 MB')
                value = json.loads(raw)
                if not isinstance(value, dict) or not isinstance(value.get('items'), list):
                    raise ValueError('AIhot response is not a v1 items object')
                trace.update(http_status=getattr(response, 'status', 200), etag=response.headers.get('ETag'))
                write(cache_path, {'url': url, 'etag': response.headers.get('ETag'), 'body': value, 'fetched_at': stamp()})
                return value
        except urllib.error.HTTPError as exc:
            if exc.code == 304 and cache.get('url') == url and 'body' in cache:
                trace.update(http_status=304, cache_hit=True, cached_at=cache.get('fetched_at'))
                return cache['body']
            problem = {}
            try:
                problem = json.loads(exc.read(8192))
            except (ValueError, OSError):
                pass
            if not isinstance(problem, dict):
                problem = {}
            seconds = retry_seconds((exc.headers or {}).get('Retry-After', '60'))
            retryable = exc.code in (429, 500, 502, 503, 504, 566, 567)
            detail = {'code': 'http_rate_limited' if exc.code == 429 else 'http_error',
                      'http_status': exc.code, 'message': f'HTTP {exc.code}', 'retryable': retryable,
                      'attempts': attempt + 1, 'url': url, 'requestId': problem.get('requestId'),
                      'help': problem.get('help'), 'retry_after_seconds': seconds if exc.code == 429 else None,
                      'action': 'wait-retry-after' if exc.code == 429 else 'bounded-retry-or-host-search'}
            exhausted = attempt >= (1 if exc.code in (566, 567) else 2)
            if not retryable or exhausted or (exc.code == 429 and seconds >= 60):
                trace['error'] = detail
                raise AIhotError(detail) from None
            sleeper(seconds if exc.code == 429 else 2 ** attempt)
        except (urllib.error.URLError, OSError) as exc:
            detail = {**transport_detail(exc), 'attempts': attempt + 1, 'url': url}
            if not detail['retryable'] or attempt >= 2:
                trace['error'] = detail
                raise AIhotError(detail) from None
            sleeper(2 ** attempt)
