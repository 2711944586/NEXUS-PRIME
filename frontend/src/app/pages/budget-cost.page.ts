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
import { CostCenter, CostGovernancePayload, CostVarianceQueueItem } from '../core/models';
import { chartLegend, compactMoneyText, compactNumberText, compactPieSeries, TagSeverity } from './page-utils';

const EMPTY_COSTS: CostGovernancePayload = {
  generated_at: '',
  source: 'cost_governance_contract',
  summary: {
    inventory_value: 0,
    sales_amount: 0,
    procurement_amount: 0,
    unpaid_amount: 0,
    paid_amount: 0,
    cash_gap: 0,
    budget_total: 0,
    actual_total: 0,
    commitment_total: 0,
    available_budget: 0,
    variance_amount: 0,
    burn_rate: 0,
    score: 0,
    p0: 0,
    p1: 0,
    queue_count: 0,
    primary_owner: '经营财务',
    next_action: '等待预算成本数据。'
  },
  cost_centers: [],
  variance_queue: [],
  categories: [],
  timeline: [],
  waterfall: [],
  runbook: [],
  service_boundary: []
};

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, RouterLink, NgxEchartsDirective, ButtonModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page budget-cost-page">
      <header class="atlas-split-hero budget-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">成本治理</span>
          <h1>预算成本中心</h1>
          <p>把预算、实际消耗、采购承诺、库存资金占用和应收现金缺口放到同一张可执行经营控制表里。</p>
          <div class="atlas-actions-row">
            <button
              pButton
              type="button"
              (click)="createPrimaryReview()"
              [loading]="reviewingId() === primaryReviewId()"
              [disabled]="loading() || !selectedCenter() || reviewingId() !== null"
              aria-label="创建首要预算差异复核任务"
            >
              <i class="pi pi-flag"></i>
              创建首要复核
            </button>
            <button pButton type="button" severity="secondary" (click)="load()" [loading]="loading()" aria-label="刷新预算成本数据">
              <i class="pi pi-refresh"></i>
              刷新数据
            </button>
            <a pButton severity="info" routerLink="/app/reports">
              <i class="pi pi-chart-line"></i>
              生成报表
            </a>
          </div>
        </div>

        <aside class="budget-governance-stack">
          <article>
            <span>预算消耗率</span>
            <strong>{{ data().summary.burn_rate }}%</strong>
            <em>{{ money(data().summary.actual_total) }} 实际 / {{ money(data().summary.commitment_total) }} 承诺</em>
          </article>
          <article>
            <span>责任人</span>
            <strong>{{ data().summary.primary_owner }}</strong>
            <em>{{ data().summary.next_action }}</em>
          </article>
          <article class="warning">
            <span>可用预算</span>
            <strong>{{ money(data().summary.available_budget) }}</strong>
            <em>{{ data().summary.p0 }} 个 P0 / {{ data().summary.p1 }} 个 P1</em>
          </article>
        </aside>
      </header>

      <section class="budget-grid budget-governance-grid">
        <article class="atlas-panel budget-command-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">经营控制层</span>
              <h2>预算、实际、承诺和可用预算</h2>
            </div>
            <p-tag [severity]="data().summary.p0 ? 'danger' : data().summary.queue_count ? 'warn' : 'success'" [value]="data().summary.p0 ? '阻塞' : data().summary.queue_count ? '需复核' : '稳定'" />
          </div>

          <div class="budget-command-summary" aria-label="预算成本摘要">
            <article>
              <span>预算池</span>
              <strong>{{ money(data().summary.budget_total) }}</strong>
              <em>{{ data().source }}</em>
            </article>
            <article>
              <span>实际消耗</span>
              <strong>{{ money(data().summary.actual_total) }}</strong>
              <em>库存、采购、应收口径</em>
            </article>
            <article>
              <span>采购承诺</span>
              <strong>{{ money(data().summary.commitment_total) }}</strong>
              <em>未完成采购和补货</em>
            </article>
            <article>
              <span>差异金额</span>
              <strong>{{ money(data().summary.variance_amount) }}</strong>
              <em>评分 {{ data().summary.score }}</em>
            </article>
          </div>

          @if (loading()) {
            <p-skeleton height="104px" />
          } @else {
            <div class="budget-center-strip">
              @for (center of data().cost_centers; track center.id) {
                <button
                  type="button"
                  [class.active]="selectedCenterId() === center.id"
                  [class.blocked]="center.status === 'blocked'"
                  [class.attention]="center.status === 'attention'"
                  (click)="selectCenter(center.id)"
                  [attr.aria-label]="'查看成本中心 ' + center.label"
                >
                  <span>{{ center.label }} · {{ center.owner }}</span>
                  <strong>{{ center.used_rate }}%</strong>
                  <p-progressbar [value]="bounded(center.used_rate)" [showValue]="false" />
                  <em>{{ money(center.available) }} 可用 · {{ center.sla }}</em>
                </button>
              }
            </div>
          }
        </article>

        <article class="atlas-panel budget-chart-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">预算控制</span>
              <h2>成本中心消耗与承诺</h2>
            </div>
            <p-tag severity="info" value="Budget / Actual / Commit" />
          </div>
          @if (loading()) {
            <p-skeleton height="340px" />
          } @else {
            <div class="budget-chart" echarts [options]="burnChart()"></div>
          }
        </article>

        <article class="atlas-panel budget-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">库存成本</span>
              <h2>库存成本结构</h2>
            </div>
          </div>
          @if (loading()) {
            <p-skeleton height="300px" />
          } @else {
            <div class="budget-chart" echarts [options]="categoryChart()"></div>
          }
        </article>

        <article class="atlas-panel budget-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">资金桥</span>
              <h2>预算瀑布</h2>
            </div>
          </div>
          @if (loading()) {
            <p-skeleton height="300px" />
          } @else {
            <div class="budget-chart" echarts [options]="waterfallChart()"></div>
          }
        </article>

        <article class="atlas-panel budget-variance-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">差异队列</span>
              <h2>预算差异复核</h2>
            </div>
            <p-tag [severity]="data().variance_queue.length ? 'warn' : 'success'" [value]="data().variance_queue.length ? data().variance_queue.length + ' 项' : '清零'" />
          </div>
          @if (loading()) {
            <p-skeleton height="92px" />
            <p-skeleton height="92px" />
          } @else if (!data().variance_queue.length) {
            <div class="budget-empty-state">
              <strong>预算差异清零</strong>
              <span>继续每日对比预算、实际和采购承诺。</span>
            </div>
          } @else {
            <div class="budget-variance-list">
              @for (item of data().variance_queue; track item.id) {
                <article [class.p0]="item.priority === 'P0'" [class.p1]="item.priority === 'P1'">
                  <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
                  <div>
                    <span>{{ item.owner }} · SLA {{ item.sla }} · 差异 {{ item.variance_rate }}%</span>
                    <strong>{{ item.title }}</strong>
                    <em>{{ item.evidence }}</em>
                  </div>
                  <div class="budget-variance-actions">
                    <a pButton [text]="true" size="small" [routerLink]="cleanPath(item.path)" [attr.aria-label]="'查看成本来源 ' + item.title">
                      <i class="pi pi-arrow-up-right"></i>
                      来源
                    </a>
                    <button
                      pButton
                      type="button"
                      size="small"
                      severity="secondary"
                      [loading]="reviewingId() === item.id"
                      [disabled]="reviewingId() !== null"
                      (click)="createVarianceReview(item)"
                      [attr.aria-label]="'创建预算差异复核任务 ' + item.title"
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

        <article class="atlas-panel budget-detail-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">成本中心</span>
              <h2>{{ selectedCenterLabel() }}</h2>
            </div>
            @if (selectedCenter()) {
              <p-tag [severity]="statusSeverity(selectedCenter()!.status)" [value]="selectedCenter()!.priority" />
            }
          </div>
          @if (selectedCenter()) {
            <div class="budget-detail-card">
              <strong>{{ selectedCenter()!.owner }} · {{ selectedCenter()!.priority_owner }}</strong>
              <span>{{ selectedCenter()!.evidence }}</span>
              <div class="budget-detail-metrics">
                <article><span>预算</span><strong>{{ money(selectedCenter()!.budget) }}</strong></article>
                <article><span>实际</span><strong>{{ money(selectedCenter()!.actual) }}</strong></article>
                <article><span>承诺</span><strong>{{ money(selectedCenter()!.commitment) }}</strong></article>
                <article><span>可用</span><strong>{{ money(selectedCenter()!.available) }}</strong></article>
              </div>
              <p-progressbar [value]="bounded(selectedCenter()!.used_rate)" [showValue]="false" />
              <em>{{ selectedCenter()!.action }}</em>
              <a pButton size="small" [routerLink]="cleanPath(selectedCenter()!.path)" [attr.aria-label]="'打开来源模块 ' + selectedCenter()!.label">
                <i class="pi pi-arrow-up-right"></i>
                来源模块
              </a>
            </div>
          }
        </article>

        <article class="atlas-panel budget-boundary-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">服务边界</span>
              <h2>成本微服务拆分面</h2>
            </div>
          </div>
          <div class="budget-boundary-list">
            @for (item of data().service_boundary; track item.service) {
              <article [class.blocked]="item.readiness === 'blocked'" [class.attention]="item.readiness === 'attention'">
                <p-tag [severity]="statusSeverity(item.readiness)" [value]="levelLabel(item.readiness)" />
                <strong>{{ item.service }}</strong>
                <span>{{ item.contract }} · {{ item.owner }}</span>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel budget-runbook-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">Runbook</span>
              <h2>预算复核运行手册</h2>
            </div>
          </div>
          <div class="budget-runbook-list">
            @for (item of data().runbook; track item.step) {
              <article>
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
export class BudgetCostPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly reviewingId = signal<string | null>(null);
  protected readonly selectedCenterId = signal('');
  protected readonly data = signal<CostGovernancePayload>(EMPTY_COSTS);
  protected readonly selectedCenter = computed(() => {
    const centers = this.data().cost_centers;
    return centers.find(item => item.id === this.selectedCenterId()) ?? centers[0] ?? null;
  });
  protected readonly selectedCenterLabel = computed(() => this.selectedCenter()?.label ?? '成本中心明细');
  protected readonly primaryVariance = computed(() => this.data().variance_queue[0] ?? null);
  protected readonly primaryReviewId = computed(() => this.primaryVariance()?.id ?? this.selectedCenter()?.id ?? 'budget-review');
  protected readonly burnChart = computed<EChartsCoreOption>(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: chartLegend('top', 'rgba(226,239,255,.82)'),
    grid: { left: 18, right: 18, top: 44, bottom: 28, containLabel: true },
    xAxis: {
      type: 'category',
      data: this.data().cost_centers.map(item => item.label),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: 'rgba(226,239,255,.68)', fontWeight: 700, width: 80, overflow: 'truncate' }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: 'rgba(226,239,255,.58)', formatter: (value: number | string) => compactNumberText(value) },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } }
    },
    series: [
      { name: '预算', type: 'bar', data: this.data().cost_centers.map(item => item.budget), itemStyle: { color: '#3b82f6', borderRadius: [9, 9, 2, 2] } },
      { name: '实际', type: 'bar', data: this.data().cost_centers.map(item => item.actual), itemStyle: { color: '#14b8a6', borderRadius: [9, 9, 2, 2] } },
      { name: '承诺', type: 'bar', data: this.data().cost_centers.map(item => item.commitment), itemStyle: { color: '#f59e0b', borderRadius: [9, 9, 2, 2] } }
    ]
  }));
  protected readonly categoryChart = computed<EChartsCoreOption>(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: chartLegend('bottom', 'rgba(226,239,255,.78)'),
    series: [compactPieSeries(this.data().categories, {
      radius: ['42%', '66%'],
      center: ['50%', '42%'],
      itemStyle: { borderColor: 'rgba(15,23,42,.56)' }
    })]
  }));
  protected readonly waterfallChart = computed<EChartsCoreOption>(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 18, right: 18, top: 26, bottom: 28, containLabel: true },
    xAxis: {
      type: 'category',
      data: this.data().waterfall.map(item => item.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: 'rgba(226,239,255,.68)', fontWeight: 700 }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: 'rgba(226,239,255,.58)', formatter: (value: number | string) => compactNumberText(value) },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } }
    },
    series: [{
      type: 'bar',
      data: this.data().waterfall.map(item => ({
        value: item.value,
        itemStyle: {
          color: item.type === 'available' ? '#22c55e' : item.type === 'budget' ? '#3b82f6' : item.type === 'commitment' ? '#f59e0b' : '#ef4444'
        }
      })),
      itemStyle: { borderRadius: [10, 10, 2, 2] }
    }]
  }));

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.get<CostGovernancePayload>('operations/costs').pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '预算成本未加载', detail: error?.message || '请稍后重试。' });
        return of(EMPTY_COSTS);
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(payload => {
      this.data.set(payload);
      if (!payload.cost_centers.some(item => item.id === this.selectedCenterId())) {
        this.selectedCenterId.set(payload.variance_queue[0]?.cost_center_id ?? payload.cost_centers[0]?.id ?? '');
      }
    });
  }

  protected selectCenter(centerId: string): void {
    this.selectedCenterId.set(centerId);
  }

  protected createPrimaryReview(): void {
    const variance = this.primaryVariance();
    if (variance) {
      this.createVarianceReview(variance);
      return;
    }
    const center = this.selectedCenter();
    if (center) {
      this.createCenterReview(center);
    }
  }

  protected createVarianceReview(item: CostVarianceQueueItem): void {
    this.reviewingId.set(item.id);
    this.postReview({
      item_id: item.id,
      cost_center_id: item.cost_center_id,
      title: item.title,
      owner: item.owner,
      priority: item.priority,
      sla: item.sla,
      evidence: item.evidence,
      action: item.action,
      path: item.path
    }, item.title);
  }

  private createCenterReview(center: CostCenter): void {
    this.reviewingId.set(center.id);
    this.postReview({
      item_id: center.id,
      cost_center_id: center.id,
      title: `${center.label}预算差异复核`,
      owner: center.owner,
      priority: center.priority,
      sla: center.sla,
      evidence: center.evidence,
      action: center.action,
      path: center.path
    }, center.label);
  }

  private postReview(payload: Record<string, string>, detail: string): void {
    this.api.post('operations/costs/review', payload).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '成本复核未创建', detail: error?.message || '复核任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.reviewingId.set(null))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '成本复核已创建', detail: `${detail} 已进入任务异常中心。` });
      }
    });
  }

  protected statusSeverity(status: string): TagSeverity {
    if (status === 'ready') {
      return 'success';
    }
    if (status === 'blocked') {
      return 'danger';
    }
    return 'warn';
  }

  protected prioritySeverity(priority: string): TagSeverity {
    if (priority === 'P0') {
      return 'danger';
    }
    if (priority === 'P1') {
      return 'warn';
    }
    return 'info';
  }

  protected levelLabel(status: string): string {
    const map: Record<string, string> = {
      ready: '稳定',
      attention: '需复核',
      blocked: '阻塞'
    };
    return map[status] ?? status;
  }

  protected bounded(value: number): number {
    return Math.max(0, Math.min(100, Math.round(Number(value || 0))));
  }

  protected cleanPath(path: string): string {
    return path.split('?')[0] || '/app/budget';
  }

  protected money(value: unknown): string {
    return compactMoneyText(value);
  }
}
