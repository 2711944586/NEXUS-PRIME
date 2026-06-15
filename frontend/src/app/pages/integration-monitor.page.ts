import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { chartLegend, compactNumberText, dateText } from './page-utils';

interface IntegrationItem {
  id: string;
  name: string;
  domain: string;
  owner: string;
  status: 'healthy' | 'attention' | string;
  latency_ms: number;
  slo_ms: number;
  records: number;
  readiness: number;
  contract_coverage: number;
  risk_note: string;
  last_sync: string;
  path: string;
  runtime: {
    unit: string;
    probe: string;
    store: string;
  };
  dependencies: string[];
  contracts: string[];
  api_surface: string[];
  data_objects: string[];
  runbook: string[];
  observability: {
    signals: Record<'metrics' | 'logs' | 'traces', boolean>;
    coverage: number;
    missing: string[];
    evidence: string[];
    span_name: string;
    metric_name: string;
    log_stream: string;
    data_objects: string[];
  };
}

interface DomainSummary {
  domain: string;
  services: number;
  attention: number;
  records: number;
  avg_readiness: number;
}

interface DependencyLink {
  from: string;
  to: string;
}

interface IntegrationPayload {
  items: IntegrationItem[];
  summary: {
    healthy: number;
    attention: number;
    records: number;
    avg_latency_ms: number;
    avg_readiness: number;
    contracts: number;
    dependencies: number;
    api_surfaces: number;
    runbook_steps: number;
    avg_contract_coverage: number;
  };
  topology: {
    deployment_units: string[];
    stores: string[];
    probe_count: number;
    edge_count: number;
    max_dependencies: number;
  };
  observability: {
    coverage: number;
    policy: string;
    missing: string[];
    signals: Array<{ key: string; label: string; ready: number; total: number; coverage: number }>;
  };
  incident_queue: IntegrationIncident[];
  readiness: {
    level: 'ready' | 'attention' | string;
    message: string;
    risk: Record<string, number>;
  };
  dependencies: DependencyLink[];
  domains: DomainSummary[];
}

interface IntegrationIncident {
  id: string;
  service_id: string;
  title: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  owner: string;
  status: string;
  path: string;
  action: string;
  evidence: string;
  due: string;
  error_budget_remaining: number;
  signal_coverage: number;
  contract_coverage: number;
  runtime_unit: string;
}

const EMPTY_INTEGRATIONS: IntegrationPayload = {
  items: [],
  summary: { healthy: 0, attention: 0, records: 0, avg_latency_ms: 0, avg_readiness: 0, contracts: 0, dependencies: 0, api_surfaces: 0, runbook_steps: 0, avg_contract_coverage: 0 },
  topology: { deployment_units: [], stores: [], probe_count: 0, edge_count: 0, max_dependencies: 0 },
  observability: { coverage: 0, policy: 'metrics + logs + traces', missing: [], signals: [] },
  incident_queue: [],
  readiness: { level: 'ready', message: '等待服务目录同步。', risk: {} },
  dependencies: [],
  domains: []
};

@Component({
  standalone: true,
  imports: [CommonModule, RouterLink, NgxEchartsDirective, ButtonModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page integration-monitor-page">
      <header class="atlas-split-hero integration-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">服务目录</span>
          <h1>集成监控中心</h1>
          <p>按平台、供应链、营收和经营分析域追踪服务契约、依赖、SLO、记录吞吐和微服务拆分就绪度。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="resync()" [loading]="syncing()" aria-label="创建接口重同步任务">
              <i class="pi pi-sync"></i>
              创建重同步任务
            </button>
            <button pButton type="button" severity="secondary" (click)="load()" aria-label="刷新集成状态">
              <i class="pi pi-refresh"></i>
              刷新状态
            </button>
            <a pButton severity="info" routerLink="/app/data-quality">
              <i class="pi pi-shield"></i>
              数据质量
            </a>
          </div>
        </div>
        <aside class="integration-summary-stack">
          <article><span>健康接口</span><strong>{{ data().summary.healthy }}</strong><em>在线</em></article>
          <article class="warning"><span>关注接口</span><strong>{{ data().summary.attention }}</strong><em>需复核</em></article>
          <article><span>契约数量</span><strong>{{ data().summary.contracts }}</strong><em>{{ data().summary.dependencies }} 条依赖</em></article>
          <article><span>契约覆盖</span><strong>{{ data().summary.avg_contract_coverage }}%</strong><em>{{ data().summary.api_surfaces }} 个 API 面</em></article>
        </aside>
      </header>

      <section class="integration-grid">
        <article class="atlas-panel integration-chart-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">吞吐</span>
              <h2>服务吞吐、延迟与 SLO</h2>
            </div>
            <p-tag [severity]="data().readiness.level === 'ready' ? 'success' : 'warn'" [value]="data().readiness.level === 'ready' ? '服务就绪' : '需要治理'" />
          </div>
          <p class="integration-readiness-copy">{{ data().readiness.message }}</p>
          @if (loading()) {
            <p-skeleton height="340px" />
          } @else {
            <div class="integration-chart" echarts [options]="chart()"></div>
          }
        </article>

        <article class="atlas-panel integration-chart-panel integration-status-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">系统健康</span>
              <h2>接口健康结构</h2>
            </div>
            <p-tag [severity]="data().summary.attention ? 'warn' : 'success'" [value]="data().summary.attention ? '需关注' : '稳定'" />
          </div>
          @if (loading()) {
            <p-skeleton height="280px" />
          } @else {
            <div class="integration-chart compact" echarts [options]="statusChart()"></div>
          }
        </article>

        <article class="atlas-panel integration-command-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">治理指挥层</span>
              <h2>服务契约、观测信号与错误预算</h2>
            </div>
            <p-tag [severity]="data().incident_queue.length ? 'warn' : 'success'" [value]="data().incident_queue.length ? data().incident_queue.length + ' 个治理项' : '稳定'" />
          </div>
          <div class="integration-command-summary" aria-label="服务治理摘要">
            <article class="business-data-row">
              <span>观测覆盖</span>
              <strong>{{ data().observability.coverage }}%</strong>
              <em>{{ data().observability.policy }}</em>
            </article>
            <article class="business-data-row">
              <span>平均就绪</span>
              <strong>{{ data().summary.avg_readiness }}%</strong>
              <em>{{ data().summary.avg_contract_coverage }}% 契约</em>
            </article>
            <article class="business-data-row">
              <span>待处理</span>
              <strong>{{ data().incident_queue.length }}</strong>
              <em>按 SLO 与信号缺口排序</em>
            </article>
          </div>
          <div class="integration-signal-strip">
            @for (signal of data().observability.signals; track signal.key) {
              <article class="business-data-row">
                <span>{{ signal.label }}</span>
                <strong>{{ signal.coverage }}%</strong>
                <em>{{ signal.ready }} / {{ signal.total }} 服务</em>
              </article>
            }
          </div>
          @if (loading()) {
            <p-skeleton height="92px" />
            <p-skeleton height="92px" />
          } @else if (!data().incident_queue.length) {
            <div class="lane-empty">当前服务契约、观测信号和错误预算均稳定</div>
          } @else {
            <div class="integration-incident-list">
              @for (item of data().incident_queue; track item.id) {
                <article class="business-data-row integration-incident-card" [class.p0]="item.priority === 'P0'" [class.p1]="item.priority === 'P1'">
                  <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
                  <div>
                    <span>{{ item.owner }} · {{ item.runtime_unit }} · {{ item.due }}</span>
                    <strong>{{ item.title }}</strong>
                    <em>{{ item.evidence }}</em>
                    <div class="integration-budget-row" aria-label="错误预算与观测覆盖">
                      <span>错误预算 {{ item.error_budget_remaining }}%</span>
                      <i><b [style.width.%]="item.error_budget_remaining"></b></i>
                      <span>信号 {{ item.signal_coverage }}% / 契约 {{ item.contract_coverage }}%</span>
                    </div>
                  </div>
                  <div class="integration-incident-actions">
                    <a pButton [text]="true" size="small" [routerLink]="item.path" [attr.aria-label]="'查看服务来源 ' + item.title">
                      <i class="pi pi-arrow-up-right"></i>
                      来源
                    </a>
                    <button pButton type="button" size="small" severity="secondary" [loading]="syncingId() === item.id" [disabled]="syncing()" (click)="resync(item)" [attr.aria-label]="'创建服务治理任务 ' + item.title">
                      <i class="pi pi-send"></i>
                      创建任务
                    </button>
                  </div>
                </article>
              }
            </div>
          }
        </article>

        <article class="atlas-panel integration-list-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">服务</span>
              <h2>服务目录</h2>
            </div>
          </div>
          <div class="integration-system-list">
            @for (item of data().items; track item.id) {
              <a class="business-data-row" [routerLink]="item.path" [class.warning]="item.status !== 'healthy'">
                <div class="service-line-head">
                  <p-tag [severity]="item.status === 'healthy' ? 'success' : 'warn'" [value]="item.status === 'healthy' ? '健康' : '关注'" />
                  <strong>{{ item.name }}</strong>
                  <b>{{ item.readiness }}%</b>
                </div>
                <span>{{ domainLabel(item.domain) }} / {{ item.owner }}</span>
                <em>{{ compact(item.records) }} 条记录 / {{ item.latency_ms }} ms / SLO {{ item.slo_ms }} ms</em>
                <p>{{ item.risk_note }}</p>
                <div class="service-readiness-meter" aria-hidden="true"><i [style.width.%]="item.readiness"></i></div>
                <small>{{ contractLabels(item.contracts).join(' · ') }}</small>
                <div class="service-runtime-strip">
                  <span>{{ item.runtime.unit }}</span>
                  <span>{{ apiLabel(item.runtime.probe) }}</span>
                  <span>{{ item.contract_coverage }}% 契约</span>
                </div>
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel integration-topology-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">拓扑</span>
              <h2>运行单元与探针</h2>
            </div>
          </div>
          <div class="integration-topology-grid">
            <article class="business-data-row">
              <span>部署单元</span>
              <strong>{{ data().topology.deployment_units.length }}</strong>
              <em>{{ data().topology.deployment_units.join(' / ') }}</em>
            </article>
            <article class="business-data-row">
              <span>健康探针</span>
              <strong>{{ data().topology.probe_count }}</strong>
              <em>最大依赖 {{ data().topology.max_dependencies }}</em>
            </article>
            <article class="business-data-row">
              <span>数据后端</span>
              <strong>{{ data().topology.stores.length }}</strong>
              <em>{{ data().topology.stores.join(' / ') }}</em>
            </article>
            <article class="business-data-row">
              <span>Runbook</span>
              <strong>{{ data().summary.runbook_steps }}</strong>
              <em>治理步骤</em>
            </article>
          </div>
        </article>

        <article class="atlas-panel integration-domain-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">域</span>
              <h2>微服务域就绪</h2>
            </div>
          </div>
          <div class="integration-domain-list">
            @for (domain of data().domains; track domain.domain) {
              <article class="business-data-row" [class.warning]="domain.attention">
                <span>{{ domainLabel(domain.domain) }}</span>
                <strong>{{ domain.avg_readiness }}%</strong>
                <em>{{ domain.services }} 个服务 / {{ compact(domain.records) }} 条记录</em>
                <p-tag [severity]="domain.attention ? 'warn' : 'success'" [value]="domain.attention ? domain.attention + ' 个关注' : '稳定'" />
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel integration-dependency-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">依赖</span>
              <h2>服务调用链</h2>
            </div>
          </div>
          <div class="integration-dependency-list">
            @for (link of data().dependencies.slice(0, 14); track link.from + '-' + link.to) {
              <span class="business-data-row"><strong>{{ serviceName(link.from) }}</strong><i class="pi pi-arrow-right"></i><em>{{ serviceName(link.to) }}</em></span>
            }
          </div>
        </article>

        <article class="atlas-panel integration-runbook-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">Runbook</span>
              <h2>{{ attentionSystemTitle() }}</h2>
            </div>
            @if (attentionSystem()) {
              <p-tag [severity]="attentionSystemSeverity()" [value]="attentionSystemStatusLabel()" />
            }
          </div>
          @if (attentionSystem(); as service) {
            <div class="integration-runbook-list">
              @for (step of service.runbook; track step) {
                <span class="business-data-row"><i class="pi pi-check-circle"></i>{{ step }}</span>
              }
            </div>
            <div class="integration-api-surface">
              @for (api of service.api_surface; track api) {
                <code>{{ apiLabel(api) }}</code>
              }
            </div>
          }
        </article>

        <aside class="atlas-panel integration-action-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">治理动作</span>
              <h2>数据落点</h2>
            </div>
          </div>
          <a class="business-data-row" routerLink="/app/inventory/stock"><i class="pi pi-database"></i><span>库存与库位同步</span></a>
          <a class="business-data-row" routerLink="/app/procurement/orders"><i class="pi pi-shopping-cart"></i><span>采购与 ERP 对账</span></a>
          <a class="business-data-row" routerLink="/app/finance/receivables"><i class="pi pi-wallet"></i><span>财务与应收回写</span></a>
          <a class="business-data-row" routerLink="/app/system/audit"><i class="pi pi-history"></i><span>接口审计追踪</span></a>
        </aside>
      </section>
    </section>
  `
})
export class IntegrationMonitorPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly syncingId = signal('');
  protected readonly syncing = computed(() => Boolean(this.syncingId()));
  protected readonly data = signal<IntegrationPayload>(EMPTY_INTEGRATIONS);
  protected readonly attentionSystem = computed(() => this.data().items.find(item => item.status !== 'healthy') ?? this.data().items[0] ?? null);
  protected readonly attentionSystemTitle = computed(() => this.attentionSystem()?.name ?? '服务治理');
  protected readonly attentionSystemSeverity = computed(() => this.attentionSystem()?.status === 'healthy' ? 'success' : 'warn');
  protected readonly attentionSystemStatusLabel = computed(() => this.attentionSystem()?.status === 'healthy' ? '稳定' : '优先复核');
  protected readonly serviceNameMap = computed(() => new Map(this.data().items.map(item => [item.id, item.name])));
  protected readonly chart = computed<EChartsCoreOption>(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: chartLegend('top'),
    grid: { left: 18, right: 18, top: 42, bottom: 28, containLabel: true },
    xAxis: { type: 'category', data: this.data().items.map(item => item.name), axisLabel: { rotate: 12 }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: [{ type: 'value' }, { type: 'value', splitLine: { show: false } }],
    series: [
      { name: '记录量', type: 'bar', data: this.data().items.map(item => item.records), itemStyle: { color: '#2563eb', borderRadius: [10, 10, 2, 2] } },
      { name: '延迟', type: 'line', yAxisIndex: 1, smooth: true, data: this.data().items.map(item => item.latency_ms), lineStyle: { width: 3, color: '#0f8f86' } },
      { name: 'SLO', type: 'line', yAxisIndex: 1, smooth: true, data: this.data().items.map(item => item.slo_ms), lineStyle: { width: 2, color: '#d99135', type: 'dashed' } }
    ]
  }));
  protected readonly statusChart = computed<EChartsCoreOption>(() => {
    const data = [
      { name: '健康', value: this.data().summary.healthy },
      { name: '关注', value: this.data().summary.attention }
    ].filter(item => item.value > 0);
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom', '#66738a'),
      series: [{
        type: 'pie',
        radius: ['46%', '74%'],
        center: ['50%', '42%'],
        itemStyle: { borderRadius: 12, borderWidth: 2, borderColor: 'rgba(255,255,255,.55)' },
        label: { fontWeight: 800 },
        data: data.length ? data : [{ name: '稳定', value: 1 }],
        color: ['#0f8f86', '#d99135']
      }]
    };
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.get<IntegrationPayload>('operations/integrations').pipe(
      catchError(() => of(EMPTY_INTEGRATIONS)),
      finalize(() => this.loading.set(false))
    ).subscribe(data => this.data.set(data));
  }

  resync(item?: IntegrationIncident | IntegrationItem): void {
    const target = item ?? this.attentionSystem();
    if (!target || this.syncing()) {
      return;
    }
    const serviceId = 'service_id' in target ? target.service_id : target.id;
    const title = 'title' in target ? target.title : target.name;
    const action = 'action' in target ? target.action : target.runbook[0];
    const evidence = 'evidence' in target ? target.evidence : target.risk_note;
    const priority = 'priority' in target ? target.priority : target.status === 'healthy' ? 'P2' : 'P1';
    this.syncingId.set(target.id);
    this.api.post('operations/integrations/resync', {
      service_id: serviceId,
      system_name: title,
      owner: target.owner,
      priority,
      evidence,
      action
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '重同步任务未创建', detail: error?.message || '接口任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.syncingId.set(''))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '重同步任务已创建', detail: title || '经营接口' });
        this.load();
      }
    });
  }

  compact(value: unknown): string {
    return compactNumberText(value);
  }

  date(value: unknown): string {
    return dateText(value);
  }

  domainLabel(value: string): string {
    const labels: Record<string, string> = {
      platform: '平台',
      supply: '供应链',
      revenue: '营收',
      insight: '分析'
    };
    return labels[value] || value || '-';
  }

  serviceName(id: string): string {
    return this.serviceNameMap().get(id) || id;
  }

  contractLabels(values: string[]): string[] {
    return values.map(value => this.apiLabel(value));
  }

  apiLabel(value: string): string {
    const labels: Record<string, string> = {
      '/api/v1/operations/todo': '运营任务队列',
      'GET /api/v1/operations/todo': 'GET 运营任务队列'
    };
    return labels[value] || value.replace('/api/v1/operations/todo', '运营任务队列');
  }

  prioritySeverity(priority: string): 'success' | 'secondary' | 'info' | 'warn' | 'danger' | 'contrast' {
    if (priority === 'P0') {
      return 'danger';
    }
    if (priority === 'P1') {
      return 'warn';
    }
    return 'info';
  }
}
