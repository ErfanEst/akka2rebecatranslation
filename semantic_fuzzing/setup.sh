#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
engine=${1:-"$repo/../semantic-differential-fuzzing"}
tools=${2:-"$repo/../.semantic-fuzzing-tools"}
for program in python3 java g++ curl sha256sum; do
    command -v "$program" >/dev/null || { printf 'Missing prerequisite: %s\n' "$program" >&2; exit 1; }
done
test -f "$engine/scripts/run_semantic_differential_campaign.py"
mkdir -p "$tools/bin" "$tools/cache" "$tools/rebeca"
tools=$(cd "$tools" && pwd)
export PIP_CACHE_DIR="$tools/cache/pip"
python3 -m venv "$tools/venv"
"$tools/venv/bin/python" -m pip install --disable-pip-version-check -r "$repo/semantic_fuzzing/requirements.txt"
download() {
    local url=$1 target=$2 expected=$3
    if [[ -f "$target" ]] && printf '%s  %s\n' "$expected" "$target" | sha256sum -c --status; then
        return
    fi
    curl --fail --location --show-error --silent "$url" -o "$target.download"
    printf '%s  %s\n' "$expected" "$target.download" | sha256sum -c -
    mv "$target.download" "$target"
}
download https://repo.maven.apache.org/maven2/org/scala-sbt/sbt-launch/1.12.13/sbt-launch-1.12.13.jar \
    "$tools/sbt-launch.jar" bfee6b097104e91afd994dd6298a9040bd3217212e462953aea91f8378b69045
download https://github.com/rebeca-lang/org.rebecalang.rmc/releases/download/2.14/rmc-2.14.jar \
    "$tools/rebeca/rmc-2.14.jar" a39112046d99e0895cf47f890242ace21db896e609f7eef86751a0d416d477f5
"$tools/venv/bin/python" - "$repo" "$engine" "$tools" <<'PY'
import json
from pathlib import Path
import shlex
import sys
repo, engine, tools = (Path(p).resolve() for p in sys.argv[1:])
(tools / "repositories").write_text("[repositories]\nlocal\nmaven-central: https://repo.maven.apache.org/maven2\n")
wrapper = tools / "bin/sbt"
wrapper.write_text('''#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ${1:-} == -batch ]]; then shift; fi
export COURSIER_CACHE="$root/cache/coursier"
exec java -XX:ActiveProcessorCount=4 -Xmx2g \\
  -Dsbt.global.base="$root/cache/sbt" -Dsbt.boot.directory="$root/cache/boot" \\
  -Dsbt.ivy.home="$root/cache/ivy" -Dsbt.override.build.repos=true \\
  -Dsbt.repository.config="$root/repositories" -Dsbt.supershell=false \\
  -Dsbt.server.autostart=false -jar "$root/sbt-launch.jar" "$@"
''')
wrapper.chmod(0o755)
(tools / "activate.sh").write_text(
    f"source {shlex.quote(str(tools / 'venv/bin/activate'))}\n"
    f"export PATH={shlex.quote(str(tools / 'bin'))}:\"$PATH\"\n"
    "export MPLBACKEND=Agg\n")
config = {"fuzzing_repo": str(engine), "rmc_jar": str(tools / "rebeca/rmc-2.14.jar"),
          "sbt": str(wrapper), "case_count": 2, "message_count": 3, "start_seed": 17,
          "trace_bound": 20, "run_millis": 1000}
for name, extra in [("runtime.json", {}), ("runtime.session.json", {
    "generation_spec": str(engine / "semantic_generation_session_workflow.example.json")})]:
    target = repo / "semantic_fuzzing" / name
    if not target.exists():
        target.write_text(json.dumps({**config, **extra}, indent=2) + "\n")
    else:
        print(f"Preserving existing configuration: {target}")
print(f"Activate with: source {shlex.quote(str(tools / 'activate.sh'))}")
print("Session demo config: semantic_fuzzing/runtime.session.json")
print("Own-program config: semantic_fuzzing/runtime.json (adjust bounds/domains as needed)")
PY
