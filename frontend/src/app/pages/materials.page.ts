import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { injectQuery } from '@tanstack/angular-query-experimental';
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
import { InventoryService } from '../core/inventory.service';
import { ListWorkbenchStore } from '../core/list-workbench.store';
import { DataRecord } from '../core/models';
import { replenishmentCreatedCount, replenishmentJobStatus, ReplenishmentJobService } from '../core/replenishment-job.service';
import { chartLegend, compactMoneyText, compactNumberText, compactPieSeries, moneyText, numberOf, percentNumber, recordTitle, statusSeverity, textOf } from './page-utils';

interface MaterialFamily {
  name: string;
  count: number;
  stock: number;
}

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule, TooltipModule],
  providers: [ListWorkbenchStore],
  template: `
    <section class="ops-atlas-page material-atlas">
      <header class="atlas-split-hero material-atlas-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">物料图谱</span>
          <h1>物料库存图谱</h1>
          <p>产品、供应商、安全库存和补货建议在同一张作业图里联动。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="generateReplenishment()" [loading]="replenishmentGenerating()" [disabled]="replenishmentGenerating()" aria-label="生成补货建议">
              <i class="pi pi-bolt"></i>
              生成补货
            </button>
            <button pButton type="button" severity="secondary" (click)="createMaterial()" aria-label="新增维护物料">
              <i class="pi pi-plus"></i>
              新增物料
            </button>
            <button pButton type="button" [text]="true" (click)="load()" aria-label="刷新物料数据" pTooltip="刷新物料数据">
              <i class="pi pi-refresh"></i>
            </button>
          </div>
        </div>

        <div class="material-shelf-map" aria-label="物料分类库存图谱">
          @for (family of families(); track family.name) {
            <button type="button" [class.active]="categoryFilter() === family.name" (click)="setCategory(family.name)">
              <span>{{ family.name }}</span>
              <strong>{{ compactNumber(family.stock) }}</strong>
              <em>{{ family.count }} 个 SKU</em>
            </button>
          }
        </div>

        <aside class="material-water-orb">
          <span>低水位</span>
          <strong>{{ lowStockCount() }}</strong>
          <em>触发补货建议</em>
          <a routerLink="/app/inventory/replenishment">查看补货队列</a>
        </aside>
      </header>

      <section class="material-chart-grid">
        <article class="atlas-panel material-chart-card wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">库存结构</span>
              <h2>分类库存与 SKU 密度</h2>
            </div>
            <div class="metric-mode-switch" aria-label="物料图表模式">
              @for (mode of chartModes; track mode.key) {
                <button type="button" [class.active]="chartMode() === mode.key" (click)="setChartMode(mode.key)">
                  <i class="pi" [class]="mode.icon"></i>
                  {{ mode.label }}
                </button>
              }
            </div>
          </div>
          <div class="material-chart" echarts [options]="activeMaterialChart()"></div>
        </article>

        <article class="atlas-panel material-chart-card">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">供应覆盖</span>
              <h2>供应覆盖</h2>
            </div>
            <p-tag severity="info" [value]="supplierCount() + ' 家'" />
          </div>
          <div class="material-chart compact" echarts [options]="supplierChart()"></div>
        </article>
      </section>

      <section class="material-atlas-grid">
        <article class="atlas-panel material-ledger-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">物料账本</span>
              <h2>物料账本</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query()" (ngModelChange)="onQueryChange($event)" placeholder="搜索 SKU、物料、供应商" />
            </div>
          </div>

          @if (error()) {
            <div class="empty-state">
              <i class="pi pi-cloud"></i>
              <strong>物料数据通道未连接</strong>
              <p>{{ error() }}</p>
              <button pButton type="button" (click)="load()">重试</button>
            </div>
          } @else if (loading()) {
            <p-skeleton height="74px" />
            <p-skeleton height="74px" />
            <p-skeleton height="74px" />
          } @else {
            <div class="atlas-record-ledger">
              @for (row of visibleRows(); track row.id) {
                <a class="atlas-record-row" [routerLink]="['/app/inventory/products', row.id]" [class.warning]="isLow(row)">
                  <span class="record-code">{{ text(row, 'sku') }}</span>
                  <strong>{{ text(row, 'name') }}</strong>
                  <em>{{ text(row, 'category_name', '未分类') }} / {{ text(row, 'supplier_name', '供应商未维护') }}</em>
                  <b>{{ compactNumber(num(row, 'total_stock')) }}</b>
                  <p-tag [severity]="isLow(row) ? 'warn' : 'success'" [value]="isLow(row) ? '低水位' : '稳定'" />
                </a>
              }
            </div>
            @if (filteredRows().length > pageSize()) {
              <div class="atlas-pagination" aria-label="物料分页">
                <button type="button" (click)="setPage(currentPage() - 1)" [disabled]="currentPage() <= 1">
                  <i class="pi pi-angle-left"></i>
                  上一页
                </button>
                <span>第 <strong>{{ currentPage() }}</strong> / {{ totalPages() }} 页 · {{ filteredRows().length }} 个 SKU</span>
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
        </article>

        <aside class="atlas-panel waterline-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">水位线</span>
              <h2>库存水位</h2>
            </div>
            <p-tag [severity]="lowStockCount() ? 'warn' : 'success'" [value]="lowStockCount() ? '需要补货' : '稳定'" />
          </div>
          <div class="waterline-stack">
            @for (row of visibleRows().slice(0, 8); track row.id) {
              <a [routerLink]="['/app/inventory/products', row.id]" [class.low]="isLow(row)">
                <span>{{ text(row, 'name') }}</span>
                <p-progressbar [value]="stockPercent(row)" [showValue]="false" />
                <strong>{{ stockPercent(row) }}%</strong>
              </a>
            }
          </div>
        </aside>
      </section>

      <section class="atlas-panel material-risk-rack">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">补货信号</span>
            <h2>补货信号与主数据缺口</h2>
          </div>
          <button type="button" [class.active]="categoryFilter() === ''" (click)="setCategory('')">全部类别</button>
        </div>
        <div class="risk-rack-grid">
          @for (row of lowStockRows().slice(0, 6); track row.id) {
            <a class="risk-rack-card" [routerLink]="['/app/inventory/products', row.id]">
              <p-tag severity="warn" value="低水位" />
              <strong>{{ recordName(row) }}</strong>
              <span>现存 {{ compactNumber(num(row, 'total_stock')) }} / 安全线 {{ compactNumber(num(row, 'min_stock')) }}</span>
            </a>
          }
          @if (!lowStockRows().length) {
            <div class="risk-rack-card calm">
              <p-tag severity="success" value="水位正常" />
              <strong>当前没有低水位物料</strong>
              <span>建议继续复核供应商、批次和价格字段完整度。</span>
            </div>
          }
          <div class="risk-rack-card metric">
            <span>库存资产</span>
            <strong>{{ compactMoney(inventoryValue()) }}</strong>
            <em>{{ supplierCount() }} 家供应商覆盖</em>
          </div>
        </div>
      </section>
    </section>
  `
})
export class MaterialsPage {
  private readonly api = inject(ApiService);
  private readonly inventory = inject(InventoryService);
  private readonly replenishmentJobs = inject(ReplenishmentJobService);
  private readonly messages = inject(MessageService);
  private readonly confirm = inject(ConfirmationService);
  protected readonly listState = inject(ListWorkbenchStore);

  protected readonly replenishmentGenerating = signal(false);
  protected readonly categoryFilter = this.listState.categoryFilter;
  protected readonly pageSize = this.listState.pageSize;
  protected readonly page = this.listState.page;
  protected readonly chartMode = computed<'category' | 'risk'>(() => this.listState.chartMode() === 'risk' ? 'risk' : 'category');
  protected readonly query = this.listState.query;
  protected pageInput = '1';
  protected readonly chartModes = [
    { key: 'category' as const, label: '分类库存', icon: 'pi-chart-bar' },
    { key: 'risk' as const, label: '低水位', icon: 'pi-exclamation-triangle' }
  ];
  protected readonly productsQuery = injectQuery(() => this.inventory.productsQuery({
    page: 1,
    page_size: 120,
    q: this.query().trim()
  }));
  protected readonly rows = computed(() => this.productsQuery.data()?.items ?? []);
  protected readonly loading = computed(() => this.productsQuery.isPending() || this.productsQuery.isFetching());
  protected readonly error = computed(() => {
    const error = this.productsQuery.error();
    return error ? error.message || '无法读取物料数据。' : '';
  });

  protected readonly filteredRows = computed(() => {
    const q = this.query().trim().toLowerCase();
    const category = this.categoryFilter();
    return this.rows().filter(row => {
      const matchesCategory = !category || textOf(row, 'category_name') === category;
      const haystack = [textOf(row, 'sku'), textOf(row, 'name'), textOf(row, 'supplier_name'), textOf(row, 'category_name')].join(' ').toLowerCase();
      return matchesCategory && (!q || haystack.includes(q));
    });
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.filteredRows().length / this.pageSize())));
  protected readonly currentPage = computed(() => Math.min(this.page(), this.totalPages()));
  protected readonly visibleRows = computed(() => {
    const start = (this.currentPage() - 1) * this.pageSize();
    return this.filteredRows().slice(start, start + this.pageSize());
  });
  protected readonly lowStockRows = computed(() => this.rows().filter(row => this.isLow(row)));
  protected readonly lowStockCount = computed(() => this.lowStockRows().length);
  protected readonly supplierCount = computed(() => new Set(this.rows().map(row => textOf(row, 'supplier_name', '')).filter(Boolean)).size);
  protected readonly inventoryValue = computed(() => this.rows().reduce((sum, row) => sum + numberOf(row, 'total_stock') * numberOf(row, 'price'), 0));
  protected readonly families = computed<MaterialFamily[]>(() => {
    const map = new Map<string, MaterialFamily>();
    for (const row of this.rows()) {
      const name = textOf(row, 'category_name', '未分类');
      const entry = map.get(name) ?? { name, count: 0, stock: 0 };
      entry.count += 1;
      entry.stock += numberOf(row, 'total_stock');
      map.set(name, entry);
    }
    return [...map.values()].sort((a, b) => b.stock - a.stock).slice(0, 5);
  });
  protected readonly activeMaterialChart = computed<EChartsCoreOption>(() => this.chartMode() === 'risk' ? this.riskChart() : this.categoryChart());

  load(): void {
    this.productsQuery.refetch();
  }

  setCategory(category: string): void {
    this.listState.setCategoryFilter(category);
    this.syncPageInput();
  }

  onQueryChange(value: string): void {
    this.listState.setQuery(value);
    this.syncPageInput();
  }

  setChartMode(mode: 'category' | 'risk'): void {
    this.listState.setChartMode(mode);
  }

  setPage(page: number): void {
    const next = Math.min(Math.max(1, Math.trunc(page || 1)), this.totalPages());
    this.listState.setPage(next);
    this.pageInput = String(next);
  }

  jumpPage(): void {
    this.setPage(Number(this.pageInput) || 1);
  }

  private syncPageInput(): void {
    this.pageInput = String(this.currentPage());
  }

  generateReplenishment(): void {
    this.confirm.confirm({
      header: '生成补货建议',
      message: `确认根据 ${this.rows().length} 个物料的库存水位生成补货建议？`,
      acceptLabel: '生成',
      rejectLabel: '取消',
      accept: () => {
        this.replenishmentGenerating.set(true);
        this.replenishmentJobs.runGenerationToFinal().pipe(
          catchError(error => {
            this.messages.add({ severity: 'warn', summary: '生成未完成', detail: error?.message || '后端拒绝生成补货建议。' });
            return of(null);
          }),
          finalize(() => this.replenishmentGenerating.set(false))
        ).subscribe(event => {
          if (!event) {
            return;
          }
          const status = replenishmentJobStatus(event.result);
          if (event.timedOut) {
            this.messages.add({ severity: 'info', summary: '补货任务仍在运行', detail: '后台仍在生成补货建议，可稍后刷新补货队列。' });
            return;
          }
          if (status === 'success') {
            this.messages.add({ severity: 'success', summary: '补货建议已生成', detail: `新增或更新 ${replenishmentCreatedCount(event.result)} 条补货建议。` });
            this.load();
          } else {
            this.messages.add({ severity: 'warn', summary: '生成未完成', detail: event.result.job?.error_message || '后台补货任务未完成。' });
          }
        });
      }
    });
  }

  createMaterial(): void {
    const stamp = Date.now().toString().slice(-6);
    this.confirm.confirm({
      header: '新增维护物料',
      message: '将创建一条可继续维护的制造业物料主数据。',
      acceptLabel: '创建',
      rejectLabel: '取消',
      accept: () => {
        this.api.post<DataRecord>('products', {
          sku: `MFG-MNT-${stamp}`,
          name: `产线维护备件包 ${stamp}`,
          price: 680,
          cost: 420,
          min_stock: 24,
          max_stock: 180,
          description: '生产线维护、检修与紧急替换使用的标准备件包'
        }).pipe(
          catchError(error => {
            this.messages.add({ severity: 'warn', summary: '创建未完成', detail: error?.message || '物料主数据未写入。' });
            return of(null);
          })
        ).subscribe(result => {
          if (result) {
            this.messages.add({ severity: 'success', summary: '物料已创建', detail: recordTitle(result) });
            this.load();
          }
        });
      }
    });
  }

  protected isLow(row: DataRecord): boolean {
    return numberOf(row, 'total_stock') <= numberOf(row, 'min_stock');
  }

  protected stockPercent(row: DataRecord): number {
    const stock = numberOf(row, 'total_stock');
    const max = Math.max(numberOf(row, 'max_stock'), numberOf(row, 'min_stock') * 2, stock, 1);
    return percentNumber((stock / max) * 100);
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

  protected compactNumber(value: unknown): string {
    return compactNumberText(value);
  }

  protected recordName(row: DataRecord): string {
    return recordTitle(row);
  }

  protected readonly categoryChart = computed<EChartsCoreOption>(() => {
    const rows = this.families();
    return {
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top', 'rgba(100,116,139,.95)'),
      grid: { left: 18, right: 20, top: 38, bottom: 26, containLabel: true },
      xAxis: { type: 'category', data: rows.map(item => item.name), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { interval: 0, rotate: 10 } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [
        { name: '库存量', type: 'bar', data: rows.map(item => item.stock), barWidth: 22, itemStyle: { color: '#2ca59d', borderRadius: [10, 10, 2, 2] } },
        { name: 'SKU 数', type: 'line', smooth: true, data: rows.map(item => item.count), yAxisIndex: 0, lineStyle: { width: 3, color: '#7c8ff4' }, symbolSize: 7 }
      ]
    };
  });

  protected readonly riskChart = computed<EChartsCoreOption>(() => {
    const rows = this.lowStockRows().slice(0, 10);
    return {
      tooltip: { trigger: 'axis' },
      dataZoom: [{ type: 'inside' }],
      grid: { left: 18, right: 20, top: 24, bottom: 20, containLabel: true },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      yAxis: {
        type: 'category',
        data: rows.map(row => this.text(row, 'name')),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { width: 128, overflow: 'truncate' }
      },
      series: [{
        type: 'bar',
        data: rows.map(row => Math.max(this.num(row, 'min_stock') - this.num(row, 'total_stock'), 0)),
        barWidth: 14,
        itemStyle: { color: '#d99135', borderRadius: 8 }
      }]
    };
  });

  protected readonly supplierChart = computed<EChartsCoreOption>(() => {
    const counts = new Map<string, number>();
    for (const row of this.rows()) {
      const supplier = this.text(row, 'supplier_name', '未维护供应商');
      counts.set(supplier, (counts.get(supplier) ?? 0) + 1);
    }
    const data = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([name, value]) => ({ name, value }));
    return {
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom'),
      series: [
        compactPieSeries(data.length ? data : [{ name: '未维护供应商', value: 1 }])
      ]
    };
  });

  protected severity(value: unknown) {
    return statusSeverity(value);
  }
}
