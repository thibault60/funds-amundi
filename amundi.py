"""
Streamlit app – Générateur de maillage interne v4
=================================================
* **Règle principale** : les fonds partageant le même *nom racine* (partie avant le premier tiret « - ») se maillent entre eux en priorité ;
* Sinon, on complète avec des fonds du **même Type** ;
* Enfin, s’il manque encore des candidats, on pioche aléatoirement dans le reste ;
* Chaque fonds reçoit **au moins un lien entrant et sortant** ;
* Export natif **Excel .xlsx**.

Tableur requis (données dès A2)
------------------------------
| Colonne | Intitulé (ligne 1) |
|---------|--------------------|
| A       | Nom du fonds       |
| B       | Code ISIN          |
| C       | Type               |
| E       | Sous type          |

Dépendances
-----------
```
streamlit>=1.34
pandas>=2.0
openpyxl
```
"""
from __future__ import annotations

import random
import re
from io import BytesIO

import streamlit as st
import pandas as pd

NB_LINKS = 3          # Lien 1-3 par fonds
SOFT_CAP = 12         # max « soft » d’apparitions d’un fonds comme suggestion

# ----------------------------------------------------------------------------
# Utilitaires ----------------------------------------------------------------
# ----------------------------------------------------------------------------

def root_name(name: str) -> str:
    """Renvoie la partie du nom avant le premier « - », normalisée."""
    return re.split(r"\s*-", name, 1)[0].strip().lower()

# ----------------------------------------------------------------------------
# Fonction principale de maillage -------------------------------------------
# ----------------------------------------------------------------------------

def build_links(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Groupes
    by_root = {}  # nom racine → index[]
    by_type = df.groupby("Type").groups

    for idx, nom in enumerate(df["Nom du fonds"]):
        key = root_name(nom)
        by_root.setdefault(key, []).append(idx)

    all_idx = list(df.index)
    links_out: list[list[str]] = []
    inbound  = [0]*len(df)
    used_cnt = [0]*len(df)

    for idx, row in df.iterrows():
        rkey  = root_name(row["Nom du fonds"])
        ttype = row["Type"]

        pool  = [j for j in by_root.get(rkey, []) if j != idx]
        pool += [j for j in by_type.get(ttype, []) if j != idx and j not in pool]
        pool += [j for j in all_idx if j != idx and j not in pool]

        random.shuffle(pool)
        pool.sort(key=lambda j: used_cnt[j])

        selected: list[int|None] = []
        for j in pool:
            if len(selected) == NB_LINKS:
                break
            if used_cnt[j] < SOFT_CAP:
                selected.append(j)
                used_cnt[j] += 1
        while len(selected) < NB_LINKS:
            selected.append(None)

        links_out.append([
            df.at[j, "Nom du fonds"] if j is not None else "" for j in selected
        ])
        for j in selected:
            if j is not None:
                inbound[j] += 1

    # Seconde passe : garantir ≥1 lien entrant
    for o_idx, cnt in enumerate(inbound):
        if cnt:
            continue
        donor = next(
            (i for i,l in enumerate(links_out) if "" in l and i != o_idx),
            None
        )
        if donor is None:
            donor = (o_idx+1) % len(df)
        empty = links_out[donor].index("")
        links_out[donor][empty] = df.at[o_idx, "Nom du fonds"]
        inbound[o_idx] += 1

    df[["Lien 1", "Lien 2", "Lien 3"]] = links_out
    return df

# ----------------------------------------------------------------------------
# Interface Streamlit --------------------------------------------------------
# ----------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="Maillage interne des fonds", layout="wide")
    st.title("🔗 Générateur de maillage interne – v4 (nom racine ▸ Type ▸ Random)")

    file = st.file_uploader("Fichier Excel (.xlsx)", type="xlsx")
    if not file:
        st.info("Déposez un fichier Excel pour commencer…")
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

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_out.to_excel(writer, index=False, sheet_name="Fonds")
    buffer.seek(0)

    st.download_button(
        "📥 Télécharger l’Excel enrichi",
        buffer,
        file_name="fonds_mailles.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

if __name__ == "__main__":
    main()
