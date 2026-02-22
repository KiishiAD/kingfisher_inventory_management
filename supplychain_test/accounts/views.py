import secrets

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .forms import InviteUserForm, OrganizationSetupForm, OrganizationSignupForm
from .models import Organization, OrganizationMembership

User = get_user_model()


def _active_organization(user, request=None):
    memberships = user.organization_memberships.select_related("organization")
    if request:
        org_id = request.session.get("active_organization_id")
        if org_id:
            current = memberships.filter(organization_id=org_id).first()
            if current:
                return current.organization
    membership = memberships.order_by("created_at").first()
    if membership and request:
        request.session["active_organization_id"] = membership.organization_id
    return membership.organization if membership else None


def _user_can_invite(user, organization):
    if not organization:
        return False
    membership = user.organization_memberships.filter(organization=organization).first()
    return bool(membership and membership.role in {OrganizationMembership.OWNER, OrganizationMembership.ADMIN})


def _send_set_password_email(request, user, to_email):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_path = reverse("password_reset_confirm", kwargs={"uidb64": uidb64, "token": token})

    if not settings.APP_BASE_URL:
        raise RuntimeError("APP_BASE_URL is not set; refusing to generate localhost links in invite emails.")

    reset_url = f"{settings.APP_BASE_URL}{reset_path}"

    sent = send_mail(
        subject="Set up your Kingfisher account",
        message=f"Set your password here:\n{reset_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        fail_silently=False,
    )
    return sent


def auth_landing(request):
    login_form = AuthenticationForm(request=request, data=request.POST or None)
    if request.method == "POST" and login_form.is_valid():
        login(request, login_form.get_user())
        return redirect(settings.LOGIN_REDIRECT_URL)
    return render(request, "registration/login.html", {"form": login_form})


def signup(request):
    form = OrganizationSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.create_user(
            username=form.cleaned_data["email"],
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        organization = Organization.objects.create(name=form.cleaned_data["organization_name"])
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrganizationMembership.OWNER,
        )
        login(request, user)
        request.session["active_organization_id"] = organization.id
        return redirect(settings.LOGIN_REDIRECT_URL)
    return render(request, "accounts/signup.html", {"form": form})


def google_start(request):
    if not all([
        getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", ""),
        getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", ""),
    ]):
        messages.warning(request, "Google SSO is not configured yet. Please use email sign up.")
        return redirect("accounts:signup")

    state = secrets.token_urlsafe(24)
    request.session["google_oauth_state"] = state
    redirect_uri = request.build_absolute_uri(reverse("accounts:google_callback"))
    scope = "openid email profile"
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_OAUTH_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code&scope={scope}&state={state}&prompt=select_account"
    )
    return redirect(auth_url)


def google_callback(request):
    if request.GET.get("state") != request.session.get("google_oauth_state"):
        messages.error(request, "Invalid Google authentication state.")
        return redirect("login")

    code = request.GET.get("code")
    if not code:
        messages.error(request, "Google sign in failed.")
        return redirect("login")

    redirect_uri = request.build_absolute_uri(reverse("accounts:google_callback"))
    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if not token_response.ok:
        messages.error(request, "Unable to authenticate with Google.")
        return redirect("login")

    access_token = token_response.json().get("access_token")
    userinfo_response = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not userinfo_response.ok:
        messages.error(request, "Unable to fetch profile from Google.")
        return redirect("login")

    email = userinfo_response.json().get("email", "").strip().lower()
    if not email:
        messages.error(request, "Google account did not provide an email.")
        return redirect("login")

    user = User.objects.filter(email__iexact=email).first()
    created = False
    if not user:
        user = User.objects.create(username=email, email=email, is_active=True)
        created = True
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])

    login(request, user)

    if not user.organization_memberships.exists():
        return redirect("accounts:organization_setup")

    organization = _active_organization(user, request)
    if organization:
        request.session["active_organization_id"] = organization.id
    return redirect(settings.LOGIN_REDIRECT_URL)


@login_required
def organization_setup(request):
    if request.user.organization_memberships.exists():
        return redirect(settings.LOGIN_REDIRECT_URL)

    form = OrganizationSetupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        organization = Organization.objects.create(name=form.cleaned_data["organization_name"])
        OrganizationMembership.objects.create(
            user=request.user,
            organization=organization,
            role=OrganizationMembership.OWNER,
        )
        request.session["active_organization_id"] = organization.id
        return redirect(settings.LOGIN_REDIRECT_URL)

    return render(request, "accounts/organization_setup.html", {"form": form})


@login_required
def invite_user(request):
    organization = _active_organization(request.user, request)
    if not _user_can_invite(request.user, organization):
        messages.error(request, "You do not have permission to invite users for this organization.")
        return redirect("supplychain:dashboard")

    if request.method == "POST":
        form = InviteUserForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            groups = form.cleaned_data["groups"]

            existing = User.objects.filter(email__iexact=email).first()
            if existing:
                user = existing
                if groups:
                    user.groups.set(groups)
            else:
                user = User.objects.create(
                    username=email,
                    email=email,
                    is_active=True,
                )
                user.set_unusable_password()
                user.save()
                if groups:
                    user.groups.set(groups)

            OrganizationMembership.objects.get_or_create(
                user=user,
                organization=organization,
                defaults={"role": OrganizationMembership.MEMBER},
            )
            _send_set_password_email(request, user, email)
            return redirect("accounts:invite_done")
    else:
        form = InviteUserForm()

    return render(request, "accounts/invite_user.html", {"form": form, "organization": organization})


@login_required
def invite_done(request):
    return render(request, "accounts/invite_done.html")
