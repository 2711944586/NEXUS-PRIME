import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { ConfirmationService, MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { ProgressBarModule } from 'primeng/progressbar';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';
import { catchError, finalize, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DataRecord } from '../core/models';
import { chartLegend, compactMoneyText, dateText, emptyPageResult, moneyText, numberOf, percentNumber, recordTitle, statusLabel, statusSeverity, textOf } from './page-utils';

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule, TooltipModule],
  template: `
    <section class="ops-atlas-page receivable-atlas">
      <header class="atlas-split-hero receivable-atlas-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">应收风控</span>
          <h1>账龄风险墙与收款作业台</h1>
          <p>账龄、客户信用、催款提醒和收款回写统一展示。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="recordNextPayment()" aria-label="记录下一笔收款">
              <i class="pi pi-wallet"></i>
              记录收款
            </button>
            <button pButton type="button" severity="warn" (click)="sendReminder()" aria-label="发送催款提醒">
              <i class="pi pi-bell"></i>
              发送催款
            </button>
            <a pButton severity="secondary" routerLink="/app/finance/credits">
              <i class="pi pi-shield"></i>
              信用管理
            </a>
          </div>
        </div>

        <div class="aging-wall" aria-label="账龄风险墙">
          @for (bucket of agingBuckets(); track bucket.label) {
            <button type="button" [class.active]="agingFilter() === bucket.key" [class.danger]="bucket.tone === 'danger'" [class.warn]="bucket.tone === 'warn'" (click)="setAgingFilter(bucket.key)">
              <span>{{ bucket.label }}</span>
              <strong>{{ compactMoney(bucket.amount) }}</strong>
              <p-progressbar [value]="bucket.percent" [showValue]="false" />
            </button>
          }
        </div>

        <aside class="cash-score-tower">
          <div><span>应收总额</span><strong>{{ compactMoney(totalAmount()) }}</strong></div>
          <div><span>未收金额</span><strong>{{ compactMoney(unpaidAmount()) }}</strong></div>
          <div><span>逾期客户</span><strong>{{ overdueRows().length }}</strong></div>
          <div><span>回款率</span><strong>{{ collectionRate() }}%</strong></div>
        </aside>
      </header>

      <section class="receivable-risk-grid">
        <article class="atlas-panel collection-column">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">催收队列</span>
              <h2>催收优先队列</h2>
            </div>
            <button pButton type="button" [text]="true" (click)="load()" aria-label="刷新应收数据" pTooltip="刷新应收数据">
              <i class="pi pi-refresh"></i>
            </button>
          </div>
          @if (loading()) {
            <p-skeleton height="82px" />
            <p-skeleton height="82px" />
            <p-skeleton height="82px" />
          } @else {
            @for (row of overdueRows().slice(0, 6); track row.id) {
              <a class="collection-workcard" [routerLink]="['/app/finance/receivables', row.id]">
                <p-tag severity="danger" [value]="text(row, 'age_bucket', '逾期')" />
                <strong>{{ text(row, 'customer_name') }}</strong>
                <span>{{ text(row, 'receivable_no') }} / 逾期 {{ num(row, 'overdue_days') }} 天</span>
                <b>{{ money(row['unpaid_amount']) }}</b>
              </a>
            }
            @if (!overdueRows().length) {
              <div class="collection-workcard calm">
                <p-tag severity="success" value="无逾期" />
                <strong>当前无逾期应收</strong>
                <span>继续复核未收金额和客户额度占用。</span>
              </div>
            }
          }
          <div class="collection-summary-grid" aria-label="账龄摘要">
            @for (bucket of agingBuckets(); track bucket.key) {
              <button type="button" [class.active]="agingFilter() === bucket.key" (click)="setAgingFilter(bucket.key)">
                <span>{{ bucket.label }}</span>
                <strong>{{ compactMoney(bucket.amount) }}</strong>
                <em>{{ bucket.percent }}%</em>
              </button>
            }
          </div>
        </article>

        <article class="atlas-panel cashflow-column">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">回款</span>
              <h2>回款进度</h2>
            </div>
          </div>
          <div class="cashflow-ladder">
            @for (row of visibleRows().slice(0, 8); track row.id) {
              <a [routerLink]="['/app/finance/receivables', row.id]" [class.warning]="isOverdue(row)">
                <span>{{ text(row, 'customer_name') }}</span>
                <p-progressbar [value]="paidPercent(row)" [showValue]="false" />
                <strong>{{ paidPercent(row) }}%</strong>
              </a>
            }
          </div>
        </article>

        <aside class="atlas-panel credit-meter-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">信用压力</span>
              <h2>信用占用</h2>
            </div>
          </div>
          <div class="credit-pressure-meter">
            <strong>{{ collectionRate() }}%</strong>
            <span>回款率</span>
          </div>
          <a routerLink="/app/finance/credits">查看客户信用额度、冻结与解冻状态</a>
        </aside>
      </section>

      <section class="atlas-panel receivable-intelligence-panel">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">应收图表</span>
            <h2>{{ receivableChartTitle() }}</h2>
          </div>
          <div class="metric-mode-switch" aria-label="应收图表模式">
            @for (mode of receivableChartModes; track mode.key) {
              <button type="button" [class.active]="chartMode() === mode.key" (click)="chartMode.set(mode.key)">
                <i class="pi" [class]="mode.icon"></i>
                {{ mode.label }}
              </button>
            }
          </div>
        </div>
        <div class="ops-chart-split">
          <div class="ops-chart-large" echarts [options]="activeReceivableChart()"></div>
          <aside class="ops-chart-insights">
            @for (item of receivableInsights(); track item.kicker) {
              <button type="button" (click)="setAgingFilter(item.filter)">
                <span>{{ item.kicker }}</span>
                <strong>{{ item.title }}</strong>
                <em>{{ item.value }}</em>
              </button>
            }
          </aside>
        </div>
      </section>

      <section class="atlas-panel receivable-ledger-panel">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">应收账本</span>
            <h2>应收账本</h2>
          </div>
          <div class="atlas-filter">
            <i class="pi pi-search"></i>
            <input pInputText [(ngModel)]="query" placeholder="搜索应收单、客户、状态" />
          </div>
          <button type="button" [class.active]="statusFilter() === ''" (click)="statusFilter.set('')">全部状态</button>
          <button type="button" [class.active]="agingFilter() === ''" (click)="setAgingFilter('')">全部账龄</button>
        </div>

        @if (error()) {
          <div class="empty-state">
            <i class="pi pi-cloud"></i>
            <strong>应收数据通道未连接</strong>
            <p>{{ error() }}</p>
            <button pButton type="button" (click)="load()">重试</button>
          </div>
        } @else {
          <div class="atlas-record-ledger">
            @for (row of pagedRows(); track row.id) {
              <a class="atlas-record-row" [routerLink]="['/app/finance/receivables', row.id]" [class.warning]="isOverdue(row)">
                <span class="record-code">{{ text(row, 'receivable_no') }}</span>
                <strong>{{ text(row, 'customer_name') }}</strong>
                <em>{{ date(row['due_date']) }} / 已收 {{ money(row['paid_amount']) }}</em>
                <b>{{ money(row['unpaid_amount']) }}</b>
                <p-tag [severity]="severity(row['status'])" [value]="status(row['status'])" />
              </a>
            }
          </div>
          @if (visibleRows().length > pageSize()) {
            <div class="atlas-pagination" aria-label="应收账本分页">
              <button type="button" (click)="setPage(currentPage() - 1)" [disabled]="currentPage() <= 1">
                <i class="pi pi-angle-left"></i>
                上一页
              </button>
              <span>第 <strong>{{ currentPage() }}</strong> / {{ totalPages() }} 页 · {{ visibleRows().length }} 笔</span>
              <label>
                跳至
                <input pInputText [ngModel]="pageInput" (ngModelChange)="pageInput = $event" (keydown.enter)="jumpPage()" inputmode="numeric" />
              </label>
              <button type="button" (click)="jumpPage()">跳转</button>
              <button type="button" (click)="setPage(currentPage() + 1)" [disabled]="currentPage() >= totalPages()">
                下一页
                <i class="pi pi-angle-right"></i>
              </button>
            </div>
          }
        }
      </section>
    </section>
  `
})
export class ReceivablesPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);
  private readonly confirm = inject(ConfirmationService);

  protected readonly rows = signal<DataRecord[]>([]);
  protected readonly loading = signal(false);
  protected readonly error = signal('');
  protected readonly statusFilter = signal('');
  protected readonly agingFilter = signal('');
  protected readonly chartMode = signal<'aging' | 'cash' | 'customer'>('aging');
  protected readonly pageSize = signal(12);
  protected readonly page = signal(1);
  protected pageInput = '1';
  protected query = '';
  protected readonly receivableChartModes = [
    { key: 'aging' as const, label: '账龄', icon: 'pi-chart-pie' },
    { key: 'cash' as const, label: '回款', icon: 'pi-chart-line' },
    { key: 'customer' as const, label: '客户', icon: 'pi-users' }
  ];

  protected readonly visibleRows = computed(() => {
    const q = this.query.trim().toLowerCase();
    const status = this.statusFilter();
    return this.rows().filter(row => {
      const rowStatus = String(row['status'] ?? '');
      const haystack = [textOf(row, 'receivable_no'), textOf(row, 'customer_name'), rowStatus].join(' ').toLowerCase();
      return (!status || rowStatus === status) && this.matchesAging(row) && (!q || haystack.includes(q));
    });
  });
  protected readonly overdueRows = computed(() => this.rows().filter(row => this.isOverdue(row)).sort((a, b) => numberOf(b, 'overdue_days') - numberOf(a, 'overdue_days')));
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.visibleRows().length / this.pageSize())));
  protected readonly currentPage = computed(() => Math.min(this.page(), this.totalPages()));
  protected readonly pagedRows = computed(() => {
    const start = (this.currentPage() - 1) * this.pageSize();
    return this.visibleRows().slice(start, start + this.pageSize());
  });
  protected readonly totalAmount = computed(() => this.rows().reduce((sum, row) => sum + numberOf(row, 'total_amount'), 0));
  protected readonly paidAmount = computed(() => this.rows().reduce((sum, row) => sum + numberOf(row, 'paid_amount'), 0));
  protected readonly unpaidAmount = computed(() => this.rows().reduce((sum, row) => sum + numberOf(row, 'unpaid_amount'), 0));
  protected readonly collectionRate = computed(() => percentNumber((this.paidAmount() / Math.max(this.totalAmount(), 1)) * 100));
  protected readonly receivableChartTitle = computed(() => {
    if (this.chartMode() === 'cash') {
      return '回款与未收对比';
    }
    if (this.chartMode() === 'customer') {
      return '客户未收金额排行';
    }
    return '账龄风险分布';
  });
  protected readonly receivableInsights = computed(() => [
    { kicker: '未到期', title: this.compactMoney(this.agingBuckets().find(item => item.key === 'current')?.amount ?? 0), value: '正常跟进', filter: 'current' },
    { kicker: '1-30天', title: this.compactMoney(this.agingBuckets().find(item => item.key === '1-30')?.amount ?? 0), value: '需要催款提醒', filter: '1-30' },
    { kicker: '60天以上', title: this.compactMoney(this.agingBuckets().find(item => item.key === '60+')?.amount ?? 0), value: '建议信用冻结复核', filter: '60+' },
    { kicker: '回款率', title: `${this.collectionRate()}%`, value: '收款后释放信用占用', filter: '' }
  ]);
  protected readonly agingBuckets = computed(() => {
    const rows = this.rows();
    const total = Math.max(this.totalAmount(), 1);
    const current = rows.filter(row => numberOf(row, 'overdue_days') <= 0).reduce((sum, row) => sum + numberOf(row, 'unpaid_amount'), 0);
    const short = rows.filter(row => numberOf(row, 'overdue_days') > 0 && numberOf(row, 'overdue_days') <= 30).reduce((sum, row) => sum + numberOf(row, 'unpaid_amount'), 0);
    const medium = rows.filter(row => numberOf(row, 'overdue_days') > 30 && numberOf(row, 'overdue_days') <= 60).reduce((sum, row) => sum + numberOf(row, 'unpaid_amount'), 0);
    const long = rows.filter(row => numberOf(row, 'overdue_days') > 60).reduce((sum, row) => sum + numberOf(row, 'unpaid_amount'), 0);
    return [
      { key: 'current', label: '未到期', amount: current, tone: 'info' },
      { key: '1-30', label: '1-30 天', amount: short, tone: 'warn' },
      { key: '31-60', label: '31-60 天', amount: medium, tone: 'warn' },
      { key: '60+', label: '60+ 天', amount: long, tone: 'danger' }
    ].map(bucket => ({ ...bucket, percent: percentNumber((bucket.amount / total) * 100) }));
  });
  protected readonly activeReceivableChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'cash') {
      return this.cashChart();
    }
    if (this.chartMode() === 'customer') {
      return this.customerChart();
    }
    return this.agingChart();
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.list<DataRecord>('receivables', { page: 1, page_size: 120, q: this.query, status: this.statusFilter() }).pipe(
      catchError(error => {
        this.error.set(error?.message || '无法读取应收数据。');
        return of(emptyPageResult<DataRecord>());
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(result => {
      this.rows.set(result.items);
      this.setPage(1);
    });
  }

  setPage(page: number): void {
    const next = Math.min(Math.max(1, Math.trunc(page || 1)), this.totalPages());
    this.page.set(next);
    this.pageInput = String(next);
  }

  jumpPage(): void {
    this.setPage(Number(this.pageInput) || 1);
  }

  recordNextPayment(): void {
    const target = this.visibleRows().find(row => numberOf(row, 'unpaid_amount') > 0) ?? this.overdueRows()[0];
    if (!target?.id) {
      this.messages.add({ severity: 'info', summary: '应收收款', detail: '当前没有可收款应收单。' });
      return;
    }
    const amount = Math.max(1, numberOf(target, 'unpaid_amount') || numberOf(target, 'total_amount') - numberOf(target, 'paid_amount'));
    this.confirm.confirm({
      header: '记录收款',
      message: `确认对 ${recordTitle(target)} 记录 ${moneyText(amount)} 银行回款？`,
      acceptLabel: '记录',
      rejectLabel: '取消',
      accept: () => this.api.post(`receivables/${target.id}/payment`, {
        amount,
        payment_method: 'bank',
        reference_no: `PAY-${Date.now()}`,
        remark: '应收风控中心回款'
      }).pipe(
        catchError(error => {
          this.messages.add({ severity: 'warn', summary: '收款未完成', detail: error?.message || '收款金额或状态不满足条件。' });
          return of(null);
        })
      ).subscribe(result => {
        if (result) {
          this.messages.add({ severity: 'success', summary: '收款已记录', detail: '应收、客户信用和审计链路已更新。' });
          this.load();
        }
      })
    });
  }

  sendReminder(): void {
    const target = this.overdueRows()[0];
    if (!target?.id) {
      this.messages.add({ severity: 'info', summary: '催款提醒', detail: '当前没有逾期应收需要催款。' });
      return;
    }
    this.confirm.confirm({
      header: '发送催款提醒',
      message: `确认给 ${textOf(target, 'customer_name')} 发送催款提醒？`,
      acceptLabel: '发送',
      rejectLabel: '取消',
      accept: () => this.api.post(`finance/receivables/${target.id}/reminder`, {}).pipe(
        catchError(error => {
          this.messages.add({ severity: 'warn', summary: '催款未完成', detail: error?.message || '催款提醒未写入通知中心。' });
          return of(null);
        })
      ).subscribe(result => {
        if (result !== null) {
          this.messages.add({ severity: 'success', summary: '催款提醒已发送', detail: '通知中心已生成对应任务。' });
        }
      })
    });
  }

  setAgingFilter(key: string): void {
    this.agingFilter.set(this.agingFilter() === key ? '' : key);
    this.setPage(1);
  }

  private matchesAging(row: DataRecord): boolean {
    const filter = this.agingFilter();
    const days = numberOf(row, 'overdue_days');
    if (!filter) {
      return true;
    }
    if (filter === 'current') {
      return days <= 0;
    }
    if (filter === '1-30') {
      return days > 0 && days <= 30;
    }
    if (filter === '31-60') {
      return days > 30 && days <= 60;
    }
    return days > 60;
  }

  protected isOverdue(row: DataRecord): boolean {
    return ['overdue', 'bad_debt'].includes(String(row['status'] ?? '')) || numberOf(row, 'overdue_days') > 0;
  }

  protected paidPercent(row: DataRecord): number {
    return percentNumber((numberOf(row, 'paid_amount') / Math.max(numberOf(row, 'total_amount'), 1)) * 100);
  }

  protected text(row: DataRecord, key: string, emptyText = '-'): string {
    return textOf(row, key, emptyText);
  }

  protected num(row: DataRecord, key: string): number {
    return numberOf(row, key);
  }

  protected money(value: unknown): string {
    return moneyText(value);
  }

  protected compactMoney(value: unknown): string {
    return compactMoneyText(value);
  }

  protected date(value: unknown): string {
    return dateText(value);
  }

  protected status(value: unknown): string {
    return statusLabel(value);
  }

  protected severity(value: unknown) {
    return statusSeverity(value);
  }

  private agingChart(): EChartsCoreOption {
    const buckets = this.agingBuckets();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom', 'rgba(100,116,139,.95)'),
      series: [{
        type: 'pie',
        radius: ['44%', '72%'],
        center: ['50%', '43%'],
        itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.5)' },
        data: buckets.map(item => ({ name: item.label, value: Math.max(0, item.amount) }))
      }]
    };
  }

  private cashChart(): EChartsCoreOption {
    const items = this.rows().slice(0, 14).reverse();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      dataZoom: [{ type: 'inside' }],
      legend: chartLegend('top', 'rgba(100,116,139,.95)'),
      grid: { left: 30, right: 18, top: 38, bottom: 34, containLabel: true },
      xAxis: { type: 'category', data: items.map(row => textOf(row, 'receivable_no').slice(-8)), axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [
        { name: '已收', type: 'bar', stack: 'cash', data: items.map(row => numberOf(row, 'paid_amount')), barWidth: 18, itemStyle: { color: '#0f766e', borderRadius: [8, 8, 2, 2] } },
        { name: '未收', type: 'bar', stack: 'cash', data: items.map(row => numberOf(row, 'unpaid_amount')), barWidth: 18, itemStyle: { color: '#be123c', borderRadius: [8, 8, 2, 2] } }
      ]
    };
  }

  private customerChart(): EChartsCoreOption {
    const customerAmount = new Map<string, number>();
    for (const row of this.rows()) {
      const customer = textOf(row, 'customer_name', '未维护客户');
      customerAmount.set(customer, (customerAmount.get(customer) ?? 0) + numberOf(row, 'unpaid_amount'));
    }
    const data = [...customerAmount.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 28, right: 18, top: 22, bottom: 24, containLabel: true },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      yAxis: {
        type: 'category',
        data: data.map(item => item[0]),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { width: 128, overflow: 'truncate' }
      },
      series: [{
        type: 'bar',
        data: data.map(item => item[1]),
        barWidth: 16,
        itemStyle: { color: '#be123c', borderRadius: 8 }
      }]
    };
  }
}
