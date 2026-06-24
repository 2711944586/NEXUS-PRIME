import { CommonModule, DOCUMENT } from '@angular/common';
import { AfterViewInit, Component, ElementRef, inject, OnDestroy, ViewChild } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';

import { entryVideoSource, LANDING_POSTER } from '../core/landing-visuals';
import { ThemeService } from '../core/theme.service';

@Component({
  standalone: true,
  imports: [CommonModule, RouterLink, ButtonModule],
  template: `
    <main id="main-content" class="entry-screen nexus-motion-entry">
      <div class="motion-video-stage" aria-hidden="true">
        <video
          #entryVideo
          class="motion-video-bg"
          autoplay
          muted
          loop
          playsinline
          preload="auto"
          [poster]="poster"
          [src]="entryVideoSource()"
          (canplay)="playBackgroundVideo($event)"
          (loadeddata)="playBackgroundVideo($event)"
        >
        </video>
        <div class="motion-video-aurora"></div>
        <div class="motion-data-scan"></div>
        <div class="motion-video-wash"></div>
        <div class="motion-grid-field"></div>
      </div>

      <header class="motion-nav" aria-label="首页导航">
        <a class="motion-brand" routerLink="/" aria-label="NEXUS Prime 首页">
          <span>NX</span>
          <strong>NEXUS Prime</strong>
        </a>
        <nav class="motion-links" aria-label="入场操作">
          <a href="#entry-hero" (click)="scrollToAnchor($event, 'entry-hero')">Entry</a>
          <a href="#entry-flow" (click)="scrollToAnchor($event, 'entry-flow')">Flow</a>
          <a href="#entry-signals" (click)="scrollToAnchor($event, 'entry-signals')">Audit</a>
          <a routerLink="/auth/login" class="motion-login">
            <i class="pi pi-sign-in"></i>
            登录
          </a>
          <button
            type="button"
            class="motion-theme-toggle"
            (click)="toggleTheme()"
            [attr.aria-label]="theme.mode() === 'dark-cockpit' ? '切换到亮色主题' : '切换到暗色主题'"
          >
            <i class="pi" [ngClass]="theme.mode() === 'dark-cockpit' ? 'pi-sun' : 'pi-moon'"></i>
            <span>{{ theme.mode() === 'dark-cockpit' ? 'Light' : 'Dark' }}</span>
          </button>
        </nav>
      </header>

      <section class="motion-hero" id="entry-hero" aria-label="NEXUS Prime 入场页">
        <div class="motion-hero-copy">
          <div class="motion-kicker">
            <span>ERP Operating System</span>
            <i></i>
            <span>Manufacturing command layer</span>
          </div>

          <h1 class="motion-title" aria-label="NEXUS Prime">
            <span>NEXUS</span>
            <em>Prime</em>
          </h1>

          <p class="motion-lede">
            给制造企业使用的经营工作台。现场收货、库存预警、采购审批、销售履约、应收回款和审计记录，在同一套权限体系里流转。
          </p>

          <div class="motion-actions">
            <a pButton routerLink="/auth/login" class="motion-primary" aria-label="进入登录页面">
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
        </div>

        <aside class="motion-command-slab" id="entry-flow" aria-label="入场页系统状态">
          <div class="slab-head">
            <span>06:40</span>
            <strong>早班经营快照</strong>
            <em><i></i>Live</em>
          </div>

          <div class="slab-score">
            <span>经营健康度</span>
            <strong>92</strong>
            <em>库存、采购和履约链路可执行</em>
          </div>

          <div class="slab-proof" aria-label="系统摘要">
            @for (proof of proofs; track proof.label) {
              <span>
                <strong>{{ proof.value }}</strong>
                <em>{{ proof.label }}</em>
              </span>
            }
          </div>

          <div class="slab-flow" aria-label="经营流程">
            @for (node of flowNodes; track node.code) {
              <span [class.hot]="node.hot">
                <em>{{ node.code }}</em>
                <strong>{{ node.label }}</strong>
              </span>
            }
          </div>
        </aside>

        <div class="motion-scroll" aria-hidden="true">
          <span>Scroll</span>
          <i></i>
        </div>
      </section>

      <section class="motion-operations" id="entry-floor" aria-label="真实业务现场">
        <header class="motion-section-head">
          <span>Selected operations</span>
          <h2>真实业务现场</h2>
          <p>把制造、仓配、控制台和质检场景接入同一套 ERP 工作流。</p>
        </header>

        <div class="motion-runway">
          @for (photo of photos; track photo.src) {
            <figure [class.featured]="photo.featured">
              <img [src]="photo.src" [alt]="photo.alt" />
              <figcaption>
                <span>{{ photo.kicker }}</span>
                <strong>{{ photo.title }}</strong>
              </figcaption>
            </figure>
          }
        </div>
      </section>

      <section class="motion-system" id="entry-signals" aria-label="准入与部署提示">
        <div class="motion-system-title">
          <span>System notes</span>
          <h2>准入审计与<br />部署边界</h2>
        </div>

        <div class="motion-signal-stack">
          @for (signal of signals; track signal.title) {
            <article>
              <span>{{ signal.kicker }}</span>
              <strong>{{ signal.title }}</strong>
              <p>{{ signal.body }}</p>
            </article>
          }
        </div>

        <div class="motion-process-strip" aria-label="关键流程">
          @for (step of flowSteps; track step.title) {
            <article>
              <i [class]="step.icon"></i>
              <span>
                <strong>{{ step.title }}</strong>
                <em>{{ step.body }}</em>
              </span>
            </article>
          }
        </div>
      </section>
    </main>
  `
})
export class EntryPage implements AfterViewInit, OnDestroy {
  @ViewChild('entryVideo') private readonly entryVideo?: ElementRef<HTMLVideoElement>;
  private readonly document = inject(DOCUMENT);
  private readonly handleHashChange = () => {
    this.document.defaultView?.setTimeout(() => this.syncHashScroll(), 80);
  };
  protected readonly theme = inject(ThemeService);
  protected readonly poster = LANDING_POSTER;

  protected readonly flowSteps = [
    { title: '经营总览', body: '指标、任务与风险进入同一屏', icon: 'pi pi-chart-line' },
    { title: '流程协作', body: '采购、销售、库存形成闭环', icon: 'pi pi-sitemap' },
    { title: '权限审计', body: '角色边界与操作记录可追踪', icon: 'pi pi-shield' }
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
      src: '/images/automated-production-line-wide.jpg',
      alt: '制造车间产线现场',
      kicker: 'Plant floor',
      title: '现场任务进入经营链路',
      featured: true
    },
    {
      src: '/images/warehouse-operator-aisle-wide.jpg',
      alt: '仓库团队在货架区协同作业',
      kicker: 'Warehouse',
      title: '仓储与移动扫码协同',
      featured: false
    },
    {
      src: '/images/control-panel-wide.jpg',
      alt: '控制台屏幕展示经营指标',
      kicker: 'Control room',
      title: '管理层查看实时指标',
      featured: false
    },
    {
      src: '/images/factory-quality-control-wide.jpg',
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

  ngAfterViewInit(): void {
    void this.theme.mode();
    queueMicrotask(() => this.playBackgroundVideo());
    this.document.defaultView?.addEventListener('hashchange', this.handleHashChange);
    this.document.defaultView?.setTimeout(() => this.syncHashScroll(), 120);
  }

  ngOnDestroy(): void {
    this.document.defaultView?.removeEventListener('hashchange', this.handleHashChange);
  }

  protected scrollToAnchor(event: Event, id: string): void {
    event.preventDefault();
    this.scrollToTarget(id, true);
  }

  protected toggleTheme(): void {
    this.theme.toggle(false);
    queueMicrotask(() => this.playBackgroundVideo());
  }

  protected entryVideoSource(): string {
    return entryVideoSource(this.theme.mode());
  }

  protected playBackgroundVideo(event?: Event): void {
    const video = (event?.target as HTMLVideoElement | null) ?? this.entryVideo?.nativeElement;
    if (!video) {
      return;
    }

    video.muted = true;
    void video.play().catch(() => {
      // Browsers can still decline autoplay; the poster and local fallback remain visible.
    });
  }

  private syncHashScroll(): void {
    const hash = this.document.defaultView?.location.hash.slice(1);
    if (hash === 'entry-hero' || hash === 'entry-flow' || hash === 'entry-signals') {
      this.scrollToTarget(hash, false);
    }
  }

  private scrollToTarget(id: string, updateHash: boolean): void {
    const win = this.document.defaultView;
    const target = this.document.getElementById(id);
    if (!win || !target) {
      return;
    }

    const reduceMotion = win.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (updateHash) {
      win.history.pushState(null, '', `${win.location.pathname}${win.location.search}#${id}`);
    }

    if (id === 'entry-hero') {
      win.scrollTo({
        top: 0,
        behavior: reduceMotion ? 'auto' : 'smooth'
      });
      win.setTimeout(() => win.scrollTo({ top: 0, behavior: 'auto' }), reduceMotion ? 0 : 420);
      return;
    }

    const navBottom = this.document.querySelector('.motion-nav')?.getBoundingClientRect().bottom ?? 0;
    const desktopOffset = id === 'entry-flow' ? 140 : 124;
    const mobileOffset = id === 'entry-flow' ? 102 : 92;
    const baseOffset = win.innerWidth <= 720 ? mobileOffset : desktopOffset;
    const offset = Math.max(navBottom + 24, baseOffset);
    const top = Math.max(0, target.getBoundingClientRect().top + win.scrollY - offset);

    win.scrollTo({
      top,
      behavior: reduceMotion ? 'auto' : 'smooth'
    });
  }
}
