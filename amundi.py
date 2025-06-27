"""
Streamlit app – Générateur de maillage interne (v2)
--------------------------------------------------
Priorité des liens sortants (colonnes « Lien 1‑3 ») :
1. **Même Sous type**
2. **Même Type**
3. **Aléatoire** parmi le reste si nécessaire

✓ Garantit qu’un fonds possède toujours **au moins un lien sortant**
✓ Les orphelins (aucun lien entrant) sont rarissimes grâce au fallback aléatoire ;
  si vous préférez un contrôle strict, activez _ensure_one_inbound_ (voir code).

Structure Excel attendue
-----------------------
| Colonne | Intitulé (ligne 1) |
|---------|--------------------|
| A       | Nom du fonds       |
| B       | Code ISIN          |
| C       | Type               |
| E       | Sous type          |

Données à partir de **A2**. Extension : .xlsx (moteur *openpyxl*).

requirements.txt
----------------
```
streamlit>=1.34
pandas
openpyxl
```
"""
import random
import streamlit as st
import pandas as pd

NB_LINKS = 3  # Lien 1‑3

# ----------------------------------------------------------------------------
# FONCTION DE MAILLAGE -------------------------------------------------------
# ----------------------------------------------------------------------------

def build_links(df: pd.DataFrame, ensure_one_inbound: bool = False) -> pd.DataFrame:
    """Retourne un DataFrame enrichi de trois colonnes « Lien 1‑3 ».

    Priorité : Sous type → Type → Random.  
    `ensure_one_inbound` (False par défaut) : si True, garantit au
    moins 1 lien entrant par fonds via un post‑traitement (légère
    complexité supplémentaire).
    """
    df = df.copy()

    # Index pour accès rapide
    by_sous = df.groupby("Sous type").groups
    by_type = df.groupby("Type").groups
    all_idx = list(df.index)

    links_out = []          # pour chaque ligne : [l1,l2,l3]
    inbound    = [0]*len(df)  # compteurs entrants (optionnel)

    for idx, row in df.iterrows():
        stype = row["Sous type"]
        ttype = row["Type"]

        # 1. mêmes Sous‑type (hors ligne courante)
        pool = [j for j in by_sous.get(stype, []) if j != idx]

        # 2. mêmes Type, hors doublons
        pool += [j for j in by_type.get(ttype, []) if j != idx and j not in pool]

        # 3. aléatoire si < NB_LINKS
        if len(pool) < NB_LINKS:
            remaining = [j for j in all_idx if j != idx and j not in pool]
            random.shuffle(remaining)
            pool += remaining

        selected = pool[:NB_LINKS]
        line_links = [df.at[j, "Nom du fonds"] for j in selected]
        links_out.append(line_links)

        # inbound count si on veut la contrainte stricte
        for j in selected:
            inbound[j] += 1

    # Post‑traitement inbound optionnel
    if ensure_one_inbound:
        for i, cnt in enumerate(inbound):
            if cnt == 0:
                donor = next((d for d,l in enumerate(links_out)
                               if i != d and df.at[i,"Nom du fonds"] not in l), None)
                if donor is not None:
                    links_out[donor][-1] = df.at[i, "Nom du fonds"]

    df[["Lien 1", "Lien 2", "Lien 3"]] = links_out
    return df

# ----------------------------------------------------------------------------
# INTERFACE STREAMLIT --------------------------------------------------------
# ----------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="Maillage interne des fonds", layout="wide")
    st.title("📈 Générateur de maillage interne – Priorité Sous‑type > Type > Aléatoire")

    st.markdown(
        """Chargez un fichier **Excel (.xlsx)** avec les colonnes :
        **Nom du fonds**, **Code ISIN**, **Type**, **Sous type** (ligne 1)."""
    )

    file = st.file_uploader("Déposez le fichier Excel", type="xlsx")
    ensure_inb = st.checkbox("Garantir ≥ 1 lien entrant par fonds", value=False)

    if not file:
        st.info("En attente d'un fichier …")
        return

    try:
        df_in = pd.read_excel(file, engine="openpyxl")
    except Exception as e:
        st.error(f"Erreur lecture Excel : {e}")
        return

    required = {"Nom du fonds", "Code ISIN", "Type", "Sous type"}
    miss = required - set(df_in.columns)
    if miss:
        st.error("Colonnes manquantes : " + ", ".join(miss))
        return

    df_out = build_links(df_in, ensure_one_inbound=ensure_inb)

    st.success("Maillage généré ✔️")
    st.dataframe(df_out, height=600)

    csv = df_out.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Télécharger le CSV enrichi", csv, "fonds_mailles.csv", "text/csv")

if __name__ == "__main__":
    main()
