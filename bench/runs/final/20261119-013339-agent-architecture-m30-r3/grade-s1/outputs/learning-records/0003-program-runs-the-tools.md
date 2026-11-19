# Open misconception: Riley thinks the model runs the tools itself (M4)

On quiz 0001 (s1), Riley answered q2 and q4 as if the model opens the booking system and runs several tools inside one call. In fact the model only writes a request as text, the program runs the tool, and each result starts a new model call. Riley also thinks the model remembers across sessions without the program supplying it (M3, q6).

**Evidence:** quiz 0001, submission s1, items q2, q4, q6. Correct on q1 (the loop's structure) and q3 (a stopping condition breaks repetition).

**Implications:** Fix this before context and memory: the context window is what the program sends on each call, so M4 and M3 would undermine that lesson. Use a two-column trace (model output, program action) on the makerspace request.
