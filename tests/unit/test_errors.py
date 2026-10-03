"""Exit codes (spec section 7.3)."""

from musegauge import errors


def test_exit_code_values():
    assert (errors.EXIT_OK, errors.EXIT_USAGE, errors.EXIT_INPUT, errors.EXIT_ENVIRONMENT,
            errors.EXIT_ALL_FAILED, errors.EXIT_LICENCE, errors.EXIT_PARTIAL) == (0, 2, 3, 4, 5, 6, 10)


def test_exception_exit_codes():
    assert errors.UsageError("x").exit_code == 2
    assert errors.InputError("x").exit_code == 3
    assert errors.ManifestError("x").exit_code == 3
    assert errors.FatalEnvironmentError("x").exit_code == 4
    assert errors.LicenceRefusal("x").exit_code == 6
