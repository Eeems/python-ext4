.DEFAULT_GOAL := all
VERSION := $(shell grep -m 1 version pyproject.toml | tr -s ' ' | tr -d "'\":" | cut -d' ' -f3)
PACKAGE := $(shell grep -m 1 name pyproject.toml | tr -s ' ' | tr -d "'\":" | cut -d' ' -f3)

OBJ := $(wildcard ${PACKAGE}/**)
OBJ += pyproject.toml
OBJ += README.md
OBJ += LICENSE

SHELL := /bin/bash
ifeq ($(OS),Windows_NT)
	ifeq ($(VENV_BIN_ACTIVATE),)
		VENV_BIN_ACTIVATE := .venv/Scripts/activate
	endif
else
	ifeq ($(VENV_BIN_ACTIVATE),)
		VENV_BIN_ACTIVATE := .venv/bin/activate
	endif
endif

ifeq ($(FUZZ_TIMEOUT),)
FUZZ_TIMEOUT := 60
endif

.PHONY: clean
clean:
	git clean --force -dX

${VENV_BIN_ACTIVATE}: pyproject.toml
	emake requirements dev

.PHONY: fuzz
fuzz: ${VENV_BIN_ACTIVATE}
	@. ${VENV_BIN_ACTIVATE}; \
	python -m pip install \
	  --require-virtualenv \
	  --editable \
	  .[fuzz]
	. ${VENV_BIN_ACTIVATE};\
	python fuzz.py \
	  -rss_limit_mb=2048 \
	  -max_total_time=$(FUZZ_TIMEOUT)

.PHONY: all
all: release
