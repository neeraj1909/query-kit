import subprocess
import sys


def test_module_help_exits_successfully():
    completed = subprocess.run(
        [sys.executable, "-m", "query_cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "query-cli" in completed.stdout
    assert "search" in completed.stdout
    assert "ask" not in completed.stdout
