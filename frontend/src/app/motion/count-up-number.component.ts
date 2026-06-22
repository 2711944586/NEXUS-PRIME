import { ChangeDetectionStrategy, Component, Input, OnChanges, OnDestroy, signal } from '@angular/core';

export type CountUpNumberFormat = 'number' | 'money' | 'percent';

@Component({
  selector: 'nexus-count-up-number',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'nexus-count-up-number',
    '[attr.aria-label]': 'resolvedAriaLabel',
    '[attr.data-format]': 'format'
  },
  template: `{{ displayValue() }}`
})
export class CountUpNumberComponent implements OnChanges, OnDestroy {
  @Input() value = 0;
  @Input() format: CountUpNumberFormat = 'number';
  @Input() suffix = '';
  @Input() prefix = '';
  @Input() compact = true;
  @Input() duration = 650;
  @Input() maximumFractionDigits = 1;
  @Input() currency = 'CNY';
  @Input() locale = 'zh-CN';
  @Input() ariaLabel = '';

  protected readonly displayValue = signal('0');

  private displayedValue = 0;
  private frameId?: number;

  get resolvedAriaLabel(): string {
    return this.ariaLabel || this.displayValue();
  }

  ngOnChanges(): void {
    const targetValue = this.toFiniteNumber(this.value);
    this.cancelAnimation();

    if (this.shouldSkipAnimation()) {
      this.setDisplayValue(targetValue);
      return;
    }

    const fromValue = this.displayedValue;
    const duration = Math.max(0, this.duration);
    const startTime = window.performance?.now?.() ?? Date.now();

    const tick = (now: number): void => {
      const progress = Math.min(1, (now - startTime) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      this.setDisplayValue(fromValue + (targetValue - fromValue) * eased);

      if (progress < 1) {
        this.frameId = window.requestAnimationFrame(tick);
      } else {
        this.setDisplayValue(targetValue);
      }
    };

    this.frameId = window.requestAnimationFrame(tick);
  }

  ngOnDestroy(): void {
    this.cancelAnimation();
  }

  private shouldSkipAnimation(): boolean {
    if (this.duration <= 0 || typeof window === 'undefined' || !window.requestAnimationFrame) {
      return true;
    }
    return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  }

  private cancelAnimation(): void {
    if (this.frameId !== undefined && typeof window !== 'undefined') {
      window.cancelAnimationFrame?.(this.frameId);
      this.frameId = undefined;
    }
  }

  private setDisplayValue(value: number): void {
    this.displayedValue = value;
    this.displayValue.set(this.formatValue(value));
  }

  private formatValue(value: number): string {
    const digits = Math.max(0, this.maximumFractionDigits);
    const notation = this.compact ? 'compact' : 'standard';
    let formatted: string;

    if (this.format === 'money') {
      formatted = new Intl.NumberFormat(this.locale, {
        style: 'currency',
        currency: this.currency,
        notation,
        maximumFractionDigits: digits
      }).format(value);
    } else {
      formatted = new Intl.NumberFormat(this.locale, {
        notation,
        maximumFractionDigits: digits
      }).format(value);
      if (this.format === 'percent') {
        formatted = `${formatted}%`;
      }
    }

    return `${this.prefix}${formatted}${this.suffix}`;
  }

  private toFiniteNumber(value: number): number {
    return Number.isFinite(value) ? value : 0;
  }
}
