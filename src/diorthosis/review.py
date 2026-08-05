"""The review loop: every apparatus entry face to face with the printed
band it came from, corrections exported as a replayable overrides file.

``diorthosis review edition.pdf -o review/`` writes a self-contained
``review/index.html``: for each entry, the IMAGE SNIPPET of the
apparatus band lines it was split from (cropped from the PDF itself —
per-entry provenance a reviewer can check at a glance), the structured
parse the TEI will carry, its status (parsed / refused / unanchored /
reviewed), and an editable override form. Filters put refusals and
unanchored entries first — the work queue. The "download overrides"
button assembles ``overrides.json``; ``diorthosis build --overrides``
replays it on every rebuild, marking each correction
``resp="#human-review"`` in the TEI.

Each exported record carries the CONTENT BINDING of the entry it was made
against (``source_sha``, shown next to the key). The binding is injected at
download time from the page's own data, never from the editable textarea, so
a reviewer cannot detach a correction from its entry by editing JSON — and a
later build whose band splitting drifted refuses to replay it instead of
re-targeting a scholar's authority onto a different entry.

Rendering needs the optional review extra: ``pip install
diorthosis[review]`` (pypdfium2 — BSD/Apache — and Pillow).
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from .model import Document
from .overrides import FORMAT, entry_keys, source_digest, source_excerpt
from .tei import resolve_parsed


def _norm(s: str) -> str:
  return " ".join(s.split())


def entry_line_span(line_texts: list[str], raw: str) -> tuple[int, int] | None:
  """Which consecutive band lines carry this entry? Entries were split
  from the flattened band text, so the raw (normalized) occurs in the
  running concatenation of the lines; map its char span back to line
  indices. Falls back to a first-words search when hyphenation or
  marginalia break the exact match; None means 'show the whole band'."""
  flat_parts: list[str] = []
  starts: list[int] = []
  pos = 0
  for t in line_texts:
    starts.append(pos)
    nt = _norm(t)
    flat_parts.append(nt)
    pos += len(nt) + 1
  flat = " ".join(flat_parts)

  needle = _norm(raw)
  i = flat.find(needle)
  if i < 0:
    lead = " ".join(needle.split()[:5])
    if len(lead) >= 8:
      i = flat.find(lead)
    if i < 0:
      return None
    needle = lead
  end = i + len(needle)
  first = last = None
  for li, s in enumerate(starts):
    e = s + len(flat_parts[li])
    if first is None and e > i:
      first = li
    if s < end:
      last = li
  if first is None or last is None:
    return None
  return first, last


def _foot_geometry(pdf_path: str, page_indices: list[int]):
  """page index -> (page_width, page_height, [line boxes+texts]) for the
  foot bands, straight from the layerer (the adapter drops geometry)."""
  from regreek.layers import layer_pages

  geo = {}
  for lp in layer_pages(pdf_path, pages=page_indices):
    lines = []
    for band in lp.bands:
      if band.layer in ("notes", "apparatus"):
        for ln in band.lines:
          lines.append(((ln.x0, ln.y0, ln.x1, ln.y1),
                        (ln.decoded or ln.text)))
    geo[lp.page] = (lp.width, lp.height, lines)
  return geo


def _snippet(pdfium_page, page_h: float, boxes: list, out_png: Path,
             scale: float = 2.2, pad: float = 4.0) -> bool:
  if not boxes:
    return False
  x0 = min(b[0] for b in boxes) - pad
  y0 = min(b[1] for b in boxes) - pad
  x1 = max(b[2] for b in boxes) + pad
  y1 = max(b[3] for b in boxes) + pad
  bitmap = pdfium_page.render(scale=scale)
  img = bitmap.to_pil()
  # PDF y grows upward; the bitmap's grows downward
  left, top = max(0, int(x0 * scale)), max(0, int((page_h - y1) * scale))
  right, bottom = int(x1 * scale), int((page_h - y0) * scale)
  img.crop((left, top, min(right, img.width),
            min(bottom, img.height))).save(out_png)
  return True


def _attr_str(a) -> str:
  parts = []
  if a.witnesses:
    parts.append("wits: " + " ".join(a.witnesses))
  if a.editors:
    parts.append("eds: " + " ".join(a.editors))
  if a.qualifiers:
    parts.append("quals: " + " ".join(a.qualifiers))
  return " · ".join(parts)


def bind_record(body: dict, entry) -> dict:
  """Attach the content binding to a correction body.

  The Python twin of what the download button does in the browser: the
  reviewer owns the correction, the build owns the binding. Exposed so a
  scripted export (an inter-annotator study, a batch of adjudications)
  produces records that replay under the same guarantee as the UI's.
  """
  return {**body, "source_sha": source_digest(entry),
          "source_excerpt": source_excerpt(entry)}


def export_file(records: dict[str, dict]) -> dict:
  """The versioned container the download button writes: bound records
  under an explicit format marker, so a reader never has to guess."""
  return {"format": FORMAT, "entries": records}


def _override_json(parsed) -> dict:
  """The editable half of a record — what the reviewer may change. The
  binding is added by ``bind_record``, never typed into the textarea."""
  if parsed is None:
    return {"action": "verbatim", "note": ""}
  return {
    "action": "parse",
    "lemma": parsed.lemma,
    "lemma_wits": parsed.lemma_attribution.witnesses,
    "lemma_editors": parsed.lemma_attribution.editors,
    "lemma_qualifiers": parsed.lemma_attribution.qualifiers,
    "readings": [
      {"text": r.text, "wits": r.attribution.witnesses,
       "editors": r.attribution.editors,
       "qualifiers": r.attribution.qualifiers}
      for r in parsed.readings
    ],
    "comments": parsed.comments,
    "note": "",
  }


_CSS = """
body{font:14px/1.5 -apple-system,'Segoe UI',sans-serif;margin:0;
  background:#f6f5f2;color:#1c1b19}
header{position:sticky;top:0;background:#fffdf9;border-bottom:1px solid #d8d4cc;
  padding:10px 18px;display:flex;gap:14px;align-items:center;z-index:5}
header h1{font-size:16px;margin:0 12px 0 0}
button,select{font:inherit;padding:4px 10px;border:1px solid #b7b1a5;
  border-radius:4px;background:#fff;cursor:pointer}
button.primary{background:#2d5b3e;color:#fff;border-color:#2d5b3e}
.entry{background:#fff;border:1px solid #ddd8cf;border-radius:6px;
  margin:14px 18px;padding:12px 14px;display:grid;
  grid-template-columns:minmax(280px,1fr) minmax(280px,1fr);gap:12px}
.entry img{max-width:100%;border:1px solid #e6e1d8;background:#fff}
.entry.hidden{display:none}
.meta{grid-column:1/-1;display:flex;gap:10px;align-items:baseline}
.key{font-family:ui-monospace,monospace;color:#6d675d}
.sha{font-family:ui-monospace,monospace;font-size:11px;color:#8c8578}
.chip{font-size:11px;padding:1px 8px;border-radius:9px;color:#fff}
.chip.parsed{background:#2d5b3e}.chip.refused{background:#a8620a}
.chip.unanchored{background:#9a2c2c}.chip.reviewed{background:#2b4d7c}
.parse{font-size:13px}
.parse .lem{font-weight:600}
.parse .rdg{margin-left:14px}
.parse .att{color:#6d675d;font-size:12px}
.raw{grid-column:1/-1;font-family:ui-monospace,monospace;font-size:12px;
  color:#4d483f;background:#faf8f4;padding:6px 8px;border-radius:4px;
  overflow-wrap:anywhere}
details{grid-column:1/-1}
textarea{width:100%;min-height:130px;font:12px ui-monospace,monospace;
  border:1px solid #cfc9be;border-radius:4px;box-sizing:border-box}
.inc{margin-right:6px}
"""

_JS = """
function applyFilter(){
  const f=document.getElementById('filter').value;
  document.querySelectorAll('.entry').forEach(e=>{
    e.classList.toggle('hidden', f!=='all' && e.dataset.status!==f);});
  count();}
function count(){
  const v=document.querySelectorAll('.entry:not(.hidden)').length;
  document.getElementById('count').textContent=v+' shown';}
function markDirty(cb){
  cb.closest('details').open=true;}
function download(){
  const entries={};
  document.querySelectorAll('.entry').forEach(e=>{
    const cb=e.querySelector('.inc');
    if(!cb||!cb.checked)return;
    let rec;
    try{rec=JSON.parse(e.querySelector('textarea').value);}
    catch(err){alert('Invalid JSON in '+e.dataset.key+': '+err);throw err;}
    // the binding comes from the build, never from the editable textarea:
    // a correction must not be detachable from the entry it was made against
    rec.source_sha=e.dataset.sha;
    rec.source_excerpt=e.dataset.src;
    entries[e.dataset.key]=rec;});
  const doc={format:document.body.dataset.format,entries:entries};
  const blob=new Blob([JSON.stringify(doc,null,1)],{type:'application/json'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);a.download='overrides.json';a.click();}
window.addEventListener('DOMContentLoaded',()=>{applyFilter();});
"""


def render_review(doc: Document, pdf_path: str, outdir: Path,
                  registry) -> dict:
  """Write review/index.html + review/snippets/*.png. Returns counters."""
  import pypdfium2 as pdfium

  outdir.mkdir(parents=True, exist_ok=True)
  snip_dir = outdir / "snippets"
  snip_dir.mkdir(exist_ok=True)

  page_indices = [p.index for p in doc.pages]
  geo = _foot_geometry(pdf_path, page_indices)
  pdf = pdfium.PdfDocument(pdf_path)

  stats = {"entries": 0, "parsed": 0, "refused": 0, "unanchored": 0,
           "reviewed": 0, "snippets": 0}
  rows: list[str] = []
  for page in doc.pages:
    pw, ph, lines = geo.get(page.index, (0.0, 0.0, []))
    line_texts = [t for _, t in lines]
    pdfium_page = pdf[page.index] if ph else None
    for key, e in entry_keys(page):
      stats["entries"] += 1
      parsed = resolve_parsed(e, registry)
      anchored = (e.anchor is not None and e.anchor.block_index is not None
                  and e.anchor.char_offset is not None)
      if e.override_action:
        status = "reviewed"
      elif e.refusal_evidence:
        status = "refused"
      elif not anchored:
        status = "unanchored"
      elif parsed is None:
        status = "refused"
      else:
        status = "parsed"
      stats[status if status != "parsed" else "parsed"] += 1

      png_rel = ""
      span = entry_line_span(line_texts, e.raw) if line_texts else None
      boxes = ([b for b, _ in (lines[span[0]:span[1] + 1])] if span
               else [b for b, _ in lines])
      if pdfium_page is not None and boxes:
        png = snip_dir / f"{key}.png"
        if _snippet(pdfium_page, ph, boxes, png):
          png_rel = f"snippets/{key}.png"
          stats["snippets"] += 1

      if parsed is not None:
        lem_att = _attr_str(parsed.lemma_attribution)
        p_rows = [f"<div class='lem'>{html.escape(parsed.lemma)}"
                  + (f" <span class='att'>[{html.escape(lem_att)}]</span>"
                     if lem_att else "") + "</div>"]
        for r in parsed.readings:
          att = _attr_str(r.attribution)
          p_rows.append(
            f"<div class='rdg'>{html.escape(r.text) or '<em>om.</em>'}"
            + (f" <span class='att'>[{html.escape(att)}]</span>"
               if att else "") + "</div>")
        for c in parsed.comments:
          p_rows.append(f"<div class='rdg att'>note: {html.escape(c)}</div>")
        parse_html = "".join(p_rows)
      else:
        reason = (
          f"<div class='rdg att'>{html.escape(e.refusal_evidence)}</div>"
          if e.refusal_evidence else ""
        )
        parse_html = (
          "<em>refused — kept as a verbatim note</em>" + reason
        )

      body = _override_json(parsed)
      record = bind_record(body, e)
      ov = json.dumps(body, ensure_ascii=False, indent=1)
      folio = html.escape(page.printed_page or "?")
      sha = record["source_sha"]
      rows.append(f"""
<div class="entry" data-key="{key}" data-status="{status}"
     data-sha="{sha}" data-src="{html.escape(record['source_excerpt'])}">
 <div class="meta"><span class="key">{key}</span>
  <span class="sha">{sha}</span>
  <span>folio {folio}</span>
  <span class="chip {status}">{status}</span></div>
 <div>{f'<img loading="lazy" src="{png_rel}">' if png_rel
       else '<em>no snippet (geometry unavailable)</em>'}</div>
 <div class="parse">{parse_html}</div>
 <div class="raw">{html.escape(e.raw)}</div>
 <details><summary>override</summary>
  <label><input type="checkbox" class="inc" onchange="markDirty(this)">
   include in overrides.json</label>
  <textarea spellcheck="false">{html.escape(ov)}</textarea>
 </details>
</div>""")

  title = html.escape(Path(doc.source_name).name)
  page_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>diorthosis review — {title}</title>
<style>{_CSS}</style><script>{_JS}</script></head>
<body data-format="{FORMAT}">
<header><h1>diorthosis review — {title}</h1>
 <select id="filter" onchange="applyFilter()">
  <option value="all">all entries</option>
  <option value="refused">refused (work queue)</option>
  <option value="unanchored">unanchored (work queue)</option>
  <option value="parsed">parsed</option>
  <option value="reviewed">reviewed</option>
 </select>
 <span id="count"></span>
 <button class="primary" onclick="download()">download overrides.json</button>
</header>
{''.join(rows)}
</body></html>"""
  (outdir / "index.html").write_text(page_html, encoding="utf-8")
  return stats
