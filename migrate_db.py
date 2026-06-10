"""Add any remaining missing columns to videos table."""
from app.database.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'videos' ORDER BY ordinal_position"
    ))
    vid_cols = [r[0] for r in result]
    print(f"Videos columns: {vid_cols}")

    missing = {
        "engine": "VARCHAR DEFAULT 'pexels'",
        "ai_video_prompt": "TEXT",
    }

    for col_name, col_type in missing.items():
        if col_name not in vid_cols:
            conn.execute(text(f"ALTER TABLE videos ADD COLUMN {col_name} {col_type}"))
            conn.commit()
            print(f"Added: videos.{col_name}")
        else:
            print(f"OK: videos.{col_name} exists")

    # Re-check
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'videos' ORDER BY ordinal_position"
    ))
    print(f"\nFinal Videos columns: {[r[0] for r in result]}")

print("Done!")
