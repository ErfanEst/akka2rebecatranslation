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

## Run

Syntax plus semantic validation:

```bash
python run_pipeline.py data/input_akka_codes/simple_examples/simpleCounter.txt \
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

`run_grid.py` runs all eight built-in prompt strategies over the Cartesian
product of the shared parameter grid:

```text
8 prompts × 4 temperatures × 4 top_p values = 128 settings per input file
```

Preview all settings and paths without calling the model or creating files:

```bash
python run_grid.py \
  data/input_akka_codes/simple_examples/simplePingPong.txt \
  --candidate-id simplePingPong \
  --benchmark simple_ping_pong \
  --dry-run
```

Run the complete syntax and semantic grid:

```bash
python run_grid.py \
  data/input_akka_codes/simple_examples/simplePingPong.txt \
  --candidate-id simplePingPong \
  --benchmark simple_ping_pong \
  --model gpt-5.1-2025-11-13 \
  --max-attempts 5 \
  --workspace-root workspace/simple_ping_pong_grid
```

The default axes come from `experiments/parameter_grid.py`:

```text
temperature = 0.0, 0.1, 0.3, 0.5
top_p       = 0.5, 0.8, 0.9, 1.0
```

Use `--prompt-strategies`, `--temperatures`, and `--top-p-values` to run a
smaller subset. A directory can be processed recursively with `--syntax-only`;
use semantic mode only when every selected input belongs to the same benchmark.

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

Grid artifacts add explicit model, prompt, and sampling-configuration levels:

```text
workspace/<grid-run>/
├── grid_manifest.json
├── grid_result.json
└── model_<model>/
    └── <prompt_strategy>/
        └── temp<temperature>_topp<top_p>/
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
indexed even during a long-running grid. Every candidate report repeats the
model, prompt strategy, temperature, top_p, and `grid_setting_id` in metadata.

## Tests

```bash
python -m unittest discover -s tests -v
```

See `docs/modular_pipeline.md` for component boundaries and status semantics.
