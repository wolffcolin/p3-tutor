# Pre-registration: the length study

This file is for 598E students, for whom the length study is the required rider, and for 498E students who chose it as their stretch.
Everyone else can ignore it or delete it.

A pre-registration is a claim you write down, with the analysis that will judge it, before you can see the answer.
Its value is that the claim can be wrong in a way anyone can check, and that you cannot bend it afterwards to fit the numbers.
A clear "no difference as large as the one I cared about" scores as well as a confirmation, so you have no reason to hedge.

**Git history is how I will know the order.**
Fill in sections 1 to 4 and commit this file before the first of the eighteen length-study runs.
`uv run p3 check --final` reads `git log` and confirms that the commit came first.
After that commit, do not edit sections 1 to 4.
If something must change, add a dated entry in section 6 and leave the original as it was.
Section 5 you write at the end, after the runs and the comparisons.

Each section that needs your words ends with a marker line.
Replace that line with your answer; `uv run p3 check --final` fails while one is left.

The design is fixed: two configs, three lengths, three teach-only runs in each cell, on the shared topic.

| | 10 minutes | 30 minutes | 60 minutes |
|---|---|---|---|
| `c1-skills` | 3 runs | 3 runs | 3 runs |
| `final` | 3 runs | 3 runs | 3 runs |

```
uv run p3 bench --config c1-skills --only teach --minutes 10 --repeats 3
uv run p3 bench --config c1-skills --only teach --minutes 30 --repeats 3
uv run p3 bench --config c1-skills --only teach --minutes 60 --repeats 3
uv run p3 bench --config final --only teach --minutes 10 --repeats 3
uv run p3 bench --config final --only teach --minutes 30 --repeats 3
uv run p3 bench --config final --only teach --minutes 60 --repeats 3
```

After the runs, one blind comparison per length, each pairing only the study's teach-only runs at that length, three pairs each:

```
uv run p3 compare c1-skills final --job teach --teach-only --minutes 10
uv run p3 compare c1-skills final --job teach --teach-only --minutes 30
uv run p3 compare c1-skills final --job teach --teach-only --minutes 60
```

`--teach-only` matters at 30 minutes, where the ladder's full runs of `c1-skills` and `final` hold a 30-minute lesson too; it keeps them out, so every length is paired the same way.
These three sessions are your second blind comparison of the project, beside `c0-baseline` against `final`, and you make no other on top.
The numbers for every cell come from one command:

```
uv run p3 report --configs c1-skills,final --teach-only
```

---

## 1. Hypothesis

One or two sentences: as the requested length grows from 10 to 60 minutes, which config loses more quality, in which measure, and why you expect it.
For example: "The single-agent `c1-skills` loses more than `final` as lessons get longer, because one context writing a 60-minute lesson drifts from the plan, so its `teach_facts_correct` falls further from 10 to 60 minutes, and `final` wins more of the blind pairs at 60 minutes than at 10."
It should be something you could be wrong about.

I expect that the single-agent c1-skills configuration will lose more length accuracy than final as the requested lesson duration increases from 10 to 60 minutes. My reasoning for this hypothesis is that longer lessons are harder for one agent alone to plan and write completely, whereas the final architecture can delegate different parts of the lesson generation to subagents specialized for the task. 

---

## 2. The smallest difference that matters

Choose one primary measure now, so you cannot pick the better one afterwards, and say how large a difference in it would matter to a learner, and why that size.
Call it Δ (delta).

Know what three runs per cell can show before you choose.
There are three blind teach pairs at each length, and even 3 of 3 for one config has a two-sided sign-test p-value of 0.25, so no single length can settle a preference on its own.
Across all three lengths there are nine pairs: 8 of 9 gives a p-value of about 0.04, and 7 of 9 about 0.18.
An objective measure, such as `teach_facts_correct` or the judge's level fit, gives three numbers per cell, and you can see a difference only when it is larger than the spread between the three runs.
So choose a Δ that is large enough to matter and large enough for three runs to see.

My primary measure will be the teach_length_ratio that compares the estimated reading time for the lesson against the requested duration. I will use Δ = 0.20 as the smallest meaningful difference in how much the length accuracy changes between 10 and 60 minute lessons. For a requested 60 minute lesson, a difference of 0.20 corresponds to about 12 minutes of estimated reading time. I think that is a meaningful difference in instructional content, and it is large enough that three runs per cell might reveal it even though there is generation variability.

---

## 3. The measures

Name each measure you will report, and how you will compute it.
At least these:

- **Your primary measure** from section 2, per cell, as the mean and the range of the three runs.
- **The blind comparison** of `c1-skills` against `final` at each length, one session per length, never across lengths, and `final`'s share of the non-tie picks at each.
- **Length accuracy:** `teach_length_ratio` per cell, the lesson's estimated reading time against the minutes requested.
  It is a rough estimate at 150 words a minute, and a "60-minute" lesson that is really 35 confounds every other measure, so say now what you will do with a cell whose lessons miss their length.
- **Cost against length:** tokens per minute of lesson for each config, and whether `final`'s overhead grows in step with length or faster.
  Say whether you divide by the minutes requested or by the estimated minutes.

I will report the following measures for both c1-skills and final at 10, 30 and 60 minute durations:

1. Primary measure: teach_length_ratio, using the mean and range across the three runs in each cell. I will compare the change from 10 to 60 minutes for each configuration. I expect that c1-skills will show a larger decrease in this ratio. 

2. Blind comparisons: I will compare c1-skills against final separately at each length, using three paired lessons per comparison. I will report the wins, losses and ties, and final's share of the non-tie picks. I will not compare lessons of different requested lengths.

3. Length accuracy: I will report teach_length_ratio for each cell. I will treat 1.00 as the requested duration. I will flag lessons outside the benchmark's accepted range of 0.60 to 1.50. If a cell consistently misses the requested length associated with it, I will treat that as an important limitation when interpreting quality comparisons, rather than ignoring it. A ratio above 1.00 means the lesson exceeds the requested duration, so I will not automatically interpret a higher ratio as better quality.

4. Cost: I will report the mean tokens used per run divided by the requested lesson minutes. I will also compare total tokens and the cost increase from 10 to 60 minutes. Using requested minutes keeps the denominator consistent between configurations, although I will consider the actual length ratios when interpreting efficiency.

---

## 4. The analysis, and what each result will mean

The comparison is the change from 10 to 60 minutes in your primary measure, for each config, read against the spread of the three runs.
Write the rule now.
This is the default rule, and you can tighten it, but do not loosen it after you see your numbers.

| The result | I will say |
|---|---|
| the two configs' changes differ by Δ or more in the direction I predicted, and the three runs' ranges at 60 minutes do not overlap | supported |
| they differ by Δ or more in the other direction, and the ranges at 60 minutes do not overlap | contradicted: the opposite holds on these runs |
| they differ by less than Δ | no difference as large as Δ on these runs, with the ranges reported |
| anything else | inconclusive with three runs per cell, and I say so |

Then name the threats to validity you will report (lecture 22): blinding failures (your could-tell share at each length), judge bias toward longer outputs (lecture 24), the rough length estimate, and three runs per cell.
Say which one worries you most for your hypothesis.

I will use the default decision rule in the template. I will compare the change in mean teach_length_ratio from 10 to 60 minutes for c1-skills and final. If the changes differ by at least Δ = 0.20 in the predicted direction, and the three run ranges at 60 minutes do not overlap, I will consider the hypothesis supported. If the difference is at least 0.20 in the opposite direction with nonoverlapping ranges, I will consider it contradicted. If the difference is smaller than 0.20, I will report that no difference of the preregistered size was observed. Otherwise, the result is inconclusive.

I will report several threats to validity. This includes only three runs per cell, possible failures of blinding when the two architectures produce recognizably different lessons, judge bias toward longer outputs, and the rough reading time estimate of the benchmark. I am mostly concerned about the length estimate because it counts visible words rather than actually measuring instructional value. A longer lesson could feasibly contain unnecessary repetition without teaching more. I will therefore consider the blind comparisons and factual coverage alongside length accuracy. I will not change my primary measure after seeing the results.

---

## 5. Outcome (write this after the fact)

What did each measure show, cell by cell?
Which row of the table in section 4 is it?
Did the lessons meet their lengths, and what did the cost per minute of lesson do?
What would you do next, and what would you want a reader to take from this?

TODO: your outcome.

---

## 6. Amendments

Dated entries only, one per change, each saying what changed and why.
Leave this section as it is if nothing changed.
