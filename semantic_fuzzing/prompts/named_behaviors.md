# Enabled backend extension: named Akka behaviors v1

This section overrides only the earlier prohibition on behavior switching and
the prohibition on adding observation fields, for the subset below. Stash, the
Akka FSM library, timers, routers, EventBus and unsupported numeric types remain
outside this extension. Do not infer support for them from this section.

Supported actors extend Actor directly. Their initial `def receive` and other
behaviors are parameterless `def name: Receive` methods whose bodies are literal
partial functions. Every `context.become` target must be one of these named
methods. `discardOld` must be a literal true/false (default true). Support
`context.unbecome()` and nested pushes with `discardOld = false`. Anonymous,
parameterized, dynamically constructed, aliased and composed behaviors are not
covered. Actor restart/stop and supervision are not covered.

The runtime continues to execute the ORIGINAL Akka context operations. It adds
observable scalar fields to record the behavior stack after every handler.
The Rebeca model MUST include these exact int fields for every switching actor:

    fuzzBehaviorMode
    fuzzBehaviorDepth
    fuzzBehaviorSlot0
    fuzzBehaviorSlot1
    fuzzBehaviorSlot2
    fuzzBehaviorSlot3

Initial mode and depth are 0; all four slots are -1. Mode 0 is receive. Other
named Receive methods are sorted lexicographically and assigned IDs 1, 2, ... .
The depth counts overrides above the original receive, not receive itself.

Push(mode, discard): if discard and depth > 0, pop once first. Check depth < 4;
write mode into Slot[depth], increment depth, then set Mode to mode. Thus
become(active) at depth 0 creates one override; unbecome subsequently restores
the original receive. become(active, false) preserves the previous override.

Pop: if depth > 0, decrement it and clear the removed slot to -1. Set Mode to
Slot[depth-1] when depth > 0, otherwise to 0. Popping an empty stack is a no-op.
Four overrides are the explicit verification bound. Never wrap, clamp, discard
older modes, or silently handle an overflow; use assertion(depth < 4) when
pushing. Akka instrumentation fails on overflow, so it cannot establish a match.

Dispatch each message according to the mode AT HANDLER ENTRY. A mode change
inside that handler affects only the next message. Use if/else-if or a local
entry-mode snapshot; do not run another mode's branch after changing Mode.
Preserve guards and first-match ordering within each behavior. A message absent
from a behavior is not permission to run another behavior's handler. The current
observation workflow does not certify unhandled-message/dead-letter semantics.

Implement the bounded stack with the six scalar fields, not additional actor
messages. Pure synchronous helper methods for push/pop are permitted. Preserve
all original scalar state and sends. Missing or wrong observation fields are
semantic mismatches even if the final application value happens to agree.

Do not add these fields to actors that never switch behavior. These fields and
their exact initialization are runtime observation data; they are not new source
protocol messages or a change to the original Akka behavior.
