"""
Streamlit app – Générateur de maillage interne entre fonds
---------------------------------------------------------
Chargement d'un CSV (colonnes : Nom du fonds, Code ISIN, Type, Sous type),
calcul de 3 liens internes (même Sous-type, puis Type) et garantie qu'aucun
fonds ne reste sans lien entrant.

Exécuter en local :
    pip install -r requirements.txt
    streamlit run app.py

requirements.txt :
    streamlit>=1.34
    pandas
"""
import streamlit as st
import pandas as pd

NB_LINKS = 3  # nombre de liens internes par fiche (colonnes F-G-H)

def build_links(df: pd.DataFrame) -> pd.DataFrame:
    """Retourne une copie du DataFrame enrichi avec trois colonnes :
    Lien 1, Lien 2, Lien 3 ; assure ≥ 1 lien entrant par fonds.
    """
    df = df.copy()

    # Pré-création des structures
    inbound = {i: 0 for i in df.index}      # compteur de liens entrants
    links   = [[] for _ in df.index]        # liens sortants par ligne

    # Indexation
    by_sous = df.groupby("Sous type").groups
    by_type = df.groupby("Type").groups

    # 1) Première passe : même Sous-type → même Type
    for idx, row in df.iterrows():
        sous_type = row["Sous type"]
        f_type    = row["Type"]

        pool  = [j for j in by_sous.get(sous_type, []) if j != idx]
        pool += [j for j in by_type.get(f_type, []) if j != idx and j not in pool]

        pool.sort(key=lambda j: df.at[j, "Nom du fonds"])  # tri alphabétique
        picks = pool[:NB_LINKS]

        # Enregistrement et comptage
        links[idx] = [df.at[j, "Nom du fonds"] for j in picks] + [""] * (NB_LINKS - len(picks))
        for j in picks:
            inbound[j] += 1

    # 2) Seconde passe : tout fonds sans lien entrant en reçoit un
    for orphan_idx, cnt in inbound.items():
        if cnt > 0:
            continue  # déjà lié

        sous_type = df.at[orphan_idx, "Sous type"]
        f_type    = df.at[orphan_idx, "Type"]

        # Cherche un donneur avec slot libre (même Sous-type -> même Type)
        donors = [i for i in by_sous.get(sous_type, []) if i != orphan_idx and "" in links[i]]
        if not donors:
            donors = [i for i in by_type.get(f_type, []) if i != orphan_idx and "" in links[i]]
        if not donors:
            continue  # pas de place dispo ; rare mais possible

        donor = donors[0]
        empty_pos = links[donor].index("")
        links[donor][empty_pos] = df.at[orphan_idx, "Nom du fonds"]
        inbound[orphan_idx] += 1

    # Ajout des colonnes au DataFrame
    df[["Lien 1", "Lien 2", "Lien 3"]] = links
    return df

# ---------------------------------------------------------------------------
# Interface Streamlit
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Maillage interne des fonds", layout="wide")

st.title("📈 Générateur de maillage interne pour fonds")

st.markdown("""
Téléchargez un fichier **CSV** contenant au minimum les colonnes :
* **Nom du fonds**
* **Code ISIN**
* **Type**
* **Sous type**

Le script calcule jusqu'à trois liens internes logiques pour chaque fonds et garantit qu'aucun fonds ne reste sans lien entrant.
""")

uploaded = st.file_uploader("Fichier CSV", type="csv")

if uploaded:
    df_in = pd.read_csv(uploaded)
    required = {"Nom du fonds", "Code ISIN", "Type", "Sous type"}
    if not required.issubset(df_in.columns):
        st.error(f"Le CSV doit contenir les colonnes : {', '.join(required)}")
        st.stop()

    df_out = build_links(df_in)

    st.success("Maillage généré !")
    st.dataframe(df_out, height=600)

    csv = df_out.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Télécharger le CSV enrichi",
        data=csv,
        file_name="fonds_mailles.csv",
        mime="text/csv",
    )
else:
    st.info("Déposez votre fichier CSV pour commencer.")
