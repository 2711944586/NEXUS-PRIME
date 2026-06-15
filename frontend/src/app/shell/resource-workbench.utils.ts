import { LookupItem, PageMeta, DataRecord } from '../core/models';
import { ResourceFieldConfig, ResourceWorkflowConfig } from '../core/resource-workflow';

export type LookupOption = {
  label: string;
  value: string | number | boolean;
  description?: string | null;
  meta?: LookupItem;
};

export interface FormValidationResult {
  errors: Record<string, string>;
  message: string | null;
}

export function emptyPageMeta(pageSize: number): PageMeta {
  return {
    page: 1,
    page_size: pageSize,
    total: 0,
    pages: 0,
    has_next: false,
    has_prev: false
  };
}

export function rowKey(row: DataRecord | null, fallback = -1): string {
  return row?.id !== undefined && row.id !== null ? String(row.id) : `row-${fallback}`;
}

export function displayTitle(row: DataRecord | null): string {
  if (!row) {
    return '未选择记录';
  }
  for (const key of ['name', 'title', 'product_name', 'order_no', 'po_no', 'receivable_no', 'report_name', 'filename', 'username', 'sku']) {
    const value = row[key];
    if (value !== null && value !== undefined && value !== '') {
      return String(value);
    }
  }
  return `#${row.id ?? '-'}`;
}

export function valueText(value: unknown, type?: ResourceFieldConfig['type']): string {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  if (type === 'number') {
    return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(Number(value ?? 0));
  }
  if (type === 'date') {
    return String(value).replace('T', ' ').slice(0, 16);
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }
  if (Array.isArray(value)) {
    return `${value.length} 条`;
  }
  if (typeof value === 'object') {
    return `${Object.keys(value as object).length} 个字段`;
  }
  return String(value);
}

export function pageSummary(meta: PageMeta, query: string): string {
  const trimmedQuery = query.trim();
  if (!meta.total) {
    return trimmedQuery ? '没有匹配记录' : '暂无记录';
  }
  const start = (meta.page - 1) * meta.page_size + 1;
  const end = Math.min(meta.total, meta.page * meta.page_size);
  const queryNote = trimmedQuery ? ` · 筛选「${trimmedQuery}」` : '';
  return `${start}-${end} / ${meta.total} 条${queryNote}`;
}

export function defaultForm(
  fields: ResourceFieldConfig[],
  lookupOptions: Record<string, LookupOption[]> = {}
): Record<string, unknown> {
  return fields.reduce<Record<string, unknown>>((acc, field) => {
    if (field.defaultValue !== undefined) {
      acc[field.key] = field.defaultValue;
    } else if (field.type === 'select' && field.options?.length) {
      acc[field.key] = field.options[0].value;
    } else if (field.type === 'lookup') {
      const options = lookupOptions[field.key] ?? [];
      acc[field.key] = field.required && options.length ? options[0].value : '';
    } else if (field.type === 'number') {
      acc[field.key] = field.min ?? 0;
    } else {
      acc[field.key] = '';
    }
    return acc;
  }, {});
}

export function formFromRecord(
  row: DataRecord,
  fields: ResourceFieldConfig[],
  lookupOptions: Record<string, LookupOption[]> = {}
): Record<string, unknown> {
  const form = defaultForm(fields, lookupOptions);
  for (const field of fields) {
    const value = row[field.key];
    if (value !== undefined && value !== null) {
      form[field.key] = field.type === 'date' ? String(value).slice(0, 10) : value;
    }
  }
  return form;
}

export function validateForm(
  cfg: ResourceWorkflowConfig,
  fields: ResourceFieldConfig[],
  form: Record<string, unknown>
): FormValidationResult {
  const errors: Record<string, string> = {};
  for (const field of fields) {
    const value = form[field.key];
    if (field.required && (value === undefined || value === null || value === '')) {
      errors[field.key] = `请填写${field.label}`;
      continue;
    }
    if (field.type === 'number' && value !== undefined && value !== null && value !== '') {
      const numberValue = Number(value);
      if (!Number.isFinite(numberValue)) {
        errors[field.key] = `${field.label}必须是数字`;
      } else if (field.min !== undefined && numberValue < field.min) {
        errors[field.key] = `${field.label}不能小于 ${field.min}`;
      }
    }
  }
  if (cfg.key === 'stocktakes' && form['take_type'] === 'partial' && !form['product_id']) {
    errors['product_id'] = '抽盘需要选择物料';
  }
  return {
    errors,
    message: Object.values(errors)[0] ?? null
  };
}

export function normalizedForm(fields: ResourceFieldConfig[], form: Record<string, unknown>): Record<string, unknown> {
  return fields.reduce<Record<string, unknown>>((acc, field) => {
    const value = form[field.key];
    if (!field.required && (value === '' || value === undefined || value === null)) {
      return acc;
    }
    acc[field.key] = value;
    return acc;
  }, {});
}

export function toLookupOption(item: LookupItem): LookupOption {
  const detail = item.description || item.sku || item.type || null;
  return {
    label: detail ? `${item.label} · ${detail}` : item.label,
    value: item.id,
    description: item.description,
    meta: item
  };
}

export function errorDetail(error: unknown, fallback: string): string {
  const candidate = error as { error?: { message?: string; error?: string }; message?: string };
  return candidate?.error?.message || candidate?.error?.error || candidate?.message || fallback;
}
