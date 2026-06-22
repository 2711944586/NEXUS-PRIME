import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DataRecord } from '../core/models';
import { dateText, emptyPageResult, statusSeverity, textOf } from './page-utils';

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page audit-console-page">
      <header class="audit-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">审计账本</span>
          <h1>审计日志</h1>
          <p>登录、采购审批、收货、库存调整、收款、文件下载和系统设置都会写入审计账本，支持按模块回看。</p>
          <div class="atlas-actions-row">
            <a pButton routerLink="/app/system/users">
              <i class="pi pi-shield"></i>
              安全中心
            </a>
            <a pButton severity="secondary" routerLink="/app/reports">
              <i class="pi pi-chart-line"></i>
              报表工作室
            </a>
          </div>
        </div>

        <aside class="audit-summary-card">
          <article>
            <span>审计记录</span>
            <strong>{{ rows().length }}</strong>
            <em>最近读取</em>
          </article>
          <article>
            <span>模块覆盖</span>
            <strong>{{ moduleCount() }}</strong>
            <em>业务域</em>
          </article>
          <article>
            <span>高频动作</span>
            <strong>{{ topAction() }}</strong>
            <em>最近日志</em>
          </article>
        </aside>
      </header>

      <section class="audit-grid">
        <article class="atlas-panel audit-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">追踪图谱</span>
              <h2>模块与动作分布</h2>
            </div>
            <div class="flow-chart-tabs">
              <button type="button" [class.active]="chartMode() === 'module'" (click)="chartMode.set('module')">模块</button>
              <button type="button" [class.active]="chartMode() === 'action'" (click)="chartMode.set('action')">动作</button>
              <button type="button" [class.active]="chartMode() === 'timeline'" (click)="chartMode.set('timeline')">时间</button>
            </div>
          </div>
          <div class="audit-chart" echarts [options]="activeChart()"></div>
        </article>

        <aside class="atlas-panel audit-filter-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">筛选</span>
              <h2>模块筛选</h2>
            </div>
          </div>
          <div class="audit-module-list">
            <button type="button" [class.active]="moduleFilter() === ''" (click)="setModule('')">
              <strong>全部模块</strong>
              <span>{{ rows().length }}</span>
            </button>
            @for (item of moduleBuckets(); track item.name) {
              <button type="button" [class.active]="moduleFilter() === item.name" (click)="setModule(item.name)">
                <strong>{{ item.name }}</strong>
                <span>{{ item.value }}</span>
              </button>
            }
          </div>
        </aside>

        <article class="atlas-panel audit-ledger-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">账本</span>
              <h2>审计账本</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="onQuery($event)" placeholder="搜索模块、动作、操作者、详情" />
            </div>
          </div>

          @if (loading()) {
            <p-skeleton height="78px" />
            <p-skeleton height="78px" />
          } @else {
            <div class="atlas-record-ledger">
              @for (row of pagedRows(); track row.id) {
                <a class="atlas-record-row" [routerLink]="['/app/system/audit', row.id]">
                  <span class="record-code">{{ text(row, 'module') }}</span>
                  <strong>{{ text(row, 'action') }}</strong>
                  <em>{{ text(row, 'username', 'system') }} / {{ date(row['created_at']) }}</em>
                  <b>{{ text(row, 'ip_address') }}</b>
                  <p-tag [severity]="severity(row['module'])" [value]="text(row, 'module')" />
                </a>
              }
            </div>
            @if (filteredRows().length > pageSize()) {
              <div class="atlas-pagination" aria-label="审计分页">
                <button type="button" (click)="setPage(page() - 1)" [disabled]="page() <= 1">
                  <i class="pi pi-angle-left"></i>
                  上一页
                </button>
                <span>第 <strong>{{ page() }}</strong> / {{ totalPages() }} 页 · {{ filteredRows().length }} 条</span>
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
      </section>
    </section>
  `
})
export class AuditPage implements OnInit {
  private readonly api = inject(ApiService);

  protected readonly loading = signal(false);
  protected readonly rows = signal<DataRecord[]>([]);
  protected readonly moduleFilter = signal('');
  protected readonly chartMode = signal<'module' | 'action' | 'timeline'>('module');
  protected readonly pageSize = signal(14);
  protected readonly page = signal(1);
  protected query = '';
  protected pageInput = '1';

  protected readonly moduleBuckets = computed(() => this.bucket('module'));
  protected readonly moduleCount = computed(() => this.moduleBuckets().length);
  protected readonly topAction = computed(() => this.bucket('action')[0]?.name ?? '-');
  protected readonly filteredRows = computed(() => {
    const q = this.query.trim().toLowerCase();
    const module = this.moduleFilter();
    return this.rows().filter(row => {
      const haystack = [textOf(row, 'module'), textOf(row, 'action'), textOf(row, 'username'), textOf(row, 'details')].join(' ').toLowerCase();
      return (!module || textOf(row, 'module') === module) && (!q || haystack.includes(q));
    });
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.filteredRows().length / this.pageSize())));
  protected readonly pagedRows = computed(() => {
    const start = (this.page() - 1) * this.pageSize();
    return this.filteredRows().slice(start, start + this.pageSize());
  });
  protected readonly activeChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'action') {
      return this.bucketChart('action', '#8da2ff');
    }
    if (this.chartMode() === 'timeline') {
      return this.timelineChart();
    }
    return this.bucketChart('module', '#62d8cb');
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.list<DataRecord>('audit-logs', { page: 1, page_size: 180, sort: 'created_at', order: 'desc' }).pipe(
      catchError(() => of(emptyPageResult<DataRecord>())),
      finalize(() => this.loading.set(false))
    ).subscribe(result => {
      this.rows.set(result.items);
      this.setPage(1);
    });
  }

  setModule(module: string): void {
    this.moduleFilter.set(module);
    this.setPage(1);
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

  date(value: unknown): string {
    return dateText(value);
  }

  severity(value: unknown) {
    return statusSeverity(value);
  }

  private bucket(key: string): Array<{ name: string; value: number }> {
    const counts = new Map<string, number>();
    for (const row of this.rows()) {
      const name = textOf(row, key, 'unknown');
      counts.set(name, (counts.get(name) ?? 0) + 1);
    }
    return [...counts.entries()].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
  }

  private bucketChart(key: string, color: string): EChartsCoreOption {
    const rows = this.bucket(key).slice(0, 12);
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 24, right: 18, top: 28, bottom: 30, containLabel: true },
      xAxis: { type: 'category', data: rows.map(item => item.name), axisLabel: { rotate: 18, width: 88, overflow: 'truncate' }, axisTick: { show: false }, axisLine: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } } },
      series: [{ type: 'bar', data: rows.map(item => item.value), itemStyle: { color, borderRadius: [10, 10, 2, 2] } }]
    };
  }

  private timelineChart(): EChartsCoreOption {
    const rows = this.rows().slice(0, 30).reverse();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 24, right: 18, top: 28, bottom: 30, containLabel: true },
      xAxis: { type: 'category', data: rows.map(row => dateText(row['created_at']).slice(5, 16)), axisLabel: { rotate: 16 }, axisTick: { show: false }, axisLine: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.14)' } } },
      series: [{ type: 'line', smooth: true, symbolSize: 6, data: rows.map((_row, index) => index + 1), lineStyle: { width: 3, color: '#f0b76a' }, areaStyle: { color: 'rgba(240,183,106,.16)' } }]
    };
  }
}
