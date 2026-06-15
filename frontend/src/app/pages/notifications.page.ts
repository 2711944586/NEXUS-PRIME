import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { RouterLink } from '@angular/router';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { ProgressBarModule } from 'primeng/progressbar';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DataRecord } from '../core/models';
import { chartLegend, dateText, emptyPageResult, statusSeverity, textOf } from './page-utils';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page notification-center-page">
      <header class="notification-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">行动收件箱</span>
          <h1>任务通知中心</h1>
          <p>库存预警、采购审批、应收催款、报表完成和系统安全消息按优先级进入收件箱。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="markAllRead()" [loading]="marking()" aria-label="全部标记已读">
              <i class="pi pi-check-circle"></i>
              全部已读
            </button>
            <button pButton type="button" severity="secondary" (click)="setFilter('unread')" aria-label="查看未读">
              <i class="pi pi-bell"></i>
              未读任务
            </button>
            <a pButton severity="info" routerLink="/app/ai">
              <i class="pi pi-chart-line"></i>
              风险摘要
            </a>
          </div>
        </div>

        <aside class="notification-meter">
          <div>
            <span>未读</span>
            <strong>{{ unreadCount() }}</strong>
            <p-progressbar [value]="unreadRate()" [showValue]="false" />
          </div>
          <div>
            <span>高优先级</span>
            <strong>{{ priorityCount() }}</strong>
            <p-progressbar [value]="Math.min(100, priorityCount() * 18)" [showValue]="false" />
          </div>
        </aside>
      </header>

      <section class="notification-insights">
        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">消息结构</span>
              <h2>消息类型结构</h2>
            </div>
            <p-tag severity="info" [value]="notifications().length + ' 条'" />
          </div>
          <div class="notification-chart" echarts [options]="categoryChart()"></div>
        </article>
        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">处理状态</span>
              <h2>处理状态</h2>
            </div>
            <p-tag severity="warn" [value]="unreadCount() + ' 未读'" />
          </div>
          <div class="notification-chart" echarts [options]="readChart()"></div>
        </article>
      </section>

      <section class="notification-grid">
        <aside class="atlas-panel notification-filter-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">收件箱</span>
              <h2>收件箱视图</h2>
            </div>
            <button type="button" class="icon-only-refresh" (click)="load()" aria-label="刷新通知">
              <i class="pi pi-refresh"></i>
            </button>
          </div>

          @for (item of filters; track item.key) {
            <button type="button" [class.active]="filter() === item.key" (click)="setFilter(item.key)">
              <span>{{ item.label }}</span>
              <strong>{{ filterCount(item.key) }}</strong>
              <em>{{ item.description }}</em>
            </button>
          }
        </aside>

        <article class="atlas-panel notification-list-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">任务</span>
              <h2>任务与预警</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="onQueryChange($event)" placeholder="搜索标题、内容、分类" />
            </div>
          </div>

          @if (loading()) {
            <p-skeleton height="76px" />
            <p-skeleton height="76px" />
            <p-skeleton height="76px" />
          } @else if (error()) {
            <div class="empty-state">
              <i class="pi pi-cloud"></i>
              <strong>通知数据通道未连接</strong>
              <p>{{ error() }}</p>
              <button pButton type="button" (click)="load()">重试</button>
            </div>
          } @else {
            <div class="notification-stack">
              @for (item of visibleNotifications(); track item.id) {
                <article class="notification-task" [class.unread]="item['is_read'] !== true" [class.priority]="isPriority(item)">
                  <p-tag [severity]="severity(item)" [value]="categoryText(item)" />
                  <a class="notification-task-main" [routerLink]="detailPath(item)" [attr.aria-label]="'查看通知详情 ' + text(item, 'title')">
                    <strong>{{ text(item, 'title') }}</strong>
                    <p>{{ text(item, 'content', '无正文') }}</p>
                    <em>{{ text(item, 'user_name', '系统') }} / {{ date(item['created_at']) }}</em>
                  </a>
                  <div class="notification-task-actions">
                    <span>{{ item['is_read'] === true ? '已处理' : '未处理' }}</span>
                    <a pButton [text]="true" size="small" [routerLink]="sourcePath(item)" [attr.aria-label]="'查看来源 ' + text(item, 'title')">
                      <i class="pi pi-arrow-up-right"></i>
                      来源
                    </a>
                    @if (item['is_read'] !== true) {
                      <button
                        pButton
                        type="button"
                        size="small"
                        severity="success"
                        [loading]="completingId() === numericId(item)"
                        [disabled]="completingId() !== 0"
                        (click)="completeTask(item)"
                        [attr.aria-label]="'处理完成 ' + text(item, 'title')"
                      >
                        <i class="pi pi-check"></i>
                        处理完成
                      </button>
                    }
                  </div>
                </article>
              }
              @if (!visibleNotifications().length) {
                <div class="empty-state compact">
                  <i class="pi pi-inbox"></i>
                  <strong>没有匹配通知</strong>
                  <p>当前视图没有任务，切换分类或刷新数据。</p>
                </div>
              }
            </div>
            @if (filteredNotifications().length > pageSize()) {
              <div class="atlas-pagination" aria-label="通知分页">
                <button type="button" (click)="setPage(currentPage() - 1)" [disabled]="currentPage() <= 1">
                  <i class="pi pi-angle-left"></i>
                  上一页
                </button>
                <span>第 <strong>{{ currentPage() }}</strong> / {{ totalPages() }} 页 · {{ filteredNotifications().length }} 条</span>
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
        </article>

        <aside class="atlas-panel notification-playbook">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">处理手册</span>
              <h2>处理建议</h2>
            </div>
          </div>
          <a routerLink="/app/inventory/replenishment">
            <strong>库存预警</strong>
            <span>生成补货建议并转采购</span>
          </a>
          <a routerLink="/app/procurement/orders">
            <strong>采购审批</strong>
            <span>审批后推进收货入库</span>
          </a>
          <a routerLink="/app/finance/receivables">
            <strong>应收催款</strong>
            <span>收款或冻结信用额度</span>
          </a>
          <a routerLink="/app/reports">
            <strong>报表完成</strong>
            <span>预览并归档经营摘要</span>
          </a>
        </aside>
      </section>
    </section>
  `
})
export class NotificationsPage implements OnInit {
  protected readonly Math = Math;
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly marking = signal(false);
  protected readonly completingId = signal(0);
  protected readonly error = signal('');
  protected readonly notifications = signal<DataRecord[]>([]);
  protected readonly filter = signal('unread');
  protected readonly pageSize = signal(8);
  protected readonly page = signal(1);
  protected pageInput = '1';
  protected query = '';
  protected readonly filters = [
    { key: 'unread', label: '未读任务', description: '需要处理或确认' },
    { key: 'stock', label: '库存预警', description: '安全库存与补货' },
    { key: 'approval', label: '审批提醒', description: '采购与流程审批' },
    { key: 'report', label: '报表状态', description: '生成与归档结果' },
    { key: 'all', label: '全部通知', description: '完整消息记录' }
  ];

  protected readonly unreadCount = computed(() => this.notifications().filter(item => item['is_read'] !== true).length);
  protected readonly priorityCount = computed(() => this.notifications().filter(item => this.isPriority(item)).length);
  protected readonly unreadRate = computed(() => {
    const total = Math.max(1, this.notifications().length);
    return Math.round((this.unreadCount() / total) * 100);
  });
  protected readonly filteredNotifications = computed(() => {
    const filter = this.filter();
    const q = this.query.trim().toLowerCase();
    return this.notifications().filter(item => {
      const category = String(item['category'] ?? '').toLowerCase();
      const type = String(item['type'] ?? '').toLowerCase();
      const matchesFilter =
        filter === 'all' ||
        (filter === 'unread' && item['is_read'] !== true) ||
        category.includes(filter) ||
        type.includes(filter);
      const haystack = [textOf(item, 'title'), textOf(item, 'content'), category, type].join(' ').toLowerCase();
      return matchesFilter && (!q || haystack.includes(q));
    });
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.filteredNotifications().length / this.pageSize())));
  protected readonly currentPage = computed(() => Math.min(this.page(), this.totalPages()));
  protected readonly visibleNotifications = computed(() => {
    const start = (this.currentPage() - 1) * this.pageSize();
    return this.filteredNotifications().slice(start, start + this.pageSize());
  });
  protected readonly categoryChart = computed<EChartsCoreOption>(() => {
    const counts = new Map<string, number>();
    for (const item of this.notifications()) {
      const label = this.categoryText(item);
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
    const data = [...counts.entries()].map(([name, value]) => ({ name, value }));
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom', 'rgba(100,116,139,.95)'),
      series: [{
        type: 'pie',
        radius: ['44%', '72%'],
        center: ['50%', '43%'],
        itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.56)' },
        data: data.length ? data : [{ name: '通知', value: 1 }]
      }]
    };
  });
  protected readonly readChart = computed<EChartsCoreOption>(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 24, right: 20, top: 28, bottom: 24, containLabel: true },
    xAxis: { type: 'category', data: ['未读', '已读', '高优先'], axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
    series: [{
      type: 'bar',
      data: [this.unreadCount(), this.notifications().length - this.unreadCount(), this.priorityCount()],
      barWidth: 34,
      itemStyle: {
        borderRadius: [12, 12, 2, 2],
        color: (params: { dataIndex: number }) => ['#d99135', '#0f8f86', '#c75062'][params.dataIndex] ?? '#0f8f86'
      }
    }]
  }));

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.list<DataRecord>('notifications', { page: 1, page_size: 100, sort: 'created_at', order: 'desc' }).pipe(
      catchError(error => {
        this.error.set(error?.message || '无法读取通知数据。');
        return of(emptyPageResult<DataRecord>());
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(result => {
      this.notifications.set(result.items);
      this.setPage(1);
    });
  }

  markAllRead(): void {
    const ids = this.notifications().filter(item => item['is_read'] !== true).map(item => item.id).filter(Boolean);
    if (!ids.length) {
      this.messages.add({ severity: 'info', summary: '通知中心', detail: '当前没有未读通知。' });
      return;
    }
    this.marking.set(true);
    this.api.post<{ changed: number }>('notifications/mark-read', { ids }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '标记失败', detail: error?.message || '通知状态未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.marking.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '通知已处理', detail: `${result.changed} 条通知已标记为已读。` });
        this.notifications.set(this.notifications().map(item => ids.includes(item.id) ? { ...item, is_read: true } : item));
      }
    });
  }

  completeTask(item: DataRecord): void {
    const id = this.numericId(item);
    if (!id || this.completingId()) {
      return;
    }
    this.completingId.set(id);
    const sourcePath = this.sourcePath(item);
    this.api.post<DataRecord>('notifications/complete', {
      id,
      source_path: sourcePath,
      resolution: `已按来源 ${sourcePath} 完成任务处理。`
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '处理失败', detail: error?.message || '任务状态未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.completingId.set(0))
    ).subscribe(result => {
      if (!result) {
        return;
      }
      this.notifications.set(this.notifications().map(row => this.numericId(row) === id ? { ...row, ...result, is_read: true } : row));
      this.messages.add({ severity: 'success', summary: '任务已处理', detail: '通知状态和审计日志已更新。' });
    });
  }

  filterCount(key: string): number {
    if (key === 'all') {
      return this.notifications().length;
    }
    if (key === 'unread') {
      return this.unreadCount();
    }
    return this.notifications().filter(item => String(item['category'] ?? '').toLowerCase().includes(key) || String(item['type'] ?? '').toLowerCase().includes(key)).length;
  }

  setFilter(key: string): void {
    this.filter.set(key);
    this.setPage(1);
  }

  onQueryChange(value: string): void {
    this.query = value;
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

  isPriority(item: DataRecord): boolean {
    const text = `${item['type'] ?? ''} ${item['category'] ?? ''}`.toLowerCase();
    return text.includes('alert') || text.includes('warning') || text.includes('stock') || text.includes('approval');
  }

  severity(item: DataRecord): 'success' | 'secondary' | 'info' | 'warn' | 'danger' | 'contrast' {
    if (String(item['type'] ?? '').toLowerCase().includes('alert')) {
      return 'danger';
    }
    return statusSeverity(item['type']);
  }

  categoryText(item: DataRecord): string {
    const category = textOf(item, 'category', 'system');
    const map: Record<string, string> = {
      stock: '库存预警',
      approval: '审批提醒',
      report: '报表状态',
      order: '订单通知',
      system: '系统通知'
    };
    return map[category] ?? category;
  }

  detailPath(item: DataRecord): string {
    return `/app/notifications/${item.id ?? 0}`;
  }

  sourcePath(item: DataRecord): string {
    const relatedType = String(item['related_type'] ?? '');
    const relatedId = Number(item['related_id'] ?? 0);
    if (relatedType.includes('deployment_readiness')) {
      return '/app/settings';
    }
    if (relatedType.includes('integration')) {
      return '/app/integrations';
    }
    if (relatedType.includes('quality')) {
      return '/app/data-quality';
    }
    if (relatedType.includes('cost')) {
      return '/app/budget';
    }
    if (relatedType.includes('mobile_terminal')) {
      return '/app/mobile-terminal';
    }
    if (relatedType.includes('rules')) {
      return '/app/rules';
    }
    if (relatedType.includes('purchase') && relatedId) {
      return `/app/procurement/orders/${relatedId}`;
    }
    if (relatedType.includes('order') && relatedId) {
      return `/app/sales/orders/${relatedId}`;
    }
    if (relatedType.includes('report') && relatedId) {
      return `/app/reports/${relatedId}`;
    }
    if (relatedType.includes('product') && relatedId) {
      return `/app/inventory/products/${relatedId}`;
    }
    return `/app/notifications/${item.id ?? 0}`;
  }

  numericId(item: DataRecord): number {
    return Number(item.id ?? 0);
  }

  text(row: DataRecord, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  date(value: unknown): string {
    return dateText(value);
  }
}
