# Mission: Agent architecture

## Why
My senior design team is building an assistant for our university makerspace that answers students' questions from the machine manuals, checks the booking calendar and books equipment time.
I am the one designing how it works, so I need to understand agents well enough to choose an architecture, defend it at our design reviews and keep it within the small budget our sponsor gave us for model usage.

## Success looks like
- I can sketch the assistant's loop for a real request: the tools it calls, what comes back, and when it stops.
- I can write a clear description for one of our tools and explain how the model uses it.
- I can decide what the assistant keeps in its context, what it saves between sessions, and how it finds the right page in a long manual.
- I can argue, with a reason, which parts of the assistant should be a fixed workflow rather than an agent.
- I can explain to my team when splitting the work across several agents would pay off and when it would not.

## Constraints
- I have about three hours a week alongside a full course load, and our first design review is in five weeks.
- I am comfortable with Python but have never called a language model from code.
- Our model budget is small, so cost per request matters.

## Out of scope
- Training or fine-tuning models, and the math inside them.
- Deploying and scaling the assistant in production; the team will handle hosting later.
- Comparing specific AI companies and their products.
