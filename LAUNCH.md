# Launch & visibility playbook

A practical checklist for taking Fathom from "pushed" to "people are starring it".
Remove this file from the repo after launch if you prefer, or keep it as a maintainer note.

## 0. Publish (≈15 minutes)

```bash
cd fathom
# 1. Replace the placeholder everywhere
grep -rl Rishabh2991 . | xargs sed -i '' 's/Rishabh2991/<your-username>/g'   # macOS
# grep -rl Rishabh2991 . | xargs sed -i 's/Rishabh2991/<your-username>/g'   # Linux

# 2. Create the GitHub repo and push (needs the GitHub CLI: https://cli.github.com)
gh repo create fathom --public --source . --remote origin \
  --description "The shell that reads the room: AI next-step suggestions for any terminal. Works offline." --push

# 3. Topics drive GitHub search and the topic pages
gh repo edit --add-topic shell,terminal,cli,ai,llm,ollama,local-llm,offline,devops,sre,developer-tools,python

# 4. First release: builds binaries for 5 platforms and publishes to PyPI
git tag v0.1.0 && git push origin v0.1.0
```

For PyPI, set up **trusted publishing** once at pypi.org → *Your projects → Publishing* (owner, repo,
workflow `release.yml`, environment `pypi`). No tokens to manage.

In the repo settings: enable **Discussions**, **private vulnerability reporting**, and upload a
**social preview image** (1280×640: logo + "AI next moves for any shell — offline").

## 1. Before you tell anyone

- [ ] Record the demo GIF: `brew install vhs && vhs docs/demo.tape` — the GIF is the single biggest
      factor in whether a visitor stars. Keep it under 20 seconds and show the offline badge.
- [ ] Open 8–10 issues labelled `good first issue` / `new-rule` (Terraform lock, cargo errors, AWS
      expired token, Postgres connection refused, Helm upgrade failed…). Newcomers need a door.
- [ ] Pin a Discussion: "What error should Fathom learn next?"
- [ ] Make sure `pipx install fathom-shell && fathom` works on a clean machine.

## 2. Launch week (stagger, don't blast)

| Day | Channel | Angle |
|---|---|---|
| Tue | **Show HN** — "Show HN: Fathom – AI next-step suggestions for any shell, works offline" | Post 8–10am US Eastern. First comment: why you built it, how offline works, what's next. Answer every comment. |
| Wed | Reddit: r/commandline, r/selfhosted, r/LocalLLaMA | Lead with offline + Ollama for r/LocalLLaMA and r/selfhosted; with the server/SSH angle for r/commandline. Read each sub's self-promo rules. |
| Thu | r/devops, r/sysadmin, r/Python | "It tails logs and suggests fixes" for ops; "zero-dependency stdlib-only" for r/Python. |
| Fri | X/Twitter, LinkedIn, Bluesky, Mastodon (#fediverse devs) | 20-second clip, not a link alone. Tag Ollama. |
| Next week | Product Hunt | Line up a few people to leave genuine feedback early in the day. |

India-specific: post in the Bangalore/Python India/DevOps India communities and HasGeek; submit a
lightning talk to a local meetup (PyCon India, DevOpsDays India, Bangalore Python meetup).

## 3. Get into the lists (permanent, compounding traffic)

Open PRs to add Fathom to: `awesome-shell`, `awesome-cli-apps`, `awesome-ollama`,
`awesome-selfhosted` (if it fits their criteria), `awesome-devops`, `awesome-sysadmin`,
`awesome-llm-apps`, `awesome-python`. Also submit to Ollama's community integrations list,
openalternative.co, AlternativeTo and Console.dev's newsletter.

## 4. Content that keeps working

- Blog post: "I made my shell suggest the next command — offline, in under 2,000 lines of Python" (dev.to + Hashnode + your blog, canonical link to one).
- Post the **error benchmark** results (see ROADMAP): "Which small local model is best at fixing shell errors?" — benchmark posts get shared widely in the local-LLM community.
- 60-second YouTube Short / Reel per feature (watch mode, offline mode, natural-language mode).

## 5. Keep momentum

- Ship a small release every 1–2 weeks; each release is a reason to post again.
- Reply to issues within 24 hours for the first month; credit contributors in release notes.
- Add a `CONTRIBUTORS` section (all-contributors bot) — people share repos they appear in.
- Track: stars, PyPI downloads (pepy.tech), traffic (Insights → Traffic), and which referrer converts.
