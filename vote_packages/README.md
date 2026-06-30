# BDV3 Vote Packages

Standalone BallsDex voting packages collected into one repo.

## Included packages

- `topgg_notifier`
- `discordlist_notifier`
- `discordbotlist_notifier`
- `botlistme_notifier`
- `vote_pkg`

## Layout

Each package is kept in its own folder under this repository root so it can be installed together through the root `pyproject.toml`.

## Usage

Add the repository to your BallsDex `extra.toml` or install the packages from the repo, then enable the specific packages you want in your bot configuration.
