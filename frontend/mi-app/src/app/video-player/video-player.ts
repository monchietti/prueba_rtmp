import { Component, AfterViewInit, ViewChild, ElementRef } from '@angular/core';
import Hls from 'hls.js';


@Component({
  selector: 'app-video-player',
  imports: [],
  templateUrl: './video-player.html',
  styleUrl: './video-player.css',
})
export class VideoPlayer implements AfterViewInit {

  @ViewChild('videoPlayer', { static: false }) video!: ElementRef<HTMLVideoElement>;

  streamUrl = 'http://192.168.2.101:5555/hls/valen.m3u8';

  ngAfterViewInit(): void {
    const video = this.video.nativeElement;

    if (Hls.isSupported()) {
      const hls = new Hls();
      hls.loadSource(this.streamUrl);
      hls.attachMedia(video);

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        video.play();
      });

    } 
  }
}