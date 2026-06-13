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
    content += macro("KSStaticTotal", static["total_cases"])
    content += macro("KSStaticMatched", static["matched_cases"])
    content += macro("KSStaticExpectedFailures", static["expected_failures"])
    content += macro("KSStaticExpectedSuccesses", static["expected_successes"])
    content += macro("KSStaticLifecycle", static["matched_by_category"].get("lifecycle_api", 0))
    content += macro("KSStaticContext", static["matched_by_category"].get("context_signature", 0))
    content += macro("KSStaticSafety", static["matched_by_category"].get("safety_analysis", 0))

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

    OUT.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
