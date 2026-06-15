import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NavigationEnd, Router } from '@angular/router';
import { ConfirmationService, MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TooltipModule } from 'primeng/tooltip';
import { Observable, Subscription, catchError, filter, finalize, forkJoin, map, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { apiUrl } from '../core/api-url';
import { DataRecord, PageMeta, PageResult } from '../core/models';
import {
  ResourceFieldConfig,
  ResourceWorkflowAction,
  ResourceWorkflowConfig,
  resourceConfigForUrl
} from '../core/resource-workflow';
import { emptyPageResult } from '../pages/page-utils';
import {
  ResourceWorkbenchFieldChange,
  ResourceWorkbenchInspectorComponent,
  ResourceWorkbenchMode
} from './resource-workbench-inspector.component';
import { ResourceWorkbenchRecordsComponent } from './resource-workbench-records.component';
import {
  LookupOption,
  defaultForm,
  displayTitle,
  emptyPageMeta,
  errorDetail,
  formFromRecord,
  normalizedForm,
  pageSummary as summarizePage,
  rowKey,
  toLookupOption,
  validateForm
} from './resource-workbench.utils';

@Component({
  selector: 'app-resource-workbench',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule, InputTextModule, TooltipModule, ResourceWorkbenchInspectorComponent, ResourceWorkbenchRecordsComponent],
  host: { class: 'resource-workbench-host' },
  template: `
    @if (config(); as cfg) {
      <section class="module-workbench" aria-label="当前模块操作台">
        <div class="workbench-head">
          <div class="workbench-title">
            <span>{{ cfg.eyebrow }}</span>
            <strong>{{ cfg.title }}操作台</strong>
            <p>{{ workbenchSummary() }}</p>
          </div>

          <div class="workbench-toolbar">
            <label class="workbench-search">
              <i class="pi pi-search"></i>
              <input
                pInputText
                [(ngModel)]="query"
                [placeholder]="cfg.searchPlaceholder"
                (keydown.enter)="searchRecords()"
                aria-label="搜索当前模块记录"
              />
            </label>
            <button pButton type="button" severity="secondary" [text]="true" (click)="searchRecords()" [disabled]="!cfg.resource" aria-label="查询当前模块">
              <i class="pi pi-search"></i>
              查询
            </button>
            <button pButton type="button" severity="secondary" [text]="true" (click)="load(true)" [loading]="loading()" aria-label="刷新当前模块">
              <i class="pi pi-refresh"></i>
            </button>
            <button pButton type="button" (click)="startCreate()" [disabled]="!canCreate(cfg)" aria-label="新建当前模块记录" [pTooltip]="createTooltip(cfg)">
              <i class="pi pi-plus"></i>
              新建
            </button>
            @if (cfg.exportable && cfg.resource) {
              <button pButton type="button" severity="secondary" [text]="true" (click)="exportResource('excel')" aria-label="导出当前模块">
                <i class="pi pi-download"></i>
                导出
              </button>
            }
          </div>
        </div>

        <div class="workbench-capability-strip" aria-label="模块能力状态">
          @for (item of capabilityCards(cfg); track item.label) {
            <div class="workbench-capability">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <em>{{ item.detail }}</em>
            </div>
          }
        </div>

        <app-resource-workbench-records
          [config]="cfg"
          [loading]="loading()"
          [rows]="rows()"
          [pageMeta]="pageMeta()"
          [operationNote]="operationNote()"
          [query]="query"
          [selected]="selected()"
          [busyRecordKey]="busyRecordKey()"
          [currentUrl]="currentUrl()"
          (clearSearch)="clearSearch()"
          (refresh)="load(true)"
          (create)="startCreate()"
          (previous)="previousPage()"
          (next)="nextPage()"
          (select)="select($event)"
          (edit)="startEdit($event)"
          (clone)="cloneRecord($event)"
          (remove)="deleteRecord($event)"
        />

        <app-resource-workbench-inspector
          [config]="cfg"
          [mode]="mode()"
          [selected]="selected()"
          [activeFields]="activeFields()"
          [form]="form()"
          [formErrors]="formErrors()"
          [lookupOptions]="lookupOptions()"
          [saving]="saving()"
          [actionRunning]="actionRunning()"
          (modeChange)="mode.set($event)"
          (edit)="startEdit(selected())"
          (fieldChange)="setFormField($event)"
          (save)="saveForm()"
          (cancel)="cancelForm()"
          (runAction)="runAction($event)"
        />
      </section>
    }
  `
})
export class ResourceWorkbenchComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly messages = inject(MessageService);
  private readonly confirm = inject(ConfirmationService);
  private routerSub?: Subscription;

  protected readonly currentUrl = signal('');
  protected readonly config = signal<ResourceWorkflowConfig | null>(null);
  protected readonly rows = signal<DataRecord[]>([]);
  protected readonly page = signal(1);
  protected readonly pageMeta = signal<PageMeta>(emptyPageMeta(8));
  protected readonly selected = signal<DataRecord | null>(null);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly busyRecordKey = signal('');
  protected readonly actionRunning = signal('');
  protected readonly operationNote = signal('');
  protected readonly mode = signal<ResourceWorkbenchMode>('inspect');
  protected readonly form = signal<Record<string, unknown>>({});
  protected readonly formErrors = signal<Record<string, string>>({});
  protected readonly lookupOptions = signal<Record<string, LookupOption[]>>({});
  protected readonly rowKey = rowKey;
  protected readonly displayTitle = displayTitle;
  protected query = '';

  protected readonly activeFields = computed(() => {
    const cfg = this.config();
    if (!cfg) {
      return [];
    }
    return this.mode() === 'create' ? cfg.createFields : cfg.editFields;
  });

  protected readonly workbenchSummary = computed(() => {
    const cfg = this.config();
    if (!cfg?.resource) {
      return '聚合看板页面已接入任务、来源和流程入口。';
    }
    const writable = cfg.editFields.length ? '可编辑' : '领域动作维护';
    const creatable = this.canCreate(cfg) ? '可新建' : '流程新建';
    return `${this.rows().length} 条最近记录 · ${creatable} · ${writable} · ${cfg.exportable ? '可导出' : '流程归档'}`;
  });

  protected capabilityCards(cfg: ResourceWorkflowConfig): Array<{ label: string; value: string; detail: string }> {
    const total = this.pageMeta().total || this.rows().length;
    const createState = this.canCreate(cfg) ? '新建可用' : '流程创建';
    const editState = cfg.editFields.length ? '字段可维护' : '动作维护';
    const deleteState = cfg.canDelete === false ? '只读保留' : cfg.deleteEndpoint || cfg.resource ? '可审计删除' : '不可删除';
    const actionCount = cfg.actions.length;
    return [
      {
        label: '数据对象',
        value: cfg.resource ? `${total} 条` : '聚合看板',
        detail: cfg.resource ? `${this.pageSummary()}` : '以流程入口和责任动作组织'
      },
      {
        label: '写入能力',
        value: `${createState} / ${editState}`,
        detail: deleteState
      },
      {
        label: '业务流程',
        value: `${cfg.workflowSteps.length} 步 / ${actionCount} 动作`,
        detail: cfg.workflowSteps.map(step => step.label).slice(0, 3).join(' -> ') || '页面级流程'
      },
      {
        label: '当前焦点',
        value: this.modeLabel(),
        detail: this.selected()?.id ? `记录 ${this.selected()?.id}` : (cfg.readonlyReason || '选择记录后推进')
      }
    ];
  }

  ngOnInit(): void {
    this.syncRoute(this.router.url);
    this.routerSub = this.router.events
      .pipe(filter(event => event instanceof NavigationEnd))
      .subscribe(event => this.syncRoute((event as NavigationEnd).urlAfterRedirects));
  }

  ngOnDestroy(): void {
    this.routerSub?.unsubscribe();
  }

  protected load(force = false): void {
    const cfg = this.config();
    if (!cfg?.resource) {
      this.rows.set([]);
      this.selected.set(null);
      return;
    }
    if (this.loading() && !force) {
      return;
    }
    this.loading.set(true);
    this.api.list<DataRecord>(cfg.resource, { page: this.page(), page_size: 8, q: this.query }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '操作台未加载', detail: errorDetail(error, `${cfg.title}数据暂不可用。`) });
        return of(emptyPageResult<DataRecord>(8) as PageResult<DataRecord>);
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(result => {
      this.rows.set(result.items);
      this.pageMeta.set(result.pagination ?? emptyPageMeta(8));
      const current = this.selected();
      const next = current ? result.items.find(row => this.rowKey(row) === this.rowKey(current)) : result.items[0];
      this.selected.set(next ?? result.items[0] ?? null);
      if (!this.selected()) {
        this.mode.set('workflow');
      }
    });
  }

  protected searchRecords(): void {
    this.page.set(1);
    this.operationNote.set('');
    this.load(true);
  }

  protected nextPage(): void {
    if (!this.pageMeta().has_next || this.loading()) {
      return;
    }
    this.page.set(this.page() + 1);
    this.load(true);
  }

  protected clearSearch(): void {
    this.query = '';
    this.page.set(1);
    this.operationNote.set('');
    this.load(true);
  }

  protected previousPage(): void {
    if (!this.pageMeta().has_prev || this.loading()) {
      return;
    }
    this.page.set(Math.max(1, this.page() - 1));
    this.load(true);
  }

  protected select(row: DataRecord): void {
    this.selected.set(row);
    if (this.mode() === 'create' || this.mode() === 'edit') {
      this.mode.set('inspect');
    }
  }

  protected startCreate(): void {
    const cfg = this.config();
    if (!cfg || !this.canCreate(cfg)) {
      this.messages.add({ severity: 'info', summary: '需要领域流程', detail: cfg?.readonlyReason || '该模块通过专用流程创建。' });
      return;
    }
    this.form.set(defaultForm(cfg.createFields, this.lookupOptions()));
    this.formErrors.set({});
    this.operationNote.set('');
    this.lookupOptions.set({});
    this.selected.set(null);
    this.mode.set('create');
    this.loadFieldLookups(cfg.createFields, true);
  }

  protected startEdit(row: DataRecord | null): void {
    const cfg = this.config();
    const target = row ?? this.selected();
    if (!cfg || !target || !this.canEdit(cfg)) {
      this.messages.add({ severity: 'info', summary: '暂不可编辑', detail: cfg?.readonlyReason || '请选择可编辑记录。' });
      return;
    }
    this.selected.set(target);
    this.form.set(formFromRecord(target, cfg.editFields, this.lookupOptions()));
    this.formErrors.set({});
    this.operationNote.set('');
    this.mode.set('edit');
    this.loadFieldLookups(cfg.editFields, false);
  }

  protected cloneRecord(row: DataRecord): void {
    const cfg = this.config();
    if (!cfg || !this.canCreate(cfg)) {
      this.messages.add({ severity: 'info', summary: '不能复制创建', detail: cfg?.readonlyReason || '该模块通过领域流程创建。' });
      return;
    }
    const form = formFromRecord(row, cfg.createFields, this.lookupOptions());
    if (typeof form['sku'] === 'string') {
      form['sku'] = `${form['sku']}-COPY`;
    }
    if (typeof form['name'] === 'string') {
      form['name'] = `${form['name']} 副本`;
    }
    if (typeof form['title'] === 'string') {
      form['title'] = `${form['title']} 副本`;
    }
    this.form.set(form);
    this.formErrors.set({});
    this.operationNote.set('');
    this.selected.set(null);
    this.mode.set('create');
    this.loadFieldLookups(cfg.createFields, true);
  }

  protected saveForm(): void {
    const cfg = this.config();
    const form = this.form();
    if (!cfg?.resource || !this.activeFields().length) {
      return;
    }
    const validation = validateForm(cfg, this.activeFields(), form);
    this.formErrors.set(validation.errors);
    if (validation.message) {
      this.messages.add({ severity: 'warn', summary: '表单未完成', detail: validation.message });
      return;
    }
    if (this.mode() === 'edit' && !this.selected()?.id) {
      this.messages.add({ severity: 'warn', summary: '请选择记录', detail: '选择一条记录后再保存编辑。' });
      return;
    }
    const sanitizedForm = normalizedForm(this.activeFields(), form);
    const payload = this.mode() === 'create'
      ? (cfg.toCreatePayload ? cfg.toCreatePayload(sanitizedForm) : sanitizedForm)
      : (cfg.toUpdatePayload ? cfg.toUpdatePayload(sanitizedForm) : sanitizedForm);
    const request = this.mode() === 'create'
      ? this.api.post<DataRecord>(cfg.createEndpoint || cfg.resource, payload)
      : this.api.patch<DataRecord>(`${cfg.updateEndpoint || cfg.resource}/${this.selected()?.id}`, payload);
    this.saving.set(true);
    request.pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '保存未完成', detail: errorDetail(error, '记录未写入，请检查权限或字段。') });
        return of(null);
      }),
      finalize(() => this.saving.set(false))
    ).subscribe(result => {
      if (!result) {
        return;
      }
      this.messages.add({ severity: 'success', summary: this.mode() === 'create' ? '记录已创建' : '记录已更新', detail: this.displayTitle(result) });
      this.operationNote.set(`${this.mode() === 'create' ? '已创建' : '已更新'}：${this.displayTitle(result)}`);
      this.selected.set(result);
      this.mode.set('inspect');
      this.load(true);
    });
  }

  protected cancelForm(): void {
    this.mode.set(this.selected() ? 'inspect' : 'workflow');
    this.form.set({});
    this.formErrors.set({});
  }

  protected deleteRecord(row: DataRecord): void {
    const cfg = this.config();
    if (!cfg?.resource || !row.id || !this.canDelete(cfg, row)) {
      return;
    }
    this.confirm.confirm({
      header: '删除记录',
      message: `确认删除「${this.displayTitle(row)}」？该动作会写入审计。`,
      acceptLabel: '删除',
      rejectLabel: '取消',
      acceptButtonStyleClass: 'p-button-danger',
      accept: () => {
        this.busyRecordKey.set(this.rowKey(row));
        this.api.delete(`${cfg.deleteEndpoint || cfg.resource}/${row.id}`).pipe(
          catchError(error => {
            this.messages.add({ severity: 'warn', summary: '删除未完成', detail: errorDetail(error, '记录未删除，请检查权限。') });
            return of(null);
          }),
          finalize(() => this.busyRecordKey.set(''))
        ).subscribe(result => {
          if (result !== null) {
            this.messages.add({ severity: 'success', summary: '记录已删除', detail: this.displayTitle(row) });
            this.operationNote.set(`已删除：${this.displayTitle(row)}`);
            if (this.rows().length === 1 && this.page() > 1) {
              this.page.set(this.page() - 1);
            }
            this.load(true);
          }
        });
      }
    });
  }

  protected runAction(action: ResourceWorkflowAction): void {
    const record = this.selected();
    if (action.path) {
      this.router.navigateByUrl(action.path);
      return;
    }
    if (action.requiresRecord && !record?.id) {
      this.messages.add({ severity: 'info', summary: action.label, detail: '请先选择一条记录。' });
      return;
    }
    if (!action.endpoint) {
      return;
    }
    if (this.actionRunning()) {
      return;
    }
    const endpoint = action.endpoint.replace(':id', String(record?.id ?? ''));
    const body = action.body ? action.body(record) : {};
    const request = action.method === 'PATCH'
      ? this.api.patch(endpoint, body)
      : action.method === 'PUT'
        ? this.api.put(endpoint, body)
        : action.method === 'DELETE'
          ? this.api.delete(endpoint)
          : this.api.post(endpoint, body);
    this.actionRunning.set(action.label);
    request.pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: `${action.label}未完成`, detail: errorDetail(error, '业务状态不满足执行条件。') });
        return of(null);
      }),
      finalize(() => this.actionRunning.set(''))
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: action.label, detail: '流程动作已执行，操作台已刷新。' });
        this.operationNote.set(`已执行：${action.label}`);
        this.load(true);
      }
    });
  }

  protected exportResource(format: 'csv' | 'excel' | 'pdf'): void {
    const cfg = this.config();
    if (!cfg?.resource) {
      return;
    }
    const resource = cfg.resource.split('/').pop() || cfg.resource;
    window.open(apiUrl(`export/${resource}/${format}`), '_blank', 'noopener,noreferrer');
  }

  protected canCreate(cfg: ResourceWorkflowConfig): boolean {
    return Boolean((cfg.createEndpoint || cfg.resource) && cfg.createFields.length);
  }

  protected canEdit(cfg: ResourceWorkflowConfig, row?: DataRecord | null): boolean {
    return Boolean(cfg.resource && cfg.editFields.length && (row ?? this.selected()));
  }

  protected canDelete(cfg: ResourceWorkflowConfig, row?: DataRecord | null): boolean {
    return Boolean((cfg.deleteEndpoint || cfg.resource) && cfg.canDelete !== false && (row ?? this.selected())?.id);
  }

  protected createTooltip(cfg: ResourceWorkflowConfig): string {
    return this.canCreate(cfg) ? '新建记录' : (cfg.readonlyReason || '请通过领域流程创建');
  }

  protected setFormField(change: ResourceWorkbenchFieldChange): void {
    const { field, value } = change;
    const next = { ...this.form() };
    next[field.key] = field.type === 'number' && value !== '' ? Number(value) : value;
    if (field.key === 'product_id' && value) {
      const options: LookupOption[] = this.lookupOptions()[field.key] ?? [];
      const option = options.find(item => String(item.value) === String(value));
      const price = option?.meta?.cost ?? option?.meta?.price;
      if (price !== undefined && price !== null && (!next['unit_price'] || Number(next['unit_price']) <= 1)) {
        next['unit_price'] = Number(price) || 1;
      }
    }
    this.form.set(next);
    if (this.formErrors()[field.key]) {
      const errors = { ...this.formErrors() };
      delete errors[field.key];
      this.formErrors.set(errors);
    }
  }

  protected modeLabel(): string {
    if (this.mode() === 'create') {
      return '创建记录';
    }
    if (this.mode() === 'edit') {
      return '编辑记录';
    }
    if (this.mode() === 'workflow') {
      return '工作流准备';
    }
    return '记录查看';
  }

  protected pageSummary(): string {
    return summarizePage(this.pageMeta(), this.query);
  }

  private syncRoute(url: string): void {
    this.currentUrl.set(url);
    const cfg = resourceConfigForUrl(url);
    this.config.set(cfg);
    this.query = '';
    this.page.set(1);
    this.pageMeta.set(emptyPageMeta(8));
    this.mode.set('inspect');
    this.form.set({});
    this.formErrors.set({});
    this.lookupOptions.set({});
    this.operationNote.set('');
    this.busyRecordKey.set('');
    this.actionRunning.set('');
    this.selected.set(null);
    this.rows.set([]);
    this.load(true);
  }

  private loadFieldLookups(fields: ResourceFieldConfig[], applyDefaults: boolean): void {
    const lookupFields = fields.filter(field => field.lookup);
    if (!lookupFields.length) {
      if (applyDefaults) {
        this.applyDefaults(fields);
      }
      return;
    }
    const requests = lookupFields.reduce<Record<string, Observable<LookupOption[]>>>((acc, field) => {
      acc[field.key] = this.api.lookup(field.lookup?.path ?? '', field.lookup?.params).pipe(
        map(items => items.map(item => toLookupOption(item))),
        catchError(error => {
          this.messages.add({ severity: 'warn', summary: '选项未加载', detail: errorDetail(error, `${field.label}选项暂不可用。`) });
          return of([]);
        })
      );
      return acc;
    }, {});
    forkJoin(requests).subscribe(options => {
      this.lookupOptions.set({ ...this.lookupOptions(), ...options });
      if (applyDefaults) {
        this.applyDefaults(fields);
      }
    });
  }

  private applyDefaults(fields: ResourceFieldConfig[]): void {
    const current = { ...this.form() };
    const defaults = defaultForm(fields, this.lookupOptions());
    for (const field of fields) {
      if (current[field.key] === undefined || current[field.key] === null || current[field.key] === '') {
        current[field.key] = defaults[field.key];
      }
    }
    this.form.set(current);
  }

}
