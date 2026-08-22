"""Migración: agrega columnas faltantes a products y videos."""
from app.database.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # ── Products ──────────────────────────────────────────────────────────────
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'products' ORDER BY ordinal_position"
    ))
    prod_cols = [r[0] for r in result]
    print(f"Products columns: {prod_cols}")

    prod_missing = {
        "affiliate_url": "VARCHAR",
    }

    for col_name, col_type in prod_missing.items():
        if col_name not in prod_cols:
            conn.execute(text(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}"))
            conn.commit()
            print(f"Added: products.{col_name}")
        else:
            print(f"OK: products.{col_name} exists")

    # ── Videos ────────────────────────────────────────────────────────────────
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'videos' ORDER BY ordinal_position"
    ))
    vid_cols = [r[0] for r in result]
    print(f"\nVideos columns: {vid_cols}")

    vid_missing = {
        "engine": "VARCHAR DEFAULT 'ai'",
        "language": "VARCHAR",
        "ai_video_prompt": "TEXT",
        "base_video_path": "TEXT",
    }

    for col_name, col_type in vid_missing.items():
        if col_name not in vid_cols:
            conn.execute(text(f"ALTER TABLE videos ADD COLUMN {col_name} {col_type}"))
            conn.commit()
            print(f"Added: videos.{col_name}")
        else:
            print(f"OK: videos.{col_name} exists")

    # ── Verificación Final ────────────────────────────────────────────────────
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'products' ORDER BY ordinal_position"
    ))
    print(f"\nFinal Products columns: {[r[0] for r in result]}")

    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'videos' ORDER BY ordinal_position"
    ))
    print(f"Final Videos columns: {[r[0] for r in result]}")

print("\nDone!")
