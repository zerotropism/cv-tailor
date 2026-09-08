from io import BytesIO

import streamlit as st
from docx import Document
from markdown import markdown

from cv_loader import load_resumes
from llm_client import rank_cvs, rewrite_cv


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


def welcome_screen():
    st.title("🚀 CV Booster")
    st.write("Optimisez vos CV selon les descriptions de poste")
    if st.button("Commencer"):
        st.session_state.step = "JD_INPUT"
        st.rerun()


def extract_text_from_docx(file) -> str:
    """Extrait le texte d'un fichier Word."""
    doc = Document(file)
    full_text = []
    for paragraph in doc.paragraphs:
        full_text.append(paragraph.text)
    return "\n".join(full_text)


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
                    top_resumes = rank_cvs(st.session_state.job_description, resumes)
                st.session_state.rankings = [
                    f"{resume['name']} - {resume['score']} - {resume['explanation']}"
                    for resume in top_resumes
                ]
                st.session_state.step = "RANKING_DISPLAY"
                st.rerun()
            except ConnectionError:
                st.error(
                    "❌ Impossible de se connecter à Ollama. Vérifiez que le service est démarré."
                )
            except TimeoutError:
                st.error("⏱️ Le traitement a pris trop de temps. Réessayez.")
            except Exception as e:
                st.error(f"❌ Erreur lors de l'analyse: {str(e)}")


def ranking_display_screen():
    st.title("📊 Classement des CV")
    for i, ranking in enumerate(st.session_state.rankings, 1):
        st.write(f"{i}. {ranking}")
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
    selected_resume = st.selectbox("Choisissez un CV", st.session_state.rankings)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Retour"):
            st.session_state.step = "RANKING_DISPLAY"
            st.rerun()
    with col2:
        if st.button("Générer →"):
            st.session_state.selected_cv = selected_resume
            try:
                with st.spinner("✍️ Optimisation du wording du CV en cours..."):
                    st.session_state.result = rewrite_cv(
                        st.session_state.job_description, selected_resume
                    )
                st.session_state.step = "RESULT"
                st.rerun()
            except ConnectionError:
                st.error(
                    "❌ Impossible de se connecter à Ollama. Vérifiez que le service est démarré."
                )
            except TimeoutError:
                st.error("⏱️ Le traitement a pris trop de temps. Réessayez.")
            except Exception as e:
                st.error(f"❌ Erreur lors de l'optimisation: {str(e)}")


def result_screen():
    st.title("✅ Résultat")
    st.text_area("CV Optimisé", value=st.session_state.result, height=400)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("← Retour"):
            st.session_state.step = "CV_SELECTION"
            st.rerun()
    with col2:
        # Téléchargement Word
        from exporters import to_word

        doc = to_word(st.session_state.result)
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        st.download_button(
            label="📥 Télécharger (Word)",
            data=buffer.getvalue(),
            file_name="cv_optimise.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    with col3:
        # Téléchargement PDF
        from weasyprint import HTML

        html_content = markdown(st.session_state.result, extensions=["extra", "nl2br"])
        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        st.download_button(
            label="📥 Télécharger (PDF)",
            data=pdf_buffer.getvalue(),
            file_name="cv_optimise.pdf",
            mime="application/pdf",
        )
    with col4:
        # Téléchargement TXT
        st.download_button(
            label="📥 Télécharger (TXT)",
            data=st.session_state.result.encode("utf-8"),
            file_name="cv_optimise.txt",
            mime="text/plain",
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
