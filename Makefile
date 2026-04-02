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

.PHONY: build
build: wheel

.PHONY: release
release: wheel sdist

.PHONY: sdist
sdist: dist/${PACKAGE}-${VERSION}.tar.gz

.PHONY: wheel
wheel: dist/${PACKAGE}-${VERSION}-py3-none-any.whl

dist:
	mkdir -p dist

dist/${PACKAGE}-${VERSION}.tar.gz: ${VENV_BIN_ACTIVATE} dist $(OBJ)
	. ${VENV_BIN_ACTIVATE}; \
	python -m build --sdist

dist/${PACKAGE}-${VERSION}-py3-none-any.whl: ${VENV_BIN_ACTIVATE} dist $(OBJ)
	. ${VENV_BIN_ACTIVATE}; \
	python -m build --wheel

${VENV_BIN_ACTIVATE}: pyproject.toml
	@echo "Setting up development virtual env in .venv"
	python -m venv .venv
	. ${VENV_BIN_ACTIVATE}; \
	python -m pip install \
	  --require-virtualenv \
	  --editable \
	  .[dev];

.PHONY: test
test: ${VENV_BIN_ACTIVATE}
	@. ${VENV_BIN_ACTIVATE}; \
	python -m pip install \
	  --require-virtualenv \
	  --editable \
	  .[test];
	$(SHELL) test.sh

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

.PHONY: lint
lint: $(VENV_BIN_ACTIVATE);
	@. ${VENV_BIN_ACTIVATE}; \
	python -m pip install \
	  --require-virtualenv \
	  --editable \
	    .[test]; \
	python -m pip install \
	  --require-virtualenv \
	  --editable \
	    .[fuzz]
	. $(VENV_BIN_ACTIVATE); \
	python -m ruff check; \
	python -m basedpyright

.PHONY: lint-fix
lint-fix: $(VENV_BIN_ACTIVATE); \
	@. ${VENV_BIN_ACTIVATE}; \
	python -m pip install \
	  --require-virtualenv \
	  --editable \
	    .[test]; \
	python -m pip install \
	  --require-virtualenv \
	  --editable \
	    .[fuzz]
	. $(VENV_BIN_ACTIVATE); \
	python -m ruff check --fix; \
	python -m basedpyright

.PHONY: format
format: $(VENV_BIN_ACTIVATE)
	. $(VENV_BIN_ACTIVATE); \
	python -m ruff format --diff

.PHONY: format-fix
format-fix: $(VENV_BIN_ACTIVATE)
	. $(VENV_BIN_ACTIVATE); \
	python -m ruff format
