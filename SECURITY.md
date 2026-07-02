# Security Policy

## Supported versions

The latest released `2.x` line receives security fixes.

## Reporting a vulnerability

Please report suspected vulnerabilities privately, not in a public issue:

- Open a **GitHub Security Advisory** ("Report a vulnerability" under the repository's *Security* tab), or
- email **massimiliano.caretti@gmail.com** with a clear description and, if possible, a minimal reproduction.

You will receive an acknowledgement within a reasonable time. Please allow a fix to be prepared before any
public disclosure. There is no bug-bounty program.

## Scope and design notes

OUTLIER_MCB is a pure-Python library with **zero required runtime dependencies** and, by default, performs
**no network access and executes no external code**. Capabilities that touch the network (online prior-art
providers), run a repository's tests, or invoke an external prover/CAS/LLM are **opt-in and named**; when you
enable them you are responsible for the trust boundary of the endpoints, repositories, and models you supply.
The library does not transmit your prompts anywhere on its own.
