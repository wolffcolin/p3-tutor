# Open gaps in the agent loop: the program runs tools, and a loop needs a stop

On the spaced-practice retake of quiz 0001 (s2), Riley chose the right option for what an agent is and for what the model outputs on a tool call, and knew that a tool result goes back as the model's next input. Three gaps remain: Riley said "the model runs one tool itself each call" (M4) while counting the calls correctly, chose "let it run longer" for a looping agent (M6), and said the model picks a tool "by the name" alone.

**Evidence:** quiz 0001, submission s2, items q3, q4 and q6.

**Implications:** Before building on tool definitions, revisit that the program runs tools and the model only writes requests. Teach that the model chooses from the whole tool description, and that every loop needs a stopping condition such as a step limit, which also caps cost.
