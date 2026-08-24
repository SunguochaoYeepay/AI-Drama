# Performance Guidelines

## Character And Voice Selection

- Match age, social role, temperament, accent, and dramatic function before tuning emotion.
- Query the current MiniMax account for available voices. Do not rely on remembered IDs because the catalog changes.
- Prefer explicitly described standard Mandarin voices when accent matters.
- Keep recurring characters on the same voice ID across episodes.
- Avoid assigning a warm, soothing voice to a confrontational role unless the contrast is intentional.

## Emotional Direction

- Design an arc instead of applying one emotion to every line. A typical argument moves through restraint, challenge, escalation, hurt, and recovery.
- Use the supported values only: `happy`, `sad`, `angry`, `fearful`, `disgusted`, `surprised`, and `calm`.
- Omit `emotion` when automatic interpretation is more natural, especially for lines that shift tone internally.
- Avoid fixed `calm` on every older-character line. Combined with slow speed and long sentences, it often sounds like synthetic narration.
- Use expressive tags such as `(sighs)` sparingly and only when the sound belongs to the speaking character.

## Dialogue Writing

- Write spoken Chinese, not explanatory prose. Use contractions and discourse particles where they fit the character: `你们俩`, `哎`, `啊`, `行了`.
- Break speeches into short clauses with meaningful punctuation. Long moralizing paragraphs amplify AI cadence.
- Use exclamation marks for actual peaks, questions for pressure, and ellipses only for hesitation. Too many ellipses make the scene drag.
- Put emotional transitions into the wording. For example, a restrained accusation should not use the same syntax as an explosive accusation.
- Keep narration concise and let sound design carry actions that do not need explanation.

## Starting Mix Levels

Use these as starting points, then inspect the mix:

- Continuous room ambience: `-28` to `-34` dB.
- Distinct foley such as doors or table impacts: `-10` to `-16` dB.
- Crying or crowds underneath dialogue: `-17` to `-23` dB.
- Fade looping ambience in and out. Fade sustained emotional effects before they end.
- Keep intelligible words out of generated effects; human language belongs on the MiniMax dialogue track.

## Quality Checks

- The voice fits the character before any emotion parameter is considered.
- Anger develops rather than starting at maximum intensity.
- Sad lines retain energy and do not become flat recitation.
- Older voices do not become excessively slow or sermon-like.
- Child and background sounds do not mask dialogue.
- Effects begin at the intended line after the final timeline is built.
- SRT timing ends within the audio duration and stays aligned near the final lines.
- The final mix does not clip; leave practical headroom near the peak.
