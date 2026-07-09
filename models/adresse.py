from dataclasses import dataclass


@dataclass(slots=True)
class Adresse:
    ligne: str = ""
    code_postal: str = ""
    commune: str = ""

    @property
    def complete(self) -> str:
        return self.ligne or f"{self.code_postal} {self.commune}".strip()