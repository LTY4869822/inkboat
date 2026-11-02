"""Validate Nitter search/timeline and persist workspace-only endpoint settings."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode

import x_fetch as x
from xtf.backends.nitter import _HEADERS
from xtf.parsers.nitter_html import _parse_html, _extract_tweets_from_events


def inspect_html(html):
    # A reachable homepage or HTTP 200 robot challenge is not usable tweet search.
    if any(marker in html.lower() for marker in ('anubis_challenge', 'cf-chl-', 'verify you are human', 'checking your browser')):
        return {'status': 'blocked', 'error_code': 'browser_challenge', 'count': 0}
    tweets = _extract_tweets_from_events(_parse_html(html).events)
    useful = [item for item in tweets if re.fullmatch(r'\d+', item.get('tweet_id', ''))
              and item.get('username') and item.get('text', '').strip()]
    if not useful:
        return {'status': 'failed', 'error_code': 'no_readable_tweets', 'count': 0}
    return {'status': 'passed', 'count': len(useful),
            'sample_urls': [f"https://x.com/{item['username']}/status/{item['tweet_id']}" for item in useful[:2]]}


def probe(instance, query, purpose):
    start = time.perf_counter()
    url = instance + '/search?' + urlencode({'q': query, 'f': 'tweets'})
    try:
        html = x.http.get_text(url, headers=_HEADERS, timeout=8, retries=0)
        result = inspect_html(html)
    except x.XtfError as error:
        result = {'status': 'failed', 'error_code': error.code, 'count': 0}
    except OSError:
        result = {'status': 'failed', 'error_code': 'network_error', 'count': 0}
    return {**result, 'instance': instance, 'query': query, 'purpose': purpose,
            'observed_at': x.now(), 'seconds': round(time.perf_counter() - start, 3)}


def configure(workspace, endpoints, query='AI', user='OpenAI'):
    if not query.strip() or not re.fullmatch(r'[A-Za-z0-9_]{1,15}', user.lstrip('@')):
        raise ValueError('A search query and valid timeline username are required')
    instances = x.nitter_config(endpoints, workspace)
    if not instances:
        raise ValueError('Specify --nitter with a real instance address')
    jobs = [(instance, query, 'search') for instance in instances]
    jobs += [(instance, 'from:' + user.lstrip('@'), 'timeline') for instance in instances]
    with ThreadPoolExecutor(max_workers=2) as pool:
        checks = list(pool.map(lambda task: probe(*task), jobs))
    usable = [instance for instance in instances if all(check['status'] == 'passed'
              for check in checks if check['instance'] == instance)]
    result = {'status': 'configured' if usable else 'failed', 'observed_at': x.now(), 'checks': checks,
              'instances_enabled': usable, 'scope': 'Validation checks search and timeline for readable tweet material; replies and screenshots were not tested.'}
    folder = Path(workspace).resolve() / '.wechat-tools'
    x.save(folder / 'x-nitter-last-check.json', result)
    if usable:
        settings = {'schema': 1, 'instances': usable, 'validation': {'observed_at': result['observed_at'],
                    'search': 'passed', 'timeline': 'passed', 'replies': 'not_tested', 'checks': checks}}
        target = folder / 'x-nitter.json'
        temporary = target.with_suffix('.tmp')
        x.save(temporary, settings)
        temporary.replace(target)
        result['config_path'] = str(target)
    else:
        result['next'] = 'No endpoint was enabled. Existing active settings were preserved. Supply a working instance or complete self-host prerequisites.'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--nitter', required=True)
    parser.add_argument('--query', default='AI')
    parser.add_argument('--user', default='OpenAI')
    args = parser.parse_args()
    try:
        result = configure(args.workspace, args.nitter, args.query, args.user)
    except (ValueError, OSError) as error:
        result = {'status': 'failed', 'error_code': 'invalid_configuration', 'error': str(error)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'configured' else 1


if __name__ == '__main__':
    raise SystemExit(main())
