"""Forms for the commuter account area.

Commuters can only ever edit their own profile and password. The role flags
(``is_staff`` / ``is_superuser``) and the activation flag are deliberately
absent from these forms, so a forged POST can never promote an account or
re-activate a suspended one.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


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
            else:
                css = 'form-control'
            existing = widget.attrs.get('class', '')
            widget.attrs['class'] = f'{existing} {css}'.strip()


class CommuterProfileForm(BootstrapFormMixin, forms.ModelForm):
    """Edit a commuter's own personal details.

    Only name, username and e-mail are editable. The role and the account
    status stay under administrator control.
    """

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'placeholder': 'Your first name',
                'autocomplete': 'given-name',
            }),
            'last_name': forms.TextInput(attrs={
                'placeholder': 'Your last name',
                'autocomplete': 'family-name',
            }),
            'username': forms.TextInput(attrs={
                'autocomplete': 'username',
            }),
            'email': forms.EmailInput(attrs={
                'autocomplete': 'email',
                'placeholder': 'name@example.com',
            }),
        }
        labels = {
            'first_name': 'First name',
            'last_name': 'Last name',
            'username': 'Username',
            'email': 'E-mail address',
        }

    def __init__(self, *args, **kwargs):
        self.actor = kwargs.pop('actor', None)
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        duplicate = User.objects.filter(username__iexact=username)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError('That username is already taken.')
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        duplicate = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError('That e-mail address is already in use.')
        return email

    def clean_first_name(self):
        return (self.cleaned_data.get('first_name') or '').strip()

    def clean_last_name(self):
        return (self.cleaned_data.get('last_name') or '').strip()


class CommuterPasswordForm(BootstrapFormMixin, forms.Form):
    """Change the signed-in commuter's own password."""

    current_password = forms.CharField(
        label='Current password',
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
        }),
        strip=False,
    )
    new_password1 = forms.CharField(
        label='New password',
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
        }),
        help_text=(
            'Use at least 8 characters and avoid common passwords.'
        ),
        strip=False,
    )
    new_password2 = forms.CharField(
        label='Confirm new password',
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
        }),
        strip=False,
    )

    def __init__(self, *args, actor=None, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        password = self.cleaned_data.get('current_password')
        if self.actor is not None and not self.actor.check_password(password):
            raise ValidationError('Your current password is not correct.')
        return password

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('new_password1')
        password2 = cleaned.get('new_password2')

        if password1 and password2 and password1 != password2:
            self.add_error('new_password2', 'The passwords do not match.')

        if password1 and self.actor is not None:
            try:
                validate_password(password1, self.actor)
            except ValidationError as exc:
                self.add_error('new_password1', exc)

        return cleaned

    def save(self, actor):
        actor.set_password(self.cleaned_data['new_password1'])
        actor.save(update_fields=['password'])
        return actor


class CommuterRegistrationForm(BootstrapFormMixin, forms.Form):
    """Public commuter self-registration.

    There is no role field on purpose. The commuter role is assigned by the
    view after the account is created, so a crafted POST cannot ask for
    administrator privileges.
    """

    full_name = forms.CharField(
        max_length=150,
        label='Full name',
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Juan Dela Cruz',
            'autocomplete': 'name',
        }),
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'autocomplete': 'username',
            'placeholder': 'juan.dela.cruz',
        }),
    )
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            'autocomplete': 'email',
            'placeholder': 'name@example.com',
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'placeholder': 'At least 8 characters',
        }),
        strip=False,
    )
    confirm_password = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'placeholder': 'Repeat your password',
        }),
        strip=False,
    )

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
        confirm = cleaned.get('confirm_password')

        full_name = (cleaned.get('full_name') or '').strip()
        if not full_name:
            # The legacy /register/ form posted a first and last name
            # separately. Accept both shapes so old links keep working.
            first = (self.data.get('first_name') or '').strip()
            last = (self.data.get('last_name') or '').strip()
            full_name = ' '.join(part for part in (first, last) if part)
        if not full_name:
            self.add_error('full_name', 'Full name is required.')
        else:
            cleaned['full_name'] = full_name

        if password and confirm and password != confirm:
            self.add_error('confirm_password', 'The passwords do not match.')

        if password and full_name:
            candidate = User(
                username=cleaned.get('username') or '',
                email=cleaned.get('email') or '',
                first_name=full_name,
            )
            try:
                validate_password(password, candidate)
            except ValidationError as exc:
                self.add_error('password', exc)

        return cleaned

    def save(self):
        """Create the commuter account with the commuter role hard-set."""
        data = self.cleaned_data
        full_name = data['full_name'].strip()
        first_name, _, last_name = full_name.partition(' ')

        user = User(
            username=data['username'],
            email=data['email'],
            first_name=first_name.strip(),
            last_name=(last_name.strip() or first_name.strip()),
        )
        user.set_password(data['password'])
        # Commuter role. Never promoted from public input.
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.save()
        return user
