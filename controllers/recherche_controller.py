from models.commune import Commune
from models.entreprise import Entreprise
from services.entreprise_service import EntrepriseService
from services.export_service import ExportService
from services.geo_service import GeoService


class RechercheController:
    def __init__(self):
        self.geo_service = GeoService()
        self.entreprise_service = EntrepriseService()
        self.export_service = ExportService()
        self.resultats: list[Entreprise] = []

    def suggestions_communes(self, texte: str) -> list[str]:
        return self.geo_service.suggestions_communes(texte)

    def calculer_communes_rayon(self, saisie: str, choix_rayon: str) -> list[Commune]:
        return self.geo_service.calculer_communes_rayon(saisie, choix_rayon)

    def rechercher_entreprises(
        self,
        communes: list[Commune],
        code_naf_selectionne: str,
        code_tranche_max: str,
        message_callback=None,
    ) -> list[Entreprise]:
        codes_insee = [commune.code for commune in communes]

        self.resultats = self.entreprise_service.rechercher(
            codes_insee=codes_insee,
            code_naf_selectionne=code_naf_selectionne,
            code_tranche_max=code_tranche_max,
            message_callback=message_callback,
        )

        return self.resultats

    def exporter_csv(self, fichier: str) -> None:
        self.export_service.exporter_csv(fichier, self.resultats)