# GitHub Pages Setup

This repository includes a static project page in `docs/`.

Expected public URL:

```text
https://Haoyi-Zhang.github.io/WatermarkScope/
```

## Recommended Deployment

Use the included GitHub Actions workflow:

1. Push this repository to GitHub.
2. Open **Settings -> Pages**.
3. Set **Source** to **GitHub Actions**.
4. Open **Actions -> Deploy GitHub Pages**.
5. Run the workflow manually, or push to `main`.

The workflow uploads `docs/` directly as the Pages artifact, so no build step is
required.

## Branch Deployment Alternative

If GitHub Actions is unavailable:

1. Open **Settings -> Pages**.
2. Set **Source** to **Deploy from a branch**.
3. Select branch `main`.
4. Select folder `/docs`.
5. Save.

The page is intentionally static. It links back to the repository for claim
boundaries, traceability, result manifests, and the viva check script.
