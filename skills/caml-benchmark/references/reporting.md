# Reading and reporting CAML results

## Where the numbers are

| File | What |
|---|---|
| `output/results.csv` | One row per job: framework × task × fold. Append-only, across every run on the server. |
| `output/sweeps/<sweep>/ledger.jsonl` | One record per sweep job: status (`ok`/`error`/`timeout`/`killed`/`crash`/`no_result`), wall time, host CPU and RAM, log path |
| `output/sweeps/<sweep>/logs/<fw>.<task>.<fold>.log` | The full output of one job |
| `input/datasets/<name>/dataset.json` | Provenance of the prepared data |

The `results.csv` columns you'll use:

| Column | Meaning |
|---|---|
| `framework`, `task`, `fold`, `constraint` | Identify the job |
| `type` | `binary`, `multiclass` or `regression` |
| `metric`, `result` | The primary metric and its value, **normalized so higher is better**: losses are stored negated, with a `neg_` prefix (`neg_rmse` = −RMSE) |
| `auc`, `logloss`, `acc`, `balacc`, `rmse`, `r2`, `mae` | Every computed metric, in its natural direction |
| `training_duration`, `predict_duration`, `duration` | Seconds |
| `models_count` | Models the framework trained, as it reports it |
| `version` | The framework's installed version |
| `app_version` | CAML's version and revision, e.g. `1.0.0 [main, 3eb1cf7]` (`+worktree` = uncommitted changes) |
| `seed` | The seed passed to the framework |
| `info` | The error message when the job failed (`result` is then empty) |
| `n_features_total`, `n_features_used`, `features_used` | Which input columns the final model used, where the framework exposes it |

`caml leaderboard` reads all of this for you. When the same job ran more
than once, it counts only the latest run.

## The two comparison tools

- **`caml leaderboard --benchmark B`**: per dataset, it ranks frameworks by
  the mean of the primary metric over the folds, with the standard
  deviation, the folds that succeeded and the mean training time.
  `--markdown` gives a table ready to paste. Filters: `--constraint`,
  `--task`, `--framework` (each repeatable).
- **`caml compare FW1 FW2 [FW3 ...] --benchmark B`**: tests significance
  **across datasets** (paired per task, with each task's folds averaged).
  For 2 frameworks it runs a Wilcoxon signed-rank test (plus a paired
  t-test); for 3 or more, a Friedman test with Holm-corrected pairwise
  tests. **It needs at least 2 tasks**, and a handful more before the
  p-values mean much. On a single dataset, use the leaderboard and talk
  about spread, not significance.

## How strong is a single-dataset result?

The folds are not independent experiments: the training sets overlap. Rules
of thumb that keep a report honest:

- A gap smaller than about **one standard deviation across folds** is a tie.
  Say "statistically indistinguishable on this data", not "X wins".
- Look at **the folds that succeeded**. A framework that scored well on 3 of 5
  folds and failed on 2 hasn't beaten one that completed all 5.
- **The budget matters.** Under `quick` (5 minutes), fast frameworks look
  better than they would with an hour. Before a decision, re-run the top
  2-3 under `1h8c`, with the same folds.
- **Training time is part of the result.** A framework that ties on score
  but trains 10× faster is often the better choice.

## Report template

Fill this in from the leaderboard, `dataset.json`, the ledger and
`results.csv`:

```markdown
## AutoML benchmark: <dataset name>

**Question**: which AutoML framework predicts `<target>` best on <dataset>?
**Setup**: <rows> rows, <columns> features, <task type>; <K>-fold stratified CV
(seed <seed>); <constraint> budget (<seconds> s per fold, <cores> cores);
server: <vCPU> vCPU, <RAM> GB RAM; CAML <app_version>.

| rank | framework | <metric> mean | std | folds ok | train s |
|---|---|---|---|---|---|
| ... paste `caml leaderboard --markdown` ... |

**Reading it**: <1-3 sentences: who leads, whether the gaps exceed the
fold-to-fold spread, the time/score trade-off>.

**Failures**: <framework>: <n> folds failed, <reason> (<limitation / budget / bug>).
**Not run**: <e.g. TabPFNClient: not permitted to upload this data>.

**Next step**: <e.g. re-run AutoGluon and H2O AutoML under 1h8c; or train the
winner on all data with its own API>.

Framework versions: <framework=version, ...>. Data SHA-256: <from dataset.json>.
```

Include CAML, AMLB and the compared frameworks in the references, and tell
the user you did (see "Citing CAML" in SKILL.md).

## Turning a winner into a model

CAML compares frameworks; it doesn't export a production model. To use the
winner, install that framework in the user's own environment and train it
on all of the data with its own API, using a similar budget (for example,
`TabularPredictor(label=...).fit(df, time_limit=300)` for AutoGluon). The
framework's page under `docs/frameworks/` shows how CAML calls it.
