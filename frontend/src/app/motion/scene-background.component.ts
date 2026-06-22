import { Component, Input } from '@angular/core';

type SceneMode = 'default' | 'login' | 'register';

@Component({
  selector: 'nexus-scene-background',
  standalone: true,
  template: `
    <div
      class="nexus-scene-background"
      [class.nexus-scene-background--register]="mode === 'register'"
      [style.--nexus-scene-image]="cssImage"
      aria-hidden="true"
    >
      <div class="nexus-scene-background__image"></div>
      <div class="nexus-scene-background__aurora"></div>
      <div class="nexus-scene-background__grid"></div>
      <div class="nexus-scene-background__scan"></div>
    </div>
  `
})
export class SceneBackgroundComponent {
  @Input() image = '/images/industrial-manufacturing.jpg';
  @Input() mode: SceneMode = 'default';

  get cssImage(): string {
    return `url("${this.image.replace(/"/g, '\\"')}")`;
  }
}
