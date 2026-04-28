# Project rules for Claude

## Git workflow

**Never push directly to `main`.** Even when the remote accepts the push (bypass rights exist on this repo), the branch is protected and the maintainer expects all changes to go through pull requests.

When asked to "commit and push", interpret that as:

1. Create a feature branch (`git checkout -b <short-descriptive-name>`).
2. Commit the changes there.
3. Push the branch with `-u` to set upstream.
4. Open a PR with `gh pr create` and return the PR URL.

If you're already sitting on `main` with local commits when this comes up, move them to a new branch before pushing — do not push `main` directly. Reset `main` to `origin/main` only after the new branch is in place and pushed.
