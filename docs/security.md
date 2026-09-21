# Security decisions

1. Web content is untrusted data and cannot change a run, execute tools, or grant approval.
2. Live crawling defaults to public HTTP(S) hosts only. Loopback, private, link-local, file, data, and custom schemes are refused.
3. Crawl4AI LLM extraction is disabled. Reasoning happens through the separate provider-neutral protocol.
4. Runs are create-only. Later work appends new artifacts or creates a new revision instead of overwriting evidence.
5. Raw page bodies are temporary by default. Durable artifacts retain normalized evidence, locators, metadata, and hashes under declared budgets.
6. Browser profiles, cookies, credentials, and proxies are out of scope for the first release.
7. MOZAK exports remain proposal-only and require ordinary owner acceptance.
