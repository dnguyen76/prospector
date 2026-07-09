from dataclasses import dataclass


@dataclass(slots=True)
class Dirigeant:
    prenom: str = ""
    nom: str = ""
    qualite: str = ""

    @property
    def nom_complet(self) -> str:
        return f"{self.prenom} {self.nom}".strip()