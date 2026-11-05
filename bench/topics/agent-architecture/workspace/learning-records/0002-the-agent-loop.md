# An agent is a model called in a loop, with tools and a way to stop

Riley can describe the agent loop: the model is given a goal and a set of tools, it asks for an action, the action is carried out, the result goes back to the model, and this repeats until the model gives a final answer or a limit is reached.
This is what turns a chatbot that answers into a system that acts, and it is the core of the makerspace assistant.

**Evidence:** Traced one request on paper ("Is the laser cutter free on Friday?") from the question to the final answer, naming the tool that gets called and the result that comes back.

**Implications:** Next in the mission is context and memory: what the model actually sees at each step, and what the assistant can remember between sessions.
Not yet checked: whether Riley sees that the program, not the model, runs each tool, and that every step is a separate model call.
Quiz 0001 tests both, along with the loop itself.
