# Safari 12 compatibility and device acceptance

Target: iPad Air first generation A1474, iOS 12.5.8 Safari.

## Cause and implementation

The V1 initialization script contains optional chaining and nullish coalescing.
Safari 12 cannot parse these expressions, so none of that script runs; the static
header survives while the screen remains empty. After parsing is repaired, login
also depends on SubmitEvent.submitter and Object.fromEntries, absent on this device.

The existing HTML middleware serves offline Babel output for iOS 12/Safari 12
user agents on the same routes. It does not add a device mode or alternate page.
Modern agents keep original scripts. Normalized content hashes select compiled
inline scripts; the dynamic PAGE_BUILD value is restored from each current response.
Vary: User-Agent and representation-specific ETags prevent cache crossover.
No production npm dependency, runtime compiler or external compatibility CDN.

Feature-checked shims address current API use. CSS fallbacks cover viewport sizing,
unsupported sizing functions/inset, flex spacing and modal scrolling. Photo crop
and assistant dragging use touch events when Pointer Events are missing. Account,
JWT, assignment APIs, schema and data ownership are unchanged.

## Regeneration and regression

Use an isolated SQLite database, never production:

```sh
npm install --prefix /tmp/ios12-build --no-audit --no-fund @babel/core@7.28.5 @babel/preset-env@7.28.5 acorn@8.15.0
DATABASE_URL=sqlite:////tmp/ios12-build.sqlite3 python -m changying.compat_tools.build_safari12 /tmp/ios12-build/node_modules
pytest -q tests/test_safari12_compat.py tests/test_v1_html_etag.py tests/test_v1_auth_storage_contract.py tests/test_v1_cross_context_auth_handoff.py tests/test_student_wrong_practice.py
```

Optional DOM simulation (mock API, not an actual login/data acceptance):

```sh
npm install --prefix /tmp/ios12-build --no-audit --no-fund jsdom@22.1.0
node changying/compat_tools/simulate_safari12.cjs /tmp/ios12-build/node_modules /tmp/safari12-rendered.html
```

The route regression above writes `/tmp/safari12-rendered.html` from the actual
application response. This simulation removes newer browser APIs and exercises
first render, existing login submission, A logout/B login storage isolation and
modal closure/scroll unlocking. API responses are mocks, not production records.

The builder renders existing routes and Classic query variants through TestClient,
covers enabled/disabled homework and classroom-login flags, compiles unsupported syntax to the iOS 12 target, and checks ES2019 grammar and
regexp lookbehind. Assets are gzip/base64 text for GitHub review. Regenerate after
any inline script changes. Route coverage tests reject missing/stale snapshots;
they deliberately fail rather than silently serving stale business logic.
Generated files are not hand-edited. Source runtime.js/fallback.css remain readable.
ES2019 parsing is a conservative syntax check, not a complete Safari engine test.
Node VM shims, TestClient and DOM simulation cannot prove device layout or memory.

## Real-device acceptance (pending; no pass claimed)

Only run against a separately authorized deployment containing the PR commit.
Record deployed SHA, URL, iPad model, iOS version, date, network, screenshots/video
and observed result for every step. Current production has not been changed.

1. On the A1474, confirm Settings > General > About shows iOS 12.5.8. Open Safari
   directly, clear this site's website data, then open the ordinary website URL.
   Verify login form appears below the header on first load and refresh, with no
   blank body. Test portrait and landscape, address-bar expansion and scrolling.
2. Log in as test student A using an existing account. On a shared device leave
   Remember unchecked. Enter the normal student view. Verify menu, return, buttons,
   input keyboard, dialogs and dismissal; no invisible overlay should block taps.
3. Complete existing choice and written-answer assignments; submit once. Check
   teacher console receives A's answers and that A's score, learning points, wrong
   questions and learning history belong to A. Refresh to confirm persistence.
4. Upload a photo using the existing feature, drag each crop corner with one finger,
   cancel and reopen, then submit. Confirm crop, preview, scrolling and dismissal.
   Check assistant panel can be moved and closed without covering controls.
5. Explicitly log out. Verify login reappears. Log in as existing test student B
   on the same Safari session. Check B sees B's assignments/records and cannot
   reopen A's answer or upload through a stale page. Submit B's answer and verify
   teacher console/points/history attributes it to B. Test browser Back and refresh.
6. Log B out and A in again. Confirm A's submitted answers and records remain
   correct and B's data has not appeared. Repeat with Remember enabled then logout.
7. Check teacher classroom control and display routes if this device is used for
   teaching; exercise long content, nested scrolling, reveal-answer and review UI.
8. Repeat login, submission, upload and account switching on current Safari and
   Chrome. Compare behavior/data with the original system.

Acceptance remains pending until real iOS 12.5.8 evidence is recorded. A modern
browser with an old user agent, jsdom, or a current WebKit build is insufficient.
