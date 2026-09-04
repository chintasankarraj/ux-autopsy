"""Proves the live-regression harness's task-text handling is shell-safe —
these tests exercise only argument parsing / task resolution, never main()'s
network-calling code, so they make zero HTTP or Gemini requests. The extra
defense-in-depth guard in conftest.py (blocking the real Gemini SDK) would
also fail these tests loudly if anything here ever tried to reach it."""
from backend.scripts.live_gemini_regression import DEFAULT_TASK, build_parser, resolve_task

INTENDED_TASK = "Find a laptop priced below $800 and add it to the cart."


def test_default_task_is_the_intended_string():
    # Locks in that the script's own built-in default is exactly right —
    # this default is a Python literal, never touched by any shell, so a
    # caller who doesn't override --task always gets this exact text.
    assert DEFAULT_TASK == INTENDED_TASK


def test_task_arg_with_dollar_sign_reaches_resolve_task_unchanged():
    # Passed as a literal Python list element — exactly how argv arrives
    # after a correctly single-quoted (or --task-file'd) shell invocation.
    # A prior real run corrupted "$800" into "00" by placing it inside
    # double quotes on a bash command line; that corruption happens in the
    # shell before argv ever reaches Python, so this test's job is to prove
    # parsing/resolution itself never mangles the string once it arrives.
    args = build_parser().parse_args(["--task", INTENDED_TASK])
    assert resolve_task(args) == INTENDED_TASK
    assert "$800" in resolve_task(args)


def test_task_file_reaches_resolve_task_unchanged(tmp_path):
    task_file = tmp_path / "task.txt"
    task_file.write_text(INTENDED_TASK, encoding="utf-8")

    args = build_parser().parse_args(["--task-file", str(task_file)])
    assert resolve_task(args) == INTENDED_TASK
    assert "$800" in resolve_task(args)


def test_task_file_takes_priority_over_task_arg(tmp_path):
    task_file = tmp_path / "task.txt"
    task_file.write_text(INTENDED_TASK, encoding="utf-8")

    args = build_parser().parse_args([
        "--task", "this should be ignored",
        "--task-file", str(task_file),
    ])
    assert resolve_task(args) == INTENDED_TASK


def test_task_file_strips_trailing_whitespace(tmp_path):
    task_file = tmp_path / "task.txt"
    task_file.write_text(INTENDED_TASK + "\n\n", encoding="utf-8")

    args = build_parser().parse_args(["--task-file", str(task_file)])
    assert resolve_task(args) == INTENDED_TASK


def test_no_task_arg_falls_back_to_intended_default():
    args = build_parser().parse_args([])
    assert resolve_task(args) == INTENDED_TASK
