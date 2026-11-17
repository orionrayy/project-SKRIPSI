# Mendeley API Integration (local, user-authorized)

**Status:** implementation candidate on `feature/mendeley-api-integration`; not yet merged or connected to a live account.

## Scope

The connector is a local Python-standard-library adapter over the documented Mendeley REST API. It does not automate clicks in Mendeley Desktop, inspect private desktop databases, scrape the website, or bypass subscription, library, copyright, or API access controls.

With an explicitly authorized Mendeley account, it exposes:

- OAuth 2.0 Authorization Code login, one-time `state`, refresh-token rotation, and private token storage.
- Profiles v2: read and update the authorized user's profile, retrieve a profile by ID, and list profiles visible to the account. Profile Search and follower/followee endpoints are retired and are deliberately not exposed.
- Document list/search/get/create/update/trash/restore/permanent delete; document types and deleted-document ID retrieval.
- Folder list/get/create/update/delete and document membership operations.
- Annotation list/get/create/update/delete.
- File listing, upload, download, and deletion using the API file resources and document-scoped file routes.
- Public Catalog search and document lookup. Profile search is not included because Mendeley retired that endpoint.
- Groups v2: list/get and the documented private-group, membership, invitation, join-request and limits operations supported by the current API contract. Public/invite-only group access, profile followers, public-group joining and popular-public-group search are not exposed; Mendeley retired the corresponding social/public-group capabilities. Legacy `/groups` endpoints are not used.
- Optional workspace sync. Preview is the default; applying it only appends new Mendeley metadata records as `METADATA_ONLY` with `rights_status=UNKNOWN`. It creates no claim-evidence links and does not promote metadata to reviewed evidence.

Not every Mendeley GUI function has a documented API equivalent. API endpoint coverage is bounded by Mendeley's published OpenAPI/REST reference and the permissions of the authorizing account. Availability of a feature in the desktop/web UI does not prove an API operation exists.

## Cost and terms

The Mendeley Developer Portal offers free API application registration. This connector has no third-party Python runtime dependency and does not require a paid SDK. This does not guarantee unlimited API requests, uptime, or that every account/API feature is available without provider limits.

Read the current Mendeley Developer API terms before registering or using the integration, especially sections covering multiple applications for the same use case and products that compete with Mendeley. This project must not assume that embedding Mendeley library operations in a commercial multi-client service is automatically permitted. Keep this branch as a personal/local integration candidate until the intended production use has been checked against the current terms or written permission has been obtained where required.

Reference pages:

- [Mendeley Developer Portal: application registration](https://dev.mendeley.com/myapps.html)
- [Authorization Code flow](https://dev.mendeley.com/reference/topics/authorization_auth_code.html)
- [Current API OpenAPI index](https://api.mendeley.com/apidocs/openapi)
- [Mendeley API reference](https://dev.mendeley.com/methods/)
- [Mendeley API change notice](https://www.elsevier.support/mendeley/answer/mendeley-api-changes)

### Retired Mendeley API features

Mendeley's API change notice records the removal of Profile Search and follower endpoints, and the removal of public/invite-only group capabilities. This connector intentionally omits those resources even though some older pages in the reference site still show examples. Public group joins and follower relationships are not supported. The private-group routes retained in this adapter are still subject to the permissions and live behavior of the account that authorizes the app.
- [Developer terms and conditions](https://dev.mendeley.com/terms-and-conditions.html)

## Register a Mendeley API application

1. Sign in to the Mendeley account that owns the library.
2. Open the Developer Portal application page and register one application for this use case.
3. Set the redirect URI to exactly `http://localhost:8765/mendeley/callback` (or choose another fixed localhost URI and use that exact string in both the portal and environment configuration).
4. Keep the resulting client ID and client secret private. Do not paste them into chat, issue trackers, screenshots, repository files, or source code.

Do not register multiple production applications for the same use case without checking the terms. Development/staging/production registration should follow the provider's documented exception and account rules.

## Configure locally

Python 3.10 or newer is required. The connector uses the standard library; no `mendeley` SDK or paid package is installed.

### Windows PowerShell

```powershell
$env:MENDELEY_CLIENT_ID = "YOUR_CLIENT_ID"
$env:MENDELEY_CLIENT_SECRET = "YOUR_CLIENT_SECRET"
$env:MENDELEY_REDIRECT_URI = "http://localhost:8765/mendeley/callback"
python -m pip install -e .
project-skripsi-mendeley login
```

### Linux, macOS, or Termux

```sh
export MENDELEY_CLIENT_ID='YOUR_CLIENT_ID'
export MENDELEY_CLIENT_SECRET='YOUR_CLIENT_SECRET'
export MENDELEY_REDIRECT_URI='http://localhost:8765/mendeley/callback'
python -m pip install -e .
project-skripsi-mendeley login
```

The redirect URI must match the application registration exactly. During `login`, a temporary HTTP listener is bound only to the loopback interface and the configured port/path. The browser opens the Mendeley consent page. Approve the requested access in Mendeley; the CLI then exchanges the authorization code and stores the resulting tokens locally.

The default credential file is `~/.project-skripsi/mendeley/tokens.json` (on Windows, under the user home directory). POSIX directory/file permissions are restricted to the current user where supported. Windows ACLs remain managed by Windows. Set `MENDELEY_TOKEN_FILE` or the global `--token-file` option only when a different private local path is necessary. Never place token files under the public repository.

If localhost callback hosting is unavailable, `auth-url` and `auth-exchange` provide a manual fallback. Treat the one-time state and callback code as sensitive, short-lived values.

## Verify the connection

```sh
project-skripsi-mendeley status
project-skripsi-mendeley profile
project-skripsi-mendeley documents --limit 50
project-skripsi-mendeley folders
project-skripsi-mendeley annotations
project-skripsi-mendeley files
```

`status` does not display tokens. A successful `profile` request confirms the token works against the live API; unit tests and a saved token file alone do not establish that.

## Work with the library

```sh
# Search the signed-in user's own library
project-skripsi-mendeley library-search "research methodology" --limit 20

# Search the public Catalog (not the private library)
project-skripsi-mendeley catalog-search --query "climate adaptation" --min-year 2018 --view all --limit 25

# Retrieve a Catalog item by DOI or by its Mendeley Catalog ID
project-skripsi-mendeley catalog-lookup --doi 10.1234/example
project-skripsi-mendeley catalog-get CATALOG_DOCUMENT_ID --view bib

# Retrieve one item, create or update metadata
project-skripsi-mendeley document-get DOCUMENT_ID
project-skripsi-mendeley document-create new-document.json
project-skripsi-mendeley document-update DOCUMENT_ID updated-fields.json --if-unmodified-since "Tue, 17 Nov 2026 00:00:00 GMT"

# Move an item to trash, restore it, or permanently delete it
project-skripsi-mendeley document-trash DOCUMENT_ID
project-skripsi-mendeley document-restore DOCUMENT_ID
project-skripsi-mendeley document-delete DOCUMENT_ID --confirm DOCUMENT_ID

# Folders, annotations, and files
project-skripsi-mendeley folder-create "Thesis references"
project-skripsi-mendeley folder-add-document FOLDER_ID DOCUMENT_ID
project-skripsi-mendeley annotation-create annotation.json
project-skripsi-mendeley document-files DOCUMENT_ID
project-skripsi-mendeley file-upload DOCUMENT_ID ./paper.pdf
project-skripsi-mendeley document-file-upload DOCUMENT_ID ./paper.pdf
project-skripsi-mendeley file-download FILE_ID ./paper-copy.pdf
project-skripsi-mendeley file-delete FILE_ID --confirm FILE_ID

# Groups v2
project-skripsi-mendeley groups --limit 100
project-skripsi-mendeley group-get GROUP_ID
project-skripsi-mendeley group-members GROUP_ID
project-skripsi-mendeley group-create new-group.json
project-skripsi-mendeley group-invite GROUP_ID invitations.json
project-skripsi-mendeley group-invitations --id GROUP_ID
```

Payload commands take a local JSON object file. Only use write commands when the intended changes are understood. Permanent deletion, folder deletion, file deletion, group deletion, member removal, leaving, and unfollowing operations require an exact confirmation identifier in the CLI. A confirmation flag is a local safety gate, not a provider-side undo mechanism. `document-update --if-unmodified-since` can send Mendeley's `If-Unmodified-Since` precondition to avoid overwriting a document changed after the caller's snapshot. Use the API-provided `last_modified` value in the format accepted by the HTTP header; do not guess it. The invitation API's documented email sending is currently disabled, so invitation creation does not guarantee that an email is sent.

## Import Mendeley library metadata into a thesis workspace

Preview first:

```sh
project-skripsi-mendeley sync-workspace .private/workspaces/PROJECT_ID
```

Apply only after reviewing the preview:

```sh
project-skripsi-mendeley sync-workspace .private/workspaces/PROJECT_ID --apply

# Remove local tokens from this machine (does not revoke the app grant at Mendeley)
project-skripsi-mendeley logout
```

The sync is append-only and stable-ID deduplicated. Existing source records are not overwritten. Imported items remain `METADATA_ONLY`, `UNKNOWN` rights, and have no exact content locator. The sync does not fetch article full text, infer access rights, create evidence claims, or mark the reference as reviewed. A private source-register backup and hash-chained audit event are created when changes are applied.

To treat a linked PDF as reviewed evidence, independently inspect the file and its license/access conditions, record the actual locator, and perform the project's human review gate. A reference-manager entry or attachment is not proof of copyright permission or claim support.

## Operational and safety model

- Read-only list/search/get calls may use a bounded retry policy and honor short `Retry-After` delays. Long provider-specified waits fail closed for manual retry.
- Mutating requests are never blindly retried after ambiguous network errors. Inspect Mendeley state before retrying a create/update/upload/delete that may have reached the server.
- OAuth state is one-use and expires after ten minutes. Access-token refresh is serialized and rotated tokens are atomically stored.
- API requests use HTTPS and explicit Mendeley resource media types. Pagination links are restricted to the configured API host.
- File upload/download is bounded to 100 MiB per operation. Signed download URLs are fetched without forwarding the Mendeley bearer token.
- Secrets, raw PDFs, library exports, private source registers, and user-specific API responses must not be committed to the public repository.
- Mendeley API rate limits, endpoint permissions, account policy, and provider availability may change. An HTTP/API test double is not a live integration test.

## Validation evidence

The isolated connector test suite covers OAuth state/refresh, private token storage, pagination, resource media types, library operations, group-v2 operations, file endpoints, error handling, retry behavior, ID/path validation, confirmation gates, and metadata-only workspace synchronization. Its passing result is not equivalent to a successful OAuth round-trip, a live API test, provider approval, or a full test run of the complete repository. The PR CI run must validate it against the real repository package and existing regression suite before merge.
