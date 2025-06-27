"""
Streamlit app – Générateur de maillage interne entre fonds (import Excel)
------------------------------------------------------------------------
Ce script Streamlit charge un **fichier Excel (.xlsx)** contenant AU MINIMUM
les quatre colonnes :
    Nom du fonds | Code ISIN | Type | Sous type
(la première ligne – ligne 1 – contient ces en-têtes ; les données
commencent en A2).

Il calcule pour chaque ligne jusqu'à trois liens internes :
1. autres fonds partageant le même Sous-type ;
2. complété, si besoin, par d'autres fonds du même Type ;
3. assure qu'aucun fonds n'est dépourvu de lien entrant.

Pour l'exécuter localement :
    pip install -r requirements.txt
    streamlit run app.py

requirements.txt :
    streamlit>=1.34
    pandas
    openpyxl   # pour lire les .xlsx
"""
import streamlit as st
import pandas as pd

NB_LINKS = 3  # nombre de liens internes à générer

# ---------------------------------------------------------------------------
# FONCTION DE MAILLAGE -------------------------------------------------------
# ---------------------------------------------------------------------------

def build_links(df: pd.DataFrame) -> pd.DataFrame:
    """Renvoie un DataFrame enrichi de trois colonnes « Lien 1-3 » et assure
    ≥ 1 lien entrant par fonds."""
    df = df.copy()
    inbound = {i: 0 for i in df.index}
    links   = [[] for _ in df.index]

    by_sous = df.groupby("Sous type").groups  # index par Sous-type
    by_type = df.groupby("Type").groups      # index par Type

    # 1) première passe : même Sous-type → même Type
    for idx, row in df.iterrows():
        stype = row["Sous type"]
        ttype = row["Type"]

        pool  = [j for j in by_sous.get(stype, []) if j != idx]
        pool += [j for j in by_type.get(ttype, []) if j != idx and j not in pool]
        pool.sort(key=lambda j: df.at[j, "Nom du fonds"])  # tri déterministe

        picks = pool[:NB_LINKS]
        links[idx] = [df.at[j, "Nom du fonds"] for j in picks] + [""]*(NB_LINKS-len(picks))
        for j in picks:
            inbound[j] += 1

    # 2) seconde passe : on s’assure qu’il reste 0 orphelin
    for orphan_idx, cnt in inbound.items():
        if cnt:
            continue  # déjà au moins un lien entrant
        stype = df.at[orphan_idx, "Sous type"]
        ttype = df.at[orphan_idx, "Type"]

        potential = [i for i in by_sous.get(stype, []) if i != orphan_idx and "" in links[i]]
        if not potential:
            potential = [i for i in by_type.get(ttype, []) if i != orphan_idx and "" in links[i]]
        if not potential:
            continue  # aucun slot libre ; cas extrême

        donor = potential[0]
        slot  = links[donor].index("")
        links[donor][slot] = df.at[orphan_idx, "Nom du fonds"]
        inbound[orphan_idx] += 1

    df[["Lien 1", "Lien 2", "Lien 3"]] = links
    return df

# ---------------------------------------------------------------------------
# INTERFACE STREAMLIT --------------------------------------------------------
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Maillage interne des fonds", layout="wide")

st.title("📈 Générateur de maillage interne – Import Excel")

st.markdown(
    """
Chargez un fichier **Excel (.xlsx)** organisé comme suit :

| Colonne | Intitulé exact | Commentaire |
|---------|----------------|-------------|
| A | **Nom du fonds** | texte complet |
| B | **Code ISIN** | facultatif dans le maillage |
| C | **Type** | ex. Action, Obligataire… |
| E | **Sous type** | ex. Actions Asie |

La ligne 1 doit contenir ces en-têtes ; les données commencent ligne 2.
    """
)

uploaded = st.file_uploader("Déposez votre fichier .xlsx", type=["xlsx"])

if uploaded is None:
    st.info("En attente d'un fichier Excel…")
    st.stop()

try:
    df_input = pd.read_excel(uploaded, engine="openpyxl")
except Exception as e:
    st.error(f"Erreur de lecture du fichier : {e}")
    st.stop()

required_cols = {"Nom du fonds", "Code ISIN", "Type", "Sous type"}
missing = required_cols - set(df_input.columns)
if missing:
    st.error(f"Colonnes manquantes : {', '.join(missing)}")
    st.stop()

st.success("Fichier chargé ✔️ – génération des liens…")

df_output = build_links(df_input)

st.subheader("Aperçu du maillage interne")
st.dataframe(df_output, height=600)

csv_bytes = df_output.to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Télécharger le CSV enrichi",
    data=csv_bytes,
    file_name="fonds_mailles.csv",
    mime="text/csv",
)
