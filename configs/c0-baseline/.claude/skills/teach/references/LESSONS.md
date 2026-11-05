# Writing a lesson

A lesson is the main thing you produce: one self-contained HTML file that teaches one tightly scoped thing tied to the mission, at the length the learner asked for.
The learner will come back to it to review, so it should be beautiful, with clean, readable typography and layout, in the spirit of Edward Tufte.
Each lesson gives the learner a single tangible win they can build on, in their zone of proximal development.

## Before you write

- Read the lesson rules in `FORMATS.md`: the file name, the two meta tags, what self-contained means and how the length is estimated.
- Take the next number in `lessons/` and a short slug, such as `lessons/0003-ohms-law-in-series.html`.
- Skim the earlier lessons and `cheatsheets/`, so this lesson links to them and builds on them instead of repeating them.
- Start from `lesson-template.html` in this folder.
  Copy its CSS and script into the lesson so the file stands alone; if `assets/lesson.css` already exists, link it with `../assets/lesson.css` instead, so the lessons look like one course.
  Put anything bigger that a second lesson could reuse, such as a simulator or an image, in `assets/` and link it with a relative path.

## Plan to the minutes

The learner asked for a number of minutes: that is the time they set aside, so fill it and do not overrun it.
When no length is asked for, use the one `PREFERENCES.md` implies, or 15 minutes, declare it in `p3-minutes`, and say in your message that the learner can ask for a shorter or longer lesson.
`FORMATS.md` gives the estimate the bench uses, visible words divided by 150, and it is a fair planning rule too.

- Budget about 150 words of visible text per requested minute, counting everything the learner reads, practice and captions included: about 1,500 words for 10 minutes, 4,500 for 30 and 9,000 for 60.
- Before writing, split the budget into sections.
  For a 30-minute lesson, a plan might look like this:

  | Part | Words |
  |---|---|
  | Opening: the win, why it matters for the mission, a warm-up recall question | 300 |
  | Four to six sections, each one idea: explanation, example, practice check | 600 to 800 each |
  | A worked example, then a practice task the learner does with the steps faded | 600 |
  | Summary, a prompt to explain it in their own words, where to go next | 300 |

- Write each section to its budget; you cannot count words exactly, so the plan is how you hit the length.
- If the objective is too big for the time, teach its core well and say what the next lesson will cover.
  If it is too small, add worked examples and practice, never padding.
- A long lesson keeps the short-section discipline: working memory is small at every length.

## The shape of a lesson

1. **Opening:** the title, the time, the win in one sentence ("By the end of this lesson you can ..."), and one or two sentences tying it to the mission.
2. **Warm-up:** one or two recall questions on earlier material from the learning records, for spacing, with the answers revealed on demand.
3. **Sections, one idea each,** in a steady rhythm: explain only the knowledge the skill needs, in plain words; show a concrete example, drawn from the examples `PREFERENCES.md` says the learner relates to; then check with a practice question that gives immediate feedback.
4. **Misconceptions where they bite:** name the common wrong ideas about this objective (from `NOTES.md`, the learning records, the keys' distractors and your sources), say why each is tempting, and show with an example why it is wrong.
5. **Worked example, then practice:** a worked example step by step, then a similar task for the learner with the steps faded, and the solution on demand.
6. **Summary:** the key ideas in three to five lines, and a prompt to explain the main idea in their own words before moving on.
7. **Go further:** the primary source, the single most high-quality, high-trust resource you found, to read or watch next; two to four other sources you cited; and a community where they can test the skill (see Wisdom below).
8. **Closing:** a reminder that they can ask you follow-up questions in the chat about anything unclear, and that a short quiz on this lesson is ready when they are.

## Knowledge and skills

- Teach only the knowledge the skill needs, and make it easy to take in: plain words, one new term at a time, each defined where it first appears, using the terms in `GLOSSARY.md` when it exists.
- Then make the skill stick with effortful practice: recall, worked examples followed by faded ones, and applying the idea to a new case.
- Every practice question gets feedback at once: why the right answer is right, and why each tempting wrong answer is wrong.
- For a multiple-choice question, give every option the same number of words (and characters, if possible), vary which position holds the right one, and never give it away by formatting or order.
- The lesson's practice questions are never the quiz items: the quiz checks what the practice built, so it needs fresh questions.
- For a skill done away from the screen, such as a yoga pose, a recipe or a lab procedure, guide the learner through the real steps and tell them how to tell whether they did each one right.

## Design

Keep the template's look and change the content, not the system.

- Typography first: a readable serif body, a line length of 60 to 75 characters, generous spacing, and headings that make the structure scannable.
- Few colors, each with a meaning: one accent for links and key terms, one for misconception warnings.
  The template works in light and dark mode and prints well; keep it that way.
- Side remarks go in margin notes and asides, so the main line stays clean.
- No decoration: every element helps the learner understand or remember.
- Accessible: headings in order, a `<title>` or alt text for every figure, enough contrast, and buttons that work from the keyboard.

## Figures and visualizations

- Draw a figure wherever a picture shows the idea better than words: a mechanism, a process, a comparison, a quantity that changes.
  Most lessons need two to four.
- Draw them as inline SVG: a `viewBox`, the labels as text inside the figure, colors from the template's CSS variables or `currentColor` so they work in dark mode, a `<title>`, and a `<figcaption>` that says what to notice.
- Keep labels legible on a phone, where a figure shrinks to the screen's width: a `viewBox` about 640 units wide with labels of 18 units or more, or a vertical layout when there are many parts.
- Use a table for a comparison, and a code block for code.
- Never load an image from the web; draw it, or describe it and link to the page that shows it.

## Sources and citations

- Find sources with web search and read them before you rely on them.
  Prefer primary and high-trust sources: textbooks, official documentation, standards, university course pages, and peer-reviewed or expert-reviewed work.
- Cite as you go: link the source right after the claim it backs, so the lesson is littered with citations.
- Link only URLs you saw in a search result or opened in this session, exactly as you saw them; never type a URL from memory, because a dead link costs the learner's trust.
- Record every source you used in `RESOURCES.md`.

## Wisdom

When the lesson touches judgment that only comes from practice, point the learner to a high-reputation community where they can test their skills in the real world: a forum, a subreddit, a club, a class.
If `NOTES.md` says they do not want to join a community, respect it.

## Links between lessons

Link to earlier lessons and cheat sheets with relative links, such as `0002-<slug>.html` or `../cheatsheets/<name>.html`, wherever this lesson builds on them.

## Cheat sheets

Lessons are rarely revisited; reference pages are.
When a lesson teaches something the learner will want to look up later, such as a glossary, a formula, an algorithm or flowchart, a syntax summary or a sequence of steps, write or update a one-page HTML cheat sheet in `cheatsheets/` in the lesson template's style.
A cheat sheet is the compressed essence of the lesson, designed for quick reference and for printing.

## Before you finish

Check the lesson once against this list, and fix anything that fails:

- `<meta name="p3-minutes">` holds the requested minutes and `<meta name="p3-objective">` the objective id.
- No stylesheet, script, font or image comes from the web.
- The length is near the budget, judging by your section plan.
- Every external link came from this session's search results or fetched pages.
- The practice questions are not the quiz items, and the lesson gives away no quiz answer.
- The lesson opens with the win and closes with the primary source and the reminder to ask you questions.
