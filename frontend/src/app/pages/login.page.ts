import { CommonModule } from '@angular/common';
import { AfterViewInit, Component, ElementRef, inject, OnDestroy, OnInit, signal, ViewChild } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { catchError, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import {
  authFallbackImage,
  authPanelVideoSource,
  authVideoSource,
  LANDING_POSTER
} from '../core/landing-visuals';
import { ThemeService } from '../core/theme.service';
import { environment } from '../../environments/environment';
import type { DemoAccountRole } from '../../environments/environment.model';
import { NexusRevealDirective, NexusSpotlightDirective } from '../motion';

interface RegisterPolicy {
  terms_version: string;
  permissions: string[];
  required_acceptances: string[];
}

interface CaptchaChallenge {
  token: string;
  image: string;
  image_data_url: string;
  prompt: string;
  expires_in: number;
  terms_version: string;
}

type AuthMode = 'login' | 'register';
type LoginFieldName = 'email' | 'password' | 'confirm_password' | 'full_name' | 'username' | 'position' | 'department_name' | 'captcha_answer';

interface CapabilityTile {
  icon: string;
  title: string;
  body: string;
}

interface AuthModeStripItem {
  icon: string;
  label: string;
  value: string;
}

interface AuthIntelItem {
  label: string;
  value: string;
  body: string;
}

interface AuthMetric {
  label: string;
  value: number;
}

const ROLE_ENTRIES: ReadonlyArray<{ kind: DemoAccountRole; title: string; body: string; icon: string }> = [
  { kind: 'admin', title: '管理员', body: '用户、权限、审计、全部业务写入', icon: 'pi pi-shield' },
  { kind: 'member', title: '普通用户', body: '采购、销售、文件、报表等授权流程', icon: 'pi pi-user' }
];

const REGISTER_STEPS: ReadonlyArray<{ icon: string; label: string }> = [
  { icon: 'pi pi-id-card', label: '资料完整' },
  { icon: 'pi pi-envelope', label: '邮箱唯一' },
  { icon: 'pi pi-eye', label: '验证码识别' },
  { icon: 'pi pi-file-check', label: '许可确认' },
  { icon: 'pi pi-history', label: '审计留痕' }
];

const CAPABILITY_TILES: Record<AuthMode, ReadonlyArray<CapabilityTile>> = {
  register: [
    { icon: 'pi pi-user-plus', title: '成员账号', body: '默认普通权限' },
    { icon: 'pi pi-shield', title: '许可确认', body: '服务与隐私' },
    { icon: 'pi pi-eye', title: '验证码', body: '人工识别' },
    { icon: 'pi pi-history', title: '审计记录', body: '注册留痕' }
  ],
  login: [
    { icon: 'pi pi-database', title: '数据记录', body: '业务写入留痕' },
    { icon: 'pi pi-shield', title: '权限矩阵', body: '角色差异访问' },
    { icon: 'pi pi-comments', title: '协同审计', body: '流程通知闭环' },
    { icon: 'pi pi-chart-line', title: '经营分析', body: '指标与图表' }
  ]
};

const AUTH_MODE_STRIP: Record<AuthMode, ReadonlyArray<AuthModeStripItem>> = {
  register: [
    { icon: 'pi pi-id-card', label: '账号资料', value: '完整性校验' },
    { icon: 'pi pi-file-check', label: '服务许可', value: '版本锁定' },
    { icon: 'pi pi-history', label: '审计链路', value: '注册留痕' }
  ],
  login: [
    { icon: 'pi pi-key', label: '会话密钥', value: '已准备' },
    { icon: 'pi pi-shield', label: '角色边界', value: '按账号注入' },
    { icon: 'pi pi-chart-line', label: '经营入口', value: '总览跳转' }
  ]
};

const VISUAL_METRICS: Record<AuthMode, ReadonlyArray<AuthMetric>> = {
  register: [
    { label: '资料', value: 88 },
    { label: '校验', value: 76 },
    { label: '许可', value: 94 }
  ],
  login: [
    { label: '会话', value: 92 },
    { label: '权限', value: 84 },
    { label: '审计', value: 97 }
  ]
};

const AUTH_HERO_KICKER: Record<AuthMode, string> = {
  register: 'Robotic onboarding',
  login: 'Server access'
};

const AUTH_HERO_COPY: Record<AuthMode, string> = {
  register: '新成员资料、岗位边界和许可确认进入同一条可审计链路。',
  login: '会话、角色和关键动作在进入工作台之前完成准入校验。'
};

const STAGE_TITLE_LINES: Record<AuthMode, readonly string[]> = {
  register: ['成员入网', '准入许可'],
  login: ['安全准入', '经营中枢']
};

const LOGIN_LIVE_TAGS = ['Session sealed', 'Role scoped', 'Trace live'] as const;
const LOGIN_INTEL_RAIL: ReadonlyArray<AuthIntelItem> = [
  { label: 'Identity', value: '2 roles', body: '管理员 / 普通用户' },
  { label: 'Session', value: 'CSRF', body: '安全令牌校验' },
  { label: 'Trace', value: 'Live', body: '登录动作留痕' }
];

const AUTH_VALIDATED_FIELDS = [
  'full_name',
  'username',
  'position',
  'department_name',
  'password',
  'confirm_password',
  'captcha_answer',
  'accepted_terms',
  'accepted_privacy',
  'accepted_data_scope'
] as const;

const LOGIN_PASSWORD_VALIDATORS = [Validators.required, Validators.minLength(6)];
const REGISTER_PASSWORD_VALIDATORS = [Validators.required, Validators.minLength(8), Validators.pattern(/^(?=.*[A-Za-z])(?=.*\d).{8,}$/)];
const REQUIRED_PROFILE_VALIDATORS = [Validators.required, Validators.minLength(2)];
const USERNAME_VALIDATORS = [Validators.required, Validators.minLength(3), Validators.pattern(/^[a-zA-Z0-9._-]+$/)];
const REQUIRED_CONFIRMATION_VALIDATORS = [Validators.required];
const REQUIRED_CAPTCHA_VALIDATORS = [Validators.required, Validators.minLength(1)];
const REQUIRED_ACCEPTANCE_VALIDATORS = [Validators.requiredTrue];

@Component({
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    ReactiveFormsModule,
    ButtonModule,
    InputTextModule,
    NexusRevealDirective,
    NexusSpotlightDirective
  ],
  template: `
    <main class="login-screen nexus-login-redesign" [class.register-screen]="authMode() === 'register'">
      <div class="auth-video-stage" aria-hidden="true">
        <video
          #authVideo
          class="auth-video-bg"
          autoplay
          muted
          loop
          playsinline
          preload="auto"
          [poster]="poster"
          [src]="authVideoSource()"
          (canplay)="playBackgroundVideo($event)"
          (loadeddata)="playBackgroundVideo($event)"
        >
        </video>
        <div class="auth-video-aurora"></div>
        <div class="auth-data-scan"></div>
        <div class="auth-video-wash"></div>
        <div class="auth-depth-grid"></div>
      </div>
      <section class="login-stage" aria-label="NEXUS Prime 登录">
        <a class="login-back-link" routerLink="/" nexusReveal [nexusRevealDelay]="40">
          <i class="pi pi-arrow-left"></i>
          首页
        </a>

        <div class="login-composition" [class.register-composition]="authMode() === 'register'">
          <aside class="login-identity-panel" aria-label="入口现场" nexusReveal [nexusRevealDelay]="110">
            <figure class="login-photo-card" nexusSpotlight>
              <video
                #authPanelVideo
                class="auth-panel-video"
                autoplay
                muted
                loop
                playsinline
                preload="auto"
                [poster]="poster"
                [src]="authPanelVideoSource()"
                (canplay)="playPanelVideo($event)"
                (loadeddata)="playPanelVideo($event)"
              >
              </video>
              <img [src]="authFallbackImage()" alt="制造与仓配现场" />
              <figcaption>
                <span>{{ authHeroKicker() }}</span>
                <strong class="auth-stage-title" [attr.aria-label]="authMode() === 'register' ? '创建普通成员账号' : '进入经营工作台'">
                  @for (line of stageTitleLines(); track line) {
                    <span>{{ line }}</span>
                  }
                </strong>
                <p>{{ authHeroCopy() }}</p>
              </figcaption>
            </figure>

            @if (authMode() === 'login') {
              <div class="login-live-strip" aria-label="入口状态" nexusReveal [nexusRevealDelay]="160">
                @for (item of authLiveTags(); track item) {
                  <span>{{ item }}</span>
                }
              </div>

              <div class="auth-intel-rail" aria-label="准入态势">
                @for (item of authIntelRail(); track item.label) {
                  <article nexusSpotlight>
                    <span>{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                    <em>{{ item.body }}</em>
                  </article>
                }
              </div>
            }
          </aside>

          <section
            class="login-panel enterprise-login-panel login-card-shell"
            [class.register-mode]="authMode() === 'register'"
            nexusReveal
            nexusSpotlight
            [nexusRevealDelay]="170"
          >
            <button
              pButton
              type="button"
              class="theme-fab"
              [text]="true"
              [rounded]="true"
              (click)="toggleTheme()"
              [attr.aria-label]="theme.mode() === 'dark-cockpit' ? '切换到亮色主题' : '切换到暗色主题'"
              [attr.title]="theme.mode() === 'dark-cockpit' ? '切换到亮色主题' : '切换到暗色主题'"
            >
              <i class="pi" [ngClass]="theme.mode() === 'dark-cockpit' ? 'pi-sun' : 'pi-moon'"></i>
            </button>

            <div class="brand-lockup">
              <div class="brand-mark">NX</div>
              <div>
                <p>{{ authMode() === 'login' ? 'AUTHORIZED ACCESS' : 'MEMBER ACCOUNT' }}</p>
                <h1>{{ authMode() === 'login' ? '欢迎回来' : '创建账号' }}</h1>
              </div>
            </div>

            <div class="login-copy">
              <p>{{ authMode() === 'login' ? '选择身份，进入对应工作台。' : '普通成员账号，注册后按岗位授权。' }}</p>
              @if (authMode() === 'register') {
                <div class="register-policy-strip">
                  <span>许可版本 {{ registerPolicy()?.terms_version || captcha()?.terms_version || '读取中' }}</span>
                  <button type="button" (click)="openPolicyTop()">查看许可</button>
                </div>
              }
            </div>

            <div class="auth-mode-strip" aria-label="准入模式">
              @for (item of authModeStrip(); track item.label) {
                <span nexusSpotlight>
                  <i [class]="item.icon"></i>
                  <strong>{{ item.label }}</strong>
                  <em>{{ item.value }}</em>
                </span>
              }
            </div>

            @if (authMode() === 'login') {
              @if (demoRoleEntries().length) {
                <div class="login-role-switch" aria-label="账号角色">
                  @for (entry of demoRoleEntries(); track entry.kind) {
                    <button type="button" [class.active]="selectedRole() === entry.kind" (click)="prefillRole(entry.kind)" nexusSpotlight>
                      <i [class]="entry.icon"></i>
                      <strong>{{ entry.title }}</strong>
                      <span>{{ entry.body }}</span>
                    </button>
                  }
                </div>
              }
            } @else {
              <div class="register-assurance-strip" aria-label="注册流程">
                @for (step of registerSteps; track step.label) {
                  <span nexusSpotlight><i [class]="step.icon"></i>{{ step.label }}</span>
                }
              </div>
            }

            <section class="auth-visual-core" aria-label="访问准入图" nexusReveal nexusSpotlight [nexusRevealDelay]="230">
              <div class="auth-orbit" aria-hidden="true">
                <span class="orbit-node node-user"><i class="pi pi-user"></i></span>
                <span class="orbit-node node-role"><i class="pi pi-key"></i></span>
                <span class="orbit-node node-audit"><i class="pi pi-history"></i></span>
                <strong>NX</strong>
              </div>
              <div class="auth-signal-chart" aria-label="认证链路状态">
                @for (metric of visualMetrics(); track metric.label) {
                  <span [style.--bar]="metric.value + '%'">
                    <em>{{ metric.label }}</em>
                    <i></i>
                    <strong>{{ metric.value }}%</strong>
                  </span>
                }
              </div>
            </section>

            <form id="login-form" [formGroup]="form" (ngSubmit)="submit()" class="login-form" novalidate nexusReveal [nexusRevealDelay]="260">
              @if (csrfReady() === false) {
                <div class="login-alert warn" role="status">
                  <i class="pi pi-wifi"></i>
                  <span>安全会话准备中，请稍后重试或联系系统管理员。</span>
                </div>
              }

              @if (errorMessage()) {
                <div class="login-alert danger" role="alert">
                  <i class="pi pi-exclamation-circle"></i>
                  <span>{{ errorMessage() }}</span>
                </div>
              }

              @if (authMode() === 'register') {
                <label class="login-field">
                  <span>姓名</span>
                  <input
                    pInputText
                    formControlName="full_name"
                    autocomplete="name"
                    placeholder="例如：林知远"
                    [class.ng-invalid]="fieldInvalid('full_name')"
                  />
                  @if (fieldInvalid('full_name')) {
                    <small>{{ fieldMessage('full_name', '请输入姓名或岗位昵称。') }}</small>
                  }
                </label>

                <label class="login-field">
                  <span>用户名</span>
                  <input
                    pInputText
                    formControlName="username"
                    autocomplete="username"
                    placeholder="例如：warehouse.ops"
                    [class.ng-invalid]="fieldInvalid('username')"
                  />
                  @if (fieldInvalid('username')) {
                    <small>{{ fieldMessage('username', '用户名需为 3-32 位字母、数字、点、下划线或短横线。') }}</small>
                  }
                </label>

                <label class="login-field">
                  <span>岗位</span>
                  <input
                    pInputText
                    formControlName="position"
                    autocomplete="organization-title"
                    placeholder="例如：仓配运营专员"
                    [class.ng-invalid]="fieldInvalid('position')"
                  />
                  @if (fieldInvalid('position')) {
                    <small>{{ fieldMessage('position', '请输入岗位或业务角色。') }}</small>
                  }
                </label>

                <label class="login-field">
                  <span>部门</span>
                  <input
                    pInputText
                    formControlName="department_name"
                    autocomplete="organization"
                    placeholder="例如：供应链运营部"
                    [class.ng-invalid]="fieldInvalid('department_name')"
                  />
                  @if (fieldInvalid('department_name')) {
                    <small>{{ fieldMessage('department_name', '请输入所属部门。') }}</small>
                  }
                </label>

                <label class="login-field">
                  <span>手机号</span>
                  <input
                    pInputText
                    formControlName="phone"
                    autocomplete="tel"
                    placeholder="用于通知与身份核验"
                  />
                </label>
              }

              <label class="login-field">
                <span>邮箱</span>
                <input
                  pInputText
                  type="email"
                  formControlName="email"
                  autocomplete="email"
                  placeholder="name@company.com"
                  [class.ng-invalid]="fieldInvalid('email')"
                />
                @if (fieldInvalid('email')) {
                  <small>{{ fieldMessage('email', '请输入有效邮箱地址。') }}</small>
                }
              </label>

              <label class="login-field">
                <span>密码</span>
                <input
                  pInputText
                  type="password"
                  formControlName="password"
                  [autocomplete]="authMode() === 'login' ? 'current-password' : 'new-password'"
                  placeholder="输入账号密码"
                  [class.ng-invalid]="fieldInvalid('password')"
                />
                @if (fieldInvalid('password')) {
                  <small>{{ fieldMessage('password', authMode() === 'register' ? '密码至少 8 位，并包含字母和数字。' : '请输入账号密码。') }}</small>
                }
              </label>

              @if (authMode() === 'register') {
                <label class="login-field">
                  <span>确认密码</span>
                  <input
                    pInputText
                    type="password"
                    formControlName="confirm_password"
                    autocomplete="new-password"
                    placeholder="再次输入密码"
                    [class.ng-invalid]="fieldInvalid('confirm_password')"
                  />
                  @if (fieldInvalid('confirm_password')) {
                    <small>{{ fieldMessage('confirm_password', '两次密码需要保持一致。') }}</small>
                  }
                </label>
              }

              @if (authMode() === 'register') {
                <section class="register-verification" aria-label="注册验证码" nexusSpotlight>
                  <div>
                    <span>验证码识别</span>
                    <strong>{{ captcha()?.prompt || '正在生成验证码' }}</strong>
                  </div>
                  @if (captcha(); as challenge) {
                    <img [src]="challenge.image_data_url" alt="注册验证码" />
                  } @else {
                    <div class="captcha-skeleton">生成中</div>
                  }
                  <label class="login-field captcha-answer">
                    <span>输入结果</span>
                    <input
                      pInputText
                      formControlName="captcha_answer"
                      autocomplete="off"
                      placeholder="输入图中结果"
                      [class.ng-invalid]="fieldInvalid('captcha_answer')"
                    />
                    @if (fieldInvalid('captcha_answer')) {
                      <small>{{ fieldMessage('captcha_answer', '请输入验证码结果。') }}</small>
                    }
                  </label>
                  <button type="button" class="captcha-refresh" (click)="loadCaptcha()" [disabled]="captchaLoading()">
                    <i class="pi pi-refresh"></i>
                    换一张
                  </button>
                </section>

                <section class="register-consent" aria-label="注册许可确认" nexusSpotlight>
                  <div class="register-consent-head">
                    <strong>许可确认</strong>
                    <nav aria-label="注册许可">
                      <button type="button" (click)="openPolicy('terms')">服务许可</button>
                      <button type="button" (click)="openPolicy('privacy')">隐私说明</button>
                      <button type="button" (click)="openPolicy('data_scope')">数据范围</button>
                    </nav>
                  </div>
                  <label>
                    <input type="checkbox" formControlName="accepted_terms" />
                    <span>我已阅读并同意《NEXUS Prime 服务许可》。</span>
                  </label>
                  <label>
                    <input type="checkbox" formControlName="accepted_privacy" />
                    <span>我理解系统会保存登录、注册资料和业务审计记录。</span>
                  </label>
                  <label>
                    <input type="checkbox" formControlName="accepted_data_scope" />
                    <span>我同意管理员按岗位分配采购、销售、文件、报表等权限。</span>
                  </label>
                </section>
              }

              <button pButton type="submit" [loading]="loading()" [disabled]="submitDisabled()" class="login-submit" nexusSpotlight>
                {{ authMode() === 'login' ? '进入系统' : '注册并进入' }}
                <i class="pi pi-arrow-right"></i>
              </button>
            </form>

            <div class="login-capabilities" aria-label="系统能力">
              @for (item of capabilityTiles(); track item.title) {
                <div nexusSpotlight>
                  <i [class]="item.icon"></i>
                  <strong>{{ item.title }}</strong>
                  <span>{{ item.body }}</span>
                </div>
              }
            </div>

            <div class="login-footnote">
              <span>{{ authMode() === 'login' ? '可信网络访问。' : '已有账号可直接登录。' }}</span>
              @if (authMode() === 'login') {
                @for (entry of demoRoleEntries(); track entry.kind) {
                  <button type="button" (click)="prefillRole(entry.kind)">填入{{ entry.title }}</button>
                }
                <button type="button" (click)="switchMode('register')">创建普通成员</button>
              } @else {
                <button type="button" (click)="switchMode('login')">返回登录</button>
              }
            </div>
          </section>
        </div>
      </section>
    </main>
  `
})
export class LoginPage implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('authVideo') private readonly authVideo?: ElementRef<HTMLVideoElement>;
  @ViewChild('authPanelVideo') private readonly authPanelVideo?: ElementRef<HTMLVideoElement>;

  protected readonly theme = inject(ThemeService);
  protected readonly poster = LANDING_POSTER;
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly csrfReady = signal<boolean | null>(null);
  protected readonly errorMessage = signal('');
  protected readonly authMode = signal<AuthMode>('login');
  protected readonly selectedRole = signal<DemoAccountRole>('admin');
  protected readonly captcha = signal<CaptchaChallenge | null>(null);
  protected readonly captchaLoading = signal(false);
  protected readonly registerPolicy = signal<RegisterPolicy | null>(null);
  private loginWatchdog: ReturnType<typeof setTimeout> | null = null;
  protected readonly demoRoleEntries = signal(ROLE_ENTRIES.filter(entry => Boolean(environment.demoAccounts[entry.kind])));
  protected readonly registerSteps = REGISTER_STEPS;
  protected readonly form = this.fb.nonNullable.group({
    full_name: [''],
    username: [''],
    position: [''],
    department_name: [''],
    phone: [''],
    email: ['', [Validators.required, Validators.email]],
    password: ['', LOGIN_PASSWORD_VALIDATORS],
    confirm_password: [''],
    captcha_answer: [''],
    accepted_terms: [false],
    accepted_privacy: [false],
    accepted_data_scope: [false]
  });

  ngOnInit(): void {
    this.loadRegisterPolicy();
    if (this.route.snapshot.queryParamMap.get('mode') === 'register') {
      this.switchMode('register');
    } else if (this.demoRoleEntries().length) {
      this.prefillRole(this.demoRoleEntries()[0].kind);
    }
    this.auth.ensureCsrfToken().pipe(
      catchError(() => {
        this.csrfReady.set(false);
        return of(null);
      })
    ).subscribe(result => {
      if (result) {
        this.csrfReady.set(true);
      }
    });
  }

  ngAfterViewInit(): void {
    queueMicrotask(() => this.playBackgroundVideo());
    queueMicrotask(() => this.playPanelVideo());
  }

  ngOnDestroy(): void {
    this.clearLoginWatchdog();
  }

  protected toggleTheme(): void {
    this.theme.toggle(false);
    queueMicrotask(() => this.ensureVideosPlaying());
  }

  protected playBackgroundVideo(event?: Event): void {
    const video = (event?.target as HTMLVideoElement | null) ?? this.authVideo?.nativeElement;
    if (!video) {
      return;
    }

    video.muted = true;
    video.playsInline = true;
    void video.play().catch(() => {
      // The scene background and poster keep the entrance usable if autoplay is blocked.
    });
  }

  protected playPanelVideo(event?: Event): void {
    const video = (event?.target as HTMLVideoElement | null) ?? this.authPanelVideo?.nativeElement;
    if (!video) {
      return;
    }

    video.muted = true;
    video.playsInline = true;
    void video.play().catch(() => {
      // The fallback photo remains below the cinematic overlay if autoplay is blocked.
    });
  }

  submit(): void {
    this.errorMessage.set('');
    this.form.markAllAsTouched();
    if (this.submitDisabled()) {
      return;
    }
    const raw = this.form.getRawValue();
    if (this.authMode() === 'register' && raw.password !== raw.confirm_password) {
      this.form.controls.confirm_password.setErrors({ mismatch: true });
      this.errorMessage.set('两次输入的密码不一致，请重新确认。');
      return;
    }
    this.loading.set(true);
    this.startLoginWatchdog();
    const request$ = this.authMode() === 'login'
      ? this.auth.login({ email: raw.email, password: raw.password })
      : this.auth.register({
        full_name: raw.full_name,
        username: raw.username || raw.email.split('@')[0],
        email: raw.email,
        password: raw.password,
        phone: raw.phone,
        position: raw.position || '业务协同成员',
        department_name: raw.department_name,
        accepted_terms: raw.accepted_terms,
        accepted_privacy: raw.accepted_privacy,
        accepted_data_scope: raw.accepted_data_scope,
        terms_version: this.registerPolicy()?.terms_version || this.captcha()?.terms_version || '',
        captcha_token: this.captcha()?.token || '',
        captcha_answer: raw.captcha_answer
      });
    request$.subscribe({
      next: () => {
        this.finishLoginRequest();
        if (this.authMode() === 'register') {
          this.messages.add({ severity: 'success', summary: '注册成功', detail: '账号资料已写入系统。' });
        }
        const redirect = this.safeRedirect();
        this.router.navigateByUrl(redirect);
      },
      error: error => {
        this.finishLoginRequest();
        this.applyFieldErrors(error);
        this.errorMessage.set(this.loginErrorText(error));
        if (this.authMode() === 'register') {
          this.loadCaptcha();
        }
      }
    });
  }

  prefillRole(role: DemoAccountRole): void {
    this.selectedRole.set(role);
    const account = environment.demoAccounts[role];
    if (account) {
      this.form.patchValue(account);
    }
    this.errorMessage.set('');
  }

  switchMode(mode: AuthMode): void {
    this.authMode.set(mode);
    this.errorMessage.set('');
    queueMicrotask(() => this.reloadBackgroundVideo());
    if (mode === 'register') {
      this.form.controls.full_name.setValidators(REQUIRED_PROFILE_VALIDATORS);
      this.form.controls.username.setValidators(USERNAME_VALIDATORS);
      this.form.controls.position.setValidators(REQUIRED_PROFILE_VALIDATORS);
      this.form.controls.department_name.setValidators(REQUIRED_PROFILE_VALIDATORS);
      this.form.controls.password.setValidators(REGISTER_PASSWORD_VALIDATORS);
      this.form.controls.confirm_password.setValidators(REQUIRED_CONFIRMATION_VALIDATORS);
      this.form.controls.captcha_answer.setValidators(REQUIRED_CAPTCHA_VALIDATORS);
      this.form.controls.accepted_terms.setValidators(REQUIRED_ACCEPTANCE_VALIDATORS);
      this.form.controls.accepted_privacy.setValidators(REQUIRED_ACCEPTANCE_VALIDATORS);
      this.form.controls.accepted_data_scope.setValidators(REQUIRED_ACCEPTANCE_VALIDATORS);
      this.form.patchValue({
        email: '',
        password: '',
        confirm_password: '',
        username: '',
        full_name: '',
        position: '业务协同成员',
        department_name: '供应链运营部',
        phone: '',
        captcha_answer: '',
        accepted_terms: false,
        accepted_privacy: false,
        accepted_data_scope: false
      });
      this.loadCaptcha();
    } else {
      this.form.controls.full_name.clearValidators();
      this.form.controls.username.clearValidators();
      this.form.controls.position.clearValidators();
      this.form.controls.department_name.clearValidators();
      this.form.controls.password.setValidators(LOGIN_PASSWORD_VALIDATORS);
      this.form.controls.confirm_password.clearValidators();
      this.form.controls.captcha_answer.clearValidators();
      this.form.controls.accepted_terms.clearValidators();
      this.form.controls.accepted_privacy.clearValidators();
      this.form.controls.accepted_data_scope.clearValidators();
      this.captcha.set(null);
      if (this.demoRoleEntries().length) {
        this.prefillRole(this.demoRoleEntries()[0].kind);
      }
    }
    AUTH_VALIDATED_FIELDS.forEach(field => this.form.controls[field].updateValueAndValidity());
  }

  fieldInvalid(name: LoginFieldName): boolean {
    const control = this.form.controls[name];
    return control.invalid && (control.dirty || control.touched);
  }

  fieldMessage(name: LoginFieldName, fallback: string): string {
    const serverMessage = this.form.controls[name].errors?.['server'];
    return typeof serverMessage === 'string' ? serverMessage : fallback;
  }

  submitDisabled(): boolean {
    if (this.loading() || this.csrfReady() === false || this.form.invalid) {
      return true;
    }
    return this.authMode() === 'register' && (!this.captcha() || this.captchaLoading());
  }

  loadCaptcha(): void {
    if (this.captchaLoading()) {
      return;
    }
    this.captchaLoading.set(true);
    this.api.get<CaptchaChallenge>('auth/captcha').pipe(
      catchError(() => {
        this.errorMessage.set('验证码生成失败，请稍后重试或联系系统管理员。');
        return of(null);
      })
    ).subscribe(result => {
      this.captchaLoading.set(false);
      if (result) {
        this.captcha.set(result);
        this.form.controls.captcha_answer.setValue('');
        this.form.controls.captcha_answer.markAsPristine();
        this.form.controls.captcha_answer.markAsUntouched();
      }
    });
  }

  capabilityTiles(): ReadonlyArray<CapabilityTile> {
    return CAPABILITY_TILES[this.authMode()];
  }

  authVideoSource(): string {
    return authVideoSource(this.authMode(), this.theme.mode());
  }

  authPanelVideoSource(): string {
    return authPanelVideoSource(this.authMode(), this.theme.mode());
  }

  authFallbackImage(): string {
    return authFallbackImage(this.authMode());
  }

  authHeroKicker(): string {
    return AUTH_HERO_KICKER[this.authMode()];
  }

  authHeroCopy(): string {
    return AUTH_HERO_COPY[this.authMode()];
  }

  authLiveTags(): readonly string[] {
    return LOGIN_LIVE_TAGS;
  }

  authIntelRail(): ReadonlyArray<AuthIntelItem> {
    return LOGIN_INTEL_RAIL;
  }

  authModeStrip(): ReadonlyArray<AuthModeStripItem> {
    return AUTH_MODE_STRIP[this.authMode()];
  }

  visualMetrics(): ReadonlyArray<AuthMetric> {
    return VISUAL_METRICS[this.authMode()];
  }

  stageTitleLines(): readonly string[] {
    return STAGE_TITLE_LINES[this.authMode()];
  }

  private reloadBackgroundVideo(): void {
    const video = this.authVideo?.nativeElement;
    if (video) {
      video.load();
      this.playBackgroundVideo();
    }

    const panelVideo = this.authPanelVideo?.nativeElement;
    if (panelVideo) {
      panelVideo.load();
      this.playPanelVideo();
    }
  }

  private ensureVideosPlaying(): void {
    this.playBackgroundVideo();
    this.playPanelVideo();
  }

  openPolicy(fragment: 'terms' | 'privacy' | 'data_scope'): void {
    this.router.navigate(['/auth/register-policy'], { fragment });
  }

  openPolicyTop(): void {
    this.router.navigate(['/auth/register-policy']);
  }

  private loadRegisterPolicy(): void {
    this.api.get<RegisterPolicy>('auth/register-policy').pipe(
      catchError(() => of(null))
    ).subscribe(result => {
      if (result) {
        this.registerPolicy.set(result);
      }
    });
  }

  private safeRedirect(): string {
    const redirect = this.route.snapshot.queryParamMap.get('redirect') || '';
    return redirect.startsWith('/app/') ? redirect : '/app/overview';
  }

  private loginErrorText(error: unknown): string {
    const status = typeof error === 'object' && error !== null && 'status' in error ? Number((error as { status?: number }).status) : undefined;
    if (status === 0) {
      return '暂时无法连接安全会话服务，请稍后重试或联系系统管理员。';
    }
    return error instanceof Error ? error.message : '登录失败，请稍后重试。';
  }

  private applyFieldErrors(error: unknown): void {
    if (typeof error !== 'object' || error === null || !('fields' in error)) {
      return;
    }
    const fields = (error as { fields?: Record<string, string> }).fields ?? {};
    Object.keys(fields).forEach(key => {
      if (key in this.form.controls) {
        const control = this.form.controls[key as keyof typeof this.form.controls];
        control.setErrors({ server: fields[key] });
        control.markAsTouched();
      }
    });
  }

  private startLoginWatchdog(): void {
    this.clearLoginWatchdog();
    this.loginWatchdog = setTimeout(() => {
      if (!this.loading()) {
        return;
      }
      this.loading.set(false);
      this.errorMessage.set('登录请求没有完成，请检查账号密码或稍后重试。');
    }, 8000);
  }

  private finishLoginRequest(): void {
    this.loading.set(false);
    this.clearLoginWatchdog();
  }

  private clearLoginWatchdog(): void {
    if (this.loginWatchdog) {
      clearTimeout(this.loginWatchdog);
      this.loginWatchdog = null;
    }
  }
}
