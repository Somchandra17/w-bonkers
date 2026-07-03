# {{PLAN_LABEL}} — Changelog (append-only history)

Each `/{{COMMAND_NAME}}` run appends a dated entry here: what changed (EXIT/SWITCH/ADD/TRIM/fill) or "no change". This is the running history the next run reads for context.

## {{INSTALL_DATE}} · Rev 1 (baseline)
- Plan installed by w-bonkers. Corpus {{CORPUS_INR_PRETTY}} across buckets: {{BUCKETS_SUMMARY}}.
- Opening book: {{POSITIONS_SUMMARY}}.
- Levels anchored to {{PRICES_ASOF}}. All positions status=pending (nothing executed yet).
- Scheduling: {{SCHEDULE_MODE}}. First review: {{FIRST_REVIEW_DATE}}.
