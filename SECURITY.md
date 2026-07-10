# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Instead, report vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/bmir-radx/radx-data-dictionary-specification/security/advisories/new)
(the **Security** tab → **Report a vulnerability**), or by email to
**horridge@stanford.edu**.

Please include enough detail to reproduce the issue — the affected package,
version or commit, and a minimal example. We will acknowledge your report and
keep you informed as we investigate and fix it.

## Scope

These packages parse data-dictionary files (CSV, LinkML YAML, REDCap exports)
and render output (HTML, JSON). Reports of parser crashes, unsafe deserialization,
resource-exhaustion on crafted input, or unsafe output rendering (e.g. HTML
injection via the printer) are all in scope.

## Supported versions

This project releases from `main`; fixes are applied there and published as a
new release. Please upgrade to the latest release before reporting, and pin to a
released tag in production.
