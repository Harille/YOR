"""
OUTIL — LE JOURNAL DES OPERATIONS : ce qui a ete reellement achete
...............................................................................
Ce que ca fait  : garde en un seul endroit les MW achetes au T1 et au T2, avec
                  le jalon auquel chaque achat a ete passe. C'est un FAIT, pas
                  un calcul : ces contrats ont ete signes a ces dates-la, a ces
                  prix-la. Le §1 des guidelines interdit de justifier une
                  decision du T1 avec une information posterieure — donc on ne
                  recalcule jamais ce journal, on le constate.

                  verifier() fait l'inverse : il controle que le journal
                  correspond toujours a ce que les parametres actuels
                  produiraient, et le dit si ce n'est plus le cas. Sans lui, un
                  changement de parametre laisserait les trois jalons tourner
                  avec des chiffres incoherents, sans aucun message.

Ce que ca lit   : rien
Ce que ca ecrit : rien
Qui s'en sert   : t2_decision.py (controle), t3_spot.py (la position detenue)
A changer ici   : ACHETE, apres chaque passage d'ordre reel
"""

# (produit, nature) -> (MW, jalon auquel l'achat a ete passe)
ACHETE = {
    ("Q1-27", "Base"): (49.58, "T1"),      # 22/09/2026, strategie 70/20/10, mix trimestres
    ("Q2-27", "Base"): (37.91, "T1"),
    ("Q3-27", "Base"): (36.47, "T1"),
    ("Q4-27", "Base"): (47.65, "T1"),
    ("Cal-27", "Base"): (14.42, "T2"),     # 01/12/2026, completement a 100 %
}

TOLERANCE_MW = 0.05        # au-dela, le journal ne decrit plus les parametres actuels


def au_jalon(jalon):
    """Les achats passes a ce jalon, au format {(produit, nature): MW}."""
    return {cle: mw for cle, (mw, j) in ACHETE.items() if j == jalon}


def verifier(mix_calcule, jalon, bavard=True):
    """Le journal correspond-il encore a ce que les parametres produiraient ?

    Renvoie la liste des ecarts. Vide = tout va bien. Ne leve jamais : le but
    est d'avertir, pas d'empecher de tourner.
    """
    journal = au_jalon(jalon)
    ecarts = []
    for cle in sorted(set(journal) | set(mix_calcule)):
        attendu, note = mix_calcule.get(cle, 0.0), journal.get(cle, 0.0)
        if abs(attendu - note) > TOLERANCE_MW:
            ecarts.append((cle, note, attendu))

    if bavard:
        if not ecarts:
            print(f"  controle du journal ({jalon}) : conforme aux parametres actuels")
        else:
            print(f"  ATTENTION — le journal du {jalon} ne correspond plus aux parametres :")
            for (produit, nature), note, attendu in ecarts:
                print(f"     {produit} {nature} : journal {note:.2f} MW,"
                      f" parametres actuels {attendu:.2f} MW")
            print(f"     -> mettre a jour ACHETE dans outils/position.py,"
                  f" ou revenir aux parametres d'origine.")
    return ecarts
