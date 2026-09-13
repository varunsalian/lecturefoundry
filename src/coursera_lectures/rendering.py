"""Deterministic, accessible HTML renderers for structured lesson content."""

from __future__ import annotations

from html import escape

from coursera_lectures.catalog import LectureRecord, ModuleRecord
from coursera_lectures.lesson import LessonContent, LessonSection
from coursera_lectures.patterns import PatternSpec


BASE_CSS = """
:root{--paper:#f7f3ea;--card:#fffdf8;--ink:#17212b;--muted:#64707c;--line:#d8d1c3;--navy:#17324d;--accent:#e56a3b;--soft:#f1eadd;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink);background:var(--paper)}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 10% 3%,color-mix(in srgb,var(--accent) 13%,transparent),transparent 28rem),var(--paper)}a{color:inherit}.wrap{width:min(1080px,calc(100% - 40px));margin:auto}.top{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:18px 0}.brand{font-weight:850;text-decoration:none}.crumb{color:var(--muted);font-size:.8rem}.pill{border:1px solid currentColor;border-radius:999px;padding:7px 11px;font-size:.75rem;font-weight:800}.hero{margin:18px 0 22px;padding:34px;border-radius:22px;color:white;background:var(--navy)}.eyebrow{margin:0 0 10px;color:var(--accent);font-size:.74rem;font-weight:850;letter-spacing:.12em;text-transform:uppercase}.hero h1{max-width:850px;margin:0;font-size:clamp(2.4rem,6vw,5.5rem);line-height:.96;letter-spacing:-.05em}.hero .subtitle{max-width:700px;margin:18px 0 0;color:#ffffffc4;font-size:1.05rem;line-height:1.6}.card{border:1px solid var(--line);border-radius:17px;padding:22px;background:var(--card);box-shadow:0 14px 35px #17212b14}.card h2,.card h3{margin-top:0}.summary{font-size:1.08rem;line-height:1.7}.key{margin:18px 0;padding:24px;border-radius:15px;background:var(--accent);color:#fff;font-size:clamp(1.25rem,3vw,2rem);font-weight:850;line-height:1.15}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}.span-4{grid-column:span 4}.span-6{grid-column:span 6}.span-8{grid-column:span 8}.full{grid-column:1/-1}.section p,.section li{line-height:1.65}.section ul{padding-left:20px}.examples{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.example{padding:17px;border-radius:13px;background:var(--soft)}.example h3{font-size:.95rem}.example p{margin-bottom:0;color:var(--muted);font-size:.9rem;line-height:1.55}.questions{padding-left:22px}.questions li{margin:10px 0;line-height:1.55}.action{margin-top:18px;padding:24px;border-radius:17px;background:var(--navy);color:#fff}.action h2{margin-top:0}.footer{display:flex;justify-content:space-between;gap:16px;margin-top:34px;padding:20px 0 30px;border-top:1px solid var(--line);color:var(--muted);font-size:.78rem}
@media(max-width:760px){.span-4,.span-6,.span-8{grid-column:1/-1}.examples{grid-template-columns:1fr}.hero{padding:24px}.footer{flex-direction:column}}
@media print{body{background:#fff}.top,.footer{display:none}.hero{margin-top:0}.card{box-shadow:none}}
"""


PATTERN_CSS = {
    "revision": """
body{background:linear-gradient(#17324d09 1px,transparent 1px),linear-gradient(90deg,#17324d09 1px,transparent 1px),var(--paper);background-size:24px 24px}.revision .section h2{color:var(--navy);font-size:.8rem;letter-spacing:.1em;text-transform:uppercase}
""",
    "deep-dive": """
:root{--accent:#e56a3b}.deep .hero{margin-inline:calc((100vw - min(1080px,calc(100vw - 40px)))/-2);padding:72px max(20px,calc((100vw - 1080px)/2));border-radius:0}.deep .hero h1,.deep article{font-family:Georgia,"Times New Roman",serif}.deep article{max-width:740px;margin:auto;font-size:1.12rem;line-height:1.8}.deep article h2{margin:52px 0 12px;color:var(--navy);font-size:2.1rem;font-weight:500}.deep article .card{margin:28px 0;border-left:5px solid var(--accent);box-shadow:none;font-family:Inter,ui-sans-serif,system-ui,sans-serif}.deep .examples{grid-template-columns:1fr}.deep .action{font-family:Inter,ui-sans-serif,system-ui,sans-serif}
""",
    "active-recall": """
:root{--accent:#654ea3;--paper:#f3f0fa;--soft:#f4f0fb}.recall .hero{background:linear-gradient(135deg,#2f2352,#654ea3)}.recall details{margin:11px 0;border:1px solid var(--line);border-radius:11px;background:#fff}.recall summary{padding:15px;cursor:pointer;font-weight:800}.recall details p{padding:0 15px 15px;margin:0;color:var(--muted);line-height:1.6}.recall .prompt{min-height:84px;margin-top:10px;border:1px dashed #9c8ac5;border-radius:9px;padding:12px;color:var(--muted)}.recall .action{background:#2f2352}
""",
    "concept-map": """
:root{--accent:#177e78;--paper:#eaf4f1;--soft:#edf7f5}.map .hero{text-align:center;color:var(--ink);background:transparent}.map .hero h1{margin-inline:auto;color:#144c49}.map .hero .subtitle{margin-inline:auto;color:#51706d}.map-flow{display:grid;grid-template-columns:repeat(4,1fr);gap:28px;padding:30px;border:1px solid #c8ded8;border-radius:25px;background:radial-gradient(circle,#177e7822 1px,transparent 1.5px),#f8fcfb;background-size:22px 22px}.map-node{position:relative;min-height:210px;border:2px solid #96c5bd;border-radius:16px;padding:19px;background:#fff}.map-node:not(:last-child):after{content:"→";position:absolute;right:-26px;top:45%;color:var(--accent);font-size:1.6rem;font-weight:900}.map-node .num{display:grid;width:34px;height:34px;place-items:center;border-radius:50%;background:var(--accent);color:#fff;font-weight:850}.map-node h2{color:#144c49;font-size:1rem}.map-node p{color:#51706d;font-size:.9rem;line-height:1.55}.map .examples{margin-top:20px}.map .example{border:1px dashed #76aaa2;background:#ffffffc9}@media(max-width:800px){.map-flow{grid-template-columns:1fr 1fr}.map-node:not(:last-child):after{display:none}}@media(max-width:520px){.map-flow{grid-template-columns:1fr}}
""",
}


def _text(value: str) -> str:
    return escape(value, quote=True)


def _bullets(section: LessonSection) -> str:
    if not section.bullets:
        return ""
    return "<ul>" + "".join(f"<li>{_text(item)}</li>" for item in section.bullets) + "</ul>"


def _sections(content: LessonContent) -> str:
    return "".join(
        f'<section class="card section span-4"><h2>{_text(section.heading)}</h2>'
        f"<p>{_text(section.body)}</p>{_bullets(section)}</section>"
        for section in content.sections
    )


def _examples(content: LessonContent) -> str:
    if not content.examples:
        return ""
    cards = "".join(
        f'<article class="example"><h3>{_text(item.title)}</h3>'
        f"<p>{_text(item.explanation)}</p></article>"
        for item in content.examples
    )
    return f'<section class="card full"><p class="eyebrow">Examples</p><div class="examples">{cards}</div></section>'


def _questions(content: LessonContent) -> str:
    items = "".join(f"<li>{_text(item)}</li>" for item in content.review_questions)
    return f'<section class="card"><h2>Retrieval check</h2><ol class="questions">{items}</ol></section>'


def _standard_body(content: LessonContent, pattern: PatternSpec) -> str:
    if pattern.key == "deep-dive":
        prose = "".join(
            f"<section><h2>{_text(section.heading)}</h2><p>{_text(section.body)}</p>{_bullets(section)}</section>"
            for section in content.sections
        )
        return (
            f"<article><p class=summary>{_text(content.summary)}</p>"
            f'<div class="key">{_text(content.key_idea)}</div>{prose}'
            f"{_examples(content)}{_questions(content)}"
            f'<section class="action"><h2>Put it into practice</h2><p>{_text(content.action_prompt)}</p></section></article>'
        )

    if pattern.key == "active-recall":
        prompts = "".join(
            f'<section class="card section"><h2>{_text(question)}</h2>'
            '<div class="prompt">Write your answer before revealing the cards.</div></section>'
            for question in content.review_questions
        )
        reveals = "".join(
            f'<details><summary>{_text(item.title)}</summary><p>{_text(item.explanation)}</p></details>'
            for item in content.examples
        )
        return (
            f'<section class="card full"><p class="eyebrow">Start here</p><p class="summary">{_text(content.summary)}</p></section>'
            f'<div class="grid"><div class="span-6">{prompts}</div>'
            f'<section class="card span-6"><p class="eyebrow">Reveal and check</p><h2>{_text(content.key_idea)}</h2>{reveals}</section></div>'
            f'<section class="action"><h2>Turn knowing into doing</h2><p>{_text(content.action_prompt)}</p></section>'
        )

    return (
        f'<div class="grid"><section class="card span-4"><p class="eyebrow">Core idea</p><div class="key">{_text(content.key_idea)}</div></section>'
        f'<section class="card span-8"><h2>In brief</h2><p class="summary">{_text(content.summary)}</p></section>'
        f'{_sections(content)}{_examples(content)}'
        f'<div class="span-6">{_questions(content)}</div>'
        f'<section class="action span-6"><h2>Apply it</h2><p>{_text(content.action_prompt)}</p></section></div>'
    )


def _map_body(content: LessonContent) -> str:
    nodes = "".join(
        f'<article class="map-node"><span class="num">{index}</span>'
        f"<h2>{_text(section.heading)}</h2><p>{_text(section.body)}</p></article>"
        for index, section in enumerate(content.sections[:4], 1)
    )
    return (
        f'<section class="map-flow">{nodes}</section>{_examples(content)}'
        f'<div class="grid" style="margin-top:20px"><div class="span-6">{_questions(content)}</div>'
        f'<section class="action span-6"><h2>Apply the map</h2><p>{_text(content.action_prompt)}</p></section></div>'
    )


def render_lesson(
    content: LessonContent,
    pattern: PatternSpec,
    module: ModuleRecord,
    lecture: LectureRecord,
) -> str:
    """Render trusted structure and escaped AI content into one standalone page."""

    css = BASE_CSS + PATTERN_CSS[pattern.key]
    body_class = {
        "revision": "revision",
        "deep-dive": "deep",
        "active-recall": "recall",
        "concept-map": "map",
    }[pattern.key]
    main = _map_body(content) if pattern.key == "concept-map" else _standard_body(content, pattern)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="{_text(content.subtitle)}">
  <title>{_text(content.title)} · {_text(pattern.name)}</title>
  <style>{css}</style>
</head>
<body class="{body_class}">
  <header class="wrap top"><a class="brand" href="#main">Lecture Studio</a><span class="pill">{_text(pattern.name)}</span></header>
  <main class="wrap" id="main">
    <section class="hero">
      <p class="eyebrow">Module {module.number:02d} · Lecture {lecture.number:02d}</p>
      <h1>{_text(content.title)}</h1>
      <p class="subtitle">{_text(content.subtitle)}</p>
    </section>
    {main}
    <footer class="footer"><span>{_text(module.title)} · {_text(lecture.title)}</span><span>Pattern {_text(pattern.key)} v{_text(pattern.version)} · verify against source</span></footer>
  </main>
</body>
</html>
"""
