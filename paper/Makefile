PAPER=kernelscript-paper

.PHONY: all clean

all: $(PAPER).pdf

../results/paper_numbers.tex: ../experiments/update_paper_numbers.py ../results/environment.json ../results/unit_tests_summary.json ../results/evaluation_summary.json ../results/examples_summary.json ../results/smoke_summary.json ../results/microbench_summary.json ../results/xdp_traffic_summary.json ../results/tc_traffic_summary.json ../results/traffic_stress_summary.json ../results/perf_event_loader_summary.json ../results/perf_event_counter_summary.json ../results/ringbuf_workload_summary.json ../results/static_checks_summary.json ../results/lowering_ablation_summary.json ../results/compiler_patch_ablation_summary.json ../results/verifier_matrix_summary.json ../results/attach_matrix_summary.json ../results/struct_ops_compat_summary.json ../results/struct_ops_workload_summary.json ../results/struct_ops_callback_workload_summary.json ../results/struct_ops_skeleton_repair_summary.json ../results/sched_ext_verifier_summary.json ../results/sched_ext_attach_summary.json
	cd .. && ./experiments/update_paper_numbers.py

$(PAPER).pdf: $(PAPER).tex references.bib ../results/paper_numbers.tex
	latexmk -pdf -interaction=nonstopmode -halt-on-error $(PAPER).tex

clean:
	latexmk -C $(PAPER).tex
