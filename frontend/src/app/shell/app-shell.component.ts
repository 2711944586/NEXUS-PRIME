import { CommonModule } from '@angular/common';
import { Component, DestroyRef, HostListener, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { MessageService } from 'primeng/api';
import { catchError, filter, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { DockGroup, DockItem, ManufacturingCommandCenter, ServiceHealth } from '../core/models';
import {
  DESKTOP_DOCK_KEYS,
  dockItemForUrl,
  dockItemMatchesUrl,
  dockItemsByKeys,
  DOCK_ITEMS,
  groupedDockItems,
  MOBILE_DOCK_KEYS,
  MORE_DOCK_ITEMS
} from '../core/navigation';
import { ThemeService } from '../core/theme.service';
import { COMMAND_CENTER_PHOTOS } from '../core/visual-assets';
import { activeWorkflowStage, workflowForUrl } from '../core/workflow-blueprints';
import type { WorkflowBlueprint, WorkflowStage } from '../core/workflow-blueprints';
import { AppDockComponent } from './app-dock.component';
import { AppContextPanelComponent } from './app-context-panel.component';
import { AppModuleMapComponent } from './app-module-map.component';
import { AppTopbarComponent, QuickCreateAction } from './app-topbar.component';
import { ResourceWorkbenchComponent } from './resource-workbench.component';
import {
  EMPTY_COMMAND_CENTER,
  EMPTY_SERVICE_HEALTH,
  buildShiftHandoffActions,
  buildWorkflowSignals,
  calculateShellHealth,
  compactMoney,
  compactNumber,
  moduleEntryCount,
  nextWorkflowSteps,
  normalizeServiceHealth,
  pageEvidenceTiles,
  riskPath,
  serviceHealthLabel,
  serviceHealthLatencyLabel,
  serviceHealthTooltip,
  userInitials,
  workflowEvidenceTiles
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
  imports: [CommonModule, FormsModule, RouterOutlet, RouterLink, AppContextPanelComponent, AppDockComponent, AppModuleMapComponent, AppTopbarComponent, ResourceWorkbenchComponent],
  template: `
    <div class="atlas-shell" [class.drawer-open]="moreOpen">
      <app-topbar
        [activeDock]="activeDock()"
        [searchQuery]="searchQuery"
        [searchResults]="searchResults()"
        [quickCreateActions]="quickCreateActions"
        [createOpen]="createOpen"
        [moreOpen]="moreOpen"
        [serviceHealth]="serviceHealth()"
        [serviceHealthLabel]="serviceHealthLabel()"
        [serviceHealthLatencyLabel]="serviceHealthLatencyLabel()"
        [serviceHealthTooltip]="serviceHealthTooltip()"
        [todayText]="todayText"
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
        (moduleMapOpen)="openModuleMap($event)"
        (logout)="logout()"
      />

      <app-dock
        [groups]="visibleDockGroups()"
        [drawerOpen]="moreOpen"
        [moreActive]="moreIsActive()"
        [itemIsActive]="itemIsActive"
        [groupIsActive]="groupIsActive"
        (moreOpen)="openModuleMap($event)"
      />

      <div class="atlas-workbench">
        <main class="content-stage atlas-stage" id="main-content">
          <router-outlet />
        </main>

        <section class="page-evidence-strip" aria-label="页面级现场证据">
          <div class="context-title">
            <span>页面现场</span>
            <em>{{ currentWorkflow().title }} · {{ pageEvidenceTiles().length }} 张</em>
          </div>
          <div class="page-evidence-grid">
            @for (tile of pageEvidenceTiles(); track tile.photo.src + tile.stage.key) {
              <a [routerLink]="tile.stage.path" [class.warning]="tile.stage.tone === 'warning'" [class.danger]="tile.stage.tone === 'danger'" [class.success]="tile.stage.tone === 'success'">
                <img [src]="tile.photo.src" [alt]="tile.photo.alt" loading="eager" decoding="async" fetchpriority="high" />
                <span>{{ tile.photo.label }}</span>
                <strong>{{ tile.stage.label }} · {{ tile.stage.metric }}</strong>
                <em>{{ tile.photo.caption }}</em>
              </a>
            }
          </div>
        </section>

        <app-resource-workbench />

        <app-context-panel
          [currentWorkflow]="currentWorkflow()"
          [activeWorkflowStep]="activeWorkflowStep()"
          [shellHealth]="shellHealth()"
          [shellRisks]="shellRisks()"
          [totalRiskCount]="commandData().risks.length"
          [stockQuantityLabel]="compactNumber(commandData().kpis.stock_quantity)"
          [pendingPurchase]="commandData().kpis.pending_purchase"
          [overdueAmountLabel]="compactMoney(commandData().kpis.overdue_amount)"
          [workflowSignals]="workflowSignals()"
          [workflowEvidenceTiles]="workflowEvidenceTiles()"
          [shiftHandoffActions]="shiftHandoffActions()"
          [nextWorkflowSteps]="nextWorkflowSteps()"
          [moduleEntryCount]="moduleEntryCount()"
          [visualAssetCount]="visualAssetCount"
          [todayText]="todayText"
          [riskPath]="riskPath"
        />
      </div>

      @if (moreOpen) {
        <app-module-map
          [currentWorkflow]="currentWorkflow()"
          [activeWorkflowStep]="activeWorkflowStep()"
          [shellHealth]="shellHealth()"
          [serviceHealthLabel]="serviceHealthLabel()"
          [serviceHealthLatencyLabel]="serviceHealthLatencyLabel()"
          [riskCount]="commandData().risks.length"
          [modulePhotos]="modulePhotos"
          [groups]="extraDockGroups()"
          [itemIsActive]="itemIsActive"
          (close)="closeModuleMap()"
        />
      }
    </div>
  `
})
export class AppShellComponent implements OnInit, OnDestroy {
  protected readonly theme = inject(ThemeService);
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly messages = inject(MessageService);
  private readonly destroyRef = inject(DestroyRef);

  protected moreOpen = false;
  protected createOpen = false;
  protected searchQuery = '';
  protected readonly searchResults = signal<Array<{ type: string; label: string; description?: string; path: string }>>([]);
  protected readonly quickCreateActions = QUICK_CREATE_ACTIONS;
  protected readonly modulePhotos = COMMAND_CENTER_PHOTOS.slice(0, 12);
  protected readonly visualAssetCount = COMMAND_CENTER_PHOTOS.length;
  protected readonly primaryDockItems = DOCK_ITEMS;
  protected readonly desktopDockItems = dockItemsByKeys(DESKTOP_DOCK_KEYS);
  protected readonly mobileDockItems = dockItemsByKeys(MOBILE_DOCK_KEYS);
  private readonly currentUrl = signal(this.router.url);
  protected readonly commandData = signal<ManufacturingCommandCenter>(EMPTY_COMMAND_CENTER);
  protected readonly serviceHealth = signal<ServiceHealth>(EMPTY_SERVICE_HEALTH);
  protected readonly activeDock = computed<DockItem>(() => dockItemForUrl(this.currentUrl()));
  protected readonly isMobileDock = signal(false);
  protected readonly brokenAvatarUrl = signal('');
  protected readonly visibleDockItems = computed(() => this.isMobileDock() ? this.mobileDockItems : this.desktopDockItems);
  protected readonly visibleDockGroups = computed<DockGroup[]>(() => groupedDockItems(this.visibleDockItems()));
  protected readonly currentWorkflow = computed<WorkflowBlueprint>(() => workflowForUrl(this.currentUrl()));
  protected readonly activeWorkflowStep = computed<WorkflowStage>(() => activeWorkflowStage(this.currentWorkflow(), this.currentUrl()));
  protected readonly workflowSignals = computed(() => buildWorkflowSignals(this.commandData(), this.currentWorkflow()));
  protected readonly nextWorkflowSteps = computed<WorkflowStage[]>(() => nextWorkflowSteps(this.currentWorkflow(), this.activeWorkflowStep()));
  protected readonly workflowEvidenceTiles = computed(() => workflowEvidenceTiles(this.currentWorkflow(), COMMAND_CENTER_PHOTOS));
  protected readonly pageEvidenceTiles = computed(() => pageEvidenceTiles(this.currentWorkflow(), COMMAND_CENTER_PHOTOS));
  protected readonly shiftHandoffActions = computed(() => buildShiftHandoffActions(this.currentWorkflow(), this.workflowSignals(), this.nextWorkflowSteps()));
  protected readonly extraDockGroups = computed(() => {
    const all = [...DOCK_ITEMS, ...MORE_DOCK_ITEMS];
    const seen = new Set<string>();
    return groupedDockItems(all.filter(item => {
      if (seen.has(item.key)) {
        return false;
      }
      seen.add(item.key);
      return true;
    }));
  });
  protected readonly moduleEntryCount = computed(() => moduleEntryCount(this.extraDockGroups()));
  protected readonly shellRisks = computed(() => this.commandData().risks.slice(0, 3));
  private commandDataLoadedAt = 0;
  private commandDataLoading = false;
  private serviceHealthLoadedAt = 0;
  private serviceHealthLoading = false;
  private spotlightFrame = 0;
  private spotlightTarget: HTMLElement | null = null;
  private spotlightPoint: { x: number; y: number } | null = null;
  protected readonly shellHealth = computed(() => calculateShellHealth(this.commandData()));
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
    this.theme.hydrateFromServer();
    this.loadCommandData();
    this.loadServiceHealth();
    this.syncViewportMode();
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe(event => {
      this.moreOpen = false;
      this.createOpen = false;
      this.clearSearch();
      this.currentUrl.set((event as NavigationEnd).urlAfterRedirects);
      this.loadCommandData();
      this.loadServiceHealth();
      this.scrollMainToTop();
    });
    if (typeof window !== 'undefined') {
      window.addEventListener('resize', this.onResize);
      window.addEventListener('pointermove', this.onPointerMove, { passive: true });
      window.addEventListener('pointerleave', this.clearSpotlight);
    }
  }

  ngOnDestroy(): void {
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', this.onResize);
      window.removeEventListener('pointermove', this.onPointerMove);
      window.removeEventListener('pointerleave', this.clearSpotlight);
      if (this.spotlightFrame) {
        window.cancelAnimationFrame(this.spotlightFrame);
        this.spotlightFrame = 0;
      }
    }
    this.clearSpotlight();
  }

  logout(): void {
    this.auth.logout();
    this.router.navigateByUrl('/auth/login');
  }

  @HostListener('document:keydown.escape')
  protected closeTransientPanels(): void {
    this.moreOpen = false;
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
    const insideModuleSurface = Boolean(target.closest('.module-panel, button[aria-label="更多模块"], .atlas-dock-more'));
    if (!insideCreateSurface) {
      this.createOpen = false;
    }
    if (!insideModuleSurface && !target.closest('.module-panel-backdrop')) {
      this.moreOpen = false;
    }
  }

  toggleQuickCreate(event?: Event): void {
    event?.stopPropagation();
    this.createOpen = !this.createOpen;
    if (this.createOpen) {
      this.moreOpen = false;
      this.focusAfterRender('.quick-create-popover a');
    }
  }

  closeQuickCreate(): void {
    this.createOpen = false;
  }

  openModuleMap(event?: Event): void {
    event?.stopPropagation();
    this.createOpen = false;
    this.clearSearch();
    this.moreOpen = true;
    this.focusAfterRender('.module-panel button[aria-label="关闭更多模块"]');
  }

  closeModuleMap(): void {
    this.moreOpen = false;
  }

  runSearch(): void {
    const q = this.searchQuery.trim();
    if (q.length < 2) {
      this.showSearchSuggestions();
      return;
    }
    this.api.get<{ items: Array<{ type: string; label: string; description?: string; path: string }> }>('search', { q }).subscribe({
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
    const q = value.trim();
    if (!q) {
      this.showSearchSuggestions();
      return;
    }
    if (q.length >= 2) {
      this.runSearch();
    }
  }

  showSearchSuggestions(): void {
    if (!this.searchQuery.trim()) {
      this.searchResults.set(COMMAND_SUGGESTIONS);
    }
  }

  refreshShell(): void {
    this.loadCommandData(true);
    this.loadServiceHealth(true);
    this.messages.add({ severity: 'success', summary: '运营数据已同步', detail: '顶部指标、风险队列、服务状态和业务入口已刷新。' });
  }

  protected readonly riskPath = (risk: ManufacturingCommandCenter['risks'][number]): string => {
    return riskPath(risk);
  };

  compactMoney(value: number): string {
    return compactMoney(value);
  }

  compactNumber(value: number): string {
    return compactNumber(value);
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
    return dockItemMatchesUrl(item, this.currentUrl());
  };

  moreIsActive(): boolean {
    const visibleKeys = new Set(this.visibleDockItems().map(item => item.key));
    return !visibleKeys.has(this.activeDock().key);
  }

  protected readonly groupIsActive = (group: DockGroup): boolean => {
    return group.items.some(item => this.itemIsActive(item));
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

  private loadCommandData(force = false): void {
    const now = Date.now();
    if (!force && (this.commandDataLoading || now - this.commandDataLoadedAt < 45000)) {
      return;
    }
    this.commandDataLoading = true;
    this.api.get<ManufacturingCommandCenter>('manufacturing/command-center').pipe(
      catchError(() => of(EMPTY_COMMAND_CENTER))
    ).subscribe(data => {
      this.commandData.set(data);
      this.commandDataLoadedAt = Date.now();
      this.commandDataLoading = false;
    });
  }

  private loadServiceHealth(force = false): void {
    const now = Date.now();
    if (!force && (this.serviceHealthLoading || now - this.serviceHealthLoadedAt < 45000)) {
      return;
    }
    this.serviceHealthLoading = true;
    this.api.get<ServiceHealth>('health').pipe(
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

  private syncViewportMode(): void {
    this.isMobileDock.set(typeof window !== 'undefined' ? window.innerWidth <= 760 : false);
  }

  private readonly onResize = (): void => {
    this.syncViewportMode();
  };

  private readonly onPointerMove = (event: PointerEvent): void => {
    const target = event.target instanceof Element
      ? event.target.closest<HTMLElement>('[data-spotlight-surface], .atlas-panel, .context-block, .dock-item, .atlas-dock-more, .atlas-record-row, .business-data-row, .procurement-task-card, .shift-stage-card, .shift-action-queue a, .shift-event-timeline a, .module-card-link, .page-evidence-grid a, .field-evidence-grid a, .workflow-signal-list a, .shift-handoff-list a, .context-action')
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
