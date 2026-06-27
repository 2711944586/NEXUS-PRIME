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
import { DataRecord, ManufacturingCommandCenter } from '../core/models';
import { CountUpNumberComponent, NexusRevealDirective, NexusSpotlightDirective, SceneBackgroundComponent } from '../motion';
import { compactNumberText, dateText, emptyPageResult, numberOf, statusSeverity, textOf } from './page-utils';
import { buildWarehouseNetwork } from './warehouse-flow-network';

const EMPTY_COMMAND: ManufacturingCommandCenter = {
  kpis: { order_amount: 0, stock_quantity: 0, low_stock_products: 0, pending_purchase: 0, overdue_amount: 0 },
  warehouse_heat: [],
  flows: [],
  risks: []
};

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    NgxEchartsDirective,
    ButtonModule,
    InputTextModule,
    ProgressBarModule,
    SkeletonModule,
    TagModule,
    SceneBackgroundComponent,
    NexusRevealDirective,
    NexusSpotlightDirective,
    CountUpNumberComponent
  ],
  template: `
    <section class="ops-atlas-page flow-console-page">
      <nexus-scene-background image="/images/warehouse-wide.jpg"></nexus-scene-background>

      <header class="flow-hero" nexusReveal [nexusRevealDelay]="60">
        <div class="hero-narrative">
          <span class="atlas-kicker">仓配流向</span>
          <h1>仓配流向图</h1>
          <p>把供应商到货、工厂仓入库、区域仓调拨、客户发货和库存流水放在同一张运营地图里追踪。</p>
          <div class="flow-hero-stats" aria-label="仓配网络概览">
            <span>
              <i class="pi pi-sitemap"></i>
              <strong>
                <nexus-count-up-number
                  [value]="network().summary.warehouseCount"
                  [compact]="false"
                  [maximumFractionDigits]="0"
                  suffix=" 座"
                  ariaLabel="覆盖仓库"
                ></nexus-count-up-number>
              </strong>
              覆盖仓库
            </span>
            <span class="warning">
              <i class="pi pi-bolt"></i>
              <strong>
                <nexus-count-up-number
                  [value]="network().summary.lowStockCount"
                  [compact]="false"
                  [maximumFractionDigits]="0"
                  suffix=" 项"
                  ariaLabel="低水位物料"
                ></nexus-count-up-number>
              </strong>
              低水位物料
            </span>
            <span>
              <i class="pi pi-sync"></i>
              <strong>
                <nexus-count-up-number
                  [value]="network().summary.totalThroughput"
                  [compact]="false"
                  [maximumFractionDigits]="0"
                  suffix=" 批"
                  ariaLabel="当班吞吐"
                ></nexus-count-up-number>
              </strong>
              当班吞吐
            </span>
          </div>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="createDispatchTask()" [loading]="taskCreating()" aria-label="创建仓配调度任务">
              <i class="pi pi-send"></i>
              创建调度任务
            </button>
            <button pButton type="button" severity="secondary" (click)="generateMovementReport()" [loading]="reporting()" aria-label="生成库存变动报表">
              <i class="pi pi-chart-line"></i>
              生成流向报表
            </button>
            <a pButton severity="info" routerLink="/app/stocktakes">
              <i class="pi pi-qrcode"></i>
              进入盘点
            </a>
          </div>
          <section class="flow-fast-lane" aria-label="仓配执行快线">
            <article>
              <span>库存水位</span>
              <strong>{{ network().summary.lowStockCount }} 项需复核</strong>
              <em>{{ network().summary.warehouseCount }} 座仓库在线</em>
            </article>
            <article>
              <span>当班吞吐</span>
              <strong>{{ network().summary.totalThroughput }} 批流转</strong>
              <em>调拨、入库、发货同步监控</em>
            </article>
            @for (link of fastLaneLinks(); track link.label) {
              <a class="business-data-row" [routerLink]="link.path">
                <span>{{ link.kicker }}</span>
                <strong>{{ link.label }}</strong>
                <em>{{ link.detail }}</em>
              </a>
            }
          </section>
        </div>

        <div class="flow-hero-map" aria-label="仓配链路" nexusReveal [nexusRevealDelay]="130" nexusSpotlight>
          @for (node of flowNodes(); track node.label) {
            <a class="business-data-row" [routerLink]="node.path" [class.warning]="node.tone === 'warning'">
              <span>{{ node.kicker }}</span>
              <strong>{{ node.label }}</strong>
              <em>{{ node.metric }}</em>
            </a>
          }
          <i class="flow-pulse p1"></i>
          <i class="flow-pulse p2"></i>
          <i class="flow-pulse p3"></i>
        </div>
      </header>

      <section class="atlas-panel flow-compact-workbench" aria-label="仓配流向执行摘要" nexusReveal [nexusRevealDelay]="140">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">执行摘要</span>
            <h2>节点、仓库与下一步</h2>
          </div>
        </div>
        <div class="flow-compact-grid">
          @for (node of flowNodes(); track node.label) {
            <a class="business-data-row" [routerLink]="node.path" [class.warning]="node.tone === 'warning'">
              <span>{{ node.kicker }}</span>
              <strong>{{ node.label }}</strong>
              <em>{{ node.metric }}</em>
            </a>
          }
          @for (warehouse of command().warehouse_heat; track warehouse.name) {
            <a class="business-data-row" routerLink="/app/inventory/stock">
              <span>{{ warehouse.name }}</span>
              <strong>{{ compactNumber(warehouse.stock_quantity) }}</strong>
              <em>{{ warehouse.slot_count }} 个库位</em>
            </a>
          }
        </div>
        <nav class="governance-action-strip" aria-label="仓配流向快捷动作">
          <a routerLink="/app/dispatch">调度中心</a>
          <a routerLink="/app/inventory/replenishment">补货建议</a>
          <a routerLink="/app/stocktakes">现场盘点</a>
          <a routerLink="/app/reports">流向报表</a>
        </nav>
      </section>

      <section class="flow-grid">
        <article class="atlas-panel flow-network-panel" nexusReveal [nexusRevealDelay]="160" nexusSpotlight>
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">实时网络</span>
              <h2>出入库与调拨流向</h2>
            </div>
            <div class="flow-chart-tabs">
              <button type="button" [class.active]="chartMode() === 'sankey'" (click)="chartMode.set('sankey')">链路</button>
              <button type="button" [class.active]="chartMode() === 'heat'" (click)="chartMode.set('heat')">热区</button>
              <button type="button" [class.active]="chartMode() === 'movement'" (click)="chartMode.set('movement')">流水</button>
            </div>
          </div>
          <div class="warehouse-network-map" aria-label="仓配节点网络">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="供应商、仓库、区域仓和客户之间的仓配流向">
              <defs>
                <linearGradient id="warehouse-network-flow" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="currentColor" stop-opacity=".12"></stop>
                  <stop offset="48%" stop-color="currentColor" stop-opacity=".9"></stop>
                  <stop offset="100%" stop-color="currentColor" stop-opacity=".12"></stop>
                </linearGradient>
              </defs>
              @for (link of network().links; track link.id) {
                <line
                  class="warehouse-network-link"
                  [class.warning]="link.tone === 'warning'"
                  [class.danger]="link.tone === 'danger'"
                  [attr.x1]="link.x1"
                  [attr.y1]="link.y1"
                  [attr.x2]="link.x2"
                  [attr.y2]="link.y2"
                  [attr.stroke-width]="link.width"
                ></line>
              }
            </svg>
            @for (node of network().nodes; track node.id) {
              <a
                class="warehouse-network-node business-data-row"
                [class.warning]="node.tone === 'warning'"
                [class.danger]="node.tone === 'danger'"
                [class.supplier]="node.kind === 'supplier'"
                [class.customer]="node.kind === 'customer'"
                [routerLink]="node.path"
                [style.--node-x]="node.x + '%'"
                [style.--node-y]="node.y + '%'"
              >
                <span>{{ node.kicker }}</span>
                <strong>{{ node.label }}</strong>
                <em>{{ node.metric }}</em>
                <small>{{ node.detail }}</small>
              </a>
            }
          </div>
          <div class="flow-main-chart" echarts [options]="activeChart()"></div>
        </article>

        <aside class="atlas-panel flow-warehouse-panel" nexusReveal [nexusRevealDelay]="210" nexusSpotlight>
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">仓库</span>
              <h2>仓库负载</h2>
            </div>
          </div>
          <div class="warehouse-load-list">
            @for (warehouse of command().warehouse_heat; track warehouse.name) {
              <a class="business-data-row" routerLink="/app/inventory/stock">
                <span>{{ warehouse.name }}</span>
                <strong>{{ compactNumber(warehouse.stock_quantity) }}</strong>
                <p-progressbar [value]="loadRate(warehouse.stock_quantity)" [showValue]="false" />
                <em>{{ warehouse.slot_count }} 个库位记录</em>
              </a>
            }
          </div>
        </aside>

        <article class="atlas-panel flow-ledger-wide" nexusReveal [nexusRevealDelay]="240">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">库存账本</span>
              <h2>库存流水</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="onQuery($event)" placeholder="搜索物料、仓库、库位" />
            </div>
          </div>

          @if (loading()) {
            <p-skeleton height="78px" />
            <p-skeleton height="78px" />
          } @else {
            <div class="atlas-record-ledger">
              @for (row of pagedStock(); track row.id) {
                <a class="atlas-record-row" [routerLink]="['/app/inventory/stock', row.id]" [class.warning]="isLowRow(row)">
                  <span class="record-code">{{ text(row, 'product_sku') }}</span>
                  <strong>{{ text(row, 'product_name') }}</strong>
                  <em>{{ text(row, 'warehouse_name') }} / {{ text(row, 'shelf_location') }}</em>
                  <b>{{ text(row, 'quantity') }} 件</b>
                  <p-tag [severity]="isLowRow(row) ? 'warn' : 'success'" [value]="isLowRow(row) ? '低水位' : '稳定'" />
                </a>
              }
            </div>
            @if (filteredStock().length > pageSize()) {
              <div class="atlas-pagination" aria-label="库存流水分页">
                <button type="button" (click)="setPage(page() - 1)" [disabled]="page() <= 1">
                  <i class="pi pi-angle-left"></i>
                  上一页
                </button>
                <span>第 <strong>{{ page() }}</strong> / {{ totalPages() }} 页 · {{ filteredStock().length }} 条</span>
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

        <aside class="atlas-panel flow-risk-panel" nexusReveal [nexusRevealDelay]="280" nexusSpotlight>
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">调度队列</span>
              <h2>调度优先级</h2>
            </div>
          </div>
          <div class="flow-risk-stack">
            @for (risk of command().risks.slice(0, 7); track risk.title + risk.type) {
              <a class="business-data-row" [routerLink]="riskPath(risk)" [class.critical]="risk.level === 'critical'">
                <p-tag [severity]="risk.level === 'critical' ? 'danger' : 'warn'" [value]="risk.type" />
                <strong>{{ risk.title }}</strong>
                <span>{{ risk.description }}</span>
              </a>
            }
          </div>
        </aside>
      </section>
    </section>
  `
})
export class WarehouseFlowPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly taskCreating = signal(false);
  protected readonly reporting = signal(false);
  protected readonly command = signal<ManufacturingCommandCenter>(EMPTY_COMMAND);
  protected readonly stock = signal<DataRecord[]>([]);
  protected readonly chartMode = signal<'sankey' | 'heat' | 'movement'>('sankey');
  protected readonly pageSize = signal(12);
  protected readonly page = signal(1);
  protected pageInput = '1';
  protected query = '';
  protected readonly network = computed(() => buildWarehouseNetwork(this.command(), this.stock()));

  protected readonly filteredStock = computed(() => {
    const q = this.query.trim().toLowerCase();
    if (!q) {
      return this.stock();
    }
    return this.stock().filter(row => [
      textOf(row, 'product_name'),
      textOf(row, 'product_sku'),
      textOf(row, 'warehouse_name'),
      textOf(row, 'shelf_location')
    ].join(' ').toLowerCase().includes(q));
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.filteredStock().length / this.pageSize())));
  protected readonly pagedStock = computed(() => {
    const start = (this.page() - 1) * this.pageSize();
    return this.filteredStock().slice(start, start + this.pageSize());
  });
  protected readonly flowNodes = computed(() => [
    { kicker: '01', label: '供应商到货', metric: `${this.command().flows[0]?.value ?? 0} 批`, path: '/app/procurement/orders', tone: 'success' },
    { kicker: '02', label: this.command().warehouse_heat[0]?.name ?? '工厂仓', metric: this.compactNumber(this.command().warehouse_heat[0]?.stock_quantity ?? 0), path: '/app/inventory/stock', tone: 'success' },
    { kicker: '03', label: this.command().warehouse_heat[1]?.name ?? '区域仓', metric: `${this.command().flows[1]?.value ?? 0} 单调拨`, path: '/app/dispatch', tone: 'warning' },
    { kicker: '04', label: '客户发货', metric: `${this.command().flows[2]?.value ?? 0} 单`, path: '/app/sales/orders', tone: 'success' }
  ]);
  protected readonly fastLaneLinks = computed(() => [
    { kicker: '调度', label: '调度中心', detail: `${this.command().risks.length} 个优先事项`, path: '/app/dispatch' },
    { kicker: '补货', label: '补货建议', detail: `${this.command().kpis.low_stock_products ?? 0} 项低水位`, path: '/app/inventory/replenishment' },
    { kicker: '盘点', label: '现场盘点', detail: `${this.stock().length} 条库存样本`, path: '/app/stocktakes' },
    { kicker: '采购', label: '采购订单', detail: `${this.command().kpis.pending_purchase ?? 0} 单待跟进`, path: '/app/procurement/orders' },
    { kicker: '销售', label: '销售订单', detail: this.compactNumber(this.command().kpis.order_amount), path: '/app/sales/orders' },
    { kicker: '移动', label: '移动扫码', detail: '入库、移库、发货扫码', path: '/app/mobile-terminal' },
    { kicker: '资料', label: '仓配资料', detail: '凭证、照片、附件归档', path: '/app/files' },
    { kicker: '报表', label: '流向报表', detail: '库存流水与吞吐趋势', path: '/app/reports' }
  ]);
  protected readonly activeChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'heat') {
      return this.heatChart();
    }
    if (this.chartMode() === 'movement') {
      return this.movementChart();
    }
    return this.sankeyChart();
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      command: this.api.get<ManufacturingCommandCenter>('manufacturing/command-center').pipe(catchError(() => of(EMPTY_COMMAND))),
      stock: this.api.list<DataRecord>('stock', { page: 1, page_size: 24, sort: 'updated_at', order: 'desc' }).pipe(catchError(() => of(emptyPageResult<DataRecord>())))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(({ command, stock }) => {
      this.command.set(command);
      this.stock.set(stock.items);
      this.setPage(1);
    });
  }

  createDispatchTask(): void {
    this.taskCreating.set(true);
    this.api.post('operations/dispatch-task', {
      title: '仓配流向复核任务',
      content: '复核工厂仓、区域仓、客户发货和低库存补货节点，更新调拨优先级。',
      related_type: 'stock'
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '任务未创建', detail: error?.message || '调度任务未写入。' });
        return of(null);
      }),
      finalize(() => this.taskCreating.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '调度任务已创建', detail: '已进入通知中心。' });
      }
    });
  }

  generateMovementReport(): void {
    this.reporting.set(true);
    this.api.post('reports/generate/inventory_movement', { params: {} }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '报表未生成', detail: error?.message || '流向报表生成失败。' });
        return of(null);
      }),
      finalize(() => this.reporting.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '流向报表已生成', detail: '可在报表工作室查看。' });
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

  isLowRow(row: DataRecord): boolean {
    return numberOf(row, 'quantity') < 40;
  }

  loadRate(value: number): number {
    const max = Math.max(...this.command().warehouse_heat.map(item => item.stock_quantity), 1);
    return Math.max(6, Math.round((value / max) * 100));
  }

  riskPath(risk: ManufacturingCommandCenter['risks'][number]): string {
    if (risk.type.includes('应收')) {
      return '/app/finance/receivables';
    }
    if (risk.type.includes('采购')) {
      return '/app/procurement/orders';
    }
    return '/app/inventory/replenishment';
  }

  text(row: DataRecord, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  date(value: unknown): string {
    return dateText(value);
  }

  severity(value: unknown) {
    return statusSeverity(value);
  }

  compactNumber(value: unknown): string {
    return compactNumberText(value);
  }

  private sankeyChart(): EChartsCoreOption {
    const flows = this.command().flows.length ? this.command().flows : [
      { from: '供应商', to: '工厂仓', value: 1 },
      { from: '工厂仓', to: '区域仓', value: 1 },
      { from: '区域仓', to: '客户', value: 1 }
    ];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      series: [{
        type: 'sankey',
        draggable: true,
        nodeWidth: 18,
        nodeGap: 26,
        layoutIterations: 24,
        lineStyle: { color: 'gradient', curveness: .56, opacity: .34 },
        itemStyle: { borderRadius: 10, borderWidth: 0, color: '#4bb5a9' },
        label: { color: 'inherit', fontWeight: 700 },
        data: [...new Set(flows.flatMap(item => [item.from, item.to]))].map(name => ({ name })),
        links: flows.map(item => ({ source: item.from, target: item.to, value: Math.max(1, item.value) }))
      }]
    };
  }

  private heatChart(): EChartsCoreOption {
    const rows = this.command().warehouse_heat.length ? this.command().warehouse_heat : [{ name: '仓库', stock_quantity: 0, slot_count: 0 }];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 26, right: 18, top: 24, bottom: 34, containLabel: true },
      xAxis: { type: 'category', data: rows.map(item => item.name), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { rotate: 10, color: '#667085' } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } } },
      series: [{
        type: 'bar',
        name: '库存量',
        data: rows.map(item => item.stock_quantity),
        barWidth: 28,
        itemStyle: {
          borderRadius: [12, 12, 3, 3],
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [{ offset: 0, color: '#6aa8ff' }, { offset: 1, color: '#6ee7d8' }]
          }
        }
      }]
    };
  }

  private movementChart(): EChartsCoreOption {
    const rows = this.stock().slice(0, 18);
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      dataZoom: [{ type: 'inside' }],
      grid: { left: 26, right: 18, top: 28, bottom: 28, containLabel: true },
      xAxis: { type: 'category', data: rows.map(row => textOf(row, 'product_name')).reverse(), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { width: 86, overflow: 'truncate', rotate: 18 } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } } },
      series: [{
        type: 'line',
        smooth: true,
        symbolSize: 7,
        data: rows.map(row => numberOf(row, 'quantity')).reverse(),
        lineStyle: { width: 3, color: '#4bb5a9' },
        areaStyle: { color: 'rgba(75,181,169,.16)' }
      }]
    };
  }
}
