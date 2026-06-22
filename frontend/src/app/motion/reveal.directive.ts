import { Directive, ElementRef, Input, OnDestroy, OnInit, Renderer2, RendererStyleFlags2 } from '@angular/core';

@Directive({
  selector: '[nexusReveal]',
  standalone: true
})
export class NexusRevealDirective implements OnInit, OnDestroy {
  @Input() nexusRevealDelay = 0;

  private observer?: IntersectionObserver;

  constructor(
    private readonly elementRef: ElementRef<HTMLElement>,
    private readonly renderer: Renderer2
  ) {}

  ngOnInit(): void {
    const element = this.elementRef.nativeElement;
    this.renderer.addClass(element, 'nexus-reveal');
    this.renderer.setStyle(
      element,
      '--reveal-delay',
      `${Math.max(0, this.nexusRevealDelay)}ms`,
      RendererStyleFlags2.DashCase
    );

    if (!('IntersectionObserver' in window)) {
      this.reveal();
      return;
    }

    this.observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          this.reveal();
          this.observer?.disconnect();
        }
      }
    }, { threshold: 0.18 });
    this.observer.observe(element);
  }

  ngOnDestroy(): void {
    this.observer?.disconnect();
  }

  private reveal(): void {
    this.renderer.addClass(this.elementRef.nativeElement, 'nexus-reveal--visible');
  }
}
