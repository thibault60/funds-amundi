"""
Streamlit app – Générateur de maillage interne v3
================================================
* Assure **≥ 1 lien entrant et sortant** pour chaque fonds.
* Priorité des suggestions : **Sous-type → Type → Aléatoire**.
* **Variation** : la liste des candidats est systématiquement mélangée;
  un compteur d’utilisation limite les répétitions (soft-cap).
* Export natif **Excel (.xlsx)** via `st.download_button`.

Tableur attendu
---------------
| Colonne | Étiquette (ligne 1) |
|---------|---------------------|
| A       | Nom du fonds        |
| B       | Code ISIN           |
| C       | Type                |
| E       | Sous type           |

Données à partir de **A2**.

Dependencies
------------
```
streamlit>=1.34
pandas>=2.0
openpyxl
```
"""
from __future__ import annotations

import random
from io import BytesIO

import streamlit as st
import pandas as pd

NB_LINKS = 3                # Lien 1-3 par fiche
MAX_OCCURRENCE = 10         # plafond mou : nb max d'apparitions d'un fonds comme lien

# ---------------------------------------------------------------------------
# Maillage ------------------------------------------------------------------
# ---------------------------------------------------------------------------

def build_links(df: pd.DataFrame) -> pd.DataFrame:
    """Construit trois colonnes de liens sortants en priorisant :
    Sous-type ▸ Type ▸ Aléatoire ; garantit ≥ 1 lien entrant par fonds et
    limite doucement les répétitions grâce à *MAX_OCCURRENCE*.
    """
    df = df.copy()

    by_sous = df.groupby("Sous type").groups
    by_type = df.groupby("Type").groups
    all_idx = list(df.index)

    links_out: list[list[str]] = []       # par ligne
    inbound  = [0] * len(df)              # liens entrants
    used_cnt = [0] * len(df)              # nombre de fois utilisé comme suggestion

    for idx, row in df.iterrows():
        stype, ttype = row["Sous type"], row["Type"]

        pool  = [j for j in by_sous.get(stype, []) if j != idx]
        pool += [j for j in by_type.get(ttype, []) if j != idx and j not in pool]
        pool += [j for j in all_idx if j != idx and j not in pool]

        # Mélange pour la variation :
        random.shuffle(pool)
        # Bias : trier par nombre d'usages (asc.) pour limiter répétitions :
        pool.sort(key=lambda j: used_cnt[j])

        selected = []
        for j in pool:
            if len(selected) >= NB_LINKS:
                break
            if used_cnt[j] < MAX_OCCURRENCE:   # soft-cap
                selected.append(j)
                used_cnt[j] += 1

        # Pad si manque de candidats :
        while len(selected) < NB_LINKS:
            selected.append(None)

        links_out.append([
            df.at[j, "Nom du fonds"] if j is not None else "" for j in selected
        ])
        for j in selected:
            if j is not None:
                inbound[j] += 1

    # Seconde passe : tout fonds sans lien entrant en reçoit un
    for orphan_idx, cnt in enumerate(inbound):
        if cnt:
            continue
        # Cherche une ligne avec slot vide
        donor = next((i for i, l in enumerate(links_out) if "" in l and i != orphan_idx), None)
        if donor is None:
            donor = (orphan_idx + 1) % len(df)  # fallback circulaire
        empty_pos = links_out[donor].index("")
        links_out[donor][empty_pos] = df.at[orphan_idx, "Nom du fonds"]
        inbound[orphan_idx] += 1

    df[["Lien 1", "Lien 2", "Lien 3"]] = links_out
    return df

# ---------------------------------------------------------------------------
# Interface Streamlit --------------------------------------------------------
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="Maillage interne des fonds", layout="wide")
    st.title("🔗 Générateur de maillage interne – v3 (Sous-type ▸ Type ▸ Random)")

    st.markdown("""
    **Étapes :**
    1. Déposez un fichier **Excel (.xlsx)** comportant les colonnes obligatoires ;
    2. Cliquez sur *Télécharger* pour récupérer le fichier enrichi (Lien 1-3).
    """)

    file = st.file_uploader("Fichier Excel (.xlsx)", type="xlsx")
    if file is None:
        st.info("En attente d'un fichier …")
        return

    try:
        df_in = pd.read_excel(file, engine="openpyxl")
    except Exception as e:
        st.error(f"Erreur de lecture : {e}")
        return

    required = {"Nom du fonds", "Code ISIN", "Type", "Sous type"}
    if missing := required - set(df_in.columns):
        st.error("Colonnes manquantes : " + ", ".join(missing))
        return

    df_out = build_links(df_in)

    st.success("Maillage généré ✔️")
    st.dataframe(df_out, height=600)

    # Export Excel -----------------------------------------------------------
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_out.to_excel(writer, index=False, sheet_name="Fonds")
    buffer.seek(0)

    st.download_button(
        label="📥 Télécharger l’Excel enrichi",
        data=buffer,
        file_name="fonds_mailles.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

if __name__ == "__main__":
    main()
