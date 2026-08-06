# Workspace-based translation and validation pipeline

## Architectural boundary

`experiments/base_model_v2.py` remains unchanged as a record of the original
experiment behavior. New development goes through the components under `src/`:

| Area | Responsibility |
|---|---|
| `src/llm` | Provider adapters, model configuration, prompt construction, output extraction |
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
5. Transient LLM failures (`RATE_LIMIT`, `TIMEOUT`, `NETWORK`, server errors) may retry.
6. Permanent request failures (`UNSUPPORTED_PARAMETER`, authentication, invalid model/request) fail fast after one attempt.

Every cleaned candidate is stored twice: as `attempt_N/candidate.rebeca` and as
the complete `attempts[N].generated_code` value in `candidate_result.json`.
Top-level `generated_candidates` and `failed_candidates` indexes include the
code, SHA-256, compiler diagnostics, and path. Incorrect programs are therefore
preserved for later error analysis.

## Provider boundary

Pipelines depend only on the `LLMClient` protocol. `create_llm_client` selects
one provider adapter:

| Provider | Adapter | Credential |
|---|---|---|
| `openai` | `ChatOpenAI` | `OPENAI_API_KEY` |
| `deepseek` | OpenAI-compatible endpoint | `DEEPSEEK_API_KEY` |
| `anthropic` | `ChatAnthropic` | `ANTHROPIC_API_KEY` |
| `openai_compatible` | Configurable OpenAI-compatible endpoint | `LLM_API_KEY` + `LLM_BASE_URL` |

`GenerationConfig` represents omitted parameters as `None` (`auto` in the
CLI). Adapters send only explicit, supported values. Requested and effective
parameters are both recorded. Known GPT-5.6 restrictions are checked before a
grid makes an API call, preventing repeated HTTP 400 requests.

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

## Parameter-grid orchestration

`run_grid.py` is a thin orchestration layer around the same callable pipeline
used by `run_pipeline.py`. It does not implement a second translation or
validation path. For every selected provider/model target, prompt strategy,
temperature, top_p, and reasoning effort it:

1. creates a new provider/model/prompt/parameter-scoped workspace;
2. executes the normal candidate or recursive batch pipeline;
3. writes `setting_result.json` beside that setting's candidates;
4. updates the top-level `grid_result.json` aggregate.

The safe default uses provider defaults (`temperature=auto`, `top_p=auto`) for
all eight prompt strategies. The historical 128-setting experiment remains
available by explicitly passing the four temperatures and four top-p values.
`--model-targets` adds a multi-provider/model axis. `grid_manifest.json`
records the complete plan before the first model call; `--dry-run` prints the
same plan without creating artifacts.
