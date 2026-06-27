#!/usr/bin/env python3
"""Generate LaTeX macros from checked-in evaluation results."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = RESULTS / "paper_numbers.tex"


def load_json(name: str):
    path = RESULTS / name
    if not path.exists():
        raise SystemExit(f"missing result file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def macro(name: str, value) -> str:
    return f"\\newcommand{{\\{name}}}{{{value}}}\n"


def pct(part: int | float, total: int | float) -> str:
    return f"{(part / total * 100.0):.1f}\\%" if total else "0.0\\%"


def feature_counts(rows, feature: str) -> tuple[int, int, int]:
    attempted = sum(1 for row in rows if row[feature])
    ks_ok = sum(1 for row in rows if row[feature] and row["ks_status"] == "ok")
    build_ok = sum(1 for row in rows if row[feature] and row["make_status"] == "ok")
    return attempted, ks_ok, build_ok


def micro_row(micro, name: str):
    rows = {row["name"]: row for row in micro["rows"]}
    return rows[name]


def ns_range(row) -> str:
    return f"{row['median_avg_ns']:.0f} ({row['min_avg_ns']:.0f}--{row['max_avg_ns']:.0f})"


def gbps_range(row) -> str:
    return (
        f"{row['median_receiver_gbps']:.1f} "
        f"({row['min_receiver_gbps']:.1f}--{row['max_receiver_gbps']:.1f})"
    )


def mpps(value: int | float) -> str:
    return f"{value:.2f}"


def mps_range(row) -> str:
    return (
        f"{row['median_event_rate_mps']:.2f} "
        f"({row['min_event_rate_mps']:.2f}--{row['max_event_rate_mps']:.2f})"
    )


def elapsed_ms_range(row) -> str:
    return (
        f"{row['median_elapsed_sec'] * 1000.0:.1f} "
        f"({row['min_elapsed_sec'] * 1000.0:.1f}--{row['max_elapsed_sec'] * 1000.0:.1f})"
    )


def elapsed_ms(value: int | float) -> str:
    return f"{value * 1000.0:.1f}"


def ips(value: int | float) -> str:
    return f"{value:.1f}"


def integer(value: int | float) -> str:
    return f"{value:.0f}"


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def latex_texttt(value: str) -> str:
    escaped = value.replace("\\", r"\textbackslash{}").replace("_", r"\_")
    return rf"\texttt{{{escaped}}}"


def latex_join(values: list[str]) -> str:
    formatted = [latex_texttt(value) for value in values]
    if not formatted:
        return "none"
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]} and {formatted[1]}"
    return ", ".join(formatted[:-1]) + f", and {formatted[-1]}"


def turbo_state(no_turbo: str) -> str:
    if no_turbo == "0":
        return "enabled"
    if no_turbo == "1":
        return "disabled"
    return "unavailable"


def main() -> int:
    env = load_json("environment.json")
    unit = load_json("unit_tests_summary.json")
    summary = load_json("evaluation_summary.json")
    examples = load_json("examples_summary.json")
    smoke = load_json("smoke_summary.json")
    micro = load_json("microbench_summary.json")
    static = load_json("static_checks_summary.json")
    lowering = load_json("lowering_ablation_summary.json")
    compiler_patch = load_json("compiler_patch_ablation_summary.json")
    verifier = load_json("verifier_matrix_summary.json")
    attach = load_json("attach_matrix_summary.json")
    xdp_traffic = load_json("xdp_traffic_summary.json")
    tc_traffic = load_json("tc_traffic_summary.json")
    traffic_stress = load_json("traffic_stress_summary.json")
    perf_loader = load_json("perf_event_loader_summary.json")
    perf_counter = load_json("perf_event_counter_summary.json")
    ringbuf = load_json("ringbuf_workload_summary.json")
    struct_ops = load_json("struct_ops_compat_summary.json")
    struct_ops_repair = load_json("struct_ops_skeleton_repair_summary.json")
    struct_ops_workload = load_json("struct_ops_workload_summary.json")
    struct_ops_callback = load_json("struct_ops_callback_workload_summary.json")
    sched_ext_verifier = load_json("sched_ext_verifier_summary.json")
    sched_ext_attach = load_json("sched_ext_attach_summary.json")
    source_footprint = load_json("source_footprint_summary.json")
    change_amplification = load_json("change_amplification_summary.json")
    external_corpus = load_json("external_corpus_summary.json")
    external_port = load_json("external_port_summary.json")
    organic = load_json("organic_mistakes_summary.json")

    if unit.get("returncode") != 0 or unit.get("reported_failures") != 0:
        raise SystemExit("unit tests are not clean; refusing to generate paper numbers")
    if smoke.get("status") != "ok":
        raise SystemExit("smoke test did not complete successfully")
    if micro.get("status") != "ok":
        raise SystemExit("microbenchmarks did not complete successfully")
    if static.get("status") != "ok":
        raise SystemExit("static checks did not complete successfully")
    if lowering.get("status") != "ok":
        raise SystemExit("lowering ablation did not complete successfully")
    if compiler_patch.get("status") != "ok":
        raise SystemExit("compiler patch ablation did not complete successfully")
    if verifier.get("status") != "ok":
        raise SystemExit("verifier matrix did not complete successfully")
    if attach.get("status") != "ok":
        raise SystemExit("attach matrix did not complete successfully")
    if xdp_traffic.get("status") != "ok":
        raise SystemExit("XDP traffic benchmark did not complete successfully")
    if tc_traffic.get("status") != "ok":
        raise SystemExit("TC traffic benchmark did not complete successfully")
    if traffic_stress.get("status") != "ok":
        raise SystemExit("traffic stress benchmark did not complete successfully")
    if perf_loader.get("status") != "ok":
        raise SystemExit("perf_event generated-loader smoke test did not complete successfully")
    if perf_counter.get("status") != "ok":
        raise SystemExit("perf_event counter benchmark did not complete successfully")
    if ringbuf.get("status") != "ok":
        raise SystemExit("ringbuf workload benchmark did not complete successfully")
    if struct_ops.get("status") != "ok":
        raise SystemExit("struct_ops compatibility check did not complete successfully")
    if struct_ops_repair.get("status") != "ok":
        raise SystemExit("struct_ops skeleton repair check did not complete successfully")
    if struct_ops_workload.get("status") != "ok":
        raise SystemExit("struct_ops workload check did not complete successfully")
    if struct_ops_callback.get("status") != "ok":
        raise SystemExit("struct_ops callback workload check did not complete successfully")
    if sched_ext_verifier.get("status") != "ok":
        raise SystemExit("sched_ext verifier diagnostic did not complete successfully")
    if sched_ext_attach.get("status") != "ok":
        raise SystemExit("sched_ext attach workload did not complete successfully")
    if source_footprint.get("status") != "ok":
        raise SystemExit("source-footprint proxy did not complete successfully")
    if change_amplification.get("status") != "ok":
        raise SystemExit("change-amplification study did not complete successfully")
    if external_corpus.get("status") != "ok":
        raise SystemExit("external corpus scan did not complete successfully")
    external_audit = external_corpus.get("classifier_audit", {})
    if external_audit.get("status") != "ok":
        raise SystemExit("external corpus classifier audit did not complete successfully")
    if external_port.get("status") != "ok":
        raise SystemExit("external port check did not complete successfully")
    if organic.get("status") != "ok":
        raise SystemExit("organic mistakes study did not complete successfully")

    content = ""
    content += macro("KSCommitShort", str(env["kernelscript_git_head"])[:7])
    content += macro("KSKernelVersion", env["kernel"])
    content += macro("KSCPUModel", env.get("cpu_model", "unavailable"))
    content += macro("KSCPUCount", env.get("cpu_count", "unavailable"))
    content += macro("KSCPUGovernor", env.get("cpu_governor_cpu0", "unavailable"))
    content += macro("KSTurboState", turbo_state(str(env.get("cpu_intel_pstate_no_turbo", "unavailable"))))
    content += macro("KSVirtualization", env.get("virtualization", "unavailable"))
    content += macro("KSTotalUnitSuites", unit["suites_successful"])
    content += macro("KSTotalUnitTests", unit["tests_successful"])
    content += macro("KSTotalExamples", summary["total_examples"])
    content += macro("KSKSCompileOK", summary["ks_compile_ok"])
    content += macro("KSKSCompilePct", pct(summary["ks_compile_ok"], summary["total_examples"]))
    content += macro("KSMakeOK", summary["make_ok"])
    content += macro("KSMakePct", pct(summary["make_ok"], summary["total_examples"]))
    content += macro("KSSafetyPct", pct(1, summary["total_examples"]))
    content += macro("KSStructOpsMismatchPct", pct(2, summary["total_examples"]))
    content += macro("KSMedianKSSloc", f"{summary['median_ks_sloc_success']:.0f}")
    content += macro("KSMedianGeneratedSloc", f"{summary['median_generated_sloc_success']:.0f}")
    content += macro("KSMedianGeneratedRatio", f"{summary['median_generated_to_ks_ratio_success']:.1f}x")
    content += macro("KSMedianInstructions", f"{summary['median_ebpf_instructions_success']:.1f}")
    source_footprint_workload = source_footprint["aggregate_workload_rows"]
    source_footprint_unique = source_footprint["aggregate_unique_sources"]
    content += macro("KSSourceFootprintWorkloads", source_footprint["workload_count"])
    content += macro("KSSourceFootprintRowsKSSloc", source_footprint_workload["ks_sloc"])
    content += macro("KSSourceFootprintRowsCSloc", source_footprint_workload["c_total_sloc"])
    content += macro("KSSourceFootprintRowsCEbpfSloc", source_footprint_workload["c_ebpf_sloc"])
    content += macro("KSSourceFootprintRowsCUserSloc", source_footprint_workload["c_user_sloc"])
    content += macro("KSSourceFootprintRowsRatio", f"{source_footprint_workload['c_to_ks_ratio']:.2f}x")
    content += macro("KSSourceFootprintMedianKSSloc", integer(source_footprint_workload["median_ks_sloc"]))
    content += macro("KSSourceFootprintMedianCSloc", integer(source_footprint_workload["median_c_total_sloc"]))
    content += macro("KSSourceFootprintMedianRatio", f"{source_footprint_workload['median_c_to_ks_ratio']:.1f}x")
    content += macro("KSSourceFootprintKSSmaller", source_footprint_workload["ks_smaller_rows"])
    content += macro("KSSourceFootprintKSNotSmaller", source_footprint_workload["ks_not_smaller_rows"])
    content += macro("KSSourceFootprintUniqueKSSloc", source_footprint_unique["ks_sloc"])
    content += macro("KSSourceFootprintUniqueCSloc", source_footprint_unique["c_total_sloc"])
    content += macro("KSSourceFootprintUniqueCEbpfSloc", source_footprint_unique["c_ebpf_sloc"])
    content += macro("KSSourceFootprintUniqueCUserSloc", source_footprint_unique["c_user_sloc"])
    content += macro("KSSourceFootprintUniqueRatio", f"{source_footprint_unique['c_to_ks_ratio']:.2f}x")
    content += macro(
        "KSSourceFootprintUniqueObjectRatio",
        f"{(source_footprint_unique['c_ebpf_sloc'] / source_footprint_unique['ks_sloc']):.2f}x",
    )
    change_rows = {
        (row["case"], row["implementation"]): row
        for row in change_amplification["rows"]
    }
    change_agg_ks = change_amplification["aggregate"]["kernelscript"]
    change_agg_c = change_amplification["aggregate"]["c_libbpf"]
    content += macro("KSChangeAmpCases", change_amplification["case_count"])
    content += macro("KSChangeAmpMedianFilesKS", change_agg_ks["median_changed_files"])
    content += macro("KSChangeAmpMedianFilesC", change_agg_c["median_changed_files"])
    content += macro("KSChangeAmpMedianSitesKS", change_agg_ks["median_edit_sites"])
    content += macro("KSChangeAmpMedianSitesC", change_agg_c["median_edit_sites"])
    content += macro("KSChangeAmpMedianLocKS", change_agg_ks["median_changed_loc"])
    content += macro("KSChangeAmpMedianLocC", change_agg_c["median_changed_loc"])
    content += macro("KSChangeAmpKernelSyncCasesKS", change_agg_ks["kernel_sync_cases"])
    content += macro("KSChangeAmpKernelSyncCasesC", change_agg_c["kernel_sync_cases"])
    content += macro("KSChangeAmpUserspaceSyncCasesKS", change_agg_ks["userspace_sync_cases"])
    content += macro("KSChangeAmpUserspaceSyncCasesC", change_agg_c["userspace_sync_cases"])
    content += macro("KSChangeAmpSkeletonSyncCasesKS", change_agg_ks["skeleton_sync_cases"])
    content += macro("KSChangeAmpSkeletonSyncCasesC", change_agg_c["skeleton_sync_cases"])
    change_case_labels = {
        "map_type_percpu_array": "MapType",
        "program_xdp_to_tc": "ProgType",
        "perf_event_grouped": "PerfGroup",
        "shared_event_schema": "EventSchema",
        "userspace_ringbuf_consumer": "Userspace",
    }
    for case_name, label in change_case_labels.items():
        ks_row = change_rows[(case_name, "kernelscript")]
        c_row = change_rows[(case_name, "c_libbpf")]
        content += macro(f"KSChangeAmp{label}FilesKS", ks_row["changed_files"])
        content += macro(f"KSChangeAmp{label}FilesC", c_row["changed_files"])
        content += macro(f"KSChangeAmp{label}SitesKS", ks_row["edit_sites"])
        content += macro(f"KSChangeAmp{label}SitesC", c_row["edit_sites"])
        content += macro(f"KSChangeAmp{label}LocKS", ks_row["changed_loc"])
        content += macro(f"KSChangeAmp{label}LocC", c_row["changed_loc"])
        content += macro(f"KSChangeAmp{label}SyncKS", ks_row["sync_surface_label"])
        content += macro(f"KSChangeAmp{label}SyncC", c_row["sync_surface_label"])
    external_features = external_corpus["feature_file_counts"]
    external_roles = external_corpus["roles"]
    external_sloc_by_role = external_corpus["sloc_by_role"]
    content += macro("KSExternalCorpusRepos", external_corpus["repo_count"])
    content += macro("KSExternalCorpusFiles", external_corpus["file_count"])
    content += macro("KSExternalCorpusSLOC", external_corpus["total_sloc"])
    content += macro("KSExternalCorpusKernelFiles", external_roles["kernel"])
    content += macro("KSExternalCorpusUserspaceFiles", external_roles["userspace"])
    content += macro("KSExternalCorpusHeaderFiles", external_roles["header"])
    content += macro("KSExternalCorpusKernelSLOC", external_sloc_by_role["kernel"])
    content += macro("KSExternalCorpusUserspaceSLOC", external_sloc_by_role["userspace"])
    content += macro("KSExternalCorpusHeaderSLOC", external_sloc_by_role["header"])
    content += macro("KSExternalCorpusFeatureCount", external_corpus["feature_count"])
    content += macro("KSExternalCorpusSectionCount", external_corpus["section_count"])
    content += macro("KSExternalCorpusXDPFiles", external_features["xdp"])
    content += macro("KSExternalCorpusTCFiles", external_features["tc"])
    content += macro("KSExternalCorpusTracepointFiles", external_features["tracepoint"])
    content += macro("KSExternalCorpusKprobeFiles", external_features["kprobe"])
    content += macro("KSExternalCorpusUprobeFiles", external_features["uprobe"])
    content += macro("KSExternalCorpusPerfEventFiles", external_features["perf_event"])
    content += macro("KSExternalCorpusMapsFiles", external_features["maps"])
    content += macro("KSExternalCorpusRingbufFiles", external_features["ringbuf"])
    content += macro("KSExternalCorpusStructOpsFiles", external_features["struct_ops"])
    content += macro("KSExternalCorpusSchedExtFiles", external_features["sched_ext"])
    content += macro("KSExternalCorpusKfuncFiles", external_features["kfunc"])
    content += macro("KSExternalCorpusTailCallFiles", external_features["tail_call"])
    content += macro("KSExternalCorpusAuditSamples", external_audit["sample_count"])
    content += macro("KSExternalCorpusAuditMatched", external_audit["matched_samples"])
    content += macro("KSExternalCorpusAuditFalsePositives", external_audit["false_positive_count"])
    content += macro("KSExternalCorpusAuditFalseNegatives", external_audit["false_negative_count"])
    external_port_rows = external_port["rows"]
    external_port_by_workload = {}
    for row in external_port_rows:
        external_port_by_workload.setdefault(row["workload"], {})[row["implementation"]] = row
    external_port_scope = external_port["scope"]
    external_port_comparison = external_port["comparison"]
    external_port_ks_gbps = [
        float(row["median_receiver_gbps"]) for row in external_port_rows if row["implementation"] == "kernelscript"
    ]
    external_port_c_gbps = [
        float(row["median_receiver_gbps"]) for row in external_port_rows if row["implementation"] == "original_external_c"
    ]
    map_counter_rows = external_port_by_workload["basic03_map_counter"]
    content += macro("KSExternalPortWorkloads", external_port["workload_count"])
    content += macro("KSExternalPortVariants", external_port["variant_count"])
    content += macro("KSExternalPortOracleOK", external_port["oracle_passed"])
    content += macro("KSExternalPortTrials", external_port["trials"])
    content += macro("KSExternalPortSeconds", external_port["seconds_per_trial"])
    content += macro("KSExternalPortCommitShort", str(external_port_scope["source_commit"])[:12])
    content += macro("KSExternalPortKSSloc", external_port["aggregate_source_sloc"]["kernelscript_port_sloc"])
    content += macro("KSExternalPortCSloc", external_port["aggregate_source_sloc"]["external_c_ebpf_sloc"])
    content += macro("KSExternalPortKSMedianGbpsRange", f"{min(external_port_ks_gbps):.1f}--{max(external_port_ks_gbps):.1f}")
    content += macro("KSExternalPortCMedianGbpsRange", f"{min(external_port_c_gbps):.1f}--{max(external_port_c_gbps):.1f}")
    content += macro("KSExternalPortMapKSMedianMpps", f"{map_counter_rows['kernelscript']['median_rx_mpps']:.2f}")
    content += macro("KSExternalPortMapCMedianMpps", f"{map_counter_rows['original_external_c']['median_rx_mpps']:.2f}")
    content += macro("KSExternalPortMapKSMedianGbps", f"{map_counter_rows['kernelscript']['median_receiver_gbps']:.1f}")
    content += macro("KSExternalPortMapCMedianGbps", f"{map_counter_rows['original_external_c']['median_receiver_gbps']:.1f}")
    content += macro(
        "KSExternalPortMapRatio",
        f"{external_port_comparison['basic03_map_counter']['ks_over_external_c_ratio']:.2f}x",
    )
    source_rows = {row["name"]: row for row in source_footprint["rows"]}
    evo_pass = source_rows["xdp_pass"]
    evo_count = source_rows["xdp_count"]
    evo_ringbuf = source_rows["ringbuf_emit"]
    evo_struct_ops = source_rows["struct_ops_callback_flags"]
    content += macro("KSEvolutionPassKSSloc", evo_pass["ks_sloc"])
    content += macro("KSEvolutionPassCEbpfSloc", evo_pass["c_ebpf_sloc"])
    content += macro("KSEvolutionPassCUserSloc", evo_pass["c_user_sloc"])
    content += macro("KSEvolutionPassCTotalSloc", evo_pass["c_total_sloc"])
    content += macro("KSEvolutionCountKSSloc", evo_count["ks_sloc"])
    content += macro("KSEvolutionCountCEbpfSloc", evo_count["c_ebpf_sloc"])
    content += macro("KSEvolutionCountCUserSloc", evo_count["c_user_sloc"])
    content += macro("KSEvolutionCountCTotalSloc", evo_count["c_total_sloc"])
    content += macro("KSEvolutionRingbufKSSloc", evo_ringbuf["ks_sloc"])
    content += macro("KSEvolutionRingbufCEbpfSloc", evo_ringbuf["c_ebpf_sloc"])
    content += macro("KSEvolutionRingbufCUserSloc", evo_ringbuf["c_user_sloc"])
    content += macro("KSEvolutionRingbufCTotalSloc", evo_ringbuf["c_total_sloc"])
    content += macro("KSEvolutionStructOpsKSSloc", evo_struct_ops["ks_sloc"])
    content += macro("KSEvolutionStructOpsCEbpfSloc", evo_struct_ops["c_ebpf_sloc"])
    content += macro("KSEvolutionStructOpsCUserSloc", evo_struct_ops["c_user_sloc"])
    content += macro("KSEvolutionStructOpsCTotalSloc", evo_struct_ops["c_total_sloc"])
    content += macro("KSEvolutionPassToCountKSDelta", evo_count["ks_sloc"] - evo_pass["ks_sloc"])
    content += macro("KSEvolutionPassToCountCDelta", evo_count["c_total_sloc"] - evo_pass["c_total_sloc"])
    content += macro("KSEvolutionCountToRingbufKSDelta", evo_ringbuf["ks_sloc"] - evo_count["ks_sloc"])
    content += macro("KSEvolutionCountToRingbufCDelta", evo_ringbuf["c_total_sloc"] - evo_count["c_total_sloc"])
    content += macro("KSEvolutionRingbufToStructOpsKSDelta", evo_struct_ops["ks_sloc"] - evo_ringbuf["ks_sloc"])
    content += macro("KSEvolutionRingbufToStructOpsCDelta", evo_struct_ops["c_total_sloc"] - evo_ringbuf["c_total_sloc"])
    content += macro("KSEvolutionRingbufRatio", f"{(evo_ringbuf['c_total_sloc'] / evo_ringbuf['ks_sloc']):.1f}x")
    content += macro("KSEvolutionStructOpsRatio", f"{(evo_struct_ops['c_total_sloc'] / evo_struct_ops['ks_sloc']):.1f}x")
    organic_rows = {row["name"]: row for row in organic["rows"]}
    organic_stage_label = {
        "compile_reject": "compile reject",
        "build_fail": "build fail",
        "verifier_reject": "verifier reject",
        "attach_fail": "attach fail",
        "runtime_wrong": "runtime wrong",
        "undetected": "undetected",
        "untested": "untested",
    }
    organic_case_label = {
        "wrong_context": "WrongContext",
        "map_undeclared": "MapUndeclared",
        "map_value_type": "MapValueType",
        "stack_overflow": "StackOverflow",
    }
    content += macro("KSOrganicTotal", organic["total"])
    content += macro("KSOrganicKSEarlier", organic["ks_earlier"])
    content += macro("KSOrganicTie", organic["tie"])
    content += macro("KSOrganicKSLater", organic["ks_later"])
    content += macro("KSOrganicInconclusive", organic["inconclusive"])
    content += macro("KSOrganicVerifierTested", yes_no(bool(organic["verifier_tested"])))
    for name, label in organic_case_label.items():
        row = organic_rows[name]
        content += macro(f"KSOrganic{label}KS", organic_stage_label[row["ks_stage"]])
        content += macro(f"KSOrganic{label}C", organic_stage_label[row["c_stage"]])
    content += macro("KSStaticTotal", static["total_cases"])
    content += macro("KSStaticMatched", static["matched_cases"])
    content += macro("KSStaticExpectedFailures", static["expected_failures"])
    content += macro("KSStaticExpectedSuccesses", static["expected_successes"])
    static_categories = static["matched_by_category"]
    content += macro("KSStaticLifecycle", static_categories.get("lifecycle_api", 0))
    content += macro("KSStaticProgramSignature", static_categories.get("program_signature", 0))
    content += macro("KSStaticMapType", static_categories.get("map_type", 0))
    content += macro("KSStaticTypeSystem", static_categories.get("type_system", 0))
    content += macro("KSStaticSymbolValidation", static_categories.get("symbol_validation", 0))
    content += macro("KSStaticConfigBoundary", static_categories.get("config_boundary", 0))
    content += macro("KSStaticHelperScope", static_categories.get("helper_scope", 0))
    content += macro("KSStaticKernelContext", static_categories.get("kernel_context", 0))
    content += macro("KSStaticPerfEventGroup", static_categories.get("perf_event_group", 0))
    content += macro("KSStaticRingbuf", static_categories.get("ringbuf_api", 0))
    content += macro("KSStaticSafety", static_categories.get("safety_analysis", 0))
    content += macro(
        "KSBugClassCrossBoundary",
        static_categories.get("program_signature", 0)
        + static_categories.get("map_type", 0)
        + static_categories.get("type_system", 0)
        + static_categories.get("ringbuf_api", 0),
    )
    content += macro("KSBugClassLifecycle", static_categories.get("lifecycle_api", 0))
    content += macro(
        "KSBugClassAttachConfig",
        static_categories.get("config_boundary", 0)
        + static_categories.get("perf_event_group", 0),
    )
    content += macro(
        "KSBugClassHelperDomain",
        static_categories.get("helper_scope", 0)
        + static_categories.get("kernel_context", 0)
        + static_categories.get("symbol_validation", 0),
    )
    content += macro("KSBugClassSafetyBound", static_categories.get("safety_analysis", 0))
    content += macro("KSVerifierTotalObjects", verifier["total_objects"])
    content += macro("KSVerifierLoadOK", verifier["load_ok"])
    content += macro("KSVerifierLoadFailed", verifier["load_failed"])
    content += macro("KSVerifierBuildObjects", verifier["build_success_objects"])
    content += macro("KSVerifierBuildLoadOK", verifier["build_success_load_ok"])
    content += macro("KSVerifierBuildLoadFailed", verifier["build_success_load_failed"])
    content += macro("KSVerifierBuildLoadOKPct", pct(verifier["build_success_load_ok"], verifier["build_success_objects"]))
    failure_classes = verifier["failure_classes"]
    content += macro("KSVerifierReferenceLeak", failure_classes.get("verifier_reference_leak", 0))
    content += macro("KSVerifierRejected", failure_classes.get("verifier_rejected", 0))
    content += macro("KSVerifierMapCreateFailed", failure_classes.get("map_create_failed", 0))
    content += macro("KSVerifierMissingBTF", failure_classes.get("missing_kernel_btf_symbol", 0))
    content += macro("KSVerifierStructOpsArg", failure_classes.get("struct_ops_argument_type", 0))
    content += macro("KSVerifierNoProgramPinned", failure_classes.get("no_program_pinned", 0))
    content += macro("KSAttachEligible", attach["eligible_xdp_objects"])
    content += macro("KSAttachOK", attach["attach_ok"])
    content += macro("KSAttachFailed", attach["attach_failed"])
    content += macro("KSAttachOKPct", pct(attach["attach_ok"], attach["eligible_xdp_objects"]))

    features = {
        "XDP": "feature_xdp",
        "TC": "feature_tc",
        "Probe": "feature_probe",
        "Tracepoint": "feature_tracepoint",
        "Perf": "feature_perf_event",
        "Maps": "feature_maps",
        "Ringbuf": "feature_ringbuf",
        "Dynptr": "feature_dynptr",
        "Kfunc": "feature_kfunc",
        "StructOps": "feature_struct_ops",
        "TailCall": "feature_tail_call",
        "Userspace": "feature_userspace",
    }
    for label, key in features.items():
        attempted, ks_ok, build_ok = feature_counts(examples, key)
        content += macro(f"KSFeat{label}Attempt", attempted)
        content += macro(f"KSFeat{label}KS", ks_ok)
        content += macro(f"KSFeat{label}Build", build_ok)

    for name in ["ks_pass", "c_pass", "ks_count", "c_count"]:
        row = micro_row(micro, name)
        label = "".join(part.capitalize() for part in name.split("_"))
        content += macro(f"KSMicro{label}Instr", row["instructions"])
        content += macro(f"KSMicro{label}Ns", ns_range(row))

    ablation_labels = {
        "ks_count_current": "Current",
        "ks_count_atomic": "Atomic",
        "c_count": "C",
    }
    for name, label in ablation_labels.items():
        row = micro_row(lowering, name)
        content += macro(f"KSAbl{label}Instr", row["instructions"])
        content += macro(f"KSAbl{label}Ns", ns_range(row))
    ablation_current = micro_row(lowering, "ks_count_current")
    content += macro("KSAblTrials", ablation_current["trials"])
    content += macro("KSAblExpectedCount", ablation_current["expected_count"])
    current_vs_atomic = lowering["comparisons"]["current_vs_atomic"]
    content += macro("KSAblInstrReduction", current_vs_atomic["instruction_reduction"])
    content += macro("KSAblInstrReductionPct", pct(current_vs_atomic["instruction_reduction"], ablation_current["instructions"]))
    content += macro("KSAblNsReduction", f"{current_vs_atomic['median_ns_reduction']:.0f}")
    content += macro("KSAblNsReductionPct", pct(current_vs_atomic["median_ns_reduction"], ablation_current["median_avg_ns"]))

    compiler_patch_labels = {
        "ks_count_current": "Current",
        "ks_count_compiler_patch": "CompilerPatch",
        "c_count": "C",
    }
    for name, label in compiler_patch_labels.items():
        row = micro_row(compiler_patch, name)
        content += macro(f"KSCP{label}Instr", row["instructions"])
        content += macro(f"KSCP{label}Ns", ns_range(row))
    cp_current = micro_row(compiler_patch, "ks_count_current")
    content += macro("KSCPTrials", cp_current["trials"])
    content += macro("KSCPExpectedCount", cp_current["expected_count"])
    current_vs_compiler_patch = compiler_patch["comparisons"]["current_vs_compiler_patch"]
    content += macro("KSCPInstrReduction", current_vs_compiler_patch["instruction_reduction"])
    content += macro("KSCPInstrReductionPct", pct(current_vs_compiler_patch["instruction_reduction"], cp_current["instructions"]))
    content += macro("KSCPNsReduction", f"{current_vs_compiler_patch['median_ns_reduction']:.0f}")
    content += macro("KSCPNsReductionPct", pct(current_vs_compiler_patch["median_ns_reduction"], cp_current["median_avg_ns"]))

    traffic_rows = {row["name"]: row for row in xdp_traffic["rows"]}
    traffic_comparisons = xdp_traffic["comparisons"]
    content += macro("KSTrafficTrials", xdp_traffic["trials"])
    content += macro("KSTrafficSeconds", xdp_traffic["seconds_per_trial"])
    content += macro("KSTrafficKsPassGbps", gbps_range(traffic_rows["ks_pass"]))
    content += macro("KSTrafficCPassGbps", gbps_range(traffic_rows["c_pass"]))
    content += macro("KSTrafficKsCountGbps", gbps_range(traffic_rows["ks_count"]))
    content += macro("KSTrafficCCountGbps", gbps_range(traffic_rows["c_count"]))
    content += macro("KSTrafficKsCountMpps", mpps(traffic_rows["ks_count"]["median_xdp_map_mpps"]))
    content += macro("KSTrafficCCountMpps", mpps(traffic_rows["c_count"]["median_xdp_map_mpps"]))
    content += macro("KSTrafficPassRatio", f"{traffic_comparisons['pass']['ks_over_c_ratio']:.2f}x")
    content += macro("KSTrafficCountRatio", f"{traffic_comparisons['count']['ks_over_c_ratio']:.2f}x")
    content += macro("KSTrafficCountOverheadPct", f"{traffic_comparisons['count']['overhead_pct']:.1f}\\%")

    tc_rows = {row["name"]: row for row in tc_traffic["rows"]}
    tc_comparisons = tc_traffic["comparisons"]
    content += macro("KSTCTrafficTrials", tc_traffic["trials"])
    content += macro("KSTCTrafficSeconds", tc_traffic["seconds_per_trial"])
    content += macro("KSTCTrafficKsPassGbps", gbps_range(tc_rows["ks_pass"]))
    content += macro("KSTCTrafficCPassGbps", gbps_range(tc_rows["c_pass"]))
    content += macro("KSTCTrafficKsCountGbps", gbps_range(tc_rows["ks_count"]))
    content += macro("KSTCTrafficCCountGbps", gbps_range(tc_rows["c_count"]))
    content += macro("KSTCTrafficKsCountMpps", mpps(tc_rows["ks_count"]["median_tc_map_mpps"]))
    content += macro("KSTCTrafficCCountMpps", mpps(tc_rows["c_count"]["median_tc_map_mpps"]))
    content += macro("KSTCTrafficPassRatio", f"{tc_comparisons['pass']['ks_over_c_ratio']:.2f}x")
    content += macro("KSTCTrafficCountRatio", f"{tc_comparisons['count']['ks_over_c_ratio']:.2f}x")
    content += macro("KSTCTrafficCountOverheadPct", f"{tc_comparisons['count']['overhead_pct']:.1f}\\%")

    stress_rows = {(row["family"], row["name"]): row for row in traffic_stress["rows"]}
    stress_comparisons = traffic_stress["comparisons"]
    content += macro("KSTrafficStressTrials", traffic_stress["trials"])
    content += macro("KSTrafficStressSeconds", traffic_stress["seconds_per_trial"])
    content += macro("KSTrafficStressXDPKsPassGbps", gbps_range(stress_rows[("xdp", "ks_pass")]))
    content += macro("KSTrafficStressXDPCPassGbps", gbps_range(stress_rows[("xdp", "c_pass")]))
    content += macro("KSTrafficStressXDPKsCountGbps", gbps_range(stress_rows[("xdp", "ks_count")]))
    content += macro("KSTrafficStressXDPCCountGbps", gbps_range(stress_rows[("xdp", "c_count")]))
    content += macro("KSTrafficStressXDPKsCountMpps", mpps(stress_rows[("xdp", "ks_count")]["median_map_mpps"]))
    content += macro("KSTrafficStressXDPCCountMpps", mpps(stress_rows[("xdp", "c_count")]["median_map_mpps"]))
    content += macro("KSTrafficStressXDPCountOverheadPct", f"{stress_comparisons['xdp']['count']['overhead_pct']:.1f}\\%")
    content += macro("KSTrafficStressTCKsPassGbps", gbps_range(stress_rows[("tc", "ks_pass")]))
    content += macro("KSTrafficStressTCCPassGbps", gbps_range(stress_rows[("tc", "c_pass")]))
    content += macro("KSTrafficStressTCKsCountGbps", gbps_range(stress_rows[("tc", "ks_count")]))
    content += macro("KSTrafficStressTCCCountGbps", gbps_range(stress_rows[("tc", "c_count")]))
    content += macro("KSTrafficStressTCKsCountMpps", mpps(stress_rows[("tc", "ks_count")]["median_map_mpps"]))
    content += macro("KSTrafficStressTCCCountMpps", mpps(stress_rows[("tc", "c_count")]["median_map_mpps"]))
    content += macro("KSTrafficStressTCCountOverheadPct", f"{stress_comparisons['tc']['count']['overhead_pct']:.1f}\\%")

    perf_rows = {row["name"]: row for row in perf_loader["rows"]}
    perf_loader_comparison = perf_loader["comparison"]
    content += macro("KSPerfLoaderTrials", perf_loader["trials"])
    content += macro("KSPerfLoaderKsPageFaults", integer(perf_rows["ks_generated"]["median_page_fault_count"]))
    content += macro("KSPerfLoaderCPageFaults", integer(perf_rows["c_libbpf"]["median_page_fault_count"]))
    content += macro("KSPerfLoaderKsBranchMisses", integer(perf_rows["ks_generated"]["median_branch_miss_count"]))
    content += macro("KSPerfLoaderCBranchMisses", integer(perf_rows["c_libbpf"]["median_branch_miss_count"]))
    content += macro("KSPerfLoaderKsElapsedMs", elapsed_ms_range(perf_rows["ks_generated"]))
    content += macro("KSPerfLoaderCElapsedMs", elapsed_ms_range(perf_rows["c_libbpf"]))
    content += macro("KSPerfLoaderKsPNinetyMs", elapsed_ms(perf_rows["ks_generated"]["p90_elapsed_sec"]))
    content += macro("KSPerfLoaderCPNinetyMs", elapsed_ms(perf_rows["c_libbpf"]["p90_elapsed_sec"]))
    content += macro("KSPerfLoaderKsIps", ips(perf_rows["ks_generated"]["median_lifecycle_invocations_per_sec"]))
    content += macro("KSPerfLoaderCIps", ips(perf_rows["c_libbpf"]["median_lifecycle_invocations_per_sec"]))
    content += macro("KSPerfLoaderElapsedOverheadPct", f"{perf_loader_comparison['elapsed_overhead_pct']:.1f}\\%")
    content += macro("KSPerfLoaderRateRatio", f"{perf_loader_comparison['ks_over_c_rate_ratio']:.2f}x")

    perf_counter_rows = {row["name"]: row for row in perf_counter["rows"]}
    perf_counter_comparison = perf_counter["comparison"]
    content += macro("KSPerfCounterTrials", perf_counter["trials"])
    content += macro("KSPerfCounterPages", perf_counter["pages"])
    content += macro("KSPerfCounterRounds", perf_counter["rounds"])
    content += macro("KSPerfCounterKsEvents", integer(perf_counter_rows["ks_generated"]["median_bpf_count"]))
    content += macro("KSPerfCounterCEvents", integer(perf_counter_rows["c_libbpf"]["median_bpf_count"]))
    content += macro("KSPerfCounterKsMps", mps_range(perf_counter_rows["ks_generated"]))
    content += macro("KSPerfCounterCMps", mps_range(perf_counter_rows["c_libbpf"]))
    content += macro("KSPerfCounterRatio", f"{perf_counter_comparison['ks_over_c_ratio']:.2f}x")
    content += macro("KSPerfCounterOverheadPct", f"{perf_counter_comparison['overhead_pct']:.1f}\\%")

    ringbuf_rows = {row["name"]: row for row in ringbuf["rows"]}
    ringbuf_comparison = ringbuf["comparison"]
    content += macro("KSRingbufTrials", ringbuf["trials"])
    content += macro("KSRingbufEvents", ringbuf["target_events"])
    content += macro("KSRingbufPollEvery", ringbuf["poll_every"])
    content += macro("KSRingbufKsSubmitted", integer(ringbuf_rows["ks_generated"]["median_submitted"]))
    content += macro("KSRingbufKsReceived", integer(ringbuf_rows["ks_generated"]["median_received"]))
    content += macro("KSRingbufKsDropped", integer(ringbuf_rows["ks_generated"]["median_dropped"]))
    content += macro("KSRingbufCSubmitted", integer(ringbuf_rows["c_libbpf"]["median_submitted"]))
    content += macro("KSRingbufCReceived", integer(ringbuf_rows["c_libbpf"]["median_received"]))
    content += macro("KSRingbufCDropped", integer(ringbuf_rows["c_libbpf"]["median_dropped"]))
    content += macro("KSRingbufKsMps", mps_range(ringbuf_rows["ks_generated"]))
    content += macro("KSRingbufCMps", mps_range(ringbuf_rows["c_libbpf"]))
    content += macro("KSRingbufRatio", f"{ringbuf_comparison['ks_over_c_ratio']:.2f}x")
    content += macro("KSRingbufOverheadPct", f"{ringbuf_comparison['overhead_pct']:.1f}\\%")

    struct_ops_rows = {row["name"]: row for row in struct_ops["rows"]}
    content += macro("KSStructOpsTrials", struct_ops["trials"])
    content += macro("KSStructOpsLibbpfVersion", struct_ops["libbpf_version"])
    content += macro("KSStructOpsBpftoolVersion", struct_ops["bpftool_version"].replace("bpftool ", ""))
    content += macro("KSStructOpsSkeletonLinkSupported", yes_no(bool(struct_ops["skeleton_map_link_field_supported"])))
    content += macro("KSStructOpsKsLoadOK", sum(struct_ops_rows["ks_generated"]["load_ok_samples"]))
    content += macro("KSStructOpsKsAttachOK", sum(struct_ops_rows["ks_generated"]["attach_ok_samples"]))
    content += macro("KSStructOpsKsDetachOK", sum(struct_ops_rows["ks_generated"]["detach_ok_samples"]))
    content += macro("KSStructOpsCLoadOK", sum(struct_ops_rows["c_libbpf"]["load_ok_samples"]))
    content += macro("KSStructOpsCAttachOK", sum(struct_ops_rows["c_libbpf"]["attach_ok_samples"]))
    content += macro("KSStructOpsCDetachOK", sum(struct_ops_rows["c_libbpf"]["detach_ok_samples"]))
    content += macro("KSStructOpsRepairExamples", struct_ops_repair["examples"])
    content += macro("KSStructOpsRepairLibbpfVersion", struct_ops_repair["libbpf_version"])
    content += macro("KSStructOpsRepairSkeletonLinkSupported", yes_no(bool(struct_ops_repair["skeleton_map_link_field_supported"])))
    content += macro("KSStructOpsRepairBaselineBuildOK", struct_ops_repair["baseline_build_ok"])
    content += macro("KSStructOpsRepairBaselineMapLinkFailures", struct_ops_repair["baseline_map_link_failures"])
    content += macro("KSStructOpsRepairNeeded", struct_ops_repair["repair_needed"])
    content += macro("KSStructOpsRepairBuildOK", struct_ops_repair["repaired_build_ok"])
    content += macro("KSStructOpsRepairRemovedAssignments", struct_ops_repair["removed_map_link_assignments"])
    sched_ext_rows = {row["name"]: row for row in sched_ext_verifier["rows"]}
    content += macro("KSSchedExtAttachAttempted", yes_no(bool(sched_ext_verifier["attach_attempted"])))
    content += macro("KSSchedExtStateBefore", sched_ext_verifier["sched_ext_state_before"])
    content += macro("KSSchedExtStateAfter", sched_ext_verifier["sched_ext_state_after"])
    content += macro("KSSchedExtEnableSeqBefore", sched_ext_verifier["sched_ext_enable_seq_before"])
    content += macro("KSSchedExtEnableSeqAfter", sched_ext_verifier["sched_ext_enable_seq_after"])
    content += macro("KSSchedExtDiagnosis", latex_texttt(sched_ext_verifier["diagnosis"]))
    content += macro("KSSchedExtKsLoadOK", 1 if sched_ext_rows["ks_generated"]["load_status"] == "ok" else 0)
    content += macro("KSSchedExtCLoadOK", 1 if sched_ext_rows["c_libbpf"]["load_status"] == "ok" else 0)
    content += macro("KSSchedExtKsProgramCount", sched_ext_rows["ks_generated"]["program_count"])
    content += macro("KSSchedExtCProgramCount", sched_ext_rows["c_libbpf"]["program_count"])
    content += macro("KSSchedExtKsPinnedProgramCount", sched_ext_rows["ks_generated"]["pinned_program_count"])
    content += macro("KSSchedExtCPinnedProgramCount", sched_ext_rows["c_libbpf"]["pinned_program_count"])
    content += macro("KSSchedExtKsFailureClass", latex_texttt(sched_ext_rows["ks_generated"]["failure_class"]))
    sched_ext_attach_rows = {row["name"]: row for row in sched_ext_attach["rows"]}
    content += macro("KSSchedExtAttachVariants", len(sched_ext_attach_rows))
    content += macro("KSSchedExtAttachOK", sum(1 for row in sched_ext_attach_rows.values() if row["status"] == "ok"))
    content += macro("KSSchedExtAttachWorkloadSeconds", sched_ext_attach["workload_seconds"])
    content += macro("KSSchedExtAttachWorkloadWorkers", sched_ext_attach["workload_max_workers"])
    content += macro("KSSchedExtAttachWorkloadTrials", sched_ext_attach["workload_trials"])
    content += macro("KSSchedExtAttachKsOK", 1 if sched_ext_attach_rows["ks_generated"]["status"] == "ok" else 0)
    content += macro("KSSchedExtAttachCOK", 1 if sched_ext_attach_rows["c_libbpf"]["status"] == "ok" else 0)
    content += macro("KSSchedExtAttachKsProgramCount", len(sched_ext_attach_rows["ks_generated"]["program_sections"]))
    content += macro("KSSchedExtAttachCProgramCount", len(sched_ext_attach_rows["c_libbpf"]["program_sections"]))
    content += macro("KSSchedExtAttachKsStateAfterRegister", sched_ext_attach_rows["ks_generated"]["state_after_register"])
    content += macro("KSSchedExtAttachCStateAfterRegister", sched_ext_attach_rows["c_libbpf"]["state_after_register"])
    content += macro("KSSchedExtAttachKsStateAfterWorkload", sched_ext_attach_rows["ks_generated"]["state_after_workload"])
    content += macro("KSSchedExtAttachCStateAfterWorkload", sched_ext_attach_rows["c_libbpf"]["state_after_workload"])
    content += macro("KSSchedExtAttachKsStateAfterCleanup", sched_ext_attach_rows["ks_generated"]["state_after_unregister"])
    content += macro("KSSchedExtAttachCStateAfterCleanup", sched_ext_attach_rows["c_libbpf"]["state_after_unregister"])
    content += macro("KSSchedExtAttachKsRejectedAfter", sched_ext_attach_rows["ks_generated"]["nr_rejected_after"])
    content += macro("KSSchedExtAttachCRejectedAfter", sched_ext_attach_rows["c_libbpf"]["nr_rejected_after"])
    sched_ext_attach_comparison = sched_ext_attach["comparison"]
    content += macro("KSSchedExtAttachKsMedianIterations", integer(sched_ext_attach_rows["ks_generated"]["workload_median_total_iterations"]))
    content += macro("KSSchedExtAttachCMedianIterations", integer(sched_ext_attach_rows["c_libbpf"]["workload_median_total_iterations"]))
    content += macro("KSSchedExtAttachKsMinIterations", integer(sched_ext_attach_rows["ks_generated"]["workload_min_total_iterations"]))
    content += macro("KSSchedExtAttachCMinIterations", integer(sched_ext_attach_rows["c_libbpf"]["workload_min_total_iterations"]))
    content += macro("KSSchedExtAttachIterationRatio", f"{sched_ext_attach_comparison['ks_over_c_total_iterations_ratio']:.2f}x")
    content += macro("KSSchedExtAttachKsFairnessCV", f"{sched_ext_attach_comparison['ks_median_fairness_cv']:.3f}")
    content += macro("KSSchedExtAttachCFairnessCV", f"{sched_ext_attach_comparison['c_median_fairness_cv']:.3f}")
    struct_ops_workload_rows = {row["name"]: row for row in struct_ops_workload["rows"]}
    content += macro("KSStructOpsWorkloadTrials", struct_ops_workload["trials"])
    content += macro("KSStructOpsWorkloadBytes", struct_ops_workload["bytes_per_trial"])
    content += macro("KSStructOpsWorkloadMiB", f"{struct_ops_workload['bytes_per_trial'] / (1024 * 1024):.0f}")
    content += macro("KSStructOpsWorkloadKsOK", sum(struct_ops_workload_rows["ks_generated"]["workload_ok_samples"]))
    content += macro("KSStructOpsWorkloadCOK", sum(struct_ops_workload_rows["c_libbpf"]["workload_ok_samples"]))
    content += macro("KSStructOpsWorkloadKsSelected", sum(struct_ops_workload_rows["ks_generated"]["cc_selected_samples"]))
    content += macro("KSStructOpsWorkloadCSelected", sum(struct_ops_workload_rows["c_libbpf"]["cc_selected_samples"]))
    content += macro("KSStructOpsWorkloadKsDetachOK", sum(struct_ops_workload_rows["ks_generated"]["detach_ok_samples"]))
    content += macro("KSStructOpsWorkloadCDetachOK", sum(struct_ops_workload_rows["c_libbpf"]["detach_ok_samples"]))
    content += macro("KSStructOpsWorkloadKsElapsedMs", elapsed_ms(struct_ops_workload_rows["ks_generated"]["median_elapsed_sec"]))
    content += macro("KSStructOpsWorkloadCElapsedMs", elapsed_ms(struct_ops_workload_rows["c_libbpf"]["median_elapsed_sec"]))
    content += macro("KSStructOpsWorkloadKsMiBps", f"{struct_ops_workload_rows['ks_generated']['median_mib_per_sec']:.1f}")
    content += macro("KSStructOpsWorkloadCMiBps", f"{struct_ops_workload_rows['c_libbpf']['median_mib_per_sec']:.1f}")
    struct_ops_callback_rows = {row["name"]: row for row in struct_ops_callback["rows"]}
    struct_ops_callback_loss_rows = {row["name"]: row for row in struct_ops_callback["loss_rows"]}
    callback_flag_names = struct_ops_callback["flag_names"]
    callback_ssthresh = callback_flag_names.index("ssthresh")
    callback_undo_cwnd = callback_flag_names.index("undo_cwnd")
    callback_cong_avoid = callback_flag_names.index("cong_avoid")
    callback_set_state = callback_flag_names.index("set_state")
    callback_cwnd_event = callback_flag_names.index("cwnd_event")
    required_callback_flags = struct_ops_callback["required_callback_flags"]
    loss_required_callback_flags = struct_ops_callback["loss_required_callback_flags"]
    content += macro("KSStructOpsCallbackTrials", struct_ops_callback["trials"])
    content += macro("KSStructOpsCallbackBytes", struct_ops_callback["bytes_per_trial"])
    content += macro("KSStructOpsCallbackMiB", f"{struct_ops_callback['bytes_per_trial'] / (1024 * 1024):.0f}")
    content += macro("KSStructOpsCallbackRequired", latex_join(required_callback_flags))
    content += macro("KSStructOpsCallbackKsOK", sum(struct_ops_callback_rows["ks_generated"]["workload_ok_samples"]))
    content += macro("KSStructOpsCallbackCOK", sum(struct_ops_callback_rows["c_libbpf"]["workload_ok_samples"]))
    content += macro("KSStructOpsCallbackKsOracleOK", sum(struct_ops_callback_rows["ks_generated"]["callback_oracle_samples"]))
    content += macro("KSStructOpsCallbackCOracleOK", sum(struct_ops_callback_rows["c_libbpf"]["callback_oracle_samples"]))
    content += macro("KSStructOpsCallbackKsCongAvoid", sum(struct_ops_callback_rows["ks_generated"]["callback_flags_by_slot"][callback_cong_avoid]))
    content += macro("KSStructOpsCallbackCCongAvoid", sum(struct_ops_callback_rows["c_libbpf"]["callback_flags_by_slot"][callback_cong_avoid]))
    content += macro("KSStructOpsCallbackKsCwndEvent", sum(struct_ops_callback_rows["ks_generated"]["callback_flags_by_slot"][callback_cwnd_event]))
    content += macro("KSStructOpsCallbackCCwndEvent", sum(struct_ops_callback_rows["c_libbpf"]["callback_flags_by_slot"][callback_cwnd_event]))
    content += macro("KSStructOpsCallbackKsDetachOK", sum(struct_ops_callback_rows["ks_generated"]["detach_ok_samples"]))
    content += macro("KSStructOpsCallbackCDetachOK", sum(struct_ops_callback_rows["c_libbpf"]["detach_ok_samples"]))
    content += macro("KSStructOpsCallbackKsElapsedMs", elapsed_ms(struct_ops_callback_rows["ks_generated"]["median_elapsed_sec"]))
    content += macro("KSStructOpsCallbackCElapsedMs", elapsed_ms(struct_ops_callback_rows["c_libbpf"]["median_elapsed_sec"]))
    content += macro("KSStructOpsCallbackKsMiBps", f"{struct_ops_callback_rows['ks_generated']['median_mib_per_sec']:.1f}")
    content += macro("KSStructOpsCallbackCMiBps", f"{struct_ops_callback_rows['c_libbpf']['median_mib_per_sec']:.1f}")
    content += macro("KSStructOpsCallbackLossTrials", struct_ops_callback["loss_trials"])
    content += macro("KSStructOpsCallbackLossBytes", struct_ops_callback["loss_bytes_per_trial"])
    content += macro("KSStructOpsCallbackLossMiB", f"{struct_ops_callback['loss_bytes_per_trial'] / (1024 * 1024):.0f}")
    content += macro("KSStructOpsCallbackLossPct", str(struct_ops_callback["loss_percent"]).replace("%", r"\%"))
    content += macro("KSStructOpsCallbackLossRequired", latex_join(loss_required_callback_flags))
    content += macro("KSStructOpsCallbackKsLossOK", sum(struct_ops_callback_loss_rows["ks_generated"]["workload_ok_samples"]))
    content += macro("KSStructOpsCallbackCLossOK", sum(struct_ops_callback_loss_rows["c_libbpf"]["workload_ok_samples"]))
    content += macro("KSStructOpsCallbackKsLossOracleOK", sum(struct_ops_callback_loss_rows["ks_generated"]["callback_oracle_samples"]))
    content += macro("KSStructOpsCallbackCLossOracleOK", sum(struct_ops_callback_loss_rows["c_libbpf"]["callback_oracle_samples"]))
    content += macro("KSStructOpsCallbackKsLossSsthresh", sum(struct_ops_callback_loss_rows["ks_generated"]["callback_flags_by_slot"][callback_ssthresh]))
    content += macro("KSStructOpsCallbackCLossSsthresh", sum(struct_ops_callback_loss_rows["c_libbpf"]["callback_flags_by_slot"][callback_ssthresh]))
    content += macro("KSStructOpsCallbackKsLossUndoCwnd", sum(struct_ops_callback_loss_rows["ks_generated"]["callback_flags_by_slot"][callback_undo_cwnd]))
    content += macro("KSStructOpsCallbackCLossUndoCwnd", sum(struct_ops_callback_loss_rows["c_libbpf"]["callback_flags_by_slot"][callback_undo_cwnd]))
    content += macro("KSStructOpsCallbackKsLossCongAvoid", sum(struct_ops_callback_loss_rows["ks_generated"]["callback_flags_by_slot"][callback_cong_avoid]))
    content += macro("KSStructOpsCallbackCLossCongAvoid", sum(struct_ops_callback_loss_rows["c_libbpf"]["callback_flags_by_slot"][callback_cong_avoid]))
    content += macro("KSStructOpsCallbackKsLossSetState", sum(struct_ops_callback_loss_rows["ks_generated"]["callback_flags_by_slot"][callback_set_state]))
    content += macro("KSStructOpsCallbackCLossSetState", sum(struct_ops_callback_loss_rows["c_libbpf"]["callback_flags_by_slot"][callback_set_state]))
    content += macro("KSStructOpsCallbackKsLossCwndEvent", sum(struct_ops_callback_loss_rows["ks_generated"]["callback_flags_by_slot"][callback_cwnd_event]))
    content += macro("KSStructOpsCallbackCLossCwndEvent", sum(struct_ops_callback_loss_rows["c_libbpf"]["callback_flags_by_slot"][callback_cwnd_event]))
    content += macro("KSStructOpsCallbackKsLossDetachOK", sum(struct_ops_callback_loss_rows["ks_generated"]["detach_ok_samples"]))
    content += macro("KSStructOpsCallbackCLossDetachOK", sum(struct_ops_callback_loss_rows["c_libbpf"]["detach_ok_samples"]))
    content += macro("KSStructOpsCallbackKsLossElapsedMs", elapsed_ms(struct_ops_callback_loss_rows["ks_generated"]["median_elapsed_sec"]))
    content += macro("KSStructOpsCallbackCLossElapsedMs", elapsed_ms(struct_ops_callback_loss_rows["c_libbpf"]["median_elapsed_sec"]))
    content += macro("KSStructOpsCallbackKsLossMiBps", f"{struct_ops_callback_loss_rows['ks_generated']['median_mib_per_sec']:.1f}")
    content += macro("KSStructOpsCallbackCLossMiBps", f"{struct_ops_callback_loss_rows['c_libbpf']['median_mib_per_sec']:.1f}")

    OUT.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
