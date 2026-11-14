# Examples — a sample World

A small World that exercises every part of the format: one campaign, two
events, one NPC, one PC, one mod that features them, and the after-action whose
canon change moved the NPC's status.

The tests load these files and change them a little at a time, so a schema
change that invalidates them fails a test. Keep them in step with the schema.

```sh
plotcanon validate --root examples   # expect: 7 documents · 0 errors · 0 warnings
```
