import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { TextareaModule } from 'primeng/textarea';
import { catchError, finalize, forkJoin, of, Subscription } from 'rxjs';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { ExecutiveAnalytics, ManufacturingCommandCenter, OperationsTodoPayload, User } from '../core/models';
import { chartLegend, compactMoneyText, compactNumberText, EMPTY_TODO } from './page-utils';

const AVATAR_MAX_BYTES = 3 * 1024 * 1024;
const AVATAR_TYPES = new Set(['image/png', 'image/jpeg', 'image/gif']);

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

const EMPTY_COMMAND: ManufacturingCommandCenter = {
  kpis: { order_amount: 0, stock_quantity: 0, low_stock_products: 0, pending_purchase: 0, overdue_amount: 0 },
  warehouse_heat: [],
  flows: [],
  risks: []
};


@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, SkeletonModule, TagModule, TextareaModule],
  template: `
    <section class="ops-atlas-page profile-console-page profile-studio-page">
      @if (user(); as current) {
        <header class="atlas-panel profile-studio-hero">
          <div class="profile-studio-person">
            <div class="profile-avatar-wrap profile-studio-avatar-wrap">
              <div class="profile-avatar" [class.loading]="avatarUploading() || avatarDeleting()">
                @if (avatarDisplayUrl(current); as avatarUrl) {
                  <img [src]="avatarUrl" [alt]="current.full_name || current.username" (error)="markAvatarBroken(avatarUrl)" />
                } @else {
                  <span class="profile-avatar-initials">{{ initials(current) }}</span>
                }
                @if (avatarUploading() || avatarDeleting()) {
                  <span class="avatar-change-badge">处理中</span>
                }
              </div>
              <div class="avatar-control-row">
                <input #avatarInput class="avatar-file-input" type="file" accept="image/png,image/jpeg,image/gif" (change)="uploadAvatar($event)" tabindex="-1" aria-hidden="true" />
                <button pButton type="button" size="small" [disabled]="avatarUploading() || avatarDeleting()" (click)="avatarInput.click()">
                  <i class="pi pi-upload"></i>
                  更换头像
                </button>
                <button pButton type="button" size="small" severity="secondary" [text]="true" [disabled]="!current.avatar || avatarUploading() || avatarDeleting()" (click)="deleteAvatar()">
                  <i class="pi pi-refresh"></i>
                  恢复默认
                </button>
              </div>
            </div>

            <div class="profile-studio-copy">
              <span class="atlas-kicker">个人工作台</span>
              <h1>{{ current.full_name || current.username }}</h1>
              <p>{{ current.position || '业务协同成员' }} / {{ current.department_name_display || current.department_name || '未设置部门' }}</p>
              <div class="profile-meta-row" aria-label="账号信息">
                <span><i class="pi pi-envelope"></i>{{ current.email || '未绑定邮箱' }}</span>
                <span><i class="pi pi-briefcase"></i>{{ current.role_name || 'User' }}</span>
                <span><i class="pi pi-building"></i>{{ current.department_name_display || current.department_name || '未设置部门' }}</span>
              </div>
              <div class="profile-tags">
                <p-tag [value]="current.role_name || 'User'" severity="info" />
                <p-tag [value]="current.is_admin_effective ? '管理员' : '成员'" [severity]="current.is_admin_effective ? 'success' : 'secondary'" />
              </div>
            </div>
          </div>

          <aside class="profile-session-panel" aria-label="当前会话">
            <div class="profile-session-head">
              <span>当前会话</span>
              <strong>{{ current.is_admin_effective ? '管理权限' : '成员权限' }}</strong>
              <em>{{ draft.preferences?.theme === 'dark-cockpit' ? '深色驾驶舱' : '白色系统' }}</em>
            </div>
            <div class="profile-signal-grid" aria-label="个人工作摘要">
              <article>
                <span>资料完整度</span>
                <strong>{{ profileCompletion() }}%</strong>
                <em>账号、岗位、说明</em>
              </article>
              <article>
                <span>待处理任务</span>
                <strong>{{ todoTotal() }}</strong>
                <em>业务队列</em>
              </article>
              <article>
                <span>经营风险</span>
                <strong>{{ command().risks.length }}</strong>
                <em>库存、采购、应收</em>
              </article>
              <article>
                <span>回款压力</span>
                <strong>{{ compactMoney(analytics().kpis.unpaid_amount) }}</strong>
                <em>账龄占用</em>
              </article>
            </div>
          </aside>
        </header>
      } @else {
        <p-skeleton height="180px" />
      }

      <section class="profile-studio-insights" aria-label="个人经营工作台">
        <article class="atlas-panel profile-chart-panel profile-workload-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">个人负载</span>
              <h2>工作负载</h2>
            </div>
            <p-tag severity="info" [value]="todoTotal() + ' 项待处理'" />
          </div>
          <div class="profile-workload-board">
            @if (hasWorkloadData()) {
              <div class="profile-chart" echarts [options]="workloadChart()"></div>
            } @else {
              <div class="profile-workload-empty">
                <i class="pi pi-check-circle"></i>
                <strong>当前没有积压任务</strong>
                <span>资料、采购、库存和回款队列暂无新增待办。</span>
              </div>
            }
            <div class="profile-workload-summary" aria-label="个人业务摘要">
              @for (item of workloadSummary(); track item.label) {
                <article [class.warning]="item.tone === 'warning'">
                  <i class="pi" [class]="item.icon"></i>
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                  <em>{{ item.note }}</em>
                </article>
              }
            </div>
          </div>
        </article>

        <aside class="atlas-panel profile-action-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">业务入口</span>
              <h2>下一步处理</h2>
            </div>
          </div>
          <div class="profile-action-list">
            @for (item of profileActions(); track item.path) {
              <a class="profile-action-row" [routerLink]="item.path" [class.warning]="item.tone === 'warning'">
                <i class="pi" [class]="item.icon"></i>
                <span>
                  <em>{{ item.kicker }}</em>
                  <strong>{{ item.title }}</strong>
                  <small>{{ item.body }}</small>
                </span>
              </a>
            }
            <a class="profile-action-row" routerLink="/app/notifications">
              <i class="pi pi-bell"></i>
              <span>
                <em>通知</em>
                <strong>待处理消息</strong>
                <small>库存、审批、收款和报表完成消息集中进入通知中心。</small>
              </span>
            </a>
            <a class="profile-action-row" routerLink="/app/ai">
              <i class="pi pi-chart-line"></i>
              <span>
                <em>分析</em>
                <strong>经营摘要</strong>
                <small>快速回到经营分析、报表和风险队列。</small>
              </span>
            </a>
          </div>
        </aside>
      </section>

      <section class="profile-studio-grid">
        <article class="atlas-panel profile-editor profile-form-card">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">资料</span>
              <h2>个人资料</h2>
            </div>
            <button pButton type="button" (click)="save()" [loading]="saving()" aria-label="保存资料">
              <i class="pi pi-save"></i>
              保存
            </button>
          </div>

          <div class="profile-form-grid">
            <label>
              <span>姓名</span>
              <input pInputText [(ngModel)]="draft.full_name" placeholder="姓名" />
            </label>
            <label>
              <span>用户名</span>
              <input pInputText [(ngModel)]="draft.username" placeholder="用户名" />
            </label>
            <label>
              <span>手机</span>
              <input pInputText [(ngModel)]="draft.phone" placeholder="手机号码" />
            </label>
            <label>
              <span>岗位</span>
              <input pInputText [(ngModel)]="draft.position" placeholder="岗位" />
            </label>
            <label>
              <span>部门</span>
              <input pInputText [(ngModel)]="draft.department_name" placeholder="部门" />
            </label>
            <label>
              <span>邮箱</span>
              <input pInputText [ngModel]="draft.email" disabled />
            </label>
            <label class="wide">
              <span>工作说明</span>
              <textarea pTextarea rows="4" [(ngModel)]="draft.bio" placeholder="负责的业务范围、班组协同或审批说明"></textarea>
            </label>
          </div>
        </article>

        <aside class="atlas-panel profile-ops-card profile-settings-card">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">偏好</span>
              <h2>工作偏好</h2>
            </div>
          </div>
          <div class="profile-preference-list">
            <button type="button" [class.active]="draft.preferences?.theme === 'dark-cockpit'" (click)="setTheme('dark-cockpit')">
              <strong>深色驾驶舱</strong>
              <span>监控屏和夜间值守</span>
            </button>
            <button type="button" [class.active]="draft.preferences?.theme === 'light-luxury'" (click)="setTheme('light-luxury')">
              <strong>白色系统</strong>
              <span>日常办公和报表复核</span>
            </button>
          </div>
          <div class="profile-ledger">
            <div><span>账号</span><strong>{{ user()?.email || '-' }}</strong></div>
            <div><span>角色</span><strong>{{ user()?.role_name || 'User' }}</strong></div>
            <div><span>会话</span><strong>{{ user()?.is_admin_effective ? '管理会话' : '业务会话' }}</strong></div>
          </div>
          <div class="profile-session-actions">
            <button pButton type="button" severity="secondary" [outlined]="true" (click)="logout()" aria-label="退出登录">
              <i class="pi pi-sign-out"></i>
              退出登录
            </button>
          </div>
        </aside>
      </section>
    </section>
  `
})
export class ProfilePage implements OnInit, OnDestroy {
  private readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);
  private readonly router = inject(Router);
  private subscription?: Subscription;

  protected readonly user = signal<User | null>(null);
  protected readonly saving = signal(false);
  protected readonly avatarUploading = signal(false);
  protected readonly avatarDeleting = signal(false);
  protected readonly brokenAvatarUrl = signal('');
  protected readonly avatarPreviewUrl = signal<string | null>(null);
  protected readonly contextLoading = signal(false);
  protected readonly analytics = signal<ExecutiveAnalytics>(EMPTY_ANALYTICS);
  protected readonly command = signal<ManufacturingCommandCenter>(EMPTY_COMMAND);
  protected readonly todo = signal<OperationsTodoPayload>(EMPTY_TODO);
  protected draft: Partial<User> = {};
  protected readonly todoTotal = computed(() => this.todo().items.reduce((sum, item) => sum + Number(item.value || 0), 0));
  protected readonly workloadRows = computed(() => {
    const todoRows = this.todo().items.filter(item => Number(item.value || 0) > 0);
    if (todoRows.length) {
      return todoRows;
    }
    return (this.analytics().module_throughput ?? []).map(item => ({
      label: item.name,
      value: item.todo,
      path: '/app/tasks'
    }));
  });
  protected readonly hasWorkloadData = computed(() => this.workloadRows().some(item => Number(item.value || 0) > 0));
  protected readonly workloadSummary = computed(() => [
    {
      label: '库存预警',
      value: this.compactNumber(this.command().kpis.low_stock_products),
      note: '补货队列',
      icon: 'pi-box',
      tone: this.command().kpis.low_stock_products ? 'warning' : 'normal'
    },
    {
      label: '采购待审',
      value: this.compactNumber(this.command().kpis.pending_purchase),
      note: '审批闭环',
      icon: 'pi-shopping-cart',
      tone: this.command().kpis.pending_purchase ? 'warning' : 'normal'
    },
    {
      label: '逾期应收',
      value: this.compactMoney(this.command().kpis.overdue_amount || this.analytics().kpis.unpaid_amount),
      note: '回款跟进',
      icon: 'pi-wallet',
      tone: (this.command().kpis.overdue_amount || this.analytics().kpis.unpaid_amount) ? 'warning' : 'normal'
    }
  ]);
  protected readonly profileActions = computed(() => [
    {
      kicker: '库存',
      title: `${this.command().kpis.low_stock_products} 项低水位`,
      body: '进入补货队列，复核安全库存、建议量和供应商交期。',
      path: '/app/inventory/replenishment',
      icon: 'pi-bolt',
      tone: this.command().kpis.low_stock_products ? 'warning' : 'success'
    },
    {
      kicker: '采购',
      title: `${this.command().kpis.pending_purchase} 单待审批`,
      body: '推进采购审批、到货质检和收货入库。',
      path: '/app/procurement/orders',
      icon: 'pi-shopping-cart',
      tone: this.command().kpis.pending_purchase ? 'warning' : 'success'
    },
    {
      kicker: '应收',
      title: this.compactMoney(this.command().kpis.overdue_amount || this.analytics().kpis.unpaid_amount),
      body: '按账龄、客户信用和收款记录处理回款风险。',
      path: '/app/finance/receivables',
      icon: 'pi-wallet',
      tone: (this.command().kpis.overdue_amount || this.analytics().kpis.unpaid_amount) ? 'warning' : 'success'
    }
  ]);
  protected readonly workloadChart = computed<EChartsCoreOption>(() => {
    const rows = this.workloadRows();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 26, right: 20, top: 28, bottom: 24, containLabel: true },
      xAxis: { type: 'category', data: rows.map(item => item.label), axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [{
        name: '待处理',
        type: 'bar',
        data: rows.map(item => item.value),
        barWidth: 24,
        itemStyle: {
          borderRadius: [12, 12, 2, 2],
          color: '#0f8f86'
        }
      }]
    };
  });
  protected readonly riskFocusChart = computed<EChartsCoreOption>(() => {
    const riskMix = this.analytics().risk_mix.length ? this.analytics().risk_mix : [
      { name: '库存预警', value: this.command().kpis.low_stock_products },
      { name: '采购审批', value: this.command().kpis.pending_purchase },
      { name: '逾期应收', value: Math.round((this.command().kpis.overdue_amount || 0) / 100000) }
    ];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom', 'rgba(100,116,139,.95)'),
      series: [{
        type: 'pie',
        radius: ['46%', '72%'],
        center: ['50%', '43%'],
        itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.55)' },
        data: riskMix
      }]
    };
  });
  protected readonly efficiencyChart = computed<EChartsCoreOption>(() => {
    const rows = this.analytics().operational_efficiency?.length ? this.analytics().operational_efficiency! : [
      { name: '履约完成率', value: 0, target: 92 },
      { name: '采购闭环率', value: 0, target: 88 },
      { name: '回款覆盖率', value: 0, target: 86 }
    ];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      radar: {
        radius: '62%',
        indicator: rows.map(item => ({ name: item.name, max: 100 })),
        axisName: { color: 'rgba(100,116,139,.95)' }
      },
      series: [{
        type: 'radar',
        data: [
          { name: '当前', value: rows.map(item => item.value), areaStyle: { color: 'rgba(15,143,134,.18)' }, lineStyle: { color: '#0f8f86', width: 3 } },
          { name: '目标', value: rows.map(item => item.target), areaStyle: { color: 'rgba(240,183,106,.12)' }, lineStyle: { color: '#f0b76a', width: 2 } }
        ]
      }]
    };
  });

  ngOnInit(): void {
    this.subscription = this.auth.currentUser$.subscribe(user => {
      this.user.set(user);
      this.draft = {
        ...user,
        preferences: { ...(user?.preferences ?? {}) }
      };
    });
    this.auth.refreshCurrentUser().subscribe();
    this.loadContext();
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
    this.revokeAvatarPreview();
  }

  setTheme(theme: 'dark-cockpit' | 'light-luxury'): void {
    this.draft.preferences = { ...(this.draft.preferences ?? {}), theme };
  }

  profileCompletion(): number {
    const fields = [this.draft.full_name, this.draft.username, this.draft.phone, this.draft.position, this.draft.department_name, this.draft.bio];
    const filled = fields.filter(value => String(value ?? '').trim().length > 0).length;
    return Math.round((filled / fields.length) * 100);
  }

  compactMoney(value: unknown): string {
    return compactMoneyText(value);
  }

  compactNumber(value: unknown): string {
    return compactNumberText(value);
  }

  loadContext(): void {
    this.contextLoading.set(true);
    forkJoin({
      analytics: this.api.get<ExecutiveAnalytics>('analytics/executive').pipe(catchError(() => of(EMPTY_ANALYTICS))),
      command: this.api.get<ManufacturingCommandCenter>('manufacturing/command-center').pipe(catchError(() => of(EMPTY_COMMAND))),
      todo: this.api.get<OperationsTodoPayload>('operations/todo').pipe(catchError(() => of(EMPTY_TODO)))
    }).pipe(finalize(() => this.contextLoading.set(false))).subscribe(({ analytics, command, todo }) => {
      this.analytics.set(analytics);
      this.command.set(command);
      this.todo.set(todo);
    });
  }

  initials(user: User | null | undefined): string {
    const name = (user?.full_name || user?.username || user?.email || 'NX').replace(/\s+/g, '');
    return name.slice(0, 2).toUpperCase();
  }

  markAvatarBroken(url: string | null | undefined): void {
    if (url) {
      this.brokenAvatarUrl.set(url);
    }
  }

  avatarDisplayUrl(user: User | null | undefined): string | null {
    const preview = this.avatarPreviewUrl();
    if (preview) {
      return preview;
    }
    const avatar = user?.avatar;
    return avatar && this.brokenAvatarUrl() !== avatar ? avatar : null;
  }

  save(): void {
    this.saving.set(true);
    this.auth.updateProfile(this.draft).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '保存失败', detail: error?.message || '资料未更新。' });
        return of(null);
      }),
      finalize(() => this.saving.set(false))
    ).subscribe(user => {
      if (user) {
        this.messages.add({ severity: 'success', summary: '资料已保存', detail: user.full_name || user.username });
      }
    });
  }

  uploadAvatar(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      return;
    }
    if (!AVATAR_TYPES.has(file.type)) {
      this.messages.add({ severity: 'warn', summary: '头像格式不支持', detail: '请选择 PNG、JPG 或 GIF 图片。' });
      input.value = '';
      return;
    }
    if (file.size > AVATAR_MAX_BYTES) {
      this.messages.add({ severity: 'warn', summary: '头像过大', detail: '头像文件不能超过 3MB。' });
      input.value = '';
      return;
    }
    this.setAvatarPreview(file);
    const data = new FormData();
    data.append('file', file);
    this.avatarUploading.set(true);
    this.api.postForm<User>('me/avatar', data).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '头像上传失败', detail: error?.message || '头像未更新。' });
        return of(null);
      }),
      finalize(() => {
        this.avatarUploading.set(false);
        input.value = '';
      })
    ).subscribe(user => {
      if (user) {
        this.revokeAvatarPreview();
        this.brokenAvatarUrl.set('');
        this.auth.updateCurrentUser(user);
        this.messages.add({ severity: 'success', summary: '头像已更新', detail: user.full_name || user.username });
      } else {
        this.revokeAvatarPreview();
      }
    });
  }

  deleteAvatar(): void {
    if (this.avatarDeleting()) {
      return;
    }
    this.avatarDeleting.set(true);
    this.api.delete<User>('me/avatar').pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '头像未恢复', detail: error?.message || '默认头像未恢复。' });
        return of(null);
      }),
      finalize(() => this.avatarDeleting.set(false))
    ).subscribe(user => {
      if (user) {
        this.revokeAvatarPreview();
        this.brokenAvatarUrl.set('');
        this.auth.updateCurrentUser(user);
        this.messages.add({ severity: 'success', summary: '头像已恢复', detail: user.full_name || user.username });
      }
    });
  }

  logout(): void {
    this.auth.logout();
    this.router.navigateByUrl('/auth/login');
  }

  private setAvatarPreview(file: File): void {
    this.revokeAvatarPreview();
    this.avatarPreviewUrl.set(URL.createObjectURL(file));
  }

  private revokeAvatarPreview(): void {
    const current = this.avatarPreviewUrl();
    if (current) {
      URL.revokeObjectURL(current);
      this.avatarPreviewUrl.set(null);
    }
  }
}
