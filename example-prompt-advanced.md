# Advanced prompt patterns

## Variables — supply at fire time

Prompts can declare variables in their frontmatter. Variables make prompts reusable
across different resources, entities, or contexts.

Fire with a value:
```
/fire add-endpoint Resource=Invoice id=invoiceId
```

Fire without a value — Claude infers from context:
```
/fire add-endpoint
```

---

## Scheduling — run overnight

```
/schedule refactor-service 02:00
```

Fires at 2:00am in your local timezone. Useful for long jobs you want ready by morning.

---

## Multi-fire — queue several jobs at once

```
/fire fix-bug add-tests update-docs
```

Jobs run sequentially. Each creates its own branch and PR.

---

## Inline one-offs with /run

For tasks that don't need a saved prompt:

```
/run Fix the pagination bug on the users list — it skips every other page when filtering by status
```

Override model or thinking:
```
/run --model opus --thinking high Redesign the caching layer to handle concurrent writes correctly
/run --repo web --branch feature/redesign Update the login page to match the new design system
```

---

## Thinking levels — when to use each

| Level | Prompt prefix | Use for |
|---|---|---|
| `none` | (none) | Routine tasks, clear requirements |
| `low` | think | Tasks with a few non-obvious tradeoffs |
| `medium` | think hard | Architecture decisions, complex bugs |
| `high` | ultrathink | Major refactors, subtle correctness issues |
