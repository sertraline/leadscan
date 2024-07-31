from aiogram.types import ChatMemberUpdated
from aiogram import Router, Bot
from logging import Logger
from models.users import UserManager
from aiogram.enums import ChatMemberStatus


class MemberWatch:
    router = Router()

    def __init__(
        self,
        log: Logger,
        bot: Bot,
        user_manager: UserManager,
        **kw,
    ):
        self.log = log
        self.bot = bot
        self.um = user_manager

        self.router.my_chat_member.register(
            self.check_group
        )

    async def check_group(self, event: ChatMemberUpdated):
        new_chat_member = event.new_chat_member

        if new_chat_member.status == ChatMemberStatus.MEMBER:
            if new_chat_member.user.is_bot:
                u = new_chat_member.user
                me = await self.bot.get_me()
                if me.id == u.id:
                    await self.bot.leave_chat(event.chat.id)
