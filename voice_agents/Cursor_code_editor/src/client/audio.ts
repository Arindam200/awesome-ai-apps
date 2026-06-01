export type AudioControls = {
  setPaused: (paused: boolean) => void;
  stop: () => void;
};

export async function startMicrophoneStream(
  sendChunk: (chunk: ArrayBuffer) => void,
  onLevel: (level: number) => void,
  onVoiceActivity?: () => void
): Promise<AudioControls> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true
    }
  });
  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(4096, 1, 1);
  let paused = false;

  processor.onaudioprocess = (event) => {
    const input = event.inputBuffer.getChannelData(0);
    const level = rms(input);
    onLevel(level);
    if (paused) return;
    if (level > 0.075) onVoiceActivity?.();
    const downsampled = downsample(input, context.sampleRate, 24000);
    sendChunk(pcm16(downsampled));
  };

  source.connect(processor);
  processor.connect(context.destination);

  return {
    setPaused: (nextPaused) => {
      paused = nextPaused;
      if (paused) onLevel(0);
    },
    stop: () => {
      processor.disconnect();
      source.disconnect();
      stream.getTracks().forEach((track) => track.stop());
      void context.close();
    }
  };
}

export class PcmPlayer {
  private context: AudioContext | null = null;
  private nextPlayTime = 0;

  async play(arrayBuffer: ArrayBuffer) {
    if (!this.context) {
      this.context = new AudioContext({ sampleRate: 24000 });
      this.nextPlayTime = this.context.currentTime;
    }

    const samples = new Int16Array(arrayBuffer);
    if (samples.length === 0) return;

    const buffer = this.context.createBuffer(1, samples.length, 24000);
    const channel = buffer.getChannelData(0);
    for (let index = 0; index < samples.length; index += 1) {
      channel[index] = samples[index] / 32768;
    }

    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);
    const startAt = Math.max(this.context.currentTime, this.nextPlayTime);
    source.start(startAt);
    this.nextPlayTime = startAt + buffer.duration;
  }

  reset() {
    if (this.context) {
      void this.context.close();
      this.context = null;
    }
    this.nextPlayTime = 0;
  }

  bufferedMs() {
    if (!this.context) return 0;
    return Math.max(0, (this.nextPlayTime - this.context.currentTime) * 1000);
  }
}

function downsample(input: Float32Array, inputRate: number, outputRate: number) {
  if (inputRate === outputRate) return input;
  const ratio = inputRate / outputRate;
  const outputLength = Math.floor(input.length / ratio);
  const output = new Float32Array(outputLength);

  for (let index = 0; index < outputLength; index += 1) {
    const start = Math.floor(index * ratio);
    const end = Math.floor((index + 1) * ratio);
    let sum = 0;
    let count = 0;

    for (let sample = start; sample < end && sample < input.length; sample += 1) {
      sum += input[sample];
      count += 1;
    }

    output[index] = count ? sum / count : 0;
  }

  return output;
}

function pcm16(input: Float32Array) {
  const output = new Int16Array(input.length);
  for (let index = 0; index < input.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, input[index]));
    output[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return output.buffer;
}

function rms(input: Float32Array) {
  let sum = 0;
  for (const sample of input) {
    sum += sample * sample;
  }
  return Math.min(1, Math.sqrt(sum / input.length) * 12);
}
