import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  LucideBarChart3,
  LucideBell,
  LucideBoxes,
  LucideCircleDollarSign,
  LucideFolderOpen,
  LucideGauge,
  LucideLockKeyhole,
  LucideNetwork,
  LucideScanLine,
  LucideSend,
  LucideSettings2,
  LucideShieldAlert,
  LucideShoppingCart,
  LucideSparkles,
  LucideUserRound,
  LucideX
} from '@lucide/angular';
import { ButtonModule } from 'primeng/button';

import { DockGroup, DockItem } from '../core/models';
import { COMMAND_CENTER_PHOTOS, VisualAsset } from '../core/visual-assets';
import type { WorkflowBlueprint, WorkflowStage } from '../core/workflow-blueprints';

const ICONS = [
  LucideBarChart3,
  LucideBell,
  LucideBoxes,
  LucideCircleDollarSign,
  LucideFolderOpen,
  LucideGauge,
  LucideLockKeyhole,
  LucideNetwork,
  LucideScanLine,
  LucideSend,
  LucideSettings2,
  LucideShieldAlert,
  LucideShoppingCart,
  LucideSparkles,
  LucideUserRound,
  LucideX
];

@Component({
  selector: 'app-module-map',
  standalone: true,
  host: { style: 'display: contents' },
  imports: [CommonModule, RouterLink, ButtonModule, ...ICONS],
  template: `
    <div
      class="module-panel-backdrop"
      role="presentation"
      tabindex="-1"
      (click)="close.emit()"
      (keydown.escape)="close.emit()"
    >
      <aside
        id="module-map-panel"
        class="module-panel atlas-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="模块地图"
        (click)="$event.stopPropagation()"
      >
        <div class="drawer-nav">
          <div class="drawer-head">
            <div class="atlas-brand in-drawer">
              <span class="atlas-brand-mark">NX</span>
              <span>
                <strong>NEXUS Prime</strong>
                <em>模块地图</em>
              </span>
            </div>
            <button pButton type="button" [text]="true" [rounded]="true" (click)="close.emit()" aria-label="关闭更多模块">
              <svg lucideX size="18" strokeWidth="2.2"></svg>
            </button>
          </div>

          <section class="module-command-deck" aria-label="当前业务指挥面">
            <article>
              <span>当前闭环</span>
              <strong>{{ currentWorkflow.title }}</strong>
              <em>{{ activeWorkflowStep.label }} · {{ activeWorkflowStep.metric }}</em>
            </article>
            <article>
              <span>链路健康</span>
              <strong>{{ shellHealth }}%</strong>
              <em>{{ serviceHealthLabel }} · {{ serviceHealthLatencyLabel }}</em>
            </article>
            <article>
              <span>风险队列</span>
              <strong>{{ riskCount }} 条</strong>
              <em>低库存、采购与应收联动</em>
            </article>
          </section>

          <section class="module-workflow-strip" aria-label="当前流程跳转">
            @for (stage of currentWorkflow.stages; track stage.key) {
              <a
                [routerLink]="stage.path"
                (click)="close.emit()"
                [class.active]="stage.path === activeWorkflowStep.path"
                [class.success]="stage.tone === 'success'"
                [class.warning]="stage.tone === 'warning'"
                [class.danger]="stage.tone === 'danger'"
                [class.info]="stage.tone === 'info'"
              >
                <span>{{ stage.label }}</span>
                <strong>{{ stage.metric }}</strong>
              </a>
            }
          </section>

          <section class="module-route-primer" aria-label="推荐跳转">
            <div>
              <span>推荐路径</span>
              <strong>{{ activeWorkflowStep.label }} 后续处理</strong>
              <em>{{ activeWorkflowStep.metric }}</em>
            </div>
            @for (item of recommendedItems(); track item.path) {
              <a [routerLink]="item.path" (click)="close.emit()" [style.--dock-tone]="item.accent">
                <span class="drawer-icon">
                  @switch (item.icon) {
                    @case ('gauge') { <svg lucideGauge size="18" strokeWidth="2.25"></svg> }
                    @case ('boxes') { <svg lucideBoxes size="18" strokeWidth="2.25"></svg> }
                    @case ('network') { <svg lucideNetwork size="18" strokeWidth="2.25"></svg> }
                    @case ('shopping-cart') { <svg lucideShoppingCart size="18" strokeWidth="2.25"></svg> }
                    @case ('send') { <svg lucideSend size="18" strokeWidth="2.25"></svg> }
                    @case ('scan-line') { <svg lucideScanLine size="18" strokeWidth="2.25"></svg> }
                    @case ('shield-alert') { <svg lucideShieldAlert size="18" strokeWidth="2.25"></svg> }
                    @case ('bar-chart-3') { <svg lucideBarChart3 size="18" strokeWidth="2.25"></svg> }
                    @case ('folder-open') { <svg lucideFolderOpen size="18" strokeWidth="2.25"></svg> }
                    @case ('lock-keyhole') { <svg lucideLockKeyhole size="18" strokeWidth="2.25"></svg> }
                    @case ('bell') { <svg lucideBell size="18" strokeWidth="2.25"></svg> }
                    @case ('sparkles') { <svg lucideSparkles size="18" strokeWidth="2.25"></svg> }
                    @case ('circle-dollar-sign') { <svg lucideCircleDollarSign size="18" strokeWidth="2.25"></svg> }
                    @case ('user-round') { <svg lucideUserRound size="18" strokeWidth="2.25"></svg> }
                    @case ('settings-2') { <svg lucideSettings2 size="18" strokeWidth="2.25"></svg> }
                  }
                </span>
                <span>
                  <strong>{{ item.label }}</strong>
                  <em>{{ item.quickActions[0]?.label || item.group }}</em>
                </span>
              </a>
            }
          </section>

          <section class="module-photo-rail" aria-label="业务现场证据">
            @for (photo of modulePhotos; track photo.src) {
              <figure>
                <img [src]="photo.src" [alt]="photo.alt" loading="lazy" decoding="async" />
                <figcaption>
                  <span>{{ photo.label }}</span>
                  <strong>{{ photo.caption }}</strong>
                </figcaption>
              </figure>
            }
          </section>

          <section class="drawer-section module-library">
            <div class="module-library-head">
              <span class="nav-group-label">模块库</span>
              <strong>{{ groups.length }} 组</strong>
            </div>
            @for (group of groups; track group.key) {
              <div class="drawer-group module-card-group" [style.--dock-group-tone]="group.tone">
                <div class="drawer-group-head">
                  <div>
                    <strong>{{ group.label }}</strong>
                    <em>{{ group.items.length }} 个入口 · {{ groupActionCount(group) }} 个动作</em>
                  </div>
                  <a [routerLink]="group.items[0].path" (click)="close.emit()">进入{{ group.label }}</a>
                </div>
                <div class="module-action-row" aria-label="组内快捷动作">
                  @for (action of groupQuickActions(group); track action.path + action.label) {
                    <a [routerLink]="action.path" (click)="close.emit()">{{ action.label }}</a>
                  }
                </div>
                <div class="module-card-grid">
                  @for (item of group.items; track item.path) {
                    <a class="module-card-link" [routerLink]="item.path" [class.active]="itemIsActive(item)" (click)="close.emit()" [style.--dock-tone]="item.accent">
                      <span class="drawer-icon">
                        @switch (item.icon) {
                          @case ('gauge') { <svg lucideGauge size="18" strokeWidth="2.25"></svg> }
                          @case ('boxes') { <svg lucideBoxes size="18" strokeWidth="2.25"></svg> }
                          @case ('network') { <svg lucideNetwork size="18" strokeWidth="2.25"></svg> }
                          @case ('shopping-cart') { <svg lucideShoppingCart size="18" strokeWidth="2.25"></svg> }
                          @case ('send') { <svg lucideSend size="18" strokeWidth="2.25"></svg> }
                          @case ('scan-line') { <svg lucideScanLine size="18" strokeWidth="2.25"></svg> }
                          @case ('shield-alert') { <svg lucideShieldAlert size="18" strokeWidth="2.25"></svg> }
                          @case ('bar-chart-3') { <svg lucideBarChart3 size="18" strokeWidth="2.25"></svg> }
                          @case ('folder-open') { <svg lucideFolderOpen size="18" strokeWidth="2.25"></svg> }
                          @case ('lock-keyhole') { <svg lucideLockKeyhole size="18" strokeWidth="2.25"></svg> }
                          @case ('bell') { <svg lucideBell size="18" strokeWidth="2.25"></svg> }
                          @case ('sparkles') { <svg lucideSparkles size="18" strokeWidth="2.25"></svg> }
                          @case ('circle-dollar-sign') { <svg lucideCircleDollarSign size="18" strokeWidth="2.25"></svg> }
                          @case ('user-round') { <svg lucideUserRound size="18" strokeWidth="2.25"></svg> }
                          @case ('settings-2') { <svg lucideSettings2 size="18" strokeWidth="2.25"></svg> }
                        }
                      </span>
                      <span>
                        <strong>{{ item.label }}</strong>
                        <em>{{ item.quickActions[0]?.label || item.group }}</em>
                      </span>
                    </a>
                  }
                </div>
              </div>
            }
          </section>
        </div>
      </aside>
    </div>
  `
})
export class AppModuleMapComponent {
  protected readonly modulePhotos: VisualAsset[] = COMMAND_CENTER_PHOTOS.slice(0, 12);

  @Input({ required: true }) currentWorkflow!: WorkflowBlueprint;
  @Input({ required: true }) activeWorkflowStep!: WorkflowStage;
  @Input() shellHealth = 0;
  @Input() serviceHealthLabel = '';
  @Input() serviceHealthLatencyLabel = '';
  @Input() riskCount = 0;
  @Input() groups: DockGroup[] = [];
  @Input({ required: true }) itemIsActive!: (item: DockItem) => boolean;

  @Output() close = new EventEmitter<void>();

  recommendedItems(): DockItem[] {
    const activePath = this.activeWorkflowStep.path;
    const flattened = this.groups.flatMap(group => group.items);
    const active = flattened.find(item => item.path === activePath || item.activePaths?.some(path => activePath.startsWith(path)));
    return [active, ...flattened].filter((item): item is DockItem => Boolean(item)).filter((item, index, list) => list.findIndex(entry => entry.path === item.path) === index).slice(0, 3);
  }

  groupQuickActions(group: DockGroup): Array<{ label: string; path: string }> {
    const seen = new Set<string>();
    return group.items
      .flatMap(item => item.quickActions)
      .filter(action => {
        const key = `${action.label}:${action.path}`;
        if (seen.has(key)) {
          return false;
        }
        seen.add(key);
        return true;
      })
      .slice(0, 4);
  }

  groupActionCount(group: DockGroup): number {
    return group.items.reduce((sum, item) => sum + item.quickActions.length, 0);
  }
}
