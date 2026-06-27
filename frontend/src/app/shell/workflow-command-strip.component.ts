import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ProgressBarModule } from 'primeng/progressbar';

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
          <span>当前闭环</span>
          <strong>{{ workflow.title }}</strong>
          <p>{{ workflow.summary }}</p>
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

      <div class="workflow-command-bottom">
        <div class="workflow-command-signals" aria-label="执行信号">
          @for (signal of signals; track signal.label) {
            <a
              [routerLink]="signal.path"
              [class.warning]="signal.tone === 'warning'"
              [class.danger]="signal.tone === 'danger'"
              [class.success]="signal.tone === 'success'"
              [class.info]="signal.tone === 'info'"
            >
              <span>{{ signal.label }}</span>
              <strong>{{ signal.value }}</strong>
              <em>{{ signal.caption }}</em>
            </a>
          }
        </div>

        <div class="workflow-command-actions" aria-label="下一步动作">
          @for (action of handoffActions.slice(0, 2); track action.path + action.label) {
            <a
              [routerLink]="action.path"
              [class.warning]="action.tone === 'warning'"
              [class.danger]="action.tone === 'danger'"
              [class.success]="action.tone === 'success'"
            >
              <span>{{ action.priority }} / {{ action.owner }}</span>
              <strong>{{ action.label }}</strong>
              <em>{{ action.metric }} / {{ action.due }}</em>
            </a>
          }
          @for (stage of nextStages.slice(0, 1); track stage.key) {
            <a class="workflow-next-link" [routerLink]="stage.path">
              <span>下一节点</span>
              <strong>{{ stage.label }}</strong>
              <em>{{ stage.metric }}</em>
            </a>
          }
        </div>
      </div>
    </section>
  `
})
export class WorkflowCommandStripComponent {
  @Input({ required: true }) workflow!: WorkflowBlueprint;
  @Input({ required: true }) activeStage!: WorkflowStage;
  @Input() signals: WorkflowSignal[] = [];
  @Input() nextStages: WorkflowStage[] = [];
  @Input() handoffActions: ShiftHandoffAction[] = [];
  @Input() shellHealth = 0;
  @Input() riskCount = 0;
}
