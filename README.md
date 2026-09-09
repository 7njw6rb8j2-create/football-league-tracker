# Football League Tracker

Tracks Wrexham, Stockport County, Chelsea and Barnet using BBC Sport league tables.

The GitHub Actions workflow scrapes the BBC table every 15 minutes and deploys the static site to GitHub Pages.

## GitHub setup

1. Create a repository.
2. Upload the repository files, preserving the folders:
   - `site/index.html`
   - `site/data.json`
   - `scraper.py`
   - `requirements.txt`
   - `.github/workflows/update-and-deploy.yml`
3. In **Settings → Pages**, set **Source** to **GitHub Actions**.
4. Open **Actions → Update and deploy football tracker** and choose **Run workflow** once.
5. GitHub Pages will provide the site URL after the deployment completes.
