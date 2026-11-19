"""Forms used by the SakayGuide administrator dashboard.

The transit models are mapped to the existing MySQL schema with
``managed = False``. Django can still validate and save them normally; the
SakayGuide database router decides which connection receives each write.

SakayGuide has exactly two application-level roles: ``administrator`` and
``commuter``. The single role flag is ``User.is_staff``: a staff account is an
administrator with full management permissions, every other account is a
commuter. There is no separate super administrator role.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from routes.models import (
    Barangay,
    FareType,
    Location,
    Route,
    RouteFare,
    RouteStop,
    RouteTransfer,
    TransportationType,
)

User = get_user_model()

LOCATION_TYPE_SUGGESTIONS = [
    'terminal', 'stop', 'landmark', 'establishment', 'government',
    'hospital', 'school', 'market', 'barangay', 'other',
]

# The two application roles. Administrators have full control over every
# account, record, fare, location and report in SakayGuide.
ROLE_ADMINISTRATOR = 'administrator'
ROLE_COMMUTER = 'commuter'
ROLE_CHOICES = [
    (ROLE_COMMUTER, 'Commuter'),
    (ROLE_ADMINISTRATOR, 'Administrator'),
]


def role_for(user):
    """Return the application role key for a Django user.

    ``is_staff`` is the only role flag. Accounts that were created as
    Django superusers are administrators like every other staff account, so
    they keep their account and their permissions.
    """
    return ROLE_ADMINISTRATOR if user.is_staff else ROLE_COMMUTER


class BootstrapFormMixin:
    """Give every widget the Tabler/Bootstrap class used by the project."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = 'form-check-input'
            elif isinstance(widget, forms.Select):
                css = 'form-select'
            elif isinstance(widget, forms.FileInput):
                css = 'form-control'
            else:
                css = 'form-control'
            existing = widget.attrs.get('class', '')
            widget.attrs['class'] = f'{existing} {css}'.strip()


class LocationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Location
        fields = [
            'barangay', 'location_name', 'location_type', 'address',
            'description', 'status', 'latitude', 'longitude',
        ]
        widgets = {
            'address': forms.TextInput(),
            'description': forms.Textarea(attrs={'rows': 4}),
            'latitude': forms.NumberInput(attrs={
                'step': '0.0000001', 'min': '-90', 'max': '90',
                'placeholder': 'e.g. 9.9898000',
            }),
            'longitude': forms.NumberInput(attrs={
                'step': '0.0000001', 'min': '-180', 'max': '180',
                'placeholder': 'e.g. 122.8123000',
            }),
        }
        labels = {
            'barangay': 'Barangay',
            'location_name': 'Location name',
            'location_type': 'Location type',
            'latitude': 'Latitude',
            'longitude': 'Longitude',
        }
        help_texts = {
            'latitude': 'Optional. WGS 84 latitude. Leave both coordinates blank '
                        'when the map position has not been verified.',
            'longitude': 'Optional. WGS 84 longitude.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['barangay'].queryset = (
            Barangay.objects.select_related('municipality')
            .order_by('municipality__municipality_name', 'barangay_name')
        )
        self.fields['location_type'].widget.attrs.update({
            'list': 'location-type-options',
            'autocomplete': 'off',
        })
        self.fields['status'].choices = [
            ('active', 'Active'), ('inactive', 'Inactive'),
        ]

    def clean(self):
        cleaned = super().clean()
        latitude = cleaned.get('latitude')
        longitude = cleaned.get('longitude')

        if (latitude is None) != (longitude is None):
            raise ValidationError(
                'Enter both latitude and longitude, or leave both blank.'
            )
        if latitude is not None and not (-90 <= latitude <= 90):
            self.add_error('latitude', 'Latitude must be between -90 and 90.')
        if longitude is not None and not (-180 <= longitude <= 180):
            self.add_error('longitude', 'Longitude must be between -180 and 180.')

        name = (cleaned.get('location_name') or '').strip()
        location_type = (cleaned.get('location_type') or '').strip()
        barangay = cleaned.get('barangay')
        if name and location_type and barangay:
            duplicate = Location.objects.filter(
                barangay=barangay,
                location_name__iexact=name,
                location_type__iexact=location_type,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise ValidationError(
                    'A location with this name and type already exists in that '
                    'barangay.'
                )
        return cleaned


class RouteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Route
        fields = [
            'route_code', 'route_name', 'transport_type', 'origin',
            'destination', 'estimated_travel_time', 'route_description',
            'status',
        ]
        widgets = {
            'route_code': forms.TextInput(attrs={
                'placeholder': 'e.g. KAB-JP-06', 'autocomplete': 'off',
            }),
            'route_name': forms.TextInput(attrs={
                'placeholder': 'e.g. Public Terminal - CityMall Jeepney',
            }),
            'estimated_travel_time': forms.NumberInput(attrs={
                'min': '1', 'step': '1',
            }),
            'route_description': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'route_code': 'Route code',
            'route_name': 'Route name',
            'transport_type': 'Transport mode',
            'origin': 'Origin / boarding point',
            'destination': 'Destination / drop-off point',
            'estimated_travel_time': 'Estimated travel time (minutes)',
            'route_description': 'Route description',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        locations = Location.objects.select_related('barangay').order_by(
            'location_name'
        )
        self.fields['origin'].queryset = locations
        self.fields['destination'].queryset = locations
        self.fields['transport_type'].queryset = (
            TransportationType.objects.order_by('transport_name')
        )
        self.fields['status'].choices = [
            ('active', 'Active'), ('inactive', 'Inactive'),
        ]

    def clean_route_code(self):
        code = (self.cleaned_data.get('route_code') or '').strip()
        duplicate = Route.objects.filter(route_code__iexact=code)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError('That route code is already in use.')
        return code

    def clean(self):
        cleaned = super().clean()
        origin = cleaned.get('origin')
        destination = cleaned.get('destination')
        travel_time = cleaned.get('estimated_travel_time')

        if origin and destination and origin.pk == destination.pk:
            self.add_error(
                'destination',
                'The destination must be different from the origin.',
            )
        if travel_time is not None and travel_time <= 0:
            self.add_error(
                'estimated_travel_time',
                'Estimated travel time must be greater than zero.',
            )
        return cleaned


class TransportationTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TransportationType
        fields = ['transport_name', 'description', 'status']
        labels = {'transport_name': 'Transport mode name'}
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = [
            ('active', 'Active'), ('inactive', 'Inactive'),
        ]

    def clean_transport_name(self):
        name = (self.cleaned_data.get('transport_name') or '').strip()
        duplicate = TransportationType.objects.filter(
            transport_name__iexact=name
        )
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError('That transport mode already exists.')
        return name


class FareTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FareType
        fields = [
            'fare_type_name', 'description', 'discount_percentage', 'status',
        ]
        labels = {'fare_type_name': 'Fare category'}
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'discount_percentage': forms.NumberInput(attrs={
                'min': '0', 'max': '100', 'step': '0.01',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = [
            ('active', 'Active'), ('inactive', 'Inactive'),
        ]

    def clean_fare_type_name(self):
        name = (self.cleaned_data.get('fare_type_name') or '').strip()
        duplicate = FareType.objects.filter(fare_type_name__iexact=name)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError('That fare category already exists.')
        return name


class RouteStopForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RouteStop
        fields = [
            'route', 'location', 'stop_order', 'is_transfer_point',
            'estimated_stop_time',
        ]
        labels = {
            'stop_order': 'Stop order',
            'is_transfer_point': 'Usable as a transfer point',
            'estimated_stop_time': 'Estimated stop time (minutes)',
        }
        widgets = {
            'stop_order': forms.NumberInput(attrs={'min': '1', 'step': '1'}),
            'estimated_stop_time': forms.NumberInput(attrs={
                'min': '0', 'step': '1',
            }),
        }

    def __init__(self, *args, route=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.locked_route = route
        if route is not None and 'route' in self.fields:
            self.fields.pop('route')
        elif 'route' in self.fields:
            self.fields['route'].queryset = (
                Route.objects.select_related('origin', 'destination')
                .order_by('route_code')
            )
            self.fields['route'].label = 'Route'
        if 'location' in self.fields:
            self.fields['location'].queryset = Location.objects.order_by(
                'location_name'
            )
            self.fields['location'].label = 'Location / stop'

    def _route(self):
        if self.locked_route is not None:
            return self.locked_route
        route = self.cleaned_data.get('route')
        if route is not None:
            return route
        if self.instance.pk:
            return self.instance.route
        return None

    def clean(self):
        cleaned = super().clean()
        route = self._route()
        order = cleaned.get('stop_order')
        location = cleaned.get('location')

        if order is not None and order <= 0:
            self.add_error('stop_order', 'Stop order must be greater than zero.')

        if route is not None:
            duplicates = RouteStop.objects.filter(route=route)
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if order is not None and duplicates.filter(
                stop_order=order
            ).exists():
                self.add_error(
                    'stop_order',
                    'Another stop already uses this order on the route.',
                )
            if location is not None and duplicates.filter(
                location=location
            ).exists():
                self.add_error(
                    'location',
                    'That location is already a stop on this route.',
                )

            if (
                self.instance.pk
                and location is not None
                and self.instance.location_id != location.pk
                and RouteTransfer.objects.filter(
                    Q(from_route=route) | Q(to_route=route),
                    transfer_location_id=self.instance.location_id,
                ).exists()
            ):
                self.add_error(
                    'location',
                    'This stop is used by a transfer connection at its current '
                    'location. Update or remove the transfer before moving it.',
                )
        return cleaned

    def save(self, commit=True):
        stop = super().save(commit=False)
        if self.locked_route is not None:
            stop.route = self.locked_route
        if commit:
            stop.save()
        return stop


class RouteFareForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RouteFare
        fields = [
            'route', 'fare_type', 'minimum_fare', 'fare_per_km',
            'total_estimated_fare', 'effective_date', 'expiry_date', 'status',
        ]
        labels = {
            'minimum_fare': 'Minimum fare (PHP)',
            'fare_per_km': 'Fare per kilometre (PHP)',
            'total_estimated_fare': 'Total estimated fare (PHP)',
            'effective_date': 'Effective date',
            'expiry_date': 'Expiry date (optional)',
        }
        help_texts = {
            'minimum_fare': (
                'The lowest amount charged for a short segment of this route. '
                'Commuters never see less than this.'
            ),
            'total_estimated_fare': (
                'The amount charged for the full route. Commuter dashboards '
                'and journey results use this saved total.'
            ),
        }
        widgets = {
            'minimum_fare': forms.NumberInput(attrs={
                'min': '0', 'step': '0.01',
            }),
            'fare_per_km': forms.NumberInput(attrs={
                'min': '0', 'step': '0.01',
            }),
            'total_estimated_fare': forms.NumberInput(attrs={
                'min': '0', 'step': '0.01',
            }),
            'effective_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, route=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.locked_route = route
        if route is not None and 'route' in self.fields:
            self.fields.pop('route')
        elif 'route' in self.fields:
            self.fields['route'].queryset = (
                Route.objects.select_related('origin', 'destination')
                .order_by('route_code')
            )
        self.fields['fare_type'].queryset = FareType.objects.order_by(
            'fare_type_name'
        )
        self.fields['status'].choices = RouteFare.FARE_STATUS_CHOICES

    def _route(self):
        if self.locked_route is not None:
            return self.locked_route
        route = self.cleaned_data.get('route')
        if route is not None:
            return route
        if self.instance.pk:
            return self.instance.route
        return None

    def clean(self):
        cleaned = super().clean()
        route = self._route()
        fare_type = cleaned.get('fare_type')
        effective = cleaned.get('effective_date')
        expiry = cleaned.get('expiry_date')
        minimum = cleaned.get('minimum_fare')
        per_km = cleaned.get('fare_per_km')
        total = cleaned.get('total_estimated_fare')

        for field_name, value in (
            ('minimum_fare', minimum),
            ('fare_per_km', per_km),
            ('total_estimated_fare', total),
        ):
            if value is not None and value < 0:
                self.add_error(field_name, 'Amounts cannot be negative.')

        if expiry and effective and expiry < effective:
            self.add_error(
                'expiry_date',
                'The expiry date cannot be before the effective date.',
            )

        if route and fare_type and effective:
            duplicate = RouteFare.objects.filter(
                route=route, fare_type=fare_type, effective_date=effective,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error(
                    'effective_date',
                    'This fare category already has a record for that route '
                    'and effective date.',
                )
        return cleaned

    def save(self, commit=True):
        fare = super().save(commit=False)
        if self.locked_route is not None:
            fare.route = self.locked_route
        # The minimum fare is a floor for every commuter display, so a total
        # entered below it can never be shown as the route's fare. Lift the
        # saved total instead of silently displaying less than the minimum.
        if (
            fare.total_estimated_fare is not None
            and fare.minimum_fare is not None
            and fare.total_estimated_fare < fare.minimum_fare
        ):
            fare.total_estimated_fare = fare.minimum_fare
        if commit:
            fare.save()
        return fare


class RouteTransferForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RouteTransfer
        fields = [
            'from_route', 'to_route', 'transfer_location',
            'transfer_instructions', 'estimated_transfer_time',
            'additional_estimated_fare',
        ]
        labels = {
            'from_route': 'From route',
            'to_route': 'To route',
            'transfer_location': 'Transfer location',
            'estimated_transfer_time': 'Estimated transfer time (minutes)',
            'additional_estimated_fare': 'Additional fare (PHP)',
        }
        widgets = {
            'transfer_instructions': forms.Textarea(attrs={'rows': 4}),
            'estimated_transfer_time': forms.NumberInput(attrs={
                'min': '0', 'step': '1',
            }),
            'additional_estimated_fare': forms.NumberInput(attrs={
                'min': '0', 'step': '0.01',
            }),
        }

    def __init__(self, *args, route=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.locked_route = route
        routes = Route.objects.select_related(
            'origin', 'destination'
        ).order_by('route_code')

        if route is not None and 'from_route' in self.fields:
            self.fields.pop('from_route')
        elif 'from_route' in self.fields:
            self.fields['from_route'].queryset = routes

        if 'to_route' in self.fields:
            self.fields['to_route'].queryset = routes
        if 'transfer_location' in self.fields:
            self.fields['transfer_location'].queryset = Location.objects.order_by(
                'location_name'
            )

    def _from_route(self):
        if self.locked_route is not None:
            return self.locked_route
        route = self.cleaned_data.get('from_route')
        if route is not None:
            return route
        if self.instance.pk:
            return self.instance.from_route
        return None

    def clean(self):
        cleaned = super().clean()
        from_route = self._from_route()
        to_route = cleaned.get('to_route')
        location = cleaned.get('transfer_location')
        transfer_time = cleaned.get('estimated_transfer_time')
        fare = cleaned.get('additional_estimated_fare')

        if from_route and to_route and from_route.pk == to_route.pk:
            self.add_error(
                'to_route',
                'A route cannot transfer to itself.',
            )

        if transfer_time is not None and transfer_time < 0:
            self.add_error(
                'estimated_transfer_time',
                'Transfer time cannot be negative.',
            )
        if fare is not None and fare < 0:
            self.add_error(
                'additional_estimated_fare',
                'Additional fare cannot be negative.',
            )

        if from_route and to_route and location:
            from_has_stop = RouteStop.objects.filter(
                route=from_route, location=location,
            ).exists()
            to_has_stop = RouteStop.objects.filter(
                route=to_route, location=location,
            ).exists()
            if not from_has_stop or not to_has_stop:
                self.add_error(
                    'transfer_location',
                    'The transfer location must be a stop on both routes. '
                    'Add it to the route stops first.',
                )

            duplicate = RouteTransfer.objects.filter(
                from_route=from_route,
                to_route=to_route,
                transfer_location=location,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise ValidationError(
                    'That transfer connection already exists.'
                )
        return cleaned

    def save(self, commit=True):
        transfer = super().save(commit=False)
        if self.locked_route is not None:
            transfer.from_route = self.locked_route
        if commit:
            transfer.save()
        return transfer


class AdminUserCreateForm(BootstrapFormMixin, forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(max_length=254)
    role = forms.ChoiceField(choices=ROLE_CHOICES, initial='commuter')
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )
    password_confirm = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )
    is_active = forms.BooleanField(
        label='Account is active', required=False, initial=True,
    )

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        # Every administrator may create administrator accounts, so both
        # roles stay selectable for any authorized administrator.
        self.fields['role'].choices = list(ROLE_CHOICES)

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('That username is already taken.')
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('That e-mail address is already in use.')
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        confirm = cleaned.get('password_confirm')

        if password and confirm and password != confirm:
            self.add_error('password_confirm', 'The passwords do not match.')

        if password:
            candidate = User(
                username=cleaned.get('username') or '',
                email=cleaned.get('email') or '',
                first_name=cleaned.get('first_name') or '',
                last_name=cleaned.get('last_name') or '',
            )
            try:
                validate_password(password, candidate)
            except ValidationError as exc:
                self.add_error('password', exc)
        return cleaned

    def save(self):
        data = self.cleaned_data
        role = data['role']
        user = User(
            username=data['username'],
            email=data['email'],
            first_name=data.get('first_name') or '',
            last_name=data.get('last_name') or '',
            is_active=bool(data.get('is_active')),
            # The administrator role. Accounts created here never receive a
            # Django superuser flag; that is only granted by
            # `python manage.py createsuperuser`.
            is_staff=role == ROLE_ADMINISTRATOR,
            is_superuser=False,
        )
        user.set_password(data['password'])
        user.save()
        return user


class AdminUserEditForm(BootstrapFormMixin, forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(max_length=254)
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )
    password_confirm = forms.CharField(
        label='Confirm new password',
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )
    is_active = forms.BooleanField(
        label='Account is active', required=False,
    )

    def __init__(self, *args, actor=None, target=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.target = target
        if target is not None and not self.is_bound:
            self.initial.update({
                'username': target.username,
                'first_name': target.first_name,
                'last_name': target.last_name,
                'email': target.email,
                'role': role_for(target),
                'is_active': target.is_active,
            })
        # Every administrator may assign the administrator role.
        self.fields['role'].choices = list(ROLE_CHOICES)

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        duplicate = User.objects.filter(username__iexact=username)
        if self.target is not None:
            duplicate = duplicate.exclude(pk=self.target.pk)
        if duplicate.exists():
            raise ValidationError('That username is already taken.')
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        duplicate = User.objects.filter(email__iexact=email)
        if self.target is not None:
            duplicate = duplicate.exclude(pk=self.target.pk)
        if duplicate.exists():
            raise ValidationError('That e-mail address is already in use.')
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        confirm = cleaned.get('password_confirm')
        role = cleaned.get('role')

        if password and confirm and password != confirm:
            self.add_error('password_confirm', 'The passwords do not match.')
        if password and not confirm:
            self.add_error('password_confirm', 'Confirm the new password.')
        if confirm and not password:
            self.add_error('password', 'Enter the new password.')

        if password and self.target is not None:
            try:
                validate_password(password, self.target)
            except ValidationError as exc:
                self.add_error('password', exc)
        return cleaned

    def save(self):
        target = self.target
        data = self.cleaned_data
        role = data['role']
        target.username = data['username']
        target.first_name = data.get('first_name') or ''
        target.last_name = data.get('last_name') or ''
        target.email = data['email']
        target.is_active = bool(data.get('is_active'))
        target.is_staff = role == ROLE_ADMINISTRATOR
        # The Django superuser flag is never granted or revoked here. It
        # belongs to `python manage.py createsuperuser` and is preserved so
        # existing accounts keep the permissions they already had.
        if data.get('password'):
            target.set_password(data['password'])
        target.save()
        return target
