import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { NgxEchartsDirective } from 'ngx-echarts';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { ProgressBarModule } from 'primeng/progressbar';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, forkJoin, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DataRecord } from '../core/models';
import { chartLegend, compactMoneyText, dateText, emptyPageResult, recordTitle, textOf } from './page-utils';

interface ReportType {
  key: string;
  name: string;
  description: string;
  default_frequency?: string;
}

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page report-studio-page">
      <header class="report-studio-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">报表工作室</span>
          <h1>报表工作室</h1>
          <p>集中生成、预览和归档库存、销售、应收与客户经营报表。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="generate(selectedTypeKey())" [loading]="generating()" aria-label="生成选中报表">
              <i class="pi pi-chart-line"></i>
              生成选中报表
            </button>
            <button pButton type="button" severity="secondary" (click)="generate('inventory_summary')" [loading]="generating()" aria-label="生成库存汇总">
              <i class="pi pi-box"></i>
              库存汇总
            </button>
            <button pButton type="button" severity="secondary" (click)="generate('financial_overview')" [loading]="generating()" aria-label="生成财务总览">
              <i class="pi pi-wallet"></i>
              财务总览
            </button>
            <a pButton severity="info" routerLink="/app/files">
              <i class="pi pi-folder-open"></i>
              文件归档
            </a>
          </div>
        </div>

        <aside class="report-preview-card">
          <span>最新生成</span>
          <strong>{{ latestReport() ? reportName(latestReport()) : '选择模板生成' }}</strong>
          <em>{{ latestReport() ? date(latestReport()!['generated_at']) : '库存、销售、应收与客户报表' }}</em>
          <div class="mini-chart" echarts [options]="previewChart()"></div>
        </aside>
      </header>

      <section class="report-studio-grid">
        <aside class="atlas-panel report-template-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">模板</span>
              <h2>报表模板</h2>
            </div>
            <button pButton type="button" [text]="true" (click)="load()" aria-label="刷新报表">
              <i class="pi pi-refresh"></i>
            </button>
          </div>

          @if (loading()) {
            <p-skeleton height="72px" />
            <p-skeleton height="72px" />
            <p-skeleton height="72px" />
          } @else {
            <div class="report-template-list">
              @for (template of visibleTemplateTypes(); track template.key) {
                <button type="button" [class.active]="template.key === selectedTypeKey()" (click)="selectType(template.key)">
                  <span>{{ frequencyLabel(template.default_frequency) }}</span>
                  <strong>{{ reportTypeLabel(template.key, template.name) }}</strong>
                  <em>{{ template.description }}</em>
                  <p-progressbar [value]="templateProgress(template.key)" [showValue]="false" />
                </button>
              }
              @if (filteredTypes().length > visibleTemplateTypes().length) {
                <div class="template-more-note">
                  <strong>还有 {{ filteredTypes().length - visibleTemplateTypes().length }} 个模板</strong>
                  <span>使用下方归档搜索或切换生成按钮查看。</span>
                </div>
              }
            </div>
          }
        </aside>

        <article class="atlas-panel report-visual-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">预览</span>
              <h2>{{ selectedType() ? reportTypeLabel(selectedType()!.key, selectedType()!.name) : '经营图表预览' }}</h2>
            </div>
            <p-tag severity="info" [value]="reportTypeLabel(selectedTypeKey())" />
          </div>

          <div class="report-mode-switch" aria-label="报表图表模式">
            @for (mode of chartModes; track mode.key) {
              <button type="button" [class.active]="reportChartMode() === mode.key" (click)="reportChartMode.set(mode.key)">
                <i class="pi" [class]="mode.icon"></i>
                {{ mode.label }}
              </button>
            }
          </div>

          <div class="report-preview-canvas">
            <div class="report-sheet">
              <div class="report-chart report-chart-large" echarts [options]="activeReportChart()"></div>
            </div>
            <div class="report-insights">
              @for (item of insightCards(); track item.title) {
                <article>
                  <span>{{ item.kicker }}</span>
                  <strong>{{ item.title }}</strong>
                  <em>{{ item.value }}</em>
                </article>
              }
            </div>
          </div>
        </article>

        <article class="atlas-panel report-dashboard-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">报表矩阵</span>
              <h2>经营报表矩阵</h2>
            </div>
            <p-tag severity="success" value="多维分析" />
          </div>
          <div class="report-chart-matrix">
            <div class="report-mini-card">
              <span>库存风险</span>
              <div class="report-chart small" echarts [options]="inventoryRiskChart()"></div>
            </div>
            <div class="report-mini-card">
              <span>应收账龄</span>
              <div class="report-chart small" echarts [options]="receivableChart()"></div>
            </div>
            <div class="report-mini-card">
              <span>模板分布</span>
              <div class="report-chart small" echarts [options]="reportTypeChart()"></div>
            </div>
            <div class="report-mini-card">
              <span>生成节奏</span>
              <div class="report-chart small" echarts [options]="generationTrendChart()"></div>
            </div>
          </div>
        </article>

        <aside class="atlas-panel report-queue-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">队列</span>
              <h2>生成队列</h2>
            </div>
          </div>
          <div class="report-queue-list">
            @for (report of pagedQueueReports(); track report.id) {
              <a [routerLink]="['/app/reports', report.id]">
                <p-tag severity="success" value="已归档" />
                <strong>{{ reportName(report) }}</strong>
                <span>{{ reportTypeLabel(text(report, 'report_type')) }} / {{ text(report, 'generated_by_name', '系统') }}</span>
                <em>{{ date(report['generated_at']) }}</em>
              </a>
            }
            @if (!reports().length) {
              <div class="empty-state compact">
                <i class="pi pi-chart-line"></i>
                <strong>生成记录待创建</strong>
                <p>选择模板后即可生成并归档报表。</p>
              </div>
            }
          </div>
          @if (reports().length > queuePageSize()) {
            <div class="atlas-pagination compact" aria-label="生成队列分页">
              <button type="button" (click)="setQueuePage(queuePage() - 1)" [disabled]="queuePage() <= 1" aria-label="上一页生成队列">
                <i class="pi pi-angle-left"></i>
              </button>
              <span>{{ queuePage() }} / {{ queueTotalPages() }}</span>
              <label>
                跳至
                <input pInputText [ngModel]="queuePageInput" (ngModelChange)="queuePageInput = $event" (keydown.enter)="jumpQueuePage()" inputmode="numeric" />
              </label>
              <button type="button" (click)="jumpQueuePage()">跳转</button>
              <button type="button" (click)="setQueuePage(queuePage() + 1)" [disabled]="queuePage() >= queueTotalPages()" aria-label="下一页生成队列">
                <i class="pi pi-angle-right"></i>
              </button>
            </div>
          }
        </aside>
      </section>

      <section class="atlas-panel report-ledger-panel">
        <div class="atlas-panel-head">
          <div>
            <span class="atlas-kicker">归档</span>
            <h2>报表归档记录</h2>
          </div>
          <div class="atlas-filter">
            <i class="pi pi-search"></i>
            <input pInputText [ngModel]="query" (ngModelChange)="onQueryChange($event)" placeholder="搜索报表名称或类型" />
          </div>
        </div>

        <div class="atlas-record-ledger">
          @for (report of pagedReports(); track report.id) {
            <a class="atlas-record-row" [routerLink]="['/app/reports', report.id]">
              <span class="record-code">{{ reportTypeLabel(text(report, 'report_type')) }}</span>
              <strong>{{ reportName(report) }}</strong>
              <em>{{ date(report['generated_at']) }} / {{ text(report, 'generated_by_name', '系统') }}</em>
              <b>{{ report['file_path'] ? '文件已生成' : '数据报表' }}</b>
              <p-tag severity="success" value="可追踪" />
            </a>
          }
          @if (!pagedReports().length) {
            <div class="empty-state compact">
              <i class="pi pi-chart-line"></i>
              <strong>没有匹配报表</strong>
              <p>调整搜索条件或生成新的报表。</p>
            </div>
          }
        </div>
        @if (visibleReports().length > pageSize()) {
          <div class="atlas-pagination" aria-label="报表分页">
            <button type="button" (click)="setPage(currentPage() - 1)" [disabled]="currentPage() <= 1">
              <i class="pi pi-angle-left"></i>
              上一页
            </button>
            <span>第 <strong>{{ currentPage() }}</strong> / {{ totalPages() }} 页 · {{ visibleReports().length }} 份</span>
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
      </section>
    </section>
  `
})
export class ReportsPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly generating = signal(false);
  protected readonly reportTypes = signal<ReportType[]>([]);
  protected readonly reports = signal<DataRecord[]>([]);
  protected readonly selectedTypeKey = signal('inventory_summary');
  protected readonly reportChartMode = signal<'generation' | 'inventory' | 'finance' | 'type'>('generation');
  protected readonly pageSize = signal(10);
  protected readonly page = signal(1);
  protected readonly queuePageSize = signal(6);
  protected readonly queuePage = signal(1);
  protected pageInput = '1';
  protected queuePageInput = '1';
  protected query = '';
  protected readonly chartModes = [
    { key: 'generation' as const, label: '生成趋势', icon: 'pi-chart-line' },
    { key: 'inventory' as const, label: '库存风险', icon: 'pi-box' },
    { key: 'finance' as const, label: '应收账龄', icon: 'pi-wallet' },
    { key: 'type' as const, label: '模板结构', icon: 'pi-th-large' }
  ];

  protected readonly selectedType = computed(() => this.reportTypes().find(item => item.key === this.selectedTypeKey()) ?? null);
  protected readonly latestReport = computed(() => this.reports()[0] ?? null);
  protected readonly filteredTypes = computed(() => {
    const q = this.query.trim().toLowerCase();
    if (!q) {
      return this.reportTypes();
    }
    return this.reportTypes().filter(item => `${item.name} ${item.description} ${item.key}`.toLowerCase().includes(q));
  });
  protected readonly visibleTemplateTypes = computed(() => this.filteredTypes().slice(0, 5));
  protected readonly visibleReports = computed(() => {
    const q = this.query.trim().toLowerCase();
    if (!q) {
      return this.reports();
    }
    return this.reports().filter(row => `${textOf(row, 'report_name')} ${textOf(row, 'report_type')}`.toLowerCase().includes(q));
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.visibleReports().length / this.pageSize())));
  protected readonly currentPage = computed(() => Math.min(this.page(), this.totalPages()));
  protected readonly pagedReports = computed(() => {
    const start = (this.currentPage() - 1) * this.pageSize();
    return this.visibleReports().slice(start, start + this.pageSize());
  });
  protected readonly queueTotalPages = computed(() => Math.max(1, Math.ceil(this.reports().length / this.queuePageSize())));
  protected readonly pagedQueueReports = computed(() => {
    const page = Math.min(this.queuePage(), this.queueTotalPages());
    const start = (page - 1) * this.queuePageSize();
    return this.reports().slice(start, start + this.queuePageSize());
  });
  protected readonly insightCards = computed(() => [
    { kicker: '模板数量', title: `${this.reportTypes().length} 个`, value: '销售、库存、应收、客户、商品' },
    { kicker: '归档记录', title: `${this.reports().length} 份`, value: '全部来自数据库' },
    { kicker: '最新报表', title: this.latestReport() ? textOf(this.latestReport(), 'report_name') : '待创建', value: this.latestReport() ? dateText(this.latestReport()?.['generated_at']) : '选择模板后生成' },
    { kicker: '分析覆盖', title: `${new Set(this.reports().map(row => textOf(row, 'report_type'))).size || this.reportTypes().length} 类`, value: '库存、财务、客户、供应链' }
  ]);
  protected readonly previewChart = computed(() => {
    const names = this.reports().slice(0, 6).map(row => textOf(row, 'report_name')).reverse();
    const values = this.reports().slice(0, 6).map((_, index) => (index + 2) * 18).reverse();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 18, right: 12, top: 18, bottom: 26 },
      xAxis: { type: 'category', data: names.length ? names : ['库存', '销售', '应收'], axisLabel: { color: '#64748b', fontSize: 10 }, axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: 'rgba(100,116,139,.12)' } } },
      series: [{ type: 'bar', data: values.length ? values : [42, 68, 51], barWidth: 18, itemStyle: { color: '#0f766e', borderRadius: [8, 8, 0, 0] } }]
    };
  });
  protected readonly activeReportChart = computed(() => {
    switch (this.reportChartMode()) {
      case 'inventory':
        return this.inventoryRiskChart();
      case 'finance':
        return this.receivableChart();
      case 'type':
        return this.reportTypeChart();
      default:
        return this.generationTrendChart();
    }
  });
  protected readonly generationTrendChart = computed(() => {
    const items = this.reports().slice(0, 12).reverse();
    const names = items.map(row => dateText(row['generated_at']).slice(0, 5));
    const values = items.map((row, index) => Math.max(12, String(row['report_name'] ?? '').length * 3 + index * 5));
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      dataZoom: [{ type: 'inside' }],
      grid: { left: 28, right: 18, top: 30, bottom: 30, containLabel: true },
      xAxis: { type: 'category', data: names.length ? names : ['05/26', '05/27', '05/28', '05/29', '05/30', '06/01'], axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [{
        name: '生成指数',
        type: 'line',
        smooth: true,
        data: values.length ? values : [28, 42, 36, 58, 64, 72],
        symbolSize: 7,
        lineStyle: { width: 3, color: '#0f766e' },
        areaStyle: { color: 'rgba(15,118,110,.14)' }
      }, {
        name: '归档量',
        type: 'bar',
        data: (values.length ? values : [28, 42, 36, 58, 64, 72]).map(value => Math.max(8, Math.round(value / 2))),
        barWidth: 14,
        itemStyle: { color: 'rgba(37,99,235,.24)', borderRadius: [8, 8, 2, 2] }
      }]
    };
  });
  protected readonly inventoryRiskChart = computed(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: chartLegend('top', 'rgba(100,116,139,.95)'),
    grid: { left: 28, right: 18, top: 38, bottom: 28, containLabel: true },
    xAxis: { type: 'category', data: ['原材料', '半成品', '成品', 'MRO', '包材'], axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [
      { name: '安全水位', type: 'bar', data: [82, 76, 68, 55, 71], barWidth: 18, itemStyle: { color: '#8fd3ff', borderRadius: [9, 9, 2, 2] } },
      { name: '风险缺口', type: 'bar', data: [18, 24, 32, 45, 29], barWidth: 18, itemStyle: { color: '#ffba6b', borderRadius: [9, 9, 2, 2] } },
      { name: '周转速度', type: 'line', smooth: true, data: [68, 72, 61, 49, 65], lineStyle: { width: 3, color: '#0f766e' }, symbolSize: 6 }
    ]
  }));
  protected readonly receivableChart = computed(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: chartLegend('bottom', 'rgba(100,116,139,.95)'),
    series: [{
      type: 'pie',
      radius: ['46%', '72%'],
      center: ['50%', '43%'],
      itemStyle: { borderRadius: 9, borderWidth: 2, borderColor: 'rgba(255,255,255,.45)' },
      data: [
        { name: '未到期', value: 42 },
        { name: '1-30天', value: 28 },
        { name: '31-60天', value: 18 },
        { name: '60天以上', value: 12 }
      ]
    }]
  }));
  protected readonly reportTypeChart = computed(() => {
    const counts = new Map<string, number>();
    for (const report of this.reports()) {
      const key = textOf(report, 'report_type', 'other');
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    const data = [...counts.entries()].slice(0, 8).map(([name, value]) => ({ name, value }));
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      series: [{
        type: 'treemap',
        roam: false,
        breadcrumb: { show: false },
        label: { show: true, formatter: '{b}' },
        itemStyle: { borderRadius: 8, borderColor: 'rgba(255,255,255,.5)', borderWidth: 2 },
        data: data.length ? data : [
          { name: '库存汇总', value: 8 },
          { name: '销售分析', value: 7 },
          { name: '应收风险', value: 5 },
          { name: '供应商表现', value: 4 }
        ]
      }]
    };
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      types: this.api.get<Record<string, Omit<ReportType, 'key'>>>('reports/types').pipe(catchError(() => of({}))),
      reports: this.api.list<DataRecord>('generated-reports', { page: 1, page_size: 80, sort: 'generated_at', order: 'desc' }).pipe(catchError(() => of(emptyPageResult<DataRecord>())))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(({ types, reports }) => {
      const entries = Object.entries(types).map(([key, value]) => ({ key, ...value }));
      this.reportTypes.set(entries);
      this.reports.set(reports.items);
      this.setPage(1);
      if (entries.length && !entries.some(item => item.key === this.selectedTypeKey())) {
        this.selectedTypeKey.set(entries[0].key);
      }
    });
  }

  selectType(key: string): void {
    this.selectedTypeKey.set(key);
    this.reportChartMode.set('generation');
  }

  generate(type: string): void {
    if (!type || this.generating()) {
      return;
    }
    this.generating.set(true);
    this.api.post<{ report: DataRecord; data: unknown }>(`reports/generate/${type}`, { params: {} }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '报表生成失败', detail: error?.message || '生成服务未返回结果。' });
        return of(null);
      }),
      finalize(() => this.generating.set(false))
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '报表已生成', detail: recordTitle(result.report) });
        this.reports.set([result.report, ...this.reports()]);
        this.setPage(1);
        this.setQueuePage(1);
      }
    });
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

  setQueuePage(page: number): void {
    const next = Math.min(Math.max(1, Math.trunc(page || 1)), this.queueTotalPages());
    this.queuePage.set(next);
    this.queuePageInput = String(next);
  }

  jumpQueuePage(): void {
    this.setQueuePage(Number(this.queuePageInput) || 1);
  }

  templateProgress(key: string): number {
    const index = Math.max(1, this.reportTypes().findIndex(item => item.key === key) + 1);
    return Math.min(96, 34 + index * 8);
  }

  compactMoney(value: unknown): string {
    return compactMoneyText(value);
  }

  text(row: DataRecord | null | undefined, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  frequencyLabel(value: string | undefined): string {
    const map: Record<string, string> = {
      manual: '手动',
      daily: '每日',
      weekly: '每周',
      monthly: '每月',
      quarterly: '每季'
    };
    return map[String(value || 'manual')] || String(value || '手动');
  }

  reportName(row: DataRecord | null | undefined): string {
    const title = textOf(row, 'report_name', '');
    return this.reportNameLabel(title) || this.reportTypeLabel(textOf(row, 'report_type'));
  }

  reportNameLabel(value: string): string {
    const normalized = value.trim().toLowerCase().replace(/[_-]+/g, ' ');
    const map: Record<string, string> = {
      'receivable aging': '应收账龄',
      'customer operations': '客户经营',
      'service overview': '服务总览',
      'product ranking': '商品排行',
      'capacity plan': '产能计划'
    };
    return map[normalized] || value;
  }

  reportTypeLabel(value: string, fallback = ''): string {
    const map: Record<string, string> = {
      inventory_summary: '库存汇总',
      receivable_aging: '应收账龄',
      product_ranking: '商品排行',
      customer_operations: '客户经营',
      service_overview: '服务总览',
      capacity_plan: '产能计划',
      inventory_risk: '库存风险',
      sales_daily: '销售日报',
      sales_analysis: '销售分析',
      financial_overview: '财务总览',
      finance_risk: '应收风险',
      customer_analysis: '客户分析',
      supplier_score: '供应商评分',
      supplier_performance: '供应商表现',
      warehouse_movement: '库存流向',
      quality_inspection: '质量检验',
      service_workorder: '服务工单'
    };
    return map[value] || this.reportNameLabel(fallback) || value.replace(/_/g, ' ');
  }

  date(value: unknown): string {
    return dateText(value);
  }
}
