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

## Tests

```bash
python -m unittest discover -s tests -v
```

See `docs/modular_pipeline.md` for component boundaries and status semantics.
