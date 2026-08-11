from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.lines import Line2D

OUTPUT_PATH = Path(__file__).resolve().parent / "pipeline_flowchart.png"

fig, ax = plt.subplots(figsize=(14.4, 13.12), dpi=100)
ax.set_xlim(0, 100)
ax.set_ylim(100, 0)  # top-down, like the original
ax.axis("off")
fig.patch.set_facecolor("white")

def box(x, y, w, h, title, subtitle, fill, border, textcolor, fontsize_title=15, fontsize_sub=11.5):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=1.6",
        linewidth=1.6,
        edgecolor=border,
        facecolor=fill,
        mutation_aspect=1,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h * 0.38, title, ha="center", va="center",
             fontsize=fontsize_title, fontweight="bold", color=textcolor, family="DejaVu Sans")
    ax.text(x + w / 2, y + h * 0.68, subtitle, ha="center", va="center",
             fontsize=fontsize_sub, color=textcolor, family="DejaVu Sans", linespacing=1.9)
    return (x, y, w, h)

def stage_label(y_center, line1, line2):
    ax.text(1, y_center, line1, ha="left", va="center", fontsize=13, color="#8a8a8a", family="DejaVu Sans")
    ax.text(1, y_center + 3.3, line2, ha="left", va="center", fontsize=13, color="#8a8a8a", family="DejaVu Sans")

def varrow(x, y_top, y_bottom, color="#5a5a5a"):
    ax.annotate("", xy=(x, y_bottom), xytext=(x, y_top),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.6, shrinkA=0, shrinkB=0))

LEFT, WIDE_W = 15, 73

# ---- Stage 1: Ingestion ----
s1 = box(LEFT, 8, WIDE_W, 9.5,
          "NYT Books API",
          "Python pulls top 10 books per category weekly, stores raw JSON",
          "#E3FCF6", "#2E7D6B", "#1B5E4F")
stage_label(12.5, "Stage 1", "Ingestion")

# ---- Stage 2: Storage ----
s2 = box(LEFT, 24, WIDE_W, 9.5,
          "BigQuery (GCP)",
          "Raw table: raw_bestsellers. GCP free tier covers this project",
          "#E7F1FB", "#2F6FB0", "#1D4E7A")
stage_label(28.5, "Stage 2", "Storage")

# ---- Stage 3: Transform (UPDATED) ----
s3 = box(LEFT, 42.5, WIDE_W, 9.5,
          "dbt (transformation)",
          "stg_nyt_bestsellers → int_bestsellers_by_category → fct_bestsellers_summary\n(GROUPING SETS — 6 rollup grains, 1 model)",
          "#ECEBFB", "#6B5FC4", "#3B3480", fontsize_sub=10.8)
stage_label(47, "Stage 3", "Transform")

# ---- Stage 4: Delivery (split) ----
HALF_W = 33
s4a = box(LEFT, 60.5, HALF_W, 9.5,
           "Email digest",
           "Python + SendGrid per category",
           "#FDEDEC", "#C0524A", "#7A2E28")
s4b = box(LEFT + WIDE_W - HALF_W, 60.5, HALF_W, 9.5,
           "Looker Studio",
           "Rank trends, weeks on list",
           "#FDF1E0", "#C98A2E", "#7A5518")
stage_label(65, "Stage 4", "Delivery")

# ---- Stage 5: Orchestrate (UPDATED) ----
s5 = box(LEFT, 81, WIDE_W, 9.5,
          "Orchestration",
          "Airflow via Docker",
          "#F3F0EB", "#8A8378", "#4A463D")
stage_label(85.5, "Stage 5", "Orchestrate")

cx = LEFT + WIDE_W / 2

# Stage1 -> Stage2
varrow(cx, 17.5, 24)
# Stage2 -> Stage3
varrow(cx, 33.5, 42.5)

# Stage3 -> Stage4 (split into two)
x_left_c = LEFT + HALF_W / 2
x_right_c = LEFT + WIDE_W - HALF_W / 2
varrow(x_left_c, 52, 60.5)
varrow(x_right_c, 52, 60.5)

# Stage4 -> Stage5 (merge)
merge_y = 76.5
ax.plot([x_left_c, x_left_c], [70, merge_y], color="#5a5a5a", lw=1.6)
ax.plot([x_right_c, x_right_c], [70, merge_y], color="#5a5a5a", lw=1.6)
ax.plot([x_left_c, x_right_c], [merge_y, merge_y], color="#5a5a5a", lw=1.6)
varrow(cx, merge_y, 81)

plt.tight_layout(pad=0.6)
fig.savefig(OUTPUT_PATH, dpi=100, facecolor="white")
print("done")
