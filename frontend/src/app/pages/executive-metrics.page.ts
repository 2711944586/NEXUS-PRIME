import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { ProgressBarModule } from 'primeng/progressbar';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, forkJoin, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { ExecutiveAnalytics, ManufacturingCommandCenter, OperationsTodoPayload } from '../core/models';
import { chartLegend, compactMoneyText, compactNumberText } from './page-utils';

const EMPTY_ANALYTICS: ExecutiveAnalytics = {
  kpis: { total_sales: 0, unpaid_amount: 0, pending_purchase: 0, active_alerts: 0, collaboration_items: 0 },
  sales_trend: [],
  risk_mix: [],
  collaboration: [],
  top_customers: [],
  procurement_stages: [],
  aging_buckets: [],
  warehouse_turnover: [],
  supplier_score: [],
  inventory_risk_rank: [],
  order_status_flow: [],
  cash_collection_trend: [],
  action_queue: [],
  operational_efficiency: [],
  module_throughput: []
};

const EMPTY_COMMAND: ManufacturingCommandCenter = {
  kpis: { order_amount: 0, stock_quantity: 0, low_stock_products: 0, pending_purchase: 0, overdue_amount: 0 },
  warehouse_heat: [],
  flows: [],
  risks: []
};

const EMPTY_TODO: OperationsTodoPayload = { items: [], stock_quantity: 0 };

@Component({
  standalone: true,
  imports: [CommonModule, RouterLink, NgxEchartsDirective, ButtonModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page executive-metrics-page">
      <header class="executive-metrics-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">经营指标</span>
          <h1>经营指标中心</h1>
          <p>把销售、库存、采购、履约、财务与协作处理率放在同一个经营视图，便于管理层快速判断系统运行质量。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="createDailyBrief()" [loading]="briefCreating()" aria-label="创建经营复盘任务">
              <i class="pi pi-flag"></i>
              创建复盘任务
            </button>
            <button pButton type="button" severity="secondary" (click)="generateReport()" [loading]="reporting()" aria-label="生成经营指标报表">
              <i class="pi pi-chart-line"></i>
              生成指标报表
            </button>
            <a pButton severity="info" routerLink="/app/reports">
              <i class="pi pi-folder-open"></i>
              报表归档
            </a>
          </div>
        </div>

        <aside class="metrics-hero-board">
          <article class="business-data-row">
            <span>销售额</span>
            <strong>{{ compactMoney(analytics().kpis.total_sales) }}</strong>
            <em>累计订单金额</em>
          </article>
          <article class="business-data-row">
            <span>库存量</span>
            <strong>{{ compactNumber(command().kpis.stock_quantity || todo().stock_quantity) }}</strong>
            <em>跨仓合计</em>
          </article>
          <article class="warning business-data-row">
            <span>待处理</span>
            <strong>{{ todoTotal() }}</strong>
            <em>跨模块队列</em>
          </article>
        </aside>
      </header>

      <section class="metrics-kpi-strip">
        @for (card of kpiCards(); track card.label) {
          <a class="business-data-row" [routerLink]="card.path" [class.warning]="card.tone === 'warning'">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <em>{{ card.description }}</em>
            <p-progressbar [value]="card.progress" [showValue]="false" />
          </a>
        }
      </section>

      <section class="metrics-grid">
        <article class="atlas-panel metrics-chart-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">趋势</span>
              <h2>销售与回款趋势</h2>
            </div>
            <div class="metric-mode-switch" aria-label="指标图表模式">
              @for (mode of chartModes; track mode.key) {
                <button type="button" [class.active]="chartMode() === mode.key" (click)="chartMode.set(mode.key)">
                  <i class="pi" [class]="mode.icon"></i>
                  {{ mode.label }}
                </button>
              }
            </div>
          </div>
          @if (loading()) {
            <p-skeleton height="360px" />
          } @else {
            <div class="executive-chart large" echarts [options]="activeChart()"></div>
          }
        </article>

        <article class="atlas-panel metrics-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">效率</span>
              <h2>运营效率</h2>
            </div>
            <p-tag severity="success" value="目标对照" />
          </div>
          <div class="efficiency-list">
            @for (item of efficiency(); track item.name) {
              <a class="business-data-row" [routerLink]="efficiencyPath(item.name)" [class.warning]="item.value < item.target">
                <span>{{ item.name }}</span>
                <strong>{{ item.value }}%</strong>
                <em>目标 {{ item.target }}%</em>
                <p-progressbar [value]="item.value" [showValue]="false" />
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel metrics-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">吞吐</span>
              <h2>模块吞吐</h2>
            </div>
          </div>
          <div class="executive-chart" echarts [options]="throughputChart()"></div>
        </article>

        <article class="atlas-panel metrics-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">风险结构</span>
              <h2>风险构成</h2>
            </div>
          </div>
          <div class="executive-chart" echarts [options]="riskChart()"></div>
        </article>

        <article class="atlas-panel metrics-todo-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">行动</span>
              <h2>待办入口</h2>
            </div>
            <button pButton type="button" [text]="true" (click)="load()" aria-label="刷新经营指标">
              <i class="pi pi-refresh"></i>
            </button>
          </div>
          <div class="metrics-action-list">
            @for (item of todo().items; track item.label) {
              <a class="business-data-row" [routerLink]="cleanPath(item.path)" [class.warning]="item.value > 0">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
                <em>进入处理</em>
              </a>
            }
          </div>
        </article>
      </section>
    </section>
  `
})
export class ExecutiveMetricsPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly reporting = signal(false);
  protected readonly briefCreating = signal(false);
  protected readonly analytics = signal<ExecutiveAnalytics>(EMPTY_ANALYTICS);
  protected readonly command = signal<ManufacturingCommandCenter>(EMPTY_COMMAND);
  protected readonly todo = signal<OperationsTodoPayload>(EMPTY_TODO);
  protected readonly chartMode = signal<'trend' | 'warehouse' | 'customer'>('trend');
  protected readonly chartModes = [
    { key: 'trend' as const, label: '趋势', icon: 'pi-chart-line' },
    { key: 'warehouse' as const, label: '仓库', icon: 'pi-database' },
    { key: 'customer' as const, label: '客户', icon: 'pi-users' }
  ];

  protected readonly todoTotal = computed(() => this.todo().items.reduce((sum, item) => sum + Number(item.value || 0), 0));
  protected readonly efficiency = computed(() => this.analytics().operational_efficiency?.length ? this.analytics().operational_efficiency! : [
    { name: '履约完成率', value: 0, target: 92 },
    { name: '采购闭环率', value: 0, target: 88 },
    { name: '库存容量利用', value: 0, target: 76 },
    { name: '回款覆盖率', value: 0, target: 86 }
  ]);
  protected readonly kpiCards = computed(() => [
    { label: '销售收入', value: this.compactMoney(this.analytics().kpis.total_sales), description: '订单累计金额', progress: 82, path: '/app/sales/orders', tone: 'success' },
    { label: '未收款', value: this.compactMoney(this.analytics().kpis.unpaid_amount), description: '应收账款余额', progress: Math.min(100, this.analytics().kpis.unpaid_amount / Math.max(this.analytics().kpis.total_sales, 1) * 100), path: '/app/finance/receivables', tone: this.analytics().kpis.unpaid_amount ? 'warning' : 'success' },
    { label: '采购审批', value: `${this.analytics().kpis.pending_purchase} 单`, description: '排队处理', progress: Math.min(100, this.analytics().kpis.pending_purchase * 12), path: '/app/procurement/orders', tone: this.analytics().kpis.pending_purchase ? 'warning' : 'success' },
    { label: '库存预警', value: `${this.analytics().kpis.active_alerts} 项`, description: '安全水位以下', progress: Math.min(100, this.analytics().kpis.active_alerts * 9), path: '/app/inventory/replenishment', tone: this.analytics().kpis.active_alerts ? 'warning' : 'success' }
  ]);
  protected readonly activeChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'warehouse') {
      return this.warehouseChart();
    }
    if (this.chartMode() === 'customer') {
      return this.customerChart();
    }
    return this.trendChart();
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      analytics: this.api.get<ExecutiveAnalytics>('analytics/executive').pipe(catchError(() => of(EMPTY_ANALYTICS))),
      command: this.api.get<ManufacturingCommandCenter>('manufacturing/command-center').pipe(catchError(() => of(EMPTY_COMMAND))),
      todo: this.api.get<OperationsTodoPayload>('operations/todo').pipe(catchError(() => of(EMPTY_TODO)))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(({ analytics, command, todo }) => {
      this.analytics.set(analytics);
      this.command.set(command);
      this.todo.set(todo);
    });
  }

  createDailyBrief(): void {
    this.briefCreating.set(true);
    this.api.post('operations/data-quality-notice', {
      title: '经营指标复盘任务',
      content: `请复核销售、采购、库存和应收指标；当前跨模块待办 ${this.todoTotal()} 项。`,
      type: this.todoTotal() > 0 ? 'warning' : 'info'
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '任务未创建', detail: error?.message || '复盘任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.briefCreating.set(false))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '任务已创建', detail: '已进入通知中心。' });
      }
    });
  }

  generateReport(): void {
    this.reporting.set(true);
    this.api.post('reports/generate/financial_overview', { params: {} }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '报表未生成', detail: error?.message || '报表服务未返回结果。' });
        return of(null);
      }),
      finalize(() => this.reporting.set(false))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '报表已生成', detail: '财务总览已归档。' });
      }
    });
  }

  protected readonly trendChart = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'axis' },
    dataZoom: [{ type: 'inside' }],
    legend: chartLegend('top', 'rgba(100,116,139,.95)'),
    grid: { left: 18, right: 18, top: 38, bottom: 24, containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: this.analytics().sales_trend.map(item => item.name), axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
    series: [
      { name: '销售', type: 'line', smooth: true, symbolSize: 6, data: this.analytics().sales_trend.map(item => item.value), lineStyle: { width: 3, color: '#2ca59d' }, areaStyle: { color: 'rgba(44,165,157,.14)' } },
      { name: '回款', type: 'line', smooth: true, symbolSize: 6, data: (this.analytics().cash_collection_trend ?? []).map(item => item.value), lineStyle: { width: 3, color: '#d99135' }, areaStyle: { color: 'rgba(217,145,53,.13)' } }
    ]
  }));

  protected readonly warehouseChart = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'axis' },
    legend: chartLegend('top', 'rgba(100,116,139,.95)'),
    grid: { left: 18, right: 22, top: 38, bottom: 28, containLabel: true },
    xAxis: { type: 'category', data: (this.analytics().warehouse_turnover ?? []).map(item => item.name), axisLabel: { rotate: 12 }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: [{ type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } }, { type: 'value', splitLine: { show: false } }],
    series: [
      { name: '库存', type: 'bar', data: (this.analytics().warehouse_turnover ?? []).map(item => item.stock_quantity), barWidth: 18, itemStyle: { color: '#7b8fff', borderRadius: [9, 9, 2, 2] } },
      { name: '流水', type: 'line', yAxisIndex: 1, smooth: true, data: (this.analytics().warehouse_turnover ?? []).map(item => item.movement_count), lineStyle: { width: 3, color: '#2ca59d' } }
    ]
  }));

  protected readonly customerChart = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'axis' },
    grid: { left: 18, right: 18, top: 24, bottom: 18, containLabel: true },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
    yAxis: { type: 'category', data: (this.analytics().top_customers ?? []).map(item => item.name), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { width: 110, overflow: 'truncate' } },
    series: [{ type: 'bar', data: (this.analytics().top_customers ?? []).map(item => item.value), barWidth: 14, itemStyle: { color: '#58b883', borderRadius: 8 } }]
  }));

  protected readonly throughputChart = computed<EChartsCoreOption>(() => {
    const rows = this.analytics().module_throughput?.length ? this.analytics().module_throughput! : [
      { name: '库存', todo: 0, done: 1, blocked: 0 },
      { name: '采购', todo: 0, done: 1, blocked: 0 },
      { name: '履约', todo: 0, done: 1, blocked: 0 },
      { name: '财务', todo: 0, done: 1, blocked: 0 },
      { name: '协作', todo: 0, done: 1, blocked: 0 }
    ];
    return {
      tooltip: { trigger: 'axis' },
      legend: chartLegend('bottom', 'rgba(100,116,139,.95)'),
      radar: {
        radius: '64%',
        indicator: rows.map(item => ({ name: item.name, max: Math.max(item.todo, item.done, item.blocked, 10) + 6 }))
      },
      series: [{
        type: 'radar',
        data: [
          { name: '待办', value: rows.map(item => item.todo), areaStyle: { color: 'rgba(217,145,53,.18)' }, lineStyle: { color: '#d99135' } },
          { name: '完成', value: rows.map(item => item.done), areaStyle: { color: 'rgba(44,165,157,.18)' }, lineStyle: { color: '#2ca59d' } }
        ]
      }]
    };
  });

  protected readonly riskChart = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'item' },
    legend: chartLegend('bottom', 'rgba(100,116,139,.95)'),
    series: [{
      type: 'pie',
      radius: ['46%', '72%'],
      center: ['50%', '42%'],
      itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.48)' },
      data: this.analytics().risk_mix
    }]
  }));

  protected efficiencyPath(name: string): string {
    if (name.includes('采购')) return '/app/procurement/orders';
    if (name.includes('库存')) return '/app/inventory/stock';
    if (name.includes('回款')) return '/app/finance/receivables';
    if (name.includes('协作')) return '/app/notifications';
    return '/app/sales/orders';
  }

  protected cleanPath(path: string): string {
    return (path || '/app/overview').split('?')[0];
  }

  protected compactMoney(value: unknown): string {
    return compactMoneyText(value);
  }

  protected compactNumber(value: unknown): string {
    return compactNumberText(value);
  }
}
