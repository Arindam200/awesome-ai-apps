const recordButton = document.getElementById("recordButton");
const recordLabel = document.getElementById("recordLabel");
const recordHint = document.getElementById("recordHint");
const timeline = document.getElementById("timeline");
const currentPrompt = document.getElementById("currentPrompt");
const connectionStatus = document.getElementById("connectionStatus");
const scoreboard = document.getElementById("scoreboard");
const overallScore = document.getElementById("overallScore");
const scoreGrid = document.getElementById("scoreGrid");

let recorder = null;
let previousQuestion = "Give me your 45-second opening pitch.";

recordButton.addEventListener("click", async () => {
  if (recorder?.recording) {
    await stopTurn();
    return;
  }
  await startTurn();
});

async function startTurn() {
  try {
    recorder = await createWavRecorder();
    recorder.start();
    recordButton.classList.add("recording");
    recordLabel.textContent = "Stop and send";
    recordHint.textContent = "Listening. Keep it under a minute for a crisp coaching turn.";
    connectionStatus.textContent = "Recording";
  } catch (error) {
    showError(error.message || "Could not start microphone recording.");
  }
}

async function stopTurn() {
  recordButton.disabled = true;
  recordButton.classList.remove("recording");
  recordLabel.textContent = "Processing";
  recordHint.textContent = "Transcribing, coaching, then generating spoken feedback.";
  connectionStatus.textContent = "Thinking";

  try {
    const wavBlob = await recorder.stop();
    addBubble("user", "You", "Recorded voice turn");
    await submitTurn(wavBlob);
  } catch (error) {
    showError(error.message || "The voice turn failed.");
  } finally {
    recordButton.disabled = false;
    recordLabel.textContent = "Start speaking";
    recordHint.textContent = "Ready for the next turn.";
    connectionStatus.textContent = "Ready";
  }
}

async function submitTurn(wavBlob) {
  const form = new FormData();
  form.append("audio", wavBlob, "turn.wav");
  form.append("scenario", document.getElementById("scenario").value);
  form.append("audience", document.getElementById("audience").value);
  form.append("goal", document.getElementById("goal").value);
  form.append("previous_question", previousQuestion);

  const response = await fetch("/api/turn", {
    method: "POST",
    body: form,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Voice agent request failed.");
  }

  const coach = payload.coach;
  updateLastUserBubble(payload.transcript);
  addCoachBubble(coach, payload.spoken_reply, payload.audio_base64, payload.audio_content_type);
  previousQuestion = coach.next_question;
  currentPrompt.textContent = coach.next_question;
  updateScores(coach);
}

function addBubble(type, role, text) {
  const article = document.createElement("article");
  article.className = `bubble ${type}`;
  article.innerHTML = `<p class="role"></p><p></p>`;
  article.querySelector(".role").textContent = role;
  article.querySelector("p:last-child").textContent = text;
  timeline.appendChild(article);
  timeline.scrollTop = timeline.scrollHeight;
  return article;
}

function updateLastUserBubble(transcript) {
  const bubbles = [...timeline.querySelectorAll(".bubble.user")];
  const last = bubbles[bubbles.length - 1];
  if (last) {
    last.querySelector("p:last-child").textContent = transcript;
  }
}

function addCoachBubble(coach, spokenReply, audioBase64, contentType) {
  const article = addBubble("coach", "Coach", coach.spoken_feedback);
  const details = document.createElement("div");
  details.className = "coach-details";
  details.innerHTML = `
    <h3>Next question</h3>
    <p></p>
    <h3>Tighter version</h3>
    <p></p>
    <h3>Work on this</h3>
    <ul></ul>
  `;
  const paragraphs = details.querySelectorAll("p");
  paragraphs[0].textContent = coach.next_question;
  paragraphs[1].textContent = coach.suggested_rewrite;
  const list = details.querySelector("ul");
  coach.improvements.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  });
  article.appendChild(details);

  const audio = document.createElement("audio");
  audio.className = "audio-player";
  audio.controls = true;
  audio.src = `data:${contentType};base64,${audioBase64}`;
  article.appendChild(audio);

  audio.play().catch(() => {
    recordHint.textContent = "Tap play on the coach response if the browser blocked autoplay.";
  });
  timeline.scrollTop = timeline.scrollHeight;
}

function updateScores(coach) {
  scoreboard.hidden = false;
  overallScore.textContent = `${coach.overall_score}`;
  scoreGrid.innerHTML = "";
  Object.entries(coach.scores).forEach(([label, value]) => {
    const item = document.createElement("div");
    item.className = "score-item";
    item.innerHTML = `<span></span><b></b>`;
    item.querySelector("span").textContent = label.replaceAll("_", " ");
    item.querySelector("b").textContent = value;
    scoreGrid.appendChild(item);
  });
}

function showError(message) {
  connectionStatus.textContent = "Error";
  addBubble("coach", "System", message);
}

async function createWavRecorder() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const audioContext = new AudioContext();
  const source = audioContext.createMediaStreamSource(stream);
  const processor = audioContext.createScriptProcessor(4096, 1, 1);
  const chunks = [];
  let recording = false;

  processor.onaudioprocess = (event) => {
    if (!recording) return;
    chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
  };

  source.connect(processor);
  processor.connect(audioContext.destination);

  return {
    get recording() {
      return recording;
    },
    start() {
      chunks.length = 0;
      recording = true;
    },
    async stop() {
      recording = false;
      await new Promise((resolve) => setTimeout(resolve, 120));
      stream.getTracks().forEach((track) => track.stop());
      processor.disconnect();
      source.disconnect();
      await audioContext.close();
      return encodeWav(chunks, audioContext.sampleRate);
    },
  };
}

function encodeWav(chunks, sampleRate) {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const samples = new Float32Array(length);
  let offset = 0;
  chunks.forEach((chunk) => {
    samples.set(chunk, offset);
    offset += chunk.length;
  });

  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);

  floatTo16BitPcm(view, 44, samples);
  return new Blob([view], { type: "audio/wav" });
}

function floatTo16BitPcm(view, offset, input) {
  for (let i = 0; i < input.length; i += 1, offset += 2) {
    const sample = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
}

function writeString(view, offset, string) {
  for (let i = 0; i < string.length; i += 1) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}
