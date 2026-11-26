/**
 * Original procedural luxury ambient architectural soundscape generated
 * purely via the Web Audio API (zero external audio files required).
 */
export class AmbientAudioEngine {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private filter: BiquadFilterNode | null = null;
  private timerId: number | null = null;

  public isMuted = true;
  public volume = 0.28;
  private chordStep = 0;

  // Lush warm architectural maj9 / add9 voicings in D Lydian / D Major (Hz)
  private readonly chords: number[][] = [
    [146.83, 220.0, 277.18, 329.63, 369.99], // Dmaj9
    [123.47, 185.0, 246.94, 293.66, 369.99], // Bm9
    [196.0, 246.94, 293.66, 369.99, 440.0],  // Gmaj9
    [164.81, 220.0, 277.18, 329.63, 440.0],  // A6/9
  ];

  private ensureContext(): void {
    if (this.ctx) return;
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.ctx = new AudioCtx();

    this.filter = this.ctx.createBiquadFilter();
    this.filter.type = 'lowpass';
    this.filter.frequency.value = 820;
    this.filter.Q.value = 0.8;

    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.value = 0.0001;

    this.filter.connect(this.masterGain);
    this.masterGain.connect(this.ctx.destination);
  }

  start(): void {
    this.ensureContext();
    if (!this.ctx || !this.masterGain) return;
    if (this.ctx.state === 'suspended') {
      void this.ctx.resume();
    }
    this.isMuted = false;
    this.masterGain.gain.cancelScheduledValues(this.ctx.currentTime);
    this.masterGain.gain.setTargetAtTime(this.volume, this.ctx.currentTime, 0.8);

    if (this.timerId === null) {
      this.playWarmChord();
      this.timerId = window.setInterval(() => this.playWarmChord(), 5200);
    }
  }

  toggleMute(): boolean {
    if (this.isMuted) {
      this.start();
    } else {
      this.mute();
    }
    return this.isMuted;
  }

  mute(): void {
    this.isMuted = true;
    if (this.ctx && this.masterGain) {
      this.masterGain.gain.cancelScheduledValues(this.ctx.currentTime);
      this.masterGain.gain.setTargetAtTime(0.0001, this.ctx.currentTime, 0.35);
    }
  }

  setVolume(val: number): void {
    this.volume = Math.max(0, Math.min(1, val));
    if (!this.isMuted && this.ctx && this.masterGain) {
      this.masterGain.gain.setTargetAtTime(this.volume, this.ctx.currentTime, 0.15);
    }
  }

  private playWarmChord(): void {
    if (this.isMuted || !this.ctx || !this.filter) return;
    const now = this.ctx.currentTime;
    const freqs = this.chords[this.chordStep % this.chords.length];
    this.chordStep++;

    freqs.forEach((f, idx) => {
      if (!this.ctx || !this.filter) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = idx === 0 ? 'sine' : 'triangle';
      osc.frequency.setValueAtTime(f, now);
      osc.detune.setValueAtTime((idx - 2) * 3.5, now);

      const peak = idx === 0 ? 0.12 : 0.045;
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.linearRampToValueAtTime(peak, now + 1.8);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 6.4);

      osc.connect(gain);
      gain.connect(this.filter);
      osc.start(now);
      osc.stop(now + 6.6);
    });
  }

  dispose(): void {
    if (this.timerId !== null) {
      clearInterval(this.timerId);
      this.timerId = null;
    }
    if (this.ctx) {
      void this.ctx.close();
      this.ctx = null;
    }
  }
}
