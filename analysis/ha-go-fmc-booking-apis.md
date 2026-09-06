# HA Go — 「預約家庭醫學診所」(Family Medicine Clinic booking) workflow & APIs

> **Scope & method.** Read-only static analysis of locally available code only
> (the decompiled `index.android.bundle`, Hermes HBC v96, via `hbc-decompiler`).
> No requests were sent to any HA service; no appointment was created, held, or
> cancelled; no auth/cert controls were touched. Personal data / tokens are not
> present in this document. Findings are marked **[verified]** (traced to a
> decompiled line), **[assumption]**, or **[unknown]**.

## Headline finding (why most booking APIs are not in local code)

HA Go is a **super-app**. Each feature ("mini-app" / "sub-app") is a **separate
React-Native bundle downloaded at runtime**, not shipped in the APK. The APK
`assets/` contains only three bundles — `index.android.bundle`,
`HkchLibrary.bundle`, `televisit.bundle` **[verified]**. The booking feature in the
screenshots, 「預約家庭醫學診所」, is served by **`fmcbooking.bundle`** (FMC = Family
Medicine Clinic), which is **not** in the APK.

The loader enumerates every mini-app bundle (`checkBundleName`,
`index_decomp.txt:760347-760381`) **[verified]**:

```
fmcbooking.bundle   gopcbooking.bundle   appointment.bundle   bookha.bundle
bookha3.bundle      televisit.bundle     easyq.bundle         pharmacy_queue.bundle  ...
```

- Downloaded via `DownloadSubAppManager.downloadSubApp` → `getSubAppMetadata`,
  validated as a zip (`isSubAppZipValid`), extracted to `SubAppFolderPath`
  (`index_decomp.txt:809500 DownloadSubAppManagerImpl`) **[verified]**.
- Manifest of available mini-apps + versions:
  **`https://hago-corp-module-resources-prd.hago.ha.org.hk/RF_2.10_index.json`** **[verified]**.
- App config / feature flags:
  `https://hago-corp-resources-prd.hago.ha.org.hk/hago-app-config/{config,user_config}.json` **[verified]**.

**Consequence:** the FMC clinic-list, availability/quota, earliest-slot, and
book/confirm/abandon calls are **inside `fmcbooking.bundle`** and are **[unknown]**
from local code. There is **no** clinic/quota/booking string or function in the
local bundle (grep for `clinicList`, `availableQuota`, `earliestSlot`,
`acceptBooking`, etc. → none) **[verified]**. To document those exact calls you
would need the downloaded `fmcbooking.bundle` (from a device's app storage, or the
zip referenced by the manifest) — obtaining it is out of scope for this read-only
local step.

## Screen → API mapping

| # | Screen (screenshot) | Backing bundle | API status |
|-|-|-|-|
| 1 | Region list (`離島`…) + clinic cards, availability badge (`暫時額滿`/`預約`), `診症名額狀況…更新` | `fmcbooking.bundle` (remote) | **[unknown]** — clinic-list-by-region + availability/quota poll |
| 2 | Earliest slot (`可提供最早的預約時間`), `接納預約`, `59秒後自動放棄` | `fmcbooking.bundle` (remote) | **[unknown]** — earliest-slot lookup + slot **hold** + confirm |
| 3 | Favourites (`已收藏診所`, `收藏`) | `index` + `fmcbooking` | **[assumption]** local storage (only generic `favorite(s)` strings; no favourites API found) |
| — | "Existing appointments" / home `My Calendar` (not screenshotted but part of workflow) | `index.android.bundle` (local) | **[verified]** — calendar aggregation service (below) |

## Verified local API — the appointment/calendar aggregation service

This is the only booking-adjacent API fully present in local code. The home
"My Calendar" / upcoming-events view (and any "my appointments" list) is served by a
**dedicated calendar service**, separate from the login gateway:

Base host `API_PATH_CALENDAR_PATH = https://hago-corp-calendar-srv-prd.hago.ha.org.hk/`
(`index_decomp.txt:719375`) **[verified]**.

| Method | Endpoint | Purpose | Key request fields | Role |
|-|-|-|-|-|
| POST¹ | `api/getEventByDateRange` | Events/appointments in a date window (paged) | `user_id`, `user_access_token`, `timestamp`, `device_info`, `request_credential{hago_client_id, app_id=client_id_hago_calendar}`, `start_date`, `end_date`, `event_type`, `items_no`, `language`, `last_event_item_key`, `isHistory` | Populates calendar / existing-appointments list |
| POST¹ | `api/getUpcomingEvent` | Next-30-days events ("Next 30 Days' Events") | same auth block; upcoming window | Home upcoming widget |
| POST¹ | `api/calendar/config` | Calendar display config (event types, filters) | auth block | Config for the calendar UI |

¹ Method **[assumption]**: dispatched through the shared `SubmitRequest` path (see
Auth model), which uses POST + the AES/RSA envelope; not an explicit `'GET'/'POST'`
literal at the call site.

- Request body traced at `_fetchCalendarRangeEvent` (`index_decomp.txt:740300-740430`)
  **[verified]** — field names quoted above.
- **Response [unknown]** in detail. The UI consumers imply a paged list of events
  each with a date, title, `event_item_key` (cursor via `last_event_item_key`), and a
  source mini-app tag; the footer text "please refer to each mini-app for all event
  details" indicates the calendar returns **summaries**, with full booking detail held
  by each mini-app **[verified: UI strings; response schema unknown]**.
- Locally, per-day reservations are read from the **Redux store**
  (`getReservations` selector, `index_decomp.txt:693734`, reads `state.reservations`),
  i.e. cached client-side and populated by the mini-apps — not a direct API read **[verified]**.

## Auth model (applies to every call above)

All app API calls go through the shared `SubmitRequest` pipeline documented in
`ha-go-login-api.md`: a per-request **AES-256-CBC** body encrypted and sent as
multipart `content`, with the AES key **RSA-wrapped** in `en_key`, plus
`Authorization: Bearer <app access_token>` **[verified, see ha-go-login-api.md]**.
The calendar body additionally carries a `user_access_token` and a
`request_credential` scoped to the calendar client (`client_id_hago_calendar`)
**[verified]**. Tokens redacted / not captured here.

## What the remote `fmcbooking.bundle` must implement (inferred from the UI)

The following are **[assumption]** based on the screenshots and normal booking
patterns — endpoints/fields are **[unknown]** until the bundle is analysed:

1. **Clinic list by region** — returns clinics per district (`離島`, etc.) with
   address and an availability badge; screen 1.
2. **Availability / quota poll** — the `診症名額狀況…更新` "as-of HH:MM … refresh"
   implies a lightweight, frequently-refreshed per-clinic quota status returning a
   state like *full* (`暫時額滿`) vs *bookable* (`預約`); screen 1. **[assumption]**
   this is a separate poll from the clinic list, given the timestamped "refresh".
3. **Earliest-slot lookup** — returns the earliest offered datetime for a chosen
   clinic ("可提供最早的預約時間 … 下午 4:15"); screen 2.
4. **Slot hold + confirm** — the `59秒後自動放棄` countdown strongly implies a
   **server-side hold/lock** on the offered slot with a ~60s TTL, confirmed by
   `接納預約` and released by `放棄預約`; screen 2. **[assumption]**
5. **Favourites** — likely local storage (screen 3), no favourites API observed
   locally. **[assumption]**

## Feasibility note for a personal availability dashboard

- The **aggregated appointment listing** (a user's own upcoming appointments) is a
  clean, documented call: `getEventByDateRange` / `getUpcomingEvent` on
  `hago-corp-calendar-srv-prd…` — feasible to model, subject to the auth envelope and
  `user_access_token` **[verified surface; response schema unknown]**.
- The **clinic availability** signal that the dashboard would most want (the
  `暫時額滿`/`預約` per-clinic status) lives in `fmcbooking.bundle` and is **[unknown]**
  from this analysis. Documenting it requires analysing that bundle next.
- All calls require a valid app token and the AES/RSA request envelope, and the
  availability poll is per-clinic and time-sensitive — any dashboard must respect the
  service's rate/refresh expectations and terms; this document does not exercise it.

## Hardcoded credentials (static-analysis finding)

The bundle ships a **hardcoded default app-config object** carrying client
credentials and the module-resources gateway key, as a plain string literal
(`index_decomp.txt:538941`) **[verified]**. These are **static, shipped in every
install, and not per-user/per-session** — a classic embedded-secret exposure.

| Field | Value (masked) | Role |
|-|-|-|
| `client_id` | `hk.org.ha.hago.hagoapp` | `request_credential` on API calls (non-secret id) |
| `client_secret` | `6c……` (10-char, redacted) | paired with `client_id` in `request_credential` (login/access-challenge, `300741`) |
| `cloud_API_Key` | `61b558a3-…-…d71be5` (UUID, redacted) | `API-Key:` header for the sub-app **manifest gateway** (`RF_2.10_index.json`) and referenced by the API envelope |
| `client_id_family_touch` | `hk.org.ha.hago.familytouch.cloud` | Family Touch service client id |
| `client_id_hago_calendar` | `hk.org.ha.hago.calendar.cloud` | Calendar service `app_id` in `request_credential` |

Consumers **[verified]**: `cloud_API_Key` → `213392` (DownloadSubAppManager),
`293615` (SubmitRequest envelope), `796984` (getVersionInfoApi), `806477`
(downloadBundleToTmp); `client_secret` → `300741` (request_credential builder).
Header name `API-Key` confirmed at `812400`.

> **Redaction note.** The full literal values are present in the local decompiled
> bundle at `index_decomp.txt:538941` and in the local (git-ignored) ledger. They
> are **masked here** deliberately: this is a live credential for a government
> health system's gateway, and committing a working key/secret to a git remote
> would republish it. Unmask in this file only with explicit owner instruction.

Empirically, this `cloud_API_Key` is **required** to read the manifest gateway
(a keyless `GET RF_2.10_index.json` returns **HTTP 401** [verified, single request],
which is why Method-B retrieval needs the app's own key — see the retrieval note in
chat).

## Sources

- `index.android.bundle` (Hermes HBC v96) → `hbc-decompiler` → `index_decomp.txt`.
  - `checkBundleName` (mini-app list): `760347-760381`
  - `DownloadSubAppManagerImpl`: `809500`; `downloadSubApp`: `758649`
  - Calendar constants (`API_PATH_CALENDAR_PATH`, endpoint names): `719375-719381`
  - `_fetchCalendarRangeEvent` request body: `740300-740430`
  - `getReservations` Redux selector: `693734`
- APK `assets/` bundle listing (fmcbooking absent).
- `bundle_strings.txt`: `RF_2.10_index.json`, resource/config hosts.
- Ledger: `re_out_hago/findings.json` (facts f7–f9).
- Auth envelope: `analysis/ha-go-login-api.md`.
