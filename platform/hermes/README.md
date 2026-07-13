# Hermes runtime

Hermes is the initial agent runtime and Telegram gateway. It remains separate from the Aitegrate backend and is replaceable through `app/integrations/hermes/`.

This directory stores versioned templates only:

- `config/` for reviewed non-secret configuration;
- `prompts/` for agent behavior;
- `skills/` for product-specific tools;
- `workspace-template/` for a clean per-company workspace.

Runtime state, OAuth credentials, tokens, conversations, and personal memory must not be committed. The concrete Hermes installation and configuration files will be added after pinning the version used by the project.
