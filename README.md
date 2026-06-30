# BDV3-Vote-Packages
Vote package for different voting websites for your Dex instance.

## Included packages

- `topgg_notifier`
- `discordlist_notifier`
- `discordbotlist_notifier`
- `botlistme_notifier`
- `vote_links`

## Installation

1. Add these packages to your BallsDex `config/extra.toml`:
```toml
[[ballsdex.packages]]
location = "git+https://github.com/CharGoon26/BDV3-Vote-Packages"
path = "topgg_notifier"
enabled = true
editable = false

[[ballsdex.packages]]
location = "git+https://github.com/CharGoon26/BDV3-Vote-Packages"
path = "discordlist_notifier"
enabled = true
editable = false

[[ballsdex.packages]]
location = "git+https://github.com/CharGoon26/BDV3-Vote-Packages"
path = "discordbotlist_notifier"
enabled = true
editable = false

[[ballsdex.packages]]
location = "git+https://github.com/CharGoon26/BDV3-Vote-Packages"
path = "botlistme_notifier"
enabled = true
editable = false

[[ballsdex.packages]]
location = "git+https://github.com/CharGoon26/BDV3-Vote-Packages"
path = "vote_links"
enabled = true
editable = false
```

2. Then add these webhook routes in `admin_panel/admin_panel/urls.py`:

```python
path("topgg/", include("topgg_notifier.urls")),
path("discordlist/", include("discordlist_notifier.urls")),
path("discordbotlist/", include("discordbotlist_notifier.urls")),
path("botlistme/", include("botlistme_notifier.urls")),
```

## Update

After installing or changing the package list:

```bash
docker compose build
docker compose run --rm migration
docker compose up -d
```

## How to use

1. Top.gg

2. DiscordList

3. DiscordBotList
