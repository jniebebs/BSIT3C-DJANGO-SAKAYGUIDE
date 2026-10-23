"""SakayGuide transit domain models: terminals, routes, fares and advisories."""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

TWO_PLACES = Decimal('0.01')


def money(value):
    """Round a Decimal to two decimal places using half-up rounding."""
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class TransportMode(models.Model):
    """A way of getting around: jeepney, bus, train, tricycle, and so on."""

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    icon = models.CharField(
        max_length=32,
        help_text='Icon key the frontend maps to an image/SVG.',
    )
    color = models.CharField(max_length=7, default='#6366f1')
    avg_speed_kmh = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('20.00'),
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text='Average operating speed used for travel time estimates.',
    )

    class Meta:
        db_table = 'sakay_transport_mode'
        ordering = ['name']

    def __str__(self):
        return self.name


class Terminal(models.Model):
    """A bus terminal, jeepney terminal, station or transport hub."""

    name = models.CharField(max_length=150, unique=True)
    municipality = models.CharField(
        max_length=100,
        help_text='City or municipality the terminal belongs to.',
    )
    province = models.CharField(max_length=100, blank=True)
    landmark = models.CharField(
        max_length=255,
        blank=True,
        help_text='Nearby landmark used for fuzzy search.',
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('-90.0')), MaxValueValidator(Decimal('90.0'))],
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('-180.0')), MaxValueValidator(Decimal('180.0'))],
    )
    description = models.TextField(blank=True)
    transport_modes = models.ManyToManyField(
        TransportMode,
        related_name='terminals',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sakay_terminal'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def coordinates(self):
        """Latitude/longitude pair as JSON friendly floats."""
        return [float(self.latitude), float(self.longitude)]

    def destinations(self, limit=8):
        """Distinct terminals reachable directly via routes serving this terminal."""
        terminal_ids = (
            Route.objects.filter(
                is_active=True,
                stops__terminal=self,
            )
            .exclude(destination_terminal=self)
            .values_list('destination_terminal_id', flat=True)
            .distinct()
        )
        terminals = Terminal.objects.filter(pk__in=terminal_ids).order_by('name')[:limit]
        return [{'id': t.id, 'name': t.name, 'municipality': t.municipality} for t in terminals]

    def served_routes(self):
        """Active routes that stop at this terminal."""
        return (
            Route.objects.filter(is_active=True, stops__terminal=self)
            .distinct()
            .select_related('transport_mode', 'origin_terminal', 'destination_terminal')
            .order_by('code')
        )


class Route(models.Model):
    """A single transport line, e.g. the Kabankalan City to Barangay Camansi jeepney route."""

    OPTIMIZE_CHOICES = (('fastest', 'Fastest'), ('cheapest', 'Cheapest'))

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    transport_mode = models.ForeignKey(
        TransportMode,
        related_name='routes',
        on_delete=models.PROTECT,
    )
    origin_terminal = models.ForeignKey(
        Terminal,
        related_name='routes_starting',
        on_delete=models.CASCADE,
    )
    destination_terminal = models.ForeignKey(
        Terminal,
        related_name='routes_ending',
        on_delete=models.CASCADE,
    )
    base_fare = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('13.00'),
        help_text='Flag-down fare charged once per boarding.',
    )
    fare_per_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('2.00'),
        help_text='Distance fare added on top of the base fare.',
    )
    dwell_time_seconds = models.PositiveIntegerField(
        default=30,
        help_text='Average time spent at each intermediate stop.',
    )
    bidirectional = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sakay_route'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'

    # ------------------------------------------------------------------
    # Cumulative fare matrix (auto-maintained from route stops)
    # ------------------------------------------------------------------
    def recompute_fare_matrix(self):
        """Recalculate every stop's cumulative fare and travel time.

        Cumulative values are measured from the route origin:

        * ``cumulative_fare``       = base_fare + fare_per_km * distance
        * ``cumulative_time_minutes`` = cruising time + dwell time at the
          stops already passed.
        """
        speed = self.transport_mode.avg_speed_kmh or Decimal('1')
        dwell_minutes = Decimal(self.dwell_time_seconds) / Decimal(60)
        stops = list(self.stops.order_by('sequence'))

        for index, stop in enumerate(stops):
            distance = stop.distance_from_origin_km
            run_minutes = (distance / speed) * Decimal(60)
            cumulative_time = run_minutes + dwell_minutes * index
            RouteStop.objects.filter(pk=stop.pk).update(
                cumulative_fare=money(self.base_fare + self.fare_per_km * distance),
                cumulative_time_minutes=money(cumulative_time),
            )
        return stops

    def fare_between(self, board_index, alight_index, stops=None):
        """Fare for riding between two stop indexes (board_index < alight_index).

        Each boarding pays the flag-down base fare plus the per-kilometre rate
        for the distance actually travelled.
        """
        if board_index > alight_index:
            board_index, alight_index = alight_index, board_index
        if stops is None:
            stops = list(self.stops.order_by('sequence'))
        board = stops[board_index]
        alight = stops[alight_index]
        distance = alight.distance_from_origin_km - board.distance_from_origin_km
        return money(self.base_fare + self.fare_per_km * distance)

    def time_between_minutes(self, board_index, alight_index, stops=None):
        """Estimated travel minutes between two stop indexes of this route."""
        if board_index > alight_index:
            board_index, alight_index = alight_index, board_index
        if stops is None:
            stops = list(self.stops.order_by('sequence'))
        board = stops[board_index]
        alight = stops[alight_index]
        speed = self.transport_mode.avg_speed_kmh or Decimal('1')
        run_minutes = (
            (alight.distance_from_origin_km - board.distance_from_origin_km) / speed
        ) * Decimal(60)
        dwell_minutes = Decimal(self.dwell_time_seconds) / Decimal(60)
        return money(run_minutes + dwell_minutes * (alight_index - board_index))

    def fare_matrix(self):
        """Full pairwise cumulative fare/time matrix between every stop pair."""
        stops = list(self.stops.select_related('terminal').order_by('sequence'))
        matrix = []
        for i, board in enumerate(stops):
            for j, alight in enumerate(stops):
                if i >= j:
                    continue
                matrix.append({
                    'from_sequence': board.sequence,
                    'from_terminal': board.terminal.name,
                    'to_sequence': alight.sequence,
                    'to_terminal': alight.terminal.name,
                    'fare': float(self.fare_between(i, j, stops)),
                    'time_minutes': float(self.time_between_minutes(i, j, stops)),
                    'distance_km': float(
                        money(alight.distance_from_origin_km - board.distance_from_origin_km)
                    ),
                })
        return matrix


class RouteStop(models.Model):
    """A stop of a route; cumulative fare/time columns are automated."""

    route = models.ForeignKey(Route, related_name='stops', on_delete=models.CASCADE)
    terminal = models.ForeignKey(Terminal, related_name='route_stops', on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField(
        help_text='1-based position of the stop along the route.',
    )
    distance_from_origin_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    cumulative_fare = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0)
    cumulative_time_minutes = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
        default=0,
    )

    class Meta:
        db_table = 'sakay_route_stop'
        ordering = ['sequence']
        constraints = [
            models.UniqueConstraint(fields=['route', 'sequence'], name='unique_route_sequence'),
            models.UniqueConstraint(fields=['route', 'terminal'], name='unique_route_terminal'),
        ]

    def __str__(self):
        return f'{self.route.code} #{self.sequence}: {self.terminal.name}'

    def clean(self):
        if self.distance_from_origin_km is not None and self.distance_from_origin_km < 0:
            raise ValidationError({'distance_from_origin_km': 'Distance cannot be negative.'})
        if self.sequence is not None and self.sequence < 1:
            raise ValidationError({'sequence': 'Sequence must be 1 or greater.'})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.route.recompute_fare_matrix()

    def delete(self, *args, **kwargs):
        route = self.route
        super().delete(*args, **kwargs)
        route.recompute_fare_matrix()


class Advisory(models.Model):
    """Lightweight community-submitted transit advisory/alert."""

    CATEGORY_CHOICES = (
        ('delay', 'Delay'),
        ('accident', 'Accident'),
        ('reroute', 'Reroute'),
        ('flooding', 'Flooding'),
        ('roadwork', 'Roadwork'),
        ('event', 'Public Event'),
        ('other', 'Other'),
    )
    SEVERITY_CHOICES = (
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    )
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('expired', 'Expired'),
    )

    title = models.CharField(max_length=120)
    message = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='delay')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='info')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    terminal = models.ForeignKey(
        Terminal,
        related_name='advisories',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    routes = models.ManyToManyField(Route, related_name='advisories', blank=True)
    reported_by = models.CharField(max_length=60, blank=True)
    upvotes = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sakay_advisory'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.category}] {self.title}'

    @property
    def is_live(self):
        """True while the advisory is active and has not expired."""
        if self.status != 'active':
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True


class SavedRoute(models.Model):
    """A commuter's saved (frequently used) route.

    Tied to the authenticated user. Anonymous commuters are not supported for
    saved routes because there is no stable identifier to attach them to.
    Duplicate (user, origin, destination) combinations are prevented.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='saved_routes',
        on_delete=models.CASCADE,
    )
    origin_terminal = models.ForeignKey(
        Terminal,
        related_name='saved_routes_from',
        on_delete=models.CASCADE,
    )
    destination_terminal = models.ForeignKey(
        Terminal,
        related_name='saved_routes_to',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=100,
        blank=True,
        help_text='Optional commuter-chosen name for this saved route.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sakay_saved_route'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'origin_terminal', 'destination_terminal'],
                name='unique_user_saved_route',
            ),
        ]

    def __str__(self):
        label = self.name or f'{self.origin_terminal} → {self.destination_terminal}'
        return f'{self.user.username}: {label}'


class SearchHistory(models.Model):
    """A commuter's route search history.

    The user is nullable so anonymous searches can be recorded when a session
    key is available. Older entries are pruned by administrators.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='search_history',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    origin_terminal = models.ForeignKey(
        Terminal,
        related_name='search_history_from',
        on_delete=models.CASCADE,
    )
    destination_terminal = models.ForeignKey(
        Terminal,
        related_name='search_history_to',
        on_delete=models.CASCADE,
    )
    searched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sakay_search_history'
        ordering = ['-searched_at']

    def __str__(self):
        user_label = self.user.username if self.user_id else 'anonymous'
        return f'{user_label}: {self.origin_terminal} → {self.destination_terminal}'
