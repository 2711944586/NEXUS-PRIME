import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { NgxEchartsDirective } from 'ngx-echarts';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { ProgressBarModule } from 'primeng/progressbar';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, forkJoin, of, switchMap } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DataRecord, SupplierCollaborationPayload, SupplierCollaborationQueueItem } from '../core/models';
import { chartLegend, compactMoneyText, dateText, emptyPageResult, moneyText, numberOf, percentNumber, recordTitle, statusSeverity, TagSeverity, textOf } from './page-utils';

const EMPTY_SUPPLIER_COLLABORATION: SupplierCollaborationPayload = {
  generated_at: '',
  source: 'supplier_collaboration_contract',
  summary: {
    network_score: 0,
    active_suppliers: 0,
    preferred_suppliers: 0,
    risk_suppliers: 0,
    qualification_due: 0,
    pending_orders: 0,
    delivery_due: 0,
    quality_watch: 0,
    open_tasks: 0,
    spend_amount: 0,
    p0: 0,
    p1: 0,
    queue_count: 0,
    primary_owner: '供应商经理',
    next_action: '等待供应商协同数据。'
  },
  collaboration_lanes: [],
  supplier_cards: [],
  risk_queue: [],
  qualification_queue: [],
  delivery_windows: [],
  supplier_matrix: [],
  collaboration_flow: [],
  service_boundaries: [],
  deployment_checks: [],
  runbook: []
};

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page supplier-performance-page">
      <header class="supplier-hero atlas-split-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">供应商协同网络</span>
          <h1>供应商协同与资质风险工作台</h1>
          <p>把供应商准入、交付 SLA、质量 CAPA、采购集中度和协同任务压到同一个可执行控制面。</p>
          <div class="atlas-actions-row">
            <button
              pButton
              type="button"
              severity="contrast"
              (click)="createSupplierTask(primarySupplierTask())"
              [disabled]="!primarySupplierTask() || creatingTaskId() !== null"
              aria-label="创建首要供应商协同任务"
            >
              <i class="pi pi-send"></i>
              创建协同任务
            </button>
            <button pButton type="button" (click)="generateReport()" [loading]="generating()" aria-label="生成供应商绩效报表">
              <i class="pi pi-chart-line"></i>
              生成绩效报表
            </button>
            <button pButton type="button" severity="secondary" (click)="createPurchaseFromBest()" aria-label="基于优选供应商创建采购草稿">
              <i class="pi pi-shopping-cart"></i>
              创建采购草稿
            </button>
            <a pButton severity="info" routerLink="/app/procurement/orders">
              <i class="pi pi-check-circle"></i>
              采购审批
            </a>
          </div>
        </div>

        <div class="supplier-score-board">
          <article>
            <span>网络评分</span>
            <strong>{{ controlSummary().network_score }}%</strong>
            <em>{{ controlSummary().primary_owner }}</em>
          </article>
          <article>
            <span>活跃供应商</span>
            <strong>{{ controlSummary().active_suppliers || rows().length }}</strong>
            <em>{{ controlSummary().preferred_suppliers }} 家优选</em>
          </article>
          <article>
            <span>P0 / P1</span>
            <strong>{{ controlSummary().p0 }} / {{ controlSummary().p1 }}</strong>
            <em>{{ controlSummary().queue_count }} 个协同项</em>
          </article>
          <article>
            <span>采购暴露</span>
            <strong>{{ compactMoney(controlSummary().spend_amount || totalAmount()) }}</strong>
            <em>{{ controlSummary().pending_orders }} 单未完</em>
          </article>
        </div>

        <aside class="supplier-radar-card">
          <span>绩效雷达</span>
          <div class="supplier-radar" echarts [options]="radarChart()"></div>
        </aside>
      </header>

      <section class="supplier-command-grid" aria-label="供应商协同控制层">
        <article class="atlas-panel supplier-lane-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">Supplier 360</span>
              <h2>资质、交付、质量和商务集中度</h2>
            </div>
            <p-tag [severity]="controlSummary().p0 ? 'danger' : controlSummary().p1 ? 'warn' : 'success'" [value]="controlSummary().queue_count + ' 项'" />
          </div>
          <p class="supplier-next-action">{{ controlSummary().next_action }}</p>
          <div class="supplier-lane-strip">
            @for (lane of control().collaboration_lanes; track lane.id) {
              <a [routerLink]="lane.path" [class.blocked]="lane.status === 'blocked'" [class.attention]="lane.status === 'attention'">
                <span>{{ lane.label }} · {{ lane.owner }}</span>
                <strong>{{ lane.score }}%</strong>
                <p-progressbar [value]="bounded(lane.score)" [showValue]="false" />
                <em>{{ lane.active_count }} 项 · {{ lane.sla }}</em>
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel supplier-task-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">协同队列</span>
              <h2>可派发供应商任务</h2>
            </div>
          </div>
          <div class="supplier-task-stack">
            @for (item of riskQueue().slice(0, 8); track item.id) {
              <article [class.blocked]="item.priority === 'P0'" [class.attention]="item.priority === 'P1'">
                <div>
                  <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
                  <span>{{ item.kind }} · {{ item.owner }} · {{ item.sla }}</span>
                </div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.evidence }}</p>
                <footer>
                  <a [routerLink]="cleanPath(item.path)">{{ item.metric }}</a>
                  <button type="button" (click)="createSupplierTask(item)" [disabled]="creatingTaskId() === item.id">
                    <i class="pi" [class.pi-spin]="creatingTaskId() === item.id" [class.pi-spinner]="creatingTaskId() === item.id" [class.pi-send]="creatingTaskId() !== item.id"></i>
                    任务
                  </button>
                </footer>
              </article>
            }
          </div>
        </article>
      </section>

      <section class="supplier-360-grid" aria-label="供应商 360 卡片">
        @for (card of supplierCards().slice(0, 8); track card.id) {
          <article class="supplier-360-card" [class.blocked]="card.status === 'blocked'" [class.attention]="card.status === 'attention'">
            <div class="supplier-360-head">
              <p-tag [severity]="prioritySeverity(card.priority)" [value]="card.priority" />
              <span>{{ card.owner }}</span>
            </div>
            <strong>{{ card.name }}</strong>
            <em>{{ card.contact || '联系人待维护' }} · {{ card.email || '邮箱待维护' }}</em>
            <div class="supplier-360-metrics">
              <span><b>{{ card.score }}%</b>综合</span>
              <span><b>{{ card.on_time_rate }}%</b>准点</span>
              <span><b>{{ card.quality_rate }}%</b>质量</span>
              <span><b>{{ card.spend_share }}%</b>占比</span>
            </div>
            <p>{{ card.action }}</p>
          </article>
        }
      </section>

      <section class="supplier-collaboration-grid" aria-label="供应商交付和服务边界">
        <article class="atlas-panel supplier-delivery-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">交付 SLA</span>
              <h2>采购承诺与到货窗口</h2>
            </div>
          </div>
          <div class="supplier-delivery-list">
            @for (item of deliveryWindows(); track item.id) {
              <a [routerLink]="cleanPath(item.path)" [class.blocked]="item.status === 'blocked'" [class.attention]="item.status === 'attention'">
                <div>
                  <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
                  <strong>{{ item.po_no }}</strong>
                  <span>{{ item.supplier }} / {{ item.warehouse }}</span>
                </div>
                <p-progressbar [value]="bounded(item.progress)" [showValue]="false" />
                <em>{{ item.progress }}% · {{ item.days_to_due }}d · {{ compactMoney(item.amount) }}</em>
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel supplier-boundary-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">服务边界</span>
              <h2>供应商微服务拆分面</h2>
            </div>
          </div>
          <div class="supplier-boundary-list">
            @for (item of control().service_boundaries; track item.service) {
              <article [class.blocked]="item.readiness === 'blocked'" [class.attention]="item.readiness === 'attention'">
                <p-tag [severity]="statusTone(item.readiness)" [value]="item.readiness" />
                <strong>{{ item.service }}</strong>
                <span>{{ item.deploy_unit }} / {{ item.owner }}</span>
                <p>{{ item.contract }}</p>
              </article>
            }
          </div>
          <div class="supplier-deploy-checks">
            @for (check of control().deployment_checks; track check.key) {
              <div>
                <i class="pi" [class.pi-check-circle]="check.status === 'ready'" [class.pi-exclamation-triangle]="check.status !== 'ready'"></i>
                <strong>{{ check.label }}</strong>
                <span>{{ check.owner }} · {{ check.evidence }}</span>
              </div>
            }
          </div>
        </article>

        <article class="atlas-panel supplier-flow-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">协同流程</span>
              <h2>从准入到绩效回写</h2>
            </div>
          </div>
          <div class="supplier-flow-list">
            @for (item of control().collaboration_flow; track item.step) {
              <article>
                <i>{{ $index + 1 }}</i>
                <div>
                  <strong>{{ item.step }}</strong>
                  <span>{{ item.detail }}</span>
                </div>
              </article>
            }
          </div>
        </article>
      </section>

      <section class="supplier-grid">
        <article class="atlas-panel supplier-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">绩效</span>
              <h2>准点与质量对比</h2>
            </div>
            <div class="chart-tabs">
              <button type="button" [class.active]="chartMode() === 'score'" (click)="chartMode.set('score')">评分</button>
              <button type="button" [class.active]="chartMode() === 'amount'" (click)="chartMode.set('amount')">金额</button>
            </div>
          </div>
          <div class="supplier-chart" echarts [options]="activeChart()"></div>
        </article>

        <aside class="atlas-panel supplier-action-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">行动队列</span>
              <h2>供应链动作</h2>
            </div>
          </div>
          @for (item of actionQueue(); track item.title) {
            <a [routerLink]="item.path" [class.warning]="item.tone === 'warning'">
              <span>{{ item.metric }}</span>
              <strong>{{ item.title }}</strong>
              <em>{{ item.body }}</em>
            </a>
          }
        </aside>
      </section>

      <section class="atlas-panel supplier-ledger-panel">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">供应商账本</span>
            <h2>供应商绩效账本</h2>
          </div>
          <div class="atlas-filter">
            <i class="pi pi-search"></i>
            <input pInputText [ngModel]="query" (ngModelChange)="query = $event" placeholder="搜索供应商、联系人、邮箱" />
          </div>
          <button pButton type="button" [text]="true" (click)="load()" aria-label="刷新供应商绩效">
            <i class="pi pi-refresh"></i>
          </button>
        </div>

        @if (loading()) {
          <p-skeleton height="74px" />
          <p-skeleton height="74px" />
          <p-skeleton height="74px" />
        } @else if (error()) {
          <div class="empty-state">
            <i class="pi pi-cloud"></i>
            <strong>供应商绩效数据通道未连接</strong>
            <p>{{ error() }}</p>
            <button pButton type="button" (click)="load()">重试</button>
          </div>
        } @else {
          <div class="atlas-record-ledger">
            @for (row of visibleRows(); track row.id) {
              <a class="atlas-record-row" routerLink="/app/procurement/orders" [queryParams]="{ supplier: row['supplier_id'] }">
                <span class="record-code">{{ text(row, 'supplier_name') }}</span>
                <strong>{{ recordName(row) }}</strong>
                <em>{{ text(row, 'contact_person', '未维护联系人') }} / {{ date(row['last_order_date']) }}</em>
                <b>{{ money(row['total_amount']) }}</b>
                <p-tag [severity]="scoreSeverity(row)" [value]="scoreLabel(row)" />
              </a>
            }
          </div>
        }
      </section>
    </section>
  `
})
export class SupplierPerformancePage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly rows = signal<DataRecord[]>([]);
  protected readonly loading = signal(false);
  protected readonly generating = signal(false);
  protected readonly creatingTaskId = signal<string | null>(null);
  protected readonly error = signal('');
  protected readonly control = signal<SupplierCollaborationPayload>(EMPTY_SUPPLIER_COLLABORATION);
  protected readonly chartMode = signal<'score' | 'amount'>('score');
  protected query = '';

  protected readonly visibleRows = computed(() => {
    const q = this.query.trim().toLowerCase();
    if (!q) {
      return this.rows();
    }
    return this.rows().filter(row => [textOf(row, 'supplier_name'), textOf(row, 'contact_person'), textOf(row, 'email')].join(' ').toLowerCase().includes(q));
  });
  protected readonly totalAmount = computed(() => this.rows().reduce((sum, row) => sum + numberOf(row, 'total_amount'), 0));
  protected readonly avgOnTime = computed(() => this.avg('on_time_rate'));
  protected readonly avgQuality = computed(() => this.avg('quality_rate'));
  protected readonly controlSummary = computed(() => this.control().summary);
  protected readonly supplierCards = computed(() => this.control().supplier_cards);
  protected readonly riskQueue = computed(() => this.control().risk_queue);
  protected readonly deliveryWindows = computed(() => this.control().delivery_windows.slice(0, 8));
  protected readonly primarySupplierTask = computed(() => this.riskQueue()[0]);
  protected readonly actionQueue = computed(() => [
    { title: '待审批采购', metric: `${this.controlSummary().pending_orders || this.rows().reduce((sum, row) => sum + numberOf(row, 'pending_orders'), 0)} 单`, body: '供应商表现会影响审批优先级', path: '/app/procurement/orders', tone: 'warning' },
    { title: '补货建议', metric: '低水位', body: '把低库存物料转成采购草稿', path: '/app/inventory/replenishment', tone: 'warning' },
    { title: '供应商报表', metric: `${this.rows().length} 档`, body: '生成后进入报表归档', path: '/app/reports', tone: 'success' }
  ]);
  protected readonly activeChart = computed(() => this.chartMode() === 'amount' ? this.amountChart() : this.scoreChart());
  protected readonly scoreChart = computed(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: chartLegend('top'),
    grid: { left: 24, right: 18, top: 42, bottom: 34, containLabel: true },
    xAxis: { type: 'category', data: this.visibleRows().slice(0, 8).map(row => textOf(row, 'supplier_name')), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { interval: 0, rotate: 16 } },
    yAxis: { type: 'value', max: 100, splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
    series: [
      { name: '准点率', type: 'bar', data: this.visibleRows().slice(0, 8).map(row => numberOf(row, 'on_time_rate')), barWidth: 18, itemStyle: { color: '#62d8cb', borderRadius: [8, 8, 2, 2] } },
      { name: '质量率', type: 'bar', data: this.visibleRows().slice(0, 8).map(row => numberOf(row, 'quality_rate')), barWidth: 18, itemStyle: { color: '#9aa8ff', borderRadius: [8, 8, 2, 2] } }
    ]
  }));
  protected readonly amountChart = computed(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    series: [{
      type: 'treemap',
      roam: false,
      breadcrumb: { show: false },
      label: { formatter: '{b}' },
      itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.52)' },
      data: this.visibleRows().slice(0, 12).map(row => ({ name: textOf(row, 'supplier_name'), value: Math.max(1, numberOf(row, 'total_amount')) }))
    }]
  }));
  protected readonly radarChart = computed(() => ({
    backgroundColor: 'transparent',
    radar: {
      radius: '66%',
      indicator: [
        { name: '准点', max: 100 },
        { name: '质量', max: 100 },
        { name: '信用', max: 100 },
        { name: '活跃', max: 100 }
      ]
    },
    series: [{
      type: 'radar',
      areaStyle: { color: 'rgba(98,216,203,.2)' },
      lineStyle: { color: '#62d8cb', width: 3 },
      data: [{ value: [this.avgOnTime(), this.avgQuality(), this.avg('credit_score'), Math.min(100, this.rows().length * 8)] }]
    }]
  }));

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    forkJoin({
      rows: this.api.list<DataRecord>('supplier-performance', { page: 1, page_size: 80 }).pipe(
        catchError(error => {
          this.error.set(error?.message || '无法读取供应商绩效数据。');
          return of(emptyPageResult<DataRecord>());
        })
      ),
      control: this.api.get<SupplierCollaborationPayload>('operations/supplier-collaboration').pipe(
        catchError(error => {
          this.messages.add({ severity: 'warn', summary: '供应商协同台未加载', detail: error?.message || '请稍后重试。' });
          return of(EMPTY_SUPPLIER_COLLABORATION);
        })
      )
    }).pipe(
      finalize(() => this.loading.set(false))
    ).subscribe(({ rows, control }) => {
      this.rows.set(rows.items);
      this.control.set(control);
    });
  }

  generateReport(): void {
    this.generating.set(true);
    this.api.post<{ report: DataRecord }>('reports/generate/supplier_performance', { params: {} }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '报表未生成', detail: error?.message || '供应商报表生成失败。' });
        return of(null);
      }),
      finalize(() => this.generating.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '供应商报表已生成', detail: recordTitle(result.report) });
      }
    });
  }

  createPurchaseFromBest(): void {
    const supplier = this.visibleRows()[0];
    const supplierId = Number(supplier?.['supplier_id'] ?? 0);
    if (!supplierId) {
      this.messages.add({ severity: 'warn', summary: '采购草稿未创建', detail: '当前没有可用供应商。' });
      return;
    }
    forkJoin({
      products: this.api.lookup('lookups/products'),
      warehouses: this.api.lookup('lookups/warehouses')
    }).pipe(
      switchMap(({ products, warehouses }) => {
        const product = products[0];
        const warehouse = warehouses[0];
        if (!product?.id || !warehouse?.id) {
          this.messages.add({ severity: 'warn', summary: '采购草稿未创建', detail: '缺少物料或收货仓库。' });
          return of(null);
        }
        return this.api.post<DataRecord>('purchase-orders', {
          supplier_id: supplierId,
          warehouse_id: warehouse.id,
          items: [{
            product_id: product.id,
            quantity: 24,
            unit_price: product.cost || product.price || 100
          }],
          remark: `供应商绩效中心创建：${textOf(supplier, 'supplier_name')}`
        });
      }),
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '采购草稿未创建', detail: error?.message || '采购单未写入数据库。' });
        return of(null);
      })
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '采购草稿已创建', detail: recordTitle(result) });
      }
    });
  }

  protected createSupplierTask(item?: SupplierCollaborationQueueItem): void {
    if (!item) {
      this.messages.add({ severity: 'info', summary: '供应商协同', detail: '当前没有可创建的供应商任务。' });
      return;
    }
    this.creatingTaskId.set(item.id);
    this.api.post('operations/supplier-collaboration/task', {
      queue_item_id: item.id,
      supplier_id: item.supplier_id,
      title: item.title,
      owner: item.owner,
      priority: item.priority,
      sla: item.sla,
      evidence: item.evidence,
      action: item.action,
      path: item.path,
      kind: item.kind
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '供应商任务未创建', detail: error?.message || '任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.creatingTaskId.set(null))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '供应商任务已创建', detail: `${item.title} 已进入任务异常中心。` });
      }
    });
  }

  private avg(key: string): number {
    const rows = this.rows();
    if (!rows.length) {
      return 0;
    }
    return percentNumber(rows.reduce((sum, row) => sum + numberOf(row, key), 0) / rows.length);
  }

  protected text(row: DataRecord, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  protected recordName(row: DataRecord): string {
    return textOf(row, 'supplier_name', recordTitle(row));
  }

  protected date(value: unknown): string {
    return dateText(value);
  }

  protected money(value: unknown): string {
    return moneyText(value);
  }

  protected compactMoney(value: unknown): string {
    return compactMoneyText(value);
  }

  protected bounded(value: unknown): number {
    return Math.max(0, Math.min(100, Number(value) || 0));
  }

  protected cleanPath(path: string | null | undefined): string {
    return path || '/app/suppliers/performance';
  }

  protected prioritySeverity(priority: string): TagSeverity {
    if (priority === 'P0' || priority === 'blocked') {
      return 'danger';
    }
    if (priority === 'P1' || priority === 'attention') {
      return 'warn';
    }
    return 'success';
  }

  protected statusTone(status: string): TagSeverity {
    return statusSeverity(status);
  }

  protected scoreLabel(row: DataRecord): string {
    const score = Math.round((numberOf(row, 'on_time_rate') + numberOf(row, 'quality_rate')) / 2);
    return score >= 90 ? '优选' : score >= 78 ? '观察' : '风险';
  }

  protected scoreSeverity(row: DataRecord): 'success' | 'warn' | 'danger' {
    const score = Math.round((numberOf(row, 'on_time_rate') + numberOf(row, 'quality_rate')) / 2);
    return score >= 90 ? 'success' : score >= 78 ? 'warn' : 'danger';
  }
}
