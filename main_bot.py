import redis
from telegram import BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config import load_config
from bot import make_command_handlers

_COMMANDS = [
    BotCommand("help", "Show all commands"),
    BotCommand("list", "List saved prompts"),
    BotCommand("view", "View a prompt in full"),
    BotCommand("fire", "Queue one or more prompts"),
    BotCommand("run", "Queue an inline one-off prompt"),
    BotCommand("dryrun", "Preview a prompt without queuing"),
    BotCommand("schedule", "Schedule a prompt for a Brisbane local time"),
    BotCommand("save", "Save a new prompt"),
    BotCommand("delete", "Delete a saved prompt"),
    BotCommand("status", "Show running job and queue"),
    BotCommand("cancel", "Cancel the running job"),
    BotCommand("usage", "Token usage since last reset"),
    BotCommand("resettime", "Set the daily usage reset time"),
    BotCommand("log", "Last 5 completed jobs"),
]


async def _post_init(app: Application) -> None:
    await app.bot.set_my_commands(_COMMANDS)


def main():
    config = load_config()
    r = redis.from_url(config.redis_url, decode_responses=True)
    handlers = make_command_handlers(config, r)
    app = Application.builder().token(config.telegram_token).post_init(_post_init).build()
    for name, fn in handlers["commands"].items():
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(MessageHandler(filters.Document.ALL, handlers["document"]))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers["text"]))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
