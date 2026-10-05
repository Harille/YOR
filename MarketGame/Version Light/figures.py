"""Rejoue les cinq scripts et enregistre leurs figures matplotlib dans sorties/figures/.

Ce fichier ne calcule rien : il remplace seulement plt.show() par un savefig().
Les figures obtenues sont donc exactement celles qui s'affichent quand on lance
les scripts a la main.
"""
import matplotlib
matplotlib.use("Agg")                       # pas d'ecran : on enregistre, on n'affiche pas
import matplotlib.pyplot as plt
import runpy
from pathlib import Path

SORTIE = Path(__file__).parent / "sorties" / "figures"
SORTIE.mkdir(parents=True, exist_ok=True)

NOMS = {
    "Modelisation_Conso.py":    ["01_charge_annee", "02_semaine_hiver", "03_1er_janvier"],
    "scenarios.py":             ["04_scenario_2021"],
    "comparaison_scenarios.py": ["05_comparaison_scenarios"],
    "decision_t2.py":           ["06_decision_t2"],
    "spot_t3.py":               ["07_spot_t3"],
}

etat = {"noms": [], "i": 0}


def show(*a, **k):
    noms, i = etat["noms"], etat["i"]
    nom = noms[i] if i < len(noms) else f"extra_{i}"
    fig = plt.gcf()
    fig.savefig(SORTIE / f"{nom}.png", dpi=130, bbox_inches="tight", facecolor="white")
    print(f"   -> sorties/figures/{nom}.png")
    plt.close(fig)
    etat["i"] += 1


plt.show = show

if __name__ == "__main__":
    dossier = Path(__file__).parent
    for fichier, noms in NOMS.items():
        print(f"\n{'#' * 70}\n# {fichier}\n{'#' * 70}")
        etat["noms"], etat["i"] = noms, 0
        runpy.run_path(str(dossier / fichier), run_name="__main__")
    print(f"\nLes sept figures sont dans {SORTIE}")
