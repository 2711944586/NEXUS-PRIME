import os
from pathlib import Path

from flask import current_app

from app.services.health_service import service_health
from app.services.service_catalog import integration_payload
from app.utils.cloud_storage import is_cloud_storage_enabled
from app.utils.time import utcnow


ROOT = Path(__file__).resolve().parents[3]


def deployment_readiness_payload():
    health = service_health(include_database=True)
    integrations = integration_payload()
    env = os.environ
    checks = [
        env_check(
            'frontend-api-url',
            '前端 API 地址',
            env.get('NEXUS_API_BASE_URL') or env.get('VITE_NEXUS_API_BASE_URL'),
            'frontend',
            'Vercel 前端项目必须只保存公开 /api/v1 地址。',
            'vercel env add NEXUS_API_BASE_URL production',
        ),
        env_check(
            'database-url',
            'Supabase 数据库连接',
            env.get('DATABASE_URL'),
            'backend',
            '后端项目必须使用 Supabase Pooler PostgreSQL URL。',
            'vercel env add DATABASE_URL production --sensitive',
        ),
        env_check(
            'secret-key',
            '后端 SECRET_KEY',
            env.get('SECRET_KEY'),
            'backend',
            '生产环境必须使用 32 位以上随机密钥。',
            'vercel env add SECRET_KEY production --sensitive',
            min_length=32,
        ),
        {
            'key': 'database-probe',
            'label': '数据库探针',
            'scope': 'backend',
            'status': 'ready' if health['database']['status'] == 'ready' else 'blocked',
            'evidence': f"{health['database']['engine']} / {health['database'].get('latency_ms', 0)}ms",
            'action': '确认 Supabase 连接串、SSL 和迁移状态。',
        },
        {
            'key': 'storage-mode',
            'label': '文件存储模式',
            'scope': 'backend',
            'status': storage_status(health),
            'evidence': storage_evidence(health),
            'action': '生产环境建议配置 CLOUDINARY_URL 或确认持久化卷。',
        },
        {
            'key': 'ai-provider',
            'label': 'AI 分析服务',
            'scope': 'backend',
            'status': 'ready' if health['ai']['external_configured'] or health['ai']['local_enabled'] else 'attention',
            'evidence': f"{health['ai']['provider']} / {health['ai']['model']} / {health['ai']['status']}",
            'action': '如需外部智能分析，在后端写入 DEEPSEEK_API_KEY 或 OPENAI_API_KEY。',
        },
        {
            'key': 'shared-cache',
            'label': '共享缓存与限流',
            'scope': 'backend',
            'status': 'ready' if current_app.config.get('CACHE_REDIS_URL') else 'attention',
            'evidence': current_app.config.get('CACHE_TYPE') or 'SimpleCache',
            'action': '生产多实例建议接入 Redis/Upstash，避免登录限流只在单实例生效。',
        },
        {
            'key': 'cors-origin',
            'label': '跨域与 Cookie 策略',
            'scope': 'backend',
            'status': cors_status(),
            'evidence': cors_evidence(),
            'action': '上线前将 CORS_ORIGINS、AUTH_COOKIE_SECURE、AUTH_COOKIE_SAMESITE 调整为生产域名。',
        },
        {
            'key': 'microservice-catalog',
            'label': '微服务目录与契约',
            'scope': 'platform',
            'status': 'ready' if integrations['summary']['avg_contract_coverage'] >= 90 else 'attention',
            'evidence': f"{len(integrations['items'])} 服务 / {integrations['summary']['contracts']} 契约 / {integrations['summary']['dependencies']} 依赖",
            'action': '按服务目录拆分 identity、inventory、procurement、finance、reporting 等域。',
        },
        file_check(
            'vercel-config',
            'Vercel 配置文件',
            ['frontend/vercel.json', 'backend/vercel.json'],
            'platform',
            '确认前后端项目都具备独立 Vercel 配置。',
        ),
        file_check(
            'runtime-config',
            '前端运行时配置',
            ['frontend/public/runtime-config.js', 'frontend/scripts/write-runtime-config.mjs'],
            'frontend',
            '确认 runtime-config.js 由构建脚本生成，部署时可注入后端 API 地址。',
        ),
        file_check(
            'deployment-scripts',
            '部署脚本与预检',
            ['scripts/preflight.ps1', 'scripts/deploy-supabase-vercel.ps1', 'scripts/quality-gate.ps1'],
            'platform',
            '上线前先跑质量闸门，再执行 Supabase/Vercel 部署脚本。',
        ),
    ]
    ready = sum(1 for item in checks if item['status'] == 'ready')
    attention = sum(1 for item in checks if item['status'] == 'attention')
    blocked = sum(1 for item in checks if item['status'] == 'blocked')
    score = round((ready * 100 + attention * 64) / max(len(checks), 1))
    if blocked:
        level = 'blocked'
        next_action = '先处理阻塞项，再执行远程部署。'
    elif attention:
        level = 'attention'
        next_action = '补齐关注项后可以进入预生产部署。'
    else:
        level = 'ready'
        next_action = '可以执行质量闸门和 Vercel/Supabase 部署。'

    return {
        'generated_at': utcnow().isoformat(),
        'source': 'deployment-readiness',
        'summary': {
            'score': score,
            'level': level,
            'ready': ready,
            'attention': attention,
            'blocked': blocked,
            'total': len(checks),
            'next_action': next_action,
            'frontend_boundary': 'NEXUS_API_BASE_URL only',
            'backend_boundary': 'DATABASE_URL / SECRET_KEY / AI / storage secrets',
        },
        'checks': checks,
        'service_snapshot': {
            'services': len(integrations['items']),
            'domains': integrations['domains'],
            'avg_readiness': integrations['summary']['avg_readiness'],
            'avg_contract_coverage': integrations['summary']['avg_contract_coverage'],
            'avg_split_score': integrations['summary'].get('avg_split_score', 0),
            'deployment_units': integrations['topology']['deployment_units'],
            'stores': integrations['topology']['stores'],
            'dependencies': integrations['summary']['dependencies'],
            'api_surfaces': integrations['summary']['api_surfaces'],
            'split_plan': integrations.get('split_plan', []),
            'observability': integrations.get('observability', {}),
            'incident_queue': integrations.get('incident_queue', [])[:6],
        },
        'maturity': erp_maturity_payload(checks, integrations, health),
        'runbook': [
            {'step': '质量闸门', 'command': 'powershell -ExecutionPolicy Bypass -File scripts\\quality-gate.ps1'},
            {'step': '生成后端密钥', 'command': '[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))'},
            {'step': '写入后端数据库', 'command': 'vercel env add DATABASE_URL production --sensitive'},
            {'step': '写入前端 API', 'command': 'vercel env add NEXUS_API_BASE_URL production'},
            {'step': '部署前后端', 'command': '.\\scripts\\deploy-supabase-vercel.ps1 -SyncDatabase'},
        ],
    }


def erp_maturity_payload(checks, integrations, health):
    evidence = maturity_evidence()
    dimensions = [
        maturity_dimension(
            'front-back',
            '前后端分离',
            score=score_front_back_boundary(checks),
            evidence='Angular SPA、Flask REST API、运行时 API 地址和 Cookie/CSRF 边界已拆开。',
            action='继续保持前端只读取 NEXUS_API_BASE_URL，后端集中保管数据库、AI、存储和 Cookie 密钥。',
            weight=18,
        ),
        maturity_dimension(
            'business-closure',
            '业务闭环完整度',
            score=score_business_closure(integrations),
            evidence=f"{len(integrations['items'])} 个服务覆盖 {integrations['summary']['api_surfaces']} 个 API 面和 {integrations['summary']['contracts']} 个业务契约。",
            action='把库存、采购、履约、财务、报表、通知和审计动作继续沉淀为任务队列。',
            weight=20,
        ),
        maturity_dimension(
            'microservices',
            '微服务拆分就绪',
            score=score_microservice_topology(integrations),
            evidence=f"{integrations['summary']['dependencies']} 条依赖、{integrations['summary']['avg_contract_coverage']}% 契约覆盖、{integrations['topology']['edge_count']} 条拓扑边。",
            action='按 identity、inventory、procurement、fulfillment、finance、reporting、files、ai、notifications、audit 分阶段拆分。',
            weight=17,
        ),
        maturity_dimension(
            'deployment',
            '部署与运行就绪',
            score=score_deployment_checks(checks, health),
            evidence=f"{sum(1 for item in checks if item['status'] == 'ready')} ready / {len(checks)} checks，健康探针状态 {health['status']}。",
            action='在目标环境补齐 DATABASE_URL、SECRET_KEY、Cloudinary、Redis、CORS 与前端 API 地址。',
            weight=17,
        ),
        maturity_dimension(
            'security',
            '安全与审计治理',
            score=score_security_controls(checks, integrations),
            evidence='HttpOnly Cookie、CSRF、RBAC、审计日志、上传类型校验和用户隔离已纳入运行检查。',
            action='生产环境启用 Secure Cookie、SameSite=None、固定 CORS 域名和共享限流缓存。',
            weight=14,
        ),
        maturity_dimension(
            'delivery-assets',
            '交付资产与真实度',
            score=score_delivery_assets(evidence),
            evidence=f"{sum(1 for item in evidence if item['status'] == 'ready')} / {len(evidence)} 项交付资产可追溯。",
            action='每次最终交付后重新运行截图、DOCX、API 契约和资产审计。',
            weight=14,
        ),
    ]
    total_weight = sum(item['weight'] for item in dimensions)
    score = round(sum(item['score'] * item['weight'] for item in dimensions) / max(total_weight, 1))
    attention = sum(1 for item in dimensions if item['level'] == 'attention')
    blocked = sum(1 for item in dimensions if item['level'] == 'blocked')
    level = 'blocked' if blocked else 'attention' if attention else 'ready'
    next_dimension = next((item for item in dimensions if item['level'] != 'ready'), dimensions[0])
    return {
        'summary': {
            'score': score,
            'level': level,
            'target': '行业头部级制造开发管理 ERP',
            'dimensions': len(dimensions),
            'ready': sum(1 for item in dimensions if item['level'] == 'ready'),
            'attention': attention,
            'blocked': blocked,
            'next_action': next_dimension['action'],
        },
        'dimensions': dimensions,
        'capability_map': maturity_capability_map(integrations),
        'topology_nodes': maturity_topology_nodes(integrations),
        'topology_edges': integrations.get('dependencies', []),
        'evidence': evidence,
    }


def maturity_dimension(key, label, score, evidence, action, weight):
    normalized = max(0, min(100, int(round(score or 0))))
    if normalized >= 86:
        level = 'ready'
    elif normalized >= 68:
        level = 'attention'
    else:
        level = 'blocked'
    return {
        'key': key,
        'label': label,
        'score': normalized,
        'level': level,
        'evidence': evidence,
        'action': action,
        'weight': weight,
    }


def score_front_back_boundary(checks):
    required_keys = {'frontend-api-url', 'vercel-config', 'runtime-config'}
    ready = sum(1 for item in checks if item['key'] in required_keys and item['status'] == 'ready')
    api_files = [
        ROOT / 'backend/app/api/routes.py',
        ROOT / 'backend/app/api/experience.py',
        ROOT / 'frontend/src/app/core/api.service.ts',
        ROOT / 'frontend/src/app/core/auth.interceptor.ts',
    ]
    file_score = sum(1 for path in api_files if path.exists()) / len(api_files) * 52
    return file_score + ready / len(required_keys) * 48


def score_business_closure(integrations):
    summary = integrations['summary']
    service_score = min(len(integrations['items']) / 10 * 32, 32)
    api_score = min(summary['api_surfaces'] / 30 * 22, 22)
    contract_score = min(summary['contracts'] / 20 * 20, 20)
    runbook_score = min(summary['runbook_steps'] / 24 * 14, 14)
    record_score = 12 if summary['records'] > 0 else 0
    return service_score + api_score + contract_score + runbook_score + record_score


def score_microservice_topology(integrations):
    summary = integrations['summary']
    topology = integrations['topology']
    return (
        min(len(topology['deployment_units']) / 8 * 22, 22)
        + min(summary['dependencies'] / 16 * 22, 22)
        + min(summary['avg_contract_coverage'], 100) * .34
        + min(summary['avg_readiness'], 100) * .22
    )


def score_deployment_checks(checks, health):
    status_score = sum({'ready': 100, 'attention': 70, 'blocked': 25}.get(item['status'], 55) for item in checks) / max(len(checks), 1)
    probe_bonus = 8 if health['database']['status'] == 'ready' else 0
    storage_penalty = 8 if health['storage']['status'] == 'missing_cloud' else 0
    return min(100, status_score + probe_bonus - storage_penalty)


def score_security_controls(checks, integrations):
    check_map = {item['key']: item for item in checks}
    cors_score = 24 if check_map.get('cors-origin', {}).get('status') == 'ready' else 16
    cache_score = 18 if check_map.get('shared-cache', {}).get('status') == 'ready' else 10
    identity = next((item for item in integrations['items'] if item['id'] == 'identity'), None)
    audit = next((item for item in integrations['items'] if item['id'] == 'audit'), None)
    identity_score = min((identity or {}).get('contract_coverage', 0), 100) * .24
    audit_score = min((audit or {}).get('readiness', 0), 100) * .22
    return cors_score + cache_score + identity_score + audit_score


def score_delivery_assets(evidence):
    if not evidence:
        return 0
    weights = {'ready': 100, 'attention': 70, 'blocked': 25}
    return sum(weights.get(item['status'], 55) for item in evidence) / len(evidence)


def maturity_evidence():
    items = [
        ('README', 'README.md', '项目说明与运行边界'),
        ('最终报告', 'docs/final-delivery-report.md', 'Markdown 交付报告'),
        ('DOCX 报告', 'docs/final-delivery-report.docx', 'Word 交付报告'),
        ('截图报告', 'docs/final-screenshot-report.md', '最终截图与 Playwright 证据'),
        ('API 契约审计', 'docs/api-contract-audit-latest.json', '前后端接口合同审计输出'),
        ('交付资产审计', 'docs/delivery-audit-latest.json', '截图、文档、图片和项目卫生审计输出'),
        ('部署手册', 'docs/deployment-supabase-vercel.md', 'Supabase + Vercel 部署说明'),
        ('ER 图', 'docs/images/final/er-diagram.png', '数据库关系图'),
        ('入口截图', 'docs/images/final/entry.png', '最终入口页截图'),
        ('总览截图', 'docs/images/final/final-dark-overview.png', '最终运营总览截图'),
        ('移动端截图', 'docs/images/final/final-mobile-light-overview.png', '最终移动端截图'),
    ]
    evidence = []
    for label, path, description in items:
        target = ROOT / path
        status = 'ready' if target.exists() and (target.is_dir() or target.stat().st_size > 0) else 'blocked'
        evidence.append({
            'label': label,
            'path': path,
            'description': description,
            'status': status,
        })
    return evidence


def maturity_capability_map(integrations):
    groups = {}
    for item in integrations['items']:
        domain = item['domain']
        bucket = groups.setdefault(domain, {
            'domain': domain,
            'modules': [],
            'services': 0,
            'contracts': 0,
            'api_surfaces': 0,
            'data_objects': 0,
            'records': 0,
            'avg_readiness': 0,
            'attention': 0,
        })
        bucket['services'] += 1
        bucket['modules'].append(item['name'])
        bucket['contracts'] += len(item.get('contracts') or [])
        bucket['api_surfaces'] += len(item.get('api_surface') or [])
        bucket['data_objects'] += len(item.get('data_objects') or [])
        bucket['records'] += int(item.get('records') or 0)
        bucket['avg_readiness'] += int(item.get('readiness') or 0)
        bucket['attention'] += 1 if item.get('status') != 'healthy' else 0
    for bucket in groups.values():
        bucket['avg_readiness'] = round(bucket['avg_readiness'] / max(bucket['services'], 1))
        bucket['modules'] = bucket['modules'][:6]
    return list(groups.values())


def maturity_topology_nodes(integrations):
    return [
        {
            'id': item['id'],
            'name': item['name'],
            'domain': item['domain'],
            'owner': item['owner'],
            'path': item['path'],
            'runtime_unit': item['runtime']['unit'],
            'store': item['runtime']['store'],
            'readiness': item['readiness'],
            'contract_coverage': item['contract_coverage'],
            'status': item['status'],
            'risk_note': item['risk_note'],
        }
        for item in integrations['items']
    ]


def env_check(key, label, value, scope, evidence, action, min_length=1):
    configured = bool(value and len(str(value)) >= min_length and 'example' not in str(value).lower())
    return {
        'key': key,
        'label': label,
        'scope': scope,
        'status': 'ready' if configured else 'attention',
        'evidence': evidence if configured else '当前环境未配置，需在目标平台写入。',
        'action': action,
    }


def file_check(key, label, files, scope, action):
    missing = [item for item in files if not (ROOT / item).exists()]
    return {
        'key': key,
        'label': label,
        'scope': scope,
        'status': 'ready' if not missing else 'blocked',
        'evidence': ' / '.join(files) if not missing else f"缺失: {', '.join(missing)}",
        'action': action,
    }


def storage_status(health):
    if is_cloud_storage_enabled():
        return 'ready'
    if health['storage']['status'] == 'missing_cloud':
        return 'blocked'
    return 'attention'


def storage_evidence(health):
    status = health['storage']['status']
    requirement = health['storage']['requirement']
    writable = health['storage']['writable']
    return f"{status} / requirement={requirement} / writable={sum(1 for value in writable.values() if value)}/{len(writable)}"


def cors_status():
    origins = current_app.config.get('CORS_ORIGINS') or []
    secure = bool(current_app.config.get('AUTH_COOKIE_SECURE'))
    if secure and origins and not any('localhost' in item or '127.0.0.1' in item for item in origins):
        return 'ready'
    return 'attention'


def cors_evidence():
    origins = current_app.config.get('CORS_ORIGINS') or []
    secure = current_app.config.get('AUTH_COOKIE_SECURE')
    same_site = current_app.config.get('AUTH_COOKIE_SAMESITE')
    return f"{len(origins)} origins / secure={secure} / sameSite={same_site}"
