"""
Streamlit app – Générateur de maillage interne v6
=================================================
> **Amélioration clé :** un nom racine « normalisé » beaucoup plus robuste
dans `root_name()` pour que les déclinaisons listées (ETF, DR, Acc, etc.)
se reconnaissent mutuellement et reçoivent **au moins un lien entrant et
sortant**.

### Niveaux de maillage
1. **Même nom racine** (après normalisation) – cyclique jusqu’à 3 liens.
2. Complément avec fonds du **même Type**.
3. Fallback aléatoire (rare).

### Normalisation du nom racine
* Coupe au premier `-` (tiret) **ou** au premier `(` parenthèse.
* Supprime les termes génériques : `UCITS`, `ETF`, `INDEX`, `DR`, `ACC`,
  `DIST`, `CAP`, `HEDGED`, codes court « A3E », « IE », etc.
* Réduit les espaces multiples → simple espace, passe en minuscules.

Ainsi :
> *« AMUNDI INDEX FTSE EPRA NAREIT GLOBAL  - AU (C) »*  ⇒  
> **amundi index ftse epra nareit global**

Toutes les variantes listées dans votre message partageront donc le même
nom racine et seront correctement maillées.

Dépendances (fichier *requirements.txt*)
---------------------------------------
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

NB_LINKS = 3     # Lien 1‑3
SOFT_CAP = 15    # apparition max avant débordement

# ---------------------------------------------------------------------------
# Normalisation du “nom racine” ---------------------------------------------
# ---------------------------------------------------------------------------

REMOVE_TERMS = {
    "ucits", "etf", "index", "dr", "acc", "dist", "cap", "hedged", "usd",
    "eur", "gbp", "mxn", "sgd", "class", "fund", "ie", "a3e", "a3u", "ae",
    "ihe", "ihc", "ihu", "iu", "me", "mu", "ahe", "mhe", "hedged", "exf"
}

RE_PAREN = re.compile(r"\(.*?\)")
RE_WHITESPACE = re.compile(r"\s+")

def root_name(name: str) -> str:
    """Normalise le nom pour grouper correctement les déclinaisons ETF.
    Étapes :
    1. Coupe au premier `-` ou `(`.
    2. Retire les parenthèses restantes.
    3. Supprime les termes génériques / codes share‑class.
    4. Nettoie les espaces, passe en minuscules.
    """
    # Coupe au premier - ou (
    base = re.split(r"[-(]", name, 1)[0]
    base = RE_PAREN.sub("", base)
    tokens = [t for t in RE_WHITESPACE.split(base) if t]
    tokens = [t for t in tokens if t.lower() not in REMOVE_TERMS]
    cleaned = " ".join(tokens)
    return cleaned.lower().strip()

# ---------------------------------------------------------------------------
# Maillage ------------------------------------------------------------------
# ---------------------------------------------------------------------------

def build_links(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    by_root: dict[str, list[int]] = {}
    by_type = df.groupby("Type").groups
    for idx, nom in enumerate(df["Nom du fonds"]):
        by_root.setdefault(root_name(nom), []).append(idx)

    all_idx = list(df.index)
    links_out = [[] for _ in df.index]
    inbound   = [0]*len(df)
    used_cnt  = [0]*len(df)

    # Maillage intra‑groupe cyclique
    for group in by_root.values():
        g = len(group)
        if g == 1:
            continue
        for k, idx in enumerate(group):
            picks = [group[(k+s) % g] for s in range(1, min(NB_LINKS, g))]
            for j in picks:
                if len(links_out[idx]) == NB_LINKS:
                    break
                links_out[idx].append(df.at[j, "Nom du fonds"])
                inbound[j] += 1
                used_cnt[j] += 1

    # Compléter si < NB_LINKS
    for idx, row in df.iterrows():
        if len(links_out[idx]) == NB_LINKS:
            continue
        ttype = row["Type"]
        existing = set(links_out[idx])

        # même Type
        pool = [j for j in by_type.get(ttype, []) if j != idx and df.at[j, "Nom du fonds"] not in existing]
        random.shuffle(pool)
        pool.sort(key=lambda j: used_cnt[j])
        for j in pool:
            if len(links_out[idx]) == NB_LINKS:
                break
            links_out[idx].append(df.at[j, "Nom du fonds"])
            inbound[j] += 1
            used_cnt[j] += 1
            existing.add(df.at[j, "Nom du fonds"])

        # aléatoire global si besoin
        if len(links_out[idx]) < NB_LINKS:
            remaining = [j for j in all_idx if j != idx and df.at[j, "Nom du fonds"] not in existing]
            random.shuffle(remaining)
            for j in remaining:
                if len(links_out[idx]) == NB_LINKS:
                    break
                links_out[idx].append(df.at[j, "Nom du fonds"])
                inbound[j] += 1
                used_cnt[j] += 1

        # padding éventuel
        links_out[idx] += [""] * (NB_LINKS - len(links_out[idx]))

    # Orphelins (aucun lien entrant) -> injection forcée
    for o, cnt in enumerate(inbound):
        if cnt:
            continue
        donor = next((i for i,l in enumerate(links_out) if "" in l and i != o), None)
        if donor is None:
            donor = (o+1) % len(df)
        slot = links_out[donor].index("") if "" in links_out[donor] else NB_LINKS-1
        links_out[donor][slot] = df.at[o, "Nom du fonds"]
        inbound[o] += 1

    df[["Lien 1", "Lien 2", "Lien 3"]] = links_out
    return df

# ---------------------------------------------------------------------------
# Streamlit UI ---------------------------------------------------------------
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="Maillage interne des fonds", layout="wide")
    st.title("🔗 Générateur de maillage interne – v6 (nom racine avancé)")

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
