import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
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
import { catchError, finalize, forkJoin, of, switchMap } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DataRecord } from '../core/models';
import { chartLegend, compactMoneyText, compactNumberText, emptyPageResult, numberOf, statusLabel, statusSeverity, textOf } from './page-utils';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page replenishment-console-page">
      <header class="replenishment-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">补货控制</span>
          <h1>采购补货建议</h1>
          <p>从库存预警、供应商交期和安全库存计算建议量，接受后直接生成采购单并进入审批与收货链路。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="regenerate()" [loading]="generating()" aria-label="重新生成补货建议">
              <i class="pi pi-bolt"></i>
              重新计算建议
            </button>
            <button pButton type="button" severity="secondary" (click)="acceptTop()" [loading]="accepting()" aria-label="接受优先补货建议">
              <i class="pi pi-shopping-cart"></i>
              接受优先建议
            </button>
            <a pButton severity="info" routerLink="/app/procurement/orders">
              <i class="pi pi-check-circle"></i>
              采购审批
            </a>
          </div>
        </div>

        <aside class="replenishment-scoreboard">
          <article>
            <span>待处理建议</span>
            <strong>{{ pendingSuggestions().length }}</strong>
            <em>可转采购</em>
          </article>
          <article>
            <span>建议补货量</span>
            <strong>{{ compactNumber(totalSuggestedQty()) }}</strong>
            <em>按安全库存与交期</em>
          </article>
          <article>
            <span>低水位 SKU</span>
            <strong>{{ lowStockRows().length }}</strong>
            <em>库存预警来源</em>
          </article>
        </aside>
      </header>

      <section class="replenishment-grid">
        <article class="atlas-panel replenishment-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">计划看板</span>
              <h2>补货量、现有水位与交期</h2>
            </div>
            <div class="flow-chart-tabs">
              <button type="button" [class.active]="chartMode() === 'waterfall'" (click)="chartMode.set('waterfall')">水位</button>
              <button type="button" [class.active]="chartMode() === 'supplier'" (click)="chartMode.set('supplier')">供应商</button>
              <button type="button" [class.active]="chartMode() === 'status'" (click)="chartMode.set('status')">状态</button>
            </div>
          </div>
          <div class="replenishment-chart" echarts [options]="activeChart()"></div>
        </article>

        <aside class="atlas-panel replenishment-action-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">优先级</span>
              <h2>优先动作</h2>
            </div>
          </div>
          <div class="replenishment-action-list">
            @for (item of priorityActions(); track item.title) {
              <a [routerLink]="item.path" [class.warning]="item.tone === 'warning'">
                <span>{{ item.kicker }}</span>
                <strong>{{ item.title }}</strong>
                <em>{{ item.body }}</em>
              </a>
            }
          </div>
        </aside>

        <article class="atlas-panel replenishment-ledger-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">建议</span>
              <h2>建议队列</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="onQuery($event)" placeholder="搜索物料、供应商、仓库" />
            </div>
          </div>

          @if (loading()) {
            <p-skeleton height="80px" />
            <p-skeleton height="80px" />
          } @else {
            <div class="atlas-record-ledger">
              @for (row of pagedSuggestions(); track row.id) {
                <a class="atlas-record-row" [routerLink]="['/app/inventory/replenishment', row.id]" [class.warning]="text(row, 'status') === 'pending'">
                  <span class="record-code">{{ text(row, 'product_sku') }}</span>
                  <strong>{{ text(row, 'product_name') }}</strong>
                  <em>{{ text(row, 'warehouse_name') }} / {{ text(row, 'supplier_name') }}</em>
                  <b>{{ text(row, 'current_qty') }} → {{ text(row, 'suggested_qty') }}</b>
                  <p-tag [severity]="severity(row['status'])" [value]="status(row['status'])" />
                </a>
              }
            </div>
            @if (filteredSuggestions().length > pageSize()) {
              <div class="atlas-pagination" aria-label="补货建议分页">
                <button type="button" (click)="setPage(page() - 1)" [disabled]="page() <= 1">
                  <i class="pi pi-angle-left"></i>
                  上一页
                </button>
                <span>第 <strong>{{ page() }}</strong> / {{ totalPages() }} 页 · {{ filteredSuggestions().length }} 条</span>
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

        <aside class="atlas-panel replenishment-stock-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">低库存</span>
              <h2>预警来源</h2>
            </div>
          </div>
          <div class="low-stock-list">
            @for (row of lowStockRows().slice(0, 8); track row.id) {
              <a [routerLink]="['/app/inventory/products', row['product_id'] || row.id]">
                <strong>{{ text(row, 'product_name') || text(row, 'name') }}</strong>
                <span>当前 {{ text(row, 'current_qty', text(row, 'quantity')) }} / 安全 {{ text(row, 'min_qty', text(row, 'min_stock')) }}</span>
                <p-progressbar [value]="lowStockRate(row)" [showValue]="false" />
              </a>
            }
          </div>
        </aside>
      </section>
    </section>
  `
})
export class ReplenishmentPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly generating = signal(false);
  protected readonly accepting = signal(false);
  protected readonly suggestions = signal<DataRecord[]>([]);
  protected readonly alerts = signal<DataRecord[]>([]);
  protected readonly pageSize = signal(12);
  protected readonly page = signal(1);
  protected readonly chartMode = signal<'waterfall' | 'supplier' | 'status'>('waterfall');
  protected pageInput = '1';
  protected query = '';

  protected readonly pendingSuggestions = computed(() => this.suggestions().filter(row => String(row['status'] ?? '') === 'pending'));
  protected readonly totalSuggestedQty = computed(() => this.pendingSuggestions().reduce((sum, row) => sum + numberOf(row, 'suggested_qty'), 0));
  protected readonly lowStockRows = computed(() => this.alerts().length ? this.alerts() : this.suggestions().filter(row => numberOf(row, 'current_qty') <= numberOf(row, 'safety_stock', 1)));
  protected readonly filteredSuggestions = computed(() => {
    const q = this.query.trim().toLowerCase();
    if (!q) {
      return this.suggestions();
    }
    return this.suggestions().filter(row => [
      textOf(row, 'product_name'),
      textOf(row, 'product_sku'),
      textOf(row, 'warehouse_name'),
      textOf(row, 'supplier_name'),
      textOf(row, 'status')
    ].join(' ').toLowerCase().includes(q));
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.filteredSuggestions().length / this.pageSize())));
  protected readonly pagedSuggestions = computed(() => {
    const start = (this.page() - 1) * this.pageSize();
    return this.filteredSuggestions().slice(start, start + this.pageSize());
  });
  protected readonly priorityActions = computed(() => [
    { kicker: `${this.pendingSuggestions().length} 条`, title: '建议转采购', body: '按低水位优先生成采购单', path: '/app/procurement/orders', tone: this.pendingSuggestions().length ? 'warning' : 'success' },
    { kicker: `${this.lowStockRows().length} 项`, title: '低库存复核', body: '确认安全库存、供应商与库位', path: '/app/inventory/products', tone: this.lowStockRows().length ? 'warning' : 'success' },
    { kicker: compactMoneyText(this.estimatedAmount()), title: '采购预算', body: '建议量乘以物料成本估算', path: '/app/reports', tone: 'success' }
  ]);
  protected readonly activeChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'supplier') {
      return this.supplierChart();
    }
    if (this.chartMode() === 'status') {
      return this.statusChart();
    }
    return this.waterfallChart();
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      suggestions: this.api.list<DataRecord>('replenishment-suggestions', { page: 1, page_size: 180, sort: 'created_at', order: 'desc' }).pipe(catchError(() => of(emptyPageResult<DataRecord>()))),
      alerts: this.api.list<DataRecord>('stock-alerts', { page: 1, page_size: 80, sort: 'created_at', order: 'desc' }).pipe(catchError(() => of(emptyPageResult<DataRecord>())))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(({ suggestions, alerts }) => {
      this.suggestions.set(suggestions.items);
      this.alerts.set(alerts.items);
      this.setPage(1);
    });
  }

  regenerate(): void {
    this.generating.set(true);
    this.api.post<{ created: number }>('replenishment-suggestions/generate', {}).pipe(
      switchMap(() => this.api.list<DataRecord>('replenishment-suggestions', { page: 1, page_size: 180, sort: 'created_at', order: 'desc' })),
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '建议未更新', detail: error?.message || '补货建议生成失败。' });
        return of(emptyPageResult<DataRecord>());
      }),
      finalize(() => this.generating.set(false))
    ).subscribe(result => {
      this.suggestions.set(result.items);
      this.messages.add({ severity: 'success', summary: '建议已更新', detail: `当前队列 ${result.items.length} 条。` });
    });
  }

  acceptTop(): void {
    const target = this.pendingSuggestions()[0];
    if (!target?.id) {
      this.messages.add({ severity: 'info', summary: '没有待接受建议', detail: '当前建议队列无需转采购。' });
      return;
    }
    this.accepting.set(true);
    this.api.post<{ purchase_order?: DataRecord }>(`replenishment-suggestions/${target.id}/accept`, {}).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '转采购失败', detail: error?.message || '建议未转成采购单。' });
        return of(null);
      }),
      finalize(() => this.accepting.set(false))
    ).subscribe(result => {
      if (!result) {
        return;
      }
      this.messages.add({ severity: 'success', summary: '采购单已创建', detail: textOf(result.purchase_order, 'po_no', '已进入采购队列') });
      this.load();
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

  estimatedAmount(): number {
    return this.pendingSuggestions().slice(0, 40).reduce((sum, row) => sum + numberOf(row, 'suggested_qty') * 120, 0);
  }

  lowStockRate(row: DataRecord): number {
    const current = numberOf(row, 'current_qty', numberOf(row, 'quantity'));
    const min = Math.max(1, numberOf(row, 'min_qty', numberOf(row, 'min_stock', 100)));
    return Math.max(3, Math.min(100, Math.round((current / min) * 100)));
  }

  text(row: DataRecord, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  status(value: unknown): string {
    return statusLabel(value);
  }

  severity(value: unknown) {
    return statusSeverity(value);
  }

  compactNumber(value: unknown): string {
    return compactNumberText(value);
  }

  private waterfallChart(): EChartsCoreOption {
    const rows = this.pendingSuggestions().slice(0, 12);
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top'),
      dataZoom: [{ type: 'inside' }],
      grid: { left: 26, right: 18, top: 42, bottom: 32, containLabel: true },
      xAxis: { type: 'category', data: rows.map(row => textOf(row, 'product_name')), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { rotate: 18, width: 88, overflow: 'truncate' } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } } },
      series: [
        { name: '当前库存', type: 'bar', data: rows.map(row => numberOf(row, 'current_qty')), itemStyle: { color: '#8fb7ff', borderRadius: [8, 8, 2, 2] } },
        { name: '建议补货', type: 'bar', data: rows.map(row => numberOf(row, 'suggested_qty')), itemStyle: { color: '#f0b76a', borderRadius: [8, 8, 2, 2] } }
      ]
    };
  }

  private supplierChart(): EChartsCoreOption {
    const counts = new Map<string, number>();
    for (const row of this.pendingSuggestions()) {
      const key = textOf(row, 'supplier_name', '未指定供应商');
      counts.set(key, (counts.get(key) ?? 0) + numberOf(row, 'suggested_qty'));
    }
    const data = [...counts.entries()].slice(0, 10).map(([name, value]) => ({ name, value }));
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      series: [{
        type: 'treemap',
        roam: false,
        breadcrumb: { show: false },
        label: { show: true, formatter: '{b}' },
        itemStyle: { borderRadius: 10, borderColor: 'rgba(255,255,255,.52)', borderWidth: 2 },
        data: data.length ? data : [{ name: '供应商队列', value: 1 }]
      }]
    };
  }

  private statusChart(): EChartsCoreOption {
    const counts = new Map<string, number>();
    for (const row of this.suggestions()) {
      const key = this.status(row['status']);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    const data = [...counts.entries()].map(([name, value]) => ({ name, value }));
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom'),
      series: [{
        type: 'pie',
        radius: ['45%', '72%'],
        center: ['50%', '42%'],
        itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.48)' },
        data: data.length ? data : [{ name: '建议队列', value: 1 }]
      }]
    };
  }
}
