import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { NgxEchartsDirective } from 'ngx-echarts';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { ProgressBarModule } from 'primeng/progressbar';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, forkJoin, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DataRecord, ExecutiveAnalytics } from '../core/models';
import { chartLegend, compactMoneyText, emptyPageResult, moneyText, numberOf, percentNumber, recordTitle, textOf } from './page-utils';

const EMPTY_ANALYTICS: ExecutiveAnalytics = {
  kpis: { total_sales: 0, unpaid_amount: 0, pending_purchase: 0, active_alerts: 0, collaboration_items: 0 },
  sales_trend: [],
  risk_mix: [],
  collaboration: []
};

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page customer-ops-page">
      <header class="customer-hero atlas-split-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">客户运营</span>
          <h1>客户经营中心</h1>
          <p>客户主数据、订单贡献、应收风险、信用评分和协作跟进合并为一张经营视图。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="createFollowup()" [loading]="followupCreating()" aria-label="创建客户跟进任务">
              <i class="pi pi-bell"></i>
              创建跟进任务
            </button>
            <button pButton type="button" severity="secondary" (click)="generateReport()" [loading]="reporting()" aria-label="生成客户经营报表">
              <i class="pi pi-chart-line"></i>
              生成客户报表
            </button>
            <a pButton severity="info" routerLink="/app/finance/receivables">
              <i class="pi pi-wallet"></i>
              应收风控
            </a>
          </div>
        </div>

        <div class="customer-score-grid">
          <article>
            <span>客户数</span>
            <strong>{{ customers().length }}</strong>
            <em>主数据档案</em>
          </article>
          <article>
            <span>订单金额</span>
            <strong>{{ compactMoney(analytics().kpis.total_sales) }}</strong>
            <em>销售贡献</em>
          </article>
          <article>
            <span>未收金额</span>
            <strong>{{ compactMoney(analytics().kpis.unpaid_amount) }}</strong>
            <em>应收风险</em>
          </article>
          <article>
            <span>平均信用</span>
            <strong>{{ avgCreditScore() }}</strong>
            <em>客户评分</em>
          </article>
        </div>

        <aside class="customer-radar-card">
          <span>客户健康雷达</span>
          <div class="customer-radar" echarts [options]="radarChart()"></div>
        </aside>
      </header>

      <section class="customer-ops-grid">
        <article class="atlas-panel customer-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">客户组合</span>
              <h2>客户贡献与风险</h2>
            </div>
            <div class="chart-tabs">
              <button type="button" [class.active]="chartMode() === 'value'" (click)="chartMode.set('value')">贡献</button>
              <button type="button" [class.active]="chartMode() === 'risk'" (click)="chartMode.set('risk')">风险</button>
              <button type="button" [class.active]="chartMode() === 'trend'" (click)="chartMode.set('trend')">趋势</button>
            </div>
          </div>
          <div class="customer-chart" echarts [options]="activeChart()"></div>
        </article>

        <aside class="atlas-panel customer-action-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">行动队列</span>
              <h2>客户跟进行动</h2>
            </div>
          </div>
          @for (item of actionQueue(); track item.title) {
            <a [routerLink]="item.path" [class.warning]="item.tone === 'warning'">
              <span>{{ item.kicker }}</span>
              <strong>{{ item.title }}</strong>
              <em>{{ item.body }}</em>
            </a>
          }
        </aside>

        <article class="atlas-panel customer-ledger-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">客户账本</span>
              <h2>客户经营账本</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="query = $event" placeholder="搜索客户、联系人、电话、邮箱" />
            </div>
            <button pButton type="button" [text]="true" (click)="load()" aria-label="刷新客户数据">
              <i class="pi pi-refresh"></i>
            </button>
          </div>

          @if (loading()) {
            <p-skeleton height="76px" />
            <p-skeleton height="76px" />
            <p-skeleton height="76px" />
          } @else {
            <div class="atlas-record-ledger">
              @for (row of visibleCustomers(); track row.id) {
                <a class="atlas-record-row" [routerLink]="['/app/customers', row.id]">
                  <span class="record-code">{{ text(row, 'credit_score') }}</span>
                  <strong>{{ recordName(row) }}</strong>
                  <em>{{ text(row, 'contact_person', '未维护联系人') }} / {{ text(row, 'phone', '未维护电话') }}</em>
                  <b>{{ customerRiskLabel(row) }}</b>
                  <p-tag [severity]="customerRiskSeverity(row)" [value]="customerRiskLabel(row)" />
                </a>
              }
            </div>
          }
        </article>
      </section>
    </section>
  `
})
export class CustomerOperationsPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly followupCreating = signal(false);
  protected readonly reporting = signal(false);
  protected readonly customers = signal<DataRecord[]>([]);
  protected readonly receivables = signal<DataRecord[]>([]);
  protected readonly analytics = signal<ExecutiveAnalytics>(EMPTY_ANALYTICS);
  protected readonly chartMode = signal<'value' | 'risk' | 'trend'>('value');
  protected query = '';

  protected readonly visibleCustomers = computed(() => {
    const q = this.query.trim().toLowerCase();
    return this.customers().filter(row => {
      const haystack = [textOf(row, 'name'), textOf(row, 'contact_person'), textOf(row, 'phone'), textOf(row, 'email')].join(' ').toLowerCase();
      return !q || haystack.includes(q);
    });
  });
  protected readonly avgCreditScore = computed(() => {
    const rows = this.customers();
    if (!rows.length) {
      return 0;
    }
    return Math.round(rows.reduce((sum, row) => sum + numberOf(row, 'credit_score'), 0) / rows.length);
  });
  protected readonly overdueCount = computed(() => this.receivables().filter(row => numberOf(row, 'overdue_days') > 0 || ['overdue', 'bad_debt'].includes(String(row['status'] ?? ''))).length);
  protected readonly activeChart = computed(() => {
    if (this.chartMode() === 'risk') {
      return this.riskChart();
    }
    if (this.chartMode() === 'trend') {
      return this.trendChart();
    }
    return this.valueChart();
  });
  protected readonly actionQueue = computed(() => [
    { kicker: `${this.overdueCount()} 项`, title: '逾期客户跟进', body: '进入应收风控处理账龄与催款', path: '/app/finance/receivables', tone: 'warning' },
    { kicker: `${this.analytics().top_customers?.length ?? 0} 家`, title: '高价值客户复核', body: '复核订单贡献和履约窗口', path: '/app/sales/orders', tone: 'success' },
    { kicker: `${this.customers().length} 档`, title: '客户主数据治理', body: '补齐联系人、电话、地址和信用评分', path: '/app/data-quality', tone: 'warning' }
  ]);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      customers: this.api.list<DataRecord>('partners', { page: 1, page_size: 140, type: 'customer' }).pipe(catchError(() => of(emptyPageResult<DataRecord>()))),
      receivables: this.api.list<DataRecord>('receivables', { page: 1, page_size: 140 }).pipe(catchError(() => of(emptyPageResult<DataRecord>()))),
      analytics: this.api.get<ExecutiveAnalytics>('analytics/executive').pipe(catchError(() => of(EMPTY_ANALYTICS)))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(result => {
      this.customers.set(result.customers.items);
      this.receivables.set(result.receivables.items);
      this.analytics.set(result.analytics);
    });
  }

  createFollowup(): void {
    const customer = this.visibleCustomers()[0] ?? this.customers()[0];
    this.followupCreating.set(true);
    this.api.post('operations/customer-followup', {
      customer_id: customer?.id,
      title: `客户经营跟进 - ${recordTitle(customer)}`,
      content: '请复核客户订单履约、应收账龄、信用占用和近期协作记录。',
      type: this.customerRiskSeverity(customer) === 'danger' ? 'alert' : 'warning'
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '跟进任务未创建', detail: error?.message || '通知任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.followupCreating.set(false))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '客户跟进已创建', detail: '任务已进入通知中心。' });
      }
    });
  }

  generateReport(): void {
    this.reporting.set(true);
    this.api.post('reports/generate/customer_operations', { params: {} }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '客户报表未生成', detail: error?.message || '报表服务未返回结果。' });
        return of(null);
      }),
      finalize(() => this.reporting.set(false))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '客户报表已生成', detail: '已进入报表归档。' });
      }
    });
  }

  protected valueChart() {
    const data = this.analytics().top_customers ?? [];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 18, right: 20, top: 24, bottom: 20, containLabel: true },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      yAxis: { type: 'category', data: data.map(item => item.name), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { width: 110, overflow: 'truncate' } },
      series: [{ type: 'bar', data: data.map(item => item.value), barWidth: 16, itemStyle: { color: '#5fa8ff', borderRadius: [0, 9, 9, 0] } }]
    };
  }

  protected riskChart() {
    const risk = [
      { name: '逾期应收', value: this.overdueCount() },
      { name: '低信用评分', value: this.customers().filter(row => numberOf(row, 'credit_score') < 75).length },
      { name: '资料缺失', value: this.customers().filter(row => !textOf(row, 'phone', '') || !textOf(row, 'contact_person', '')).length }
    ];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom'),
      series: [{ type: 'pie', radius: ['46%', '72%'], center: ['50%', '43%'], itemStyle: { borderRadius: 10, borderColor: 'rgba(255,255,255,.5)', borderWidth: 2 }, data: risk }]
    };
  }

  protected trendChart() {
    const trend = this.analytics().sales_trend;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      dataZoom: [{ type: 'inside' }],
      grid: { left: 24, right: 18, top: 28, bottom: 28, containLabel: true },
      xAxis: { type: 'category', data: trend.map(item => item.name), boundaryGap: false, axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [{ type: 'line', smooth: true, data: trend.map(item => item.value), lineStyle: { width: 3, color: '#62d8cb' }, areaStyle: { color: 'rgba(98,216,203,.16)' }, symbolSize: 5 }]
    };
  }

  protected radarChart() {
    return {
      backgroundColor: 'transparent',
      radar: {
        radius: '64%',
        indicator: [
          { name: '信用', max: 100 },
          { name: '回款', max: 100 },
          { name: '贡献', max: 100 },
          { name: '资料', max: 100 }
        ]
      },
      series: [{
        type: 'radar',
        areaStyle: { color: 'rgba(95,168,255,.2)' },
        lineStyle: { color: '#5fa8ff', width: 3 },
        data: [{ value: [this.avgCreditScore(), 100 - Math.min(80, this.overdueCount() * 6), Math.min(100, (this.analytics().top_customers?.length ?? 0) * 12), this.profileCoverage()] }]
      }]
    };
  }

  protected profileCoverage(): number {
    const rows = this.customers();
    if (!rows.length) {
      return 0;
    }
    const complete = rows.filter(row => textOf(row, 'contact_person', '') && textOf(row, 'phone', '') && textOf(row, 'email', '')).length;
    return percentNumber((complete / rows.length) * 100);
  }

  protected customerRiskLabel(row?: DataRecord): string {
    const score = numberOf(row, 'credit_score');
    if (score < 70) {
      return '高风险';
    }
    if (score < 85) {
      return '观察';
    }
    return '稳定';
  }

  protected customerRiskSeverity(row?: DataRecord): 'success' | 'warn' | 'danger' {
    const score = numberOf(row, 'credit_score');
    return score < 70 ? 'danger' : score < 85 ? 'warn' : 'success';
  }

  protected compactMoney(value: unknown): string {
    return compactMoneyText(value);
  }

  protected money(value: unknown): string {
    return moneyText(value);
  }

  protected text(row: DataRecord, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  protected recordName(row: DataRecord): string {
    return recordTitle(row);
  }
}
