import { CommonModule } from '@angular/common';
import { AfterViewInit, Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, NavigationEnd, Router, RouterLink } from '@angular/router';
import { catchError, filter, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { ThemeService } from '../core/theme.service';

interface RegisterPolicy {
  terms_version: string;
  permissions: string[];
  required_acceptances: string[];
  documents?: RegisterPolicyDocument[];
}

interface RegisterPolicyDocument {
  id: string;
  title: string;
  summary: string;
  items: string[];
}

@Component({
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <main class="policy-screen nexus-login-redesign">
      <header class="policy-topbar">
        <a class="entry-brand-inline" routerLink="/" aria-label="NEXUS Prime 首页">
          <span class="brand-mark">NX</span>
          <span>
            <strong>NEXUS Prime</strong>
            <em>Account policy</em>
          </span>
        </a>
        <nav aria-label="许可页操作">
          <a routerLink="/auth/login" [queryParams]="{ mode: 'register' }">返回注册</a>
          <button type="button" (click)="theme.toggle(false)" aria-label="切换主题">
            <i class="pi" [ngClass]="theme.mode() === 'dark-cockpit' ? 'pi-moon' : 'pi-sun'"></i>
          </button>
        </nav>
      </header>

      <section class="policy-hero" aria-label="注册许可">
        <div class="policy-hero-copy">
          <span>Register policy</span>
          <h1 aria-label="注册许可">
            <span>注册</span>
            <span>许可</span>
          </h1>
          <p>普通成员账号适用于制造台账、采购、销售、文件、报表与协同流程。注册前请确认账号边界、隐私资料和业务数据范围。</p>
          <div class="policy-actions">
            <strong>版本 {{ policy()?.terms_version || '2026.06' }}</strong>
            <a routerLink="/auth/login" [queryParams]="{ mode: 'register' }">创建账号</a>
          </div>
        </div>
        <figure class="policy-photo-card">
          <img src="/images/contracts-desk-wide.jpg" alt="业务合同与注册许可资料桌面" />
          <figcaption>
            <span>Policy desk</span>
            <strong>许可与审计资料</strong>
          </figcaption>
        </figure>
      </section>

      <section class="policy-layout" aria-label="许可条款正文">
        <aside class="policy-index">
          @for (document of registerPolicyDocuments(); track document.id) {
            <button type="button" (click)="scrollToDocument(document.id)" [class.active]="activeDocument() === document.id">
              <span>{{ document.id === 'terms' ? '01' : document.id === 'privacy' ? '02' : '03' }}</span>
              <strong>{{ document.title }}</strong>
            </button>
          }
        </aside>

        <div class="policy-documents">
          @for (document of registerPolicyDocuments(); track document.id) {
            <article [id]="document.id" class="policy-document">
              <header>
                <span>{{ document.id === 'terms' ? '01' : document.id === 'privacy' ? '02' : '03' }}</span>
                <h2>{{ document.title }}</h2>
                <p>{{ document.summary }}</p>
              </header>
              <ul>
                @for (item of document.items; track $index) {
                  <li>{{ item }}</li>
                }
              </ul>
            </article>
          }
        </div>
      </section>
    </main>
  `
})
export class RegisterPolicyPage implements OnInit, AfterViewInit {
  protected readonly theme = inject(ThemeService);
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  protected readonly policy = signal<RegisterPolicy | null>(null);
  protected readonly activeDocument = signal<'terms' | 'privacy' | 'data_scope'>('terms');
  private hasDocumentFragment = false;

  ngOnInit(): void {
    this.api.get<RegisterPolicy>('auth/register-policy').pipe(
      catchError(() => of(null))
    ).subscribe(result => {
      if (result) {
        this.policy.set(result);
        this.queueInitialScroll();
      }
    });
    this.route.fragment.subscribe(fragment => {
      const target = this.validDocumentId(fragment);
      this.hasDocumentFragment = Boolean(target);
      this.activeDocument.set(target ?? 'terms');
      this.queueInitialScroll();
    });
    this.router.events.pipe(filter(event => event instanceof NavigationEnd)).subscribe(() => {
      this.queueInitialScroll();
    });
  }

  ngAfterViewInit(): void {
    this.queueInitialScroll();
  }

  scrollToDocument(id: string, updateUrl = true): void {
    const target = this.validDocumentId(id) ?? 'terms';
    this.activeDocument.set(target);
    if (updateUrl) {
      this.hasDocumentFragment = true;
      this.router.navigate([], { fragment: target, replaceUrl: false });
    }
    this.performPolicyScroll(target, updateUrl ? 'smooth' : 'auto');
  }

  registerPolicyDocuments(): RegisterPolicyDocument[] {
    return this.policy()?.documents?.length ? this.policy()!.documents! : [
      {
        id: 'terms',
        title: 'NEXUS Prime 服务许可',
        summary: '普通成员准入、业务动作、文件上传、审计责任和管理员授权规则。',
        items: [
          '注册成功后系统创建普通成员账号，不自动授予用户管理、审计删除、全局权限配置、部署设置等高风险能力。',
          '账号仅用于 NEXUS Prime 内的制造台账、采购审批、销售履约、财务应收、报表分析、文件归档和协同演示业务。',
          '用户应使用真实邮箱、姓名或岗位昵称、所属部门和业务岗位；管理员可根据岗位补充分组、角色和业务权限。',
          '用户名需为 3-32 位字母、数字、点、下划线或短横线；密码至少 8 位，并同时包含字母和数字。',
          '禁止上传恶意脚本、伪装可执行文件、含敏感凭据的配置文件或与业务无关的大文件；文件中心会记录上传人、时间和类型。',
          '采购审批、盘点调整、信用冻结、文件删除等关键动作会进入审计日志，便于课程演示、部署检查和责任追踪。'
        ]
      },
      {
        id: 'privacy',
        title: '隐私与身份资料说明',
        summary: '账号资料、通知、头像、偏好设置、审计归属和前端安全边界说明。',
        items: [
          '注册资料包括邮箱、用户名、姓名或岗位昵称、手机号、部门、岗位和界面偏好设置。',
          '这些资料用于登录识别、通知送达、头像展示、业务负责人展示和审计日志归属。',
          '头像文件存放在专用头像目录或生产持久化存储，不与采购合同、质检附件、报表文件等业务附件混放。',
          '系统不会在浏览器端保存数据库连接串、部署 Token、Supabase secret、Cloudinary secret 或 AI API Key。',
          '管理员可以查看业务审计与账号状态，但普通成员无法访问用户管理、角色配置和全局安全配置。',
          '生产部署时应通过 HTTPS、SameSite Cookie、CSRF Token 和环境变量隔离保护登录会话。'
        ]
      },
      {
        id: 'data_scope',
        title: '数据使用范围',
        summary: '库存、采购、履约、应收、文件、报表和 AI 经营分析的数据边界。',
        items: [
          '系统会把注册账号与后续上传、评论、报表生成、AI 会话、业务写入和审批动作建立关联。',
          '库存、采购、销售、履约、应收、信用、盘点、质检和维护数据仅用于系统内业务流转、演示分析和审计追踪。',
          'AI 分析只通过后端读取经营汇总和用户输入；外部模型调用由服务端统一转发，并可降级为本地分析。',
          '文件附件存放在专用文件目录或生产持久化存储；Seed 图片和演示素材位于前端公共资源。',
          '生产部署应使用 Supabase PostgreSQL、Vercel 环境变量和 Cloudinary 或等价对象存储承载持久文件。',
          '管理员可按岗位分配采购、销售、文件、报表、AI、系统审计等权限，普通成员只能访问被授权的业务范围。'
        ]
      }
    ];
  }

  private validDocumentId(id: string | null | undefined): 'terms' | 'privacy' | 'data_scope' | null {
    return id === 'terms' || id === 'privacy' || id === 'data_scope' ? id : null;
  }

  private queueInitialScroll(): void {
    if (this.hasDocumentFragment) {
      this.queuePolicyScroll(this.activeDocument());
      return;
    }
    this.queuePageTop();
  }

  private queuePageTop(): void {
    [0, 80, 240, 520].forEach(delay => {
      setTimeout(() => window.scrollTo({ top: 0, behavior: 'auto' }), delay);
    });
  }

  private queuePolicyScroll(id: 'terms' | 'privacy' | 'data_scope'): void {
    [0, 80, 240, 520].forEach(delay => {
      setTimeout(() => this.performPolicyScroll(id, 'auto'), delay);
    });
  }

  private performPolicyScroll(id: 'terms' | 'privacy' | 'data_scope', behavior: ScrollBehavior): void {
    const target = document.getElementById(id);
    if (!target) {
      return;
    }
    const offset = Math.min(112, Math.max(84, window.innerHeight * 0.12));
    const top = target.getBoundingClientRect().top + window.scrollY - offset;
    window.scrollTo({ top: Math.max(0, top), behavior });
  }
}
