# Statuses

Copied in meaning from the cartographer instrument (github.com/iantitus-fit/cartographer, reference/statuses.md).

| Status | Test | What the reader does |
|---|---|---|
| live | Wired on both ends: something writes it, something reads it, on a path that runs. | Implement and cite against it. |
| leftover | Exists, wired on neither end. | Leave it unless retiring it is the task. |
| ghost | A name with no object behind it (a doc, a UI list, an enum label). | Never implement against it. |
| half-wired | Wired on exactly one end. Carries a direction: reader-only, writer-only, or admitted-but-unrouted. | Wire the missing end deliberately, as its own change. |

A VERIFY line marks one fact nobody could confirm from the code, and names what settles it.
