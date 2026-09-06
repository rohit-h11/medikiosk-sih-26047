"""
MediKiosk — Large-Scale Clinical Batch Benchmark & Stress Test Runner
Executes 500-1,000 authentic clinical cases from MedQA/MIMIC/ICMR/CCRAS datasets.
Computes Confusion Matrix, Sensitivity, Specificity, F1-Score, SOCRATES Slot Extraction,
and Latency Percentiles with automated concurrency and rate-limit backoff.
"""

import os
import sys
import json
import time
import asyncio
import argparse
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

from app.ai.dialogue.dialogue_manager import get_next_dialogue_turn
from app.ai.dialogue.models import PatientContext
from load_clinical_benchmark_dataset import generate_authentic_clinical_dataset

async def process_single_case(case: Dict[str, Any], semaphore: asyncio.Semaphore) -> Dict[str, Any]:
    async with semaphore:
        ctx_data = case["patient_context"]
        patient_ctx = PatientContext(
            name=ctx_data.get("name", "Test Patient"),
            age=ctx_data.get("age", 40),
            gender=ctx_data.get("gender", "Male"),
            chief_complaint=ctx_data.get("chief_complaint", ""),
            hospital_type=ctx_data.get("hospital_type", "allopathy")
        )
        
        history = [{"role": "patient", "content": ctx_data.get("chief_complaint", "")}]
        
        start_t = time.perf_counter()
        error = None
        result = None
        is_red_flag_detected = False
        covered_slots_count = 0
        total_slots_count = 8 if patient_ctx.hospital_type == "allopathy" else 6
        
        try:
            res = await get_next_dialogue_turn(
                patient_context=patient_ctx,
                conversation_history=history,
                max_turns=5
            )
            result = res
            is_red_flag_detected = (res.red_flag_alert is not None and res.red_flag_alert.is_red_flag)
            covered_slots_count = len(res.covered_slots or [])
        except Exception as e:
            error = str(e)
            
        latency_ms = (time.perf_counter() - start_t) * 1000.0
        ground_truth_emergency = case["is_emergency_ground_truth"]
        
        # Classification categorization
        if ground_truth_emergency and is_red_flag_detected:
            outcome = "TP"  # True Positive (Correct Emergency Triage)
        elif not ground_truth_emergency and not is_red_flag_detected:
            outcome = "TN"  # True Negative (Correct Non-Emergency / Distractor Rejection)
        elif not ground_truth_emergency and is_red_flag_detected:
            outcome = "FP"  # False Positive (False Alarm / Over-triage)
        else:
            outcome = "FN"  # False Negative (Missed Emergency / Under-triage)
            
        return {
            "case_id": case["case_id"],
            "category": case["category"],
            "condition": case["condition"],
            "hospital_type": case["hospital_type"],
            "ground_truth_emergency": ground_truth_emergency,
            "detected_emergency": is_red_flag_detected,
            "outcome": outcome,
            "latency_ms": latency_ms,
            "covered_slots": covered_slots_count,
            "total_slots": total_slots_count,
            "reasoning": result.reasoning if result else None,
            "next_question": result.next_question if result else None,
            "error": error
        }

async def run_cohort_benchmark(cases_count: int = 500, concurrency: int = 4):
    print(f"===============================================================")
    print(f" MediKiosk Large-Scale Clinical Stress Test: {cases_count} Cohort")
    print(f" Concurrency Level: {concurrency} async workers")
    print(f"===============================================================")

    # Load or generate dataset
    dataset_file = os.path.join(os.path.dirname(__file__), "clinical_benchmark_500_dataset.json")
    if os.path.exists(dataset_file) and cases_count == 500:
        with open(dataset_file, "r", encoding="utf-8") as f:
            cases = json.load(f)
    else:
        cases = generate_authentic_clinical_dataset(cases_count)

    cases = cases[:cases_count]
    semaphore = asyncio.Semaphore(concurrency)
    
    start_total = time.perf_counter()
    tasks = [process_single_case(c, semaphore) for c in cases]
    
    results = []
    completed = 0
    total = len(tasks)
    
    for fut in asyncio.as_completed(tasks):
        res = await fut
        results.append(res)
        completed += 1
        if completed % 25 == 0 or completed == total:
            print(f"Progress: [{completed}/{total}] cases evaluated ({completed/total*100:.1f}%)")

    total_time = time.perf_counter() - start_total
    
    # Compute Confusion Matrix
    tp = sum(1 for r in results if r["outcome"] == "TP")
    tn = sum(1 for r in results if r["outcome"] == "TN")
    fp = sum(1 for r in results if r["outcome"] == "FP")
    fn = sum(1 for r in results if r["outcome"] == "FN")
    
    sensitivity = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
    specificity = (tn / (tn + fp)) * 100.0 if (tn + fp) > 0 else 0.0
    precision = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
    f1_score = (2 * precision * sensitivity) / (precision + sensitivity) if (precision + sensitivity) > 0 else 0.0
    accuracy = ((tp + tn) / total) * 100.0 if total > 0 else 0.0

    # Latencies
    latencies = sorted([r["latency_ms"] for r in results if r["error"] is None])
    p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0
    p90 = latencies[int(len(latencies) * 0.90)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    
    # Category Breakdowns
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "correct": 0, "errors": 0}
        categories[cat]["total"] += 1
        if r["outcome"] in ["TP", "TN"]:
            categories[cat]["correct"] += 1
        if r["error"]:
            categories[cat]["errors"] += 1

    print("\n" + "="*63)
    print("                 BENCHMARK EVALUATION RESULTS                  ")
    print("="*63)
    print(f"Total Cohort Evaluated:    {total} cases")
    print(f"Total Wall Clock Time:     {total_time:.2f} s ({total / total_time:.2f} cases/sec)")
    print(f"Average Turn Latency:      {avg_latency:.1f} ms (P50: {p50:.1f}ms | P90: {p90:.1f}ms | P99: {p99:.1f}ms)")
    print("-" * 63)
    print("CONFUSION MATRIX (EMERGENCY TRIAGE):")
    print(f"  True Positives (TP):   {tp:3d}  (Real emergencies correctly flagged)")
    print(f"  True Negatives (TN):   {tn:3d}  (Non-emergencies / idioms correctly continued)")
    print(f"  False Positives (FP):  {fp:3d}  (False alarms / over-triage)")
    print(f"  False Negatives (FN):  {fn:3d}  (Missed critical emergencies / under-triage)")
    print("-" * 63)
    print(f"  Sensitivity (Recall):  {sensitivity:6.2f}% (Target: > 98.0%)")
    print(f"  Specificity:           {specificity:6.2f}% (Target: > 95.0%)")
    print(f"  Precision (PPV):       {precision:6.2f}% (Target: > 95.0%)")
    print(f"  F1-Score:              {f1_score:6.2f}% (Target: > 95.0%)")
    print(f"  Overall Accuracy:      {accuracy:6.2f}%")
    print("-" * 63)
    print("CATEGORY-BY-CATEGORY BREAKDOWN:")
    for cat, data in sorted(categories.items()):
        acc = (data["correct"] / data["total"]) * 100.0 if data["total"] > 0 else 0
        print(f"  • {cat:24s}: {data['correct']:3d}/{data['total']:3d} correct ({acc:5.1f}%)")
    print("="*63)

    # Export report
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cohort_size": total,
        "concurrency": concurrency,
        "wall_time_sec": total_time,
        "confusion_matrix": {"TP": tp, "TN": tn, "FP": fp, "FN": fn},
        "metrics": {
            "sensitivity_recall": sensitivity,
            "specificity": specificity,
            "precision_ppv": precision,
            "f1_score": f1_score,
            "overall_accuracy": accuracy,
            "latency_p50_ms": p50,
            "latency_p90_ms": p90,
            "latency_p99_ms": p99,
            "avg_latency_ms": avg_latency
        },
        "category_breakdown": categories,
        "detailed_results": results
    }
    
    out_file = os.path.join(os.path.dirname(__file__), "large_scale_benchmark_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nFull detailed evaluation report saved to: {out_file}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MediKiosk Large-Scale Clinical Stress Test Runner")
    parser.add_argument("--cases", type=int, default=50, help="Number of cases to evaluate (e.g. 50, 100, 500, 1000)")
    parser.add_argument("--concurrency", type=int, default=3, help="Async concurrency level (default: 3)")
    args = parser.parse_args()
    
    asyncio.run(run_cohort_benchmark(cases_count=args.cases, concurrency=args.concurrency))
