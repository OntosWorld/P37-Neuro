# P37-Neuro web interface — Steel playground reference

Reference: [Skild Steel live demo](https://www.skild.ai/demos/steel) and the
[Apache-2.0 Steel WebGPU open-source viewer](https://github.com/skild-ai/steel-webgpu)
(`apps/viewer/src/steel/styles.ts`, `apps/viewer/src/demo/Gallery.tsx`).

The reference was inspected as a live page at **1512 × 930** and **390 × 844**
in Chrome (GitHub Actions captures `skild-steel-reference`). Skild's top-level
editorial site and embedded physics viewer are different visual layers. This
design preserves that split.

## Shared visual system

| Area | Design contract | Implementation |
| --- | --- | --- |
| Editorial page | White `#fff`, deep green-black `#1b2b28`, Geist-style sans, measured margins | `sim/web/steel-site-shell.css` |
| Simulation canvas | Dark `#1d2125`, full-width physics, compact status overlays | `sim/web/steel-playground.css` |
| Physics HUD | `rgba(20,24,28,.92)`, border `#45525e`, monospace 13px | Same; React `src/steel-playground.css` |
| Controls | `#2c3640` input surfaces, 5–8px radius, selected `#9fd3ff` | Shared CSS and React workcell CSS |
| Scenes | On-demand gallery, image-led cards, visible active item, keyboard dismiss | Robot library and `SceneGallery.tsx` |
| Responsive | Scene remains the focus; drawer/gallery work at 390px without horizontal overflow | Shared CSS + Playwright checks |
| P37 attribution | ONTOS mark, real robot preview licenses, source-specific research claims | First-party React/HTML; Menagerie notices |

We use Skild as a UX and technical viewer reference. We **do not** use its
trademarks, logos, text, videos, model weights, or proprietary scene assets.
The code, branding, architecture descriptions, and source attribution belong
to P37-Neuro and its actual upstream dependencies.

## Routes covered

1. `/`: original Brain Lab, ten real Menagerie robot models and physics; floating
   HUD and image-led on-demand robot model gallery.
2. `/demos/`: scene chooser, actual MuJoCo viewports, two-robot comparison,
   measured disturbances, P37 checkpoint evidence and qualifications.
3. `/lab/`: architecture explorer; scenario switches remain functional.
4. `/lab/sim/`: kinematic simulator with task controls and reference body switches.
5. `/lab/compare/`: source-attributed offline episode playback and numerical traces.
6. `/lab/steel/`: original industrial physics workcell, selected scene gallery,
   object controls, cameras, reference robot and solver tuning.

## Robotics claim boundaries

- The actual Menagerie models are physically simulated in MuJoCo, and the Steel
  workcell attempts WebGPU rigid-body simulation when the device supports it.
- Two recorded MimicGen Panda source episodes can be inspected in the same
  experiment viewer and overlaid as **source trajectories** in the workcell.
  They are not P37-trained output, nor different embodiments.
- The workcell reference arms use a deterministic analytic reach baseline.
  Do not state that the arms were driven by a learned P37 policy.
- The existing brief G1 checkpoint evaluation records are separate evidence;
  they do not establish cross-body transfer or general-purpose locomotion.
- Hosted Chrome/SwiftShader can lose its Steel WebGPU device. A successful
  fallback screenshot validates fallback UX, **not** live Steel rendering.

## Release acceptance

- The website preserves all ten model scenes, the simulation gallery,
  evidence imports, source attributions and every control ID used by JS.
- The site assembles both CSS layers and ten actual Menagerie preview images
  from the pinned checkout with `robot-thumbnails/THIRD_PARTY_LICENSES.txt`.
- Desktop and mobile browser tests verify routes, scene switching,
  model previews, source JSON playback and no horizontal overflow.
- Steel Vite builds and the browser test validates its gallery, solver choices,
  controls, responsive layout and honest GPU fallback.
- **Do not claim full live Steel QA** until a browser with stable WebGPU runs
  the actual physics and object-picking test end to end.
- GitHub Pages must publish successfully after merging. Passing PR checks
  alone does not mean the public website has been updated.
