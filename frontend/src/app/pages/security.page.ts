import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { ProgressBarModule } from 'primeng/progressbar';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, forkJoin, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DataRecord } from '../core/models';
import { chartLegend, emptyPageResult, statusSeverity, textOf } from './page-utils';

const PERMISSION_MATRIX = [
  { key: 'inventory.adjust', label: '库存调整', module: '库存', role: '仓储主管' },
  { key: 'purchase.approve', label: '采购审批', module: '采购', role: '采购经理' },
  { key: 'purchase.receive', label: '采购收货', module: '仓配', role: '仓储主管' },
  { key: 'finance.payment', label: '收款处理', module: '财务', role: '财务会计' },
  { key: 'finance.credit.write', label: '信用管理', module: '财务', role: '风控经理' },
  { key: 'reports.generate', label: '报表生成', module: '分析', role: '经营分析师' },
  { key: 'files.manage', label: '文件管理', module: '协作', role: '资料管理员' },
  { key: 'admin', label: '系统管理', module: '系统', role: '管理员' }
];

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page security-console-page">
      <header class="security-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">安全中心</span>
          <h1>系统安全中心</h1>
          <p>把用户、角色、权限矩阵、登录风险和关键业务审计放在一个安全视图中，写入动作必须有权限、有记录。</p>
          <div class="atlas-actions-row">
            <a pButton routerLink="/app/system/audit">
              <i class="pi pi-history"></i>
              查看审计日志
            </a>
            <a pButton severity="secondary" routerLink="/app/profile">
              <i class="pi pi-user"></i>
              个人资料
            </a>
            <a pButton severity="info" routerLink="/app/data-quality">
              <i class="pi pi-shield"></i>
              数据质量
            </a>
          </div>
        </div>

        <aside class="security-health-card">
          <span>安全健康度</span>
          <strong>{{ securityScore() }}%</strong>
          <p-progressbar [value]="securityScore()" [showValue]="false" />
          <em>{{ activeUsers().length }} 个启用账号 / {{ adminUsers().length }} 个管理员</em>
        </aside>
      </header>

      <section class="security-grid">
        <article class="atlas-panel security-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">访问图谱</span>
              <h2>账号、角色与权限</h2>
            </div>
            <div class="flow-chart-tabs">
              <button type="button" [class.active]="chartMode() === 'roles'" (click)="chartMode.set('roles')">角色</button>
              <button type="button" [class.active]="chartMode() === 'departments'" (click)="chartMode.set('departments')">部门</button>
              <button type="button" [class.active]="chartMode() === 'audit'" (click)="chartMode.set('audit')">审计</button>
            </div>
          </div>
          <div class="security-chart" echarts [options]="activeChart()"></div>
        </article>

        <aside class="atlas-panel permission-matrix-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">权限矩阵</span>
              <h2>关键权限矩阵</h2>
            </div>
          </div>
          <div class="permission-matrix">
            @for (item of permissionMatrix; track item.key) {
              <article>
                <span>{{ item.module }}</span>
                <strong>{{ item.label }}</strong>
                <em>{{ item.role }}</em>
              </article>
            }
          </div>
        </aside>

        <article class="atlas-panel users-ledger-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">用户</span>
              <h2>用户与角色</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="onQuery($event)" placeholder="搜索姓名、邮箱、部门、角色" />
            </div>
          </div>

          @if (loading()) {
            <p-skeleton height="78px" />
            <p-skeleton height="78px" />
          } @else {
            <div class="atlas-record-ledger">
              @for (row of pagedUsers(); track row.id) {
                <a class="atlas-record-row" [routerLink]="['/app/system/users', row.id]" [class.warning]="row['is_active_user'] === false">
                  <span class="record-code">{{ text(row, 'role_name') }}</span>
                  <strong>{{ text(row, 'full_name', text(row, 'username')) }}</strong>
                  <em>{{ text(row, 'email') }} / {{ text(row, 'department_name_display', text(row, 'department_name')) }}</em>
                  <b>{{ text(row, 'position') }}</b>
                  <p-tag [severity]="row['is_admin_effective'] === true ? 'success' : 'info'" [value]="row['is_admin_effective'] === true ? '管理员' : '成员'" />
                </a>
              }
            </div>
            @if (filteredUsers().length > pageSize()) {
              <div class="atlas-pagination" aria-label="用户分页">
                <button type="button" (click)="setPage(page() - 1)" [disabled]="page() <= 1">
                  <i class="pi pi-angle-left"></i>
                  上一页
                </button>
                <span>第 <strong>{{ page() }}</strong> / {{ totalPages() }} 页 · {{ filteredUsers().length }} 人</span>
                <label>
                  跳至
                  <input pInputText [ngModel]="pageInput" (ngModelChange)="pageInput = $event" (keydown.enter)="jumpPage()" inputmode="numeric" />
                </label>
                <button type="button" (click)="jumpPage()">跳转</button>
                <button type="button" (click)="setPage(page() + 1)" [disabled]="page() >= totalPages()">
                  下一页
                  <i class="pi pi-angle-right"></i>
                </button>
              </div>
            }
          }
        </article>

        <aside class="atlas-panel audit-preview-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">审计预览</span>
              <h2>最近动作</h2>
            </div>
            <a routerLink="/app/system/audit">全部</a>
          </div>
          <div class="audit-preview-list">
            @for (row of audits().slice(0, 8); track row.id) {
              <a [routerLink]="['/app/system/audit', row.id]">
                <p-tag [severity]="severity(row['module'])" [value]="text(row, 'module')" />
                <strong>{{ text(row, 'action') }}</strong>
                <span>{{ text(row, 'username', 'system') }} / {{ text(row, 'created_at') }}</span>
              </a>
            }
          </div>
        </aside>
      </section>
    </section>
  `
})
export class SecurityPage implements OnInit {
  private readonly api = inject(ApiService);

  protected readonly permissionMatrix = PERMISSION_MATRIX;
  protected readonly loading = signal(false);
  protected readonly users = signal<DataRecord[]>([]);
  protected readonly audits = signal<DataRecord[]>([]);
  protected readonly chartMode = signal<'roles' | 'departments' | 'audit'>('roles');
  protected readonly pageSize = signal(12);
  protected readonly page = signal(1);
  protected query = '';
  protected pageInput = '1';

  protected readonly activeUsers = computed(() => this.users().filter(row => row['is_active_user'] !== false));
  protected readonly adminUsers = computed(() => this.users().filter(row => row['is_admin_effective'] === true || row['is_admin'] === true));
  protected readonly securityScore = computed(() => {
    const inactive = this.users().length - this.activeUsers().length;
    const adminPressure = Math.max(0, this.adminUsers().length - 5);
    return Math.max(72, 98 - inactive - adminPressure);
  });
  protected readonly filteredUsers = computed(() => {
    const q = this.query.trim().toLowerCase();
    if (!q) {
      return this.users();
    }
    return this.users().filter(row => [
      textOf(row, 'full_name'),
      textOf(row, 'username'),
      textOf(row, 'email'),
      textOf(row, 'role_name'),
      textOf(row, 'department_name_display'),
      textOf(row, 'position')
    ].join(' ').toLowerCase().includes(q));
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.filteredUsers().length / this.pageSize())));
  protected readonly pagedUsers = computed(() => {
    const start = (this.page() - 1) * this.pageSize();
    return this.filteredUsers().slice(start, start + this.pageSize());
  });
  protected readonly activeChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'departments') {
      return this.departmentChart();
    }
    if (this.chartMode() === 'audit') {
      return this.auditChart();
    }
    return this.roleChart();
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      users: this.api.list<DataRecord>('users', { page: 1, page_size: 180, sort: 'created_at', order: 'desc' }).pipe(catchError(() => of(emptyPageResult<DataRecord>()))),
      audits: this.api.list<DataRecord>('audit-logs', { page: 1, page_size: 80, sort: 'created_at', order: 'desc' }).pipe(catchError(() => of(emptyPageResult<DataRecord>())))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(({ users, audits }) => {
      this.users.set(users.items);
      this.audits.set(audits.items);
      this.setPage(1);
    });
  }

  onQuery(value: string): void {
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

  text(row: DataRecord, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  severity(value: unknown) {
    return statusSeverity(value);
  }

  private roleChart(): EChartsCoreOption {
    return this.barFromCounts('role_name', '角色人数', '#8da2ff');
  }

  private departmentChart(): EChartsCoreOption {
    return this.barFromCounts('department_name_display', '部门人数', '#62d8cb');
  }

  private auditChart(): EChartsCoreOption {
    const counts = new Map<string, number>();
    for (const row of this.audits()) {
      const key = textOf(row, 'module', 'system');
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom'),
      series: [{
        type: 'pie',
        radius: ['44%', '72%'],
        center: ['50%', '42%'],
        itemStyle: { borderRadius: 10, borderColor: 'rgba(255,255,255,.5)', borderWidth: 2 },
        data: [...counts.entries()].map(([name, value]) => ({ name, value }))
      }]
    };
  }

  private barFromCounts(key: string, name: string, color: string): EChartsCoreOption {
    const counts = new Map<string, number>();
    for (const row of this.users()) {
      const value = textOf(row, key, '未设置');
      counts.set(value, (counts.get(value) ?? 0) + 1);
    }
    const rows = [...counts.entries()].slice(0, 12);
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 24, right: 18, top: 28, bottom: 30, containLabel: true },
      xAxis: { type: 'category', data: rows.map(([label]) => label), axisLabel: { rotate: 16, width: 88, overflow: 'truncate' }, axisTick: { show: false }, axisLine: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } } },
      series: [{ name, type: 'bar', data: rows.map(([, value]) => value), itemStyle: { color, borderRadius: [10, 10, 2, 2] } }]
    };
  }
}
