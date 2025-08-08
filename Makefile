.DEFAULT_GOAL := all
VERSION := $(shell grep -m 1 version pyproject.toml | tr -s ' ' | tr -d "'\":" | cut -d' ' -f3)
PACKAGE := $(shell grep -m 1 name pyproject.toml | tr -s ' ' | tr -d "'\":" | cut -d' ' -f3)

OBJ := $(wildcard ${PACKAGE}/**)
OBJ += requirements.txt
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

ifeq ($(PYTHON),)
PYTHON := python
endif

clean:
	git clean --force -dX

build: wheel

release: wheel sdist

sdist: dist/${PACKAGE}-${VERSION}.tar.gz

wheel: dist/${PACKAGE}-${VERSION}-py3-none-any.whl

dist:
	mkdir -p dist

dist/${PACKAGE}-${VERSION}.tar.gz: ${VENV_BIN_ACTIVATE} dist $(OBJ)
	. ${VENV_BIN_ACTIVATE}; \
	$(PYTHON) -m build --sdist

dist/${PACKAGE}-${VERSION}-py3-none-any.whl: ${VENV_BIN_ACTIVATE} dist $(OBJ)
	. ${VENV_BIN_ACTIVATE}; \
	$(PYTHON) -m build --wheel

${VENV_BIN_ACTIVATE}: requirements.txt
	@echo "Setting up development virtual env in .venv"
	$(PYTHON) -m venv .venv
	. ${VENV_BIN_ACTIVATE}; \
	$(PYTHON) -m pip install wheel build ruff; \
	$(PYTHON) -m pip install \
	    -r requirements.txt

test: ${VENV_BIN_ACTIVATE}
	$(SHELL) test.sh

all: release

lint: $(VENV_BIN_ACTIVATE)
	. $(VENV_BIN_ACTIVATE); \
	$(PYTHON) -m ruff check

lint-fix: $(VENV_BIN_ACTIVATE)
	. $(VENV_BIN_ACTIVATE); \
	$(PYTHON) -m ruff check --fix

format: $(VENV_BIN_ACTIVATE)
	. $(VENV_BIN_ACTIVATE); \
	$(PYTHON) -m ruff format --diff

format-fix: $(VENV_BIN_ACTIVATE)
	. $(VENV_BIN_ACTIVATE); \
	$(PYTHON) -m ruff format

.PHONY: \
	all \
	build \
	clean \
	sdist \
	wheel \
	test \
	lint \
	lint-fix \
	format \
	format-fix
