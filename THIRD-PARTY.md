# Third-party notices

## The teach skill

`tutor/.claude/skills/teach/` is adapted from the `teach` skill in Matt Pocock's [mattpocock/skills](https://github.com/mattpocock/skills), folder [`skills/productivity/teach`](https://github.com/mattpocock/skills/tree/main/skills/productivity/teach), and is used under the MIT License below.
It was taken from the `main` branch on 2026-11-01, at commit `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d`; the folder last changed upstream in commit `ad5400b930b297b0c0cb231ff1ffe42a7da666aa` (2026-10-07).

What came from upstream, and what changed:

- `SKILL.md` keeps the upstream workspace model (the mission, learning records, lessons, assets, resources, glossary and notes) and its pedagogy (knowledge, skills and wisdom; fluency against storage strength; retrieval practice, spacing and interleaving; the zone of proximal development; beautiful lessons with citations and a primary source; communities for wisdom).
  It was rewritten so that one agent does four jobs (teach, tutor, quiz and grade) in one pass: `disable-model-invocation` is dropped, a lesson honors a requested length in minutes, every lesson comes with a short quiz and its key, every file the bench reads follows `FORMATS.md`, the workspace's `reference/` folder is renamed `cheatsheets/` so it cannot be confused with the skill's own `references/`, and the detailed guidance moved into `references/`.
- `references/MISSION-FORMAT.md`, `references/LEARNING-RECORD-FORMAT.md`, `references/RESOURCES-FORMAT.md` and `references/GLOSSARY-FORMAT.md` are the upstream format files, lightly edited: one sentence per line, "the learner" for "the user", and paths and numbering matched to `FORMATS.md`.
- `references/LESSONS.md`, `references/lesson-template.html`, `references/QUIZZES.md`, `references/GRADING.md` and `references/TUTORING.md` are new, written for this course on the upstream skill's guidance.
- Upstream's `agents/openai.yaml` (metadata for Codex) is not included.

The same notice covers every copy of these files under `configs/`.

## MIT License (mattpocock/skills)

```text
MIT License

Copyright (c) 2026 Matt Pocock

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## The guide's fonts

The pages in `guide/` load three typefaces from Google Fonts when you open them: Bitter, Public Sans and IBM Plex Mono.
All three are under the SIL Open Font License 1.1, and none of their files are in this repo.
Without a network connection the pages use your system's fonts instead.
