# ChinaList — Authenticated Subscription Experience

## Goal

Extend an enterprise-intelligence product from public browsing into an authenticated, consent-aware subscription experience.

## Work completed

- Google OAuth with Auth.js database sessions;
- HttpOnly and SameSite session-cookie boundaries;
- protected account, watchlist and settings pages plus API-side authorization;
- account, privacy, consent withdrawal and time-zone preferences;
- personal watchlist and shared enterprise watchlist behavior;
- digest and breaking-news preview flows;
- clear feedback for validation and state changes.

The implemented product rule used a five-company personal limit and a fifteen-company shared enterprise limit. The portfolio does not expose internal company records or production configuration.

## Verification

The working branch passed **14 unit tests**, TypeScript checking, lint and a Next.js production build. Browser checks covered login, logout, protected-route redirects and authenticated session behavior.

## Boundary

The work demonstrated preferences, consent and preview/test-delivery behavior. It does not claim that real billing, unrestricted email delivery or a production membership rollout was launched.

The screenshots in the repository are from the local development environment. The personal email and avatar identifier were replaced before publication. They show a consented preference state and a failed-save feedback state; they do not show a production deployment or real customer data.

