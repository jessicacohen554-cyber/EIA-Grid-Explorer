"""
Build script for EIA Grid Explorer
Combines EIA Grid Story (historic mix 2019-2025) and 3D Grid Viz (hourly grid story)
into a single page with shared header, tile map selector, and toggle between modes.

Strategy:
  - Historic mode functions get a simple gs* prefix rename
  - Hourly mode code is wrapped in an IIFE to completely isolate its scope,
    avoiding all namespace collisions. Only hvInit() is exposed globally.
  - The shared REGIONS object uses .name/.desc (from EIA Grid Story).
    The hourly IIFE receives REGIONS and maps .n/.d aliases so existing code works.
"""
import re, os

BASE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(BASE)

# ── Read source files ─────────────────────────────────────────────────────────
# Try sibling directories first (original layout), fall back to src/ (repo layout)
grid_story_path = os.path.join(PARENT, "EIA Grid Story", "grid-story.html")
if not os.path.exists(grid_story_path):
    grid_story_path = os.path.join(BASE, "src", "grid-story.html")

grid_viz_path = os.path.join(PARENT, "3D Grid Viz", "grid_story.html")
if not os.path.exists(grid_viz_path):
    grid_viz_path = os.path.join(BASE, "src", "grid_story.html")

with open(grid_story_path, "r", encoding="utf-8") as f:
    gs_lines = f.readlines()

with open(grid_viz_path, "r", encoding="utf-8") as f:
    gv_lines = f.readlines()

gs_text = "".join(gs_lines)
gv_text = "".join(gv_lines)

# ── Extract data blobs ────────────────────────────────────────────────────────
gs_data_line = ""
for line in gs_lines:
    if line.strip().startswith("const INLINE_DATA"):
        gs_data_line = line.strip()
        break

gv_data_line = ""
for line in gv_lines:
    if line.strip().startswith("const RDATA"):
        gv_data_line = line.strip()
        break

print(f"  INLINE_DATA: {len(gs_data_line)} chars")
print(f"  RDATA: {len(gv_data_line)} chars")

# ── Extract Highcharts + Sankey from 3D Grid Viz head ─────────────────────────
head_section = gv_text.split("<style>")[0]
script_blocks = re.findall(r'<script>(.*?)</script>', head_section, re.DOTALL)

highcharts_js = ""
sankey_js = ""
for block in script_blocks:
    block_stripped = block.strip()
    if "Highcharts" in block_stripped[:200] and "sankey" not in block_stripped[:200].lower():
        highcharts_js = block_stripped
    elif "Sankey" in block_stripped[:300] or "sankey" in block_stripped[:300]:
        sankey_js = block_stripped

print(f"  Highcharts JS: {len(highcharts_js)} chars")
print(f"  Sankey JS: {len(sankey_js)} chars")

# ── Extract tile map SVG paths from EIA Grid Story ────────────────────────────
tile_paths_match = re.search(r"const T=(\{[^;]+\});", gs_text)
tile_paths = tile_paths_match.group(1) if tile_paths_match else "{}"
print(f"  Tile paths: {len(tile_paths)} chars")

# ── Extract historic mode viz functions (viz2 through viz7) ───────────────────
# These are lines 309-528 in the EIA Grid Story source
# Stop before sliderStep (line 532) since we provide our own gsSliderStep
gs_viz_lines = []
capture = False
for i, line in enumerate(gs_lines):
    ln = i + 1
    stripped = line.strip()
    # Start at viz2 definition
    if stripped.startswith("function viz2("):
        capture = True
    if capture:
        # Stop before sliderStep and any functions after viz7
        if stripped.startswith("function sliderStep(") or stripped.startswith("function setupScrollObserver(") or stripped.startswith("function goToStep("):
            break
        gs_viz_lines.append(line)

gs_viz_code = "".join(gs_viz_lines)

# Rename viz functions with gs prefix using word-boundary-safe replacements
gs_viz_code = re.sub(r'\bviz2\b', 'gsViz2', gs_viz_code)
gs_viz_code = re.sub(r'\bviz3\b', 'gsViz3', gs_viz_code)
gs_viz_code = re.sub(r'\bviz4\b', 'gsViz4', gs_viz_code)
gs_viz_code = re.sub(r'\bviz5\b', 'gsViz5', gs_viz_code)
gs_viz_code = re.sub(r'\bviz6\b', 'gsViz6', gs_viz_code)
gs_viz_code = re.sub(r'\bviz7\b', 'gsViz7', gs_viz_code)
# setupCanvas → gsSetupCanvas (only in historic viz code)
gs_viz_code = re.sub(r'\bsetupCanvas\b', 'gsSetupCanvas', gs_viz_code)
# DATA.annual / DATA.monthly → GS_DATA.annual / GS_DATA.monthly
gs_viz_code = gs_viz_code.replace("DATA.annual", "GS_DATA.annual")
gs_viz_code = gs_viz_code.replace("DATA.monthly", "GS_DATA.monthly")
# animFrames → gsAnimFrames (only in viz code)
gs_viz_code = re.sub(r'\banimFrames\b', 'gsAnimFrames', gs_viz_code)
# window.onSlider → window.gsOnSlider
gs_viz_code = gs_viz_code.replace("window.onSlider2", "window.gsOnSlider2")
gs_viz_code = gs_viz_code.replace("window.onSlider4", "window.gsOnSlider4")
gs_viz_code = gs_viz_code.replace("window.onSlider6", "window.gsOnSlider6")

print(f"  Historic viz code: {len(gs_viz_code)} chars")

# ── Extract hourly mode viz functions (rateColor through buildSankey) ─────────
# We capture from COL definition through end of buildSankey, but EXCLUDE:
#   - const REGIONS, RCOL, ACTIVE (already defined / not needed)
#   - let selReg=null, curStep=0, animFrames={} (IIFE has its own)
#   - buildMap(), selectRegion(), buildStory(), setupObs(), goToStep()
#     (we use our shared/custom versions of these)

# Functions to skip entirely (we provide our own implementations)
SKIP_FUNCS = ["buildMap()", "selectRegion(", "buildStory(", "setupObs()", "goToStep("]

gv_viz_lines = []
capture = False
skip_func = False
brace_depth = 0
for i, line in enumerate(gv_lines):
    ln = i + 1
    stripped = line.strip()

    # Start capture at COL definition (line 312)
    if stripped.startswith("const COL = {") or stripped.startswith("const COL={"):
        capture = True

    if not capture:
        continue

    # Stop BEFORE window.addEventListener (scroll progress) — we provide our own
    if "window.addEventListener('scroll'" in stripped or "window.addEventListener(\"scroll\"" in stripped:
        break
    # Also stop at DOMContentLoaded
    if "DOMContentLoaded" in stripped:
        break

    # Skip single-line declarations we don't need
    if stripped.startswith("const REGIONS =") or stripped.startswith("const REGIONS="):
        continue
    if stripped.startswith("const RCOL =") or stripped.startswith("const RCOL="):
        continue
    if stripped.startswith("const ACTIVE =") or stripped.startswith("const ACTIVE="):
        continue
    if stripped.startswith("let selReg="):
        continue

    # Check if this line starts a function we want to skip
    if not skip_func:
        for func_sig in SKIP_FUNCS:
            if f"function {func_sig}" in stripped:
                skip_func = True
                brace_depth = 0
                break

    if skip_func:
        brace_depth += line.count("{") - line.count("}")
        if brace_depth <= 0 and brace_depth + line.count("}") > 0:
            # We've closed all braces — function is complete
            skip_func = False
        continue

    gv_viz_lines.append(line)

gv_viz_code = "".join(gv_viz_lines)
print(f"  Hourly viz code: {len(gv_viz_code)} chars")

# ── Build the combined HTML ────────────────────────────────────────────────────
html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EIA Grid Explorer: Regional Grid Data &amp; Hourly Analysis</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script>{highcharts_js}</script>
<script>{sankey_js}</script>
<style>
:root {{
  --c-navy:#0A2540; --c-navy-dark:#061B2E; --c-navy-mid:#0F3460;
  --c-blue:#2372B9; --c-blue-light:#60A5FA; --c-blue-pale:#DBEAFE;
  --c-gold:#FBB254; --c-orange:#F47B27; --c-green:#6BA543; --c-lime:#CADB2E;
  --c-white:#fff;
  --c-gray-50:#F8FAFC; --c-gray-100:#F1F5F9; --c-gray-200:#E2E8F0;
  --c-gray-300:#CBD5E1; --c-gray-400:#94A3B8; --c-gray-500:#64748B;
  --c-gray-600:#475569; --c-gray-700:#334155; --c-gray-800:#1E293B;
  --font:'Plus Jakarta Sans','Inter','Segoe UI',sans-serif;
  --font-heading:'Plus Jakarta Sans','Inter','Segoe UI Semibold',sans-serif;
  --radius-sm:8px; --radius-md:12px; --radius-lg:16px; --radius-pill:9999px;
  --shadow-md:0 4px 6px -1px rgba(0,0,0,0.07),0 2px 4px -2px rgba(0,0,0,0.05);
  --shadow-lg:0 10px 15px -3px rgba(0,0,0,0.08),0 4px 6px -4px rgba(0,0,0,0.04);
  --glass-bg:rgba(255,255,255,0.88); --glass-border:rgba(126,128,131,0.18);
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{font-size:16px;scroll-behavior:smooth}}
body{{font-family:var(--font);color:var(--c-gray-700);background:var(--c-gray-50);line-height:1.7;-webkit-font-smoothing:antialiased;overflow-x:hidden;}}

/* ═══ HEADER ═══ */
.header{{background:#0A2540;color:var(--c-white);padding:60px 24px 56px;text-align:center;position:relative;overflow:hidden;}}
.header::before{{content:'';position:absolute;inset:0;background:linear-gradient(135deg,#0A2540 0%,#1a5a9e 18%,#2372B9 32%,#F47B27 52%,#6BA543 72%,#CADB2E 100%);opacity:0.92;pointer-events:none;}}
.header::after{{content:'';position:absolute;inset:0;background:radial-gradient(circle 320px at 15% 60%,rgba(35,114,185,0.35) 0%,transparent 70%),radial-gradient(circle 250px at 50% 30%,rgba(244,123,39,0.18) 0%,transparent 60%),radial-gradient(circle 280px at 85% 55%,rgba(107,165,67,0.22) 0%,transparent 65%),radial-gradient(circle 180px at 35% 20%,rgba(255,255,255,0.04) 0%,transparent 50%),radial-gradient(rgba(255,255,255,0.035) 1px,transparent 1px);background-size:100% 100%,100% 100%,100% 100%,100% 100%,18px 18px;pointer-events:none;}}
.header-accent{{position:absolute;bottom:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#2372B9 0%,#2372B9 33%,#F47B27 33%,#F47B27 66%,#6BA543 66%,#6BA543 100%);z-index:2;}}
.header h1{{font-family:var(--font-heading);font-size:2.6rem;font-weight:800;letter-spacing:-1px;margin-bottom:12px;position:relative;z-index:1;text-shadow:0 2px 12px rgba(0,0,0,0.25);line-height:1.15;}}
.header .subtitle{{font-size:1.05rem;font-weight:400;opacity:0.92;max-width:640px;margin:0 auto;letter-spacing:0.1px;position:relative;z-index:1;text-shadow:0 1px 6px rgba(0,0,0,0.2);line-height:1.55;}}

/* ═══ MAP SECTION ═══ */
.map-section{{max-width:1100px;margin:40px auto 0;padding:0 24px;text-align:center;}}
.map-section h2{{font-family:var(--font-heading);font-size:1.8rem;font-weight:800;color:var(--c-navy);letter-spacing:-0.5px;margin-bottom:8px;}}
.map-section .map-sub{{color:var(--c-gray-500);font-size:0.95rem;margin-bottom:24px;}}
.map-card{{background:var(--glass-bg);backdrop-filter:blur(12px);border:1px solid var(--glass-border);border-radius:var(--radius-lg);padding:32px;box-shadow:var(--shadow-lg);}}
#map-container{{max-width:920px;margin:0 auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px;padding:0 8px;}}
.region-tile{{position:relative;border-radius:var(--radius-md);background:var(--glass-bg);backdrop-filter:blur(8px);border:2px solid var(--c-gray-200);cursor:pointer;padding:12px 8px 10px;display:flex;flex-direction:column;align-items:center;gap:4px;transition:all 0.25s ease;overflow:hidden;}}
.region-tile:hover{{border-color:var(--c-blue);background:rgba(35,114,185,0.06);transform:translateY(-2px);box-shadow:0 4px 12px rgba(35,114,185,0.15);}}
.region-tile.active{{border-color:var(--c-gold);background:rgba(251,178,84,0.08);box-shadow:0 4px 16px rgba(251,178,84,0.2);}}
.region-tile svg{{width:100%;height:70px;display:block;}}
.region-tile svg path{{fill:var(--c-blue);opacity:0.25;transition:opacity 0.25s ease,fill 0.25s ease;}}
.region-tile:hover svg path{{opacity:0.4;}}
.region-tile.active svg path{{fill:var(--c-gold);opacity:0.5;}}
.region-tile .tile-name{{font:700 0.82rem var(--font-heading);color:var(--c-navy);text-align:center;line-height:1.2;letter-spacing:-0.2px;}}
.region-tile .tile-code{{font:600 0.65rem var(--font);color:var(--c-gray-400);text-transform:uppercase;letter-spacing:1px;}}
.region-tile:hover .tile-name{{color:var(--c-blue);}}
.region-tile.active .tile-name{{color:var(--c-navy);}}

/* ═══ REGION BANNER ═══ */
.region-banner{{text-align:center;padding:20px;margin:24px auto 0;max-width:1100px;border-radius:var(--radius-md);background:linear-gradient(135deg,rgba(35,114,185,0.06) 0%,rgba(107,165,67,0.04) 100%);border:1px solid rgba(35,114,185,0.12);display:none;}}
.region-banner h2{{font-family:var(--font-heading);font-size:1.8rem;font-weight:800;color:var(--c-navy);letter-spacing:-0.5px;}}
.region-banner p{{color:var(--c-gray-500);font-size:0.9rem;margin-top:4px;}}

/* ═══ MODE TOGGLE ═══ */
.mode-toggle-section{{max-width:1100px;margin:24px auto 0;padding:0 24px;text-align:center;display:none;}}
.mode-toggle-section.visible{{display:block;}}
.mode-toggle{{display:inline-flex;background:var(--glass-bg);backdrop-filter:blur(12px);border:1px solid var(--glass-border);border-radius:var(--radius-pill);padding:4px;box-shadow:var(--shadow-md);}}
.mode-btn{{padding:12px 28px;border-radius:var(--radius-pill);border:none;background:transparent;font-family:var(--font);font-size:0.92rem;font-weight:600;color:var(--c-gray-500);cursor:pointer;transition:all 0.3s ease;white-space:nowrap;}}
.mode-btn:hover{{color:var(--c-navy);}}
.mode-btn.active{{background:var(--c-navy);color:var(--c-white);box-shadow:0 2px 8px rgba(10,37,64,0.25);}}
.mode-desc{{margin-top:12px;font-size:0.88rem;color:var(--c-gray-500);}}

/* ═══ SHARED STORY STYLES ═══ */
.story-container{{position:relative;display:none;max-width:1400px;margin:0 auto;}}
.story-container.visible{{display:flex;}}
.viz-sticky{{position:sticky;top:0;width:55%;height:100vh;display:flex;align-items:center;justify-content:center;background:var(--c-gray-50);z-index:1;overflow:hidden;}}
.viz-panel{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;opacity:0;transform:scale(0.96) translateY(12px);transition:opacity 0.8s cubic-bezier(0.4,0,0.2,1),transform 0.8s cubic-bezier(0.4,0,0.2,1);pointer-events:none;}}
.viz-panel.active{{opacity:1;transform:scale(1) translateY(0);pointer-events:auto;}}
.viz-panel canvas{{width:100%;height:100%;border-radius:var(--radius-md);}}
.viz-caption{{position:absolute;bottom:24px;left:24px;background:rgba(255,255,255,0.92);backdrop-filter:blur(12px);border:1px solid var(--glass-border);border-radius:var(--radius-md);padding:14px 20px;max-width:360px;font-size:0.82rem;color:var(--c-gray-600);line-height:1.6;box-shadow:var(--shadow-lg);z-index:10;opacity:0;transition:opacity 0.6s ease;}}
.viz-caption.visible{{opacity:1;}}
.viz-controls{{position:absolute;top:20px;left:50%;transform:translateX(-50%);z-index:20;display:flex;align-items:center;gap:12px;background:rgba(255,255,255,0.92);backdrop-filter:blur(12px);border:1px solid var(--glass-border);border-radius:var(--radius-pill);padding:8px 20px;box-shadow:var(--shadow-md);}}
.viz-controls .yr-label{{font:700 15px var(--font);color:var(--c-navy);min-width:42px;text-align:center;}}
.viz-controls input[type=range]{{-webkit-appearance:none;appearance:none;width:180px;height:6px;border-radius:3px;background:var(--c-gray-200);outline:none;cursor:pointer;}}
.viz-controls input[type=range]::-webkit-slider-thumb{{-webkit-appearance:none;appearance:none;width:20px;height:20px;border-radius:50%;background:var(--c-blue);border:3px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.2);cursor:pointer;transition:transform 0.15s ease;}}
.viz-controls input[type=range]::-webkit-slider-thumb:hover{{transform:scale(1.2);}}
.viz-controls input[type=range]::-moz-range-thumb{{width:20px;height:20px;border-radius:50%;background:var(--c-blue);border:3px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.2);cursor:pointer;}}
.viz-controls .yr-btn{{background:none;border:2px solid var(--c-gray-300);border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;cursor:pointer;font:700 14px var(--font);color:var(--c-gray-600);transition:all 0.2s ease;}}
.viz-controls .yr-btn:hover{{border-color:var(--c-blue);color:var(--c-blue);}}
.viz-caption .cap-label{{font-weight:700;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.8px;color:var(--c-blue);margin-bottom:4px;}}

/* ═══ SLIDER SWEEP ANIMATION ═══ */
@keyframes sliderGlow {{
  0%,100% {{ box-shadow:0 0 0 0 rgba(35,114,185,0); }}
  50% {{ box-shadow:0 0 16px 4px rgba(35,114,185,0.35); }}
}}
@keyframes sliderHintFade {{
  0% {{ opacity:0; transform:translateX(-50%) translateY(6px); }}
  15% {{ opacity:1; transform:translateX(-50%) translateY(0); }}
  85% {{ opacity:1; transform:translateX(-50%) translateY(0); }}
  100% {{ opacity:0; transform:translateX(-50%) translateY(-4px); }}
}}
.viz-controls.sweeping {{
  animation:sliderGlow 0.6s ease-in-out 3;
  border-color:var(--c-blue);
}}
.viz-controls.sweeping input[type=range]::-webkit-slider-thumb {{
  background:var(--c-gold);
  transform:scale(1.3);
  box-shadow:0 2px 8px rgba(251,178,84,0.4);
}}
.slider-hint {{
  position:absolute;top:100%;left:50%;transform:translateX(-50%);
  margin-top:10px;white-space:nowrap;
  font:600 0.72rem var(--font);color:var(--c-blue);
  background:rgba(255,255,255,0.95);backdrop-filter:blur(8px);
  border:1px solid rgba(35,114,185,0.2);border-radius:var(--radius-pill);
  padding:5px 14px;box-shadow:var(--shadow-md);
  opacity:0;pointer-events:none;
  animation:sliderHintFade 4s ease forwards;
  animation-delay:2.2s;
}}
.narrative-column{{width:45%;position:relative;z-index:2;padding:0;}}
.story-step{{min-height:100vh;display:flex;align-items:center;padding:80px 48px 80px 56px;}}
.step-inner{{max-width:440px;opacity:0;transform:translateY(40px);transition:opacity 0.8s cubic-bezier(0.4,0,0.2,1),transform 0.8s cubic-bezier(0.4,0,0.2,1);}}
.story-step.active .step-inner{{opacity:1;transform:translateY(0);}}
.step-badge{{display:inline-block;padding:4px 14px;border-radius:var(--radius-pill);font-size:0.68rem;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:16px;}}
.step-badge.blue{{background:rgba(35,114,185,0.12);color:var(--c-blue);}}
.step-badge.orange{{background:rgba(244,123,39,0.12);color:#D4820C;}}
.step-badge.green{{background:rgba(107,165,67,0.12);color:#6BA543;}}
.step-badge.gold{{background:rgba(251,178,84,0.12);color:#B8860B;}}
.step-badge.navy{{background:rgba(10,37,64,0.12);color:var(--c-navy);}}
.step-badge.red{{background:rgba(192,57,43,0.12);color:#C0392B;}}
.step-inner h2{{font-size:1.8rem;font-weight:800;color:var(--c-navy);letter-spacing:-0.8px;line-height:1.15;margin-bottom:16px;}}
.step-inner p{{font-size:1.02rem;color:var(--c-gray-600);line-height:1.75;margin-bottom:16px;}}
.step-inner p:last-child{{margin-bottom:0;}}
.step-inner .hl{{font-weight:700;}}
.step-inner .hl.blue{{color:var(--c-blue);}}
.step-inner .hl.orange{{color:#D4820C;}}
.step-inner .hl.green{{color:#6BA543;}}
.step-inner .hl.gold{{color:#B8860B;}}
.step-inner .hl.red{{color:#C0392B;}}
.stat-row{{display:flex;gap:20px;margin:20px 0;flex-wrap:wrap;}}
.stat-box{{flex:1;min-width:100px;background:var(--glass-bg);border:1px solid var(--glass-border);border-radius:var(--radius-md);padding:16px;text-align:center;backdrop-filter:blur(8px);}}
.stat-box .sv{{font-size:1.6rem;font-weight:800;letter-spacing:-0.5px;font-variant-numeric:tabular-nums;color:var(--c-navy);line-height:1.1;}}
.stat-box .sl{{font-size:0.72rem;color:var(--c-gray-500);margin-top:4px;font-weight:500;}}
.inline-gradient{{height:10px;border-radius:5px;margin:12px 0;background:linear-gradient(90deg,#2372B9 0%,#6BA543 25%,#CADB2E 40%,#FBB254 55%,#D4820C 70%,#F47B27 82%,#C0392B 100%);border:1px solid rgba(0,0,0,0.08);}}
.gradient-labels{{display:flex;justify-content:space-between;font-size:0.68rem;color:var(--c-gray-400);font-weight:600;}}

/* ═══ VIZ LABELS (Hourly mode) ═══ */
.viz-label{{font-size:0.82rem;font-weight:700;color:var(--c-navy);letter-spacing:0.5px;text-transform:uppercase;margin-bottom:12px;text-align:center;}}
.viz-sublabel{{font-size:0.78rem;color:var(--c-gray-500);margin-top:8px;text-align:center;max-width:400px;line-height:1.5;}}

/* ═══ CTA / FOOTER ═══ */
.cta-section{{background:var(--c-navy);color:var(--c-white);padding:100px 48px;text-align:center;position:relative;overflow:hidden;display:none;}}
.cta-section.visible{{display:block;}}
.cta-section::before{{content:'';position:absolute;inset:0;background:linear-gradient(135deg,#0A2540 0%,#1a5a9e 40%,#2372B9 100%);opacity:0.95;}}
.cta-content{{position:relative;z-index:2;max-width:680px;margin:0 auto;}}
.cta-content h2{{font-size:2.4rem;font-weight:800;letter-spacing:-1px;margin-bottom:20px;line-height:1.1;}}
.cta-content p{{font-size:1.05rem;opacity:0.8;line-height:1.7;margin-bottom:32px;}}
.footer-attr{{text-align:center;padding:20px 24px 40px;font-size:0.78rem;color:var(--c-gray-400);background:var(--c-gray-50);max-width:1100px;margin:0 auto;line-height:1.6;display:none;}}
.footer-attr.visible{{display:block;}}
.scroll-progress{{position:fixed;top:0;left:0;height:3px;z-index:1001;background:linear-gradient(90deg,var(--c-blue),#F47B27,var(--c-green));width:0%;transition:width 0.1s;}}
.bottom-bar{{position:fixed;bottom:0;left:0;right:0;height:4px;z-index:1000;background:linear-gradient(90deg,#2372B9 0%,#2372B9 33%,#F47B27 33%,#F47B27 66%,#6BA543 66%,#6BA543 100%);}}

@media(max-width:1024px){{
  .story-container.visible{{display:block;}}
  .viz-sticky{{width:100%;height:50vh;}}
  .narrative-column{{width:100%;}}
  .story-step{{min-height:auto;padding:48px 24px;}}
}}
@media(max-width:768px){{
  .header{{padding:40px 16px 36px;}}
  .header h1{{font-size:1.8rem;letter-spacing:-0.5px;}}
  .header .subtitle{{font-size:0.88rem;}}
  .map-section{{padding:0 12px;margin-top:24px;}}
  .map-section h2{{font-size:1.4rem;}}
  .map-card{{padding:16px;}}
  #map-container{{grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:8px;padding:0;}}
  .region-tile{{padding:8px 4px 6px;}}
  .region-tile svg{{height:48px;}}
  .region-tile .tile-name{{font-size:0.7rem;}}
  .region-tile .tile-code{{font-size:0.58rem;}}
  .region-banner{{margin:16px 12px 0;padding:14px;}}
  .region-banner h2{{font-size:1.3rem;}}
  .mode-toggle-section{{padding:0 12px;margin-top:16px;}}
  .mode-toggle{{flex-direction:column;gap:4px;border-radius:var(--radius-md);}}
  .mode-btn{{padding:10px 20px;font-size:0.82rem;border-radius:var(--radius-md);}}
  .viz-sticky{{height:45vh;}}
  .viz-controls{{padding:6px 12px;gap:8px;}}
  .viz-controls input[type=range]{{width:120px;}}
  .viz-controls .yr-label{{font-size:13px;min-width:36px;}}
  .viz-controls .yr-btn{{width:24px;height:24px;font-size:12px;}}
  .step-inner h2{{font-size:1.35rem;}}
  .step-inner p{{font-size:0.92rem;}}
  .stat-row{{gap:10px;}}
  .stat-box{{min-width:70px;padding:10px;}}
  .stat-box .sv{{font-size:1.25rem;}}
  .stat-box .sl{{font-size:0.65rem;}}
  .viz-label{{font-size:0.72rem;}}
  .viz-sublabel{{font-size:0.68rem;max-width:300px;}}
  .cta-section{{padding:60px 20px;}}
  .cta-content h2{{font-size:1.6rem;}}
  .cta-content p{{font-size:0.9rem;}}
  .slider-hint{{font-size:0.65rem;padding:4px 10px;}}
}}
@media(max-width:480px){{
  .header{{padding:28px 12px 24px;}}
  .header h1{{font-size:1.5rem;}}
  .header .subtitle{{font-size:0.8rem;line-height:1.45;}}
  #map-container{{grid-template-columns:repeat(auto-fill,minmax(75px,1fr));gap:6px;}}
  .region-tile svg{{height:36px;}}
  .viz-sticky{{height:38vh;}}
  .story-step{{padding:32px 16px;}}
  .step-inner h2{{font-size:1.15rem;}}
  .step-inner p{{font-size:0.85rem;line-height:1.6;}}
  .viz-controls{{flex-wrap:wrap;justify-content:center;}}
  .mode-desc{{font-size:0.78rem;}}
}}
</style>
</head>
<body>
<div class="scroll-progress" id="progressBar"></div>

<header class="header">
  <h1>Grid Explorer</h1>
  <p class="subtitle">Explore how America's electricity grid works &mdash; from historic generation mix trends (2019&ndash;2025) to hour-by-hour grid operations across 13 regions</p>
  <div class="header-accent"></div>
</header>

<section class="map-section">
  <h2>Choose Your Grid Region</h2>
  <p class="map-sub">Click a region to explore its energy data. Then choose between historic trends or hourly grid analysis.</p>
  <div class="map-card"><div id="map-container"></div></div>
</section>

<div class="region-banner" id="region-banner">
  <h2 id="region-title"></h2>
  <p id="region-subtitle"></p>
</div>

<div class="mode-toggle-section" id="modeToggleSection">
  <div class="mode-toggle">
    <button class="mode-btn active" id="btnHistoric" onclick="setMode('historic')">Historic Grid Mix (2019&ndash;2025)</button>
    <button class="mode-btn" id="btnHourly" onclick="setMode('hourly')">How This Grid Works (Hourly)</button>
  </div>
  <p class="mode-desc" id="modeDesc">Explore how the generation mix has changed across 7 years of EIA data.</p>
</div>

<!-- ═══════════ HISTORIC MODE (EIA Grid Story) ═══════════ -->
<div class="story-container" id="historicContainer">
  <div class="viz-sticky" id="vizStickyH">
    <div class="viz-panel active" id="vizPanel2"><canvas id="c2"></canvas><div class="viz-controls" id="ctrl2"><button class="yr-btn" onclick="gsSliderStep('s2',-1)">&lsaquo;</button><input type="range" id="s2" min="0" max="6" value="0" oninput="gsOnSlider2()"><button class="yr-btn" onclick="gsSliderStep('s2',1)">&rsaquo;</button><span class="yr-label" id="lbl2">2019</span></div></div>
    <div class="viz-panel" id="vizPanel3"><canvas id="c3"></canvas></div>
    <div class="viz-panel" id="vizPanel4"><canvas id="c4"></canvas><div class="viz-controls" id="ctrl4"><button class="yr-btn" onclick="gsSliderStep('s4',-1)">&lsaquo;</button><input type="range" id="s4" min="0" max="6" value="0" oninput="gsOnSlider4()"><button class="yr-btn" onclick="gsSliderStep('s4',1)">&rsaquo;</button><span class="yr-label" id="lbl4">2019</span></div></div>
    <div class="viz-panel" id="vizPanel5"><canvas id="c5"></canvas></div>
    <div class="viz-panel" id="vizPanel6"><canvas id="c6"></canvas><div class="viz-controls" id="ctrl6"><button class="yr-btn" onclick="gsSliderStep('s6',-1)">&lsaquo;</button><input type="range" id="s6" min="0" max="6" value="0" oninput="gsOnSlider6()"><button class="yr-btn" onclick="gsSliderStep('s6',1)">&rsaquo;</button><span class="yr-label" id="lbl6">2019</span></div></div>
    <div class="viz-panel" id="vizPanel7"><canvas id="c7"></canvas></div>
  </div>
  <div class="narrative-column" id="narrativeColumnH"></div>
</div>

<!-- ═══════════ HOURLY MODE (3D Grid Viz) ═══════════ -->
<div class="story-container" id="hourlyContainer">
  <div class="viz-sticky" id="vizStickyHr">
    <div class="viz-panel" id="hvPanel1" data-act="1">
      <div class="viz-label" id="hvLbl1">Every Hour of Electricity Generation in 2024</div>
      <canvas id="cvs1"></canvas>
      <div class="viz-sublabel" id="hvSub1">Each dot is one hour. Color shows grid emission intensity: <span style="color:#2372B9">blue = clean</span>, <span style="color:#C0392B">red = dirty</span></div>
    </div>
    <div class="viz-panel" id="hvPanel2" data-act="2">
      <div class="viz-label" id="hvLbl2">The Clean Baseload: Nuclear + Hydro, Every Hour</div>
      <canvas id="cvs2"></canvas>
      <div class="viz-sublabel">Blue area = clean firm generation (nuclear + hydro). Gray area = total grid load.</div>
    </div>
    <div class="viz-panel" id="hvPanel3" data-act="3">
      <div class="viz-label" id="hvLbl3">A Typical Summer Day: How the Stack Dispatches</div>
      <canvas id="cvs3"></canvas>
      <div class="viz-sublabel">Stacked generation by source across 24 hours. Fossil fuels ramp up as demand rises.</div>
    </div>
    <div class="viz-panel" id="hvPanel4" data-act="4">
      <div class="viz-label" id="hvLbl4">Wind + Solar by Month: When Nature Delivers</div>
      <canvas id="cvs4"></canvas>
      <div class="viz-sublabel">Top two rows: wind. Bottom two rows: solar. Each tile is one month's average 24-hour profile.</div>
    </div>
    <div class="viz-panel" id="hvPanel5" data-act="5">
      <div class="viz-label" id="hvLbl5">Annual Average vs. Hourly Reality</div>
      <canvas id="cvs5"></canvas>
      <div class="viz-sublabel">Left: the single annual number. Right: every hour revealed. The average hides the chaos.</div>
    </div>
    <div class="viz-panel" id="hvPanel6" data-act="6">
      <div class="viz-label" id="hvLbl6">Two Hours, Same Grid, Different Worlds</div>
      <canvas id="cvs6"></canvas>
      <div class="viz-sublabel">A clean hour vs. a dirty hour. The resource mix changes dramatically.</div>
    </div>
    <div class="viz-panel" id="hvPanel7" data-act="7">
      <div class="viz-label" id="hvLbl7">Where the Energy Comes From</div>
      <div id="act7-chart" style="width:100%;height:380px;"></div>
      <div class="viz-sublabel">Energy flow from generation sources to the grid. Clean vs. fossil, in TWh.</div>
    </div>
  </div>

  <div class="narrative-column" id="narrativeColumnHr">
    <div class="story-step hv-step" data-step="1" id="hvStep1"><div class="step-inner">
      <span class="step-badge blue">Act I</span>
      <h2>The Grid Never Sleeps</h2>
      <p>Right now &mdash; this very second &mdash; grid operators are orchestrating a symphony of thousands of generators to deliver electricity to millions of homes, hospitals, data centers, and factories.</p>
      <p>Every hour, they must perfectly balance supply with demand. The margin for error is razor-thin: even a small imbalance can cascade into blackouts.</p>
      <div class="stat-row">
        <div class="stat-box"><div class="sv" id="statTWh"></div><div class="sl">TWh in 2024</div></div>
        <div class="stat-box"><div class="sv" id="statHours"></div><div class="sl">Hours/year</div></div>
        <div class="stat-box"><div class="sv" id="statAvgGW"></div><div class="sl">GW avg load</div></div>
      </div>
      <p>What you see is <strong>every single hour</strong> of electricity generation in 2024 &mdash; 8,760 dots arranged in a grid. Each dot represents the grid's total output during one hour, sized by generation and colored by emission intensity.</p>
      <p><span class="hl blue">Blue and green dots</span> are the cleanest hours &mdash; nuclear, hydro, wind, and solar carried the load. <span class="hl red">Orange and red dots</span> are the dirtiest: fossil generators were ramped to maximum.</p>
      <p style="font-style:italic;opacity:0.7;font-size:0.85rem;margin-top:24px">Scroll to discover why annual accounting is misleading.</p>
    </div></div>

    <div class="story-step hv-step" data-step="2" id="hvStep2"><div class="step-inner">
      <span class="step-badge blue">Act II</span>
      <h2>The Baseload Foundation</h2>
      <p><span class="hl blue">Nuclear and hydroelectric power</span> form the grid's clean, firm foundation. They run 24/7/365 regardless of weather.</p>
      <p>The chart shows all 8,760 hours of demand (gray area) with the clean baseload (blue area) overlaid. Look at the blue band &mdash; it barely moves. That's the steady, unwavering stream of carbon-free power.</p>
      <div class="stat-row">
        <div class="stat-box"><div class="sv" id="statCF"></div><div class="sl">GW avg clean firm</div></div>
        <div class="stat-box"><div class="sv">24/7</div><div class="sl">Always on</div></div>
      </div>
    </div></div>

    <div class="story-step hv-step" data-step="3" id="hvStep3"><div class="step-inner">
      <span class="step-badge orange">Act III</span>
      <h2>When Demand Rises, Fossil Fuels Answer</h2>
      <p>This stacked area chart shows a typical summer day: 24 hours of generation broken out by fuel source. As demand climbs each morning, <span class="hl orange">fossil generators ramp up</span>. First efficient gas, then dirtier units.</p>
      <div class="inline-gradient"></div>
      <div class="gradient-labels"><span>Clean (0 kg CO&#8322;/MWh)</span><span>Dirty (high emissions)</span></div>
      <p><strong>The emission rate of every MWh changes dramatically by hour.</strong></p>
      <div class="stat-row">
        <div class="stat-box"><div class="sv" id="statMinRate"></div><div class="sl">Cleanest hours</div></div>
        <div class="stat-box"><div class="sv" id="statMaxRate"></div><div class="sl">Dirtiest hours</div></div>
      </div>
    </div></div>

    <div class="story-step hv-step" data-step="4" id="hvStep4"><div class="step-inner">
      <span class="step-badge green">Act IV</span>
      <h2>The Renewable Revolution &mdash; It's Not That Simple</h2>
      <p><span class="hl green">Wind and solar</span> have transformed the grid. But they generate when nature allows, not when needed.</p>
      <p>The heatmap grid shows 12 months of average 24-hour generation profiles &mdash; wind on top, solar on the bottom. Summer midday: solar floods the grid. Winter evenings: almost nothing. The pattern is dramatic and seasonal.</p>
    </div></div>

    <div class="story-step hv-step" data-step="5" id="hvStep5"><div class="step-inner">
      <span class="step-badge gold">Act V</span>
      <h2>The Annual Accounting Illusion</h2>
      <p>Annual Scope 2 gives one number &mdash; the single colored tile on the left showing the annual average emission rate in kg CO&#8322;/MWh. It looks clean. Reassuring.</p>
      <p>But the dot grid on the right reveals the reality: every single hour has a different emission rate. Some hours are nearly zero-carbon. Others are heavily fossil-fueled. The average hides the chaos.</p>
      <div class="stat-row">
        <div class="stat-box"><div class="sv" id="statAvgFossil"></div><div class="sl">Avg fossil share</div></div>
        <div class="stat-box"><div class="sv" id="statHighHours"></div><div class="sl">High-fossil hours</div></div>
      </div>
    </div></div>

    <div class="story-step hv-step" data-step="6" id="hvStep6"><div class="step-inner">
      <span class="step-badge red">Act VI</span>
      <h2>Every Hour Tells a Different Story</h2>
      <p>Same grid. Two hours. Radically different resource mixes. The stacked bars show the fuel breakdown for this region's single cleanest and dirtiest hours of 2024.</p>
      <p>The <span class="hl blue">clean hour</span> is dominated by nuclear and renewables. The <span class="hl red">dirty hour</span> has fossil fuels stacked high. Look at how the total height and color composition change.</p>
      <p><strong>Hourly accounting</strong> reveals what annual numbers hide.</p>
    </div></div>

    <div class="story-step hv-step" data-step="7" id="hvStep7"><div class="step-inner">
      <span class="step-badge green">Act VII</span>
      <h2>The Path Forward</h2>
      <p>The transition: from <strong>reliable + affordable</strong> to <strong>reliable + affordable + clean</strong>.</p>
      <p><strong>Hourly matching</strong> tells markets: &ldquo;We need clean power at 6 PM in January, not just sunny April afternoons.&rdquo;</p>
      <p>This drives investment in <span class="hl blue">firm clean power</span>, <span class="hl green">storage</span>, and <span class="hl orange">demand flexibility</span>.</p>
    </div></div>
  </div>
</div>

<section class="cta-section" id="ctaSection">
  <div class="cta-content">
    <h2>Every Region Has a Story. Every Hour Matters.</h2>
    <p>Data from EIA Form 930 Hourly Electric Grid Monitor, covering 2019&ndash;2025 annual trends and 2024 hourly generation across 13 grid regions.</p>
  </div>
</section>
<div class="footer-attr" id="footerAttr">Data: U.S. Energy Information Administration (EIA) Form 930 &middot; Hourly Electric Grid Monitor &middot; 2019&ndash;2025 &middot; 13 Grid Regions</div>
<div class="bottom-bar"></div>

<script>
// ═══════════════════════════════════════════════════════════════════════════
// DATA
// ═══════════════════════════════════════════════════════════════════════════
{gs_data_line}
{gv_data_line}

// ═══════════════════════════════════════════════════════════════════════════
// SHARED STATE
// ═══════════════════════════════════════════════════════════════════════════
let selectedRegion = null;
let currentMode = 'historic';

// ═══════════════════════════════════════════════════════════════════════════
// SHARED REGIONS (uses .name/.desc from EIA Grid Story format)
// ═══════════════════════════════════════════════════════════════════════════
const REGIONS = {{
  CAL:{{name:'California',desc:'CAISO / Western'}},
  CAR:{{name:'Carolinas',desc:'Duke Energy / Southeast'}},
  CENT:{{name:'Central',desc:'SPP / Central'}},
  FLA:{{name:'Florida',desc:'FRCC / Southeast'}},
  MIDA:{{name:'Mid-Atlantic',desc:'PJM Interconnection'}},
  MIDW:{{name:'Midwest',desc:'MISO / Eastern'}},
  NE:{{name:'New England',desc:'ISO-NE / Northeast'}},
  NW:{{name:'Northwest',desc:'BPA / Western'}},
  NY:{{name:'New York',desc:'NYISO / Northeast'}},
  SE:{{name:'Southeast',desc:'Southern Co / Southeast'}},
  SW:{{name:'Southwest',desc:'Western Interconnection'}},
  TEN:{{name:'Tennessee',desc:'TVA / Southeast'}},
  TEX:{{name:'Texas',desc:'ERCOT Interconnection'}}
}};

const TILE_ORDER = ['NW','CAL','SW','CENT','TEX','MIDW','MIDA','NY','NE','TEN','SE','CAR','FLA'];

function buildMap() {{
  const container = document.getElementById('map-container');
  container.innerHTML = '';
  const T = {tile_paths};
  TILE_ORDER.forEach(k => {{
    if (!T[k] || !REGIONS[k]) return;
    const tile = document.createElement('div');
    tile.className = 'region-tile'; tile.dataset.region = k;
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', T[k].vb); svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    const p = document.createElementNS(ns, 'path');
    p.setAttribute('d', T[k].d); p.setAttribute('fill-rule', 'evenodd');
    svg.appendChild(p);
    const name = document.createElement('div'); name.className = 'tile-name'; name.textContent = REGIONS[k].name;
    const code = document.createElement('div'); code.className = 'tile-code'; code.textContent = k;
    tile.appendChild(svg); tile.appendChild(name); tile.appendChild(code);
    tile.addEventListener('click', () => selectRegion(k));
    container.appendChild(tile);
  }});
}}

function selectRegion(rk) {{
  selectedRegion = rk;
  document.querySelectorAll('.region-tile').forEach(t => {{
    if (t.dataset.region === rk) t.classList.add('active');
    else t.classList.remove('active');
  }});
  const info = REGIONS[rk], banner = document.getElementById('region-banner');
  banner.style.display = '';
  document.getElementById('region-title').textContent = info.name + ' (' + rk + ')';
  document.getElementById('region-subtitle').textContent = info.desc;
  document.getElementById('modeToggleSection').classList.add('visible');
  activateMode(rk);
  banner.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
}}

function setMode(mode) {{
  currentMode = mode;
  document.getElementById('btnHistoric').classList.toggle('active', mode === 'historic');
  document.getElementById('btnHourly').classList.toggle('active', mode === 'hourly');
  document.getElementById('modeDesc').textContent = mode === 'historic'
    ? 'Explore how the generation mix has changed across 7 years of EIA data.'
    : 'See how the grid dispatches generation hour by hour throughout 2024.';
  if (selectedRegion) activateMode(selectedRegion);
}}

function activateMode(rk) {{
  const hc = document.getElementById('historicContainer');
  const hr = document.getElementById('hourlyContainer');
  const cta = document.getElementById('ctaSection');
  const fa = document.getElementById('footerAttr');

  if (currentMode === 'historic') {{
    hc.classList.add('visible'); hr.classList.remove('visible');
    gsInit(rk);
  }} else {{
    hr.classList.add('visible'); hc.classList.remove('visible');
    hvInit(rk);
  }}
  cta.classList.add('visible');
  fa.classList.add('visible');
}}

// ═══════════════════════════════════════════════════════════════════════════
// HISTORIC MODE (from EIA Grid Story)
// ═══════════════════════════════════════════════════════════════════════════
var GS_DATA;
var gsCurrentStep = 0, gsAnimFrames = {{}};
const RCOL_H = {{CAL:'#2372B9',CAR:'#6BA543',CENT:'#D4820C',FLA:'#F47B27',MIDA:'#0F3460',MIDW:'#007FA4',NE:'#5B8DEF',NW:'#2E7D32',NY:'#7B1FA2',SE:'#C0392B',SW:'#E65100',TEN:'#00838F',TEX:'#FBB254'}};
const SRC = {{coal:{{c:'#5C636A',n:'Coal'}},gas:{{c:'#D4820C',n:'Natural Gas'}},nuclear:{{c:'#2372B9',n:'Nuclear'}},oil:{{c:'#8B5E3C',n:'Oil'}},solar:{{c:'#FBB254',n:'Solar'}},wind:{{c:'#CADB2E',n:'Wind'}},hydro:{{c:'#007FA4',n:'Hydro'}},storage:{{c:'#F47B27',n:'Storage'}},geo:{{c:'#6BA543',n:'Geothermal'}},other:{{c:'#94A3B8',n:'Other'}}}};
const FUELS = ['coal','gas','oil','other','nuclear','hydro','geo','wind','solar','storage'];
const CLEAN = ['nuclear','hydro','geo','wind','solar'], FOSSIL = ['coal','gas','oil'];
const fmt = (v,d=0) => v==null||isNaN(v)?'-':Number(v).toLocaleString('en-US',{{minimumFractionDigits:d,maximumFractionDigits:d}});
const gv = (yr,f) => Math.max(0,yr[f+'_gwh']||0);
const totalGen = yr => FUELS.reduce((s,f)=>s+gv(yr,f),0);
const cleanPct = yr => {{ const t=totalGen(yr); return t>0?CLEAN.reduce((s,f)=>s+gv(yr,f),0)/t*100:0; }};

let gsScrollObserver = null;

function gsSetupCanvas(id) {{
  const c = document.getElementById(id); if (!c) return null;
  const dpr = window.devicePixelRatio || 1;
  const rect = c.parentElement.getBoundingClientRect();
  c.width = rect.width * dpr; c.height = rect.height * dpr;
  c.style.width = rect.width + 'px'; c.style.height = rect.height + 'px';
  const ctx = c.getContext('2d'); ctx.scale(dpr, dpr);
  return {{ ctx, w: rect.width, h: rect.height }};
}}

function gsInit(rk) {{
  Object.values(gsAnimFrames).forEach(id => cancelAnimationFrame(id)); gsAnimFrames = {{}}; gsCurrentStep = 0;
  const rd = GS_DATA.annual[rk], md = GS_DATA.monthly[rk], years = Object.keys(rd).sort();
  const fy = years[0], ly = years[years.length-1], first = rd[fy], last = rd[ly], info = REGIONS[rk];
  const fC = cleanPct(first), lC = cleanPct(last), dC = lC - fC;
  const dD = ((last.demand_avg_mw - first.demand_avg_mw) / first.demand_avg_mw * 100);
  const fCoal = first.coal_gwh||0, lCoal = last.coal_gwh||0, coalChg = fCoal>10?((lCoal-fCoal)/fCoal*100):0;
  const fR = (first.solar_gwh||0)+(first.wind_gwh||0), lR = (last.solar_gwh||0)+(last.wind_gwh||0);
  const rChg = fR>0?((lR-fR)/fR*100):(lR>0?999:0);
  const showCoal = fCoal>10||lCoal>10;
  const narr = document.getElementById('narrativeColumnH');
  let html = '', stepNum = 0;
  window._rk = rk; window._showCoal = showCoal;

  stepNum++;
  html += `<div class="story-step gs-step" data-step="${{stepNum}}"><div class="step-inner">
    <span class="step-badge blue">Overview</span>
    <h2>${{info.name}}'s Grid at a Glance</h2>
    <p>This donut chart shows ${{info.name}}'s full generation mix &mdash; every fuel source as a share of total production. Watch it animate from <span class="hl blue">${{fy}}</span> to <span class="hl blue">${{ly}}</span>.</p>
    <div class="stat-row">
      <div class="stat-box"><div class="sv">${{fmt(last.demand_avg_mw,0)}}</div><div class="sl">MW avg demand ${{ly}}</div></div>
      <div class="stat-box"><div class="sv">${{lC.toFixed(1)}}%</div><div class="sl">Clean share ${{ly}}</div></div>
      <div class="stat-box"><div class="sv">${{dD>=0?'+':''}}${{dD.toFixed(1)}}%</div><div class="sl">Demand change</div></div>
    </div>
    <p>${{dC>3?`Clean energy grew from <span class="hl green">${{fC.toFixed(1)}}%</span> to <span class="hl green">${{lC.toFixed(1)}}%</span> &mdash; a <span class="hl green">${{dC.toFixed(1)}}pp</span> increase.`:dC<-3?`Clean energy declined from ${{fC.toFixed(1)}}% to ${{lC.toFixed(1)}}%.`:`Clean energy held stable near <span class="hl blue">${{lC.toFixed(1)}}%</span>.`}}</p>
    <p style="font-size:0.88rem;color:var(--c-blue);font-weight:600;margin-top:12px;">\u21c6 Drag the year slider above the chart to compare how the generation mix shifted year by year.</p>
  </div></div>`;

  stepNum++;
  html += `<div class="story-step gs-step" data-step="${{stepNum}}"><div class="step-inner">
    <span class="step-badge orange">Demand</span>
    <h2>The Pulse of Demand</h2>
    <p>Each bar represents one year's average hourly demand in megawatts. The <span class="hl orange">orange dots and line</span> connect each year's peak demand &mdash; the highest single hour the grid had to serve.</p>
    <p>${{dD>2?`Demand climbed <span class="hl orange">${{dD.toFixed(1)}}%</span> since ${{fy}}.`:dD<-2?`Demand fell ${{Math.abs(dD).toFixed(1)}}% since ${{fy}}.`:`Demand stayed relatively flat.`}}${{last.peak_demand_mw>0?` Peak in ${{ly}}: <span class="hl orange">${{fmt(last.peak_demand_mw,0)}} MW</span>.`:''}}</p>
  </div></div>`;

  if (showCoal) {{
    stepNum++;
    html += `<div class="story-step gs-step" data-step="${{stepNum}}"><div class="step-inner">
      <span class="step-badge navy">Coal</span>
      <h2>The Fading of Coal</h2>
      <p>Each filled square represents a unit of coal-fired generation. The ghost squares show where coal stood in ${{fy}} &mdash; revealing how much has been retired or displaced.</p>
      <p>${{coalChg<-10?`Coal has <span class="hl red">fallen ${{Math.abs(coalChg).toFixed(0)}}%</span> since ${{fy}}.`:coalChg>10?`Unusually, coal rose ${{coalChg.toFixed(0)}}% here.`:`Coal has held relatively steady.`}}</p>
      <p style="font-size:0.88rem;color:var(--c-blue);font-weight:600;margin-top:12px;">\u21c6 Drag the year slider above the chart to watch coal squares disappear year by year.</p>
    </div></div>`;
  }}

  stepNum++;
  html += `<div class="story-step gs-step" data-step="${{stepNum}}"><div class="step-inner">
    <span class="step-badge green">Renewables</span>
    <h2>Solar &amp; Wind: Rapid Rise</h2>
    <p>Each circle represents one year's generation: <span class="hl gold">golden orbs</span> are solar (with radiating rays) and <span class="hl green">green orbs</span> are wind (with spiral traces). Larger circles mean more GWh produced.</p>
    <p>${{rChg>50?`Combined solar and wind grew ${{rChg>500?'<span class="hl green">dramatically</span>':`<span class="hl green">${{rChg.toFixed(0)}}%</span>`}}.`:rChg>0?`Solar and wind grew modestly.`:`Limited renewable change here.`}}</p>
  </div></div>`;

  stepNum++;
  html += `<div class="story-step gs-step" data-step="${{stepNum}}"><div class="step-inner">
    <span class="step-badge gold">Seasonality</span>
    <h2>The Rhythm of the Seasons</h2>
    <p>This radial chart arranges all 12 months in a circle, like a clock. Each petal shows that month's total generation, with fuel layers stacking outward from the center &mdash; revealing how the mix shifts with the seasons.</p>
    <p>Summer peaks push the petals outward; milder months contract. Notice how the <span class="hl green">green (renewables)</span> layer grows thicker in recent years.</p>
    <p style="font-size:0.88rem;color:var(--c-blue);font-weight:600;margin-top:12px;">\u21c6 Drag the year slider above the chart to see how seasonal patterns have evolved.</p>
  </div></div>`;

  stepNum++;
  html += `<div class="story-step gs-step" data-step="${{stepNum}}"><div class="step-inner">
    <span class="step-badge blue">Then vs Now</span>
    <h2>${{fy}} vs ${{ly}}</h2>
    <p>Two donut rings side by side &mdash; the generation mix at the start and end of the period. The center percentage shows each year's clean energy share. An arrow connects them to highlight the direction of change.</p>
    <div class="stat-row">
      <div class="stat-box"><div class="sv">${{fC.toFixed(1)}}%</div><div class="sl">Clean ${{fy}}</div></div>
      <div class="stat-box"><div class="sv">${{lC.toFixed(1)}}%</div><div class="sl">Clean ${{ly}}</div></div>
      <div class="stat-box"><div class="sv">${{dC>=0?'+':''}}${{dC.toFixed(1)}}</div><div class="sl">pp change</div></div>
    </div>
  </div></div>`;

  narr.innerHTML = html;
  gsSetupScrollObserver();
  setTimeout(() => gsGoToStep(1), 300);
}}

function gsSliderStep(id,dir) {{ const sl=document.getElementById(id); const v=Math.max(+sl.min,Math.min(+sl.max,+sl.value+dir)); sl.value=v; sl.dispatchEvent(new Event('input')); }}

// Auto-sweep: animate the slider from min→max then leave it at max
let _gsSweepTimer = null;
function gsAutoSweep(sliderId, ctrlId, hintText) {{
  if (_gsSweepTimer) clearInterval(_gsSweepTimer);
  const sl = document.getElementById(sliderId);
  const ctrl = document.getElementById(ctrlId);
  if (!sl || !ctrl) return;

  // Remove any previous hint
  const oldHint = ctrl.querySelector('.slider-hint');
  if (oldHint) oldHint.remove();

  // Reset slider to start
  sl.value = sl.min;
  sl.dispatchEvent(new Event('input'));

  // Add sweeping class for glow animation
  ctrl.classList.add('sweeping');

  // Add hint text below the controls
  if (hintText) {{
    const hint = document.createElement('div');
    hint.className = 'slider-hint';
    hint.textContent = hintText;
    ctrl.appendChild(hint);
  }}

  // Step through each value with a delay
  const maxVal = +sl.max;
  let cur = 0;
  const stepDelay = 250; // ms between steps
  _gsSweepTimer = setInterval(() => {{
    cur++;
    if (cur > maxVal) {{
      clearInterval(_gsSweepTimer);
      _gsSweepTimer = null;
      // Remove sweep glow after animation completes
      setTimeout(() => {{
        ctrl.classList.remove('sweeping');
      }}, 600);
      return;
    }}
    sl.value = cur;
    sl.dispatchEvent(new Event('input'));
  }}, stepDelay);
}}

function gsSetupScrollObserver() {{
  if (gsScrollObserver) gsScrollObserver.disconnect();
  const steps = document.querySelectorAll('.gs-step');
  gsScrollObserver = new IntersectionObserver(entries => {{
    entries.forEach(e => {{
      if (e.isIntersecting) {{ e.target.classList.add('active'); gsGoToStep(parseInt(e.target.dataset.step)); }}
    }});
  }}, {{ threshold: 0.4, rootMargin: '-10% 0px -10% 0px' }});
  steps.forEach(s => gsScrollObserver.observe(s));
}}

function gsGoToStep(step) {{
  if (step === gsCurrentStep || !selectedRegion) return; gsCurrentStep = step;
  document.querySelectorAll('#historicContainer .viz-panel').forEach(p => p.classList.remove('active'));
  Object.values(gsAnimFrames).forEach(id => cancelAnimationFrame(id)); gsAnimFrames = {{}};
  // Clear any running sweep
  if (_gsSweepTimer) {{ clearInterval(_gsSweepTimer); _gsSweepTimer = null; }}
  document.querySelectorAll('.viz-controls').forEach(c => c.classList.remove('sweeping'));

  const rd = GS_DATA.annual[selectedRegion], years = Object.keys(rd).sort();
  const hasCoal = (rd[years[0]].coal_gwh||0)>10 || (rd[years[years.length-1]].coal_gwh||0)>10;
  const baseMap = [2,3,4,5,6,7];
  let vizNum;
  if (hasCoal) {{ vizNum = baseMap[step-1]||7; }}
  else {{ const noCoalMap = [2,3,5,6,7]; vizNum = noCoalMap[step-1]||7; }}
  const panel = document.getElementById('vizPanel'+vizNum);
  if (panel) panel.classList.add('active');
  const rk = selectedRegion;
  switch(vizNum) {{ case 2:gsViz2(rk);break; case 3:gsViz3(rk);break; case 4:gsViz4(rk);break; case 5:gsViz5(rk);break; case 6:gsViz6(rk);break; case 7:gsViz7(rk);break; }}

  // Trigger auto-sweep on slider panels after a brief delay for the viz to render
  setTimeout(() => {{
    if (vizNum === 2) gsAutoSweep('s2', 'ctrl2', '\u2190 Drag to compare years');
    else if (vizNum === 4) gsAutoSweep('s4', 'ctrl4', '\u2190 Drag to compare years');
    else if (vizNum === 6) gsAutoSweep('s6', 'ctrl6', '\u2190 Drag to compare years');
  }}, 400);
}}
'''

# ── Append the historic viz functions (viz2-viz7, renamed to gsViz2-gsViz7) ──
html += "\n// Historic visualization functions\n"
html += gs_viz_code

# ── Append the hourly mode code inside an IIFE ──────────────────────────────
# The IIFE completely isolates the hourly code scope.
# It receives RDATA and REGIONS from the outer scope.
# Internally, REGIONS properties are accessed as .n and .d (the original format),
# so we create a mapped version inside the IIFE.
html += """
// ═══════════════════════════════════════════════════════════════════════════
// HOURLY MODE (from 3D Grid Viz) — wrapped in IIFE to isolate scope
// ═══════════════════════════════════════════════════════════════════════════
var hvInit; // exposed to global scope
(function() {
  // Map shared REGIONS (.name/.desc) to the format hourly code expects (.n/.d)
  const REGIONS = {};
  Object.entries(window.REGIONS || {}).forEach(([k, v]) => {
    REGIONS[k] = { n: v.name, d: v.desc };
  });

  // Hourly mode's own state (isolated from historic mode)
  let selReg = null, curStep = 0, animFrames = {};

"""

html += gv_viz_code

# Now add the buildStory, setupObs, goToStep functions that reference
# the hourly-specific DOM elements
html += """
  function buildStory(k) {
    const D = RDATA[k], S = D.stats;
    document.getElementById('statTWh').textContent = S.totalTWh;
    document.getElementById('statHours').textContent = S.nHours.toLocaleString();
    document.getElementById('statAvgGW').textContent = Math.round(S.avgGen / 1000);
    document.getElementById('statCF').textContent = Math.round(S.avgCF / 1000);
    document.getElementById('statMinRate').textContent = S.rateP5 + ' kg';
    document.getElementById('statMaxRate').textContent = S.rateP95 + ' kg';
    document.getElementById('statAvgFossil').textContent = S.avgFossil + '%';
    document.getElementById('statHighHours').textContent = S.highFossilHours.toLocaleString();

    Object.values(animFrames).forEach(id => cancelAnimationFrame(id));
    animFrames = {};

    drawAct1(k); drawAct2(k); drawAct3(k); drawAct4(k); drawAct5(k); drawAct6(k); buildSankey(k);

    curStep = 0;
    document.querySelectorAll('.hv-step').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('#hourlyContainer .viz-panel').forEach(p => p.classList.remove('active'));
    setupObs();
  }

  function setupObs() {
    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('active');
          goToStep(parseInt(e.target.dataset.step));
        }
      });
    }, {threshold: 0.4, rootMargin: '-10% 0px -10% 0px'});
    document.querySelectorAll('.hv-step').forEach(s => obs.observe(s));
  }

  function goToStep(step) {
    if (step === curStep) return;
    curStep = step;
    document.querySelectorAll('#hourlyContainer .viz-panel').forEach(p => p.classList.remove('active'));
    const panel = document.getElementById('hvPanel' + step);
    if (panel) panel.classList.add('active');
  }

  // Expose hvInit to global scope
  hvInit = function(rk) {
    if (!RDATA[rk]) return;
    selReg = rk;
    buildStory(rk);
  };
})();

"""

# Add scroll progress and DOMContentLoaded
html += """
// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════
window.addEventListener('scroll', () => {
  const h = document.documentElement.scrollHeight - window.innerHeight;
  document.getElementById('progressBar').style.width = (h>0?(window.scrollY/h)*100:0)+'%';
}, {passive:true});

document.addEventListener('DOMContentLoaded', () => {
  GS_DATA = INLINE_DATA;
  buildMap();
});
</script>
</body>
</html>
"""

# Write the combined file
out_path = os.path.join(BASE, "index.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)

file_size_kb = os.path.getsize(out_path) / 1024
print(f"\nBuilt: {out_path}")
print(f"Size: {file_size_kb:.0f} KB")
print("Done!")
