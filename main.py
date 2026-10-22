"""
Text to Voice - free TTS backend (FastAPI + edge-tts) with a simple web page.
Run:  python main.py   then open  http://127.0.0.1:8000
"""
import io
import re
import time
from pathlib import Path

import edge_tts
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

import os
import base64
import secrets
from fastapi import Response

app = FastAPI(title="Text to Voice")

PASSWORD = os.environ.get("APP_PASSWORD")

@app.middleware("http")
async def check_password(request, call_next):
    if PASSWORD:
        auth = request.headers.get("authorization", "")
        ok = False
        if auth.startswith("Basic "):
            try:
                given = base64.b64decode(auth[6:]).decode().split(":", 1)[-1]
                ok = secrets.compare_digest(given, PASSWORD)
            except Exception:
                ok = False
        if not ok:
            return Response(status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="Text to Voice"'})
    return await call_next(request)

OUTPUT_DIR = Path("outputs")  # every generated voice is also saved here
OUTPUT_DIR.mkdir(exist_ok=True)

# langs: "hi" = Hindi script/Hinglish, "en" = English
# "Multilingual" voices sound the most natural and can read both Hindi and English.
VOICES = [
    # ---- Female ----
    {"id": "hi-IN-SwaraNeural", "name": "Swara", "gender": "female", "langs": ["hi"], "note": "Clear, friendly"},
    {"id": "en-US-AvaMultilingualNeural", "name": "Ava", "gender": "female", "langs": ["hi", "en"], "note": "Warm, very natural"},
    {"id": "en-US-EmmaMultilingualNeural", "name": "Emma", "gender": "female", "langs": ["hi", "en"], "note": "Soft, calm"},
    {"id": "en-IN-NeerjaNeural", "name": "Neerja", "gender": "female", "langs": ["en"], "note": "Indian accent"},
    {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "female", "langs": ["en"], "note": "Casual, friendly"},
    {"id": "en-GB-SoniaNeural", "name": "Sonia", "gender": "female", "langs": ["en"], "note": "British, clear"},
    # ---- Male ----
    {"id": "hi-IN-MadhurNeural", "name": "Madhur", "gender": "male", "langs": ["hi"], "note": "Clear, friendly"},
    {"id": "en-US-AndrewMultilingualNeural", "name": "Andrew", "gender": "male", "langs": ["hi", "en"], "note": "Warm, conversational"},
    {"id": "en-US-BrianMultilingualNeural", "name": "Brian", "gender": "male", "langs": ["hi", "en"], "note": "Deep, calm"},
    {"id": "en-IN-PrabhatNeural", "name": "Prabhat", "gender": "male", "langs": ["en"], "note": "Indian accent"},
    {"id": "en-US-GuyNeural", "name": "Guy", "gender": "male", "langs": ["en"], "note": "Casual, energetic"},
    {"id": "en-GB-RyanNeural", "name": "Ryan", "gender": "male", "langs": ["en"], "note": "British, confident"},
]


class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-AvaMultilingualNeural"
    rate: int = 0     # speed in percent, -50 to +100
    pitch: int = 0    # pitch in Hz, -50 to +50
    save: bool = True  # False for quick previews (not saved to outputs folder)


def humanize(text: str) -> str:
    """Clean the script so the voice sounds less robotic:
    - removes emojis, hashtags and markdown symbols that get read out loud
    - makes sure every line ends with punctuation, so the voice pauses naturally
    """
    text = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf]", "", text)  # emojis
    text = re.sub(r"[#*_~`>|]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    fixed = []
    for ln in lines:
        if ln[-1] not in ".!?,:;\u0964\u2026":  # \u0964 is the Hindi full stop
            ln += "."
        fixed.append(ln)
    return " ".join(fixed)


@app.get("/voices")
async def voices():
    return VOICES


@app.post("/speak")
async def speak(req: TTSRequest):
    text = humanize(req.text)
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty")

    rate = f"{max(-50, min(100, req.rate)):+d}%"
    pitch = f"{max(-50, min(50, req.pitch)):+d}Hz"

    try:
        communicate = edge_tts.Communicate(text, req.voice, rate=rate, pitch=pitch)
        audio = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.write(chunk["data"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")

    data = audio.getvalue()
    if not data:
        raise HTTPException(
            status_code=500,
            detail="No audio returned. Check internet, or try a different voice.",
        )

    filename = f"voice_{int(time.time())}.mp3"
    if req.save:
        (OUTPUT_DIR / filename).write_bytes(data)

    return StreamingResponse(
        io.BytesIO(data),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Text to Voice</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 760px; margin: 30px auto; padding: 0 16px; background: #f5f6f8; color: #222; }
  h1 { margin-bottom: 4px; }
  .card { background: #fff; padding: 20px; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }
  textarea { width: 100%; height: 170px; padding: 10px; font-size: 16px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 6px; }
  label.t { display: block; margin-top: 16px; font-weight: bold; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
  button { font-family: inherit; cursor: pointer; border: 1px solid #cbd5e1; background: #fff; border-radius: 8px; padding: 9px 16px; font-size: 15px; }
  button.active { background: #2563eb; color: #fff; border-color: #2563eb; }
  .vbtn { text-align: left; min-width: 140px; }
  .vbtn small { display: block; font-size: 12px; opacity: .75; margin-top: 2px; }
  .sub { font-size: 13px; color: #666; margin-top: 12px; }
  input[type=range] { width: 100%; margin-top: 6px; }
  .main { background: #16a34a; color: #fff; border: 0; padding: 12px 26px; font-size: 16px; margin-top: 18px; }
  .main:disabled, .sample:disabled { background: #94a3b8; color: #fff; }
  .sample { margin-top: 18px; margin-left: 8px; padding: 12px 18px; }
  #status { margin-top: 12px; color: #555; }
  audio { width: 100%; margin-top: 14px; }
  a.dl { display: inline-block; margin-top: 10px; }
</style>
</head>
<body>
<h1>Text to Voice</h1>
<p>Script paste karo, voice chuno, MP3 pao.</p>
<div class="card">
  <label class="t" style="margin-top:0">Script</label>
  <textarea id="text" placeholder="Apni reel ki script yahan paste karo..."></textarea>

  <label class="t">Language</label>
  <div class="row" id="langs">
    <button data-lang="hi" class="active">Hindi / Hinglish</button>
    <button data-lang="en">English</button>
  </div>

  <label class="t">Female voices</label>
  <div class="row" id="female"></div>

  <label class="t">Male voices</label>
  <div class="row" id="male"></div>

  <label class="t">Style</label>
  <div class="row" id="presets">
    <button data-rate="-3" class="active">Natural</button>
    <button data-rate="8">Reel / Fast</button>
    <button data-rate="-12">Calm / Story</button>
  </div>

  <label class="t">Speed: <span id="rateVal">-3</span>%</label>
  <input type="range" id="rate" min="-50" max="100" value="-3">
  <div class="sub">Tip: har line ke end me full stop (.) ya comma (,) lagao, voice natural pause lega.</div>

  <button class="main" id="go">Generate Voice</button>
  <button class="sample" id="sample">Sample suno</button>
  <div id="status"></div>
  <audio id="player" controls style="display:none"></audio>
  <a id="download" class="dl" style="display:none">Download MP3</a>
</div>

<script>
const $ = id => document.getElementById(id);
let voices = [], lang = "hi", selected = null;

const SAMPLES = {
  hi: "\\u0928\\u092e\\u0938\\u094d\\u0924\\u0947 \\u0926\\u094b\\u0938\\u094d\\u0924\\u094b\\u0902, \\u0906\\u091c \\u0939\\u092e \\u090f\\u0915 \\u092c\\u0939\\u0941\\u0924 \\u0939\\u0940 \\u092e\\u095b\\u0947\\u0926\\u093e\\u0930 \\u091a\\u0940\\u095b \\u0915\\u0947 \\u092c\\u093e\\u0930\\u0947 \\u092e\\u0947\\u0902 \\u092c\\u093e\\u0924 \\u0915\\u0930\\u0947\\u0902\\u0917\\u0947\\u0964",
  en: "Hey everyone, welcome back. Today I want to share something really interesting with you."
};

function render() {
  for (const g of ["female", "male"]) {
    const box = $(g);
    box.innerHTML = "";
    voices.filter(v => v.gender === g && v.langs.includes(lang)).forEach(v => {
      const b = document.createElement("button");
      b.className = "vbtn" + (v.id === selected ? " active" : "");
      b.innerHTML = "<b>" + v.name + "</b><small>" + v.note + "</small>";
      b.onclick = () => { selected = v.id; render(); };
      box.appendChild(b);
    });
  }
}

function pickDefault() {
  const first = voices.find(v => v.langs.includes(lang) && (v.langs.length > 1));
  const any = voices.find(v => v.langs.includes(lang));
  selected = (first || any).id;
}

fetch("/voices").then(r => r.json()).then(v => { voices = v; pickDefault(); render(); });

document.querySelectorAll("#langs button").forEach(b => {
  b.onclick = () => {
    document.querySelectorAll("#langs button").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    lang = b.dataset.lang;
    pickDefault();
    render();
  };
});

document.querySelectorAll("#presets button").forEach(b => {
  b.onclick = () => {
    document.querySelectorAll("#presets button").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    $("rate").value = b.dataset.rate;
    $("rateVal").textContent = b.dataset.rate;
  };
});

$("rate").oninput = () => {
  $("rateVal").textContent = $("rate").value;
  document.querySelectorAll("#presets button").forEach(x => x.classList.remove("active"));
};

async function generate(text, save) {
  $("go").disabled = true; $("sample").disabled = true;
  $("status").textContent = "Generating...";
  try {
    const res = await fetch("/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, voice: selected, rate: parseInt($("rate").value), pitch: 0, save: save })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed");
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    $("player").src = url;
    $("player").style.display = "block";
    $("player").play();
    if (save) {
      $("download").href = url;
      $("download").download = "voice.mp3";
      $("download").style.display = "inline-block";
      $("status").textContent = "Done! 'outputs' folder me bhi save ho gaya.";
    } else {
      $("status").textContent = "Sample ready. Pasand aaye to Generate Voice dabao.";
    }
  } catch (e) {
    $("status").textContent = "Error: " + e.message;
  }
  $("go").disabled = false; $("sample").disabled = false;
}

$("go").onclick = () => {
  const text = $("text").value.trim();
  if (!text) { $("status").textContent = "Pehle script paste karo."; return; }
  generate(text, true);
};
$("sample").onclick = () => generate(SAMPLES[lang], false);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def home():
    return PAGE


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"
    uvicorn.run(app, host=host, port=port)
