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
import { DataRecord, ManufacturingCommandCenter } from '../core/models';
import { compactNumberText, emptyPageResult, numberOf, textOf } from './page-utils';

const EMPTY_COMMAND: ManufacturingCommandCenter = {
  kpis: { order_amount: 0, stock_quantity: 0, low_stock_products: 0, pending_purchase: 0, overdue_amount: 0 },
  warehouse_heat: [],
  flows: [],
  risks: []
};

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page dispatch-center-page">
      <header class="dispatch-hero atlas-split-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">调度控制</span>
          <h1>仓配调度中心</h1>
          <p>把工厂仓、区域仓、库位热区、调拨方向和低水位任务组织成一张可执行调度图。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="createDispatchTask()" [loading]="taskCreating()" aria-label="生成仓配调度任务">
              <i class="pi pi-directions"></i>
              生成调度任务
            </button>
            <button pButton type="button" severity="secondary" (click)="checkStockAlerts()" [loading]="checking()" aria-label="检查库存预警">
              <i class="pi pi-bell"></i>
              检查库存预警
            </button>
            <a pButton severity="info" routerLink="/app/inventory/stock">
              <i class="pi pi-database"></i>
              库存流水
            </a>
          </div>
        </div>

        <div class="dispatch-network">
          @for (node of warehouseNodes(); track node.name) {
            <button type="button" class="business-data-row" [class.active]="warehouseFilter() === node.name" (click)="toggleWarehouse(node.name)">
              <span>{{ node.name }}</span>
              <strong>{{ compactNumber(node.stock_quantity) }}</strong>
              <em>{{ node.slot_count }} 个库位</em>
            </button>
          }
        </div>

        <aside class="dispatch-kpi-stack">
          <article class="business-data-row">
            <span>库存总量</span>
            <strong>{{ compactNumber(command().kpis.stock_quantity) }}</strong>
          </article>
          <article class="business-data-row">
            <span>低水位</span>
            <strong>{{ command().kpis.low_stock_products }}</strong>
          </article>
          <article class="business-data-row">
            <span>今日流向</span>
            <strong>{{ command().flows.length }}</strong>
          </article>
        </aside>

        <nav class="governance-action-strip dispatch-action-strip" aria-label="仓配调度快捷动作">
          <a class="business-data-row" routerLink="/app/inventory/stock">库存流水</a>
          <a class="business-data-row" routerLink="/app/inventory/replenishment">补货建议</a>
          <a class="business-data-row" routerLink="/app/stocktakes">盘点中心</a>
          <a class="business-data-row" routerLink="/app/procurement/orders">采购到货</a>
          <a class="business-data-row" routerLink="/app/sales/orders">销售发货</a>
          <a class="business-data-row" routerLink="/app/mobile-terminal">移动扫码</a>
          <a class="business-data-row" routerLink="/app/reports">调度报表</a>
        </nav>
      </header>

      <section class="dispatch-grid">
        <article class="atlas-panel dispatch-map-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">流向图</span>
              <h2>仓配流向桑基图</h2>
            </div>
            <p-tag severity="info" value="可拖拽缩放" />
          </div>
          <div class="dispatch-chart" echarts [options]="flowChart()"></div>
        </article>

        <article class="atlas-panel dispatch-heat-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">库位热力</span>
              <h2>库位热区</h2>
            </div>
            <div class="atlas-filter compact">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="query = $event" placeholder="搜索物料、仓库、库位" />
            </div>
          </div>
          <div class="slot-heat-grid">
            @if (loading()) {
              <p-skeleton height="72px" />
              <p-skeleton height="72px" />
            } @else {
              @for (row of visibleStock().slice(0, 16); track row.id) {
                <a class="business-data-row" [routerLink]="['/app/inventory/stock', row.id]" [class.low]="number(row, 'quantity') <= 30">
                  <span>{{ text(row, 'shelf_location', '未分配') }}</span>
                  <strong>{{ text(row, 'product_name') }}</strong>
                  <em>{{ compactNumber(number(row, 'quantity')) }}</em>
                </a>
              }
            }
          </div>
        </article>

        <aside class="atlas-panel dispatch-task-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">调度队列</span>
              <h2>调度队列</h2>
            </div>
          </div>
          @for (risk of command().risks.slice(0, 5); track risk.title + risk.type) {
            <a class="business-data-row" [routerLink]="riskPath(risk)" [class.critical]="risk.level === 'critical'">
              <span>{{ risk.type }}</span>
              <strong>{{ risk.title }}</strong>
              <em>{{ risk.description }}</em>
            </a>
          }
          @if (!command().risks.length) {
            <div class="dispatch-task-empty">
              <strong>调度队列清爽</strong>
              <span>可继续检查库存预警或复核仓配流向。</span>
            </div>
          }
        </aside>
      </section>
    </section>
  `
})
export class DispatchCenterPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly checking = signal(false);
  protected readonly taskCreating = signal(false);
  protected readonly stock = signal<DataRecord[]>([]);
  protected readonly command = signal<ManufacturingCommandCenter>(EMPTY_COMMAND);
  protected readonly warehouseFilter = signal('');
  protected query = '';

  protected readonly warehouseNodes = computed(() => this.command().warehouse_heat);
  protected readonly visibleStock = computed(() => {
    const q = this.query.trim().toLowerCase();
    const warehouse = this.warehouseFilter();
    return this.stock().filter(row => {
      const haystack = [textOf(row, 'product_name'), textOf(row, 'product_sku'), textOf(row, 'warehouse_name'), textOf(row, 'shelf_location')].join(' ').toLowerCase();
      return (!warehouse || textOf(row, 'warehouse_name') === warehouse) && (!q || haystack.includes(q));
    });
  });
  protected readonly flowChart = computed(() => {
    const flows = this.command().flows.length ? this.command().flows : [
      { from: '供应商', to: '工厂仓', value: 1 },
      { from: '工厂仓', to: '区域仓', value: 1 },
      { from: '区域仓', to: '客户', value: 1 }
    ];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item', triggerOn: 'mousemove' },
      series: [{
        type: 'sankey',
        draggable: true,
        nodeGap: 18,
        nodeWidth: 14,
        lineStyle: { color: 'gradient', curveness: .55, opacity: .34 },
        itemStyle: { borderRadius: 8, color: '#62d8cb' },
        label: { color: 'inherit', fontWeight: 700 },
        data: [...new Set(flows.flatMap(item => [item.from, item.to]))].map(name => ({ name })),
        links: flows.map(item => ({ source: item.from, target: item.to, value: Math.max(1, item.value) }))
      }]
    };
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      stock: this.api.list<DataRecord>('stock', { page: 1, page_size: 24 }).pipe(catchError(() => of(emptyPageResult<DataRecord>()))),
      command: this.api.get<ManufacturingCommandCenter>('manufacturing/command-center').pipe(catchError(() => of(EMPTY_COMMAND)))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(({ stock, command }) => {
      this.stock.set(stock.items);
      this.command.set(command);
    });
  }

  toggleWarehouse(name: string): void {
    this.warehouseFilter.set(this.warehouseFilter() === name ? '' : name);
  }

  checkStockAlerts(): void {
    this.checking.set(true);
    this.api.post<{ created: number }>('stock-alerts/check', {}).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '预警检查未完成', detail: error?.message || '库存预警检查失败。' });
        return of(null);
      }),
      finalize(() => this.checking.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '库存预警已更新', detail: `生成或更新 ${result.created} 条预警。` });
        this.load();
      }
    });
  }

  createDispatchTask(): void {
    const risk = this.command().risks[0];
    this.taskCreating.set(true);
    this.api.post('bulk-actions', {
      action: 'operations.dispatch_task',
      ids: [Number(this.visibleStock()[0]?.id ?? 0)].filter(Boolean),
      params: {
      title: risk ? `仓配调度任务 - ${risk.title}` : '仓配调度任务',
      content: risk ? risk.description : '请复核仓配流向、库存预警和库位热区。',
      type: risk?.level === 'critical' ? 'alert' : 'warning',
      related_type: 'stock',
      related_id: this.visibleStock()[0]?.id
      }
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '调度任务未创建', detail: error?.message || '通知任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.taskCreating.set(false))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '调度任务已创建', detail: '任务已进入通知中心。' });
      }
    });
  }

  protected riskPath(risk: ManufacturingCommandCenter['risks'][number]): string {
    return risk.type.includes('应收') ? '/app/finance/receivables' : risk.type.includes('采购') ? '/app/procurement/orders' : '/app/inventory/replenishment';
  }

  protected text(row: DataRecord, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  protected number(row: DataRecord, key: string): number {
    return numberOf(row, key);
  }

  protected compactNumber(value: unknown): string {
    return compactNumberText(value);
  }
}
