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
import { CapacityBottleneckItem, CapacityGovernancePayload, CapacityWorkCenter } from '../core/models';
import { chartLegend, compactMoneyText, compactNumberText, compactPieSeries, TagSeverity } from './page-utils';

const EMPTY_CAPACITY: CapacityGovernancePayload = {
  generated_at: '',
  source: 'capacity_governance_contract',
  summary: {
    load_score: 0,
    demand_units: 0,
    incoming_units: 0,
    shortage_units: 0,
    active_orders: 0,
    pending_purchase: 0,
    low_materials: 0,
    warehouse_utilization: 0,
    p0: 0,
    p1: 0,
    queue_count: 0,
    primary_owner: '计划主管',
    next_action: '等待产能计划数据。'
  },
  work_centers: [],
  shift_plan: [],
  bottleneck_queue: [],
  demand: [],
  supply: [],
  material_constraints: [],
  load_curve: [],
  runbook: [],
  service_boundary: []
};

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, RouterLink, NgxEchartsDirective, ButtonModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page capacity-page capacity-governance-page">
      <header class="capacity-hero atlas-split-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">产能治理</span>
          <h1>产能计划中心</h1>
          <p>把销售需求、采购到货、物料齐套、仓库释放和班次负载合并到一张可执行计划表里。</p>
          <div class="atlas-actions-row">
            <button
              pButton
              type="button"
              (click)="createPrimaryReview()"
              [loading]="reviewingId() === primaryReviewId()"
              [disabled]="loading() || !selectedCenter() || reviewingId() !== null"
              aria-label="创建首要产能复核任务"
            >
              <i class="pi pi-calendar-plus"></i>
              创建首要复核
            </button>
            <button pButton type="button" severity="secondary" (click)="load()" [loading]="loading()" aria-label="刷新产能计划数据">
              <i class="pi pi-refresh"></i>
              刷新计划
            </button>
            <a pButton severity="info" routerLink="/app/procurement/orders">
              <i class="pi pi-truck"></i>
              到货窗口
            </a>
          </div>
        </div>

        <aside class="capacity-governance-stack">
          <article>
            <span>综合负载</span>
            <strong>{{ data().summary.load_score }}%</strong>
            <em>{{ data().summary.active_orders }} 单需求 / {{ data().summary.pending_purchase }} 单供给</em>
          </article>
          <article>
            <span>责任人</span>
            <strong>{{ data().summary.primary_owner }}</strong>
            <em>{{ data().summary.next_action }}</em>
          </article>
          <article class="warning">
            <span>物料缺口</span>
            <strong>{{ compact(data().summary.shortage_units) }}</strong>
            <em>{{ data().summary.low_materials }} 项低水位 · {{ data().summary.warehouse_utilization }}% 库容</em>
          </article>
        </aside>
      </header>

      <section class="capacity-grid capacity-governance-grid">
        <article class="atlas-panel capacity-command-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">计划控制层</span>
              <h2>需求、供给、齐套和释放能力</h2>
            </div>
            <p-tag [severity]="data().summary.p0 ? 'danger' : data().summary.queue_count ? 'warn' : 'success'" [value]="data().summary.p0 ? '阻塞' : data().summary.queue_count ? '需复核' : '稳定'" />
          </div>

          <div class="capacity-command-summary" aria-label="产能计划摘要">
            <article>
              <span>销售需求</span>
              <strong>{{ compact(data().summary.demand_units) }}</strong>
              <em>{{ data().summary.active_orders }} 单履约窗口</em>
            </article>
            <article>
              <span>采购供给</span>
              <strong>{{ compact(data().summary.incoming_units) }}</strong>
              <em>{{ data().summary.pending_purchase }} 单到货释放</em>
            </article>
            <article>
              <span>物料缺口</span>
              <strong>{{ compact(data().summary.shortage_units) }}</strong>
              <em>{{ data().summary.low_materials }} 项低于安全线</em>
            </article>
            <article>
              <span>库容利用</span>
              <strong>{{ data().summary.warehouse_utilization }}%</strong>
              <em>{{ data().source }}</em>
            </article>
          </div>

          <nav class="governance-action-strip" aria-label="产能计划快捷动作">
            <a routerLink="/app/sales/orders">销售需求</a>
            <a routerLink="/app/procurement/orders">到货释放</a>
            <a routerLink="/app/inventory/replenishment">物料齐套</a>
            <a routerLink="/app/dispatch">仓配调度</a>
            <button type="button" (click)="chartMode.set('supply')">供需视图</button>
          </nav>

          @if (loading()) {
            <p-skeleton height="108px" />
          } @else {
            <div class="capacity-center-strip">
              @for (center of data().work_centers; track center.id) {
                <button
                  type="button"
                  [class.active]="selectedCenterId() === center.id"
                  [class.blocked]="center.status === 'blocked'"
                  [class.attention]="center.status === 'attention'"
                  (click)="selectCenter(center.id)"
                  [attr.aria-label]="'查看产能工位 ' + center.label"
                >
                  <span>{{ center.label }} · {{ center.owner }}</span>
                  <strong>{{ center.load }}%</strong>
                  <p-progressbar [value]="bounded(center.load)" [showValue]="false" />
                  <em>{{ center.required_hours }}h 需求 / {{ center.available_hours }}h 可用 · {{ center.sla }}</em>
                </button>
              }
            </div>
          }
        </article>

        <article class="atlas-panel capacity-chart-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">排程视图</span>
              <h2>{{ chartTitle() }}</h2>
            </div>
            <div class="chart-tabs">
              <button type="button" [class.active]="chartMode() === 'load'" (click)="chartMode.set('load')">负载</button>
              <button type="button" [class.active]="chartMode() === 'shift'" (click)="chartMode.set('shift')">班次</button>
              <button type="button" [class.active]="chartMode() === 'supply'" (click)="chartMode.set('supply')">供需</button>
            </div>
          </div>
          @if (loading()) {
            <p-skeleton height="340px" />
          } @else {
            <div class="capacity-chart" echarts [options]="activeChart()"></div>
          }
        </article>

        <article class="atlas-panel capacity-bottleneck-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">约束队列</span>
              <h2>产能瓶颈复核</h2>
            </div>
            <p-tag [severity]="data().bottleneck_queue.length ? 'warn' : 'success'" [value]="data().bottleneck_queue.length ? data().bottleneck_queue.length + ' 项' : '清零'" />
          </div>
          @if (loading()) {
            <p-skeleton height="92px" />
            <p-skeleton height="92px" />
          } @else if (!data().bottleneck_queue.length) {
            <div class="capacity-empty-state">
              <strong>产能约束清零</strong>
              <span>继续按班次复核需求、供给和库存释放能力。</span>
            </div>
          } @else {
            <div class="capacity-bottleneck-list">
              @for (item of data().bottleneck_queue; track item.id) {
                <article [class.p0]="item.priority === 'P0'" [class.p1]="item.priority === 'P1'">
                  <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
                  <div>
                    <span>{{ item.owner }} · SLA {{ item.sla }} · 负载 {{ item.load }}%</span>
                    <strong>{{ item.title }}</strong>
                    <em>{{ item.evidence }}</em>
                  </div>
                  <div class="capacity-bottleneck-actions">
                    <a pButton [text]="true" size="small" [routerLink]="cleanPath(item.path)" [attr.aria-label]="'查看产能来源 ' + item.title">
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
                      (click)="createBottleneckReview(item)"
                      [attr.aria-label]="'创建产能复核任务 ' + item.title"
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

        <article class="atlas-panel capacity-detail-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">工位合同</span>
              <h2>{{ selectedCenterLabel() }}</h2>
            </div>
            @if (selectedCenter()) {
              <p-tag [severity]="statusSeverity(selectedCenter()!.status)" [value]="selectedCenter()!.priority" />
            }
          </div>
          @if (selectedCenter()) {
            <div class="capacity-detail-card">
              <strong>{{ selectedCenter()!.owner }} · {{ selectedCenter()!.sla }}</strong>
              <span>{{ selectedCenter()!.evidence }}</span>
              <div class="capacity-detail-metrics">
                <article><span>负载</span><strong>{{ selectedCenter()!.load }}%</strong></article>
                <article><span>需求</span><strong>{{ selectedCenter()!.required_hours }}h</strong></article>
                <article><span>可用</span><strong>{{ selectedCenter()!.available_hours }}h</strong></article>
                <article><span>缺口</span><strong>{{ selectedCenter()!.hour_gap }}h</strong></article>
              </div>
              <p-progressbar [value]="bounded(selectedCenter()!.load)" [showValue]="false" />
              <em>{{ selectedCenter()!.action }}</em>
              <a pButton size="small" [routerLink]="cleanPath(selectedCenter()!.path)" [attr.aria-label]="'打开来源模块 ' + selectedCenter()!.label">
                <i class="pi pi-arrow-up-right"></i>
                来源模块
              </a>
            </div>
          }
        </article>

        <article class="atlas-panel capacity-record-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">需求窗口</span>
              <h2>销售履约需求</h2>
            </div>
          </div>
          <div class="capacity-record-list">
            @for (item of data().demand.slice(0, 5); track item.id) {
              <a [routerLink]="cleanPath(item.path)">
                <strong>{{ item.title }}</strong>
                <span>{{ item.customer }} · {{ statusLabel(item.status) }}</span>
                <em>{{ compact(item.units) }} 件 · {{ money(item.amount) }}</em>
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel capacity-record-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">供给窗口</span>
              <h2>采购到货释放</h2>
            </div>
          </div>
          <div class="capacity-record-list">
            @for (item of data().supply.slice(0, 5); track item.id) {
              <a [routerLink]="cleanPath(item.path)">
                <strong>{{ item.title }}</strong>
                <span>{{ item.supplier }} · {{ item.warehouse }}</span>
                <em>{{ item.progress }}% 到货 · {{ money(item.amount) }}</em>
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel capacity-material-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">齐套约束</span>
              <h2>物料缺口</h2>
            </div>
          </div>
          <div class="capacity-material-list">
            @for (item of data().material_constraints.slice(0, 6); track item.id) {
              <a [routerLink]="cleanPath(item.path)">
                <strong>{{ item.name }}</strong>
                <span>{{ item.sku }} · 缺口 {{ compact(item.shortage_units) }}</span>
                <em>现存 {{ compact(item.total_stock) }} / 安全线 {{ compact(item.min_stock) }}</em>
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel capacity-boundary-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">服务边界</span>
              <h2>产能微服务拆分面</h2>
            </div>
          </div>
          <div class="capacity-boundary-list">
            @for (item of data().service_boundary; track item.service) {
              <article [class.blocked]="item.readiness === 'blocked'" [class.attention]="item.readiness === 'attention'">
                <p-tag [severity]="statusSeverity(item.readiness)" [value]="levelLabel(item.readiness)" />
                <strong>{{ item.service }}</strong>
                <span>{{ item.contract }} · {{ item.owner }}</span>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel capacity-runbook-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">Runbook</span>
              <h2>计划复核运行手册</h2>
            </div>
          </div>
          <div class="capacity-runbook-list">
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
export class CapacityPlanningPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly reviewingId = signal<string | null>(null);
  protected readonly selectedCenterId = signal('');
  protected readonly chartMode = signal<'load' | 'shift' | 'supply'>('load');
  protected readonly data = signal<CapacityGovernancePayload>(EMPTY_CAPACITY);
  protected readonly selectedCenter = computed(() => {
    const centers = this.data().work_centers;
    return centers.find(item => item.id === this.selectedCenterId()) ?? centers[0] ?? null;
  });
  protected readonly selectedCenterLabel = computed(() => this.selectedCenter()?.label ?? '产能工位明细');
  protected readonly primaryBottleneck = computed(() => this.data().bottleneck_queue[0] ?? null);
  protected readonly primaryReviewId = computed(() => this.primaryBottleneck()?.id ?? this.selectedCenter()?.id ?? 'capacity-review');
  protected readonly chartTitle = computed(() => {
    if (this.chartMode() === 'shift') {
      return '班次负载节奏';
    }
    if (this.chartMode() === 'supply') {
      return '供需释放结构';
    }
    return '工位负载与小时缺口';
  });
  protected readonly activeChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'shift') {
      return this.shiftChart();
    }
    if (this.chartMode() === 'supply') {
      return this.supplyChart();
    }
    return this.loadChart();
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.get<CapacityGovernancePayload>('operations/capacity').pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '产能计划未加载', detail: error?.message || '请稍后重试。' });
        return of(EMPTY_CAPACITY);
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(payload => {
      this.data.set(payload);
      if (!payload.work_centers.some(item => item.id === this.selectedCenterId())) {
        this.selectedCenterId.set(payload.bottleneck_queue[0]?.work_center_id ?? payload.work_centers[0]?.id ?? '');
      }
    });
  }

  protected selectCenter(centerId: string): void {
    this.selectedCenterId.set(centerId);
  }

  protected createPrimaryReview(): void {
    const bottleneck = this.primaryBottleneck();
    if (bottleneck) {
      this.createBottleneckReview(bottleneck);
      return;
    }
    const center = this.selectedCenter();
    if (center) {
      this.createCenterReview(center);
    }
  }

  protected createBottleneckReview(item: CapacityBottleneckItem): void {
    this.reviewingId.set(item.id);
    this.postReview({
      item_id: item.id,
      work_center_id: item.work_center_id,
      title: item.title,
      owner: item.owner,
      priority: item.priority,
      sla: item.sla,
      evidence: item.evidence,
      action: item.action,
      path: item.path
    }, item.title);
  }

  private createCenterReview(center: CapacityWorkCenter): void {
    this.reviewingId.set(center.id);
    this.postReview({
      item_id: center.id,
      work_center_id: center.id,
      title: `${center.label}产能复核`,
      owner: center.owner,
      priority: center.priority,
      sla: center.sla,
      evidence: center.evidence,
      action: center.action,
      path: center.path
    }, center.label);
  }

  private postReview(payload: Record<string, string>, detail: string): void {
    this.api.post('operations/capacity/review', payload).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '产能复核未创建', detail: error?.message || '复核任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.reviewingId.set(null))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '产能复核已创建', detail: `${detail} 已进入任务异常中心。` });
      }
    });
  }

  private loadChart(): EChartsCoreOption {
    const centers = this.data().work_centers;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top', 'rgba(226,239,255,.82)'),
      grid: { left: 18, right: 18, top: 44, bottom: 28, containLabel: true },
      xAxis: {
        type: 'category',
        data: centers.map(item => item.label),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: 'rgba(226,239,255,.68)', fontWeight: 700, width: 86, overflow: 'truncate' }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: 'rgba(226,239,255,.58)', formatter: (value: number | string) => compactNumberText(value) },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } }
      },
      series: [
        { name: '负载', type: 'bar', data: centers.map(item => item.load), itemStyle: { color: '#14b8a6', borderRadius: [10, 10, 2, 2] } },
        { name: '需求小时', type: 'line', smooth: true, data: centers.map(item => item.required_hours), lineStyle: { color: '#60a5fa', width: 3 }, symbolSize: 8 },
        { name: '可用小时', type: 'line', smooth: true, data: centers.map(item => item.available_hours), lineStyle: { color: '#f59e0b', width: 3 }, symbolSize: 8 }
      ]
    };
  }

  private shiftChart(): EChartsCoreOption {
    const shifts = this.data().shift_plan;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 18, right: 18, top: 28, bottom: 30, containLabel: true },
      xAxis: {
        type: 'category',
        data: shifts.map(item => item.label),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: 'rgba(226,239,255,.68)', fontWeight: 800 }
      },
      yAxis: {
        type: 'value',
        max: 100,
        axisLabel: { color: 'rgba(226,239,255,.58)', formatter: '{value}%' },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } }
      },
      series: [{ type: 'bar', data: shifts.map(item => item.load), itemStyle: { color: '#3b82f6', borderRadius: [12, 12, 2, 2] }, barWidth: 42 }]
    };
  }

  private supplyChart(): EChartsCoreOption {
    const summary = this.data().summary;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom', 'rgba(226,239,255,.78)'),
      series: [compactPieSeries([
        { name: '销售需求', value: summary.demand_units },
        { name: '采购供给', value: summary.incoming_units },
        { name: '物料缺口', value: Math.max(1, summary.shortage_units) }
      ], {
        radius: ['42%', '66%'],
        center: ['50%', '42%'],
        itemStyle: { borderColor: 'rgba(15,23,42,.56)' }
      })]
    };
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
    return path.split('?')[0] || '/app/capacity';
  }

  protected statusLabel(value: string): string {
    const map: Record<string, string> = {
      pending: '待处理',
      paid: '已付款',
      shipped: '已发货',
      draft: '草稿',
      approved: '已批准',
      ordered: '已下单',
      partial: '部分到货'
    };
    return map[value] ?? value;
  }

  protected compact(value: unknown): string {
    return compactNumberText(value);
  }

  protected money(value: unknown): string {
    return compactMoneyText(value);
  }
}
