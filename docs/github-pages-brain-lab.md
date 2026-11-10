# Host P37 Brain Lab on GitHub Pages

P37 Brain Lab is a static MuJoCo WebAssembly website. Visitors can select the
actual Unitree G1, Unitree Go2 and Franka Panda simulation models and interact
with them entirely in their browsers. No NVIDIA GPU, application server, or
Cloudflare credentials are required.

The site **does not yet include a qualified P37 walking policy**. The model
viewer is real physics; training artifacts and P37 policy claims have their
own separate validation gates.

## Intended public address

`https://ontosrobotics.github.io/P37-Neuro/`

The URL above is a **target**, not proof that Pages is live. Check GitHub
Actions and the URL after the first successful deployment.

## One-time GitHub Pages setup

1. Go to [P37-Neuro → Settings → Pages](https://github.com/OntosRobotics/P37-Neuro/settings/pages).
2. In **Build and deployment**, set **Source** to **GitHub Actions**. Do not
   choose `main /docs` or `gh-pages`; this project generates an application
   and its WASM/assets in the Pages CI workflow.
3. Confirm the organization permits public GitHub Pages websites.
4. If this private repository does not have Pages available on the current
   GitHub plan, you must upgrade to an eligible plan or publish the
   **generated static website only** from a separate public repository.
   Do not make the P37 source repository public solely to enable Pages.
5. Open [Actions → P37 Brain Lab — GitHub Pages](https://github.com/OntosRobotics/P37-Neuro/actions/workflows/p37-github-pages.yml),
   choose **Run workflow** → **main**. Future changes under `sim/web/**`
   automatically rebuild and deploy.

No Cloudflare token is required. The Cloudflare workflow remains available
only for manual use.

## What the workflow verifies

- Clones MuJoCo Menagerie to get accurate third-party robot MJCF models
- Generates the simulator with mjswan at the correct GitHub **project-site**
  base path `/P37-Neuro/simulator/` (root-relative URLs are not sufficient)
- Bundles `index.html`, physics WASM, model meshes, and scene manifests
- Exercises all three robots, selection, canvas rendering, reset, and pointer
  interaction in headless Chromium at `/P37-Neuro/`
- Uploads screenshots and a downloadable site build even on preview PRs
- On `main`, deploys the exact tested website using official GitHub Pages Actions

### The public URL must be verified

The workflow must report `Publish at GitHub Pages: success`. Then open:

`https://ontosrobotics.github.io/P37-Neuro/`

Confirm G1, Go2 and Franka load, the physics runs and no assets fail to load.
GitHub Pages can take time to propagate. A successful CI **build** without
a successful deployment does not make the website public.

## Private-source safety

GitHub Pages is publicly viewable even when its source repository is private
on a supported plan. The deployment artifact is generated from only
`sim/web/index.html`, the compiled public mjswan viewer, and
`build-info.json`. No P37 model weights, internal training logs, credentials,
or unqualified policy binaries are included.

Before publication, verify MuJoCo Menagerie model-specific license notices
are preserved in the compiled viewer.
