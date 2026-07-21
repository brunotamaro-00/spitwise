"""Espejo del enum DocumentKind de Andiamo (prisma/schema.prisma).

Si acá llega un kind que Andiamo no conoce, su endpoint lo degrada a 'other',
así que un desync nunca rompe — solo clasifica peor. Al sumar un kind en
Andiamo, agregarlo acá con su etiqueta UI.
"""

DOC_KINDS: dict[str, str] = {
    "checkin": "Check-in",
    "voucher": "Voucher",
    "ticket": "Entrada",
    "carRental": "Auto",
    "train": "Tren",
    "insurance": "Seguro",
    "flight": "Vuelo",
    "other": "Otro",
}

DOC_KIND_EMOJI: dict[str, str] = {
    "checkin": "🏨",
    "voucher": "🎟️",
    "ticket": "🎟️",
    "carRental": "🚗",
    "train": "🚆",
    "insurance": "🛡️",
    "flight": "✈️",
    "other": "📄",
}


def normalize_kind(kind: str | None) -> str:
    return kind if kind in DOC_KINDS else "other"


def kind_label(kind: str | None) -> str:
    k = normalize_kind(kind)
    return f"{DOC_KIND_EMOJI[k]} {DOC_KINDS[k]}"
