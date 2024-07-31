from .register_user import Register
from .notes import Notes


def init_plugins(payload):
    pl = [
        # Порядок регистрации плагинов имеет значение
        Register,
        Notes
    ]
    for i, plugin in enumerate(pl):
        pl[i] = plugin(**payload) # type: ignore
    return pl
