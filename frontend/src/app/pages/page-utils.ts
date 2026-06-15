import { DataRecord, PageResult, RecordValue } from '../core/models';

export type TagSeverity = 'success' | 'secondary' | 'info' | 'warn' | 'danger' | 'contrast';
export type ChartLegendPosition = 'top' | 'bottom';
export type ChartDatum = { name: string; value: number; [key: string]: unknown };
export type RadarIndicator = { name: string; max: number; [key: string]: unknown };

type PieSeriesOverride = Record<string, unknown> & { itemStyle?: Record<string, unknown> };
type RadarOverride = Record<string, unknown> & { axisName?: Record<string, unknown> };

const DEFAULT_CHART_TEXT = 'rgba(100,116,139,.95)';
const DEFAULT_PIE_ITEM_STYLE = {
  borderRadius: 9,
  borderWidth: 2,
  borderColor: 'rgba(255,255,255,.52)'
};

export function valueOf(row: DataRecord | null | undefined, key: string): RecordValue {
  return row ? row[key] : undefined;
}

export function textOf(row: DataRecord | null | undefined, keys: string | string[], emptyText = '-'): string {
  const list = Array.isArray(keys) ? keys : [keys];
  for (const key of list) {
    const value = valueOf(row, key);
    if (value !== null && value !== undefined && value !== '') {
      return String(value);
    }
  }
  return emptyText;
}

export function numberOf(row: DataRecord | null | undefined, key: string, emptyValue = 0): number {
  const value = Number(valueOf(row, key) ?? emptyValue);
  return Number.isFinite(value) ? value : emptyValue;
}

export function moneyText(value: unknown): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    maximumFractionDigits: 0
  }).format(Number(value ?? 0));
}

export function compactMoneyText(value: unknown): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    notation: 'compact',
    maximumFractionDigits: 1
  }).format(Number(value ?? 0));
}

export function compactNumberText(value: unknown): string {
  return new Intl.NumberFormat('zh-CN', {
    notation: 'compact',
    maximumFractionDigits: 1
  }).format(Number(value ?? 0));
}

export function percentText(value: unknown): string {
  return `${percentNumber(value)}%`;
}

export function percentNumber(value: unknown): number {
  return Math.max(0, Math.min(100, Math.round(Number(value ?? 0))));
}

export function dateText(value: unknown): string {
  if (!value) {
    return '-';
  }
  return String(value).replace('T', ' ').slice(0, 16);
}

export function statusLabel(value: unknown): string {
  const raw = String(value ?? '-');
  const map: Record<string, string> = {
    pending: '待处理',
    draft: '草稿',
    approved: '已批准',
    partial: '部分完成',
    received: '已收货',
    paid: '已付款',
    shipped: '已发货',
    done: '已完成',
    overdue: '逾期',
    bad_debt: '坏账风险',
    cancelled: '已取消',
    counting: '盘点中',
    planned: '已计划',
    published: '已发布',
    true: '是',
    false: '否'
  };
  return map[raw] ?? raw;
}

export function statusSeverity(value: unknown): TagSeverity {
  const raw = String(value ?? '');
  if (['done', 'received', 'paid', 'shipped', 'approved', 'published', 'true'].includes(raw)) {
    return 'success';
  }
  if (['overdue', 'bad_debt', 'cancelled'].includes(raw)) {
    return 'danger';
  }
  if (['pending', 'partial', 'counting', 'draft', 'planned'].includes(raw)) {
    return 'warn';
  }
  return 'info';
}

export function recordTitle(row: DataRecord | null | undefined): string {
  return textOf(row, ['name', 'product_name', 'order_no', 'po_no', 'receivable_no', 'report_name', 'title', 'filename'], `#${row?.id ?? '-'}`);
}

export function rowId(row: DataRecord | null | undefined): number {
  return Number(row?.id ?? 0);
}

export function emptyPageResult<T>(pageSize = 50): PageResult<T> {
  return {
    items: [],
    pagination: {
      page: 1,
      page_size: pageSize,
      total: 0,
      pages: 1,
      has_next: false,
      has_prev: false
    }
  };
}

export function chartLegend(position: ChartLegendPosition = 'bottom', color = DEFAULT_CHART_TEXT) {
  const placement = position === 'top' ? { top: 0 } : { bottom: 0 };
  return {
    type: 'scroll' as const,
    left: 8,
    right: 8,
    itemWidth: 12,
    itemHeight: 8,
    itemGap: 10,
    pageButtonItemGap: 4,
    pageIconSize: 10,
    pageTextStyle: { color, fontSize: 10 },
    textStyle: {
      color,
      fontSize: 11,
      width: 92,
      overflow: 'truncate' as const
    },
    ...placement
  };
}

export function compactPieSeries(data: ChartDatum[], overrides: PieSeriesOverride = {}) {
  const { itemStyle, ...rest } = overrides;
  return {
    type: 'pie' as const,
    radius: ['36%', '58%'],
    center: ['50%', '40%'],
    avoidLabelOverlap: true,
    minAngle: 4,
    minShowLabelAngle: 8,
    label: { show: false },
    labelLine: { show: false },
    emphasis: {
      scaleSize: 4,
      label: {
        show: true,
        formatter: '{b}\n{d}%',
        fontSize: 11,
        fontWeight: 800,
        color: 'inherit'
      }
    },
    ...rest,
    itemStyle: { ...DEFAULT_PIE_ITEM_STYLE, ...(itemStyle ?? {}) },
    data
  };
}

export function compactRadar(indicator: RadarIndicator[], overrides: RadarOverride = {}) {
  const { axisName, ...rest } = overrides;
  return {
    center: ['50%', '46%'],
    radius: '52%',
    indicator,
    axisName: {
      color: DEFAULT_CHART_TEXT,
      fontSize: 11,
      fontWeight: 700,
      width: 72,
      overflow: 'truncate' as const,
      ...(axisName ?? {})
    },
    splitLine: { lineStyle: { color: 'rgba(100,116,139,.16)' } },
    splitArea: { areaStyle: { color: ['rgba(15,143,134,.035)', 'rgba(61,125,216,.045)'] } },
    ...rest
  };
}
