# Fleetwright — Blockers

---

## OPEN: Domain registration (M6)

**Date logged:** 2026-07-03  
**Milestone:** M6 — Public flip + launch  
**Status:** Open — awaiting JD action

**What's blocked:** Registration of `fleetwright.dev` and `fleetwright.ai`.

**What's needed from JD:**
1. Log in to your preferred domain registrar (Porkbun, Namecheap, Google Domains/Squarespace, etc.)
2. Register `fleetwright.dev` (~$12/yr) and optionally `fleetwright.ai` (~$50–100/yr)
3. Add CNAME records pointing both domains → `jddavenport.github.io`
4. GitHub Pages CNAME is already configured (`docs/CNAME` → `fleetwright.dev`), so docs will auto-serve once DNS propagates

**Name availability (verified 2026-06-01):** both TLDs were clean at research time. Re-verify before registering.

**Why I can't do it:** Domain registration requires authenticated access to a registrar account + payment method. No registrar API credentials are available in the agent system.

**Impact:** The docs site resolves at `https://jddavenport.github.io/fleetwright/` in the meantime (GitHub Pages auto-deployed via `docs.yml` on push to main). All launch posts reference `fleetwright.dev` — update them if registration is delayed.

---

## OPEN: Social media posting (M6)

**Date logged:** 2026-07-03  
**Milestone:** M6 — Public flip + launch  
**Status:** Open — drafts ready in LAUNCH.md, JD to post

**What's blocked:** Actually submitting the Show HN post, X thread, and Reddit posts.

**What's ready in LAUNCH.md:**
- Show HN submission (title + body, ready to copy-paste into HN form)
- X/Twitter thread (5 tweets)
- r/ClaudeAI post (title + body)
- r/LocalLLaMA post (title + body)
- Discord template

**What's needed from JD:**
- HN: submit via https://news.ycombinator.com/submit (best time: Tue/Wed 8-10am ET)
- X: post the 5-tweet thread from your account
- Reddit: post to r/ClaudeAI and r/LocalLLaMA
- Discord: post in Claude Code Discord, Latent Space Discord, AI Engineer Discord

**Why I can't do it:** No authenticated HN/X/Reddit session available to the agent in the current setup. The X Socrates agent (@Th3RealSocrates) is under a shadowban per memory.
