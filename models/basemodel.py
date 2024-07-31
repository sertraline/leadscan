import abc
import asyncpg
import traceback


class BaseModel:

    async def create(self):
        try:
            await self._init_table()
        except asyncpg.exceptions.DuplicateTableError:
            pass
        except Exception:
            print(traceback.format_exc())

    @abc.abstractmethod  # pyright: ignore[reportAssignmentType]
    async def _init_table(self):
        """Table initialization"""
        return
