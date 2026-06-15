import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { RouterLink } from '@angular/router';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { FileUploadHandlerEvent, FileUploadModule } from 'primeng/fileupload';
import { InputTextModule } from 'primeng/inputtext';
import { ProgressBarModule } from 'primeng/progressbar';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { catchError, finalize, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { apiUrl } from '../core/api-url';
import { DataRecord } from '../core/models';
import { chartLegend, dateText, emptyPageResult, recordTitle, textOf } from './page-utils';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, FileUploadModule, InputTextModule, ProgressBarModule, SkeletonModule, TagModule],
  template: `
    <section class="ops-atlas-page file-vault-page">
      <header class="file-vault-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">文件中心</span>
          <h1>文件资料库</h1>
          <p>库位图、供应商报告、盘点模板、SOP 附件和经营报表按类型归档。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="uploadOpen.set(!uploadOpen())" aria-label="打开上传区">
              <i class="pi pi-upload"></i>
              上传文件
            </button>
            <a pButton severity="secondary" routerLink="/app/content/articles">
              <i class="pi pi-book"></i>
              公告知识
            </a>
            <button pButton type="button" severity="info" (click)="load()" aria-label="刷新文件">
              <i class="pi pi-refresh"></i>
              刷新
            </button>
          </div>

          <div class="file-hero-analytics">
            <article>
              <span>归档文件</span>
              <strong>{{ files().length }}</strong>
              <em>{{ totalSize() }}</em>
            </article>
            <article>
              <span>安全类型</span>
              <strong>{{ safeFiles() }}</strong>
              <em>可下载、可追踪</em>
            </article>
            <article>
              <span>当前视图</span>
              <strong>{{ filteredFiles().length }}</strong>
              <em>{{ typeFilter() ? bucketLabel(typeFilter()) : '全部文件' }}</em>
            </article>
          </div>
        </div>

        <aside class="file-type-tower">
          @for (bucket of buckets(); track bucket.key) {
            <button type="button" [class.active]="typeFilter() === bucket.key" (click)="setTypeFilter(bucket.key)">
              <span>{{ bucket.label }}</span>
              <strong>{{ bucket.count }}</strong>
              <em>{{ bucket.size }}</em>
            </button>
          }
        </aside>
      </header>

      <section class="file-vault-insights">
        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">归档结构</span>
              <h2>资料类型结构</h2>
            </div>
            <p-tag severity="success" [value]="files().length + ' 份'" />
          </div>
          <div class="file-vault-chart" echarts [options]="typeChart()"></div>
        </article>
        <article class="atlas-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">容量</span>
              <h2>归档容量分布</h2>
            </div>
            <p-tag severity="info" [value]="totalSize()" />
          </div>
          <div class="file-vault-chart" echarts [options]="sizeChart()"></div>
        </article>
      </section>

      @if (uploadOpen()) {
        <section class="atlas-panel file-upload-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">上传</span>
              <h2>安全上传</h2>
            </div>
            <p-tag severity="success" value="MIME 校验" />
          </div>
          <p-fileupload
            mode="advanced"
            name="file"
            [customUpload]="true"
            [auto]="true"
            [multiple]="false"
            accept=".pdf,.csv,.xlsx,.xls,.doc,.docx,.png,.jpg,.jpeg,.txt"
            chooseLabel="选择文件"
            uploadLabel="上传"
            cancelLabel="取消"
            (uploadHandler)="uploadFile($event)"
          >
            <ng-template pTemplate="empty">
              <div class="upload-empty">
                <i class="pi pi-cloud-upload"></i>
                <strong>拖入仓库图纸、供应商报告、盘点模板或 SOP 文件</strong>
                <span>禁止脚本、网页、可执行文件和 SVG 等危险类型。</span>
              </div>
            </ng-template>
          </p-fileupload>
          <label class="native-upload-control">
            <span>{{ uploading() ? '正在写入资料库' : '选择本地文件上传' }}</span>
            <input
              type="file"
              accept=".pdf,.csv,.xlsx,.xls,.doc,.docx,.png,.jpg,.jpeg,.txt"
              [disabled]="uploading()"
              (change)="uploadNativeFile($event)"
            />
          </label>
        </section>
      }

      <section class="file-vault-grid">
        <article class="atlas-panel file-library-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">文件库</span>
              <h2>文件资料库</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="onQueryChange($event)" placeholder="搜索文件名、类型" />
            </div>
          </div>

          @if (loading()) {
            <p-skeleton height="78px" />
            <p-skeleton height="78px" />
            <p-skeleton height="78px" />
          } @else if (error()) {
            <div class="empty-state">
              <i class="pi pi-cloud"></i>
              <strong>文件数据通道未连接</strong>
              <p>{{ error() }}</p>
              <button pButton type="button" (click)="load()">重试</button>
            </div>
          } @else {
            <div class="file-card-grid">
              @for (file of visibleFiles(); track file.id) {
                <article class="file-card clickable" [routerLink]="['/app/files', file.id]" tabindex="0" [attr.aria-label]="'查看文件 ' + text(file, 'filename')">
                  <div class="file-icon" [class]="fileTone(file)">
                    <i class="pi" [class]="fileIcon(file)"></i>
                  </div>
                  <div>
                    <p-tag [severity]="fileSeverity(file)" [value]="fileTypeLabel(file)" />
                    <strong>{{ text(file, 'filename') }}</strong>
                    <span>{{ text(file, 'mimetype') }}</span>
                    <em>{{ fileSize(file['size']) }} / {{ date(file['created_at']) }}</em>
                  </div>
                  <footer>
                    <button pButton type="button" [text]="true" (click)="downloadFile(file, $event)" [loading]="downloadingId() === file.id">
                      <i class="pi pi-download"></i>
                      下载
                    </button>
                    <span class="file-detail-chip">
                      <i class="pi pi-eye"></i>
                      详情
                    </span>
                  </footer>
                </article>
              }
              @if (!visibleFiles().length) {
                <div class="empty-state compact">
                  <i class="pi pi-folder-open"></i>
                  <strong>没有匹配文件</strong>
                  <p>上传业务文件或切换文件类型。</p>
                </div>
              }
            </div>
            @if (filteredFiles().length > pageSize()) {
              <div class="atlas-pagination" aria-label="文件分页">
                <button type="button" (click)="setPage(currentPage() - 1)" [disabled]="currentPage() <= 1">
                  <i class="pi pi-angle-left"></i>
                  上一页
                </button>
                <span>第 <strong>{{ currentPage() }}</strong> / {{ totalPages() }} 页 · {{ filteredFiles().length }} 份文件</span>
                <label>
                  跳至
                  <input pInputText [ngModel]="pageInput" (ngModelChange)="pageInput = $event" (keydown.enter)="jumpPage()" inputmode="numeric" />
                </label>
                <button type="button" (click)="jumpPage()">跳转</button>
                <button type="button" (click)="setPage(currentPage() + 1)" [disabled]="currentPage() >= totalPages()">
                  下一页
                  <i class="pi pi-angle-right"></i>
                </button>
              </div>
            }
          }
        </article>

        <aside class="atlas-panel file-governance-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">治理</span>
              <h2>文件治理</h2>
            </div>
          </div>
          <div class="file-governance-list">
            <article>
              <span>安全类型</span>
              <strong>{{ safeFiles() }}</strong>
              <em>PDF / Office / 图片 / 文本</em>
            </article>
            <article>
              <span>归档容量</span>
              <strong>{{ totalSize() }}</strong>
              <em>数据库附件记录</em>
            </article>
            <article>
              <span>资料联动</span>
              <strong>公告 / 报表</strong>
              <em>从内容中心引用</em>
            </article>
          </div>
          <p>文件下载接口会校验会话和权限，文件上传会拒绝危险扩展名和 MIME 类型。</p>
        </aside>
      </section>
    </section>
  `
})
export class FilesPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly http = inject(HttpClient);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly error = signal('');
  protected readonly files = signal<DataRecord[]>([]);
  protected readonly typeFilter = signal('');
  protected readonly uploadOpen = signal(false);
  protected readonly uploading = signal(false);
  protected readonly downloadingId = signal<number | null>(null);
  protected readonly pageSize = signal(12);
  protected readonly page = signal(1);
  protected pageInput = '1';
  protected query = '';

  protected readonly filteredFiles = computed(() => {
    const q = this.query.trim().toLowerCase();
    const type = this.typeFilter();
    return this.files().filter(file => {
      const bucket = this.fileBucket(file).key;
      const haystack = [textOf(file, 'filename'), textOf(file, 'mimetype')].join(' ').toLowerCase();
      return (!type || bucket === type) && (!q || haystack.includes(q));
    });
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.filteredFiles().length / this.pageSize())));
  protected readonly currentPage = computed(() => Math.min(this.page(), this.totalPages()));
  protected readonly visibleFiles = computed(() => {
    const start = (this.currentPage() - 1) * this.pageSize();
    return this.filteredFiles().slice(start, start + this.pageSize());
  });
  protected readonly buckets = computed(() => {
    const bucketMap = new Map<string, { key: string; label: string; count: number; bytes: number }>();
    for (const file of this.files()) {
      const meta = this.fileBucket(file);
      const bucket = bucketMap.get(meta.key) ?? { key: meta.key, label: meta.label, count: 0, bytes: 0 };
      bucket.count += 1;
      bucket.bytes += Number(file['size'] ?? 0);
      bucketMap.set(meta.key, bucket);
    }
    const result = [...bucketMap.values()].map(item => ({ ...item, size: this.fileSize(item.bytes) }));
    return [{ key: '', label: '全部文件', count: this.files().length, bytes: this.files().reduce((sum, file) => sum + Number(file['size'] ?? 0), 0), size: this.totalSize() }, ...result];
  });
  protected readonly typeChart = computed<EChartsCoreOption>(() => {
    const data = this.buckets()
      .filter(bucket => bucket.key)
      .map(bucket => ({ name: bucket.label, value: bucket.count }));
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: chartLegend('bottom', 'rgba(100,116,139,.95)'),
      series: [{
        type: 'pie',
        radius: ['46%', '72%'],
        center: ['50%', '43%'],
        itemStyle: { borderRadius: 10, borderWidth: 2, borderColor: 'rgba(255,255,255,.56)' },
        data: data.length ? data : [{ name: '资料库', value: 1 }]
      }]
    };
  });
  protected readonly sizeChart = computed<EChartsCoreOption>(() => {
    const buckets = this.buckets().filter(bucket => bucket.key);
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 18, right: 16, top: 26, bottom: 30, containLabel: true },
      xAxis: {
        type: 'category',
        data: buckets.map(bucket => bucket.label),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: 'rgba(100,116,139,.95)', interval: 0, rotate: buckets.length > 4 ? 18 : 0 }
      },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } } },
      series: [{
        name: '容量 KB',
        type: 'bar',
        data: buckets.map(bucket => Math.max(1, Math.round(bucket.bytes / 1024))),
        barWidth: 22,
        itemStyle: { color: '#0f8f86', borderRadius: [10, 10, 2, 2] }
      }]
    };
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.list<DataRecord>('files', { page: 1, page_size: 120, q: this.query, sort: 'created_at', order: 'desc' }).pipe(
      catchError(error => {
        this.error.set(error?.message || '无法读取文件数据。');
        return of(emptyPageResult<DataRecord>());
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(result => {
      this.files.set(result.items);
      this.setPage(1);
    });
  }

  setTypeFilter(type: string): void {
    this.typeFilter.set(type);
    this.setPage(1);
  }

  onQueryChange(value: string): void {
    this.query = value;
    this.setPage(1);
  }

  setPage(page: number): void {
    const next = Math.min(Math.max(1, Math.trunc(page || 1)), this.totalPages());
    this.page.set(next);
    this.pageInput = String(next);
  }

  jumpPage(): void {
    this.setPage(Number(this.pageInput) || 1);
  }

  uploadFile(event: FileUploadHandlerEvent): void {
    const file = event.files?.[0];
    this.uploadSelectedFile(file);
  }

  uploadNativeFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    this.uploadSelectedFile(file, () => {
      input.value = '';
    });
  }

  private uploadSelectedFile(file: File | undefined, done?: () => void): void {
    if (!file) {
      this.messages.add({ severity: 'warn', summary: '上传文件', detail: '请选择文件。' });
      done?.();
      return;
    }
    if (this.uploading()) {
      done?.();
      return;
    }
    const form = new FormData();
    form.append('file', file, file.name);
    this.uploading.set(true);
    this.api.postForm<DataRecord>('files/upload', form).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '上传失败', detail: error?.message || '文件类型或权限不满足要求。' });
        return of(null);
      }),
      finalize(() => {
        this.uploading.set(false);
        done?.();
      })
    ).subscribe(result => {
      if (result) {
        this.messages.add({ severity: 'success', summary: '上传成功', detail: recordTitle(result) });
        this.files.set([result, ...this.files()]);
        this.uploadOpen.set(false);
      }
    });
  }

  downloadHref(file: DataRecord): string {
    const url = textOf(file, 'download_url', '');
    return apiUrl(url || `/api/v1/files/${file.id}/download`);
  }

  downloadFile(file: DataRecord, event?: Event): void {
    event?.preventDefault();
    event?.stopPropagation();
    if (!file.id || this.downloadingId()) {
      return;
    }
    this.downloadingId.set(file.id);
    this.http.get(this.downloadHref(file), { responseType: 'blob', withCredentials: true }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '下载失败', detail: error?.message || '文件下载接口未返回内容。' });
        return of(null);
      }),
      finalize(() => this.downloadingId.set(null))
    ).subscribe(blob => {
      if (!blob) {
        return;
      }
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = textOf(file, 'filename', `nexus-file-${file.id}`);
      anchor.click();
      URL.revokeObjectURL(url);
      this.messages.add({ severity: 'success', summary: '下载已开始', detail: textOf(file, 'filename') });
    });
  }

  fileBucket(file: DataRecord): { key: string; label: string } {
    const name = textOf(file, 'filename').toLowerCase();
    const mime = textOf(file, 'mimetype').toLowerCase();
    if (mime.includes('pdf') || name.endsWith('.pdf')) {
      return { key: 'pdf', label: 'PDF 图纸' };
    }
    if (mime.includes('spreadsheet') || mime.includes('excel') || name.endsWith('.xlsx') || name.endsWith('.xls') || name.endsWith('.csv')) {
      return { key: 'sheet', label: '表格报表' };
    }
    if (mime.includes('word') || name.endsWith('.docx') || name.endsWith('.doc')) {
      return { key: 'doc', label: '文档 SOP' };
    }
    if (mime.includes('image')) {
      return { key: 'image', label: '现场图片' };
    }
    return { key: 'other', label: '其他资料' };
  }

  fileIcon(file: DataRecord): string {
    const bucket = this.fileBucket(file).key;
    return {
      pdf: 'pi-file-pdf',
      sheet: 'pi-table',
      doc: 'pi-file-word',
      image: 'pi-image',
      other: 'pi-file'
    }[bucket] ?? 'pi-file';
  }

  fileTone(file: DataRecord): string {
    return `tone-${this.fileBucket(file).key}`;
  }

  fileSeverity(file: DataRecord): 'success' | 'secondary' | 'info' | 'warn' | 'danger' | 'contrast' {
    return this.fileBucket(file).key === 'other' ? 'warn' : 'success';
  }

  fileTypeLabel(file: DataRecord): string {
    return this.fileBucket(file).label;
  }

  bucketLabel(key: string): string {
    return this.buckets().find(bucket => bucket.key === key)?.label ?? '文件视图';
  }

  fileSize(value: unknown): string {
    const bytes = Number(value ?? 0);
    if (bytes > 1024 * 1024) {
      return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }
    if (bytes > 1024) {
      return `${Math.round(bytes / 1024)} KB`;
    }
    return `${bytes} B`;
  }

  totalSize(): string {
    return this.fileSize(this.files().reduce((sum, file) => sum + Number(file['size'] ?? 0), 0));
  }

  safeFiles(): number {
    return this.files().filter(file => this.fileBucket(file).key !== 'other').length;
  }

  text(row: DataRecord | null | undefined, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  date(value: unknown): string {
    return dateText(value);
  }
}
