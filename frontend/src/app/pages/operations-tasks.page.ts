import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, forkJoin, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DataRecord, ExecutiveAnalytics, OperationsExceptionItem, OperationsExceptionsPayload, OperationsTaskQueueItem, OperationsTaskQueuePayload, OperationsTodoPayload } from '../core/models';
import { streamWorkflowTodo, WorkflowTodoSnapshot } from '../core/workflow-todo-stream';
import { chartLegend, compactNumberText, EMPTY_TODO } from './page-utils';

const WORKFLOW_TODO_RECONNECT_MS = 3000;

const EMPTY_EXCEPTIONS: OperationsExceptionsPayload = { items: [], total: 0 };
const EMPTY_TASK_QUEUE: OperationsTaskQueuePayload = {
  summary: {
    total: 0,
    open_notifications: 0,
    deployment_attention: 0,
    business_exceptions: 0,
    p0: 0,
    p1: 0,
    p2: 0,
    generated_at: '',
    next_action: '当前没有待处理任务。'
  },
  items: []
};
const EMPTY_ANALYTICS: ExecutiveAnalytics = {
  kpis: { total_sales: 0, unpaid_amount: 0, pending_purchase: 0, active_alerts: 0, collaboration_items: 0 },
  sales_trend: [],
  risk_mix: [],
  collaboration: [],
  top_customers: [],
  procurement_stages: [],
  aging_buckets: [],
  warehouse_turnover: [],
  supplier_score: [],
  inventory_risk_rank: [],
  order_status_flow: [],
  cash_collection_trend: [],
  action_queue: [],
  operational_efficiency: [],
  module_throughput: []
};

@Component({
  standalone: true,
  imports: [CommonModule, RouterLink, NgxEchartsDirective, ButtonModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page operations-task-page">
      <header class="operations-task-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">任务中心</span>
          <h1>任务异常中心</h1>
          <p>库存预警、采购审批、应收逾期和通知待办统一进入任务队列。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="createTask()" [loading]="taskCreating()" aria-label="创建异常复核任务">
              <i class="pi pi-flag"></i>
              创建复核任务
            </button>
            <button pButton type="button" severity="secondary" (click)="refreshAlerts()" [loading]="alertChecking()" aria-label="刷新库存预警">
              <i class="pi pi-refresh"></i>
              刷新预警
            </button>
            <a pButton severity="info" routerLink="/app/notifications">
              <i class="pi pi-bell"></i>
              通知中心
            </a>
          </div>
        </div>

        <aside class="task-hero-metrics">
          <article>
            <span>任务总数</span>
            <strong>{{ todoTotal() + exceptions().items.length }}</strong>
            <em>待办与异常</em>
          </article>
          <article class="warning">
            <span>高优先</span>
            <strong>{{ highPriorityCount() }}</strong>
            <em>需要当班处理</em>
          </article>
          <article>
            <span>库存量</span>
            <strong>{{ compactNumber(todo().stock_quantity) }}</strong>
            <em>实时库存合计</em>
          </article>
        </aside>
      </header>

      <section class="task-grid">
        <article class="atlas-panel task-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">队列</span>
              <h2>待办分布</h2>
            </div>
            <button pButton type="button" [text]="true" (click)="load()" aria-label="刷新任务中心">
              <i class="pi pi-refresh"></i>
            </button>
          </div>
          @if (loading()) {
            <p-skeleton height="320px" />
          } @else {
            <div class="task-chart" echarts [options]="todoChart()"></div>
          }
        </article>

        <article class="atlas-panel task-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">模块负载</span>
              <h2>模块负载</h2>
            </div>
            <p-tag severity="info" value="可交互" />
          </div>
          <div class="task-chart" echarts [options]="moduleLoadChart()"></div>
        </article>

        <article class="atlas-panel task-command-queue wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">当班任务</span>
              <h2>当班任务队列</h2>
            </div>
            <p-tag [severity]="taskQueue().summary.p0 ? 'danger' : taskQueue().summary.total ? 'warn' : 'success'" [value]="taskQueue().summary.total + ' 项'" />
          </div>
          <div class="task-queue-summary" aria-label="任务队列摘要">
            <article>
              <span>P0</span>
              <strong>{{ taskQueue().summary.p0 }}</strong>
            </article>
            <article>
              <span>P1</span>
              <strong>{{ taskQueue().summary.p1 }}</strong>
            </article>
            <article>
              <span>通知</span>
              <strong>{{ taskQueue().summary.open_notifications }}</strong>
            </article>
            <article>
              <span>部署</span>
              <strong>{{ taskQueue().summary.deployment_attention }}</strong>
            </article>
          </div>
          <p>{{ taskQueue().summary.next_action }}</p>
          @if (loading()) {
            <p-skeleton height="84px" />
            <p-skeleton height="84px" />
          } @else if (!taskQueue().items.length) {
            <div class="lane-empty">当前没有待处理任务</div>
          } @else {
            <div class="task-queue-stack">
              @for (item of taskQueue().items.slice(0, 12); track item.id) {
                <article class="task-queue-card" [class.p0]="item.priority === 'P0'" [class.p1]="item.priority === 'P1'">
                  <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
                  <div>
                    <span>{{ sourceLabel(item.source) }} · {{ item.owner }}</span>
                    <strong>{{ item.title }}</strong>
                    <em>{{ item.description }}</em>
                  </div>
                  <div class="task-queue-actions">
                    <a pButton [text]="true" size="small" [routerLink]="cleanPath(item.source_path)" [attr.aria-label]="'查看来源 ' + item.title">
                      <i class="pi pi-arrow-up-right"></i>
                      来源
                    </a>
                    @if (item.action_kind === 'complete_notification') {
                      <button pButton type="button" size="small" severity="success" [loading]="queueCompletingId() === item.id" [disabled]="queueBusy()" (click)="completeQueueTask(item)" [attr.aria-label]="'处理完成 ' + item.title">
                        <i class="pi pi-check"></i>
                        处理完成
                      </button>
                    } @else if (item.action_kind === 'create_deployment_task') {
                      <button pButton type="button" size="small" severity="secondary" [loading]="queueCreatingId() === item.id" [disabled]="queueBusy()" (click)="createDeploymentQueueTask(item)" [attr.aria-label]="'创建预检任务 ' + item.title">
                        <i class="pi pi-send"></i>
                        创建任务
                      </button>
                    } @else if (item.source === 'workflow') {
                      <button pButton type="button" size="small" severity="success" [loading]="queueWorkflowActionId() === item.id + ':approve'" [disabled]="queueBusy() || !item.source_id" (click)="approveWorkflowQueueTask(item)" [attr.aria-label]="'审批通过 ' + item.title">
                        <i class="pi pi-check"></i>
                        通过
                      </button>
                      <button pButton type="button" size="small" severity="danger" [loading]="queueWorkflowActionId() === item.id + ':reject'" [disabled]="queueBusy() || !item.source_id" (click)="rejectWorkflowQueueTask(item)" [attr.aria-label]="'审批驳回 ' + item.title">
                        <i class="pi pi-times"></i>
                        驳回
                      </button>
                    } @else {
                      <a pButton size="small" severity="secondary" [routerLink]="cleanPath(item.detail_path)">
                        {{ item.action_label }}
                      </a>
                    }
                  </div>
                </article>
              }
            </div>
          }
        </article>

        <article class="atlas-panel task-lane-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">异常泳道</span>
              <h2>异常处理泳道</h2>
            </div>
            <p-tag [severity]="highPriorityCount() ? 'warn' : 'success'" [value]="highPriorityCount() ? '需要处理' : '稳定'" />
          </div>

          <div class="exception-lanes">
            @for (lane of lanes(); track lane.key) {
              <section>
                <div class="lane-head">
                  <span>{{ lane.label }}</span>
                  <strong>{{ lane.items.length }}</strong>
                </div>
                @for (item of lane.items.slice(0, 5); track item.title + item.path) {
                  <a [routerLink]="cleanPath(item.path)" [class.critical]="item.level === '高'">
                    <p-tag [severity]="item.level === '高' ? 'danger' : item.level === '中' ? 'warn' : 'info'" [value]="item.level" />
                    <strong>{{ item.title }}</strong>
                    <span>{{ item.description }}</span>
                  </a>
                }
                @if (!lane.items.length) {
                  <div class="lane-empty">当前无阻塞任务</div>
                }
              </section>
            }
          </div>
        </article>

        <aside class="atlas-panel task-action-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">待办</span>
              <h2>快速处理</h2>
            </div>
          </div>
          <div class="task-action-list">
            @for (item of todo().items; track item.label) {
              <a [routerLink]="cleanPath(item.path)" [class.warning]="item.value > 0">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </a>
            }
            <a routerLink="/app/ai">
              <span>经营分析</span>
              <strong>诊断</strong>
            </a>
          </div>
        </aside>
      </section>
    </section>
  `
})
export class OperationsTasksPage implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly taskCreating = signal(false);
  protected readonly alertChecking = signal(false);
  protected readonly queueCompletingId = signal('');
  protected readonly queueCreatingId = signal('');
  protected readonly queueWorkflowActionId = signal('');
  protected readonly todo = signal<OperationsTodoPayload>(EMPTY_TODO);
  protected readonly exceptions = signal<OperationsExceptionsPayload>(EMPTY_EXCEPTIONS);
  protected readonly taskQueue = signal<OperationsTaskQueuePayload>(EMPTY_TASK_QUEUE);
  protected readonly analytics = signal<ExecutiveAnalytics>(EMPTY_ANALYTICS);
  private workflowTodoAbort?: AbortController;
  private workflowTodoReconnectTimer?: ReturnType<typeof setTimeout>;
  private workflowTodoDestroyed = false;
  protected readonly todoTotal = computed(() => this.todo().items.reduce((sum, item) => sum + Number(item.value || 0), 0));
  protected readonly highPriorityCount = computed(() => this.exceptions().items.filter(item => item.level === '高').length);
  protected readonly queueBusy = computed(() => Boolean(this.queueCompletingId() || this.queueCreatingId() || this.queueWorkflowActionId()));
  protected readonly lanes = computed(() => {
    const map = new Map<string, { key: string; label: string; items: OperationsExceptionItem[] }>();
    for (const item of this.exceptions().items) {
      const key = item.type || '其他';
      const lane = map.get(key) ?? { key, label: key, items: [] };
      lane.items.push(item);
      map.set(key, lane);
    }
    return [...map.values()].sort((a, b) => b.items.length - a.items.length);
  });

  ngOnInit(): void {
    this.workflowTodoDestroyed = false;
    this.load();
    this.startWorkflowTodoStream();
  }

  ngOnDestroy(): void {
    this.workflowTodoDestroyed = true;
    if (this.workflowTodoReconnectTimer) {
      clearTimeout(this.workflowTodoReconnectTimer);
    }
    this.workflowTodoAbort?.abort();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      todo: this.api.get<OperationsTodoPayload>('operations/todo').pipe(catchError(() => of(EMPTY_TODO))),
      exceptions: this.api.get<OperationsExceptionsPayload>('operations/exceptions').pipe(catchError(() => of(EMPTY_EXCEPTIONS))),
      taskQueue: this.api.get<OperationsTaskQueuePayload>('operations/task-queue').pipe(catchError(() => of(EMPTY_TASK_QUEUE))),
      analytics: this.api.get<ExecutiveAnalytics>('analytics/executive').pipe(catchError(() => of(EMPTY_ANALYTICS)))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(({ todo, exceptions, taskQueue, analytics }) => {
      this.todo.set(todo);
      this.exceptions.set(exceptions);
      this.taskQueue.set(taskQueue);
      this.analytics.set(analytics);
    });
  }

  private startWorkflowTodoStream(): void {
    if (this.workflowTodoDestroyed || typeof AbortController === 'undefined') {
      return;
    }
    if (this.workflowTodoAbort && !this.workflowTodoAbort.signal.aborted) {
      return;
    }
    if (this.workflowTodoReconnectTimer) {
      clearTimeout(this.workflowTodoReconnectTimer);
      this.workflowTodoReconnectTimer = undefined;
    }
    const controller = new AbortController();
    this.workflowTodoAbort = controller;
    streamWorkflowTodo(
      { onSnapshot: snapshot => this.applyWorkflowTodoSnapshot(snapshot) },
      { signal: controller.signal }
    ).then(() => {
      if (this.workflowTodoAbort === controller) {
        this.workflowTodoAbort = undefined;
      }
      this.scheduleWorkflowTodoReconnect();
    }).catch(error => {
      if (controller.signal.aborted) {
        return;
      }
      if (this.workflowTodoAbort === controller) {
        this.workflowTodoAbort = undefined;
      }
      console.warn('Workflow todo stream unavailable, keeping task queue fallback.', error);
      this.scheduleWorkflowTodoReconnect();
    });
  }

  private scheduleWorkflowTodoReconnect(): void {
    if (this.workflowTodoDestroyed) {
      return;
    }
    if (this.workflowTodoReconnectTimer) {
      clearTimeout(this.workflowTodoReconnectTimer);
    }
    this.workflowTodoReconnectTimer = setTimeout(() => this.startWorkflowTodoStream(), WORKFLOW_TODO_RECONNECT_MS);
  }

  private applyWorkflowTodoSnapshot(snapshot: WorkflowTodoSnapshot): void {
    const workflowItems = snapshot.items.map(item => this.workflowTodoQueueItem(item));
    this.taskQueue.update(queue => this.mergeWorkflowQueueItems(queue, workflowItems, snapshot.generated_at));
  }

  private workflowTodoQueueItem(item: DataRecord): OperationsTaskQueueItem {
    const businessType = String(item['business_type'] ?? '');
    const businessId = String(item['business_id'] ?? '');
    const fallbackId = businessId || String(item.id ?? '');
    const sourcePath = businessType === 'purchase_order' && businessId ? `/app/procurement/orders/${businessId}` : `/app/tasks`;
    return {
      id: `workflow-${item.id ?? `${businessType}-${businessId}`}`,
      source_id: Number(item.id ?? 0) || undefined,
      source: 'workflow',
      business_type: businessType || null,
      business_id: businessId || null,
      title: String(item['title'] ?? '工作流审批待办'),
      description: `${String(item['process_key'] ?? 'workflow')} · ${businessType || 'business'} #${fallbackId}`,
      priority: 'P1',
      status: 'open',
      owner: String(item['assignee_name'] ?? 'workflow'),
      source_path: sourcePath,
      detail_path: sourcePath,
      action_label: '查看审批',
      action_kind: 'navigate',
      category: 'approval',
      created_at: typeof item['created_at'] === 'string' ? item['created_at'] : null
    };
  }

  private mergeWorkflowQueueItems(queue: OperationsTaskQueuePayload, workflowItems: OperationsTaskQueueItem[], generatedAt?: string): OperationsTaskQueuePayload {
    const nonWorkflowItems = queue.items.filter(item => item.source !== 'workflow');
    const items = this.sortQueueItems([...workflowItems, ...nonWorkflowItems]).slice(0, 24);
    const summary = {
      ...queue.summary,
      total: items.length,
      business_exceptions: Math.max(0, queue.summary.business_exceptions - queue.items.filter(item => item.source === 'workflow').length) + workflowItems.length,
      p0: items.filter(item => item.priority === 'P0').length,
      p1: items.filter(item => item.priority === 'P1').length,
      p2: items.filter(item => item.priority === 'P2').length,
      generated_at: generatedAt || queue.summary.generated_at,
      next_action: items.length ? queue.summary.next_action : '当前没有待处理任务。'
    };
    return { summary, items };
  }

  private sortQueueItems(items: OperationsTaskQueueItem[]): OperationsTaskQueueItem[] {
    const priorityRank: Record<string, number> = { P0: 0, P1: 1, P2: 2 };
    const actionRank: Record<string, number> = { complete_notification: 0, create_deployment_task: 1, navigate: 2 };
    const sourceRank: Record<string, number> = { notification: 0, workflow: 1, deployment: 2, stock: 3, purchase: 4 };
    return [...items].sort((a, b) => {
      const rankDelta =
        (a.priority === 'P0' ? 0 : 1) - (b.priority === 'P0' ? 0 : 1) ||
        (priorityRank[a.priority] ?? 3) - (priorityRank[b.priority] ?? 3) ||
        (actionRank[a.action_kind] ?? 9) - (actionRank[b.action_kind] ?? 9) ||
        (sourceRank[a.source] ?? 9) - (sourceRank[b.source] ?? 9);
      return rankDelta || String(a.created_at || '').localeCompare(String(b.created_at || ''));
    });
  }

  createTask(): void {
    const top = this.exceptions().items[0];
    this.taskCreating.set(true);
    this.api.post('operations/dispatch-task', {
      title: top ? `异常复核 - ${top.title}` : '运营异常复核任务',
      content: top ? top.description : `请复核跨模块待办 ${this.todoTotal()} 项并完成闭环处理。`,
      type: top?.level === '高' ? 'alert' : 'warning',
      related_type: top?.type || 'operations'
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '任务未创建', detail: error?.message || '复核任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.taskCreating.set(false))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '复核任务已创建', detail: '任务已进入通知中心。' });
      }
    });
  }

  refreshAlerts(): void {
    this.alertChecking.set(true);
    this.api.post<{ created: number }>('stock-alerts/check', {}).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '预警刷新失败', detail: error?.message || '库存预警未更新。' });
        return of(null);
      }),
      finalize(() => this.alertChecking.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '预警已刷新', detail: `更新 ${result.created} 条库存预警。` });
        this.load();
      }
    });
  }

  completeQueueTask(item: OperationsTaskQueueItem): void {
    if (!item.source_id || this.queueBusy()) {
      return;
    }
    this.queueCompletingId.set(item.id);
    this.api.post<DataRecord>('notifications/complete', {
      id: item.source_id,
      source_path: item.source_path,
      resolution: `已在任务异常中心完成 ${item.title}。`
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '处理失败', detail: error?.message || '任务状态未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.queueCompletingId.set(''))
    ).subscribe(result => {
      if (!result) {
        return;
      }
      this.messages.add({ severity: 'success', summary: '任务已处理', detail: '通知状态和审计日志已更新。' });
      this.load();
    });
  }

  createDeploymentQueueTask(item: OperationsTaskQueueItem): void {
    if (this.queueBusy()) {
      return;
    }
    this.queueCreatingId.set(item.id);
    this.api.post<DataRecord>('operations/deployment-readiness/task', item.payload ?? {
      key: item.id,
      label: item.title,
      scope: item.owner,
      status: item.status,
      evidence: item.description,
      action: item.action_label
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '任务未创建', detail: error?.message || '部署预检任务未写入通知中心。' });
        return of(null);
      }),
      finalize(() => this.queueCreatingId.set(''))
    ).subscribe(result => {
      if (!result) {
        return;
      }
      this.messages.add({ severity: 'success', summary: '预检任务已创建', detail: '部署关注项已写入通知中心。' });
      this.load();
    });
  }

  approveWorkflowQueueTask(item: OperationsTaskQueueItem): void {
    this.completeWorkflowQueueTask(item, 'approve');
  }

  rejectWorkflowQueueTask(item: OperationsTaskQueueItem): void {
    this.completeWorkflowQueueTask(item, 'reject');
  }

  private completeWorkflowQueueTask(item: OperationsTaskQueueItem, action: 'approve' | 'reject'): void {
    if (!item.source_id || this.queueBusy()) {
      return;
    }
    const endpoint = this.workflowActionEndpoint(item, action);
    if (!endpoint) {
      this.messages.add({ severity: 'warn', summary: '审批失败', detail: '任务缺少可处理的业务标识。' });
      return;
    }
    const actionText = action === 'approve' ? '通过' : '驳回';
    this.queueWorkflowActionId.set(`${item.id}:${action}`);
    this.api.post<DataRecord>(endpoint, {
      remark: `任务中心${actionText}：${item.title}`,
      comment: `任务中心${actionText}：${item.title}`
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '审批失败', detail: error?.message || '工作流任务未完成。' });
        return of(null);
      }),
      finalize(() => this.queueWorkflowActionId.set(''))
    ).subscribe(result => {
      if (!result) {
        return;
      }
      this.removeQueueItem(item.id);
      this.messages.add({ severity: 'success', summary: `审批已${actionText}`, detail: '业务状态和工作流待办已同步。' });
      this.load();
    });
  }

  private workflowActionEndpoint(item: OperationsTaskQueueItem, action: 'approve' | 'reject'): string | null {
    const businessType = String(item.business_type ?? '');
    const businessId = String(item.business_id ?? '');
    if (businessType === 'purchase_order' && businessId) {
      return `procurement/orders/${businessId}/${action}`;
    }
    return item.source_id ? `workflows/tasks/${item.source_id}/${action}` : null;
  }

  private removeQueueItem(itemId: string): void {
    this.taskQueue.update(queue => {
      const items = queue.items.filter(item => item.id !== itemId);
      const removed = queue.items.length - items.length;
      return {
        ...queue,
        summary: {
          ...queue.summary,
          total: Math.max(0, queue.summary.total - removed),
          business_exceptions: Math.max(0, queue.summary.business_exceptions - removed),
          p0: items.filter(item => item.priority === 'P0').length,
          p1: items.filter(item => item.priority === 'P1').length,
          p2: items.filter(item => item.priority === 'P2').length,
          next_action: items.length ? queue.summary.next_action : '当前没有待处理任务。'
        },
        items
      };
    });
  }

  protected readonly todoChart = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'item' },
    legend: chartLegend('bottom', 'rgba(100,116,139,.95)'),
    series: [{
      type: 'pie',
      radius: ['42%', '72%'],
      center: ['50%', '42%'],
      roseType: 'radius',
      itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.5)' },
      data: this.todo().items.map(item => ({ name: item.label, value: item.value }))
    }]
  }));

  protected readonly moduleLoadChart = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'axis' },
    legend: chartLegend('top', 'rgba(100,116,139,.95)'),
    grid: { left: 18, right: 18, top: 38, bottom: 26, containLabel: true },
    xAxis: { type: 'category', data: (this.analytics().module_throughput ?? []).map(item => item.name), axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
    series: [
      { name: '待办', type: 'bar', stack: 'total', data: (this.analytics().module_throughput ?? []).map(item => item.todo), itemStyle: { color: '#d99135', borderRadius: [8, 8, 0, 0] } },
      { name: '阻塞', type: 'bar', stack: 'total', data: (this.analytics().module_throughput ?? []).map(item => item.blocked), itemStyle: { color: '#d65f5f' } },
      { name: '完成', type: 'line', smooth: true, data: (this.analytics().module_throughput ?? []).map(item => item.done), lineStyle: { color: '#2ca59d', width: 3 } }
    ]
  }));

  protected cleanPath(path: string): string {
    return (path || '/app/overview').split('?')[0];
  }

  protected prioritySeverity(priority: string): 'success' | 'secondary' | 'info' | 'warn' | 'danger' | 'contrast' {
    if (priority === 'P0') {
      return 'danger';
    }
    if (priority === 'P1') {
      return 'warn';
    }
    return 'info';
  }

  protected sourceLabel(source: string): string {
    const map: Record<string, string> = {
      notification: '通知',
      workflow: '审批',
      deployment: '部署',
      stock: '库存',
      purchase: '采购'
    };
    return map[source] ?? source;
  }

  protected compactNumber(value: unknown): string {
    return compactNumberText(value);
  }
}
