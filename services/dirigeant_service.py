from utils.constants import ORDRE_PRIORITE_QUALITES


def extraire_dirigeant_principal(ent: dict) -> tuple[str, str, str]:
    dirigeants = ent.get("dirigeants") or []
    candidats = [
        d for d in dirigeants
        if d.get("type_dirigeant") == "personne physique"
    ]

    if not candidats:
        return "", "", ""

    def rang_priorite(d: dict) -> int:
        qualite = (d.get("qualite") or "").lower()

        if "commissaire" in qualite or "surveillance" in qualite:
            return len(ORDRE_PRIORITE_QUALITES) + 1

        for i, mot_cle in enumerate(ORDRE_PRIORITE_QUALITES):
            if mot_cle in qualite:
                return i

        return len(ORDRE_PRIORITE_QUALITES)

    candidats.sort(key=rang_priorite)
    meilleur = candidats[0]

    prenoms = (meilleur.get("prenoms") or "").strip()
    prenom = prenoms.split()[0].title() if prenoms else ""

    nom_brut = (meilleur.get("nom") or "").strip()
    nom = nom_brut.split("(")[0].strip().title()

    qualite = (meilleur.get("qualite") or "").strip()

    return prenom, nom, qualite