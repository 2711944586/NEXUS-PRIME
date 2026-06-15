import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';

import { ThemeService } from '../core/theme.service';

@Component({
  standalone: true,
  imports: [CommonModule, RouterLink, ButtonModule],
  template: `
    <main class="entry-screen nexus-entry-redesign">
      <header class="entry-topline" aria-label="首页导航">
        <a class="entry-brand-inline" routerLink="/" aria-label="NEXUS Prime 首页">
          <span class="brand-mark">NX</span>
          <span>
            <strong>NEXUS Prime</strong>
            <em>Manufacturing Operating System</em>
          </span>
        </a>
        <nav class="entry-top-actions" aria-label="入场操作">
          <span class="entry-live-chip"><i class="pi pi-circle-fill"></i> 经营在线</span>
          <a pButton [text]="true" routerLink="/auth/login" class="entry-nav-login">
            <i class="pi pi-sign-in"></i>
            登录
          </a>
          <button pButton type="button" class="entry-theme-toggle" [text]="true" [rounded]="true" (click)="theme.toggle(false)" aria-label="切换主题">
            <i class="pi" [ngClass]="theme.mode() === 'dark-cockpit' ? 'pi-moon' : 'pi-sun'"></i>
          </button>
        </nav>
      </header>

      <section class="entry-hero" aria-label="NEXUS Prime 入场页">
        <div class="entry-story">
          <span class="entry-kicker">Manufacturing Operations</span>
          <h1>NEXUS Prime</h1>
          <p>一套面向制造现场的经营工作台，把库存、采购、履约、应收、文件和审计放进同一条清晰链路。</p>

          <div class="entry-actions">
            <a pButton routerLink="/auth/login" class="entry-primary-action" aria-label="进入登录页面">
              <span>进入登录</span>
              <i class="pi pi-arrow-right"></i>
            </a>
            <a pButton severity="secondary" [outlined]="true" routerLink="/auth/login" [queryParams]="{ mode: 'register' }" aria-label="创建普通成员账号">
              <i class="pi pi-user-plus"></i>
              创建账号
            </a>
            <a pButton severity="secondary" [text]="true" routerLink="/app/overview" aria-label="进入工作台">
              <i class="pi pi-desktop"></i>
              已有会话
            </a>
          </div>

          <div class="entry-proof-strip" aria-label="系统摘要">
            @for (proof of proofs; track proof.label) {
              <span>
                <strong>{{ proof.value }}</strong>
                <em>{{ proof.label }}</em>
              </span>
            }
          </div>
        </div>

        <aside class="entry-operations-card entry-minimal-panel" aria-label="入场页系统状态">
          <div class="entry-photo-mosaic" aria-hidden="true">
            <img class="primary" src="/images/manufacturing-wide.jpg" alt="" />
            <img src="/images/operations-team-wide.jpg" alt="" />
            <img src="/images/finance-dashboard-wide.jpg" alt="" />
          </div>

          <div class="entry-ops-summary">
            <span>今日经营链路</span>
            <strong>从现场到财务的闭环已同步</strong>
          </div>

          <div class="entry-process-lines" aria-label="关键流程">
            @for (step of flowSteps; track step.title) {
              <a [routerLink]="step.path">
                <i [class]="step.icon"></i>
                <span>
                  <strong>{{ step.title }}</strong>
                  <em>{{ step.body }}</em>
                </span>
              </a>
            }
          </div>

          <div class="entry-panel-foot">
            <span>权限入口</span>
            <i></i>
            <span>经营在线</span>
          </div>
        </aside>
      </section>
    </main>
  `
})
export class EntryPage {
  protected readonly theme = inject(ThemeService);
  protected readonly flowSteps = [
    { title: '经营总览', body: '指标、任务与风险进入同一屏', path: '/app/overview', icon: 'pi pi-chart-line' },
    { title: '流程协作', body: '采购、销售、库存形成闭环', path: '/app/tasks', icon: 'pi pi-sitemap' },
    { title: '权限审计', body: '角色边界与操作记录可追踪', path: '/app/system/audit', icon: 'pi pi-shield' }
  ];
  protected readonly proofs = [
    { label: '业务模块', value: '18' },
    { label: '流程节点', value: '42' },
    { label: '审计动作', value: '实时' }
  ];
}
