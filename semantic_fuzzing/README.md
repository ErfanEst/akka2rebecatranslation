# Translation With Semantic Differential Fuzzing

راهنمای فارسی نصب و اجرا: [GUIDE_FA.md](GUIDE_FA.md).
گزارش اجرای واقعی و محدودیت‌ها: [EXECUTION_REPORT_FA.md](EXECUTION_REPORT_FA.md).
راهنمای افزونهٔ محدود `become`/`unbecome`: [NAMED_BEHAVIORS_FA.md](NAMED_BEHAVIORS_FA.md).

This is a new, opt-in pipeline. All pre-existing translation code, evaluators,
experiment scripts, tests, and dependency files are unchanged. The integration
calls the real `semantic-differential-fuzzing` engine in its sibling checkout;
it does not copy or reimplement the engine's comparison algorithms.

## Pipeline

1. Supply an original Akka source and a candidate Rebeca model, or translate
   an Akka source with `FuzzingTranslator` and the full `handbook_rebeca` profile.
2. Check syntax/types with RMC and require fresh generated C++ artifacts. Reject
   invalid models before extraction or fuzzing; save `SYNTAX_ERROR` / `NOT_RUN`.
3. Extract the Akka interface and instrument scalar state, branches, and complete
   post-handler mailboxes using the engine's ScalaMeta tools.
4. Run the engine's full semantic differential campaign: seeded scenarios,
   message/value coverage, parameter domains, bound sequences, Akka execution,
   initial-mailbox alignment, exhaustive RMC trace export, state/mailbox/trace
   comparison, branch feedback between cases, and mutation classification.
5. Save the complete engine reports and an integration `result.json`.
6. In translation mode, send the original source, previous candidate, and
   counterexample through the handbook repair prompt. A translation succeeds
   only after a nonempty trusted bounded match.

This path uses neither the old benchmark-specific semantic evaluators nor the
broken custom compiler-JAR launcher. RMC performs candidate compilation. The
official compiler 2.25 JAR is not needed for this path.

## Prerequisites

- Both repository checkouts, with the fuzzing engine at the configured path.
- Python 3.10+; translation mode also needs the translation project's Python packages.
- Java, sbt 1.12.13, g++, and the official RMC 2.14 JAR.
- A usable OpenAI API key only for live `translate`, never for `check` or `batch`.

Validated engine commit: `3086cba00497848d2a999ed6f219a6e6fca2fa13`.
Each result records the actual engine commit, input hashes, configuration, and
stage commands. Use the recorded commit when reproducing an experiment.

In the prepared cloud environment:

```bash
source /workspace/cloud-setup/activate.sh
cd /workspace/akka2rebecatranslation
```

## Check a Candidate

The bundled `cloud.example.json` is specifically configured for the engine's
session-workflow benchmark. Run it from this repository:

```bash
python -m semantic_fuzzing --config semantic_fuzzing/cloud.example.json check \
  --akka-source ../semantic-differential-fuzzing/examples/akka/SessionWorkflow.scala \
  --candidate ../semantic-differential-fuzzing/examples/session_workflow.rebeca \
  --mutant ../semantic-differential-fuzzing/examples/session_workflow_mutant_wrong_submit_id.rebeca \
  --output /tmp/session-fuzz-run
```

Use a fresh output path on every run. Existing output directories are rejected.
Multiple `--akka-source` arguments support multi-file programs. `.txt` source
files are staged as `.scala`; source basenames must be unique.

For your own benchmark, create a configuration JSON with `fuzzing_repo` and
`rmc_jar`. Remove the session-specific `generation_spec` or provide your own.
All configuration paths are relative to the JSON file. Executable names such
as `java`, `sbt`, and `g++` use PATH; executable paths are relative to the JSON.
CLI input/output paths are relative to the current working directory.

Supported configuration fields:

| Field | Default / Meaning |
| --- | --- |
| `fuzzing_repo`, `rmc_jar` | Required paths |
| `sbt`, `java`, `cxx` | Executable names or paths |
| `case_count`, `message_count`, `start_seed` | 3, 10, 1 |
| `trace_bound`, `run_millis` | 40 events, 1000 milliseconds |
| `model_timeout_seconds` | 120 per model |
| `stage_timeout_seconds` | 600 for extraction and each RMC generation |
| `campaign_timeout_seconds` | 3600 for the whole campaign |
| `coverage_mode` | `message`, `sender-message`, or `random` |
| `value_coverage` | `boundary` or `random` |
| `bootstrap_sender_policy` | `abstract-external` or `exact` |
| `generation_spec` | Optional engine domain/sequence specification |
| `first_case_scenario` | Optional exact first-case replay |
| `initial_priority_branches` | Optional list of engine branch-target objects |

Output includes copied inputs, isolated Scala build projects, instrumented
sources, generated baseline models, stage logs, and the original campaign
tree. Neither source checkout is modified by a check. Timeouts terminate the
campaign's child processes as well as its Python parent (Linux/POSIX).

## Archived Results and Batch Checks

Replace `--candidate` with `--translation-result path/to/example_result.json`
to validate `final_code` from an existing successful BaseModelV2 result. Its
original success means the old validator accepted it, not semantic equivalence.
The new pipeline independently evaluates it. Failed/empty translation records
are rejected; the original JSON and benchmark files are never overwritten.

Batch manifests require explicit pairing to avoid comparing a translation with
the wrong original program. Paths are relative to the manifest:

```json
{
  "jobs": [
    {
      "akka_sources": ["sources/Example.scala"],
      "translation_result": "results/Example_result.json"
    },
    {
      "akka_sources": ["sources/Another.scala"],
      "candidate": "models/Another.rebeca",
      "mutants": [
        {
          "source": "models/Another_mutant.rebeca",
          "activation_policy": "any",
          "activation_targets": [{"receiver": "target", "message": "Update"}]
        }
      ]
    }
  ]
}
```

```bash
python -m semantic_fuzzing --config /path/to/fuzzing.json batch \
  --manifest /path/to/jobs.json --output /tmp/fuzz-batch
```

Jobs run sequentially. An error in one job is recorded without losing later
jobs. `batch_summary.json` is updated after every job. Mutants receive stable
internal names `mutant_1`, `mutant_2`, etc. All mutation outcomes remain in the
campaign report; a killed mutant does not reject a matching candidate.

## New Translations

For runnable, documented derivatives of five research kernels, use
`python -m semantic_fuzzing.validated_batch --cases 50 --output ../runs/validated/group-01`.
See [the validated-input guide](benchmarks/validated/README_FA.md) for adaptation
boundaries, the audit of all 50 original entries, and fixture-based verification.

For the uploaded 50-source research archive, run groups of five with
`python -m semantic_fuzzing.research_batch --group 1 --dry-run`, then provide
`--output ../runs/research50/group-01` instead of `--dry-run` to translate.
The runner requests 50 random scenarios per validation attempt by default.
Compatibility warnings are printed and saved before API calls; incompatible
examples are attempted, not silently skipped. Full original source files are
used, not extracted/adapted kernels. See [the Persian batch guide](benchmarks/research50/README_FA.md).

`FuzzingTranslator` subclasses `BaseModelV2`, reusing its LLM client, retry loop,
prompt logs, and file/directory runners. It now defaults to the `handbook_rebeca`
profile as well as the fuzzing validation gate. Existing historical experiment
entry points still use their original behavior; invoke the integrated entry
point explicitly.

The profile combines the detailed translation contract in
`prompts/handbook_rebeca.md` with reference text from the user-supplied
52-page Handbook of Rebeca (2025-04-05) and 8-page Rebeca 2.1 manual (2016-12-06).
Both complete UTF-8 extractions are committed under `prompts/`. The source PDF
hashes, text hashes, page counts and extraction method are in `prompts/sources.json`.
PDF drawings/screenshots are not embedded in this text-only prompt; extracted
captions and any extractable figure text are retained. No document is fetched
from the network at runtime. The default `handbook_reference_mode` is `compact`:
all translation rules, the complete manual, and handbook PDF pages 11-18
(printed pages 5-12, Core syntax and the complete bridge listing) are sent.
Other handbook pages remain in the repository but are omitted from requests.
Set `"handbook_reference_mode": "full"` in the translation JSON to restore the
original complete appendices. Unknown modes fail before an API request.

The contract covers source topology, Core syntax, constructors, message and
sender identity, scalar state, FIFO queues, atomicity, capacity bounds, sequence
semantics, compiler diagnostics, and counterexample-driven repair. It separates
Core Rebeca from the timed/probabilistic/priority extensions in the references.
It also explains known draft/legacy syntax inconsistencies. Source comments and
reference exercises are treated as data, not as new instructions.

Every initial and retry API call carries the full system prompt. Retry calls also
retain the original Akka source, including literal braces, alongside the previous
translation and diagnostics. Validation bounds and optional domain/sequence or
replay JSON are included as test context. Prompt logs store the full payload;
result JSON includes `prompt_profile` and `prompt_metadata`, including the
effective system prompt SHA-256 and character count.

`handbook_rebeca` is the default even if an old configuration contains
`system_prompt`, `initial_prompt_template`, or `retry_prompt_template`: these old
prompt fields do not bypass the requested replacement. To deliberately run an
older/custom prompt experiment, explicitly select `"prompt_profile": "custom"`.
Unknown profile names fail rather than silently falling back.

The compact system prompt has 69,079 characters versus 177,138 in full mode,
a 61% character reduction before Akka source and feedback. These are not token
counts; actual usage depends on the tokenizer and request. Metadata records
reference mode, included PDF pages and content hashes. All 16 translation-rule
sections are preserved verbatim. Omitted material includes front matter,
extended analysis tutorials, case studies, timed/probabilistic and advanced
chapters, and bibliography. Their relevant restrictions remain in the contract.
Equal translation quality is not guaranteed by text tests: compare both modes
on the same sources, seeds, bounds and model to assess accuracy.
The profile defaults to `gpt-4o`; use a model with adequate context
and leave room for the input and output. Known legacy GPT-4 8K/32K model names
are rejected for this profile. Other model limits still apply; the pipeline does
not silently shorten the documents to fit. No API key belongs in a config file.

Ready-to-use example in this cloud environment:

```bash
python -m semantic_fuzzing --config semantic_fuzzing/cloud.example.json translate \
  --akka-source ../semantic-differential-fuzzing/examples/akka/SessionWorkflow.scala \
  --translation-config semantic_fuzzing/translation.handbook.example.json
```

For GPT-5.6 Sol with medium reasoning, use the bundled translation config:

```bash
python -m semantic_fuzzing --config semantic_fuzzing/examples/configs/simple_counter.json translate \
  --akka-source semantic_fuzzing/examples/akka/SimpleCounter.scala \
  --translation-config semantic_fuzzing/translation.gpt-5.6-sol-medium.json \
  --output ../runs/simple-counter-gpt-5-6-sol-medium-01
```

The API model name is `gpt-5.6-sol`; the longer
`openai-gpt-5.6-sol-standard-2026-08-06` identifier belongs to a model/rate
catalog and is not sent as the OpenAI model parameter. Reasoning mode passes
`reasoning_effort=medium`. With the pinned client it uses the required
`temperature=1` and rejects `top_p`, frequency penalty, and presence penalty
instead of silently sending incompatible sampling controls.

For a deliberately custom experiment, supply the usual BaseModelV2 configuration
as JSON with `prompt_profile` set to `custom`. Example:

```json
{
  "experiment_name": "my_experiment",
  "prompt_profile": "custom",
  "model": "gpt-4o",
  "temperature": 0.1,
  "max_retries": 3,
  "system_prompt": "Translate Akka Classic to Core Rebeca. Preserve static actor names, message names, parameters and observable scalar state names.",
  "initial_prompt_template": "{akka_code}",
  "retry_prompt_template": "Previous translation:\n{previous_code}\nValidation feedback:\n{errors}\nReturn corrected Rebeca code."
}
```

```bash
python -m semantic_fuzzing --config /path/to/fuzzing.json translate \
  --akka-source /path/to/Example.scala \
  --translation-config /path/to/translation.json
```

CLI results use a fresh run directory under
`experiments/results/semantic_fuzzing/<experiment_name>/run-*`, or the fresh path
specified by `translate --output`. Each validation attempt also has a unique
directory. Direct Python directory/grid runners still retain BaseModelV2's
experiment-name behavior; use a new experiment name for each run. `semantic_checks` in the
result links to each attempt's full report. `validation_success`/`success`
now mean a bounded semantic match. They do not assert equivalence.

The original retry loop retries failed validations, including infrastructure
errors; fix toolchain errors before launching large paid experiment grids.
For the existing directory/grid workflow, import `FuzzingTranslator` from
`semantic_fuzzing.translator`, construct it with `FuzzingPipeline(config)` and
the existing experiment configuration, and call `run_on_directory(...)`.

## Outcomes and Limits

| Status | CLI exit | Meaning |
| --- | --- | --- |
| `BOUNDED_MATCH` | 0 | Every requested candidate case produced a trusted, nonempty matching trace |
| `MISMATCH` | 1 | Trusted trace/state/mailbox mismatch or queue overflow |
| `INCONCLUSIVE` | 2 | Empty, untrusted, incomplete, or missing observations |
| `ERROR` | 3 | Toolchain, generation, compilation, timeout, or runner error |
| `SYNTAX_ERROR` | 4 | RMC frontend rejected a candidate/mutant; semantic checking did not run |

The full reports preserve coverage gaps, sequence coverage, mismatch evidence,
and mutation results. Partial coverage can still be a bounded match; it is not
full coverage or a proof of equivalence. `semantic_equivalence` remains
`NOT_ESTABLISHED`, including for successful runs. A real counterexample takes
precedence over an error in another case, which is still retained in reports.

Engine limitations remain: Scala 2.13 Akka Classic, static actors, supported
scalar state and message parameters, and corresponding names between Akka and
Rebeca. Unsupported dynamic creation or differently named actors/state require
separate work; the adapter does not silently rewrite either input.

## Tests

```bash
python -m unittest -v semantic_fuzzing.test_pipeline semantic_fuzzing.test_handbook_prompt semantic_fuzzing.test_workflow
```

These tests cover verdict trust, empty/missing traces, queue overflow, mutant
classification, archived-result pairing, output isolation, and the actual
translation retry loop with a mocked LLM. The command in "Check a Candidate"
exercises the real Scala, Java, C++, and Python pipeline without an API key.
The handbook tests additionally check complete document inclusion, page counts,
hashes, actual first/retry message payloads, literal source braces, full prompt
logs, replacement of stale prompt fields, result metadata, and profile selection.

Verified in the cloud environment with the supplied session configuration:

- Two candidate cases matched four observed events each, including exact
  receiver state and all-actor FIFO mailboxes.
- The wrong-submit-ID mutant was killed by `STATE_MISMATCH` in both cases.
- Parameter-value coverage was 6/6 and sequence coverage was 1/1.
- Passing that mutant as the candidate yielded `MISMATCH`, not success.
- A batch with a missing first candidate continued to the second job and
  retained both its `ERROR` and the second job's `MISMATCH`.

Live `gpt-4o` translation succeeded on SessionWorkflow after the environment
credential was replaced (`live-20261021-124105`). The first response passed RMC
syntax/type checking and both real fuzzing cases (seeds 17 and 18), with four
observed events per case and matching state/mailboxes. The final status was
`BOUNDED_MATCH`, exit 0, in about 45.5 seconds. No mock, fixture substitution or
manual candidate edit was used in this run. Its complete prompt, final Rebeca,
campaign and result JSON are preserved under `/workspace/execution-evidence`.

An earlier live run (`live-20261021-123138`) failed with HTTP 401,
`token_invalidated`; its records remain as historical evidence. The separate
three-attempt retry test used scripted LLM responses with real validators;
live retry behavior was not needed in the successful first-attempt run.
See the Persian execution report for details and coverage limitations.
