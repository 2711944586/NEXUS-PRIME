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
import { MobileTerminalLane, MobileTerminalPayload, MobileTerminalTask } from '../core/models';
import { chartLegend, compactNumberText, compactPieSeries, statusLabel, TagSeverity } from './page-utils';

const EMPTY_MOBILE: MobileTerminalPayload = {
  generated_at: '',
  source: 'mobile_terminal_governance_contract',
  summary: {
    total_tasks: 0,
    receiving: 0,
    counting: 0,
    shipping: 0,
    alerts: 0,
    p0: 0,
    p1: 0,
    completion_rate: 100,
    sync_rate: 100,
    active_devices: 0,
    primary_owner: '现场主管',
    next_action: '等待移动现场数据。'
  },
  lanes: [],
  scan_queue: [],
  device_sessions: [],
  warehouse_zones: [],
  scan_flow: [],
  runbook: [],
  service_boundary: []
};

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, RouterLink, NgxEchartsDirective, ButtonModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page mobile-terminal-page mobile-governance-page">
      <header class="atlas-split-hero mobile-terminal-hero mobile-field-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">移动现场治理</span>
          <h1>移动扫码终端</h1>
          <p>把收货、盘点、发货和库存异常压成一张现场执行队列，扫码任务回写通知、库存和审计链路。</p>
          <div class="atlas-actions-row">
            <button
              pButton
              type="button"
              (click)="createPrimaryTask()"
              [loading]="creatingId() === primaryTaskId()"
              [disabled]="loading() || !selectedTask() || creatingId() !== null"
              aria-label="创建首要现场扫码任务"
            >
              <i class="pi pi-qrcode"></i>
              创建首要任务
            </button>
            <button pButton type="button" severity="secondary" (click)="load()" [loading]="loading()" aria-label="刷新现场任务">
              <i class="pi pi-refresh"></i>
              刷新现场
            </button>
            <a pButton severity="info" routerLink="/app/stocktakes">
              <i class="pi pi-list-check"></i>
              盘点中心
            </a>
          </div>
        </div>

        <aside class="mobile-governance-stack">
          <article>
            <span>现场任务</span>
            <strong>{{ data().summary.total_tasks }}</strong>
            <em>{{ data().summary.receiving }} 收货 / {{ data().summary.counting }} 盘点 / {{ data().summary.shipping }} 发货</em>
          </article>
          <article>
            <span>设备同步</span>
            <strong>{{ data().summary.sync_rate }}%</strong>
            <em>{{ data().summary.active_devices }} 台在线 · {{ data().source }}</em>
          </article>
          <article class="warning">
            <span>P0 / P1</span>
            <strong>{{ data().summary.p0 }} / {{ data().summary.p1 }}</strong>
            <em>{{ data().summary.primary_owner }} · {{ data().summary.next_action }}</em>
          </article>
        </aside>
      </header>

      <section class="mobile-governance-grid">
        <article class="atlas-panel mobile-command-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">现场控制层</span>
              <h2>任务、设备、SLA 和扫码口令</h2>
            </div>
            <p-tag [severity]="data().summary.p0 ? 'danger' : data().summary.p1 ? 'warn' : 'success'" [value]="data().summary.p0 ? '阻塞' : data().summary.p1 ? '需复核' : '稳定'" />
          </div>

          <div class="mobile-summary-strip" aria-label="移动现场摘要">
            <article>
              <span>完成率</span>
              <strong>{{ data().summary.completion_rate }}%</strong>
              <em>收货、盘点、发货综合</em>
            </article>
            <article>
              <span>活跃设备</span>
              <strong>{{ data().summary.active_devices }}</strong>
              <em>RF / PDA / 叉车 / 平板</em>
            </article>
            <article>
              <span>异常库位</span>
              <strong>{{ data().summary.alerts }}</strong>
              <em>低水位与补货核验</em>
            </article>
            <article>
              <span>首要负责人</span>
              <strong>{{ data().summary.primary_owner }}</strong>
              <em>{{ data().summary.next_action }}</em>
            </article>
          </div>

          <nav class="governance-action-strip" aria-label="移动扫码快捷动作">
            <a routerLink="/app/procurement/orders">收货扫码</a>
            <a routerLink="/app/stocktakes">盘点录入</a>
            <a routerLink="/app/sales/orders">发货确认</a>
            <a routerLink="/app/inventory/stock">库位流水</a>
            <a routerLink="/app/dispatch">月台调度</a>
            <a routerLink="/app/files">现场附件</a>
            <button type="button" (click)="chartMode.set('zones')">库区视图</button>
          </nav>

          @if (loading()) {
            <p-skeleton height="112px" />
          } @else {
            <div class="mobile-lane-strip">
              @for (lane of data().lanes; track lane.id) {
                <button
                  type="button"
                  [class.active]="selectedLaneId() === lane.id"
                  [class.blocked]="lane.status === 'blocked'"
                  [class.attention]="lane.status === 'attention'"
                  (click)="selectLane(lane)"
                  [attr.aria-label]="'查看移动现场泳道 ' + lane.label"
                >
                  <span>{{ lane.label }} · {{ lane.owner }}</span>
                  <strong>{{ lane.active_count }} 项</strong>
                  <p-progressbar [value]="bounded(lane.progress)" [showValue]="false" />
                  <em>{{ lane.scan_target }} · {{ lane.metric }}</em>
                </button>
              }
            </div>
          }
        </article>

        <article class="atlas-panel mobile-chart-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">现场视图</span>
              <h2>{{ chartTitle() }}</h2>
            </div>
            <div class="mobile-chart-tabs">
              <button type="button" [class.active]="chartMode() === 'lanes'" (click)="chartMode.set('lanes')">泳道</button>
              <button type="button" [class.active]="chartMode() === 'devices'" (click)="chartMode.set('devices')">设备</button>
              <button type="button" [class.active]="chartMode() === 'zones'" (click)="chartMode.set('zones')">库区</button>
            </div>
          </div>
          @if (loading()) {
            <p-skeleton height="340px" />
          } @else {
            <div class="mobile-terminal-chart" echarts [options]="activeChart()"></div>
          }
        </article>

        <article class="atlas-panel mobile-queue-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">扫码队列</span>
              <h2>当班现场任务</h2>
            </div>
            <p-tag [severity]="data().scan_queue.length ? 'warn' : 'success'" [value]="data().scan_queue.length + ' 项'" />
          </div>
          @if (loading()) {
            <p-skeleton height="96px" />
            <p-skeleton height="96px" />
          } @else {
            <div class="mobile-queue-list">
              @for (task of data().scan_queue; track task.id) {
                <article
                  [class.active]="selectedTaskId() === task.id"
                  [class.p0]="task.priority === 'P0'"
                  [class.p1]="task.priority === 'P1'"
                >
                  <button type="button" class="mobile-queue-main" (click)="selectTask(task.id)" [attr.aria-label]="'选择扫码任务 ' + task.title">
                    <p-tag [severity]="prioritySeverity(task.priority)" [value]="task.priority" />
                    <div>
                      <span>{{ task.type }} · {{ task.owner }} · SLA {{ task.sla }}</span>
                      <strong>{{ task.title }}</strong>
                      <em>{{ task.evidence }}</em>
                    </div>
                    <b>{{ task.progress }}%</b>
                  </button>
                  <div class="mobile-queue-actions">
                    <a pButton [text]="true" size="small" [routerLink]="cleanPath(task.path)" [attr.aria-label]="'打开任务来源 ' + task.title">
                      <i class="pi pi-arrow-up-right"></i>
                      来源
                    </a>
                    <button
                      pButton
                      type="button"
                      size="small"
                      severity="secondary"
                      [loading]="creatingId() === task.id"
                      [disabled]="creatingId() !== null"
                      (click)="createQueueTask(task)"
                      [attr.aria-label]="'创建现场任务 ' + task.title"
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

        <article class="atlas-panel mobile-selected-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">当前扫码</span>
              <h2>{{ selectedTask()?.type || '现场任务' }}</h2>
            </div>
            @if (selectedTask()) {
              <p-tag [severity]="statusSeverity(selectedTask()!.readiness)" [value]="selectedTask()!.scan_code" />
            }
          </div>
          @if (selectedTask(); as task) {
            <div class="mobile-scan-card">
              <div class="scan-code-block">
                <span>扫码口令</span>
                <strong>{{ task.scan_code }}</strong>
                <em>{{ task.warehouse }} · {{ task.location }}</em>
              </div>
              <p-progressbar [value]="bounded(task.progress)" [showValue]="false" />
              <p>{{ task.next_action }}</p>
              <div class="mobile-checklist">
                @for (item of task.checklist; track item) {
                  <span><i class="pi pi-check-circle"></i>{{ item }}</span>
                }
              </div>
            </div>
          } @else {
            <div class="empty-state compact">
              <i class="pi pi-qrcode"></i>
              <strong>暂无扫码任务</strong>
              <p>刷新后可查看收货、盘点、发货或异常队列。</p>
            </div>
          }
        </article>

        <article class="atlas-panel mobile-device-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">设备会话</span>
              <h2>RF、PDA 和叉车终端</h2>
            </div>
          </div>
          <div class="mobile-device-grid">
            @for (device of data().device_sessions; track device.id) {
              <article [class.attention]="device.status === 'attention'" [class.blocked]="device.status === 'blocked'">
                <p-tag [severity]="statusSeverity(device.status)" [value]="device.id" />
                <strong>{{ device.label }}</strong>
                <span>{{ device.owner }} · {{ device.zone }}</span>
                <div>
                  <em>任务 {{ device.task_count }}</em>
                  <em>电量 {{ device.battery }}%</em>
                  <em>同步 {{ device.sync_latency_ms }}ms</em>
                </div>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel mobile-zone-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">库区热区</span>
              <h2>扫码覆盖库区</h2>
            </div>
          </div>
          <div class="mobile-zone-list">
            @for (zone of data().warehouse_zones; track zone.id) {
              <article [class.attention]="zone.status === 'attention'" [class.blocked]="zone.status === 'blocked'">
                <div>
                  <strong>{{ zone.label }}</strong>
                  <span>{{ zone.location }} · {{ zone.slot_count }} 个库位</span>
                </div>
                <b>{{ zone.utilization }}%</b>
                <p-progressbar [value]="bounded(zone.utilization)" [showValue]="false" />
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel mobile-flow-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">闭环链路</span>
              <h2>扫码到审计</h2>
            </div>
          </div>
          <div class="mobile-flow-list">
            @for (item of data().scan_flow; track item.step; let index = $index) {
              <article>
                <i>{{ index + 1 }}</i>
                <div>
                  <strong>{{ item.step }}</strong>
                  <span>{{ item.detail }}</span>
                </div>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel mobile-boundary-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">服务边界</span>
              <h2>移动端微服务拆分面</h2>
            </div>
          </div>
          <div class="mobile-boundary-list">
            @for (item of data().service_boundary; track item.service) {
              <article [class.attention]="item.readiness === 'attention'" [class.blocked]="item.readiness === 'blocked'">
                <p-tag [severity]="statusSeverity(item.readiness)" [value]="levelLabel(item.readiness)" />
                <strong>{{ item.service }}</strong>
                <span>{{ item.contract }} · {{ item.owner }}</span>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel mobile-runbook-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">Runbook</span>
              <h2>现场执行手册</h2>
            </div>
          </div>
          <div class="mobile-runbook-list">
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
export class MobileTerminalPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly creatingId = signal<string | null>(null);
  protected readonly data = signal<MobileTerminalPayload>(EMPTY_MOBILE);
  protected readonly selectedLaneId = signal('receiving');
  protected readonly selectedTaskId = signal('');
  protected readonly chartMode = signal<'lanes' | 'devices' | 'zones'>('lanes');
  protected readonly selectedTask = computed<MobileTerminalTask | null>(() => {
    const tasks = this.data().scan_queue;
    return tasks.find(item => item.id === this.selectedTaskId()) ?? tasks[0] ?? null;
  });
  protected readonly primaryTaskId = computed(() => this.selectedTask()?.id ?? 'mobile-task');
  protected readonly chartTitle = computed(() => {
    if (this.chartMode() === 'devices') {
      return '设备电量与任务负载';
    }
    if (this.chartMode() === 'zones') {
      return '库区利用与扫码覆盖';
    }
    return '现场任务泳道';
  });
  protected readonly activeChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'devices') {
      return this.deviceChart();
    }
    if (this.chartMode() === 'zones') {
      return this.zoneChart();
    }
    return this.laneChart();
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.get<MobileTerminalPayload>('operations/mobile-terminal').pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '移动现场未加载', detail: error?.message || '请稍后重试。' });
        return of(EMPTY_MOBILE);
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(payload => {
      this.data.set(payload);
      if (!payload.scan_queue.some(item => item.id === this.selectedTaskId())) {
        this.selectedTaskId.set(payload.scan_queue[0]?.id ?? '');
      }
      if (!payload.lanes.some(item => item.id === this.selectedLaneId())) {
        this.selectedLaneId.set(payload.lanes[0]?.id ?? 'receiving');
      }
    });
  }

  protected selectLane(lane: MobileTerminalLane): void {
    this.selectedLaneId.set(lane.id);
    const typeMap: Record<string, string> = {
      receiving: '收货',
      counting: '盘点',
      shipping: '发货',
      exceptions: '预警'
    };
    const first = this.data().scan_queue.find(item => item.type === typeMap[lane.id]);
    if (first) {
      this.selectedTaskId.set(first.id);
    }
  }

  protected selectTask(taskId: string): void {
    this.selectedTaskId.set(taskId);
  }

  protected createPrimaryTask(): void {
    const task = this.selectedTask();
    if (task) {
      this.createQueueTask(task);
    }
  }

  protected createQueueTask(task: MobileTerminalTask): void {
    this.creatingId.set(task.id);
    this.api.post('operations/mobile-terminal/task', {
      queue_item_id: task.id,
      task_type: task.type,
      title: task.title,
      owner: task.owner,
      priority: task.priority,
      sla: task.sla,
      evidence: task.evidence,
      next_action: task.next_action,
      path: task.path
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '现场任务未创建', detail: error?.message || '扫码任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.creatingId.set(null))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '现场任务已创建', detail: `${task.title} 已进入任务异常中心。` });
      }
    });
  }

  private laneChart(): EChartsCoreOption {
    const lanes = this.data().lanes;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top', 'rgba(226,239,255,.82)'),
      grid: { left: 18, right: 18, top: 44, bottom: 32, containLabel: true },
      xAxis: {
        type: 'category',
        data: lanes.map(item => item.label),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: 'rgba(226,239,255,.7)', fontWeight: 800, width: 86, overflow: 'truncate' }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: 'rgba(226,239,255,.58)' },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } }
      },
      series: [
        { name: '任务数', type: 'bar', data: lanes.map(item => item.active_count), itemStyle: { color: '#14b8a6', borderRadius: [10, 10, 2, 2] } },
        { name: '完成率', type: 'line', smooth: true, data: lanes.map(item => item.progress), lineStyle: { color: '#60a5fa', width: 3 }, symbolSize: 8 }
      ]
    };
  }

  private deviceChart(): EChartsCoreOption {
    const devices = this.data().device_sessions;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top', 'rgba(226,239,255,.82)'),
      grid: { left: 18, right: 18, top: 44, bottom: 32, containLabel: true },
      xAxis: {
        type: 'category',
        data: devices.map(item => item.id),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: 'rgba(226,239,255,.7)', fontWeight: 800 }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: 'rgba(226,239,255,.58)' },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } }
      },
      series: [
        { name: '电量', type: 'bar', data: devices.map(item => item.battery), itemStyle: { color: '#f59e0b', borderRadius: [10, 10, 2, 2] } },
        { name: '任务', type: 'line', smooth: true, data: devices.map(item => item.task_count), lineStyle: { color: '#22d3ee', width: 3 }, symbolSize: 8 }
      ]
    };
  }

  private zoneChart(): EChartsCoreOption {
    const zones = this.data().warehouse_zones;
    if (zones.length) {
      return {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { left: 18, right: 18, top: 28, bottom: 32, containLabel: true },
        xAxis: {
          type: 'category',
          data: zones.map(item => item.label),
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: 'rgba(226,239,255,.7)', fontWeight: 800, width: 86, overflow: 'truncate' }
        },
        yAxis: {
          type: 'value',
          max: 100,
          axisLabel: { color: 'rgba(226,239,255,.58)', formatter: '{value}%' },
          splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } }
        },
        series: [{ type: 'bar', data: zones.map(item => item.utilization), itemStyle: { color: '#3b82f6', borderRadius: [10, 10, 2, 2] } }]
      };
    }
    const summary = this.data().summary;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom', 'rgba(226,239,255,.78)'),
      series: [compactPieSeries([
        { name: '收货', value: summary.receiving },
        { name: '盘点', value: summary.counting },
        { name: '发货', value: summary.shipping },
        { name: '预警', value: summary.alerts }
      ], { radius: ['42%', '66%'], center: ['50%', '42%'], itemStyle: { borderColor: 'rgba(15,23,42,.56)' } })]
    };
  }

  protected statusSeverity(status: string): TagSeverity {
    if (status === 'ready') {
      return 'success';
    }
    if (status === 'blocked') {
      return 'danger';
    }
    if (status === 'offline') {
      return 'secondary';
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
      blocked: '阻塞',
      offline: '离线'
    };
    return map[status] ?? status;
  }

  protected bounded(value: number): number {
    return Math.max(0, Math.min(100, Math.round(Number(value || 0))));
  }

  protected compact(value: unknown): string {
    return compactNumberText(value);
  }

  protected statusLabel(value: unknown): string {
    return statusLabel(value);
  }

  protected cleanPath(path: string): string {
    return path.split('?')[0] || '/app/mobile-terminal';
  }
}
