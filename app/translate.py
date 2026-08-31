"""Best-effort Hebrew -> English translation for vehicle fields.

The upstream stub API returns manufacturer/model/color in Hebrew. Since the
underlying dataset is small and fixed (it's a stub), a maintained lookup
table is more reliable than calling out to a translation API: no extra
network dependency, no added latency, no cost, fully deterministic.

Unknown values fall back to being passed through untranslated (rather than
erroring) so the service never breaks on a value we haven't seen yet -- it
just won't be translated. Unknown values are logged so the map can be
extended.
"""
import logging

logger = logging.getLogger("vehicle_info_wrapper.translate")

# NOTE: placeholder starter set -- to be filled in / corrected with real
# values pulled from the live upstream API.
MANUFACTURER_HE_TO_EN = {
    "טויוטה": "Toyota",
    "יונדאי": "Hyundai",
    "קיה": "Kia",
    "מאזדה": "Mazda",
    "פורד": "Ford",
    "סקודה": "Skoda",
    "סוזוקי": "Suzuki",
    "מיצובישי": "Mitsubishi",
    "הונדה": "Honda",
    "ניסאן": "Nissan",
    "פולקסווגן": "Volkswagen",
    "רנו": "Renault",
    "פיג'ו": "Peugeot",
    "סיטרואן": "Citroen",
    "שברולט": "Chevrolet",
    "ב.מ.וו": "BMW",
    "מרצדס": "Mercedes-Benz",
    "אאודי": "Audi",
    "סובארו": "Subaru",
    "וולוו": "Volvo",
}

MODEL_HE_TO_EN = {
    "קורולה": "Corolla",
    "יאריס": "Yaris",
    "אאוריס": "Auris",
    "i10": "i10",
    "i20": "i20",
    "i35": "i35",
    "פיקנטו": "Picanto",
    "ספורטאז'": "Sportage",
    "פוקוס": "Focus",
    "פייסטה": "Fiesta",
    "אוקטביה": "Octavia",
    "גולף": "Golf",
    "פולו": "Polo",
    "סיוויק": "Civic",
    "קורוז'": "Corsa",
}

COLOR_HE_TO_EN = {
    "לבן": "White",
    "שחור": "Black",
    "כסוף": "Silver",
    "אפור": "Gray",
    "אדום": "Red",
    "כחול": "Blue",
    "ירוק": "Green",
    "צהוב": "Yellow",
    "כתום": "Orange",
    "חום": "Brown",
    "בז'": "Beige",
    "זהב": "Gold",
}


def _translate(value: str, table: dict[str, str], field_name: str) -> str:
    if value in table:
        return table[value]
    # Already English / not in our map -- pass through, but note it so the
    # map can be extended.
    if not any("֐" <= ch <= "׿" for ch in value):
        return value  # no Hebrew characters at all, nothing to translate
    logger.info("No translation found for %s value: %r", field_name, value)
    return value


def translate_manufacturer(value: str) -> str:
    return _translate(value, MANUFACTURER_HE_TO_EN, "manufacturer")


def translate_model(value: str) -> str:
    return _translate(value, MODEL_HE_TO_EN, "model")


def translate_color(value: str) -> str:
    return _translate(value, COLOR_HE_TO_EN, "color")
