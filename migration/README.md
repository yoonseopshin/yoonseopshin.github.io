# Migration from the Minimal Mistakes blog (2026-10-31)

Source: the previous `yoonseopshin/yoonseopshin.github.io` repository (a fork of `haileyjohj/devinlife.github.io`), last content change 2021-10-02.

## What changed in the posts

Body text is identical except:

| Post | Change | Why |
|---|---|---|
| 62 (`vue-drf-todo-app-frontend`) | `{{ task.description }}` wrapped in `{% raw %}` (2 places) | Liquid removed it from the code block on the old site |
| 78 (`github-actions-include-gitignored-file`) | `${{ secrets.FIREBASE_SECRET }}` wrapped in `{% raw %}` | Same; the old site showed `FIREBASE_SECRET: $` |
| 78 | `78-1.png` → `78-1.jpg` | Only `78-1.jpg` was ever committed; the image was missing |
| 34, 48 (2), 62 | Links to other posts on this blog, `https://sys09270883.github.io/<cat>/<n>/` → `/posts/<slug>/` | That host no longer exists |

Front matter:

- `excerpt` → `description`, `use_math` → `math`, `toc_sticky` dropped.
- `toc: false` where the old post had no table of contents (Chirpy shows one by default).
- `lang: ko` so the page declares Korean.
- `redirect_from:` with the old URL.
- Tags that differed only in case were merged: `Android`→`android`, `Web`→`web`, `Django`→`django`, `Python`→`python` (6 posts). They produced the same tag page.

Theme syntax kept as is: kramdown attributes (`{: .align-center width="80%"}`), `<details><div markdown="1">`, `$`/`$$` math. `.align-center` is recreated in `assets/css/jekyll-theme-chirpy.scss`.

## Old URL → new URL

| Old | New |
|---|---|
| `/<category>/<n>/` (80 posts) | `/posts/<slug>/` |
| `/page2/` … `/page16/` | `/` |
| `/year-archive/` | `/archives/` |
| `/categories/`, `/tags/`, `/`, `/feed.xml`, `/sitemap.xml`, `/robots.txt` | same path |

## Not carried over

Disqus comments (`yoonseopshin`), Universal Analytics `UA-155863161-1` (Google retired UA in 2023), AdSense scripts, Staticman, Lunr search, the Minimal Mistakes theme files, the title "Yoonseop's Corgaxm", and files from the original fork author (devinlife): their AdSense include and `cmd.sh`.

Kept: Google Search Console verification (`google_site_verification` in `_config.yml` and `google3a62db448687fdd8.html`), the Naver verification file, and `ads.txt` for the existing AdSense publisher ID.

## Known issues inherited from the old posts

- Post 10 (`shortest-path-algorithms`) embeds two images from i.imgur.com that do not load in browsers on either site.
- About 20 links point to `github.com/sys09270883/...` (the old GitHub user name) and return 404. Some of those repositories are private now. Left unchanged.
- External links that use `http://` (8) are left unchanged; CI runs htmlproofer with `--no-enforce-https` for that reason.
