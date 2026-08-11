# H3 Prompt Continuity

`H3SegmentPromptCompiler` turns one time-coded 30-second master prompt into two isolated H3 prompts.

- Segment 1 receives only the story beats before the split.
- Segment 2 receives only later beats, rewritten onto a local 0-second timeline.
- Segment 2 begins with MiniMax H3's official I2VA `<Picture 1>` alignment instruction.
- Missing or ambiguous second-half beats stop before H3 sampling instead of silently replaying segment 1.

Use explicit ranges such as `0-15秒：...` and `15-30秒：...`; finer ranges are supported.
