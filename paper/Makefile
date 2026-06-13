PAPER=kernelscript-paper

.PHONY: all clean

all: $(PAPER).pdf

../results/paper_numbers.tex: ../experiments/update_paper_numbers.py ../results/environment.json ../results/unit_tests_summary.json ../results/evaluation_summary.json ../results/examples_summary.json ../results/smoke_summary.json ../results/microbench_summary.json
	cd .. && ./experiments/update_paper_numbers.py

$(PAPER).pdf: $(PAPER).tex references.bib ../results/paper_numbers.tex
	latexmk -pdf -interaction=nonstopmode -halt-on-error $(PAPER).tex

clean:
	latexmk -C $(PAPER).tex
