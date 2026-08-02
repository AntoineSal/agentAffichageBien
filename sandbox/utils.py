"""
Fonctions utilitaires pour l'application Streamlit.
Inclut l'appel a l'API Mistral et la gestion des fichiers.
"""

import requests
import os
from typing import Optional, List


def call_mistral_api(prompt: str, api_key: Optional[str] = None) -> str:
    """
    Appelle l'API Mistral avec le prompt donne.
    
    Args:
        prompt (str): Le texte a envoyer a l'API.
        api_key (str, optional): Cle API Mistral. Si None, utilise la variable d'environnement MISTRAL_API_KEY.
    
    Returns:
        str: La reponse de l'API ou un message d'erreur.
    """
    # Recuperer la cle API depuis les variables d'environnement ou le parametre
    api_key = api_key or os.getenv("MISTRAL_API_KEY")
    
    if not api_key:
        return "Erreur : Aucune cle API Mistral trouvee. Veuillez la configurer dans les parametres ou via la variable d'environnement MISTRAL_API_KEY."
    
    try:
        # Utiliser l'endpoint correct pour l'API Mistral (le endpoint /v1/chat n'existe plus)
        # Pour les modeles de type chat, on utilise /v1/chat/completions
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            json={
                "model": "mistral-tiny-latest",
                "messages": [{"role": "user", "content": prompt}]
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=30
        )
        
        # Verifier si la requete a reussi
        response.raise_for_status()
        
        # Extraire la reponse
        response_data = response.json()
        if "choices" in response_data and len(response_data["choices"]) > 0:
            return response_data["choices"][0]["message"]["content"]
        else:
            return f"Erreur : Reponse inattendue de l'API. Donnees : {response_data}"
            
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return "Erreur : L'endpoint de l'API Mistral a change. Veuillez verifier l'URL ou utiliser le mode Agent pour tester sans API."
        return f"Erreur HTTP lors de l'appel a l'API Mistral : {str(e)}"
    except requests.exceptions.RequestException as e:
        return f"Erreur lors de l'appel a l'API Mistral : {str(e)}"
    except Exception as e:
        return f"Erreur inattendue : {str(e)}"


def read_uploaded_file(uploaded_file) -> str:
    """
    Lit le contenu d'un fichier uploade.
    
    Args:
        uploaded_file: Fichier uploade via Streamlit.
    
    Returns:
        str: Le contenu du fichier en texte.
    """
    try:
        return uploaded_file.getvalue().decode("utf-8")
    except Exception as e:
        return f"Erreur lors de la lecture du fichier : {str(e)}"


def save_uploaded_file(uploaded_file, save_path: str) -> bool:
    """
    Sauvegarde un fichier uploade sur le disque.
    
    Args:
        uploaded_file: Fichier uploade via Streamlit.
        save_path (str): Chemin ou sauvegarder le fichier.
    
    Returns:
        bool: True si succes, False sinon.
    """
    try:
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde du fichier : {str(e)}")
        return False
