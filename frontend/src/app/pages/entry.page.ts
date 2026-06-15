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
          <a href="#entry-floor" class="entry-nav-anchor">现场</a>
          <a href="#entry-system" class="entry-nav-anchor">体系</a>
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
          <span class="entry-kicker">Manufacturing command entry</span>
          <h1>NEXUS Prime</h1>
          <p>给制造企业使用的经营工作台。现场收货、库存预警、采购审批、销售履约、应收回款和审计记录，在同一套权限体系里流转。</p>

          <div class="entry-actions">
            <a pButton routerLink="/auth/login" class="entry-primary-action" aria-label="进入登录页面">
              <span>进入系统</span>
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
          <div class="entry-command-head">
            <span>Shift board</span>
            <strong>06:40 早班经营快照</strong>
          </div>

          <div class="entry-command-score" aria-label="经营健康度">
            <span>经营健康度</span>
            <strong>92</strong>
            <em>库存、采购和履约链路可执行</em>
          </div>

          <div class="entry-ops-summary">
            <span>今日主链路</span>
            <strong>收货入库、销售发运和回款提醒已经同步到工作台</strong>
          </div>

          <div class="entry-flow-map" aria-label="经营流程">
            @for (node of flowNodes; track node.code) {
              <span [class.hot]="node.hot">
                <em>{{ node.code }}</em>
                <strong>{{ node.label }}</strong>
              </span>
            }
          </div>

          <div class="entry-process-lines" id="entry-system" aria-label="关键流程">
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

      <section class="entry-photo-runway" id="entry-floor" aria-label="真实业务现场">
        @for (photo of photos; track photo.src) {
          <figure [class.featured]="photo.featured">
            <img [src]="photo.src" [alt]="photo.alt" />
            <figcaption>
              <span>{{ photo.kicker }}</span>
              <strong>{{ photo.title }}</strong>
            </figcaption>
          </figure>
        }
      </section>

      <section class="entry-signal-band" aria-label="准入与部署提示">
        @for (signal of signals; track signal.title) {
          <article>
            <span>{{ signal.kicker }}</span>
            <strong>{{ signal.title }}</strong>
            <p>{{ signal.body }}</p>
          </article>
        }
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
  protected readonly flowNodes = [
    { code: '01', label: '收货', hot: false },
    { code: '02', label: '库存', hot: true },
    { code: '03', label: '采购', hot: false },
    { code: '04', label: '履约', hot: true },
    { code: '05', label: '回款', hot: false }
  ];
  protected readonly photos = [
    {
      src: '/images/plant-floor-wide.jpg',
      alt: '制造车间产线现场',
      kicker: 'Plant floor',
      title: '现场任务进入经营链路',
      featured: true
    },
    {
      src: '/images/warehouse-team-wide.jpg',
      alt: '仓库团队在货架区协同作业',
      kicker: 'Warehouse',
      title: '仓储与移动扫码协同',
      featured: false
    },
    {
      src: '/images/control-dashboard-wide.jpg',
      alt: '控制台屏幕展示经营指标',
      kicker: 'Control room',
      title: '管理层查看实时指标',
      featured: false
    },
    {
      src: '/images/quality-inspection-wide.jpg',
      alt: '质检人员检查制造物料',
      kicker: 'Quality',
      title: '质检、文件和审计留痕',
      featured: false
    }
  ];
  protected readonly signals = [
    {
      kicker: 'Access',
      title: '普通成员从注册开始进入权限体系',
      body: '注册只创建成员账号，管理员后续按岗位分配采购、销售、文件、报表等能力。'
    },
    {
      kicker: 'Audit',
      title: '关键动作有账号、时间和业务记录',
      body: '登录、注册、审批、上传和删除动作都会落入审计链路，便于部署前检查。'
    },
    {
      kicker: 'Deploy',
      title: '前端、后端和存储边界清晰',
      body: '入口页只暴露登录与注册，业务数据通过后端 API 与会话 Cookie 访问。'
    }
  ];
}
