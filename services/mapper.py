from models.adresse import Adresse
from models.dirigeant import Dirigeant
from models.entreprise import Entreprise


class EntrepriseMapper:
    @staticmethod
    def depuis_api(
        ent: dict,
        etablissement: dict,
        dirigeant_prenom: str,
        dirigeant_nom: str,
        dirigeant_qualite: str,
        libelle_activite: str,
        libelle_effectif: str,
    ) -> Entreprise:
        adresse_ligne = etablissement.get("adresse") or (
            f"{etablissement.get('code_postal', '')} "
            f"{etablissement.get('libelle_commune', '')}"
        ).strip()

        return Entreprise(
            nom=ent.get("nom_complet", ""),
            siren=ent.get("siren", ""),
            siret=etablissement.get("siret", ""),
            activite=libelle_activite,
            effectif=libelle_effectif,
            adresse=Adresse(
                ligne=adresse_ligne,
                code_postal=etablissement.get("code_postal", ""),
                commune=etablissement.get("libelle_commune", ""),
            ),
            dirigeant=Dirigeant(
                prenom=dirigeant_prenom,
                nom=dirigeant_nom,
                qualite=dirigeant_qualite,
            ),
        )