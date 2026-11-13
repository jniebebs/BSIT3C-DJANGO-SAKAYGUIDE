"""Route SakayGuide tables to the 'sakayguide' database.

The project keeps its Django app tables (auth, sessions, info records) on the
'default' connection, while the 14 SakayGuide transit tables live in
sakayguide_db. The administrator dashboard writes to the same tables commuters
read from: locations, routes, stops, fares, transfers and the user mirror/audit
trail. The schema still belongs to the SakayGuide SQL scripts, so these models
remain ``managed = False`` -- Django never creates or alters their tables.
"""
SAKAYGUIDE_TABLES = {
    'municipalities', 'barangays', 'locations', 'transportation_types',
    'fare_types', 'routes', 'route_stops', 'route_fares', 'route_transfers',
    'saved_routes', 'search_history', 'route_landmarks',
    'admin_activity_logs', 'users',
}

# Tables the administrator dashboard may write to. Master records are normally
# deactivated instead of hard-deleted so existing searches, saved routes and
# audit records keep their foreign keys.
SAKAYGUIDE_WRITABLE_TABLES = {
    'search_history', 'saved_routes', 'users', 'admin_activity_logs',
    'locations', 'routes', 'route_stops', 'route_fares', 'route_transfers',
    'transportation_types', 'fare_types',
}


class SakayGuideRouter:
    def _db_for(self, model):
        table = model._meta.db_table
        if table in SAKAYGUIDE_TABLES:
            return 'sakayguide'
        return None

    def db_for_read(self, model, **hints):
        return self._db_for(model)

    def db_for_write(self, model, **hints):
        table = model._meta.db_table
        if table in SAKAYGUIDE_WRITABLE_TABLES:
            return 'sakayguide'
        if table in SAKAYGUIDE_TABLES:
            raise RuntimeError(
                f'Table "{table}" is managed by the SakayGuide SQL scripts; '
                'it is read-only from Django.'
            )
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Never create/migrate Django tables on the SakayGuide database.
        return db != 'sakayguide'
