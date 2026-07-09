from dataclasses import dataclass, field

from models.adresse import Adresse
from models.dirigeant import Dirigeant


@dataclass(slots=True)
class Entreprise:
    nom: str = ""
    siren: str = ""
    siret: str = ""
    activite: str = ""
    effectif: str = ""
    adresse: Adresse = field(default_factory=Adresse)
    dirigeant: Dirigeant = field(default_factory=Dirigeant)

    def to_csv_row(self) -> list[str]:
        return [
            self.nom,
            self.siren,
            self.siret,
            self.activite,
            self.adresse.complete,
            self.effectif,
            self.dirigeant.prenom,
            self.dirigeant.nom,
            self.dirigeant.qualite,
        ]