"""
LANCER — toute la chaine, du 22/09/2026 a l'ordre day-ahead du 01/01/2027
...............................................................................
    python lancer.py              les trois jalons : T1, puis T2, puis T3
    python lancer.py --figures    idem + enregistre les figures en PNG
    python lancer.py --tout       ajoute le scenario detaille (outils/marche.py)

Les figures ne s'ouvrent pas a l'ecran ici : lancer.py enchaine les scripts sans
s'arreter. Pour voir une figure, lance le script tout seul (python t3_spot.py),
ou demande --figures et ouvre les PNG de sorties/figures/.

Chaque script de jalon est independant : il reconstruit tout depuis les CSV de
donnees/. On peut donc relancer t2_decision.py seul apres avoir change un
parametre, sans repasser par le T1.
"""
import matplotlib
matplotlib.use("Agg")                       # on enchaine : aucune fenetre ne doit bloquer
import matplotlib.pyplot as plt
import runpy
import sys
import time
from pathlib import Path

import figures                              # la table des noms de figures

RACINE = Path(__file__).parent

ETAPES = [
    ("outils/demande.py", "Le moteur de demande, seul  - courbe de charge et volumes"),
    ("outils/marche.py",  "Un scenario de prix, en detail (pedagogique)"),
    ("t1_strategie.py",   "T1  22/09/2026 - construire, choisir et executer la strategie"),
    ("t2_decision.py",    "T2  01/12/2026 - actualiser, reviser, decider, executer"),
    ("t3_spot.py",        "T3  31/12/2026 - actualiser, reequilibrer, envoyer les ordres"),
]
JALONS = {"t1_strategie.py", "t2_decision.py", "t3_spot.py"}


def main(argv):
    garder = "--figures" in argv
    tout = "--tout" in argv or garder        # les figures couvrent les cinq fichiers
    etapes = [e for e in ETAPES if tout or e[0] in JALONS]

    plt.show = figures.show if garder else (lambda *a, **k: plt.close("all"))

    debut = time.time()
    for i, (fichier, titre) in enumerate(etapes, 1):
        print(f"\n{'=' * 78}\n[{i}/{len(etapes)}]  {fichier}\n         {titre}\n{'=' * 78}")
        figures.etat["noms"], figures.etat["i"] = figures.NOMS[fichier], 0
        t = time.time()
        runpy.run_path(str(RACINE / fichier), run_name="__main__")
        print(f"\n({fichier} : {time.time() - t:.0f} s)")

    print(f"\nTermine en {time.time() - debut:.0f} s. Tout est dans sorties/"
          + (", les figures dans sorties/figures/." if garder else "."))


if __name__ == "__main__":
    main(sys.argv[1:])
