from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    db.drop_all()
    db.create_all()

    try:
        from app.seed import seed_if_empty
        seed_if_empty()
        print("Database recreated and seeded successfully.")
    except Exception as e:
        print("Database recreated, but seed failed:", e)