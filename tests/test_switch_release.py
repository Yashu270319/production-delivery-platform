import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SWITCH_SCRIPT = PROJECT_DIR / "scripts" / "switch-release.sh"


class SwitchReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.scripts_dir = self.root / "scripts"
        self.proxy_dir = self.root / "proxy"
        self.mock_bin = self.root / "mock-bin"

        self.scripts_dir.mkdir()
        self.proxy_dir.mkdir()
        self.mock_bin.mkdir()

        shutil.copy2(SWITCH_SCRIPT, self.scripts_dir / "switch-release.sh")

        self.backend_file = self.proxy_dir / "active-backend.conf"
        self.original_config = (
            "upstream pdp_backend {\n"
            "    server pdp-release-1.0.1:8000;\n"
            "}\n"
        )
        self.backend_file.write_text(self.original_config)

        validator = self.scripts_dir / "validate-deployment.sh"
        validator.write_text(
            "#!/usr/bin/env bash\n"
            "echo 'MOCK: candidate validation passed'\n"
            "exit 0\n"
        )
        validator.chmod(0o755)

        self.test_count_file = self.root / "nginx-test-count"
        self.docker_log = self.root / "docker.log"

        sudo_mock = self.mock_bin / "sudo"
        sudo_mock.write_text(
            "#!/usr/bin/env bash\n"
            'exec "$@"\n'
        )
        sudo_mock.chmod(0o755)

        docker_mock = self.mock_bin / "docker"
        docker_mock.write_text(
            r'''#!/usr/bin/env bash
set -u

printf '%s\n' "$*" >> "$DOCKER_LOG"

if [[ "$1" == "container" && "$2" == "inspect" ]]; then
    echo true
    exit 0
fi

if [[ "$1" == "exec" && "$3" == "nginx" && "$4" == "-t" ]]; then
    count=0
    [[ -f "$NGINX_TEST_COUNT_FILE" ]] &&
        count=$(cat "$NGINX_TEST_COUNT_FILE")
    count=$((count + 1))
    printf '%s\n' "$count" > "$NGINX_TEST_COUNT_FILE"

    # First check: existing config is valid.
    # Second check: new config fails.
    # Third check: restored config is valid.
    if [[ "$count" -eq 2 ]]; then
        echo "MOCK: simulated Nginx configuration failure" >&2
        exit 1
    fi

    echo "MOCK: Nginx configuration valid"
    exit 0
fi

if [[ "$1" == "exec" && "$3" == "nginx" && "$4" == "-s" ]]; then
    echo "MOCK: Nginx reload succeeded"
    exit 0
fi

echo "Unexpected mocked Docker command: $*" >&2
exit 1
'''
        )
        docker_mock.chmod(0o755)

        self.env = os.environ.copy()
        self.env["PATH"] = f"{self.mock_bin}:{self.env['PATH']}"
        self.env["NGINX_TEST_COUNT_FILE"] = str(self.test_count_file)
        self.env["DOCKER_LOG"] = str(self.docker_log)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_switch(self, version):
        return subprocess.run(
            ["bash", str(self.scripts_dir / "switch-release.sh"), version],
            cwd=self.root,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=15,
        )

    def test_unsupported_version_does_not_change_backend(self):
        result = self.run_switch("9.9.9")

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Unsupported release", result.stderr)
        self.assertEqual(self.backend_file.read_text(), self.original_config)
        self.assertFalse(self.docker_log.exists())

    def test_failed_new_config_restores_previous_backend(self):
        result = self.run_switch("1.0.1")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("simulated Nginx configuration failure", result.stderr)
        self.assertIn("Previous backend configuration restored.", result.stderr)
        self.assertEqual(self.backend_file.read_text(), self.original_config)

        docker_calls = self.docker_log.read_text()
        self.assertIn("nginx -s reload", docker_calls)
        self.assertEqual(self.test_count_file.read_text().strip(), "3")


if __name__ == "__main__":
    unittest.main(verbosity=2)
