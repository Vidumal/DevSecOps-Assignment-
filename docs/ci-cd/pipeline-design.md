# CI/CD pipeline design and evidence

Use this page to document the actual workflow in .github/workflows/. Update the descriptions after checking the workflow and attach screenshots or scanner logs from real runs.

## Required gates

| Gate | Record in the report |
|---|---|
| Build | What is built, the command, and the successful/failed run |
| SAST (Semgrep) | Rule set, findings relevant to the four selected flaws, and before/after results |
| Dependency scan (Trivy) | Scan target, severity threshold, relevant findings, and before/after results |
| Secret scan (Gitleaks) | Scan scope and result; never include real secrets in evidence |
| Container scan (Trivy) | Exact image/tag scanned, severity threshold, relevant findings, and before/after results |

## Evidence to collect

- evidence/10-pipeline/blocking-run/: a real run showing at least one configured gate returning failure and blocking the workflow.
- evidence/10-pipeline/passing-run/: a real run after remediation showing the resulting gate statuses.
- The assignment asks for evidence of a blocking gate. Capture the failed job details, the finding, and the workflow summary. Do not present a planned run as completed evidence.
- Keep baseline and remediated evidence separate under each vulnerability folder. Include the request/response or scanner output, a short explanation, and the corresponding commit or run identifier where available.

## Important repository state

This file is an evidence checklist, not a claim that the four flaws are fixed or that all gates pass. Confirm the current source, workflow, and scan results before writing conclusions in the report.
