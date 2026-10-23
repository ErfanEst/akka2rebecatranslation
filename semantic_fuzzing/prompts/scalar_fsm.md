# Enabled backend extension: untimed scalar FSM v1

This overrides earlier FSM prohibitions ONLY for Akka Classic FSM[Phase, Int].
States are named singleton objects used in literal untimed when(State) clauses.
startWith(State, initialInt) initializes the machine. goto targets must be named
declared states. No timers, Stash, stop/restart/supervision, subscriptions,
structured state data, or external side effects are supported.

Execute the same Event message handlers and guards in their original order:
try the current state's when handlers, then whenUnhandled. Preserve goto, stay,
using, and onTransition semantics. Do not replace the source with a different FSM.
Use the FSM state AT HANDLER ENTRY for dispatch; changing state must not execute
another state's handler for the same message. `using` supplies the next data;
otherwise preserve current data. `stay` normally does not notify transitions;
`goto` notifies even when targeting the same state. During onTransition,
stateData is the old data and nextStateData is the proposed new data. Preserve
all sends, their sender identity and order, and scalar user state changes.
Commit the target state/data after callbacks, within the same Rebeca handler.

The instrumenter runs the REAL Akka FSM and records after its aroundReceive
returns, so callbacks and their sends are included in that event's post-state.
Every FSM actor's Rebeca model MUST have two int state variables:
  fuzzFsmState: state names in all when clauses sorted lexicographically,
                numbered from zero. Initialize to startWith's state ID.
  fuzzFsmData: exact Int stateData, initialized to startWith's data expression.
These are observation fields, not new messages. Keep all original supported
scalar state variables too. Do not add behavior-stack fields for FSM actors.
Never silently encode collections, AnyRef, Either, BigDecimal or floating-point
values as Int. Unsupported source features must not be erased to pass checking.

The checker validates bounded trace/state/mailbox agreement, not equivalence
for all inputs. FSM branch coverage is not instrumented in this version.
