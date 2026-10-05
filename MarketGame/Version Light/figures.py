"""Rejoue chaque script et enregistre ses figures matplotlib en PNG."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import runpy, sys
from pathlib import Path

SORTIE = Path(__file__).parent / "figures"
SORTIE.mkdir(exist_ok=True)

NOMS = {
    "Modelisation_Conso.py": ["01_charge_annee", "02_semaine_hiver", "03_1er_janvier"],
    "scenarios.py":          ["04_scenario_2021"],
    "comparaison_scenarios.py": ["05_comparaison_scenarios"],
    "decision_t2.py":        ["06_decision_t2"],
    "spot_t3.py":            ["07_spot_t3"],
}

etat = {"noms": [], "i": 0}

def show(*a, **k):
    noms, i = etat["noms"], etat["i"]
    nom = noms[i] if i < len(noms) else f"extra_{i}"
    fig = plt.gcf()
    fig.savefig(SORTIE / f"{nom}.png", dpi=130, bbox_inches="tight", facecolor="white")
    print(f"   -> figures/{nom}.png")
    plt.close(fig)
    etat["i"] += 1

plt.show = show

for fichier, noms in NOMS.items():
    print(f"\n{'#' * 70}\n# {fichier}\n{'#' * 70}")
    etat["noms"], etat["i"] = noms, 0
    runpy.run_path(fichier, run_name="__main__")
