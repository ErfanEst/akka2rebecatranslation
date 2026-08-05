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
from src.cli.run_grid import (
    build_settings,
    main,
    plan_payload,
    setting_workspace,
)


class GridPipelineTests(unittest.TestCase):
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
            self.assertEqual(payload["total_settings"], 128)
            self.assertFalse(root.exists())

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
            self.assertEqual(
                aggregate["setting_status_counts"], {"COMPLETED_SUCCESS": 4}
            )
            self.assertEqual(
                {entry[1]["grid_setting_id"] for entry in observed_metadata},
                {
                    "minimal/temp0_0_topp0_5",
                    "minimal/temp0_1_topp0_5",
                    "basic/temp0_0_topp0_5",
                    "basic/temp0_1_topp0_5",
                },
            )
            for report_path in setting_reports:
                report = json.loads(report_path.read_text())
                self.assertEqual(report["model"], "test/model")
                self.assertEqual(len(report["candidates"]), 1)


if __name__ == "__main__":
    unittest.main()
