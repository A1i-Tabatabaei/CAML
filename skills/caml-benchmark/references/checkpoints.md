# The three check-ins with the user

A CAML run takes hours and costs money. If you get the goal wrong, miss a
key or misread the task, all of that is wasted, and a misread task can also
give results that look fine but are wrong. So three
check-ins are **mandatory**. At each one, stop, ask, and **wait for the
user's answer**. Don't skip one because you think you can guess the answer:
guessing is exactly what goes wrong.

| # | Check-in | When | What waits for it |
|---|---|---|---|
| 1 | [The goal](#1-the-goal-benchmark-study-or-best-model) | Your first message, before you change anything on the server | The plan (frameworks, folds, budget) and the shape of the report |
| 2 | [Credentials](#2-credentials-keys-go-to-the-server-never-through-chat) | Right after setup. Installs can run meanwhile | TabPFN, and anything else that needs a key |
| 3 | [The task](#3-the-task-probe-then-confirm) | After the upload (and anonymization) and `describe-data` | `prepare-data` and the sweep |

Write each answer down: the goal and the plan go at the top of `report.md`,
and the confirmed task card goes in `task.md` in the report folder.

## 1. The goal: benchmark study, or best model?

Ask in your first message, together with your questions about anything
missing from the prompt. If the prompt already says, confirm it in one
line instead ("You want X, so I'll ..."). Template:

```text
Before I plan the run: what are the results for?

A) A benchmark study. The comparison itself is the result, and you'll write
   about it (an article, thesis or report). I'll run a broad, fair,
   reproducible comparison, report every framework including the ones that
   fail, and give you the methods and numbers you need to cite it.
B) The best model. You want the best-scoring model for this dataset and will
   use it in the rest of your project. I'll screen quickly, spend the budget
   on the top frameworks, and hand you the winner: how to train it, and if
   you want, a model trained on all of your data.
C) Both.
```

What changes with the answer:

| | A: benchmark study | B: best model |
|---|---|---|
| Frameworks | Every framework that can run, under identical budgets. Failures stay in the results | Screen them all briefly, then focus on the top 2–3 |
| Folds | 10 if the data has at least ~1,000 rows and the time allows, else 5. Same folds for everyone | 5 |
| Budget | One constraint for all: `1h8c` (AMLB's standard) if affordable, otherwise `quick`, and say so | `quick` to screen, then `1h8c` for the top 2–3 |
| More datasets | Offer to add OpenML tasks (`--benchmark validation`): a claim about frameworks in general needs several datasets, and `caml compare` needs at least 2 | Not needed |
| Report | Methods (setup, versions, seeds, hardware), the full leaderboard with spread, every failure with its reason, time against score, limitations, citations | One page: the winner, the runners-up within noise, the time and cost trade-off, and how to use the winner |
| Extra deliverable | The data behind the tables (the bundle) | Optionally, a model trained on all of the data ([reporting.md](reporting.md#handing-over-the-winner-goal-b)) |

"Both" means option A's run with option B's hand-over at the end.

## 2. Credentials: keys go to the server, never through chat

CAML reads API keys from the environment of the `caml` user on the server.
They're stored in `~caml/.caml-secrets` (mode 600) and loaded for every
`camlctl` command. **Never ask for a key in the chat, never put one in a
command line, and never read, print or copy one.** A key in the chat ends up
in the provider's logs. A key on a command line ends up in shell history
and the server's process list.

After setup, see what's there:

```bash
ssh caml-vps camlctl secrets --check
```

It prints one line per key: `TABPFN_TOKEN: set`, `missing` or
`placeholder`, with what each key is for. Never the value. Which keys you
need depends on the plan:

| Key | Needed when |
|---|---|
| `TABPFN_TOKEN` | `TabPFN` or `TabPFNClient` is in the plan ([tabpfn.md](tabpfn.md) says how the user gets one) |

That's the only key CAML's frameworks use today. The user can store others
under any NAME in capitals. Those reach camlctl's commands and your
`camlctl script` files, but a framework only sees the variables its
integration passes through, so don't promise that a key will reach one. If
nothing in the plan needs a key, say so and skip the rest of this check-in. Otherwise, offer the user two ways.

**Way 1 (preferred): they type it in.** It's one command, the same in
PowerShell, cmd, Terminal and any Linux terminal. They run it **in their own
terminal window**, not through your shell tool. It needs a real terminal,
and from your tool it stops with a message that says so. Template:

```text
TabPFN needs your Prior Labs API key on the server. Please run this in your
own terminal (not here):

    ssh -t caml-vps camlctl secrets

It asks for each key in turn. Paste the key and press Enter: nothing appears
while you paste, that's on purpose. Press Enter alone to skip a key. Tell me
when it says "Done". Please don't paste the key into this chat.
```

**Way 2: a file they fill in.** For users who'd rather use an editor.

1. Get the template with `ssh caml-vps camlctl secrets --template`, and
   write it to `caml-secrets.env` in the report folder **with your file
   tool**. Not with `>`: Windows PowerShell 5.1's `>` writes UTF-16 (the
   import copes with it, but other tools might not).
2. Ask the user to open it, type the keys after the `=` signs, save and
   close it, then tell you. The command that opens it for each OS is in
   your operator profile (section 4).
3. **From now on, don't open, read, print or copy that file.** You don't
   need to see it to move it.
4. Upload it, import it and delete both copies:

   ```bash
   scp caml-secrets.env caml-vps:caml-secrets.env
   ssh caml-vps camlctl secrets --import caml-secrets.env
   ```

   `--import` reads `NAME=value` lines (comments, blank lines, `export `,
   quotes, a BOM, CRLF and UTF-16 are all fine), stores the keys, **deletes
   the uploaded copy**, and prints only names, lengths and the check. It
   exits 1 if nothing was filled in. Then delete the local copy with your
   profile's delete command.

Either way, finish with `ssh caml-vps camlctl secrets --check`. Every key
the plan needs must say `set`.

- **The user has no key, or doesn't want one**: take TabPFN out of the plan,
  and say so in the report under "Not run".
- **A key was pasted into the chat** (or a log or a file) by mistake: tell
  the user to revoke it and create a new one. Don't use the pasted one.
- **Removing keys**: `camlctl secrets --remove NAME`, or `--remove --all`.
  Offer it at cleanup if the server stays.
- `camlctl tabpfn-token` (from 1.1.0) still works, for `TABPFN_TOKEN` only.

## 3. The task: probe, then confirm

You may guess the task from the data, but **the user decides it**. Probe
first, so that your questions are specific, then confirm everything that
shapes the benchmark before `prepare-data`.

### 3a. Personal data first

Ask early (it fits in your first message): "Does the file contain personal
data, like names, emails, phone numbers, addresses, or customer or patient
IDs? Has it been anonymized?" Then:

- **No, or already anonymized**: carry on.
- **Yes, not anonymized**: the user chooses.
  - They remove those columns themselves before uploading (for example by
    deleting them in Excel and exporting again). That's the safest, because
    the identifiers never leave their machine.
  - Or you remove them on the server, right after the upload and before
    anything else reads the file. That's 3b.

Either way, confirm that the user is fine with their data being copied to
their own server (ground rule 2).

### 3b. Upload, then remove identifiers

```bash
scp "/path/to/My Data.csv" caml-vps:churn.csv
ssh caml-vps camlctl dataset churn.csv
ssh caml-vps camlctl caml describe-data /home/caml/data/churn.csv
```

`describe-data` never prints cell values. It prints each column's kind,
missing share, distinct count and flags: `pii?` (it looks like personal data,
by its name or its values), `id-like` (unique on every row), `group-id?`
(several rows share an ID), `date`, `free-text`, `constant`, and `leak?`
once you give a target. Show the user the `pii?` and `id-like` columns and
propose one of two things for each:

- **drop** it: names, emails, phone numbers, addresses, free-text notes;
- **hash** it: an ID you still need, for example to keep one customer's rows
  in the same fold. Equal values stay equal, but they can't be reversed.

With the user's OK:

```bash
ssh caml-vps camlctl caml anonymize-data /home/caml/data/churn.csv --drop 2 --drop email --hash customer_id --out /home/caml/data/churn-anon.csv --delete-original
```

Columns go by name, or **by number** (from `describe-data`) when the name
has spaces or symbols. `--delete-original` deletes the uploaded file, and
the pre-conversion `.orig` copy if there is one. Tell the user plainly what
this does and doesn't do: it removes **direct** identifiers, but
combinations of ordinary columns (postcode, birth date, job title) can still
single people out. It is not anonymization in the legal sense. Record it in
`task.md`.

### 3c. Probe, and form your guess

```bash
ssh caml-vps camlctl caml describe-data /home/caml/data/churn-anon.csv
ssh caml-vps camlctl caml describe-data /home/caml/data/churn-anon.csv --target Churn
```

The first run lists `target_candidates`, each with the task type it implies.
They're guesses from the column names and kinds. The second run, with the
likely target, adds that column's class labels and counts (the only values
it prints), `leak?` flags (a column that predicts the target perfectly on
its own), the default metric, imbalance advice, `suggest_drop`, and
`ask_user`: the questions the data itself raises. Add `--json` if you'd
rather parse JSON.

### 3d. The task card: ask, and wait

Put everything that shapes the benchmark into one message. Mark what you
inferred, and ask about everything you couldn't know. Template (fill it in,
and leave out lines that don't apply):

```text
Here's the task as I understand it from the data. Please confirm, or correct
any line:

- Data: churn-anon.csv, 7,043 rows x 19 columns (Full Name and email
  dropped, customer_id hashed)
- Predict (y): Churn, column #21. What does it mean exactly? My guess: the
  customer cancelled within the contract period.
- Task type: binary classification (No 5,174 / Yes 1,869, 27% Yes).
  [Ambiguous: a 1-5 rating could be classes or a number. Which?]
- Features (X): all other columns, except the ones I'd leave out:
  - customer_id: unique on every row, so it teaches nothing
  - refund_flag: possible leak. It matches Churn exactly. Is it recorded
    after the customer leaves?
  - notes: free text. Frameworks treat it as one huge category. Drop it?
  Should every other column be used, or only some?
- Rows: are they independent? account_id repeats (one account, several
  rows): should one account's rows stay in the same fold? signup_date is a
  date: should the test folds be later in time than the training folds?
- Metric: AUC to rank (also log loss, accuracy, balanced accuracy). Is one
  kind of error worse for you than the other?
- Rows left out: 11 with no Churn value.
- Split: random, stratified 5-fold cross-validation, seed 42.

Reply "confirmed", or tell me what to change.
```

**Don't run `prepare-data` until the user confirms.** If they change the
target, run `describe-data --target NEW` again, and show the card again. A
reply that only answers some lines isn't a confirmation: ask about the rest.

### 3e. From the card to the command

| Card line | Option |
|---|---|
| Predict | `--target NAME` (or its number) |
| Task type | `--type binary\|multiclass\|regression`. Always pass it once confirmed, even if `auto` would agree |
| Features: leave some out | `--drop COL` for each (repeatable) |
| Features: only some | `--keep COL` for each feature to use (repeatable; not with `--drop`) |
| Metric | `--metric NAME`, repeatable. The first is the one frameworks optimize and the leaderboard ranks by |
| Split | `--folds K`, or `--folds 1 --test-size 0.2`; `--seed N` |
| Rows grouped or ordered in time | Not `prepare-data`: the manual split in [data-preparation.md](data-preparation.md) |

```bash
ssh caml-vps camlctl caml prepare-data /home/caml/data/churn-anon.csv --target Churn --type binary --drop customer_id --drop refund_flag --drop notes --metric auc --name churn --folds 5
```

Read `prepare-data`'s output back against the card (task type, rows,
feature count, metric, warnings), and write the confirmed card and the exact
command to `task.md`.

Special cases:

- **No obvious target**, or the user wants several things predicted: CAML
  benchmarks one target per task. Prepare each one as its own task
  (`--name churn`, `--name upsell`) and say so in the plan.
- **Dates**: a raw date becomes a category. Offer to drop it, or to derive
  numeric parts (year, month, weekday) with a small `camlctl script` before
  preparing.
- **Huge data** (more than ~1M rows, or RAM below 10× the file size): propose
  a random sample and say so in the card.
