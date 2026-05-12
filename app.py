import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import date

# =========================
# CONFIGURATION
# =========================

st.set_page_config(
    page_title="Révisions Infectio",
    page_icon="🦠",
    layout="wide"
)

DATA_DIR = Path("data")

QCM_FILE = DATA_DIR / "qcm.csv"
THEMES_FILE = DATA_DIR / "themes.csv"
CAS_FILE = DATA_DIR / "cas_cliniques.csv"
PROGRESSION_FILE = DATA_DIR / "progression.csv"
PRIORITES_FILE = DATA_DIR / "analyse_priorites.csv"


# =========================
# OUTILS DE CHARGEMENT
# =========================

@st.cache_data
def load_csv(path):
    return pd.read_csv(path, sep=";", dtype=str).fillna("")


def save_progression(df):
    df.to_csv(PROGRESSION_FILE, sep=";", index=False)


def load_data():
    qcm = load_csv(QCM_FILE)
    themes = load_csv(THEMES_FILE)
    cas = load_csv(CAS_FILE)
    progression = load_csv(PROGRESSION_FILE)
    priorites = load_csv(PRIORITES_FILE)
    return qcm, themes, cas, progression, priorites


def get_progression_map(progression):
    if "id" not in progression.columns:
        return {}
    return progression.set_index("id").to_dict(orient="index")


def update_progression(progression, item_id, statut, score_confiance=None):
    if not item_id:
        return

    mask = progression["id"] == item_id

    if not mask.any():
        new_row = {
            "id": item_id,
            "type_objet": "",
            "statut": statut,
            "score_confiance": str(score_confiance if score_confiance is not None else 0),
            "nb_revisions": "1",
            "derniere_revision": str(date.today())
        }
        progression = pd.concat([progression, pd.DataFrame([new_row])], ignore_index=True)

    else:
        idx = progression[mask].index[0]

        progression.at[idx, "statut"] = statut
        progression.at[idx, "derniere_revision"] = str(date.today())

        try:
            current_nb = int(progression.at[idx, "nb_revisions"])
        except Exception:
            current_nb = 0

        progression.at[idx, "nb_revisions"] = str(current_nb + 1)

        if score_confiance is not None:
            progression.at[idx, "score_confiance"] = str(score_confiance)

    save_progression(progression)
    st.cache_data.clear()
    st.rerun()


# =========================
# OUTILS GÉNÉRAUX
# =========================

def safe_get(row, *possible_columns):
    """
    Récupère la première colonne existante et non vide.
    Utile car les fichiers CSV n'ont pas toujours exactement les mêmes noms de colonnes.
    """
    for col in possible_columns:
        if col in row.index:
            value = row.get(col, "")
            if str(value).strip():
                return str(value)
    return ""


def normalize_text(value):
    return str(value).strip().lower()


def dataframe_filter_by_column(df, label, column):
    if column not in df.columns:
        return df

    values = sorted([x for x in df[column].dropna().unique() if str(x).strip()])
    selected = st.selectbox(label, ["Toutes"] + values)

    if selected != "Toutes":
        df = df[df[column] == selected]

    return df


def global_search(df, search):
    if not search:
        return df

    search_lower = search.lower()

    return df[
        df.apply(
            lambda row: search_lower in " ".join(row.astype(str)).lower(),
            axis=1
        )
    ]


# =========================
# OUTILS QCM
# =========================

def get_qcm_question(row):
    return safe_get(
        row,
        "question_resume",
        "enonce",
        "question",
        "resume_question"
    )


def get_qcm_propositions(row):
    return safe_get(
        row,
        "propositions_resume",
        "propositions",
        "items",
        "choix"
    )


def get_qcm_reponse(row):
    return safe_get(
        row,
        "reponse",
        "correction",
        "bonne_reponse",
        "reponses"
    )


def get_qcm_explication(row):
    return safe_get(
        row,
        "explication_courte",
        "explication",
        "commentaire",
        "justification"
    )


def get_qcm_piege(row):
    return safe_get(
        row,
        "piege",
        "pieges",
        "pieges_classiques"
    )


# =========================
# STATS DE RÉCURRENCE
# =========================

def build_recurrence_stats(qcm_df, cas_df):
    """
    Construit des stats de récurrence par thème exact :
    - nombre de QCM liés au thème
    - années où le thème apparaît
    - sessions
    - nombre de cas cliniques liés au thème
    """

    stats = {}

    if "theme" in qcm_df.columns:
        for _, row in qcm_df.iterrows():
            theme = normalize_text(row.get("theme", ""))
            sous_matiere = str(row.get("sous_matiere_app", "")).strip()

            if not theme:
                continue

            key = (sous_matiere, theme)

            if key not in stats:
                stats[key] = {
                    "nb_qcm": 0,
                    "nb_cas": 0,
                    "annees": set(),
                    "sessions": set(),
                    "types": set(),
                }

            stats[key]["nb_qcm"] += 1

            if row.get("annee", ""):
                stats[key]["annees"].add(str(row.get("annee", "")))

            if row.get("session", ""):
                stats[key]["sessions"].add(str(row.get("session", "")))

            if row.get("type", ""):
                stats[key]["types"].add(str(row.get("type", "")))

    if "theme" in cas_df.columns:
        for _, row in cas_df.iterrows():
            theme = normalize_text(row.get("theme", ""))
            sous_matiere = str(row.get("sous_matiere_app", "")).strip()

            if not theme:
                continue

            key = (sous_matiere, theme)

            if key not in stats:
                stats[key] = {
                    "nb_qcm": 0,
                    "nb_cas": 0,
                    "annees": set(),
                    "sessions": set(),
                    "types": set(),
                }

            stats[key]["nb_cas"] += 1

            if row.get("annee", ""):
                stats[key]["annees"].add(str(row.get("annee", "")))

            if row.get("session", ""):
                stats[key]["sessions"].add(str(row.get("session", "")))

            stats[key]["types"].add("DP / Cas clinique")

    return stats


def display_recurrence_box(stats, sous_matiere, theme):
    key = (str(sous_matiere).strip(), normalize_text(theme))
    info = stats.get(key)

    if not info:
        st.info("📊 **Rentabilité annales :** thème non retrouvé exactement dans les autres lignes de la base.")
        return

    annees = ", ".join(sorted(info["annees"])) if info["annees"] else "Non précisé"
    sessions = ", ".join(sorted(info["sessions"])) if info["sessions"] else "Non précisé"
    types = ", ".join(sorted(info["types"])) if info["types"] else "Non précisé"

    st.info(
        f"""
📊 **Rentabilité annales**

Ce thème apparaît dans :
- **{info["nb_qcm"]} QCM**
- **{info["nb_cas"]} cas clinique(s)**
- **{len(info["annees"])} année(s)** : {annees}
- **Session(s)** : {sessions}
- **Type(s) de questions** : {types}
"""
    )


def explain_score_box(row):
    score_final = safe_get(row, "score_final")
    score_priorite = safe_get(row, "score_priorite")
    score_provisoire = safe_get(row, "score_priorite_provisoire")
    nb_questions = safe_get(row, "nb_questions_associees")
    type_questions = safe_get(row, "type_questions", "types_questions")

    with st.expander("🧮 Comprendre le score et la priorité"):
        st.write(
            """
Le **score final** est un score de rentabilité pour les révisions.

Il ne veut pas dire “probabilité exacte de tomber”, mais plutôt :

> Est-ce que ce thème vaut le coup d’être révisé maintenant si Dounssiiii a peu de temps ?
"""
        )

        if score_final:
            st.write(f"**Score final de rentabilité :** {score_final}")

        if score_priorite:
            st.write(f"**Score de priorité :** {score_priorite}")

        if score_provisoire:
            st.write(f"**Score de priorité initial :** {score_provisoire}")

        if nb_questions:
            st.write(f"**Nombre de questions associées dans ce bloc :** {nb_questions}")

        if type_questions:
            st.write(f"**Types de questions où le thème apparaît :** {type_questions}")

        st.write(
            """
La priorité tient compte de plusieurs éléments :
- importance médicale du thème ;
- présence en cas clinique / DP ;
- nombre de questions associées ;
- pièges classiques ;
- récurrence dans les annales.
"""
        )


# =========================
# CHARGEMENT DES DONNÉES
# =========================

qcm, themes, cas, progression, priorites = load_data()
progress_map = get_progression_map(progression)
recurrence_stats = build_recurrence_stats(qcm, cas)


# =========================
# HEADER
# =========================

st.title("🦠 Révisions Infectio")
st.caption(
    "Objectif : réviser efficacement bactériologie, virologie et parasitologie/mycologie "
    "sans se noyer dans les annales."
)

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Thèmes prioritaires",
        "Quiz QCM",
        "Cas cliniques",
        "Plan express"
    ]
)


# =========================
# DASHBOARD
# =========================

if page == "Dashboard":
    st.header("Tableau de bord")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("QCM", len(qcm))

    with col2:
        st.metric("Thèmes", len(themes))

    with col3:
        st.metric("Cas cliniques", len(cas))

    with col4:
        mastered = 0
        if "statut" in progression.columns:
            mastered = (progression["statut"] == "Maîtrisé").sum()
        st.metric("Objets maîtrisés", mastered)

    st.subheader("Répartition des QCM par sous-matière")

    if "sous_matiere_app" in qcm.columns:
        repartition = qcm["sous_matiere_app"].value_counts().reset_index()
        repartition.columns = ["Sous-matière", "Nombre de QCM"]
        st.dataframe(repartition, use_container_width=True)

    st.subheader("Top 15 thèmes à réviser en priorité")

    priorites_display = priorites.copy()

    if "score_final" in priorites_display.columns:
        priorites_display["score_final_num"] = pd.to_numeric(
            priorites_display["score_final"],
            errors="coerce"
        ).fillna(0)
        priorites_display = priorites_display.sort_values("score_final_num", ascending=False)

    cols_to_show = [
        c for c in [
            "id_theme",
            "sous_matiere_app",
            "theme",
            "niveau_priorite",
            "nb_questions_associees",
            "score_priorite",
            "score_final",
            "resume",
            "points_cles",
            "pieges",
            "pieges_classiques"
        ]
        if c in priorites_display.columns
    ]

    st.dataframe(priorites_display[cols_to_show].head(15), use_container_width=True)

    st.info(
        """
**Comment lire le dashboard ?**

- Plus le score final est élevé, plus le thème est rentable.
- Un thème en DP / cas clinique est souvent plus important qu’un QCM isolé.
- `nb_questions_associees` indique combien de questions du bloc analysé sont liées au thème.
- La vraie stratégie : priorités ultra fortes → QCM actifs → cas cliniques → pièges.
"""
    )


# =========================
# THEMES PRIORITAIRES
# =========================

elif page == "Thèmes prioritaires":
    st.header("🎯 Thèmes prioritaires")

    df = priorites.copy()

    if "sous_matiere_app" in df.columns:
        df = dataframe_filter_by_column(df, "Sous-matière", "sous_matiere_app")
    elif "sous_matiere" in df.columns:
        df = dataframe_filter_by_column(df, "Sous-matière", "sous_matiere")

    if "niveau_priorite" in df.columns:
        niveaux = sorted([x for x in df["niveau_priorite"].dropna().unique() if str(x).strip()])
        niveau = st.selectbox("Niveau de priorité", ["Tous"] + niveaux)

        if niveau != "Tous":
            df = df[df["niveau_priorite"] == niveau]

    search = st.text_input("Recherche par mot-clé")
    df = global_search(df, search)

    if "score_final" in df.columns:
        df["score_final_num"] = pd.to_numeric(df["score_final"], errors="coerce").fillna(0)
        df = df.sort_values("score_final_num", ascending=False)

    st.write(f"{len(df)} thème(s) trouvé(s).")

    for i, (_, row) in enumerate(df.head(100).iterrows()):
        item_id = safe_get(row, "id_theme", "id")
        if not item_id:
            item_id = f"theme_{i}"

        statut = progress_map.get(item_id, {}).get("statut", "Non vu")
        score_conf = progress_map.get(item_id, {}).get("score_confiance", "0")

        theme_title = safe_get(row, "theme", "titre")
        sous_matiere = safe_get(row, "sous_matiere_app", "sous_matiere")
        niveau_priorite = safe_get(row, "niveau_priorite")

        with st.expander(f"{theme_title} — {sous_matiere} — {niveau_priorite}"):
            st.write(f"**Statut :** {statut} | **Confiance :** {score_conf}/5")

            explain_score_box(row)

            display_recurrence_box(recurrence_stats, sous_matiere, theme_title)

            resume = safe_get(row, "resume")
            points = safe_get(row, "points_cles", "mots_cles")
            pieges = safe_get(row, "pieges", "pieges_classiques")

            if resume:
                st.write("### Résumé")
                st.write(resume)

            if points:
                st.write("### Points clés")
                st.write(points)

            if pieges:
                st.write("### Pièges classiques")
                st.write(pieges)

            col_a, col_b, col_c = st.columns(3)

            with col_a:
                if st.button("✅ Maîtrisé", key=f"theme_ok_{item_id}_{i}"):
                    update_progression(progression, item_id, "Maîtrisé", 5)

            with col_b:
                if st.button("🟡 En cours", key=f"theme_mid_{item_id}_{i}"):
                    update_progression(progression, item_id, "En cours", 3)

            with col_c:
                if st.button("🔁 À revoir", key=f"theme_review_{item_id}_{i}"):
                    update_progression(progression, item_id, "À revoir", 1)


# =========================
# QUIZ QCM
# =========================

elif page == "Quiz QCM":
    st.header("🧠 Quiz QCM")

    df = qcm.copy()

    if "sous_matiere_app" in df.columns:
        df = dataframe_filter_by_column(df, "Sous-matière", "sous_matiere_app")

    if "niveau_priorite" in df.columns:
        niveaux = sorted([x for x in df["niveau_priorite"].dropna().unique() if str(x).strip()])
        niveau = st.selectbox("Priorité", ["Toutes"] + niveaux)

        if niveau != "Toutes":
            df = df[df["niveau_priorite"] == niveau]

    search = st.text_input("Recherche dans les QCM")
    df = global_search(df, search)

    mode = st.radio("Mode", ["Aléatoire", "Dans l’ordre"], horizontal=True)

    if len(df) == 0:
        st.warning("Aucun QCM trouvé avec ces filtres.")

    else:
        if mode == "Aléatoire":
            row = df.sample(1).iloc[0]
        else:
            idx = st.number_input(
                "Numéro dans la liste filtrée",
                min_value=0,
                max_value=len(df) - 1,
                value=0
            )
            row = df.iloc[idx]

        item_id = safe_get(row, "id")
        statut = progress_map.get(item_id, {}).get("statut", "Non vu")

        theme = safe_get(row, "theme")
        annee = safe_get(row, "annee")
        session = safe_get(row, "session")
        sous_matiere = safe_get(row, "sous_matiere_app")
        type_question = safe_get(row, "type")
        numero_question = safe_get(row, "numero_question")
        niveau_priorite = safe_get(row, "niveau_priorite")

        st.subheader(theme if theme else "Question")
        st.caption(
            f"{annee} — {session} — {sous_matiere} — {type_question} — Q{numero_question} — {niveau_priorite}"
        )

        display_recurrence_box(recurrence_stats, sous_matiere, theme)

        question_text = get_qcm_question(row)
        propositions = get_qcm_propositions(row)
        reponse = get_qcm_reponse(row)
        explication = get_qcm_explication(row)
        piege = get_qcm_piege(row)

        st.write("### Question")

        if question_text:
            st.write(question_text)
        else:
            st.warning("Question vide : vérifie le nom de colonne ou la ligne dans qcm.csv.")

        if propositions:
            st.write("### Propositions")
            for part in propositions.split("|"):
                part = part.strip()
                if part:
                    st.write(f"- {part}")

        with st.expander("Afficher la correction"):
            if reponse:
                st.success(f"Réponse : {reponse}")
            else:
                st.warning("Réponse vide.")

            if explication:
                st.write(f"**Explication :** {explication}")

            if piege:
                st.write(f"**Piège :** {piege}")

        st.write(f"**Statut actuel :** {statut}")

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            if st.button("✅ Maîtrisé", key=f"qcm_ok_{item_id}"):
                update_progression(progression, item_id, "Maîtrisé", 5)

        with col_b:
            if st.button("🟡 En cours", key=f"qcm_mid_{item_id}"):
                update_progression(progression, item_id, "En cours", 3)

        with col_c:
            if st.button("🔁 À revoir", key=f"qcm_review_{item_id}"):
                update_progression(progression, item_id, "À revoir", 1)


# =========================
# CAS CLINIQUES
# =========================

elif page == "Cas cliniques":
    st.header("🩺 Cas cliniques")

    df = cas.copy()

    if "sous_matiere_app" in df.columns:
        df = dataframe_filter_by_column(df, "Sous-matière", "sous_matiere_app")
    elif "sous_matiere" in df.columns:
        df = dataframe_filter_by_column(df, "Sous-matière", "sous_matiere")

    search = st.text_input("Recherche dans les cas cliniques")
    df = global_search(df, search)

    st.write(f"{len(df)} cas clinique(s) trouvé(s).")

    for i, (_, row) in enumerate(df.iterrows()):
        item_id = safe_get(row, "id", "id_cas")
        if not item_id:
            item_id = f"cas_{i}"

        statut = progress_map.get(item_id, {}).get("statut", "Non vu")

        title = safe_get(row, "titre_cas", "titre", "theme")
        sous_matiere = safe_get(row, "sous_matiere_app", "sous_matiere")
        theme = safe_get(row, "theme")

        with st.expander(f"{title} — {sous_matiere}"):
            st.write(f"**Statut :** {statut}")

            if theme:
                display_recurrence_box(recurrence_stats, sous_matiere, theme)

            sous_theme = safe_get(row, "sous_theme")
            mots_cles = safe_get(row, "mots_cles")
            resume_clinique = safe_get(row, "enonce_resume", "resume_clinique")
            questions = safe_get(row, "questions_resume", "questions_typiques")
            correction = safe_get(row, "correction_resume", "correction_synthetique")
            points_cles = safe_get(row, "points_cles", "reflexes_a_retenir")
            pieges = safe_get(row, "pieges", "pieges_classiques")

            if theme:
                st.write(f"**Thème :** {theme}")

            if sous_theme:
                st.write(f"**Sous-thème :** {sous_theme}")

            if mots_cles:
                st.write(f"**Mots-clés :** {mots_cles}")

            if resume_clinique:
                st.write("### Résumé clinique")
                st.write(resume_clinique)

            if questions:
                st.write("### Questions typiques")
                st.write(questions)

            if correction:
                st.write("### Correction")
                st.write(correction)

            if points_cles:
                st.write("### Points clés")
                st.write(points_cles)

            if pieges:
                st.write("### Pièges")
                st.write(pieges)

            col_a, col_b, col_c = st.columns(3)

            with col_a:
                if st.button("✅ Maîtrisé", key=f"cas_ok_{item_id}_{i}"):
                    update_progression(progression, item_id, "Maîtrisé", 5)

            with col_b:
                if st.button("🟡 En cours", key=f"cas_mid_{item_id}_{i}"):
                    update_progression(progression, item_id, "En cours", 3)

            with col_c:
                if st.button("🔁 À revoir", key=f"cas_review_{item_id}_{i}"):
                    update_progression(progression, item_id, "À revoir", 1)


# =========================
# PLAN EXPRESS
# =========================

elif page == "Plan express":
    st.header("⚡ Plan express")

    duree = st.selectbox(
        "⏳ Dounssiiii, combien de temps tu as aujourd’hui pour sauver Infectio ?",
        ["30 min", "1h", "2h", "4h"]
    )

    sous_matiere_plan = st.selectbox(
        "Quelle sous-matière on attaque en mode commando ?",
        [
            "Toutes",
            "Bactériologie",
            "Virologie",
            "Parasitologie-Mycologie",
            "Transversal-Nosocomial"
        ]
    )

    st.subheader(f"🔥 Mission survie Infectio — {duree}")

    st.info(
        "Allez Dounssiiii, pas besoin de tout maîtriser parfaitement : "
        "on vise les points rentables, les thèmes qui retombent, et les pièges classiques. "
        "Objectif : valider chaque sous-matière sans paniquer."
    )

    if duree == "30 min":
        st.write("""
### 🧃 Plan mini mais rentable

1. **10 min** — Relire 3 thèmes ultra prioritaires.
2. **10 min** — Faire 5 QCM ciblés.
3. **10 min** — Revoir 1 cas clinique très rentable.

🎯 Objectif : grappiller des points vite, sans partir dans 40 chapitres.
""")

    elif duree == "1h":
        st.write("""
### 🍵 Plan solide sans surcharge

1. **20 min** — Thèmes ultra prioritaires.
2. **20 min** — Quiz QCM.
3. **15 min** — Cas clinique.
4. **5 min** — Pièges classiques.

🎯 Objectif : consolider une sous-matière au lieu de paniquer devant tout le programme.
""")

    elif duree == "2h":
        st.write("""
### ⚔️ Plan vraie session efficace

1. **30 min** — Top thèmes d’une sous-matière.
2. **40 min** — QCM actifs.
3. **30 min** — Cas cliniques.
4. **20 min** — Reprise des erreurs.

🎯 Objectif : transformer les annales en points faciles.
""")

    else:
        st.write("""
### 🫡 Plan commando demi-journée

1. **45 min** — Virologie prioritaire.
2. **45 min** — Bactériologie prioritaire.
3. **45 min** — Parasitologie/Mycologie prioritaire.
4. **45 min** — Cas cliniques.
5. **30 min** — QCM aléatoires.
6. **30 min** — Pièges classiques.

🎯 Objectif : couvrir large, mais toujours avec les thèmes les plus rentables d’abord.
""")

    st.subheader("🎯 Suggestions automatiques à faire maintenant")

    suggestions = priorites.copy()

    if sous_matiere_plan != "Toutes" and "sous_matiere_app" in suggestions.columns:
        suggestions = suggestions[suggestions["sous_matiere_app"] == sous_matiere_plan]

    if "score_final" in suggestions.columns:
        suggestions["score_final_num"] = pd.to_numeric(
            suggestions["score_final"],
            errors="coerce"
        ).fillna(0)
        suggestions = suggestions.sort_values("score_final_num", ascending=False)

    cols_to_show = [
        c for c in [
            "sous_matiere_app",
            "theme",
            "niveau_priorite",
            "nb_questions_associees",
            "score_final",
            "resume",
            "points_cles",
            "pieges"
        ]
        if c in suggestions.columns
    ]

    st.dataframe(suggestions[cols_to_show].head(10), use_container_width=True)

    st.success(
        "Dounssiiii mode commando activé 🫡 : pas de perfectionnisme, pas de panique. "
        "On sécurise les classiques, on évite les pièges, et on va chercher le 10/20 minimum partout."
    )