# Akka2Rebeca Translation Pipeline

This repository translates Akka programs to Rebeca and validates both compiler
acceptance and benchmark semantics. The modular pipeline under `src/` replaces
the experiment-oriented responsibilities of `BaseModelV2`; that legacy class is
kept only as a behavior reference.

```text
Akka -> prompt -> LLM -> clean output -> RMC 2.14 -> generated C++
     -> g++ -> model checker -> result.xml -> parser -> evaluator -> report
```

Every candidate and retry gets an isolated workspace. The shared files
`benchmarks/temp.rebeca` and `validation_output/temp.txt` are not used.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` or export the API key:

```text
OPENAI_API_KEY=your-key-here
```

Other adapters use `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`, or the generic
`LLM_API_KEY` plus `LLM_BASE_URL`. Provider clients are created lazily, so unit
tests do not require credentials.

## Run

Syntax plus semantic validation:

```bash
python run_pipeline.py data/input_akka_codes/simple_examples/simpleCounter.txt \
  --provider openai \
  --model gpt-5.6-sol \
  --temperature auto \
  --top-p auto \
  --reasoning-effort medium \
  --benchmark simple_counter \
  --prompt-strategy basic
```

Syntax-only validation:

```bash
python run_pipeline.py path/to/program.scala --syntax-only
```

Backend failures are separate from infrastructure failures. If RMC accepts a
candidate but the generated C++ does not compile, the candidate is reported as
`CODEGEN_FAIL`. Opt in to oracle-free backend repair with:

```bash
python run_pipeline.py path/to/program.scala \
  --benchmark simple_ping_pong \
  --max-codegen-repairs 1 \
  --max-attempts 3
```

The first request of each codegen-repair cycle receives the complete generated
C++ compiler diagnostic and the previous Rebeca candidate. It does not receive
benchmark-oracle output. Baseline experiments remain unchanged because
`--max-codegen-repairs` defaults to `0`.

Validate an already-generated Rebeca candidate without constructing an LLM
client or making an API request:

```bash
python validate_candidate.py path/to/candidate.rebeca \
  --benchmark simple_ping_pong \
  --workspace-root workspace/offline_candidate_check
```

The resulting `offline_validation_result.json` records
`"llm_request_count": 0` and distinguishes `SYNTAX_FAIL`, `CODEGEN_FAIL`,
semantic outcomes, and `INFRA_ERROR`.

Recursive batch execution accepts `.txt` and `.scala` files:

```bash
python run_pipeline.py data/input_akka_codes/simple_examples \
  --benchmark simple_counter
```

## Run the complete prompt/parameter grid

`run_grid.py` supports a Cartesian product of providers, models, prompts,
sampling parameters, and reasoning effort. The safe default omits sampling
parameters and uses provider defaults:

```text
8 prompts × 1 temperature(auto) × 1 top_p(auto) = 8 settings per model
```

Preview all settings and paths without calling the model or creating files:

```bash
python run_grid.py \
  data/input_akka_codes/simple_examples/simplePingPong.txt \
  --candidate-id simplePingPong \
  --benchmark simple_ping_pong \
  --dry-run
```

Run GPT-5.6 with two researched prompts and provider-default sampling:

```bash
python run_grid.py \
  data/input_akka_codes/simple_examples/simplePingPong.txt \
  --candidate-id simplePingPong \
  --benchmark simple_ping_pong \
  --provider openai \
  --model gpt-5.6-sol \
  --prompt-strategies minimal_v2 handbook_zero_shot_v1 \
  --temperatures auto \
  --top-p-values auto \
  --reasoning-efforts medium \
  --max-attempts 5 \
  --workspace-root workspace/simple_ping_pong_grid
```

The grid is resumable. Re-run the identical command with `--resume`; completed
`setting_result.json` files are skipped. If a process stopped inside one setting,
its incomplete directory is preserved with an `__interrupted_<timestamp>` suffix
before that setting is retried.

```bash
python run_grid.py ... \
  --workspace-root workspace/simple_ping_pong_grid \
  --resume
```

Model output is not guaranteed to be byte-identical even at temperature zero.
Use `--repetitions N` to represent independent samples explicitly. The default
is one, so historical setting IDs and grid sizes remain unchanged. With more
than one repetition, artifacts gain a `replicate_01`, `replicate_02`, ... level.

GPT-5.6 accepts only default sampling values. `auto` is not a numeric
temperature: it means the parameter is omitted from the API request and the
model/provider default is used. Consequently, `auto` contributes one setting,
not a temperature grid. To reproduce the historical 128-setting grid on a
model that supports custom sampling, pass the axes explicitly:

```bash
--temperatures 0.0 0.1 0.3 0.5 \
--top-p-values 0.5 0.8 0.9 1.0
```

GPT-5.1 supports an explicit `temperature` or `top_p` only in non-reasoning
mode. Its default reasoning effort is `none`, so either `auto` or an explicit
`--reasoning-efforts none` is valid. For an unambiguous GPT-5.1 temperature
grid:

```bash
--provider openai \
--model gpt-5.1-2025-11-13 \
--temperatures 0.0 0.1 0.3 0.5 \
--top-p-values auto \
--reasoning-efforts none
```

Changing both `temperature` and `top_p` at once is supported by the grid
runner, but a one-axis-at-a-time experiment is easier to interpret.

Run several providers/models in one experiment. Model IDs are supplied by the
caller so future GPT, DeepSeek, Claude, and compatible models do not require
pipeline changes:

```bash
python run_grid.py \
  data/input_akka_codes/simple_examples/simplePingPong.txt \
  --candidate-id simplePingPong \
  --benchmark simple_ping_pong \
  --model-targets \
    openai:gpt-5.6-sol \
    openai:gpt-5.4 \
    openai:gpt-5.1-2025-11-13 \
    deepseek:deepseek-v4-pro \
    anthropic:claude-sonnet-4-5 \
  --prompt-strategies minimal_v2 handbook_zero_shot_v1 \
  --temperatures auto \
  --top-p-values auto \
  --reasoning-efforts auto \
  --max-attempts 1 \
  --workspace-root workspace/ping_pong_multi_model
```

For another OpenAI-compatible service:

```bash
export LLM_API_KEY="..."
export LLM_BASE_URL="https://provider.example/v1"
python run_pipeline.py input.scala \
  --provider openai_compatible \
  --model provider-model-id \
  --syntax-only
```

A directory can be processed recursively with `--syntax-only`; use semantic
mode only when every selected input belongs to the same benchmark.

Defaults:

```text
RMC:  /home/erfan/Thesis/tools/rmc-2.14.jar
Java: /usr/lib/jvm/java-17-openjdk-amd64/bin/java
```

Override them with `--rmc-jar` and `--java-bin`. A timestamped workspace is
created by default; `--workspace-root` selects another new directory. Existing
candidate workspaces are never overwritten.

## Artifact layout

```text
workspace/<run>/<candidate>/
├── candidate_result.json
├── final_candidate.rebeca
├── attempt_1/
│   ├── prompt.json
│   ├── llm_response.txt
│   ├── candidate.rebeca
│   ├── rmc_stdout.log
│   ├── rmc_stderr.log
│   └── attempt_result.json
└── attempt_2/
    ├── candidate.rebeca
    ├── generated_cpp/
    └── semantic/
```

Grid artifacts add explicit provider, model, prompt, and parameter levels:

```text
workspace/<grid-run>/
├── grid_manifest.json
├── grid_result.json
└── provider_<provider>/
    └── model_<model>/
        └── <prompt_strategy>/
            └── temp<temperature>_topp<top_p>[_reasoning<effort>]/
                ├── setting_result.json
                └── <candidate>/
                    ├── candidate_result.json
                    ├── final_candidate.rebeca
                    └── attempt_N/
                        ├── prompt.json
                        ├── llm_response.txt
                        ├── candidate.rebeca
                        ├── rmc_stdout.log
                        └── rmc_stderr.log
```

`grid_result.json` is updated after every setting, so completed results remain
indexed even during a long-running grid. Its `outcome_index` maps every setting
directly to syntax, codegen, semantic, valid-attempt, and report fields;
`semantic_passes` contains the exact passing settings and report paths. Every
report records provider, model, prompt, requested parameters, effective
parameters, repetition, and `grid_setting_id`.

```bash
jq '.semantic_passes' "$GRID_ROOT/grid_result.json"

jq -r '.outcome_index[] | [
  .setting_id,
  .status,
  .syntax_valid_attempt,
  .final_codegen_status,
  .semantic_status,
  .report
] | @tsv' "$GRID_ROOT/grid_result.json" | column -t -s $'\t'
```

## Token usage and cost reporting

Every successful LLM response stores provider-reported usage and a list-price
cost estimate in both `attempt_result.json` and `candidate_result.json`:

```text
attempts[].llm.input_tokens
attempts[].llm.uncached_input_tokens
attempts[].llm.cached_input_tokens
attempts[].llm.cache_write_input_tokens
attempts[].llm.cache_status
attempts[].llm.cache_read_ratio
attempts[].llm.estimated_cache_savings_usd
attempts[].llm.output_tokens
attempts[].llm.reasoning_tokens
attempts[].llm.cost_usd
attempts[].llm.cost_status
attempts[].llm.cost_details
```

Reasoning tokens are recorded separately for analysis but are already included
in output tokens, so they are never charged twice. Candidate, setting, and grid
reports contain `usage_and_cost`; `grid_result.json` additionally contains
`usage_and_cost_by_model`. Aggregates also record cache-read/write/miss request
counts, cached-input ratio, and estimated savings against the uncached list rate.

### GPT-5.1 prompt caching

Prompt caching is provider-managed and the first eligible request is a cache
warm-up, not a cache hit. For GPT-5.1, use stable routing plus 24-hour retention:

```text
--prompt-cache-key-prefix ping-pong-gpt51-new-prompts-v1
--prompt-cache-retention 24h
```

The grid derives a different key for every model/prompt family and includes the
system-prompt hash in that key. Actual hits are determined only from
provider-reported `cached_tokens`. See `docs/gpt51_ping_pong_grid.md` for the
frozen 32-setting Ping-Pong protocol.

Show every request in a grid:

```bash
find "$GRID_ROOT" -name candidate_result.json -print0 |
while IFS= read -r -d '' REPORT
do
  jq -r --arg report "$REPORT" '
    .attempts[] |
    [
      $report,
      (.attempt_number | tostring),
      .llm.provider,
      .llm.model,
      (.llm.input_tokens // 0 | tostring),
      (.llm.output_tokens // 0 | tostring),
      (.llm.cost_usd // "unknown" | tostring),
      .llm.cost_status
    ] | @tsv
  ' "$REPORT"
done | column -t -s $'\t'
```

Show totals per model:

```bash
jq '.usage_and_cost_by_model' "$GRID_ROOT/grid_result.json"
```

Prices come from the versioned `config/model_pricing.json` snapshot. The
default snapshot covers GPT-5.6 Sol, GPT-5.4, GPT-5.1, DeepSeek V4 Flash/Pro,
and Claude Sonnet 4.5/4.6. Unknown models keep their exact token usage and use
`cost_status=PRICE_UNAVAILABLE`; add a dated provider price entry or pass a
custom snapshot with `--pricing-file`. Do not edit a snapshot after an
experiment: create a new dated file so thesis results remain reproducible.

These values are public standard API list-price estimates. Credits, negotiated
discounts, Batch/Flex/Fast tiers, regional uplifts, taxes, and separately billed
tools can make the provider invoice differ.

## Failed-code retention

Incorrect generated Rebeca is never discarded. It remains in
`attempt_N/candidate.rebeca` and is embedded directly in
`candidate_result.json`. List all failed generations with:

```bash
jq -r '.failed_candidates[] | "attempt=\(.attempt_number)\n\(.code)\n"' \
  workspace/.../candidate_result.json
```

Permanent API failures such as unsupported parameters are categorized as
`UNSUPPORTED_PARAMETER` and fail fast after one attempt. Transient rate-limit,
timeout, network, and server failures remain retryable.

Every grid also writes `grid_report.md`. It embeds all generated candidates,
full compiler logs, semantic test IDs, and detailed semantic test results. It can
be regenerated after an interrupted run with:

```bash
python3 experiments/generate_grid_report.py workspace/<grid-run>
```

## Tests

```bash
python -m unittest discover -s tests -v
```

See `docs/modular_pipeline.md` for component boundaries and status semantics.
