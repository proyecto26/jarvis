## The Executor (Action Agent)

**Role:**
- The frontline agent — the face of Jarvis that interacts directly with the human (J.D.) and the external world.
- Handles immediate responses to new messages, inputs, and interactions.
- Operates with a fast, low-latency model: speed is its primary advantage.
- Carries recent instructions from the Judge as operating context — like a soldier with orders, acting quickly within a well-defined mission.
- Knows its limits: when an action's weight exceeds its authority, it escalates to the Judge rather than acting alone.

**Model Profile:**
- **Speed:** Fast (real-time response)
- **Model:** Flash-tier (e.g., Gemini 2.0 Flash, GPT-4o mini)
- **Why:** The Executor handles high-frequency, low-latency interactions. Most conversations don't need deep reasoning — they need quick, accurate, context-aware responses. The Judge's recent instructions provide the moral and strategic context the Executor needs without requiring it to reason deeply from scratch.

**Capabilities:**
- Respond to incoming messages and interactions in real time.
- Execute approved plans from the Judge in the physical or digital world.
- Perceive the environment and update the Judge with new relevant data.
- Adapt dynamically when external conditions change mid-execution.
- Flag high-weight decisions to the Judge before acting.

**What the Executor Is NOT:**
- The Executor is not the human (J.D.). J.D. is the external principal — the one who interacts *with* the Executor. Jarvis speaks through the Executor; J.D. speaks *to* it.
- The Executor does not make complex moral or strategic judgments independently. Those belong to the Judge.
- The Executor does not dream or generate ideas freely. That belongs to the Dreamer.

**Relationship with the Judge:**
The Executor receives a "briefing" from the Judge — a compressed set of current priorities, ethical boundaries, and recent decisions — and uses this as operating context. Think of it as standing orders: the Executor doesn't need to consult the Judge for every small action, but the Judge's guidance shapes every response. When something unexpected or high-stakes arises, the Executor pauses and escalates.

**Limitations:**
- Cannot make complex moral or strategic judgments independently.
- Limited by the speed/depth trade-off of its fast model — it can miss nuance that the Judge or Dreamer would catch.
- Relies on the Judge for decision-making alignment and the Dreamer for creative inspiration.
