import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { MessageService } from 'primeng/api';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { SkeletonModule } from 'primeng/skeleton';
import { TagModule } from 'primeng/tag';
import { TextareaModule } from 'primeng/textarea';
import { catchError, finalize, of } from 'rxjs';

import { ApiService } from '../core/api.service';
import { DataRecord } from '../core/models';
import { chartLegend, dateText, emptyPageResult, recordTitle, statusSeverity, textOf } from './page-utils';

@Component({
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, RouterLink, NgxEchartsDirective, ButtonModule, InputTextModule, SelectModule, SkeletonModule, TagModule, TextareaModule],
  template: `
    <section class="ops-atlas-page content-hub-page">
      <header class="content-hub-hero">
        <div class="hero-narrative">
          <span class="atlas-kicker">知识中心</span>
          <h1>公告与知识库</h1>
          <p>集中发布公告、SOP、制度和协同资料，评论区用于跨岗位跟进执行状态。</p>
          <div class="atlas-actions-row">
            <button pButton type="button" (click)="publishArticle()" [loading]="publishing()" aria-label="发布公告">
              <i class="pi pi-megaphone"></i>
              发布公告
            </button>
            <button pButton type="button" severity="secondary" (click)="draftFromOperations()" aria-label="生成运营简报草稿">
              <i class="pi pi-file-edit"></i>
              运营简报草稿
            </button>
            <a pButton severity="info" routerLink="/app/notifications">
              <i class="pi pi-bell"></i>
              通知触达
            </a>
          </div>
        </div>

        <section class="content-hero-chart" aria-label="内容中心概览图表">
          <div class="hero-chart-head">
            <div>
              <span>知识触达</span>
              <strong>{{ articles().length }}</strong>
            </div>
            <p-tag severity="success" [value]="publishedCount() + ' 已发布'" />
          </div>
          <div class="content-hub-chart" echarts [options]="contentOverviewChart()"></div>
        </section>

        <aside class="content-editor-card">
          <span>快速发布</span>
          <input pInputText [(ngModel)]="draftTitle" placeholder="标题，例如：华东工厂仓月末盘点通知" />
          <p-select [(ngModel)]="draftCategory" [options]="categoryOptions" optionLabel="label" optionValue="value" />
          <textarea pTextarea [(ngModel)]="draftContent" rows="5" placeholder="输入公告、SOP 或协同说明"></textarea>
        </aside>
      </header>

      <section class="content-hub-grid">
        <aside class="atlas-panel content-lanes">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">分类</span>
              <h2>知识分类</h2>
            </div>
            <button pButton type="button" [text]="true" (click)="load()" aria-label="刷新内容">
              <i class="pi pi-refresh"></i>
            </button>
          </div>
          @for (lane of lanes(); track lane.category) {
            <button type="button" class="business-data-row" [class.active]="categoryFilter() === lane.category" (click)="setCategory(lane.category)">
              <span>{{ lane.label }}</span>
              <strong>{{ lane.count }}</strong>
              <em>{{ lane.description }}</em>
            </button>
          }
          <button type="button" class="business-data-row" [class.active]="categoryFilter() === ''" (click)="setCategory('')">
            <span>全部内容</span>
            <strong>{{ articles().length }}</strong>
            <em>公告、SOP、制度和复盘</em>
          </button>
        </aside>

        <article class="atlas-panel content-board">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">看板</span>
              <h2>公告与 SOP 看板</h2>
            </div>
            <div class="atlas-filter">
              <i class="pi pi-search"></i>
              <input pInputText [ngModel]="query" (ngModelChange)="onQueryChange($event)" placeholder="搜索标题、内容、分类" />
            </div>
          </div>

          @if (loading()) {
            <p-skeleton height="88px" />
            <p-skeleton height="88px" />
            <p-skeleton height="88px" />
          } @else if (error()) {
            <div class="empty-state">
              <i class="pi pi-cloud"></i>
              <strong>内容数据通道未连接</strong>
              <p>{{ error() }}</p>
              <button pButton type="button" (click)="load()">重试</button>
            </div>
          } @else {
            <div class="content-card-grid">
              @for (article of visibleArticles(); track article.id) {
                <button type="button" class="content-card business-data-row" [class.active]="selectedArticle()?.id === article.id" (click)="selectArticle(article)">
                  <p-tag [severity]="severity(article['status'])" [value]="statusText(article['status'])" />
                  <strong>{{ text(article, 'title') }}</strong>
                  <p>{{ articleSummary(article) }}</p>
                  <div>
                    <span>{{ text(article, 'category') }} / {{ number(article['comment_count']) }} 条讨论</span>
                    <em>{{ text(article, 'author_name', '系统') }} / {{ date(article['created_at']) }}</em>
                  </div>
                </button>
              }
              @if (!visibleArticles().length) {
                <div class="empty-state compact">
                  <i class="pi pi-book"></i>
                  <strong>没有匹配内容</strong>
                  <p>调整搜索或发布一条新的运营公告。</p>
                </div>
              }
            </div>
            @if (filteredArticles().length > pageSize()) {
              <div class="atlas-pagination" aria-label="内容分页">
                <button type="button" (click)="setPage(currentPage() - 1)" [disabled]="currentPage() <= 1">
                  <i class="pi pi-angle-left"></i>
                  上一页
                </button>
                <span>第 <strong>{{ currentPage() }}</strong> / {{ totalPages() }} 页 · {{ filteredArticles().length }} 条内容</span>
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

        <aside class="atlas-panel content-impact-panel">
          <div class="atlas-panel-head">
            <div>
              <span class="atlas-kicker">触达</span>
              <h2>内容触达</h2>
            </div>
          </div>
          @if (selectedArticle(); as article) {
            <div class="forum-thread-head">
              <img [src]="text(article, 'author_avatar')" [alt]="text(article, 'author_name')" />
              <div>
                <strong>{{ text(article, 'title') }}</strong>
                <span>{{ text(article, 'category') }} / {{ text(article, 'author_name', '系统') }}</span>
              </div>
            </div>

            <div class="forum-thread-list">
              @if (commentsLoading()) {
                <p-skeleton height="54px" />
                <p-skeleton height="54px" />
              } @else {
                @for (comment of comments(); track comment.id) {
                  <article class="forum-comment business-data-row">
                    <img [src]="text(comment, 'author_avatar')" [alt]="text(comment, 'author_name')" />
                    <div>
                      <strong>{{ text(comment, 'author_full_name', text(comment, 'author_name', '成员')) }}</strong>
                      <p>{{ text(comment, 'content') }}</p>
                      <span>{{ date(comment['created_at']) }}</span>
                    </div>
                  </article>
                }
                @if (!comments().length) {
                  <div class="empty-state compact">
                    <i class="pi pi-comments"></i>
                    <strong>讨论区待跟进</strong>
                    <p>发布第一条执行进展或跨部门回复。</p>
                  </div>
                }
              }
            </div>

            <form class="forum-composer" (ngSubmit)="publishComment(article)">
              <textarea pTextarea rows="3" [(ngModel)]="commentDraft" name="commentDraft" placeholder="输入执行进展、异常说明或跨部门回复"></textarea>
              <button pButton type="submit" [loading]="commentPosting()" [disabled]="!commentDraft.trim()">
                <i class="pi pi-send"></i>
                发布回复
              </button>
            </form>
          } @else {
            <div class="content-impact-list">
            <article class="business-data-row">
              <span>已发布</span>
              <strong>{{ publishedCount() }}</strong>
              <em>可在详情页追踪</em>
            </article>
            <article class="business-data-row">
              <span>草稿</span>
              <strong>{{ draftCount() }}</strong>
              <em>待审批发布</em>
            </article>
            <article class="business-data-row">
              <span>分类覆盖</span>
              <strong>{{ lanes().length }}</strong>
              <em>运营、盘点、风控、SOP</em>
            </article>
            </div>
            <p>发布内容后，结合通知中心推送到对应岗位；文件中心可归档附件，审计日志追踪修改和下载。</p>
          }
        </aside>
      </section>
    </section>
  `
})
export class ContentPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly messages = inject(MessageService);

  protected readonly loading = signal(false);
  protected readonly publishing = signal(false);
  protected readonly commentsLoading = signal(false);
  protected readonly commentPosting = signal(false);
  protected readonly error = signal('');
  protected readonly articles = signal<DataRecord[]>([]);
  protected readonly comments = signal<DataRecord[]>([]);
  protected readonly selectedArticle = signal<DataRecord | null>(null);
  protected readonly categoryFilter = signal('');
  protected readonly pageSize = signal(9);
  protected readonly page = signal(1);
  protected pageInput = '1';
  protected query = '';
  protected commentDraft = '';
  protected draftTitle = '华东工厂仓月末盘点通知';
  protected draftCategory = '盘点公告';
  protected draftContent = '请仓库主管、采购补货和财务风控在月末盘点前完成库位复核、在途采购核对、应收风险确认，并将异常写入通知中心。';
  protected readonly categoryOptions = [
    { label: '运营公告', value: '运营公告' },
    { label: '盘点公告', value: '盘点公告' },
    { label: '流程制度', value: '流程制度' },
    { label: '风控规则', value: '风控规则' },
    { label: '供应商协同', value: '供应商协同' }
  ];

  protected readonly filteredArticles = computed(() => {
    const q = this.query.trim().toLowerCase();
    const category = this.categoryFilter();
    return this.articles().filter(article => {
      const matchesCategory = !category || textOf(article, 'category') === category;
      const haystack = [textOf(article, 'title'), textOf(article, 'category'), textOf(article, 'content'), textOf(article, 'content_raw')].join(' ').toLowerCase();
      return matchesCategory && (!q || haystack.includes(q));
    });
  });
  protected readonly totalPages = computed(() => Math.max(1, Math.ceil(this.filteredArticles().length / this.pageSize())));
  protected readonly currentPage = computed(() => Math.min(this.page(), this.totalPages()));
  protected readonly visibleArticles = computed(() => {
    const start = (this.currentPage() - 1) * this.pageSize();
    return this.filteredArticles().slice(start, start + this.pageSize());
  });
  protected readonly publishedCount = computed(() => this.articles().filter(item => item['status'] === 'published').length);
  protected readonly draftCount = computed(() => this.articles().filter(item => item['status'] === 'draft').length);
  protected readonly lanes = computed(() => {
    const meta: Record<string, string> = {
      '运营公告': '日常运营触达',
      '盘点公告': '仓库现场协同',
      '流程制度': 'SOP 与制度',
      '风控规则': '信用与应收规则',
      '供应商协同': '采购到货协同'
    };
    const map = new Map<string, number>();
    for (const article of this.articles()) {
      const category = textOf(article, 'category', '未分类');
      map.set(category, (map.get(category) ?? 0) + 1);
    }
    return [...map.entries()].map(([category, count]) => ({ category, count, label: category, description: meta[category] ?? '知识条目' }));
  });
  protected readonly contentOverviewChart = computed<EChartsCoreOption>(() => {
    const lanes = this.lanes();
    const categories = lanes.length ? lanes.map(item => item.label) : ['运营公告', '盘点公告', '流程制度'];
    const counts = lanes.length ? lanes.map(item => item.count) : [0, 0, 0];
    return {
      backgroundColor: 'transparent',
      color: ['#0f8f86', '#2563eb', '#f0b76a'],
      tooltip: { trigger: 'axis' },
      legend: chartLegend('top', 'rgba(100,116,139,.95)'),
      grid: { left: 18, right: 18, top: 42, bottom: 26, containLabel: true },
      xAxis: {
        type: 'category',
        data: categories,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: 'rgba(100,116,139,.95)', interval: 0, overflow: 'truncate', width: 76 }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(148,163,184,.16)' } },
        axisLabel: { color: 'rgba(100,116,139,.8)' }
      },
      series: [
        {
          name: '内容数',
          type: 'bar',
          data: counts,
          barWidth: 20,
          itemStyle: { color: '#0f8f86', borderRadius: [10, 10, 2, 2] }
        },
        {
          name: '讨论热度',
          type: 'line',
          smooth: true,
          symbolSize: 7,
          data: categories.map(category => this.articles()
            .filter(article => textOf(article, 'category') === category)
            .reduce((sum, article) => sum + Number(article['comment_count'] || 0), 0)
          ),
          lineStyle: { width: 3, color: '#2563eb' },
          areaStyle: { color: 'rgba(37,99,235,.12)' }
        }
      ]
    };
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.list<DataRecord>('articles', { page: 1, page_size: 12, q: this.query, sort: 'created_at', order: 'desc' }).pipe(
      catchError(error => {
        this.error.set(error?.message || '无法读取内容数据。');
        return of(emptyPageResult<DataRecord>());
      }),
      finalize(() => this.loading.set(false))
    ).subscribe(result => {
      this.articles.set(result.items);
      this.setPage(1);
      if (!this.selectedArticle() && result.items.length) {
        this.selectArticle(result.items[0]);
      }
    });
  }

  setCategory(category: string): void {
    this.categoryFilter.set(category);
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

  draftFromOperations(): void {
    this.draftTitle = `制造仓配运营简报 ${new Date().toLocaleDateString('zh-CN')}`;
    this.draftCategory = '运营公告';
    this.draftContent = '今日重点：低库存物料请转补货建议；待审批采购单需在班次结束前处理；已发货订单请同步应收；逾期客户进入催款队列；经营日报生成后归档到文件中心。';
  }

  publishArticle(): void {
    const title = this.draftTitle.trim();
    const content = this.draftContent.trim();
    if (!title || !content) {
      this.messages.add({ severity: 'warn', summary: '内容不完整', detail: '请填写标题和正文。' });
      return;
    }
    this.publishing.set(true);
    this.api.post<DataRecord>('articles', {
      title,
      category: this.draftCategory,
      status: 'published',
      content,
      content_raw: content
    }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '发布失败', detail: error?.message || '公告未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.publishing.set(false))
    ).subscribe(article => {
      if (article) {
        this.messages.add({ severity: 'success', summary: '公告已发布', detail: recordTitle(article) });
        this.articles.set([article, ...this.articles()]);
        this.selectArticle(article);
      }
    });
  }

  selectArticle(article: DataRecord): void {
    this.selectedArticle.set(article);
    this.commentsLoading.set(true);
    this.api.get<{ items: DataRecord[] }>(`articles/${article.id}/comments`).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '讨论读取失败', detail: error?.message || '无法读取评论。' });
        return of({ items: [] });
      }),
      finalize(() => this.commentsLoading.set(false))
    ).subscribe(result => this.comments.set(result.items));
  }

  publishComment(article: DataRecord): void {
    const content = this.commentDraft.trim();
    if (!content || !article.id) {
      return;
    }
    this.commentPosting.set(true);
    this.api.post<DataRecord>(`articles/${article.id}/comments`, { content }).pipe(
      catchError(error => {
        this.messages.add({ severity: 'warn', summary: '回复失败', detail: error?.message || '评论未写入数据库。' });
        return of(null);
      }),
      finalize(() => this.commentPosting.set(false))
    ).subscribe(comment => {
      if (!comment) {
        return;
      }
      this.commentDraft = '';
      this.comments.set([...this.comments(), comment]);
      const next = this.articles().map(item => item.id === article.id ? { ...item, comment_count: Number(item['comment_count'] || 0) + 1 } : item);
      this.articles.set(next);
      this.messages.add({ severity: 'success', summary: '回复已发布', detail: recordTitle(article) });
    });
  }

  text(row: DataRecord | null | undefined, key: string, empty = '-'): string {
    return textOf(row, key, empty);
  }

  date(value: unknown): string {
    return dateText(value);
  }

  number(value: unknown): number {
    return Number(value ?? 0) || 0;
  }

  severity(value: unknown): 'success' | 'secondary' | 'info' | 'warn' | 'danger' | 'contrast' {
    return statusSeverity(value);
  }

  statusText(value: unknown): string {
    return String(value ?? '') === 'draft' ? '草稿' : '已发布';
  }

  articleSummary(article: DataRecord): string {
    const content = textOf(article, 'content_raw', textOf(article, 'content', '')).trim();
    if (content) {
      return content.slice(0, 110);
    }
    const title = textOf(article, 'title', '知识条目');
    const category = textOf(article, 'category', '知识库');
    return `${category}《${title}》已进入内容库，可在详情页补充执行说明、附件和讨论记录。`.slice(0, 110);
  }
}
