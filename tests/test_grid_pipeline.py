import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.artifacts.result_models import PipelineStatus
from src.llm.model_config import parse_model_target
from src.cli.run_grid import (
    aggregate_payload,
    build_settings,
    main,
    plan_payload,
    setting_prompt_cache_key,
    setting_workspace,
)


class GridPipelineTests(unittest.TestCase):
    def test_repetitions_create_distinct_samples_without_changing_default_ids(self) -> None:
        default_setting = build_settings(["basic"], [0.0], [0.9])[0]
        repeated = build_settings(
            ["basic"], [0.0], [0.9], repetitions=3
        )

        self.assertEqual(default_setting.setting_id, "basic/temp0_0_topp0_9")
        self.assertEqual(len(repeated), 3)
        self.assertEqual(
            [setting.setting_id for setting in repeated],
            [
                "basic/temp0_0_topp0_9/replicate_01",
                "basic/temp0_0_topp0_9/replicate_02",
                "basic/temp0_0_topp0_9/replicate_03",
            ],
        )
        root = Path("workspace/grid").resolve()
        self.assertEqual(
            len(
                {
                    setting_workspace(root, "model", setting)
                    for setting in repeated
                }
            ),
            3,
        )

    def test_default_axes_produce_128_unique_settings(self) -> None:
        prompts = [
            "minimal",
            "basic",
            "detailed_rules",
            "v1_advanced",
            "v2_advanced",
            "few_shot_1",
            "few_shot_2",
            "few_shot_3",
        ]
        settings = build_settings(
            prompts,
            [0.0, 0.1, 0.3, 0.5],
            [0.5, 0.8, 0.9, 1.0],
        )

        self.assertEqual(len(settings), 128)
        self.assertEqual(len({setting.setting_id for setting in settings}), 128)
        self.assertEqual(settings[0].setting_id, "minimal/temp0_0_topp0_5")
        self.assertEqual(settings[-1].setting_id, "few_shot_3/temp0_5_topp1_0")

    def test_plan_paths_identify_model_prompt_and_parameters(self) -> None:
        settings = build_settings(["basic"], [0.1], [0.8])
        args = argparse.Namespace(
            input=Path("example.scala"),
            candidate_id="example",
            model="provider/model:version",
            prompt_strategies=["basic"],
            temperatures=[0.1],
            top_p_values=[0.8],
            max_attempts=5,
            benchmark=None,
            syntax_only=True,
        )
        root = Path("workspace/grid").resolve()

        plan = plan_payload(args, settings, root)
        workspace = setting_workspace(root, args.model, settings[0])

        self.assertIn("model_provider_model_version", workspace.parts)
        self.assertEqual(workspace.parts[-2:], ("basic", "temp0_1_topp0_8"))
        self.assertEqual(plan["settings"][0]["workspace"], str(workspace))

    def test_dry_run_does_not_create_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "grid"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "missing.scala",
                        "--workspace-root",
                        str(root),
                        "--dry-run",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            # Provider defaults are the safe cross-model baseline. The legacy
            # 128-setting sampling grid remains available when axes are explicit.
            self.assertEqual(payload["total_settings"], 8)
            self.assertFalse(root.exists())

    def test_gpt_5_1_new_prompt_grid_has_32_settings_and_cache_families(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "missing.scala",
                    "--provider",
                    "openai",
                    "--model",
                    "gpt-5.1-2025-11-13",
                    "--prompt-strategies",
                    "minimal_v2",
                    "handbook_zero_shot_v1",
                    "--temperatures",
                    "0.0",
                    "0.1",
                    "0.3",
                    "0.5",
                    "--top-p-values",
                    "0.5",
                    "0.8",
                    "0.9",
                    "1.0",
                    "--reasoning-efforts",
                    "none",
                    "--prompt-cache-key-prefix",
                    "ping-pong-gpt51-v1",
                    "--prompt-cache-retention",
                    "24h",
                    "--dry-run",
                ]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["total_settings"], 32)
        self.assertEqual(
            sum(
                item["prompt_cache_role"] == "WARMUP_CANDIDATE"
                for item in payload["settings"]
            ),
            2,
        )
        keys = {item["prompt_cache_key"] for item in payload["settings"]}
        self.assertEqual(len(keys), 2)
        self.assertEqual(payload["prompt_cache"]["retention"], "24h")

    def test_each_setting_gets_an_isolated_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_root = Path(directory)
            source = temp_root / "sample.scala"
            source.write_text("actor sample", encoding="utf-8")
            grid_root = temp_root / "grid"
            observed_metadata = []

            def fake_run_pipeline(args, *, extra_metadata):
                observed_metadata.append((args, extra_metadata))
                candidate_root = args.workspace_root / "sample"
                candidate_root.mkdir()
                return (
                    [
                        SimpleNamespace(
                            candidate_id="sample",
                            overall_status=PipelineStatus.SYNTAX_PASS,
                            workspace_path=str(candidate_root),
                        )
                    ],
                    [],
                )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch(
                "src.cli.run_grid.run_pipeline", side_effect=fake_run_pipeline
            ), patch("src.cli.run_grid.preflight_grid"), redirect_stdout(
                stdout
            ), redirect_stderr(stderr):
                exit_code = main(
                    [
                        str(source),
                        "--workspace-root",
                        str(grid_root),
                        "--model",
                        "test/model",
                        "--prompt-strategies",
                        "minimal",
                        "basic",
                        "--temperatures",
                        "0.0",
                        "0.1",
                        "--top-p-values",
                        "0.5",
                        "--syntax-only",
                    ]
                )

            aggregate = json.loads((grid_root / "grid_result.json").read_text())
            setting_reports = sorted(grid_root.rglob("setting_result.json"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(observed_metadata), 4)
            self.assertEqual(len(setting_reports), 4)
            self.assertEqual(aggregate["completed_settings"], 4)
            self.assertTrue((grid_root / "grid_report.md").is_file())
            self.assertEqual(
                aggregate["setting_status_counts"], {"COMPLETED_SUCCESS": 4}
            )
            self.assertEqual(
                {entry[1]["grid_setting_id"] for entry in observed_metadata},
                {
                    "openai/test/model/minimal/temp0_0_topp0_5",
                    "openai/test/model/minimal/temp0_1_topp0_5",
                    "openai/test/model/basic/temp0_0_topp0_5",
                    "openai/test/model/basic/temp0_1_topp0_5",
                },
            )
            for report_path in setting_reports:
                report = json.loads(report_path.read_text())
                self.assertEqual(report["model"], "test/model")
                self.assertEqual(len(report["candidates"]), 1)

    def test_resume_skips_completed_settings_without_another_llm_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_root = Path(directory)
            source = temp_root / "sample.scala"
            source.write_text("actor sample", encoding="utf-8")
            grid_root = temp_root / "grid"
            argv = [
                str(source),
                "--workspace-root",
                str(grid_root),
                "--model",
                "test/model",
                "--prompt-strategies",
                "minimal",
                "--temperatures",
                "0.0",
                "--top-p-values",
                "0.9",
                "--syntax-only",
            ]

            def fake_run_pipeline(args, *, extra_metadata):
                candidate_root = args.workspace_root / "sample"
                candidate_root.mkdir()
                return (
                    [
                        SimpleNamespace(
                            candidate_id="sample",
                            overall_status=PipelineStatus.SYNTAX_PASS,
                            workspace_path=str(candidate_root),
                        )
                    ],
                    [],
                )

            with patch(
                "src.cli.run_grid.run_pipeline", side_effect=fake_run_pipeline
            ) as first_run, patch("src.cli.run_grid.preflight_grid"), redirect_stdout(
                io.StringIO()
            ), redirect_stderr(io.StringIO()):
                self.assertEqual(main(argv), 0)
                self.assertEqual(first_run.call_count, 1)

            with patch("src.cli.run_grid.run_pipeline") as resumed_run, patch(
                "src.cli.run_grid.preflight_grid"
            ) as resumed_preflight, redirect_stdout(io.StringIO()), redirect_stderr(
                io.StringIO()
            ):
                self.assertEqual(main([*argv, "--resume"]), 0)
                resumed_run.assert_not_called()
                resumed_preflight.assert_not_called()

            aggregate = json.loads((grid_root / "grid_result.json").read_text())
            self.assertEqual(aggregate["completed_settings"], 1)

    def test_multi_model_settings_are_separated_by_provider_and_model(self) -> None:
        targets = [
            parse_model_target("openai:gpt-5.6-sol"),
            parse_model_target("deepseek:deepseek-reasoner"),
            parse_model_target("anthropic:claude-sonnet-4-5"),
        ]
        settings = build_settings(
            ["minimal_v2"],
            [None],
            [None],
            model_targets=targets,
        )
        root = Path("workspace/grid").resolve()

        self.assertEqual(len(settings), 3)
        paths = [setting_workspace(root, setting.model, setting) for setting in settings]
        self.assertEqual(len(set(paths)), 3)
        self.assertIn("provider_openai", paths[0].parts)
        self.assertIn("model_gpt-5.6-sol", paths[0].parts)
        self.assertEqual(
            settings[0].setting_id,
            "openai/gpt-5.6-sol/minimal_v2/tempauto_toppauto",
        )

    def test_dry_run_rejects_gpt_5_6_non_default_temperature(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main(
                [
                    "missing.scala",
                    "--model-targets",
                    "openai:gpt-5.6-sol",
                    "--temperatures",
                    "0.0",
                    "--top-p-values",
                    "auto",
                    "--dry-run",
                ]
            )
        self.assertEqual(exit_code, 1)
        self.assertIn("only supports the default temperature=1.0", stderr.getvalue())

    def test_grid_costs_are_grouped_by_provider_and_model(self) -> None:
        manifest = {
            "model": "fallback",
            "provider": "auto",
            "model_targets": ["openai:gpt-5.1", "deepseek:deepseek-v4-pro"],
            "input": "sample.scala",
            "workspace_root": "workspace/grid",
            "total_settings": 2,
            "pricing_snapshot": {"snapshot_version": "test"},
        }
        common = {
            "status": "COMPLETED_SUCCESS",
            "candidates": [{"status": "SYNTAX_PASS"}],
        }
        settings = [
            {
                **common,
                "provider": "openai",
                "model": "gpt-5.1",
                "usage_and_cost": {
                    "request_count": 1,
                    "responses_with_usage": 1,
                    "requests_without_usage": 0,
                    "costed_requests": 1,
                    "uncosted_requests": 0,
                    "input_tokens": 100,
                    "uncached_input_tokens": 100,
                    "cached_input_tokens": 0,
                    "cache_write_input_tokens": 0,
                    "output_tokens": 20,
                    "reasoning_tokens": 0,
                    "total_tokens": 120,
                    "known_cost_usd": 0.001,
                    "is_complete": True,
                },
            },
            {
                **common,
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
                "usage_and_cost": {
                    "request_count": 1,
                    "responses_with_usage": 1,
                    "requests_without_usage": 0,
                    "costed_requests": 1,
                    "uncosted_requests": 0,
                    "input_tokens": 200,
                    "uncached_input_tokens": 200,
                    "cached_input_tokens": 0,
                    "cache_write_input_tokens": 0,
                    "output_tokens": 40,
                    "reasoning_tokens": 0,
                    "total_tokens": 240,
                    "known_cost_usd": 0.002,
                    "is_complete": True,
                },
            },
        ]

        aggregate = aggregate_payload(
            manifest,
            settings,
            started_at="start",
            finished_at="finish",
        )

        self.assertEqual(aggregate["usage_and_cost"]["request_count"], 2)
        self.assertAlmostEqual(
            aggregate["usage_and_cost"]["known_cost_usd"], 0.003
        )
        self.assertEqual(len(aggregate["usage_and_cost_by_model"]), 2)
        self.assertEqual(len(aggregate["outcome_index"]), 2)


if __name__ == "__main__":
    unittest.main()
