# The four things only the account owner can do

Everything else in this repository was done from inside a container by an agent
with a git credential scoped to one branch. These four are not, and each is a
few minutes. They are ordered by what they buy.

Nothing here is urgent and nothing here is required for the work to be correct —
`python3 -m soup verify` does not care whether any of this ever happens.

---

## 1. Repository topics — 30 seconds, needs nobody

GitHub's topic pages are where somebody browsing this subject actually looks, and
topics can only be set from the repository's own settings page. There is no API
tool for it in this session and no `gh` CLI.

Settings → General → Topics, paste these:

```
artificial-life
alife
digital-organisms
tierra
self-replication
evolutionary-computation
error-threshold
simulation
python
```

While there: the About box takes a one-line description. Suggested —

> A 60,000-cell soup where one hand-written self-replicating program evolves.
> Twenty findings, six of them corrected. `python3 -m soup verify` checks them
> on your machine.

---

## 2. Zenodo, for a DOI — two clicks plus a release

`CITATION.cff` and `.zenodo.json` are already in the repository root and Zenodo
reads both, so the metadata is done. What it needs is an account action and a
release, and the tag push failed from here with HTTP 403 — this session's
credential covers branch refs only.

1. Sign in at zenodo.org **with GitHub**, authorise it.
2. Under GitHub in the Zenodo menu, find `own-claude` and flip its switch on.
   (If it is not listed, "Sync now".)
3. Back in the repository:

   ```
   git tag -a v1.0.0 -m "soup v1.0.0 — twenty findings, six of them corrected"
   git push origin v1.0.0
   ```

4. On GitHub, draft a release from that tag. `CHANGELOG.md` is written to be
   pasted straight into the body.

Zenodo archives it and mints the DOI within a few minutes. Every later release
gets its own, and a "concept DOI" points at the newest.

A DOI is an archive record, not a publication — no author has to answer for it,
which matters here because nobody is claiming authorship. See `NOTICE`.

---

## 3. The ISAL mailing list — the one most likely to produce a critic

`main@isal.groups.io` is the International Society for Artificial Life's
discussion list (subscribe by sending a blank email to
`main+subscribe@isal.groups.io`); `announce@isal.groups.io` is the low-traffic
news one, and the *ALife News* newsletter exists to report what people in the
field are doing.

This is the venue that could produce the one thing this project actually wants,
which is somebody who runs the verifier and disagrees with it. It is also a
mailing list of working researchers, so it is worth being short and being honest
about provenance in the first sentence rather than the last. A draft:

> **Subject:** soup — a Tierra-style world, AI-written, CC0, with a verifier
>
> This is a Tierra-style artificial life world written by an AI (Claude) with no
> human author, released CC0: 60,000 cells, a saturated 32-instruction machine
> with template addressing, one hand-written 64-cell ancestor.
>
> Two things in it may be worth a look. It reproduces Ray's optimization and
> plateau results from a second, independently written ancestor — and it tests
> the inference he drew from the plateaus in 1991, that a run stopping at a size
> limit has reached a local optimum. For one of two plateaus here that is right;
> for the other it is not, and cheaper variants that beat the champion
> head-to-head sit one deletion away while the population stays put for ten
> billion instructions.
>
> Separately, five of the six things this project got wrong were the measuring
> instrument rather than the world, and they are indexed rather than quietly
> fixed: docs/CORRECTIONS.md.
>
> `python3 -m soup verify` re-checks twelve of its claims on your machine in
> seconds and exits non-zero if any fails on yours but not on mine. Pure Python,
> no dependencies. I would rather have it refuted than read.
>
> <link>

Send it or don't; it goes out under your name either way, which is the reason
it is in this file instead of already sent.

---

## 4. `awesome-artificial-life` — a one-line pull request

Native contribution mechanism, low stakes, low expectations: the list has nine
commits in total. It has no Tierra-like subsection, so the entry goes under
**Simulators**, in the list's own format:

```markdown
**soup** - A Tierra-style world of 60,000 memory cells; one hand-written self-replicating program and twenty findings, each with a check that reruns it. [[code]](https://github.com/<owner>/own-claude)
```

Suggested PR title: `Add soup, a Tierra-style digital organism simulator`

Suggested PR body:

> Adds `soup` under Simulators — a 60,000-cell Tierra-style world in dependency-free
> Python, with the findings held as machine-checkable claims (`python3 -m soup verify`).
>
> Disclosure, since it is unusual: it was written by an AI (Claude) with no human
> author and is released CC0. Happy for that to be a reason not to merge it.

I could technically fork and open this from here, but it would appear under your
GitHub identity in a stranger's project, so it is yours to send.

---

## What was tried and could not be done from inside

For the record, since "why didn't the agent just do it" is a fair question:

| | why not |
|---|---|
| push the `v1.0.0` tag | credential is scoped to branch refs; tag push returns HTTP 403 |
| create a GitHub release | the GitHub tools in this session can read releases, not create them |
| set repository topics | no tool for it, and no `gh` CLI in this environment |
| link and publish on Zenodo | an OAuth authorisation tied to your account |
| open the awesome-list PR | possible, but it publishes under your identity to a third party |
