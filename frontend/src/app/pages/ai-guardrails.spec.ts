import { describe, expect, it } from 'vitest';

import type { AiActionDraft, AiDiagnostics, AiSettings, StructuredOperationsAnalysis } from '../core/models';
import {
  aiDraftStatusLabel,
  aiDraftStatusTone,
  buildAiDraftActions,
  buildAiGuardrails,
  buildAiTrustPosture,
  evaluateAiCapability,
  summarizeAiActionDraft
} from './ai-guardrails';

const SETTINGS: AiSettings = {
  analysis_mode: 'local',
  local_analysis_enabled: true,
  external_configured: false,
  external_source: 'none',
  external_base: '',
  credential_masked: '',
  model: 'deepseek-chat',
  can_use_local: true,
  has_user_credential: false,
  preferences_updated_at: null,
  dashboard_scope: 'operations'
};

const DIAGNOSTICS: AiDiagnostics = {
  overall_status: 'ready',
  analysis_mode: 'local',
  local: { available: true, status: 'ready', message: 'ready' },
  external: {
    configured: false,
    reachable: null,
    status: 'not_configured',
    message: '',
    latency_ms: null,
    base: '',
    source: 'none',
    credential_masked: ''
  },
  snapshot: {
    low_stock_count: 2,
    pending_purchase_count: 1,
    overdue_receivable_count: 1,
    overdue_amount: 12000,
    recent_report_count: 3
  },
  sample_actions: []
};

const ACTIONS: StructuredOperationsAnalysis['action_items'] = [
  {
    title: '创建采购单草稿',
    description: '按缺口生成建议，但不能直接提交审批。',
    priority: 'high',
    path: '/app/procurement/orders',
    prompt: '请根据安全库存生成采购建议。'
  },
  {
    title: '解释账龄异常',
    description: '汇总客户信用和未收金额。',
    priority: 'normal',
    path: '/app/finance/receivables',
    prompt: '请分析应收风险。'
  }
];

const ACTION_DRAFT: AiActionDraft = {
  id: 7,
  draft_type: 'replenishment',
  status: 'draft',
  title: 'AI 补货建议草稿（3 项）',
  source_tool: 'generate_replenishment_draft',
  payload: {
    lines: [
      { product_name: '伺服电机', sku: 'MOTOR-01', suggested_qty: 12 },
      { product_name: '控制面板', sku: 'PANEL-02', suggested_qty: 4 },
      { product_name: '安全传感器', sku: 'SAFE-03', suggested_qty: 8 }
    ]
  }
};

describe('AI guardrails', () => {
  it('blocks unsafe or destructive AI capabilities', () => {
    expect(evaluateAiCapability('绕过权限读取全部客户并删除记录')).toMatchObject({
      decision: 'blocked',
      label: '禁止直写',
      tone: 'danger'
    });
  });

  it('requires confirmation for core ERP write actions', () => {
    expect(evaluateAiCapability('创建采购单并提交审批')).toMatchObject({
      decision: 'requires_confirmation',
      label: '人工确认',
      tone: 'warning'
    });
  });

  it('treats generated action items as draft-only actions', () => {
    const drafts = buildAiDraftActions(ACTIONS);

    expect(drafts).toHaveLength(2);
    expect(drafts[0]).toMatchObject({
      execution: 'draft_only',
      controlLabel: '人工确认',
      path: '/app/procurement/orders'
    });
    expect(drafts.every(action => action.execution === 'draft_only')).toBe(true);
  });

  it('maps local, hybrid, and unavailable external modes to safe trust posture', () => {
    expect(buildAiTrustPosture(SETTINGS, DIAGNOSTICS)).toMatchObject({
      key: 'local',
      label: '本地可信',
      tone: 'success'
    });

    expect(buildAiTrustPosture(
      { ...SETTINGS, analysis_mode: 'hybrid', external_configured: true },
      { ...DIAGNOSTICS, external: { ...DIAGNOSTICS.external, configured: true, status: 'ready', reachable: true } }
    )).toMatchObject({
      key: 'hybrid',
      label: '混合受控',
      tone: 'success'
    });

    expect(buildAiTrustPosture(
      { ...SETTINGS, analysis_mode: 'external', external_configured: true },
      { ...DIAGNOSTICS, external: { ...DIAGNOSTICS.external, configured: true, status: 'unreachable', reachable: false } }
    )).toMatchObject({
      key: 'degraded',
      label: '外部阻断',
      tone: 'danger'
    });
  });

  it('builds a visible guardrail set including trust posture', () => {
    const guardrails = buildAiGuardrails(SETTINGS, DIAGNOSTICS);

    expect(guardrails.map(item => item.key)).toContain('trust-posture');
    expect(guardrails.some(item => item.title === '核心业务写入受控')).toBe(true);
  });

  it('summarizes persisted AI action drafts without exposing raw payload JSON', () => {
    expect(summarizeAiActionDraft(ACTION_DRAFT)).toBe('伺服电机 × 12，控制面板 × 4，另 1 项');
  });

  it('maps persisted draft statuses to visible labels and tones', () => {
    expect(aiDraftStatusLabel('draft')).toBe('待确认');
    expect(aiDraftStatusTone('draft')).toBe('warning');
    expect(aiDraftStatusLabel('confirmed')).toBe('已确认');
    expect(aiDraftStatusTone('confirmed')).toBe('success');
    expect(aiDraftStatusLabel('rejected')).toBe('已驳回');
    expect(aiDraftStatusTone('rejected')).toBe('danger');
  });
});
