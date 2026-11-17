# Open misconception: Riley thinks the model runs the tools itself (M4)

On quiz 0001, submission s1, Riley chose the option where the model reads the booking system itself (q2) and said the model "runs the 3 tools itself" in one call (q4).
Riley does know the loop's shape and that the model picks tools from their descriptions (q1, q3, q6).
Riley also assumed the model remembers its past tool choices across sessions (M3).

**Evidence:** quiz 0001, submission s1, items q2, q4 and q6.

**Implications:** The next lesson should draw the split between model and program: the model outputs a tool request as text, the program runs it, and each result starts a new model call.
Memory must be taught as something the program saves and resends, not something the model does on its own.
Check this again with a fresh item after the lesson.
