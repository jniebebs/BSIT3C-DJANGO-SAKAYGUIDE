"""Password reset flows for the two SakayGuide account portals.

Django's built-in reset views are reused as-is; only the templates, the
success URL and the wording change so a commuter is always sent back to the
commuter portal and an administrator to the administrator portal.

The reset e-mail is delivered with the e-mail backend configured in
``mysite/settings.py``. It defaults to the console backend, so the flow works
out of the box in development without any SMTP credentials.
"""
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy


class SakayPasswordResetView(auth_views.PasswordResetView):
    """Shared behaviour for both password reset portals."""

    template_name = 'auth/password_reset.html'
    email_template_name = 'auth/password_reset_email.txt'
    subject_template_name = 'auth/password_reset_subject.txt'
    portal = 'commuter'
    portal_label = 'Commuter'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['portal'] = self.portal
        context['portal_label'] = self.portal_label
        context['login_url_name'] = f'{self.portal}_login'
        return context

    def get_extra_email_context(self):
        return {'portal': self.portal, 'portal_label': self.portal_label}

    def form_valid(self, form):
        # ``extra_email_context`` is merged into the e-mail template
        # context, which lets the message name the right portal.
        self.extra_email_context = self.get_extra_email_context()
        return super().form_valid(form)


class SakayPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'auth/password_reset_done.html'

    portal = 'commuter'
    portal_label = 'Commuter'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['portal'] = self.portal
        context['portal_label'] = self.portal_label
        context['login_url_name'] = f'{self.portal}_login'
        return context


class SakayPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'auth/password_reset_confirm.html'

    portal = 'commuter'
    portal_label = 'Commuter'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['portal'] = self.portal
        context['portal_label'] = self.portal_label
        context['login_url_name'] = f'{self.portal}_login'
        return context

    def get_success_url(self):
        # ``password_reset_complete`` is role specific.
        return reverse_lazy(f'{self.portal}_password_reset_complete')


class SakayPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'auth/password_reset_complete.html'

    portal = 'commuter'
    portal_label = 'Commuter'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['portal'] = self.portal
        context['portal_label'] = self.portal_label
        context['login_url_name'] = f'{self.portal}_login'
        return context


# ---------------------------------------------------------------------------
# Administrator portal
# ---------------------------------------------------------------------------

class AdminPasswordResetView(SakayPasswordResetView):
    portal = 'admin'
    portal_label = 'Administrator'
    success_url = reverse_lazy('admin_password_reset_done')


class AdminPasswordResetDoneView(SakayPasswordResetDoneView):
    portal = 'admin'
    portal_label = 'Administrator'


class AdminPasswordResetConfirmView(SakayPasswordResetConfirmView):
    portal = 'admin'
    portal_label = 'Administrator'


class AdminPasswordResetCompleteView(SakayPasswordResetCompleteView):
    portal = 'admin'
    portal_label = 'Administrator'


# ---------------------------------------------------------------------------
# Commuter portal
# ---------------------------------------------------------------------------

class CommuterPasswordResetView(SakayPasswordResetView):
    portal = 'commuter'
    portal_label = 'Commuter'
    success_url = reverse_lazy('commuter_password_reset_done')


class CommuterPasswordResetDoneView(SakayPasswordResetDoneView):
    portal = 'commuter'
    portal_label = 'Commuter'


class CommuterPasswordResetConfirmView(SakayPasswordResetConfirmView):
    portal = 'commuter'
    portal_label = 'Commuter'


class CommuterPasswordResetCompleteView(SakayPasswordResetCompleteView):
    portal = 'commuter'
    portal_label = 'Commuter'
