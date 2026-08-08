# GPT-5.1 Ping-Pong Grid Protocol

This protocol is the first gated experiment for the new prompt architecture. It
runs only `simplePingPong`, preserves every generated candidate, measures actual
provider-reported cache reads, and generates a complete Markdown evidence report.

## Experimental design

- Model snapshot: `gpt-5.1-2025-11-13`
- Prompt strategies: `minimal_v2`, `handbook_zero_shot_v1`
- Temperature: `0.0`, `0.1`, `0.3`, `0.5`
- Top-p: `0.5`, `0.8`, `0.9`, `1.0`
- Reasoning effort: `none`
- Settings: 2 prompts × 4 temperatures × 4 top-p values = 32
- Syntax retry ceiling: 5 attempts per setting
- Semantic repairs: 0, so the baseline is not oracle-assisted
- Maximum possible API requests: 160; successful syntax stops retries early

`retrieved_few_shot_v1` is intentionally excluded from this first gate because
it requires a leakage-checked corpus of syntax- and semantic-verified examples.

## Cache protocol

GPT-5.1 prompt caching is automatic for eligible exact prefixes. The grid adds a
stable `prompt_cache_key` per model and prompt strategy and requests `24h`
retention. The first request for each key is the natural warm-up request; no
pre-existing cache can be guaranteed. Later requests are classified using the
API's `cached_tokens`, never by assumption.

The cache key includes a SHA-256 fragment of the actual system prompt. Editing a
prompt therefore creates a new cache family instead of silently reusing a key
from an older prompt version.

OpenAI applies a minimum cacheable-prefix size. The short `minimal_v2` prompt may
remain below that threshold for Ping-Pong and legitimately report zero cached
tokens. The handbook prompt is the main cache candidate. Do not pad prompts only
to force a cache hit; that would alter the experimental treatment.

## 1. Dry-run the exact matrix

```bash
cd "$HOME/Python Projects/akka2rebecatranslation"
source .venv/bin/activate

RUN_ID="$(date +%Y%m%d_%H%M%S)"
GRID_ROOT="$PWD/workspace/ping_pong_gpt51_new_prompts_${RUN_ID}"

python3 run_grid.py \
  data/input_akka_codes/simple_examples/simplePingPong.txt \
  --candidate-id simplePingPong \
  --benchmark simple_ping_pong \
  --provider openai \
  --model gpt-5.1-2025-11-13 \
  --prompt-strategies minimal_v2 handbook_zero_shot_v1 \
  --temperatures 0.0 0.1 0.3 0.5 \
  --top-p-values 0.5 0.8 0.9 1.0 \
  --reasoning-efforts none \
  --prompt-cache-key-prefix ping-pong-gpt51-new-prompts-v1 \
  --prompt-cache-retention 24h \
  --max-attempts 5 \
  --max-semantic-repairs 0 \
  --workspace-root "$GRID_ROOT" \
  --dry-run > "${GRID_ROOT}_plan.json"

jq '{total_settings, prompt_cache, first: .settings[0], last: .settings[-1]}' \
  "${GRID_ROOT}_plan.json"
```

Expected: `total_settings` is 32 and exactly two settings are marked
`WARMUP_CANDIDATE`, one for each prompt strategy.

## 2. Run a two-request cache smoke test

Use the handbook prompt twice with the same cache family. The first request is
the warm-up; the second is the first request that can report a cache hit. Keep
the key prefix unchanged for the full grid so it can reuse the warm cache.

```bash
SMOKE_ROOT="$PWD/workspace/ping_pong_gpt51_cache_smoke_${RUN_ID}"

python3 run_grid.py \
  data/input_akka_codes/simple_examples/simplePingPong.txt \
  --candidate-id simplePingPong \
  --benchmark simple_ping_pong \
  --provider openai \
  --model gpt-5.1-2025-11-13 \
  --prompt-strategies handbook_zero_shot_v1 \
  --temperatures 0.0 \
  --top-p-values 0.9 1.0 \
  --reasoning-efforts none \
  --prompt-cache-key-prefix ping-pong-gpt51-new-prompts-v1 \
  --prompt-cache-retention 24h \
  --max-attempts 1 \
  --max-semantic-repairs 0 \
  --workspace-root "$SMOKE_ROOT" \
  2>&1 | tee "${SMOKE_ROOT}.log"

jq '.usage_and_cost | {
  request_count,
  cache_read_request_count,
  cached_input_tokens,
  cache_read_ratio,
  known_cost_usd
}' "$SMOKE_ROOT/grid_result.json"
```

Proceed only if both requests have usage records and there is no API/configuration
infrastructure error. A zero cache hit must be investigated, but it must never be
rewritten as a successful cache event.

## 3. Run the real grid

```bash
python3 run_grid.py \
  data/input_akka_codes/simple_examples/simplePingPong.txt \
  --candidate-id simplePingPong \
  --benchmark simple_ping_pong \
  --provider openai \
  --model gpt-5.1-2025-11-13 \
  --prompt-strategies minimal_v2 handbook_zero_shot_v1 \
  --temperatures 0.0 0.1 0.3 0.5 \
  --top-p-values 0.5 0.8 0.9 1.0 \
  --reasoning-efforts none \
  --prompt-cache-key-prefix ping-pong-gpt51-new-prompts-v1 \
  --prompt-cache-retention 24h \
  --max-attempts 5 \
  --max-semantic-repairs 0 \
  --workspace-root "$GRID_ROOT" \
  2>&1 | tee "${GRID_ROOT}.log"

echo "Grid exit code: ${PIPESTATUS[0]}"
```

The grid is sequential by design. This keeps identical prompt families close in
time and improves cache locality while avoiding concurrent writes to result
artifacts.

## 4. Inspect the acceptance evidence

```bash
jq '{
  total_settings,
  completed_settings,
  setting_status_counts,
  candidate_status_counts,
  usage_and_cost,
  usage_and_cost_by_model,
  markdown_report
}' "$GRID_ROOT/grid_result.json"
```

Actual cache behavior:

```bash
jq '{
  requests: .usage_and_cost.request_count,
  cache_reads: .usage_and_cost.cache_read_request_count,
  cached_tokens: .usage_and_cost.cached_input_tokens,
  cache_ratio: .usage_and_cost.cache_read_ratio,
  estimated_cache_savings_usd: .usage_and_cost.estimated_cache_savings_usd,
  total_cost_usd: .usage_and_cost.known_cost_usd
}' "$GRID_ROOT/grid_result.json"
```

The generated `grid_report.md` contains:

- the request-level token, cache, latency, and cost ledger;
- every generated Rebeca candidate, including compiler-rejected code;
- the complete RMC stdout and stderr for every attempt;
- semantic status and failed/not-observed test IDs;
- complete semantic-test result objects with failure details;
- infrastructure errors and their logs.

If a run is interrupted after at least one completed setting, regenerate the
current report from the checkpointed JSON:

```bash
python3 experiments/generate_grid_report.py "$GRID_ROOT"
```

## Acceptance gate before more examples

Do not expand to the remaining benchmarks until all of the following are checked:

1. `completed_settings` equals 32.
2. There are no unexplained `INFRA_ERROR` results.
3. `usage_and_cost.is_complete` is true, or every missing usage/cost record is explained.
4. At least the eligible handbook requests show provider-reported cache reads; a
   zero result is documented rather than overwritten or guessed.
5. Every syntax failure has non-empty generated code and compiler evidence.
6. Every semantic failure contains test IDs and detailed semantic-test results.
7. The best settings are chosen using semantic pass first, syntax pass second,
   and cost/cache/attempt count as secondary evidence.

Only after this review should the same frozen protocol be expanded to other
examples. The GPT-5.6 Sol experiment must use a separate workspace, sampling
parameters set to `auto`, `reasoning_effort=max`, a cache key, and legacy cache
retention left at `auto`.
