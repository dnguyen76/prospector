from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt

from models.entreprise import Entreprise


class EntrepriseTableModel(QAbstractTableModel):
    HEADERS = [
        "Nom",
        "SIREN",
        "SIRET",
        "Activité",
        "Effectif",
        "Adresse",
        "Dirigeant",
        "Qualité",
    ]

    def __init__(self, entreprises: list[Entreprise] | None = None):
        super().__init__()
        self.entreprises = entreprises or []

    def set_entreprises(self, entreprises: list[Entreprise]):
        self.beginResetModel()
        self.entreprises = entreprises
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.entreprises)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role):
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]

        return section + 1

    def data(self, index, role):
        if not index.isValid():
            return None

        entreprise = self.entreprises[index.row()]

        values = [
            entreprise.nom,
            entreprise.siren,
            entreprise.siret,
            entreprise.activite,
            entreprise.effectif,
            entreprise.adresse.complete,
            entreprise.dirigeant.nom_complet,
            entreprise.dirigeant.qualite,
        ]

        if role == Qt.ItemDataRole.DisplayRole:
            return values[index.column()]

        return None

    def sort(self, column, order):
        reverse = order == Qt.SortOrder.DescendingOrder

        def key_func(e: Entreprise):
            return [
                e.nom,
                e.siren,
                e.siret,
                e.activite,
                e.effectif,
                e.adresse.complete,
                e.dirigeant.nom_complet,
                e.dirigeant.qualite,
            ][column]

        self.layoutAboutToBeChanged.emit()
        self.entreprises.sort(key=key_func, reverse=reverse)
        self.layoutChanged.emit()