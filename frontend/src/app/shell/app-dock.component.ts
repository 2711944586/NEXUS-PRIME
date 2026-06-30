import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
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
  LucideUserRound
} from '@lucide/angular';

import { DockGroup, DockItem } from '../core/models';
import type { NavigationState } from '../core/navigation';

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
  LucideUserRound
];

@Component({
  selector: 'app-dock',
  standalone: true,
  host: { style: 'display: contents' },
  imports: [CommonModule, RouterLink, ...ICONS],
  template: `
    <nav class="atlas-dock atlas-dock-island dock-grouped-island" aria-label="主业务流程导航">
      <div class="dock-current-domain" [style.--dock-group-tone]="navigation.activeGroup.tone">
        <span>当前域</span>
        <strong>{{ navigation.activeGroup.label }}</strong>
      </div>
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
                [attr.title]="item.label"
                (mouseenter)="showDockHint(item, $event)"
                (focus)="showDockHint(item, $event)"
                (mouseleave)="hideDockHint()"
                (blur)="hideDockHint()"
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

    </nav>
    @if (activeDockHint) {
      <div class="dock-floating-popover" [style.top.px]="activeDockHint.top" [style.left.px]="activeDockHint.left" role="tooltip">
        <b>{{ activeDockHint.label }}</b>
        <em>{{ activeDockHint.group }}</em>
      </div>
    }
  `
})
export class AppDockComponent {
  @Input({ required: true }) navigation!: NavigationState;
  @Input() groups: DockGroup[] = [];
  @Input({ required: true }) itemIsActive!: (item: DockItem) => boolean;
  @Input({ required: true }) groupIsActive!: (group: DockGroup) => boolean;

  activeDockHint: { label: string; group: string; top: number; left: number } | null = null;

  showDockHint(item: DockItem, event: MouseEvent | FocusEvent): void {
    const target = event.currentTarget;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const rect = target.getBoundingClientRect();
    const left = Math.min(rect.right + 12, window.innerWidth - 236);
    this.activeDockHint = {
      label: item.label,
      group: item.group,
      top: rect.top + rect.height / 2,
      left: Math.max(12, left)
    };
  }

  hideDockHint(): void {
    this.activeDockHint = null;
  }
}
