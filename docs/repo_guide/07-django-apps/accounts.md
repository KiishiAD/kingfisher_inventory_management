# Accounts App

## What this app is for
The `accounts` app handles who can log in, how organizations are created, and who is allowed to invite teammates.

## When users touch this app
- New company signup
- Login/logout and password reset routes
- Google sign-in
- Organization setup for first-time SSO users
- Team invite flow

## Step-by-step flow
First, user signs up or signs in.
Then the app ensures the user belongs to an organization.
Then session stores an active organization id.
Because invites are organization-scoped, only owner/admin can invite users.

## URLs
- `/accounts/signup/`
- `/accounts/google/start/`
- `/accounts/google/callback/`
- `/accounts/organization/setup/`
- `/accounts/invite/`
- `/accounts/invite/done/`

## Core models
- `Organization`
- `OrganizationMembership`

## Templates used
- `accounts/signup.html`
- `accounts/organization_setup.html`
- `accounts/invite_user.html`
- `accounts/invite_done.html`

## Where in code
- URL map: `supplychain_test/accounts/urls.py::urlpatterns`
- Organization helper: `supplychain_test/accounts/views.py::_active_organization`
- Invite authorization: `supplychain_test/accounts/views.py::_user_can_invite`
- Signup flow: `supplychain_test/accounts/views.py::signup`
- Google OAuth flow: `supplychain_test/accounts/views.py::google_start`, `supplychain_test/accounts/views.py::google_callback`
- Models: `supplychain_test/accounts/models.py::OrganizationMembership`
