"""Fill the sidebar navigation and the previous/next links of every page of the P3 Guide from chapters.json.

Run from this folder: python3 build.py
Each page keeps its own content; only the text between the nav and pager markers is rewritten.
"""

import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHAPTERS = json.loads((HERE / "chapters.json").read_text(encoding="utf-8"))
NAME_IN_PARENS = re.compile(r"\(([a-z0-9-]+)\)")


def title_html(title: str) -> str:
    """A chapter title, escaped, with a config name in parentheses kept on one line: (c3-split)."""
    return NAME_IN_PARENS.sub(r'<span class="nw">(\1)</span>', html.escape(title))


def nav_html(current: str) -> str:
    out = ['<nav class="toc" aria-label="Chapters">', '<details class="toc-box" open>', '<summary>Chapters</summary>', '<ol class="toc-list">']
    part = None
    for c in CHAPTERS:
        if c["part"] and c["part"] != part:
            part = c["part"]
            out.append(f'<li class="toc-part">{html.escape(part)}</li>')
        cls = ' class="current" aria-current="page"' if c["file"] == current else ""
        out.append(f'<li><a href="{c["file"]}"{cls}>{title_html(c["title"])}</a></li>')
    out += ["</ol>", "</details>", "</nav>"]
    return "\n".join(out)


def pager_html(current: str) -> str:
    files = [c["file"] for c in CHAPTERS]
    i = files.index(current)
    parts = ['<nav class="pager" aria-label="Previous and next chapter">']
    if i > 0:
        p = CHAPTERS[i - 1]
        parts.append(f'<a class="prev" href="{p["file"]}"><span class="pager-label">Previous</span><span class="pager-title">{title_html(p["title"])}</span></a>')
    else:
        parts.append("<span></span>")
    if i < len(files) - 1:
        n = CHAPTERS[i + 1]
        parts.append(f'<a class="next" href="{n["file"]}"><span class="pager-label">Next</span><span class="pager-title">{title_html(n["title"])}</span></a>')
    parts.append("</nav>")
    return "\n".join(parts)


def main() -> None:
    for c in CHAPTERS:
        page = HERE / c["file"]
        if not page.exists():
            print(f"missing: {c['file']}")
            continue
        text = page.read_text(encoding="utf-8")
        text = re.sub(r"<!-- nav:start -->.*?<!-- nav:end -->", f"<!-- nav:start -->\n{nav_html(c['file'])}\n<!-- nav:end -->", text, flags=re.S)
        text = re.sub(r"<!-- pager:start -->.*?<!-- pager:end -->", f"<!-- pager:start -->\n{pager_html(c['file'])}\n<!-- pager:end -->", text, flags=re.S)
        page.write_text(text, encoding="utf-8", newline="\n")
        print(f"built: {c['file']}")


if __name__ == "__main__":
    main()
