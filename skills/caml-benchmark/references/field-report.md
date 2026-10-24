# Field reports: what went wrong, and how you got past it

Every agent run on a user's machine produces a **field report**: a Markdown
file that tells the CAML maintainer what broke, what was confusing, what you
had to work around, and what simply worked, on this operator OS. The user
sends it to the maintainer, who uses it to fix CAML and its docs for the
next person on that OS. It's a deliverable, as important as the benchmark
report.

## Rules

1. **The file**: `<report folder>/caml-field-report-<os>.md`, where `<os>`
   is `windows`, `macos` or `linux` (`linux` for WSL, noting WSL in
   Environment). Create it from the template below **before your first
   command**.
2. **Write each entry when it happens**, not from memory at the end. A
   one-line placeholder now beats a lost detail later.
3. **Record everything that cost time**, including problems you fixed in
   seconds:
   - an error or a wrong result;
   - a command from the docs that needed changing on this OS;
   - a doc that was wrong, missing, out of date or ambiguous;
   - a place where you had to guess;
   - a slow or confusing step;
   - anything that would trip the next agent (a gotcha), even if it didn't
     fail this time.
4. **Exact text.** Give the command as run, the error as printed (trim long
   logs to the 20–40 relevant lines), the exit code, and the UTC time. Say
   when a cause is a guess.
5. **Don't change CAML's code to get past a problem.** Work around it, and
   describe both the workaround and the change you'd suggest to CAML.
6. **Never include** passwords, keys, tokens, the server's IP or hostname
   (write `caml-vps`), rows of the user's data, or the user's name in paths
   (write `<user>`). Include column names only if the user agrees.
7. **Finish it**: fill in the Summary, and keep "What worked first time"
   even when everything worked. That is useful evidence too.
8. **Hand it over.** At the end, tell the user where the file is and that
   it's meant for the CAML maintainer. The easiest way to send it is a new
   GitHub issue with the "Field report" template, with the file attached:
   https://github.com/A1i-Tabatabaei/CAML/issues/new/choose. **Don't post it
   yourself.**

## Template

````markdown
# CAML field report: <Windows | macOS | Linux>, <YYYY-MM-DD>

## Environment
- Operator machine: <OS and version, CPU architecture>
- Shell: <Windows PowerShell 5.1 | PowerShell 7.x | Git Bash | cmd | zsh 5.x | bash 5.x | WSL distro>
- Agent: <product and version, model>
- Local tools: `ssh -V`: <...>; git: <version or "not used">; tar: <...>
- Server: <provider>, <vCPU / RAM / disk>, <`os:` line from `camlctl info`>
- CAML: <`camlctl version` output>
- Dataset: <rows x columns>, <format and encoding as exported>, <task type>

## Summary
- Outcome: <finished | partly finished | blocked at phase N>
- Timeline (UTC): setup <start-end>, installs <...>, sweep <...>, report <...>
- Problems: <n> (<n> blocking); doc changes suggested: <n>

## Problems
One entry per problem, in the order they happened.

### P1: <short title>
- When: <phase and step>, <UTC time>
- Where: operator machine | server | CAML docs | a framework
- Severity: blocker | slowed me down | cosmetic
- Command:
  ```
  <exactly as run>
  ```
- What happened:
  ```
  <error or output excerpt, with the exit code>
  ```
- Cause: <what you found; say if it's a guess>
- Fix or workaround: <what worked, with commands>
- Suggested change to CAML: <file and section, and what to change>
- Status: fixed | worked around | unresolved

## Check-ins
- Goal: <benchmark study | best model | both>; asked in the first message? <yes/no>
- Credentials: <the hidden prompt | the file | not needed>; anything that went wrong
  (no names or values of keys)
- Task card: what the user corrected (target, task type, columns, row
  structure, metric), and how many rounds it took
- describe-data flags that were wrong: <column kind or flag, and why> (column
  names only if the user agrees)

## Gotchas
Things that didn't fail but would trip the next agent on this OS.
- ...

## Docs: wrong, missing or unclear
| File | Section | Problem | Suggested text |
|---|---|---|---|

## What worked first time
- ...

## Monitoring
- How you polled (camlctl wait, camlctl status, your scheduler), how often,
  and anything you missed or would do differently.
````
