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
            "font.size": 12.5,
            "axes.titlesize": 14.8,
            "axes.labelsize": 11.7,
            "xtick.labelsize": 10.5,
            "ytick.labelsize": 10.5,
            "legend.fontsize": 10.0,
            "mathtext.fontset": "stix",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(FIG / name, format="pdf", bbox_inches="tight", pad_inches=0.075)
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
    fig, ax = plt.subplots(figsize=(7.72, 3.82))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.90)
    ax.axis("off")

    stages = [
        ("1", "Benchmark", "Executable\nrelease", "run vector", "finite matrix", COLORS["bench"], COLORS["softblue"]),
        ("2", "Provenance", "White-box\nmodel cell", "carrier recovery", "admitted cells", COLORS["sem"], COLORS["softgreen"]),
        ("3", "Audit", "Black-box\nprovider", "transcript hash", "null-audit", COLORS["audit"], COLORS["softamber"]),
        ("4", "Attribution", "Owner\nregistry", "owner witness", "source-bound", COLORS["probe"], COLORS["softviolet"]),
        ("5", "Triage", "Marker-hidden\nrisk case", "risk row", "selective triage", COLORS["seal"], COLORS["softrose"]),
    ]

    left, right = 0.36, 9.64
    y0, h = 2.18, 1.68
    stage_w = (right - left) / len(stages)

    ax.text(left, 4.52, "WatermarkScope evidence lifecycle", ha="left", va="center", fontsize=12.4, fontweight="bold", color=COLORS["ink"])
    ax.text(right, 4.52, "new access -> new evidence object -> new claim boundary", ha="right", va="center", fontsize=8.3, color=COLORS["muted"])
    ax.plot([left, right], [4.26, 4.26], color=COLORS["line"], lw=0.70)

    for i, (num, name, access, evidence, claim, color, fill) in enumerate(stages):
        x = left + i * stage_w
        w = stage_w - 0.16
        rounded(ax, x, y0, w, h, "white", COLORS["line"], lw=0.74, radius=0.010)
        ax.add_patch(Rectangle((x, y0 + h - 0.12), w, 0.12, facecolor=color, edgecolor=color, linewidth=0))
        ax.text(x + 0.20, y0 + h - 0.36, num, ha="center", va="center", fontsize=8.5, fontweight="bold", color="white",
                bbox=dict(boxstyle="circle,pad=0.20", facecolor=color, edgecolor=color, linewidth=0))
        ax.text(x + 0.46, y0 + h - 0.36, name, ha="left", va="center", fontsize=8.15, fontweight="bold", color=COLORS["ink"])
        ax.text(x + 0.16, y0 + 0.90, access, ha="left", va="center", fontsize=6.85, color=COLORS["muted"], linespacing=0.92)
        ax.plot([x + 0.14, x + w - 0.14], [y0 + 0.64, y0 + 0.64], color=COLORS["line"], lw=0.42)
        ax.text(x + 0.16, y0 + 0.46, evidence, ha="left", va="center", fontsize=6.82, color=COLORS["ink"])
        ax.text(x + 0.16, y0 + 0.20, claim, ha="left", va="center", fontsize=6.78, color=color)
        if i < len(stages) - 1:
            arrow(ax, x + w + 0.04, y0 + 0.81, x + stage_w - 0.05, y0 + 0.81, color=COLORS["muted"], lw=0.70, scale=7)

    ax.add_patch(Rectangle((left, 0.78), right - left, 0.82, facecolor=COLORS["panel"], edgecolor=COLORS["line"], linewidth=0.62))
    ax.text(left + 0.16, 1.33, "Shared evidence contract", ha="left", va="center", fontsize=8.55, fontweight="bold", color=COLORS["ink"])
    ax.text(left + 0.16, 1.06, "row admitted before outcome", ha="left", va="center", fontsize=6.75, color=COLORS["muted"])
    tokens = ["denominator", "controls", "hashes", "versions", "CI/bounds", "forbidden claim"]
    token_x0 = left + 2.65
    token_w = (right - token_x0 - 0.06) / len(tokens)
    for i, token in enumerate(tokens):
        x = token_x0 + i * token_w
        ax.add_patch(Rectangle((x, 1.00), token_w - 0.05, 0.30, facecolor="white", edgecolor=COLORS["line"], linewidth=0.42))
        ax.text(x + token_w / 2 - 0.025, 1.15, token, ha="center", va="center", fontsize=5.9, color=COLORS["muted"])
    ax.text(left, 0.42, "Reading rule: do not carry a claim across stages without admitting a new evidence object.",
            ha="left", va="center", fontsize=6.75, color=COLORS["muted"])

    save(fig, "watermarkscope_framework_map.pdf")


def evidence_contract_stack() -> None:
    fig, ax = plt.subplots(figsize=(7.70, 3.42))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.02)
    ax.axis("off")

    ax.text(0.36, 4.68, "Row admission contract", ha="left", va="center", fontsize=11.2, fontweight="bold", color=COLORS["ink"])
    ax.text(9.64, 4.68, "outcomes are interpreted only after row admission", ha="right", va="center", fontsize=8.2, color=COLORS["muted"])
    ax.plot([0.36, 9.64], [4.46, 4.46], color=COLORS["line"], lw=0.62)

    x0, x1 = 0.48, 9.52
    top_y = 3.42
    node_w = 1.72
    nodes = [
        (0.54, "Candidate", "task, hashes,\nversions", COLORS["softblue"]),
        (2.74, "Admission", "metadata only;\nscore hidden", COLORS["softgreen"]),
        (6.20, "Decision", "apply $\\delta_j$;\ncount outcome", COLORS["softamber"]),
        (8.24, "Report", "$k/n$, CI,\nboundary", COLORS["softviolet"]),
    ]
    for i, (x, head, body, fill) in enumerate(nodes):
        rounded(ax, x, top_y, node_w, 0.74, "white", COLORS["line"], lw=0.72, radius=0.012)
        ax.add_patch(Rectangle((x, top_y + 0.64), node_w, 0.10, facecolor=fill, edgecolor=fill, linewidth=0))
        ax.text(x + node_w / 2, top_y + 0.48, head, ha="center", va="center", fontsize=8.35, fontweight="bold", color=COLORS["ink"])
        ax.text(x + node_w / 2, top_y + 0.22, body, ha="center", va="center", fontsize=6.95, color=COLORS["muted"], linespacing=0.90)
        if i in (0, 2):
            arrow(ax, x + node_w + 0.05, top_y + 0.37, nodes[i + 1][0] - 0.07, top_y + 0.37, color=COLORS["muted"], lw=0.74, scale=8)

    # Clean branch after pre-outcome admission.
    ax.plot([x0, x1], [2.92, 2.92], color=COLORS["line"], lw=0.55)
    ax.text(2.26, 2.92, "fails pre-outcome rule", ha="center", va="center", fontsize=6.5, color=COLORS["muted"],
            bbox=dict(facecolor="white", edgecolor="none", pad=0.6))
    ax.text(6.02, 2.92, "admitted rows only", ha="center", va="center", fontsize=6.7, color=COLORS["contract"],
            bbox=dict(facecolor="white", edgecolor="none", pad=0.6))

    rounded(ax, 0.78, 1.64, 3.64, 0.78, "white", COLORS["line"], lw=0.70, radius=0.010)
    ax.add_patch(Rectangle((0.78, 1.64), 0.10, 0.78, facecolor="#991B1B", edgecolor="#991B1B", linewidth=0))
    ax.text(2.60, 2.10, "Support-only ledger", ha="center", va="center", fontsize=8.55, fontweight="bold", color="#991B1B")
    ax.text(2.60, 1.82, "preserved for audit; no numerator effect", ha="center", va="center", fontsize=6.95, color=COLORS["ink"])

    rounded(ax, 5.02, 1.64, 4.32, 0.78, "white", COLORS["line"], lw=0.70, radius=0.010)
    ax.add_patch(Rectangle((5.02, 1.64), 0.10, 0.78, facecolor=COLORS["contract"], edgecolor=COLORS["contract"], linewidth=0))
    ax.text(7.18, 2.10, "Claim-bearing denominator", ha="center", va="center", fontsize=8.55, fontweight="bold", color=COLORS["contract"])
    ax.text(7.18, 1.82, "misses, abstentions, and failures stay counted", ha="center", va="center", fontsize=6.95, color=COLORS["ink"])

    # Orthogonal connectors avoid crossing the figure.
    ax.plot([3.60, 3.60, 2.60, 2.60], [3.42, 2.92, 2.92, 2.48], color=COLORS["gray"], lw=0.70)
    ax.add_patch(FancyArrowPatch((2.60, 2.50), (2.60, 2.42), arrowstyle="-|>", mutation_scale=8, color=COLORS["gray"], linewidth=0.70))
    ax.plot([4.46, 4.46, 7.18, 7.18], [3.42, 2.92, 2.92, 2.48], color=COLORS["contract"], lw=0.78)
    ax.add_patch(FancyArrowPatch((7.18, 2.50), (7.18, 2.42), arrowstyle="-|>", mutation_scale=8, color=COLORS["contract"], linewidth=0.78))
    arrow(ax, 7.18, 1.64, 7.18, 0.98, color=COLORS["contract"], lw=0.68, scale=7)

    rounded(ax, 1.14, 0.40, 7.72, 0.48, COLORS["panel"], COLORS["line"], lw=0.55, radius=0.006)
    ax.text(5.00, 0.64, "Invariant: no outcome pruning, no support promotion, abstentions counted",
            ha="center", va="center", fontsize=7.05, color=COLORS["muted"])

    save(fig, "evidence_contract_stack.pdf")


def claim_boundary_matrix() -> None:
    fig, ax = plt.subplots(figsize=(7.45, 3.18))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.12)
    ax.axis("off")

    ax.text(0.30, 4.86, "Claim Boundaries by Lifecycle Stage", ha="left", va="center", fontsize=10.4, fontweight="bold", color=COLORS["ink"])
    ax.text(9.70, 4.86, "one stage, one evidence object, one bounded claim", ha="right", va="center", fontsize=7.9, color=COLORS["muted"])
    ax.plot([0.30, 9.70], [4.62, 4.62], color=COLORS["line"], lw=0.62)

    cols = [0.30, 2.02, 4.18, 6.42]
    widths = [1.46, 1.90, 2.00, 3.28]
    headers = ["Stage", "Evidence", "Allowed", "Blocked overclaim"]
    for x, w, h in zip(cols, widths, headers):
        ax.add_patch(Rectangle((x, 4.18), w, 0.34, facecolor=COLORS["panel2"], edgecolor=COLORS["line"], linewidth=0.58))
        ax.text(x + 0.08, 4.35, h, ha="left", va="center", fontsize=8.15, fontweight="bold", color=COLORS["ink"])

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
        ax.text(cols[0] + 0.16, y + 0.22, row[0], ha="left", va="center", fontsize=7.75, fontweight="bold", color=COLORS["ink"])
        ax.text(cols[1] + 0.08, y + 0.22, row[1], ha="left", va="center", fontsize=7.70, color=COLORS["ink"])
        ax.text(cols[2] + 0.08, y + 0.22, "OK", ha="left", va="center", fontsize=6.85, fontweight="bold", color=COLORS["contract"])
        ax.text(cols[2] + 0.38, y + 0.22, row[2], ha="left", va="center", fontsize=7.65, fontweight="bold", color=COLORS["contract"])
        ax.add_patch(Rectangle((cols[3], y), widths[3], 0.44, facecolor="#FFF1F2", edgecolor=COLORS["line"], linewidth=0.42, alpha=0.45))
        ax.text(cols[3] + 0.08, y + 0.22, "NO", ha="left", va="center", fontsize=6.85, fontweight="bold", color="#991B1B")
        ax.text(cols[3] + 0.38, y + 0.22, row[3], ha="left", va="center", fontsize=7.65, color="#991B1B")
        y -= 0.50

    rounded(ax, 0.66, 0.48, 8.68, 0.52, COLORS["panel"], COLORS["line"], lw=0.52, radius=0.006)
    ax.text(5.00, 0.74, "A broader claim needs a new admitted surface; it cannot borrow another stage's denominator.",
            ha="center", va="center", fontsize=7.10, color=COLORS["muted"])
    save(fig, "claim_boundary_matrix.pdf")


def tradeoff() -> None:
    rows = [
        ("SWEET", 0.3361, 0.6467, 0.3827, 0.0000, COLORS["bench"]),
        ("EWD", 0.2645, 0.6467, 0.3761, 0.0000, COLORS["sem"]),
        ("STONE", 0.3536, 0.6509, 0.3504, 0.1465, COLORS["audit"]),
        ("KGW", 0.4439, 0.6476, 0.3498, 0.0000, COLORS["probe"]),
    ]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.35, 3.65), gridspec_kw={"width_ratios": [1.22, 1.0], "wspace": 0.36})
    for name, robust, utility, score, fpr, color in rows:
        size = 230 + 650 * score
        marker = "X" if fpr > 0 else "o"
        ax.scatter(robust, utility, s=size, color=color, alpha=0.86, marker=marker, edgecolor="white", linewidth=0.8)
        offsets = {"EWD": (-0.020, 0.00033), "KGW": (-0.018, 0.00033), "STONE": (0.006, 0.00046), "SWEET": (0.006, 0.00028)}
        dx, dy = offsets[name]
        ax.text(robust + dx, utility + dy, name, fontsize=10.9, fontweight="bold", color=COLORS["ink"])
    ax.set_title("Executable Tradeoff", pad=7, fontweight="bold", fontsize=12.3)
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
    ax2.set_title("Release Scalar Context", pad=7, fontweight="bold", fontsize=12.3)
    ax2.grid(axis="x", color=COLORS["line"], linewidth=0.55, alpha=0.7)
    for yi, score, fpr in zip(y, scores, fprs):
        suffix = "" if fpr == 0 else "  (FPR 14.65%)"
        ax2.text(score + 0.010, yi, f"{score:.3f}{suffix}", va="center", fontsize=9.4, color=COLORS["ink"])
    ax.text(0.232, 0.65155, "X = nonzero negative-control FPR", ha="left", va="center", fontsize=8.0, color=COLORS["muted"])
    save(fig, "codemarkbench_tradeoff.pdf")


def ablation() -> None:
    fig, (ax, ax2) = plt.subplots(
        1,
        2,
        figsize=(7.35, 3.85),
        gridspec_kw={"width_ratios": [1.08, 1.28], "wspace": 0.52},
    )
    main_rows = [
        ("Positive recovery", 23342, 24000, COLORS["sem"]),
        ("Miss/abstain/reject", 658, 24000, COLORS["gray"]),
        ("Negative hits", 0, 48000, COLORS["seal"]),
    ]
    y = range(len(main_rows))[::-1]
    for yi, (name, k, n, color) in zip(y, main_rows):
        frac = k / n if n else 0
        ax.barh(yi, 1.0, color=COLORS["panel2"], height=0.46)
        if frac > 0:
            ax.barh(yi, frac, color=color, height=0.46)
        ax.text(-0.02, yi, name, va="center", ha="right", fontsize=9.3, fontweight="bold", color=COLORS["ink"])
        label = f"{k:,}/{n:,}" if k else f"0/{n:,}"
        ax.text(1.02, yi, label, va="center", ha="left", fontsize=9.5, color=COLORS["ink"])
    ax.set_xlim(-0.36, 1.20)
    ax.set_ylim(-0.55, 2.55)
    ax.set_yticks([])
    ax.set_xticks([0, 0.5, 1.0])
    ax.set_xticklabels(["0", "50%", "100%"])
    ax.set_title("Main Claim Surface", pad=7, fontweight="bold")
    ax.grid(axis="x", color=COLORS["line"], linewidth=0.55, alpha=0.6)

    arms = ["Full", "AST-only", "CFG-only", "SSA-only", "Drop AST", "Drop CFG", "Drop SSA", "ECC-off", "Unkeyed"]
    counts = [4800] * len(arms)
    yy = list(range(len(arms)))[::-1]
    colors = [COLORS["sem"]] + [COLORS["gray"]] * (len(arms) - 1)
    ax2.barh(yy, counts, color=colors, height=0.48, alpha=0.88)
    ax2.set_yticks(yy)
    ax2.set_yticklabels(arms, fontsize=9.5)
    ax2.set_xlim(0, 5200)
    ax2.set_xlabel("Generation-changing rows")
    ax2.set_title("Ablation Coverage", pad=7, fontweight="bold")
    ax2.grid(axis="x", color=COLORS["line"], linewidth=0.55, alpha=0.7)
    for yi, count in zip(yy, counts):
        ax2.text(count + 75, yi, "done 4,800", va="center", fontsize=8.8, color=COLORS["ink"])
    fig.subplots_adjust(bottom=0.16, wspace=0.52)
    save(fig, "semcodebook_ablation.pdf")


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

    fig, ax = plt.subplots(figsize=(7.45, 3.28))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(-0.26, 3.24)
    ax.axis("off")

    ax.text(0.02, 3.00, "Deployment Evidence Is Access-Specific", ha="left", va="center",
            fontsize=10.7, fontweight="bold", color=COLORS["ink"])
    ax.text(0.98, 3.00, "main row + controls + blocked overclaim", ha="right", va="center",
            fontsize=7.55, color=COLORS["muted"])
    ax.plot([0.02, 0.98], [2.82, 2.82], color=COLORS["line"], lw=0.58)

    header_y = 2.58
    for x, label in [(0.03, "Module"), (0.22, "Main evidence"), (0.51, "Controls"), (0.78, "Claim boundary")]:
        ax.text(x, header_y, label, ha="left", va="center", fontsize=7.60, fontweight="bold", color=COLORS["muted"])

    y_values = [2.13, 1.32, 0.51]
    for y, row in zip(y_values, rows):
        color = row["color"]
        ax.add_patch(Rectangle((0.02, y - 0.30), 0.96, 0.60, facecolor="white", edgecolor=COLORS["line"], linewidth=0.45))
        ax.add_patch(Rectangle((0.02, y - 0.30), 0.012, 0.60, facecolor=color, edgecolor=color, linewidth=0))
        ax.text(0.045, y + 0.10, row["name"], ha="left", va="center", fontsize=8.35, fontweight="bold", color=COLORS["ink"])
        ax.text(0.045, y - 0.12, row["reading"], ha="left", va="center", fontsize=6.95, color=color)

        k, n = row["main"]
        frac = k / n
        ax.text(0.22, y + 0.12, row["main_label"], ha="left", va="center", fontsize=7.05, color=COLORS["ink"])
        ax.text(0.22, y - 0.10, f"{k:,}/{n:,}", ha="left", va="center", fontsize=7.80, fontweight="bold", color=COLORS["ink"])
        ax.add_patch(Rectangle((0.34, y - 0.16), 0.14, 0.12, facecolor=COLORS["panel2"], edgecolor=COLORS["line"], linewidth=0.28))
        if frac > 0:
            ax.add_patch(Rectangle((0.34, y - 0.16), 0.14 * frac, 0.12, facecolor=color, edgecolor=color, linewidth=0))
        else:
            ax.plot([0.34, 0.34], [y - 0.17, y - 0.03], color=color, lw=0.75)

        cx = 0.51
        for i, (label, ck, cn) in enumerate(row["controls"]):
            yy = y + 0.11 - i * 0.24
            cfrac = ck / cn
            ax.text(cx, yy, label, ha="left", va="center", fontsize=6.75, color=COLORS["muted"])
            ax.text(cx + 0.115, yy, f"{ck:,}/{cn:,}", ha="left", va="center", fontsize=6.90, color=COLORS["ink"])
            ax.add_patch(Rectangle((cx + 0.235, yy - 0.045), 0.10, 0.075, facecolor=COLORS["panel2"], edgecolor=COLORS["line"], linewidth=0.22))
            if cfrac > 0:
                fill_color = COLORS["gray"] if label in {"support", "review"} else color
                alpha = 0.45 if label in {"support", "review"} else 0.90
                ax.add_patch(Rectangle((cx + 0.235, yy - 0.045), 0.10 * cfrac, 0.075, facecolor=fill_color, edgecolor=fill_color, linewidth=0, alpha=alpha))
            else:
                ax.plot([cx + 0.235, cx + 0.235], [yy - 0.052, yy + 0.037], color=color, lw=0.65)

        ax.text(0.78, y + 0.10, f"OK {row['reading']}", ha="left", va="center", fontsize=7.10, fontweight="bold", color=COLORS["contract"])
        ax.text(0.78, y - 0.12, f"NO {row['blocked']}", ha="left", va="center", fontsize=6.95, color="#991B1B")

    rounded(ax, 0.18, -0.16, 0.64, 0.22, COLORS["panel"], COLORS["line"], lw=0.35, radius=0.004)
    ax.text(0.50, -0.05, "The comparison is by evidence contract, not by one shared accuracy score.",
            ha="center", va="center", fontsize=6.85, color=COLORS["muted"])
    save(fig, "blackbox_outcomes.pdf")


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
