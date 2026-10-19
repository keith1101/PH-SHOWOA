import os
import sys
import tempfile
from pathlib import Path

# Set MPLCONFIGDIR to temp directory to avoid warning
os.environ["MPLCONFIGDIR"] = tempfile.gettempdir()

import csv
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path("D:/Project/PH-SHOWOA")
ARTIFACT_DIR = Path(r"C:\Users\LENOVO\.gemini\antigravity-cli\brain\8c71c89b-793f-495c-8e0d-47f499c388ff")
OUTPUT_FIG_DIR = PROJECT_ROOT / "outputs" / "figures"
OUTPUT_FIG_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

CSV_FILE = PROJECT_ROOT / "outputs" / "final_benchmark_summary_65instances.csv"

# Load data
rows = []
with open(CSV_FILE, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append({
            "instance": r["instance"],
            "our_nv": float(r["our_mean_nv"]),
            "paper_nv": float(r["paper_nv"]) if r["paper_nv"] else None,
            "our_td": float(r["our_mean_td"]),
            "paper_td": float(r["paper_td"]) if r["paper_td"] else None,
            "diff_td_pct": float(r["diff_td_pct"]) if r["diff_td_pct"] else 0.0,
            "avg_time_sec": float(r["avg_time_sec"]),
            "avg_time_str": r["avg_time_str"],
        })

print(f"Loaded {len(rows)} instances.")

# Style configuration
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.titlesize": 14,
    "figure.dpi": 300,
})

def save_fig(fig, filename):
    p1 = ARTIFACT_DIR / filename
    p2 = OUTPUT_FIG_DIR / filename
    fig.savefig(p1, bbox_inches="tight", dpi=300)
    fig.savefig(p2, bbox_inches="tight", dpi=300)
    print(f"Saved: {p1} & {p2}")
    plt.close(fig)

# Categorize instances
def get_category(inst):
    if inst.startswith("RCdp100") and len(inst) == 8:
        return "Small (10)"
    if inst.startswith("RCdp250"):
        return "Small (25)"
    if inst.startswith("RCdp500"):
        return "Small (50)"
    if inst.startswith("RCdp1"):
        return "RC1 (100)"
    if inst.startswith("RCdp2"):
        return "RC2 (100)"
    if inst.startswith("Cdp1"):
        return "C1 (100)"
    if inst.startswith("Cdp2"):
        return "C2 (100)"
    if inst.startswith("Rdp1"):
        return "R1 (100)"
    if inst.startswith("Rdp2"):
        return "R2 (100)"
    return "Other"

for r in rows:
    r["category"] = get_category(r["instance"])

# ==============================================================================
# FIG 1: Vehicle Count Comparison (NV) Across All 65 Instances
# ==============================================================================
fig, ax = plt.subplots(figsize=(18, 6.5))
x = np.arange(len(rows))
width = 0.4

our_nvs = [r["our_nv"] for r in rows]
paper_nvs = [r["paper_nv"] for r in rows]
inst_names = [r["instance"] for r in rows]

rects1 = ax.bar(x - width/2, paper_nvs, width, label="Wang & Chen (2012)", color="#7f8c8d", alpha=0.85)
rects2 = ax.bar(x + width/2, our_nvs, width, label="PH-SHOWOA (Mean NV)", color="#2980b9", alpha=0.95)

# Highlight instances where PH-SHOWOA reduced vehicles
for i, r in enumerate(rows):
    if r["paper_nv"] and r["our_nv"] < r["paper_nv"] - 0.05:
        diff = int(round(r["paper_nv"] - r["our_nv"]))
        ax.annotate(f"-{diff}V", (i, max(r["our_nv"], r["paper_nv"]) + 0.3),
                    ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#27ae60",
                    rotation=90)

ax.set_ylabel("Number of Vehicles (NV)", fontweight="bold")
ax.set_title("Vehicle Fleet Size Comparison: PH-SHOWOA vs. Wang & Chen (2012) Across 65 Instances\n(Primary Objective: Minimizing NV)", fontweight="bold", pad=12)
ax.set_xticks(x)
ax.set_xticklabels(inst_names, rotation=90, fontsize=8)
ax.legend(loc="upper right", frameon=True, shadow=True)
ax.grid(axis="y", linestyle="--", alpha=0.4)
ax.set_ylim(0, max(paper_nvs) + 2.5)

# Add category dividers
cat_indices = []
prev_cat = None
for i, r in enumerate(rows):
    if r["category"] != prev_cat:
        if i > 0:
            ax.axvline(i - 0.5, color="#bdc3c7", linestyle=":", linewidth=1.2)
        prev_cat = r["category"]

save_fig(fig, "fig1_vehicle_comparison.png")

# ==============================================================================
# FIG 2: Total Distance Percentage Difference (% ΔTD)
# ==============================================================================
fig, ax = plt.subplots(figsize=(18, 6.5))
diffs = [r["diff_td_pct"] for r in rows]
colors = ["#27ae60" if d < 0 else "#e74c3c" if d > 20 else "#e67e22" if d > 10 else "#3498db" for d in diffs]

bars = ax.bar(x, diffs, color=colors, width=0.65, edgecolor="none", alpha=0.9)
ax.axhline(0, color="black", linewidth=1.0, linestyle="-")

# Annotate notable improvements
for i, d in enumerate(diffs):
    if d < -5.0:
        ax.annotate(f"{d:.1f}%", (i, d - 1.5), ha="center", va="top", fontsize=7, fontweight="bold", color="#1e8449", rotation=90)
    elif d > 30.0:
        ax.annotate(f"+{d:.1f}%", (i, d + 1.5), ha="center", va="bottom", fontsize=7, color="#c0392b", rotation=90)

ax.set_ylabel("Difference in Total Distance (%) [ (Our TD - Paper TD) / Paper TD ]", fontweight="bold")
ax.set_title("Total Distance Difference (%) vs. Wang & Chen (2012)\n(Green = PH-SHOWOA Better Distance, Blue/Orange = Controlled Trade-off due to Vehicle Fleet Reduction)", fontweight="bold", pad=12)
ax.set_xticks(x)
ax.set_xticklabels(inst_names, rotation=90, fontsize=8)
ax.grid(axis="y", linestyle="--", alpha=0.4)
ax.set_ylim(min(diffs) - 6, max(diffs) + 8)

save_fig(fig, "fig2_td_diff_percentage.png")

# ==============================================================================
# FIG 3: Category-Level Aggregated Performance (NV, TD, Total Cost)
# ==============================================================================
categories = ["Small (10)", "Small (25)", "Small (50)", "RC1 (100)", "RC2 (100)", "C1 (100)", "C2 (100)", "R1 (100)", "R2 (100)"]

cat_stats = {}
for cat in categories:
    cat_rows = [r for r in rows if r["category"] == cat]
    cat_stats[cat] = {
        "count": len(cat_rows),
        "our_avg_nv": np.mean([r["our_nv"] for r in cat_rows]),
        "paper_avg_nv": np.mean([r["paper_nv"] for r in cat_rows]),
        "our_avg_td": np.mean([r["our_td"] for r in cat_rows]),
        "paper_avg_td": np.mean([r["paper_td"] for r in cat_rows]),
        "our_avg_tc": np.mean([2000.0 * r["our_nv"] + r["our_td"] for r in cat_rows]),
        "paper_avg_tc": np.mean([2000.0 * r["paper_nv"] + r["paper_td"] for r in cat_rows]),
        "avg_time_min": np.mean([r["avg_time_sec"] / 60.0 for r in cat_rows]),
    }

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# Subplot 1: Average Vehicles by Category
cx = np.arange(len(categories))
cwidth = 0.35

ax1.bar(cx - cwidth/2, [cat_stats[c]["paper_avg_nv"] for c in categories], cwidth, label="Wang & Chen (2012)", color="#95a5a6")
ax1.bar(cx + cwidth/2, [cat_stats[c]["our_avg_nv"] for c in categories], cwidth, label="PH-SHOWOA (Mean NV)", color="#2980b9")
ax1.set_title("Average Number of Vehicles (NV) by Problem Class", fontweight="bold")
ax1.set_ylabel("Average Vehicles (NV)", fontweight="bold")
ax1.set_xticks(cx)
ax1.set_xticklabels(categories, rotation=35, ha="right")
ax1.legend()
ax1.grid(axis="y", linestyle="--", alpha=0.4)

# Subplot 2: Total Hierarchical Cost (2000 * NV + TD)
paper_tcs = [cat_stats[c]["paper_avg_tc"] for c in categories]
our_tcs = [cat_stats[c]["our_avg_tc"] for c in categories]

ax2.bar(cx - cwidth/2, paper_tcs, cwidth, label="Wang & Chen (2012)", color="#7f8c8d")
bars_tc = ax2.bar(cx + cwidth/2, our_tcs, cwidth, label="PH-SHOWOA Total Cost", color="#27ae60")
ax2.set_title("Hierarchical Total Cost (2000 * NV + TD) by Problem Class", fontweight="bold")
ax2.set_ylabel("Total Objective Cost", fontweight="bold")
ax2.set_xticks(cx)
ax2.set_xticklabels(categories, rotation=35, ha="right")
ax2.legend()
ax2.grid(axis="y", linestyle="--", alpha=0.4)

# Annotate savings in total cost
for i, c in enumerate(categories):
    diff_tc = our_tcs[i] - paper_tcs[i]
    pct = (diff_tc / paper_tcs[i]) * 100.0
    color = "#1e8449" if diff_tc <= 0 else "#c0392b"
    ax2.annotate(f"{pct:+.1f}%", (i + cwidth/2, our_tcs[i] + 500), ha="center", va="bottom", fontsize=8, fontweight="bold", color=color)

plt.tight_layout()
save_fig(fig, "fig3_category_summary.png")

# ==============================================================================
# FIG 4: Runtime Scaling Analysis Across Instance Classes
# ==============================================================================
fig, ax = plt.subplots(figsize=(14, 6))

times_min = [r["avg_time_sec"] / 60.0 for r in rows]
colors_time = ["#3498db" if "Small" in r["category"] else "#9b59b6" if "1 (" in r["category"] else "#e67e22" for r in rows]

ax.bar(x, times_min, color=colors_time, width=0.7, alpha=0.9)
ax.set_ylabel("Average Computation Time (Minutes)", fontweight="bold")
ax.set_title("Computation Runtime per Run across 65 Benchmark Instances\n(Blue: Small 10-50 | Purple: Series 1 Tight TW ~1h | Orange: Series 2 Wide TW ~2.5-4.5h)", fontweight="bold", pad=12)
ax.set_xticks(x)
ax.set_xticklabels(inst_names, rotation=90, fontsize=8)
ax.grid(axis="y", linestyle="--", alpha=0.4)

# Add reference lines for 1h, 2h, 4h
ax.axhline(60, color="#7f8c8d", linestyle="--", alpha=0.7, label="1 Hour")
ax.axhline(120, color="#95a5a6", linestyle="--", alpha=0.7, label="2 Hours")
ax.axhline(240, color="#bdc3c7", linestyle="--", alpha=0.7, label="4 Hours")
ax.legend(loc="upper left")

save_fig(fig, "fig4_runtime_scaling.png")

# ==============================================================================
# FIG 5: Scatter Comparison of Paper Cost vs Our Cost
# ==============================================================================
fig, ax = plt.subplots(figsize=(9, 8))

our_all_tc = np.array([2000.0 * r["our_nv"] + r["our_td"] for r in rows])
paper_all_tc = np.array([2000.0 * r["paper_nv"] + r["paper_td"] for r in rows])

# Color by size
sizes = [10 if "Small (10)" in r["category"] else 25 if "Small (25)" in r["category"] else 50 if "Small (50)" in r["category"] else 100 for r in rows]

scatter = ax.scatter(paper_all_tc, our_all_tc, c=sizes, cmap="viridis", s=70, alpha=0.85, edgecolors="black", linewidth=0.5)
cbar = plt.colorbar(scatter, ax=ax)
cbar.set_label("Problem Size (Customers)", fontweight="bold")

# Diagonal line y = x
max_val = max(np.max(paper_all_tc), np.max(our_all_tc)) * 1.05
ax.plot([0, max_val], [0, max_val], "r--", linewidth=1.5, label="Equal Performance Line (y = x)")

# Fill area where Our Cost < Paper Cost (Superiority region)
ax.fill_between([0, max_val], [0, max_val], [0, 0], color="#2ecc71", alpha=0.1, label="PH-SHOWOA Outperforms Paper Region")

ax.set_xlabel("Wang & Chen (2012) Total Cost (2000 * NV + TD)", fontweight="bold")
ax.set_ylabel("PH-SHOWOA Total Cost (2000 * NV + TD)", fontweight="bold")
ax.set_title("Total Hierarchical Objective Cost: PH-SHOWOA vs. Wang & Chen (2012)\n(Points below diagonal line represent superior solutions)", fontweight="bold", pad=12)
ax.set_xlim(0, max_val)
ax.set_ylim(0, max_val)
ax.legend(loc="upper left")
ax.grid(True, linestyle="--", alpha=0.4)

save_fig(fig, "fig5_total_cost_scatter.png")

print("\nAll 5 charts generated successfully!")
