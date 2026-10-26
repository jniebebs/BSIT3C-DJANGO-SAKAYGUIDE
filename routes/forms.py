from django import forms

from .models import Location

SORT_CHOICES = [
    ('fare', 'Lowest estimated fare'),
    ('time', 'Shortest estimated travel time'),
    ('transfers', 'Fewest transfers'),
]


class RouteSearchForm(forms.Form):
    """Validates the From/To pair submitted by the search page."""

    origin = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    destination = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES, initial='fare')

    def clean(self):
        cleaned_data = super().clean()
        origin_id = cleaned_data.get('origin')
        destination_id = cleaned_data.get('destination')

        if origin_id and destination_id and origin_id == destination_id:
            self.add_error(
                'destination',
                'Origin and destination must be different locations.',
            )

        for field, value in (('origin', origin_id), ('destination', destination_id)):
            if value and not Location.objects.filter(
                pk=value, status='active'
            ).exists():
                self.add_error(field, 'Please choose a location from the list.')

        return cleaned_data


class SaveRouteForm(forms.Form):
    """Validates a Save Route request from a journey result card."""

    origin = forms.IntegerField(min_value=1)
    destination = forms.IntegerField(min_value=1)
    nickname = forms.CharField(required=False, max_length=100)

    def clean(self):
        cleaned_data = super().clean()
        origin_id = cleaned_data.get('origin')
        destination_id = cleaned_data.get('destination')

        if origin_id and destination_id and origin_id == destination_id:
            raise forms.ValidationError(
                'Origin and destination must be different locations.'
            )

        for field, value in (('origin', origin_id), ('destination', destination_id)):
            if value and not Location.objects.filter(
                pk=value, status='active'
            ).exists():
                self.add_error(field, 'Unknown location selected.')

        return cleaned_data
