import csv

from models.entreprise import Entreprise


class ExportService:
    @staticmethod
    def exporter_csv(fichier: str, entreprises: list[Entreprise]) -> None:
        with open(fichier, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")

            writer.writerow([
                "Nom",
                "SIREN",
                "SIRET",
                "Activité (Libellé)",
                "Adresse",
                "Tranche Effectif",
                "Dirigeant Prénom",
                "Dirigeant Nom",
                "Dirigeant Qualité",
            ])

            for entreprise in entreprises:
                writer.writerow(entreprise.to_csv_row())