import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, ElementRef, inject, OnInit, signal, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { ProgressBarModule } from 'primeng/progressbar';
import { SkeletonModule } from 'primeng/skeleton';
import { TabsModule } from 'primeng/tabs';
import { TagModule } from 'primeng/tag';
import { TextareaModule } from 'primeng/textarea';
import { catchError, finalize, firstValueFrom, forkJoin, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { AiChatStreamError, streamAiChat } from '../core/ai-chat-stream';
import {
  AiActionDraft,
  AiDiagnostics,
  AiDraftConfirmResult,
  AiDraftRejectResult,
  AiSettings,
  ExecutiveAnalytics,
  ManufacturingCommandCenter,
  StructuredOperationsAnalysis
} from '../core/models';
import { NexusRevealDirective, NexusSpotlightDirective, SceneBackgroundComponent } from '../motion';
import type { AiGuardrailTone } from './ai-guardrails';
import {
  aiDraftStatusLabel,
  aiDraftStatusTone,
  buildAiDraftActions,
  buildAiGuardrails,
  summarizeAiActionDraft
} from './ai-guardrails';
import { chartLegend, compactMoneyText, compactNumberText, dateText } from './page-utils';

interface AiSession {
  id: number;
  title: string;
  created_at?: string | null;
  last_message_at?: string | null;
  message_count?: number;
}

interface AiMessage {
  id?: number;
  role: 'user' | 'assistant';
  content: string;
  tokens?: number;
  created_at?: string | null;
  pending?: boolean;
  source?: string;
  provider_warning?: string | null;
}

interface AiChatResult {
  session: AiSession;
  message: AiMessage;
  source?: string;
  provider_warning?: string | null;
  usage?: Record<string, unknown>;
}

type AnalysisScenario = 'daily_brief' | 'inventory' | 'procurement' | 'receivables';
type ChartMode = 'trend' | 'warehouse' | 'supplier';

const EMPTY_COMMAND_CENTER: ManufacturingCommandCenter = {
  kpis: { order_amount: 0, stock_quantity: 0, low_stock_products: 0, pending_purchase: 0, overdue_amount: 0 },
  warehouse_heat: [],
  flows: [],
  risks: []
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
  action_queue: []
};

const EMPTY_SETTINGS: AiSettings = {
  analysis_mode: 'local',
  local_analysis_enabled: true,
  external_configured: false,
  external_source: 'none',
  external_base: '',
  credential_masked: '',
  model: 'deepseek-chat',
  can_use_local: true,
  has_user_credential: false,
  preferences_updated_at: null,
  dashboard_scope: 'operations'
};

const EMPTY_DIAGNOSTICS: AiDiagnostics = {
  overall_status: 'attention',
  analysis_mode: 'local',
  local: { available: true, status: 'ready', message: '' },
  external: {
    configured: false,
    reachable: null,
    status: 'not_configured',
    message: '',
    latency_ms: null,
    base: '',
    source: 'none',
    credential_masked: ''
  },
  snapshot: {
    low_stock_count: 0,
    pending_purchase_count: 0,
    overdue_receivable_count: 0,
    overdue_amount: 0,
    recent_report_count: 0
  },
  sample_actions: []
};

const EMPTY_STRUCTURED: StructuredOperationsAnalysis = {
  scenario: 'daily_brief',
  headline: '',
  summary: '',
  generated_at: null,
  insight_cards: [],
  action_items: [],
  related_records: {
    low_stock: [],
    pending_purchase: [],
    overdue_receivables: [],
    recent_reports: []
  }
};

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    NgxEchartsDirective,
    ButtonModule,
    DialogModule,
    InputTextModule,
    ProgressBarModule,
    SkeletonModule,
    SceneBackgroundComponent,
    TabsModule,
    TagModule,
    TextareaModule,
    NexusRevealDirective,
    NexusSpotlightDirective
  ],
  template: `
    <section class="ops-atlas-page ai-command-page ai-command-studio">
      <nexus-scene-background image="/images/control-panel-wide.jpg"></nexus-scene-background>

      <header class="ai-command-hero refined-ai-hero" nexusReveal nexusSpotlight>
        <div class="hero-narrative">
          <span class="atlas-kicker">经营分析</span>
          <h1>经营分析台</h1>
          <p>连接本地经营数据和外部推理服务，按库存、采购、履约、应收生成可追踪分析。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="openSettings()" aria-label="打开分析服务设置">
              <i class="pi pi-cog"></i>
              分析服务设置
            </button>
            <button pButton type="button" severity="secondary" (click)="runDiagnostics()" [loading]="diagnosticsLoading()" aria-label="执行诊断">
              <i class="pi pi-wave-pulse"></i>
              运行诊断
            </button>
            <button pButton type="button" severity="contrast" (click)="runStructuredAnalysis(activeScenario())" [loading]="structuredLoading()" aria-label="刷新结构化分析">
              <i class="pi pi-sparkles"></i>
              刷新经营摘要
            </button>
          </div>
        </div>

        <section class="ai-hero-chart" aria-label="经营分析首屏图表">
          <div class="ai-hero-chart-head">
            <span>销售 / 回款</span>
            <strong>{{ compactMoney(analytics().kpis.total_sales) }}</strong>
          </div>
          <div class="ai-hero-mini-chart" echarts [options]="primaryChart()"></div>
        </section>

        <aside class="ai-live-brief">
          <article>
            <span>服务模式</span>
            <strong>{{ modeLabel(settings().analysis_mode) }}</strong>
            <em>{{ aiEndpointLabel() }}</em>
          </article>
          <article>
            <span>诊断状态</span>
            <strong>{{ diagnosticsToneLabel(diagnostics().overall_status) }}</strong>
            <em>{{ diagnostics().external.latency_ms ? diagnostics().external.latency_ms + ' ms' : '即时检测' }}</em>
          </article>
          <article>
            <span>当班风险</span>
            <strong>{{ command().kpis.low_stock_products + analytics().kpis.pending_purchase }}</strong>
            <em>低库存与待审批采购</em>
          </article>
          <article>
            <span>外部接口</span>
            <strong>{{ settings().external_configured ? '已接入' : '未接入' }}</strong>
            <em>{{ settings().credential_masked || '可在设置中填写' }}</em>
          </article>
        </aside>
      </header>

      <section class="ai-decision-grid ai-decision-grid-expanded">
        <article class="atlas-panel ai-briefing-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">经营摘要</span>
              <h2>{{ structured().headline || '当班经营总览' }}</h2>
            </div>
            <div class="atlas-actions-row compact">
              <button
                pButton
                type="button"
                [text]="activeScenario() !== 'daily_brief'"
                [severity]="activeScenario() === 'daily_brief' ? 'contrast' : undefined"
                (click)="runStructuredAnalysis('daily_brief')"
              >
                全局
              </button>
              <button
                pButton
                type="button"
                [text]="activeScenario() !== 'inventory'"
                [severity]="activeScenario() === 'inventory' ? 'contrast' : undefined"
                (click)="runStructuredAnalysis('inventory')"
              >
                库存
              </button>
              <button
                pButton
                type="button"
                [text]="activeScenario() !== 'procurement'"
                [severity]="activeScenario() === 'procurement' ? 'contrast' : undefined"
                (click)="runStructuredAnalysis('procurement')"
              >
                采购
              </button>
              <button
                pButton
                type="button"
                [text]="activeScenario() !== 'receivables'"
                [severity]="activeScenario() === 'receivables' ? 'contrast' : undefined"
                (click)="runStructuredAnalysis('receivables')"
              >
                应收
              </button>
            </div>
          </div>

          <div class="ai-structured-summary">
            <p>{{ structured().summary || '正在读取库存、采购、履约和收款数据。' }}</p>
            @if (structured().generated_at) {
              <span>更新时间 {{ date(structured().generated_at) }}</span>
            }
          </div>

          <div class="ai-metric-mosaic">
            @for (card of briefCards(); track card.title) {
              <a [routerLink]="card.path" [class.warning]="card.tone === 'warning'" [class.danger]="card.tone === 'danger'">
                <span>{{ card.title }}</span>
                <strong>{{ card.metric }}</strong>
                <em>{{ card.note }}</em>
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel ai-action-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">行动队列</span>
              <h2>行动队列</h2>
            </div>
            <p-tag [severity]="diagnostics().overall_status === 'ready' ? 'success' : diagnostics().overall_status === 'degraded' ? 'warn' : 'danger'" [value]="diagnosticsToneLabel(diagnostics().overall_status)" />
          </div>

          <div class="ai-action-list">
            @for (action of briefActions(); track action.title) {
              <a [routerLink]="action.path" [class.high]="action.priority === 'high'">
                <span>{{ action.priority === 'high' ? '高优先' : '常规' }}</span>
                <strong>{{ action.title }}</strong>
                <p>{{ action.description }}</p>
              </a>
            }
            @for (action of actionQueue(); track action.title + action.module) {
              <a [routerLink]="action.path" [class.high]="action.priority === 'high'">
                <span>{{ action.module }}</span>
                <strong>{{ action.title }}</strong>
                <p>{{ action.description }}</p>
                <em>{{ action.metric }}</em>
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel ai-guardrail-panel" nexusReveal [nexusRevealDelay]="120" nexusSpotlight>
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">安全边界</span>
              <h2>AI 决策护栏</h2>
            </div>
            <p-tag [severity]="tagSeverity(trustGuardrail().tone)" [value]="trustGuardrail().title" />
          </div>

          <div class="ai-guardrail-list" aria-label="AI 决策护栏">
            @for (guardrail of guardrails(); track guardrail.key) {
              <div class="ai-guardrail-row" [class.warning]="guardrail.tone === 'warning'" [class.danger]="guardrail.tone === 'danger'" [class.success]="guardrail.tone === 'success'">
                <span>{{ guardrail.label }}</span>
                <strong>{{ guardrail.title }}</strong>
                <p>{{ guardrail.detail }}</p>
              </div>
            }
          </div>

          <div class="ai-draft-action-list" aria-label="AI 草稿动作">
            @for (action of draftActions(); track action.id) {
              <div class="ai-draft-action-row" [class.high]="action.priority === 'high'">
                <span>{{ action.controlLabel }}</span>
                <strong>{{ action.title }}</strong>
                <p>{{ action.description }}</p>
                <div class="ai-draft-action-controls">
                  <button pButton type="button" [text]="true" severity="secondary" (click)="loadDraftPrompt(action.prompt)" aria-label="将 AI 草稿动作写入提问框">
                    <i class="pi pi-pencil"></i>
                    写入提问
                  </button>
                  <a pButton [text]="true" [routerLink]="action.path" aria-label="进入对应业务页面确认动作">
                    <i class="pi pi-arrow-right"></i>
                    进入确认页
                  </a>
                </div>
              </div>
            }
          </div>

          <div class="ai-draft-review-head">
            <div>
              <span class="atlas-kicker">人工确认</span>
              <h3>待确认草稿</h3>
            </div>
            <div class="ai-draft-review-meta">
              <p-tag [severity]="pendingDraftCount() ? 'warn' : 'success'" [value]="pendingDraftCount() + ' 项'" />
              <button pButton type="button" [text]="true" severity="secondary" (click)="loadAiDrafts()" [loading]="draftsLoading()" aria-label="刷新 AI 待确认草稿">
                <i class="pi pi-refresh"></i>
              </button>
            </div>
          </div>

          @if (draftsLoading()) {
            <div class="ai-draft-action-list ai-draft-review-list" aria-busy="true" aria-label="AI 待确认草稿加载中">
              <p-skeleton height="82px" />
              <p-skeleton height="82px" />
            </div>
          } @else if (visibleAiDrafts().length) {
            <div class="ai-draft-action-list ai-draft-review-list" aria-label="AI 待确认草稿">
              @for (draftItem of visibleAiDrafts(); track draftItem.id) {
                <div class="ai-draft-action-row ai-draft-review-row" [class.high]="draftItem.status === 'draft'">
                  <div class="ai-draft-review-title">
                    <p-tag [severity]="tagSeverity(draftStatusTone(draftItem.status))" [value]="draftStatusLabel(draftItem.status)" />
                    <strong>{{ draftItem.title }}</strong>
                  </div>
                  <p>{{ draftSummary(draftItem) }}</p>
                  <span>{{ date(draftItem.created_at) }}</span>
                  <div class="ai-draft-action-controls">
                    <button pButton type="button" size="small" severity="success" (click)="confirmAiDraft(draftItem)" [loading]="draftReviewing() === draftActionKey(draftItem, 'confirm')" [disabled]="draftReviewing() !== null" aria-label="确认 AI 草稿并生成补货建议">
                      <i class="pi pi-check"></i>
                      确认
                    </button>
                    <button pButton type="button" size="small" severity="secondary" [text]="true" (click)="rejectAiDraft(draftItem)" [loading]="draftReviewing() === draftActionKey(draftItem, 'reject')" [disabled]="draftReviewing() !== null" aria-label="驳回 AI 草稿">
                      <i class="pi pi-times"></i>
                      驳回
                    </button>
                    <a pButton size="small" [text]="true" routerLink="/app/inventory/replenishment" aria-label="进入补货建议中心">
                      <i class="pi pi-arrow-right"></i>
                      补货中心
                    </a>
                  </div>
                </div>
              }
            </div>
          } @else {
            <div class="empty-state compact ai-draft-review-empty" role="status">
              <i class="pi pi-check-circle"></i>
              <strong>暂无待确认草稿</strong>
            </div>
          }
        </article>

        <article class="atlas-panel ai-settings-inline-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">AI 设置</span>
              <h2>AI 服务接入</h2>
            </div>
            <p-tag [severity]="settings().external_configured ? 'success' : 'warn'" [value]="settings().external_configured ? '已配置' : '待配置'" />
          </div>

          <div class="ai-settings-status">
            <article>
              <span>当前模式</span>
              <strong>{{ modeLabel(settings().analysis_mode) }}</strong>
              <em>{{ aiEndpointLabel() }}</em>
            </article>
            <article>
              <span>凭证</span>
              <strong>{{ settings().credential_masked || '未设置' }}</strong>
              <em>{{ settings().external_source === 'system' ? '系统配置' : settings().external_source === 'user' ? '个人配置' : '本地分析' }}</em>
            </article>
          </div>

          <div class="mode-switch compact">
            <button type="button" [class.active]="settingsDraft.analysis_mode === 'local'" (click)="settingsDraft.analysis_mode = 'local'">本地</button>
            <button type="button" [class.active]="settingsDraft.analysis_mode === 'hybrid'" (click)="settingsDraft.analysis_mode = 'hybrid'">混合</button>
            <button type="button" [class.active]="settingsDraft.analysis_mode === 'external'" (click)="settingsDraft.analysis_mode = 'external'">外部</button>
          </div>

          <div class="ai-settings-inline-form">
            <label>
              <span>Base URL</span>
              <input pInputText [(ngModel)]="settingsDraft.ai_api_base" placeholder="https://api.deepseek.com" />
            </label>
            <label>
              <span>模型</span>
              <input pInputText [(ngModel)]="settingsDraft.ai_model" placeholder="deepseek-chat" />
            </label>
            <label>
              <span>API Key</span>
              <input pInputText [(ngModel)]="settingsDraft.ai_api_key" placeholder="留空保留现有凭证" />
            </label>
          </div>

          <div class="atlas-actions-row compact">
            <button pButton type="button" (click)="saveSettings()" [loading]="settingsSaving()">
              <i class="pi pi-save"></i>
              保存 AI 设置
            </button>
            <button pButton type="button" severity="success" (click)="saveSettings(true)" [loading]="settingsSaving() || chatLoading()">
              <i class="pi pi-send"></i>
              保存并试问
            </button>
            <button pButton type="button" severity="secondary" (click)="runDiagnostics()" [loading]="diagnosticsLoading()">
              <i class="pi pi-wave-pulse"></i>
              诊断
            </button>
            <a pButton [text]="true" routerLink="/app/settings">
              <i class="pi pi-sliders-h"></i>
              全局设置
            </a>
          </div>
        </article>

        <article class="atlas-panel ai-diagnostic-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">服务诊断</span>
              <h2>服务诊断</h2>
            </div>
            <button pButton type="button" [text]="true" (click)="runDiagnostics()" [loading]="diagnosticsLoading()" aria-label="刷新服务诊断">
              <i class="pi pi-refresh"></i>
            </button>
          </div>

          <div class="ai-diagnostic-stack">
            <article [class.warning]="diagnostics().local.status !== 'ready'">
              <span>本地分析</span>
              <strong>{{ diagnostics().local.available ? '可用' : '关闭' }}</strong>
              <em>{{ diagnostics().local.message }}</em>
            </article>
            <article [class.warning]="diagnostics().external.status !== 'ready' && diagnostics().external.configured" [class.danger]="diagnostics().external.status === 'credential_invalid' || diagnostics().external.status === 'unreachable'">
              <span>外部推理</span>
              <strong>{{ diagnostics().external.configured ? diagnosticsToneLabel(diagnostics().external.status) : '未配置' }}</strong>
              <em>{{ diagnostics().external.message || '尚未启用。' }}</em>
            </article>
            <article>
              <span>诊断快照</span>
              <strong>{{ compactMoney(diagnostics().snapshot.overdue_amount) }}</strong>
              <em>{{ diagnostics().snapshot.low_stock_count }} 项低库存 / {{ diagnostics().snapshot.pending_purchase_count }} 单采购</em>
            </article>
          </div>

          <div class="ai-sample-actions">
            @for (item of diagnostics().sample_actions; track item.title) {
              <a [routerLink]="item.path">
                <strong>{{ item.title }}</strong>
                <span>{{ item.metric }}</span>
              </a>
            }
          </div>
        </article>
      </section>

      <section class="ai-workbench">
        <aside class="atlas-panel ai-session-rail">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">会话</span>
              <h2>分析会话</h2>
            </div>
            <button pButton type="button" [text]="true" (click)="createSession()" [loading]="sessionCreating()" aria-label="新建分析会话">
              <i class="pi pi-plus"></i>
            </button>
          </div>

          @if (loading()) {
            <p-skeleton height="58px" />
            <p-skeleton height="58px" />
            <p-skeleton height="58px" />
          } @else {
            <div class="ai-session-list">
              @for (session of pagedSessions(); track session.id) {
                <button type="button" [class.active]="session.id === activeSessionId()" (click)="selectSession(session)">
                  <strong>{{ session.title }}</strong>
                  <span>{{ session.message_count || 0 }} 条消息</span>
                  <em>{{ date(session.last_message_at || session.created_at) }}</em>
                </button>
              }
              @if (!sessions().length) {
                <div class="empty-state compact">
                  <i class="pi pi-comments"></i>
                  <strong>会话库已就绪</strong>
                </div>
              }
            </div>
            @if (sessions().length > sessionPageSize()) {
              <div class="atlas-pagination compact" aria-label="分析会话分页">
                <button type="button" (click)="setSessionPage(sessionPage() - 1)" [disabled]="sessionPage() <= 1" aria-label="上一页分析会话">
                  <i class="pi pi-angle-left"></i>
                </button>
                <span>{{ sessionPage() }} / {{ sessionTotalPages() }}</span>
                <button type="button" (click)="setSessionPage(sessionPage() + 1)" [disabled]="sessionPage() >= sessionTotalPages()" aria-label="下一页分析会话">
                  <i class="pi pi-angle-right"></i>
                </button>
              </div>
            }
          }
        </aside>

        <article class="atlas-panel ai-chat-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">提问</span>
              <h2>{{ activeSession()?.title || '经营异常分析' }}</h2>
            </div>
            <p-tag [severity]="chatLoading() ? 'warn' : 'success'" [value]="chatLoading() ? '分析中' : '可提问'" />
          </div>

          <div #messageStream class="ai-message-stream" aria-live="polite" aria-label="经营分析对话记录">
            @for (message of messages(); track message.id || message.content) {
              <div class="ai-message" [class.assistant]="message.role === 'assistant'" [class.pending]="message.pending">
                <span class="ai-message-avatar" aria-hidden="true">{{ message.role === 'assistant' ? 'AI' : '我' }}</span>
                <div class="ai-message-card">
                  <div class="ai-message-meta">
                    <strong>{{ message.role === 'assistant' ? '分析助手' : '你' }}</strong>
                    @if (message.pending) {
                      <small>生成中</small>
                    } @else if (message.tokens) {
                      <small>{{ message.tokens }} tokens</small>
                    }
                  </div>
                  <p>{{ message.content }}</p>
                  @if (message.source || message.provider_warning) {
                    <footer>
                      @if (message.source) {
                        <em class="ai-message-source">{{ sourceLabel(message.source) }}</em>
                      }
                      @if (message.provider_warning) {
                        <em class="ai-message-source warning">{{ message.provider_warning }}</em>
                      }
                    </footer>
                  }
                </div>
              </div>
            }
            @if (!messages().length) {
              <div class="ai-message assistant starter">
                <span class="ai-message-avatar" aria-hidden="true">AI</span>
                <div class="ai-message-card">
                  <div class="ai-message-meta">
                    <strong>分析助手</strong>
                    <small>就绪</small>
                  </div>
                  <p>会话已就绪。</p>
                </div>
              </div>
            }
          </div>

          <form class="ai-composer" (ngSubmit)="sendMessage()">
            <div class="ai-prompt-shelf" aria-label="预设分析问题">
              @for (prompt of prompts; track prompt.label) {
                <button
                  type="button"
                  class="ai-prompt-chip"
                  [class.active]="selectedPreset()?.label === prompt.label"
                  [attr.aria-pressed]="selectedPreset()?.label === prompt.label"
                  (click)="usePrompt(prompt)"
                >
                  <i class="pi" [ngClass]="prompt.icon"></i>
                  <span>{{ prompt.label }}</span>
                </button>
              }
            </div>
            <div class="ai-composer-shell">
              <textarea
                pTextarea
                [ngModel]="draft"
                (ngModelChange)="onDraftChange($event)"
                name="draft"
                rows="3"
                placeholder="输入经营问题，例如：汇总今天库存、采购、应收风险，并给出优先动作。"
              ></textarea>
              <button pButton class="ai-send-button" type="submit" [loading]="chatLoading()" [disabled]="!draft.trim() || chatLoading()" aria-label="发送经营分析问题">
                <i class="pi pi-send"></i>
                <span>发送</span>
              </button>
            </div>
          </form>
        </article>

        <aside class="atlas-panel ai-insight-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">即时摘要</span>
              <h2>即时摘要</h2>
            </div>
          </div>

          <div class="ai-risk-list">
            @for (risk of command().risks.slice(0, 5); track risk.title + risk.type) {
              <a [routerLink]="riskPath(risk)" [class.critical]="risk.level === 'critical'">
                <p-tag [severity]="risk.level === 'critical' ? 'danger' : 'warn'" [value]="risk.type" />
                <strong>{{ risk.title }}</strong>
                <span>{{ risk.description }}</span>
              </a>
            }
          </div>

          <div class="ai-analysis-output">
            <span>库存分析</span>
            <p>{{ inventoryAnalysis() || '库存风险待分析。' }}</p>
            <div class="atlas-actions-row compact">
              <button pButton type="button" severity="secondary" (click)="runInventoryAnalysis()" [loading]="analysisLoading()">
                <i class="pi pi-box"></i>
                分析库存风险
              </button>
              <button pButton type="button" [text]="true" (click)="runStructuredAnalysis('receivables')" [loading]="structuredLoading()">
                <i class="pi pi-wallet"></i>
                追踪应收
              </button>
            </div>
          </div>
        </aside>
      </section>

      <section class="ai-chart-grid ai-chart-grid-rich">
        <article class="atlas-panel ai-chart-panel-wide">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">图表模式</span>
              <h2>{{ chartModeLabel(chartMode()) }}</h2>
            </div>
            <div class="atlas-actions-row compact">
              <button pButton type="button" [text]="chartMode() !== 'trend'" [severity]="chartMode() === 'trend' ? 'contrast' : undefined" (click)="chartMode.set('trend')">趋势</button>
              <button pButton type="button" [text]="chartMode() !== 'warehouse'" [severity]="chartMode() === 'warehouse' ? 'contrast' : undefined" (click)="chartMode.set('warehouse')">仓库</button>
              <button pButton type="button" [text]="chartMode() !== 'supplier'" [severity]="chartMode() === 'supplier' ? 'contrast' : undefined" (click)="chartMode.set('supplier')">供应商</button>
            </div>
          </div>
          <div class="ai-chart ai-chart-tall" echarts [options]="primaryChart()"></div>
        </article>

        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">风险构成</span>
              <h2>风险构成</h2>
            </div>
            <p-tag severity="warn" [value]="analytics().kpis.active_alerts + ' 项预警'" />
          </div>
          <div class="ai-chart" echarts [options]="riskMixChart()"></div>
        </article>

        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">账龄结构</span>
              <h2>账龄结构</h2>
            </div>
            <p-tag severity="warn" [value]="compactMoney(analytics().kpis.unpaid_amount)" />
          </div>
          <div class="ai-chart" echarts [options]="agingChart()"></div>
        </article>

        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">客户贡献</span>
              <h2>客户贡献</h2>
            </div>
            <p-tag severity="success" value="销售金额" />
          </div>
          <div class="ai-chart" echarts [options]="customerChart()"></div>
        </article>

        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">履约阶段</span>
              <h2>履约阶段</h2>
            </div>
            <p-tag severity="info" [value]="(analytics().order_status_flow?.length || 0) + ' 阶段'" />
          </div>
          <div class="ai-chart" echarts [options]="orderFlowChart()"></div>
        </article>
      </section>

      <section class="ai-related-grid">
        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">低库存</span>
              <h2>低库存对象</h2>
            </div>
          </div>
          <div class="ai-related-list">
            @for (item of relatedLowStock(); track item.sku) {
              <a routerLink="/app/inventory/replenishment">
                <strong>{{ item.name }}</strong>
                <span>{{ item.sku }}</span>
                <em>当前 {{ item.quantity }} / 安全线 {{ item.min_stock }}</em>
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">采购</span>
              <h2>待审批采购</h2>
            </div>
          </div>
          <div class="ai-related-list">
            @for (item of relatedPurchases(); track item.po_no) {
              <a routerLink="/app/procurement/orders">
                <strong>{{ item.po_no }}</strong>
                <span>{{ item.supplier }}</span>
                <em>{{ compactMoney(item.amount) }}</em>
              </a>
            }
          </div>
        </article>

        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">应收</span>
              <h2>逾期应收</h2>
            </div>
          </div>
          <div class="ai-related-list">
            @for (item of relatedReceivables(); track item.receivable_no) {
              <a routerLink="/app/finance/receivables">
                <strong>{{ item.receivable_no }}</strong>
                <span>{{ item.customer }}</span>
                <em>{{ compactMoney(item.unpaid) }}</em>
              </a>
            }
          </div>
        </article>
      </section>

      <p-dialog [(visible)]="settingsOpen" [modal]="true" [style]="{ width: 'min(720px, 96vw)' }" header="分析服务设置" closeAriaLabel="关闭">
        <div class="ai-settings-dialog">
          <div class="dialog-grid">
            <label>
              <span>分析模式</span>
              <div class="mode-switch">
                <button type="button" [class.active]="settingsDraft.analysis_mode === 'local'" (click)="settingsDraft.analysis_mode = 'local'">本地</button>
                <button type="button" [class.active]="settingsDraft.analysis_mode === 'hybrid'" (click)="settingsDraft.analysis_mode = 'hybrid'">混合</button>
                <button type="button" [class.active]="settingsDraft.analysis_mode === 'external'" (click)="settingsDraft.analysis_mode = 'external'">外部</button>
              </div>
            </label>

            <label>
              <span>服务地址</span>
              <input pInputText [(ngModel)]="settingsDraft.ai_api_base" placeholder="https://api.deepseek.com" />
              <small>支持兼容 OpenAI Chat Completions 的 base URL。</small>
            </label>

            <label>
              <span>模型</span>
              <input pInputText [(ngModel)]="settingsDraft.ai_model" placeholder="deepseek-chat" />
              <small>例如 deepseek-chat、gpt-4.1-mini 或企业代理模型名。</small>
            </label>

            <label class="full-width">
              <span>服务凭证</span>
              <input pInputText [(ngModel)]="settingsDraft.ai_api_key" placeholder="留空则继续使用当前配置" />
              <small>当前状态：{{ settings().credential_masked || '未设置' }}</small>
            </label>
          </div>

          <div class="atlas-actions-row">
            <button pButton type="button" severity="secondary" (click)="settingsOpen = false">取消</button>
            <button pButton type="button" (click)="saveSettings()" [loading]="settingsSaving()">保存设置</button>
            <button pButton type="button" severity="success" (click)="saveSettings(true)" [loading]="settingsSaving() || chatLoading()">保存并试问</button>
          </div>
        </div>
      </p-dialog>
    </section>
  `
})
export class AiPage implements OnInit {
  @ViewChild('messageStream') private readonly messageStream?: ElementRef<HTMLElement>;

  private readonly api = inject(ApiService);
  private readonly messagesService = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly chatLoading = signal(false);
  protected readonly analysisLoading = signal(false);
  protected readonly sessionCreating = signal(false);
  protected readonly structuredLoading = signal(false);
  protected readonly diagnosticsLoading = signal(false);
  protected readonly settingsSaving = signal(false);
  protected readonly draftsLoading = signal(false);
  protected readonly draftReviewing = signal<string | null>(null);
  protected readonly command = signal<ManufacturingCommandCenter>(EMPTY_COMMAND_CENTER);
  protected readonly analytics = signal<ExecutiveAnalytics>(EMPTY_ANALYTICS);
  protected readonly sessions = signal<AiSession[]>([]);
  protected readonly messages = signal<AiMessage[]>([]);
  protected readonly aiDrafts = signal<AiActionDraft[]>([]);
  protected readonly settings = signal<AiSettings>(EMPTY_SETTINGS);
  protected readonly diagnostics = signal<AiDiagnostics>(EMPTY_DIAGNOSTICS);
  protected readonly structured = signal<StructuredOperationsAnalysis>(EMPTY_STRUCTURED);
  protected readonly activeSessionId = signal<number | null>(null);
  protected readonly activeScenario = signal<AnalysisScenario>('daily_brief');
  protected readonly chartMode = signal<ChartMode>('trend');
  protected readonly sessionPageSize = signal(4);
  protected readonly sessionPage = signal(1);
  protected readonly inventoryAnalysis = signal('');
  protected readonly selectedPreset = signal<{ label: string; value: string; icon: string } | null>(null);
  protected draft = '';
  protected settingsOpen = false;
  protected settingsDraft: { analysis_mode: AiSettings['analysis_mode']; ai_api_base: string; ai_api_key: string; ai_model: string } = {
    analysis_mode: 'local',
    ai_api_base: '',
    ai_api_key: '',
    ai_model: 'deepseek-chat'
  };
  protected readonly prompts = [
    { label: '库存风险', icon: 'pi-box', value: '请按风险优先级汇总当前低库存、补货建议和采购审批阻塞，并给出下一步动作。' },
    { label: '应收催款', icon: 'pi-wallet', value: '请汇总逾期应收风险，给出客户催款和信用冻结建议。' },
    { label: '采购审批', icon: 'pi-shopping-cart', value: '请生成采购审批摘要，并说明最先需要确认的收货前置条件。' },
    { label: '日报摘要', icon: 'pi-chart-line', value: '请生成一段管理层经营日报摘要，覆盖库存、采购、履约、应收和报表归档。' }
  ];
  protected readonly activeSession = computed(() => this.sessions().find(item => item.id === this.activeSessionId()) ?? null);
  protected readonly actionQueue = computed(() => this.analytics().action_queue ?? []);
  protected readonly guardrails = computed(() => buildAiGuardrails(this.settings(), this.diagnostics()));
  protected readonly trustGuardrail = computed(() => this.guardrails().find(item => item.key === 'trust-posture') ?? this.guardrails()[0]);
  protected readonly aiEndpointLabel = computed(() => {
    const settings = this.settings();
    if (settings.analysis_mode === 'local') {
      return '本地数据引擎';
    }
    const base = settings.external_base || '外部 API';
    return `${settings.model || '默认模型'} · ${base.replace(/^https?:\/\//, '')}`;
  });
  protected readonly briefCards = computed(() => {
    const cards = this.structured().insight_cards;
    const command = this.command();
    const analytics = this.analytics();
    const operationalCards = [
      {
        title: '库存风险',
        metric: `${command.kpis.low_stock_products} 项`,
        note: '低水位 SKU 与补货建议联动',
        tone: command.kpis.low_stock_products ? 'warning' : 'success',
        path: '/app/inventory/replenishment'
      },
      {
        title: '采购推进',
        metric: `${command.kpis.pending_purchase} 单`,
        note: '审批、到货和收货入库队列',
        tone: command.kpis.pending_purchase ? 'warning' : 'success',
        path: '/app/procurement/orders'
      },
      {
        title: '应收压力',
        metric: this.compactMoney(command.kpis.overdue_amount || analytics.kpis.unpaid_amount),
        note: '账龄、信用占用和收款动作',
        tone: command.kpis.overdue_amount || analytics.kpis.unpaid_amount ? 'danger' : 'success',
        path: '/app/finance/receivables'
      },
      {
        title: '协同任务',
        metric: `${analytics.kpis.collaboration_items} 项`,
        note: '通知、报表和跨部门待办',
        tone: analytics.kpis.collaboration_items ? 'warning' : 'success',
        path: '/app/notifications'
      }
    ];
    if (!cards.length) {
      return operationalCards;
    }
    return cards.length < 4 ? [...cards, ...operationalCards].slice(0, 4) : cards;
  });
  protected readonly briefActions = computed(() => {
    const actions = this.structured().action_items;
    const operationalActions = [
      {
        title: '锁定低水位 SKU',
        description: '进入补货队列，按安全库存缺口和供应交期生成采购草稿。',
        priority: this.command().kpis.low_stock_products ? 'high' : 'normal',
        path: '/app/inventory/replenishment',
        prompt: '请按安全库存缺口、供应商交期和采购金额排序低水位 SKU。'
      },
      {
        title: '推进采购审批',
        description: '复核待审批采购单的供应商、金额、收货仓和质检前置条件。',
        priority: this.command().kpis.pending_purchase ? 'high' : 'normal',
        path: '/app/procurement/orders',
        prompt: '请汇总待审批采购单，并指出最先需要审批的三张单据。'
      },
      {
        title: '处理应收风险',
        description: '按账龄和客户信用占用安排催款、收款或额度冻结。',
        priority: this.command().kpis.overdue_amount ? 'high' : 'normal',
        path: '/app/finance/receivables',
        prompt: '请按账龄、客户信用和未收金额生成收款优先级。'
      }
    ];
    if (!actions.length) {
      return operationalActions;
    }
    return actions.length < 3 ? [...actions, ...operationalActions].slice(0, 3) : actions;
  });
  protected readonly draftActions = computed(() => buildAiDraftActions(this.briefActions()));
  protected readonly pendingDraftCount = computed(() => this.aiDrafts().filter(item => item.status === 'draft').length);
  protected readonly visibleAiDrafts = computed(() => this.aiDrafts().slice(0, 4));
  protected readonly relatedLowStock = computed(() => {
    const rows = this.structured().related_records.low_stock;
    if (rows.length) {
      return rows;
    }
    return (this.analytics().inventory_risk_rank ?? []).slice(0, 5).map(item => ({
      sku: item.sku,
      name: item.name,
      quantity: item.current_qty,
      min_stock: item.current_qty + item.gap
    }));
  });
  protected readonly relatedPurchases = computed(() => {
    const rows = this.structured().related_records.pending_purchase;
    if (rows.length) {
      return rows;
    }
    return (this.analytics().procurement_stages ?? []).slice(0, 5).map((item, index) => ({
      po_no: `PO-${String(index + 1).padStart(4, '0')}`,
      supplier: item.name,
      amount: item.value
    }));
  });
  protected readonly relatedReceivables = computed(() => {
    const rows = this.structured().related_records.overdue_receivables;
    if (rows.length) {
      return rows;
    }
    return (this.analytics().aging_buckets ?? []).slice(0, 5).map((item, index) => ({
      receivable_no: `AR-${String(index + 1).padStart(4, '0')}`,
      customer: item.name,
      unpaid: item.value
    }));
  });
  protected readonly sessionTotalPages = computed(() => Math.max(1, Math.ceil(this.sessions().length / this.sessionPageSize())));
  protected readonly pagedSessions = computed(() => {
    const start = (Math.min(this.sessionPage(), this.sessionTotalPages()) - 1) * this.sessionPageSize();
    return this.sessions().slice(start, start + this.sessionPageSize());
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      sessions: this.api.get<{ items: AiSession[] }>('ai/sessions').pipe(catchError(() => of({ items: [] }))),
      command: this.api.get<ManufacturingCommandCenter>('manufacturing/command-center').pipe(catchError(() => of(EMPTY_COMMAND_CENTER))),
      analytics: this.api.get<ExecutiveAnalytics>('analytics/executive').pipe(catchError(() => of(EMPTY_ANALYTICS))),
      settings: this.api.get<AiSettings>('ai/settings').pipe(catchError(() => of(EMPTY_SETTINGS))),
      diagnostics: this.api.post<AiDiagnostics>('ai/diagnostics', {}).pipe(catchError(() => of(EMPTY_DIAGNOSTICS))),
      structured: this.api.post<StructuredOperationsAnalysis>('ai/analyze/structured', { scenario: 'daily_brief', limit: 8 }).pipe(catchError(() => of(EMPTY_STRUCTURED))),
      drafts: this.api.get<{ items: AiActionDraft[] }>('ai/drafts', { status: 'draft' }).pipe(catchError(() => of({ items: [] })))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(({ sessions, command, analytics, settings, diagnostics, structured, drafts }) => {
      this.sessions.set(sessions.items);
      this.setSessionPage(1);
      this.command.set(command);
      this.analytics.set(analytics);
      this.aiDrafts.set(drafts.items);
      this.settings.set(settings);
      this.diagnostics.set(diagnostics);
      this.structured.set(structured);
      this.activeScenario.set((structured.scenario as AnalysisScenario) || 'daily_brief');
      this.hydrateSettingsDraft(settings);
      const first = sessions.items[0];
      if (first && !this.activeSessionId()) {
        this.selectSession(first);
      }
    });
  }

  openSettings(): void {
    this.hydrateSettingsDraft(this.settings());
    this.settingsOpen = true;
  }

  saveSettings(probe = false): void {
    this.settingsSaving.set(true);
    this.api.put<AiSettings>('ai/settings', this.settingsDraft).pipe(
      catchError(error => {
        this.messagesService.add({ severity: 'warn', summary: '设置未保存', detail: error?.message || '分析服务设置未更新。' });
        return of(null);
      }),
      finalize(() => this.settingsSaving.set(false))
    ).subscribe(result => {
      if (!result) {
        return;
      }
      this.settings.set(result);
      this.hydrateSettingsDraft(result);
      this.settingsOpen = false;
      this.messagesService.add({ severity: 'success', summary: '设置已保存', detail: this.modeLabel(result.analysis_mode) });
      this.runDiagnostics();
      if (probe) {
        this.runAiSmokeTest();
      }
    });
  }

  runDiagnostics(): void {
    this.diagnosticsLoading.set(true);
    this.api.post<AiDiagnostics>('ai/diagnostics', {}).pipe(
      catchError(error => {
        this.messagesService.add({ severity: 'warn', summary: '诊断失败', detail: error?.message || '无法完成分析服务诊断。' });
        return of(null);
      }),
      finalize(() => this.diagnosticsLoading.set(false))
    ).subscribe(result => {
      if (result) {
        this.diagnostics.set(result);
      }
    });
  }

  runStructuredAnalysis(scenario: AnalysisScenario): void {
    this.activeScenario.set(scenario);
    this.structuredLoading.set(true);
    this.api.post<StructuredOperationsAnalysis>('ai/analyze/structured', { scenario, limit: 8 }).pipe(
      catchError(error => {
        this.messagesService.add({ severity: 'warn', summary: '经营摘要异常', detail: error?.message || '结构化分析没有返回可用结果。' });
        return of(null);
      }),
      finalize(() => this.structuredLoading.set(false))
    ).subscribe(result => {
      if (result) {
        this.structured.set(result);
      }
    });
  }

  selectSession(session: AiSession): void {
    this.activeSessionId.set(session.id);
    this.api.get<{ session: AiSession; items: AiMessage[] }>(`ai/sessions/${session.id}/messages`).pipe(
      catchError(error => {
        this.messagesService.add({ severity: 'warn', summary: '会话读取失败', detail: error?.message || '无法读取分析消息。' });
        return of({ session, items: [] });
      })
    ).subscribe(result => {
      this.messages.set(result.items);
      this.scrollMessagesToBottom();
    });
  }

  createSession(): void {
    this.sessionCreating.set(true);
    this.api.post<AiSession>('ai/sessions', { title: `经营分析 ${new Date().toLocaleString('zh-CN', { hour12: false })}` }).pipe(
      catchError(error => {
        this.messagesService.add({ severity: 'warn', summary: '新建会话失败', detail: error?.message || '会话未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.sessionCreating.set(false))
    ).subscribe(session => {
      if (!session) {
        return;
      }
      this.sessions.set([session, ...this.sessions()]);
      this.setSessionPage(1);
      this.selectSession(session);
      this.messagesService.add({ severity: 'success', summary: '会话已创建', detail: session.title });
    });
  }

  sendMessage(): void {
    const text = this.draft.trim();
    if (!text || this.chatLoading()) {
      return;
    }
    this.chatLoading.set(true);
    this.draft = '';
    this.selectedPreset.set(null);
    const optimistic: AiMessage = { role: 'user', content: text };
    const pending: AiMessage = { role: 'assistant', content: '经营数据分析中...', pending: true };
    this.messages.set([...this.messages(), optimistic, pending]);
    this.scrollMessagesToBottom();
    void this.sendMessageWithStream(text, this.activeSessionId());
  }

  runAiSmokeTest(): void {
    const prompt = '请用一段简短中文确认当前经营分析服务是否可用，并基于库存、采购、应收数据给出一个最优先动作。';
    this.draft = prompt;
    this.selectedPreset.set(null);
    this.sendMessage();
  }

  runInventoryAnalysis(): void {
    this.analysisLoading.set(true);
    this.api.post<{ content: string }>('ai/analyze/inventory', { limit: 12 }).pipe(
      catchError(error => {
        this.messagesService.add({ severity: 'warn', summary: '库存分析失败', detail: error?.message || '库存分析未完成。' });
        return of(null);
      }),
      finalize(() => this.analysisLoading.set(false))
    ).subscribe(result => {
      if (result) {
        this.inventoryAnalysis.set(result.content);
        this.messages.set([...this.messages(), { role: 'assistant', content: result.content }]);
        this.scrollMessagesToBottom();
        this.messagesService.add({ severity: 'success', summary: '库存分析完成', detail: '已生成可追踪建议。' });
      }
    });
  }

  onDraftChange(value: string): void {
    this.draft = value;
    const selected = this.selectedPreset();
    if (selected && value !== selected.value) {
      this.selectedPreset.set(null);
    }
  }

  usePrompt(prompt: { label: string; value: string; icon: string }): void {
    this.draft = prompt.value;
    this.selectedPreset.set(prompt);
    if (typeof document !== 'undefined') {
      document.querySelector('.ai-chat-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  loadDraftPrompt(prompt: string): void {
    this.draft = prompt;
    this.selectedPreset.set(null);
    if (typeof document !== 'undefined') {
      document.querySelector('.ai-chat-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  loadAiDrafts(): void {
    this.draftsLoading.set(true);
    this.api.get<{ items: AiActionDraft[] }>('ai/drafts', { status: 'draft' }).pipe(
      catchError(error => {
        this.messagesService.add({ severity: 'warn', summary: '草稿读取失败', detail: error?.message || '无法读取 AI 待确认草稿。' });
        return of({ items: [] });
      }),
      finalize(() => this.draftsLoading.set(false))
    ).subscribe(result => {
      this.aiDrafts.set(result.items);
    });
  }

  confirmAiDraft(draft: AiActionDraft): void {
    const key = this.draftActionKey(draft, 'confirm');
    this.draftReviewing.set(key);
    this.api.post<AiDraftConfirmResult>(`ai/drafts/${draft.id}/confirm`, {}).pipe(
      catchError(error => {
        this.messagesService.add({ severity: 'warn', summary: '草稿未确认', detail: error?.message || 'AI 草稿没有转入补货建议。' });
        return of(null);
      }),
      finalize(() => this.draftReviewing.set(null))
    ).subscribe(result => {
      if (!result) {
        return;
      }
      this.removeAiDraft(result.draft.id);
      const count = result.replenishment_suggestion_ids?.length ?? 0;
      this.messagesService.add({
        severity: 'success',
        summary: '草稿已确认',
        detail: count ? `已转入 ${count} 条补货建议。` : '已转入补货建议中心。'
      });
    });
  }

  rejectAiDraft(draft: AiActionDraft): void {
    const key = this.draftActionKey(draft, 'reject');
    this.draftReviewing.set(key);
    this.api.post<AiDraftRejectResult>(`ai/drafts/${draft.id}/reject`, {}).pipe(
      catchError(error => {
        this.messagesService.add({ severity: 'warn', summary: '草稿未驳回', detail: error?.message || 'AI 草稿状态未更新。' });
        return of(null);
      }),
      finalize(() => this.draftReviewing.set(null))
    ).subscribe(result => {
      if (!result) {
        return;
      }
      this.removeAiDraft(result.draft.id);
      this.messagesService.add({ severity: 'success', summary: '草稿已驳回', detail: result.draft.title });
    });
  }

  draftSummary(draft: AiActionDraft): string {
    return summarizeAiActionDraft(draft);
  }

  draftStatusLabel(status: AiActionDraft['status']): string {
    return aiDraftStatusLabel(status);
  }

  draftStatusTone(status: AiActionDraft['status']): AiGuardrailTone {
    return aiDraftStatusTone(status);
  }

  draftActionKey(draft: AiActionDraft, action: 'confirm' | 'reject'): string {
    return `${action}:${draft.id}`;
  }

  private scrollMessagesToBottom(): void {
    if (typeof queueMicrotask === 'undefined') {
      return;
    }
    queueMicrotask(() => {
      const element = this.messageStream?.nativeElement;
      if (element) {
        element.scrollTop = element.scrollHeight;
      }
    });
  }

  private async sendMessageWithStream(text: string, sessionId: number | null): Promise<void> {
    let streamedContent = '';
    let streamAccepted = false;
    try {
      const result = await streamAiChat(
        { message: text, session_id: sessionId },
        {
          onStatus: status => {
            streamAccepted = true;
            if (status.session?.id) {
              this.activeSessionId.set(status.session.id);
              this.upsertSession(status.session);
            }
          },
          onChunk: content => {
            streamedContent += content;
            this.replacePendingMessage({
              role: 'assistant',
              content: streamedContent || '经营数据分析中...',
              pending: true
            });
          }
        }
      );
      this.applyAiChatResult(result);
    } catch (error) {
      if (this.canFallbackToPlainChat(error, streamedContent, streamAccepted)) {
        await this.sendMessageWithoutStream(text, sessionId);
        return;
      }
      this.messagesService.add({ severity: 'warn', summary: '分析失败', detail: errorMessage(error) || '分析请求未完成。' });
      this.removePendingMessage();
    } finally {
      this.chatLoading.set(false);
    }
  }

  private async sendMessageWithoutStream(text: string, sessionId: number | null): Promise<void> {
    const result = await firstValueFrom(this.api.post<AiChatResult>('ai/chat', { message: text, session_id: sessionId }).pipe(
      catchError(error => {
        this.messagesService.add({ severity: 'warn', summary: '分析失败', detail: error?.message || '分析请求未完成。' });
        return of(null);
      })
    ));
    if (!result) {
      this.removePendingMessage();
      return;
    }
    this.applyAiChatResult(result);
  }

  private canFallbackToPlainChat(error: unknown, streamedContent: string, streamAccepted: boolean): boolean {
    if (streamedContent || streamAccepted) {
      return false;
    }
    if (error instanceof AiChatStreamError) {
      return !error.status || error.status === 404 || error.status === 405 || error.status >= 500;
    }
    return true;
  }

  private applyAiChatResult(result: AiChatResult): void {
    this.activeSessionId.set(result.session.id);
    const assistantMessage = {
      ...result.message,
      source: result.source,
      provider_warning: result.provider_warning
    };
    this.replacePendingMessage(assistantMessage);
    this.scrollMessagesToBottom();
    this.upsertSession(result.session);
  }

  private replacePendingMessage(message: AiMessage): void {
    let replaced = false;
    const next = this.messages().map(item => {
      if (!item.pending) {
        return item;
      }
      replaced = true;
      return message;
    });
    this.messages.set(replaced ? next : [...next, message]);
    this.scrollMessagesToBottom();
  }

  private removePendingMessage(): void {
    this.messages.set(this.messages().filter(item => !item.pending));
  }

  setSessionPage(page: number): void {
    this.sessionPage.set(Math.min(Math.max(1, Math.trunc(page || 1)), this.sessionTotalPages()));
  }

  riskPath(risk: ManufacturingCommandCenter['risks'][number]): string {
    if (risk.type.includes('应收')) {
      return '/app/finance/receivables';
    }
    if (risk.type.includes('采购')) {
      return '/app/procurement/orders';
    }
    return '/app/inventory/replenishment';
  }

  modeLabel(mode: AiSettings['analysis_mode']): string {
    return mode === 'external' ? '外部推理' : mode === 'hybrid' ? '混合分析' : '本地分析';
  }

  diagnosticsToneLabel(status: string): string {
    if (status === 'ready') {
      return '就绪';
    }
    if (status === 'degraded') {
      return '降级';
    }
    if (status === 'credential_invalid') {
      return '凭证异常';
    }
    if (status === 'unreachable') {
      return '不可达';
    }
    return '待处理';
  }

  chartModeLabel(mode: ChartMode): string {
    return mode === 'warehouse' ? '仓库周转与流动' : mode === 'supplier' ? '供应商准时率与质量率' : '销售与回款趋势';
  }

  sourceLabel(source: string): string {
    return source === 'analysis_provider' ? '外部模型已响应' : '本地经营引擎响应';
  }

  tagSeverity(tone: AiGuardrailTone): 'success' | 'warn' | 'danger' | 'info' {
    if (tone === 'warning') {
      return 'warn';
    }
    if (tone === 'danger') {
      return 'danger';
    }
    if (tone === 'success') {
      return 'success';
    }
    return 'info';
  }

  compactMoney(value: unknown): string {
    return compactMoneyText(value);
  }

  compactNumber(value: unknown): string {
    return compactNumberText(value);
  }

  date(value: unknown): string {
    return dateText(value);
  }

  protected readonly primaryChart = computed<EChartsCoreOption>(() => {
    if (this.chartMode() === 'warehouse') {
      return {
        grid: { left: 16, right: 16, top: 20, bottom: 28, containLabel: true },
        tooltip: { trigger: 'axis' },
        legend: chartLegend('top', 'rgba(148,163,184,.95)'),
        xAxis: { type: 'category', data: (this.analytics().warehouse_turnover ?? []).map(item => item.name), axisLine: { show: false }, axisTick: { show: false } },
        yAxis: [{ type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } }, { type: 'value', splitLine: { show: false } }],
        series: [
          { type: 'bar', name: '库存量', data: (this.analytics().warehouse_turnover ?? []).map(item => item.stock_quantity), barWidth: 18, itemStyle: { borderRadius: 8, color: '#5cc6b5' } },
          { type: 'line', name: '流水数', yAxisIndex: 1, smooth: true, data: (this.analytics().warehouse_turnover ?? []).map(item => item.movement_count), lineStyle: { width: 3, color: '#ffba6b' }, symbolSize: 6 }
        ]
      };
    }
    if (this.chartMode() === 'supplier') {
      const suppliers = (this.analytics().supplier_score ?? []).length ? this.analytics().supplier_score! : [
        { name: '供应商A', on_time_rate: 0, quality_rate: 0 },
        { name: '供应商B', on_time_rate: 0, quality_rate: 0 },
        { name: '供应商C', on_time_rate: 0, quality_rate: 0 }
      ];
      return {
        radar: {
          indicator: suppliers.map(item => ({ name: item.name, max: 100 })),
          radius: '64%',
          axisName: { color: 'rgba(100,116,139,.95)' }
        },
        legend: chartLegend('bottom', 'rgba(148,163,184,.95)'),
        series: [{
          type: 'radar',
          data: [
            { value: suppliers.map(item => item.on_time_rate), name: '准时率', areaStyle: { color: 'rgba(102,203,255,.22)' }, lineStyle: { color: '#66cbff' } },
            { value: suppliers.map(item => item.quality_rate), name: '质量率', areaStyle: { color: 'rgba(102,214,143,.18)' }, lineStyle: { color: '#66d68f' } }
          ]
        }]
      };
    }
    return {
      grid: { left: 16, right: 18, top: 28, bottom: 22, containLabel: true },
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top', 'rgba(148,163,184,.95)'),
      xAxis: { type: 'category', data: this.analytics().sales_trend.map(item => item.name), boundaryGap: false, axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.18)' } } },
      series: [
        { type: 'line', name: '销售额', smooth: true, data: this.analytics().sales_trend.map(item => item.value), lineStyle: { width: 3, color: '#62d8cb' }, areaStyle: { color: 'rgba(98,216,203,.16)' }, symbolSize: 5 },
        { type: 'line', name: '回款额', smooth: true, data: (this.analytics().cash_collection_trend ?? []).map(item => item.value), lineStyle: { width: 3, color: '#ffba6b' }, areaStyle: { color: 'rgba(255,186,107,.12)' }, symbolSize: 5 }
      ]
    };
  });

  protected readonly riskMixChart = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'item' },
    legend: chartLegend('bottom', 'rgba(148,163,184,.95)'),
    series: [{
      type: 'pie',
      radius: ['48%', '72%'],
      center: ['50%', '42%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 8, borderColor: 'rgba(15,23,42,.2)', borderWidth: 2 },
      data: this.analytics().risk_mix
    }]
  }));

  protected readonly agingChart = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'item' },
    legend: chartLegend('bottom', 'rgba(148,163,184,.95)'),
    series: [{
      type: 'pie',
      radius: ['42%', '70%'],
      center: ['50%', '42%'],
      itemStyle: { borderRadius: 9, borderColor: 'rgba(15,23,42,.18)', borderWidth: 2 },
      data: this.analytics().aging_buckets ?? []
    }]
  }));

  protected readonly customerChart = computed<EChartsCoreOption>(() => ({
    grid: { left: 12, right: 18, top: 18, bottom: 16, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'value', axisLine: { show: false }, splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
    yAxis: {
      type: 'category',
      data: (this.analytics().top_customers ?? []).map(item => item.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: 'rgba(100,116,139,.95)', width: 96, overflow: 'truncate' }
    },
    series: [{
      type: 'bar',
      data: (this.analytics().top_customers ?? []).map(item => item.value),
      barWidth: 14,
      itemStyle: { borderRadius: 8, color: '#67d19b' }
    }]
  }));

  protected readonly orderFlowChart = computed<EChartsCoreOption>(() => ({
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: (this.analytics().order_status_flow ?? []).map(item => item.name), axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
    series: [{
      type: 'bar',
      data: (this.analytics().order_status_flow ?? []).map(item => item.value),
      barWidth: 24,
      itemStyle: {
        borderRadius: [10, 10, 2, 2],
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: '#8fb7ff' },
            { offset: 1, color: '#4f7cff' }
          ]
        }
      }
    }]
  }));

  private hydrateSettingsDraft(settings: AiSettings): void {
    this.settingsDraft = {
      analysis_mode: settings.analysis_mode,
      ai_api_base: settings.external_base || '',
      ai_api_key: '',
      ai_model: settings.model || 'deepseek-chat'
    };
  }

  private upsertSession(session: AiSession): void {
    const next = [session, ...this.sessions().filter(item => item.id !== session.id)];
    this.sessions.set(next);
  }

  private removeAiDraft(draftId: number): void {
    this.aiDrafts.set(this.aiDrafts().filter(item => item.id !== draftId));
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '';
}
