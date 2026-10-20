# SPDX-License-Identifier: GPL-2.0
# Convenience targets for the vendored P4TC tdc suites (see README.md).

KERNEL_TREE ?= /home/jhs/git-trees/linux/p4tc-hybris
P4EXTDIR ?=
RUN_ARGS ?=

RUN = ./run.sh --kernel-tree $(KERNEL_TREE) \
	$(if $(P4EXTDIR),--p4extdir $(P4EXTDIR))

.PHONY: all list run

all: list

list:
	$(RUN) --list

run:
	$(RUN) $(RUN_ARGS)
