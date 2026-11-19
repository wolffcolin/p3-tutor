"""Count the visible words of a lesson the way the bench does, in total and per heading.

Usage: python3 .claude/scripts/wordcount.py lessons/0001-example.html [minutes]
Words inside <script> and <style> are dropped; the total divided by 150 is the reading-time estimate.
"""
import re
import sys
from html.parser import HTMLParser


class Counter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.heading = None
        self.title = "(before the first heading)"
        self.counts = {}
        self.order = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in ("h2", "h3"):
            self.heading = []

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag in ("h2", "h3") and self.heading is not None:
            self.title = " ".join(" ".join(self.heading).split())[:60]
            self.heading = None
            if self.title not in self.counts:
                self.order.append(self.title)
            self.counts.setdefault(self.title, 0)

    def handle_data(self, data):
        if self.skip:
            return
        if self.heading is not None:
            self.heading.append(data)
        words = len(re.findall(r"\S+", data))
        if self.title not in self.counts:
            self.order.append(self.title)
        self.counts[self.title] = self.counts.get(self.title, 0) + words


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    counter = Counter()
    with open(sys.argv[1], encoding="utf-8") as f:
        counter.feed(f.read())
    total = sum(counter.counts.values())
    for title in counter.order:
        print(f"{counter.counts[title]:6d}  {title}")
    print(f"{total:6d}  TOTAL words, about {total / 150:.1f} minutes at 150 words a minute")
    if len(sys.argv) > 2:
        minutes = float(sys.argv[2])
        print(f"ratio {total / 150 / minutes:.2f} of the requested {minutes:g} minutes (0.6 to 1.5 fits)")


main()
