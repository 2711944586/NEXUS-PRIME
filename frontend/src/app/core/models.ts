export type ThemeMode = 'dark-cockpit' | 'light-luxury';
export type ThemeSource = 'system' | ThemeMode;

export interface ApiEnvelope<T> {
  data: T;
  message: string;
  error: string | null;
}

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface PageResult<T> {
  items: T[];
  pagination: PageMeta;
}

export interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string | null;
  phone?: string | null;
  avatar?: string | null;
  role_name?: string | null;
  department_name_display?: string | null;
  department_name?: string | null;
  position?: string | null;
  bio?: string | null;
  is_admin_effective?: boolean;
  preferences?: UserPreferences;
}

export interface PermissionSummary {
  name: string;
  label: string;
}

export interface LoginResult {
  csrf_token: string;
  user: User;
  permissions: PermissionSummary[];
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  full_name?: string;
  phone?: string;
  position?: string;
  department_name?: string;
  accepted_terms: boolean;
  accepted_privacy: boolean;
  accepted_data_scope: boolean;
  terms_version: string;
  captcha_token: string;
  captcha_answer: string;
}

export interface ExecutiveAnalytics {
  kpis: {
    total_sales: number;
    unpaid_amount: number;
    pending_purchase: number;
    active_alerts: number;
    collaboration_items: number;
  };
  sales_trend: Array<{ name: string; value: number }>;
  risk_mix: Array<{ name: string; value: number }>;
  collaboration: Array<{ name: string; value: number }>;
  top_customers?: Array<{ name: string; value: number }>;
  procurement_stages?: Array<{ name: string; value: number }>;
  aging_buckets?: Array<{ name: string; value: number }>;
  warehouse_turnover?: Array<{ name: string; stock_quantity: number; movement_count: number }>;
  supplier_score?: Array<{ name: string; on_time_rate: number; quality_rate: number }>;
  inventory_risk_rank?: Array<{ name: string; sku: string; gap: number; current_qty: number }>;
  order_status_flow?: Array<{ name: string; value: number }>;
  cash_collection_trend?: Array<{ name: string; value: number }>;
  action_queue?: Array<{
    title: string;
    module: string;
    priority: 'high' | 'normal' | string;
    metric: string;
    path: string;
    description: string;
  }>;
  operational_efficiency?: Array<{ name: string; value: number; target: number }>;
  module_throughput?: Array<{ name: string; todo: number; done: number; blocked: number }>;
}

export interface OperationsTodoPayload {
  items: Array<{ label: string; value: number; path: string }>;
  stock_quantity: number;
}

export interface OperationsExceptionItem {
  type: string;
  level: string;
  title: string;
  description: string;
  path: string;
}

export interface OperationsExceptionsPayload {
  items: OperationsExceptionItem[];
  total: number;
  overdue_updated?: boolean;
}

export interface OperationsTaskQueueItem {
  id: string;
  source_id?: number;
  source: 'notification' | 'deployment' | 'stock' | 'purchase' | string;
  business_type?: string | null;
  business_id?: string | number | null;
  title: string;
  description: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: string;
  owner: string;
  source_path: string;
  detail_path: string;
  action_label: string;
  action_kind: 'complete_notification' | 'create_deployment_task' | 'navigate' | string;
  category: string;
  payload?: DataRecord;
  created_at?: string | null;
}

export interface OperationsTaskQueuePayload {
  summary: {
    total: number;
    open_notifications: number;
    deployment_attention: number;
    business_exceptions: number;
    p0: number;
    p1: number;
    p2: number;
    generated_at: string;
    next_action: string;
  };
  items: OperationsTaskQueueItem[];
}

export interface DataQualityIssue {
  id: string;
  module: string;
  dimension: string;
  title: string;
  count: number;
  severity: 'success' | 'warn' | 'danger' | 'info' | string;
  priority: 'P0' | 'P1' | 'P2' | string;
  owner: string;
  status: string;
  sla: string;
  path: string;
  evidence: string;
  action: string;
  runbook: string[];
}

export interface DataQualityDimension {
  key: string;
  label: string;
  owner: string;
  total: number;
  failed: number;
  score: number;
  coverage: number;
  status: 'ready' | 'attention' | 'blocked' | string;
}

export interface DataQualityPayload {
  generated_at: string;
  source: string;
  summary: {
    score: number;
    level: 'ready' | 'attention' | 'blocked' | string;
    issue_count: number;
    failed_tests: number;
    passed_tests: number;
    total_tests: number;
    p0: number;
    p1: number;
    coverage: number;
    next_action: string;
    primary_owner: string;
  };
  dimensions: DataQualityDimension[];
  issue_queue: DataQualityIssue[];
  test_suites: Array<{
    id: string;
    name: string;
    scope: string;
    owner: string;
    passed: number;
    failed: number;
    coverage: number;
    last_run: string;
    slo: string;
    status: 'ready' | 'attention' | 'blocked' | string;
  }>;
  lineage: Array<{ from: string; to: string; status: 'ready' | 'attention' | 'blocked' | string; label: string }>;
  runbook: Array<{ step: string; detail: string }>;
}

export interface RuleDecisionColumn {
  id: string;
  label: string;
  source: string;
  value: string;
}

export interface RuleDecisionRow {
  id: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  conditions: string[];
  outputs: string[];
  action: string;
  hit_count: number;
  risk_count: number;
  status: 'ready' | 'attention' | 'blocked' | string;
}

export interface RuleItem {
  id: string;
  name: string;
  domain: string;
  trigger: string;
  action: string;
  enabled: boolean;
  status: 'ready' | 'attention' | 'blocked' | string;
  owner: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  sla: string;
  hit_policy: string;
  hit_count: number;
  risk_count: number;
  automation_rate: number;
  coverage: number;
  confidence: number;
  path: string;
  risk_note: string;
  evidence: string;
  runbook: string[];
  decision_table: {
    hit_policy: string;
    inputs: RuleDecisionColumn[];
    outputs: RuleDecisionColumn[];
    rows: RuleDecisionRow[];
  };
  governance: {
    version: string;
    last_reviewed: string;
    next_review_due: string;
    approval_group: string;
    change_window: string;
    monitoring_metric: string;
  };
  service_boundary: {
    service: string;
    contract: string;
    event: string;
    fallback: string;
  };
}

export interface RuleDecisionQueueItem {
  id: string;
  rule_id: string;
  title: string;
  domain: string;
  owner: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  sla: string;
  status: 'ready' | 'attention' | 'blocked' | string;
  path: string;
  hit_count: number;
  risk_count: number;
  evidence: string;
  action: string;
  runbook: string[];
  escalation: string;
  created_at: string;
}

export interface RulesPayload {
  generated_at: string;
  source: string;
  summary: {
    total: number;
    enabled: number;
    hits: number;
    risks: number;
    p0: number;
    p1: number;
    queue_count: number;
    automation_rate: number;
    coverage: number;
    primary_owner: string;
    next_action: string;
  };
  items: RuleItem[];
  decision_queue: RuleDecisionQueueItem[];
  domains: Array<{
    key: string;
    label: string;
    owner: string;
    hits: number;
    risks: number;
    coverage: number;
    status: 'ready' | 'attention' | 'blocked' | string;
    metric: string;
  }>;
  decision_map: Array<{
    from: string;
    to: string;
    label: string;
    status: 'ready' | 'attention' | 'blocked' | string;
  }>;
  runbook: Array<{ step: string; detail: string }>;
}

export interface CostCenter {
  id: string;
  label: string;
  owner: string;
  priority_owner: string;
  budget: number;
  actual: number;
  commitment: number;
  available: number;
  variance: number;
  variance_rate: number;
  used_rate: number;
  status: 'ready' | 'attention' | 'blocked' | string;
  priority: 'P0' | 'P1' | 'P2' | string;
  sla: string;
  path: string;
  evidence: string;
  action: string;
  runbook: string[];
}

export interface CostVarianceQueueItem {
  id: string;
  cost_center_id: string;
  title: string;
  owner: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  sla: string;
  status: 'ready' | 'attention' | 'blocked' | string;
  budget: number;
  actual: number;
  commitment: number;
  available: number;
  variance: number;
  variance_rate: number;
  path: string;
  evidence: string;
  action: string;
  runbook: string[];
  created_at: string;
}

export interface CostGovernancePayload {
  generated_at: string;
  source: string;
  summary: {
    inventory_value: number;
    sales_amount: number;
    procurement_amount: number;
    unpaid_amount: number;
    paid_amount: number;
    cash_gap: number;
    budget_total: number;
    actual_total: number;
    commitment_total: number;
    available_budget: number;
    variance_amount: number;
    burn_rate: number;
    score: number;
    p0: number;
    p1: number;
    queue_count: number;
    primary_owner: string;
    next_action: string;
  };
  cost_centers: CostCenter[];
  variance_queue: CostVarianceQueueItem[];
  categories: Array<{ name: string; value: number }>;
  timeline: Array<{ name: string; value: number }>;
  waterfall: Array<{ name: string; value: number; type: 'budget' | 'actual' | 'commitment' | 'available' | string }>;
  runbook: Array<{ step: string; detail: string }>;
  service_boundary: Array<{
    service: string;
    contract: string;
    owner: string;
    readiness: 'ready' | 'attention' | 'blocked' | string;
  }>;
}

export interface CapacityWorkCenter {
  id: string;
  label: string;
  owner: string;
  load: number;
  available_hours: number;
  required_hours: number;
  hour_gap: number;
  status: 'ready' | 'attention' | 'blocked' | string;
  priority: 'P0' | 'P1' | 'P2' | string;
  sla: string;
  path: string;
  evidence: string;
  action: string;
  runbook: string[];
}

export interface CapacityBottleneckItem {
  id: string;
  work_center_id: string;
  title: string;
  owner: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  sla: string;
  status: 'ready' | 'attention' | 'blocked' | string;
  path: string;
  load: number;
  hour_gap: number;
  evidence: string;
  action: string;
  runbook: string[];
  created_at: string;
}

export interface CapacityGovernancePayload {
  generated_at: string;
  source: string;
  summary: {
    load_score: number;
    demand_units: number;
    incoming_units: number;
    shortage_units: number;
    active_orders: number;
    pending_purchase: number;
    low_materials: number;
    warehouse_utilization: number;
    p0: number;
    p1: number;
    queue_count: number;
    primary_owner: string;
    next_action: string;
  };
  work_centers: CapacityWorkCenter[];
  shift_plan: Array<{ id: string; label: string; window: string; owner: string; load: number; focus: string; status: 'ready' | 'attention' | 'blocked' | string }>;
  bottleneck_queue: CapacityBottleneckItem[];
  demand: Array<{ id: number; title: string; customer: string; status: string; amount: number; units: number; path: string }>;
  supply: Array<{ id: number; title: string; supplier: string; warehouse: string; status: string; amount: number; progress: number; path: string }>;
  material_constraints: Array<{ id: number; sku: string; name: string; total_stock: number; min_stock: number; shortage_units: number; path: string }>;
  load_curve: Array<{ name: string; value: number }>;
  runbook: Array<{ step: string; detail: string }>;
  service_boundary: Array<{
    service: string;
    contract: string;
    owner: string;
    readiness: 'ready' | 'attention' | 'blocked' | string;
  }>;
}

export interface MobileTerminalTask {
  id: string;
  source_id?: number | null;
  type: string;
  source: string;
  title: string;
  owner: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: string;
  readiness: 'ready' | 'attention' | 'blocked' | string;
  warehouse: string;
  location: string;
  path: string;
  progress: number;
  quantity: number;
  evidence: string;
  next_action: string;
  scan_code: string;
  sla: string;
  created_at: string;
  checklist: string[];
}

export interface MobileTerminalLane {
  id: string;
  label: string;
  owner: string;
  active_count: number;
  p0: number;
  p1: number;
  progress: number;
  status: 'ready' | 'attention' | 'blocked' | string;
  path: string;
  scan_target: string;
  metric: string;
}

export interface MobileDeviceSession {
  id: string;
  label: string;
  owner: string;
  task_count: number;
  battery: number;
  sync_latency_ms: number;
  zone: string;
  status: 'ready' | 'attention' | 'blocked' | 'offline' | string;
  last_sync: string;
}

export interface MobileTerminalPayload {
  generated_at: string;
  source: string;
  summary: {
    total_tasks: number;
    receiving: number;
    counting: number;
    shipping: number;
    alerts: number;
    p0: number;
    p1: number;
    completion_rate: number;
    sync_rate: number;
    active_devices: number;
    primary_owner: string;
    next_action: string;
  };
  lanes: MobileTerminalLane[];
  scan_queue: MobileTerminalTask[];
  device_sessions: MobileDeviceSession[];
  warehouse_zones: Array<{
    id: number;
    label: string;
    location: string;
    quantity: number;
    capacity: number;
    utilization: number;
    slot_count: number;
    status: 'ready' | 'attention' | 'blocked' | string;
  }>;
  scan_flow: Array<{ step: string; detail: string }>;
  runbook: Array<{ step: string; detail: string }>;
  service_boundary: Array<{
    service: string;
    contract: string;
    owner: string;
    readiness: 'ready' | 'attention' | 'blocked' | string;
  }>;
}

export interface MaintenanceAssetLine {
  id: string;
  label: string;
  owner: string;
  health: number;
  risk_hours: number;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  sla: string;
  path: string;
  evidence: string;
  action: string;
}

export interface MaintenanceWorkorderItem {
  id: string;
  source: string;
  source_id: number | string | null;
  product_id: number | null;
  title: string;
  asset: string;
  line: string;
  part_name: string;
  owner: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  sla: string;
  risk_score: number;
  path: string;
  evidence: string;
  action: string;
  checklist: string[];
  created_at: string;
}

export interface MaintenanceSparePart {
  id: number;
  product_id: number;
  name: string;
  sku: string;
  supplier: string;
  category: string;
  total_stock: number;
  min_stock: number;
  max_stock: number;
  shortage: number;
  coverage: number;
  warehouse_count: number;
  location: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  path: string;
  evidence: string;
  action: string;
}

export interface MaintenanceReliabilityPayload {
  generated_at: string;
  source: string;
  summary: {
    health_score: number;
    spare_parts: number;
    low_spares: number;
    active_alerts: number;
    red_alerts: number;
    documents: number;
    audit_events: number;
    open_workorders: number;
    p0: number;
    p1: number;
    queue_count: number;
    primary_owner: string;
    next_action: string;
  };
  asset_lines: MaintenanceAssetLine[];
  workorder_queue: MaintenanceWorkorderItem[];
  spare_parts: MaintenanceSparePart[];
  technician_roster: Array<{
    id: string;
    name: string;
    role: string;
    task_count: number;
    load: number;
    status: 'ready' | 'attention' | 'blocked' | string;
    focus: string;
  }>;
  downtime_windows: Array<{
    id: string;
    label: string;
    window: string;
    owner: string;
    risk_hours: number;
    status: 'ready' | 'attention' | 'blocked' | string;
    evidence: string;
  }>;
  documents: Array<{ id: number; title: string; size: number; mimetype: string; path: string }>;
  maintenance_flow: Array<{ step: string; detail: string }>;
  runbook: Array<{ step: string; detail: string }>;
  service_boundary: Array<{
    service: string;
    contract: string;
    owner: string;
    readiness: 'ready' | 'attention' | 'blocked' | string;
  }>;
}

export interface QualityInspectionLane {
  id: string;
  label: string;
  owner: string;
  active_count: number;
  p0: number;
  p1: number;
  score: number;
  status: 'ready' | 'attention' | 'blocked' | string;
  priority: 'P0' | 'P1' | 'P2' | string;
  path: string;
  metric: string;
  evidence: string;
  action: string;
}

export interface QualityInspectionQueueItem {
  id: string;
  source: string;
  source_id: number | string | null;
  product_id: number | null;
  supplier_id: number | null;
  purchase_id: number | null;
  title: string;
  lot_code: string;
  product_name: string;
  supplier: string;
  owner: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  sla: string;
  risk_score: number;
  decision: string;
  path: string;
  evidence: string;
  action: string;
  checklist: string[];
  created_at: string;
}

export interface QualitySupplierQuality {
  id: string;
  supplier_id: number;
  name: string;
  contact?: string | null;
  phone?: string | null;
  on_time_rate: number;
  quality_rate: number;
  total_orders: number;
  quality_pass_orders: number;
  pending_orders: number;
  score: number;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  path: string;
  evidence: string;
  action: string;
}

export interface QualityInspectionPayload {
  generated_at: string;
  source: string;
  summary: {
    quality_score: number;
    pending_lots: number;
    blocked_lots: number;
    supplier_alerts: number;
    defects: number;
    documents: number;
    open_tasks: number;
    quality_reports: number;
    usage_decision_rate: number;
    p0: number;
    p1: number;
    queue_count: number;
    primary_owner: string;
    next_action: string;
  };
  inspection_lanes: QualityInspectionLane[];
  inspection_queue: QualityInspectionQueueItem[];
  supplier_quality: QualitySupplierQuality[];
  defect_taxonomy: Array<{
    id: string;
    label: string;
    type: string;
    count: number;
    impact: string;
    owner: string;
    priority: 'P0' | 'P1' | 'P2' | string;
    status: 'ready' | 'attention' | 'blocked' | string;
    path: string;
    evidence: string;
    action: string;
  }>;
  inspection_lots: Array<{
    id: string;
    purchase_id: number;
    lot_code: string;
    reference: string;
    supplier: string;
    supplier_id?: number | null;
    warehouse: string;
    status: 'ready' | 'attention' | 'blocked' | string;
    order_status: string;
    progress: number;
    quantity: number;
    received_qty: number;
    amount: number;
    expected_date?: string | null;
    owner: string;
    priority: 'P0' | 'P1' | 'P2' | string;
    decision: string;
    inspection_type: string;
    path: string;
    evidence: string;
    action: string;
  }>;
  document_set: Array<{
    id: string;
    title: string;
    type: string;
    size: number;
    status: 'ready' | 'attention' | 'blocked' | string;
    path: string;
    evidence: string;
  }>;
  quality_flow: Array<{ step: string; detail: string }>;
  runbook: Array<{ step: string; detail: string }>;
  service_boundary: Array<{
    service: string;
    contract: string;
    owner: string;
    readiness: 'ready' | 'attention' | 'blocked' | string;
  }>;
}

export interface LookupItem {
  id: number;
  label: string;
  description?: string | null;
  sku?: string;
  price?: number;
  cost?: number;
  type?: string;
  quantity?: number;
  warehouse_id?: number;
  product_id?: number;
}

export interface ManufacturingCommandCenter {
  kpis: {
    order_amount: number;
    stock_quantity: number;
    low_stock_products: number;
    pending_purchase: number;
    overdue_amount: number;
  };
  warehouse_heat: Array<{ name: string; stock_quantity: number; slot_count: number }>;
  flows: Array<{ from: string; to: string; value: number }>;
  risks: Array<{ type: string; level: 'critical' | 'warning' | string; title: string; description: string }>;
}

export interface OperationsWorkflowBoard {
  generated_at: string;
  source: string;
  summary: {
    title: string;
    health_score: number;
    active_stages: number;
    attention_count: number;
    blocked_count: number;
    next_action: string;
    next_path: string;
    cadence: string;
    shift_window?: string;
    commander?: string;
    evidence_count?: number;
    open_action_count?: number;
  };
  stages: Array<{
    key: string;
    code: string;
    label: string;
    owner: string;
    path: string;
    value: string;
    detail: string;
    progress: number;
    status: 'complete' | 'ready' | 'attention' | 'blocked' | string;
    next_action: string;
    sla: string;
    records: Array<{
      label: string;
      metric: string;
      meta: string;
      path: string;
    }>;
  }>;
  handoffs: Array<{
    from: string;
    to: string;
    value: number;
    label: string;
  }>;
  bottlenecks: Array<{
    key: string;
    label: string;
    status: 'complete' | 'ready' | 'attention' | 'blocked' | string;
    rank: number;
    metric: string;
    action: string;
    path: string;
    owner: string;
  }>;
  action_queue: Array<{
    key: string;
    stage_key: string;
    priority: 'P0' | 'P1' | 'P2' | string;
    title: string;
    owner: string;
    path: string;
    metric: string;
    due: string;
    evidence: string;
    handoff: string;
  }>;
  service_boundaries: Array<{
    name: string;
    owner: string;
    surface: string;
    contract: string;
    deploy_unit: string;
    readiness: 'ready' | 'attention' | 'blocked' | string;
  }>;
  deployment_checks: Array<{
    key: string;
    label: string;
    status: 'ready' | 'attention' | 'blocked' | string;
    owner: string;
    evidence: string;
  }>;
  role_views: Array<{
    role: string;
    focus: string;
  }>;
  role_command_center: Array<{
    role: string;
    owner: string;
    workload: number;
    primary_metric: string;
    readiness: 'ready' | 'attention' | 'blocked' | string;
    next_action: string;
    path: string;
    evidence: string;
    domains: string[];
  }>;
  execution_events: Array<{
    id: string;
    at: string;
    module: string;
    title: string;
    detail: string;
    severity: 'ready' | 'attention' | 'blocked' | 'complete' | string;
    actor: string;
    metric: string;
    path: string;
    evidence: string;
  }>;
  data_contracts: Array<{
    surface: string;
    consumer: string;
    provider: string;
    payload: string;
    readiness: 'ready' | 'attention' | 'blocked' | string;
    evidence: string;
  }>;
}

export interface ErpControlTower {
  generated_at: string;
  source: string;
  summary: {
    title: string;
    control_score: number;
    health_score: number;
    total_records: number;
    revenue: number;
    cash_exposure: number;
    open_actions: number;
    risk_count: number;
    evidence_count: number;
    service_boundaries: number;
    next_action: string;
    next_path: string;
    cadence: string;
  };
  domain_health: Array<{
    key: string;
    label: string;
    owner: string;
    path: string;
    metric: string;
    score: number;
    status: 'ready' | 'attention' | 'blocked' | string;
    evidence: string;
  }>;
  action_queue: Array<{
    id: string;
    title: string;
    owner: string;
    priority: 'P0' | 'P1' | 'P2' | string;
    path: string;
    metric: string;
    due: string;
    evidence: string;
    domain: string;
  }>;
  readiness: Array<{
    name: string;
    owner: string;
    surface: string;
    contract: string;
    runtime: string;
    readiness: 'ready' | 'attention' | 'blocked' | string;
    path: string;
  }>;
  evidence_ledger: Array<{
    label: string;
    value: number;
    unit: string;
    description: string;
    path: string;
  }>;
  workflow: {
    stages: OperationsWorkflowBoard['stages'];
    handoffs: OperationsWorkflowBoard['handoffs'];
    bottlenecks: OperationsWorkflowBoard['bottlenecks'];
  };
}

export interface ProcurementControlPayload {
  generated_at: string;
  source: string;
  summary: {
    control_score: number;
    pending_approvals: number;
    receiving_due: number;
    supplier_risk: number;
    quality_hold: number;
    budget_exposure: number;
    replenishment_pending: number;
    open_tasks: number;
    queue_count: number;
    p0: number;
    p1: number;
    primary_owner: string;
    next_action: string;
    next_path: string;
  };
  procurement_lanes: ProcurementControlLane[];
  approval_queue: ProcurementApprovalItem[];
  receiving_windows: ProcurementReceivingWindow[];
  supplier_risk_cards: ProcurementSupplierRiskCard[];
  supplier_risk_queue: ProcurementControlQueueItem[];
  replenishment_candidates: ProcurementReplenishmentCandidate[];
  control_queue: ProcurementControlQueueItem[];
  purchase_flow: Array<{ step: string; detail: string }>;
  service_boundaries: ProcurementServiceBoundary[];
  deployment_checks: ProcurementDeploymentCheck[];
  runbook: Array<{ step: string; detail: string }>;
}

export interface ProcurementControlLane {
  id: string;
  label: string;
  owner: string;
  active_count: number;
  p0: number;
  p1: number;
  score: number;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  path: string;
  evidence: string;
  action: string;
  sla: string;
}

export interface ProcurementApprovalItem {
  id: string;
  source: string;
  purchase_id: number;
  supplier_id: number | null;
  po_no: string;
  title: string;
  supplier: string;
  warehouse: string;
  amount: number;
  status: string;
  owner: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  sla: string;
  age_hours: number;
  risk: string;
  path: string;
  evidence: string;
  action: string;
}

export interface ProcurementReceivingWindow {
  id: string;
  source: string;
  purchase_id: number;
  supplier_id: number | null;
  po_no: string;
  title: string;
  supplier: string;
  warehouse: string;
  expected_date: string | null;
  days_to_due: number;
  progress: number;
  amount: number;
  owner: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  sla: string;
  path: string;
  evidence: string;
  action: string;
}

export interface ProcurementSupplierRiskCard {
  id: string;
  supplier_id: number;
  name: string;
  contact: string | null;
  phone: string | null;
  on_time_rate: number;
  quality_rate: number;
  pending_orders: number;
  total_orders: number;
  total_amount: number;
  score: number;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  path: string;
  evidence: string;
  action: string;
}

export interface ProcurementReplenishmentCandidate {
  id: string;
  suggestion_id: number;
  product_id: number;
  supplier_id: number | null;
  sku: string;
  title: string;
  supplier: string;
  warehouse: string;
  status: string;
  current_qty: number;
  suggested_qty: number;
  lead_time_days: number;
  amount: number;
  priority: 'P0' | 'P1' | 'P2' | string;
  path: string;
  evidence: string;
  action: string;
}

export interface ProcurementControlQueueItem {
  id: string;
  source: string;
  purchase_id?: number | null;
  supplier_id?: number | null;
  suggestion_id?: number;
  product_id?: number;
  title: string;
  owner: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  sla: string;
  path: string;
  metric: string;
  kind: string;
  evidence: string;
  action: string;
}

export interface ProcurementServiceBoundary {
  service: string;
  contract: string;
  owner: string;
  deploy_unit: string;
  readiness: 'ready' | 'attention' | 'blocked' | string;
}

export interface ProcurementDeploymentCheck {
  key: string;
  label: string;
  status: 'ready' | 'attention' | 'blocked' | string;
  owner: string;
  evidence: string;
}

export interface SupplierCollaborationPayload {
  generated_at: string;
  source: string;
  summary: {
    network_score: number;
    active_suppliers: number;
    preferred_suppliers: number;
    risk_suppliers: number;
    qualification_due: number;
    pending_orders: number;
    delivery_due: number;
    quality_watch: number;
    open_tasks: number;
    spend_amount: number;
    p0: number;
    p1: number;
    queue_count: number;
    primary_owner: string;
    next_action: string;
  };
  collaboration_lanes: SupplierCollaborationLane[];
  supplier_cards: SupplierCollaborationCard[];
  risk_queue: SupplierCollaborationQueueItem[];
  qualification_queue: SupplierCollaborationQueueItem[];
  delivery_windows: SupplierDeliveryWindow[];
  supplier_matrix: Array<{
    name: string;
    score: number;
    on_time_rate: number;
    quality_rate: number;
    credit_score: number;
    spend_share: number;
    pending_orders: number;
    status: 'ready' | 'attention' | 'blocked' | string;
  }>;
  collaboration_flow: Array<{ step: string; detail: string }>;
  service_boundaries: SupplierServiceBoundary[];
  deployment_checks: SupplierDeploymentCheck[];
  runbook: Array<{ step: string; detail: string }>;
}

export interface SupplierCollaborationLane {
  id: string;
  label: string;
  owner: string;
  active_count: number;
  p0: number;
  p1: number;
  score: number;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  path: string;
  evidence: string;
  action: string;
  sla: string;
}

export interface SupplierCollaborationCard {
  id: string;
  supplier_id: number;
  name: string;
  contact: string | null;
  phone: string | null;
  email: string | null;
  credit_score: number;
  on_time_rate: number;
  quality_rate: number;
  score: number;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  qualification_status: 'ready' | 'attention' | 'blocked' | string;
  capa_status: 'ready' | 'attention' | 'blocked' | string;
  pending_orders: number;
  active_amount: number;
  spend_share: number;
  product_count: number;
  suggestion_count: number;
  last_order_date: string | null;
  owner: string;
  path: string;
  evidence: string;
  action: string;
}

export interface SupplierCollaborationQueueItem {
  id: string;
  supplier_id?: number | null;
  purchase_id?: number | null;
  title: string;
  owner: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  sla: string;
  metric: string;
  path: string;
  evidence: string;
  action: string;
  kind: string;
}

export interface SupplierDeliveryWindow {
  id: string;
  purchase_id: number;
  supplier_id: number | null;
  po_no: string;
  supplier: string;
  warehouse: string;
  status: 'ready' | 'attention' | 'blocked' | string;
  order_status: string;
  priority: 'P0' | 'P1' | 'P2' | string;
  expected_date: string | null;
  days_to_due: number;
  progress: number;
  amount: number;
  owner: string;
  path: string;
  evidence: string;
  action: string;
}

export interface SupplierServiceBoundary {
  service: string;
  contract: string;
  owner: string;
  deploy_unit: string;
  readiness: 'ready' | 'attention' | 'blocked' | string;
}

export interface SupplierDeploymentCheck {
  key: string;
  label: string;
  status: 'ready' | 'attention' | 'blocked' | string;
  owner: string;
  evidence: string;
}

export interface UserPreferences {
  theme?: ThemeMode;
  theme_source?: ThemeSource;
  density?: 'compact' | 'comfortable';
  default_workspace?: string;
  charts_motion?: 'standard' | 'reduced';
  dock_labels?: 'hover' | 'always';
  context_panel?: 'visible' | 'compact';
}

export type AiActionDraftStatus = 'draft' | 'confirmed' | 'rejected' | string;

export interface AiActionDraftLine {
  product_id?: number | string | null;
  product_name?: string | null;
  name?: string | null;
  sku?: string | null;
  warehouse_id?: number | string | null;
  warehouse_name?: string | null;
  supplier_id?: number | string | null;
  supplier_name?: string | null;
  current_qty?: number | string | null;
  suggested_qty?: number | string | null;
  min_stock?: number | string | null;
  [key: string]: unknown;
}

export interface AiActionDraftPayload {
  type?: string;
  status?: string;
  requires_human_confirmation?: boolean;
  params?: Record<string, unknown>;
  lines?: AiActionDraftLine[];
  [key: string]: unknown;
}

export interface AiActionDraft {
  id: number;
  draft_type: string;
  status: AiActionDraftStatus;
  title: string;
  source_tool?: string | null;
  payload?: AiActionDraftPayload | null;
  result_type?: string | null;
  result_id?: string | null;
  note?: string | null;
  created_by?: number | null;
  confirmed_by?: number | null;
  confirmed_at?: string | null;
  rejected_by?: number | null;
  rejected_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AiDraftConfirmResult {
  draft: AiActionDraft;
  replenishment_suggestion_ids?: Array<number | string>;
  created_purchase_order?: boolean;
  requires_next_human_confirmation?: boolean;
}

export interface AiDraftRejectResult {
  draft: AiActionDraft;
}

export interface AiSettings {
  analysis_mode: 'local' | 'hybrid' | 'external';
  local_analysis_enabled: boolean;
  external_configured: boolean;
  external_source: 'user' | 'system' | 'none' | string;
  external_base: string;
  credential_masked: string;
  model: string;
  can_use_local: boolean;
  has_user_credential: boolean;
  preferences_updated_at?: string | null;
  dashboard_scope?: 'operations' | 'finance' | 'supply' | 'fulfillment' | string;
}

export interface DeploymentReadinessCheck {
  key: string;
  label: string;
  scope: 'frontend' | 'backend' | 'platform' | string;
  status: 'ready' | 'attention' | 'blocked' | string;
  evidence: string;
  action: string;
}

export interface DeploymentReadiness {
  generated_at: string;
  source: string;
  summary: {
    score: number;
    level: 'ready' | 'attention' | 'blocked' | string;
    ready: number;
    attention: number;
    blocked: number;
    total: number;
    next_action: string;
    frontend_boundary: string;
    backend_boundary: string;
  };
  checks: DeploymentReadinessCheck[];
  service_snapshot: {
    services: number;
    domains: Array<{ domain: string; services: number; attention: number; records: number; avg_readiness: number }>;
    avg_readiness: number;
    avg_contract_coverage: number;
    avg_split_score: number;
    deployment_units: string[];
    stores: string[];
    dependencies: number;
    api_surfaces: number;
    split_plan: Array<{
      phase: string;
      services: string[];
      ready: number;
      attention: number;
      avg_split_score: number;
      events: number;
      gateway_routes: number;
    }>;
    observability: {
      coverage: number;
      policy: string;
      missing: string[];
      signals: Array<{ key: string; label: string; ready: number; total: number; coverage: number }>;
    };
    incident_queue: Array<{
      id: string;
      service_id: string;
      title: string;
      priority: 'P0' | 'P1' | 'P2' | string;
      owner: string;
      status: string;
      path: string;
      action: string;
      evidence: string;
      due: string;
      error_budget_remaining: number;
      signal_coverage: number;
      contract_coverage: number;
      runtime_unit: string;
    }>;
  };
  maturity: {
    summary: {
      score: number;
      level: 'ready' | 'attention' | 'blocked' | string;
      target: string;
      dimensions: number;
      ready: number;
      attention: number;
      blocked: number;
      next_action: string;
    };
    dimensions: Array<{
      key: string;
      label: string;
      score: number;
      level: 'ready' | 'attention' | 'blocked' | string;
      evidence: string;
      action: string;
      weight: number;
    }>;
    capability_map: Array<{
      domain: string;
      modules: string[];
      services: number;
      contracts: number;
      api_surfaces: number;
      data_objects: number;
      records: number;
      avg_readiness: number;
      attention: number;
    }>;
    topology_nodes: Array<{
      id: string;
      name: string;
      domain: string;
      owner: string;
      path: string;
      runtime_unit: string;
      store: string;
      readiness: number;
      contract_coverage: number;
      status: 'healthy' | 'attention' | string;
      risk_note: string;
    }>;
    topology_edges: Array<{ from: string; to: string }>;
    evidence: Array<{
      label: string;
      path: string;
      description: string;
      status: 'ready' | 'attention' | 'blocked' | string;
    }>;
  };
  runbook: Array<{
    step: string;
    command: string;
  }>;
}

export interface AiDiagnostics {
  overall_status: 'ready' | 'degraded' | 'attention' | string;
  analysis_mode: AiSettings['analysis_mode'];
  local: {
    available: boolean;
    status: string;
    message: string;
  };
  external: {
    configured: boolean;
    reachable: boolean | null;
    status: string;
    message: string;
    latency_ms: number | null;
    base: string;
    source: string;
    credential_masked: string;
  };
  snapshot: {
    low_stock_count: number;
    pending_purchase_count: number;
    overdue_receivable_count: number;
    overdue_amount: number;
    recent_report_count: number;
  };
  sample_actions: Array<{ title: string; metric: string; path: string }>;
}

export interface ServiceHealth {
  status: 'ok' | 'degraded' | 'down' | string;
  service: string;
  api_base: string;
  timestamp?: string;
  latency_ms: number;
  database: {
    status: 'ready' | 'down' | 'not_checked' | string;
    latency_ms?: number;
    engine?: string;
    message?: string;
  };
  ai: {
    status: 'configured' | 'local' | 'not_configured' | string;
    local_enabled: boolean;
    external_configured: boolean;
    provider: string;
    base_url: string;
    model: string;
  };
  storage: {
    status: 'cloud' | 'local' | 'missing_cloud' | string;
    cloud_configured: boolean;
    cloud_required: boolean;
    requirement: string;
    upload_folder?: string;
    folders?: {
      root?: string | null;
      files?: string | null;
      avatars?: string | null;
      library?: string | null;
    };
    writable?: {
      root?: boolean;
      files?: boolean;
      avatars?: boolean;
      library?: boolean;
    };
  };
  checks: {
    database: boolean;
    ai: boolean;
    storage: boolean;
  };
}

export interface StructuredOperationsAnalysis {
  scenario: 'inventory' | 'procurement' | 'receivables' | 'daily_brief' | string;
  headline: string;
  summary: string;
  generated_at?: string | null;
  insight_cards: Array<{
    title: string;
    metric: string;
    note: string;
    tone: 'success' | 'warning' | 'danger' | string;
    path: string;
  }>;
  action_items: Array<{
    title: string;
    description: string;
    priority: 'high' | 'normal' | string;
    path: string;
    prompt: string;
  }>;
  related_records: {
    low_stock: Array<{ sku: string; name: string; quantity: number; min_stock: number }>;
    pending_purchase: Array<{ po_no: string; supplier: string; amount: number }>;
    overdue_receivables: Array<{ receivable_no: string; customer: string; unpaid: number }>;
    recent_reports: Array<{ name: string; type: string }>;
  };
}

export interface DockItem {
  key: string;
  label: string;
  shortLabel: string;
  path: string;
  activePaths?: string[];
  icon: string;
  group: string;
  dockGroup: 'operations' | 'warehouse' | 'supply' | 'fulfillment' | 'finance' | 'insight' | 'security' | 'collaboration' | 'personal';
  accent: string;
  quickActions: Array<{ label: string; path: string }>;
}

export interface DockGroup {
  key: DockItem['dockGroup'];
  label: string;
  tone: string;
  summary?: string;
  items: DockItem[];
}

export interface TimelineEvent {
  code: string;
  title: string;
  time: string;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info';
}

export interface RelatedRecord {
  label: string;
  value: string;
  meta?: string;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info';
}

export interface BusinessAction {
  label: string;
  icon: string;
  kind: string;
  endpoint?: string;
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  confirm?: string;
}

export interface DetailPageConfig {
  key: string;
  title: string;
  eyebrow: string;
  resource: string;
  backPath: string;
  titleFields: string[];
  subtitleFields: string[];
  heroMetricFields: string[];
  fields: Array<{ key: string; label: string; type?: 'money' | 'number' | 'status' | 'date' | 'percent' }>;
  timeline: TimelineEvent[];
  related: RelatedRecord[];
  actions: BusinessAction[];
}

export interface ModulePageConfig {
  key: string;
  title: string;
  path: string;
  detailPath: string;
  resource: string;
  dock: DockItem;
  visualDensity?: 'compact' | 'balanced' | 'immersive';
  heroVariant?: 'control-tower' | 'material-lab' | 'flow-network' | 'approval-lane' | 'fulfillment-lane' | 'risk-studio' | 'report-studio' | 'security-matrix' | 'scanner-floor' | 'knowledge-studio';
  storyBlocks?: Array<{ title: string; body: string; metric?: string; tone?: 'default' | 'success' | 'warning' | 'danger' | 'info' }>;
}

export interface ActionResult {
  ok: boolean;
  message: string;
  data?: unknown;
}

export type RecordValue = string | number | boolean | null | undefined | Record<string, unknown> | unknown[];
export type DataRecord = Record<string, RecordValue> & { id?: number };
