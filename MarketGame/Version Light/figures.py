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

SORTIE = Path(__file__).parent / "sorties" / "figures"   # chemin absolu : le dossier
SORTIE.mkdir(parents=True, exist_ok=True)                # courant n'a aucune importance

# Dans quel ORDRE chaque script appelle plt.show(), et sous quel nom enregistrer.
# Le numero en tete du nom fixe l'ordre d'affichage dans l'explorateur de fichiers.
NOMS = {
    "outils/demande.py": ["01_charge_annee", "02_semaine_hiver", "03_1er_janvier"],
    "outils/marche.py":  ["04_scenario_2021"],
    "t1_strategie.py":   ["05_comparaison_scenarios"],
    "t2_decision.py":    ["06_decision_t2"],
    "t3_spot.py":        ["07_spot_t3"],
}

# Qui est en cours, et combien de figures ce script a deja produites. Un dict
# plutot que deux variables : lancer.py le modifie de l'exterieur (figures.etat).
etat = {"noms": [], "i": 0}


def show(*a, **k):
    """Remplacante de plt.show() : au lieu d'ouvrir une fenetre, on enregistre.

    Signature permissive (*a, **k) : matplotlib peut passer des arguments qu'on
    ignore. Le script appelant ne sait pas qu'il a ete detourne.
    """
    noms, i = etat["noms"], etat["i"]
    nom = noms[i] if i < len(noms) else f"extra_{i}"   # figure en trop -> nom de secours
    fig = plt.gcf()                                    # la figure courante, celle a montrer
    fig.savefig(SORTIE / f"{nom}.png", dpi=130, bbox_inches="tight", facecolor="white")
    print(f"   -> sorties/figures/{nom}.png")
    plt.close(fig)                                     # liberer la memoire : 7 figures d'affilee
    etat["i"] += 1                                     # la prochaine prendra le nom suivant


plt.show = show     # LE detournement : tout appel a plt.show() passe desormais ici

if __name__ == "__main__":
    racine = Path(__file__).parent
    for fichier, noms in NOMS.items():
        print(f"\n{'#' * 70}\n# {fichier}\n{'#' * 70}")
        etat["noms"], etat["i"] = noms, 0        # remettre le compteur a zero par script
        # run_name="__main__" fait croire au script qu'il est lance directement :
        # son bloc final s'execute donc, et avec lui ses appels a plt.show().
        runpy.run_path(str(racine / fichier), run_name="__main__")
    print(f"\nLes sept figures sont dans {SORTIE}")
