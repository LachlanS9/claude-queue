import redis
import asyncio
from telegram import Bot
from config import load_config
from worker import run_worker


def main():
    config = load_config()
    r = redis.from_url(config.redis_url, decode_responses=True)
    bot = Bot(token=config.telegram_token)

    def send_telegram(msg: str) -> None:
        for user_id in config.allowed_user_ids:
            asyncio.run(bot.send_message(chat_id=user_id, text=msg))

    run_worker(config, send_telegram, r)


if __name__ == "__main__":
    main()
