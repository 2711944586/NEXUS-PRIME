import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
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
import { catchError, finalize, of, switchMap } from 'rxjs';

import { ApiService } from '../core/api.service';
import { ProcurementService } from '../core/procurement.service';
import { DataRecord, ProcurementControlPayload, ProcurementControlQueueItem } from '../core/models';
import { replenishmentJobStatus, ReplenishmentJobService } from '../core/replenishment-job.service';
import { WorkflowStepperComponent, WorkflowStepperStep } from '../motion';
import { chartLegend, compactMoneyText, dateText, moneyText, numberOf, percentNumber, recordTitle, statusLabel, statusSeverity, textOf } from './page-utils';

const EMPTY_PROCUREMENT_CONTROL: ProcurementControlPayload = {
  generated_at: '',
  source: 'procurement_control_contract',
  summary: {
    control_score: 0,
    pending_approvals: 0,
    receiving_due: 0,
    supplier_risk: 0,
    quality_hold: 0,
    budget_exposure: 0,
    replenishment_pending: 0,
    open_tasks: 0,
    queue_count: 0,
    p0: 0,
    p1: 0,
    primary_owner: '采购负责人',
    next_action: '等待采购协同控制台数据。',
    next_path: '/app/procurement/orders'
  },
  procurement_lanes: [],
  approval_queue: [],
  receiving_windows: [],
  supplier_risk_cards: [],
  supplier_risk_queue: [],
  replenishment_candidates: [],
  control_queue: [],
  purchase_flow: [],
  service_boundaries: [],
  deployment_checks: [],
  runbook: []
};

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule, TooltipModule, WorkflowStepperComponent],
  template: `
    <section class="ops-atlas-page procurement-atlas">
      <header class="atlas-split-hero procurement-atlas-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">采购协同控制台</span>
          <h1>采购与供应商协同控制台</h1>
          <p>把补货需求、审批承诺、供应商确认、收货质检和预算暴露压到同一条可执行链路里。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="approveNext()" aria-label="审批下一张采购单">
              <i class="pi pi-check-circle"></i>
              审批下一张
            </button>
            <button pButton type="button" severity="info" (click)="receiveNext()" aria-label="推进收货">
              <i class="pi pi-inbox"></i>
              推进收货
            </button>
            <button pButton type="button" severity="secondary" (click)="acceptSuggestion()" [loading]="replenishmentConverting()" [disabled]="replenishmentConverting()" aria-label="补货转采购">
              <i class="pi pi-bolt"></i>
              补货转采购
            </button>
            <button pButton type="button" severity="contrast" (click)="createProcurementTask(primaryControlTask())" [disabled]="!primaryControlTask()" aria-label="创建采购协同任务">
              <i class="pi pi-flag"></i>
              创建协同任务
            </button>
          </div>
        </div>

        <div class="procurement-lane-map" aria-label="采购审批管线">
          @for (lane of controlLanes(); track lane.id) {
            <a [routerLink]="lane.path" [class.active]="lane.status !== 'ready'">
              <span>{{ lane.label }}</span>
              <strong>{{ lane.active_count }}</strong>
              <em>{{ lane.owner }} · {{ lane.sla }}</em>
              <p-progressbar [value]="lane.score" [showValue]="false" />
            </a>
          }
          @if (!controlLanes().length) {
            @for (lane of lanes(); track lane.status) {
              <button type="button" [class.active]="statusFilter() === lane.status" (click)="statusFilter.set(lane.status)">
                <span>{{ lane.label }}</span>
                <strong>{{ lane.count }}</strong>
                <p-progressbar [value]="lane.percent" [showValue]="false" />
              </button>
            }
          }
        </div>

        <aside class="purchase-score-tower">
          <div><span>控制分</span><strong>{{ controlSummary().control_score }}%</strong></div>
          <div><span>待审批</span><strong>{{ controlSummary().pending_approvals }}</strong></div>
          <div><span>到货窗口</span><strong>{{ controlSummary().receiving_due }}</strong></div>
          <div><span>预算暴露</span><strong>{{ compactMoney(controlSummary().budget_exposure) }}</strong></div>
          <div><span>P0 / P1</span><strong>{{ controlSummary().p0 }} / {{ controlSummary().p1 }}</strong></div>
          <div><span>负责人</span><strong>{{ controlSummary().primary_owner }}</strong></div>
        </aside>
      </header>

      <section class="procurement-control-command" aria-label="采购协同控制队列">
        <article class="atlas-panel procurement-control-queue">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">控制队列</span>
              <h2>采购协同任务</h2>
            </div>
            <p-tag [severity]="prioritySeverity(controlSummary().p0 ? 'P0' : controlSummary().p1 ? 'P1' : 'P2')" [value]="controlSummary().queue_count + ' 项'" />
          </div>
          <p class="procurement-next-action">{{ controlSummary().next_action }}</p>
          <div class="procurement-task-stack">
            @for (item of controlQueue().slice(0, 8); track item.id) {
              <article class="procurement-task-card" [class.blocked]="item.priority === 'P0'">
                <div>
                  <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
                  <span>{{ item.kind }} · {{ item.owner }} · {{ item.sla }}</span>
                </div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.evidence }}</p>
                <footer>
                  <a [routerLink]="item.path">{{ item.metric }}</a>
                  <button type="button" (click)="createProcurementTask(item)" [disabled]="creatingTaskId() === item.id">
                    <i class="pi" [class.pi-spin]="creatingTaskId() === item.id" [class.pi-spinner]="creatingTaskId() === item.id" [class.pi-flag]="creatingTaskId() !== item.id"></i>
                    任务
                  </button>
                </footer>
              </article>
            }
          </div>
        </article>

        <aside class="atlas-panel procurement-flow-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">端到端流程</span>
              <h2>从补货到绩效回写</h2>
            </div>
          </div>
          <nexus-workflow-stepper
            [steps]="purchaseWorkflowSteps()"
            [activeIndex]="activePurchaseWorkflowIndex()"
            ariaLabel="采购补货审批流程"
          ></nexus-workflow-stepper>
        </aside>
      </section>

      <section class="procurement-collaboration-grid" aria-label="供应商、收货、部署协同">
        <article class="atlas-panel procurement-dock-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">收货与质检交接</span>
              <h2>到货窗口</h2>
            </div>
          </div>
          <div class="procurement-window-list">
            @for (window of receivingWindows(); track window.id) {
              <a [routerLink]="window.path">
                <div>
                  <p-tag [severity]="prioritySeverity(window.priority)" [value]="window.priority" />
                  <strong>{{ window.po_no }}</strong>
                  <span>{{ window.supplier }} / {{ window.warehouse }}</span>
                </div>
                <p-progressbar [value]="window.progress" [showValue]="false" />
                <em>{{ window.progress }}% · {{ window.days_to_due }}d</em>
              </a>
            }
            @if (!receivingWindows().length) {
              <div class="dock-empty-state">
                <i class="pi pi-inbox"></i>
                <strong>暂无临近到货窗口</strong>
                <span>审批通过的采购单会进入月台与质检交接。</span>
              </div>
            }
          </div>
        </article>

        <article class="atlas-panel procurement-supplier-risk">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">供应商协同</span>
              <h2>风险与备选信号</h2>
            </div>
          </div>
          <div class="supplier-risk-grid">
            @for (supplier of supplierRiskCards(); track supplier.id) {
              <a [routerLink]="supplier.path" [class.blocked]="supplier.priority === 'P0'">
                <span>{{ supplier.name }}</span>
                <strong>{{ supplier.score }}分</strong>
                <em>准点 {{ supplier.on_time_rate }}% · 质量 {{ supplier.quality_rate }}%</em>
                <p>{{ supplier.evidence }}</p>
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel procurement-contract-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">微服务边界</span>
              <h2>合同与上线检查</h2>
            </div>
          </div>
          <div class="procurement-boundary-list">
            @for (boundary of serviceBoundaries(); track boundary.service) {
              <article>
                <p-tag [severity]="prioritySeverity(boundary.readiness)" [value]="boundary.readiness" />
                <strong>{{ boundary.service }}</strong>
                <span>{{ boundary.deploy_unit }} / {{ boundary.owner }}</span>
                <p>{{ boundary.contract }}</p>
              </article>
            }
          </div>
          <div class="procurement-deploy-checks">
            @for (check of deploymentChecks(); track check.key) {
              <div>
                <i class="pi" [class.pi-check-circle]="check.status === 'ready'" [class.pi-exclamation-triangle]="check.status !== 'ready'"></i>
                <strong>{{ check.label }}</strong>
                <span>{{ check.owner }} · {{ check.evidence }}</span>
              </div>
            }
          </div>
        </article>
      </section>

      <section class="procurement-atlas-board">
        <article class="atlas-panel approval-column">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">审批队列</span>
              <h2>审批队列</h2>
            </div>
            <button pButton type="button" [text]="true" (click)="load()" aria-label="刷新采购数据" pTooltip="刷新采购数据">
              <i class="pi pi-refresh"></i>
            </button>
          </div>
          @if (loading()) {
            <p-skeleton height="78px" />
            <p-skeleton height="78px" />
            <p-skeleton height="78px" />
          } @else {
            @for (order of pendingOrders().slice(0, 6); track order.id) {
              <a class="approval-workcard" [routerLink]="['/app/procurement/orders', order.id]">
                <p-tag [severity]="severity(order['status'])" [value]="status(order['status'])" />
                <strong>{{ text(order, 'po_no') }}</strong>
                <span>{{ text(order, 'supplier_name') }} / {{ text(order, 'warehouse_name') }}</span>
                <b>{{ money(order['total_amount']) }}</b>
              </a>
            }
            @if (!pendingOrders().length) {
              <div class="approval-workcard calm">
                <p-tag severity="success" value="队列清空" />
                <strong>当前没有待审批采购单</strong>
                <span>继续关注补货建议或收货进度。</span>
              </div>
            }
          }
        </article>

        <article class="atlas-panel receiving-column">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">收货月台</span>
              <h2>收货月台</h2>
            </div>
          </div>
          <div class="dock-progress-list">
            @for (order of receivingOrders().slice(0, 7); track order.id) {
              <a [routerLink]="['/app/procurement/orders', order.id]">
                <span>{{ text(order, 'po_no') }}</span>
                <strong>{{ text(order, 'supplier_name') }}</strong>
                <p-progressbar [value]="percent(order['receive_progress'])" [showValue]="false" />
                <em>{{ percent(order['receive_progress']) }}%</em>
              </a>
            }
            @if (!receivingOrders().length) {
              <div class="dock-empty-state">
                <i class="pi pi-inbox"></i>
                <strong>当前没有待收货采购单</strong>
                <span>审批通过后会自动进入收货月台。</span>
              </div>
            }
          </div>
          <div class="receiving-summary-grid" aria-label="收货阶段摘要">
            @for (lane of lanes().slice(2); track lane.status) {
              <button type="button" [class.active]="statusFilter() === lane.status" (click)="statusFilter.set(lane.status)">
                <span>{{ lane.label }}</span>
                <strong>{{ lane.count }}</strong>
                <em>{{ lane.percent }}%</em>
              </button>
            }
          </div>
        </article>

        <aside class="atlas-panel supplier-tower">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">供应商信号</span>
              <h2>供应商画像</h2>
            </div>
          </div>
          <div class="supplier-metrics">
            <div><strong>91%</strong><span>准点率</span></div>
            <div><strong>96%</strong><span>质检通过</span></div>
            <div><strong>4.8d</strong><span>平均交期</span></div>
            <div><strong>{{ supplierCount() }}</strong><span>供应商</span></div>
          </div>
          <p>收货结果会反哺供应商评分，补货转采购会优先选择更稳定的供应商。</p>
        </aside>
      </section>

      <section class="atlas-panel procurement-intelligence-panel">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">采购图表</span>
            <h2>{{ procurementChartTitle() }}</h2>
          </div>
          <div class="metric-mode-switch" aria-label="采购图表模式">
            @for (mode of procurementChartModes; track mode.key) {
              <button type="button" [class.active]="chartMode() === mode.key" (click)="chartMode.set(mode.key)">
                <i class="pi" [class]="mode.icon"></i>
                {{ mode.label }}
              </button>
            }
          </div>
        </div>
        <div class="ops-chart-split">
          <div class="ops-chart-large" echarts [options]="activeProcurementChart()"></div>
          <aside class="ops-chart-insights">
            @for (item of procurementInsights(); track item.kicker) {
              <button type="button" (click)="statusFilter.set(item.filter)">
                <span>{{ item.kicker }}</span>
                <strong>{{ item.title }}</strong>
                <em>{{ item.value }}</em>
              </button>
            }
          </aside>
        </div>
      </section>

      <section class="atlas-panel purchase-ledger-panel">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">采购账本</span>
            <h2>采购单账本</h2>
          </div>
          <div class="atlas-filter">
            <i class="pi pi-search"></i>
            <input pInputText [ngModel]="query()" (ngModelChange)="onQueryChange($event)" placeholder="搜索采购单、供应商、收货仓" />
          </div>
          <button type="button" [class.active]="statusFilter() === ''" (click)="statusFilter.set('')">全部状态</button>
        </div>

        @if (error()) {
          <div class="empty-state">
            <i class="pi pi-cloud"></i>
            <strong>采购数据通道未连接</strong>
            <p>{{ error() }}</p>
            <button pButton type="button" (click)="load()">重试</button>
          </div>
        } @else {
          <div class="atlas-record-ledger">
            @for (order of pagedOrders(); track order.id) {
              <a class="atlas-record-row" [routerLink]="['/app/procurement/orders', order.id]">
                <span class="record-code">{{ text(order, 'po_no') }}</span>
                <strong>{{ text(order, 'supplier_name') }}</strong>
                <em>{{ text(order, 'warehouse_name') }} / {{ date(order['expected_date'] ?? order['created_at']) }}</em>
                <b>{{ money(order['total_amount']) }}</b>
                <p-tag [severity]="severity(order['status'])" [value]="status(order['status'])" />
              </a>
            }
          </div>
          @if (visibleOrders().length > pageSize()) {
            <div class="atlas-pagination" aria-label="采购账本分页">
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
export class ProcurementPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly procurement = inject(ProcurementService);
  private readonly replenishmentJobs = inject(ReplenishmentJobService);
  private readonly messages = inject(MessageService);
  private readonly confirm = inject(ConfirmationService);

  protected readonly control = signal<ProcurementControlPayload>(EMPTY_PROCUREMENT_CONTROL);
  protected readonly controlLoading = signal(false);
  protected readonly replenishmentConverting = signal(false);
  protected readonly statusFilter = signal('');
  protected readonly chartMode = signal<'stage' | 'amount' | 'supplier'>('stage');
  protected readonly creatingTaskId = signal<string | null>(null);
  protected readonly pageSize = signal(12);
  protected readonly page = signal(1);
  protected readonly query = signal('');
  protected pageInput = '1';
  protected readonly procurementChartModes = [
    { key: 'stage' as const, label: '阶段', icon: 'pi-chart-bar' },
    { key: 'amount' as const, label: '金额', icon: 'pi-wallet' },
    { key: 'supplier' as const, label: '供应商', icon: 'pi-sitemap' }
  ];
  protected readonly ordersQuery = injectQuery(() => this.procurement.ordersQuery({
    page: 1,
    page_size: 100,
    q: this.query().trim()
  }));
  protected readonly rows = computed(() => this.ordersQuery.data()?.items ?? []);
  protected readonly loading = computed(() => this.ordersQuery.isPending() || this.ordersQuery.isFetching() || this.controlLoading());
  protected readonly error = computed(() => {
    const error = this.ordersQuery.error();
    return error ? error.message || '无法读取采购数据。' : '';
  });

  protected readonly visibleOrders = computed(() => {
    const q = this.query().trim().toLowerCase();
    const status = this.statusFilter();
    return this.rows().filter(row => {
      const rowStatus = String(row['status'] ?? '');
      const haystack = [textOf(row, 'po_no'), textOf(row, 'supplier_name'), textOf(row, 'warehouse_name'), rowStatus].join(' ').toLowerCase();
      return (!status || rowStatus === status) && (!q || haystack.includes(q));
    });
  });
  protected readonly pendingOrders = computed(() => this.rows().filter(row => ['draft', 'pending'].includes(String(row['status'] ?? ''))));
  protected readonly receivingOrders = computed(() => this.rows().filter(row => ['approved', 'partial'].includes(String(row['status'] ?? ''))));
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.visibleOrders().length / this.pageSize())));
  protected readonly currentPage = computed(() => Math.min(this.page(), this.totalPages()));
  protected readonly pagedOrders = computed(() => {
    const start = (this.currentPage() - 1) * this.pageSize();
    return this.visibleOrders().slice(start, start + this.pageSize());
  });
  protected readonly totalAmount = computed(() => this.rows().reduce((sum, row) => sum + numberOf(row, 'total_amount'), 0));
  protected readonly averageProgress = computed(() => {
    const rows = this.rows();
    if (!rows.length) {
      return 0;
    }
    return Math.round(rows.reduce((sum, row) => sum + numberOf(row, 'receive_progress'), 0) / rows.length);
  });
  protected readonly supplierCount = computed(() => new Set(this.rows().map(row => textOf(row, 'supplier_name', '')).filter(Boolean)).size);
  protected readonly controlSummary = computed(() => this.control().summary);
  protected readonly controlLanes = computed(() => this.control().procurement_lanes);
  protected readonly controlQueue = computed(() => this.control().control_queue);
  protected readonly primaryControlTask = computed(() => this.controlQueue()[0]);
  protected readonly supplierRiskCards = computed(() => this.control().supplier_risk_cards.slice(0, 6));
  protected readonly receivingWindows = computed(() => this.control().receiving_windows.slice(0, 6));
  protected readonly serviceBoundaries = computed(() => this.control().service_boundaries);
  protected readonly deploymentChecks = computed(() => this.control().deployment_checks);
  protected readonly replenishmentCandidates = computed(() => this.control().replenishment_candidates.slice(0, 6));
  protected readonly purchaseWorkflowSteps = computed<WorkflowStepperStep[]>(() => {
    const source = this.control().purchase_flow.length
      ? this.control().purchase_flow
      : [
        { step: '需求来源', detail: '低库存、补货建议和销售履约压力进入采购需求池。' },
        { step: '审批承诺', detail: '采购负责人按金额、供应商风险、预算暴露和到货窗口推进审批。' },
        { step: '到货与质检', detail: '收货入库前核对采购明细、来料检验、库位和批次证据。' },
        { step: '预算与绩效回写', detail: '采购承诺、收货结果和供应商表现回写成本、质量和报表。' }
      ];
    const active = this.activePurchaseWorkflowIndex();

    return source.map((step, index) => ({
      label: step.step,
      detail: step.detail,
      meta: this.purchaseWorkflowMeta(index),
      tone: this.purchaseWorkflowTone(index),
      state: index < active ? 'complete' : index === active ? 'active' : 'pending',
      path: this.purchaseWorkflowPath(index, step.step)
    }));
  });
  protected readonly activePurchaseWorkflowIndex = computed(() => {
    const summary = this.controlSummary();
    if (summary.replenishment_pending > 0 && summary.pending_approvals === 0) {
      return 0;
    }
    if (summary.pending_approvals > 0) {
      return 1;
    }
    if (summary.receiving_due > 0 || this.receivingOrders().length > 0) {
      return 2;
    }
    if (summary.supplier_risk > 0 || this.supplierRiskCards().length > 0) {
      return 3;
    }
    return Math.min(4, Math.max(0, this.control().purchase_flow.length - 1));
  });
  protected readonly procurementChartTitle = computed(() => {
    if (this.chartMode() === 'amount') {
      return '采购金额与收货进度';
    }
    if (this.chartMode() === 'supplier') {
      return '供应商采购占比';
    }
    return '采购阶段漏斗';
  });
  protected readonly procurementInsights = computed(() => [
    { kicker: '待审批', title: `${this.pendingOrders().length} 单`, value: '待处理队列', filter: 'pending' },
    { kicker: '收货中', title: `${this.receivingOrders().length} 单`, value: `${this.averageProgress()}% 平均进度`, filter: 'approved' },
    { kicker: '供应商', title: `${this.supplierCount()} 家`, value: '按采购金额集中度复核', filter: '' },
    { kicker: '金额', title: this.compactMoney(this.totalAmount()), value: '当前加载批次合计', filter: '' }
  ]);
  protected readonly lanes = computed(() => {
    const rows = this.rows();
    const total = Math.max(rows.length, 1);
    return [
      { status: 'draft', label: '草稿', count: rows.filter(row => row['status'] === 'draft').length },
      { status: 'pending', label: '待审批', count: rows.filter(row => row['status'] === 'pending').length },
      { status: 'approved', label: '已批准', count: rows.filter(row => row['status'] === 'approved').length },
      { status: 'partial', label: '部分收货', count: rows.filter(row => row['status'] === 'partial').length },
      { status: 'received', label: '已收货', count: rows.filter(row => row['status'] === 'received').length }
    ].map(lane => ({ ...lane, percent: Math.round((lane.count / total) * 100) }));
  });
  protected readonly activeProcurementChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'amount') {
      return this.amountChart();
    }
    if (this.chartMode() === 'supplier') {
      return this.supplierChart();
    }
    return this.stageChart();
  });

  ngOnInit(): void {
    this.loadControl();
  }

  load(): void {
    this.ordersQuery.refetch();
    this.loadControl();
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

  private loadControl(): void {
    this.controlLoading.set(true);
    this.api.get<ProcurementControlPayload>('operations/procurement-control').pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '采购控制台未加载', detail: error?.message || '请稍后重试。' });
        return of(EMPTY_PROCUREMENT_CONTROL);
      }),
      finalize(() => this.controlLoading.set(false))
    ).subscribe(control => {
      this.control.set(control);
    });
  }

  approveNext(): void {
    const target = this.pendingOrders()[0];
    if (!target?.id) {
      this.messages.add({ severity: 'info', summary: '审批队列', detail: '当前没有可审批采购单。' });
      return;
    }
    const status = String(target['status'] ?? '');
    const endpoint = status === 'draft' ? `purchase-orders/${target.id}/submit` : `purchase-orders/${target.id}/approve`;
    this.confirm.confirm({
      header: '审批采购单',
      message: `确认推进 ${recordTitle(target)}？`,
      acceptLabel: '确认',
      rejectLabel: '取消',
      accept: () => this.postAction(endpoint, { remark: '采购中心审批推进' }, '采购单已推进')
    });
  }

  receiveNext(): void {
    const target = this.receivingOrders()[0];
    if (!target?.id) {
      this.messages.add({ severity: 'info', summary: '收货队列', detail: '当前没有可收货采购单。' });
      return;
    }
    const items = Array.isArray(target['items']) ? target['items'] as DataRecord[] : [];
    const receivableItems = items
      .filter(item => numberOf(item, 'pending_qty') > 0)
      .map(item => ({ item_id: item.id, receive_qty: Math.max(1, numberOf(item, 'pending_qty')) }));
    this.confirm.confirm({
      header: '推进采购收货',
      message: `确认对 ${recordTitle(target)} 执行收货入库？`,
      acceptLabel: '收货',
      rejectLabel: '取消',
      accept: () => this.postAction(`purchase-orders/${target.id}/receive`, { items: receivableItems }, '收货动作已提交')
    });
  }

  acceptSuggestion(): void {
    this.confirm.confirm({
      header: '补货转采购',
      message: '将刷新补货建议，并接受第一条待处理建议生成采购单。',
      acceptLabel: '执行',
      rejectLabel: '取消',
      accept: () => {
        this.replenishmentConverting.set(true);
        this.replenishmentJobs.runGenerationToFinal().pipe(
          switchMap(event => {
            const status = replenishmentJobStatus(event.result);
            if (event.timedOut) {
              this.messages.add({ severity: 'info', summary: '补货任务仍在运行', detail: '后台仍在生成补货建议，请稍后再转采购。' });
              return of(null);
            }
            if (status !== 'success') {
              this.messages.add({ severity: 'warn', summary: '补货建议未刷新', detail: event.result.job?.error_message || '后台补货任务未完成。' });
              return of(null);
            }
            return this.api.list<DataRecord>('replenishment-suggestions', { page: 1, page_size: 20, status: 'pending' });
          }),
          switchMap(result => {
            if (!result) {
              return of(null);
            }
            const suggestion = result.items[0];
            if (!suggestion?.id) {
              this.messages.add({ severity: 'info', summary: '补货建议', detail: '当前没有待转采购的补货建议。' });
              return of(null);
            }
            return this.api.post(`replenishment-suggestions/${suggestion.id}/accept`, {});
          }),
          catchError(error => {
            this.messages.add({ severity: 'warn', summary: '转采购未完成', detail: error?.message || '补货建议未能转采购。' });
            return of(null);
          }),
          finalize(() => this.replenishmentConverting.set(false))
        ).subscribe(result => {
          if (result) {
            this.messages.add({ severity: 'success', summary: '采购单已创建', detail: '补货建议已写入采购链路。' });
            this.load();
          }
        });
      }
    });
  }

  protected createProcurementTask(item?: ProcurementControlQueueItem): void {
    if (!item) {
      this.messages.add({ severity: 'info', summary: '采购协同', detail: '当前没有可创建的采购协同任务。' });
      return;
    }
    this.creatingTaskId.set(item.id);
    this.api.post('operations/procurement-control/task', {
      queue_item_id: item.id,
      purchase_id: item.purchase_id,
      supplier_id: item.supplier_id,
      title: item.title,
      owner: item.owner,
      priority: item.priority,
      sla: item.sla,
      kind: item.kind,
      evidence: item.evidence,
      action: item.action,
      path: item.path
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '采购协同任务未创建', detail: error?.message || '任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.creatingTaskId.set(null))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '采购协同任务已创建', detail: `${item.title} 已进入任务异常中心。` });
        this.load();
      }
    });
  }

  private postAction(endpoint: string, body: Record<string, unknown>, success: string): void {
    this.api.post(endpoint, body).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '动作未完成', detail: error?.message || '业务状态不满足执行条件。' });
        return of(null);
      })
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: success, detail: '数据库已更新，页面正在刷新。' });
        this.load();
      }
    });
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

  protected prioritySeverity(priority: unknown) {
    const value = String(priority ?? '');
    if (value === 'P0' || value === 'blocked') {
      return 'danger';
    }
    if (value === 'P1' || value === 'attention') {
      return 'warn';
    }
    return 'success';
  }

  protected percent(value: unknown): number {
    return percentNumber(value);
  }

  private purchaseWorkflowMeta(index: number): string {
    const summary = this.controlSummary();
    const values = [
      `${summary.replenishment_pending} 条建议`,
      `${summary.pending_approvals} 单审批`,
      `${summary.receiving_due} 个窗口`,
      `${summary.supplier_risk} 个风险`,
      this.compactMoney(summary.budget_exposure)
    ];
    return values[index] ?? summary.primary_owner;
  }

  private purchaseWorkflowTone(index: number): WorkflowStepperStep['tone'] {
    const summary = this.controlSummary();
    if ((index === 1 && summary.pending_approvals > 0) || (index === 2 && summary.receiving_due > 0)) {
      return summary.p0 > 0 ? 'danger' : 'warning';
    }
    if (index === 3 && summary.supplier_risk > 0) {
      return 'warning';
    }
    return index < this.activePurchaseWorkflowIndex() ? 'success' : index === this.activePurchaseWorkflowIndex() ? 'info' : 'default';
  }

  private purchaseWorkflowPath(index: number, label: string): string {
    const text = label.toLowerCase();
    if (text.includes('需求') || text.includes('建议') || text.includes('replenishment')) {
      return '/app/inventory/replenishment';
    }
    if (text.includes('质检') || text.includes('quality')) {
      return '/app/quality';
    }
    if (text.includes('供应商') || text.includes('绩效') || text.includes('supplier')) {
      return '/app/suppliers/performance';
    }
    const paths = ['/app/inventory/replenishment', '/app/procurement/orders', '/app/quality', '/app/suppliers/performance', '/app/reports'];
    return paths[index] ?? '/app/procurement/orders';
  }

  private stageChart(): EChartsCoreOption {
    const controlLanes = this.controlLanes();
    const lanes = controlLanes.length
      ? controlLanes.map(item => ({ label: item.label, count: item.active_count, score: item.score, status: item.status }))
      : this.lanes().map(item => ({ label: item.label, count: item.count, score: item.percent, status: item.status }));
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 28, right: 18, top: 28, bottom: 30, containLabel: true },
      xAxis: { type: 'category', data: lanes.map(item => item.label), axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [
        {
          name: '待处理',
          type: 'bar',
          data: lanes.map(item => item.count),
          barWidth: 26,
          itemStyle: { color: '#b7791f', borderRadius: [12, 12, 3, 3] }
        },
        {
          name: '就绪度',
          type: 'line',
          smooth: true,
          data: lanes.map(item => item.score),
          lineStyle: { width: 3, color: '#0f766e' },
          symbolSize: 7
        }
      ]
    };
  }

  private amountChart(): EChartsCoreOption {
    const items = this.rows().slice(0, 12).reverse();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      dataZoom: [{ type: 'inside' }],
      grid: { left: 28, right: 18, top: 28, bottom: 34, containLabel: true },
      xAxis: { type: 'category', data: items.map(row => textOf(row, 'po_no').slice(-8)), axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [
        {
          name: '采购金额',
          type: 'line',
          smooth: true,
          data: items.map(row => numberOf(row, 'total_amount')),
          lineStyle: { width: 3, color: '#0f766e' },
          areaStyle: { color: 'rgba(15,118,110,.14)' },
          symbolSize: 7
        },
        {
          name: '收货进度',
          type: 'bar',
          yAxisIndex: 0,
          data: items.map(row => numberOf(row, 'receive_progress') * 1200),
          barWidth: 14,
          itemStyle: { color: 'rgba(183,121,31,.36)', borderRadius: [8, 8, 2, 2] }
        }
      ]
    };
  }

  private supplierChart(): EChartsCoreOption {
    const supplierAmount = new Map<string, number>();
    const cards = this.supplierRiskCards();
    if (cards.length) {
      for (const card of cards) {
        supplierAmount.set(card.name, card.total_amount || card.pending_orders || 1);
      }
    } else {
      for (const row of this.rows()) {
        const supplier = textOf(row, 'supplier_name', '未维护供应商');
        supplierAmount.set(supplier, (supplierAmount.get(supplier) ?? 0) + numberOf(row, 'total_amount'));
      }
    }
    const data = [...supplierAmount.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 9)
      .map(([name, value]) => ({ name, value }));
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom', 'rgba(100,116,139,.95)'),
      series: [{
        type: 'pie',
        radius: ['42%', '72%'],
        center: ['50%', '43%'],
        itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.48)' },
        data: data.length ? data : [{ name: '采购数据', value: 1 }]
      }]
    };
  }
}
