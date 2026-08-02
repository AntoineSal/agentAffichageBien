#!/usr/bin/env python3
"""
Point d'entrée principal pour lancer l'application Streamlit.
Exécuter avec : streamlit run main.py
"""

import sys
import os

# Ajouter le dossier courant au path pour les imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from sandbox.app import main

if __name__ == "__main__":
    main()
