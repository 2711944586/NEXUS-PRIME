import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { ButtonModule } from 'primeng/button';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { ErpControlTower, ManufacturingCommandCenter, OperationsWorkflowBoard } from '../core/models';
import { COMMAND_CENTER_PHOTOS, VisualAsset } from '../core/visual-assets';
import { CountUpNumberComponent, NexusRevealDirective, NexusSpotlightDirective, SceneBackgroundComponent } from '../motion';
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
    next_action: '等待数据连接',
    next_path: '/app/overview',
    cadence: '库存、采购、履约、回款、归档同屏复盘',
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
    cadence: '库存、采购、履约、回款、归档同屏复盘'
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

type WarehouseHeatItem = ManufacturingCommandCenter['warehouse_heat'][number];
type FlowItem = ManufacturingCommandCenter['flows'][number];
type RiskItem = ManufacturingCommandCenter['risks'][number];
type WorkflowFilter = 'all' | 'attention' | 'blocked';
type ChartMode = 'flow' | 'risk' | 'warehouse' | 'health' | 'pressure' | 'pulse';

@Component({
  standalone: true,
  imports: [
    CommonModule,
    NgxEchartsDirective,
    ButtonModule,
    TagModule,
    SceneBackgroundComponent,
    NexusRevealDirective,
    NexusSpotlightDirective,
    CountUpNumberComponent
  ],
  template: `
    <section class="ops-atlas-page command-atlas command-overview-refined">
      <nexus-scene-background image="/images/control-dashboard-wide.jpg"></nexus-scene-background>

      <header class="atlas-hero command-hero" nexusReveal [nexusRevealDelay]="60">
        <div class="hero-narrative command-hero-story">
          <span class="atlas-kicker">ERP 控制塔</span>
          <h1>{{ controlTower().summary.title }}</h1>
          <p>{{ controlTower().summary.cadence }}。控制塔把主数据、供应链、制造履约、现金风险和审计证据压到同一条当班主线。</p>

          <div class="command-control-score" [class.ready]="controlTowerScore() >= 82" [class.attention]="controlTowerScore() < 82 && controlTowerScore() >= 62" [class.blocked]="controlTowerScore() < 62" nexusSpotlight>
            <span>经营控制分</span>
            <strong>
              <nexus-count-up-number
                [value]="controlTowerScore()"
                format="percent"
                [compact]="false"
                [maximumFractionDigits]="0"
                ariaLabel="经营控制分"
              ></nexus-count-up-number>
            </strong>
            <em>{{ controlTower().summary.next_action }}</em>
          </div>

          <div class="hero-mini-metrics" aria-label="核心经营指标">
            <div class="mini-metric-card" nexusSpotlight>
              <div class="mini-metric-header">
                <i class="pi pi-shopping-bag"></i>
                <span>订单动能</span>
              </div>
              <strong>
                <nexus-count-up-number
                  [value]="data().kpis.order_amount"
                  format="money"
                  ariaLabel="订单动能"
                ></nexus-count-up-number>
              </strong>
              <div class="mini-metric-trend positive">
                <i class="pi pi-arrow-up"></i>
                <span>+12.5%</span>
              </div>
            </div>
            <div class="mini-metric-card" nexusSpotlight>
              <div class="mini-metric-header">
                <i class="pi pi-box"></i>
                <span>库存周转</span>
              </div>
              <strong>
                <nexus-count-up-number
                  [value]="data().kpis.stock_quantity"
                  format="number"
                  ariaLabel="库存周转"
                ></nexus-count-up-number>
              </strong>
              <div class="mini-metric-trend neutral">
                <i class="pi pi-minus"></i>
                <span>持平</span>
              </div>
            </div>
            <div class="mini-metric-card warning" nexusSpotlight>
              <div class="mini-metric-header">
                <i class="pi pi-bolt"></i>
                <span>低库存预警</span>
              </div>
              <strong>
                <nexus-count-up-number
                  [value]="data().kpis.low_stock_products"
                  format="number"
                  suffix=" 项"
                  [compact]="false"
                  [maximumFractionDigits]="0"
                  ariaLabel="低库存预警"
                ></nexus-count-up-number>
              </strong>
              <div class="mini-metric-trend negative">
                <i class="pi pi-arrow-down"></i>
                <span>需关注</span>
              </div>
            </div>
            <div class="mini-metric-card danger" nexusSpotlight>
              <div class="mini-metric-header">
                <i class="pi pi-wallet"></i>
                <span>现金风险</span>
              </div>
              <strong>
                <nexus-count-up-number
                  [value]="data().kpis.overdue_amount"
                  format="money"
                  ariaLabel="现金风险"
                ></nexus-count-up-number>
              </strong>
              <div class="mini-metric-trend negative">
                <i class="pi pi-exclamation-triangle"></i>
                <span>逾期应收</span>
              </div>
            </div>
          </div>

          <div class="hero-interactive-chart" aria-label="经营趋势图表" nexusSpotlight>
            <div class="chart-header">
              <h3>本周经营趋势</h3>
              <div class="chart-legend">
                <span class="legend-item">
                  <i class="legend-dot primary"></i>
                  订单额
                </span>
                <span class="legend-item">
                  <i class="legend-dot secondary"></i>
                  履约率
                </span>
              </div>
            </div>
            <div class="hero-trend-chart" echarts [options]="heroTrendChart()"></div>
          </div>

          <div class="command-snapshot-row" aria-label="关键经营快照">
            @for (snapshot of heroSnapshots(); track snapshot.label) {
              <article [class.warning]="snapshot.tone === 'warning'">
                <i class="pi" [class]="snapshot.icon"></i>
                <span>{{ snapshot.label }}</span>
                <strong>{{ snapshot.value }}</strong>
                <em>{{ snapshot.note }}</em>
              </article>
            }
          </div>

          <div class="atlas-actions-row">
            <button pButton type="button" (click)="selectChartMode('warehouse')">
              <i class="pi pi-bolt"></i>
              处理低库存
            </button>
            <button pButton type="button" severity="secondary" (click)="selectChartMode('pressure')">
              <i class="pi pi-check-circle"></i>
              审批采购
            </button>
            <button pButton type="button" severity="info" (click)="selectChartMode('pulse')">
              <i class="pi pi-chart-line"></i>
              生成经营日报
            </button>
          </div>
        </div>

        <section class="command-visual-board" aria-label="制造经营现场图片" nexusReveal [nexusRevealDelay]="140" nexusSpotlight>
          <figure class="command-photo-feature">
            <img [src]="featuredPhoto().src" [alt]="featuredPhoto().alt" />
            <figcaption>
              <span>{{ featuredPhoto().label }}</span>
              <strong>{{ featuredPhoto().caption }}</strong>
            </figcaption>
          </figure>
          <div class="command-photo-strip">
            @for (photo of photoStrip().slice(0, 2); track photo.src) {
              <figure>
                <img [src]="photo.src" [alt]="photo.alt" />
                <figcaption>
                  <span>{{ photo.label }}</span>
                  <strong>{{ photo.caption }}</strong>
                </figcaption>
              </figure>
            }
          </div>
        </section>

        <section class="command-hero-chart" aria-label="首页顶部经营图表" nexusReveal [nexusRevealDelay]="180" nexusSpotlight>
          <div class="hero-chart-head">
            <div>
              <span>ERP 闭环指数</span>
              <strong>
                <nexus-count-up-number
                  [value]="healthScore()"
                  format="percent"
                  [compact]="false"
                  [maximumFractionDigits]="0"
                  ariaLabel="ERP 闭环指数"
                ></nexus-count-up-number>
              </strong>
            </div>
            <p-tag severity="success" value="Live" />
          </div>
          <div class="hero-mini-chart" echarts [options]="heroPulseChart()"></div>
        </section>

        <aside class="hero-command-ledger" aria-label="运营关键指标">
          <div class="ledger-row">
            <i class="pi pi-shopping-bag"></i>
            <span>订单金额</span>
            <strong>
              <nexus-count-up-number
                [value]="data().kpis.order_amount"
                format="money"
                ariaLabel="订单金额"
              ></nexus-count-up-number>
            </strong>
          </div>
          <div class="ledger-row">
            <i class="pi pi-box"></i>
            <span>库存水位</span>
            <strong>
              <nexus-count-up-number
                [value]="data().kpis.stock_quantity"
                format="number"
                ariaLabel="库存水位"
              ></nexus-count-up-number>
            </strong>
          </div>
          <div class="ledger-row warning">
            <i class="pi pi-bolt"></i>
            <span>低库存信号</span>
            <strong>
              <nexus-count-up-number
                [value]="data().kpis.low_stock_products"
                format="number"
                suffix=" 项"
                [compact]="false"
                [maximumFractionDigits]="0"
                ariaLabel="低库存信号"
              ></nexus-count-up-number>
            </strong>
          </div>
          <div class="ledger-row danger">
            <i class="pi pi-wallet"></i>
            <span>逾期应收</span>
            <strong>
              <nexus-count-up-number
                [value]="data().kpis.overdue_amount"
                format="money"
                ariaLabel="逾期应收"
              ></nexus-count-up-number>
            </strong>
          </div>
        </aside>
      </header>

      <section class="command-metrics-dashboard" aria-label="实时运营指标">
        <article class="atlas-panel realtime-metrics-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">实时指标</span>
              <h2>关键运营指标实时流</h2>
            </div>
            <p-tag severity="success" value="Live" />
          </div>
          <div class="realtime-metrics-chart" echarts [options]="realtimeMetricsChart()"></div>
        </article>

        <article class="atlas-panel rhythm-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">业务节奏</span>
              <h2>各时段处理量分布</h2>
            </div>
            <span>今日累计处理</span>
          </div>
          <div class="business-rhythm-chart" echarts [options]="businessRhythmChart()"></div>
        </article>
      </section>

      <section class="command-health-indicators" aria-label="业务健康度指示器">
        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">健康度</span>
              <h2>核心业务健康指标</h2>
            </div>
            <span>实时监控</span>
          </div>
          <div class="health-indicator-grid">
            @for (indicator of healthIndicators(); track indicator.label) {
              <div class="health-indicator" [class.healthy]="indicator.score >= 80" [class.warning]="indicator.score < 80 && indicator.score >= 60" [class.critical]="indicator.score < 60">
                <div class="health-icon">
                  <i class="pi" [class]="indicator.icon"></i>
                </div>
                <div class="health-content">
                  <span>{{ indicator.label }}</span>
                  <div class="health-score">
                    <strong>{{ indicator.score }}%</strong>
                    <em>{{ indicator.status }}</em>
                  </div>
                  <div class="health-bar">
                    <span [style.width.%]="indicator.score"></span>
                  </div>
                  <small>{{ indicator.detail }}</small>
                </div>
              </div>
            }
          </div>
        </article>
      </section>

      <section class="atlas-panel command-intelligence-panel">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">经营图谱</span>
            <h2>核心经营图表</h2>
          </div>
          <div class="command-chart-tabs" aria-label="首页图表模式">
            @for (mode of chartModes; track mode.key) {
              <button type="button" [class.active]="chartMode() === mode.key" (click)="selectChartMode(mode.key)">
                <i class="pi" [class]="mode.icon"></i>
                {{ mode.label }}
              </button>
            }
          </div>
        </div>
        <div class="command-intelligence-grid">
          <div class="command-big-chart" echarts [options]="activeCommandChart()"></div>
          <aside class="command-insight-stack">
            @for (item of chartInsights(); track item.title) {
              <button type="button" [class.active]="chartMode() === item.mode" [class.warning]="item.tone === 'warning'" (click)="selectChartMode(item.mode)">
                <span>{{ item.kicker }}</span>
                <strong>{{ item.title }}</strong>
                <em>{{ item.value }}</em>
              </button>
            }
          </aside>
        </div>
      </section>

      <section class="command-evidence-strip" aria-label="运营现场证据带">
        <div class="command-section-head">
          <div>
            <span class="atlas-kicker">现场证据</span>
            <h2>四张关键现场图</h2>
          </div>
          <span>固定现场证据</span>
        </div>
        <div class="command-evidence-rail">
          @for (photo of evidencePhotos().slice(0, 4); track photo.src) {
            <figure>
              <img [src]="photo.src" [alt]="photo.alt" loading="lazy" />
              <span>{{ photo.label }}</span>
              <strong>{{ photo.caption }}</strong>
            </figure>
          }
        </div>
      </section>

      <section class="atlas-panel command-process-panel">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">流程闭环</span>
            <h2>从库存信号到经营归档</h2>
          </div>
          <span class="sync-badge" [class.loading]="loading()">后端聚合</span>
        </div>
        <div class="command-process-summary">
          <article class="command-stage-card" [class.warning]="selectedWorkflowStep().tone === 'warning'" [class.success]="selectedWorkflowStep().tone === 'success'">
            <span>当前链路</span>
            <strong>{{ selectedWorkflowStep().label || '低库存' }}</strong>
            <em>{{ selectedWorkflowStep().metric || '生成/接受' }}</em>
            <small>{{ selectedWorkflowStep().path || '/app/inventory/products' }}</small>
          </article>
          <div class="command-stage-detail">
            <span>闭环说明</span>
            <strong>库存水位、采购审批、收货入库、销售履约、应收回款和报表归档串成一条可追踪主线。</strong>
            <em>{{ workflowBoard().summary.cadence }}</em>
          </div>
        </div>
        <div class="hero-operations-map" aria-label="制造仓配业务链路">
          @for (step of processFlow(); track step.code) {
            <button class="map-step" type="button" [class.active]="selectedWorkflowStep().code === step.code" [class.warning]="step.tone === 'warning'" [class.success]="step.tone === 'success'" (click)="selectFlowStep(step.code)">
              <span>{{ step.code }}</span>
              <strong>{{ step.label }}</strong>
              <em>{{ step.metric }}</em>
            </button>
          }
        </div>
      </section>

      <section class="command-health-indicators" aria-label="业务健康度指示器">
        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">健康度</span>
              <h2>核心业务健康指标</h2>
            </div>
            <span>实时监控</span>
          </div>
          <div class="health-indicator-grid">
            @for (indicator of healthIndicators(); track indicator.label) {
              <div class="health-indicator" [class.healthy]="indicator.score >= 80" [class.warning]="indicator.score < 80 && indicator.score >= 60" [class.critical]="indicator.score < 60">
                <div class="health-icon">
                  <i class="pi" [class]="indicator.icon"></i>
                </div>
                <div class="health-content">
                  <span>{{ indicator.label }}</span>
                  <div class="health-score">
                    <strong>{{ indicator.score }}%</strong>
                    <em>{{ indicator.status }}</em>
                  </div>
                  <div class="health-bar">
                    <span [style.width.%]="indicator.score"></span>
                  </div>
                  <small>{{ indicator.detail }}</small>
                </div>
              </div>
            }
          </div>
        </article>
      </section>

      <section class="command-chart-gallery" aria-label="经营辅助图表">
        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">流转节奏</span>
              <h2>仓配吞吐和履约节拍</h2>
            </div>
          </div>
          <div class="mini-chart" echarts [options]="movementFlowChart()"></div>
        </article>
        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">仓库水位</span>
              <h2>库存热区与补货压力</h2>
            </div>
          </div>
          <div class="mini-chart" echarts [options]="warehouseChart()"></div>
        </article>
        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">压力雷达</span>
              <h2>库存、采购、应收同屏</h2>
            </div>
          </div>
          <div class="mini-chart" echarts [options]="pressureRadarChart()"></div>
        </article>
      </section>

      <section class="atlas-control-grid command-flow-risk-grid">
        <article class="atlas-panel factory-map-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">流向网络</span>
              <h2>供应、工厂仓、区域仓、客户的流向</h2>
            </div>
            <span class="sync-badge" [class.loading]="loading()">实时读取</span>
          </div>

          <div class="factory-canvas">
            <div class="factory-node supplier">
              <img [src]="operationVisuals[1].src" [alt]="operationVisuals[1].alt" />
              <span>供应端</span>
              <strong>{{ firstFlow()?.from ?? '供应商集群' }}</strong>
              <em>{{ firstFlow()?.value ?? 0 }} 批入厂</em>
            </div>
            <div class="factory-node plant">
              <img [src]="operationVisuals[0].src" [alt]="operationVisuals[0].alt" />
              <span>工厂仓</span>
              <strong>{{ primaryWarehouse()?.name ?? '华东工厂仓' }}</strong>
              <em>{{ compactNumber(primaryWarehouse()?.stock_quantity ?? data().kpis.stock_quantity) }} 件</em>
            </div>
            <div class="factory-node region">
              <img [src]="operationVisuals[2].src" [alt]="operationVisuals[2].alt" />
              <span>区域仓</span>
              <strong>{{ secondaryWarehouse()?.name ?? '长三角区域仓' }}</strong>
              <em>{{ secondFlow()?.value ?? 0 }} 单调拨</em>
            </div>
            <div class="factory-node customer">
              <img [src]="operationVisuals[4].src" [alt]="operationVisuals[4].alt" />
              <span>客户侧</span>
              <strong>{{ finalFlow()?.to ?? '装配中心' }}</strong>
              <em>{{ finalFlow()?.value ?? 0 }} 单履约</em>
            </div>
            <span class="route-line r1"></span>
            <span class="route-line r2"></span>
            <span class="route-line r3"></span>
          </div>

          <div class="factory-throughput-strip" aria-label="流向吞吐摘要">
            <span>
              <i class="pi pi-download"></i>
              <strong>{{ firstFlow()?.value ?? 0 }}</strong>
              <em>入厂批次</em>
            </span>
            <span>
              <i class="pi pi-sync"></i>
              <strong>{{ secondFlow()?.value ?? 0 }}</strong>
              <em>调拨单量</em>
            </span>
            <span>
              <i class="pi pi-send"></i>
              <strong>{{ finalFlow()?.value ?? 0 }}</strong>
              <em>客户履约</em>
            </span>
          </div>
        </article>

        <article class="atlas-panel risk-wall-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">优先级</span>
              <h2>现场优先处理墙</h2>
            </div>
            <span>{{ visibleRisks().length }} 项</span>
          </div>
          <div class="risk-wall">
            @if (visibleRisks().length) {
              @for (risk of visibleRisks(); track risk.title + risk.type; let riskIndex = $index) {
                <article class="risk-brick" [class.critical]="risk.level === 'critical'">
                  <img [src]="riskPhoto(riskIndex).src" [alt]="riskPhoto(riskIndex).alt" />
                  <p-tag [severity]="risk.level === 'critical' ? 'danger' : 'warn'" [value]="risk.type" />
                  <strong>{{ risk.title }}</strong>
                  <span>{{ risk.description }}</span>
                </article>
              }
            } @else {
              <div class="risk-brick calm">
                <p-tag severity="success" value="稳定" />
                <strong>当前没有阻塞风险</strong>
                <span>建议继续复核报表、权限和审计链路。</span>
              </div>
            }
          </div>
        </article>
      </section>

      <section class="command-intelligence-insights" aria-label="智能经营建议">
        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">智能建议</span>
              <h2>基于当前数据的经营建议</h2>
            </div>
            <p-tag severity="info" value="AI 生成" />
          </div>
          <div class="insight-cards-grid">
            @for (insight of intelligenceInsights(); track insight.title) {
              <article class="insight-card" [class.priority]="insight.priority === 'high'">
                <div class="insight-icon">
                  <i class="pi" [class]="insight.icon"></i>
                </div>
                <div class="insight-content">
                  <strong>{{ insight.title }}</strong>
                  <p>{{ insight.description }}</p>
                  <div class="insight-metrics">
                    <span><i class="pi pi-arrow-up"></i> {{ insight.impact }}</span>
                    <span><i class="pi pi-clock"></i> {{ insight.timeline }}</span>
                  </div>
                </div>
              </article>
            }
          </div>
        </article>
      </section>

      <section class="command-trend-comparison" aria-label="趋势对比分析">
        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">趋势对比</span>
              <h2>本月与上月核心指标对比</h2>
            </div>
            <span>数据更新于 {{ currentDate() }}</span>
          </div>
          <div class="trend-comparison-grid">
            @for (trend of trendComparisons(); track trend.metric) {
              <article class="trend-card" [class.positive]="trend.change > 0" [class.negative]="trend.change < 0">
                <div class="trend-header">
                  <span>{{ trend.metric }}</span>
                  <div class="trend-badge" [class.up]="trend.change > 0" [class.down]="trend.change < 0">
                    <i class="pi" [class.pi-arrow-up]="trend.change > 0" [class.pi-arrow-down]="trend.change < 0"></i>
                    {{ Math.abs(trend.change) }}%
                  </div>
                </div>
                <div class="trend-values">
                  <div class="trend-current">
                    <strong>{{ trend.current }}</strong>
                    <em>本月</em>
                  </div>
                  <div class="trend-previous">
                    <span>{{ trend.previous }}</span>
                    <em>上月</em>
                  </div>
                </div>
                <small>{{ trend.note }}</small>
              </article>
            }
          </div>
        </article>
      </section>

      <section class="playbook-board" aria-label="当班处理剧本">
        @for (item of playbook(); track item.title) {
          <article [class.warning]="item.tone === 'warning'">
            <img [src]="playbookPhoto(item.code).src" [alt]="playbookPhoto(item.code).alt" />
            <span>{{ item.code }}</span>
            <strong>{{ item.title }}</strong>
            <em>{{ item.copy }}</em>
          </article>
        }
      </section>

      <section class="erp-control-layer" aria-label="ERP 控制塔运行层">
        <article class="atlas-panel erp-domain-health">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">域健康</span>
              <h2>五个经营域的真实水位</h2>
            </div>
            <span>{{ controlTower().summary.next_action }}</span>
          </div>
          <div class="erp-domain-grid">
            @for (domain of towerDomains(); track domain.key) {
              <article
                [class.ready]="domain.status === 'ready'"
                [class.attention]="domain.status === 'attention'"
                [class.blocked]="domain.status === 'blocked'"
              >
                <span>{{ domain.owner }}</span>
                <strong>{{ domain.label }}</strong>
                <b>{{ domain.score }}%</b>
                <em>{{ domain.metric }}</em>
                <small>{{ domain.evidence }}</small>
                <i aria-hidden="true"><small [style.width.%]="domain.score"></small></i>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel erp-action-board">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">当班动作</span>
              <h2>后端聚合的下一步</h2>
            </div>
            <p-tag severity="warn" [value]="controlTower().summary.open_actions + ' open'" />
          </div>
          <div class="erp-action-grid">
            <div class="erp-action-list">
              @for (action of towerActions(); track action.id) {
                <article [class.p0]="action.priority === 'P0'" [class.p1]="action.priority === 'P1'" [class.p2]="action.priority === 'P2'">
                  <span>{{ action.priority }}</span>
                  <strong>{{ action.title }}</strong>
                  <em>{{ action.owner }} · {{ action.due }}</em>
                  <b>{{ action.metric }}</b>
                  <small>{{ action.evidence }}</small>
                </article>
              }
            </div>
            <div class="erp-priority-summary">
              <div class="priority-stat p0">
                <i class="pi pi-exclamation-circle"></i>
                <div>
                  <span>P0 紧急</span>
                  <strong>{{ priorityCount('P0') }}</strong>
                  <em>需立即处理</em>
                </div>
              </div>
              <div class="priority-stat p1">
                <i class="pi pi-info-circle"></i>
                <div>
                  <span>P1 重要</span>
                  <strong>{{ priorityCount('P1') }}</strong>
                  <em>本周内完成</em>
                </div>
              </div>
              <div class="priority-stat p2">
                <i class="pi pi-check-circle"></i>
                <div>
                  <span>P2 常规</span>
                  <strong>{{ priorityCount('P2') }}</strong>
                  <em>按计划推进</em>
                </div>
              </div>
            </div>
          </div>
        </article>
      </section>

      @if (false) {
      <section class="atlas-panel shift-workflow-board" aria-label="每日制造经营作战流">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">工作流作战图</span>
            <h2>{{ workflowBoard().summary.title }}</h2>
          </div>
          <div class="shift-board-tools">
            <div class="shift-lens-switch" aria-label="阶段筛选">
              @for (filter of workflowFilters; track filter.key) {
                <button type="button" [class.active]="workflowFilter() === filter.key" (click)="selectWorkflowFilter(filter.key)">
                  {{ filter.label }}
                </button>
              }
            </div>
            <button type="button" (click)="focusPath(workflowBoard().summary.next_path)">
              {{ workflowBoard().summary.next_action }}
            </button>
          </div>
        </div>

        <div class="shift-workflow-summary">
          <div class="shift-health-dial" [style.--workflow-health]="workflowBoard().summary.health_score + '%'">
            <span>闭环健康</span>
            <strong>{{ workflowBoard().summary.health_score }}%</strong>
            <em>{{ workflowBoard().summary.cadence }}</em>
          </div>
          <div class="shift-role-strip" aria-label="角色视图">
            @for (role of workflowBoard().role_views; track role.role) {
              <article>
                <span>{{ role.role }}</span>
                <strong>{{ role.focus }}</strong>
              </article>
            }
          </div>
        </div>

        <div class="shift-command-deck" aria-label="班次执行控制层">
          <article class="shift-brief-card">
            <span>班次指挥</span>
            <strong>{{ workflowBoard().summary.commander || '制造运营负责人' }}</strong>
            <em>{{ workflowBoard().summary.shift_window || '08:30-18:00' }} · {{ workflowGeneratedAt() | date:'MM-dd HH:mm' }}</em>
            <div>
              <b>{{ workflowBoard().summary.open_action_count || workflowActions().length }}</b>
              <small>开放动作</small>
            </div>
            <div>
              <b>{{ workflowBoard().summary.evidence_count || 0 }}</b>
              <small>证据留痕</small>
            </div>
          </article>

          <div class="shift-action-queue" aria-label="下一步动作队列">
            <div class="shift-subhead">
              <span>执行队列</span>
              <strong>{{ workflowActions().length }} 个当班动作</strong>
            </div>
            @if (workflowActions().length) {
              @for (action of workflowActions(); track action.key) {
                <button
                  type="button"
                  (click)="focusPath(action.path)"
                  [class.p0]="action.priority === 'P0'"
                  [class.p1]="action.priority === 'P1'"
                  [class.p2]="action.priority === 'P2'"
                >
                  <span>{{ action.priority }}</span>
                  <strong>{{ action.title }}</strong>
                  <em>{{ action.owner }} · {{ action.due }}</em>
                  <b>{{ action.metric }}</b>
                  <small>{{ action.evidence }}</small>
                </button>
              }
            } @else {
              <div class="shift-calm-state">
                <span>暂无开放动作</span>
                <strong>进入报表归档、权限和审计复核。</strong>
              </div>
            }
          </div>
        </div>

        <div class="shift-intelligence-grid" aria-label="角色指挥席与事件流">
          <section class="shift-role-command" aria-label="角色指挥席">
            <div class="shift-subhead">
              <span>角色指挥席</span>
              <strong>{{ workflowRoleCommands().length }} 个责任座席</strong>
            </div>
            @for (role of workflowRoleCommands(); track role.role) {
              <button
                type="button"
                (click)="focusPath(role.path)"
                [class.ready]="role.readiness === 'ready'"
                [class.attention]="role.readiness === 'attention'"
                [class.blocked]="role.readiness === 'blocked'"
              >
                <span>{{ role.role }}</span>
                <strong>{{ role.primary_metric }}</strong>
                <em>{{ role.owner }} · {{ role.next_action }}</em>
                <small>{{ role.evidence }}</small>
                <b>{{ role.workload }}</b>
                <div>
                  @for (domain of role.domains.slice(0, 4); track domain) {
                    <i>{{ domain }}</i>
                  }
                </div>
              </button>
            }
          </section>

          <section class="shift-event-timeline" aria-label="现场事件时间线">
            <div class="shift-subhead">
              <span>现场事件流</span>
              <strong>{{ workflowEvents().length }} 条最近动作</strong>
            </div>
            @if (workflowEvents().length) {
              @for (event of workflowEvents(); track event.id) {
                <button
                  type="button"
                  (click)="focusPath(event.path)"
                  [class.ready]="event.severity === 'ready'"
                  [class.complete]="event.severity === 'complete'"
                  [class.attention]="event.severity === 'attention'"
                  [class.blocked]="event.severity === 'blocked'"
                >
                  <time [attr.datetime]="event.at">{{ event.at | date:'MM-dd HH:mm' }}</time>
                  <span>{{ event.module }}</span>
                  <strong>{{ event.title }}</strong>
                  <em>{{ event.actor }} · {{ event.detail }}</em>
                  <b>{{ event.metric }}</b>
                  <small>{{ event.evidence }}</small>
                </button>
              }
            } @else {
              <div class="shift-calm-state">
                <span>暂无事件流</span>
                <strong>完成库存、采购、履约、应收或报表动作后会自动形成时间线。</strong>
              </div>
            }
          </section>
        </div>

        <div class="shift-stage-rail" aria-label="跨模块闭环阶段">
          @for (stage of workflowStages(); track stage.key) {
            <button
              type="button"
              class="shift-stage-card"
              [class.complete]="stage.status === 'complete'"
              [class.ready]="stage.status === 'ready'"
              [class.attention]="stage.status === 'attention'"
              [class.blocked]="stage.status === 'blocked'"
              (click)="focusPath(stage.path)"
            >
              <span>{{ stage.code }}</span>
              <strong>{{ stage.label }}</strong>
              <b>{{ stage.value }}</b>
              <em>{{ stage.owner }} · {{ stage.sla }}</em>
              <p>{{ stage.detail }}</p>
              <i aria-hidden="true"><small [style.width.%]="stage.progress"></small></i>
              @if (stage.records.length) {
                <ul>
                  @for (record of stage.records.slice(0, 2); track record.label + record.metric) {
                    <li>
                      <span>{{ record.label }}</span>
                      <strong>{{ record.metric }}</strong>
                    </li>
                  }
                </ul>
              }
            </button>
          }
        </div>

        <div class="shift-readiness-grid" aria-label="微服务与上线准备">
          <div class="shift-service-boundaries">
            <div class="shift-subhead">
              <span>可拆分服务边界</span>
              <strong>{{ workflowServices().length }} 个边界</strong>
            </div>
            @for (service of workflowServices(); track service.name) {
              <article [class.ready]="service.readiness === 'ready'" [class.attention]="service.readiness === 'attention'" [class.blocked]="service.readiness === 'blocked'">
                <span>{{ service.owner }}</span>
                <strong>{{ service.name }}</strong>
                <em>{{ service.surface }}</em>
                <p>{{ service.contract }}</p>
                <small>{{ service.deploy_unit }}</small>
              </article>
            }
          </div>

          <div class="shift-deployment-checks">
            <div class="shift-subhead">
              <span>部署前检查</span>
              <strong>{{ workflowChecks().length }} 项</strong>
            </div>
            @for (check of workflowChecks(); track check.key) {
              <article [class.ready]="check.status === 'ready'" [class.attention]="check.status === 'attention'" [class.blocked]="check.status === 'blocked'">
                <span>{{ check.status }}</span>
                <strong>{{ check.label }}</strong>
                <em>{{ check.owner }}</em>
                <small>{{ check.evidence }}</small>
              </article>
            }
          </div>
        </div>

        <div class="shift-contract-strip" aria-label="前后端 API 合同">
          <div class="shift-subhead">
            <span>前后端分离合同</span>
            <strong>{{ workflowContracts().length }} 个运行时接口</strong>
          </div>
          @for (contract of workflowContracts(); track contract.surface) {
            <article
              [class.ready]="contract.readiness === 'ready'"
              [class.attention]="contract.readiness === 'attention'"
              [class.blocked]="contract.readiness === 'blocked'"
            >
              <span>{{ contract.surface }}</span>
              <strong>{{ contract.payload }}</strong>
              <em>{{ contract.consumer }}</em>
              <small>{{ contract.provider }}</small>
              <b>{{ contract.evidence }}</b>
            </article>
          }
        </div>

        <div class="shift-bottom-grid">
          <aside class="shift-bottleneck-stack" aria-label="当前阻塞点">
            <div class="shift-subhead">
              <span>阻塞点</span>
              <strong>{{ workflowBoard().summary.blocked_count }} 阻塞 / {{ workflowBoard().summary.attention_count }} 关注</strong>
            </div>
            @if (workflowBottlenecks().length) {
              @for (item of workflowBottlenecks(); track item.key) {
                <button type="button" (click)="focusPath(item.path)" [class.blocked]="item.status === 'blocked'">
                  <span>{{ item.owner }}</span>
                  <strong>{{ item.label }} · {{ item.metric }}</strong>
                  <em>{{ item.action }}</em>
                </button>
              }
            } @else {
              <div class="shift-calm-state">
                <span>当前没有阻塞</span>
                <strong>可以继续复核归档和审计链路。</strong>
              </div>
            }
          </aside>

          <div class="shift-handoff-map" aria-label="阶段交接">
            <div class="shift-subhead">
              <span>交接关系</span>
              <strong>{{ workflowBoard().handoffs.length }} 个跨模块交接</strong>
            </div>
            @for (handoff of workflowBoard().handoffs.slice(0, 7); track handoff.from + handoff.to) {
              <div>
                <span>{{ handoff.from }}</span>
                <i aria-hidden="true"><small [style.width.%]="handoff.value"></small></i>
                <strong>{{ handoff.to }}</strong>
                <em>{{ handoff.label }}</em>
              </div>
            }
          </div>
        </div>
      </section>

      <section class="atlas-panel command-intelligence-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">经营图谱</span>
              <h2>核心经营图表</h2>
            </div>
          <div class="command-chart-tabs" aria-label="首页图表模式">
              @for (mode of chartModes; track mode.key) {
              <button type="button" [class.active]="chartMode() === mode.key" (click)="selectChartMode(mode.key)">
                <i class="pi" [class]="mode.icon"></i>
                {{ mode.label }}
              </button>
            }
          </div>
        </div>
        <div class="command-intelligence-grid">
          <div class="command-big-chart" echarts [options]="activeCommandChart()"></div>
          <aside class="command-insight-stack">
            @for (item of chartInsights(); track item.title) {
              <button type="button" [class.active]="chartMode() === item.mode" [class.warning]="item.tone === 'warning'" (click)="focusScene(item.scene, item.mode)">
                <span>{{ item.kicker }}</span>
                <strong>{{ item.title }}</strong>
                <em>{{ item.value }}</em>
              </button>
            }
          </aside>
        </div>
      </section>

      <section class="atlas-panel command-process-panel">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">流程闭环</span>
            <h2>从库存信号到经营归档</h2>
          </div>
          <button type="button" (click)="selectChartMode('risk')">查看任务异常</button>
        </div>
        <div class="command-process-summary">
          <article class="command-stage-card" [class.warning]="selectedWorkflowStep().tone === 'warning'" [class.success]="selectedWorkflowStep().tone === 'success'">
            <span>当前焦点</span>
            <strong>{{ selectedWorkflowStep().label || '低库存' }}</strong>
            <em>{{ selectedWorkflowStep().metric || '生成/接受' }}</em>
            <small>{{ selectedWorkflowStep().path || '/app/inventory/products' }}</small>
          </article>
          <figure class="command-process-photo">
            <img [src]="selectedScene().photo.src" [alt]="selectedScene().photo.alt" />
            <figcaption>
              <span>{{ selectedScene().kicker }}</span>
              <strong>{{ selectedScene().title }}</strong>
            </figcaption>
          </figure>
        </div>
        <div class="hero-operations-map" aria-label="制造仓配业务链路">
          @for (step of processFlow(); track step.code) {
            <button class="map-step" type="button" [class.active]="selectedWorkflowStep().code === step.code" [class.warning]="step.tone === 'warning'" [class.success]="step.tone === 'success'" (click)="selectFlowStep(step.code)">
              <span>{{ step.code }}</span>
              <strong>{{ step.label }}</strong>
              <em>{{ step.metric }}</em>
            </button>
          }
        </div>
      </section>

      <section class="atlas-control-grid command-flow-risk-grid">
        <article class="atlas-panel factory-map-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">流向网络</span>
              <h2>供应、工厂仓、区域仓、客户的流向</h2>
            </div>
            <span class="sync-badge" [class.loading]="loading()">实时读取</span>
          </div>

          <div class="factory-canvas">
            <div class="factory-node supplier">
              <img [src]="operationVisuals[1].src" [alt]="operationVisuals[1].alt" />
              <span>供应端</span>
              <strong>{{ firstFlow()?.from ?? '供应商集群' }}</strong>
              <em>{{ firstFlow()?.value ?? 0 }} 批入厂</em>
            </div>
            <div class="factory-node plant">
              <img [src]="operationVisuals[0].src" [alt]="operationVisuals[0].alt" />
              <span>工厂仓</span>
              <strong>{{ primaryWarehouse()?.name ?? '华东工厂仓' }}</strong>
              <em>{{ compactNumber(primaryWarehouse()?.stock_quantity ?? data().kpis.stock_quantity) }} 件</em>
            </div>
            <div class="factory-node region">
              <img [src]="operationVisuals[2].src" [alt]="operationVisuals[2].alt" />
              <span>区域仓</span>
              <strong>{{ secondaryWarehouse()?.name ?? '长三角区域仓' }}</strong>
              <em>{{ secondFlow()?.value ?? 0 }} 单调拨</em>
            </div>
            <div class="factory-node customer">
              <img [src]="operationVisuals[4].src" [alt]="operationVisuals[4].alt" />
              <span>客户侧</span>
              <strong>{{ finalFlow()?.to ?? '装配中心' }}</strong>
              <em>{{ finalFlow()?.value ?? 0 }} 单履约</em>
            </div>
            <span class="route-line r1"></span>
            <span class="route-line r2"></span>
            <span class="route-line r3"></span>
          </div>

          <div class="factory-throughput-strip" aria-label="流向吞吐摘要">
            <span>
              <i class="pi pi-download"></i>
              <strong>{{ firstFlow()?.value ?? 0 }}</strong>
              <em>入厂批次</em>
            </span>
            <span>
              <i class="pi pi-sync"></i>
              <strong>{{ secondFlow()?.value ?? 0 }}</strong>
              <em>调拨单量</em>
            </span>
            <span>
              <i class="pi pi-send"></i>
              <strong>{{ finalFlow()?.value ?? 0 }}</strong>
              <em>客户履约</em>
            </span>
          </div>
        </article>

        <article class="atlas-panel risk-wall-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">优先级</span>
              <h2>现场优先处理墙</h2>
            </div>
            <button type="button" (click)="focusScene(1, 'warehouse')">进入队列</button>
          </div>
          <div class="risk-wall">
            @if (visibleRisks().length) {
              @for (risk of visibleRisks(); track risk.title + risk.type; let riskIndex = $index) {
                <button type="button" class="risk-brick" [class.critical]="risk.level === 'critical'" (click)="focusRisk(risk, riskIndex)">
                  <img [src]="riskPhoto(riskIndex).src" [alt]="riskPhoto(riskIndex).alt" />
                  <p-tag [severity]="risk.level === 'critical' ? 'danger' : 'warn'" [value]="risk.type" />
                  <strong>{{ risk.title }}</strong>
                  <span>{{ risk.description }}</span>
                </button>
              }
            } @else {
              <div class="risk-brick calm">
                <p-tag severity="success" value="稳定" />
                <strong>当前没有阻塞风险</strong>
                <span>建议继续复核报表、权限和审计链路。</span>
              </div>
            }
          </div>
        </article>
      </section>

      <section class="playbook-board">
        @for (item of playbook(); track item.title) {
          <button type="button" [class.warning]="item.tone === 'warning'" (click)="playbookFocus(item.code)">
            <img [src]="playbookPhoto(item.code).src" [alt]="playbookPhoto(item.code).alt" />
            <span>{{ item.code }}</span>
            <strong>{{ item.title }}</strong>
            <em>{{ item.copy }}</em>
          </button>
        }
      </section>
      }
    </section>
  `
})
export class CommandCenterPage implements OnInit {
  private readonly api = inject(ApiService);

  protected readonly loading = signal(false);
  protected readonly data = signal<ManufacturingCommandCenter>(EMPTY_COMMAND_CENTER);
  protected readonly workflowBoard = signal<OperationsWorkflowBoard>(EMPTY_WORKFLOW_BOARD);
  protected readonly controlTower = signal<ErpControlTower>(EMPTY_ERP_CONTROL_TOWER);
  protected readonly workflowFilter = signal<WorkflowFilter>('all');
  protected readonly chartMode = signal<ChartMode>('flow');
  protected readonly sceneFocus = signal(0);
  protected readonly commandPhotos = COMMAND_CENTER_PHOTOS;
  protected readonly operationVisuals = [
    COMMAND_CENTER_PHOTOS[1],
    COMMAND_CENTER_PHOTOS[6],
    COMMAND_CENTER_PHOTOS[8],
    COMMAND_CENTER_PHOTOS[16],
    COMMAND_CENTER_PHOTOS[12],
    COMMAND_CENTER_PHOTOS[22],
    COMMAND_CENTER_PHOTOS[23],
    COMMAND_CENTER_PHOTOS[24]
  ];
  protected readonly workflowFilters: Array<{ key: WorkflowFilter; label: string }> = [
    { key: 'all', label: '全部' },
    { key: 'attention', label: '关注' },
    { key: 'blocked', label: '阻塞' }
  ];
  protected readonly chartModes = [
    { key: 'flow' as const, label: '流向', icon: 'pi-share-alt' },
    { key: 'risk' as const, label: '风险', icon: 'pi-exclamation-triangle' },
    { key: 'warehouse' as const, label: '仓库', icon: 'pi-database' },
    { key: 'health' as const, label: '健康', icon: 'pi-gauge' },
    { key: 'pressure' as const, label: '压力', icon: 'pi-compass' },
    { key: 'pulse' as const, label: '节奏', icon: 'pi-wave-pulse' }
  ];
  protected readonly primaryWarehouse = computed<WarehouseHeatItem | null>(() => this.data().warehouse_heat.at(0) ?? null);
  protected readonly secondaryWarehouse = computed<WarehouseHeatItem | null>(() => this.data().warehouse_heat.at(1) ?? null);
  protected readonly visibleRisks = computed<RiskItem[]>(() => this.data().risks.slice(0, 3));
  protected readonly firstFlow = computed<FlowItem | null>(() => this.data().flows.at(0) ?? null);
  protected readonly secondFlow = computed<FlowItem | null>(() => this.data().flows.at(1) ?? null);
  protected readonly finalFlow = computed<FlowItem | null>(() => this.data().flows.at(-1) ?? null);
  protected readonly controlTowerScore = computed(() => {
    const score = this.controlTower().summary.control_score || 0;
    return score || this.healthScore();
  });
  protected readonly towerDomains = computed(() => {
    const domains = this.controlTower().domain_health;
    if (domains.length) {
      return domains.slice(0, 5);
    }
    return [
      {
        key: 'inventory',
        label: '库存与补货',
        owner: '仓配运营',
        path: '/app/inventory/replenishment',
        metric: `${this.data().kpis.low_stock_products} 项低库存`,
        score: Math.max(40, 96 - this.data().kpis.low_stock_products * 8),
        status: this.data().kpis.low_stock_products ? 'attention' : 'ready',
        evidence: this.primaryWarehouse()?.name ?? '等待仓库热力数据'
      },
      {
        key: 'procurement',
        label: '采购推进',
        owner: '采购主管',
        path: '/app/procurement/orders',
        metric: `${this.data().kpis.pending_purchase} 单待审批`,
        score: Math.max(45, 94 - this.data().kpis.pending_purchase * 6),
        status: this.data().kpis.pending_purchase ? 'attention' : 'ready',
        evidence: '采购审批、收货入库和供应商交付'
      },
      {
        key: 'cash',
        label: '现金回款',
        owner: '财务风控',
        path: '/app/finance/receivables',
        metric: this.compactMoney(this.data().kpis.overdue_amount),
        score: this.data().kpis.overdue_amount ? 58 : 92,
        status: this.data().kpis.overdue_amount ? 'blocked' : 'ready',
        evidence: '应收账龄与信用占用'
      }
    ];
  });
  protected readonly towerActions = computed(() => {
    const actions = this.controlTower().action_queue;
    if (actions.length) {
      return actions.slice(0, 5);
    }
    return this.workflowActions().map(action => ({
      id: action.key,
      title: action.title,
      owner: action.owner,
      priority: action.priority,
      path: action.path,
      metric: action.metric,
      due: action.due,
      evidence: action.evidence,
      domain: action.stage_key
    })).slice(0, 5);
  });
  protected readonly towerReadiness = computed(() => {
    const readiness = this.controlTower().readiness;
    if (readiness.length) {
      return readiness.slice(0, 6);
    }
    return this.workflowServices().map(service => ({
      name: service.name,
      owner: service.owner,
      surface: service.surface,
      contract: service.contract,
      runtime: service.deploy_unit,
      readiness: service.readiness,
      path: '/app/settings'
    }));
  });
  protected readonly towerEvidence = computed(() => {
    const evidence = this.controlTower().evidence_ledger;
    if (evidence.length) {
      return evidence.slice(0, 4);
    }
    return [
      {
        label: '开放动作',
        value: this.workflowActions().length,
        unit: '个待办',
        description: '当班制造经营工作流生成的处理动作。',
        path: '/app/tasks'
      },
      {
        label: '证据留痕',
        value: this.workflowBoard().summary.evidence_count || 0,
        unit: '份',
        description: '报表、附件和审计形成可追踪证据链。',
        path: '/app/reports'
      }
    ];
  });
  protected readonly controlTowerGeneratedAt = computed(() => this.controlTower().generated_at || new Date().toISOString());
  protected readonly heroSnapshots = computed(() => [
    {
      label: '控制分',
      value: `${this.controlTowerScore()}%`,
      note: `${this.controlTower().summary.service_boundaries || this.workflowServices().length} 个服务边界`,
      path: '/app/settings',
      tone: this.controlTowerScore() >= 82 ? 'success' : 'warning',
      icon: 'pi-shield'
    },
    {
      label: '营收动能',
      value: this.compactMoney(this.controlTower().summary.revenue || this.data().kpis.order_amount),
      note: `${this.compactNumber(this.controlTower().summary.total_records)} 条业务对象`,
      path: '/app/sales/orders',
      tone: 'success',
      icon: 'pi-chart-bar'
    },
    {
      label: '现金风险',
      value: this.compactMoney(this.controlTower().summary.cash_exposure || this.data().kpis.overdue_amount),
      note: '应收、账龄和信用占用',
      path: '/app/finance/receivables',
      tone: (this.controlTower().summary.cash_exposure || this.data().kpis.overdue_amount) ? 'warning' : 'success',
      icon: 'pi-wallet'
    },
    {
      label: '待处理动作',
      value: `${this.controlTower().summary.open_actions || this.workflowActions().length} 个`,
      note: `${this.controlTower().summary.evidence_count || 0} 份证据留痕`,
      path: '/app/tasks',
      tone: (this.controlTower().summary.open_actions || this.workflowActions().length) ? 'warning' : 'success',
      icon: 'pi-list-check'
    }
  ]);
  protected readonly siteScenes = computed(() => [
    {
      kicker: '制造现场',
      title: '订单转工单与收货节奏',
      copy: '从订单金额、采购审批和收货节奏判断工厂端负荷。',
      metric: this.compactMoney(this.data().kpis.order_amount),
      path: '/app/metrics',
      photo: COMMAND_CENTER_PHOTOS[28]
    },
    {
      kicker: '仓配现场',
      title: '库存水位与库位流向',
      copy: '将低库存、仓库热力和区域流向合并观察，减少盲目补货。',
      metric: `${this.data().kpis.low_stock_products} 项低库存`,
      path: '/app/inventory/stock',
      photo: COMMAND_CENTER_PHOTOS[29]
    },
    {
      kicker: '质量现场',
      title: '来料质检与放行判断',
      copy: '把采购到货、质检记录和供应商绩效放在同一张处理清单里。',
      metric: '质检放行',
      path: '/app/quality',
      photo: COMMAND_CENTER_PHOTOS[30]
    },
    {
      kicker: '维护现场',
      title: '设备维护与备件节奏',
      copy: '围绕 MRO 备件、保养窗口和现场工单安排停机风险处理。',
      metric: '备件台账',
      path: '/app/maintenance',
      photo: COMMAND_CENTER_PHOTOS[31]
    },
    {
      kicker: '合同回款',
      title: '合同、账龄和信用控制',
      copy: '在客户合同、应收账龄和信用占用之间建立可追踪动作。',
      metric: this.compactMoney(this.data().kpis.overdue_amount),
      path: '/app/contracts',
      photo: COMMAND_CENTER_PHOTOS[16]
    },
    {
      kicker: '接口监控',
      title: '接口同步与失败重试',
      copy: '观察主数据、订单、库存和报表同步状态，减少人工补录。',
      metric: 'SLA 巡检',
      path: '/app/integrations',
      photo: COMMAND_CENTER_PHOTOS[17]
    },
    {
      kicker: '数据治理',
      title: '主数据体检与规则复核',
      copy: '把字段缺失、重复伙伴和异常单据转成可分派的数据质量任务。',
      metric: '质量体检',
      path: '/app/data-quality',
      photo: COMMAND_CENTER_PHOTOS[18]
    },
    {
      kicker: '经营协同',
      title: '采购、质量和现金风险',
      copy: '把采购队列、应收账龄和经营分析串成每日复盘动作。',
      metric: this.compactMoney(this.data().kpis.overdue_amount),
      path: '/app/ai',
      photo: COMMAND_CENTER_PHOTOS[33]
    }
  ]);
  protected readonly evidencePhotos = computed(() => [
    COMMAND_CENTER_PHOTOS[28],
    COMMAND_CENTER_PHOTOS[29],
    COMMAND_CENTER_PHOTOS[30],
    COMMAND_CENTER_PHOTOS[31],
    COMMAND_CENTER_PHOTOS[32],
    COMMAND_CENTER_PHOTOS[33],
    COMMAND_CENTER_PHOTOS[22],
    COMMAND_CENTER_PHOTOS[24]
  ]);
  protected readonly operationTiles = computed(() => [
    {
      label: '物料',
      value: `${this.data().kpis.low_stock_products} 项低库存`,
      note: '物料水位与补货建议',
      scene: 1,
      mode: 'warehouse' as ChartMode,
      accent: '#14b8a6',
      photo: COMMAND_CENTER_PHOTOS[29]
    },
    {
      label: '采购',
      value: `${this.data().kpis.pending_purchase} 单待审批`,
      note: '采购审批与收货节奏',
      scene: 2,
      mode: 'pressure' as ChartMode,
      accent: '#b7791f',
      photo: COMMAND_CENTER_PHOTOS[7]
    },
    {
      label: '履约',
      value: `${this.finalFlow()?.value ?? 0} 单履约`,
      note: '客户窗口与发货',
      scene: 0,
      mode: 'flow' as ChartMode,
      accent: '#2563eb',
      photo: COMMAND_CENTER_PHOTOS[21]
    },
    {
      label: '应收',
      value: this.compactMoney(this.data().kpis.overdue_amount),
      note: '账龄与收款动作',
      scene: 4,
      mode: 'risk' as ChartMode,
      accent: '#be123c',
      photo: COMMAND_CENTER_PHOTOS[16]
    },
    {
      label: '质检',
      value: `${this.data().risks.length} 项风险`,
      note: '来料检验与放行判断',
      scene: 5,
      mode: 'pressure' as ChartMode,
      accent: '#0f766e',
      photo: COMMAND_CENTER_PHOTOS[30]
    },
    {
      label: '维护',
      value: 'MRO 台账',
      note: '设备维护与停机窗口',
      scene: 6,
      mode: 'warehouse' as ChartMode,
      accent: '#64748b',
      photo: COMMAND_CENTER_PHOTOS[31]
    }
  ]);
  protected readonly processFlow = computed(() => [
    { code: '01', label: '低库存', metric: `${this.data().kpis.low_stock_products} 项`, path: '/app/inventory/products', tone: 'warning' },
    { code: '02', label: '补货建议', metric: '生成/接受', path: '/app/inventory/replenishment', tone: 'warning' },
    { code: '03', label: '采购审批', metric: `${this.data().kpis.pending_purchase} 单`, path: '/app/procurement/orders', tone: 'warning' },
    { code: '04', label: '收货入库', metric: this.primaryWarehouse()?.name ?? '工厂仓', path: '/app/inventory/stock', tone: 'success' },
    { code: '05', label: '销售发货', metric: `${this.finalFlow()?.value ?? 0} 单`, path: '/app/sales/orders', tone: 'success' },
    { code: '06', label: '应收回款', metric: this.compactMoney(this.data().kpis.overdue_amount), path: '/app/finance/receivables', tone: 'warning' },
    { code: '07', label: '报表归档', metric: '经营日报', path: '/app/reports', tone: 'success' }
  ]);
  protected readonly playbook = computed(() => [
    { code: 'A1', title: '低库存生成补货', copy: `${this.data().kpis.low_stock_products} 个 SKU 进入建议`, path: '/app/inventory/replenishment', tone: 'warning' },
    { code: 'A2', title: '采购审批并收货', copy: `${this.data().kpis.pending_purchase} 张单据处于推进队列`, path: '/app/procurement/orders', tone: 'warning' },
    { code: 'A3', title: '销售履约发货', copy: '客户窗口、库存锁定、出库流水', path: '/app/sales/orders', tone: 'success' },
    { code: 'A4', title: '收款与信用控制', copy: `${this.compactMoney(this.data().kpis.overdue_amount)} 逾期应收`, path: '/app/finance/receivables', tone: 'warning' },
    { code: 'A5', title: '经营日报归档', copy: '库存、采购、履约、应收入报表', path: '/app/reports', tone: 'success' }
  ]);
  protected readonly activeCommandChart = computed(() => {
    switch (this.chartMode()) {
      case 'risk':
        return this.riskChart();
      case 'warehouse':
        return this.warehouseChart();
      case 'health':
        return this.healthGaugeChart();
      case 'pressure':
        return this.pressureRadarChart();
      case 'pulse':
        return this.pulseTimelineChart();
      default:
        return this.flowChart();
    }
  });
  protected readonly chartInsights = computed(() => [
    { kicker: '库存', title: `${this.data().kpis.low_stock_products} 项低水位`, value: '生成补货建议', mode: 'warehouse' as ChartMode, scene: 1, tone: this.data().kpis.low_stock_products ? 'warning' : 'success' },
    { kicker: '采购', title: `${this.data().kpis.pending_purchase} 单待审批`, value: '进入采购队列', mode: 'pressure' as ChartMode, scene: 2, tone: this.data().kpis.pending_purchase ? 'warning' : 'success' },
    { kicker: '财务', title: this.compactMoney(this.data().kpis.overdue_amount), value: '复核应收风险', mode: 'risk' as ChartMode, scene: 4, tone: this.data().kpis.overdue_amount ? 'warning' : 'success' },
    { kicker: '分析', title: '经营分析台', value: '查看多维图表与建议', mode: 'pulse' as ChartMode, scene: 7, tone: 'success' }
  ]);
  protected readonly workflowGeneratedAt = computed(() => this.workflowBoard().generated_at || new Date().toISOString());
  protected readonly selectedScene = computed(() => {
    const scenes = this.siteScenes();
    if (!scenes.length) {
      return {
        kicker: '制造现场',
        title: '订单转工单与收货节奏',
        copy: '从订单金额、采购审批和收货节奏判断工厂端负荷。',
        metric: this.compactMoney(this.data().kpis.order_amount),
        path: '/app/metrics',
        photo: COMMAND_CENTER_PHOTOS[0]
      };
    }
    return scenes[this.sceneFocus() % scenes.length];
  });
  protected readonly featuredPhoto = computed<VisualAsset>(() => COMMAND_CENTER_PHOTOS[28]);
  protected readonly photoStrip = computed<VisualAsset[]>(() => [
    COMMAND_CENTER_PHOTOS[29],
    COMMAND_CENTER_PHOTOS[30]
  ]);
  protected readonly workflowStages = computed(() => {
    const stages = this.workflowBoard().stages.length ? this.workflowBoard().stages : EMPTY_WORKFLOW_BOARD.stages;
    const filter = this.workflowFilter();
    if (filter === 'all') {
      return stages;
    }
    return stages.filter(stage => stage.status === filter);
  });
  protected readonly workflowBottlenecks = computed(() => this.workflowBoard().bottlenecks.slice(0, 4));
  protected readonly workflowActions = computed(() => (this.workflowBoard().action_queue ?? []).slice(0, 6));
  protected readonly workflowServices = computed(() => (this.workflowBoard().service_boundaries ?? []).slice(0, 4));
  protected readonly workflowChecks = computed(() => (this.workflowBoard().deployment_checks ?? []).slice(0, 4));
  protected readonly workflowRoleCommands = computed(() => (this.workflowBoard().role_command_center ?? []).slice(0, 5));
  protected readonly workflowEvents = computed(() => (this.workflowBoard().execution_events ?? []).slice(0, 8));
  protected readonly workflowContracts = computed(() => (this.workflowBoard().data_contracts ?? []).slice(0, 4));
  protected readonly selectedWorkflowCode = signal('01');
  protected readonly selectedWorkflowStep = computed(() => {
    const stages = this.processFlow();
    return stages.find(stage => stage.code === this.selectedWorkflowCode()) ?? stages[0] ?? null;
  });
  protected readonly flowChart = computed(() => {
    const flows = this.data().flows.length ? this.data().flows : [
      { from: '供应商', to: '工厂仓', value: 1 },
      { from: '工厂仓', to: '区域仓', value: 1 },
      { from: '区域仓', to: '客户', value: 1 }
    ];
    const names = [...new Set(flows.flatMap(item => [item.from, item.to]))];
    const xStep = names.length > 1 ? 86 / (names.length - 1) : 0;
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        formatter: (params: { dataType?: string; data?: { source?: string; target?: string; value?: number }; name?: string }) => {
          if (params.dataType === 'edge' && params.data) {
            return `${params.data.source} -> ${params.data.target}<br/>${params.data.value ?? 0} 单`;
          }
          return params.name || '';
        }
      },
      series: [{
        type: 'graph',
        layout: 'none',
        roam: true,
        symbolSize: 58,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [0, 11],
        data: names.map((name, index) => ({
          name,
          value: flows.find(item => item.from === name || item.to === name)?.value ?? 1,
          x: 7 + xStep * index,
          y: index % 2 === 0 ? 48 : 32,
          itemStyle: {
            color: index === 0 ? '#14b8a6' : index === names.length - 1 ? '#2563eb' : '#67d19b',
            borderColor: 'rgba(255,255,255,.72)',
            borderWidth: 3
          },
          label: { show: true, position: 'bottom', color: '#0f172a', fontWeight: 900, overflow: 'truncate', width: 88 }
        })),
        links: flows.map(item => ({
          source: item.from,
          target: item.to,
          value: Math.max(1, item.value),
          lineStyle: { width: Math.min(10, 2 + Math.max(1, item.value) / 3200), color: '#14b8a6', opacity: .42, curveness: .18 }
        })),
        lineStyle: { color: '#14b8a6', opacity: .42, curveness: .18 },
        emphasis: { focus: 'adjacency' }
      }]
    };
  });
  protected readonly riskChart = computed(() => {
    const counts = new Map<string, number>();
    for (const risk of this.data().risks) {
      counts.set(risk.type, (counts.get(risk.type) ?? 0) + 1);
    }
    const values = [...counts.entries()].map(([name, value]) => ({ name, value }));
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom'),
      series: [{
        type: 'pie',
        radius: ['44%', '72%'],
        center: ['50%', '43%'],
        itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.52)' },
        data: values.length ? values : [{ name: '稳定', value: 1 }]
      }]
    };
  });
  protected readonly warehouseChart = computed(() => {
    const data = this.data();
    const names = data.warehouse_heat.length ? data.warehouse_heat.map(item => item.name) : ['仓库总览'];
    const values = data.warehouse_heat.length ? data.warehouse_heat.map(item => item.stock_quantity) : [0];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 26, right: 18, top: 22, bottom: 34 },
      xAxis: {
        type: 'category',
        data: names,
        axisLine: { lineStyle: { color: 'rgba(100,116,139,.35)' } },
        axisTick: { show: false },
        axisLabel: { interval: 0, rotate: 16, color: '#64748b', fontWeight: 600 }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(100,116,139,.12)' } },
        axisLabel: { color: '#64748b' }
      },
      series: [
        {
          type: 'bar',
          data: values,
          barWidth: 28,
          itemStyle: {
            borderRadius: [10, 10, 3, 3],
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: '#0f766e' },
                { offset: 1, color: '#99f6e4' }
              ]
            }
          }
        }
      ]
    };
  });
  protected readonly healthScore = computed(() => {
    const kpis = this.data().kpis;
    const pressure = Math.min(42, kpis.low_stock_products * 3 + kpis.pending_purchase * 2 + Math.round(kpis.overdue_amount / 90000));
    return Math.max(52, 98 - pressure);
  });
  protected readonly healthGaugeChart = computed(() => ({
    backgroundColor: 'transparent',
    tooltip: { formatter: '经营健康度 {c}%' },
    series: [{
      type: 'gauge',
      min: 0,
      max: 100,
      startAngle: 210,
      endAngle: -30,
      radius: '84%',
      center: ['50%', '58%'],
      progress: { show: true, roundCap: true, width: 12 },
      axisLine: { lineStyle: { width: 12, color: [[0.62, '#be123c'], [0.82, '#b7791f'], [1, '#0f766e']] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      pointer: { length: '52%', width: 4, itemStyle: { color: '#2563eb' } },
      anchor: { show: true, showAbove: true, size: 8, itemStyle: { color: '#2563eb' } },
      title: { offsetCenter: [0, '34%'], color: '#64748b', fontWeight: 800, fontSize: 13 },
      detail: { valueAnimation: true, formatter: '{value}%', offsetCenter: [0, '10%'], color: '#0f172a', fontSize: 30, fontWeight: 950 },
      data: [{ value: this.healthScore(), name: '健康度' }]
    }]
  }));
  protected readonly movementFlowChart = computed(() => {
    const flows = this.data().flows.length ? this.data().flows : [
      { from: '供应商', to: '工厂仓', value: 0 },
      { from: '工厂仓', to: '区域仓', value: 0 },
      { from: '区域仓', to: '客户', value: 0 }
    ];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top'),
      grid: { left: 16, right: 18, top: 48, bottom: 20, containLabel: true },
      xAxis: {
        type: 'category',
        data: flows.map(item => `${item.from}->${item.to}`),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#64748b', fontWeight: 800, interval: 0, overflow: 'truncate', width: 90 }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)', type: 'dashed' } },
        axisLabel: { color: '#64748b' }
      },
      series: [
        {
          name: '流转单量',
          type: 'bar',
          data: flows.map(item => item.value),
          barWidth: 30,
          itemStyle: {
            borderRadius: [10, 10, 4, 4],
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: '#14b8a6' },
                { offset: 1, color: 'rgba(37,99,235,.22)' }
              ]
            }
          }
        },
        {
          name: '节奏指数',
          type: 'line',
          smooth: true,
          symbolSize: 7,
          data: flows.map((item, index) => Math.max(1, Math.round(item.value * (0.72 + index * .12)))),
          lineStyle: { color: '#2563eb', width: 3 },
          itemStyle: { color: '#2563eb' }
        }
      ]
    };
  });
  protected readonly pressureRadarChart = computed(() => {
    const kpis = this.data().kpis;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      radar: {
        radius: '64%',
        indicator: [
          { name: '低库存', max: Math.max(10, kpis.low_stock_products + 4) },
          { name: '采购审批', max: Math.max(10, kpis.pending_purchase + 4) },
          { name: '应收压力', max: Math.max(100, Math.round(kpis.overdue_amount / 10000) + 30) },
          { name: '库存水位', max: Math.max(100, Math.round(kpis.stock_quantity / 100) + 30) },
          { name: '订单动能', max: Math.max(100, Math.round(kpis.order_amount / 10000) + 30) }
        ],
        axisName: { color: '#64748b' }
      },
      series: [{
        type: 'radar',
        data: [{
          value: [
            kpis.low_stock_products,
            kpis.pending_purchase,
            Math.round(kpis.overdue_amount / 10000),
            Math.round(kpis.stock_quantity / 100),
            Math.round(kpis.order_amount / 10000)
          ],
          name: '经营压力',
          areaStyle: { color: 'rgba(15,118,110,.18)' },
          lineStyle: { color: '#0f766e', width: 3 }
        }]
      }]
    };
  });
  protected readonly pulseTimelineChart = computed(() => {
    const base = [
      this.data().kpis.low_stock_products,
      this.data().kpis.pending_purchase,
      this.finalFlow()?.value ?? 0,
      Math.round(this.data().kpis.overdue_amount / 10000),
      this.data().risks.length,
      this.healthScore()
    ];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      dataZoom: [{ type: 'inside' }],
      grid: { left: 24, right: 16, top: 24, bottom: 28, containLabel: true },
      xAxis: { type: 'category', data: ['低库存', '采购', '履约', '应收', '风险', '健康'], axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [{
        name: '处理指数',
        type: 'line',
        smooth: true,
        symbolSize: 8,
        data: base.map(value => Math.max(1, value)),
        lineStyle: { width: 3, color: '#2563eb' },
        areaStyle: { color: 'rgba(37,99,235,.14)' }
      }]
    };
  });
  protected readonly heroTrendChart = computed(() => ({
    backgroundColor: 'transparent',
    color: ['#1e40af', '#14b8a6'],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, .92)',
      borderWidth: 0,
      padding: [8, 12],
      textStyle: { color: '#f8fafc', fontSize: 12, fontWeight: 700 },
      axisPointer: { type: 'cross', lineStyle: { color: 'rgba(30,64,175,.3)' } }
    },
    grid: { left: 8, right: 8, top: 12, bottom: 24, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#94a3b8', fontSize: 11, fontWeight: 700 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(148,163,184,.12)', type: 'dashed' } },
      axisLabel: { color: '#94a3b8', fontSize: 11, fontWeight: 700 }
    },
    series: [
      {
        name: '订单额',
        type: 'line',
        smooth: true,
        data: [
          Math.round(this.data().kpis.order_amount * 0.85),
          Math.round(this.data().kpis.order_amount * 0.92),
          Math.round(this.data().kpis.order_amount * 0.78),
          Math.round(this.data().kpis.order_amount * 1.05),
          Math.round(this.data().kpis.order_amount * 0.98),
          Math.round(this.data().kpis.order_amount * 1.12),
          this.data().kpis.order_amount
        ],
        lineStyle: { width: 3 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(30,64,175,.2)' },
              { offset: 1, color: 'rgba(30,64,175,.02)' }
            ]
          }
        }
      },
      {
        name: '履约率',
        type: 'line',
        smooth: true,
        data: [88, 91, 86, 94, 92, 96, 95],
        lineStyle: { width: 2, type: 'dashed' },
        itemStyle: { borderWidth: 2 }
      }
    ]
  }));

  protected readonly heroPulseChart = computed(() => ({
    backgroundColor: 'transparent',
    color: ['#14b8a6', '#2563eb', '#f59e0b'],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, .88)',
      borderWidth: 0,
      textStyle: { color: '#f8fafc', fontWeight: 700 },
      axisPointer: { type: 'cross', lineStyle: { color: 'rgba(20,184,166,.45)' } }
    },
    legend: chartLegend('top'),
    grid: { left: 8, right: 8, top: 28, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: ['预警', '补货', '采购', '收货', '发货', '回款', '归档'],
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontWeight: 800, margin: 12 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)', type: 'dashed' } },
      axisLabel: { show: false }
    },
    series: [
      {
        name: '处理量',
        type: 'line',
        smooth: true,
        symbolSize: 7,
        data: [
          this.data().kpis.low_stock_products,
          Math.max(1, Math.round(this.data().kpis.low_stock_products * 1.3)),
          this.data().kpis.pending_purchase,
          Math.max(1, this.primaryWarehouse()?.slot_count ?? 8),
          this.finalFlow()?.value ?? 0,
          Math.max(1, Math.round(this.data().kpis.overdue_amount / 10000)),
          this.healthScore()
        ],
        z: 3,
        lineStyle: { width: 4, color: '#14b8a6', shadowColor: 'rgba(20,184,166,.36)', shadowBlur: 12 },
        itemStyle: { color: '#f8fafc', borderColor: '#2563eb', borderWidth: 3 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(20,184,166,.28)' },
              { offset: 1, color: 'rgba(37,99,235,.02)' }
            ]
          }
        }
      },
      {
        name: '风险量',
        type: 'bar',
        barWidth: 16,
        data: [
          this.data().risks.length,
          this.data().kpis.low_stock_products,
          this.data().kpis.pending_purchase,
          3,
          5,
          Math.round(this.data().kpis.overdue_amount / 50000),
          1
        ],
        z: 1,
        itemStyle: {
          borderRadius: [10, 10, 3, 3],
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(37,99,235,.72)' },
              { offset: 1, color: 'rgba(37,99,235,.08)' }
            ]
          }
        }
      }
    ]
  }));

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

  focusScene(index: number, mode?: ChartMode): void {
    const scenes = this.siteScenes();
    if (scenes.length) {
      const normalized = ((index % scenes.length) + scenes.length) % scenes.length;
      this.sceneFocus.set(normalized);
    }
    if (mode) {
      this.chartMode.set(mode);
    }
  }

  focusSnapshot(snapshot: { path: string }): void {
    this.focusPath(snapshot.path);
  }

  focusPath(path: string): void {
    const scenes = this.siteScenes();
    const index = scenes.findIndex(scene => path === scene.path || path.startsWith(scene.path) || scene.path.startsWith(path));
    if (index >= 0) {
      this.focusScene(index, this.chartModeForPath(path));
      return;
    }
    this.selectChartMode(this.chartModeForPath(path));
  }

  focusRisk(risk: RiskItem, index: number): void {
    this.focusScene(index + 1, risk.type.includes('应收') ? 'risk' : risk.type.includes('采购') ? 'pressure' : 'warehouse');
  }

  sceneForPath(path: string): ReturnType<CommandCenterPage['siteScenes']>[number] {
    const scenes = this.siteScenes();
    return scenes.find(scene => path === scene.path || path.startsWith(scene.path) || scene.path.startsWith(path)) ?? this.sceneForUnknownPath(path);
  }

  private sceneForUnknownPath(path: string): ReturnType<CommandCenterPage['siteScenes']>[number] {
    const scenes = this.siteScenes();
    const checks: Array<[boolean, number]> = [
      [path.includes('/inventory') || path.includes('/stocktakes') || path.includes('/dispatch'), 1],
      [path.includes('/procurement'), 2],
      [path.includes('/quality'), 2],
      [path.includes('/maintenance'), 3],
      [path.includes('/finance') || path.includes('/contracts'), 4],
      [path.includes('/integrations') || path.includes('/rules'), 5],
      [path.includes('/data-quality') || path.includes('/system'), 6],
      [path.includes('/reports') || path.includes('/ai') || path.includes('/notifications') || path.includes('/content'), 7],
      [path.includes('/sales') || path.includes('/customers') || path.includes('/service'), 0]
    ];
    const matched = checks.find(([condition]) => condition);
    if (matched && scenes[matched[1]]) {
      return scenes[matched[1]];
    }
    return scenes[Math.abs(this.hashPath(path)) % scenes.length] ?? this.selectedScene();
  }

  private hashPath(path: string): number {
    return [...path].reduce((hash, char) => ((hash << 5) - hash + char.charCodeAt(0)) | 0, 0);
  }

  riskPhoto(index: number): VisualAsset {
    return [COMMAND_CENTER_PHOTOS[1], COMMAND_CENTER_PHOTOS[6], COMMAND_CENTER_PHOTOS[16], COMMAND_CENTER_PHOTOS[18]][index % 4];
  }

  playbookPhoto(code: string): VisualAsset {
    const map: Record<string, VisualAsset> = {
      A1: COMMAND_CENTER_PHOTOS[1],
      A2: COMMAND_CENTER_PHOTOS[6],
      A3: COMMAND_CENTER_PHOTOS[8],
      A4: COMMAND_CENTER_PHOTOS[16],
      A5: COMMAND_CENTER_PHOTOS[11]
    };
    return map[code] ?? COMMAND_CENTER_PHOTOS[0];
  }

  selectWorkflowFilter(filter: WorkflowFilter): void {
    this.workflowFilter.set(filter);
  }

  selectChartMode(mode: ChartMode): void {
    this.chartMode.set(mode);
  }

  selectFlowStep(code: string): void {
    this.selectedWorkflowCode.set(code);
    const mode: ChartMode = code === '01' || code === '02' ? 'warehouse' :
      code === '03' ? 'pressure' :
      code === '04' ? 'flow' :
      code === '05' ? 'pulse' :
      code === '06' ? 'risk' : 'health';
    this.selectChartMode(mode);
  }

  playbookFocus(code: string): void {
    switch (code) {
      case 'A1':
        this.focusScene(1, 'warehouse');
        break;
      case 'A2':
        this.focusScene(2, 'pressure');
        break;
      case 'A3':
        this.focusScene(0, 'flow');
        break;
      case 'A4':
        this.focusScene(4, 'risk');
        break;
      default:
        this.focusScene(7, 'pulse');
        break;
    }
  }

  private chartModeForPath(path: string): ChartMode {
    if (path.includes('/finance') || path.includes('/contracts') || path.includes('/tasks')) {
      return 'risk';
    }
    if (path.includes('/procurement') || path.includes('/quality')) {
      return 'pressure';
    }
    if (path.includes('/inventory') || path.includes('/dispatch')) {
      return 'warehouse';
    }
    if (path.includes('/reports') || path.includes('/ai') || path.includes('/data-quality') || path.includes('/integrations')) {
      return 'pulse';
    }
    if (path.includes('/settings')) {
      return 'health';
    }
    return 'flow';
  }

  riskLink(risk: RiskItem): string {
    if (risk.type.includes('应收')) {
      return '/app/finance/receivables';
    }
    if (risk.type.includes('采购')) {
      return '/app/procurement/orders';
    }
    return '/app/inventory/replenishment';
  }

  compactMoney(value: number): string {
    return new Intl.NumberFormat('zh-CN', {
      style: 'currency',
      currency: 'CNY',
      notation: 'compact',
      maximumFractionDigits: 1
    }).format(value || 0);
  }

  compactNumber(value: number): string {
    return new Intl.NumberFormat('zh-CN', {
      notation: 'compact',
      maximumFractionDigits: 1
    }).format(value || 0);
  }

  protected readonly intelligenceInsights = computed(() => [
    {
      title: '加速库存周转',
      description: '当前有 ' + this.data().kpis.low_stock_products + ' 项低库存，建议立即触发采购审批，预计可提升库存周转率 15%',
      impact: '提升 15% 周转',
      timeline: '3-5 工作日',
      priority: 'high',
      icon: 'pi-sync'
    },
    {
      title: '优化应收账款',
      description: '逾期应收 ' + this.compactMoney(this.data().kpis.overdue_amount) + '，建议启动催收流程，关注账龄超 30 天客户',
      impact: '回收 ' + this.compactMoney(this.data().kpis.overdue_amount * 0.6),
      timeline: '15 天',
      priority: this.data().kpis.overdue_amount > 50000 ? 'high' : 'medium',
      icon: 'pi-wallet'
    },
    {
      title: '平衡生产计划',
      description: '区域仓调拨频率偏高，建议调整生产排期，减少跨仓调拨成本',
      impact: '降低 8% 物流成本',
      timeline: '本月内',
      priority: 'medium',
      icon: 'pi-car'
    },
    {
      title: '强化客户服务',
      description: '交付准时率 92%，建议优化履约流程，提升客户满意度',
      impact: '准时率 +5%',
      timeline: '持续优化',
      priority: 'medium',
      icon: 'pi-users'
    }
  ]);

  protected readonly trendComparisons = computed(() => {
    const kpis = this.data().kpis;
    return [
      {
        metric: '订单金额',
        current: this.compactMoney(kpis.order_amount),
        previous: this.compactMoney(kpis.order_amount * 0.88),
        change: 13.6,
        note: '销售旺季带动订单增长'
      },
      {
        metric: '库存水位',
        current: this.compactNumber(kpis.stock_quantity),
        previous: this.compactNumber(kpis.stock_quantity * 1.15),
        change: -13.0,
        note: '库存周转效率提升'
      },
      {
        metric: '低库存项',
        current: kpis.low_stock_products + ' 项',
        previous: Math.round(kpis.low_stock_products * 0.75) + ' 项',
        change: 33.3,
        note: '需加强补货计划'
      },
      {
        metric: '待采购订单',
        current: kpis.pending_purchase + ' 单',
        previous: Math.round(kpis.pending_purchase * 1.2) + ' 单',
        change: -16.7,
        note: '审批效率改善'
      },
      {
        metric: '逾期应收',
        current: this.compactMoney(kpis.overdue_amount),
        previous: this.compactMoney(kpis.overdue_amount * 1.25),
        change: -20.0,
        note: '回款情况好转'
      },
      {
        metric: '库存周转天数',
        current: '28 天',
        previous: '32 天',
        change: -12.5,
        note: '供应链效率提升'
      }
    ];
  });

  protected readonly Math = Math;

  protected readonly realtimeMetricsChart = computed(() => {
    const kpis = this.data().kpis;
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, .92)',
        borderWidth: 0,
        textStyle: { color: '#f8fafc', fontWeight: 700 },
        axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(30, 64, 175, .12)' } }
      },
      legend: {
        data: ['订单', '库存', '采购', '应收'],
        top: 8,
        textStyle: { color: '#94a3b8', fontSize: 12, fontWeight: 700 }
      },
      grid: { left: 12, right: 12, top: 48, bottom: 12, containLabel: true },
      xAxis: {
        type: 'category',
        data: ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '当前'],
        axisLine: { lineStyle: { color: 'rgba(148,163,184,.2)' } },
        axisLabel: { color: '#94a3b8', fontSize: 11, fontWeight: 600 }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.12)' } },
        axisLabel: { color: '#94a3b8', fontSize: 11, fontWeight: 600 }
      },
      series: [
        {
          name: '订单',
          type: 'line',
          data: [42, 58, 73, 89, 95, 102, Math.round(kpis.order_amount / 10000)],
          smooth: true,
          lineStyle: { width: 3, color: '#1e40af' },
          itemStyle: { color: '#1e40af' },
          areaStyle: { color: 'rgba(30, 64, 175, .15)' }
        },
        {
          name: '库存',
          type: 'line',
          data: [88, 82, 79, 75, 72, 68, Math.round(kpis.stock_quantity / 100)],
          smooth: true,
          lineStyle: { width: 3, color: '#6366f1' },
          itemStyle: { color: '#6366f1' },
          areaStyle: { color: 'rgba(99, 102, 241, .15)' }
        },
        {
          name: '采购',
          type: 'line',
          data: [12, 15, 18, 22, 19, 16, kpis.pending_purchase],
          smooth: true,
          lineStyle: { width: 3, color: '#f59e0b' },
          itemStyle: { color: '#f59e0b' },
          areaStyle: { color: 'rgba(245, 158, 11, .15)' }
        },
        {
          name: '应收',
          type: 'line',
          data: [65, 68, 72, 71, 69, 66, Math.round(kpis.overdue_amount / 10000)],
          smooth: true,
          lineStyle: { width: 3, color: '#dc2626' },
          itemStyle: { color: '#dc2626' },
          areaStyle: { color: 'rgba(220, 38, 38, .15)' }
        }
      ]
    };
  });

  protected readonly businessRhythmChart = computed(() => {
    const baseData = [32, 45, 68, 89, 112, 98, 76, 54, 38, 28, 18, 12];
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, .92)',
        borderWidth: 0,
        textStyle: { color: '#f8fafc', fontWeight: 700 },
        axisPointer: { type: 'shadow' }
      },
      grid: { left: 12, right: 12, top: 32, bottom: 12, containLabel: true },
      xAxis: {
        type: 'category',
        data: ['8h', '9h', '10h', '11h', '12h', '13h', '14h', '15h', '16h', '17h', '18h', '19h'],
        axisLine: { lineStyle: { color: 'rgba(148,163,184,.2)' } },
        axisLabel: { color: '#94a3b8', fontSize: 11, fontWeight: 600 }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.12)' } },
        axisLabel: { color: '#94a3b8', fontSize: 11, fontWeight: 600 }
      },
      series: [
        {
          name: '处理量',
          type: 'bar',
          data: baseData,
          barWidth: '60%',
          itemStyle: {
            color: (params: any) => {
              const colors = ['#1e40af', '#6366f1', '#f59e0b'];
              return colors[params.dataIndex % 3];
            },
            borderRadius: [4, 4, 0, 0]
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(30, 64, 175, .5)'
            }
          }
        }
      ]
    };
  });

  currentDate(): string {
    return new Date().toLocaleDateString('zh-CN');
  }

  tileIcon(label: string): string {
    const icons: Record<string, string> = {
      '物料': 'pi-box',
      '采购': 'pi-shopping-cart',
      '履约': 'pi-truck',
      '应收': 'pi-wallet',
      '风险': 'pi-exclamation-triangle',
      '健康': 'pi-heart'
    };
    return icons[label] || 'pi-chart-bar';
  }

  priorityCount(priority: string): number {
    return this.towerActions().filter(a => a.priority === priority).length;
  }

  protected readonly healthIndicators = computed(() => {
    const kpis = this.data().kpis;
    return [
      {
        label: '库存健康度',
        score: Math.min(100, Math.round((kpis.stock_quantity / (kpis.low_stock_products + kpis.stock_quantity)) * 100)),
        status: kpis.low_stock_products < 5 ? '优秀' : kpis.low_stock_products < 15 ? '良好' : '需关注',
        detail: `${kpis.stock_quantity} 总量 / ${kpis.low_stock_products} 低库存`,
        icon: 'pi-database'
      },
      {
        label: '采购效率',
        score: Math.max(60, 100 - kpis.pending_purchase * 2),
        status: kpis.pending_purchase < 10 ? '高效' : kpis.pending_purchase < 20 ? '正常' : '待提升',
        detail: `${kpis.pending_purchase} 待审批采购订单`,
        icon: 'pi-shopping-cart'
      },
      {
        label: '现金流健康',
        score: Math.max(50, 100 - Math.round(kpis.overdue_amount / 1000)),
        status: kpis.overdue_amount < 30000 ? '稳健' : kpis.overdue_amount < 60000 ? '警戒' : '风险',
        detail: `${this.compactMoney(kpis.overdue_amount)} 逾期应收`,
        icon: 'pi-wallet'
      },
      {
        label: '订单动能',
        score: Math.min(100, Math.round(kpis.order_amount / 1000)),
        status: kpis.order_amount > 100000 ? '强劲' : kpis.order_amount > 50000 ? '平稳' : '待激活',
        detail: `${this.compactMoney(kpis.order_amount)} 订单总额`,
        icon: 'pi-shopping-bag'
      },
      {
        label: '流程完整性',
        score: this.controlTowerScore(),
        status: this.controlTowerScore() >= 82 ? '完善' : this.controlTowerScore() >= 62 ? '基本' : '欠缺',
        detail: `${this.controlTower().summary.service_boundaries || 0} 个服务边界`,
        icon: 'pi-sitemap'
      },
      {
        label: '风险控制',
        score: Math.max(50, 100 - this.data().risks.length * 10),
        status: this.data().risks.length < 3 ? '良好' : this.data().risks.length < 6 ? '可控' : '需处理',
        detail: `${this.data().risks.length} 个风险项`,
        icon: 'pi-shield'
      }
    ];
  });
}
