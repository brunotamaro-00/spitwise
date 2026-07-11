from dataclasses import dataclass, field


@dataclass
class BotReply:
    text: str | None = None
    buttons: list[tuple[str, str]] = field(default_factory=list)
    movement_id: int | None = None  # seteado por la captura al crear un movimiento


def text_reply(s: str) -> BotReply:
    return BotReply(text=s)


def buttons_reply(s: str, buttons: list[tuple[str, str]]) -> BotReply:
    return BotReply(text=s, buttons=buttons)
