import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  LucideBarChart3,
  LucideBell,
  LucideChevronRight,
  LucideCircleDollarSign,
  LucideLogOut,
  LucideMoon,
  LucideMoreHorizontal,
  LucidePlus,
  LucideRefreshCw,
  LucideSearch,
  LucideSend,
  LucideSettings2,
  LucideShoppingCart,
  LucideSparkles,
  LucideSun,
  LucideUserRound,
  LucideWarehouse
} from '@lucide/angular';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TooltipModule } from 'primeng/tooltip';

import { AuthService } from '../core/auth.service';
import { DockItem, ServiceHealth, User } from '../core/models';
import { ThemeService } from '../core/theme.service';

export type QuickCreateAction = {
  label: string;
  description: string;
  path: string;
  icon: 'warehouse' | 'shopping-cart' | 'send' | 'money' | 'chart';
  accent: string;
};

export type CommandSearchResult = {
  type: string;
  label: string;
  description?: string;
  path: string;
};

const ICONS = [
  LucideBarChart3,
  LucideBell,
  LucideChevronRight,
  LucideCircleDollarSign,
  LucideLogOut,
  LucideMoon,
  LucideMoreHorizontal,
  LucidePlus,
  LucideRefreshCw,
  LucideSearch,
  LucideSend,
  LucideSettings2,
  LucideShoppingCart,
  LucideSparkles,
  LucideSun,
  LucideUserRound,
  LucideWarehouse
];

@Component({
  selector: 'app-topbar',
  standalone: true,
  host: { style: 'display: contents' },
  imports: [CommonModule, FormsModule, RouterLink, ButtonModule, InputTextModule, TooltipModule, ...ICONS],
  template: `
    <header class="atlas-topbar">
      <a class="atlas-brand" routerLink="/app/overview" aria-label="返回运营总览">
        <span class="atlas-brand-mark">NX</span>
        <span>
          <strong>NEXUS Prime</strong>
          <em>制造经营系统</em>
        </span>
      </a>

      <div class="atlas-location">
        <nav class="breadcrumbs" aria-label="当前位置">
          <a routerLink="/app/overview">控制塔</a>
          <svg lucideChevronRight size="14" strokeWidth="2.2"></svg>
          <span>{{ activeDock.group }}</span>
        </nav>
        <strong>{{ activeDock.label }}</strong>
      </div>

      <div class="atlas-search" role="search">
        <svg lucideSearch size="17" strokeWidth="2.2"></svg>
        <input
          pInputText
          [ngModel]="searchQuery"
          aria-label="搜索物料、订单、客户和报表"
          placeholder="搜索物料、订单、客户、报表"
          (focus)="searchFocus.emit()"
          (ngModelChange)="searchQueryChange.emit($event)"
          (keydown.enter)="searchSubmit.emit()"
        />
        @if (searchResults.length) {
          <div class="search-popover atlas-search-popover">
            @for (item of searchResults; track item.path) {
              <a [routerLink]="item.path" (click)="searchClear.emit()">
                <span class="search-result-type">{{ item.type }}</span>
                <span class="search-result-copy">
                  <strong>{{ item.label }}</strong>
                  <em>{{ item.description }}</em>
                </span>
                <svg lucideChevronRight size="15" strokeWidth="2.3"></svg>
              </a>
            }
          </div>
        }
      </div>

      <div class="atlas-actions">
        <a
          class="service-health-chip"
          routerLink="/app/integrations"
          [class.degraded]="serviceHealth.status === 'degraded'"
          [class.down]="serviceHealth.status === 'down'"
          [attr.aria-label]="'服务状态：' + serviceHealthLabel"
          [pTooltip]="serviceHealthTooltip"
        >
          <span class="health-dot"></span>
          <strong>{{ serviceHealthLabel }}</strong>
          <em>{{ serviceHealthLatencyLabel }}</em>
        </a>
        <a pButton class="ai-topbar-action" routerLink="/app/ai" aria-label="打开经营分析台" pTooltip="经营分析台">
          <span class="toolbar-icon"><svg lucideSparkles size="17" strokeWidth="2.35"></svg></span>
          <span class="topbar-action-label">经营分析</span>
        </a>
        <a pButton class="icon-action" [text]="true" [rounded]="true" routerLink="/app/settings" aria-label="全局设置" pTooltip="全局设置">
          <span class="toolbar-icon"><svg lucideSettings2 size="18" strokeWidth="2.2"></svg></span>
        </a>
        <button
          pButton
          type="button"
          class="create-action"
          (click)="quickCreateToggle.emit($event)"
          aria-label="打开快捷创建"
          aria-haspopup="menu"
          aria-controls="quick-create-popover"
          [attr.aria-expanded]="createOpen"
        >
          <span class="toolbar-icon"><svg lucidePlus size="17" strokeWidth="2.4"></svg></span>
          <span class="topbar-action-label">创建</span>
        </button>
        @if (createOpen) {
          <div id="quick-create-popover" class="quick-create-popover" role="menu" aria-label="快捷创建">
            <div class="quick-create-head">
              <span>快捷创建</span>
              <strong>选择要推进的业务动作</strong>
            </div>
            @for (action of quickCreateActions; track action.path) {
              <a role="menuitem" [routerLink]="action.path" (click)="quickCreateClose.emit()" [style.--quick-tone]="action.accent">
                <i>
                  @switch (action.icon) {
                    @case ('warehouse') { <svg lucideWarehouse size="17" strokeWidth="2.25"></svg> }
                    @case ('shopping-cart') { <svg lucideShoppingCart size="17" strokeWidth="2.25"></svg> }
                    @case ('send') { <svg lucideSend size="17" strokeWidth="2.25"></svg> }
                    @case ('money') { <svg lucideCircleDollarSign size="17" strokeWidth="2.25"></svg> }
                    @case ('chart') { <svg lucideBarChart3 size="17" strokeWidth="2.25"></svg> }
                  }
                </i>
                <span>
                  <strong>{{ action.label }}</strong>
                  <em>{{ action.description }}</em>
                </span>
              </a>
            }
          </div>
        }
        <button pButton type="button" class="sync-action icon-action" severity="secondary" (click)="refresh.emit()" aria-label="同步运营数据" pTooltip="同步运营数据">
          <span class="toolbar-icon"><svg lucideRefreshCw size="16" strokeWidth="2.25"></svg></span>
        </button>
        <span class="atlas-clock"><i></i>{{ todayText }}</span>
        <button pButton type="button" class="icon-action" [text]="true" [rounded]="true" (click)="theme.toggle()" aria-label="切换主题" pTooltip="切换主题">
          @if (theme.mode() === 'dark-cockpit') {
            <span class="toolbar-icon"><svg lucideMoon size="18" strokeWidth="2.2"></svg></span>
          } @else {
            <span class="toolbar-icon"><svg lucideSun size="18" strokeWidth="2.2"></svg></span>
          }
        </button>
        <a pButton class="icon-action" [text]="true" [rounded]="true" routerLink="/app/notifications" aria-label="通知中心" pTooltip="通知中心">
          <span class="toolbar-icon toolbar-icon-badge">
            <svg lucideBell size="18" strokeWidth="2.2"></svg>
            @if (notificationCount > 0) {
              <span class="toolbar-badge" aria-label="{{ notificationCount }} 条未读通知">{{ notificationCount > 99 ? '99+' : notificationCount }}</span>
            }
          </span>
        </a>
        <a pButton [text]="true" [rounded]="true" routerLink="/app/profile" class="profile-avatar-button icon-action" aria-label="个人工作台" pTooltip="个人工作台">
          @if (auth.currentUser$ | async; as user) {
            @if (user.avatar && brokenAvatarUrl !== user.avatar) {
              <img [src]="user.avatar" [alt]="user.full_name || user.username" (error)="avatarBroken.emit(user.avatar)" />
            } @else {
              <span class="avatar-initials">{{ initials(user) }}</span>
            }
          } @else {
            <span class="toolbar-icon"><svg lucideUserRound size="18" strokeWidth="2.2"></svg></span>
          }
        </a>
        <button
          pButton
          type="button"
          class="icon-action"
          [text]="true"
          [rounded]="true"
          (click)="moduleMapOpen.emit($event)"
          aria-label="更多模块"
          aria-haspopup="dialog"
          aria-controls="module-map-panel"
          [attr.aria-expanded]="moreOpen"
          pTooltip="更多模块"
        >
          <span class="toolbar-icon"><svg lucideMoreHorizontal size="19" strokeWidth="2.3"></svg></span>
        </button>
        <button pButton type="button" class="icon-action" [text]="true" [rounded]="true" (click)="logout.emit()" aria-label="退出登录" pTooltip="退出登录">
          <span class="toolbar-icon"><svg lucideLogOut size="18" strokeWidth="2.2"></svg></span>
        </button>
      </div>
    </header>
  `
})
export class AppTopbarComponent {
  protected readonly theme = inject(ThemeService);
  protected readonly auth = inject(AuthService);

  @Input({ required: true }) activeDock!: DockItem;
  @Input() searchQuery = '';
  @Input() searchResults: CommandSearchResult[] = [];
  @Input() quickCreateActions: QuickCreateAction[] = [];
  @Input() createOpen = false;
  @Input() moreOpen = false;
  @Input({ required: true }) serviceHealth!: ServiceHealth;
  @Input() serviceHealthLabel = '';
  @Input() serviceHealthLatencyLabel = '';
  @Input() serviceHealthTooltip = '';
  @Input() todayText = '';
  @Input() brokenAvatarUrl = '';
  @Input({ required: true }) initials!: (user: Pick<User, 'full_name' | 'username' | 'email'>) => string;

  @Input() notificationCount = 0;

  @Output() searchFocus = new EventEmitter<void>();
  @Output() searchQueryChange = new EventEmitter<string>();
  @Output() searchSubmit = new EventEmitter<void>();
  @Output() searchClear = new EventEmitter<void>();
  @Output() quickCreateToggle = new EventEmitter<Event>();
  @Output() quickCreateClose = new EventEmitter<void>();
  @Output() refresh = new EventEmitter<void>();
  @Output() avatarBroken = new EventEmitter<string | null | undefined>();
  @Output() moduleMapOpen = new EventEmitter<Event>();
  @Output() logout = new EventEmitter<void>();
}
