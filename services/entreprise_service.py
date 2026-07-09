import time
from collections.abc import Callable

import requests

from services.dirigeant_service import extraire_dirigeant_principal
from services.mapper import EntrepriseMapper
from utils.constants import LISTE_NAF_SELECTION, TRANCHES_EFFECTIFS


class EntrepriseService:
    API_URL = "https://recherche-entreprises.api.gouv.fr/search"
    PER_PAGE = 25
    MAX_PAGES_PAR_COMMUNE = 40

    def rechercher(
        self,
        codes_insee: list[str],
        code_naf_selectionne: str,
        code_tranche_max: str,
        message_callback: Callable[[str], None] | None = None,
    ):
        resultats = []

        valeur_tri_max = TRANCHES_EFFECTIFS[code_tranche_max][0]

        code_formate = None
        if code_naf_selectionne != "TOUS":
            if len(code_naf_selectionne) == 5 and code_naf_selectionne[2] != ".":
                code_formate = f"{code_naf_selectionne[:2]}.{code_naf_selectionne[2:]}"
            else:
                code_formate = code_naf_selectionne

        for idx, code_insee in enumerate(codes_insee, 1):
            page = 1
            total_pages = 1

            while page <= total_pages and page <= self.MAX_PAGES_PAR_COMMUNE:
                if message_callback:
                    suffixe_page = f" (page {page}/{total_pages})" if total_pages > 1 else ""
                    message_callback(
                        f"Commune {idx}/{len(codes_insee)} — INSEE {code_insee}{suffixe_page}..."
                    )

                params = {
                    "per_page": self.PER_PAGE,
                    "page": page,
                    "code_commune": code_insee,
                }

                if code_formate:
                    params["activite_principale"] = code_formate

                response = requests.get(self.API_URL, params=params, timeout=10)

                if response.status_code == 429:
                    attente = float(response.headers.get("Retry-After", 2))
                    if message_callback:
                        message_callback(
                            f"   Limite de débit de l'API atteinte, pause de {attente:.0f}s..."
                        )
                    time.sleep(attente)
                    continue

                if response.status_code != 200:
                    if message_callback:
                        message_callback(
                            f"   Erreur API ({response.status_code}) sur cette page — commune ignorée pour la suite."
                        )
                    break

                data = response.json()
                total_pages = data.get("total_pages") or 1
                resultats_bruts = data.get("results", [])

                for ent in resultats_bruts:
                    etablissements_candidats = ent.get("matching_etablissements") or []

                    if not etablissements_candidats:
                        etablissements_candidats = [ent.get("siege", {})]

                    if code_naf_selectionne != "TOUS":
                        filtres = [
                            e
                            for e in etablissements_candidats
                            if (e.get("activite_principale") or "").replace(".", "")
                            == code_naf_selectionne
                        ]

                        if filtres:
                            etablissements_candidats = filtres

                    tranche_ent = ent.get("tranche_effectif_salarie", "00")

                    if not tranche_ent or tranche_ent == "NN":
                        tranche_ent = "00"

                    valeur_tri_ent = TRANCHES_EFFECTIFS.get(tranche_ent, (0, ""))[0]

                    if code_tranche_max != "TOUS" and valeur_tri_ent > valeur_tri_max:
                        continue

                    dirigeant_prenom, dirigeant_nom, dirigeant_qualite = (
                        extraire_dirigeant_principal(ent)
                    )

                    for etab in etablissements_candidats:
                        siret_cible = etab.get("siret", "")

                        if not siret_cible:
                            continue

                        raw_naf = (
                            etab.get("activite_principale")
                            or ent.get("activite_principale", "")
                        ).replace(".", "")

                        libelle_activite = LISTE_NAF_SELECTION.get(
                            raw_naf,
                            ent.get("libelle_activite_principale", "Inconnue"),
                        )

                        libelle_effectif = TRANCHES_EFFECTIFS.get(
                            tranche_ent,
                            (0, "Inconnu"),
                        )[1]

                        entreprise = EntrepriseMapper.depuis_api(
                            ent=ent,
                            etablissement=etab,
                            dirigeant_prenom=dirigeant_prenom,
                            dirigeant_nom=dirigeant_nom,
                            dirigeant_qualite=dirigeant_qualite,
                            libelle_activite=libelle_activite,
                            libelle_effectif=libelle_effectif,
                        )

                        if entreprise.siret not in [e.siret for e in resultats]:
                            resultats.append(entreprise)

                page += 1
                time.sleep(0.15)

        return resultats