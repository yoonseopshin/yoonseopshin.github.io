# yoonseopshin.github.io

Personal blog. Jekyll with the [Chirpy](https://github.com/cotes2020/jekyll-theme-chirpy) theme, built and deployed by GitHub Actions (`.github/workflows/pages-deploy.yml`).

## Local build

```sh
bundle install
bundle exec jekyll serve          # http://127.0.0.1:4000
JEKYLL_ENV=production bundle exec jekyll build
python3 tools/verify_urls.py _site
```

## URLs

- Posts: `/posts/<slug>/`. The slug comes from the file name `_posts/YYYY-MM-DD-<slug>.md`. Lowercase English, hyphens, no dates or numbers that are not part of the subject.
- Every URL ends with a slash.
- Tags `/tags/<tag>/`, categories `/categories/<category>/`, archive `/archives/`, pages `/page/<n>/`.

## Posts from the old blog

The 80 posts from 2019–2021 came from the previous Minimal Mistakes blog. Their text is unchanged; only front matter was adapted (`excerpt` became `description`, `use_math` became `math`). The full list of changes and why is in `migration/`.

Old URLs such as `/ps/1/` or `/parallel%20programming/72/` are redirect pages made by `jekyll-redirect-from` (`redirect_from` in each post). GitHub Pages cannot send a 301, so each redirect page has a meta refresh, `rel=canonical` to the new URL and `noindex`.

- `migration/baseline-urls.tsv`: every URL the old site served, taken from its sitemap and a crawl on 2026-10-31.
- `migration/slugs.tsv`: old post number to new slug.
- `tools/verify_urls.py`: checks old URLs redirect in one hop to the right page, the sitemap lists only real pages, and no internal link is broken. CI runs it.
- `tools/verify_content.py`: compares post bodies with the old repository.

Other paths under this domain belong to other repositories (for example `/static-hosting/`). Do not add a top-level directory with the same name here.

## Two languages

English is the default. A post written in both languages is two files that share `ref`:

| | English | Korean |
|---|---|---|
| `lang` | `en` | `ko-KR` (Korean UI) |
| `permalink` | `/posts/<slug>/` | `/ko/posts/<slug>/` |
| `hidden` | — | `true` (keeps it off the English front page) |

- `_includes/metadata-hook.html` writes `hreflang` en / ko / x-default (→ English) on both pages; each page keeps its own canonical.
- `_includes/lang-switch.html` shows a link to the other version. On the English page a banner offers the Korean version when the browser's first language is Korean. Nothing redirects automatically.
- `/ko/` (`_tabs/ko.md`) lists Korean posts, including the 2019–2021 posts. `/ko/feed.xml` is the Korean feed.
- `tools/verify_urls.py` fails CI if an hreflang set is not reciprocal or a page loses its self canonical.
