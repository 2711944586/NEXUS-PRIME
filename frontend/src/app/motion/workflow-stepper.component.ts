import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';

export type WorkflowStepperTone = 'default' | 'success' | 'warning' | 'danger' | 'info';
export type WorkflowStepperState = 'complete' | 'active' | 'pending' | 'blocked';

export interface WorkflowStepperStep {
  label: string;
  detail?: string;
  meta?: string;
  path?: string;
  tone?: WorkflowStepperTone;
  state?: WorkflowStepperState;
}

@Component({
  selector: 'nexus-workflow-stepper',
  standalone: true,
  imports: [CommonModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'nexus-workflow-stepper',
    '[class.nexus-workflow-stepper--compact]': 'compact',
    '[attr.aria-label]': 'ariaLabel'
  },
  template: `
    @if (steps.length) {
      <ol class="nexus-workflow-stepper__list" role="list">
        @for (step of steps; track step.label) {
          <li
            class="nexus-workflow-stepper__item"
            [class]="toneClass(step)"
            [class.is-complete]="stateFor($index, step) === 'complete'"
            [class.is-active]="stateFor($index, step) === 'active'"
            [class.is-pending]="stateFor($index, step) === 'pending'"
            [class.is-blocked]="stateFor($index, step) === 'blocked'"
            [attr.aria-current]="stateFor($index, step) === 'active' ? 'step' : null"
          >
            @if (step.path) {
              <a class="nexus-workflow-stepper__surface" [routerLink]="step.path">
                <ng-container *ngTemplateOutlet="stepBody; context: { step, index: $index }"></ng-container>
              </a>
            } @else {
              <div class="nexus-workflow-stepper__surface">
                <ng-container *ngTemplateOutlet="stepBody; context: { step, index: $index }"></ng-container>
              </div>
            }
          </li>
        }
      </ol>
    } @else {
      <p class="nexus-workflow-stepper__empty" role="status">暂无流程节点</p>
    }

    <ng-template #stepBody let-step="step" let-index="index">
      <span class="nexus-workflow-stepper__index">{{ index + 1 }}</span>
      <span class="nexus-workflow-stepper__copy">
        <strong>{{ step.label }}</strong>
        @if (step.detail) {
          <span>{{ step.detail }}</span>
        }
      </span>
      @if (step.meta) {
        <em>{{ step.meta }}</em>
      }
    </ng-template>
  `
})
export class WorkflowStepperComponent {
  @Input() steps: WorkflowStepperStep[] = [];
  @Input() activeIndex = 0;
  @Input() compact = false;
  @Input() ariaLabel = '流程步骤';

  protected stateFor(index: number, step: WorkflowStepperStep): WorkflowStepperState {
    if (step.state) {
      return step.state;
    }
    const active = this.clampedActiveIndex();
    if (index < active) {
      return 'complete';
    }
    if (index === active) {
      return 'active';
    }
    return 'pending';
  }

  protected toneClass(step: WorkflowStepperStep): string {
    return `tone-${step.tone || 'default'}`;
  }

  private clampedActiveIndex(): number {
    if (!this.steps.length) {
      return 0;
    }
    return Math.min(Math.max(0, Math.trunc(this.activeIndex || 0)), this.steps.length - 1);
  }
}
