#!/usr/bin/env python3
"""
render_plan.py — deterministic renderer for a w-bonkers plan.

state.json (the single source of truth)  ->  _artifact-source.html (body-only, optional hosted artifact),
                                             board.html (standalone, opens offline),
                                             tasks.md, tasks.ics, todoist_tasks.json

Design goal: SAME state.json => byte-identical output every run (no LLM drift).
Only the data (state.json) changes between runs; this view generator never does.
All personalization (owner, plan label, tag, Todoist project, command name, currency)
is read from state.json -> meta at runtime. This script contains no personal data.

Run from the plan folder:
      python3 scripts/render_plan.py            (validates, then writes all files)
      python3 scripts/render_plan.py --check    (validate only, write nothing)
      python3 scripts/render_plan.py --force    (write even if validation has hard errors)
"""
import json, os, sys, shutil, re

def find_state():
    """state.json lives at the plan-folder root: prefer CWD, else the script's parent dir."""
    for cand in (os.path.abspath("state.json"),
                 os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state.json")):
        if os.path.isfile(cand):
            return cand
    sys.exit("ERROR: state.json not found (run from the plan folder, or keep scripts/ inside it).")

STATE = find_state()
ROOT = os.path.dirname(STATE)
CUR = "₹"  # set from meta.currency in main()

# ---------- helpers ----------
def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def money(n):
    try:
        return CUR + format(int(round(float(n))), ",")
    except Exception:
        return CUR + str(n)

def parse_range(s):
    """'326-338' -> (326.0, 338.0); single '950' -> (950,950); non-numeric -> None."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return (float(s), float(s))
    m = re.findall(r"\d+(?:\.\d+)?", str(s))  # positive prices; '-' is a range separator, not a sign
    if not m:
        return None
    return (float(m[0]), float(m[-1]))

def bucket_label(key, meta):
    return meta.get("bucket_labels", {}).get(key, key.replace("_", " ").title())

# ---------- validation ----------
def validate(state):
    errors, warnings = [], []
    corpus = state["meta"]["corpus_inr"]
    buckets = state["buckets_inr"]
    bsum = sum(buckets.values())
    if bsum != corpus:
        errors.append(f"buckets sum {bsum} != corpus {corpus}")
    stock_amt = sum(p.get("amount_inr", 0) for p in state["positions"])
    if "stocks" in buckets and abs(stock_amt - buckets.get("stocks", 0)) > 1:
        warnings.append(f"position amounts {stock_amt} != stocks bucket {buckets.get('stocks')}")
    for p in state["positions"]:
        e, s, t = parse_range(p.get("entry")), p.get("stop"), parse_range(p.get("target"))
        if e and isinstance(s, (int, float)) and t:
            if not (s < e[0]):
                warnings.append(f"{p['ticker']}: stop {s} not below entry-low {e[0]}")
            if not (e[1] <= t[1]):
                warnings.append(f"{p['ticker']}: entry-high {e[1]} not below target-high {t[1]}")
    return errors, warnings

# ---------- task assembly (deterministic order) ----------
def tasks(state):
    """Ordered list of action items: fund + dated positions (by date) + trigger positions + event/ipo."""
    items = []
    f = state.get("fund")
    if f:
        items.append({"id": "FUND", "title": f"BUY {f['name']}", "amount": f.get("amount_inr"),
                      "due": f.get("due"), "trigger": None, "spec": [],
                      "note": f.get("note", "no intraday-timing risk; start the diversified sleeve")})
    dated = sorted([p for p in state["positions"] if p.get("due")], key=lambda p: (p["due"], p["ticker"]))
    trig = sorted([p for p in state["positions"] if not p.get("due")], key=lambda p: p["ticker"])
    for p in dated + trig:
        spec = [f"Buy zone {p['entry']}", f"Stop-loss {p['stop']}", f"Sell/target {p['target']}",
                f"{p['shares']} sh ≈ {money(p['amount_inr'])}"]
        items.append({"id": p["ticker"], "title": f"{p['action']} {p['ticker']} ({p['theme']}) — {p['shares']} sh",
                      "amount": p["amount_inr"], "due": p.get("due"), "trigger": p.get("trigger"),
                      "spec": spec, "note": p.get("note", "")})
    ipo = state.get("ipo")
    if ipo:
        items.append({"id": "EVENT", "title": f"Apply {ipo['name']} — 1 lot", "amount": ipo.get("topup_to_inr"),
                      "due": None, "trigger": ipo.get("trigger"),
                      "spec": [f"earmark {money(ipo['earmark_inr'])} → top to {money(ipo['topup_to_inr'])}", ipo.get("window", "")],
                      "note": ipo.get("note", "")})
    return items

# ---------- CSS / JS (static; never varies) ----------
CSS = """
:root{--paper:#F4F6F9;--surface:#fff;--ink:#14202E;--muted:#5A6B7B;--accent:#1B3A6B;--accent2:#3E6299;--gold:#A9791C;--goldS:#EFE2C4;--gain:#1B9E5A;--warn:#C68314;--risk:#CC4033;--line:#E2E8F0;--line2:#CBD5E1;--paper2:#ECF0F5;--mono:"SF Mono","Cascadia Mono","Roboto Mono",Menlo,Consolas,monospace;--serif:"Iowan Old Style","Palatino Linotype",Charter,Georgia,serif;--sans:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);line-height:1.55;font-size:16px;-webkit-font-smoothing:antialiased}
.shell{max-width:920px;margin:0 auto;padding:0 clamp(16px,4vw,28px)}
.masthead{background:linear-gradient(160deg,#142C52,#12294D);color:#Eaf0f8;padding:clamp(24px,5vw,40px) 0 clamp(20px,4vw,30px);border-bottom:3px solid var(--gold)}
.eyebrow{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--goldS);margin:0 0 .5rem;font-weight:600}
.masthead h1{font-family:var(--serif);font-weight:600;font-size:clamp(1.7rem,4.4vw,2.5rem);line-height:1.08;margin:0 0 .4rem}
.masthead .sub{margin:0 0 1rem;color:#B7C6DC;font-size:.95rem}
.chips{display:flex;flex-wrap:wrap;gap:.5rem}.chip{font-size:.74rem;padding:.3rem .65rem;border-radius:999px;border:1px solid rgba(255,255,255,.28);color:#D7E2F1;background:rgba(255,255,255,.06)}.chip.gold{border-color:var(--gold);color:#F3E6C7}
main{padding:clamp(18px,3vw,26px) 0 8px;display:flex;flex-direction:column;gap:16px}
.updbar{background:#FCF5E8;border:1px solid #EAD7AE;border-left:4px solid var(--warn);border-radius:10px;padding:.7rem 1rem;font-size:.88rem}
.toolbar{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:.7rem 1rem}
#prog{font-weight:700;font-variant-numeric:tabular-nums}#due-note{font-size:.8rem;color:var(--muted);flex:1 1 100%}
.btn{font:inherit;font-size:.82rem;font-weight:600;padding:.42rem .85rem;border-radius:8px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer}.btn.ghost{background:transparent;color:var(--accent)}.spacer{margin-left:auto}
#export-panel{display:none;margin-top:.7rem;flex:1 1 100%}#export-ta{width:100%;min-height:150px;font-family:var(--mono);font-size:.76rem;border:1px solid var(--line2);border-radius:8px;padding:.6rem}#export-hint{font-size:.8rem;color:var(--muted);margin:.3rem 0 0}#export-label{font-weight:700;font-size:.86rem}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}
.metric{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:12px;padding:16px 18px;display:flex;flex-direction:column;gap:.25rem}
.metric.good{border-left-color:var(--gain)}.metric.warn{border-left-color:var(--warn)}
.metric .k{font-size:.72rem;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);font-weight:600}.metric .v{font-size:1.4rem;font-weight:700;font-variant-numeric:tabular-nums}.metric .note{font-size:.83rem;color:var(--muted)}
.grp{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:clamp(16px,2.4vw,22px)}.grp.now{border:2px solid var(--accent)}
.grp>h2{display:flex;align-items:center;gap:.6rem;margin:0 0 .3rem;font-size:1.15rem;font-weight:700}.grp>.gsub{color:var(--muted);font-size:.85rem;margin:0 0 .7rem}
.tag{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;padding:.16rem .5rem;border-radius:999px;background:var(--accent);color:#fff}.tag.trig{background:var(--gold)}
.task{display:flex;gap:.7rem;align-items:flex-start;padding:.75rem .85rem;border:1px solid var(--line);border-radius:10px;background:var(--surface);margin:.5rem 0;cursor:pointer}
.task:hover{background:#FAFBFD}.task input{margin-top:.15rem;width:19px;height:19px;flex:0 0 auto;accent-color:var(--accent);cursor:pointer}.task-body{flex:1 1 auto;min-width:0}
.task-title{font-weight:700;font-size:.97rem}.task.done{opacity:.5;background:var(--paper2)}.task.done .task-title{text-decoration:line-through}
.task-spec{display:flex;flex-wrap:wrap;gap:.35rem;margin:.4rem 0 .1rem}.task-spec span{font-family:var(--mono);font-size:.75rem;background:var(--paper2);border:1px solid var(--line);border-radius:6px;padding:.12rem .45rem}
.task-spec .when{font-family:var(--sans);font-weight:700;background:#EAF0FA;border-color:#CFDDF0;color:var(--accent)}.task-spec .stop{color:var(--risk);border-color:#F0C9C5}.task-spec .tgt{color:var(--gain);border-color:#A6DCC0}.task-spec .amt{color:var(--gold);border-color:var(--goldS)}
.task-why{font-size:.82rem;color:var(--muted);margin-top:.3rem}
.badge{flex:0 0 auto;font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;padding:.2rem .5rem;border-radius:999px;border:1px solid var(--line2);color:var(--muted);white-space:nowrap}
.badge.today{color:#fff;background:var(--accent);border-color:var(--accent)}.badge.over{color:var(--risk);border-color:#F0C9C5;background:#FBEDEC}.badge.trig{color:var(--gold);border-color:var(--goldS);background:#FBF5E6}.badge.done{color:var(--gain);border-color:#A6DCC0;background:#EAF7F0}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:10px;margin:.3rem 0}table{border-collapse:collapse;width:100%;font-size:.86rem;min-width:560px}th,td{padding:.55rem .7rem;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}thead th{background:var(--paper2);font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700;white-space:nowrap}tbody tr:last-child td{border-bottom:none}
.ticker{font-family:var(--mono);font-weight:600}.price{font-family:var(--mono);white-space:nowrap}.neg{color:var(--risk)}.pos{color:var(--gain)}
.alloc{display:flex;height:32px;border-radius:8px;overflow:hidden;border:1px solid var(--line2);margin:.3rem 0 .8rem}.seg{height:100%}.legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px;font-size:.85rem}.leg{display:flex;gap:.5rem;align-items:center}.sw{width:13px;height:13px;border-radius:4px;flex:0 0 auto}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}ul.tight{margin:.3rem 0;padding-left:1.1rem}ul.tight li{margin:.25rem 0;font-size:.9rem}.muted{color:var(--muted)}h3{font-size:1rem;color:#12294D;margin:0 0 .5rem}
footer{border-top:1px solid var(--line);margin-top:8px;padding:20px 0 40px;color:var(--muted);font-size:.8rem}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

JS = r"""
(function(){
  var TAG='__TAG__';
  var tasks=[].slice.call(document.querySelectorAll('.task'));
  var today=new Date();today.setHours(0,0,0,0);var DAY=86400000;
  function pd(s){var p=s.split('-');return new Date(+p[0],+p[1]-1,+p[2]);}
  function badge(t,on){var b=t.querySelector('.badge');if(!b)return;if(on){b.textContent='✓ done';b.className='badge done';return;}
    var ds=t.getAttribute('data-date'),tr=t.getAttribute('data-trigger');
    if(ds){var d=Math.round((pd(ds)-today)/DAY);if(d<0){b.textContent='overdue';b.className='badge over';}else if(d===0){b.textContent='DUE TODAY';b.className='badge today';}else if(d===1){b.textContent='tomorrow';b.className='badge';}else{b.textContent='in '+d+'d';b.className='badge';}}
    else if(tr){b.textContent='trigger';b.className='badge trig';}}
  function refresh(){var done=0,due=0,over=0;tasks.forEach(function(t){var cb=t.querySelector('input');t.classList.toggle('done',cb.checked);badge(t,cb.checked);if(cb.checked){done++;return;}var ds=t.getAttribute('data-date');if(ds){var d=Math.round((pd(ds)-today)/DAY);if(d===0)due++;else if(d<0)over++;}});
    var p=document.getElementById('prog');if(p)p.textContent=done+' / '+tasks.length+' done';var n=document.getElementById('due-note');if(n)n.textContent='Detected today: '+today.toDateString()+'  ·  '+due+' due today, '+over+' overdue';}
  tasks.forEach(function(t){var id=t.getAttribute('data-task'),cb=t.querySelector('input');try{if(localStorage.getItem(TAG+'-'+id)==='1')cb.checked=true;}catch(e){}cb.addEventListener('change',function(){try{localStorage.setItem(TAG+'-'+id,cb.checked?'1':'0');}catch(e){}refresh();});});
  refresh();
  function spec(t){var s=t.querySelector('.task-spec');return s?s.textContent.replace(/\s+/g,' ').trim():'';}
  function md(){var o=['# __PLAN__ — Action Checklist','','Detected today: '+today.toDateString(),''];document.querySelectorAll('.tgroup').forEach(function(g){o.push('## '+g.getAttribute('data-group'));g.querySelectorAll('.task').forEach(function(t){var cb=t.querySelector('input'),ti=t.querySelector('.task-title').textContent.trim();var w=t.getAttribute('data-date')||('when '+(t.getAttribute('data-trigger')||''));o.push('- ['+(cb.checked?'x':' ')+'] ('+w+') '+ti+' — '+spec(t));});o.push('');});return o.join('\n');}
  function reveal(txt,lbl){var p=document.getElementById('export-panel');document.getElementById('export-label').textContent=lbl;var ta=document.getElementById('export-ta');ta.value=txt;p.style.display='block';ta.focus();ta.select();var h=document.getElementById('export-hint');try{navigator.clipboard.writeText(txt).then(function(){h.textContent='✓ Copied.';},function(){h.textContent='Select above & copy.';});}catch(e){h.textContent='Select above & copy.';}}
  var c=document.getElementById('copy-btn');if(c)c.addEventListener('click',function(){reveal(md(),'Checklist (paste into your task app):');});
})();
"""

# ---------- HTML ----------
def task_card(it):
    did = ('data-date="%s"' % it["due"]) if it["due"] else ('data-trigger="%s"' % esc(it["trigger"] or ""))
    chips = []
    if it["due"]:
        chips.append('<span class="when">\U0001F4C5 %s</span>' % it["due"])
    elif it["trigger"]:
        chips.append('<span class="when">⚡ %s</span>' % esc(it["trigger"]))
    for s in it["spec"]:
        cls = "stop" if "Stop" in s else "tgt" if ("Sell" in s or "target" in s.lower()) else "amt" if ("≈" in s or "earmark" in s) else ""
        chips.append('<span class="%s">%s</span>' % (cls, esc(s)))
    return ('<label class="task" data-task="%s" %s><input type="checkbox"><div class="task-body">'
            '<div class="task-title">%s</div><div class="task-spec">%s</div>'
            '<div class="task-why">%s</div></div><span class="badge"></span></label>') % (
        esc(it["id"]), did, esc(it["title"]), "".join(chips), esc(it["note"]))

# palette cycled across however many buckets the user defined
BUCKET_COLORS = ["var(--accent)", "var(--accent2)", "var(--gold)", "#9AA9B8", "#1B9E5A", "#CC4033", "#7C6BAF", "#3E8E9E"]

def render_body(state):
    m = state["meta"]; b = state["buckets_inr"]; reg = state.get("regime", {}); tax = state.get("tax"); nr = m.get("next_review", {})
    plan_label = m.get("plan_label", "Action Board")
    owner = m.get("owner", "")
    its = tasks(state)
    dated = [i for i in its if i["due"]]; trig = [i for i in its if not i["due"]]
    # allocation bar — iterate whatever buckets exist, stable order = insertion order of state.json
    tot = sum(b.values()); segs = []; legs = []
    for idx, (k, v) in enumerate(b.items()):
        col = BUCKET_COLORS[idx % len(BUCKET_COLORS)]
        pct = round(v * 100.0 / tot, 1) if tot else 0
        lbl = bucket_label(k, m)
        segs.append('<div class="seg" style="width:%s%%;background:%s"></div>' % (pct, col))
        legs.append('<div class="leg"><span class="sw" style="background:%s"></span><div><b>%s</b> &mdash; %s (%s%%)</div></div>' % (col, esc(lbl), money(v), pct))
    # levels table
    rows = ""
    for p in state["positions"]:
        rows += ('<tr><td><span class="ticker">%s</span></td><td>%s</td><td class="price">%s</td>'
                 '<td class="price neg">%s</td><td class="price pos">%s</td><td class="price">%s</td></tr>') % (
            esc(p["ticker"]), esc(p["theme"]), esc(p["entry"]), esc(p["stop"]), esc(p["target"]), money(p["amount_inr"]))
    keep = "".join("<li>%s</li>" % esc(x) for x in state.get("keep_not_rotated", []))
    watch = " · ".join(esc(x) for x in state.get("watchlist", []))
    # tax metric card + tax reference block render only when a tax block exists
    if tax:
        tax_metric = ('<div class="metric warn"><span class="k">Tax</span><span class="v">%s</span>'
                      '<span class="note">%s left · NPS 80CCD(2) saves %s/yr</span></div>') % (
            money(tax.get("net_tax_inr", 0)), money(tax.get("remaining_inr", 0)), money(tax.get("nps_saving_inr", 0)))
        tax_section = ('<h3>Tax &amp; NPS</h3><ul class="tight"><li>Net tax %s; %s remaining.</li><li>%s</li>'
                       '<li>Employer NPS 80CCD(2): deduct %s → save %s/yr.</li></ul>') % (
            money(tax.get("net_tax_inr", 0)), money(tax.get("remaining_inr", 0)), esc(tax.get("note", "")),
            money(tax.get("nps_deduction_inr", 0)), money(tax.get("nps_saving_inr", 0)))
    else:
        tax_metric = ('<div class="metric"><span class="k">Positions</span><span class="v">%d</span>'
                      '<span class="note">%d dated · %d trigger</span></div>') % (len(state["positions"]), len(dated), len(trig))
        tax_section = ""
    dated_html = "".join(task_card(i) for i in dated)
    trig_html = "".join(task_card(i) for i in trig)
    js = JS.replace("__TAG__", m.get("tag", "W").lower()).replace("__PLAN__", plan_label.replace("'", ""))
    return TEMPLATE.format(
        plan_label=esc(plan_label), owner=esc(owner),
        rev=m["rev"], refreshed=esc(m["last_refreshed"]), asof=esc(m["prices_asof"]), mode=esc(m.get("run_mode", "full")),
        goal=esc(m["goal"]), corpus=money(m["corpus_inr"]),
        guard=" · ".join(esc(g) for g in m["guardrails"]),
        regime_v=esc(reg.get("verdict", "n/a")), regime_n=esc(reg.get("note", "")),
        tax_metric=tax_metric, tax_section=tax_section,
        dated=dated_html, trig=trig_html, segs="".join(segs), legs="".join(legs),
        rows=rows, keep=keep, watch=watch, next_date=esc(nr.get("date", "—")), next_reason=esc(nr.get("reason", "")), css=CSS, js=js)

TEMPLATE = """<title>{plan_label}</title>
<style>{css}</style>
<header class="masthead"><div class="shell">
  <p class="eyebrow">{plan_label} · Rev {rev} · mode: {mode}</p>
  <h1>What to do — by date</h1>
  <p class="sub">{owner} · refreshed {refreshed} · prices {asof} · tick tasks (saved on this device)</p>
  <div class="chips"><span class="chip gold">Corpus {corpus}</span><span class="chip">Goal {goal}</span><span class="chip">{guard}</span></div>
</div></header>
<main class="shell">
  <div class="updbar"><b>Goal: {goal}.</b> Prices = {asof} — always confirm live before buying. Deterministic render from state.json.</div>
  <div class="toolbar"><span id="prog">0 / 0 done</span><div class="spacer"></div>
    <button class="btn" id="copy-btn">\U0001F4CB Copy checklist</button>
    <div id="due-note"></div>
    <div id="export-panel"><div id="export-label"></div><textarea id="export-ta" readonly></textarea><p id="export-hint"></p></div>
  </div>
  <section class="metrics">
    <div class="metric"><span class="k">Corpus</span><span class="v">{corpus}</span><span class="note">investable</span></div>
    <div class="metric good"><span class="k">Regime</span><span class="v">{regime_v}</span><span class="note">{regime_n}</span></div>
    {tax_metric}
    <div class="metric"><span class="k">⏰ Next refresh</span><span class="v">{next_date}</span><span class="note">{next_reason}</span></div>
  </section>
  <section class="grp now tgroup" data-group="Dated actions">
    <h2><span class="tag">Do by date</span> Dated actions</h2>
    <p class="gsub">Sorted by date. Confirm live prices after market open before buying.</p>
    {dated}
  </section>
  <section class="grp tgroup" data-group="Trigger actions">
    <h2><span class="tag trig">On trigger</span> Buy only when the condition is met</h2>
    {trig}
  </section>
  <section class="grp">
    <h2>Reference — levels &amp; allocation</h2>
    <div class="tw"><table><thead><tr><th>Stock</th><th>Theme</th><th>Entry</th><th>Stop</th><th>Target</th><th>Amt</th></tr></thead><tbody>{rows}</tbody></table></div>
    <div class="alloc">{segs}</div><div class="legend">{legs}</div>
    <div class="two" style="margin-top:1rem">
      <div><h3>Regime</h3><p class="muted" style="font-size:.88rem">{regime_v} — {regime_n}</p><h3 style="margin-top:.8rem">Watchlist</h3><p class="muted" style="font-size:.85rem">{watch}</p></div>
      <div>{tax_section}
        <h3 style="margin-top:.8rem">Keep (not rotated)</h3><ul class="tight">{keep}</ul></div>
    </div>
  </section>
</main>
<footer><div class="shell"><p><b>{plan_label} (Rev {rev})</b> · {owner} · rendered from state.json by render_plan.py · refreshed {refreshed}. Educational only, not investment/tax advice — confirm live prices before every trade.</p></div></footer>
<script>{js}</script>
"""

def render_md(state):
    m = state["meta"]; out = []
    title = m.get("plan_label", "Action Board")
    owner = m.get("owner", "")
    out.append("# %s — Action Checklist%s\n" % (title, (" (%s)" % owner) if owner else ""))
    out.append("_Rev %s · refreshed %s · prices %s · goal %s · corpus %s._\n" % (
        m["rev"], m["last_refreshed"], m["prices_asof"], m["goal"], money(m["corpus_inr"])))
    out.append("_Confirm live prices before every buy. Educational only._\n")
    nr = m.get("next_review", {})
    if nr:
        out.append("**⏰ Next refresh:** %s — %s\n" % (nr.get("date", "—"), nr.get("reason", "")))
    its = tasks(state); dated = [i for i in its if i["due"]]; trig = [i for i in its if not i["due"]]
    out.append("\n## Dated actions")
    for i in dated:
        out.append("- [ ] (%s) **%s** — %s" % (i["due"], i["title"], " · ".join(i["spec"])))
    out.append("\n## Trigger actions")
    for i in trig:
        out.append("- [ ] (when: %s) **%s** — %s" % (i["trigger"] or "trigger", i["title"], " · ".join(i["spec"])))
    out.append("\n---\n**Keep:** " + " · ".join(state.get("keep_not_rotated", [])))
    return "\n".join(out) + "\n"

def render_ics(state):
    tag = state["meta"].get("tag", "W").lower()
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//w-bonkers//render_plan//EN", "CALSCALE:GREGORIAN"]
    for i in tasks(state):
        if not i["due"]:
            continue
        d = i["due"].replace("-", "")
        summ = i["title"].replace(",", "\\,")
        desc = (" · ".join(i["spec"])).replace(",", "\\,")
        L += ["BEGIN:VEVENT", "UID:%s@%s" % (i["id"], tag), "DTSTAMP:20260101T000000Z",
              "DTSTART;VALUE=DATE:%s" % d, "SUMMARY:%s" % summ, "DESCRIPTION:%s" % desc, "END:VEVENT"]
    L.append("END:VCALENDAR")
    return "\r\n".join(L) + "\r\n"

def render_todoist(state):
    """Deterministic Todoist payload with CLEAR buy zone / stop-loss / sell zone per task.
    The refresh command's sync step reads this and upserts into meta.todoist_project, matched by `ref`."""
    m = state["meta"]
    tag = m.get("tag", "W").upper()
    project = m.get("todoist_project", "%s Plan" % tag)
    cmd = m.get("command_name", "w-refresh")
    folder = m.get("folder", "your plan folder")
    out = []
    for i in tasks(state):
        lines = []
        for s in i["spec"]:
            if s.startswith("Buy zone"):
                lines.append("\U0001F7E2 " + s)          # green
            elif s.startswith("Stop-loss"):
                lines.append("\U0001F534 " + s)          # red
            elif s.startswith("Sell/target"):
                lines.append("\U0001F3AF " + s)          # target
            else:
                lines.append(s)
        lines.append("When: " + (i["due"] or (i["trigger"] or "trigger")))
        if i["note"]:
            lines.append("Why: " + i["note"])
        out.append({"ref": "%s-%s" % (tag, i["id"]), "project": project,
                    "title": "[%s] %s" % (tag, i["title"]), "due": i["due"],
                    "description": "\n".join(lines)})
    nr = m.get("next_review")
    if nr:
        out.append({"ref": "%s-NEXT-REVIEW" % tag, "project": project,
                    "title": "⏰ [%s] Run /%s next" % (tag, cmd), "due": nr.get("date"),
                    "description": "Recommended next run, timed to the market trend.\nWhy: " + nr.get("reason", "") +
                                   "\nRun your agent from %s and invoke: /%s" % (folder, cmd)})
    return out


def wrap_standalone(body, title):
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<title>%s</title>\n</head>\n<body>\n' % esc(title) + body + '\n</body>\n</html>\n')

def main():
    global CUR
    args = sys.argv[1:]
    state = json.load(open(STATE, encoding="utf-8"))
    CUR = state["meta"].get("currency", "₹")
    errors, warnings = validate(state)
    for w in warnings:
        print("WARN:", w)
    for e in errors:
        print("ERROR:", e)
    if errors and "--force" not in args:
        print("Validation failed — not writing (use --force to override).")
        sys.exit(1)
    if "--check" in args:
        print("Check only — validation %s." % ("passed" if not errors else "had errors"))
        return
    shutil.copyfile(STATE, STATE + ".bak")  # backup before we emit derived files
    body = render_body(state)
    title = state["meta"].get("plan_label", "Action Board")
    w = lambda name, data: open(os.path.join(ROOT, name), "w", encoding="utf-8").write(data)
    w("_artifact-source.html", body)
    w("board.html", wrap_standalone(body, title))
    w("tasks.md", render_md(state))
    w("tasks.ics", render_ics(state))
    w("todoist_tasks.json", json.dumps(render_todoist(state), ensure_ascii=False, indent=2))
    print("Rendered Rev %s: _artifact-source.html, board.html, tasks.md, tasks.ics, todoist_tasks.json (state.json.bak saved)." % state["meta"]["rev"])
    print("Validation: %d error(s), %d warning(s)." % (len(errors), len(warnings)))

if __name__ == "__main__":
    main()
