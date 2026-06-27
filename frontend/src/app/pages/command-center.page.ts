import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { ButtonModule } from 'primeng/button';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { ErpControlTower, ManufacturingCommandCenter, OperationsWorkflowBoard } from '../core/models';
import { COMMAND_CENTER_PHOTOS, VisualAsset } from '../core/visual-assets';
import { NexusRevealDirective, NexusSpotlightDirective, SceneBackgroundComponent } from '../motion';
import { chartLegend } from './page-utils';

const EMPTY_COMMAND_CENTER: ManufacturingCommandCenter = {
  kpis: {
    order_amount: 0,
    stock_quantity: 0,
    low_stock_products: 0,
    pending_purchase: 0,
    overdue_amount: 0
  },
  warehouse_heat: [],
  flows: [],
  risks: []
};

const EMPTY_WORKFLOW_BOARD: OperationsWorkflowBoard = {
  generated_at: '',
  source: 'empty',
  summary: {
    title: '每日制造经营作战流',
    health_score: 0,
    active_stages: 0,
    attention_count: 0,
    blocked_count: 0,
    next_action: '等待后端数据连接',
    next_path: '/app/overview',
    cadence: '库存、采购、履约、回款、归档按状态流转',
    shift_window: '08:30-18:00',
    commander: '制造运营负责人',
    evidence_count: 0,
    open_action_count: 0
  },
  stages: [],
  handoffs: [],
  bottlenecks: [],
  action_queue: [],
  service_boundaries: [],
  deployment_checks: [],
  role_views: [],
  role_command_center: [],
  execution_events: [],
  data_contracts: []
};

const EMPTY_ERP_CONTROL_TOWER: ErpControlTower = {
  generated_at: '',
  source: 'empty',
  summary: {
    title: 'Nexus Prime ERP 控制塔',
    control_score: 0,
    health_score: 0,
    total_records: 0,
    revenue: 0,
    cash_exposure: 0,
    open_actions: 0,
    risk_count: 0,
    evidence_count: 0,
    service_boundaries: 0,
    next_action: '等待控制塔数据',
    next_path: '/app/overview',
    cadence: '低库存、采购、收货、履约、回款、报表归档串成一条主线'
  },
  domain_health: [],
  action_queue: [],
  readiness: [],
  evidence_ledger: [],
  workflow: {
    stages: [],
    handoffs: [],
    bottlenecks: []
  }
};

type Tone = 'default' | 'success' | 'warning' | 'danger' | 'info';

interface HeroMetric {
  label: string;
  value: string;
  note: string;
  path: string;
  tone: Tone;
}

interface WorkflowStep {
  code: string;
  label: string;
  metric: string;
  detail: string;
  path: string;
  tone: Tone;
}

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CommonModule,
    RouterLink,
    NgxEchartsDirective,
    ButtonModule,
    TagModule,
    SceneBackgroundComponent,
    NexusRevealDirective,
    NexusSpotlightDirective
  ],
  template: `
    <section class="ops-atlas-page command-atlas command-overview-lean">
      <nexus-scene-background image="/images/control-dashboard-wide.jpg"></nexus-scene-background>

      <header class="command-lean-hero" nexusReveal>
        <figure class="command-hero-photo" nexusSpotlight>
          <img [src]="heroPhoto().src" [alt]="heroPhoto().alt" fetchpriority="high" decoding="async" />
          <figcaption>
            <span>{{ heroPhoto().label }}</span>
            <strong>{{ heroPhoto().caption }}</strong>
          </figcaption>
        </figure>

        <div class="command-hero-copy">
          <span class="atlas-kicker">ERP 控制塔</span>
          <h1>{{ controlTower().summary.title }}</h1>
          <p>{{ controlTower().summary.cadence }}。页面只保留当班最需要看的经营信号，更多细节进入对应业务模块处理。</p>

          <div class="command-control-card" [class.warning]="controlScore() < 80" [class.danger]="controlScore() < 60" nexusSpotlight>
            <span>经营控制分</span>
            <strong>{{ controlScore() }}%</strong>
            <em>{{ controlTower().summary.next_action }}</em>
          </div>

          <div class="command-hero-actions">
            <a pButton routerLink="/app/inventory/replenishment">
              <i class="pi pi-bolt"></i>
              处理低库存
            </a>
            <a pButton severity="secondary" routerLink="/app/procurement/orders">
              <i class="pi pi-check-circle"></i>
              审批采购
            </a>
            <a pButton severity="info" routerLink="/app/reports">
              <i class="pi pi-chart-line"></i>
              生成日报
            </a>
          </div>
        </div>
      </header>

      <section class="command-lean-metrics" aria-label="关键经营指标" nexusReveal [nexusRevealDelay]="80">
        @for (metric of heroMetrics(); track metric.label) {
          <a [routerLink]="metric.path" [class.warning]="metric.tone === 'warning'" [class.danger]="metric.tone === 'danger'" [class.success]="metric.tone === 'success'" nexusSpotlight>
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}</strong>
            <em>{{ metric.note }}</em>
          </a>
        }
      </section>

      <section class="atlas-panel command-workflow-panel" aria-label="ERP 业务闭环" nexusReveal [nexusRevealDelay]="120">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">业务闭环</span>
            <h2>从库存信号到经营归档</h2>
          </div>
          <p-tag [severity]="loading() ? 'warn' : 'success'" [value]="loading() ? '同步中' : '后端聚合'" />
        </div>
        <div class="command-workflow-rail">
          @for (step of workflowSteps(); track step.code) {
            <a [routerLink]="step.path" [class.warning]="step.tone === 'warning'" [class.danger]="step.tone === 'danger'" [class.success]="step.tone === 'success'" nexusSpotlight>
              <span>{{ step.code }}</span>
              <strong>{{ step.label }}</strong>
              <em>{{ step.metric }}</em>
              <small>{{ step.detail }}</small>
            </a>
          }
        </div>
      </section>

      <section class="command-main-grid" aria-label="经营图表与待办">
        <article class="atlas-panel command-chart-panel" nexusReveal [nexusRevealDelay]="160">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">经营趋势</span>
              <h2>库存、采购、履约与现金风险</h2>
            </div>
            <span>{{ workflowBoard().summary.shift_window || '当班窗口' }}</span>
          </div>
          <div class="command-lean-chart" echarts [options]="operationsChart()"></div>
        </article>

        <aside class="atlas-panel command-action-panel" nexusReveal [nexusRevealDelay]="200">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">当班待办</span>
              <h2>只看下一步</h2>
            </div>
            <span>{{ actionQueue().length }} 项</span>
          </div>
          <div class="command-action-list">
            @for (item of actionQueue(); track item.title) {
              <a [routerLink]="item.path" [class.danger]="item.priority === 'P0'" [class.warning]="item.priority === 'P1'" nexusSpotlight>
                <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
                <strong>{{ item.title }}</strong>
                <span>{{ item.owner }} · {{ item.metric }}</span>
                <em>{{ item.evidence }}</em>
              </a>
            }
          </div>
        </aside>
      </section>

      <section class="atlas-panel command-domain-panel" aria-label="ERP 模块边界" nexusReveal [nexusRevealDelay]="240">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">模块边界</span>
            <h2>每个页面只承担一个业务对象</h2>
          </div>
          <span>{{ controlTower().summary.service_boundaries || 6 }} 个服务边界</span>
        </div>
        <div class="command-domain-grid">
          @for (domain of domainCards(); track domain.label) {
            <a [routerLink]="domain.path" [class.warning]="domain.tone === 'warning'" [class.danger]="domain.tone === 'danger'" [class.success]="domain.tone === 'success'" nexusSpotlight>
              <span>{{ domain.owner }}</span>
              <strong>{{ domain.label }}</strong>
              <em>{{ domain.metric }}</em>
              <small>{{ domain.evidence }}</small>
            </a>
          }
        </div>
      </section>

      <section class="command-evidence-strip lean" aria-label="真实现场图片证据" nexusReveal [nexusRevealDelay]="280">
        <div class="command-section-head">
          <div>
            <span class="atlas-kicker">现场证据</span>
            <h2>真实工作流照片</h2>
          </div>
          <span>首页同源视觉资产</span>
        </div>
        <div class="command-evidence-rail">
          @for (photo of evidencePhotos(); track photo.src) {
            <figure nexusSpotlight>
              <img [src]="photo.src" [alt]="photo.alt" loading="eager" decoding="async" />
              <span>{{ photo.label }}</span>
              <strong>{{ photo.caption }}</strong>
            </figure>
          }
        </div>
      </section>
    </section>
  `
})
export class CommandCenterPage implements OnInit {
  private readonly api = inject(ApiService);

  protected readonly loading = signal(false);
  protected readonly data = signal<ManufacturingCommandCenter>(EMPTY_COMMAND_CENTER);
  protected readonly workflowBoard = signal<OperationsWorkflowBoard>(EMPTY_WORKFLOW_BOARD);
  protected readonly controlTower = signal<ErpControlTower>(EMPTY_ERP_CONTROL_TOWER);

  protected readonly heroPhoto = computed<VisualAsset>(() => COMMAND_CENTER_PHOTOS[28] ?? COMMAND_CENTER_PHOTOS[0]);
  protected readonly controlScore = computed(() => {
    const summary = this.controlTower().summary;
    const score = summary.control_score || summary.health_score || this.workflowBoard().summary.health_score;
    if (score) {
      return Math.round(score);
    }
    const kpis = this.data().kpis;
    return Math.max(54, Math.min(96, 88 - kpis.low_stock_products * 2 - this.data().risks.length * 4));
  });

  protected readonly heroMetrics = computed<HeroMetric[]>(() => {
    const kpis = this.data().kpis;
    return [
      {
        label: '低库存',
        value: `${kpis.low_stock_products || 0} 项`,
        note: '进入补货建议队列',
        path: '/app/inventory/replenishment',
        tone: kpis.low_stock_products > 0 ? 'warning' : 'success'
      },
      {
        label: '待审批采购',
        value: `${kpis.pending_purchase || 0} 单`,
        note: '审批后进入收货窗口',
        path: '/app/procurement/orders',
        tone: kpis.pending_purchase > 0 ? 'warning' : 'success'
      },
      {
        label: '逾期应收',
        value: this.compactMoney(kpis.overdue_amount),
        note: '影响客户信用与现金节奏',
        path: '/app/finance/receivables',
        tone: kpis.overdue_amount > 0 ? 'danger' : 'success'
      },
      {
        label: '库存水位',
        value: this.compactNumber(kpis.stock_quantity),
        note: '来自仓库与批次流水',
        path: '/app/inventory/stock',
        tone: 'info'
      }
    ];
  });

  protected readonly workflowSteps = computed<WorkflowStep[]>(() => {
    const stages = this.controlTower().workflow.stages.length
      ? this.controlTower().workflow.stages
      : this.workflowBoard().stages;
    if (stages.length) {
      return stages.slice(0, 6).map(stage => ({
        code: stage.code,
        label: stage.label,
        metric: stage.value || stage.sla,
        detail: stage.detail || stage.next_action,
        path: stage.path,
        tone: this.toneFromStatus(stage.status)
      }));
    }
    return [
      { code: '01', label: '低库存', metric: `${this.data().kpis.low_stock_products || 0} 项`, detail: '低水位物料先进入补货队列。', path: '/app/inventory/replenishment', tone: 'warning' },
      { code: '02', label: '采购审批', metric: `${this.data().kpis.pending_purchase || 0} 单`, detail: '采购负责人按金额、供应商和仓库确认。', path: '/app/procurement/orders', tone: 'warning' },
      { code: '03', label: '收货入库', metric: '质检后入库', detail: '到货、质检、批次和库位一次记录。', path: '/app/quality', tone: 'info' },
      { code: '04', label: '销售履约', metric: '库存锁定', detail: '订单发货会联动库存流水和应收。', path: '/app/sales/orders', tone: 'info' },
      { code: '05', label: '应收回款', metric: this.compactMoney(this.data().kpis.overdue_amount), detail: '回款后释放客户信用额度。', path: '/app/finance/receivables', tone: this.data().kpis.overdue_amount > 0 ? 'danger' : 'success' },
      { code: '06', label: '经营归档', metric: '日报', detail: '报表、文件和审计记录归档。', path: '/app/reports', tone: 'success' }
    ];
  });

  protected readonly actionQueue = computed(() => {
    const towerActions = this.controlTower().action_queue.map(item => ({
      title: item.title,
      owner: item.owner,
      priority: item.priority,
      path: item.path,
      metric: item.metric,
      evidence: item.evidence
    }));
    if (towerActions.length) {
      return towerActions.slice(0, 5);
    }
    const risks = this.data().risks.map((risk, index) => ({
      title: risk.title,
      owner: risk.type,
      priority: risk.level === 'critical' ? 'P0' : 'P1',
      path: risk.type.includes('应收') ? '/app/finance/receivables' : risk.type.includes('采购') ? '/app/procurement/orders' : '/app/inventory/replenishment',
      metric: risk.level,
      evidence: risk.description || '来自经营聚合接口'
    }));
    return risks.length ? risks.slice(0, 5) : [
      { title: '复核低库存队列', owner: '仓库主管', priority: 'P1', path: '/app/inventory/replenishment', metric: '补货建议', evidence: '根据安全库存和当前库存生成采购草稿' },
      { title: '审批待处理采购', owner: '采购负责人', priority: 'P1', path: '/app/procurement/orders', metric: '采购审批', evidence: '审批后进入收货与质检窗口' },
      { title: '生成经营日报', owner: '运营负责人', priority: 'P2', path: '/app/reports', metric: '日报归档', evidence: '报表会进入文件中心和通知中心' }
    ];
  });

  protected readonly domainCards = computed(() => {
    const domains = this.controlTower().domain_health.map(domain => ({
      label: domain.label,
      owner: domain.owner,
      path: domain.path,
      metric: domain.metric,
      evidence: domain.evidence,
      tone: this.toneFromStatus(domain.status)
    }));
    if (domains.length) {
      return domains.slice(0, 6);
    }
    return [
      { label: '物料与库存', owner: '仓配域', path: '/app/inventory/products', metric: this.compactNumber(this.data().kpis.stock_quantity), evidence: '主数据、批次、库位和水位', tone: 'info' as Tone },
      { label: '采购补货', owner: '供应域', path: '/app/procurement/orders', metric: `${this.data().kpis.pending_purchase || 0} 单`, evidence: '补货建议、审批、收货和供应商绩效', tone: 'warning' as Tone },
      { label: '销售履约', owner: '履约域', path: '/app/sales/orders', metric: this.compactMoney(this.data().kpis.order_amount), evidence: '订单、出库、客户窗口和应收联动', tone: 'success' as Tone },
      { label: '应收风控', owner: '财务域', path: '/app/finance/receivables', metric: this.compactMoney(this.data().kpis.overdue_amount), evidence: '账龄、信用、回款和审计', tone: this.data().kpis.overdue_amount > 0 ? 'danger' as Tone : 'success' as Tone },
      { label: '报表归档', owner: '分析域', path: '/app/reports', metric: '日报', evidence: '经营报表、导出文件和通知留痕', tone: 'info' as Tone },
      { label: '系统审计', owner: '平台域', path: '/app/system/audit', metric: '全链路', evidence: '权限、关键动作和文件访问记录', tone: 'success' as Tone }
    ];
  });

  protected readonly evidencePhotos = computed<VisualAsset[]>(() => [
    COMMAND_CENTER_PHOTOS[1],
    COMMAND_CENTER_PHOTOS[6],
    COMMAND_CENTER_PHOTOS[14],
    COMMAND_CENTER_PHOTOS[16]
  ].filter(Boolean) as VisualAsset[]);

  protected readonly operationsChart = computed<EChartsCoreOption>(() => {
    const kpis = this.data().kpis;
    const labels = ['库存', '采购', '履约', '应收', '报表'];
    return {
      backgroundColor: 'transparent',
      color: ['#1f5f7a', '#2ca58d', '#d99135'],
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top', '#64748b'),
      grid: { left: 20, right: 20, top: 46, bottom: 24, containLabel: true },
      xAxis: {
        type: 'category',
        data: labels,
        axisLine: { show: false },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(100,116,139,.16)', type: 'dashed' } }
      },
      series: [
        {
          name: '业务量',
          type: 'bar',
          barWidth: 28,
          data: [
            Math.max(1, Math.round(kpis.stock_quantity / 100)),
            kpis.pending_purchase,
            Math.max(1, Math.round(kpis.order_amount / 10000)),
            Math.max(1, Math.round(kpis.overdue_amount / 10000)),
            this.controlTower().summary.evidence_count || 8
          ],
          itemStyle: { borderRadius: [10, 10, 3, 3] }
        },
        {
          name: '健康度',
          type: 'line',
          smooth: true,
          symbolSize: 8,
          data: [86, 78, 82, this.data().kpis.overdue_amount > 0 ? 62 : 88, this.controlScore()],
          lineStyle: { width: 3 }
        }
      ]
    };
  });

  ngOnInit(): void {
    this.loading.set(true);
    this.api.get<ErpControlTower>('erp/control-tower').pipe(
      catchError(() => of(EMPTY_ERP_CONTROL_TOWER))
    ).subscribe(result => this.controlTower.set(result));
    this.api.get<ManufacturingCommandCenter>('manufacturing/command-center').pipe(
      catchError(() => of(EMPTY_COMMAND_CENTER)),
      finalize(() => this.loading.set(false))
    ).subscribe(result => this.data.set(result));
    this.api.get<OperationsWorkflowBoard>('manufacturing/workflow-board').pipe(
      catchError(() => of(EMPTY_WORKFLOW_BOARD))
    ).subscribe(result => this.workflowBoard.set(result));
  }

  protected prioritySeverity(priority: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast' {
    if (priority === 'P0') {
      return 'danger';
    }
    if (priority === 'P1') {
      return 'warn';
    }
    return 'success';
  }

  private toneFromStatus(status: string): Tone {
    if (status === 'blocked' || status === 'critical' || status === 'danger') {
      return 'danger';
    }
    if (status === 'attention' || status === 'warning') {
      return 'warning';
    }
    if (status === 'complete' || status === 'ready' || status === 'success') {
      return 'success';
    }
    return 'info';
  }

  private compactMoney(value: number): string {
    return new Intl.NumberFormat('zh-CN', {
      style: 'currency',
      currency: 'CNY',
      notation: 'compact',
      maximumFractionDigits: 1
    }).format(value || 0);
  }

  private compactNumber(value: number): string {
    return new Intl.NumberFormat('zh-CN', {
      notation: 'compact',
      maximumFractionDigits: 1
    }).format(value || 0);
  }
}
