# The Windows operator profile's commands, checked on real Windows.
#
# CI's operator-windows job runs this under Windows PowerShell 5.1 (what
# Windows ships) and PowerShell 7. It needs no server: it checks what the
# profile (skills/caml-benchmark/references/operator-windows.md) claims
# about this machine. Run from the repo root: .\tests\operator\windows.ps1
$ErrorActionPreference = 'Continue'
$script:failures = 0
function Check([string]$Name, [bool]$Ok, [string]$Detail = '') {
    if ($Ok) { Write-Host "ok    $Name" } else { Write-Host "FAIL  $Name $Detail"; $script:failures++ }
}
function Note([string]$Text) { Write-Host "note  $Text" }

Write-Host "PowerShell $($PSVersionTable.PSVersion) ($($PSVersionTable.PSEdition)) on $([Environment]::OSVersion.VersionString)"
Note "git core.autocrlf = $(git config --get core.autocrlf)"
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("caml-operator-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null

# 1. Everything that runs on the Ubuntu server keeps LF line endings in a
#    Windows checkout (.gitattributes), and in `git archive` output, which
#    is what provision_vps.sh pushes from Git Bash.
$serverFiles = @('scripts/camlctl') + (Get-ChildItem scripts -Filter *.sh | ForEach-Object { "scripts/$($_.Name)" })
foreach ($f in $serverFiles) {
    $bytes = [IO.File]::ReadAllBytes((Join-Path (Get-Location) $f))
    Check "LF in checkout: $f" (-not ($bytes -contains [byte]13))
}
git archive --format=tar -o "$tmp\archive.tar" HEAD scripts/camlctl scripts/bootstrap_vps.sh scripts/setup_workspace.sh
$systar = Join-Path $env:SystemRoot 'System32\tar.exe'
& $systar -xf "$tmp\archive.tar" -C $tmp
foreach ($f in 'scripts/camlctl', 'scripts/bootstrap_vps.sh', 'scripts/setup_workspace.sh') {
    $bytes = [IO.File]::ReadAllBytes((Join-Path $tmp $f))
    Check "LF in git archive: $f" (-not ($bytes -contains [byte]13))
}

# 2. The built-in tools the profile relies on.
foreach ($t in 'ssh', 'scp', 'ssh-keygen') {
    $cmd = Get-Command $t -ErrorAction SilentlyContinue
    Check "$t on PATH" ([bool]$cmd)
    if ($cmd) { Note "$t -> $($cmd.Source)" }
}
Check "Windows tar.exe present" (Test-Path $systar)
Note ("ssh -V: " + (cmd /c "ssh -V 2>&1"))

# 3. The SSH host alias, written the way the profile says (ASCII).
$cfg = Join-Path $tmp 'config'
@"
Host caml-vps
  HostName 203.0.113.10
  User root
  IdentityFile ~/.ssh/id_ed25519
  ServerAliveInterval 30
  ServerAliveCountMax 6
"@ | Add-Content -Encoding ascii -Path $cfg
$resolved = (ssh -G -F $cfg caml-vps 2>&1 | Out-String)
Check "ssh reads the alias: hostname" ($resolved -match '(?m)^hostname 203\.0\.113\.10\s*$') $resolved
Check "ssh reads the alias: user" ($resolved -match '(?m)^user root\s*$')
Check "ssh reads the alias: serveraliveinterval" ($resolved -match '(?m)^serveraliveinterval 30\s*$')
# The trap the profile warns about: Windows PowerShell 5.1's Out-File and >
# write UTF-16, which ssh can't parse. (PowerShell 7 writes UTF-8.)
$cfg16 = Join-Path $tmp 'config-utf16'
"Host caml-vps`n  HostName 203.0.113.10" | Out-File -FilePath $cfg16
$r16 = (ssh -G -F $cfg16 caml-vps 2>&1 | Out-String)
if ($r16 -match '(?m)^hostname 203\.0\.113\.10\s*$') { Note "Out-File config: ssh read it (PowerShell $($PSVersionTable.PSVersion.Major))" }
else { Note "Out-File config: ssh could NOT read it (PowerShell $($PSVersionTable.PSVersion.Major)): $($r16.Trim().Split([Environment]::NewLine)[0])" }

# 4. The documented remote command strings reach ssh unchanged. A native
#    program that prints its first argument stands in for ssh.
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    $echo = 'import sys; sys.stdout.write(sys.argv[1])'
    $got = & $py.Source -c $echo "command -v git || (apt-get update -qq && apt-get install -y -qq git)"
    Check "double-quoted remote command survives (git install)" ($got -eq 'command -v git || (apt-get update -qq && apt-get install -y -qq git)') $got
    $got = & $py.Source -c $echo "test -d /opt/caml-src || git clone -q https://github.com/A1i-Tabatabaei/CAML.git /opt/caml-src"
    Check "double-quoted remote command survives (clone)" ($got -eq 'test -d /opt/caml-src || git clone -q https://github.com/A1i-Tabatabaei/CAML.git /opt/caml-src') $got
    $got = & $py.Source -c $echo "mkdir -p ~/.ssh && chmod 700 ~/.ssh && tr -d '\r' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
    Check "double-quoted remote command survives (key copy)" ($got -eq "mkdir -p ~/.ssh && chmod 700 ~/.ssh && tr -d '\r' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys") $got
    $words = & $py.Source -c 'import sys; sys.stdout.write(chr(124).join(sys.argv[1:]))' camlctl start sweep caml sweep FLAML --benchmark input/datasets/churn/churn.yaml --constraint quick
    Check "bare-word camlctl command survives" ($words -eq 'camlctl|start|sweep|caml|sweep|FLAML|--benchmark|input/datasets/churn/churn.yaml|--constraint|quick') $words
    # Why the profile bans $ inside the quotes: PowerShell expands it here.
    $dollar = & $py.Source -c $echo "echo $HOME"
    Note "PowerShell turns ""echo `$HOME"" into: $dollar"
} else {
    Note "python not found; skipped the argument-passing checks"
}

# 5. SHA-256 the profile's way.
Set-Content -Path "$tmp\abc.txt" -Value 'abc' -NoNewline -Encoding ascii
$h = (Get-FileHash -Algorithm SHA256 "$tmp\abc.txt").Hash.ToLower()
Check "Get-FileHash SHA-256" ($h -eq 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad') $h

# 6. A result bundle (gzip tar, like camlctl bundle) unpacks with tar.exe.
if ($py) {
    & $py.Source -c "import io, tarfile, sys; t = tarfile.open(sys.argv[1], 'w:gz'); d = b'framework,result\nFLAML,0.9\n'; i = tarfile.TarInfo('run1/output/results.csv'); i.size = len(d); t.addfile(i, io.BytesIO(d)); t.close()" "$tmp\run1.tar.gz"
    Push-Location $tmp
    & $systar -xzf run1.tar.gz
    Pop-Location
    Check "tar.exe unpacks a bundle" (Test-Path (Join-Path $tmp 'run1\output\results.csv'))
}

# 7. Things the profile warns about, recorded for the field report.
$curl = Get-Command curl -ErrorAction SilentlyContinue
if ($curl) { Note "curl resolves to a $($curl.CommandType) ($($curl.Definition))" }

Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
if ($script:failures -gt 0) { Write-Host "$($script:failures) check(s) failed"; exit 1 }
Write-Host "all checks passed"
exit 0
