import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { WorkflowStepperComponent, WorkflowStepperStep } from './workflow-stepper.component';

const STEPS: WorkflowStepperStep[] = [
  { label: '生成建议', detail: '低库存进入采购需求池。', tone: 'info', path: '/app/inventory/replenishment' },
  { label: '审批承诺', detail: '采购负责人复核金额和供应商风险。', tone: 'warning', meta: '待审批 4 单' },
  { label: '收货入库', detail: '到货质检后回写库存。', tone: 'success' }
];

@Component({
  standalone: true,
  imports: [WorkflowStepperComponent],
  template: `
    <nexus-workflow-stepper
      [steps]="steps"
      [activeIndex]="activeIndex"
      ariaLabel="采购审批流程"
    ></nexus-workflow-stepper>
  `
})
class WorkflowStepperHostComponent {
  steps = STEPS;
  activeIndex = 1;
}

describe('WorkflowStepperComponent', () => {
  it('renders active, complete, and pending workflow states', async () => {
    const fixture = await createFixture();
    const items = fixture.nativeElement.querySelectorAll('.nexus-workflow-stepper__item') as NodeListOf<HTMLElement>;

    expect(items).toHaveLength(3);
    expect(items[0].classList.contains('is-complete')).toBe(true);
    expect(items[1].classList.contains('is-active')).toBe(true);
    expect(items[1].getAttribute('aria-current')).toBe('step');
    expect(items[2].classList.contains('is-pending')).toBe(true);
    expect(items[1].textContent).toContain('待审批 4 单');
  });

  it('keeps linked steps navigable and labelled', async () => {
    const fixture = await createFixture();
    const host = fixture.nativeElement.querySelector('nexus-workflow-stepper') as HTMLElement;
    const link = fixture.nativeElement.querySelector('a.nexus-workflow-stepper__surface') as HTMLAnchorElement;

    expect(host.getAttribute('aria-label')).toBe('采购审批流程');
    expect(link.getAttribute('href')).toBe('/app/inventory/replenishment');
  });

  it('shows an empty state when no steps are available', async () => {
    const fixture = await createFixture([]);

    const empty = fixture.nativeElement.querySelector('.nexus-workflow-stepper__empty') as HTMLElement;
    expect(empty.textContent?.trim()).toBe('暂无流程节点');
  });
});

async function createFixture(steps = STEPS): Promise<ComponentFixture<WorkflowStepperHostComponent>> {
  TestBed.resetTestingModule();
  await TestBed.configureTestingModule({
    imports: [WorkflowStepperHostComponent],
    providers: [provideRouter([])]
  }).compileComponents();
  const fixture = TestBed.createComponent(WorkflowStepperHostComponent);
  fixture.componentInstance.steps = steps;
  fixture.detectChanges();
  return fixture;
}
