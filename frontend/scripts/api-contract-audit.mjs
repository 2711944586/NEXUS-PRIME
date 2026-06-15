import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import path from 'node:path';

const rootDir = path.resolve(process.cwd(), '..');
const frontendConfigPath = path.resolve(process.cwd(), 'src', 'app', 'core', 'resource-workflow.ts');
const backendDir = path.resolve(rootDir, 'backend');
const outDir = path.resolve(rootDir, 'output', 'playwright', `api-contract-audit-${Date.now()}`);

await mkdir(outDir, { recursive: true });

const frontendSource = await readFile(frontendConfigPath, 'utf8');
const frontendContracts = extractFrontendContracts(frontendSource);
const backendRoutes = loadBackendRoutes();
const findings = [];
const notes = [];

for (const config of frontendContracts) {
  if (!config.resource) {
    notes.push({ key: config.key, issue: 'No backing resource; page is workflow/read-only driven.' });
    continue;
  }

  assertEndpoint(config, 'GET', config.resource, 'list');
  assertEndpoint(config, 'GET', `${config.resource}/:id`, 'detail');

  if (config.createFields > 0) {
    assertEndpoint(config, 'POST', config.createEndpoint || config.resource, 'create');
  }
  if (config.editFields > 0) {
    assertEndpoint(config, 'PATCH', `${config.updateEndpoint || config.resource}/:id`, 'update');
  }
  if (config.canDelete !== false) {
    assertEndpoint(config, 'DELETE', `${config.deleteEndpoint || config.resource}/:id`, 'delete');
  }
  if (config.exportable) {
    assertEndpoint(config, 'GET', `export/${lastSegment(config.resource)}/:format`, 'export');
  }

  for (const lookup of config.lookups) {
    assertEndpoint(config, 'GET', lookup, `lookup:${lookup}`);
  }

  for (const action of config.actions) {
    if (!action.endpoint) {
      if (!action.path) {
        findings.push({ key: config.key, contract: 'action', issue: `Action "${action.label}" has neither endpoint nor path.` });
      }
      continue;
    }
    assertEndpoint(config, action.method || 'POST', action.endpoint, `action:${action.label}`);
  }
}

const report = {
  generatedAt: new Date().toISOString(),
  frontendContracts,
  backendRoutes,
  findings,
  notes
};
await writeFile(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2));

const summary = {
  outDir,
  passed: findings.length === 0,
  resources: frontendContracts.length,
  backendRoutes: backendRoutes.length,
  findings,
  notes: notes.slice(0, 12)
};

console.log(JSON.stringify(summary, null, 2));
if (findings.length) {
  process.exit(1);
}

function assertEndpoint(config, method, endpoint, contract) {
  const normalized = normalizeEndpoint(endpoint);
  const matched = backendRoutes.some(route => route.methods.includes(method) && routeMatches(route.rule, normalized));
  if (!matched) {
    findings.push({
      key: config.key,
      title: config.title,
      contract,
      method,
      endpoint: normalized,
      issue: 'No matching backend route in Flask url_map.'
    });
  }
}

function loadBackendRoutes() {
  const script = String.raw`
import json
import os
os.environ.setdefault('SECRET_KEY', 'audit-secret-key-with-enough-length-123456')
os.environ.setdefault('FLASK_ENV', 'development')
from app import create_app
app = create_app('development')
routes = []
for rule in sorted(app.url_map.iter_rules(), key=lambda r: str(r)):
    text = str(rule)
    if not text.startswith('/api/v1'):
        continue
    routes.append({
        'rule': text.replace('/api/v1/', '').replace('/api/v1', ''),
        'methods': sorted(m for m in rule.methods if m not in {'HEAD', 'OPTIONS'}),
    })
print(json.dumps(routes, ensure_ascii=False))
`;
  const result = spawnSync('python', ['-c', script], {
    cwd: backendDir,
    encoding: 'utf8',
    env: {
      ...process.env,
      SECRET_KEY: process.env.SECRET_KEY || 'audit-secret-key-with-enough-length-123456',
      FLASK_ENV: 'development',
      FLASK_CONFIG: 'development'
    }
  });

  if (result.status !== 0) {
    throw new Error(`Failed to load Flask url_map:\n${result.stderr || result.stdout}`);
  }
  const jsonLine = result.stdout.trim().split(/\r?\n/).find(line => line.trim().startsWith('['));
  if (!jsonLine) {
    throw new Error(`Flask route dump did not produce JSON:\n${result.stdout}\n${result.stderr}`);
  }
  return JSON.parse(jsonLine).map(route => ({
    ...route,
    rule: normalizeRule(route.rule)
  }));
}

function extractFrontendContracts(source) {
  const configs = [];
  const start = source.indexOf('export const RESOURCE_WORKFLOW_CONFIGS');
  const end = source.indexOf('export function resourceConfigForUrl', start);
  if (start < 0 || end < 0) {
    throw new Error('Could not locate RESOURCE_WORKFLOW_CONFIGS block.');
  }
  const block = source.slice(start, end);
  const objectBlocks = splitTopLevelObjects(block.slice(block.indexOf('[') + 1, block.lastIndexOf(']')));

  for (const item of objectBlocks) {
    const key = stringProp(item, 'key');
    if (!key) {
      continue;
    }
    configs.push({
      key,
      title: stringProp(item, 'title') || key,
      resource: stringProp(item, 'resource'),
      createEndpoint: stringProp(item, 'createEndpoint'),
      updateEndpoint: stringProp(item, 'updateEndpoint'),
      deleteEndpoint: stringProp(item, 'deleteEndpoint'),
      createFields: arrayPropLength(item, 'createFields'),
      editFields: arrayPropLength(item, 'editFields'),
      exportable: booleanProp(item, 'exportable'),
      canDelete: booleanProp(item, 'canDelete'),
      lookups: [...item.matchAll(/lookup:\s*\{\s*path:\s*'([^']+)'/g)].map(match => match[1]),
      actions: extractActions(item)
    });
  }
  return configs;
}

function extractActions(configBlock) {
  const actionsBlock = arrayPropBlock(configBlock, 'actions');
  if (!actionsBlock) {
    return [];
  }
  return splitTopLevelObjects(actionsBlock).map(action => ({
    label: stringProp(action, 'label') || 'unnamed',
    endpoint: stringProp(action, 'endpoint'),
    method: stringProp(action, 'method'),
    path: stringProp(action, 'path')
  }));
}

function splitTopLevelObjects(text) {
  const objects = [];
  let depth = 0;
  let start = -1;
  let quote = '';
  let escaped = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (char === '\\') {
        escaped = true;
      } else if (char === quote) {
        quote = '';
      }
      continue;
    }
    if (char === '"' || char === "'" || char === '`') {
      quote = char;
      continue;
    }
    if (char === '{') {
      if (depth === 0) {
        start = index;
      }
      depth += 1;
    } else if (char === '}') {
      depth -= 1;
      if (depth === 0 && start >= 0) {
        objects.push(text.slice(start, index + 1));
        start = -1;
      }
    }
  }
  return objects;
}

function arrayPropBlock(text, prop) {
  const marker = `${prop}:`;
  const propIndex = text.indexOf(marker);
  if (propIndex < 0) {
    return '';
  }
  const start = text.indexOf('[', propIndex);
  if (start < 0) {
    return '';
  }
  let depth = 0;
  let quote = '';
  let escaped = false;
  for (let index = start; index < text.length; index += 1) {
    const char = text[index];
    if (quote) {
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === quote) quote = '';
      continue;
    }
    if (char === '"' || char === "'" || char === '`') {
      quote = char;
      continue;
    }
    if (char === '[') depth += 1;
    if (char === ']') {
      depth -= 1;
      if (depth === 0) {
        return text.slice(start + 1, index);
      }
    }
  }
  return '';
}

function stringProp(text, prop) {
  const match = text.match(new RegExp(`${prop}:\\s*'([^']*)'`));
  return match?.[1] || '';
}

function booleanProp(text, prop) {
  const match = text.match(new RegExp(`${prop}:\\s*(true|false)`));
  return match ? match[1] === 'true' : undefined;
}

function arrayPropLength(text, prop) {
  const arrayBlock = arrayPropBlock(text, prop);
  if (arrayBlock) {
    return splitTopLevelObjects(arrayBlock).length;
  }
  const variableMatch = text.match(new RegExp(`${prop}:\\s*([A-Za-z][A-Za-z0-9_]*)`));
  if (variableMatch) {
    const declaration = frontendSource.match(new RegExp(`const\\s+${variableMatch[1]}\\s*:\\s*ResourceFieldConfig\\[\\]\\s*=\\s*\\[([\\s\\S]*?)\\];`));
    return declaration ? splitTopLevelObjects(declaration[1]).length : 1;
  }
  const filteredVariableMatch = text.match(new RegExp(`${prop}:\\s*([A-Za-z][A-Za-z0-9_]*)\\.filter`));
  if (filteredVariableMatch) {
    const declaration = frontendSource.match(new RegExp(`const\\s+${filteredVariableMatch[1]}\\s*:\\s*ResourceFieldConfig\\[\\]\\s*=\\s*\\[([\\s\\S]*?)\\];`));
    return declaration ? Math.max(1, splitTopLevelObjects(declaration[1]).length - 1) : 1;
  }
  return 0;
}

function normalizeEndpoint(endpoint) {
  return String(endpoint || '')
    .replace(/^\/?api\/v1\/?/, '')
    .replace(/^\/+/, '')
    .replace(/:id\b/g, ':int')
    .replace(/:format\b/g, ':path')
    .replace(/:([A-Za-z_][A-Za-z0-9_]*)/g, ':int');
}

function normalizeRule(rule) {
  return String(rule || '')
    .replace(/^\/+/, '')
    .replace(/<int:[^>]+>/g, ':int')
    .replace(/<path:[^>]+>/g, ':path')
    .replace(/<[^>]+>/g, ':segment');
}

function routeMatches(rule, endpoint) {
  if (rule === endpoint) {
    return true;
  }
  if (rule === ':segment') {
    return !endpoint.includes('/');
  }
  if (rule === ':path') {
    return Boolean(endpoint);
  }
  if (rule === ':segment/:int') {
    return endpoint.split('/').length === 2 && endpoint.endsWith('/:int');
  }
  if (rule === ':path/:int') {
    return endpoint.endsWith('/:int');
  }
  const ruleRegex = new RegExp(`^${escapeRegex(rule).replaceAll(':int', '[^/]+').replaceAll(':path', '.+')}$`);
  return ruleRegex.test(endpoint);
}

function lastSegment(value) {
  return String(value || '').split('/').filter(Boolean).pop() || value;
}

function escapeRegex(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
