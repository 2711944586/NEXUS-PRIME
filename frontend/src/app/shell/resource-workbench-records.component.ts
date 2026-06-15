import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { SkeletonModule } from 'primeng/skeleton';
import { TooltipModule } from 'primeng/tooltip';

import { DataRecord, PageMeta } from '../core/models';
import { ResourceFieldConfig, ResourceWorkflowConfig } from '../core/resource-workflow';
import {
  displayTitle,
  emptyPageMeta,
  pageSummary as summarizePage,
  rowKey,
  valueText
} from './resource-workbench.utils';

@Component({
  selector: 'app-resource-workbench-records',
  standalone: true,
  imports: [CommonModule, RouterLink, ButtonModule, SkeletonModule, TooltipModule],
  template: `
    <div class="workbench-main">
      @if (!config.resource) {
        <p class="workbench-empty">当前页面是聚合看板，操作台以工作流任务和来源链接为主。</p>
      } @else if (loading) {
        <p-skeleton height="58px" />
        <p-skeleton height="58px" />
        <p-skeleton height="58px" />
      } @else if (!rows.length) {
        <div class="workbench-empty-state">
          <i class="pi pi-inbox"></i>
          <strong>{{ query.trim() ? '没有匹配记录' : '暂无可操作记录' }}</strong>
          <p>{{ emptyStateText(config) }}</p>
          <div class="workbench-empty-actions">
            @if (query.trim()) {
              <button pButton type="button" severity="secondary" [text]="true" (click)="clearSearch.emit()">
                <i class="pi pi-times"></i>
                清除筛选
              </button>
            }
            <button pButton type="button" severity="secondary" [text]="true" (click)="refresh.emit()">
              <i class="pi pi-refresh"></i>
              刷新
            </button>
            @if (canCreate(config)) {
              <button pButton type="button" (click)="create.emit()">
                <i class="pi pi-plus"></i>
                新建记录
              </button>
            }
          </div>
        </div>
      } @else {
        <div class="workbench-result-bar" aria-live="polite">
          <span>{{ pageSummary() }}</span>
          <div class="workbench-pager" aria-label="记录分页">
            <button type="button" (click)="previous.emit()" [disabled]="!pageMeta.has_prev || loading" aria-label="上一页">
              <i class="pi pi-angle-left"></i>
            </button>
            <button type="button" (click)="next.emit()" [disabled]="!pageMeta.has_next || loading" aria-label="下一页">
              <i class="pi pi-angle-right"></i>
            </button>
          </div>
        </div>
        @if (operationNote) {
          <div class="workbench-status-note" aria-live="polite">
            <i class="pi pi-check-circle"></i>
            <span>{{ operationNote }}</span>
          </div>
        }
        <div class="workbench-records" aria-label="当前模块记录">
          <div class="workbench-table-head" aria-hidden="true">
            <div class="workbench-column-labels">
              @for (column of visibleColumns(config); track column.key) {
                <span>{{ column.label }}</span>
              }
            </div>
            <em>操作</em>
          </div>
          @for (row of rows; track rowKey(row, $index)) {
            <article class="workbench-record" [class.active]="rowKey(row) === rowKey(selected)" [class.busy]="busyRecordKey === rowKey(row)">
              <button type="button" class="record-main" (click)="select.emit(row)" [attr.aria-label]="'选择 ' + displayTitle(row)">
                @for (column of visibleColumns(config); track column.key) {
                  <span
                    class="record-cell"
                    [class.cell-code]="$index === 0"
                    [class.cell-title]="$index === 1"
                    [class.cell-meta]="$index === 2"
                    [class.cell-value]="$index === 3"
                    [attr.data-label]="column.label"
                  >
                    @if ($index === 1) {
                      <strong>{{ valueText(row[column.key], column.type) }}</strong>
                    } @else if ($index === 3) {
                      <b>{{ valueText(row[column.key], column.type) }}</b>
                    } @else if ($index === 2) {
                      <em>{{ valueText(row[column.key], column.type) }}</em>
                    } @else {
                      <span>{{ valueText(row[column.key], column.type) }}</span>
                    }
                  </span>
                }
              </button>
              <div class="workbench-record-actions">
                <a
                  pButton
                  [text]="true"
                  size="small"
                  class="record-action-button"
                  [routerLink]="detailLink(row)"
                  [attr.aria-label]="'查看 ' + displayTitle(row)"
                  pTooltip="查看"
                  tooltipPosition="top"
                >
                  <i class="pi pi-eye"></i>
                </a>
                <button
                  pButton
                  type="button"
                  [text]="true"
                  size="small"
                  class="record-action-button"
                  (click)="edit.emit(row)"
                  [disabled]="!canEdit(config, row)"
                  [attr.aria-label]="'编辑 ' + displayTitle(row)"
                  [pTooltip]="editTooltip(config, row)"
                  tooltipPosition="top"
                >
                  <i class="pi pi-pencil"></i>
                </button>
                <button
                  pButton
                  type="button"
                  [text]="true"
                  size="small"
                  class="record-action-button"
                  severity="secondary"
                  (click)="clone.emit(row)"
                  [disabled]="!canCreate(config)"
                  [attr.aria-label]="'复制 ' + displayTitle(row)"
                  pTooltip="复制"
                  tooltipPosition="top"
                >
                  <i class="pi pi-copy"></i>
                </button>
                <button
                  pButton
                  type="button"
                  [text]="true"
                  size="small"
                  class="record-action-button"
                  severity="danger"
                  (click)="remove.emit(row)"
                  [disabled]="!canDelete(config, row)"
                  [loading]="busyRecordKey === rowKey(row)"
                  [attr.aria-label]="'删除 ' + displayTitle(row)"
                  pTooltip="删除"
                  tooltipPosition="top"
                >
                  <i class="pi pi-trash"></i>
                </button>
              </div>
            </article>
          }
        </div>
      }
    </div>
  `
})
export class ResourceWorkbenchRecordsComponent {
  @Input({ required: true }) config!: ResourceWorkflowConfig;
  @Input() loading = false;
  @Input() rows: DataRecord[] = [];
  @Input() pageMeta: PageMeta = emptyPageMeta(8);
  @Input() operationNote = '';
  @Input() query = '';
  @Input() selected: DataRecord | null = null;
  @Input() busyRecordKey = '';
  @Input() currentUrl = '';

  @Output() clearSearch = new EventEmitter<void>();
  @Output() refresh = new EventEmitter<void>();
  @Output() create = new EventEmitter<void>();
  @Output() previous = new EventEmitter<void>();
  @Output() next = new EventEmitter<void>();
  @Output() select = new EventEmitter<DataRecord>();
  @Output() edit = new EventEmitter<DataRecord>();
  @Output() clone = new EventEmitter<DataRecord>();
  @Output() remove = new EventEmitter<DataRecord>();

  protected readonly rowKey = rowKey;
  protected readonly displayTitle = displayTitle;
  protected readonly valueText = valueText;

  protected visibleColumns(config: ResourceWorkflowConfig): ResourceFieldConfig[] {
    return config.columns.slice(0, 4);
  }

  protected pageSummary(): string {
    return summarizePage(this.pageMeta, this.query);
  }

  protected detailLink(row: DataRecord | null): string {
    if (!this.config?.detailBase || !row?.id) {
      return this.currentUrl;
    }
    return `${this.config.detailBase}/${row.id}`;
  }

  protected canCreate(config: ResourceWorkflowConfig): boolean {
    return Boolean((config.createEndpoint || config.resource) && config.createFields.length);
  }

  protected canEdit(config: ResourceWorkflowConfig, row?: DataRecord | null): boolean {
    return Boolean(config.resource && config.editFields.length && row);
  }

  protected canDelete(config: ResourceWorkflowConfig, row?: DataRecord | null): boolean {
    return Boolean((config.deleteEndpoint || config.resource) && config.canDelete !== false && row?.id);
  }

  protected editTooltip(config: ResourceWorkflowConfig, row?: DataRecord | null): string {
    return this.canEdit(config, row) ? '编辑记录' : (config.readonlyReason || '当前记录不可直接编辑');
  }

  protected emptyStateText(config: ResourceWorkflowConfig): string {
    const trimmedQuery = this.query.trim();
    if (trimmedQuery) {
      return `没有找到包含「${trimmedQuery}」的记录。可以清除筛选、刷新数据，或在当前模块新建一条记录。`;
    }
    return config.emptyText || config.readonlyReason || '当前模块暂时没有记录。可以刷新数据，或从右侧流程动作进入对应业务入口。';
  }
}
