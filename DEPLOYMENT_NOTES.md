# Static Deployment Notes

The deployable site is the `app/` folder. It contains only static files:

- `index.html`
- `styles.css`
- `app.js`
- `data/shanghai_h3_seed_min.json`
- `data/project_manifest.json`

Recommended deployment path:

1. Push the `shanghai_15mc` folder to GitHub.
2. Deploy `app/` as the static publish directory on Netlify, Vercel, GitHub Pages, or Cloudflare Pages.
3. Enable gzip or Brotli compression on the host. The app payload is large as raw JSON but compresses well.
4. Open the deployed URL on desktop and mobile, then verify the map, mode toggles, layer toggles, hex click panel, recommender sliders, and data transparency section.

If the host asks for a build command, leave it empty. This prototype does not require a JavaScript build step.
