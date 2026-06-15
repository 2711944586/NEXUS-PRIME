import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ProgressBarModule } from 'primeng/progressbar';

import { ManufacturingCommandCenter } from '../core/models';
import type { WorkflowBlueprint, WorkflowStage } from '../core/workflow-blueprints';
import { ShiftHandoffAction, WorkflowEvidenceTile, WorkflowSignal } from './app-shell.models';

@Component({
  selector: 'app-context-panel',
  standalone: true,
  host: { style: 'display: contents' },
  imports: [CommonModule, RouterLink, ProgressBarModule],
  template: `
    <aside class="atlas-context-panel" aria-label="运营上下文">
      <section class="context-block live">
        <span>链路健康</span>
        <strong>{{ shellHealth }}%</strong>
        <p-progressbar [value]="shellHealth" [showValue]="false" />
      </section>

      <section class="context-block">
        <div class="context-title">
          <span>风险队列</span>
          <em>{{ shellRisks.length }} / {{ totalRiskCount }}</em>
        </div>
        @if (shellRisks.length) {
          @for (risk of shellRisks; track risk.title + risk.type) {
            <a class="context-risk" [class.critical]="risk.level === 'critical'" [routerLink]="riskPath(risk)">
              <i></i>
              <span>{{ risk.type }}</span>
              <strong>{{ risk.title }}</strong>
            </a>
          }
        } @else {
          <div class="context-risk info">
            <i></i>
            <span>风险队列</span>
            <strong>当前没有阻塞任务</strong>
          </div>
        }
      </section>

      <section class="context-block compact-ledger">
        <div><span>库存</span><strong>{{ stockQuantityLabel }}</strong></div>
        <div><span>采购</span><strong>{{ pendingPurchase }}</strong></div>
        <div><span>逾期</span><strong>{{ overdueAmountLabel }}</strong></div>
      </section>

      <section class="context-block workflow-signal-block">
        <div class="context-title">
          <span>执行信号</span>
          <em>{{ currentWorkflow.title }}</em>
        </div>
        <div class="workflow-signal-list" aria-label="当前业务执行信号">
          @for (signal of workflowSignals; track signal.label) {
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
      </section>

      <section class="context-block workflow-context-block">
        <div class="context-title">
          <span>当前闭环</span>
          <em>{{ activeWorkflowStep.label }}</em>
        </div>
        <figure class="context-workflow-photo">
          <img [src]="currentWorkflow.photo.src" [alt]="currentWorkflow.photo.alt" />
          <figcaption>
            <span>{{ currentWorkflow.photo.label }}</span>
            <strong>{{ currentWorkflow.photo.caption }}</strong>
          </figcaption>
        </figure>
        <p>{{ currentWorkflow.summary }}</p>
        <div class="workflow-step-rail" aria-label="业务闭环节点">
          @for (stage of currentWorkflow.stages; track stage.key) {
            <a
              [routerLink]="stage.path"
              [class.active]="stage.key === activeWorkflowStep.key"
              [class.warning]="stage.tone === 'warning'"
              [class.danger]="stage.tone === 'danger'"
              [class.success]="stage.tone === 'success'"
            >
              <span>{{ stage.label }}</span>
              <strong>{{ stage.metric }}</strong>
            </a>
          }
        </div>
      </section>

      <section class="context-block field-evidence-block">
        <div class="context-title">
          <span>现场证据</span>
          <em>{{ workflowEvidenceTiles.length }} 张</em>
        </div>
        <div class="field-evidence-grid" aria-label="当前闭环现场证据">
          @for (tile of workflowEvidenceTiles; track tile.photo.src + tile.stage.key) {
            <a [routerLink]="tile.stage.path">
              <img [src]="tile.photo.src" [alt]="tile.photo.alt" loading="eager" decoding="async" />
              <span>{{ tile.photo.label }}</span>
              <strong>{{ tile.stage.label }} · {{ tile.stage.metric }}</strong>
            </a>
          }
        </div>
        <div class="evidence-ledger" aria-label="系统规模摘要">
          <span><strong>{{ moduleEntryCount }}</strong><em>模块入口</em></span>
          <span><strong>{{ visualAssetCount }}</strong><em>现场图片</em></span>
          <span><strong>{{ currentWorkflow.stages.length }}</strong><em>闭环节点</em></span>
        </div>
      </section>

      <section class="context-block shift-handoff-block">
        <div class="context-title">
          <span>当班交接</span>
          <em>{{ todayText }}</em>
        </div>
        <div class="shift-handoff-list" aria-label="当班交接动作">
          @for (action of shiftHandoffActions; track action.path + action.label) {
            <a
              [routerLink]="action.path"
              [class.warning]="action.tone === 'warning'"
              [class.danger]="action.tone === 'danger'"
              [class.success]="action.tone === 'success'"
              [class.info]="action.tone === 'info'"
            >
              <span>
                <b>{{ action.priority }}</b>
                <em>{{ action.owner }} · {{ action.due }}</em>
              </span>
              <strong>{{ action.label }}</strong>
              <small>{{ action.metric }} · {{ action.evidence }}</small>
            </a>
          }
        </div>
      </section>

      <section class="context-block">
        <div class="context-title">
          <span>下一步</span>
          <em>工作流</em>
        </div>
        @for (stage of nextWorkflowSteps; track stage.key) {
          <a class="context-action" [routerLink]="stage.path">{{ stage.label }} · {{ stage.metric }}</a>
        }
      </section>
    </aside>
  `
})
export class AppContextPanelComponent {
  @Input({ required: true }) currentWorkflow!: WorkflowBlueprint;
  @Input({ required: true }) activeWorkflowStep!: WorkflowStage;
  @Input() shellHealth = 0;
  @Input() shellRisks: ManufacturingCommandCenter['risks'] = [];
  @Input() totalRiskCount = 0;
  @Input() stockQuantityLabel = '0';
  @Input() pendingPurchase = 0;
  @Input() overdueAmountLabel = '¥0';
  @Input() workflowSignals: WorkflowSignal[] = [];
  @Input() workflowEvidenceTiles: WorkflowEvidenceTile[] = [];
  @Input() shiftHandoffActions: ShiftHandoffAction[] = [];
  @Input() nextWorkflowSteps: WorkflowStage[] = [];
  @Input() moduleEntryCount = 0;
  @Input() visualAssetCount = 0;
  @Input() todayText = '';
  @Input({ required: true }) riskPath!: (risk: ManufacturingCommandCenter['risks'][number]) => string;
}
