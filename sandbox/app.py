"""
Application Streamlit principale pour la sandbox.
Gère l'interface utilisateur, l'historique des messages, et l'intégration avec l'agent d'affichage.
"""

import streamlit as st
from typing import List, Dict, Optional, Tuple
from .utils import call_mistral_api
import os
import json
from datetime import datetime

# Importer la fonction du stagiaire
from agentAffichage.afficheur import afficherJoliment


def initialize_session_state():
    """Initialise les variables de session si elles n'existent pas."""
    if "messages" not in st.session_state:
        st.session_state.messages: List[Dict[str, str]] = []
    
    if "mode" not in st.session_state:
        st.session_state.mode: str = "Utilisateur"
    
    if "api_key" not in st.session_state:
        # Charger la clé API depuis le fichier .env si disponible
        st.session_state.api_key: Optional[str] = os.getenv("MISTRAL_API_KEY")
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history: List[Dict] = []
    
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id: Optional[str] = None


def reset_chat():
    """Réinitialise l'historique des messages."""
    st.session_state.messages = []


def generate_chat_id() -> str:
    """Génère un ID unique pour un chat."""
    import uuid
    return str(uuid.uuid4())[:8]


def save_current_chat():
    """Sauvegarde le chat actuel dans l'historique."""
    if not st.session_state.messages:
        return
    
    chat_id = st.session_state.current_chat_id or generate_chat_id()
    chat_data = {
        "id": chat_id,
        "messages": st.session_state.messages.copy(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Mettre à jour ou ajouter le chat
    existing_chat_ids = [chat["id"] for chat in st.session_state.chat_history]
    if chat_id in existing_chat_ids:
        for i, chat in enumerate(st.session_state.chat_history):
            if chat["id"] == chat_id:
                st.session_state.chat_history[i] = chat_data
                break
    else:
        st.session_state.chat_history.append(chat_data)
    
    st.session_state.current_chat_id = chat_id


def load_chat(chat_id: str):
    """Charge un chat depuis l'historique."""
    for chat in st.session_state.chat_history:
        if chat["id"] == chat_id:
            st.session_state.messages = chat["messages"].copy()
            st.session_state.current_chat_id = chat_id
            break


def delete_chat(chat_id: str):
    """Supprime un chat de l'historique."""
    st.session_state.chat_history = [
        chat for chat in st.session_state.chat_history if chat["id"] != chat_id
    ]
    if st.session_state.current_chat_id == chat_id:
        st.session_state.messages = []
        st.session_state.current_chat_id = None


def display_message(message: Dict[str, str], index: int):
    """Affiche un message avec son bouton d'aperçu du code."""
    role = message["role"]
    content = message["content"]
    
    # Afficher le message de manière simple
    if role == "user":
        st.markdown(f"**Utilisateur :**\n\n{content}")
    else:  # agent
        st.markdown(f"**Agent :**\n\n{content}")
    
    # Ajouter le bouton d'aperçu du code UNIQUEMENT pour les messages de l'agent
    if role == "agent":
        if st.button(f"Afficher le code", key=f"code_{index}"):
            with st.expander("Code genere", expanded=True):
                st.code(content, language="html")


def display_messages():
    """Affiche les messages de l'historique dans le chat."""
    for index, message in enumerate(st.session_state.messages):
        display_message(message, index)


def get_mistral_response(prompt: str) -> str:
    """
    Récupère la réponse de l'API Mistral.
    
    Args:
        prompt (str): Le texte à envoyer à l'API.
    
    Returns:
        str: La réponse de l'API ou un message d'erreur.
    """
    api_key = st.session_state.get("api_key") or os.getenv("MISTRAL_API_KEY")
    return call_mistral_api(prompt, api_key)


def process_user_message(prompt: str, uploaded_files: Optional[List] = None):
    """
    Traite un message de l'utilisateur selon le mode sélectionné.
    
    Args:
        prompt (str): Le message saisi par l'utilisateur.
        uploaded_files (List, optional): Liste des fichiers uploadés.
    """
    # Ajouter le message utilisateur à l'historique
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Afficher le message utilisateur
    st.markdown(f"**Utilisateur :**\n\n{prompt}")
    
    # Traiter selon le mode
    if st.session_state.mode == "Utilisateur":
        # Appel à l'API Mistral
        with st.spinner("Reflexion en cours..."):
            response = get_mistral_response(prompt)
    else:  # Mode "Agent"
        # Simuler une réponse directe (sans API)
        response = prompt
    
    # Appeler la fonction du stagiaire pour générer l'affichage
    html_output = afficherJoliment(response, uploaded_files)
    
    # Ajouter la réponse à l'historique
    st.session_state.messages.append({"role": "agent", "content": html_output})
    
    # Afficher la réponse (HTML généré par afficherJoliment)
    st.markdown(f"**Agent :**\n\n{html_output}")
    
    # Bouton pour afficher le code sous le message de l'agent
    if st.button(f"Afficher le code", key=f"code_{len(st.session_state.messages)-1}"):
        with st.expander("Code genere", expanded=True):
            st.code(html_output, language="html")


def main():
    """Fonction principale de l'application Streamlit."""
    # Configuration de la page
    st.set_page_config(
        page_title="Sandbox Agent Affichage",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Appliquer le CSS personnalisé
    try:
        with open("sandbox/styles/custom.css", "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass
    
    # Initialisation de l'état de la session
    initialize_session_state()
    
    # Barre latérale pour les paramètres et l'historique
    with st.sidebar:
        st.header("Parametres")
        
        # Sélection du mode
        st.session_state.mode = st.radio(
            "Mode",
            options=["Utilisateur", "Agent"],
            index=0 if st.session_state.mode == "Utilisateur" else 1,
            help="Utilisateur : Envoie les messages a l'API Mistral. Agent : Affiche directement les messages sans appel API."
        )
        
        # Clé API Mistral (uniquement en mode Utilisateur)
        if st.session_state.mode == "Utilisateur":
            st.session_state.api_key = st.text_input(
                "Cle API Mistral",
                type="password",
                value=st.session_state.get("api_key", ""),
                help="Votre cle API Mistral. Si non fournie, la variable d'environnement MISTRAL_API_KEY sera utilisee."
            )
        
        # Upload de fichiers
        st.markdown("---")
        st.header("Fichiers")
        uploaded_files = st.file_uploader(
            "Upload de fichiers",
            accept_multiple_files=True,
            help="Les fichiers uploades seront passes a la fonction afficherJoliment."
        )
        
        # Gestion de l'historique des chats
        st.markdown("---")
        st.header("Historique des chats")
        
        # Bouton pour sauvegarder le chat actuel
        if st.session_state.messages:
            if st.button("Sauvegarder ce chat"):
                save_current_chat()
                st.success("Chat sauvegarde !")
                st.experimental_rerun()
        
        # Bouton pour créer un nouveau chat
        if st.button("Nouveau Chat"):
            if st.session_state.messages:
                save_current_chat()
            reset_chat()
            st.experimental_rerun()
        
        # Liste des chats précédents
        if st.session_state.chat_history:
            st.markdown("**Chats precedents**")
            for chat in reversed(st.session_state.chat_history):
                chat_id = chat["id"]
                timestamp = chat.get("timestamp", "Inconnu")
                chat_preview = chat["messages"][0]["content"][:25] + "..." if chat["messages"] else "Chat vide"
                
                chat_display = f"{timestamp[:10]} - {chat_preview}"
                
                col1, col2 = st.columns([0.85, 0.15])
                with col1:
                    if st.button(f"{chat_display}", key=f"load_{chat_id}"):
                        load_chat(chat_id)
                        st.experimental_rerun()
                with col2:
                    if st.button("X", key=f"delete_{chat_id}"):
                        delete_chat(chat_id)
                        st.experimental_rerun()
        else:
            st.info("Aucun chat precedent.")
    
    # Conteneur principal pour les messages (avec marge en bas pour la barre de chat)
    message_container = st.container()
    
    with message_container:
        # Affichage de l'historique des messages
        display_messages()
        
        # Espace pour éviter que le dernier message soit caché par la barre de chat
        st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)
    
    # Barre de chat fixée en bas
    st.markdown("""
    <style>
    .chat-input-fixed {
        position: fixed;
        bottom: 20px;
        left: 0;
        right: 0;
        background: white;
        padding: 10px;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
        z-index: 1000;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="chat-input-fixed">', unsafe_allow_html=True)
    col1, col2 = st.columns([0.9, 0.1])
    with col1:
        prompt = st.text_input("Ecrivez un message...", key="chat_input", label_visibility="hidden")
    with col2:
        send_button = st.button("Envoyer", key="send_button")
    st.markdown('</div>', unsafe_allow_html=True)
    
    if send_button and prompt:
        # Si c'est le premier message d'un nouveau chat, lui donner un ID
        if not st.session_state.messages:
            st.session_state.current_chat_id = generate_chat_id()
        
        process_user_message(prompt, uploaded_files)
        st.experimental_rerun()


if __name__ == "__main__":
    main()
