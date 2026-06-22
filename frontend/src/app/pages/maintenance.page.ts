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
import { MaintenanceAssetLine, MaintenanceReliabilityPayload, MaintenanceWorkorderItem } from '../core/models';
import { chartLegend, compactNumberText, TagSeverity } from './page-utils';

const EMPTY_MAINTENANCE: MaintenanceReliabilityPayload = {
  generated_at: '',
  source: 'maintenance_reliability_contract',
  summary: {
    health_score: 0,
    spare_parts: 0,
    low_spares: 0,
    active_alerts: 0,
    red_alerts: 0,
    documents: 0,
    audit_events: 0,
    open_workorders: 0,
    p0: 0,
    p1: 0,
    queue_count: 0,
    primary_owner: '设备主管',
    next_action: '等待设备可靠性数据。'
  },
  asset_lines: [],
  workorder_queue: [],
  spare_parts: [],
  technician_roster: [],
  downtime_windows: [],
  documents: [],
  maintenance_flow: [],
  runbook: [],
  service_boundary: []
};

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, RouterLink, NgxEchartsDirective, ButtonModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page maintenance-page maintenance-reliability-page">
      <header class="maintenance-hero maintenance-reliability-hero atlas-split-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">设备可靠性治理</span>
          <h1>设备维护中心</h1>
          <p>把 MRO 备件、库存预警、维护资料、库位审计和停机窗口合并为可派发的可靠性工单。</p>
          <div class="atlas-actions-row">
            <button
              pButton
              type="button"
              (click)="createPrimaryWorkorder()"
              [loading]="creatingId() === primaryWorkorderId()"
              [disabled]="loading() || !selectedWorkorder() || creatingId() !== null"
              aria-label="创建首要设备维护工单"
            >
              <i class="pi pi-wrench"></i>
              创建首要工单
            </button>
            <button pButton type="button" severity="secondary" (click)="load()" [loading]="loading()" aria-label="刷新设备可靠性数据">
              <i class="pi pi-refresh"></i>
              刷新可靠性
            </button>
            <a pButton severity="info" routerLink="/app/reports">
              <i class="pi pi-chart-line"></i>
              维护报表
            </a>
          </div>
        </div>

        <aside class="maintenance-reliability-stack">
          <article>
            <span>可靠性评分</span>
            <strong>{{ data().summary.health_score }}%</strong>
            <em>{{ data().summary.low_spares }} 项低水位 · {{ data().summary.active_alerts }} 条预警</em>
          </article>
          <article>
            <span>首要负责人</span>
            <strong>{{ data().summary.primary_owner }}</strong>
            <em>{{ data().summary.next_action }}</em>
          </article>
          <article class="warning">
            <span>P0 / P1</span>
            <strong>{{ data().summary.p0 }} / {{ data().summary.p1 }}</strong>
            <em>{{ data().summary.queue_count }} 个工单候选 · {{ data().summary.open_workorders }} 个未闭环</em>
          </article>
        </aside>
      </header>

      <section class="maintenance-reliability-grid">
        <article class="atlas-panel maintenance-command-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">可靠性控制层</span>
              <h2>资产线、备件、资料和停机风险</h2>
            </div>
            <p-tag [severity]="data().summary.p0 ? 'danger' : data().summary.queue_count ? 'warn' : 'success'" [value]="data().summary.p0 ? '阻塞' : data().summary.queue_count ? '需派工' : '稳定'" />
          </div>

          <div class="maintenance-summary-strip" aria-label="设备可靠性摘要">
            <article>
              <span>MRO 备件</span>
              <strong>{{ data().summary.spare_parts }}</strong>
              <em>{{ data().summary.low_spares }} 项低于保障线</em>
            </article>
            <article>
              <span>维护资料</span>
              <strong>{{ data().summary.documents }}</strong>
              <em>SOP、点检表、图纸</em>
            </article>
            <article>
              <span>红色预警</span>
              <strong>{{ data().summary.red_alerts }}</strong>
              <em>优先锁定停机窗口</em>
            </article>
            <article>
              <span>库存审计</span>
              <strong>{{ compact(data().summary.audit_events) }}</strong>
              <em>{{ data().source }}</em>
            </article>
          </div>

          @if (loading()) {
            <p-skeleton height="126px" />
          } @else {
            <div class="maintenance-line-strip">
              @for (line of data().asset_lines; track line.id) {
                <button
                  type="button"
                  [class.active]="selectedLineId() === line.id"
                  [class.blocked]="line.status === 'blocked'"
                  [class.attention]="line.status === 'attention'"
                  (click)="selectLine(line)"
                  [attr.aria-label]="'查看资产线 ' + line.label"
                >
                  <span>{{ line.label }} · {{ line.owner }}</span>
                  <strong>{{ line.health }}%</strong>
                  <p-progressbar [value]="bounded(line.health)" [showValue]="false" />
                  <em>{{ line.risk_hours }}h 风险窗口 · SLA {{ line.sla }}</em>
                </button>
              }
            </div>
          }
        </article>

        <article class="atlas-panel maintenance-chart-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">可靠性视图</span>
              <h2>{{ chartTitle() }}</h2>
            </div>
            <div class="maintenance-chart-tabs">
              <button type="button" [class.active]="chartMode() === 'health'" (click)="chartMode.set('health')">健康</button>
              <button type="button" [class.active]="chartMode() === 'technicians'" (click)="chartMode.set('technicians')">人员</button>
              <button type="button" [class.active]="chartMode() === 'downtime'" (click)="chartMode.set('downtime')">停机</button>
            </div>
          </div>
          @if (loading()) {
            <p-skeleton height="340px" />
          } @else {
            <div class="maintenance-chart" echarts [options]="activeChart()"></div>
          }
        </article>

        <article class="atlas-panel maintenance-workorder-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">工单队列</span>
              <h2>可靠性派工</h2>
            </div>
            <p-tag [severity]="data().workorder_queue.length ? 'warn' : 'success'" [value]="data().workorder_queue.length + ' 项'" />
          </div>
          @if (loading()) {
            <p-skeleton height="94px" />
            <p-skeleton height="94px" />
          } @else {
            <div class="maintenance-workorder-list">
              @for (item of data().workorder_queue; track item.id) {
                <article [class.active]="selectedWorkorderId() === item.id" [class.p0]="item.priority === 'P0'" [class.p1]="item.priority === 'P1'">
                  <button type="button" class="maintenance-workorder-main" (click)="selectWorkorder(item.id)" [attr.aria-label]="'选择维护工单 ' + item.title">
                    <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
                    <div>
                      <span>{{ item.asset }} · {{ item.owner }} · SLA {{ item.sla }}</span>
                      <strong>{{ item.title }}</strong>
                      <em>{{ item.evidence }}</em>
                    </div>
                    <b>{{ item.risk_score }}%</b>
                  </button>
                  <div class="maintenance-workorder-actions">
                    <a pButton [text]="true" size="small" [routerLink]="cleanPath(item.path)" [attr.aria-label]="'打开维护来源 ' + item.title">
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
                      (click)="createWorkorder(item)"
                      [attr.aria-label]="'创建设备维护工单 ' + item.title"
                    >
                      <i class="pi pi-send"></i>
                      创建工单
                    </button>
                  </div>
                </article>
              }
            </div>
          }
        </article>

        <article class="atlas-panel maintenance-selected-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">当前工单</span>
              <h2>{{ selectedWorkorder()?.asset || '设备维护' }}</h2>
            </div>
            @if (selectedWorkorder()) {
              <p-tag [severity]="prioritySeverity(selectedWorkorder()!.priority)" [value]="selectedWorkorder()!.priority" />
            }
          </div>
          @if (selectedWorkorder(); as item) {
            <div class="maintenance-selected-card">
              <div class="maintenance-risk-code">
                <span>{{ item.line }}</span>
                <strong>{{ item.part_name }}</strong>
                <em>{{ item.owner }} · {{ item.sla }} · 风险 {{ item.risk_score }}%</em>
              </div>
              <p-progressbar [value]="bounded(item.risk_score)" [showValue]="false" />
              <p>{{ item.action }}</p>
              <div class="maintenance-checklist">
                @for (step of item.checklist; track step) {
                  <span><i class="pi pi-check-circle"></i>{{ step }}</span>
                }
              </div>
            </div>
          }
        </article>

        <article class="atlas-panel maintenance-spares-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">备件保障</span>
              <h2>MRO 关键备件</h2>
            </div>
          </div>
          <div class="maintenance-spare-list">
            @for (part of data().spare_parts.slice(0, 10); track part.id) {
              <a [routerLink]="cleanPath(part.path)" [class.blocked]="part.status === 'blocked'" [class.attention]="part.status === 'attention'">
                <div>
                  <span>{{ part.sku }} · {{ part.category }}</span>
                  <strong>{{ part.name }}</strong>
                  <em>{{ part.supplier }} · {{ part.location }}</em>
                </div>
                <b>{{ part.coverage }}%</b>
                <p-progressbar [value]="bounded(part.coverage)" [showValue]="false" />
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel maintenance-technician-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">维修班组</span>
              <h2>人员负载</h2>
            </div>
          </div>
          <div class="maintenance-technician-grid">
            @for (tech of data().technician_roster; track tech.id) {
              <article [class.blocked]="tech.status === 'blocked'" [class.attention]="tech.status === 'attention'">
                <div>
                  <strong>{{ tech.name }}</strong>
                  <p-tag [severity]="statusSeverity(tech.status)" [value]="levelLabel(tech.status)" />
                </div>
                <span>{{ tech.role }} · {{ tech.task_count }} 项</span>
                <p-progressbar [value]="bounded(tech.load)" [showValue]="false" />
                <em>{{ tech.focus }}</em>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel maintenance-window-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">停机窗口</span>
              <h2>维修窗口安排</h2>
            </div>
          </div>
          <div class="maintenance-window-list">
            @for (item of data().downtime_windows; track item.id) {
              <article [class.blocked]="item.status === 'blocked'" [class.attention]="item.status === 'attention'">
                <span>{{ item.window }} · {{ item.owner }}</span>
                <strong>{{ item.label }}</strong>
                <em>{{ item.risk_hours }}h 风险 · {{ item.evidence }}</em>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel maintenance-boundary-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">服务边界</span>
              <h2>设备微服务拆分面</h2>
            </div>
          </div>
          <div class="maintenance-boundary-list">
            @for (item of data().service_boundary; track item.service) {
              <article [class.blocked]="item.readiness === 'blocked'" [class.attention]="item.readiness === 'attention'">
                <p-tag [severity]="statusSeverity(item.readiness)" [value]="levelLabel(item.readiness)" />
                <strong>{{ item.service }}</strong>
                <span>{{ item.contract }} · {{ item.owner }}</span>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel maintenance-flow-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">流程</span>
              <h2>从点检到审计</h2>
            </div>
          </div>
          <div class="maintenance-flow-list">
            @for (item of data().maintenance_flow; track item.step) {
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

        <article class="atlas-panel maintenance-runbook-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">Runbook</span>
              <h2>可靠性复核手册</h2>
            </div>
          </div>
          <div class="maintenance-runbook-list">
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
export class MaintenancePage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly creatingId = signal<string | null>(null);
  protected readonly selectedLineId = signal('');
  protected readonly selectedWorkorderId = signal('');
  protected readonly chartMode = signal<'health' | 'technicians' | 'downtime'>('health');
  protected readonly data = signal<MaintenanceReliabilityPayload>(EMPTY_MAINTENANCE);
  protected readonly selectedLine = computed<MaintenanceAssetLine | null>(() => {
    const lines = this.data().asset_lines;
    return lines.find(item => item.id === this.selectedLineId()) ?? lines[0] ?? null;
  });
  protected readonly selectedWorkorder = computed<MaintenanceWorkorderItem | null>(() => {
    const queue = this.data().workorder_queue;
    return queue.find(item => item.id === this.selectedWorkorderId()) ?? queue[0] ?? null;
  });
  protected readonly primaryWorkorder = computed<MaintenanceWorkorderItem | null>(() => this.data().workorder_queue[0] ?? null);
  protected readonly primaryWorkorderId = computed(() => this.primaryWorkorder()?.id ?? this.selectedWorkorder()?.id ?? 'maintenance-workorder');
  protected readonly chartTitle = computed(() => {
    if (this.chartMode() === 'technicians') {
      return '维修人员负载';
    }
    if (this.chartMode() === 'downtime') {
      return '停机窗口风险';
    }
    return '资产线可靠性';
  });
  protected readonly activeChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'technicians') {
      return this.technicianChart();
    }
    if (this.chartMode() === 'downtime') {
      return this.downtimeChart();
    }
    return this.healthChart();
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.get<MaintenanceReliabilityPayload>('operations/maintenance').pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '设备可靠性未加载', detail: error?.message || '请稍后重试。' });
        return of(EMPTY_MAINTENANCE);
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(payload => {
      this.data.set(payload);
      if (!payload.asset_lines.some(item => item.id === this.selectedLineId())) {
        this.selectedLineId.set(payload.asset_lines[0]?.id ?? '');
      }
      if (!payload.workorder_queue.some(item => item.id === this.selectedWorkorderId())) {
        this.selectedWorkorderId.set(payload.workorder_queue[0]?.id ?? '');
      }
    });
  }

  protected selectLine(line: MaintenanceAssetLine): void {
    this.selectedLineId.set(line.id);
    const matching = this.data().workorder_queue.find(item => item.asset === line.label || item.line === line.label);
    if (matching) {
      this.selectedWorkorderId.set(matching.id);
    }
  }

  protected selectWorkorder(id: string): void {
    this.selectedWorkorderId.set(id);
  }

  protected createPrimaryWorkorder(): void {
    const item = this.primaryWorkorder() ?? this.selectedWorkorder();
    if (item) {
      this.createWorkorder(item);
    }
  }

  protected createWorkorder(item: MaintenanceWorkorderItem): void {
    this.creatingId.set(item.id);
    this.api.post('operations/maintenance-workorder', {
      queue_item_id: item.id,
      product_id: item.product_id,
      title: item.title,
      owner: item.owner,
      priority: item.priority,
      sla: item.sla,
      evidence: item.evidence,
      action: item.action,
      path: item.path
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '维护工单未创建', detail: error?.message || '工单任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.creatingId.set(null))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '维护工单已创建', detail: `${item.title} 已进入任务异常中心。` });
      }
    });
  }

  private healthChart(): EChartsCoreOption {
    const lines = this.data().asset_lines;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top', 'rgba(226,239,255,.82)'),
      grid: { left: 18, right: 18, top: 44, bottom: 28, containLabel: true },
      xAxis: {
        type: 'category',
        data: lines.map(item => item.label),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: 'rgba(226,239,255,.7)', fontWeight: 800, width: 92, overflow: 'truncate' }
      },
      yAxis: {
        type: 'value',
        max: 100,
        axisLabel: { color: 'rgba(226,239,255,.58)', formatter: (value: number | string) => compactNumberText(value) },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } }
      },
      series: [
        { name: '健康', type: 'bar', data: lines.map(item => item.health), barWidth: 28, itemStyle: { color: '#14b8a6', borderRadius: [10, 10, 3, 3] } },
        { name: '风险小时', type: 'line', smooth: true, data: lines.map(item => item.risk_hours * 10), lineStyle: { color: '#f59e0b', width: 3 }, symbolSize: 8 }
      ]
    };
  }

  private technicianChart(): EChartsCoreOption {
    const rows = this.data().technician_roster;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top', 'rgba(226,239,255,.82)'),
      grid: { left: 18, right: 18, top: 44, bottom: 28, containLabel: true },
      xAxis: { type: 'category', data: rows.map(item => item.name), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: 'rgba(226,239,255,.7)', fontWeight: 800 } },
      yAxis: { type: 'value', axisLabel: { color: 'rgba(226,239,255,.58)' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } } },
      series: [
        { name: '负载', type: 'bar', data: rows.map(item => item.load), barWidth: 24, itemStyle: { color: '#3b82f6', borderRadius: [10, 10, 3, 3] } },
        { name: '任务', type: 'line', smooth: true, data: rows.map(item => item.task_count), lineStyle: { color: '#22d3ee', width: 3 }, symbolSize: 8 }
      ]
    };
  }

  private downtimeChart(): EChartsCoreOption {
    const rows = this.data().downtime_windows;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom', 'rgba(226,239,255,.82)'),
      series: [{
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '42%'],
        minAngle: 5,
        itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(15,23,42,.8)' },
        label: { color: 'rgba(226,239,255,.78)', formatter: '{b}\\n{d}%' },
        data: rows.map(item => ({ name: item.label, value: Math.max(1, item.risk_hours) }))
      }]
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

  protected cleanPath(path?: string): string {
    return path?.startsWith('/app') ? path : '/app/maintenance';
  }
}
