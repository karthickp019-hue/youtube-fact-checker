from flask import Flask, request, jsonify, render_template_string
import json, re, urllib.request, urllib.parse, time, os

app = Flask(__name__)
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
YOUTUBE_KEY = os.environ.get("YOUTUBE_API_KEY", "")
MODEL = "llama-3.1-8b-instant"

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YouTube Fact Checker</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, sans-serif; background: #0f0f0f; color: #fff; min-height: 100vh; }
.header { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 24px 20px; text-align: center; border-bottom: 1px solid #333; }
.header h1 { font-size: 24px; font-weight: 700; }
.header p { color: #aaa; font-size: 14px; margin-top: 6px; }
.container { max-width: 700px; margin: 0 auto; padding: 24px 16px; }
.input-box { background: #1a1a1a; border: 1px solid #333; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
.input-box label { display: block; font-size: 14px; color: #aaa; margin-bottom: 8px; }
.input-box input { width: 100%; background: #0f0f0f; border: 1px solid #444; border-radius: 8px; padding: 12px; color: #fff; font-size: 15px; outline: none; }
.input-box input:focus { border-color: #6c63ff; }
.btn { width: 100%; background: linear-gradient(135deg, #6c63ff, #3ecf8e); border: none; border-radius: 10px; padding: 16px; color: #fff; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 12px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.status { background: #1a1a1a; border: 1px solid #333; border-radius: 12px; padding: 16px; margin-bottom: 20px; display: none; }
.status-step { display: flex; align-items: center; gap: 10px; padding: 8px 0; font-size: 14px; color: #aaa; }
.status-step.active { color: #6c63ff; }
.status-step.done { color: #3ecf8e; }
.spinner { width: 16px; height: 16px; border: 2px solid #333; border-top-color: #6c63ff; border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }
.results { display: none; }
.results h2 { font-size: 18px; margin-bottom: 16px; }
.claim-card { background: #1a1a1a; border: 1px solid #333; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.claim-title { font-size: 15px; font-weight: 600; margin-bottom: 8px; line-height: 1.4; }
.verdict { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; margin-bottom: 10px; }
.verdict.Supported { background: #1a3a2a; color: #3ecf8e; border: 1px solid #3ecf8e; }
.verdict.Disputed { background: #3a1a1a; color: #ff6b6b; border: 1px solid #ff6b6b; }
.verdict.Mixed { background: #3a2e1a; color: #ffa94d; border: 1px solid #ffa94d; }
.verdict.Unverifiable { background: #2a2a2a; color: #aaa; border: 1px solid #555; }
.analysis { font-size: 13px; color: #bbb; line-height: 1.6; }
.context { font-size: 12px; color: #666; font-style: italic; margin-bottom: 8px; padding: 8px; background: #111; border-radius: 6px; border-left: 3px solid #333; }
.no-claims { text-align: center; padding: 40px 20px; color: #aaa; }
.error-box { background: #2a1a1a; border: 1px solid #ff6b6b; border-radius: 12px; padding: 16px; color: #ff6b6b; margin-bottom: 20px; display: none; }
.tip { background: #1a1a2e; border: 1px solid #333; border-radius: 10px; padding: 12px 16px; font-size: 13px; color: #aaa; margin-bottom: 20px; }
.tip span { color: #6c63ff; }
</style>
</head>
<body>
<div class="header">
  <h1>ðŸ” YouTube Fact Checker</h1>
  <p>Paste any YouTube link to check its facts</p>
</div>
<div class="container">
  <div class="tip"><span>ðŸ’¡ Tip:</span> Works best with news videos longer than 3 minutes. Supports Hindi and English videos!</div>
  <div class="input-box">
    <label>YouTube Video URL</label>
    <input type="text" id="urlInput" placeholder="https://www.youtube.com/watch?v=..." />
    <button class="btn" id="checkBtn" onclick="checkFacts()">ðŸ” Check Facts</button>
  </div>
  <div class="error-box" id="errorBox"></div>
  <div class="status" id="statusBox">
    <div class="status-step" id="step1">â³ Fetching video content...</div>
    <div class="status-step" id="step2">â³ Extracting factual claims...</div>
    <div class="status-step" id="step3">â³ Verifying claims with web search...</div>
    <div class="status-step" id="step4">â³ Generating report...</div>
  </div>
  <div class="results" id="results">
    <h2 id="resultsTitle">Fact-Check Results</h2>
    <div id="claimsList"></div>
  </div>
</div>
<script>
async function checkFacts() {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) { showError('Please paste a YouTube URL first!'); return; }
  const btn = document.getElementById('checkBtn');
  btn.disabled = true; btn.textContent = 'â³ Checking...';
  document.getElementById('errorBox').style.display = 'none';
  document.getElementById('results').style.display = 'none';
  document.getElementById('statusBox').style.display = 'block';
  setStep(1, 'active');
  try {
    const response = await fetch('/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await response.json();
    if (data.error) { showError(data.error); return; }
    setStep(1,'done'); setStep(2,'done'); setStep(3,'done'); setStep(4,'done');
    showResults(data);
  } catch(e) {
    showError('Something went wrong. Please try again.');
  } finally {
    btn.disabled = false; btn.textContent = 'ðŸ” Check Facts';
  }
}
function setStep(n, status) {
  const el = document.getElementById('step' + n);
  const labels = ['','Fetching video content...','Extracting factual claims...','Verifying claims with web search...','Generating report...'];
  if (status === 'active') el.innerHTML = '<div class="spinner"></div> ' + labels[n];
  if (status === 'done') el.innerHTML = 'âœ“ ' + labels[n];
  el.className = 'status-step ' + status;
}
function showResults(data) {
  document.getElementById('statusBox').style.display = 'none';
  const results = document.getElementById('results');
  const list = document.getElementById('claimsList');
  results.style.display = 'block';
  if (!data.claims || !data.claims.length) {
    list.innerHTML = '<div class="no-claims"><div style="font-size:40px">ðŸ”Ž</div><p>No specific factual claims found.</p><p style="margin-top:8px;font-size:12px">Try a longer news video.</p></div>';
    return;
  }
  document.getElementById('resultsTitle').textContent = `Found ${data.claims.length} claim(s) â€” Fact-Check Report`;
  const emojis = {Supported:'âœ…',Disputed:'âŒ',Mixed:'âš ï¸',Unverifiable:'â“'};
  list.innerHTML = data.claims.map((c,i) => `
    <div class="claim-card">
      <div class="claim-title">${i+1}. ${c.claim}</div>
      <div class="context">"${c.context}"</div>
      <div class="verdict ${c.verdict}">${emojis[c.verdict]||'â“'} ${c.verdict}</div>
      <div class="analysis">${c.analysis}</div>
    </div>`).join('');
}
function showError(msg) {
  document.getElementById('statusBox').style.display = 'none';
  const eb = document.getElementById('errorBox');
  eb.textContent = 'âš ï¸ ' + msg; eb.style.display = 'block';
}
document.getElementById('urlInput').addEventListener('keypress', e => { if(e.key==='Enter') checkFacts(); });
</script>
</body>
</html>"""

def vid_id(url):
    for p in [r"(?:v=|\/)([0-9A-Za-z_-]{11})", r"youtu\.be\/([0-9A-Za-z_-]{11})", r"shorts\/([0-9A-Za-z_-]{11})"]:
        m = re.search(p, url)
        if m: return m.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url): return url
    raise ValueError("Invalid YouTube URL")

def get_content_youtube_api(vid):
    """Use YouTube Data API to get video title and description"""
    if not YOUTUBE_KEY:
        return None
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?id={vid}&key={YOUTUBE_KEY}&part=snippet"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        items = data.get("items", [])
        if not items:
            return None
        snippet = items[0]["snippet"]
        title = snippet.get("title", "")
        desc = snippet.get("description", "")[:3000]
        return f"VIDEO TITLE: {title}\n\nDESCRIPTION: {desc}"
    except Exception as e:
        print(f"YouTube API error: {e}")
        return None

def get_transcript(vid):
    """Try to get transcript using youtube-transcript-api"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        try:
            ytt = YouTubeTranscriptApi()
            fetched = ytt.fetch(vid)
            return " ".join(s.text for s in fetched)
        except: pass
        try:
            segs = YouTubeTranscriptApi.get_transcript(vid)
            return " ".join(s["text"] for s in segs)
        except: pass
        try:
            tlist = YouTubeTranscriptApi.list_transcripts(vid)
            for t in tlist:
                try:
                    segs = t.fetch()
                    try: return " ".join(s.text for s in segs)
                    except: return " ".join(s["text"] for s in segs)
                except: pass
        except: pass
    except: pass
    return None

def get_content(vid):
    # Try transcript first
    text = get_transcript(vid)
    if text and len(text) > 100:
        return text
    # Fall back to YouTube API
    text = get_content_youtube_api(vid)
    if text:
        return text
    # Last resort: scrape page
    try:
        req = urllib.request.Request(
            f"https://www.youtube.com/watch?v={vid}",
            headers={"User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", "ignore")
        title = ""
        m = re.search(r'"title":"([^"]+)"', html)
        if m: title = m.group(1)
        desc = ""
        m = re.search(r'"shortDescription":"(.*?)"(?:,"isCrawlable")', html, re.DOTALL)
        if m: desc = m.group(1)[:2000].replace("\\n", " ").replace('\\"', '"')
        if title or desc:
            return f"VIDEO TITLE: {title}\n\nDESCRIPTION: {desc}"
    except: pass
    return None

def groq_call(prompt, sys_msg="You are a helpful assistant."):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
        "max_tokens": 800, "temperature": 0.1
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={
            "Authorization": "Bearer " + GROQ_KEY,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
            "Accept": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()

def search_web(query):
    q = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1"})
    req = urllib.request.Request("https://api.duckduckgo.com/?" + q, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        results = []
        if data.get("AbstractText"): results.append(data["AbstractText"])
        for t in data.get("RelatedTopics", [])[:4]:
            if isinstance(t, dict) and t.get("Text"): results.append(t["Text"])
        return "\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search error: {e}"

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/check", methods=["POST"])
def check():
    if not GROQ_KEY:
        return jsonify({"error": "GROQ_API_KEY not configured on server."})
    data = request.get_json()
    url = data.get("url", "").strip()
    try:
        vid = vid_id(url)
    except:
        return jsonify({"error": "Invalid YouTube URL."})

    content = get_content(vid)
    if not content:
        return jsonify({"error": "Could not get content from this video. Try a different video."})

    try:
        raw = groq_call(
            f"Extract up to 5 specific checkable factual claims (numbers, quotes, events, statistics) from this content. Return ONLY a JSON array: [{{\"claim\":\"...\",\"context\":\"...\"}}]. If none found, return [].\n\nCONTENT:\n{content[:6000]}",
            "You extract factual claims. Return only valid JSON arrays, no other text."
        )
        raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        try: claims = json.loads(raw)
        except:
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            claims = json.loads(m.group(0)) if m else []
    except Exception as e:
        return jsonify({"error": f"AI error: {str(e)}"})

    results = []
    for c in claims[:5]:
        try:
            search_results = search_web(c["claim"])
            analysis = groq_call(
                f'Claim: "{c["claim"]}"\nContext: "{c["context"]}"\n\nWeb info:\n{search_results}\n\nWrite 2-3 sentences on what sources say. End with: VERDICT: Supported / Disputed / Mixed / Unverifiable',
                "You are a neutral fact-checker."
            )
            verdict = "Unverifiable"
            for line in analysis.splitlines():
                if "VERDICT:" in line:
                    v = line.replace("VERDICT:", "").strip()
                    if v in ["Supported", "Disputed", "Mixed", "Unverifiable"]:
                        verdict = v
                    break
            clean = re.sub(r"VERDICT:.*", "", analysis).strip()
            results.append({"claim": c["claim"], "context": c.get("context",""), "verdict": verdict, "analysis": clean})
            time.sleep(0.5)
        except Exception as e:
            results.append({"claim": c["claim"], "context": c.get("context",""), "verdict": "Unverifiable", "analysis": str(e)})

    return jsonify({"claims": results})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
