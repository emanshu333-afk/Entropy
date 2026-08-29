# Generated to fix ProgrammingError: column bunkloop_user.identity_photo / email_verified missing
# This migration ensures the identity_photo and email_verified columns exist
# for databases that were created with an older 0001_initial without those fields.
# It is idempotent via IF NOT EXISTS / check, so it is safe on fresh databases
# where 0001_initial already creates those columns.

from django.db import migrations


def add_missing_columns(apps, schema_editor):
    # Use raw SQL with IF NOT EXISTS where supported, otherwise check information_schema
    db_engine = schema_editor.connection.vendor
    if db_engine == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='bunkloop_user' AND column_name='identity_photo'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE bunkloop_user ADD COLUMN identity_photo varchar(100)")
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='bunkloop_user' AND column_name='email_verified'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE bunkloop_user ADD COLUMN email_verified boolean DEFAULT false NOT NULL")
                cursor.execute("UPDATE bunkloop_user SET email_verified = false WHERE email_verified IS NULL")
    elif db_engine == "sqlite":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(bunkloop_user)")
            cols = [row[1] for row in cursor.fetchall()]
            if "identity_photo" not in cols:
                cursor.execute("ALTER TABLE bunkloop_user ADD COLUMN identity_photo varchar(100)")
            if "email_verified" not in cols:
                cursor.execute("ALTER TABLE bunkloop_user ADD COLUMN email_verified bool DEFAULT 0")
                cursor.execute("UPDATE bunkloop_user SET email_verified = 0 WHERE email_verified IS NULL")
    else:
        # Generic fallback - try to add, ignore if exists
        try:
            with schema_editor.connection.cursor() as cursor:
                cursor.execute("ALTER TABLE bunkloop_user ADD COLUMN identity_photo varchar(100)")
        except Exception:
            pass
        try:
            with schema_editor.connection.cursor() as cursor:
                cursor.execute("ALTER TABLE bunkloop_user ADD COLUMN email_verified boolean DEFAULT false")
        except Exception:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('bunkloop', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_missing_columns, migrations.RunPython.noop),
    ]
