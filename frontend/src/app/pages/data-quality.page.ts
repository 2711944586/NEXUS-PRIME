import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
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

@Component({
  standalone: true,
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
            <button pButton type="button" severity="secondary" (click)="load()" [loading]="loading()" aria-label="刷新数据质量体检">
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
export class DataQualityPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly creatingId = signal<string | null>(null);
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

  protected cleanPath(path: string): string {
    return path.split('?')[0] || '/app/data-quality';
  }
}
