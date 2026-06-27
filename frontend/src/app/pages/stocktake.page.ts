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
import { catchError, finalize, forkJoin, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DataRecord, LookupItem } from '../core/models';
import { chartLegend, emptyPageResult, moneyText, numberOf, percentNumber, statusLabel, statusSeverity, textOf } from './page-utils';

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page stocktake-console-page">
      <header class="stocktake-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">盘点现场</span>
          <h1>库存盘点中心</h1>
          <p>按仓库生成盘点计划，现场扫码录入实盘数量，完成后自动形成差异调整和审计记录。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="createStocktake()" [loading]="creating()" aria-label="创建盘点计划">
              <i class="pi pi-plus"></i>
              创建盘点计划
            </button>
            <button pButton type="button" severity="secondary" (click)="startSelected()" [loading]="starting()" aria-label="开始选中盘点">
              <i class="pi pi-play"></i>
              开始盘点
            </button>
            <button pButton type="button" severity="info" (click)="countSelected()" [loading]="counting()" aria-label="录入扫码数量">
              <i class="pi pi-qrcode"></i>
              扫码录入
            </button>
            <button pButton type="button" severity="success" (click)="completeSelected()" [loading]="completing()" aria-label="完成盘点">
              <i class="pi pi-check"></i>
              完成盘点
            </button>
          </div>
        </div>

        <aside class="stocktake-scanner">
          <span>现场扫码台</span>
          <strong>{{ selectedTake() ? text(selectedTake(), 'take_no') : '选择盘点单' }}</strong>
          <div class="scan-frame">
            <i></i><i></i><i></i><i></i>
            <b></b>
          </div>
          <em>{{ selectedTake() ? status(selectedTake()?.['status']) : '创建或选择任务后开始录入' }}</em>
        </aside>
      </header>

      <section class="stocktake-grid">
        <article class="atlas-panel stocktake-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">差异看板</span>
              <h2>盘点进度与差异</h2>
            </div>
            <div class="flow-chart-tabs">
              <button type="button" [class.active]="chartMode() === 'progress'" (click)="chartMode.set('progress')">进度</button>
              <button type="button" [class.active]="chartMode() === 'variance'" (click)="chartMode.set('variance')">差异</button>
              <button type="button" [class.active]="chartMode() === 'status'" (click)="chartMode.set('status')">状态</button>
            </div>
          </div>
          <div class="stocktake-chart" echarts [options]="activeChart()"></div>
        </article>

        <aside class="atlas-panel stocktake-warehouse-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">仓库</span>
              <h2>盘点仓库</h2>
            </div>
          </div>
          <div class="stocktake-selector-list">
            @for (warehouse of warehouses(); track warehouse.id) {
              <button type="button" [class.active]="selectedWarehouseId() === warehouse.id" (click)="selectedWarehouseId.set(warehouse.id)">
                <strong>{{ warehouse.label }}</strong>
                <span>{{ warehouse.description || '仓库' }}</span>
              </button>
            }
          </div>
        </aside>

        <article class="atlas-panel stocktake-ledger-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">计划</span>
              <h2>盘点任务</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="onQuery($event)" placeholder="搜索盘点单、仓库、状态" />
            </div>
          </div>

          @if (loading()) {
            <p-skeleton height="80px" />
            <p-skeleton height="80px" />
          } @else {
            <div class="atlas-record-ledger">
              @for (row of pagedRows(); track row.id) {
                <button type="button" class="atlas-record-row stocktake-row-button" [class.active]="row.id === selectedTake()?.id" [class.warning]="isOpen(row)" (click)="selectTake(row)">
                  <span class="record-code">{{ text(row, 'take_no') }}</span>
                  <strong>{{ text(row, 'warehouse_name') }}</strong>
                  <em>{{ text(row, 'take_type') }} / {{ text(row, 'planned_date') }}</em>
                  <b>{{ percent(row) }}%</b>
                  <p-tag [severity]="severity(row['status'])" [value]="status(row['status'])" />
                </button>
              }
            </div>
            @if (filteredRows().length > pageSize()) {
              <div class="atlas-pagination" aria-label="盘点分页">
                <button type="button" (click)="setPage(page() - 1)" [disabled]="page() <= 1">
                  <i class="pi pi-angle-left"></i>
                  上一页
                </button>
                <span>第 <strong>{{ page() }}</strong> / {{ totalPages() }} 页 · {{ filteredRows().length }} 单</span>
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

        <aside class="atlas-panel stocktake-detail-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">当前选择</span>
              <h2>盘点明细</h2>
            </div>
            @if (selectedTake()?.id) {
              <a [routerLink]="['/app/stocktakes', selectedTake()?.id]">详情</a>
            }
          </div>
          @if (selectedTake(); as take) {
            <div class="stocktake-summary-card">
              <strong>{{ text(take, 'take_no') }}</strong>
              <span>{{ text(take, 'warehouse_name') }} · {{ status(take['status']) }}</span>
              <p-progressbar [value]="percent(take)" [showValue]="false" />
              <div>
                <span>总项数 <b>{{ text(take, 'total_items') }}</b></span>
                <span>已盘 <b>{{ text(take, 'counted_items') }}</b></span>
                <span>差异 <b>{{ text(take, 'variance_items') }}</b></span>
              </div>
              <em>差异价值 {{ money(take['total_variance_value']) }}</em>
            </div>
          } @else {
            <div class="empty-state compact">
              <i class="pi pi-qrcode"></i>
              <strong>选择盘点任务</strong>
              <p>任务详情、扫码录入和完成动作会显示在这里。</p>
            </div>
          }
        </aside>
      </section>
    </section>
  `
})
export class StocktakePage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly creating = signal(false);
  protected readonly starting = signal(false);
  protected readonly counting = signal(false);
  protected readonly completing = signal(false);
  protected readonly rows = signal<DataRecord[]>([]);
  protected readonly warehouses = signal<LookupItem[]>([]);
  protected readonly selectedTake = signal<DataRecord | null>(null);
  protected readonly selectedWarehouseId = signal<number | null>(null);
  protected readonly chartMode = signal<'progress' | 'variance' | 'status'>('progress');
  protected readonly pageSize = signal(10);
  protected readonly page = signal(1);
  protected pageInput = '1';
  protected query = '';

  protected readonly filteredRows = computed(() => {
    const q = this.query.trim().toLowerCase();
    if (!q) {
      return this.rows();
    }
    return this.rows().filter(row => [
      textOf(row, 'take_no'),
      textOf(row, 'warehouse_name'),
      textOf(row, 'take_type'),
      textOf(row, 'status')
    ].join(' ').toLowerCase().includes(q));
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.filteredRows().length / this.pageSize())));
  protected readonly pagedRows = computed(() => {
    const start = (this.page() - 1) * this.pageSize();
    return this.filteredRows().slice(start, start + this.pageSize());
  });
  protected readonly activeChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'variance') {
      return this.varianceChart();
    }
    if (this.chartMode() === 'status') {
      return this.statusChart();
    }
    return this.progressChart();
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      takes: this.api.list<DataRecord>('stocktakes', { page: 1, page_size: 12, sort: 'created_at', order: 'desc' }).pipe(catchError(() => of(emptyPageResult<DataRecord>()))),
      warehouses: this.api.lookup('lookups/warehouses').pipe(catchError(() => of([])))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(({ takes, warehouses }) => {
      this.rows.set(takes.items);
      this.warehouses.set(warehouses);
      this.selectedTake.set(takes.items[0] ?? null);
      this.selectedWarehouseId.set(warehouses[0]?.id ?? null);
      this.setPage(1);
    });
  }

  createStocktake(): void {
    const warehouseId = this.selectedWarehouseId() ?? this.warehouses()[0]?.id;
    if (!warehouseId) {
      this.messages.add({ severity: 'warn', summary: '无法创建盘点', detail: '没有可用仓库。' });
      return;
    }
    this.creating.set(true);
    this.api.post<DataRecord>('stocktakes/create', {
      warehouse_id: warehouseId,
      take_type: 'cycle',
      product_ids: [],
      remark: '区域仓周期盘点'
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '创建失败', detail: error?.message || '盘点计划未创建。' });
        return of(null);
      }),
      finalize(() => this.creating.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '盘点计划已创建', detail: textOf(result, 'take_no') });
        this.rows.set([result, ...this.rows()]);
        this.selectedTake.set(result);
      }
    });
  }

  startSelected(): void {
    const take = this.selectedTake();
    if (!take?.id) {
      return;
    }
    this.starting.set(true);
    this.api.post(`stocktakes/${take.id}/start`, {}).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '无法开始', detail: error?.message || '盘点任务未开始。' });
        return of(null);
      }),
      finalize(() => this.starting.set(false))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '盘点已开始', detail: textOf(take, 'take_no') });
        this.load();
      }
    });
  }

  countSelected(): void {
    const take = this.selectedTake();
    if (!take?.id) {
      return;
    }
    this.counting.set(true);
    this.api.post<{ counted: number }>(`stocktakes/${take.id}/count`, { items: [{ actual_qty: numberOf(take, 'counted_items') + 1 }] }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '录入失败', detail: error?.message || '扫码数量未写入。' });
        return of(null);
      }),
      finalize(() => this.counting.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '扫码已录入', detail: `写入 ${result.counted} 项。` });
        this.load();
      }
    });
  }

  completeSelected(): void {
    const take = this.selectedTake();
    if (!take?.id) {
      return;
    }
    this.completing.set(true);
    this.api.post(`stocktakes/${take.id}/complete`, { auto_adjust: true }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '无法完成', detail: error?.message || '盘点任务未完成。' });
        return of(null);
      }),
      finalize(() => this.completing.set(false))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '盘点已完成', detail: textOf(take, 'take_no') });
        this.load();
      }
    });
  }

  selectTake(row: DataRecord): void {
    this.selectedTake.set(row);
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

  isOpen(row: DataRecord): boolean {
    return ['draft', 'in_progress', 'counting'].includes(String(row['status'] ?? ''));
  }

  percent(row: DataRecord | null | undefined): number {
    if (!row) {
      return 0;
    }
    if (row['progress'] !== undefined) {
      return percentNumber(row['progress']);
    }
    const total = Math.max(1, numberOf(row, 'total_items'));
    return Math.round((numberOf(row, 'counted_items') / total) * 100);
  }

  text(row: DataRecord | null | undefined, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  status(value: unknown): string {
    return statusLabel(value);
  }

  severity(value: unknown) {
    return statusSeverity(value);
  }

  money(value: unknown): string {
    return moneyText(value);
  }

  private progressChart(): EChartsCoreOption {
    const rows = this.rows().slice(0, 14).reverse();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      dataZoom: [{ type: 'inside' }],
      grid: { left: 24, right: 16, top: 28, bottom: 28, containLabel: true },
      xAxis: { type: 'category', data: rows.map(row => textOf(row, 'take_no')), axisLabel: { rotate: 18, width: 86, overflow: 'truncate' }, axisTick: { show: false }, axisLine: { show: false } },
      yAxis: { type: 'value', max: 100, splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } } },
      series: [{ type: 'bar', data: rows.map(row => this.percent(row)), itemStyle: { color: '#58b7aa', borderRadius: [10, 10, 2, 2] } }]
    };
  }

  private varianceChart(): EChartsCoreOption {
    const rows = this.rows().slice(0, 12).reverse();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top'),
      grid: { left: 24, right: 16, top: 42, bottom: 28, containLabel: true },
      xAxis: { type: 'category', data: rows.map(row => textOf(row, 'warehouse_name')), axisLabel: { rotate: 14, width: 90, overflow: 'truncate' }, axisTick: { show: false }, axisLine: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } } },
      series: [
        { name: '差异项', type: 'bar', data: rows.map(row => numberOf(row, 'variance_items')), itemStyle: { color: '#f0b76a', borderRadius: [8, 8, 2, 2] } },
        { name: '总项数', type: 'line', smooth: true, data: rows.map(row => numberOf(row, 'total_items')), lineStyle: { width: 3, color: '#8fb7ff' } }
      ]
    };
  }

  private statusChart(): EChartsCoreOption {
    const counts = new Map<string, number>();
    for (const row of this.rows()) {
      const key = this.status(row['status']);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom'),
      series: [{
        type: 'pie',
        radius: ['45%', '72%'],
        center: ['50%', '42%'],
        itemStyle: { borderRadius: 10, borderColor: 'rgba(255,255,255,.5)', borderWidth: 2 },
        data: [...counts.entries()].map(([name, value]) => ({ name, value }))
      }]
    };
  }
}
