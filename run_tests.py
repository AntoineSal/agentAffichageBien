#!/usr/bin/env python3
"""
Script pour lancer les tests unitaires.
Exécuter avec : python run_tests.py
"""

import unittest
import sys
import os

# Ajouter le chemin du projet au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # Découvrir et lancer tous les tests
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Quitter avec un code d'erreur si des tests échouent
    sys.exit(0 if result.wasSuccessful() else 1)
