param(
  [Parameter(Mandatory=$true)][string]$Org,
  [int]$Limit = 25,
  [string]$BranchName = "chore/add-quality-gate",
  [string]$ReusableRef = "gschull/software-quality-collapse/.github/workflows/quality-gate-reusable.yml@v0.1.0",
  [string]$PyMutationMin = "80",
  [string]$JavaMutationMin = "80",
  [string]$JavaCvss = "5.0"
)

Write-Host "Rolling out Quality Gate to org '$Org' (limit=$Limit)" -ForegroundColor Cyan

try { gh --version | Out-Null } catch { Write-Error "GitHub CLI (gh) not found."; exit 1 }

$repos = gh repo list $Org --limit $Limit --json nameWithOwner --jq ".[].nameWithOwner"
foreach ($r in $repos) {
  $name = $r.Split('/')[1]
  $tmp = Join-Path $PWD "tmp\$name"
  if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
  Write-Host "Processing $r" -ForegroundColor Yellow
  gh repo clone $r $tmp -- -q
  Push-Location $tmp
  try {
    git checkout -b $BranchName | Out-Null
    $wfDir = ".github\workflows"
    New-Item -Force -ItemType Directory $wfDir | Out-Null
    $content = @"
name: Quality Gate
on: pull_request
jobs:
  quality-gate:
    uses: $ReusableRef
    with:
      py_mutation_min: '$PyMutationMin'
      py_dep_health_fail: 'true'
      java_mutation_min: '$JavaMutationMin'
      java_cvss_threshold: '$JavaCvss'
"@
    $wfPath = Join-Path $wfDir "quality-gate.yml"
    $content | Set-Content -Encoding UTF8 $wfPath
    git add $wfPath
    git commit -m "chore: add Quality Gate workflow (initial thresholds $PyMutationMin/$JavaMutationMin, CVSS $JavaCvss)" | Out-Null
    git push --set-upstream origin $BranchName | Out-Null
    gh pr create --title "Add Quality Gate workflow" --body "Adds org-standard Quality Gate with initial thresholds and dep health." | Out-Null
    Write-Host "Opened PR for $r" -ForegroundColor Green
  } catch {
    Write-Warning "Failed for $r: $($_.Exception.Message)"
  } finally {
    Pop-Location
    Remove-Item -Recurse -Force $tmp
  }
}

Write-Host "Done. Review PRs in GitHub and make the check required in branch protection." -ForegroundColor Cyan
