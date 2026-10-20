# P4TC tdc test suites

Vendored tdc (tc-testing) suites for the P4TC userspace interface implemented
by this iproute2 tree (`tc p4template`, `tc p4runtime`, externs, filters).
They are plain JSON in the kernel `tools/testing/selftests/tc-testing` schema.

## Layout

```
p4tc_tdc/*.json                18 suites, 696 test cases (unique 4-hex IDs)
introspection-examples/        p4c-style introspection input for the test pipelines
run.sh                         self-serve runner (see below)
```

The same `ptables.json` also ships as the default introspection example at
`etc/iproute2/introspection/ptables.json`.

The scalar Register tests use `aP4proggieScalar.json`; the shared-extern
lifecycle test uses `p2.json`. These fixtures describe the objects created by
the tests, including their pipeline, extern, instance and parameter IDs. They
are hand-authored test metadata, not compiler output from a P4 program.

## Requirements

- A **P4TC-capable kernel** (`CONFIG_P4TC=y`, net/sched/p4tc) and the extern
  modules available to the guest/host. Build them from the kernel tree with:

  ```
  make -C <kernel-tree> M=net/sched/p4tc modules
  ```

  and make them resolvable via `P4EXTDIR` (default
  `/lib/modules/$(uname -r)/extra/p4tc`).
- This tree built (`./configure && make`): `tc/tc` and `ip/ip` are used for
  every test.
- libmnl development files available through `pkg-config` when building P4TC
  (for example, `libmnl-dev` on Debian/Ubuntu). P4TC requires libmnl for kernel
  extended-error and warning reporting; the suites check those messages.
  Install the runtime library in the guest too when the tools link it dynamically.
- The target kernel tree's `tools/testing/selftests/tc-testing` harness
  (its `tdc_config.py` must support `tdc_config_local.py`).
- Root, plus the usual tdc guest deps (`python3`, `pyroute2`, `ethtool`,
  `kmod`). Tests exercise kernel state and are normally run in a VM/guest or
  on a disposable root host.

## Usage

```
# validate all suites and show the generated tdc config (no kernel needed)
testsuite/p4tc/run.sh --list

# run everything serially against a kernel tree
testsuite/p4tc/run.sh --kernel-tree /home/jhs/git-trees/linux/p4tc-hybris

# one suite, or selected test IDs
testsuite/p4tc/run.sh --suite spec_types.json
testsuite/p4tc/run.sh --ids eff5,07fd

# extern modules built and installed elsewhere
testsuite/p4tc/run.sh --p4extdir /tmp/p4tc-modules
```

Options are documented in `run.sh --help`. The kernel tree is never written
to: the harness is copied to a disposable stage directory, where the TAP log
(`tdc.log`) and `tdc outfile` (`results.txt`) are kept. The stage directory
is removed after a successful run unless `--keep` is given; it is kept on
failure for inspection.

`testsuite/p4tc/Makefile` provides `make list` and `make run` shortcuts:
`make run KERNEL_TREE=... [P4EXTDIR=...] [RUN_ARGS='--ids eff5']`.

These suites are **not** part of the default `make -C testsuite` run: the
host netns framework only globs `tests/*.t`, and these tests require a P4TC
kernel rather than the build host.

## Provenance

The suites were validated against this tree's binaries and the v2 P4TC kernel
series (baseline `d24e8ac715de`, net-7.3-rc6): 696 tests, 684 passed, 12
expectation failures. All 12 remaining failures are upstream `[BUG? Bxx]`
expectations also present in the original series (IDs f75e, 17f1, 027e, e591,
5bcd, 94d3, fdf4, 48f3, 9c81, be04, 89fe, 37d2). The original series failed
43 of the same 696 expectations.

The bug-fix pipeline keeps its own copy of these suites (`P4TC_TESTS_SOURCE`,
default `/home/jhs/p4tc-tests`) and stages them together with the kernel
harness and modules; this directory is a vendored snapshot for people working
from the iproute2 tree alone. Keep the two in sync when the suites change.
