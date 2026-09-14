import streamlit as st

from cv_tailor.adapters.exporters import to_docx, to_pdf, to_txt
from cv_tailor.adapters.loader import extract_text_from_docx, load_resumes
from cv_tailor.adapters.ollama_client import OllamaClient
from cv_tailor.config import MODEL, PROMPT_RANK, PROMPT_REWRITE
from cv_tailor.domain.protocols import LLMError, LLMTimeout, LLMUnavailable
from cv_tailor.domain.ranking import rank
from cv_tailor.domain.rewriting import rewrite


@st.cache_resource
def get_llm() -> OllamaClient:
    """One client per session: it holds an httpx connection pool."""
    return OllamaClient(MODEL)


def init_session_state():
    if "step" not in st.session_state:
        st.session_state.step = "WELCOME"
    if "job_description" not in st.session_state:
        st.session_state.job_description = ""
    if "rankings" not in st.session_state:
        st.session_state.rankings = []
    if "selected_cv" not in st.session_state:
        st.session_state.selected_cv = None
    if "result" not in st.session_state:
        st.session_state.result = ""
    if "resumes" not in st.session_state:
        st.session_state.resumes = {}


def welcome_screen():
    st.title("🚀 CV Booster")
    st.write("Optimisez vos CV selon les descriptions de poste")
    if st.button("Commencer"):
        st.session_state.step = "JD_INPUT"
        st.rerun()


def jd_input_screen():
    st.title("📋 Description du poste")

    # Créer des onglets pour les deux options d'entrée
    tab1, tab2 = st.tabs(["📝 Coller le texte", "📄 Uploader un fichier Word"])

    jd = st.session_state.job_description

    with tab1:
        jd_text = st.text_area(
            "Collez la description du poste",
            value=st.session_state.job_description,
            height=300,
            key="jd_text_input",
        )
        if jd_text:
            jd = jd_text

    with tab2:
        uploaded_file = st.file_uploader(
            "Uploadez un fichier Word (.docx)",
            type=["docx"],
            help="Sélectionnez un fichier Word contenant la description du poste",
        )

        if uploaded_file is not None:
            try:
                jd = extract_text_from_docx(uploaded_file)
                st.success(f"✅ Fichier '{uploaded_file.name}' chargé avec succès!")
                # Afficher un aperçu du contenu
                with st.expander("👁️ Aperçu du contenu"):
                    st.text_area("Contenu extrait", value=jd, height=200, disabled=True)
            except Exception as e:
                st.error(f"❌ Erreur lors de la lecture du fichier: {str(e)}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Retour"):
            st.session_state.step = "WELCOME"
            st.rerun()
    with col2:
        if st.button("Analyser →") and jd and jd.strip():
            st.session_state.job_description = jd
            try:
                resumes = load_resumes()
                with st.spinner(
                    "🔍 Analyse des CV en cours... Cela peut prendre quelques instants."
                ):
                    rankings = rank(
                        st.session_state.job_description,
                        resumes,
                        get_llm(),
                        PROMPT_RANK,
                    )
                st.session_state.resumes = resumes
                st.session_state.rankings = rankings
                st.session_state.step = "RANKING_DISPLAY"
                st.rerun()
            except LLMUnavailable:
                st.error(
                    "❌ Impossible de se connecter à Ollama. Vérifiez que le service est démarré."
                )
            except LLMTimeout:
                st.error("⏱️ Le traitement a pris trop de temps. Réessayez.")
            except LLMError as e:
                st.error(f"❌ Erreur lors de l'analyse: {e}")


def ranking_display_screen():
    st.title("📊 Classement des CV")
    for i, ranking in enumerate(st.session_state.rankings, 1):
        st.write(f"{i}. {ranking.name} - {ranking.score} - {ranking.explanation}")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Retour"):
            st.session_state.step = "JD_INPUT"
            st.rerun()
    with col2:
        if st.button("Sélectionner un CV →"):
            st.session_state.step = "CV_SELECTION"
            st.rerun()


def cv_selection_screen():
    st.title("📄 Sélection du CV")
    rankings = {r.name: r for r in st.session_state.rankings}
    selected_name = st.selectbox(
        "Choisissez un CV",
        list(rankings),
        format_func=lambda name: f"{name} ({rankings[name].score})",
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Retour"):
            st.session_state.step = "RANKING_DISPLAY"
            st.rerun()
    with col2:
        if st.button("Générer →"):
            st.session_state.selected_cv = selected_name
            try:
                with st.spinner("✍️ Optimisation du wording du CV en cours..."):
                    rewritten = rewrite(
                        st.session_state.job_description,
                        selected_name,
                        st.session_state.resumes[selected_name],
                        get_llm(),
                        PROMPT_REWRITE,
                    )
                st.session_state.result = rewritten.content
                st.session_state.step = "RESULT"
                st.rerun()
            except LLMUnavailable:
                st.error(
                    "❌ Impossible de se connecter à Ollama. Vérifiez que le service est démarré."
                )
            except LLMTimeout:
                st.error("⏱️ Le traitement a pris trop de temps. Réessayez.")
            except LLMError as e:
                st.error(f"❌ Erreur lors de l'optimisation: {e}")


def result_screen():
    st.title("✅ Résultat")
    st.text_area("CV Optimisé", value=st.session_state.result, height=400)

    downloads = [
        (
            "📥 Télécharger (Word)",
            to_docx,
            "cv_optimise.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("📥 Télécharger (PDF)", to_pdf, "cv_optimise.pdf", "application/pdf"),
        ("📥 Télécharger (TXT)", to_txt, "cv_optimise.txt", "text/plain"),
    ]

    col1, *cols = st.columns(4)
    with col1:
        if st.button("← Retour"):
            st.session_state.step = "CV_SELECTION"
            st.rerun()

    for column, (label, exporter, filename, mime) in zip(cols, downloads, strict=True):
        with column:
            st.download_button(
                label=label,
                data=exporter(st.session_state.result),
                file_name=filename,
                mime=mime,
            )


def main():
    st.set_page_config(page_title="CV Booster", page_icon="🚀", layout="wide")
    init_session_state()

    screens = {
        "WELCOME": welcome_screen,
        "JD_INPUT": jd_input_screen,
        "RANKING_DISPLAY": ranking_display_screen,
        "CV_SELECTION": cv_selection_screen,
        "RESULT": result_screen,
    }

    screens[st.session_state.step]()


if __name__ == "__main__":
    main()
