# Learnings

- The first version had an unlimited whole-repo flag. The user wanted strict recursive stops, so it was removed and replaced by a bounded audit mode with an estimate step. Design every scan with ceilings from the start.
- The motivating fear was an agent grepping and reading every file of a big repo. The fix is structural: the script scans, the agent reads only a queue with a file and byte budget.
- Running the scanner on a real repo showed the remaining HIGH hits were the repo's own injection filter and its test fixtures. That is what `.pr-gate-ignore` is for. Provide it from day one.
- Allow markers need to surface as WARN, otherwise a malicious commit could add one and silence a finding.
- Tests should plant every category and also include decoys (placeholders, example emails) to prove no false positives.
- Test the hook end to end in a throwaway repo: a staged fake token must block, a clean push must pass.
- Install via symlink so edits in the project are live in the global skill.
- Cost is measured per scan: estimate runs in well under a second on tens of thousands of files because it never opens a file.
