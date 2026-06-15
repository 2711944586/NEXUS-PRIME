import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, of } from 'rxjs';

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
          <h1>注册许可</h1>
          <p>普通成员账号适用于制造台账、采购、销售、文件、报表与协同流程。</p>
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
            <a [attr.href]="'#' + document.id">
              <span>{{ document.id === 'terms' ? '01' : document.id === 'privacy' ? '02' : '03' }}</span>
              <strong>{{ document.title }}</strong>
            </a>
          }
        </aside>

        <div class="policy-documents">
          @for (document of registerPolicyDocuments(); track document.id) {
            <article [id]="document.id" class="policy-document">
              <span>{{ document.id === 'terms' ? '01' : document.id === 'privacy' ? '02' : '03' }}</span>
              <h2>{{ document.title }}</h2>
              <p>{{ document.summary }}</p>
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
export class RegisterPolicyPage implements OnInit {
  protected readonly theme = inject(ThemeService);
  private readonly api = inject(ApiService);
  protected readonly policy = signal<RegisterPolicy | null>(null);

  ngOnInit(): void {
    this.api.get<RegisterPolicy>('auth/register-policy').pipe(
      catchError(() => of(null))
    ).subscribe(result => {
      if (result) {
        this.policy.set(result);
      }
    });
  }

  registerPolicyDocuments(): RegisterPolicyDocument[] {
    return this.policy()?.documents?.length ? this.policy()!.documents! : [
      {
        id: 'terms',
        title: 'NEXUS Prime 服务许可',
        summary: '普通成员准入、业务动作和文件上传规则。',
        items: [
          '普通账号默认进入成员角色，无法访问用户管理、审计删除和全局权限配置。',
          '账号仅用于本系统制造台账、采购、销售、财务与分析演示业务。',
          '管理员可按岗位分配采购、销售、文件、报表等权限。'
        ]
      },
      {
        id: 'privacy',
        title: '隐私与身份资料说明',
        summary: '账号资料、头像、通知和审计归属说明。',
        items: [
          '注册资料用于登录、通知、头像展示和业务审计归属。',
          '头像与附件分目录存储，生产环境使用持久化对象存储。',
          '部署 Token、数据库连接串和外部 AI Key 不会保存在浏览器端。'
        ]
      },
      {
        id: 'data_scope',
        title: '数据使用范围',
        summary: '库存、采购、履约、应收、报表和 AI 分析闭环。',
        items: [
          '系统会把账号与上传、评论、报表、AI 会话和业务写入建立关联。',
          'AI 分析由后端读取经营摘要并统一调用外部或本地分析引擎。',
          '管理员可按岗位分配采购、销售、文件、报表等权限。'
        ]
      }
    ];
  }
}
