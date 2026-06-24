import sys, json, re, urllib.request, urllib.parse, time, os
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi

GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL = "llama-3.1-8b-instant"

def vid_id(url):
    for p in [r"(?:v=|\/)([0-9A-Za-z_-]{11})", r"youtu\.be\/([0-9A-Za-z_-]{11})", r"shorts\/([0-9A-Za-z_-]{11})"]:
        m = re.search(p, url)
        if m: return m.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url): return url
    raise ValueError("Cannot find video ID in: " + url)

def transcript(vid):
    segs = YouTubeTranscriptApi.get_transcript(vid)
    return " ".join(s["text"] for s in segs)

def groq(prompt, sys_msg="You are a helpful assistant."):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role":"system","content":sys_msg},{"role":"user","content":prompt}],
        "max_tokens": 800, "temperature": 0.1
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={"Authorization":"Bearer "+GROQ_KEY,"Content-Type":"application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()

def search(query):
    q = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"})
    req = urllib.request.Request(
        "https://api.duckduckgo.com/?" + q,
        headers={"User-Agent": "Mozilla/5.0"}
    )
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

def extract_claims(text):
    raw = groq(
        f"Extract up to 5 specific checkable factual claims (numbers, quotes, events, stats) from this transcript. Return ONLY a JSON array like: [{{\"claim\":\"...\",\"context\":\"...\"}}]. If none, return [].\n\nTRANSCRIPT:\n{text[:6000]}",
        "You extract factual claims from video transcripts. Return only valid JSON arrays."
    )
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try: return json.loads(raw)
    except:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            try: return json.loads(m.group(0))
            except: pass
        return []

def check_claim(claim):
    results = search(claim["claim"])
    return groq(
        f'Claim: "{claim["claim"]}"\nContext: "{claim["context"]}"\n\nWeb info:\n{results}\n\nWrite 2-3 sentences on what sources say. List sources. End with: VERDICT: Supported / Disputed / Mixed / Unverifiable',
        "You are a neutral fact-checker. Be fair regardless of political direction."
    )

def main():
    if not GROQ_KEY:
        print("ERROR: Set your key first:\nexport GROQ_API_KEY=your_key_here")
        sys.exit(1)
    url = input("Paste YouTube URL: ").strip()
    vid = vid_id(url)
    out = f"report_{vid}.txt"
    print(f"\n[1/4] Getting transcript for {vid}...")
    try: text = transcript(vid)
    except Exception as e: sys.exit(f"Error: {e}")
    print(f"      Got {len(text)} characters.\n")
    print("[2/4] Finding factual claims...")
    claims = extract_claims(text)
    print(f"      Found {len(claims)} claims.\n")
    lines = [f"FACT-CHECK REPORT", f"Video: https://youtube.com/watch?v={vid}", f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", "="*50, ""]
    if not claims:
        lines.append("No checkable factual claims found.")
    else:
        print("[3/4] Checking each claim...\n")
        for i, c in enumerate(claims, 1):
            print(f"  Claim {i}/{len(claims)}: {c['claim'][:60]}...")
            analysis = check_claim(c)
            verdict = next((l for l in analysis.splitlines() if "VERDICT:" in l), "VERDICT: Unverifiable")
            emoji = {"Supported":"[OK]","Disputed":"[NO]","Mixed":"[!!]","Unverifiable":"[?]"}
            v = verdict.replace("VERDICT:","").strip()
            lines += [f"{i}. {emoji.get(v,'[?]')} {c['claim']}", f"Context: {c['context']}", "", analysis, "", "-"*40, ""]
            time.sleep(0.5)
    print(f"[4/4] Saving report...")
    with open(out, "w") as f: f.write("\n".join(lines))
    print(f"\nDone! Report saved: {out}")
    print(f"Read it with: cat {out}")

main()
