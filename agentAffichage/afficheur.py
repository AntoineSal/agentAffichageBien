"""
Module principal pour l'agent d'affichage.
Ce fichier sera modifié par le stagiaire pour implémenter la fonction afficherJoliment.
"""

from typing import List, Optional


def afficherJoliment(texte: str, fichiers: Optional[List] = None) -> str:
    """
    Transforme le texte et les fichiers en un affichage HTML/CSS/JS interactif et professionnel.
    
    Cette fonction est le cœur du projet du stagiaire. Elle doit analyser le contenu
    (texte, fichiers, etc.) et générer une sortie HTML/CSS/JS qui permet une visualisation
    interactive et esthétique des données.
    
    Exemples d'utilisation :
    - Si le texte contient une liste de pays avec leur superficie, générer une carte interactive.
    - Si le texte contient du code, générer un éditeur de code avec coloration syntaxique.
    - Si des fichiers sont fournis, les intégrer dans l'affichage (ex: afficher un graphique depuis un CSV).
    
    Args:
        texte (str): Le texte à afficher (ex: réponse d'un chatbot).
        fichiers (List, optional): Liste de fichiers uploadés (chaque fichier est un objet Streamlit UploadedFile).
    
    Returns:
        str: Code HTML/CSS/JS autonome (peut être affiché directement dans une page web).
    """
    # Exemple basique : afficher le texte dans une boîte stylisée
    # Le stagiaire devra remplacer cette implémentation par sa propre logique.
    
    return f"""
    <div style="
        border: 1px solid #4CAF50; 
        padding: 15px; 
        border-radius: 8px; 
        background-color: #f9f9f9;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 10px 0;
    ">
        <h3 style="color: #4CAF50; margin-top: 0;">Réponse formatée</h3>
        <p style="line-height: 1.6;">{texte}</p>
        {
            "<p style='color: #666; font-style: italic;'>Aucun fichier uploadé.</p>" 
            if not fichiers else 
            f"<p style='color: #666;'>Fichiers uploadés: {len(fichiers)}</p>"
        }
    </div>
    """
