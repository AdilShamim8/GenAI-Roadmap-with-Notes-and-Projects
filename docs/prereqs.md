# Prerequisites

> **Level:** BEG · **Time:** 2–4 weeks if starting from scratch · **Purpose:** get you ready for Rung 0 of the [12-rung ladder](../README.md)

The from-zero learning path assumes four skills before you start. This file tells you how to build each one. Do not start Rung 0 until you can pass the self-checks at the bottom of this page — every rung after it silently assumes them.

## 1. Python fluency

You need enough Python to read, write, and debug 50–200 line scripts: functions, dicts and lists, f-strings, `pip` and virtual environments, `try/except`, and reading library docs. You do not need classes, decorators, or async — those show up in the curriculum itself when needed.

Work through the free [Python for Everybody (py4e)](https://www.py4e.com/) lessons 1–10, or Chapters 1–8 of the free [Automate the Boring Stuff with Python](https://automatetheboringstuff.com/) book. Then practice: write a script that reads a CSV, calls a public REST API once per row, and writes the combined result to a new CSV.

## 2. Git and GitHub

You need the daily loop: `clone`, `add`, `commit`, `push`, `pull`, `branch`, `merge`, and opening a pull request on GitHub. You also need to read a diff.

[Learn Git Branching](https://learngitbranching.js.org/) (free, interactive) covers everything through the "Remote" levels in an afternoon. Then practice for real: create a repository, commit the CSV script from the section above, open a PR from a branch, and merge it.

## 3. HTTP and JSON

You need to explain: what a request/response pair is, the common verbs (GET/POST/PUT/DELETE), status-code families (2xx/3xx/4xx/5xx), headers, and how JSON maps onto Python dicts and lists.

[MDN: HTTP Overview](https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview) plus [MDN: Working with JSON](https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Objects/JSON) is enough. Then practice: call the same public API once with `curl` and once with `requests` and confirm you get identical JSON.

## 4. Reading errors

You need to read a Python traceback bottom-up and know how to search an error message productively — strip your local variable names first, read the top results, and check the date on every answer you find.

There is no course for this. The practice tasks above will generate real errors; resist the urge to paste the whole traceback into an AI chatbot immediately. Read it yourself first, form a hypothesis, then verify.

## Self-check

You are ready for Rung 0 when you can do all four of these without help, using only the standard library plus `requests`:

1. Write a script that calls a public JSON API, handles a 4xx error with a retry, and prints parsed fields.
2. Put that script in a fresh Git repository with a `README.md` and push it to GitHub.
3. Explain, in one sentence each, what a 301, 401, 429, and 503 means and what your script should do about each.
4. Deliberately break your script (wrong URL, bad key name) and describe the error before fixing it.

If you pass: move on to [`foundations/`](../foundations). If any step takes more than 30 minutes, go back to the matching section above — the ladder is steep, and this is the cheapest place to build the base.
