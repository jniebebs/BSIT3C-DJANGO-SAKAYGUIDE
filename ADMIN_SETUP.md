# SakayGuide Administrator Setup

SakayGuide uses **Django's built-in authentication and `auth_user` table**.
There is no separate admin account database. An account becomes an
administrator when it is active and has `is_staff = True`. A Django
superuser (`is_superuser = True`) is also an administrator with the additional
right to manage other administrator accounts.

No administrator credentials are stored in this repository.

---

## 1. Open the management dashboard

| URL | Purpose |
| --- | --- |
| `/login/` | Shared login for commuters and administrators |
| `/management/` | Administrator dashboard (staff only) |
| `/dashboard/` | Commuter dashboard |
| `/admin/` | Django's built-in admin (optional, superusers only) |

Sign in with either your **username** or your **e-mail address** plus your
password. Active administrators are redirected to `/management/`; commuter
accounts continue to `/dashboard/`. Signed-in commuters who try to open a
`/management/` page are redirected to their dashboard with an access message.

---

## 2. Create the first administrator

### Option A — Django's standard command (recommended)

From the project root, with the virtual environment active:

```powershell
python manage.py createsuperuser
```

Django prompts for a username, an optional e-mail address, and a password.
The password is hashed immediately and is never written to a file. This
creates a full superuser with access to `/management/` and `/admin/`.

Check the result:

```powershell
python manage.py shell -c "from django.contrib.auth import get_user_model; print(get_user_model().objects.filter(is_superuser=True).values_list('username','email'))"
```

### Option B — secure one-time bootstrap command

The project includes a command that generates a strong random password and
writes it to the gitignored `.env` file:

```powershell
python manage.py create_admin --username sakayadmin --email admin@example.com --first-name Sakay --last-name Admin
```

Useful options:

| Option | Effect |
| --- | --- |
| `--no-superuser` | Create a staff administrator without superuser rights |
| `--no-env` | Do not write `.env`; print the generated password once |
| `--show-password` | Print the password once even when `.env` is written |
| `--noinput` | Fail instead of prompting for a missing username/e-mail |

What the command guarantees:

- It never accepts a password as a command-line argument (avoiding shell
  history and process-list exposure).
- The generated password satisfies Django's password validators.
- Usernames and e-mail addresses are checked case-insensitively and duplicates
  are refused.
- The new account is active, is staff, and is mirrored into SakayGuide's
  `users` table best-effort so audit entries have an actor.
- The initial password is stored **only** in `.env`, which is listed in
  `.gitignore`.

After the first successful sign-in:

1. Change the password in **Management → Users → Edit**.
2. Delete the `INITIAL_ADMIN_*` lines from `.env` (or at minimum
   `INITIAL_ADMIN_PASSWORD`).
3. Keep `.env` out of source control and backups that are shared publicly.

> These `INITIAL_ADMIN_*` values are only a bootstrap record. The application
> does not read them at runtime, and deleting them does not affect login.

---

## 3. Create additional administrators

Sign in as a superuser and open **Management → Users → Add user**.

- A **superuser** can create commuters, administrators, and superusers.
- A non-superuser administrator can create and manage **commuter accounts
  only**. They cannot promote anyone to administrator or edit another
  administrator.
- Self-registration on the public site always creates a commuter account.
  There is no public administrator registration endpoint.

Protective rules enforced by the dashboard:

- An administrator cannot deactivate or demote their own account.
- The last active superuser cannot be deactivated or demoted.
- Deleting accounts is not offered from the dashboard; accounts are
  deactivated instead, preserving search history and audit records.

To promote an existing account with the shell (superuser only):

```powershell
python manage.py shell -c "from django.contrib.auth import get_user_model; u=get_user_model().objects.get(username='NAME'); u.is_staff=True; u.is_superuser=True; u.is_active=True; u.save()"
```

---

## 4. Roles and access control

| Capability | Commuter | Administrator (`is_staff`) | Superuser |
| --- | ---: | ---: | ---: |
| Commuter dashboard and route search | Yes | Yes | Yes |
| `/management/` dashboard | No | Yes | Yes |
| Manage locations, routes, stops, fares, transfers, map | No | Yes | Yes |
| View users, activity, missing data | No | Yes | Yes |
| Create/edit commuter accounts | No | Yes | Yes |
| Create/edit administrator accounts | No | No | Yes |
| Django `/admin/` | No | No* | Yes |

\* Staff accounts may be granted Django model permissions separately, but
SakayGuide's supported administration surface is `/management/`.

Every management view is protected on the server by `administrator_required`
(login + active staff check), not just by hiding navigation links. All
mutations use POST, CSRF protection, server-side validation, and confirmation
dialogs. Login, logout, and management changes are recorded in the
SakayGuide audit log when that database is available.

---

## 5. Password and session security

- Passwords are hashed by Django; no plaintext password is stored in the
  application database.
- The login form supports show/hide password and protects against repeated
  failed attempts with a temporary lockout.
- Administrators are redirected to `/management/`; commuters are redirected to
  `/dashboard/`.
- Logout requires a POST request and clears the session.
- Use HTTPS and set `DJANGO_DEBUG=False` in production, with a strong
  `SECRET_KEY` supplied through the environment.
- Never commit `.env`, database dumps containing password hashes, or terminal
  transcripts that show a bootstrap password.

---

## 6. Google Maps (optional)

The map pages work without a key by showing a manual coordinate fallback. To
enable interactive maps and the location picker, add a restricted browser key
to `.env`:

```env
GOOGLE_MAPS_API_KEY=your-restricted-key
```

See `GOOGLE_MAPS_SETUP.md` for API restrictions and referrer settings.

---

## 7. Troubleshooting

**Login says the credentials are invalid**

- Confirm the account is active: `is_active = True`.
- Administrators also need `is_staff = True`.
- Email login is case-insensitive, but the password is exact.

**Administrator is sent back to the commuter dashboard**

The account is probably missing `is_staff`. Check with:

```powershell
python manage.py shell -c "from django.contrib.auth import get_user_model; print(list(get_user_model().objects.filter(is_staff=True).values_list('username','is_active','is_superuser')))"
```

**`create_admin` reports a duplicate**

An account already uses that username or e-mail. Use the management dashboard
to edit the existing account, or choose a different username/e-mail. The
command intentionally never overwrites an account.

**The last superuser cannot be deactivated**

This is intentional. Create or promote another superuser first.
