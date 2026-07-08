# Public Readiness Sweep Checklist

Work through this checklist **before** flipping the GitHub repository from
private to public. Check off each item as you complete it.

## Secrets and credentials

- [ ] Run `gitleaks detect --source . -v` locally and confirm zero findings.
- [ ] Run `gitleaks detect --source . -v --no-git` to scan the working tree.
- [ ] Review `.env.example` — confirm it contains only placeholder values, no
      real credentials, API keys, or tokens.
- [ ] Audit all source files (`rg -i 'password|secret|key|token|api.key'`) for
      hardcoded secrets, internal hostnames, or non-public URLs.
- [ ] Scan commit messages for leaked sensitive info:
      ```bash
      git log --all --oneline | grep -iE 'password|secret|key|token|credential'
      ```

## File hygiene

- [ ] Review `.gitignore` — confirm build artifacts (`dist/`, `.turbo/`),
      database files (`*.db`), IDE configs (`.vscode/`, `.idea/`), and
      environment files (`.env`, `.env.local`) are all excluded.
- [ ] Verify no `_local/` directories were accidentally committed
      (`git ls-files _local/` should return nothing).
- [ ] Confirm no `.env` files with real values are tracked
      (`git ls-files '*.env'` — only `.env.example` should appear).
- [ ] Check for large binary files that shouldn't be public:
      ```bash
      git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' | awk '/^blob/ {print $2, $3}' | sort -rn | head -20
      ```

## Licensing and attribution

- [ ] `LICENSE` file is present at repo root with the correct license (GPL 3.0).
- [ ] All source files that need copyright headers have them.
- [ ] Third-party dependency licenses are compatible with GPL 3.0.
- [ ] No copied code from other projects without proper attribution.

## Dependencies

- [ ] All dependencies are publicly available (spec repo, mule repo, npm
      packages). Private/internal package registries are not in use.
- [ ] `pnpm-lock.yaml` does not reference any private registries or
      authenticated sources.
- [ ] The spec repo (`nhl-legacy-roster-spec`) and mule repo
      (`nhl-db-studio-mule`) are also public (or will be made public).

## Game assets

- [ ] No copyrighted game assets are committed beyond the explicit exception in
      `AGENTS.md` for `tests/fixtures/xbox/roster.bin` (the 2026 trade deadline
      update, used as a small canonical test fixture).
- [ ] No executable game files, DLLs, or other proprietary binaries are present
      in the repository.
- [ ] No upstream source code from Modding Studio, `nhl-database-studio`, or
      similar tools is committed.

## Documentation

- [ ] README is complete — a stranger can understand what the project does, how
      to set it up, and how to contribute.
- [ ] `AI_USAGE.md` exists and accurately describes the project's AI usage.
- [ ] `AGENTS.md` does not contain any internal-only references or secrets.
- [ ] Architecture decisions and trade-offs are documented or discoverable.

## After going public

- [ ] Set up branch protection rules on `main`:
  - Require pull request reviews before merging.
  - Require status checks (CI) to pass before merging.
  - Require branches to be up to date before merging.
  - Do not allow bypassing the above settings.
- [ ] Enable GitHub security features:
  - **Secret scanning** — enable push protection to block commits containing
    detected secrets.
  - **Private vulnerability reporting** — allow security researchers to
    privately report vulnerabilities.
  - **Dependabot alerts** — enable for vulnerable dependencies.
- [ ] Add a `SECURITY.md` with instructions for reporting security issues.
- [ ] Update the repository description, website URL, and topics on GitHub.
- [ ] Announce the public release to relevant communities (Discord, Reddit, etc.).
