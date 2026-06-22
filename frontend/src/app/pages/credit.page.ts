import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { ProgressBarModule } from 'primeng/progressbar';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DataRecord } from '../core/models';
import { chartLegend, emptyPageResult, moneyText, numberOf, percentNumber, textOf } from './page-utils';

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page credit-console-page">
      <header class="credit-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">信用管控</span>
          <h1>客户信用中心</h1>
          <p>统一查看客户额度、占用率、冻结状态和应收压力，让销售履约、收款和信用管控保持一致。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="toggleSelectedFreeze()" [loading]="freezing()" aria-label="冻结或解冻选中客户">
              <i class="pi pi-lock"></i>
              冻结/解冻
            </button>
            <a pButton severity="secondary" routerLink="/app/finance/receivables">
              <i class="pi pi-wallet"></i>
              应收风控
            </a>
            <button pButton type="button" severity="info" (click)="generateReport()" [loading]="reporting()" aria-label="生成财务总览报表">
              <i class="pi pi-chart-line"></i>
              生成信用报表
            </button>
          </div>
        </div>

        <aside class="credit-scoreboard">
          <article>
            <span>信用总额</span>
            <strong>{{ money(totalLimit()) }}</strong>
            <em>客户额度池</em>
          </article>
          <article>
            <span>已占用</span>
            <strong>{{ money(totalUsed()) }}</strong>
            <em>{{ avgUsage() }}% 平均占用</em>
          </article>
          <article>
            <span>冻结客户</span>
            <strong>{{ frozenRows().length }}</strong>
            <em>影响新订单</em>
          </article>
        </aside>
      </header>

      <section class="credit-grid">
        <article class="atlas-panel credit-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">风险矩阵</span>
              <h2>额度占用与冻结分布</h2>
            </div>
            <div class="flow-chart-tabs">
              <button type="button" [class.active]="chartMode() === 'usage'" (click)="chartMode.set('usage')">占用</button>
              <button type="button" [class.active]="chartMode() === 'risk'" (click)="chartMode.set('risk')">风险</button>
              <button type="button" [class.active]="chartMode() === 'frozen'" (click)="chartMode.set('frozen')">冻结</button>
            </div>
          </div>
          <div class="credit-chart" echarts [options]="activeChart()"></div>
        </article>

        <aside class="atlas-panel credit-action-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">当前客户</span>
              <h2>当前客户</h2>
            </div>
            @if (selectedCredit()?.id) {
              <a [routerLink]="['/app/finance/credits', selectedCredit()?.id]">详情</a>
            }
          </div>
          @if (selectedCredit(); as row) {
            <div class="credit-focus-card" [class.frozen]="row['is_frozen'] === true">
              <strong>{{ text(row, 'customer_name') }}</strong>
              <span>{{ row['is_frozen'] === true ? '信用冻结' : '可继续履约' }}</span>
              <p-progressbar [value]="usage(row)" [showValue]="false" />
              <div>
                <em>额度 {{ money(row['credit_limit']) }}</em>
                <em>可用 {{ money(row['available_credit']) }}</em>
              </div>
            </div>
          }
        </aside>

        <article class="atlas-panel credit-ledger-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">客户账本</span>
              <h2>信用额度列表</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="onQuery($event)" placeholder="搜索客户、冻结原因" />
            </div>
          </div>

          @if (loading()) {
            <p-skeleton height="78px" />
            <p-skeleton height="78px" />
          } @else {
            <div class="atlas-record-ledger">
              @for (row of pagedRows(); track row.id) {
                <button type="button" class="atlas-record-row stocktake-row-button" [class.active]="row.id === selectedCredit()?.id" [class.warning]="isWarning(row)" (click)="selectCredit(row)">
                  <span class="record-code">{{ usage(row) }}%</span>
                  <strong>{{ text(row, 'customer_name') }}</strong>
                  <em>额度 {{ money(row['credit_limit']) }} / 已用 {{ money(row['used_credit']) }}</em>
                  <b>{{ money(row['available_credit']) }}</b>
                  <p-tag [severity]="row['is_frozen'] === true ? 'danger' : isWarning(row) ? 'warn' : 'success'" [value]="row['is_frozen'] === true ? '冻结' : isWarning(row) ? '预警' : '正常'" />
                </button>
              }
            </div>
            @if (filteredRows().length > pageSize()) {
              <div class="atlas-pagination" aria-label="信用分页">
                <button type="button" (click)="setPage(page() - 1)" [disabled]="page() <= 1">
                  <i class="pi pi-angle-left"></i>
                  上一页
                </button>
                <span>第 <strong>{{ page() }}</strong> / {{ totalPages() }} 页 · {{ filteredRows().length }} 客户</span>
                <label>
                  跳至
                  <input pInputText [ngModel]="pageInput" (ngModelChange)="pageInput = $event" (keydown.enter)="jumpPage()" inputmode="numeric" />
                </label>
                <button type="button" (click)="jumpPage()">跳转</button>
                <button type="button" (click)="setPage(page() + 1)" [disabled]="page() >= totalPages()">
                  下一页
                  <i class="pi pi-angle-right"></i>
                </button>
              </div>
            }
          }
        </article>
      </section>
    </section>
  `
})
export class CreditPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly freezing = signal(false);
  protected readonly reporting = signal(false);
  protected readonly rows = signal<DataRecord[]>([]);
  protected readonly selectedCredit = signal<DataRecord | null>(null);
  protected readonly chartMode = signal<'usage' | 'risk' | 'frozen'>('usage');
  protected readonly pageSize = signal(12);
  protected readonly page = signal(1);
  protected query = '';
  protected pageInput = '1';

  protected readonly frozenRows = computed(() => this.rows().filter(row => row['is_frozen'] === true));
  protected readonly totalLimit = computed(() => this.rows().reduce((sum, row) => sum + numberOf(row, 'credit_limit'), 0));
  protected readonly totalUsed = computed(() => this.rows().reduce((sum, row) => sum + numberOf(row, 'used_credit'), 0));
  protected readonly avgUsage = computed(() => Math.round(this.rows().reduce((sum, row) => sum + this.usage(row), 0) / Math.max(1, this.rows().length)));
  protected readonly filteredRows = computed(() => {
    const q = this.query.trim().toLowerCase();
    if (!q) {
      return this.rows();
    }
    return this.rows().filter(row => [textOf(row, 'customer_name'), textOf(row, 'frozen_reason')].join(' ').toLowerCase().includes(q));
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.filteredRows().length / this.pageSize())));
  protected readonly pagedRows = computed(() => {
    const start = (this.page() - 1) * this.pageSize();
    return this.filteredRows().slice(start, start + this.pageSize());
  });
  protected readonly activeChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'risk') {
      return this.riskChart();
    }
    if (this.chartMode() === 'frozen') {
      return this.frozenChart();
    }
    return this.usageChart();
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.list<DataRecord>('credits', { page: 1, page_size: 180 }).pipe(
      catchError(() => of(emptyPageResult<DataRecord>())),
      finalize(() => this.loading.set(false))
    ).subscribe(result => {
      this.rows.set(result.items);
      this.selectedCredit.set(result.items[0] ?? null);
      this.setPage(1);
    });
  }

  selectCredit(row: DataRecord): void {
    this.selectedCredit.set(row);
  }

  toggleSelectedFreeze(): void {
    const row = this.selectedCredit();
    if (!row?.id) {
      return;
    }
    const action = row['is_frozen'] === true ? 'unfreeze' : 'freeze';
    this.freezing.set(true);
    this.api.post(`finance/credits/${row.id}/${action}`, { reason: '应收账龄与额度占用复核' }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '信用状态未更新', detail: error?.message || '信用状态写入失败。' });
        return of(null);
      }),
      finalize(() => this.freezing.set(false))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: action === 'freeze' ? '客户已冻结' : '客户已解冻', detail: textOf(row, 'customer_name') });
        this.load();
      }
    });
  }

  generateReport(): void {
    this.reporting.set(true);
    this.api.post('reports/generate/financial_overview', { params: {} }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '报表未生成', detail: error?.message || '财务报表生成失败。' });
        return of(null);
      }),
      finalize(() => this.reporting.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '信用报表已生成', detail: '已写入报表工作室。' });
      }
    });
  }

  onQuery(value: string): void {
    this.query = value;
    this.setPage(1);
  }

  setPage(page: number): void {
    const next = Math.min(Math.max(1, Math.trunc(page || 1)), this.totalPages());
    this.page.set(next);
    this.pageInput = String(next);
  }

  jumpPage(): void {
    this.setPage(Number(this.pageInput) || 1);
  }

  usage(row: DataRecord): number {
    if (row['usage_rate'] !== undefined) {
      return percentNumber(row['usage_rate']);
    }
    return Math.round((numberOf(row, 'used_credit') / Math.max(1, numberOf(row, 'credit_limit'))) * 100);
  }

  isWarning(row: DataRecord): boolean {
    return row['is_frozen'] === true || this.usage(row) >= numberOf(row, 'warning_threshold', 80);
  }

  text(row: DataRecord | null | undefined, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  money(value: unknown): string {
    return moneyText(value);
  }

  private usageChart(): EChartsCoreOption {
    const rows = this.rows().slice(0, 14).reverse();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      dataZoom: [{ type: 'inside' }],
      grid: { left: 24, right: 18, top: 28, bottom: 30, containLabel: true },
      xAxis: { type: 'category', data: rows.map(row => textOf(row, 'customer_name')), axisLabel: { rotate: 18, width: 90, overflow: 'truncate' }, axisTick: { show: false }, axisLine: { show: false } },
      yAxis: { type: 'value', max: 100, splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } } },
      series: [{ type: 'bar', data: rows.map(row => this.usage(row)), itemStyle: { color: '#ff8fa3', borderRadius: [10, 10, 2, 2] } }]
    };
  }

  private riskChart(): EChartsCoreOption {
    const buckets = [
      { name: '0-60%', value: this.rows().filter(row => this.usage(row) < 60).length },
      { name: '60-80%', value: this.rows().filter(row => this.usage(row) >= 60 && this.usage(row) < 80).length },
      { name: '80-100%', value: this.rows().filter(row => this.usage(row) >= 80 && this.usage(row) <= 100).length },
      { name: '超额', value: this.rows().filter(row => this.usage(row) > 100).length }
    ];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom'),
      series: [{ type: 'pie', radius: ['44%', '72%'], center: ['50%', '42%'], itemStyle: { borderRadius: 10, borderColor: 'rgba(255,255,255,.5)', borderWidth: 2 }, data: buckets }]
    };
  }

  private frozenChart(): EChartsCoreOption {
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      series: [{
        type: 'treemap',
        roam: false,
        breadcrumb: { show: false },
        label: { show: true, formatter: '{b}' },
        itemStyle: { borderRadius: 10, borderColor: 'rgba(255,255,255,.5)', borderWidth: 2 },
        data: [
          { name: '冻结', value: this.frozenRows().length },
          { name: '预警', value: this.rows().filter(row => this.isWarning(row) && row['is_frozen'] !== true).length },
          { name: '正常', value: this.rows().filter(row => !this.isWarning(row)).length }
        ]
      }]
    };
  }
}
