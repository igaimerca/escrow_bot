"""
TrustHold_EscrowBot - Main Entry Point
"""
import asyncio
import logging
from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.types import CallbackQuery, Message, Update
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers import common, deals, payments, disputes, admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class UpdateLoggerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data):
        state = data.get("state")
        current_state = None
        if state is not None:
            try:
                current_state = await state.get_state()
            except Exception:
                current_state = "<state lookup failed>"

        if event.message:
            message: Message = event.message
            logger.info(
                "Update log: type=message user=%s chat=%s state=%s content_type=%s text=%r caption=%r photo=%s document=%s",
                message.from_user.id if message.from_user else None,
                message.chat.id if message.chat else None,
                current_state,
                message.content_type,
                message.text,
                message.caption,
                bool(message.photo),
                bool(message.document),
            )
        elif event.callback_query:
            callback_query: CallbackQuery = event.callback_query
            logger.info(
                "Update log: type=callback_query user=%s chat=%s state=%s data=%r",
                callback_query.from_user.id if callback_query.from_user else None,
                callback_query.message.chat.id if callback_query.message and callback_query.message.chat else None,
                current_state,
                callback_query.data,
            )
        else:
            logger.info("Update log: type=%s state=%s", event.event_type, current_state)

        return await handler(event, data)


async def main():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.update.outer_middleware(UpdateLoggerMiddleware())

    # Register routers
    dp.include_router(common.router)
    dp.include_router(deals.router)
    dp.include_router(payments.router)
    dp.include_router(disputes.router)
    dp.include_router(admin.router)

    logger.info("TrustHold_EscrowBot is starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
