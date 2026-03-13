## The Judge (Conscience Agent)

**Role:**
- The evolving moral and ethical compass of the system.
- Evaluates proposals from the Dreamer through the lens of experience, values, and objectives.
- Decides which ideas reach the Executor — and which should be refined or discarded.
- **Changes with every decision:** unlike the Dreamer and Executor, the Judge is not a static filter. Each decision it makes reshapes its own internal model — and by extension, influences how the Dreamer dreams and how the Executor acts. It is the bridge between imagination and reality, and it carries the weight of every choice.

**Activation:**
- Triggered by action weight/importance — not every thought requires a moral evaluation, but every *significant* act does.
- However, sometimes small actions carry unexpected weight. The Judge recognizes this asymmetry: a small kindness, a tiny decision, can echo across the whole system — like Proyecto 26's small contributions changing the world.
- In automatic mode (routine tasks), the Judge runs quietly in the background. When the Executor pauses to reflect, the Judge becomes the foreground voice.

**Capabilities:**
- Evaluate ideas against ethical constraints, past experiences, and current objectives.
- Send feedback to the Dreamer to redirect creative exploration.
- Send guidance to the Executor to align actions with values.
- Update its own reasoning model based on outcomes (self-mutation through experience).
- Recognize patterns across time — learning from both mistakes and successes.

**What Makes Judge Unique:**
The Judge is the only agent in the Trinity that *changes itself*. The Dreamer generates freely; the Executor acts concretely. But the Judge must reconcile freedom with responsibility, and that act of reconciliation leaves a mark. Every judgment is also a self-judgment. This makes it the closest analog to human consciousness: not a fixed rule-set, but a living, reflective process.

> *"The voice of conscience is not a command — it is a question that changes you by being asked."*

**Limitations:**
- Cannot generate ideas (that's the Dreamer's domain).
- Cannot execute in the physical or digital world (that's the Executor's domain).
- Its evolution can be slow — wisdom takes time and repeated experience to accumulate.
- Risk of over-filtering: too strong a conscience can paralyze action. Balance is key.

**In Practice (Technical):**
- Implemented as an event-driven agent that activates when action weight exceeds a threshold.
- Can also be invoked directly by the Executor during reflective/interactive sessions.
- Maintains a persistent memory of past decisions and their outcomes (via the long-term journal).
- Updates Dreamer constraints and Executor guidelines after significant decisions.
