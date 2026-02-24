# Accounts App

## Purpose
Handles account onboarding, organization ownership/membership, and invite-based user creation.

## URLs (`accounts/urls.py`)
- `/accounts/signup/`
- `/accounts/google/start/`
- `/accounts/google/callback/`
- `/accounts/organization/setup/`
- `/accounts/invite/`
- `/accounts/invite/done/`

## Models
- `Organization`: unique organization name.
- `OrganizationMembership`: FK user + FK organization + role + uniqueness constraint.

## Forms
- `OrganizationSignupForm`: org + owner account creation (with password validation).
- `OrganizationSetupForm`: SSO-first users create org after first login.
- `InviteUserForm`: invite email + optional group assignment.

## View behavior highlights
- `auth_landing`: wraps `AuthenticationForm` on custom login template.
- `signup`: creates user + org + OWNER membership and logs user in.
- `google_start/google_callback`: full OAuth code flow with CSRF-like `state`.
- `organization_setup`: enforced for users without org memberships.
- `invite_user`: OWNER/ADMIN-only invite path, creates membership and set-password mail.

## Templates
- `accounts/signup.html`
- `accounts/organization_setup.html`
- `accounts/invite_user.html`
- `accounts/invite_done.html`

## How it interacts with supplychain
- Supplychain dashboard scopes requisition counters by active organization membership.
- Session key `active_organization_id` is set in accounts flows and reused downstream.
