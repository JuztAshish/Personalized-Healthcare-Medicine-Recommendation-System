# Member 4 - One-time admin seed script
# Creates/updates the 4 approved admin accounts in MongoDB.
# Run: python seed_admins.py (prompts for passwords via getpass, no passwords stored in code)

import getpass
from werkzeug.security import generate_password_hash
from db import users, ping_db

ADMINS = [
    {"name": "Ashish Kumar Prajapati", "email": "ashish280971@gmail.com"},
    {"name": "Somil Sahu", "email": "somilsahu086@gmail.com"},
    {"name": "Maria Varsha", "email": "nilaevara@gmail.com"},
    {"name": "Harshvardhan", "email": "hv1214293@gmail.com"},
]


def main():
    try:
        ping_db()
        print("MongoDB connection: OK")
    except Exception as e:
        print("MongoDB connection failed:", e)
        return

    for admin in ADMINS:
        pw = getpass.getpass(f"Set password for {admin['name']} ({admin['email']}): ")
        if not pw:
            print("Skipped (empty password):", admin["email"])
            continue
        users.update_one(
            {"email": admin["email"].lower()},
            {"$set": {
                "name": admin["name"],
                "email": admin["email"].lower(),
                "password_hash": generate_password_hash(pw),
                "role": "admin",
            }},
            upsert=True,
        )
        print("Upserted admin:", admin["email"])

    print("Done. Admin accounts are ready.")


if __name__ == "__main__":
    main()