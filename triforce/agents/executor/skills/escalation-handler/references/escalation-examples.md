# Escalation Examples

Reference examples for weight classification edge cases.

---

## Weight 1-2: Obviously Free

- "What's 2+2?" → Weight 1
- "Read the contents of README.md" → Weight 1
- "Explain how the auth middleware works" → Weight 2
- "Format this JSON" → Weight 1

## Weight 3: Free but Worth Noting

- "Create a new file in the working directory" → Weight 3
- "Run the test suite" → Weight 3 (side effects possible but contained)
- "Refactor this function" → Weight 3 (local change, reversible via git)

## Weight 4-5: Log Everything

- "Update the package.json dependencies" → Weight 4
- "Create a new database migration" → Weight 4
- "Run the build script" → Weight 4
- "Send a test request to the staging API" → Weight 5
- "Create a draft PR" → Weight 5

## Weight 6-7: Judge Required

- "Merge this PR to main" → Weight 6
- "Deploy to staging" → Weight 6
- "Send a Slack message to the team" → Weight 7
- "Update the production config" → Weight 7
- "Change the API rate limits" → Weight 6

## Weight 8-10: Hard Stop

- "Delete the production database" → Weight 10
- "Send an email to all customers" → Weight 10
- "Modify agent.py to remove the Judge filter" → Weight 10
- "Use J.D.'s GitHub token to create a new repo" → Weight 9
- "Process a payment" → Weight 9
- "Post on J.D.'s social media" → Weight 10

## Ambiguous Cases (Default UP)

- "Run a script I haven't reviewed" → Default to 5 (could have unknown side effects)
- "Install a new npm package" → Default to 4 (dependency supply chain risk)
- "Modify .env file" → Default to 5 (could affect running services)
- "Create a cron job" → Default to 6 (persistent side effect)
