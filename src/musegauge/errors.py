"""Exception classes and exit codes (spec section 7.3)."""

from __future__ import annotations

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_ENVIRONMENT = 4
EXIT_ALL_FAILED = 5
EXIT_LICENCE = 6
EXIT_PARTIAL = 10
# Not in the spec table: the conventional shell code for an interrupt (SIGINT).
EXIT_INTERRUPTED = 130


class MusegaugeError(Exception):
    """An error that stops the whole run with a fixed exit code."""

    exit_code = 1


class UsageError(MusegaugeError):
    """Wrong command line usage."""

    exit_code = EXIT_USAGE


class InputError(MusegaugeError):
    """A problem with clips, reference, prompts or manifests."""

    exit_code = EXIT_INPUT


class ManifestError(InputError):
    """A plugin manifest or suite file is invalid."""


class FatalEnvironmentError(MusegaugeError):
    """Platform, uv, MUSEGAUGE_HOME or a required system tool is not usable."""

    exit_code = EXIT_ENVIRONMENT


class LicenceRefusal(MusegaugeError):
    """The licence policy (--commercial) refused the run."""

    exit_code = EXIT_LICENCE


class SchemaError(ValueError):
    """A JSON document does not match its schema."""

    def __init__(self, name: str, problems: list[str]):
        self.name = name
        self.problems = problems
        super().__init__(f"{name}: " + "; ".join(problems))


class EnvError(Exception):
    """A plugin environment failed to build. Fails that plugin's metrics only."""

    def __init__(self, message: str, output_tail: str = ""):
        self.output_tail = output_tail
        super().__init__(message)


class NoLockError(Exception):
    """A plugin has no lock file for this platform and --allow-unlocked was not given."""
