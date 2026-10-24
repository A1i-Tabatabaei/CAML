# TabPFN: token, licenses and privacy

TabPFN is a pretrained tabular foundation model from Prior Labs. Instead of
searching, it predicts in one forward pass. CAML offers it two ways:

| | `TabPFN` (local) | `TabPFNClient` (hosted) |
|---|---|---|
| Where the model runs | On the server, CPU or GPU | Prior Labs' servers |
| **Does the user's data leave the server?** | No. The token only authorizes a one-time weight download. | **Yes: the training and test data are uploaded on every fit and predict.** |
| Size limits | On CPU, it refuses more than 1,000 training rows (TabPFN-3's guard); a GPU lifts this | Server-side limits per request and daily usage quotas |
| License | Code Apache-2.0-based; **model weights non-commercial** | Apache-2.0 client; Prior Labs' terms of service apply to the API |
| Needs `TABPFN_TOKEN` | For the first download of the weights | On every call |

## 1. Decide with the user

Ask before including either:

- **TabPFN (local)**: "TabPFN's model weights are licensed for
  non-commercial use only. Is this benchmark for non-commercial purposes
  (research, education, personal)? If not, check Prior Labs' license
  terms before using it."
- **TabPFNClient**: "TabPFNClient uploads your training and test data to
  Prior Labs' servers. Are you allowed to share this dataset with a third
  party?" Proceed only on a clear yes. Without it, leave TabPFNClient out
  and say so in the report.

Also check the size. On a CPU-only server, local TabPFN fails every fold
whose training split has more than 1,000 rows (with `--folds 5`, about
1,250 rows in total). Skip it on larger data, or tell the user it will show
up as failed folds and why.

## 2. Get a token (the user does this)

1. Register at https://ux.priorlabs.ai.
2. On the account's **Licenses** tab, accept the licenses. The local
   `TabPFN` needs the **TabPFN-3 model license**
   (`tabpfn-3-license-v1.0`); without it the weight download fails with
   `TabPFNLicenseError` even with a valid token. Accepting every license
   offered is simplest and also covers `TabPFNClient`.
3. Copy an API key from the account page.

## 3. Store it on the server, outside chat and git

This is check-in 2 in [checkpoints.md](checkpoints.md#2-credentials-keys-go-to-the-server-never-through-chat).
The user runs this themselves, from their own terminal (PowerShell, Windows
Terminal, macOS Terminal or a Linux terminal; not through the agent's shell
tool, because it needs a real terminal). It prompts with the input hidden,
so the key never appears on screen, in shell history or in the conversation:

```bash
ssh -t caml-vps camlctl secrets
```

Users who'd rather type the key into a file get `caml-secrets.env` from
`camlctl secrets --template`; the agent uploads it unread and imports it
with `camlctl secrets --import caml-secrets.env`, which deletes the
uploaded copy. Either way, the key ends up as `export TABPFN_TOKEN=...` in
`~caml/.caml-secrets` (mode 600), which `~caml/.profile` sources. That's
`~/.profile`, not `~/.bashrc`, because camlctl runs commands in a login
shell, which reads `~/.profile`, and Ubuntu's default `~/.bashrc` returns
early for non-interactive shells.

**Check**, without printing the key:

```bash
ssh caml-vps camlctl secrets --check
```

`TABPFN_TOKEN: set` means it's there. (`camlctl tabpfn-token --check`, from
1.1.0, still prints `token-set` or `token-missing`.)

If the user pasted a key into a chat, a log or a file by mistake, tell
them to revoke it and create a new one on ux.priorlabs.ai.

## 4. Install and smoke-test

```bash
ssh caml-vps camlctl install TabPFN
ssh caml-vps camlctl start tabpfn-smoke caml run TabPFN --benchmark test --constraint test
ssh caml-vps camlctl install TabPFNClient
```

The first installs the local model (a CPU torch wheel, or CUDA on a GPU
box). Install `TabPFNClient` only if the user agreed to the upload.

The first local run downloads the weights to `~/.cache/tabpfn` (once). A
missing or placeholder token fails fast, with an error that names
`TABPFN_TOKEN`.

## 5. In the report

- Say which variant ran. For TabPFNClient, say that the compute ran on Prior
  Labs' servers: its training time isn't comparable to the frameworks
  running on the server.
- Report TabPFN's 1,000-row CPU refusals as a hardware limit, not as poor
  model quality.
