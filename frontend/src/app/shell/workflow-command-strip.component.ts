import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ProgressBarModule } from 'primeng/progressbar';

import type { NavigationState } from '../core/navigation';
import type { WorkflowBlueprint, WorkflowStage } from '../core/workflow-blueprints';
import type { ShiftHandoffAction, WorkflowSignal } from './app-shell.models';

@Component({
  selector: 'app-workflow-command-strip',
  standalone: true,
  imports: [CommonModule, RouterLink, ProgressBarModule],
  template: `
    <section class="workflow-command-strip" aria-label="当前页面业务流程指挥条">
      <div class="workflow-command-primary">
        <div class="workflow-command-copy">
          <span>{{ navigation.activeGroup.label }} / {{ navigation.activeItem.shortLabel }}</span>
          <strong>{{ navigation.activeItem.label }}</strong>
          <p>{{ navigation.activeGroup.summary }}</p>
        </div>
        <div class="workflow-command-health" [class.warning]="riskCount > 0" [class.danger]="riskCount > 4">
          <span>链路健康</span>
          <strong>{{ shellHealth }}%</strong>
          <p-progressbar [value]="shellHealth" [showValue]="false" />
        </div>
      </div>

      <nav class="workflow-command-steps" aria-label="业务闭环节点">
        @for (stage of workflow.stages; track stage.key) {
          <a
            [routerLink]="stage.path"
            [class.active]="stage.key === activeStage.key"
            [class.warning]="stage.tone === 'warning'"
            [class.danger]="stage.tone === 'danger'"
            [class.success]="stage.tone === 'success'"
            [attr.aria-current]="stage.key === activeStage.key ? 'step' : null"
          >
            <span>{{ stage.label }}</span>
            <strong>{{ stage.metric }}</strong>
          </a>
        }
      </nav>

      <div class="workflow-command-summary" aria-label="当前链路状态">
        @for (signal of signals.slice(0, 3); track signal.label) {
          <a
            [routerLink]="signal.path"
            [class.warning]="signal.tone === 'warning'"
            [class.danger]="signal.tone === 'danger'"
            [class.success]="signal.tone === 'success'"
            [class.info]="signal.tone === 'info'"
          >
            <span>{{ signal.label }}</span>
            <strong>{{ signal.value }}</strong>
          </a>
        }
        @for (action of handoffActions.slice(0, 1); track action.path + action.label) {
          <a
            class="workflow-handoff-link"
            [routerLink]="action.path"
            [class.warning]="action.tone === 'warning'"
            [class.danger]="action.tone === 'danger'"
            [class.success]="action.tone === 'success'"
          >
            <span>{{ action.owner }} / {{ action.due }}</span>
            <strong>{{ action.label }}</strong>
          </a>
        }
        @for (stage of nextStages.slice(0, 1); track stage.key) {
          <a class="workflow-next-link" [routerLink]="stage.path">
            <span>下一节点</span>
            <strong>{{ stage.label }}</strong>
          </a>
        }
      </div>
    </section>
  `
})
export class WorkflowCommandStripComponent {
  @Input({ required: true }) navigation!: NavigationState;
  @Input({ required: true }) workflow!: WorkflowBlueprint;
  @Input({ required: true }) activeStage!: WorkflowStage;
  @Input() signals: WorkflowSignal[] = [];
  @Input() nextStages: WorkflowStage[] = [];
  @Input() handoffActions: ShiftHandoffAction[] = [];
  @Input() shellHealth = 0;
  @Input() riskCount = 0;
}
