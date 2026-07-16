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
* Head to your bot on topgg and then click edit
<img width="1044" height="485" alt="image" src="https://github.com/user-attachments/assets/f813d0dd-3946-40d4-88b9-1f1bf1d8a96a" />

* Click integrations and API
<img width="1417" height="336" alt="image" src="https://github.com/user-attachments/assets/82de24df-00f9-45ce-835b-a360b543805a" />

* Create a new webhook. Your webhook should be your admin panel link with /topgg/webhook at the end (E.G. https://drwhodex.ballsdex.com/topgg/webhook). Label it whatever you want and tick vote created
<img width="544" height="437" alt="image" src="https://github.com/user-attachments/assets/d6d5f7fe-e56b-4a17-9556-da076aee95e9" />

* Copy the webhook secret and paste it into the topgg configuration in the admin panel
<img width="768" height="326" alt="image" src="https://github.com/user-attachments/assets/8330d804-233b-4f59-a4a1-e06dc357150a" />

* Just fill in the other slots you need to fill in
<img width="1387" height="705" alt="image" src="https://github.com/user-attachments/assets/f86acf31-f898-47e4-b0aa-8f9965976dd1" />

2. DiscordList

3. DiscordBotList
