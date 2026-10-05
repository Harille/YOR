"""Lance toute la chaine dans l'ordre, du profil Enedis a l'ordre day-ahead.

    python lancer.py              les quatre etapes qui comptent
    python lancer.py --figures    idem + enregistre les figures dans sorties/figures/
    python lancer.py --tout       ajoute scenarios.py (le scenario seul, facultatif)

Les figures ne s'ouvrent pas a l'ecran ici : lancer.py enchaine les scripts sans
s'arreter. Pour voir une figure, lance le script tout seul (python spot_t3.py),
ou demande --figures et ouvre les PNG.

Chaque script est independant : il reconstruit tout depuis les CSV de donnees/.
On peut donc en relancer un seul apres avoir change un parametre.
"""
import matplotlib
matplotlib.use("Agg")                       # on enchaine : aucune fenetre ne doit bloquer
import matplotlib.pyplot as plt
import runpy
import sys
import time
from pathlib import Path

import figures                              # la table des noms de figures

DOSSIER = Path(__file__).parent

ETAPES = [
    ("Modelisation_Conso.py",    "Etapes 1 a 7  - courbe de charge 2027, T1 puis T2"),
    ("scenarios.py",             "Etapes 8 a 10 - un seul scenario, en detail (facultatif)"),
    ("comparaison_scenarios.py", "Etapes 11-12  - mix EEX, marges, choix de la strategie T1"),
    ("decision_t2.py",           "Etapes 13-14  - revision au 01/12, decision T2, position ouverte"),
    ("spot_t3.py",               "Etape 15      - T3 : reequilibrage et ordre day-ahead"),
]
FACULTATIF = {"scenarios.py"}


def main(argv):
    garder = "--figures" in argv
    tout = "--tout" in argv or garder        # les figures couvrent les cinq scripts
    etapes = [e for e in ETAPES if tout or e[0] not in FACULTATIF]

    plt.show = figures.show if garder else (lambda *a, **k: plt.close("all"))

    debut = time.time()
    for i, (fichier, titre) in enumerate(etapes, 1):
        print(f"\n{'=' * 78}\n[{i}/{len(etapes)}]  {fichier}\n         {titre}\n{'=' * 78}")
        figures.etat["noms"], figures.etat["i"] = figures.NOMS[fichier], 0
        t = time.time()
        runpy.run_path(str(DOSSIER / fichier), run_name="__main__")
        print(f"\n({fichier} : {time.time() - t:.0f} s)")

    print(f"\nTermine en {time.time() - debut:.0f} s. Tout est dans sorties/"
          + (", les figures dans sorties/figures/." if garder else "."))


if __name__ == "__main__":
    main(sys.argv[1:])
