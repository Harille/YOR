"""
FIGURES — enregistrer les sept graphiques en PNG
...............................................................................
Ce que ca fait  : rejoue les scripts et enregistre leurs figures matplotlib.
                  Aucun calcul n'est ajoute : plt.show() est remplace par un
                  savefig(). Les figures obtenues sont donc exactement celles
                  qui s'affichent quand on lance un script a la main.
Ce que ca lit   : donnees/ (via les scripts)
Ce que ca ecrit : sorties/figures/01..07.png
Duree           : ~30 s
Usage           : python figures.py      (ou python lancer.py --figures)
"""
import matplotlib
matplotlib.use("Agg")                       # pas d'ecran : on enregistre, on n'affiche pas
import matplotlib.pyplot as plt
import runpy
from pathlib import Path

SORTIE = Path(__file__).parent / "sorties" / "figures"
SORTIE.mkdir(parents=True, exist_ok=True)

NOMS = {
    "outils/demande.py": ["01_charge_annee", "02_semaine_hiver", "03_1er_janvier"],
    "outils/marche.py":  ["04_scenario_2021"],
    "t1_strategie.py":   ["05_comparaison_scenarios"],
    "t2_decision.py":    ["06_decision_t2"],
    "t3_spot.py":        ["07_spot_t3"],
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
    racine = Path(__file__).parent
    for fichier, noms in NOMS.items():
        print(f"\n{'#' * 70}\n# {fichier}\n{'#' * 70}")
        etat["noms"], etat["i"] = noms, 0
        runpy.run_path(str(racine / fichier), run_name="__main__")
    print(f"\nLes sept figures sont dans {SORTIE}")
