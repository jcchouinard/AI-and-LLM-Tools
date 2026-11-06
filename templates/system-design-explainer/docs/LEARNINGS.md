# Learnings

Distilled from building and iterating on this skill with a real user and a real internal repository.

## Product lessons
- **Users preferred the plain document.** The first public design was a dark, animated showcase. Feedback: the simple Confluence-style page was better. Keep both modes in the same clean layout and add only one interactive element where it helps.
- **Less text.** The first draft had long descriptions everywhere. The user asked for about half. Write 6 to 12 words per description and 2 to 5 words per flow message.
- **Titles are the app's name.** A descriptive rename ("Something Lab") confused the user. Use the real app name in both modes unless asked to hide it.
- **Security never goes in public output.** Enforce it in the renderer (drop the list), not per item. A per-item "empty public text" worked but relied on the author remembering.
- **Always show the AI models.** Users want exact model ids, provider and purpose. Include models selectable in the UI, and hide configured-but-unused models from public.
- **Diagram text must be readable.** SVG text scales down with the container. Give the diagram full width and large font units, then measure rendered pixels.

## Safety lessons
- The leak scan found real leaks the author had missed: table names inside descriptions, a vendor name in a tech field, internal ids in Mermaid source, and a route fragment inside a flow message. Keep the scan and fix the data when it fails.
- Use whole-word matching. Substring matching flagged ordinary words (a short column name matched "radio").
- Generic column names that are also normal words need an explicit `scan_ignore`, a deliberate human decision.
- Do not write reassuring public claims you did not verify. One draft said credentials were injected at runtime. The repo actually committed them. It was removed.
- While reading a real repo the agent found committed API keys and a key printed to a UI. Report these to the user directly and never copy values into any output.

## Technical lessons
- Anonymize diagram node ids as well as labels, because Mermaid source and page data reveal ids.
- A 9-digit hex color is invalid CSS and drops the whole rule. The page background went white and headings disappeared.
- Scroll-reveal animation (opacity 0 until visible) makes automated element screenshots blank. Prefer no reveal animation.
- Fan-out edges overlap their labels near the source. Put labels on a top layer at about 70 percent along the curve and show them on hover only.
- Long node names overflow. Scale the font by name length and keep component names under about 20 characters.
- Nav highlighting by IntersectionObserver picked the wrong section. Compute the active section from scroll position instead (the section whose top is above 45 percent of the viewport).
- A string replace that edits JSON in place can make later tool writes fail with "file changed since read". Re-read before writing.

## Testing lessons
- Some browser tools block `file:` URLs. Serve the output with `python3 -m http.server`.
- Requested viewport sizes may not apply, and screenshots may capture only part of the page. After two bad screenshots, stop and verify with DOM queries: scroll width, font size times scale, overlaps, overflow, console errors, and the copy payload.
- Verify the explorer by clicking a node, switching to a flow, stepping with the next button, and checking the active step and caption text.
