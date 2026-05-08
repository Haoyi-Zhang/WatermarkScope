from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


FIG = Path(__file__).resolve().parent


COLORS = {
    "ink": "#111827",
    "muted": "#475569",
    "line": "#CBD5E1",
    "panel": "#F8FAFC",
    "panel2": "#F1F5F9",
    "bench": "#2563EB",
    "sem": "#15803D",
    "audit": "#B45309",
    "probe": "#7C3AED",
    "seal": "#BE123C",
    "contract": "#0F766E",
    "red": "#B91C1C",
    "gray": "#94A3B8",
    "softblue": "#DBEAFE",
    "softgreen": "#DCFCE7",
    "softamber": "#FEF3C7",
    "softviolet": "#EDE9FE",
    "softrose": "#FFE4E6",
    "softteal": "#CCFBF1",
}


def configure() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "TeX Gyre Termes", "DejaVu Serif"],
            "font.size": 13.8,
            "axes.titlesize": 15.5,
            "axes.labelsize": 12.8,
            "xtick.labelsize": 11.8,
            "ytick.labelsize": 11.8,
            "legend.fontsize": 11.2,
            "mathtext.fontset": "stix",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def save(fig: plt.Figure, name: str, pad: float = 0.035) -> None:
    fig.savefig(FIG / name, format="pdf", bbox_inches="tight", pad_inches=pad)
    plt.close(fig)


def rounded(ax, x, y, w, h, fc, ec=None, lw=0.9, radius=0.04, z=1):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        facecolor=fc,
        edgecolor=ec or fc,
        linewidth=lw,
        zorder=z,
    )
    ax.add_patch(patch)
    return patch


def arrow(ax, x1, y1, x2, y2, color=None, lw=1.0, scale=10):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=scale,
            linewidth=lw,
            color=color or COLORS["muted"],
            shrinkA=3,
            shrinkB=3,
        )
    )


def framework() -> None:
    fig, ax = plt.subplots(figsize=(6.70, 2.78))
    ax.set_xlim(0, 10)
    ax.set_ylim(0.42, 3.03)
    ax.axis("off")

    stages = [
        ("1", "Benchmark", "Executable\nrelease", "run vector", "finite matrix", COLORS["bench"], COLORS["softblue"]),
        ("2", "Provenance", "White-box\ncell", "carrier rec.", "admitted cells", COLORS["sem"], COLORS["softgreen"]),
        ("3", "Audit", "Black-box\nAPI", "transcript", "null audit", COLORS["audit"], COLORS["softamber"]),
        ("4", "Attribution", "Owner\nregistry", "owner witness", "source-bound", COLORS["probe"], COLORS["softviolet"]),
        ("5", "Triage", "Hidden\nmarker", "risk row", "selective", COLORS["seal"], COLORS["softrose"]),
    ]

    left, right = 0.16, 9.84
    y0, h = 1.47, 1.37
    gap = 0.044
    stage_w = (right - left - gap * (len(stages) - 1)) / len(stages)

    for i, (num, name, access, evidence, claim, color, fill) in enumerate(stages):
        x = left + i * (stage_w + gap)
        w = stage_w
        rounded(ax, x, y0, w, h, "white", COLORS["line"], lw=0.82, radius=0.010)
        ax.add_patch(Rectangle((x, y0 + h - 0.27), w, 0.27, facecolor=color, edgecolor=color, linewidth=0))
        ax.text(x + 0.16, y0 + h - 0.135, num, ha="center", va="center", fontsize=9.7, fontweight="bold", color="white")
        ax.text(x + 0.34, y0 + h - 0.135, name, ha="left", va="center", fontsize=10.1, fontweight="bold", color="white")
        ax.text(x + 0.15, y0 + 0.76, access, ha="left", va="center", fontsize=10.8, color=COLORS["muted"], linespacing=0.91)
        ax.plot([x + 0.13, x + w - 0.13], [y0 + 0.52, y0 + 0.52], color=COLORS["line"], lw=0.42)
        ax.text(x + 0.15, y0 + 0.34, evidence, ha="left", va="center", fontsize=10.35, color=COLORS["ink"])
        ax.text(x + 0.15, y0 + 0.13, claim, ha="left", va="center", fontsize=10.15, color=color)
        if i < len(stages) - 1:
            arrow(ax, x + w + 0.012, y0 + 0.81, x + w + gap - 0.012, y0 + 0.81, color=COLORS["muted"], lw=0.68, scale=7)

    ax.add_patch(Rectangle((left, 0.56), right - left, 0.62, facecolor=COLORS["panel"], edgecolor=COLORS["line"], linewidth=0.62))
    ax.text(left + 0.15, 1.005, "Shared evidence contract", ha="left", va="center", fontsize=10.45, fontweight="bold", color=COLORS["ink"])
    ax.text(left + 0.15, 0.76, "row admitted pre-outcome", ha="left", va="center", fontsize=9.10, color=COLORS["muted"])
    tokens = ["denom.", "controls", "hashes", "versions", "CI", "blocked"]
    token_x0 = left + 3.76
    token_w = (right - token_x0 - 0.06) / len(tokens)
    for i, token in enumerate(tokens):
        x = token_x0 + i * token_w
        ax.add_patch(Rectangle((x, 0.72), token_w - 0.045, 0.30, facecolor="white", edgecolor=COLORS["line"], linewidth=0.42))
        ax.text(x + token_w / 2 - 0.022, 0.87, token, ha="center", va="center", fontsize=9.2, color=COLORS["muted"])

    save(fig, "watermarkscope_framework_map.pdf", pad=0.025)


def evidence_contract_stack() -> None:
    fig, ax = plt.subplots(figsize=(7.70, 3.16))
    ax.set_xlim(0, 10)
    ax.set_ylim(0.30, 4.08)
    ax.axis("off")

    top_y = 3.03
    node_w = 1.86
    nodes = [
        (0.40, "Candidate", "task, hashes,\nversions", COLORS["softblue"]),
        (2.56, "Admission", "metadata only;\nscore hidden", COLORS["softgreen"]),
        (5.62, "Decision", "apply $\\delta_j$;\ncount outcome", COLORS["softamber"]),
        (7.78, "Report", "$k/n$, CI,\nboundary", COLORS["softviolet"]),
    ]
    for i, (x, head, body, fill) in enumerate(nodes):
        rounded(ax, x, top_y, node_w, 0.78, "white", COLORS["line"], lw=0.72, radius=0.012)
        ax.add_patch(Rectangle((x, top_y + 0.68), node_w, 0.10, facecolor=fill, edgecolor=fill, linewidth=0))
        ax.text(x + node_w / 2, top_y + 0.585, head, ha="center", va="center", fontsize=10.95, fontweight="bold", color=COLORS["ink"])
        ax.text(x + node_w / 2, top_y + 0.160, body, ha="center", va="center", fontsize=8.85, color=COLORS["muted"], linespacing=0.88)

    arrow(ax, nodes[0][0] + node_w + 0.05, top_y + 0.39, nodes[1][0] - 0.07, top_y + 0.39, color=COLORS["muted"], lw=0.74, scale=8)
    arrow(ax, nodes[1][0] + node_w + 0.08, top_y + 0.39, nodes[2][0] - 0.10, top_y + 0.39, color=COLORS["contract"], lw=0.86, scale=8)
    arrow(ax, nodes[2][0] + node_w + 0.05, top_y + 0.39, nodes[3][0] - 0.07, top_y + 0.39, color=COLORS["muted"], lw=0.74, scale=8)

    support_x, support_y, support_w, support_h = 0.58, 1.55, 3.66, 0.76
    denom_x, denom_y, denom_w, denom_h = 5.03, 1.55, 4.24, 0.76
    rounded(ax, support_x, support_y, support_w, support_h, "white", COLORS["line"], lw=0.70, radius=0.010)
    ax.add_patch(Rectangle((support_x, support_y), 0.10, support_h, facecolor="#991B1B", edgecolor="#991B1B", linewidth=0))
    ax.text(support_x + support_w / 2, support_y + 0.47, "Support-only ledger", ha="center", va="center", fontsize=10.8, fontweight="bold", color="#991B1B")
    ax.text(support_x + support_w / 2, support_y + 0.19, "preserved for audit; no numerator effect", ha="center", va="center", fontsize=8.72, color=COLORS["ink"])

    rounded(ax, denom_x, denom_y, denom_w, denom_h, "white", COLORS["line"], lw=0.70, radius=0.010)
    ax.add_patch(Rectangle((denom_x, denom_y), 0.10, denom_h, facecolor=COLORS["contract"], edgecolor=COLORS["contract"], linewidth=0))
    ax.text(denom_x + denom_w / 2, denom_y + 0.47, "Claim-bearing denominator", ha="center", va="center", fontsize=10.8, fontweight="bold", color=COLORS["contract"])
    ax.text(denom_x + denom_w / 2, denom_y + 0.19, "misses, abstentions, and failures stay counted", ha="center", va="center", fontsize=9.00, color=COLORS["ink"])

    # Admission has exactly two visible outcomes. The short, non-crossing elbows
    # show the logic: failed admission is preserved as support; admitted rows are
    # locked before the decision is evaluated.
    admission_center = nodes[1][0] + node_w / 2
    admission_bottom = top_y
    support_center = support_x + support_w / 2
    denom_center = denom_x + denom_w / 2
    lane_y = 2.58
    ax.plot([admission_center, admission_center], [admission_bottom, lane_y], color=COLORS["gray"], lw=0.70, solid_capstyle="butt")
    ax.plot([admission_center, support_center], [lane_y, lane_y], color=COLORS["gray"], lw=0.70, solid_capstyle="butt")
    ax.add_patch(FancyArrowPatch((support_center, lane_y), (support_center, support_y + support_h + 0.03),
                                 arrowstyle="-|>", mutation_scale=8, color=COLORS["gray"], linewidth=0.70))
    ax.text(2.36, lane_y + 0.12, "fails admission", ha="center", va="center", fontsize=9.0,
            color=COLORS["muted"], bbox=dict(facecolor="white", edgecolor="none", pad=0.35))

    pass_y = lane_y - 0.24
    ax.plot([admission_center, denom_center], [pass_y, pass_y],
            color=COLORS["contract"], lw=0.84, solid_capstyle="butt")
    ax.add_patch(FancyArrowPatch((denom_center, pass_y), (denom_center, denom_y + denom_h + 0.03),
                                 arrowstyle="-|>", mutation_scale=8, color=COLORS["contract"], linewidth=0.84))
    ax.text(5.45, pass_y + 0.10, "passes admission", ha="center", va="center", fontsize=9.0,
            color=COLORS["contract"], bbox=dict(facecolor="white", edgecolor="none", pad=0.35))

    arrow(ax, denom_x + denom_w * 0.72, denom_y, denom_x + denom_w * 0.72, 0.98, color=COLORS["contract"], lw=0.68, scale=7)

    rounded(ax, 1.14, 0.40, 7.72, 0.48, COLORS["panel"], COLORS["line"], lw=0.55, radius=0.006)
    ax.text(5.00, 0.64, "Invariant: no outcome pruning, no support promotion, abstentions counted",
            ha="center", va="center", fontsize=9.45, color=COLORS["muted"])

    save(fig, "evidence_contract_stack.pdf", pad=0.025)


def claim_boundary_matrix() -> None:
    fig, ax = plt.subplots(figsize=(7.70, 2.46))
    ax.set_xlim(0, 10)
    ax.set_ylim(1.46, 4.60)
    ax.axis("off")

    cols = [0.25, 1.72, 3.82, 6.04]
    widths = [1.30, 1.92, 2.03, 3.62]
    headers = ["Stage", "Evidence", "Allowed", "Blocked overclaim"]
    for x, w, h in zip(cols, widths, headers):
        ax.add_patch(Rectangle((x, 4.18), w, 0.34, facecolor=COLORS["panel2"], edgecolor=COLORS["line"], linewidth=0.58))
        ax.text(x + 0.08, 4.35, h, ha="left", va="center", fontsize=11.1, fontweight="bold", color=COLORS["ink"])

    rows = [
        ("Benchmark", "run vector", "finite release", "universal ranking"),
        ("Provenance", "carrier recovery", "admitted cells", "all models"),
        ("Audit", "transcript hash", "sparse audit", "prevalence proof"),
        ("Attribution", "owner witness", "single owner", "open-world authorship"),
        ("Triage", "hidden marker row", "risk routing", "safety certificate"),
    ]
    y = 3.70
    colors = [COLORS["bench"], COLORS["sem"], COLORS["audit"], COLORS["probe"], COLORS["seal"]]
    for i, row in enumerate(rows):
        fc = "white" if i % 2 == 0 else COLORS["panel"]
        for x, w in zip(cols, widths):
            ax.add_patch(Rectangle((x, y), w, 0.44, facecolor=fc, edgecolor=COLORS["line"], linewidth=0.42))
        ax.add_patch(Rectangle((cols[0], y), 0.08, 0.44, facecolor=colors[i], edgecolor=colors[i], linewidth=0))
        ax.text(cols[0] + 0.15, y + 0.22, row[0], ha="left", va="center", fontsize=9.85, fontweight="bold", color=COLORS["ink"])
        ax.text(cols[1] + 0.08, y + 0.22, row[1], ha="left", va="center", fontsize=9.85, color=COLORS["ink"])
        ax.text(cols[2] + 0.08, y + 0.22, "OK", ha="left", va="center", fontsize=8.85, fontweight="bold", color=COLORS["contract"])
        ax.text(cols[2] + 0.42, y + 0.22, row[2], ha="left", va="center", fontsize=9.75, fontweight="bold", color=COLORS["contract"])
        ax.add_patch(Rectangle((cols[3], y), widths[3], 0.44, facecolor="#FFF1F2", edgecolor=COLORS["line"], linewidth=0.42, alpha=0.45))
        ax.text(cols[3] + 0.08, y + 0.22, "NO", ha="left", va="center", fontsize=8.85, fontweight="bold", color="#991B1B")
        ax.text(cols[3] + 0.44, y + 0.22, row[3], ha="left", va="center", fontsize=9.75, color="#991B1B")
        y -= 0.50

    save(fig, "claim_boundary_matrix.pdf", pad=0.025)


def tradeoff() -> None:
    rows = [
        ("SWEET", 0.3361, 0.6467, 0.3827, 0.0000, COLORS["bench"]),
        ("EWD", 0.2645, 0.6467, 0.3761, 0.0000, COLORS["sem"]),
        ("STONE", 0.3536, 0.6509, 0.3504, 0.1465, COLORS["audit"]),
        ("KGW", 0.4439, 0.6476, 0.3498, 0.0000, COLORS["probe"]),
    ]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.58, 3.46), gridspec_kw={"width_ratios": [1.22, 1.0], "wspace": 0.34})
    for name, robust, utility, score, fpr, color in rows:
        size = 230 + 650 * score
        marker = "X" if fpr > 0 else "o"
        ax.scatter(robust, utility, s=size, color=color, alpha=0.86, marker=marker, edgecolor="white", linewidth=0.8)
        offsets = {"EWD": (-0.020, 0.00033), "KGW": (-0.018, 0.00033), "STONE": (0.006, 0.00046), "SWEET": (0.006, 0.00028)}
        dx, dy = offsets[name]
        ax.text(robust + dx, utility + dy, name, fontsize=14.2, fontweight="bold", color=COLORS["ink"])
    ax.set_xlabel("Robust detection under executable attacks")
    ax.set_ylabel("Executable utility")
    ax.set_xlim(0.23, 0.47)
    ax.set_ylim(0.6460, 0.6520)
    ax.grid(axis="both", color=COLORS["line"], linewidth=0.55, alpha=0.65)

    rows_score = sorted(rows, key=lambda r: r[3])
    names = [r[0] for r in rows_score]
    scores = [r[3] for r in rows_score]
    fprs = [r[4] for r in rows_score]
    colors = [r[5] for r in rows_score]
    y = range(len(rows_score))
    ax2.barh(y, scores, color=colors, alpha=0.86, height=0.56)
    ax2.set_yticks(y)
    ax2.set_yticklabels(names, fontweight="bold")
    ax2.set_xlim(0.0, 0.45)
    ax2.set_xlabel("Release scalar")
    ax2.grid(axis="x", color=COLORS["line"], linewidth=0.55, alpha=0.7)
    for yi, score, fpr in zip(y, scores, fprs):
        suffix = "" if fpr == 0 else "  (FPR 14.65%)"
        ax2.text(score + 0.010, yi, f"{score:.3f}{suffix}", va="center", fontsize=12.4, color=COLORS["ink"])
    ax.text(0.03, 0.93, "X = nonzero FPR", transform=ax.transAxes,
            ha="left", va="center", fontsize=11.4, color=COLORS["muted"],
            bbox=dict(facecolor="white", edgecolor=COLORS["line"], linewidth=0.25, pad=1.6))
    save(fig, "codemarkbench_tradeoff.pdf", pad=0.035)


def ablation() -> None:
    fig, (ax, ax2) = plt.subplots(
        1,
        2,
        figsize=(7.75, 3.70),
        gridspec_kw={"width_ratios": [1.08, 1.32], "wspace": 0.60},
    )
    main_rows = [
        ("Positive recovery", 23342, 24000, COLORS["sem"]),
        ("Miss/abstain/reject", 658, 24000, COLORS["gray"]),
        ("Negative hits", 0, 48000, COLORS["seal"]),
    ]
    y = range(len(main_rows))[::-1]
    names = []
    for yi, (name, k, n, color) in zip(y, main_rows):
        names.append(name)
        frac = k / n if n else 0
        ax.barh(yi, 1.0, color=COLORS["panel2"], height=0.46)
        if frac > 0:
            ax.barh(yi, frac, color=color, height=0.46)
        label = f"{k:,}/{n:,}" if k else f"0/{n:,}"
        ax.text(0.965, yi, label, va="center", ha="right", fontsize=11.45, color=COLORS["ink"],
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.82, pad=0.7))
    ax.set_xlim(0, 1.05)
    ax.set_ylim(-0.55, 2.55)
    ax.set_yticks(list(y))
    ax.set_yticklabels(names, fontsize=12.1, fontweight="bold")
    ax.set_xticks([0, 0.5, 1.0])
    ax.set_xticklabels(["0", "50%", "100%"])
    ax.grid(axis="x", color=COLORS["line"], linewidth=0.55, alpha=0.6)

    arms = ["Full", "AST-only", "CFG-only", "SSA-only", "Drop AST", "Drop CFG", "Drop SSA", "ECC-off", "Unkeyed"]
    counts = [4800] * len(arms)
    yy = list(range(len(arms)))[::-1]
    colors = [COLORS["sem"]] + [COLORS["gray"]] * (len(arms) - 1)
    ax2.barh(yy, counts, color=colors, height=0.48, alpha=0.88)
    ax2.set_yticks(yy)
    ax2.set_yticklabels(arms, fontsize=12.0)
    ax2.set_xlim(0, 5200)
    ax2.set_xlabel("Generation-changing rows")
    ax2.grid(axis="x", color=COLORS["line"], linewidth=0.55, alpha=0.7)
    for yi, count in zip(yy, counts):
        ax2.text(count + 75, yi, "done 4,800", va="center", fontsize=11.5, color=COLORS["ink"])
    fig.subplots_adjust(bottom=0.14, wspace=0.60)
    save(fig, "semcodebook_ablation.pdf", pad=0.035)


def blackbox() -> None:
    rows = [
        {
            "name": "CodeDye",
            "color": COLORS["audit"],
            "main_label": "live signal",
            "main": (6, 300),
            "controls": [("pos.", 170, 300), ("neg.", 0, 300)],
            "reading": "null-audit",
            "blocked": "prevalence",
        },
        {
            "name": "ProbeTrace",
            "color": COLORS["probe"],
            "main_label": "APIS",
            "main": (300, 300),
            "controls": [("false owner", 0, 1200), ("support", 900, 900)],
            "reading": "source-bound",
            "blocked": "open-world",
        },
        {
            "name": "SealAudit",
            "color": COLORS["seal"],
            "main_label": "decisive",
            "main": (81, 960),
            "controls": [("review", 879, 960), ("unsafe", 0, 960)],
            "reading": "selective triage",
            "blocked": "certificate",
        },
    ]

    fig, ax = plt.subplots(figsize=(7.72, 3.26))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0.26, 3.02)
    ax.axis("off")

    header_y = 2.78
    col_module, col_main, col_ctrl, col_count, col_claim = 0.045, 0.224, 0.466, 0.602, 0.770
    for x, label in [(col_module, "Module"), (col_main, "Main evidence"), (col_ctrl, "Control"), (col_count, "Count"), (col_claim, "Claim boundary")]:
        ax.text(x, header_y, label, ha="left", va="center", fontsize=10.0, fontweight="bold", color=COLORS["muted"])

    y_values = [2.30, 1.49, 0.68]
    for y, row in zip(y_values, rows):
        color = row["color"]
        ax.add_patch(Rectangle((0.02, y - 0.30), 0.96, 0.60, facecolor="white", edgecolor=COLORS["line"], linewidth=0.45))
        ax.add_patch(Rectangle((0.02, y - 0.30), 0.012, 0.60, facecolor=color, edgecolor=color, linewidth=0))
        ax.text(col_module, y + 0.10, row["name"], ha="left", va="center", fontsize=11.0, fontweight="bold", color=COLORS["ink"])
        ax.text(col_module, y - 0.12, row["reading"], ha="left", va="center", fontsize=9.35, color=color)

        k, n = row["main"]
        rate = 100.0 * k / n
        ax.text(col_main, y + 0.12, row["main_label"], ha="left", va="center", fontsize=9.45, color=COLORS["ink"])
        ax.text(col_main, y - 0.10, f"{k:,}/{n:,} ({rate:.1f}%)", ha="left", va="center", fontsize=10.0, fontweight="bold", color=COLORS["ink"])

        cx = col_ctrl
        for i, (label, ck, cn) in enumerate(row["controls"]):
            yy = y + 0.11 - i * 0.24
            ax.text(cx, yy, label, ha="left", va="center", fontsize=9.05, color=COLORS["muted"])
            ax.text(col_count, yy, f"{ck:,}/{cn:,}", ha="left", va="center", fontsize=9.25, color=COLORS["ink"])

        ax.text(col_claim, y + 0.10, f"OK {row['reading']}", ha="left", va="center", fontsize=9.05, fontweight="bold", color=COLORS["contract"])
        ax.text(col_claim, y - 0.12, f"NO {row['blocked']}", ha="left", va="center", fontsize=8.9, color="#991B1B")

    save(fig, "blackbox_outcomes.pdf", pad=0.025)


def main() -> None:
    configure()
    framework()
    evidence_contract_stack()
    claim_boundary_matrix()
    tradeoff()
    ablation()
    blackbox()
    print("Rebuilt paper figures.")


if __name__ == "__main__":
    main()
