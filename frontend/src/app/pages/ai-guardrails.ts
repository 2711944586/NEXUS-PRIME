import { AiActionDraft, AiActionDraftStatus, AiDiagnostics, AiSettings, StructuredOperationsAnalysis } from '../core/models';

export type AiGuardrailTone = 'success' | 'warning' | 'danger' | 'info';
export type AiCapabilityDecision = 'allowed' | 'requires_confirmation' | 'blocked';

export interface AiGuardrail {
  key: string;
  title: string;
  label: string;
  detail: string;
  tone: AiGuardrailTone;
}

export interface AiTrustPosture {
  key: 'local' | 'hybrid' | 'external' | 'degraded';
  label: string;
  detail: string;
  tone: AiGuardrailTone;
}

export interface AiCapabilityRule {
  decision: AiCapabilityDecision;
  label: string;
  tone: AiGuardrailTone;
}

export interface AiDraftAction {
  id: string;
  title: string;
  description: string;
  priority: string;
  path: string;
  prompt: string;
  controlLabel: string;
  tone: AiGuardrailTone;
  execution: 'draft_only';
}

type AiActionSource = StructuredOperationsAnalysis['action_items'][number];

const BLOCKED_PATTERNS = ['绕过权限', '未授权', '删除', '导出敏感', '敏感字段', '越权'];
const CONFIRMATION_PATTERNS = ['创建采购单', '提交审批', '修改库存', '扣减库存', '记录付款', '付款', '冻结额度', '生成订单'];

export function evaluateAiCapability(text: string): AiCapabilityRule {
  const normalized = text.trim();
  if (BLOCKED_PATTERNS.some(pattern => normalized.includes(pattern))) {
    return { decision: 'blocked', label: '禁止直写', tone: 'danger' };
  }
  if (CONFIRMATION_PATTERNS.some(pattern => normalized.includes(pattern))) {
    return { decision: 'requires_confirmation', label: '人工确认', tone: 'warning' };
  }
  return { decision: 'allowed', label: '权限内建议', tone: 'success' };
}

export function buildAiTrustPosture(settings: AiSettings, diagnostics: AiDiagnostics): AiTrustPosture {
  const externalReady = diagnostics.external.configured && diagnostics.external.status === 'ready';
  if (settings.analysis_mode === 'local') {
    return {
      key: 'local',
      label: '本地可信',
      detail: '仅使用本地经营数据引擎，外部模型不可用时保持可分析。',
      tone: 'success'
    };
  }
  if (settings.analysis_mode === 'hybrid') {
    return externalReady
      ? {
          key: 'hybrid',
          label: '混合受控',
          detail: '本地引擎兜底，外部模型只参与解释和摘要生成。',
          tone: 'success'
        }
      : {
          key: 'degraded',
          label: '外部降级',
          detail: '外部推理不可用，分析自动回落到本地经营引擎。',
          tone: 'warning'
        };
  }
  return externalReady
    ? {
        key: 'external',
        label: '外部可用',
        detail: '外部模型已接入，核心动作仍需权限校验、人工确认与审计。',
        tone: 'info'
      }
    : {
        key: 'degraded',
        label: '外部阻断',
        detail: '外部模型未就绪，避免把关键经营判断交给不可达服务。',
        tone: 'danger'
      };
}

export function buildAiGuardrails(settings: AiSettings, diagnostics: AiDiagnostics): AiGuardrail[] {
  const posture = buildAiTrustPosture(settings, diagnostics);
  return [
    {
      key: 'data-scope',
      title: '权限内读取',
      label: 'Policy',
      detail: '经营分析只能读取当前用户可访问的数据范围。',
      tone: 'success'
    },
    {
      key: 'draft-only',
      title: '建议只进草稿',
      label: 'Draft',
      detail: '补货、审批、催收等建议先沉淀为草稿动作。',
      tone: 'info'
    },
    {
      key: 'core-write',
      title: '核心业务写入受控',
      label: 'Guard',
      detail: '采购、库存、收款、删除等动作必须进入正式业务页面确认。',
      tone: 'warning'
    },
    {
      key: 'trust-posture',
      title: posture.label,
      label: 'Trust',
      detail: posture.detail,
      tone: posture.tone
    }
  ];
}

export function buildAiDraftActions(actions: AiActionSource[], maxItems = 3): AiDraftAction[] {
  return actions.slice(0, maxItems).map((action, index) => {
    const decision = evaluateAiCapability(`${action.title} ${action.description} ${action.prompt}`);
    return {
      id: `draft-${slugify(action.title, index)}`,
      title: action.title,
      description: action.description,
      priority: action.priority,
      path: action.path,
      prompt: action.prompt,
      controlLabel: decision.decision === 'requires_confirmation' ? '人工确认' : '仅草稿',
      tone: action.priority === 'high' ? 'warning' : decision.tone,
      execution: 'draft_only'
    };
  });
}

export function aiDraftStatusLabel(status: AiActionDraftStatus): string {
  if (status === 'draft') {
    return '待确认';
  }
  if (status === 'confirmed') {
    return '已确认';
  }
  if (status === 'rejected') {
    return '已驳回';
  }
  return '待处理';
}

export function aiDraftStatusTone(status: AiActionDraftStatus): AiGuardrailTone {
  if (status === 'confirmed') {
    return 'success';
  }
  if (status === 'rejected') {
    return 'danger';
  }
  if (status === 'draft') {
    return 'warning';
  }
  return 'info';
}

export function summarizeAiActionDraft(draft: AiActionDraft, maxLines = 2): string {
  const lines = Array.isArray(draft.payload?.lines) ? draft.payload.lines : [];
  if (!lines.length) {
    return draft.source_tool ? `${draft.source_tool} · 等待人工确认` : '等待人工确认';
  }
  const visible = lines.slice(0, Math.max(1, maxLines)).map(line => {
    const name = line.product_name || line.name || line.sku || `物料 ${line.product_id ?? '-'}`;
    const quantity = formatQuantity(line.suggested_qty);
    return `${name} × ${quantity}`;
  });
  const remaining = lines.length - visible.length;
  return remaining > 0 ? `${visible.join('，')}，另 ${remaining} 项` : visible.join('，');
}

function slugify(value: string, index: number): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || String(index + 1);
}

function formatQuantity(value: unknown): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return '0';
  }
  return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(2);
}
