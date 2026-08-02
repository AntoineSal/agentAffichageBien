"""
Fonctions utilitaires pour l'application Streamlit.
Inclut l'appel à l'API Mistral et la gestion des fichiers.
"""

import requests
import os
from typing import Optional, List


def call_mistral_api(prompt: str, api_key: Optional[str] = None) -> str:
    """
    Appelle l'API Mistral avec le prompt donné.
    
    Args:
        prompt (str): Le texte à envoyer à l'API.
        api_key (str, optional): Clé API Mistral. Si None, utilise la variable d'environnement MISTRAL_API_KEY.
    
    Returns:
        str: La réponse de l'API ou un message d'erreur.
    """
    # Récupérer la clé API depuis les variables d'environnement ou le paramètre
    api_key = api_key or os.getenv("MISTRAL_API_KEY")
    
    if not api_key:
        return "Erreur : Aucune clé API Mistral trouvée. Veuillez la configurer dans les paramètres ou via la variable d'environnement MISTRAL_API_KEY."
    
    try:
        response = requests.post(
            "https://api.mistral.ai/v1/chat",
            json={
                "model": "mistral-tiny",
                "messages": [{"role": "user", "content": prompt}]
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=30
        )
        
        # Vérifier si la requête a réussi
        response.raise_for_status()
        
        # Extraire la réponse
        response_data = response.json()
        if "choices" in response_data and len(response_data["choices"]) > 0:
            return response_data["choices"][0]["message"]["content"]
        else:
            return f"Erreur : Réponse inattendue de l'API. Données : {response_data}"
            
    except requests.exceptions.RequestException as e:
        return f"Erreur lors de l'appel à l'API Mistral : {str(e)}"
    except Exception as e:
        return f"Erreur inattendue : {str(e)}"


def read_uploaded_file(uploaded_file) -> str:
    """
    Lit le contenu d'un fichier uploadé.
    
    Args:
        uploaded_file: Fichier uploadé via Streamlit.
    
    Returns:
        str: Le contenu du fichier en texte.
    """
    try:
        return uploaded_file.getvalue().decode("utf-8")
    except Exception as e:
        return f"Erreur lors de la lecture du fichier : {str(e)}"


def save_uploaded_file(uploaded_file, save_path: str) -> bool:
    """
    Sauvegarde un fichier uploadé sur le disque.
    
    Args:
        uploaded_file: Fichier uploadé via Streamlit.
        save_path (str): Chemin où sauvegarder le fichier.
    
    Returns:
        bool: True si succès, False sinon.
    """
    try:
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde du fichier : {str(e)}")
        return False
