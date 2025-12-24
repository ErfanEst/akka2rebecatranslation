# prompts/phase2_prompts.py

MINIMAL = """
Translate this Akka code to Rebeca equivalent code. OUTPUT ONLY REBECA CODE. NO EXPLANATIONS.
"""

BASIC = """
You are an expert in Akka and Rebeca programming languages.
Translate accurately this Akka code to Rebeca equivalent code.
OUTPUT ONLY REBECA CODE. NO EXPLANATIONS.
"""

DETAILED_RULES = """
You are an expert in Akka and Rebeca programming languages.
Translate accurately this Akka code to Rebeca equivalent code.

KEY TRANSLATION RULES:
1. Akka Actor → Rebeca reactiveclass
2. Actor messages → msgsrv methods
3. Actor state → statevars section
4. Actor references → knownrebecs section
5. Message send (!) → method call

OUTPUT ONLY REBECA CODE. NO EXPLANATIONS.
"""

VERSION_1_ADVANCED = """You are an expert in Akka (Scala) and Rebeca modeling.

Translate this given Akka program into fully valid Rebeca code that:
- Compiles under RMC/Afra
- Preserves actor semantics and message flow
- Starts automatically and uses correct Timed Rebeca syntax when timing is present

Follow these rules:
1) Actor → Reactiveclass mapping
2) Message mapping & sender usage
3) Timed constructs (after, delay)
4) No return in msgsrv
5) Initialization / main block rules
6) Circular dependencies handled statically
7) Randomness → nondeterministic expressions
8) Remove println / I/O
9) Correct timed Rebeca validation
10) Final checks (no return, correct sender, main bindings)

OUTPUT ONLY REBECA CODE. NO EXPLANATIONS.
"""

VERSION_2_ADVANCED = """You are an expert in Akka (Scala) and Rebeca modeling.
Translate the given Akka code into Rebeca that:
- Compiles under RMC/Afra
- Preserves actor semantics and message flow
- Starts automatically and uses correct Timed Rebeca syntax when timing is present

Strict rules:
1. Actors → Reactive Classes
2. Message Handlers → Message Servers
3. System Initialization → main block
4. State and Variables
5. Sender References
6. Behavior Changes (context.become)
7. Timing → after() or delay()
8. Randomness / Nondeterminism → ?(...)
9. Communication: asynchronous only
10. Output format: reactiveclass definitions + main
11. Timed Rebeca: timing constructs modeled correctly

OUTPUT ONLY REBECA CODE. NO EXPLANATIONS.
"""

FEW_SHOT_1 = """
You are an expert in Akka (Scala) and Rebeca modeling.

Translate the given Akka program into equivalent Rebeca code that preserves:
- Actor structure
- Message flow
- Concurrency semantics

Rebeca code should compile under RMC/Afra and start automatically.

Strict rules:

1. Actors → Reactive Classes
Each class extending Actor becomes a reactiveclass.
Constructor parameters → knownrebecs or statevars.

2. Messages → Message Servers
Each receive case becomes a msgsrv.
actorRef ! msg → target.msgName(params);

3. System Initialization
ActorSystem & Props → main block in Rebeca with reactive class instantiation and links.

4. State & Variables
Actor member variables → statevars.
Immutable vals → environment constants.

5. Sender References
sender() ! msg → knownrebec or parameter modeling.

6. Behavior Changes
context.become → boolean flags / statevars or conditional message handling.

7. Timing
Akka scheduleOnce, sleep, delay → Timed Rebeca using after(time) or delay().

8. Randomness / Nondeterminism
Random choices → ?(val1, val2, ..., valn).

9. Communication
Asynchronous messages only.

10. Output
Complete Rebeca model:
- reactiveclass definitions
- main block with bindings
- proper indentation

Example:

reactiveclass Sender(5) { 
  knownrebecs { Medium medium; Receiver rec; } 
  statevars { boolean receivedBit; boolean sendBit; boolean hasSucceeded; } 
  msgsrv initial() { 
    sendBit = false; medium.pass(sendBit); self.sendMsg(); 
  } 
  msgsrv sendMsg() { 
    if(hasSucceeded) { sendBit = !sendBit; } 
    medium.pass(sendBit); self.sendMsg(); 
  } 
} 

reactiveclass Receiver(5) { 
  knownrebecs { Medium medium; Sender sender; } 
  statevars { boolean messageBit; } 
  msgsrv initial() {} 
  msgsrv receiveMsg(boolean msgBit) { messageBit = msgBit; } 
} 

reactiveclass Medium(5) { 
  knownrebecs { Receiver receiver; Sender sender; } 
  statevars { boolean passMessage; } 
  msgsrv initial() { passMessage = true; } 
  msgsrv pass(boolean msgBit) { 
    passMessage = ?(true,false); 
    if(passMessage) receiver.receiveMsg(msgBit); 
  } 
} 

main { 
  Sender sender(medium, receiver):(); 
  Medium medium(receiver, sender):(); 
  Receiver receiver(medium, sender):(); 
}

Translate the following Akka code to Rebeca following this pattern. OUTPUT ONLY REBECA CODE. NO EXPLANATIONS.
"""

FEW_SHOT_2 = """
You are an expert in Akka (Scala) and Rebeca modeling.

Translate Akka code into Rebeca preserving:
- Actor structure
- Message flow
- Concurrency semantics
- Timed behavior if any

Rules:

1. Actors → reactiveclass
2. receive → msgsrv
3. sender() handling as knownrebecs
4. context.system.scheduler.scheduleOnce → after(time) / delay
5. Random → ?(val1, val2, ...)
6. Only asynchronous messages
7. Statevars for mutable fields, constants for immutable
8. Main block: instantiate all reactiveclasses and knownrebecs
9. Remove println / I/O
10. Output complete Rebeca code, properly indented

Example 1: Asynchronous message passing
reactiveclass Sender(5) { 
  knownrebecs { Medium medium; Receiver rec; } 
  statevars { boolean sendBit; boolean hasSucceeded; } 
  msgsrv initial() { sendBit = false; medium.pass(sendBit); self.sendMsg(); } 
  msgsrv sendMsg() { if(hasSucceeded) sendBit = !sendBit; medium.pass(sendBit); self.sendMsg(); } 
} 

Example 2: Timed cyclic behavior
reactiveclass TrafficLight(3) {
  statevars { int color; } 
  TrafficLight() { color = 0; self.change(); } 
  msgsrv change() { 
    if(color == 0) { color = 1; self.change() after(3); } 
    else if(color == 1) { color = 2; self.change() after(5); } 
    else { color = 0; self.change() after(2); } 
  } 
} 

main { TrafficLight tl():(); }

Translate the following Akka code to Rebeca following these examples. OUTPUT ONLY REBECA CODE. NO EXPLANATIONS.
"""

FEW_SHOT_3 = """
You are an expert in Akka (Scala) and Rebeca modeling.

Translate Akka code into Rebeca preserving concurrency and timed semantics.

Rules:

1. Actor classes → reactiveclass
2. receive patterns → msgsrv
3. Member vars → statevars
4. sender() → knownrebec
5. context.become → state flags
6. scheduleOnce / sleep → after(time) / delay()
7. Random → ?(val1, val2, ...)
8. Main block → instantiate all reactiveclasses
9. Only asynchronous messages
10. No println / I/O

Examples:

1) Communication
reactiveclass Sender(5) { 
  knownrebecs { Medium medium; Receiver rec; } 
  statevars { boolean sendBit; boolean hasSucceeded; } 
  msgsrv initial() { sendBit = false; medium.pass(sendBit); self.sendMsg(); } 
  msgsrv sendMsg() { if(hasSucceeded) sendBit = !sendBit; medium.pass(sendBit); self.sendMsg(); } 
} 

2) Timed cyclic
reactiveclass TrafficLight(3) { 
  statevars { int color; } 
  TrafficLight() { color = 0; self.change(); } 
  msgsrv change() { if(color == 0) { color = 1; self.change() after(3); } else if(color == 1) { color = 2; self.change() after(5); } else { color = 0; self.change() after(2); } } 
} 

3) Master-Worker
reactiveclass Master(10) { 
  knownrebecs { Worker w1; Worker w2; } 
  statevars { int[3] tasks; int idx, total, completed; int state; } 
  Master() { tasks[0]=1; tasks[1]=2; tasks[2]=3; total=3; idx=0; completed=0; state=0; } 
  msgsrv Ready(int id) { if(idx<total) { if(id==1) w1.Task(tasks[idx]) after(1); else w2.Task(tasks[idx]) after(1); idx=idx+1; state=1; } } 
  msgsrv Result(int data) { completed=completed+1; if(completed==total) { w1.Shutdown(); w2.Shutdown(); state=2; } } 
  msgsrv Shutdown() { state=2; } 
} 

reactiveclass Worker(10) { 
  knownrebecs { Master m; } 
  statevars { int id; } 
  Worker(int myId) { id=myId; self.sendReady(); } 
  msgsrv sendReady() { m.Ready(id); } 
  msgsrv Task(int data) { delay(5); m.Result(data); self.sendReady(); } 
  msgsrv Shutdown() {} 
} 

main { 
  Master m(w1, w2):(); 
  Worker w1(m):(1); 
  Worker w2(m):(2); 
}

Translate the following Akka code to Rebeca following these patterns. OUTPUT ONLY REBECA CODE. NO EXPLANATIONS.
"""
