import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const pagesDir = path.resolve(process.cwd(), 'src', 'app', 'pages');
const appConfigPath = path.resolve(process.cwd(), 'src', 'app', 'app.config.ts');
const guardPath = path.resolve(process.cwd(), 'src', 'app', 'core', 'echarts-layout.ts');
const outDir = path.resolve(process.cwd(), '..', 'output', 'playwright', `chart-audit-${Date.now()}`);
const files = (await readdir(pagesDir)).filter(file => file.endsWith('.page.ts'));
const findings = [];
const notes = [];

const appConfig = await readFile(appConfigPath, 'utf8');
const guard = await readFile(guardPath, 'utf8');
if (!appConfig.includes('configureEchartsLayout(echarts)')) {
  findings.push({ file: 'src/app/app.config.ts', line: 1, issue: 'ECharts 全局布局 guard 未在启动配置中注册。' });
}
for (const token of ['registerPreprocessor', 'labelLine', 'axisName', 'overflow']) {
  if (!guard.includes(token)) {
    findings.push({ file: 'src/app/core/echarts-layout.ts', line: 1, issue: `ECharts 全局布局 guard 缺少 ${token} 安全配置。` });
  }
}
for (const token of ['normalizeInteraction', 'dataZoom', 'toolbox', 'axisPointer', 'blurScope', 'saveAsImage']) {
  if (!guard.includes(token)) {
    findings.push({ file: 'src/app/core/echarts-layout.ts', line: 1, issue: `ECharts 全局交互 guard 缺少 ${token} 配置。` });
  }
}

for (const file of files) {
  const source = await readFile(path.join(pagesDir, file), 'utf8');
  const lines = source.split(/\r?\n/);
  const hasChartLegend = source.includes('chartLegend(');
  const hasUnsafeLegend = /legend:\s*\{\s*(top|bottom):\s*0/.test(source);
  if (hasUnsafeLegend) {
    pushFinding(file, lines, /legend:\s*\{\s*(top|bottom):\s*0/, '图例未使用 chartLegend，容易在小卡片内挤压或溢出。');
  }

  for (const [index, line] of lines.entries()) {
    if (line.includes("type: 'pie'") && !near(lines, index, 'labelLine') && !source.includes('compactPieSeries(')) {
      notes.push({ file, line: index + 1, issue: '饼图依赖全局布局 guard 隐藏外部标签。' });
      break;
    }
  }

  for (const [index, line] of lines.entries()) {
    if (line.includes("type: 'radar'") && !near(lines, index, 'axisName') && !source.includes('compactRadar(')) {
      notes.push({ file, line: index + 1, issue: '雷达图依赖全局布局 guard 截断指标名。' });
      break;
    }
  }

  if (hasChartLegend && !/import \{[^}]*chartLegend[^}]*\} from '\.\/page-utils';/.test(source)) {
    findings.push({ file, line: 1, issue: '使用 chartLegend 但未从 page-utils 导入。' });
  }
}

await mkdir(outDir, { recursive: true });
await writeFile(path.join(outDir, 'report.json'), JSON.stringify({ findings, notes }, null, 2));

if (findings.length) {
  console.error(`Chart audit failed: ${findings.length} findings. Report: ${path.join(outDir, 'report.json')}`);
  for (const finding of findings.slice(0, 12)) {
    console.error(`${finding.file}:${finding.line} ${finding.issue}`);
  }
  process.exit(1);
}

console.log(`Chart audit passed for ${files.length} page files. Report: ${path.join(outDir, 'report.json')}`);

function near(lines, index, needle) {
  return lines.slice(Math.max(0, index - 12), Math.min(lines.length, index + 24)).some(line => line.includes(needle));
}

function pushFinding(file, lines, pattern, issue) {
  const line = lines.findIndex(item => pattern.test(item)) + 1;
  findings.push({ file, line, issue });
}
