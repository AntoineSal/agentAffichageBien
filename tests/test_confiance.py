"""
confiance.py : filtrage déterministe des candidats par score de confiance.
"""

from agentAffichage.selection.confiance import SEUIL_AFFICHAGE, widgets_retenus
from agentAffichage.selection.schemas import ResultatSelection


def _candidat(type_, confidence, **donnees):
    return {"type": type_, "confidence": confidence, "raison": "test", "donnees": donnees}


def test_candidat_exactement_au_seuil_est_retenu():
    resultat = ResultatSelection(candidats=[
        _candidat("stats", SEUIL_AFFICHAGE, indicateurs=[{"label": "A", "valeur": "1"}]),
    ])
    assert len(widgets_retenus(resultat)) == 1


def test_candidat_juste_sous_le_seuil_est_rejete():
    resultat = ResultatSelection(candidats=[
        _candidat("stats", SEUIL_AFFICHAGE - 0.01, indicateurs=[{"label": "A", "valeur": "1"}]),
    ])
    assert widgets_retenus(resultat) == []


def test_seuil_est_eleve_privilegie_faux_negatifs():
    """La spec demande une logique conservatrice : le seuil doit être dans la
    bande "bonne pertinence" (0.75-0.89), pas plus bas."""
    assert SEUIL_AFFICHAGE >= 0.75


def test_ordre_des_candidats_retenus_preserve():
    resultat = ResultatSelection(candidats=[
        _candidat("card", 0.9, titre="A", attributs=[]),
        _candidat("timeline", 0.8, evenements=[{"date": "2020", "titre": "X"}]),
    ])
    retenus = widgets_retenus(resultat)
    assert [c.type for c in retenus] == ["card", "timeline"]
