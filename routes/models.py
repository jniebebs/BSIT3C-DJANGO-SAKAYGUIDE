"""Django models mapped to the existing sakayguide_db tables.

All models are ``managed = False``: the 14 tables already exist in MySQL and
are owned by the SakayGuide SQL scripts. Django only reads/writes them through
the ``sakayguide`` database connection (see mysite/routers.py). No schema is
created or changed by these models.
"""
from django.db import models
from django.utils import timezone

ACTIVE = 'active'
INACTIVE = 'inactive'
STATUS_CHOICES = [(ACTIVE, 'Active'), (INACTIVE, 'Inactive')]


class Municipality(models.Model):
    municipality_id = models.AutoField(primary_key=True)
    municipality_name = models.CharField(max_length=100)
    province = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=ACTIVE)

    class Meta:
        db_table = 'municipalities'
        managed = False
        constraints = [
            models.UniqueConstraint(
                fields=['municipality_name', 'province'],
                name='uq_municipality_name_province',
            ),
        ]

    def __str__(self):
        return f'{self.municipality_name}, {self.province}'


class Barangay(models.Model):
    barangay_id = models.AutoField(primary_key=True)
    municipality = models.ForeignKey(
        Municipality, on_delete=models.DO_NOTHING, db_column='municipality_id',
        related_name='barangays',
    )
    barangay_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'barangays'
        managed = False
        constraints = [
            models.UniqueConstraint(
                fields=['municipality', 'barangay_name'],
                name='uq_barangay_municipality_name',
            ),
        ]

    def __str__(self):
        return self.barangay_name


class Location(models.Model):
    location_id = models.AutoField(primary_key=True)
    barangay = models.ForeignKey(
        Barangay, on_delete=models.DO_NOTHING, db_column='barangay_id',
        related_name='locations',
    )
    location_name = models.CharField(max_length=150)
    location_type = models.CharField(max_length=50)
    address = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=ACTIVE)
    # Verified WGS 84 coordinates (added by sakayguide_locations_coordinates.sql).
    # They stay NULL for any location whose map position has not been verified
    # yet; the map feature treats NULL as "show in instructions only".
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True,
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True,
    )

    class Meta:
        db_table = 'locations'
        managed = False
        constraints = [
            models.UniqueConstraint(
                fields=['barangay', 'location_name', 'location_type'],
                name='uq_location_barangay_name_type',
            ),
        ]

    def __str__(self):
        return self.location_name


class TransportationType(models.Model):
    transport_type_id = models.AutoField(primary_key=True)
    transport_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=ACTIVE)

    class Meta:
        db_table = 'transportation_types'
        managed = False

    def __str__(self):
        return self.transport_name


class FareType(models.Model):
    fare_type_id = models.AutoField(primary_key=True)
    fare_type_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=ACTIVE)

    class Meta:
        db_table = 'fare_types'
        managed = False

    def __str__(self):
        return self.fare_type_name


class SakayUser(models.Model):
    """Mirror of the sakayguide_db ``users`` table (not Django auth)."""
    ROLE_ADMIN = 'admin'
    ROLE_COMMUTER = 'commuter'
    ROLE_CHOICES = [(ROLE_ADMIN, 'Admin'), (ROLE_COMMUTER, 'Commuter')]

    user_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=100)
    email = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=8, choices=ROLE_CHOICES, default=ROLE_COMMUTER)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=ACTIVE)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'users'
        managed = False

    def __str__(self):
        return self.full_name or self.email


class Route(models.Model):
    route_id = models.AutoField(primary_key=True)
    route_name = models.CharField(max_length=150)
    route_code = models.CharField(max_length=30, unique=True)
    origin = models.ForeignKey(
        Location, on_delete=models.DO_NOTHING, db_column='origin_id',
        related_name='+',
    )
    destination = models.ForeignKey(
        Location, on_delete=models.DO_NOTHING, db_column='destination_id',
        related_name='+',
    )
    transport_type = models.ForeignKey(
        TransportationType, on_delete=models.DO_NOTHING,
        db_column='transport_type_id', related_name='routes',
    )
    estimated_travel_time = models.PositiveIntegerField()
    route_description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=ACTIVE)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'routes'
        managed = False

    def __str__(self):
        return f'{self.route_code} - {self.route_name}'


class RouteStop(models.Model):
    stop_id = models.AutoField(primary_key=True)
    route = models.ForeignKey(
        Route, on_delete=models.DO_NOTHING, db_column='route_id',
        related_name='stops',
    )
    location = models.ForeignKey(
        Location, on_delete=models.DO_NOTHING, db_column='location_id',
        related_name='stops',
    )
    stop_order = models.PositiveSmallIntegerField()
    is_transfer_point = models.BooleanField(default=False)
    estimated_stop_time = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'route_stops'
        managed = False
        ordering = ['route_id', 'stop_order']
        constraints = [
            models.UniqueConstraint(
                fields=['route', 'stop_order'], name='uq_route_stop_order',
            ),
            models.UniqueConstraint(
                fields=['route', 'location'], name='uq_route_stop_location',
            ),
        ]

    def __str__(self):
        return f'{self.route_id}#{self.stop_order}: {self.location_id}'


class RouteFare(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_EXPIRED = 'expired'
    FARE_STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    fare_id = models.AutoField(primary_key=True)
    route = models.ForeignKey(
        Route, on_delete=models.DO_NOTHING, db_column='route_id',
        related_name='fares',
    )
    fare_type = models.ForeignKey(
        FareType, on_delete=models.DO_NOTHING, db_column='fare_type_id',
        related_name='fares',
    )
    minimum_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fare_per_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_estimated_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    effective_date = models.DateField()
    expiry_date = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=8, choices=FARE_STATUS_CHOICES, default=STATUS_ACTIVE,
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'route_fares'
        managed = False
        constraints = [
            models.UniqueConstraint(
                fields=['route', 'fare_type', 'effective_date'],
                name='uq_route_fare_type_date',
            ),
        ]

    def __str__(self):
        return f'{self.route_id} {self.fare_type_id} {self.total_estimated_fare}'


class RouteTransfer(models.Model):
    transfer_id = models.AutoField(primary_key=True)
    from_route = models.ForeignKey(
        Route, on_delete=models.DO_NOTHING, db_column='from_route_id',
        related_name='transfers_from',
    )
    to_route = models.ForeignKey(
        Route, on_delete=models.DO_NOTHING, db_column='to_route_id',
        related_name='transfers_to',
    )
    transfer_location = models.ForeignKey(
        Location, on_delete=models.DO_NOTHING, db_column='transfer_location_id',
        related_name='transfers',
    )
    transfer_instructions = models.TextField()
    estimated_transfer_time = models.PositiveSmallIntegerField(default=0)
    additional_estimated_fare = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
    )

    class Meta:
        db_table = 'route_transfers'
        managed = False

    def __str__(self):
        return f'{self.from_route_id} -> {self.to_route_id} @ {self.transfer_location_id}'


class SavedRoute(models.Model):
    saved_route_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        SakayUser, on_delete=models.DO_NOTHING, db_column='user_id',
        related_name='saved_routes',
    )
    origin = models.ForeignKey(
        Location, on_delete=models.DO_NOTHING, db_column='origin_id',
        related_name='+',
    )
    destination = models.ForeignKey(
        Location, on_delete=models.DO_NOTHING, db_column='destination_id',
        related_name='+',
    )
    nickname = models.CharField(max_length=100, blank=True, null=True)
    saved_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'saved_routes'
        managed = False
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'origin', 'destination'],
                name='uq_saved_route_user_od',
            ),
        ]

    def __str__(self):
        return self.nickname or f'{self.origin_id} -> {self.destination_id}'


class SearchHistory(models.Model):
    search_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        SakayUser, on_delete=models.DO_NOTHING, db_column='user_id',
        blank=True, null=True, related_name='searches',
    )
    origin = models.ForeignKey(
        Location, on_delete=models.DO_NOTHING, db_column='origin_id',
        related_name='+',
    )
    destination = models.ForeignKey(
        Location, on_delete=models.DO_NOTHING, db_column='destination_id',
        related_name='+',
    )
    search_date = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'search_history'
        managed = False

    def __str__(self):
        return f'{self.origin_id} -> {self.destination_id}'


class RouteLandmark(models.Model):
    route_landmark_id = models.AutoField(primary_key=True)
    route = models.ForeignKey(
        Route, on_delete=models.DO_NOTHING, db_column='route_id',
        related_name='landmarks',
    )
    location = models.ForeignKey(
        Location, on_delete=models.DO_NOTHING, db_column='location_id',
        related_name='+',
    )
    landmark_description = models.TextField(blank=True, null=True)
    distance_from_origin = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    display_order = models.PositiveSmallIntegerField()

    class Meta:
        db_table = 'route_landmarks'
        managed = False
        constraints = [
            models.UniqueConstraint(
                fields=['route', 'location'], name='uq_landmark_route_location',
            ),
            models.UniqueConstraint(
                fields=['route', 'display_order'], name='uq_landmark_route_order',
            ),
        ]

    def __str__(self):
        return f'{self.route_id} lm{self.display_order}'


class AdminActivityLog(models.Model):
    log_id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(
        SakayUser, on_delete=models.DO_NOTHING, db_column='admin_id',
        related_name='activity_logs',
    )
    action_type = models.CharField(max_length=50)
    table_affected = models.CharField(max_length=64)
    record_id = models.PositiveIntegerField(blank=True, null=True)
    action_description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'admin_activity_logs'
        managed = False

    def __str__(self):
        return f'{self.action_type} {self.table_affected}'
