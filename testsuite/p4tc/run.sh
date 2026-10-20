#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
#
# Run the vendored P4TC tdc suites against a P4TC-capable kernel tree.
#
# The suites are plain tdc JSON (p4tc_tdc/*.json). This script stages the
# kernel tree's tc-testing harness into a disposable directory, generates
# tdc_config_local.py so tdc uses this fork's tc/ip binaries and the vendored
# introspection examples, and runs the suites serially.
#
# Requirements: a built tc/tc and ip/ip in this tree, a kernel tree with
# tools/testing/selftests/tc-testing (and tdc_config_local.py support), and
# the P4TC extern modules available via P4EXTDIR (tests need root).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORK_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

KERNEL_TREE="${P4TC_KERNEL_TREE:-/home/jhs/git-trees/linux/p4tc-hybris}"
P4EXTDIR="${P4EXTDIR:-/lib/modules/$(uname -r)/extra/p4tc}"
CATEGORY="p4tc"
JOBS=1
DEST=""
KEEP=0
LIST_ONLY=0
IDS=""
SUITES=()

usage() {
	cat <<EOF
Usage: $(basename "$0") [options]

  --kernel-tree DIR   Kernel tree holding tools/testing/selftests/tc-testing
                      (default: \$P4TC_KERNEL_TREE or $KERNEL_TREE)
  --p4extdir DIR      Directory with the P4TC extern .ko modules
                      (default: \$P4EXTDIR or $P4EXTDIR)
  --category CATG     tdc category filter (default: $CATEGORY)
  --suite FILE        Run one suite only (repeatable; path relative to
                      p4tc_tdc/ is accepted; default: all suites)
  --ids ID[,ID...]    Execute only these test IDs
  --jobs N            tdc -J value (default: $JOBS; suites run serially)
  --dest DIR          Stage directory (default: a fresh mktemp dir)
  --keep              Keep the stage directory after a successful run
  --list              Validate the suites and print the generated tdc
                      config without running anything (no kernel needed)
  -h, --help          This help

Every run copies the kernel harness, so the kernel tree is never written to.
Results (TAP log + tdc outfile) stay in the stage dir; the path is printed.
EOF
}

die() { echo "error: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
	case "$1" in
	--kernel-tree) KERNEL_TREE="$2"; shift 2 ;;
	--p4extdir)    P4EXTDIR="$2"; shift 2 ;;
	--category)    CATEGORY="$2"; shift 2 ;;
	--suite)       SUITES+=("$2"); shift 2 ;;
	--ids)         IDS="$2"; shift 2 ;;
	--jobs)        JOBS="$2"; shift 2 ;;
	--dest)        DEST="$2"; shift 2 ;;
	--keep)        KEEP=1; shift ;;
	--list)        LIST_ONLY=1; shift ;;
	-h|--help)     usage; exit 0 ;;
	*)             die "unknown argument: $1 (try --help)" ;;
	esac
done

TC_BIN="$FORK_ROOT/tc/tc"
IP_BIN="$FORK_ROOT/ip/ip"
HARNESS="$KERNEL_TREE/tools/testing/selftests/tc-testing"
INTROSPECTION_DIR="$SCRIPT_DIR/introspection-examples"

resolve_suites() {
	local f
	if [ ${#SUITES[@]} -eq 0 ]; then
		SUITES=("$SCRIPT_DIR"/p4tc_tdc/*.json)
	fi
	for f in "${SUITES[@]}"; do
		if [ ! -f "$f" ] && [ -f "$SCRIPT_DIR/p4tc_tdc/$f" ]; then
			f="$SCRIPT_DIR/p4tc_tdc/$f"
		fi
		[ -f "$f" ] || die "suite not found: $f"
		echo "$f"
	done
}

validate_suites() {
	# Parses every suite, checks the tdc essentials and global ID uniqueness.
	python3 - "$INTROSPECTION_DIR" "$TC_BIN" "$IP_BIN" "$P4EXTDIR" \
		"$FORK_ROOT" "$@" <<'PY'
import json
import sys

introspection, tc_bin, ip_bin, p4extdir, fork_root, *files = sys.argv[1:]
seen = {}
total = 0
for path in files:
    try:
        with open(path) as f:
            tests = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"{path}: invalid JSON: {e}")
    if not isinstance(tests, list):
        sys.exit(f"{path}: expected a list of test cases")
    missing = [i for i, t in enumerate(tests)
               if not isinstance(t, dict) or
               not all(k in t for k in ("id", "name", "cmdUnderTest"))]
    if missing:
        sys.exit(f"{path}: malformed test case(s) at index {missing[:5]}")
    for t in tests:
        tid = t["id"]
        if tid in seen:
            sys.exit(f"{path}: duplicate test ID {tid} "
                     f"(also in {seen[tid]})")
        seen[tid] = path
    total += len(tests)
    print(f"  {len(tests):4d}  {path.rsplit('/', 1)[-1]}")
print(f"suites: {len(files)}, test cases: {total}, unique IDs: {len(seen)}")
print()
print("tdc_config_local.py:")
print(f"  EXTRA_NAMES = {{'TC': {tc_bin!r}, 'IP': {ip_bin!r}, "
      f"'P4EXTDIR': {p4extdir!r}}}")
print(f"  ENVIR['PATH'] = {fork_root + '/tc:' + fork_root + '/ip'} + $PATH")
print(f"  ENVIR['INTROSPECTION'] = {introspection!r}")
print(f"  ENVIR['P4EXTDIR'] = {p4extdir!r}")
PY
}

mapfile -t SUITE_FILES < <(resolve_suites)

if [ "$LIST_ONLY" = 1 ]; then
	validate_suites "${SUITE_FILES[@]}"
	exit 0
fi

[ -x "$TC_BIN" ] || die "$TC_BIN not built (run ./configure && make)"
[ -x "$IP_BIN" ] || die "$IP_BIN not built (run ./configure && make)"
[ -f "$HARNESS/tdc.py" ] || die "no tdc.py under $HARNESS"
grep -q tdc_config_local "$HARNESS/tdc_config.py" ||
	die "$HARNESS/tdc_config.py does not support tdc_config_local.py"
[ -d "$INTROSPECTION_DIR" ] || die "missing $INTROSPECTION_DIR"
if [ ! -d "$P4EXTDIR" ]; then
	echo "warning: P4EXTDIR $P4EXTDIR does not exist;" >&2
	echo "         extern tests will fail (build with:" >&2
	echo "         make -C $KERNEL_TREE M=net/sched/p4tc modules)" >&2
fi

validate_suites "${SUITE_FILES[@]}" >/dev/null

if [ -z "$DEST" ]; then
	DEST="$(mktemp -d "${TMPDIR:-/tmp}/p4tc-tdc.XXXXXX")"
else
	mkdir -p "$DEST"
	DEST="$(cd "$DEST" && pwd)"
fi

cleanup() {
	local rc=$?
	if [ "$rc" -ne 0 ] || [ "$KEEP" = 1 ]; then
		echo "stage kept: $DEST" >&2
	else
		rm -rf "$DEST"
	fi
}
trap cleanup EXIT

cp -a "$HARNESS/." "$DEST/tdc/"

python3 - "$DEST/tdc/tdc_config_local.py" "$TC_BIN" "$IP_BIN" \
	"$P4EXTDIR" "$FORK_ROOT/tc:$FORK_ROOT/ip" "$INTROSPECTION_DIR" <<'PY'
import sys

out, tc_bin, ip_bin, p4extdir, binpath, introspection = sys.argv[1:]
with open(out, "w") as f:
    f.write(f"""# Generated by testsuite/p4tc/run.sh -- do not edit.
import os

EXTRA_NAMES = {{
    'TC': {tc_bin!r},
    'IP': {ip_bin!r},
    'P4EXTDIR': {p4extdir!r},
}}

ENVIR = os.environ.copy()
ENVIR.update({{
    'PATH': {binpath!r} + ':' + ENVIR.get('PATH', '/usr/sbin:/usr/bin:/sbin:/bin'),
    'INTROSPECTION': {introspection!r},
    'P4EXTDIR': EXTRA_NAMES['P4EXTDIR'],
}})
""")
PY

TDC_ARGS=(-c "$CATEGORY" -J "$JOBS" --outfile "$DEST/results.txt")
if [ -n "$IDS" ]; then
	IFS=',' read -r -a id_list <<< "$IDS"
	TDC_ARGS+=(-e "${id_list[@]}")
fi
TDC_ARGS+=(-f "${SUITE_FILES[@]}")

echo "running tdc: kernel=$KERNEL_TREE tc=$TC_BIN ip=$IP_BIN"
set +e
( cd "$DEST/tdc" && python3 tdc.py "${TDC_ARGS[@]}" ) 2>&1 |
	tee "$DEST/tdc.log"
rc=${PIPESTATUS[0]}
set -e

echo "result: rc=$rc log=$DEST/tdc.log outfile=$DEST/results.txt"
exit "$rc"
