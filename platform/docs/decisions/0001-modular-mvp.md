# ADR 0001: Start with a modular MVP

## Status

Accepted.

## Decision

Start with a simple feature-oriented modular monolith. Preserve explicit boundaries around application services, authorization, RAG, repositories, channels, and external integrations.

Hermes is a replaceable runtime, not the source of truth for permissions or data lifecycle.

## Consequences

The MVP remains quick to build. A later migration to domain-oriented modules should primarily move code rather than redesign behavior.
