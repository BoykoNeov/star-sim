---
name: no-parallel-agents-without-permission
description: "Never launch multiple agents in parallel without the user's explicit order or permission."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 58010da9-37e2-4751-a038-7052b9196a7f
---

Never launch multiple agents/subagents in parallel without the user's explicit
order to do so, or without first asking for permission.

**Why:** The user wants direct control over when parallel fan-out happens — it
spends tool/token budget and spawns concurrent work they may not have intended.

**How to apply:** Default to a single agent or doing the work inline. Only run
multiple agents concurrently when the user explicitly says to (e.g. "spawn N
agents") or after I ask and they approve. This is a hard gate that overrides any
inclination to parallelize for speed. When the user *does* explicitly order it,
the concurrent-with-briefing-and-debrief rule still applies.
