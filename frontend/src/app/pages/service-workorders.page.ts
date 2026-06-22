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
import { DataRecord } from '../core/models';
import { chartLegend, compactMoneyText, compactNumberText, emptyPageResult, numberOf, percentNumber, recordTitle, statusLabel, statusSeverity, textOf } from './page-utils';

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page service-workorders-page">
      <header class="service-hero atlas-split-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">服务运营</span>
          <h1>售后服务中心</h1>
          <p>客户订单、发货状态、服务资料、备件水位和回访任务形成可追踪服务工单。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="createServiceTask()" [loading]="taskCreating()" aria-label="创建售后服务工单">
              <i class="pi pi-comments"></i>
              创建服务工单
            </button>
            <button pButton type="button" severity="secondary" (click)="generateReport()" [loading]="reporting()" aria-label="生成售后服务报表">
              <i class="pi pi-chart-line"></i>
              生成服务报表
            </button>
            <a pButton severity="info" routerLink="/app/files">
              <i class="pi pi-folder-open"></i>
              服务资料
            </a>
          </div>
        </div>

        <div class="service-kpi-grid">
          <article class="business-data-row">
            <span>可服务订单</span>
            <strong>{{ serviceOrders().length }}</strong>
            <em>已付款/发货/完成</em>
          </article>
          <article class="business-data-row">
            <span>服务客户</span>
            <strong>{{ customerCount() }}</strong>
            <em>订单关联</em>
          </article>
          <article class="business-data-row">
            <span>低水位备件</span>
            <strong>{{ lowParts().length }}</strong>
            <em>影响响应</em>
          </article>
          <article class="business-data-row">
            <span>服务资料</span>
            <strong>{{ files().length }}</strong>
            <em>SOP 与附件</em>
          </article>
        </div>

        <aside class="service-score-card business-data-row">
          <span>响应就绪</span>
          <strong>{{ readiness() }}%</strong>
          <p-progressbar [value]="readiness()" [showValue]="false" />
          <em>{{ notifications().length }} 条服务任务 · {{ lowParts().length }} 项备件关注</em>
        </aside>
      </header>

      <section class="service-grid">
        <article class="atlas-panel service-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">服务分析</span>
              <h2>{{ chartTitle() }}</h2>
            </div>
            <div class="chart-tabs">
              <button type="button" [class.active]="chartMode() === 'orders'" (click)="chartMode.set('orders')">订单</button>
              <button type="button" [class.active]="chartMode() === 'parts'" (click)="chartMode.set('parts')">备件</button>
              <button type="button" [class.active]="chartMode() === 'files'" (click)="chartMode.set('files')">资料</button>
            </div>
          </div>
          <div class="service-chart" echarts [options]="activeChart()"></div>
        </article>

        <aside class="atlas-panel service-action-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">服务队列</span>
              <h2>服务动作队列</h2>
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

        <article class="atlas-panel service-ledger-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">服务账本</span>
              <h2>售后订单账本</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="setQuery($event)" placeholder="搜索订单、客户、状态" />
            </div>
            <button pButton type="button" [text]="true" (click)="load()" aria-label="刷新服务数据">
              <i class="pi pi-refresh"></i>
            </button>
          </div>

          @if (loading()) {
            <p-skeleton height="76px" />
            <p-skeleton height="76px" />
            <p-skeleton height="76px" />
          } @else {
            <div class="atlas-record-ledger">
              @for (row of pagedOrders(); track row.id) {
                <a class="atlas-record-row business-data-row" [routerLink]="['/app/sales/orders', row.id]">
                  <span class="record-code">{{ text(row, 'order_no') }}</span>
                  <strong>{{ text(row, 'customer_name', '未关联客户') }}</strong>
                  <em>{{ status(row['status']) }} / 服务金额 {{ compactMoney(row['total_amount']) }}</em>
                  <b>{{ serviceLevel(row) }}</b>
                  <p-tag [severity]="severity(row['status'])" [value]="status(row['status'])" />
                </a>
              }
            </div>
            <div class="atlas-pagination" aria-label="售后服务分页">
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
export class ServiceWorkordersPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly taskCreating = signal(false);
  protected readonly reporting = signal(false);
  protected readonly orders = signal<DataRecord[]>([]);
  protected readonly products = signal<DataRecord[]>([]);
  protected readonly files = signal<DataRecord[]>([]);
  protected readonly notifications = signal<DataRecord[]>([]);
  protected readonly chartMode = signal<'orders' | 'parts' | 'files'>('orders');
  protected readonly page = signal(1);
  protected readonly pageSize = signal(8);
  protected query = '';
  protected pageInput = '1';

  protected readonly serviceOrders = computed(() => this.orders().filter(row => ['paid', 'shipped', 'done'].includes(String(row['status'] ?? ''))));
  protected readonly lowParts = computed(() => this.products().filter(row => numberOf(row, 'total_stock') <= numberOf(row, 'min_stock')));
  protected readonly customerCount = computed(() => new Set(this.serviceOrders().map(row => textOf(row, 'customer_name', '')).filter(Boolean)).size);
  protected readonly readiness = computed(() => percentNumber(86 - this.lowParts().length * 3 + Math.min(10, this.files().length)));
  protected readonly filteredOrders = computed(() => {
    const q = this.query.trim().toLowerCase();
    if (!q) {
      return this.serviceOrders();
    }
    return this.serviceOrders().filter(row => [textOf(row, 'order_no'), textOf(row, 'customer_name'), statusLabel(row['status'])].join(' ').toLowerCase().includes(q));
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.filteredOrders().length / this.pageSize())));
  protected readonly pagedOrders = computed(() => {
    const safePage = Math.min(this.page(), this.totalPages());
    const start = (safePage - 1) * this.pageSize();
    return this.filteredOrders().slice(start, start + this.pageSize());
  });
  protected readonly actionQueue = computed(() => [
    { title: '发货后回访', metric: `${this.serviceOrders().filter(row => String(row['status']) === 'shipped').length} 单`, body: '创建客户回访与服务确认', path: '/app/sales/orders', tone: 'warning' },
    { title: '服务备件关注', metric: `${this.lowParts().length} 项`, body: '低水位备件影响响应时效', path: '/app/maintenance', tone: 'warning' },
    { title: '服务资料归档', metric: `${this.files().length} 份`, body: '图纸、SOP、报告进入资料库', path: '/app/files', tone: 'success' }
  ]);
  protected readonly chartTitle = computed(() => this.chartMode() === 'orders' ? '服务订单状态结构' : this.chartMode() === 'parts' ? '备件库存与安全线' : '服务资料类型结构');
  protected readonly activeChart = computed(() => this.chartMode() === 'parts' ? this.partsChart() : this.chartMode() === 'files' ? this.filesChart() : this.ordersChart());

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      orders: this.api.list<DataRecord>('orders', { page: 1, page_size: 160 }).pipe(catchError(() => of(emptyPageResult<DataRecord>()))),
      products: this.api.list<DataRecord>('products', { page: 1, page_size: 140 }).pipe(catchError(() => of(emptyPageResult<DataRecord>()))),
      files: this.api.list<DataRecord>('files', { page: 1, page_size: 100 }).pipe(catchError(() => of(emptyPageResult<DataRecord>()))),
      notifications: this.api.list<DataRecord>('notifications', { page: 1, page_size: 100 }).pipe(catchError(() => of(emptyPageResult<DataRecord>())))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(result => {
      this.orders.set(result.orders.items);
      this.products.set(result.products.items);
      this.files.set(result.files.items);
      this.notifications.set(result.notifications.items.filter(row => textOf(row, 'related_type', '').includes('service')));
      this.setPage(1);
    });
  }

  createServiceTask(): void {
    const row = this.filteredOrders()[0] ?? this.serviceOrders()[0] ?? this.orders()[0];
    this.taskCreating.set(true);
    this.api.post('operations/service-workorder', {
      order_id: row?.id,
      title: `售后服务工单 - ${textOf(row, 'customer_name', recordTitle(row))}`,
      content: `请复核 ${recordTitle(row)} 发货批次、服务资料、备件库存和回访节点。`,
      type: String(row?.['status']) === 'shipped' ? 'warning' : 'info'
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '服务工单未创建', detail: error?.message || '任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.taskCreating.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '服务工单已创建', detail: '任务已进入通知中心。' });
      }
    });
  }

  generateReport(): void {
    this.reporting.set(true);
    this.api.post('reports/generate/service_overview', { params: {} }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '服务报表未生成', detail: error?.message || '报表服务未返回结果。' });
        return of(null);
      }),
      finalize(() => this.reporting.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '服务报表已生成', detail: '已进入报表归档。' });
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

  protected ordersChart() {
    const counts = new Map<string, number>();
    for (const row of this.serviceOrders()) {
      const label = statusLabel(row['status']);
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom'),
      series: [{ type: 'pie', radius: ['45%', '72%'], center: ['50%', '43%'], itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.5)' }, data: [...counts.entries()].map(([name, value]) => ({ name, value })) }]
    };
  }

  protected partsChart() {
    const rows = this.products().slice(0, 10);
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top'),
      dataZoom: [{ type: 'inside' }],
      grid: { left: 22, right: 18, top: 42, bottom: 32, containLabel: true },
      xAxis: { type: 'category', data: rows.map(row => textOf(row, 'name')), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { interval: 0, rotate: 16, width: 92, overflow: 'truncate' } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [
        { name: '当前库存', type: 'bar', data: rows.map(row => numberOf(row, 'total_stock')), barWidth: 16, itemStyle: { color: '#8fd3ff', borderRadius: [8, 8, 2, 2] } },
        { name: '安全线', type: 'line', smooth: true, data: rows.map(row => numberOf(row, 'min_stock')), lineStyle: { color: '#ff8fa3', width: 3 }, symbolSize: 5 }
      ]
    };
  }

  protected filesChart() {
    const map = new Map<string, number>();
    for (const row of this.files()) {
      const label = textOf(row, 'mimetype', '未知类型').split('/').at(-1) ?? '文件';
      map.set(label, (map.get(label) ?? 0) + 1);
    }
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      series: [{
        type: 'treemap',
        roam: false,
        breadcrumb: { show: false },
        label: { formatter: '{b}' },
        itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.52)' },
        data: [...map.entries()].map(([name, value]) => ({ name, value }))
      }]
    };
  }

  protected text(row: DataRecord, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  protected compactMoney(value: unknown): string {
    return compactMoneyText(value);
  }

  protected compactNumber(value: unknown): string {
    return compactNumberText(value);
  }

  protected status(value: unknown): string {
    return statusLabel(value);
  }

  protected severity(value: unknown): 'success' | 'secondary' | 'info' | 'warn' | 'danger' | 'contrast' {
    return statusSeverity(value);
  }

  protected serviceLevel(row: DataRecord): string {
    const amount = numberOf(row, 'total_amount');
    if (amount > 250000) {
      return 'S1';
    }
    if (amount > 120000) {
      return 'S2';
    }
    return 'S3';
  }
}
