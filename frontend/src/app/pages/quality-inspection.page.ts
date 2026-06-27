import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { ProgressBarModule } from 'primeng/progressbar';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { QualityInspectionLane, QualityInspectionPayload, QualityInspectionQueueItem } from '../core/models';
import { chartLegend, compactMoneyText, compactNumberText, TagSeverity } from './page-utils';

const EMPTY_QUALITY_INSPECTION: QualityInspectionPayload = {
  generated_at: '',
  source: 'quality_inspection_contract',
  summary: {
    quality_score: 0,
    pending_lots: 0,
    blocked_lots: 0,
    supplier_alerts: 0,
    defects: 0,
    documents: 0,
    open_tasks: 0,
    quality_reports: 0,
    usage_decision_rate: 0,
    p0: 0,
    p1: 0,
    queue_count: 0,
    primary_owner: '质量工程师',
    next_action: '等待质量检验数据。'
  },
  inspection_lanes: [],
  inspection_queue: [],
  supplier_quality: [],
  defect_taxonomy: [],
  inspection_lots: [],
  document_set: [],
  quality_flow: [],
  runbook: [],
  service_boundary: []
};

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, RouterLink, NgxEchartsDirective, ButtonModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page quality-inspection-page quality-inspection-governance-page">
      <header class="quality-hero quality-inspection-governance-hero atlas-split-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">质量检验治理</span>
          <h1>质量检验中心</h1>
          <p>把检验批、供应商质量、库存风险、缺陷遏制、使用决策和整改闭环合并成一个可派发的质量工作台。</p>
          <div class="atlas-actions-row">
            <button
              pButton
              type="button"
              (click)="createPrimaryInspectionTask()"
              [loading]="creatingId() === primaryQueueId()"
              [disabled]="loading() || !selectedQueueItem() || creatingId() !== null"
              aria-label="创建首要质量检验任务"
            >
              <i class="pi pi-verified"></i>
              创建首要检验
            </button>
            <button pButton type="button" severity="secondary" (click)="load()" [loading]="loading()" aria-label="刷新质量检验数据">
              <i class="pi pi-refresh"></i>
              刷新检验台
            </button>
            <button pButton type="button" severity="info" (click)="generateReport()" [loading]="reporting()" aria-label="生成质量检验报表">
              <i class="pi pi-chart-line"></i>
              质量报表
            </button>
          </div>
        </div>

        <aside class="quality-inspection-hero-stack">
          <article>
            <span>质量评分</span>
            <strong>{{ data().summary.quality_score }}%</strong>
            <em>{{ data().summary.pending_lots }} 个待决策批次 · {{ data().summary.defects }} 个缺陷对象</em>
          </article>
          <article>
            <span>首要负责人</span>
            <strong>{{ data().summary.primary_owner }}</strong>
            <em>{{ data().summary.next_action }}</em>
          </article>
          <article class="warning">
            <span>P0 / P1</span>
            <strong>{{ data().summary.p0 }} / {{ data().summary.p1 }}</strong>
            <em>{{ data().summary.queue_count }} 个检验候选 · {{ data().summary.open_tasks }} 个未闭环</em>
          </article>
        </aside>
      </header>

      <section class="quality-inspection-grid">
        <article class="atlas-panel quality-inspection-command-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">质量控制层</span>
              <h2>检验批、过程质量、供应商和缺陷遏制</h2>
            </div>
            <p-tag [severity]="data().summary.p0 ? 'danger' : data().summary.queue_count ? 'warn' : 'success'" [value]="data().summary.p0 ? '阻塞' : data().summary.queue_count ? '需检验' : '稳定'" />
          </div>

          <div class="quality-inspection-summary-strip" aria-label="质量检验摘要">
            <article>
              <span>待检批次</span>
              <strong>{{ data().summary.pending_lots }}</strong>
              <em>{{ data().summary.blocked_lots }} 个阻塞使用决策</em>
            </article>
            <article>
              <span>供应商预警</span>
              <strong>{{ data().summary.supplier_alerts }}</strong>
              <em>质量率、准点率、CAPA</em>
            </article>
            <article>
              <span>证据归档</span>
              <strong>{{ data().summary.documents }}</strong>
              <em>检验附件、CoA、质量报表</em>
            </article>
            <article>
              <span>使用决策</span>
              <strong>{{ data().summary.usage_decision_rate }}%</strong>
              <em>{{ data().source }}</em>
            </article>
          </div>

          <nav class="governance-action-strip" aria-label="质量检验快捷动作">
            <a routerLink="/app/procurement/orders">来料批次</a>
            <a routerLink="/app/suppliers/performance">供应商 CAPA</a>
            <a routerLink="/app/files">质量附件</a>
            <a routerLink="/app/reports">检验报表</a>
            <button type="button" (click)="chartMode.set('supplier')">供应商视图</button>
          </nav>

          @if (loading()) {
            <p-skeleton height="126px" />
          } @else {
            <div class="quality-inspection-lane-strip">
              @for (lane of data().inspection_lanes; track lane.id) {
                <button
                  type="button"
                  [class.active]="selectedLaneId() === lane.id"
                  [class.blocked]="lane.status === 'blocked'"
                  [class.attention]="lane.status === 'attention'"
                  (click)="selectLane(lane)"
                  [attr.aria-label]="'查看检验泳道 ' + lane.label"
                >
                  <span>{{ lane.label }} · {{ lane.owner }}</span>
                  <strong>{{ lane.score }}%</strong>
                  <p-progressbar [value]="bounded(lane.score)" [showValue]="false" />
                  <em>{{ lane.active_count }} 项 · P0 {{ lane.p0 }} · P1 {{ lane.p1 }}</em>
                </button>
              }
            </div>
          }
        </article>

        <article class="atlas-panel quality-inspection-chart-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">检验视图</span>
              <h2>{{ chartTitle() }}</h2>
            </div>
            <div class="quality-inspection-chart-tabs">
              <button type="button" [class.active]="chartMode() === 'supplier'" (click)="chartMode.set('supplier')">供应商</button>
              <button type="button" [class.active]="chartMode() === 'defect'" (click)="chartMode.set('defect')">缺陷</button>
              <button type="button" [class.active]="chartMode() === 'lots'" (click)="chartMode.set('lots')">批次</button>
            </div>
          </div>
          @if (loading()) {
            <p-skeleton height="340px" />
          } @else {
            <div class="quality-inspection-chart" echarts [options]="activeChart()"></div>
          }
        </article>

        <article class="atlas-panel quality-inspection-queue-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">检验队列</span>
              <h2>可派发检验任务</h2>
            </div>
            <p-tag [severity]="data().inspection_queue.length ? 'warn' : 'success'" [value]="data().inspection_queue.length + ' 项'" />
          </div>
          @if (loading()) {
            <p-skeleton height="104px" />
            <p-skeleton height="104px" />
          } @else {
            <div class="quality-inspection-queue-list">
              @for (item of data().inspection_queue; track item.id) {
                <article class="business-data-row" [class.active]="selectedQueueId() === item.id" [class.p0]="item.priority === 'P0'" [class.p1]="item.priority === 'P1'">
                  <button type="button" class="quality-inspection-queue-main" (click)="selectQueue(item.id)" [attr.aria-label]="'选择检验任务 ' + item.title">
                    <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
                    <div>
                      <span>{{ item.lot_code }} · {{ item.owner }} · SLA {{ item.sla }}</span>
                      <strong>{{ item.title }}</strong>
                      <em>{{ item.evidence }}</em>
                    </div>
                    <b>{{ item.risk_score }}%</b>
                  </button>
                  <div class="quality-inspection-queue-actions">
                    <a pButton [text]="true" size="small" [routerLink]="cleanPath(item.path)" [attr.aria-label]="'打开质量来源 ' + item.title">
                      <i class="pi pi-arrow-up-right"></i>
                      来源
                    </a>
                    <button
                      pButton
                      type="button"
                      size="small"
                      severity="secondary"
                      [loading]="creatingId() === item.id"
                      [disabled]="creatingId() !== null"
                      (click)="createInspectionTask(item)"
                      [attr.aria-label]="'创建质量检验任务 ' + item.title"
                    >
                      <i class="pi pi-send"></i>
                      创建任务
                    </button>
                  </div>
                </article>
              }
            </div>
          }
        </article>

        <article class="atlas-panel quality-inspection-selected-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">使用决策</span>
              <h2>{{ selectedQueueItem()?.decision || '质量决策' }}</h2>
            </div>
            @if (selectedQueueItem(); as item) {
              <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
            }
          </div>
          @if (selectedQueueItem(); as item) {
            <div class="quality-inspection-selected-card">
              <div class="quality-inspection-risk-code">
                <span>{{ item.supplier }} · {{ item.product_name }}</span>
                <strong>{{ item.lot_code }}</strong>
                <em>{{ item.owner }} · {{ item.sla }} · 风险 {{ item.risk_score }}%</em>
              </div>
              <p-progressbar [value]="bounded(item.risk_score)" [showValue]="false" />
              <p>{{ item.action }}</p>
              <div class="quality-inspection-checklist">
                @for (step of item.checklist; track step) {
                  <span><i class="pi pi-check-circle"></i>{{ step }}</span>
                }
              </div>
            </div>
          }
        </article>

        <article class="atlas-panel quality-inspection-supplier-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">供应商质量</span>
              <h2>SQE 观察与整改</h2>
            </div>
          </div>
          <div class="quality-inspection-supplier-list">
            @for (item of data().supplier_quality.slice(0, 8); track item.id) {
              <a class="business-data-row" [routerLink]="cleanPath(item.path)" [class.blocked]="item.status === 'blocked'" [class.attention]="item.status === 'attention'">
                <div>
                  <span>{{ item.total_orders }} 单 · 待处理 {{ item.pending_orders }}</span>
                  <strong>{{ item.name }}</strong>
                  <em>{{ item.evidence }}</em>
                </div>
                <b>{{ item.score }}%</b>
                <p-progressbar [value]="bounded(item.score)" [showValue]="false" />
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel quality-inspection-defect-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">缺陷分类</span>
              <h2>不合格与遏制面</h2>
            </div>
          </div>
          <div class="quality-inspection-defect-grid">
            @for (item of data().defect_taxonomy; track item.id) {
              <article class="business-data-row" [class.blocked]="item.status === 'blocked'" [class.attention]="item.status === 'attention'">
                <div>
                  <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
                  <strong>{{ item.count }}</strong>
                </div>
                <span>{{ item.type }} · {{ item.owner }}</span>
                <b>{{ item.label }}</b>
                <em>{{ item.impact }}</em>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel quality-inspection-lot-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">检验批账本</span>
              <h2>采购批次与放行状态</h2>
            </div>
          </div>
          <div class="quality-inspection-lot-list">
            @for (lot of data().inspection_lots.slice(0, 10); track lot.id) {
              <a class="business-data-row" [routerLink]="cleanPath(lot.path)" [class.blocked]="lot.status === 'blocked'" [class.attention]="lot.status === 'attention'">
                <div>
                  <span>{{ lot.lot_code }} · {{ lot.warehouse }} · {{ lot.inspection_type }}</span>
                  <strong>{{ lot.reference }} / {{ lot.supplier }}</strong>
                  <em>{{ lot.decision }} · {{ lot.quantity }} 件 · {{ compactMoney(lot.amount) }}</em>
                </div>
                <b>{{ lot.progress }}%</b>
                <p-progressbar [value]="bounded(lot.progress)" [showValue]="false" />
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel quality-inspection-doc-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">质量证据</span>
              <h2>附件与报表归档</h2>
            </div>
          </div>
          <div class="quality-inspection-doc-list">
            @for (doc of data().document_set; track doc.id) {
              <a class="business-data-row" [routerLink]="cleanPath(doc.path)">
                <i class="pi pi-file-check"></i>
                <div>
                  <strong>{{ doc.title }}</strong>
                  <span>{{ doc.type }} · {{ compact(doc.size) }}</span>
                  <em>{{ doc.evidence }}</em>
                </div>
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel quality-inspection-boundary-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">服务边界</span>
              <h2>质量微服务拆分面</h2>
            </div>
          </div>
          <div class="quality-inspection-boundary-list">
            @for (item of data().service_boundary; track item.service) {
              <article class="business-data-row" [class.blocked]="item.readiness === 'blocked'" [class.attention]="item.readiness === 'attention'">
                <p-tag [severity]="statusSeverity(item.readiness)" [value]="levelLabel(item.readiness)" />
                <strong>{{ item.service }}</strong>
                <span>{{ item.contract }} · {{ item.owner }}</span>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel quality-inspection-flow-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">流程</span>
              <h2>从检验批到整改</h2>
            </div>
          </div>
          <div class="quality-inspection-flow-list">
            @for (item of data().quality_flow; track item.step) {
              <article class="business-data-row">
                <i>{{ $index + 1 }}</i>
                <div>
                  <strong>{{ item.step }}</strong>
                  <span>{{ item.detail }}</span>
                </div>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel quality-inspection-runbook-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">Runbook</span>
              <h2>质量检验手册</h2>
            </div>
          </div>
          <div class="quality-inspection-runbook-list">
            @for (item of data().runbook; track item.step) {
              <article class="business-data-row">
                <i class="pi pi-check-circle"></i>
                <div>
                  <strong>{{ item.step }}</strong>
                  <span>{{ item.detail }}</span>
                </div>
              </article>
            }
          </div>
        </article>
      </section>
    </section>
  `
})
export class QualityInspectionPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly reporting = signal(false);
  protected readonly creatingId = signal<string | null>(null);
  protected readonly selectedLaneId = signal('');
  protected readonly selectedQueueId = signal('');
  protected readonly chartMode = signal<'supplier' | 'defect' | 'lots'>('supplier');
  protected readonly data = signal<QualityInspectionPayload>(EMPTY_QUALITY_INSPECTION);
  protected readonly selectedLane = computed<QualityInspectionLane | null>(() => {
    const lanes = this.data().inspection_lanes;
    return lanes.find(item => item.id === this.selectedLaneId()) ?? lanes[0] ?? null;
  });
  protected readonly selectedQueueItem = computed<QualityInspectionQueueItem | null>(() => {
    const queue = this.data().inspection_queue;
    return queue.find(item => item.id === this.selectedQueueId()) ?? queue[0] ?? null;
  });
  protected readonly primaryQueueItem = computed<QualityInspectionQueueItem | null>(() => this.data().inspection_queue[0] ?? null);
  protected readonly primaryQueueId = computed(() => this.primaryQueueItem()?.id ?? this.selectedQueueItem()?.id ?? 'quality-inspection');
  protected readonly chartTitle = computed(() => {
    if (this.chartMode() === 'defect') {
      return '缺陷分类与遏制对象';
    }
    if (this.chartMode() === 'lots') {
      return '检验批使用决策';
    }
    return '供应商质量与准点率';
  });
  protected readonly activeChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'defect') {
      return this.defectChart();
    }
    if (this.chartMode() === 'lots') {
      return this.lotChart();
    }
    return this.supplierChart();
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.get<QualityInspectionPayload>('operations/quality-inspection').pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '质量检验台未加载', detail: error?.message || '请稍后重试。' });
        return of(EMPTY_QUALITY_INSPECTION);
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(payload => {
      this.data.set(payload);
      if (!payload.inspection_lanes.some(item => item.id === this.selectedLaneId())) {
        this.selectedLaneId.set(payload.inspection_lanes[0]?.id ?? '');
      }
      if (!payload.inspection_queue.some(item => item.id === this.selectedQueueId())) {
        this.selectedQueueId.set(payload.inspection_queue[0]?.id ?? '');
      }
    });
  }

  protected selectLane(lane: QualityInspectionLane): void {
    this.selectedLaneId.set(lane.id);
    const matching = this.data().inspection_queue.find(item => item.path === lane.path || item.owner === lane.owner || item.source.includes(lane.id.split('-')[0]));
    if (matching) {
      this.selectedQueueId.set(matching.id);
    }
  }

  protected selectQueue(id: string): void {
    this.selectedQueueId.set(id);
  }

  protected createPrimaryInspectionTask(): void {
    const item = this.primaryQueueItem() ?? this.selectedQueueItem();
    if (item) {
      this.createInspectionTask(item);
    }
  }

  protected createInspectionTask(item: QualityInspectionQueueItem): void {
    this.creatingId.set(item.id);
    this.api.post('operations/quality-inspection', {
      queue_item_id: item.id,
      product_id: item.product_id,
      supplier_id: item.supplier_id,
      purchase_id: item.purchase_id,
      title: item.title,
      owner: item.owner,
      priority: item.priority,
      sla: item.sla,
      evidence: item.evidence,
      action: item.action,
      path: item.path
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '检验任务未创建', detail: error?.message || '检验任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.creatingId.set(null))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '检验任务已创建', detail: `${item.title} 已进入任务异常中心。` });
      }
    });
  }

  protected generateReport(): void {
    this.reporting.set(true);
    this.api.post('reports/generate/quality_inspection', { params: {} }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '质量报表未生成', detail: error?.message || '报表服务未返回结果。' });
        return of(null);
      }),
      finalize(() => this.reporting.set(false))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '质量报表已生成', detail: '已进入报表归档。' });
      }
    });
  }

  private supplierChart(): EChartsCoreOption {
    const rows = this.data().supplier_quality.slice(0, 10);
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top', 'rgba(226,239,255,.82)'),
      grid: { left: 18, right: 18, top: 44, bottom: 34, containLabel: true },
      xAxis: {
        type: 'category',
        data: rows.map(item => item.name),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: 'rgba(226,239,255,.7)', fontWeight: 800, width: 96, overflow: 'truncate' }
      },
      yAxis: {
        type: 'value',
        max: 100,
        axisLabel: { color: 'rgba(226,239,255,.58)', formatter: (value: number | string) => compactNumberText(value) },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } }
      },
      series: [
        { name: '质量率', type: 'bar', data: rows.map(item => item.quality_rate), barWidth: 22, itemStyle: { color: '#14b8a6', borderRadius: [10, 10, 3, 3] } },
        { name: '准点率', type: 'line', smooth: true, data: rows.map(item => item.on_time_rate), lineStyle: { color: '#3b82f6', width: 3 }, symbolSize: 8 }
      ]
    };
  }

  private defectChart(): EChartsCoreOption {
    const rows = this.data().defect_taxonomy;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      series: [{
        type: 'treemap',
        roam: false,
        breadcrumb: { show: false },
        label: { color: 'rgba(226,239,255,.86)', formatter: '{b}' },
        itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(15,23,42,.82)' },
        data: rows.map(item => ({
          name: item.label,
          value: Math.max(1, item.count),
          itemStyle: { color: item.priority === 'P0' ? '#ef5f78' : item.priority === 'P1' ? '#f59e0b' : '#14b8a6' }
        }))
      }]
    };
  }

  private lotChart(): EChartsCoreOption {
    const rows = this.data().inspection_lots.slice(0, 10);
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top', 'rgba(226,239,255,.82)'),
      grid: { left: 18, right: 18, top: 44, bottom: 34, containLabel: true },
      xAxis: { type: 'category', data: rows.map(item => item.lot_code), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: 'rgba(226,239,255,.7)', fontWeight: 800, width: 92, overflow: 'truncate' } },
      yAxis: { type: 'value', max: 100, axisLabel: { color: 'rgba(226,239,255,.58)' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } } },
      series: [
        { name: '收货进度', type: 'bar', data: rows.map(item => item.progress), barWidth: 24, itemStyle: { color: '#22d3ee', borderRadius: [10, 10, 3, 3] } },
        { name: '风险权重', type: 'line', smooth: true, data: rows.map(item => item.priority === 'P0' ? 92 : item.priority === 'P1' ? 68 : 28), lineStyle: { color: '#f59e0b', width: 3 }, symbolSize: 8 }
      ]
    };
  }

  protected prioritySeverity(priority: string): TagSeverity {
    return priority === 'P0' ? 'danger' : priority === 'P1' ? 'warn' : 'success';
  }

  protected statusSeverity(status: string): TagSeverity {
    if (status === 'blocked') {
      return 'danger';
    }
    if (status === 'attention') {
      return 'warn';
    }
    return 'success';
  }

  protected levelLabel(status: string): string {
    return status === 'blocked' ? '阻塞' : status === 'attention' ? '关注' : '稳定';
  }

  protected bounded(value: unknown): number {
    const number = Number(value ?? 0);
    return Math.max(0, Math.min(100, Number.isFinite(number) ? number : 0));
  }

  protected compact(value: unknown): string {
    return compactNumberText(value);
  }

  protected compactMoney(value: unknown): string {
    return compactMoneyText(value);
  }

  protected cleanPath(path?: string | null): string {
    return path?.startsWith('/app') ? path : '/app/quality';
  }
}
