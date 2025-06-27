"""
Streamlit app – Générateur de maillage interne v5
=================================================
### Règles de maillage
1. **Maillage intra‑groupe (nom racine)** :
   * Tous les fonds partageant le même *nom racine* (avant « - ») se lient
     entre eux.  
   * Chaque fonds pointe vers jusqu’à **3** autres partages classes du même
     groupe ; rotation cyclique ⇒ tout le monde reçoit **≥ 1 lien entrant**.
2. **Fallback** : si le groupe ne comporte qu’un seul fonds, on complète avec
   des fonds du **même Type**, puis aléatoirement si besoin.
3. Export natif **Excel .xlsx**.

### Tableur requis (ligne 1 = en‑têtes, données dès A2)
| Colonne | Intitulé |
|---------|----------|
| A       | Nom du fonds |
| B       | Code ISIN |
| C       | Type |
| E       | Sous type |

### Dépendances
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

import pandas as pd
import streamlit as st

NB_LINKS = 3  # nombre maximum de liens sortants par fonds

# ---------------------------------------------------------------------------
# Helpers -------------------------------------------------------------------
# ---------------------------------------------------------------------------

def root_name(name: str) -> str:
    """Partie avant le premier " - " (normalisée)."""
    return re.split(r"\s*-", name, 1)[0].strip().lower()

# ---------------------------------------------------------------------------
# Core ----------------------------------------------------------------------
# ---------------------------------------------------------------------------

def build_links(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Groupes par nom racine et par Type
    by_root: dict[str, list[int]] = {}
    by_type = df.groupby("Type").groups
    for idx, nom in enumerate(df["Nom du fonds"]):
        by_root.setdefault(root_name(nom), []).append(idx)

    all_idx = list(df.index)
    links_out: list[list[str]] = [[] for _ in df.index]
    inbound = [0] * len(df)

    # 1) Maillage intra‑groupe ------------------------------------------------
    for group in by_root.values():
        g = len(group)
        if g == 1:
            continue  # on gérera le fallback plus bas
        for k, idx in enumerate(group):
            # sélection cyclique des suivants dans le groupe
            picks_idx = [group[(k + s) % g] for s in range(1, min(NB_LINKS, g - 1) + 1)]
            links_out[idx] = [df.at[j, "Nom du fonds"] for j in picks_idx]
            for j in picks_idx:
                inbound[j] += 1

    # 2) Fallback pour groupes isolés ou slots vides -------------------------
    for idx, row in df.iterrows():
        if len(links_out[idx]) == NB_LINKS:
            continue  # déjà rempli au max

        ttype = row["Type"]
        existing = set(links_out[idx])

        # a) même Type
        pool = [j for j in by_type.get(ttype, []) if j != idx and df.at[j, "Nom du fonds"] not in existing]
        random.shuffle(pool)
        for j in pool:
            if len(links_out[idx]) == NB_LINKS:
                break
            links_out[idx].append(df.at[j, "Nom du fonds"])
            inbound[j] += 1
            existing.add(df.at[j, "Nom du fonds"])

        # b) aléatoire global si besoin
        if len(links_out[idx]) < NB_LINKS:
            remaining = [j for j in all_idx if j != idx and df.at[j, "Nom du fonds"] not in existing]
            random.shuffle(remaining)
            for j in remaining:
                if len(links_out[idx]) == NB_LINKS:
                    break
                links_out[idx].append(df.at[j, "Nom du fonds"])
                inbound[j] += 1

        # pad éventuel
        while len(links_out[idx]) < NB_LINKS:
            links_out[idx].append("")

    # Vérif : tout fonds possède ≥ 1 lien entrant. Si certains restent à 0, on les ajoute aléatoirement.
    orphans = [i for i, cnt in enumerate(inbound) if cnt == 0]
    if orphans:
        for o in orphans:
            donor = next((i for i, l in enumerate(links_out) if "" in l and i != o), None)
            if donor is None:
                donor = (o + 1) % len(df)
            slot = links_out[donor].index("") if "" in links_out[donor] else NB_LINKS - 1
            links_out[donor][slot] = df.at[o, "Nom du fonds"]
            inbound[o] += 1

    df[["Lien 1", "Lien 2", "Lien 3"]] = links_out
    return df

# ---------------------------------------------------------------------------
# Streamlit UI ---------------------------------------------------------------
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="Maillage interne des fonds", layout="wide")
    st.title("🔗 Générateur de maillage interne – v5 (groupe racine → Type → Random)")

    file = st.file_uploader("Fichier Excel (.xlsx)", type="xlsx")
    if not file:
        st.info("Déposez votre fichier Excel pour commencer…")
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
