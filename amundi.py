import pandas as pd

NB_LINKS = 3

def build_links(df):
    df = df.copy()
    inbound = {i: 0 for i in df.index}
    links   = [[] for _ in df.index]

    # 1) même Sous-type, trié alpha
    by_sous = df.groupby("Sous type").groups
    by_type = df.groupby("Type").groups

    for idx, row in df.iterrows():
        pool  = [j for j in by_sous[row["Sous type"]] if j != idx]
        pool += [j for j in by_type[row["Type"]] if j != idx and j not in pool]

        pool.sort(key=lambda j: df.at[j, "Nom du fonds"])
        picks = pool[:NB_LINKS]
        links[idx] = [df.at[j, "Nom du fonds"] for j in picks] + [""]*(NB_LINKS-len(picks))
        for j in picks:
            inbound[j] += 1

    # 2) ajoute un lien entrant aux éventuels orphelins
    orphans = [i for i, c in inbound.items() if c == 0]
    for o in orphans:
        giver = next(i for i,l in enumerate(links) if ("" in l) and df.at[i,"Sous type"]==df.at[o,"Sous type"])
        empty = links[giver].index("")
        links[giver][empty] = df.at[o,"Nom du fonds"]

    df[["Lien 1","Lien 2","Lien 3"]] = links
    df["Orphelin"] = (df[["Lien 1","Lien 2","Lien 3"]].apply(lambda r: df["Nom du fonds"].iloc[o in r.values],axis=1))
    return df
