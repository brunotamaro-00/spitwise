"""El prompt le tiene que llegar armado al modelo.

No valida cómo interpreta el LLM (eso solo se ve con el modelo real): valida
que las paradas y las reglas de split lleguen al texto, que es lo que faltaba
cuando el bot no reconoció "Pititas" y leyó "solo Katia" como "pagó Katia".
"""
from datetime import date

from app.llm.client import _render_system, _render_user

CATS = ["Comida", "Otros"]
USERS = ["bruno", "katia"]
TODAY = date(2026, 9, 6)
CITIES = ["París", "Portugal", "Pititas", "Estrasburgo"]


def _user_prompt(text="10 usd pititas en coca cola", cities=CITIES, sender="bruno"):
    return _render_user(text, TODAY, CATS, USERS, sender, None, cities)


def test_las_paradas_van_en_el_prompt():
    """Sin esto el LLM solo reconoce ciudades por cultura general: 'Pititas' es
    un nombre inventado y lo mandaba a la descripción."""
    p = _user_prompt()
    assert "Pititas" in p
    assert "Portugal" in p and "Estrasburgo" in p


def test_sin_paradas_no_se_rompe_el_prompt():
    """Snapshot vacío (Andiamo caído en el arranque): el bloque desaparece."""
    p = _user_prompt(cities=[])
    assert "Paradas del itinerario" not in p
    assert "Mensaje: " in p  # el resto sigue intacto


def test_la_regla_de_split_nombra_a_los_dos_usuarios():
    """'solo katia'/'solo bruno' tienen que estar por nombre: los ejemplos
    genéricos ('solo de ella') no matcheaban un nombre pelado."""
    s = _render_system(USERS, "bruno")
    assert "solo katia" in s.lower()
    assert "solo bruno" in s.lower()


def test_el_prompt_aclara_que_solo_nombre_no_es_quien_pago():
    """El bug real: 'solo Katia' se leyó como paid_by=katia y encima invirtió
    el split, dejando a Bruno debiendo la plata."""
    s = _render_system(USERS, "bruno").lower()
    assert "de quién es el gasto" in s or "de quién es" in s
    assert "no significa que pagó katia" in s
    # paid_by tiene que quedar explícitamente en null ante 'solo <nombre>'.
    assert "no dice quién pagó" in s


def test_el_split_sigue_siendo_relativo_a_quien_pago():
    s = _render_system(USERS, "bruno").lower()
    assert "relativo a quien pagó" in s
    assert "payer_only" in s and "other_only" in s
