import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';

import type { WorkflowBlueprint, WorkflowStage } from '../core/workflow-blueprints';
import type { ShiftHandoffAction, WorkflowSignal } from './app-shell.models';

type LedgerEntry = {
  key: string;
  eyebrow: string;
  title: string;
  value: string;
  detail: string;
  path: string;
  tone?: string;
};

@Component({
  selector: 'app-operations-execution-ledger',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="operations-execution-ledger atlas-panel" aria-label="当前页面业务执行账本">
      <div class="execution-ledger-head">
        <div>
          <span class="atlas-kicker">执行账本</span>
          <h2>{{ workflow.title }}作业面</h2>
        </div>
        <p>{{ activeStage.label }} · {{ activeStage.metric }} · {{ entries.length }} 个可追踪入口</p>
      </div>

      <div class="execution-ledger-grid">
        @for (entry of entries; track entry.key) {
          <a
            class="business-data-row execution-ledger-row"
            [routerLink]="entry.path"
            [class.warning]="entry.tone === 'warning'"
            [class.danger]="entry.tone === 'danger'"
            [class.success]="entry.tone === 'success'"
          >
            <span>{{ entry.eyebrow }}</span>
            <strong>{{ entry.title }}</strong>
            <b>{{ entry.value }}</b>
            <em>{{ entry.detail }}</em>
          </a>
        }
      </div>
    </section>
  `
})
export class OperationsExecutionLedgerComponent {
  @Input({ required: true }) workflow!: WorkflowBlueprint;
  @Input({ required: true }) activeStage!: WorkflowStage;
  @Input() signals: WorkflowSignal[] = [];
  @Input() nextStages: WorkflowStage[] = [];
  @Input() handoffActions: ShiftHandoffAction[] = [];
  @Input() riskCount = 0;

  protected get entries(): LedgerEntry[] {
    const seen = new Set<string>();
    const entries: LedgerEntry[] = [];
    const push = (entry: LedgerEntry): void => {
      const key = `${entry.path}:${entry.title}`;
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      entries.push(entry);
    };

    for (const signal of this.signals) {
      push({
        key: `signal:${signal.path}:${signal.label}`,
        eyebrow: signal.label,
        title: signal.caption,
        value: String(signal.value),
        detail: '来自经营指挥中心的实时信号',
        path: signal.path,
        tone: signal.tone
      });
    }

    for (const action of this.handoffActions) {
      push({
        key: `handoff:${action.path}:${action.label}`,
        eyebrow: `${action.priority} / ${action.owner}`,
        title: action.label,
        value: action.metric,
        detail: `${action.due} 进入下一环节`,
        path: action.path,
        tone: action.tone
      });
    }

    for (const stage of this.workflow.stages) {
      push({
        key: `stage:${stage.key}`,
        eyebrow: stage.label,
        title: `${stage.label} · ${stage.metric}`,
        value: stage.metric,
        detail: stage.key === this.activeStage.key ? '当前页面节点' : this.workflow.summary,
        path: stage.path,
        tone: stage.tone
      });
    }

    for (const stage of this.nextStages) {
      push({
        key: `next:${stage.key}`,
        eyebrow: '下一节点',
        title: stage.label,
        value: stage.metric,
        detail: '承接当前作业结果继续推进',
        path: stage.path,
        tone: stage.tone
      });
    }

    push({
      key: 'audit:reports',
      eyebrow: '归档',
      title: '经营报表与审计追踪',
      value: this.riskCount ? `${this.riskCount} 风险` : '稳定',
      detail: '把当前作业结果沉淀为报表、文件和审计链',
      path: '/app/reports',
      tone: this.riskCount ? 'warning' : 'success'
    });

    return entries.slice(0, 10);
  }
}
