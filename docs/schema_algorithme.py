# -*- coding: utf-8 -*-
"""Schema de la chaine de calcul, pour le rapport Market Game (partie 3)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ENCRE, GRIS, BORD = "#1a1a1a", "#5f6368", "#9aa0a6"
FOND_ENTREE, FOND_ETAPE, BORD_ETAPE = "#f2f2f2", "#e8eef7", "#4472c4"

ETAPES = [
    ("1. Demande", "demande.py\ncalendrier.py", "courbe au pas de 15 min,\nà température normale"),
    ("2. Scénarios", "marche.py", "cinq prix 2027\n(Niveau × Forme)"),
    ("3. Couverture", "couverture.py", "produits EEX, MW,\nmarge par scénario"),
    ("4. Décision", "t1_strategie.py\nt2_decision.py", "plancher d'abord,\nespérance ensuite"),
    ("5. Ordres", "t3_spot.py", "position ouverte,\nheure par heure"),
]
ENTREES = ["effectifs clients révisés", "prix EEX du jour", "journal des achats (position.py)"]

fig, ax = plt.subplots(figsize=(10, 3.45))
ax.set_xlim(0, 10); ax.set_ylim(0, 3.45); ax.axis("off")

def boite(x, y, w, h, fond, bord):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                linewidth=1.2, edgecolor=bord, facecolor=fond))

def fleche(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13,
                                 linewidth=1.1, color=GRIS, shrinkA=0, shrinkB=0))

# entrées
boite(0.10, 1.70, 2.14, 1.38, FOND_ENTREE, BORD)
ax.text(1.17, 2.92, "Entrées du jalon", ha="center", va="center",
        fontsize=9.5, color=ENCRE, fontweight="bold")
for i, txt in enumerate(ENTREES):
    ax.text(0.24, 2.56 - i * 0.29, "• " + txt, ha="left", va="center",
            fontsize=8.2, color=GRIS)
fleche(2.26, 2.41, 2.48, 2.41)

# la chaîne
x, w, gap = 2.55, 1.33, 0.16
for i, (titre, fichiers, sortie) in enumerate(ETAPES):
    gx = x + i * (w + gap)
    boite(gx, 1.95, w, 0.92, FOND_ETAPE, BORD_ETAPE)
    ax.text(gx + w / 2, 2.58, titre, ha="center", va="center",
            fontsize=10, color=ENCRE, fontweight="bold")
    ax.text(gx + w / 2, 2.31, fichiers, ha="center", va="top",
            fontsize=7.2, color=GRIS, family="monospace", linespacing=1.4)
    ax.text(gx + w / 2, 1.82, sortie, ha="center", va="top",
            fontsize=8, color=GRIS, linespacing=1.45)
    if i < len(ETAPES) - 1:
        fleche(gx + w + 0.015, 2.41, gx + w + gap - 0.015, 2.41)

# sortie finale
fin = x + 4 * (w + gap) + w / 2
fleche(fin, 1.36, fin, 1.08)
ax.text(fin, 0.98, "24 ordres déposés\navant 12h00 CET", ha="center", va="top",
        fontsize=8.6, color=ENCRE, linespacing=1.45, fontweight="bold")

# note
ax.plot([0.15, 9.85], [0.40, 0.40], color=BORD, linewidth=0.7)
ax.text(0.15, 0.21, "Les trois jalons exécutent cette chaîne à l'identique : "
        "seules les trois entrées changent.", ha="left", va="center",
        fontsize=8.4, color=GRIS, style="italic")

fig.tight_layout(pad=0.25)
base = "/tmp/claude-0/-home-user-YOR/0dc8cf05-52b0-5f11-808f-136f1bc7d762/scratchpad/schema/schema_algorithme"
fig.savefig(base + ".png", dpi=300, bbox_inches="tight", facecolor="white")
fig.savefig(base + ".svg", bbox_inches="tight", facecolor="white")
print("ok")
