import { CommonModule, DOCUMENT } from '@angular/common';
import { Component, DestroyRef, HostListener, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { NavigationEnd, NavigationStart, Router, RouterOutlet } from '@angular/router';
import { MessageService } from 'primeng/api';
import { catchError, debounceTime, distinctUntilChanged, filter, interval, of, startWith, Subject, switchMap } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DockGroup, DockItem, ServiceHealth } from '../core/models';
import {
  ALL_DOCK_ITEMS,
  groupedDockItems,
  navigationStateForUrl
} from '../core/navigation';
import { resourceConfigForUrl } from '../core/resource-workflow';
import { ThemeService } from '../core/theme.service';
import { AppDockComponent } from './app-dock.component';
import { AppTopbarComponent, QuickCreateAction } from './app-topbar.component';
import { ResourceWorkbenchComponent } from './resource-workbench.component';
import { SceneBackgroundComponent } from '../motion';
import {
  EMPTY_SERVICE_HEALTH,
  normalizeServiceHealth,
  serviceHealthLabel,
  serviceHealthLatencyLabel,
  serviceHealthTooltip,
  userInitials
} from './app-shell.models';

const QUICK_CREATE_ACTIONS: QuickCreateAction[] = [
  { label: '补货建议', description: '从低库存对象进入补货队列', path: '/app/inventory/replenishment', icon: 'warehouse', accent: '#0f766e' },
  { label: '采购单', description: '创建采购并推进审批收货', path: '/app/procurement/orders', icon: 'shopping-cart', accent: '#b7791f' },
  { label: '销售订单', description: '进入履约、发货和应收链路', path: '/app/sales/orders', icon: 'send', accent: '#2563eb' },
  { label: '收款记录', description: '处理应收、催款和信用释放', path: '/app/finance/receivables', icon: 'money', accent: '#be123c' },
  { label: '经营报表', description: '生成多维经营报表并归档', path: '/app/reports', icon: 'chart', accent: '#7c3aed' }
];

const COMMAND_SUGGESTIONS = [
  { type: '业务动作', label: '处理低库存', description: '进入补货建议并生成采购草稿', path: '/app/inventory/replenishment' },
  { type: '业务动作', label: '审批采购', description: '查看待审批采购和收货进度', path: '/app/procurement/orders' },
  { type: '业务动作', label: '推进销售发货', description: '处理履约队列、库存锁定和出库', path: '/app/sales/orders' },
  { type: '业务动作', label: '记录收款', description: '进入应收风控并释放信用占用', path: '/app/finance/receivables' },
  { type: '分析', label: '经营分析台', description: '汇总库存、采购、履约和应收风险', path: '/app/ai' },
  { type: '报表', label: '报表工作室', description: '生成经营日报并归档文件中心', path: '/app/reports' }
];

@Component({
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterOutlet,
    AppDockComponent,
    AppTopbarComponent,
    ResourceWorkbenchComponent,
    SceneBackgroundComponent
  ],
  template: `
    <div class="atlas-shell" [class.route-overview]="isOverviewRoute()">
      <nexus-scene-background image="images/automated-production-line-wide.jpg" mode="default"></nexus-scene-background>
      <a class="skip-main-link" href="#main-content">跳到主内容</a>
      @if (routeLoading()) {
        <div class="route-loading-bar" aria-hidden="true"></div>
      }
      <app-topbar
        [navigation]="navigationState()"
        [searchQuery]="searchQuery"
        [searchResults]="searchResults()"
        [quickCreateActions]="quickCreateActions"
        [createOpen]="createOpen"
        [serviceHealth]="serviceHealth()"
        [serviceHealthLabel]="serviceHealthLabel()"
        [serviceHealthLatencyLabel]="serviceHealthLatencyLabel()"
        [serviceHealthTooltip]="serviceHealthTooltip()"
        [todayText]="todayText"
        [notificationCount]="unreadNotificationCount()"
        [brokenAvatarUrl]="brokenAvatarUrl()"
        [initials]="initials"
        (searchFocus)="showSearchSuggestions()"
        (searchQueryChange)="onSearchInput($event)"
        (searchSubmit)="runSearch()"
        (searchClear)="clearSearch()"
        (quickCreateToggle)="toggleQuickCreate($event)"
        (quickCreateClose)="closeQuickCreate()"
        (refresh)="refreshShell()"
        (avatarBroken)="markAvatarBroken($event)"
      />

      <div class="atlas-workbench">
        <app-dock
          [navigation]="navigationState()"
          [groups]="visibleDockGroups()"
          [itemIsActive]="itemIsActive"
          [groupIsActive]="groupIsActive"
        />

        <main class="content-stage atlas-stage" id="main-content">
          <section class="route-page-host" aria-label="当前业务页面">
            <router-outlet />
          </section>
          @if (showResourceWorkbench()) {
            <app-resource-workbench />
          }
        </main>
      </div>
    </div>
  `
})
export class AppShellComponent implements OnInit, OnDestroy {
  protected readonly theme = inject(ThemeService);
  private readonly api = inject(ApiService);
  private readonly document = inject(DOCUMENT);
  private readonly router = inject(Router);
  private readonly messages = inject(MessageService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly currentUrl = signal(this.router.url || '/app/overview');
  protected createOpen = false;
  protected searchQuery = '';
  protected readonly searchResults = signal<Array<{ type: string; label: string; description?: string; path: string }>>([]);
  protected readonly quickCreateActions = QUICK_CREATE_ACTIONS;
  protected readonly unreadNotificationCount = signal(0);
  protected readonly routeLoading = signal(false);
  private readonly searchInput$ = new Subject<string>();
  protected readonly serviceHealth = signal<ServiceHealth>(EMPTY_SERVICE_HEALTH);
  protected readonly navigationState = computed(() => navigationStateForUrl(this.currentUrl()));
  protected readonly isOverviewRoute = computed(() => this.currentUrl().startsWith('/app/overview'));
  protected readonly showResourceWorkbench = computed(() => Boolean(resourceConfigForUrl(this.currentUrl())));
  protected readonly brokenAvatarUrl = signal('');
  protected readonly visibleDockGroups = computed<DockGroup[]>(() => groupedDockItems(ALL_DOCK_ITEMS));
  private serviceHealthLoadedAt = 0;
  private serviceHealthLoading = false;
  private spotlightFrame = 0;
  private spotlightTarget: HTMLElement | null = null;
  private spotlightPoint: { x: number; y: number } | null = null;
  protected readonly serviceHealthLabel = computed(() => serviceHealthLabel(this.serviceHealth()));
  protected readonly serviceHealthLatencyLabel = computed(() => serviceHealthLatencyLabel(this.serviceHealth()));
  protected readonly serviceHealthTooltip = computed(() => serviceHealthTooltip(this.serviceHealth()));
  protected readonly todayText = new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date());

  ngOnInit(): void {
    this.document.documentElement.classList.add('nexus-app-shell-active');
    this.theme.hydrateFromServer();
    this.loadServiceHealth();
    interval(60_000).pipe(
      startWith(0),
      switchMap(() => this.api.get<{ unread: number }>('notifications/unread-count', {}, { silent: true }).pipe(catchError(() => of({ unread: 0 })))),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe(r => this.unreadNotificationCount.set(r.unread));
    this.searchInput$.pipe(
      debounceTime(300),
      distinctUntilChanged(),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe(q => { if (q.trim().length >= 2) this.runSearch(); else this.showSearchSuggestions(); });
    this.router.events.pipe(
      filter(e => e instanceof NavigationStart || e instanceof NavigationEnd),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe(e => this.routeLoading.set(e instanceof NavigationStart));
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe(event => {
      this.createOpen = false;
      this.clearSearch();
      this.currentUrl.set((event as NavigationEnd).urlAfterRedirects);
      this.loadServiceHealth();
      this.scrollMainToTop();
    });
    if (typeof window !== 'undefined') {
      window.addEventListener('pointermove', this.onPointerMove, { passive: true });
      window.addEventListener('pointerleave', this.clearSpotlight);
    }
  }

  ngOnDestroy(): void {
    this.document.documentElement.classList.remove('nexus-app-shell-active');
    if (typeof window !== 'undefined') {
      window.removeEventListener('pointermove', this.onPointerMove);
      window.removeEventListener('pointerleave', this.clearSpotlight);
      if (this.spotlightFrame) {
        window.cancelAnimationFrame(this.spotlightFrame);
        this.spotlightFrame = 0;
      }
    }
    this.clearSpotlight();
  }

  @HostListener('document:keydown.escape')
  protected closeTransientPanels(): void {
    this.createOpen = false;
    this.clearSearch();
  }

  @HostListener('document:click', ['$event'])
  protected closeTransientPanelsFromOutside(event: MouseEvent): void {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) {
      return;
    }
    const insideCreateSurface = Boolean(target.closest('.create-action, .quick-create-popover'));
    const insideSearchSurface = Boolean(target.closest('.atlas-search, .atlas-search-popover'));
    if (!insideCreateSurface) {
      this.createOpen = false;
    }
    if (!insideSearchSurface) {
      this.clearSearch();
    }
  }

  toggleQuickCreate(event?: Event): void {
    event?.stopPropagation();
    this.createOpen = !this.createOpen;
    if (this.createOpen) {
      this.focusAfterRender('.quick-create-popover a');
    }
  }

  closeQuickCreate(): void {
    this.createOpen = false;
  }

  runSearch(): void {
    const q = this.searchQuery.trim();
    if (q.length < 2) {
      this.showSearchSuggestions();
      return;
    }
    this.api.get<{ items: Array<{ type: string; label: string; description?: string; path: string }> }>('search', { q }, { silent: true }).subscribe({
      next: result => {
        this.searchResults.set(result.items.slice(0, 8));
      },
      error: () => {
        this.searchResults.set([]);
      }
    });
  }

  clearSearch(): void {
    this.searchQuery = '';
    this.searchResults.set([]);
  }

  onSearchInput(value: string): void {
    this.searchQuery = value;
    this.searchInput$.next(value);
  }

  showSearchSuggestions(): void {
    if (!this.searchQuery.trim()) {
      this.searchResults.set(COMMAND_SUGGESTIONS);
    }
  }

  refreshShell(): void {
    this.loadServiceHealth(true);
    this.messages.add({ severity: 'success', summary: '服务状态已同步', detail: '顶部服务状态和业务入口已刷新。' });
  }

  initials(user: { full_name?: string | null; username?: string | null; email?: string | null }): string {
    return userInitials(user);
  }

  markAvatarBroken(url: string | null | undefined): void {
    if (url) {
      this.brokenAvatarUrl.set(url);
    }
  }

  protected readonly itemIsActive = (item: DockItem): boolean => {
    return item.key === this.navigationState().activeItem.key;
  };

  protected readonly groupIsActive = (group: DockGroup): boolean => {
    return group.key === this.navigationState().activeGroup.key;
  };

  private focusAfterRender(selector: string): void {
    if (typeof window === 'undefined') {
      return;
    }
    window.setTimeout(() => {
      const target = document.querySelector<HTMLElement>(selector);
      target?.focus({ preventScroll: true });
    });
  }

  private loadServiceHealth(force = false): void {
    const now = Date.now();
    if (!force && (this.serviceHealthLoading || now - this.serviceHealthLoadedAt < 45000)) {
      return;
    }
    this.serviceHealthLoading = true;
    this.api.get<ServiceHealth>('health', undefined, { silent: true }).pipe(
      catchError(() => of(normalizeServiceHealth({
        status: 'down',
        timestamp: new Date().toISOString(),
        checks: { database: false, ai: false, storage: false },
        database: { status: 'down', message: 'API health request failed' }
      })))
    ).subscribe(data => {
      this.serviceHealth.set(normalizeServiceHealth(data));
      this.serviceHealthLoadedAt = Date.now();
      this.serviceHealthLoading = false;
    });
  }

  private readonly onPointerMove = (event: PointerEvent): void => {
    const target = event.target instanceof Element
      ? event.target.closest<HTMLElement>('[data-spotlight-surface], .atlas-panel, .context-block, .dock-item, .atlas-record-row, .business-data-row, .procurement-task-card, .shift-stage-card, .shift-action-queue a, .shift-event-timeline a, .module-card-link, .page-evidence-grid a, .field-evidence-grid a, .workflow-signal-list a, .shift-handoff-list a, .context-action')
      : null;
    if (!target) {
      this.clearSpotlight();
      return;
    }
    if (this.spotlightTarget && this.spotlightTarget !== target) {
      this.spotlightTarget.classList.remove('spotlight-active');
      this.spotlightTarget.style.removeProperty('--spotlight-x');
      this.spotlightTarget.style.removeProperty('--spotlight-y');
    }

    const rect = target.getBoundingClientRect();
    this.spotlightTarget = target;
    this.spotlightPoint = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top
    };

    if (!this.spotlightFrame) {
      this.spotlightFrame = window.requestAnimationFrame(this.paintSpotlight);
    }
  };

  private readonly paintSpotlight = (): void => {
    this.spotlightFrame = 0;
    if (!this.spotlightTarget || !this.spotlightPoint) {
      return;
    }
    this.spotlightTarget.style.setProperty('--spotlight-x', `${Math.round(this.spotlightPoint.x)}px`);
    this.spotlightTarget.style.setProperty('--spotlight-y', `${Math.round(this.spotlightPoint.y)}px`);
    this.spotlightTarget.classList.add('spotlight-active');
  };

  private readonly clearSpotlight = (): void => {
    this.spotlightTarget?.classList.remove('spotlight-active');
    this.spotlightTarget?.style.removeProperty('--spotlight-x');
    this.spotlightTarget?.style.removeProperty('--spotlight-y');
    this.spotlightTarget = null;
    this.spotlightPoint = null;
  };

  private scrollMainToTop(): void {
    if (typeof window === 'undefined') {
      return;
    }
    window.requestAnimationFrame(() => {
      document.getElementById('main-content')?.scrollTo({ top: 0, left: 0, behavior: 'instant' as ScrollBehavior });
      window.scrollTo({ top: 0, left: 0, behavior: 'instant' as ScrollBehavior });
    });
  }
}
