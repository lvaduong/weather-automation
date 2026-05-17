from dataclasses import dataclass


@dataclass(frozen=True)
class CityTarget:
    name: str
    country: str
    location_url: str

    @property
    def display_name(self) -> str:
        return f"{self.name}, {self.country}".strip(", ")

    @property
    def slug(self) -> str:
        value = f"{self.name}-{self.country}".lower()
        return "".join(character if character.isalnum() else "-" for character in value).strip("-")
