import math
import requests

from models.commune import Commune


class GeoService:
    API_BASE = "https://geo.api.gouv.fr"

    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def suggestions_communes(self, texte: str) -> list[str]:
        texte = texte.strip()

        if len(texte) < 2:
            return []

        if " (" in texte:
            return []

        url = f"{self.API_BASE}/communes"

        res = requests.get(
            url,
            params={
                "nom": texte,
                "fields": "nom,codesPostaux",
                "limit": 10,
            },
            timeout=2,
        )

        if res.status_code != 200:
            return []

        suggestions = []

        for item in res.json():
            nom = item.get("nom", "")
            cp = item.get("codesPostaux", [""])[0] if item.get("codesPostaux") else ""
            suggestions.append(f"{nom} ({cp})")

        return suggestions

    def calculer_communes_rayon(self, saisie: str, choix_rayon: str) -> list[Commune]:
        saisie = saisie.strip()

        if not saisie:
            raise ValueError("Veuillez saisir un nom de commune.")

        if " (" in saisie:
            nom_saisi = saisie.split(" (")[0]
        else:
            nom_saisi = saisie

        url_base = f"{self.API_BASE}/communes"

        res = requests.get(
            url_base,
            params={
                "nom": nom_saisi,
                "fields": "code,nom,centre,codesPostaux,codeDepartement",
                "exact": True,
            },
            headers=self.headers,
            timeout=self.timeout,
        )

        if res.status_code != 200 or not res.json():
            res = requests.get(
                url_base,
                params={
                    "nom": nom_saisi,
                    "fields": "code,nom,centre,codesPostaux,codeDepartement",
                },
                headers=self.headers,
                timeout=self.timeout,
            )

        if res.status_code != 200 or not res.json():
            raise ValueError("Commune introuvable.")

        commune_centre_data = res.json()[0]
        code_insee_centre = commune_centre_data["code"]
        nom_officiel_centre = commune_centre_data["nom"]
        code_dept = commune_centre_data.get("codeDepartement", "")

        if "centre" not in commune_centre_data or "coordinates" not in commune_centre_data["centre"]:
            raise ValueError("Impossible de récupérer les coordonnées GPS du centre.")

        lon, lat = commune_centre_data["centre"]["coordinates"]
        cp_centre = commune_centre_data["codesPostaux"][0] if commune_centre_data.get("codesPostaux") else ""

        communes_trouvees: list[Commune] = []

        if choix_rayon.startswith("0 km"):
            communes_trouvees = [
                Commune(
                    code=code_insee_centre,
                    nom=nom_officiel_centre,
                    cp=cp_centre,
                )
            ]
        else:
            rayon_km = int(choix_rayon.split(" ")[0])

            if code_dept:
                url_dept = f"{self.API_BASE}/departements/{code_dept}/communes"

                res_dept = requests.get(
                    url_dept,
                    params={"fields": "code,nom,codesPostaux,centre"},
                    headers=self.headers,
                    timeout=self.timeout,
                )

                if res_dept.status_code == 200:
                    for c in res_dept.json():
                        if "centre" in c and "coordinates" in c["centre"]:
                            c_lon, c_lat = c["centre"]["coordinates"]

                            dist_lat = (c_lat - lat) * 111
                            dist_lon = (c_lon - lon) * 111 * math.cos(math.radians(lat))
                            distance_approx = math.sqrt(dist_lat**2 + dist_lon**2)

                            if distance_approx <= rayon_km:
                                cp = c["codesPostaux"][0] if c.get("codesPostaux") else "N/A"
                                communes_trouvees.append(
                                    Commune(
                                        code=c["code"],
                                        nom=c["nom"],
                                        cp=cp,
                                    )
                                )

        if not any(c.code == code_insee_centre for c in communes_trouvees):
            communes_trouvees.append(
                Commune(
                    code=code_insee_centre,
                    nom=nom_officiel_centre,
                    cp=cp_centre,
                )
            )

        communes_trouvees = sorted(communes_trouvees, key=lambda x: x.nom)

        return communes_trouvees