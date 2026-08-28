# Changelog

## 2026-08-29

### Added

- Initialized the Django project named `entropy`.
- Added the `bunkloop` app for the custom user model.
- Added BunkLoop branding to the Django admin site.
- Added a custom `User` model based on Django's `AbstractUser`.
- Registered the custom user model in the Django admin.
- Configured PostgreSQL database settings using the `DB_*` environment variables.
- Added dotenv support for loading environment variables from `.env`.
- Added `.env.example` with the required configuration keys.
- Added project-level `templates`, `static`, `assets`, and `media` directories.
- Configured `STATIC_ROOT`, `STATICFILES_DIRS`, `MEDIA_ROOT`, and `MEDIA_URL`.
- Added PostgreSQL and dotenv dependencies to `requirements.txt`.
- Added `.gitignore` entries for secrets, virtual environments, generated files, and uploaded media.

### Migration Status

- No migration files were generated.
- No migrations were applied.
- The custom user migration remains pending until the PostgreSQL connection is configured.

### Verification

- `python manage.py check` completed successfully.
