from dataclasses import dataclass


@dataclass(slots=True)
class Commune:
    code: str
    nom: str
    cp: str

    def label(self) -> str:
        return f"{self.nom} ({self.cp})"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "nom": self.nom,
            "cp": self.cp,
        }