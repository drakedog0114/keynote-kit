"""图表渲染：Keynote 脚本层没有 chart API，用 matplotlib 出图再插入。"""
from __future__ import annotations

import os
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

CJK = "/System/Library/Fonts/Hiragino Sans GB.ttc"
if os.path.exists(CJK):
    font_manager.fontManager.addfont(CJK)
    plt.rcParams["font.family"] = "Hiragino Sans GB"
plt.rcParams["axes.unicode_minus"] = False

INK = "#2B2420"
SUB = "#6E6259"
ACCENT = "#1F3A5F"
WARM = "#B85C38"
GRID = "#D8CDB8"


def _clean(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=SUB, labelsize=13)
    ax.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.7)
    ax.set_axisbelow(True)


def bar_chart(labels, values, title="", path="chart.png", width=9, height=5,
              color=ACCENT, value_suffix=""):
    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    bars = ax.bar(labels, values, color=color, width=0.55)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v}{value_suffix}",
                ha="center", va="bottom", fontsize=15, color=INK, fontweight="bold")
    _clean(ax)
    if title:
        ax.set_title(title, fontsize=20, color=INK, pad=14, loc="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)
    return path


def line_chart(labels, series: dict, title="", path="chart.png", width=9, height=5):
    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    palette = [ACCENT, WARM, "#6E7F5F", "#8C6E9E"]
    for i, (name, values) in enumerate(series.items()):
        ax.plot(labels, values, marker="o", markersize=6, linewidth=2.6,
                label=name, color=palette[i % len(palette)])
    _clean(ax)
    ax.legend(frameon=False, fontsize=13, labelcolor=SUB, loc="upper left")
    if title:
        ax.set_title(title, fontsize=20, color=INK, pad=14, loc="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)
    return path


def donut_chart(labels, values, title="", path="chart.png", width=7, height=5):
    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    palette = [ACCENT, WARM, "#6E7F5F", "#8C6E9E", "#C9A227"]
    wedges, _ = ax.pie(values, colors=palette[: len(values)], startangle=90,
                       wedgeprops=dict(width=0.38, edgecolor="white", linewidth=2))
    ax.legend(wedges, [f"{l}  {v}%" for l, v in zip(labels, values)],
              frameon=False, fontsize=13, labelcolor=SUB, loc="center left",
              bbox_to_anchor=(1.0, 0.5))
    if title:
        ax.set_title(title, fontsize=20, color=INK, pad=14, loc="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)
    return path
