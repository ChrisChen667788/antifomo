# GitHub Launch Polish Checklist

Use this checklist after a public-facing repository change and before describing a release as ready to share. It is deliberately separated from code tests and release-evidence approval: completing a public-repository check does not authorize a production release.

## 1. Repository copy and links

- [ ] README one-line pitch still describes the checked-in product, not an unverified deployment.
- [ ] English and Chinese README links resolve, including quick start, public roadmap, feature map, contributor guide, security policy, launch kit, and screenshots.
- [ ] Version/status copy distinguishes local implementation, fixtures, external evidence, and release readiness.
- [ ] No personal paths, runtime secrets, private source data, customer data, or real Mini Program credentials are present in public files.

## 2. GitHub repository settings (manual owner actions)

- [ ] Upload the current `docs/assets/github-social-preview.png` under **Settings -> General -> Social preview**.
- [ ] Update the GitHub About description, homepage, and relevant topics using the copy in the [launch kit](./open-source-launch-kit.md).
- [ ] Review pinned-repository copy with the [growth copy kit](./open-source-growth-copy.md); pin only after the public links work for a logged-out visitor.
- [ ] Check that issue, discussion, security, license, and contribution links lead to the intended public destination.

## 3. Assets and release-page links

- [ ] Regenerate and inspect the checked-in screenshot matrix with `npm run repo:screenshots` when its backend precondition is available.
- [ ] Keep the manifest, README image links, and [screenshot coverage](./feature-screenshot-coverage.md) synchronized.
- [ ] Use the documented demo-motion workflow for a short GIF/MP4; do not substitute a mockup for a product capture.
- [ ] Add only reviewed, compressed public assets. Keep raw recordings, local logs, device identifiers, and private screenshots out of Git.
- [ ] If a GitHub Release is created, verify its tag, changelog links, release assets, and source links from a fresh browser session.

## 4. Public verification

- [ ] Run the scoped test/build checks appropriate to the modified surface.
- [ ] Open the README and at least one primary screenshot on GitHub in a logged-out or private browser window.
- [ ] Confirm that any external link, source claim, screenshot date, and version claim is still current.
- [ ] Record any remaining human/Office/visual/security/performance gate as `HOLD` rather than hiding it in launch copy.

## Result record

Keep a short release note or issue comment with the following fields:

| Field | Record |
| --- | --- |
| Commit or tag |  |
| Reviewer |  |
| README/link check | pass / hold + reason |
| Social preview upload | complete / pending |
| Screenshot/demo review | pass / hold + reason |
| Remaining release-evidence gates |  |
