from abc import ABC, abstractmethod
from os import environ
from databases import Database
from logging import getLogger, DEBUG

class QueryDumper(Database):
    """ A primitive database wrapper that logs all queries and responses."""
    def __init__(self, *args, **wqargs):
        super().__init__(*args, **wqargs)
        self.logger = getLogger("Database")
        self.logger.setLevel(DEBUG)

    async def execute(self, *args, **kwargs):
        ret = await super().execute(*args, **kwargs)
        self.logger.debug(f"execute({args}, {kwargs}) -> {ret}")
        return ret
    
    async def fetch_all(self, *args, **kwargs):
        ret = await super().fetch_all(*args, **kwargs)
        self.logger.debug(f"fetch_all({args}, {kwargs}) -> {ret}")
        return ret
    
    async def fetch_one(self, *args, **kwargs):
        ret = await super().fetch_one(*args, **kwargs)
        self.logger.debug(f"fetch_one({args}, {kwargs}) -> {ret}")
        return ret

class DatabaseManager:
    def __init__(self, url=None, owner_id=None, record=False):
        self.logger = getLogger("DatabaseManager")
        if record or environ.get("RECORD_QUERIES"):
            self.logger.info("Recording queries")
            self.db = QueryDumper(url or environ['DB_URL'])
        else:
            self.db = Database(url or environ['DB_URL'])
        self.owner_id = int(owner_id or environ['OWNER_ID'])
        self.entry = None
        self.transaction = None
        

    async def connect(self):
        await self.db.connect()
        self.transaction = await self.db.transaction()
        return await self.get_entry()

    async def commit(self):
        await self.transaction.commit()

    async def get_entry(self):
        return await self.db.execute("INSERT INTO entry (owner) values (:owner) returning id", {"owner": self.owner_id})

    async def view(self, name):
        rows = await self.db.fetch_all(
            "SELECT version FROM versions WHERE component = :name AND supported=TRUE",
            {"name": f"views:{name}"}
        )
        return [row["version"] for row in rows]
    
    async def procedure(self, name):
        rows = await self.db.fetch_all(
            "SELECT version FROM versions WHERE component = :name AND supported=TRUE",
            {"name": f"procs:{name}"}
        )
        return [row["version"] for row in rows]
    
    async def best_view(self, name):
        versions = await self.view(name)
        return max(versions) if versions else None
    
    async def best_procedure(self, name):
        versions = await self.procedure(name)
        return max(versions) if versions else None
