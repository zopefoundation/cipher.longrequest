PYTHON = python2.6

scripts = bin/test bin/python bin/coverage-test bin/coverage-report bin/tags

.PHONY: all
all: $(scripts)

.PHONY: help
help:
	@echo "make test          -- run all tests"
	@echo "make fast-coverage -- compute test coverage with coverage.py"
	@echo "make slow-coverage -- compute test coverage with z3c.coverage"
	@echo "make tags          -- build ctags database"

.PHONY: test
test: bin/test
	bin/test -c 2>&1 | less -RFX

.PHONY: coverage
coverage:
	@echo "Pick one:"
	@echo
	@echo "make fast-coverage -- compute test coverage with coverage.py"
	@echo "make slow-coverage -- compute test coverage with z3c.coverage"
	@echo
	@echo "(Why even have slow-coverage, given that coverage.py is faster"
	@echo "and produces fancier HTML reports?  Well, Stephan says he likes"
	@echo "the old reports better.)"

.PHONY: fast-coverage
fast-coverage: bin/test
	bin/coverage-test -c
	bin/coverage report --include '*/cipher/longrequest/*'
	bin/coverage html --include '*/cipher/longrequest/*'
	@echo
	@echo "Now run 'xdg-open htmlcov/index.html' to view results"

.PHONY: slow-coverage
slow-coverage: bin/test
	bin/test --coverage `pwd`/coverage -c
	bin/coverage-report
	@echo
	@echo "Now run 'xdg-open coverage/report/cipher.longrequest.html' to view results"

.PHONY:
tags: bin/tags
	bin/tags


bin/buildout: bootstrap.py
	$(PYTHON) bootstrap.py
	touch -c bin/buildout

$(scripts): bin/buildout buildout.cfg setup.py
	bin/buildout $(BUILDOUTARGS)
	touch -c $(scripts)
