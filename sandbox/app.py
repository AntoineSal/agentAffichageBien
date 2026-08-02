"""
Application Streamlit principale pour la sandbox.
Gère l'interface utilisateur, l'historique des messages, et l'intégration avec l'agent d'affichage.
"""

import streamlit as st
from typing import List, Dict, Optional, Tuple
from .utils import call_mistral_api
import os
import json

# Importer la fonction du stagiaire
from agentAffichage.afficheur import afficherJoliment


def initialize_session_state():
    """Initialise les variables de session si elles n'existent pas."""
    if "messages" not in st.session_state:
        st.session_state.messages: List[Dict[str, str]] = []
    
    if "mode" not in st.session_state:
        st.session_state.mode: str = "Utilisateur"  # ou "Agent"
    
    if "api_key" not in st.session_state:
        st.session_state.api_key: Optional[str] = None
    
    if "show_code" not in st.session_state:
        st.session_state.show_code: bool = False
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history: List[Dict] = []
    
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id: Optional[str] = None


def reset_chat():
    """Réinitialise l'historique des messages."""
    st.session_state.messages = []
    st.session_state.show_code = False


def generate_chat_id() -> str:
    """Génère un ID unique pour un chat."""
    import uuid
    return str(uuid.uuid4())[:8]


def save_current_chat():
    """Sauvegarde le chat actuel dans l'historique."""
    if not st.session_state.messages:
        return
    
    from datetime import datetime
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
            st.session_state.show_code = False
            break


def delete_chat(chat_id: str):
    """Supprime un chat de l'historique."""
    st.session_state.chat_history = [
        chat for chat in st.session_state.chat_history if chat["id"] != chat_id
    ]
    if st.session_state.current_chat_id == chat_id:
        st.session_state.messages = []
        st.session_state.current_chat_id = None


def display_messages():
    """Affiche les messages de l'historique dans le chat."""
    for message in st.session_state.messages:
        # Utiliser un conteneur avec un style personnalisé pour simuler chat_message
        if message["role"] == "user":
            st.markdown(f"""
            <div style="
                background-color: #e3f2fd;
                padding: 12px 16px;
                border-radius: 12px;
                margin: 8px 0;
                margin-left: 20%;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            ">
                <strong>Utilisateur :</strong><br/>{message["content"]}
            </div>
            """, unsafe_allow_html=True)
        else:  # agent
            st.markdown(f"""
            <div style="
                background-color: #f1f1f1;
                padding: 12px 16px;
                border-radius: 12px;
                margin: 8px 0;
                margin-right: 20%;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            ">
                <strong>Agent :</strong><br/>{message["content"]}
            </div>
            """, unsafe_allow_html=True)


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
    
    Returns:
        Tuple[str, str]: (response_text, html_output) pour l'aperçu du code.
    """
    # Ajouter le message utilisateur à l'historique
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Afficher le message utilisateur (simulé avec markdown)
    st.markdown(f"""
    <div style="
        background-color: #e3f2fd;
        padding: 12px 16px;
        border-radius: 12px;
        margin: 8px 0;
        margin-left: 20%;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    ">
        <strong>Utilisateur :</strong><br/>{prompt}
    </div>
    """, unsafe_allow_html=True)
    
    # Traiter selon le mode
    if st.session_state.mode == "Utilisateur":
        # Appel à l'API Mistral
        with st.spinner("Réflexion en cours..."):
            response = get_mistral_response(prompt)
    else:  # Mode "Agent"
        # Simuler une réponse directe (sans API)
        response = prompt  # Dans ce mode, on affiche directement ce qui est saisi
    
    # Appeler la fonction du stagiaire pour générer l'affichage
    html_output = afficherJoliment(response, uploaded_files)
    
    # Stocker la dernière réponse générée pour l'aperçu du code
    st.session_state.last_response = response
    st.session_state.last_html_output = html_output
    
    # Ajouter la réponse à l'historique
    st.session_state.messages.append({"role": "agent", "content": html_output})
    
    # Afficher la réponse (HTML généré par afficherJoliment)
    st.markdown(f"""
    <div style="
        background-color: #f1f1f1;
        padding: 12px 16px;
        border-radius: 12px;
        margin: 8px 0;
        margin-right: 20%;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    ">
        <strong>Agent :</strong><br/>{html_output}
    </div>
    """, unsafe_allow_html=True)
    
    return response, html_output


def main():
    """Fonction principale de l'application Streamlit."""
    # Configuration de la page
    st.set_page_config(
        page_title="Sandbox Agent Affichage",
        page_icon="🎨",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Appliquer le CSS personnalisé
    try:
        with open("sandbox/styles/custom.css", "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("Fichier CSS personnalisé introuvable. Utilisation des styles par défaut.")
    
    # Initialisation de l'état de la session
    initialize_session_state()
    
    # Titre de l'application
    st.title("🎨 Sandbox pour l'Agent d'Affichage")
    st.markdown("""
    Bienvenue dans la sandbox pour tester l'agent d'affichage.
    
    - **Mode Utilisateur** : Vos messages sont envoyés à l'API Mistral avant d'être affichés.
    - **Mode Agent** : Vos messages sont directement affichés comme réponse (simulation).
    """)
    
    # Bouton pour afficher/masquer le code généré (en haut à droite)
    col1, col2 = st.columns([0.9, 0.1])
    with col2:
        if st.button("</>", help="Afficher/Masquer le code généré"):
            st.session_state.show_code = not st.session_state.show_code
    
    # Afficher l'aperçu du code si activé
    if st.session_state.show_code and hasattr(st.session_state, 'last_html_output'):
        with st.expander("📜 Code généré", expanded=True):
            st.code(st.session_state.last_html_output, language="html")
            if st.button("📋 Copier le code", key="copy_code"):
                st.session_state.code_copied = True
                st.success("Code copié dans le presse-papiers !")
                # Utiliser JavaScript pour copier dans le presse-papiers
                st.markdown("""
                <script>
                    navigator.clipboard.writeText(`""" + st.session_state.last_html_output.replace('`', '\\`') + """`);
                </script>
                """, unsafe_allow_html=True)
    
    # Barre latérale pour les paramètres et l'historique
    with st.sidebar:
        st.header("⚙️ Paramètres")
        
        # Sélection du mode
        st.session_state.mode = st.radio(
            "Mode",
            options=["Utilisateur", "Agent"],
            index=0 if st.session_state.mode == "Utilisateur" else 1,
            help="""
            - **Utilisateur** : Envoie les messages à l'API Mistral.
            - **Agent** : Affiche directement les messages sans appel API.
            """
        )
        
        # Clé API Mistral (uniquement en mode Utilisateur)
        if st.session_state.mode == "Utilisateur":
            st.session_state.api_key = st.text_input(
                "Clé API Mistral",
                type="password",
                value=st.session_state.get("api_key", ""),
                help="Votre clé API Mistral. Si non fournie, la variable d'environnement MISTRAL_API_KEY sera utilisée."
            )
        
        # Upload de fichiers
        st.markdown("---")
        st.header("📁 Fichiers")
        uploaded_files = st.file_uploader(
            "Upload de fichiers",
            accept_multiple_files=True,
            help="Les fichiers uploadés seront passés à la fonction afficherJoliment."
        )
        
        # Gestion de l'historique des chats
        st.markdown("---")
        st.header("💬 Historique des chats")
        
        # Bouton pour sauvegarder le chat actuel
        if st.session_state.messages:
            if st.button("💾 Sauvegarder ce chat"):
                save_current_chat()
                st.success("Chat sauvegardé !")
                st.experimental_rerun()
        
        # Bouton pour créer un nouveau chat
        if st.button("🆕 Nouveau Chat"):
            if st.session_state.messages:
                save_current_chat()  # Sauvegarder le chat actuel avant de réinitialiser
            reset_chat()
            st.experimental_rerun()
        
        # Liste des chats précédents
        if st.session_state.chat_history:
            st.markdown("**Chats précédents**")
            for chat in reversed(st.session_state.chat_history):
                chat_id = chat["id"]
                timestamp = chat.get("timestamp", "Inconnu")
                chat_preview = chat["messages"][0]["content"][:25] + "..." if chat["messages"] else "Chat vide"
                
                # Afficher le timestamp et l'aperçu
                chat_display = f"{timestamp[:10]} - {chat_preview}"
                
                col1, col2 = st.columns([0.85, 0.15])
                with col1:
                    if st.button(f"📄 {chat_display}", key=f"load_{chat_id}"):
                        load_chat(chat_id)
                        st.experimental_rerun()
                with col2:
                    if st.button("❌", key=f"delete_{chat_id}"):
                        delete_chat(chat_id)
                        st.experimental_rerun()
        else:
            st.info("Aucun chat précédent.")
    
    # Affichage de l'historique des messages
    display_messages()
    
    # Barre de chat en bas (pour Streamlit 1.11.1, on utilise text_input + bouton)
    col1, col2 = st.columns([0.9, 0.1])
    with col1:
        prompt = st.text_input("Écrivez un message...", key="chat_input")
    with col2:
        send_button = st.button("Envoyer", key="send_button")
    
    if send_button and prompt:
        # Si c'est le premier message d'un nouveau chat, lui donner un ID
        if not st.session_state.messages:
            st.session_state.current_chat_id = generate_chat_id()
            st.session_state.chat_timestamp = st.session_state.get("chat_timestamp", "")
        
        process_user_message(prompt, uploaded_files)
        st.experimental_rerun()


if __name__ == "__main__":
    main()
