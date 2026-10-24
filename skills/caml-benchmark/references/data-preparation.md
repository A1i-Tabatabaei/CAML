# Preparing a dataset for CAML

## What the data should look like

- **One table, one row per example**, with a header row. CSV, TSV or
  Parquet. Export Excel or Numbers sheets to CSV first, preferably as
  **CSV UTF-8**. Since 1.0.1, `prepare-data` detects a `;`, tab or `|`
  separator from the header line, reads decimal commas (`1,5`) in
  semicolon files, and says so in a `WARNING` line. A file that isn't UTF-8
  (Excel's plain "CSV (Comma delimited)" on Windows is Windows-1252; old Mac
  exports are Mac Roman) is refused with the `iconv` command that converts
  it. `camlctl dataset` spots this as soon as the file is uploaded, and
  converts it with `--from-encoding` (below).
- **One target column.** Classification targets can be text (`yes`/`no`,
  `gold`/`silver`/`bronze`) or integers. Regression targets must be numeric.
- **Leave the features raw.** Don't impute, scale, one-hot encode or select
  features: every framework does its own preprocessing, and doing it before
  splitting leaks test information into training. Missing values (empty
  cells) are fine.
- **Do remove**:
  - row identifiers (`id`, `customer_id`, `uuid`): they're unique per row
    and teach nothing. `prepare-data` warns about columns that look like
    one;
  - **leaky columns**: anything recorded after the outcome, or computed
    from it. Ask the user about every column whose meaning is unclear;
  - free-text columns with mostly unique values (long descriptions,
    notes). Frameworks treat text as a high-cardinality category, which
    mostly costs memory.
- **Dates**: a raw date string becomes a category. Derive numeric parts
  (year, month, day of week, days since an event) before preparing, or drop
  the column.
- **True/False targets**: pandas reads them back as booleans, which trips at
  least one framework (FEDOT). Map them to two words (`yes`/`no`) first.
  `prepare-data` warns about this.

## Getting the file onto the server: `camlctl dataset`

Upload it under a simple name (no spaces), then hand it to `camlctl`:

```bash
scp "/path/on/your/machine/My Data.csv" caml-vps:churn.csv
ssh caml-vps camlctl dataset churn.csv
```

It moves the file to `/home/caml/data/` (owned by `caml`, mode 600) and
prints `key: value` lines: `sha256` (compare it with the hash of the local
file; the operator profiles show the command for each OS), `encoding`,
`line_endings`, `separator`, `columns`, `rows`, `header`, and finally
`status`:

| `status` | Meaning | Do |
|---|---|---|
| `ok` | UTF-8 text, or Parquet | Continue with the `next:` command |
| `needs-conversion` | Not UTF-8 | Ask the user which program exported it, then run the `fix:` command: `--from-encoding WINDOWS-1252` for Excel on Windows, `MACINTOSH` for old Mac exports. The original is kept as `NAME.orig`. |
| `unsupported` | An Excel workbook (zip) | Ask the user for a CSV UTF-8 export |

It refuses to overwrite a different file of the same name (exit 3) unless
you add `--replace`.

## Look before you prepare: `caml describe-data`

Probe the file without printing its values:

```bash
ssh caml-vps camlctl caml describe-data /home/caml/data/churn.csv
ssh caml-vps camlctl caml describe-data /home/caml/data/churn.csv --target churned
```

It prints `rows`, `columns`, `duplicate_rows`, then one numbered line per
column: its kind (`integer`, `numeric`, `categorical`, `boolean`,
`datetime`, `text`, `constant`, `one-value`, `empty`), missing share,
distinct count, and flags:

| Flag | Meaning | Usual action |
|---|---|---|
| `id-like` | Unique on every row | Drop it |
| `pii?` | Its name or most of its values look like personal data (names, emails, phone numbers, addresses, IBANs, card or IP numbers) | Drop it, or hash it with `anonymize-data` |
| `group-id?` | An ID column shared by several rows | Ask: must one ID's rows stay in one fold? Then a grouped split |
| `date` | Dates | Ask about time order; drop it, or derive parts |
| `free-text` | Long, mostly unique text | Usually drop it |
| `constant`, `mostly-missing`, `high-cardinality` | As named | Drop constants; ask about the others |
| `leak?` (with `--target`) | Predicts the target perfectly on its own, or whether it's empty does, or its name contains the target's | Ask whether it's known before the outcome |

Without `--target` it lists `target_candidates`, with the task type each one
implies. With `--target` it adds the task-type guess and why, the class labels
and counts (the only cell values it ever prints), the smallest class's share,
the default metric, imbalance advice, `suggest_drop` and `ask_user`. `--json`
prints the same as JSON. Use it for the task card in
[checkpoints.md](checkpoints.md#3-the-task-probe-then-confirm).

Columns whose names have spaces or symbols can't cross an ssh command line
unquoted, so pass them **by number**, the one `describe-data` prints:
`--target 21`, `--drop 4`. That works in `describe-data`, `anonymize-data`
and `prepare-data`.

## Removing identifiers: `caml anonymize-data`

```bash
ssh caml-vps camlctl caml anonymize-data /home/caml/data/churn.csv --drop 2 --drop email --hash customer_id --out /home/caml/data/churn-anon.csv --delete-original
```

`--drop` removes a column. `--hash` replaces each value with `h_` plus 16
hex digits of a salted SHA-256: equal values stay equal (so a grouped split
still works), and the salt is random and never stored, so the pseudonyms
can't be reversed or matched across runs. Missing values stay missing. The
output defaults to `NAME-anon.csv` next to the input (mode 600), and
`--delete-original` deletes the input and its `.orig` copy. It prints
`key: value` facts and no values. It removes **direct** identifiers.
Combinations of ordinary columns (postcode, birth date, job) can still
single people out, so it isn't anonymization in the legal sense.

## `caml prepare-data`

Run it on the server, through camlctl (the YAML it writes holds absolute
server paths), once the user has confirmed the task:

```bash
ssh caml-vps camlctl caml prepare-data /home/caml/data/churn.csv --target churned --type binary --drop customer_id --metric auc --name churn --folds 5
```

| Option | Default | Meaning |
|---|---|---|
| `--target COL` | required | The column to predict, by name or number |
| `--type auto\|binary\|multiclass\|regression` | `auto` | Task type. `auto` prints its reasoning; pass the type the user confirmed. |
| `--folds K` | 5 | K-fold cross-validation, stratified for classification. `1` = one holdout split. |
| `--test-size F` | 0.2 | Held-out share, only with `--folds 1` |
| `--drop COL` | none | Remove a column before splitting, by name or number (repeatable) |
| `--keep COL` | none | Use only these feature columns, by name or number (repeatable; not with `--drop`). The target is always kept. |
| `--metric NAME` | the task type's default | Metrics to score (repeatable). The first is the one frameworks optimize and the leaderboard ranks by. Written into the YAML and `dataset.json`. |
| `--name NAME` | the file's name | Task name in `results.csv` (letters, digits, `_`, `-`) |
| `--seed N` | 42 | Shuffle seed. The same seed and file give identical folds. |
| `--out DIR` | `<repo>/input/datasets` | Where the dataset folder goes (`input/` is gitignored) |
| `--force` | off | Overwrite an existing folder with the same name |

**How `auto` decides the type**: a non-numeric target with 2 values is
binary, with 3 or more it's multiclass. A numeric target with exactly 2
values is binary. An integer target with at most 10 distinct values is
multiclass, **with a warning** (it might be a count or a rating). Anything
else numeric is regression. Confirm the type with the user whenever it
printed a warning.

**What it refuses**, and what to do:

| Error | Fix |
|---|---|
| `Target column 'x' not found. Did you mean: ...` | Use the exact column name (it's case-sensitive) |
| `Class(es) ... have fewer than K rows` | Use fewer `--folds`, merge rare classes into an "other" label, or drop those rows |
| `Only N usable rows` | The dataset is too small to benchmark meaningfully |
| `Duplicate column names` | Rename the columns in the source file |
| `--type binary needs exactly 2 target values` | The target has a different number of classes than you thought; check it |

**What it writes** (`input/datasets/<name>/`):

- `<name>_train_<k>.csv`, `<name>_test_<k>.csv`: the folds. With
  `--folds 2` or more, the test folds are disjoint and together cover every
  row.
- `<name>.yaml`: the benchmark definition. Pass its path to `--benchmark`.
- `dataset.json`: provenance (the source file's SHA-256, row and column
  counts, class counts, seed, split method, time, CAML version). Quote it in
  the write-up.

Rows with a missing target are dropped, with a warning.

## Choosing folds and the budget

| Dataset size | Suggestion |
|---|---|
| < 1,000 rows | `--folds 5` (or 10); scores vary a lot between folds, so report the spread |
| 1,000 – 100,000 rows | `--folds 5`, `--constraint quick` to screen, then `1h8c` for the top frameworks |
| > 100,000 rows | `--folds 3`, or `--folds 1 --test-size 0.2`. Check RAM: at least 10× the CSV's size. |

For very large data, a random sample of 50k–200k rows usually ranks
frameworks the same way, much faster. If you sample, say so in the report.

## Choosing the metric

Defaults: binary → `auc`, multiclass → `logloss`, regression → `rmse`. The
first metric listed is the one frameworks are told to optimize (where they
support it) and the one the leaderboard ranks by. The others are also
computed and stored. To change them, pass `--metric` to `prepare-data`
(`--metric balacc --metric auc`), which checks that each one fits the task
type. It writes a `metric:` list under the task in the YAML, which you can
also edit by hand:

```yaml
- name: churn
  folds: 5
  metric: [balacc, auc, logloss]
  dataset: ...
```

| Task | Metric names CAML can score |
|---|---|
| binary | `auc`, `logloss`, `acc`, `balacc`, `f1`, `f05`, `f2`, `pr_auc` |
| multiclass | `logloss`, `acc`, `balacc`, `auc_ovr`, `auc_ovo` |
| regression | `rmse`, `mae`, `r2`, `mse`, `msle`, `rmsle` |

For imbalanced classes (smallest class under about 5% of rows), prefer
`balacc`, and `pr_auc` for binary tasks. `prepare-data` warns when it sees
strong imbalance. A framework that has no equivalent of the chosen metric
optimizes its own default instead, but every framework is still scored on
the chosen metric.

## When random folds are wrong: write the YAML by hand

`prepare-data` shuffles rows. That's wrong when:

- **Rows are time-ordered**, and the model will predict the future: train
  on the past, test on later data.
- **Rows are grouped** (several rows per patient, customer or device): one
  group's rows must not appear in both train and test.

Split the data yourself, on the server, with a short Python script (for
example, train on rows before a cutoff date and test on rows after it, or
use scikit-learn's `GroupKFold`). Write it on your machine, `scp` it over,
and run it with `ssh caml-vps camlctl script split.py`: it runs as `caml`
in the repo, with pandas and scikit-learn available. Write each fold as a
pair of CSV files with identical columns, and create the YAML:

```yaml
---
- name: sales_forecast
  folds: 2
  dataset:
    target: "units_sold"
    type: regression            # always set it: a numeric 0/1 target would otherwise be read as regression
    train:
      - "/home/caml/data/sales_train_0.csv"
      - "/home/caml/data/sales_train_1.csv"
    test:
      - "/home/caml/data/sales_test_0.csv"
      - "/home/caml/data/sales_test_1.csv"
```

Use absolute paths, keep `folds` equal to the number of file pairs, and
always set `type`. Several tasks (several datasets) can share one YAML file:
each `- name:` entry is one task, and `caml compare` can then test across
them.
