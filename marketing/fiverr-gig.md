# Fiverr/Upwork gig copy — CAPTCHA widget unblocking (IconCaptcha / odd-one-out)

## Title
I will build a reliable IconCaptcha / odd-one-out widget solver for your upload flow

## One-liner
Uploads, submissions, or scrapes blocked by an IconCaptcha (odd-one-out icon pick)? I ship a
tested solver that integrates with your browser automation in one day — synthetic-event based,
no third-party key risk, with 2captcha GridTask as fallback.

## What I deliver
- In-browser solver: widget screenshot → odd-cell detection → positional synthetic events on the
  correct overlay element (the widget's click listener ignores canvas clicks; I handle that).
- Hover-protection-safe event sequence (mouseenter before mousedown — most "silent fail"
  integrations miss this).
- State verification: wait, re-screenshot, confirm VERIFICATION COMPLETE before your form submits.
- 2captcha GridTask fallback path if you prefer human-in-the-loop solving at scale.
- Retry loop with widget self-reset handling on wrong picks.
- Test harness so you can verify the solver against your deployment before I hand over.

## Why me
- Working open-source toolkit (github.com/sushiomsky/gif-tool, 55 passing tests) with the
  solve sequence, cell geometry, and pitfalls already extracted from a live deployment.
- I've profiled the widget's event handling: zero <img> elements is normal (canvas-drawn icons),
  isTrusted-gated deployments get escalated to real-input driving, not synthetic retries.

## Pricing (suggested)
- Basic — integration into one flow: $450
- Standard — + retry/verify loop + test harness: $800
- Premium — + 2captcha fallback + deployment under load: $1,500

## Scope guard
I integrate with YOUR deployment or a sandbox you control. No bulk account creation, no ToS
circumvention on platforms without an automation-friendly posture.
