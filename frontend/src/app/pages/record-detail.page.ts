import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ConfirmationService, MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { ProgressBarModule } from 'primeng/progressbar';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';
import { catchError, finalize, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { apiUrl } from '../core/api-url';
import { BusinessAction, DataRecord, DetailPageConfig } from '../core/models';
import { DETAIL_CONFIGS, DetailKey } from './detail-data';

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, RouterLink, ButtonModule, ProgressBarModule, SkeletonModule, TagModule, TooltipModule],
  template: `
    <section class="detail-page" [class.file-detail-page]="config().key === 'files'">
      <a class="detail-back" [routerLink]="config().backPath">
        <i class="pi pi-arrow-left"></i>
        返回{{ config().title.replace('详情', '') }}
      </a>

      @if (loading()) {
        <div class="detail-shell skeleton">
          <p-skeleton height="46px" />
          <p-skeleton height="120px" />
          <p-skeleton height="260px" />
        </div>
      } @else if (error()) {
        <div class="empty-state detail-error">
          <i class="pi pi-cloud"></i>
          <strong>详情数据通道未连接</strong>
          <p>{{ error() }}</p>
          <button pButton type="button" (click)="load()">重试</button>
        </div>
      } @else {
        <header class="detail-hero">
          <div class="detail-title">
            <span class="eyebrow">{{ config().eyebrow }}</span>
            <h1>{{ detailTitle() }}</h1>
            <p>{{ detailSubtitle() }}</p>
          </div>
          <div class="detail-actions">
            @for (action of config().actions; track action.label) {
              <button pButton type="button" [severity]="actionSeverity(action)" (click)="runAction(action)" [attr.aria-label]="action.label">
                <i class="pi" [class]="action.icon"></i>
                {{ action.label }}
              </button>
            }
          </div>
        </header>

        <section class="detail-metrics" aria-label="业务摘要">
          @for (field of metricFields(); track field.key) {
            <article class="detail-metric">
              <span>{{ field.label }}</span>
              <strong>{{ formatValue(record()[field.key], field.type) }}</strong>
            </article>
          }
        </section>

        <section class="detail-flow-board" aria-label="详情业务闭环">
          @for (card of detailFlowCards(); track card.title) {
            <article [ngClass]="card.tone">
              <div>
                <i class="pi" [class]="card.icon"></i>
                <span>{{ card.kicker }}</span>
              </div>
              <strong>{{ card.title }}</strong>
              <p>{{ card.body }}</p>
              <em>{{ card.metric }}</em>
            </article>
          }
        </section>

        @if (config().key === 'files') {
          <section class="detail-card file-detail-preview" aria-label="文件详情">
            <div class="file-detail-visual">
              <i class="pi" [class]="fileIconClass()"></i>
            </div>
            <div class="file-detail-meta">
              <span class="eyebrow">资料库文件</span>
              <h2>{{ detailTitle() }}</h2>
              <p>{{ formatFileSize(record()['size']) }} · {{ formatValue(record()['created_at'], 'date') }} · {{ record()['mimetype'] || '未知类型' }}</p>
              <div class="audit-strip file-audit-strip">
                <div><span>下载</span><strong>权限校验</strong></div>
                <div><span>审计</span><strong>动作留痕</strong></div>
                <div><span>来源</span><strong>文件资料库</strong></div>
              </div>
            </div>
            <div class="file-detail-download">
              <button pButton type="button" (click)="downloadCurrentFile()" aria-label="下载当前文件">
                <i class="pi pi-download"></i>
                下载文件
              </button>
              <a pButton severity="secondary" routerLink="/app/files">
                <i class="pi pi-folder-open"></i>
                返回文件库
              </a>
            </div>
          </section>
        }

        <section class="detail-layout">
          <article class="detail-card field-card">
            <div class="panel-title">
              <div>
                <span class="eyebrow">关键字段</span>
                <h2>关键字段</h2>
              </div>
            </div>
            <div class="field-grid">
              @for (field of config().fields; track field.key) {
                <div class="field-row">
                  <span>{{ field.label }}</span>
                  <strong [class.status-text]="field.type === 'status'">{{ formatValue(record()[field.key], field.type) }}</strong>
                </div>
              }
            </div>
          </article>

          <article class="detail-card timeline-card">
            <div class="panel-title">
              <div>
                <span class="eyebrow">状态时间线</span>
                <h2>状态时间线</h2>
              </div>
            </div>
            <div class="detail-timeline">
              @for (event of config().timeline; track event.code) {
                <div class="detail-timeline-item" [class]="event.tone ?? 'default'">
                  <span>{{ event.code }}</span>
                  <strong>{{ event.title }}</strong>
                  <em>{{ event.time }}</em>
                </div>
              }
            </div>
          </article>

          <article class="detail-card related-card">
            <div class="panel-title">
              <div>
                <span class="eyebrow">关联对象</span>
                <h2>关联对象</h2>
              </div>
            </div>
            <div class="related-list">
              @for (item of config().related; track item.label) {
                <a [routerLink]="linkOrNull(item.meta)" [class.disabled]="!isRoute(item.meta)" [class]="item.tone ?? 'default'">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                  <em>{{ item.meta }}</em>
                </a>
              }
            </div>
          </article>

          <article class="detail-card audit-card">
            <div class="panel-title">
              <div>
                <span class="eyebrow">动作审计</span>
                <h2>动作留痕</h2>
              </div>
            </div>
            <div class="audit-strip">
              <div><span>权限</span><strong>已校验</strong></div>
              <div><span>CSRF</span><strong>写请求保护</strong></div>
              <div><span>事务</span><strong>领域动作提交</strong></div>
            </div>
            <p>{{ auditCopy() }}</p>
          </article>
        </section>
      }
    </section>
  `
})
export class RecordDetailPage implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ApiService);
  private readonly http = inject(HttpClient);
  private readonly messages = inject(MessageService);
  private readonly confirm = inject(ConfirmationService);

  protected readonly loading = signal(false);
  protected readonly error = signal('');
  protected readonly record = signal<DataRecord>({});
  protected readonly config = signal<DetailPageConfig>(DETAIL_CONFIGS.products);
  protected readonly id = signal(0);
  protected readonly metricFields = computed(() => {
    const config = this.config();
    return config.heroMetricFields.map(key => config.fields.find(field => field.key === key) ?? { key, label: key });
  });
  protected readonly detailTitle = computed(() => firstFilled(this.record(), this.config().titleFields) || `${this.config().title} #${this.id()}`);
  protected readonly detailSubtitle = computed(() => {
    const parts = this.config().subtitleFields.map(field => this.formatValue(this.record()[field])).filter(Boolean);
    return parts.length ? parts.join(' · ') : '业务对象详情';
  });
  protected readonly detailFlowCards = computed(() => buildDetailFlowCards(this.config(), this.record()));

  ngOnInit(): void {
    this.route.data.subscribe(data => {
      this.config.set(DETAIL_CONFIGS[(data['detail'] as DetailKey) ?? 'products']);
      this.id.set(Number(this.route.snapshot.paramMap.get('id') ?? 0));
      this.load();
    });
  }

  load(): void {
    const config = this.config();
    const id = this.id();
    this.loading.set(true);
    this.error.set('');
    this.api.get<DataRecord>(`${config.resource}/${id}`).pipe(
      catchError(error => {
        this.record.set({});
        this.error.set(error?.message || '详情数据没有返回，请确认记录是否存在。');
        return of(null);
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(record => {
      if (record) {
        this.record.set(record);
      }
    });
  }

  runAction(action: BusinessAction): void {
    if (action.kind === 'refresh') {
      this.load();
      return;
    }
    if (action.kind === 'download-file') {
      this.downloadCurrentFile(action);
      return;
    }
    this.confirm.confirm({
      header: action.label,
      message: action.confirm ?? `确认执行「${action.label}」？`,
      acceptLabel: '确认',
      rejectLabel: '取消',
      accept: () => this.commitAction(action)
    });
  }

  commitAction(action: BusinessAction): void {
    const request = this.actionRequest(action);
    if (!request) {
      this.messages.add({ severity: 'warn', summary: action.label, detail: '请确认该记录状态满足动作条件。' });
      return;
    }
    request.pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: `${action.label} 未完成`, detail: error?.message || '业务状态不满足执行条件，请检查权限和记录状态。' });
        return of(null);
      })
    ).subscribe(result => {
      if (result !== null) {
        this.messages.add({ severity: 'success', summary: action.label, detail: '业务接口已执行，详情数据已刷新。' });
        this.load();
      }
    });
  }

  actionSeverity(action: BusinessAction): 'primary' | 'secondary' | 'success' | 'info' | 'warn' | 'danger' {
    if (action.kind.includes('freeze')) {
      return 'danger';
    }
    if (action.kind.includes('approve') || action.kind.includes('complete') || action.kind.includes('payment')) {
      return 'success';
    }
    if (action.kind.includes('receive') || action.kind.includes('ship') || action.kind.includes('generate')) {
      return 'info';
    }
    return 'secondary';
  }

  formatValue(value: unknown, type?: string): string {
    if (value === null || value === undefined || value === '') {
      return '-';
    }
    if (type === 'money') {
      return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 0 }).format(Number(value ?? 0));
    }
    if (type === 'percent') {
      return `${Math.max(0, Math.min(100, Math.round(Number(value ?? 0))))}%`;
    }
    if (type === 'date') {
      return String(value).replace('T', ' ').slice(0, 16);
    }
    if (type === 'status') {
      return statusLabel(value);
    }
    if (Array.isArray(value)) {
      return value.length ? `${value.length} 条关联记录` : '无关联记录';
    }
    if (typeof value === 'object') {
      return this.objectSummary(value);
    }
    return String(value);
  }

  private objectSummary(value: object): string {
    const record = value as Record<string, unknown>;
    const preferredKeys = ['name', 'title', 'code', 'sku', 'order_no', 'warehouse_name', 'customer_name', 'supplier_name', 'label'];
    const parts = preferredKeys
      .map(key => record[key])
      .filter(item => item !== null && item !== undefined && item !== '')
      .map(item => String(item));
    if (parts.length) {
      return parts.slice(0, 2).join(' · ');
    }
    return `${Object.keys(record).length} 个业务字段`;
  }

  auditCopy(): string {
    const title = this.detailTitle();
    return `${title} 的审批、收货、发货、收款、下载或权限变更都会进入审计链路。`;
  }

  isRoute(value?: string): boolean {
    return Boolean(value?.startsWith('/app/'));
  }

  linkOrNull(value?: string): string | null {
    return this.isRoute(value) ? value ?? null : null;
  }

  private actionRequest(action: BusinessAction) {
    let endpoint = action.kind === 'complete-stocktake'
      ? this.stocktakeActionEndpoint(action)
      : action.endpoint?.replace(':id', String(this.id()));
    if (action.kind === 'count-stocktake') {
      endpoint = `stocktakes/${this.id()}/count`;
    }
    if (!endpoint) {
      return null;
    }
    const body = this.actionBody(action);
    if (action.method === 'GET') {
      return this.api.get(endpoint);
    }
    if (action.method === 'PATCH') {
      return this.api.patch(endpoint, body);
    }
    if (action.method === 'PUT') {
      return this.api.put(endpoint, body);
    }
    return this.api.post(endpoint, body);
  }

  downloadCurrentFile(action: BusinessAction = { label: '下载文件', icon: 'pi-download', kind: 'download-file' }): void {
    const id = this.id();
    if (!id) {
      this.messages.add({ severity: 'warn', summary: action.label, detail: '文件记录不存在。' });
      return;
    }
    const record = this.record();
    const url = this.downloadHref(record, id);
    this.http.get(url, { responseType: 'blob', withCredentials: true }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '下载失败', detail: error?.message || '文件下载接口未返回内容。' });
        return of(null);
      })
    ).subscribe(blob => {
      if (!blob) {
        return;
      }
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = firstFilled(record, ['filename', 'title']) || `nexus-file-${id}`;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
      this.messages.add({ severity: 'success', summary: '下载已开始', detail: firstFilled(record, ['filename', 'title']) || `#${id}` });
    });
  }

  private downloadHref(record: DataRecord, id: number): string {
    const url = String(record['download_url'] ?? '');
    return apiUrl(url || `/api/v1/files/${id}/download`);
  }

  fileIconClass(): string {
    const name = String(this.record()['filename'] ?? '').toLowerCase();
    const mime = String(this.record()['mimetype'] ?? '').toLowerCase();
    if (mime.includes('pdf') || name.endsWith('.pdf')) {
      return 'pi-file-pdf';
    }
    if (mime.includes('spreadsheet') || mime.includes('excel') || name.endsWith('.xlsx') || name.endsWith('.xls') || name.endsWith('.csv')) {
      return 'pi-table';
    }
    if (mime.includes('word') || name.endsWith('.docx') || name.endsWith('.doc')) {
      return 'pi-file-word';
    }
    if (mime.includes('image')) {
      return 'pi-image';
    }
    return 'pi-file';
  }

  formatFileSize(value: unknown): string {
    const bytes = Number(value ?? 0);
    if (bytes > 1024 * 1024) {
      return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }
    if (bytes > 1024) {
      return `${Math.round(bytes / 1024)} KB`;
    }
    return `${bytes} B`;
  }

  private actionBody(action: BusinessAction): Record<string, unknown> {
    const record = this.record();
    if (action.kind === 'record-payment') {
      return {
        amount: Number(record['unpaid_amount'] ?? 0) || Math.max(1, Number(record['total_amount'] ?? 0) - Number(record['paid_amount'] ?? 0)),
        payment_method: 'bank',
        reference_no: `PAY-${Date.now()}`,
        remark: '银行回款'
      };
    }
    if (action.kind === 'receive-purchase') {
      const items = Array.isArray(record['items']) ? record['items'] as DataRecord[] : [];
      return {
        items: items
          .filter(item => Number(item['pending_qty'] ?? 0) > 0)
          .map(item => ({ item_id: item.id, receive_qty: Math.max(1, Number(item['pending_qty'] ?? 1)) }))
      };
    }
    if (action.kind === 'ship-order') {
      const status = String(record['status'] ?? '');
      return { status: status === 'pending' ? 'paid' : status === 'shipped' ? 'done' : 'shipped', remark: '销售履约推进' };
    }
    if (action.kind === 'freeze-credit') {
      return { reason: '逾期风险控制' };
    }
    if (action.kind === 'complete-stocktake') {
      const status = String(record['status'] ?? '');
      const items = Array.isArray(record['items']) ? record['items'] as DataRecord[] : [];
      const uncounted = items.filter(item => item['actual_qty'] === null || item['actual_qty'] === undefined);
      if (status === 'draft' || status === 'planned') {
        return { start_only: true };
      }
      if ((status === 'in_progress' || status === 'counting') && uncounted.length) {
        return {
          items: uncounted.slice(0, 12).map(item => ({
            item_id: item.id,
            actual_qty: Number(item['system_qty'] ?? 0),
            remark: '现场扫码录入'
          }))
        };
      }
      return { auto_adjust: true };
    }
    if (action.kind === 'count-stocktake') {
      const items = Array.isArray(record['items']) ? record['items'] as DataRecord[] : [];
      const target = items.find(item => item['actual_qty'] === null || item['actual_qty'] === undefined) ?? items[0];
      return target?.id ? { items: [{ item_id: target.id, actual_qty: Number(target['system_qty'] ?? 0), remark: '现场扫码录入' }] } : { items: [] };
    }
    if (action.kind === 'mark-read') {
      return { is_read: true };
    }
    if (action.kind === 'customer-followup') {
      return {
        customer_id: this.id(),
        title: `客户经营跟进 - ${firstFilled(record, ['name', 'customer_name']) || `#${this.id()}`}`,
        content: '请复核客户订单履约、应收账龄、信用占用和近期协作记录。',
        type: 'warning'
      };
    }
    return { remark: '业务动作执行' };
  }

  private stocktakeActionEndpoint(action: BusinessAction): string {
    const record = this.record();
    const status = String(record['status'] ?? '');
    const items = Array.isArray(record['items']) ? record['items'] as DataRecord[] : [];
    const hasUncounted = items.some(item => item['actual_qty'] === null || item['actual_qty'] === undefined);
    if (action.kind === 'complete-stocktake') {
      if (status === 'draft' || status === 'planned') {
        return `stocktakes/${this.id()}/start`;
      }
      if ((status === 'in_progress' || status === 'counting') && hasUncounted) {
        return `stocktakes/${this.id()}/count`;
      }
    }
    return action.endpoint?.replace(':id', String(this.id())) ?? '';
  }
}

function firstFilled(record: DataRecord, fields: string[]): string {
  for (const field of fields) {
    const value = record[field];
    if (value !== null && value !== undefined && value !== '') {
      return String(value);
    }
  }
  return '';
}

function statusLabel(value: unknown): string {
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
    counting: '盘点中',
    planned: '已计划',
    true: '是',
    false: '否',
    published: '已发布'
  };
  return map[raw] ?? raw;
}

function buildDetailFlowCards(config: DetailPageConfig, record: DataRecord) {
  const value = (keys: string[], emptyText: string) => {
    const found = keys.map(key => record[key]).find(item => item !== null && item !== undefined && item !== '');
    return found === undefined ? emptyText : String(found);
  };
  const amount = (key: string, emptyText: string) => {
    const raw = Number(record[key] ?? 0);
    return raw ? new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 0 }).format(raw) : emptyText;
  };
  const cards: Record<string, Array<{ icon: string; kicker: string; title: string; body: string; metric: string; tone: string }>> = {
    products: [
      { icon: 'pi-box', kicker: '水位', title: value(['name', 'sku'], '伺服电机组件'), body: '主数据、批次、供应商和安全库存共同呈现当前物料状态。', metric: value(['total_stock'], '168'), tone: 'info' },
      { icon: 'pi-map-marker', kicker: '库位', title: value(['warehouse_name', 'shelf_location'], '华东工厂仓 A区-03-02'), body: '详情页把库存对象落到仓库与库位，方便现场复核。', metric: '批次', tone: 'success' },
      { icon: 'pi-bolt', kicker: '下一步', title: '生成补货建议', body: '低于安全线时直接进入采购补货中心，避免手工传递。', metric: '补货', tone: 'warning' }
    ],
    stock: [
      { icon: 'pi-warehouse', kicker: '位置', title: value(['warehouse_name'], '华东工厂仓'), body: '库存详情聚焦仓、区、位和当前可用量。', metric: value(['quantity'], '88'), tone: 'info' },
      { icon: 'pi-directions', kicker: '流水', title: '采购/调拨/出库流水', body: '每次库存变化都可以追到来源动作。', metric: '流向', tone: 'success' },
      { icon: 'pi-qrcode', kicker: '复核', title: '盘点复核', body: '异常库位可进入扫码盘点与差异确认。', metric: '扫码', tone: 'warning' }
    ],
    replenishment: [
      { icon: 'pi-exclamation-triangle', kicker: '信号', title: value(['product_name'], 'MRO 备件包'), body: '建议来自安全库存、现存量和交期。', metric: value(['suggested_qty'], '160'), tone: 'warning' },
      { icon: 'pi-shopping-cart', kicker: '转采购', title: '转采购草稿', body: '接受建议后自动带入物料、仓库和建议量。', metric: '采购单', tone: 'success' },
      { icon: 'pi-star', kicker: '供应商', title: '供应商推荐', body: '准点率与质检稳定性决定优先供应商。', metric: '91%', tone: 'info' }
    ],
    purchaseOrders: [
      { icon: 'pi-file-check', kicker: '审批', title: value(['po_no'], 'PO-20260529-A118'), body: '采购单从补货来源进入审批队列。', metric: amount('total_amount', '¥153,600'), tone: 'warning' },
      { icon: 'pi-inbox', kicker: '收货', title: '收货入库', body: '收货进度会更新库存水位并写入流水。', metric: value(['receive_progress'], '64') + '%', tone: 'success' },
      { icon: 'pi-history', kicker: '审计', title: '审批与收货留痕', body: '提交、审批、收货全部进入审计。', metric: '留痕', tone: 'info' }
    ],
    salesOrders: [
      { icon: 'pi-send', kicker: '发货', title: value(['order_no'], 'SO-20260529-0018'), body: '销售详情把订单阶段与仓库出库动作放在同一视图。', metric: amount('total_amount', '¥248,600'), tone: 'success' },
      { icon: 'pi-box', kicker: '库存', title: '库存锁定', body: '发货会扣减库存并生成出库流水。', metric: 'A区', tone: 'info' },
      { icon: 'pi-wallet', kicker: '应收', title: '应收联动', body: '客户发货后进入应收风控和信用占用。', metric: '财务', tone: 'warning' }
    ],
    receivables: [
      { icon: 'pi-shield', kicker: '风险', title: value(['customer_name'], '华南新能源客户群'), body: '账龄、未收金额和信用占用共同决定风险等级。', metric: value(['overdue_days'], '17') + ' 天', tone: 'danger' },
      { icon: 'pi-wallet', kicker: '收款', title: '记录收款', body: '收款动作校验金额边界并释放信用额度。', metric: amount('paid_amount', '¥82,000'), tone: 'success' },
      { icon: 'pi-bell', kicker: '催款', title: '催款/冻结联动', body: '高风险客户可触发催款和信用冻结。', metric: 'P1', tone: 'warning' }
    ],
    credits: [
      { icon: 'pi-percentage', kicker: '占用', title: value(['customer_name'], '长三角装配中心'), body: '额度、已用、可用共同判断客户能否继续信用销售。', metric: value(['usage_rate'], '84') + '%', tone: 'warning' },
      { icon: 'pi-ban', kicker: '冻结', title: '冻结控制', body: '冻结和解冻都进入权限校验与审计。', metric: value(['is_frozen'], 'false'), tone: 'danger' },
      { icon: 'pi-wallet', kicker: '释放', title: '回款释放额度', body: '应收收款后客户履约能力恢复。', metric: amount('available_credit', '¥551,400'), tone: 'success' }
    ],
    stocktakes: [
      { icon: 'pi-qrcode', kicker: '扫码', title: value(['take_no'], 'ST-20260529-01'), body: '扫码录入让盘点详情接近现场操作。', metric: value(['progress'], '64') + '%', tone: 'info' },
      { icon: 'pi-sliders-h', kicker: '差异', title: '差异确认', body: '盘盈盘亏先确认，再生成库存调整。', metric: value(['total_variance_qty'], '+4'), tone: 'warning' },
      { icon: 'pi-check-circle', kicker: '完成', title: '完成盘点', body: '完成后写库存流水和审计日志。', metric: '自动调整', tone: 'success' }
    ],
    reports: [
      { icon: 'pi-chart-bar', kicker: '模板', title: value(['report_name'], '制造仓配经营日报'), body: '报表详情展示模板来源和生成对象。', metric: value(['report_type'], 'daily'), tone: 'info' },
      { icon: 'pi-spinner', kicker: '队列', title: '生成队列', body: '图表、预览、导出状态形成完整产物链。', metric: '72%', tone: 'warning' },
      { icon: 'pi-file-export', kicker: '导出', title: value(['file_path'], 'operations-daily.pdf'), body: '导出后进入文件中心并通知管理层。', metric: 'PDF', tone: 'success' }
    ],
    files: [
      { icon: 'pi-upload', kicker: '类型', title: value(['filename'], '华东工厂仓库位图.pdf'), body: '上传时校验类型并拦截危险文件。', metric: value(['mimetype'], 'PDF'), tone: 'success' },
      { icon: 'pi-eye', kicker: '预览', title: '分类预览', body: '库位图纸、供应商报告和 SOP 附件按业务分类。', metric: '4 类', tone: 'info' },
      { icon: 'pi-lock', kicker: '权限', title: '下载审计', body: '下载前校验权限，下载后写访问日志。', metric: '留痕', tone: 'warning' }
    ],
    articles: [
      { icon: 'pi-book', kicker: '知识', title: value(['title'], '华东工厂仓月末盘点通知'), body: '内容详情承接公告、SOP 和制度发布。', metric: value(['category'], '制度'), tone: 'info' },
      { icon: 'pi-paperclip', kicker: '附件', title: '附件联动', body: '公告可引用文件中心中的图纸、报表和 SOP。', metric: '关联', tone: 'success' },
      { icon: 'pi-send', kicker: '发布', title: '角色触达', body: '发布后推送给仓库、采购和财务角色。', metric: '推送', tone: 'warning' }
    ],
    users: [
      { icon: 'pi-user', kicker: '身份', title: value(['username'], 'warehouse.lead'), body: '用户详情展示身份、部门和角色。', metric: value(['role_name'], '角色'), tone: 'info' },
      { icon: 'pi-lock', kicker: '矩阵', title: '权限矩阵', body: '库存、采购、财务、报表和审计拆分授权。', metric: '6 域', tone: 'success' },
      { icon: 'pi-history', kicker: '审计', title: '动作审计', body: '关键动作与登录风险均可追踪。', metric: '留痕', tone: 'warning' }
    ],
    auditLogs: [
      { icon: 'pi-history', kicker: '事件', title: value(['action'], 'approve'), body: '审计详情按模块、操作者、对象和时间组织。', metric: value(['module'], '模块'), tone: 'info' },
      { icon: 'pi-shield', kicker: '策略', title: '权限结果', body: '审计记录展示动作是否通过边界校验。', metric: '权限', tone: 'success' },
      { icon: 'pi-search', kicker: '复核', title: '追踪回放', body: '可回到相关业务对象复核上下文。', metric: '留痕', tone: 'warning' }
    ],
    notifications: [
      { icon: 'pi-bell', kicker: '收件', title: value(['title'], '库存预警'), body: '通知详情承接业务事件和个人任务。', metric: value(['category'], '通知'), tone: 'warning' },
      { icon: 'pi-check', kicker: '已读', title: '标记已读', body: '处理后回写通知状态并保留动作反馈。', metric: '状态回写', tone: 'success' },
      { icon: 'pi-directions', kicker: '来源', title: '跳回业务源', body: '库存、采购、应收和报表通知都能回到对应模块。', metric: '关联', tone: 'info' }
    ],
    aiSessions: [
      { icon: 'pi-chart-line', kicker: '上下文', title: value(['title'], '经营分析'), body: '经营分析详情引用库存、采购、应收和报表上下文。', metric: '分析', tone: 'info' },
      { icon: 'pi-lightbulb', kicker: '洞察', title: '指标建议', body: '建议可追溯到业务对象和指标来源。', metric: '可追溯', tone: 'success' },
      { icon: 'pi-send', kicker: '行动', title: '转行动草案', body: '分析结果可转补货、催款或报表说明。', metric: '下一步', tone: 'warning' }
    ]
  };
  return cards[config.key] ?? [
    { icon: 'pi-sparkles', kicker: '对象', title: config.title, body: '该详情页展示关键字段、时间线和关联动作。', metric: '更新', tone: 'info' },
    { icon: 'pi-directions', kicker: '流程', title: '关联流程', body: '关键字段、时间线和关联对象共同呈现业务状态。', metric: '下一步', tone: 'success' },
    { icon: 'pi-history', kicker: '审计', title: '动作留痕', body: '详情动作会进入权限和审计闭环。', metric: '留痕', tone: 'warning' }
  ];
}
