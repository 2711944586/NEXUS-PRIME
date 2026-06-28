import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { CountUpNumberComponent, NexusRevealDirective, NexusSpotlightDirective, SceneBackgroundComponent } from './index';

@Component({
  standalone: true,
  imports: [NexusRevealDirective, NexusSpotlightDirective, SceneBackgroundComponent, CountUpNumberComponent],
  template: `
    <nexus-scene-background image="/images/receiving-dock-wide.jpg" mode="login"></nexus-scene-background>
    <section class="test-reveal" nexusReveal [nexusRevealDelay]="80">Reveal target</section>
    <button class="test-spotlight" nexusSpotlight>Spotlight target</button>
    <nexus-count-up-number class="test-count-money" [value]="125000" format="money" [duration]="0" ariaLabel="订单动能"></nexus-count-up-number>
    <nexus-count-up-number class="test-count-percent" [value]="88" format="percent" [compact]="false" [maximumFractionDigits]="0" [duration]="0"></nexus-count-up-number>
  `
})
class MotionHostComponent {}

describe('motion primitives', () => {
  it('renders the scene background with a concrete image token', async () => {
    const fixture = await createFixture();
    const scene = fixture.nativeElement.querySelector('.nexus-scene-background') as HTMLElement;

    expect(scene.getAttribute('aria-hidden')).toBe('true');
    expect(scene.dataset['sceneMode']).toBe('login');
    expect(scene.style.getPropertyValue('--nexus-scene-image')).toContain('/images/receiving-dock-wide.jpg');
  });

  it('reveals content without leaving a blank state when IntersectionObserver is unavailable', async () => {
    const fixture = await createFixture();
    const reveal = fixture.nativeElement.querySelector('.test-reveal') as HTMLElement;

    expect(reveal.classList.contains('nexus-reveal')).toBe(true);
    expect(reveal.classList.contains('nexus-reveal--visible')).toBe(true);
    expect(reveal.style.getPropertyValue('--reveal-delay')).toBe('80ms');
  });

  it('updates spotlight coordinates from pointer movement', async () => {
    const fixture = await createFixture();
    const spotlight = fixture.nativeElement.querySelector('.test-spotlight') as HTMLElement;
    spotlight.getBoundingClientRect = () => ({
      x: 0,
      y: 0,
      top: 10,
      left: 20,
      right: 220,
      bottom: 110,
      width: 200,
      height: 100,
      toJSON: () => ({})
    });

    spotlight.dispatchEvent(new PointerEvent('pointermove', { clientX: 120, clientY: 60, bubbles: true }));
    fixture.detectChanges();

    expect(spotlight.classList.contains('spotlight-active')).toBe(true);
    expect(spotlight.style.getPropertyValue('--spotlight-x')).toBe('50%');
    expect(spotlight.style.getPropertyValue('--spotlight-y')).toBe('50%');
  });

  it('formats count-up numbers immediately when duration is disabled', async () => {
    const fixture = await createFixture();
    const money = fixture.nativeElement.querySelector('.test-count-money') as HTMLElement;
    const percent = fixture.nativeElement.querySelector('.test-count-percent') as HTMLElement;

    expect(money.textContent?.trim()).toMatch(/12\.5/);
    expect(money.getAttribute('aria-label')).toBe('订单动能');
    expect(percent.textContent?.trim()).toBe('88%');
    expect(percent.getAttribute('data-format')).toBe('percent');
  });
});

async function createFixture(): Promise<ComponentFixture<MotionHostComponent>> {
  TestBed.resetTestingModule();
  await TestBed.configureTestingModule({
    imports: [MotionHostComponent]
  }).compileComponents();
  const fixture = TestBed.createComponent(MotionHostComponent);
  fixture.detectChanges();
  return fixture;
}
