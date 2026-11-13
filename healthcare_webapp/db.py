# Member 4 - Database connection (MongoDB)
from pymongo import MongoClient, ASCENDING
from config import MONGO_URI, MONGO_DB_NAME

# Create a MongoDB client and select database/collection.
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = client[MONGO_DB_NAME]
users = db["users"]

# Ensure email is unique (safe to call multiple times).
try:
    users.create_index([("email", ASCENDING)], unique=True)
except Exception:
    # If MongoDB is not reachable at import/startup, routes will show error.
    pass


def ping_db():
    """Check MongoDB connection."""
    client.admin.command("ping")