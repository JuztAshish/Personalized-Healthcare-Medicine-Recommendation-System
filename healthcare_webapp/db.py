# Member 4 - Database connection (MongoDB)
from pymongo import MongoClient, ASCENDING, DESCENDING
from config import MONGO_URI, MONGO_DB_NAME

# Create a MongoDB client and select database/collection.
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = client[MONGO_DB_NAME]
users = db["users"]
activity_logs = db["activity_logs"]

# Ensure indexes (safe to call multiple times).
try:
    users.create_index([("email", ASCENDING)], unique=True)
    activity_logs.create_index([("timestamp", DESCENDING)])
    activity_logs.create_index([("email", ASCENDING), ("timestamp", DESCENDING)])
except Exception:
    # If MongoDB is not reachable at import/startup, routes will show error.
    pass


def ping_db():
    """Check MongoDB connection."""
    client.admin.command("ping")