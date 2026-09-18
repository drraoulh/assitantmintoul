let ctx: AudioContext | null = null;

function audioCtx() {
  if (typeof window === "undefined") return null;
  const AC =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!AC) return null;
  if (!ctx) ctx = new AC();
  if (ctx.state === "suspended") void ctx.resume();
  return ctx;
}

function beep(
  ac: AudioContext,
  freq: number,
  when: number,
  dur: number,
  type: OscillatorType,
  volume: number,
) {
  const osc = ac.createOscillator();
  const gain = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, when);
  gain.gain.setValueAtTime(0.0001, when);
  gain.gain.exponentialRampToValueAtTime(volume, when + 0.018);
  gain.gain.exponentialRampToValueAtTime(0.0001, when + dur);
  osc.connect(gain);
  gain.connect(ac.destination);
  osc.start(when);
  osc.stop(when + dur + 0.03);
}

/** Short bright arpeggio — bonne réponse. */
export function playCorrectSound() {
  const ac = audioCtx();
  if (!ac) return;
  const t = ac.currentTime;
  beep(ac, 523.25, t, 0.11, "sine", 0.16);
  beep(ac, 659.25, t + 0.09, 0.11, "sine", 0.16);
  beep(ac, 783.99, t + 0.18, 0.22, "triangle", 0.2);
}

/** Low fall — mauvaise réponse. */
export function playWrongSound() {
  const ac = audioCtx();
  if (!ac) return;
  const t = ac.currentTime;
  beep(ac, 196, t, 0.16, "square", 0.07);
  beep(ac, 147, t + 0.1, 0.28, "sawtooth", 0.06);
}
