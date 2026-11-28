"""Tests for the MFA code generation."""

import pytest

from ocma import connect

# Example secret from the README, cut to the tested lengths.
SECRET = "NBSWY3DPEB3W64TMMQ"


def test_microsoft_length_secret_accepted() -> None:
    """Accept the 16 character (80 bit) secrets Microsoft issues."""
    code = connect.get_mfa_code(SECRET[:16])
    assert len(code) == 6
    assert code.isdigit()


def test_too_short_secret_rejected() -> None:
    """Reject secrets shorter than 80 bits."""
    with pytest.raises(ValueError, match="at least 80 bits"):
        connect.get_mfa_code(SECRET[:8])
