from django import forms
from django.core.validators import RegexValidator

from .models import User

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


class AddressForm(forms.Form):
    """Validate address fields before saving an address."""

    full_name = forms.CharField(
        min_length=3,
        max_length=100,
        validators=[
            RegexValidator(
                regex=r"\A[A-Za-z ]+\Z",
                message="Full name can contain only letters and spaces.",
            )
        ],
        error_messages={
            "required": "Full name is required.",
            "min_length": "Full name must contain at least 3 characters.",
            "max_length": "Full name cannot exceed 100 characters.",
        },
    )

    phone = forms.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"\A[6-9][0-9]{9}\Z",
                message=(
                    "Phone number must contain exactly 10 digits "
                    "and start with 6, 7, 8, or 9."
                ),
            )
        ],
        error_messages={
            "required": "Phone number is required.",
        },
    )

    address_line1 = forms.CharField(
        min_length=5,
        max_length=255,
        error_messages={
            "required": "Address line 1 is required.",
            "min_length": (
                "Address line 1 must contain at least 5 characters."
            ),
            "max_length": "Address line 1 cannot exceed 255 characters.",
        },
    )

    address_line2 = forms.CharField(
        max_length=255,
        required=False,
        error_messages={
            "max_length": "Address line 2 cannot exceed 255 characters.",
        },
    )

    landmark = forms.CharField(
        max_length=100,
        required=False,
        error_messages={
            "max_length": "Landmark cannot exceed 100 characters.",
        },
    )

    city = forms.CharField(
        min_length=2,
        max_length=100,
        validators=[
            RegexValidator(
                regex=r"\A[A-Za-z ]+\Z",
                message="City can contain only letters and spaces.",
            )
        ],
        error_messages={
            "required": "City is required.",
            "min_length": "City must contain at least 2 characters.",
            "max_length": "City cannot exceed 100 characters.",
        },
    )

    state = forms.CharField(
        min_length=2,
        max_length=100,
        validators=[
            RegexValidator(
                regex=r"\A[A-Za-z ]+\Z",
                message="State can contain only letters and spaces.",
            )
        ],
        error_messages={
            "required": "State is required.",
            "min_length": "State must contain at least 2 characters.",
            "max_length": "State cannot exceed 100 characters.",
        },
    )

    postal_code = forms.CharField(
        max_length=6,
        validators=[
            RegexValidator(
                regex=r"\A[1-9][0-9]{5}\Z",
                message=(
                    "Postal code must contain exactly 6 digits "
                    "and cannot start with 0."
                ),
            )
        ],
        error_messages={
            "required": "Postal code is required.",
        },
    )

    address_type = forms.ChoiceField(
        choices=[
            ("home", "Home"),
            ("work", "Work"),
        ],
        required=False,
        initial="home",
        error_messages={
            "invalid_choice": "Invalid address type.",
        },
    )

    is_default = forms.BooleanField(required=False)

    # Clean the address type, defaulting to 'home' if none was selected.
    def clean_address_type(self):
        """Use home when no address type is submitted."""
        return self.cleaned_data.get("address_type") or "home"


class ProfileForm(forms.Form):
    """Validate username, phone number, and email during profile updates."""

    username = forms.CharField(
        max_length=150,
        validators=[
            RegexValidator(
                regex=r"\A[A-Za-z0-9]+\Z",
                message="Username must contain only letters and numbers.",
            )
        ],
        error_messages={
            "required": "Username is required.",
            "max_length": "Username cannot exceed 150 characters.",
        },
    )

    phone = forms.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"\A[0-9]{10}\Z",
                message="Phone number must contain exactly 10 digits.",
            )
        ],
        error_messages={
            "required": "Phone number is required.",
        },
    )

    email = forms.EmailField(
        max_length=254,
        error_messages={
            "required": "Email is required.",
            "invalid": "Enter a valid email address.",
        },
    )

    # Initialize the profile form and store the current user reference.
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    # Ensure the updated username is unique and not taken by another user.
    def clean_username(self):
        """Prevent duplicate usernames, ignoring letter case."""
        username = self.cleaned_data["username"].strip()

        existing_users = User.objects.filter(
            username__iexact=username
        )

        if self.user:
            existing_users = existing_users.exclude(
                id=self.user.id
            )

        if existing_users.exists():
            raise forms.ValidationError(
                "This username is already taken."
            )

        return username

    # Ensure the updated email address is unique across other user accounts.
    def clean_email(self):
        """Prevent duplicate email addresses, ignoring letter case."""
        email = self.cleaned_data["email"].strip()

        existing_users = User.objects.filter(
            email__iexact=email
        )

        if self.user:
            existing_users = existing_users.exclude(
                id=self.user.id
            )

        if existing_users.exists():
            raise forms.ValidationError(
                "This email has already been taken."
            )

        return email


class SignupForm(forms.Form):
    """Validate registration fields before starting OTP verification."""

    username = forms.CharField(
        min_length=3,
        max_length=150,
        validators=[
            RegexValidator(
                regex=r"\A[A-Za-z ]+\Z",
                message="Name can contain only letters and spaces.",
            )
        ],
        error_messages={
            "required": "Username is required.",
            "min_length": "Username must contain at least 3 characters.",
            "max_length": "Username cannot exceed 150 characters.",
        },
    )

    email = forms.EmailField(
        max_length=254,
        error_messages={
            "required": "Email is required.",
            "invalid": "Please enter a valid email address.",
        },
    )

    phone = forms.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"\A[6-9][0-9]{9}\Z",
                message="Please enter a valid 10-digit phone number.",
            )
        ],
        error_messages={
            "required": "Phone number is required.",
        },
    )

    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput,
        validators=[
            RegexValidator(
                regex=r"\A(?=.*[A-Z])(?=.*[a-z])(?=.*\d)"
                      r"(?=.*[@$!%*?&]).{8,}\Z",
                message=(
            "Password must contain at least 8 characters, "
            "one uppercase letter, one lowercase letter, "
            "one number, and one special character (@$!%%*?&)."
        )
            )
        ],
        error_messages={
            "required": "Password is required.",
        },
    )

    confirm_password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput,
        error_messages={
            "required": "Please confirm your password.",
        },
    )

    # Check that the username chosen during signup does not already exist.
    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Username already exists.")

        return username

    # Check that the email address entered during signup is not already registered.
    def clean_email(self):
        email = self.cleaned_data["email"].strip()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email already exists.")

        return email

    # Validate the signup password against Django password security validators.
    def clean_password(self):
        password = self.cleaned_data["password"]

        try:
            validate_password(password)
        except DjangoValidationError as error:
            raise forms.ValidationError(error.messages)

        return password

    # Ensure that the password and confirmation password match.
    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if (
            password
            and confirm_password
            and password != confirm_password
        ):
            self.add_error(
                "confirm_password",
                "Passwords do not match.",
            )

        return cleaned_data

class ForgotPasswordForm(forms.Form):
    """Validate the email entered for password recovery."""

    email = forms.EmailField(
        max_length=254,
        error_messages={
            "required": "Email is required.",
            "invalid": "Please enter a valid email address.",
        },
    )



class ResetPasswordForm(forms.Form):
    """Validate a new password and its confirmation."""

    new_password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput,
        error_messages={
            "required": "Both password fields are required.",
        },
    )

    confirm_password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput,
        error_messages={
            "required": "Both password fields are required.",
        },
    )

    # Validate the new password against Django security validators.
    def clean_new_password(self):
        from django.contrib.auth.password_validation import validate_password

        password = self.cleaned_data["new_password"]
        validate_password(password)
        return password

    # Verify that the new password and confirmation password match.
    def clean(self):
        cleaned_data = super().clean()

        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if (
            new_password
            and confirm_password
            and new_password != confirm_password
        ):
            self.add_error(
                "confirm_password",
                "Passwords do not match.",
            )

        return cleaned_data

from django.contrib.auth.password_validation import validate_password


class SetNewPasswordForm(forms.Form):
    """Validate a new password and its confirmation."""

    new_password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput,
        error_messages={
            "required": "New password is required.",
        },
    )

    confirm_password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput,
        error_messages={
            "required": "Confirm password is required.",
        },
    )

    # Initialize the set-new-password form with the target user.
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    # Validate the new password against password validators for this user.
    def clean_new_password(self):
        password = self.cleaned_data["new_password"]

        # Apply the password validators configured in Django settings.
        validate_password(password, user=self.user)

        return password

    # Ensure the new password and confirmation password match.
    def clean(self):
        cleaned_data = super().clean()

        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if (
            new_password
            and confirm_password
            and new_password != confirm_password
        ):
            self.add_error(
                "confirm_password",
                "Passwords do not match.",
            )

        return cleaned_data