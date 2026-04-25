import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { VideoPlayer } from './video-player/video-player';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, VideoPlayer],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  protected readonly title = signal('mi-app');
}
