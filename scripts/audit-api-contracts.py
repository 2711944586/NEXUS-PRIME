from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_APP = ROOT / 'frontend' / 'src' / 'app'
BACKEND_DIR = ROOT / 'backend'

API_CALL_RE = re.compile(
    r'\b(?:this\.)?api\.(?P<method>get|postForm|post|put|patch|delete)'
    r'(?:<[^`\'"]+>)?\s*\(\s*(?P<quote>[`\'"])(?P<path>.*?)(?P=quote)',
    re.DOTALL,
)
API_URL_RE = re.compile(
    r'\bapiUrl\s*\(\s*(?P<quote>[`\'"])(?P<path>.*?)(?P=quote)',
    re.DOTALL,
)
ENDPOINT_PROPERTY_RE = re.compile(
    r'endpoint\s*:\s*(?P<quote>[`\'"])(?P<path>.*?)(?P=quote)(?P<tail>[^\n}]*)',
    re.DOTALL,
)
STRING_LITERAL_RE = re.compile(r'(?P<quote>[`\'"])(?P<path>[^`\'"]*?/[^`\'"]*?)(?P=quote)')
TEMPLATE_EXPR_RE = re.compile(r'\$\{[^}]+\}')
COLON_PARAM_RE = re.compile(r'(?<=/):[A-Za-z_][A-Za-z0-9_]*(?=/|$)|^:[A-Za-z_][A-Za-z0-9_]*(?=/|$)')
BACKEND_PARAM_RE = re.compile(r'^<(?:(?P<converter>[A-Za-z_][A-Za-z0-9_]*):)?[^>]+>$')


@dataclass(frozen=True)
class EndpointUse:
    method: str | None
    path: str
    raw: str
    file: Path
    line: int
    source: str

    @property
    def rel(self) -> str:
        return self.file.relative_to(ROOT).as_posix()

    @property
    def label(self) -> str:
        method = self.method or 'ANY'
        return f'{method} {self.path}'


@dataclass(frozen=True)
class BackendPattern:
    methods: frozenset[str]
    raw: str
    parts: tuple[str, ...]


@dataclass
class BackendContract:
    exact_patterns: list[BackendPattern]
    resource_names: set[str]
    resource_aliases: dict[str, str]
    new_resource_routes: dict[str, str]
    api_first_segments: set[str]


def line_number(source: str, offset: int) -> int:
    return source.count('\n', 0, offset) + 1


def normalize_method(method: str | None) -> str | None:
    if not method:
        return None
    value = method.upper()
    if value == 'POSTFORM':
        return 'POST'
    return value


def normalize_frontend_path(raw: str, first_segments: set[str]) -> str | None:
    value = raw.strip()
    if not value or value.startswith(('http://', 'https://', 'data:', 'mailto:', '#')):
        return None
    if any(token in value for token in (' ', '\n', '\r', '<', '>')):
        return None
    value = value.split('?', 1)[0].split('#', 1)[0]
    if value.startswith('/api/v1/'):
        value = value[len('/api/v1/'):]
    elif value.startswith('api/v1/'):
        value = value[len('api/v1/'):]
    elif value.startswith('/'):
        value = value[1:]
    value = TEMPLATE_EXPR_RE.sub('{param}', value)
    value = COLON_PARAM_RE.sub('{param}', value)
    value = value.strip('/')
    if not value or value.startswith(('/app/', 'app/', 'images/', 'assets/')):
        return None
    first = value.split('/', 1)[0]
    if first not in first_segments:
        return None
    return value


def iter_frontend_files() -> Iterable[Path]:
    for path in FRONTEND_APP.rglob('*.ts'):
        if path.name.endswith('.spec.ts'):
            continue
        yield path


def collect_frontend_uses(contract: BackendContract) -> list[EndpointUse]:
    uses: list[EndpointUse] = []
    seen: set[tuple[str | None, str, str, int, str]] = set()

    def add(file: Path, source: str, start: int, method: str | None, raw: str, origin: str) -> None:
        path = normalize_frontend_path(raw, contract.api_first_segments)
        if not path:
            return
        normalized_method = normalize_method(method)
        key = (normalized_method, path, file.as_posix(), line_number(source, start), origin)
        if key in seen:
            return
        seen.add(key)
        uses.append(EndpointUse(normalized_method, path, raw, file, line_number(source, start), origin))

    for file in iter_frontend_files():
        source = file.read_text(encoding='utf-8')
        for match in API_CALL_RE.finditer(source):
            add(file, source, match.start(), match.group('method'), match.group('path'), 'ApiService call')
        for match in API_URL_RE.finditer(source):
            add(file, source, match.start(), 'GET', match.group('path'), 'apiUrl call')
        for match in ENDPOINT_PROPERTY_RE.finditer(source):
            tail = match.group('tail') or ''
            method_match = re.search(r"method\s*:\s*['\"](?P<method>GET|POST|PUT|PATCH|DELETE)['\"]", tail)
            add(file, source, match.start(), method_match.group('method') if method_match else None, match.group('path'), 'BusinessAction endpoint')

        for line_index, line in enumerate(source.splitlines(), start=1):
            if 'endpoint' not in line:
                continue
            for literal in STRING_LITERAL_RE.finditer(line):
                add(file, source, source.find(line) + literal.start(), None, literal.group('path'), 'endpoint expression')

    return sorted(uses, key=lambda item: (item.path, item.method or '', item.rel, item.line))


def backend_part(part: str) -> str:
    match = BACKEND_PARAM_RE.match(part)
    if not match:
        return part
    return '**' if match.group('converter') == 'path' else '*'


def backend_pattern(rule: str, methods: Iterable[str]) -> BackendPattern:
    path = rule.removeprefix('/api/v1').strip('/')
    parts = tuple(backend_part(part) for part in path.split('/') if part)
    return BackendPattern(frozenset(methods), path, parts)


def load_backend_contract() -> BackendContract:
    sys.path.insert(0, str(BACKEND_DIR.resolve()))
    os.environ.setdefault('FLASK_CONFIG', 'testing')
    from app import create_app  # type: ignore
    from app.api.experience import NEW_RESOURCE_ROUTES  # type: ignore
    from app.api.routes import RESOURCE_ALIASES, RESOURCE_CONFIG  # type: ignore

    app = create_app('testing')
    exact_patterns: list[BackendPattern] = []
    all_first_segments: set[str] = set()
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith('/api/v1'):
            continue
        route_path = rule.rule.removeprefix('/api/v1').strip('/')
        if route_path:
            all_first_segments.add(route_path.split('/', 1)[0])
        if route_path.startswith('<resource>') or route_path.startswith('<path:new_path>'):
            continue
        methods = sorted((rule.methods or set()) - {'HEAD', 'OPTIONS'})
        exact_patterns.append(backend_pattern(rule.rule, methods))

    resource_names = set(RESOURCE_CONFIG)
    resource_aliases = dict(RESOURCE_ALIASES)
    new_resource_routes = dict(NEW_RESOURCE_ROUTES)
    for item in resource_names | set(resource_aliases) | set(new_resource_routes):
        all_first_segments.add(item.split('/', 1)[0])
    return BackendContract(
        exact_patterns=sorted(exact_patterns, key=lambda pattern: pattern.raw),
        resource_names=resource_names,
        resource_aliases=resource_aliases,
        new_resource_routes=new_resource_routes,
        api_first_segments=all_first_segments,
    )


def method_allowed(method: str | None, allowed: Iterable[str]) -> bool:
    return method is None or method in set(allowed)


def parts_match(frontend_parts: list[str], backend_parts: tuple[str, ...]) -> bool:
    i = 0
    j = 0
    while i < len(frontend_parts) and j < len(backend_parts):
        backend = backend_parts[j]
        frontend = frontend_parts[i]
        if backend == '**':
            return True
        if backend == '*' or frontend == '{param}' or backend == frontend:
            i += 1
            j += 1
            continue
        return False
    return i == len(frontend_parts) and j == len(backend_parts)


def matches_exact_route(use: EndpointUse, contract: BackendContract) -> str | None:
    frontend_parts = use.path.split('/')
    for pattern in contract.exact_patterns:
        if method_allowed(use.method, pattern.methods) and parts_match(frontend_parts, pattern.parts):
            return pattern.raw
    return None


def matches_resource_route(use: EndpointUse, contract: BackendContract) -> str | None:
    parts = use.path.split('/')
    resource = parts[0] if parts else ''
    canonical = contract.resource_aliases.get(resource, resource)
    if canonical not in contract.resource_names:
        return None
    if len(parts) == 1 and method_allowed(use.method, {'GET', 'POST'}):
        return f'<resource:{canonical}>'
    if len(parts) == 2 and parts[1] == '{param}' and method_allowed(use.method, {'GET', 'PUT', 'PATCH', 'DELETE'}):
        return f'<resource:{canonical}>/{{id}}'
    return None


def matches_new_resource_route(use: EndpointUse, contract: BackendContract) -> str | None:
    parts = use.path.split('/')
    for frontend_path, resource in contract.new_resource_routes.items():
        alias_parts = frontend_path.split('/')
        if parts == alias_parts and method_allowed(use.method, {'GET', 'POST'}):
            return f'<path:{frontend_path}->{resource}>'
        if len(parts) == len(alias_parts) + 1 and parts[:-1] == alias_parts and parts[-1] == '{param}' and method_allowed(use.method, {'GET', 'PUT', 'PATCH', 'DELETE'}):
            return f'<path:{frontend_path}/{{id}}->{resource}>'
    return None


def match_backend(use: EndpointUse, contract: BackendContract) -> str | None:
    return (
        matches_exact_route(use, contract)
        or matches_new_resource_route(use, contract)
        or matches_resource_route(use, contract)
    )


def audit() -> dict[str, object]:
    contract = load_backend_contract()
    uses = collect_frontend_uses(contract)
    missing: list[dict[str, object]] = []
    matched: list[dict[str, object]] = []
    for use in uses:
        route = match_backend(use, contract)
        row = {
            'method': use.method or 'ANY',
            'path': use.path,
            'raw': use.raw,
            'file': use.rel,
            'line': use.line,
            'source': use.source,
        }
        if route:
            matched.append({**row, 'backend': route})
        else:
            missing.append(row)
    return {
        'summary': {
            'frontend_uses': len(uses),
            'matched': len(matched),
            'missing': len(missing),
            'backend_exact_routes': len(contract.exact_patterns),
            'backend_resources': len(contract.resource_names),
            'backend_path_aliases': len(contract.new_resource_routes),
        },
        'missing': missing,
        'matched': matched,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit frontend API calls against Flask runtime routes and resource contracts.')
    parser.add_argument('--json-output', type=Path, help='Optional JSON report path.')
    args = parser.parse_args()

    report = audit()
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    summary = report['summary']
    print(
        'API contract audit: '
        f"{summary['matched']}/{summary['frontend_uses']} frontend endpoint uses matched "
        f"against {summary['backend_exact_routes']} runtime routes and {summary['backend_resources']} resources."
    )
    missing = report['missing']
    if missing:
        print('')
        print('API contract audit failed:')
        for item in missing[:20]:
            print(f"- {item['file']}:{item['line']} {item['method']} {item['path']} has no backend contract")
        if len(missing) > 20:
            print(f'- ... {len(missing) - 20} more missing endpoints')
        return 1
    print('API contract audit passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
