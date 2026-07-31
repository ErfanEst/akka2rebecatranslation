# Workspace-based translation and validation pipeline

## Architectural boundary

`experiments/base_model_v2.py` remains unchanged as a record of the original
experiment behavior. New development goes through the components under `src/`:

| Area | Responsibility |
|---|---|
| `src/llm` | Provider call, prompt construction, output extraction |
| `src/syntax` | RMC 2.14 invocation and syntax result |
| `src/pipeline` | Retry, candidate orchestration, batch isolation |
| `src/semantic` | C++ compile, model checking, existing parser/evaluator adapter |
| `src/artifacts` | Workspaces, result contracts, JSON reports |
| `src/cli` | Dependency wiring and command-line interface |

The new syntax path never invokes `compiler-2.25-jar-with-dependencies.jar`.
RMC code generation is the syntax gate. A candidate passes only when RMC exits
successfully and emits at least one C++ source file.

## Retry contract

1. Attempt 1 receives the Akka source.
2. RMC validates the cleaned candidate.
3. On failure, the next prompt receives the previous candidate and RMC error.
4. Processing stops at the first syntax-valid attempt or after `max_attempts`.
5. LLM/infrastructure failures are retained as attempt records and can be retried.

## Semantic reuse

The adapter does not change the existing semantic parser, evaluator registry,
specifications, or evaluator scripts. It reuses the C++ emitted by the syntax
stage, then performs the established steps: `g++`, model checker, XML parser,
and benchmark evaluator. This avoids a second syntax pass through the legacy
validator.

## Final statuses

| Status | Meaning |
|---|---|
| `SYNTAX_FAIL` | Attempts completed but no RMC-valid candidate exists |
| `SYNTAX_PASS` | Syntax-only run produced an RMC-valid candidate |
| `SEMANTIC_PASS` | Every semantic requirement passed |
| `SEMANTIC_FAIL` | Observable behavior contradicted one or more tests |
| `SEMANTIC_NOT_OBSERVED` | Trace evidence was insufficient, without observed failure |
| `INFRA_ERROR` | A tool, parser, evaluator, path, or provider failed |

`candidate_result.json` is the canonical report. It includes metadata, all
attempts, syntax details, semantic details, artifact paths, and final status.
