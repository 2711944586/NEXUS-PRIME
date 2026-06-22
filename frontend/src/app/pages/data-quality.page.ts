import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
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
import { DataQualityIssue, DataQualityPayload } from '../core/models';
import { compactNumberText, compactRadar, dateText, TagSeverity } from './page-utils';

const DATA_QUALITY_JOB_POLL_MS = 2200;
const DATA_QUALITY_JOB_MAX_ATTEMPTS = 25;

const EMPTY_DATA_QUALITY: DataQualityPayload = {
  generated_at: '',
  source: 'database_quality_contract',
  summary: {
    score: 0,
    level: 'attention',
    issue_count: 0,
    failed_tests: 0,
    passed_tests: 0,
    total_tests: 0,
    p0: 0,
    p1: 0,
    coverage: 0,
    next_action: '等待数据质量体检。',
    primary_owner: '数据治理台'
  },
  dimensions: [],
  issue_queue: [],
  test_suites: [],
  lineage: [],
  runbook: []
};

type DataQualityJobStatus = 'pending' | 'running' | 'success' | 'failed' | string;

interface DataQualityJobRecord {
  id: string;
  job_id?: string;
  status?: DataQualityJobStatus;
  error_message?: string | null;
  finished_at?: string | null;
  result?: Record<string, unknown>;
  [key: string]: unknown;
}

interface DataQualityJobResult {
  job_id: string;
  job: DataQualityJobRecord;
  result?: {
    source?: string;
    generated_at?: string;
    summary?: DataQualityPayload['summary'];
    issue_count?: number;
    failed_tests?: number;
    [key: string]: unknown;
  } | null;
}

interface DataQualityScanState {
  id: string;
  status: DataQualityJobStatus;
  attempts: number;
  message: string;
  job?: DataQualityJobRecord;
  result?: DataQualityJobResult['result'];
}

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, RouterLink, NgxEchartsDirective, ButtonModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page data-quality-page">
      <header class="data-quality-hero atlas-split-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">数据质量治理</span>
          <h1>数据质量中心</h1>
          <p>以数据库体检结果驱动主数据、库存、采购、履约和应收治理，失败测试进入整改队列并写入审计。</p>
          <div class="atlas-actions-row">
            <button
              pButton
              type="button"
              (click)="createPrimaryRemediation()"
              [loading]="creatingId() === primaryIssueId()"
              [disabled]="!primaryIssue() || creatingId() !== null"
              aria-label="创建首要数据质量整改任务"
            >
              <i class="pi pi-send"></i>
              创建首要整改
            </button>
            <button pButton type="button" severity="secondary" (click)="startScan()" [loading]="scanning()" [disabled]="loading()" aria-label="后台扫描数据质量">
              <i class="pi pi-play"></i>
              后台扫描
            </button>
            <button pButton type="button" severity="secondary" (click)="load()" [loading]="loading()" [disabled]="scanning()" aria-label="刷新数据质量体检">
              <i class="pi pi-refresh"></i>
              刷新体检
            </button>
            <a pButton severity="info" routerLink="/app/system/audit">
              <i class="pi pi-history"></i>
              审计追踪
            </a>
          </div>
        </div>

        <div class="quality-score-card">
          <span>质量评分</span>
          <strong>{{ data().summary.score }}</strong>
          <p-progressbar [value]="data().summary.score" [showValue]="false" />
          <em>{{ data().summary.failed_tests }} 个失败测试 / {{ data().summary.issue_count }} 条治理记录</em>
          @if (scanJob(); as job) {
            <div class="quality-scan-status" [class.success]="job.status === 'success'" [class.failed]="job.status === 'failed'" aria-live="polite">
              <p-tag [severity]="jobSeverity(job.status)" [value]="jobStatusLabel(job.status)" />
              <span>{{ job.message }}</span>
              <em>{{ job.job?.finished_at ? date(job.job?.finished_at) : job.id }}</em>
            </div>
          }
        </div>

        <aside class="quality-rings quality-governance-stack">
          <article>
            <span>整改负责人</span>
            <strong>{{ data().summary.primary_owner }}</strong>
            <em>{{ data().summary.next_action }}</em>
          </article>
          <article>
            <span>测试覆盖</span>
            <strong>{{ data().summary.coverage }}%</strong>
            <em>{{ data().summary.p0 }} 个 P0 / {{ data().summary.p1 }} 个 P1</em>
          </article>
          <article>
            <span>最近体检</span>
            <strong>{{ generatedAt() }}</strong>
            <em>{{ data().source }}</em>
          </article>
        </aside>
      </header>

      <section class="quality-grid">
        <article class="atlas-panel quality-command-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">治理指挥层</span>
              <h2>质量测试、责任人和整改 SLA</h2>
            </div>
            <p-tag [severity]="statusSeverity(data().summary.level)" [value]="levelLabel(data().summary.level)" />
          </div>

          <div class="quality-command-summary" aria-label="数据质量摘要">
            <article>
              <span>通过测试</span>
              <strong>{{ data().summary.passed_tests }}</strong>
              <em>{{ data().summary.total_tests }} 个测试</em>
            </article>
            <article>
              <span>失败测试</span>
              <strong>{{ data().summary.failed_tests }}</strong>
              <em>按影响链路排序</em>
            </article>
            <article>
              <span>P0 阻塞</span>
              <strong>{{ data().summary.p0 }}</strong>
              <em>4 小时内处理</em>
            </article>
            <article>
              <span>治理记录</span>
              <strong>{{ compact(data().summary.issue_count) }}</strong>
              <em>进入任务异常中心</em>
            </article>
          </div>
          <div class="quality-action-strip" aria-label="数据质量治理入口">
            <a class="business-data-row" routerLink="/app/integrations">
              <i class="pi pi-sitemap"></i>
              接口契约复核
            </a>
            <a class="business-data-row" routerLink="/app/rules">
              <i class="pi pi-sliders-h"></i>
              规则命中复盘
            </a>
            <a class="business-data-row" routerLink="/app/notifications">
              <i class="pi pi-bell"></i>
              整改任务队列
            </a>
            <a class="business-data-row" routerLink="/app/reports">
              <i class="pi pi-chart-bar"></i>
              质量报告归档
            </a>
          </div>

          @if (loading()) {
            <p-skeleton height="96px" />
          } @else {
            <div class="quality-dimension-strip">
              @for (dimension of data().dimensions; track dimension.key) {
                <article [class.blocked]="dimension.status === 'blocked'" [class.attention]="dimension.status === 'attention'">
                  <div>
                    <span>{{ dimension.label }} · {{ dimension.owner }}</span>
                    <strong>{{ dimension.score }}%</strong>
                  </div>
                  <p-progressbar [value]="dimension.score" [showValue]="false" />
                  <em>{{ dimension.failed }} 条异常 / {{ dimension.total }} 条记录</em>
                </article>
              }
            </div>
          }
        </article>

        <article class="atlas-panel quality-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">维度覆盖</span>
              <h2>模块质量雷达</h2>
            </div>
            <p-tag [severity]="data().summary.score >= 85 ? 'success' : 'warn'" [value]="data().summary.score >= 85 ? '稳定' : '需治理'" />
          </div>
          @if (loading()) {
            <p-skeleton height="320px" />
          } @else {
            <div class="quality-chart" echarts [options]="qualityChart()"></div>
          }
        </article>

        <article class="atlas-panel quality-issue-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">整改队列</span>
              <h2>质量问题队列</h2>
            </div>
            <p-tag [severity]="data().issue_queue.length ? 'warn' : 'success'" [value]="data().issue_queue.length ? data().issue_queue.length + ' 项' : '清零'" />
          </div>
          @if (loading()) {
            <p-skeleton height="86px" />
            <p-skeleton height="86px" />
            <p-skeleton height="86px" />
          } @else if (!data().issue_queue.length) {
            <div class="quality-empty">
              <strong>核心链路数据完整</strong>
              <span>继续通过审计日志、报表和服务契约复核异常动作。</span>
            </div>
          } @else {
            <div class="quality-issue-stack">
              @for (issue of data().issue_queue; track issue.id) {
                <article class="quality-issue-card" [class.p0]="issue.priority === 'P0'" [class.p1]="issue.priority === 'P1'">
                  <p-tag [severity]="prioritySeverity(issue.priority)" [value]="issue.priority" />
                  <div>
                    <span>{{ issue.module }} · {{ issue.dimension }} · {{ issue.owner }} · SLA {{ issue.sla }}</span>
                    <strong>{{ issue.title }}</strong>
                    <em>{{ issue.evidence }}</em>
                  </div>
                  <div class="quality-issue-actions">
                    <a pButton [text]="true" size="small" [routerLink]="cleanPath(issue.path)" [attr.aria-label]="'查看来源 ' + issue.title">
                      <i class="pi pi-arrow-up-right"></i>
                      来源
                    </a>
                    <button
                      pButton
                      type="button"
                      size="small"
                      severity="secondary"
                      [loading]="creatingId() === issue.id"
                      [disabled]="creatingId() !== null"
                      (click)="createRemediation(issue)"
                      [attr.aria-label]="'创建整改任务 ' + issue.title"
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

        <article class="atlas-panel quality-runbook-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">Runbook</span>
              <h2>整改运行手册</h2>
            </div>
          </div>
          <div class="quality-runbook-list">
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

        <article class="atlas-panel quality-lineage-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">血缘链路</span>
              <h2>数据链路状态</h2>
            </div>
          </div>
          <div class="quality-lineage-list">
            @for (item of data().lineage; track item.from + item.to) {
              <article [class.blocked]="item.status === 'blocked'" [class.attention]="item.status === 'attention'">
                <p-tag [severity]="statusSeverity(item.status)" [value]="levelLabel(item.status)" />
                <strong>{{ item.from }} → {{ item.to }}</strong>
                <span>{{ item.label }}</span>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel quality-suite-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">测试套件</span>
              <h2>数据质量测试明细</h2>
            </div>
          </div>
          <div class="quality-suite-table">
            @for (suite of data().test_suites; track suite.id) {
              <article>
                <div>
                  <strong>{{ suite.name }}</strong>
                  <span>{{ suite.owner }} · {{ suite.scope }} · {{ suite.slo }}</span>
                </div>
                <p-tag [severity]="statusSeverity(suite.status)" [value]="suite.passed + '/' + (suite.passed + suite.failed)" />
              </article>
            }
          </div>
        </article>
      </section>
    </section>
  `
})
export class DataQualityPage implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);
  private scanJobTimer: ReturnType<typeof setTimeout> | null = null;

  protected readonly loading = signal(false);
  protected readonly scanning = signal(false);
  protected readonly creatingId = signal<string | null>(null);
  protected readonly scanJob = signal<DataQualityScanState | null>(null);
  protected readonly data = signal<DataQualityPayload>(EMPTY_DATA_QUALITY);
  protected readonly primaryIssue = computed(() => this.data().issue_queue[0] ?? null);
  protected readonly primaryIssueId = computed(() => this.primaryIssue()?.id ?? '');
  protected readonly generatedAt = computed(() => dateText(this.data().generated_at));
  protected readonly qualityChart = computed<EChartsCoreOption>(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    radar: compactRadar(
      this.data().dimensions.map(item => ({ name: item.label, max: 100 })),
      { radius: '58%', axisName: { color: 'rgba(226,239,255,.78)', fontSize: 11, fontWeight: 700 } }
    ),
    series: [{
      type: 'radar',
      areaStyle: { color: 'rgba(45,212,191,.2)' },
      lineStyle: { color: '#2dd4bf', width: 3 },
      symbolSize: 7,
      data: [{ value: this.data().dimensions.map(item => item.score), name: '质量覆盖' }]
    }]
  }));

  ngOnInit(): void {
    this.load();
  }

  ngOnDestroy(): void {
    this.clearScanJobTimer();
  }

  load(): void {
    this.loading.set(true);
    this.api.get<DataQualityPayload>('operations/data-quality').pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '质量体检未加载', detail: error?.message || '请稍后重试。' });
        return of(EMPTY_DATA_QUALITY);
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(payload => this.data.set(payload));
  }

  startScan(): void {
    if (this.scanning()) {
      return;
    }
    this.scanning.set(true);
    this.api.post<DataQualityJobResult>('operations/data-quality/scan', {}).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '扫描未启动', detail: error?.message || '后台任务未创建。' });
        return of(null);
      }),
      finalize(() => this.scanning.set(false))
    ).subscribe(result => {
      if (!result) {
        return;
      }
      const status = result.job?.status || 'pending';
      if (status === 'success') {
        this.applyScanJobResult(result);
      } else if (status === 'failed') {
        this.applyScanJobResult(result);
      } else {
        this.trackScanJob(result);
        this.messages.add({ severity: 'info', summary: '扫描已入队', detail: `任务 ${result.job_id}` });
        this.scheduleScanJobPoll();
      }
    });
  }

  createPrimaryRemediation(): void {
    const issue = this.primaryIssue();
    if (issue) {
      this.createRemediation(issue);
    }
  }

  createRemediation(issue: DataQualityIssue): void {
    this.creatingId.set(issue.id);
    this.api.post('operations/data-quality/remediation', {
      issue_id: issue.id,
      title: issue.title,
      owner: issue.owner,
      priority: issue.priority,
      sla: issue.sla,
      evidence: issue.evidence,
      action: issue.action,
      path: issue.path
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '整改任务未创建', detail: error?.message || '通知未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.creatingId.set(null))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '整改任务已创建', detail: '任务已进入通知中心和当班任务队列。' });
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
      attention: '需治理',
      blocked: '阻塞'
    };
    return map[status] ?? status;
  }

  protected compact(value: unknown): string {
    return compactNumberText(value);
  }

  protected date(value: unknown): string {
    return dateText(value);
  }

  protected cleanPath(path: string): string {
    return path.split('?')[0] || '/app/data-quality';
  }

  protected jobSeverity(status: string): TagSeverity {
    if (status === 'success') {
      return 'success';
    }
    if (status === 'failed') {
      return 'danger';
    }
    if (status === 'running') {
      return 'info';
    }
    return 'warn';
  }

  protected jobStatusLabel(status: string): string {
    const map: Record<string, string> = {
      pending: '排队中',
      running: '扫描中',
      success: '已完成',
      failed: '失败'
    };
    return map[status] ?? status;
  }

  private trackScanJob(result: DataQualityJobResult): void {
    const status = result.job?.status || 'pending';
    this.scanJob.set({
      id: result.job_id,
      status,
      attempts: 0,
      message: result.job?.error_message || this.scanJobMessage(status, 0),
      job: result.job,
      result: result.result
    });
  }

  private scheduleScanJobPoll(): void {
    this.clearScanJobTimer();
    this.scanJobTimer = setTimeout(() => this.pollScanJob(), DATA_QUALITY_JOB_POLL_MS);
  }

  private pollScanJob(): void {
    const current = this.scanJob();
    if (!current || current.status === 'success' || current.status === 'failed') {
      this.clearScanJobTimer();
      return;
    }
    if (current.attempts >= DATA_QUALITY_JOB_MAX_ATTEMPTS) {
      this.scanJob.set({
        ...current,
        message: '后台仍在扫描，可稍后刷新体检结果。'
      });
      this.clearScanJobTimer();
      return;
    }

    this.api.get<DataQualityJobResult>(`operations/data-quality/jobs/${current.id}`, undefined, { silent: true }).pipe(
      catchError(error => {
        this.scanJob.set({
          ...current,
          attempts: current.attempts + 1,
          message: error?.message || '暂时无法读取扫描状态，稍后自动重试。'
        });
        return of(null);
      })
    ).subscribe(result => {
      if (!result) {
        this.scheduleScanJobPoll();
        return;
      }
      const status = this.applyScanJobResult(result, current.attempts + 1);
      if (status === 'success' || status === 'failed') {
        this.clearScanJobTimer();
      } else {
        this.scheduleScanJobPoll();
      }
    });
  }

  private applyScanJobResult(result: DataQualityJobResult, attempts = this.scanJob()?.attempts ?? 0): DataQualityJobStatus {
    const current = this.scanJob();
    const status = result.job?.status || 'pending';
    this.scanJob.set({
      id: result.job_id,
      status,
      attempts,
      message: result.job?.error_message || this.scanJobMessage(status, attempts),
      job: result.job,
      result: result.result
    });

    if (status === 'success') {
      if (current?.status !== 'success') {
        this.messages.add({ severity: 'success', summary: '扫描完成', detail: '数据质量体检结果已刷新。' });
      }
      this.load();
    } else if (status === 'failed' && current?.status !== 'failed') {
      this.messages.add({ severity: 'warn', summary: '扫描失败', detail: result.job?.error_message || '后台扫描未完成。' });
    }
    return status;
  }

  private scanJobMessage(status: string, attempts: number): string {
    if (status === 'success') {
      return '后台扫描已完成，页面正在同步最新体检结果。';
    }
    if (status === 'failed') {
      return '后台扫描失败，请查看任务错误并重试。';
    }
    if (status === 'running') {
      return `后台正在扫描主数据、仓配、采购、履约和财务链路，第 ${attempts + 1} 次检查。`;
    }
    return `扫描任务已进入 data-quality 队列，第 ${attempts + 1} 次检查。`;
  }

  private clearScanJobTimer(): void {
    if (this.scanJobTimer) {
      clearTimeout(this.scanJobTimer);
      this.scanJobTimer = null;
    }
  }
}
