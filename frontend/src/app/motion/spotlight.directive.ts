import { Directive, ElementRef, HostListener, OnDestroy, OnInit, Renderer2, RendererStyleFlags2 } from '@angular/core';

@Directive({
  selector: '[nexusSpotlight]',
  standalone: true
})
export class NexusSpotlightDirective implements OnInit, OnDestroy {
  private prefersReducedMotion?: MediaQueryList;

  constructor(
    private readonly elementRef: ElementRef<HTMLElement>,
    private readonly renderer: Renderer2
  ) {}

  ngOnInit(): void {
    this.prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    this.renderer.addClass(this.elementRef.nativeElement, 'spotlight-active');
  }

  ngOnDestroy(): void {
    this.renderer.removeClass(this.elementRef.nativeElement, 'spotlight-active');
  }

  @HostListener('pointermove', ['$event'])
  onPointerMove(event: PointerEvent): void {
    if (this.prefersReducedMotion?.matches) {
      return;
    }
    const rect = this.elementRef.nativeElement.getBoundingClientRect();
    const x = `${Math.round(((event.clientX - rect.left) / Math.max(rect.width, 1)) * 100)}%`;
    const y = `${Math.round(((event.clientY - rect.top) / Math.max(rect.height, 1)) * 100)}%`;
    this.renderer.setStyle(this.elementRef.nativeElement, '--spotlight-x', x, RendererStyleFlags2.DashCase);
    this.renderer.setStyle(this.elementRef.nativeElement, '--spotlight-y', y, RendererStyleFlags2.DashCase);
  }

  @HostListener('pointerleave')
  onPointerLeave(): void {
    this.renderer.setStyle(this.elementRef.nativeElement, '--spotlight-x', '50%', RendererStyleFlags2.DashCase);
    this.renderer.setStyle(this.elementRef.nativeElement, '--spotlight-y', '50%', RendererStyleFlags2.DashCase);
  }
}
