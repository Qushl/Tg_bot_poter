from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    database_url: str
    proxy_url: str | None


def load_config() -> Config:
    load_dotenv()
    values = {
        "BOT_TOKEN": os.getenv("BOT_TOKEN"),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"Не заданы переменные окружения: {', '.join(missing)}")
    return Config(
        bot_token=values["BOT_TOKEN"],  # type: ignore[arg-type]
        database_url="sqlite+aiosqlite:///lost_found.db",
        proxy_url=os.getenv("PROXY_URL") or None,
    )
