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
import { RuleDecisionQueueItem, RuleItem, RulesPayload } from '../core/models';
import { chartLegend, compactNumberText, compactRadar, TagSeverity } from './page-utils';

const EMPTY_RULES: RulesPayload = {
  generated_at: '',
  source: 'rules_governance_contract',
  summary: {
    total: 0,
    enabled: 0,
    hits: 0,
    risks: 0,
    p0: 0,
    p1: 0,
    queue_count: 0,
    automation_rate: 0,
    coverage: 0,
    primary_owner: '规则治理台',
    next_action: '等待规则命中数据。'
  },
  items: [],
  decision_queue: [],
  domains: [],
  decision_map: [],
  runbook: []
};

@Component({
  standalone: true,
  imports: [CommonModule, RouterLink, NgxEchartsDirective, ButtonModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page rules-engine-page">
      <header class="atlas-split-hero rules-engine-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">规则治理</span>
          <h1>规则引擎中心</h1>
          <p>把补货、采购审批、应收信用、报表归档和关键写入审计沉淀为可复核决策表，风险命中进入任务队列。</p>
          <div class="atlas-actions-row">
            <button
              pButton
              type="button"
              (click)="createPrimaryReview()"
              [loading]="reviewingId() === primaryReviewId()"
              [disabled]="loading() || !selectedRule() || reviewingId() !== null"
              aria-label="创建首要规则复核任务"
            >
              <i class="pi pi-flag"></i>
              创建首要复核
            </button>
            <button pButton type="button" severity="secondary" (click)="load()" [loading]="loading()" aria-label="刷新规则治理数据">
              <i class="pi pi-refresh"></i>
              刷新命中
            </button>
            <a pButton severity="info" routerLink="/app/system/audit">
              <i class="pi pi-history"></i>
              审计回放
            </a>
          </div>
        </div>

        <aside class="rules-governance-stack">
          <article>
            <span>自动化率</span>
            <strong>{{ data().summary.automation_rate }}%</strong>
            <em>{{ compact(data().summary.hits) }} 命中 / {{ compact(data().summary.risks) }} 风险</em>
          </article>
          <article>
            <span>责任人</span>
            <strong>{{ data().summary.primary_owner }}</strong>
            <em>{{ data().summary.next_action }}</em>
          </article>
          <article class="warning">
            <span>治理队列</span>
            <strong>{{ data().summary.queue_count }}</strong>
            <em>{{ data().summary.p0 }} 个 P0 / {{ data().summary.p1 }} 个 P1</em>
          </article>
        </aside>
      </header>

      <section class="rules-engine-grid rules-governance-grid">
        <article class="atlas-panel rules-command-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">治理指挥层</span>
              <h2>规则健康、负责人和 SLA</h2>
            </div>
            <p-tag [severity]="data().summary.p0 ? 'danger' : data().summary.queue_count ? 'warn' : 'success'" [value]="data().summary.p0 ? '阻塞' : data().summary.queue_count ? '需复核' : '稳定'" />
          </div>

          <div class="rules-command-summary" aria-label="规则治理摘要">
            <article>
              <span>启用规则</span>
              <strong>{{ data().summary.enabled }}</strong>
              <em>{{ data().summary.total }} 条规则</em>
            </article>
            <article>
              <span>命中对象</span>
              <strong>{{ compact(data().summary.hits) }}</strong>
              <em>{{ data().source }}</em>
            </article>
            <article>
              <span>风险对象</span>
              <strong>{{ compact(data().summary.risks) }}</strong>
              <em>已按 P0/P1 排序</em>
            </article>
            <article>
              <span>契约覆盖</span>
              <strong>{{ data().summary.coverage }}%</strong>
              <em>DMN 表 + 审计证据</em>
            </article>
          </div>

          @if (loading()) {
            <p-skeleton height="102px" />
          } @else {
            <div class="rules-domain-strip">
              @for (domain of data().domains; track domain.key) {
                <button
                  type="button"
                  [class.active]="selectedRuleId() === domain.key"
                  [class.blocked]="domain.status === 'blocked'"
                  [class.attention]="domain.status === 'attention'"
                  (click)="selectRule(domain.key)"
                  [attr.aria-label]="'查看规则域 ' + domain.label"
                >
                  <span>{{ domain.label }} · {{ domain.owner }}</span>
                  <strong>{{ compact(domain.risks) }}</strong>
                  <p-progressbar [value]="domain.coverage" [showValue]="false" />
                  <em>{{ compact(domain.hits) }} 命中 · {{ metricLabel(domain.metric) }}</em>
                </button>
              }
            </div>
          }
        </article>

        <article class="atlas-panel rules-chart-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">规则命中</span>
              <h2>规则命中与风险对象</h2>
            </div>
            <p-tag severity="info" value="实时聚合" />
          </div>
          @if (loading()) {
            <p-skeleton height="320px" />
          } @else {
            <div class="rules-chart" echarts [options]="ruleChart()"></div>
          }
        </article>

        <article class="atlas-panel rules-chart-panel rules-radar-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">控制雷达</span>
              <h2>规则覆盖面</h2>
            </div>
            <p-tag [severity]="data().summary.coverage >= 92 ? 'success' : 'warn'" [value]="data().summary.coverage + '%'" />
          </div>
          @if (loading()) {
            <p-skeleton height="320px" />
          } @else {
            <div class="rules-chart compact" echarts [options]="radarChart()"></div>
          }
        </article>

        <article class="atlas-panel rules-decision-panel wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">DMN 决策表</span>
              <h2>{{ selectedRuleName() }}</h2>
            </div>
            @if (selectedRule()) {
              <p-tag [severity]="statusSeverity(selectedRule()!.status)" [value]="selectedRule()!.hit_policy" />
            }
          </div>

          @if (loading()) {
            <p-skeleton height="280px" />
          } @else if (!selectedRule()) {
            <div class="rules-empty-state">
              <strong>暂无规则命中数据</strong>
              <span>刷新规则引擎或先完成业务数据初始化。</span>
            </div>
          } @else {
            <div class="rules-decision-workbench">
              <aside class="rules-selected-brief">
                <p-tag [severity]="prioritySeverity(selectedRule()!.priority)" [value]="selectedRule()!.priority" />
                <strong>{{ selectedRule()!.domain }} · {{ selectedRule()!.owner }}</strong>
                <span>{{ selectedRule()!.trigger }}</span>
                <em>{{ selectedRule()!.risk_note }}</em>
                <div class="rules-selected-metrics">
                  <article><span>命中</span><strong>{{ compact(selectedRule()!.hit_count) }}</strong></article>
                  <article><span>风险</span><strong>{{ compact(selectedRule()!.risk_count) }}</strong></article>
                  <article><span>信心</span><strong>{{ selectedRule()!.confidence }}%</strong></article>
                </div>
                <a pButton size="small" [routerLink]="cleanPath(selectedRule()!.path)" [attr.aria-label]="'打开来源模块 ' + selectedRule()!.name">
                  <i class="pi pi-arrow-up-right"></i>
                  来源模块
                </a>
              </aside>

              <div class="rules-decision-table">
                <div class="rules-io-grid">
                  <section>
                    <span>输入列</span>
                    @for (input of selectedRule()!.decision_table.inputs; track input.id) {
                      <article>
                        <strong>{{ input.label }}</strong>
                        <em>{{ input.source }}</em>
                        <code>{{ input.value }}</code>
                      </article>
                    }
                  </section>
                  <section>
                    <span>输出列</span>
                    @for (output of selectedRule()!.decision_table.outputs; track output.id) {
                      <article>
                        <strong>{{ output.label }}</strong>
                        <em>{{ output.source }}</em>
                        <code>{{ output.value }}</code>
                      </article>
                    }
                  </section>
                </div>

                <div class="rules-row-list">
                  @for (row of selectedRule()!.decision_table.rows; track row.id) {
                    <article [class.blocked]="row.status === 'blocked'" [class.attention]="row.status === 'attention'">
                      <p-tag [severity]="prioritySeverity(row.priority)" [value]="row.priority" />
                      <div>
                        <strong>{{ row.id }} · {{ row.action }}</strong>
                        <span>{{ row.conditions.join(' / ') }}</span>
                        <em>{{ row.outputs.join(' / ') }}</em>
                      </div>
                      <div>
                        <span>命中</span>
                        <strong>{{ compact(row.hit_count) }}</strong>
                        <em>风险 {{ compact(row.risk_count) }}</em>
                      </div>
                    </article>
                  }
                </div>
              </div>
            </div>
          }
        </article>

        <article class="atlas-panel rules-queue-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">复核队列</span>
              <h2>风险决策队列</h2>
            </div>
            <p-tag [severity]="data().decision_queue.length ? 'warn' : 'success'" [value]="data().decision_queue.length ? data().decision_queue.length + ' 项' : '清零'" />
          </div>
          @if (loading()) {
            <p-skeleton height="92px" />
            <p-skeleton height="92px" />
          } @else if (!data().decision_queue.length) {
            <div class="rules-empty-state">
              <strong>规则风险清零</strong>
              <span>继续按 runbook 做抽样复核和审计回放。</span>
            </div>
          } @else {
            <div class="rules-queue-list">
              @for (item of data().decision_queue; track item.id) {
                <article [class.p0]="item.priority === 'P0'" [class.p1]="item.priority === 'P1'">
                  <p-tag [severity]="prioritySeverity(item.priority)" [value]="item.priority" />
                  <div>
                    <span>{{ item.domain }} · {{ item.owner }} · SLA {{ item.sla }}</span>
                    <strong>{{ item.title }}</strong>
                    <em>{{ item.evidence }}</em>
                  </div>
                  <div class="rules-queue-actions">
                    <a pButton [text]="true" size="small" [routerLink]="cleanPath(item.path)" [attr.aria-label]="'查看规则来源 ' + item.title">
                      <i class="pi pi-arrow-up-right"></i>
                      来源
                    </a>
                    <button
                      pButton
                      type="button"
                      size="small"
                      severity="secondary"
                      [loading]="reviewingId() === item.id"
                      [disabled]="reviewingId() !== null"
                      (click)="createQueueReview(item)"
                      [attr.aria-label]="'创建规则复核任务 ' + item.title"
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

        <article class="atlas-panel rules-boundary-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">服务边界</span>
              <h2>规则微服务拆分面</h2>
            </div>
          </div>
          <div class="rules-boundary-list">
            @for (rule of data().items; track rule.id) {
              <button type="button" [class.active]="selectedRuleId() === rule.id" (click)="selectRule(rule.id)" [attr.aria-label]="'查看服务边界 ' + rule.name">
                <strong>{{ rule.service_boundary.service }}</strong>
                <span>{{ rule.service_boundary.contract }}</span>
                <em>{{ rule.service_boundary.event }}</em>
              </button>
            }
          </div>
        </article>

        <article class="atlas-panel rules-map-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">闭环链路</span>
              <h2>规则到任务的路径</h2>
            </div>
          </div>
          <div class="rules-map-list">
            @for (item of data().decision_map; track item.from + item.to) {
              <article [class.blocked]="item.status === 'blocked'" [class.attention]="item.status === 'attention'">
                <p-tag [severity]="statusSeverity(item.status)" [value]="levelLabel(item.status)" />
                <strong>{{ item.from }} → {{ item.to }}</strong>
                <span>{{ item.label }}</span>
              </article>
            }
          </div>
        </article>

        <article class="atlas-panel rules-runbook-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">Runbook</span>
              <h2>规则复核运行手册</h2>
            </div>
          </div>
          <div class="rules-runbook-list">
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
export class RulesEnginePage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly reviewingId = signal<string | null>(null);
  protected readonly selectedRuleId = signal('');
  protected readonly data = signal<RulesPayload>(EMPTY_RULES);
  protected readonly selectedRule = computed(() => {
    const rules = this.data().items;
    return rules.find(item => item.id === this.selectedRuleId()) ?? rules[0] ?? null;
  });
  protected readonly selectedRuleName = computed(() => this.selectedRule()?.name ?? '规则决策表');
  protected readonly primaryQueueItem = computed(() => this.data().decision_queue[0] ?? null);
  protected readonly primaryReviewId = computed(() => this.primaryQueueItem()?.id ?? this.selectedRule()?.id ?? 'primary-rule-review');
  protected readonly ruleChart = computed<EChartsCoreOption>(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: chartLegend('top', 'rgba(226,239,255,.82)'),
    grid: { left: 18, right: 18, top: 42, bottom: 28, containLabel: true },
    xAxis: {
      type: 'category',
      data: this.data().items.map(item => item.domain),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: 'rgba(226,239,255,.68)', fontWeight: 700 }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: 'rgba(226,239,255,.58)' },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } }
    },
    series: [
      { name: '命中', type: 'bar', data: this.data().items.map(item => item.hit_count), itemStyle: { color: '#14b8a6', borderRadius: [10, 10, 2, 2] } },
      { name: '风险', type: 'line', smooth: true, data: this.data().items.map(item => item.risk_count), lineStyle: { width: 3, color: '#f59e0b' }, itemStyle: { color: '#f59e0b' } }
    ]
  }));
  protected readonly radarChart = computed<EChartsCoreOption>(() => ({
    backgroundColor: 'transparent',
    tooltip: {},
    radar: compactRadar(
      this.data().items.map(item => ({ name: item.domain, max: 100 })),
      { radius: '58%', axisName: { color: 'rgba(226,239,255,.78)', fontSize: 11, fontWeight: 700 } }
    ),
    series: [{
      type: 'radar',
      areaStyle: { opacity: .18, color: 'rgba(45,212,191,.22)' },
      lineStyle: { width: 3, color: '#2dd4bf' },
      symbolSize: 7,
      data: [{ name: '契约覆盖', value: this.data().items.map(item => item.coverage) }]
    }]
  }));

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.get<RulesPayload>('operations/rules').pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '规则治理未加载', detail: error?.message || '请稍后重试。' });
        return of(EMPTY_RULES);
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(payload => {
      this.data.set(payload);
      if (!payload.items.some(item => item.id === this.selectedRuleId())) {
        this.selectedRuleId.set(payload.decision_queue[0]?.rule_id ?? payload.items[0]?.id ?? '');
      }
    });
  }

  protected selectRule(ruleId: string): void {
    this.selectedRuleId.set(ruleId);
  }

  protected createPrimaryReview(): void {
    const queueItem = this.primaryQueueItem();
    if (queueItem) {
      this.createQueueReview(queueItem);
      return;
    }
    const rule = this.selectedRule();
    if (rule) {
      this.createRuleReview(rule);
    }
  }

  protected createQueueReview(item: RuleDecisionQueueItem): void {
    this.reviewingId.set(item.id);
    this.postReview({
      rule_id: item.rule_id,
      rule_name: item.title.replace(/复核$/, ''),
      owner: item.owner,
      priority: item.priority,
      sla: item.sla,
      evidence: item.evidence,
      action: item.action,
      path: item.path
    }, item.title);
  }

  private createRuleReview(rule: RuleItem): void {
    this.reviewingId.set(rule.id);
    this.postReview({
      rule_id: rule.id,
      rule_name: rule.name,
      owner: rule.owner,
      priority: rule.priority,
      sla: rule.sla,
      evidence: rule.risk_note || rule.evidence,
      action: rule.action,
      path: rule.path
    }, rule.name);
  }

  private postReview(payload: Record<string, string>, detail: string): void {
    this.api.post('operations/rules/review', payload).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '复核任务未创建', detail: error?.message || '规则任务未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.reviewingId.set(null))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: '复核任务已创建', detail: `${detail} 已进入任务异常中心。` });
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
      attention: '需复核',
      blocked: '阻塞'
    };
    return map[status] ?? status;
  }

  protected cleanPath(path: string): string {
    return path.split('?')[0] || '/app/rules';
  }

  protected compact(value: unknown): string {
    return compactNumberText(value);
  }

  protected metricLabel(metric: string): string {
    return metric
      .replace(/^nexus_rule_/, '')
      .replace(/_hits$/, '')
      .replace(/_/g, ' · ');
  }

}
