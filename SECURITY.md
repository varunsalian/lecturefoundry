# Security policy

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Report it
privately through GitHub's **Security > Report a vulnerability** flow for this
repository. Include reproduction steps, affected versions, and the potential
impact where possible.

## Credential safety

- Treat Coursera `CAUTH` values and AI provider keys like passwords.
- Supply secrets only through a hidden prompt, environment variable, or secret
  manager. Never place literal secrets in `lecture.toml`.
- Do not attach transcripts, generated course pages, cookies, or credentials to
  issues or pull requests.
- Review the remote-provider notice before sending a transcript to an online AI
  service.

There is currently no formal security-support window while the project is in
alpha. Security fixes will be documented in GitHub releases when releases are
available.
