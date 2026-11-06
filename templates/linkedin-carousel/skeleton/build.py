#!/usr/bin/env python3
"""Build a LinkedIn carousel (PDF + PNG slides) and a Substack thumbnail from a JSON spec.

Usage: python3 build.py spec.json [--out DIR]
Needs: macOS (sips) + Google Chrome. No pip packages.
See SKILL.md for the spec format.
"""
import json, os, shutil, struct, subprocess, sys, glob, re

CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
HERE = os.path.dirname(os.path.abspath(__file__))

def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def img_size(path):
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                         capture_output=True, text=True, check=True).stdout
    return int(re.search(r"pixelWidth: (\d+)", out).group(1)), int(re.search(r"pixelHeight: (\d+)", out).group(1))

def shot(url, out, w, h, scale=1):
    run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         f"--force-device-scale-factor={scale}", f"--window-size={w},{h}",
         f"--screenshot={out}", url])

CAROUSEL = r"""<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:#000}
body{font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;color:#fff}
.page{width:1080px;height:1350px;overflow:hidden;position:relative;background:#0a0a0a}
.strip{position:absolute;top:0;left:0;height:1350px}
.glow{position:absolute;inset:0;background:radial-gradient(900px 600px at 0 1350px,rgba(108,232,111,.14),transparent 70%)}
.tag{position:absolute;font:700 26px/1 "SF Mono",Menlo,monospace;letter-spacing:3px;color:#6ce86f}
.h{position:absolute;width:960px;font-weight:800;font-size:66px;line-height:1.04;letter-spacing:-1.5px}
.h em{font-style:normal;color:#6ce86f}
.sub{position:absolute;width:900px;font-size:30px;line-height:1.35;color:#a9a9a9}
.card{position:absolute;border-radius:28px;border:2px solid #2c2c2c;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,.7),0 0 0 1px rgba(108,232,111,.15);background:#000}
.line{position:absolute;height:6px;background:#6ce86f;border-radius:3px}
.arrow{position:absolute;width:112px;height:112px;border-radius:56px;background:#6ce86f;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 10px rgba(108,232,111,.18)}
.arrow svg{width:56px;height:56px}
.foot{position:absolute;font:700 30px/1 "Helvetica Neue",Helvetica,Arial,sans-serif;color:#e8e8e8;white-space:nowrap}
.me{position:absolute;width:76px;height:76px;border-radius:50%;border:3px solid #6ce86f;background:center/118% no-repeat}
.btn{position:absolute;height:92px;padding:0 44px;border-radius:46px;background:#6ce86f;color:#06260a;font-weight:800;font-size:34px;display:flex;align-items:center}
.chip{position:absolute;width:420px;height:56px;border-radius:28px;border:2px solid #6ce86f;color:#fff;font-weight:700;font-size:26px;display:flex;align-items:center;padding:0 26px;background:rgba(108,232,111,.08)}
</style></head><body><script>
const SPEC=__SPEC__, slides=SPEC.slides, N=slides.length, W=1080, TOP=280, BAND0=820;
let html='<div class="glow"></div>';
slides.forEach((s,i)=>{
  const x0=i*W, BAND=s.band||BAND0, ch=Math.min(BAND,900/s.ar), cw=ch*s.ar;
  // cards start 120px inside the previous slide (empty padded edge) so the next card peeks in and invites the swipe
  const pad=i===0?0:180, cx=x0+(i===0?60:-120), cy=TOP+(BAND-ch)/2;
  html+=`<div class="tag" style="left:${x0+60}px;top:56px">${String(i+1).padStart(2,'0')} / ${String(N).padStart(2,'0')}</div>`;
  html+=`<div class="h" style="left:${x0+60}px;top:104px">${s.h}</div>`;
  if(s.sub) html+=`<div class="sub" style="left:${x0+60}px;top:190px">${s.sub}</div>`;
  html+=`<div class="card" style="left:${cx}px;top:${cy}px;width:${cw+pad}px;height:${ch}px"><img src="img/${s.img}" style="position:absolute;left:${pad}px;top:0;width:${cw}px;height:${ch}px"></div>`;
  if(i>0) html+=`<svg style="position:absolute;left:${x0-90}px;top:${cy+ch/2-30}px;width:60px;height:60px" viewBox="0 0 24 24" fill="none" stroke="#6ce86f" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5l7 7-7 7"/></svg>`;
  (s.chips||[]).forEach((c,k)=>{html+=`<div class="chip" style="left:${x0+60+(k%2)*440}px;top:${905+Math.floor(k/2)*70}px">${c}</div>`});
  if(s.cta) html+=`<div class="btn" style="left:${x0+120}px;top:1135px">${s.cta}</div>`;
  html+=`<div class="me" style="left:${x0+60}px;top:1258px;background-image:url(img/_avatar.png)"></div>`;
  html+=`<div class="foot" style="left:${x0+148}px;top:1278px">${SPEC.brand.handle}</div>`;
  if(i<N-1){const sx=x0+W;
    html+=`<div class="line" style="left:${sx-220}px;top:1217px;width:440px"></div>`;
    html+=`<div class="arrow" style="left:${sx-56}px;top:1161px"><svg viewBox="0 0 24 24" fill="none" stroke="#06260a" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></div>`;}
});
const only=+new URLSearchParams(location.search).get('p');
document.write(`<section class="page"><div class="strip" style="width:${N*W}px;transform:translateX(${-only*W}px)">${html}</div></section>`);
</script></body></html>"""

THUMB = r"""<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
body{width:1200px;height:630px;overflow:hidden;background:#0a0a0a;font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;color:#fff;position:relative}
.glow{position:absolute;inset:0;background:radial-gradient(600px 420px at 850px 330px,rgba(108,232,111,.20),transparent 70%)}
/* safe zone x 150..1050: survives Substack's ~3:2 feed crop (trims ~125px per side) */
.tag{position:absolute;left:150px;top:92px;font:700 17px/1 "SF Mono",Menlo,monospace;letter-spacing:3px;color:#6ce86f}
.h{position:absolute;left:150px;top:134px;width:480px;font-weight:800;font-size:60px;line-height:1.05;letter-spacing:-1.2px}
.h em{font-style:normal;color:#6ce86f}
.card{position:absolute;border-radius:22px;border:2px solid #2c2c2c;overflow:hidden;background:#000;box-shadow:0 20px 60px rgba(0,0,0,.7),0 0 0 1px rgba(108,232,111,.2)}
.card img{width:100%;display:block}
.me{position:absolute;left:150px;top:492px;width:46px;height:46px;border-radius:50%;border:3px solid #6ce86f;background:url(img/_avatar.png) center/118% no-repeat}
.brand{position:absolute;left:210px;top:506px;font:700 20px/1 "Helvetica Neue",Helvetica,Arial,sans-serif;color:#e8e8e8;white-space:nowrap}
</style></head><body><div class="glow"></div>
<div class="tag">__TAG__</div><div class="h">__LINES__</div>
<div class="card" style="__CARD__"><img src="img/__IMG__"></div>
<div class="me"></div><div class="brand">__HANDLE__</div></body></html>"""


TWITTER = r"""<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
body{width:1600px;height:900px;overflow:hidden;background:#0a0a0a;font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;color:#fff;position:relative}
.glow{position:absolute;inset:0;background:radial-gradient(800px 560px at 1120px 450px,rgba(108,232,111,.20),transparent 70%)}
/* safe zone x 160..1440, y 90..810: X crops the 4-image grid tiles */
.left{position:absolute;left:160px;top:100px;width:600px;height:610px;display:flex;flex-direction:column;justify-content:center;gap:24px}
.tag{font:700 22px/1 "SF Mono",Menlo,monospace;letter-spacing:3px;color:#6ce86f}
.h{font-weight:800;font-size:70px;line-height:1.04;letter-spacing:-1.5px}
.h em{font-style:normal;color:#6ce86f}
.sub{font-size:32px;line-height:1.3;color:#a9a9a9}
.btn{align-self:flex-start;padding:16px 34px;border-radius:40px;background:#6ce86f;color:#06260a;font-weight:800;font-size:30px}
.card{position:absolute;border-radius:24px;border:2px solid #2c2c2c;overflow:hidden;background:#000;box-shadow:0 24px 70px rgba(0,0,0,.7),0 0 0 1px rgba(108,232,111,.2)}
.card img{width:100%;height:100%;display:block}
.me{position:absolute;left:160px;top:742px;width:58px;height:58px;border-radius:50%;border:3px solid #6ce86f;background:url(img/_avatar.png) center/118% no-repeat}
.brand{position:absolute;left:236px;top:760px;font:700 26px/1 "Helvetica Neue",Helvetica,Arial,sans-serif;color:#e8e8e8;white-space:nowrap}
</style></head><body><div class="glow"></div>
<div class="left"><div class="tag">__TAG__</div><div class="h">__H__</div>__SUB____BTN__</div>
<div class="card" style="__CARD__"><img src="img/__IMG__"></div>
<div class="me"></div><div class="brand">__HANDLE__</div></body></html>"""

def pick_twitter(n, tw):
    if tw and tw.get("slides"): return [i - 1 for i in tw["slides"]][:4]
    if n <= 4: return list(range(n))
    return sorted({0, round((n-1)/3), round(2*(n-1)/3), n-1})

def build_pdf(jpgs, out):
    W, H = 1080, 1350
    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"); offs = {}
    def add(n, body):
        offs[n] = len(buf); buf.extend(f"{n} 0 obj\n".encode() + body + b"\nendobj\n")
    kids, nxt = [], 3
    for f in jpgs:
        b = open(f, "rb").read(); w = h = None; i = 2
        while i < len(b):
            m, L = b[i+1], struct.unpack(">H", b[i+2:i+4])[0]
            if m in (0xC0, 0xC1, 0xC2): h, w = struct.unpack(">HH", b[i+5:i+9]); break
            i += 2 + L
        pg, ct, im = nxt, nxt+1, nxt+2; nxt += 3; kids.append(pg)
        add(pg, f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {W} {H}] /Resources << /XObject << /Im0 {im} 0 R >> >> /Contents {ct} 0 R >>".encode())
        s = f"q {W} 0 0 {H} 0 0 cm /Im0 Do Q".encode()
        add(ct, f"<< /Length {len(s)} >>\nstream\n".encode() + s + b"\nendstream")
        add(im, f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {len(b)} >>\nstream\n".encode() + b + b"\nendstream")
    add(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    add(2, f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode())
    x = len(buf)
    buf.extend(f"xref\n0 {nxt}\n0000000000 65535 f \n".encode())
    for i in range(1, nxt): buf.extend(f"{offs[i]:010d} 00000 n \n".encode())
    buf.extend(f"trailer\n<< /Size {nxt} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode())
    open(out, "wb").write(buf)

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    spec_path = os.path.abspath(sys.argv[1]); base = os.path.dirname(spec_path)
    out = os.path.abspath(sys.argv[sys.argv.index("--out")+1]) if "--out" in sys.argv else os.path.join(base, "build")
    spec = json.load(open(spec_path))
    for d in ("img", "slides", "_tmp"): os.makedirs(os.path.join(out, d), exist_ok=True)
    # copy images (flat names) + avatar, measure aspect ratios
    def stage(p):
        src = p if os.path.isabs(p) else os.path.join(base, p)
        name = os.path.basename(src).replace(" ", "_")
        shutil.copy(src, os.path.join(out, "img", name)); return name, os.path.join(out, "img", name)
    av = spec["brand"].get("avatar") or os.path.join(HERE, "assets", "avatar.png")
    shutil.copy(av if os.path.isabs(av) else os.path.join(base, av), os.path.join(out, "img", "_avatar.png"))
    for s in spec["slides"]:
        s["img"], p = stage(s["img"]); w, h = img_size(p); s["ar"] = w / h
    open(os.path.join(out, "carousel.html"), "w").write(CAROUSEL.replace("__SPEC__", json.dumps(spec)))
    n = len(spec["slides"]); jpgs = []
    for i in range(n):
        k = f"{i+1:02d}"; url = f"file://{out}/carousel.html?p={i}"
        shot(url, f"{out}/slides/slide-{k}.png", 1080, 1350, 1)
        t = f"{out}/_tmp/s{k}"; shot(url, t + ".png", 1080, 1350, 2)
        run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "92", t + ".png", "--out", t + ".jpg"]); jpgs.append(t + ".jpg")
    build_pdf(jpgs, f"{out}/carousel.pdf")
    # thumbnail
    th = spec.get("thumbnail")
    if th:
        name, p = stage(th["img"]); w, h = img_size(p); ar = w / h
        if ar < 0.9:  cw = 390; ch = min(550, cw / ar); top = 40
        else:         cw = 430; ch = cw / ar; top = 315 - ch / 2
        card = f"left:{1050-cw}px;top:{top}px;width:{cw}px;height:{ch}px"
        html = (THUMB.replace("__TAG__", th.get("tag", "")).replace("__LINES__", "<br>".join(th["lines"]))
                .replace("__CARD__", card).replace("__IMG__", name).replace("__HANDLE__", spec["brand"]["handle"]))
        open(f"{out}/thumbnail.html", "w").write(html)
        shot(f"file://{out}/thumbnail.html", f"{out}/thumbnail.png", 1200, 630, 1)
        shot(f"file://{out}/thumbnail.html", f"{out}/<EMAIL>", 1200, 630, 2)

    # X / Twitter: max 4 images (1600x900) + tweet text
    tw = spec.get("twitter")
    if tw is not None:
        os.makedirs(f"{out}/twitter", exist_ok=True)
        idx = pick_twitter(n, tw)
        for k, si in enumerate(idx, 1):
            s = spec["slides"][si]; ar = s["ar"]
            if ar >= 1: cw = 640; ch = min(620, cw / ar)
            else:       ch = 620; cw = ch * ar
            card = f"left:{1440-cw}px;top:{450-ch/2}px;width:{cw}px;height:{ch}px"
            sub = f'<div class="sub">{s["sub"]}</div>' if s.get("sub") else ""
            btn = f'<div class="btn">{s["cta"]}</div>' if s.get("cta") else ""
            html = (TWITTER.replace("__TAG__", f"{k:02d} / {len(idx):02d}").replace("__H__", s["h"])
                    .replace("__SUB__", sub).replace("__BTN__", btn).replace("__CARD__", card)
                    .replace("__IMG__", s["img"]).replace("__HANDLE__", spec["brand"]["handle"]))
            open(f"{out}/_t{k}.html", "w").write(html)
            shot(f"file://{out}/_t{k}.html", f"{out}/twitter/twitter-{k}.png", 1600, 900, 1)
            os.remove(f"{out}/_t{k}.html")
        text = tw.get("text", "")
        open(f"{out}/twitter/tweet.txt", "w").write(text + "\n")
        if len(text) > 280: print(f"WARNING: tweet is {len(text)} chars (limit 280; each URL counts as 23)")
    shutil.rmtree(f"{out}/_tmp")
    print(f"OK -> {out}\n  carousel.pdf ({n} pages, 1080x1350pt)\n  slides/slide-01..{n:02d}.png\n  thumbnail.png (+@2x)" + ("\n  twitter/twitter-1..4.png + tweet.txt" if tw is not None else "") if th else f"OK -> {out}")

main()
