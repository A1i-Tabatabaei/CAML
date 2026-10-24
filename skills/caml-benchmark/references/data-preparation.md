# Preparing a dataset for CAML

## What the data should look like

- **One table, one row per example**, with a header row. CSV, TSV or
  Parquet. Export Excel or Numbers sheets to CSV first, preferably as
  **CSV UTF-8**. Since 1.0.1, `prepare-data` detects a `;`, tab or `|`
  separator from the header line, reads decimal commas (`1,5`) in
  semicolon files, and says so in a `WARNING` line. A file that isn't UTF-8
  (an older "CSV (Comma delimited)" or Mac Roman export) is refused with
  the `iconv` command that converts it.
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

## `caml prepare-data`

```bash
uv run caml prepare-data DATA_FILE --target COLUMN [options]
```

| Option | Default | Meaning |
|---|---|---|
| `--target COL` | required | The column to predict |
| `--type auto\|binary\|multiclass\|regression` | `auto` | Task type. `auto` prints its reasoning; override it when that's wrong. |
| `--folds K` | 5 | K-fold cross-validation, stratified for classification. `1` = one holdout split. |
| `--test-size F` | 0.2 | Held-out share, only with `--folds 1` |
| `--drop COL` | none | Remove a column before splitting (repeatable) |
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
computed and stored. To change them, add a `metric:` list under the task in
the YAML:

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

Split the data yourself (for example, train on rows before a cutoff date and
test on rows after it, or use scikit-learn's `GroupKFold`), write each fold
as a pair of CSV files with identical columns, and create the YAML:

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
