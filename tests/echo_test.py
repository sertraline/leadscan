import pytest

from unittest.mock import AsyncMock
from plugins.echo import echo


@pytest.mark.asyncio
async def test_echo_handler():
    text_mock = "test123"
    message_mock = AsyncMock(text=text_mock)
    await echo(message=message_mock)
    print(message_mock.answer)
    message_mock.answer.assert_called_with(text_mock)
