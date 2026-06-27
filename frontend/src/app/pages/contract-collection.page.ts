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
import { chartLegend, compactMoneyText, emptyPageResult, moneyText, numberOf, percentNumber, recordTitle, statusLabel, statusSeverity, textOf } from './page-utils';

const EMPTY_ANALYTICS: ExecutiveAnalytics = {
  kpis: { total_sales: 0, unpaid_amount: 0, pending_purchase: 0, active_alerts: 0, collaboration_items: 0 },
  sales_trend: [],
  risk_mix: [],
  collaboration: [],
  aging_buckets: [],
  cash_collection_trend: [],
  top_customers: []
};

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page contract-collection-page">
      <header class="contract-hero atlas-split-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">合同回款</span>
          <h1>合同回款中心</h1>
          <p>合同节点、应收账龄、客户信用、催款任务和回款趋势在同一视图联动。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="createReviewTask()" [loading]="taskCreating()" aria-label="创建合同回款任务">
              <i class="pi pi-briefcase"></i>
              创建回款任务
            </button>
            <button pButton type="button" severity="secondary" (click)="generateReport()" [loading]="reporting()" aria-label="生成合同回款报表">
              <i class="pi pi-chart-line"></i>
              生成回款报表
            </button>
            <a pButton severity="info" routerLink="/app/finance/receivables">
              <i class="pi pi-wallet"></i>
              应收风控
            </a>
          </div>
        </div>

        <div class="contract-kpi-grid">
          <article>
            <span>合同应收</span>
            <strong>{{ compactMoney(totalReceivable()) }}</strong>
            <em>{{ receivables().length }} 笔</em>
          </article>
          <article>
            <span>已收金额</span>
            <strong>{{ compactMoney(paidAmount()) }}</strong>
            <em>回款入账</em>
          </article>
          <article>
            <span>未收金额</span>
            <strong>{{ compactMoney(unpaidAmount()) }}</strong>
            <em>待跟进</em>
          </article>
          <article>
            <span>回款率</span>
            <strong>{{ collectionRate() }}%</strong>
            <em>按合同金额</em>
          </article>
        </div>

        <aside class="contract-score-card">
          <span>现金流健康</span>
          <strong>{{ cashHealth() }}%</strong>
          <p-progressbar [value]="cashHealth()" [showValue]="false" />
          <em>{{ overdueRows().length }} 笔逾期 · {{ credits().filter(isFrozen).length }} 个冻结客户</em>
        </aside>
      </header>

      <section class="contract-grid">
        <article class="atlas-panel contract-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">回款分析</span>
              <h2>{{ chartTitle() }}</h2>
            </div>
            <div class="chart-tabs">
              <button type="button" [class.active]="chartMode() === 'aging'" (click)="chartMode.set('aging')">账龄</button>
              <button type="button" [class.active]="chartMode() === 'cash'" (click)="chartMode.set('cash')">趋势</button>
              <button type="button" [class.active]="chartMode() === 'customer'" (click)="chartMode.set('customer')">客户</button>
            </div>
          </div>
          <div class="contract-chart" echarts [options]="activeChart()"></div>
        </article>

        <aside class="atlas-panel contract-action-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">催收队列</span>
              <h2>回款动作队列</h2>
            </div>
          </div>
          @for (item of actionQueue(); track item.title) {
            <a class="business-data-row" [routerLink]="item.path" [class.warning]="item.tone === 'warning'">
              <span>{{ item.metric }}</span>
              <strong>{{ item.title }}</strong>
              <em>{{ item.body }}</em>
            </a>
          }
        </aside>

        <article class="atlas-panel contract-ledger-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">合同账本</span>
              <h2>合同回款账本</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="setQuery($event)" placeholder="搜索应收单、客户、状态" />
            </div>
            <button pButton type="button" [text]="true" (click)="load()" aria-label="刷新合同回款数据">
              <i class="pi pi-refresh"></i>
            </button>
          </div>

          @if (loading()) {
            <p-skeleton height="76px" />
            <p-skeleton height="76px" />
            <p-skeleton height="76px" />
          } @else {
            <div class="atlas-record-ledger">
              @for (row of pagedReceivables(); track row.id) {
                <a class="atlas-record-row" [routerLink]="['/app/finance/receivables', row.id]" [class.warning]="number(row, 'overdue_days') > 0">
                  <span class="record-code">{{ text(row, 'receivable_no') }}</span>
                  <strong>{{ text(row, 'customer_name', '未关联客户') }}</strong>
                  <em>未收 {{ money(row['unpaid_amount']) }} / 逾期 {{ number(row, 'overdue_days') }} 天</em>
                  <b>{{ money(row['total_amount']) }}</b>
                  <p-tag [severity]="severity(row['status'])" [value]="status(row['status'])" />
                </a>
              }
            </div>
            <div class="atlas-pagination" aria-label="合同回款分页">
              <button type="button" (click)="setPage(page() - 1)" [disabled]="page() <= 1" aria-label="上一页">
                <i class="pi pi-angle-left"></i>
              </button>
              <span>{{ page() }} / {{ totalPages() }}</span>
              <label>
                <em>跳至</em>
                <input pInputText [ngModel]="pageInput" (ngModelChange)="pageInput = $event" (keydown.enter)="jumpPage()" />
              </label>
              <button type="button" (click)="jumpPage()">跳转</button>
              <button type="button" (click)="setPage(page() + 1)" [disabled]="page() >= totalPages()" aria-label="下一页">
                <i class="pi pi-angle-right"></i>
              </button>
            </div>
          }
        </article>
      </section>
    </section>
  `
})
export class ContractCollectionPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly taskCreating = signal(false);
  protected readonly reporting = signal(false);
  protected readonly receivables = signal<DataRecord[]>([]);
  protected readonly credits = signal<DataRecord[]>([]);
  protected readonly analytics = signal<ExecutiveAnalytics>(EMPTY_ANALYTICS);
  protected readonly chartMode = signal<'aging' | 'cash' | 'customer'>('aging');
  protected readonly page = signal(1);
  protected readonly pageSize = signal(8);
  protected query = '';
  protected pageInput = '1';
  protected readonly isFrozen = (row: DataRecord) => row['is_frozen'] === true || row['is_frozen'] === 'true';

  protected readonly totalReceivable = computed(() => this.receivables().reduce((sum, row) => sum + numberOf(row, 'total_amount'), 0));
  protected readonly paidAmount = computed(() => this.receivables().reduce((sum, row) => sum + numberOf(row, 'paid_amount'), 0));
  protected readonly unpaidAmount = computed(() => this.receivables().reduce((sum, row) => sum + numberOf(row, 'unpaid_amount'), 0));
  protected readonly collectionRate = computed(() => percentNumber((this.paidAmount() / Math.max(this.totalReceivable(), 1)) * 100));
  protected readonly overdueRows = computed(() => this.receivables().filter(row => numberOf(row, 'overdue_days') > 0 || ['overdue', 'bad_debt'].includes(String(row['status'] ?? ''))));
  protected readonly cashHealth = computed(() => percentNumber(92 - this.overdueRows().length * 3 - this.credits().filter(this.isFrozen).length * 5 + Math.round(this.collectionRate() / 12)));
  protected readonly filteredReceivables = computed(() => {
    const q = this.query.trim().toLowerCase();
    if (!q) {
      return this.receivables();
    }
    return this.receivables().filter(row => [textOf(row, 'receivable_no'), textOf(row, 'customer_name'), statusLabel(row['status'])].join(' ').toLowerCase().includes(q));
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.filteredReceivables().length / this.pageSize())));
  protected readonly pagedReceivables = computed(() => {
    const safePage = Math.min(this.page(), this.totalPages());
    const start = (safePage - 1) * this.pageSize();
    return this.filteredReceivables().slice(start, start + this.pageSize());
  });
  protected readonly actionQueue = computed(() => [
    { title: '逾期合同复核', metric: `${this.overdueRows().length} 笔`, body: '生成催款与信用控制动作', path: '/app/finance/receivables', tone: 'warning' },
    { title: '信用冻结客户', metric: `${this.credits().filter(this.isFrozen).length} 个`, body: '复核冻结原因与解除条件', path: '/app/finance/credits', tone: 'warning' },
    { title: '经营报表归档', metric: `${this.collectionRate()}%`, body: '输出合同回款报表', path: '/app/reports', tone: 'success' }
  ]);
  protected readonly chartTitle = computed(() => this.chartMode() === 'aging' ? '应收账龄结构' : this.chartMode() === 'cash' ? '销售与回款趋势' : '客户未收金额排行');
  protected readonly activeChart = computed(() => this.chartMode() === 'cash' ? this.cashChart() : this.chartMode() === 'customer' ? this.customerChart() : this.agingChart());

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      receivables: this.api.list<DataRecord>('receivables', { page: 1, page_size: 24 }).pipe(catchError(() => of(emptyPageResult<DataRecord>()))),
      credits: this.api.list<DataRecord>('credits', { page: 1, page_size: 24 }).pipe(catchError(() => of(emptyPageResult<DataRecord>())))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(result => {
      this.receivables.set(result.receivables.items);
      this.credits.set(result.credits.items);
      this.setPage(1);
    });
    this.api.get<ExecutiveAnalytics>('analytics/executive').pipe(
      catchError(() => of(EMPTY_ANALYTICS))
    ).subscribe(analytics => {
      this.analytics.set(analytics);
    });
  }

  createReviewTask(): void {
    const row = this.overdueRows()[0] ?? this.filteredReceivables()[0] ?? this.receivables()[0];
    this.taskCreating.set(true);
    this.api.post('operations/contract-review', {
      receivable_id: row?.id,
      title: `合同回款复核 - ${textOf(row, 'customer_name', recordTitle(row))}`,
      content: `请复核 ${recordTitle(row)} 合同节点、未收金额 ${moneyText(row?.['unpaid_amount'])} 和回款承诺。`,
      type: numberOf(row, 'overdue_days') > 0 ? 'warning' : 'info'
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '回款任务未创建', detail: error?.message || '任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.taskCreating.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '回款任务已创建', detail: '任务已进入通知中心。' });
      }
    });
  }

  generateReport(): void {
    this.reporting.set(true);
    this.api.post('reports/generate/contract_collection', { params: {} }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '回款报表未生成', detail: error?.message || '报表服务未返回结果。' });
        return of(null);
      }),
      finalize(() => this.reporting.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '回款报表已生成', detail: '已进入报表归档。' });
      }
    });
  }

  setQuery(value: string): void {
    this.query = value;
    this.setPage(1);
  }

  setPage(value: number): void {
    const next = Math.min(Math.max(1, Math.trunc(value || 1)), this.totalPages());
    this.page.set(next);
    this.pageInput = String(next);
  }

  jumpPage(): void {
    this.setPage(Number(this.pageInput));
  }

  protected agingChart() {
    const buckets = this.analytics().aging_buckets?.length ? this.analytics().aging_buckets : this.buildAging();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom'),
      series: [{ type: 'pie', radius: ['45%', '72%'], center: ['50%', '43%'], itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.5)' }, data: buckets }]
    };
  }

  protected cashChart() {
    const sales = this.analytics().sales_trend ?? [];
    const cash = this.analytics().cash_collection_trend ?? [];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top'),
      dataZoom: [{ type: 'inside' }],
      grid: { left: 24, right: 18, top: 42, bottom: 30, containLabel: true },
      xAxis: { type: 'category', data: sales.map(item => item.name), boundaryGap: false, axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [
        { name: '销售', type: 'line', smooth: true, data: sales.map(item => item.value), lineStyle: { color: '#8da2ff', width: 3 }, areaStyle: { color: 'rgba(141,162,255,.12)' }, symbolSize: 5 },
        { name: '回款', type: 'line', smooth: true, data: cash.map(item => item.value), lineStyle: { color: '#55c7a6', width: 3 }, areaStyle: { color: 'rgba(85,199,166,.14)' }, symbolSize: 5 }
      ]
    };
  }

  protected customerChart() {
    const rows = this.groupByCustomer().slice(0, 10);
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 24, right: 18, top: 28, bottom: 28, containLabel: true },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      yAxis: { type: 'category', data: rows.map(item => item.name), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { width: 110, overflow: 'truncate' } },
      series: [{ type: 'bar', data: rows.map(item => item.value), barWidth: 16, itemStyle: { color: '#ff8fa3', borderRadius: [0, 9, 9, 0] } }]
    };
  }

  private buildAging(): Array<{ name: string; value: number }> {
    const buckets = new Map<string, number>([['未到期', 0], ['1-30天', 0], ['31-60天', 0], ['60天以上', 0]]);
    for (const row of this.receivables()) {
      const days = numberOf(row, 'overdue_days');
      const key = days <= 0 ? '未到期' : days <= 30 ? '1-30天' : days <= 60 ? '31-60天' : '60天以上';
      buckets.set(key, (buckets.get(key) ?? 0) + numberOf(row, 'unpaid_amount'));
    }
    return [...buckets.entries()].map(([name, value]) => ({ name, value: Math.max(1, value) }));
  }

  private groupByCustomer(): Array<{ name: string; value: number }> {
    const map = new Map<string, number>();
    for (const row of this.receivables()) {
      const key = textOf(row, 'customer_name', '未关联客户');
      map.set(key, (map.get(key) ?? 0) + numberOf(row, 'unpaid_amount'));
    }
    return [...map.entries()].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
  }

  protected text(row: DataRecord, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  protected number(row: DataRecord, key: string): number {
    return numberOf(row, key);
  }

  protected money(value: unknown): string {
    return moneyText(value);
  }

  protected compactMoney(value: unknown): string {
    return compactMoneyText(value);
  }

  protected status(value: unknown): string {
    return statusLabel(value);
  }

  protected severity(value: unknown): 'success' | 'secondary' | 'info' | 'warn' | 'danger' | 'contrast' {
    return statusSeverity(value);
  }
}
