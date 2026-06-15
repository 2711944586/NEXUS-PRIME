import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TagModule } from 'primeng/tag';
import { TextareaModule } from 'primeng/textarea';
import { catchError, finalize, forkJoin, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { AiSettings, DataRecord, DeploymentReadiness, DeploymentReadinessCheck, ThemeMode, UserPreferences } from '../core/models';
import { ThemeService } from '../core/theme.service';
import { COMMAND_CENTER_PHOTOS } from '../core/visual-assets';

const EMPTY_AI_SETTINGS: AiSettings = {
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

const EMPTY_DEPLOYMENT_READINESS: DeploymentReadiness = {
  generated_at: '',
  source: 'empty',
  summary: {
    score: 0,
    level: 'attention',
    ready: 0,
    attention: 0,
    blocked: 0,
    total: 0,
    next_action: '等待后端就绪数据',
    frontend_boundary: 'NEXUS_API_BASE_URL only',
    backend_boundary: 'DATABASE_URL / SECRET_KEY / AI / storage secrets'
  },
  checks: [],
  service_snapshot: {
    services: 0,
    domains: [],
    avg_readiness: 0,
    avg_contract_coverage: 0,
    avg_split_score: 0,
    deployment_units: [],
    stores: [],
    dependencies: 0,
    api_surfaces: 0,
    split_plan: [],
    observability: {
      coverage: 0,
      policy: 'metrics + logs + traces',
      missing: [],
      signals: []
    },
    incident_queue: []
  },
  maturity: {
    summary: {
      score: 0,
      level: 'attention',
      target: '行业头部级制造开发管理 ERP',
      dimensions: 0,
      ready: 0,
      attention: 0,
      blocked: 0,
      next_action: '等待成熟度数据'
    },
    dimensions: [],
    capability_map: [],
    topology_nodes: [],
    topology_edges: [],
    evidence: []
  },
  runbook: []
};

interface DeploymentLink {
  title: string;
  description: string;
  url: string;
  variable: string;
  secret: boolean;
  scope: 'frontend' | 'backend' | 'script';
}

interface DeploymentCommand {
  title: string;
  description: string;
  command: string;
}

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, ButtonModule, InputTextModule, TagModule, TextareaModule],
  template: `
    <section class="ops-atlas-page settings-page">
      <header class="settings-hero atlas-panel">
        <div class="hero-narrative">
          <span class="atlas-kicker">系统设置</span>
          <h1>控制中心</h1>
          <p>统一控制主题、密度、导航、图表动画、右侧信息栏和 AI 分析接入。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="saveAll()" [loading]="saving()" aria-label="保存全部设置">
              <i class="pi pi-save"></i>
              保存全部
            </button>
            <button pButton type="button" severity="secondary" (click)="load()" [loading]="loading()" aria-label="重新读取设置">
              <i class="pi pi-refresh"></i>
              重新读取
            </button>
            <a pButton severity="info" routerLink="/app/ai">
              <i class="pi pi-sparkles"></i>
              AI 分析台
            </a>
          </div>
        </div>

        <div class="settings-status-board">
          <article>
            <span>主题</span>
            <strong>{{ preferenceDraft.theme === 'dark-cockpit' ? '深色' : '亮色' }}</strong>
            <em>{{ preferenceDraft.density === 'compact' ? '紧凑密度' : '舒适密度' }}</em>
          </article>
          <article>
            <span>AI 接入</span>
            <strong>{{ aiDraft.analysis_mode === 'external' ? '外部' : aiDraft.analysis_mode === 'hybrid' ? '混合' : '本地' }}</strong>
            <em>{{ aiSettings().credential_masked || '未配置凭证' }}</em>
          </article>
          <article>
            <span>导航</span>
            <strong>{{ preferenceDraft.dock_labels === 'always' ? '常显' : '悬停' }}</strong>
            <em>{{ preferenceDraft.context_panel === 'compact' ? '右栏精简' : '右栏显示' }}</em>
          </article>
        </div>

        <div class="settings-visual-rail" aria-label="系统控制台现场图片">
          @for (photo of settingsPhotos; track photo.src) {
            <figure>
              <img [src]="photo.src" [alt]="photo.alt" loading="eager" decoding="async" />
              <figcaption>
                <span>{{ photo.label }}</span>
                <strong>{{ photo.caption }}</strong>
              </figcaption>
            </figure>
          }
        </div>
      </header>

      <section class="settings-grid">
        <article class="atlas-panel settings-card">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">外观</span>
              <h2>界面与动效</h2>
            </div>
            <p-tag severity="info" value="全局" />
          </div>

          <div class="settings-option-grid">
            <button type="button" [class.active]="preferenceDraft.theme === 'light-luxury'" (click)="setTheme('light-luxury')">
              <i class="pi pi-sun"></i>
              <strong>亮色系统</strong>
              <span>适合日常办公、报表复核和文件查看。</span>
            </button>
            <button type="button" [class.active]="preferenceDraft.theme === 'dark-cockpit'" (click)="setTheme('dark-cockpit')">
              <i class="pi pi-moon"></i>
              <strong>深色驾驶舱</strong>
              <span>适合值守屏、夜间监控和经营风险看板。</span>
            </button>
          </div>

          <div class="settings-form-grid">
            <label>
              <span>信息密度</span>
              <select [(ngModel)]="preferenceDraft.density">
                <option value="compact">紧凑</option>
                <option value="comfortable">舒适</option>
              </select>
            </label>
            <label>
              <span>图表动效</span>
              <select [(ngModel)]="preferenceDraft.charts_motion">
                <option value="standard">标准</option>
                <option value="reduced">减少动效</option>
              </select>
            </label>
            <label>
              <span>默认工作台</span>
              <select [(ngModel)]="preferenceDraft.default_workspace">
                <option value="/app/overview">运营总览</option>
                <option value="/app/ai">AI 分析</option>
                <option value="/app/reports">报表工作室</option>
                <option value="/app/files">文件中心</option>
              </select>
            </label>
          </div>
        </article>

        <article class="atlas-panel settings-card">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">导航</span>
              <h2>Dock 与上下文栏</h2>
            </div>
            <p-tag severity="success" value="布局" />
          </div>

          <div class="settings-form-grid">
            <label>
              <span>Dock 名称</span>
              <select [(ngModel)]="preferenceDraft.dock_labels">
                <option value="hover">悬停显示</option>
                <option value="always">始终显示</option>
              </select>
            </label>
            <label>
              <span>右侧上下文栏</span>
              <select [(ngModel)]="preferenceDraft.context_panel">
                <option value="visible">显示完整信息</option>
                <option value="compact">精简显示</option>
              </select>
            </label>
          </div>

          <div class="settings-link-list">
            <a routerLink="/app/profile"><i class="pi pi-user"></i><span>个人工作台</span></a>
            <a routerLink="/app/system/users"><i class="pi pi-shield"></i><span>用户权限</span></a>
            <a routerLink="/app/system/audit"><i class="pi pi-lock"></i><span>审计日志</span></a>
          </div>
        </article>

        <article class="atlas-panel settings-card ai-settings-card">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">AI</span>
              <h2>AI 分析服务</h2>
            </div>
            <p-tag [severity]="aiSettings().external_configured ? 'success' : 'warn'" [value]="aiSettings().external_configured ? '已配置' : '未配置'" />
          </div>

          <div class="mode-switch settings-mode-switch">
            <button type="button" [class.active]="aiDraft.analysis_mode === 'local'" (click)="aiDraft.analysis_mode = 'local'">本地</button>
            <button type="button" [class.active]="aiDraft.analysis_mode === 'hybrid'" (click)="aiDraft.analysis_mode = 'hybrid'">混合</button>
            <button type="button" [class.active]="aiDraft.analysis_mode === 'external'" (click)="aiDraft.analysis_mode = 'external'">外部</button>
          </div>

          <div class="settings-form-grid">
            <label>
              <span>Base URL</span>
              <input pInputText [(ngModel)]="aiDraft.ai_api_base" placeholder="https://api.deepseek.com" />
            </label>
            <label>
              <span>模型</span>
              <input pInputText [(ngModel)]="aiDraft.ai_model" placeholder="deepseek-chat" />
            </label>
            <label class="wide">
              <span>API Key</span>
              <input pInputText [(ngModel)]="aiDraft.ai_api_key" placeholder="留空则保留当前凭证" />
            </label>
          </div>

          <div class="settings-note">
            <strong>{{ aiSettings().credential_masked || '当前未配置外部凭证' }}</strong>
            <span>外部服务需兼容 Chat Completions 请求格式；保存后可在 AI 分析台运行诊断。</span>
          </div>
        </article>

        <article class="atlas-panel settings-card deployment-settings-card">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">部署</span>
              <h2>上线准备与密钥入口</h2>
            </div>
            <p-tag severity="contrast" value="后端密钥隔离" />
          </div>

          <div class="deployment-boundary-strip" aria-label="部署边界">
            <article>
              <span>前端项目</span>
              <strong>NEXUS_API_BASE_URL</strong>
              <em>只保存公开 API 地址。</em>
            </article>
            <article>
              <span>后端项目</span>
              <strong>DATABASE_URL / SECRET_KEY / AI / Cloudinary</strong>
              <em>所有密钥只写入后端环境变量。</em>
            </article>
            <article>
              <span>旧版快照</span>
              <strong>legacy/monolith-flask</strong>
              <em>保留作升级报告对照，不参与部署。</em>
            </article>
          </div>

          <section class="deployment-readiness-board" aria-label="动态部署就绪看板">
            <article class="deployment-score-card" [class.ready]="deploymentReadiness().summary.level === 'ready'" [class.blocked]="deploymentReadiness().summary.level === 'blocked'">
              <span>上线就绪分</span>
              <strong>{{ deploymentReadiness().summary.score }}%</strong>
              <em>{{ deploymentReadiness().summary.next_action }}</em>
              <div>
                <b>{{ deploymentReadiness().summary.ready }}</b>
                <small>ready</small>
              </div>
              <div>
                <b>{{ deploymentReadiness().summary.attention }}</b>
                <small>attention</small>
              </div>
              <div>
                <b>{{ deploymentReadiness().summary.blocked }}</b>
                <small>blocked</small>
              </div>
            </article>

            <div class="deployment-check-board">
              <div class="deployment-section-head">
                <span>部署前检查</span>
                <strong>{{ deploymentReadiness().summary.total }} 项动态检查</strong>
              </div>
              @for (check of readinessChecks(); track check.key) {
                <article [class.ready]="check.status === 'ready'" [class.blocked]="check.status === 'blocked'" [class.attention]="check.status === 'attention'">
                  <p-tag [severity]="statusSeverity(check.status)" [value]="check.status" />
                  <span>{{ check.scope }}</span>
                  <strong>{{ check.label }}</strong>
                  <em>{{ check.evidence }}</em>
                  <small>{{ check.action }}</small>
                  @if (check.status !== 'ready') {
                    <div class="deployment-check-actions">
                      <button
                        pButton
                        type="button"
                        size="small"
                        severity="secondary"
                        [loading]="deploymentTaskCreating() === check.key"
                        [disabled]="deploymentTaskCreating() !== ''"
                        (click)="createDeploymentTask(check)"
                        [attr.aria-label]="'创建部署预检任务 ' + check.label"
                      >
                        <i class="pi pi-send"></i>
                        创建任务
                      </button>
                      @if (deploymentTaskCreated() === check.key) {
                        <a pButton [text]="true" size="small" routerLink="/app/notifications">
                          通知中心
                        </a>
                      }
                    </div>
                  }
                </article>
              }
            </div>
          </section>

          <section class="deployment-service-snapshot" aria-label="微服务拆分就绪快照">
            <div class="deployment-section-head">
              <span>微服务拆分快照</span>
              <strong>{{ deploymentReadiness().service_snapshot.services }} 服务 / {{ deploymentReadiness().service_snapshot.dependencies }} 依赖 / {{ deploymentReadiness().service_snapshot.api_surfaces }} API 面 / 拆分 {{ deploymentReadiness().service_snapshot.avg_split_score }}%</strong>
            </div>
            <div class="deployment-domain-grid">
              @for (domain of readinessDomains(); track domain.domain) {
                <article [class.attention]="domain.attention > 0">
                  <span>{{ domain.domain }}</span>
                  <strong>{{ domain.avg_readiness }}%</strong>
                  <em>{{ domain.services }} 服务 · {{ domain.records }} 记录</em>
                  <small>{{ domain.attention }} 个关注服务</small>
                </article>
              }
            </div>
            <div class="deployment-runtime-strip">
              <span>部署单元：{{ deploymentReadiness().service_snapshot.deployment_units.join(' / ') || '等待数据' }}</span>
              <span>存储：{{ deploymentReadiness().service_snapshot.stores.join(' / ') || '等待数据' }}</span>
              <span>契约覆盖：{{ deploymentReadiness().service_snapshot.avg_contract_coverage }}%</span>
            </div>
          </section>

          <section class="deployment-architecture-board" aria-label="架构拆分与可观测性">
            <article class="architecture-score-card">
              <span>可观测性覆盖</span>
              <strong>{{ deploymentReadiness().service_snapshot.observability.coverage }}%</strong>
              <em>{{ deploymentReadiness().service_snapshot.observability.policy }}</em>
              <div>
                @for (signal of architectureSignals(); track signal.key) {
                  <span>
                    <b>{{ signal.label }}</b>
                    <small>{{ signal.ready }}/{{ signal.total }} · {{ signal.coverage }}%</small>
                  </span>
                }
              </div>
            </article>

            <div class="architecture-split-plan">
              <div class="deployment-section-head">
                <span>拆分路线</span>
                <strong>{{ architectureSplitPlan().length }} 阶段 · 网关与事件优先</strong>
              </div>
              @for (phase of architectureSplitPlan(); track phase.phase) {
                <article>
                  <span>{{ phase.phase }}</span>
                  <strong>{{ phase.avg_split_score }}%</strong>
                  <em>{{ phase.services.join(' / ') }}</em>
                  <small>{{ phase.ready }} ready · {{ phase.attention }} attention · {{ phase.events }} events · {{ phase.gateway_routes }} gateway routes</small>
                </article>
              }
            </div>

            <div class="architecture-incident-queue">
              <div class="deployment-section-head">
                <span>架构治理队列</span>
                <strong>{{ architectureIncidents().length }} 项</strong>
              </div>
              @for (incident of architectureIncidents(); track incident.id) {
                <a [routerLink]="incident.path" [class.p0]="incident.priority === 'P0'" [class.p1]="incident.priority === 'P1'">
                  <span>{{ incident.priority }} · {{ incident.owner }}</span>
                  <strong>{{ incident.title }}</strong>
                  <em>{{ incident.runtime_unit }} · error budget {{ incident.error_budget_remaining }}%</em>
                  <small>{{ incident.evidence }}</small>
                  <b>{{ incident.signal_coverage }}% obs / {{ incident.contract_coverage }}% contract</b>
                </a>
              }
            </div>
          </section>

          <section class="erp-maturity-board" aria-label="ERP 成熟度验收">
            <article class="erp-maturity-score" [class.ready]="deploymentReadiness().maturity.summary.level === 'ready'" [class.blocked]="deploymentReadiness().maturity.summary.level === 'blocked'">
              <span>行业成熟度</span>
              <strong>{{ deploymentReadiness().maturity.summary.score }}%</strong>
              <em>{{ deploymentReadiness().maturity.summary.target }}</em>
              <small>{{ deploymentReadiness().maturity.summary.next_action }}</small>
            </article>

            <div class="erp-maturity-dimensions">
              <div class="deployment-section-head">
                <span>验收维度</span>
                <strong>{{ deploymentReadiness().maturity.summary.ready }} ready / {{ deploymentReadiness().maturity.summary.attention }} attention / {{ deploymentReadiness().maturity.summary.blocked }} blocked</strong>
              </div>
              @for (dimension of maturityDimensions(); track dimension.key) {
                <article [class.ready]="dimension.level === 'ready'" [class.blocked]="dimension.level === 'blocked'" [class.attention]="dimension.level === 'attention'">
                  <div>
                    <span>{{ dimension.label }}</span>
                    <strong>{{ dimension.score }}%</strong>
                  </div>
                  <i aria-hidden="true"><small [style.width.%]="dimension.score"></small></i>
                  <em>{{ dimension.evidence }}</em>
                  <small>{{ dimension.action }}</small>
                </article>
              }
            </div>
          </section>

          <section class="erp-capability-map" aria-label="能力域与服务拓扑">
            <div class="deployment-section-head">
              <span>能力域地图</span>
              <strong>{{ maturityCapabilities().length }} 域 / {{ maturityTopologyNodes().length }} 服务节点 / {{ deploymentReadiness().maturity.topology_edges.length }} 依赖边</strong>
            </div>
            <div class="erp-capability-grid">
              @for (capability of maturityCapabilities(); track capability.domain) {
                <article [class.attention]="capability.attention > 0">
                  <span>{{ capability.domain }}</span>
                  <strong>{{ capability.avg_readiness }}%</strong>
                  <em>{{ capability.services }} 服务 · {{ capability.contracts }} 契约 · {{ capability.api_surfaces }} API</em>
                  <small>{{ capability.modules.join(' / ') }}</small>
                </article>
              }
            </div>
            <div class="erp-topology-list">
              @for (node of maturityTopologyNodes(); track node.id) {
                <a [routerLink]="node.path" [class.attention]="node.status !== 'healthy'">
                  <span>{{ node.domain }}</span>
                  <strong>{{ node.name }}</strong>
                  <em>{{ node.runtime_unit }} · {{ node.owner }}</em>
                  <small>{{ node.risk_note }}</small>
                  <b>{{ node.readiness }}%</b>
                </a>
              }
            </div>
            <div class="erp-evidence-strip" aria-label="交付证据">
              @for (item of maturityEvidence(); track item.path) {
                <article [class.ready]="item.status === 'ready'" [class.blocked]="item.status === 'blocked'">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.path }}</strong>
                  <em>{{ item.description }}</em>
                </article>
              }
            </div>
          </section>

          <div class="deployment-token-grid" aria-label="Token 获取入口">
            @for (item of deploymentLinks; track item.title) {
              <a [href]="item.url" target="_blank" rel="noopener noreferrer">
                <span>
                  <strong>{{ item.title }}</strong>
                  <em>{{ item.description }}</em>
                </span>
                <p-tag [severity]="item.secret ? 'warn' : 'info'" [value]="item.variable" />
                <small>{{ item.scope === 'frontend' ? '前端变量' : item.scope === 'backend' ? '后端变量' : '脚本变量' }}</small>
              </a>
            }
          </div>

          <div class="deployment-copy-grid" aria-label="可复制部署命令">
            @for (item of deploymentRunbookItems(); track item.title) {
              <article>
                <span>{{ item.title }}</span>
                <strong>{{ item.description }}</strong>
                <code>{{ item.command }}</code>
                <button pButton type="button" severity="secondary" (click)="copyCommand(item.command)" [attr.aria-label]="'复制 ' + item.title">
                  <i class="pi pi-copy"></i>
                  复制命令
                </button>
              </article>
            }
          </div>

          <div class="settings-note">
            <strong>部署手册：docs/api-token-deployment-guide.md</strong>
            <span>页面只提供入口和命令模板；真实 Token、数据库密码、AI Key 和 Cloudinary secret 仍由 Vercel 后端项目或本地部署脚本保存。</span>
          </div>
        </article>
      </section>
    </section>
  `
})
export class SettingsPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly theme = inject(ThemeService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly deploymentTaskCreating = signal('');
  protected readonly deploymentTaskCreated = signal('');
  protected readonly aiSettings = signal<AiSettings>(EMPTY_AI_SETTINGS);
  protected readonly deploymentReadiness = signal<DeploymentReadiness>(EMPTY_DEPLOYMENT_READINESS);
  protected readonly settingsPhotos = COMMAND_CENTER_PHOTOS.slice(4, 8);
  protected readonly readinessChecks = computed(() => {
    const priority: Record<string, number> = { blocked: 0, attention: 1, ready: 2 };
    return [...this.deploymentReadiness().checks]
      .sort((a, b) => (priority[a.status] ?? 9) - (priority[b.status] ?? 9))
      .slice(0, 12);
  });
  protected readonly readinessRunbook = computed(() => this.deploymentReadiness().runbook.slice(0, 5));
  protected readonly readinessDomains = computed(() => this.deploymentReadiness().service_snapshot.domains.slice(0, 6));
  protected readonly architectureSignals = computed(() => this.deploymentReadiness().service_snapshot.observability.signals.slice(0, 3));
  protected readonly architectureSplitPlan = computed(() => this.deploymentReadiness().service_snapshot.split_plan.slice(0, 5));
  protected readonly architectureIncidents = computed(() => this.deploymentReadiness().service_snapshot.incident_queue.slice(0, 4));
  protected readonly maturityDimensions = computed(() => {
    const priority: Record<string, number> = { blocked: 0, attention: 1, ready: 2 };
    return [...this.deploymentReadiness().maturity.dimensions]
      .sort((a, b) => (priority[a.level] ?? 9) - (priority[b.level] ?? 9))
      .slice(0, 6);
  });
  protected readonly maturityCapabilities = computed(() => [...this.deploymentReadiness().maturity.capability_map]
    .sort((a, b) => b.attention - a.attention || b.avg_readiness - a.avg_readiness)
    .slice(0, 6));
  protected readonly maturityTopologyNodes = computed(() => [...this.deploymentReadiness().maturity.topology_nodes]
    .sort((a, b) => (a.status === 'healthy' ? 1 : 0) - (b.status === 'healthy' ? 1 : 0) || b.readiness - a.readiness)
    .slice(0, 8));
  protected readonly maturityEvidence = computed(() => {
    const priority: Record<string, number> = { blocked: 0, attention: 1, ready: 2 };
    return [...this.deploymentReadiness().maturity.evidence]
      .sort((a, b) => (priority[a.status] ?? 9) - (priority[b.status] ?? 9))
      .slice(0, 8);
  });
  protected readonly deploymentRunbookItems = computed<DeploymentCommand[]>(() => {
    const runbook = this.readinessRunbook();
    if (!runbook.length) {
      return this.deploymentCommands;
    }
    return runbook.map(item => ({
      title: item.step,
      description: '部署运行手册步骤',
      command: item.command
    }));
  });
  protected preferenceDraft: UserPreferences = {
    theme: 'light-luxury',
    density: 'compact',
    default_workspace: '/app/overview',
    charts_motion: 'standard',
    dock_labels: 'hover',
    context_panel: 'visible'
  };
  protected aiDraft: { analysis_mode: AiSettings['analysis_mode']; ai_api_base: string; ai_api_key: string; ai_model: string } = {
    analysis_mode: 'local',
    ai_api_base: '',
    ai_api_key: '',
    ai_model: 'deepseek-chat'
  };
  protected readonly deploymentLinks: DeploymentLink[] = [
    {
      title: 'Vercel Token',
      description: 'Account Settings / Tokens，供一键部署脚本使用。',
      url: 'https://vercel.com/account/settings/tokens',
      variable: 'VERCEL_TOKEN',
      secret: true,
      scope: 'script'
    },
    {
      title: 'Supabase Database',
      description: 'Project Settings / Database，复制 Pooler PostgreSQL URL。',
      url: 'https://supabase.com/dashboard/projects',
      variable: 'DATABASE_URL',
      secret: true,
      scope: 'backend'
    },
    {
      title: 'Supabase API Keys',
      description: '后续接 Storage 或 Edge API 时使用，当前前端不直连。',
      url: 'https://supabase.com/dashboard/projects',
      variable: 'SUPABASE_KEYS',
      secret: true,
      scope: 'backend'
    },
    {
      title: 'Cloudinary API Keys',
      description: '生产头像与文件持久化存储。',
      url: 'https://console.cloudinary.com/settings/api-keys',
      variable: 'CLOUDINARY_URL',
      secret: true,
      scope: 'backend'
    },
    {
      title: 'DeepSeek API Key',
      description: 'AI 经营分析外部模型，兼容 Chat Completions。',
      url: 'https://platform.deepseek.com/api_keys',
      variable: 'DEEPSEEK_API_KEY',
      secret: true,
      scope: 'backend'
    },
    {
      title: '前端 API 地址',
      description: 'Vercel 前端项目环境变量，只填写后端 /api/v1 地址。',
      url: 'https://vercel.com/docs/environment-variables',
      variable: 'NEXUS_API_BASE_URL',
      secret: false,
      scope: 'frontend'
    }
  ];
  protected readonly deploymentCommands: DeploymentCommand[] = [
    {
      title: '生成 SECRET_KEY',
      description: '本地生成后写入后端 Vercel 项目。',
      command: '[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))'
    },
    {
      title: '写入后端数据库',
      description: '在 backend 项目中添加 Supabase PostgreSQL 连接串。',
      command: 'vercel env add DATABASE_URL production --sensitive'
    },
    {
      title: '写入前端 API',
      description: '在 frontend 项目中添加公开 API 地址。',
      command: 'vercel env add NEXUS_API_BASE_URL production'
    },
    {
      title: '一键预检部署',
      description: '从仓库根目录执行前后端部署与数据同步。',
      command: '.\\scripts\\deploy-supabase-vercel.ps1 -DatabaseUrl "postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require" -BackendProjectName "nexus-prime-api" -FrontendProjectName "nexus-prime-web" -SyncDatabase -SecretKey "<32位以上随机字符串>" -CloudinaryUrl "cloudinary://api_key:api_secret@cloud_name"'
    }
  ];

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      preferences: this.api.preferences().pipe(catchError(() => of({} as UserPreferences))),
      ai: this.api.get<AiSettings>('ai/settings').pipe(catchError(() => of(EMPTY_AI_SETTINGS))),
      deployment: this.api.get<DeploymentReadiness>('operations/deployment-readiness').pipe(catchError(() => of(EMPTY_DEPLOYMENT_READINESS)))
    }).pipe(finalize(() => this.loading.set(false))).subscribe(({ preferences, ai, deployment }) => {
      this.preferenceDraft = {
        theme: preferences.theme ?? this.theme.mode(),
        density: preferences.density ?? 'compact',
        default_workspace: preferences.default_workspace ?? '/app/overview',
        charts_motion: preferences.charts_motion ?? 'standard',
        dock_labels: preferences.dock_labels ?? 'hover',
        context_panel: preferences.context_panel ?? 'visible'
      };
      this.theme.setPreferences(this.preferenceDraft, false);
      this.aiSettings.set(ai);
      this.deploymentReadiness.set(deployment);
      this.aiDraft = {
        analysis_mode: ai.analysis_mode,
        ai_api_base: ai.external_base || '',
        ai_api_key: '',
        ai_model: ai.model || 'deepseek-chat'
      };
    });
  }

  setTheme(mode: ThemeMode): void {
    this.preferenceDraft.theme = mode;
    this.theme.setPreferences(this.preferenceDraft, false);
  }

  saveAll(): void {
    this.saving.set(true);
    forkJoin({
      preferences: this.api.savePreferences(this.preferenceDraft),
      ai: this.api.put<AiSettings>('ai/settings', this.aiDraft)
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '设置未保存', detail: error?.message || '请检查配置内容。' });
        return of(null);
      }),
      finalize(() => this.saving.set(false))
    ).subscribe(result => {
      if (!result) {
        return;
      }
      this.preferenceDraft = { ...this.preferenceDraft, ...result.preferences };
      this.aiSettings.set(result.ai);
      this.theme.setPreferences(result.preferences, false);
      this.messages.add({ severity: 'success', summary: '设置已保存', detail: '全局偏好和 AI 服务设置已更新。' });
    });
  }

  async copyCommand(command: string): Promise<void> {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(command);
      } else if (!this.fallbackCopy(command)) {
        throw new Error('clipboard_unavailable');
      }
      this.messages.add({ severity: 'success', summary: '已复制', detail: '部署命令已复制到剪贴板。' });
    } catch {
      this.messages.add({ severity: 'warn', summary: '复制失败', detail: '请手动复制命令，浏览器未开放剪贴板权限。' });
    }
  }

  protected createDeploymentTask(check: DeploymentReadinessCheck): void {
    if (check.status === 'ready' || this.deploymentTaskCreating()) {
      return;
    }
    this.deploymentTaskCreating.set(check.key);
    this.api.post<DataRecord>('operations/deployment-readiness/task', {
      key: check.key,
      label: check.label,
      scope: check.scope,
      status: check.status,
      evidence: check.evidence,
      action: check.action
    }).pipe(
      catchError(error => {
        this.messages.add({
          severity: 'warn',
          summary: '任务未创建',
          detail: error?.message || '请稍后重试部署预检任务。'
        });
        return of(null);
      }),
      finalize(() => this.deploymentTaskCreating.set(''))
    ).subscribe(result => {
      if (!result) {
        return;
      }
      this.deploymentTaskCreated.set(check.key);
      this.messages.add({
        severity: 'success',
        summary: '部署任务已创建',
        detail: `${check.label} 已写入通知中心和审计日志。`
      });
    });
  }

  protected statusSeverity(status: string): 'success' | 'warn' | 'danger' | 'info' {
    if (status === 'ready') {
      return 'success';
    }
    if (status === 'blocked') {
      return 'danger';
    }
    if (status === 'attention') {
      return 'warn';
    }
    return 'info';
  }

  private fallbackCopy(value: string): boolean {
    const textarea = document.createElement('textarea');
    textarea.value = value;
    textarea.setAttribute('readonly', 'true');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      return document.execCommand('copy');
    } finally {
      document.body.removeChild(textarea);
    }
  }
}
