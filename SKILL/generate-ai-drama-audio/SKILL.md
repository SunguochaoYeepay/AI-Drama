---
name: generate-ai-drama-audio
description: Turn Chinese stories, social-media plots, or dialogue scripts into expressive multi-character drama audio in this repository. Use when an agent needs to adapt a story into roles and lines, choose verified MiniMax Speech 2.8 voices, direct per-line emotion and pacing, generate ElevenLabs ambience or foley, render dialogue and a final mix, revise selected performances through caching, or validate audio and subtitles before video production.
---

# Generate AI Drama Audio

Create finished Chinese drama audio with MiniMax Speech 2.8 for every human voice and ElevenLabs Sound Effects for ambience and foley. Work from the repository root that contains `ai_drama/`, `examples/`, and `pyproject.toml`.

Read [performance-guidelines.md](references/performance-guidelines.md) before writing or revising a performance. Read the root `README.md` when the JSON format or CLI output is unfamiliar.

## Workflow

1. Inspect the current branch, working tree, existing examples, and generated output without exposing `.env` values.
2. Confirm the story has a clear conflict, escalation, turn, and resolution. Preserve user-provided facts; do not invent claims about real people or current events.
3. Create or update one JSON file under `examples/`. Use `speech-2.8-hd` and `language_boost: Chinese` unless the user requests otherwise.
4. Define one stable character key per speaker. Keep all human dialogue on MiniMax. Use ElevenLabs only for nonverbal ambience, foley, or non-intelligible crowd/crying sounds unless the user explicitly requests a provider comparison.
5. Verify voice IDs instead of guessing. From the repository root, run:

   ```bash
   python3 SKILL/generate-ai-drama-audio/scripts/list_minimax_voices.py
   ```

   Use `--match` to filter descriptions, for example `--match '普通话|中年|奶奶'`.
6. Direct the performance line by line. Combine voice choice, `emotion`, `speed`, punctuation, wording, and `pause_after_ms`; do not expect `emotion` alone to create nuanced acting.
7. Describe sound effects in English. Add `no music` and `no voices` when intelligible speech or unwanted music would be harmful. Place effects with `start_at_line` where possible so timing follows dialogue revisions.
8. Validate without API cost:

   ```bash
   python3 -m ai_drama generate examples/<story>.json --dry-run
   ```

9. Generate the real result only after validation:

   ```bash
   python3 -m ai_drama generate examples/<story>.json
   ```

10. Run the same command once more. Confirm every unchanged speech segment and sound effect reports that it was reused. Investigate any unexpected regeneration before making more API calls.
11. Check `manifest.json`, `dialogue.srt`, output duration, file sizes, and final peak level. Run `python3 -m unittest discover -v` and `git diff --check` before publishing source changes.
12. Deliver playable links to both `dialogue.mp3` and `final_mix.mp3`. Never commit `.env`, API keys, `outputs/`, or generated media.

## Revision Rules

- Preserve the accepted version as `final_mix_vN.mp3` before overwriting a local mix for comparison.
- Revise the same story and output directory when only selected lines or characters change. Request hashes will reuse unaffected speech and effects.
- Change one performance dimension at a time when diagnosing flat or synthetic speech: first voice fit, then line wording and punctuation, then emotion, speed, and pitch.
- Regenerate only the affected lines. Do not delete caches to force a full rerun.
- Stop after producing the requested audio. Treat image keyframes, video generation, and lip sync as a separate workflow.

## Safety And Publishing

- Read only the names of configured environment variables when checking setup. Never print or commit their values.
- Treat network-hotspot stories as potentially copyrighted, private, or defamatory. Require fact checking and meaningful adaptation before monetized publication.
- Keep generated audio under ignored `outputs/`; commit only reusable scripts, story configurations, tests, and Skill files.
