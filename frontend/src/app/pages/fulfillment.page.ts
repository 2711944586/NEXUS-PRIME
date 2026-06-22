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
import { catchError, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { SalesService } from '../core/sales.service';
import { DataRecord } from '../core/models';
import { compactMoneyText, dateText, moneyText, numberOf, percentNumber, recordTitle, statusLabel, statusSeverity, textOf } from './page-utils';

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule, TooltipModule],
  template: `
    <section class="ops-atlas-page fulfillment-atlas">
      <header class="atlas-split-hero fulfillment-atlas-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">销售履约</span>
          <h1>客户窗口与发货调度台</h1>
          <p>订单阶段、库存锁定、发货和应收集中在同一调度台。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="advanceNext()" aria-label="推进下一张订单">
              <i class="pi pi-send"></i>
              推进下一张
            </button>
            <button pButton type="button" severity="secondary" (click)="createFollowOrder()" aria-label="复制客户创建订单">
              <i class="pi pi-plus"></i>
              创建跟进订单
            </button>
            <a pButton severity="info" routerLink="/app/finance/receivables">
              <i class="pi pi-wallet"></i>
              应收联动
            </a>
          </div>
        </div>

        <div class="dispatch-runway" aria-label="订单履约阶段">
          @for (stage of stages(); track stage.status) {
            <button type="button" [class.active]="statusFilter() === stage.status" (click)="statusFilter.set(stage.status)">
              <span>{{ stage.label }}</span>
              <strong>{{ stage.count }}</strong>
              <em>{{ stage.copy }}</em>
            </button>
          }
        </div>

        <aside class="dispatch-score-tower">
          <div><span>订单金额</span><strong>{{ compactMoney(totalAmount()) }}</strong></div>
          <div><span>待推进</span><strong>{{ actionableOrders().length }}</strong></div>
          <div><span>已发货</span><strong>{{ shippedOrders().length }}</strong></div>
          <div><span>完成率</span><strong>{{ completionRate() }}%</strong></div>
        </aside>
      </header>

      <section class="fulfillment-dispatch-grid">
        <article class="atlas-panel dispatch-column">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">调度看板</span>
              <h2>待推进订单</h2>
            </div>
            <button pButton type="button" [text]="true" (click)="load()" aria-label="刷新订单数据" pTooltip="刷新订单数据">
              <i class="pi pi-refresh"></i>
            </button>
          </div>
          @if (loading()) {
            <p-skeleton height="82px" />
            <p-skeleton height="82px" />
            <p-skeleton height="82px" />
          } @else {
            @for (order of actionableOrders().slice(0, 6); track order.id) {
              <a class="dispatch-workcard" [routerLink]="['/app/sales/orders', order.id]">
                <p-tag [severity]="severity(order['status'])" [value]="status(order['status'])" />
                <strong>{{ text(order, 'order_no') }}</strong>
                <span>{{ text(order, 'customer_name') }} / {{ date(order['created_at']) }}</span>
                <b>{{ money(order['total_amount']) }}</b>
              </a>
            }
            @if (!actionableOrders().length) {
              <div class="dispatch-workcard calm">
                <p-tag severity="success" value="队列清空" />
                <strong>当前没有待推进订单</strong>
                <span>继续查看应收和报表归档。</span>
              </div>
            }
          }
        </article>

        <article class="atlas-panel customer-window-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">客户窗口</span>
              <h2>客户交付窗口</h2>
            </div>
          </div>
          <div class="customer-window-rail">
            @for (order of rows().slice(0, 7); track order.id) {
              <a [routerLink]="['/app/sales/orders', order.id]" [class.hot]="isHot(order)">
                <span>{{ status(order['status']) }}</span>
                <strong>{{ text(order, 'customer_name') }}</strong>
                <em>{{ text(order, 'order_no') }}</em>
              </a>
            }
          </div>
        </article>

        <aside class="atlas-panel fulfillment-link-tower">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">联动控制</span>
              <h2>库存与财务联动</h2>
            </div>
          </div>
          <a routerLink="/app/inventory/stock"><i class="pi pi-box"></i><span>库存锁定与出库流水</span></a>
          <a routerLink="/app/finance/receivables"><i class="pi pi-wallet"></i><span>发货后进入应收风控</span></a>
          <a routerLink="/app/reports"><i class="pi pi-chart-line"></i><span>履约结果进入经营日报</span></a>
          <p-progressbar [value]="completionRate()" />
        </aside>
      </section>

      <section class="atlas-panel fulfillment-intelligence-panel">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">履约图表</span>
            <h2>{{ fulfillmentChartTitle() }}</h2>
          </div>
          <div class="metric-mode-switch" aria-label="履约图表模式">
            @for (mode of fulfillmentChartModes; track mode.key) {
              <button type="button" [class.active]="chartMode() === mode.key" (click)="chartMode.set(mode.key)">
                <i class="pi" [class]="mode.icon"></i>
                {{ mode.label }}
              </button>
            }
          </div>
        </div>
        <div class="ops-chart-split">
          <div class="ops-chart-large" echarts [options]="activeFulfillmentChart()"></div>
          <aside class="ops-chart-insights">
            @for (item of fulfillmentInsights(); track item.kicker) {
              <button type="button" (click)="statusFilter.set(item.filter)">
                <span>{{ item.kicker }}</span>
                <strong>{{ item.title }}</strong>
                <em>{{ item.value }}</em>
              </button>
            }
          </aside>
        </div>
      </section>

      <section class="atlas-panel fulfillment-ledger-panel">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">订单账本</span>
            <h2>订单履约账本</h2>
          </div>
          <div class="atlas-filter">
            <i class="pi pi-search"></i>
            <input pInputText [ngModel]="query()" (ngModelChange)="onQueryChange($event)" placeholder="搜索订单、客户、阶段" />
          </div>
          <button type="button" [class.active]="statusFilter() === ''" (click)="statusFilter.set('')">全部阶段</button>
        </div>

        @if (error()) {
          <div class="empty-state">
            <i class="pi pi-cloud"></i>
            <strong>销售数据通道未连接</strong>
            <p>{{ error() }}</p>
            <button pButton type="button" (click)="load()">重试</button>
          </div>
        } @else {
          <div class="atlas-record-ledger">
            @for (order of pagedOrders(); track order.id) {
              <a class="atlas-record-row" [routerLink]="['/app/sales/orders', order.id]">
                <span class="record-code">{{ text(order, 'order_no') }}</span>
                <strong>{{ text(order, 'customer_name') }}</strong>
                <em>{{ date(order['created_at']) }} / {{ itemsCount(order) }} 项明细</em>
                <b>{{ money(order['total_amount']) }}</b>
                <p-tag [severity]="severity(order['status'])" [value]="status(order['status'])" />
              </a>
            }
          </div>
          @if (visibleOrders().length > pageSize()) {
            <div class="atlas-pagination" aria-label="订单履约分页">
              <button type="button" (click)="setPage(currentPage() - 1)" [disabled]="currentPage() <= 1">
                <i class="pi pi-angle-left"></i>
                上一页
              </button>
              <span>第 <strong>{{ currentPage() }}</strong> / {{ totalPages() }} 页 · {{ visibleOrders().length }} 单</span>
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
export class FulfillmentPage {
  private readonly api = inject(ApiService);
  private readonly sales = inject(SalesService);
  private readonly messages = inject(MessageService);
  private readonly confirm = inject(ConfirmationService);

  protected readonly statusFilter = signal('');
  protected readonly chartMode = signal<'stage' | 'amount' | 'customer'>('stage');
  protected readonly pageSize = signal(12);
  protected readonly page = signal(1);
  protected readonly query = signal('');
  protected pageInput = '1';
  protected readonly fulfillmentChartModes = [
    { key: 'stage' as const, label: '阶段', icon: 'pi-chart-bar' },
    { key: 'amount' as const, label: '金额', icon: 'pi-chart-line' },
    { key: 'customer' as const, label: '客户', icon: 'pi-users' }
  ];
  protected readonly salesOrdersQuery = injectQuery(() => this.sales.ordersQuery({
    page: 1,
    page_size: 100,
    q: this.query().trim()
  }));
  protected readonly rows = computed(() => this.salesOrdersQuery.data()?.items ?? []);
  protected readonly loading = computed(() => this.salesOrdersQuery.isPending() || this.salesOrdersQuery.isFetching());
  protected readonly error = computed(() => {
    const error = this.salesOrdersQuery.error();
    return error ? error.message || '无法读取销售订单。' : '';
  });

  protected readonly visibleOrders = computed(() => {
    const q = this.query().trim().toLowerCase();
    const status = this.statusFilter();
    return this.rows().filter(row => {
      const rowStatus = String(row['status'] ?? '');
      const haystack = [textOf(row, 'order_no'), textOf(row, 'customer_name'), rowStatus].join(' ').toLowerCase();
      return (!status || rowStatus === status) && (!q || haystack.includes(q));
    });
  });
  protected readonly actionableOrders = computed(() => this.rows().filter(row => ['pending', 'paid', 'shipped'].includes(String(row['status'] ?? ''))));
  protected readonly shippedOrders = computed(() => this.rows().filter(row => ['shipped', 'done'].includes(String(row['status'] ?? ''))));
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.visibleOrders().length / this.pageSize())));
  protected readonly currentPage = computed(() => Math.min(this.page(), this.totalPages()));
  protected readonly pagedOrders = computed(() => {
    const start = (this.currentPage() - 1) * this.pageSize();
    return this.visibleOrders().slice(start, start + this.pageSize());
  });
  protected readonly totalAmount = computed(() => this.rows().reduce((sum, row) => sum + numberOf(row, 'total_amount'), 0));
  protected readonly completionRate = computed(() => {
    const rows = this.rows();
    if (!rows.length) {
      return 0;
    }
    return percentNumber((rows.filter(row => row['status'] === 'done').length / rows.length) * 100);
  });
  protected readonly fulfillmentChartTitle = computed(() => {
    if (this.chartMode() === 'amount') {
      return '订单金额走势';
    }
    if (this.chartMode() === 'customer') {
      return '客户履约贡献';
    }
    return '订单阶段分布';
  });
  protected readonly fulfillmentInsights = computed(() => [
    { kicker: '待发货', title: `${this.rows().filter(row => row['status'] === 'paid').length} 单`, value: '需要库存锁定', filter: 'paid' },
    { kicker: '已发货', title: `${this.shippedOrders().length} 单`, value: '跟进签收与应收', filter: 'shipped' },
    { kicker: '完成率', title: `${this.completionRate()}%`, value: '完成订单进入报表', filter: 'done' },
    { kicker: '金额', title: this.compactMoney(this.totalAmount()), value: '当前加载批次合计', filter: '' }
  ]);
  protected readonly stages = computed(() => {
    const rows = this.rows();
    return [
      { status: 'pending', label: '待付款', copy: '信用/收款前置' },
      { status: 'paid', label: '待发货', copy: '库存锁定' },
      { status: 'shipped', label: '已发货', copy: '客户签收' },
      { status: 'done', label: '已完成', copy: '归档报表' }
    ].map(stage => ({ ...stage, count: rows.filter(row => row['status'] === stage.status).length }));
  });
  protected readonly activeFulfillmentChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'amount') {
      return this.amountChart();
    }
    if (this.chartMode() === 'customer') {
      return this.customerChart();
    }
    return this.stageChart();
  });

  load(): void {
    this.salesOrdersQuery.refetch();
    this.setPage(1);
  }

  onQueryChange(value: string): void {
    this.query.set(value);
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

  advanceNext(): void {
    const target = this.actionableOrders()[0];
    if (!target?.id) {
      this.messages.add({ severity: 'info', summary: '履约队列', detail: '当前没有可推进订单。' });
      return;
    }
    const status = String(target['status'] ?? '');
    const next = status === 'pending' ? 'paid' : status === 'shipped' ? 'done' : 'shipped';
    this.confirm.confirm({
      header: '推进销售履约',
      message: `确认将 ${recordTitle(target)} 推进到「${statusLabel(next)}」？`,
      acceptLabel: '推进',
      rejectLabel: '取消',
      accept: () => this.api.post(`sales/orders/${target.id}/transition`, { status: next, remark: '销售履约中心推进' }).pipe(
        catchError(error => {
          this.messages.add({ severity: 'warn', summary: '履约未完成', detail: error?.message || '订单状态不允许流转。' });
          return of(null);
        })
      ).subscribe(result => {
        if (result) {
          this.messages.add({ severity: 'success', summary: '订单已推进', detail: '订单状态、库存或应收链路已刷新。' });
          this.load();
        }
      })
    });
  }

  createFollowOrder(): void {
    const source = this.rows()[0];
    const customerId = Number(source?.['customer_id'] ?? 0);
    const items = Array.isArray(source?.['items']) ? source?.['items'] as DataRecord[] : [];
    const firstItem = items.find(item => item['product_id']);
    if (!customerId || !firstItem?.['product_id']) {
      this.messages.add({ severity: 'warn', summary: '创建订单', detail: '当前订单缺少客户或产品关联，无法复制创建。' });
      return;
    }
    this.confirm.confirm({
      header: '创建跟进订单',
      message: `确认基于 ${textOf(source, 'customer_name')} 创建一张跟进订单？`,
      acceptLabel: '创建',
      rejectLabel: '取消',
      accept: () => this.api.post<DataRecord>('sales/orders', {
        customer_id: customerId,
        items: [{ product_id: firstItem['product_id'], quantity: Math.max(1, numberOf(firstItem, 'quantity')) }],
        status: 'pending'
      }).pipe(
        catchError(error => {
          this.messages.add({ severity: 'warn', summary: '创建未完成', detail: error?.message || '订单未写入数据库。' });
          return of(null);
        })
      ).subscribe(result => {
        if (result) {
          this.messages.add({ severity: 'success', summary: '订单已创建', detail: recordTitle(result) });
          this.load();
        }
      })
    });
  }

  protected itemsCount(order: DataRecord): number {
    return Array.isArray(order['items']) ? order['items'].length : 0;
  }

  protected isHot(order: DataRecord): boolean {
    return ['pending', 'paid', 'shipped'].includes(String(order['status'] ?? ''));
  }

  protected text(row: DataRecord, key: string, emptyText = '-'): string {
    return textOf(row, key, emptyText);
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

  private stageChart(): EChartsCoreOption {
    const stages = this.stages();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 28, right: 18, top: 28, bottom: 30, containLabel: true },
      xAxis: { type: 'category', data: stages.map(item => item.label), axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [{
        name: '订单数',
        type: 'bar',
        data: stages.map(item => item.count),
        barWidth: 26,
        itemStyle: { color: '#2563eb', borderRadius: [12, 12, 3, 3] }
      }]
    };
  }

  private amountChart(): EChartsCoreOption {
    const items = this.rows().slice(0, 14).reverse();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      dataZoom: [{ type: 'inside' }],
      grid: { left: 30, right: 18, top: 28, bottom: 34, containLabel: true },
      xAxis: { type: 'category', data: items.map(row => textOf(row, 'order_no').slice(-8)), axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [{
        name: '订单金额',
        type: 'line',
        smooth: true,
        data: items.map(row => numberOf(row, 'total_amount')),
        symbolSize: 8,
        lineStyle: { width: 3, color: '#2563eb' },
        areaStyle: { color: 'rgba(37,99,235,.14)' }
      }]
    };
  }

  private customerChart(): EChartsCoreOption {
    const customerAmount = new Map<string, number>();
    for (const row of this.rows()) {
      const customer = textOf(row, 'customer_name', '未维护客户');
      customerAmount.set(customer, (customerAmount.get(customer) ?? 0) + numberOf(row, 'total_amount'));
    }
    const data = [...customerAmount.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([name, value]) => ({ name, value }));
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      series: [{
        type: 'treemap',
        roam: false,
        breadcrumb: { show: false },
        label: { show: true, formatter: '{b}', color: '#0f172a', fontWeight: 700 },
        upperLabel: { show: false },
        itemStyle: { borderRadius: 10, borderColor: 'rgba(255,255,255,.58)', borderWidth: 2 },
        data: data.length ? data : [{ name: '客户订单', value: 1 }]
      }]
    };
  }
}
