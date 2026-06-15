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
  LucideMoreHorizontal,
  LucideNetwork,
  LucideScanLine,
  LucideSend,
  LucideSettings2,
  LucideShieldAlert,
  LucideShoppingCart,
  LucideSparkles,
  LucideUserRound
} from '@lucide/angular';

import { DockGroup, DockItem } from '../core/models';

const ICONS = [
  LucideBarChart3,
  LucideBell,
  LucideBoxes,
  LucideCircleDollarSign,
  LucideFolderOpen,
  LucideGauge,
  LucideLockKeyhole,
  LucideMoreHorizontal,
  LucideNetwork,
  LucideScanLine,
  LucideSend,
  LucideSettings2,
  LucideShieldAlert,
  LucideShoppingCart,
  LucideSparkles,
  LucideUserRound
];

@Component({
  selector: 'app-dock',
  standalone: true,
  host: { style: 'display: contents' },
  imports: [CommonModule, RouterLink, ...ICONS],
  template: `
    <nav class="atlas-dock atlas-dock-island dock-grouped-island" aria-label="主业务流程导航">
      @for (group of groups; track group.key) {
        <section
          class="dock-capsule"
          [class.contains-active]="groupIsActive(group)"
          [style.--dock-group-tone]="group.tone"
          [attr.aria-label]="group.label"
        >
          <span class="dock-capsule-label">{{ group.label }}</span>
          <div class="dock-island-track">
            @for (item of group.items; track item.path) {
              <a
                class="dock-item"
                [routerLink]="item.path"
                [class.active]="itemIsActive(item)"
                [attr.aria-current]="itemIsActive(item) ? 'page' : null"
                [style.--dock-tone]="item.accent"
                [attr.aria-label]="item.label"
              >
                <span class="dock-active-line"></span>
                <span class="dock-icon">
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
                <span class="dock-label" aria-hidden="true">{{ item.shortLabel }}</span>
                <span class="dock-popover" aria-hidden="true">
                  <b>{{ item.label }}</b>
                  <em>{{ item.group }}</em>
                </span>
              </a>
            }
          </div>
        </section>
      }

      <section class="dock-capsule dock-capsule-more" [class.active]="moreActive">
        <button
          type="button"
          class="atlas-dock-more"
          [class.active]="moreActive"
          (click)="moreOpen.emit($event)"
          aria-label="查看更多模块"
          aria-haspopup="dialog"
          aria-controls="module-map-panel"
          [attr.aria-expanded]="drawerOpen"
        >
          <svg lucideMoreHorizontal size="18" strokeWidth="2.35"></svg>
          <span class="dock-label" aria-hidden="true">更多</span>
          <span class="dock-popover more" aria-hidden="true">
            <b>更多模块</b>
          </span>
        </button>
      </section>
    </nav>
  `
})
export class AppDockComponent {
  @Input() groups: DockGroup[] = [];
  @Input() drawerOpen = false;
  @Input() moreActive = false;
  @Input({ required: true }) itemIsActive!: (item: DockItem) => boolean;
  @Input({ required: true }) groupIsActive!: (group: DockGroup) => boolean;

  @Output() moreOpen = new EventEmitter<Event>();
}
