from aiogram.types import Message

async def echo(message: Message):
    await message.answer(message.text if message.text else "")
