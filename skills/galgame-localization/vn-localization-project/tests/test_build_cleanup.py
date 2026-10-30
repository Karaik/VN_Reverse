from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_cleanup.py"


class BuildCleanupTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "The reusable cleanup module must exist.")
        spec = importlib.util.spec_from_file_location("tested_build_cleanup", SCRIPT)
        self.api = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.api
        spec.loader.exec_module(self.api)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "title"
        self.root.mkdir()
        self.out = self.root / "out"
        self.out.mkdir()
        self.options = dict(project_root=self.root, output_roots=[self.out], builder_id="fixture-builder")

    def output(self, name="package_old", run_id="old-run", mutable_paths=()):
        path = self.out / name
        path.mkdir()
        (path / "game.bin").write_bytes(b"generated game")
        self.api.mark_generated_output(path, **self.options, run_id=run_id, kind="package", mutable_paths=mutable_paths)
        return path

    def cleanup(self, **kwargs):
        return self.api.cleanup_previous_outputs(**self.options, log=lambda line: None, **kwargs)

    def make_link(self, link, target):
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
            if result.returncode:
                self.skipTest("This host cannot create a symlink or junction fixture.")

    def test_removes_only_marked_old_output(self):
        old = self.output()
        manual = self.out / "package_manual"
        manual.mkdir()
        (manual / "notes.txt").write_text("keep", encoding="utf-8")
        archive = self.out / "uploaded.zip"
        archive.write_bytes(b"keep")
        cache = self.out / "unpacked_input"
        cache.mkdir()
        plan = self.cleanup()
        self.assertEqual(plan.remove, (old,))
        self.assertFalse(old.exists())
        self.assertTrue((manual / "notes.txt").exists())
        self.assertTrue(archive.exists())
        self.assertTrue(cache.exists())

    def test_preserves_current_run_and_explicit_current_output(self):
        old = self.output()
        current = self.output("package_current", "current-run")
        excluded = self.output("release_current")
        self.cleanup(current_run_id="current-run", exclude_paths=[excluded])
        self.assertFalse(old.exists())
        self.assertTrue(current.exists())
        self.assertTrue(excluded.exists())

    def test_keep_and_dry_run_do_not_delete(self):
        old = self.output()
        lines = []
        self.api.cleanup_previous_outputs(**self.options, dry_run=True, log=lines.append)
        self.assertTrue(old.exists())
        self.assertTrue(any("Would remove" in line for line in lines))
        self.cleanup(keep_previous_outputs=True)
        self.assertTrue(old.exists())

    def test_preserves_foreign_builder_output(self):
        old = self.output()
        self.api.cleanup_previous_outputs(**{**self.options, "builder_id": "another-builder"}, log=lambda line: None)
        self.assertTrue(old.exists())

    def test_preserves_marker_copied_from_another_output(self):
        old = self.output()
        copy = self.out / "package_copy"
        copy.mkdir()
        (copy / self.api.MARKER_NAME).write_bytes((old / self.api.MARKER_NAME).read_bytes())
        self.cleanup()
        self.assertFalse(old.exists())
        self.assertTrue(copy.exists())

    def test_preserves_unknown_manual_file_in_owned_directory(self):
        old = self.output()
        (old / "my-notes.txt").write_text("keep", encoding="utf-8")
        self.cleanup()
        self.assertTrue((old / "game.bin").exists())
        self.assertTrue((old / "my-notes.txt").exists())

    def test_preserves_modified_owned_file(self):
        old = self.output()
        (old / "game.bin").write_bytes(b"hand edited")
        self.cleanup()
        self.assertEqual((old / "game.bin").read_bytes(), b"hand edited")

    def test_removes_registered_runtime_changes_inside_disposable_copy(self):
        old = self.output(mutable_paths=("savedata_cn/**", "override/patch.log"))
        (old / "savedata_cn").mkdir()
        (old / "savedata_cn" / "slot1.dat").write_bytes(b"test save")
        (old / "override").mkdir()
        (old / "override" / "patch.log").write_text("runtime log", encoding="utf-8")
        self.cleanup()
        self.assertFalse(old.exists())

    def test_rejects_broad_or_escaping_mutable_paths(self):
        for pattern in ("**", "../savedata/**", "/savedata/**", "game*", "savedata/../**"):
            with self.subTest(pattern=pattern):
                path = self.out / "package_bad"
                path.mkdir(exist_ok=True)
                with self.assertRaises(self.api.CleanupError):
                    self.api.mark_generated_output(path, **self.options, run_id="old", kind="package", mutable_paths=[pattern])

    def test_rejects_outside_or_project_root_output_root(self):
        for target in (self.base, self.root, "../outside"):
            with self.subTest(target=target), self.assertRaises(self.api.CleanupError):
                self.api.cleanup_previous_outputs(**{**self.options, "output_roots": [target]}, log=lambda line: None)

    def test_rejects_input_roots(self):
        for name in ("game", "game_script", "solution", "patch", "savedata", "cache"):
            target = self.root / name
            target.mkdir()
            with self.subTest(name=name), self.assertRaises(self.api.CleanupError):
                self.api.cleanup_previous_outputs(**{**self.options, "output_roots": [target]}, log=lambda line: None)

    def test_rejects_nested_outputs_and_overlapping_output_roots(self):
        nested = self.out / "nested"
        nested.mkdir()
        package = nested / "package_old"
        package.mkdir()
        with self.assertRaises(self.api.CleanupError):
            self.api.mark_generated_output(package, **self.options, run_id="old", kind="package")
        with self.assertRaises(self.api.CleanupError):
            self.api.plan_cleanup(**{**self.options, "output_roots": [self.out, nested]})

    def test_missing_output_root_is_a_noop_without_creating_it(self):
        missing = self.root / "not_created"
        plan = self.api.cleanup_previous_outputs(**{**self.options, "output_roots": [missing]}, log=lambda line: None)
        self.assertEqual(plan.remove, ())
        self.assertFalse(missing.exists())

    def test_rejects_unrecognized_or_abnormal_output_names(self):
        for name in ("manual", "package_bad.", "package_bad "):
            path = self.out / name
            with self.subTest(name=name), self.assertRaises(self.api.CleanupError):
                self.api.mark_generated_output(path, **self.options, run_id="old", kind="package")

    def test_rejects_symlink_or_junction_output_directory(self):
        external = self.base / "external"
        external.mkdir()
        (external / "keep.bin").write_bytes(b"keep")
        self.make_link(self.out / "package_link", external)
        with self.assertRaises(self.api.CleanupError):
            self.cleanup()
        self.assertTrue((external / "keep.bin").exists())

    def test_rejects_symlink_or_junction_output_root(self):
        external = self.base / "external"
        external.mkdir()
        sentinel = external / "keep.bin"
        sentinel.write_bytes(b"keep")
        link = self.root / "linked_output"
        self.make_link(link, external)
        with self.assertRaises(self.api.CleanupError):
            self.api.cleanup_previous_outputs(**{**self.options, "output_roots": [link]}, log=lambda line: None)
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_nested_link_aborts_whole_plan_before_any_deletion(self):
        first = self.output("package_a")
        second = self.output("package_b")
        external = self.base / "external"
        external.mkdir()
        (external / "keep.bin").write_bytes(b"keep")
        self.make_link(second / "linked", external)
        with self.assertRaises(self.api.CleanupError):
            self.cleanup()
        self.assertTrue(first.exists())
        self.assertTrue((external / "keep.bin").exists())

    def test_mutable_subtree_still_rejects_links(self):
        old = self.output(mutable_paths=("savedata/**",))
        external = self.base / "external"
        external.mkdir()
        self.make_link(old / "savedata", external)
        with self.assertRaises(self.api.CleanupError):
            self.cleanup()
        self.assertTrue(old.exists())

    def test_revalidates_entire_plan_before_deletion(self):
        first = self.output("package_a")
        second = self.output("package_b")
        plan = self.api.plan_cleanup(**self.options)
        (second / "manual.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises(self.api.CleanupError):
            self.api.execute_cleanup(plan, log=lambda line: None)
        self.assertTrue(first.exists())
        self.assertTrue((second / "manual.txt").exists())

    def test_generator_copies_helper_without_overwriting_existing_source(self):
        generator = SCRIPT.with_name("generate_title_layout.py")
        new_root = self.base / "new_title"
        result = subprocess.run([sys.executable, str(generator), str(new_root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        copied = new_root / "solution" / "build" / "build_cleanup.py"
        self.assertTrue(copied.is_file())
        self.assertTrue((new_root / "solution" / "build" / "README.md").is_file())
        copied.write_text("# local implementation\n", encoding="utf-8")
        result = subprocess.run([sys.executable, str(generator), str(new_root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(copied.read_text(encoding="utf-8"), "# local implementation\n")

    def test_standalone_cli_previews_keeps_and_cleans_only_fixture_output(self):
        old = self.output()
        command = [sys.executable, str(SCRIPT), "--project-root", str(self.root), "--output-root", "out", "--builder-id", "fixture-builder"]
        result = subprocess.run(command + ["--dry-run"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Would remove:", result.stdout)
        self.assertTrue(old.exists())
        result = subprocess.run(command + ["--keep-previous-outputs"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(old.exists())
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(old.exists())

    def test_failed_copy_is_sealed_and_cleaned_on_next_run(self):
        self.assertTrue(hasattr(self.api, "generated_output"), "Failed outputs need a controlled creation context.")
        failed = self.out / "package_failed"
        historical = self.out / "package_historical"
        historical.mkdir()
        (historical / "manual.txt").write_text("keep", encoding="utf-8")
        source = self.root / "game"
        source.mkdir()
        (source / "partial.bin").write_bytes(b"partial generated data")

        def copy_and_fail(source_file, target_file):
            shutil.copy2(source_file, target_file)
            raise OSError("copy interrupted after writing a file")

        failure = None
        with self.assertRaises(shutil.Error) as raised:
            with self.api.generated_output(failed, **self.options, run_id="failed-run", kind="package") as target:
                try:
                    shutil.copytree(source, target, dirs_exist_ok=True, copy_function=copy_and_fail)
                except shutil.Error as error:
                    failure = error
                    raise
        self.assertIs(raised.exception, failure)
        self.assertTrue((failed / self.api.MARKER_NAME).is_file())
        self.cleanup(current_run_id="failed-run")
        self.assertTrue(failed.exists())
        self.cleanup(current_run_id="next-run")
        self.assertFalse(failed.exists())
        self.assertTrue((historical / "manual.txt").exists())
        self.assertEqual((source / "partial.bin").read_bytes(), b"partial generated data")

    def test_generated_output_refuses_to_claim_preexisting_manual_directory(self):
        self.assertTrue(hasattr(self.api, "generated_output"), "Controlled creation must reject existing paths.")
        old = self.out / "package_existing"
        old.mkdir()
        (old / "manual.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            with self.api.generated_output(old, **self.options, run_id="new-run", kind="package"):
                self.fail("An existing directory must never enter the build body.")
        self.assertFalse((old / self.api.MARKER_NAME).exists())
        self.cleanup()
        self.assertTrue((old / "manual.txt").exists())

    def test_successful_generated_output_does_not_replace_existing_current_marker(self):
        self.assertTrue(hasattr(self.api, "generated_output"), "Controlled output creation must be available.")
        output = self.out / "package_success"
        with self.api.generated_output(output, **self.options, run_id="current-run", kind="package") as target:
            (target / "game.bin").write_bytes(b"generated")
            marker = self.api.mark_generated_output(target, **self.options, run_id="current-run", kind="package")
            before = marker.read_bytes()
        self.assertEqual(marker.read_bytes(), before)
        self.cleanup()
        self.assertFalse(output.exists())

    def test_sealing_error_preserves_original_build_failure(self):
        self.assertTrue(hasattr(self.api, "generated_output"), "Controlled output creation must be available.")
        output = self.out / "package_failure"
        failure = RuntimeError("original build failure")
        logs = []
        with self.assertRaises(RuntimeError) as raised:
            with self.api.generated_output(output, **self.options, run_id="failed-run", kind="package", log=logs.append):
                (output / self.api.MARKER_NAME).mkdir()
                raise failure
        self.assertIs(raised.exception, failure)
        self.assertTrue(any("Failed to seal" in line for line in logs))

    def test_generated_output_does_not_claim_replacement_directory(self):
        self.assertTrue(hasattr(self.api, "generated_output"), "Controlled creation must track directory identity.")
        output = self.out / "package_replace"
        moved = self.out / "moved_directory"
        with self.assertRaises(self.api.CleanupError):
            with self.api.generated_output(output, **self.options, run_id="new-run", kind="package"):
                output.rename(moved)
                output.mkdir()
                (output / "manual.txt").write_text("keep", encoding="utf-8")
        self.assertFalse((output / self.api.MARKER_NAME).exists())
        self.assertFalse((moved / self.api.MARKER_NAME).exists())

    def test_generated_output_does_not_recreate_a_removed_directory(self):
        self.assertTrue(hasattr(self.api, "generated_output"), "Controlled creation must tolerate a removed output.")
        output = self.out / "package_removed"
        with self.api.generated_output(output, **self.options, run_id="new-run", kind="package"):
            output.rmdir()
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
