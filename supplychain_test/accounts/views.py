from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .forms import InviteUserForm

User = get_user_model()

def superuser_required(u):
    return u.is_authenticated and u.is_superuser

@login_required
@user_passes_test(superuser_required)
def invite_user(request):
    if request.method == "POST":
        form = InviteUserForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            groups = form.cleaned_data["groups"]

            if User.objects.filter(email__iexact=email).exists():
                form.add_error("email", "User already exists.")
            else:
                user = User.objects.create(
                    username=email,   # simplest with default User
                    email=email,
                    is_active=True,
                )
                user.set_unusable_password()
                user.save()

                if groups:
                    user.groups.set(groups)

                uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)

                reset_path = reverse("password_reset_confirm", kwargs={"uidb64": uidb64, "token": token})
                reset_url = request.build_absolute_uri(reset_path)

                send_mail(
                    subject="Set up your Kingfisher account",
                    message=f"Set your password here:\n{reset_url}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                )

                return redirect("accounts:invite_done")
    else:
        form = InviteUserForm()

    return render(request, "accounts/invite_user.html", {"form": form})

@login_required
@user_passes_test(superuser_required)
def invite_done(request):
    return render(request, "accounts/invite_done.html")
