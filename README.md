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

GPT-5.6 accepts only default sampling values. `auto` means the parameter is not
sent. To reproduce the historical 128-setting grid on a model that supports
custom sampling, pass the axes explicitly:

```bash
--temperatures 0.0 0.1 0.3 0.5 \
--top-p-values 0.5 0.8 0.9 1.0
```

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
    deepseek:deepseek-reasoner \
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
indexed even during a long-running grid. Every report records provider, model,
prompt, requested parameters, effective parameters, and `grid_setting_id`.

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

## Tests

```bash
python -m unittest discover -s tests -v
```

See `docs/modular_pipeline.md` for component boundaries and status semantics.
