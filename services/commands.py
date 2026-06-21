from services.memory import PERSONA_SETTING_COMMAND, handle_persona_settings


def is_command(text: str) -> bool:
    return text.strip().startswith(PERSONA_SETTING_COMMAND)


def should_store_user_message(text: str) -> bool:
    return not is_command(text)


def handle_command(chat_id, text: str):
    stripped_text = text.strip()

    if stripped_text.startswith(PERSONA_SETTING_COMMAND):
        return handle_persona_settings(chat_id, stripped_text)

    return None
