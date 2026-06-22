from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

try:
    from PIL import Image
except Exception:  # pragma: no cover - reported at runtime
    Image = None


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
FINAL_IMAGES = DOCS / 'images' / 'final'

REQUIRED_FILES = [
    'README.md',
    'docs/final-delivery-report.md',
    'docs/final-delivery-report.docx',
    'docs/final-completion-audit.md',
    'docs/final-screenshot-report.md',
    'docs/frontend-upgrade-research-notes.md',
    'docs/final-video-script.md',
    'docs/deployment-supabase-vercel.md',
    'docs/api-token-deployment-guide.md',
    'docs/project-standards.md',
    'docs/architecture-maintenance-review.md',
    'docs/er.mmd',
    'docs/images/final/er-diagram.svg',
    'docs/images/final/er-diagram.png',
    'scripts/preflight.ps1',
    'scripts/deploy-supabase-vercel.ps1',
    'scripts/audit-api-contracts.py',
    'scripts/check-openapi-sync.py',
    'scripts/generate_final_report_docx.py',
    'frontend/src/app/core/visual-assets.ts',
    'legacy/monolith-flask',
]

REQUIRED_SCREENSHOTS = [
    'entry.png',
    'login.png',
    'register.png',
    'after-login.png',
    'overview.png',
    'dock.png',
    'command.png',
    'ai.png',
    'ai-fix.png',
    'settings.png',
    'profile.png',
    'files.png',
    'file-detail.png',
    'reports.png',
    'mobile.png',
    'final-dark-overview.png',
    'final-dark-procurement.png',
    'final-dark-fulfillment.png',
    'final-dark-receivables.png',
    'final-dark-stocktakes.png',
    'final-dark-reports.png',
    'final-dark-integrations.png',
    'final-dark-supplier-collaboration.png',
    'final-light-overview.png',
    'final-light-procurement.png',
    'final-light-receivables.png',
    'final-light-reports.png',
    'final-light-integrations.png',
    'final-mobile-light-overview.png',
    'final-mobile-dark-stocktakes.png',
    'final-mobile-supplier-collaboration.png',
]

TEXT_EXTENSIONS = {
    '.css',
    '.html',
    '.js',
    '.json',
    '.md',
    '.mjs',
    '.ps1',
    '.py',
    '.scss',
    '.ts',
    '.txt',
    '.yml',
    '.yaml',
}

SKIP_PARTS = {
    '.angular',
    '.git',
    '.pytest_cache',
    'dist',
    'legacy',
    'node_modules',
    'output',
    'venv',
}

BAD_TEXT_PATTERNS = [
    ('unfinished Chinese placeholder copy', re.compile(r'占位|内容待完善|截图占位')),
    ('dead href', re.compile(r'href\s*=\s*["\']#["\']')),
    ('dead routerLink', re.compile(r'routerLink\s*=\s*["\']#')),
    ('javascript void link', re.compile(r'javascript:void\(0\)', re.IGNORECASE)),
    ('lorem ipsum copy', re.compile(r'lorem\s+ipsum', re.IGNORECASE)),
]

MARKDOWN_IMAGE_RE = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')
VISUAL_ASSET_RE = re.compile(r'["\'](/images/[^"\']+)["\']')


class Audit:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def regenerate_docx_if_stale(audit: Audit, enabled: bool) -> None:
    source = ROOT / 'docs' / 'final-delivery-report.md'
    output = ROOT / 'docs' / 'final-delivery-report.docx'
    if not source.exists():
        audit.fail('docs/final-delivery-report.md is missing')
        return
    stale = not output.exists() or output.stat().st_mtime < source.stat().st_mtime
    if not stale:
        audit.note('final-delivery-report.docx is current')
        return
    if not enabled:
        audit.fail('docs/final-delivery-report.docx is older than final-delivery-report.md')
        return
    generator = ROOT / 'scripts' / 'generate_final_report_docx.py'
    if not generator.exists():
        audit.fail('scripts/generate_final_report_docx.py is missing')
        return
    result = subprocess.run(
        [sys.executable, str(generator), '--source', str(source), '--output', str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        audit.fail('failed to regenerate final DOCX: ' + (result.stderr or result.stdout).strip())
    else:
        audit.note('regenerated docs/final-delivery-report.docx')


def check_required_files(audit: Audit) -> None:
    for item in REQUIRED_FILES:
        path = ROOT / item
        if not path.exists():
            audit.fail(f'missing required delivery file: {item}')


def clean_markdown_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith('<') and value.endswith('>'):
        value = value[1:-1]
    if ' ' in value and not Path(value).exists():
        value = value.split(' ', 1)[0]
    value = value.split('#', 1)[0].split('?', 1)[0]
    return unquote(value.strip())


def check_markdown_images(audit: Audit) -> None:
    markdown_files = [ROOT / 'README.md'] + sorted(DOCS.rglob('*.md'))
    for md_file in markdown_files:
        if not md_file.exists():
            continue
        source = md_file.read_text(encoding='utf-8')
        for match in MARKDOWN_IMAGE_RE.finditer(source):
            raw = clean_markdown_target(match.group(1))
            if not raw or raw.startswith(('http://', 'https://', 'data:')):
                continue
            target = (md_file.parent / raw).resolve()
            if not target.exists():
                audit.fail(f'{relative(md_file)} references missing image: {match.group(1)}')


def check_final_screenshots(audit: Audit) -> None:
    if Image is None:
        audit.fail('Pillow is required to inspect screenshot dimensions')
        return
    for name in REQUIRED_SCREENSHOTS:
        path = FINAL_IMAGES / name
        if not path.exists():
            audit.fail(f'missing final screenshot: docs/images/final/{name}')
            continue
        if path.stat().st_size < 120_000:
            audit.fail(f'final screenshot is unexpectedly small: {relative(path)}')
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
        except Exception as exc:
            audit.fail(f'cannot read screenshot {relative(path)}: {exc}')
            continue
        is_mobile = name.startswith('final-mobile') or name == 'mobile.png'
        min_width = 320 if is_mobile else 900
        min_height = 520
        if width < min_width or height < min_height:
            audit.fail(f'final screenshot has weak dimensions: {relative(path)} {width}x{height}')
    er_png = FINAL_IMAGES / 'er-diagram.png'
    if er_png.exists() and er_png.stat().st_size < 20_000:
        audit.fail('ER diagram PNG is unexpectedly small')


def check_visual_assets(audit: Audit) -> None:
    registry = ROOT / 'frontend' / 'src' / 'app' / 'core' / 'visual-assets.ts'
    if not registry.exists():
        audit.fail('visual asset registry is missing')
        return
    source = registry.read_text(encoding='utf-8')
    assets = sorted(set(VISUAL_ASSET_RE.findall(source)))
    if len(assets) < 20:
        audit.fail(f'visual asset registry has too few images: {len(assets)}')
    for asset in assets:
        path = ROOT / 'frontend' / 'public' / asset.lstrip('/')
        if not path.exists():
            audit.fail(f'visual asset missing from frontend/public: {asset}')
        elif path.stat().st_size < 30_000:
            audit.fail(f'visual asset is unexpectedly small: {relative(path)}')


def iter_text_files() -> list[Path]:
    roots = [ROOT / 'README.md', ROOT / 'docs', ROOT / 'scripts', ROOT / 'frontend', ROOT / 'backend']
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob('*'):
            if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS and not should_skip(path):
                if path.name == 'audit-delivery-assets.py':
                    continue
                if path.stat().st_size <= 1_200_000:
                    files.append(path)
    return files


def check_dead_copy_and_links(audit: Audit) -> None:
    for path in iter_text_files():
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if '::placeholder' in line:
                continue
            if any(marker in line for marker in ('不得出现', '禁止出现', 'BAD_TEXT_PATTERNS')):
                continue
            for label, pattern in BAD_TEXT_PATTERNS:
                if pattern.search(line):
                    audit.fail(f'{relative(path)}:{line_number} contains {label}')


def git_output(args: list[str]) -> str:
    result = subprocess.run(
        ['git', *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return ''
    return result.stdout


def check_repository_hygiene(audit: Audit) -> None:
    tracked = set(git_output(['ls-files']).splitlines())
    staged_or_changed = git_output(['status', '--short'])
    gitignore = (ROOT / '.gitignore').read_text(encoding='utf-8') if (ROOT / '.gitignore').exists() else ''

    for item in ('backend/instance/nexus_prime.db', 'frontend/public/runtime-config.js'):
        if item in tracked or item in staged_or_changed:
            audit.fail(f'forbidden runtime artifact is tracked or staged: {item}')

    if '!backend/instance/nexus_prime.db' in gitignore:
        audit.fail('.gitignore re-includes backend/instance/nexus_prime.db')
    if 'frontend/public/runtime-config.js' not in gitignore:
        audit.fail('.gitignore must ignore frontend/public/runtime-config.js')

    runtime_config = ROOT / 'frontend' / 'public' / 'runtime-config.js'
    if runtime_config.exists() and re.search(r'127\.0\.0\.1|localhost', runtime_config.read_text(encoding='utf-8')):
        audit.fail('frontend/public/runtime-config.js points to localhost')

    deploy_script = ROOT / 'scripts' / 'deploy-supabase-vercel.ps1'
    if deploy_script.exists():
        text = deploy_script.read_text(encoding='utf-8')
        seed_block = re.search(r'if \(\$SeedRemoteWhenEmpty\) \{(?P<body>.*?)\n\}', text, re.DOTALL)
        if not seed_block:
            audit.fail('deploy script is missing SeedRemoteWhenEmpty block')
        elif '--reset' in seed_block.group('body'):
            audit.fail('SeedRemoteWhenEmpty must not pass --reset')
        elif re.search(r'--admin-password|--user-password', seed_block.group('body')):
            audit.fail('SeedRemoteWhenEmpty must not expose demo passwords as command arguments')
        if '$ResetAndSeedRemote' not in text:
            audit.fail('deploy script should expose ResetAndSeedRemote for explicit destructive reseed')
        if 'NEXUS_DEMO_ADMIN_PASSWORD' not in text or 'NEXUS_DEMO_USER_PASSWORD' not in text:
            audit.fail('deploy script should require custom remote demo passwords')
        if "DemoAdminPassword -ne 'admin123'" not in text or "DemoUserPassword -ne 'password123'" not in text:
            audit.fail('deploy script should reject default demo passwords for remote seeds')
        if 'Format-CommandForLog' not in text or 'Redact-SecretText' not in text:
            audit.fail('deploy script should redact sensitive command output')
        if '--token' not in text or '--target' not in text:
            audit.fail('deploy script should route Vercel token and database target through redacted command logging')

    auth_service = ROOT / 'frontend' / 'src' / 'app' / 'core' / 'auth.service.ts'
    if auth_service.exists():
        auth_text = auth_service.read_text(encoding='utf-8')
        if 'localStorage.setItem(USER_KEY' in auth_text:
            audit.fail('AuthService must not persist user profiles in localStorage')
        if 'sessionStorage.setItem(USER_KEY' not in auth_text:
            audit.fail('AuthService should keep only session-scoped user profile cache')

    routes = ROOT / 'backend' / 'app' / 'api' / 'routes.py'
    if routes.exists():
        routes_text = routes.read_text(encoding='utf-8')
        auth_payloads = re.findall(r'return with_auth_cookies\(\s*(?P<payload>\{[^\n]*\})', routes_text)
        if any(re.search(r"'token'\s*:\s*token", payload) for payload in auth_payloads):
            audit.fail('auth responses must not expose JWT token in JSON payloads')

    models = ROOT / 'frontend' / 'src' / 'app' / 'core' / 'models.ts'
    if models.exists():
        models_text = models.read_text(encoding='utf-8')
        login_match = re.search(r'export interface LoginResult \{(?P<body>.*?)\n\}', models_text, re.DOTALL)
        if login_match and re.search(r'\btoken\??:', login_match.group('body')):
            audit.fail('frontend LoginResult should not model a readable access token')

    login_page = ROOT / 'frontend' / 'src' / 'app' / 'pages' / 'login.page.ts'
    if login_page.exists():
        login_page_text = login_page.read_text(encoding='utf-8')
        if re.search(r'admin123|password123', login_page_text):
            audit.fail('login page must not hard-code local demo passwords')

    prod_environment = ROOT / 'frontend' / 'src' / 'environments' / 'environment.prod.ts'
    if prod_environment.exists():
        prod_environment_text = prod_environment.read_text(encoding='utf-8')
        if re.search(r'admin123|password123', prod_environment_text):
            audit.fail('production environment must not contain local demo passwords')
        if not re.search(r'demoAccounts:\s*\{\s*\}', prod_environment_text):
            audit.fail('production environment should disable demo account shortcuts')

    experience = ROOT / 'backend' / 'app' / 'api' / 'experience.py'
    if experience.exists():
        exp_text = experience.read_text(encoding='utf-8')
        if 'attachment_query = attachment_query.filter(Attachment.uploader_id == user.id)' not in exp_text:
            audit.fail('global search must scope attachment results to current user for non-admins')
        if 'unread_query = unread_query.filter(Notification.user_id == user.id)' not in exp_text:
            audit.fail('operations todo/exceptions must scope unread notifications to current user for non-admins')

    upload_policy = ROOT / 'backend' / 'upload_policy.py'
    if upload_policy.exists():
        upload_text = upload_policy.read_text(encoding='utf-8')
        if 'office_zip_signature_matches' not in upload_text or '[Content_Types].xml' not in upload_text:
            audit.fail('upload policy must validate Office zip structure, not only ZIP magic bytes')

    config_py = ROOT / 'backend' / 'config.py'
    if config_py.exists():
        config_text = config_py.read_text(encoding='utf-8')
        if 'cache_config_from_env' not in config_text or 'REDIS_URL' not in config_text:
            audit.fail('backend config must support shared Redis cache for production rate limits')
        if 'ALLOW_PRODUCTION_SIMPLE_CACHE' not in config_text:
            audit.fail('production config must reject SimpleCache unless explicitly overridden')

    clean_script = ROOT / 'scripts' / 'clean-workspace.ps1'
    if clean_script.exists():
        clean_text = clean_script.read_text(encoding='utf-8')
        if 'Restore-RuntimeConfig' not in clean_text or "apiBaseUrl: ''" not in clean_text:
            audit.fail('clean-workspace.ps1 must restore runtime-config.js fallback')
        if "'.pytest_cache'" not in clean_text:
            audit.fail('clean-workspace.ps1 should remove root .pytest_cache')

    quality_gate = ROOT / 'scripts' / 'quality-gate.ps1'
    if quality_gate.exists():
        quality_text = quality_gate.read_text(encoding='utf-8')
        if 'Get-PowerShellExecutable' not in quality_text:
            audit.fail('quality-gate.ps1 should resolve pwsh/powershell before invoking helper scripts')
        if 'CACHE_TYPE' not in quality_text or 'REDIS_URL' not in quality_text or 'CACHE_REDIS_URL' not in quality_text:
            audit.fail('quality-gate.ps1 preflight environment must include shared Redis cache settings')
        layout_block = re.search(r"if \(-not \$SkipLayoutAudit(?:[^\n]*?)\) \{(?P<body>.*?)\n    \}", quality_text, re.DOTALL)
        if not layout_block or 'Restore-RuntimeConfig' not in layout_block.group('body'):
            audit.fail('quality-gate.ps1 must restore runtime-config.js after layout audit before deployment preflight')
        if 'audit:deployment-readiness' not in quality_text or 'SkipDeploymentReadinessAudit' not in quality_text:
            audit.fail('quality-gate.ps1 must run deployment readiness and ERP maturity audit by default')
        delivery_restore = re.search(r'Restore-RuntimeConfig\s+-Force\s*\n\s*if \(-not \$SkipDeliveryAssets\)', quality_text)
        if not delivery_restore:
            audit.fail('quality-gate.ps1 must force-restore runtime-config.js before delivery asset audit')
        if 'audit-api-contracts.py' not in quality_text or 'SkipApiContractAudit' not in quality_text:
            audit.fail('quality-gate.ps1 must run frontend/backend API contract audit by default')
        if 'check-openapi-sync.py' not in quality_text:
            audit.fail('quality-gate.ps1 must check generated OpenAPI artifacts stay synchronized')

    ci_workflow = ROOT / '.github' / 'workflows' / 'ci.yml'
    if ci_workflow.exists():
        ci_text = ci_workflow.read_text(encoding='utf-8')
        if 'audit-api-contracts.py' not in ci_text:
            audit.fail('CI delivery hygiene must run API contract audit')
        if 'check-openapi-sync.py' not in ci_text:
            audit.fail('CI delivery hygiene must check generated OpenAPI artifacts stay synchronized')
        if 'actions/upload-artifact@v4' not in ci_text or 'delivery-hygiene-reports' not in ci_text:
            audit.fail('CI delivery hygiene must upload audit reports as artifacts')
        if 'output/*.json' not in ci_text or 'frontend/output/**/*.json' not in ci_text:
            audit.fail('CI delivery hygiene artifact upload must include backend and frontend JSON reports')


def write_json_report(audit: Audit, output: Path | None) -> None:
    if not output:
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                'failures': audit.failures,
                'warnings': audit.warnings,
                'notes': audit.notes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit final delivery docs, screenshots, and frontend visual assets.')
    parser.add_argument('--no-regenerate-docx', action='store_true', help='Fail instead of regenerating a stale DOCX report.')
    parser.add_argument('--json-output', type=Path, help='Optional JSON report path.')
    args = parser.parse_args()

    audit = Audit()
    regenerate_docx_if_stale(audit, enabled=not args.no_regenerate_docx)
    check_required_files(audit)
    check_markdown_images(audit)
    check_final_screenshots(audit)
    check_visual_assets(audit)
    check_dead_copy_and_links(audit)
    check_repository_hygiene(audit)
    write_json_report(audit, args.json_output)

    for note in audit.notes:
        print(f'OK  {note}')
    for warning in audit.warnings:
        print(f'WARN {warning}')
    if audit.failures:
        print('')
        print('Delivery asset audit failed:')
        for failure in audit.failures:
            print(f'- {failure}')
        return 1

    print('Delivery asset audit passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
