"""
Tests unitaires pour le module afficheur.py.
Ces tests vérifient que la fonction afficherJoliment fonctionne correctement.
"""

import unittest
import sys
import os

# Ajouter le chemin du projet au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentAffichage.afficheur import afficherJoliment


class TestAfficheur(unittest.TestCase):
    """Classe de tests pour la fonction afficherJoliment."""

    def test_texte_simple(self):
        """Test avec un texte simple."""
        texte = "Bonjour, comment ça va ?"
        result = afficherJoliment(texte)
        
        # Vérifier que le résultat est une chaîne de caractères
        self.assertIsInstance(result, str)
        
        # Vérifier que le texte est présent dans le résultat
        self.assertIn("Bonjour, comment ça va ?", result)
        
        # Vérifier que le résultat contient du HTML
        self.assertIn("<div", result)
        self.assertIn("</div>", result)

    def test_texte_vide(self):
        """Test avec un texte vide."""
        texte = ""
        result = afficherJoliment(texte)
        
        # Vérifier que le résultat est une chaîne de caractères
        self.assertIsInstance(result, str)
        
        # Vérifier que le résultat contient du HTML
        self.assertIn("<div", result)

    def test_texte_avec_saut_de_ligne(self):
        """Test avec un texte contenant des sauts de ligne."""
        texte = "Ligne 1\nLigne 2\nLigne 3"
        result = afficherJoliment(texte)
        
        # Vérifier que le résultat contient le texte
        self.assertIn("Ligne 1", result)
        self.assertIn("Ligne 2", result)
        self.assertIn("Ligne 3", result)

    def test_texte_avec_caracteres_speciaux(self):
        """Test avec des caractères spéciaux."""
        texte = "Test avec des <tags> & des \"guillemets\""
        result = afficherJoliment(texte)
        
        # Vérifier que le résultat contient le texte (même si les caractères spéciaux sont échappés)
        self.assertIn("Test avec des", result)

    def test_avec_fichiers_vides(self):
        """Test avec une liste de fichiers vide."""
        texte = "Test avec fichiers"
        fichiers = []
        result = afficherJoliment(texte, fichiers)
        
        # Vérifier que le résultat contient une mention des fichiers
        self.assertIn("Aucun fichier uploadé", result)

    def test_avec_fichiers_none(self):
        """Test avec fichiers=None."""
        texte = "Test sans fichiers"
        result = afficherJoliment(texte, None)
        
        # Vérifier que le résultat contient une mention des fichiers
        self.assertIn("Aucun fichier uploadé", result)

    def test_texte_long(self):
        """Test avec un texte très long."""
        texte = "A" * 1000  # Texte de 1000 caractères
        result = afficherJoliment(texte)
        
        # Vérifier que le résultat contient le texte
        self.assertIn("A" * 100, result)  # Vérifier au moins une partie
        
        # Vérifier que le résultat est du HTML valide
        self.assertIn("<div", result)
        self.assertIn("</div>", result)

    def test_structure_html_valide(self):
        """Test que la structure HTML est valide."""
        texte = "Test"
        result = afficherJoliment(texte)
        
        # Vérifier que le HTML est bien formé (au moins une balise ouvrante et fermante)
        self.assertTrue(result.count("<div") >= 1)
        self.assertTrue(result.count("</div") >= 1)
        
        # Vérifier que les balises sont correctement imbriquées
        self.assertTrue(result.count("<div") == result.count("</div"))


class TestAfficheurIntegration(unittest.TestCase):
    """Tests d'intégration pour vérifier que la fonction s'intègre bien avec Streamlit."""

    def test_retourne_chaine_html(self):
        """Test que la fonction retourne toujours une chaîne HTML."""
        test_cases = [
            ("Texte simple", None),
            ("", []),
            ("Texte avec fichiers", ["fichier1.txt", "fichier2.txt"]),
            ("Autre test", None),
        ]
        
        for texte, fichiers in test_cases:
            with self.subTest(texte=texte, fichiers=fichiers):
                result = afficherJoliment(texte, fichiers)
                self.assertIsInstance(result, str)
                self.assertIn("<", result)  # Contient au moins une balise HTML


if __name__ == "__main__":
    unittest.main()
