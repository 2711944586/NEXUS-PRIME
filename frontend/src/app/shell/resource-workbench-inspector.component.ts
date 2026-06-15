import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';

import { DataRecord } from '../core/models';
import { ResourceFieldConfig, ResourceWorkflowAction, ResourceWorkflowConfig } from '../core/resource-workflow';
import { LookupOption, displayTitle, valueText } from './resource-workbench.utils';

export type ResourceWorkbenchMode = 'inspect' | 'edit' | 'create' | 'workflow';

export interface ResourceWorkbenchFieldChange {
  field: ResourceFieldConfig;
  value: unknown;
}

@Component({
  selector: 'app-resource-workbench-inspector',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, ButtonModule],
  template: `
    <aside class="workbench-inspector" aria-label="记录检查器">
      <div class="workbench-inspector-head">
        <div class="workbench-title">
          <span>{{ modeLabel() }}</span>
          <strong>{{ inspectorTitle() }}</strong>
          <p>{{ inspectorSubtitle() }}</p>
        </div>
        <div class="mode-tabs" aria-label="操作台视图">
          <button type="button" [class.active]="mode === 'inspect'" (click)="modeChange.emit('inspect')">查看</button>
          <button type="button" [class.active]="mode === 'edit' || mode === 'create'" (click)="edit.emit()" [disabled]="!canEdit()">编辑</button>
          <button type="button" [class.active]="mode === 'workflow'" (click)="modeChange.emit('workflow')">流程</button>
        </div>
      </div>

      @if (mode === 'edit' || mode === 'create') {
        <form class="workbench-form" (ngSubmit)="save.emit()">
          @for (field of activeFields; track field.key) {
            <label>
              <span>{{ field.label }}</span>
              @if (field.type === 'textarea') {
                <textarea [ngModel]="formValue(field.key)" (ngModelChange)="fieldChange.emit({ field, value: $event })" [name]="field.key" [attr.name]="field.key" [placeholder]="field.placeholder || field.label"></textarea>
              } @else if (field.type === 'select' || field.type === 'lookup') {
                <select
                  [ngModel]="formValue(field.key)"
                  (ngModelChange)="fieldChange.emit({ field, value: $event })"
                  [name]="field.key"
                  [attr.name]="field.key"
                  [required]="field.required || false"
                >
                  <option [ngValue]="''" [disabled]="field.required || false">{{ field.placeholder || '请选择' }}</option>
                  @for (option of fieldOptions(field); track option.value) {
                    <option [ngValue]="option.value">{{ option.label }}</option>
                  }
                </select>
                @if (field.type === 'lookup' && !fieldOptions(field).length) {
                  <small class="field-helper">暂无可选数据，请先确认基础资料或刷新操作台。</small>
                }
              } @else {
                <input
                  [type]="field.type === 'number' ? 'number' : field.type === 'date' ? 'date' : 'text'"
                  [ngModel]="formValue(field.key)"
                  (ngModelChange)="fieldChange.emit({ field, value: $event })"
                  [name]="field.key"
                  [attr.name]="field.key"
                  [placeholder]="field.placeholder || field.label"
                  [attr.min]="field.min ?? null"
                  [attr.step]="field.step ?? null"
                  [required]="field.required || false"
                />
              }
              @if (fieldError(field.key); as message) {
                <small class="field-error">{{ message }}</small>
              }
            </label>
          }
          <div class="workbench-form-actions">
            <button pButton type="button" severity="secondary" [text]="true" (click)="cancel.emit()">取消</button>
            <button pButton type="submit" [loading]="saving">
              <i class="pi pi-save"></i>
              保存
            </button>
          </div>
        </form>
      } @else if (mode === 'workflow') {
        <div class="workflow-stack">
          @for (step of config.workflowSteps; track step.label) {
            <article class="workflow-step" [class]="step.tone || 'default'">
              <i>{{ $index + 1 }}</i>
              <div>
                <strong>{{ step.label }}</strong>
                <p>{{ step.detail }}</p>
                @if (step.path) {
                  <a [routerLink]="step.path">进入页面</a>
                }
              </div>
            </article>
          }
        </div>
        <div class="workflow-actions">
          @for (action of config.actions; track action.label) {
            <button type="button" class="workflow-action" [class]="action.tone || 'default'" (click)="runAction.emit(action)" [disabled]="actionDisabled(action)" [attr.aria-label]="action.label">
              <i class="pi" [class]="action.icon"></i>
              <span>
                <strong>{{ actionRunning === action.label ? '执行中...' : action.label }}</strong>
                <span>{{ action.description }}</span>
              </span>
            </button>
          }
        </div>
        @if (config.readonlyReason) {
          <p class="readonly-note">{{ config.readonlyReason }}</p>
        }
      } @else {
        @if (selected; as row) {
          <div class="field-grid">
            @for (field of config.columns; track field.key) {
              <div class="field-row">
                <span class="field-label">{{ field.label }}</span>
                <strong class="field-value">{{ valueText(row[field.key], field.type) }}</strong>
              </div>
            }
          </div>
        } @else {
          <p class="workbench-empty">选择一条记录后，可在这里查看关键字段、编辑和执行流程动作。</p>
        }
        @if (config.readonlyReason) {
          <p class="readonly-note">{{ config.readonlyReason }}</p>
        }
      }
    </aside>
  `
})
export class ResourceWorkbenchInspectorComponent {
  @Input({ required: true }) config!: ResourceWorkflowConfig;
  @Input() mode: ResourceWorkbenchMode = 'inspect';
  @Input() selected: DataRecord | null = null;
  @Input() activeFields: ResourceFieldConfig[] = [];
  @Input() form: Record<string, unknown> = {};
  @Input() formErrors: Record<string, string> = {};
  @Input() lookupOptions: Record<string, LookupOption[]> = {};
  @Input() saving = false;
  @Input() actionRunning = '';

  @Output() modeChange = new EventEmitter<ResourceWorkbenchMode>();
  @Output() edit = new EventEmitter<void>();
  @Output() fieldChange = new EventEmitter<ResourceWorkbenchFieldChange>();
  @Output() save = new EventEmitter<void>();
  @Output() cancel = new EventEmitter<void>();
  @Output() runAction = new EventEmitter<ResourceWorkflowAction>();

  protected readonly valueText = valueText;

  protected canEdit(): boolean {
    return Boolean(this.config.resource && this.config.editFields.length && this.selected);
  }

  protected actionDisabled(action: ResourceWorkflowAction): boolean {
    return Boolean(this.actionRunning || (action.requiresRecord && !this.selected?.id));
  }

  protected formValue(key: string): unknown {
    return this.form[key] ?? '';
  }

  protected fieldOptions(field: ResourceFieldConfig): LookupOption[] {
    return field.options ?? this.lookupOptions[field.key] ?? [];
  }

  protected fieldError(key: string): string {
    return this.formErrors[key] ?? '';
  }

  protected modeLabel(): string {
    if (this.mode === 'create') {
      return '创建记录';
    }
    if (this.mode === 'edit') {
      return '编辑记录';
    }
    if (this.mode === 'workflow') {
      return '工作流准备';
    }
    return '记录查看';
  }

  protected inspectorTitle(): string {
    if (this.mode === 'create') {
      return `新建${this.config.title}`;
    }
    return displayTitle(this.selected);
  }

  protected inspectorSubtitle(): string {
    if (this.mode === 'workflow') {
      return `${this.config.workflowSteps.length} 个步骤 · ${this.config.actions.length} 个动作`;
    }
    return this.selected?.id ? `记录 ID ${this.selected.id}` : (this.config.readonlyReason || '选择记录或进入流程动作。');
  }
}
